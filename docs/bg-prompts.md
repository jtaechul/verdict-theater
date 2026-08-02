# 배경 이미지 생성 프롬프트 (제미나이용)

배경 18종. **각 블록을 그대로 복사해 제미나이에 붙여넣으면 바로 나온다.**
추가로 붙일 말은 없다 — 화면비·금지사항·화풍이 전부 블록 안에 들어 있다.

## 저장하는 법

나온 그림을 아래 파일 이름 그대로 저장해서 저장소의 `assets/bg/` 에 올린다.
오른쪽 아래 제미나이 로고는 **지우지 않아도 된다** — 영상 만들기 워크플로가
렌더링 직전에 자동으로 지운다(`src/dewatermark.py`).

## 왜 이런 조건이 붙어 있나

| 조건 | 이유 |
|---|---|
| 사람이 없어야 한다 | 인물은 컷아웃으로 따로 얹는다. 배경에 사람이 있으면 두 겹이 겹쳐 이상해진다 |
| 글자·간판·숫자 금지 | AI가 만든 한글은 깨져 나온다. 블러로 덮어도 티가 난다 |
| 가운데에 담아라 | 쇼츠(세로)는 **가운데만 잘라 쓴다.** 양옆에 중요한 것을 두면 잘려 나간다 |
| 낮은 채도·낮은 대비 | 배경은 흐리게 깔리고 78%로 어두워진다. 화려하면 인물과 자막이 묻힌다 |
| 16:9 | 렌더러가 가로 1920x1080 · 세로 1080x1920 양쪽으로 잘라 쓴다 |

---

## 법원 건물 외부  ·  `court_exterior.jpg`  (5컷에서 쓰임)

```
Photorealistic cinematic film still of the plaza and front steps of a plain civic courthouse — grey granite stairs, unadorned concrete columns, a bare flagpole, thin leafless trees, damp pavement in South Korea, present day. The place is completely empty — absolutely no people, no human figures, no silhouettes, no reflections of people. Eye-level 35mm lens, centred composition with the main subject held in the middle third of the frame so that a vertical centre-crop still reads correctly. Overcast winter daylight, flat and shadowless, cold blue-grey cast. Muted desaturated palette — warm greys, dull navy, faded beige; low contrast, slightly cool shadows, shallow depth of field with the far background softly out of focus. Quiet, melancholic, documentary mood. Lived-in and ordinary, never a showroom or a catalogue photo. No text, no letters, no Hangul, no Korean characters, no signage, no numbers, no logos, no brand marks, no watermark, no captions, no UI overlay, no borders, no frame, no collage, no split screen, no diptych. Not an illustration, not anime, not a 3D render, not CGI, not a painting. No distorted perspective, no warped straight lines, no melted furniture, no duplicated objects. High detail, natural film grain, 16:9 aspect ratio, at least 1920x1080.
```

## 법원 복도  ·  `court_hall.jpg`  (15컷에서 쓰임)

```
Photorealistic cinematic film still of a long corridor inside a courthouse — polished stone floor, a row of plain wooden doors down the right wall, empty steel-and-vinyl waiting benches along the left, tall windows at the far end in South Korea, present day. The place is completely empty — absolutely no people, no human figures, no silhouettes, no reflections of people. Eye-level 35mm lens, centred composition with the main subject held in the middle third of the frame so that a vertical centre-crop still reads correctly. Cold daylight pouring from the windows at the end of the corridor, long soft reflections on the floor. Muted desaturated palette — warm greys, dull navy, faded beige; low contrast, slightly cool shadows, shallow depth of field with the far background softly out of focus. Quiet, melancholic, documentary mood. Lived-in and ordinary, never a showroom or a catalogue photo. No text, no letters, no Hangul, no Korean characters, no signage, no numbers, no logos, no brand marks, no watermark, no captions, no UI overlay, no borders, no frame, no collage, no split screen, no diptych. Not an illustration, not anime, not a 3D render, not CGI, not a painting. No distorted perspective, no warped straight lines, no melted furniture, no duplicated objects. High detail, natural film grain, 16:9 aspect ratio, at least 1920x1080.
```

