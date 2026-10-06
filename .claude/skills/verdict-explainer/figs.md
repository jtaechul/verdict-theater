# 그림 설계 칸 (`figs[id]`) — `src/diagram60.py`

모든 종류에 공통으로 들어가는 칸:
- `"type"`
- `"bg"`: 바탕으로 깔 창고 영상 번호. `library.json` 의 `n`
- `"title"`(선택)

화면은 1080×1920이다. 연도·금액·지명은 그림 글에도 익명화 규칙(SKILL.md 0장 9)을 지킨다. 그림은 위쪽 180~1250에 앉히고, 그 아래는 자막·쇼츠 단추 자리로 비운다.
⭐ 긴 영상(`layout: "long"`)은 1920×1080 이다 — 그림은 위 90~830, 이름표 752, 자막 868~1040. 칸 이름·요소 이름은 세로와 같고
자리만 코드가 가로로 잡는다. 다만 관계도 `nodes` 의 `at` 은 대본에 적은 자리 그대로이므로 **가로 화면 자리로** 적는다
(S95 `family`: 남편 [760, 250] · 아내 [1320, 250] · 아들 [600, 610] · 다른 자녀 [920, 610]).
색 이름은 `gold` · `red` · `ink` · `soft` · `grey` · `mute` 를 쓴다. `who` 에는 인물표의 **관계 이름**(`딸`, `땅주인` …)을 적는다.
얼굴은 인물 시트 카드에서 잘라 온다. 이름표는 「가명 (관계)」로 저절로 붙는다.

컷의 `add` 에는 아래 **요소 이름**만 쓴다. 틀리면 `drama60 check` 가 잡는다.

## card — 때 넘김
`{"type": "card", "text": "40여 년 전", "sub": "사연의 시작"}`  ← 연도는 상대로 (SKILL.md 0장 9 익명화)
요소: `card`

## relations — 인물 관계도 (S94 `family`)
```
nodes  [{"id", "who": 인물 | "ghost": true + "name": "아버지",   ← 사진 없는 사람(고인 등)은 윤곽
         "at": [x, y], "r": 78~112, "role": 괄호 글, "gold": 주인공, "size": 이름 글씨,
         "label": "below"(기본) | "right" | false}]
edges  [{"id", "a", "b", "style": "solid"(실제) | "paper"(금색 점선 · 서류상) | "sibling"(형제 점선),
         "down": true(위 사람 이름표 아래에서 곧장 내려온다), "text", "text_at", "chip", "chip_t"}]
labels [{"id", "node", "role", "replaces": [요소…]}]     ← 이름표 괄호를 바꿔 끼운다 (내연녀 → 새어머니)
texts  [{"id", "text", "at", "color", "replaces"}]       ← 선 위 글 (내연 관계 → 1973년 재혼)
marks  [{"id", "kind": "caption"(얼굴 아래 띠) | "grave"(묘 표시 · at) | "banner"(맨 위 주장 띠 · tag+text)
         | "glow"(붉은 고리 · node), …}]
legend "auto"(서류상 선이 있을 때만 · 기본) | true | false | [["solid", "실제 관계"], ["paper", "서류상"]]
```
요소: `heading` · `legend` · 각 edge/node/label/text/mark 의 `id`

S94 자리:
- 아버지 [540,400] r78 (이름 오른쪽)
- 어머니 [235,660] r92
- 새어머니 [845,660] r104
- 딸 [235,1010] r112 (금색)
- 이복동생 [845,1010] r112

S94 쌓는 차례 (컷 6~11):
- 컷6: heading, legend, child1 → 아버지 → 어머니·부부선 → 내연녀·내연 관계 → 「한옥자」 에 이름표
- 컷7: 「윤기철」 에 child2·선
- 컷8: 「본처」 에 paper(서류상: 본처의 아들)
- 컷9: 「친동생」 에 sibling
- 컷10: 「세상을」 에 별세, 「묻었습니다」 에 산에 묘 (S94 당시엔 「1969 별세」 — 새 대본은 연도를 안 쓴다)
- 컷11: 「재혼」 · 「새어머니」 에서 글과 이름표를 갈아 끼운다

주장 ① 은 같은 그림에 banner(legend 를 갈아 끼운다) + glow 로 보였다 (컷21).

## timeline — 연표
```
rows  [{"id", "year": "10년 뒤", "who": "아버지 별세 · 한옥자 → 윤정숙", "what": "세 번에 걸쳐 1억 9,500만 원",
        "color": "gold"|"red", "what_color"}]      ← 다섯 줄 안팎 (줄마다 140px)
cards [{"id", "after": 줄 id, "title": "확인서", "text": "'…다투지 않는다'"}]
faces [{"id", "row": 줄 id, "who"}]               ← 그 줄 오른쪽에 얼굴
```
요소: `heading` · 줄 `id` · card `id` · face `id`

