# 배경음악 생성 프롬프트 (제미나이용)

빠진 2곡. **각 블록을 그대로 복사해 제미나이에 붙여넣으면 바로 나온다.**
추가로 붙일 말은 없다 — 분위기·악기·빠르기·길이·금지사항이 전부 블록 안에 들어 있다.

## 나온 음악을 어떻게 넘기나

나온 파일을 **대화창에 그대로 보내면 된다.** 이름을 바꿀 필요도, 어디에 올릴
필요도 없다 — 저장소에 넣는 일은 클로드가 한다. `care` 인지 `verdict` 인지만
알려주면 된다.

## ⭐ 이 두 곡이 지켜야 하는 것 (왜 이런 조건이 붙어 있나)

우리 영상은 **말이 주인공**이다. 음악은 대사 밑에 **−36dB**로 깔린다
(`render.TARGET_DB`) — 목소리(−16dB)보다 20dB 아래, 사람 귀에는 "있는 줄은
알지만 무슨 곡인지는 모르는" 크기다.

| 조건 | 이유 |
|---|---|
| **선율이 뚜렷하면 안 된다** | 귀가 멜로디를 따라가면 대사를 놓친다 |
| **박자·드럼 금지** | 규칙적인 타격음은 작게 깔아도 말을 뚫고 올라온다 |
| **사람 목소리 금지** | 배우 목소리와 싸운다. 허밍도 안 된다 |
| **큰 변화·클라이맥스 금지** | 갑자기 커지면 그 순간 대사가 묻힌다 |
| **2~3분 이상** | 45초 미만이면 한 장면에서 여러 번 되풀이돼 티가 난다 |
| **시작·끝이 조용해야** | 장면 경계에서 뚝 끊기지 않는다 |

> ⚠️ 짧게 나오면 다시 요청하십시오. **45초 미만은 못 씁니다.** 2~3분이 가장 좋습니다.
> (자동으로 받아오는 길도 있습니다 — 「소리·음악 받아오기」 → '배경음악 — 빠진 것만 받기', 0원)

---

## 보살핌  ·  `care.mp3`

> 쓰이는 곳: 아픈 부모를 간병하는 장면, 가족이 곁을 지키는 장면, 조용히 손을
> 잡아 주는 장면. 슬프되 절망은 아니고, **따뜻하게 버티는** 느낌이어야 한다.

```
Compose a 3 minute instrumental background music track for a quiet Korean family drama, to play very softly underneath spoken dialogue. Mood: tender, warm, patient, quietly sad but never despairing — the feeling of someone sitting at a sick parent's bedside through the night, holding their hand and staying. Instrumentation: a solo felt piano playing long sustained single notes with a great deal of space and silence between them, supported by a very soft sustained string pad underneath, and nothing else. Tempo about 56 BPM, very slow, no rhythmic pulse. Key of C major drifting occasionally into A minor. Dynamics stay almost completely flat and quiet throughout at a soft mezzo-piano level. IMPORTANT — this music sits 20 decibels underneath a speaking voice, so it must never compete with speech: no clear or memorable melody that the ear wants to follow, no drums, no percussion of any kind, no rhythmic pulse, no bass line, no vocals, no humming, no choir, no sound effects, no build-up, no climax, no dramatic swell, no sudden change in volume or instrumentation, no key change. The whole three minutes should feel like one continuous unchanging moment. Begin from silence with a gentle two second fade in, and end with a gentle four second fade out, so it can be laid under a scene without a hard edge. Make it loop cleanly if repeated. Output as a stereo audio file, 44.1 kHz, consistent loudness with no clipping and no silence gaps in the middle. Do not add any spoken introduction, title announcement, or narration to the audio.
```

---

## 선고  ·  `verdict.mp3`

> 쓰이는 곳: 재판장이 판결을 읽는 순간, 결과가 정해지는 순간. 승리도 비극도
> 아니다 — **되돌릴 수 없다는 무게**만 있어야 한다.

```
Compose a 3 minute instrumental background music track for a Korean courtroom drama, to play very softly underneath a judge reading out a verdict. Mood: solemn, grave, still, weighted — the feeling of a decision that cannot be taken back. It is neither triumphant nor tragic; it simply carries weight. Instrumentation: low sustained cello and double bass holding long slow notes, with a very faint low piano note struck occasionally and allowed to ring out and decay, plus a barely audible low drone underneath, and nothing else. Tempo about 48 BPM, extremely slow, no rhythmic pulse. Key of D minor, harmonically static, resting on the same chord for long stretches without resolving. Dynamics stay flat and restrained throughout at a soft level, dark in tone but never muddy. IMPORTANT — this music sits 20 decibels underneath a speaking voice, so it must never compete with speech: no clear or memorable melody that the ear wants to follow, no drums, no timpani, no percussion of any kind, no cymbal swells, no rhythmic pulse, no brass stabs, no vocals, no choir, no sound effects, no build-up, no climax, no dramatic crescendo, no sudden change in volume or instrumentation, no resolution into a major chord at the end. The whole three minutes should feel like one held breath. Begin from silence with a gentle two second fade in, and end with a gentle four second fade out, so it can be laid under a scene without a hard edge. Make it loop cleanly if repeated. Output as a stereo audio file, 44.1 kHz, consistent loudness with no clipping and no silence gaps in the middle. Do not add any spoken introduction, title announcement, or narration to the audio.
```

---

## 이미 있는 6곡 (참고 — 새로 뽑지 않아도 된다)

`hook`(도입 긴장) · `past`(회상) · `reveal`(드러남) · `conflict`(갈등)
· `court`(법정) · `outro`(마무리)

같은 규칙으로 만들어져 있다. 나중에 어느 한 곡이 마음에 안 들면 위 두 블록을
본떠서 그 곡의 분위기만 바꿔 쓰면 된다.
