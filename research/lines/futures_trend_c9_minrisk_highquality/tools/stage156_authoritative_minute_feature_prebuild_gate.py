from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage156"
MODEL_TAG = "stage156_authoritative_minute_feature_prebuild_gate_v1"
OUTPUT_PREFIX = "qmt_roll_stage156_c9_minrisk_authoritative_minute_feature_prebuild_gate"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage156_authoritative_minute_feature_prebuild_gate"

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
STAGE152_FIELD_SCHEMA_IN = STAGE152_DIR / f"{STAGE152_PREFIX}_field_schema_{STAGE152_TAG}.csv"

STAGE153_DIR = LINE_DIR / "outputs" / "stage153_authoritative_minute_ohlcv_intake_validator"
STAGE153_PREFIX = "qmt_roll_stage153_c9_minrisk_authoritative_minute_ohlcv_intake_validator"
STAGE153_TAG = "stage153_authoritative_minute_ohlcv_intake_validator_v1"
STAGE153_SUMMARY_IN = STAGE153_DIR / f"{STAGE153_PREFIX}_summary_{STAGE153_TAG}.csv"
STAGE153_REQUEST_AUDIT_IN = STAGE153_DIR / f"{STAGE153_PREFIX}_request_file_audit_{STAGE153_TAG}.csv"
STAGE153_SCHEMA_AUDIT_IN = STAGE153_DIR / f"{STAGE153_PREFIX}_normalized_schema_audit_{STAGE153_TAG}.csv"
STAGE153_WINDOW_COVERAGE_IN = STAGE153_DIR / f"{STAGE153_PREFIX}_window_coverage_audit_{STAGE153_TAG}.csv"

STAGE155_DIR = LINE_DIR / "outputs" / "stage155_authoritative_minute_ohlcv_delivery_failure_modes"
STAGE155_PREFIX = "qmt_roll_stage155_c9_minrisk_authoritative_minute_ohlcv_delivery_failure_modes"
STAGE155_TAG = "stage155_authoritative_minute_ohlcv_delivery_failure_modes_v1"
STAGE155_SUMMARY_IN = STAGE155_DIR / f"{STAGE155_PREFIX}_summary_{STAGE155_TAG}.csv"

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
FEATURE_CONTRACT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_contract_{MODEL_TAG}.csv"
WINDOW_FEATURE_READINESS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_feature_readiness_{MODEL_TAG}.csv"
AGGREGATION_CONTRACT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_aggregation_contract_{MODEL_TAG}.csv"
LEAKAGE_GUARD_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_leakage_overfit_guard_{MODEL_TAG}.csv"
GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_feature_gate_status_{MODEL_TAG}.png"
FEATURE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_family_readiness_matrix_{MODEL_TAG}.png"
WINDOW_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_feature_readiness_heatmap_{MODEL_TAG}.png"
LEAKAGE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_leakage_guard_matrix_{MODEL_TAG}.png"
GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_matrix_{MODEL_TAG}.png"

REQUIRED_FEATURE_COLUMNS = ["open", "high", "low", "close", "volume", "open_interest"]


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
        else:
            data[column] = data[column].map(lambda value: "" if pd.isna(value) else str(value).replace("|", "\\|"))
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


