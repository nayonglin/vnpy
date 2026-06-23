from __future__ import annotations

from datetime import datetime
import importlib.util
import json
from pathlib import Path
import shutil
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage137"
MODEL_TAG = "stage137_wave0_watch_inbox_trigger_selftest_v1"
OUTPUT_PREFIX = "qmt_roll_stage137_c9_minrisk_wave0_watch_inbox_trigger_selftest"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage137_wave0_watch_inbox_trigger_selftest"
FIXTURE_ROOT = OUTPUT_DIR / "fixture_drops"

STAGE136_TOOL = LINE_DIR / "tools" / "stage136_wave0_watch_inbox_arrival_monitor.py"
STAGE124_FILE_CONTRACT_IN = (
    LINE_DIR
    / "outputs"
    / "stage124_wave0_delivery_handoff_package"
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
CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)
FORBIDDEN_FIXTURE_DIR = (
    LINE_DIR
    / "outputs"
    / "stage131_wave0_positive_drop_supergate_audit"
    / "positive_drop"
    / "contract_positive_fixture_drop"
)

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CASE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_case_trigger_audit_{MODEL_TAG}.csv"
EXPECTATION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_expectation_audit_{MODEL_TAG}.csv"
SNAPSHOT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_case_snapshot_rows_{MODEL_TAG}.csv"
ROLE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_case_role_progress_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_selftest_status_{MODEL_TAG}.png"
CASE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_case_trigger_matrix_{MODEL_TAG}.png"
ROLE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_case_role_completeness_matrix_{MODEL_TAG}.png"
EXPECTATION_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_expectation_matrix_{MODEL_TAG}.png"

ROLE_ORDER = ["raw", "normalized_parquet", "proof"]
SYNTHETIC_CONTENT = b"stage137 synthetic trigger selftest file; not real vendor W0 data\n"


def _load_stage136() -> Any:
    spec = importlib.util.spec_from_file_location("stage136_wave0_watch_inbox_arrival_monitor", STAGE136_TOOL)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import Stage136 tool: {STAGE136_TOOL}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def _prepare_fixture_root() -> None:
    if FIXTURE_ROOT.exists():
        shutil.rmtree(FIXTURE_ROOT)
    FIXTURE_ROOT.mkdir(parents=True, exist_ok=True)


def _touch(path: Path, payload: bytes = SYNTHETIC_CONTENT) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def _contract_path(row: pd.Series) -> Path:
    rel = str(row["recommended_relative_path"]).replace("<vendor_raw_ext>", "raw")
    return Path(rel)


def _make_partial_drop(file_contract: pd.DataFrame) -> Path:
    drop = FIXTURE_ROOT / "partial_one_raw_contract_file"
    request_id = str(file_contract["request_id"].dropna().iloc[0])
    _touch(drop / "W0_pipeline_smoke" / "partial" / request_id / f"{request_id}__partial__raw.raw")
    return drop


def _make_unknown_drop() -> Path:
    drop = FIXTURE_ROOT / "unknown_only_changed"
    _touch(drop / "README_NOT_A_CONTRACT_FILE.txt", b"unknown file without request id\n")
    return drop


def _make_complete_name_only_drop(file_contract: pd.DataFrame) -> Path:
    drop = FIXTURE_ROOT / "complete_name_only_contract_files"
    required = file_contract[file_contract["required_now"].astype(int).eq(1)].copy()
    for _, row in required.iterrows():
        _touch(drop / _contract_path(row))
    return drop


def _prior_empty_for(path: Path) -> dict[str, Any]:
    return {
        "dir_state": {
            str(path): {
                "signature": "",
                "known_file_count": 0,
                "total_file_count": 0,
            }
        }
    }


