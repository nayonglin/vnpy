#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime
import json
import math
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

import pandas as pd


ARTIFACT_TEXT_FIELDS = {
    "action",
    "combo_variant",
    "direction",
    "exchange",
    "label",
    "offset",
    "orderid",
    "product",
    "profile",
    "start_month",
    "status",
    "symbol",
    "variant",
    "vt_orderid",
    "vt_symbol",
}


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    return value


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"official_shadow_json_invalid:{path}:{exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"official_shadow_json_root_invalid:{path}")
    return payload


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    try:
        return pd.read_csv(
            path,
            encoding="utf-8-sig",
            keep_default_na=False,
            dtype={field: str for field in ARTIFACT_TEXT_FIELDS},
        )
    except UnicodeDecodeError:
        try:
            return pd.read_csv(
                path,
                keep_default_na=False,
                dtype={field: str for field in ARTIFACT_TEXT_FIELDS},
            )
        except pd.errors.EmptyDataError:
            return pd.DataFrame()
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _target_rows(frame: pd.DataFrame, target_date: str) -> pd.DataFrame:
    if frame.empty or "date" not in frame.columns:
        return frame.iloc[0:0].copy()
    normalized = frame.copy()
    normalized["date"] = pd.to_datetime(
        normalized["date"], errors="coerce"
    ).dt.strftime("%Y-%m-%d")
    return normalized[normalized["date"].eq(target_date)].reset_index(drop=True)


