from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage076"
MODEL_TAG = "stage076_data_exit_route_scorecard_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage076_c9_minrisk_data_exit_route_scorecard_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage076_data_exit_route_scorecard_audit"

STAGE033_DIR = LINE_DIR / "outputs" / "stage033_tick_source_feasibility_audit"
STAGE045_DIR = LINE_DIR / "outputs" / "stage045_event_time_field_sync_audit"
STAGE074_DIR = LINE_DIR / "outputs" / "stage074_initial_entry_authoritative_source_decision_audit"
STAGE075_DIR = LINE_DIR / "outputs" / "stage075_raw_authority_feature_gate_audit"

STAGE033_SUMMARY_IN = (
    STAGE033_DIR
    / "qmt_roll_stage033_c9_minrisk_tick_source_feasibility_audit_summary_"
    "stage033_tick_source_feasibility_audit_v1.csv"
)
STAGE033_SOURCE_SUMMARY_IN = (
    STAGE033_DIR
    / "qmt_roll_stage033_c9_minrisk_tick_source_feasibility_audit_source_summary_"
    "stage033_tick_source_feasibility_audit_v1.csv"
)
STAGE045_CURVE_IN = (
    STAGE045_DIR
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)
STAGE045_SUMMARY_IN = (
    STAGE045_DIR
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_summary_"
    "stage045_event_time_field_sync_audit_v1.csv"
)
STAGE074_AUDIT_IN = (
    STAGE074_DIR
    / "qmt_roll_stage074_c9_minrisk_initial_entry_authoritative_source_decision_audit_source_decision_audit_"
    "stage074_initial_entry_authoritative_source_decision_audit_v1.csv"
)
STAGE075_SUMMARY_IN = (
    STAGE075_DIR
    / "qmt_roll_stage075_c9_minrisk_raw_authority_feature_gate_audit_summary_"
    "stage075_raw_authority_feature_gate_audit_v1.csv"
)
STAGE075_PERMISSION_IN = (
    STAGE075_DIR
    / "qmt_roll_stage075_c9_minrisk_raw_authority_feature_gate_audit_feature_permission_matrix_"
    "stage075_raw_authority_feature_gate_audit_v1.csv"
)
RAW_AUTHORITY_ROOTS = [
    EXAMPLE_DIR / "downloaded_futures" / "tqsdk_stage452_true_path_fallback_1455",
    EXAMPLE_DIR / "downloaded_futures" / "tqsdk_stage448_minute_session_rebuild_batch",
]

ROUTE_SCORECARD_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_route_scorecard_{MODEL_TAG}.csv"
LOCAL_CATALOG_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_local_source_catalog_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
ROUTE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_route_scorecard_chart_{MODEL_TAG}.png"
READINESS_ATLAS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_route_readiness_atlas_{MODEL_TAG}.png"
OFFICIAL_PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_route_boundary_chart_{MODEL_TAG}.png"

OFFICIAL_LIVE_VERSION = "official_live_stage847_c9_15w_stage819_05r_stop_retry_once"
OFFICIAL_LIVE_ALIAS = "Stage847-C9-15w"
INITIAL_CAPITAL = 150_000.0


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return pd.Timestamp(value).strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    return value


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if np.isfinite(result) else default


def _safe_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    data = frame.copy()
    if max_rows is not None:
        data = data.head(max_rows)
    display = data.copy()
    for col in display.columns:
        if pd.api.types.is_float_dtype(display[col]):
            display[col] = display[col].map(lambda value: "" if pd.isna(value) else f"{value:.4f}")
    lines = [
        "| " + " | ".join(str(col) for col in display.columns) + " |",
        "| " + " | ".join(["---"] * len(display.columns)) + " |",
    ]
    for _, row in display.iterrows():
        lines.append("| " + " | ".join(str(row[col]) for col in display.columns) + " |")
    return "\n".join(lines)


def _count_files(root: Path, patterns: list[str]) -> int:
    if not root.exists():
        return 0
    files: set[Path] = set()
    for pattern in patterns:
        files.update(path for path in root.rglob(pattern) if path.is_file())
    return len(files)


