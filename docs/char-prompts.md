# 인물 이미지 생성 프롬프트 (제미나이용)

배우 7명. **각 블록을 그대로 복사해 제미나이에 붙여넣으면 바로 나온다.**
추가로 붙일 말은 없다 — 화풍·화질·격자·금지사항이 전부 블록 안에 들어 있다.
공통 프롬프트 같은 것은 없다. 한 사람당 한 번 복사, 한 번 붙여넣기다.

## 화풍 — 인물은 애니, 배경은 사진 (2026-08-12 확정)

처음에는 **인물 프롬프트에만 화풍이 안 적혀 있었다.** 화풍을 안 적으면 AI 가
알아서 정한다. 그래서 손님 모르게 애니가 나왔고, "말도 안 하고 애니메이션으로
바꾸냐" 는 지적을 받았다. 그 뒤 손님이 직접 정하셨다 —

| | 화풍 | 까닭 |
|---|---|---|
| **인물** | 반실사 애니 (극화체) | 싼 flash 모델로도 쓸 만하다. 장당 **197원 → 57원**. 회차마다 얼굴을 바꾸기로 했으므로 벌 수만큼 그 차이가 곱해진다 |
| **배경** | 사진 그대로 | 픽사베이·픽셀스에서 **0원**으로 받는다. AI 로 다시 그리면 30장에 약 1,700원이 들고 그 뒤로도 계속 든다 |

### 두 화풍을 섞는데 왜 안 겉도나

배경은 화면에 깔릴 때 **14px 흐리게 + 22% 어둡게** 처리된다. 또렷한 사진이
아니라 뭉개진 색면이 된다. 그 위에 그림 인물이 서는 것은 사연 채널에서 흔히
쓰는 방식이고, 실제로 잘 붙는다.

**다만 아무 애니나 되는 것은 아니다.** 눈 큰 소녀풍(모에)으로 나오면 흐린 법정
사진 위에서 반드시 겉돈다. 그래서 아래 블록마다 이렇게 못 박아 두었다.

- 실제 사람 비율 **7~8등신**, 적힌 나이 그대로 (`no chibi, no moe`)
- 배경 팔레트에 맞춘 **낮은 채도** (`muted, desaturated palette`)
- **굵은 검은 윤곽선 금지** — 보기에도 튀고, 검은 옷과 붙어 오려낼 때 딸려 온다

> ⚠️ 아래 블록에서 `Semi-realistic anime` 와 `Not a photograph` 를 지우지
> 마십시오. 그 두 줄이 화풍이 다시 갈라지는 것을 막습니다.
> (`tools/style_check.py` 가 올릴 때마다 자동으로 확인합니다)

## 그림이 나온 뒤

나온 그림을 **대화창에 그대로 보내면 된다.** 파일 이름을 바꿀 필요도, 어디에
올릴 필요도 없다 — 저장소에 넣는 일은 클로드가 한다. 누구인지만 알려주면 된다.

오른쪽 아래 제미나이 로고는 **신경 쓰지 않아도 된다.** 18번 칸(오른쪽 맨 아래)을
아예 비워 두라고 프롬프트에 적어 뒀기 때문에, 로고는 빈 칸에 얹히고 인물을
가리지 않는다.

## 왜 이런 조건이 붙어 있나

| 조건 | 이유 |
|---|---|
| 배경 크로마 그린 `#00B140` | 인물만 오려내 배경 위에 얹는다. 초록 단색이라야 깨끗하게 떨어진다 |
| 칸 선 마젠타 `#FF00FF` 12px | 예전엔 검은 선이었다. **검은 옷과 구분이 안 돼 옷이 잘려 나갔다** |
| 사람 밖에 검정·회색·흰 선 금지 | 같은 이유. 사람 아닌 색은 초록과 마젠타 둘뿐이어야 한다 |
| 바닥 그림자 금지 | 그림자까지 오려져 배경 위에 떠 있는 회색 얼룩으로 남는다 |
| 18번 칸 비우기 | 제미나이 워터마크 자리 |
| 18칸 얼굴 동일 | 한 사람이 회차 내내 같은 얼굴이어야 한다 |
| 사람마다 옷 색이 다름 | 50~60대 시청자는 **옷 색으로 인물을 기억한다.** 예전에 일곱 명이 전부 남색이라 "아버지랑 차남이 똑같다" 는 지적을 받았다 |

## 칸 순서 (코드가 이 순서로 자른다 · `CELL_ORDER`)

