"""Does support matter for put-spread strike placement?  Needs data/bars_cache.pkl.
Test 1 (placement): fix the short strike at 0.84 sigma (21d). For each support-level type compute where the
  level sits relative to that strike: p = (level - strike) / sigma_h. p>0 means the level is between price and
  strike (strike BELOW support); p<0 means the strike sits above the level. Compare touch rate / return on risk
  across p buckets, as excess over the same-date universe average.
Test 2 (reaction): when price tests a support level and holds, does the next 10d return beat the same-date average?
Read-only. Writes reports/levels_research.md."""
import os
import pickle

import numpy as np
import pandas as pd

from viking import indicators as ind, research as rs

H, Z = 21, 0.84
bars = pickle.load(open("data/bars_cache.pkl", "rb"))
ETF = set("SPY QQQ IWM DIA XLF XLE XLK XLV XLY XLP XLI XLU XLB XLC XLRE SMH XBI KRE XOP XHB TLT IEF HYG LQD GLD SLV USO UNG EEM EFA FXI EWZ VNQ".split())
LEVELS = ["swing low (5-bar fractal, 252d)", "20d low", "60d low", "252d low", "HVN floor (180d profile)", "POC (180d profile)",
          "AVWAP from 252d low", "50d SMA", "200d SMA", "round number"]


def roll_min_prev(a, n):
    return pd.Series(a).rolling(n).min().shift(1).to_numpy()


def swing_levels(l, c):
    n = len(l)
    piv = [i for i in range(5, n - 5) if l[i] == l[i - 5:i + 6].min()]
    pidx = np.array(piv)
    pval = l[pidx] if len(pidx) else np.array([])
    conf = pidx + 5
    out = np.full(n, np.nan)
    for t in range(n):
        if not len(pidx):
            break
        b = np.searchsorted(conf, t, side="right")
        a = np.searchsorted(pidx, t - 252, side="left")
        if b <= a:
            continue
        v = pval[a:b]
        v = v[v < c[t]]
        if len(v):
            out[t] = v.max()
    return out


def levels_for(df):
    c, l, h, v = (df[k].to_numpy() for k in ("close", "low", "high", "volume"))
    n = len(c)
    L = {"swing low (5-bar fractal, 252d)": swing_levels(l, c), "20d low": roll_min_prev(l, 20),
         "60d low": roll_min_prev(l, 60), "252d low": roll_min_prev(l, 252)}
    floor_, poc = np.full(n, np.nan), np.full(n, np.nan)
    for t in range(180, n, 10):
        hv = ind.volume_profile_hvn(df.iloc[t - 179:t + 1], 180)
        floor_[t:t + 10], poc[t:t + 10] = hv["low"], hv["poc"]
    L["HVN floor (180d profile)"], L["POC (180d profile)"] = floor_, poc
    tp = (h + l + c) / 3
    cpv, cv = np.cumsum(tp * v), np.cumsum(v)
    av = np.full(n, np.nan)
    if n > 252:
        from numpy.lib.stride_tricks import sliding_window_view
        am = sliding_window_view(l, 252).argmin(axis=1)
        t = np.arange(251, n)
        a = t - 251 + am
        prev = np.where(a > 0, cpv[np.maximum(a - 1, 0)], 0.0), np.where(a > 0, cv[np.maximum(a - 1, 0)], 0.0)
        av[251:] = (cpv[t] - prev[0]) / np.maximum(cv[t] - prev[1], 1e-9)
    L["AVWAP from 252d low"] = av
    L["50d SMA"] = pd.Series(c).rolling(50).mean().to_numpy()
    L["200d SMA"] = pd.Series(c).rolling(200).mean().to_numpy()
    step = 10 ** np.floor(np.log10(c)) / 2
    rn = np.floor(c / step) * step
    L["round number"] = np.where(rn >= c, rn - step, rn)
    return L


