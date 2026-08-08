#!/usr/bin/env python3
"""작업이 끝나면 **텔레그램으로 알린다.**

    python3 src/notify.py --kind produce --ep EP001 --status ok   --run-url ...
    python3 src/notify.py --kind script  --ep EP001 --status fail --run-url ...

왜 필요한가
    영상 한 편을 만드는 데 30분 안팎이 걸린다. 그동안 GitHub 화면을 지키고 있을
    수는 없다. 끝나면 폰으로 알려주고, 링크를 눌러 바로 확인할 수 있어야 한다.

⚠️ 이 파일은 **절대 실행을 실패시키지 않는다.**
    알림은 곁다리다. 알림이 안 갔다고 다 만든 영상을 실패로 처리하면 안 된다.
    그래서 무슨 일이 있어도 종료 코드 0 으로 끝난다. 실패해도 이유만 화면에 찍는다.

필요한 시크릿 (저장소 Settings → Secrets and variables → Actions)
    TELEGRAM_BOT_TOKEN   BotFather 가 준 봇 열쇠
    TELEGRAM_CHAT_ID     받을 대화방 번호
  둘 다 없으면 조용히 넘어간다. 예전 NOTIFY_WEBHOOK 이 있으면 그쪽으로 보낸다.
"""

import argparse
import html
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "data" / "scripts"
EPISODES = ROOT / "state" / "episodes.json"
BUILD = ROOT / "build"

# 관리자 페이지. 여기서 영상을 바로 재생하고 대본을 읽는다.
ADMIN = os.environ.get(
    "ADMIN_URL", "https://verdict-theater-admin.jtaechul.workers.dev").rstrip("/")

# 제작이 어느 단계까지 갔는지는 **로그 파일이 있느냐**로 알 수 있다.
# 순서대로 만들어지므로, 마지막으로 존재하는 것이 멈춘 자리다.
STEPS = [("asset.log", "그림 준비"), ("tts.log", "나레이션"),
         ("render.log", "영상 렌더링"), ("upload.log", "유튜브 업로드"),
         ("gate.log", "소재 심사"), ("script.log", "대본 쓰기")]

TG_LIMIT = 3800          # 텔레그램 한 메시지 한도는 4096자. 여유를 둔다


def esc(s):
    return html.escape(str(s), quote=False)


def read_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default


def human_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f}{unit}" if unit != "GB" else f"{n:.1f}{unit}"
        n /= 1024.0


def human_sec(sec):
    """754.3 → '12분 34초'. 분이 0이면 '54초'."""
    sec = int(round(float(sec)))
    m, s = divmod(sec, 60)
    return f"{m}분 {s}초" if m else f"{s}초"


