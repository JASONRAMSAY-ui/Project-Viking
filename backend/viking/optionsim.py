"""Model-based put-credit-spread simulation on real underlying history.

No historical option prices are available, so spreads are priced with Black-Scholes:
  IV0 = iv_mult x 90d realised vol (the volatility risk premium; sensitivity-tested),
  IV rises when the underlying falls (vol-on-drop), short strike solved for ~0.20 delta,
  width = width_sigma x sigma_h, cost = cost_frac x width per round trip (slippage + fees).
Results depend on these assumptions and are NOT a forecast of real fills."""
from __future__ import annotations

from dataclasses import dataclass
from math import erf, exp, log, sqrt

import numpy as np
import pandas as pd


def _N(x: float) -> float:
    return 0.5 * (1 + erf(x / sqrt(2)))


def put_price(S: float, K: float, T: float, vol: float, r: float = 0.04) -> float:
    if T <= 0:
        return max(K - S, 0.0)
    d1 = (log(S / K) + (r + vol * vol / 2) * T) / (vol * sqrt(T))
    d2 = d1 - vol * sqrt(T)
    return K * exp(-r * T) * _N(-d2) - S * _N(-d1)


@dataclass(frozen=True)
class SimConfig:
    dte_trading: int = 31          # ~45 calendar days
    iv_mult: float = 1.15
    delta_d1: float = 0.8416       # N(d1)=0.80 -> |put delta| 0.20
    width_sigma: float = 0.5
    cost_frac: float = 0.05        # of width, round trip
    vol_on_drop: float = 2.0       # IV_t = IV0 * (S0/S_t)**vol_on_drop
    skip_after: int = 10


@dataclass(frozen=True)
class Rule:
    name: str
    exit_dte: int | None = None        # close when this many trading days remain
    take_profit: float | None = None   # close at this fraction of credit captured
    stop_close_below_short: bool = False
    stop_loss_mult: float | None = None  # close when MTM loss >= mult x credit


RULES = [
    Rule("hold to expiry"),
    Rule("exit at 21 cal DTE", exit_dte=15),
    Rule("exit at 14 cal DTE", exit_dte=10),
    Rule("take profit 50%", take_profit=0.5),
    Rule("take profit 50% + exit 21 DTE", take_profit=0.5, exit_dte=15),
    Rule("stop: close below short strike", stop_close_below_short=True),
    Rule("stop: loss = 2x credit", stop_loss_mult=2.0),
    Rule("TP 50% + stop below short + 21 DTE", take_profit=0.5, stop_close_below_short=True, exit_dte=15),
]


def simulate_trade(bars: pd.DataFrame, t: int, sig: float, cfg: SimConfig, rule: Rule) -> dict | None:
    """One put credit spread entered at the close of bar t. Returns return-on-risk net of costs."""
    c = bars["close"].to_numpy()
    h = cfg.dte_trading
    if t + h >= len(c) or not sig or np.isnan(sig):
        return None
    S0 = c[t]
    iv0 = cfg.iv_mult * sig * sqrt(252)
    T0 = h / 252
    K1 = S0 * exp(0.04 * T0 + iv0 ** 2 / 2 * T0 - cfg.delta_d1 * iv0 * sqrt(T0))   # short
    width = cfg.width_sigma * sig * sqrt(h) * S0
    K2 = K1 - width
    credit = put_price(S0, K1, T0, iv0) - put_price(S0, K2, T0, iv0)
    if credit <= 0.02 * width or credit >= 0.8 * width:
        return None
    risk = width - credit
    cost = cfg.cost_frac * width
    for i in range(1, h + 1):
        S, left = c[t + i], h - i
        if left == 0:
            val = max(K1 - S, 0) - max(K2 - S, 0)
            return {"ror": (credit - val - cost) / risk, "days": i, "exit": "expiry"}
        iv = iv0 * (S0 / S) ** cfg.vol_on_drop
        val = put_price(S, K1, left / 252, iv) - put_price(S, K2, left / 252, iv)
        pnl = credit - val
        why = None
        if rule.take_profit is not None and pnl >= rule.take_profit * credit:
            why = "tp"
        elif rule.stop_loss_mult is not None and -pnl >= rule.stop_loss_mult * credit:
            why = "stop_loss"
        elif rule.stop_close_below_short and S < K1:
            why = "stop_short"
        elif rule.exit_dte is not None and left <= rule.exit_dte:
            why = "time"
        if why:
            return {"ror": (pnl - cost) / risk, "days": i, "exit": why}
    return None


def run(bars: pd.DataFrame, entry_mask: pd.Series, cfg: SimConfig, rule: Rule, start: int = 250) -> pd.DataFrame:
    sig = np.log(bars["close"]).diff().rolling(90).std().to_numpy()
    m = entry_mask.to_numpy()
    out, t = [], start
    while t < len(bars) - cfg.dte_trading - 1:
        if m[t]:
            r = simulate_trade(bars, t, sig[t], cfg, rule)
            if r:
                out.append({"date": bars.index[t], **r})
                t += cfg.skip_after
                continue
        t += 1
    return pd.DataFrame(out)


def stats(df: pd.DataFrame) -> dict:
    if df is None or not len(df):
        return {"n": 0}
    r = df["ror"]
    eq = r.cumsum()
    return {"n": len(r), "win": float((r > 0).mean()), "avg": float(r.mean()), "median": float(r.median()),
            "worst": float(r.min()), "best": float(r.max()),
            "pf": float(r[r > 0].sum() / -r[r < 0].sum()) if (r < 0).any() else float("inf"),
            "maxdd": float((eq.cummax() - eq).max()), "avg_days": float(df["days"].mean())}
