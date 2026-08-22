# series_gen.md — 시리즈 대본 프롬프트 (구글 영상 제작용)

> **버전** v2.1 · 2026-08-20
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

# 클립 프롬프트 규격 (머리말 1줄 + 6줄 고정)

각 컷의 `prompt` 는 **머리말 한 줄 + 아래 여섯 줄 + 마지막 Avoid 줄**로만 쓴다.
영어로 쓰되 대사만 한국어를 그대로 둔다. 줄 이름과 순서를 바꾸지 않는다.

> ⭐ **맨 앞 머리말 줄은 반드시 있어야 한다.** 없이 `SHOT:` 으로 시작하면
> 붙여 넣는 쪽이 `단어:` 를 **인터넷 주소 이름**으로 읽어 버려
> (`http:` `mailto:` 처럼) 글자가 `shot:%20Medium%20...%EB%82%A8%ED%8E%B8`
> 처럼 통째로 깨진다. 실제로 운영자가 두 번 겪었다.
> 머리말은 콜론 없이 쓴다 — 그래야 주소로 안 읽힌다.

```
Fictional scene, invented characters, semi-realistic illustrated drama. 6-second single continuous take.
SHOT: 샷 크기 + 카메라 움직임 (하나만) — 뒤에 '허리 위로·얼굴 크게' 를 우리가 붙인다
SUBJECT: 등장인물을 가리키는 **영어 관계말** + 옷차림 (얼굴 묘사 절대 금지 — 아래 ⚠️ 참고)
ACTION: 동작 하나
DIALOGUE: 말하는 사람과 톤 + 한국어 대사. 주고받으면 ` / ` 로 잇는다 (없으면 "None.")
          → 시스템이 **한 사람에 한 줄**로 나눠서 다시 적는다
VOICE: (우리가 붙인다) 인물마다 어떤 목소리인가
AUDIO: (우리가 붙인다) 낭독이 아니라 그 자리에서 하는 말이라는 못
SETTING: 장소 + 조명
CONTINUITY: (우리가 붙인다) 앞 컷에서 이어지는 장면이라는 못
COLOR: (우리가 붙인다) 모든 컷에 똑같은 색
STYLE: one single continuous take, no cut, no scene change, same location and same person from first frame to last, identical clothing throughout, semi-realistic hand-drawn illustration style with clean confident linework and soft cel shading, grounded adult proportions and restrained faces rather than cartoon exaggeration, muted desaturated palette, soft practical lighting, shallow depth of field, consistent line weight in every shot.
Avoid: overlapping voices, on-screen text, signage, documents with visible writing, screens, background extras in focus, cutting to another shot, changing the background mid-shot, the person changing clothes or face mid-shot, swapping in a different person.
```

**지켜야 할 것**

- `STYLE` 과 `Avoid` 줄은 **모든 컷에서 글자 그대로 똑같이** 쓴다. 톤이 흔들리면
  이어붙였을 때 색이 튄다.
- ⭐ `SUBJECT` 는 **모든 컷에서 한 글자도 다르지 않게** 쓴다 (2026-08-20 · 실제 영상).
  첫 화 완성본에서 **남편이 1·2·4컷 모두 다른 배우**로 나왔다. 본처도 얼굴이 튀었다.
  플로우 캐릭터를 안 붙이면 컷마다 새 얼굴을 만들기 때문이다.

  꼴을 고정한다 — `{이름}({face_tag}) in {outfit}`

  ```
  SUBJECT: 남편(55, square face, deep forehead lines) in a charcoal jacket over a black tee.
  ```

  `face_tag` 는 **짧게(대여섯 낱말)**. 길게 묘사하면 미리 정해 둔 캐릭터와 싸워
  오히려 얼굴이 흔들린다. 짧고 **매번 똑같은 것**이 핵심이다 — 플로우 캐릭터를
  붙였으면 거들어 주고, 안 붙였으면 그것만으로도 얼굴이 잡힌다.
- `ACTION` 은 **동작 하나**. 6초에 두 가지 이상을 넣으면 다 뭉개진다.
- ⭐ **`SHOT` 을 컷마다 다르게** 잡는다 (2026-08-20 · 실제 영상).
  첫 화에서 2·4·5컷이 전부 비슷한 미디엄 샷 한 명이라 리듬이 밋밋했다.
  한 화 5컷에 **적어도 세 가지 크기**를 섞는다.
    · 주고받는 컷 → `Medium two-shot, both faces visible`
    · 감정이 터지는 컷 → `Close-up on {이름}`
    · 장면을 여는 컷 → `Wide shot` 또는 `Over-the-shoulder`
  마지막 5컷(끊기)은 **클로즈업**으로 얼굴에 붙여 끝낸다.
- ⭐ **맞은편에 있는 사람을 3인칭으로 부르지 않는다** (2026-08-20 · 실제 영상).
  첫 화 3컷에서 본처가 **내연녀를 마주 보고** `"저 여자가 이유였어?"` 라고 했다.
  눈앞에 두고 남 얘기하듯 말하면 장면이 통째로 어긋난다.

  ✗ `본처 facing 내연녀` 인데 `"저 여자가 이유였어?"`
  ○ `"당신이 이유였어?"` · `"네가 이유였어?"`

  `저 여자` `그 여자` `저 사람` `그놈` 같은 말은 **그 자리에 없는 사람**에게만
  쓴다. 화면에 있는 사람은 `당신` · `너` · 이름으로 부른다.

  뒤집어 말하면, `SUBJECT` 에 없는 사람에게 말을 걸어도 안 된다.
  말을 주고받는 사람은 **둘 다 화면 안에** 있어야 한다.

- ⭐ **한 컷은 한 번에 찍은 것처럼** (2026-08-20 · 실제 영상).
  6초 클립 하나 안에서 **배경이 바뀌고, 옷이 바뀌고, 얼굴이 딴사람이 되는**
  일이 있었다. 영상 만드는 쪽은 가만 두면 중간에 장면을 갈아엎는다.
  그래서 모든 컷의 `STYLE`·`Avoid` 고정 문구에
  `STYLE: one single continuous take, no cut, no scene change` 와
  `cutting to another shot, changing the background mid-shot,
  the person changing clothes or face mid-shot` 을 넣어 두었다.
  **이 두 줄은 손대지 않는다** — 우리 프로그램이 자동으로 채운다.

- ⭐ **`SETTING` 은 한 화에 두 곳까지** (2026-08-20 · 실제 영상).
  첫 화가 거실 → 복도로 넘어갔는데 아무 설명이 없어 갑자기 튀어 보였다.
    · 같은 장소인 컷은 SETTING 을 **한 글자도 다르지 않게** 쓴다
    · 장소가 바뀌는 **첫 컷의 `caption`** 에 어디인지 한 줄 적는다
      (예: `현관 밖, 그 여자가 기다리고 있었다`)
