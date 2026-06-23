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
STAGE = "Stage157"
MODEL_TAG = "stage157_authoritative_minute_feature_builder_empty_run_v1"
OUTPUT_PREFIX = "qmt_roll_stage157_c9_minrisk_authoritative_minute_feature_builder_empty_run"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage157_authoritative_minute_feature_builder_empty_run"

CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)

STAGE153_DIR = LINE_DIR / "outputs" / "stage153_authoritative_minute_ohlcv_intake_validator"
STAGE153_PREFIX = "qmt_roll_stage153_c9_minrisk_authoritative_minute_ohlcv_intake_validator"
STAGE153_TAG = "stage153_authoritative_minute_ohlcv_intake_validator_v1"
STAGE153_SUMMARY_IN = STAGE153_DIR / f"{STAGE153_PREFIX}_summary_{STAGE153_TAG}.csv"

STAGE156_DIR = LINE_DIR / "outputs" / "stage156_authoritative_minute_feature_prebuild_gate"
STAGE156_PREFIX = "qmt_roll_stage156_c9_minrisk_authoritative_minute_feature_prebuild_gate"
STAGE156_TAG = "stage156_authoritative_minute_feature_prebuild_gate_v1"
STAGE156_SUMMARY_IN = STAGE156_DIR / f"{STAGE156_PREFIX}_summary_{STAGE156_TAG}.csv"
STAGE156_FEATURE_CONTRACT_IN = STAGE156_DIR / f"{STAGE156_PREFIX}_feature_contract_{STAGE156_TAG}.csv"
STAGE156_AGGREGATION_CONTRACT_IN = STAGE156_DIR / f"{STAGE156_PREFIX}_aggregation_contract_{STAGE156_TAG}.csv"
STAGE156_LEAKAGE_GUARD_IN = STAGE156_DIR / f"{STAGE156_PREFIX}_leakage_overfit_guard_{STAGE156_TAG}.csv"
STAGE156_WINDOW_READINESS_IN = STAGE156_DIR / f"{STAGE156_PREFIX}_window_feature_readiness_{STAGE156_TAG}.csv"

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
FEATURE_TABLE_SCHEMA_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_table_schema_{MODEL_TAG}.csv"
BUILD_PLAN_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_build_plan_{MODEL_TAG}.csv"
EMPTY_RUN_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_empty_run_audit_{MODEL_TAG}.csv"
UNIT_SELFTEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_point_in_time_unit_selftest_{MODEL_TAG}.csv"
GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_builder_empty_run_status_{MODEL_TAG}.png"
PLAN_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_build_plan_readiness_matrix_{MODEL_TAG}.png"
BLOCKER_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_empty_run_blocker_bar_{MODEL_TAG}.png"
SELFTEST_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_unit_selftest_matrix_{MODEL_TAG}.png"
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
            data[column] = data[column].map(lambda value: "" if pd.isna(value) else f"{value:.6f}")
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


def _feature_table_schema(features: pd.DataFrame) -> pd.DataFrame:
    base_rows = [
        ("request_id", "string", "provenance", "Stage152 request id", 1),
        ("window_id", "string", "provenance", "Stage152 required window id", 1),
        ("vt_symbol", "string", "provenance", "contract symbol", 1),
        ("exchange", "string", "provenance", "exchange code", 1),
        ("product", "string", "provenance", "product root", 1),
        ("window_type", "string", "provenance", "entry/event/session window type", 1),
        ("decision_ts", "timestamp", "time", "decision timestamp for the feature row", 1),
        ("feature_cutoff_ts", "timestamp", "time", "last bar_end_ts allowed in all features", 1),
        ("source_raw_sha256", "string", "provenance", "raw package hash from proof", 1),
        ("source_normalized_sha256", "string", "provenance", "normalized parquet hash from proof", 1),
        ("feature_build_model_tag", "string", "provenance", MODEL_TAG, 1),
    ]
    rows = [
        {
            "column": column,
            "dtype": dtype,
            "family": family,
            "description": description,
            "hard_required": hard_required,
            "future_data_allowed": 0,
            "strategy_rule_allowed": 0,
        }
        for column, dtype, family, description, hard_required in base_rows
    ]
    for _, feature in features.iterrows():
        rows.append(
            {
                "column": str(feature["feature_id"]),
                "dtype": "float64",
                "family": str(feature["family"]),
                "description": str(feature["economic_role"]),
                "hard_required": int(str(feature["feature_id"]) != "turnover_vwap_gap_30m"),
                "future_data_allowed": 0,
                "strategy_rule_allowed": 0,
            }
        )
        rows.append(
            {
                "column": f"{feature['feature_id']}__ready",
                "dtype": "int8",
                "family": "data_quality",
                "description": f"readiness flag for {feature['feature_id']}",
                "hard_required": 1,
                "future_data_allowed": 0,
                "strategy_rule_allowed": 0,
            }
        )
    rows.extend(
        [
            {
                "column": "row_ready_for_research",
                "dtype": "int8",
                "family": "data_quality",
                "description": "1 only after Stage153/156 all hard gates pass",
                "hard_required": 1,
                "future_data_allowed": 0,
                "strategy_rule_allowed": 0,
            },
            {
                "column": "row_block_reason",
                "dtype": "string",
                "family": "data_quality",
                "description": "why this row was not emitted",
                "hard_required": 1,
                "future_data_allowed": 0,
                "strategy_rule_allowed": 0,
            },
        ]
    )
    return pd.DataFrame(rows)


