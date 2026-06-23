from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage136"
MODEL_TAG = "stage136_wave0_watch_inbox_arrival_monitor_v1"
OUTPUT_PREFIX = "qmt_roll_stage136_c9_minrisk_wave0_watch_inbox_arrival_monitor"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage136_wave0_watch_inbox_arrival_monitor"

STAGE124_DIR = LINE_DIR / "outputs" / "stage124_wave0_delivery_handoff_package"
STAGE124_FILE_CONTRACT_IN = (
    STAGE124_DIR
    / "qmt_roll_stage124_c9_minrisk_wave0_delivery_handoff_package_delivery_file_contract_"
    "stage124_wave0_delivery_handoff_package_v1.csv"
)
STAGE134_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage134_wave0_total_gate_cli_entry_selftest"
    / "qmt_roll_stage134_c9_minrisk_wave0_total_gate_cli_entry_selftest_summary_"
    "stage134_wave0_total_gate_cli_entry_selftest_v1.csv"
)
STAGE135_CANDIDATE_DIRS_IN = (
    LINE_DIR
    / "outputs"
    / "stage135_wave0_real_drop_operator_pack"
    / "qmt_roll_stage135_c9_minrisk_wave0_real_drop_operator_pack_candidate_drop_dir_audit_"
    "stage135_wave0_real_drop_operator_pack_v1.csv"
)
CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)

STAGE125_TOOL = LINE_DIR / "tools" / "stage125_wave0_receipt_preflight_audit.py"
STAGE133_TOOL = LINE_DIR / "tools" / "stage133_wave0_total_intake_downstream_gate_audit.py"
FORBIDDEN_FIXTURE_DIR = (
    LINE_DIR
    / "outputs"
    / "stage131_wave0_positive_drop_supergate_audit"
    / "positive_drop"
    / "contract_positive_fixture_drop"
)

DEFAULT_CANDIDATE_DROP_DIRS = [
    LINE_DIR / "inputs" / "w0_real_drop",
    LINE_DIR / "inputs" / "authorized_w0_real_drop",
    LINE_DIR / "data" / "w0_real_drop",
    LINE_DIR / "data" / "authorized_w0_real_drop",
    LINE_DIR / "incoming" / "w0_real_drop",
]

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
SNAPSHOT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_candidate_inbox_snapshot_{MODEL_TAG}.csv"
ROLE_PROGRESS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_candidate_role_progress_{MODEL_TAG}.csv"
FILE_INVENTORY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_file_inventory_{MODEL_TAG}.csv"
TRIGGER_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_watch_trigger_status_{MODEL_TAG}.csv"
HISTORY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_watch_history_{MODEL_TAG}.csv"
STATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_latest_watch_state_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_watch_status_{MODEL_TAG}.png"
SNAPSHOT_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_candidate_snapshot_progress_{MODEL_TAG}.png"
ROLE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_role_progress_matrix_{MODEL_TAG}.png"
TRIGGER_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_watch_trigger_chart_{MODEL_TAG}.png"

REQUEST_RE = re.compile(r"stage114_req_\d{4}")
RAW_SUFFIXES = {".raw", ".dbn", ".dat", ".bin", ".gz", ".zip"}
ROLE_ORDER = ["raw", "normalized_parquet", "proof"]


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


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists() or path.stat().st_size == 0:
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


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


def _load_curve() -> pd.DataFrame:
    curve = _read_csv(CURVE_IN)
    if curve.empty:
        raise RuntimeError(f"missing curve input: {CURVE_IN}")
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]:
        curve[column] = pd.to_numeric(curve[column], errors="coerce")
    return curve[curve["date"].notna()].sort_values("date").reset_index(drop=True)


