"""Fail-closed A-to-Z pipeline quality and reconciliation audits.

The checks in this module are observational. They do not alter strategy rules.
Market-input blockers can stop downstream engines; full-pipeline blockers mark
performance as invalid for interpretation until the evidence is repaired.
"""
from __future__ import annotations

import json
import time
from decimal import Decimal

from . import aggregator, importer, listings, venues

QUALITY_VERSION = "quality-v0.4-draft"
# v0.4: the v0.3 demotion held a list of everything that could still resolve a
# trade across the hole, and that list was short by one — execution.monitor_paper
# walks candles to settle durable PAPER intents and was never in it. A symbol
# carrying one is now pinned, so the same delisted market can report BLOCKED
# under v0.4 where v0.3 reported PASS. That is a different verdict for the same
# store, which is a version, not an edit.
# v0.3: a market its VENUE no longer lists reports RETIRED_SEQUENCE_GAPS
# (PASS, at rung SERVE_FLAG — a note, NOT a warning) instead of SEQUENCE_GAPS
# (BLOCKED). Its holes cannot be repaired —
# no import can serve history for a market that does not exist — so blocking
# halted the store forever with no action available to the operator (CRVUSDT,
# delisted from Phemex, absent from /public/products and the 24h ticker while
# BTCUSDT returned a full 1000 rows; verified against the live API 2026-09-01).
# The delisting evidence is `listings.listed_on_venue`, NOT universe membership:
# `members` is the top_n slice of the ranking, so an earlier attempt keyed on it
# demoted 81 live Phemex perps and was reverted (ba9d8fb). Two guards keep this
# narrow — a symbol with an unresolved order still BLOCKS, and only gaps demote.
# v0.2: venue-acknowledged empty buckets remain auditable SERVE_FLAG notes but
# no longer turn an otherwise healthy scanner DEGRADED. They are evidence that
# a bucket did not exist, not a repair queue; unexplained sequence gaps remain
# blocking. The persisted read model now carries notes separately from warnings.
# v0.1: the persisted verdict distinguishes current missing producer lineage
# from historical/operational facts, and repeated imports of the same empty
# window no longer multiply the anonymous known-gap budget.  Both change what
# Diagnostics calls an issue, so the read model carries a version from birth.

STAGES = ("DATA", "AGGREGATION", "FACTS", "SETUP", "RISK", "EXECUTION", "ACCOUNTING")
ORDER = {"PASS": 0, "DEGRADED": 1, "BLOCKED": 2}

# Kill-Switch Ladder — the single vocabulary every audit finding declares itself
# in, and the routing table the watchdog dispatches on. Adding a new _issue()
# code without an entry in CODE_RUNG falls back to HALT/SERVE_FLAG (see
# _rung_for) — safe, but the mapping must be made explicit in the same change.
RUNGS = ("SERVE", "SERVE_FLAG", "QUARANTINE", "AUTO_DISABLE", "HALT")
RUNG_ORD = {r: i for i, r in enumerate(RUNGS)}

CODE_RUNG = {
    # DATA
    "NO_CANDLES":              "HALT",
    # Per-(symbol, tf) — audit_market_inputs `continue`s past an unknown tf and
    # evaluates the rest, so this cannot break the pipeline the way HALT
    # implies. It was HALT and the watchdog restart-looped a live scanner every
    # ~7 minutes on 2026-08-08 over 27 findings that were never data at all:
    # THIS module reads importer.TF_SECONDS from whatever commit the auditing
    # process booted from, `5m` had been added after the supervisor started,
    # and 27 symbols carried 5m candles. The rows were fine; the reader was
    # two days stale, and restarting the SCANNER could never fix either.
    # Same reasoning as STALE_SERIES → QUARANTINE and watchdog.py's "a data
    # verdict is not a process fault" — plus one this code can't see: the
    # finding may indict the auditing process itself, and the rung must not
    # hand that process a gun.
    "UNKNOWN_TIMEFRAME":       "QUARANTINE",
    "OHLC_INVARIANT_FAILURE":  "HALT",
    "SEQUENCE_GAPS":           "HALT",
    "DEVELOPING_CANDLES":      "HALT",
    "STALE_SERIES":            "QUARANTINE",   # per-symbol/tf degrade
    # Same rung and reasoning as STALE_SERIES: a per-symbol finding on a market
    # that no longer exists to trade. HALT would hand the watchdog a restart
    # that cannot heal it (the 2026-08-08 loop) — no restart relists a market.
    # SERVE_FLAG, not QUARANTINE, for the same reason KNOWN_VENUE_GAPS is:
    # a note, not a repair queue. The alternative is a DEGRADED warning per
    # delisted (symbol, tf) that can NEVER be cleared — no action exists, the
    # venue is gone — which is the 108-permanent-warnings shape the
    # STALE_SERIES scoping and the v0.2 note both exist to prevent.
    "RETIRED_SEQUENCE_GAPS":   "SERVE_FLAG",
    "KNOWN_VENUE_GAPS":        "SERVE_FLAG",   # documented, not corruption
    # AGGREGATION
    "AGGREGATE_PENDING":       "SERVE_FLAG",   # scheduling lag
    "MISSING_AGGREGATE":       "HALT",
    "AGGREGATE_MISMATCH":      "HALT",
    "ORPHAN_AGGREGATE":        "HALT",
    "NO_COMPLETE_BUCKETS":     "SERVE_FLAG",
    # FACTS
    "CAUSALITY_VIOLATION":     "HALT",
    "UNATTRIBUTED_CURRENT_FACTS": "HALT",
    # SETUP
    "INVALID_BRACKET":         "AUTO_DISABLE",
    "INCOMPLETE_LINEAGE":      "SERVE_FLAG",
    # RISK
    "ORPHAN_RISK_DECISION":    "HALT",
    "REJECTED_WITH_EXPOSURE":  "HALT",
    "SIZED_DECISION_INCOMPLETE": "HALT",
    # EXECUTION
    "ORPHAN_ORDER":            "HALT",
    "ORDER_BEFORE_AVAILABLE":  "HALT",
    "EXIT_WITHOUT_ORDER":      "HALT",
    "EXIT_BEFORE_FILL":        "HALT",
    # ACCOUNTING
    "ACCOUNT_SUMMARY_MISSING": "HALT",
    "EQUITY_RECONCILIATION_FAILED": "HALT",
    # REFERENCE SERIES (symbols carrying an '@' — venues.is_reference_key).
    # Every finding on one is demoted at the end of audit_market_inputs to a
    # REFERENCE_-prefixed code at QUARANTINE, DEGRADED — never BLOCKED, never
    # HALT — because a reference feed gates no trade and sizes no order, so a
    # blocking verdict from one could only do two kinds of damage: wedge the
    # store-wide evaluation gate over data nothing trades on, or hand the
    # watchdog a restart the scanner cannot heal (the 2026-08-08 loop). The
    # finding itself survives, visibly, under its own name.
    "REFERENCE_NO_CANDLES":             "QUARANTINE",
    "REFERENCE_STALE_SERIES":           "QUARANTINE",
    "REFERENCE_UNKNOWN_TIMEFRAME":      "QUARANTINE",
    "REFERENCE_OHLC_INVARIANT_FAILURE": "QUARANTINE",
    "REFERENCE_SEQUENCE_GAPS":          "QUARANTINE",
    "REFERENCE_DEVELOPING_CANDLES":     "QUARANTINE",
    "REFERENCE_MISSING_AGGREGATE":      "QUARANTINE",
    "REFERENCE_AGGREGATE_MISMATCH":     "QUARANTINE",
    "REFERENCE_ORPHAN_AGGREGATE":       "QUARANTINE",
    # ...and the fact-level codes a per-symbol audit of an '@'-key can demote
    # (facts on a reference key are themselves a bug — see the demotion pass
    # in audit()). Any REFERENCE_ code not declared here falls to _rung_for's
    # DEGRADED default, SERVE_FLAG, which is also non-blocking by design.
    "REFERENCE_CAUSALITY_VIOLATION":    "QUARANTINE",
}