def _line_tick_files() -> int:
    patterns = ["*tick*.csv", "*orderbook*.csv", "*order_book*.csv", "*depth*.csv", "*dur0*.csv"]
    files: set[Path] = set()
    for pattern in patterns:
        files.update(path for path in LINE_DIR.rglob(pattern) if path.is_file())
    return len(files)


def _raw_authority_tick_files() -> int:
    patterns = ["*tick*.csv", "*orderbook*.csv", "*order_book*.csv", "*depth*.csv", "*dur0*.csv"]
    return sum(_count_files(root, patterns) for root in RAW_AUTHORITY_ROOTS)


def _raw_authority_minute_files() -> int:
    return sum(_count_files(root, ["*_minute_backtest.csv", "*.csv"]) for root in RAW_AUTHORITY_ROOTS)


def _prepare_audit(stage074: pd.DataFrame) -> pd.DataFrame:
    audit = stage074.copy()
    audit["official_open_date"] = pd.to_datetime(audit["official_open_date"], errors="coerce")
    audit["realized_pnl"] = _safe_num(audit.get("realized_pnl", pd.Series(np.nan, index=audit.index))).fillna(0.0)
    audit["timestamp_ready"] = _safe_num(audit.get("timestamp_ready", pd.Series(0, index=audit.index))).fillna(0).astype(int)
    audit["stage449_anchor_ready"] = _safe_num(
        audit.get("stage449_anchor_ready", pd.Series(0, index=audit.index))
    ).fillna(0).astype(int)
    audit["stage449_anchor_exact_official"] = _safe_num(
        audit.get("stage449_anchor_exact_official", pd.Series(0, index=audit.index))
    ).fillna(0).astype(int)
    audit["route_boundary_class"] = np.select(
        [
            audit["timestamp_ready"].eq(0),
            audit["source_decision_class"].astype(str).str.contains("stage452_fallback", na=False),
        ],
        ["fallback_no_proxy_gap", "stage452_raw_fallback_gap"],
        default="stage449_raw_price_boundary",
    )
    return audit


def _build_local_catalog(stage033_sources: pd.DataFrame, facts: dict[str, int]) -> pd.DataFrame:
    rows = [
        {
            "source_name": "raw_authority_roots_minute_files",
            "source_type": "local_minute_price_proxy",
            "file_count": facts["raw_authority_minute_files"],
            "event_relevance": "initial_open_raw_price_authority",
            "same_source_to_official_open": 1,
            "historical_backtest_ready": 1,
            "tick_or_orderbook_ready": 0,
            "note": "Stage074 exact price authority, but zero-volume/OHLC-flat proxy",
        },
        {
            "source_name": "raw_authority_roots_tick_orderbook_files",
            "source_type": "local_tick_orderbook",
            "file_count": facts["raw_authority_tick_files"],
            "event_relevance": "same_source_microstructure_required",
            "same_source_to_official_open": 0,
            "historical_backtest_ready": 0,
            "tick_or_orderbook_ready": 0,
            "note": "not present locally",
        },
        {
            "source_name": "line_local_tick_like_files",
            "source_type": "mixed_line_outputs",
            "file_count": facts["line_tick_like_files"],
            "event_relevance": "heterologous_or_prior_audit_assets",
            "same_source_to_official_open": 0,
            "historical_backtest_ready": 1,
            "tick_or_orderbook_ready": 1,
            "note": "includes TqBacktest and local smoke/live files; not raw authority source",
        },
    ]
    if not stage033_sources.empty:
        for _, row in stage033_sources.iterrows():
            rows.append(
                {
                    "source_name": row.get("source_name"),
                    "source_type": row.get("source_type"),
                    "file_count": int(_safe_float(row.get("file_count"), 0)),
                    "event_relevance": "stage033_tick_feasibility",
                    "same_source_to_official_open": 0,
                    "historical_backtest_ready": int(_safe_float(row.get("ready_for_stage030_replay"), 0)),
                    "tick_or_orderbook_ready": int(_safe_float(row.get("event_moment_near_count"), 0) > 0),
                    "note": row.get("note"),
                }
            )
    return pd.DataFrame(rows)


