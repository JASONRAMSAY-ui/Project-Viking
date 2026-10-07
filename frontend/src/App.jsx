import React, { useEffect, useRef, useState } from 'react'
import {
  Activity, AlertOctagon, AlertTriangle, CheckCircle2, Crosshair, Flame, Gauge,
  Layers, Radio, ShieldAlert, ShieldCheck, TrendingDown, TrendingUp, Zap,
} from 'lucide-react'

const DELTA_STOP = 0.35
const PIVOT_LIMIT_MIN = 15

const post = (url, body) =>
  fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })

function useLiveState() {
  const [state, setState] = useState(null)
  const [connected, setConnected] = useState(false)
  const retry = useRef(0)

  useEffect(() => {
    let ws, timer, closed = false
    const connect = () => {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      ws = new WebSocket(`${proto}://${location.host}/ws`)
      ws.onopen = () => { retry.current = 0; setConnected(true) }
      ws.onmessage = (e) => setState(JSON.parse(e.data))
      ws.onclose = () => {
        setConnected(false)
        if (!closed) timer = setTimeout(connect, Math.min(1000 * 2 ** retry.current++, 10000))
      }
    }
    connect()
    return () => { closed = true; clearTimeout(timer); ws && ws.close() }
  }, [])
  return { state, connected }
}

const Panel = ({ title, icon: Icon, right, children, className = '' }) => (
  <section className={`rounded-md border border-zinc-800 bg-zinc-900/60 ${className}`}>
    <header className="flex items-center justify-between border-b border-zinc-800 px-3 py-1.5">
      <h2 className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-widest text-zinc-400">
        <Icon size={13} /> {title}
      </h2>
      {right}
    </header>
    {children}
  </section>
)

