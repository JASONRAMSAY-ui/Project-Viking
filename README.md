# Project Lithosphere

Option screening, contract optimisation and underlying-price invalidation engine for
OTM vertical spreads / iron condors, with a React control console.

```
backend/lithosphere/   screening.py  optimizer.py  invalidation.py  chaser.py
                       indicators.py tastytrade.py runtime.py server.py sim.py
backend/tests/         pytest suite (24 tests)
frontend/              Vite + React + Tailwind v4 + lucide-react (src/App.jsx)
```

## Run (demo mode, no credentials)

```bash
cd backend && python -m venv ../.venv && . ../.venv/bin/activate && pip install -e '.[dev]'
pytest                                   # tests
uvicorn lithosphere.server:app --port 8000
cd ../frontend && npm install && npm run dev   # http://localhost:5173
```

The console is clearly badged **DEMO · SYNTHETIC DATA · SIMULATED ORDERS**. Demo controls push
spot to the short strike / below support and force backwardation so each rule can be seen firing.

## Status: what is and isn't real

| Piece | State |
|---|---|
| Phase 1 filters, gatekeeper, Phase 2 OSQS, Phase 3 rules, chaser | Implemented and unit-tested |
| Console + REST/WebSocket feed | Implemented, verified in a browser against demo data |
| `TastytradeBroker` (OAuth2 refresh, orders, replace, dry-run) | Written to the documented API; **never run against tastytrade** |
| DXLink streaming quotes/Greeks/candles | **Not implemented.** `QuoteSource` in `runtime.py` is the seam |
| Historical daily bars for screening | Synthetic only; needs a real provider (DXLink candles or other) |
| Short-leg delta in the demo | Black-Scholes-style approximation, not streamed Greeks |
| Live runtime wiring (broker + real data into `runtime.py`) | Not done; the server only runs `DemoRuntime` |

Before any live use: wire real data, run on the tastytrade cert sandbox
(`TT_BASE_URL` defaults to `https://api.cert.tastyworks.com`), and review everything.
`BrokerConfig` reads `LITHOSPHERE_LIVE`, `TT_CLIENT_SECRET`, `TT_REFRESH_TOKEN`, `TT_ACCOUNT`.
Nothing here is financial advice.

## Deliberate departures from the spec text

1. **Chaser direction.** Closing a credit position is a *debit*; the ladder starts at mid and
   steps *up* toward the natural price, capped at `start_mid + 0.10` (dollars/share, not "cents").
   It re-quotes each rung, and re-checks status before replacing so a filled order is never amended.
2. **No market-order fallback by default.** Multi-leg options are generally not accepted as market
   orders and a market fill defeats the anti-slippage goal. After the last rung the order keeps
   resting at the cap and raises an ALERT for manual action. `ChaserConfig.allow_market_fallback`
   restores the spec's behaviour.
3. **No auto-close by default.** A tripped rule flags the position and the console offers
   "Close via chaser". `LITHOSPHERE_AUTOCLOSE=1` makes it automatic.
4. **Spec bug fixed:** `https://tastytrade.com` is not the API host; base URL is configurable.
5. "0.05c" spread limit is read as **$0.05** per share.
6. ΔADX < 0 over 3 sessions = ADX fell on each of the last 3 sessions.
7. Pivot rule: "more than 15 consecutive minutes" counts only regular-session minutes
   (Mon–Fri 09:30–16:00 ET, holidays not modelled); any return inside the level resets the clock.
8. Penalty coefficient 0.2 multiplies the final OSQS.

## Spec issue worth your decision

The skew adjustment raises the **call** target delta to `0.20 + modifier` (up to 0.28), but the
POP rule penalises any short delta > 0.25. Whenever the skew ratio exceeds ~1.10 the call side is
penalised by construction (visible in the demo: all call spreads show `PEN`). Likely fix: apply
the skew symmetrically around the base (`put - m`, `call + m`, cap at 0.25) or relax the cap
for calls. I implemented the spec as written.

Also: Filters 2 and 3 together are strict (about 10% of synthetic symbols pass) and the BIS window
is empty whenever `mean − 0.5σ < 4`.
