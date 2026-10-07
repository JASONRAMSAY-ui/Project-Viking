"""Forward paper-trade log: record real candidate credits daily, resolve them at expiry from real prices.
Read-only; no orders. Log lives in paper/paper_log.jsonl (committed so evidence accumulates across sessions)."""
from __future__ import annotations

import json
import os
from datetime import date

import pandas as pd

LOG = "paper/paper_log.jsonl"


def snapshot_rows(rt, day: date | None = None, per_symbol: int = 2) -> list[dict]:
    """One row per (symbol, structure) from the live runtime's current candidates (put spreads in phase 1)."""
    day = day or date.today()
    rows = []
    for sym, cands in rt.cands.items():
        for c in cands[:per_symbol]:
            rows.append({"logged": day.isoformat(), "symbol": sym, "kind": c["kind"], "expiry": c["expiry"], "dte": c["dte"],
                         "spot": c["spot"], "legs": c["legs"], "width": c["width"], "credit_mid": c["credit"],
                         "credit_natural": c["credit_natural"], "multiplier": c["multiplier"], "pop_model": c["pop"],
                         "osqs": c["osqs"], "z": c.get("z"), "hist_contained": c.get("hist_contained"),
                         "ivr": c["ivr"], "trend_break": c["trend_break"], "signal": c["signal"],
                         "screen_passed": c["screen_passed"], "asset": c["asset"]})
    return rows


def append(rows: list[dict], path: str = LOG) -> int:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    seen = set()
    if os.path.exists(path):
        for line in open(path):
            r = json.loads(line)
            seen.add((r["logged"], r["symbol"], r["kind"], tuple(l["strike"] for l in r["legs"]), r["expiry"]))
    n = 0
    with open(path, "a") as f:
        for r in rows:
            k = (r["logged"], r["symbol"], r["kind"], tuple(l["strike"] for l in r["legs"]), r["expiry"])
            if k not in seen:
                f.write(json.dumps(r) + "\n")
                n += 1
    return n


def _payoff(r: dict, settle: float) -> float:
    """Net debit to close at expiry per share (>=0) for a credit spread; positive means a cost."""
    out = 0.0
    for l in r["legs"]:
        intrinsic = max(l["strike"] - settle, 0) if l["right"] == "P" else max(settle - l["strike"], 0)
        out += intrinsic if l["side"] == "short" else -intrinsic
    return out


def resolve(rows: list[dict], bars: dict[str, pd.DataFrame], today: date | None = None) -> pd.DataFrame:
    """Outcome of every logged paper trade whose expiry has passed. bars: {symbol: daily OHLC}."""
    today = today or date.today()
    out = []
    for r in rows:
        exp = pd.Timestamp(r["expiry"])
        if exp.date() >= today or r["symbol"] not in bars:
            continue
        b = bars[r["symbol"]]
        life = b[(b.index > pd.Timestamp(r["logged"])) & (b.index <= exp)]
        if life.empty or life.index[-1] < exp - pd.Timedelta(days=4):
            continue
        settle = float(life["close"].iloc[-1])
        shorts = [l["strike"] for l in r["legs"] if l["side"] == "short"]
        width = r["width"]
        pay = _payoff(r, settle)
        for nm in ("credit_mid", "credit_natural"):
            risk = max(width - r[nm], 1e-9)
            r[f"pnl_{nm}"] = r[nm] - pay
            r[f"ror_{nm}"] = (r[nm] - pay) / risk
        r["settle"] = settle
        r["touched_short"] = bool(((life["low"] <= min(shorts)).any()) if r["kind"] == "put_spread" else ((life["high"] >= max(shorts)).any()))
        out.append(r)
    return pd.DataFrame(out)