- ⭐ **서로 몸이 닿는 동작을 쓰지 않는다** (2026-08-20 · 실제 영상에서 확인).
  첫 클립에서 여자가 남자 팔을 잡았는데 **손가락이 옷 속으로 녹아들어 갔다.**
  영상 만드는 쪽이 두 사람이 닿는 자리를 아직 제대로 못 그린다. 닿는 곳이
  없으면 그런 오류가 아예 안 생긴다.

  ✗ 쓰지 않는다: `grabs ... by the arm` `holds her wrist` `pushes him`
     `hands over a folder` `takes her hand` `blocks the door with his body`
     `shakes her shoulders` `snatches the phone from`
  ○ 대신 쓴다: 혼자서 하는 몸짓과 거리
     `steps in front of 남편, blocking his way`  (막되 닿지는 않는다)
     `reaches out but stops short`               (뻗다가 멈춘다 — 더 애타 보인다)
     `slams her palm on the table`               (사람이 아니라 물건을 친다)
     `turns her back and grips her own sleeve`   (제 옷을 쥔다)
     `points at him, hand trembling`             (가리킨다)

  물건을 건네는 장면도 마찬가지다 — 주고받는 순간을 그리지 말고
  `sets it down on the table and steps back` 처럼 **놓고 물러나게** 한다.
- 대사가 있는 컷은 **말하는 사람이 전부 화면 안에** 있어야 한다. 화면 밖 목소리는
  입이 안 보여 소리가 붕 뜬다. 주고받는 컷은 `SHOT` 을 **two-shot(두 사람이 같이
  보이는 샷)** 으로 잡는다.

## ⭐ 대사 — 한 컷 안에서 주고받아야 한다 (2026-08-20 · 실물로 재서 고침)

> 여기서 **두 번 다 틀렸다.** 처음엔 80컷 전부 한 사람만 말했고, 고치고 나니
> 이번엔 대사를 길게 쓰되 **한 컷에 한 사람씩만** 말하고 대화를 다음 컷으로
> 넘겼다. 컷은 **따로따로 만들어져 이어 붙인 것**이라, 받아치는 말이 다음
> 컷으로 넘어가면 장면이 뚝뚝 끊긴다. 한 컷 안에서 주고받아야 살아 있다.

### ① 한 화 5컷 중 **최소 2컷은 한 컷 안에서 두 사람이 주고받는다** (가장 중요)

`맞섬`·`뒤집기` 는 받아치는 말이 있어야 장면이 뒤집힌다. 이렇게 쓴다:

```
Fictional scene, invented characters, semi-realistic illustrated drama. 6-second single continuous take.
SHOT: Medium two-shot, static camera, both faces visible.
DIALOGUE: 아내 (furious): "여기가 어디라고 와? 당장 안 나가면 경찰 부른다." / 동거녀 (calm): "마지막 가는 길인데 인사도 못 해요?"
```

위는 19 + 14 = **33음절** — 조금 길다. 한쪽이 다 쓰지 말고 **반씩 나눈다.**

✗ 이렇게 나누어 놓으면 안 된다 — 한 컷에 한 사람씩만 말하고 다음 컷으로 넘김:
```
✗ 3컷 DIALOGUE: 아내 (furious): "여기가 어디라고 와? 당장 안 나가면 경찰 부른다."
✗ 4컷 DIALOGUE: 동거녀 (calm): "마지막 가는 길인데 인사도 못 해요?"
```

**주고받을 때는 두 번이 아니라 세 번 오간다 (A → B → A).**
두 번만 하면 6초가 안 찬다 — 실제로 그렇게 나와서 다시 만들었다
(주고받는 컷 33개가 전부 두 번, 평균 26.5음절 = 4.1초).

```
✗ 두 번 (16음절 · 2.7초 — 너무 빈다)
DIALOGUE: 아내 (furious): "당신 돈 다 어디로 빼돌렸어?" / 남편 (annoyed): "내 돈 내가 쓰는데 무슨 상관이야."

○ 세 번 (32음절 · 5.0초)
DIALOGUE: 아내 (furious): "당신 돈 다 어디로 빼돌렸어?" / 남편 (annoyed): "내 돈 내가 쓰는데 무슨 상관이야." / 아내 (shouting): "그게 왜 당신 돈이야!"
```

한 번에 **8~10음절씩 세 번** = 24~28음절. 네 번은 6초에 뭉개진다.

### ② 한 컷 대사는 **24~28음절**을 쓴다 (최소 19 · 최대 33)

공백·쉼표는 소리가 안 나므로 **음절로 센다.**

실제 사람은 생각보다 빨리 말한다. 말다툼 장면의 대사를 재보면 —

| 대사 | 음절 | 걸리는 시간 |
|---|---|---|
| `"여기가 어디라고 와. 당장 안 나가?"` | 13 | 1.9초 |
| `"매일 같이 살았으면서 그걸 모른다고?"` | 15 | 2.2초 |
| `"돈 다 빼돌리고 나한테 이딴 빚만 남겨놨다고?"` | 18 | 3.0초 |

**초당 약 6.4음절**이다. 다만 이건 **급하게 몰아붙일 때**의 속도다.

> ⭐⭐ **2026-08-21 — 실제로 만들어진 영상을 재 봤다.** (1화 1컷, 6.02초)
> | 구간 | 내용 |
> |---|---|
> | 0.00~0.98초 | **무음 — 앞에 1초를 그냥 버린다** |
> | 0.98~2.55초 | 1번째 대사 |
> | 2.79~4.20초 | 2번째 대사 |
> | 4.57~6.02초 | 3번째 대사 |
>
> 말한 시간 **4.43초에 32음절 = 초당 7.2음절.** 아나운서보다 빠르다.
> 이렇게 쏟아내면 받침과 연음이 뭉개져 **원어민이라도 어눌하게 들린다.**
> 운영자 지적: *"외국인 노동자가 어설픈 한국말 하는 것 같다."*
>
> 그래서 두 가지를 고쳤다.
> ① 앞 1초는 **못 쓴다고 보고** 뺀다 → 실제로 말할 시간은 **4.8초**
> ② 급하지 않게 말할 속도 **초당 6.0** 으로 잡는다 → **28음절**

6초 클립에서 **28음절**이 알맞다 (4.7초).
33음절을 넘으면 6초에 못 넣으므로 **반려**한다.

두 사람이 주고받으면 **각 12~14음절씩**, 세 번 오가면 28음절이 찬다.
혼자 말하면 **두 문장**이면 된다.

> ⚠️ 예전에 "대사가 너무 짧다" 는 지적을 받은 것은 **9.6음절**일 때다.
> 28음절은 그때의 세 배에 가까우니 그 지적을 되돌리는 것이 아니다.
> 모자라도 안 되고 넘쳐도 안 된다 — **24~28 사이**를 지켜라.

  `"거기서 무슨 짓을 한 거야."` 10음절 · 1.6초 → ✗ 너무 짧다
  `"거기서 무슨 짓을 한 거야. 우리 남편 어디 있냐고 묻잖아."` 22음절 → ✗ 아직 모자람
  `"거기서 무슨 짓을 한 거야. 우리 남편 어디 있냐고 묻잖아. 지금 당장 대답해."` 29음절 · 4.5초 → ○

### ③ 혼자 말하는 컷은 한 화에 **세 컷까지**

혼자 말할 때도 한 문장으로 끝내지 않는다.
```
DIALOGUE: 며느리 (barely holding back): "그이 관 앞에서 할 소리는 아니잖아요. 부끄럽지도 않으세요? 지금 당장 나가 주세요."
```