def _rung_for(status: str, code: str) -> str:
    if code in CODE_RUNG:
        return CODE_RUNG[code]
    return "HALT" if status == "BLOCKED" else "SERVE_FLAG"


def _current_versions():
    """Active engine chain. Generation-specific checks (SETUP/RISK/EXECUTION)
    evaluate ONLY the active chain: per docs/HARDENING.md, older generations
    are retained as historical artifacts and are not comparable — auditing
    them as if they were the live pipeline permanently blocks evaluation on
    facts that the active chain never produced. Lazy import avoids cycles."""
    from . import setups, scalein, execsim, risk
    return {"setup": (setups.SETUP_VERSION, scalein.SCALE_VERSION),
            "risk": (risk.RISK_VERSION,),
            "exec": (execsim.EXEC_VERSION,),
            "order": (execsim.EXEC_VERSION,)}


def _known_gap_buckets(con, sym: str, tf: str) -> tuple[set[int], int]:
    """Gaps the importer acknowledged at import time (gap-honesty rule: gaps are
    logged, never fabricated). Coinbase legitimately omits a bucket when zero
    trades occurred in it — an acknowledged void is data, not corruption.

    Returns (explicitly listed timestamps, acknowledged count after duplicate
    retry chains are collapsed). The list is truncated at import (gaps[:200])
    while n_gaps is exact, so a thin listing like EUL-USD 15m with 830 real
    voids must be judged on the COUNT — otherwise truncation alone re-wedges
    the fail-closed gate (regression seen 2026-07-26).
    """
    listed: set[int] = set()
    # A quiet tail is retried every cycle from the same last stored candle.
    # Summing every import_log row counted the same missing buckets again and
    # again: LSETH-USD accumulated 17, then 18, then 19... for one expanding
    # empty window.  That inflated anonymous budget could excuse a genuinely
    # unexplained hole later. One range_start is one retry chain: retain its
    # largest count, while preserving every explicitly listed timestamp.
    # A new stored candle advances range_start, so genuinely disjoint import
    # spans still add normally.
    retry_chains: dict[int, int] = {}
    # range_start >= PRE_2000: the quarantined cold-start rows (importer.py)
    # hold ~2M fabricated gap entries each. This reader ingested their counts
    # into its budget until 2026-08-09 — harmless only because those symbols'
    # real voids dwarfed nothing, but a budget built on fabricated numbers is
    # the exact defect the quarantine exists to contain.
    for start, g, n in con.execute(
            "SELECT range_start, gaps, n_gaps FROM import_log "
            "WHERE symbol=? AND tf=? "
            "AND range_start>=?", (sym, tf, importer.PRE_2000)):
        # A later response can finally contain a candle and report zero gaps
        # for its shortened tail, but earlier recorded empty buckets remain
        # real. Selecting only the final row erased 202 legitimate LSETH-USD
        # acknowledgements on the first live verification of this fix.
        try:
            listed.update(int(t) for t in json.loads(g))
        except Exception:
            pass
        key = int(start)
        retry_chains[key] = max(retry_chains.get(key, 0), int(n or 0))
    return listed, sum(retry_chains.values())


# These are operator/system events, not deterministic engine outputs.  They
# may be written outside RunRecorder by design and therefore have no producer
# run to attach.  Calling them unattributed made a current alert look like a
# broken engine fact and made the warning impossible to clear.
LINEAGE_OPTIONAL_KINDS = frozenset({
    "alert", "manual_intent", "manual_exec", "manual_override", "retention",
})


class DataQualityError(RuntimeError):
    pass


def _live_symbols(con) -> set:
    """Symbols currently in the scan universe.

    Computed once per audit and passed down — deliberately NOT cached in a
    module global. A cache keyed on nothing is shared across CONNECTIONS, so an
    audit of one database would suppress warnings in another.
    """
    try:
        from . import universe
        return set(universe.current_symbols(con))
    except Exception:
        # Fail OPEN: if we cannot tell what is live, report staleness rather
        # than silently suppressing a real one. Minus reference keys — they
        # are never universe members, and letting the fallback include them
        # would route their staleness through the tradeable-symbol check
        # instead of the REFERENCE_STALE_SERIES branch that owns it.
        return {r[0] for r in con.execute(
            "SELECT DISTINCT symbol FROM candles").fetchall()
            if not venues.is_reference_key(r[0])}


