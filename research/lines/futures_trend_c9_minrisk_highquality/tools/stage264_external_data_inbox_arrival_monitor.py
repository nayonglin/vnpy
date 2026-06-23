from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage264"
MODEL_TAG = "stage264_external_data_inbox_arrival_monitor_v1"
OUTPUT_PREFIX = "qmt_roll_stage264_c9_minrisk_external_data_inbox_arrival_monitor"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage264_external_data_inbox_arrival_monitor"

STAGE135_DIR = LINE_DIR / "outputs" / "stage135_wave0_real_drop_operator_pack"
STAGE251_DIR = LINE_DIR / "outputs" / "stage251_dd30_account_floor_true_engine"
STAGE261_REPLAY_DIR = LINE_DIR / "outputs" / "stage261_execution_replay_import_acceptance_packet"
STAGE263_DIR = LINE_DIR / "outputs" / "stage263_external_data_arrival_supergate_audit"

STAGE135_PREFIX = "qmt_roll_stage135_c9_minrisk_wave0_real_drop_operator_pack"
STAGE251_PREFIX = "qmt_roll_stage251_c9_minrisk_dd30_account_floor_true_engine"
STAGE261_REPLAY_PREFIX = "qmt_roll_stage261_c9_minrisk_execution_replay_import_acceptance_packet"
STAGE263_PREFIX = "qmt_roll_stage263_c9_minrisk_external_data_arrival_supergate_audit"

STAGE135_TAG = "stage135_wave0_real_drop_operator_pack_v1"
STAGE251_TAG = "stage251_dd30_account_floor_true_engine_v1"
STAGE261_REPLAY_TAG = "stage261_execution_replay_import_acceptance_packet_v1"
STAGE263_TAG = "stage263_external_data_arrival_supergate_audit_v1"

STAGE135_CANDIDATE_DIRS_IN = STAGE135_DIR / f"{STAGE135_PREFIX}_candidate_drop_dir_audit_{STAGE135_TAG}.csv"
STAGE135_COMMAND_IN = STAGE135_DIR / f"{STAGE135_PREFIX}_operator_command_manifest_{STAGE135_TAG}.csv"
STAGE251_CURVE_IN = STAGE251_DIR / f"{STAGE251_PREFIX}_curve_{STAGE251_TAG}.csv"
STAGE251_SUMMARY_IN = STAGE251_DIR / f"{STAGE251_PREFIX}_summary_{STAGE251_TAG}.csv"
STAGE261_REPLAY_MANIFEST_IN = STAGE261_REPLAY_DIR / f"{STAGE261_REPLAY_PREFIX}_manifest_template_{STAGE261_REPLAY_TAG}.csv"
STAGE261_REPLAY_SUMMARY_IN = STAGE261_REPLAY_DIR / f"{STAGE261_REPLAY_PREFIX}_summary_{STAGE261_REPLAY_TAG}.csv"
STAGE263_ROUTE_IN = STAGE263_DIR / f"{STAGE263_PREFIX}_route_supergate_{STAGE263_TAG}.csv"
STAGE263_DECISION_TREE_IN = STAGE263_DIR / f"{STAGE263_PREFIX}_arrival_decision_tree_{STAGE263_TAG}.csv"

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
WATCH_ROOTS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_watch_roots_{MODEL_TAG}.csv"
PACKAGE_INVENTORY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_package_inventory_{MODEL_TAG}.csv"
ROLE_PRESENCE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_role_presence_{MODEL_TAG}.csv"
TRIGGER_GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trigger_gate_{MODEL_TAG}.csv"
NEXT_ACTION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_next_action_queue_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_inbox_status_{MODEL_TAG}.png"
WATCH_ROOT_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_watch_root_matrix_{MODEL_TAG}.png"
PACKAGE_ROLE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_package_role_heatmap_{MODEL_TAG}.png"
TRIGGER_GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trigger_gate_chart_{MODEL_TAG}.png"
NEXT_ACTION_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_next_action_chart_{MODEL_TAG}.png"

W0_EXPECTED_REQUEST_COUNT = 41
W0_EXPECTED_FILE_COUNT = 123
REPLAY_EXPECTED_ENTRY_COUNT = 219


