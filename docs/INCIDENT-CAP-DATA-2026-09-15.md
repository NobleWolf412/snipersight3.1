# CAP-USD history repair — 2026-09-15

## Incident

Paper entry decisions were being rejected with `DATA_HEALTH_BLOCKED`. The
latest scanner report identified CAP-USD 5m sequence gaps as its only hard
blocker. Risk applies this verdict across the account, even though strategy
calculation can continue on other markets. The UI had incorrectly described
the restriction as affecting only the markets with bad data.

## Repair

CAP-USD remained listed on Coinbase. A read-only inspection found 4,683
unacknowledged missing 5m bucket slots in the interval
2026-08-15 20:10 UTC through 2026-09-01 02:20 UTC. The routine forward importer
had not revisited this historical interval.

The existing importer fetched `[1786824600, 1788229500)` from Coinbase into an
isolated CAP-only database. It returned 4,226 valid candles, 457 explicit
venue-acknowledged empty buckets, and zero malformed candles. Checking the
whole copied CAP 5m series afterward found zero unexplained missing buckets.

The verified candle rows and corresponding import acknowledgement were applied
in one transaction. Existing candles were compared before insertion; none were
overwritten. The import retains Coinbase provenance and its actual fetch time.
No artificial candles, other-venue prices, strategy facts, orders or historical
trade results were substituted. The global data-health guard stays enabled.

Local evidence and the application receipt are under
`artifacts/cap-repair-20260915/` (not tracked). An independent read-only audit
returned no blockers and `evaluation_allowed=true`. The supervisor subsequently
reported HALT=0 at 15:34:41 local time. Only the scanner may publish the durable
operator quality verdict; neither diagnostic wrote `quality_runs`.

## UI correction and checks

Quality messages now explain that, when data-health protection is enabled,
new entries are stopped across the account. The named market identifies the
data defect, not the scope of the trading restriction. No strategy or sizing
rule changed, so no algorithm version was moved.

Seven focused quality-copy tests passed, followed by the repository JavaScript,
lint and source-integrity checks. Only the API process was restarted to load
the copy change; the scanner was left running.

The scanner completed pass 46 after the repair and persisted its own verdict:
DEGRADED, evaluation_allowed=true, blockers=[]. The web status endpoint was
checked afterward and no longer reported the CAP entry halt.
