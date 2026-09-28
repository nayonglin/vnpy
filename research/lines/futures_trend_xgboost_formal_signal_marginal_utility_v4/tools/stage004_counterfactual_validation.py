from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import traceback
from contextlib import contextmanager
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parents[2]
STAGE = "stage004_counterfactual_validation"
UPSTREAM = ROOT / "artifacts/stage003_frozen_baseline_event_qualification"
CONTRACT = ROOT / "stages/20260905_1928_stage004_counterfactual_implementation_contract.md"
EXECUTION_CONTRACT = ROOT / "stages/20260905_stage004_execution_contract.md"
OUTPUT = ROOT / "artifacts" / STAGE
ARMS = ("A", "A0", "S")
FRAME_NAMES = ("daily", "trades", "positions", "entry_candidates", "entry_risk", "stop_retry_events", "root_features")


def load_stage003():
    path = ROOT / "tools/stage003_frozen_baseline_event_qualification.py"
    spec = importlib.util.spec_from_file_location("stage004_frozen_support", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def collect_inputs():
    files = load_stage003().collect_input_files()
    files.update({
        "stage004_runner": Path(__file__).resolve(),
        "stage004_tests": ROOT / "tests/test_stage004_counterfactual_validation.py",
        "stage004_implementation_contract": CONTRACT,
        "stage004_execution_contract": EXECUTION_CONTRACT,
        "stage003_success_record": ROOT / "stages/20260905_1928_stage003_event_feature_qualification_pass.md",
        "stage003_success_summary": UPSTREAM / "summary.json",
        "stage003_success_features": UPSTREAM / "event_features.csv",
        "stage003_success_manifest": UPSTREAM / "input_manifest.json",
        "stage003_success_A1": UPSTREAM / "workers/A1/receipt.json",
        "stage003_success_A2": UPSTREAM / "workers/A2/receipt.json",
        "stage003_claim": ROOT / "stages/20260905_stage003_execution_state/claim.json",
        "stage003_freeze": ROOT / "stages/20260905_stage003a_input_contract_freeze.json",
    })
    if any(path.is_symlink() or not path.is_file() for path in files.values()):
        raise RuntimeError("stage004_input_missing")
    return dict(sorted(files.items()))


def support():
    runner = load_stage003().load_runner()
    runner.STAGE = STAGE
    runner.collect_input_files = collect_inputs
    runner.EXPECTED_INPUT_FILE_COUNT = 1481
    return runner


def earliest_target():
    import pandas as pd

    summary = json.loads((UPSTREAM / "summary.json").read_text())
    source = UPSTREAM / "event_features.csv"
    if not summary["passed"] or load_stage003().sha256(source) != summary["event_feature_file"]["sha256"]:
        raise RuntimeError("upstream_qualification_invalid")
    frame = pd.read_csv(source).sort_values(["decision_datetime", "event_id"], kind="stable")
    target = json.loads(frame.iloc[0].to_json())
    if target["product_vt_symbol"] == "fu.SHFE":
        raise RuntimeError("fixed_fu_intervention_forbidden")
    return target


@contextmanager
def intervention(strategy_class, target):
    plan_name = "_plan_flat_entry_candidates"
    record_name = "_record_entry_candidate_snapshot"
    original_plan = getattr(strategy_class, plan_name)
    original_record = getattr(strategy_class, record_name)
    local = {name: strategy_class.__dict__.get(name) for name in (plan_name, record_name)}
    audit = {"skip_count": 0, "verified_snapshot_count": 0, "target": target}

    def filtered(self, contexts):
        plans = original_plan(self, contexts)
        if target is None:
            return plans
        plan = plans.get(target["product_vt_symbol"])
        if plan is None or plan["target_bar"].datetime.isoformat() != target["decision_datetime"]:
            return plans
        identity = {
            "product_vt_symbol": str(plan["product_vt_symbol"]),
            "contract_vt_symbol": str(plan["target_contract"]),
            "direction": str(plan["direction"]),
            "signal": str(plan["signal"]),
        }
        if any(identity[key] != target[key] for key in identity) or plan["candidate_status"] != "opened" or audit["skip_count"]:
            raise RuntimeError("intervention_plan_identity_mismatch")
        audit["skip_count"] += 1
        audit["selected_volume"] = int(plan["volume"])
        audit["pre_event_equity"] = float(self.estimated_equity)
        plan["candidate_status"] = "skipped"
        plan["skip_reason"] = "research_frozen_root_skip"
        return plans

    def recorded(self, **kwargs):
        result = original_record(self, **kwargs)
        if target is None or kwargs["product_vt_symbol"] != target["product_vt_symbol"] or kwargs["bar"].datetime.isoformat() != target["decision_datetime"]:
            return result
        row = self.entry_candidate_snapshots[-1]
        if (int(row["candidate_index"]) != int(target["candidate_index"])
                or row["candidate_status"] != "skipped"
                or row["skip_reason"] != "research_frozen_root_skip"
                or row["entry_context"] != "flat_entry"):
            raise RuntimeError("intervention_snapshot_identity_mismatch")
        audit["verified_snapshot_count"] += 1
        return result

    setattr(strategy_class, plan_name, filtered)
    setattr(strategy_class, record_name, recorded)
    try:
        yield audit
    finally:
        for name, value in local.items():
            if value is None:
                delattr(strategy_class, name)
            else:
                setattr(strategy_class, name, value)


def equity_metrics(daily, trades, initial=150000.0):
    import numpy as np

    values = daily.sort_values("date")["account_equity"].to_numpy(dtype=float)
    curve = np.r_[initial, values]
    if not len(values) or not np.isfinite(curve).all() or (curve <= 0).any():
        raise RuntimeError("invalid_account_equity")
    returns = curve[1:] / curve[:-1] - 1
    deviation = returns.std(ddof=1) if len(returns) > 1 else 0.0
    pnl = daily["total_net_pnl"].to_numpy(dtype=float)
    active = pnl[pnl != 0]
    return {
        "end_equity": float(values[-1]),
        "total_return_pct": float((values[-1] / initial - 1) * 100),
        "max_drawdown_pct": float((curve / np.maximum.accumulate(curve) - 1).min() * 100),
        "sharpe": float(returns.mean() / deviation * np.sqrt(252)) if deviation else None,
        "total_slippage": float(daily["total_slippage"].sum()),
        "total_commission": float(daily["commission"].sum()),
        "trade_count": int(len(trades)),
        "nonzero_daily_win_rate_pct": float((active > 0).mean() * 100) if len(active) else None,
    }


def _frame_equal(left, right):
    import pandas as pd

    pd.testing.assert_frame_equal(left.reset_index(drop=True), right.reset_index(drop=True),
                                  check_dtype=False, check_exact=True)


def event_endpoint(frames, target, contract_products):
    import pandas as pd

    candidates = frames["entry_candidates"]
    date = str(target["decision_date"])
    next_roots = candidates[
        candidates.product_vt_symbol.eq(target["product_vt_symbol"])
        & candidates.entry_context.eq("flat_entry") & candidates.candidate_status.eq("opened")
        & candidates.candidate_index.gt(int(target["candidate_index"]))
    ]
    next_date = str(next_roots.date.min())[:10] if len(next_roots) else "9999-12-31"
    trades = frames["trades"]
    opens = trades[
        trades.vt_symbol.eq(target["contract_vt_symbol"]) & trades.offset.eq("Open")
        & trades.direction.eq("Long" if target["direction"] == "long" else "Short")
        & trades.date.astype(str).str[:10].ge(date) & trades.date.astype(str).str[:10].lt(next_date)
    ]
    if opens.empty:
        return {"status": "unresolved_no_root_fill", "event_id": target["event_id"]}
    first_fill = str(opens.date.min())[:10]
    positions = frames["positions"].copy()
    positions["product"] = positions.vt_symbol.map(contract_products)
    if positions["product"].isna().any():
        raise RuntimeError("position_product_mapping_missing")
    positions = positions[positions["product"].eq(target["product_vt_symbol"])].copy()
    positions["date"] = positions.date.astype(str).str[:10]
    positions["absolute_position"] = positions.end_pos.abs()
    exposure = positions.groupby("date").absolute_position.sum()
    closed = exposure[(exposure.index >= first_fill) & exposure.eq(0)]
    if closed.empty:
        return {"status": "right_censored", "event_id": target["event_id"], "first_fill_date": first_fill}
    end = str(closed.index.min())
    if end >= next_date:
        return {"status": "unresolved_same_day_root_overlap", "event_id": target["event_id"]}
    return {"status": "mature", "event_id": target["event_id"], "first_fill_date": first_fill, "end_date": end}


def account_marginal(a_daily, s_daily, start_date, end_date, pre_equity):
    import numpy as np

    curves = []
    dates = None
    for frame in (a_daily, s_daily):
        frame = frame.sort_values("date")
        selected = frame[frame.date.astype(str).str[:10].between(start_date, end_date)]
        observed = selected.date.astype(str).str[:10].tolist()
        if (not observed or observed[0] != start_date or observed[-1] != end_date
                or len(observed) != len(set(observed)) or (dates is not None and observed != dates)):
            raise RuntimeError("label_curve_dates_mismatch")
        dates = observed
        curve = np.r_[pre_equity, selected.account_equity.to_numpy(dtype=float)]
        if not np.isfinite(curve).all() or (curve <= 0).any():
            raise RuntimeError("label_curve_invalid")
        curves.append(curve)
    a, s = curves
    drawdowns = [float((curve / np.maximum.accumulate(curve) - 1).min()) for curve in curves]
    return {
        "return_marginal": float((a[-1] - s[-1]) / pre_equity),
        "drawdown_marginal": drawdowns[0] - drawdowns[1],
        "A_end_equity": float(a[-1]), "S_end_equity": float(s[-1]),
        "A_max_drawdown": drawdowns[0], "S_max_drawdown": drawdowns[1],
        "pre_event_equity": pre_equity, "start_date": start_date, "end_date": end_date,
    }


def run_worker(args):
    stage3 = load_stage003()
    runner = support()
    metadata_support = runner.load_metadata_preflight_module()
    preflight = metadata_support.load_preflight_module()
    root = args.worker_root.resolve(strict=True)
    runtime = root / "runtime"
    preflight._validate_worker_bootstrap(runtime)
    preflight.prove_external_write_denied(root.parent.parent / f"probe_{args.arm}")
    sys.path.extend([str(preflight.python_site_packages()), str(WORKSPACE)])
    manifest = json.loads(args.manifest.read_text())
    runner.validate_current_input_manifest(manifest)
    if runner._file_identity(runtime / ".vntrader/database.db")["sha256"] != manifest["files"]["source_database"]["sha256"]:
        raise RuntimeError("database_copy_mismatch")
    attestation = preflight._load_release_attestation(runner.RELEASE_ATTESTATION)
    v1 = runner.load_v1_runner()
    target = earliest_target()
    formal = v1._active_formal_identity()
    for field in ("formal_release_id", "formal_strategy", "official_live_version", "formal_material_manifest_sha256"):
        if target[field] != formal[field]:
            raise RuntimeError("target_formal_identity_mismatch")
    expected = metadata_support.validate_frozen_metadata_files(manifest)
    network = preflight.NetworkBlock()
    guard = stage3.baseline_guard_class(preflight)((root,), allowed_formal_replay_count=1)
    guard.assert_no_sensitive_modules_loaded()
    runner._write_json_exclusive(root / "started.json", {"pid": os.getpid(), "arm": args.arm, "status": "replaying"})
    with network, guard:
        context, adapter_calls, adapter_restored = preflight.import_production_context_with_attestation(attestation)
        candidate = sys.modules[runner.CANDIDATE_MODULE_NAME]
        strategy_class = context["s901"].s847.QmtRollPortfolioStrategyStage847C9StopRetry
        with metadata_support.redirect_metadata_outputs(candidate, root) as targets:
            metadata = context["s901"].s513._metadata()
            restore_trace = v1._install_correlation_trace_instrumentation(strategy_class)
            try:
                if args.arm == "A":
                    audit = {"skip_count": 0, "verified_snapshot_count": 0, "target": None}
                    daily, raw, spec = context["s901"]._run_live_c9(metadata, v1.START, v1.END)
                else:
                    with intervention(strategy_class, target if args.arm == "S" else None) as audit:
                        daily, raw, spec = context["s901"]._run_live_c9(metadata, v1.START, v1.END)
            finally:
                restore_trace()
            metadata_support.verify_derived_outputs(targets, expected)
        if float(spec.capital.account_capital) != 150000 or spec.profile != context["live_config"].OFFICIAL_LIVE_PROFILE_NAME:
            raise RuntimeError("formal_spec_mismatch")
        if args.arm == "S" and (audit["skip_count"] != 1 or audit["verified_snapshot_count"] != 1):
            raise RuntimeError("intervention_not_applied_exactly_once")
        eligibility = v1.pd.read_csv(formal["eligibility_path"])
        features = runner.load_feature_module().build_formal_root_event_features(raw["entry_candidates"], eligibility, formal)
        frames = {"daily": daily, "root_features": features, **{name: raw[name] for name in FRAME_NAMES if name not in {"daily", "root_features"}}}
    if any(guard.counters.values()) or network.attempts or guard.formal_replay_call_count != 1 or len(adapter_calls) != 1 or not adapter_restored:
        raise RuntimeError("worker_safety_gate_failed")
    identities = {}
    for name, frame in frames.items():
        path = root / f"{name}.csv"
        runner._write_bytes_exclusive(path, frame.to_csv(index=False, float_format="%.17g").encode())
        identities[name] = runner._file_identity(path)
    receipt = {
        "status": "passed", "stage": STAGE, "arm": args.arm, "pid": os.getpid(),
        "file_contract_sha256": manifest["file_contract_sha256"], "formal_identity": formal,
        "audit": audit, "frames": identities, "baseline_inference": guard.receipt(),
        "sensitive_counters": guard.counters, "formal_replay_call_count": 1,
        "network_connection_attempt_count": 0,
        "metrics": equity_metrics(daily, raw["trades"]),
        "contract_products": metadata["source_symbol_by_contract"],
    }
    runner._write_json_exclusive(root / "receipt.json", receipt)


def read_frames(root):
    import pandas as pd

    frames = {}
    for name in FRAME_NAMES:
        try:
            frames[name] = pd.read_csv(root / f"{name}.csv", low_memory=False, float_precision="round_trip")
        except pd.errors.EmptyDataError:
            frames[name] = pd.DataFrame()
    return frames


def validate_results(results, target):
    import pandas as pd

    a, a0, s = [item["frames"] for item in results]
    for name in FRAME_NAMES:
        _frame_equal(a[name], a0[name])
    runner = support()
    parity = runner.evaluate_stage002_features(a["root_features"], pd.read_csv(UPSTREAM / "event_features.csv"))
    if parity["passed"] is not True:
        raise RuntimeError("baseline_event_parity_failed")
    for name, column in (("daily", "date"), ("trades", "datetime"), ("positions", "date")):
        left, right = a[name], s[name]
        mask_left = left[column].astype(str).str[:10].lt(target["decision_date"])
        mask_right = right[column].astype(str).str[:10].lt(target["decision_date"])
        _frame_equal(left[mask_left], right[mask_right])
    _frame_equal(
        a["entry_candidates"][a["entry_candidates"].candidate_index.lt(int(target["candidate_index"]))],
        s["entry_candidates"][s["entry_candidates"].candidate_index.lt(int(target["candidate_index"]))],
    )
    baseline_row = a["entry_candidates"][a["entry_candidates"].candidate_index.eq(int(target["candidate_index"]))]
    skipped_row = s["entry_candidates"][s["entry_candidates"].candidate_index.eq(int(target["candidate_index"]))]
    if len(baseline_row) != 1 or len(skipped_row) != 1 or skipped_row.iloc[0]["candidate_status"] != "skipped":
        raise RuntimeError("target_snapshot_verification_failed")
    endpoint = event_endpoint(a, target, results[0]["receipt"]["contract_products"])
    marginal = None
    if endpoint["status"] == "mature":
        marginal = account_marginal(a["daily"], s["daily"], target["decision_date"], endpoint["end_date"], float(baseline_row.iloc[0]["estimated_equity"]))
    return {
        "no_op_equal": True, "baseline_event_parity": True, "pre_target_equal": True,
        "single_skip_verified": True, "endpoint": endpoint, "marginal": marginal,
        "label_mechanism_ready": endpoint["status"] == "mature",
    }


def run_parent():
    runner = support()
    if OUTPUT.exists():
        raise RuntimeError("stage004_output_already_exists")
    manifest = runner.build_input_manifest()
    runner.validate_input_manifest_payload(manifest)
    freeze = ROOT / "stages/20260905_stage004_input_contract_freeze.json"
    runner.validate_frozen_input_contract(freeze, manifest)
    claim = runner.claim_execution(ROOT / "stages/20260905_stage004_execution_state/claim.json", manifest)
    OUTPUT.mkdir(parents=True, mode=0o700)
    runner._write_json_exclusive(OUTPUT / "input_manifest.json", manifest)
    target = earliest_target()
    runner._write_json_exclusive(OUTPUT / "target.json", target)
    metadata_support = runner.load_metadata_preflight_module()
    preflight = metadata_support.load_preflight_module()
    try:
        results = []
        for arm in ARMS:
            database = manifest["files"]["source_database"]
            paths = runner.prepare_stage002_worker_root(OUTPUT / "workers" / arm,
                source_database=Path(database["path"]), expected_database_sha256=database["sha256"])
            preflight.write_sandbox_profile(paths["profile"], paths["worker_root"])
            command = ["/usr/bin/sandbox-exec", "-f", str(paths["profile"]),
                       str(Path(sys.executable).resolve()), "-I", "-S", "-B", str(Path(__file__).resolve()),
                       "--worker", "--arm", arm, "--worker-root", str(paths["worker_root"]),
                       "--manifest", str(OUTPUT / "input_manifest.json")]
            with paths["log"].open("wb") as log:
                completed = subprocess.run(command, cwd=paths["runtime"],
                    env=preflight.expected_worker_environment(paths["runtime"]), stdout=log, stderr=subprocess.STDOUT)
            if completed.returncode:
                raise RuntimeError(f"worker_failed:{arm}:{paths['log']}")
            receipt = json.loads(paths["receipt"].read_text())
            if receipt["file_contract_sha256"] != manifest["file_contract_sha256"]:
                raise RuntimeError("worker_manifest_mismatch")
            for name in FRAME_NAMES:
                path = paths["worker_root"] / f"{name}.csv"
                if runner._file_identity(path) != receipt["frames"][name]:
                    raise RuntimeError(f"worker_frame_changed:{arm}:{name}")
            results.append({"receipt": receipt, "frames": read_frames(paths["worker_root"])})
            shutil.rmtree(paths["runtime"])
            print(json.dumps({"arm": arm, "status": "complete", "rows": len(results[-1]["frames"]["daily"])}), flush=True)
        if len({item["receipt"]["pid"] for item in results}) != 3:
            raise RuntimeError("workers_not_distinct")
        validation = validate_results(results, target)
        runner.validate_current_input_manifest(manifest)
        summary = {
            "stage": STAGE, "status": "passed", "reviewer_started": False,
            "campaign_nonce": claim["campaign_nonce"], "file_contract_sha256": manifest["file_contract_sha256"],
            "target": target, "metrics": {arm: item["receipt"]["metrics"] for arm, item in zip(ARMS, results)},
            "formal_replay_call_count": 3, **validation,
        }
        runner._write_json_exclusive(OUTPUT / "summary.json", summary)
        print(json.dumps(summary), flush=True)
    except BaseException as exc:
        for runtime in (OUTPUT / "workers").glob("*/runtime"):
            shutil.rmtree(runtime)
        runner._write_json_exclusive(OUTPUT / "failure.json", {"stage": STAGE, "status": "failed", "error": str(exc), "traceback": traceback.format_exc()})
        raise


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--worker", action="store_true")
    parser.add_argument("--arm", choices=ARMS)
    parser.add_argument("--worker-root", type=Path)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    if args.run:
        run_parent()
    else:
        try:
            run_worker(args)
        except BaseException:
            print(traceback.format_exc(), file=sys.stderr, flush=True)
            raise


if __name__ == "__main__":
    main()
