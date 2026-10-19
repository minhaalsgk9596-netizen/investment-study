# 주간 투자 스터디 글 작성 루틴

이 저장소는 투자 스터디 사이트다(GitHub Pages). 매주 이 지시에 따라 `content/weekly/` 에 이번 주 글을 쓰고 main 에 푸시한다. 푸시하면 GitHub Actions 가 자동으로 사이트와 발표 슬라이드를 다시 배포한다.

## 1. 숫자 확보 (지어내지 말 것)
1. `pip install -r scripts/requirements.txt` 후 `python scripts/fetch_data.py && python scripts/indicators.py` 를 실행해 `data/` 를 만든다.
2. 실패하면 배포된 사이트의 `data/market.json`, `data/macro.json`, `data/signals.json` 을 읽는다.
3. 글에 넣는 지수·등락률·금리·환율·CPI 같은 수치는 **반드시 이 데이터나 검색한 기사에 실제로 있는 값**만 쓴다. 기사끼리 수치가 다르면 data 값을 우선한다.

## 2. 조사 (웹 검색)
- 이번 주(직전 월~금) 한국·미국 증시 시황: 큰 움직임의 원인
- 매크로: 물가·고용 지표 발표 결과(예상치 대비), 연준·한국은행 발언과 결정, 유가·환율
- AI 섹터: 빅테크 실적·CapEx, 엔비디아·반도체·메모리(HBM) 뉴스, AI 기업 매출·자금조달
- 전력 인프라: LS일렉트릭·HD현대일렉트릭·효성중공업·LS(전선)·대한전선의 수주·실적·증설 공시, 미국 전력망·데이터센터 전력 뉴스, 변압기 리드타임·가격, 구리 가격, 관세·전력망 정책(미국 232조·반덤핑, 한국 전력망 특별법·HVDC), 800V DC 등 기술 동향
- 다음 주 일정: FOMC·금통위·CPI·고용·주요 실적 발표 (날짜는 확인된 것만, 불확실하면 "날짜 확인 필요")
- 출처는 Bloomberg, Reuters, CNBC, WSJ, 연합뉴스, 한국경제, 매일경제, 기업 IR, 연준·한은·BLS 원문을 우선한다.

## 3. 파일 쓰기
`content/weekly/YYYY-MM-DD.json`(작성일)을 만들고, 같은 내용을 `content/weekly/latest.json` 에 덮어쓰고, `content/weekly/index.json` 배열 **맨 앞**에 `{date, week, headline}` 를 추가한다.
스키마는 기존 파일(`content/weekly/2026-10-18.json`)과 **완전히 같게** 유지한다.

```
date, week, headline, one_liner,
market_summary: [{title, body}] (3개: 한국 / 미국 / 매크로),
macro_view: {summary, points[] (3~5개)},
news: [{title, source, url, why_it_matters}] (6~10개, url 필수, 실제 기사 링크),
ai_sector: {summary, themes: [{title, body}] (3~4개), winners_losers, risks[], watch[]},
power_sector: {summary, themes: [{title, body}] (2~3개), ls_electric (LS일렉트릭 이번 주 이슈 1~2문장), risks[], watch[]},
calendar: [{date, event, why}] (4~7개),
study_questions: [] (4~5개, 이번 주 사건과 보조지표/매크로 학습을 연결),
slides: {one_liner, key_points[] (4~5개, 짧게), deep_dive_indicator}
```
- `deep_dive_indicator` 는 `rsi`, `ma`, `bb`, `macd`, `stoch` 중 하나. 지난주와 다른 것을 고르되, 이번 주 시장 상황과 연결되는 지표를 고른다 (예: 급락장 → rsi, 박스권 → bb).
- `power_sector` 의 수주 금액·실적 수치는 공시나 기사에 나온 값만 쓰고, 이번 주 특별한 소식이 없으면 그렇다고 쓴다. 전력 인프라 종목 등락률은 data/market.json 의 group "power" 값을 쓴다.
- 한국어, 스터디원이 이해하기 쉬운 문장으로 쓴다. 전문용어는 처음 나올 때 짧게 풀어 쓴다.
- 특정 종목 매수·매도 권유 표현("사라", "목표가")은 쓰지 않는다.

## 4. 검증 후 푸시
- `python -c "import json;[json.load(open(f,encoding='utf-8')) for f in ['content/weekly/latest.json','content/weekly/index.json']]"` 로 JSON 이 깨지지 않았는지 확인한다.
- `git add content/weekly && git commit -m "weekly: YYYY-MM-DD" && git push origin main`
- `data/` 는 커밋하지 않는다(.gitignore).
