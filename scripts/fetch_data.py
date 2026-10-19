"""시세·매크로 데이터를 수집해 data/*.json 으로 저장한다.

- 가격(5년 일봉): yfinance (지수, 환율, 원자재, AI·전력 인프라 종목) → data/prices/<심볼>.json, data/market.json
- 매크로: FRED 공개 CSV (API 키 불필요) → data/macro.json
- 한국 기준금리·CPI: 한국은행 ECOS (ECOS_API_KEY 없으면 공개 sample 키 사용)
"""
from __future__ import annotations

import io
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PRICES = DATA / "prices"
KST = timezone(timedelta(hours=9))

# group: index | fx | rate | commodity | ai | power
TICKERS = {
    "^KS11": ("KOSPI", "index"),
    "^KQ11": ("KOSDAQ", "index"),
    "^GSPC": ("S&P 500", "index"),
    "^IXIC": ("나스닥", "index"),
    "^SOX": ("필라델피아 반도체", "index"),
    "^VIX": ("VIX (공포지수)", "index"),
    "KRW=X": ("원/달러 환율", "fx"),
    "DX-Y.NYB": ("달러 인덱스", "fx"),
    "^TNX": ("미 10년물 금리", "rate"),
    "GC=F": ("금", "commodity"),
    "CL=F": ("WTI 원유", "commodity"),
    "HG=F": ("구리", "commodity"),
    "NVDA": ("엔비디아", "ai"),
    "MSFT": ("마이크로소프트", "ai"),
    "GOOGL": ("알파벳", "ai"),
    "META": ("메타", "ai"),
    "AMZN": ("아마존", "ai"),
    "AVGO": ("브로드컴", "ai"),
    "TSM": ("TSMC", "ai"),
    "AMD": ("AMD", "ai"),
    "005930.KS": ("삼성전자", "ai"),
    "000660.KS": ("SK하이닉스", "ai"),
    "010120.KS": ("LS일렉트릭", "power"),
    "267260.KS": ("HD현대일렉트릭", "power"),
    "298040.KS": ("효성중공업", "power"),
    "006260.KS": ("LS", "power"),
    "001440.KS": ("대한전선", "power"),
}

# AI 밸류체인 분류 (ai.html 에서 사용)
AI_LAYER = {
    "NVDA": "칩 설계", "AMD": "칩 설계", "AVGO": "칩 설계",
    "TSM": "파운드리", "005930.KS": "메모리", "000660.KS": "메모리",
    "MSFT": "클라우드·모델", "GOOGL": "클라우드·모델", "AMZN": "클라우드·모델",
    "META": "모델·서비스",
}

# 전력 인프라 분류 (power.html 에서 사용)
POWER_LAYER = {
    "010120.KS": "배전·초고압 변압기·자동화", "267260.KS": "초고압 변압기·차단기",
    "298040.KS": "초고압 변압기·차단기", "006260.KS": "전선·해저케이블 (LS전선 지주사)",
    "001440.KS": "전선·해저케이블",
}

# id: (이름, 그룹, 변환) 변환: level | yoy | diff (전월 대비 증감)
# CPI 는 발표 헤드라인과 같은 원계열(NSA) 사용
FRED = {
    "CPIAUCNS": ("미국 CPI (YoY)", "us_inflation", "yoy"),
    "CPILFENS": ("미국 근원 CPI (YoY)", "us_inflation", "yoy"),
    "PCEPILFE": ("미국 근원 PCE (YoY)", "us_inflation", "yoy"),
    "DFF": ("미 연방기금금리", "us_rates", "level"),
    "DGS2": ("미 2년물 금리", "us_rates", "level"),
    "DGS10": ("미 10년물 금리", "us_rates", "level"),
    "T10Y2Y": ("장단기 금리차 (10Y-2Y)", "us_rates", "level"),
    "UNRATE": ("미국 실업률", "us_jobs", "level"),
    "PAYEMS": ("비농업 고용 증감 (천 명)", "us_jobs", "diff"),
    "PCU335311335311": ("미국 변압기 생산자물가지수", "us_power", "level"),
    "PCU335311335311_YOY": ("미국 변압기 생산자물가 (YoY)", "us_power", "yoy"),
}