def _canonical_artifact_value(value: Any) -> Any:
    safe = _json_safe(value)
    if safe is None or safe == "":
        return None
    if isinstance(safe, dict):
        return {
            str(key): _canonical_artifact_value(item)
            for key, item in sorted(safe.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(safe, list):
        return [_canonical_artifact_value(item) for item in safe]
    if isinstance(safe, float):
        if not math.isfinite(safe):
            raise ValueError("canonical_c9_stage901_artifact_nonfinite_number")
        if safe.is_integer():
            return int(safe)
    return safe


def _canonical_record_value(field: str, value: Any) -> Any:
    canonical = _canonical_artifact_value(value)
    if field in ARTIFACT_TEXT_FIELDS and canonical is not None:
        return str(canonical)
    if field != "datetime" or canonical is None:
        return canonical
    try:
        timestamp = pd.Timestamp(canonical)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"canonical_c9_stage901_datetime_invalid:{canonical}"
        ) from exc
    if pd.isna(timestamp):
        raise ValueError("canonical_c9_stage901_datetime_invalid:NaT")
    return timestamp.isoformat()


def _canonical_records(value: Any, *, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError(f"canonical_c9_stage901_{label}_records_invalid")
    records: list[dict[str, Any]] = []
    for index, record in enumerate(value):
        if not isinstance(record, dict):
            raise ValueError(
                f"canonical_c9_stage901_{label}_record_invalid:{index}"
            )
        records.append(
            {
                str(field): _canonical_record_value(str(field), item)
                for field, item in sorted(
                    record.items(),
                    key=lambda pair: str(pair[0]),
                )
            }
        )
    return records


def _require_count(decision: dict[str, Any], field: str, actual: int) -> None:
    declared = decision.get(field)
    if type(declared) is not int or declared != actual:
        raise ValueError(
            f"canonical_c9_stage901_{field}_mismatch:{declared}!={actual}"
        )


def _validate_production_authority(
    *,
    repo_root: Path,
    state_root: Path,
    target_date: str,
    stage945: Any,
) -> dict[str, Any]:
    if state_root != stage945.PRODUCTION_STATE_ROOT.resolve(strict=True):
        raise ValueError("production_authority_state_root_noncanonical")
    stage945._assert_stable_deploy_root()
    manifest = _read_json(state_root / "release-manifest.json")
    qualification = _read_json(
        state_root / "qualification-bundle" / "qualification.json"
    )
    activation = _read_json(state_root / "activation" / "latest.json")
    receipt = _read_json(state_root / "data-readiness" / "latest.json")
    head = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.strip()
    source_commit = str(manifest.get("source_commit", ""))
    manifest_sha256 = str(manifest.get("manifest_sha256", ""))
    if not source_commit or head != source_commit:
        raise ValueError(
            f"production_authority_stable_head_mismatch:{head}!={source_commit}"
        )
    validated_manifest = stage945._validate_release_and_receipt(
        release_manifest=stage945.PRODUCTION_RELEASE_MANIFEST,
        activation_receipt=stage945.PRODUCTION_ACTIVATION_RECEIPT,
        runtime_root=stage945.PRODUCTION_RUNTIME_ROOT,
    )
    stage945._validate_code_qualification(manifest=validated_manifest)
    surface_valid, surface_blocker = (
        stage945._validate_current_owned_launchd_surface()
    )
    if not surface_valid:
        raise ValueError(
            f"production_authority_owned_launchd_surface_invalid:{surface_blocker}"
        )
    activation_valid, activation_blocker = (
        stage945._validate_activation_success_barrier(
            expected_source_commit=source_commit,
            expected_manifest_sha256=manifest_sha256,
        )
    )
    if not activation_valid:
        raise ValueError(
            f"production_authority_activation_barrier_invalid:{activation_blocker}"
        )
    for label, payload in (
        ("qualification", qualification),
        ("activation", activation),
        ("daily_receipt", receipt),
    ):
        if str(payload.get("source_commit", "")) != source_commit:
            raise ValueError(f"production_authority_{label}_source_commit_mismatch")
    for label, payload in (("activation", activation), ("daily_receipt", receipt)):
        if str(payload.get("manifest_sha256", "")) != manifest_sha256:
            raise ValueError(f"production_authority_{label}_manifest_mismatch")
    if activation.get("status") != "production_launchd_activated_no_ctp_connection":
        raise ValueError("production_authority_activation_status_invalid")
    for field in (
        "ctp_connection_attempted_count",
        "send_order_api_called_count",
        "cancel_order_api_called_count",
        "order_api_called_count",
    ):
        if activation.get(field) != 0:
            raise ValueError(f"production_authority_activation_{field}_invalid")
    if (
        manifest.get("execution_profile") != "c9-15w"
        or qualification.get("execution_profile") != "c9-15w"
        or manifest.get("capital") != 150000
        or qualification.get("capital") != 150000
        or str(manifest.get("capital_label", "")) != "15w"
        or str(qualification.get("capital_label", "")) != "15w"
    ):
        raise ValueError("production_authority_profile_identity_invalid")
    if str(receipt.get("target_cutoff_date", "")) != target_date:
        raise ValueError(
            "production_authority_daily_receipt_target_mismatch:"
            f"{receipt.get('target_cutoff_date', '')}!={target_date}"
        )
    stage945.load_and_validate_production_daily_data_receipt(
        stage945.PRODUCTION_DAILY_DATA_RECEIPT,
        declared_data_link=stage945.PRODUCTION_DATA_LINK,
        expected_data_root=stage945.PRODUCTION_DATA_ROOT,
        source_commit=source_commit,
        manifest_sha256=manifest_sha256,
        target_cutoff_date=target_date,
        production_database_path=stage945.PRODUCTION_DATABASE_PATH,
        signal_input_root=stage945.PRODUCTION_SIGNAL_INPUT_ROOT,
        official_ai_eligibility_path=stage945.PRODUCTION_AI_ELIGIBILITY_PATH,
    )
    return {
        "stable_head": head,
        "manifest_sha256": manifest_sha256,
        "activation_status": activation["status"],
        "daily_receipt_target": receipt["target_cutoff_date"],
        "qualification_evidence_id": qualification["evidence_sha256"],
        "owned_launchd_surface": "exact",
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export canonical C9/15w Stage901 shadow evidence."
    )
    parser.add_argument(
        "--repo-root",
        default="/Users/bytedance/Desktop/person/vnpy_production_live",
    )
    parser.add_argument("--target-date", required=True)
    parser.add_argument(
        "--state-root",
        default=(
            "/Users/bytedance/Library/Application Support/"
            "qmt-roll-stage179/production-live"
        ),
    )
    parser.add_argument(
        "--output-dir",
        default=(
            "/Users/bytedance/Library/Application Support/"
            "qmt-roll-stage179/readonly-audits"
        ),
    )
    parser.add_argument(
        "--output-prefix",
        default="qmt_roll_c9_15w_official_shadow_audit",
    )
    args = parser.parse_args()

    target_date = datetime.strptime(args.target_date, "%Y-%m-%d").date().isoformat()
    repo_root = Path(args.repo_root).expanduser().resolve(strict=True)
    state_root = Path(args.state_root).expanduser().resolve(strict=True)
    project_dir = repo_root / "examples" / "portfolio_backtesting"
    if not project_dir.is_dir():
        raise FileNotFoundError(f"missing portfolio_backtesting dir: {project_dir}")
    os.chdir(repo_root)
    sys.path.insert(0, str(project_dir))
    sys.path.insert(0, str(repo_root))

    import run_qmt_roll_stage945_official_live_production_session_launcher as stage945  # noqa: WPS433
    import analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow as stage901  # noqa: WPS433
    from qmt_roll_official_execution_profile import (  # noqa: WPS433
        C9_15W_PROFILE,
        assert_profile_identity,
    )
    authority = _validate_production_authority(
        repo_root=repo_root,
        state_root=state_root,
        target_date=target_date,
        stage945=stage945,
    )

    decision_path = Path(C9_15W_PROFILE.summary_path)
    pending_path = Path(C9_15W_PROFILE.pending_orders_path)
    signal_path = Path(C9_15W_PROFILE.signal_plan_path)
    positions_path = Path(C9_15W_PROFILE.current_positions_path)
    for required in (decision_path, pending_path, signal_path, positions_path):
        if not required.exists():
            raise FileNotFoundError(
                f"canonical_c9_stage901_artifact_missing:{required}"
            )

    decision = _read_json(decision_path)
    if decision.get("execution_profile") != C9_15W_PROFILE.profile_key:
        raise ValueError("canonical_c9_stage901_execution_profile_mismatch")
    assert_profile_identity(
        C9_15W_PROFILE,
        official_version=decision.get("official_live_version"),
        capital=decision.get("capital"),
        capital_label=decision.get("capital_label"),
    )
    if str(decision.get("analysis_end", "")) != target_date:
        raise ValueError(
            "canonical_c9_stage901_target_date_mismatch:"
            f"{decision.get('analysis_end', '')}!={target_date}"
        )
    if str(decision.get("latest_available_data_date", "")) != target_date:
        raise ValueError(
            "canonical_c9_stage901_latest_data_date_mismatch:"
            f"{decision.get('latest_available_data_date', '')}!={target_date}"
        )
    if decision.get("order_api_called") is not False:
        raise ValueError("canonical_c9_stage901_order_api_evidence_invalid")
    for field_name in (
        "send_order_api_called_count",
        "cancel_order_api_called_count",
    ):
        if type(decision.get(field_name)) is not int or decision[field_name] != 0:
            raise ValueError(
                f"canonical_c9_stage901_{field_name}_invalid"
            )

    pending_orders = _read_csv(pending_path)
    signal_plan = _read_csv(signal_path)
    current_positions = _read_csv(positions_path)
    _require_count(decision, "pending_order_count", len(pending_orders))
    _require_count(decision, "target_signal_count", len(signal_plan))
    _require_count(decision, "current_position_count", len(current_positions))
    embedded_pending = _canonical_records(
        decision.get("pending_orders"),
        label="pending_orders",
    )
    published_pending = _canonical_records(
        pending_orders.to_dict(orient="records"),
        label="published_pending_orders",
    )
    if embedded_pending != published_pending:
        raise ValueError("canonical_c9_stage901_pending_orders_snapshot_mismatch")
    trade_events = _read_csv(Path(stage901.TRADE_EVENTS_PATH))
    entry_candidates = _read_csv(Path(stage901.ENTRY_CANDIDATES_PATH))
    target_events = _target_rows(trade_events, target_date)
    target_candidates = _target_rows(entry_candidates, target_date)
    opened_candidates = (
        target_candidates[
            target_candidates["candidate_status"].astype(str).eq("opened")
        ].reset_index(drop=True)
        if not target_candidates.empty
        and "candidate_status" in target_candidates.columns
        else target_candidates.iloc[0:0].copy()
    )
    target_close_events = (
        target_events[target_events["offset"].astype(str).str.lower().eq("close")]
        .reset_index(drop=True)
        if not target_events.empty and "offset" in target_events.columns
        else target_events.iloc[0:0].copy()
    )

    output_dir = Path(args.output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{args.output_prefix}_{target_date.replace('-', '')}"
    paths = {
        "summary": output_dir / f"{stem}_summary.json",
        "pending_orders": output_dir / f"{stem}_pending_orders.csv",
        "signal_plan": output_dir / f"{stem}_signal_plan.csv",
        "target_events": output_dir / f"{stem}_target_events.csv",
        "target_entry_candidates": (
            output_dir / f"{stem}_target_entry_candidates.csv"
        ),
        "current_positions": output_dir / f"{stem}_current_positions.csv",
    }
    pending_orders.to_csv(paths["pending_orders"], index=False, encoding="utf-8-sig")
    signal_plan.to_csv(paths["signal_plan"], index=False, encoding="utf-8-sig")
    target_events.to_csv(paths["target_events"], index=False, encoding="utf-8-sig")
    target_candidates.to_csv(
        paths["target_entry_candidates"], index=False, encoding="utf-8-sig"
    )
    current_positions.to_csv(
        paths["current_positions"], index=False, encoding="utf-8-sig"
    )

    summary = {
        "execution_profile": C9_15W_PROFILE.profile_key,
        "official_live_version": C9_15W_PROFILE.official_version,
        "capital": C9_15W_PROFILE.capital,
        "capital_label": C9_15W_PROFILE.capital_label,
        "target_date": target_date,
        "production_authority": authority,
        "risk_snapshot": decision.get("risk_snapshot", {}),
        "live_stop_alignment": decision.get("live_stop_alignment", {}),
        "pending_order_count": int(len(pending_orders)),
        "signal_plan_count": int(len(signal_plan)),
        "target_event_count": int(len(target_events)),
        "target_close_event_count": int(len(target_close_events)),
        "target_entry_candidate_count": int(len(target_candidates)),
        "target_opened_candidate_count": int(len(opened_candidates)),
        "current_position_count": int(len(current_positions)),
        "pending_orders": pending_orders.to_dict(orient="records"),
        "signal_plan": signal_plan.to_dict(orient="records"),
        "target_close_events": target_close_events.to_dict(orient="records"),
        "target_opened_candidates": opened_candidates.to_dict(orient="records"),
        "target_entry_candidates": target_candidates.to_dict(orient="records"),
        "current_positions": current_positions.to_dict(orient="records"),
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "order_api_called_count": 0,
        "note": (
            "Stage901 canonical pending_orders are the primary next-session "
            "theoretical action list; no broker order API was called."
        ),
        "source_artifacts": {
            "decision": str(decision_path),
            "pending_orders": str(pending_path),
            "signal_plan": str(signal_path),
            "current_positions": str(positions_path),
        },
        "outputs": {key: str(path) for key, path in paths.items()},
    }
    safe_summary = _json_safe(summary)
    paths["summary"].write_text(
        json.dumps(
            safe_summary,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            safe_summary,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )
    )


if __name__ == "__main__":
    main()
