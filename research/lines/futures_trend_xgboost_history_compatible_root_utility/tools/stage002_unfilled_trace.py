from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
V4 = ROOT.parent / "futures_trend_xgboost_formal_signal_marginal_utility_v4"
STAGE = "stage002b_unfilled_trace"
OUTPUT = ROOT / "artifacts" / STAGE
FREEZE = ROOT / "stages" / f"{STAGE}_input_freeze.json"
END = "2020-05-13"
CONTRACT = ROOT / "stages/20260905_2033_stage002_unfilled_trace_contract.md"
REFERENCE = V4 / "artifacts/stage004_counterfactual_validation/workers/A"
HISTORY = ROOT / "artifacts/stage001_history_qualification"
SYMBOL = "CF009.CZCE"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def trace_snapshot(strategy, method, phase):
    engine = strategy.strategy_engine
    date = str(engine.datetime)[:10]
    if not "2020-05-11" <= date <= END:
        return None
    state = strategy.states.get("CF.CZCE")
    orders = []
    for order in getattr(engine, "limit_orders", {}).values():
        if order.vt_symbol != SYMBOL:
            continue
        orders.append({key: str(getattr(order, key, "")) for key in
            ("vt_orderid", "datetime", "direction", "offset", "price", "volume", "traded", "status")})
    return {"date": date, "method": method, "phase": phase,
            "target": strategy.target_data.get(SYMBOL, 0), "position": strategy.pos_data.get(SYMBOL, 0),
            "state_contract": getattr(state, "contract_vt_symbol", None),
            "state_direction": getattr(state, "direction", None),
            "layers": [{key: str(getattr(layer, key, "")) for key in ("direction", "volume", "entry_price", "stop_price")}
                       for layer in getattr(state, "layers", [])],
            "orders": orders,
            "active_order_ids": [str(key) for key, order in getattr(engine, "active_limit_orders", {}).items()
                                 if order.vt_symbol == SYMBOL],
            "trade_events": [{key: str(value) for key, value in row.items()}
                             for row in getattr(strategy, "trade_event_diagnostics", [])
                             if str(row.get("vt_symbol", row.get("contract_vt_symbol", ""))) == SYMBOL
                             and str(row.get("datetime", ""))[:10] == date]}


def install_trace(strategy_class, rows):
    methods = ("on_bars", "rebalance_portfolio", "_apply_state_target", "_close_all_layers_and_set_flat_target",
               "_process_forced_margin_deleverage", "_reconcile_state_with_position")
    originals = {}
    local = {}
    for name in methods:
        if not hasattr(strategy_class, name):
            continue
        originals[name] = getattr(strategy_class, name)
        local[name] = strategy_class.__dict__.get(name)
        def wrapper(self, *args, _name=name, _original=originals[name], **kwargs):
            before = trace_snapshot(self, _name, "before")
            if before is not None:
                rows.append(before)
            result = _original(self, *args, **kwargs)
            after = trace_snapshot(self, _name, "after")
            if after is not None:
                rows.append(after)
            return result
        setattr(strategy_class, name, wrapper)
    def restore():
        for name in originals:
            if local[name] is None:
                delattr(strategy_class, name)
            else:
                setattr(strategy_class, name, local[name])
    return restore


def collect_inputs():
    base = load("trace_input_base", V4 / "tools/stage004_counterfactual_validation.py")
    files = base.collect_inputs()
    files.update({"history_trace_runner": Path(__file__).resolve(), "history_trace_contract": CONTRACT,
                  "history_trace_tests": ROOT / "tests/test_stage002_unfilled_trace.py",
                  "history_features_runner": ROOT / "tools/stage001_history_qualification.py",
                  "history_features_tests": ROOT / "tests/test_stage001_history_qualification.py",
                  "history_line": ROOT / "LINE.md", "history_summary": HISTORY / "summary.json",
                  "history_features": HISTORY / "event_features.csv", "history_lifecycles": HISTORY / "event_lifecycles.csv",
                  "history_lifecycle_source": V4 / "tools/stage005_event_lifecycle_audit.py",
                  "history_headroom_source": V4 / "tools/stage007_objective_headroom_audit.py",
                  "history_archive_source": V4 / "tools/stage006_prefix_equivalence.py",
                  "reference_receipt": REFERENCE / "receipt.json"})
    for name in base.FRAME_NAMES:
        files[f"reference_{name}"] = REFERENCE / f"{name}.csv"
    return dict(sorted(files.items()))


def configured(rows=None):
    base = load("trace_worker_base", V4 / "tools/stage004_counterfactual_validation.py")
    runner = base.support()
    base.STAGE = runner.STAGE = STAGE
    runner.LINE_ID = ROOT.name
    runner.collect_input_files = collect_inputs
    runner.EXPECTED_INPUT_FILE_COUNT = 1501
    original_v1 = runner.load_v1_runner
    def local_v1():
        v1 = original_v1()
        v1.END = v1.pd.Timestamp(END)
        original_install = v1._install_correlation_trace_instrumentation
        def instrument(strategy_class):
            correlation_restore = original_install(strategy_class)
            trace_restore = install_trace(strategy_class, rows)
            def restore():
                trace_restore()
                correlation_restore()
            return restore
        v1._install_correlation_trace_instrumentation = instrument
        return v1
    runner.load_v1_runner = local_v1
    def feature_module():
        history = load("trace_history_features", ROOT / "tools/stage001_history_qualification.py")
        return SimpleNamespace(build_formal_root_event_features=lambda candidates, eligibility, identity:
                               history.build_features(candidates, identity))
    runner.load_feature_module = feature_module
    base.FRAME_NAMES = (*base.FRAME_NAMES, "trade_events", "pending_orders")
    base.support = lambda: runner
    return base, runner