def _symbols_that_must_keep_blocking(con) -> set:
    """Symbols where an unexplained gap can still invent a fill.

    The harm is stated in live.py's own comment: resolving an exit across an
    unexplained candle gap "would invent which level hit first". A delisting
    makes that WORSE, not better, because the missing bars are never coming, so
    the invented fill is permanent and enters the graded book that decides
    whether live routing unlocks.

    Four populations walk candles to settle a trade:

      · an unresolved SIMULATOR order — live.py's pinned-exit path, and the
        one this gate actually protects: `assert_market_ready` runs at
        pipeline.py before execsim, and stops on BLOCKED;
      · a durable PAPER intent — execution.monitor_paper walks candles from
        `intent.created_at` to fill, stop or target;
      · an unresolved MANUAL intent — manual.run settles the operator's own
        hand-armed trades by walking candles, on the same roster;
      · anything still in the SCAN SET. `pinned` is computed once before the
        audit loop, but pipeline runs setups and execsim immediately after
        assert_market_ready passes, so a demoted symbol still being scanned
        acquires a NEW order in the same pass — no order existed when we
        looked. A delisted symbol normally leaves the scan set at the next
        refresh, but `universe.refresh` keeps the previous members INDEFINITELY
        when Coinbase rank coverage is low, while the /products call feeding
        the listing sweep still succeeds. That window is not an hour.

    BE HONEST ABOUT THE REACH: `assert_market_ready` gates only the pipeline
    (pipeline.py), the pinned-exit path (live.py) and backfill.py. It is NOT in
    front of `manual.run` or `execution.monitor_paper` — live.py calls both
    directly — so listing those two buys no protection TODAY. They are here
    because completeness is this guard's whole value: the cost is one indexed
    query each, and the alternative is that whoever puts a gate in front of
    either inherits an enumeration that silently already missed them. An
    earlier draft of this docstring claimed the gate covered manual.run; it
    never did.

    Fails CLOSED — on any error every symbol is treated as unsafe to demote,
    so the demotion cannot fire on a store we could not read.
    """
    out: set = set()
    try:
        from . import execsim, manual, universe
        out |= {symbol for symbol, _tf in execsim.unresolved(con)}
        out |= {str(key[0]) if isinstance(key, tuple) else str(key)
                for key in manual.unresolved(con)}
        # Durable PAPER intents, straight off the outbox. monitor_paper reads
        # exactly these two states and walks candles from intent.created_at, so
        # the states are the roster — reading it here rather than through
        # execution keeps this a single indexed query with no plan decoding.
        #
        # The table is created by execution._ensure on the first enqueue, so a
        # store where nothing has ever been armed does not have it. That is an
        # EMPTY population, not an unreadable one, and the difference matters:
        # letting the missing table raise would reach the fail-closed handler
        # below and pin every symbol on exactly the cold stores the demotion is
        # supposed to work on. Absent table -> no paper intents exist.
        if con.execute("SELECT count(*) FROM sqlite_master WHERE type='table' "
                       "AND name='execution_outbox'").fetchone()[0]:
            out |= {r[0] for r in con.execute(
                "SELECT DISTINCT symbol FROM execution_outbox WHERE mode='PAPER' "
                "AND state IN ('PAPER_ROUTED','PAPER_FILLED')").fetchall()}
        out |= set(universe.scan_symbols(con))
    except Exception as exc:
        # Loud-fallback rule: the safe direction is still a degraded one, and
        # a silent one looks exactly like "nothing is at risk".
        from .runlog import get_logger
        get_logger().warning(
            f"quality: cannot read the open-order/scan set "
            f"({type(exc).__name__}: {exc}) — no market will be treated as "
            f"retired this audit; every gap keeps blocking")
        return _ALL_SYMBOLS
    return out


class _AllSymbols(frozenset):
    """Contains everything — the fail-closed answer when the store could not
    be read.

    Honest about it under every operation, not just `in`. As a bare frozenset
    subclass it would report len 0 and falsey while containing everything, so
    the next person to log `len(pinned)` prints "0 symbols pinned" at the exact
    moment every symbol is.
    """

    def __contains__(self, item) -> bool:
        return True

    def __len__(self) -> int:
        raise TypeError("_AllSymbols is unbounded — test membership, not size")

    def __iter__(self):
        raise TypeError("_AllSymbols is unbounded — test membership, not iteration")

    def __bool__(self) -> bool:
        return True

    def __repr__(self) -> str:
        return "<every symbol (fail-closed)>"


_ALL_SYMBOLS = _AllSymbols()


def _issue(checks, stage, status, code, details, symbol=None, tf=None):
    checks.append({"stage": stage, "status": status, "code": code,
                   "rung": _rung_for(status, code),
                   "symbol": symbol, "tf": tf, "details": details})


def _stage_status(checks, stage):
    relevant = [c["status"] for c in checks if c["stage"] == stage]
    return max(relevant, key=ORDER.get) if relevant else "PASS"


def _stage_rung(checks, stage):
    relevant = [c["rung"] for c in checks if c["stage"] == stage]
    return max(relevant, key=RUNG_ORD.get) if relevant else "SERVE"


# Keyed BY DATABASE PATH. It was a single global, and the background refresh
# below called store.connect() with no argument — so a caller passing any other
# store got back a verdict audited from the DEFAULT one. With a single
# production database that is invisible; it is still a violation of the rule
# this module exists to enforce, because an audit belongs to the store it
# audited and to no other.
#
# Found 2026-07-30 by a test that could not fail on its own: risk.py's
# data-health gate read a cached BLOCKED verdict belonging to a different
# database, rejected every intent as DATA_HEALTH_BLOCKED, and the drawdown halt
# it was testing therefore never fired. Silent, order-dependent, and it would
# have behaved the same way against any second store — a replay copy, a
# scratch DB, an A/B run.
_AUDIT_CACHE: dict = {}
AUDIT_TTL = 300


def _db_key(con) -> str:
    """Identify the store behind a connection, so a verdict cannot cross stores."""
    try:
        for _, name, path in con.execute("PRAGMA database_list").fetchall():
            if name == "main":
                return path or ":memory:"
    except Exception:
        pass
    return f"unknown-{id(con)}"


