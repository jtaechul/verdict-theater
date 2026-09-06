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
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parent.parent


def cut_durations(*a, **kw):
    """컷마다 몇 초인지 — 목차 시각을 매길 때만 쓴다.

    ⚠️ **여기서 늦게 불러온다(lazy import).** 예전에는 파일 맨 위에서
       `from render import cut_durations` 를 했는데, render.py 는 그림을 그리는
       파일이라 맨 윗줄에서 Pillow(PIL, 그림 라이브러리)를 부른다.
       그래서 **그림과 아무 상관없는 올리기 작업까지** Pillow 가 있어야 돌았다.

       실제로 2026-08-09 13:11, 손님이 [유튜브에 올리기 · 즉시 공개] 를 누르자
       18초 만에 `ModuleNotFoundError: No module named 'PIL'` 로 죽었다
       (그 워크플로에는 Pillow 를 깔지 않는다). 버튼이 작동하지 않은 원인이 이것이다.

       보관해 둔 meta.json 이 있으면 이 함수는 아예 불리지 않으므로,
       늦게 불러오면 Pillow 없이도 올리기가 끝까지 간다."""
    from render import cut_durations as _f
    return _f(*a, **kw)


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


# ── 검색 해시태그 ────────────────────────────────────────
#
# 유튜브 규칙 두 가지를 알고 정한다.
#   ① 설명란 해시태그는 **앞 3개만** 제목 위에 뜬다.
#      그리고 **15개를 넘으면 유튜브가 전부 무시한다.** 많이 쓰면 손해다.
#   ② 태그 필드(안 보이는 것)는 500자까지 들어간다. 검색 순위 영향은 작지만
#      오타·유사어를 잡아 준다. 여기는 넉넉히 채우는 것이 이득이다.
# → 보이는 것은 3개, 안 보이는 것은 많이. 지금까지는 반대로 하고 있었다.
#
# 태그는 세 층으로 만든다.
#   1층 고정   채널 정체성. **AI 에 맡기지 않는다** — 매회 흔들리면 채널이 안 쌓인다.
#   2층 법률   그 사건의 법률 용어. 대본이 뽑는다.
#   3층 일상어 사람들이 **실제로 검색창에 치는 말**. 대본이 뽑는다.
#              50~60대는 '특별수익' 이라고 안 친다. '형제 재산 싸움' 이라고 친다.
FIXED_TAGS = ["판결극장", "사연극장", "실화사건", "실화사연",
               "법률상식", "판례", "가족이야기"]
SHOWN_TAGS = 3          # 설명란에 글자로 보일 개수 (제목 위에 뜨는 것도 3개다)


def all_tags(doc):
    """1층(고정) + 대본이 뽑은 것. 순서를 지키고 중복만 없앤다.

    ⚠️ 고정층을 **뒤에** 붙인다. 앞 3개가 화면에 보이는 자리라,
       그 자리는 그 사건을 가리키는 말이어야 한다('상속' 이 '실화사연' 보다 낫다).
       다만 채널 이름은 맨 앞에 한 번 둔다 — 채널을 각인시키는 자리다."""
    got = [t.strip().lstrip("#") for t in (doc.get("youtube", {}).get("tags") or [])]
    out, seen = [], set()
    for t in ["판결극장"] + got + FIXED_TAGS:
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out[:15]                    # 유튜브가 무시하기 시작하는 선 아래로 묶는다


