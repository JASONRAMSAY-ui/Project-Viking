"""Phase 1: universe pre-screening funnel + global volatility gatekeeper."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import pandas as pd

from . import indicators as ind
from .config import ScreenConfig


class TermStructure(str, Enum):
    CONTANGO = "contango"
    BACKWARDATION = "backwardation"


def term_structure(front_iv: float, back_iv: float) -> TermStructure:
    """VIX / VIX3M (or any front vs back implied vol). Front above back = backwardation."""
    return TermStructure.BACKWARDATION if front_iv >= back_iv else TermStructure.CONTANGO


@dataclass
class ScreenResult:
    symbol: str
    passed: bool = False
    liquidity: bool = False
    volatility: bool = False
    temporal: bool = False
    breakout_threat: bool = False
    metrics: dict = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)


def screen_symbol(symbol: str, bars: pd.DataFrame, near_money_spreads: list[float],
                  cfg: ScreenConfig = ScreenConfig()) -> ScreenResult:
    r = ScreenResult(symbol)
    m = r.metrics

    # Filter 1: structural liquidity gate
    adv = ind.average_dollar_volume(bars, cfg.adv_window).iloc[-1]
    worst = max(near_money_spreads) if near_money_spreads else float("inf")
    m.update(adv=float(adv), worst_option_spread=float(worst))
    r.liquidity = bool(adv > cfg.min_adv_usd and worst <= cfg.max_option_spread)
    if not adv > cfg.min_adv_usd:
        r.reasons.append(f"ADV ${adv:,.0f} <= ${cfg.min_adv_usd:,.0f}")
    if not worst <= cfg.max_option_spread:
        r.reasons.append(f"near-money option spread {worst:.2f} > {cfg.max_option_spread:.2f}")

    # Filter 2: push-to-pause
    close = bars["close"]
    hv_s = ind.historical_volatility(close, cfg.hv_short).iloc[-1]
    hv_l = ind.historical_volatility(close, cfg.hv_long).iloc[-1]
    adx = ind.adx(bars, cfg.adx_period)
    adx_now = adx.iloc[-1]
    adx_falling = bool((adx.diff().tail(cfg.adx_slope_sessions) < 0).all())
    box = ind.squeeze_box(bars, cfg.squeeze_std_window, cfg.squeeze_atr_period, cfg.squeeze_atr_sma)
    in_box = bool(box.iloc[-1])
    explosion = bool(hv_s > cfg.hv_explosion_ratio * hv_l)
    exhausted = bool(adx_now < cfg.adx_max and adx_falling)
    m.update(hv20=float(hv_s), hv90=float(hv_l), adx=float(adx_now), adx_falling=adx_falling)
    r.volatility = explosion and exhausted and in_box
    if not explosion:
        r.reasons.append(f"no vol explosion (HV20 {hv_s:.2f} <= {cfg.hv_explosion_ratio}x HV90 {hv_l:.2f})")
    if not exhausted:
        r.reasons.append(f"trend not exhausted (ADX {adx_now:.1f}, falling={adx_falling})")
    if not in_box:
        r.reasons.append("not inside range squeeze box")

    # Filter 3: dynamic temporal alignment
    bis, history = ind.run_lengths(box)
    m["bis"] = bis
    if len(history) < 3:
        r.reasons.append(f"only {len(history)} historical squeezes; cannot size window")
    else:
        s = pd.Series(history, dtype=float)
        upper = float(s.mean() - cfg.bis_std_haircut * s.std(ddof=1))
        m.update(bis_mean=float(s.mean()), bis_std=float(s.std(ddof=1)), bis_upper=upper)
        r.temporal = cfg.min_bis <= bis <= upper
        r.breakout_threat = bis > upper
        if r.breakout_threat:
            r.reasons.append(f"BIS {bis} > {upper:.1f}: imminent breakout threat")
        elif not r.temporal:
            r.reasons.append(f"BIS {bis} outside window [{cfg.min_bis}, {upper:.1f}]")

    r.passed = r.liquidity and r.volatility and r.temporal
    return r


def run_screen(universe: dict[str, tuple[pd.DataFrame, list[float]]], front_iv: float,
               back_iv: float, cfg: ScreenConfig = ScreenConfig()) -> dict:
    """Gatekeeper first: in backwardation the watchlist is purged and nothing is routed."""
    ts = term_structure(front_iv, back_iv)
    if ts is TermStructure.BACKWARDATION:
        return {"term_structure": ts, "halted": True, "results": [], "watchlist": []}
    results = [screen_symbol(s, b, sp, cfg) for s, (b, sp) in universe.items()]
    return {"term_structure": ts, "halted": False, "results": results,
            "watchlist": [r.symbol for r in results if r.passed]}