def _read_csv(path: Path, required: bool = True) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size <= 4:
        if required:
            raise RuntimeError(f"missing required input: {path}")
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        number = float(value)
        return number if np.isfinite(number) else None
    if isinstance(value, (pd.Timestamp, datetime)):
        if pd.isna(value):
            return None
        return pd.Timestamp(value).strftime("%Y-%m-%d %H:%M:%S")
    if pd.isna(value):
        return None
    return value


def _row(frame: pd.DataFrame) -> dict[str, Any]:
    return frame.iloc[0].to_dict() if not frame.empty else {}


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if pd.isna(value):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if np.isfinite(number) else default


def _get(row: dict[str, Any], *keys: str, default: Any = 0) -> Any:
    for key in keys:
        if key in row and not pd.isna(row[key]):
            return row[key]
    return default


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    for column in data.columns:
        if pd.api.types.is_float_dtype(data[column]):
            data[column] = data[column].map(lambda value: "" if pd.isna(value) else f"{value:.4f}")
    lines = [
        "| " + " | ".join(str(column) for column in data.columns) + " |",
        "| " + " | ".join(["---"] * len(data.columns)) + " |",
    ]
    for _, row in data.iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in data.columns) + " |")
    return "\n".join(lines)


def _official_summary(stage251_summary: pd.DataFrame) -> dict[str, Any]:
    arm = stage251_summary.get("arm", pd.Series(dtype=str)).astype(str)
    official = stage251_summary[arm.eq("A_official_stage847_c9_15w")]
    return _row(official) if not official.empty else _row(stage251_summary)


def _official_curve(stage251_curve: pd.DataFrame) -> pd.DataFrame:
    curve = stage251_curve.copy()
    arm = curve.get("arm", pd.Series(dtype=str)).astype(str)
    official = curve[arm.eq("A_official_stage847_c9_15w")].copy()
    if official.empty:
        official = curve.copy()
    official["date"] = pd.to_datetime(official["date"], errors="coerce")
    for column in ["account_equity", "drawdown_pct"]:
        official[column] = pd.to_numeric(official[column], errors="coerce")
    return official[official["date"].notna()].sort_values("date").reset_index(drop=True)


def _load_inputs() -> dict[str, Any]:
    return {
        "stage135_candidate_dirs": _read_csv(STAGE135_CANDIDATE_DIRS_IN),
        "stage135_command": _read_csv(STAGE135_COMMAND_IN),
        "stage251_curve": _read_csv(STAGE251_CURVE_IN),
        "stage251_summary": _read_csv(STAGE251_SUMMARY_IN),
        "stage261_manifest": _read_csv(STAGE261_REPLAY_MANIFEST_IN),
        "stage261_summary": _row(_read_csv(STAGE261_REPLAY_SUMMARY_IN)),
        "stage263_route": _read_csv(STAGE263_ROUTE_IN),
        "stage263_decision_tree": _read_csv(STAGE263_DECISION_TREE_IN),
    }


def _safe_rglob(root: Path) -> list[Path]:
    if not root.exists() or not root.is_dir():
        return []
    return sorted([path for path in root.rglob("*") if path.is_file()], key=lambda item: str(item))


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_DIR))
    except ValueError:
        return str(path)