def build_description(doc, durs):
    """설명란. 줄거리(모델) + 챕터 + 관련 법령 + 고지문(시스템 고정)."""
    y = doc.get("youtube", {})
    out = [y.get("description_body", "").strip(), ""]

    # 챕터 — 어르신은 다시 찾아보기를 쓴다. 첫 항목은 반드시 0:00
    #
    # ⭐ 제목은 **대본이 쓴 것**을 쓴다(손님 선택 2026-08-07).
    #    막 이름('1막','2막')은 정확하지만 아무도 안 누른다.
    #    대본이 지어 준 제목은 '덫에 걸린 사냥꾼' 처럼 궁금하게 만든다 — 그게 목차의 일이다.
    # ⚠️ **시각은 대본에 적힌 값을 쓰지 않는다.** 실제 컷 길이를 더해서 낸다.
    #    대본의 sec 은 예상치이고, 실제 영상은 음성 길이에 맞춰 늘었다 줄었다 한다.
    #    어긋나면 목차를 눌렀을 때 엉뚱한 데로 간다.
    labels = [c.get("label") for c in y.get("chapters", []) if c.get("label")]
    out.append("── 목차 ──")
    t = 0.0
    i = 0
    for k, act in enumerate(doc.get("acts", [])):
        name = labels[k] if k < len(labels) else act.get("title", act["id"])
        out.append(f"{mmss(t)} {name}")
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
    tags = all_tags(doc)
    if tags:
        out.append("")
        out.append(" ".join(f"#{t}" for t in tags[:SHOWN_TAGS]))
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
def upload_video(token, path, title, description, tags, vertical=False,
                 privacy="private", publish_at=None):
    """재개 가능 업로드. 큰 파일이라 한 번에 밀어 넣지 않는다.

    publish_at — **예약 공개** 시각 (2026-09-01T10:00:00Z 꼴). 주면 그때 저절로
      공개된다. 한 사건을 세 편으로 나눠 올릴 때, 손님이 사흘 동안 다시
      들어오지 않아도 하루 간격으로 공개되게 하려고 쓴다.

      ⚠️ 유튜브 규칙 — 예약을 걸려면 **지금은 비공개(private)** 여야 한다.
         공개로 두고 예약을 걸면 유튜브가 통째로 거절한다. 그래서 여기서
         강제로 private 으로 바꾼다. 부르는 쪽이 실수해도 안 죽게.
    """
    if publish_at:
        privacy = "private"
    meta = {
        "snippet": {
            "title": title[:100],
            "description": description[:4900],
            "tags": (tags or [])[:15],
            "categoryId": "24",                 # 엔터테인먼트
            "defaultLanguage": "ko",
        },
        "status": {
            # ⭐ 2026-08-07 부터 관리자 페이지에서 **바로 공개**로도 올린다.
            #    영상을 눈으로 보고 누르는 버튼이라 따로 검수 단계가 필요 없다.
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
            "license": "youtube",
            "embeddable": True,
        },
    }
    if publish_at:
        meta["status"]["publishAt"] = publish_at
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


def set_thumbnail(token, video_id, path):
    """썸네일을 올린다. **1280×720 JPEG · 2MB 이하** (유튜브 상한).

    ⚠️ `youtube.force-ssl` 권한이 있어야 한다. 자막·고정댓글과 같은 권한이라
       이미 받아 두었다(yt_verify.py 가 매번 확인한다).
    유튜브가 기본으로 뽑는 자동 썸네일은 영상 한 프레임이라 글자가 없다.
    이 채널은 **금액을 큰 글씨로 내건 썸네일**이 곧 조회수라 반드시 갈아 끼운다."""
    req = urllib.request.Request(
        f"{UPLOAD}/thumbnails/set?" + urllib.parse.urlencode(
            {"videoId": video_id, "uploadType": "media"}),
        data=path.read_bytes(), method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "image/jpeg"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())


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

    # ⭐ 썸네일을 갈아 끼운다. 유튜브 기본값은 영상 한 프레임이라 글자가 없다.
    #    없으면 조용히 넘어간다 — 썸네일 때문에 업로드가 실패하면 안 된다.
    thumb = Path(args.thumb) if getattr(args, "thumb", "") else video.parent / "thumb.jpg"
    if thumb.exists():
        try:
            set_thumbnail(token, vid, thumb)
            print(f"  썸네일 등록 ({thumb.stat().st_size / 1024:.0f}KB)")
        except Exception as e:
            print(f"  썸네일 등록 실패(넘어감): {e}")
    else:
        print(f"  썸네일 없음 — 유튜브 자동 썸네일이 쓰인다 ({thumb})")

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


def cmd_thumb(args):
    """이미 올라간 영상의 썸네일만 갈아 끼운다.

    관리자 페이지의 **'다시 만들기'** 버튼이 쓰는 길이다. 영상을 다시 만들지 않고
    그림 한 장만 바꾼다 — 값이 0원이고 몇 초면 끝난다.
    아직 유튜브에 올린 적이 없으면 조용히 넘어간다(그림은 이미 만들어졌으므로 실패가 아니다)."""
    ep = args.episode
    thumb = Path(args.thumb)
    if not thumb.exists():
        print(f"썸네일 파일이 없다: {thumb}")
        return 2
    row = _load(EPISODES, {}).get(ep) or {}
    vid = row.get("longform_id")
    if not vid:
        print(f"{ep} 는 아직 유튜브에 올라가지 않았다 — 유튜브 썸네일은 건드리지 않는다.")
        return 0
    set_thumbnail(access_token(), vid, thumb)
    print(f"유튜브 썸네일 교체: https://youtu.be/{vid}  ({thumb.stat().st_size / 1024:.0f}KB)")
    return 0