def probe_sec(path):
    """영상 길이(초). ffprobe 가 없거나 실패하면 None."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(path)],
            capture_output=True, text=True, timeout=60)
        return float(out.stdout.strip())
    except Exception:
        return None


def latest_ep():
    """가장 최근 회차 번호. 워크플로가 회차를 안 넘겨줄 때 쓴다.

    대본 워크플로는 '어느 회차가 만들어질지' 를 미리 알 수 없다(판례를 골라야
    번호가 정해진다). 그래서 끝난 뒤 파일을 보고 알아낸다."""
    try:
        got = sorted(p.stem for p in SCRIPTS.glob("EP*.json")
                     if "." not in p.stem)
        return got[-1] if got else ""
    except Exception:
        return ""


def title_of(ep):
    doc = read_json(SCRIPTS / f"{ep}.json", {})
    meta = doc.get("meta", {})
    cands = meta.get("title_candidates") or []
    return (doc.get("youtube", {}).get("title")
            or (cands[0] if cands else "")
            or meta.get("title", ""))


def voice_line():
    """음성이 몇 컷이고 그중 몇 컷이 무음으로 때워졌는지.

    ⚠️ 이 줄이 중요하다. 무음으로 때운 컷이 있으면 그 자리에서 소리가 끊긴다.
       영상은 '성공' 으로 나와도 사람이 알아야 하는 사실이다."""
    voice = BUILD / "voice"
    if not voice.is_dir():
        return None
    # _master_*.mp3 는 컷이 아니라 '한 통 원본' 보관본이다 — 컷 수에서 뺀다
    total = len([p for p in voice.glob("*.mp3") if not p.name.startswith("_")])
    if not total:
        return None
    quiet = len(list(voice.glob("*.silent")))
    if quiet:
        return f"음성: {total}컷 중 <b>{quiet}컷이 무음</b>(소리가 끊깁니다)"
    return f"음성: {total}컷 전부 정상"


def video_lines():
    """만들어진 mp4 들을 사람이 읽는 줄로."""
    if not BUILD.is_dir():
        return []
    lines = []
    longform = BUILD / "longform.mp4"
    if longform.exists():
        sec = probe_sec(longform)
        sz = human_size(longform.stat().st_size)
        lines.append("본편: " + (f"{human_sec(sec)} ({sz})" if sec else sz))
    shorts = sorted(p for p in BUILD.glob("*.mp4") if p.name != "longform.mp4")
    if shorts:
        durs = [probe_sec(p) for p in shorts]
        got = [human_sec(d) for d in durs if d]
        lines.append(f"쇼츠: {len(shorts)}편"
                     + (f" ({' · '.join(got)})" if got else ""))
    return lines


def youtube_link(ep):
    row = read_json(EPISODES, {}).get(ep, {})
    vid = row.get("longform_id")
    return f"https://youtu.be/{vid}" if vid else None


def failed_at():
    """어느 단계에서 멈췄는지 + 그 로그의 마지막 줄들."""
    last = None
    for name, label in STEPS:
        if (ROOT / name).exists():
            last = (ROOT / name, label)
    if not last:
        return "준비 단계", ""
    path, label = last
    try:
        tail = [ln.rstrip() for ln in
                path.read_text(encoding="utf-8", errors="replace").splitlines()
                if ln.strip()][-6:]
    except Exception:
        tail = []
    return label, "\n".join(tail)[:900]


def links(*pairs):
    """(이름, 주소) 들을 눌러서 열리는 줄로. 주소가 없는 것은 건너뛴다."""
    out = [f'<a href="{esc(u)}">{esc(n)}</a>' for n, u in pairs if u]
    return "\n".join(out)


def build_message(kind, ep, status, run_url, note):
    ttl = title_of(ep)
    head_ep = esc(ep)

    if kind == "produce" and status == "ok":
        body = [f"<b>판결극장 · {head_ep} 영상 완성</b>", ""]
        if ttl:
            body.append(f"제목: {esc(ttl)}")
        body += video_lines()
        vl = voice_line()
        if vl:
            body.append(vl)
        body += ["", links(("영상 보기 (관리자 페이지)", f"{ADMIN}/"),
                           ("유튜브 (비공개)", youtube_link(ep)),
                           ("실행 기록", run_url))]

    elif kind == "produce":
        where, tail = failed_at()
        body = [f"<b>판결극장 · {head_ep} 영상 제작 실패</b>", ""]
        if ttl:
            body.append(f"제목: {esc(ttl)}")
        body.append(f"멈춘 곳: <b>{esc(where)}</b>")
        if tail:
            body += ["", f"<pre>{esc(tail)}</pre>"]
        body += ["", links(("실행 기록 보기", run_url))]

    elif kind == "script" and status == "ok":
        row = read_json(EPISODES, {}).get(ep, {})
        doc = read_json(SCRIPTS / f"{ep}.json", {})
        cuts = sum(len(a.get("cuts") or []) for a in doc.get("acts", []))
        sh = read_json(SCRIPTS / f"{ep}.shorts.json", {})
        body = [f"<b>판결극장 · {head_ep} 대본 완성</b>", ""]
        if ttl:
            body.append(f"제목: {esc(ttl)}")
        if cuts:
            body.append(f"본편: 5단 구조 {cuts}컷")
        if sh.get("shorts"):
            body.append(f"쇼츠: {len(sh['shorts'])}편")
        if row.get("script_score"):
            body.append(f"채점: {row['script_score']}점")
        if row.get("validation_errors"):
            body.append(f"검증 경고 <b>{row['validation_errors']}건</b>")
        body += ["", "읽어보고 괜찮으면 영상 만들기를 누르십시오.", "",
                 links(("대본 읽기 (관리자 페이지)", f"{ADMIN}/"),
                       ("실행 기록", run_url))]

    else:                                   # script 실패
        where, tail = failed_at()
        body = [f"<b>판결극장 · {head_ep} 대본 만들기 실패</b>", "",
                f"멈춘 곳: <b>{esc(where)}</b>"]
        if tail:
            body += ["", f"<pre>{esc(tail)}</pre>"]
        body += ["", links(("실행 기록 보기", run_url))]

    if note:
        body += ["", esc(note)]
    return "\n".join(x for x in body if x is not None)[:TG_LIMIT]


def post(url, payload, ctype="application/json"):
    data = (json.dumps(payload).encode("utf-8")
            if ctype == "application/json" else payload)
    req = urllib.request.Request(url, data=data, headers={"Content-Type": ctype})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def send(text):
    """텔레그램으로. 없으면 예전 웹훅으로. 둘 다 없으면 조용히 넘어간다."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if token and chat:
        try:
            post(f"https://api.telegram.org/bot{token}/sendMessage", {
                "chat_id": chat,
                "text": text,
                "parse_mode": "HTML",
                # 링크 미리보기 카드가 뜨면 알림이 길어져 한눈에 안 들어온다.
                "disable_web_page_preview": True,
            })
            print("텔레그램 알림 보냄")
            return True
        except urllib.error.HTTPError as e:
            # ⚠️ 열쇠·번호를 절대 찍지 않는다. 로그는 남는다.
            detail = ""
            try:
                detail = json.loads(e.read().decode("utf-8", "replace")).get(
                    "description", "")
            except Exception:
                pass
            print(f"텔레그램 실패(HTTP {e.code}) {detail}")
            # 무엇을 고쳐야 하는지 코드별로 정확히 알려준다. 손님이 직접 볼 화면이다.
            if e.code == 401:
                print("  → TELEGRAM_BOT_TOKEN 이 틀렸습니다."
                      " BotFather 에서 봇 열쇠를 다시 확인해 등록하십시오.")
            elif "chat not found" in detail.lower():
                print("  → TELEGRAM_CHAT_ID 가 틀렸거나, 그 봇에게 아직 먼저"
                      " 말을 걸지 않았습니다. 봇은 먼저 말을 건 사람에게만 보낼 수 있습니다.")
            elif e.code == 403:
                print("  → 봇이 차단돼 있습니다. 텔레그램에서 그 봇 대화방을 열고"
                      " 차단을 푸십시오.")
        except Exception as e:
            print(f"텔레그램 실패({type(e).__name__})")
    elif token or chat:
        print("텔레그램 시크릿이 하나만 등록돼 있다 —"
              " TELEGRAM_BOT_TOKEN 과 TELEGRAM_CHAT_ID 둘 다 필요하다.")

    hook = os.environ.get("NOTIFY_WEBHOOK", "").strip()
    if hook:
        try:
            # 예전 방식(슬랙형 웹훅)과 호환. HTML 태그는 빼고 보낸다.
            import re
            post(hook, {"text": re.sub(r"<[^>]+>", "", text)})
            print("웹훅 알림 보냄")
            return True
        except Exception as e:
            print(f"웹훅 실패({type(e).__name__})")
    if not token or not chat:
        # ⚠️ 로그에만 적으면 손님은 영영 못 본다 — 로그를 열어보지 않기 때문이다.
        #    아이폰에서 바로 보이는 **요약 화면**에 설정법을 적는다. 등록하면 사라진다.
        setup_hint()
    return False


