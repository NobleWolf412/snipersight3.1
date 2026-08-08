"""Versioned champion/challenger registry with human-only promotion.

Models may rank or propose.  This registry has no import of risk, settings,
broker, setup, or automation mutation functions, so approval cannot silently
rewrite hard gates or enable a live mode.  A promoted model still has to pass
the ordinary playbook and operating-mode gates at decision time.
"""
from __future__ import annotations

import json
import time


LEARNING_VERSION = "learning-v0.1-draft"
STAGES = ("RESEARCH", "SHADOW", "CHAMPION", "RETIRED")


class LearningRejected(ValueError):
    pass


def _ensure(con) -> None:
    con.execute("""CREATE TABLE IF NOT EXISTS model_registry (
        model_id TEXT PRIMARY KEY,
        strategy TEXT NOT NULL,
        horizon TEXT NOT NULL,
        algorithm_version TEXT NOT NULL,
        dataset_version TEXT NOT NULL,
        point_in_time INTEGER NOT NULL,
        stage TEXT NOT NULL,
        created_at INTEGER NOT NULL,
        metadata TEXT NOT NULL)""")
    con.execute("""CREATE TABLE IF NOT EXISTS model_evaluations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        model_id TEXT NOT NULL,
        observed_at INTEGER NOT NULL,
        split_method TEXT NOT NULL,
        report TEXT NOT NULL)""")
    con.execute("""CREATE TABLE IF NOT EXISTS promotion_proposals (
        proposal_id TEXT PRIMARY KEY,
        model_id TEXT NOT NULL,
        target_stage TEXT NOT NULL,
        expected_algorithm_version TEXT NOT NULL,
        status TEXT NOT NULL,
        proposed_at INTEGER NOT NULL,
        decided_at INTEGER,
        decided_by TEXT,
        note TEXT NOT NULL)""")
    con.execute("""CREATE TABLE IF NOT EXISTS learning_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event TEXT NOT NULL,
        occurred_at INTEGER NOT NULL,
        actor TEXT NOT NULL,
        payload TEXT NOT NULL)""")


def register_challenger(con, *, model_id: str, strategy: str, horizon: str,
                        algorithm_version: str, dataset_version: str,
                        point_in_time: bool, metadata: dict | None = None) -> dict:
    if not all((model_id, strategy, horizon, algorithm_version, dataset_version)):
        raise LearningRejected("model, strategy, horizon and version ids are required")
    if not point_in_time:
        raise LearningRejected("training dataset is not certified point-in-time")
    _ensure(con)
    now = int(time.time())
    con.execute(
        "INSERT INTO model_registry(model_id,strategy,horizon,algorithm_version,"
        "dataset_version,point_in_time,stage,created_at,metadata) "
        "VALUES(?,?,?,?,?,?, 'RESEARCH',?,?)",
        (model_id, strategy, horizon, algorithm_version, dataset_version, 1,
         now, json.dumps(metadata or {}, sort_keys=True)))
    con.commit()
    return get(con, model_id)


def get(con, model_id: str) -> dict:
    _ensure(con)
    row = con.execute(
        "SELECT model_id,strategy,horizon,algorithm_version,dataset_version,"
        "point_in_time,stage,created_at,metadata FROM model_registry WHERE model_id=?",
        (model_id,)).fetchone()
    if not row:
        raise LearningRejected("model not found")
    return {"model_id": row[0], "strategy": row[1], "horizon": row[2],
            "algorithm_version": row[3], "dataset_version": row[4],
            "point_in_time": bool(row[5]), "stage": row[6],
            "created_at": row[7], "metadata": json.loads(row[8]),
            "version": LEARNING_VERSION}


def record_walk_forward(con, model_id: str, report: dict, *,
                        split_method: str = "CHRONOLOGICAL_WALK_FORWARD") -> dict:
    model = get(con, model_id)
    if split_method != "CHRONOLOGICAL_WALK_FORWARD":
        raise LearningRejected("only chronological walk-forward evaluation is allowed")
    required = {"windows", "by_regime", "by_horizon", "forward_metrics"}
    missing = sorted(required - set(report))
    if missing:
        raise LearningRejected(f"evaluation is missing {missing}")
    now = int(time.time())
    con.execute(
        "INSERT INTO model_evaluations(model_id,observed_at,split_method,report) "
        "VALUES(?,?,?,?)", (model_id, now, split_method,
                            json.dumps(report, sort_keys=True)))
    con.commit()
    return {"model_id": model["model_id"], "observed_at": now,
            "split_method": split_method, "report": report,
            "version": LEARNING_VERSION}


