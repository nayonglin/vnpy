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


PROJECT_DIR = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
UPSTREAM_LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage009"
MODEL_TAG = "stage009_meta_label_entry_quality_audit_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage009_meta_label_entry_quality_audit"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage009_meta_label_entry_quality_audit"
UPSTREAM_LINE_DIR = PROJECT_DIR / "research" / "lines" / UPSTREAM_LINE_ID
STAGE019_OUTPUT_DIR = UPSTREAM_LINE_DIR / "outputs" / "stage019_stage018_regime_gate_failure_attribution"
STAGE019_PREFIX = "rebuilt_c9_stage019_stage018_regime_gate_failure_attribution"
STAGE019_TAG = "stage019_stage018_regime_gate_failure_attribution_v1"
STAGE013_CLOSED_LOTS_PATH = (
    STAGE019_OUTPUT_DIR / f"{STAGE019_PREFIX}_stage013_rebuilt_closed_lots_{STAGE019_TAG}.csv"
)

QUALITY_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_quality_events_{MODEL_TAG}.csv.gz"
CONDITION_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_condition_summary_{MODEL_TAG}.csv"
YEAR_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_summary_{MODEL_TAG}.csv"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_condition_quality_chart_{MODEL_TAG}.png"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
STAGE_RECORD_PATH = LINE_DIR / "stages" / "20260702_0426_stage009_meta_label_entry_quality_audit.md"

MIN_ENTRY_DATE = pd.Timestamp("2020-01-01")
MAX_ENTRY_DATE = pd.Timestamp("2026-06-30")
BIG_WINNER_R = 6.0
BAD_PATH_R = -1.0
BAD_PATH_MAE_R = 3.0

DEFAULT_MIN_EVENT_COUNT = 80
DEFAULT_MIN_YEAR_COUNT = 4
DEFAULT_MIN_MEAN_PNL_LIFT = 1.25
DEFAULT_MAX_BAD_PATH_RATE_DELTA_PP = 5.0


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if not np.isfinite(number) else number
    if isinstance(value, (pd.Timestamp, datetime)):
        return None if pd.isna(value) else value.isoformat()
    if pd.isna(value):
        return None
    return value


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


def _numeric(frame: pd.DataFrame, column: str, default: float = np.nan) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce")


