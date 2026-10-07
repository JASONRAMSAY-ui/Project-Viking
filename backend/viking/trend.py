"""Phase 1 candidate signal: a recent break of an established DOWNtrend.

STATUS: UNVALIDATED. The 11-symbol backtest below looked promising, but a 191-symbol test with same-date
controls (reports/setup_research.md) found no edge. Treat `signal` in the live view as an information flag.

Backtested on ~10y of daily data (scripts/sweep_trend_break.py): put strikes at ~0.20 delta were
touched far less often after such a break than on drift-matched control days, in both the
2016-2022 fit and the 2023+ test. The call-side mirror showed no edge, so phase 1 is put-only."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from . import indicators as ind


@dataclass(frozen=True)
class TrendConfig:
    sma: int = 50
    adx_min: float = 30.0
    frac: float = 0.9      # share of the lookback closed below the average
    lookback: int = 60
    window: int = 5        # signal stays active this many sessions after the break


def downtrend_break(bars: pd.DataFrame, cfg: TrendConfig = TrendConfig()) -> dict:
    c = bars["close"]
    sma = c.rolling(cfg.sma).mean()
    below = (c < sma).astype(float).rolling(cfg.lookback).mean().shift(1)
    adx_peak = ind.adx(bars, 14).rolling(cfg.lookback).max().shift(1)
    est = (below >= cfg.frac) & (adx_peak > cfg.adx_min) & (sma.diff(10).shift(1) < 0)
    broke = est & (c > sma)
    recent = broke.rolling(cfg.window, min_periods=1).max().astype(bool)
    idx = [i for i, v in enumerate(broke.to_numpy()) if v]
    return {"active": bool(recent.iloc[-1]),
            "days_since_break": (len(c) - 1 - idx[-1]) if idx else None,
            "established_downtrend": bool(est.iloc[-1]),
            "sma": float(sma.iloc[-1]) if pd.notna(sma.iloc[-1]) else None}
