"""The per-symbol engine sequence — declared ONCE, imported by every runner.

Three runners walked the same pipeline from three separately-maintained lists:
`live.ENGINES`, `ingest.PER_SYMBOL_ENGINES` and `backfill.ENGINES`. They had
drifted, and the drift was silent because nothing compared them:

  · `cooldowns` was in NONE of them. It was built in S41, tested, documented,
    and consumed by `risk.py` — which read an empty list on every pass, so the
    re-entry lockout has never fired once. Measured 2026-07-30: 0 cooldown
    facts in the store, `cooldowns` absent from `engine_runs` entirely, and 86
    of 1,007 VALIDATED intents (8.5%) would have been blocked. The 53 that
    filled returned -5.19 R. A guardrail that is not in the roster is not a
    guardrail.
  · `ranges, ma, momentum, volatility, volume, breakout` were in `live` only,
    so a symbol onboarded today got full history for the older engines and
    forward-only for these six — two populations in one fact store, with
    nothing marking which was which.

The order is load-bearing and is the reason this is a sequence rather than a
set. Each engine reads the facts the ones before it wrote:

    swings -> structure -> zones/liquidity/regime -> setups -> execsim

`execsim` appears TWICE on purpose: `scalein` adds to positions the first pass
opened, and those adds need filling. `cooldowns` is LAST of the trading
engines because it derives purely from exec facts, so it must see the adds too.

`cycles` is observational (BTC 1D, no consumers) and sits at the end.
"""

from . import (breakout, cooldowns, cycles, execsim, liquidity, ma, manual,
               momentum, ranges, regime, scalein, setups, structure, swings,
               volatility, volume, zones)

# Facts the market DESCRIPTION layer derives. No trading consumer reads the
# indicator engines yet and none may until `factorstats` grades them — they are
# here because an engine that is built, tested and never run emits nothing to
# grade, which is exactly how `ranges.py` and `cooldowns.py` both died.
DESCRIPTIVE = (swings, structure, zones, liquidity, regime, ranges,
               ma, momentum, volatility, volume)

# MEASURED AND NOT ENABLED. `breakout` emits setup facts so its sample keeps
# growing and can be re-graded, but neither `execsim` nor `risk` reads
# BREAKOUT_VERSION, so it trades nothing. Graded 2026-07-30: n=55, -0.076 R,
# CI [-0.545, +0.426], P(>0) 37.4% — indistinguishable from zero. REVERSAL
# cleared this bar; this did not, so it does not ship.
MEASURED_NOT_ENABLED = (breakout,)

# The trading path, in dependency order. See the module docstring for why
# `execsim` is listed twice and why `cooldowns` is last.
TRADING = (setups, execsim, scalein, execsim, cooldowns)

OBSERVATIONAL = (cycles,)

# The OPERATOR's own paper book, and deliberately NOT part of TRADING. It
# resolves trades the operator armed by hand, under `manual-v0.1-draft` — a tag
# no strategy consumer queries, so a discretionary trade cannot reach the record
# `edgestats`/`factorstats` grade. It is in this roster for the reason given
# above for `cooldowns`: an engine that is built, tested and never run resolves
# nothing, and an unresolved intent is a trade the operator placed and can never
# see the outcome of.
OPERATOR = (manual,)

PER_SYMBOL = (DESCRIPTIVE + MEASURED_NOT_ENABLED + TRADING + OPERATOR
              + OBSERVATIONAL)


def names() -> list[str]:
    """Engine names in run order, for logging and for the roster test.

    A module that appears twice (`execsim`) is suffixed on the repeat, so a log
    line can say WHICH pass it is without a hand-written label drifting from the
    module beside it.
    """
    out, seen = [], {}
    for m in PER_SYMBOL:
        n = m.__name__.rsplit(".", 1)[-1]
        seen[n] = seen.get(n, 0) + 1
        out.append(n if seen[n] == 1 else f"{n}{seen[n]}")
    return out