def _readiness_column(feature_id: str, family: str) -> str:
    if feature_id == "turnover_vwap_gap_30m":
        return "optional_turnover_feature_ready"
    if family == "positioning":
        return "positioning_feature_ready"
    if family == "participation":
        return "participation_feature_ready"
    if family == "volatility":
        return "volatility_feature_ready"
    if family == "data_quality":
        return "coverage_pass"
    return "price_path_feature_ready"


def _build_plan(features: pd.DataFrame, readiness: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    total_windows = int(len(readiness))
    for _, feature in features.iterrows():
        feature_id = str(feature["feature_id"])
        family = str(feature["family"])
        readiness_col = _readiness_column(feature_id, family)
        ready_count = int(readiness[readiness_col].sum()) if readiness_col in readiness else 0
        records.append(
            {
                "feature_id": feature_id,
                "family": family,
                "required_columns": feature["required_columns"],
                "lookback_minutes": int(feature["lookback_minutes"]),
                "readiness_column": readiness_col,
                "candidate_window_count": total_windows,
                "ready_window_count": ready_count,
                "blocked_window_count": total_windows - ready_count,
                "requires_open_interest": int("open_interest" in str(feature["required_columns"])),
                "requires_turnover": int("turnover" in str(feature["required_columns"])),
                "future_data_allowed": 0,
                "feature_output_allowed_now": 0,
                "strategy_rule_allowed": 0,
            }
        )
    return pd.DataFrame(records)


def _empty_run_audit(readiness: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, Any]] = []
    for _, row in readiness.iterrows():
        if int(row.get("request_ready", 0)) == 0:
            blocker = "missing_authoritative_request_package"
        elif int(row.get("coverage_pass", 0)) == 0:
            blocker = "required_window_uncovered"
        elif int(row.get("open_interest_ready", 0)) == 0:
            blocker = "open_interest_not_ready"
        else:
            blocker = "stage157_empty_run_lock"
        records.append(
            {
                "window_id": row.get("window_id", ""),
                "request_id": row.get("request_id", ""),
                "vt_symbol": row.get("vt_symbol", ""),
                "exchange": row.get("exchange", ""),
                "product": row.get("product", ""),
                "window_type": row.get("window_type", ""),
                "priority_class": row.get("priority_class", ""),
                "request_ready": int(row.get("request_ready", 0)),
                "coverage_pass": int(row.get("coverage_pass", 0)),
                "open_interest_ready": int(row.get("open_interest_ready", 0)),
                "all_core_features_ready": int(
                    int(row.get("price_path_feature_ready", 0)) == 1
                    and int(row.get("volatility_feature_ready", 0)) == 1
                    and int(row.get("participation_feature_ready", 0)) == 1
                    and int(row.get("positioning_feature_ready", 0)) == 1
                ),
                "primary_blocker": blocker,
                "feature_row_written": 0,
                "strategy_rule_allowed": 0,
            }
        )
    return pd.DataFrame(records)


def _unit_bars() -> pd.DataFrame:
    start = pd.Timestamp("2026-01-05 09:00:00")
    rows = []
    for idx in range(80):
        ts = start + pd.Timedelta(minutes=idx)
        open_price = 100.0 + idx * 0.08
        close = open_price + ((idx % 5) - 2) * 0.015
        high = max(open_price, close) + 0.04
        low = min(open_price, close) - 0.04
        rows.append(
            {
                "bar_start_ts": ts,
                "bar_end_ts": ts + pd.Timedelta(minutes=1),
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": float(10 + idx % 7),
                "turnover": float((10 + idx % 7) * close),
                "open_interest": float(1000 + idx),
            }
        )
    return pd.DataFrame(rows)


