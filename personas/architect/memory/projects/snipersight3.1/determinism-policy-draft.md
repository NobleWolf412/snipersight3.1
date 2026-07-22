---
name: SniperSight3 Determinism Policy — Draft (Remediation Item A)
description: Architect draft of the Determinism Policy subsection to be added under §4 of the Constitution. Fixes ATR canonical definition (period, Wilder seed, TR[0]), numeric library, precision, enumerated rounding boundaries, tie-break ordering (including intra_bar_seq assignment), candle-boundary origin, replay granularity, algo-source hash target, and canonical fact serialization. Addresses audit FINDING-002, 003, 006, 011 (partial), 017; re-audit A-01…A-08; and re-verification R-01…R-07 (Decimal-zero recipe, Decimal special values, ATR recursion off-by-one, D1 rounding-wording, negative zero, tar portability, hash-algorithm rationale).
type: project
---

# Determinism Policy — Draft §4.1

**Status:** Architect draft **v0.3**, 2026-07-17. Supersedes v0.2. Incorporates re-audit fixes A-01…A-08 (v0.2) and re-verification fixes R-01…R-07 (v0.3). Requires user sign-off and closes-with §30 (F) before merging into Constitution — see freeze caveat in re-audit §1.
**Scope:** Every rule in this policy is normative for v0 Layer-2 fact emission and Layer-1 canonical candles. Layer-3+ modules may add stricter rules but not looser.

---

## D1. Numeric library and precision