# 한국은행 ECOS: id: (이름, 통계표, 항목, 변환)
ECOS = {
    "KR_BASE_RATE": ("한국 기준금리", "722Y001", "0101000", "level"),
    "KR_CPI": ("한국 CPI (YoY)", "901Y009", "0", "yoy"),
}

failures: list[str] = []


def pct(a: float, b: float) -> float | None:
    if b is None or b == 0 or pd.isna(a) or pd.isna(b):
        return None
    return round((a / b - 1) * 100, 2)


def fetch_prices() -> dict:
    summary = {}
    PRICES.mkdir(parents=True, exist_ok=True)
    for sym, (name, group) in TICKERS.items():
        try:
            df = pd.DataFrame()
            for attempt in range(3):  # 야후 응답이 가끔 비어서 재시도
                df = yf.Ticker(sym).history(period="5y", interval="1d", auto_adjust=True)
                df = df.dropna(subset=["Close"])
                if not df.empty:
                    break
                time.sleep(3 * (attempt + 1))
            if df.empty:
                raise ValueError("empty")
            df.index = df.index.tz_localize(None)
            rows = [
                [d.strftime("%Y-%m-%d"), round(r.Open, 4), round(r.High, 4),
                 round(r.Low, 4), round(r.Close, 4), int(r.Volume or 0)]
                for d, r in df.iterrows()
            ]
            fname = safe_name(sym)
            (PRICES / f"{fname}.json").write_text(
                json.dumps({"symbol": sym, "name": name, "rows": rows}, ensure_ascii=False),
                encoding="utf-8")

            close = df["Close"]
            last = close.iloc[-1]
            year_start = close[close.index >= datetime(close.index[-1].year, 1, 1)]
            item = {
                "name": name, "group": group, "file": fname,
                "date": rows[-1][0], "last": round(float(last), 2),
                "chg1d": pct(last, close.iloc[-2]) if len(close) > 1 else None,
                "chg1w": pct(last, close.iloc[-6]) if len(close) > 5 else None,
                "chg1m": pct(last, close.iloc[-22]) if len(close) > 21 else None,
                "chg3m": pct(last, close.iloc[-64]) if len(close) > 63 else None,
                "ytd": pct(last, year_start.iloc[0]) if len(year_start) else None,
                "high52": round(float(close.iloc[-252:].max()), 2),
                "low52": round(float(close.iloc[-252:].min()), 2),
                "spark": [round(float(x), 2) for x in close.iloc[-66:]],
            }
            if group in ("ai", "power"):
                item["layer"] = (AI_LAYER if group == "ai" else POWER_LAYER).get(sym)
                item.update(fetch_fundamentals(sym))
            summary[sym] = item
            print(f"  ok  {sym:10s} {name} {item['last']}")
        except Exception as e:  # 한 종목 실패가 전체를 멈추지 않게
            failures.append(f"price:{sym}:{e}")
            print(f"  FAIL {sym}: {e}", file=sys.stderr)
    return summary


def fetch_fundamentals(sym: str) -> dict:
    try:
        info = yf.Ticker(sym).info
    except Exception:
        return {}
    keys = {"trailingPE": "per", "forwardPE": "fwd_per", "priceToBook": "pbr",
            "marketCap": "mcap", "currency": "currency"}
    out = {}
    for k, v in keys.items():
        val = info.get(k)
        if val is not None:
            out[v] = round(val, 2) if isinstance(val, float) else val
    return out


def safe_name(sym: str) -> str:
    return sym.replace("^", "").replace("=", "_").replace(".", "_")


