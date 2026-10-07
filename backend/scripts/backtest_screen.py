"""Backtest the screen on real daily candles. Read-only. Usage: python scripts/backtest_screen.py [SYMBOLS...]"""
import sys

import httpx
import pandas as pd

from viking import dxlink
from viking.backtest import evaluate_symbol, summarise
from viking.config import BrokerConfig
from viking.tastytrade import TastytradeBroker

cfg = BrokerConfig()
b = TastytradeBroker.__new__(TastytradeBroker)
b.cfg, b._token, b._expires = cfg, "", 0.0
b.http = httpx.Client(base_url=cfg.base_url, timeout=15.0)
tok = b.http.get("/api-quote-tokens", headers=b._auth()).json()["data"]
syms = sys.argv[1:] or ["SPY", "IWM", "QQQ", "XLF", "TLT", "GLD", "/ES:XCME", "/NQ:XCME", "/GC:XCEC", "/CL:XNYM", "/ZN:XCBT"]
bars = dxlink.fetch_daily(tok["dxlink-url"], tok["token"], syms, days=3650, timeout=40)
allr = []
for s in syms:
    if s not in bars or len(bars[s]) < 300:
        print(s, "insufficient history", len(bars.get(s, [])))
        continue
    df = evaluate_symbol(bars[s])
    df["symbol"] = s
    allr.append(df)
    sm = summarise(df)["SIGNAL (vol+temporal)"]
    print(f"{s:10s} bars={len(bars[s])} signal_days={sm['days']} episodes={sm['episodes']}", flush=True)
df = pd.concat(allr)
df.to_pickle("/tmp/viking_backtest.pkl")
print()
for k, v in summarise(df).items():
    print(f"{k:24s} days={v['days']:6d} episodes={v['episodes']} touch={v['touch_either']:.1%} "
          f"finish_outside={v['finish_outside']:.1%} avg|move|={v['avg_move_sigma']:.2f}σ")
