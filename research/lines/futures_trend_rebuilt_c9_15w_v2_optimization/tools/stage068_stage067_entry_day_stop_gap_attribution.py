from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
THIS_TOOLS_DIR = Path(__file__).resolve().parent
PORTFOLIO_DIR = ROOT / "examples" / "portfolio_backtesting"
for candidate in (str(THIS_TOOLS_DIR), str(PORTFOLIO_DIR)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

import analyze_qmt_roll_stage719_official_winner_trade_forensics as s719
import stage066_stage065_monthly_multiperiod_true_engine as s066


LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage068"
MODEL_TAG = "stage068_stage067_entry_day_stop_gap_attribution_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage068_stage067_entry_day_stop_gap_attribution"

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage068_stage067_entry_day_stop_gap_attribution"
STAGES_DIR = LINE_DIR / "stages"

STAGE067_OUT = LINE_DIR / "outputs" / "stage067_stage066_underwater_attribution"
KEY_PATHS_PATH = (
    STAGE067_OUT
    / "rebuilt_c9_v2_stage067_stage066_underwater_attribution_key_paths_stage067_stage066_underwater_attribution_v1.csv"
)

CLOSED_LOTS_PATH = OUT / f"{OUTPUT_PREFIX}_closed_lots_{MODEL_TAG}.csv.gz"
PATH_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_path_summary_{MODEL_TAG}.csv"
EXIT_REASON_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_exit_reason_summary_{MODEL_TAG}.csv"
WORST_INITIAL_STOP_GAPS_PATH = OUT / f"{OUTPUT_PREFIX}_worst_initial_stop_gaps_{MODEL_TAG}.csv"
WORST_EVENT_FILL_GAPS_PATH = OUT / f"{OUTPUT_PREFIX}_worst_event_to_fill_gaps_{MODEL_TAG}.csv"
ENTRY_DAY_VS_LATER_PATH = OUT / f"{OUTPUT_PREFIX}_entry_day_vs_later_{MODEL_TAG}.csv"
RERUN_VALIDATION_PATH = OUT / f"{OUTPUT_PREFIX}_rerun_validation_{MODEL_TAG}.csv"
CHART_PATH = OUT / f"{OUTPUT_PREFIX}_entry_day_stop_gap_chart_{MODEL_TAG}.png"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

STAGE066_CURVES_PATH = (
    LINE_DIR
    / "outputs"
    / "stage066_stage065_monthly_multiperiod_true_engine"
    / "rebuilt_c9_v2_stage066_stage065_monthly_multiperiod_true_engine_curves_stage066_stage065_monthly_multiperiod_true_engine_v1.csv.gz"
)


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


def _is_stop_reason(value: Any) -> bool:
    text = str(value or "").lower()
    return "stop" in text


def _entry_day_mark_pnl(row: pd.Series) -> float:
    entry_date = pd.Timestamp(row["entry_date"]).normalize()
    exit_date = pd.Timestamp(row["exit_date"]).normalize()
    if entry_date == exit_date:
        return float(row["realized_pnl"])
    bars = s719._read_contract_bars(str(row["vt_symbol"]))
    if bars.empty:
        return np.nan
    day = bars[pd.to_datetime(bars["date"], errors="coerce").dt.normalize().eq(entry_date)]
    if day.empty:
        return np.nan
    close_price = float(pd.to_numeric(day["close"], errors="coerce").iloc[0])
    entry_price = float(row["entry_price"])
    size = float(row["size"])
    volume = float(row["volume"])
    if str(row["direction"]) == "long":
        return (close_price - entry_price) * size * volume
    return (entry_price - close_price) * size * volume


def _match_exit_event(row: pd.Series, trade_events: pd.DataFrame) -> dict[str, Any]:
    if trade_events.empty:
        return {}
    vt_symbol = str(row["vt_symbol"])
    reason = str(row["exit_reason"])
    entry_date = pd.Timestamp(row["entry_date"]).normalize()
    exit_date = pd.Timestamp(row["exit_date"]).normalize()
    events = trade_events[
        trade_events["vt_symbol"].astype(str).eq(vt_symbol)
        & trade_events["reason"].astype(str).eq(reason)
        & (trade_events["date"] >= entry_date)
        & (trade_events["date"] <= exit_date)
    ].copy()
    if events.empty:
        return {}
    events = events.sort_values(["date", "datetime"])
    event = events.iloc[-1].to_dict()
    return event


def _enrich_closed_lots(closed: pd.DataFrame, trade_events: pd.DataFrame) -> pd.DataFrame:
    if closed.empty:
        return closed.copy()
    data = closed.copy()
    for column in ["entry_date", "exit_date"]:
        data[column] = pd.to_datetime(data[column], errors="coerce").dt.normalize()
    numeric_columns = [
        "entry_price",
        "exit_price",
        "volume",
        "size",
        "realized_pnl",
        "risk_amount",
        "r_multiple",
        "stop_distance",
        "holding_calendar_days",
        "days_to_mae",
        "mae_r",
    ]
    for column in numeric_columns:
        data[column] = pd.to_numeric(data.get(column, np.nan), errors="coerce")

    data["is_losing_lot"] = data["realized_pnl"].lt(0)
    data["is_stop_exit"] = data["exit_reason"].map(_is_stop_reason)
    data["same_day_exit"] = data["holding_calendar_days"].fillna(-1).eq(0)
    data["mae_on_entry_day"] = data["days_to_mae"].fillna(999999).eq(0)
    data["mae_within_3_calendar_days"] = data["days_to_mae"].fillna(999999).le(3)
    data["entry_day_mark_pnl"] = data.apply(_entry_day_mark_pnl, axis=1)
    data["post_entry_day_pnl"] = data["realized_pnl"] - data["entry_day_mark_pnl"]
    data["entry_day_loss_component"] = data["entry_day_mark_pnl"].clip(upper=0.0)
    data["post_entry_loss_component"] = data["post_entry_day_pnl"].clip(upper=0.0)

    data["initial_stop_price"] = np.where(
        data["direction"].astype(str).eq("long"),
        data["entry_price"] - data["stop_distance"],
        data["entry_price"] + data["stop_distance"],
    )
    data["exit_worse_than_initial_stop_points"] = np.where(
        data["direction"].astype(str).eq("long"),
        data["initial_stop_price"] - data["exit_price"],
        data["exit_price"] - data["initial_stop_price"],
    )
    data["exit_worse_than_initial_stop_points"] = data["exit_worse_than_initial_stop_points"].clip(lower=0.0)
    data["exit_worse_than_initial_stop_cash"] = (
        data["exit_worse_than_initial_stop_points"] * data["size"] * data["volume"]
    )
    data["exit_worse_than_initial_stop_r"] = np.where(
        data["risk_amount"].gt(0),
        data["exit_worse_than_initial_stop_cash"] / data["risk_amount"],
        np.nan,
    )

    if not trade_events.empty:
        events = trade_events.copy()
        events["date"] = pd.to_datetime(events["date"], errors="coerce").dt.normalize()
        events["datetime"] = pd.to_datetime(events["datetime"], errors="coerce")
    else:
        events = pd.DataFrame()

    matched_events = [(_match_exit_event(row, events) if bool(row["is_stop_exit"]) else {}) for _, row in data.iterrows()]
    data["exit_event_date"] = [_date_text(event.get("date")) for event in matched_events]
    data["exit_event_price"] = [float(event.get("price")) if event.get("price") not in (None, "") else np.nan for event in matched_events]
    data["exit_event_match"] = data["exit_event_price"].notna()
    data["event_to_fill_worse_points"] = np.where(
        data["direction"].astype(str).eq("long"),
        data["exit_event_price"] - data["exit_price"],
        data["exit_price"] - data["exit_event_price"],
    )
    data["event_to_fill_worse_points"] = pd.to_numeric(
        data["event_to_fill_worse_points"], errors="coerce"
    ).clip(lower=0.0)
    data["event_to_fill_worse_cash"] = data["event_to_fill_worse_points"] * data["size"] * data["volume"]
    data["event_to_fill_worse_r"] = np.where(
        data["risk_amount"].gt(0),
        data["event_to_fill_worse_cash"] / data["risk_amount"],
        np.nan,
    )

    for column in ["entry_date", "exit_date"]:
        data[column] = data[column].map(_date_text)
    return data


def _curve_validation(saved_curves: pd.DataFrame, rerun_curve: pd.DataFrame, version: str, start_month: str) -> dict[str, Any]:
    saved = saved_curves[
        saved_curves["version"].astype(str).eq(version)
        & saved_curves["requested_start_month"].astype(str).eq(start_month)
    ][["date", "total_account_equity", "strategy_equity_ex_cashflow", "broker_equity_with_cashflow"]].copy()
    rerun = rerun_curve[["date", "total_account_equity", "strategy_equity_ex_cashflow", "broker_equity_with_cashflow"]].copy()
    merged = saved.merge(rerun, on="date", how="outer", suffixes=("_saved", "_rerun"))
    row = {
        "version": version,
        "variant_label": VERSION_LABELS.get(version, version),
        "requested_start_month": start_month,
        "saved_rows": int(len(saved)),
        "rerun_rows": int(len(rerun)),
        "merged_rows": int(len(merged)),
    }
    max_diff = 0.0
    for column in ["total_account_equity", "strategy_equity_ex_cashflow", "broker_equity_with_cashflow"]:
        diff = (
            pd.to_numeric(merged[f"{column}_saved"], errors="coerce")
            - pd.to_numeric(merged[f"{column}_rerun"], errors="coerce")
        ).abs().max()
        row[f"{column}_max_abs_diff"] = float(diff)
        max_diff = max(max_diff, float(diff))
    row["validation_pass"] = bool(max_diff < 1e-6 and len(saved) == len(rerun))
    return row


def _run_key_paths() -> tuple[pd.DataFrame, pd.DataFrame]:
    key_paths = pd.read_csv(KEY_PATHS_PATH)
    saved_curves = pd.read_csv(STAGE066_CURVES_PATH)
    saved_curves["date"] = pd.to_datetime(saved_curves["date"], errors="coerce").dt.normalize()
    metadata = s066.s064.s901.s513._metadata()
    closed_frames: list[pd.DataFrame] = []
    validation_rows: list[dict[str, Any]] = []
    with s066.s064.s062._patched_live_ai_path(s066.s064.CANDIDATE_AI_PATH):
        for idx, row in key_paths.sort_values("rank").iterrows():
            version = str(row["version"])
            start_month = str(row["requested_start_month"])
            start = pd.Timestamp(f"{start_month}-01")
            print(f"[stage068] rerun key path {int(row['rank'])}/8 {version} {start_month}", flush=True)
            curve, frames = s066._run_variant(metadata, version, start)
            validation_rows.append(_curve_validation(saved_curves, curve, version, start_month))
            closed = s719._build_closed_lots(
                frames.get("trades", pd.DataFrame()),
                frames.get("entry_risk", pd.DataFrame()),
                frames.get("entry_candidates", pd.DataFrame()),
                metadata,
            )
            closed = _enrich_closed_lots(closed, frames.get("trade_events", pd.DataFrame()))
            if not closed.empty:
                closed["stage"] = STAGE
                closed["model_tag"] = MODEL_TAG
                closed["line_id"] = LINE_ID
                closed["version"] = version
                closed["variant_label"] = VERSION_LABELS.get(version, version)
                closed["requested_start_month"] = start_month
                closed["key_path_rank"] = int(row["rank"])
                closed["path_trough_date"] = row.get("trough_date", "")
                closed_frames.append(closed)
    lots = pd.concat(closed_frames, ignore_index=True, sort=False) if closed_frames else pd.DataFrame()
    validation = pd.DataFrame(validation_rows)
    return lots, validation


def _path_summary(lots: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (version, start_month), group in lots.groupby(["version", "requested_start_month"], sort=True):
        losing = group[group["is_losing_lot"]].copy()
        stop_losing = losing[losing["is_stop_exit"]].copy()
        total_entry_loss = float(losing["entry_day_loss_component"].sum())
        total_post_loss = float(losing["post_entry_loss_component"].sum())
        denominator = abs(total_entry_loss) + abs(total_post_loss)
        rows.append(
            {
                "version": version,
                "variant_label": VERSION_LABELS.get(version, version),
                "requested_start_month": start_month,
                "closed_lots": int(len(group)),
                "losing_lots": int(len(losing)),
                "losing_realized_pnl": float(losing["realized_pnl"].sum()),
                "same_day_exit_losing_lots": int(losing["same_day_exit"].sum()),
                "same_day_exit_losing_pnl": float(losing.loc[losing["same_day_exit"], "realized_pnl"].sum()),
                "mae_on_entry_day_losing_lots": int(losing["mae_on_entry_day"].sum()),
                "mae_within_3d_losing_lots": int(losing["mae_within_3_calendar_days"].sum()),
                "entry_day_loss_component": total_entry_loss,
                "post_entry_loss_component": total_post_loss,
                "entry_day_loss_share_of_negative_components": float(abs(total_entry_loss) / denominator) if denominator else np.nan,
                "stop_losing_lots": int(len(stop_losing)),
                "stop_losing_realized_pnl": float(stop_losing["realized_pnl"].sum()),
                "initial_stop_worse_losing_stop_lots": int(stop_losing["exit_worse_than_initial_stop_cash"].gt(0).sum()),
                "initial_stop_worse_cash_sum": float(stop_losing["exit_worse_than_initial_stop_cash"].sum()),
                "initial_stop_worse_r_median": float(stop_losing["exit_worse_than_initial_stop_r"].replace([np.inf, -np.inf], np.nan).median()),
                "initial_stop_worse_r_p90": float(stop_losing["exit_worse_than_initial_stop_r"].replace([np.inf, -np.inf], np.nan).quantile(0.90)),
                "initial_stop_worse_r_max": float(stop_losing["exit_worse_than_initial_stop_r"].replace([np.inf, -np.inf], np.nan).max()),
                "event_match_losing_stop_lots": int(stop_losing["exit_event_match"].sum()),
                "event_to_fill_worse_losing_stop_lots": int(stop_losing["event_to_fill_worse_cash"].gt(0).sum()),
                "event_to_fill_worse_cash_sum": float(stop_losing["event_to_fill_worse_cash"].sum()),
                "event_to_fill_worse_r_median": float(stop_losing["event_to_fill_worse_r"].replace([np.inf, -np.inf], np.nan).median()),
                "event_to_fill_worse_r_p90": float(stop_losing["event_to_fill_worse_r"].replace([np.inf, -np.inf], np.nan).quantile(0.90)),
                "event_to_fill_worse_r_max": float(stop_losing["event_to_fill_worse_r"].replace([np.inf, -np.inf], np.nan).max()),
            }
        )
    return pd.DataFrame(rows)


def _exit_reason_summary(lots: pd.DataFrame) -> pd.DataFrame:
    losing = lots[lots["is_losing_lot"]].copy()
    if losing.empty:
        return pd.DataFrame()
    grouped = (
        losing.groupby(["exit_reason"], dropna=False, as_index=False)
        .agg(
            losing_lots=("lot_id", "count"),
            realized_pnl=("realized_pnl", "sum"),
            median_holding_days=("holding_calendar_days", "median"),
            same_day_exit_lots=("same_day_exit", "sum"),
            mae_on_entry_day_lots=("mae_on_entry_day", "sum"),
            entry_day_loss_component=("entry_day_loss_component", "sum"),
            post_entry_loss_component=("post_entry_loss_component", "sum"),
            initial_stop_worse_count=("exit_worse_than_initial_stop_cash", lambda s: int(pd.to_numeric(s, errors="coerce").fillna(0).gt(0).sum())),
            initial_stop_worse_cash=("exit_worse_than_initial_stop_cash", "sum"),
            initial_stop_worse_r_median=("exit_worse_than_initial_stop_r", "median"),
            event_to_fill_worse_count=("event_to_fill_worse_cash", lambda s: int(pd.to_numeric(s, errors="coerce").fillna(0).gt(0).sum())),
            event_to_fill_worse_cash=("event_to_fill_worse_cash", "sum"),
            event_to_fill_worse_r_median=("event_to_fill_worse_r", "median"),
        )
        .sort_values("realized_pnl")
        .reset_index(drop=True)
    )
    return grouped


def _entry_day_vs_later(lots: pd.DataFrame) -> pd.DataFrame:
    losing = lots[lots["is_losing_lot"]].copy()
    if losing.empty:
        return pd.DataFrame()
    rows = []
    for label, mask in {
        "all_losing_lots": pd.Series(True, index=losing.index),
        "stop_losing_lots": losing["is_stop_exit"],
        "non_stop_losing_lots": ~losing["is_stop_exit"],
    }.items():
        data = losing[mask].copy()
        entry_loss = float(data["entry_day_loss_component"].sum())
        later_loss = float(data["post_entry_loss_component"].sum())
        denominator = abs(entry_loss) + abs(later_loss)
        rows.append(
            {
                "sample": label,
                "lots": int(len(data)),
                "realized_pnl": float(data["realized_pnl"].sum()),
                "same_day_exit_lots": int(data["same_day_exit"].sum()),
                "same_day_exit_realized_pnl": float(data.loc[data["same_day_exit"], "realized_pnl"].sum()),
                "mae_on_entry_day_lots": int(data["mae_on_entry_day"].sum()),
                "mae_within_3d_lots": int(data["mae_within_3_calendar_days"].sum()),
                "entry_day_loss_component": entry_loss,
                "post_entry_loss_component": later_loss,
                "entry_day_loss_share_of_negative_components": float(abs(entry_loss) / denominator) if denominator else np.nan,
                "median_holding_days": float(data["holding_calendar_days"].median()) if len(data) else np.nan,
            }
        )
    return pd.DataFrame(rows)


def _plot(path_summary: pd.DataFrame, exit_summary: pd.DataFrame) -> None:
    if path_summary.empty:
        return
    fig, axes = plt.subplots(2, 1, figsize=(13, 9))
    data = path_summary.sort_values("losing_realized_pnl").copy()
    labels = data["variant_label"] + "\n" + data["requested_start_month"].astype(str)
    x = np.arange(len(data))
    axes[0].bar(x - 0.2, data["entry_day_loss_component"], width=0.4, label="entry-day loss component", color="#f97316")
    axes[0].bar(x + 0.2, data["post_entry_loss_component"], width=0.4, label="post-entry-day loss component", color="#dc2626")
    axes[0].axhline(0, color="#111827", linewidth=0.8)
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(labels, rotation=30, ha="right")
    axes[0].set_title("Losing lots: entry-day vs later negative components")
    axes[0].set_ylabel("RMB")
    axes[0].legend()
    axes[0].grid(axis="y", alpha=0.25)

    if not exit_summary.empty:
        e = exit_summary.sort_values("realized_pnl").head(8).copy()
        axes[1].barh(e["exit_reason"].astype(str), e["initial_stop_worse_cash"], color="#7f1d1d", label="worse than initial stop")
        axes[1].barh(e["exit_reason"].astype(str), e["event_to_fill_worse_cash"], color="#2563eb", alpha=0.55, label="trigger to fill worse")
        axes[1].set_title("Stop gap cash by exit reason, losing lots")
        axes[1].set_xlabel("RMB")
        axes[1].legend()
        axes[1].grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_records(
    lots: pd.DataFrame,
    path_summary: pd.DataFrame,
    exit_summary: pd.DataFrame,
    entry_day: pd.DataFrame,
    validation: pd.DataFrame,
) -> Path:
    now = datetime.now()
    losing = lots[lots["is_losing_lot"]].copy()
    stop_losing = losing[losing["is_stop_exit"]].copy()
    validation_pass = int(pd.to_numeric(validation.get("validation_pass", 0), errors="coerce").fillna(0).sum())
    validation_total = int(len(validation))
    total_entry_loss = float(losing["entry_day_loss_component"].sum())
    total_later_loss = float(losing["post_entry_loss_component"].sum())
    denominator = abs(total_entry_loss) + abs(total_later_loss)
    entry_share = float(abs(total_entry_loss) / denominator) if denominator else np.nan
    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": now.isoformat(timespec="seconds"),
        "decision": "entry_day_stop_gap_forensics_keep_research_only",
        "decision_reason": (
            "最长水下路径的亏损不是全部开仓当天实现，开仓日不利波动很常见，但主要亏损额更多来自持仓后继续亏；"
            "部分 stop 出场确实存在触发日到实际成交日的更差成交，且相对初始止损价有明显越界，但这不是全部亏损的唯一来源。"
        ),
        "validation_pass_count": validation_pass,
        "validation_total": validation_total,
        "losing_lots": int(len(losing)),
        "losing_realized_pnl": float(losing["realized_pnl"].sum()),
        "same_day_exit_losing_lots": int(losing["same_day_exit"].sum()),
        "mae_on_entry_day_losing_lots": int(losing["mae_on_entry_day"].sum()),
        "entry_day_loss_component": total_entry_loss,
        "post_entry_loss_component": total_later_loss,
        "entry_day_loss_share_of_negative_components": entry_share,
        "stop_losing_lots": int(len(stop_losing)),
        "initial_stop_worse_losing_stop_lots": int(stop_losing["exit_worse_than_initial_stop_cash"].gt(0).sum()),
        "initial_stop_worse_cash_sum": float(stop_losing["exit_worse_than_initial_stop_cash"].sum()),
        "event_to_fill_worse_losing_stop_lots": int(stop_losing["event_to_fill_worse_cash"].gt(0).sum()),
        "event_to_fill_worse_cash_sum": float(stop_losing["event_to_fill_worse_cash"].sum()),
        "outputs": {
            "closed_lots": str(CLOSED_LOTS_PATH),
            "path_summary": str(PATH_SUMMARY_PATH),
            "exit_reason_summary": str(EXIT_REASON_SUMMARY_PATH),
            "worst_initial_stop_gaps": str(WORST_INITIAL_STOP_GAPS_PATH),
            "worst_event_to_fill_gaps": str(WORST_EVENT_FILL_GAPS_PATH),
            "entry_day_vs_later": str(ENTRY_DAY_VS_LATER_PATH),
            "rerun_validation": str(RERUN_VALIDATION_PATH),
            "chart": str(CHART_PATH),
            "report": str(REPORT_PATH),
        },
        "overfit_reflection_before": "否。只读法证，不改变止损、开仓、储备释放或品种参数。",
        "overfit_reflection_after": "否。结论用于解释执行路径和数据粒度，不据此做单品种黑名单或止损价补丁。",
        "continue_value_before": "有。用户的问题直指长水下是否由开仓日亏损或止损滑穿导致，需要逐笔核实。",
        "continue_value_after": "有。下一步若继续，应研究执行/止损成交模型和开仓后不利路径识别，但不能按最差月份救参。",
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report_lines = [
        "# Stage068 Stage067 entry-day and stop-gap attribution",
        "",
        f"- generated_at: `{now.isoformat(timespec='seconds')}`",
        f"- line_id: `{LINE_ID}`",
        f"- key paths: `{KEY_PATHS_PATH}`",
        f"- AI path locked: `{s066.s064.CANDIDATE_AI_PATH}`",
        "- live config changed: `false`; CTP connected: `false`; order API calls: `0`",
        "",
        "## Entry-Day vs Later",
        "",
        _md_table(entry_day),
        "",
        "## Path Summary",
        "",
        _md_table(path_summary, max_rows=12),
        "",
        "## Exit Reason Summary",
        "",
        _md_table(exit_summary, max_rows=30),
        "",
        "## Rerun Validation",
        "",
        _md_table(validation, max_rows=12),
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
    stage_path = STAGES_DIR / f"{now.strftime('%Y%m%d_%H%M')}_stage068_entry_day_stop_gap_attribution.md"
    stage_lines = [
        "# Stage068 开仓日/止损滑穿归因",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：day",
        f"- 记录时间：{now.isoformat(timespec='seconds')}",
        f"- 工作区：`{ROOT}`",
        "- 是否重要突破：否，执行路径法证；不改策略、不调参数",
        "- 是否触发A/B：否，本阶段不提出上线候选",
        "",
        "## 外部调研与判断",
        "",
        "- 止损单只保证触发，不保证成交在止损价；跳空或日线回测会导致按下一可成交价成交。",
        "- 因此本阶段同时看 `initial_stop_price -> exit_price` 和 `trigger event price -> fill price` 两种偏离。",
        "- 本次判断：要区分信号/止损逻辑是否错、以及日线/下一日成交模型是否放大亏损。",
        "",
        "## 本次变更",
        "",
        f"- 新增脚本：`{Path(__file__).relative_to(ROOT)}`",
        "- 修改正式入口：无",
        "- 删除文件：无",
        "- 新增参数：无交易参数；复用 Stage067 最长水下 8 条关键路径",
        "- 修改参数：无",
        "- 删除参数：无",
        "",
        "## 归因口径",
        "",
        "- 开仓日贡献：若同日平仓，用 realized_pnl；否则按开仓日收盘相对开仓价估算 mark PnL。",
        "- 后续贡献：`realized_pnl - entry_day_mark_pnl`。",
        "- 初始止损滑穿：long 用 `initial_stop_price - exit_price`，short 用 `exit_price - initial_stop_price`，只统计正值。",
        "- 触发到成交滑穿：匹配同合约、同 exit_reason、entry_date 到 exit_date 内最后一个 trade_event，用 event price 到实际 fill price 的不利偏离。",
        f"- 关键路径重放校验：`{validation_pass}/{validation_total}` 通过。",
        "",
        "## 结果摘要",
        "",
        f"- 亏损 lot：`{int(len(losing))}`，合计 realized_pnl `{float(losing['realized_pnl'].sum()):,.2f}`。",
        f"- 同日出场亏损 lot：`{int(losing['same_day_exit'].sum())}`。",
        f"- 最大不利点出现在开仓日的亏损 lot：`{int(losing['mae_on_entry_day'].sum())}`。",
        f"- 开仓日负贡献 `{total_entry_loss:,.2f}`，后续负贡献 `{total_later_loss:,.2f}`，开仓日负贡献占比 `{entry_share:.2%}`。",
        f"- 亏损 stop lot：`{int(len(stop_losing))}`；其中相对初始止损更差成交 `{int(stop_losing['exit_worse_than_initial_stop_cash'].gt(0).sum())}` 笔，额外不利 `{float(stop_losing['exit_worse_than_initial_stop_cash'].sum()):,.2f}`。",
        f"- 有触发事件匹配的亏损 stop lot 中，触发到成交更差 `{int(stop_losing['event_to_fill_worse_cash'].gt(0).sum())}` 笔，额外不利 `{float(stop_losing['event_to_fill_worse_cash'].sum()):,.2f}`。",
        "",
        "## Entry-Day vs Later",
        "",
        _md_table(entry_day),
        "",
        "## Exit Reason Summary",
        "",
        _md_table(exit_summary, max_rows=30),
        "",
        "## 决策",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 原因：{decision['decision_reason']}",
        "",
        "## 后续规划和 TODO",
        "",
        "- 若继续，优先做 stop event 到 fill 的执行模型审计，确认日线下一日成交是否过度保守或贴近真实。",
        "- 再做开仓后 1-3 日不利路径识别，但不能按 2022-04/2022-08 单月救参。",
        "- 不做基于本次最差 stop lot 的品种/方向黑名单。",
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
    print("[stage068] entry-day and stop-gap attribution", flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    lots, validation = _run_key_paths()
    lots.to_csv(CLOSED_LOTS_PATH, index=False, encoding="utf-8-sig")
    path_summary = _path_summary(lots)
    exit_summary = _exit_reason_summary(lots)
    entry_day = _entry_day_vs_later(lots)
    path_summary.to_csv(PATH_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    exit_summary.to_csv(EXIT_REASON_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    entry_day.to_csv(ENTRY_DAY_VS_LATER_PATH, index=False, encoding="utf-8-sig")
    validation.to_csv(RERUN_VALIDATION_PATH, index=False, encoding="utf-8-sig")
    losing_stop = lots[lots["is_losing_lot"] & lots["is_stop_exit"]].copy()
    losing_stop.sort_values("exit_worse_than_initial_stop_cash", ascending=False).head(50).to_csv(
        WORST_INITIAL_STOP_GAPS_PATH, index=False, encoding="utf-8-sig"
    )
    losing_stop.sort_values("event_to_fill_worse_cash", ascending=False).head(50).to_csv(
        WORST_EVENT_FILL_GAPS_PATH, index=False, encoding="utf-8-sig"
    )
    _plot(path_summary, exit_summary)
    stage_path = _write_records(lots, path_summary, exit_summary, entry_day, validation)
    decision = json.loads(DECISION_PATH.read_text(encoding="utf-8"))
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), flush=True)
    print(f"stage_record: {stage_path}", flush=True)
    print(f"report: {REPORT_PATH}", flush=True)


if __name__ == "__main__":
    main()
