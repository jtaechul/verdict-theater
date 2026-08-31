#!/usr/bin/env python3
"""⭐ 90초 한 편을 만든다 — 그림 + 나레이션 + 자막 (2026-08-27 신설).

    python3 src/short90.py stills          컷마다 그림 한 장 (세로 9:16)
    python3 src/short90.py voice           컷마다 소리 (나레이션·대사)
    python3 src/short90.py build           한 편으로 조립 → build/s90/S90_short.mp4
    python3 src/short90.py all             위 셋을 차례로

왜 16화가 아니라 한 편인가
    운영자 확정 — "90초로 만들어." 16화는 한 화에 사건이 하나뿐이라 "그래서
    뭔데" 를 16번 기다려야 했다. 한 편이면 5초 만에 32억이 나온다.

왜 Veo 를 안 쓰나 (기본값)
    운영자: "비오로 하기 돈아까우니까." 컷마다 영상을 만들면 90초에 7천 원이
    넘는다. **그림 한 장 + 나레이션**으로 만들면 같은 90초가 3천 원대다.
    손님이 보고 좋다고 한 참고 영상들도 전부 이 방식이다.
    대사 컷을 손으로 좋게 만들고 싶으면 S90.json 의 `veo` 프롬프트를 제미나이에
    붙여 만든 mp4 를 build/s90/clips/c07.mp4 로 넣어 두면 그 컷만 영상이 된다.

화면 (1080 × 1920 · 세로 꽉 채움)
    그림이 화면 전체 · 아주 느린 줌
    y 1300~1620  자막 (대사 컷은 위에 이름표)
    y 1620~1920  비움 — 유튜브 쇼츠 단추가 덮는 자리
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cost                                                  # noqa: E402
import reuse                                                 # noqa: E402
import still as ST                                           # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "data" / "series" / "S90.json"
OUT = ROOT / "build" / "s90"

W, H = 1080, 1920
FPS = 30
FONT_SUB = ROOT / "assets" / "fonts" / "NanumGothic_ExtraBold.ttf"
FONT_NAME = ROOT / "assets" / "fonts" / "KoPub_Batang_Pro_Bold.otf"

SUB_TOP, SUB_BOT = 1300, 1620    # 자막 칸 (아래 300px 은 쇼츠 단추 자리라 비운다)
SUB_MAX, SUB_MIN, SUB_LINES = 84, 58, 3
SUB_GAP = 1.24
SIDE = 60
# ⭐⭐ 2026-08-31 손님: "등장인물 소개 문구는 잘 보이게 바꿔 주고 왼쪽에
#    세로로 된 바(bar)를 그어 줘."
#    예전 이름표는 **가운데 정렬 + 옅은 금색 + 테두리 없음**이라, 아내의 밝은
#    가디건 위에서 글자가 그대로 묻혔다. 방송 자막처럼 바꾼다 —
#    왼쪽에 금색 세로 막대를 세우고, 그 옆에 왼쪽 맞춤으로 크게 적는다.
NAME_Y, NAME_SIZE = 1214, 54
NAME_BAR_W = 7          # 왼쪽 세로 막대 두께
NAME_BAR_GAP = 20       # 막대와 글자 사이
NAME_BAR_PAD = 7        # 막대가 글자 위아래로 더 뻗는 정도
SCRIM_TOP = 1080                 # 여기부터 아래로 서서히 어두워진다
SCRIM_MAX = 0.88                 # 맨 아래 어두움 (0~1)
MARK_SIZE, MARK_Y = 34, 44
CHANNEL = "판결극장"
GOLD = (198, 160, 74, 255)
GOLD_BRIGHT = (232, 197, 112, 255)   # 이름표 글자 — 밝은 그림 위에서도 읽히게

# ⭐⭐ 2026-08-31 손님: "카라오케 자막으로 변경하자."
#    한 낱말씩 불이 들어온다 — 지금 말하는 낱말이 금색으로 도드라진다.
#    ① 이미 말한 낱말  흰색 그대로
#    ② 지금 말하는 낱말 금색 (여기가 카라오케다)
#    ③ 아직 안 한 낱말 흰색을 흐리게
#    ⚠️ 흐린 글자도 **읽을 수는 있어야** 한다. 너무 흐리면 다음 말을 눈으로
#       못 좇는다 — 40% 아래로는 내리지 않는다.
SUB_DONE = (255, 255, 255, 255)
SUB_NOW = (245, 205, 116, 255)
SUB_TODO = (255, 255, 255, 112)
WHITE = (255, 255, 255, 255)
PAD = 0.55                       # 말이 끝난 뒤 남기는 여운(초)
ZOOM_TO = 1.10                   # 컷 하나 도는 동안 커지는 정도
ZOOM_SRC = 1.4                   # 줌 전에 그림을 키워 두는 배수 (떨림 방지)

# 목소리 — 사람마다 고정한다 (컷마다 달라지면 딴 사람이 된다)
# ⭐⭐⭐ 2026-08-31 손님 확정: "갈아탄다."
#
#   ⚠️ 여기가 목소리가 밋밋했던 **까닭 그 자체**였다. 이름이 `ko-KR-…` 이면
#      tts.say() 가 곧장 옛 구글 엔진으로 보낸다. 그 엔진에는 연기 지시를
#      받는 자리가 아예 없다. 16화 쪽에는 지시를 보내는 길이 다 만들어져
#      있는데 90초 편만 그 길을 안 쓰고 있었다.
#      → 제미나이 목소리 이름으로 바꾸면 그 길이 열린다.
#
#   나이에 맞춰 고른다 (tts.MATURE_F / MATURE_M 과 같은 결) —
#     아내 52세·남편 55세 → 연륜 있는 목소리
#     내연녀 30대·딸 20대 → 젊은 목소리
#     나레이션은 **누구와도 안 겹치는** 목소리여야 한다
VOICE = {
    "나레이션": "Alnilam",       # 낮고 묵직 — 사건을 전하는 소리
    "아내": "Gacrux",            # 연륜 — 50대 여성
    "내연녀": "Erinome",         # 젊다 — 30대 여성
    "남편": "Algenib",           # 거칠다 — 50대 남성
    "변호사": "Iapetus",         # 사무적 — 40대 남성
    "딸": "Leda",                # 어리다 — 20대 여성
}
NARR_RATE = 1.02                 # 나레이션은 아주 조금 빠르게 (또박또박은 유지)


class Short90Error(RuntimeError):
    pass


def turns_of(c):
    """이 컷에서 말하는 차례. 옛 대본(turns 없음)도 받아 준다."""
    if c.get("turns"):
        return [(w, t) for w, t in c["turns"]]
    return [(c.get("kind") or "나레이션", c.get("text") or "")]


def is_narr(c):
    return all(w == "나레이션" for w, _ in turns_of(c))


def load():
    if not DOC.exists():
        raise Short90Error("data/series/S90.json 이 없다 — "
                           "python3 tools/build_short90.py 를 먼저 돌린다.")
    return json.loads(DOC.read_text(encoding="utf-8"))


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise Short90Error(f"ffmpeg 가 실패했다:\n{p.stderr[-900:]}")
    return p.stdout


def dur_of(path):
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=nw=1:nk=1", str(path)])
    return float(out.strip() or 0)


def has_audio(path):
    """이 영상에 소리가 붙어 있는가."""
    out = run(["ffprobe", "-v", "error", "-select_streams", "a",
               "-show_entries", "stream=codec_type", "-of",
               "default=nw=1:nk=1", str(path)])
    return "audio" in out


# ── ① 그림 ────────────────────────────────────────────────────
# 화면 이름 ↔ 인물 카드 파일 이름 (카드에는 아내가 '본처' 로 적혀 있다)
ST_NAME = {"아내": "본처"}


def cards_dir():
    return OUT / "cards"


def salvage(d, suffix=".png"):
    """이미 만들어 둔 것을 **지문으로** 찾아 둔다 — {지문: 파일 내용}.

    ⚠️⚠️ 2026-08-31 — 컷 하나를 중간에 끼워 넣었더니 뒤 컷 번호가 전부 하나씩
       밀렸다. 파일 이름이 컷 번호(c13.png)라, 내용은 그대로인데 **이름이
       어긋나** 여덟 장을 다시 그릴 뻔했다 (1,056원).
       → 이름이 아니라 **지문**으로 찾는다. 앞으로 컷을 끼워 넣어도 값이 안 든다.
       ⚠️ 먼저 통째로 읽어 두고 나서 쓴다. 하나씩 옮기면 아직 안 옮긴 것을
          덮어써 버린다 (13→14 를 쓰는 순간 원래 14 가 사라진다).
    """
    have = {}
    for f in sorted(Path(d).glob(f"*{suffix}")):
        sg = reuse.sig_file(f)
        if not sg.exists():
            continue
        key = sg.read_text(encoding="utf-8").strip()
        if key and key not in have:
            have[key] = f.read_bytes()
    return have


def stills(doc):
    d = OUT / "stills"
    d.mkdir(parents=True, exist_ok=True)
    kept = salvage(d)
    print(f"■ 컷 그림 {len(doc['cuts'])}장 (세로 9:16 · 약 "
          f"{cost.image_krw(ST.MODEL, ST.SIZE) * len(doc['cuts']):,.0f}원)")
    made = 0
    for c in doc["cuts"]:
        out = d / f"c{c['n']:02d}.png"
        refs = [p for p in (ST.card_path(cards_dir(), ST_NAME.get(w, w))
                            for w in c.get("who") or []) if p.exists()]
        sig = reuse.sig_of(c["still"], *refs)
        ok, why = reuse.can_reuse(out, sig)
        print(f"  컷{c['n']:>2} {'·'.join(c.get('who') or []) or '—'}")
        if ok:
            print("    (그대로다 — 건너뛴다)")
            made += 1
            continue
        # ⭐ 이름은 어긋났어도 **같은 지문**의 그림이 있으면 그것을 옮겨 쓴다
        #    (컷을 끼워 넣어 번호가 밀렸을 때 — 값이 안 든다)
        if sig in kept:
            out.write_bytes(kept[sig])
            reuse.stamp(out, sig)
            print("    (이름만 밀렸다 — 그대로 옮겨 쓴다 · 0원)")
            made += 1
            continue
        if why:
            print(f"    ⚠️ {why} — 다시 만든다")
        ST.gen(c["still"], out, refs=refs, ratio="9:16",
               seed=ST.seed_of("S90", c["n"]))
        reuse.stamp(out, sig)
        made += 1
    print(f"\n■ 그림 {made}/{len(doc['cuts'])}장")
    return 0 if made == len(doc["cuts"]) else 1


# ── ② 소리 ────────────────────────────────────────────────────
def voice_route_ok(tts, need):
    """이 길로 **필요한 줄 수만큼** 만들 수 있는가 — 만들기 **전에** 본다.

    ⚠️⚠️ 2026-08-31 — 여기가 조용히 망가지는 자리다.
       제미나이 목소리는 두 길이 있는데 한도가 하늘과 땅 차이다.
         구글 클라우드 길 — 하루 횟수 제한 없음
         AI 스튜디오 길   — **무료 등급 하루 10번**
       우리는 스물세 줄이 필요하다. 스튜디오 길로 가면 열한 번째 줄부터
       막히고, tts.say() 가 조용히 옛 구글 목소리로 물러선다. 그러면
       **한 편 안에서 아내 목소리가 중간에 바뀌고 감정이 사라진다.**
       영상은 멀쩡히 나오므로 눈으로는 안 보인다 — 그게 제일 나쁘다.
       → 돈 쓰기 전에 미리 보고, 안 되면 **아예 시작하지 않는다.**
    """
    if str(os.environ.get("SKIP_VOICE_ROUTE", "")).strip() == "1":
        return
    note = tts.route_note()
    print(f"■ 목소리 길: {note}")
    if "하루 10번" in note and need > 10:
        raise Short90Error(
            f"이 길로는 {need}줄을 못 만듭니다 (하루 10번까지).\n"
            f"   지금 길: {note}\n"
            f"   → 구글 클라우드 콘솔에서 **Vertex AI API"
            f"(aiplatform.googleapis.com)** 를 [사용] 하면 열립니다.\n"
            f"   그냥 밀어붙이면 열한 번째 줄부터 옛 목소리로 바뀌어 "
            f"한 편 안에서 사람 목소리가 달라집니다.")


def voices(doc):
    import tts                                               # 늦게 부른다(열쇠 필요)
    d = OUT / "voice"
    d.mkdir(parents=True, exist_ok=True)
    need = sum(len(turns_of(c)) for c in doc["cuts"])
    voice_route_ok(tts, need)
    print(f"■ 소리 {len(doc['cuts'])}줄")
    made = 0
    for c in doc["cuts"]:
        out = d / f"c{c['n']:02d}.wav"
        turns = turns_of(c)
        # ⭐ 줄마다 **어떻게 읽을지**(say)를 같이 들고 간다. 이게 이번 바꿈의
        #   핵심 — 같은 글자라도 어떻게 읽으라고 말해 주면 낭독이 연기가 된다.
        says = c.get("say") or [""] * len(turns)
        plan = [(w, t, VOICE.get(w) or VOICE["나레이션"],
                 NARR_RATE if w == "나레이션" else 1.0,
                 says[i] if i < len(says) else "")
                for i, (w, t) in enumerate(turns)]
        # ⚠️ 지문에 지시도 넣는다 — 지시를 고치면 그 줄만 다시 만들어야 한다
        sig = reuse.sig_of(*[f"{w}|{t}|{v}|{r}|{h}" for w, t, v, r, h in plan])
        ok, why = reuse.can_reuse(out, sig)
        # ⚠️ 길이 기록이 없으면 자막을 맞출 수가 없다 → 그 컷만 다시 만든다
        if ok and not lens_of(out).exists():
            ok, why = False, "줄마다 길이 기록이 없다 — 자막을 못 맞춘다"
        print(f"  컷{c['n']:>2} [{'·'.join(w for w, _ in turns)}] {c['text'][:30]}")
        if ok:
            print("    (그대로다 — 건너뛴다)")
            made += 1
            continue
        if why:
            print(f"    ⚠️ {why} — 다시 만든다")
        # ⭐ 한 컷 안에서 두 사람이 주고받으면 목소리를 따로 만들어 이어 붙인다
        parts = []
        for i, (w, t, v, r, how) in enumerate(plan):
            one = d / f"c{c['n']:02d}_{i}.wav"
            # 지시가 있으면 구글이 권하는 모양 그대로 (지시 → 쌍점 → 큰따옴표)
            style = f'{how} 다음 큰따옴표 안의 말만 그대로: "{t}"' if how else None
            got = tts.say(t, v, r, 0.0, one, style=style)
            if not got or not Path(got).exists():
                raise Short90Error(f"컷{c['n']} {w} 소리를 못 만들었다")
            parts.append(Path(got))
        # ⭐⭐ 2026-08-31 손님: "대사 목소리와 자막이 시간차가 발생."
        #    자막 바뀌는 때를 **글자 수로 짐작**하고 있었다. 그런데 실제로
        #    말하는 데 걸리는 시간은 글자 수와 안 맞는다(사람마다 속도가
        #    다르고 쉼도 있다). 게다가 컷 길이에는 여운(PAD)까지 들어 있어
        #    자막이 통째로 늘어났다 — 그래서 첫 줄이 오래 남고 둘째 줄이
        #    목소리보다 늦게 떴다.
        #    → 여기서 **줄마다 진짜 길이**를 재서 적어 둔다. 짐작을 없앤다.
        lens_of(out).write_text(
            json.dumps([round(dur_of(x), 3) for x in parts]), encoding="utf-8")
        if len(parts) == 1:
            parts[0].replace(out)
        else:
            lst = d / f"c{c['n']:02d}.txt"
            lst.write_text("".join(f"file '{x.name}'\n" for x in parts),
                           encoding="utf-8")
            run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
                 "-i", str(lst), "-c", "copy", str(out)])
            for x in parts:
                x.unlink(missing_ok=True)
            lst.unlink(missing_ok=True)
        reuse.stamp(out, sig)
        made += 1
        print(f"    ✅ {out.name} ({dur_of(out):.1f}초)")
    print(f"\n■ 소리 {made}/{len(doc['cuts'])}줄")
    return 0 if made == len(doc["cuts"]) else 1


# ── ③ 자막 그림 ───────────────────────────────────────────────
def wrap(d, text, font, max_w):
    lines, cur = [], ""
    for word in str(text).split():
        t = (cur + " " + word).strip()
        if cur and d.textlength(t, font=font) > max_w:
            lines.append(cur)
            cur = word
        else:
            cur = t
    if cur:
        lines.append(cur)
    return lines


def fit(d, text, size_max, max_w, max_h):
    """칸에 들어갈 때까지 글자를 줄인다. 어르신용이라 SUB_MIN 아래로는 안 줄인다."""
    for size in range(size_max, SUB_MIN - 1, -2):
        f = ImageFont.truetype(str(FONT_SUB), size)
        lines = wrap(d, text, f, max_w)
        if len(lines) <= SUB_LINES and len(lines) * size * SUB_GAP <= max_h:
            return f, lines, size
    f = ImageFont.truetype(str(FONT_SUB), SUB_MIN)
    return f, wrap(d, text, f, max_w)[:SUB_LINES], SUB_MIN


def overlay(c, out, turn=None, now=None):
    """컷 하나(또는 그 안의 한 차례)의 자막·이름표를 투명 그림으로 그린다.

    now — 지금 말하고 있는 **낱말 번호** (0부터). None 이면 전부 흰색.
    """
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    # 아래쪽 어둡게 — 그림 위에 흰 글자를 얹어도 읽히게 (서서히 진해진다)
    scrim = Image.new("RGBA", (W, H - SCRIM_TOP), (0, 0, 0, 0))
    sd = ImageDraw.Draw(scrim)
    # ⚠️ 맨 아래(1920)에서 가장 진해지게 두면 **자막이 있는 자리(1300~1620)가
    #    아직 옅다.** 밝은 그림 위에서 글자가 묻힌다 — 자막 칸 아래쪽에서
    #    이미 가장 진하도록 잡는다.
    span = H - SCRIM_TOP
    full = max(1, SUB_BOT - SCRIM_TOP)
    for y in range(span):
        a = int(255 * SCRIM_MAX * min(1.0, y / full) ** 1.2)
        sd.line([(0, y), (W, y)], fill=(0, 0, 0, a))
    img.alpha_composite(scrim, (0, SCRIM_TOP))

    d = ImageDraw.Draw(img)
    # 채널 이름 (오른쪽 위, 조용하게)
    mf = ImageFont.truetype(str(FONT_NAME), MARK_SIZE)
    d.text((W - SIDE, MARK_Y), CHANNEL, font=mf, fill=(255, 255, 255, 168),
           anchor="ra")

    who, text = turn if turn else ("나레이션" if is_narr(c) else c["kind"], c["text"])

    # 이름표 — 대사만 (나레이션은 말하는 사람이 없다)
    #   ⭐ 왼쪽 금색 세로 막대 + 왼쪽 맞춤 글자 + 검은 테두리.
    #     막대 높이는 **글자가 실제로 차지하는 높이**를 재서 맞춘다 —
    #     이름이 두 글자든 세 글자든 늘 글자와 나란하다.
    if who != "나레이션":
        nf = ImageFont.truetype(str(FONT_NAME), NAME_SIZE)
        tx = SIDE + NAME_BAR_W + NAME_BAR_GAP
        box = d.textbbox((tx, NAME_Y), who, font=nf, anchor="la")
        d.rectangle([SIDE, box[1] - NAME_BAR_PAD,
                     SIDE + NAME_BAR_W, box[3] + NAME_BAR_PAD], fill=GOLD)
        d.text((tx, NAME_Y), who, font=nf, fill=GOLD_BRIGHT, anchor="la",
               stroke_width=3, stroke_fill=(0, 0, 0, 205))

    # 자막 — **낱말 하나씩** 그린다 (카라오케)
    #   now 가 None 이면 옛날처럼 전부 흰색 (자막 한 장짜리)
    #   now 가 숫자면 그 낱말이 지금 말하는 것 — 금색으로 도드라진다
    f, lines, size = fit(d, text, SUB_MAX, W - SIDE * 2, SUB_BOT - SUB_TOP)
    step = size * SUB_GAP
    y = SUB_TOP + max(0, ((SUB_BOT - SUB_TOP) - len(lines) * step) / 2)
    k = 0                                    # 몇 번째 낱말까지 그렸나
    space = d.textlength(" ", font=f)
    for ln in lines:
        ws = ln.split()
        wide = sum(d.textlength(w, font=f) for w in ws) + space * (len(ws) - 1)
        x = (W - wide) / 2                   # 줄 전체를 가운데에 놓는다
        for w in ws:
            if now is None:
                fill = WHITE
            elif k < now:
                fill = SUB_DONE
            elif k == now:
                fill = SUB_NOW
            else:
                fill = SUB_TODO
            # 얇은 검은 테두리 — 밝은 그림 위에서도 글자가 안 묻힌다
            d.text((x, y), w, font=f, fill=fill, anchor="la",
                   stroke_width=4, stroke_fill=(0, 0, 0, 210))
            x += d.textlength(w, font=f) + space
            k += 1
        y += step
    img.save(out)
    return out


# ── ④ 조립 ────────────────────────────────────────────────────
def lens_of(wav):
    """그 컷의 **줄마다 소리 길이**를 적어 둔 자리 (자막을 맞추는 데 쓴다)."""
    return Path(wav).with_suffix(".len.json")


def syl(t):
    """한국어 글자 수 (자막이 떠 있을 시간을 나누는 잣대)."""
    return max(1, len([x for x in str(t) if not x.isspace()]))


def sub_windows(c, sec, voice):
    """자막 한 줄씩 **언제부터 언제까지** 떠 있을지.

    ⭐⭐ 2026-08-31 손님: "대사 목소리와 자막이 시간차가 발생."
       예전에는 **글자 수로 짐작**해 컷 길이를 나눴다. 두 군데가 어긋난다 —
         ① 글자 수와 실제 말하는 시간은 안 맞는다 (속도·쉼이 사람마다 다르다)
         ② 컷 길이(sec)에는 말이 끝난 뒤의 여운(PAD)과 대본에 적힌 넉넉한
            초까지 들어 있다. 그 비율로 나누면 자막이 **통째로 늘어나서**
            첫 줄이 오래 남고 둘째 줄이 목소리보다 늦게 뜬다.
       이제 소리를 만들 때 적어 둔 **줄마다 진짜 길이**로 나눈다.
       (voice 가 None 이면 — 올린 영상의 소리를 쓰는 컷 — 옛 방식으로 돌아간다)
    """
    turns = turns_of(c)
    real = []
    if voice:
        f = lens_of(voice)
        if f.exists():
            try:
                got = json.loads(f.read_text(encoding="utf-8"))
                if isinstance(got, list) and len(got) == len(turns):
                    real = [float(x) for x in got]
            except Exception:                                # noqa: BLE001
                real = []
    at, t0 = [], 0.0
    if real:
        for i, d in enumerate(real):
            # 마지막 줄은 여운까지 끌고 간다 (말이 끝나도 글은 남아 있어야 한다)
            t1 = sec if i == len(real) - 1 else min(sec, t0 + d)
            at.append((t0, t1))
            t0 = t1
    else:
        tot = sum(syl(t) for _, t in turns)
        for i, (_, t) in enumerate(turns):
            t1 = sec if i == len(turns) - 1 else t0 + sec * syl(t) / tot
            at.append((t0, t1))
            t0 = t1
    return at


def cut_sec(c, voice, clip):
    """이 컷이 몇 초짜리인가, 그리고 소리를 올린 영상에서 가져오는가.

    ⚠️ 자막 장을 만들려면 컷 길이를 **먼저** 알아야 한다. 그래서 길이 셈을
       cut_video 밖으로 꺼내 두 곳이 같은 값을 쓰게 한다 (따로 세면 어긋난다).
    """
    clip = Path(clip) if clip and Path(clip).exists() else None
    talks = not is_narr(c)
    if clip and talks and has_audio(clip):
        return dur_of(clip), True
    return max(float(c["sec"]), dur_of(voice) + PAD), False


def karaoke(c, sec, voice, d, n):
    """카라오케 자막 장들 — [(그림, 언제부터, 언제까지), …].

    ⭐⭐ 2026-08-31 손님: "카라오케 자막으로 변경하자."
       한 낱말씩 불이 들어오게 하려면 낱말마다 자막 장이 한 장씩 필요하다.
       낱말이 언제 나오는지는 **그 줄의 진짜 소리 길이**(.len.json)를
       글자 수로 나눠 잡는다 — 컷 안에서 자막이 목소리를 따라가게 한 것과
       같은 잣대다.

    ⚠️ 낱말 시간은 **재는 것이 아니라 나누는 것**이다. 구글 목소리는 낱말이
       언제 나오는지 안 알려 준다. 그래서 글자 수로 고르게 나눈다 — 한 줄
       안에서는 오차가 크지 않다(줄 자체는 진짜 길이에 맞춰 놓았기 때문).
    """
    # ⚠️ 2026-08-31 진짜 크기 시험이 잡았다 — 여기서 폴더를 안 만들고 있었다.
    #    build() 가 미리 만들어 줘서 안 드러났을 뿐, 다른 데서 부르면 죽는다.
    #    "부르는 쪽이 챙겨 주겠지" 는 언젠가 반드시 어긋난다.
    d = Path(d)
    d.mkdir(parents=True, exist_ok=True)
    turns = turns_of(c)
    wins = sub_windows(c, sec, voice)
    out = []
    for i, ((who, text), (a, b)) in enumerate(zip(turns, wins)):
        words = str(text).split()
        if not words:
            continue
        span = max(0.05, b - a)
        tot = sum(syl(w) for w in words)
        t0 = a
        for k, w in enumerate(words):
            t1 = b if k == len(words) - 1 else t0 + span * syl(w) / tot
            png = d / f"c{n:02d}_{i}_{k:02d}.png"
            overlay(c, png, (who, text), now=k)
            out.append((png, t0, t1))
            t0 = t1
    return out


def cut_video(c, still, voice, clip, ovs, out):
    """컷 하나 → mp4. 손으로 만든 영상(clip)이 있으면 그것을 쓰고, 없으면 그림.

    ⭐⭐ 2026-08-27 손님: "이미지는 중간중간 섞여 있고 동영상도 있어야 돼."
       그래서 소리를 누가 낼지도 컷마다 갈린다 —
         · **대사 컷 + 올린 영상** → 그 영상 안에서 사람이 한국어로 말한다.
           우리 목소리를 덮어씌우면 입과 소리가 어긋난다 → **영상 소리를 쓴다**
         · **나레이션 컷** → 화면에서 아무도 말하지 않는다 → **우리 나레이션**
           (영상을 올렸어도 그 소리는 안 쓴다. 그래야 나레이션이 안 묻힌다)
    """
    clip = Path(clip) if clip and Path(clip).exists() else None
    # ⚠️ 길이는 cut_sec 한 곳에서만 센다. 자막 장을 만드는 쪽도 같은 값을 쓴다.
    sec, use_clip_audio = cut_sec(c, voice, clip)
    if use_clip_audio:
        # ⚠️ 말하는 길이는 **영상이 정한다.** 대본의 초에 맞춰 늘이거나 줄이면
        #    말이 잘리거나 같은 말이 두 번 나온다. 컷 길이 = 영상 길이.
        snd = []                      # 소리는 영상(0번) 안에 있다
        amap = "0:a"
        loop = []                     # 늘일 일이 없으니 되돌려 잇지 않는다
    else:
        snd = ["-i", str(voice)]      # 0=화면 · 자막들 · 마지막이 우리 목소리
        loop = ["-stream_loop", "-1"] if clip else []
    frames = max(2, int(round(sec * FPS)))
    if clip:
        # ⚠️ 올린 영상이 컷보다 짧으면 마지막 그림이 얼어붙는다 — 되돌려 잇는다
        src = [*loop, "-i", str(clip)]
        vf = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,"
              f"crop={W}:{H},fps={FPS},trim=0:{sec:.3f},setpts=PTS-STARTPTS[bg];")
    else:
        src = ["-loop", "1", "-i", str(still)]
        # 조금 키운 뒤 아주 느리게 줌 — 원본 크기에서 바로 줌하면 덜덜 떨린다.
        # ⚠️ 2배로 키우면 컷 하나에 6초씩 걸려 23컷이 너무 느리다. 1.4배면
        #    1.10 배 줌까지 또렷하고 속도는 3분의 2다.
        sw, sh = int(W * ZOOM_SRC), int(H * ZOOM_SRC)
        step = (ZOOM_TO - 1) / frames
        # 컷마다 줌 방향을 바꾼다 — 스물세 컷이 다 같은 쪽으로 커지면 지겹다
        z = (f"min(1+{step:.6f}*on,{ZOOM_TO})" if c["n"] % 2 else
             f"max({ZOOM_TO}-{step:.6f}*on,1.0)")
        vf = (f"[0:v]scale={sw}:{sh}:force_original_aspect_ratio=increase,"
              f"crop={sw}:{sh},"
              f"zoompan=z='{z}':d={frames}:x='iw/2-(iw/zoom/2)'"
              f":y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={FPS}[bg];")
    # ⭐ 한 컷 안에서 두 사람이 주고받으면 **자막도 차례대로** 바뀌어야 한다.
    #
    # ⭐⭐ 2026-08-31 손님: "대사 목소리와 자막이 시간차가 발생."
    #    예전에는 **글자 수로 짐작**해 컷 길이를 나눴다. 두 군데가 어긋난다 —
    #      ① 글자 수와 실제 말하는 시간은 안 맞는다 (사람마다 속도·쉼이 다르다)
    #      ② 컷 길이(sec)에는 말이 끝난 뒤의 여운(PAD)과 대본에 적힌 넉넉한
    #         초까지 들어 있어, 그 비율로 나누면 자막이 통째로 늘어난다.
    #         → 첫 줄이 오래 남고, 둘째 줄이 목소리보다 **늦게** 뜬다.
    #    이제 소리를 만들 때 적어 둔 **줄마다 진짜 길이**로 나눈다.
    #    (올린 영상의 소리를 쓰는 컷은 우리 목소리가 아니므로 옛 방식 그대로)
    #    이제 자막 장은 **낱말마다 한 장**이고, 각자 자기 시간대를 달고 온다
    #    (karaoke 가 만들어 준다). 여기서는 그 시간대에만 얹어 주면 된다.
    chain = "[bg]"
    for i, (_png, a, b) in enumerate(ovs):
        nxt = f"[v{i}]" if i < len(ovs) - 1 else "[v]"
        chain_in = chain
        vf += (f"{chain_in}[{i + 1}:v]overlay=0:0:format=auto"
               f":enable='between(t,{a:.3f},{b:.3f})'{nxt};")
        chain = nxt
    vf = vf.rstrip(";")
    ovin = []
    for o, _a, _b in ovs:
        ovin += ["-i", str(o)]
    # 소리 입력 번호는 화면(0) + 자막 장수 뒤부터다
    if not use_clip_audio:
        amap = f"{1 + len(ovs)}:a"
    run(["ffmpeg", "-y", "-v", "error", *src, *ovin, *snd,
         "-filter_complex", vf,
         "-map", "[v]", "-map", amap, "-af", "apad",
         "-t", f"{sec:.3f}", "-r", str(FPS),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
         "-shortest", str(out)])
    return sec


def build(doc):
    stills_d, voice_d = OUT / "stills", OUT / "voice"
    clips_d = OUT / "clips"
    parts_d = OUT / "parts"
    parts_d.mkdir(parents=True, exist_ok=True)
    (OUT / "ov").mkdir(parents=True, exist_ok=True)

    total, parts = 0.0, []
    print(f"■ 「{doc['title']}」 {len(doc['cuts'])}컷 조립")
    for c in doc["cuts"]:
        n = c["n"]
        still = stills_d / f"c{n:02d}.png"
        voice = voice_d / f"c{n:02d}.wav"
        clip = clips_d / f"c{n:02d}.mp4"
        if not still.exists() and not clip.exists():
            raise Short90Error(f"컷{n} 그림이 없다 — 먼저 stills 를 돌린다")
        if not voice.exists():
            raise Short90Error(f"컷{n} 소리가 없다 — 먼저 voice 를 돌린다")
        # ⭐ 카라오케 — 낱말마다 자막 장 한 장. 컷 길이를 먼저 알아야 하므로
        #    길이 셈(cut_sec)을 여기서 한 번 하고, cut_video 도 같은 값을 쓴다.
        sec0, uca = cut_sec(c, voice, clip if clip.exists() else None)
        ovs = karaoke(c, sec0, None if uca else voice, OUT / "ov", n)
        out = parts_d / f"c{n:02d}.mp4"
        sec = cut_video(c, still, voice, clip if clip.exists() else None, ovs, out)
        total += sec
        parts.append(out)
        if not clip.exists():
            mark = "그림"
        elif is_narr(c):
            mark = "영상 + 우리 나레이션"
        else:
            mark = "영상 (그 안에서 말한다)" if has_audio(clip) else "영상 + 우리 목소리"
        print(f"  컷{n:>2} [{c['kind']:<4}] {sec:>5.2f}초 ({mark})")

    # ⚠️ concat 목록 안의 경로는 **목록 파일이 있는 자리 기준**이다. 파일 이름만
    #    적으면 옆 폴더에 있는 컷을 못 찾는다 (시험이 바로 잡아 줬다).
    lst = OUT / "parts.txt"
    lst.write_text("".join(f"file '{p.relative_to(OUT)}'\n" for p in parts),
                   encoding="utf-8")
    final = OUT / "S90_short.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
         "-i", str(lst), "-c", "copy", str(final)])
    got = dur_of(final)
    try:
        name = final.relative_to(ROOT)
    except ValueError:                     # 시험처럼 저장소 밖에 만들 때
        name = final
    print(f"\n■ {name} — {got:.1f}초 ({final.stat().st_size / 1e6:.1f}MB)")
    if got < 60 or got > 130:
        print(f"  ⚠️ 90초 편인데 {got:.0f}초다 — 대본 길이를 손봐야 한다")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["stills", "voice", "build", "all"])
    a = ap.parse_args()
    try:
        doc = load()
        if a.what in ("stills", "all"):
            if stills(doc):
                return 1
        if a.what in ("voice", "all"):
            if voices(doc):
                return 1
        if a.what in ("build", "all"):
            return build(doc)
        return 0
    except (Short90Error, ST.StillError, cost.MonthlyCapReached) as e:
        print(f"❌ {e}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