## 법정 내부  ·  `court_room.jpg`  (7컷에서 쓰임)

```
Photorealistic cinematic film still of the interior of a courtroom seen from the empty public gallery — a raised wooden judge's bench, a plain undecorated back wall with no emblem, dark wood panelling, two bare counsel tables, rows of empty seats in South Korea, present day. The place is completely empty — absolutely no people, no human figures, no silhouettes, no reflections of people. Eye-level 35mm lens, centred composition with the main subject held in the middle third of the frame so that a vertical centre-crop still reads correctly. Even cold overhead lighting, no strong shadows, slightly clinical. Muted desaturated palette — warm greys, dull navy, faded beige; low contrast, slightly cool shadows, shallow depth of field with the far background softly out of focus. Quiet, melancholic, documentary mood. Lived-in and ordinary, never a showroom or a catalogue photo. No text, no letters, no Hangul, no Korean characters, no signage, no numbers, no logos, no brand marks, no watermark, no captions, no UI overlay, no borders, no frame, no collage, no split screen, no diptych. Not an illustration, not anime, not a 3D render, not CGI, not a painting. No distorted perspective, no warped straight lines, no melted furniture, no duplicated objects. High detail, natural film grain, 16:9 aspect ratio, at least 1920x1080.
```

## 동네 카페  ·  `daily_cafe.jpg`  (6컷에서 쓰임)

```
Photorealistic cinematic film still of a small neighbourhood cafe — a worn wooden two-seat table by a wide window, two empty ceramic cups left behind, a potted plant on the sill, mismatched chairs in South Korea, present day. The place is completely empty — absolutely no people, no human figures, no silhouettes, no reflections of people. Eye-level 35mm lens, centred composition with the main subject held in the middle third of the frame so that a vertical centre-crop still reads correctly. Low afternoon sun coming through the window from the left, warm dusty light, soft haze. Muted desaturated palette — warm greys, dull navy, faded beige; low contrast, slightly cool shadows, shallow depth of field with the far background softly out of focus. Quiet, melancholic, documentary mood. Lived-in and ordinary, never a showroom or a catalogue photo. No text, no letters, no Hangul, no Korean characters, no signage, no numbers, no logos, no brand marks, no watermark, no captions, no UI overlay, no borders, no frame, no collage, no split screen, no diptych. Not an illustration, not anime, not a 3D render, not CGI, not a painting. No distorted perspective, no warped straight lines, no melted furniture, no duplicated objects. High detail, natural film grain, 16:9 aspect ratio, at least 1920x1080.
```

## 백반 식당  ·  `daily_restaurant.jpg`  (1컷에서 쓰임)

```
Photorealistic cinematic film still of a modest home-style Korean diner — a stainless steel table, small empty side-dish bowls, stacked plastic chairs, a steel water jug, an old tiled wall in South Korea, present day. The place is completely empty — absolutely no people, no human figures, no silhouettes, no reflections of people. Eye-level 35mm lens, centred composition with the main subject held in the middle third of the frame so that a vertical centre-crop still reads correctly. Flat fluorescent ceiling light, slightly green cast, everyday and unglamorous. Muted desaturated palette — warm greys, dull navy, faded beige; low contrast, slightly cool shadows, shallow depth of field with the far background softly out of focus. Quiet, melancholic, documentary mood. Lived-in and ordinary, never a showroom or a catalogue photo. No text, no letters, no Hangul, no Korean characters, no signage, no numbers, no logos, no brand marks, no watermark, no captions, no UI overlay, no borders, no frame, no collage, no split screen, no diptych. Not an illustration, not anime, not a 3D render, not CGI, not a painting. No distorted perspective, no warped straight lines, no melted furniture, no duplicated objects. High detail, natural film grain, 16:9 aspect ratio, at least 1920x1080.
```

## 영정이 놓인 제단 앞  ·  `funeral_altar.jpg`  (1컷에서 쓰임)

