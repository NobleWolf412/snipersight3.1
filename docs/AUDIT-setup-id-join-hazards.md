# AUDIT — `setup_id` join hazards after the S37/S40 version cascade

**First measured 2026-07-30 05:54 (setup-v0.8/exec-v0.9). Re-measured and
CORRECTED 2026-07-30 21:40 against setup-v0.13/exec-v0.17.** Two conclusions in
the first pass were wrong; §3 and §4 below say which and why. One fix applied
(`engine/risk.py`), one proposed fix withdrawn (`server.py`).

---

## 1. Cascade status — closed

| engine | at `a143691` | now | spec §2.1 asked for |
|---|---|---|---|
| `setups.py` | `setup-v0.6-draft` | `setup-v0.13-draft` | `setup-v0.7-draft` |
| `execsim.py` | `exec-v0.7-draft` | `exec-v0.17-draft` | `exec-v0.8-draft` |
| `risk.py` | `risk-v0.7-draft` | `risk-v0.16-draft` | `risk-v0.8-draft` |
| `scalein.py` | `scale-v0.2-draft` | `scale-v0.11-draft` | `scale-v0.3-draft` |

`tests/test_version_cascade.py` is the lockfile and passes. **Do not "bump
`EXEC_VERSION` to `exec-v0.8-draft`"** — that tag holds 564 `exec` and 1,370
`order` facts; writing to it again is the S37 defect, not its fix.

`setup_id` is version-scoped (`{symbol}|{tf}|{strategy}|{zone_id}|{SETUP_VERSION}`,
`engine/setups.py`), so cross-generation collisions are structurally impossible
for new facts. Any doc still saying "`setup_id` carries no version" is stale.

---

## 2. `setup_id` IS unique per VALIDATED setup — verified

Across **every** setup version in the store, the number of setup_ids that reach
`VALIDATED` at two different `confirmed_at` is **zero**. A zone validates once.
Repeat VALIDATED facts under one id (144 in the current book, 54 ids) are the
*same* instance re-recorded with fresher `confluence`, and collapsing them to the
newest is intended.

This is the correction that matters most: it means a consumer keyed on
`setup_id` is not merging distinct setups, and the first pass of this audit was
wrong to imply otherwise.

---

## 3. `engine/risk.py` — real defect, FIXED

Not "112 exits silently dropped". That framing was wrong. Where one setup_id
carries several `exec` facts (exec-v0.8: 112 of 452 ids; exec-v0.16: 7) those are
**one trade costed several ways** — the plan re-simulated after the cost/venue
manifest moved. Collapsing them is correct.

**The defect is that *which* one survived was arbitrary.** `store.get_facts`
orders `market_time, confirmed_at, id`, so a plain `exits[setup_id] = ...`
overwrite keeps whichever row the scan reaches last — which is *not* the newest
fact. Demonstrated:

```
scan order (market_time, id, manifest): [(11, 3, 'NEW'), (99, 2, 'OLD')]
plain last-wins picks: OLD        newest by fact id: NEW
```

The settled equity curve therefore moved with scan order rather than with the
current costing. Fixed by keying `(setup_id, available_at)` and breaking ties on
fact id explicitly, with the collision count surfaced in `rec.notes` as
`exit_manifest_collisions=N` — a merge that resolves silently is the whole defect
class.

Two constraints the fix has to respect, both verified on the store:

- **786 `exec` facts (v0.1–v0.6) have no `available_at`.** They fall back to the
  old setup_id-only path. A tighter key that silently matched *nothing* would be
  worse than the merge it replaced. (Two tests catch this if the fallback is
  removed: `test_core_hardening.TestRiskVenueContract.test_daily_halt_uses_start_of_day_equity`
  and `test_settings.DrawdownHaltTest.test_halt_trips_and_blocks_later_entries`.)
- The tighter key matches exactly as many intents as `setup_id` did (644 of 654),
  so it costs no exit.

---

## 4. `server.py` `lifecycle_map()` — NOT a defect. Proposed fix withdrawn

