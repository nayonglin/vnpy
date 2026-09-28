from __future__ import annotations

import importlib.util
import json
import math
import traceback
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts/stage017_label_path_decomposition"
SNAPSHOT = ROOT / "artifacts/stage005_label_collection/20260906_020434_393264/summary.json"
CONTRACT = ROOT / "stages/20260906_0422_stage017_label_path_decomposition_contract.md"
TOL = 1e-6


def load(name):
    spec = importlib.util.spec_from_file_location("decomposition_" + name, ROOT / "tools" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_daily(daily):
    if (daily.empty or daily.date.tolist() != sorted(set(daily.date))
            or not daily.date.astype(str).str.fullmatch(r"\d{4}-\d{2}-\d{2}").all()
            or pd.to_datetime(daily.date, errors="coerce").isna().any()
            or not np.isfinite(daily[["total_net_pnl", "account_equity"]].to_numpy(dtype=float)).all()
            or daily.account_equity.le(0).any()):
        raise RuntimeError("decomposition_daily_invalid")


def product_ledger(positions, daily, mapping):
    validate_daily(daily)
    if (not mapping or positions.duplicated(["date", "vt_symbol"]).any()
            or not np.isfinite(positions.net_pnl.to_numpy(dtype=float)).all()):
        raise RuntimeError("decomposition_position_invalid")
    frame = positions[["date", "vt_symbol", "net_pnl"]].copy()
    frame["product"] = frame.vt_symbol.map(mapping)
    if frame["product"].isna().any():
        raise RuntimeError("decomposition_contract_unmapped")
    frame = frame.loc[frame.date.between(daily.date.iloc[0], daily.date.iloc[-1])]
    if sorted(set(frame.date)) != daily.date.tolist():
        raise RuntimeError("decomposition_ledger_calendar_incomplete")
    matrix = frame.groupby(["date", "product"], sort=True).net_pnl.sum().unstack(fill_value=0.0)
    matrix = matrix.reindex(index=daily.date.tolist(), columns=sorted(set(mapping.values())), fill_value=0.0)
    error = float(np.max(np.abs(matrix.sum(axis=1).to_numpy() - daily.total_net_pnl.to_numpy())))
    if error > TOL:
        raise RuntimeError(f"decomposition_daily_pnl_not_conserved:{error}")
    return matrix, error


def decompose(a_matrix, s_matrix, a_daily, s_daily, product, decision, end, pre_equity, label):
    validate_daily(a_daily)
    validate_daily(s_daily)
    a = a_daily.loc[a_daily.date.le(end)].set_index("date")
    s = s_daily.set_index("date")
    if (not math.isfinite(pre_equity) or pre_equity <= 0 or not math.isfinite(label)
            or not a.index.equals(s.index) or end != s.index[-1] or decision not in s.index or decision > end
            or a_matrix.index.tolist() != a_daily.date.tolist() or s_matrix.index.tolist() != s_daily.date.tolist()
            or not a_matrix.columns.equals(s_matrix.columns) or product not in a_matrix.columns):
        raise RuntimeError("decomposition_event_window_invalid")
    delta = a_matrix.loc[s.index] - s_matrix
    if not np.isfinite(delta.to_numpy()).all():
        raise RuntimeError("decomposition_delta_nonfinite")
    before = s.index < decision
    if before.any() and (np.max(np.abs(delta.loc[before].to_numpy())) > TOL
                         or np.max(np.abs(a.loc[before, "account_equity"] - s.loc[before, "account_equity"])) > TOL):
        raise RuntimeError("decomposition_prefix_changed")
    window = delta.loc[decision:end]
    target = window[product]
    other = window.drop(columns=product).sum(axis=1)
    total = target + other
    cash_delta = a.loc[window.index, "account_equity"] - s.loc[window.index, "account_equity"]
    daily_delta = a.loc[window.index, "total_net_pnl"] - s.loc[window.index, "total_net_pnl"]
    residual = max(float(np.max(np.abs(total.cumsum() - cash_delta))),
                   float(np.max(np.abs(total - daily_delta))),
                   abs(float(total.sum()) - label * pre_equity))
    if residual > TOL:
        raise RuntimeError(f"decomposition_label_or_daily_path_mismatch:{residual}")
    product_delta = window.sum(axis=0)
    target_cash, other_cash, total_cash = float(target.sum()), float(other.sum()), float(total.sum())
    denominator = abs(target_cash) + abs(other_cash)
    other_values = product_delta.drop(product)
    result = {"horizon_days": len(window), "target_delta_cash": target_cash, "other_delta_cash": other_cash,
              "total_delta_cash": total_cash, "target_component_fraction": target_cash / pre_equity,
              "other_component_fraction": other_cash / pre_equity, "return_marginal_from_ledger": total_cash / pre_equity,
              "other_abs_net_share": abs(other_cash) / denominator if denominator > TOL else None,
              "other_nonzero": bool(abs(other_cash) > TOL), "other_dominates": bool(abs(other_cash) > abs(target_cash) + TOL),
              "target_total_sign_flip": bool(abs(target_cash) > TOL and abs(total_cash) > TOL and target_cash * total_cash < 0),
              "other_nonzero_product_count": int(other_values.abs().gt(TOL).sum()),
              "other_gross_abs_product_delta_cash": float(other_values.abs().sum()), "max_reconciliation_error_cash": residual}
    days = pd.DataFrame({"date": window.index, "target_delta_net_pnl": target.to_numpy(),
                         "other_delta_net_pnl": other.to_numpy(), "total_delta_net_pnl": total.to_numpy(),
                         "cumulative_delta_net_pnl": total.cumsum().to_numpy(), "equity_delta": cash_delta.to_numpy()})
    products = pd.DataFrame({"product": product_delta.index,
                             "A_net_pnl": a_matrix.loc[window.index].sum(axis=0).to_numpy(),
                             "S_net_pnl": s_matrix.loc[window.index].sum(axis=0).to_numpy(),
                             "delta_net_pnl": product_delta.to_numpy(), "is_target": product_delta.index == product})
    return result, days, products


def describe(frame):
    shares = frame.other_abs_net_share.dropna()
    denominator = float(frame.target_delta_cash.abs().sum() + frame.other_delta_cash.abs().sum())
    x, y = frame.target_component_fraction, frame.return_marginal_from_ledger
    correlation = float(x.corr(y)) if len(frame) > 1 and x.std() > 0 and y.std() > 0 else None
    return {"count": len(frame), "other_nonzero_count": int(frame.other_nonzero.sum()),
            "other_dominates_count": int(frame.other_dominates.sum()),
            "target_total_sign_flip_count": int(frame.target_total_sign_flip.sum()),
            "zero_share_denominator_count": int(frame.other_abs_net_share.isna().sum()),
            "weighted_other_abs_net_share": float(frame.other_delta_cash.abs().sum()) / denominator if denominator > TOL else None,
            "other_share_quantiles": {str(q): float(shares.quantile(q)) for q in (0, .25, .5, .75, 1)} if len(shares) else {},
            "horizon_days_quantiles": {str(q): float(frame.horizon_days.quantile(q)) for q in (0, .25, .5, .75, 1)},
            "target_total_fraction_correlation": correlation,
            "max_reconciliation_error_cash": float(frame.max_reconciliation_error_cash.max())}


def prepare_inputs():
    batch = load("stage004_label_batch")
    _, runner = batch.configured()
    collector = load("stage005_label_collection")
    if collector.digest(SNAPSHOT) != "c5a166ee35972197d411de197d64408fb605889ab630f94549bda71d16f10435":
        raise RuntimeError("decomposition_snapshot_changed")
    events, _, _ = load("stage006_monthly_models").load_verified_snapshot(SNAPSHOT)
    plan = batch.read_plan()
    manifest_path = batch.OUTPUT / "input_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    runner.validate_current_input_manifest(manifest)
    batch.verify_baseline_inputs(manifest)
    snapshot = json.loads(SNAPSHOT.read_text())
    files = {Path(path) for path in snapshot["source_identities"]}
    files.update(Path(item["path"]) for item in snapshot["output_identities"].values())
    files.update(Path(item["path"]) for item in manifest["files"].values())
    files.update({SNAPSHOT, Path(__file__).resolve(), CONTRACT, ROOT / "tests/test_stage017_label_path_decomposition.py",
                  ROOT / "tools/stage006_monthly_models.py", manifest_path})
    a_receipt_path = batch.REFERENCE / "receipt.json"
    a_receipt = json.loads(a_receipt_path.read_text())
    mapping = a_receipt["contract_products"]
    if len(mapping) != 801 or len(set(mapping.values())) != 19:
        raise RuntimeError("decomposition_frozen_mapping_changed")
    for name in ("daily", "positions"):
        path = batch.REFERENCE / (name + ".csv")
        collector.verify_identity(path, a_receipt["frames"][name])
        files.add(path)
    jobs = []
    for job in plan["jobs"]:
        folder = batch.OUTPUT / "jobs" / job["event_id"]
        label_path, receipt_path, archive_path = (folder / name for name in ("label.json", "receipt.json", "archive_receipt.json"))
        label, receipt, archives = (json.loads(path.read_text()) for path in (label_path, receipt_path, archive_path))
        if (label["status"] != "passed" or label["event_id"] != job["event_id"] or label["lifecycle_status"] != job["status"]
                or label["receipt_sha256"] != collector.digest(receipt_path)
                or label["file_contract_sha256"] != manifest["file_contract_sha256"]
                or label["plan_sha256"] != collector.digest(batch.PLAN)
                or receipt["contract_products"] != mapping or receipt["audit"]["target"] != job["target"]
                or receipt["audit"]["skip_count"] != 1 or not label["pre_target_equal"] or not label["target_features_exact"]):
            raise RuntimeError("decomposition_job_identity_invalid")
        files.update({label_path, receipt_path, archive_path})
        normalized = "analysis_normalization_sha256" in label
        if normalized:
            norm_path = folder / "normalization_receipt.json"
            if (collector.digest(norm_path) != label["analysis_normalization_sha256"]
                    or collector.digest(ROOT / "tools/stage004b_zero_trade_analysis.py") != label["analysis_tool_sha256"]
                    or job["event_id"] != load("stage004b_zero_trade_analysis").EVENT_ID):
                raise RuntimeError("decomposition_normalization_not_bound")
            normal = json.loads(norm_path.read_text())
            files.add(norm_path)
            for path, identity in normal["source_identities"].items():
                collector.verify_identity(path, identity)
                files.add(Path(path))
        elif (folder / "normalization_receipt.json").exists():
            raise RuntimeError("decomposition_unbound_normalization")
        views = {}
        for name in ("daily", "positions"):
            identity = normal["normalized_" + name] if normalized else archives[name]
            path = folder / (("normalized_" if normalized else "") + name + ".csv.gz")
            collector.verify_identity(path, identity["archive"])
            if not normalized and (identity["raw_sha256"] != receipt["frames"][name]["sha256"]
                                   or identity["raw_size"] != receipt["frames"][name]["size"]):
                raise RuntimeError("decomposition_archive_receipt_mismatch")
            files.add(path)
            views[name] = (path, identity)
        jobs.append({"job": job, "label": label, "receipt": receipt, "views": views})
    sources = {str(path): runner._file_identity(path) for path in sorted(files)}
    return batch, runner, collector, events, manifest, mapping, jobs, sources


def run():
    if OUTPUT.exists():
        raise RuntimeError("decomposition_output_already_exists")
    batch, runner, collector, events, manifest, mapping, jobs, sources = prepare_inputs()
    OUTPUT.mkdir(mode=0o700)
    (OUTPUT / "events").mkdir()
    batch.write_json(OUTPUT / "input_manifest.json", {"source_identities": sources,
                     "evidence_type": "post_failure_descriptive_account_pnl_decomposition", "cash_tolerance": TOL})
    records, daily_parts, product_parts = [], [], []
    try:
        network = runner.load_metadata_preflight_module().load_preflight_module().NetworkBlock()
        with network:
            a_daily = batch.read_frame(batch.REFERENCE / "daily.csv")
            columns = ["date", "vt_symbol", "net_pnl"]
            a_matrix, max_day_error = product_ledger(pd.read_csv(batch.REFERENCE / "positions.csv", usecols=columns,
                                                               float_precision="round_trip"), a_daily, mapping)
            by_id = events.set_index("event_id")
            for number, item in enumerate(jobs, 1):
                job, label, receipt = item["job"], item["label"], item["receipt"]
                for path, identity in item["views"].values():
                    collector.verify_archive(path, identity)
                s_daily = batch.read_frame(item["views"]["daily"][0])
                s_positions = pd.read_csv(item["views"]["positions"][0], usecols=columns, float_precision="round_trip")
                if s_positions.date.gt(job["end_date"]).any():
                    raise RuntimeError("decomposition_source_after_endpoint")
                s_matrix, error = product_ledger(s_positions, s_daily, mapping)
                max_day_error = max(max_day_error, error)
                event = by_id.loc[job["event_id"]]
                if (event.label_status != "verified" or event.label_end_date != job["end_date"]
                        or event.return_marginal != label["marginal"]["return_marginal"]
                        or event.drawdown_marginal != label["marginal"]["drawdown_marginal"]):
                    raise RuntimeError("decomposition_original_label_mismatch")
                result, days, products = decompose(a_matrix, s_matrix, a_daily, s_daily, event.product_vt_symbol,
                    event.decision_date, job["end_date"], receipt["audit"]["pre_event_equity"], event.return_marginal)
                record = {"event_id": job["event_id"], "candidate_index": int(event.candidate_index),
                          "decision_date": event.decision_date, "end_date": job["end_date"],
                          "product_vt_symbol": event.product_vt_symbol, "lifecycle_status": event.lifecycle_status,
                          "original_return_marginal": float(event.return_marginal),
                          "pre_event_equity": float(receipt["audit"]["pre_event_equity"]), **result}
                records.append(record)
                daily_parts.append(days.assign(event_id=job["event_id"]))
                product_parts.append(products.assign(event_id=job["event_id"]))
                batch.write_json(OUTPUT / "events" / (job["event_id"] + ".json"), record)
                if number % 20 == 0 or number == len(jobs):
                    print(json.dumps({"completed": number, "planned": len(jobs)}), flush=True)
        if network.attempts or len(records) != 274 or len({row["event_id"] for row in records}) != 274:
            raise RuntimeError("decomposition_inventory_or_network_invalid")
        frame = pd.DataFrame(records)
        outputs = {"event_decomposition.csv": frame, "daily_decomposition.csv": pd.concat(daily_parts, ignore_index=True),
                   "product_decomposition.csv": pd.concat(product_parts, ignore_index=True),
                   "censored_events.csv": events.loc[events.label_status.eq("censored"),
                        ["event_id", "candidate_index", "decision_date", "product_vt_symbol", "label_status", "lifecycle_status"]]}
        for name, value in outputs.items():
            with (OUTPUT / name).open("x") as stream:
                value.to_csv(stream, index=False, float_format="%.17g")
        for path, identity in sources.items():
            if runner._file_identity(path) != identity:
                raise RuntimeError(f"decomposition_source_changed:{path}")
        runner.validate_current_input_manifest(manifest)
        summary = {"stage": "stage017_label_path_decomposition", "status": "passed", "event_count": len(frame),
                   "censored_count": len(outputs["censored_events.csv"]), "source_count": len(sources),
                   "decoded_s_archive_count": 2 * len(jobs), "daily_pnl_max_error_cash": max_day_error,
                   "all_events": describe(frame), "by_year": {year: describe(rows) for year, rows in frame.groupby(frame.decision_date.str[:4])},
                   "new_label_count": 0, "new_fit_count": 0, "new_prediction_count": 0, "new_strategy_replay_count": 0,
                   "network_attempt_count": network.attempts, "reviewer_started": False,
                   "evidence_type": "post_failure_descriptive_account_pnl_decomposition", "drawdown_decomposed": False,
                   "output_identities": {name: runner._file_identity(OUTPUT / name) for name in ["input_manifest.json", *outputs]},
                   "created_at_utc": datetime.now(timezone.utc).isoformat()}
        batch.write_json(OUTPUT / "summary.json", summary)
        print(json.dumps(summary, allow_nan=False), flush=True)
        return summary
    except BaseException as exc:
        batch.write_json(OUTPUT / "failure.json", {"status": "failed", "completed": len(records), "error": str(exc),
                                                  "traceback": traceback.format_exc()})
        raise


if __name__ == "__main__":
    run()
