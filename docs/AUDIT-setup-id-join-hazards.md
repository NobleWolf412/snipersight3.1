# AUDIT — `setup_id` join hazards after the S37/S40 version cascade

**Measured 2026-07-30 against `app/data/snipersight.db`.** Read-only audit; no
engine code changed. Written from a second session while another was mid-sweep
across `app/engine/`, so the two hazards in §3 were deliberately left unpatched
rather than risk clobbering in-flight edits. Line numbers are as of this date.

---

## 1. Cascade status — done, and further than the spec asked

| engine | at `a143691` | now | spec §2.1 target |
|---|---|---|---|
| `setups.py` | `setup-v0.6-draft` | `setup-v0.8-draft` | `setup-v0.7-draft` |
| `execsim.py` | `exec-v0.7-draft` | `exec-v0.9-draft` | `exec-v0.8-draft` |
| `risk.py` | `risk-v0.7-draft` | `risk-v0.8-draft` | `risk-v0.8-draft` ✓ |
| `scalein.py` | `scale-v0.2-draft` | `scale-v0.3-draft` | `scale-v0.3-draft` ✓ |

`tests/test_version_cascade.py` is the lockfile for this and passes (5 tests).
Its docstring records the two occurrences: **S37** (execsim) and **S40** (risk and
scalein left behind after setup-v0.8/exec-v0.9).

**Do not "bump `EXEC_VERSION` to `exec-v0.8-draft`."** That tag already holds 564
`exec` and 1,370 `order` facts. Writing to it again is the S37 defect, not the
fix for it.

**The root cause is fixed structurally, not by a join convention.** `setup_id` is
now version-scoped — `{symbol}|{tf}|{strategy}|{zone_id}|{SETUP_VERSION}`
(`engine/setups.py:632`, `:559`). Cross-generation collisions are impossible for
new facts. Any doc still claiming "`setup_id` carries no version" is stale.

---

## 2. The discriminator is `manifest_hash` — not `limit_price`

`limit_price` is `None` on **every** `exec` fact; it exists only on `order` facts.
So the composite key `(setup_id, available_at, limit_price)` does not apply to the
exec side. `entrystats.py` correctly substitutes `entry` there
(`entrystats.py:483`) — but `entry` is not sufficient either.

Duplicate counts per candidate key, all three exec books:

| join key | `exec-v0.7` | `exec-v0.8` | `exec-v0.9` |
|---|---|---|---|
| `setup_id` alone | 25 | 112 | 0 |
| `(setup_id, available_at)` | 12 | 112 | 0 |
| `(setup_id, available_at, entry)` | 0 | 16 | 0 |
| `(setup_id, available_at, manifest_hash)` | **0** | **0** | **0** |

Reproduce:

```bash
cd app && python -X utf8 -c "import sqlite3,json;from collections import Counter;con=sqlite3.connect('file:data/snipersight.db?mode=ro',uri=True);[print(v,sum(1 for n in Counter((json.loads(r[0])['setup_id'],json.loads(r[0]).get('available_at'),json.loads(r[0]).get('manifest_hash')) for r in con.execute(\"SELECT payload FROM facts WHERE kind='exec' AND algo_version=?\",(v,))).values() if n>1)) for v in ('exec-v0.7-draft','exec-v0.8-draft','exec-v0.9-draft')]"
```

### Why `entry` leaves 16: `exec-v0.8-draft` holds three manifests

The two `exec` facts for `SOLUSDT|1D|PULLBACK|SOLUSDT|1D|SUPPLY|1685836800|setup-v0.7-draft`
(fact ids 922214, 945938) share `market_time`, `confirmed_at`, `available_at`,
`outcome` and `r_multiple`, and differ only in:

```
entry            21.33        vs  21.453857763700
entry_fee_role   TAKER        vs  MAKER
fees_price_units 0.0263802... vs  0.0157276...
mae_r / mfe_r    1.40 / 0.70  vs  1.45 / 0.89
manifest_hash    daedfead...  vs  7b3aaa5a...
```

