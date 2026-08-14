# ADR-001: Isolated Market Workspaces

**Status:** Accepted

**Date:** 2026-08-13
**Decider:** Operator

## Context

SniperSight's current store, symbol resolver, venue capabilities, scanner clock,
risk rules and strategies describe crypto. US equities add exchange sessions,
consolidated-tape data, listings and delistings, corporate actions, short
availability and market-specific risk rules. Treating Stocks as a filter over
the crypto book would make identical-looking screens carry different meanings
and would allow equity symbols to inherit crypto assumptions.

## Decision

The product has one shared shell and separate Crypto and US Stocks workspaces.
The browser remembers the last selected workspace and provides a permanent
switcher. Existing operators default to Crypto; new operators choose a market
on first launch.

The workspaces share visual primitives, encrypted credential storage and loud
failure conventions. They do not share scanners, stores, universes, positions,
performance baselines, setup counts or execution readiness. Background reads
pause for the inactive workspace.

The Stocks foundation has two deliberately separate readiness tracks:

- Alpaca Paper is the eventual paper-execution/account authority.
- Alpaca consolidated SIP is required for current stock market data; IEX-only
  data is not accepted as the full US market.
- Massive is the point-in-time universe and corporate-action authority.
- Provider checks are read-only and live stock routing is absent.
- The stock store schema targets `data/stocks.db`, separate from the crypto
  store, and requires asset identity, session, source and evidence scope.
- A deterministic, bundled training tape exercises session classification,
  stock-native setup/rejection evidence and a local paper replay without keys.
- Training output is always `FIXTURE`, visibly synthetic, grade-ineligible and
  structurally unable to enter a provider or live-order path.

## Options Considered

### Reskin the crypto application

Low initial effort, but it reuses crypto symbol identity, 24/7 clocks, venue
capabilities, risk assumptions and baselines where they are not valid. Rejected.

### Build a separate application

Strong isolation, but duplicates security, diagnostics, navigation and design
infrastructure and creates two products that can drift. Rejected.

### Shared platform with isolated market workspaces

Moderate initial effort. It preserves proven operational infrastructure while
making market-specific authorities explicit. Accepted.

## Consequences

- A stock outage or scan cannot block the crypto scanner.
- Stock figures cannot be silently summed with crypto figures.
- Market-specific strategies receive their own versions and evidence records.
- Cross-market portfolio reporting, if later desired, needs a deliberate
  read-only aggregation contract rather than a UI sum.
- A Stocks workspace can be visible before it can trade, but every unavailable
  capability must say why and must not render a confident zero.
