#!/usr/bin/env python3
"""금고의 제미나이 열쇠가 **결제가 붙은 열쇠인가**. 값 0원.

    python3 tools/gemini_key_check.py

왜 이 검사가 있는가 (2026-08-23)
    그림·영상이 429 로 막혔다. 계정은 유료(Tier 1 선불)인데, 시스템에 담긴 열쇠가
    **결제가 안 붙은 다른 프로젝트 것**이었다. 글자 생성은 멀쩡히 됐기 때문에
    "열쇠는 살아 있다" 로만 보였고, 그림을 실제로 만들어 보기 전에는 안 드러났다.

값이 0원인 까닭
    그림 모델에게 "그림 말고 글자로 답하라" 고 시킨다. 한도는 **모델 단위**로
    걸리므로 무료 등급이면 이 요청도 똑같이 429 로 막힌다(막히면 0원).
    통과하면 글자 몇 자 값만 든다 — 0.01원이 안 된다.

    Veo(영상)만 싸게 찔러볼 길이 없다. 4초만 만들어도 340원쯤 든다.
    그림이 통과하면 결제가 붙었다는 뜻이므로 영상도 같이 열린다.
"""

import hashlib
import json
import os
import sys
import urllib.error
import urllib.request

API = "https://generativelanguage.googleapis.com/v1beta/models"
IMAGE_MODELS = ["gemini-2.5-flash-image", "gemini-3.1-flash-lite-image"]


def text_model(key):
    """글자 모델 이름을 **목록에서 골라온다.**

    ⚠️ 처음엔 'gemini-2.5-flash' 를 박아 뒀는데 새 열쇠에서 404 가 났다 —
       "이 모델은 새 사용자에게 더 이상 제공되지 않습니다". 새로 만든 프로젝트는
       옛 모델을 못 쓴다. 이름을 박으면 열쇠를 갈아낄 때마다 이런 일이 난다.
       진짜 파이프라인(src/llm.py)도 목록에서 골라 쓰므로 방식을 맞춘다."""
    req = urllib.request.Request(f"{API}?pageSize=200",
                                 headers={"x-goog-api-key": key})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
    except Exception:
        return None, []
    names = []
    for m in data.get("models", []):
        n = m.get("name", "").split("/")[-1]
        if "generateContent" not in m.get("supportedGenerationMethods", []):
            continue
        if any(x in n for x in ("image", "tts", "embedding", "veo", "vision")):
            continue
        names.append(n)
    # 값싼 flash 계열을 먼저, 없으면 아무거나
    pick = next((n for n in names if "flash" in n and "lite" not in n),
                next((n for n in names if "flash" in n), names[0] if names else None))
    return pick, names


def call(model, body, key):
    req = urllib.request.Request(
        f"{API}/{model}:generateContent",
        data=json.dumps(body).encode(),
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {}
    except Exception as e:
        return 0, {"error": {"message": str(e)}}


def main():
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    print("## 제미나이 열쇠 점검 (값 0원)")
    print()
    if not key:
        print("**금고에 GEMINI_API_KEY 가 없습니다.**")
        return 1

    # 열쇠 값은 절대 안 찍는다. 어느 열쇠인지 알아볼 수 있는 표시만 찍는다.
    print(f"- 열쇠 끝 4자리 `{key[-4:]}` · 지문 `{hashlib.sha256(key.encode()).hexdigest()[:8]}` "
          f"(값은 찍지 않습니다)")
    print()
    print("| 무엇 | 결과 |")
    print("|---|---|")

    tm, names = text_model(key)
    ok_text = False
    if not tm:
        mark = "쓸 수 있는 글자 모델이 목록에 없습니다"
    else:
        st, body = call(tm, {"contents": [{"parts": [{"text": "hi"}]}],
                             "generationConfig": {"maxOutputTokens": 1}}, key)
        if st == 200:
            ok_text, mark = True, f"통과 — `{tm}` 로 대본·심사·채점을 합니다"
        elif st == 429:
            mark = "한도 초과 — 무료 등급이거나 잔액이 0원입니다"
        else:
            mark = f"막힘 (HTTP {st}) — {(body.get('error') or {}).get('message', '')[:80]}"
    print(f"| 글자 (대본) | {mark} |")
    if names:
        print(f"| 쓸 수 있는 글자 모델 | {len(names)}개 — `{'`, `'.join(names[:4])}` … |")

    free, ok_img = [], False
    for m in IMAGE_MODELS:
        st, body = call(m, {"contents": [{"parts": [{"text": "hi"}]}],
                            "generationConfig": {"responseModalities": ["TEXT"],
                                                 "maxOutputTokens": 1}}, key)
        if st == 200:
            ok_img, mark = True, "통과 — 결제가 붙은 열쇠입니다"
        elif st == 429:
            txt = json.dumps(body, ensure_ascii=False)
            if "FreeTier" in txt or "free_tier" in txt:
                free.append(m)
                mark = "**무료 등급으로 세고 있습니다 (한도 0)**"
            else:
                mark = "한도 초과 — 잠시 뒤 다시 눌러 보십시오"
        else:
            mark = f"막힘 (HTTP {st})"
        print(f"| 그림 ({m}) | {mark} |")

    print(f"| 영상 (Veo) | 따로 찔러보면 340원이 들어 안 합니다 — "
          f"{'그림이 통과했으니 같이 열려 있습니다' if ok_img else '그림이 막혔으니 같이 막혀 있습니다'} |")
    print()

    if ok_img:
        print("### 결과 — 쓸 수 있습니다")
        print()
        print("결제가 붙은 열쇠입니다. 그림과 영상 모두 만들 수 있습니다.")
        return 0

    print("### 결과 — 아직 못 씁니다")
    print()
    if free:
        print("구글이 이 열쇠를 **무료 등급**으로 세고 있습니다. 그림·영상 한도가 0입니다.")
        print()
        print("의심되는 곳은 셋입니다.")
        print()
        print("1. 금고에 든 열쇠가 결제 붙은 프로젝트 것이 아닙니다 "
              "(위 '끝 4자리' 를 AI 스튜디오 목록과 맞춰 보십시오)")
        print("2. **선불 잔액이 0원**입니다 — 결제 계정이 붙어 있어도 무료처럼 막힙니다")
        print("3. 그 프로젝트에서 결제가 아직 켜지지 않았습니다")
    elif not ok_text:
        print("글자도 막혔습니다. 열쇠가 틀렸거나 잔액이 없습니다.")
    else:
        print("글자는 되는데 그림이 막혔습니다. 잠시 뒤 다시 눌러 보십시오.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