def meta_for(doc, sh, durs, what):
    """유튜브에 올라갈 **제목·설명·해시태그**를 만든다. 화면 미리보기와 실제 업로드가
    반드시 **같은 함수**를 써야 한다 — 따로 만들면 보여준 것과 올라간 것이 달라진다."""
    if what == "longform":
        return {
            "title": doc["meta"]["title_candidates"][0],
            "description": build_description(doc, durs),
            "tags": all_tags(doc),          # 안 보이는 검색용 — 넉넉히
            "pinned": doc.get("youtube", {}).get("pinned_comment", ""),
        }
    no = what.replace("short", "")
    for x in (sh or {}).get("shorts", []):
        if str(x.get("no")) == no:
            y = x.get("youtube", {}) or {}
            t = (y.get("title") or doc["meta"]["title_candidates"][0])[:80]
            return {
                "title": f"{t} #Shorts",
                "description": (y.get("description_body", "") + "\n\n" + NOTICE).strip(),
                "tags": y.get("tags", [])[:15],
                "pinned": "",
            }
    return None


WHATS = ("longform", "short1", "short2", "short3")


def cmd_meta(args):
    """올라갈 내용을 meta.json 으로 뽑는다. **영상과 같이 보관**해 두고, 나중에
    올릴 때 그대로 쓴다 — 그래야 화면에 보여드린 목차 시각과 실제 영상이 안 어긋난다."""
    ep = args.episode
    doc = json.loads((SCRIPTS / f"{ep}.json").read_text(encoding="utf-8"))
    shp = SCRIPTS / f"{ep}.shorts.json"
    sh = json.loads(shp.read_text(encoding="utf-8")) if shp.exists() else {}
    durs = cut_durations(doc, args.narration or None)
    out = {"episode": ep, "videos": {}}
    for w in WHATS:
        m = meta_for(doc, sh, durs, w)
        if m:
            out["videos"][w] = m
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2),
                              encoding="utf-8")
    print(f"올라갈 내용을 적었다: {args.out} ({len(out['videos'])}편)")
    for w, m in out["videos"].items():
        print(f"  {w:9s} {m['title'][:46]}")
    return 0