def fetch_fred() -> dict:
    out = {}
    start = (datetime.now() - timedelta(days=365 * 12)).strftime("%Y-%m-%d")
    for sid, (name, group, mode) in FRED.items():
        try:
            src = sid.removesuffix("_YOY")  # 같은 원계열을 수준·YoY 두 가지로 저장
            url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={src}&cosd={start}"
            r = requests.get(url, timeout=60)  # 브라우저 UA를 붙이면 FRED가 응답하지 않음
            r.raise_for_status()
            df = pd.read_csv(io.StringIO(r.text))
            df.columns = ["date", "value"]
            df["value"] = pd.to_numeric(df["value"], errors="coerce")
            df = df.dropna()
            df["date"] = pd.to_datetime(df["date"])
            s = df.set_index("date")["value"]
            if sid in ("DFF", "DGS2", "DGS10", "T10Y2Y"):
                s = s.resample("W-FRI").last().dropna()  # 일간 → 주간 (용량 절약)
            if mode == "yoy":
                s = yoy(s)
            elif mode == "diff":
                m = s.resample("MS").last()
                s = m.diff().dropna()
            s = s[s.index >= pd.Timestamp(datetime.now() - timedelta(days=365 * 10))]
            out[sid] = series_item(name, group, s, f"https://fred.stlouisfed.org/series/{src}")
            print(f"  ok  {sid:16s} {out[sid]['last']} ({out[sid]['date']})")
        except Exception as e:
            failures.append(f"fred:{sid}:{e}")
            print(f"  FAIL {sid}: {e}", file=sys.stderr)
    return out


def yoy(s: pd.Series) -> pd.Series:
    """월 단위로 맞춘 뒤 12개월 전과 비교 (2025-10 처럼 결측 월이 있어도 밀리지 않게)."""
    m = s.resample("MS").last()
    return (m / m.shift(12) - 1).mul(100).dropna()


def series_item(name: str, group: str, s: pd.Series, source: str) -> dict:
    pts = [[d.strftime("%Y-%m-%d"), round(float(v), 3)] for d, v in s.items()]
    return {
        "name": name, "group": group, "source": source,
        "date": pts[-1][0], "last": pts[-1][1],
        "prev": pts[-2][1] if len(pts) > 1 else None,
        "series": pts,
    }


def fetch_ecos(macro: dict) -> None:
    """한국 기준금리·CPI. ECOS_API_KEY 가 없으면 공개 sample 키(호출당 10건)로 나눠 받는다."""
    key = os.environ.get("ECOS_API_KEY") or "sample"
    step = 10 if key == "sample" else 1000
    now = pd.Timestamp(datetime.now()).to_period("M")
    months = pd.period_range(now - 12 * 11, now, freq="M")
    for sid, (name, stat, item, mode) in ECOS.items():
        try:
            vals = {}
            for i in range(0, len(months), step):
                chunk = months[i:i + step]
                url = (f"https://ecos.bok.or.kr/api/StatisticSearch/{key}/json/kr/1/{step}/"
                       f"{stat}/M/{chunk[0].strftime('%Y%m')}/{chunk[-1].strftime('%Y%m')}/{item}")
                body = requests.get(url, timeout=30).json()
                for r in body.get("StatisticSearch", {}).get("row", []):
                    vals[pd.to_datetime(r["TIME"], format="%Y%m")] = float(r["DATA_VALUE"])
            s = pd.Series(vals).sort_index()
            if s.empty:
                raise ValueError("no rows")
            if mode == "yoy":
                s = yoy(s)
            macro[sid] = series_item(name, "kr", s, "https://ecos.bok.or.kr")
            print(f"  ok  {sid:16s} {macro[sid]['last']} ({macro[sid]['date']})")
        except Exception as e:
            failures.append(f"ecos:{sid}:{e}")
            print(f"  FAIL {sid}: {e}", file=sys.stderr)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    DATA.mkdir(exist_ok=True)
    print("[가격]")
    market = fetch_prices()
    print("[매크로]")
    macro = fetch_fred()
    fetch_ecos(macro)

    (DATA / "market.json").write_text(json.dumps(market, ensure_ascii=False), encoding="utf-8")
    (DATA / "macro.json").write_text(json.dumps(macro, ensure_ascii=False), encoding="utf-8")
    (DATA / "updated.json").write_text(json.dumps({
        "updated_at": datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"),
        "failures": failures,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"완료. 실패 {len(failures)}건")
    if len(market) < len(TICKERS) // 2:  # 절반 이상 실패하면 배포하지 않도록 오류 종료
        sys.exit("가격 데이터 수집 실패가 너무 많습니다")


if __name__ == "__main__":
    main()