```
Photorealistic cinematic film still of the altar of a funeral hall — banks of white chrysanthemums, a dark framed portrait standing on the altar that is deliberately far out of focus and completely unreadable with no discernible face, black-and-white mourning ribbon, a brass incense burner with thin smoke in South Korea, present day. The place is completely empty — absolutely no people, no human figures, no silhouettes, no reflections of people. Eye-level 35mm lens, centred composition with the main subject held in the middle third of the frame so that a vertical centre-crop still reads correctly. Dim warm tungsten light falling from above onto the flowers, deep soft shadows around the edges. Muted desaturated palette — warm greys, dull navy, faded beige; low contrast, slightly cool shadows, shallow depth of field with the far background softly out of focus. Quiet, melancholic, documentary mood. Lived-in and ordinary, never a showroom or a catalogue photo. No text, no letters, no Hangul, no Korean characters, no signage, no numbers, no logos, no brand marks, no watermark, no captions, no UI overlay, no borders, no frame, no collage, no split screen, no diptych. Not an illustration, not anime, not a 3D render, not CGI, not a painting. No distorted perspective, no warped straight lines, no melted furniture, no duplicated objects. High detail, natural film grain, 16:9 aspect ratio, at least 1920x1080.
```

## 장례식장 긴 복도  ·  `funeral_hall.jpg`  (3컷에서 쓰임)

```
Photorealistic cinematic film still of a long corridor of a funeral hall — closed doors on both sides with small blank nameplate boards, muted carpet, low warm wall sconces, a folded partition screen at the end in South Korea, present day. The place is completely empty — absolutely no people, no human figures, no silhouettes, no reflections of people. Eye-level 35mm lens, centred composition with the main subject held in the middle third of the frame so that a vertical centre-crop still reads correctly. Dim warm sconce light, pools of light and shadow alternating down the corridor. Muted desaturated palette — warm greys, dull navy, faded beige; low contrast, slightly cool shadows, shallow depth of field with the far background softly out of focus. Quiet, melancholic, documentary mood. Lived-in and ordinary, never a showroom or a catalogue photo. No text, no letters, no Hangul, no Korean characters, no signage, no numbers, no logos, no brand marks, no watermark, no captions, no UI overlay, no borders, no frame, no collage, no split screen, no diptych. Not an illustration, not anime, not a 3D render, not CGI, not a painting. No distorted perspective, no warped straight lines, no melted furniture, no duplicated objects. High detail, natural film grain, 16:9 aspect ratio, at least 1920x1080.
```

## 밤의 주차장  ·  `funeral_parking.jpg`  (2컷에서 쓰임)

```
Photorealistic cinematic film still of an outdoor parking lot behind a funeral hall at night — wet asphalt reflecting orange sodium lamps, a few parked sedans, a low painted kerb, bare trees at the edge in South Korea, present day. The place is completely empty — absolutely no people, no human figures, no silhouettes, no reflections of people. Eye-level 35mm lens, centred composition with the main subject held in the middle third of the frame so that a vertical centre-crop still reads correctly. Night. Orange sodium lamps overhead against a deep blue-black sky, strong reflections on wet ground. Muted desaturated palette — warm greys, dull navy, faded beige; low contrast, slightly cool shadows, shallow depth of field with the far background softly out of focus. Quiet, melancholic, documentary mood. Lived-in and ordinary, never a showroom or a catalogue photo. No text, no letters, no Hangul, no Korean characters, no signage, no numbers, no logos, no brand marks, no watermark, no captions, no UI overlay, no borders, no frame, no collage, no split screen, no diptych. Not an illustration, not anime, not a 3D render, not CGI, not a painting. No distorted perspective, no warped straight lines, no melted furniture, no duplicated objects. High detail, natural film grain, 16:9 aspect ratio, at least 1920x1080.
```

## 접객실  ·  `funeral_reception.jpg`  (3컷에서 쓰임)