def _build_route_scorecard(facts: dict[str, int]) -> pd.DataFrame:
    rows = [
        {
            "route_id": "R1_raw_authority_price_boundary",
            "route_name": "继续 raw authority bar-level 账本边界审计",
            "local_evidence_count": facts["same_source_price_authority_count"],
            "covers_initial_opens": facts["same_source_price_authority_count"],
            "historical_2018_2026": 1,
            "same_source_execution": 1,
            "nondegenerate_ohlcv": 0,
            "tick_orderbook": 0,
            "independent_preentry_source": 0,
            "not_final_pnl_derived": 1,
            "rule_candidate_allowed": 0,
            "decision": "audit_only_not_strategy_rule",
            "next_action_rank": 3,
            "next_action": "只允许账本/执行边界审计，不写真正交易候选",
        },
        {
            "route_id": "R2_same_source_tick_orderbook_backfill",
            "route_name": "补同源 tick/orderbook 或 vendor 授权源",
            "local_evidence_count": facts["raw_authority_tick_files"],
            "covers_initial_opens": 0,
            "historical_2018_2026": 0,
            "same_source_execution": 0,
            "nondegenerate_ohlcv": 0,
            "tick_orderbook": 0,
            "independent_preentry_source": 0,
            "not_final_pnl_derived": 1,
            "rule_candidate_allowed": 0,
            "decision": "best_data_engineering_exit_required_before_microstructure_rules",
            "next_action_rank": 1,
            "next_action": "获取能解释 Stage449/raw zero-volume open 的同源 tick/orderbook 后复验 exact",
        },
        {
            "route_id": "R3_existing_tq_tick",
            "route_name": "继续使用既有 Tq tick",
            "local_evidence_count": facts["heterologous_tq_tick_ready_count"],
            "covers_initial_opens": facts["heterologous_tq_tick_ready_count"],
            "historical_2018_2026": 0,
            "same_source_execution": 0,
            "nondegenerate_ohlcv": 1,
            "tick_orderbook": 1,
            "independent_preentry_source": 0,
            "not_final_pnl_derived": 1,
            "rule_candidate_allowed": 0,
            "decision": "blocked_heterologous_tca_only",
            "next_action_rank": 6,
            "next_action": "只保留 TCA 观察，不进入规则",
        },
        {
            "route_id": "R4_fallback_no_proxy_refill",
            "route_name": "补 105 笔 no-proxy raw authority",
            "local_evidence_count": 0,
            "covers_initial_opens": facts["fallback_no_proxy_count"],
            "historical_2018_2026": 0,
            "same_source_execution": 0,
            "nondegenerate_ohlcv": 0,
            "tick_orderbook": 0,
            "independent_preentry_source": 0,
            "not_final_pnl_derived": 1,
            "rule_candidate_allowed": 0,
            "decision": "coverage_gap_refill_not_alpha",
            "next_action_rank": 2,
            "next_action": "先补 raw proxy 覆盖，仍不得按 no-proxy 写规则",
        },
        {
            "route_id": "R5_ctp_live_forward_tick_recorder",
            "route_name": "CTP/vn.py live tick 前向记录",
            "local_evidence_count": int(facts.get("stage033_local_tick_like_file_count", 0)),
            "covers_initial_opens": 0,
            "historical_2018_2026": 0,
            "same_source_execution": 0,
            "nondegenerate_ohlcv": 1,
            "tick_orderbook": 1,
            "independent_preentry_source": 0,
            "not_final_pnl_derived": 1,
            "rule_candidate_allowed": 0,
            "decision": "forward_watch_only_not_historical_backtest",
            "next_action_rank": 5,
            "next_action": "可用于未来样本记录，不能回填本轮历史目标",
        },
        {
            "route_id": "R6_authorized_external_preentry_source",
            "route_name": "授权外生入场前数据源",
            "local_evidence_count": 0,
            "covers_initial_opens": 0,
            "historical_2018_2026": 0,
            "same_source_execution": 0,
            "nondegenerate_ohlcv": 0,
            "tick_orderbook": 0,
            "independent_preentry_source": 1,
            "not_final_pnl_derived": 1,
            "rule_candidate_allowed": 0,
            "decision": "second_best_data_engineering_exit_requires_complete_point_in_time_coverage",
            "next_action_rank": 4,
            "next_action": "只在覆盖完整、点时化、非最终盈亏标签后重启只读审计",
        },
    ]
    return pd.DataFrame(rows)


