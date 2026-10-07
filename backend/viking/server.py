"""FastAPI app: REST + WebSocket feed for the console. Demo data unless wired to a live source."""
from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .runtime import DemoRuntime


class Spot(BaseModel):
    symbol: str
    price: float


class Term(BaseModel):
    front: float
    back: float


def create_app(runtime: DemoRuntime | None = None, tick_seconds: float = 1.0) -> FastAPI:
    rt = runtime or DemoRuntime(auto_close=os.getenv("VIKING_AUTOCLOSE") == "1")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async def loop():
            while True:
                await asyncio.sleep(tick_seconds)
                rt.tick()
        task = asyncio.create_task(loop()) if tick_seconds > 0 else None
        yield
        if task:
            task.cancel()

    app = FastAPI(title="Project Viking", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"],
                       allow_methods=["*"], allow_headers=["*"])

    @app.get("/api/state")
    def state():
        return rt.snapshot()

    @app.post("/api/positions/{pos_id}/close")
    def close(pos_id: str):
        if pos_id not in rt.positions:
            raise HTTPException(404, "unknown position")
        return rt.close_position(pos_id)

    @app.post("/api/demo/spot")
    def demo_spot(body: Spot):
        if body.symbol not in rt.spot:
            raise HTTPException(404, "unknown symbol")
        rt.set_spot(body.symbol, body.price)
        return {"ok": True}

    @app.post("/api/demo/term")
    def demo_term(body: Term):
        rt.set_term_structure(body.front, body.back)
        return {"ok": True}

    @app.websocket("/ws")
    async def ws(sock: WebSocket):
        await sock.accept()
        try:
            while True:
                await sock.send_json(rt.snapshot())
                await asyncio.sleep(1.0)
        except (WebSocketDisconnect, RuntimeError):
            pass

    return app


app = create_app()