def propose(con, *, proposal_id: str, model_id: str, target_stage: str,
            expected_algorithm_version: str, note: str = "") -> dict:
    model = get(con, model_id)
    if target_stage not in ("SHADOW", "CHAMPION"):
        raise LearningRejected("a challenger may be proposed only for SHADOW or CHAMPION")
    if model["algorithm_version"] != expected_algorithm_version:
        raise LearningRejected("proposal algorithm version does not match the model")
    if not con.execute("SELECT 1 FROM model_evaluations WHERE model_id=? LIMIT 1",
                       (model_id,)).fetchone():
        raise LearningRejected("walk-forward evidence is required before promotion")
    now = int(time.time())
    con.execute(
        "INSERT INTO promotion_proposals(proposal_id,model_id,target_stage,"
        "expected_algorithm_version,status,proposed_at,note) "
        "VALUES(?,?,?,?, 'PENDING',?,?)",
        (proposal_id, model_id, target_stage, expected_algorithm_version,
         now, note[:500]))
    con.commit()
    return {"proposal_id": proposal_id, "model_id": model_id,
            "target_stage": target_stage, "status": "PENDING",
            "version": LEARNING_VERSION}


def approve(con, proposal_id: str, *, human_approver: str,
            new_algorithm_version: str) -> dict:
    """Promote registry state only; never alter trading or risk configuration."""
    if not human_approver.strip():
        raise LearningRejected("a named human approver is required")
    _ensure(con)
    row = con.execute(
        "SELECT model_id,target_stage,expected_algorithm_version,status "
        "FROM promotion_proposals WHERE proposal_id=?", (proposal_id,)).fetchone()
    if not row or row[3] != "PENDING":
        raise LearningRejected("pending proposal not found")
    if new_algorithm_version != row[2]:
        raise LearningRejected("promotion requires the proposal's new algorithm version")
    model = get(con, row[0])
    now = int(time.time())
    if row[1] == "CHAMPION":
        con.execute(
            "UPDATE model_registry SET stage='RETIRED' WHERE strategy=? AND horizon=? "
            "AND stage='CHAMPION' AND model_id<>?",
            (model["strategy"], model["horizon"], model["model_id"]))
    con.execute("UPDATE model_registry SET stage=? WHERE model_id=?",
                (row[1], model["model_id"]))
    con.execute(
        "UPDATE promotion_proposals SET status='APPROVED',decided_at=?,decided_by=? "
        "WHERE proposal_id=?", (now, human_approver.strip(), proposal_id))
    con.execute(
        "INSERT INTO learning_events(event,occurred_at,actor,payload) VALUES(?,?,?,?)",
        ("PROMOTION_APPROVED", now, human_approver.strip(), json.dumps({
            "proposal_id": proposal_id, "model_id": model["model_id"],
            "target_stage": row[1], "algorithm_version": new_algorithm_version,
            "does_not_enable_live": True}, sort_keys=True)))
    con.commit()
    return {"proposal_id": proposal_id, "model_id": model["model_id"],
            "stage": row[1], "approved_by": human_approver.strip(),
            "does_not_enable_live": True, "version": LEARNING_VERSION}


def registry(con) -> dict:
    models = []
    try:
        model_rows = con.execute(
            "SELECT model_id FROM model_registry ORDER BY created_at,model_id").fetchall()
    except Exception:
        return {"models": [], "proposals": [],
                "policy": "Models rank and propose; humans promote; live gates remain separate.",
                "version": LEARNING_VERSION}
    for (model_id,) in model_rows:
        model = get(con, model_id)
        evaluation = con.execute(
            "SELECT observed_at,split_method,report FROM model_evaluations "
            "WHERE model_id=? ORDER BY id DESC LIMIT 1", (model_id,)).fetchone()
        model["latest_evaluation"] = (None if not evaluation else {
            "observed_at": evaluation[0], "split_method": evaluation[1],
            "report": json.loads(evaluation[2])})
        models.append(model)
    proposals = [{"proposal_id": r[0], "model_id": r[1], "target_stage": r[2],
                  "status": r[3], "proposed_at": r[4], "decided_at": r[5],
                  "decided_by": r[6]}
                 for r in con.execute(
                     "SELECT proposal_id,model_id,target_stage,status,proposed_at,"
                     "decided_at,decided_by FROM promotion_proposals ORDER BY proposed_at")]
    return {"models": models, "proposals": proposals,
            "policy": "Models rank and propose; humans promote; live gates remain separate.",
            "version": LEARNING_VERSION}