def _slot(key: str) -> dict:
    return _AUDIT_CACHE.setdefault(
        key, {"at": 0.0, "report": None, "refreshing": False})


def _default_db_key() -> str:
    """Path of the production store, resolved the same way store.connect does."""
    try:
        from . import store
        return str(store.DB_PATH)
    except Exception:
        return "unresolvable-default"


def last_persisted(con):
    """The most recent audit THE SCANNER RECORDED, or None before the first.

    ONE VERDICT, AND IT IS THIS ONE. `cached_audit` keeps its report in module
    state, so the api-server and the scanner each hold their own — two
    processes, two caches, no reason for them to agree. `risk.py` runs inside
    the scanner and gates trading on that process's verdict; the UI read the
    api-server's, which audits at whatever moment a request happens to arrive.

    Measured 4 Aug 2026: the server audited at 11:44:58 and caught 23 symbols
    whose 15m bar closed at 11:45 — legitimately open, flagged DEVELOPING_
    CANDLES, which is a HALT-rung code, so it published BLOCKED. The scanner
    audited the same store at 11:45:06, eight seconds later, and recorded
    DEGRADED with trading allowed. Because `cached_audit` serves its last
    report until a background refresh replaces it, the server was still
    serving that BLOCKED snapshot four minutes later, under a chip reading
    "the engine is refusing to size new entries". It was not.

    A read-only surface must never publish a verdict the engine never acted
    on. This returns the recorded one, with its age, so a scanner that has
    stopped is visible as staleness rather than hidden behind a fresh-looking
    audit nobody used.
    """
    row = con.execute(
        "SELECT observed_at, report FROM quality_runs "
        "WHERE report IS NOT NULL ORDER BY observed_at DESC LIMIT 1").fetchone()
    if row is None:
        return None
    try:
        report = json.loads(row[1])
    except (ValueError, TypeError):
        return None
    report["observed_at"] = row[0]
    report["age_s"] = max(0, int(time.time()) - row[0])
    report["source"] = "scanner"
    return report


def cached_audit(con, force: bool = False):
    """The one verdict every surface reads, for THIS store.

    A full audit was measured at 72s cold while contending with the scanner's
    writes. Any HTTP handler that calls audit() directly therefore hangs its
    caller — which is exactly how the redesigned shell's health chip and the
    ApexShell pane came to disagree and stall. Serve the last known report and
    refresh off the request path; `force` runs a local, non-authoritative audit
    synchronously for diagnostic callers.
    Returns None only before the very first audit completes — callers must
    render that as "pending", never as a confident zero.
    """
    import threading
    key = _db_key(con)
    slot = _slot(key)
    if force:
        # A cache refresh is not scanner authority. Persisting here allowed an
        # API-process diagnostic to become the newest durable report and then
        # be mislabeled as the verdict the scanner acted on.
        slot["report"] = audit(con)
        slot["at"] = time.time()
        return slot["report"]

    stale = (slot["report"] is None or time.time() - slot["at"] > AUDIT_TTL)
    # The background refresh exists for ONE reason: keeping the production
    # request path off a 72s audit. It is therefore only ever run against the
    # default store. Backgrounding a thread into whatever database a caller
    # happened to pass is how this function came to hold a temporary store open
    # past its owner's lifetime — and, before the cache was keyed, how it came
    # to answer questions about one database using another's verdict.
    # Any other store gets the honest answer: None, meaning "pending". A caller
    # that needs a real verdict for it uses force=True or audit() directly.
    if stale and not slot["refreshing"] and key == _default_db_key():
        slot["refreshing"] = True

        def _bg(target=slot):
            from . import store
            try:
                c = store.connect()
                try:
                    target["report"] = audit(c)
                    target["at"] = time.time()
                finally:
                    c.close()
            except Exception:
                pass
            finally:
                target["refreshing"] = False

        threading.Thread(target=_bg, daemon=True).start()
    return slot["report"]


