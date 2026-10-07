"""Phase 2: skew-adjusted delta targeting and Option Setup Quality Score (OSQS)."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .config import OptimizerConfig


def calculate_skew_adjusted_deltas(target_base_delta=0.20, put_iv_25d=0.22, call_iv_25d=0.16,
                                   atm_iv: float | None = None, max_shift: float = 0.08) -> dict:
    """Each wing moves further OTM only by its own excess IV over ATM, so heavy put skew widens
    the put side without touching the call side. atm_iv defaults to the wings' average."""
    atm = atm_iv if atm_iv else (put_iv_25d + call_iv_25d) / 2
    shift = lambda iv: float(np.clip((iv / atm - 1.0) * 0.5, 0.0, max_shift)) if atm > 0 else 0.0
    return {"target_put_delta": round(target_base_delta - shift(put_iv_25d), 3),
            "target_call_delta": round(target_base_delta - shift(call_iv_25d), 3)}


@dataclass(frozen=True)
class OptionQuote:
    strike: float
    right: str  # "P" or "C"
    bid: float
    ask: float
    delta: float  # signed; puts negative
    theta: float  # per-share per-day, negative for longs

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2


@dataclass
class Setup:
    kind: str  # "put_spread" | "call_spread" | "iron_condor"
    legs: list  # [(OptionQuote, +1 long / -1 short)]
    width: float
    credit: float
    pop: float
    max_short_delta: float
    theta_per_day: float  # net, positive when the position decays in our favour
    components: dict = field(default_factory=dict)
    penalised: bool = False
    osqs: float = 0.0


def _wing(shorts_and_longs: list) -> tuple[float, float]:
    """Credit and theta of one vertical: short - long."""
    (s, l) = shorts_and_longs
    return s.mid - l.mid, l.theta - s.theta


def _threshold_score(value: float, threshold: float) -> float:
    """0.5 exactly at the threshold, rising to 1.0 at 2x, falling linearly to 0 at 0."""
    if value <= 0:
        return 0.0
    if value < threshold:
        return 0.5 * value / threshold
    return min(1.0, 0.5 + 0.5 * (value - threshold) / threshold)


def score_setup(setup: Setup, ivr: float, premium_trend: float,
                cfg: OptimizerConfig = OptimizerConfig()) -> Setup:
    """premium_trend: slope of the multi-day implied premium base (>0 expanding / <0 contracting
    as a fraction per day). Flat or expanding is down-scored."""
    w = cfg.weights
    pop_s = float(np.clip((setup.pop - 0.60) / 0.30, 0, 1))

    width_cap = setup.width
    if setup.kind == "iron_condor":
        yield_ratio = setup.credit / width_cap
        y_thr = cfg.min_condor_yield
    else:
        yield_ratio = setup.credit / (width_cap - setup.credit)  # credit / max risk
        y_thr = cfg.min_vertical_yield
    yield_s = _threshold_score(yield_ratio, y_thr)

    # Expected value per unit of risk, assuming a breached short loses the full width.
    risk = max(width_cap - setup.credit, 1e-9)
    ev_ratio = (setup.pop * setup.credit - (1 - setup.pop) * risk) / risk
    ev_s = float(np.clip(0.5 + ev_ratio / 0.2, 0, 1))

    theta_ratio = setup.theta_per_day / setup.credit if setup.credit > 0 else 0.0
    theta_s = _threshold_score(theta_ratio, cfg.min_theta_ratio)

    if ivr <= cfg.min_ivr:
        ivr_s = 0.5 * max(ivr, 0.0) / cfg.min_ivr
    else:
        ivr_s = 0.5 + 0.5 * min((ivr - cfg.min_ivr) / (100 - cfg.min_ivr), 1.0)
    trend_factor = 0.4 if premium_trend >= 0 else float(np.clip(0.6 + min(-premium_trend, 0.05) * 8, 0.6, 1.0))
    vega_s = ivr_s * trend_factor

    setup.components = {"pop": pop_s, "yield": yield_s, "ev": ev_s, "ev_ratio": ev_ratio, "theta": theta_s, "vega": vega_s,
                        "yield_ratio": yield_ratio, "theta_ratio": theta_ratio}
    raw = pop_s * w["pop"] + yield_s * w["yield"] + ev_s * w["ev"] + theta_s * w["theta"] + vega_s * w["vega"]
    setup.penalised = setup.max_short_delta > cfg.max_short_delta or setup.pop < cfg.min_pop
    setup.osqs = raw * (cfg.penalty if setup.penalised else 1.0)
    return setup


def _nearest(quotes: list[OptionQuote], target_abs_delta: float) -> OptionQuote:
    return min(quotes, key=lambda q: abs(abs(q.delta) - target_abs_delta))


def build_candidates(chain: list[OptionQuote], put_iv_25d: float, call_iv_25d: float,
                     widths=(1.0, 2.0, 5.0), cfg: OptimizerConfig = OptimizerConfig(),
                     atm_iv: float | None = None) -> list[Setup]:
    """Short strikes land at the skew-adjusted deltas; longs are `width` further OTM."""
    tgt = calculate_skew_adjusted_deltas(cfg.base_delta, put_iv_25d, call_iv_25d, atm_iv, cfg.max_skew_shift)
    puts = sorted((q for q in chain if q.right == "P"), key=lambda q: q.strike)
    calls = sorted((q for q in chain if q.right == "C"), key=lambda q: q.strike)
    by = {(q.right, q.strike): q for q in chain}
    sp = _nearest(puts, tgt["target_put_delta"])
    sc = _nearest(calls, tgt["target_call_delta"])
    out = []
    for width in widths:
        lp, lc = by.get(("P", sp.strike - width)), by.get(("C", sc.strike + width))
        if lp:
            c, th = _wing((sp, lp))
            out.append(Setup("put_spread", [(sp, -1), (lp, 1)], width, c,
                             1 - abs(sp.delta), abs(sp.delta), th))
        if lc:
            c, th = _wing((sc, lc))
            out.append(Setup("call_spread", [(sc, -1), (lc, 1)], width, c,
                             1 - abs(sc.delta), abs(sc.delta), th))
        if lp and lc:
            c1, t1 = _wing((sp, lp))
            c2, t2 = _wing((sc, lc))
            # POP of a condor: price finishes between the two short strikes.
            pop = 1 - abs(sp.delta) - abs(sc.delta)
            out.append(Setup("iron_condor", [(sp, -1), (lp, 1), (sc, -1), (lc, 1)], width,
                             c1 + c2, pop, max(abs(sp.delta), abs(sc.delta)), t1 + t2))
    return [s for s in out if s.credit > 0]


def rank_setups(chain, put_iv_25d, call_iv_25d, ivr, premium_trend,
                widths=(1.0, 2.0, 5.0), cfg: OptimizerConfig = OptimizerConfig(),
                atm_iv: float | None = None) -> list[Setup]:
    setups = [score_setup(s, ivr, premium_trend, cfg)
              for s in build_candidates(chain, put_iv_25d, call_iv_25d, widths, cfg, atm_iv)]
    return sorted(setups, key=lambda s: s.osqs, reverse=True)
