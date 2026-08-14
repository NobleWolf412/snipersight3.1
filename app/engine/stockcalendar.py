"""US-equity session classification from an explicit calendar authority.

Production must supply an exchange calendar.  The bundled training tape supplies
its own schedule, so this module never guesses a holiday or special close.
"""
from __future__ import annotations

from datetime import datetime


STOCK_CALENDAR_VERSION = "stock-calendar-v0.1-draft"


def _instant(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def classify(at: str, session: dict) -> dict:
    """Classify one instant against one authority-owned exchange session."""
    moment = _instant(at)
    boundaries = {
        key: _instant(session[key])
        for key in ("premarket_open", "regular_open", "regular_close",
                    "after_hours_close")
    }
    if moment < boundaries["premarket_open"] or moment >= boundaries["after_hours_close"]:
        phase, tradable = "CLOSED", False
        next_boundary = boundaries["premarket_open"] if moment < boundaries["premarket_open"] else None
    elif moment < boundaries["regular_open"]:
        phase, tradable, next_boundary = "PREMARKET", True, boundaries["regular_open"]
    elif moment < boundaries["regular_close"]:
        phase, tradable, next_boundary = "REGULAR", True, boundaries["regular_close"]
    else:
        phase, tradable, next_boundary = "AFTER_HOURS", True, boundaries["after_hours_close"]
    return {
        "version": STOCK_CALENDAR_VERSION,
        "phase": phase,
        "tradable": tradable,
        "authority": session.get("authority") or "NOT_REPORTED",
        "next_boundary": next_boundary.isoformat() if next_boundary else None,
    }
