#!/usr/bin/env python3
"""유튜브 계정을 연결한다 — PC 없이, 버튼 하나로.

    python3 src/yt_connect.py

왜 이 방식인가
    유튜브에 자동으로 영상을 올리려면 '갱신 토큰(refresh token)' 이 있어야 한다.
    토큰 = 비밀번호 대신 쓰는 긴 문자열. 한 번 받아 두면 계속 쓴다.

    보통은 PC에서 프로그램을 켜고 브라우저가 뜨면 로그인하는 방식으로 받는다.
    그런데 운영자는 **아이폰만** 쓰고 터미널이 없다. 그 방식은 아예 불가능하다.

    그래서 **TV 로그인 방식**(공식 이름: OAuth 2.0 Device Flow)을 쓴다.
    스마트TV에서 유튜브에 로그인할 때 화면에 코드가 뜨고, 폰으로 주소에 들어가
    그 코드를 넣으면 TV가 로그인되는 그 방식이다. 똑같이 한다.

      ① 이 프로그램이 구글에 '코드 하나 주세요' 하고 요청한다
      ② 구글이 주소와 8자리 코드를 준다  → 화면과 텔레그램으로 보여준다
      ③ 운영자가 폰 브라우저에서 그 주소에 들어가 코드를 넣고 '허용' 을 누른다
      ④ 이 프로그램은 그동안 구글에 계속 물어본다 — "허락됐나요?"
      ⑤ 허락되면 갱신 토큰을 받아 요약 화면에 적는다

    운영자가 하는 일은 **주소 열기 · 코드 넣기 · 허용 누르기** 뿐이다.

⚠️ 구글 클라우드에서 만든 열쇠의 **종류가 'TV 및 제한된 입력 장치' 여야 한다.**
   '웹 애플리케이션' 으로 만들면 이 방식이 통하지 않는다.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

DEVICE_URL = "https://oauth2.googleapis.com/device/code"
TOKEN_URL = "https://oauth2.googleapis.com/token"
GRANT = "urn:ietf:params:oauth:grant-type:device_code"

# 업로드 코드(upload.py)가 실제로 하는 일에 맞춘 권한.
#   youtube.upload    영상 올리기
#   youtube.force-ssl 자막 넣기 · 고정댓글 달기 · 재생목록 만들기
#
# ⚠️ TV 로그인 방식은 **아무 권한이나 받아주지 않는다.** 구글이 허용한 목록만 통한다.
#    어느 조합이 통하는지는 계정·앱 설정에 따라 다를 수 있어서, 위에서부터 차례로
#    시도하고 **먼저 되는 것을 쓴다.** 하나 막혔다고 손님이 다시 나를 찾아오게 만들지 않는다.
#    아래로 갈수록 권한이 넓다(= 덜 정밀하다). 그래서 좁은 것부터 시도한다.
SCOPE_TRY = [
    "https://www.googleapis.com/auth/youtube.upload "
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/youtube",
]
if os.environ.get("YT_SCOPE", "").strip():
    SCOPE_TRY = [os.environ["YT_SCOPE"].strip()]


def post(url, data):
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read()), None
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return json.loads(raw), e.code
        except Exception:
            return {"error": "http_error", "error_description": raw[:300]}, e.code


def summary(text):
    """GitHub 요약 화면에 적는다. 없으면(로컬 실행) 그냥 화면에 찍는다."""
    p = os.environ.get("GITHUB_STEP_SUMMARY")
    if p:
        with open(p, "a", encoding="utf-8") as f:
            f.write(text + "\n")
    else:
        print(text)


def telegram(text):
    """텔레그램으로 알린다. 설정이 없으면 조용히 건너뛴다 — 실패해도 죽지 않는다."""
    tok = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not (tok and chat):
        return
    try:
        post(f"https://api.telegram.org/bot{tok}/sendMessage",
             {"chat_id": chat, "text": text, "disable_web_page_preview": "false"})
    except Exception:
        pass


def die(msg, hint=""):
    summary(f"## 유튜브 연결 실패\n\n{msg}\n")
    if hint:
        summary(hint)
    print(f"::error::{msg}")
    sys.exit(1)


def main():
    cid = os.environ.get("YOUTUBE_CLIENT_ID", "").strip()
    sec = os.environ.get("YOUTUBE_CLIENT_SECRET", "").strip()
    if not cid or not sec:
        die("YOUTUBE_CLIENT_ID 와 YOUTUBE_CLIENT_SECRET 이 먼저 등록돼 있어야 합니다.",
            "저장소 → Settings → Secrets and variables → Actions 에 두 개를 넣고 다시 실행하십시오.")

    # ① 구글에 코드를 요청한다 — 권한 조합을 위에서부터 시도해 먼저 되는 것을 쓴다
    got, scope_used, last = None, "", {}
    for sc in SCOPE_TRY:
        res, _ = post(DEVICE_URL, {"client_id": cid, "scope": sc})
        if "device_code" in res:
            got, scope_used = res, sc
            break
        last = res
        err = res.get("error", "")
        if err == "invalid_client":
            break                      # 열쇠 자체가 틀린 것 — 권한을 바꿔도 소용없다
        print(f"  권한 조합이 거절됨({err}) — 다음 조합으로 시도합니다", flush=True)

    if got is None:
        err = last.get("error", "")
        desc = last.get("error_description", "")
        hint = ""
        if err == "invalid_client":
            hint = ("**열쇠 종류가 잘못됐을 가능성이 큽니다.** 구글 클라우드에서 OAuth 클라이언트를\n"
                    "만들 때 애플리케이션 유형을 **'TV 및 제한된 입력 장치'** 로 골라야 합니다.\n"
                    "'웹 애플리케이션' 으로 만들었다면 새로 만들어 주십시오.\n")
        else:
            hint = ("시도해 본 권한 조합이 모두 거절됐습니다.\n\n```\n"
                    + "\n".join(SCOPE_TRY) + "\n```\n")
        die(f"구글이 코드를 주지 않았습니다. (`{err}`) {desc}", hint)
    print(f"  쓸 권한: {scope_used}", flush=True)

    user_code = got["user_code"]
    url = got.get("verification_url") or got.get("verification_uri")
    interval = max(5, int(got.get("interval", 5)))
    expires = int(got.get("expires_in", 1800))

    msg = (f"판결극장 유튜브 연결\n\n"
           f"1) 이 주소를 여세요\n{url}\n\n"
           f"2) 이 코드를 넣으세요\n{user_code}\n\n"
           f"3) '허용' 을 누르시면 끝납니다.\n"
           f"({expires // 60}분 안에 하셔야 합니다)")
    print("\n" + "=" * 52)
    print(msg)
    print("=" * 52 + "\n", flush=True)
    telegram(msg)
    summary(
        "## 유튜브 연결 — 지금 폰에서 해주십시오\n\n"
        f"### 1단계. 이 주소를 누르십시오\n\n[{url}]({url})\n\n"
        f"### 2단계. 이 코드를 넣으십시오\n\n```\n{user_code}\n```\n\n"
        "### 3단계. 계정을 고르고 **허용** 을 누르십시오\n\n"
        f"- {expires // 60}분 안에 하셔야 합니다.\n"
        "- 채널이 여러 개면 **판결극장** 채널을 고르십시오.\n"
        "- '이 앱은 확인되지 않았습니다' 가 뜨면 **고급 → 안전하지 않은 페이지로 이동** 을 누르십시오.\n"
        "  (본인이 만든 앱이라 그렇습니다)\n\n---\n")

    # ④ 허락될 때까지 구글에 계속 물어본다
    deadline = time.time() + expires
    waited = 0
    while time.time() < deadline:
        time.sleep(interval)
        waited += interval
        res, _ = post(TOKEN_URL, {
            "client_id": cid, "client_secret": sec,
            "device_code": got["device_code"], "grant_type": GRANT,
        })
        err = res.get("error")
        if not err:
            break
        if err == "authorization_pending":
            if waited % 30 == 0:
                print(f"  기다리는 중… {waited}초", flush=True)
            continue
        if err == "slow_down":
            interval += 5
            continue
        if err == "access_denied":
            die("허용이 거부됐습니다. 다시 실행해 '허용' 을 눌러 주십시오.")
        if err == "expired_token":
            die("시간이 지나 코드가 만료됐습니다. 다시 실행해 주십시오.")
        die(f"구글이 거절했습니다. (`{err}`) {res.get('error_description', '')}")
    else:
        die("시간 안에 허용되지 않았습니다. 다시 실행해 주십시오.")

    refresh = res.get("refresh_token", "")
    if not refresh:
        die("갱신 토큰이 오지 않았습니다.",
            "이미 연결한 적이 있는 계정이면 구글이 토큰을 다시 주지 않습니다.\n"
            "[이 주소](https://myaccount.google.com/connections) 를 열어 **Third-party apps "
            "with account access** (구글 계정 화면은 영어면 이 이름, 한글이면 '타사 앱 및 서비스')"
            "목록에서 이 앱을 찾아 연결을 지우고 다시 실행해 주십시오.\n")

    # ⑤ 받은 토큰이 진짜 되는지 그 자리에서 확인한다
    who, _ = post(TOKEN_URL, {
        "client_id": cid, "client_secret": sec,
        "refresh_token": refresh, "grant_type": "refresh_token",
    })
    ok = "access_token" in who

    print("::add-mask::" + refresh)          # 로그에는 남기지 않는다
    summary(
        "## 연결됐습니다\n\n"
        + (f"받은 토큰으로 접속까지 확인했습니다.\n\n" if ok
           else "⚠️ 토큰은 받았지만 접속 확인에 실패했습니다. 그래도 아래 값을 넣어 보십시오.\n\n")
        + "### 마지막 한 단계\n\n"
        "아래 값을 복사해 **저장소 → Settings → Secrets and variables → Actions** 에서\n"
        "`YOUTUBE_REFRESH_TOKEN` 이라는 이름으로 새 시크릿을 만들어 넣으십시오.\n\n"
        f"```\n{refresh}\n```\n\n"
        "> ⚠️ **넣으신 뒤에는 이 실행 기록을 지워 주십시오.**\n"
        "> 이 화면에 토큰이 그대로 적혀 있습니다. 오른쪽 위 `...` → **Delete workflow run**.\n"
        "> 토큰은 유튜브 계정에 영상을 올릴 수 있는 열쇠입니다.\n")
    telegram("판결극장 유튜브 연결이 끝났습니다.\n"
             "GitHub 요약 화면에서 토큰을 복사해 시크릿에 넣어 주세요.\n"
             "넣으신 뒤에는 그 실행 기록을 지워 주세요.")
    print("연결 완료. 요약 화면을 보십시오.")


if __name__ == "__main__":
    main()
