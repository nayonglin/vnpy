from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "stages/20260905_2049_stage004b_zero_trade_analysis_contract.md"
EVENT_ID = "5a18f7dca90da5275c014d7201dfb1cbe4564ff75914cf3251c96215917f3dd5"
ZERO_POSITION_FIELDS = ["start_pos", "end_pos", "trade_count", "commission", "slippage", "holding_pnl", "trading_pnl", "total_pnl", "net_pnl"]


def normalize_zero_trade(raw, positions, trades, dates, columns, capital=150000.0):
    if (not trades.empty or len(raw) != 1 or not dates or dates != sorted(set(dates))
            or raw.iloc[0]["date"] != dates[-1] or float(raw.iloc[0]["account_equity"]) != capital
            or positions.duplicated(["date", "vt_symbol"]).any()):
        raise RuntimeError("not_verified_zero_trade_account")
    numbers = positions[ZERO_POSITION_FIELDS].apply(pd.to_numeric, errors="raise").to_numpy(dtype=float)
    if not np.isfinite(numbers).all() or np.count_nonzero(numbers):
        raise RuntimeError("nonzero_or_unknown_position_ledger")
    observed_dates = sorted(set(positions.loc[positions.date.between(dates[0], dates[-1]), "date"]))
    if observed_dates != dates:
        raise RuntimeError("zero_ledger_calendar_incomplete")
    zero_daily = ["net_pnl", "total_net_pnl", "total_slippage", "commission", "trade_count"]
    optional = ["slippage", "turnover", "c3_margin_exact", "c3_active_contracts", "c3_active_products",
                "total_margin_exact", "broker10_total_margin_exact", "broker10_margin_to_equity_pct"]
    zero_daily += [key for key in optional if key in raw]
    values = raw[zero_daily].to_numpy(dtype=float)
    if not np.isfinite(values).all() or np.count_nonzero(values):
        raise RuntimeError("nonzero_raw_daily")
    missing = set(columns) - set(raw)
    if missing - {"holding_pnl", "trading_pnl", "total_pnl"} or set(raw) - set(columns):
        raise RuntimeError("unknown_daily_schema")
    result = pd.concat([raw.copy() for _ in dates], ignore_index=True)
    result["date"] = dates
    for key in missing:
        result[key] = 0.0
    return result.loc[:, columns]


def normalize_zero_positions(positions):
    values = positions[ZERO_POSITION_FIELDS].to_numpy(dtype=float)
    if (not np.isfinite(values).all() or np.count_nonzero(values) or positions.pre_close.ne(0).any()
            or not np.isfinite(positions.close_price.to_numpy(dtype=float)).all()
            or positions.duplicated(["date", "vt_symbol"]).any()):
        raise RuntimeError("not_uncomputed_zero_position_ledger")
    dates = sorted(positions.date.unique())
    previous = dict(zip(dates, [None, *dates[:-1]]))
    keys = pd.MultiIndex.from_tuples([(previous[day], symbol) for day, symbol in
                                     zip(positions.date, positions.vt_symbol)], names=["date", "vt_symbol"])
    close_prices = positions.set_index(["date", "vt_symbol"]).close_price
    result = positions.copy()
    result["pre_close"] = close_prices.reindex(keys).fillna(0).to_numpy(dtype=float)
    return result