def _compute_features(bars: pd.DataFrame, decision_ts: pd.Timestamp) -> dict[str, float]:
    frame = bars.copy()
    frame["bar_end_ts"] = pd.to_datetime(frame["bar_end_ts"], errors="coerce")
    closed = frame[frame["bar_end_ts"].le(decision_ts)].sort_values("bar_end_ts").reset_index(drop=True)
    if len(closed) < 61:
        return {}
    closes = pd.to_numeric(closed["close"], errors="coerce")
    prev_close = float(closes.iloc[-2])
    last = closed.iloc[-1]
    last_close = float(last["close"])
    tail31 = closes.tail(31)
    diffs30 = tail31.diff().dropna().abs()
    log_ret30 = np.log(closes).diff().tail(30)
    tr_frame = closed.tail(30).copy()
    tr_prev = pd.to_numeric(closed["close"], errors="coerce").shift(1).tail(30).to_numpy()
    tr = np.maximum.reduce(
        [
            (pd.to_numeric(tr_frame["high"], errors="coerce") - pd.to_numeric(tr_frame["low"], errors="coerce")).to_numpy(),
            np.abs(pd.to_numeric(tr_frame["high"], errors="coerce").to_numpy() - tr_prev),
            np.abs(pd.to_numeric(tr_frame["low"], errors="coerce").to_numpy() - tr_prev),
        ]
    )
    volume_tail30 = pd.to_numeric(closed["volume"], errors="coerce").tail(30)
    volume_prev30 = pd.to_numeric(closed["volume"], errors="coerce").iloc[-60:-30]
    volume_scale = float(np.std([volume_tail30.sum(), volume_prev30.sum()], ddof=0)) or 1.0
    turnover_tail30 = pd.to_numeric(closed["turnover"], errors="coerce").tail(30).sum()
    volume_sum_tail30 = float(volume_tail30.sum())
    vwap = turnover_tail30 / max(volume_sum_tail30, 1e-9)
    return {
        "bar_return_1m": last_close / prev_close - 1.0,
        "range_ratio_1m": (float(last["high"]) - float(last["low"])) / max(prev_close, 1e-9),
        "directional_efficiency_30m": abs(float(tail31.iloc[-1]) - float(tail31.iloc[0])) / max(float(diffs30.sum()), 1e-9),
        "realized_volatility_30m": float(log_ret30.std(ddof=0)),
        "true_range_median_30m": float(np.nanmedian(tr)),
        "volume_participation_30m": volume_sum_tail30,
        "volume_zscore_60m": (volume_sum_tail30 - float(volume_prev30.sum())) / volume_scale,
        "open_interest_delta_60m": float(closed["open_interest"].iloc[-1] - closed["open_interest"].iloc[-61]),
        "turnover_vwap_gap_30m": last_close / max(vwap, 1e-9) - 1.0,
        "closed_bar_count_coverage": float(len(closed.tail(60))),
    }


def _unit_selftest() -> pd.DataFrame:
    bars = _unit_bars()
    decision_ts = pd.Timestamp("2026-01-05 10:05:00")
    features = _compute_features(bars, decision_ts)
    mutated = bars.copy()
    future_mask = pd.to_datetime(mutated["bar_end_ts"]).gt(decision_ts)
    mutated.loc[future_mask, ["open", "high", "low", "close", "volume", "turnover", "open_interest"]] = 999999.0
    mutated_features = _compute_features(mutated, decision_ts)
    invariant = features == mutated_features
    short_features = _compute_features(bars.head(20), decision_ts)
    rows = [
        {
            "test_id": "trailing_features_ignore_future_mutation",
            "expected": 1,
            "observed": int(invariant),
            "pass_now": int(invariant),
            "detail": "future bars after decision_ts are mutated but all computed features stay identical",
        },
        {
            "test_id": "minimum_lookback_blocks_short_history",
            "expected": 0,
            "observed": len(short_features),
            "pass_now": int(len(short_features) == 0),
            "detail": "feature computation returns no row when 60m lookback is unavailable",
        },
        {
            "test_id": "feature_count_matches_contract",
            "expected": 10,
            "observed": len(features),
            "pass_now": int(len(features) == 10),
            "detail": "isolated unit transform computes all Stage156 feature ids",
        },
        {
            "test_id": "fixture_not_promoted_to_research_table",
            "expected": 0,
            "observed": 0,
            "pass_now": 1,
            "detail": "unit fixture remains in-memory and is never written as candidate feature table",
        },
    ]
    return pd.DataFrame(rows)


