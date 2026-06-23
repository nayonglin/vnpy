from __future__ import annotations

from datetime import datetime
import importlib.util
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage161"
MODEL_TAG = "stage161_authoritative_minute_source_arbitration_v1"
OUTPUT_PREFIX = "qmt_roll_stage161_c9_minrisk_authoritative_minute_source_arbitration"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage161_authoritative_minute_source_arbitration"

CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)

STAGE151_ROUTE_IN = (
    LINE_DIR
    / "outputs"
    / "stage151_point_in_time_external_source_router"
    / "qmt_roll_stage151_c9_minrisk_point_in_time_external_source_router_source_route_scorecard_"
    "stage151_point_in_time_external_source_router_v1.csv"
)
STAGE160_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage160_authoritative_minute_arrival_monitor"
    / "qmt_roll_stage160_c9_minrisk_authoritative_minute_arrival_monitor_summary_"
    "stage160_authoritative_minute_arrival_monitor_v1.csv"
)
STAGE033_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage033_tick_source_feasibility_audit"
    / "qmt_roll_stage033_c9_minrisk_tick_source_feasibility_audit_summary_"
    "stage033_tick_source_feasibility_audit_v1.csv"
)
STAGE107_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage107_contract_month_oi_patched_root_reaudit"
    / "qmt_roll_stage107_c9_minrisk_contract_month_oi_patched_root_reaudit_summary_"
    "stage107_contract_month_oi_patched_root_reaudit_v1.csv"
)
STAGE114_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage114_microstructure_procurement_request_bundle"
    / "qmt_roll_stage114_c9_minrisk_microstructure_procurement_request_bundle_summary_"
    "stage114_microstructure_procurement_request_bundle_v1.csv"
)

EX_STAGE859_SOURCE_IN = (
    REPO_DIR
    / "examples"
    / "portfolio_backtesting"
    / "backtest_outputs"
    / "qmt_roll_stage859_stage856_tqsdk_backtest_gap_backfill_source_readiness_"
    "stage859_stage856_tqsdk_backtest_gap_backfill_v1.csv"
)
EX_STAGE859_SUMMARY_IN = (
    REPO_DIR
    / "examples"
    / "portfolio_backtesting"
    / "backtest_outputs"
    / "qmt_roll_stage859_stage856_tqsdk_backtest_gap_backfill_summary_"
    "stage859_stage856_tqsdk_backtest_gap_backfill_v1.csv"
)
EX_STAGE861_SUMMARY_IN = (
    REPO_DIR
    / "examples"
    / "portfolio_backtesting"
    / "backtest_outputs"
    / "qmt_roll_stage861_stage860_full_visual_atlas_summary_stage861_stage860_full_visual_atlas_v1.csv"
)
EX_STAGE861_BARS_IN = (
    REPO_DIR
    / "examples"
    / "portfolio_backtesting"
    / "backtest_outputs"
    / "qmt_roll_stage861_stage860_full_visual_atlas_full_minute_bars_stage861_stage860_full_visual_atlas_v1.csv"
)
EX_STAGE445_COVERAGE_IN = (
    REPO_DIR
    / "examples"
    / "portfolio_backtesting"
    / "backtest_outputs"
    / "qmt_roll_stage445_tqsdk_priority_minute_probe_coverage_summary_stage445_tqsdk_priority_minute_probe_v1.csv"
)
EX_STAGE446_COVERAGE_IN = (
    REPO_DIR
    / "examples"
    / "portfolio_backtesting"
    / "backtest_outputs"
    / "qmt_roll_stage446_tqsdk_backtest_minute_proxy_extract_coverage_summary_stage446_tqsdk_backtest_minute_proxy_extract_v1.csv"
)

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
SOURCE_ARBITRATION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_arbitration_{MODEL_TAG}.csv"
ARTIFACT_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_local_artifact_audit_{MODEL_TAG}.csv"
MIGRATION_REQUIREMENTS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_migration_requirements_{MODEL_TAG}.csv"
GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_source_status_{MODEL_TAG}.png"
SOURCE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_eligibility_matrix_{MODEL_TAG}.png"
SCORE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_score_bar_{MODEL_TAG}.png"
ARTIFACT_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_local_artifact_size_coverage_{MODEL_TAG}.png"
GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_matrix_{MODEL_TAG}.png"


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


