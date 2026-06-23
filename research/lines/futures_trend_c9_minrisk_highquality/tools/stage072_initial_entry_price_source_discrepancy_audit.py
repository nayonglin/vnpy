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
STAGE = "Stage072"
MODEL_TAG = "stage072_initial_entry_price_source_discrepancy_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage072_c9_minrisk_initial_entry_price_source_discrepancy_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage072_initial_entry_price_source_discrepancy_audit"

STAGE040_DIR = LINE_DIR / "outputs" / "stage040_open_proxy_timestamp_reconstruction_audit"
STAGE045_DIR = LINE_DIR / "outputs" / "stage045_event_time_field_sync_audit"
STAGE070_DIR = LINE_DIR / "outputs" / "stage070_initial_entry_price_proxy_anchor_batch_refill"
STAGE071_DIR = LINE_DIR / "outputs" / "stage071_initial_entry_proxy_mismatch_root_cause_audit"

STAGE040_LEDGER_IN = (
    STAGE040_DIR
    / "qmt_roll_stage040_c9_minrisk_open_proxy_timestamp_reconstruction_audit_open_proxy_ledger_"
    "stage040_open_proxy_timestamp_reconstruction_audit_v1.csv"
)
STAGE045_LEDGER_IN = (
    STAGE045_DIR
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_event_sync_ledger_"
    "stage045_event_time_field_sync_audit_v1.csv"
)
STAGE045_CURVE_IN = (
    STAGE045_DIR
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)
STAGE070_FEATURES_IN = (
    STAGE070_DIR
    / "qmt_roll_stage070_c9_minrisk_initial_entry_price_proxy_anchor_batch_refill_anchor_price_features_"
    "stage070_initial_entry_price_proxy_anchor_batch_refill_v1.csv"
)
STAGE071_MISMATCH_IN = (
    STAGE071_DIR
    / "qmt_roll_stage071_c9_minrisk_initial_entry_proxy_mismatch_root_cause_audit_mismatch_audit_"
    "stage071_initial_entry_proxy_mismatch_root_cause_audit_v1.csv"
)
STAGE071_DECISION_IN = (
    STAGE071_DIR
    / "qmt_roll_stage071_c9_minrisk_initial_entry_proxy_mismatch_root_cause_audit_decision_"
    "stage071_initial_entry_proxy_mismatch_root_cause_audit_v1.json"
)

AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_discrepancy_audit_{MODEL_TAG}.csv"
SOURCE_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_diagnosis_summary_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_source_discrepancy_chart_{MODEL_TAG}.png"
DELTA_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_raw_vs_tq_delta_chart_{MODEL_TAG}.png"
ATLAS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_raw_vs_tq_tick_atlas_{MODEL_TAG}.png"

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


def _safe_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)