```
 1 무표정얼굴   2 슬픔얼굴   3 분노얼굴
 4 놀람얼굴     5 냉담얼굴   6 우는얼굴
 7 무표정상반신 8 슬픔상반신 9 분노상반신
10 놀람상반신  11 냉담상반신 12 우는상반신
13 전신 서기   14 전신 걷기 15 전신 앉기
16 전신 뒷모습 17 주저앉기  18 (빈 칸)
```

---

## 어머니·60대 여성 (F50A)  ·  `F50A.png`

```
Semi-realistic anime character sheet in the restrained style of a serious adult Korean television drama: 18 drawings of ONE Korean woman, all drawn in one single consistent style, arranged in a strict grid of 3 columns across and 6 rows down, portrait orientation, overall aspect ratio 1:2. This is a hand-drawn semi-realistic anime illustration. Not a photograph, not photorealistic, not a 3D render, not CGI. Draw her with realistic adult body proportions of seven to eight heads tall and a face that reads her true age. Do NOT give her oversized eyes, do NOT make her look younger, cuter or prettier than described. No chibi, no moe, no shoujo sparkle, no glossy highlights in the eyes, no thick black outline around the body.

THE WOMAN — she must be the same identifiable individual in every single cell:
She is 62 years old, Korean, 155 cm, slightly stout with softly rounded shoulders. Her face is a soft oval with a gentle jawline and a slight fullness under the chin. Her hair is short and tightly permed into small dense curls, black going clearly grey at both temples, brushed back off the forehead with no fringe. Her eyes are small monolid eyes with heavy, tired lower lids and faint dark circles beneath them, framed by deep crow's feet. Her eyebrows are sparse and softly arched. Her nose is small with a low bridge and a rounded tip. Her lips are thin with slightly downturned corners, and the folds from her nose to the corners of her mouth are deep. Her skin is warm ivory with sun spots across both cheekbones and faint freckling. She has one small dark mole about a centimetre below the left corner of her mouth. She wears no makeup. She wears a loose light beige crew-neck knitted sweater over a plain white cotton undershirt, and loose dark brown trousers. Her only jewellery is a thin plain gold wedding band on her left hand.

WHAT IS IN EACH CELL, reading left to right then top to bottom:
Cell 1 head-and-shoulders close-up, neutral expression. Cell 2 same close-up, sad. Cell 3 same close-up, angry. Cell 4 same close-up, shocked. Cell 5 same close-up, cold and unfeeling. Cell 6 same close-up, crying with tears on her cheeks. Cell 7 waist-up, neutral. Cell 8 waist-up, sad. Cell 9 waist-up, angry. Cell 10 waist-up, shocked. Cell 11 waist-up, cold. Cell 12 waist-up, crying. Cell 13 full body standing straight, facing the camera. Cell 14 full body mid-stride walking to the left. Cell 15 full body seated on a plain chair. Cell 16 full body seen from directly behind. Cell 17 full body sinking down to sit on the floor, knees folding. Cell 18 is COMPLETELY EMPTY — flat green only, absolutely no person, no object, no shadow, nothing at all.

BACKGROUND AND GRID — follow this exactly:
The background behind and around her in every cell is FLAT PURE CHROMA GREEN #00B140, perfectly even, with no gradient, no texture, no vignette. Separate the cells with straight lines of PURE MAGENTA #FF00FF about 12 pixels thick, drawn edge to edge across the whole image. Outside the woman herself there are only two colours in the entire image: the chroma green #00B140 background and the magenta #FF00FF divider lines. Never draw a black, grey or white border, frame, outline or line anywhere. Do not draw a ground shadow, a cast shadow, or a contact shadow under her feet or anywhere else.

CONSISTENCY:
Her face, hairstyle, hair colour, clothing and body must be identical in all 17 occupied cells — the same woman, same age, same clothes, same lighting. Only her expression and her pose change from cell to cell. Do not make her younger, thinner or better dressed in any cell.

QUALITY — this is the most important part after the layout:
Maximum image quality. Ultra-high resolution, at least 2048 x 4096 pixels. Clean, crisp, deliberate linework of an even weight, with no wobbling lines, no sketchy double lines and no stray marks. Soft cel shading — a few clear tonal steps plus gentle soft-edged gradients on the face and the fabric — lit evenly from the front with no dramatic rim light. A muted, desaturated palette of warm greys, dull navy, faded beige and soft earth tones, so that the figure sits naturally against a softly blurred, slightly darkened photographic background. Every cell is a fully finished, fully coloured drawing — not a sketch, not bare lineart, not a work in progress — and all 17 are finished to exactly the same standard.

DO NOT INCLUDE:
No text, no letters, no Hangul, no Korean characters, no numbers, no cell labels, no captions, no arrows, no logos, no brand marks, no watermark, no signature, no colour swatches, no ruler, no border around the outside of the image. No extra people. No props other than the plain chair in cell 15. No distorted hands, no extra fingers, no missing fingers, no duplicated limbs, no warped faces, no heavy black outline around the body.
```

