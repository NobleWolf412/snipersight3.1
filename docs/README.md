# docs/ — what each file is and whether it is current

Use [PRODUCTION-ARCHITECTURE.md](PRODUCTION-ARCHITECTURE.md) for source ownership
and [REPOSITORY-AUDIT-2026-09-28.md](REPOSITORY-AUDIT-2026-09-28.md) for cleanup
evidence and retained items. Other plans, specs and audits record decisions.
Nothing in here moves — too many files in `app/` and
in these docs cite each other by path.

**The conventions are not in here.** They live in `CLAUDE.md`, the file that is
always loaded; they were `PROGRAM-PLAN.md` §6 until 2026-08-07, and code
comments citing `§6` mean that list.

## Load-bearing (read this first)

- [HARDENING.md](HARDENING.md) — the hardening contract from the 2026-07-21
  audit, venue section revised 2026-07-31. Current authority on
  venue/leverage/shorts being a per-symbol contract, and it matches
  `venues.py`.
- [AUTONOMY-OPERATIONS.md](AUTONOMY-OPERATIONS.md) — the current operator guide
  to modes, risk, evidence, promotion gates, execution, and manual custody.

## The program plan (a dated snapshot, and it says so)

- [PROGRAM-PLAN.md](PROGRAM-PLAN.md) — the program plan, written 2026-07-31
  against code and fact store; supersedes the sequencing in REDESIGN-PLAN. Its
  statuses and counts are true as of that date and are not re-verified on edit.
  §6 keeps the parallelisation rules — what agents can and cannot do in
  parallel here.

Historical plans and reports below are retained in place for provenance and
link stability. They are not implementation references unless explicitly
requested. Their headers and this index are dated evidence; verify claims
against source before acting on them.

## Specs (built or gated, kept as the record)

- [SPEC-confirmed-entry.md](SPEC-confirmed-entry.md) — confirmed entry and the
  explanatory layer. §1.1–1.5 built and measured; §1.6 rejected by its own
  gate.
- [SPEC-persistence-retention.md](SPEC-persistence-retention.md) — retention
  policy proposal/history; current maintenance is implemented in `app/prune.py`.
- [SPEC-log-retention.md](SPEC-log-retention.md) — `data/engine.log` retention,
  proposal/history; inspect current `runlog.py` and watchdog rotation handling.

## Plans

- [MOBILE-PLAN.md](MOBILE-PLAN.md) — full cockpit on Android over the tailnet.
- [CONSISTENCY-PLAN.md](CONSISTENCY-PLAN.md) — ordered frontend implementation
  plan, every claim carries `file:line`.
- [DESIGN-SYSTEM.md](DESIGN-SYSTEM.md) — the UI design system (colors, type,
  components).

## Historical (superseded or dated — kept, not current)

- [REDESIGN-PLAN.md](REDESIGN-PLAN.md) — **HISTORICAL as of 2026-07-31**;
  built, sequencing superseded by PROGRAM-PLAN.
- [PRODUCT-REVIEW-2026-07-29.md](PRODUCT-REVIEW-2026-07-29.md) — dated review
  and expansion proposal; nothing in it was built as written.
- [AUDIT-setup-id-join-hazards.md](AUDIT-setup-id-join-hazards.md) —
  `setup_id` join-hazard audit after the S37/S40 cascade, corrected
  2026-07-30.
- [SALVAGE-from-snipersight-trading.md](SALVAGE-from-snipersight-trading.md) —
  what to take from the old `snipersight-trading` repo, reviewed 2026-07-30.

## Other

- [alerts.example.json](alerts.example.json) — example alert config.

Related: `sources/ss3_v0.1.txt` is the product constitution. `war-room/` may
appear at the repo root at runtime — the `brief` command drops dossiers there
(see `engine/apexbridge.py`, which recreates the directory on demand).
