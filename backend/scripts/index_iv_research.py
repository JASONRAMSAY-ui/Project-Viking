"""Real-implied-vol test on index products (no IV model): SPY,/ES use VIX; IWM,/RTY use RVX; DIA,/YM use VXD.
Put credit spread priced with the real 30d index IV x a put-skew multiplier, held to expiry (21 trading days).
Compares volatility-regime and chart setups. Read-only. Writes reports/index_iv_research.md.
Needs data/bars_cache.pkl (fetch_universe.py)."""
import os
import pickle

import httpx
import numpy as np
import pandas as pd

from viking import dxlink, indicators as ind, research as rs
from viking.config import BrokerConfig
from viking.tastytrade import TastytradeBroker

H, D1, COST = 21, 0.8416, 0.05
bars = pickle.load(open("data/bars_cache.pkl", "rb"))
cfg = BrokerConfig(); b = TastytradeBroker.__new__(TastytradeBroker); b.cfg, b._token, b._expires = cfg, "", 0.0
b.http = httpx.Client(base_url=cfg.base_url, timeout=15.0)
tok = b.http.get("/api-quote-tokens", headers=b._auth()).json()["data"]
ivx = dxlink.fetch_daily(tok["dxlink-url"], tok["token"], ["VIX", "VIX3M", "RVX", "VXD"], days=3650, timeout=40)
PAIRS = [("SPY", "VIX"), ("/ES:XCME", "VIX"), ("IWM", "RVX"), ("/RTY:XCME", "RVX"), ("DIA", "VXD"), ("/YM:XCBT", "VXD")]


def frame(sym, ivs, skew):
    df = bars[sym]
    iv = ivx[ivs]["close"].reindex(df.index).ffill() / 100
    c, lo = df["close"], df["low"]
    T0 = H / 252
    iv0 = iv * skew
    K1 = c * np.exp(0.04 * T0 + iv0 ** 2 / 2 * T0 - D1 * iv0 * np.sqrt(T0))
    width = 0.5 * iv * np.sqrt(T0) * c
    K2 = K1 - width
    credit = rs.put_price(c, K1, T0, iv0) - rs.put_price(c, K2, T0, iv0)
    ST = c.shift(-H)
    pay = (K1 - ST).clip(lower=0) - (K2 - ST).clip(lower=0)
    ror = (credit - pay - COST * width) / (width - credit)
    fmin = pd.concat([lo.shift(-i) for i in range(1, H + 1)], axis=1).min(axis=1)
    ok = ror.notna() & fmin.notna() & iv.notna() & (credit > 0.02 * width) & (credit < 0.8 * width)
    ret = np.log(c).diff()
    hv20 = ret.rolling(20).std() * np.sqrt(252)
    hv90 = ret.rolling(90).std() * np.sqrt(252)
    ivr = (iv - iv.rolling(252).min()) / (iv.rolling(252).max() - iv.rolling(252).min())
    v3 = (ivx["VIX3M"]["close"].reindex(df.index).ffill() / 100)
    f = rs.setups(df, bars.get("SPY"))
    S = {
        "ALL DAYS": c == c,
        "IV rank > 50": ivr > 0.5, "IV rank > 30": ivr > 0.3, "IV rank < 20": ivr < 0.2,
        "IV > realised 20d (VRP>0)": iv > hv20, "IV > 1.3x realised 20d": iv > 1.3 * hv20, "IV < realised 20d": iv < hv20,
        "IV spiked then falling (max10d>1.3x now, below 5d ago)": (iv.rolling(10).max() > 1.3 * iv) & (iv < iv.shift(5)),
        "IV falling 5d & IV rank>30": (iv < iv.shift(5)) & (ivr > 0.3),
        "IV spike day (>+15% in 1d)": iv > 1.15 * iv.shift(1),
        "VIX3M>VIX (contango)": (v3 > ivx["VIX"]["close"].reindex(df.index).ffill() / 100),
        "hv20/hv90 > 1.5 & close>20d": f["vol shock recovery (hv20/hv90>1.5, >20d, RSI>50)"],
        "quiet (hv20/hv90<0.7)": f["quiet (hv20/hv90<0.7)"],
        "downtrend break (phase1)": f["downtrend break (phase1: sma50 adx30 90% 60d)"],
        "capitulation day then up": f["capitulation: -2.5sd day, then up close"],
        "RSI<30": f["RSI<30"], "uptrend + RSI<40": f["uptrend + RSI<40"],
    }
    out = pd.DataFrame({k: v.fillna(False).astype(bool) for k, v in S.items()})
    out["ror"], out["touch"] = ror, (fmin <= c * (1 - 0.84 * iv * np.sqrt(T0)))
    out["sym"] = sym
    out["date"] = df.index
    return out[ok]


L = ["# Index put-spread research on REAL implied vol (hold to expiry, return on risk net of 5% cost)\n",
     "SPY,/ES: VIX; IWM,/RTY: RVX; DIA,/YM: VXD. Skew = put IV / index ATM IV. 6 series but only 3 independent underlyings.\n"]
for skew in (1.0, 1.12, 1.25):
    d = pd.concat([frame(s, i, skew) for s, i in PAIRS], ignore_index=True)
    d["month"] = d["date"].dt.to_period("M")
    names = [c for c in d.columns if c not in ("ror", "touch", "sym", "date", "month")]
    rows = []
    base = d["ror"].mean()
    for nm in names:
        e = d[d[nm]]
        if len(e) < 100:
            continue
        mon = e.groupby("month")["ror"].mean()
        t = (mon.mean()) / (mon.std(ddof=1) / np.sqrt(len(mon))) if len(mon) > 3 else np.nan
        r = {"setup": nm, "n": len(e), "touch%": 100 * e.touch.mean(), "win%": 100 * (e.ror > 0).mean(),
             "avg_ror": e.ror.mean(), "vs_all": e.ror.mean() - base, "worst": e.ror.min(), "t(vs0)": t}
        for blk, a, z in (("16-19", "2016", "2020"), ("20-22", "2020", "2023"), ("23-26", "2023", "2031")):
            s_ = e[(e.date >= a) & (e.date < z)]
            r[blk] = s_.ror.mean() if len(s_) >= 30 else np.nan
        rows.append(r)
    res = pd.DataFrame(rows).sort_values("avg_ror", ascending=False)
    L += [f"\n## Put skew multiplier {skew}\n```", res.round(3).to_string(index=False), "```"]
os.makedirs("reports", exist_ok=True)
open("reports/index_iv_research.md", "w").write("\n".join(L) + "\n")
print("\n".join(L))
