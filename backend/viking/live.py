"""Read-only live data from tastytrade: REST for positions, quotes, Greeks, chains and IV rank;
DXLink (websocket) only for daily candles and VIX/VIX3M. Covers equities/ETFs and futures
options. Places no orders."""
from __future__ import annotations

import os
import re
import threading
import time
from datetime import datetime

import httpx

from . import dxlink
from . import containment as ct
from . import indicators as ind
from .config import BrokerConfig
from .invalidation import NY, InvalidationEngine, Pivot, Position
from .optimizer import OptionQuote, rank_setups
from .config import ScreenConfig
from .screening import run_screen
from .trend import downtrend_break
from .tastytrade import TastytradeBroker

WATCHLIST = [x for x in os.getenv("VIKING_WATCHLIST", "SPY,IWM,XLF,QQQ,TLT,GLD").split(",") if x]
FUTURES = [x for x in os.getenv("VIKING_FUTURES", "/ES,/NQ,/GC,/CL,/ZN").split(",") if x]
UNIVERSE = WATCHLIST + FUTURES
SIDE = os.getenv("VIKING_SIDE", "put")  # phase 1: one-sided put spreads
HISTORY_TTL = 600.0  # seconds between daily-history refreshes

OCC = re.compile(r"^(?P<u>.{1,6}?)\s*(?P<d>\d{6})(?P<r>[CP])(?P<k>\d{8})$")


def parse_option(symbol: str) -> tuple[str, str, str, float] | None:
    m = OCC.match(symbol.strip())
    if not m:
        return None
    return m["u"].strip(), m["d"], m["r"], int(m["k"]) / 1000


FOPT = re.compile(r"^\./(?P<fut>\S+)\s+(?P<opt>\S+)\s+(?P<d>\d{6})(?P<r>[CP])(?P<k>[\d.]+)$")
FROOT = re.compile(r"^(?P<root>[A-Z0-9]+?)[FGHJKMNQUVXZ]\d{1,2}$")


def parse_future_option(symbol: str) -> tuple[str, str, str, str, float] | None:
    """'./ESZ6 E1BV6 261006P6610' -> ('/ES', '/ESZ6', '261006', 'P', 6610.0)"""
    m = FOPT.match(symbol.strip())
    r = FROOT.match(m["fut"]) if m else None
    if not (m and r):
        return None
    return f"/{r['root']}", f"/{m['fut']}", m["d"], m["r"], float(m["k"])


def group_positions(items: list[dict]) -> list[Position]:
    """Group short/long option legs per underlying+expiry into put/call spreads or condors.
    Handles equity options and futures options."""
    groups: dict[tuple, list] = {}
    for it in items:
        itype = it.get("instrument-type")
        if itype == "Equity Option":
            o = parse_option(it["symbol"])
            key = (o[0], o[0], o[1], False) if o else None
            right, strike = (o[2], o[3]) if o else (None, None)
        elif itype == "Future Option":
            o = parse_future_option(it["symbol"])
            key = (o[0], o[1], o[2], True) if o else None
            right, strike = (o[3], o[4]) if o else (None, None)
        else:
            continue
        if not key:
            continue
        qty = int(float(it["quantity"])) * (1 if it["quantity-direction"] == "Long" else -1)
        groups.setdefault(key, []).append((right, strike, qty, it["symbol"]))
    out = []
    for (root, quote, exp, fut), legs in groups.items():
        sp = max((k for r, k, q, _ in legs if r == "P" and q < 0), default=None)
        sc = min((k for r, k, q, _ in legs if r == "C" and q < 0), default=None)
        if sp is None and sc is None:
            continue
        qty = abs(min(q for _, _, q, _ in legs))
        kind = "iron_condor" if sp and sc else ("put_spread" if sp else "call_spread")
        pos = Position(f"{quote}-{exp}", root, kind, sp, sc, qty, 0.0, 0.0, [], futures=fut,
                       quote_symbol=quote if fut else "")
        pos.leg_symbols = {(r, k): sym for r, k, _, sym in legs}
        out.append(pos)
    return out