def _feature_contract() -> pd.DataFrame:
    records = [
        {
            "feature_id": "bar_return_1m",
            "family": "price_path",
            "required_columns": "close",
            "lookback_minutes": 1,
            "formula": "closed_bar.close / previous_closed_bar.close - 1",
            "point_in_time_rule": "only closed bars strictly before decision timestamp",
            "economic_role": "local momentum / immediate adverse excursion context",
        },
        {
            "feature_id": "range_ratio_1m",
            "family": "price_path",
            "required_columns": "open,high,low,close",
            "lookback_minutes": 1,
            "formula": "(high - low) / max(previous_close, tick_size_proxy)",
            "point_in_time_rule": "current feature row uses completed bar only",
            "economic_role": "realized noise floor before risking capital",
        },
        {
            "feature_id": "directional_efficiency_30m",
            "family": "price_path",
            "required_columns": "close",
            "lookback_minutes": 30,
            "formula": "abs(close_t - close_t_minus_30) / sum(abs(diff(close)))",
            "point_in_time_rule": "rolling window ends before decision timestamp",
            "economic_role": "distinguish trend persistence from churn without final PnL labels",
        },
        {
            "feature_id": "realized_volatility_30m",
            "family": "volatility",
            "required_columns": "close",
            "lookback_minutes": 30,
            "formula": "std(log(close).diff()) over closed 30 minute window",
            "point_in_time_rule": "window excludes future event and post-decision bars",
            "economic_role": "risk budget denominator and stop distance sanity check",
        },
        {
            "feature_id": "true_range_median_30m",
            "family": "volatility",
            "required_columns": "high,low,close",
            "lookback_minutes": 30,
            "formula": "median(max(high-low, abs(high-prev_close), abs(low-prev_close)))",
            "point_in_time_rule": "uses previous close from already closed minute bars",
            "economic_role": "universal tradeability and slippage/noise proxy",
        },
        {
            "feature_id": "volume_participation_30m",
            "family": "participation",
            "required_columns": "volume",
            "lookback_minutes": 30,
            "formula": "sum(volume) and nonzero-volume minute share in closed lookback",
            "point_in_time_rule": "missing/no-trade bars follow vendor declared no-trade policy",
            "economic_role": "can the signal carry real participation rather than quote-only movement",
        },
        {
            "feature_id": "volume_zscore_60m",
            "family": "participation",
            "required_columns": "volume",
            "lookback_minutes": 60,
            "formula": "last_30m_volume versus previous closed 60m distribution",
            "point_in_time_rule": "uses only same contract historical minutes before decision",
            "economic_role": "participation surprise without product-specific thresholds",
        },
        {
            "feature_id": "open_interest_delta_60m",
            "family": "positioning",
            "required_columns": "open_interest",
            "lookback_minutes": 60,
            "formula": "last closed OI - first closed OI in 60m window",
            "point_in_time_rule": "requires real vendor OI, never synthetic fill",
            "economic_role": "whether movement is backed by position expansion or liquidation",
        },
        {
            "feature_id": "turnover_vwap_gap_30m",
            "family": "participation",
            "required_columns": "close,volume,turnover",
            "lookback_minutes": 30,
            "formula": "close / volume-weighted price proxy - 1 when turnover is authoritative",
            "point_in_time_rule": "optional; absent turnover blocks this feature only",
            "economic_role": "execution quality proxy when vendor provides authoritative turnover",
        },
        {
            "feature_id": "closed_bar_count_coverage",
            "family": "data_quality",
            "required_columns": "bar_start_ts,volume",
            "lookback_minutes": 60,
            "formula": "observed unique closed bars, duplicate count, nonzero-volume count",
            "point_in_time_rule": "quality field only, never alpha or product/year filter",
            "economic_role": "prevent false confidence from sparse or duplicated minute history",
        },
    ]
    frame = pd.DataFrame(records)
    frame["universal_rule"] = 1
    frame["contains_final_pnl_label"] = 0
    frame["contains_product_or_year_patch"] = 0
    frame["threshold_frozen"] = 1
    frame["strategy_rule_allowed"] = 0
    frame["feature_table_write_allowed_now"] = 0
    return frame