def audit_market_inputs(con, symbol: str | None = None, now: int | None = None):
    now = int(time.time()) if now is None else now
    checks = []
    args = []
    where = ""
    if symbol:
        where = " WHERE symbol=?"
        args.append(symbol)
    series = con.execute(
        "SELECT DISTINCT symbol,tf FROM candles" + where + " ORDER BY symbol,tf",
        args).fetchall()
    if not series:
        _issue(checks, "DATA", "BLOCKED", "NO_CANDLES",
               "no market candles are available", symbol)
    live = _live_symbols(con)

    # LAZY, and memoised for this audit. `_symbols_that_must_keep_blocking` is
    # dominated by `execsim.unresolved`, whose ROW_NUMBER window plus a join on
    # an unindexed setup_id scales superlinearly with the CURRENT generation's
    # order facts: measured 14 ms at 500 orders, 456 ms at 3,000, 1,726 ms at
    # 6,000. `assert_market_ready` runs once per scan symbol, so computing it
    # eagerly added that cost ~75x per cycle — 34s at 3,000 orders, over two
    # minutes at 6,000 — and threw the answer away on every healthy symbol.
    #
    # That directly attacks the fixed-clock-snapshot rule: a cycle that takes
    # minutes longer widens the gap between the snapshot import used and the
    # clock the later engines judge against. Before this guard existed the cost
    # was zero, so it had to go back to about zero.
    #
    # The set is identical for every symbol in a cycle, so one call per audit
    # is enough — and the delisting check below is ordered cheap-first, so on a
    # store with no positively-delisted gapped market it is never called at
    # all. A list holds the memo rather than the set itself: `_ALL_SYMBOLS`
    # refuses len() by design, and an `if not cached` on it would be a trap.
    _unsafe_memo: list = []

    def unsafe_to_retire():
        if not _unsafe_memo:
            _unsafe_memo.append(_symbols_that_must_keep_blocking(con))
        return _unsafe_memo[0]

    for sym, tf in series:
        sec = importer.TF_SECONDS.get(tf)
        if not sec:
            _issue(checks, "DATA", "BLOCKED", "UNKNOWN_TIMEFRAME", tf, sym, tf)
            continue
        rows = con.execute(
            "SELECT open_ts,open,high,low,close,volume,source FROM candles "
            "WHERE symbol=? AND tf=? ORDER BY open_ts", (sym, tf)).fetchall()
        bad = 0
        for ts, op, hi, lo, cl, vol, _ in rows:
            op, hi, lo, cl, vol = map(Decimal, (op, hi, lo, cl, vol))
            aligned = (aggregator._bucket_start(ts, "1W") == ts
                       if tf == "1W" else ts % sec == 0)
            bad += not (aligned and hi >= max(op, cl) and
                        lo <= min(op, cl) and lo > 0 and vol >= 0)
        if bad:
            _issue(checks, "DATA", "BLOCKED", "OHLC_INVARIANT_FAILURE",
                   f"{bad} malformed or misaligned candles", sym, tf)
        missing: list[int] = []
        for i in range(1, len(rows)):
            t = rows[i - 1][0] + sec
            while t < rows[i][0] and len(missing) <= 5000:
                missing.append(t)
                t += sec
        if missing:
            if tf in importer.NATIVE_TFS:
                listed, acknowledged = _known_gap_buckets(con, sym, tf)
                remaining = [t for t in missing if t not in listed]
                # voids the importer counted but could not list (truncation)
                budget = max(0, acknowledged - len([t for t in missing if t in listed]))
                unexplained = remaining[budget:]
            else:
                # Aggregate TFs: a missing bucket is BY DESIGN when its source
                # bucket was incomplete (never fabricate). Genuine aggregation
                # failures are caught independently by MISSING_AGGREGATE below.
                unexplained = []
            if unexplained:
                # A market its VENUE no longer lists has RETIRED history, not
                # broken history. The hole is unrepairable BY CONSTRUCTION, so
                # a blocker on it never clears and the operator has no action
                # to take — CRVUSDT halted the store on every cycle this way.
                # Same cry-wolf failure the STALE_SERIES scoping below already
                # fixed for its own check; gaps were the DATA blocker it was
                # never applied to.
                #
                # THE EVIDENCE IS THE VENUE'S PRODUCT LIST, not universe
                # membership. `members` is the top_n slice of the ranking
                # (default 20) while Phemex listed 101 perps, so keying on it
                # demoted 81 live markets — reverted as ba9d8fb, and the reason
                # this reads `listings` instead. `listed_on_venue` answers None
                # for every doubt (never swept, sweep failed, record stale,
                # venue unknown) and only False on positive evidence that the
                # venue answered without naming the symbol; None keeps the
                # blocker, so an outage cannot retire a book.
                #
                # LISTED, not tradeable-right-now: the sweep reads each
                # venue's product naming, so a maintenance halt or a
                # cancel-only wind-down still reads as listed. Calling a
                # reversible halt a delisting would tell the operator a live
                # market's repairable holes are unrepairable.
                #
                # Two deliberate narrowings on top of that:
                #  · Anything that could still resolve a trade across the hole
                #    keeps BLOCKING — an open simulator order, an unresolved
                #    manual intent, or simply still being in the scan set,
                #    since the pipeline creates a new order moments after this
                #    gate passes. See _symbols_that_must_keep_blocking.
                #  · Only gaps demote. Malformed rows and developing candles
                #    indict the STORE, which is live and repairable whatever
                #    the venue did, so they keep blocking.
                retired = (listings.listed_on_venue(con, sym, now) is False
                           and sym not in unsafe_to_retire())
                if retired:
                    # Loud-fallback rule. This is the only path in v0.3 that
                    # LIFTS a blocker, and it was the only one that said
                    # nothing: the store could go evaluation_allowed False ->
                    # True between two cycles with no line in data/live.log
                    # explaining why, leaving "why did it start sizing again"
                    # answerable only by opening Diagnostics.
                    from .runlog import get_logger
                    get_logger().warning(
                        f"quality: {sym} {tf} has {len(unexplained)} unexplained "
                        f"candle gaps, but {venues.venue_for(sym).key} no longer "
                        f"lists it — recorded RETIRED_SEQUENCE_GAPS and NOT "
                        f"blocking; its history is retired, not broken")
                    # PASS puts this in `notes` rather than `warnings`:
                    # recorded under its own name and count (rejections stay as
                    # auditable as approvals), but not a standing alarm nobody
                    # can answer. The market is gone; its data feeds nothing.
                    _issue(checks, "DATA", "PASS", "RETIRED_SEQUENCE_GAPS",
                           f"{len(unexplained)} unexplained discontinuities in a "
                           f"market the venue no longer lists — retired history, "
                           f"unrepairable, not blocking", sym, tf)
                else:
                    _issue(checks, "DATA", "BLOCKED", "SEQUENCE_GAPS",
                           f"{len(unexplained)} unexplained discontinuities in candle sequence",
                           sym, tf)
            if len(missing) > len(unexplained):
                _issue(checks, "DATA", "PASS", "KNOWN_VENUE_GAPS",
                       f"{len(missing) - len(unexplained)} venue-acknowledged empty "
                       f"buckets (accepted evidence note; no repair required)", sym, tf)
        developing = sum(r[0] + sec > now for r in rows)
        if developing:
            _issue(checks, "DATA", "BLOCKED", "DEVELOPING_CANDLES",
                   f"{developing} candles have not closed", sym, tf)
        # Staleness only means something for a symbol we are STILL tracking. A
        # symbol deliberately dropped from the universe has retired data, not
        # stale data, and reporting it forever buries the one series that goes
        # quiet while it matters. Switching to perps retired 108 spot symbols
        # and produced 108 permanent warnings — the same cry-wolf failure as the
        # 1,364 blockers that wedged the scanner for days.
        if rows and sym in live and now - (rows[-1][0] + sec) > 2 * sec:
            _issue(checks, "DATA", "DEGRADED", "STALE_SERIES",
                   f"latest closed candle is {now - (rows[-1][0] + sec)}s old", sym, tf)
        # A reference key is never in `live` (current_symbols excludes it by
        # design), so the check above structurally cannot see one — and a
        # DEAD REFERENCE FEED IS THE FAILURE THIS FEED WILL ACTUALLY HAVE:
        # Binance delists a symbol routinely, every later import serves
        # nothing, backfill returns candles=0 gaps=0 (nothing served is not a
        # gap), and the basis stream quietly ends while grading accumulates a
        # sample that stopped without a word. Loud-fallback rule: the one
        # series whose silence IS the failure mode gets its own staleness
        # check, at the rung reference findings live on.
        elif rows and venues.is_reference_key(sym) \
                and now - (rows[-1][0] + sec) > 2 * sec:
            _issue(checks, "DATA", "DEGRADED", "REFERENCE_STALE_SERIES",
                   f"reference feed's latest closed candle is "
                   f"{now - (rows[-1][0] + sec)}s old — a delisted or dead "
                   f"feed ends the basis stream silently", sym, tf)

    for target, rule in aggregator.RULES.items():
        sources = con.execute(
            "SELECT DISTINCT symbol FROM candles WHERE tf=?" +
            (" AND symbol=?" if symbol else ""),
            (rule["source"], symbol) if symbol else (rule["source"],)).fetchall()
        for (sym,) in sources:
            source_rows = con.execute(
                "SELECT open_ts,open,high,low,close,volume,imported_at "
                "FROM candles "
                "WHERE symbol=? AND tf=? ORDER BY open_ts", (sym, rule["source"])).fetchall()
            by_bucket = {}
            for row in source_rows:
                by_bucket.setdefault(aggregator._bucket_start(row[0], target), []).append(row)
            actual = {r[0]: r[1:] for r in con.execute(
                "SELECT open_ts,open,high,low,close,volume FROM candles "
                "WHERE symbol=? AND tf=?", (sym, target)).fetchall()}
            src_sec = importer.TF_SECONDS[rule["source"]]
            # Lazy for the same reason the aggregator's copy is: on a liquid
            # symbol no bucket is partial and the set is never built.
            acknowledged: set | None = None
            expected = 0
            for bstart, group in by_bucket.items():
                if bstart + rule["bucket"] > now:
                    continue
                partial = len(group) != rule["n_expected"]
                if partial:
                    # MIRROR OF THE AGGREGATOR'S OWN RULE (agg-v0.2), asked
                    # independently against the same records: a partial bucket
                    # is verifiable iff every source candle occupies a slot
                    # and every missing slot is one the venue acknowledged
                    # serving nothing for. Before v0.2 this loop skipped every
                    # partial group, which was correct while the aggregator
                    # refused to build them and would have been a silent
                    # verification hole the day it stopped refusing — a
                    # partial bar on disk that no check ever reconciled.
                    present = {r[0] for r in group}
                    slots = range(bstart, bstart + rule["bucket"], src_sec)
                    if not present.issubset(slots):
                        # Misaligned source candle beside aligned ones — the
                        # aggregator refuses the bucket for the same reason,
                        # and the candle itself is OHLC_INVARIANT_FAILURE's.
                        continue
                    missing = [t for t in slots if t not in present]
                    if acknowledged is None:
                        acknowledged = importer.acknowledged_gaps(
                            con, sym, rule["source"])
                    if any(t not in acknowledged for t in missing):
                        # Unverifiable absence (never fetched / failed fetch /
                        # pre-listing). The aggregator refuses these too, so
                        # there is no bar to check; if one somehow exists it
                        # reconciles against nothing and stays visible via the
                        # source-tf SEQUENCE_GAPS check instead.
                        continue
                elif any(group[i][0] - group[i - 1][0] != src_sec
                         for i in range(1, len(group))):
                    # A full-count group with uneven spacing means a misaligned
                    # source candle; OHLC_INVARIANT_FAILURE reports it.
                    continue
                expected += 1
                want = (group[0][1], str(max(Decimal(r[2]) for r in group)),
                        str(min(Decimal(r[3]) for r in group)), group[-1][4],
                        str(sum(Decimal(r[5]) for r in group)))
                got = actual.get(bstart)
                if got is None:
                    # A bucket that closed moments ago simply has not been
                    # aggregated yet — that is scheduling lag, not corruption,
                    # and blocking on it wedges the pipeline against itself
                    # (regression 2026-07-26: ONDO/SUI 4H). Only a COMPLETE
                    # bucket that stayed unemitted for more than one further
                    # bucket period is a genuine aggregation failure. A
                    # PARTIAL one never escalates past DEGRADED: ~48 stored
                    # symbols are outside the scan universe, nothing ever
                    # re-aggregates them, and a HALT the scanner cannot heal
                    # is the watchdog's documented anti-pattern — the same
                    # shape as UNKNOWN_TIMEFRAME above.
                    #
                    # AND A BUCKET WHOSE SOURCES JUST ARRIVED IS LAG TOO,
                    # however old its market_time. Onboarding a symbol imports
                    # months of history in one cycle, every historical 4H
                    # window becomes complete instantly, and the bucket-age
                    # test alone read all of them as ancient failures —
                    # 2026-08-10 13:46: OPUSDT joined the universe, 63
                    # MISSING_AGGREGATE HALTs fired mid-onboarding, and the
                    # watchdog shot the scanner seconds before the same
                    # cycle's aggregation pass would have built every one of
                    # them. The import stamp is the honest discriminator: a
                    # bucket can only be MISSING once its sources have sat
                    # unaggregated longer than a scan cycle could plausibly
                    # take (~5-6 min measured; 900s is generous).
                    fresh_sources = now - max(r[6] for r in group) <= 900
                    lagging = fresh_sources or \
                        now - (bstart + rule["bucket"]) <= 2 * rule["bucket"]
                    if partial:
                        _issue(checks, "AGGREGATION", "DEGRADED",
                               "AGGREGATE_PENDING",
                               f"qualifying partial {target} bucket {bstart} "
                               f"({len(group)}/{rule['n_expected']} source candles, "
                               f"absences venue-acknowledged) not emitted",
                               sym, target)
                    else:
                        _issue(checks, "AGGREGATION",
                               "DEGRADED" if lagging else "BLOCKED",
                               "AGGREGATE_PENDING" if lagging else "MISSING_AGGREGATE",
                               (f"complete {target} bucket {bstart} not yet emitted "
                                f"(awaiting next aggregation pass)" if lagging else
                                f"complete {target} bucket {bstart} was not emitted"),
                               sym, target)
                elif tuple(map(str, got)) != tuple(map(str, want)):
                    _issue(checks, "AGGREGATION", "BLOCKED", "AGGREGATE_MISMATCH",
                           f"{target} bucket {bstart} does not reconcile to {rule['source']}", sym, target)
            extras = set(actual) - set(by_bucket)
            if extras:
                _issue(checks, "AGGREGATION", "BLOCKED", "ORPHAN_AGGREGATE",
                       f"{len(extras)} aggregate candles lack source buckets", sym, target)
            if expected == 0 and source_rows:
                _issue(checks, "AGGREGATION", "DEGRADED", "NO_COMPLETE_BUCKETS",
                       f"no complete closed {target} bucket could be verified", sym, target)

    # ── Reference-series demotion, ONE choke point ──
    # Every check above ran at full strength on reference keys — the series
    # get the same OHLC, gap, and aggregation scrutiny as tradeable ones,
    # deliberately. What changes is only what a finding is ALLOWED TO DO:
    # nothing trades on a reference series, so a BLOCKED verdict from one
    # could only wedge the store-wide evaluation gate or hand the watchdog an
    # unhealable restart (2026-08-08). Demoting here, after all issuers,
    # rather than at each _issue site: a future check added to the loops
    # above is then demoted automatically instead of arriving as a new HALT
    # nobody scoped. The REFERENCE_ codes are declared in CODE_RUNG per this
    # module's own rule that no mapping may be implicit.
    for c in checks:
        if c["symbol"] and venues.is_reference_key(str(c["symbol"])) \
                and c["status"] == "BLOCKED":
            c["status"] = "DEGRADED"
            c["code"] = "REFERENCE_" + c["code"]
            c["rung"] = _rung_for("DEGRADED", c["code"])
    return checks