---

## 아내·50대 여성 (F50B)  ·  `F50B.png`

```
Semi-realistic anime character sheet in the restrained style of a serious adult Korean television drama: 18 drawings of ONE Korean woman, all drawn in one single consistent style, arranged in a strict grid of 3 columns across and 6 rows down, portrait orientation, overall aspect ratio 1:2. This is a hand-drawn semi-realistic anime illustration. Not a photograph, not photorealistic, not a 3D render, not CGI. Draw her with realistic adult body proportions of seven to eight heads tall and a face that reads her true age. Do NOT give her oversized eyes, do NOT make her look younger, cuter or prettier than described. No chibi, no moe, no shoujo sparkle, no glossy highlights in the eyes, no thick black outline around the body.

THE WOMAN — she must be the same identifiable individual in every single cell:
She is 54 years old, Korean, 163 cm, slim and noticeably upright in posture. Her face is an angular oval with a clearly defined jawline and high cheekbones. Her hair is a glossy near-black blunt bob cut level with her chin, parted on the right and tucked behind her left ear. Her eyes are narrow double-lidded eyes with a direct, sharp gaze, with a thin line of dark eyeliner along the upper lash line. Her eyebrows are straight, slightly thick and neatly groomed. Her nose is straight with a well-defined bridge. Her lips are of medium fullness with a muted rose lipstick, held in a composed, level line. Her skin is fair and well cared for, with fine lines only at the outer corners of her eyes. She has one small mole on the right side of her jaw. She wears a deep plum aubergine blouse with a soft satin sheen, buttoned to the second button and tucked in, with black tailored trousers. She wears small pearl stud earrings and no other jewellery.

WHAT IS IN EACH CELL, reading left to right then top to bottom:
Cell 1 head-and-shoulders close-up, neutral expression. Cell 2 same close-up, sad. Cell 3 same close-up, angry. Cell 4 same close-up, shocked. Cell 5 same close-up, cold and unfeeling. Cell 6 same close-up, crying with tears on her cheeks. Cell 7 waist-up, neutral. Cell 8 waist-up, sad. Cell 9 waist-up, angry. Cell 10 waist-up, shocked. Cell 11 waist-up, cold. Cell 12 waist-up, crying. Cell 13 full body standing straight, facing the camera. Cell 14 full body mid-stride walking to the left. Cell 15 full body seated on a plain chair. Cell 16 full body seen from directly behind. Cell 17 full body sinking down to sit on the floor, knees folding. Cell 18 is COMPLETELY EMPTY — flat green only, absolutely no person, no object, no shadow, nothing at all.

BACKGROUND AND GRID — follow this exactly:
The background behind and around her in every cell is FLAT PURE CHROMA GREEN #00B140, perfectly even, with no gradient, no texture, no vignette. Separate the cells with straight lines of PURE MAGENTA #FF00FF about 12 pixels thick, drawn edge to edge across the whole image. Outside the woman herself there are only two colours in the entire image: the chroma green #00B140 background and the magenta #FF00FF divider lines. Never draw a black, grey or white border, frame, outline or line anywhere. Do not draw a ground shadow, a cast shadow, or a contact shadow under her feet or anywhere else.

CONSISTENCY:
Her face, hairstyle, hair colour, clothing and body must be identical in all 17 occupied cells — the same woman, same age, same clothes, same lighting. Only her expression and her pose change from cell to cell. Her bob must stay exactly the same length and keep the same right-side parting in every cell.

QUALITY — this is the most important part after the layout:
Maximum image quality. Ultra-high resolution, at least 2048 x 4096 pixels. Clean, crisp, deliberate linework of an even weight, with no wobbling lines, no sketchy double lines and no stray marks. Soft cel shading — a few clear tonal steps plus gentle soft-edged gradients on the face and the fabric — lit evenly from the front with no dramatic rim light. A muted, desaturated palette of warm greys, dull navy, faded beige and soft earth tones, so that the figure sits naturally against a softly blurred, slightly darkened photographic background. Every cell is a fully finished, fully coloured drawing — not a sketch, not bare lineart, not a work in progress — and all 17 are finished to exactly the same standard.

DO NOT INCLUDE:
No text, no letters, no Hangul, no Korean characters, no numbers, no cell labels, no captions, no arrows, no logos, no brand marks, no watermark, no signature, no colour swatches, no ruler, no border around the outside of the image. No extra people. No props other than the plain chair in cell 15. No distorted hands, no extra fingers, no missing fingers, no duplicated limbs, no warped faces, no heavy black outline around the body.
```

