# SPEC — Persistence & Retention (remediation Item D)

**Written:** 2026-07-30. Measured, not estimated.
**Status:** policy proposed; **no deletion implemented**, deliberately — see §6.

---

## 1. What the store actually holds

| | |
|---|---|
| database | **1.4 GB** |
| facts | **1,432,051** |
| candles | 570,151 |
| **facts from superseded engine versions** | **546,304 — 38.1%** |
| facts from current versions | 885,747 — 61.9% |

By kind:

| kind | facts | share |
|---|---|---|
| swing | 604,575 | 42.2% |
| zone | 304,428 | 21.3% |
| volume | 156,785 | 10.9% |
| ma | 121,590 | 8.5% |
| momentum | 99,105 | 6.9% |
| volatility | 59,059 | 4.1% |
| structure | 32,393 | 2.3% |
| setup_rejection | 14,690 | 1.0% |

Two facts about this shape drive everything below.

**Growth is dominated by the cheapest layer.** `swing` and `zone` together are
63.5% of the store and neither is read directly by a human — they are inputs to
structure, liquidity and setups. The expensive-to-recompute facts (setups, execs,
risk decisions) are a rounding error by comparison.

**38% of the store is already dead weight** — facts under `swing-v0.7`,
`zone-v0.9`, `exec-v0.7`, and every other version this codebase has moved past.
That number will keep rising, because the versioning discipline that makes this
project trustworthy *guarantees* it: every rule change mints a new generation and
leaves the old one intact.

---

## 2. The tension this policy has to resolve

The constitution says facts are **append-only** and that a past decision must be
reconstructable (§7, §8). Retention is deletion. Those pull against each other,
and resolving it by never deleting is not a policy — it is the absence of one,
which ends with an operator running out of disk at an unchosen moment.

The resolution: **append-only is a rule about how the system writes, not a
promise that every byte is kept forever.** What must be reconstructable is a
*decision*. A decision is reconstructable from the facts it consumed plus the
manifest that describes the rules — not from every intermediate fact that has
since been superseded by a newer generation of the same engine.

---

## 3. Retention classes

Four classes. Every fact kind belongs to exactly one.

### 3.1 PERMANENT — never deleted
`setup` · `exec` · `order` · `risk` · `account` · `cooldown` · `universe` ·
manifests · `research_baselines`

These *are* the track record. They are also tiny: setups, execs, orders and risk
decisions together are under 2% of the store. Deleting them to save space would
trade the entire evidentiary basis of the project for a rounding error.

### 3.2 DERIVED-CURRENT — kept while their version is live
`swing` · `structure` · `zone` · `liquidity` · `regime` · `ranges` · `ma` ·
`momentum` · `volatility` · `volume` · `cycle`

Deterministically recomputable from candles at any time. The only reason to keep
them is speed.

### 3.3 DERIVED-SUPERSEDED — eligible for pruning
The same kinds, at any `algo_version` that is no longer current AND is not
referenced by a PERMANENT fact.

The reference test is what makes this safe, and it is not optional: an `exec`
fact carries a `manifest_hash`, and a `setup_id` is version-scoped since S37.
A superseded `zone` generation that some retained `setup` was actually built
from is **not** eligible — pruning it would break the reconstruction the
constitution guarantees.

### 3.4 CANDLES — never deleted
570k rows, the ground truth everything else is derived from. Re-importing is
possible but not free: a venue's history window is finite, delisted symbols
cannot be re-fetched at all, and the OHLC integrity check (`importer-v0.3`)
would have to re-run over the whole span. Candles are the cheapest thing to keep
and the most expensive to lose.

---

## 4. Policy

```
PERMANENT            keep forever
CANDLES              keep forever
DERIVED-CURRENT      keep
DERIVED-SUPERSEDED   eligible for prune when ALL hold:
                       · version != the engine's current version
                       · no PERMANENT fact references its manifest_hash
                       · no version-scoped setup_id names it
                       · at least PRUNE_MIN_AGE_DAYS = 30 old
```

**Retention is measured in VERSIONS, not days.** A time-based rule ("delete
facts older than 90 days") would delete the oldest and most valuable history —
the four years of perp data that make any backtest meaningful — while leaving
last week's superseded generation untouched. Version-based retention deletes
exactly the thing that has no consumer.

`PRUNE_MIN_AGE_DAYS` exists because an A/B loser is evidence for as long as the
comparison is live. S3's `structure-v0.3` was retained deliberately as "the A/B
loser"; thirty days is long enough that a comparison has been read and recorded
in `BUILDLOG.md` before its inputs can go.

---

## 5. Operational shape

- **`prune.py --dry-run` first, always.** It reports what would go, by version
  and kind, with the freed bytes — and refuses to run without the flag.
- **Prune emits a fact.** A `retention` fact recording version, kind, count and
  reason. Deleting evidence without recording the deletion would be the one
  thing this store has never done.
- **VACUUM is a separate, explicit step.** SQLite does not return freed pages
  to the filesystem without it, and it rewrites the whole database — which is
  not something to do implicitly under a running scanner.
- **Never prune while a scan is in flight.** The heartbeat and the watchdog lock
  already answer "is the scanner busy"; `prune.py` must consult them and refuse.

---

## 6. Why nothing is implemented yet — and what would change that

**1.4 GB is not a problem.** It is a large file on a machine with plenty of
disk, and every deletion mechanism is a chance to delete the wrong thing. The
policy is written now so it predates the need, which was the whole point of
raising Item D; the code should follow when a threshold is crossed, not before.

**Triggers, any one of which makes this urgent:**
- store above ~10 GB, or
- superseded share above ~60% (it is 38.1% today), or
- a full-pipeline rebuild taking long enough to disrupt the scan cadence, or
- the first deployment to a machine where disk is actually constrained.

**Cheaper things to do first — DONE 2026-07-30, and they found nothing:**
1. `ANALYZE` run (1.0s). Query planner statistics now exist; they had not before.
2. Index coverage checked. Two composite indexes already cover the hot shapes:
   `ix_facts_query (symbol, tf, kind, algo_version, confirmed_at)` and
   `ix_facts_feed (kind, algo_version, confirmed_at, id)`.
3. The hot query measured **sub-millisecond before and after**. There is no
   performance problem to solve here, which strengthens the case for leaving
   pruning unimplemented: the only cost 1.4 GB is imposing today is disk.

**One measurement worth taking before any of it:** how long a full rebuild takes
from candles alone. If superseded facts can be regenerated in minutes, pruning
is nearly free; if it is hours, the 30-day window should widen. The current
partial rebuild runs ~36s over the admitted set and ~390s over all 59 symbols,
which suggests the former — but that is a rebuild of CURRENT versions, not a
reconstruction of a superseded one, and the two are not the same measurement.

---

## 7. Open question for the operator

**How long should an A/B loser outlive its comparison?** 30 days is a guess
chosen to exceed the interval between reading a result and recording it. The
honest alternative is to keep every superseded generation until its BUILDLOG
entry is written and then prune on that signal rather than on a calendar.
