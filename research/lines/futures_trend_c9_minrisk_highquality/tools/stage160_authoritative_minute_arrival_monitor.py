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
STAGE = "Stage160"
MODEL_TAG = "stage160_authoritative_minute_arrival_monitor_v1"
OUTPUT_PREFIX = "qmt_roll_stage160_c9_minrisk_authoritative_minute_arrival_monitor"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage160_authoritative_minute_arrival_monitor"

INCOMING_ROOT = REPO_DIR / "incoming" / "stage152_authoritative_minute_ohlcv"

CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)

STAGE152_DIR = LINE_DIR / "outputs" / "stage152_authoritative_minute_ohlcv_manifest"
STAGE152_PREFIX = "qmt_roll_stage152_c9_minrisk_authoritative_minute_ohlcv_manifest"
STAGE152_TAG = "stage152_authoritative_minute_ohlcv_manifest_v1"
STAGE152_REQUEST_TEMPLATE_IN = STAGE152_DIR / f"{STAGE152_PREFIX}_request_manifest_template_{STAGE152_TAG}.csv"

STAGE159_DIR = LINE_DIR / "outputs" / "stage159_authoritative_minute_release_runbook"
STAGE159_PREFIX = "qmt_roll_stage159_c9_minrisk_authoritative_minute_release_runbook"
STAGE159_TAG = "stage159_authoritative_minute_release_runbook_v1"
STAGE159_SUMMARY_IN = STAGE159_DIR / f"{STAGE159_PREFIX}_summary_{STAGE159_TAG}.csv"
STAGE159_COMMAND_MANIFEST_IN = STAGE159_DIR / f"{STAGE159_PREFIX}_operator_command_manifest_{STAGE159_TAG}.csv"

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
REQUEST_SNAPSHOT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_request_arrival_snapshot_{MODEL_TAG}.csv"
ROLE_PROGRESS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_role_progress_{MODEL_TAG}.csv"
EXCHANGE_PROGRESS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_exchange_progress_{MODEL_TAG}.csv"
PRODUCT_GAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_gap_{MODEL_TAG}.csv"
UNEXPECTED_FILE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_unexpected_file_inventory_{MODEL_TAG}.csv"
TRIGGER_GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trigger_gate_status_{MODEL_TAG}.csv"
OPERATOR_QUEUE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_operator_action_queue_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_arrival_status_{MODEL_TAG}.png"
ROLE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_role_progress_bar_{MODEL_TAG}.png"
EXCHANGE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_exchange_arrival_progress_{MODEL_TAG}.png"
PRODUCT_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_missing_bar_{MODEL_TAG}.png"
GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trigger_gate_matrix_{MODEL_TAG}.png"

ROLE_COLUMNS = {
    "raw": "expected_raw_file",
    "normalized": "expected_normalized_file",
    "proof": "expected_proof_file",
}


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if np.isnan(number) or np.isinf(number) else number
    if isinstance(value, (pd.Timestamp, datetime)):
        if pd.isna(value):
            return None
        return pd.Timestamp(value).strftime("%Y-%m-%d %H:%M:%S")
    return value


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size <= 4:
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    for column in data.columns:
        if pd.api.types.is_float_dtype(data[column]):
            data[column] = data[column].map(lambda value: "" if pd.isna(value) else f"{value:.6f}")
        else:
            data[column] = data[column].map(
                lambda value: "" if pd.isna(value) else str(value).replace("|", "\\|").replace("\n", "<br>")
            )
    lines = [
        "| " + " | ".join(str(column) for column in data.columns) + " |",
        "| " + " | ".join(["---"] * len(data.columns)) + " |",
    ]
    for _, row in data.iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in data.columns) + " |")
    return "\n".join(lines)


def _row(path: Path) -> dict[str, Any]:
    frame = _read_csv(path)
    return frame.iloc[0].to_dict() if not frame.empty else {}


def _num(row: dict[str, Any], key: str, default: float = 0.0) -> float:
    value = row.get(key, default)
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if np.isnan(number) or np.isinf(number):
        return default
    return number


