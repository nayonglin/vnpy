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
STAGE = "Stage075"
MODEL_TAG = "stage075_raw_authority_feature_gate_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage075_c9_minrisk_raw_authority_feature_gate_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage075_raw_authority_feature_gate_audit"

STAGE045_DIR = LINE_DIR / "outputs" / "stage045_event_time_field_sync_audit"
STAGE074_DIR = LINE_DIR / "outputs" / "stage074_initial_entry_authoritative_source_decision_audit"

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
RAW_AUTHORITY_ROOTS = [
    EXAMPLE_DIR / "downloaded_futures" / "tqsdk_stage452_true_path_fallback_1455",
    EXAMPLE_DIR / "downloaded_futures" / "tqsdk_stage448_minute_session_rebuild_batch",
]

AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_gate_audit_{MODEL_TAG}.csv"
PERMISSION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_permission_matrix_{MODEL_TAG}.csv"
CLASS_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_gate_class_summary_{MODEL_TAG}.csv"
YEAR_MATRIX_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_feature_gate_matrix_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_feature_gate_chart_{MODEL_TAG}.png"
PERMISSION_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_permission_chart_{MODEL_TAG}.png"
ATLAS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_gate_atlas_{MODEL_TAG}.png"

OFFICIAL_LIVE_VERSION = "official_live_stage847_c9_15w_stage819_05r_stop_retry_once"
OFFICIAL_LIVE_ALIAS = "Stage847-C9-15w"
INITIAL_CAPITAL = 150_000.0
EPS = 1e-9


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


def _safe_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if np.isfinite(result) else default


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


def _authority_tick_files() -> list[Path]:
    patterns = ["*tick*.csv", "*orderbook*.csv", "*order_book*.csv", "*depth*.csv", "*dur0*.csv"]
    files: list[Path] = []
    for root in RAW_AUTHORITY_ROOTS:
        if not root.exists():
            continue
        for pattern in patterns:
            files.extend(path for path in root.rglob(pattern) if path.is_file())
    return sorted(set(files))


def _prepare_audit(stage074: pd.DataFrame) -> pd.DataFrame:
    audit = stage074.copy()
    audit["official_open_date"] = pd.to_datetime(audit["official_open_date"], errors="coerce")
    audit["open_year"] = _safe_num(audit.get("open_year", audit["official_open_date"].dt.year)).fillna(
        audit["official_open_date"].dt.year
    )
    audit["realized_pnl"] = _safe_num(audit.get("realized_pnl", pd.Series(np.nan, index=audit.index))).fillna(0.0)
    for col in [
        "timestamp_ready",
        "raw_anchor_ready",
        "raw_anchor_exact_official",
        "raw_anchor_zero_volume",
        "raw_anchor_degenerate_ohlc",
        "stage449_anchor_ready",
        "stage449_anchor_exact_official",
        "tq_proxy_anchor_ready",
        "tq_price_exact_any",
    ]:
        audit[col] = _safe_num(audit.get(col, pd.Series(0, index=audit.index))).fillna(0).astype(int)

    audit["same_source_price_authority_ready"] = (
        audit["timestamp_ready"].eq(1)
        & audit["raw_anchor_ready"].eq(1)
        & audit["raw_anchor_exact_official"].eq(1)
    ).astype(int)
    audit["same_source_nonzero_volume_ready"] = (
        audit["same_source_price_authority_ready"].eq(1) & audit["raw_anchor_zero_volume"].eq(0)
    ).astype(int)
    audit["same_source_non_degenerate_ohlc_ready"] = (
        audit["same_source_price_authority_ready"].eq(1) & audit["raw_anchor_degenerate_ohlc"].eq(0)
    ).astype(int)
    audit["same_source_ohlcv_rule_ready"] = (
        audit["same_source_nonzero_volume_ready"].eq(1) & audit["same_source_non_degenerate_ohlc_ready"].eq(1)
    ).astype(int)
    audit["same_source_tick_orderbook_ready"] = 0
    audit["heterologous_tq_tick_ready"] = audit["tq_proxy_anchor_ready"]
    audit["heterologous_tq_tick_exact"] = audit["tq_price_exact_any"]

    def classify(row: pd.Series) -> str:
        source_class = str(row.get("source_decision_class", ""))
        if int(row["timestamp_ready"]) == 0:
            return "fallback_no_proxy_official_path_only"
        if "stage452_fallback" in source_class:
            return "raw_stage452_fallback_price_only_no_ohlcv"
        return "raw_stage449_price_only_no_ohlcv"

    audit["feature_gate_class"] = audit.apply(classify, axis=1)
    audit["allowed_research_scope"] = np.where(
        audit["feature_gate_class"].eq("fallback_no_proxy_official_path_only"),
        "official_path_or_data_refill_only",
        "price_boundary_audit_only",
    )
    audit["trading_rule_permission"] = "no_trade_rule"
    audit.loc[audit["same_source_price_authority_ready"].eq(1), "trading_rule_permission"] = (
        "bar_price_boundary_only_no_signal"
    )
    audit["rule_block_reason"] = np.select(
        [
            audit["feature_gate_class"].eq("fallback_no_proxy_official_path_only"),
            audit["same_source_ohlcv_rule_ready"].eq(0) & audit["same_source_price_authority_ready"].eq(1),
        ],
        [
            "no_raw_proxy_minute_authority",
            "raw_authority_is_zero_volume_ohlc_flat_price_proxy",
        ],
        default="unknown",
    )
    return audit