def _aggregation_contract() -> pd.DataFrame:
    rows = [
        ("open", "first closed 1m bar open in bucket", "price", "hard"),
        ("high", "max closed 1m bar high in bucket", "price", "hard"),
        ("low", "min closed 1m bar low in bucket", "price", "hard"),
        ("close", "last closed 1m bar close in bucket", "price", "hard"),
        ("volume", "sum authoritative 1m volume", "participation", "hard"),
        ("turnover", "sum authoritative 1m turnover when present", "participation", "optional"),
        ("open_interest", "last authoritative 1m open_interest in bucket", "positioning", "hard"),
        ("bar_start_ts", "left edge of closed bucket in Asia/Shanghai", "time", "hard"),
        ("bar_end_ts", "right edge of closed bucket in Asia/Shanghai", "time", "hard"),
    ]
    return pd.DataFrame(
        [
            {
                "field": field,
                "aggregation_rule": rule,
                "family": family,
                "requirement": requirement,
                "allowed_timeframes": "1m,5m,15m,30m",
                "future_bar_allowed": 0,
                "same_open_bar_execution_allowed": 0,
            }
            for field, rule, family, requirement in rows
        ]
    )


def _leakage_guard() -> pd.DataFrame:
    rows = [
        ("final_realized_pnl", "target_leakage", "profit/loss after entry is unavailable at decision time"),
        ("max_future_mfe_mae", "target_leakage", "future path magnitude would encode outcome"),
        ("post_event_stop_or_progress", "event_leakage", "event result must not define an entry-quality feature"),
        ("product_year_exception", "overfit_patch", "product/year cells are not universal market structure"),
        ("right_tail_label", "selection_leakage", "right-tail membership is a review label only"),
        ("bottom_loss_label", "selection_leakage", "bottom-loss membership is a review label only"),
        ("local_fixture_or_synthetic", "data_provenance", "non-authoritative files must not reach features"),
        ("vendor_ready_missing_as_alpha", "data_provenance", "data availability cannot become a trading condition"),
        ("threshold_search_current_sample", "overfit_patch", "no threshold search before OOS and feature table exist"),
    ]
    return pd.DataFrame(
        [
            {
                "blocked_input": blocked_input,
                "guard_family": guard_family,
                "reason": reason,
                "present_in_feature_contract": 0,
                "pass_now": 1,
                "strategy_rule_allowed": 0,
            }
            for blocked_input, guard_family, reason in rows
        ]
    )


def _window_feature_readiness(window_coverage: pd.DataFrame, request_audit: pd.DataFrame, schema_audit: pd.DataFrame) -> pd.DataFrame:
    ready_by_request = request_audit.set_index("request_id")["request_ready"].to_dict() if not request_audit.empty else {}
    oi_by_request = schema_audit.set_index("request_id")["optional_open_interest_present"].to_dict() if not schema_audit.empty else {}
    turnover_by_request = schema_audit.set_index("request_id")["optional_turnover_present"].to_dict() if not schema_audit.empty else {}
    rows: list[dict[str, Any]] = []
    for _, row in window_coverage.iterrows():
        request_id = str(row.get("request_id", ""))
        coverage_pass = int(row.get("coverage_pass", 0))
        request_ready = int(ready_by_request.get(request_id, 0))
        oi_ready = int(oi_by_request.get(request_id, 0))
        turnover_ready = int(turnover_by_request.get(request_id, 0))
        core_ready = int(coverage_pass == 1 and request_ready == 1)
        rows.append(
            {
                "window_id": row.get("window_id", ""),
                "request_id": request_id,
                "vt_symbol": row.get("vt_symbol", ""),
                "exchange": row.get("exchange", ""),
                "product": row.get("product", ""),
                "window_type": row.get("window_type", ""),
                "priority_class": row.get("priority_class", ""),
                "right_tail_visual": int(row.get("right_tail_visual", 0)),
                "bottom_loss_visual": int(row.get("bottom_loss_visual", 0)),
                "maxdd_context": int(row.get("maxdd_context", 0)),
                "coverage_pass": coverage_pass,
                "request_ready": request_ready,
                "open_interest_ready": oi_ready,
                "turnover_ready": turnover_ready,
                "price_path_feature_ready": core_ready,
                "volatility_feature_ready": core_ready,
                "participation_feature_ready": core_ready,
                "positioning_feature_ready": int(core_ready == 1 and oi_ready == 1),
                "optional_turnover_feature_ready": int(core_ready == 1 and turnover_ready == 1),
                "feature_table_row_allowed": 0,
                "strategy_rule_allowed": 0,
            }
        )
    return pd.DataFrame(rows)