def setup_hint():
    """텔레그램 설정이 안 돼 있으면 요약 화면에 하는 법을 적는다."""
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        print("알림 설정이 없다 — 넘어간다"
              " (TELEGRAM_BOT_TOKEN · TELEGRAM_CHAT_ID 를 등록하면 폰으로 옵니다)")
        return
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write("""
## 폰으로 알림을 받으려면 (한 번만)

지금은 끝나도 알림이 가지 않습니다. 값 2개를 등록하면 이 안내는 사라집니다.

**1.** 텔레그램에서 `@BotFather` → `/mybots` → 쓰던 봇 → **API Token** 복사

**2.** 텔레그램에서 `@userinfobot` 에게 아무 말이나 보내면 **Id** 숫자를 알려줍니다

**3.** 저장소 → **Settings** → **Secrets and variables** → **Actions**
→ **New repository secret** 으로 아래 둘을 등록

| Name | Secret |
|---|---|
| `TELEGRAM_BOT_TOKEN` | 1번에서 복사한 토큰 |
| `TELEGRAM_CHAT_ID` | 2번의 Id 숫자 |

> 알림 봇은 **먼저 말을 건 사람에게만** 보낼 수 있습니다.
> 그 봇 대화방에 아무 말이나 한 번 보내 두십시오.
""")
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=["produce", "script"], required=True)
    ap.add_argument("--ep", default="")
    ap.add_argument("--status", choices=["ok", "fail"], required=True)
    ap.add_argument("--run-url", default="")
    ap.add_argument("--note", default="")
    ap.add_argument("--dry-run", action="store_true",
                    help="보내지 않고 메시지만 찍는다(시험용)")
    args = ap.parse_args()

    ep = (args.ep or "").strip() or latest_ep() or "회차"
    text = build_message(args.kind, ep, args.status, args.run_url, args.note)
    if args.dry_run:
        print(text)
        return
    send(text)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # 알림 때문에 실행이 실패하는 일은 없어야 한다.
        print(f"알림 중 오류(넘어간다): {type(e).__name__}: {e}")
    sys.exit(0)