```
Photorealistic cinematic film still of the reception room of a funeral hall — long low tables in rows, flat floor cushions, cleared paper cups and empty soup bowls stacked at one end, sliding paper-panel doors in South Korea, present day. The place is completely empty — absolutely no people, no human figures, no silhouettes, no reflections of people. Eye-level 35mm lens, centred composition with the main subject held in the middle third of the frame so that a vertical centre-crop still reads correctly. Dim warm ceiling light, slightly yellow, heavy quiet air. Muted desaturated palette — warm greys, dull navy, faded beige; low contrast, slightly cool shadows, shallow depth of field with the far background softly out of focus. Quiet, melancholic, documentary mood. Lived-in and ordinary, never a showroom or a catalogue photo. No text, no letters, no Hangul, no Korean characters, no signage, no numbers, no logos, no brand marks, no watermark, no captions, no UI overlay, no borders, no frame, no collage, no split screen, no diptych. Not an illustration, not anime, not a 3D render, not CGI, not a painting. No distorted perspective, no warped straight lines, no melted furniture, no duplicated objects. High detail, natural film grain, 16:9 aspect ratio, at least 1920x1080.
```

## 옷장 앞  ·  `home_closet.jpg`  (5컷에서 쓰임)

```
Photorealistic cinematic film still of a bedroom of a modest older apartment, in front of an old wooden wardrobe — one door ajar, folded blankets on the top shelf, a stack of old paper documents and a shoebox pulled out onto the floor in South Korea, present day. The place is completely empty — absolutely no people, no human figures, no silhouettes, no reflections of people. Eye-level 35mm lens, centred composition with the main subject held in the middle third of the frame so that a vertical centre-crop still reads correctly. Weak late-afternoon light through a half-closed curtain from the left, dusty and dim. Muted desaturated palette — warm greys, dull navy, faded beige; low contrast, slightly cool shadows, shallow depth of field with the far background softly out of focus. Quiet, melancholic, documentary mood. Lived-in and ordinary, never a showroom or a catalogue photo. No text, no letters, no Hangul, no Korean characters, no signage, no numbers, no logos, no brand marks, no watermark, no captions, no UI overlay, no borders, no frame, no collage, no split screen, no diptych. Not an illustration, not anime, not a 3D render, not CGI, not a painting. No distorted perspective, no warped straight lines, no melted furniture, no duplicated objects. High detail, natural film grain, 16:9 aspect ratio, at least 1920x1080.
```

## 현관  ·  `home_entrance.jpg`  (1컷에서 쓰임)

```
Photorealistic cinematic film still of the small entryway of an old apartment — a low shoe rack with one pair of worn shoes, a coat hook on the wall, a heavy steel front door, a tiled step down in South Korea, present day. The place is completely empty — absolutely no people, no human figures, no silhouettes, no reflections of people. Eye-level 35mm lens, centred composition with the main subject held in the middle third of the frame so that a vertical centre-crop still reads correctly. Dim indoor light with a thin bright edge leaking around the door frame. Muted desaturated palette — warm greys, dull navy, faded beige; low contrast, slightly cool shadows, shallow depth of field with the far background softly out of focus. Quiet, melancholic, documentary mood. Lived-in and ordinary, never a showroom or a catalogue photo. No text, no letters, no Hangul, no Korean characters, no signage, no numbers, no logos, no brand marks, no watermark, no captions, no UI overlay, no borders, no frame, no collage, no split screen, no diptych. Not an illustration, not anime, not a 3D render, not CGI, not a painting. No distorted perspective, no warped straight lines, no melted furniture, no duplicated objects. High detail, natural film grain, 16:9 aspect ratio, at least 1920x1080.
```

## 부엌  ·  `home_kitchen.jpg`  (7컷에서 쓰임)

