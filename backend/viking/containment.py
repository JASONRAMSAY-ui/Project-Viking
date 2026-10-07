"""Historical containment profile of an asset: how far price actually travels against a short
vertical over different horizons, how often a strike distance holds, and when breaches happen.

Distances are in daily-vol sigma units: z * sigma_d * sqrt(h), sigma_d = 90d realised daily vol,
so the same z means the same thing across assets and horizons (z=0.84 ~ 0.20 delta, z=1.28 ~ 0.10)."""
from __future__ import annotations

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

HORIZONS = (5, 10, 21, 30, 45)
ZS = (0.5, 0.84, 1.0, 1.28, 1.65, 2.0)
QS = (50, 75, 90, 95, 99)


def daily_sigma(bars: pd.DataFrame, n: int = 90) -> pd.Series:
    return np.log(bars["close"]).diff().rolling(n).std()


def _fwd(arr: np.ndarray, h: int, fn) -> np.ndarray:
    """fn over arr[t+1 : t+1+h] for each t; NaN where the window is incomplete."""
    out = np.full(len(arr), np.nan)
    if len(arr) > h + 1:
        w = sliding_window_view(arr[1:], h)
        out[: len(w)] = fn(w, axis=1)[: len(arr)]
        out[len(w):] = np.nan
    return out


def _side(bars, side):
    return (bars["low"].to_numpy(), np.min) if side == "down" else (bars["high"].to_numpy(), np.max)


def excursion(bars: pd.DataFrame, h: int, side: str = "down") -> pd.Series:
    """Worst move against the position over the next h sessions, as a positive fraction of the close."""
    arr, fn = _side(bars, side)
    ext = _fwd(arr, h, fn)
    c = bars["close"].to_numpy()
    adverse = (1 - ext / c) if side == "down" else (ext / c - 1)
    return pd.Series(np.maximum(adverse, 0), index=bars.index)


def contained(bars: pd.DataFrame, h: int, z: float, side: str = "down", mask=None) -> tuple[int, float]:
    """(n, P(strike at z sigma_h is never touched within h sessions))."""
    mae = excursion(bars, h, side)
    dist = z * daily_sigma(bars) * np.sqrt(h)
    ok = mae.notna() & dist.notna()
    if mask is not None:
        ok &= mask
    n = int(ok.sum())
    return n, float((mae[ok] < dist[ok]).mean()) if n else float("nan")


def profile(bars: pd.DataFrame, side: str = "down", mask=None, horizons=HORIZONS, zs=ZS) -> dict:
    out = {}
    sd = daily_sigma(bars)
    for h in horizons:
        mae = excursion(bars, h, side)
        ok = mae.notna() & sd.notna()
        if mask is not None:
            ok &= mask
        m = mae[ok]
        out[h] = {"n": int(ok.sum()),
                  "mae_pct": {q: float(np.percentile(m, q) * 100) if len(m) else float("nan") for q in QS},
                  "contained": {z: contained(bars, h, z, side, mask)[1] for z in zs}}
    return out


def first_touch_timing(bars: pd.DataFrame, z: float = 0.84, h0: int = 21, hmax: int = 45,
                       side: str = "down", mask=None, marks=(5, 10, 21, 30, 45)) -> dict:
    """Strike set at z sigma for horizon h0. Of the paths that touch it within hmax sessions: what share
    have already touched by each mark, and what share of those paths ever recovered (close back
    beyond the strike at hmax)."""
    arr, _ = _side(bars, side)
    c = bars["close"].to_numpy()
    sd = daily_sigma(bars).to_numpy()
    n = len(c)
    first = np.full(n, np.nan)
    recovered = np.full(n, np.nan)
    for t in range(n - hmax):
        if np.isnan(sd[t]) or (mask is not None and not mask[t]):
            continue
        d = z * sd[t] * np.sqrt(h0)
        k = c[t] * (1 - d) if side == "down" else c[t] * (1 + d)
        w = arr[t + 1: t + 1 + hmax]
        hit = np.flatnonzero(w <= k if side == "down" else w >= k)
        if len(hit):
            first[t] = hit[0] + 1
            end = c[t + hmax]
            recovered[t] = (end > k) if side == "down" else (end < k)
    touched = first[~np.isnan(first)]
    if not len(touched):
        return {"touches": 0}
    return {"touches": int(len(touched)),
            "by_day": {m: float((touched <= m).mean()) for m in marks},
            "median_day": float(np.median(touched)),
            "recovered_by_hmax": float(np.nanmean(recovered))}
