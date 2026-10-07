"""Compare commonly cited chart setups for short put spreads on the same footing.
Outcome: ~0.20-delta put strike (0.84 x 90d-vol sigma) touched within 21 trading days.
Fit 2016-22, test 2023+. Read-only."""
import httpx
import numpy as np
import pandas as pd

from viking import dxlink, indicators as ind
from viking.config import BrokerConfig
from viking.tastytrade import TastytradeBroker
from viking.trend import TrendConfig

H, K, SPLIT = 21, 0.84, pd.Timestamp("2023-01-01")
cfg = BrokerConfig()
b = TastytradeBroker.__new__(TastytradeBroker)
b.cfg, b._token, b._expires = cfg, "", 0.0
b.http = httpx.Client(base_url=cfg.base_url, timeout=15.0)
tok = b.http.get("/api-quote-tokens", headers=b._auth()).json()["data"]
syms = ["SPY", "IWM", "QQQ", "XLF", "TLT", "GLD", "/ES:XCME", "/NQ:XCME", "/GC:XCEC", "/CL:XNYM", "/ZN:XCBT"]
bars = dxlink.fetch_daily(tok["dxlink-url"], tok["token"], syms, days=3650, timeout=40)
tc = TrendConfig()
frames = []
for s in syms:
    if s not in bars or len(bars[s]) < 400:
        continue
    df = bars[s]
    c, lo, hi = df["close"], df["low"], df["high"]
    sma20, sma50, sma200 = c.rolling(20).mean(), c.rolling(50).mean(), c.rolling(200).mean()
    d = c.diff()
    rsi = 100 - 100 / (1 + d.clip(lower=0).ewm(alpha=1 / 14).mean() / (-d.clip(upper=0)).ewm(alpha=1 / 14).mean())
    bb_lo = sma20 - 2 * c.rolling(20).std()
    low20 = lo.rolling(20).min()
    below = (c < sma50).astype(float).rolling(tc.lookback).mean().shift(1)
    est = (below >= tc.frac) & (ind.adx(df, 14).rolling(tc.lookback).max().shift(1) > tc.adx_min) & (sma50.diff(10).shift(1) < 0)
    dtb = (est & (c > sma50)).rolling(tc.window, min_periods=1).max().astype(bool)
    up = (c > sma200) & (sma50 > sma50.shift(10))
    sig = (np.log(c).diff().rolling(90).std() * np.sqrt(252)) * np.sqrt(H / 252)
    strike = c * (1 - K * sig)
    fwd_min = pd.concat([lo.shift(-i) for i in range(1, H + 1)], axis=1).min(axis=1)
    ok = sig.notna() & sma200.notna() & fwd_min.notna()
    f = pd.DataFrame({
        "touch": (fwd_min <= strike), "ok": ok,
        "uptrend_pullback (RSI<40 in uptrend)": up & (rsi < 40),
        "oversold (RSI<30)": rsi < 30,
        "pullback to rising 50d (within 1%)": up & ((c / sma50 - 1).abs() < 0.01),
        "bounce off lower Bollinger": (c.shift(1) < bb_lo.shift(1)) & (c > bb_lo),
        "20d-low reversal day (close>prior high)": (lo.shift(1) <= low20.shift(1)) & (c > hi.shift(1)),
        "above rising 50d & 200d, near 20d high": up & (c >= hi.rolling(20).max() * 0.98),
        "downtrend break (phase 1)": dtb}).assign(sym=s)
    frames.append(f[f.ok])
d = pd.concat(frames)
names = [c for c in d.columns if c not in ("touch", "ok", "sym")]
print("short put 0.84σ(90d) strike touched within 21 trading days; n = signal days (overlapping, so independent trades are fewer)\n")
base = {k: d[(d.index < SPLIT) if k == "fit" else (d.index >= SPLIT)].touch.mean() for k in ("fit", "test")}
print(f"{'setup':44s}   fit: n  touch  | test: n  touch   (all-days baseline fit {base['fit']:.1%} / test {base['test']:.1%})")
for n in names:
    out = f"{n:44s}"
    for k, m in (("fit", d.index < SPLIT), ("test", d.index >= SPLIT)):
        x = d[m & d[n]]
        out += f" | {len(x):5d} {x.touch.mean():6.1%}"
    print(out)