The first pass flagged `out[sid] = ...` as the same last-write-wins hazard. It
is not. Its query is `ORDER BY confirmed_at,id` — explicitly id-major within a
timestamp — so the survivor is genuinely the newest fact, which is exactly what
orders need (`PLACED` then `FILLED`, later one is the state). Combined with §2,
there is nothing to separate.

A composite-key version was written, tested and reverted: it changed no outcome
on any data that has ever existed, and its causal-attribution fallback was strictly
more ways to be wrong. `server.py` carries only a comment recording why the simple
key is correct. **Do not "fix" this again without first re-checking §2.**

---

## 5. The manifest field split — for whoever keys on it next

Duplicate counts per candidate key, all 17 exec books:

| join key | v0.7 | v0.8 | v0.16 | all others |
|---|---|---|---|---|
| `setup_id` | 25 | 112 | 7 | 0 |
| `(setup_id, available_at)` | 12 | 112 | 7 | 0 |
| `+ manifest_hash` | 0 | 0 | **7** | 0 |
| `+ execution_manifest_hash` | **12** | **112** | 0 | 0 |
| `+ both` | **0** | **0** | **0** | **0** |

The payload schema changed mid-history: older facts discriminate on
`manifest_hash`, newer ones on `execution_manifest_hash` (the v0.16 pairs differ
only in that field, plus `venue` and `cost_profile_version`). **Only both
together are unique across every book.** `limit_price` is `None` on every `exec`
fact — it exists only on `order` facts — so the `(setup_id, available_at,
limit_price)` key applies to orders, not to exec/outcome rows.

Reproduce:

```bash
cd app && python -X utf8 -c "import sqlite3,json;from collections import Counter;con=sqlite3.connect('file:data/snipersight.db?mode=ro',uri=True);[print(v,sum(1 for n in Counter((p['setup_id'],p.get('available_at'),p.get('manifest_hash'),p.get('execution_manifest_hash')) for p in (json.loads(r[0]) for r in con.execute(\"SELECT payload FROM facts WHERE kind='exec' AND algo_version=?\",(v,)))).values() if n>1)) for v in ['exec-v0.%d-draft'%i for i in range(1,18)]]"
```

---

## 6. Clean — checked, no change needed

| consumer | why |
|---|---|
| `engine/apexbridge.py` | Counts VALIDATED setups per version; reads `account`/`setup_rejection` by version. No `setup_id` join. |
| `server.py` `KIND_VERSIONS` | Every entry is a live reference to an engine's VERSION constant — followed the cascade automatically. |
| `server.py` `_baseline_setup_ids()` | Filters `algo_version IN (SETUP_VERSION, SCALE_VERSION)` dynamically. |
| `engine/telemetry.py` | Pure functions, no store reads, no joins. |
| `server.py` `/api/setup-trace` | Deliberately not version-pinned; reports `stale_versions` rather than 404-ing a setup that exists. |
| `engine/entrystats.py` | Pins `setup-v0.6`/`exec-v0.7`/`scale-v0.2` on purpose and joins on the composite key. Reads the historical mixed book correctly. Do not change. |

---

## 7. Unrelated failure seen while verifying

`tests/test_zone_causality.py::test_no_zone_counts_a_swing_it_could_not_see`
fails on the live store: **220 of 1146 recorded zones have a cluster count that
differs from the causal one** (e.g. `AAVEUSDT 4H`, recorded 6 vs causal 7). It
imports only `store`/`zones`/`swings` and is untouched by anything in this audit.
Separate defect in the zone engine, not triaged here.

*(Resolved same day, and the defect was not in the zone engine: `swings` was
re-emitting every promoted pivot each cycle because the promotion payload
embedded the per-bar `held_candles` counter, so the "cluster" recount grew
between a zone's write and the test's run. Root-caused 2026-07-31, fixed by
swing-v0.9 and the S53 full-lockfile cascade — see `app/BUILDLOG.md` S53. The
test passes on the current store.)*