def _build_permission_matrix(audit: pd.DataFrame, authority_tick_file_count: int) -> pd.DataFrame:
    rows = [
        {
            "feature_bucket": "all_initial_opens",
            "event_count": int(len(audit)),
            "permission": "reference",
            "rule_use": "reference_only",
        },
        {
            "feature_bucket": "same_source_price_authority_exact",
            "event_count": int(audit["same_source_price_authority_ready"].sum()),
            "permission": "allowed_for_boundary_audit",
            "rule_use": "price_boundary_only",
        },
        {
            "feature_bucket": "stage449_same_source_price_authority",
            "event_count": int(
                (audit["stage449_anchor_ready"].eq(1) & audit["stage449_anchor_exact_official"].eq(1)).sum()
            ),
            "permission": "allowed_for_boundary_audit",
            "rule_use": "price_boundary_only",
        },
        {
            "feature_bucket": "stage452_raw_fallback_price_authority",
            "event_count": int(audit["feature_gate_class"].eq("raw_stage452_fallback_price_only_no_ohlcv").sum()),
            "permission": "fallback_mark_required",
            "rule_use": "price_boundary_only",
        },
        {
            "feature_bucket": "same_source_ohlcv_non_degenerate",
            "event_count": int(audit["same_source_ohlcv_rule_ready"].sum()),
            "permission": "blocked",
            "rule_use": "no_volume_range_body_rule",
        },
        {
            "feature_bucket": "same_source_tick_orderbook_local_files",
            "event_count": int(authority_tick_file_count),
            "permission": "missing",
            "rule_use": "no_spread_depth_imbalance_rule",
        },
        {
            "feature_bucket": "heterologous_tq_tick_batch_ready",
            "event_count": int(audit["heterologous_tq_tick_ready"].sum()),
            "permission": "blocked_heterologous",
            "rule_use": "tca_observation_only",
        },
        {
            "feature_bucket": "heterologous_tq_tick_exact",
            "event_count": int(audit["heterologous_tq_tick_exact"].sum()),
            "permission": "blocked_heterologous",
            "rule_use": "tca_observation_only",
        },
        {
            "feature_bucket": "fallback_no_proxy",
            "event_count": int(audit["feature_gate_class"].eq("fallback_no_proxy_official_path_only").sum()),
            "permission": "blocked_until_refill",
            "rule_use": "official_path_only",
        },
    ]
    return pd.DataFrame(rows)