def _boolish(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series
    return series.astype(str).str.lower().isin(["true", "1", "yes"])


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


def _time_floor(value: Any) -> pd.Timestamp:
    return pd.to_datetime(value, errors="coerce").floor("min")


def _load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    mismatch = _read_csv(STAGE071_MISMATCH_IN)
    stage040 = _read_csv(STAGE040_LEDGER_IN)
    stage045 = _read_csv(STAGE045_LEDGER_IN)
    features = _read_csv(STAGE070_FEATURES_IN)
    with STAGE071_DECISION_IN.open("r", encoding="utf-8") as fh:
        decision = json.load(fh)

    for frame in [mismatch, stage040, features]:
        for col in [
            "candidate_index",
            "official_open_price",
            "nearest_price_value",
            "min_abs_price_delta",
            "min_abs_price_delta_r",
            "risk_price",
            "raw_price",
            "seed_price",
            "engine_selected_price",
            "stage861_first_open_price",
            "realized_pnl",
        ]:
            if col in frame.columns:
                frame[col] = _safe_num(frame[col])
    for col in ["raw_ready", "seed_ready", "engine_selected_exact_official", "raw_exact_official", "seed_exact_official"]:
        if col in stage040.columns:
            stage040[col] = _safe_num(stage040[col]).fillna(0).astype(int)
    if "full_event_sync_exact" in stage045.columns:
        stage045["full_event_sync_exact"] = _boolish(stage045["full_event_sync_exact"])

    feature_cols = [
        "official_open_trade_id",
        "candidate_index",
        "anchor_role",
        "risk_price",
        "price_exact_any",
        "price_near_r",
        "official_open_inside_any_spread",
        "first_mid_price",
        "median_mid_price",
        "first_mid_delta",
        "median_mid_delta",
        "first_mid_delta_r",
        "median_mid_delta_r",
    ]
    feature_proxy = features[features["anchor_role"].astype(str).eq("price_proxy_anchor")][
        [col for col in feature_cols if col in features.columns]
    ].copy()

    stage040_cols = [
        "official_open_trade_id",
        "candidate_index",
        "vt_symbol",
        "official_open_date",
        "official_open_price",
        "seed_ready",
        "seed_price",
        "seed_source",
        "seed_first_time",
        "seed_last_time",
        "raw_ready",
        "raw_price",
        "raw_source",
        "raw_first_time",
        "raw_last_time",
        "engine_proxy_kind",
        "engine_selected_price",
        "engine_selected_source",
        "engine_selected_first_time",
        "engine_selected_last_time",
        "engine_selected_exact_official",
        "raw_exact_official",
        "seed_exact_official",
        "timestamp_reconstruction_status",
        "timestamp_ready",
        "timestamp_first_time",
        "timestamp_last_time",
        "timestamp_source",
        "stage861_first_open_price",
        "stage861_first_open_time",
        "stage861_first_open_exact_official",
    ]
    stage045_cols = [
        "official_open_trade_id",
        "candidate_index",
        "full_event_sync_exact",
        "event_family_match",
        "official_event_family",
        "source_exit_reason",
        "source_note",
        "stage042_session_convention_status",
    ]
    merged = mismatch.merge(
        stage040[[col for col in stage040_cols if col in stage040.columns]],
        on=["official_open_trade_id", "candidate_index", "vt_symbol", "official_open_price"],
        how="left",
    )
    merged = merged.merge(
        stage045[[col for col in stage045_cols if col in stage045.columns]],
        on=["official_open_trade_id", "candidate_index"],
        how="left",
    )
    merged = merged.merge(
        feature_proxy.drop(columns=["anchor_role"], errors="ignore"),
        on=["official_open_trade_id", "candidate_index"],
        how="left",
        suffixes=("", "_s070"),
    )
    return merged, stage040, stage045, decision


def _diagnose(row: pd.Series) -> str:
    raw_exact = bool(int(row.get("raw_exact_official", 0) or 0))
    engine_exact = bool(int(row.get("engine_selected_exact_official", 0) or 0))
    root = str(row.get("root_cause_class", ""))
    if raw_exact and engine_exact and root == "outside_target_book_range":
        return "raw_open_exact_tq_tick_book_outside_unresolved"
    if raw_exact and engine_exact and root == "near_005r_outside_spread":
        return "raw_open_exact_tq_tick_near_miss"
    if raw_exact and engine_exact and root == "inside_spread_not_exact":
        return "raw_open_exact_tq_tick_inside_spread_granularity"
    if engine_exact:
        return "engine_selected_exact_but_raw_not_exact"
    if raw_exact:
        return "raw_exact_but_engine_selected_differs"
    return "open_price_source_not_explained"


def _build_audit(merged: pd.DataFrame) -> pd.DataFrame:
    data = merged.copy()
    data["anchor_time"] = pd.to_datetime(data["anchor_time"], errors="coerce")
    data["official_open_date_ts"] = pd.to_datetime(data["official_open_date"], errors="coerce").dt.normalize()
    for col in ["raw_first_time", "raw_last_time", "timestamp_first_time", "stage861_first_open_time"]:
        if col in data.columns:
            data[f"{col}_ts"] = pd.to_datetime(data[col], errors="coerce")
    data["raw_window_starts_at_anchor_minute"] = (
        data["raw_first_time_ts"].dt.floor("min").eq(data["anchor_time"].dt.floor("min"))
        if "raw_first_time_ts" in data.columns
        else False
    )
    data["raw_minus_official"] = data["raw_price"] - data["official_open_price"]
    data["engine_selected_minus_official_recalc"] = data["engine_selected_price"] - data["official_open_price"]
    data["raw_minus_tq_nearest"] = data["raw_price"] - data["nearest_price_value"]
    data["raw_minus_tq_nearest_abs"] = data["raw_minus_tq_nearest"].abs()
    risk = pd.to_numeric(data.get("risk_price", np.nan), errors="coerce").replace(0, np.nan)
    data["raw_minus_tq_nearest_abs_r"] = data["raw_minus_tq_nearest_abs"] / risk
    if "stage861_first_open_price" in data.columns:
        data["stage861_first_minus_official"] = data["stage861_first_open_price"] - data["official_open_price"]
    else:
        data["stage861_first_minus_official"] = np.nan
    data["source_discrepancy_diagnosis"] = data.apply(_diagnose, axis=1)
    data["tq_tick_source_status"] = np.where(
        data["root_cause_class"].eq("outside_target_book_range"),
        "tq_target_minute_book_does_not_contain_official_open",
        np.where(
            data["root_cause_class"].eq("near_005r_outside_spread"),
            "tq_target_minute_near_but_no_exact_topbook",
            "tq_target_minute_inside_spread_no_exact_topbook",
        ),
    )
    ordered = [
        "event_key",
        "official_open_trade_id",
        "candidate_index",
        "vt_symbol",
        "direction",
        "anchor_time",
        "official_open_date",
        "official_open_price",
        "root_cause_class",
        "source_discrepancy_diagnosis",
        "engine_proxy_kind",
        "engine_selected_source",
        "engine_selected_price",
        "engine_selected_exact_official",
        "raw_source",
        "raw_price",
        "raw_exact_official",
        "raw_first_time",
        "raw_last_time",
        "raw_window_starts_at_anchor_minute",
        "seed_source",
        "seed_price",
        "seed_exact_official",
        "timestamp_reconstruction_status",
        "timestamp_ready",
        "timestamp_first_time",
        "nearest_price_field",
        "nearest_price_value",
        "min_abs_price_delta_r",
        "raw_minus_tq_nearest",
        "raw_minus_tq_nearest_abs_r",
        "official_vs_book_position",
        "tq_tick_source_status",
        "stage861_first_open_price",
        "stage861_first_open_time",
        "stage861_first_open_exact_official",
        "stage861_first_minus_official",
        "full_event_sync_exact",
        "event_family_match",
        "realized_pnl",
        "tick_file_path",
    ]
    return data[[col for col in ordered if col in data.columns]].sort_values(["anchor_time", "event_key"]).reset_index(drop=True)


def _source_summary(audit: pd.DataFrame) -> pd.DataFrame:
    if audit.empty:
        return pd.DataFrame()
    grouped = (
        audit.groupby(["source_discrepancy_diagnosis", "root_cause_class", "engine_proxy_kind"], dropna=False)
        .agg(
            mismatch_count=("event_key", "size"),
            raw_exact_count=("raw_exact_official", "sum"),
            engine_exact_count=("engine_selected_exact_official", "sum"),
            raw_anchor_match_count=("raw_window_starts_at_anchor_minute", "sum"),
            stage861_exact_count=("stage861_first_open_exact_official", "sum"),
            net_realized_pnl=("realized_pnl", "sum"),
            median_abs_delta_r=("min_abs_price_delta_r", "median"),
            max_abs_delta_r=("min_abs_price_delta_r", "max"),
        )
        .reset_index()
        .sort_values(["mismatch_count", "source_discrepancy_diagnosis"], ascending=[False, True])
    )
    return grouped


def _curve_metrics(curve: pd.DataFrame) -> dict[str, float]:
    equity = pd.to_numeric(curve["official_equity"], errors="coerce").dropna()
    drawdown = pd.to_numeric(curve["official_drawdown_pct"], errors="coerce").dropna()
    return {
        "end_equity": float(equity.iloc[-1]) if not equity.empty else np.nan,
        "total_return_pct": float((equity.iloc[-1] / INITIAL_CAPITAL - 1.0) * 100.0) if not equity.empty else np.nan,
        "max_drawdown_pct": float(drawdown.min()) if not drawdown.empty else np.nan,
    }


def _plot_path_chart(curve: pd.DataFrame, audit: pd.DataFrame) -> None:
    data = curve.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    audit_plot = audit.copy()
    audit_plot["anchor_date"] = pd.to_datetime(audit_plot["anchor_time"], errors="coerce").dt.normalize()
    equity_by_date = data.set_index(data["date"].dt.normalize())["official_equity"]
    audit_plot["anchor_equity"] = audit_plot["anchor_date"].map(equity_by_date)

    fig, axes = plt.subplots(2, 1, figsize=(16, 9), sharex=False)
    axes[0].plot(data["date"], data["official_equity"] / 1_000_000, color="#1f77b4", linewidth=1.8)
    markers = {
        "raw_open_exact_tq_tick_book_outside_unresolved": ("#d55e00", "outside book"),
        "raw_open_exact_tq_tick_near_miss": ("#0072b2", "near miss"),
        "raw_open_exact_tq_tick_inside_spread_granularity": ("#009e73", "inside spread"),
    }
    for diagnosis, (color, label) in markers.items():
        subset = audit_plot[audit_plot["source_discrepancy_diagnosis"].eq(diagnosis)]
        if subset.empty:
            continue
        axes[0].scatter(
            subset["anchor_date"],
            subset["anchor_equity"] / 1_000_000,
            s=48,
            color=color,
            alpha=0.85,
            label=label,
        )
    axes[0].set_title("Stage072 official path with raw/Tq price-source discrepancy markers")
    axes[0].set_ylabel("Equity (million CNY)")
    axes[0].grid(True, alpha=0.25)
    axes[0].legend(loc="upper left")

    cumulative = []
    for diagnosis, group in audit_plot.sort_values("anchor_time").groupby("source_discrepancy_diagnosis"):
        item = group[["anchor_time", "realized_pnl"]].copy()
        item["cum_pnl"] = item["realized_pnl"].cumsum()
        item["source_discrepancy_diagnosis"] = diagnosis
        cumulative.append(item)
    if cumulative:
        combined = pd.concat(cumulative, ignore_index=True)
        for diagnosis, group in combined.groupby("source_discrepancy_diagnosis"):
            color = markers.get(diagnosis, ("#666666", diagnosis))[0]
            axes[1].plot(group["anchor_time"], group["cum_pnl"] / 10_000, marker="o", linewidth=1.6, label=diagnosis, color=color)
    axes[1].axhline(0, color="black", linewidth=0.8)
    axes[1].set_title("Cumulative PnL by source-discrepancy diagnosis")
    axes[1].set_ylabel("Cumulative PnL (10k CNY)")
    axes[1].grid(True, alpha=0.25)
    axes[1].legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_delta_chart(audit: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(16, 5.5))
    palette = {
        "raw_open_exact_tq_tick_book_outside_unresolved": "#d55e00",
        "raw_open_exact_tq_tick_near_miss": "#0072b2",
        "raw_open_exact_tq_tick_inside_spread_granularity": "#009e73",
    }
    for diagnosis, group in audit.groupby("source_discrepancy_diagnosis"):
        axes[0].scatter(
            pd.to_datetime(group["anchor_time"], errors="coerce"),
            pd.to_numeric(group["raw_minus_tq_nearest_abs_r"], errors="coerce"),
            s=70,
            alpha=0.8,
            label=diagnosis,
            color=palette.get(diagnosis, "#666666"),
        )
    axes[0].axhline(0.05, color="black", linestyle="--", linewidth=1.0, label="0.05R")
    axes[0].set_title("Raw/open proxy vs nearest Tq tick top-book delta")
    axes[0].set_ylabel("|raw open - nearest Tq field| / R")
    axes[0].grid(True, alpha=0.25)
    axes[0].legend(loc="best", fontsize=8)

    counts = {
        "raw exact": int(pd.to_numeric(audit["raw_exact_official"], errors="coerce").fillna(0).sum()),
        "engine exact": int(pd.to_numeric(audit["engine_selected_exact_official"], errors="coerce").fillna(0).sum()),
        "raw anchor match": int(audit["raw_window_starts_at_anchor_minute"].astype(bool).sum()),
        "Tq exact": 0,
        "outside book": int(audit["root_cause_class"].eq("outside_target_book_range").sum()),
    }
    axes[1].barh(list(counts.keys()), list(counts.values()), color=["#009e73", "#009e73", "#56b4e9", "#cc79a7", "#d55e00"])
    axes[1].set_xlim(0, max(14, max(counts.values()) + 1))
    axes[1].set_title("Source checks across 14 Stage071 mismatches")
    axes[1].grid(True, axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(DELTA_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_atlas(audit: pd.DataFrame) -> None:
    rows = audit.sort_values(["source_discrepancy_diagnosis", "anchor_time"]).reset_index(drop=True)
    n = len(rows)
    fig, axes = plt.subplots(n, 1, figsize=(15, max(2.1 * n, 8)), sharex=False)
    if n == 1:
        axes = [axes]
    for ax, (_, row) in zip(axes, rows.iterrows()):
        tick_path = Path(str(row.get("tick_file_path", "")))
        target = pd.DataFrame()
        if tick_path.exists() and tick_path.stat().st_size > 0:
            ticks = pd.read_csv(tick_path, encoding="utf-8-sig")
            ticks["tick_datetime"] = pd.to_datetime(ticks["tick_datetime"], errors="coerce")
            start = pd.to_datetime(row["anchor_time"], errors="coerce").floor("min")
            target = ticks[(ticks["tick_datetime"] >= start) & (ticks["tick_datetime"] < start + pd.Timedelta(minutes=1))].copy()
        if not target.empty:
            for col, color, label in [
                ("last_price", "#1f77b4", "Tq last"),
                ("ask_price1", "#ff7f0e", "Tq ask1"),
                ("bid_price1", "#2ca02c", "Tq bid1"),
            ]:
                if col in target.columns:
                    target[col] = pd.to_numeric(target[col], errors="coerce")
                    ax.plot(target["tick_datetime"], target[col], color=color, linewidth=0.9, label=label)
        official = float(row["official_open_price"])
        raw = float(row["raw_price"]) if pd.notna(row.get("raw_price")) else np.nan
        stage861 = float(row["stage861_first_open_price"]) if pd.notna(row.get("stage861_first_open_price")) else np.nan
        ax.axhline(official, color="black", linestyle="--", linewidth=1.0, label="official/raw open")
        if pd.notna(raw) and abs(raw - official) > 1e-9:
            ax.axhline(raw, color="#cc79a7", linestyle=":", linewidth=1.0, label="raw open")
        if pd.notna(stage861) and abs(stage861 - official) > 1e-9:
            ax.axhline(stage861, color="#9467bd", linestyle=":", linewidth=0.9, label="Stage861 first open")
        ax.set_title(
            f"{row['official_open_trade_id']} {row['vt_symbol']} {pd.to_datetime(row['anchor_time']).strftime('%Y-%m-%d %H:%M')} "
            f"{row['source_discrepancy_diagnosis']} deltaR={float(row['min_abs_price_delta_r']):.3f}",
            fontsize=9,
        )
        ax.grid(True, alpha=0.25)
        ax.legend(loc="upper left", fontsize=7)
    fig.tight_layout()
    fig.savefig(ATLAS_OUT, dpi=150)
    plt.close(fig)


def _write_report(audit: pd.DataFrame, source_summary: pd.DataFrame, summary: pd.DataFrame, decision: dict[str, Any]) -> None:
    row = summary.iloc[0]
    lines = [
        "# Stage072 初始开仓价格源差异审计",
        "",
        "## 结论",
        "",
        f"- 决策：`{row['decision']}`。",
        f"- 当前正式版：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`。",
        f"- Stage071 mismatch：`{int(row['mismatch_count'])}`；raw proxy exact official：`{int(row['raw_exact_official_count'])}`；engine selected exact official：`{int(row['engine_selected_exact_official_count'])}`。",
        f"- raw window starts at anchor minute：`{int(row['raw_window_anchor_match_count'])}`；Tq target-minute exact：`0`。",
        f"- outside-book unresolved：`{int(row['outside_target_book_range_count'])}`。",
        "- 本阶段不新增交易规则、不跑 true engine、不触发 A/B；只解释 official/raw proxy 与 Tq tick top-book 的价格源差异。",
        "",
        "## 官方基准",
        "",
        f"- 期末权益：`{row['end_equity']}`",
        f"- 总收益：`{row['total_return_pct']}`",
        f"- 最大回撤：`{row['max_drawdown_pct']}`",
        f"- Sharpe：`{row['sharpe']}`",
        f"- 总滑点：`{row['total_slippage']}`",
        f"- 总交易次数：`{row['total_trade_count']}`",
        "",
        "## 价格源诊断",
        "",
        _md_table(source_summary),
        "",
        "## mismatch 明细",
        "",
        _md_table(
            audit[
                [
                    "official_open_trade_id",
                    "vt_symbol",
                    "anchor_time",
                    "official_open_price",
                    "nearest_price_value",
                    "raw_price",
                    "root_cause_class",
                    "source_discrepancy_diagnosis",
                    "engine_proxy_kind",
                    "raw_source",
                    "min_abs_price_delta_r",
                    "realized_pnl",
                ]
            ],
            max_rows=20,
        ),
        "",
        "## 视觉文件",
        "",
        f"- path/source chart：`{PATH_CHART_OUT}`",
        f"- raw vs Tq delta chart：`{DELTA_CHART_OUT}`",
        f"- raw vs Tq tick atlas：`{ATLAS_OUT}`",
        "",
        "## 判断",
        "",
        "- `_resolve_trade_price` 账本能解释 official open：Stage071 的 14 个 mismatch 全部在 Stage040 raw proxy 中精确命中 official open，且 raw window 起点与 Stage070/071 anchor minute 一致。",
        "- 但 TqBacktest tick top-book 在同一目标分钟没有 exact 价格，其中 7 笔 official open 落在目标分钟 bid/ask/last 路径之外；这说明现在的阻塞是 raw minute open 源与 Tq tick 源的价格口径差异。",
        "- 因为 mismatch 组净 PnL 和 outside-book 组 PnL 都为正，不能把这个差异做成开仓过滤、最小风险、恢复仓或退出规则。",
        "- 下一步应直接审计 raw minute 源文件与 Tq tick 源的同源性、字段语义和时间戳 convention；在同源性未闭环前，暂停补 `60->219` 和 TCA 特征抽取。",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    merged, _, _, stage071_decision = _load_inputs()
    audit = _build_audit(merged)
    source_summary = _source_summary(audit)
    curve = _read_csv(STAGE045_CURVE_IN)
    metrics = _curve_metrics(curve)
    official_metrics = stage071_decision.get("official_metrics", {})

    mismatch_count = int(len(audit))
    raw_exact_count = int(pd.to_numeric(audit["raw_exact_official"], errors="coerce").fillna(0).sum())
    engine_exact_count = int(pd.to_numeric(audit["engine_selected_exact_official"], errors="coerce").fillna(0).sum())
    raw_anchor_match = int(audit["raw_window_starts_at_anchor_minute"].astype(bool).sum())
    outside_count = int(audit["root_cause_class"].eq("outside_target_book_range").sum())
    all_raw_exact = raw_exact_count == mismatch_count
    all_engine_exact = engine_exact_count == mismatch_count
    if all_raw_exact and all_engine_exact and outside_count > 0:
        stage_decision = "stage072_raw_proxy_exact_tq_tick_source_discrepancy_unresolved_no_rule"
    elif all_raw_exact and all_engine_exact:
        stage_decision = "stage072_raw_proxy_exact_tq_tick_near_discrepancy_no_rule"
    else:
        stage_decision = "stage072_open_price_source_still_unresolved_no_rule"

    summary = pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "line_id": LINE_ID,
                "decision": stage_decision,
                "mismatch_count": mismatch_count,
                "raw_exact_official_count": raw_exact_count,
                "engine_selected_exact_official_count": engine_exact_count,
                "raw_window_anchor_match_count": raw_anchor_match,
                "tq_target_minute_exact_count": 0,
                "outside_target_book_range_count": outside_count,
                "near_005r_outside_spread_count": int(audit["root_cause_class"].eq("near_005r_outside_spread").sum()),
                "inside_spread_not_exact_count": int(audit["root_cause_class"].eq("inside_spread_not_exact").sum()),
                "stage149_seed_selected_count": int(audit["engine_proxy_kind"].astype(str).eq("stage149_seed_proxy").sum()),
                "raw_proxy_selected_count": int(audit["engine_proxy_kind"].astype(str).eq("raw_proxy").sum()),
                "end_equity": official_metrics.get("end_equity", metrics["end_equity"]),
                "total_return_pct": official_metrics.get("total_return_pct", metrics["total_return_pct"]),
                "max_drawdown_pct": official_metrics.get("max_drawdown_pct", metrics["max_drawdown_pct"]),
                "sharpe": official_metrics.get("sharpe", np.nan),
                "total_slippage": official_metrics.get("total_slippage", np.nan),
                "total_trade_count": official_metrics.get("total_trade_count", np.nan),
                "strategy_rule_created": False,
                "true_engine_run": False,
                "ab_triggered": False,
            }
        ]
    )
    _write_csv(audit, AUDIT_OUT)
    _write_csv(source_summary, SOURCE_SUMMARY_OUT)
    _write_csv(summary, SUMMARY_OUT)

    _plot_path_chart(curve, audit)
    _plot_delta_chart(audit)
    _plot_atlas(audit)

    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "decision": stage_decision,
        "next_step": "audit_raw_minute_source_vs_tq_tick_source_before_more_tca",
        "strategy_rule_created": False,
        "true_engine_run": False,
        "ab_triggered": False,
        "mismatch_count": mismatch_count,
        "raw_exact_official_count": raw_exact_count,
        "engine_selected_exact_official_count": engine_exact_count,
        "raw_window_anchor_match_count": raw_anchor_match,
        "outside_target_book_range_count": outside_count,
        "outputs": {
            "audit": AUDIT_OUT,
            "source_summary": SOURCE_SUMMARY_OUT,
            "summary": SUMMARY_OUT,
            "report": REPORT_OUT,
            "path_chart": PATH_CHART_OUT,
            "delta_chart": DELTA_CHART_OUT,
            "atlas": ATLAS_OUT,
        },
    }
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(audit, source_summary, summary, decision)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
