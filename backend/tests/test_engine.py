from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from viking import indicators as ind
from viking.chaser import execute_chaser_exit
from viking.config import ChaserConfig, ScreenConfig
from viking.invalidation import InvalidationEngine, Pivot, Position, market_minutes_between
from viking.optimizer import (calculate_skew_adjusted_deltas, rank_setups, OptionQuote,
                                   Setup, score_setup)
from viking.screening import TermStructure, run_screen, screen_symbol, term_structure
from viking.sim import synthetic_bars, synthetic_chain
from viking.tastytrade import SimBroker

NY = ZoneInfo("America/New_York")


def at(d, h, m=0):
    return datetime(2026, 10, d, h, m, tzinfo=NY)  # Oct 5 2026 is a Monday


# ---- screening
def test_run_lengths():
    cur, hist = ind.run_lengths(pd.Series([1, 1, 0, 1, 1, 1, 0, 1]).astype(bool))
    assert cur == 1 and hist == [2, 3]


def test_liquidity_gate_rejects_wide_spread_and_low_adv():
    bars = synthetic_bars(volume=5_000_000)
    assert screen_symbol("X", bars, [0.10]).liquidity is False
    thin = synthetic_bars(volume=1_000)
    assert screen_symbol("X", thin, [0.02]).liquidity is False
    assert screen_symbol("X", bars, [0.02]).liquidity is True


def test_backwardation_halts_and_purges():
    assert term_structure(22, 20) is TermStructure.BACKWARDATION
    out = run_screen({"X": (synthetic_bars(), [0.01])}, front_iv=22, back_iv=20)
    assert out["halted"] and out["watchlist"] == []
    assert not run_screen({"X": (synthetic_bars(), [0.01])}, 18, 20)["halted"]


def test_breakout_threat_flagged_when_bis_exceeds_upper_bound(monkeypatch):
    bars = synthetic_bars()
    box = pd.Series([True] * 3 + [False] + [True] * 4 + [False] + [True] * 3 + [False] + [True] * 40,
                    index=bars.index[-53:]).reindex(bars.index, fill_value=False)
    monkeypatch.setattr(ind, "squeeze_box", lambda *a, **k: box)
    r = screen_symbol("X", bars, [0.01])
    assert r.breakout_threat and not r.temporal and not r.passed


# ---- optimiser
def test_skew_deltas():
    d = calculate_skew_adjusted_deltas(0.20, 0.18, 0.16)  # ratio 1.125 -> modifier 0.0625
    assert d == {"target_put_delta": 0.138, "target_call_delta": 0.263}
    assert calculate_skew_adjusted_deltas()["target_put_delta"] == 0.12  # spec defaults hit the clamp
    assert calculate_skew_adjusted_deltas(0.2, 0.16, 0.22)["target_put_delta"] == 0.2  # no negative skew
    assert calculate_skew_adjusted_deltas(0.2, 1.0, 0.1)["target_call_delta"] == 0.28  # clamped at 0.08


def _setup(short_delta, credit=1.0, width=3.0, pop=None, kind="put_spread"):
    return Setup(kind, [], width, credit, pop if pop is not None else 1 - short_delta,
                 short_delta, 0.03)


def test_penalty_on_high_delta_or_low_pop():
    good = score_setup(_setup(0.18), ivr=60, premium_trend=-0.02)
    hi_delta = score_setup(_setup(0.27, pop=0.80), ivr=60, premium_trend=-0.02)
    low_pop = score_setup(_setup(0.18, pop=0.60), ivr=60, premium_trend=-0.02)
    assert not good.penalised and hi_delta.penalised and low_pop.penalised
    assert hi_delta.osqs < good.osqs * 0.5


def test_vega_downscored_for_flat_or_expanding_premium_and_low_ivr():
    contracting = score_setup(_setup(0.18), 60, -0.03).components["vega"]
    expanding = score_setup(_setup(0.18), 60, +0.03).components["vega"]
    low_ivr = score_setup(_setup(0.18), 30, -0.03).components["vega"]
    assert expanding < contracting and low_ivr < contracting


def test_yield_definitions():
    vert = score_setup(_setup(0.18, credit=1.0, width=4.0), 60, -0.02)
    assert vert.components["yield_ratio"] == pytest.approx(1 / 3)  # credit / max risk
    ic = score_setup(_setup(0.18, credit=1.0, width=3.0, kind="iron_condor"), 60, -0.02)
    assert ic.components["yield_ratio"] == pytest.approx(1 / 3)  # credit / single-side width