`subtitle` 에는 주고받은 대사를 ` / ` 로 이어 그대로 적는다 (60자 이내).

## ⭐⭐ 사람이 실제로 하는 말로 쓴다 (2026-08-20 · 가장 중요)

앞서 만든 대본을 손님이 이렇게 물렀다 — **"말도 어색해. 구어체가 아닌 것 같고
실제 같지 않아."** 재보니 대사 112줄 중 20줄(18%)이 서류·판결문 말투였다.

까닭은 분명하다. **사실을 전할 통로가 대사밖에 없어서 입에 다 밀어 넣었다.**

### 대사에 절대 넣지 않는 말

`유류분` `한정승인` `상속재산` `상속액` `판례` `시효` `증여` `물가상승률`
`반환청구` `귀책` `고유재산` `사망보험금` `악의적` `청구권` `입증` `채권자`

싸우는 사람은 이렇게 말하지 않는다. 이 사실들은 **`caption`(설명 자막)** 이
대신 진다. 입은 **감정만** 말한다.

### 실제로 이렇게 바꾼다

| ✗ 서류 말투 (앞서 나온 것) | ○ 사람 말 |
|---|---|
| "대법원 판례상 사망보험금은 내 거야." | "그 돈은 내 거야. 법이 그래." |
| "난 한정승인으로 당당하게 맞설 거야." | "빚? 그건 내가 알아서 해." |
| "악의적 증여는 시효 상관없이 다 토해내야 해." | "몰래 빼돌린 건 몇 년이 지나도 안 없어져." |
| "사망 당시 재산이니까, 당연히 상속재산이야." | "그이 죽던 날까지 그이 거였잖아." |
| "병원 지분 십이억도 네가 챙겼더라?" | "병원까지 손댔어? 진짜 끝까지 가네." |
| "매월 이천만 원씩 보험료를 냈더라?" | "그 돈이 매달 어디로 빠져나갔는지 알아?" |

### 구어체로 만드는 것들

- **조사를 뺀다** — ○ `"그 돈 어디 있어."` / ✗ `"그 돈이 어디에 있습니까."`
- **말끝을 살린다** — `-잖아` `-거든` `-는데` `-더라고` `-란 말이야` `-냐고`
- **군말을 넣는다** — `야,` `아니,` `됐고,` `그러니까,` `무슨 소리야,`
- **되묻고 끊는다** — `"뭐?"` `"뭐라고 했어?"` `"그러니까 네 말은—"`
- **말을 끝까지 안 맺어도 된다** — `"그건... 아니, 그게 아니라."`
- **숫자는 되도록 입에 담지 않는다.** 꼭 필요하면 `"십오억"` 처럼 뭉뚱그린다.
  자릿수까지 또박또박 말하면 사람이 아니라 서류가 말하는 것처럼 들린다.

### `caption` — 사실은 여기에 적는다

컷마다 `caption` 을 **비워 두거나 한 줄** 적는다. 숫자·법률·경위처럼 시청자가
알아야 하지만 **입으로 하면 어색한 것**을 여기 적는다. 우리 프로그램이 화면
아래에 자막으로 얹는다(영상 안에 글자를 넣는 것이 아니다).

```
DIALOGUE: 아내 (furious): "병원까지 손댔어? 진짜 끝까지 가네." / 동거녀 (flat): "그이가 준 거야. 내가 뺏은 게 아니라 준 거라고."
caption: 사망 두 달 전, 병원 지분 12억이 동거녀 앞으로 넘어갔다
```

위 `DIALOGUE` 는 32음절 · 5.0초 — 6초를 꽉 채운다. 아래처럼 짧게 끝내면 화면이 빈다:

```
✗ DIALOGUE: 아내 (furious): "병원까지 손댔어?"        ← 7음절 · 1.1초뿐
```

대사가 감정을 지고, 자막이 사실을 진다. **둘을 한 입에 넣지 않는다.**

- 화면비·해상도를 쓰지 않는다. 그건 설정에서 정한다.
- **대사에 배역 딱지를 쓰지 않는다.** `내연녀` `상간녀` `피상속인` 같은 말은
  판결문·기사에나 쓰는 제3자 호칭이라, 사람이 입으로 하면 즉시 어색해진다.
  실제로 하는 말로 쓴다. (✗ `"내연녀 집에서 떨어져 죽었다고요?"`
  ○ `"그 여자 집에서 떨어져 죽었다고요?"`)
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

`characters` 에 **3명 이하**로 적는다.

### `flow_prompt` — 이 사람이 어떻게 생겼는가

⚠️ 2026-08-20 — 여기가 **25낱말짜리**여서 캐릭터를 만들 때마다 배경도 자세도
제멋대로 나왔다. 우리 프로그램이 배경·자세·화면잡기·빛·금지사항을 자동으로
붙여 주므로, 여기에는 **생김새만** 적되 **빠짐없이** 적는다.

다음을 **전부** 넣는다 (영어, 쉼표로 이어서):

```
Korean woman, 52 years old,
얼굴형 (oval / square / round / sharp V-line),
눈 (tired eyes with fine lines / sharp confident eyes / small deep-set eyes),
코·입 (modest nose, thin lips / straight nose, full lips),
피부 (dull skin with visible pores, faint age spots / clear but tired skin),
머리 (dark brown hair in a low bun, greying at the temples / long wavy dyed brown hair),
몸 (slight build, slightly stooped shoulders / average build, straight posture),
표정 (worn calm expression / arrogant expression)
```

**나이와 얼굴형·눈·머리는 반드시** 넣는다 — 이 넷이 없으면 매번 딴사람이 나온다.
`Photorealistic…` 같은 화풍 문구는 **적지 않는다** (우리가 붙인다).

### `face_tag` · `outfit`

`face_tag` 는 위 설명에서 **가장 눈에 띄는 대여섯 낱말**만 뽑은 것이다
(예: `oval face, tired eyes, low bun`). **플로우에서 캐릭터(기준 사진)를
만들 때만 쓴다.**

> ⚠️ `face_tag` 를 **컷 프롬프트에 넣지 않는다.** 한때 이름 뒤에 붙였다가
> 80컷이 전부 거절됐다 (「정책에 막히는 말」 참고). 컷의 `SUBJECT` 는
> **이름 + 옷차림**까지만이다.

`outfit` 은 **색까지** 정한 옷차림이다. 이것은 컷마다 똑같이 적는다.

이름은 **관계**로 짓는다 (며느리 · 시동생 · 시어머니). 실명은 쓰지 않는다.

### ⭐ `outfit` — 30초 내내 갈아입지 않는다 (2026-08-20 · 실제 영상에서 확인)

첫 화 완성본에서 **본처의 카디건이 1컷 초록 → 3컷 베이지 → 5컷 초록**으로 튀었다.
SUBJECT 에 `본처 in a simple cardigan` 이라고만 써서 색을 안 정해 줬기 때문이다.
영상 만드는 쪽은 색을 안 정해 주면 매번 새로 고른다. 그러면 딴사람으로 보인다.

