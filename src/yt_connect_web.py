#!/usr/bin/env python3
"""유튜브 계정을 연결한다 — 웹 방식(Web application).

    python3 src/yt_connect_web.py --url            로그인 주소를 만든다
    python3 src/yt_connect_web.py --code "붙여넣은코드"   코드를 토큰으로 바꾼다

⭐ 왜 TV 방식을 버리고 이걸 만들었나 (실측으로 확인한 것)

    처음에는 TV 로그인 방식(Device Flow)을 썼다. PC 없이 폰만으로 된다는 장점이
    있었지만 **두 가지를 못 한다는 것이 실제로 확인됐다.**

    ① force-ssl 권한을 아예 안 준다
       구글 device 엔드포인트에 네 조합을 직접 던져 본 결과:
         youtube.upload + force-ssl  → 거절 "Invalid device flow scope"
         force-ssl 단독              → 거절 "Invalid device flow scope"
         youtube 단독                → 통과
         youtube.upload 단독         → 통과
       실제 API 호출로도 확인했다 — captions 요청이 403 insufficientPermissions.
       upload.py 는 **자막 넣기**와 **고정 댓글 달기**에 force-ssl 이 필요하다.
       고정 댓글은 변호사법 방어 고지문이 들어가는 자리라 뺄 수 없다.

    ② 채널을 고를 수 없다
       계정 하나에 채널이 여러 개면 TV 방식은 **기본 채널로 그냥 붙어 버린다.**
       실제로 판결극장이 아니라 다른 채널(ABYSS)로 연결됐다.
       웹 방식은 로그인 도중 **채널 선택 화면**이 떠서 고를 수 있다.

    그래서 웹 방식으로 바꾼다. 리다이렉트 주소를 구글이 주는 확인용 페이지
    (urn:ietf:wg:oauth:2.0:oob 는 폐지됨)가 아니라, **localhost 로 두고
    주소창에 찍히는 code 를 손님이 복사해 오는 방식**을 쓴다.
    폰에서도 된다 — 로그인 뒤 '연결할 수 없음' 페이지가 떠도, 주소창의
    code= 뒤 글자만 복사하면 그게 열쇠다.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"

# 웹 방식에서 쓸 리다이렉트 주소. 구글 클라우드의 OAuth 클라이언트에
# **똑같이** 등록돼 있어야 한다.
REDIRECT = "http://localhost:8080/"

# upload.py 가 실제로 하는 일에 맞춘 권한. 웹 방식은 force-ssl 을 준다.
#   youtube.upload    영상 올리기
#   youtube.force-ssl 자막 · 고정댓글 · 재생목록
SCOPE = ("https://www.googleapis.com/auth/youtube.upload "
         "https://www.googleapis.com/auth/youtube.force-ssl")

OUT = Path("connect_out")
TOKEN_FILE = OUT / "token.txt"


def post(url, data):
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return json.loads(raw)
        except Exception:
            return {"error": "http_error", "error_description": raw[:300]}


def summary(text):
    p = os.environ.get("GITHUB_STEP_SUMMARY")
    if p:
        with open(p, "a", encoding="utf-8") as f:
            f.write(text + "\n")
    else:
        print(text)


def telegram(text):
    tok = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not (tok and chat):
        return
    try:
        post(f"https://api.telegram.org/bot{tok}/sendMessage",
             {"chat_id": chat, "text": text, "disable_web_page_preview": "true"})
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
        die("YOUTUBE_CLIENT_ID 와 YOUTUBE_CLIENT_SECRET 이 먼저 등록돼 있어야 합니다.")
    return cid, sec


def make_url():
    """로그인 주소를 만들어 요약 화면·텔레그램에 띄운다."""
    cid, _ = keys()
    q = urllib.parse.urlencode({
        "client_id": cid,
        "redirect_uri": REDIRECT,
        "response_type": "code",
        "scope": SCOPE,
        # ⭐ 이 둘이 있어야 **갱신 토큰**이 나온다.
        #    prompt=consent 를 빼면 두 번째부터는 refresh_token 이 안 온다.
        "access_type": "offline",
        "prompt": "consent select_account",
    })
    url = f"{AUTH_URL}?{q}"

    msg = ("판결극장 유튜브 연결 (웹 방식)\n\n"
           "1) 아래 주소를 여세요\n" + url + "\n\n"
           "2) 계정과 **판결극장 채널**을 고르고 허용하세요\n"
           "3) '연결할 수 없음' 페이지가 뜨면 정상입니다.\n"
           "   주소창의 code= 뒤 글자를 복사해서 클로드에게 주세요.")
    print("\n" + "=" * 60 + "\n" + msg + "\n" + "=" * 60 + "\n", flush=True)
    telegram(msg)
    summary(
        "## 유튜브 연결 (웹 방식)\n\n"
        f"### 1. 이 주소를 누르십시오\n\n[{url}]({url})\n\n"
        "### 2. 계정을 고르고, **판결극장 채널**을 고르십시오\n\n"
        "- 채널 선택 화면이 뜹니다. **반드시 판결극장을 고르십시오.**\n"
        "- \"Google hasn't verified this app\" 이 뜨면 "
        "**Advanced** → **Go to … (unsafe)**\n\n"
        "### 3. 마지막에 흰 화면(\"연결할 수 없음\")이 뜹니다 — 정상입니다\n\n"
        "주소창을 보면 이렇게 되어 있습니다.\n\n"
        "```\nhttp://localhost:8080/?code=4/0AX4...&scope=...\n```\n\n"
        "**`code=` 와 `&scope` 사이의 글자**를 복사해서 클로드에게 주십시오.\n")
    OUT.mkdir(exist_ok=True)
    (OUT / "auth_url.txt").write_text(url, encoding="utf-8")


def exchange(code):
    """손님이 복사해 온 코드를 갱신 토큰으로 바꾼다."""
    cid, sec = keys()
    code = urllib.parse.unquote(code.strip())
    res = post(TOKEN_URL, {
        "client_id": cid, "client_secret": sec, "code": code,
        "grant_type": "authorization_code", "redirect_uri": REDIRECT,
    })
    if "refresh_token" not in res:
        err = res.get("error", "")
        hint = ""
        if err == "invalid_grant":
            hint = ("코드는 **한 번만** 쓸 수 있고 몇 분 안에 만료됩니다.\n"
                    "이미 썼거나 시간이 지난 코드입니다. 주소를 다시 열어 새 코드를 받아 주십시오.\n")
        elif err == "redirect_uri_mismatch":
            hint = (f"구글 클라우드의 OAuth 클라이언트에 리다이렉트 주소\n`{REDIRECT}`\n"
                    "가 등록돼 있어야 합니다. **Authorized redirect URIs** 에 넣어 주십시오.\n")
        elif "refresh" in str(res):
            hint = ("갱신 토큰이 오지 않았습니다. 이미 연결한 적이 있는 계정이면 "
                    "[여기](https://myaccount.google.com/connections) 에서 연결을 지우고 "
                    "다시 해주십시오.\n")
        die(f"토큰을 받지 못했습니다. (`{err}`) {res.get('error_description','')}", hint)

    refresh = res["refresh_token"]
    # 받은 토큰이 진짜 되는지, 어느 채널인지 그 자리에서 확인한다
    chk = post(TOKEN_URL, {"client_id": cid, "client_secret": sec,
                           "refresh_token": refresh, "grant_type": "refresh_token"})
    at = chk.get("access_token", "")
    who = "(확인 실패)"
    if at:
        try:
            req = urllib.request.Request(
                "https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true",
                headers={"Authorization": f"Bearer {at}"})
            with urllib.request.urlopen(req, timeout=30) as r:
                items = json.loads(r.read()).get("items", [])
            if items:
                s = items[0]["snippet"]
                who = f"{s.get('title')} ({s.get('customUrl','')})"
        except Exception as e:
            who = f"(확인 실패: {e})"

    OUT.mkdir(exist_ok=True)
    TOKEN_FILE.write_text(refresh, encoding="utf-8")
    print("::add-mask::" + refresh)
    summary(
        "## 연결됐습니다\n\n"
        f"**연결된 채널: {who}**\n\n"
        f"권한: `{res.get('scope','')}`\n\n"
        "### 마지막 한 단계\n\n"
        "아래 값을 `YOUTUBE_REFRESH_TOKEN` 시크릿에 넣으십시오.\n\n"
        f"```\n{refresh}\n```\n\n"
        "> 넣으신 뒤 이 실행 기록을 지워 주십시오 — `...` → **Delete workflow run**\n")
    telegram(f"판결극장 유튜브 연결 완료\n연결된 채널: {who}")
    print(f"연결 완료. 채널: {who}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", action="store_true", help="로그인 주소 만들기")
    ap.add_argument("--code", help="복사해 온 코드를 토큰으로 바꾸기")
    a = ap.parse_args()
    if a.url:
        make_url()
    elif a.code:
        exchange(a.code)
    else:
        ap.error("--url 또는 --code 중 하나를 주십시오")


if __name__ == "__main__":
    main()