def _summaries(audit: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    class_summary = (
        audit.groupby(["feature_gate_class", "allowed_research_scope", "rule_block_reason"], dropna=False)
        .agg(
            event_count=("candidate_index", "count"),
            same_source_price_authority_count=("same_source_price_authority_ready", "sum"),
            same_source_ohlcv_rule_ready_count=("same_source_ohlcv_rule_ready", "sum"),
            same_source_tick_orderbook_ready_count=("same_source_tick_orderbook_ready", "sum"),
            heterologous_tq_tick_ready_count=("heterologous_tq_tick_ready", "sum"),
            heterologous_tq_tick_exact_count=("heterologous_tq_tick_exact", "sum"),
            stage449_ready_count=("stage449_anchor_ready", "sum"),
            stage449_exact_count=("stage449_anchor_exact_official", "sum"),
            net_realized_pnl=("realized_pnl", "sum"),
            positive_pnl=("realized_pnl", lambda s: float(s[s > 0].sum())),
            negative_pnl_abs=("realized_pnl", lambda s: float(-s[s < 0].sum())),
        )
        .reset_index()
        .sort_values(["event_count", "net_realized_pnl"], ascending=[False, False])
    )
    year_matrix = (
        audit.groupby(["open_year", "feature_gate_class"], dropna=False)
        .agg(
            event_count=("candidate_index", "count"),
            same_source_price_authority_count=("same_source_price_authority_ready", "sum"),
            same_source_ohlcv_rule_ready_count=("same_source_ohlcv_rule_ready", "sum"),
            heterologous_tq_tick_ready_count=("heterologous_tq_tick_ready", "sum"),
            net_realized_pnl=("realized_pnl", "sum"),
        )
        .reset_index()
        .sort_values(["open_year", "feature_gate_class"])
    )
    return class_summary, year_matrix


def _curve_for_markers(curve: pd.DataFrame) -> pd.DataFrame:
    data = curve.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    equity_col = "official_equity" if "official_equity" in data.columns else "account_equity"
    dd_col = "official_drawdown_pct" if "official_drawdown_pct" in data.columns else "drawdown_pct"
    data["plot_equity"] = _safe_num(data[equity_col])
    data["plot_drawdown_pct"] = _safe_num(data[dd_col])
    return data[["date", "plot_equity", "plot_drawdown_pct"]].dropna(subset=["date"]).sort_values("date")


def _marker_equity(audit: pd.DataFrame, curve: pd.DataFrame) -> pd.DataFrame:
    markers = audit.copy().sort_values("official_open_date")
    curve_index = curve.set_index("date")
    merged = pd.merge_asof(
        markers.sort_values("official_open_date"),
        curve_index[["plot_equity"]].reset_index().sort_values("date"),
        left_on="official_open_date",
        right_on="date",
        direction="backward",
    )
    return merged


def _plot_path_chart(audit: pd.DataFrame, curve: pd.DataFrame, path: Path) -> None:
    curve_plot = _curve_for_markers(curve)
    markers = _marker_equity(audit, curve_plot)
    colors = {
        "raw_stage449_price_only_no_ohlcv": "#009e73",
        "raw_stage452_fallback_price_only_no_ohlcv": "#0072b2",
        "fallback_no_proxy_official_path_only": "#9e9e9e",
    }
    fig, axes = plt.subplots(2, 1, figsize=(16, 9), sharex=False)
    axes[0].plot(curve_plot["date"], curve_plot["plot_equity"] / 1_000_000, color="#1f77b4", lw=1.8)
    for klass, group in markers.groupby("feature_gate_class"):
        axes[0].scatter(
            group["official_open_date"],
            group["plot_equity"] / 1_000_000,
            s=26,
            color=colors.get(klass, "#333333"),
            label=klass,
            alpha=0.82,
        )
    axes[0].set_title("Stage075 official path with feature-gate classes")
    axes[0].set_ylabel("Equity (million CNY)")
    axes[0].grid(alpha=0.25)
    axes[0].legend(loc="upper left", fontsize=9)

    event_curves = audit.sort_values(["official_open_date", "candidate_index"]).copy()
    for klass, group in event_curves.groupby("feature_gate_class"):
        axes[1].plot(
            group["official_open_date"],
            group["realized_pnl"].cumsum() / 10_000,
            marker="o",
            ms=3,
            lw=1.7,
            color=colors.get(klass, "#333333"),
            label=klass,
        )
    axes[1].axhline(0, color="#333333", lw=0.8)
    axes[1].set_title("Cumulative realized PnL by feature-gate class (not a trading rule)")
    axes[1].set_ylabel("Cumulative PnL (10k CNY)")
    axes[1].grid(alpha=0.25)
    axes[1].legend(loc="upper left", fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _plot_permission_chart(permission: pd.DataFrame, year_matrix: pd.DataFrame, path: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(17, 7))
    perm_colors = {
        "reference": "#7f7f7f",
        "allowed_for_boundary_audit": "#009e73",
        "fallback_mark_required": "#56b4e9",
        "blocked": "#d55e00",
        "missing": "#cc79a7",
        "blocked_heterologous": "#e69f00",
        "blocked_until_refill": "#999999",
    }
    order = permission.sort_values("event_count", ascending=True)
    axes[0].barh(
        order["feature_bucket"],
        order["event_count"],
        color=[perm_colors.get(x, "#333333") for x in order["permission"]],
    )
    axes[0].set_title("Feature permission matrix")
    axes[0].set_xlabel("Count")
    axes[0].grid(axis="x", alpha=0.25)

    pivot = (
        year_matrix.pivot_table(
            index="open_year", columns="feature_gate_class", values="event_count", aggfunc="sum", fill_value=0
        )
        .sort_index()
    )
    colors = {
        "fallback_no_proxy_official_path_only": "#9e9e9e",
        "raw_stage449_price_only_no_ohlcv": "#009e73",
        "raw_stage452_fallback_price_only_no_ohlcv": "#0072b2",
    }
    bottom = np.zeros(len(pivot))
    for col in pivot.columns:
        axes[1].bar(pivot.index.astype(str), pivot[col], bottom=bottom, label=col, color=colors.get(col))
        bottom += pivot[col].to_numpy()
    axes[1].set_title("Feature-gate classes by open year")
    axes[1].set_ylabel("Initial opens")
    axes[1].tick_params(axis="x", rotation=45)
    axes[1].legend(loc="upper right", fontsize=9)
    axes[1].grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _plot_feature_atlas(audit: pd.DataFrame, path: Path) -> None:
    features = [
        "same_source_price_authority_ready",
        "stage449_anchor_exact_official",
        "same_source_nonzero_volume_ready",
        "same_source_non_degenerate_ohlc_ready",
        "same_source_tick_orderbook_ready",
        "heterologous_tq_tick_ready",
        "heterologous_tq_tick_exact",
    ]
    sample = (
        audit.sort_values(["feature_gate_class", "official_open_date", "candidate_index"])
        .groupby("feature_gate_class", group_keys=False)
        .head(7)
        .copy()
        .reset_index(drop=True)
    )
    if sample.empty:
        return
    matrix = sample[features].astype(float).to_numpy()
    fig, ax = plt.subplots(figsize=(13, max(6, 0.34 * len(sample) + 1.8)))
    ax.imshow(matrix, aspect="auto", cmap="Greens", vmin=0, vmax=1)
    ax.set_xticks(np.arange(len(features)))
    ax.set_xticklabels(features, rotation=35, ha="right")
    ylabels = [
        f"{row.official_open_trade_id} | {row.vt_symbol} | {row.official_open_date.date()} | {row.feature_gate_class}"
        for row in sample.itertuples()
    ]
    ax.set_yticks(np.arange(len(sample)))
    ax.set_yticklabels(ylabels, fontsize=8)
    for y in range(matrix.shape[0]):
        for x in range(matrix.shape[1]):
            ax.text(x, y, int(matrix[y, x]), ha="center", va="center", color="#111111", fontsize=8)
    ax.set_title("Stage075 feature gate atlas: 1 means field is ready, not necessarily tradable")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def _build_report(
    summary: dict[str, Any],
    permission: pd.DataFrame,
    class_summary: pd.DataFrame,
    year_matrix: pd.DataFrame,
) -> str:
    return f"""# Stage075 raw authority feature-gate 审计

## 结论

- 决策：`{summary["decision"]}`。
- 当前正式版：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`。
- initial opens：`{summary["initial_open_count"]}`。
- same-source price authority ready：`{summary["same_source_price_authority_count"]}`。
- same-source OHLCV non-degenerate ready：`{summary["same_source_ohlcv_rule_ready_count"]}`。
- same-source tick/orderbook local files：`{summary["authority_tick_file_count"]}`。
- heterologous Tq tick batch/exact：`{summary["heterologous_tq_tick_ready_count"]}` / `{summary["heterologous_tq_tick_exact_count"]}`。
- fallback no proxy：`{summary["fallback_no_proxy_count"]}`。
- 本阶段不新增交易规则、不跑 true engine、不触发 A/B。

## 官方基准

- 期末权益：`{summary["end_equity"]}`
- 总收益：`{summary["total_return_pct"]}`
- 最大回撤：`{summary["max_drawdown_pct"]}`
- Sharpe：`{summary["sharpe"]}`
- 总滑点：`{summary["total_slippage"]}`
- 总交易次数：`{summary["total_trade_count"]}`
- 胜率：`{summary["closed_lot_win_rate_pct"]}`
- broker10 峰值：`{summary["max_broker10_margin_to_equity_pct"]}`

## 特征许可矩阵

{_md_table(permission)}

## feature gate class summary

{_md_table(class_summary)}

## 年度矩阵

{_md_table(year_matrix)}

## 视觉文件

- official path feature gate chart：`{PATH_CHART_OUT}`
- feature permission chart：`{PERMISSION_CHART_OUT}`
- feature gate atlas：`{ATLAS_OUT}`

## 判断

- Stage075 的第一性判断是：raw proxy bar authority 只能证明 official open 的价格边界，不能提供高质量信号所需的真实量能、range/body 或盘口队列。
- 允许继续使用的字段只有 price-boundary 审计意义；它不足以构成开仓过滤、最小风险恢复、恢复风险或退出规则。
- 本地 raw authority 目录没有 same-source tick/orderbook 文件；已有 Tq tick 是异源观测，Stage073/074 已证明不能直接解释 official open。
- 因此下一步若继续策略目标，必须先补同源 tick/orderbook 或换真正外生、入场前可见、覆盖完整的数据源；否则只能做 bar-level 账本审计，不应写候选。
"""


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stage074 = _read_csv(STAGE074_AUDIT_IN)
    curve = _read_csv(STAGE045_CURVE_IN)
    summary_in = _read_csv(STAGE045_SUMMARY_IN)
    authority_tick_files = _authority_tick_files()

    audit = _prepare_audit(stage074)
    permission = _build_permission_matrix(audit, len(authority_tick_files))
    class_summary, year_matrix = _summaries(audit)

    official = summary_in.iloc[0].to_dict()
    summary = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "decision": "stage075_raw_authority_price_only_no_valid_minute_rule_without_same_source_data",
        "next_step": "get_same_source_tick_orderbook_or_external_preentry_source_before_rule",
        "strategy_rule_created": False,
        "true_engine_run": False,
        "ab_triggered": False,
        "initial_open_count": int(len(audit)),
        "same_source_price_authority_count": int(audit["same_source_price_authority_ready"].sum()),
        "same_source_ohlcv_rule_ready_count": int(audit["same_source_ohlcv_rule_ready"].sum()),
        "authority_tick_file_count": int(len(authority_tick_files)),
        "heterologous_tq_tick_ready_count": int(audit["heterologous_tq_tick_ready"].sum()),
        "heterologous_tq_tick_exact_count": int(audit["heterologous_tq_tick_exact"].sum()),
        "fallback_no_proxy_count": int(audit["feature_gate_class"].eq("fallback_no_proxy_official_path_only").sum()),
        "stage449_price_only_count": int(audit["feature_gate_class"].eq("raw_stage449_price_only_no_ohlcv").sum()),
        "stage452_fallback_price_only_count": int(
            audit["feature_gate_class"].eq("raw_stage452_fallback_price_only_no_ohlcv").sum()
        ),
        "end_equity": _safe_float(official.get("end_equity")),
        "total_return_pct": _safe_float(official.get("total_return_pct")),
        "max_drawdown_pct": _safe_float(official.get("max_drawdown_pct")),
        "sharpe": _safe_float(official.get("sharpe")),
        "total_slippage": _safe_float(official.get("total_slippage")),
        "total_trade_count": _safe_float(official.get("total_trade_count")),
        "closed_lot_win_rate_pct": _safe_float(official.get("closed_lot_win_rate_pct")),
        "max_broker10_margin_to_equity_pct": _safe_float(official.get("max_broker10_margin_to_equity_pct")),
        "outputs": {
            "audit": AUDIT_OUT,
            "permission": PERMISSION_OUT,
            "class_summary": CLASS_SUMMARY_OUT,
            "year_matrix": YEAR_MATRIX_OUT,
            "summary": SUMMARY_OUT,
            "decision": DECISION_OUT,
            "report": REPORT_OUT,
            "path_chart": PATH_CHART_OUT,
            "permission_chart": PERMISSION_CHART_OUT,
            "atlas": ATLAS_OUT,
        },
    }

    _write_csv(audit, AUDIT_OUT)
    _write_csv(permission, PERMISSION_OUT)
    _write_csv(class_summary, CLASS_SUMMARY_OUT)
    _write_csv(year_matrix, YEAR_MATRIX_OUT)
    _write_csv(pd.DataFrame([summary]), SUMMARY_OUT)
    DECISION_OUT.write_text(json.dumps(_json_safe(summary), ensure_ascii=False, indent=2), encoding="utf-8")

    _plot_path_chart(audit, curve, PATH_CHART_OUT)
    _plot_permission_chart(permission, year_matrix, PERMISSION_CHART_OUT)
    _plot_feature_atlas(audit, ATLAS_OUT)
    REPORT_OUT.write_text(_build_report(summary, permission, class_summary, year_matrix), encoding="utf-8")

    print(json.dumps(_json_safe(summary), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
