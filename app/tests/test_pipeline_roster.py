"""The engine roster is one list, and everything `risk.py` consumes is on it.

Three runners walked the pipeline from three hand-maintained lists and the
copies drifted. The drift was invisible because nothing compared them, and it
cost a guardrail: `cooldowns` was in NONE of the three, so `risk.py` read an
empty cooldown list on every pass since S41 and the re-entry lockout never
fired once. Measured 2026-07-30 against the live store: 0 cooldown facts, and
`cooldowns` absent from `engine_runs` while all sixteen other engines were
present.

These tests are the lockfile. They do not check that the engines WORK — every
engine has its own suite for that. They check that an engine which is built,
imported and consumed is actually SCHEDULED, which is the failure mode three
separate modules have now hit (`ranges`, `cooldowns`, and the four indicator
engines).
"""
import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine import pipeline  # noqa: E402


def test_all_runners_share_one_roster():
    """live, ingest and backfill must walk the identical sequence.

    Not "the same set" — the same ORDER. `swings` before `structure` before
    `setups` before `execsim` is a data dependency, and a runner that reorders
    them produces facts derived from inputs that did not exist yet.
    """
    import live
    from engine import ingest
    import backfill

    assert live.ENGINES is pipeline.PER_SYMBOL
    assert ingest.PER_SYMBOL_ENGINES is pipeline.PER_SYMBOL
    assert [m for _, m in backfill.ENGINES] == list(pipeline.PER_SYMBOL)


def test_cooldowns_is_scheduled():
    """The specific regression. `risk.py` imports and consumes cooldowns."""
    from engine import cooldowns
    assert cooldowns in pipeline.PER_SYMBOL, (
        "cooldowns is consumed by risk.py but was in no runner's engine list "
        "for eight sessions — the re-entry lockout never fired once")


def test_every_engine_risk_consumes_is_scheduled():
    """Generalised: if `risk.py` reads an engine's facts, that engine runs.

    A version constant imported by the risk authority is a declaration that
    those facts are expected to exist. If nothing produces them, the gate that
    reads them is unreachable code wearing a guardrail's clothes.
    """
    import ast
    src = Path(__file__).resolve().parents[1] / "engine" / "risk.py"
    tree = ast.parse(src.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "") in ("", "engine"):
            for a in node.names:
                imported.add(a.name)

    scheduled = {m.__name__.rsplit(".", 1)[-1] for m in pipeline.PER_SYMBOL}
    # Modules risk imports that are FACT PRODUCERS (have the engine contract).
    for name in sorted(imported):
        try:
            mod = importlib.import_module(f"engine.{name}")
        except Exception:
            continue
        run = getattr(mod, "run", None)
        if run is None:
            continue
        argnames = run.__code__.co_varnames[:run.__code__.co_argcount]
        if argnames[:4] != ("con", "symbol", "tf", "tf_seconds"):
            continue          # not a per-symbol engine (e.g. risk.run(con))
        assert name in scheduled, (
            f"risk.py consumes engine '{name}' but no runner schedules it — "
            f"its gate can never fire")


def test_names_disambiguate_repeats():
    """`execsim` runs twice; the labels must say which pass."""
    names = pipeline.names()
    assert len(names) == len(pipeline.PER_SYMBOL)
    assert len(set(names)) == len(names), f"duplicate labels in {names}"
    assert "execsim" in names and "execsim2" in names


def test_execsim_runs_after_setups_and_after_scalein():
    """Order is load-bearing: adds opened by scalein still need filling, and
    cooldowns derives from exec facts so it must see the adds."""
    names = pipeline.names()
    assert names.index("setups") < names.index("execsim")
    assert names.index("scalein") < names.index("execsim2")
    assert names.index("execsim2") < names.index("cooldowns"), (
        "cooldowns derives from exec facts and must run after the final "
        "execsim pass, or scale-in exits are invisible to the lockout")