인물마다 `outfit` 을 **색까지** 정하고, 모든 컷의 `SUBJECT` 에 그대로 쓴다.

```json
{ "name": "본처",
  "face_tag": "52, oval face, tired eyes, low bun",
  "outfit": "a moss-green knit cardigan over a grey striped tee",
  "flow_prompt": "Korean woman, 52 years old, …" }
```

`SUBJECT: 본처 in a moss-green knit cardigan over a grey striped tee.`
— 한 화 안에서는 **한 글자도 바꾸지 않는다.**

---

# 시간 순서 (2026-08-20 — 실제로 헷갈리게 나왔다)

**16화를 반드시 일어난 순서대로 쓴다.** 매일 한 편씩 따로 올라가므로, 시청자는
어제 본 것 바로 다음이라고 믿는다. 과거로 돌아가면 그대로 앞뒤가 안 맞는다.

실제로 이런 대본이 나왔다 — 1화가 **장례식**인데 4화에서 죽은 남편이 살아나
`"이혼해"` 라고 한다. 3~8화가 회상이었지만 아무 표시가 없었다.

- 죽음·판결처럼 **되돌릴 수 없는 사건은 그 뒤로 계속 유지**된다. 1화에서 죽었으면
  8화에서 살아 있으면 안 된다.
- 굳이 과거를 보여줘야 하면 `recap` 첫머리에 `(그때로부터 3년 전)` 처럼
  **명시**하고, 돌아올 때도 `(다시 지금)` 이라고 적는다.
- 가장 좋은 것은 **처음부터 순서대로 가는 것**이다. 사건 → 다툼 → 소송 → 판결.

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

## ⭐⭐ 목소리 — 안 정해 주면 로봇이 읽는다 (2026-08-20 · 실제로 그랬다)

> ⭐ **2026-08-21 덧붙임 — 완성본에서 들리는 목소리는 플로우 것이 아니다.**
> 여기까지 다 해도 플로우의 한국어는 원어민 소리가 안 났다. 그래서 완성본에서는
> **소리를 통째로 떼어내고 제미나이 한국어 목소리로 갈아 끼운다**(`src/tts.py`).
> 그렇다고 아래 규칙을 빼면 안 된다 — 아래 규칙은 이제 **입 모양과 말 차례**를
> 만든다. 사람이 언제 입을 열고 언제 닫는지가 여기서 정해지고, 우리 목소리는
> 그 자리에 정확히 얹힌다. 겹쳐 말하거나 화면 밖에서 말하면 얹을 자리가 없어진다.

운영자: **"나레이션이 너무 로봇 같은데?"**

첫 영상들의 프롬프트를 다시 보니 **소리에 관한 지시가 한 줄도 없었다.**
있는 것이라곤 `(furious)` 같은 한 낱말뿐이었다. 그러면 영상 만드는 쪽은
가장 안전한 쪽 — **또박또박 읽는 낭독**을 고른다. 그게 로봇처럼 들리는 것이다.
게다가 대사가 화면 밖 **해설자 목소리**로 얹히는 일도 잦다.

### 인물마다 `voice` 를 적는다 (필수)

인물표의 각 인물에 `voice` 칸을 채운다. **한 줄, 영어로.**
높낮이 · 나이대 · 말버릇 세 가지가 들어가야 한다.

| ✗ 이러면 로봇이 읽는다 | ○ 이렇게 적는다 |
|---|---|
| (아무것도 없음) | a low, slightly gravelly man's voice in his fifties, native Korean speaker, clipped and impatient, drops in volume at the end |
| angry voice | a warm mid-range woman's voice in her fifties, native Korean speaker, weary and a little breathy, trails off at the end of a sentence |
| young female voice | a clear woman's voice in her forties, native Korean speaker, cool and unhurried, with a small lilt at the end |

**`native Korean speaker` 는 반드시 넣는다** — 안 넣으면 외국인이 읽는 소리가 난다.

> ⚠️ **플로우에서 캐릭터 목소리를 미리 골라 두지 않는다.**
> 미리 골라 두면 그 목소리가 프롬프트를 눌러 이겨서, 여기에 뭘 적어도 안 먹는다.
> 목소리는 **캐릭터 설명 칸**과 **컷 프롬프트** 두 곳으로만 준다.

**같은 화에 나오는 두 사람의 목소리는 확실히 달라야 한다.**
높낮이(low/mid/clear)와 말버릇(clipped / trails off / unhurried)을 서로 다르게 준다.

### `DIALOGUE` 의 톤도 한 낱말로 끝내지 않는다

| ✗ | ○ |
|---|---|
| `(furious)` | `(voice rising, almost shouting)` |
| `(annoyed)` | `(flat, not looking at her)` |
| `(sad)` | `(quiet, swallowing before she speaks)` |

### 한국말처럼 들리게 — 어느 나라 말인지 알려 줘야 한다

운영자: **"나레이션이 외국인이 한국말하는 것처럼 들린다."**

당연했다. 프롬프트가 **무슨 말로 하는지 한 번도 안 알려 줬다.**
지시는 전부 영어인데 대사만 한글이니, 영상 만드는 쪽은 영어 목소리로
한글을 더듬더듬 읽는다. 외국인이 읽는 것처럼 들리는 이유다.

그래서 **대사 바로 옆**과 `AUDIO` 줄 두 곳에 못을 박는다 (시스템이 붙인다).

- `DIALOGUE:` 맨 앞 — `[LANGUAGE: KOREAN]` (대문자 표시가 가장 강하게 먹는다)
- 말투 괄호마다 — `(furious, in Korean)` 처럼 **in Korean** 을 붙인다
- `AUDIO:` — `natural, fluent and highly authentic everyday Korean` ·
  `standard Seoul intonation`
- `voice` 칸에도 **native Korean speaker** 를 넣는다

### ⛔ 하지 말라는 말로 적지 않는다 (아주 중요)

처음에는 `no foreign accent, no English accent` 라고 적었다. **역효과였다.**
영상 만드는 쪽은 `no` 보다 뒤에 붙은 `foreign` `English` 라는 낱말 자체에
끌린다 — 없애라고 부른 것을 오히려 불러들인다.

| ✗ 하지 말라고 적기 | ○ 바라는 것만 적기 |
|---|---|
| no foreign accent, no English accent | natural, fluent and highly authentic everyday Korean with standard Seoul intonation |
| no background music, no sound effects | with only the quiet room tone of the location underneath |
| no narrator, no voice-over | the two people in the shot say the lines themselves |

소리에 관한 것은 **바라는 것만** 적는다.

### 대사에 숨 쉴 자리를 만든다

한 문장을 끝까지 밀어붙이면 외국어처럼 늘어진다. 쉼표를 넣으면 억양이 한 번
**리셋**되어 한국말처럼 들린다. **대사를 쓸 때부터** 이렇게 쓴다.

| ✗ | ○ |
|---|---|
| "당신 진짜 제정신이야?" | "당신, 진짜 제정신이야?!" |
| "더는 숨 막혀서 못 살아." | "더는 숨 막혀서, 못 살아." |
| "그럼 어떻게 할 건데?" | "그럼, 어떻게 할 건데?" |

