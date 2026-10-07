"""Orchestrates screening, optimisation, invalidation and chaser exits; feeds the console.

Market data comes from a `QuoteSource`. Only the demo (synthetic) source ships in this
repo; a DXLink-backed source implementing the same protocol is the integration point for
live data."""
from __future__ import annotations

import threading
from datetime import datetime, timedelta
from math import erf, sqrt
from typing import Protocol

import numpy as np

from . import indicators as ind
from .chaser import execute_chaser_exit
from .config import ChaserConfig, RiskConfig
from .invalidation import NY, InvalidationEngine, Pivot, Position
from .optimizer import rank_setups
from .screening import run_screen
from .sim import synthetic_bars, synthetic_chain
from .tastytrade import SimBroker


class QuoteSource(Protocol):
    def spot(self, symbol: str) -> float: ...
    def term_structure(self) -> tuple[float, float]: ...


def _cdf(x: float) -> float:
    return 0.5 * (1 + erf(x / sqrt(2)))


def short_delta(spot: float, strike: float, right: str, iv: float = 0.25, dte: int = 30) -> float:
    """Approximate |delta| of a short leg (rises past 0.5 once it goes ITM); stand-in
    until streamed Greeks are wired."""
    z = (spot - strike if right == "P" else strike - spot) / (spot * iv * sqrt(dte / 365))
    return _cdf(-z)