- **All price and threshold arithmetic uses `decimal.Decimal` (Python) or equivalent fixed-precision decimal type.** No `float64` in Layer-1 or Layer-2. Rationale: crypto venue tick sizes are exact decimals; float64 introduces representation error that compounds across ATR chains.
- **Working precision:** 28 significant digits (Python `Decimal` default). Sufficient for 8-decimal BTC quantities × 2-decimal USDT prices with headroom.
- **Rounding mode:** `ROUND_HALF_EVEN` (banker's rounding) for all division results. Applied only at explicit rounding boundaries; intermediate values retain full working precision.
- **Rounding boundaries — closed enumeration (A-03).** Rounding may occur *only* at the following points; any other rounding is a determinism defect:
  1. **Ingest quantization:** prices read from a venue kline are already tick-quantized by the venue; no further rounding is applied at ingest. Volumes are stored as reported.
  2. **Display / UI:** Layer-5 rendering only. Layer-1 and Layer-2 never emit rounded values into a fact body.
  3. **Canonical serialization for `content_hash` and `input_hash`:** Decimals are serialized using the fixed rule in §D8 (no numerical rounding — string-form is normalized only for representation, not magnitude).
  Distinguish **context-level rounding** (the deterministic `ROUND_HALF_EVEN` at 28-digit working precision that every `Decimal` division applies — unavoidable and part of the canonical arithmetic) from **user-level rounding** (`round()`, `Decimal.quantize()`, truncation, or any ad-hoc reduction of precision written in application code). Context-level rounding at 28-digit `ROUND_HALF_EVEN` is the **only** rounding applied inside the ATR recursion. User-level rounding is **forbidden** inside the ATR recursion, in any intermediate quantity that feeds a subsequent computation, and in every rule-predicate comparison (`<`, `≤`, `==`) — those must operate on the full-precision `Decimal` operands directly. Comparing rounded values in a rule predicate is a determinism defect.
- **Display precision:** venue tick size (BTCUSDT = 0.01 USDT, ETHUSDT = 0.01 USDT for spot). All price comparisons in rules use full-precision `Decimal`; tick-quantization applies to display only.

## D2. ATR canonical definition

**ATR is a single canonical function.** No module may compute ATR differently.

- **Period:** 14 bars.
- **Smoothing:** Wilder's RMA (recursive: `atr[i] = (atr[i-1] * 13 + tr[i]) / 14` for `i ≥ 15`, 1-based bar index; the seed at `i = 14` is defined below and the recursion first *applies* at bar 15, dereferencing the seed as `atr[14]`).
- **True range:** `TR[i] = max(high[i] - low[i], |high[i] - close[i-1]|, |low[i] - close[i-1]|)` for `i ≥ 2`. For the first bar of a stream (or the first bar after a gap-reset), **`TR[1] = high[1] - low[1]`** (A-06). `prev_close` is undefined at the stream origin.
- **Seed (A-02):** `atr[14] = SMA(TR[1..14]) = (TR[1] + TR[2] + … + TR[14]) / 14`. This is the classical Wilder seed.
- **Per-timeframe:** ATR is computed independently per timeframe from that timeframe's canonical candles. A rule referring to "0.05 ATR" on a 15m break uses 15m ATR(14).
- **Warmup:** Bars 1..14 of any timeframe have `atr = NULL`. Any Layer-2 rule with an ATR-scaled threshold emits **no fact** during warmup and records a diagnostic (see §D9).
- **Missing bars:** If a gap is detected in the source stream (per §19 importer), ATR resets and re-enters warmup at the first bar after the gap. The re-seed uses the same SMA(TR[1..14]) rule over the first 14 post-gap bars.

## D3. Tie-break and total ordering

Every emitted Layer-2 fact carries a **total order key** `(bar_close_ts, timeframe_rank, entity_kind_rank, intra_bar_seq)`.

- `bar_close_ts`: UTC epoch nanoseconds at bar close.
- `timeframe_rank`: fixed integer, larger = higher timeframe. `1W=5, 1D=4, 4H=3, 1H=2, 15m=1, 5m=0`.
- `entity_kind_rank`: fixed integer per entity kind to break ties when a swing and a zone confirm on the same bar close. Order: `candle=0, swing=1, structure_break=2, zone=3, liquidity=4, regime=5`.
- `intra_bar_seq`: 0-based counter for multiple facts of same kind on the same bar (rare, e.g., two liquidity sweeps in one bar).

**`intra_bar_seq` assignment rule (A-04).** For a set of same-kind facts confirming at the same `(bar_close_ts, timeframe_rank, entity_kind_rank)`, `intra_bar_seq` is the rank (0-based, ascending) under the following comparator, applied in order and stopping at the first differing key:
  1. `body.price` if the body has a scalar `price` field (e.g., LiquidityLevel); or `body.anchor_price` for swings; or `body.break_price` for structure breaks; or `body.top` for zones. Comparison is ascending `Decimal`.
  2. `body.side` if present, lexicographic ascending (`high` < `low`, `long` < `short`, `demand` < `supply` — alphabetical by enum spelling).
  3. `body.direction` if present, alphabetical ascending (`down` < `up`).
  4. Deterministic fallback: `content_hash` (as defined in §D8), lexicographic ascending. This last key guarantees a total order because §D8 excludes `intra_bar_seq` from the hash input, so ties on keys 1–3 always resolve here.

**Two facts with identical `(bar_close_ts, timeframe_rank, entity_kind_rank, intra_bar_seq)` and different content are a determinism bug and must fail replay validation.**

## D4. Candle-boundary origin

- **Venue:** Binance USDT-margined spot (klines API) for BTCUSDT and ETHUSDT.
- **Boundary rule:** UTC-anchored, matching Binance kline boundaries exactly.
- **Weekly candle:** starts Monday 00:00:00 UTC, ends Sunday 23:59:59.999 UTC. (Binance kline `1w` convention.)
- **Daily candle:** starts 00:00:00 UTC.
- **Intra-day bucketing (A-07):**
  - **4H:** bars begin at UTC hours `{0, 4, 8, 12, 16, 20}`.
  - **1H:** bars begin at each UTC hour `{0..23}`.
  - **15m:** bars begin at UTC minutes `{0, 15, 30, 45}` of each hour.
  - **5m:** bars begin at UTC minutes `{0, 5, 10, …, 55}` of each hour.
  This matches Binance kline conventions.
- **No exchange-local or user-local time appears at Layer-1 or Layer-2.** UI (Layer-5) may render local time; underlying facts remain UTC.

## D5. Replay granularity

- **v0 replay is event-clock at bar close, per timeframe, ordered by D3.**
- A fact goes `PROVISIONAL` at the bar close on which its provisional criteria first hold, and `CONFIRMED` at the bar close on which its confirmation criteria first hold. It never toggles state mid-bar.
- Sub-bar replay (tick-tape or 1s resampling) is deferred to v1 and out of scope for §29 acceptance.
- **Cross-timeframe ordering:** on a bar close instant when multiple timeframes align (e.g., 1H and 4H both close at 04:00 UTC), facts emit in **ascending timeframe order** (low → high). Rationale: higher-timeframe facts are supersets of lower-timeframe evidence; producing them last lets HTF references check LTF facts already committed at the same instant without a two-pass emitter.

## D6. Version and lineage stamping

Every Layer-2 fact carries:
- `algo_version`: semver of the emitting module.
- `policy_version`: semver of this Determinism Policy document.
- `content_hash`: BLAKE2b-256 over the canonical serialization defined in **§D8**. Input field set is enumerated in §D8.
- `input_hash`: BLAKE2b-256 of the ordered input-candle window (see §D8 for canonicalization).

**Hash-algorithm asymmetry (R-07).** `content_hash` and `input_hash` use **BLAKE2b-256** — chosen for speed on the hot fact-emit path (a full replay hashes millions of facts). `algo_source_hash` uses **SHA-256** — chosen to interoperate with standard binary-signing and supply-chain toolchains (cosign, in-toto, sigstore) which consume SHA-256 by default. Both algorithms are cryptographically adequate for their use; the asymmetry is deliberate.

**Algo-source hash target (A-05).** The version registry key is `(algo_version, algo_source_hash)` where:
- `algo_source_hash = SHA-256` of a **pinned build artifact**, specifically a sorted-tar (POSIX ustar, no timestamps, no owner metadata — `tar --sort=name --owner=0 --group=0 --numeric-owner --mtime='UTC 1970-01-01'`) containing:
  - the Layer-1 + Layer-2 source tree at the versioned commit,
  - the lockfile pinning transitive Python dependencies (`poetry.lock` or `requirements.txt` with `--hash`),
  - the pinned Python interpreter version string (e.g., `python-3.12.4`),
  - the `policy_version` string.
- Live file-tree hashing is **not** acceptable (imports mutate). Container-image hashing is acceptable as a superset but the tarball rule above is the minimum required for registry acceptance.
- **Tar toolchain (R-06).** `--sort=name` and `--mtime` are GNU-tar extensions and are absent from BSD tar (macOS default) and busybox tar. **GNU tar ≥ 1.28 is required for the reference build**; both the CI image and the developer build instructions MUST pin it. An alternative deterministic recipe using `find <tree> -print0 | LC_ALL=C sort -z | xargs -0 tar --format=ustar --owner=0 --group=0 --numeric-owner --mtime='UTC 1970-01-01' -cf …` MAY be substituted **provided the resulting byte stream is byte-identical to the GNU-tar output on the same tree** (verified against a golden tarball hash in CI).
- The build step that produces the tarball is documented in remediation item D (Persistence & Audit Store).

**Immutability mechanism (resolves FINDING-011 partially):** an append-only version registry keyed by `(algo_version, algo_source_hash)` refuses to load any backtest / paper trade / live record whose stamped versions are not in the registry. Registry lives in the audit store (item D).

## D7. Non-determinism sources explicitly forbidden in Layer-1/2

- Wall-clock reads inside fact computation (only `bar_close_ts` from candle stream).
- Random number generation without a stamped seed.
- Set / dict iteration order sensitivity (use sorted iteration when order affects output).
- Parallelism whose output depends on scheduling.
- Floating-point in any rule predicate.
- **Locale-dependent parsing (A-08):** all decimal ingest uses `Decimal('<string>')` with a locale-independent, `.`-decimal string. `float(s)` and `locale.atof(s)` are forbidden on price/volume fields.
- **Unpinned library stack (A-08):** all runtime dependency versions (Python, numpy, pandas, decimal-compat shims, hashing libs) are pinned via the lockfile hashed into `algo_source_hash` (§D6). Behavior differences across versions (e.g., pandas 2.0 groupby ordering, numpy sort stability) are neutralized by pin-and-hash, not by defensive code.

Layer-3+ (strategy, ML) may use RNG *only* with a seed persisted alongside the run manifest.

## D8. Fact Identity — canonical serialization and content_hash inputs (A-01 + B-01)

This subsection is the **single source of truth** for `content_hash` and `input_hash`. Draft B §S2 references this section; do not re-specify elsewhere.

### D8.1 Canonical serialization format

`content_hash` and `input_hash` are BLAKE2b-256 (32-byte digest) computed over a byte string produced by **RFC 8785 JSON Canonicalization Scheme (JCS)** with the following bindings:

- **Encoding:** UTF-8, no BOM.
- **Object member ordering:** lexicographic by UTF-16 code unit, per RFC 8785.
- **Strings:** RFC 8785 rules; no unnecessary escapes.
- **Integers:** JSON number form, no leading zeros, no `+`, no decimal point.
- **`Decimal` values:** serialized as a **JSON string** (not a JSON number — JCS number canonicalization does not preserve trailing zeros or precision). The canonical string is produced by the following algorithm, in order:
  1. **Finiteness check.** If `d.is_nan()` or `d.is_infinite()` (including `NaN`, `sNaN`, `Infinity`, `-Infinity`), **raise at fact-emit time** — such values MUST NOT reach the canonicalizer. Decimal values in a fact body MUST be finite.
  2. **Zero case (R-01, R-05).** If `d.is_zero()`, emit the literal string `"0"`. This applies regardless of exponent (`Decimal("0")`, `Decimal("0.0")`, `Decimal("0.00")`, `Decimal("0E-8")`) and regardless of sign (`Decimal("-0")` also serializes as `"0"` — negative zero is not preserved). This branch is required because `format(Decimal("0.00").normalize(), 'f')` returns `"0.00"`, not `"0"`; the recipe below would otherwise contradict the rule for every zero with a non-zero exponent.
  3. **Finite non-zero case.** Emit `format(d.normalize(), 'f')` — fixed-point notation with no exponent, no leading zeros before the decimal point except a single `0`, no trailing zeros after the decimal point, and a leading `-` only if negative.
  Examples: `Decimal("1.2300")` → `"1.23"`; `Decimal("0.00")` → `"0"`; `Decimal("0E-8")` → `"0"`; `Decimal("-0")` → `"0"`; `Decimal("-42")` → `"-42"`; `Decimal("100")` → `"100"`.
- **Timestamps (`bar_close_ts`, `bar_open_ts`, etc.):** integer nanoseconds since UTC epoch, serialized as a JSON number (they always fit in JCS's I-JSON safe integer range for the target date span).
- **Enums:** serialized as their string spelling (e.g., `"BOS"`, `"demand"`).
- **Arrays:** order-preserving; array element order is part of the hash input.
- **Absent optional fields:** omitted entirely, not serialized as `null`. `null` and absence are distinct.

A **golden test vector** (a hand-computed `Fact` body + expected canonical bytes + expected 32-byte digest hex) is required in the audit store's `policy-vectors/` directory and re-verified in CI. Item D (Persistence) owns the vector store; §D8.1 owns the format. The vector set MUST include, at minimum: (a) a Fact with a positive Decimal body value, (b) a Fact with a negative Decimal, (c) a Fact with `Decimal("0")`, (d) a Fact with `Decimal("0.00")` (non-zero exponent zero — exercises R-01), (e) a Fact with `Decimal("-0")` (exercises R-05), and (f) a Fact-emit attempt with `Decimal("NaN")` or `Decimal("Infinity")` that MUST raise before serialization (exercises R-02).

### D8.2 `content_hash` input field set

`content_hash` is computed over a JCS object with **exactly** these keys, in the natural order JCS enforces:

**Included:**
- `kind` — enum string
- `symbol` — string
- `timeframe` — enum string
- `body` — the kind-specific body object (Draft B §S3), fully serialized per §D8.1
- `order_key.bar_close_ts` — integer nanoseconds
- `order_key.timeframe_rank` — integer
- `order_key.entity_kind_rank` — integer
- `provenance` — array of `{timeframe, bar_close_ts}` objects (see Draft B §S2, updated per B-02)

**Excluded** (mutating any of these must not change `content_hash`):
- `state`, `state_history` — mutate on lifecycle transitions; a fact's *identity* is fixed at emit time.
- `algo_version`, `policy_version` — orthogonal to fact identity; identity is anchored to inputs+body, versioning is tracked separately in the registry.
- `content_hash`, `input_hash`, `fact_id` — self-reference; would be circular.
- `order_key.intra_bar_seq` — assigned *from* `content_hash` per §D3, so excluded to avoid circularity.

`fact_id = "<kind>:" + hex(content_hash)`. It is stable across all lifecycle transitions of the same fact.

### D8.3 `input_hash` input field set

`input_hash` is computed over a JCS array of `Candle` records (Draft B §S1) — the exact ordered candle window read by the emitting algorithm. Per candle, the following fields are included in the canonical serialization: `{symbol, venue, timeframe, bar_open_ts, bar_close_ts, open, high, low, close, volume, source_lineage}`. `ingest_batch_id` and `gap_before` are **excluded** — they are metadata about how the candle arrived, not the candle itself.

### D8.4 Consequences for §D3 and §S2

- §D3's `intra_bar_seq` fallback comparator (`content_hash` lexicographic) is well-defined because `content_hash` is computed *before* `intra_bar_seq` is assigned.
- Draft B §S2 must change `provenance` from `[bar_close_ts, ...]` to `[{timeframe, bar_close_ts}, ...]` for §D8.2 to apply to multi-timeframe facts (closes B-02).

## D9. Diagnostic channel binding

Warmup, gap, and other emitter diagnostics (§D2 `atr_warmup`) are written to the **diagnostic record stream** owned by item D (Persistence). Schema: `{diagnostic_id, at_bar_close_ts, symbol, timeframe, algo_version, policy_version, reason: str, detail: dict}`. Retention and query API are defined in item D. This subsection binds the diagnostic field to a real channel so it is not orphaned (closes A-09 nit).

---

## Open items requiring user sign-off

1. **Venue = Binance spot.** Confirm — audit doesn't specify and §18 only names symbols. If it should be Binance perp (BTCUSDT-PERP funding-relevant per §11), boundaries are still UTC but the symbol set changes.
2. **ATR period = 14, Wilder RMA.** Standard, but user may want a different default for crypto (some houses use 20).
3. **Decimal over float.** Non-trivial performance cost. Confirm acceptable for v0's offline-replay workload.
4. **Weekly boundary = Monday UTC.** Confirm — some analysts prefer Sunday-anchored weeks. Binance kline is Monday.