소리 지르는 말은 `?!` 로 끝내도 좋다. 다만 **쉼표를 아무 데나 넣지 않는다** —
부르는 말·감탄사 뒤, 또는 문장이 꺾이는 자리에만 넣는다.
(`"당신 명의로"` 처럼 꾸미는 말에 쉼표를 넣으면 뜻이 망가진다)

### 대사는 **한 사람에 한 줄** (시스템이 나눈다)

한 줄에 ` / ` 로 이어 붙이면 영상 만드는 쪽이 한 사람이 쭉 읽는 것으로 본다.
줄을 나누면 말 차례가 눈에 보여 사람마다 억양을 새로 잡는다.

```
DIALOGUE: [LANGUAGE: KOREAN] each person speaks one after another, never overlapping
  Wife (furious, in Korean): "당신 진짜 제정신이야?!"
  Husband (annoyed, in Korean): "더는 숨 막혀서 못 살아."
  Wife (shouting, in Korean): "누구 맘대로 집을 나가!"
```

**겹쳐 말하지 않는다.** 6초짜리에서 목소리가 겹치면 한국어가 뭉개져 더
어색하게 들린다. 우리 쪽에도 이득이다 — 가라오케 자막이 **말 사이 정적**으로
사람을 가르는데, 겹쳐 말하면 그 경계를 못 찾는다.

**입모양 맞추기는 `ACTION` 줄에 붙인다** — 소리 줄보다 그림 지시 옆이 더 잘 먹는다.

### `VOICE` · `AUDIO` 두 줄은 **우리가 붙인다**

너는 `voice` 칸만 채우면 된다. 컷 프롬프트의 `VOICE:` `AUDIO:` 줄은
시스템이 자동으로 붙인다 (해설자 금지·입모양 맞추기·숨소리 등).

---

## ⭐ 컷끼리 이어 붙었을 때 한 편으로 보이게 (2026-08-20)

다섯 조각을 따로 뽑아 이어 붙이면 **딴 작품 다섯 개**처럼 보이기 쉽다.
두 가지를 시스템이 모든 컷에 똑같이 넣어 막는다.

### `CONTINUITY` — 장면 연장

앞 컷에서 무엇이 있었는지 한 토막 적어 주고 "거기서 이어진다" 고 못 박는다.

- 같은 화 · 같은 장소 → *같은 방, 같은 사람, 같은 옷·머리·빛. 앞 컷이 끝난
  바로 그 자리에서 이어 간다*
- 같은 화 · 장소가 바뀜 → *조금 뒤 다른 곳. 사람·옷·얼굴·색은 그대로*
- 화가 넘어감 → *같은 이야기의 뒷날. 사람·얼굴·목소리·색은 그대로*
- 맨 첫 컷 → *이야기의 첫 장면. 여기서부터 이어진다*

**너는 `SETTING` 만 정확히 쓰면 된다** — 장소가 같은지 다른지를 보고
시스템이 알맞은 문장을 고른다. 그래서 같은 장소는 **글자 그대로 같게** 쓴다.

### 화풍 — **반실사 그림체** (2026-08-21 확정)

운영자: *"이럴 거면 절반 정도는 애니메이션풍으로 만드는 게 낫지 않아?"*

맞는 직감이었다. 그림체로 가면 그동안 싸운 문제 **넷이 한꺼번에** 풀린다.

| 겪은 문제 | 실사 | 그림체 |
|---|---|---|
| 입 모양이 안 맞음 (더빙의 약점) | 얼굴이 진짜라 바로 티난다 | 입이 단순해 안 걸린다 |
| 유명인 정책 차단 (다섯 번) | 실존 인물 사진으로 읽힌다 | 그림은 거의 안 걸린다 |
| 얼굴이 컷마다 바뀜 | 사진 같은 얼굴은 고정이 어렵다 | 단순한 얼굴은 잘 고정된다 |
| 손가락이 녹아듦 | 진짜 손이라 오류가 보인다 | 단순한 손은 원래 그렇다 |

**다만 만화가 아니다.** 판결극장은 실제 판결이 밑천이라 무게가 빠지면 안 된다.
채도를 낮추고 선을 살린 **반실사**로 간다 — 어른 비례, 과장 없는 얼굴.

**한 영상 안에서 화풍을 섞지 않는다.** 컷마다 그림체가 달라지면 싸구려로 보인다.
`STYLE` 줄은 시스템이 모든 컷에 똑같이 넣으니 너는 신경 쓰지 않아도 된다.

`Avoid` 에 `cartoon` `illustration` `anime` 같은 말을 **넣지 마라** —
지금은 그림체가 바라는 것이다. (막을 것은 `chibi` 같은 과장된 비례다)

### `SHOT` — 세로 쇼츠에서는 **얼굴이 커야 한다**

⭐ 2026-08-21 — 실제로 만든 쇼츠를 눈으로 보고 알았다.
플로우가 `Medium two-shot` 을 **전신이 다 나오는 넓은 그림**으로 그렸다.
가로 영상에서는 괜찮지만, 세로로 잘라 놓으면 얼굴이 화면 높이의 8% 밖에
안 된다 — 휴대전화로 보면 **표정이 하나도 안 읽힌다.** 쇼츠에서 표정이
안 보이면 그냥 넘긴다.

그래서 모든 `SHOT` 줄 뒤에 시스템이 이렇게 붙인다 (너는 안 적어도 된다).

```
Framed from the waist up so both faces fill much of the frame,
close enough that every expression is clear.
```

**샷 크기를 쓸 때도 넓게 잡지 마라.** `wide shot` `full body` `establishing
shot` 은 세로 쇼츠에서 쓸모가 없다. `medium close-up` · `close-up` ·
`over-the-shoulder` 쪽으로 쓴다.

### `COLOR` — 색 통일

모든 컷에 **글자 하나 다르지 않은** 색 지시를 넣는다. 컷마다 색이 튀면
이어 붙였을 때 바로 티가 난다. 이 줄은 시스템이 붙이니 적지 않는다.

---

## ⭐ 정책에 막히는 말 (2026-08-20 · 실제로 막혔다)

플로우가 컷 프롬프트를 이렇게 되돌려 보냈다 —
> **"이 프롬프트는 유명인의 동영상 생성에 관한 Google 정책을 위반할 가능성이 있습니다."**

원인은 **실제 방송·배우를 가리키는 말**이 겹친 것이었다.
`Live-action Korean drama` + `Korean TV drama realism` + `swapping in a different actor`
→ "실제로 방영된 한국 드라마를 실존 배우로 다시 만들어 달라" 로 읽힌다.

### ⚠️ 컷 프롬프트 안에서는 배역을 **영어 관계말**로 부른다

`SUBJECT: 남편 …` 처럼 한글 배역말을 쓰면 기계는 그것이 무슨 뜻인지 모른다.
아는 것은 "사람 자리에 들어간 모르는 낱말" 뿐이라 **사람 이름**으로 읽고,
이름 붙은 사람을 사진처럼 만들어 달라는 말이 되어 유명인 검사에 걸린다.

| ✗ 막힌다 | ○ 통과한다 |
|---|---|
| `SUBJECT: 남편 in a casual jacket` | `SUBJECT: the husband in a casual jacket` |
| `ACTION: 본처 steps in front of 남편` | `ACTION: the wife steps in front of the husband` |
| `DIALOGUE: 본처 (furious): "…"` | `DIALOGUE: the wife (furious): "…"` |