def _baseline_metrics(curve: pd.DataFrame) -> dict[str, float]:
    stage134 = _read_csv(STAGE134_SUMMARY_IN)
    if not stage134.empty:
        row = stage134.iloc[0]
        return {
            "end_equity": float(row.get("end_equity", np.nan)),
            "total_return_pct": float(row.get("total_return_pct", np.nan)),
            "max_drawdown_pct": float(row.get("max_drawdown_pct", np.nan)),
            "sharpe": float(row.get("sharpe", np.nan)),
            "total_slippage": float(row.get("total_slippage", np.nan)),
            "total_trade_count": float(row.get("total_trade_count", np.nan)),
            "closed_lot_win_rate_pct": float(row.get("closed_lot_win_rate_pct", np.nan)),
            "max_broker10_margin_to_equity_pct": float(row.get("max_broker10_margin_to_equity_pct", np.nan)),
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


def _role_for_file(path: Path) -> str:
    parts = {part.lower() for part in path.parts}
    name = path.name.lower()
    suffix = "".join(path.suffixes).lower()
    if path.suffix.lower() == ".parquet" or "parquet" in parts or "normalized" in name:
        return "normalized_parquet"
    if path.suffix.lower() == ".json" and ("proof" in parts or "proof" in name):
        return "proof"
    if "raw" in parts or "raw" in name or path.suffix.lower() in RAW_SUFFIXES or suffix.endswith(".csv.gz"):
        return "raw"
    return "ignored"


def _request_id_for_path(path: Path) -> str:
    match = REQUEST_RE.search(str(path))
    return match.group(0) if match else ""


def _path_inside(child: Path, parent: Path) -> int:
    try:
        child.resolve().relative_to(parent.resolve())
        return 1
    except ValueError:
        return 0


def _load_candidate_dirs(extra_dirs: list[str]) -> list[Path]:
    dirs: list[Path] = []
    stage135 = _read_csv(STAGE135_CANDIDATE_DIRS_IN)
    if not stage135.empty and "drop_dir" in stage135:
        dirs.extend(Path(value) for value in stage135["drop_dir"].dropna().astype(str).tolist())
    else:
        dirs.extend(DEFAULT_CANDIDATE_DROP_DIRS)
    dirs.extend(Path(value) for value in extra_dirs)
    unique: list[Path] = []
    seen: set[str] = set()
    for path in dirs:
        resolved = path if path.is_absolute() else (REPO_DIR / path)
        key = str(resolved)
        if key not in seen:
            seen.add(key)
            unique.append(resolved)
    return unique


def _scan_files(drop_dir: Path, expected_request_ids: set[str]) -> tuple[list[dict[str, Any]], str, int, str]:
    files = sorted(path for path in drop_dir.rglob("*") if path.is_file()) if drop_dir.exists() else []
    hasher = hashlib.sha256()
    newest_mtime = 0
    newest_mtime_text = ""
    rows: list[dict[str, Any]] = []
    for path in files:
        stat = path.stat()
        newest_mtime = max(newest_mtime, int(stat.st_mtime))
        rel = path.relative_to(drop_dir)
        hasher.update(f"{rel}|{stat.st_size}|{stat.st_mtime_ns}\n".encode("utf-8"))
        role = _role_for_file(path)
        request_id = _request_id_for_path(path)
        rows.append(
            {
                "drop_dir": str(drop_dir),
                "relative_path": str(rel),
                "path": str(path),
                "file_name": path.name,
                "bytes": int(stat.st_size),
                "modified_at": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                "request_id": request_id,
                "role": role,
                "known_contract_file": int(role in ROLE_ORDER and request_id in expected_request_ids),
            }
        )
    if newest_mtime:
        newest_mtime_text = datetime.fromtimestamp(newest_mtime).strftime("%Y-%m-%d %H:%M:%S")
    signature = hasher.hexdigest() if files else ""
    return rows, signature, newest_mtime, newest_mtime_text


def _scan_candidate_dirs(
    candidate_dirs: list[Path],
    file_contract: pd.DataFrame,
    prior_state: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    expected_request_ids = set(file_contract["request_id"].dropna().astype(str)) if "request_id" in file_contract else set()
    expected_request_count = len(expected_request_ids)
    expected_file_count = int(file_contract["required_now"].sum()) if "required_now" in file_contract else 0
    prior_dirs = prior_state.get("dir_state", {}) if isinstance(prior_state.get("dir_state", {}), dict) else {}
    dir_rows: list[dict[str, Any]] = []
    role_rows: list[dict[str, Any]] = []
    inventory_rows: list[dict[str, Any]] = []
    for drop_dir in candidate_dirs:
        rows, signature, newest_mtime, newest_mtime_text = _scan_files(drop_dir, expected_request_ids)
        inventory_rows.extend(rows)
        inventory = pd.DataFrame(rows)
        known = inventory[inventory["known_contract_file"].eq(1)] if not inventory.empty else pd.DataFrame()
        role_counts = known["role"].value_counts().to_dict() if not known.empty else {}
        request_role_complete = 0
        partial_request_count = 0
        if not known.empty:
            pivot = known.pivot_table(index="request_id", columns="role", values="path", aggfunc="count", fill_value=0)
            for role in ROLE_ORDER:
                if role not in pivot.columns:
                    pivot[role] = 0
            complete_mask = pivot[ROLE_ORDER].ge(1).all(axis=1)
            request_role_complete = int(complete_mask.sum())
            partial_request_count = int((~complete_mask).sum())
        forbidden_fixture = _path_inside(drop_dir, FORBIDDEN_FIXTURE_DIR) or _path_inside(FORBIDDEN_FIXTURE_DIR, drop_dir)
        prior = prior_dirs.get(str(drop_dir), {}) if isinstance(prior_dirs.get(str(drop_dir), {}), dict) else {}
        prior_signature = str(prior.get("signature", ""))
        prior_known_file_count = int(prior.get("known_file_count", 0) or 0)
        prior_total_file_count = int(prior.get("total_file_count", 0) or 0)
        prior_available = int(bool(prior_state))
        changed = int(prior_available and signature != prior_signature)
        known_delta = int(len(known)) - prior_known_file_count if prior_available else 0
        total_delta = len(rows) - prior_total_file_count if prior_available else 0
        candidate_ready = int(
            drop_dir.exists()
            and int(len(known)) >= expected_file_count
            and request_role_complete >= expected_request_count
            and not forbidden_fixture
        )
        dir_rows.append(
            {
                "drop_dir": str(drop_dir),
                "exists": int(drop_dir.exists()),
                "total_file_count": len(rows),
                "known_file_count": int(len(known)),
                "expected_file_count": expected_file_count,
                "known_file_completeness_pct": (int(len(known)) / expected_file_count * 100.0) if expected_file_count else 0.0,
                "unknown_file_count": int(len(inventory) - len(known)) if not inventory.empty else 0,
                "raw_file_count": int(role_counts.get("raw", 0)),
                "normalized_parquet_file_count": int(role_counts.get("normalized_parquet", 0)),
                "proof_file_count": int(role_counts.get("proof", 0)),
                "request_count_with_any_role": int(known["request_id"].nunique()) if not known.empty else 0,
                "request_role_complete_count": request_role_complete,
                "partial_request_count": partial_request_count,
                "expected_request_count": expected_request_count,
                "newest_mtime": newest_mtime_text,
                "signature": signature,
                "prior_signature": prior_signature,
                "changed_since_prior_snapshot": changed,
                "known_file_count_delta": known_delta,
                "total_file_count_delta": total_delta,
                "under_forbidden_fixture_root": int(forbidden_fixture),
                "candidate_ready_for_stage125": int(drop_dir.exists() and int(len(known)) > 0 and not forbidden_fixture),
                "candidate_ready_for_stage133": candidate_ready,
            }
        )
        for role in ROLE_ORDER:
            observed = int(role_counts.get(role, 0))
            role_rows.append(
                {
                    "drop_dir": str(drop_dir),
                    "artifact_role": role,
                    "observed_count": observed,
                    "expected_count": expected_request_count,
                    "completeness_pct": (observed / expected_request_count * 100.0) if expected_request_count else 0.0,
                    "pass_now": int(observed >= expected_request_count and expected_request_count > 0),
                }
            )
    return pd.DataFrame(dir_rows), pd.DataFrame(role_rows), pd.DataFrame(inventory_rows)


def _trigger_status(snapshot: pd.DataFrame) -> tuple[pd.DataFrame, str, str]:
    best_known = int(snapshot["known_file_count"].max()) if not snapshot.empty else 0
    candidate_ready = int(snapshot["candidate_ready_for_stage133"].sum()) if not snapshot.empty else 0
    stage125_ready = int(snapshot["candidate_ready_for_stage125"].sum()) if not snapshot.empty else 0
    forbidden = int(snapshot["under_forbidden_fixture_root"].sum()) if not snapshot.empty else 0
    changed = int(snapshot["changed_since_prior_snapshot"].sum()) if not snapshot.empty else 0
    if forbidden:
        decision = "stage136_wave0_watch_inbox_attention_forbidden_fixture_no_strategy"
        next_action = "remove forbidden fixture path from real candidate list; do not run downstream gates"
    elif candidate_ready:
        decision = "stage136_wave0_watch_inbox_complete_candidate_run_stage125_stage133_no_strategy"
        next_action = "run Stage125 receipt preflight, then Stage133 total release verdict with expected downstream release"
    elif stage125_ready:
        decision = "stage136_wave0_watch_inbox_partial_drop_detected_run_stage125_only_no_strategy"
        next_action = "run Stage125 receipt preflight only; do not run Stage133 release until 123/123 files are complete"
    elif changed:
        decision = "stage136_wave0_watch_inbox_changed_but_no_contract_files_wait_no_strategy"
        next_action = "inspect new non-contract files manually; keep Stage112/113 locked"
    else:
        decision = "stage136_wave0_watch_inbox_waiting_no_real_w0_no_strategy"
        next_action = "wait for a real W0 drop under one candidate directory"
    rows = [
        {
            "trigger_id": "monitor_snapshot_ready",
            "observed": 1,
            "required": 1,
            "pass_now": 1,
            "severity": "monitor_hard",
        },
        {
            "trigger_id": "candidate_dir_changed_since_prior",
            "observed": changed,
            "required": ">=1 only means inspect, not release",
            "pass_now": int(changed > 0),
            "severity": "watch_info",
        },
        {
            "trigger_id": "stage125_preflight_candidate_present",
            "observed": stage125_ready,
            "required": ">=1 real candidate with known contract files",
            "pass_now": int(stage125_ready > 0),
            "severity": "data_watch",
        },
        {
            "trigger_id": "stage133_release_candidate_complete",
            "observed": candidate_ready,
            "required": ">=1 candidate with 123/123 known files and 41 complete requests",
            "pass_now": int(candidate_ready > 0),
            "severity": "data_hard",
        },
        {
            "trigger_id": "forbidden_fixture_absent",
            "observed": forbidden,
            "required": 0,
            "pass_now": int(forbidden == 0),
            "severity": "anti_selection_hard",
        },
        {
            "trigger_id": "stage133_release_allowed_now",
            "observed": 0,
            "required": "0 until Stage133 returns ready_for_stage112_113_minutes_research",
            "pass_now": 1,
            "severity": "anti_selection_hard",
        },
        {
            "trigger_id": "best_known_file_count",
            "observed": best_known,
            "required": 123,
            "pass_now": int(best_known >= 123),
            "severity": "data_progress",
        },
    ]
    return pd.DataFrame(rows), decision, next_action


def _state_payload(snapshot_id: str, snapshot: pd.DataFrame, summary: pd.DataFrame) -> dict[str, Any]:
    dir_state: dict[str, Any] = {}
    for _, row in snapshot.iterrows():
        dir_state[str(row["drop_dir"])] = {
            "exists": int(row["exists"]),
            "total_file_count": int(row["total_file_count"]),
            "known_file_count": int(row["known_file_count"]),
            "request_role_complete_count": int(row["request_role_complete_count"]),
            "signature": str(row["signature"]),
            "newest_mtime": str(row["newest_mtime"]),
        }
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "snapshot_id": snapshot_id,
        "created_at": summary.iloc[0]["created_at"],
        "decision": summary.iloc[0]["decision"],
        "dir_state": dir_state,
    }


def _append_history(summary: pd.DataFrame) -> pd.DataFrame:
    previous = _read_csv(HISTORY_OUT)
    history = pd.concat([previous, summary], ignore_index=True) if not previous.empty else summary.copy()
    _write_csv(history, HISTORY_OUT)
    return history


def _write_report(summary: pd.DataFrame, snapshot: pd.DataFrame, role_progress: pd.DataFrame, triggers: pd.DataFrame) -> None:
    report = [
        f"# {STAGE} W0 watched inbox arrival monitor",
        "",
        f"- model_tag: `{MODEL_TAG}`",
        f"- decision: `{summary.iloc[0]['decision']}`",
        "- scope: poll-style arrival snapshot and next-action digest only; no strategy rule, true engine, A/B, CTP, order API, or official config change.",
        "",
        "## Summary",
        "",
        _md_table(summary),
        "",
        "## Candidate Inbox Snapshot",
        "",
        _md_table(snapshot),
        "",
        "## Role Progress",
        "",
        _md_table(role_progress),
        "",
        "## Trigger Status",
        "",
        _md_table(triggers),
        "",
        "## Commands When Triggered",
        "",
        "- Stage125 only for partial or complete real drops:",
        f"  - `.py311/bin/python {STAGE125_TOOL.relative_to(REPO_DIR)} --drop-dir <real_w0_drop> --case-id real_w0_receipt_preflight`",
        "- Stage133 only after the drop appears complete:",
        (
            f"  - `.py311/bin/python {STAGE133_TOOL.relative_to(REPO_DIR)} --drop-dir <real_w0_drop> "
            "--case-id real_w0_total_gate --expected-stage112-intake 1 --expected-downstream-release 1`"
        ),
        "",
        "## Visual Outputs",
        "",
        f"- `{PATH_CHART_OUT.name}`",
        f"- `{SNAPSHOT_CHART_OUT.name}`",
        f"- `{ROLE_CHART_OUT.name}`",
        f"- `{TRIGGER_CHART_OUT.name}`",
    ]
    REPORT_OUT.write_text("\n".join(report) + "\n", encoding="utf-8")


def _plot_official_path(curve: pd.DataFrame, summary: pd.DataFrame) -> None:
    fig, axes = plt.subplots(4, 1, figsize=(15, 11), sharex=False)
    fig.suptitle("Stage136 W0 watched inbox: data arrival monitor, release locked", fontsize=14, fontweight="bold")
    axes[0].plot(curve["date"], curve["account_equity"] / 1_000_000, color="#1f5d4a", linewidth=1.2)
    axes[0].set_ylabel("equity (m)")
    axes[1].fill_between(curve["date"], curve["drawdown_pct"], 0, color="#C2410C", alpha=0.28)
    axes[1].set_ylabel("drawdown %")
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#3B5BDB", linewidth=1.0)
    axes[2].axhline(100, color="#333333", linestyle="--", linewidth=0.9)
    axes[2].set_ylabel("broker10 %")
    cols = [
        "monitor_ready",
        "arrival_detected_now",
        "candidate_ready_count",
        "stage133_release_allowed_now",
    ]
    plot = summary[cols].T
    plot.columns = ["status"]
    colors = ["#0F766E", "#2563EB", "#C2410C", "#7F1D1D"]
    plot.plot(kind="bar", ax=axes[3], legend=False, color=colors)
    axes[3].set_ylim(0, max(1.2, float(plot["status"].max()) + 0.5))
    axes[3].set_title("Watch/release status")
    axes[3].set_ylabel("count / flag")
    for ax in axes:
        ax.grid(alpha=0.25)
    fig.tight_layout(rect=[0, 0.02, 1, 0.96])
    fig.savefig(PATH_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_snapshot(snapshot: pd.DataFrame) -> None:
    view = snapshot.copy()
    def label_for_path(value: str) -> str:
        path = Path(str(value))
        try:
            return str(path.relative_to(LINE_DIR))
        except ValueError:
            return str(path)

    view["label"] = view["drop_dir"].map(label_for_path)
    fig, ax = plt.subplots(figsize=(14, max(5, len(view) * 0.65)))
    y = np.arange(len(view))
    ax.barh(y, view["expected_file_count"], color="#D1D5DB", label="expected")
    ax.barh(y, view["known_file_count"], color="#0F766E", label="known")
    ax.set_yticks(y)
    ax.set_yticklabels(view["label"], fontsize=9)
    ax.set_xlabel("file count")
    ax.set_title("Stage136 candidate inbox file progress")
    ax.legend()
    for row, (_, item) in enumerate(view.iterrows()):
        ax.text(
            float(item["known_file_count"]) + 1,
            row,
            f"{int(item['known_file_count'])}/{int(item['expected_file_count'])}",
            va="center",
            fontsize=8,
        )
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(SNAPSHOT_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_role_matrix(role_progress: pd.DataFrame) -> None:
    data = role_progress.pivot_table(
        index="drop_dir",
        columns="artifact_role",
        values="completeness_pct",
        aggfunc="max",
        fill_value=0,
    )
    for role in ROLE_ORDER:
        if role not in data.columns:
            data[role] = 0
    data = data[ROLE_ORDER]
    values = data.to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(9, max(5, len(data) * 0.6)))
    image = ax.imshow(values, aspect="auto", cmap="RdYlGn", vmin=0, vmax=100)
    ax.set_title("Stage136 role completeness pct")
    ax.set_xticks(np.arange(len(data.columns)))
    ax.set_xticklabels(data.columns, rotation=25, ha="right")
    ax.set_yticks(np.arange(len(data.index)))
    labels: list[str] = []
    for index in data.index:
        path = Path(str(index))
        try:
            labels.append(str(path.relative_to(LINE_DIR)))
        except ValueError:
            labels.append(str(path))
    ax.set_yticklabels(labels, fontsize=9)
    for row in range(values.shape[0]):
        for col in range(values.shape[1]):
            ax.text(col, row, f"{values[row, col]:.0f}%", ha="center", va="center", fontsize=8)
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(ROLE_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_triggers(triggers: pd.DataFrame) -> None:
    values = pd.to_numeric(triggers["pass_now"], errors="coerce").fillna(0).to_numpy(dtype=float).reshape(-1, 1)
    fig, ax = plt.subplots(figsize=(9, max(5, len(triggers) * 0.58)))
    image = ax.imshow(values, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_title("Stage136 watch trigger status")
    ax.set_xticks([0])
    ax.set_xticklabels(["pass_now"], rotation=25, ha="right")
    ax.set_yticks(np.arange(len(triggers)))
    ax.set_yticklabels(triggers["trigger_id"], fontsize=9)
    for row in range(values.shape[0]):
        ax.text(0, row, int(values[row, 0]), ha="center", va="center", fontsize=9)
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(TRIGGER_CHART_OUT, dpi=170)
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage136 W0 watched inbox arrival monitor.")
    parser.add_argument(
        "--candidate-dir",
        action="append",
        default=[],
        help="Extra candidate real W0 drop directory to scan. May be provided multiple times.",
    )
    parser.add_argument(
        "--no-state-update",
        action="store_true",
        help="Do not write latest watch state or append history. Useful for dry-run inspection.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    curve = _load_curve()
    metrics = _baseline_metrics(curve)
    file_contract = _read_csv(STAGE124_FILE_CONTRACT_IN)
    candidate_dirs = _load_candidate_dirs(args.candidate_dir)
    prior_state = _read_json(STATE_OUT)
    snapshot, role_progress, inventory = _scan_candidate_dirs(candidate_dirs, file_contract, prior_state)
    triggers, decision, next_action = _trigger_status(snapshot)

    expected_file_count = int(file_contract["required_now"].sum()) if not file_contract.empty and "required_now" in file_contract else 0
    best_known_file_count = int(snapshot["known_file_count"].max()) if not snapshot.empty else 0
    candidate_ready_count = int(snapshot["candidate_ready_for_stage133"].sum()) if not snapshot.empty else 0
    stage125_candidate_count = int(snapshot["candidate_ready_for_stage125"].sum()) if not snapshot.empty else 0
    changed_count = int(snapshot["changed_since_prior_snapshot"].sum()) if not snapshot.empty else 0
    prior_snapshot_available = int(bool(prior_state))
    monitor_ready = int(len(file_contract) == 123 and len(candidate_dirs) >= 5 and STAGE125_TOOL.exists() and STAGE133_TOOL.exists())

    summary = pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "snapshot_id": snapshot_id,
                "line_id": LINE_ID,
                "decision": decision,
                "recommended_next_action": next_action,
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "monitor_ready": monitor_ready,
                "prior_snapshot_available": prior_snapshot_available,
                "candidate_dir_count": len(candidate_dirs),
                "existing_candidate_dir_count": int(snapshot["exists"].sum()) if not snapshot.empty else 0,
                "changed_candidate_dir_count": changed_count,
                "stage125_candidate_count": stage125_candidate_count,
                "candidate_ready_count": candidate_ready_count,
                "arrival_detected_now": int(best_known_file_count > 0),
                "best_known_file_count": best_known_file_count,
                "expected_file_count": expected_file_count,
                "best_completeness_pct": (best_known_file_count / expected_file_count * 100.0) if expected_file_count else 0.0,
                "stage133_release_allowed_now": 0,
                "real_w0_data_delivered": int(candidate_ready_count > 0),
                "real_stage112_intake_allowed_now": 0,
                "true_engine_allowed": 0,
                "strategy_feature_usable": 0,
                **metrics,
            }
        ]
    )

    _write_csv(summary, SUMMARY_OUT)
    _write_csv(snapshot, SNAPSHOT_OUT)
    _write_csv(role_progress, ROLE_PROGRESS_OUT)
    _write_csv(inventory, FILE_INVENTORY_OUT)
    _write_csv(triggers, TRIGGER_OUT)
    if not args.no_state_update:
        _append_history(summary)
        _write_json(STATE_OUT, _state_payload(snapshot_id, snapshot, summary))
    _write_report(summary, snapshot, role_progress, triggers)
    _plot_official_path(curve, summary)
    _plot_snapshot(snapshot)
    _plot_role_matrix(role_progress)
    _plot_triggers(triggers)
    _write_json(
        DECISION_OUT,
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "decision": decision,
            "recommended_next_action": next_action,
            "snapshot_id": snapshot_id,
            "outputs": {
                "summary": str(SUMMARY_OUT),
                "snapshot": str(SNAPSHOT_OUT),
                "role_progress": str(ROLE_PROGRESS_OUT),
                "file_inventory": str(FILE_INVENTORY_OUT),
                "triggers": str(TRIGGER_OUT),
                "history": str(HISTORY_OUT),
                "state": str(STATE_OUT),
                "report": str(REPORT_OUT),
                "charts": [str(PATH_CHART_OUT), str(SNAPSHOT_CHART_OUT), str(ROLE_CHART_OUT), str(TRIGGER_CHART_OUT)],
            },
            "locks": {
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "true_engine_allowed": 0,
                "strategy_feature_usable": 0,
            },
        },
    )
    print(json.dumps(_json_safe(summary.iloc[0].to_dict()), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
