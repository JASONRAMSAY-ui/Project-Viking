"""Read-only live data from tastytrade REST (no orders, no streaming).

Available over REST: positions, spot, option quotes with Greeks, IV rank, VIX.
NOT available over REST: daily history (HVN/pivots/ADX) and VIX3M; those need DXLink."""
from __future__ import annotations

import os
import re
import threading
import time
from datetime import datetime

import httpx

from . import dxlink
from . import indicators as ind
from .config import BrokerConfig
from .invalidation import NY, InvalidationEngine, Position
from .screening import run_screen
from .tastytrade import TastytradeBroker

WATCHLIST = [x for x in os.getenv("VIKING_WATCHLIST", "SPY,IWM,XLF,QQQ,TLT,GLD").split(",") if x]
HISTORY_TTL = 600.0  # seconds between daily-history refreshes

OCC = re.compile(r"^(?P<u>.{1,6}?)\s*(?P<d>\d{6})(?P<r>[CP])(?P<k>\d{8})$")


def parse_option(symbol: str) -> tuple[str, str, str, float] | None:
    m = OCC.match(symbol.strip())
    if not m:
        return None
    return m["u"].strip(), m["d"], m["r"], int(m["k"]) / 1000


def group_positions(items: list[dict]) -> list[Position]:
    """Group short/long option legs per underlying+expiry into put/call spreads or condors."""
    groups: dict[tuple, list] = {}
    for it in items:
        if it.get("instrument-type") != "Equity Option":
            continue
        o = parse_option(it["symbol"])
        if not o:
            continue
        qty = int(float(it["quantity"])) * (1 if it["quantity-direction"] == "Long" else -1)
        groups.setdefault((o[0], o[1]), []).append((o[2], o[3], qty))
    out = []
    for (und, exp), legs in groups.items():
        sp = max((k for r, k, q in legs if r == "P" and q < 0), default=None)
        sc = min((k for r, k, q in legs if r == "C" and q < 0), default=None)
        if sp is None and sc is None:
            continue
        qty = abs(min(q for _, _, q in legs))
        kind = "iron_condor" if sp and sc else ("put_spread" if sp else "call_spread")
        out.append(Position(f"{und}-{exp}", und, kind, sp, sc, qty, 0.0, 0.0, []))
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
        self._hist_at = 0.0
        self.hist_error = ""

    def _refresh_history(self, unds: list[str]) -> None:
        if time.time() - self._hist_at < HISTORY_TTL:
            return
        self._hist_at = time.time()  # also throttles retries after a failure
        try:
            tok = self._get("/api-quote-tokens")
            syms = sorted(set(WATCHLIST) | set(unds))
            got = dxlink.fetch_daily(tok["dxlink-url"], tok["token"], syms + ["VIX", "VIX3M"], timeout=12)
            vix, v3 = got.pop("VIX", None), got.pop("VIX3M", None)
            if vix is not None and v3 is not None and len(vix) and len(v3):
                self.term = (float(vix["close"].iloc[-1]), float(v3["close"].iloc[-1]))
            self.bars = {s: df for s, df in got.items() if len(df) >= 120}
            for s in self.bars:
                self.nm_spread[s] = self._near_money_spread(s, float(self.bars[s]["close"].iloc[-1]))
            self._screen = None
            if self.term and self.bars:
                uni = {s: (b, [self.nm_spread.get(s, float("inf"))]) for s, b in self.bars.items()
                       if s in WATCHLIST}
                self._screen = run_screen(uni, *self.term)
            for p in self.positions.values():
                if p.symbol in self.bars:
                    h = ind.volume_profile_hvn(self.bars[p.symbol], self.engine.cfg.hvn_lookback)
                    p.hvn_low, p.hvn_high = h["low"], h["high"]
            self.hist_error = ""
        except Exception as e:
            self.hist_error = f"history: {type(e).__name__}: {e}"

    def _near_money_spread(self, sym: str, spot: float) -> float:
        """Worst bid/ask width ($/share) on near-the-money options ~30-45 DTE (inf if unknown)."""
        try:
            exps = self._get(f"/option-chains/{sym}/nested")["items"][0]["expirations"]
            ex = min((e for e in exps if e["days-to-expiration"] >= 30),
                     key=lambda e: e["days-to-expiration"])
            ks = sorted(ex["strikes"], key=lambda k: abs(float(k["strike-price"]) - spot))[:2]
            syms = [k[r] for k in ks for r in ("call", "put")]
            q = self._quotes("equity-option", syms)
            return max(float(v["ask"]) - float(v["bid"]) for v in q.values())
        except Exception:
            return float("inf")

    def _get(self, path: str, **params):
        r = self.b.http.get(path, headers=self.b._auth(), params=params)
        r.raise_for_status()
        return r.json()["data"]

    def _quotes(self, kind: str, symbols: list[str]) -> dict[str, dict]:
        if not symbols:
            return {}
        items = self._get("/market-data/by-type", **{kind: ",".join(symbols)})["items"]
        return {i["symbol"]: i for i in items}

    def tick(self, minutes: float = 1.0) -> None:
        try:
            with self.lock:
                self.clock = datetime.now(NY)
                if not self._acct:
                    self._acct = self._get("/customers/me/accounts")["items"][0]["account"]["account-number"]
                pos = group_positions(self._get(f"/accounts/{self._acct}/positions")["items"])
                self.positions = {p.id: p for p in pos}
                unds = sorted({p.symbol for p in pos})
                self.spot = {s: float(q["mark"]) for s, q in self._quotes("equity", unds).items()}
                vx = self._quotes("index", ["VIX"]).get("VIX")
                self.vix = float(vx["mark"]) if vx else None
                if unds:
                    mm = self._get("/market-metrics", symbols=",".join(unds))["items"]
                    self.ivr = {m["symbol"]: float(m["tw-implied-volatility-index-rank"]) * 100 for m in mm}
                self._refresh_history(unds)
                self._refresh_deltas()
                self.error = self.hist_error
        except Exception as e:  # keep the console alive; surface the error
            self.error = f"{type(e).__name__}: {e}"

    def _refresh_deltas(self) -> None:
        for p in self.positions.values():
            for attr, right, k in (("short_put_delta", "P", p.short_put), ("short_call_delta", "C", p.short_call)):
                if k is None:
                    continue
                exp = p.id.split("-")[1]
                sym = f"{p.symbol:<6}{exp}{right}{int(round(k * 1000)):08d}"
                q = self._quotes("equity-option", [sym]).get(sym)
                if q and q.get("delta") is not None:
                    setattr(p, attr, float(q["delta"]))

    def close_position(self, pos_id: str) -> dict:
        return {"started": False, "reason": "live closing is disabled; requires explicit user approval"}

    def snapshot(self) -> dict:
        with self.lock:
            pos = [{
                "id": p.id, "symbol": p.symbol, "kind": p.kind, "qty": p.qty,
                "spot": round(self.spot.get(p.symbol, 0.0), 2),
                "short_put": p.short_put, "short_call": p.short_call,
                "put_delta": round(p.short_put_delta, 3), "call_delta": round(p.short_call_delta, 3),
                "hvn": [round(p.hvn_low, 2), round(p.hvn_high, 2)], "pivots": [], "triggers": [], "exit": None,
                "ivr": round(self.ivr.get(p.symbol, 0.0), 1)} for p in self.positions.values()]
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
                "candidates": [], "positions": pos, "log": [],
                "notes": ["Live screen and gatekeeper use real history. Pivot rules and ranked "
                          "candidates are not wired yet; closing is disabled."]}
