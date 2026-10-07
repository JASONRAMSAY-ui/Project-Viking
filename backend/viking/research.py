"""Cross-sectional research engine: test many chart setups for short put spreads on a broad universe.

For every symbol-day we compute a hold-to-expiry put-credit-spread return on risk (Black-Scholes priced,
see optionsim.py for the assumptions) and whether a 0.84-sigma strike was touched. A setup's edge is its
EXCESS over the same-date average across the whole universe, which removes market-wide timing luck
(everything sells off together). Significance uses monthly clustering."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import indicators as ind

H = 21
D1, WIDTH_SIGMA, COST = 0.8416, 0.5, 0.05


def _erf(x):
    # Abramowitz-Stegun 7.1.26, |error| < 1.5e-7
    s = np.sign(x); x = np.abs(x)
    t = 1 / (1 + 0.3275911 * x)
    y = 1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * np.exp(-x * x)
    return s * y


def _N(x):
    return 0.5 * (1 + _erf(x / np.sqrt(2)))


def put_price(S, K, T, vol, r=0.04):
    d1 = (np.log(S / K) + (r + vol ** 2 / 2) * T) / (vol * np.sqrt(T))
    d2 = d1 - vol * np.sqrt(T)
    return K * np.exp(-r * T) * _N(-d2) - S * _N(-d1)


def rsi(c: pd.Series, n: int = 14) -> pd.Series:
    d = c.diff()
    return 100 - 100 / (1 + d.clip(lower=0).ewm(alpha=1 / n).mean() / (-d.clip(upper=0)).ewm(alpha=1 / n).mean())


def downtrend_break(c, adx, sma_n, adx_min, frac, look, window):
    sma = c.rolling(sma_n).mean()
    below = (c < sma).astype(float).rolling(look).mean().shift(1)
    est = (below >= frac) & (adx.rolling(look).max().shift(1) > adx_min) & (sma.diff(10).shift(1) < 0)
    return (est & (c > sma)).rolling(window, min_periods=1).max().astype(bool)


def outcomes(df: pd.DataFrame, iv_mult: float = 1.15, iv_w: float = 0.0) -> pd.DataFrame:
    """iv_w: weight of 20d realised vol in the implied vol used to price the credit (0 = anchored to 90d vol)."""
    c, lo = df["close"], df["low"]
    ret_ = np.log(c).diff()
    sig = ret_.rolling(90).std()
    T0 = H / 252
    iv0 = iv_mult * (iv_w * ret_.rolling(20).std() + (1 - iv_w) * sig) * np.sqrt(252)
    K1 = c * np.exp(0.04 * T0 + iv0 ** 2 / 2 * T0 - D1 * iv0 * np.sqrt(T0))
    width = WIDTH_SIGMA * sig * np.sqrt(H) * c
    K2 = K1 - width
    credit = put_price(c, K1, T0, iv0) - put_price(c, K2, T0, iv0)
    ST = c.shift(-H)
    payoff = (K1 - ST).clip(lower=0) - (K2 - ST).clip(lower=0)
    ror = (credit - payoff - COST * width) / (width - credit)
    valid = ror.notna() & (credit > 0.02 * width) & (credit < 0.8 * width)
    fmin = pd.concat([lo.shift(-i) for i in range(1, H + 1)], axis=1).min(axis=1)
    fwd_ok = ST.notna() & fmin.notna()
    return pd.DataFrame({
        "ror": ror.where(valid & fwd_ok), "valid": valid & fwd_ok,
        "touch84": (fmin <= c * (1 - 0.84 * sig * np.sqrt(H))).where(fwd_ok & sig.notna()),
        "touch128": (fmin <= c * (1 - 1.28 * sig * np.sqrt(H))).where(fwd_ok & sig.notna())})


def setups(df: pd.DataFrame, spy: pd.DataFrame | None) -> pd.DataFrame:
    c, h, l, v = df["close"], df["high"], df["low"], df["volume"]
    ret = np.log(c).diff()
    sd = ret.rolling(90).std()
    hv20, hv90 = ret.rolling(20).std(), sd
    s20, s50, s100, s200 = (c.rolling(n).mean() for n in (20, 50, 100, 200))
    adx = ind.adx(df, 14)
    r = rsi(c)
    up = (c > s200) & (s50 > s50.shift(10))
    hi252 = c.rolling(252).max()
    bb_lo = s20 - 2 * c.rolling(20).std()
    vavg = v.rolling(20).mean()
    rs63 = np.log(c / c.shift(63)) - (np.log(spy["close"] / spy["close"].shift(63)).reindex(c.index) if spy is not None else 0)
    dtb = downtrend_break(c, adx, 50, 30, 0.9, 60, 5)
    box = ind.squeeze_box(df, 10, 14, 50)
    S = {
        "ALL DAYS": c == c,
        # trend breaks
        "downtrend break (phase1: sma50 adx30 90% 60d)": dtb,
        "downtrend break (sma20 adx25 80% 60d)": downtrend_break(c, adx, 20, 25, 0.8, 60, 5),
        "downtrend break (sma100 adx25 80% 60d)": downtrend_break(c, adx, 100, 25, 0.8, 60, 5),
        "downtrend break (sma50 adx20 80% 30d, 10d window)": downtrend_break(c, adx, 50, 20, 0.8, 30, 10),
        "  + breakout volume >1.5x": dtb & (v > 1.5 * vavg).rolling(5, min_periods=1).max().astype(bool),
        "  + still below 200d (no new uptrend)": dtb & (c < s200),
        "  + above 200d": dtb & (c > s200),
        "  + RSI>50": dtb & (r > 50),
        "  + outperforming SPY 63d": dtb & (rs63 > 0),
        "  + vol contracting (hv20<hv90)": dtb & (hv20 < hv90),
        # oversold / reversal
        "RSI<30": r < 30, "RSI<25": r < 25,
        "bounce off lower Bollinger": (c.shift(1) < bb_lo.shift(1)) & (c > bb_lo),
        "20d-low reversal day": (l.shift(1) <= l.rolling(20).min().shift(1)) & (c > h.shift(1)),
        "capitulation: -2.5sd day, then up close": (ret.shift(1) < -2.5 * sd.shift(1)) & (ret > 0),
        # uptrend pullbacks and strength
        "uptrend + RSI<40": up & (r < 40),
        "uptrend + close<20d": up & (c < s20),
        "uptrend pullback to 50d (1%)": up & ((c / s50 - 1).abs() < 0.01),
        "near 52w high (2%)": c >= 0.98 * hi252,
        "new 52w high": c >= hi252,
        "above 50&200, near 20d high": up & (c >= h.rolling(20).max() * 0.98),
        "strong RS (63d vs SPY >10%) + uptrend": up & (rs63 > 0.10),
        # volatility regimes
        "quiet (hv20/hv90<0.7)": hv20 / hv90 < 0.7,
        "quiet + uptrend": (hv20 / hv90 < 0.7) & up,
        "vol shock recovery (hv20/hv90>1.5, >20d, RSI>50)": (hv20 / hv90 > 1.5) & (c > s20) & (r > 50),
        "vol shock fading (hv20 -20% in 10d, ratio>1.1)": (hv20 < 0.8 * hv20.shift(10)) & (hv20 / hv90 > 1.1),
        "squeeze box + uptrend": box & up,
        "squeeze box": box,
    }
    return pd.DataFrame({k: v_.fillna(False).astype(bool) for k, v_ in S.items()})


def build(bars: dict, groups: dict, iv_mult: float = 1.15, iv_w: float = 0.0) -> pd.DataFrame:
    spy = bars.get("SPY")
    parts = []
    for s, df in bars.items():
        if len(df) < 800:
            continue
        o = outcomes(df, iv_mult, iv_w)
        f = setups(df, spy)
        x = pd.concat([o, f], axis=1)
        x["sym"], x["group"] = s, groups.get(s, "stock")
        x["date"] = df.index
        parts.append(x[x["valid"] & x["touch84"].notna()])
    return pd.concat(parts, ignore_index=True)


def episodes(sym: pd.Series, mask: pd.Series, gap: int = 10) -> int:
    n = 0
    for _, g in mask[mask].groupby(sym[mask]):
        idx = g.index.to_numpy()
        n += 1 + int((np.diff(idx) > gap).sum()) if len(idx) else 0
    return n


def evaluate(d: pd.DataFrame, names: list[str]) -> pd.DataFrame:
    d = d.copy()
    d["ex_ror"] = d["ror"] - d.groupby("date")["ror"].transform("mean")
    d["ex_touch"] = d["touch84"].astype(float) - d.groupby("date")["touch84"].transform(lambda s: s.astype(float).mean())
    d["month"] = d["date"].dt.to_period("M")
    blocks = [("16-19", "2016-01-01", "2020-01-01"), ("20-22", "2020-01-01", "2023-01-01"), ("23-26", "2023-01-01", "2030-01-01")]
    rows = []
    for nm in names:
        m = d[nm]
        e = d[m]
        if len(e) < 30:
            continue
        mon = e.groupby("month")["ex_ror"].mean()
        t = mon.mean() / (mon.std(ddof=1) / np.sqrt(len(mon))) if len(mon) > 3 and mon.std(ddof=1) > 0 else np.nan
        row = {"setup": nm, "n": len(e), "episodes": episodes(d["sym"], m), "touch84": e["touch84"].astype(float).mean(),
               "ex_touch": e["ex_touch"].mean(), "ror": e["ror"].mean(), "win": (e["ror"] > 0).mean(),
               "ex_ror": e["ex_ror"].mean(), "t": t}
        for b, a, z in blocks:
            sub = e[(e.date >= a) & (e.date < z)]
            row[b] = sub["ex_ror"].mean() if len(sub) >= 20 else np.nan
        for g in ("stock", "etf", "future"):
            sub = e[e.group == g]
            row[g] = sub["ex_ror"].mean() if len(sub) >= 20 else np.nan
        rows.append(row)
    return pd.DataFrame(rows)
