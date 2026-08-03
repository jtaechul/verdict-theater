#!/usr/bin/env python3
"""유튜브 업로드 · 자막 · 고지문 · 챕터 · 재생목록 · 공개 전환.

    python3 src/upload.py private EP001 --video build/longform.mp4
    python3 src/upload.py shorts  EP001 --dir build
    python3 src/upload.py publish EP001            비공개 → 공개
    python3 src/upload.py publish EP001 --shorts 1  쇼츠 1번만 공개

검수 흐름 (지침서 10번)

    Actions 렌더링 → 유튜브 **비공개** 업로드 → stage: uploaded_private
        ↓
    운영자가 아이폰 유튜브 앱에서 확인 (비공개 영상은 본인만 보임)
        ↓
    승인 → `publish` 실행 → stage: published

구글 라이브러리를 쓰지 않는 이유
    google-api-python-client 는 의존성이 무겁고 러너 설치가 느리다.
    필요한 것은 토큰 갱신과 업로드 두 가지뿐이라 표준 라이브러리로 충분하다.
"""

import argparse
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render import cut_durations  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "data" / "scripts"
EPISODES = ROOT / "state" / "episodes.json"
CAL = ROOT / "state" / "calendar.json"

TOKEN_URL = "https://oauth2.googleapis.com/token"
API = "https://www.googleapis.com/youtube/v3"
UPLOAD = "https://www.googleapis.com/upload/youtube/v3"

# ⚠️ 이 고지문은 모델이 쓰지 않는다. 시스템이 붙인다.
#    법적 방어선이라 회차마다 문구가 흔들리면 안 된다.
NOTICE = """
※ 이 영상은 실제 법원 판결을 바탕으로 재구성한 드라마입니다.
   등장인물의 이름, 지역, 직업, 금액, 시기는 모두 각색되었으며
   실제 사건 당사자와 무관합니다.

※ 이 채널은 법률 상담을 제공하지 않습니다.
   개별 사안은 반드시 변호사와 상담하십시오.

※ 이 영상은 AI 기술을 활용해 제작되었습니다.
""".strip()

PINNED_SUFFIX = "\n\n※ 이 채널은 법률 상담을 제공하지 않습니다. 개별 사안은 변호사와 상담하십시오."


# ── 인증 ────────────────────────────────────────────────
def access_token():
    cid = os.environ.get("YOUTUBE_CLIENT_ID", "").strip()
    sec = os.environ.get("YOUTUBE_CLIENT_SECRET", "").strip()
    ref = os.environ.get("YOUTUBE_REFRESH_TOKEN", "").strip()
    missing = [n for n, v in (("YOUTUBE_CLIENT_ID", cid), ("YOUTUBE_CLIENT_SECRET", sec),
                              ("YOUTUBE_REFRESH_TOKEN", ref)) if not v]
    if missing:
        raise RuntimeError(
            "유튜브 열쇠가 없다: " + ", ".join(missing) + "\n"
            "  Actions 탭 → '유튜브 연결하기 (최초 1회)' 를 실행하면 버튼만으로 받을 수 있다.\n"
            "  절차는 STARTGUIDE.md 3-2 에 있다."
        )
    data = urllib.parse.urlencode({
        "client_id": cid, "client_secret": sec,
        "refresh_token": ref, "grant_type": "refresh_token",
    }).encode()
    req = urllib.request.Request(TOKEN_URL, data=data,
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())["access_token"]


def api(method, path, token, body=None, params=None, base=API):
    url = f"{base}/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"유튜브 API {method} {path} 실패 "
                           f"(HTTP {e.code})\n{e.read().decode('utf-8', 'replace')[:600]}")


# ── 설명란 · 자막 ────────────────────────────────────────
def mmss(sec):
    return f"{int(sec) // 60}:{int(sec) % 60:02d}"


def build_description(doc, durs):
    """설명란. 줄거리(모델) + 챕터 + 관련 법령 + 고지문(시스템 고정)."""
    y = doc.get("youtube", {})
    out = [y.get("description_body", "").strip(), ""]

    # 챕터 — 어르신은 다시 찾아보기를 쓴다. 첫 항목은 반드시 0:00
    out.append("── 목차 ──")
    t = 0.0
    i = 0
    for act in doc.get("acts", []):
        out.append(f"{mmss(t)} {act.get('title', act['id'])}")
        n = len(act.get("cuts", []))
        t += sum(durs[i:i + n])
        i += n
    out.append("")

    laws = doc.get("law", {}).get("refs_from_case", [])
    if laws:
        out.append("── 관련 법령 ──")
        out += [f"· {x}" for x in laws]
        out.append("")

    out.append(NOTICE)
    tags = y.get("tags", [])
    if tags:
        out.append("")
        out.append(" ".join(f"#{t}" for t in tags[:5]))
    return "\n".join(out).strip()


