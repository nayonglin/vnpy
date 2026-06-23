from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage265"
MODEL_TAG = "stage265_execution_replay_real_package_validator_v1"
OUTPUT_PREFIX = "qmt_roll_stage265_c9_minrisk_execution_replay_real_package_validator"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage265_execution_replay_real_package_validator"

STAGE251_DIR = LINE_DIR / "outputs" / "stage251_dd30_account_floor_true_engine"
STAGE261_DIR = LINE_DIR / "outputs" / "stage261_execution_replay_import_acceptance_packet"
STAGE264_DIR = LINE_DIR / "outputs" / "stage264_external_data_inbox_arrival_monitor"

STAGE251_PREFIX = "qmt_roll_stage251_c9_minrisk_dd30_account_floor_true_engine"
STAGE261_PREFIX = "qmt_roll_stage261_c9_minrisk_execution_replay_import_acceptance_packet"
STAGE264_PREFIX = "qmt_roll_stage264_c9_minrisk_external_data_inbox_arrival_monitor"

STAGE251_TAG = "stage251_dd30_account_floor_true_engine_v1"
STAGE261_TAG = "stage261_execution_replay_import_acceptance_packet_v1"
STAGE264_TAG = "stage264_external_data_inbox_arrival_monitor_v1"

STAGE251_CURVE_IN = STAGE251_DIR / f"{STAGE251_PREFIX}_curve_{STAGE251_TAG}.csv"
STAGE251_SUMMARY_IN = STAGE251_DIR / f"{STAGE251_PREFIX}_summary_{STAGE251_TAG}.csv"
STAGE261_SCHEMA_IN = STAGE261_DIR / f"{STAGE261_PREFIX}_required_schema_contract_{STAGE261_TAG}.csv"
STAGE261_MANIFEST_TEMPLATE_IN = STAGE261_DIR / f"{STAGE261_PREFIX}_manifest_template_{STAGE261_TAG}.csv"
STAGE264_PACKAGE_INVENTORY_IN = STAGE264_DIR / f"{STAGE264_PREFIX}_package_inventory_{STAGE264_TAG}.csv"

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
PACKAGE_INVENTORY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_package_inventory_{MODEL_TAG}.csv"
FILE_ROLE_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_file_role_audit_{MODEL_TAG}.csv"
TABLE_SCHEMA_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_table_schema_audit_{MODEL_TAG}.csv"
MANIFEST_VALUE_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_manifest_value_audit_{MODEL_TAG}.csv"
JOIN_COVERAGE_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_join_coverage_audit_{MODEL_TAG}.csv"
PACKAGE_GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_package_gate_{MODEL_TAG}.csv"
NEXT_ACTION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_next_action_queue_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_validator_status_{MODEL_TAG}.png"
ROLE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_file_role_matrix_{MODEL_TAG}.png"
SCHEMA_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_schema_gate_heatmap_{MODEL_TAG}.png"
JOIN_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_join_coverage_chart_{MODEL_TAG}.png"
PACKAGE_GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_package_gate_chart_{MODEL_TAG}.png"

REPLAY_ROOT = LINE_DIR / "incoming" / "execution_replay"
FULL_ENTRY_DECISION_COUNT = 219
RIGHT_TAIL_REQUIRED_COUNT = 18
BOTTOM_LOSS_REQUIRED_COUNT = 18
FORBIDDEN_MARKERS = [
    "smoke",
    "dry_run",
    "dry-run",
    "readonly",
    "read_only",
    "adapter",
    "synthetic",
    "fixture",
    "backtest_ledger",
    "paper",
]


