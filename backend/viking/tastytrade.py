"""tastytrade REST broker (OAuth2 refresh-token flow) and an in-memory simulated broker.

NOTE: this module has NOT been exercised against the live tastytrade API (no credentials
were available when it was written). It targets the sandbox host by default; verify
endpoint shapes against https://developer.tastytrade.com before enabling live orders.
Streaming quotes (DXLink) are intentionally behind the QuoteSource protocol in
runtime.py rather than implemented here."""
from __future__ import annotations

import itertools
import time

import httpx

from .config import BrokerConfig


class LiveOrderBlocked(RuntimeError):
    """Raised when a real order is attempted without VIKING_LIVE=1 and explicit approval."""


def order_fingerprint(order: dict) -> str:
    """Identity of an order ignoring price, so a chase (price replace) stays within one approval."""
    legs = sorted((l.get("symbol"), l.get("action"), l.get("quantity")) for l in order.get("legs", []))
    return repr((order.get("order-type"), order.get("time-in-force"), order.get("price-effect"), legs))


class TastytradeBroker:
    def __init__(self, cfg: BrokerConfig, client: httpx.Client | None = None):
        if not (cfg.client_secret and cfg.refresh_token and cfg.account_number):
            raise ValueError("TT_CLIENT_SECRET, TT_REFRESH_TOKEN and TT_ACCOUNT are required")
        self.cfg = cfg
        self.http = client or httpx.Client(base_url=cfg.base_url, timeout=10.0,
                                           headers={"User-Agent": "viking/0.1"})
        self._token, self._expires = "", 0.0
        self._approved: set[str] = set()   # fingerprints the user approved, one-shot
        self._live_ids: set[str] = set()   # order ids this broker submitted under approval

    def approve(self, order: dict) -> None:
        """Record explicit user approval for exactly this order (one submission)."""
        self._approved.add(order_fingerprint(order))

    def _auth(self) -> dict:
        if time.time() > self._expires - 60:
            r = self.http.post("/oauth/token", json={
                "grant_type": "refresh_token", "refresh_token": self.cfg.refresh_token,
                "client_secret": self.cfg.client_secret})
            r.raise_for_status()
            body = r.json()
            self._token = body["access_token"]
            self._expires = time.time() + int(body.get("expires_in", 900))
        return {"Authorization": f"Bearer {self._token}"}

    def _path(self, suffix: str = "") -> str:
        return f"/accounts/{self.cfg.account_number}/orders{suffix}"

    def dry_run(self, order: dict) -> dict:
        r = self.http.post(self._path("/dry-run"), json=order, headers=self._auth())
        r.raise_for_status()
        return r.json()["data"]

    def submit(self, order: dict) -> str:
        fp = order_fingerprint(order)
        if not self.cfg.live_orders:
            raise LiveOrderBlocked("live orders disabled (VIKING_LIVE != 1); use dry_run()")
        if fp not in self._approved:
            raise LiveOrderBlocked("order has not been explicitly approved by the user")
        self._approved.discard(fp)
        r = self.http.post(self._path(), json=order, headers=self._auth())
        r.raise_for_status()
        data = r.json()["data"]
        oid = str(data.get("order", data)["id"])
        self._live_ids.add(oid)
        return oid

    def replace(self, order_id: str, order: dict) -> None:
        if not self.cfg.live_orders or order_id not in self._live_ids:
            raise LiveOrderBlocked("can only replace an order submitted under approval in this session")
        self.http.put(self._path(f"/{order_id}"), json=order, headers=self._auth()).raise_for_status()

    def status(self, order_id: str) -> str:
        r = self.http.get(self._path(f"/{order_id}"), headers=self._auth())
        r.raise_for_status()
        data = r.json()["data"]
        return data.get("order", data)["status"]

    def cancel(self, order_id: str) -> None:
        self.http.delete(self._path(f"/{order_id}"), headers=self._auth()).raise_for_status()


class SimBroker:
    """Fills a debit limit order once its price reaches `fill_at` (the simulated natural)."""

    def __init__(self, fill_at: float = 0.0):
        self.fill_at = fill_at
        self.orders: dict[str, dict] = {}
        self._ids = itertools.count(1)

    def submit(self, order: dict) -> str:
        oid = str(next(self._ids))
        self.orders[oid] = {"order": order, "status": "Live"}
        self._maybe_fill(oid)
        return oid

    def replace(self, order_id: str, order: dict) -> None:
        if self.orders[order_id]["status"] == "Filled":
            raise RuntimeError("order already filled")
        self.orders[order_id]["order"] = order
        self._maybe_fill(order_id)

    def _maybe_fill(self, oid: str) -> None:
        o = self.orders[oid]["order"]
        if o["order-type"] == "Market" or float(o["price"]) >= self.fill_at:
            self.orders[oid]["status"] = "Filled"

    def status(self, order_id: str) -> str:
        return self.orders[order_id]["status"]

    def cancel(self, order_id: str) -> None:
        self.orders[order_id]["status"] = "Cancelled"