def build_srt(doc, durs, path):
    """자막 파일. 자동 생성보다 정확하고 검색 색인에도 유리하다."""
    def ts(sec):
        h, rem = divmod(sec, 3600)
        m, s = divmod(rem, 60)
        return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int((s % 1) * 1000):03d}"

    lines, t, n = [], 0.0, 0
    for cut, d in zip((c for a in doc["acts"] for c in a["cuts"]), durs):
        text = (cut.get("text") or "").strip()
        if text:
            n += 1
            lines += [str(n), f"{ts(t)} --> {ts(t + d - 0.1)}", text, ""]
        t += d
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# ── 업로드 ──────────────────────────────────────────────
def upload_video(token, path, title, description, tags, vertical=False):
    """재개 가능 업로드. 큰 파일이라 한 번에 밀어 넣지 않는다."""
    meta = {
        "snippet": {
            "title": title[:100],
            "description": description[:4900],
            "tags": (tags or [])[:15],
            "categoryId": "24",                 # 엔터테인먼트
            "defaultLanguage": "ko",
        },
        "status": {
            "privacyStatus": "private",         # 반드시 비공개로 올린다. 검수 후 공개
            "selfDeclaredMadeForKids": False,
            "license": "youtube",
            "embeddable": True,
        },
    }
    size = path.stat().st_size
    req = urllib.request.Request(
        f"{UPLOAD}/videos?" + urllib.parse.urlencode(
            {"part": "snippet,status", "uploadType": "resumable"}),
        data=json.dumps(meta).encode(), method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-Upload-Content-Length": str(size),
            "X-Upload-Content-Type": mimetypes.guess_type(str(path))[0] or "video/mp4",
        })
    with urllib.request.urlopen(req, timeout=120) as r:
        session = r.headers["Location"]

    body = path.read_bytes()
    put = urllib.request.Request(session, data=body, method="PUT", headers={
        "Authorization": f"Bearer {token}",
        "Content-Length": str(size),
        "Content-Type": "video/mp4",
    })
    with urllib.request.urlopen(put, timeout=1800) as r:
        return json.loads(r.read())["id"]


def upload_caption(token, video_id, srt_path):
    meta = {"snippet": {"videoId": video_id, "language": "ko",
                        "name": "한국어", "isDraft": False}}
    boundary = "----vt-boundary"
    parts = [
        f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n"
        f"{json.dumps(meta)}\r\n".encode(),
        f"--{boundary}\r\nContent-Type: application/octet-stream\r\n\r\n".encode(),
        srt_path.read_bytes(),
        f"\r\n--{boundary}--\r\n".encode(),
    ]
    data = b"".join(parts)
    req = urllib.request.Request(
        f"{UPLOAD}/captions?" + urllib.parse.urlencode({"part": "snippet", "uploadType": "multipart"}),
        data=data, method="POST", headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/related; boundary={boundary}",
        })
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read()).get("id")


def post_comment(token, video_id, text):
    return api("POST", "commentThreads", token, params={"part": "snippet"}, body={
        "snippet": {"videoId": video_id,
                    "topLevelComment": {"snippet": {"textOriginal": text[:9000]}}}
    }).get("id")


def ensure_playlist(token, title):
    got = api("GET", "playlists", token, params={"part": "snippet", "mine": "true", "maxResults": 50})
    for it in got.get("items", []):
        if it["snippet"]["title"] == title:
            return it["id"]
    made = api("POST", "playlists", token, params={"part": "snippet,status"}, body={
        "snippet": {"title": title, "description": "판결극장 시리즈"},
        "status": {"privacyStatus": "public"},
    })
    return made["id"]


def add_to_playlist(token, playlist_id, video_id):
    return api("POST", "playlistItems", token, params={"part": "snippet"}, body={
        "snippet": {"playlistId": playlist_id,
                    "resourceId": {"kind": "youtube#video", "videoId": video_id}}
    }).get("id")


# ── 명령 ────────────────────────────────────────────────
def _load(p, d):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else d