```
Photorealistic cinematic film still of the small kitchen of an older apartment — dated tiled backsplash, a kettle on a two-burner gas stove, a small dining table with two mismatched chairs, a drying rack of dishes in South Korea, present day. The place is completely empty — absolutely no people, no human figures, no silhouettes, no reflections of people. Eye-level 35mm lens, centred composition with the main subject held in the middle third of the frame so that a vertical centre-crop still reads correctly. Soft morning light through a narrow window above the sink, warm and gentle. Muted desaturated palette — warm greys, dull navy, faded beige; low contrast, slightly cool shadows, shallow depth of field with the far background softly out of focus. Quiet, melancholic, documentary mood. Lived-in and ordinary, never a showroom or a catalogue photo. No text, no letters, no Hangul, no Korean characters, no signage, no numbers, no logos, no brand marks, no watermark, no captions, no UI overlay, no borders, no frame, no collage, no split screen, no diptych. Not an illustration, not anime, not a 3D render, not CGI, not a painting. No distorted perspective, no warped straight lines, no melted furniture, no duplicated objects. High detail, natural film grain, 16:9 aspect ratio, at least 1920x1080.
```

## 낮의 거실  ·  `home_living_day.jpg`  (30컷에서 쓰임)

```
Photorealistic cinematic film still of the living room of a modest older apartment in daytime — a worn fabric sofa, a low wooden table, a folded blanket, an old flat television on a low stand, patterned wallpaper, a wall clock in South Korea, present day. The place is completely empty — absolutely no people, no human figures, no silhouettes, no reflections of people. Eye-level 35mm lens, centred composition with the main subject held in the middle third of the frame so that a vertical centre-crop still reads correctly. Bright but soft daylight through a wide window on the left, gentle falloff into the corners. Muted desaturated palette — warm greys, dull navy, faded beige; low contrast, slightly cool shadows, shallow depth of field with the far background softly out of focus. Quiet, melancholic, documentary mood. Lived-in and ordinary, never a showroom or a catalogue photo. No text, no letters, no Hangul, no Korean characters, no signage, no numbers, no logos, no brand marks, no watermark, no captions, no UI overlay, no borders, no frame, no collage, no split screen, no diptych. Not an illustration, not anime, not a 3D render, not CGI, not a painting. No distorted perspective, no warped straight lines, no melted furniture, no duplicated objects. High detail, natural film grain, 16:9 aspect ratio, at least 1920x1080.
```

## 밤의 거실  ·  `home_living_night.jpg`  (4컷에서 쓰임)

```
Photorealistic cinematic film still of the same kind of living room at night — a worn fabric sofa, a low wooden table, curtains drawn, an old television switched off in South Korea, present day. The place is completely empty — absolutely no people, no human figures, no silhouettes, no reflections of people. Eye-level 35mm lens, centred composition with the main subject held in the middle third of the frame so that a vertical centre-crop still reads correctly. Night. Only a single floor lamp in the corner, deep warm pools of light and large soft shadows. Muted desaturated palette — warm greys, dull navy, faded beige; low contrast, slightly cool shadows, shallow depth of field with the far background softly out of focus. Quiet, melancholic, documentary mood. Lived-in and ordinary, never a showroom or a catalogue photo. No text, no letters, no Hangul, no Korean characters, no signage, no numbers, no logos, no brand marks, no watermark, no captions, no UI overlay, no borders, no frame, no collage, no split screen, no diptych. Not an illustration, not anime, not a 3D render, not CGI, not a painting. No distorted perspective, no warped straight lines, no melted furniture, no duplicated objects. High detail, natural film grain, 16:9 aspect ratio, at least 1920x1080.
```

## 1인 병실  ·  `medical_room_single.jpg`  (3컷에서 쓰임)

```
Photorealistic cinematic film still of a single-occupancy hospital room — one empty adjustable bed with crisp white linen, an IV stand, a bedside cabinet with a water cup, a window with thin horizontal blinds in South Korea, present day. The place is completely empty — absolutely no people, no human figures, no silhouettes, no reflections of people. Eye-level 35mm lens, centred composition with the main subject held in the middle third of the frame so that a vertical centre-crop still reads correctly. Pale cold daylight through the blinds casting soft stripes, clinical and quiet. Muted desaturated palette — warm greys, dull navy, faded beige; low contrast, slightly cool shadows, shallow depth of field with the far background softly out of focus. Quiet, melancholic, documentary mood. Lived-in and ordinary, never a showroom or a catalogue photo. No text, no letters, no Hangul, no Korean characters, no signage, no numbers, no logos, no brand marks, no watermark, no captions, no UI overlay, no borders, no frame, no collage, no split screen, no diptych. Not an illustration, not anime, not a 3D render, not CGI, not a painting. No distorted perspective, no warped straight lines, no melted furniture, no duplicated objects. High detail, natural film grain, 16:9 aspect ratio, at least 1920x1080.
```

