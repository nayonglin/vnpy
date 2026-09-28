from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from datetime import date, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "artifacts/stage010_failure_diagnostics/event_predictions.csv"
SOURCE_SHA = "0534369bd1d0e6c4dc9a20680bdf8c25f31d0d4827e20d0a6092bd5ed7eccc17"
CONTRACT = ROOT / "stages/20260906_0533_stage022_prequential_error_contract.md"
OUTPUT = ROOT / "artifacts/stage022_prequential_error_audit"
TARGETS = ("return_marginal", "drawdown_marginal")


def upper_error(values):
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in values):
        raise ValueError("nonfinite residual")
    n = len(values)
    k = ((n + 1) * 39 + 39) // 40
    return sorted(values)[k - 1] if k <= n else None


def valid_date(value):
    if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
        raise ValueError("invalid date")
    return value


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate(rows):
    if any(not r["event_id"] for r in rows) or len({r["event_id"] for r in rows}) != len(rows):
        raise ValueError("duplicate or empty identity")
    for r in rows:
        day = valid_date(r["decision_date"])
        if r["cutoff"] != day[:7] + "-01":
            raise ValueError("prediction month mismatch")
        if r["label_status"] == "verified":
            if valid_date(r["label_end_date"]) < day or not all(finite(r[t]) for t in TARGETS):
                raise ValueError("invalid closed label")
        elif r["label_status"] == "censored":
            if any(r[t] is not None for t in TARGETS):
                raise ValueError("censored label populated")
        else:
            raise ValueError("invalid label status")
        p = [r["pred_" + t] for t in TARGETS]
        if not isinstance(r["skip"], bool):
            raise ValueError("invalid action type")
        if r["status"] == "predicted":
            if not all(finite(v) for v in p) or r["skip"] != all(v < 0 for v in p):
                raise ValueError("invalid saved prediction or action")
        elif r["status"] == "untrained":
            if any(v is not None for v in p) or r["skip"]:
                raise ValueError("untrained prediction populated")
        else:
            raise ValueError("invalid prediction status")


def audit(rows, cutoffs):
    validate(rows)
    if len(set(cutoffs)) != len(cutoffs):
        raise ValueError("duplicate cutoff")
    months, events = [], []
    for cutoff in sorted(cutoffs):
        if valid_date(cutoff)[8:] != "01":
            raise ValueError("cutoff is not month start")
        past = sorted((r for r in rows if r["status"] == "predicted"
                       and r["label_status"] == "verified" and r["decision_date"] < cutoff
                       and r["label_end_date"] < cutoff), key=lambda r: (r["decision_date"], r["event_id"]))
        margins = {t: upper_error([r[t] - r["pred_" + t] for r in past]) for t in TARGETS}
        ready = all(v is not None for v in margins.values())
        months.append({"cutoff": cutoff, "reference_count": len(past), "ready": ready,
                       "reference_event_ids": [r["event_id"] for r in past], "upper_errors": margins})
        for r in rows:
            if r["cutoff"] != cutoff:
                continue
            bounds = {t: r["pred_" + t] + margins[t] if ready and r["status"] == "predicted" else None
                      for t in TARGETS}
            supported = r["skip"] and all(v is not None and v < 0 for v in bounds.values())
            events.append({"event_id": r["event_id"], "decision_date": r["decision_date"], "cutoff": cutoff,
                           "reference_count": len(past), "upper_bounds": bounds,
                           "point_veto": r["skip"], "supported_veto": supported})
    return {"months": months, "events": events}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def run():
    if OUTPUT.exists():
        raise RuntimeError("diagnostic output already exists")
    body = SOURCE.read_bytes()
    if hashlib.sha256(body).hexdigest() != SOURCE_SHA:
        raise RuntimeError("frozen prediction input changed")
    summary_path = SOURCE.parent / "summary.json"
    old = json.loads(summary_path.read_text())
    identity = old["output_identities"][SOURCE.name]
    if old["status"] != "passed" or identity["sha256"] != SOURCE_SHA or identity["size"] != len(body):
        raise RuntimeError("prediction receipt mismatch")
    inputs = {str(p): sha(p) for p in (SOURCE, summary_path, CONTRACT, Path(__file__),
              ROOT / "tests/test_stage022_prequential_error_audit.py")}
    rows = []
    for raw in csv.DictReader(io.StringIO(body.decode())):
        r = {k: raw[k] for k in ("event_id", "decision_date", "cutoff", "label_end_date", "label_status", "status")}
        if raw["skip"] not in ("True", "False"):
            raise ValueError("invalid serialized action")
        r["skip"] = raw["skip"] == "True"
        for t in TARGETS:
            for key in (t, "pred_" + t):
                r[key] = float(raw[key]) if raw[key] else None
        rows.append(r)
    if len(rows) != 276 or sum(r["label_status"] == "verified" for r in rows) != 274:
        raise ValueError("historical event inventory changed")
    cutoffs = [f"{year}-{month:02d}-01" for year in range(2020, 2027) for month in range(1, 13)
               if (year, month) <= (2026, 8)]
    detail = audit(rows, cutoffs)
    if len(detail["events"]) != len(rows):
        raise ValueError("event omitted from diagnostic")
    by_id = {r["event_id"]: r for r in rows}
    evaluated = [r for r in detail["events"] if by_id[r["event_id"]]["label_status"] == "verified"
                 and all(v is not None for v in r["upper_bounds"].values())]
    breaches = {t: sum(by_id[r["event_id"]][t] > r["upper_bounds"][t] for r in evaluated) for t in TARGETS}
    joint = sum(any(by_id[r["event_id"]][t] > r["upper_bounds"][t] for t in TARGETS) for r in evaluated)
    ready = [m for m in detail["months"] if m["ready"]]
    result = {"status": "completed_diagnostic_only", "created_at": datetime.now().astimezone().isoformat(),
              "evidence_type": "post_failure_prequential_empirical_error_diagnostic",
              "nominal_joint_error_level": 0.05, "formal_coverage_guarantee": False,
              "source_identities": inputs, "event_count": len(rows), "month_count": len(cutoffs),
              "ready_month_count": len(ready), "first_ready_month": ready[0]["cutoff"] if ready else None,
              "point_veto_count": sum(r["point_veto"] for r in detail["events"]),
              "supported_veto_count": sum(r["supported_veto"] for r in detail["events"]),
              "bounded_event_count": sum(all(v is not None for v in r["upper_bounds"].values()) for r in detail["events"]),
              "closed_bounded_event_count": len(evaluated), "breach_counts": breaches, "joint_breach_count": joint,
              "new_labels": 0, "new_historical_fits": 0, "new_model_predictions": 0,
              "new_strategy_replays": 0, "reviewers": 0, "candidate_created": False}
    for path, expected in inputs.items():
        if sha(Path(path)) != expected:
            raise RuntimeError("source changed during diagnostic")
    OUTPUT.mkdir(mode=0o700)
    write_json(OUTPUT / "details.json", detail)
    result["output_identities"] = {"details.json": sha(OUTPUT / "details.json")}
    write_json(OUTPUT / "summary.json", result)
    return result


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True, allow_nan=False))