def _int(row: dict[str, Any], key: str, default: int = 0) -> int:
    return int(round(_num(row, key, float(default))))


def _load_curve() -> pd.DataFrame:
    curve = _read_csv(CURVE_IN)
    if curve.empty:
        raise RuntimeError(f"missing curve input: {CURVE_IN}")
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]:
        curve[column] = pd.to_numeric(curve[column], errors="coerce")
    return curve[curve["date"].notna()].sort_values("date").reset_index(drop=True)


def _baseline_metrics(curve: pd.DataFrame) -> dict[str, float]:
    stage159 = _row(STAGE159_SUMMARY_IN)
    if stage159:
        return {
            "end_equity": _num(stage159, "end_equity", np.nan),
            "total_return_pct": _num(stage159, "total_return_pct", np.nan),
            "max_drawdown_pct": _num(stage159, "max_drawdown_pct", np.nan),
            "sharpe": _num(stage159, "sharpe", np.nan),
            "total_slippage": _num(stage159, "total_slippage", np.nan),
            "total_trade_count": _num(stage159, "total_trade_count", np.nan),
            "closed_lot_win_rate_pct": _num(stage159, "closed_lot_win_rate_pct", np.nan),
            "max_broker10_margin_to_equity_pct": _num(stage159, "max_broker10_margin_to_equity_pct", np.nan),
        }
    first_equity = float(curve["account_equity"].dropna().iloc[0])
    end_equity = float(curve["account_equity"].dropna().iloc[-1])
    return {
        "end_equity": end_equity,
        "total_return_pct": (end_equity / first_equity - 1.0) * 100.0,
        "max_drawdown_pct": float(curve["drawdown_pct"].min()),
        "sharpe": np.nan,
        "total_slippage": np.nan,
        "total_trade_count": np.nan,
        "closed_lot_win_rate_pct": np.nan,
        "max_broker10_margin_to_equity_pct": float(curve["broker10_margin_to_equity_pct"].max()),
    }


