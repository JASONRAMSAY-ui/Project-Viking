"""Phase 1 (one-sided, put spreads): does a recent break of an established DOWNtrend make the
short put safer? Sweeps definitions, fits on 2016-2022, tests on 2023+, controls for drift.
Outcome: price touches the ~0.20-delta put strike (0.84 x 90d-vol sigma) within 21 trading days.
Read-only. Usage: python scripts/sweep_trend_break.py [--call]  (--call mirrors for call spreads)"""
import itertools
import sys

import httpx
import numpy as np
import pandas as pd

from viking import dxlink, indicators as ind
from viking.config import BrokerConfig
from viking.tastytrade import TastytradeBroker

CALL = "--call" in sys.argv
H, K, SPLIT = 21, 0.84, pd.Timestamp("2023-01-01")
cfg = BrokerConfig()
b = TastytradeBroker.__new__(TastytradeBroker)
b.cfg, b._token, b._expires = cfg, "", 0.0
b.http = httpx.Client(base_url=cfg.base_url, timeout=15.0)
tok = b.http.get("/api-quote-tokens", headers=b._auth()).json()["data"]
syms = ["SPY", "IWM", "QQQ", "XLF", "TLT", "GLD", "/ES:XCME", "/NQ:XCME", "/GC:XCEC", "/CL:XNYM", "/ZN:XCBT"]
bars = dxlink.fetch_daily(tok["dxlink-url"], tok["token"], syms, days=3650, timeout=40)

GRID = list(itertools.product((20, 50, 100), (20, 25, 30), (0.7, 0.8, 0.9), (20, 30, 60), (1, 5, 10)))
# sma, adx_min, frac_on_side, lookback, days_since_break_window


def touched(df):
    c, hi, lo = df["close"].to_numpy(), df["high"].to_numpy(), df["low"].to_numpy()
    sig = (np.log(df["close"]).diff().rolling(90).std() * np.sqrt(252)).to_numpy() * np.sqrt(H / 252)
    out = np.full(len(df), np.nan)
    for t in range(len(df) - H):
        if np.isnan(sig[t]):
            continue
        if CALL:
            out[t] = hi[t + 1: t + 1 + H].max() >= c[t] * (1 + K * sig[t])
        else:
            out[t] = lo[t + 1: t + 1 + H].min() <= c[t] * (1 - K * sig[t])
    return out


def events(df, sma_n, adx_min, frac, look, win):
    c = df["close"]
    sma = c.rolling(sma_n).mean()
    side = (c < sma) if not CALL else (c > sma)          # the established trend's side
    on = side.astype(float).rolling(look).mean().shift(1)
    adxmax = ind.adx(df, 14).rolling(look).max().shift(1)
    slope = sma.diff(10).shift(1)
    est = (on >= frac) & (adxmax > adx_min) & ((slope < 0) if not CALL else (slope > 0))
    broke = est & ((c > sma) if not CALL else (c < sma))   # first close back through the average
    return broke.rolling(win, min_periods=1).max().astype(bool), c > sma if not CALL else c < sma


data = {}
for s in syms:
    if s in bars and len(bars[s]) > 400:
        df = bars[s]
        data[s] = (df, touched(df))

rows = []
for g in GRID:
    ev, ctl = [], []
    for s, (df, t) in data.items():
        e, ctrl = events(df, *g)
        ok = ~np.isnan(t)
        x = pd.DataFrame({"t": t, "e": e.to_numpy(), "ctl": ctrl.to_numpy(), "d": df.index}, index=df.index)[ok]
        ev.append(x)
    x = pd.concat(ev)
    res = {"params": g}
    for name, m in (("train", x.d < SPLIT), ("test", x.d >= SPLIT)):
        y = x[m]
        sig, ctrl = y[y.e], y[y.ctl & ~y.e]
        res[name] = (len(sig), sig.t.mean() if len(sig) else np.nan, ctrl.t.mean())
    rows.append(res)

print(f"side={'CALL' if CALL else 'PUT'}  outcome: price touches 0.84σ(90d) strike within {H}d")
print("params=(sma, adx_min, frac, lookback, window)  n=signal days; touch vs drift-matched control\n")
good = []
for r in rows:
    (n1, t1, c1), (n2, t2, c2) = r["train"], r["test"]
    if n1 >= 100 and n2 >= 60 and t1 < c1 - 0.05 and t2 < c2 - 0.05:
        good.append((r["params"], n1, t1, c1, n2, t2, c2))
print(f"{len(good)} of {len(rows)} parameter sets beat the control by >=5pts in BOTH periods "
      f"(n>=100 train, >=60 test)\n")
good.sort(key=lambda g: (g[2] - g[3]) + (g[5] - g[6]))
for p, n1, t1, c1, n2, t2, c2 in good[:10]:
    print(f"{p}  train n={n1:4d} touch={t1:.1%} vs ctrl {c1:.1%} | test n={n2:4d} touch={t2:.1%} vs ctrl {c2:.1%}")