def _read_csv(path: Path, required: bool = True, nrows: int | None = None) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size <= 4:
        if required:
            raise RuntimeError(f"missing required input: {path}")
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig", nrows=nrows)


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
        return {str(k): _json_safe(v) for k, v in value.items()}
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
        "stage251_curve": _read_csv(STAGE251_CURVE_IN),
        "stage251_summary": _read_csv(STAGE251_SUMMARY_IN),
        "required_schema": _read_csv(STAGE261_SCHEMA_IN),
        "manifest_template": _read_csv(STAGE261_MANIFEST_TEMPLATE_IN),
        "stage264_package_inventory": _read_csv(STAGE264_PACKAGE_INVENTORY_IN, required=False),
    }


def _safe_rglob(root: Path) -> list[Path]:
    if not root.exists() or not root.is_dir():
        return []
    return sorted([path for path in root.rglob("*") if path.is_file()], key=lambda item: str(item))


def _package_dirs() -> list[Path]:
    if not REPLAY_ROOT.exists() or not REPLAY_ROOT.is_dir():
        return [REPLAY_ROOT]
    direct_files = [path for path in REPLAY_ROOT.iterdir() if path.is_file()]
    dirs = sorted([path for path in REPLAY_ROOT.iterdir() if path.is_dir()], key=lambda item: str(item))
    if direct_files:
        return [REPLAY_ROOT] + dirs
    return dirs if dirs else [REPLAY_ROOT]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _row_count(path: Path) -> int:
    if not path.exists() or not path.is_file():
        return 0
    if path.suffix.lower() == ".csv":
        try:
            with path.open("rb") as handle:
                return max(sum(1 for _ in handle) - 1, 0)
        except OSError:
            return 0
    if path.suffix.lower() in {".jsonl", ".ndjson"}:
        try:
            with path.open("r", encoding="utf-8", errors="ignore") as handle:
                return sum(1 for line in handle if line.strip())
        except OSError:
            return 0
    if path.suffix.lower() == ".json":
        try:
            payload = json.loads(path.read_text(encoding="utf-8", errors="ignore") or "{}")
            return len(payload) if isinstance(payload, list) else int(bool(payload))
        except (OSError, json.JSONDecodeError):
            return 0
    return 1


def _read_table(path: Path, max_rows: int | None = None) -> pd.DataFrame:
    if not path.exists() or not path.is_file():
        return pd.DataFrame()
    suffix = path.suffix.lower()
    try:
        if suffix == ".csv":
            return pd.read_csv(path, encoding="utf-8-sig", nrows=max_rows)
        if suffix == ".json":
            payload = json.loads(path.read_text(encoding="utf-8", errors="ignore") or "{}")
            if isinstance(payload, list):
                return pd.DataFrame(payload[:max_rows] if max_rows else payload)
            if isinstance(payload, dict):
                return pd.DataFrame([payload])
        if suffix in {".jsonl", ".ndjson"}:
            rows = []
            with path.open("r", encoding="utf-8", errors="ignore") as handle:
                for idx, line in enumerate(handle):
                    if max_rows is not None and idx >= max_rows:
                        break
                    if not line.strip():
                        continue
                    rows.append(json.loads(line))
            return pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame()
    return pd.DataFrame()


def _forbidden_marker_hit(path: Path) -> str:
    text = str(path).lower()
    hits = [marker for marker in FORBIDDEN_MARKERS if marker in text]
    return ",".join(hits)


