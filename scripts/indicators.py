"""data/prices/*.json 으로 보조지표·매수 체크리스트·백테스트를 계산한다.

출력
- data/indicators/<파일>.json : 차트용 시계열 (최근 1년)
- data/signals.json           : 종목별 최신 지표값, 신호, 체크리스트 점수, 백테스트 결과
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = DATA / "indicators"
CHART_DAYS = 260
SKIP_GROUPS = {"rate"}  # 금리는 가격 지표 의미가 약해 제외


# ---------- 지표 계산 ----------
def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    """Wilder 방식 (TradingView·HTS 와 같은 계산)."""
    diff = close.diff()
    up = diff.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    down = (-diff.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = up / down.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def compute(df: pd.DataFrame) -> pd.DataFrame:
    c, h, l, v = df["close"], df["high"], df["low"], df["volume"]
    for n in (5, 20, 60, 120, 200):
        df[f"sma{n}"] = sma(c, n)
    df["ema12"], df["ema26"] = ema(c, 12), ema(c, 26)
    df["rsi"] = rsi(c)
    df["macd"] = df["ema12"] - df["ema26"]
    df["macd_signal"] = ema(df["macd"], 9)
    df["macd_hist"] = df["macd"] - df["macd_signal"]
    # 볼린저밴드 (20, 2) - 표본이 아닌 모집단 표준편차 (ddof=0, 일반적인 차트 툴 기준)
    mid, std = sma(c, 20), c.rolling(20).std(ddof=0)
    df["bb_mid"], df["bb_up"], df["bb_low"] = mid, mid + 2 * std, mid - 2 * std
    df["bb_pctb"] = (c - df["bb_low"]) / (df["bb_up"] - df["bb_low"])
    df["bb_width"] = (df["bb_up"] - df["bb_low"]) / mid * 100
    # 스토캐스틱 슬로우 (14, 3, 3)
    ll, hh = l.rolling(14).min(), h.rolling(14).max()
    fast_k = (c - ll) / (hh - ll) * 100
    df["stoch_k"] = fast_k.rolling(3).mean()
    df["stoch_d"] = df["stoch_k"].rolling(3).mean()
    # ATR (14)
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    df["atr"] = tr.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    # 거래량
    df["obv"] = (np.sign(c.diff()).fillna(0) * v).cumsum()
    df["vol_ratio"] = v / v.rolling(20).mean()
    return df


# ---------- 신호 판정 ----------
def crossed_up(a: pd.Series, b: pd.Series | float, lookback: int = 5) -> bool:
    b = b if isinstance(b, pd.Series) else pd.Series(b, index=a.index)
    above = a > b
    recent = above.iloc[-lookback - 1:]
    return bool(recent.iloc[-1] and not recent.iloc[:-1].all() and (~recent.iloc[:-1]).any())


def crossed_down(a: pd.Series, b: pd.Series | float, lookback: int = 5) -> bool:
    b = b if isinstance(b, pd.Series) else pd.Series(b, index=a.index)
    return crossed_up(b, a, lookback)


def bullish_divergence(df: pd.DataFrame, n: int = 20) -> bool:
    """최근 n일 저점이 직전 n일 저점보다 낮은데 RSI 저점은 높으면 상승 다이버전스."""
    if len(df) < 2 * n:
        return False
    recent, prior = df.iloc[-n:], df.iloc[-2 * n:-n]
    return bool(recent["low"].min() < prior["low"].min()
                and recent["rsi"].min() > prior["rsi"].min()
                and recent["rsi"].min() < 40)


def signals(df: pd.DataFrame) -> list[dict]:
    last = df.iloc[-1]
    out = []

    def add(kind: str, text: str, tone: str) -> None:
        out.append({"kind": kind, "text": text, "tone": tone})

    if crossed_up(df["sma20"], df["sma60"]):
        add("이평선", "골든크로스 (20일선이 60일선 상향 돌파, 최근 5일)", "up")
    if crossed_down(df["sma20"], df["sma60"]):
        add("이평선", "데드크로스 (20일선이 60일선 하향 돌파, 최근 5일)", "down")
    if crossed_up(df["sma60"], df["sma120"], 10):
        add("이평선", "중기 골든크로스 (60일선 > 120일선)", "up")
    if last.sma5 > last.sma20 > last.sma60 > last.sma120:
        add("이평선", "정배열 (5 > 20 > 60 > 120)", "up")
    elif last.sma5 < last.sma20 < last.sma60 < last.sma120:
        add("이평선", "역배열 (5 < 20 < 60 < 120)", "down")
    if last.rsi < 30:
        add("RSI", f"과매도 구간 (RSI {last.rsi:.0f})", "up")
    elif last.rsi > 70:
        add("RSI", f"과매수 구간 (RSI {last.rsi:.0f})", "down")
    if crossed_up(df["rsi"], 30):
        add("RSI", "RSI 30 상향 돌파 (과매도 탈출)", "up")
    if bullish_divergence(df):
        add("RSI", "상승 다이버전스 (가격 저점↓, RSI 저점↑)", "up")
    if last.close < last.bb_low:
        add("볼린저", "하단 밴드 이탈", "up")
    elif last.close > last.bb_up:
        add("볼린저", "상단 밴드 돌파", "down")
    if crossed_up(df["close"], df["bb_low"]):
        add("볼린저", "하단 밴드 아래에서 안으로 복귀", "up")
    width = df["bb_width"].dropna().iloc[-120:]
    if len(width) > 60 and last.bb_width <= width.quantile(0.1):
        add("볼린저", "스퀴즈 (밴드폭 6개월 하위 10%) - 큰 움직임 예고", "neutral")
    if crossed_up(df["macd"], df["macd_signal"]):
        add("MACD", "MACD 시그널선 상향 교차", "up")
    if crossed_down(df["macd"], df["macd_signal"]):
        add("MACD", "MACD 시그널선 하향 교차", "down")
    if last.vol_ratio > 2:
        add("거래량", f"거래량 급증 (20일 평균의 {last.vol_ratio:.1f}배)", "neutral")
    return out


def checklist(df: pd.DataFrame) -> tuple[int, list[dict]]:
    """매수 체크리스트. 추세 필터 + 진입 타이밍 + 거래량 확인. 합계 100점."""
    last, prev5 = df.iloc[-1], df.iloc[-6]
    sma200_20ago = df["sma200"].iloc[-21]
    obv_up = df["obv"].iloc[-1] > df["obv"].iloc[-21]
    items = [
        ("추세", "종가가 200일선 위", 20, last.close > last.sma200),
        ("추세", "200일선이 우상향 (20일 전 대비)", 5, last.sma200 > sma200_20ago),
        ("추세", "20 > 60 > 120일선 정배열", 15, last.sma20 > last.sma60 > last.sma120),
        ("모멘텀", "RSI 30~55 이면서 5일 전보다 상승 (눌림 후 반등)", 15,
         30 <= last.rsi <= 55 and last.rsi > prev5.rsi),
        ("모멘텀", "MACD가 시그널선 위", 15, last.macd > last.macd_signal),
        ("모멘텀", "스토캐스틱 %K > %D 이고 %K 80 미만", 10,
         last.stoch_k > last.stoch_d and last.stoch_k < 80),
        ("변동성", "볼린저 %B 0~0.5 (과열 아님, 하단~중심)", 10, 0 <= last.bb_pctb <= 0.5),
        ("거래량", "OBV 20일 상승 (매수세 유입)", 10, obv_up),
    ]
    rows = [{"group": g, "label": t, "weight": w, "pass": bool(p)} for g, t, w, p in items]
    return sum(r["weight"] for r in rows if r["pass"]), rows


# ---------- 백테스트 ----------
STRATEGIES = {
    "rsi": "RSI 30 상향 돌파 매수 → RSI 70 도달 또는 -8% 손절 시 매도",
    "golden": "20일선이 60일선 골든크로스 매수 → 데드크로스 매도",
    "bollinger": "볼린저 하단 복귀 매수 → 상단 도달 또는 -8% 손절 시 매도",
    "macd200": "200일선 위에서 MACD 상향 교차 매수 → MACD 하향 교차 매도",
}


def backtest(df: pd.DataFrame, key: str) -> dict:
    """종가 기준, 수수료 0.1% 왕복 가정. 롱 온리. 신호 다음 날 종가에 체결."""
    d = df.dropna(subset=["sma200", "rsi", "macd_signal", "bb_low"]).reset_index(drop=True)
    c = d["close"]
    up = lambda a, b: (a > b) & (a.shift() <= b.shift())  # noqa: E731
    if key == "rsi":
        entry = up(d["rsi"], pd.Series(30, index=d.index))
    elif key == "golden":
        entry = up(d["sma20"], d["sma60"])
    elif key == "bollinger":
        entry = up(c, d["bb_low"])
    else:
        entry = up(d["macd"], d["macd_signal"]) & (c > d["sma200"])

    trades, pos, equity, peak, mdd = [], None, 1.0, 1.0, 0.0
    for i in range(1, len(d)):
        if pos is None and entry.iloc[i - 1]:
            pos = c.iloc[i]
            continue
        if pos is None:
            continue
        r = c.iloc[i] / pos - 1
        if key == "rsi":
            exit_ = d["rsi"].iloc[i] >= 70 or r <= -0.08
        elif key == "golden":
            exit_ = d["sma20"].iloc[i] < d["sma60"].iloc[i]
        elif key == "bollinger":
            exit_ = c.iloc[i] >= d["bb_up"].iloc[i] or r <= -0.08
        else:
            exit_ = d["macd"].iloc[i] < d["macd_signal"].iloc[i]
        if exit_ or i == len(d) - 1:
            trades.append(r - 0.001)
            pos = None
        # MDD 는 보유 중 일별 평가액 기준
        cur = equity * (1 + r)
        peak = max(peak, cur)
        mdd = min(mdd, cur / peak - 1)
        if pos is None:
            equity *= 1 + trades[-1]
    bh = c.iloc[-1] / c.iloc[0] - 1
    wins = [t for t in trades if t > 0]
    return {
        "trades": len(trades),
        "win_rate": round(len(wins) / len(trades) * 100, 1) if trades else None,
        "avg_return": round(float(np.mean(trades)) * 100, 2) if trades else None,
        "total_return": round((equity - 1) * 100, 1),
        "mdd": round(mdd * 100, 1),
        "buy_hold": round(bh * 100, 1),
        "period": f"{d['date'].iloc[0]} ~ {d['date'].iloc[-1]}",
    }


# ---------- 메인 ----------
def r(x, n=2):
    return None if pd.isna(x) else round(float(x), n)


def main() -> None:
    market = json.loads((DATA / "market.json").read_text(encoding="utf-8"))
    OUT.mkdir(exist_ok=True)
    result = {"strategies": STRATEGIES, "items": {}}
    for sym, meta in market.items():
        if meta["group"] in SKIP_GROUPS:
            continue
        raw = json.loads((DATA / "prices" / f"{meta['file']}.json").read_text(encoding="utf-8"))
        df = pd.DataFrame(raw["rows"], columns=["date", "open", "high", "low", "close", "volume"])
        if len(df) < 260:
            continue
        df = compute(df)
        has_volume = df["volume"].iloc[-60:].sum() > 0
        score, rows = checklist(df)
        if not has_volume:  # 지수 일부·환율은 거래량이 없음 → OBV 항목 제외 후 환산
            rows = [x for x in rows if x["group"] != "거래량"]
            score = round(sum(x["weight"] for x in rows if x["pass"]) / 90 * 100)
        last = df.iloc[-1]
        result["items"][sym] = {
            "name": meta["name"], "group": meta["group"], "file": meta["file"],
            "date": last.date, "close": r(last.close),
            "rsi": r(last.rsi, 1), "macd": r(last.macd, 3), "macd_signal": r(last.macd_signal, 3),
            "bb_pctb": r(last.bb_pctb, 2), "bb_width": r(last.bb_width, 1),
            "stoch_k": r(last.stoch_k, 1), "stoch_d": r(last.stoch_d, 1),
            "atr": r(last.atr), "atr_pct": r(last.atr / last.close * 100, 2),
            "vol_ratio": r(last.vol_ratio, 2) if has_volume else None,
            "sma": {n: r(last[f"sma{n}"]) for n in (5, 20, 60, 120, 200)},
            "dist_sma200": r((last.close / last.sma200 - 1) * 100, 1),
            "signals": signals(df),
            "score": int(score), "checklist": rows,
            "backtest": {k: backtest(df, k) for k in STRATEGIES},
        }
        tail = df.iloc[-CHART_DAYS:]
        cols = ["open", "high", "low", "close", "volume", "sma5", "sma20", "sma60", "sma120",
                "sma200", "bb_up", "bb_mid", "bb_low", "rsi", "macd", "macd_signal",
                "macd_hist", "stoch_k", "stoch_d", "obv"]
        series = {"date": tail["date"].tolist()}
        for col in cols:
            series[col] = [r(x, 4) for x in tail[col]]
        (OUT / f"{meta['file']}.json").write_text(json.dumps(series), encoding="utf-8")
        print(f"  {sym:10s} 점수 {score:3d}  RSI {last.rsi:5.1f}  신호 {len(result['items'][sym]['signals'])}개")
    (DATA / "signals.json").write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    print("완료")


if __name__ == "__main__":
    main()
