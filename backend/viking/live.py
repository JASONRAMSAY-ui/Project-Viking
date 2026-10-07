"""Read-only live data from tastytrade REST (no orders, no streaming).

Available over REST: positions, spot, option quotes with Greeks, IV rank, VIX.
NOT available over REST: daily history (HVN/pivots/ADX) and VIX3M; those need DXLink."""
from __future__ import annotations

import re
import threading
from datetime import datetime

import httpx

from .config import BrokerConfig
from .invalidation import NY, InvalidationEngine, Position
from .tastytrade import TastytradeBroker

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
                self._refresh_deltas()
                self.error = ""
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
                "hvn": [0, 0], "pivots": [], "triggers": [], "exit": None,
                "ivr": round(self.ivr.get(p.symbol, 0.0), 1)} for p in self.positions.values()]
            return {
                "mode": self.mode, "live_orders": False, "clock": self.clock.isoformat(),
                "auto_close": False, "error": self.error,
                "gatekeeper": {"front": self.vix, "back": None, "state": "unavailable (needs VIX3M via DXLink)",
                               "halted": False},
                "watchlist": [], "screen": [], "candidates": [], "positions": pos, "log": [],
                "notes": ["History-based rules (HVN/pivots/ADX) and the term-structure gatekeeper "
                          "need the DXLink host, which this environment does not yet allow."]}
