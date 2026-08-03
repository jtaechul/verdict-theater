#!/usr/bin/env python3
"""유튜브 계정을 연결한다 — PC 없이, 버튼 하나로.

    python3 src/yt_connect.py --request    코드를 받아 파일·요약에 적는다 (몇 초)
    python3 src/yt_connect.py --poll       허용될 때까지 기다렸다 토큰을 받는다

왜 두 단계로 나누나 (⭐ 중요 — 처음엔 한 단계였고 그게 실패했다)
    처음에는 '코드 받기 + 기다리기' 를 한 단계에 넣었다. 그랬더니
      · 그 단계가 계속 실행 중이라 **요약 화면이 안 뜬다** (요약은 단계가 끝나야 올라간다)
      · 실행이 끝나야 로그를 받을 수 있어서 **클로드도 코드를 못 읽는다**
      · 결국 손님이 폰에서 실행 중인 로그를 손으로 헤집어야 했다
    그래서 나눈다. 코드 받기는 몇 초 만에 끝나고, 그 순간
      ① 요약 화면에 주소·코드가 뜨고
      ② 첨부파일(artifact)로도 올라가 **클로드가 직접 읽어 손님에게 건넬 수 있다**
    기다리는 일은 그다음 단계가 따로 한다.

TV 로그인 방식(OAuth 2.0 Device Flow)
    스마트TV에서 유튜브에 로그인할 때 화면에 코드가 뜨고, 폰으로 주소에 들어가
    그 코드를 넣으면 TV가 로그인되는 그 방식이다. PC도 터미널도 필요 없다.
    손님이 하는 일은 **주소 열기 · 코드 넣기 · 허용 누르기** 뿐이다.

⚠️ 구글 클라우드에서 만든 열쇠의 **종류가 'TV and Limited Input devices' 여야 한다.**
   'Web application' 으로 만들면 이 방식이 통하지 않는다.
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DEVICE_URL = "https://oauth2.googleapis.com/device/code"
TOKEN_URL = "https://oauth2.googleapis.com/token"
GRANT = "urn:ietf:params:oauth:grant-type:device_code"

OUT = Path("connect_out")          # 첨부파일로 올릴 폴더
CODE_FILE = OUT / "device.json"    # 코드 받기 단계가 남기는 것
TOKEN_FILE = OUT / "token.txt"     # 기다리기 단계가 남기는 것

# 업로드 코드(upload.py)가 실제로 하는 일에 맞춘 권한.
#   youtube.upload    영상 올리기
#   youtube.force-ssl 자막 넣기 · 고정댓글 달기 · 재생목록 만들기
#
# ⚠️ TV 로그인 방식은 **아무 권한이나 받아주지 않는다.** 구글이 허용한 목록만 통한다.
#    어느 조합이 통하는지는 계정·앱 설정에 따라 다를 수 있어서, 위에서부터 차례로
#    시도하고 **먼저 되는 것을 쓴다.** 하나 막혔다고 손님이 다시 나를 찾아오게 만들지 않는다.
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


def keys():
    cid = os.environ.get("YOUTUBE_CLIENT_ID", "").strip()
    sec = os.environ.get("YOUTUBE_CLIENT_SECRET", "").strip()
    if not cid or not sec:
        die("YOUTUBE_CLIENT_ID 와 YOUTUBE_CLIENT_SECRET 이 먼저 등록돼 있어야 합니다.",
            "저장소 → Settings → Secrets and variables → Actions 에 두 개를 넣고 "
            "다시 실행하십시오.")
    return cid, sec


# ── 1단계 : 코드 받기 (몇 초 만에 끝난다) ────────────────────
def request_code():
    cid, _ = keys()
    got, scope_used, last = None, "", {}
    for sc in SCOPE_TRY:
        res, _ = post(DEVICE_URL, {"client_id": cid, "scope": sc})
        if "device_code" in res:
            got, scope_used = res, sc
            break
        last = res
        if res.get("error") == "invalid_client":
            break                      # 열쇠 자체가 틀린 것 — 권한을 바꿔도 소용없다
        print(f"  권한 조합 거절({res.get('error')}) — 다음 조합 시도", flush=True)

    if got is None:
        err = last.get("error", "")
        hint = ""
        if err == "invalid_client":
            hint = ("**열쇠 종류가 잘못됐을 가능성이 큽니다.** 구글 클라우드에서 OAuth 클라이언트를\n"
                    "만들 때 **Application type** 을 **TV and Limited Input devices** 로 "
                    "골라야 합니다.\n'Web application' 으로 만들었다면 새로 만들어 주십시오.\n")
        else:
            hint = ("시도한 권한 조합이 모두 거절됐습니다.\n\n```\n" + "\n".join(SCOPE_TRY) + "\n```\n")
        die(f"구글이 코드를 주지 않았습니다. (`{err}`) {last.get('error_description','')}", hint)

    url = got.get("verification_url") or got.get("verification_uri")
    user_code = got["user_code"]
    mins = int(got.get("expires_in", 1800)) // 60

    OUT.mkdir(exist_ok=True)
    CODE_FILE.write_text(json.dumps({
        "device_code": got["device_code"], "user_code": user_code,
        "verification_url": url, "interval": int(got.get("interval", 5)),
        "expires_in": int(got.get("expires_in", 1800)), "scope": scope_used,
    }, ensure_ascii=False), encoding="utf-8")

    msg = (f"판결극장 유튜브 연결\n\n"
           f"1) 이 주소를 여세요\n{url}\n\n"
           f"2) 이 코드를 넣으세요\n{user_code}\n\n"
           f"3) '허용(Allow)' 을 누르시면 끝납니다.\n"
           f"({mins}분 안에 해주세요)")
    print("\n" + "=" * 52 + "\n" + msg + "\n" + "=" * 52 + "\n", flush=True)
    telegram(msg)
    summary(
        "## 유튜브 연결 — 지금 폰에서 해주십시오\n\n"
        f"### 1. 이 주소를 누르십시오\n\n# [{url}]({url})\n\n"
        f"### 2. 이 코드를 넣으십시오\n\n# `{user_code}`\n\n"
        "### 3. 계정을 고르고 **Allow(허용)** 를 누르십시오\n\n"
        f"- **{mins}분 안에** 하셔야 합니다.\n"
        "- 채널이 여러 개면 **판결극장** 채널을 고르십시오.\n"
        "- **\"Google hasn't verified this app\"** 경고가 뜨면 "
        "**Advanced** → **Go to … (unsafe)** 를 누르십시오. (본인이 만든 앱이라 그렇습니다)\n\n"
        "누르고 나면 아래 단계가 저절로 끝나고 토큰이 나옵니다.\n\n---\n")
    print("코드 발급 완료. 다음 단계가 허용을 기다립니다.")


# ── 2단계 : 허용될 때까지 기다렸다 토큰 받기 ──────────────────
def poll():
    cid, sec = keys()
    if not CODE_FILE.exists():
        die("코드 파일이 없습니다. 앞 단계가 실패했습니다.")
    d = json.loads(CODE_FILE.read_text(encoding="utf-8"))
    interval = max(5, int(d.get("interval", 5)))
    deadline = time.time() + int(d.get("expires_in", 1800))

    waited = 0
    res = {}
    while time.time() < deadline:
        time.sleep(interval)
        waited += interval
        res, _ = post(TOKEN_URL, {
            "client_id": cid, "client_secret": sec,
            "device_code": d["device_code"], "grant_type": GRANT,
        })
        err = res.get("error")
        if not err:
            break
        if err == "authorization_pending":
            if waited % 30 == 0:
                print(f"  허용을 기다리는 중… {waited}초", flush=True)
            continue
        if err == "slow_down":
            interval += 5
            continue
        if err == "access_denied":
            die("허용이 거부됐습니다. 다시 실행해 '허용' 을 눌러 주십시오.")
        if err == "expired_token":
            die("시간이 지나 코드가 만료됐습니다. 다시 실행해 주십시오.")
        die(f"구글이 거절했습니다. (`{err}`) {res.get('error_description','')}")
    else:
        die("시간 안에 허용되지 않았습니다. 다시 실행해 주십시오.")

    refresh = res.get("refresh_token", "")
    if not refresh:
        die("갱신 토큰이 오지 않았습니다.",
            "이미 연결한 적이 있는 계정이면 구글이 토큰을 다시 주지 않습니다.\n"
            "[이 주소](https://myaccount.google.com/connections) 에서 "
            "**Third-party apps with account access** 목록의 이 앱 연결을 지우고 "
            "다시 실행해 주십시오.\n")

    # 받은 토큰이 진짜 되는지 그 자리에서 확인한다
    who, _ = post(TOKEN_URL, {"client_id": cid, "client_secret": sec,
                              "refresh_token": refresh, "grant_type": "refresh_token"})
    ok = "access_token" in who

    OUT.mkdir(exist_ok=True)
    TOKEN_FILE.write_text(refresh, encoding="utf-8")
    print("::add-mask::" + refresh)          # 로그에는 남기지 않는다
    summary(
        "## 연결됐습니다\n\n"
        + ("받은 토큰으로 접속까지 확인했습니다.\n\n" if ok
           else "⚠️ 토큰은 받았지만 접속 확인에 실패했습니다. 그래도 아래 값을 넣어 보십시오.\n\n")
        + "### 마지막 한 단계\n\n"
        "아래 값을 복사해 **Settings → Secrets and variables → Actions** 에서\n"
        "`YOUTUBE_REFRESH_TOKEN` 이라는 이름으로 새 시크릿을 만들어 넣으십시오.\n\n"
        f"```\n{refresh}\n```\n\n"
        "> ⚠️ 넣으신 뒤 이 실행 기록을 지워 주십시오 — `...` → **Delete workflow run**\n")
    telegram("판결극장 유튜브 연결이 끝났습니다.\n"
             "GitHub 요약 화면의 토큰을 시크릿에 넣어 주세요.")
    print("연결 완료.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--request", action="store_true", help="코드 받기")
    ap.add_argument("--poll", action="store_true", help="허용 기다렸다 토큰 받기")
    a = ap.parse_args()
    if a.request:
        request_code()
    elif a.poll:
        poll()
    else:
        ap.error("--request 또는 --poll 중 하나를 주십시오")


if __name__ == "__main__":
    main()
