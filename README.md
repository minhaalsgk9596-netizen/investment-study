# 투자 스터디

한·미 매크로, 시황, AI 섹터, 보조지표 매수 기준을 공부하는 사이트와 주간 발표 슬라이드.

| 페이지 | 내용 | 갱신 방식 |
|---|---|---|
| `index.html` 대시보드 | 지수·환율·금리·매크로 카드, AI 종목 성과, 체크리스트 점수 | 자동 (평일 2회) |
| `macro.html` 매크로 | 미국 물가·금리·장단기 금리차·고용, 한국 금리·물가, 환율 차트와 해설 | 자동 + 주간 글 |
| `market.html` 시황·뉴스 | 주간 시황, 핵심 뉴스, 기간별 수익률, 일정 | 주간 글 |
| `ai.html` AI 섹터 | 밸류체인, 테마, 종목 PER·성과·점수 | 자동 + 주간 글 |
| `indicators.html` 보조지표 | 이평선·RSI·볼린저·MACD·스토캐스틱·OBV·ATR 강의, 실차트, 매수 체크리스트, 백테스트 | 자동 |
| `learn.html` 더 공부하기 | 밸류에이션, 실적, 수급, 통화정책, 리스크 관리(포지션 계산기), 로드맵, 용어집 | 정적 |
| `slides.html` 발표 | 위 내용을 12장으로 자동 구성 (S: 발표자 노트, `?print-pdf`: PDF 저장) | 자동 |

## 구조
- `scripts/fetch_data.py`: Yahoo Finance(시세 5년), FRED(미국 매크로), 한국은행 ECOS(한국 금리·CPI)에서 받아 `data/` 에 저장
- `scripts/indicators.py`: 보조지표, 신호, 매수 체크리스트 점수, 백테스트 계산 → `data/signals.json`, `data/indicators/`
- `content/weekly/`: 매주 Claude 루틴이 쓰는 글(JSON). 작성 지침은 `content/ROUTINE_PROMPT.md`
- `docs/`: 화면(HTML/CSS/JS). 빌드 단계 없음
- `.github/workflows/update-data.yml`: 데이터 수집 → Pages 배포 (평일 07:30·16:30 KST, content 푸시 시)

## 로컬에서 보기
`serve.bat` 더블클릭 (데이터가 없으면 먼저 `python scripts/fetch_data.py && python scripts/indicators.py`).

## 선택 설정
- 한국은행 ECOS API 키(무료 발급)를 GitHub 저장소 Settings → Secrets → `ECOS_API_KEY` 로 넣으면 한국 데이터를 한 번에 받습니다. 없어도 공개 sample 키로 동작합니다.
- 관심 종목 추가: `scripts/fetch_data.py` 의 `TICKERS` 에 `"심볼": ("이름", "ai")` 형식으로 추가 (한국 주식은 `005930.KS`, 코스닥은 `.KQ`).

학습용 자료이며 투자 권유가 아닙니다.