TAKER vs MAKER on the same trade means `exec-v0.8-draft` was run under **two
different execution models** and both wrote to that one tag — a two-books-under-
one-tag instance *inside* a single version, which no version bump separates
retroactively. `exec-v0.7` carries 2 manifests, `exec-v0.8` 3, `exec-v0.9` 3.
`manifest_hash` is therefore the only key that is stable under this, and it is
part of fact identity whether or not a version moves.

---

## 3. Outstanding — two readers still merge on bare `setup_id`

Both are last-write-wins over a dict keyed on `setup_id` alone. Neither is fixed
by version-scoping, because in both cases the collision is *within* one version.

### 3.1 `engine/risk.py:118` (read back at `:324`)

```python
exits[p["setup_id"]] = {"exit_ts": r["confirmed_at"], ...}   # :118
ex = exits.get(it["setup_id"])                                # :324
```

Measured: **112 of 452 setup_ids in `exec-v0.8-draft` carry more than one `exec`
fact**, so 112 exits are silently discarded and `fill_outcome` / `open_pos`
settlement take whichever row happened to land last. `exec-v0.9-draft` shows 0
collisions today only because it is a fresh single-pass book — it already has 3
manifests and will accumulate them exactly as v0.8 did.

Note the intent side cannot supply the *exec* manifest: setup facts carry their
own `manifest_hash`/`cost_manifest_hash`, which is a different manifest. So the
fix is not a symmetric key — `exits` must be keyed
`(setup_id, available_at, manifest_hash)` and the lookup at `:324` must resolve
the current exec manifest (or select deterministically and record the collision
rather than absorb it).

### 3.2 `server.py:199` — `lifecycle_map()`

```python
out[sid] = {"confirmed_at": confirmed_at, **p}
```

Same shape, applied to `risk`, `order` and `exec` (`:202-204`), feeding
`/api/setup-telemetry`. `ORDER BY confirmed_at,id` makes the survivor
deterministic but still arbitrary among manifests.

---

## 4. Clean — checked, no change needed

| consumer | why it is safe |
|---|---|
| `engine/apexbridge.py` | Counts VALIDATED setups per version (`:103-107`), reads `account`/`setup_rejection` by version (`:187`). No `setup_id` join. |
| `server.py` `KIND_VERSIONS` (`:17-30`) | Every entry is a live reference to an engine's VERSION constant — followed the cascade automatically. |
| `server.py` `_baseline_setup_ids()` (`:38-60`) | Filters `algo_version IN (SETUP_VERSION, SCALE_VERSION)` dynamically. Was pulling a 3-generation `scale-v0.2` set; the `scale-v0.3` bump resolved it. |
| `engine/telemetry.py` | Pure functions (`classify_failure`, `build_record`, `summarize_diagnostics`) — no store reads, no joins. The hazard is in its callers, i.e. §3.2. |
| `server.py` `/api/setup-trace` | Deliberately not version-pinned and documents why; reports `stale_versions` instead of 404-ing a setup that plainly exists. |
| `engine/entrystats.py` | Pins `setup-v0.6`/`exec-v0.7`/`scale-v0.2` as module constants on purpose (`:103-116`) and joins on the composite key. Reads the historical mixed book correctly. Do not change. |

---

## 5. Evidence appendix — store snapshot

```
exec   exec-v0.7-draft  346    order  exec-v0.7-draft   694
       exec-v0.8-draft  564           exec-v0.8-draft  1370
       exec-v0.9-draft  340           exec-v0.9-draft   688

setup  setup-v0.6-draft  919   risk   risk-v0.4-draft  361 risk / 2 account
       setup-v0.7-draft 4538          risk-v0.6-draft    1 risk / 3 account
       setup-v0.8-draft 2507          risk-v0.7-draft    0 risk / 4 account
       scale-v0.1-draft    6
       scale-v0.2-draft    3
```

`scale-v0.2-draft`'s three `setup` facts spanned **three** setup generations
under one tag — the S40 collision, materialised:

```
TAOUSDT|1D|PULLBACK|TAOUSDT|1D|DEMAND|1780704000|ADD1                    <- pre-fix, unversioned parent
SOLUSDT|4H|REVERSAL|SOLUSDT|4H|DEMAND|1773000000|setup-v0.7-draft|ADD1
SOLUSDT|4H|REVERSAL|SOLUSDT|4H|DEMAND|1773000000|setup-v0.8-draft|ADD1
```
