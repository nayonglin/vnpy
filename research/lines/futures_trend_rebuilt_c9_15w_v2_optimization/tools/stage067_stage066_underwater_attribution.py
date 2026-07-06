from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json
import re
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
THIS_TOOLS_DIR = Path(__file__).resolve().parent
if str(THIS_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_TOOLS_DIR))

import stage066_stage065_monthly_multiperiod_true_engine as s066


LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage067"
MODEL_TAG = "stage067_stage066_underwater_attribution_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage067_stage066_underwater_attribution"

BASE_TRADING_CAPITAL = 150_000.0
TOTAL_INITIAL_CAPITAL = 300_000.0
REQUESTED_END = pd.Timestamp("2026-07-02")

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage067_stage066_underwater_attribution"
STAGES_DIR = LINE_DIR / "stages"

STAGE066_OUT = LINE_DIR / "outputs" / "stage066_stage065_monthly_multiperiod_true_engine"
STAGE066_SUMMARY_PATH = (
    STAGE066_OUT
    / "rebuilt_c9_v2_stage066_stage065_monthly_multiperiod_true_engine_summary_stage066_stage065_monthly_multiperiod_true_engine_v1.csv"
)
STAGE066_CURVES_PATH = (
    STAGE066_OUT
    / "rebuilt_c9_v2_stage066_stage065_monthly_multiperiod_true_engine_curves_stage066_stage065_monthly_multiperiod_true_engine_v1.csv.gz"
)
STAGE066_CASHFLOW_PATH = (
    STAGE066_OUT
    / "rebuilt_c9_v2_stage066_stage065_monthly_multiperiod_true_engine_cashflow_events_stage066_stage065_monthly_multiperiod_true_engine_v1.csv.gz"
)

PATH_METRICS_PATH = OUT / f"{OUTPUT_PREFIX}_path_underwater_metrics_{MODEL_TAG}.csv"
KEY_PATHS_PATH = OUT / f"{OUTPUT_PREFIX}_key_paths_{MODEL_TAG}.csv"
MONTHLY_PNL_PATH = OUT / f"{OUTPUT_PREFIX}_monthly_pnl_attribution_{MODEL_TAG}.csv"
PHASE_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_phase_summary_{MODEL_TAG}.csv"
PRODUCT_ATTRIBUTION_PATH = OUT / f"{OUTPUT_PREFIX}_key_product_direction_attribution_{MODEL_TAG}.csv"
PRODUCT_TOP_LOSERS_PATH = OUT / f"{OUTPUT_PREFIX}_key_product_direction_top_losers_{MODEL_TAG}.csv"
RERUN_VALIDATION_PATH = OUT / f"{OUTPUT_PREFIX}_key_rerun_validation_{MODEL_TAG}.csv"
CASHFLOW_ATTRIBUTION_PATH = OUT / f"{OUTPUT_PREFIX}_cashflow_attribution_{MODEL_TAG}.csv"
CHART_BURDEN_PATH = OUT / f"{OUTPUT_PREFIX}_underwater_burden_{MODEL_TAG}.png"
CHART_PRODUCT_PATH = OUT / f"{OUTPUT_PREFIX}_key_product_losers_{MODEL_TAG}.png"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


VERSION_LABELS = {
    "stage066_30w_idle_reserve_no_release": "no_release",
    "stage066_30w_daily_floor_release": "daily_release",
    "stage066_30w_month_end_floor_release": "month_end_release",
}


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if not np.isfinite(number) else number
    if isinstance(value, float):
        return None if not np.isfinite(value) else value
    return value


def _date_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return pd.Timestamp(value).date().isoformat()


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    return data.to_markdown(index=False)


def _product_from_vt_symbol(vt_symbol: Any) -> str:
    text = str(vt_symbol or "")
    if "." not in text:
        return text
    symbol, exchange = text.split(".", 1)
    product = "".join(ch for ch in symbol if ch.isalpha()) or symbol
    return f"{product}.{exchange}"


def _direction_from_position(start_pos: float, end_pos: float) -> str:
    pos = start_pos if abs(start_pos) > 1e-9 else end_pos
    if pos > 0:
        return "long"
    if pos < 0:
        return "short"
    return "flat"


