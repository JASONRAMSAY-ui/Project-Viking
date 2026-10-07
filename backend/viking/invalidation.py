"""Phase 3: local, underlying-price-based invalidation rules. No premium stops."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from .config import RiskConfig

NY = ZoneInfo("America/New_York")
OPEN, CLOSE = time(9, 30), time(16, 0)


def market_minutes_between(start: datetime, end: datetime) -> float:
    """Minutes of regular US session (Mon-Fri 09:30-16:00 ET) between two instants.
    Exchange holidays are not modelled."""
    start, end = start.astimezone(NY), end.astimezone(NY)
    if end <= start:
        return 0.0
    total, day = 0.0, start.date()
    while day <= end.date():
        if day.weekday() < 5:
            s = max(start, datetime.combine(day, OPEN, NY))
            e = min(end, datetime.combine(day, CLOSE, NY))
            if e > s:
                total += (e - s).total_seconds() / 60
        day += timedelta(days=1)
    return total


@dataclass
class Pivot:
    name: str
    level: float
    side: str  # "support" (breach = below) or "resistance" (breach = above)

    def breached(self, price: float) -> bool:
        return price < self.level if self.side == "support" else price > self.level


@dataclass
class Position:
    id: str
    symbol: str
    kind: str
    short_put: float | None
    short_call: float | None
    qty: int
    hvn_low: float
    hvn_high: float
    pivots: list[Pivot] = field(default_factory=list)
    short_put_delta: float = 0.0
    short_call_delta: float = 0.0


@dataclass
class Trigger:
    rule: str
    detail: str


class InvalidationEngine:
    """Stateful per position: tracks how long each pivot has been continuously breached."""

    def __init__(self, cfg: RiskConfig = RiskConfig()):
        self.cfg = cfg
        self._breach_since: dict[tuple[str, str], datetime] = {}

    def breach_minutes(self, pos_id: str, pivot: Pivot, now: datetime) -> float:
        since = self._breach_since.get((pos_id, pivot.name))
        return market_minutes_between(since, now) if since else 0.0

    def on_tick(self, pos: Position, price: float, now: datetime) -> list[Trigger]:
        """Evaluate delta stop and pivot-breach timers on every spot update."""
        out: list[Trigger] = []
        for leg, d in (("put", pos.short_put_delta), ("call", pos.short_call_delta)):
            if abs(d) >= self.cfg.delta_stop:
                out.append(Trigger("delta_acceleration",
                                   f"short {leg} delta {abs(d):.2f} >= {self.cfg.delta_stop:.2f}"))
        for pv in pos.pivots:
            key = (pos.id, pv.name)
            if not pv.breached(price):
                self._breach_since.pop(key, None)  # any recovery resets the clock
                continue
            self._breach_since.setdefault(key, now)
            mins = self.breach_minutes(pos.id, pv, now)
            if mins > self.cfg.pivot_breach_minutes:
                out.append(Trigger("pivot_breach",
                                   f"{pv.name} {pv.level:.2f} breached {mins:.0f} market min"))
        return out

    def on_daily_close(self, pos: Position, close: float, atr: float) -> list[Trigger]:
        """Daily close 1 x ATR beyond the 180-day HVN borders."""
        pad = self.cfg.hvn_atr_multiple * atr
        if close < pos.hvn_low - pad:
            return [Trigger("hvn_exit", f"close {close:.2f} < HVN low {pos.hvn_low:.2f} - {pad:.2f}")]
        if close > pos.hvn_high + pad:
            return [Trigger("hvn_exit", f"close {close:.2f} > HVN high {pos.hvn_high:.2f} + {pad:.2f}")]
        return []

    def clear(self, pos_id: str) -> None:
        for k in [k for k in self._breach_since if k[0] == pos_id]:
            del self._breach_since[k]
