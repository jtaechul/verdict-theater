# 폰트 두는 곳

여기 있는 폰트를 **영상이 자동으로 씁니다.** 파일을 지우면 서버 기본 나눔 폰트로 돌아갑니다.

## 지금 쓰는 폰트 — KoPub Pro (한국출판인회의, 상업적 사용 무료)

| 파일 | 쓰는 곳 |
|---|---|
| `KoPub_Dotum_Pro_Bold.otf` | 자막 · 금액 숫자 |
| `KoPub_Dotum_Pro_Medium.otf` | 인물 이름표 · 작은 라벨 |
| `KoPub_Dotum_Pro_Light.otf` | 설명 보조 글자 |
| `KoPub_Batang_Pro_Bold.otf` | 회상 시점 자막 · 판결 · 제목 |
| `KoPub_Batang_Pro_Medium.otf` | 예비 |
| `KoPub_Batang_Pro_Light.otf` | 예비 |

- 파일 이름의 **띄어쓰기·밑줄·대소문자는 상관없습니다.**
  `KoPub_Dotum_Pro_Bold.otf` 도 `KoPubWorld Dotum Bold.ttf` 도 똑같이 인식합니다.
- 일부만 있어도 됩니다. 없는 것은 나눔으로 채웁니다.
- 어떤 역할에 어떤 폰트가 잡혔는지 확인: `python3 src/graphics.py`

## 긴 영상 썸네일 글씨 — Black Han Sans (SIL 오픈 폰트 라이선스 · 상업적 사용 무료)

| 파일 | 쓰는 곳 |
|---|---|
| `BlackHanSans-Regular.ttf` | 긴 영상 썸네일 큰 글 · 이름표 (`tools/drama60.py` 의 `thumb_vs`) |
| `OFL_BlackHanSans.txt` | 라이선스 전문 (폰트와 함께 둔다) |

- 2026-10-07 손님: "썸네일 보고도 아무도 안누른다." 굵은 썸네일 전용 글씨로 바꿨다.
  폰 목록 크기(가로 360·168px)에서도 두 줄이 읽혀야 한다.
- 이 파일이 없으면 썸네일 만들기가 멈춘다 (가는 나눔으로 몰래 바꾸지 않는다 — 목록에서 안 보인다).