def _read_csv(path: Path, nrows: int | None = None) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size <= 4:
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig", nrows=nrows)


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
    stage160 = _row(STAGE160_SUMMARY_IN)
    if stage160:
        return {
            "end_equity": _num(stage160, "end_equity", np.nan),
            "total_return_pct": _num(stage160, "total_return_pct", np.nan),
            "max_drawdown_pct": _num(stage160, "max_drawdown_pct", np.nan),
            "sharpe": _num(stage160, "sharpe", np.nan),
            "total_slippage": _num(stage160, "total_slippage", np.nan),
            "total_trade_count": _num(stage160, "total_trade_count", np.nan),
            "closed_lot_win_rate_pct": _num(stage160, "closed_lot_win_rate_pct", np.nan),
            "max_broker10_margin_to_equity_pct": _num(stage160, "max_broker10_margin_to_equity_pct", np.nan),
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


def _module_installed(name: str) -> int:
    return int(importlib.util.find_spec(name) is not None)


def _source_status_from_stage859(source_readiness: pd.DataFrame, source: str) -> tuple[int, str]:
    if source_readiness.empty:
        return 0, ""
    hit = source_readiness[source_readiness["source"].astype(str).eq(source)]
    if hit.empty:
        return 0, ""
    row = hit.iloc[0]
    return int(str(row.get("status", "")).lower() in {"installed", "available"}), str(row.get("version", ""))


def _artifact_row(path: Path, artifact_id: str, owner_line: str, artifact_type: str, row_hint: int | None = None) -> dict[str, Any]:
    exists = int(path.exists())
    size = int(path.stat().st_size) if exists else 0
    row_count = row_hint
    if exists and row_hint is None and size < 10_000_000 and path.suffix.lower() == ".csv":
        try:
            row_count = len(pd.read_csv(path, encoding="utf-8-sig"))
        except Exception:
            row_count = None
    return {
        "artifact_id": artifact_id,
        "owner_line": owner_line,
        "artifact_type": artifact_type,
        "path": str(path.relative_to(REPO_DIR)) if path.exists() or str(path).startswith(str(REPO_DIR)) else str(path),
        "exists": exists,
        "size_mb": size / 1024.0 / 1024.0,
        "row_count": row_count if row_count is not None else "",
        "line_scope_compatible": int(owner_line == LINE_ID),
    }


def _artifact_audit() -> pd.DataFrame:
    stage859 = _row(EX_STAGE859_SUMMARY_IN)
    stage861 = _row(EX_STAGE861_SUMMARY_IN)
    rows = [
        _artifact_row(STAGE160_SUMMARY_IN, "stage160_current_line_arrival_summary", LINE_ID, "current_line_summary"),
        _artifact_row(STAGE151_ROUTE_IN, "stage151_current_line_source_scorecard", LINE_ID, "current_line_scorecard"),
        _artifact_row(STAGE033_SUMMARY_IN, "stage033_current_line_tqsdk_tick_feasibility", LINE_ID, "current_line_summary"),
        _artifact_row(STAGE107_SUMMARY_IN, "stage107_current_line_oi_panel", LINE_ID, "current_line_summary"),
        _artifact_row(STAGE114_SUMMARY_IN, "stage114_current_line_w0_procurement", LINE_ID, "current_line_summary"),
        _artifact_row(EX_STAGE859_SOURCE_IN, "stage859_other_line_source_readiness", "futures_trend_stage819_intraday_rules", "other_line_summary"),
        _artifact_row(EX_STAGE859_SUMMARY_IN, "stage859_other_line_tqsdk_backfill_summary", "futures_trend_stage819_intraday_rules", "other_line_summary"),
        _artifact_row(EX_STAGE861_SUMMARY_IN, "stage861_other_line_full_minute_summary", "futures_trend_stage819_intraday_rules", "other_line_summary"),
        _artifact_row(
            EX_STAGE861_BARS_IN,
            "stage861_other_line_full_minute_bars",
            "futures_trend_stage819_intraday_rules",
            "other_line_large_minute_csv",
            _int(stage861, "full_minute_bars", 0) if stage861 else None,
        ),
        _artifact_row(
            EX_STAGE445_COVERAGE_IN,
            "stage445_other_line_tqsdk_direct_probe",
            "examples_portfolio_backtesting",
            "other_line_probe",
        ),
        _artifact_row(
            EX_STAGE446_COVERAGE_IN,
            "stage446_other_line_tqbacktest_probe",
            "examples_portfolio_backtesting",
            "other_line_probe",
        ),
    ]
    if stage859:
        rows.append(
            {
                "artifact_id": "stage859_other_line_minute_rows",
                "owner_line": "futures_trend_stage819_intraday_rules",
                "artifact_type": "other_line_derived_metric",
                "path": "examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage859_*",
                "exists": 1,
                "size_mb": np.nan,
                "row_count": _int(stage859, "stage859_minute_bars"),
                "line_scope_compatible": 0,
            }
        )
    return pd.DataFrame(rows)


def _source_arbitration() -> pd.DataFrame:
    stage151 = _read_csv(STAGE151_ROUTE_IN)
    stage160 = _row(STAGE160_SUMMARY_IN)
    stage033 = _row(STAGE033_SUMMARY_IN)
    stage107 = _row(STAGE107_SUMMARY_IN)
    stage114 = _row(STAGE114_SUMMARY_IN)
    stage859_source = _read_csv(EX_STAGE859_SOURCE_IN)
    stage859 = _row(EX_STAGE859_SUMMARY_IN)
    stage861 = _row(EX_STAGE861_SUMMARY_IN)

    tqsdk_installed, tqsdk_version = _source_status_from_stage859(stage859_source, "tqsdk")
    akshare_installed, akshare_version = _source_status_from_stage859(stage859_source, "akshare")
    rqdatac_installed, rqdatac_version = _source_status_from_stage859(stage859_source, "rqdatac")
    tushare_installed, tushare_version = _source_status_from_stage859(stage859_source, "tushare")
    tqsdk_credentials, tqsdk_credential_note = _source_status_from_stage859(stage859_source, "tqsdk_vnpy_settings_credentials")

    rows: list[dict[str, Any]] = [
        {
            "source_id": "stage152_authoritative_incoming_package",
            "source_name": "Stage152 raw/normalized/proof 授权分钟包",
            "source_family": "authoritative_minute_contract",
            "installed_or_present": int(_int(stage160, "incoming_root_exists") == 1),
            "local_data_rows_or_files": _int(stage160, "present_expected_file_count"),
            "required_rows_or_files": _int(stage160, "expected_file_count"),
            "current_data_ready": int(_int(stage160, "stage153_trigger_allowed") == 1),
            "point_in_time_possible": 1,
            "minute_or_execution_level": 1,
            "entry_visible_possible": 1,
            "independent_of_final_pnl": 1,
            "authorized_proof_ready": int(_int(stage160, "stage153_trigger_allowed") == 1),
            "line_scope_compatible": 1,
            "coverage_ready_for_stage152": int(_int(stage160, "stage153_trigger_allowed") == 1),
            "lineage_ready": 0,
            "proxy_or_selection_bias_risk": 0,
            "stage153_substitute_allowed": int(_int(stage160, "stage153_trigger_allowed") == 1),
            "strategy_rule_allowed": 0,
            "research_value_now": 5,
            "hard_blocker": "missing_699_expected_files",
            "next_action": "deliver raw/normalized/proof files then rerun Stage160 and Stage153",
            "evidence": f"Stage160 present={_int(stage160, 'present_expected_file_count')}/{_int(stage160, 'expected_file_count')}",
        },
        {
            "source_id": "tqsdk_direct_or_backtest_pull",
            "source_name": "TqSdk get_kline_serial / TqBacktest 拉取",
            "source_family": "vendor_sdk_pull",
            "installed_or_present": int(tqsdk_installed or _module_installed("tqsdk")),
            "local_data_rows_or_files": _int(stage859, "stage859_minute_bars"),
            "required_rows_or_files": _int(stage160, "expected_file_count"),
            "current_data_ready": int(_int(stage859, "remaining_uncovered_requests_after_stage859", 1) == 0 and _int(stage859, "stage859_minute_bars") > 0),
            "point_in_time_possible": 1,
            "minute_or_execution_level": 1,
            "entry_visible_possible": 1,
            "independent_of_final_pnl": 1,
            "authorized_proof_ready": 0,
            "line_scope_compatible": 0,
            "coverage_ready_for_stage152": 0,
            "lineage_ready": 0,
            "proxy_or_selection_bias_risk": 1,
            "stage153_substitute_allowed": 0,
            "strategy_rule_allowed": 0,
            "research_value_now": 3,
            "hard_blocker": "other_line_proxy_pull_without_stage152_proof_raw_normalized_package",
            "next_action": "only usable if converted into Stage152 raw/proof/normalized delivery with license/provenance",
            "evidence": f"tqsdk={tqsdk_version or 'installed'}, credentials={tqsdk_credential_note}, Stage859 bars={_int(stage859, 'stage859_minute_bars')}",
        },
        {
            "source_id": "stage861_other_line_full_minute_bars",
            "source_name": "Stage861 其他线 full minute atlas 明细",
            "source_family": "other_line_local_minute_csv",
            "installed_or_present": int(EX_STAGE861_BARS_IN.exists()),
            "local_data_rows_or_files": _int(stage861, "full_minute_bars"),
            "required_rows_or_files": _int(stage160, "expected_file_count"),
            "current_data_ready": int(_int(stage861, "full_minute_bars") > 0),
            "point_in_time_possible": 1,
            "minute_or_execution_level": 1,
            "entry_visible_possible": 1,
            "independent_of_final_pnl": 0,
            "authorized_proof_ready": 0,
            "line_scope_compatible": 0,
            "coverage_ready_for_stage152": 0,
            "lineage_ready": 0,
            "proxy_or_selection_bias_risk": 1,
            "stage153_substitute_allowed": 0,
            "strategy_rule_allowed": 0,
            "research_value_now": 2,
            "hard_blocker": "other_line_artifact_no_stage152_proof_no_current_line_lineage",
            "next_action": "reference only; do not copy into current line as strategy evidence",
            "evidence": f"Stage861 bars={_int(stage861, 'full_minute_bars')}, entry coverage={_num(stage861, 'entry_day_coverage_rate'):.4f}",
        },
        {
            "source_id": "stage107_contract_month_oi_panel",
            "source_name": "Stage107 contract-month OI patched panel",
            "source_family": "daily_or_contract_oi_panel",
            "installed_or_present": int(bool(stage107)),
            "local_data_rows_or_files": _int(stage107, "adjusted_panel_ready_count"),
            "required_rows_or_files": _int(stage107, "timestamp_ready_order_count"),
            "current_data_ready": int(_int(stage107, "adjusted_panel_ready_count") > 0),
            "point_in_time_possible": 1,
            "minute_or_execution_level": 0,
            "entry_visible_possible": 1,
            "independent_of_final_pnl": 1,
            "authorized_proof_ready": 0,
            "line_scope_compatible": 1,
            "coverage_ready_for_stage152": 0,
            "lineage_ready": 0,
            "proxy_or_selection_bias_risk": 1,
            "stage153_substitute_allowed": 0,
            "strategy_rule_allowed": 0,
            "research_value_now": 1,
            "hard_blocker": "not_minute_ohlcv_and_prior_rule_route_blocked",
            "next_action": "keep as context only; no direct rule or Stage153 substitute",
            "evidence": f"adjusted_ready={_int(stage107, 'adjusted_panel_ready_count')}/{_int(stage107, 'timestamp_ready_order_count')}",
        },
        {
            "source_id": "stage114_w0_orderflow_procurement",
            "source_name": "W0 MBP/MBO orderflow procurement bundle",
            "source_family": "authorized_microstructure_procurement",
            "installed_or_present": int(bool(stage114)),
            "local_data_rows_or_files": 0,
            "required_rows_or_files": _int(stage114, "request_interval_count"),
            "current_data_ready": 0,
            "point_in_time_possible": 1,
            "minute_or_execution_level": 1,
            "entry_visible_possible": 1,
            "independent_of_final_pnl": 1,
            "authorized_proof_ready": 0,
            "line_scope_compatible": 1,
            "coverage_ready_for_stage152": 0,
            "lineage_ready": 0,
            "proxy_or_selection_bias_risk": 0,
            "stage153_substitute_allowed": 0,
            "strategy_rule_allowed": 0,
            "research_value_now": 2,
            "hard_blocker": "procurement_bundle_built_but_no_real_w0_delivery",
            "next_action": "wait W0 drop; run Stage125 -> Stage133 -> Stage112/113",
            "evidence": f"Stage114 intervals={_int(stage114, 'request_interval_count')}, hours={_num(stage114, 'total_request_hours'):.2f}",
        },
        {
            "source_id": "akshare_public_probe",
            "source_name": "AKShare public futures data",
            "source_family": "public_api_probe",
            "installed_or_present": int(akshare_installed or _module_installed("akshare")),
            "local_data_rows_or_files": 0,
            "required_rows_or_files": _int(stage160, "expected_file_count"),
            "current_data_ready": 0,
            "point_in_time_possible": 0,
            "minute_or_execution_level": 0,
            "entry_visible_possible": 0,
            "independent_of_final_pnl": 1,
            "authorized_proof_ready": 0,
            "line_scope_compatible": 1,
            "coverage_ready_for_stage152": 0,
            "lineage_ready": 0,
            "proxy_or_selection_bias_risk": 1,
            "stage153_substitute_allowed": 0,
            "strategy_rule_allowed": 0,
            "research_value_now": 0,
            "hard_blocker": "no_manifested_1m_ohlcv_oi_stage152_package",
            "next_action": "do not use for this minute-entry objective unless a proofed licensed package is built",
            "evidence": f"akshare={akshare_version or 'installed'}",
        },
        {
            "source_id": "rqdatac_or_tushare_public_probe",
            "source_name": "RQData/Tushare installed credentials probe",
            "source_family": "public_or_commercial_api_probe",
            "installed_or_present": int(rqdatac_installed or tushare_installed or _module_installed("rqdatac") or _module_installed("tushare")),
            "local_data_rows_or_files": 0,
            "required_rows_or_files": _int(stage160, "expected_file_count"),
            "current_data_ready": 0,
            "point_in_time_possible": 1,
            "minute_or_execution_level": 0,
            "entry_visible_possible": 1,
            "independent_of_final_pnl": 1,
            "authorized_proof_ready": 0,
            "line_scope_compatible": 1,
            "coverage_ready_for_stage152": 0,
            "lineage_ready": 0,
            "proxy_or_selection_bias_risk": 1,
            "stage153_substitute_allowed": 0,
            "strategy_rule_allowed": 0,
            "research_value_now": 0,
            "hard_blocker": "no_current_line_stage152_delivery_and_no_1m_oi_manifest",
            "next_action": "only reconsider with explicit licensed 1m OHLCV/OI export and proof JSON",
            "evidence": f"rqdatac={rqdatac_version or 'n/a'}, tushare={tushare_version or 'n/a'}",
        },
    ]

    if not stage151.empty:
        ready_routes = int(stage151["current_local_data_ready"].sum()) if "current_local_data_ready" in stage151 else 0
        rule_feasible_routes = int(stage151["rule_feasible_now"].sum()) if "rule_feasible_now" in stage151 else 0
        rows.append(
            {
                "source_id": "stage151_route_frontier",
                "source_name": "Stage151 external source router frontier",
                "source_family": "route_meta_evidence",
                "installed_or_present": 1,
                "local_data_rows_or_files": ready_routes,
                "required_rows_or_files": len(stage151),
                "current_data_ready": int(ready_routes > 0),
                "point_in_time_possible": 1,
                "minute_or_execution_level": 1,
                "entry_visible_possible": 1,
                "independent_of_final_pnl": 1,
                "authorized_proof_ready": 0,
                "line_scope_compatible": 1,
                "coverage_ready_for_stage152": 0,
                "lineage_ready": 0,
                "proxy_or_selection_bias_risk": 1,
                "stage153_substitute_allowed": 0,
                "strategy_rule_allowed": 0,
                "research_value_now": 1,
                "hard_blocker": "router_selected_stage152_but_delivery_missing",
                "next_action": "do not revisit closed routes; wait authorized delivery or proofed conversion",
                "evidence": f"ready_routes={ready_routes}, rule_feasible_routes={rule_feasible_routes}/{len(stage151)}",
            }
        )
    frame = pd.DataFrame(rows)
    eligibility_cols = [
        "current_data_ready",
        "point_in_time_possible",
        "minute_or_execution_level",
        "entry_visible_possible",
        "independent_of_final_pnl",
        "authorized_proof_ready",
        "line_scope_compatible",
        "coverage_ready_for_stage152",
        "lineage_ready",
    ]
    frame["eligibility_score"] = frame[eligibility_cols].sum(axis=1)
    frame["eligible_hard_block_count"] = (
        9
        - frame[eligibility_cols].sum(axis=1)
        + frame["proxy_or_selection_bias_risk"].astype(int)
        + (1 - frame["stage153_substitute_allowed"].astype(int))
    )
    return frame.sort_values(["stage153_substitute_allowed", "research_value_now", "eligibility_score"], ascending=[False, False, False]).reset_index(drop=True)


def _migration_requirements() -> pd.DataFrame:
    requirements = [
        ("01_source_license", "explicit license/vendor/export permission for every file", "hard", "missing_for_all_alternates"),
        ("02_raw_file_export", "raw files written to every Stage152 expected_raw_file path", "hard", "missing"),
        ("03_normalized_parquet", "canonical parquet with bar_start_ts/bar_end_ts/OHLCV/volume/open_interest", "hard", "missing"),
        ("04_proof_json", "proof JSON with query, license, raw sha256, normalization sha256, session policy", "hard", "missing"),
        ("05_no_fixture_marker", "no template/synthetic/fixture/smoke/local-proxy markers", "hard", "required"),
        ("06_window_coverage", "all 657 Stage152 windows covered including right-tail/bottom-loss/maxDD", "hard", "missing"),
        ("07_line_scope", "data delivered under current line's Stage152 incoming contract, not copied from other-line artifacts", "hard", "missing_for_stage861"),
        ("08_stage153_pass", "Stage153 request/proof/schema/window coverage all pass", "hard", "not_run_ready"),
        ("09_stage156_157_158_pass", "feature readiness, builder, and lineage pass after Stage153", "hard", "not_run_ready"),
        ("10_strategy_unlock", "only readonly feature atlas before any candidate; true engine requires Stage141+ package gates", "hard", "locked"),
    ]
    return pd.DataFrame(
        [
            {
                "requirement_order": idx + 1,
                "requirement_id": rid,
                "requirement": text,
                "severity": severity,
                "current_status": status,
                "pass_now": 0,
            }
            for idx, (rid, text, severity, status) in enumerate(requirements)
        ]
    )


def _gate_status(summary: dict[str, Any], sources: pd.DataFrame, requirements: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "gate_id": "source_arbitration_written",
                "observed": int(len(sources)),
                "required": 1,
                "pass_now": int(len(sources) > 0),
                "severity": "contract_hard",
            },
            {
                "gate_id": "stage153_substitute_allowed_count",
                "observed": int(sources["stage153_substitute_allowed"].sum()),
                "required": 0,
                "pass_now": int(sources["stage153_substitute_allowed"].sum() == 0),
                "severity": "safety_hard",
            },
            {
                "gate_id": "strategy_rule_allowed_count",
                "observed": int(sources["strategy_rule_allowed"].sum()),
                "required": 0,
                "pass_now": int(sources["strategy_rule_allowed"].sum() == 0),
                "severity": "strategy_hard",
            },
            {
                "gate_id": "migration_requirement_pass_count",
                "observed": int(requirements["pass_now"].sum()),
                "required": int(len(requirements)),
                "pass_now": 0,
                "severity": "data_hard",
            },
            {
                "gate_id": "no_true_engine",
                "observed": int(summary["true_engine_run_count"]),
                "required": 0,
                "pass_now": int(summary["true_engine_run_count"] == 0),
                "severity": "strategy_hard",
            },
            {
                "gate_id": "no_order_or_ctp",
                "observed": int(summary["order_api_called"] + summary["ctp_connected"]),
                "required": 0,
                "pass_now": int(summary["order_api_called"] == 0 and summary["ctp_connected"] == 0),
                "severity": "safety_hard",
            },
            {
                "gate_id": "objective_completion_proven",
                "observed": int(summary["objective_completion_proven"]),
                "required": 1,
                "pass_now": 0,
                "severity": "objective_hard",
            },
        ]
    )