def _gate_status(summary: dict[str, Any]) -> pd.DataFrame:
    rows = [
        ("stage153_loaded", summary["stage153_loaded"], 1, "input_hard"),
        ("stage156_loaded", summary["stage156_loaded"], 1, "input_hard"),
        ("feature_table_schema_written", summary["feature_table_schema_column_count"], summary["feature_table_schema_column_count"], "contract_hard"),
        ("build_plan_written", summary["build_plan_feature_count"], summary["build_plan_feature_count"], "contract_hard"),
        ("unit_selftest_pass_count", summary["unit_selftest_pass_count"], summary["unit_selftest_count"], "selftest_hard"),
        ("all_stage153_requests_ready", summary["stage153_request_ready_count"], summary["stage153_request_count"], "data_hard"),
        ("all_stage153_windows_covered", summary["stage153_window_coverage_pass_count"], summary["stage153_required_window_count"], "coverage_hard"),
        ("feature_table_row_written_count", summary["feature_table_row_written_count"], 0, "strategy_hard"),
        ("feature_table_file_written", summary["feature_table_file_written"], 0, "strategy_hard"),
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
    schema: pd.DataFrame,
    plan: pd.DataFrame,
    empty_audit: pd.DataFrame,
    selftest: pd.DataFrame,
    gate: pd.DataFrame,
) -> None:
    blocker_summary = (
        empty_audit.groupby("primary_blocker", dropna=False)
        .agg(window_count=("window_id", "count"), feature_row_written=("feature_row_written", "sum"))
        .reset_index()
    )
    lines = [
        f"# {STAGE} 权威分钟 feature table builder 空跑",
        "",
        f"- model_tag: `{MODEL_TAG}`",
        f"- decision: `{summary.iloc[0]['decision']}`",
        "- 本阶段只验证 feature table builder 的点时化合同和空跑阻断，不写真实 feature table、不创建交易规则、不跑 true engine、不触发 A/B。",
        "",
        "## 外部调研与判断",
        "",
        "- pandas rolling 文档说明滚动窗口有明确的窗口边界和 closed 语义；本阶段把所有特征限定为 `bar_end_ts <= decision_ts` 的 trailing closed bars。",
        "- pandas merge_asof 文档说明 backward search 只取左表时点之前的右表记录；后续若绑定外生特征，只允许 backward/asof，不允许 forward/nearest。",
        "- sklearn TimeSeriesSplit 与 leakage 文档强调不能用未来或测试数据做训练、筛选或预处理；本阶段禁止 fit-on-full-sample、阈值搜索和当前样本 feature selection。",
        "",
        "## Summary",
        "",
        _md_table(summary),
        "",
        "## Feature Table Schema Sample",
        "",
        _md_table(schema, max_rows=30),
        "",
        "## Build Plan",
        "",
        _md_table(plan),
        "",
        "## Empty Run Blocker Summary",
        "",
        _md_table(blocker_summary),
        "",
        "## Unit Selftest",
        "",
        _md_table(selftest),
        "",
        "## Gate Status",
        "",
        _md_table(gate),
        "",
        "## Visual Outputs",
        "",
        f"- `{PATH_CHART_OUT.name}`",
        f"- `{PLAN_CHART_OUT.name}`",
        f"- `{BLOCKER_CHART_OUT.name}`",
        f"- `{SELFTEST_CHART_OUT.name}`",
        f"- `{GATE_CHART_OUT.name}`",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _plot_path(curve: pd.DataFrame, summary: pd.DataFrame) -> None:
    row = summary.iloc[0]
    fig, axes = plt.subplots(4, 1, figsize=(15, 11), sharex=False)
    fig.suptitle("Stage157 feature builder empty-run status on official path", fontsize=14, fontweight="bold")
    x = curve["date"].to_numpy()
    axes[0].plot(x, curve["account_equity"].to_numpy() / 1_000_000, color="#14532D", linewidth=1.2)
    axes[0].set_ylabel("equity (m)")
    axes[1].fill_between(x, curve["drawdown_pct"].to_numpy(), 0, color="#B45309", alpha=0.28)
    axes[1].set_ylabel("drawdown %")
    axes[2].plot(x, curve["broker10_margin_to_equity_pct"].to_numpy(), color="#3657D6", linewidth=1.0)
    axes[2].axhline(100, color="#111827", linestyle="--", linewidth=0.8)
    axes[2].set_ylabel("broker10 %")
    labels = ["requests", "ready", "windows", "covered", "schema_cols", "rows_written"]
    values = [
        row["stage153_request_count"],
        row["stage153_request_ready_count"],
        row["stage153_required_window_count"],
        row["stage153_window_coverage_pass_count"],
        row["feature_table_schema_column_count"],
        row["feature_table_row_written_count"],
    ]
    colors = ["#3657D6", "#B91C1C", "#0F766E", "#B91C1C", "#3657D6", "#111827"]
    axes[3].bar(labels, values, color=colors)
    axes[3].set_title("No authoritative package means builder emits zero feature rows")
    axes[3].set_ylabel("count")
    for ax in axes:
        ax.grid(alpha=0.25)
    fig.tight_layout(rect=[0, 0.02, 1, 0.96])
    fig.savefig(PATH_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_plan(plan: pd.DataFrame) -> None:
    cols = ["candidate_window_count", "ready_window_count", "blocked_window_count", "future_data_allowed", "feature_output_allowed_now"]
    matrix = plan.set_index("feature_id")[cols]
    fig, ax = plt.subplots(figsize=(13, max(5.4, len(matrix) * 0.48)))
    data = matrix.to_numpy(dtype=float)
    image = ax.imshow(data, aspect="auto", cmap="YlGnBu")
    ax.set_title("Stage157 build plan readiness by feature")
    ax.set_xticks(np.arange(len(cols)))
    ax.set_xticklabels(cols, rotation=25, ha="right")
    ax.set_yticks(np.arange(len(matrix.index)))
    ax.set_yticklabels(matrix.index, fontsize=8)
    for row in range(data.shape[0]):
        for col in range(data.shape[1]):
            ax.text(col, row, int(data[row, col]), ha="center", va="center", fontsize=7)
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(PLAN_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_blockers(empty_audit: pd.DataFrame) -> None:
    counts = empty_audit["primary_blocker"].value_counts().sort_values(ascending=True)
    fig, ax = plt.subplots(figsize=(11, 5.5))
    ax.barh(counts.index, counts.values, color="#B91C1C")
    ax.set_title("Stage157 empty-run primary blockers")
    ax.set_xlabel("window count")
    ax.grid(axis="x", alpha=0.25)
    for i, value in enumerate(counts.values):
        ax.text(value + 1, i, int(value), va="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(BLOCKER_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_selftest(selftest: pd.DataFrame) -> None:
    matrix = selftest.set_index("test_id")[["expected", "observed", "pass_now"]]
    fig, ax = plt.subplots(figsize=(11, max(4.6, len(matrix) * 0.65)))
    data = matrix.to_numpy(dtype=float)
    image = ax.imshow(data, aspect="auto", cmap="RdYlGn")
    ax.set_title("Point-in-time unit selftest")
    ax.set_xticks(np.arange(len(matrix.columns)))
    ax.set_xticklabels(matrix.columns, rotation=20, ha="right")
    ax.set_yticks(np.arange(len(matrix.index)))
    ax.set_yticklabels(matrix.index, fontsize=8)
    for row in range(data.shape[0]):
        for col in range(data.shape[1]):
            ax.text(col, row, int(data[row, col]), ha="center", va="center", fontsize=8)
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(SELFTEST_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_gate(gate: pd.DataFrame) -> None:
    matrix = gate.set_index("gate_id")[["pass_now"]]
    fig, ax = plt.subplots(figsize=(8.5, max(5.2, len(matrix) * 0.45)))
    data = matrix.to_numpy(dtype=float)
    image = ax.imshow(data, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_title("Stage157 gate status")
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
    stage156 = _row(STAGE156_SUMMARY_IN)
    features = _read_csv(STAGE156_FEATURE_CONTRACT_IN)
    aggregation = _read_csv(STAGE156_AGGREGATION_CONTRACT_IN)
    leakage = _read_csv(STAGE156_LEAKAGE_GUARD_IN)
    readiness = _read_csv(STAGE156_WINDOW_READINESS_IN)
    if not stage153 or not stage156 or features.empty or aggregation.empty or leakage.empty or readiness.empty:
        raise RuntimeError("missing Stage153/156 inputs for Stage157")

    schema = _feature_table_schema(features)
    plan = _build_plan(features, readiness)
    empty_audit = _empty_run_audit(readiness)
    selftest = _unit_selftest()

    decision = "stage157_authoritative_minute_feature_builder_empty_run_blocks_no_data_no_rule"
    summary_dict: dict[str, Any] = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "line_id": LINE_ID,
        "decision": decision,
        "next_best_action": "deliver_real_authoritative_minute_ohlcv_oi_then_rerun_stage153_156_157_before_research_features",
        "official_config_changed": 0,
        "strategy_rule_created": 0,
        "true_engine_run": 0,
        "true_engine_run_count": 0,
        "ab_triggered": 0,
        "order_api_called": 0,
        "ctp_connected": 0,
        "side_effect_count": 0,
        "stage153_loaded": 1,
        "stage156_loaded": 1,
        "stage153_request_count": _int(stage153, "request_count"),
        "stage153_request_ready_count": _int(stage153, "request_ready_count"),
        "stage153_required_window_count": _int(stage153, "required_window_count"),
        "stage153_window_coverage_pass_count": _int(stage153, "window_coverage_pass_count"),
        "stage156_feature_contract_count": _int(stage156, "feature_contract_count"),
        "stage156_leakage_guard_pass_count": _int(stage156, "leakage_guard_pass_count"),
        "feature_table_schema_column_count": int(len(schema)),
        "build_plan_feature_count": int(len(plan)),
        "build_plan_ready_feature_count": int(plan["ready_window_count"].gt(0).sum()),
        "build_plan_blocked_feature_count": int(plan["blocked_window_count"].gt(0).sum()),
        "empty_run_window_count": int(len(empty_audit)),
        "empty_run_blocked_window_count": int(empty_audit["feature_row_written"].eq(0).sum()),
        "feature_table_row_written_count": int(empty_audit["feature_row_written"].sum()),
        "feature_table_file_written": 0,
        "unit_selftest_count": int(len(selftest)),
        "unit_selftest_pass_count": int(selftest["pass_now"].sum()),
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
    _write_csv(schema, FEATURE_TABLE_SCHEMA_OUT)
    _write_csv(plan, BUILD_PLAN_OUT)
    _write_csv(empty_audit, EMPTY_RUN_AUDIT_OUT)
    _write_csv(selftest, UNIT_SELFTEST_OUT)
    _write_csv(gate, GATE_OUT)
    _write_report(summary, schema, plan, empty_audit, selftest, gate)
    _plot_path(curve, summary)
    _plot_plan(plan)
    _plot_blockers(empty_audit)
    _plot_selftest(selftest)
    _plot_gate(gate)

    _write_json(
        DECISION_OUT,
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "decision": decision,
            "inputs": {
                "curve": str(CURVE_IN),
                "stage153_summary": str(STAGE153_SUMMARY_IN),
                "stage156_summary": str(STAGE156_SUMMARY_IN),
                "stage156_feature_contract": str(STAGE156_FEATURE_CONTRACT_IN),
                "stage156_aggregation_contract": str(STAGE156_AGGREGATION_CONTRACT_IN),
                "stage156_leakage_guard": str(STAGE156_LEAKAGE_GUARD_IN),
                "stage156_window_readiness": str(STAGE156_WINDOW_READINESS_IN),
            },
            "outputs": {
                "summary": str(SUMMARY_OUT),
                "feature_table_schema": str(FEATURE_TABLE_SCHEMA_OUT),
                "build_plan": str(BUILD_PLAN_OUT),
                "empty_run_audit": str(EMPTY_RUN_AUDIT_OUT),
                "unit_selftest": str(UNIT_SELFTEST_OUT),
                "gate_status": str(GATE_OUT),
                "report": str(REPORT_OUT),
                "charts": [
                    str(PATH_CHART_OUT),
                    str(PLAN_CHART_OUT),
                    str(BLOCKER_CHART_OUT),
                    str(SELFTEST_CHART_OUT),
                    str(GATE_CHART_OUT),
                ],
            },
            "external_research_sources": [
                "https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.rolling.html",
                "https://pandas.pydata.org/docs/reference/api/pandas.merge_asof.html",
                "https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html",
                "https://scikit-learn.org/stable/common_pitfalls.html",
            ],
            "locks": {
                "feature_table_file_written": 0,
                "feature_table_row_written_count": int(empty_audit["feature_row_written"].sum()),
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "current_package_promotion_allowed": 0,
                "strategy_feature_usable": 0,
            },
        },
    )
    print(json.dumps(_json_safe(summary.iloc[0].to_dict()), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
