"""Phase 1 refinement: downtrend break AT/ABOVE the POC or congestion (HVN), short put placed
BELOW the congestion. Strike rule: min(0.84σ strike, HVN low). Compared with drift-matched
control days using the same position rule and the same strike rule. Fit 2016-22, test 2023+.
Read-only. Usage: python scripts/sweep_poc.py"""
import httpx
import numpy as np
import pandas as pd

from viking import dxlink, indicators as ind
from viking.config import BrokerConfig
from viking.tastytrade import TastytradeBroker
from viking.trend import TrendConfig

H, K, SPLIT, LOOK = 21, 0.84, pd.Timestamp("2023-01-01"), 180
cfg = BrokerConfig()
b = TastytradeBroker.__new__(TastytradeBroker)
b.cfg, b._token, b._expires = cfg, "", 0.0
b.http = httpx.Client(base_url=cfg.base_url, timeout=15.0)
tok = b.http.get("/api-quote-tokens", headers=b._auth()).json()["data"]
syms = ["SPY", "IWM", "QQQ", "XLF", "TLT", "GLD", "/ES:XCME", "/NQ:XCME", "/GC:XCEC", "/CL:XNYM", "/ZN:XCBT"]
bars = dxlink.fetch_daily(tok["dxlink-url"], tok["token"], syms, days=3650, timeout=40)
tc = TrendConfig()

rows = []
for s in syms:
    if s not in bars or len(bars[s]) < 400:
        continue
    df = bars[s]
    c = df["close"]
    sma = c.rolling(tc.sma).mean()
    below = (c < sma).astype(float).rolling(tc.lookback).mean().shift(1)
    est = (below >= tc.frac) & (ind.adx(df, 14).rolling(tc.lookback).max().shift(1) > tc.adx_min) \
        & (sma.diff(10).shift(1) < 0)
    brk = (est & (c > sma)).rolling(tc.window, min_periods=1).max().astype(bool)
    sig = (np.log(c).diff().rolling(90).std() * np.sqrt(252)) * np.sqrt(H / 252)
    cl, lo = c.to_numpy(), df["low"].to_numpy()
    for t in range(max(LOOK, 250), len(df) - H):
        is_ev, is_ctl = bool(brk.iloc[t]), bool(c.iloc[t] > sma.iloc[t]) and not bool(brk.iloc[t])
        if not (is_ev or (is_ctl and t % 3 == 0)):
            continue
        h = ind.volume_profile_hvn(df.iloc[: t + 1], LOOK)
        base = cl[t] * (1 - K * sig.iloc[t])
        strike = min(base, h["low"] * 0.998)
        rows.append({"d": df.index[t], "ev": is_ev, "at_poc": cl[t] >= h["poc"] * 0.995,
                     "in_or_above": cl[t] >= h["low"], "below_cong": cl[t] < h["low"],
                     "touch": lo[t + 1: t + 1 + H].min() <= strike,
                     "plain": lo[t + 1: t + 1 + H].min() <= base,
                     "dist_sigma": (cl[t] - strike) / (cl[t] * sig.iloc[t]),
                     "moved": strike < base})
d = pd.DataFrame(rows)


def line(name, m):
    out = f"{name:30s}"
    for nm, per in (("fit ", d.d < SPLIT), ("test", d.d >= SPLIT)):
        e, k = d[m & d.ev & per], d[m & ~d.ev & per]
        out += (f" | {nm} n={len(e):3d} plain 0.84σ strike: {e.plain.mean():5.1%} vs ctrl {k.plain.mean():5.1%}"
                f" | strike-below-congestion: {e.touch.mean():5.1%} vs {k.touch.mean():5.1%}"
                f" (dist {e.dist_sigma.median():.2f}σ vs {k.dist_sigma.median():.2f}σ)")
    print(out)
    print(out)


print("touch = price reaches the short put within 21 trading days; ctrl = drift-matched days, same location class\n")
line("trend break (any location)", d.ev == d.ev)
line("  ... at/above POC", d.at_poc)
line("  ... in or above congestion", d.in_or_above)
line("  ... below congestion", d.below_cong)
e = d[d.ev]
print(f"\nbreak days: {len(e)}; strike pushed below congestion on {e.moved.mean():.0%} of them")