---

## 장남·50대 남성 (M50A)  ·  `M50A.png`

```
Semi-realistic anime character sheet in the restrained style of a serious adult Korean television drama: 18 drawings of ONE Korean man, all drawn in one single consistent style, arranged in a strict grid of 3 columns across and 6 rows down, portrait orientation, overall aspect ratio 1:2. This is a hand-drawn semi-realistic anime illustration. Not a photograph, not photorealistic, not a 3D render, not CGI. Draw him with realistic adult body proportions of seven to eight heads tall and a face that reads his true age. Do NOT give him oversized eyes, do NOT make him look younger, cuter or prettier than described. No chibi, no moe, no shoujo sparkle, no glossy highlights in the eyes, no thick black outline around the body.

THE MAN — he must be the same identifiable individual in every single cell:
He is 56 years old, Korean, 172 cm, solidly built and slightly thick around the middle. His face is square with a broad forehead, a strong jaw and the beginning of jowls. His hair is short and parted at the side, black heavily salted with grey at both temples, receding a little at the corners of the forehead. His eyes are deep-set monolid eyes with a level, tired gaze and visible bags underneath. His eyebrows are thick, straight and dark. His nose is broad and straight with a fleshy tip. His lips are firm and held in a straight line, with deep folds running from his nose to the corners of his mouth. His skin is a medium tan drawn with a faint dark shadow of stubble along the jaw and above the upper lip. He has a small pale scar cutting through the outer third of his left eyebrow. He wears a navy single-breasted two-button suit jacket, a plain white dress shirt and a plain dark burgundy necktie with no pattern, with matching navy suit trousers and a black leather belt.

WHAT IS IN EACH CELL, reading left to right then top to bottom:
Cell 1 head-and-shoulders close-up, neutral expression. Cell 2 same close-up, sad. Cell 3 same close-up, angry. Cell 4 same close-up, shocked. Cell 5 same close-up, cold and unfeeling. Cell 6 same close-up, crying with tears on his cheeks. Cell 7 waist-up, neutral. Cell 8 waist-up, sad. Cell 9 waist-up, angry. Cell 10 waist-up, shocked. Cell 11 waist-up, cold. Cell 12 waist-up, crying. Cell 13 full body standing straight, facing the camera. Cell 14 full body mid-stride walking to the left. Cell 15 full body seated on a plain chair. Cell 16 full body seen from directly behind. Cell 17 full body sinking down to sit on the floor, knees folding. Cell 18 is COMPLETELY EMPTY — flat green only, absolutely no person, no object, no shadow, nothing at all.

BACKGROUND AND GRID — follow this exactly:
The background behind and around him in every cell is FLAT PURE CHROMA GREEN #00B140, perfectly even, with no gradient, no texture, no vignette. Separate the cells with straight lines of PURE MAGENTA #FF00FF about 12 pixels thick, drawn edge to edge across the whole image. Outside the man himself there are only two colours in the entire image: the chroma green #00B140 background and the magenta #FF00FF divider lines. Never draw a black, grey or white border, frame, outline or line anywhere. Do not draw a ground shadow, a cast shadow, or a contact shadow under his feet or anywhere else.

CONSISTENCY:
His face, hairstyle, hair colour, clothing and body must be identical in all 17 occupied cells — the same man, same age, same suit, same tie, same lighting. Only his expression and his pose change from cell to cell. The scar through his left eyebrow must be present in every cell where his face is visible.

QUALITY — this is the most important part after the layout:
Maximum image quality. Ultra-high resolution, at least 2048 x 4096 pixels. Clean, crisp, deliberate linework of an even weight, with no wobbling lines, no sketchy double lines and no stray marks. Soft cel shading — a few clear tonal steps plus gentle soft-edged gradients on the face and the fabric — lit evenly from the front with no dramatic rim light. A muted, desaturated palette of warm greys, dull navy, faded beige and soft earth tones, so that the figure sits naturally against a softly blurred, slightly darkened photographic background. Every cell is a fully finished, fully coloured drawing — not a sketch, not bare lineart, not a work in progress — and all 17 are finished to exactly the same standard.

DO NOT INCLUDE:
No text, no letters, no Hangul, no Korean characters, no numbers, no cell labels, no captions, no arrows, no logos, no brand marks, no watermark, no signature, no colour swatches, no ruler, no border around the outside of the image. No extra people. No props other than the plain chair in cell 15. No distorted hands, no extra fingers, no missing fingers, no duplicated limbs, no warped faces, no heavy black outline around the body.
```

---

