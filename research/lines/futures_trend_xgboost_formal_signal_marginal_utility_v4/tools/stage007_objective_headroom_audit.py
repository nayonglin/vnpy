from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts/stage007_objective_headroom_audit"
DAILY = ROOT / "artifacts/stage004_counterfactual_validation/workers/A/daily.csv"
EVENTS = ROOT / "artifacts/stage005_event_lifecycle_audit/event_lifecycles.csv"
MIN_TRAIN_EVENTS = 60


def objective_headroom(daily, events, min_train_events, initial=150000.0):
    if daily.date.tolist() != sorted(set(daily.date)):
        raise RuntimeError("daily_calendar_invalid")
    equity = np.r_[initial, daily.account_equity.to_numpy(dtype=float)]
    if not np.isfinite(equity).all() or (equity <= 0).any():
        raise RuntimeError("equity_invalid")
    mature = events[events.status.eq("mature") & events.end_date.notna()]
    first = None
    count = 0
    for month in pd.date_range(pd.Timestamp(daily.date.iloc[0]).replace(day=1), daily.date.iloc[-1], freq="MS"):
        cutoff = str(month.date())
        count = int((mature.decision_date.lt(cutoff) & mature.end_date.lt(cutoff)).sum())
        if count >= min_train_events:
            first = cutoff
            break
    drawdown = equity / np.maximum.accumulate(equity) - 1
    prefix_count = int(daily.date.lt(first).sum()) if first else len(daily)
    fixed_drawdown = float(drawdown[:prefix_count + 1].min())
    full_drawdown = float(drawdown.min())
    worst_index = int(np.argmin(drawdown))
    fixed_worst = int(np.argmin(drawdown[:prefix_count + 1]))
    headroom = first is not None and fixed_drawdown > full_drawdown
    return {
        "min_train_events": min_train_events, "first_eligible_training_month": first,
        "mature_count_at_first_month": count, "full_max_drawdown_pct": full_drawdown * 100,
        "full_max_drawdown_date": daily.date.iloc[worst_index - 1] if worst_index else "initial",
        "immutable_prefix_max_drawdown_pct": fixed_drawdown * 100,
        "immutable_prefix_worst_date": daily.date.iloc[fixed_worst - 1] if fixed_worst else "initial",
        "strict_full_drawdown_improvement_possible": bool(headroom),
        "decision": "headroom_exists_not_model_evidence" if headroom else "stop_current_shape_joint_objective_impossible",
    }


def identity(path):
    return {"path": str(path), "size": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    if OUTPUT.exists():
        raise RuntimeError("headroom_audit_already_exists")
    paths = [DAILY, EVENTS, Path(__file__).resolve(), ROOT / "tests/test_stage007_objective_headroom_audit.py",
             ROOT / "stages/20260905_2012_stage006_prefix_equivalence_contract.md",
             ROOT / "artifacts/stage004_counterfactual_validation/workers/A/receipt.json",
             ROOT / "artifacts/stage005_event_lifecycle_audit/summary.json"]
    identities = {str(path): identity(path) for path in paths}
    receipt = json.loads(paths[-2].read_text())
    qualified = json.loads(paths[-1].read_text())
    if identities[str(DAILY)]["sha256"] != receipt["frames"]["daily"]["sha256"]:
        raise RuntimeError("baseline_changed")
    if identities[str(EVENTS)]["sha256"] != qualified["event_lifecycle_file"]["sha256"]:
        raise RuntimeError("lifecycles_changed")
    daily = pd.read_csv(DAILY, usecols=["date", "account_equity"], float_precision="round_trip")
    events = pd.read_csv(EVENTS, usecols=["decision_date", "end_date", "status"])
    result = objective_headroom(daily, events, MIN_TRAIN_EVENTS)
    if any(identity(Path(path)) != value for path, value in identities.items()):
        raise RuntimeError("headroom_input_drift")
    summary = {"stage": "stage007_objective_headroom_audit", "status": "completed", **result,
               "source_identities": identities, "new_replay_count": 0, "new_label_count": 0,
               "model_fit_count": 0, "reviewer_started": False}
    OUTPUT.mkdir(mode=0o700)
    with (OUTPUT / "summary.json").open("x") as stream:
        json.dump(summary, stream, indent=2)
    print(json.dumps({k: v for k, v in summary.items() if k != "source_identities"}), flush=True)


if __name__ == "__main__":
    main()