def main():
    spec = importlib.util.spec_from_file_location("zero_trade_batch", ROOT / "tools/stage004_label_batch.py")
    batch = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(batch)
    base, runner = batch.configured()
    root = batch.OUTPUT / "jobs" / EVENT_ID
    if (root / "label.json").exists() or (batch.OUTPUT / "run.lock").exists():
        raise RuntimeError("already_analyzed_or_batch_active")
    failed = json.loads((root / "failure.json").read_text())
    if failed["error"] != "daily_calendar_mismatch":
        raise RuntimeError("unexpected_failure")
    manifest = json.loads((batch.OUTPUT / "input_manifest.json").read_text())
    runner.validate_current_input_manifest(manifest)
    jobs = [job for job in batch.read_plan()["jobs"] if job["event_id"] == EVENT_ID]
    if len(jobs) != 1:
        raise RuntimeError("job_not_unique")
    job = jobs[0]
    receipt = json.loads((root / "receipt.json").read_text())
    for name, identity in receipt["frames"].items():
        if runner._file_identity(root / f"{name}.csv") != identity:
            raise RuntimeError("raw_artifact_changed")
    reference = {name: batch.read_frame(batch.REFERENCE / f"{name}.csv") for name in ("daily", "trades", "positions", "entry_candidates")}
    dates = reference["daily"].loc[reference["daily"].date.le(job["end_date"]), "date"].tolist()
    normalized = normalize_zero_trade(batch.read_frame(root / "daily.csv"), batch.read_frame(root / "positions.csv"),
                                      batch.read_frame(root / "trades.csv"), dates, reference["daily"].columns.tolist())
    normalized_positions = normalize_zero_positions(batch.read_frame(root / "positions.csv"))
    original_read = batch.read_frame
    def read_view(path):
        if Path(path) == root / "daily.csv":
            return normalized.copy()
        if Path(path) == root / "positions.csv":
            return normalized_positions.copy()
        return original_read(path)
    batch.read_frame = read_view
    try:
        label = batch.validate_job(job, root, manifest, reference)
    finally:
        batch.read_frame = original_read
    sources = [Path(__file__).resolve(), CONTRACT, ROOT / "tests/test_stage004b_zero_trade_analysis.py",
               root / "failure.json", root / "receipt.json", batch.OUTPUT / "batches/0001/summary.json"]
    identities = {str(path): runner._file_identity(path) for path in sources}
    normalized_path = root / "normalized_daily.csv"
    with normalized_path.open("x") as stream:
        normalized.to_csv(stream, index=False, float_format="%.17g")
    archiver = batch.load("zero_trade_archiver", batch.V4 / "tools/stage006_prefix_equivalence.py")
    normalized_archive = archiver.archive_csv(normalized_path, runner._file_identity(normalized_path))
    position_path = root / "normalized_positions.csv"
    with position_path.open("x") as stream:
        normalized_positions.to_csv(stream, index=False, float_format="%.17g")
    positions_archive = archiver.archive_csv(position_path, runner._file_identity(position_path))
    archives = {name: archiver.archive_csv(root / f"{name}.csv", identity) for name, identity in receipt["frames"].items()}
    batch.write_json(root / "archive_receipt.json", archives)
    evidence = {"status": "passed", "event_id": EVENT_ID, "reason": "engine_zero_trade_early_return_with_complete_zero_position_ledger",
                "normalized_daily": normalized_archive, "normalized_positions": positions_archive,
                "daily_row_count": len(normalized), "source_identities": identities,
                "new_replay_count": 0, "reviewer_started": False}
    batch.write_json(root / "normalization_receipt.json", evidence)
    label["analysis_normalization_sha256"] = batch.digest(root / "normalization_receipt.json")
    label["analysis_tool_sha256"] = batch.digest(Path(__file__).resolve())
    batch.write_json(root / "label.json", label)
    completed = [batch.verify_completed(item, batch.OUTPUT / "jobs" / item["event_id"], manifest)
                 for item in batch.read_plan()["jobs"] if item["event_id"] in batch.read_plan()["canary_event_ids"]]
    runner.validate_current_input_manifest(manifest)
    summary = {"stage": "stage004b_zero_trade_analysis", "status": "passed", "canary_completed": len(completed),
               "original_batch_status": "failed", "original_failure_retained": True, "new_replay_count": 0,
               "additional_label_count": 1, "model_fit_count": 0, "reviewer_started": False,
               "normalization_receipt_sha256": batch.digest(root / "normalization_receipt.json"), "marginal": label["marginal"]}
    batch.write_json(batch.OUTPUT / "batches/0001/recovery_summary.json", summary)
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
