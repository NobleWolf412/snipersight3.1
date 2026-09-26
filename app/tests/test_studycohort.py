"""A study version bump archives the old cohort and starts fresh; scratch stores only."""
import json

from engine import execution, forwardtrial, stopstudy, store, zonestudy

START = 1800000


def _stale(con, table, version):
    """Rewrite the stored config as an older cohort."""
    config = json.loads(con.execute(f"SELECT payload FROM {table}").fetchone()[0])
    config["version"] = version
    con.execute(f"UPDATE {table} SET payload=? WHERE id=1", (json.dumps(config),))
    con.commit()


def _scratch(tmp_path):
    con = store.connect(tmp_path/'cohort.db')
    execution._ensure(con)
    con.commit()
    forwardtrial.run(con, set(), now=START)
    stopstudy.run(con, now=START)
    zonestudy.run(con, now=START)
    return con


def test_version_bump_archives_old_cohort_and_starts_fresh(tmp_path):
    con = _scratch(tmp_path)
    for i in range(5):
        con.execute("INSERT INTO forward_trial_events(setup_id,event,observed_at,payload) VALUES (?,?,?,?)",
                    (f"s{i}", "OBSERVED", START, "{}"))
    con.commit()
    _stale(con, "forward_trial", "forward-trial-v0.1-draft")
    _stale(con, "stop_study", "stop-study-v0.1-draft")

    # The stop study runs first on an idle pass. It must wait for the trial,
    # or its watermark (5) would skip the restarted trial's events 1..5.
    stopstudy.run(con, now=START+900)
    assert stopstudy.report(con, now=START+900)["state"] == "PAUSED"
    assert stopstudy.report(con, now=START+900)["previous"] is None

    forwardtrial.run(con, set(), now=START+900)
    stopstudy.run(con, now=START+900)

    trial = forwardtrial.report(con, now=START+900)
    assert trial["state"] == "COLLECTING" and trial["started_at"] == START+900
    assert trial["previous"]["version"] == "forward-trial-v0.1-draft"
    assert trial["previous"]["started_at"] == START
    archived = trial["previous"]["archived_as"]["forward_trial_events"]
    assert con.execute(f"SELECT COUNT(*) FROM {archived}").fetchone()[0] == 5
    assert con.execute("SELECT COUNT(*) FROM forward_trial_events").fetchone()[0] == 0

    study = stopstudy.report(con, now=START+900)
    assert study["state"] == "COLLECTING" and study["previous"]["version"] == "stop-study-v0.1-draft"
    config = json.loads(con.execute("SELECT payload FROM stop_study").fetchone()[0])
    assert config["version"] == stopstudy.STOP_STUDY_VERSION and config["trial_watermark"] == 0
    con.close()


def test_dependency_drift_without_a_bump_still_pauses(tmp_path, monkeypatch):
    con = _scratch(tmp_path)
    monkeypatch.setattr(execution, "EXECUTION_CORE_VERSION", "changed")
    zonestudy.run(con, now=START+900)
    report = zonestudy.report(con, now=START+900)
    assert report["state"] == "PAUSED" and report["previous"] is None
    assert not con.execute("SELECT 1 FROM sqlite_master WHERE name GLOB '*__zone_study_*'").fetchone()
    con.close()


def test_restart_happens_once(tmp_path):
    con = _scratch(tmp_path)
    _stale(con, "zone_study", "zone-study-v0.1-draft")
    zonestudy.run(con, now=START+900)
    zonestudy.run(con, now=START+1800)
    names = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name GLOB '*__zone_study_*'")]
    assert sorted(names) == ["zone_study__zone_study_v0_1_draft", "zone_study_checks__zone_study_v0_1_draft",
                             "zone_study_events__zone_study_v0_1_draft"]
    assert zonestudy.report(con, now=START+1800)["started_at"] == START+900
    con.close()
