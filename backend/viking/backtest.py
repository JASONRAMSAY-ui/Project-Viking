"""Backtest the screen on real daily history (underlying price only, no option P&L).

For each day the screen is run on data up to that day. Outcome over the next HORIZON trading days:
  touch  - price traded beyond +/- k sigma of the entry price at any time (a short strike at
           ~0.20 delta sits at about k=0.84 sigma; sigma = realised 20d vol scaled to the horizon)
  finish - the close at the horizon is beyond that band
Signal days are compared with every other day, so the screen has to beat the base rate."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import indicators as ind
from .screening import screen_symbol

HORIZON = 21     # trading days, ~30 calendar days
K_SIGMA = 0.84   # ~0.20 delta short strike
WINDOW = 400


def evaluate_symbol(bars: pd.DataFrame, horizon: int = HORIZON, k: float = K_SIGMA) -> pd.DataFrame:
    rows = []
    close = bars["close"].to_numpy()
    hi, lo = bars["high"].to_numpy(), bars["low"].to_numpy()
    for t in range(150, len(bars) - horizon):
        r = screen_symbol("x", bars.iloc[max(0, t + 1 - WINDOW): t + 1], [0.0])
        if "hv20" not in r.metrics:
            continue
        sigma = r.metrics["hv20"] * np.sqrt(horizon / 252)
        up, dn = close[t] * (1 + k * sigma), close[t] * (1 - k * sigma)
        win_hi, win_lo = hi[t + 1: t + 1 + horizon].max(), lo[t + 1: t + 1 + horizon].min()
        end = close[t + horizon]
        rows.append({
            "date": bars.index[t], "volatility": r.volatility, "temporal": r.temporal,
            "breakout_threat": r.breakout_threat, "signal": r.volatility and r.temporal,
            "touch_put": win_lo <= dn, "touch_call": win_hi >= up,
            "touch_either": win_lo <= dn or win_hi >= up,
            "finish_outside": end < dn or end > up,
            "fwd_move_sigma": abs(end / close[t] - 1) / sigma if sigma else np.nan})
    return pd.DataFrame(rows)


def episodes(sig: pd.Series, gap: int = 5) -> int:
    """Number of distinct signal episodes (signals closer than `gap` days count as one)."""
    idx = np.flatnonzero(sig.to_numpy())
    return int(1 + (np.diff(idx) > gap).sum()) if len(idx) else 0


def summarise(df: pd.DataFrame) -> dict:
    out = {}
    for name, mask in (("all days", df.index == df.index), ("volatility filter", df["volatility"]),
                       ("temporal filter", df["temporal"]), ("SIGNAL (vol+temporal)", df["signal"]),
                       ("breakout threat", df["breakout_threat"])):
        d = df[mask]
        out[name] = {"days": len(d), "episodes": episodes(mask) if name != "all days" else None,
                     "touch_either": d["touch_either"].mean() if len(d) else np.nan,
                     "finish_outside": d["finish_outside"].mean() if len(d) else np.nan,
                     "avg_move_sigma": d["fwd_move_sigma"].mean() if len(d) else np.nan}
    return out