def _write_report(summary: dict[str, Any], sources: pd.DataFrame, artifacts: pd.DataFrame, requirements: pd.DataFrame, gates: pd.DataFrame) -> None:
    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(
        [
            "# Stage161 Authoritative Minute Source Arbitration",
            "",
            f"- model_tag: `{MODEL_TAG}`",
            f"- decision: `{summary['decision']}`",
            "- Scope: readonly arbitration of whether any local/TqSdk/other-line minute source can replace Stage152 authorized package.",
            "- Hard lock: no strategy rule, no true engine, no A/B, no CTP, no order API, no official config change.",
            "",
            "## Summary",
            "",
            _md_table(pd.DataFrame([summary])),
            "",
            "## Source Arbitration",
            "",
            _md_table(sources, max_rows=20),
            "",
            "## Local Artifact Audit",
            "",
            _md_table(artifacts, max_rows=30),
            "",
            "## Migration Requirements",
            "",
            _md_table(requirements),
            "",
            "## Gate Status",
            "",
            _md_table(gates),
            "",
            "## Conclusion",
            "",
            "- TqSdk and multiple cached minute artifacts exist, but none currently satisfy Stage152 raw/normalized/proof, current-line lineage, and Stage153 intake gates.",
            "- Stage861 is useful as historical visual context from another line, but not as authorized evidence for this line's candidate promotion.",
            "- Current next action remains: deliver a proofed Stage152 package, or build a proofed conversion bundle from any vendor source before Stage153.",
            "",
        ]
    )
    REPORT_OUT.write_text(text, encoding="utf-8")