class LiveRuntime:
    """Read-only: real positions/spot/Greeks. Closing is disabled; orders need explicit approval."""

    mode = "LIVE · READ-ONLY"

    def __init__(self, cfg: BrokerConfig | None = None):
        self.cfg = cfg or BrokerConfig()
        b = TastytradeBroker.__new__(TastytradeBroker)
        b.cfg, b._token, b._expires = self.cfg, "", 0.0
        b.http = httpx.Client(base_url=self.cfg.base_url, timeout=10.0, headers={"User-Agent": "viking/0.1"})
        self.b = b
        self.lock = threading.RLock()
        self.engine = InvalidationEngine()
        self.positions: dict[str, Position] = {}
        self.spot: dict[str, float] = {}
        self.exits: dict = {}
        self.flags: dict[str, list] = {}
        self.vix: float | None = None
        self.ivr: dict[str, float] = {}
        self.error = ""
        self.clock = datetime.now(NY)
        self._acct = self.cfg.account_number
        self.bars: dict = {}
        self.term: tuple[float, float] | None = None
        self.nm_spread: dict[str, float] = {}
        self._screen = None
        self.cands: dict[str, list] = {}
        self.trend: dict[str, dict] = {}
        self.fmeta: dict[str, dict] = {}  # futures root -> {"bar": "/ES:XCME", "mult": 50.0}
        self._hist_at = 0.0
        self.hist_error = ""

    # ---- helpers
    def _get(self, path: str, **params):
        r = self.b.http.get(path, headers=self.b._auth(), params=params)
        r.raise_for_status()
        return r.json()["data"]

    def _quotes(self, kind: str, symbols: list[str]) -> dict[str, dict]:
        if not symbols:
            return {}
        items = self._get("/market-data/by-type", **{kind: ",".join(symbols)})["items"]
        return {i["symbol"]: i for i in items}

    @staticmethod
    def _is_future(sym: str) -> bool:
        return sym.startswith("/")

    def _opt_kind(self, sym: str) -> str:
        return "future-option" if self._is_future(sym) else "equity-option"

    def _key(self, p: Position) -> str:
        return p.quote_symbol or p.symbol

    def _future_meta(self, sym: str) -> dict:
        """Continuous-candle symbol and contract multiplier for a futures root such as /ES."""
        if sym not in self.fmeta:
            root = sym.lstrip("/")
            fut = self._get(f"/futures-option-chains/{root}/nested")["futures"][0]
            exch = fut["streamer-symbol"].split(":")[1]
            items = self._get("/instruments/futures", **{"product-code[]": root})["items"]
            self.fmeta[sym] = {"bar": f"/{root}:{exch}", "mult": float(items[0]["notional-multiplier"])}
        return self.fmeta[sym]

    def _mult(self, sym: str) -> float:
        return self._future_meta(sym)["mult"] if self._is_future(sym) else 100.0

    def _expirations(self, sym: str) -> list[dict]:
        if self._is_future(sym):
            return self._get(f"/futures-option-chains/{sym.lstrip('/')}/nested")["option-chains"][0]["expirations"]
        return self._get(f"/option-chains/{sym}/nested")["items"][0]["expirations"]

    def _pick_expiry(self, sym: str) -> dict:
        return min((e for e in self._expirations(sym) if e["days-to-expiration"] >= 30),
                   key=lambda e: e["days-to-expiration"])

    def _spot_for(self, sym: str, ex: dict) -> float:
        if self._is_future(sym):
            u = ex["underlying-symbol"]
            return float(self._quotes("future", [u])[u]["mark"])
        return float(self.bars[sym]["close"].iloc[-1])

    # ---- history, screen, candidates
    def _refresh_history(self, unds: list[str]) -> None:
        if time.time() - self._hist_at < HISTORY_TTL:
            return
        self._hist_at = time.time()  # also throttles retries after a failure
        try:
            tok = self._get("/api-quote-tokens")
            syms = sorted(set(UNIVERSE) | set(unds))
            wire = {s: (self._future_meta(s)["bar"] if self._is_future(s) else s) for s in syms}
            got = dxlink.fetch_daily(tok["dxlink-url"], tok["token"], list(wire.values()) + ["VIX", "VIX3M"],
                                     timeout=15)
            vix, v3 = got.pop("VIX", None), got.pop("VIX3M", None)
            if vix is not None and v3 is not None and len(vix) and len(v3):
                self.term = (float(vix["close"].iloc[-1]), float(v3["close"].iloc[-1]))
            self.bars = {s: got[w] for s, w in wire.items() if w in got and len(got[w]) >= 120}
            for s in self.bars:
                self.nm_spread[s] = self._near_money_spread(s)
            self.trend = {s: downtrend_break(b) for s, b in self.bars.items()}
            self._screen = None
            if self.term and self.bars:
                uni = {}
                for s, b in self.bars.items():
                    if s in UNIVERSE:
                        # dollar volume for futures needs the contract multiplier
                        sb = b.assign(volume=b["volume"] * self._mult(s)) if self._is_future(s) else b
                        uni[s] = (sb, [self.nm_spread.get(s, float("inf"))])
                self._screen = run_screen(uni, *self.term, cfg=ScreenConfig(spread_relative=True))
            for p in self.positions.values():
                if p.symbol in self.bars:
                    h = ind.volume_profile_hvn(self.bars[p.symbol], self.engine.cfg.hvn_lookback)
                    p.hvn_low, p.hvn_high = h["low"], h["high"]
                    p.pivots = self._pivots(p, self.bars[p.symbol])
            self._refresh_candidates()
            self.hist_error = ""
        except Exception as e:
            self.hist_error = f"history: {type(e).__name__}: {e}"

    def _live_chain(self, sym: str) -> dict:
        """OTM option quotes (~30-45 DTE) with real Greeks, plus skew inputs and a sensible width step."""
        ex = self._pick_expiry(sym)
        spot = self._spot_for(sym, ex)
        kind = self._opt_kind(sym)
        want, strikes = [], []
        for k in ex["strikes"]:
            K = float(k["strike-price"])
            if K < spot * 0.85 or K > spot * 1.15:
                continue
            strikes.append(K)
            if K < spot:
                want.append((k["put"], "P", K))
            if K > spot:
                want.append((k["call"], "C", K))
        meta = {w[0]: w for w in want}
        chain, iv, atm = [], {"P": [], "C": []}, []
        for i in range(0, len(want), 80):
            for sym_, q in self._quotes(kind, [w[0] for w in want[i:i + 80]]).items():
                _, right, K = meta[sym_]
                try:
                    bid, ask, d, th = float(q["bid"]), float(q["ask"]), float(q["delta"]), float(q["theta"])
                except (KeyError, TypeError, ValueError):
                    continue
                if ask <= 0 or ask < bid:
                    continue
                chain.append(OptionQuote(K, right, bid, ask, d, th))
                if q.get("volatility") is not None:
                    iv[right].append((abs(abs(d) - 0.25), float(q["volatility"])))
                    atm.append((abs(abs(d) - 0.5), float(q["volatility"])))
        pick = lambda r, dflt: min(iv[r])[1] if iv[r] else dflt
        near = sorted(k for k in strikes if abs(k - spot) < spot * 0.05)
        gaps = sorted(b - a for a, b in zip(near, near[1:]) if b > a)
        sp = gaps[len(gaps) // 2] if gaps else 1.0
        if self._is_future(sym):
            step = max(sp, round(spot * 0.003 / sp) * sp)
        else:
            step = 5.0 if spot > 300 else 2.0 if spot > 100 else 1.0
        return {"chain": chain, "put_iv": pick("P", 0.22), "call_iv": pick("C", 0.16),
                "dte": ex["days-to-expiration"], "atm_iv": min(atm)[1] if atm else None, "step": step}

    def _refresh_candidates(self) -> None:
        syms = sorted(set(UNIVERSE))
        mm = {m["symbol"]: m for m in self._get("/market-metrics", symbols=",".join(syms))["items"]}
        passed = {r.symbol for r in self._screen["results"] if r.passed} if self._screen else set()
        liquid = {r.symbol for r in self._screen["results"] if r.liquidity} if self._screen else set()
        halted = bool(self._screen and self._screen["halted"])
        self.cands = {}
        for sym in syms:
            if sym not in self.bars:
                continue
            m = mm.get(sym, {})
            ivr = float(m.get("tw-implied-volatility-index-rank") or 0) * 100
            iv = float(m.get("implied-volatility-index") or 0) or 1.0
            trend = float(m.get("implied-volatility-index-5-day-change") or 0) / iv / 5
            try:
                c = self._live_chain(sym)
                ranked = rank_setups(c["chain"], c["put_iv"], c["call_iv"], ivr, trend,
                                     widths=(c["step"], 2 * c["step"]), atm_iv=c["atm_iv"])
                if SIDE in ("put", "call"):
                    ranked = [x for x in ranked if x.kind == f"{SIDE}_spread"]
                ranked = ranked[:4]
                mult = self._mult(sym)
                hv = ind.volume_profile_hvn(self.bars[sym], self.engine.cfg.hvn_lookback)
            except Exception:
                continue
            sd = float(ct.daily_sigma(self.bars[sym]).iloc[-1])
            spot0 = float(self.bars[sym]["close"].iloc[-1])
            h = max(1, round(c["dte"] * 5 / 7))  # trading days to expiry

            def hist(x):
                shorts = [q.strike for q, d in x.legs if d < 0]
                side = "down" if x.kind == "put_spread" else "up" if x.kind == "call_spread" else None
                if side is None or not sd or not shorts:
                    return {}
                dist = (1 - min(shorts) / spot0) if side == "down" else (max(shorts) / spot0 - 1)
                z = dist / (sd * h ** 0.5)
                n, pc = ct.contained(self.bars[sym], h, z, side)
                return {"z": round(z, 2), "hist_contained": round(pc, 3), "hist_n": n, "hist_horizon_days": h}

            self.cands[sym] = [{**hist(x),
                "symbol": sym, "kind": x.kind, "osqs": round(x.osqs, 3), "pop": round(x.pop, 3),
                "credit": round(x.credit, 2), "width": x.width, "penalised": x.penalised,
                "asset": "future" if self._is_future(sym) else "equity", "multiplier": mult,
                "credit_usd": round(x.credit * mult, 2),
                "max_risk_usd": round((x.width - x.credit) * mult, 2),
                "dte": c["dte"], "ivr": round(ivr, 1), "screen_passed": sym in passed,
                "poc": round(hv["poc"], 2), "congestion": [round(hv["low"], 2), round(hv["high"], 2)],
                # info only: backtest found no edge from requiring a break at/above the POC
                "short_outside_congestion": not (hv["low"] <= min(q.strike for q, d in x.legs if d < 0) <= hv["high"])
                                            if x.kind == "put_spread" else None,
                "trend_break": bool(self.trend.get(sym, {}).get("active")),
                "days_since_break": self.trend.get(sym, {}).get("days_since_break"),
                # phase 1 signal: downtrend just broke, put spread, liquid, gatekeeper open
                "signal": bool(SIDE == "put" and x.kind == "put_spread" and self.trend.get(sym, {}).get("active")
                               and sym in liquid and not halted),
                "strikes": [f"{'-' if d < 0 else '+'}{q.strike:g}{q.right}" for q, d in x.legs],
                "components": {k: round(v, 3) for k, v in x.components.items()}} for x in ranked]

    @staticmethod
    def _pivots(p: Position, b) -> list[Pivot]:
        """Support under a short put (anchored VWAP, S1 pivot), resistance over a short call (R1 pivot)."""
        last = b.iloc[-1]
        pp = (last["high"] + last["low"] + last["close"]) / 3
        out = []
        if p.short_put is not None:
            out.append(Pivot("Anchored VWAP", float(ind.anchored_vwap(b, max(len(b) - 45, 0))), "support"))
            out.append(Pivot("S1 pivot", float(2 * pp - last["high"]), "support"))
        if p.short_call is not None:
            out.append(Pivot("R1 pivot", float(2 * pp - last["low"]), "resistance"))
        return out

    def _near_money_spread(self, sym: str) -> float:
        """Worst bid/ask width as a fraction of mid on near-the-money options ~30-45 DTE (inf if unknown)."""
        try:
            ex = self._pick_expiry(sym)
            spot = self._spot_for(sym, ex)
            ks = sorted(ex["strikes"], key=lambda k: abs(float(k["strike-price"]) - spot))[:2]
            q = self._quotes(self._opt_kind(sym), [k[r] for k in ks for r in ("call", "put")])
            return max((float(v["ask"]) - float(v["bid"])) / max((float(v["ask"]) + float(v["bid"])) / 2, 0.01)
                       for v in q.values())
        except Exception:
            return float("inf")

    # ---- loop
    def tick(self, minutes: float = 1.0) -> None:
        try:
            with self.lock:
                self.clock = datetime.now(NY)
                if not self._acct:
                    self._acct = self._get("/customers/me/accounts")["items"][0]["account"]["account-number"]
                pos = group_positions(self._get(f"/accounts/{self._acct}/positions")["items"])
                self.positions = {p.id: p for p in pos}
                for p in pos:
                    if p.futures:
                        p.multiplier = self._mult(p.symbol)
                eq = sorted({p.symbol for p in pos if not p.futures})
                fut = sorted({p.quote_symbol for p in pos if p.futures})
                self.spot = {s: float(q["mark"]) for s, q in self._quotes("equity", eq).items()}
                self.spot.update({s: float(q["mark"]) for s, q in self._quotes("future", fut).items()})
                vx = self._quotes("index", ["VIX"]).get("VIX")
                self.vix = float(vx["mark"]) if vx else None
                unds = sorted({p.symbol for p in pos})
                if unds:
                    mm = self._get("/market-metrics", symbols=",".join(unds))["items"]
                    self.ivr = {m["symbol"]: float(m["tw-implied-volatility-index-rank"]) * 100 for m in mm}
                self._refresh_history(unds)
                self._refresh_deltas()
                self._evaluate()
                self.error = self.hist_error
        except Exception as e:  # keep the console alive; surface the error
            self.error = f"{type(e).__name__}: {e}"

    def _refresh_deltas(self) -> None:
        for p in self.positions.values():
            for attr, right, k in (("short_put_delta", "P", p.short_put), ("short_call_delta", "C", p.short_call)):
                sym = p.leg_symbols.get((right, k)) if k is not None else None
                if not sym:
                    continue
                q = self._quotes("future-option" if p.futures else "equity-option", [sym]).get(sym)
                if q and q.get("delta") is not None:
                    setattr(p, attr, float(q["delta"]))

    def _evaluate(self) -> None:
        for p in self.positions.values():
            spot = self.spot.get(self._key(p))
            if spot is None:
                continue
            trig = self.engine.on_tick(p, spot, self.clock)
            b = self.bars.get(p.symbol)
            c = self.clock.astimezone(NY)
            # equities close at 16:00 ET; CME futures settle at 17:00 ET
            close_hr, close_min = (16, 59) if p.futures else (15, 59)
            if b is not None and c.hour == close_hr and c.minute >= close_min:
                trig += self.engine.on_daily_close(p, spot, float(ind.atr(b).iloc[-1]))
            self.flags[p.id] = [t.__dict__ for t in trig]

    # ---- actions (all read-only)
    def close_position(self, pos_id: str) -> dict:
        return {"started": False, "reason": "live closing is disabled; requires explicit user approval"}

    def dry_run_close(self, pos_id: str) -> dict:
        """Validate a closing order with tastytrade's dry-run endpoint. Places nothing."""
        p = self.positions.get(pos_id)
        if not p:
            return {"ok": False, "error": "unknown position"}
        itype = "Future Option" if p.futures else "Equity Option"
        legs = [{"instrument-type": itype, "symbol": p.leg_symbols[(r, k)], "quantity": p.qty,
                 "action": "Buy to Close"} for r, k in (("P", p.short_put), ("C", p.short_call))
                if k and (r, k) in p.leg_symbols]
        order = {"time-in-force": "Day", "order-type": "Limit", "price": 0.05, "price-effect": "Debit",
                 "legs": legs}
        b = TastytradeBroker(self.cfg.__class__(**{**self.cfg.__dict__, "account_number": self._acct}))
        b.http = self.b.http
        b._token, b._expires = self.b._token, self.b._expires
        try:
            return {"ok": True, "result": b.dry_run(order)}
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    # ---- view
    def snapshot(self) -> dict:
        with self.lock:
            pos = []
            for p in self.positions.values():
                spot = self.spot.get(self._key(p), 0.0)
                pos.append({
                    "id": p.id, "symbol": p.symbol, "kind": p.kind, "qty": p.qty,
                    "asset": "future" if p.futures else "equity", "multiplier": p.multiplier,
                    "spot": round(spot, 2),
                    "short_put": p.short_put, "short_call": p.short_call,
                    "put_delta": round(p.short_put_delta, 3), "call_delta": round(p.short_call_delta, 3),
                    "hvn": [round(p.hvn_low, 2), round(p.hvn_high, 2)],
                    "pivots": [{"name": v.name, "level": round(v.level, 2), "side": v.side,
                                "breach_min": round(self.engine.breach_minutes(p.id, v, self.clock, p.futures), 1),
                                "breached": v.breached(spot)} for v in p.pivots],
                    "triggers": self.flags.get(p.id, []), "exit": None,
                    "ivr": round(self.ivr.get(p.symbol, 0.0), 1)})
            scr = self._screen
            gk = ({"front": round(self.term[0], 2), "back": round(self.term[1], 2),
                   "state": scr["term_structure"].value, "halted": scr["halted"]} if scr else
                  {"front": self.vix, "back": None, "state": "unavailable", "halted": False})
            screen = [{"symbol": r.symbol, "passed": r.passed, "liquidity": r.liquidity,
                       "volatility": r.volatility, "temporal": r.temporal,
                       "breakout_threat": r.breakout_threat, "reasons": r.reasons[:2],
                       "bis": r.metrics.get("bis"), "adx": round(r.metrics["adx"], 1),
                       "hv_ratio": round(r.metrics["hv20"] / r.metrics["hv90"], 2)}
                      for r in scr["results"]] if scr else []
            return {
                "mode": self.mode, "live_orders": False, "clock": self.clock.isoformat(),
                "auto_close": False, "error": self.error,
                "gatekeeper": gk,
                "watchlist": scr["watchlist"] if scr else [], "screen": screen,
                "candidates": sorted((c for v in self.cands.values() for c in v),
                                     key=lambda c: (not c["signal"], not c["screen_passed"], -c["osqs"]))[:12],
                "phase1_signals": [c for v in self.cands.values() for c in v if c["signal"]],
                "trend": {k: v for k, v in self.trend.items()},
                "positions": pos, "log": [],
                "notes": ["Screens equities/ETFs and futures (set VIKING_WATCHLIST / VIKING_FUTURES). "
                          "Futures use a 24h session clock and contract multipliers. Closing is disabled. "
                          "The phase 1 trend-break flag is UNVALIDATED on the broader universe."]}
