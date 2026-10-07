"""Rank chart setups for short put spreads across the broad universe (needs data/bars_cache.pkl from
fetch_universe.py). Edge = excess hold-to-expiry return on risk over the same-date universe average.
Writes reports/setup_research.md. Read-only. Usage: python scripts/setup_research.py"""
import os
import pickle

import numpy as np
import pandas as pd

from viking import research as rs

bars = pickle.load(open("data/bars_cache.pkl", "rb"))
groups = {s: ("future" if s.startswith("/") else "etf" if s in
             "SPY QQQ IWM DIA XLF XLE XLK XLV XLY XLP XLI XLU XLB XLC XLRE SMH XBI KRE XOP XHB TLT IEF HYG LQD GLD SLV USO UNG EEM EFA FXI EWZ VNQ".split()
             else "stock") for s in bars}
cnt = pd.Series(groups).value_counts().to_dict()
d = rs.build(bars, groups, 1.15)
names = [c for c in d.columns if c in rs.setups(next(iter(bars.values())), bars.get("SPY")).columns]
res = rs.evaluate(d, names).sort_values("t", ascending=False)
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30); pd.set_option("display.max_colwidth", 52)
fmt = res.copy()
for c in ("touch84", "ex_touch", "win"):
    fmt[c] = (fmt[c] * 100).round(1)
for c in ("ror", "ex_ror", "16-19", "20-22", "23-26", "stock", "etf", "future", "t"):
    fmt[c] = fmt[c].round(3 if c != "t" else 2)
L = [f"# Setup research: {len(bars)} symbols {cnt}; {len(d):,} symbol-days; hold-to-expiry put spread ROR, iv_mult 1.15\n",
     "ex_ror = return on risk minus the same-date universe average. t = monthly-clustered t-stat. "
     "Blocks/groups show ex_ror consistency.\n", "```", fmt.to_string(index=False), "```"]
top = res[(res.t > 2) & (res.setup != "ALL DAYS")].head(6)["setup"].tolist()
L.append("\n## Sensitivity of the leaders to the IV assumption (ex_ror)\n```")
for m in (1.0, 1.3):
    dm = rs.build(bars, groups, m)
    r2 = rs.evaluate(dm, top)
    L.append(f"iv_mult {m}:\n" + r2[["setup", "n", "ror", "ex_ror", "t", "touch84"]].round(3).to_string(index=False))
L.append("```")
os.makedirs("reports", exist_ok=True)
open("reports/setup_research.md", "w").write("\n".join(L) + "\n")
print("\n".join(L))
