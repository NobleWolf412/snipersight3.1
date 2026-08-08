# SPEC — Log Retention (`data/engine.log`)

**Written:** 2026-08-07. Measured, not estimated.
**Status:** policy proposed; **nothing implemented**. The log is unmanaged today
and grows without bound.

Companion to [SPEC-persistence-retention.md](SPEC-persistence-retention.md),
which covers the fact store and deliberately says nothing about logs. This spec
covers the gap: `data/engine.log` is not in any retention class, is not rotated,
and holds the only record of some things that are not reconstructable.

---

## 1. What the file actually holds

Measured 2026-08-07 over the whole file.

| | |
|---|---|
| size | **475,128,174 bytes (474 MB)** |
| lines | 4,291,374 |
| span | 2026-07-20 23:19:41 → 2026-08-07 21:47:03 (18.0 days) |
| growth | **~26 MB/day — ~9.6 GB/year** at the current scan cadence |

By level:

| level | lines | share of bytes |
|---|---|---|
| DEBUG | 4,257,625 | **98.5%** |
| WARNING | 19,261 | 0.4% |
| INFO | 14,087 | 0.2% |
| ERROR | 401 | 0.0% |

**The file is 98.5% one line type.** Every DEBUG line is `RunRecorder.__exit__`
recording one engine run (`runlog.py:131`). Over the same span the
`engine_runs` table holds **4,171,356** rows across an identical window
(2026-07-20 23:19:41 → 2026-08-07 21:47:25). The DEBUG stream and the table are
the same event written twice — once queryable, once as text.

That is the whole finding. The 474 MB is not evidence; it is a second copy of a
table, in the least useful format, on the path `/api/console` polls.

---

## 2. What is NOT a second copy

The remaining 1.5% is the part with no other home.

**Operator write actions** (INFO). Every write endpoint in `server.py` logs
here and nowhere else: `MANUAL ARM` (205 in the window), `MANUAL ARM REFUSED`,
`SETTINGS CHANGED`, `CREDENTIAL stored/cleared`, `MANUAL SCAN requested`,
position close and adopt. The credential line is deliberately
event-only — *"log the EVENT, never the value"* (`server.py:2324`).

**Degraded paths** (WARNING, 19,261 lines). The conventions in `CLAUDE.md`
require a fallback to be audible, and this file is the mechanism that makes
that true — not a test. The window holds `drift check failed` (3,068), `UNIVERSE UNCHANGED:
rank` (950), `universe rank coverage` (846), `perp ranking unavailable` (470),
`REJECTED malformed candle` (506).

**Failures** (ERROR, 401 lines). `live cycle failed` (372) plus per-engine
errors, which also land in `engine_runs.status`.

**Loop heartbeat** (INFO, the majority of the 14,087). `cycle done`, `WAL
checkpoint returned`, `awake`, `sleeping 60.0s until`. Operationally useful for
about a day, evidence for nothing.

So the honest split is not "logs are disposable". It is: **one line type is
98.5% of the bytes and is duplicated in SQLite; a few thousand lines a fortnight
are the only copy that exists.**

---

## 3. Retention classes

Three. Every line belongs to exactly one, decided by level and prefix.

### 3.1 DUPLICATED — safe to drop at any age
DEBUG lines from `RunRecorder`. Reconstructable in full from `engine_runs`,
which carries strictly more: `run_id`, `input_fingerprint`,
`output_fingerprint`, `input_watermark`, `status`.

### 3.2 OPERATIONAL — keep a short window
INFO loop heartbeat (`cycle done`, `awake`, `sleeping`, `WAL checkpoint`).
Answers "is it alive and what is it doing now". Value decays in hours.

### 3.3 EVIDENCE — keep, and keep separately
Operator write actions, all WARNING, all ERROR. ~34k lines per 18 days —
roughly **2 MB/year**. Not reconstructable from anything: no `producer_run_id`
equivalent, no table. This is the class the whole spec exists to protect.

---

## 4. Policy

```
DUPLICATED    rotate; keep 2 files x 64 MB, discard beyond
OPERATIONAL   same rotation - it shares the stream
EVIDENCE      separate file, never rotated, never pruned
```

**Split by destination, not by deletion.** The obvious fix — rotate
`engine.log` — is wrong on its own, because rotation is size-based and the
evidence lines are 0.6% of the volume. Any size cap that controls the DEBUG
flood also discards operator actions at the same rate. The evidence has to
leave the hot stream *before* rotation applies to it.

Concretely: a second handler on the same logger, filtered to
`level >= WARNING or message startswith one of the operator-action prefixes`,
writing `data/engine-audit.log`. That file grows at ~2 MB/year and is never
touched. `engine.log` then rotates freely, because everything left in it is
either duplicated in SQLite or worthless after a day.

**Retention here is measured in BYTES, unlike the fact store.** The reasoning in
`SPEC-persistence-retention.md` §4 — that time-based rules delete the oldest and
most valuable history — does not carry over. Log lines have no versions, no
consumers holding references, and the valuable ones are being moved out by
class, not kept by age.

---

## 5. The constraint that makes this non-trivial

**Two processes write this file.** The scanner (`live.py`) and the API server
both call `get_logger()` and both append. `/api/console` documents exactly this
and uses a byte offset as its cursor *because* an in-process ring buffer would
show the operator half the story (`server.py:3148`).

That rules out `logging.handlers.RotatingFileHandler` as-is. It rotates by
renaming the open file, which two independent processes will race on, and which
fails outright on Windows while the other process holds a handle. Any
implementation has to either:

- rotate from **one** owner only — the watchdog, between child restarts, when
  neither child holds the file; or
- use a rotation scheme that never renames a file another process has open
  (write to a dated name, let the writers reopen on date change).

The watchdog option is the smaller change and fits the existing supervision
model. It is also the honest one: rotation becomes a supervised event with a
log line of its own, rather than something that happens mid-write.

**`/api/console` survives rotation already.** Its cursor handling resets to the
tail when `offset > size` (`server.py:3157`), which is exactly the state a
rotation produces. The visible effect is the console jumping to the end once.
Acceptable, and worth stating so nobody later reads it as a bug.

---

## 6. Why nothing is implemented here

Same posture as the retention spec it accompanies. The measurement is the
deliverable; the change touches `runlog.py`, which every engine imports, and the
file `/api/console` reads on a 30s poll from every cockpit surface. That is not
a change to make in the same breath as writing it down.

What is decided: the file needs a policy, the policy is a split rather than a
truncation, and the split is worth doing before the log passes a gigabyte —
which at the measured rate is **around 2026-09-27**.

---

## 7. Not covered

`watchdog.log` (1.6 MB), `live-scanner.err.log` (0.6 MB) and `live-exit.log`
(9.8 KB) are all small and none is on a growth path that matters. They are named
here so a later reader knows they were looked at and set aside, not missed.