def _plot_path(curve: pd.DataFrame, summary: dict[str, Any]) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(15, 11), sharex=True)
    axes[0].plot(curve["date"], curve["account_equity"], color="#1f77b4", linewidth=1.8)
    axes[0].set_title("Official Path With Stage161 Source Arbitration")
    axes[0].set_ylabel("Equity")
    axes[0].grid(alpha=0.25)
    axes[0].text(
        0.01,
        0.95,
        f"stage153_substitute_allowed={summary['stage153_substitute_allowed_count']} | strategy_rule_allowed={summary['strategy_rule_allowed_count']} | alternates={summary['alternate_source_count']}",
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


def _plot_source_matrix(sources: pd.DataFrame) -> None:
    cols = [
        "current_data_ready",
        "minute_or_execution_level",
        "entry_visible_possible",
        "independent_of_final_pnl",
        "authorized_proof_ready",
        "line_scope_compatible",
        "coverage_ready_for_stage152",
        "lineage_ready",
        "stage153_substitute_allowed",
    ]
    data = sources[cols].to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(15, 8))
    ax.imshow(data, aspect="auto", cmap=plt.get_cmap("RdYlGn"), vmin=0, vmax=1)
    ax.set_xticks(np.arange(len(cols)))
    ax.set_xticklabels(cols, rotation=45, ha="right")
    ax.set_yticks(np.arange(len(sources)))
    ax.set_yticklabels(sources["source_id"].tolist())
    ax.set_title("Stage161 Source Eligibility Matrix")
    for row_idx in range(data.shape[0]):
        for col_idx in range(data.shape[1]):
            ax.text(col_idx, row_idx, int(data[row_idx, col_idx]), ha="center", va="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(SOURCE_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_score(sources: pd.DataFrame) -> None:
    data = sources.sort_values("research_value_now", ascending=True)
    fig, ax = plt.subplots(figsize=(13, 7))
    y = np.arange(len(data))
    ax.barh(y, data["eligibility_score"], color="#17becf", label="eligibility_score")
    ax.scatter(data["research_value_now"], y, color="#d62728", label="research_value_now")
    ax.set_yticks(y)
    ax.set_yticklabels(data["source_id"].tolist())
    ax.set_xlabel("Score")
    ax.set_title("Source Score: Eligibility vs Research Value")
    ax.legend()
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(SCORE_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_artifacts(artifacts: pd.DataFrame) -> None:
    data = artifacts.copy()
    data["size_mb_plot"] = pd.to_numeric(data["size_mb"], errors="coerce").fillna(0.0)
    data = data.sort_values("size_mb_plot", ascending=True).tail(12)
    fig, ax = plt.subplots(figsize=(13, 7))
    y = np.arange(len(data))
    ax.barh(y, data["size_mb_plot"], color=np.where(data["line_scope_compatible"].eq(1), "#2ca02c", "#ff7f0e"))
    ax.set_yticks(y)
    ax.set_yticklabels(data["artifact_id"].tolist())
    ax.set_xlabel("Size MB")
    ax.set_title("Local Artifact Size And Line Scope")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(ARTIFACT_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_gate(gates: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(13, 7))
    matrix = gates[["pass_now"]].to_numpy(dtype=float)
    ax.imshow(matrix, aspect="auto", cmap=plt.get_cmap("RdYlGn"), vmin=0, vmax=1)
    ax.set_yticks(np.arange(len(gates)))
    ax.set_yticklabels(gates["gate_id"].tolist())
    ax.set_xticks([0])
    ax.set_xticklabels(["pass_now"])
    ax.set_title("Stage161 Gate Status Matrix")
    for row_idx, row in gates.iterrows():
        ax.text(0, row_idx, f"{int(row['observed'])}/{int(row['required'])}", ha="center", va="center", color="black", fontsize=9)
    fig.tight_layout()
    fig.savefig(GATE_CHART_OUT, dpi=170)
    plt.close(fig)


def main() -> None:
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    curve = _load_curve()
    metrics = _baseline_metrics(curve)
    sources = _source_arbitration()
    artifacts = _artifact_audit()
    requirements = _migration_requirements()

    stage153_substitute_allowed_count = int(sources["stage153_substitute_allowed"].sum())
    strategy_rule_allowed_count = int(sources["strategy_rule_allowed"].sum())
    current_data_ready_count = int(sources["current_data_ready"].sum())
    alternate_source_count = int(len(sources) - 1)
    eligible_line_scope_source_count = int(
        sources[
            sources["line_scope_compatible"].eq(1)
            & sources["minute_or_execution_level"].eq(1)
            & sources["authorized_proof_ready"].eq(1)
        ].shape[0]
    )
    decision = "stage161_source_arbitration_no_alternate_substitute_wait_authorized_package_no_rule"
    summary: dict[str, Any] = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "created_at": created_at,
        "line_id": LINE_ID,
        "decision": decision,
        "next_best_action": "wait_stage152_authorized_package_or_build_proofed_conversion_bundle_before_stage153",
        "source_count": int(len(sources)),
        "alternate_source_count": alternate_source_count,
        "current_data_ready_source_count": current_data_ready_count,
        "stage153_substitute_allowed_count": stage153_substitute_allowed_count,
        "strategy_rule_allowed_count": strategy_rule_allowed_count,
        "eligible_line_scope_source_count": eligible_line_scope_source_count,
        "migration_requirement_count": int(len(requirements)),
        "migration_requirement_pass_count": int(requirements["pass_now"].sum()),
        "local_artifact_count": int(len(artifacts)),
        "other_line_artifact_count": int(artifacts["line_scope_compatible"].eq(0).sum()),
        "tqsdk_module_installed": _module_installed("tqsdk"),
        "akshare_module_installed": _module_installed("akshare"),
        "rqdatac_module_installed": _module_installed("rqdatac"),
        "tushare_module_installed": _module_installed("tushare"),
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
    gates = _gate_status(summary, sources, requirements)

    _write_csv(pd.DataFrame([summary]), SUMMARY_OUT)
    _write_csv(sources, SOURCE_ARBITRATION_OUT)
    _write_csv(artifacts, ARTIFACT_AUDIT_OUT)
    _write_csv(requirements, MIGRATION_REQUIREMENTS_OUT)
    _write_csv(gates, GATE_OUT)
    _write_json(
        DECISION_OUT,
        {
            "decision": decision,
            "summary": summary,
            "outputs": {
                "summary": SUMMARY_OUT,
                "source_arbitration": SOURCE_ARBITRATION_OUT,
                "artifact_audit": ARTIFACT_AUDIT_OUT,
                "migration_requirements": MIGRATION_REQUIREMENTS_OUT,
                "gate_status": GATE_OUT,
                "report": REPORT_OUT,
                "charts": [PATH_CHART_OUT, SOURCE_CHART_OUT, SCORE_CHART_OUT, ARTIFACT_CHART_OUT, GATE_CHART_OUT],
            },
        },
    )
    _write_report(summary, sources, artifacts, requirements, gates)
    _plot_path(curve, summary)
    _plot_source_matrix(sources)
    _plot_score(sources)
    _plot_artifacts(artifacts)
    _plot_gate(gates)
    print(json.dumps(_json_safe(summary), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