def _plot_route_scorecard(route: pd.DataFrame, path: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(17, 7))
    order = route.sort_values("next_action_rank", ascending=False)
    colors = np.where(order["rule_candidate_allowed"].eq(1), "#009e73", "#d55e00")
    axes[0].barh(order["route_id"], order["local_evidence_count"], color=colors)
    axes[0].set_title("Local evidence count by data-exit route")
    axes[0].set_xlabel("Local evidence count")
    axes[0].grid(axis="x", alpha=0.25)

    flags = [
        "historical_2018_2026",
        "same_source_execution",
        "nondegenerate_ohlcv",
        "tick_orderbook",
        "independent_preentry_source",
        "not_final_pnl_derived",
        "rule_candidate_allowed",
    ]
    matrix = route.sort_values("next_action_rank")[flags].astype(float).to_numpy()
    axes[1].imshow(matrix, aspect="auto", cmap="Greens", vmin=0, vmax=1)
    axes[1].set_yticks(np.arange(len(route)))
    axes[1].set_yticklabels(route.sort_values("next_action_rank")["route_id"])
    axes[1].set_xticks(np.arange(len(flags)))
    axes[1].set_xticklabels(flags, rotation=35, ha="right")
    for y in range(matrix.shape[0]):
        for x in range(matrix.shape[1]):
            axes[1].text(x, y, int(matrix[y, x]), ha="center", va="center", fontsize=9)
    axes[1].set_title("Route readiness flags")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _plot_readiness_atlas(route: pd.DataFrame, path: Path) -> None:
    data = route.sort_values("next_action_rank")
    flags = [
        "historical_2018_2026",
        "same_source_execution",
        "nondegenerate_ohlcv",
        "tick_orderbook",
        "independent_preentry_source",
        "not_final_pnl_derived",
        "rule_candidate_allowed",
    ]
    matrix = data[flags].astype(float).to_numpy()
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.imshow(matrix, aspect="auto", cmap="Greens", vmin=0, vmax=1)
    ax.set_xticks(np.arange(len(flags)))
    ax.set_xticklabels(flags, rotation=35, ha="right")
    ax.set_yticks(np.arange(len(data)))
    ax.set_yticklabels(data["route_id"], fontsize=9)
    for y in range(matrix.shape[0]):
        for x in range(matrix.shape[1]):
            ax.text(x, y, int(matrix[y, x]), ha="center", va="center", fontsize=9)
    ax.set_title("Stage076 route readiness atlas: 1 means requirement is currently satisfied")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _plot_official_path(audit: pd.DataFrame, curve: pd.DataFrame, path: Path) -> None:
    curve_plot = curve.copy()
    curve_plot["date"] = pd.to_datetime(curve_plot["date"], errors="coerce")
    equity_col = "official_equity" if "official_equity" in curve_plot.columns else "account_equity"
    curve_plot["equity"] = _safe_num(curve_plot[equity_col])
    markers = audit.sort_values("official_open_date")
    merged = pd.merge_asof(
        markers[["official_open_date", "route_boundary_class", "realized_pnl"]].sort_values("official_open_date"),
        curve_plot[["date", "equity"]].dropna().sort_values("date"),
        left_on="official_open_date",
        right_on="date",
        direction="backward",
    )
    colors = {
        "stage449_raw_price_boundary": "#009e73",
        "stage452_raw_fallback_gap": "#0072b2",
        "fallback_no_proxy_gap": "#9e9e9e",
    }
    fig, axes = plt.subplots(2, 1, figsize=(16, 9), sharex=False)
    axes[0].plot(curve_plot["date"], curve_plot["equity"] / 1_000_000, color="#1f77b4", lw=1.8)
    for klass, group in merged.groupby("route_boundary_class"):
        axes[0].scatter(
            group["official_open_date"],
            group["equity"] / 1_000_000,
            color=colors.get(klass, "#333333"),
            s=25,
            alpha=0.82,
            label=klass,
        )
    axes[0].set_title("Stage076 official path by route-boundary class")
    axes[0].set_ylabel("Equity (million CNY)")
    axes[0].legend(loc="upper left", fontsize=9)
    axes[0].grid(alpha=0.25)

    for klass, group in markers.groupby("route_boundary_class"):
        ordered = group.sort_values("official_open_date")
        axes[1].plot(
            ordered["official_open_date"],
            ordered["realized_pnl"].cumsum() / 10_000,
            marker="o",
            ms=3,
            lw=1.7,
            color=colors.get(klass, "#333333"),
            label=klass,
        )
    axes[1].axhline(0, color="#333333", lw=0.8)
    axes[1].set_title("Cumulative realized PnL by route-boundary class (source route, not alpha)")
    axes[1].set_ylabel("Cumulative PnL (10k CNY)")
    axes[1].legend(loc="upper left", fontsize=9)
    axes[1].grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _build_report(route: pd.DataFrame, catalog: pd.DataFrame, summary: dict[str, Any]) -> str:
    return f"""# Stage076 data-exit route scorecard 审计

## 结论

- 决策：`{summary["decision"]}`。
- 当前正式版：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`。
- route_count：`{summary["route_count"]}`。
- rule_candidate_allowed_route_count：`{summary["rule_candidate_allowed_route_count"]}`。
- raw authority same-source price events：`{summary["same_source_price_authority_count"]}`。
- raw authority same-source tick/orderbook files：`{summary["raw_authority_tick_file_count"]}`。
- fallback no-proxy gap：`{summary["fallback_no_proxy_count"]}`。
- 本阶段不新增交易规则、不跑 true engine、不触发 A/B。

## route scorecard

{_md_table(route)}

## local source catalog

{_md_table(catalog, max_rows=20)}

## 官方基准

- 期末权益：`{summary["end_equity"]}`
- 总收益：`{summary["total_return_pct"]}`
- 最大回撤：`{summary["max_drawdown_pct"]}`
- Sharpe：`{summary["sharpe"]}`
- 总滑点：`{summary["total_slippage"]}`
- 总交易次数：`{summary["total_trade_count"]}`
- 胜率：`{summary["closed_lot_win_rate_pct"]}`
- broker10 峰值：`{summary["max_broker10_margin_to_equity_pct"]}`

## 视觉文件

- route scorecard chart：`{ROUTE_CHART_OUT}`
- route readiness atlas：`{READINESS_ATLAS_OUT}`
- official path route boundary chart：`{OFFICIAL_PATH_CHART_OUT}`

## 判断

- 当前没有任何 route 同时满足历史覆盖、同源执行、可交易微观结构、非最终盈亏标签和可写规则条件。
- 最优先的数据工程出口是 R2：补同源 tick/orderbook 或能解释 Stage449/raw zero-volume open 的授权/vendor 源；但在本地证据为 0 的当前状态下不能写规则。
- R4 no-proxy raw refill 是覆盖缺口治理，不是 alpha；R3 既有 Tq tick 是异源 TCA 观察，不能转规则；R5 CTP/vn.py live tick 只能形成未来样本，不能补历史回测。
- 若暂时不补同源盘口源，下一步应换真正外生、入场前可见、覆盖完整的数据源，并先做点时化覆盖审计。
"""


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stage033_summary = _read_csv(STAGE033_SUMMARY_IN)
    stage033_sources = _read_csv(STAGE033_SOURCE_SUMMARY_IN)
    curve = _read_csv(STAGE045_CURVE_IN)
    official_summary = _read_csv(STAGE045_SUMMARY_IN).iloc[0].to_dict()
    stage074 = _read_csv(STAGE074_AUDIT_IN)
    stage075 = _read_csv(STAGE075_SUMMARY_IN).iloc[0].to_dict()

    facts = {
        "same_source_price_authority_count": int(_safe_float(stage075.get("same_source_price_authority_count"), 0)),
        "heterologous_tq_tick_ready_count": int(_safe_float(stage075.get("heterologous_tq_tick_ready_count"), 0)),
        "fallback_no_proxy_count": int(_safe_float(stage075.get("fallback_no_proxy_count"), 0)),
        "raw_authority_tick_files": _raw_authority_tick_files(),
        "raw_authority_minute_files": _raw_authority_minute_files(),
        "line_tick_like_files": _line_tick_files(),
        "stage033_local_tick_like_file_count": int(
            _safe_float(stage033_summary.iloc[0].get("local_tick_like_file_count"), 0)
        ),
    }

    audit = _prepare_audit(stage074)
    catalog = _build_local_catalog(stage033_sources, facts)
    route = _build_route_scorecard(facts)

    summary = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "decision": "stage076_no_rule_ready_route_get_same_source_or_external_preentry_data",
        "next_step": "same_source_tick_orderbook_or_complete_external_preentry_source_coverage_audit",
        "strategy_rule_created": False,
        "true_engine_run": False,
        "ab_triggered": False,
        "route_count": int(len(route)),
        "rule_candidate_allowed_route_count": int(route["rule_candidate_allowed"].sum()),
        "same_source_price_authority_count": facts["same_source_price_authority_count"],
        "raw_authority_tick_file_count": facts["raw_authority_tick_files"],
        "line_tick_like_file_count": facts["line_tick_like_files"],
        "fallback_no_proxy_count": facts["fallback_no_proxy_count"],
        "end_equity": _safe_float(official_summary.get("end_equity")),
        "total_return_pct": _safe_float(official_summary.get("total_return_pct")),
        "max_drawdown_pct": _safe_float(official_summary.get("max_drawdown_pct")),
        "sharpe": _safe_float(official_summary.get("sharpe")),
        "total_slippage": _safe_float(official_summary.get("total_slippage")),
        "total_trade_count": _safe_float(official_summary.get("total_trade_count")),
        "closed_lot_win_rate_pct": _safe_float(official_summary.get("closed_lot_win_rate_pct")),
        "max_broker10_margin_to_equity_pct": _safe_float(
            official_summary.get("max_broker10_margin_to_equity_pct")
        ),
        "outputs": {
            "route_scorecard": ROUTE_SCORECARD_OUT,
            "local_catalog": LOCAL_CATALOG_OUT,
            "summary": SUMMARY_OUT,
            "decision": DECISION_OUT,
            "report": REPORT_OUT,
            "route_chart": ROUTE_CHART_OUT,
            "readiness_atlas": READINESS_ATLAS_OUT,
            "official_path_chart": OFFICIAL_PATH_CHART_OUT,
        },
    }

    _write_csv(route, ROUTE_SCORECARD_OUT)
    _write_csv(catalog, LOCAL_CATALOG_OUT)
    _write_csv(pd.DataFrame([summary]), SUMMARY_OUT)
    DECISION_OUT.write_text(json.dumps(_json_safe(summary), ensure_ascii=False, indent=2), encoding="utf-8")
    _plot_route_scorecard(route, ROUTE_CHART_OUT)
    _plot_readiness_atlas(route, READINESS_ATLAS_OUT)
    _plot_official_path(audit, curve, OFFICIAL_PATH_CHART_OUT)
    REPORT_OUT.write_text(_build_report(route, catalog, summary), encoding="utf-8")
    print(json.dumps(_json_safe(summary), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