**따옴표 안의 대사는 한국어 그대로 둔다** — 그건 화면에 나올 말이다.
`characters` 의 `name` 은 한글 그대로 적는다 (화면·도서관에서 쓴다).
바뀌는 것은 **플로우에 보내는 컷 프롬프트뿐**이다.

관계말 예: 본처 → `the wife` · 남편 → `the husband` ·
내연녀 → `the other woman` · 며느리 → `the daughter-in-law` ·
시동생 → `the brother-in-law` · 시어머니 → `the mother-in-law`

### ⚠️ `SUBJECT` 에 얼굴을 적으면 **모든 컷이 막힌다** (실제로 겪었다)

`SUBJECT: 남편(55, square face, short neatly parted black hair) …` 로 적었더니
80컷이 전부 거절됐다. 기계 눈에는 이렇게 보인다 —
**"남편이라는 사람, 55살, 이 얼굴"** = 실존 인물을 찍어 달라는 말.
`본처` `남편` 은 배역말인데 기계는 **사람 이름**으로 읽는다.

| ✗ 막힌다 | ○ 통과한다 |
|---|---|
| `남편(55, square face, short black hair) in a casual jacket` | `남편 in a casual jacket` |
| `본처, a 52-year-old woman with an oval face` | `본처 in a simple cardigan` |

얼굴은 **플로우 캐릭터(기준 사진)** 가 잡아 준다. 컷 프롬프트는
**이름 + 옷차림**까지만 적는다. 나이·얼굴형·머리 모양을 컷에 적지 않는다.

### 절대 쓰지 않는 말

`actor` · `actress` · `celebrity` · `famous` · `star` · `idol` ·
`K-drama` · `Korean TV drama` · `live-action drama` ·
실제 드라마·영화 제목 · 실제 배우·가수·정치인 이름 ·
`looks like ...` · `resembling ...` · `in the style of <사람 이름>`

### 대신 이렇게 쓴다

| ✗ 막힌다 | ○ 통과한다 |
|---|---|
| Korean TV drama realism | grounded everyday Korean realism |
| photorealistic live-action photograph | photorealistic studio photograph |
| swapping in a different actor | swapping in a different person |
| a Korean actress in her 50s | a Korean woman in her 50s |
| looks like a famous actor | ordinary, plain features |

인물은 **지어낸 사람**이다. `flow_prompt` 에도 실제 사람을 떠올리게 하는 말을
넣지 않는다 — 나이·얼굴형·머리·표정처럼 **생김새만** 적는다.

---

## ⭐⭐ 후킹과 제목 — 점잖게 쓰면 아무도 안 본다 (2026-08-20 운영자 지시)

> 운영자 원문: **"제목이랑 후킹 좀 더 자극적으로 뽑아. 자꾸 점잔 빼지 말고
> 선비처럼. 신경을 자극하고 관심을 유도하고, 속이지 않는 범위 내에서
> 최대한 과장되고 사람들이 유인되게끔."**

쇼츠는 **첫 1초**에 손가락이 멈추느냐로 끝난다. 아무리 좋은 이야기도
맨 위 한 줄이 밋밋하면 아무도 안 본다. 지금까지 뽑힌 것들이 이랬다 —
`집을 나가는 남편` `이혼 소송 기각` `앙심을 품다`. 이건 **목차**지 후킹이 아니다.
아무 일도 안 일어난 것처럼 보인다.

### 지켜야 할 여섯 가지

1. **거짓말은 절대 금지.** 판결문에 없는 일은 한 글자도 안 쓴다.
   과장은 하되 **속이지 않는다.** (사람이 안 죽었는데 죽었다고 쓰면 끝이다)
2. **숫자를 넣는다.** `15억` `0원` `십 원 한 장` `이십 년` — 숫자는 그 자체로 세다.
3. **배신 · 상실 · 뒤집기 중 하나를 반드시 드러낸다.** 무엇을 잃었는지,
   누가 배신했는지, 무엇이 뒤집혔는지가 한 줄에 보여야 한다.
4. **결말은 말하지 않는다.** 궁금해야 남는다. "결국 다 돌려받았다" 는 최악이다.
5. **사실 보고가 아니라 판정이다.** ⭐ 이게 가장 중요하다.
   신문 기사처럼 "무슨 일이 있었다" 고 적으면 아무도 안 멈춘다.
   **누가 나쁜 놈인지 이름을 붙이고** 감정을 실어라.
   | ✗ 사실 보고 | ○ 판정 |
   |---|---|
   | 그 여자를 데려와 이혼을 요구했다 | **불륜녀를 집에 데려온 쓰레기 남편** |
   | 보험금 15억도 그 여자 앞으로였다 | **보험금 15억, 받는 사람은 불륜녀** |
   | 법원이 내린 답은 15억이었다 | **법원이 15억을 다 토해내라고 했다** |
   왼쪽은 다 맞는 말이지만 손가락이 안 멈춘다. 오른쪽은 **화가 난다.**
   ⚠️ 끝맺음이 명사여도 좋다 — `쓰레기 남편` `빚 6억` 처럼 **체언으로
      끝나면 오히려 세다.** 동사로 끝내라는 예전 규칙은 틀렸다.
6. **센 대사 한 줄을 그대로 써도 좋다.** `"내 눈에 흙이 들어가기 전엔"`
   처럼 따옴표째 쓰면 사람 목소리가 들려서 더 세다.

### 쓰면 안 되는 밋밋한 말투

`~에 대하여` · `~의 진실` · `~하는 이유` · `~ 이야기` · `~의 전말` ·
`충격` · `경악` · `소름` (이 셋은 흔해 빠져서 오히려 안 눌린다)

### 강조할 한 토막을 `*별표*`로 감싼다 (색이 들어갈 자리)

화면에서 후킹은 흰 글자로 크게 나간다. 그중 **가장 센 한 토막**만 금색으로
칠하면 눈이 거기부터 간다. 어디를 칠할지는 **네가 정해서 별표로 감싼다.**

```
보험금 *15억*도 그 여자 앞으로였다
*그 여자*를 데려와 이혼을 요구했다
아내에게 남은 건 *빚 6억*뿐이었다
```

- **한 토막만** 감싼다. 두 군데 이상 칠하면 아무 데도 안 튄다.
- 감쌀 것은 **숫자·돈**(`15억` `0원` `빚 6억`)이나 **사건의 핵심**
  (`그 여자` `떨어져 죽었다` `자필 서명`).
- 조사는 밖에 둔다 — `*15억*도` (○) / `*15억도*` (✗)
- 별표는 **화면에 안 나온다.** 22자를 셀 때도 별표는 안 센다.
- 유튜브 제목·설명에는 시스템이 별표를 떼고 넣는다.

### `hook` — 화면 맨 위에 30초 내내 붙는 한 줄 (**22자 이내**)

