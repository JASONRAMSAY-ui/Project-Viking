import time

from fastapi.testclient import TestClient

from lithosphere.chaser import ChaserConfig
from lithosphere.runtime import DemoRuntime
from lithosphere.server import create_app
from lithosphere.sim import synthetic_bars
from lithosphere.screening import screen_symbol


def client(**kw):
    rt = DemoRuntime(chaser=ChaserConfig(wait_seconds=0), **kw)
    return rt, TestClient(create_app(rt, tick_seconds=0))


def test_synthetic_universe_can_pass_screen():
    assert screen_symbol("X", synthetic_bars(seed=2, shock_ago=20), [0.02]).passed


def test_snapshot_shape_and_watchlist():
    rt, c = client()
    s = c.get("/api/state").json()
    assert s["mode"] == "DEMO" and s["live_orders"] is False
    assert s["watchlist"] and s["candidates"] and len(s["positions"]) == 2
    assert s["candidates"] == sorted(s["candidates"], key=lambda x: -x["osqs"])


def test_backwardation_halts_and_empties_watchlist():
    rt, c = client()
    c.post("/api/demo/term", json={"front": 25, "back": 20})
    s = c.get("/api/state").json()
    assert s["gatekeeper"]["state"] == "backwardation" and s["gatekeeper"]["halted"]
    assert s["watchlist"] == [] and s["candidates"] == []


def test_delta_stop_flags_then_chaser_closes_position():
    rt, c = client()
    p = c.get("/api/state").json()["positions"][0]
    c.post("/api/demo/spot", json={"symbol": p["symbol"], "price": p["short_call"] - 0.5})
    p = c.get("/api/state").json()["positions"][0]
    assert any(t["rule"] == "delta_acceleration" for t in p["triggers"])
    assert c.post(f"/api/positions/{p['id']}/close").json() == {"started": True}
    for _ in range(50):
        if len(c.get("/api/state").json()["positions"]) == 1:
            break
        time.sleep(0.05)
    s = c.get("/api/state").json()
    assert [x["id"] for x in s["positions"]] == ["P2"] and s["log"]


def test_auto_close_is_off_by_default():
    rt, c = client()
    p = c.get("/api/state").json()["positions"][0]
    c.post("/api/demo/spot", json={"symbol": p["symbol"], "price": p["short_call"]})
    time.sleep(0.2)
    assert len(c.get("/api/state").json()["positions"]) == 2


def test_short_delta_goes_past_half_when_itm():
    from lithosphere.runtime import short_delta
    assert short_delta(100, 95, "P") < 0.5 < short_delta(94, 95, "P")
    assert short_delta(100, 105, "C") < 0.5 < short_delta(106, 105, "C")