const Pill = ({ ok, children }) => (
  <span className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${
    ok ? 'bg-emerald-500/15 text-emerald-400' : 'bg-zinc-800 text-zinc-500'}`}>
    {children}
  </span>
)

function DeltaBar({ value }) {
  const v = Math.abs(value)
  const pct = Math.min(v / 0.5, 1) * 100
  const hot = v >= DELTA_STOP
  const warn = v >= 0.28
  return (
    <div className="flex items-center gap-2">
      <div className="relative h-1.5 w-20 rounded bg-zinc-800">
        <div className={`h-full rounded ${hot ? 'bg-red-500' : warn ? 'bg-amber-400' : 'bg-emerald-500'}`}
             style={{ width: `${pct}%` }} />
        <div className="absolute top-[-2px] h-[10px] w-px bg-zinc-300"
             style={{ left: `${(DELTA_STOP / 0.5) * 100}%` }} title="0.35 stop" />
      </div>
      <span className={`tabular-nums ${hot ? 'font-bold text-red-400' : 'text-zinc-300'}`}>{v.toFixed(3)}</span>
    </div>
  )
}

function Gatekeeper({ g }) {
  const back = g.state === 'backwardation'
  return (
    <div className={`flex items-center gap-3 rounded border px-3 py-1 ${
      back ? 'border-red-500/50 bg-red-500/10' : 'border-emerald-500/30 bg-emerald-500/5'}`}>
    {back ? <ShieldAlert size={16} className="text-red-400" /> : <ShieldCheck size={16} className="text-emerald-400" />}
      <div className="text-[11px] leading-tight">
        <div className="font-bold uppercase tracking-wider">
          {back ? 'Backwardation · routing halted' : 'Contango · routing enabled'}
        </div>
        <div className="text-zinc-400 tabular-nums">
          VIX {g.front.toFixed(2)} / VIX3M {g.back.toFixed(2)} = {(g.front / g.back).toFixed(3)}
        </div>
      </div>
    </div>
  )
}

function PositionCard({ p }) {
  const flagged = p.triggers.length > 0
  const ex = p.exit
  const [lo, hi] = p.hvn
  const span = Math.max(hi - lo, 1e-6)
  const lane = (x) => `${Math.min(Math.max(((x - (lo - span * 0.6)) / (span * 2.2)) * 100, 0), 100)}%`
  return (
    <div className={`border-b border-zinc-800 p-3 last:border-0 ${flagged ? 'bg-red-500/5' : ''}`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-bold text-zinc-100">{p.symbol}</span>
          <span className="text-[10px] uppercase text-zinc-500">{p.kind.replace('_', ' ')} ×{p.qty}</span>
          <span className="text-xs tabular-nums text-zinc-400">spot {p.spot.toFixed(2)}</span>
        </div>
        <div className="flex items-center gap-2">
          {ex?.state === 'working' && <span className="flex items-center gap-1 text-[11px] text-amber-400"><Activity size={12} className="animate-pulse" /> chasing…</span>}
          {ex?.state === 'alert' && <span className="flex items-center gap-1 text-[11px] text-red-400"><AlertOctagon size={12} /> manual action</span>}
          <button
            disabled={!!ex}
            onClick={() => post(`/api/positions/${p.id}/close`)}
            className={`flex items-center gap-1 rounded px-2 py-1 text-[11px] font-bold disabled:opacity-40 ${
              flagged ? 'bg-red-600 text-white hover:bg-red-500' : 'bg-zinc-800 text-zinc-300 hover:bg-zinc-700'}`}>
            <Zap size={12} /> Close via chaser
          </button>
        </div>
      </div>

      <div className="mt-2 grid grid-cols-2 gap-x-6 gap-y-1 text-[11px] text-zinc-400">
        <div className="flex items-center justify-between"><span>Short put {p.short_put}</span><DeltaBar value={p.put_delta} /></div>
        <div className="flex items-center justify-between"><span>Short call {p.short_call}</span><DeltaBar value={p.call_delta} /></div>
      </div>

      <div className="mt-3">
        <div className="relative h-2 rounded bg-zinc-800">
          <div className="absolute h-full rounded bg-sky-500/30" style={{ left: lane(lo), width: `calc(${lane(hi)} - ${lane(lo)})` }} title="180d HVN" />
          <div className="absolute top-[-3px] h-[14px] w-0.5 bg-emerald-400" style={{ left: lane(p.short_put) }} />
          <div className="absolute top-[-3px] h-[14px] w-0.5 bg-emerald-400" style={{ left: lane(p.short_call) }} />
          <div className="absolute top-[-4px] h-4 w-1 rounded bg-white" style={{ left: lane(p.spot) }} title="spot" />
        </div>
        <div className="mt-1 flex justify-between text-[10px] text-zinc-500 tabular-nums">
          <span>HVN {lo.toFixed(1)} – {hi.toFixed(1)}</span>
          <span>blue = 180d HVN · green = short strikes · white = spot</span>
        </div>
      </div>

      <div className="mt-2 flex flex-wrap gap-2">
        {p.pivots.map((v) => (
          <span key={v.name} className={`rounded border px-1.5 py-0.5 text-[10px] tabular-nums ${
            v.breached ? 'border-amber-500/50 text-amber-300' : 'border-zinc-800 text-zinc-500'}`}>
            {v.name} {v.level.toFixed(2)}{v.breached && ` · ${v.breach_min.toFixed(0)}/${PIVOT_LIMIT_MIN}m`}
          </span>
        ))}
      </div>

      {flagged && (
        <ul className="mt-2 space-y-1">
          {p.triggers.map((t, i) => (
            <li key={i} className="flex items-center gap-2 text-[11px] font-semibold text-red-400">
              <AlertTriangle size={12} /> {t.rule.replace('_', ' ').toUpperCase()}: <span className="font-normal text-red-300">{t.detail}</span>
            </li>
          ))}
        </ul>
      )}
      {ex?.steps?.length > 0 && (
        <div className="mt-2 font-mono text-[10px] text-zinc-500">
          ladder: {ex.steps.map((s) => s.price.toFixed(2)).join(' → ')} · {ex.message}
        </div>
      )}
    </div>
  )
}

function ScreenTable({ rows, halted }) {
  if (halted) {
    return <div className="p-4 text-xs text-red-400">Watchlist purged: term structure in backwardation.</div>
  }
  return (
    <table className="w-full text-[11px]">
      <thead className="text-left text-[10px] uppercase text-zinc-500">
        <tr><th className="px-3 py-1">Sym</th><th>Liq</th><th>Vol</th><th>BIS</th><th>ADX</th><th>HV20/90</th><th>Note</th></tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.symbol} className="border-t border-zinc-800/70">
            <td className="px-3 py-1 font-bold text-zinc-200">
              {r.symbol} {r.passed && <CheckCircle2 size={11} className="ml-1 inline text-emerald-400" />}
            </td>
            <td><Pill ok={r.liquidity}>{r.liquidity ? 'OK' : 'NO'}</Pill></td>
            <td><Pill ok={r.volatility}>{r.volatility ? 'OK' : 'NO'}</Pill></td>
            <td className={`tabular-nums ${r.breakout_threat ? 'text-red-400' : 'text-zinc-300'}`}>
              {r.bis}{r.breakout_threat && <Flame size={11} className="ml-1 inline" />}
            </td>
            <td className="tabular-nums text-zinc-300">{r.adx}</td>
            <td className="tabular-nums text-zinc-300">{r.hv_ratio}</td>
            <td className="max-w-[16rem] truncate text-zinc-500" title={r.reasons.join('; ')}>{r.passed ? 'deployable' : r.reasons[0]}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function Candidates({ rows }) {
  if (!rows.length) return <div className="p-4 text-xs text-zinc-500">No approved underlyings.</div>
  return (
    <table className="w-full text-[11px]">
      <thead className="text-left text-[10px] uppercase text-zinc-500">
        <tr><th className="px-3 py-1">Setup</th><th>Strikes</th><th>Credit</th><th>POP</th><th className="pr-3">OSQS</th></tr>
      </thead>
      <tbody>
        {rows.map((c, i) => (
          <tr key={i} className="border-t border-zinc-800/70">
            <td className="px-3 py-1 text-zinc-200">{c.symbol} {c.kind.replace('_', ' ')} <span className="text-zinc-500">w{c.width}</span></td>
            <td className="font-mono text-zinc-400">{c.strikes.join(' ')}</td>
            <td className="tabular-nums text-zinc-300">{c.credit.toFixed(2)}</td>
            <td className="tabular-nums text-zinc-300">{(c.pop * 100).toFixed(0)}%</td>
            <td className="pr-3">
              <div className="flex items-center gap-2">
                <div className="h-1.5 w-16 rounded bg-zinc-800">
                  <div className={`h-full rounded ${c.penalised ? 'bg-red-500' : 'bg-sky-400'}`} style={{ width: `${Math.min(c.osqs, 1) * 100}%` }} />
                </div>
                <span className="tabular-nums text-zinc-200">{c.osqs.toFixed(2)}</span>
                {c.penalised && <span className="text-[9px] font-bold text-red-400" title="short delta > 0.25 or POP < 68%">PEN</span>}
              </div>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export default function App() {
  const { state: s, connected } = useLiveState()

  if (!s) {
    return (
      <div className="flex h-screen items-center justify-center bg-zinc-950 text-sm text-zinc-500">
        <Radio size={16} className="mr-2 animate-pulse" /> Connecting to engine…
      </div>
    )
  }
  const demo = s.mode === 'DEMO'
  const nudge = (p, to) => post('/api/demo/spot', { symbol: p.symbol, price: to })

  return (
    <div className="min-h-screen bg-zinc-950 p-3 font-sans text-zinc-200">
      <header className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Layers size={18} className="text-sky-400" />
          <h1 className="text-sm font-bold uppercase tracking-[0.25em]">Viking</h1>
          <span className={`rounded px-2 py-0.5 text-[10px] font-bold ${demo ? 'bg-amber-500/20 text-amber-300' : s.live_orders ? 'bg-red-600 text-white' : 'bg-zinc-800 text-zinc-300'}`}>
            {demo ? 'DEMO · SYNTHETIC DATA · SIMULATED ORDERS' : s.live_orders ? 'LIVE ORDERS' : 'DRY-RUN'}
          </span>
          <span className="text-[11px] tabular-nums text-zinc-500">{new Date(s.clock).toLocaleString()}</span>
        </div>
        <div className="flex items-center gap-3">
          <Gatekeeper g={s.gatekeeper} />
          <span className={`flex items-center gap-1 text-[11px] ${connected ? 'text-emerald-400' : 'text-red-400'}`}>
            <Radio size={12} /> {connected ? 'stream' : 'reconnecting'}
          </span>
        </div>
      </header>

      <div className="grid gap-3 lg:grid-cols-5">
        <Panel title="Open positions · invalidation" icon={Crosshair} className="lg:col-span-3"
          right={<span className="text-[10px] text-zinc-500">{s.auto_close ? 'AUTO-CLOSE ON' : 'manual confirm'} · stop δ {DELTA_STOP}</span>}>
          {s.positions.length === 0 && <div className="p-4 text-xs text-zinc-500">No open positions.</div>}
          {s.positions.map((p) => <PositionCard key={p.id} p={p} />)}
        </Panel>

        <div className="space-y-3 lg:col-span-2">
          <Panel title="Phase 1 · screen" icon={Gauge}
            right={<span className="text-[10px] text-zinc-500">{s.watchlist.length} deployable</span>}>
            <ScreenTable rows={s.screen} halted={s.gatekeeper.halted} />
          </Panel>
          <Panel title="Phase 2 · OSQS ranking" icon={TrendingUp}>
            <Candidates rows={s.candidates} />
          </Panel>
          <Panel title="Chaser log" icon={Activity}>
            <ul className="max-h-32 space-y-1 overflow-auto p-3 font-mono text-[10px] text-zinc-400">
              {s.log.length === 0 && <li className="text-zinc-600">no exits yet</li>}
              {[...s.log].reverse().map((l, i) => <li key={i}>{l.position}: {l.message}</li>)}
            </ul>
          </Panel>
        </div>
      </div>

      {demo && (
        <Panel title="Demo controls" icon={TrendingDown} className="mt-3">
          <div className="flex flex-wrap items-center gap-2 p-3 text-[11px]">
            {s.positions.map((p) => (
              <button key={p.id} onClick={() => nudge(p, p.short_call - 0.4)}
                className="rounded bg-zinc-800 px-2 py-1 hover:bg-zinc-700">
                Push {p.symbol} to short call
              </button>
            ))}
            {s.positions.map((p) => (
              <button key={p.id + 'b'} onClick={() => nudge(p, p.pivots[0].level - 0.5)}
                className="rounded bg-zinc-800 px-2 py-1 hover:bg-zinc-700">
                Push {p.symbol} below support
              </button>
            ))}
            <button onClick={() => post('/api/demo/term', { front: 24, back: 20 })} className="rounded bg-zinc-800 px-2 py-1 hover:bg-zinc-700">Force backwardation</button>
            <button onClick={() => post('/api/demo/term', { front: 17.8, back: 19.9 })} className="rounded bg-zinc-800 px-2 py-1 hover:bg-zinc-700">Restore contango</button>
          </div>
        </Panel>
      )}
    </div>
  )
}