## 차남·50대 남성 (M50B)  ·  `M50B.png`

```
Semi-realistic anime character sheet in the restrained style of a serious adult Korean television drama: 18 drawings of ONE Korean man, all drawn in one single consistent style, arranged in a strict grid of 3 columns across and 6 rows down, portrait orientation, overall aspect ratio 1:2. This is a hand-drawn semi-realistic anime illustration. Not a photograph, not photorealistic, not a 3D render, not CGI. Draw him with realistic adult body proportions of seven to eight heads tall and a face that reads his true age. Do NOT give him oversized eyes, do NOT make him look younger, cuter or prettier than described. No chibi, no moe, no shoujo sparkle, no glossy highlights in the eyes, no thick black outline around the body.

THE MAN — he must be the same identifiable individual in every single cell:
He is 51 years old, Korean, 175 cm, lean and slightly stooped. His face is long with a narrow jaw and a high, bare forehead. His black hair has thinned and receded well back at both temples, leaving the forehead broad and exposed, and what remains is kept short at the sides and back. His eyes are double-lidded and slightly prominent, with a restless, unsettled gaze. His eyebrows are thin and uneven and angle downwards at the outer ends. His nose is long and narrow with a slight hook at the bridge. His lips are thin, and one corner of his mouth sits habitually tighter than the other, giving his face a faintly lopsided set. His skin is sallow with a faint sheen across the forehead. He has two small dark moles on his right cheek, one just below the cheekbone and one nearer the jaw. He wears an olive green zip-up field jacket left unzipped and open, over a plain cream polo shirt, with dark brown trousers.

WHAT IS IN EACH CELL, reading left to right then top to bottom:
Cell 1 head-and-shoulders close-up, neutral expression. Cell 2 same close-up, sad. Cell 3 same close-up, angry. Cell 4 same close-up, shocked. Cell 5 same close-up, cold and unfeeling. Cell 6 same close-up, crying with tears on his cheeks. Cell 7 waist-up, neutral. Cell 8 waist-up, sad. Cell 9 waist-up, angry. Cell 10 waist-up, shocked. Cell 11 waist-up, cold. Cell 12 waist-up, crying. Cell 13 full body standing straight, facing the camera. Cell 14 full body mid-stride walking to the left. Cell 15 full body seated on a plain chair. Cell 16 full body seen from directly behind. Cell 17 full body sinking down to sit on the floor, knees folding. Cell 18 is COMPLETELY EMPTY — flat green only, absolutely no person, no object, no shadow, nothing at all.

BACKGROUND AND GRID — follow this exactly:
The background behind and around him in every cell is FLAT PURE CHROMA GREEN #00B140, perfectly even, with no gradient, no texture, no vignette. Separate the cells with straight lines of PURE MAGENTA #FF00FF about 12 pixels thick, drawn edge to edge across the whole image. Outside the man himself there are only two colours in the entire image: the chroma green #00B140 background and the magenta #FF00FF divider lines. Never draw a black, grey or white border, frame, outline or line anywhere. Do not draw a ground shadow, a cast shadow, or a contact shadow under his feet or anywhere else.

CONSISTENCY:
His face, hairline, clothing and body must be identical in all 17 occupied cells — the same man, same age, same jacket, same lighting. Only his expression and his pose change from cell to cell. His hairline must stay equally receded in every cell; do not give him more hair in any cell.

QUALITY — this is the most important part after the layout:
Maximum image quality. Ultra-high resolution, at least 2048 x 4096 pixels. Clean, crisp, deliberate linework of an even weight, with no wobbling lines, no sketchy double lines and no stray marks. Soft cel shading — a few clear tonal steps plus gentle soft-edged gradients on the face and the fabric — lit evenly from the front with no dramatic rim light. A muted, desaturated palette of warm greys, dull navy, faded beige and soft earth tones, so that the figure sits naturally against a softly blurred, slightly darkened photographic background. Every cell is a fully finished, fully coloured drawing — not a sketch, not bare lineart, not a work in progress — and all 17 are finished to exactly the same standard.

DO NOT INCLUDE:
No text, no letters, no Hangul, no Korean characters, no numbers, no cell labels, no captions, no arrows, no logos, no brand marks, no watermark, no signature, no colour swatches, no ruler, no border around the outside of the image. No extra people. No props other than the plain chair in cell 15. No distorted hands, no extra fingers, no missing fingers, no duplicated limbs, no warped faces, no heavy black outline around the body.
```

---

## 노모·70대 여성 (F70)  ·  `F70.png`

