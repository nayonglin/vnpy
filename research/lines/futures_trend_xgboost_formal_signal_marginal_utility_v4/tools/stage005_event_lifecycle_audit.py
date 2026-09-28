from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "artifacts/stage004_counterfactual_validation/workers/A"
OUTPUT = ROOT / "artifacts/stage005_event_lifecycle_audit"
CONTRACT = ROOT / "stages/20260905_2007_stage005_lifecycle_audit_contract.md"
PRODUCTION = ROOT.parents[2].parent / "vnpy_production_live"
IDENTITY_COLUMNS = ["event_id", "candidate_index", "decision_date", "decision_datetime", "product_vt_symbol",
                    "contract_vt_symbol", "direction", "signal", "formal_release_id", "analysis_start", "analysis_end"]


def file_identity(path):
    path = Path(path).resolve(strict=True)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return {"path": str(path), "size": path.stat().st_size, "sha256": digest.hexdigest()}


def reconcile_positions(trades, positions):
    if trades.trade_id.isna().any() or trades.trade_id.duplicated().any():
        raise RuntimeError("trade_identity_invalid")
    expected_signed = trades.direction.map({"Long": 1, "Short": -1}) * trades.volume
    if (not np.isfinite(trades[["volume", "signed_volume"]].to_numpy()).all()
            or trades.volume.le(0).any() or expected_signed.isna().any()
            or not expected_signed.eq(trades.signed_volume).all()):
        raise RuntimeError("trade_quantity_invalid")
    keys = ["date", "vt_symbol"]
    if positions.duplicated(keys).any() or not np.isfinite(positions[["start_pos", "end_pos"]].to_numpy()).all():
        raise RuntimeError("position_identity_invalid")
    fills = trades.groupby(keys).signed_volume.sum().rename("signed_fills")
    ledger = positions.set_index(keys).join(fills, how="outer")
    if ledger[["start_pos", "end_pos"]].isna().any().any():
        raise RuntimeError("position_reconciliation_missing_row")
    error = ledger.end_pos - ledger.start_pos - ledger.signed_fills.fillna(0)
    maximum = float(error.abs().max())
    ordered = positions.sort_values(["vt_symbol", "date"])
    previous = ordered.groupby("vt_symbol").end_pos.shift().fillna(0)
    if maximum != 0 or not ordered.start_pos.eq(previous).all():
        raise RuntimeError("position_reconciliation_failed")
    return {"max_abs_position_error": maximum, "position_row_count": len(positions), "trade_count": len(trades)}


def event_lifecycle(target, candidates, trades, exposure, calendar):
    date = target["decision_date"]
    next_roots = candidates[
        candidates.product_vt_symbol.eq(target["product_vt_symbol"])
        & candidates.entry_context.eq("flat_entry") & candidates.candidate_status.eq("opened")
        & candidates.candidate_index.gt(int(target["candidate_index"]))
    ]
    next_date = next_roots.date.min() if len(next_roots) else "9999-12-31"
    result = {"event_id": target["event_id"], "next_root_decision_date": next_date if len(next_roots) else None,
              "root_trade_id": None, "first_fill_date": None, "end_date": None}
    if next_date <= date:
        return {**result, "status": "unresolved_root_order"}
    # Daily matching precedes that day's closing-signal decisions in Stage502.
    opens = trades[
        trades.vt_symbol.eq(target["contract_vt_symbol"])
        & trades.direction.eq("Long" if target["direction"] == "long" else "Short")
        & trades.offset.eq("Open") & trades.date.gt(date) & trades.date.le(next_date)
    ].sort_values("date", kind="stable")
    if opens.empty:
        status = "right_censored_pending_entry" if date == calendar[-1] else "unresolved_no_root_fill"
        return {**result, "status": status}
    first = opens.iloc[0]
    first_date = str(first["date"])
    result.update(root_trade_id=str(first["trade_id"]), first_fill_date=first_date)
    observed = exposure.reindex([day for day in calendar if day >= first_date])
    closed = observed[observed.eq(0)]
    end = str(closed.index.min()) if len(closed) else calendar[-1]
    if observed.loc[:end].isna().any():
        return {**result, "status": "unresolved_position_coverage"}
    if end > next_date:
        return {**result, "status": "unresolved_root_overlap"}
    if closed.empty:
        return {**result, "status": "right_censored_open"}
    return {**result, "status": "mature", "end_date": end}


