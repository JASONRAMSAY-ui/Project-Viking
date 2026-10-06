"""Algorithmic chaser: walk a closing limit order from mid toward the natural price."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Protocol

from .config import ChaserConfig

TERMINAL = {"Filled", "Cancelled", "Rejected", "Expired", "Removed"}


class Broker(Protocol):
    def submit(self, order: dict) -> str: ...
    def replace(self, order_id: str, order: dict) -> None: ...
    def status(self, order_id: str) -> str: ...
    def cancel(self, order_id: str) -> None: ...


@dataclass
class ChaseResult:
    ok: bool
    order_id: str | None
    status: str
    final_price: float | None
    steps: list[dict] = field(default_factory=list)
    message: str = ""


def execute_chaser_exit(broker: Broker, legs: list[dict],
                        get_quote: Callable[[], dict], cfg: ChaserConfig = ChaserConfig(),
                        sleep: Callable[[float], None] = time.sleep) -> ChaseResult:
    """Close a credit position by buying it back (a debit). `get_quote()` must return the
    live closing-package quotes: {"mid": float, "natural": float} where natural is the
    price that crosses the whole spread (sum of asks on buys minus bids on sells).

    Price starts at mid and rises by max_slippage/max_chases per step, never exceeding
    min(natural, start_mid + max_slippage). Each step re-reads the quote so the ladder
    tracks a moving market, and re-checks status before replacing so a filled order is
    never amended."""
    q = get_quote()
    start_mid = q["mid"]
    ceiling = min(q["natural"], start_mid + cfg.max_slippage)
    step = cfg.max_slippage / cfg.max_chases
    price = round(start_mid, 2)
    res = ChaseResult(False, None, "New", None)

    def order(p: float) -> dict:
        return {"time-in-force": "Day", "order-type": "Limit", "price": f"{p:.2f}",
                "price-effect": "Debit", "legs": legs}

    for i in range(cfg.max_chases + 1):  # +1: last rung rests at the ceiling
        price = round(min(price, ceiling), 2)
        if res.order_id is None:
            res.order_id = broker.submit(order(price))
        else:
            try:
                broker.replace(res.order_id, order(price))
            except Exception as exc:  # replace can lose the race against a fill
                res.status = broker.status(res.order_id)
                if res.status == "Filled":
                    break
                res.message = f"replace failed: {exc}"
                res.steps.append({"step": i, "price": price, "status": "replace-failed"})
                return res
        sleep(cfg.wait_seconds)
        res.status = broker.status(res.order_id)
        res.final_price = price
        res.steps.append({"step": i, "price": price, "status": res.status})
        if res.status in TERMINAL:
            break
        q = get_quote()
        ceiling = min(q["natural"], start_mid + cfg.max_slippage)
        price = max(price + step, q["mid"])  # never fall behind a market running away

    if res.status == "Filled":
        res.ok, res.message = True, f"closed via chaser at {res.final_price:.2f}"
        return res
    if res.status in TERMINAL:
        res.message = f"order ended {res.status}"
        return res
    if cfg.allow_market_fallback:
        final = order(res.final_price or price)
        final["order-type"] = "Market"
        final.pop("price"), final.pop("price-effect")
        broker.replace(res.order_id, final)
        res.message = "EMERGENCY: chase exhausted; escalated to market"
    else:
        res.message = ("ALERT: chase exhausted, order still resting at "
                       f"{res.final_price:.2f}. Manual intervention required.")
    return res