## issue — 재판의 쟁점 (소송 배경 → 원칙 → 쟁점)
```
suit     {"from": 원고, "to": 피고, "quote": "\"묘를 파내 달라\"", "year": "40여 년 뒤 소송"}
rule     [["grave", "묘를 지킬 권리는"], ["table", "제사를 모시는 사람에게"]]   ← 두 줄 · 작은 그림 이름 + 글
question "어머니 제사를 모실 사람은?"
cands    [{"who", "role": "호적상 아들"}, {"who", "role": "친딸", "gold": true}]   ← 한 명이면 가운데
chips    [{"id", "under": 0|1, "text": "땅주인: 윤정숙 씨는 아니다", "color": "red"}]
```
요소: `heading` · `suit` · `rule` · `question` · `cands` · chip `id`

## flow — 돈·물건이 간 길 (S94 `money`)
```
from {"who"} · to {"who"} · amount "1억 9,500만 원" · sub "세 번에 나눠"   ← 판결문 금액 × amount_scale
claim {"tag": "땅주인 주장", "text": "묘를 포기한 대가였다"}     ← cross 요소로 X 를 긋는다
doc   {"tag": "확인서", "text": "한옥자·윤기철 모자와 법적으로 다투지 않는다"}
chips [{"id", "text", "color", "solid", "side": "left"|"right"}]
```
요소: `heading` · `people` · `flow` · `claim` · `doc` · `cross` · chip `id`

## compare — 서류 vs 실제 (S94 `paper`)
```
subject {"who": 이복동생}
left    {"chip": "서류상 엄마", "ghost": true, "name": "윤정숙 씨 어머니"}
right   {"chip": "진짜 엄마", "who": 새어머니}
year "그보다 앞서" · ruling "'친아들 아님' 판결" · fix "호적 정정" · broken "남남" · result "서류상으로도 남남"
```
요소: `heading` · `son` · `slots` · `link_paper` · `link_real` · `year` · `ruling` · `fix` · `broken`
(`broken` 이 나오면 `year` · `ruling` · `link_paper` 는 사라진다)

## verdict — 판결 정리
```
rows [{"id", "icon": {"who": 인물} | "coin" | "home" | …, "claim": "호적상 아들이 제사?",
       "answer": "→ 친딸 윤정숙 씨가 지킨다", "mark": "x"(기본 · 안 받아들임) | "o"(받아들임) | ""}]   ← 1~3줄
lose "1심 · 항소심 모두 땅주인 패소"                 ← 금색 결론 띠
stay {"icon": "grave", "text": "어머니 묘는 그대로"}  ← 끝 한 줄 (icon 없으면 가운데 글만)
```
요소: `heading` · 줄 `id` · `lose` · `stay`

## board — 글판 (법 원칙 · 몫 셈 · 주장과 판단 · S95)
```
items [{"id", "kind", "text", "sub", "icon", "tag", "color", "segs", "new"}]   ← 위에서부터 한 줄씩 쌓인다
  kind: big(큰 말 + 풀이) · line(작은 그림 + 한 줄) · chip(알약) · claim(주장 상자 · tag 「최동준 씨 주장」) ·
        quote(판결 말 · 따옴표) · result(결론 · 금색 · sub 작은 줄) · eq(셈) ·
        bar(몫 막대 · segs [{"label": "아내", "n": 3, "color": "gold"}, {"label": "자녀", "n": 2}])
  new: true — 이야기가 바뀌는 줄 (칸이 남아도 새 장으로 넘긴다)
cross "claim 줄 id"   ← 그 줄에 X 를 긋는다 (요소 이름도 `cross`)
```
요소: `heading` · 줄 `id` · `cross`
- 칸이 차거나 `new` 를 만나면 다음 장으로 넘어간다. 앞 장 줄은 사라지고 제목은 남는다. 주장 장이 넘어가면 X 도 사라진다.
- 셈(eq) 바로 뒤의 결론(result)은 늘 같은 장에 나온다 (셈만 보이고 답이 다음 장으로 가지 않게).
- 한 장에 4~5줄이 알맞다. 「주장 → 이유 넷 → 판결 말 → 결론」 처럼 이야기가 바뀌는 곳에 `new` 를 단다.

## 작은 그림 (ICONS)
`grave` 묘 · `table` 제사상 · `coin` 돈(₩) · `home` 집·땅 · `doc` 서류 · `scale` 저울(법) · `ring` 반지(혼인)
— issue 의 `rule` 줄, verdict 의 `icon` · `stay.icon` 에 쓴다.