def run_parent():
    import pandas as pd

    base, runner = configured()
    archive = load("trace_archiver", V4 / "tools/stage006_prefix_equivalence.py")
    if OUTPUT.exists():
        raise RuntimeError("trace_output_exists")
    manifest = runner.build_input_manifest()
    runner.validate_frozen_input_contract(FREEZE, manifest)
    runner.claim_execution(ROOT / "stages" / f"{STAGE}_execution/claim.json", manifest)
    OUTPUT.mkdir(mode=0o700)
    runner._write_json_exclusive(OUTPUT / "input_manifest.json", manifest)
    preflight = runner.load_metadata_preflight_module().load_preflight_module()
    paths = None
    try:
        database = manifest["files"]["source_database"]
        paths = runner.prepare_stage002_worker_root(OUTPUT / "workers/A", source_database=Path(database["path"]),
                                                   expected_database_sha256=database["sha256"])
        preflight.write_sandbox_profile(paths["profile"], paths["worker_root"])
        command = ["/usr/bin/sandbox-exec", "-f", str(paths["profile"]), str(Path(sys.executable).resolve()), "-I", "-S", "-B",
                   str(Path(__file__).resolve()), "--worker", "--arm", "A", "--worker-root", str(paths["worker_root"]),
                   "--manifest", str(OUTPUT / "input_manifest.json")]
        start = time.monotonic()
        with paths["log"].open("wb") as stream:
            process = subprocess.run(command, cwd=paths["runtime"], env=preflight.expected_worker_environment(paths["runtime"]),
                                     stdout=stream, stderr=subprocess.STDOUT)
        if process.returncode:
            raise RuntimeError(f"trace_worker_failed:{process.returncode}:{paths['log']}")
        receipt = json.loads(paths["receipt"].read_text())
        if (receipt["status"] != "passed" or receipt["stage"] != STAGE or receipt["arm"] != "A"
                or receipt["file_contract_sha256"] != manifest["file_contract_sha256"]
                or receipt["formal_replay_call_count"] != 1 or any(receipt["sensitive_counters"].values())
                or receipt["network_connection_attempt_count"] != 0 or receipt["audit"]["skip_count"] != 0):
            raise RuntimeError("trace_worker_receipt_invalid")
        for name, identity in receipt["frames"].items():
            if runner._file_identity(paths["worker_root"] / f"{name}.csv") != identity:
                raise RuntimeError(f"frame_identity_mismatch:{name}")
        columns = {"daily": "date", "trades": "datetime", "positions": "date", "entry_candidates": "datetime",
                   "entry_risk": "datetime", "stop_retry_events": "datetime", "root_features": "decision_datetime"}
        for name, column in columns.items():
            ref = HISTORY / "event_features.csv" if name == "root_features" else REFERENCE / f"{name}.csv"
            reference = pd.read_csv(ref, float_precision="round_trip")
            expected = reference[reference[column].astype(str).str[:10].le(END)].reset_index(drop=True)
            observed = pd.read_csv(paths["worker_root"] / f"{name}.csv", float_precision="round_trip")
            pd.testing.assert_frame_equal(expected, observed, check_dtype=False, check_exact=True)
        trace_path = paths["worker_root"] / "execution_trace.json"
        trace = json.loads(trace_path.read_text())
        if not trace:
            raise RuntimeError("trace_empty")
        archives = {name: archive.archive_csv(paths["worker_root"] / f"{name}.csv", identity)
                    for name, identity in receipt["frames"].items()}
        runner._write_json_exclusive(paths["worker_root"] / "archive_receipt.json", archives)
        runner.validate_current_input_manifest(manifest)
        summary = {"stage": STAGE, "status": "passed", "prefix_tables_equal": 7, "execution_end": END,
                   "trace_rows": len(trace), "trace_identity": runner._file_identity(trace_path),
                   "seconds": time.monotonic() - start, "metrics": receipt["metrics"],
                   "file_contract_sha256": manifest["file_contract_sha256"], "new_replay_count": 1,
                   "new_label_count": 0, "model_fit_count": 0, "reviewer_started": False, "archives": archives}
        runner._write_json_exclusive(OUTPUT / "summary.json", summary)
        print(json.dumps({key: value for key, value in summary.items() if key != "archives"}), flush=True)
    except BaseException as exc:
        runner._write_json_exclusive(OUTPUT / "failure.json", {"status": "failed", "error": str(exc), "traceback": traceback.format_exc()})
        raise
    finally:
        if paths and paths["runtime"].exists():
            shutil.rmtree(paths["runtime"])


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--worker", action="store_true")
    parser.add_argument("--arm", choices=["A"])
    parser.add_argument("--worker-root", type=Path)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    if args.freeze:
        _, runner = configured()
        manifest = runner.build_input_manifest()
        runner.validate_input_manifest_payload(manifest)
        payload = {key: manifest[key] for key in ("schema_version", "stage", "line_id", "input_file_count",
                   "input_logical_key_sha256", "file_contract_sha256", "runtime_contract_sha256")}
        payload["execution_authorized"] = True
        runner._write_json_exclusive(FREEZE, payload)
        print(json.dumps(payload), flush=True)
    elif args.run:
        run_parent()
    else:
        rows = []
        base, runner = configured(rows)
        base.run_worker(args)
        runner._write_json_exclusive(args.worker_root / "execution_trace.json", rows)


if __name__ == "__main__":
    main()
