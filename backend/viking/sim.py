"""Deterministic synthetic market data so the engine and console run with no credentials."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .optimizer import OptionQuote


def synthetic_bars(n=400, seed=0, start=100.0, shock_ago=22, calm=0.004, shock=0.02,
                   volume=5_000_000) -> pd.DataFrame:
    """Regime-switching random walk: periodic short vol bursts through history (so completed
    squeezes exist), then a final shock `shock_ago` bars ago followed by consolidation."""
    rng = np.random.default_rng(seed)
    vol = np.full(n, calm)
    pos = int(rng.integers(20, 40))
    while pos < n - 60:
        vol[pos : pos + int(rng.integers(6, 12))] = shock * rng.uniform(0.6, 1.0)
        pos += int(rng.integers(30, 55))
    vol[n - shock_ago : n - shock_ago + 8] = shock
    ret = rng.normal(0, vol)
    close = start * np.exp(np.cumsum(ret))
    spread = np.abs(rng.normal(0, 1, n)) * vol * close * 0.8 + 0.001 * close
    high, low = close + spread, close - spread
    open_ = np.r_[start, close[:-1]]
    vols = rng.integers(int(volume * 0.7), int(volume * 1.3), n)
    idx = pd.bdate_range(end="2026-10-02", periods=n)
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close,
                         "volume": vols}, index=idx)


def synthetic_chain(spot: float, put_iv=0.30, call_iv=0.22, strike_step=1.0) -> list[OptionQuote]:
    """Roughly BS-shaped deltas with skewed wings; good enough for exercising the optimiser."""
    from math import erf, sqrt
    cdf = lambda x: 0.5 * (1 + erf(x / sqrt(2)))
    t = 30 / 365
    out = []
    for k in np.arange(round(spot * 0.8), round(spot * 1.2) + strike_step, strike_step):
        for right in ("P", "C"):
            iv = put_iv if (right == "P") else call_iv
            otm = (spot - k) if right == "P" else (k - spot)
            if otm <= 0:
                continue
            z = otm / (spot * iv * sqrt(t))
            delta = cdf(-z) * (-1 if right == "P" else 1) * 1.0
            price = max(spot * iv * sqrt(t) * 0.4 * np.exp(-0.5 * z * z) - otm * cdf(-z) * 0.5, 0.05)
            out.append(OptionQuote(float(k), right, round(price - 0.02, 2), round(price + 0.02, 2),
                                   float(delta), -price * 0.04))
    return out