def _gate_status(summary: dict[str, Any]) -> pd.DataFrame:
    rows = [
        ("stage153_loaded", summary["stage153_loaded"], 1, "input_hard"),
        ("stage155_negative_gate_loaded", summary["stage155_negative_gate_loaded"], 1, "input_hard"),
        ("feature_contract_written", summary["feature_contract_count"], summary["feature_contract_count"], "contract_hard"),
        ("leakage_guard_pass", summary["leakage_guard_pass_count"], summary["leakage_guard_count"], "leakage_hard"),
        ("all_stage153_requests_ready", summary["stage153_request_ready_count"], summary["stage153_request_count"], "data_hard"),
        ("all_required_windows_covered", summary["stage153_window_coverage_pass_count"], summary["stage153_required_window_count"], "coverage_hard"),
        ("all_feature_windows_ready", summary["feature_ready_window_count"], summary["stage153_required_window_count"], "feature_hard"),
        ("positioning_windows_ready", summary["positioning_feature_ready_window_count"], summary["stage153_required_window_count"], "feature_hard"),
        ("feature_table_write_allowed", summary["feature_table_write_allowed"], 0, "strategy_hard"),
        ("strategy_rule_created", summary["strategy_rule_created"], 0, "strategy_hard"),
        ("true_engine_run", summary["true_engine_run"], 0, "strategy_hard"),
        ("ab_triggered", summary["ab_triggered"], 0, "strategy_hard"),
        ("side_effect_count", summary["side_effect_count"], 0, "execution_hard"),
    ]
    return pd.DataFrame(
        [
            {
                "gate_id": gate_id,
                "observed": int(observed),
                "required": int(required),
                "pass_now": int(int(observed) == int(required)),
                "severity": severity,
            }
            for gate_id, observed, required, severity in rows
        ]
    )


