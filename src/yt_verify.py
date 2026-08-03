#!/usr/bin/env python3
"""유튜브 연결이 실제로 되는지 확인한다 — 아무것도 올리지 않는다.

    python3 src/yt_verify.py

왜 필요한가
    시크릿을 넣었다고 해서 되는 것이 아니다. 값을 잘못 붙여넣었거나,
    엉뚱한 채널에 붙었거나, 권한이 모자랄 수 있다.
    그걸 **12분 렌더링을 다 하고 업로드 단계에서** 알게 되면 늦다.
    여기서 30초 만에 확인한다.

    실제로 그런 일이 있었다. TV 로그인 방식으로 받은 토큰이
      · 판결극장이 아니라 다른 채널(ABYSS)에 붙어 있었고
      · 자막·고정댓글에 필요한 권한이 빠져 있었다
    둘 다 업로드를 시도해 봐야만 드러나는 문제였다.

무엇을 보나
    ① 시크릿 3개가 다 있는가
    ② 갱신 토큰으로 접속 토큰이 나오는가
    ③ 어느 채널에 붙었는가  ← 판결극장이 맞는가
    ④ 영상·자막·고정댓글·재생목록 권한이 다 있는가
"""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

TOKEN_URL = "https://oauth2.googleapis.com/token"
API = "https://www.googleapis.com/youtube/v3"

# 채널 이름에 이 말이 들어 있어야 맞게 붙은 것으로 본다.
WANT = os.environ.get("YT_EXPECT_CHANNEL", "판결극장")


def summary(text):
    p = os.environ.get("GITHUB_STEP_SUMMARY")
    if p:
        with open(p, "a", encoding="utf-8") as f:
            f.write(text + "\n")
    else:
        print(text)


def get(url, token):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read()), None
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read()), e.code
        except Exception:
            return {}, e.code


def main():
    cid = os.environ.get("YOUTUBE_CLIENT_ID", "").strip()
    sec = os.environ.get("YOUTUBE_CLIENT_SECRET", "").strip()
    ref = os.environ.get("YOUTUBE_REFRESH_TOKEN", "").strip()

    lines, bad = [], []

    # ① 시크릿이 다 있는가
    for name, v in (("YOUTUBE_CLIENT_ID", cid), ("YOUTUBE_CLIENT_SECRET", sec),
                    ("YOUTUBE_REFRESH_TOKEN", ref)):
        if v:
            lines.append(f"| {name} | 있음 (…{v[-6:]}) |")
        else:
            lines.append(f"| {name} | **없음** |")
            bad.append(f"{name} 가 등록돼 있지 않습니다")

    if bad:
        summary("## 유튜브 연결 확인 — 실패\n\n| 항목 | 상태 |\n|---|---|\n"
                + "\n".join(lines) + "\n\n" + "\n".join(f"- {b}" for b in bad))
        print("::error::시크릿이 모자랍니다")
        sys.exit(1)

    # ② 갱신 토큰이 도는가
    data = urllib.parse.urlencode({
        "client_id": cid, "client_secret": sec,
        "refresh_token": ref, "grant_type": "refresh_token"}).encode()
    req = urllib.request.Request(
        TOKEN_URL, data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            tok = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")[:300]
        summary("## 유튜브 연결 확인 — 실패\n\n| 항목 | 상태 |\n|---|---|\n"
                + "\n".join(lines)
                + f"\n\n갱신 토큰이 거절됐습니다.\n\n```\n{raw}\n```\n\n"
                "세 값이 **같은 세트**인지 확인하십시오. "
                "Client ID/Secret 을 새로 만들었다면 토큰도 그것으로 다시 받아야 합니다.")
        print("::error::갱신 토큰이 거절됐습니다")
        sys.exit(1)

    at = tok["access_token"]
    lines.append("| 갱신 토큰 → 접속 토큰 | 정상 |")

    # ③ 어느 채널인가
    d, _ = get(f"{API}/channels?part=snippet&mine=true", at)
    items = d.get("items", [])
    if not items:
        lines.append("| 연결된 채널 | **조회 실패** |")
        bad.append("채널을 조회하지 못했습니다")
        title = ""
    else:
        s = items[0]["snippet"]
        title, handle = s.get("title", ""), s.get("customUrl", "")
        ok = WANT in title
        lines.append(f"| 연결된 채널 | {'' if ok else '**'}{title} ({handle})"
                     f"{'' if ok else '**'} |")
        if not ok:
            bad.append(f"'{WANT}' 채널이 아니라 '{title}' 에 연결돼 있습니다")

    # ④ 권한 — 실제로 API 를 때려서 본다
    checks = [
        ("자막 넣기", f"{API}/captions?part=snippet&videoId=dQw4w9WgXcQ"),
        ("재생목록", f"{API}/playlists?part=snippet&mine=true&maxResults=1"),
    ]
    for name, url in checks:
        r, code = get(url, at)
        e = r.get("error", {})
        reason = (e.get("errors") or [{}])[0].get("reason", "") if e else ""
        if reason == "insufficientPermissions":
            lines.append(f"| {name} 권한 | **없음** |")
            bad.append(f"{name} 권한이 없습니다 (force-ssl 이 빠졌습니다)")
        else:
            lines.append(f"| {name} 권한 | 있음 |")

    scope = tok.get("scope", "")
    lines.append(f"| 받은 권한 | `{scope}` |")
    if "force-ssl" not in scope:
        bad.append("force-ssl 권한이 없어 자막·고정댓글이 안 됩니다")

    head = "## 유튜브 연결 확인 — " + ("실패" if bad else "정상")
    body = head + "\n\n| 항목 | 상태 |\n|---|---|\n" + "\n".join(lines)
    if bad:
        body += "\n\n### 고쳐야 할 것\n\n" + "\n".join(f"- {b}" for b in bad)
    else:
        body += ("\n\n**모두 정상입니다.** 이제 '3. 영상 만들기' 에서 "
                 "유튜브 업로드를 켜고 실행하시면 됩니다.")
    summary(body)
    print(body)
    if bad:
        print("::error::유튜브 연결에 문제가 있습니다. 요약 화면을 보십시오.")
        sys.exit(1)


if __name__ == "__main__":
    main()
