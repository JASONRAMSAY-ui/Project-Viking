"""Read-only tastytrade API smoke test. Places NO orders.

Checks: OAuth refresh -> accounts -> balances -> positions -> option chain.
Usage: python scripts/smoke_tastytrade.py [SYMBOL]
Env:   TT_CLIENT_SECRET, TT_REFRESH_TOKEN, TT_ACCOUNT (optional: defaults to first account),
       TT_BASE_URL (default: cert sandbox; set https://api.tastyworks.com for the real account)."""
import sys

from viking.config import BrokerConfig
from viking.tastytrade import TastytradeBroker

cfg = BrokerConfig()
symbol = sys.argv[1] if len(sys.argv) > 1 else "SPY"
missing = [n for n, v in (("TT_CLIENT_SECRET", cfg.client_secret), ("TT_REFRESH_TOKEN", cfg.refresh_token)) if not v]
if missing:
    sys.exit(f"missing env: {', '.join(missing)}")
print(f"host: {cfg.base_url}")

b = TastytradeBroker.__new__(TastytradeBroker)  # allow empty TT_ACCOUNT; we discover it below
import httpx, time
b.cfg, b._token, b._expires = cfg, "", 0.0
b.http = httpx.Client(base_url=cfg.base_url, timeout=10.0, headers={"User-Agent": "viking/0.1"})


def get(path, **params):
    r = b.http.get(path, headers=b._auth(), params=params)
    import re
    print(f"GET {re.sub(r'/accounts/([A-Z0-9]{2})[A-Z0-9]+([A-Z0-9]{2})', r'/accounts/\\1***\\2', path)} -> {r.status_code}")
    r.raise_for_status()
    return r.json()["data"]


accts = get("/customers/me/accounts")["items"]
numbers = [a["account"]["account-number"] for a in accts]
print("accounts:", [n[:2] + "***" + n[-2:] for n in numbers])  # masked
acct = cfg.account_number or numbers[0]
bal = get(f"/accounts/{acct}/balances")
print("net-liquidating-value:", bal.get("net-liquidating-value"), "| option-buying-power:", bal.get("derivative-buying-power"))
pos = get(f"/accounts/{acct}/positions")["items"]
print("open positions:", len(pos), [(p["symbol"], p["quantity"], p["quantity-direction"]) for p in pos[:5]])
chain = get(f"/option-chains/{symbol}/nested")["items"]
exps = chain[0]["expirations"]
print(f"{symbol} chain: {len(exps)} expirations; first {exps[0]['expiration-date']} ({exps[0]['days-to-expiration']} DTE), {len(exps[0]['strikes'])} strikes")
print("OK - read-only checks passed; no orders were sent.")
