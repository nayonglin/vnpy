from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT / "artifacts/stage001_history_qualification"
TRACE_ROOT = ROOT / "artifacts/stage002b_unfilled_trace"
OUTPUT = ROOT / "artifacts/stage003_cancelled_lifecycle"
TARGET_ID = "2bd6f24490dbe1222edb49251312e73b7cdf9425f6b1d03628c32a62ba8a9a76"


def adjudicate(target, trace):
    if target["contract_vt_symbol"] != "CF009.CZCE":
        raise RuntimeError("trace_contract_mismatch")
    date = target["decision_date"]
    endings = [row for row in trace if row["date"] == date and row["method"] == "on_bars" and row["phase"] == "after"]
    if len(endings) != 1:
        raise RuntimeError("terminal_snapshot_missing")
    final = endings[0]
    if final["position"] != 0 or final["target"] != 0 or final["layers"] or final["active_order_ids"]:
        raise RuntimeError("root_not_terminal_flat")
    if len(final["orders"]) != 1:
        raise RuntimeError("root_order_ambiguous")
    order = final["orders"][0]
    direction = "Direction.LONG" if target["direction"] == "long" else "Direction.SHORT"
    if (str(order["datetime"])[:10] != date or order["direction"] != direction or order["offset"] != "Offset.OPEN"
            or order["status"] != "Status.CANCELLED" or float(order["traded"]) != 0 or float(order["volume"]) <= 0):
        raise RuntimeError("order_not_unfilled_cancelled")
    submitted = [row for row in trace if row["date"] == date and row["method"] == "rebalance_portfolio"
                 and row["phase"] == "after" and order["vt_orderid"] in row["active_order_ids"]
                 and row["target"] == float(order["volume"]) * (1 if target["direction"] == "long" else -1)]
    forced = [row for row in trace if row["date"] == date and row["method"] == "_process_forced_margin_deleverage"
              and row["phase"] == "after" and not row["layers"] and row["target"] == 0
              and any(event.get("reason") == "forced_margin_deleverage" and event.get("vt_symbol") == target["contract_vt_symbol"]
                      and float(event.get("volume", 0)) == float(order["volume"]) for event in row["trade_events"])]
    if len(submitted) != 1 or len(forced) != 1:
        raise RuntimeError("order_cancellation_cause_unproven")
    if not trace.index(submitted[0]) < trace.index(forced[0]) < trace.index(final):
        raise RuntimeError("trace_sequence_invalid")
    return {"status": "mature_cancelled_unfilled", "end_date": date, "terminal_order_id": order["vt_orderid"],
            "terminal_reason": "same_bar_forced_margin_deleverage_cancelled_before_fill", "root_trade_id": None,
            "first_fill_date": None}


def main():
    if OUTPUT.exists():
        raise RuntimeError("output_exists")
    source_path = ROOT.parent / "futures_trend_xgboost_formal_signal_marginal_utility_v4/tools/stage005_event_lifecycle_audit.py"
    spec = importlib.util.spec_from_file_location("cancelled_lifecycle_source", source_path)
    source = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(source)
    history_summary = json.loads((HISTORY / "summary.json").read_text())
    trace_summary = json.loads((TRACE_ROOT / "summary.json").read_text())
    trace_path = TRACE_ROOT / "workers/A/execution_trace.json"
    event_path = HISTORY / "event_lifecycles.csv"
    paths = [HISTORY / "summary.json", TRACE_ROOT / "summary.json", trace_path, event_path, source_path,
             Path(__file__).resolve(), ROOT / "tests/test_stage003_cancelled_lifecycle.py"]
    identities = {str(path): source.file_identity(path) for path in paths}
    if (identities[str(trace_path)]["sha256"] != trace_summary["trace_identity"]["sha256"]
            or identities[str(event_path)] != history_summary["output_identities"]["event_lifecycles"]
            or trace_summary["status"] != "passed" or trace_summary["prefix_tables_equal"] != 7):
        raise RuntimeError("source_identity_invalid")
    events = pd.read_csv(event_path, float_precision="round_trip")
    unresolved = events[events.status.str.startswith("unresolved")]
    if len(unresolved) != 1 or unresolved.iloc[0].event_id != TARGET_ID or unresolved.iloc[0].candidate_index != 36:
        raise RuntimeError("unexpected_unresolved_set")
    target = unresolved.iloc[0].to_dict()
    result = adjudicate(target, json.loads(trace_path.read_text()))
    for key in ["terminal_order_id", "terminal_reason"]:
        events[key] = None
    for key, value in result.items():
        events.loc[unresolved.index[0], key] = value
    if events.status.str.startswith("unresolved").any() or len(events) != history_summary["event_count"]:
        raise RuntimeError("event_set_changed")
    for path, identity in identities.items():
        if source.file_identity(Path(path)) != identity:
            raise RuntimeError("source_drift")
    OUTPUT.mkdir(mode=0o700)
    with (OUTPUT / "event_lifecycles.csv").open("x") as stream:
        events.to_csv(stream, index=False, float_format="%.17g")
    summary = {"stage": "stage003_cancelled_lifecycle", "status": "passed", "event_count": len(events),
               "status_counts": events.status.value_counts().to_dict(), "adjudicated_event_id": TARGET_ID,
               "terminal_evidence": result, "source_identities": identities,
               "event_lifecycle_identity": source.file_identity(OUTPUT / "event_lifecycles.csv"),
               "objective_headroom_excluding_cancelled_conservatively": history_summary["objective_headroom"],
               "new_replay_count": 0, "new_label_count": 0, "model_fit_count": 0, "reviewer_started": False,
               "eligible_for_label_preregistration": True,
               "cancelled_label_rule": "compute_accept_minus_skip_to_terminal_date_never_impute_zero"}
    with (OUTPUT / "summary.json").open("x") as stream:
        json.dump(summary, stream, ensure_ascii=False, indent=2)
    print(json.dumps({key: value for key, value in summary.items() if key != "source_identities"}), flush=True)


if __name__ == "__main__":
    main()