def load_inputs():
    receipt_path = SOURCE / "receipt.json"
    receipt = json.loads(receipt_path.read_text())
    if receipt["status"] != "passed" or receipt["arm"] != "A":
        raise RuntimeError("baseline_receipt_invalid")
    names = ["root_features", "entry_candidates", "trades", "positions", "daily"]
    source_paths = [receipt_path, Path(__file__).resolve(), ROOT / "tests/test_stage005_event_lifecycle_audit.py", CONTRACT,
                    PRODUCTION / "examples/portfolio_backtesting/analyze_qmt_roll_stage502_confirmed_daily_next_real_open_replay.py",
                    ROOT / "artifacts/stage004b_frozen_artifact_analysis/summary.json"]
    for name in names:
        path = SOURCE / f"{name}.csv"
        identity = file_identity(path)
        if any(identity[key] != receipt["frames"][name][key] for key in identity):
            raise RuntimeError(f"baseline_frame_changed:{name}")
        source_paths.append(path)
    roots = pd.read_csv(SOURCE / "root_features.csv", usecols=IDENTITY_COLUMNS)
    candidates = pd.read_csv(SOURCE / "entry_candidates.csv", usecols=["candidate_index", "date", "product_vt_symbol",
        "contract_vt_symbol", "direction", "signal", "entry_context", "candidate_status"])
    trades = pd.read_csv(SOURCE / "trades.csv", usecols=["trade_id", "order_id", "datetime", "date", "vt_symbol",
        "direction", "offset", "volume", "signed_volume"], float_precision="round_trip")
    for column, mapping in {
        "direction": {"\u591a": "Long", "\u7a7a": "Short", "Long": "Long", "Short": "Short"},
        "offset": {"\u5f00": "Open", "\u5e73": "Close", "\u5e73\u4eca": "CloseToday", "\u5e73\u6628": "CloseYesterday",
                   "Open": "Open", "Close": "Close", "CloseToday": "CloseToday", "CloseYesterday": "CloseYesterday"},
    }.items():
        trades[column] = trades[column].map(mapping)
        if trades[column].isna().any():
            raise RuntimeError(f"unknown_trade_enum:{column}")
    positions = pd.read_csv(SOURCE / "positions.csv", usecols=["date", "vt_symbol", "start_pos", "end_pos"])
    calendar = pd.read_csv(SOURCE / "daily.csv", usecols=["date"]).date.tolist()
    if calendar != sorted(set(calendar)):
        raise RuntimeError("calendar_invalid")
    mapping = receipt["contract_products"]
    return roots, candidates, trades, positions, calendar, mapping, source_paths


def audit(roots, candidates, trades, positions, calendar, mapping):
    if (len(roots) != 161 or roots.event_id.duplicated().any() or roots.candidate_index.duplicated().any()
            or roots.product_vt_symbol.eq("fu.SHFE").any()):
        raise RuntimeError("root_identity_invalid")
    reconciliation = reconcile_positions(trades, positions)
    positions = positions.assign(product=positions.vt_symbol.map(mapping), absolute_position=positions.end_pos.abs())
    trades = trades.assign(product=trades.vt_symbol.map(mapping))
    if positions["product"].isna().any() or trades["product"].isna().any():
        raise RuntimeError("contract_product_mapping_missing")
    exposures = positions.groupby(["product", "date"]).absolute_position.sum()
    rows = []
    for target in roots.sort_values(["decision_datetime", "event_id"], kind="stable").to_dict("records"):
        match = candidates[candidates.candidate_index.eq(target["candidate_index"])]
        if len(match) != 1:
            raise RuntimeError("candidate_identity_missing")
        actual = match.iloc[0]
        fields = ["product_vt_symbol", "contract_vt_symbol", "direction", "signal"]
        if (any(actual[field] != target[field] for field in fields) or actual["date"] != target["decision_date"]
                or actual["entry_context"] != "flat_entry" or actual["candidate_status"] != "opened"):
            raise RuntimeError("candidate_identity_mismatch")
        result = event_lifecycle(target, candidates, trades, exposures.loc[target["product_vt_symbol"]], calendar)
        if result["status"] == "mature":
            family = trades[trades["product"].eq(target["product_vt_symbol"])
                            & trades.date.between(result["first_fill_date"], result["end_date"])]
            result["family_contract_count"] = int(family.vt_symbol.nunique())
            result["retry_trade_count"] = int(family.order_id.str.contains(".stage847_c9.", regex=False).sum())
        rows.append({**target, **result})
    frame = pd.DataFrame(rows)
    if frame.root_trade_id.dropna().duplicated().any():
        raise RuntimeError("root_fill_reused")
    return frame, reconciliation


def main():
    if OUTPUT.exists():
        raise RuntimeError("audit_output_already_exists")
    *inputs, source_paths = load_inputs()
    identities = {str(path.resolve()): file_identity(path) for path in source_paths}
    frame, reconciliation = audit(*inputs)
    unresolved = frame.status.str.startswith("unresolved").any()
    for path, identity in identities.items():
        if file_identity(path) != identity:
            raise RuntimeError("audit_source_drift")
    OUTPUT.mkdir(mode=0o700)
    with (OUTPUT / "event_lifecycles.csv").open("x") as stream:
        frame.to_csv(stream, index=False)
    summary = {"stage": "stage005_event_lifecycle_audit", "status": "failed" if unresolved else "passed",
               "event_count": len(frame), "status_counts": frame.status.value_counts().to_dict(),
               "source_identities": identities, "reconciliation": reconciliation,
               "event_lifecycle_file": file_identity(OUTPUT / "event_lifecycles.csv"),
               "additional_replay_count": 0, "additional_label_count": 0, "model_fit_count": 0,
               "reviewer_started": False, "label_batch_qualified": not bool(unresolved)}
    with (OUTPUT / "summary.json").open("x") as stream:
        json.dump(summary, stream, ensure_ascii=False, indent=2)
    print(json.dumps({k: v for k, v in summary.items() if k != "source_identities"}), flush=True)
    return int(unresolved)


if __name__ == "__main__":
    raise SystemExit(main())