def cmd_public(args):
    """**바로 공개**로 올린다. 관리자 페이지에서 영상을 눈으로 본 뒤 누르는 버튼이다.

    meta.json 이 있으면 그것을 쓴다 — 영상과 함께 보관된 것이라 목차 시각이 정확하다.
    없으면 대본에서 그때그때 만든다(예전 영상 대비)."""
    ep, what = args.episode, args.what
    if what not in WHATS:
        print(f"무엇을 올릴지 잘못됐다: {what}")
        return 2
    video = Path(args.video)
    if not video.exists():
        print(f"영상이 없다: {video}")
        return 2

    m = None
    mp = Path(args.meta) if args.meta else video.parent / "meta.json"
    if mp.exists():
        try:
            m = json.loads(mp.read_text(encoding="utf-8")).get("videos", {}).get(what)
            print(f"보관된 내용을 쓴다: {mp}")
        except Exception:
            m = None
    if not m:
        doc = json.loads((SCRIPTS / f"{ep}.json").read_text(encoding="utf-8"))
        shp = SCRIPTS / f"{ep}.shorts.json"
        sh = json.loads(shp.read_text(encoding="utf-8")) if shp.exists() else {}
        m = meta_for(doc, sh, cut_durations(doc, args.narration or None), what)
        print("보관된 내용이 없어 대본에서 새로 만든다")
    if not m:
        print(f"{what} 의 올릴 내용을 못 만들었다")
        return 2

    # 유튜브 열쇠가 살아 있는지 여기서 판가름난다 — 안 되면 여기서 멈춘다.
    token = access_token()
    thumb = Path(args.thumb) if args.thumb else video.parent / "thumb.jpg"

    # ⭐ 연습(dry) — **올리지 않고** 여기까지가 되는지만 본다.
    #    2026-08-09 손님: "즉시공개 버튼 작동되는지 다시 한번 검증해서 정상 작동되도록 조치해."
    #    진짜로 올려서 확인하면 되돌릴 수 없다(유튜브에 공개로 올라가 버린다).
    #    그래서 **올리기 직전까지 전부 실제로 해 보고** 마지막 한 걸음만 멈춘다:
    #      영상 꺼내기 · 올릴 내용 읽기 · 유튜브 열쇠로 출입증 받기 — 여기까지 되면
    #      남은 것은 파일을 보내는 일뿐이다.
    if getattr(args, "dry", False):
        print(f"\n── 연습입니다. 올리지 않았습니다 ──")
        print(f"  영상      {video} ({video.stat().st_size / 1e6:.0f}MB)")
        print(f"  유튜브 열쇠 정상 (출입증을 받았습니다)")
        print(f"  제목      {m['title']}")
        print(f"  설명      {len(m['description'])}자")
        print(f"  해시태그   {len(m.get('tags') or [])}개 · "
              f"{' '.join('#' + t for t in (m.get('tags') or [])[:6])}")
        print(f"  썸네일     {'있음 ' + str(thumb) if thumb.exists() else '없음'}")
        print(f"  고정 댓글  {'있음' if m.get('pinned') else '없음'}")
        print(f"  공개 여부  public (바로 공개)")
        print("\n  → 여기까지 모두 정상입니다. 실제로 누르시면 그대로 올라갑니다.")
        return 0

    print(f"{ep} {what} 올리는 중 ({video.stat().st_size / 1e6:.0f}MB) — **바로 공개** …")
    vid = upload_video(token, video, m["title"], m["description"], m["tags"],
                       vertical=what != "longform", privacy="public")
    print(f"  올라갔다: https://youtu.be/{vid}  (공개)")

    if what == "longform" and thumb.exists():
        try:
            set_thumbnail(token, vid, thumb)
            print("  썸네일 등록")
        except Exception as e:
            print(f"  썸네일 등록 실패(넘어감): {e}")

    if m.get("pinned"):
        try:
            post_comment(token, vid, m["pinned"])
            print("  고정 댓글 등록")
        except Exception as e:
            print(f"  고정 댓글 실패(넘어감): {e}")

    eps = _load(EPISODES, {})
    row = eps.setdefault(ep, {})
    if what == "longform":
        row["longform_id"] = vid
    else:
        row.setdefault("shorts", []).append(vid)
    row["stage"] = "published"
    _save(EPISODES, eps)
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