def _expectation_rows(case_id: str, observed: dict[str, Any], expected: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for field, expected_value in expected.items():
        observed_value = observed.get(field)
        passed = int(str(observed_value) == str(expected_value))
        rows.append(
            {
                "case_id": case_id,
                "field": field,
                "observed": observed_value,
                "expected": expected_value,
                "pass_now": passed,
            }
        )
    return rows


def _run_case(stage136: Any, file_contract: pd.DataFrame, case: dict[str, Any]) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    snapshot, role_progress, inventory = stage136._scan_candidate_dirs(  # noqa: SLF001
        [case["drop_dir"]],
        file_contract,
        case.get("prior_state", {}),
    )
    triggers, decision, next_action = stage136._trigger_status(snapshot)  # noqa: SLF001
    row = snapshot.iloc[0] if not snapshot.empty else pd.Series(dtype=object)
    trigger_map = triggers.set_index("trigger_id")["observed"].to_dict() if not triggers.empty else {}
    observed = {
        "decision": decision,
        "changed_candidate_dir_count": int(snapshot["changed_since_prior_snapshot"].sum()) if not snapshot.empty else 0,
        "stage125_candidate_count": int(snapshot["candidate_ready_for_stage125"].sum()) if not snapshot.empty else 0,
        "candidate_ready_count": int(snapshot["candidate_ready_for_stage133"].sum()) if not snapshot.empty else 0,
        "forbidden_fixture_count": int(snapshot["under_forbidden_fixture_root"].sum()) if not snapshot.empty else 0,
        "best_known_file_count": int(snapshot["known_file_count"].max()) if not snapshot.empty else 0,
        "request_role_complete_count": int(row.get("request_role_complete_count", 0) or 0),
        "next_action": next_action,
        "stage133_release_allowed_observed": int(trigger_map.get("stage133_release_allowed_now", 0) or 0),
    }
    expectation = _expectation_rows(case["case_id"], observed, case["expected"])
    expectation_pass_count = sum(item["pass_now"] for item in expectation)
    expectation_count = len(expectation)
    case_row = {
        "case_id": case["case_id"],
        "case_description": case["description"],
        "drop_dir": str(case["drop_dir"]),
        "decision": decision,
        "next_action": next_action,
        "total_file_count": int(row.get("total_file_count", 0) or 0),
        "known_file_count": int(row.get("known_file_count", 0) or 0),
        "raw_file_count": int(row.get("raw_file_count", 0) or 0),
        "normalized_parquet_file_count": int(row.get("normalized_parquet_file_count", 0) or 0),
        "proof_file_count": int(row.get("proof_file_count", 0) or 0),
        "request_role_complete_count": int(row.get("request_role_complete_count", 0) or 0),
        "changed_candidate_dir_count": observed["changed_candidate_dir_count"],
        "stage125_candidate_count": observed["stage125_candidate_count"],
        "candidate_ready_count": observed["candidate_ready_count"],
        "forbidden_fixture_count": observed["forbidden_fixture_count"],
        "expectation_pass_count": expectation_pass_count,
        "expectation_count": expectation_count,
        "case_expectation_pass": int(expectation_pass_count == expectation_count),
        "synthetic_selftest_only": 1,
        "stage125_command_executed": 0,
        "stage133_command_executed": 0,
        "true_engine_allowed": 0,
    }
    snapshot = snapshot.copy()
    snapshot.insert(0, "case_id", case["case_id"])
    role_progress = role_progress.copy()
    role_progress.insert(0, "case_id", case["case_id"])
    return case_row, pd.DataFrame(expectation), snapshot, role_progress


def _write_report(summary: pd.DataFrame, case_audit: pd.DataFrame, expectation: pd.DataFrame) -> None:
    report = [
        f"# {STAGE} W0 watched inbox trigger selftest",
        "",
        f"- model_tag: `{MODEL_TAG}`",
        f"- decision: `{summary.iloc[0]['decision']}`",
        "- scope: synthetic trigger-boundary selftest only; no real W0 data, no Stage125/133 execution, no strategy rule, true engine, A/B, CTP, order API, or official config change.",
        "",
        "## Summary",
        "",
        _md_table(summary),
        "",
        "## Case Audit",
        "",
        _md_table(case_audit),
        "",
        "## Expectations",
        "",
        _md_table(expectation),
        "",
        "## Visual Outputs",
        "",
        f"- `{PATH_CHART_OUT.name}`",
        f"- `{CASE_CHART_OUT.name}`",
        f"- `{ROLE_CHART_OUT.name}`",
        f"- `{EXPECTATION_CHART_OUT.name}`",
    ]
    REPORT_OUT.write_text("\n".join(report) + "\n", encoding="utf-8")


def _plot_official_path(curve: pd.DataFrame, summary: pd.DataFrame) -> None:
    fig, axes = plt.subplots(4, 1, figsize=(15, 11), sharex=False)
    fig.suptitle("Stage137 W0 watched inbox trigger selftest: synthetic only, release locked", fontsize=14, fontweight="bold")
    axes[0].plot(curve["date"], curve["account_equity"] / 1_000_000, color="#1f5d4a", linewidth=1.2)
    axes[0].set_ylabel("equity (m)")
    axes[1].fill_between(curve["date"], curve["drawdown_pct"], 0, color="#C2410C", alpha=0.28)
    axes[1].set_ylabel("drawdown %")
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#3B5BDB", linewidth=1.0)
    axes[2].axhline(100, color="#333333", linestyle="--", linewidth=0.9)
    axes[2].set_ylabel("broker10 %")
    cols = [
        "selftest_pass",
        "case_count",
        "case_pass_count",
        "stage133_release_allowed_now",
    ]
    plot = summary[cols].T
    plot.columns = ["status"]
    plot.plot(kind="bar", ax=axes[3], legend=False, color="#0F766E")
    axes[3].set_title("Selftest/release status")
    axes[3].set_ylabel("count / flag")
    for ax in axes:
        ax.grid(alpha=0.25)
    fig.tight_layout(rect=[0, 0.02, 1, 0.96])
    fig.savefig(PATH_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_case_matrix(case_audit: pd.DataFrame) -> None:
    cols = [
        "changed_candidate_dir_count",
        "stage125_candidate_count",
        "candidate_ready_count",
        "forbidden_fixture_count",
        "case_expectation_pass",
    ]
    matrix = case_audit.set_index("case_id")[cols].copy()
    data = matrix.to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(10, max(4.5, len(matrix) * 0.65)))
    image = ax.imshow(np.clip(data, 0, 1), aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_title("Stage137 case trigger matrix")
    ax.set_xticks(np.arange(len(cols)))
    ax.set_xticklabels(cols, rotation=30, ha="right")
    ax.set_yticks(np.arange(len(matrix.index)))
    ax.set_yticklabels(matrix.index, fontsize=9)
    for row in range(data.shape[0]):
        for col in range(data.shape[1]):
            ax.text(col, row, int(data[row, col]), ha="center", va="center", fontsize=8)
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(CASE_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_role_matrix(role_progress: pd.DataFrame) -> None:
    pivot = role_progress.pivot_table(
        index="case_id",
        columns="artifact_role",
        values="completeness_pct",
        aggfunc="max",
        fill_value=0,
    )
    for role in ROLE_ORDER:
        if role not in pivot.columns:
            pivot[role] = 0
    pivot = pivot[ROLE_ORDER]
    data = pivot.to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(8.5, max(4.5, len(pivot) * 0.65)))
    image = ax.imshow(data, aspect="auto", cmap="RdYlGn", vmin=0, vmax=100)
    ax.set_title("Stage137 case role completeness pct")
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=25, ha="right")
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=9)
    for row in range(data.shape[0]):
        for col in range(data.shape[1]):
            ax.text(col, row, f"{data[row, col]:.0f}%", ha="center", va="center", fontsize=8)
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(ROLE_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_expectation_matrix(expectation: pd.DataFrame) -> None:
    matrix = expectation.pivot_table(index="case_id", columns="field", values="pass_now", aggfunc="min")
    matrix = matrix.fillna(1)
    data = matrix.to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(max(10, len(matrix.columns) * 1.1), max(4.5, len(matrix) * 0.65)))
    image = ax.imshow(data, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_title("Stage137 expectation pass matrix")
    ax.set_xticks(np.arange(len(matrix.columns)))
    ax.set_xticklabels(matrix.columns, rotation=30, ha="right")
    ax.set_yticks(np.arange(len(matrix.index)))
    ax.set_yticklabels(matrix.index, fontsize=9)
    for row in range(data.shape[0]):
        for col in range(data.shape[1]):
            ax.text(col, row, int(data[row, col]), ha="center", va="center", fontsize=8)
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(EXPECTATION_CHART_OUT, dpi=170)
    plt.close(fig)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _prepare_fixture_root()
    stage136 = _load_stage136()
    file_contract = _read_csv(STAGE124_FILE_CONTRACT_IN)
    if file_contract.empty:
        raise RuntimeError(f"missing file contract: {STAGE124_FILE_CONTRACT_IN}")
    curve = _load_curve()
    metrics = _baseline_metrics(curve)

    empty_dir = FIXTURE_ROOT / "empty_existing_dir"
    empty_dir.mkdir(parents=True, exist_ok=True)
    unknown_dir = _make_unknown_drop()
    partial_dir = _make_partial_drop(file_contract)
    complete_dir = _make_complete_name_only_drop(file_contract)
    cases = [
        {
            "case_id": "empty_wait",
            "description": "existing empty candidate directory should keep waiting",
            "drop_dir": empty_dir,
            "prior_state": {},
            "expected": {
                "decision": "stage136_wave0_watch_inbox_waiting_no_real_w0_no_strategy",
                "changed_candidate_dir_count": 0,
                "stage125_candidate_count": 0,
                "candidate_ready_count": 0,
                "forbidden_fixture_count": 0,
                "best_known_file_count": 0,
                "request_role_complete_count": 0,
                "stage133_release_allowed_observed": 0,
            },
        },
        {
            "case_id": "unknown_changed_wait",
            "description": "unknown-only file change should not trigger Stage125",
            "drop_dir": unknown_dir,
            "prior_state": _prior_empty_for(unknown_dir),
            "expected": {
                "decision": "stage136_wave0_watch_inbox_changed_but_no_contract_files_wait_no_strategy",
                "changed_candidate_dir_count": 1,
                "stage125_candidate_count": 0,
                "candidate_ready_count": 0,
                "forbidden_fixture_count": 0,
                "best_known_file_count": 0,
                "request_role_complete_count": 0,
                "stage133_release_allowed_observed": 0,
            },
        },
        {
            "case_id": "partial_stage125_only",
            "description": "one known raw file should suggest Stage125 only",
            "drop_dir": partial_dir,
            "prior_state": _prior_empty_for(partial_dir),
            "expected": {
                "decision": "stage136_wave0_watch_inbox_partial_drop_detected_run_stage125_only_no_strategy",
                "changed_candidate_dir_count": 1,
                "stage125_candidate_count": 1,
                "candidate_ready_count": 0,
                "forbidden_fixture_count": 0,
                "best_known_file_count": 1,
                "request_role_complete_count": 0,
                "stage133_release_allowed_observed": 0,
            },
        },
        {
            "case_id": "complete_prompt_stage133",
            "description": "name-complete synthetic drop should prompt Stage125 then Stage133, but not execute them",
            "drop_dir": complete_dir,
            "prior_state": _prior_empty_for(complete_dir),
            "expected": {
                "decision": "stage136_wave0_watch_inbox_complete_candidate_run_stage125_stage133_no_strategy",
                "changed_candidate_dir_count": 1,
                "stage125_candidate_count": 1,
                "candidate_ready_count": 1,
                "forbidden_fixture_count": 0,
                "best_known_file_count": 123,
                "request_role_complete_count": 41,
                "stage133_release_allowed_observed": 0,
            },
        },
        {
            "case_id": "forbidden_fixture_block",
            "description": "Stage131 fixture path must be treated as forbidden, regardless of files",
            "drop_dir": FORBIDDEN_FIXTURE_DIR,
            "prior_state": {},
            "expected": {
                "decision": "stage136_wave0_watch_inbox_attention_forbidden_fixture_no_strategy",
                "changed_candidate_dir_count": 0,
                "stage125_candidate_count": 0,
                "candidate_ready_count": 0,
                "forbidden_fixture_count": 1,
                "request_role_complete_count": 41,
                "stage133_release_allowed_observed": 0,
            },
        },
    ]

    case_rows: list[dict[str, Any]] = []
    expectation_frames: list[pd.DataFrame] = []
    snapshot_frames: list[pd.DataFrame] = []
    role_frames: list[pd.DataFrame] = []
    for case in cases:
        case_row, expectation, snapshot, role_progress = _run_case(stage136, file_contract, case)
        case_rows.append(case_row)
        expectation_frames.append(expectation)
        snapshot_frames.append(snapshot)
        role_frames.append(role_progress)
    case_audit = pd.DataFrame(case_rows)
    expectation = pd.concat(expectation_frames, ignore_index=True)
    snapshot_rows = pd.concat(snapshot_frames, ignore_index=True)
    role_progress = pd.concat(role_frames, ignore_index=True)

    expectation_pass_count = int(expectation["pass_now"].sum())
    expectation_count = len(expectation)
    case_pass_count = int(case_audit["case_expectation_pass"].sum())
    decision = (
        "stage137_wave0_watch_inbox_trigger_selftests_passed_no_real_data_no_strategy"
        if expectation_pass_count == expectation_count and case_pass_count == len(case_audit)
        else "stage137_wave0_watch_inbox_trigger_selftests_failed_attention_no_strategy"
    )
    summary = pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "decision": decision,
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "selftest_pass": int(decision.endswith("passed_no_real_data_no_strategy")),
                "case_count": len(case_audit),
                "case_pass_count": case_pass_count,
                "expectation_pass_count": expectation_pass_count,
                "expectation_count": expectation_count,
                "empty_wait_pass": int(case_audit.loc[case_audit["case_id"].eq("empty_wait"), "case_expectation_pass"].iloc[0]),
                "unknown_changed_wait_pass": int(
                    case_audit.loc[case_audit["case_id"].eq("unknown_changed_wait"), "case_expectation_pass"].iloc[0]
                ),
                "partial_stage125_only_pass": int(
                    case_audit.loc[case_audit["case_id"].eq("partial_stage125_only"), "case_expectation_pass"].iloc[0]
                ),
                "complete_prompt_stage133_pass": int(
                    case_audit.loc[case_audit["case_id"].eq("complete_prompt_stage133"), "case_expectation_pass"].iloc[0]
                ),
                "forbidden_fixture_block_pass": int(
                    case_audit.loc[case_audit["case_id"].eq("forbidden_fixture_block"), "case_expectation_pass"].iloc[0]
                ),
                "synthetic_complete_known_file_count": int(
                    case_audit.loc[case_audit["case_id"].eq("complete_prompt_stage133"), "known_file_count"].iloc[0]
                ),
                "synthetic_complete_request_role_complete_count": int(
                    case_audit.loc[case_audit["case_id"].eq("complete_prompt_stage133"), "request_role_complete_count"].iloc[0]
                ),
                "stage125_command_executed_count": int(case_audit["stage125_command_executed"].sum()),
                "stage133_command_executed_count": int(case_audit["stage133_command_executed"].sum()),
                "stage133_release_allowed_now": 0,
                "real_w0_data_delivered": 0,
                "real_stage112_intake_allowed_now": 0,
                "true_engine_allowed": 0,
                "strategy_feature_usable": 0,
                **metrics,
            }
        ]
    )

    _write_csv(summary, SUMMARY_OUT)
    _write_csv(case_audit, CASE_OUT)
    _write_csv(expectation, EXPECTATION_OUT)
    _write_csv(snapshot_rows, SNAPSHOT_OUT)
    _write_csv(role_progress, ROLE_OUT)
    _write_report(summary, case_audit, expectation)
    _plot_official_path(curve, summary)
    _plot_case_matrix(case_audit)
    _plot_role_matrix(role_progress)
    _plot_expectation_matrix(expectation)
    _write_json(
        DECISION_OUT,
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "decision": decision,
            "outputs": {
                "summary": str(SUMMARY_OUT),
                "case_audit": str(CASE_OUT),
                "expectation": str(EXPECTATION_OUT),
                "snapshots": str(SNAPSHOT_OUT),
                "role_progress": str(ROLE_OUT),
                "report": str(REPORT_OUT),
                "charts": [str(PATH_CHART_OUT), str(CASE_CHART_OUT), str(ROLE_CHART_OUT), str(EXPECTATION_CHART_OUT)],
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