| ✗ 이렇게 쓰면 안 된다 | ○ 이렇게 쓴다 |
|---|---|
| 집을 나가는 남편 | **불륜녀를 집에 데려온 쓰레기 남편** |
| 이혼 소송 기각 | **바람피운 놈이 먼저 이혼하자고 했다** |
| 앙심을 품다 | **재판에서 지자 재산을 다 숨겼다** |
| 끝없는 빼돌리기 | **병원도 아파트도 불륜녀 이름으로** |
| 갑작스러운 죽음 | **그 여자 집에서 떨어져 죽은 남편** |
| 장례식장의 불청객 | **남편 장례식장에 불륜녀가 왔다** |
| 상속 재산 분쟁 | **아내가 받은 유산은 빚 6억** |

왼쪽은 **무슨 일인지 설명**하고, 오른쪽은 **누가 나쁜 놈인지 판정**한다.
그 차이가 손가락을 멈추게 한다.

**최소 12자는 되어야 한다.** 밋밋한 것들은 하나같이 짧았다 —
`앙심을 품다`(6자) `끝없는 빼돌리기`(7자). 누가 무엇을 했는지 담을 자리가 없다.

### `yt_title` — 유튜브에 올릴 제목 (**40자 이내**)

`hook` 보다 한 뼘 더 길게 쓴다. **누가 무엇을 어떻게 했는지**를 다 넣고,
`(n/16)` 은 우리가 붙이니 적지 않는다. `#shorts` 도 우리가 붙인다.

| ✗ | ○ |
|---|---|
| 집을 나가는 남편 | 불륜녀를 집에 데려온 남편이 이혼하자고 했습니다 |
| 이혼 소송 기각 | 바람피운 남편이 오히려 먼저 이혼 소송을 걸었습니다 |
| 갑작스러운 죽음 | 그 여자 아파트에서 떨어져 죽은 남편, 4년 만이었습니다 |
| 상속 재산 분쟁 | 20년을 산 아내가 받은 유산은 빚 6억뿐이었습니다 |

**16화 전부**에 `hook` 과 `yt_title` 을 넣는다. 하나라도 비면 그 화는
아무도 안 보는 영상이 된다.

---

# 출력 형식

**JSON 하나만** 출력한다. 머리말·설명·코드펜스 없이 `{` 로 시작해 `}` 로 끝난다.

```json
{
  "title": "이십 년 며느리, 상속은 0원",
  "case_id": "230761",
  "characters": [
    { "name": "며느리", "face_tag": "50s, oval face, low bun", "voice": "a warm mid-range woman's voice in her fifties, weary and a little breathy, trails off at the end of a sentence", "outfit": "a black mourning hanbok", "flow_prompt": "Korean woman, 52 years old, oval face, tired eyes with fine lines, dark brown hair in a low bun, worn calm expression. Photorealistic, natural skin texture, plain natural look." }
  ],
  "episodes": [
    {
      "no": 1,
      "hook": "*장례 다음 날* 집을 내놓으라 했다",
      "yt_title": "남편 장례 다음 날, 시동생이 집을 비우라고 했습니다",
      "title": "장례식 다음 날",
      "recap": "",
      "cuts": [
        {
          "n": 1,
          "role": "후킹",
          "subtitle": "\"이 집, 오늘 안에 비워 주세요.\" / \"그이 장례가 어제였어요. 지금 그 말이 나와요?\"",
          "caption": "장례를 치른 다음 날, 시동생이 집을 요구했다",
          "prompt": "Fictional scene, invented characters, semi-realistic illustrated drama. 6-second single continuous take.\nSHOT: Medium two-shot, static camera, both faces visible.\nSUBJECT: the brother-in-law in a black suit facing the daughter-in-law in black mourning hanbok.\nACTION: the brother-in-law sets a closed folder on the table and steps back.\nDIALOGUE: the brother-in-law (calm and cold): \"이 집, 오늘 안에 비워 주세요.\" / the daughter-in-law (trembling): \"그이 장례가 어제였어요. 지금 그 말이 나와요?\"\nSETTING: Korean funeral hall reception room, evening, dim overhead fluorescent light.\nSTYLE: one single continuous take, no cut, no scene change, same location and same person from first frame to last, identical clothing throughout, semi-realistic hand-drawn illustration style with clean confident linework and soft cel shading, grounded adult proportions and restrained faces rather than cartoon exaggeration, muted desaturated palette, soft practical lighting, shallow depth of field, consistent line weight in every shot.\nAvoid: overlapping voices, on-screen text, signage, documents with visible writing, screens, background extras in focus, cutting to another shot, changing the background mid-shot, the person changing clothes or face mid-shot, swapping in a different person."
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
| `subtitle` | 화면에 우리가 얹을 **대사 자막**. **60자 이내.** 주고받으면 ` / ` 로 잇는다 |
| `caption` | 화면에 우리가 얹을 **설명 자막** (없으면 빈 문자열). 숫자·법률·경위처럼 입으로 하면 어색한 사실을 여기 적는다. 40자 이내 |
| `prompt` | 위 규격 그대로 — **머리말 줄 + 6줄**. 줄바꿈은 `\n` |
| `recap` | 2화부터 채운다. 지난 줄거리 한 줄, **30자 이내** (1화는 빈 문자열) |
| `hook` | **화면 맨 위에 30초 내내 붙어 있을 한 줄.** **22자 이내(별표는 안 센다).** 가장 센 한 토막을 `*별표*` 로 감싼다 — 그 토막만 금색으로 칠해진다. 이걸 보고 남느냐 떠나느냐가 갈린다 — 제목이 아니라 **후킹**이다. 위 「후킹과 제목」 규칙을 그대로 따른다 (○ `이혼 패소 날 재산이 사라졌다` / ✗ `집을 나가는 남편`) |
| `yt_title` | **유튜브에 올릴 제목.** **40자 이내.** `(n/16)` 과 `#shorts` 는 우리가 붙이니 적지 않는다 (○ `바람난 남편이 통장을 비우고 집을 나갔습니다`) |
| `voice` | 인물마다 **필수.** 목소리 한 줄(영어) — 높낮이·나이대·말버릇 |
| `characters` | 3명 이하 |

---

# 출력 전 스스로 점검

- [ ] 16화 × 5컷 = 80컷이 다 있는가
- [ ] 모든 화의 컷1이 **대사 또는 충격 장면**으로 시작하는가 (설명 금지)
- [ ] 모든 `prompt` 가 **머리말 줄**(`Fictional scene, invented characters, semi-realistic illustrated drama. 6-second single continuous take.`) 로 시작하는가
      (`SHOT:` 으로 시작하면 붙여 넣을 때 주소로 읽혀 글자가 통째로 깨진다)
- [ ] 머리말 다음이 `SHOT:` 이고 `Avoid:` 로 끝나는가
- [ ] 모든 `prompt` 에 `STYLE:` 줄이 **글자 그대로 똑같이** 들어갔는가
- [ ] 문서·간판·화면처럼 **글자가 나올 물건**을 부른 컷이 하나도 없는가
- [ ] 대사가 있는 컷은 말하는 사람이 화면 안에 있는가
- [ ] 한 컷 대사가 **30~34음절**인가 (세어 봤는가)
- [ ] 주고받는 컷이 **세 번**(A→B→A) 오가는가 (두 번이면 6초가 빈다)
- [ ] **서로 몸이 닿는 동작**이 한 컷도 없는가 (손이 옷 속으로 녹아든다)
- [ ] 모든 화에 `hook`(22자 이내) 과 `yt_title`(40자 이내) 이 있는가
- [ ] `hook` 에서 **가장 센 한 토막**을 `*별표*` 로 감쌌는가 (한 군데만)
- [ ] `hook` 이 **사실 보고가 아니라 판정**인가
      (`그 여자를 데려와 이혼을 요구했다` ✗ → `불륜녀를 집에 데려온 쓰레기 남편` ○)
