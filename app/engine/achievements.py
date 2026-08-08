"""Discipline-only progression for the Tactical Cockpit.

Progress is derived from authorities that already exist.  It never rewards
profit, leverage, trading frequency, winning streaks, or continuing after a
loss.  Those incentives are unsafe precisely when they feel most game-like.
"""
from __future__ import annotations

from decimal import Decimal

from .contracts import AchievementProgress, to_wire


ACHIEVEMENT_VERSION = "achievements-v0.1-draft"


def _progress(have, need) -> Decimal:
    if not need:
        return Decimal("1")
    return min(Decimal("1"), max(Decimal("0"),
               Decimal(str(have or 0)) / Decimal(str(need))))


def calculate(*, live_gate: dict, automation_status: dict,
              journal_count: int, quality_status: str | None) -> list[dict]:
    """Return safe progression using server-owned evidence and gate state."""
    criteria = {c.get("key"): c for c in live_gate.get("criteria", [])}
    sample = criteria.get("sample", {})
    promotion = automation_status.get("promotion", {})
    quality_ok = str(quality_status or "UNKNOWN").upper() in {"PASS", "DEGRADED"}

    rows = [
        AchievementProgress(
            key="SAFE_DEFAULTS", label="Guardrails locked",
            description="Initial risk is 0.25%, one position, and a 1% UTC daily halt.",
            progress=Decimal("1"), completed=True, completed_at=None,
            version=ACHIEVEMENT_VERSION),
        AchievementProgress(
            key="DATA_DRILL", label="Data integrity drill",
            description="The latest pipeline audit is not blocking decisions.",
            progress=Decimal("1") if quality_ok else Decimal("0"),
            completed=quality_ok, completed_at=None,
            version=ACHIEVEMENT_VERSION),
        AchievementProgress(
            key="FORWARD_RECORD", label="Forward record",
            description="Build 100 current-baseline, fully journalled paper trades.",
            progress=_progress(sample.get("have", journal_count),
                               sample.get("need", 100)),
            completed=bool(sample.get("pass")), completed_at=None,
            version=ACHIEVEMENT_VERSION),
        AchievementProgress(
            key="SHADOW_GATE", label="Shadow operator",
            description="Complete 14 days and 100 intents with no unexplained divergence.",
            progress=Decimal("1") if promotion.get("shadow_ready") else Decimal("0"),
            completed=bool(promotion.get("shadow_ready")), completed_at=None,
            version=ACHIEVEMENT_VERSION),
        AchievementProgress(
            key="TESTNET_GATE", label="Testnet qualified",
            description="Complete the lifecycle, reconciliation, and safety-drill gate.",
            progress=Decimal("1") if promotion.get("testnet_ready") else Decimal("0"),
            completed=bool(promotion.get("testnet_ready")), completed_at=None,
            version=ACHIEVEMENT_VERSION),
    ]
    return [to_wire(row) for row in rows]