class DemoRuntime:
    mode = "DEMO"

    def __init__(self, seed: int = 7, auto_close: bool = False,
                 risk: RiskConfig = RiskConfig(), chaser: ChaserConfig | None = None):
        self.rng = np.random.default_rng(seed)
        self.risk, self.auto_close = risk, auto_close
        self.chaser_cfg = chaser or ChaserConfig(wait_seconds=0.6)
        self.clock = datetime(2026, 10, 5, 10, 0, tzinfo=NY)  # a Monday, simulated
        self.front_iv, self.back_iv = 17.8, 19.9  # VIX / VIX3M
        self.lock = threading.RLock()
        names = {"SPY": 2, "IWM": 6, "XLF": 7, "QQQ": 1, "TLT": 3, "GLD": 4}
        self.bars = {s: synthetic_bars(seed=sd, shock_ago=20) for s, sd in names.items()}
        self.spot = {s: float(b["close"].iloc[-1]) for s, b in self.bars.items()}
        self.engine = InvalidationEngine(risk)
        self.positions: dict[str, Position] = {}
        self.flags: dict[str, list] = {}
        self.exits: dict[str, dict] = {}
        self.log: list[dict] = []
        self._open_demo_positions()
        self._screen = None
        self._screen_key = None

    # ---- setup
    def _open_demo_positions(self) -> None:
        for i, sym in enumerate(("SPY", "IWM")):
            b, s = self.bars[sym], self.spot[sym]
            hvn = ind.volume_profile_hvn(b, self.risk.hvn_lookback)
            avwap = ind.anchored_vwap(b, len(b) - 45)
            sp, sc = round(s * 0.93), round(s * 1.07)
            self.positions[f"P{i + 1}"] = Position(
                f"P{i + 1}", sym, "iron_condor", sp, sc, 1, hvn["low"], hvn["high"],
                [Pivot("Anchored VWAP", min(avwap, s * 0.96), "support"),
                 Pivot("R1 pivot", s * 1.04, "resistance")])
        self._refresh_deltas()

    def _refresh_deltas(self) -> None:
        for p in self.positions.values():
            s = self.spot[p.symbol]
            p.short_put_delta = -short_delta(s, p.short_put, "P")
            p.short_call_delta = short_delta(s, p.short_call, "C")

    # ---- loop
    def tick(self, minutes: float = 1.0) -> None:
        with self.lock:
            self.clock += timedelta(minutes=minutes)
            self.front_iv = max(10.0, self.front_iv + self.rng.normal(0, 0.05))
            self.back_iv = max(10.0, self.back_iv + self.rng.normal(0, 0.03))
            for s in self.spot:
                self.spot[s] *= float(np.exp(self.rng.normal(0, 0.0004)))
            self._evaluate()

    def _evaluate(self) -> None:
        self._refresh_deltas()
        for p in list(self.positions.values()):
            if p.id in self.exits:
                continue
            trig = self.engine.on_tick(p, self.spot[p.symbol], self.clock)
            b = self.bars[p.symbol]
            trig += self.engine.on_daily_close(p, self.spot[p.symbol],
                                               float(ind.atr(b).iloc[-1])) if self._at_close() else []
            self.flags[p.id] = [t.__dict__ for t in trig]
            if trig and self.auto_close:
                self.close_position(p.id)

    def _at_close(self) -> bool:
        c = self.clock.astimezone(NY)
        return c.hour == 15 and c.minute >= 59

    # ---- actions
    def set_spot(self, symbol: str, price: float) -> None:
        with self.lock:
            self.spot[symbol] = price
            self._evaluate()

    def set_term_structure(self, front: float, back: float) -> None:
        with self.lock:
            self.front_iv, self.back_iv = front, back

    def close_position(self, pos_id: str) -> dict:
        with self.lock:
            if pos_id not in self.positions or pos_id in self.exits:
                return {"started": False}
            pos = self.positions[pos_id]
            self.exits[pos_id] = {"state": "working", "steps": [], "message": ""}
        threading.Thread(target=self._run_chaser, args=(pos,), daemon=True).start()
        return {"started": True}

    def _run_chaser(self, pos: Position) -> None:
        legs = [{"instrument-type": "Equity Option", "action": a, "quantity": pos.qty,
                 "symbol": f"{pos.symbol} {k}"}
                for a, k in (("Buy to Close", f"P{pos.short_put}"), ("Buy to Close", f"C{pos.short_call}"))]
        mid = 0.80 + float(self.rng.uniform(0, 0.3))
        quote = lambda: {"mid": mid, "natural": mid + 0.25}
        res = execute_chaser_exit(SimBroker(fill_at=mid + 0.06), legs, quote, self.chaser_cfg)
        with self.lock:
            self.exits[pos.id] = {"state": "closed" if res.ok else "alert", "steps": res.steps,
                                  "message": res.message}
            self.log.append({"t": self.clock.isoformat(), "position": pos.id, "message": res.message})
            if res.ok:
                self.positions.pop(pos.id, None)
                self.engine.clear(pos.id)

    # ---- views
    def _screen_results(self):
        key = (round(self.front_iv, 1), round(self.back_iv, 1))
        if key != self._screen_key:
            uni = {s: (b, [0.02]) for s, b in self.bars.items()}
            self._screen, self._screen_key = run_screen(uni, self.front_iv, self.back_iv), key
        return self._screen

    def snapshot(self) -> dict:
        with self.lock:
            scr = self._screen_results()
            cands = []
            if scr["watchlist"]:
                sym = scr["watchlist"][0]
                for s in rank_setups(synthetic_chain(self.spot[sym]), 0.30, 0.22, ivr=58,
                                     premium_trend=-0.02)[:6]:
                    cands.append({"symbol": sym, "kind": s.kind, "osqs": round(s.osqs, 3),
                                  "pop": round(s.pop, 3), "credit": round(s.credit, 2),
                                  "width": s.width, "penalised": s.penalised,
                                  "strikes": [f"{'-' if d < 0 else '+'}{q.strike:g}{q.right}" for q, d in s.legs],
                                  "components": {k: round(v, 3) for k, v in s.components.items()}})
            pos = []
            for p in self.positions.values():
                spot = self.spot[p.symbol]
                pos.append({
                    "id": p.id, "symbol": p.symbol, "kind": p.kind, "qty": p.qty, "spot": round(spot, 2),
                    "short_put": p.short_put, "short_call": p.short_call,
                    "put_delta": round(p.short_put_delta, 3), "call_delta": round(p.short_call_delta, 3),
                    "hvn": [round(p.hvn_low, 2), round(p.hvn_high, 2)],
                    "pivots": [{"name": v.name, "level": round(v.level, 2), "side": v.side,
                                "breach_min": round(self.engine.breach_minutes(p.id, v, self.clock), 1),
                                "breached": v.breached(spot)} for v in p.pivots],
                    "triggers": self.flags.get(p.id, []), "exit": self.exits.get(p.id)})
            return {
                "mode": self.mode, "live_orders": False, "clock": self.clock.isoformat(),
                "auto_close": self.auto_close,
                "gatekeeper": {"front": round(self.front_iv, 2), "back": round(self.back_iv, 2),
                               "state": scr["term_structure"].value, "halted": scr["halted"]},
                "watchlist": scr["watchlist"],
                "screen": [{"symbol": r.symbol, "passed": r.passed, "liquidity": r.liquidity,
                            "volatility": r.volatility, "temporal": r.temporal,
                            "breakout_threat": r.breakout_threat, "reasons": r.reasons[:2],
                            "bis": r.metrics.get("bis"), "adx": round(r.metrics["adx"], 1),
                            "hv_ratio": round(r.metrics["hv20"] / r.metrics["hv90"], 2)}
                           for r in scr["results"]],
                "candidates": cands, "positions": pos, "log": self.log[-20:],
            }
