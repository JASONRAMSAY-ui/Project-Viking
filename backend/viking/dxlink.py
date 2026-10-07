"""Read-only DXLink client: fetch daily candles and last quotes (no orders)."""
from __future__ import annotations

import asyncio
import json
import time

import pandas as pd
import websockets


async def _session(url: str, token: str, subs: list[dict], fields: dict, until, timeout: float):
    out: dict[str, list] = {}
    async with websockets.connect(url) as ws:
        send = lambda m: ws.send(json.dumps(m))
        await send({"type": "SETUP", "channel": 0, "version": "0.1-DXF-JS/0.3.0",
                    "keepaliveTimeout": 60, "acceptKeepaliveTimeout": 60})
        await send({"type": "AUTH", "channel": 0, "token": token})
        while True:  # the server must report AUTHORIZED before channels may be opened
            m = json.loads(await asyncio.wait_for(ws.recv(), 10))
            if m.get("type") == "AUTH_STATE" and m.get("state") == "AUTHORIZED":
                break
        await send({"type": "CHANNEL_REQUEST", "channel": 1, "service": "FEED",
                    "parameters": {"contract": "AUTO"}})
        await send({"type": "FEED_SETUP", "channel": 1, "acceptAggregationPeriod": 0.1,
                    "acceptDataFormat": "COMPACT", "acceptEventFields": fields})
        await send({"type": "FEED_SUBSCRIPTION", "channel": 1, "reset": True, "add": subs})
        end = time.time() + timeout
        while time.time() < end:
            try:
                m = json.loads(await asyncio.wait_for(ws.recv(), max(0.1, end - time.time())))
            except asyncio.TimeoutError:
                break
            if DEBUG:
                print(str(m)[:200])
            if m.get("type") == "FEED_DATA":
                d = m["data"]
                for i in range(0, len(d), 2):
                    out.setdefault(d[i], []).extend(_rows(d[i], d[i + 1], fields[d[i]]))
                if until(out):
                    break
    return out


def _rows(event: str, flat: list, names: list[str]) -> list[dict]:
    n = len(names)
    return [dict(zip(names, flat[i:i + n])) for i in range(0, len(flat), n)]


DEBUG = False
CANDLE = ["eventSymbol", "time", "open", "high", "low", "close", "volume"]
QUOTE = ["eventSymbol", "bidPrice", "askPrice"]


def fetch_daily(url: str, token: str, symbols: list[str], days: int = 400, timeout: float = 20) -> dict:
    """Return {symbol: DataFrame[open,high,low,close,volume]} of completed+current daily bars."""
    start = int((time.time() - days * 86400) * 1000)
    subs = [{"type": "Candle", "symbol": f"{s}{{=d}}", "fromTime": start} for s in symbols]
    # candle stream is a snapshot; stop after a quiet period via timeout
    raw = asyncio.run(_session(url, token, subs, {"Candle": CANDLE}, lambda o: False, timeout))
    res = {}
    for r in raw.get("Candle", []):
        pass
    by: dict[str, list] = {}
    for r in raw.get("Candle", []):
        if r["close"] in (None, "NaN"):
            continue
        by.setdefault(r["eventSymbol"].split("{")[0], []).append(r)
    for s, rows in by.items():
        df = pd.DataFrame(rows).drop_duplicates("time", keep="last").sort_values("time")
        df.index = pd.to_datetime(df["time"], unit="ms")
        res[s] = df[["open", "high", "low", "close", "volume"]].astype(float).fillna(0.0)
    return res


def fetch_quotes(url: str, token: str, symbols: list[str], timeout: float = 10) -> dict[str, float]:
    subs = [{"type": "Quote", "symbol": s} for s in symbols]
    want = set(symbols)
    raw = asyncio.run(_session(url, token, subs, {"Quote": QUOTE},
                               lambda o: want <= {r["eventSymbol"] for r in o.get("Quote", [])}, timeout))
    out = {}
    for r in raw.get("Quote", []):
        b, a = r["bidPrice"], r["askPrice"]
        if isinstance(b, (int, float)) and isinstance(a, (int, float)):
            out[r["eventSymbol"]] = (b + a) / 2
    return out