def test_rank_setups_end_to_end():
    ranked = rank_setups(synthetic_chain(100.0), 0.30, 0.22, ivr=60, premium_trend=-0.02)
    assert ranked and ranked == sorted(ranked, key=lambda s: -s.osqs)
    ic = next(s for s in ranked if s.kind == "iron_condor")
    assert ic.pop == pytest.approx(1 - sum(abs(q.delta) for q, side in ic.legs if side < 0))


# ---- invalidation
def test_market_minutes_skip_overnight_and_weekend():
    assert market_minutes_between(at(2, 15, 50), at(5, 9, 40)) == 20  # Fri 10m + Mon 10m
    assert market_minutes_between(at(3, 17), at(3, 18)) == 0


def pos(**kw):
    base = dict(id="p1", symbol="X", kind="iron_condor", short_put=95, short_call=105, qty=1,
                hvn_low=94, hvn_high=106,
                pivots=[Pivot("AVWAP", 96, "support"), Pivot("R1", 104, "resistance")])
    base.update(kw)
    return Position(**base)


def test_pivot_needs_more_than_15_continuous_market_minutes():
    e, p = InvalidationEngine(), pos()
    assert e.on_tick(p, 95.5, at(6, 10, 0)) == []
    assert e.on_tick(p, 95.5, at(6, 10, 15)) == []  # exactly 15: not "more than"
    assert [t.rule for t in e.on_tick(p, 95.5, at(6, 10, 16))] == ["pivot_breach"]


def test_pivot_recovery_resets_clock():
    e, p = InvalidationEngine(), pos()
    e.on_tick(p, 95.5, at(6, 10, 0))
    e.on_tick(p, 97.0, at(6, 10, 10))  # back inside
    assert e.on_tick(p, 95.5, at(6, 10, 20)) == []
    assert e.on_tick(p, 95.5, at(6, 10, 30)) == []


def test_pivot_clock_ignores_after_hours():
    e, p = InvalidationEngine(), pos()
    e.on_tick(p, 95.5, at(6, 15, 50))
    assert e.on_tick(p, 95.5, at(7, 9, 35)) == []  # 10 + 5 = 15 market min


def test_delta_stop_and_hvn_exit():
    e = InvalidationEngine()
    assert [t.rule for t in e.on_tick(pos(short_call_delta=0.35), 100, at(6, 11))] == ["delta_acceleration"]
    assert e.on_tick(pos(short_put_delta=-0.34), 100, at(6, 11)) == []
    assert e.on_daily_close(pos(), 93.5, atr=1.0) == []        # within 1 ATR of border
    assert e.on_daily_close(pos(), 92.9, atr=1.0)[0].rule == "hvn_exit"
    assert e.on_daily_close(pos(), 107.1, atr=1.0)[0].rule == "hvn_exit"


# ---- chaser
LEGS = [{"symbol": "X 261120P95", "action": "Buy to Close", "quantity": 1}]
quote = lambda: {"mid": 1.00, "natural": 1.20}
fast = ChaserConfig(wait_seconds=0)


def test_chaser_fills_at_first_acceptable_rung_and_prices_ascend():
    b = SimBroker(fill_at=1.05)
    r = execute_chaser_exit(b, LEGS, quote, fast, sleep=lambda s: None)
    assert r.ok and r.final_price == 1.06
    prices = [s["price"] for s in r.steps]
    assert prices == sorted(prices) and prices[0] == 1.00


def test_chaser_never_exceeds_slippage_cap_and_never_goes_market_by_default():
    b = SimBroker(fill_at=9.99)  # never fills
    r = execute_chaser_exit(b, LEGS, quote, fast, sleep=lambda s: None)
    assert not r.ok and "Manual intervention" in r.message
    assert max(s["price"] for s in r.steps) <= 1.10
    assert b.orders[r.order_id]["order"]["order-type"] == "Limit"


def test_chaser_market_fallback_is_opt_in():
    b = SimBroker(fill_at=9.99)
    cfg = ChaserConfig(wait_seconds=0, allow_market_fallback=True)
    r = execute_chaser_exit(b, LEGS, quote, cfg, sleep=lambda s: None)
    assert "EMERGENCY" in r.message and b.orders[r.order_id]["order"]["order-type"] == "Market"


def test_chaser_chases_a_running_market():
    mids = iter([1.00] + [1.30] * 20)
    r = execute_chaser_exit(SimBroker(9.99), LEGS, lambda: {"mid": next(mids), "natural": 1.40},
                            fast, sleep=lambda s: None)
    assert max(s["price"] for s in r.steps) <= 1.10  # cap is anchored to the starting mid