def _bool_column(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(False, index=frame.index)
    text = frame[column].astype(str).str.strip().str.lower()
    return text.isin(["1", "1.0", "true", "yes", "y", "pass", "passed", "opened"])


def _pctize(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    sample = values.replace([np.inf, -np.inf], np.nan).dropna().abs()
    if not sample.empty and sample.quantile(0.99) <= 1.5:
        values = values * 100.0
    return values


def _md_table(frame: pd.DataFrame, max_rows: int = 20) -> str:
    if frame.empty:
        return "_无数据_"
    shown = frame.head(max_rows).copy()
    for column in shown.columns:
        if pd.api.types.is_float_dtype(shown[column]):
            shown[column] = shown[column].map(lambda value: f"{value:.4f}" if pd.notna(value) else "")
    return shown.to_markdown(index=False)


def prepare_closed_lots_for_quality_audit(
    closed_lots: pd.DataFrame,
    *,
    min_entry_date: pd.Timestamp = MIN_ENTRY_DATE,
    max_entry_date: pd.Timestamp = MAX_ENTRY_DATE,
) -> pd.DataFrame:
    data = closed_lots.copy()
    if "entry_context" not in data.columns:
        data["entry_context"] = ""
    if "direction" not in data.columns:
        data["direction"] = ""
    if "entry_date" not in data.columns:
        data["entry_date"] = pd.NaT
    if "product" not in data.columns:
        data["product"] = ""
    if "requested_start_month" not in data.columns:
        data["requested_start_month"] = ""
    data["entry_context"] = data["entry_context"].astype(str)
    data["direction"] = data["direction"].astype(str).str.lower()
    data["entry_date"] = pd.to_datetime(data["entry_date"], errors="coerce").dt.normalize()
    data["product"] = data["product"].astype(str)
    data["requested_start_month"] = data["requested_start_month"].astype(str)
    for column in [
        "risk_amount",
        "r_multiple",
        "realized_pnl",
        "ai_product_pool_rank",
        "ai_product_pool_score",
        "active_positions_before",
        "loss_streak",
        "risk_multiplier",
        "selected_volume",
        "rsi_value",
        "breakout",
        "bullish_alignment",
        "bearish_alignment",
        "portfolio_drawdown_pct",
        "same_direction_correlation_max_corr",
        "same_direction_correlation_active_count",
        "entry_risk_distance_pct",
        "mfe_r",
        "mae_r",
        "holding_calendar_days",
        "volume",
        "size",
    ]:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    mask = (
        data["entry_context"].eq("flat_entry")
        & data["direction"].isin(["long", "short"])
        & data["entry_date"].ge(min_entry_date)
        & data["entry_date"].le(max_entry_date)
        & _numeric(data, "risk_amount").gt(0)
        & _numeric(data, "r_multiple").replace([np.inf, -np.inf], np.nan).notna()
        & _numeric(data, "ai_product_pool_rank").gt(0)
    )
    data = data.loc[mask].copy().reset_index(drop=True)
    data["entry_year"] = data["entry_date"].dt.year.astype(int)
    data["winner"] = _numeric(data, "r_multiple").gt(0).astype(int)
    if "big_winner" in data.columns:
        data["big_winner"] = _bool_column(data, "big_winner").astype(int)
    else:
        data["big_winner"] = _numeric(data, "r_multiple").ge(BIG_WINNER_R).astype(int)
    data["bad_path"] = (
        _numeric(data, "r_multiple").le(BAD_PATH_R) | _numeric(data, "mae_r").ge(BAD_PATH_MAE_R)
    ).astype(int)
    if "portfolio_drawdown_pct" in data.columns:
        data["portfolio_drawdown_abs_pct"] = _pctize(data["portfolio_drawdown_pct"]).abs()
    else:
        data["portfolio_drawdown_abs_pct"] = np.nan
    if "entry_risk_distance_pct" in data.columns:
        data["entry_risk_distance_pct_abs"] = _pctize(data["entry_risk_distance_pct"]).abs()
    else:
        data["entry_risk_distance_pct_abs"] = np.nan
    return data


def _safe_div(numerator: float, denominator: float) -> float:
    if not np.isfinite(numerator) or not np.isfinite(denominator) or abs(denominator) < 1e-12:
        return np.nan
    return float(numerator / denominator)


def evaluate_quality_condition(
    events: pd.DataFrame,
    *,
    name: str,
    description: str,
    mask: pd.Series,
    min_event_count: int = DEFAULT_MIN_EVENT_COUNT,
    min_year_count: int = DEFAULT_MIN_YEAR_COUNT,
    min_mean_pnl_lift: float = DEFAULT_MIN_MEAN_PNL_LIFT,
    max_bad_path_rate_delta_pp: float = DEFAULT_MAX_BAD_PATH_RATE_DELTA_PP,
    candidate_eligible: bool = True,
) -> dict[str, Any]:
    mask = mask.reindex(events.index).fillna(False).astype(bool)
    subset = events.loc[mask].copy()
    base_count = int(len(events))
    event_count = int(len(subset))
    base_pnl = float(_numeric(events, "realized_pnl").sum())
    selected_pnl = float(_numeric(subset, "realized_pnl").sum()) if event_count else 0.0
    base_mean_pnl = float(_numeric(events, "realized_pnl").mean()) if base_count else np.nan
    selected_mean_pnl = float(_numeric(subset, "realized_pnl").mean()) if event_count else np.nan
    base_big_rate = float(_numeric(events, "big_winner").mean() * 100.0) if base_count else np.nan
    selected_big_rate = float(_numeric(subset, "big_winner").mean() * 100.0) if event_count else np.nan
    base_bad_rate = float(_numeric(events, "bad_path").mean() * 100.0) if base_count else np.nan
    selected_bad_rate = float(_numeric(subset, "bad_path").mean() * 100.0) if event_count else np.nan
    year = (
        subset.groupby("entry_year", dropna=False)
        .agg(
            event_count=("realized_pnl", "size"),
            total_pnl=("realized_pnl", "sum"),
            mean_pnl=("realized_pnl", "mean"),
            big_winner_rate_pct=("big_winner", lambda s: float(pd.to_numeric(s, errors="coerce").mean() * 100.0)),
            bad_path_rate_pct=("bad_path", lambda s: float(pd.to_numeric(s, errors="coerce").mean() * 100.0)),
        )
        .reset_index()
        if event_count
        else pd.DataFrame(columns=["entry_year", "event_count", "total_pnl", "mean_pnl"])
    )
    positive_year_count = int(pd.to_numeric(year.get("total_pnl", pd.Series(dtype=float)), errors="coerce").gt(0).sum())
    year_count = int(year["entry_year"].nunique()) if "entry_year" in year else 0
    min_year_pnl = float(pd.to_numeric(year.get("total_pnl", pd.Series(dtype=float)), errors="coerce").min()) if len(year) else np.nan
    mean_lift = _safe_div(selected_mean_pnl, base_mean_pnl)
    big_lift = _safe_div(selected_big_rate, base_big_rate)
    bad_delta = selected_bad_rate - base_bad_rate if np.isfinite(selected_bad_rate) and np.isfinite(base_bad_rate) else np.nan
    stable = (
        bool(candidate_eligible)
        and event_count >= int(min_event_count)
        and year_count >= int(min_year_count)
        and positive_year_count >= int(min_year_count)
        and selected_pnl > 0.0
        and np.isfinite(mean_lift)
        and mean_lift >= float(min_mean_pnl_lift)
        and np.isfinite(bad_delta)
        and bad_delta <= float(max_bad_path_rate_delta_pp)
    )
    return {
        "condition": name,
        "description": description,
        "candidate_eligible": bool(candidate_eligible),
        "event_count": event_count,
        "event_share_pct": event_count / base_count * 100.0 if base_count else 0.0,
        "year_count": year_count,
        "positive_year_count": positive_year_count,
        "min_year_pnl": min_year_pnl,
        "total_pnl": selected_pnl,
        "total_pnl_share_pct": _safe_div(selected_pnl, base_pnl) * 100.0 if np.isfinite(_safe_div(selected_pnl, base_pnl)) else np.nan,
        "mean_pnl": selected_mean_pnl,
        "baseline_mean_pnl": base_mean_pnl,
        "mean_pnl_lift": mean_lift,
        "winner_rate_pct": float(_numeric(subset, "winner").mean() * 100.0) if event_count else np.nan,
        "big_winner_rate_pct": selected_big_rate,
        "baseline_big_winner_rate_pct": base_big_rate,
        "big_winner_rate_lift": big_lift,
        "bad_path_rate_pct": selected_bad_rate,
        "baseline_bad_path_rate_pct": base_bad_rate,
        "bad_path_rate_delta_pp": bad_delta,
        "median_r_multiple": float(_numeric(subset, "r_multiple").median()) if event_count else np.nan,
        "median_ai_rank": float(_numeric(subset, "ai_product_pool_rank").median()) if event_count else np.nan,
        "median_active_positions_before": float(_numeric(subset, "active_positions_before").median()) if event_count else np.nan,
        "median_portfolio_drawdown_abs_pct": float(_numeric(subset, "portfolio_drawdown_abs_pct").median()) if event_count else np.nan,
        "stable_quality_candidate": bool(stable),
    }


def _condition_masks(events: pd.DataFrame) -> list[tuple[str, str, pd.Series, bool]]:
    index = events.index

    def num(column: str) -> pd.Series:
        return _numeric(events, column)

    direction = events["direction"].astype(str).str.lower()
    ai_rank = num("ai_product_pool_rank")
    active = num("active_positions_before")
    loss_streak = num("loss_streak")
    risk_multiplier = num("risk_multiplier")
    selected_volume = num("selected_volume")
    rsi = num("rsi_value")
    breakout = num("breakout")
    bullish = num("bullish_alignment")
    bearish = num("bearish_alignment")
    drawdown = num("portfolio_drawdown_abs_pct")
    corr_count = num("same_direction_correlation_corr_count")
    corr_active = num("same_direction_correlation_active_count")
    corr_max = num("same_direction_correlation_max_corr")
    entry_risk = num("entry_risk_distance_pct_abs")

    trend_aligned = (direction.eq("long") & bullish.eq(1)) | (direction.eq("short") & bearish.eq(1))
    rsi_follow = (direction.eq("long") & rsi.ge(60)) | (direction.eq("short") & rsi.le(40))
    rsi_extreme = (direction.eq("long") & rsi.ge(75)) | (direction.eq("short") & rsi.le(25))
    no_corr = corr_count.fillna(0).le(0) & corr_active.fillna(0).le(0) & corr_max.fillna(0).le(0)
    healthy = drawdown.lt(20)
    low_active = active.lt(3)
    ai_top8 = ai_rank.ge(1) & ai_rank.le(8)
    ai_top6 = ai_rank.ge(1) & ai_rank.le(6)
    ai_top4 = ai_rank.ge(1) & ai_rank.le(4)

    return [
        ("all_ai_flat_entries", "2020+ AI 可见 flat-entry 全部事件；只作基准", pd.Series(True, index=index), False),
        ("ai_rank_1_4", "AI rank 1-4", ai_top4, True),
        ("ai_rank_1_6", "AI rank 1-6", ai_top6, True),
        ("ai_rank_1_8", "AI rank 1-8", ai_top8, True),
        ("active_positions_lt3", "入场前活跃持仓 <3", low_active, True),
        ("account_drawdown_lt20", "账户回撤绝对值 <20%", healthy, True),
        ("trend_aligned", "入场方向与中长期均线方向一致", trend_aligned, True),
        ("rsi_directional_follow", "RSI 顺势：long>=60 或 short<=40", rsi_follow, True),
        ("rsi_extreme_follow", "RSI 极端顺势：long>=75 或 short<=25", rsi_extreme, True),
        ("breakout_true", "breakout 为真", breakout.eq(1), True),
        ("selected_volume_gt1", "selected_volume >1", selected_volume.gt(1), True),
        ("risk_multiplier_ge2", "risk_multiplier >=2", risk_multiplier.ge(2), True),
        ("loss_streak_eq0", "loss_streak=0", loss_streak.eq(0), True),
        ("same_direction_corr_none", "无同向相关持仓", no_corr, True),
        ("entry_risk_distance_le2pct", "入场止损距离 <=2%", entry_risk.le(2), True),
        ("ai_rank_1_8_and_active_lt3", "AI rank 1-8 且活跃持仓 <3", ai_top8 & low_active, True),
        ("ai_rank_1_8_and_account_healthy", "AI rank 1-8 且账户回撤 <20%", ai_top8 & healthy, True),
        ("ai_rank_1_8_and_trend_aligned", "AI rank 1-8 且趋势方向一致", ai_top8 & trend_aligned, True),
        ("ai_rank_1_8_and_no_corr", "AI rank 1-8 且无同向相关持仓", ai_top8 & no_corr, True),
        ("ai_rank_1_8_and_loss_streak0", "AI rank 1-8 且 loss_streak=0", ai_top8 & loss_streak.eq(0), True),
        ("ai_rank_1_8_and_rsi_follow", "AI rank 1-8 且 RSI 顺势", ai_top8 & rsi_follow, True),
        ("ai_rank_1_8_and_selected_volume_gt1", "AI rank 1-8 且 selected_volume>1", ai_top8 & selected_volume.gt(1), True),
        (
            "ai_rank_1_8_active_lt3_no_corr",
            "AI rank 1-8 且活跃持仓 <3 且无同向相关持仓",
            ai_top8 & low_active & no_corr,
            True,
        ),
        (
            "ai_rank_1_6_active_lt3_no_corr",
            "AI rank 1-6 且活跃持仓 <3 且无同向相关持仓",
            ai_top6 & low_active & no_corr,
            True,
        ),
        (
            "ai_rank_1_8_active_lt3_trend_aligned",
            "AI rank 1-8 且活跃持仓 <3 且趋势方向一致",
            ai_top8 & low_active & trend_aligned,
            True,
        ),
        (
            "ai_rank_1_8_active_lt3_account_healthy",
            "AI rank 1-8 且活跃持仓 <3 且账户回撤 <20%",
            ai_top8 & low_active & healthy,
            True,
        ),
        (
            "ai_rank_1_8_active_lt3_rsi_follow",
            "AI rank 1-8 且活跃持仓 <3 且 RSI 顺势",
            ai_top8 & low_active & rsi_follow,
            True,
        ),
        (
            "ai_rank_1_8_active_lt3_selected_volume_gt1",
            "AI rank 1-8 且活跃持仓 <3 且 selected_volume>1",
            ai_top8 & low_active & selected_volume.gt(1),
            True,
        ),
    ]


def build_condition_summary(events: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    year_rows: list[pd.DataFrame] = []
    for name, description, mask, eligible in _condition_masks(events):
        row = evaluate_quality_condition(events, name=name, description=description, mask=mask, candidate_eligible=eligible)
        rows.append(row)
        selected = events.loc[mask.reindex(events.index).fillna(False).astype(bool)].copy()
        if selected.empty:
            continue
        year = (
            selected.groupby("entry_year", as_index=False)
            .agg(
                event_count=("realized_pnl", "size"),
                total_pnl=("realized_pnl", "sum"),
                mean_pnl=("realized_pnl", "mean"),
                big_winner_rate_pct=("big_winner", lambda s: float(pd.to_numeric(s, errors="coerce").mean() * 100.0)),
                bad_path_rate_pct=("bad_path", lambda s: float(pd.to_numeric(s, errors="coerce").mean() * 100.0)),
            )
            .sort_values("entry_year")
        )
        year["condition"] = name
        year_rows.append(year)
    summary = pd.DataFrame(rows)
    if not summary.empty:
        summary = summary.sort_values(
            ["stable_quality_candidate", "mean_pnl_lift", "total_pnl", "event_count"],
            ascending=[False, False, False, False],
        ).reset_index(drop=True)
    year_summary = pd.concat(year_rows, ignore_index=True, sort=False) if year_rows else pd.DataFrame()
    return summary, year_summary


def make_decision(events: pd.DataFrame, condition_summary: pd.DataFrame) -> dict[str, Any]:
    stable = (
        condition_summary[
            condition_summary.get("stable_quality_candidate", pd.Series(False, index=condition_summary.index)).astype(bool)
            & condition_summary.get("candidate_eligible", pd.Series(False, index=condition_summary.index)).astype(bool)
        ].copy()
        if not condition_summary.empty
        else pd.DataFrame()
    )
    baseline = condition_summary[condition_summary["condition"].eq("all_ai_flat_entries")].head(1)
    if events.empty:
        decision = "stage009_no_ai_flat_entry_events_stop"
        reason = "2020+ AI 可见 flat-entry 事件为空，无法做高质量入场审计。"
    elif stable.empty:
        decision = "stage009_no_stable_meta_label_quality_candidate_stop"
        reason = "没有满足样本数、跨年正贡献、mean PnL lift 与 bad-path 约束的点时质量条件。"
    else:
        decision = "stage009_has_stable_quality_candidates_need_path_proxy"
        reason = "存在跨年稳定的点时质量条件，但本阶段只是 closed-lot 元标签审计；下一步只能先做代理路径或冻结真实引擎 A/B，不能直接上线。"
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "input_paths": {
            "stage013_closed_lots": str(STAGE013_CLOSED_LOTS_PATH.relative_to(PROJECT_DIR)),
        },
        "output_paths": {
            "quality_events": str(QUALITY_EVENTS_PATH.relative_to(PROJECT_DIR)),
            "condition_summary": str(CONDITION_SUMMARY_PATH.relative_to(PROJECT_DIR)),
            "year_summary": str(YEAR_SUMMARY_PATH.relative_to(PROJECT_DIR)),
            "chart": str(CHART_PATH.relative_to(PROJECT_DIR)),
            "report": str(REPORT_PATH.relative_to(PROJECT_DIR)),
            "decision": str(DECISION_PATH.relative_to(PROJECT_DIR)),
            "stage_record": str(STAGE_RECORD_PATH.relative_to(PROJECT_DIR)),
        },
        "analysis_scope": {
            "event_count": int(len(events)),
            "year_count": int(events["entry_year"].nunique()) if not events.empty else 0,
            "source_start_month_count": int(events["requested_start_month"].nunique()) if not events.empty else 0,
            "product_count": int(events["product"].nunique()) if not events.empty else 0,
            "total_pnl": float(_numeric(events, "realized_pnl").sum()) if not events.empty else 0.0,
            "mean_pnl": float(_numeric(events, "realized_pnl").mean()) if not events.empty else np.nan,
            "winner_rate_pct": float(_numeric(events, "winner").mean() * 100.0) if not events.empty else np.nan,
            "big_winner_rate_pct": float(_numeric(events, "big_winner").mean() * 100.0) if not events.empty else np.nan,
            "bad_path_rate_pct": float(_numeric(events, "bad_path").mean() * 100.0) if not events.empty else np.nan,
        },
        "candidate_thresholds": {
            "min_event_count": DEFAULT_MIN_EVENT_COUNT,
            "min_year_count": DEFAULT_MIN_YEAR_COUNT,
            "min_mean_pnl_lift": DEFAULT_MIN_MEAN_PNL_LIFT,
            "max_bad_path_rate_delta_pp": DEFAULT_MAX_BAD_PATH_RATE_DELTA_PP,
            "big_winner_r": BIG_WINNER_R,
            "bad_path_r": BAD_PATH_R,
            "bad_path_mae_r": BAD_PATH_MAE_R,
        },
        "baseline_row": _json_safe(baseline.to_dict("records")[0]) if not baseline.empty else {},
        "stable_candidate_count": int(len(stable)),
        "stable_candidate_conditions": stable["condition"].head(12).tolist() if not stable.empty else [],
        "top_stable_candidates": _json_safe(stable.head(12).to_dict("records")) if not stable.empty else [],
        "decision": decision,
        "decision_reason": reason,
        "external_research_judgment": (
            "Meta-labeling literature supports using a secondary layer to size/filter an existing primary signal, "
            "but also requires PIT features and robust OOS validation. Stage009 therefore audits only entry-visible "
            "conditions and does not train a free-form model."
        ),
        "overfit_reflection_before": (
            "有风险。closed-lot 标签天然使用事后收益；本阶段只把它当元标签审计，不直接交易化，且条件集合预声明、禁止产品/日期黑名单。"
        ),
        "continue_value_before": (
            "有价值。用户目标要求 AI 识别超高质量信号并加风险，必须先判断点时字段是否有跨年稳定的正向质量信息。"
        ),
        "overfit_reflection_after": (
            "待本次结果判断；若稳定候选仍只来自少数年份或失败后继续调 rank/topN/阈值，就是过拟合。"
        ),
        "continue_value_after": (
            "待本次结果判断；只有稳定候选能覆盖足够样本且不提高 bad-path 风险，才值得进路径代理或真实引擎。"
        ),
        "official_live_impact": {
            "strategy_changed": False,
            "official_live_config_changed": False,
            "order_api_called": False,
            "ctp_connected": False,
            "research_only": True,
        },
    }


def _plot_condition_summary(summary: pd.DataFrame) -> None:
    if summary.empty:
        return
    shown = summary[summary["candidate_eligible"].astype(bool)].head(16).copy()
    if shown.empty:
        return
    fig, axes = plt.subplots(1, 2, figsize=(16, 7), constrained_layout=True)
    labels = shown["condition"].astype(str).tolist()
    y = np.arange(len(shown))
    colors = np.where(shown["stable_quality_candidate"].astype(bool), "#16a34a", "#64748b")
    axes[0].barh(y, shown["mean_pnl_lift"], color=colors)
    axes[0].axvline(1.0, color="#111827", linestyle="--", linewidth=0.8)
    axes[0].set_yticks(y)
    axes[0].set_yticklabels(labels, fontsize=8)
    axes[0].invert_yaxis()
    axes[0].set_title("Mean PnL Lift")
    axes[0].grid(True, axis="x", alpha=0.25)
    axes[1].barh(y, shown["bad_path_rate_delta_pp"], color=colors)
    axes[1].axvline(0.0, color="#111827", linestyle="--", linewidth=0.8)
    axes[1].set_yticks(y)
    axes[1].set_yticklabels(labels, fontsize=8)
    axes[1].invert_yaxis()
    axes[1].set_title("Bad Path Rate Delta pp")
    axes[1].grid(True, axis="x", alpha=0.25)
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(events: pd.DataFrame, summary: pd.DataFrame, decision: dict[str, Any]) -> None:
    stable = summary[summary["stable_quality_candidate"].astype(bool)].copy() if not summary.empty else pd.DataFrame()
    top_cols = [
        "condition",
        "event_count",
        "year_count",
        "positive_year_count",
        "total_pnl",
        "mean_pnl_lift",
        "big_winner_rate_lift",
        "bad_path_rate_delta_pp",
        "stable_quality_candidate",
    ]
    text = f"""# Stage009 Meta-label 入场质量审计

- line_id：`{LINE_ID}`
- 记录时间：{decision["generated_at"]}
- 输入：`{decision["input_paths"]["stage013_closed_lots"]}`
- 样本：2020+、AI rank 可见、`flat_entry`、risk/R 可计算的 Stage013 closed lots
- 决策：`{decision["decision"]}`

## 外部调研与判断

Meta-labeling 的合理用法是：主策略继续负责方向，二级层只判断信号质量或仓位置信度。它不能凭同一批噪声特征“凭空创造 alpha”，所以本阶段只做点时字段的闭环审计，不训练自由模型、不改交易逻辑。

## 样本概况

```json
{json.dumps(_json_safe(decision["analysis_scope"]), ensure_ascii=False, indent=2)}
```

## 稳定候选

{_md_table(stable[top_cols] if not stable.empty else stable)}

## 条件总表

{_md_table(summary[top_cols] if not summary.empty else summary, max_rows=28)}

## 结论

- {decision["decision_reason"]}
- 本阶段不是资金曲线回测，不产生新的期末权益、最大回撤、Sharpe、滑点、交易次数或胜率。
- 若进入下一步，只能选择一个冻结候选做路径代理或真实引擎 A/B；不得按产品、日期、方向、rank/topN 或坏窗口继续救参。

## 过拟合反思

- 运行前：{decision["overfit_reflection_before"]}
- 运行后：{decision["overfit_reflection_after"]}

## 继续价值反思

- 运行前：{decision["continue_value_before"]}
- 运行后：{decision["continue_value_after"]}
"""
    REPORT_PATH.write_text(text, encoding="utf-8")


def _write_stage_record(decision: dict[str, Any], summary: pd.DataFrame) -> None:
    stable = summary[summary["stable_quality_candidate"].astype(bool)].copy() if not summary.empty else pd.DataFrame()
    top_cols = [
        "condition",
        "event_count",
        "year_count",
        "positive_year_count",
        "total_pnl",
        "mean_pnl_lift",
        "big_winner_rate_lift",
        "bad_path_rate_delta_pp",
        "stable_quality_candidate",
    ]
    record = f"""# Stage009 Meta-label 入场质量审计

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{decision["generated_at"]}
- 阶段性质：只读元标签/入场质量审计；不改官方 live config、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否；本阶段不跑资金曲线，只决定是否值得进入下一步路径代理/真实引擎

## 外部调研与判断

- 参考资料：Lopez de Prado / Hudson & Thames meta-labeling、trend-following right-tail/risk sizing 资料、pysystemtrade capital/risk overlay 资料。
- 我的判断：AI/元标签更适合判断“主策略信号是否值得加风险”，但必须只用入场前可见字段，并通过跨年/多起点稳定性验证。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage009_meta_label_entry_quality_audit.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage009_meta_label_entry_quality_audit.py`
- 新增参数：`MIN_ENTRY_DATE=2020-01-01`、`BIG_WINNER_R={BIG_WINNER_R}`、`BAD_PATH_R={BAD_PATH_R}`、`BAD_PATH_MAE_R={BAD_PATH_MAE_R}`、`MIN_EVENT_COUNT={DEFAULT_MIN_EVENT_COUNT}`、`MIN_YEAR_COUNT={DEFAULT_MIN_YEAR_COUNT}`、`MIN_MEAN_PNL_LIFT={DEFAULT_MIN_MEAN_PNL_LIFT}`、`MAX_BAD_PATH_RATE_DELTA_PP={DEFAULT_MAX_BAD_PATH_RATE_DELTA_PP}`
- 修改参数：无
- 删除参数：无

## 审计口径

- 输入：`{decision["input_paths"]["stage013_closed_lots"]}`
- 样本：2020+、AI rank 可见、`flat_entry`、risk/R 可计算的 Stage013 closed lots。
- 标签：`realized_pnl`、`r_multiple`、`big_winner`、`bad_path`；标签仅用于审计，不直接作为交易规则。

## 样本结果

```json
{json.dumps(_json_safe(decision["analysis_scope"]), ensure_ascii=False, indent=2)}
```

## 稳定候选

{_md_table(stable[top_cols] if not stable.empty else stable)}

## 结论

- 本阶段结论：`{decision["decision"]}`
- 原因：{decision["decision_reason"]}
- 是否进入下一步：若有稳定候选，只允许选一个冻结候选做路径代理或真实引擎 A/B；若无稳定候选，停止该元标签条件集合。

## 过拟合反思

- 运行前判断：{decision["overfit_reflection_before"]}
- 运行后判断：{decision["overfit_reflection_after"]}
- 原因：本阶段条件固定且只读；后续若按结果继续调 topN、rank、阈值、产品、方向或年份就是过拟合。

## 继续价值反思

- 运行前判断：{decision["continue_value_before"]}
- 运行后判断：{decision["continue_value_after"]}
- 原因：只有稳定质量候选能进入下一步；否则应转更外生信息源或账户层结构。

## 输出文件

- quality_events: `{decision["output_paths"]["quality_events"]}`
- condition_summary: `{decision["output_paths"]["condition_summary"]}`
- year_summary: `{decision["output_paths"]["year_summary"]}`
- chart: `{decision["output_paths"]["chart"]}`
- report: `{decision["output_paths"]["report"]}`
- decision: `{decision["output_paths"]["decision"]}`
"""
    STAGE_RECORD_PATH.write_text(record, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGE_RECORD_PATH.parent.mkdir(parents=True, exist_ok=True)
    closed = _read_csv(STAGE013_CLOSED_LOTS_PATH)
    events = prepare_closed_lots_for_quality_audit(closed)
    summary, year_summary = build_condition_summary(events)
    decision = make_decision(events, summary)
    stable_count = int(decision["stable_candidate_count"])
    if stable_count > 0:
        decision["overfit_reflection_after"] = (
            "有风险但本阶段可控。发现的稳定候选来自 closed-lot 元标签，不能直接上线；若下一步只冻结一个候选做路径代理/真实引擎，风险可控。"
        )
        decision["continue_value_after"] = (
            "有价值。存在跨年稳定的点时质量候选，值得进入下一步冻结路径代理；但不能继续调 rank/topN 或叠产品方向过滤。"
        )
    else:
        decision["overfit_reflection_after"] = (
            "否。本阶段没有根据结果调参；但若继续在同一批 closed-lot 标签上搜索更多组合，就是过拟合。"
        )
        decision["continue_value_after"] = (
            "有限。当前固定条件集合找不到稳定质量候选，应转更外生的信息源或账户层结构。"
        )
    decision["decision"] = make_decision(events, summary)["decision"]
    decision["decision_reason"] = make_decision(events, summary)["decision_reason"]
    decision["stable_candidate_count"] = stable_count
    stable = summary[summary["stable_quality_candidate"].astype(bool)].copy() if not summary.empty else pd.DataFrame()
    decision["stable_candidate_conditions"] = stable["condition"].head(12).tolist() if not stable.empty else []
    decision["top_stable_candidates"] = _json_safe(stable.head(12).to_dict("records")) if not stable.empty else []

    events.to_csv(QUALITY_EVENTS_PATH, index=False, encoding="utf-8-sig", compression="gzip")
    summary.to_csv(CONDITION_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    year_summary.to_csv(YEAR_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    _plot_condition_summary(summary)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(events, summary, decision)
    _write_stage_record(decision, summary)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