```
Semi-realistic anime character sheet in the restrained style of a serious adult Korean television drama: 18 drawings of ONE elderly Korean woman, all drawn in one single consistent style, arranged in a strict grid of 3 columns across and 6 rows down, portrait orientation, overall aspect ratio 1:2. This is a hand-drawn semi-realistic anime illustration. Not a photograph, not photorealistic, not a 3D render, not CGI. Draw her with realistic adult body proportions of seven to eight heads tall and a face that reads her true age. Do NOT give her oversized eyes, do NOT make her look younger, cuter or prettier than described. No chibi, no moe, no shoujo sparkle, no glossy highlights in the eyes, no thick black outline around the body.

THE WOMAN — she must be the same identifiable individual in every single cell:
She is 74 years old, Korean, 148 cm, small and frail with a visibly rounded, stooped upper back. Her face is small and round, deeply lined, with soft sunken cheeks. Her hair is short and tightly permed into small curls, completely silver white, and thin enough that a little scalp shows at the crown. Her eyes are small watery monolid eyes hooded by drooping upper lids, surrounded by heavy crow's feet. Her eyebrows are very sparse and pale. Her nose is small with a low bridge and a rounded tip. Her lips are thin and pressed slightly inward, with deep vertical lines running into them, and her chin protrudes a little. Her skin is pale with brown age spots across the temples and cheeks, and the skin of her neck and hands is crepey and loose. Her hands have prominent knuckles and raised veins. She wears a soft lilac light purple knitted button vest over a plain white blouse with a small pointed collar, with loose dark navy trousers, and a thin plain gold wedding band on her left hand.

WHAT IS IN EACH CELL, reading left to right then top to bottom:
Cell 1 head-and-shoulders close-up, neutral expression. Cell 2 same close-up, sad. Cell 3 same close-up, angry. Cell 4 same close-up, shocked. Cell 5 same close-up, cold and unfeeling. Cell 6 same close-up, crying with tears on her cheeks. Cell 7 waist-up, neutral. Cell 8 waist-up, sad. Cell 9 waist-up, angry. Cell 10 waist-up, shocked. Cell 11 waist-up, cold. Cell 12 waist-up, crying. Cell 13 full body standing, slightly stooped, facing the camera. Cell 14 full body mid-stride walking slowly to the left. Cell 15 full body seated on a plain chair. Cell 16 full body seen from directly behind. Cell 17 full body sinking down to sit on the floor, knees folding. Cell 18 is COMPLETELY EMPTY — flat green only, absolutely no person, no object, no shadow, nothing at all.

BACKGROUND AND GRID — follow this exactly:
The background behind and around her in every cell is FLAT PURE CHROMA GREEN #00B140, perfectly even, with no gradient, no texture, no vignette. Separate the cells with straight lines of PURE MAGENTA #FF00FF about 12 pixels thick, drawn edge to edge across the whole image. Outside the woman herself there are only two colours in the entire image: the chroma green #00B140 background and the magenta #FF00FF divider lines. Never draw a black, grey or white border, frame, outline or line anywhere. Do not draw a ground shadow, a cast shadow, or a contact shadow under her feet or anywhere else.

CONSISTENCY:
Her face, hairstyle, hair colour, clothing and body must be identical in all 17 occupied cells — the same woman, same age, same clothes, same lighting. Only her expression and her pose change from cell to cell. She must look 74 in every cell; do not make her younger, taller or straighter-backed in any cell.

QUALITY — this is the most important part after the layout:
Maximum image quality. Ultra-high resolution, at least 2048 x 4096 pixels. Clean, crisp, deliberate linework of an even weight, with no wobbling lines, no sketchy double lines and no stray marks. Soft cel shading — a few clear tonal steps plus gentle soft-edged gradients on the face and the fabric — lit evenly from the front with no dramatic rim light. A muted, desaturated palette of warm greys, dull navy, faded beige and soft earth tones, so that the figure sits naturally against a softly blurred, slightly darkened photographic background. Every cell is a fully finished, fully coloured drawing — not a sketch, not bare lineart, not a work in progress — and all 17 are finished to exactly the same standard.

DO NOT INCLUDE:
No text, no letters, no Hangul, no Korean characters, no numbers, no cell labels, no captions, no arrows, no logos, no brand marks, no watermark, no signature, no colour swatches, no ruler, no border around the outside of the image. No extra people. No props other than the plain chair in cell 15. No walking stick. No distorted hands, no extra fingers, no missing fingers, no duplicated limbs, no warped faces, no heavy black outline around the body.
```

---

## 노부·70대 남성 (M70)  ·  `M70.png`

