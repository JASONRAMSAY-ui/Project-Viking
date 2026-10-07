"""Log today's real candidate credits (read-only). Run once per trading day after the open.
Usage: python scripts/paper_snapshot.py   -> appends to paper/paper_log.jsonl"""
from viking.live import LiveRuntime
from viking import papertrade as pt

rt = LiveRuntime()
rt.tick()
if rt.error:
    raise SystemExit(f"runtime error: {rt.error}")
rows = pt.snapshot_rows(rt)
print(f"candidates: {len(rows)}  new rows logged: {pt.append(rows)}  signals today: {sum(r['signal'] for r in rows)}")