def _write_report(
    summary: pd.DataFrame,
    features: pd.DataFrame,
    readiness: pd.DataFrame,
    aggregation: pd.DataFrame,
    leakage: pd.DataFrame,
    gate: pd.DataFrame,
) -> None:
    readiness_cols = [
        "window_id",
        "request_id",
        "vt_symbol",
        "window_type",
        "priority_class",
        "coverage_pass",
        "price_path_feature_ready",
        "participation_feature_ready",
        "positioning_feature_ready",
        "feature_table_row_allowed",
    ]
    lines = [
        f"# {STAGE} 权威分钟特征构建前置闸门",
        "",
        f"- model_tag: `{MODEL_TAG}`",
        f"- decision: `{summary.iloc[0]['decision']}`",
        "- 本阶段只冻结特征构建合同和泄漏/过拟合禁令；Stage153 未接收真实授权数据前，不写 feature table、不创建交易规则、不跑 true engine、不触发 A/B。",
        "",
        "## 外部调研与判断",
        "",
        "- Apache Arrow/Parquet 文档说明可先用 metadata/row group/schema 做轻量验收；因此 Stage156 只消费 Stage153 的验收结果，不绕过 raw/proof/window gate。",
        "- pandas Resampler.ohlc 与 vn.py BarGenerator 都强调 OHLC 聚合语义必须明确；因此 5m/15m/30m 只能由已闭合 1m bar 聚合，volume 求和，open_interest 取末值。",
        "- vn.py BarData/TickData 结构包含 volume、turnover、open_interest；本阶段把 OI 作为定位/持仓类硬字段，把 turnover 作为可选字段，避免用无成交量或伪 OI 设计分钟信号。",
        "",
        "## Summary",
        "",
        _md_table(summary),
        "",
        "## Feature Contract",
        "",
        _md_table(features),
        "",
        "## Aggregation Contract",
        "",
        _md_table(aggregation),
        "",
        "## Leakage / Overfit Guard",
        "",
        _md_table(leakage),
        "",
        "## Window Feature Readiness Sample",
        "",
        _md_table(readiness[readiness_cols], max_rows=24),
        "",
        "## Gate Status",
        "",
        _md_table(gate),
        "",
        "## Visual Outputs",
        "",
        f"- `{PATH_CHART_OUT.name}`",
        f"- `{FEATURE_CHART_OUT.name}`",
        f"- `{WINDOW_CHART_OUT.name}`",
        f"- `{LEAKAGE_CHART_OUT.name}`",
        f"- `{GATE_CHART_OUT.name}`",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _plot_path(curve: pd.DataFrame, summary: pd.DataFrame) -> None:
    row = summary.iloc[0]
    fig, axes = plt.subplots(4, 1, figsize=(15, 11), sharex=False)
    fig.suptitle("Stage156 authoritative minute feature prebuild gate on official path", fontsize=14, fontweight="bold")
    x = curve["date"].to_numpy()
    axes[0].plot(x, curve["account_equity"].to_numpy() / 1_000_000, color="#14532D", linewidth=1.2)
    axes[0].set_ylabel("equity (m)")
    axes[1].fill_between(x, curve["drawdown_pct"].to_numpy(), 0, color="#B45309", alpha=0.28)
    axes[1].set_ylabel("drawdown %")
    axes[2].plot(x, curve["broker10_margin_to_equity_pct"].to_numpy(), color="#3657D6", linewidth=1.0)
    axes[2].axhline(100, color="#111827", linestyle="--", linewidth=0.8)
    axes[2].set_ylabel("broker10 %")
    labels = ["requests", "ready", "windows", "covered", "feature_ready", "feature_table"]
    values = [
        row["stage153_request_count"],
        row["stage153_request_ready_count"],
        row["stage153_required_window_count"],
        row["stage153_window_coverage_pass_count"],
        row["feature_ready_window_count"],
        row["feature_table_write_allowed"],
    ]
    colors = ["#3657D6", "#B91C1C", "#0F766E", "#B91C1C", "#B91C1C", "#111827"]
    axes[3].bar(labels, values, color=colors)
    axes[3].set_title("Feature build remains blocked until real authorized 1m OHLCV+OI windows pass Stage153")
    axes[3].set_ylabel("count / flag")
    for ax in axes:
        ax.grid(alpha=0.25)
    fig.tight_layout(rect=[0, 0.02, 1, 0.96])
    fig.savefig(PATH_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_feature_matrix(features: pd.DataFrame, readiness: pd.DataFrame) -> None:
    ready_map = {
        "price_path": int(readiness["price_path_feature_ready"].sum()) if not readiness.empty else 0,
        "volatility": int(readiness["volatility_feature_ready"].sum()) if not readiness.empty else 0,
        "participation": int(readiness["participation_feature_ready"].sum()) if not readiness.empty else 0,
        "positioning": int(readiness["positioning_feature_ready"].sum()) if not readiness.empty else 0,
        "data_quality": int(readiness["coverage_pass"].sum()) if not readiness.empty else 0,
    }
    rows = []
    for family, frame in features.groupby("family", dropna=False):
        rows.append(
            {
                "family": family,
                "feature_count": int(len(frame)),
                "universal_rule": int(frame["universal_rule"].min()),
                "no_pnl_label": int((frame["contains_final_pnl_label"] == 0).all()),
                "no_product_year_patch": int((frame["contains_product_or_year_patch"] == 0).all()),
                "ready_window_count": int(ready_map.get(str(family), 0)),
                "feature_table_allowed": int(frame["feature_table_write_allowed_now"].max()),
            }
        )
    matrix = pd.DataFrame(rows).set_index("family")
    cols = ["feature_count", "universal_rule", "no_pnl_label", "no_product_year_patch", "ready_window_count", "feature_table_allowed"]
    fig, ax = plt.subplots(figsize=(12.5, max(4.8, len(matrix) * 0.8)))
    data = matrix[cols].to_numpy(dtype=float)
    image = ax.imshow(data, aspect="auto", cmap="YlGnBu")
    ax.set_title("Stage156 feature family contract and readiness")
    ax.set_xticks(np.arange(len(cols)))
    ax.set_xticklabels(cols, rotation=25, ha="right")
    ax.set_yticks(np.arange(len(matrix.index)))
    ax.set_yticklabels(matrix.index)
    for row in range(data.shape[0]):
        for col in range(data.shape[1]):
            ax.text(col, row, int(data[row, col]), ha="center", va="center", fontsize=8)
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(FEATURE_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_window_readiness(readiness: pd.DataFrame) -> None:
    cols = [
        "coverage_pass",
        "price_path_feature_ready",
        "participation_feature_ready",
        "positioning_feature_ready",
        "optional_turnover_feature_ready",
    ]
    if readiness.empty:
        matrix = pd.DataFrame(columns=cols)
    else:
        total = pd.crosstab(readiness["window_type"], readiness["priority_class"]).sort_index()
        rows = []
        for window_type in total.index:
            row = {"window_type": window_type}
            subset = readiness[readiness["window_type"].eq(window_type)]
            for col in cols:
                row[col] = int(subset[col].sum())
            row["window_count"] = int(len(subset))
            rows.append(row)
        matrix = pd.DataFrame(rows).set_index("window_type")
    fig, ax = plt.subplots(figsize=(12, max(4.8, len(matrix) * 0.8)))
    data = matrix[cols + ["window_count"]].to_numpy(dtype=float) if not matrix.empty else np.zeros((1, len(cols) + 1))
    labels_y = list(matrix.index) if not matrix.empty else ["no_windows"]
    image = ax.imshow(data, aspect="auto", cmap="RdYlGn", vmin=0, vmax=max(1, data.max()))
    ax.set_title("Window-level feature readiness by window type")
    ax.set_xticks(np.arange(len(cols) + 1))
    ax.set_xticklabels(cols + ["window_count"], rotation=25, ha="right")
    ax.set_yticks(np.arange(len(labels_y)))
    ax.set_yticklabels(labels_y)
    for row in range(data.shape[0]):
        for col in range(data.shape[1]):
            ax.text(col, row, int(data[row, col]), ha="center", va="center", fontsize=8)
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(WINDOW_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_leakage_guard(leakage: pd.DataFrame) -> None:
    matrix = leakage.set_index("blocked_input")[["present_in_feature_contract", "pass_now", "strategy_rule_allowed"]]
    fig, ax = plt.subplots(figsize=(10, max(5.2, len(matrix) * 0.5)))
    data = matrix.to_numpy(dtype=float)
    image = ax.imshow(data, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_title("Leakage and overfit guard")
    ax.set_xticks(np.arange(len(matrix.columns)))
    ax.set_xticklabels(matrix.columns, rotation=25, ha="right")
    ax.set_yticks(np.arange(len(matrix.index)))
    ax.set_yticklabels(matrix.index, fontsize=8)
    for row in range(data.shape[0]):
        for col in range(data.shape[1]):
            ax.text(col, row, int(data[row, col]), ha="center", va="center", fontsize=8)
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(LEAKAGE_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_gate_matrix(gate: pd.DataFrame) -> None:
    matrix = gate.set_index("gate_id")[["pass_now"]].copy()
    fig, ax = plt.subplots(figsize=(8.5, max(5.2, len(matrix) * 0.45)))
    data = matrix.to_numpy(dtype=float)
    image = ax.imshow(data, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_title("Stage156 gate status")
    ax.set_xticks([0])
    ax.set_xticklabels(["pass_now"])
    ax.set_yticks(np.arange(len(matrix.index)))
    ax.set_yticklabels(matrix.index, fontsize=8)
    for row in range(data.shape[0]):
        ax.text(0, row, int(data[row, 0]), ha="center", va="center", fontsize=8)
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(GATE_CHART_OUT, dpi=170)
    plt.close(fig)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    curve = _load_curve()
    stage153 = _row(STAGE153_SUMMARY_IN)
    stage155 = _row(STAGE155_SUMMARY_IN)
    stage152_schema = _read_csv(STAGE152_FIELD_SCHEMA_IN)
    request_audit = _read_csv(STAGE153_REQUEST_AUDIT_IN)
    schema_audit = _read_csv(STAGE153_SCHEMA_AUDIT_IN)
    window_coverage = _read_csv(STAGE153_WINDOW_COVERAGE_IN)
    if not stage153 or not stage155 or stage152_schema.empty or request_audit.empty or schema_audit.empty or window_coverage.empty:
        raise RuntimeError("missing Stage152/153/155 inputs for Stage156")

    features = _feature_contract()
    aggregation = _aggregation_contract()
    leakage = _leakage_guard()
    readiness = _window_feature_readiness(window_coverage, request_audit, schema_audit)

    feature_ready_window_count = int(readiness["price_path_feature_ready"].sum()) if not readiness.empty else 0
    positioning_ready_window_count = int(readiness["positioning_feature_ready"].sum()) if not readiness.empty else 0
    feature_table_write_allowed = int(
        _int(stage153, "request_ready_count") == _int(stage153, "request_count")
        and _int(stage153, "window_coverage_pass_count") == _int(stage153, "required_window_count")
        and feature_ready_window_count == _int(stage153, "required_window_count")
        and positioning_ready_window_count == _int(stage153, "required_window_count")
    )
    # Even if a future package passes, this stage is only a gate/spec builder.
    feature_table_write_allowed = 0

    decision = "stage156_authoritative_minute_feature_prebuild_gate_blocked_no_real_data_no_rule"
    summary_dict: dict[str, Any] = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "line_id": LINE_ID,
        "decision": decision,
        "next_best_action": "deliver_real_authoritative_minute_ohlcv_oi_then_rerun_stage153_and_stage156_before_feature_table",
        "official_config_changed": 0,
        "strategy_rule_created": 0,
        "true_engine_run": 0,
        "true_engine_run_count": 0,
        "ab_triggered": 0,
        "order_api_called": 0,
        "ctp_connected": 0,
        "side_effect_count": 0,
        "stage153_loaded": 1,
        "stage155_negative_gate_loaded": 1,
        "stage153_request_count": _int(stage153, "request_count"),
        "stage153_request_ready_count": _int(stage153, "request_ready_count"),
        "stage153_required_window_count": _int(stage153, "required_window_count"),
        "stage153_window_coverage_pass_count": _int(stage153, "window_coverage_pass_count"),
        "stage153_right_tail_window_coverage_pass_count": _int(stage153, "right_tail_window_coverage_pass_count"),
        "stage153_bottom_loss_window_coverage_pass_count": _int(stage153, "bottom_loss_window_coverage_pass_count"),
        "stage155_case_expectation_pass_count": _int(stage155, "case_expectation_pass_count"),
        "stage155_unexpected_ready_count": _int(stage155, "unexpected_ready_count"),
        "stage155_strategy_rule_allowed_count": _int(stage155, "strategy_rule_allowed_count"),
        "feature_contract_count": int(len(features)),
        "feature_family_count": int(features["family"].nunique()),
        "aggregation_contract_count": int(len(aggregation)),
        "leakage_guard_count": int(len(leakage)),
        "leakage_guard_pass_count": int(leakage["pass_now"].sum()),
        "feature_ready_window_count": feature_ready_window_count,
        "positioning_feature_ready_window_count": positioning_ready_window_count,
        "optional_turnover_feature_ready_window_count": int(readiness["optional_turnover_feature_ready"].sum()) if not readiness.empty else 0,
        "feature_table_write_allowed": feature_table_write_allowed,
        "current_package_promotion_allowed": 0,
        "true_engine_allowed": 0,
        "strategy_feature_usable": 0,
        "objective_completion_proven": 0,
        "visual_output_count": 5,
        "end_equity": float(stage153.get("end_equity", np.nan)),
        "total_return_pct": float(stage153.get("total_return_pct", np.nan)),
        "max_drawdown_pct": float(stage153.get("max_drawdown_pct", np.nan)),
        "sharpe": float(stage153.get("sharpe", np.nan)),
        "total_slippage": float(stage153.get("total_slippage", np.nan)),
        "total_trade_count": float(stage153.get("total_trade_count", np.nan)),
        "closed_lot_win_rate_pct": float(stage153.get("closed_lot_win_rate_pct", np.nan)),
        "max_broker10_margin_to_equity_pct": float(stage153.get("max_broker10_margin_to_equity_pct", np.nan)),
    }
    summary = pd.DataFrame([summary_dict])
    gate = _gate_status(summary_dict)

    _write_csv(summary, SUMMARY_OUT)
    _write_csv(features, FEATURE_CONTRACT_OUT)
    _write_csv(readiness, WINDOW_FEATURE_READINESS_OUT)
    _write_csv(aggregation, AGGREGATION_CONTRACT_OUT)
    _write_csv(leakage, LEAKAGE_GUARD_OUT)
    _write_csv(gate, GATE_OUT)
    _write_report(summary, features, readiness, aggregation, leakage, gate)
    _plot_path(curve, summary)
    _plot_feature_matrix(features, readiness)
    _plot_window_readiness(readiness)
    _plot_leakage_guard(leakage)
    _plot_gate_matrix(gate)

    _write_json(
        DECISION_OUT,
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "decision": decision,
            "inputs": {
                "curve": str(CURVE_IN),
                "stage152_field_schema": str(STAGE152_FIELD_SCHEMA_IN),
                "stage153_summary": str(STAGE153_SUMMARY_IN),
                "stage153_request_audit": str(STAGE153_REQUEST_AUDIT_IN),
                "stage153_schema_audit": str(STAGE153_SCHEMA_AUDIT_IN),
                "stage153_window_coverage": str(STAGE153_WINDOW_COVERAGE_IN),
                "stage155_summary": str(STAGE155_SUMMARY_IN),
            },
            "outputs": {
                "summary": str(SUMMARY_OUT),
                "feature_contract": str(FEATURE_CONTRACT_OUT),
                "window_feature_readiness": str(WINDOW_FEATURE_READINESS_OUT),
                "aggregation_contract": str(AGGREGATION_CONTRACT_OUT),
                "leakage_overfit_guard": str(LEAKAGE_GUARD_OUT),
                "gate_status": str(GATE_OUT),
                "report": str(REPORT_OUT),
                "charts": [
                    str(PATH_CHART_OUT),
                    str(FEATURE_CHART_OUT),
                    str(WINDOW_CHART_OUT),
                    str(LEAKAGE_CHART_OUT),
                    str(GATE_CHART_OUT),
                ],
            },
            "external_research_sources": [
                "https://arrow.apache.org/docs/python/parquet.html",
                "https://parquet.apache.org/docs/concepts/",
                "https://pandas.pydata.org/docs/reference/api/pandas.api.typing.Resampler.ohlc.html",
                "https://github.com/vnpy/vnpy/blob/master/vnpy/trader/utility.py",
                "https://github.com/vnpy/vnpy/blob/master/vnpy/trader/object.py",
            ],
            "locks": {
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "current_package_promotion_allowed": 0,
                "strategy_feature_usable": 0,
                "feature_table_write_allowed": feature_table_write_allowed,
            },
        },
    )
    print(json.dumps(_json_safe(summary.iloc[0].to_dict()), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