```
Semi-realistic anime character sheet in the restrained style of a serious adult Korean television drama: 18 drawings of ONE elderly Korean man, all drawn in one single consistent style, arranged in a strict grid of 3 columns across and 6 rows down, portrait orientation, overall aspect ratio 1:2. This is a hand-drawn semi-realistic anime illustration. Not a photograph, not photorealistic, not a 3D render, not CGI. Draw him with realistic adult body proportions of seven to eight heads tall and a face that reads his true age. Do NOT give him oversized eyes, do NOT make him look younger, cuter or prettier than described. No chibi, no moe, no shoujo sparkle, no glossy highlights in the eyes, no thick black outline around the body.

THE MAN — he must be the same identifiable individual in every single cell:
He is 76 years old, Korean, 168 cm, very thin, with bony shoulders that his clothes hang loosely from. His face is long and narrow with hollow cheeks and prominent cheekbones. His hair is thin and white, combed flat to one side, receded at both temples. His eyes are deep-set monolid eyes beneath a heavy brow, with a calm, slow gaze and outer corners that droop downwards. His eyebrows are white and wiry with a few long stray hairs. His nose is long and thin with a bony bridge. His lips are thin and slightly sunken, with deep vertical lines around them. His skin is pale with liver spots on the forehead and on the backs of his hands, and the skin is loose along the jaw and neck. He wears a dark brown wool button cardigan over a plain white dress shirt buttoned all the way to the collar, with dark brown trousers. He wears no tie and no glasses.

WHAT IS IN EACH CELL, reading left to right then top to bottom:
Cell 1 head-and-shoulders close-up, neutral expression. Cell 2 same close-up, sad. Cell 3 same close-up, angry. Cell 4 same close-up, shocked. Cell 5 same close-up, cold and unfeeling. Cell 6 same close-up, crying with tears on his cheeks. Cell 7 waist-up, neutral. Cell 8 waist-up, sad. Cell 9 waist-up, angry. Cell 10 waist-up, shocked. Cell 11 waist-up, cold. Cell 12 waist-up, crying. Cell 13 full body standing, slightly stooped, facing the camera. Cell 14 full body mid-stride walking slowly to the left. Cell 15 full body seated on a plain chair. Cell 16 full body seen from directly behind. Cell 17 full body sinking down to sit on the floor, knees folding. Cell 18 is COMPLETELY EMPTY — flat green only, absolutely no person, no object, no shadow, nothing at all.

BACKGROUND AND GRID — follow this exactly:
The background behind and around him in every cell is FLAT PURE CHROMA GREEN #00B140, perfectly even, with no gradient, no texture, no vignette. Separate the cells with straight lines of PURE MAGENTA #FF00FF about 12 pixels thick, drawn edge to edge across the whole image. Outside the man himself there are only two colours in the entire image: the chroma green #00B140 background and the magenta #FF00FF divider lines. Never draw a black, grey or white border, frame, outline or line anywhere. Do not draw a ground shadow, a cast shadow, or a contact shadow under his feet or anywhere else.

CONSISTENCY:
His face, hairstyle, hair colour, clothing and body must be identical in all 17 occupied cells — the same man, same age, same cardigan, same lighting. Only his expression and his pose change from cell to cell. He must look 76 and equally thin in every cell.

QUALITY — this is the most important part after the layout:
Maximum image quality. Ultra-high resolution, at least 2048 x 4096 pixels. Clean, crisp, deliberate linework of an even weight, with no wobbling lines, no sketchy double lines and no stray marks. Soft cel shading — a few clear tonal steps plus gentle soft-edged gradients on the face and the fabric — lit evenly from the front with no dramatic rim light. A muted, desaturated palette of warm greys, dull navy, faded beige and soft earth tones, so that the figure sits naturally against a softly blurred, slightly darkened photographic background. Every cell is a fully finished, fully coloured drawing — not a sketch, not bare lineart, not a work in progress — and all 17 are finished to exactly the same standard.

DO NOT INCLUDE:
No text, no letters, no Hangul, no Korean characters, no numbers, no cell labels, no captions, no arrows, no logos, no brand marks, no watermark, no signature, no colour swatches, no ruler, no border around the outside of the image. No extra people. No props other than the plain chair in cell 15. No walking stick. No distorted hands, no extra fingers, no missing fingers, no duplicated limbs, no warped faces, no heavy black outline around the body.
```

---

## 재판장 (JUDGE)  ·  `JUDGE.png`

> ⚠️ 재판장은 **회차가 바뀌어도 얼굴을 바꾸지 않는다**(손님 지시). 같은 법정,
> 같은 재판장이 채널의 얼굴이다. 그래서 이 한 장이 오래 간다.
> 표정 6종은 다른 인물보다 **절제된 정도**로 시킨다 — 재판장이 오열하면 우습다.