def _file_role_audit(manifest_template: pd.DataFrame, package_dirs: list[Path]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for package_dir in package_dirs:
        for _, role in manifest_template.iterrows():
            file_role = str(role["file_role"])
            expected_name = str(role["expected_file_name"])
            min_rows = _to_int(role["min_rows"])
            required = _to_int(role["required"])
            if file_role == "raw_files":
                path = package_dir / "raw"
                raw_files = _safe_rglob(path)
                exists = int(bool(raw_files))
                observed_rows = len(raw_files)
                total_bytes = int(sum(item.stat().st_size for item in raw_files))
                matched_path = str(path)
            else:
                path = package_dir / expected_name
                exists = int(path.exists() and path.is_file())
                observed_rows = _row_count(path)
                total_bytes = int(path.stat().st_size) if exists else 0
                matched_path = str(path)
            rows.append(
                {
                    "package_id": package_dir.name,
                    "package_path": str(package_dir),
                    "file_role": file_role,
                    "expected_file_name": expected_name,
                    "matched_path": matched_path,
                    "exists": exists,
                    "required": required,
                    "min_rows": min_rows,
                    "observed_rows_or_files": observed_rows,
                    "total_bytes": total_bytes,
                    "role_present_enough": int(exists and observed_rows >= min_rows),
                    "forbidden_marker_hit": _forbidden_marker_hit(path),
                }
            )
    return pd.DataFrame(rows)


def _package_inventory(package_dirs: list[Path], file_role: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for package_dir in package_dirs:
        files = _safe_rglob(package_dir)
        roles = file_role[file_role["package_path"].eq(str(package_dir))]
        rows.append(
            {
                "package_id": package_dir.name,
                "package_path": str(package_dir),
                "exists": int(package_dir.exists() and package_dir.is_dir()),
                "file_count": len(files),
                "total_bytes": int(sum(path.stat().st_size for path in files)),
                "required_role_count": int(roles["required"].sum()) if not roles.empty else 0,
                "role_present_count": int(roles["role_present_enough"].sum()) if not roles.empty else 0,
                "forbidden_marker_count": int((roles["forbidden_marker_hit"].astype(str).str.len() > 0).sum()) if not roles.empty else 0,
                "package_role_complete": int((not roles.empty) and (roles["role_present_enough"].sum() == roles["required"].sum())),
            }
        )
    return pd.DataFrame(rows)


def _required_fields_by_table(required_schema: pd.DataFrame) -> dict[str, list[str]]:
    required = required_schema[required_schema["required"].map(_to_int).eq(1)]
    out: dict[str, list[str]] = {}
    for table_name, group in required.groupby("table_name"):
        out[str(table_name)] = group["field_name"].astype(str).tolist()
    return out


def _table_schema_audit(required_schema: pd.DataFrame, package_dirs: list[Path]) -> pd.DataFrame:
    required_by_table = _required_fields_by_table(required_schema)
    table_file = {
        "manifest": "manifest.csv",
        "order_events": "order_events.csv",
        "trade_events": "trade_events.csv",
        "account_snapshots": "account_snapshots.csv",
        "tick_or_book_events": "tick_or_book_events.csv",
    }
    rows: list[dict[str, Any]] = []
    for package_dir in package_dirs:
        for table_name, required_fields in table_file.items():
            path = package_dir / required_fields
            frame = _read_table(path, max_rows=5000)
            columns = set(frame.columns.astype(str)) if not frame.empty else set()
            expected = required_by_table.get(table_name, [])
            missing = [field for field in expected if field not in columns]
            rows.append(
                {
                    "package_id": package_dir.name,
                    "table_name": table_name,
                    "file_path": str(path),
                    "exists": int(path.exists() and path.is_file()),
                    "row_count": _row_count(path),
                    "required_field_count": len(expected),
                    "present_required_field_count": len(expected) - len(missing),
                    "missing_required_fields": ",".join(missing),
                    "schema_pass": int(path.exists() and path.is_file() and not missing),
                }
            )
    return pd.DataFrame(rows)


def _nonempty(frame: pd.DataFrame, column: str) -> int:
    return int(column in frame.columns and frame[column].notna().all() and frame[column].astype(str).str.strip().ne("").all())


def _manifest_value_audit(package_dirs: list[Path]) -> pd.DataFrame:
    rows = []
    for package_dir in package_dirs:
        path = package_dir / "manifest.csv"
        manifest = _read_table(path)
        row = _row(manifest)
        raw_files = _safe_rglob(package_dir / "raw")
        manifest_raw_sha = str(_get(row, "raw_sha256", default="")).strip()
        raw_hash_match_count = 0
        if manifest_raw_sha and raw_files:
            for raw_file in raw_files:
                try:
                    raw_hash_match_count += int(_sha256(raw_file) == manifest_raw_sha)
                except OSError:
                    pass
        source_license = str(_get(row, "source_license", default="")).strip()
        synthetic_flag = _to_int(_get(row, "synthetic_flag", default=1), default=1)
        coverage_entry_count = _to_int(_get(row, "coverage_entry_count"))
        right_tail_count = _to_int(_get(row, "right_tail_coverage_count"))
        bottom_loss_count = _to_int(_get(row, "bottom_loss_coverage_count"))
        rows.append(
            {
                "package_id": package_dir.name,
                "manifest_exists": int(path.exists() and path.is_file()),
                "source_license_nonempty": int(bool(source_license)),
                "permission_scope_nonempty": _nonempty(manifest, "permission_scope"),
                "raw_sha256_nonempty": int(bool(manifest_raw_sha)),
                "schema_hash_nonempty": int(bool(str(_get(row, "schema_hash", default="")).strip())),
                "synthetic_flag_zero": int(synthetic_flag == 0),
                "coverage_entry_count": coverage_entry_count,
                "coverage_entry_pass": int(coverage_entry_count >= FULL_ENTRY_DECISION_COUNT),
                "right_tail_coverage_count": right_tail_count,
                "right_tail_pass": int(right_tail_count >= RIGHT_TAIL_REQUIRED_COUNT),
                "bottom_loss_coverage_count": bottom_loss_count,
                "bottom_loss_pass": int(bottom_loss_count >= BOTTOM_LOSS_REQUIRED_COUNT),
                "raw_file_count": len(raw_files),
                "raw_hash_match_count": raw_hash_match_count,
                "manifest_value_pass": int(
                    path.exists()
                    and bool(source_license)
                    and bool(manifest_raw_sha)
                    and synthetic_flag == 0
                    and coverage_entry_count >= FULL_ENTRY_DECISION_COUNT
                    and right_tail_count >= RIGHT_TAIL_REQUIRED_COUNT
                    and bottom_loss_count >= BOTTOM_LOSS_REQUIRED_COUNT
                ),
            }
        )
    return pd.DataFrame(rows)


def _join_coverage_audit(package_dirs: list[Path]) -> pd.DataFrame:
    rows = []
    for package_dir in package_dirs:
        orders = _read_table(package_dir / "order_events.csv")
        trades = _read_table(package_dir / "trade_events.csv")
        accounts = _read_table(package_dir / "account_snapshots.csv")
        books = _read_table(package_dir / "tick_or_book_events.csv")
        order_vt = set(orders["vt_orderid"].dropna().astype(str)) if "vt_orderid" in orders.columns else set()
        trade_vt = set(trades["vt_orderid"].dropna().astype(str)) if "vt_orderid" in trades.columns else set()
        signal_count = int(orders["bridge_signal_id"].dropna().astype(str).nunique()) if "bridge_signal_id" in orders.columns else 0
        order_reference_count = int(orders["order_reference"].dropna().astype(str).nunique()) if "order_reference" in orders.columns else 0
        trade_join_count = len(trade_vt.intersection(order_vt))
        trade_unmatched_count = max(len(trade_vt - order_vt), 0)
        rows.append(
            {
                "package_id": package_dir.name,
                "order_event_row_count": int(len(orders)),
                "trade_event_row_count": int(len(trades)),
                "account_snapshot_row_count": int(len(accounts)),
                "tick_or_book_row_count": int(len(books)),
                "unique_bridge_signal_count": signal_count,
                "unique_order_reference_count": order_reference_count,
                "unique_vt_orderid_count": len(order_vt),
                "trade_vt_orderid_join_count": trade_join_count,
                "trade_vt_orderid_unmatched_count": trade_unmatched_count,
                "entry_coverage_pass": int(signal_count >= FULL_ENTRY_DECISION_COUNT and len(orders) >= FULL_ENTRY_DECISION_COUNT),
                "order_trade_join_pass": int(len(trade_vt) > 0 and trade_unmatched_count == 0),
                "account_snapshot_pass": int(len(accounts) >= FULL_ENTRY_DECISION_COUNT),
                "tick_or_book_pass": int(len(books) >= FULL_ENTRY_DECISION_COUNT),
            }
        )
    return pd.DataFrame(rows)


def _package_gate(
    package_inventory: pd.DataFrame,
    file_role: pd.DataFrame,
    schema: pd.DataFrame,
    manifest: pd.DataFrame,
    join: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    for _, pkg in package_inventory.iterrows():
        package_id = str(pkg["package_id"])
        schema_rows = schema[schema["package_id"].eq(package_id)]
        manifest_row = _row(manifest[manifest["package_id"].eq(package_id)])
        join_row = _row(join[join["package_id"].eq(package_id)])
        gate_items = [
            ("package_root_exists", 1, _to_int(pkg["exists"]), "package directory exists"),
            ("no_forbidden_marker", 1, int(_to_int(pkg["forbidden_marker_count"]) == 0), "reject smoke/read-only/adapter/synthetic/backtest markers"),
            ("all_required_file_roles_present", _to_int(pkg["required_role_count"]), _to_int(pkg["role_present_count"]), "all Stage261 manifest roles present and min rows met"),
            ("all_required_table_schemas_pass", int(len(schema_rows)), int(schema_rows["schema_pass"].sum()) if not schema_rows.empty else 0, "manifest/order/trade/account/book required columns"),
            ("manifest_values_pass", 1, _to_int(_get(manifest_row, "manifest_value_pass")), "license/hash/synthetic=0/219/tail coverage"),
            ("entry_coverage_pass", 1, _to_int(_get(join_row, "entry_coverage_pass")), ">=219 unique bridge signals and order events"),
            ("order_trade_join_pass", 1, _to_int(_get(join_row, "order_trade_join_pass")), "trade vt_orderid must join orders"),
            ("account_snapshot_pass", 1, _to_int(_get(join_row, "account_snapshot_pass")), ">=219 account snapshots"),
            ("tick_or_book_pass", 1, _to_int(_get(join_row, "tick_or_book_pass")), ">=219 same-source tick/book rows"),
            ("strategy_rule_or_true_engine_allowed", 1, 0, "data validation does not create a rule"),
        ]
        for gate_id, required, observed, reason in gate_items:
            rows.append(
                {
                    "package_id": package_id,
                    "gate_id": gate_id,
                    "required": required,
                    "observed": observed,
                    "pass_now": int(observed >= required),
                    "reason": reason,
                }
            )
    return pd.DataFrame(rows)


def _next_action(package_gate: pd.DataFrame, package_inventory: pd.DataFrame) -> pd.DataFrame:
    accepted_count = 0
    if not package_gate.empty:
        accepted_count = int(package_gate.groupby("package_id")["pass_now"].min().sum())
    any_files = int((package_inventory["file_count"] > 0).sum()) if not package_inventory.empty else 0
    rows = [
        {
            "priority": 1,
            "action_id": "accepted_package_then_run_stage260_field_source_audit",
            "condition_now": int(accepted_count > 0),
            "action": "Use the accepted package as same-source execution replay evidence, then run Stage260/Stage141 gates.",
            "allowed_now": int(accepted_count > 0),
            "strategy_rule_allowed": 0,
        },
        {
            "priority": 2,
            "action_id": "partial_or_invalid_package_fix_manifest_roles_schema_join",
            "condition_now": int(any_files > 0 and accepted_count == 0),
            "action": "Keep package quarantined and fix failed role/schema/manifest/join gates.",
            "allowed_now": int(any_files > 0 and accepted_count == 0),
            "strategy_rule_allowed": 0,
        },
        {
            "priority": 3,
            "action_id": "empty_inbox_wait_real_replay_package",
            "condition_now": int(any_files == 0),
            "action": "No execution replay package files detected. Keep monitoring; do not resume local OHLCV/OI rules.",
            "allowed_now": int(any_files == 0),
            "strategy_rule_allowed": 0,
        },
    ]
    return pd.DataFrame(rows)


def _summary(
    inputs: dict[str, Any],
    package_inventory: pd.DataFrame,
    file_role: pd.DataFrame,
    schema: pd.DataFrame,
    manifest: pd.DataFrame,
    join: pd.DataFrame,
    package_gate: pd.DataFrame,
) -> pd.DataFrame:
    official = _official_summary(inputs["stage251_summary"])
    accepted_count = int(package_gate.groupby("package_id")["pass_now"].min().sum()) if not package_gate.empty else 0
    row = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "line_id": LINE_ID,
        "decision": "stage265_execution_replay_validator_no_real_package_no_rule",
        "stage_nature": "read_only_execution_replay_real_package_validator",
        "official_config_changed": 0,
        "strategy_rule_created": 0,
        "true_engine_run": 0,
        "ab_triggered": 0,
        "order_api_called": 0,
        "ctp_or_simnow_connected": 0,
        "replay_root": str(REPLAY_ROOT),
        "package_candidate_count": int(len(package_inventory)),
        "package_root_exists_count": int(package_inventory["exists"].sum()) if not package_inventory.empty else 0,
        "package_with_files_count": int((package_inventory["file_count"] > 0).sum()) if not package_inventory.empty else 0,
        "accepted_package_count": accepted_count,
        "required_file_role_count": int(file_role["required"].sum()) if not file_role.empty else 0,
        "file_role_pass_count": int(file_role["role_present_enough"].sum()) if not file_role.empty else 0,
        "table_schema_audit_count": int(len(schema)),
        "table_schema_pass_count": int(schema["schema_pass"].sum()) if not schema.empty else 0,
        "manifest_value_pass_count": int(manifest["manifest_value_pass"].sum()) if not manifest.empty else 0,
        "entry_coverage_pass_count": int(join["entry_coverage_pass"].sum()) if not join.empty else 0,
        "order_trade_join_pass_count": int(join["order_trade_join_pass"].sum()) if not join.empty else 0,
        "package_gate_count": int(len(package_gate)),
        "package_gate_pass_count": int(package_gate["pass_now"].sum()) if not package_gate.empty else 0,
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
        "Stage265 execution replay validator | "
        f"accepted packages {row['accepted_package_count']} | "
        f"file roles {row['file_role_pass_count']}/{row['required_file_role_count']}"
    )
    ax1.text(
        0.015,
        0.95,
        "Validator only: no strategy rule / no true engine",
        transform=ax1.transAxes,
        va="top",
        bbox={"facecolor": "white", "edgecolor": "#777777", "alpha": 0.9},
    )
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_role_matrix(file_role: pd.DataFrame) -> None:
    pivot = file_role.pivot_table(index="package_id", columns="file_role", values="role_present_enough", aggfunc="max", fill_value=0)
    fig, ax = plt.subplots(figsize=(10, max(3.2, len(pivot) * 0.5 + 1.5)))
    ax.imshow(pivot.to_numpy(dtype=float), cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=35, ha="right", fontsize=8)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=8)
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            ax.text(j, i, str(int(pivot.iloc[i, j])), ha="center", va="center", fontsize=8)
    ax.set_title("Execution replay file role matrix")
    fig.tight_layout()
    fig.savefig(ROLE_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_schema(schema: pd.DataFrame) -> None:
    pivot = schema.pivot_table(index="package_id", columns="table_name", values="schema_pass", aggfunc="max", fill_value=0)
    fig, ax = plt.subplots(figsize=(9, max(3.2, len(pivot) * 0.5 + 1.5)))
    ax.imshow(pivot.to_numpy(dtype=float), cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=35, ha="right", fontsize=8)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=8)
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            ax.text(j, i, str(int(pivot.iloc[i, j])), ha="center", va="center", fontsize=8)
    ax.set_title("Required table schema gate")
    fig.tight_layout()
    fig.savefig(SCHEMA_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_join(join: pd.DataFrame) -> None:
    columns = [
        "order_event_row_count",
        "trade_event_row_count",
        "unique_bridge_signal_count",
        "trade_vt_orderid_join_count",
        "account_snapshot_row_count",
        "tick_or_book_row_count",
    ]
    plot_df = join.copy()
    fig, ax = plt.subplots(figsize=(11, 5.2))
    x = np.arange(len(columns))
    width = 0.8 / max(len(plot_df), 1)
    for idx, (_, row) in enumerate(plot_df.iterrows()):
        values = [float(row[column]) for column in columns]
        ax.bar(x + idx * width, values, width=width, label=str(row["package_id"]))
    ax.axhline(FULL_ENTRY_DECISION_COUNT, color="#b5533c", linestyle="--", linewidth=1.2, label="219 entry threshold")
    ax.set_xticks(x + width * max(len(plot_df) - 1, 0) / 2)
    ax.set_xticklabels(columns, rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("Rows / unique count")
    ax.set_title("Join and coverage audit")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(loc="upper right", fontsize=7)
    fig.tight_layout()
    fig.savefig(JOIN_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_package_gate(package_gate: pd.DataFrame) -> None:
    pivot = package_gate.pivot_table(index="package_id", columns="gate_id", values="pass_now", aggfunc="max", fill_value=0)
    fig, ax = plt.subplots(figsize=(12, max(3.2, len(pivot) * 0.5 + 1.5)))
    ax.imshow(pivot.to_numpy(dtype=float), cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=35, ha="right", fontsize=7)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=8)
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            ax.text(j, i, str(int(pivot.iloc[i, j])), ha="center", va="center", fontsize=7)
    ax.set_title("Package hard gate")
    fig.tight_layout()
    fig.savefig(PACKAGE_GATE_CHART_OUT, dpi=160)
    plt.close(fig)


def _report(
    summary: pd.DataFrame,
    package_inventory: pd.DataFrame,
    file_role: pd.DataFrame,
    schema: pd.DataFrame,
    manifest: pd.DataFrame,
    join: pd.DataFrame,
    package_gate: pd.DataFrame,
    next_action: pd.DataFrame,
) -> str:
    row = _row(summary)
    return f"""# Stage265 execution replay real package validator

## Decision

`{row['decision']}`

This stage is a read-only validator for real broker/production execution replay packages under `incoming/execution_replay`. It does not create a strategy rule, run true engine, trigger A/B, change official config, connect CTP/SimNow, or call any order API.

## External research judgment

The validation design follows common data-contract practice: Frictionless Table Schema emphasizes field constraints and keys; JSON Schema makes required properties explicit; Pandera expresses dataframe column schemas; Great Expectations checkpoints formalize validation results. For this line, that means a real replay package must pass required files, required columns, manifest license/hash values, and order-trade joins before it can become research evidence.

Sources:
- https://frictionlessdata.io/specs/table-schema/
- https://json-schema.org/understanding-json-schema/reference/object
- https://pandera.readthedocs.io/en/latest/dataframe_schemas.html
- https://docs.greatexpectations.io/docs/reference/api/checkpoint_class/

## Summary

- Official A unchanged: equity `{row['official_end_equity']:.2f}`, return `{row['official_total_return_pct']:.4f}%`, maxDD `{row['official_max_dd_pct']:.4f}%`, Sharpe `{row['official_sharpe']:.4f}`, slippage `{row['official_total_slippage']:.0f}`, trades `{row['official_total_trade_count']:.0f}`, win rate `{row['official_win_rate_pct']:.4f}%`.
- Replay root: `{row['replay_root']}`.
- Package candidates: `{row['package_candidate_count']}`; package roots exist `{row['package_root_exists_count']}`; packages with files `{row['package_with_files_count']}`; accepted `{row['accepted_package_count']}`.
- File roles pass: `{row['file_role_pass_count']}/{row['required_file_role_count']}`.
- Table schemas pass: `{row['table_schema_pass_count']}/{row['table_schema_audit_count']}`.
- Manifest value pass count: `{row['manifest_value_pass_count']}`.
- Entry coverage pass count: `{row['entry_coverage_pass_count']}`.
- Order-trade join pass count: `{row['order_trade_join_pass_count']}`.
- Package gate pass: `{row['package_gate_pass_count']}/{row['package_gate_count']}`.

## Package inventory

{_md_table(package_inventory, max_rows=20)}

## File role audit

{_md_table(file_role[['package_id', 'file_role', 'exists', 'min_rows', 'observed_rows_or_files', 'role_present_enough', 'forbidden_marker_hit']], max_rows=30)}

## Table schema audit

{_md_table(schema[['package_id', 'table_name', 'exists', 'row_count', 'present_required_field_count', 'required_field_count', 'missing_required_fields', 'schema_pass']], max_rows=30)}

## Manifest values

{_md_table(manifest, max_rows=20)}

## Join coverage

{_md_table(join, max_rows=20)}

## Package gate

{_md_table(package_gate, max_rows=40)}

## Next action

{_md_table(next_action, max_rows=20)}
"""


def main() -> None:
    inputs = _load_inputs()
    curve = _official_curve(inputs["stage251_curve"])
    packages = _package_dirs()
    file_role = _file_role_audit(inputs["manifest_template"], packages)
    package_inventory = _package_inventory(packages, file_role)
    schema = _table_schema_audit(inputs["required_schema"], packages)
    manifest = _manifest_value_audit(packages)
    join = _join_coverage_audit(packages)
    package_gate = _package_gate(package_inventory, file_role, schema, manifest, join)
    next_action = _next_action(package_gate, package_inventory)
    summary = _summary(inputs, package_inventory, file_role, schema, manifest, join, package_gate)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_csv(summary, SUMMARY_OUT)
    _write_csv(package_inventory, PACKAGE_INVENTORY_OUT)
    _write_csv(file_role, FILE_ROLE_AUDIT_OUT)
    _write_csv(schema, TABLE_SCHEMA_AUDIT_OUT)
    _write_csv(manifest, MANIFEST_VALUE_AUDIT_OUT)
    _write_csv(join, JOIN_COVERAGE_AUDIT_OUT)
    _write_csv(package_gate, PACKAGE_GATE_OUT)
    _write_csv(next_action, NEXT_ACTION_OUT)

    _plot_official_path(curve, summary)
    _plot_role_matrix(file_role)
    _plot_schema(schema)
    _plot_join(join)
    _plot_package_gate(package_gate)

    report_text = _report(summary, package_inventory, file_role, schema, manifest, join, package_gate, next_action)
    _write_text(REPORT_OUT, report_text)
    _write_json(
        DECISION_OUT,
        {
            "summary": _row(summary),
            "package_gate": package_gate.to_dict(orient="records"),
            "outputs": {
                "summary": SUMMARY_OUT,
                "package_inventory": PACKAGE_INVENTORY_OUT,
                "file_role_audit": FILE_ROLE_AUDIT_OUT,
                "table_schema_audit": TABLE_SCHEMA_AUDIT_OUT,
                "manifest_value_audit": MANIFEST_VALUE_AUDIT_OUT,
                "join_coverage_audit": JOIN_COVERAGE_AUDIT_OUT,
                "package_gate": PACKAGE_GATE_OUT,
                "next_action": NEXT_ACTION_OUT,
                "report": REPORT_OUT,
                "charts": [
                    PATH_CHART_OUT,
                    ROLE_CHART_OUT,
                    SCHEMA_CHART_OUT,
                    JOIN_CHART_OUT,
                    PACKAGE_GATE_CHART_OUT,
                ],
            },
        },
    )
    print(json.dumps(_row(summary), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