rows = []
for s, df in bars.items():
    if len(df) < 800:
        continue
    o = rs.outcomes(df, 1.15, 0.0)
    c = df["close"].to_numpy()
    sd = np.log(df["close"]).diff().rolling(90).std().to_numpy()
    sh = c * sd * np.sqrt(H)
    K = c * (1 - Z * sd * np.sqrt(H))
    fwd10 = (pd.Series(c).shift(-10).to_numpy() / c - 1) / (sd * np.sqrt(10))
    x = pd.DataFrame({"sym": s, "group": "etf" if s in ETF else "future" if s.startswith("/") else "stock",
                      "date": df.index, "ror": o["ror"].to_numpy(), "touch": o["touch84"].astype(float).to_numpy(), "r10": fwd10})
    lows = df["low"].to_numpy()
    for nm, Lv in levels_for(df).items():
        ok = np.isfinite(Lv) & (Lv < c)
        x["p:" + nm] = np.where(ok, (Lv - K) / sh, np.nan)
        # held test: yesterday's level, today's low pierced/approached it but the close stayed above
        Lp = np.r_[np.nan, Lv[:-1]]
        near = np.isfinite(Lp) & (lows <= Lp + 0.25 * c * sd) & (c > Lp)
        broke = np.isfinite(Lp) & (c < Lp - 0.25 * c * sd)
        x["held:" + nm], x["broke:" + nm] = near, broke
    rows.append(x[np.isfinite(x["ror"]) & np.isfinite(x["touch"])])
d = pd.concat(rows, ignore_index=True)
d["ex_ror"] = d["ror"] - d.groupby("date")["ror"].transform("mean")
d["ex_touch"] = d["touch"] - d.groupby("date")["touch"].transform("mean")
d["ex_r10"] = d["r10"] - d.groupby("date")["r10"].transform("mean")
d["month"] = d["date"].dt.to_period("M")
BUCK = [(-9, -0.5, "strike >0.5σ ABOVE level"), (-0.5, 0, "strike just above level"), (0, 0.25, "strike 0-0.25σ BELOW level"),
        (0.25, 0.5, "strike 0.25-0.5σ below"), (0.5, 0.85, "strike >0.5σ below (level near price)")]


def tstat(e, col):
    m = e.groupby("month")[col].mean()
    return m.mean() / (m.std(ddof=1) / np.sqrt(len(m))) if len(m) > 3 and m.std(ddof=1) > 0 else np.nan


def blocks(e, col):
    out = []
    for a, z in (("2016", "2020"), ("2020", "2023"), ("2023", "2031")):
        s_ = e[(e.date >= a) & (e.date < z)]
        out.append(f"{s_[col].mean():+.3f}" if len(s_) >= 50 else "  n/a ")
    return "/".join(out)


L = ["# Do support levels matter for put-spread strike placement?  (191 symbols, strike fixed at 0.84σ/21d)\n",
     "p = (level - strike)/σh. Excess = minus same-date universe average. t = monthly clustered. Blocks = 2016-19/2020-22/2023-26 ex_ror.\n"]
for nm in LEVELS:
    L.append(f"\n## {nm}\n```")
    L.append(f"{'bucket':40s} {'n':>7s} {'touch%':>7s} {'ex_touch':>9s} {'ex_ror':>8s} {'t':>6s}  blocks(ex_ror)")
    for a, z, lab in BUCK:
        e = d[(d["p:" + nm] > a) & (d["p:" + nm] <= z)]
        if len(e) < 200:
            continue
        L.append(f"{lab:40s} {len(e):7d} {100 * e.touch.mean():7.1f} {100 * e.ex_touch.mean():+8.1f}p {e.ex_ror.mean():+8.3f} {tstat(e, 'ex_ror'):6.2f}  {blocks(e, 'ex_ror')}")
    L.append("```")
L.append("\n# Reaction test: price tests support and the close holds above it -> next 10d return (σ units), excess vs same date\n```")
L.append(f"{'level':36s} {'held n':>7s} {'ex_r10':>8s} {'t':>6s} | {'broke n':>7s} {'ex_r10':>8s} {'t':>6s}")
for nm in LEVELS:
    h_, b_ = d[d["held:" + nm]].dropna(subset=["ex_r10"]), d[d["broke:" + nm]].dropna(subset=["ex_r10"])
    L.append(f"{nm:36s} {len(h_):7d} {h_.ex_r10.mean():+8.3f} {tstat(h_, 'ex_r10'):6.2f} | {len(b_):7d} {b_.ex_r10.mean():+8.3f} {tstat(b_, 'ex_r10'):6.2f}")
L.append("```")
os.makedirs("reports", exist_ok=True)
open("reports/levels_research.md", "w").write("\n".join(L) + "\n")
print("\n".join(L))