def _file_meta(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {
            "present": 0,
            "size_bytes": 0,
            "mtime": "",
            "identity_sha256": "",
        }
    stat = path.stat()
    mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    identity = hashlib.sha256(f"{path}|{stat.st_size}|{stat.st_mtime_ns}".encode("utf-8")).hexdigest()
    return {
        "present": 1,
        "size_bytes": int(stat.st_size),
        "mtime": mtime,
        "identity_sha256": identity,
    }


def _expected_abs_path(value: Any) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else (REPO_DIR / path)


def _request_snapshot(manifest: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, source in manifest.iterrows():
        base = {
            "request_id": str(source.get("request_id", "")),
            "exchange": str(source.get("exchange", "")),
            "product": str(source.get("product", "")),
            "vt_symbol": str(source.get("vt_symbol", "")),
            "request_date": str(source.get("request_date", "")),
            "request_start_ts": str(source.get("request_start_ts", "")),
            "request_end_ts": str(source.get("request_end_ts", "")),
            "required_window_count": int(source.get("required_window_count", 0)),
            "right_tail_window_count": int(source.get("right_tail_window_count", 0)),
            "bottom_loss_window_count": int(source.get("bottom_loss_window_count", 0)),
            "maxdd_window_count": int(source.get("maxdd_window_count", 0)),
            "priority_score": float(source.get("priority_score", 0.0)),
        }
        present_count = 0
        size_total = 0
        newest_mtime = ""
        for role, column in ROLE_COLUMNS.items():
            expected_rel = str(source.get(column, ""))
            expected_abs = _expected_abs_path(expected_rel)
            meta = _file_meta(expected_abs)
            present_count += int(meta["present"])
            size_total += int(meta["size_bytes"])
            newest_mtime = max(newest_mtime, str(meta["mtime"]))
            base[f"expected_{role}_file"] = expected_rel
            base[f"{role}_present"] = int(meta["present"])
            base[f"{role}_size_bytes"] = int(meta["size_bytes"])
            base[f"{role}_mtime"] = str(meta["mtime"])
            base[f"{role}_identity_sha256"] = str(meta["identity_sha256"])
        base["present_role_count"] = present_count
        base["missing_role_count"] = len(ROLE_COLUMNS) - present_count
        base["request_complete_triplet"] = int(present_count == len(ROLE_COLUMNS))
        base["request_partial_triplet"] = int(0 < present_count < len(ROLE_COLUMNS))
        base["request_missing_triplet"] = int(present_count == 0)
        base["request_arrival_bytes"] = size_total
        base["newest_file_mtime"] = newest_mtime
        rows.append(base)
    return pd.DataFrame(rows)


def _role_progress(snapshot: pd.DataFrame) -> pd.DataFrame:
    request_count = len(snapshot)
    rows = []
    for role in ROLE_COLUMNS:
        present = int(snapshot[f"{role}_present"].sum()) if not snapshot.empty else 0
        bytes_total = int(snapshot[f"{role}_size_bytes"].sum()) if not snapshot.empty else 0
        rows.append(
            {
                "role": role,
                "present_count": present,
                "required_count": request_count,
                "missing_count": request_count - present,
                "arrival_pct": (present / request_count * 100.0) if request_count else 0.0,
                "observed_bytes": bytes_total,
                "hard_pass_now": int(request_count > 0 and present == request_count),
            }
        )
    return pd.DataFrame(rows)


def _exchange_progress(snapshot: pd.DataFrame) -> pd.DataFrame:
    if snapshot.empty:
        return pd.DataFrame()
    grouped = (
        snapshot.groupby("exchange", dropna=False)
        .agg(
            request_count=("request_id", "count"),
            complete_triplet_count=("request_complete_triplet", "sum"),
            partial_triplet_count=("request_partial_triplet", "sum"),
            missing_triplet_count=("request_missing_triplet", "sum"),
            present_role_count=("present_role_count", "sum"),
            required_role_count=("request_id", lambda values: len(values) * len(ROLE_COLUMNS)),
            arrival_bytes=("request_arrival_bytes", "sum"),
            required_window_count=("required_window_count", "sum"),
            right_tail_window_count=("right_tail_window_count", "sum"),
            bottom_loss_window_count=("bottom_loss_window_count", "sum"),
            maxdd_window_count=("maxdd_window_count", "sum"),
        )
        .reset_index()
    )
    grouped["arrival_pct"] = grouped["present_role_count"] / grouped["required_role_count"].replace(0, np.nan) * 100.0
    grouped["arrival_pct"] = grouped["arrival_pct"].fillna(0.0)
    return grouped.sort_values(["arrival_pct", "required_role_count", "exchange"], ascending=[True, False, True]).reset_index(drop=True)


def _product_gap(snapshot: pd.DataFrame) -> pd.DataFrame:
    if snapshot.empty:
        return pd.DataFrame()
    grouped = (
        snapshot.groupby(["exchange", "product"], dropna=False)
        .agg(
            request_count=("request_id", "count"),
            complete_triplet_count=("request_complete_triplet", "sum"),
            partial_triplet_count=("request_partial_triplet", "sum"),
            missing_triplet_count=("request_missing_triplet", "sum"),
            present_role_count=("present_role_count", "sum"),
            required_role_count=("request_id", lambda values: len(values) * len(ROLE_COLUMNS)),
            required_window_count=("required_window_count", "sum"),
            right_tail_window_count=("right_tail_window_count", "sum"),
            bottom_loss_window_count=("bottom_loss_window_count", "sum"),
            maxdd_window_count=("maxdd_window_count", "sum"),
        )
        .reset_index()
    )
    grouped["missing_role_count"] = grouped["required_role_count"] - grouped["present_role_count"]
    grouped["arrival_pct"] = grouped["present_role_count"] / grouped["required_role_count"].replace(0, np.nan) * 100.0
    grouped["arrival_pct"] = grouped["arrival_pct"].fillna(0.0)
    return grouped.sort_values(["missing_role_count", "required_window_count", "exchange", "product"], ascending=[False, False, True, True]).reset_index(drop=True)


def _unexpected_inventory(expected_paths: set[Path]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    columns = ["path", "size_bytes", "mtime", "unexpected_reason"]
    if not INCOMING_ROOT.exists():
        return pd.DataFrame(rows, columns=columns)
    expected_resolved = {path.resolve() for path in expected_paths}
    for path in sorted(INCOMING_ROOT.rglob("*")):
        if not path.is_file():
            continue
        resolved = path.resolve()
        if resolved in expected_resolved:
            continue
        stat = path.stat()
        rows.append(
            {
                "path": str(path.relative_to(REPO_DIR)),
                "size_bytes": int(stat.st_size),
                "mtime": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                "unexpected_reason": "not_listed_in_stage152_request_manifest",
            }
        )
    return pd.DataFrame(rows, columns=columns)


def _snapshot_fingerprint(snapshot: pd.DataFrame, unexpected: pd.DataFrame) -> str:
    hasher = hashlib.sha256()
    for frame in [snapshot, unexpected]:
        if frame.empty:
            hasher.update(b"empty\n")
            continue
        stable = frame.copy()
        for column in stable.columns:
            stable[column] = stable[column].map(lambda value: "" if pd.isna(value) else str(value))
        hasher.update(stable.to_csv(index=False).encode("utf-8"))
    return hasher.hexdigest()


def _operator_queue(summary: dict[str, Any], command_manifest: pd.DataFrame) -> pd.DataFrame:
    stage153_allowed = int(summary["stage153_trigger_allowed"])
    rows = [
        {
            "action_order": 1,
            "action_id": "create_incoming_root_if_needed",
            "allowed_now": int(not bool(summary["incoming_root_exists"])),
            "command": "mkdir -p incoming/stage152_authoritative_minute_ohlcv",
            "reason": "incoming root is absent" if not bool(summary["incoming_root_exists"]) else "incoming root already exists",
            "strategy_rule_allowed": 0,
        },
        {
            "action_order": 2,
            "action_id": "deliver_expected_raw_files",
            "allowed_now": int(summary["missing_raw_file_count"] > 0),
            "command": "deliver licensed raw files to every expected_raw_file path in Stage152 request manifest",
            "reason": f"missing_raw_file_count={summary['missing_raw_file_count']}",
            "strategy_rule_allowed": 0,
        },
        {
            "action_order": 3,
            "action_id": "deliver_expected_normalized_files",
            "allowed_now": int(summary["missing_normalized_file_count"] > 0),
            "command": "deliver canonical normalized parquet files to every expected_normalized_file path",
            "reason": f"missing_normalized_file_count={summary['missing_normalized_file_count']}",
            "strategy_rule_allowed": 0,
        },
        {
            "action_order": 4,
            "action_id": "deliver_expected_proof_files",
            "allowed_now": int(summary["missing_proof_file_count"] > 0),
            "command": "deliver proof JSON files to every expected_proof_file path",
            "reason": f"missing_proof_file_count={summary['missing_proof_file_count']}",
            "strategy_rule_allowed": 0,
        },
        {
            "action_order": 5,
            "action_id": "rerun_stage160_monitor",
            "allowed_now": 1,
            "command": ".py311/bin/python research/lines/futures_trend_c9_minrisk_highquality/tools/stage160_authoritative_minute_arrival_monitor.py",
            "reason": "refresh readonly arrival snapshot after any file delivery",
            "strategy_rule_allowed": 0,
        },
        {
            "action_order": 6,
            "action_id": "run_stage153_intake",
            "allowed_now": stage153_allowed,
            "command": ".py311/bin/python research/lines/futures_trend_c9_minrisk_highquality/tools/stage153_authoritative_minute_ohlcv_intake_validator.py",
            "reason": "only after all Stage152 raw/normalized/proof expected files are present",
            "strategy_rule_allowed": 0,
        },
    ]
    if not command_manifest.empty:
        for _, command in command_manifest.sort_values("command_order").iterrows():
            if str(command.get("command_id", "")) == "inspect_release_summary":
                continue
            rows.append(
                {
                    "action_order": int(len(rows) + 1),
                    "action_id": f"runbook_{command.get('command_id', '')}",
                    "allowed_now": int(stage153_allowed and str(command.get("command_id", "")) in {"run_stage153"}),
                    "command": str(command.get("command", "")),
                    "reason": "mirrored from Stage159 runbook; gated by complete triplets",
                    "strategy_rule_allowed": 0,
                }
            )
    return pd.DataFrame(rows)


def _trigger_gate(summary: dict[str, Any], role_progress: pd.DataFrame, command_manifest: pd.DataFrame) -> pd.DataFrame:
    safe_count = int(command_manifest["safe_command"].sum()) if not command_manifest.empty and "safe_command" in command_manifest else 0
    command_count = int(len(command_manifest))
    commands_with_order = int(command_manifest["contains_ctp_or_order_api"].sum()) if not command_manifest.empty and "contains_ctp_or_order_api" in command_manifest else 0
    commands_change_config = int(command_manifest["changes_official_config"].sum()) if not command_manifest.empty and "changes_official_config" in command_manifest else 0
    return pd.DataFrame(
        [
            {
                "gate_id": "stage152_manifest_loaded",
                "observed": summary["stage152_request_count"],
                "required": summary["stage152_request_count"],
                "pass_now": int(summary["stage152_request_count"] > 0),
                "severity": "contract_hard",
            },
            {
                "gate_id": "incoming_root_exists",
                "observed": summary["incoming_root_exists"],
                "required": 1,
                "pass_now": int(summary["incoming_root_exists"] == 1),
                "severity": "delivery_soft",
            },
            {
                "gate_id": "raw_files_present",
                "observed": int(role_progress.loc[role_progress["role"] == "raw", "present_count"].sum()),
                "required": summary["stage152_request_count"],
                "pass_now": int(summary["raw_file_present_count"] == summary["stage152_request_count"] and summary["stage152_request_count"] > 0),
                "severity": "data_hard",
            },
            {
                "gate_id": "normalized_files_present",
                "observed": int(role_progress.loc[role_progress["role"] == "normalized", "present_count"].sum()),
                "required": summary["stage152_request_count"],
                "pass_now": int(summary["normalized_file_present_count"] == summary["stage152_request_count"] and summary["stage152_request_count"] > 0),
                "severity": "data_hard",
            },
            {
                "gate_id": "proof_files_present",
                "observed": int(role_progress.loc[role_progress["role"] == "proof", "present_count"].sum()),
                "required": summary["stage152_request_count"],
                "pass_now": int(summary["proof_file_present_count"] == summary["stage152_request_count"] and summary["stage152_request_count"] > 0),
                "severity": "data_hard",
            },
            {
                "gate_id": "all_request_triplets_complete",
                "observed": summary["request_complete_triplet_count"],
                "required": summary["stage152_request_count"],
                "pass_now": int(summary["stage153_trigger_allowed"] == 1),
                "severity": "data_hard",
            },
            {
                "gate_id": "no_unexpected_files",
                "observed": summary["unexpected_file_count"],
                "required": 0,
                "pass_now": int(summary["unexpected_file_count"] == 0),
                "severity": "provenance_soft",
            },
            {
                "gate_id": "stage159_commands_safe",
                "observed": safe_count,
                "required": command_count,
                "pass_now": int(command_count > 0 and safe_count == command_count and commands_with_order == 0 and commands_change_config == 0),
                "severity": "safety_hard",
            },
            {
                "gate_id": "true_engine_allowed",
                "observed": summary["true_engine_allowed"],
                "required": 0,
                "pass_now": int(summary["true_engine_allowed"] == 0),
                "severity": "strategy_hard",
            },
        ]
    )


def _write_report(
    summary: dict[str, Any],
    role_progress: pd.DataFrame,
    exchange_progress: pd.DataFrame,
    product_gap: pd.DataFrame,
    trigger_gate: pd.DataFrame,
    operator_queue: pd.DataFrame,
) -> None:
    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(
        [
            "# Stage160 Authoritative Minute Arrival Monitor",
            "",
            f"- model_tag: `{MODEL_TAG}`",
            f"- decision: `{summary['decision']}`",
            f"- snapshot_fingerprint: `{summary['snapshot_fingerprint']}`",
            "- Scope: readonly file-arrival monitor for Stage152 authoritative minute OHLCV request package.",
            "- Hard lock: no strategy rule, no true engine, no A/B, no CTP, no order API, no official config change.",
            "",
            "## Summary",
            "",
            _md_table(pd.DataFrame([summary])),
            "",
            "## Role Progress",
            "",
            _md_table(role_progress),
            "",
            "## Exchange Progress",
            "",
            _md_table(exchange_progress, max_rows=20),
            "",
            "## Product Gap",
            "",
            _md_table(product_gap, max_rows=20),
            "",
            "## Trigger Gate",
            "",
            _md_table(trigger_gate),
            "",
            "## Operator Queue",
            "",
            _md_table(operator_queue),
            "",
            "## Stop Conditions",
            "",
            "- Stop if any expected raw, normalized, or proof file is absent.",
            "- Stop if unexpected files appear under incoming/stage152_authoritative_minute_ohlcv until operator explains or removes them.",
            "- Stop if Stage153 has not validated schema, hash, proof, and coverage.",
            "- Stop before any strategy rule, true engine, A/B, CTP, or order API.",
            "",
        ]
    )
    REPORT_OUT.write_text(text, encoding="utf-8")


def _plot_path(curve: pd.DataFrame, summary: dict[str, Any]) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(15, 11), sharex=True)
    axes[0].plot(curve["date"], curve["account_equity"], color="#1f77b4", linewidth=1.8)
    axes[0].set_title("Official Path With Stage160 Arrival Status")
    axes[0].set_ylabel("Equity")
    axes[0].grid(alpha=0.25)
    axes[0].text(
        0.01,
        0.95,
        f"arrival={summary['arrival_completion_pct']:.2f}% | complete={summary['request_complete_triplet_count']}/{summary['stage152_request_count']} | stage153_allowed={summary['stage153_trigger_allowed']}",
        transform=axes[0].transAxes,
        va="top",
        fontsize=10,
        bbox={"facecolor": "white", "edgecolor": "#cccccc", "alpha": 0.9},
    )
    axes[1].plot(curve["date"], curve["drawdown_pct"], color="#d62728", linewidth=1.3)
    axes[1].axhline(-30, color="#888888", linestyle="--", linewidth=0.9)
    axes[1].set_ylabel("Drawdown %")
    axes[1].grid(alpha=0.25)
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#9467bd", linewidth=1.2)
    axes[2].axhline(100, color="#888888", linestyle="--", linewidth=0.9)
    axes[2].set_ylabel("Broker10 %")
    axes[2].grid(alpha=0.25)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_role(role_progress: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(11, 5))
    x = np.arange(len(role_progress))
    ax.bar(x, role_progress["required_count"], color="#d9d9d9", label="required")
    ax.bar(x, role_progress["present_count"], color="#2ca02c", label="present")
    ax.set_xticks(x)
    ax.set_xticklabels(role_progress["role"].tolist())
    ax.set_title("Stage160 Expected File Role Arrival Progress")
    ax.set_ylabel("File Count")
    ax.legend()
    ax.grid(axis="y", alpha=0.25)
    for idx, row in role_progress.iterrows():
        ax.text(idx, row["required_count"] * 0.02, f"{row['present_count']}/{row['required_count']}", ha="center", va="bottom")
    fig.tight_layout()
    fig.savefig(ROLE_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_exchange(exchange_progress: pd.DataFrame) -> None:
    data = exchange_progress.sort_values("required_role_count", ascending=False).head(12).copy()
    fig, ax = plt.subplots(figsize=(13, 6))
    if data.empty:
        ax.text(0.5, 0.5, "No exchange progress data", ha="center", va="center")
        ax.axis("off")
    else:
        y = np.arange(len(data))
        ax.barh(y, data["required_role_count"], color="#d9d9d9", label="required roles")
        ax.barh(y, data["present_role_count"], color="#17becf", label="present roles")
        labels = data["exchange"].astype(str).tolist()
        ax.set_yticks(y)
        ax.set_yticklabels(labels)
        ax.invert_yaxis()
        ax.set_title("Exchange Arrival Progress")
        ax.set_xlabel("Role Files")
        ax.legend()
        ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(EXCHANGE_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_product_gap(product_gap: pd.DataFrame) -> None:
    data = product_gap.head(20).copy()
    fig, ax = plt.subplots(figsize=(13, 8))
    if data.empty:
        ax.text(0.5, 0.5, "No product gap data", ha="center", va="center")
        ax.axis("off")
    else:
        y = np.arange(len(data))
        ax.barh(y, data["missing_role_count"], color="#ff7f0e")
        labels = (data["exchange"].astype(str) + " " + data["product"].astype(str)).tolist()
        ax.set_yticks(y)
        ax.set_yticklabels(labels)
        ax.invert_yaxis()
        ax.set_title("Top Product Missing Expected Files")
        ax.set_xlabel("Missing Role Files")
        ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(PRODUCT_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_gate(trigger_gate: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(13, 7))
    matrix = trigger_gate[["pass_now"]].to_numpy(dtype=float)
    ax.imshow(matrix, aspect="auto", cmap=plt.get_cmap("RdYlGn"), vmin=0, vmax=1)
    ax.set_yticks(np.arange(len(trigger_gate)))
    ax.set_yticklabels(trigger_gate["gate_id"].tolist())
    ax.set_xticks([0])
    ax.set_xticklabels(["pass_now"])
    ax.set_title("Stage160 Trigger Gate Matrix")
    for row_idx, row in trigger_gate.iterrows():
        ax.text(0, row_idx, f"{int(row['observed'])}/{int(row['required'])}", ha="center", va="center", color="black", fontsize=9)
    fig.tight_layout()
    fig.savefig(GATE_CHART_OUT, dpi=170)
    plt.close(fig)


def main() -> None:
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    curve = _load_curve()
    metrics = _baseline_metrics(curve)
    manifest = _read_csv(STAGE152_REQUEST_TEMPLATE_IN)
    if manifest.empty:
        raise RuntimeError(f"missing Stage152 request manifest: {STAGE152_REQUEST_TEMPLATE_IN}")
    command_manifest = _read_csv(STAGE159_COMMAND_MANIFEST_IN)

    snapshot = _request_snapshot(manifest)
    role_progress = _role_progress(snapshot)
    exchange_progress = _exchange_progress(snapshot)
    product_gap = _product_gap(snapshot)
    expected_paths = {
        _expected_abs_path(value)
        for column in ROLE_COLUMNS.values()
        for value in manifest[column].dropna().astype(str).tolist()
    }
    unexpected = _unexpected_inventory(expected_paths)
    fingerprint = _snapshot_fingerprint(snapshot, unexpected)

    expected_file_count = int(len(manifest) * len(ROLE_COLUMNS))
    present_file_count = int(snapshot["present_role_count"].sum())
    complete_triplet_count = int(snapshot["request_complete_triplet"].sum())
    partial_triplet_count = int(snapshot["request_partial_triplet"].sum())
    missing_triplet_count = int(snapshot["request_missing_triplet"].sum())
    stage153_trigger_allowed = int(complete_triplet_count == len(manifest) and len(manifest) > 0 and len(unexpected) == 0)
    decision = (
        "stage160_authoritative_minute_arrival_monitor_ready_to_run_stage153_no_rule"
        if stage153_trigger_allowed
        else "stage160_authoritative_minute_arrival_monitor_waits_real_data_no_rule"
    )

    summary: dict[str, Any] = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "created_at": created_at,
        "line_id": LINE_ID,
        "decision": decision,
        "next_best_action": (
            "run_stage153_intake_validator"
            if stage153_trigger_allowed
            else "deliver_real_authoritative_minute_raw_normalized_proof_files_then_rerun_stage160"
        ),
        "incoming_root": str(INCOMING_ROOT.relative_to(REPO_DIR)),
        "incoming_root_exists": int(INCOMING_ROOT.exists()),
        "snapshot_fingerprint": fingerprint,
        "stage152_request_count": int(len(manifest)),
        "expected_file_count": expected_file_count,
        "present_expected_file_count": present_file_count,
        "missing_expected_file_count": expected_file_count - present_file_count,
        "arrival_completion_pct": (present_file_count / expected_file_count * 100.0) if expected_file_count else 0.0,
        "raw_file_present_count": int(snapshot["raw_present"].sum()),
        "missing_raw_file_count": int(len(manifest) - snapshot["raw_present"].sum()),
        "normalized_file_present_count": int(snapshot["normalized_present"].sum()),
        "missing_normalized_file_count": int(len(manifest) - snapshot["normalized_present"].sum()),
        "proof_file_present_count": int(snapshot["proof_present"].sum()),
        "missing_proof_file_count": int(len(manifest) - snapshot["proof_present"].sum()),
        "request_complete_triplet_count": complete_triplet_count,
        "request_partial_triplet_count": partial_triplet_count,
        "request_missing_triplet_count": missing_triplet_count,
        "unexpected_file_count": int(len(unexpected)),
        "observed_expected_bytes": int(snapshot["request_arrival_bytes"].sum()),
        "stage153_trigger_allowed": stage153_trigger_allowed,
        "stage156_allowed": 0,
        "stage157_allowed": 0,
        "stage158_allowed": 0,
        "readonly_feature_atlas_allowed_now": 0,
        "official_config_changed": 0,
        "strategy_rule_created": 0,
        "true_engine_run": 0,
        "true_engine_run_count": 0,
        "ab_triggered": 0,
        "order_api_called": 0,
        "ctp_connected": 0,
        "side_effect_count": 0,
        "current_package_promotion_allowed": 0,
        "true_engine_allowed": 0,
        "strategy_feature_usable": 0,
        "objective_completion_proven": 0,
        "visual_output_count": 5,
    }
    summary.update(metrics)

    operator_queue = _operator_queue(summary, command_manifest)
    trigger_gate = _trigger_gate(summary, role_progress, command_manifest)

    _write_csv(pd.DataFrame([summary]), SUMMARY_OUT)
    _write_csv(snapshot, REQUEST_SNAPSHOT_OUT)
    _write_csv(role_progress, ROLE_PROGRESS_OUT)
    _write_csv(exchange_progress, EXCHANGE_PROGRESS_OUT)
    _write_csv(product_gap, PRODUCT_GAP_OUT)
    _write_csv(unexpected, UNEXPECTED_FILE_OUT)
    _write_csv(trigger_gate, TRIGGER_GATE_OUT)
    _write_csv(operator_queue, OPERATOR_QUEUE_OUT)
    _write_json(
        DECISION_OUT,
        {
            "decision": decision,
            "summary": summary,
            "outputs": {
                "summary": SUMMARY_OUT,
                "request_snapshot": REQUEST_SNAPSHOT_OUT,
                "role_progress": ROLE_PROGRESS_OUT,
                "exchange_progress": EXCHANGE_PROGRESS_OUT,
                "product_gap": PRODUCT_GAP_OUT,
                "unexpected_file_inventory": UNEXPECTED_FILE_OUT,
                "trigger_gate": TRIGGER_GATE_OUT,
                "operator_queue": OPERATOR_QUEUE_OUT,
                "report": REPORT_OUT,
                "charts": [PATH_CHART_OUT, ROLE_CHART_OUT, EXCHANGE_CHART_OUT, PRODUCT_CHART_OUT, GATE_CHART_OUT],
            },
        },
    )
    _write_report(summary, role_progress, exchange_progress, product_gap, trigger_gate, operator_queue)
    _plot_path(curve, summary)
    _plot_role(role_progress)
    _plot_exchange(exchange_progress)
    _plot_product_gap(product_gap)
    _plot_gate(trigger_gate)

    print(json.dumps(_json_safe(summary), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
