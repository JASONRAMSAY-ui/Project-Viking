"""Resolve expired paper trades from real daily prices and summarise (read-only).
Usage: python scripts/paper_resolve.py"""
import json
import os

import httpx
import numpy as np
import pandas as pd

from viking import dxlink, papertrade as pt
from viking.config import BrokerConfig
from viking.live import LiveRuntime
from viking.tastytrade import TastytradeBroker

rows = [json.loads(l) for l in open(pt.LOG)] if os.path.exists(pt.LOG) else []
if not rows:
    raise SystemExit("no paper trades logged yet")
rt = LiveRuntime()
tok = rt._get("/api-quote-tokens")
syms = sorted({r["symbol"] for r in rows})
wire = {s: (rt._future_meta(s)["bar"] if s.startswith("/") else s) for s in syms}
got = dxlink.fetch_daily(tok["dxlink-url"], tok["token"], list(wire.values()), days=400, timeout=30)
bars = {s: got[w] for s, w in wire.items() if w in got}
d = pt.resolve(rows, bars)
print(f"logged {len(rows)}  resolved {len(d)}")
if len(d):
    for nm in ("credit_mid", "credit_natural"):
        r = d[f"ror_{nm}"]
        print(f"{nm:15s} n={len(r)} win={np.mean(r > 0):.0%} avg ROR={r.mean():+.3f} worst={r.min():+.2f} touched short={d.touched_short.mean():.0%}")
    d.to_csv("paper/paper_results.csv", index=False)
