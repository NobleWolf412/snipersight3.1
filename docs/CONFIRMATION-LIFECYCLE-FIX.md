# Confirmation and pending-order lifecycle correction

September 17, 2026.

The blocked counter combined old confirmation placeholders, expired risk
rejections and genuine current refusals. The paper account also held an
unfilled ZEC order past its deadline, reserving its only slot and causing
subsequent ETH and UNI slot-limit rejections.

## Rules

- A confirmation remains pending until the last allowed closed candle, unless
  the zone breaks first. The existing three-bar window and candle-shape rules
  are unchanged.
- A confirmed setup that fails bracket, target, reward/risk or cost checks gets
  a terminal rejection with the actual reason and confirmation identity.
- A new plan uses the confirmation candle's close as its planned reference.
  It no longer waits for a subsequent candle to close merely to read its open.
  This changes plan economics and therefore starts a new strategy generation.
  Previously armed plans retain their recorded bracket; execution, not this
  reference price, determines actual fills.
- Unfilled paper orders expire after their entry deadline only when the
  eligible candle history is complete. Eligible fills are resolved first.
  Missing history remains unresolved and cannot manufacture a no-fill or
  compress the maker waiting period. Post-deadline candles cannot create an
  entry.
- Confirmation uses its confirmation deadline; ready plans use their entry
  deadline. Expired records do not count as current blocks. Existing custody
  outranks later new-entry risk decisions and survives generation changes by
  matching the recorded attempt identity.

## Version and deployment consequences

The research cascade is setup 24, execution simulation 29, risk 30, paper
risk 6, scale 23 and cooldown 17. Operational execution is 11 and opportunity
state is 10. Historical facts, order plans, account epochs and settlements
are not rewritten. The supervised monitor resolves existing pending orders
using their saved plans after restart.

Study dependency constants describe new cohorts. Existing study configurations
remain immutable and visibly pause when their saved dependency versions differ.
No old cohort is silently resumed or repriced. The corrected generation must
build its own evidence; old results do not establish the new plans' performance.

Regression checks use scratch stores and incremental candle arrival, including
no-next-candle confirmation, future gaps, premature timeout, post-confirmation
rejections, partial maker windows, missed history, idempotent expiry and
cross-generation custody.