## 은행 창구  ·  `office_bank.jpg`  (4컷에서 쓰임)

```
Photorealistic cinematic film still of the teller counter area of a bank branch — a low counter with a glass partition, empty customer chairs, a queue-ticket machine with a completely blank dark display, a rope stanchion in South Korea, present day. The place is completely empty — absolutely no people, no human figures, no silhouettes, no reflections of people. Eye-level 35mm lens, centred composition with the main subject held in the middle third of the frame so that a vertical centre-crop still reads correctly. Even cool fluorescent lighting, slightly blue, flat and impersonal. Muted desaturated palette — warm greys, dull navy, faded beige; low contrast, slightly cool shadows, shallow depth of field with the far background softly out of focus. Quiet, melancholic, documentary mood. Lived-in and ordinary, never a showroom or a catalogue photo. No text, no letters, no Hangul, no Korean characters, no signage, no numbers, no logos, no brand marks, no watermark, no captions, no UI overlay, no borders, no frame, no collage, no split screen, no diptych. Not an illustration, not anime, not a 3D render, not CGI, not a painting. No distorted perspective, no warped straight lines, no melted furniture, no duplicated objects. High detail, natural film grain, 16:9 aspect ratio, at least 1920x1080.
```

## 변호사 사무실  ·  `office_lawyer.jpg`  (12컷에서 쓰임)

```
Photorealistic cinematic film still of a small law office — a dark wooden desk with neat stacks of paper, shelves of thick unlabelled binders with blank spines, a worn leather chair, a window with half-closed blinds in South Korea, present day. The place is completely empty — absolutely no people, no human figures, no silhouettes, no reflections of people. Eye-level 35mm lens, centred composition with the main subject held in the middle third of the frame so that a vertical centre-crop still reads correctly. Warm desk lamp light mixed with cool daylight through the blinds, strong directional shadows. Muted desaturated palette — warm greys, dull navy, faded beige; low contrast, slightly cool shadows, shallow depth of field with the far background softly out of focus. Quiet, melancholic, documentary mood. Lived-in and ordinary, never a showroom or a catalogue photo. No text, no letters, no Hangul, no Korean characters, no signage, no numbers, no logos, no brand marks, no watermark, no captions, no UI overlay, no borders, no frame, no collage, no split screen, no diptych. Not an illustration, not anime, not a 3D render, not CGI, not a painting. No distorted perspective, no warped straight lines, no melted furniture, no duplicated objects. High detail, natural film grain, 16:9 aspect ratio, at least 1920x1080.
```

## 등기소 창구  ·  `office_registry.jpg`  (5컷에서 쓰임)

```
Photorealistic cinematic film still of the public counter of a government registry office — a plain laminate counter, trays of blank unprinted forms, a pen on a chain, rows of plastic waiting chairs behind in South Korea, present day. The place is completely empty — absolutely no people, no human figures, no silhouettes, no reflections of people. Eye-level 35mm lens, centred composition with the main subject held in the middle third of the frame so that a vertical centre-crop still reads correctly. Flat fluorescent ceiling light, neutral and bureaucratic, no atmosphere. Muted desaturated palette — warm greys, dull navy, faded beige; low contrast, slightly cool shadows, shallow depth of field with the far background softly out of focus. Quiet, melancholic, documentary mood. Lived-in and ordinary, never a showroom or a catalogue photo. No text, no letters, no Hangul, no Korean characters, no signage, no numbers, no logos, no brand marks, no watermark, no captions, no UI overlay, no borders, no frame, no collage, no split screen, no diptych. Not an illustration, not anime, not a 3D render, not CGI, not a painting. No distorted perspective, no warped straight lines, no melted furniture, no duplicated objects. High detail, natural film grain, 16:9 aspect ratio, at least 1920x1080.
```
