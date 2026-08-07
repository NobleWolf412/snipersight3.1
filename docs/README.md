# docs/ — what each file is and whether it is current

Two of these are load-bearing; the rest are plans, specs and audits kept as
the record of decisions. Nothing in here moves — too many files in `app/` and
in these docs cite each other by path.

## Load-bearing (read these first)

- [PROGRAM-PLAN.md](PROGRAM-PLAN.md) — the program plan, rewritten 2026-07-31
  against code and fact store. §6 is the convention list `CLAUDE.md` points at.
  Supersedes the sequencing in REDESIGN-PLAN.
- [HARDENING.md](HARDENING.md) — the hardening contract from the 2026-07-21
  audit. Current authority on venue/leverage/shorts being a per-symbol
  contract.

## Specs (built or gated, kept as the record)

- [SPEC-confirmed-entry.md](SPEC-confirmed-entry.md) — confirmed entry and the
  explanatory layer. §1.1–1.5 built and measured; §1.6 rejected by its own
  gate.
- [SPEC-persistence-retention.md](SPEC-persistence-retention.md) — retention
  policy, proposed; deliberately no deletion implemented.

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

Related directories that are **not** docs: `war-room/` is written by the app
(`brief` drops dossiers there — see `engine/apexbridge.py`), and
`sources/ss3_v0.1.txt` is the product constitution. `PROGRAM-PLAN.md` §
"historical artefacts" says war-room, personas and sources stay as-is.