def _save(p, o):
    p.write_text(json.dumps(o, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cmd_private(args):
    ep = args.episode
    doc = json.loads((SCRIPTS / f"{ep}.json").read_text(encoding="utf-8"))
    video = Path(args.video)
    if not video.exists():
        print(f"영상이 없다: {video}")
        return 2

    token = access_token()
    durs = cut_durations(doc, args.narration or None)
    desc = build_description(doc, durs)
    title = doc["meta"]["title_candidates"][0]
    tags = doc.get("youtube", {}).get("tags", [])

    print(f"{ep} 업로드 중 ({video.stat().st_size / 1e6:.0f}MB) …")
    vid = upload_video(token, video, title, desc, tags)
    print(f"  영상 ID {vid} — 비공개")

    srt = video.with_suffix(".srt")
    build_srt(doc, durs, srt)
    try:
        upload_caption(token, vid, srt)
        print("  자막(.srt) 등록")
    except Exception as e:
        print(f"  자막 등록 실패(넘어감): {e}")

    q = doc.get("youtube", {}).get("pinned_comment", "")
    if q:
        try:
            post_comment(token, vid, q + PINNED_SUFFIX)
            print("  댓글 등록")
            print("  ⚠️ 유튜브 API는 댓글 '고정'을 지원하지 않는다. 앱에서 직접 고정해야 한다.")
        except Exception as e:
            print(f"  댓글 등록 실패(넘어감): {e}")

    try:
        pl = ensure_playlist(token, "판결극장")
        add_to_playlist(token, pl, vid)
        print("  재생목록 추가")
    except Exception as e:
        print(f"  재생목록 실패(넘어감): {e}")

    eps = _load(EPISODES, {})
    eps.setdefault(ep, {})
    eps[ep].update({"longform_id": vid, "stage": "uploaded_private"})
    _save(EPISODES, eps)

    print(f"\n검수하십시오: https://youtu.be/{vid}")
    print("  비공개라 손님만 보입니다. 확인 뒤 publish 를 실행하면 공개됩니다.")
    print("\n⚠️ 유튜브 스튜디오에서 'AI 생성 콘텐츠' 표시를 켜 주십시오.")
    print("   현재 API 로는 그 항목을 설정할 수 없습니다. 설명란에는 이미 적혀 있습니다.")
    return 0


def cmd_shorts(args):
    ep = args.episode
    doc = json.loads((SCRIPTS / f"{ep}.json").read_text(encoding="utf-8"))
    shp = SCRIPTS / f"{ep}.shorts.json"
    if not shp.exists():
        print("쇼츠 대본이 없다.")
        return 2
    sh = json.loads(shp.read_text(encoding="utf-8"))
    token = access_token()
    eps = _load(EPISODES, {})
    ids = eps.get(ep, {}).get("shorts", [])

    for s in sh.get("shorts", []):
        no = s.get("no")
        v = Path(args.dir) / f"short{no}.mp4"
        if not v.exists():
            print(f"  쇼츠 {no}번 영상이 없다: {v}")
            continue
        title = (s.get("youtube", {}).get("title") or doc["meta"]["title_candidates"][0])
        title = f"{title[:80]} #Shorts"
        desc = (s.get("youtube", {}).get("description_body", "") + "\n\n" + NOTICE).strip()
        vid = upload_video(token, v, title, desc,
                           s.get("youtube", {}).get("tags", []), vertical=True)
        ids.append(vid)
        print(f"  쇼츠 {no}번 → {vid} (비공개) · 발행 예정 +{s.get('publish_offset_days')}일")

    eps.setdefault(ep, {})["shorts"] = ids
    _save(EPISODES, eps)

    # 발행 간격 분산 — 같은 날 3편 동시 업로드 절대 금지
    cal = _load(CAL, [])
    for s, vid in zip(sh.get("shorts", []), ids[-len(sh.get("shorts", [])):]):
        cal.append({"episode": ep, "video_id": vid, "kind": f"short{s.get('no')}",
                    "offset_days": s.get("publish_offset_days"), "planned": True})
    _save(CAL, cal)
    print("\n⚠️ 쇼츠는 같은 날 한꺼번에 공개하지 않는다. +1일 / +2일 / +4일 로 나눠 공개한다.")
    return 0


def cmd_publish(args):
    ep = args.episode
    eps = _load(EPISODES, {})
    row = eps.get(ep)
    if not row:
        print(f"{ep} 기록이 없다.")
        return 2
    token = access_token()

    if args.shorts:
        idx = int(args.shorts) - 1
        vids = row.get("shorts", [])
        if idx < 0 or idx >= len(vids):
            print(f"쇼츠 {args.shorts}번이 없다.")
            return 2
        targets = [vids[idx]]
    else:
        if not row.get("longform_id"):
            print("올라간 롱폼이 없다.")
            return 2
        targets = [row["longform_id"]]

    for vid in targets:
        cur = api("GET", "videos", token, params={"part": "snippet,status", "id": vid})
        items = cur.get("items", [])
        if not items:
            print(f"  {vid} 를 찾을 수 없다.")
            continue
        snip = items[0]["snippet"]
        api("PUT", "videos", token, params={"part": "status"}, body={
            "id": vid,
            "status": {"privacyStatus": "public",
                       "selfDeclaredMadeForKids": False,
                       "license": "youtube", "embeddable": True},
        })
        print(f"  공개 전환: https://youtu.be/{vid}  {snip.get('title', '')[:40]}")

    if not args.shorts:
        row["stage"] = "published"
        row["published_at"] = date.today().isoformat()
    else:
        row.setdefault("shorts_published", []).append(date.today().isoformat())
    _save(EPISODES, eps)
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("private", help="롱폼을 비공개로 올린다")
    p.add_argument("episode")
    p.add_argument("--video", default="build/longform.mp4")
    p.add_argument("--narration", default="")

    s = sub.add_parser("shorts", help="쇼츠 3편을 비공개로 올린다")
    s.add_argument("episode")
    s.add_argument("--dir", default="build")

    b = sub.add_parser("publish", help="비공개 → 공개")
    b.add_argument("episode")
    b.add_argument("--shorts", default="", help="쇼츠 번호 (1/2/3). 비우면 롱폼")

    args = ap.parse_args()
    try:
        if args.cmd == "private":
            return cmd_private(args)
        if args.cmd == "shorts":
            return cmd_shorts(args)
        return cmd_publish(args)
    except RuntimeError as e:
        print(f"❌ {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