def _watch_roots(inputs: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    candidate_dirs = inputs["stage135_candidate_dirs"].copy()
    for _, row in candidate_dirs.iterrows():
        root = Path(str(row["drop_dir"]))
        files = _safe_rglob(root)
        rows.append(
            {
                "route_id": "authorized_orderflow_mbp10_mbo_w0_chain",
                "root_kind": "stage135_w0_drop_candidate",
                "watch_root": str(root),
                "exists": int(root.exists() and root.is_dir()),
                "file_count": len(files),
                "total_bytes": int(sum(path.stat().st_size for path in files)),
                "expected_package_count": 1,
                "detected_package_count": int(len(files) > 0),
                "next_gate_if_present": "Stage125 receipt preflight -> Stage133 release -> Stage117/120/112/113",
            }
        )
    replay_root = LINE_DIR / "incoming" / "execution_replay"
    replay_files = _safe_rglob(replay_root)
    package_dirs = []
    if replay_root.exists() and replay_root.is_dir():
        package_dirs = sorted([path for path in replay_root.iterdir() if path.is_dir()], key=lambda item: str(item))
        if any(path.is_file() for path in replay_root.iterdir()):
            package_dirs = [replay_root] + package_dirs
    rows.append(
        {
            "route_id": "broker_production_execution_replay_chain",
            "root_kind": "stage261_execution_replay_package_root",
            "watch_root": str(replay_root),
            "exists": int(replay_root.exists() and replay_root.is_dir()),
            "file_count": len(replay_files),
            "total_bytes": int(sum(path.stat().st_size for path in replay_files)),
            "expected_package_count": 1,
            "detected_package_count": len(package_dirs),
            "next_gate_if_present": "Stage261 import packet -> Stage260 field/source audit -> Stage141",
        }
    )
    return pd.DataFrame(rows)


def _w0_package_inventory(candidate_dirs: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for _, root_row in candidate_dirs.iterrows():
        root = Path(str(root_row["drop_dir"]))
        files = _safe_rglob(root)
        raw_files = [path for path in files if "raw" in path.name.lower() or "/raw/" in str(path).lower()]
        parquet_files = [path for path in files if path.suffix.lower() == ".parquet"]
        proof_files = [path for path in files if "proof" in path.name.lower() and path.suffix.lower() in {".json", ".jsonl"}]
        manifest_files = [path for path in files if path.name.lower() in {"manifest.csv", "manifest.json"}]
        complete = int(len(raw_files) >= W0_EXPECTED_REQUEST_COUNT and len(parquet_files) >= W0_EXPECTED_REQUEST_COUNT and len(proof_files) >= W0_EXPECTED_REQUEST_COUNT)
        rows.append(
            {
                "route_id": "authorized_orderflow_mbp10_mbo_w0_chain",
                "package_id": root.name,
                "package_path": str(root),
                "exists": int(root.exists() and root.is_dir()),
                "file_count": len(files),
                "total_bytes": int(sum(path.stat().st_size for path in files)),
                "manifest_file_count": len(manifest_files),
                "raw_file_count": len(raw_files),
                "parquet_file_count": len(parquet_files),
                "proof_file_count": len(proof_files),
                "expected_file_count": W0_EXPECTED_FILE_COUNT,
                "role_complete_count": int(len(raw_files) >= W0_EXPECTED_REQUEST_COUNT)
                + int(len(parquet_files) >= W0_EXPECTED_REQUEST_COUNT)
                + int(len(proof_files) >= W0_EXPECTED_REQUEST_COUNT),
                "role_expected_count": 3,
                "package_complete_now": complete,
                "next_gate_command_id": "stage125_then_stage133",
            }
        )
    return rows


def _replay_package_dirs() -> list[Path]:
    replay_root = LINE_DIR / "incoming" / "execution_replay"
    if not replay_root.exists() or not replay_root.is_dir():
        return [replay_root]
    children = sorted([path for path in replay_root.iterdir() if path.is_dir()], key=lambda item: str(item))
    direct_files = [path for path in replay_root.iterdir() if path.is_file()]
    if direct_files:
        return [replay_root] + children
    if children:
        return children
    return [replay_root]


def _file_row_count(path: Path) -> int:
    if not path.exists() or not path.is_file():
        return 0
    if path.suffix.lower() == ".csv":
        try:
            with path.open("rb") as handle:
                return max(sum(1 for _ in handle) - 1, 0)
        except OSError:
            return 0
    if path.suffix.lower() in {".json", ".jsonl", ".ndjson"}:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
            if path.suffix.lower() == ".json":
                payload = json.loads(text or "{}")
                if isinstance(payload, list):
                    return len(payload)
                return 1 if payload else 0
            return len([line for line in text.splitlines() if line.strip()])
        except (OSError, json.JSONDecodeError):
            return 0
    return 1


def _replay_package_inventory(manifest_template: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    role_names = manifest_template["file_role"].astype(str).tolist()
    expected_file_names = dict(zip(manifest_template["file_role"].astype(str), manifest_template["expected_file_name"].astype(str)))
    min_rows = dict(zip(manifest_template["file_role"].astype(str), manifest_template["min_rows"].map(_to_int)))
    for package_dir in _replay_package_dirs():
        files = _safe_rglob(package_dir)
        role_hits: dict[str, int] = {}
        role_row_hits: dict[str, int] = {}
        for role in role_names:
            expected = expected_file_names[role]
            if role == "raw_files":
                raw_root = package_dir / "raw"
                matched = _safe_rglob(raw_root)
                role_hits[role] = int(len(matched) > 0)
                role_row_hits[role] = len(matched)
                continue
            target = package_dir / expected
            role_hits[role] = int(target.exists() and target.is_file())
            role_row_hits[role] = _file_row_count(target) if role_hits[role] else 0
        row_threshold_pass = {
            role: int(role_hits[role] and role_row_hits[role] >= min_rows.get(role, 1))
            for role in role_names
        }
        rows.append(
            {
                "route_id": "broker_production_execution_replay_chain",
                "package_id": package_dir.name,
                "package_path": str(package_dir),
                "exists": int(package_dir.exists() and package_dir.is_dir()),
                "file_count": len(files),
                "total_bytes": int(sum(path.stat().st_size for path in files)),
                "manifest_file_count": role_hits.get("manifest", 0),
                "raw_file_count": role_row_hits.get("raw_files", 0),
                "parquet_file_count": 0,
                "proof_file_count": 0,
                "expected_file_count": len(role_names),
                "role_complete_count": int(sum(row_threshold_pass.values())),
                "role_expected_count": len(role_names),
                "package_complete_now": int(all(row_threshold_pass.values())),
                "next_gate_command_id": "stage261_import_packet",
            }
        )
    return rows


def _package_inventory(inputs: dict[str, Any]) -> pd.DataFrame:
    rows = _w0_package_inventory(inputs["stage135_candidate_dirs"])
    rows.extend(_replay_package_inventory(inputs["stage261_manifest"]))
    frame = pd.DataFrame(rows)
    frame["package_ready_pct"] = np.where(
        frame["role_expected_count"].astype(float) > 0,
        frame["role_complete_count"].astype(float) / frame["role_expected_count"].astype(float) * 100.0,
        np.nan,
    )
    return frame


def _role_presence(inputs: dict[str, Any], package_inventory: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, row in package_inventory.iterrows():
        route_id = str(row["route_id"])
        package_path = Path(str(row["package_path"]))
        if route_id == "authorized_orderflow_mbp10_mbo_w0_chain":
            roles = [
                ("raw", int(row["raw_file_count"] >= W0_EXPECTED_REQUEST_COUNT), row["raw_file_count"], W0_EXPECTED_REQUEST_COUNT),
                ("normalized_parquet", int(row["parquet_file_count"] >= W0_EXPECTED_REQUEST_COUNT), row["parquet_file_count"], W0_EXPECTED_REQUEST_COUNT),
                ("proof_json", int(row["proof_file_count"] >= W0_EXPECTED_REQUEST_COUNT), row["proof_file_count"], W0_EXPECTED_REQUEST_COUNT),
            ]
        else:
            manifest_template = inputs["stage261_manifest"]
            roles = []
            for _, manifest_row in manifest_template.iterrows():
                role = str(manifest_row["file_role"])
                expected = str(manifest_row["expected_file_name"])
                min_row = _to_int(manifest_row["min_rows"])
                if role == "raw_files":
                    observed = len(_safe_rglob(package_path / "raw"))
                else:
                    observed = _file_row_count(package_path / expected)
                roles.append((role, int(observed >= min_row), observed, min_row))
        for role, present_enough, observed, required in roles:
            rows.append(
                {
                    "route_id": route_id,
                    "package_id": row["package_id"],
                    "role": role,
                    "observed_count_or_rows": int(observed),
                    "required_count_or_rows": int(required),
                    "present_enough_for_receipt": int(present_enough),
                }
            )
    return pd.DataFrame(rows)


def _trigger_gate(watch_roots: pd.DataFrame, package_inventory: pd.DataFrame, role_presence: pd.DataFrame) -> pd.DataFrame:
    rows = [
        {
            "gate_id": "no_official_config_or_order_side_effect",
            "required": 1,
            "observed": 1,
            "pass_now": 1,
            "reason": "Stage264 is one-shot read-only inbox monitoring; it does not call CTP/SimNow/order API.",
        },
        {
            "gate_id": "watch_roots_defined",
            "required": 2,
            "observed": int(watch_roots["route_id"].nunique()),
            "pass_now": int(watch_roots["route_id"].nunique() >= 2),
            "reason": "Both W0/orderflow and execution replay watch routes are defined.",
        },
        {
            "gate_id": "any_real_inbox_root_exists",
            "required": 1,
            "observed": int(watch_roots["exists"].sum()),
            "pass_now": int(watch_roots["exists"].sum() >= 1),
            "reason": "At least one real inbox directory exists.",
        },
        {
            "gate_id": "any_package_files_detected",
            "required": 1,
            "observed": int((package_inventory["file_count"] > 0).sum()),
            "pass_now": int((package_inventory["file_count"] > 0).sum() >= 1),
            "reason": "A package with files must exist before route validation can run.",
        },
        {
            "gate_id": "any_manifest_detected",
            "required": 1,
            "observed": int(package_inventory["manifest_file_count"].sum()),
            "pass_now": int(package_inventory["manifest_file_count"].sum() >= 1),
            "reason": "Manifest is required to bind package identity, permission and hashes.",
        },
        {
            "gate_id": "w0_package_ready_for_stage125_133",
            "required": 1,
            "observed": int(
                package_inventory[
                    (package_inventory["route_id"] == "authorized_orderflow_mbp10_mbo_w0_chain")
                    & (package_inventory["package_complete_now"] == 1)
                ].shape[0]
            ),
            "pass_now": int(
                package_inventory[
                    (package_inventory["route_id"] == "authorized_orderflow_mbp10_mbo_w0_chain")
                    & (package_inventory["package_complete_now"] == 1)
                ].shape[0]
                >= 1
            ),
            "reason": "Needs 41 raw + 41 normalized parquet + 41 proof files before Stage125/133.",
        },
        {
            "gate_id": "execution_replay_package_ready_for_stage261",
            "required": 1,
            "observed": int(
                package_inventory[
                    (package_inventory["route_id"] == "broker_production_execution_replay_chain")
                    & (package_inventory["package_complete_now"] == 1)
                ].shape[0]
            ),
            "pass_now": int(
                package_inventory[
                    (package_inventory["route_id"] == "broker_production_execution_replay_chain")
                    & (package_inventory["package_complete_now"] == 1)
                ].shape[0]
                >= 1
            ),
            "reason": "Needs all Stage261 manifest roles and minimum row counts before import validation.",
        },
        {
            "gate_id": "all_detected_roles_present_enough",
            "required": int(len(role_presence)),
            "observed": int(role_presence["present_enough_for_receipt"].sum()) if not role_presence.empty else 0,
            "pass_now": int((not role_presence.empty) and role_presence["present_enough_for_receipt"].sum() == len(role_presence)),
            "reason": "Every role in every detected/expected package must satisfy minimum receipt counts.",
        },
        {
            "gate_id": "strategy_rule_or_true_engine_allowed",
            "required": 1,
            "observed": 0,
            "pass_now": 0,
            "reason": "Inbox detection never creates a trading rule; downstream acceptance remains required.",
        },
    ]
    return pd.DataFrame(rows)


def _next_action(watch_roots: pd.DataFrame, package_inventory: pd.DataFrame) -> pd.DataFrame:
    any_files = int((package_inventory["file_count"] > 0).sum())
    w0_ready = int(
        package_inventory[
            (package_inventory["route_id"] == "authorized_orderflow_mbp10_mbo_w0_chain")
            & (package_inventory["package_complete_now"] == 1)
        ].shape[0]
    )
    replay_ready = int(
        package_inventory[
            (package_inventory["route_id"] == "broker_production_execution_replay_chain")
            & (package_inventory["package_complete_now"] == 1)
        ].shape[0]
    )
    rows = [
        {
            "priority": 1,
            "action_id": "if_execution_replay_ready_run_stage261",
            "condition_now": replay_ready,
            "action": ".py311/bin/python research/lines/futures_trend_c9_minrisk_highquality/tools/stage261_execution_replay_import_acceptance_packet.py with the real package path wired in a future validator",
            "allowed_now": replay_ready,
            "strategy_rule_allowed": 0,
        },
        {
            "priority": 2,
            "action_id": "if_w0_ready_run_stage125_stage133",
            "condition_now": w0_ready,
            "action": "Run Stage125 receipt preflight and Stage133 total release on the complete W0 drop.",
            "allowed_now": w0_ready,
            "strategy_rule_allowed": 0,
        },
        {
            "priority": 3,
            "action_id": "if_partial_files_quarantine_and_report_missing_roles",
            "condition_now": int(any_files > 0 and not (w0_ready or replay_ready)),
            "action": "Keep package quarantined; use role_presence and package_inventory to request missing roles.",
            "allowed_now": int(any_files > 0 and not (w0_ready or replay_ready)),
            "strategy_rule_allowed": 0,
        },
        {
            "priority": 4,
            "action_id": "if_no_files_keep_monitoring_not_rules",
            "condition_now": int(any_files == 0),
            "action": "No external package files detected. Keep waiting for real data; do not resume OHLCV/OI parameter work.",
            "allowed_now": int(any_files == 0),
            "strategy_rule_allowed": 0,
        },
    ]
    return pd.DataFrame(rows)


def _summary(inputs: dict[str, Any], watch_roots: pd.DataFrame, package_inventory: pd.DataFrame, role_presence: pd.DataFrame, trigger_gate: pd.DataFrame) -> pd.DataFrame:
    official = _official_summary(inputs["stage251_summary"])
    route_supergate = inputs["stage263_route"]
    row = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "line_id": LINE_ID,
        "decision": "stage264_external_data_inbox_empty_monitor_ready_no_rule",
        "stage_nature": "read_only_external_data_inbox_arrival_monitor",
        "official_config_changed": 0,
        "strategy_rule_created": 0,
        "true_engine_run": 0,
        "ab_triggered": 0,
        "order_api_called": 0,
        "ctp_or_simnow_connected": 0,
        "watch_root_count": int(len(watch_roots)),
        "watch_root_exists_count": int(watch_roots["exists"].sum()),
        "watch_root_file_count": int(watch_roots["file_count"].sum()),
        "package_candidate_count": int(len(package_inventory)),
        "package_with_files_count": int((package_inventory["file_count"] > 0).sum()),
        "package_complete_count": int(package_inventory["package_complete_now"].sum()),
        "w0_watch_root_count": int((watch_roots["route_id"] == "authorized_orderflow_mbp10_mbo_w0_chain").sum()),
        "w0_complete_package_count": int(
            package_inventory[
                (package_inventory["route_id"] == "authorized_orderflow_mbp10_mbo_w0_chain")
                & (package_inventory["package_complete_now"] == 1)
            ].shape[0]
        ),
        "execution_replay_watch_root_count": int((watch_roots["route_id"] == "broker_production_execution_replay_chain").sum()),
        "execution_replay_complete_package_count": int(
            package_inventory[
                (package_inventory["route_id"] == "broker_production_execution_replay_chain")
                & (package_inventory["package_complete_now"] == 1)
            ].shape[0]
        ),
        "role_presence_row_count": int(len(role_presence)),
        "role_presence_pass_count": int(role_presence["present_enough_for_receipt"].sum()) if not role_presence.empty else 0,
        "trigger_gate_count": int(len(trigger_gate)),
        "trigger_gate_pass_count": int(trigger_gate["pass_now"].sum()),
        "stage263_contract_packet_ready_route_count": int(route_supergate["contract_packet_ready"].sum()) if "contract_packet_ready" in route_supergate else 0,
        "stage263_real_data_supplied_route_count": int((route_supergate["real_external_package_supplied"] > 0).sum()) if "real_external_package_supplied" in route_supergate else 0,
        "strategy_feature_usable": 0,
        "objective_completion_proven": 0,
        "official_end_equity": _to_float(_get(official, "end_equity")),
        "official_total_return_pct": _to_float(_get(official, "total_return_pct")),
        "official_max_dd_pct": _to_float(_get(official, "max_dd_pct", "max_drawdown_pct")),
        "official_sharpe": _to_float(_get(official, "sharpe")),
        "official_total_slippage": _to_float(_get(official, "total_slippage")),
        "official_total_trade_count": _to_float(_get(official, "total_trade_count")),
        "official_win_rate_pct": _to_float(_get(official, "nonzero_daily_win_rate_pct", "closed_lot_win_rate_pct")),
        "official_broker10_peak_pct": _to_float(_get(official, "max_broker10_margin_to_equity_pct")),
        "visual_file_count": 5,
    }
    return pd.DataFrame([row])


def _plot_official_path(curve: pd.DataFrame, summary: pd.DataFrame) -> None:
    row = _row(summary)
    fig, ax1 = plt.subplots(figsize=(12, 6))
    ax1.plot(curve["date"], curve["account_equity"], color="#2f6f73", linewidth=1.8)
    ax1.set_ylabel("Equity")
    ax1.grid(True, alpha=0.25)
    ax2 = ax1.twinx()
    ax2.fill_between(curve["date"], curve["drawdown_pct"], 0, color="#b5533c", alpha=0.25)
    ax2.set_ylabel("Drawdown %")
    ax1.set_title(
        "Stage264 external inbox monitor | "
        f"roots {row['watch_root_exists_count']}/{row['watch_root_count']} | "
        f"complete packages {row['package_complete_count']}"
    )
    ax1.text(
        0.015,
        0.95,
        "Inbox monitor only: no rule / no true engine",
        transform=ax1.transAxes,
        va="top",
        bbox={"facecolor": "white", "edgecolor": "#777777", "alpha": 0.9},
    )
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_watch_roots(watch_roots: pd.DataFrame) -> None:
    columns = ["exists", "detected_package_count", "file_count"]
    data = watch_roots[columns].copy()
    data["file_count"] = (data["file_count"] > 0).astype(int)
    fig, ax = plt.subplots(figsize=(10, 4.6))
    ax.imshow(data.to_numpy(dtype=float), cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(columns)))
    ax.set_xticklabels(columns, rotation=25, ha="right", fontsize=8)
    labels = watch_roots["root_kind"] + "\n" + watch_roots["watch_root"].map(lambda value: Path(str(value)).name)
    ax.set_yticks(range(len(watch_roots)))
    ax.set_yticklabels(labels, fontsize=7)
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            ax.text(j, i, str(int(data.iloc[i, j])), ha="center", va="center", fontsize=8)
    ax.set_title("Watch root matrix")
    fig.tight_layout()
    fig.savefig(WATCH_ROOT_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_role_heatmap(role_presence: pd.DataFrame) -> None:
    if role_presence.empty:
        fig, ax = plt.subplots(figsize=(9, 3))
        ax.axis("off")
        ax.text(0.5, 0.5, "No role rows", ha="center", va="center")
        fig.tight_layout()
        fig.savefig(PACKAGE_ROLE_CHART_OUT, dpi=160)
        plt.close(fig)
        return
    pivot = role_presence.pivot_table(
        index=["route_id", "package_id"],
        columns="role",
        values="present_enough_for_receipt",
        aggfunc="max",
        fill_value=0,
    )
    fig, ax = plt.subplots(figsize=(11, max(3.5, len(pivot) * 0.45 + 1.5)))
    ax.imshow(pivot.to_numpy(dtype=float), cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=35, ha="right", fontsize=8)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels([f"{idx[0]}\n{idx[1]}" for idx in pivot.index], fontsize=7)
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            ax.text(j, i, str(int(pivot.iloc[i, j])), ha="center", va="center", fontsize=8)
    ax.set_title("Package role receipt heatmap")
    fig.tight_layout()
    fig.savefig(PACKAGE_ROLE_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_trigger_gate(trigger_gate: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(10, 4.8))
    colors = np.where(trigger_gate["pass_now"].astype(int) == 1, "#2f6f73", "#b5533c")
    ax.barh(trigger_gate["gate_id"], trigger_gate["observed"].astype(float), color=colors)
    ax.set_xlabel("Observed")
    ax.set_title("Trigger gate status")
    ax.grid(axis="x", alpha=0.25)
    ax.invert_yaxis()
    for i, row in enumerate(trigger_gate.itertuples(index=False)):
        ax.text(float(row.observed) + 0.05, i, f"/ {row.required}", va="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(TRIGGER_GATE_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_next_action(next_action: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(10, 4.8))
    data = next_action.sort_values("priority")
    colors = np.where(data["condition_now"].astype(int) == 1, "#2f6f73", "#c9c9c9")
    ax.barh(data["action_id"], data["condition_now"].astype(int), color=colors)
    ax.set_xlim(0, 1.05)
    ax.set_xlabel("Condition now")
    ax.set_title("Next action queue")
    ax.grid(axis="x", alpha=0.25)
    ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(NEXT_ACTION_CHART_OUT, dpi=160)
    plt.close(fig)


def _report(summary: pd.DataFrame, watch_roots: pd.DataFrame, package_inventory: pd.DataFrame, role_presence: pd.DataFrame, trigger_gate: pd.DataFrame, next_action: pd.DataFrame) -> str:
    row = _row(summary)
    return f"""# Stage264 external data inbox arrival monitor

## Decision

`{row['decision']}`

This stage is a one-shot read-only inbox monitor. It does not create a strategy rule, run true engine, trigger A/B, change official config, connect CTP/SimNow, or call any order API.

## External research judgment

File-arrival tooling should be treated as a trigger, not as data validity proof. Python watchdog and similar filesystem event APIs only report filesystem changes. Airflow sensors formalize periodic waiting and rescheduling. S3 event notifications and Databricks Auto Loader file notification mode show the same engineering pattern: object/file creation can wake a pipeline, but downstream manifest, schema, hash, permission and coverage checks still decide usability.

Sources:
- https://python-watchdog.readthedocs.io/
- https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/sensors.html
- https://docs.aws.amazon.com/AmazonS3/latest/userguide/EventNotifications.html
- https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/

## Summary

- Official A unchanged: equity `{row['official_end_equity']:.2f}`, return `{row['official_total_return_pct']:.4f}%`, maxDD `{row['official_max_dd_pct']:.4f}%`, Sharpe `{row['official_sharpe']:.4f}`, slippage `{row['official_total_slippage']:.0f}`, trades `{row['official_total_trade_count']:.0f}`, win rate `{row['official_win_rate_pct']:.4f}%`.
- Watch roots: `{row['watch_root_exists_count']}/{row['watch_root_count']}` exist.
- Total files under watched roots: `{row['watch_root_file_count']}`.
- Package candidates: `{row['package_candidate_count']}`; with files `{row['package_with_files_count']}`; complete `{row['package_complete_count']}`.
- W0 complete packages: `{row['w0_complete_package_count']}`.
- Execution replay complete packages: `{row['execution_replay_complete_package_count']}`.
- Trigger gate: `{row['trigger_gate_pass_count']}/{row['trigger_gate_count']}`.

## Watch roots

{_md_table(watch_roots[['route_id', 'root_kind', 'watch_root', 'exists', 'file_count', 'detected_package_count', 'next_gate_if_present']], max_rows=20)}

## Package inventory

{_md_table(package_inventory[['route_id', 'package_id', 'exists', 'file_count', 'manifest_file_count', 'raw_file_count', 'parquet_file_count', 'proof_file_count', 'role_complete_count', 'role_expected_count', 'package_complete_now']], max_rows=30)}

## Role presence

{_md_table(role_presence[['route_id', 'package_id', 'role', 'observed_count_or_rows', 'required_count_or_rows', 'present_enough_for_receipt']], max_rows=40)}

## Trigger gate

{_md_table(trigger_gate, max_rows=20)}

## Next action

{_md_table(next_action, max_rows=20)}
"""


def main() -> None:
    inputs = _load_inputs()
    curve = _official_curve(inputs["stage251_curve"])
    watch_roots = _watch_roots(inputs)
    package_inventory = _package_inventory(inputs)
    role_presence = _role_presence(inputs, package_inventory)
    trigger_gate = _trigger_gate(watch_roots, package_inventory, role_presence)
    next_action = _next_action(watch_roots, package_inventory)
    summary = _summary(inputs, watch_roots, package_inventory, role_presence, trigger_gate)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_csv(summary, SUMMARY_OUT)
    _write_csv(watch_roots, WATCH_ROOTS_OUT)
    _write_csv(package_inventory, PACKAGE_INVENTORY_OUT)
    _write_csv(role_presence, ROLE_PRESENCE_OUT)
    _write_csv(trigger_gate, TRIGGER_GATE_OUT)
    _write_csv(next_action, NEXT_ACTION_OUT)

    _plot_official_path(curve, summary)
    _plot_watch_roots(watch_roots)
    _plot_role_heatmap(role_presence)
    _plot_trigger_gate(trigger_gate)
    _plot_next_action(next_action)

    report_text = _report(summary, watch_roots, package_inventory, role_presence, trigger_gate, next_action)
    _write_text(REPORT_OUT, report_text)
    _write_json(
        DECISION_OUT,
        {
            "summary": _row(summary),
            "watch_roots": watch_roots.to_dict(orient="records"),
            "trigger_gate": trigger_gate.to_dict(orient="records"),
            "outputs": {
                "summary": SUMMARY_OUT,
                "watch_roots": WATCH_ROOTS_OUT,
                "package_inventory": PACKAGE_INVENTORY_OUT,
                "role_presence": ROLE_PRESENCE_OUT,
                "trigger_gate": TRIGGER_GATE_OUT,
                "next_action": NEXT_ACTION_OUT,
                "report": REPORT_OUT,
                "charts": [
                    PATH_CHART_OUT,
                    WATCH_ROOT_CHART_OUT,
                    PACKAGE_ROLE_CHART_OUT,
                    TRIGGER_GATE_CHART_OUT,
                    NEXT_ACTION_CHART_OUT,
                ],
            },
        },
    )
    print(json.dumps(_row(summary), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