def cmd_series(args):
    """⭐ 사건 하나의 **한 편**을 올린다 (2026-09-01 개편).

    옛 회차(EP001) 방식과 달리 **대본 파일에 기대지 않는다.** 올릴 글은
    관리자 페이지에서 확인·수정한 그대로 meta.json 에 담겨 온다 —
    화면에서 본 것과 실제로 올라가는 것이 반드시 같아야 하기 때문이다.

    ⭐⭐ 2026-09-01 손님: "각각 만들어서 각각 올릴 수 있어야 되는데."
       그래서 **편 번호(--part)** 를 받는다. meta.json 은 사건 전체 것이고,
       그 안에서 그 편의 글만 골라 쓴다.

    ⚠️⚠️ **같은 편을 두 번 올리지 않는다.** 지난번에 관리자 페이지의 단추가
       두 번 눌려 같은 영상이 두 번 올라갈 뻔했다. 여기서도 한 번 더 막는다 —
       화면 쪽 잠금만 믿으면 언젠가 새어 나간다.
    """
    sys.path.insert(0, str(ROOT / "src"))
    import shortstate                                        # noqa: E402

    video = Path(args.video)
    if not video.exists():
        print(f"❌ 영상이 없다: {video}")
        return 2
    raw = json.loads(Path(args.meta).read_text(encoding="utf-8"))
    sid = raw.get("sid") or args.sid

    # 편별 글에서 그 편을 고른다. 옛 모양(낱개)도 받아 준다.
    no = int(args.part or 1)
    if isinstance(raw, dict) and raw.get("parts"):
        got = [x for x in raw["parts"] if int(x.get("part", 0)) == no]
        if not got:
            have = [x.get("part") for x in raw["parts"]]
            print(f"❌ {no}편 글이 없다 (있는 편: {have})")
            return 2
        meta = got[0]
    else:
        meta = raw

    title = (meta.get("title") or "").strip()
    desc = meta.get("description") or ""
    tags = [t for t in (meta.get("tags") or []) if t]
    privacy = (args.privacy or meta.get("privacy") or "private").strip()
    if privacy not in ("private", "unlisted", "public"):
        print(f"❌ 공개 범위가 이상하다: {privacy}")
        return 2
    if not title:
        print("❌ 제목이 비었다")
        return 2

    at = (args.publish_at or "").strip() or None
    if at:
        # 유튜브는 Z 로 끝나는 UTC 만 받는다. 모양이 틀리면 한참 뒤에 죽는다.
        try:
            datetime.strptime(at, "%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            print(f"❌ 예약 시각 모양이 틀렸다: {at} "
                  f"(2026-09-02T10:00:00Z 처럼 적는다)")
            return 2

    was = shortstate.uploaded(sid, no)
    if was and not args.again:
        print(f"❌ {sid} {no}편은 이미 올렸다 — "
              f"https://youtu.be/{was.get('video_id')} ({was.get('privacy')})\n"
              f"   정말 또 올리려면 --again 을 준다.")
        return 2

    print(f"올릴 것 — {sid} {no}편 · {video.name} "
          f"({video.stat().st_size / 1048576:.1f}MB)")
    print(f"  제목: {title}")
    print(f"  해시태그: {' '.join('#' + t for t in tags)}")
    print(f"  공개 범위: {privacy}" + (f" · 예약 공개 {at}" if at else ""))
    if args.dry:
        print("\n(연습이라 실제로는 올리지 않았다)")
        return 0

    token = access_token()
    vid = upload_video(token, video, title, desc, tags,
                       vertical=True, privacy=privacy, publish_at=at)
    print(f"\n✅ 올렸다 — https://youtu.be/{vid}")
    shortstate.mark_uploaded(sid, no, vid, "private" if at else privacy, at)

    # ⚠️ 옛 화면(state/series.json)도 아직 이것을 본다 — 같이 적어 둔다.
    #    한쪽만 적으면 화면이 '안 올림' 으로 보여 두 번 올리게 된다.
    st = _load(ROOT / "state" / "series.json", {})
    row = st.setdefault(sid, {})
    row.setdefault("uploaded", {})[str(no)] = {
        "video_id": vid, "privacy": privacy, "title": title}
    (ROOT / "state" / "series.json").write_text(
        json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


def cmd_fixmeta(args):
    """⭐⭐⭐ 2026-09-06 — **이미 올린 영상의 제목·설명·해시태그만 고친다.**

    그날 있었던 일: 세 편이 **옛 제목("…낯선 여자의 신음 소리 #shorts")과 옛
    해시태그**로 올라갔다. 아직 공개 전(예약)이라 조회수 손해는 0이지만,
    그대로 두면 그 글로 공개된다. 영상은 그대로 두고 글만 바꾼다.

    값 0원 — 유튜브 videos.update 는 하루 할당량만 쓰고 돈이 안 든다.
    ⚠️ 유튜브는 제목만 보내면 나머지를 지운다. 지금 것을 먼저 읽어 와서
       바꿀 것만 갈아 끼운 **한 벌 전체**를 보낸다.
    """
    sys.path.insert(0, str(ROOT / "src"))
    import shortstate                                        # noqa: E402

    raw = json.loads(Path(args.meta).read_text(encoding="utf-8"))
    sid = raw.get("sid") or args.sid
    parts = raw.get("parts") or [raw]
    want = [int(args.part)] if args.part and args.part != "all" else None

    token = None if args.dry else access_token()
    done = bad = 0
    for meta in parts:
        no = int(meta.get("part") or 1)
        if want and no not in want:
            continue
        was = shortstate.uploaded(sid, no)
        if not was or not was.get("video_id"):
            print(f"  {no}편 — 아직 안 올렸다. 건너뛴다.")
            continue
        vid = was["video_id"]
        title = (meta.get("title") or "").strip()
        desc = meta.get("description") or ""
        tags = [t for t in (meta.get("tags") or []) if t]
        if not title:
            print(f"  ❌ {no}편 제목이 비었다")
            bad += 1
            continue
        print(f"\n{no}편 https://youtu.be/{vid}")
        print(f"  새 제목: {title}")
        print(f"  새 해시태그: {' '.join('#' + t for t in tags)}")
        if args.dry:
            print("  (연습이라 실제로는 안 고쳤다)")
            done += 1
            continue
        got = api("GET", "videos", token, params={"part": "snippet", "id": vid})
        items = got.get("items") or []
        if not items:
            print(f"  ❌ 유튜브에서 못 찾았다 ({vid})")
            bad += 1
            continue
        snip = dict(items[0]["snippet"])
        snip["title"] = title[:100]
        snip["description"] = desc[:4900]
        snip["tags"] = tags[:15]
        snip.setdefault("categoryId", "24")
        api("PUT", "videos", token, body={"id": vid, "snippet": snip},
            params={"part": "snippet"})
        print("  ✅ 고쳤다")
        done += 1
    print(f"\n■ {done}편 고쳤다" + (f" · {bad}편 실패" if bad else ""))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("private", help="롱폼을 비공개로 올린다")
    p.add_argument("episode")
    p.add_argument("--video", default="build/longform.mp4")
    p.add_argument("--narration", default="")
    p.add_argument("--thumb", default="", help="썸네일 JPEG (비우면 영상 옆 thumb.jpg)")

    s = sub.add_parser("shorts", help="쇼츠 3편을 비공개로 올린다")
    s.add_argument("episode")
    s.add_argument("--dir", default="build")

    t = sub.add_parser("thumb", help="이미 올라간 영상의 썸네일만 갈아 끼운다")
    t.add_argument("episode")
    t.add_argument("--thumb", default="build/thumb.jpg")

    b = sub.add_parser("publish", help="비공개 → 공개")
    b.add_argument("episode")
    b.add_argument("--shorts", default="", help="쇼츠 번호 (1/2/3). 비우면 롱폼")

    m = sub.add_parser("meta", help="올라갈 제목·설명·해시태그를 파일로 뽑는다")
    m.add_argument("episode")
    m.add_argument("--narration", default="")
    m.add_argument("--out", default="build/meta.json")

    u = sub.add_parser("public", help="영상 하나를 **바로 공개**로 올린다")
    u.add_argument("episode")
    u.add_argument("--what", default="longform", help="longform / short1 / short2 / short3")
    u.add_argument("--video", default="build/longform.mp4")
    u.add_argument("--meta", default="", help="meta.json (비우면 영상 옆)")
    u.add_argument("--thumb", default="")
    u.add_argument("--narration", default="")
    u.add_argument("--dry", action="store_true",
                   help="연습 — 올리기 직전까지만 해 보고 실제로는 올리지 않는다")

    r = sub.add_parser("series", help="사건 하나의 한 편을 올린다")
    r.add_argument("sid")
    r.add_argument("ep", nargs="?", default="1")     # 옛 부름 자리 (안 쓴다)
    r.add_argument("--part", default="", help="몇 편인가 (1/2/3…)")
    r.add_argument("--video", required=True)
    r.add_argument("--meta", required=True)
    r.add_argument("--privacy", default="", help="private / unlisted / public")
    r.add_argument("--publish-at", dest="publish_at", default="",
                   help="예약 공개 시각 (2026-09-02T10:00:00Z)")
    r.add_argument("--again", action="store_true",
                   help="이미 올린 편을 **일부러** 다시 올린다")
    r.add_argument("--dry", action="store_true",
                   help="연습 — 올리기 직전까지만 해 보고 실제로는 올리지 않는다")

    x = sub.add_parser("fixmeta",
                       help="이미 올린 편의 제목·설명·해시태그만 고친다 (0원)")
    x.add_argument("sid")
    x.add_argument("--part", default="all", help="몇 편인가 (1/2/3… 또는 all)")
    x.add_argument("--meta", required=True)
    x.add_argument("--dry", action="store_true",
                   help="연습 — 무엇으로 바뀌는지만 보여 주고 안 고친다")

    args = ap.parse_args()
    try:
        if args.cmd == "fixmeta":
            return cmd_fixmeta(args)
        if args.cmd == "series":
            return cmd_series(args)
        if args.cmd == "meta":
            return cmd_meta(args)
        if args.cmd == "public":
            return cmd_public(args)
        if args.cmd == "private":
            return cmd_private(args)
        if args.cmd == "shorts":
            return cmd_shorts(args)
        if args.cmd == "thumb":
            return cmd_thumb(args)
        return cmd_publish(args)
    except RuntimeError as e:
        print(f"❌ {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