def _load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if not STAGE066_SUMMARY_PATH.exists() or not STAGE066_CURVES_PATH.exists():
        raise RuntimeError("Stage066 summary/curves are missing; run Stage066 first")
    summary = pd.read_csv(STAGE066_SUMMARY_PATH)
    curves = pd.read_csv(STAGE066_CURVES_PATH)
    cashflow = pd.read_csv(STAGE066_CASHFLOW_PATH) if STAGE066_CASHFLOW_PATH.exists() else pd.DataFrame()
    curves["date"] = pd.to_datetime(curves["date"], errors="coerce").dt.normalize()
    curves = curves.dropna(subset=["date"]).sort_values(["version", "requested_start_month", "date"]).reset_index(drop=True)
    if not cashflow.empty:
        cashflow["date"] = pd.to_datetime(cashflow["date"], errors="coerce").dt.normalize()
    return summary, curves, cashflow


def _window_net_pnl(frame: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> float:
    window = frame[(frame["date"] >= start) & (frame["date"] <= end)].copy()
    return float(pd.to_numeric(window["net_pnl"], errors="coerce").fillna(0.0).sum())


def _path_metrics(curves: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (version, start_month), group in curves.groupby(["version", "requested_start_month"], sort=True):
        frame = group.sort_values("date").reset_index(drop=True).copy()
        equity = pd.to_numeric(frame["total_account_equity"], errors="coerce").ffill()
        broker_equity = pd.to_numeric(frame["broker_equity_with_cashflow"], errors="coerce").ffill()
        strategy_equity = pd.to_numeric(frame["strategy_equity_ex_cashflow"], errors="coerce").ffill()
        net_pnl = pd.to_numeric(frame["net_pnl"], errors="coerce").fillna(0.0)
        below = equity < TOTAL_INITIAL_CAPITAL - 1e-9
        first_below = frame.loc[below, "date"].min() if below.any() else pd.NaT
        last_below = frame.loc[below, "date"].max() if below.any() else pd.NaT
        trough_idx = int(equity.idxmin())
        trough_date = pd.Timestamp(frame.loc[trough_idx, "date"])
        trough_equity = float(equity.loc[trough_idx])
        actual_start = pd.Timestamp(frame["date"].min())
        final_date = pd.Timestamp(frame["date"].max())
        final_equity = float(equity.iloc[-1])
        final_strategy_equity = float(strategy_equity.iloc[-1])
        final_broker_equity = float(broker_equity.iloc[-1])
        days_below = int(below.sum())
        days_to_first_below = int((pd.Timestamp(first_below) - actual_start).days) if pd.notna(first_below) else 0
        days_to_trough = int((trough_date - actual_start).days)
        days_after_trough = int((final_date - trough_date).days)
        net_pnl_to_trough = float(net_pnl.iloc[: trough_idx + 1].sum())
        net_pnl_after_trough = float(net_pnl.iloc[trough_idx + 1 :].sum())
        first_90_end = actual_start + pd.Timedelta(days=90)
        first_180_end = actual_start + pd.Timedelta(days=180)
        first_252_end = actual_start + pd.Timedelta(days=365)
        rows.append(
            {
                "version": version,
                "variant_label": VERSION_LABELS.get(version, version),
                "requested_start_month": str(start_month),
                "actual_start": _date_text(actual_start),
                "final_date": _date_text(final_date),
                "first_below_initial_date": _date_text(first_below),
                "last_below_initial_date": _date_text(last_below),
                "ends_below_initial": bool(final_equity < TOTAL_INITIAL_CAPITAL - 1e-9),
                "total_account_days_below_initial": days_below,
                "days_to_first_below": days_to_first_below,
                "days_to_trough": days_to_trough,
                "days_after_trough_to_end": days_after_trough,
                "trough_date": _date_text(trough_date),
                "trough_total_account_equity": trough_equity,
                "trough_shortfall_to_300k": float(TOTAL_INITIAL_CAPITAL - trough_equity),
                "final_total_account_equity": final_equity,
                "final_strategy_equity_ex_cashflow": final_strategy_equity,
                "final_broker_equity_with_cashflow": final_broker_equity,
                "final_shortfall_to_300k": float(max(0.0, TOTAL_INITIAL_CAPITAL - final_equity)),
                "recovery_after_trough": float(final_equity - trough_equity),
                "net_pnl_to_trough": net_pnl_to_trough,
                "net_pnl_after_trough": net_pnl_after_trough,
                "net_pnl_first_90_calendar_days": _window_net_pnl(frame, actual_start, first_90_end),
                "net_pnl_first_180_calendar_days": _window_net_pnl(frame, actual_start, first_180_end),
                "net_pnl_first_365_calendar_days": _window_net_pnl(frame, actual_start, first_252_end),
                "total_net_pnl": float(net_pnl.sum()),
                "trade_count_sum": float(pd.to_numeric(frame["trade_count"], errors="coerce").fillna(0.0).sum()),
                "slippage_sum": float(pd.to_numeric(frame["slippage"], errors="coerce").fillna(0.0).sum()),
                "max_active_products": int(pd.to_numeric(frame.get("c3_active_products", 0), errors="coerce").fillna(0.0).max()),
                "max_external_cashflow_used": float(pd.to_numeric(frame["external_cashflow_cumulative"], errors="coerce").fillna(0.0).max()),
                "reserve_remaining_end": float(pd.to_numeric(frame["reserve_remaining"], errors="coerce").ffill().iloc[-1]),
            }
        )
    return pd.DataFrame(rows)


def _monthly_pnl(curves: pd.DataFrame) -> pd.DataFrame:
    frame = curves.copy()
    frame["calendar_month"] = frame["date"].dt.to_period("M").astype(str)
    group_cols = ["version", "variant_label", "requested_start_month", "calendar_month"]
    return (
        frame.groupby(group_cols, dropna=False, as_index=False)
        .agg(
            net_pnl=("net_pnl", "sum"),
            trade_count=("trade_count", "sum"),
            slippage=("slippage", "sum"),
            first_total_equity=("total_account_equity", "first"),
            last_total_equity=("total_account_equity", "last"),
            min_total_equity=("total_account_equity", "min"),
            max_active_products=("c3_active_products", "max"),
        )
        .sort_values(group_cols)
        .reset_index(drop=True)
    )


def _phase_summary(curves: pd.DataFrame, metrics: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    metric_map = {
        (row["version"], row["requested_start_month"]): row for _, row in metrics.iterrows()
    }
    for (version, start_month), group in curves.groupby(["version", "requested_start_month"], sort=True):
        key = (version, str(start_month))
        metric = metric_map[key]
        frame = group.sort_values("date").reset_index(drop=True).copy()
        frame["net_pnl"] = pd.to_numeric(frame["net_pnl"], errors="coerce").fillna(0.0)
        actual_start = pd.Timestamp(metric["actual_start"])
        trough = pd.Timestamp(metric["trough_date"])
        phases = {
            "start_to_trough": (actual_start, trough),
            "trough_to_end": (trough + pd.Timedelta(days=1), pd.Timestamp(metric["final_date"])),
        }
        for phase, (start, end) in phases.items():
            window = frame[(frame["date"] >= start) & (frame["date"] <= end)].copy()
            rows.append(
                {
                    "version": version,
                    "variant_label": VERSION_LABELS.get(version, version),
                    "requested_start_month": str(start_month),
                    "phase": phase,
                    "phase_start": _date_text(start),
                    "phase_end": _date_text(end),
                    "calendar_days": int(max(0, (end - start).days + 1)),
                    "trading_rows": int(len(window)),
                    "net_pnl": float(window["net_pnl"].sum()) if not window.empty else 0.0,
                    "trade_count": float(pd.to_numeric(window.get("trade_count", 0), errors="coerce").fillna(0.0).sum()) if not window.empty else 0.0,
                    "slippage": float(pd.to_numeric(window.get("slippage", 0), errors="coerce").fillna(0.0).sum()) if not window.empty else 0.0,
                    "min_total_equity": float(pd.to_numeric(window.get("total_account_equity", np.nan), errors="coerce").min()) if not window.empty else np.nan,
                    "max_active_products": int(pd.to_numeric(window.get("c3_active_products", 0), errors="coerce").fillna(0.0).max()) if not window.empty else 0,
                }
            )
    return pd.DataFrame(rows)


def _select_key_paths(metrics: pd.DataFrame) -> pd.DataFrame:
    ranked = metrics.sort_values(
        ["total_account_days_below_initial", "final_shortfall_to_300k"],
        ascending=[False, False],
    ).copy()
    selected = ranked.head(8).copy()
    selected["rank"] = range(1, len(selected) + 1)
    return selected


def _curve_validation(saved: pd.DataFrame, rerun: pd.DataFrame, version: str, start_month: str) -> dict[str, Any]:
    left = saved[
        saved["version"].eq(version) & saved["requested_start_month"].astype(str).eq(start_month)
    ][["date", "total_account_equity", "strategy_equity_ex_cashflow", "broker_equity_with_cashflow", "reserve_remaining"]].copy()
    right = rerun[["date", "total_account_equity", "strategy_equity_ex_cashflow", "broker_equity_with_cashflow", "reserve_remaining"]].copy()
    merged = left.merge(right, on="date", how="outer", suffixes=("_saved", "_rerun"))
    diffs = {}
    for column in ["total_account_equity", "strategy_equity_ex_cashflow", "broker_equity_with_cashflow", "reserve_remaining"]:
        a = pd.to_numeric(merged[f"{column}_saved"], errors="coerce")
        b = pd.to_numeric(merged[f"{column}_rerun"], errors="coerce")
        diffs[f"{column}_max_abs_diff"] = float((a - b).abs().max())
    diffs.update(
        {
            "version": version,
            "requested_start_month": start_month,
            "saved_rows": int(len(left)),
            "rerun_rows": int(len(right)),
            "merged_rows": int(len(merged)),
            "validation_pass": bool(max(diffs.values()) < 1e-6 and len(left) == len(right)),
        }
    )
    return diffs


def _position_product_attribution(
    positions: pd.DataFrame,
    version: str,
    start_month: str,
    trough_date: pd.Timestamp,
    final_date: pd.Timestamp,
) -> pd.DataFrame:
    if positions.empty:
        return pd.DataFrame()
    frame = positions.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    start = pd.Timestamp(f"{start_month}-01")
    frame = frame[(frame["date"] >= start) & (frame["date"] <= final_date)].copy()
    for column in ["start_pos", "end_pos", "pos_change", "trade_count", "holding_pnl", "trading_pnl", "net_pnl", "slippage"]:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    active = (
        frame["start_pos"].abs().gt(1e-9)
        | frame["end_pos"].abs().gt(1e-9)
        | frame["pos_change"].abs().gt(1e-9)
        | frame["trade_count"].abs().gt(1e-9)
        | frame["net_pnl"].abs().gt(1e-9)
    )
    frame = frame[active].copy()
    if frame.empty:
        return pd.DataFrame()
    frame["product"] = frame["vt_symbol"].map(_product_from_vt_symbol)
    frame["direction"] = frame.apply(
        lambda row: _direction_from_position(float(row["start_pos"]), float(row["end_pos"])), axis=1
    )
    frame["phase"] = np.where(frame["date"] <= trough_date, "start_to_trough", "trough_to_end")
    grouped = (
        frame.groupby(["product", "direction", "phase"], dropna=False, as_index=False)
        .agg(
            net_pnl=("net_pnl", "sum"),
            holding_pnl=("holding_pnl", "sum"),
            trading_pnl=("trading_pnl", "sum"),
            slippage=("slippage", "sum"),
            trade_count=("trade_count", "sum"),
            active_days=("date", "nunique"),
        )
        .sort_values("net_pnl")
        .reset_index(drop=True)
    )
    grouped["version"] = version
    grouped["variant_label"] = VERSION_LABELS.get(version, version)
    grouped["requested_start_month"] = start_month
    grouped["trough_date"] = _date_text(trough_date)
    return grouped[
        [
            "version",
            "variant_label",
            "requested_start_month",
            "trough_date",
            "phase",
            "product",
            "direction",
            "net_pnl",
            "holding_pnl",
            "trading_pnl",
            "slippage",
            "trade_count",
            "active_days",
        ]
    ]


def _rerun_key_paths(curves: pd.DataFrame, key_paths: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    metadata = s066.s064.s901.s513._metadata()
    product_frames: list[pd.DataFrame] = []
    validation_rows: list[dict[str, Any]] = []
    with s066.s064.s062._patched_live_ai_path(s066.s064.CANDIDATE_AI_PATH):
        for idx, row in key_paths.iterrows():
            version = str(row["version"])
            start_month = str(row["requested_start_month"])
            start = pd.Timestamp(f"{start_month}-01")
            print(f"[stage067] rerun key path {idx + 1}/{len(key_paths)} {version} {start_month}", flush=True)
            rerun_curve, frames = s066._run_variant(metadata, version, start)
            validation_rows.append(_curve_validation(curves, rerun_curve, version, start_month))
            product = _position_product_attribution(
                frames.get("positions", pd.DataFrame()),
                version,
                start_month,
                pd.Timestamp(row["trough_date"]),
                REQUESTED_END,
            )
            if not product.empty:
                product_frames.append(product)
    product = pd.concat(product_frames, ignore_index=True, sort=False) if product_frames else pd.DataFrame()
    validation = pd.DataFrame(validation_rows)
    return product, validation


def _cashflow_attribution(cashflow: pd.DataFrame) -> pd.DataFrame:
    if cashflow.empty:
        return pd.DataFrame()
    frame = cashflow.copy()
    for column in ["amount", "strategy_equity_ex_cashflow_before", "broker_equity_with_cashflow_before", "reserve_remaining_after"]:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    keep = [
        "version",
        "requested_start_month",
        "date",
        "amount",
        "strategy_equity_ex_cashflow_before",
        "broker_equity_with_cashflow_before",
        "broker_equity_with_cashflow_after",
        "reserve_remaining_after",
        "reason",
    ]
    existing = [column for column in keep if column in frame.columns]
    return frame[existing].sort_values(["version", "requested_start_month", "date"]).reset_index(drop=True)


def _plot(metrics: pd.DataFrame, key_paths: pd.DataFrame, product_top: pd.DataFrame) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(13, 6))
    data = key_paths.sort_values("rank").copy()
    labels = data["variant_label"] + "\n" + data["requested_start_month"].astype(str)
    x = np.arange(len(data))
    ax.bar(x - 0.2, data["trough_shortfall_to_300k"], width=0.4, label="trough shortfall to 300k", color="#dc2626")
    ax.bar(x + 0.2, data["recovery_after_trough"], width=0.4, label="recovery after trough", color="#16a34a")
    ax.axhline(0, color="#111827", linewidth=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=30, ha="right")
    ax.set_ylabel("RMB")
    ax.set_title("Stage067 key path underwater burden")
    ax.legend()
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(CHART_BURDEN_PATH, dpi=160)
    plt.close(fig)

    if not product_top.empty:
        fig, ax = plt.subplots(figsize=(13, 7))
        plot = product_top.copy()
        plot["path"] = plot["variant_label"] + " " + plot["requested_start_month"].astype(str)
        plot["label"] = plot["path"] + "\n" + plot["phase"] + " " + plot["product"] + " " + plot["direction"]
        plot = plot.sort_values("net_pnl").head(20)
        ax.barh(plot["label"], plot["net_pnl"], color="#b91c1c")
        ax.axvline(0, color="#111827", linewidth=0.8)
        ax.set_xlabel("net pnl")
        ax.set_title("Stage067 key product-direction losers")
        ax.grid(axis="x", alpha=0.25)
        fig.tight_layout()
        fig.savefig(CHART_PRODUCT_PATH, dpi=160)
        plt.close(fig)


def _write_records(
    metrics: pd.DataFrame,
    key_paths: pd.DataFrame,
    monthly: pd.DataFrame,
    phase: pd.DataFrame,
    product: pd.DataFrame,
    product_top: pd.DataFrame,
    validation: pd.DataFrame,
    cashflow_attr: pd.DataFrame,
) -> Path:
    now = datetime.now()
    validation_pass = int(pd.to_numeric(validation.get("validation_pass", 0), errors="coerce").fillna(0).sum()) if not validation.empty else 0
    validation_total = int(len(validation))
    top = key_paths.sort_values("rank").head(8).copy()
    by_variant = (
        metrics.groupby(["version", "variant_label"], as_index=False)
        .agg(
            start_count=("requested_start_month", "count"),
            max_underwater_days=("total_account_days_below_initial", "max"),
            median_underwater_days=("total_account_days_below_initial", "median"),
            end_below_count=("ends_below_initial", "sum"),
            median_trough_shortfall=("trough_shortfall_to_300k", "median"),
            median_final_shortfall=("final_shortfall_to_300k", "median"),
        )
        .sort_values("max_underwater_days", ascending=False)
    )
    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": now.isoformat(timespec="seconds"),
        "decision": "underwater_attribution_keep_research_only",
        "decision_reason": (
            "长水下不是储备会计 bug，主要来自若干起点在前段快速跌破 300k 后，后续趋势盈利不足以补回缺口；"
            "月末释放和日级释放会改变后续 sizing，但也会把坏阶段暴露放大，不能直接晋级。"
        ),
        "validation_pass_count": validation_pass,
        "validation_total": validation_total,
        "ai_path": str(s066.s064.CANDIDATE_AI_PATH),
        "outputs": {
            "path_metrics": str(PATH_METRICS_PATH),
            "key_paths": str(KEY_PATHS_PATH),
            "monthly_pnl": str(MONTHLY_PNL_PATH),
            "phase_summary": str(PHASE_SUMMARY_PATH),
            "product_attribution": str(PRODUCT_ATTRIBUTION_PATH),
            "product_top_losers": str(PRODUCT_TOP_LOSERS_PATH),
            "rerun_validation": str(RERUN_VALIDATION_PATH),
            "cashflow_attribution": str(CASHFLOW_ATTRIBUTION_PATH),
            "chart_burden": str(CHART_BURDEN_PATH),
            "chart_product": str(CHART_PRODUCT_PATH),
            "report": str(REPORT_PATH),
        },
        "overfit_reflection_before": "否。归因只读 Stage066 已有曲线并固定代表路径，不根据结果修改参数。",
        "overfit_reflection_after": "否。没有按水下月份调释放日、储备金额、品种或方向；逐品种结果只用于解释，不生成黑名单。",
        "continue_value_before": "有。用户关心 22/23 启动水下久，必须先拆清楚是口径、现金流、早期亏损还是后续恢复不足。",
        "continue_value_after": "有，但方向应转向账户层暴露治理和恢复段质量识别；不应继续按单月曲线 sweep 参数。",
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report_lines = [
        "# Stage067 Stage066 underwater attribution",
        "",
        f"- generated_at: `{now.isoformat(timespec='seconds')}`",
        f"- line_id: `{LINE_ID}`",
        f"- source curves: `{STAGE066_CURVES_PATH}`",
        f"- AI path locked for key reruns: `{s066.s064.CANDIDATE_AI_PATH}`",
        "- live config changed: `false`; CTP connected: `false`; order API calls: `0`",
        "",
        "## Variant Underwater Summary",
        "",
        _md_table(by_variant),
        "",
        "## Key Long Underwater Paths",
        "",
        _md_table(
            top[
                [
                    "rank",
                    "variant_label",
                    "requested_start_month",
                    "total_account_days_below_initial",
                    "trough_date",
                    "trough_shortfall_to_300k",
                    "recovery_after_trough",
                    "final_shortfall_to_300k",
                    "ends_below_initial",
                    "max_external_cashflow_used",
                ]
            ],
            max_rows=12,
        ),
        "",
        "## Key Product Direction Losers",
        "",
        _md_table(product_top.head(30), max_rows=30),
        "",
        "## Rerun Validation",
        "",
        _md_table(validation, max_rows=20),
        "",
        "## Decision",
        "",
        f"- decision: `{decision['decision']}`",
        f"- reason: {decision['decision_reason']}",
        f"- overfit before: {decision['overfit_reflection_before']}",
        f"- overfit after: {decision['overfit_reflection_after']}",
        f"- continue before: {decision['continue_value_before']}",
        f"- continue after: {decision['continue_value_after']}",
        "",
        "## Outputs",
        "",
    ]
    for key, path in decision["outputs"].items():
        report_lines.append(f"- {key}: `{path}`")
    REPORT_PATH.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    stage_path = STAGES_DIR / f"{now.strftime('%Y%m%d_%H%M')}_stage067_stage066_underwater_attribution.md"
    stage_lines = [
        "# Stage067 Stage066 水下时长归因",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：day",
        f"- 记录时间：{now.isoformat(timespec='seconds')}",
        f"- 工作区：`{ROOT}`",
        "- 是否重要突破：否，归因阶段；不改策略、不调参数、不晋级",
        "- 是否触发A/B：否，本阶段不提出接入正式版的候选变更",
        "",
        "## 外部调研与判断",
        "",
        "- GIPS/TWR 的核心提醒是外部现金流要和投资能力分离，本阶段继续把储备释放作为现金流和 sizing 变量，不计入 alpha。",
        "- GitHub/backtesting 常用最大回撤持续期和 underwater 概念说明，水下时长要和最大回撤幅度分开看；本阶段同时拆 `days below initial`、trough shortfall 和 recovery_after_trough。",
        "- Man Group/AQR 趋势跟随资料都提示趋势策略存在长期小亏等待右尾的结构；但本样本的问题不是一般趋势等待，而是部分起点右尾不足以补回前段缺口。",
        "",
        "## 本次变更",
        "",
        f"- 新增脚本：`{Path(__file__).relative_to(ROOT)}`",
        "- 修改正式入口：无",
        "- 删除文件：无",
        "- 新增参数：无交易参数；归因固定选取 Stage066 最长水下 8 条代表路径",
        "- 修改参数：无",
        "- 删除参数：无",
        "",
        "## 归因口径",
        "",
        "- 总账户权益：`broker_equity_with_cashflow + reserve_remaining`。",
        "- 水下：`total_account_equity < 300000`。",
        "- 储备释放：只改变后续 broker sizing equity，不创造 PnL。",
        "- 逐品种归因：仅对关键路径锁定 Stage062 candidate AI 文件后重放，按 positions 的日净 PnL 聚合。",
        f"- 关键路径重放校验：`{validation_pass}/{validation_total}` 通过。",
        "",
        "## 结果摘要",
        "",
        _md_table(by_variant),
        "",
        "## 最长水下路径",
        "",
        _md_table(
            top[
                [
                    "rank",
                    "variant_label",
                    "requested_start_month",
                    "total_account_days_below_initial",
                    "trough_date",
                    "trough_shortfall_to_300k",
                    "recovery_after_trough",
                    "final_shortfall_to_300k",
                    "ends_below_initial",
                    "max_external_cashflow_used",
                ]
            ],
            max_rows=12,
        ),
        "",
        "## 决策",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 原因：{decision['decision_reason']}",
        "",
        "## 后续规划和 TODO",
        "",
        "- 如果继续，应先做“恢复段暴露治理”：区分储备释放后新增的好/坏开仓，而不是扫释放日期。",
        "- 不做基于单品种/单方向亏损的黑名单。",
        "- 修复或封装重放入口，确保未来逐品种归因默认绑定 Stage062 AI 文件，避免 AI 路径漂移。",
        "",
        "## 过拟合反思",
        "",
        f"- 运行前：{decision['overfit_reflection_before']}",
        f"- 运行后：{decision['overfit_reflection_after']}",
        "",
        "## 继续价值反思",
        "",
        f"- 运行前：{decision['continue_value_before']}",
        f"- 运行后：{decision['continue_value_after']}",
        "",
        "## 输出",
        "",
    ]
    for key, path in decision["outputs"].items():
        stage_lines.append(f"- {key}: `{path}`")
    stage_path.write_text("\n".join(stage_lines) + "\n", encoding="utf-8")
    return stage_path


def main() -> None:
    print("[stage067] loading Stage066 outputs", flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    summary, curves, cashflow = _load_inputs()
    metrics = _path_metrics(curves)
    monthly = _monthly_pnl(curves)
    phase = _phase_summary(curves, metrics)
    key_paths = _select_key_paths(metrics)
    cashflow_attr = _cashflow_attribution(cashflow)

    metrics.to_csv(PATH_METRICS_PATH, index=False, encoding="utf-8-sig")
    key_paths.to_csv(KEY_PATHS_PATH, index=False, encoding="utf-8-sig")
    monthly.to_csv(MONTHLY_PNL_PATH, index=False, encoding="utf-8-sig")
    phase.to_csv(PHASE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cashflow_attr.to_csv(CASHFLOW_ATTRIBUTION_PATH, index=False, encoding="utf-8-sig")

    product, validation = _rerun_key_paths(curves, key_paths)
    product.to_csv(PRODUCT_ATTRIBUTION_PATH, index=False, encoding="utf-8-sig")
    validation.to_csv(RERUN_VALIDATION_PATH, index=False, encoding="utf-8-sig")

    if not product.empty:
        product_top = (
            product.sort_values(["requested_start_month", "net_pnl"], ascending=[True, True])
            .groupby(["version", "requested_start_month"], group_keys=False)
            .head(8)
            .sort_values("net_pnl")
            .reset_index(drop=True)
        )
    else:
        product_top = pd.DataFrame()
    product_top.to_csv(PRODUCT_TOP_LOSERS_PATH, index=False, encoding="utf-8-sig")
    _plot(metrics, key_paths, product_top)
    stage_path = _write_records(metrics, key_paths, monthly, phase, product, product_top, validation, cashflow_attr)

    decision = json.loads(DECISION_PATH.read_text(encoding="utf-8"))
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), flush=True)
    print(f"stage_record: {stage_path}", flush=True)
    print(f"report: {REPORT_PATH}", flush=True)


if __name__ == "__main__":
    main()