```
Semi-realistic anime character sheet in the restrained style of a serious adult Korean television drama: 18 drawings of ONE Korean judge, all drawn in one single consistent style, arranged in a strict grid of 3 columns across and 6 rows down, portrait orientation, overall aspect ratio 1:2. This is a hand-drawn semi-realistic anime illustration. Not a photograph, not photorealistic, not a 3D render, not CGI. Draw him with realistic adult body proportions of seven to eight heads tall and a face that reads his true age. Do NOT give him oversized eyes, do NOT make him look younger, cuter or prettier than described. No chibi, no moe, no shoujo sparkle, no glossy highlights in the eyes, no thick black outline around the body.

THE JUDGE — he must be the same identifiable individual in every single cell:
He is a 53 year old Korean man, 174 cm, of average build and consistently upright, composed bearing. His face is broad and square with an even, controlled set. His hair is short, neatly combed back from the forehead, black with clear grey at both temples. His eyes are monolid with a steady, level, unhurried gaze that gives away very little. His eyebrows are thick, straight and dark. His nose is straight and of medium width. His lips are firm and held closed in a level line. His skin is an even medium tone, cleanly shaven, with fine lines across the forehead and at the outer corners of the eyes. He wears thin silver-rimmed rectangular glasses. He wears a Korean judicial robe: a plain black full-length robe with long wide sleeves, closed high at the neck, with a deep violet placket running down the centre front of the chest. A white shirt collar is just visible at the throat. He wears no other insignia and no jewellery.

WHAT IS IN EACH CELL, reading left to right then top to bottom. His expressions stay restrained and dignified throughout — a judge on the bench, never theatrical:
Cell 1 head-and-shoulders close-up, neutral. Cell 2 same close-up, quietly grave and sorrowful. Cell 3 same close-up, sternly displeased with the brows drawn down. Cell 4 same close-up, mildly taken aback, eyebrows slightly raised. Cell 5 same close-up, cool and impassive. Cell 6 same close-up, deeply moved, eyes glistening but composed and NOT weeping openly. Cell 7 waist-up, neutral. Cell 8 waist-up, grave. Cell 9 waist-up, stern. Cell 10 waist-up, taken aback. Cell 11 waist-up, impassive. Cell 12 waist-up, deeply moved but composed. Cell 13 full body standing straight, facing the camera. Cell 14 full body mid-stride walking to the left, robe moving slightly. Cell 15 full body seated on a plain chair, upright. Cell 16 full body seen from directly behind. Cell 17 full body seated and leaning forward with the head lowered. Cell 18 is COMPLETELY EMPTY — flat green only, absolutely no person, no object, no shadow, nothing at all.

BACKGROUND AND GRID — follow this exactly:
The background behind and around him in every cell is FLAT PURE CHROMA GREEN #00B140, perfectly even, with no gradient, no texture, no vignette. Separate the cells with straight lines of PURE MAGENTA #FF00FF about 12 pixels thick, drawn edge to edge across the whole image. Outside the man himself there are only two colours in the entire image: the chroma green #00B140 background and the magenta #FF00FF divider lines. Never draw a black, grey or white border, frame, outline or line anywhere. Do not draw a ground shadow, a cast shadow, or a contact shadow under his feet or anywhere else. His robe is black, but nothing outside his body may be black.

CONSISTENCY:
His face, hair, glasses, robe and build must be identical in all 17 occupied cells — the same man, same age, same robe, same lighting. Only his expression and his pose change from cell to cell.

QUALITY — this is the most important part after the layout:
Maximum image quality. Ultra-high resolution, at least 2048 x 4096 pixels. Clean, crisp, deliberate linework of an even weight, with no wobbling lines, no sketchy double lines and no stray marks. Soft cel shading — a few clear tonal steps plus gentle soft-edged gradients on the face and the fabric — lit evenly from the front with no dramatic rim light. A muted, desaturated palette of warm greys, dull navy, faded beige and soft earth tones, so that the figure sits naturally against a softly blurred, slightly darkened photographic background. Every cell is a fully finished, fully coloured drawing — not a sketch, not bare lineart, not a work in progress — and all 17 are finished to exactly the same standard.

DO NOT INCLUDE:
No text, no letters, no Hangul, no Korean characters, no numbers, no cell labels, no captions, no arrows, no logos, no brand marks, no national emblem, no court crest, no watermark, no signature, no colour swatches, no ruler, no border around the outside of the image. No gavel, no books, no desk. No extra people. No props other than the plain chair in cells 15 and 17. No distorted hands, no extra fingers, no missing fingers, no duplicated limbs, no warped faces, no heavy black outline around the body.
```