def audit(con, symbol: str | None = None, now: int | None = None, persist=False):
    now = int(time.time()) if now is None else now
    checks = audit_market_inputs(con, symbol, now)
    where, args = (" AND symbol=?", [symbol]) if symbol else ("", [])
    cur = _current_versions()

    def _ver_clause(kind):
        vers = cur[kind]
        return (" AND algo_version IN (" + ",".join("?" * len(vers)) + ")",
                list(vers))

    n = con.execute("SELECT COUNT(*) FROM facts WHERE confirmed_at<market_time" + where,
                    args).fetchone()[0]
    if n:
        _issue(checks, "FACTS", "BLOCKED", "CAUSALITY_VIOLATION",
               f"{n} facts were confirmed before their market time", symbol)
    # Producer lineage is a CURRENT-generation invariant.  The old global
    # count guaranteed a permanent warning because this append-only store
    # deliberately retains pre-lineage generations; resetting a research
    # baseline cannot and should not rewrite them.  It also counted alerts and
    # operator events that are legitimately written outside RunRecorder.
    # Audit only automated facts in the active forward window.  A missing run
    # there is not a historical note: the current evidence cannot be replayed,
    # so fail closed and name the actual defect.
    baseline = con.execute(
        "SELECT started_at FROM research_baselines WHERE active=1 "
        "ORDER BY id DESC LIMIT 1").fetchone()
    if baseline:
        excluded = sorted(LINEAGE_OPTIONAL_KINDS)
        placeholders = ",".join("?" * len(excluded))
        lineage_where = (
            " WHERE producer_run_id IS NULL AND confirmed_at>=? "
            f"AND kind NOT IN ({placeholders})")
        lineage_args: list = [int(baseline[0]), *excluded]
        if symbol:
            lineage_where += " AND symbol=?"
            lineage_args.append(symbol)
        unattributed = con.execute(
            "SELECT COUNT(*) FROM facts" + lineage_where,
            lineage_args).fetchone()[0]
        if unattributed:
            _issue(checks, "FACTS", "BLOCKED", "UNATTRIBUTED_CURRENT_FACTS",
                   f"{unattributed} current automated facts have no producer run",
                   symbol)

    sv_clause, sv_args = _ver_clause("setup")
    setup_rows = con.execute(
        "SELECT symbol,tf,payload FROM facts WHERE kind='setup'" + where + sv_clause,
        args + sv_args).fetchall()
    setup_ids = set()
    for sym, tf, raw in setup_rows:
        p = json.loads(raw)
        if p.get("state") != "VALIDATED":
            continue
        setup_ids.add(p.get("setup_id"))
        try:
            entry, sl, tp = map(Decimal, (p["entry"], p["sl"], p["tp"]))
            long = p.get("direction") == "LONG"
            valid = sl < entry < tp if long else tp < entry < sl
        except Exception:
            valid = False
        if not valid:
            _issue(checks, "SETUP", "BLOCKED", "INVALID_BRACKET",
                   f"{p.get('setup_id')} has an invalid entry/stop/target", sym, tf)
        missing = [k for k in ("why", "manifest_hash", "cost_manifest_hash") if not p.get(k)]
        if missing:
            _issue(checks, "SETUP", "DEGRADED", "INCOMPLETE_LINEAGE",
                   f"{p.get('setup_id')} missing {','.join(missing)}", sym, tf)

    rv_clause, rv_args = _ver_clause("risk")
    risk_rows = con.execute(
        "SELECT symbol,tf,payload FROM facts WHERE kind='risk'" + where + rv_clause,
        args + rv_args).fetchall()
    approved = set()
    for sym, tf, raw in risk_rows:
        p = json.loads(raw)
        if p.get("event") != "DECISION":
            continue
        sid, decision = p.get("setup_id"), p.get("decision")
        if sid not in setup_ids:
            _issue(checks, "RISK", "BLOCKED", "ORPHAN_RISK_DECISION",
                   f"risk decision references unknown setup {sid}", sym, tf)
        if decision == "REJECTED" and Decimal(p.get("risk_usd", "0")) != 0:
            _issue(checks, "RISK", "BLOCKED", "REJECTED_WITH_EXPOSURE",
                   f"rejected setup {sid} has non-zero risk", sym, tf)
        if decision in ("APPROVED", "REDUCED"):
            approved.add(sid)
            if not p.get("units") or not p.get("notional_usd"):
                _issue(checks, "RISK", "BLOCKED", "SIZED_DECISION_INCOMPLETE",
                       f"{sid} is missing units or notional", sym, tf)

    ov_clause, ov_args = _ver_clause("order")
    order_rows = con.execute(
        "SELECT symbol,tf,confirmed_at,payload FROM facts WHERE kind='order'" + where +
        ov_clause + " ORDER BY confirmed_at,id", args + ov_args).fetchall()
    orders = {}
    for sym, tf, confirmed_at, raw in order_rows:
        p = json.loads(raw); sid = p.get("setup_id"); orders[sid] = p
        if sid not in setup_ids:
            _issue(checks, "EXECUTION", "BLOCKED", "ORPHAN_ORDER",
                   f"order references unknown setup {sid}", sym, tf)
        if confirmed_at < int(p.get("available_at", confirmed_at)):
            _issue(checks, "EXECUTION", "BLOCKED", "ORDER_BEFORE_AVAILABLE",
                   f"{sid} order event precedes availability", sym, tf)

    ev_clause, ev_args = _ver_clause("exec")
    exec_rows = con.execute(
        "SELECT symbol,tf,confirmed_at,payload FROM facts WHERE kind='exec'" + where +
        ev_clause, args + ev_args).fetchall()
    for sym, tf, confirmed_at, raw in exec_rows:
        p = json.loads(raw); sid = p.get("setup_id")
        if sid not in orders:
            _issue(checks, "EXECUTION", "BLOCKED", "EXIT_WITHOUT_ORDER",
                   f"execution {sid} has no order lifecycle", sym, tf)
        fill_ts = p.get("fill_ts")
        if fill_ts is not None and confirmed_at < int(fill_ts):
            _issue(checks, "EXECUTION", "BLOCKED", "EXIT_BEFORE_FILL",
                   f"execution {sid} exits before its fill", sym, tf)

    # deliberately unversioned: a summary that fails to reconcile to its own
    # curve is corrupt whatever generation wrote it (internal consistency,
    # not a cross-generation comparison)
    account = con.execute(
        "SELECT payload FROM facts WHERE kind='account' ORDER BY id DESC LIMIT 1").fetchone()
    if risk_rows and account is None:
        _issue(checks, "ACCOUNTING", "BLOCKED", "ACCOUNT_SUMMARY_MISSING",
               "risk decisions exist without an authoritative account summary")
    if account:
        p = json.loads(account[0]); curve = p.get("curve") or []
        expected = Decimal(curve[-1]["equity"]) if curve else Decimal(p["start_equity"])
        if Decimal(p["final_equity"]) != expected:
            _issue(checks, "ACCOUNTING", "BLOCKED", "EQUITY_RECONCILIATION_FAILED",
                   f"summary {p['final_equity']} does not equal ledger {expected}")

    # The same demotion audit_market_inputs applies, repeated over the FULL
    # check list — the fact-level issuers above (CAUSALITY_VIOLATION and
    # friends) run after that function returned, and the invariant is about
    # the report, not one section of it: no finding on a reference key may
    # reach BLOCKED or HALT, because nothing trades on one and a blocking
    # verdict could only wedge evaluation or restart-loop the scanner. Only
    # reachable if descriptive facts are ever written on an '@'-key (e.g.
    # /api/analyse handed one), which is a bug — that bug should surface as
    # QUARANTINE findings, not as a wedge.
    for c in checks:
        if c["symbol"] and venues.is_reference_key(str(c["symbol"])) \
                and c["status"] == "BLOCKED":
            c["status"] = "DEGRADED"
            if not c["code"].startswith("REFERENCE_"):
                c["code"] = "REFERENCE_" + c["code"]
            c["rung"] = _rung_for("DEGRADED", c["code"])

    stages = [{"stage": stage, "status": _stage_status(checks, stage),
               "rung": _stage_rung(checks, stage),
               "checks": [c for c in checks if c["stage"] == stage]}
              for stage in STAGES]
    status = max((s["status"] for s in stages), key=ORDER.get)
    worst_rung = max((s["rung"] for s in stages), key=RUNG_ORD.get)
    rung_counts = {r: 0 for r in RUNGS}
    for c in checks:
        rung_counts[c["rung"]] = rung_counts.get(c["rung"], 0) + 1
    result = {"version": QUALITY_VERSION,
              "observed_at": now, "status": status, "worst_rung": worst_rung,
              "rung_counts": rung_counts,
              "evaluation_allowed": status != "BLOCKED",
              "strategy_rules_changed": False, "stages": stages,
              "blockers": [c for c in checks if c["status"] == "BLOCKED"],
              "warnings": [c for c in checks if c["status"] == "DEGRADED"],
              # A non-clean rung can still be accepted evidence. Keep it in
              # the durable verdict without letting it impersonate work the
              # operator or scanner can repair.
              "notes": [c for c in checks
                        if c["status"] == "PASS" and c["rung"] != "SERVE"]}
    if persist:
        cur = con.execute(
            "INSERT INTO quality_runs"
            "(observed_at,status,evaluation_allowed,summary,report) "
            "VALUES (?,?,?,?,?)", (now, status, int(result["evaluation_allowed"]),
                                  json.dumps({"blockers": len(result["blockers"]),
                                              "warnings": len(result["warnings"]),
                                              "worst_rung": worst_rung,
                                              "rung_counts": rung_counts}),
                                  # THE WHOLE VERDICT. ~40 KB per row, written
                                  # every few minutes by the scanner, so that
                                  # read-only surfaces never have to re-derive
                                  # it — see `last_persisted` for why.
                                  json.dumps(result)))
        run_id = cur.lastrowid
        con.executemany(
            "INSERT INTO quality_checks(quality_run_id,stage,status,code,rung,symbol,tf,details) "
            "VALUES (?,?,?,?,?,?,?,?)",
            [(run_id, c["stage"], c["status"], c["code"], c["rung"],
              c.get("symbol"), c.get("tf"), c["details"]) for c in checks])
        con.commit(); result["quality_run_id"] = run_id
    return result


def assert_market_ready(con, symbol: str, now: int | None = None):
    checks = audit_market_inputs(con, symbol, now)
    blockers = [c for c in checks if c["status"] == "BLOCKED"]
    if blockers:
        codes = ", ".join(sorted({c["code"] for c in blockers}))
        raise DataQualityError(f"{symbol} blocked by market-data quality: {codes}")
    return checks
