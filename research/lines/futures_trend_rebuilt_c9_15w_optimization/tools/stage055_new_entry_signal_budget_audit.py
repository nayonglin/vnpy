from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
TOOLS_DIR = Path(__file__).resolve().parent
PORTFOLIO_DIR = PROJECT_DIR / "examples" / "portfolio_backtesting"
for path in (str(TOOLS_DIR), str(PORTFOLIO_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

import stage013_account_state_pilot_gate_engine as s013
import stage038_candidate_pit_feature_matrix_audit as s038
import stage041_selected_daily_cold_start_probe as s041

from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage055"
MODEL_TAG = "stage055_new_entry_signal_budget_audit_v1"
OUTPUT_PREFIX = "rebuilt_c9_stage055_new_entry_signal_budget_audit"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage055_new_entry_signal_budget_audit"
STAGES_DIR = LINE_DIR / "stages"

STAGE054_OUTPUT_DIR = LINE_DIR / "outputs" / "stage054_daily_left_tail_path_attribution"
STAGE054_PREFIX = "rebuilt_c9_stage054_daily_left_tail_path_attribution"
STAGE054_TAG = "stage054_daily_left_tail_path_attribution_v1"
STAGE054_SELECTED_WINDOWS_PATH = STAGE054_OUTPUT_DIR / f"{STAGE054_PREFIX}_selected_windows_{STAGE054_TAG}.csv"
STAGE054_CURVE_ATTRIBUTION_PATH = STAGE054_OUTPUT_DIR / f"{STAGE054_PREFIX}_curve_window_attribution_{STAGE054_TAG}.csv"

SELECTED_WINDOWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_unique_windows_{MODEL_TAG}.csv"
TRADES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{MODEL_TAG}.csv.gz"
ENTRY_RISK_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_{MODEL_TAG}.csv.gz"
ENTRY_CANDIDATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidates_{MODEL_TAG}.csv.gz"
CLOSED_LOTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_closed_lots_{MODEL_TAG}.csv.gz"
FEATURE_MATRIX_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_matrix_{MODEL_TAG}.csv"
WINDOW_ENTRIES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stage054_window_entries_{MODEL_TAG}.csv"
CONDITION_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_condition_pnl_summary_{MODEL_TAG}.csv"
SOURCE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_summary_{MODEL_TAG}.csv"
VALIDATION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_validation_{MODEL_TAG}.csv"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_condition_chart_{MODEL_TAG}.png"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

MIN_CONDITION_COUNT = 8
MIN_CONDITION_SOURCE_COUNT = 2


def _json_safe(value: Any) -> Any:
    return s041._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s041._md_table(frame, max_rows=max_rows)


def _date_key(value: Any) -> str:
    if pd.isna(value):
        return ""
    return pd.Timestamp(value).date().isoformat()


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


def _num(frame: pd.DataFrame, column: str, default: float = np.nan) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce")


def _to_bool(series: pd.Series | Any, index: pd.Index | None = None) -> pd.Series:
    if isinstance(series, pd.Series):
        values = series.copy()
    else:
        values = pd.Series(series, index=index)
    if values.empty:
        return values.astype(bool)
    if pd.api.types.is_bool_dtype(values):
        return values.fillna(False)
    if pd.api.types.is_numeric_dtype(values):
        return pd.to_numeric(values, errors="coerce").fillna(0).ne(0)
    text = values.fillna("").astype(str).str.strip().str.lower()
    return text.isin({"1", "1.0", "true", "yes", "y", "pass", "passed", "opened"})


def unique_stage054_windows(windows: pd.DataFrame) -> pd.DataFrame:
    frame = windows.copy()
    frame["requested_start"] = frame["requested_start"].astype(str)
    frame["window_start_date"] = pd.to_datetime(frame["window_start_date"], errors="coerce").dt.normalize()
    frame["window_end_date"] = pd.to_datetime(frame["window_end_date"], errors="coerce").dt.normalize()
    frame["window_return_pct"] = pd.to_numeric(frame.get("window_return_pct"), errors="coerce")
    frame = frame.dropna(subset=["requested_start", "window_start_date", "window_end_date"])
    if frame.empty:
        return pd.DataFrame(
            columns=[
                "requested_start",
                "window_start_date",
                "window_end_date",
                "stage054_variant_count",
                "stage054_variants",
                "stage054_min_window_return_pct",
            ]
        )
    grouped = (
        frame.groupby(["requested_start", "window_start_date", "window_end_date"], dropna=False)
        .agg(
            stage054_variant_count=("variant", "nunique"),
            stage054_variants=("variant", lambda s: ",".join(sorted(set(map(str, s))))),
            stage054_min_window_return_pct=("window_return_pct", "min"),
        )
        .reset_index()
        .sort_values(["stage054_min_window_return_pct", "requested_start"])
        .reset_index(drop=True)
    )
    grouped.insert(0, "stage055_window_rank", np.arange(1, len(grouped) + 1))
    return grouped


def attach_stage054_windows_to_entries(entries: pd.DataFrame, windows: pd.DataFrame) -> pd.DataFrame:
    result = entries.copy()
    if result.empty:
        result["inside_stage054_window"] = False
        return result
    result["requested_start_month"] = result["requested_start_month"].astype(str)
    result["entry_date"] = pd.to_datetime(result["entry_date"], errors="coerce").dt.normalize()
    result["inside_stage054_window"] = False
    result["stage054_window_count"] = 0
    result["stage054_window_rank_min"] = np.nan
    result["stage054_window_start_min"] = pd.NaT
    result["stage054_window_end_max"] = pd.NaT
    if windows.empty:
        return result

    win = windows.copy()
    win["requested_start"] = win["requested_start"].astype(str)
    win["window_start_date"] = pd.to_datetime(win["window_start_date"], errors="coerce").dt.normalize()
    win["window_end_date"] = pd.to_datetime(win["window_end_date"], errors="coerce").dt.normalize()
    for row in win.itertuples(index=False):
        source = str(row.requested_start)
        start = pd.Timestamp(row.window_start_date).normalize()
        end = pd.Timestamp(row.window_end_date).normalize()
        mask = result["requested_start_month"].eq(source) & result["entry_date"].gt(start) & result["entry_date"].le(end)
        if not mask.any():
            continue
        result.loc[mask, "inside_stage054_window"] = True
        result.loc[mask, "stage054_window_count"] = result.loc[mask, "stage054_window_count"].astype(int) + 1
        current_rank = pd.to_numeric(result.loc[mask, "stage054_window_rank_min"], errors="coerce")
        rank = float(getattr(row, "stage055_window_rank", np.nan))
        result.loc[mask, "stage054_window_rank_min"] = np.where(current_rank.isna(), rank, np.minimum(current_rank, rank))
        current_start = pd.to_datetime(result.loc[mask, "stage054_window_start_min"], errors="coerce")
        current_end = pd.to_datetime(result.loc[mask, "stage054_window_end_max"], errors="coerce")
        result.loc[mask, "stage054_window_start_min"] = current_start.fillna(start).mask(
            current_start.notna() & (current_start > start), start
        )
        result.loc[mask, "stage054_window_end_max"] = current_end.fillna(end).mask(
            current_end.notna() & (current_end < end), end
        )
    return result


def _condition_masks(entries: pd.DataFrame) -> list[tuple[str, str, pd.Series, bool]]:
    index = entries.index
    ai_rank = _num(entries, "ai_rank")
    selected_volume = _num(entries, "selected_volume")
    loss_streak = _num(entries, "loss_streak", 0.0).fillna(0.0)
    drawdown = _num(entries, "drawdown_abs_pct")
    active_positions = _num(entries, "active_positions_before")
    full_market_ai_top8 = _to_bool(entries.get("full_market_ai_top8", False), index=index)
    full_market_consensus = _to_bool(entries.get("full_market_consensus_top8", False), index=index)
    oi_confirmed = _to_bool(entries.get("oi_confirmed", False), index=index)
    account_clean = _to_bool(entries.get("account_clean", False), index=index)
    account_injured = _to_bool(entries.get("account_injured", False), index=index)
    ai_rank_1_6 = _to_bool(entries.get("ai_rank_1_6", False), index=index)
    ai_rank_1_9 = _to_bool(entries.get("ai_rank_1_9", False), index=index)
    return [
        ("all_stage054_window_entries", "全部 Stage054 窗口后新开 flat_entry", pd.Series(True, index=index), False),
        ("ai_rank_1_6", "Stage182 AI rank 1-6", ai_rank_1_6, True),
        ("ai_rank_1_9", "Stage182 AI rank 1-9", ai_rank_1_9, True),
        ("ai_rank_gt9_or_missing", "AI rank >9 或缺失", ai_rank.gt(9) | ai_rank.isna(), True),
        ("full_market_ai_top8", "full-market AI top8", full_market_ai_top8, True),
        ("full_market_consensus_top8", "full-market AI/simple 共识 top8", full_market_consensus, True),
        ("oi_confirmed", "OI 与价格方向确认", oi_confirmed, True),
        ("account_clean", "入场前账户干净", account_clean, True),
        ("account_injured", "入场前账户受伤", account_injured, True),
        ("selected_volume_gt1", "释放到 1 手以上", selected_volume.gt(1), True),
        ("selected_volume_ge5", "释放到 5 手及以上", selected_volume.ge(5), True),
        ("loss_streak_ge2", "loss_streak >=2", loss_streak.ge(2), True),
        ("loss_streak_ge3", "loss_streak >=3", loss_streak.ge(3), True),
        ("drawdown_abs_ge10", "入场前回撤绝对值 >=10%", drawdown.ge(10), True),
        ("drawdown_abs_ge20", "入场前回撤绝对值 >=20%", drawdown.ge(20), True),
        ("active_positions_ge3", "入场前已有活跃持仓 >=3", active_positions.ge(3), True),
        (
            "normal_release_not_full_market_ai_top8",
            "释放到 1 手以上且不是 full-market AI top8",
            selected_volume.gt(1) & ~full_market_ai_top8,
            True,
        ),
        (
            "normal_release_not_ai_rank_1_6",
            "释放到 1 手以上且不是 Stage182 AI rank 1-6",
            selected_volume.gt(1) & ~ai_rank_1_6,
            True,
        ),
        (
            "ai_rank_1_6_and_account_clean",
            "Stage182 AI rank 1-6 且账户干净",
            ai_rank_1_6 & account_clean,
            True,
        ),
        (
            "ai_rank_1_6_and_full_market_ai_top8",
            "Stage182 AI rank 1-6 且 full-market AI top8",
            ai_rank_1_6 & full_market_ai_top8,
            True,
        ),
    ]


def summarize_condition_pnl(entries: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if entries.empty:
        return pd.DataFrame()
    pnl_all = _num(entries, "realized_pnl", 0.0).fillna(0.0)
    total_loss_abs = float(abs(pnl_all[pnl_all < 0].sum()))
    for name, description, mask, candidate_eligible in _condition_masks(entries):
        mask = mask.reindex(entries.index).fillna(False).astype(bool)
        subset = entries.loc[mask].copy()
        pnl = _num(subset, "realized_pnl", 0.0).fillna(0.0)
        negative = pnl[pnl < 0]
        loss_abs = float(abs(negative.sum()))
        rows.append(
            {
                "condition": name,
                "description": description,
                "candidate_eligible": bool(candidate_eligible),
                "count": int(len(subset)),
                "source_count": int(subset["requested_start_month"].nunique()) if "requested_start_month" in subset.columns else 0,
                "date_count": int(pd.to_datetime(subset.get("entry_date"), errors="coerce").nunique()) if len(subset) else 0,
                "product_count": int(subset["product_vt_symbol"].nunique()) if "product_vt_symbol" in subset.columns else 0,
                "total_pnl": float(pnl.sum()),
                "mean_pnl": float(pnl.mean()) if len(subset) else 0.0,
                "median_pnl": float(pnl.median()) if len(subset) else 0.0,
                "loss_rate_pct": float((pnl < 0).mean() * 100.0) if len(subset) else 0.0,
                "loss_abs": loss_abs,
                "loss_abs_share_pct": loss_abs / total_loss_abs * 100.0 if total_loss_abs else 0.0,
                "selected_volume_sum": float(_num(subset, "selected_volume", 0.0).fillna(0.0).sum()) if len(subset) else 0.0,
                "selected_volume_gt1_rate_pct": float((_num(subset, "selected_volume", 0.0).fillna(0.0) > 1).mean() * 100.0)
                if len(subset)
                else 0.0,
            }
        )
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    result["negative_contributor"] = (
        result["candidate_eligible"].astype(bool)
        & result["count"].ge(MIN_CONDITION_COUNT)
        & result["source_count"].ge(MIN_CONDITION_SOURCE_COUNT)
        & result["total_pnl"].lt(0)
    )
    return result.sort_values(["negative_contributor", "total_pnl", "count"], ascending=[False, True, False])


def _frame_with_run_columns(frame: pd.DataFrame, requested_start: str, requested_end: pd.Timestamp) -> pd.DataFrame:
    result = frame.copy()
    result["stage"] = STAGE
    result["model_tag"] = MODEL_TAG
    result["line_id"] = LINE_ID
    result["official_live_version"] = OFFICIAL_LIVE_VERSION
    result["official_live_alias"] = OFFICIAL_LIVE_ALIAS
    result["requested_start"] = requested_start
    result["requested_start_month"] = requested_start
    result["requested_end"] = _date_key(requested_end)
    return result


def _run_sources(windows: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    metadata = s013.s901.s513._metadata()
    requested_end_by_start = windows.groupby("requested_start", dropna=False)["window_end_date"].max().sort_index().to_dict()
    trade_frames: list[pd.DataFrame] = []
    entry_risk_frames: list[pd.DataFrame] = []
    candidate_frames: list[pd.DataFrame] = []
    closed_frames: list[pd.DataFrame] = []
    for index, (requested_start, requested_end) in enumerate(requested_end_by_start.items(), start=1):
        start = pd.Timestamp(requested_start).normalize()
        end = pd.Timestamp(requested_end).normalize()
        print(
            f"[stage055] rerun Stage013 source {index}/{len(requested_end_by_start)} "
            f"start={_date_key(start)} end={_date_key(end)}",
            flush=True,
        )
        _combined, frames, _spec = s013._run_live_stage013(metadata, start, end)
        trades = _frame_with_run_columns(frames.get("trades", pd.DataFrame()), _date_key(start), end)
        entry_risk = _frame_with_run_columns(frames.get("entry_risk", pd.DataFrame()), _date_key(start), end)
        candidates = _frame_with_run_columns(frames.get("entry_candidates", pd.DataFrame()), _date_key(start), end)
        closed = s041._closed_lots_from_frames(frames, metadata, start)
        closed = _frame_with_run_columns(closed, _date_key(start), end)
        if not trades.empty:
            trade_frames.append(trades)
        if not entry_risk.empty:
            entry_risk_frames.append(entry_risk)
        if not candidates.empty:
            candidate_frames.append(candidates)
        if not closed.empty:
            closed_frames.append(closed)
    return (
        pd.concat(trade_frames, ignore_index=True, sort=False) if trade_frames else pd.DataFrame(),
        pd.concat(entry_risk_frames, ignore_index=True, sort=False) if entry_risk_frames else pd.DataFrame(),
        pd.concat(candidate_frames, ignore_index=True, sort=False) if candidate_frames else pd.DataFrame(),
        pd.concat(closed_frames, ignore_index=True, sort=False) if closed_frames else pd.DataFrame(),
    )


def _build_feature_matrix(closed_lots: pd.DataFrame, entry_candidates: pd.DataFrame) -> pd.DataFrame:
    monthly = _read_csv(s038.FULL_MARKET_PREDICTIONS_PATH) if s038.FULL_MARKET_PREDICTIONS_PATH.exists() else pd.DataFrame()
    return s038.build_feature_matrix(closed_lots, monthly, entry_candidates=entry_candidates)


def _source_summary(entries: pd.DataFrame) -> pd.DataFrame:
    if entries.empty:
        return pd.DataFrame()
    rows = []
    for source, group in entries.groupby("requested_start_month", dropna=False):
        pnl = _num(group, "realized_pnl", 0.0).fillna(0.0)
        rows.append(
            {
                "requested_start_month": source,
                "entry_count": int(len(group)),
                "product_count": int(group["product_vt_symbol"].nunique()) if "product_vt_symbol" in group.columns else 0,
                "total_pnl": float(pnl.sum()),
                "loss_abs": float(abs(pnl[pnl < 0].sum())),
                "loss_rate_pct": float((pnl < 0).mean() * 100.0) if len(group) else 0.0,
                "selected_volume_sum": float(_num(group, "selected_volume", 0.0).fillna(0.0).sum()),
            }
        )
    return pd.DataFrame(rows).sort_values("total_pnl")


def _validation(
    feature_matrix: pd.DataFrame,
    window_entries: pd.DataFrame,
    stage054_curve_attr: pd.DataFrame,
) -> pd.DataFrame:
    position_net = float(pd.to_numeric(stage054_curve_attr.get("position_net_pnl"), errors="coerce").fillna(0.0).sum())
    entry_realized = float(_num(window_entries, "realized_pnl", 0.0).fillna(0.0).sum())
    rows = [
        {
            "check_type": "feature_matrix_rows",
            "actual": float(len(feature_matrix)),
            "reference": np.nan,
            "abs_diff": np.nan,
            "note": "Stage055 rerun closed flat-entry open-trade feature matrix rows",
        },
        {
            "check_type": "stage054_window_entry_rows",
            "actual": float(len(window_entries)),
            "reference": np.nan,
            "abs_diff": np.nan,
            "note": "Entries with entry_date strictly after Stage054 window start and <= window end",
        },
        {
            "check_type": "stage054_position_net_vs_window_entry_realized",
            "actual": entry_realized,
            "reference": position_net,
            "abs_diff": abs(entry_realized - position_net),
            "note": "This is expected to differ because positions include daily holding PnL and open exposure at window end",
        },
    ]
    return pd.DataFrame(rows)


def _plot(condition_summary: pd.DataFrame) -> None:
    if condition_summary.empty:
        return
    plot = condition_summary[condition_summary["count"].gt(0)].copy()
    if plot.empty:
        return
    plot = plot.sort_values("total_pnl").head(14).sort_values("total_pnl")
    plt.figure(figsize=(13, 8))
    colors = np.where(plot["negative_contributor"].astype(bool), "#c2410c", "#2563eb")
    plt.barh(plot["condition"], plot["total_pnl"], color=colors)
    plt.axvline(0.0, color="#111827", linewidth=1)
    plt.xlabel("Realized PnL inside Stage054 windows")
    plt.ylabel("Entry-visible condition")
    plt.title("Stage055 new-entry signal budget audit")
    plt.tight_layout()
    plt.savefig(CHART_PATH, dpi=180)
    plt.close()


def _decision(
    unique_windows: pd.DataFrame,
    feature_matrix: pd.DataFrame,
    window_entries: pd.DataFrame,
    condition_summary: pd.DataFrame,
    validation: pd.DataFrame,
) -> dict[str, Any]:
    negative = condition_summary[condition_summary.get("negative_contributor", False).astype(bool)].copy()
    if not negative.empty:
        decision = "stage055_has_new_entry_negative_conditions_need_true_budget_engine"
        continue_after = (
            "有。Stage054 窗口后的新开仓里存在入场前可见的负贡献条件，但这仍是 closed-lot 归因，下一步必须写真引擎验证预算规则。"
        )
    else:
        decision = "stage055_no_stable_new_entry_condition_keep_search"
        continue_after = "有但需换角度。本阶段没有找到足够稳定的入场前条件，不能写预算规则。"
    pnl = _num(window_entries, "realized_pnl", 0.0).fillna(0.0)
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "decision": decision,
        "audit_type": "read_only_new_entry_signal_budget_audit_for_stage054_left_tail_windows",
        "unique_window_count": int(len(unique_windows)),
        "feature_matrix_rows": int(len(feature_matrix)),
        "stage054_window_entry_count": int(len(window_entries)),
        "stage054_window_entry_total_realized_pnl": float(pnl.sum()),
        "stage054_window_entry_loss_abs": float(abs(pnl[pnl < 0].sum())),
        "negative_condition_count": int(len(negative)),
        "top_negative_conditions": negative.head(10)["condition"].tolist() if not negative.empty else [],
        "strategy_changed": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "external_research_judgment": (
            "趋势跟踪公开资料和 pysystemtrade/PyTrendFollow 等实现都更支持将信号、目标风险和仓位预算分离。"
            "Stage055 因此只审计 Stage054 左尾中新开仓的入场前可见条件，不按亏损品种、方向或日期写规则。参考："
            "https://github.com/pst-group/pysystemtrade ; https://github.com/chrism2671/PyTrendFollow ; "
            "https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID3231836_code1554519.pdf?abstractid=2063848&mirid=1"
        ),
        "overfit_reflection_before": (
            "否。Stage055 固定使用 Stage054 已选窗口和日级起点，只做入场前可见条件归因，不新增交易参数。"
        ),
        "overfit_reflection_after": (
            "否。本阶段没有按结果修改策略；如果下一步按单品种、单方向或单日期写预算规则，就是过拟合。"
        ),
        "continue_value_before": "有。Stage054 已证明左尾来自窗口后新增风险暴露，必须拆入场前是否有可见质量差异。",
        "continue_value_after": continue_after,
        "validation": validation.to_dict("records"),
        "outputs": {
            "unique_windows": str(SELECTED_WINDOWS_PATH),
            "trades": str(TRADES_PATH),
            "entry_risk": str(ENTRY_RISK_PATH),
            "entry_candidates": str(ENTRY_CANDIDATES_PATH),
            "closed_lots": str(CLOSED_LOTS_PATH),
            "feature_matrix": str(FEATURE_MATRIX_PATH),
            "window_entries": str(WINDOW_ENTRIES_PATH),
            "condition_summary": str(CONDITION_SUMMARY_PATH),
            "source_summary": str(SOURCE_SUMMARY_PATH),
            "validation": str(VALIDATION_PATH),
            "chart": str(CHART_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }


def _write_report(
    decision: dict[str, Any],
    unique_windows: pd.DataFrame,
    condition_summary: pd.DataFrame,
    source_summary: pd.DataFrame,
    validation: pd.DataFrame,
) -> None:
    lines = [
        "# Stage055 - 新开仓信号预算只读审计",
        "",
        f"- 生成时间：`{decision['generated_at']}`",
        f"- 决策：`{decision['decision']}`",
        "- 阶段性质：只读归因；围绕 Stage054 最差窗口后的新开 flat_entry，重跑日级起点并建立 PIT feature matrix；不改策略、不连接 CTP、不调用下单。",
        f"- 唯一窗口数：`{decision['unique_window_count']}`",
        f"- feature matrix 行数：`{decision['feature_matrix_rows']}`",
        f"- Stage054 窗口内 entry 数：`{decision['stage054_window_entry_count']}`",
        f"- 窗口 entry realized PnL：`{decision['stage054_window_entry_total_realized_pnl']:,.2f}`",
        f"- 窗口 entry loss_abs：`{decision['stage054_window_entry_loss_abs']:,.2f}`",
        "",
        "## 调研和判断结论",
        "",
        f"- {decision['external_research_judgment']}",
        "",
        "## 唯一窗口",
        "",
        _md_table(unique_windows, max_rows=30),
        "",
        "## 条件 PnL 汇总",
        "",
        _md_table(condition_summary, max_rows=40),
        "",
        "## source 汇总",
        "",
        _md_table(source_summary, max_rows=30),
        "",
        "## 校验",
        "",
        _md_table(validation, max_rows=20),
        "",
        "## 输出",
        "",
        f"- unique_windows：`{SELECTED_WINDOWS_PATH}`",
        f"- feature_matrix：`{FEATURE_MATRIX_PATH}`",
        f"- window_entries：`{WINDOW_ENTRIES_PATH}`",
        f"- condition_summary：`{CONDITION_SUMMARY_PATH}`",
        f"- chart：`{CHART_PATH}`",
        f"- decision：`{DECISION_PATH}`",
        "",
        "## 反思",
        "",
        f"- 运行前过拟合反思：{decision['overfit_reflection_before']}",
        f"- 运行后过拟合反思：{decision['overfit_reflection_after']}",
        f"- 运行前继续价值反思：{decision['continue_value_before']}",
        f"- 运行后继续价值反思：{decision['continue_value_after']}",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_stage_record(decision: dict[str, Any], condition_summary: pd.DataFrame, validation: pd.DataFrame) -> Path:
    timestamp = datetime.now()
    path = STAGES_DIR / f"{timestamp:%Y%m%d_%H%M}_stage055_new_entry_signal_budget_audit.md"
    lines = [
        "# Stage055 - 新开仓信号预算只读审计",
        "",
        f"- 记录时间：`{timestamp.isoformat(timespec='minutes')}`",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        "- 是否重要突破版本：`否`",
        f"- 决策：`{decision['decision']}`",
        "",
        "## 本次版本变更",
        "",
        f"- 新增脚本：`research/lines/{LINE_ID}/tools/stage055_new_entry_signal_budget_audit.py`",
        "- 新增测试：`tests/test_rebuilt_c9_stage055_new_entry_signal_budget_audit.py`",
        "- 新增参数：`MIN_CONDITION_COUNT=8`、`MIN_CONDITION_SOURCE_COUNT=2`，只用于只读标记负贡献条件。",
        "- 修改参数：无；Stage013/Stage054/官方 C9 配置均未改。",
        "- 删除参数：无。",
        "- 新增回测结果：Stage054 最差窗口中新开 flat_entry 的 closed-lot PIT feature matrix 和条件 PnL 归因。",
        "- 本阶段不连接 CTP，不调用订单 API，不触发 A/B。",
        "",
        "## 调研和判断结论",
        "",
        f"- {decision['external_research_judgment']}",
        "",
        "## 结果",
        "",
        f"- 唯一窗口数：`{decision['unique_window_count']}`。",
        f"- feature matrix 行数：`{decision['feature_matrix_rows']}`。",
        f"- Stage054 窗口内 entry 数：`{decision['stage054_window_entry_count']}`。",
        f"- 窗口 entry realized PnL：`{decision['stage054_window_entry_total_realized_pnl']:,.2f}`。",
        f"- 窗口 entry loss_abs：`{decision['stage054_window_entry_loss_abs']:,.2f}`。",
        f"- negative condition 数：`{decision['negative_condition_count']}`。",
        f"- top_negative_conditions：`{decision['top_negative_conditions']}`。",
        "",
        "## 条件 PnL 汇总",
        "",
        _md_table(condition_summary, max_rows=40),
        "",
        "## 校验",
        "",
        _md_table(validation, max_rows=20),
        "",
        "## 输出",
        "",
        f"- unique_windows：`{SELECTED_WINDOWS_PATH}`",
        f"- trades：`{TRADES_PATH}`",
        f"- entry_risk：`{ENTRY_RISK_PATH}`",
        f"- entry_candidates：`{ENTRY_CANDIDATES_PATH}`",
        f"- closed_lots：`{CLOSED_LOTS_PATH}`",
        f"- feature_matrix：`{FEATURE_MATRIX_PATH}`",
        f"- window_entries：`{WINDOW_ENTRIES_PATH}`",
        f"- condition_summary：`{CONDITION_SUMMARY_PATH}`",
        f"- source_summary：`{SOURCE_SUMMARY_PATH}`",
        f"- validation：`{VALIDATION_PATH}`",
        f"- chart：`{CHART_PATH}`",
        f"- decision：`{DECISION_PATH}`",
        f"- report：`{REPORT_PATH}`",
        "",
        "## 反思",
        "",
        f"- 运行前过拟合反思：{decision['overfit_reflection_before']}",
        f"- 运行后过拟合反思：{decision['overfit_reflection_after']}",
        f"- 运行前继续价值反思：{decision['continue_value_before']}",
        f"- 运行后继续价值反思：{decision['continue_value_after']}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)

    raw_windows = _read_csv(STAGE054_SELECTED_WINDOWS_PATH)
    unique_windows = unique_stage054_windows(raw_windows)
    trades, entry_risk, entry_candidates, closed_lots = _run_sources(unique_windows)
    feature_matrix = _build_feature_matrix(closed_lots, entry_candidates)
    feature_matrix = attach_stage054_windows_to_entries(feature_matrix, unique_windows)
    window_entries = feature_matrix[feature_matrix["inside_stage054_window"].astype(bool)].copy()
    condition_summary = summarize_condition_pnl(window_entries)
    source_summary = _source_summary(window_entries)
    stage054_curve_attr = _read_csv(STAGE054_CURVE_ATTRIBUTION_PATH)
    validation = _validation(feature_matrix, window_entries, stage054_curve_attr)
    decision = _decision(unique_windows, feature_matrix, window_entries, condition_summary, validation)

    unique_windows.to_csv(SELECTED_WINDOWS_PATH, index=False, encoding="utf-8-sig")
    trades.to_csv(TRADES_PATH, index=False, encoding="utf-8-sig", compression="gzip")
    entry_risk.to_csv(ENTRY_RISK_PATH, index=False, encoding="utf-8-sig", compression="gzip")
    entry_candidates.to_csv(ENTRY_CANDIDATES_PATH, index=False, encoding="utf-8-sig", compression="gzip")
    closed_lots.to_csv(CLOSED_LOTS_PATH, index=False, encoding="utf-8-sig", compression="gzip")
    feature_matrix.to_csv(FEATURE_MATRIX_PATH, index=False, encoding="utf-8-sig")
    window_entries.to_csv(WINDOW_ENTRIES_PATH, index=False, encoding="utf-8-sig")
    condition_summary.to_csv(CONDITION_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    source_summary.to_csv(SOURCE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    validation.to_csv(VALIDATION_PATH, index=False, encoding="utf-8-sig")
    _plot(condition_summary)
    _write_report(decision, unique_windows, condition_summary, source_summary, validation)
    stage_record = _write_stage_record(decision, condition_summary, validation)
    decision["stage_record_path"] = str(stage_record)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    return decision


if __name__ == "__main__":
    run()
