"""Congestion / POC on SHORT-dated options (2, 5, 10 trading days). Needs data/bars_cache.pkl.
A. Containment: is forward excursion smaller when price is inside the congestion band (HVN) than outside?
B. Magnet: does distance from POC predict the next h-day return (mean reversion toward POC)?
C. Placement: for a near-term short put at z sigma, does the strike sitting below the HVN floor / POC cut touches?
All results are excess over the same-date universe average; t is monthly-clustered. Daily-bar profiles (60d, 180d).
Read-only. Writes reports/short_term_levels.md."""
import os
import pickle

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

from viking import indicators as ind, research as rs

HS = (2, 5, 10)
LOOKS = (60, 180)
bars = pickle.load(open("data/bars_cache.pkl", "rb"))
rows = []
for s, df in bars.items():
    if len(df) < 800:
        continue
    c, l, h = (df[k].to_numpy() for k in ("close", "low", "high"))
    n = len(c)
    sd = np.log(df["close"]).diff().rolling(90).std().to_numpy()
    x = {"sym": np.full(n, s), "date": df.index.to_numpy(), "c": c, "sd": sd}
    for lk in LOOKS:
        poc, lo_, hi_ = (np.full(n, np.nan) for _ in range(3))
        for t in range(lk, n, 5):
            hv = ind.volume_profile_hvn(df.iloc[t - lk + 1:t + 1], lk)
            poc[t:t + 5], lo_[t:t + 5], hi_[t:t + 5] = hv["poc"], hv["low"], hv["high"]
        x[f"poc{lk}"], x[f"lo{lk}"], x[f"hi{lk}"] = poc, lo_, hi_
    for hh in HS:
        sh = sd * np.sqrt(hh)
        w = lambda a, fn: np.r_[fn(sliding_window_view(a[1:], hh), axis=1), np.full(hh, np.nan)][:n]
        fmin, fmax = w(l, np.min), w(h, np.max)
        x[f"ret{hh}"] = (np.r_[c[hh:], np.full(hh, np.nan)] / c - 1) / sh
        x[f"dn{hh}"] = (c - fmin) / c / sh
        x[f"up{hh}"] = (fmax - c) / c / sh
        for z in (0.5, 0.84, 1.28):
            x[f"t{z}_{hh}"] = np.where(np.isfinite(fmin), (fmin <= c * (1 - z * sh)).astype(float), np.nan)
    f = pd.DataFrame(x)
    f = f[~rs.glitch_mask(df).to_numpy()]
    rows.append(f)
d = pd.concat(rows, ignore_index=True)
d = d[np.isfinite(d.sd)]
d["month"] = pd.to_datetime(d["date"]).dt.to_period("M")
dates = d["date"]


def ex(col):
    return d[col] - d.groupby("date")[col].transform("mean")


def tstat(e):
    m = e.groupby("month")["v"].mean()
    return m.mean() / (m.std(ddof=1) / np.sqrt(len(m))) if len(m) > 3 and m.std(ddof=1) > 0 else np.nan


def blocks(e):
    out = []
    for a, z in (("2016", "2020"), ("2020", "2023"), ("2023", "2031")):
        s_ = e[(pd.to_datetime(e.date) >= a) & (pd.to_datetime(e.date) < z)]
        out.append(f"{s_.v.mean():+.3f}" if len(s_) >= 100 else " n/a ")
    return "/".join(out)


def line(label, mask, col, scale=1.0):
    e = d[mask & d[col].notna()].copy()
    if len(e) < 300:
        return None
    e["v"] = ex_cache[col][e.index]
    return f"{label:44s} {len(e):8d} {e.v.mean() * scale:+9.4f} {tstat(e):6.2f}  {blocks(e)}"


ex_cache = {}
for col in [f"{k}{hh}" for k in ("ret", "dn", "up") for hh in HS] + [f"t{z}_{hh}" for z in (0.5, 0.84, 1.28) for hh in HS]:
    ex_cache[col] = ex(col)
L = ["# Congestion / POC on short-dated options (daily-bar profiles; 191 symbols; excess vs same-date average)\n"]
L.append("\n## A. Containment: forward excursion (units of sigma_h) when price is INSIDE vs outside the HVN band\n"
         "Negative excess on dn/up = more contained. 'tight' = band narrower than the median band.\n```")
L.append(f"{'state / metric':44s} {'n':>8s} {'excess':>9s} {'t':>6s}  blocks")
for lk in LOOKS:
    inside = (d.c >= d[f"lo{lk}"]) & (d.c <= d[f"hi{lk}"])
    width = (d[f"hi{lk}"] - d[f"lo{lk}"]) / d.c
    tight = inside & (width < width[inside].median())
    for hh in HS:
        for lab, m in ((f"{lk}d inside band", inside), (f"{lk}d inside, TIGHT band", tight), (f"{lk}d above band", d.c > d[f"hi{lk}"]), (f"{lk}d below band", d.c < d[f"lo{lk}"])):
            for met in ("dn", "up"):
                r = line(f"h={hh:2d} {lab} {met}", m, f"{met}{hh}")
                if r:
                    L.append(r)
L.append("```\n\n## B. Magnet: excess next-h return (sigma_h units) by distance of price from POC (u=(price-POC)/sigma_h)\n"
         "If POC pulls price back, u>0 should show negative excess return and u<0 positive.\n```")
L.append(f"{'bucket':44s} {'n':>8s} {'excess':>9s} {'t':>6s}  blocks")
for lk in LOOKS:
    for hh in HS:
        u = (d.c - d[f"poc{lk}"]) / (d.c * d.sd * np.sqrt(hh))
        for a, z in ((-99, -1), (-1, -0.5), (-0.5, 0), (0, 0.5), (0.5, 1), (1, 99)):
            r = line(f"h={hh:2d} {lk}d u in ({a:g},{z:g}]", (u > a) & (u <= z), f"ret{hh}")
            if r:
                L.append(r)
L.append("```\n\n## C. Placement: near-term short put at z sigma_h. Excess TOUCH probability when strike is BELOW the level (protected) vs above it\n"
         "Negative excess touch = fewer touches. Level counts only if it lies between price and strike or just under the strike.\n```")
L.append(f"{'case':44s} {'n':>8s} {'ex touch':>9s} {'t':>6s}  blocks")
for lk in LOOKS:
    for hh in HS:
        for z in (0.5, 0.84, 1.28):
            K = d.c * (1 - z * d.sd * np.sqrt(hh))
            for nm, lev in ((f"HVN floor {lk}d", d[f"lo{lk}"]), (f"POC {lk}d", d[f"poc{lk}"])):
                valid = (lev < d.c) & lev.notna()
                prot = valid & (lev > K)              # level between price and strike -> strike below support
                unprot = valid & (lev <= K)           # level below the strike
                for lab, m in ((f"strike BELOW {nm}", prot), (f"strike ABOVE {nm}", unprot)):
                    r = line(f"h={hh:2d} z={z} {lab}", m, f"t{z}_{hh}", scale=100)
                    if r:
                        L.append(r + "  (pp)")
L.append("```")
os.makedirs("reports", exist_ok=True)
open("reports/short_term_levels.md", "w").write("\n".join(L) + "\n")
print(f"rows {len(d):,}")