- [ ] `hook` 이 **12자 이상**인가 (짧으면 누가 무엇을 했는지 안 그려진다)
- [ ] `hook` 에 숫자나 배신·상실·뒤집기가 드러나는가 (밋밋하면 아무도 안 본다)
- [ ] `hook` 이 판결문에 **실제로 있는 일**인가 (과장은 되나 거짓은 안 된다)
- [ ] 인물마다 `voice` 를 정했는가 (높낮이·나이대·말버릇 — 없으면 로봇이 읽는다)
- [ ] `voice` 에 **native Korean speaker** 가 들어갔는가 (없으면 외국인이 읽는 소리가 난다)
- [ ] 같은 장소를 이어 쓰는 컷들의 `SETTING` 이 **글자 그대로 같은가**
      (다르면 이어지는 장면이 아니라 딴 곳으로 읽힌다)
- [ ] 대사에 **숨 쉴 쉼표**가 들어갔는가 (한 문장을 끝까지 밀면 외국어처럼 늘어진다)
- [ ] 소리에 관한 것을 `no ~` 로 적지 않고 **바라는 것만** 적었는가
- [ ] 같은 화에 나오는 두 사람의 `voice` 가 **서로 확실히 다른가**
- [ ] `DIALOGUE` 의 톤이 한 낱말이 아니라 **어떻게 말하는지**를 적었는가
- [ ] 인물마다 `outfit`(색까지) 과 `face_tag`(짧게) 를 정했는가
- [ ] `flow_prompt` 에 **나이·얼굴형·눈·코입·피부·머리·몸·표정**이 다 들어갔는가
- [ ] 같은 인물의 `SUBJECT` 가 **모든 컷에서 한 글자도 같은가** (다르면 딴사람이 나온다)
- [ ] 한 `SUBJECT` 줄에 **같은 사람을 두 번** 적지 않았는가
      (✗ `남편 in a suit facing 본처 in a blouse facing 남편 in a suit` — 사람이 셋인 줄 알고 한 명 더 그린다)
- [ ] 한 화에 `SHOT` 크기가 **세 가지 이상** 섞였는가 (5컷은 클로즈업)
- [ ] `wide shot` `full body` 처럼 **넓게 잡는 말**을 쓰지 않았는가
      (세로 쇼츠에서 얼굴이 작으면 표정이 안 보여 그냥 넘긴다)
- [ ] `SETTING` 이 한 화에 **두 곳 이내**이고, 바뀌는 컷에 `caption` 을 달았는가
- [ ] 화면에 **있는** 사람을 `저 여자` `그 사람` 처럼 3인칭으로 부른 대사가 없는가
- [ ] 대사에 `유류분` `한정승인` `시효` 같은 **서류 말투**가 없는가
- [ ] 숫자·법률·경위는 `caption` 이 지고 있는가 (입은 감정만 말하는가)
- [ ] 소리 내어 읽었을 때 **사람이 실제로 하는 말**로 들리는가
- [ ] **모든 화에 주고받는 컷이 2컷 이상** 있는가 (혼잣말만 이어 붙이지 않았는가)
- [ ] 주고받는 컷의 `SHOT` 이 two-shot 인가
- [ ] 대사에 `내연녀` 같은 **배역 딱지**가 들어간 곳이 없는가
- [ ] 1화부터 16화까지 **일어난 순서대로**인가 (죽은 사람이 뒤에서 살아나지 않는가)
- [ ] 컷 프롬프트 안에서 배역을 **영어 관계말**(`the wife` `the husband`)로 불렀는가
      (한글 배역말은 사람 이름으로 읽혀 막힌다 · 따옴표 안 대사는 한국어 그대로)
- [ ] `SUBJECT` 에 **나이·얼굴형·머리 모양**을 적지 않았는가
      (`남편(55, square face…)` ✗ → `남편 in a casual jacket` ○ · 적으면 80컷이 전부 막힌다)
- [ ] `actor` `celebrity` `K-drama` 처럼 **실제 방송·배우를 가리키는 말**이 없는가
      (있으면 플로우가 "유명인 동영상 생성 정책" 으로 막아 영상이 아예 안 나온다)
- [ ] 실명·지명·법원명·사건번호·절대 연도가 없는가
- [ ] 16화를 순서대로 읽으면 하나의 이야기로 이어지는가

<!-- PROMPT:END -->

## 옷과 배경 — 뭉뚱그리면 컷마다 바뀐다

영상 만드는 쪽은 **앞 컷을 기억하지 못한다.** 컷마다 백지에서 새로 그린다.
그래서 "앞이랑 똑같이" 라고 써 봐야 소용이 없다 — 앞이 무엇이었는지 모르니까.

연속돼 보이게 하는 방법은 하나뿐이다: **무엇인지 못 박고, 컷마다 똑같이 쓴다.**

  ✗ `SUBJECT: 남편 in a casual jacket`
     → 세상의 온갖 자켓 중 아무거나. 다섯 컷에 다섯 벌이 나온다.
  ○ `SUBJECT: 남편 wearing an olive-green cotton work jacket over a grey
     crewneck, with dark charcoal trousers`
     → 색·소재까지 하나. 기억이 없어도 매번 같은 것이 나온다.

  ✗ `SETTING: Korean apartment living room, evening`
     → 매번 다른 거실.
  ○ `SETTING: Korean apartment living room, evening — a beige three-seat
     fabric sofa along the left wall, a tall dark-wood bookshelf behind,
     a wide balcony window with the night city beyond`
     → 가구가 자리를 잡아 준다.

규칙
  · 옷은 **색 + 소재 + 겉옷/속옷**까지. `casual` `simple` `plain` 같은
    뭉뚱그린 말은 쓰지 않는다 (아무 정보도 없다).
  · 한 인물의 옷차림은 **그 화 안에서 글자 하나까지 똑같이** 반복한다.
    (사람은 날마다 갈아입으므로, 맞출 범위는 한 화 안이다)
  · 같은 장소는 **같은 가구 목록**을 글자 그대로 반복한다.
  · ⚠️ **얼굴·나이는 절대 안 적는다.** `남편(55, square face…)` 로 적었다가
    유명인 정책에 다섯 번 막혔다. 얼굴은 플로우 캐릭터(기준 그림)가 잡는다.
    여기서는 **옷과 가구만** 적는다.

> 플로우에서 같은 장소가 이어지는 컷은, 새로 만들지 말고
> **[이 영상에서 이어서 만들기](장면 연장)** 를 쓰면 픽셀이 그대로 이어진다.
> 프롬프트로 되는 것과는 차원이 다르다.
