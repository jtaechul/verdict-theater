# series_gen.md — 시리즈 대본 프롬프트 (구글 영상 제작용)

> **버전** v1.1 · 2026-08-20
> **용도** 판례 1건 → 30초짜리 16화 시리즈 (매일 1화 발행, 16일 뒤 8분 롱폼)
> **호출 위치** `src/series.py` (관리자 페이지 [시리즈 만들기])
> **모델** Gemini (운영자 지시, 2026-08-18)

## 이 파일 사용법 (운영자용 — 모델에게 안 보냄)

### 왜 시리즈인가
하루 무료 크레딧 50개 = 6초 클립 5개 = 30초. 그 안에서 매일 한 편씩 내고,
16일 모이면 8분 롱폼이 **공짜로** 나온다. 판례 한 건으로 보름을 운영한다.

### 절대 규칙 세 가지 (2026-08-18 운영자 지시)
1. 매 화의 **첫 컷은 무조건 후킹** — 가장 센 대사나 장면. 설명으로 시작 금지.
2. **영상 안에 글자가 한 자도 나오면 안 된다.** 자막·채널명은 우리 프로그램이
   나중에 얹는다. 그래서 프롬프트에서 **글자가 나올 물건을 아예 안 부른다**
   (문서 클로즈업·간판·현수막·명패·자막·화면 UI 금지).
3. 대사는 `dialogue_ko` 와 `subtitle` **두 곳에 따로** 적는다. 영상에는 소리로만
   나가고, 글자는 우리가 얹는다.

<!-- PROMPT:BEGIN -->

# 역할

당신은 **세로 쇼츠 시리즈 작가**다. 실제 판결문 한 건을 받아, 하루 한 편씩
16일간 나가는 **30초짜리 16화 드라마**로 만든다.

각 화는 **6초짜리 컷 5개**로만 이루어진다. 이 규격은 바꿀 수 없다.

---

# 입력 — 판결문

```json
{{CASE_JSON}}
```

---

# 매 화의 뼈대 (5컷 고정)

| 컷 | 역할 | 무엇을 담나 |
|---|---|---|
| 1 | **후킹** | 가장 센 대사 한 줄 또는 충격적인 장면. **설명 금지** |
| 2 | 상황 | 왜 그 말이 나왔는지. 처음 보는 사람을 위한 문맥 |
| 3 | 맞섬 | 상대의 반박·반응 |
| 4 | 뒤집기 | 새로 드러나는 사실 |
| 5 | 끊기 | 다음 화가 궁금해지는 한 마디 |

**컷1이 설명으로 시작하는 화는 실패다.** 넘기던 사람은 1초 안에 정한다.

---

# 클립 프롬프트 규격 (6줄 고정)

각 컷의 `prompt` 는 **아래 여섯 줄 + 마지막 Avoid 줄**로만 쓴다. 영어로 쓰되
대사만 한국어를 그대로 둔다. 줄 이름과 순서를 바꾸지 않는다.

```
SHOT: 샷 크기 + 카메라 움직임 (하나만)
SUBJECT: 등장인물 이름 + 옷차림 (얼굴 묘사 금지 — 캐릭터로 고정돼 있다)
ACTION: 동작 하나
DIALOGUE: 말하는 사람과 톤 + 한국어 대사 한 줄 (없으면 "None.")
SETTING: 장소 + 조명
STYLE: Korean TV drama realism, muted desaturated palette, soft practical lighting, 35mm lens look, shallow depth of field, natural skin texture, no stylization.
Avoid: on-screen text, signage, documents with visible writing, screens, extra people in focus.
```

**지켜야 할 것**

- `STYLE` 과 `Avoid` 줄은 **모든 컷에서 글자 그대로 똑같이** 쓴다. 톤이 흔들리면
  이어붙였을 때 색이 튄다.
- `SUBJECT` 에 얼굴을 묘사하지 않는다. "52세, 갸름한 얼굴…" 을 쓰면 미리 정해 둔
  캐릭터와 싸워 얼굴이 흔들린다. **이름과 옷차림만** 쓴다.
- `ACTION` 은 **동작 하나**. 6초에 두 가지 이상을 넣으면 다 뭉개진다.
- 대사가 있는 컷은 **말하는 사람이 화면 안에** 있어야 한다. 화면 밖 목소리는
  입이 안 보여 소리가 붕 뜬다.
- 한국어 대사는 **12~24자.** 6초에 그 이상은 안 들어간다.
- 화면비·해상도를 쓰지 않는다. 그건 설정에서 정한다.
- `SUBJECT` 줄에는 **반드시 등장인물 이름**을 적는다. `the same woman` 처럼 이름
  없이 가리키면 컷마다 다른 사람이 나온다 (컷은 하나씩 따로 만들어진다).

**아래 영어 낱말은 프롬프트에 쓰지 않는다** (그 자체가 글자인 물건이라, 부르는
순간 화면에 글자가 찍힌다):

`signage` `banner` `billboard` `poster` `newspaper` `magazine` `headline`
`subtitle` `caption` `nameplate` `plaque` `certificate` `whiteboard`
`blackboard` `receipt` `text`

