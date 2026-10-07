"""Per-asset historical containment profile (read-only). Writes reports/containment_profile.md.
Usage: python scripts/containment_report.py [--call]"""
import os
import sys

import httpx
import numpy as np

from viking import containment as ct, dxlink
from viking.config import BrokerConfig
from viking.tastytrade import TastytradeBroker
from viking.trend import TrendConfig
from viking import indicators as ind

SIDE = "up" if "--call" in sys.argv else "down"
cfg = BrokerConfig()
b = TastytradeBroker.__new__(TastytradeBroker)
b.cfg, b._token, b._expires = cfg, "", 0.0
b.http = httpx.Client(base_url=cfg.base_url, timeout=15.0)
tok = b.http.get("/api-quote-tokens", headers=b._auth()).json()["data"]
syms = ["SPY", "IWM", "QQQ", "XLF", "TLT", "GLD", "/ES:XCME", "/NQ:XCME", "/GC:XCEC", "/CL:XNYM", "/ZN:XCBT"]
bars = dxlink.fetch_daily(tok["dxlink-url"], tok["token"], syms, days=3650, timeout=40)
tc = TrendConfig()


def dtb_mask(df):
    c = df["close"]; sma = c.rolling(tc.sma).mean()
    below = (c < sma).astype(float).rolling(tc.lookback).mean().shift(1)
    est = (below >= tc.frac) & (ind.adx(df, 14).rolling(tc.lookback).max().shift(1) > tc.adx_min) & (sma.diff(10).shift(1) < 0)
    return (est & (c > sma)).rolling(tc.window, min_periods=1).max().astype(bool)


L = [f"# Historical containment profile ({'calls: upside' if SIDE == 'up' else 'puts: downside'})\n",
     "Price-only, daily bars, ~10 years. Strike distance = z x 90d daily vol x sqrt(horizon); "
     "z=0.84 is about 0.20 delta, z=1.28 about 0.10 delta. 'Contained' = strike never touched within the horizon.\n"]
for s, df in bars.items():
    if len(df) < 400:
        continue
    p = ct.profile(df, SIDE)
    L.append(f"\n## {s}  ({len(df)} bars)\n")
    L.append("Worst adverse move over the horizon (% of price): median / 75th / 90th / 95th / 99th percentile\n")
    L.append("| Horizon | n | 50% | 75% | 90% | 95% | 99% | " + " | ".join(f"contained z={z}" for z in ct.ZS) + " |")
    L.append("|---|---|" + "---|" * (5 + len(ct.ZS)))
    for h, r in p.items():
        L.append(f"| {h}d | {r['n']} | " + " | ".join(f"{r['mae_pct'][q]:.1f}" for q in ct.QS) + " | "
                 + " | ".join(f"{r['contained'][z]:.0%}" for z in ct.ZS) + " |")
    t = ct.first_touch_timing(df, 0.84, 21, 45, SIDE)
    if t["touches"]:
        L.append(f"\nTiming of breaches of the z=0.84 strike (set for 21d, watched to 45d): {t['touches']} paths touched; "
                 + ", ".join(f"{int(v*100)}% by day {m}" for m, v in t["by_day"].items())
                 + f"; median first touch day {t['median_day']:.0f}; "
                 + f"{t['recovered_by_hmax']:.0%} of breached paths closed back beyond the strike by day 45.")
    if SIDE == "down":
        m = dtb_mask(df).to_numpy()
        ps = ct.profile(df, SIDE, mask=m, horizons=(21,), zs=(0.84, 1.28))
        n, c84 = ps[21]["n"], ps[21]["contained"][0.84]
        if n >= 20:
            L.append(f"\nAfter a downtrend break (phase 1 signal, {n} days): 21d contained at z=0.84: {c84:.0%} "
                     f"(all days {p[21]['contained'][0.84]:.0%}); at z=1.28: {ps[21]['contained'][1.28]:.0%} "
                     f"(all days {p[21]['contained'][1.28]:.0%}).")
os.makedirs("reports", exist_ok=True)
open("reports/containment_profile.md", "w").write("\n".join(L) + "\n")
print("\n".join(L))
