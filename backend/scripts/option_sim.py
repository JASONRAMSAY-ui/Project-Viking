"""Option-profit simulation of put credit spreads on real history (model-priced; see viking/optionsim.py).
Compares entry signals and management rules, fit 2016-22 vs test 2023+, with an IV-assumption sensitivity.
Read-only. Writes reports/option_sim.md."""
import os

import httpx
import numpy as np
import pandas as pd

from viking import dxlink, indicators as ind
from viking.config import BrokerConfig
from viking.optionsim import RULES, Rule, SimConfig, run, stats
from viking.tastytrade import TastytradeBroker
from viking.trend import TrendConfig

SPLIT = pd.Timestamp("2023-01-01")
cfg = BrokerConfig()
b = TastytradeBroker.__new__(TastytradeBroker)
b.cfg, b._token, b._expires = cfg, "", 0.0
b.http = httpx.Client(base_url=cfg.base_url, timeout=15.0)
tok = b.http.get("/api-quote-tokens", headers=b._auth()).json()["data"]
syms = ["SPY", "IWM", "QQQ", "XLF", "TLT", "GLD", "/ES:XCME", "/NQ:XCME", "/GC:XCEC", "/CL:XNYM", "/ZN:XCBT"]
bars = dxlink.fetch_daily(tok["dxlink-url"], tok["token"], syms, days=3650, timeout=40)
tc = TrendConfig()
masks = {}
for s, df in bars.items():
    if len(df) < 400:
        continue
    c = df["close"]; sma = c.rolling(50).mean()
    below = (c < sma).astype(float).rolling(tc.lookback).mean().shift(1)
    est = (below >= tc.frac) & (ind.adx(df, 14).rolling(tc.lookback).max().shift(1) > tc.adx_min) & (sma.diff(10).shift(1) < 0)
    dtb = (est & (c > sma)).rolling(tc.window, min_periods=1).max().astype(bool)
    masks[s] = {"signal": dtb, "control": (c > sma) & ~dtb, "all days": c == c}


def trades(cfg_, rule, which, syms_=None):
    parts = []
    for s, m in masks.items():
        if syms_ and s not in syms_:
            continue
        t = run(bars[s], m[which], cfg_, rule)
        if len(t):
            t["sym"] = s
            parts.append(t)
    return pd.concat(parts) if parts else pd.DataFrame()


def fmt(st):
    return "n/a" if not st["n"] else (f"n={st['n']:3d} win={st['win']:4.0%} avg={st['avg']:+.2f} med={st['median']:+.2f} "
                                      f"worst={st['worst']:+.2f} PF={st['pf']:.2f} maxDD={st['maxdd']:.1f}")


L = ["# Put credit spread simulation (model-priced, return on risk per trade, net of costs)\n",
     "Entry ~45 DTE, short ~0.20 delta, width 0.5 sigma, cost 5% of width. Fit = 2016-22, test = 2023+. "
     "Black-Scholes with IV = iv_mult x 90d realised vol and vol-on-drop. NOT real fills.\n"]
base = SimConfig()
L.append("\n## Management rules (iv_mult 1.15)\n")
for which in ("signal", "control"):
    L.append(f"\n### Entries: {which}\n")
    for r in RULES:
        d = trades(base, r, which)
        if not len(d):
            continue
        fit, test = d[d.date < SPLIT], d[d.date >= SPLIT]
        L.append(f"- {r.name:36s} FIT  {fmt(stats(fit))}\n  {'':36s} TEST {fmt(stats(test))}")
L.append("\n## Sensitivity to the volatility-premium assumption (hold to expiry vs 50% TP + stop + 21 DTE, signal entries)\n")
for mult in (1.0, 1.15, 1.3):
    for r in (RULES[0], RULES[-1]):
        d = trades(SimConfig(iv_mult=mult), r, "signal")
        L.append(f"- iv_mult {mult:4.2f} {r.name:36s} ALL {fmt(stats(d))}")
L.append("\n## Per asset (rule: TP 50% + stop below short + 21 DTE; signal entries, all years)\n")
for s in masks:
    d = trades(base, RULES[-1], "signal", {s})
    L.append(f"- {s:10s} {fmt(stats(d))}")
os.makedirs("reports", exist_ok=True)
open("reports/option_sim.md", "w").write("\n".join(L) + "\n")
print("\n".join(L))