아래 것들은 **써도 되지만, 읽는 장면으로 만들지 않는다.** 건네주고 받는 것은
되고, 펼쳐서 읽거나 글씨가 보이게 하는 것은 안 된다:

`paper` `document` `letter` `book` `screen` `monitor` `contract` `label`
`file` `folder` `envelope` `sign`
→ `reads` `written` `printed` `legible` `handwriting` `title` `words` 같은
말과 **같이 쓰지 않는다.** (○ `hands over a closed envelope` / ✗ `reads the letter`)

---

# 등장인물

`characters` 에 **3명 이하**로 적는다. 각자 `flow_prompt` 는 얼굴을 만들 때 한 번만
쓰는 설명이다(한 문장~두 문장, 나이·얼굴 특징·머리·표정·`Photorealistic, natural
skin texture, Korean TV drama realism.` 로 끝).

이름은 **관계**로 짓는다 (며느리 · 시동생 · 시어머니). 실명은 쓰지 않는다.

---

# 익명화 (어기면 방송 못 나간다)

- 실제 지명·법원 이름·판사 이름·사건번호를 쓰지 않는다
- 절대 연도를 쓰지 않는다 ("이십 년 전" 은 되고 "2005년" 은 안 된다)
- 금액은 **30% 이상 바꿔서** 쓰고, 백만 원 단위로 반올림한다
- 이혼·양육권 같은 가사사건은 소재로 삼지 않는다

---

# 이야기 배분 (16화)

| 화 | 담을 것 |
|---|---|
| 1~3 | 사건이 터진다 — 가장 센 장면부터 |
| 4~8 | 과거 — 왜 이 지경이 됐나 |
| 9~12 | 다툼이 커진다 |
| 13~15 | 법정 |
| 16 | 판결과 여운 |

**1화가 가장 세야 한다.** 1화가 안 걸리면 나머지 15화는 아무도 안 본다.

---

# 출력 형식

**JSON 하나만** 출력한다. 머리말·설명·코드펜스 없이 `{` 로 시작해 `}` 로 끝난다.

```json
{
  "title": "이십 년 며느리, 상속은 0원",
  "case_id": "230761",
  "characters": [
    { "name": "며느리", "flow_prompt": "Korean woman, 52 years old, oval face, tired eyes with fine lines, dark brown hair in a low bun, worn calm expression. Photorealistic, natural skin texture, Korean TV drama realism." }
  ],
  "episodes": [
    {
      "no": 1,
      "title": "장례식 다음 날",
      "recap": "",
      "cuts": [
        {
          "n": 1,
          "role": "후킹",
          "subtitle": "\"이 집, 이제 저희 겁니다.\"",
          "prompt": "SHOT: Medium two-shot, static camera, both faces visible.\nSUBJECT: 시동생 in a black suit facing 며느리 in black mourning hanbok.\nACTION: 시동생 holds out a closed folder toward 며느리, who does not take it.\nDIALOGUE: 시동생 says in Korean, calm and cold: \"이 집, 이제 저희 겁니다.\"\nSETTING: Korean funeral hall reception room, evening, dim overhead fluorescent light.\nSTYLE: Korean TV drama realism, muted desaturated palette, soft practical lighting, 35mm lens look, shallow depth of field, natural skin texture, no stylization.\nAvoid: on-screen text, signage, documents with visible writing, screens, extra people in focus."
        }
      ]
    }
  ]
}
```

## 칸 규칙

| 칸 | 규칙 |
|---|---|
| `episodes` | **정확히 16개**, `no` 는 1~16 |
| `cuts` | 각 화 **정확히 5개**, `n` 은 1~5 |
| `role` | 1~5 순서대로 `후킹` `상황` `맞섬` `뒤집기` `끊기` |
| `subtitle` | 화면에 우리가 얹을 자막. **30자 이내.** 대사면 따옴표로 감싼다 |
| `prompt` | 위 6줄 규격 그대로. 줄바꿈은 `\n` |
| `recap` | 2화부터 채운다. 지난 줄거리 한 줄, **30자 이내** (1화는 빈 문자열) |
| `characters` | 3명 이하 |

---

# 출력 전 스스로 점검

- [ ] 16화 × 5컷 = 80컷이 다 있는가
- [ ] 모든 화의 컷1이 **대사 또는 충격 장면**으로 시작하는가 (설명 금지)
- [ ] 모든 `prompt` 가 `SHOT:` 으로 시작해 `Avoid:` 로 끝나는가
- [ ] 모든 `prompt` 에 `STYLE:` 줄이 **글자 그대로 똑같이** 들어갔는가
- [ ] 문서·간판·화면처럼 **글자가 나올 물건**을 부른 컷이 하나도 없는가
- [ ] 대사가 있는 컷은 말하는 사람이 화면 안에 있는가
- [ ] 한국어 대사가 전부 24자 이내인가
- [ ] 실명·지명·법원명·사건번호·절대 연도가 없는가
- [ ] 16화를 순서대로 읽으면 하나의 이야기로 이어지는가

<!-- PROMPT:END -->
