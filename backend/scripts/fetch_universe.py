"""Download 10y of daily candles for a broad liquid US universe (stocks + ETFs + futures) and cache them.
Read-only. Output: data/bars_cache.pkl (git-ignored). Usage: python scripts/fetch_universe.py"""
import os
import pickle
import time

import httpx

from viking import dxlink
from viking.config import BrokerConfig
from viking.tastytrade import TastytradeBroker

STOCKS = """AAPL MSFT NVDA AMZN GOOGL META AVGO TSLA BRK/B JPM LLY V XOM UNH MA COST HD PG JNJ ORCL ABBV NFLX BAC KO CRM
CVX WMT MRK AMD CSCO PEP TMO ADBE LIN ACN MCD ABT WFC IBM GE DIS QCOM TXN VZ CAT INTU AMGN PM AXP ISRG NOW AMAT
GS MS UBER T RTX SPGI NEE LOW BKNG HON PFE PGR UNP DHR ETN COP BLK SYK TJX LMT SCHW VRTX C ADP BSX FI BA MMC PLD
MDT ADI CB MU PANW GILD SBUX DE ANET KLAC LRCX INTC MO UPS SO ICE CI DUK NKE BMY TGT CVS FDX EOG SLB MPC PSX OXY
GM F PYPL SHOP SQ COIN MRVL SNOW DDOG CRWD ABNB DASH ROKU MRNA BIIB REGN CMG LULU DG DLTR EBAY ETSY TWLO ZM DOCU
FCX NEM X CLF AA WYNN MGM LVS CCL RCL AAL DAL UAL LUV NCLH HAL KMI WMB""".split()
ETFS = "SPY QQQ IWM DIA XLF XLE XLK XLV XLY XLP XLI XLU XLB XLC XLRE SMH XBI KRE XOP XHB TLT IEF HYG LQD GLD SLV USO UNG EEM EFA FXI EWZ VNQ".split()
FUT = ["/ES:XCME", "/NQ:XCME", "/RTY:XCME", "/YM:XCBT", "/GC:XCEC", "/SI:XCEC", "/CL:XNYM", "/NG:XNYM", "/ZN:XCBT", "/ZB:XCBT"]
UNIVERSE = STOCKS + ETFS + FUT

cfg = BrokerConfig()
b = TastytradeBroker.__new__(TastytradeBroker)
b.cfg, b._token, b._expires = cfg, "", 0.0
b.http = httpx.Client(base_url=cfg.base_url, timeout=15.0)
bars, t0 = {}, time.time()
for i in range(0, len(UNIVERSE), 20):
    batch = UNIVERSE[i:i + 20]
    tok = b.http.get("/api-quote-tokens", headers=b._auth()).json()["data"]
    try:
        got = dxlink.fetch_daily(tok["dxlink-url"], tok["token"], batch, days=3650, timeout=45)
    except Exception as e:
        print("batch failed", batch[0], type(e).__name__, e)
        continue
    bars.update({k: v for k, v in got.items() if len(v) >= 600})
    print(f"{i + len(batch):3d}/{len(UNIVERSE)} got {len(got)} usable {len(bars)} ({time.time() - t0:.0f}s)", flush=True)
os.makedirs("data", exist_ok=True)
pickle.dump(bars, open("data/bars_cache.pkl", "wb"))
print("missing:", [s for s in UNIVERSE if s not in bars])
