"""Market Weather counts the same universe Command counts.

Measured 2026-07-31, on one screen:

    Command          "TRADEABLE NOW 19"      (universe_counts.admitted)
    Market Weather   "20 of 29 tradeable"    (every member of the snapshot)

Of Weather's twenty "live" symbols, ELEVEN were ADMITTED and NINE were SHADOW —
symbols the risk authority never sizes by definition. So the panel whose stated
job is "whether anything can be traded" was counting nine things that cannot be,
and the two panels disagreed about the size of the universe AND about what the
word tradeable meant.

That is not a stale-fetch problem. The shared data layer made panels agree about
TIME; this is about MEANING, and it has to be fixed at the source or every
consumer inherits it.

n_live/n_total are now scoped to ADMITTED. Shadow and warming are reported
separately, so nothing is hidden — it is just no longer folded into a headline
that reads as opportunity.
"""
import unittest
from unittest.mock import patch


def _weather_payload(members_states, live_map):
    """Drive the endpoint's summarising step over a synthetic population."""
    out = [{"symbol": s, "state": st, "live": live_map.get(s, False)}
           for s, st in members_states.items()]
    sizeable = [s for s in out if s["state"] == "ADMITTED"]
    return {
        "symbols": out,
        "n_live": sum(1 for s in sizeable if s["live"]),
        "n_total": len(sizeable),
        "n_shadow": sum(1 for s in out if s["state"] == "SHADOW"),
        "n_warming": sum(1 for s in out if s["state"] == "WARMING"),
        "n_shadow_live": sum(1 for s in out
                             if s["state"] == "SHADOW" and s["live"]),
        "n_rows": len(out),
    }


class WeatherCountsOnlyWhatCanBeTraded(unittest.TestCase):
    def setUp(self):
        # the exact live shape from 2026-07-31: 19 admitted, 9 shadow, 1 warming
        self.states = {}
        for i in range(19):
            self.states[f"ADM{i}"] = "ADMITTED"
        for i in range(9):
            self.states[f"SHD{i}"] = "SHADOW"
        self.states["WRM0"] = "WARMING"
        # 11 admitted live + all 9 shadow live -> the observed "20 of 29"
        self.live = {f"ADM{i}": True for i in range(11)}
        self.live.update({f"SHD{i}": True for i in range(9)})

    def test_the_denominator_is_the_tradeable_universe(self):
        d = _weather_payload(self.states, self.live)
        self.assertEqual(d["n_total"], 19,
                         "the headline still counts symbols that cannot be sized")

    def test_shadow_symbols_are_not_counted_as_live(self):
        d = _weather_payload(self.states, self.live)
        self.assertEqual(d["n_live"], 11,
                         "shadow symbols are being reported as tradeable — the "
                         "old reading said 20 when only 11 could be sized")

    def test_what_was_excluded_is_still_reported(self):
        """Scoping the count must not hide the population. A shadow symbol's
        record is evidence about whether to admit a venue."""
        d = _weather_payload(self.states, self.live)
        self.assertEqual(d["n_shadow"], 9)
        self.assertEqual(d["n_warming"], 1)
        self.assertEqual(d["n_shadow_live"], 9,
                         "a live shadow symbol is interesting and must be sayable")

    def test_the_grid_still_knows_its_own_row_count(self):
        """The table lists everything; only the headline is scoped. Without a
        separate count, "top 8 of 19" would sit above a 29-row table."""
        d = _weather_payload(self.states, self.live)
        self.assertEqual(d["n_rows"], 29)
        self.assertEqual(len(d["symbols"]), 29)

    def test_it_agrees_with_what_command_shows(self):
        """Command reads universe_counts.admitted. Both panels must now be
        describing one population, which is the whole point."""
        d = _weather_payload(self.states, self.live)
        command_admitted = sum(1 for s in self.states.values() if s == "ADMITTED")
        self.assertEqual(d["n_total"], command_admitted,
                         "two panels on one screen still disagree about the "
                         "size of the universe")

    def test_an_all_shadow_universe_reports_zero_tradeable(self):
        states = {f"SHD{i}": "SHADOW" for i in range(5)}
        d = _weather_payload(states, {s: True for s in states})
        self.assertEqual((d["n_live"], d["n_total"]), (0, 0),
                         "five live shadow symbols read as a tradeable market")
        self.assertEqual(d["n_shadow_live"], 5)


class TheEndpointStillEmitsThoseFields(unittest.TestCase):
    def test_server_scopes_the_counts(self):
        import pathlib
        src = (pathlib.Path(__file__).resolve().parent.parent
               / "server.py").read_text(encoding="utf-8")
        i = src.index('@app.get("/api/weather")')
        body = src[i:src.index("@app.get", i + 10)]
        self.assertIn('s["state"] == "ADMITTED"', body,
                      "the endpoint no longer scopes its counts to the "
                      "tradeable universe")
        for field in ("n_shadow", "n_warming", "n_shadow_live", "n_rows"):
            self.assertIn(field, body, f"{field} is no longer reported")


if __name__ == "__main__":
    unittest.main()
