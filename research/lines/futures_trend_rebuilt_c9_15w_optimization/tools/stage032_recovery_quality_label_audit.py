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

LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage032"
MODEL_TAG = "stage032_recovery_quality_label_audit_v1"
OUTPUT_PREFIX = "rebuilt_c9_stage032_recovery_quality_label_audit"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage032_recovery_quality_label_audit"
STAGE_RECORD_DIR = LINE_DIR / "stages"
BACK_LOG_PATH = PROJECT_DIR / "back_log.md"

STAGE006_OUTPUT_DIR = LINE_DIR / "outputs" / "stage006_current_quality_feature_binder"
STAGE007_OUTPUT_DIR = LINE_DIR / "outputs" / "stage007_minute_source_coverage_rebind"
STAGE030_OUTPUT_DIR = LINE_DIR / "outputs" / "stage030_stage029_failure_attribution"
BACKTEST_OUTPUT_DIR = PROJECT_DIR / "examples" / "portfolio_backtesting" / "backtest_outputs"

STAGE006_PREFIX = "rebuilt_c9_stage006_current_quality_feature_binder"
STAGE006_TAG = "stage006_current_quality_feature_binder_v1"
STAGE007_PREFIX = "rebuilt_c9_stage007_minute_source_coverage_rebind"
STAGE007_TAG = "stage007_minute_source_coverage_rebind_v1"
STAGE030_PREFIX = "rebuilt_c9_stage030_stage029_failure_attribution"
STAGE030_TAG = "stage030_stage029_failure_attribution_v1"

STAGE030_EVENTS_PATH = STAGE030_OUTPUT_DIR / f"{STAGE030_PREFIX}_event_lot_attribution_{STAGE030_TAG}.csv"
STAGE006_CLOSED_LOTS_PATH = STAGE006_OUTPUT_DIR / f"{STAGE006_PREFIX}_closed_lots_{STAGE006_TAG}.csv"
STAGE006_ENTRY_CANDIDATES_PATH = (
    STAGE006_OUTPUT_DIR / f"{STAGE006_PREFIX}_entry_candidates_{STAGE006_TAG}.csv"
)
STAGE007_QUALITY_FEATURES_PATH = (
    STAGE007_OUTPUT_DIR / f"{STAGE007_PREFIX}_quality_features_{STAGE007_TAG}.csv"
)
FULL_MARKET_PREDICTIONS_PATH = (
    BACKTEST_OUTPUT_DIR
    / "qmt_roll_ai_product_suitability_full_market_walkforward_predictions_product_suitability_full_market_wf_v1.csv"
)

LOT_LABELS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_lagged_lot_quality_labels_{MODEL_TAG}.csv"
LABEL_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_label_summary_{MODEL_TAG}.csv"
LABEL_COMPLEMENT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_label_complement_summary_{MODEL_TAG}.csv"
KEY_SOURCE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_key_source_summary_{MODEL_TAG}.csv"
KEY_YEAR_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_key_year_summary_{MODEL_TAG}.csv"
KEY_PRODUCT_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_key_product_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

MAX_MATCH_LAG_DAYS = 7
AI_TOP_N = 8
SIMPLE_TOP_N = 8

KEY_LABELS = [
    "label_candidate_ai_rank_1_9",
    "tag_entry_or_first_aligned",
    "label_rank_1_9_and_entry_or_first_aligned",
    "tag_ai4_6_entry_or_first_aligned",
    "stage032_ai_top8_full_market",
    "stage032_consensus_top8_full_market",
    "oi_price_confirm_passed",
    "label_preentry_core",
]

EARLY_ENTRY_LABELS = {
    "tag_entry_open_aligned",
    "tag_first_bar_aligned",
    "tag_entry_or_first_aligned",
    "tag_ai4_6_entry_or_first_aligned",
    "label_rank_1_9_and_entry_or_first_aligned",
    "label_rank_1_9_and_first_bar_aligned",
    "label_rank_1_9_and_entry_open_aligned",
    "label_early_quality_core",
}

LABEL_DESCRIPTIONS = {
    "label_candidate_ai_rank_1_9": "官方候选 AI rank 1-9；接近当前 C9 可交易池本身。",
    "label_candidate_ai_rank_1_6": "官方候选 AI rank 1-6；仅描述自然 rank 桶，不作为阈值候选。",
    "label_candidate_ai_rank_1_3": "官方候选 AI rank 1-3；仅描述自然 rank 桶，不作为阈值候选。",
    "stage032_ai_top8_full_market": "Stage021 full-market AI 预测按月 top8，按 entry_date 向前匹配最近 eval_date。",
    "stage032_simple_top8_full_market": "Stage021 simple-trend 分数按月 top8，按 entry_date 向前匹配最近 eval_date。",
    "stage032_consensus_top8_full_market": "Stage021 full-market AI top8 且 simple-trend top8。",
    "oi_price_confirm_passed": "Stage006 候选记录中的 OI/价格确认通过。",
    "tag_entry_open_aligned": "Stage007 开仓价相对信号方向有利；开仓日早段可见。",
    "tag_first_bar_aligned": "Stage007 首分钟方向有利；开仓日早段可见。",
    "tag_entry_or_first_aligned": "Stage007 开仓价或首分钟至少一个方向有利；开仓日早段可见。",
    "tag_ai4_6_entry_or_first_aligned": "旧 Stage008 固定质量标签：AI rank 4-6 且开仓/首分钟方向有利。",
    "label_rank_1_9_and_entry_or_first_aligned": "官方 AI rank 1-9 且开仓价或首分钟方向有利。",
    "label_rank_1_9_and_consensus_top8": "官方 AI rank 1-9 且 full-market AI/simple 共识 top8。",
    "label_rank_1_9_and_oi_confirm": "官方 AI rank 1-9 且 OI/价格确认通过。",
    "label_early_quality_core": "rank 1-9 且 entry_or_first_aligned 且首分钟可用；只允许作为早段质量审计。",
    "label_preentry_core": "rank 1-9 且 full-market consensus 或 OI confirm；只使用入场前/月度信息。",
}

EXTERNAL_RESEARCH_JUDGMENT = (
    "Trend-following references emphasize right-tail convexity and the risk of cutting winners after drawdowns. "
    "Stage032 therefore audits fixed, low-degree quality labels on the Stage031 recovery set before writing any "
    "engine rule. Pure post-entry or first-minute labels are treated as early-risk-release evidence, not as "
    "pre-entry sizing evidence."
)
OVERFIT_REFLECTION_BEFORE = (
    "否。标签列表来自既有 Stage007/Stage021/Stage006 固定字段和官方 AI rank 桶；本阶段只读审计，不按结果调阈值。"
)
CONTINUE_VALUE_BEFORE = (
    "有。Stage031 已证明机械暂停会砍掉恢复右尾；需要判断是否存在可见的高质量恢复标签，避免下一步继续盲目停手。"
)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        number = float(value)
        return None if not np.isfinite(number) else number
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    if pd.isna(value):
        return None
    return value


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_无数据_"
    shown = frame.copy()
    if max_rows is not None:
        shown = shown.head(max_rows)
    return shown.to_markdown(index=False)


def _boolify(series: pd.Series) -> pd.Series:
    text = series.astype(str).str.lower()
    numeric = pd.to_numeric(series, errors="coerce")
    return series.eq(True) | numeric.eq(1) | text.isin(["true", "1", "yes"])


def _product_key(product: Any, vt_symbol: Any) -> str:
    product_text = str(product or "").strip()
    if "." in product_text:
        return product_text.lower()
    vt_text = str(vt_symbol or "").strip()
    if "." not in vt_text or not product_text:
        return product_text.lower()
    exchange = vt_text.rsplit(".", 1)[-1]
    return f"{product_text}.{exchange}".lower()


def _prepare_events() -> pd.DataFrame:
    events = _read_csv(STAGE030_EVENTS_PATH, low_memory=False)
    events = events[pd.to_numeric(events["baseline_candidate_opened"], errors="coerce").fillna(0).astype(int).eq(1)]
    events = events.copy()
    events["requested_start_month"] = events["requested_start_month"].astype(str)
    events["date"] = pd.to_datetime(events["date"], errors="coerce").dt.normalize()
    events["product_vt_symbol"] = events["product_vt_symbol"].astype(str)
    events["direction"] = events["direction"].astype(str).str.lower()
    events["event_month"] = events["date"].dt.strftime("%Y-%m")
    events["event_key"] = (
        events["requested_start_month"]
        + "|"
        + events["date"].dt.strftime("%Y-%m-%d")
        + "|"
        + events["product_vt_symbol"]
        + "|"
        + events["direction"]
    )
    keep = [
        "event_key",
        "requested_start_month",
        "date",
        "event_month",
        "product_vt_symbol",
        "direction",
        "trigger_bucket",
        "baseline_candidate_min_ai_rank",
        "baseline_selected_volume_sum",
        "stage029_injury_pause_reduced_volume",
    ]
    return events[keep].dropna(subset=["date"]).reset_index(drop=True)


def _prepare_lots() -> pd.DataFrame:
    lots = _read_csv(STAGE006_CLOSED_LOTS_PATH, low_memory=False)
    lots = lots.copy()
    lots["requested_start_month"] = lots["requested_start_month"].astype(str)
    lots["entry_date"] = pd.to_datetime(lots["entry_date"], errors="coerce").dt.normalize()
    lots["exit_date"] = pd.to_datetime(lots["exit_date"], errors="coerce").dt.normalize()
    lots["product_vt_symbol"] = lots["product"].astype(str)
    lots["direction"] = lots["direction"].astype(str).str.lower()
    lots["entry_context"] = lots["entry_context"].astype(str)
    for column in ["realized_pnl", "volume", "r_multiple", "big_winner", "winner"]:
        lots[column] = pd.to_numeric(lots[column], errors="coerce").fillna(0.0)
    return lots.dropna(subset=["entry_date"]).reset_index(drop=True)


def _lagged_lot_match(events: pd.DataFrame, lots: pd.DataFrame) -> pd.DataFrame:
    merged = events.merge(
        lots,
        on=["requested_start_month", "product_vt_symbol", "direction"],
        how="left",
        suffixes=("_event", ""),
    )
    merged["match_lag_days"] = (merged["entry_date"] - merged["date"]).dt.days
    matched = merged[
        merged["match_lag_days"].ge(0)
        & merged["match_lag_days"].le(MAX_MATCH_LAG_DAYS)
        & merged["entry_context"].eq("flat_entry")
    ].copy()
    if matched.empty:
        return matched
    min_lag = matched.groupby("event_key")["match_lag_days"].transform("min")
    return matched[matched["match_lag_days"].eq(min_lag)].reset_index(drop=True)


def _quality_features() -> pd.DataFrame:
    features = _read_csv(STAGE007_QUALITY_FEATURES_PATH, low_memory=False)
    features["requested_start_month"] = features["requested_start_month"].astype(str)
    keep = [
        "requested_start_month",
        "lot_id",
        "entry_first_bar_available",
        "tag_entry_open_aligned",
        "tag_first_bar_aligned",
        "tag_entry_or_first_aligned",
        "tag_entry_and_first_aligned",
        "tag_ai4_6_entry_or_first_aligned",
        "tag_ai4_6_not_aligned",
        "tag_aligned_not_ai4_6",
        "entry_open_gap_r",
        "first_bar_directional_r",
        "first_bar_body_directional_r",
        "first_bar_adverse_wick_bucket",
        "first_bar_oi_change",
        "minute_binder_source_id",
    ]
    return features[[column for column in keep if column in features.columns]].copy()


def _candidate_features() -> pd.DataFrame:
    usecols = [
        "requested_start_month",
        "date",
        "product_vt_symbol",
        "direction",
        "entry_context",
        "is_opened",
        "oi_price_confirm_passed",
        "oi_price_confirm_oi_up",
        "oi_price_confirm_price_aligned",
        "ai_product_pool_rank",
        "ai_product_pool_score",
        "selection_pairwise_rank",
        "selection_pairwise_score",
        "portfolio_drawdown_pct",
        "loss_streak",
        "selected_volume",
    ]
    candidates = _read_csv(STAGE006_ENTRY_CANDIDATES_PATH, usecols=usecols, low_memory=False)
    candidates["requested_start_month"] = candidates["requested_start_month"].astype(str)
    candidates["date"] = pd.to_datetime(candidates["date"], errors="coerce").dt.normalize()
    candidates["product_vt_symbol"] = candidates["product_vt_symbol"].astype(str)
    candidates["direction"] = candidates["direction"].astype(str).str.lower()
    candidates = candidates[candidates["entry_context"].astype(str).eq("flat_entry")].copy()
    candidates["event_key"] = (
        candidates["requested_start_month"]
        + "|"
        + candidates["date"].dt.strftime("%Y-%m-%d")
        + "|"
        + candidates["product_vt_symbol"]
        + "|"
        + candidates["direction"]
    )

    def bool_max(values: pd.Series) -> float:
        return float(_boolify(values).max())

    return (
        candidates.groupby("event_key", as_index=False)
        .agg(
            candidate_rows=("event_key", "size"),
            candidate_opened=("is_opened", bool_max),
            oi_price_confirm_passed=("oi_price_confirm_passed", bool_max),
            oi_price_confirm_oi_up=("oi_price_confirm_oi_up", bool_max),
            oi_price_confirm_price_aligned=("oi_price_confirm_price_aligned", bool_max),
            candidate_ai_rank=("ai_product_pool_rank", "min"),
            candidate_ai_score=("ai_product_pool_score", "max"),
            selection_pairwise_rank=("selection_pairwise_rank", "min"),
            selection_pairwise_score=("selection_pairwise_score", "max"),
            portfolio_drawdown_pct=("portfolio_drawdown_pct", "max"),
            loss_streak=("loss_streak", "max"),
            selected_volume=("selected_volume", "sum"),
        )
        .reset_index(drop=True)
    )


def _predictions() -> pd.DataFrame:
    predictions = _read_csv(
        FULL_MARKET_PREDICTIONS_PATH,
        usecols=[
            "eval_date",
            "product_vt_symbol",
            "predicted_product_suitability_probability",
            "simple_trend_suitability_score",
        ],
        parse_dates=["eval_date"],
    )
    predictions["eval_date"] = pd.to_datetime(predictions["eval_date"], errors="coerce").dt.normalize()
    predictions["product_key"] = predictions["product_vt_symbol"].astype(str).str.lower()
    predictions = predictions.drop(columns=["product_vt_symbol"])
    predictions["ai_rank_desc"] = (
        predictions.groupby("eval_date")["predicted_product_suitability_probability"]
        .rank(method="first", ascending=False)
        .astype("int64")
    )
    predictions["simple_rank_desc"] = (
        predictions.groupby("eval_date")["simple_trend_suitability_score"]
        .rank(method="first", ascending=False)
        .astype("int64")
    )
    predictions["stage032_ai_top8_full_market"] = predictions["ai_rank_desc"].le(AI_TOP_N)
    predictions["stage032_simple_top8_full_market"] = predictions["simple_rank_desc"].le(SIMPLE_TOP_N)
    predictions["stage032_consensus_top8_full_market"] = (
        predictions["stage032_ai_top8_full_market"] & predictions["stage032_simple_top8_full_market"]
    )
    return predictions.sort_values(["product_key", "eval_date"]).reset_index(drop=True)


def _merge_predictions(lots: pd.DataFrame, predictions: pd.DataFrame) -> pd.DataFrame:
    lots = lots.copy()
    lots["product_key"] = [
        _product_key(product, vt_symbol)
        for product, vt_symbol in zip(lots["product"], lots["vt_symbol"], strict=False)
    ]
    frames: list[pd.DataFrame] = []
    for product_key, lot_group in lots.sort_values(["product_key", "entry_date"]).groupby("product_key", sort=False):
        left = lot_group.sort_values("entry_date").copy()
        right = predictions[predictions["product_key"].eq(product_key)].sort_values("eval_date").drop(
            columns=["product_key"]
        )
        if right.empty:
            out = left.copy()
            for column in predictions.columns:
                if column != "product_key" and column not in out.columns:
                    out[column] = np.nan
        else:
            out = pd.merge_asof(
                left,
                right,
                left_on="entry_date",
                right_on="eval_date",
                direction="backward",
                allow_exact_matches=True,
            )
        frames.append(out)
    merged = pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()
    for column in [
        "stage032_ai_top8_full_market",
        "stage032_simple_top8_full_market",
        "stage032_consensus_top8_full_market",
    ]:
        merged[column] = _boolify(merged[column]) if column in merged.columns else False
    merged["stage032_prediction_matched"] = merged["eval_date"].notna()
    return merged


def _label_lots() -> pd.DataFrame:
    events = _prepare_events()
    lots = _prepare_lots()
    matched = _lagged_lot_match(events, lots)
    quality = _quality_features()
    candidates = _candidate_features()
    predictions = _predictions()

    matched = matched.merge(quality, on=["requested_start_month", "lot_id"], how="left")
    matched = matched.merge(candidates, on="event_key", how="left")
    matched = _merge_predictions(matched, predictions)

    rank = pd.to_numeric(matched["baseline_candidate_min_ai_rank"], errors="coerce")
    matched["label_candidate_ai_rank_1_9"] = rank.between(1, 9, inclusive="both")
    matched["label_candidate_ai_rank_1_6"] = rank.between(1, 6, inclusive="both")
    matched["label_candidate_ai_rank_1_3"] = rank.between(1, 3, inclusive="both")
    for column in [
        "entry_first_bar_available",
        "tag_entry_open_aligned",
        "tag_first_bar_aligned",
        "tag_entry_or_first_aligned",
        "tag_entry_and_first_aligned",
        "tag_ai4_6_entry_or_first_aligned",
        "tag_ai4_6_not_aligned",
        "tag_aligned_not_ai4_6",
        "oi_price_confirm_passed",
        "oi_price_confirm_oi_up",
        "oi_price_confirm_price_aligned",
    ]:
        if column in matched.columns:
            matched[column] = _boolify(matched[column])
        else:
            matched[column] = False

    matched["label_rank_1_9_and_entry_or_first_aligned"] = (
        matched["label_candidate_ai_rank_1_9"] & matched["tag_entry_or_first_aligned"]
    )
    matched["label_rank_1_9_and_first_bar_aligned"] = (
        matched["label_candidate_ai_rank_1_9"] & matched["tag_first_bar_aligned"]
    )
    matched["label_rank_1_9_and_entry_open_aligned"] = (
        matched["label_candidate_ai_rank_1_9"] & matched["tag_entry_open_aligned"]
    )
    matched["label_rank_1_9_and_consensus_top8"] = (
        matched["label_candidate_ai_rank_1_9"] & matched["stage032_consensus_top8_full_market"]
    )
    matched["label_rank_1_9_and_oi_confirm"] = (
        matched["label_candidate_ai_rank_1_9"] & matched["oi_price_confirm_passed"]
    )
    matched["label_early_quality_core"] = (
        matched["label_candidate_ai_rank_1_9"]
        & matched["tag_entry_or_first_aligned"]
        & matched["entry_first_bar_available"]
    )
    matched["label_preentry_core"] = matched["label_candidate_ai_rank_1_9"] & (
        matched["stage032_consensus_top8_full_market"] | matched["oi_price_confirm_passed"]
    )

    matched["entry_year"] = pd.to_datetime(matched["entry_date"], errors="coerce").dt.year
    return matched.reset_index(drop=True)


def _label_summary(frame: pd.DataFrame) -> pd.DataFrame:
    labels = [
        "label_candidate_ai_rank_1_9",
        "label_candidate_ai_rank_1_6",
        "label_candidate_ai_rank_1_3",
        "stage032_ai_top8_full_market",
        "stage032_simple_top8_full_market",
        "stage032_consensus_top8_full_market",
        "oi_price_confirm_passed",
        "tag_entry_open_aligned",
        "tag_first_bar_aligned",
        "tag_entry_or_first_aligned",
        "tag_ai4_6_entry_or_first_aligned",
        "label_rank_1_9_and_entry_or_first_aligned",
        "label_rank_1_9_and_consensus_top8",
        "label_rank_1_9_and_oi_confirm",
        "label_early_quality_core",
        "label_preentry_core",
    ]
    base_pnl = float(pd.to_numeric(frame["realized_pnl"], errors="coerce").fillna(0.0).sum())
    rows: list[dict[str, Any]] = []
    for label in labels:
        mask = _boolify(frame[label]) if label in frame.columns else pd.Series(False, index=frame.index)
        selected = frame[mask].copy()
        if selected.empty:
            continue
        source_pnl = selected.groupby("requested_start_month")["realized_pnl"].sum()
        year_pnl = selected.groupby("entry_year")["realized_pnl"].sum()
        product_pnl = selected.groupby("product_vt_symbol")["realized_pnl"].sum()
        rows.append(
            {
                "label": label,
                "description": LABEL_DESCRIPTIONS.get(label, ""),
                "visibility": "early_entry" if label in EARLY_ENTRY_LABELS else "pre_entry_or_monthly",
                "lot_rows": int(len(selected)),
                "event_count": int(selected["event_key"].nunique()),
                "source_count": int(selected["requested_start_month"].nunique()),
                "year_count": int(selected["entry_year"].nunique()),
                "product_count": int(selected["product_vt_symbol"].nunique()),
                "realized_pnl": float(selected["realized_pnl"].sum()),
                "pnl_share_of_recovery_set": float(selected["realized_pnl"].sum() / base_pnl) if base_pnl else np.nan,
                "avg_pnl_per_lot": float(selected["realized_pnl"].mean()),
                "median_pnl_per_lot": float(selected["realized_pnl"].median()),
                "win_rate_pct": float(selected["realized_pnl"].gt(0).mean() * 100.0),
                "big_winner_count": int(pd.to_numeric(selected["big_winner"], errors="coerce").fillna(0).sum()),
                "source_positive_rate_pct": float(source_pnl.gt(0).mean() * 100.0),
                "year_positive_rate_pct": float(year_pnl.gt(0).mean() * 100.0),
                "product_positive_rate_pct": float(product_pnl.gt(0).mean() * 100.0),
            }
        )
    return pd.DataFrame(rows).sort_values("realized_pnl", ascending=False).reset_index(drop=True)


def _label_complements(frame: pd.DataFrame, labels: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for label in labels:
        mask = _boolify(frame[label])
        for side, part in [("selected", frame[mask]), ("not_selected", frame[~mask])]:
            source_pnl = part.groupby("requested_start_month")["realized_pnl"].sum()
            rows.append(
                {
                    "label": label,
                    "side": side,
                    "lot_rows": int(len(part)),
                    "event_count": int(part["event_key"].nunique()),
                    "realized_pnl": float(part["realized_pnl"].sum()),
                    "avg_pnl_per_lot": float(part["realized_pnl"].mean()) if len(part) else np.nan,
                    "median_pnl_per_lot": float(part["realized_pnl"].median()) if len(part) else np.nan,
                    "win_rate_pct": float(part["realized_pnl"].gt(0).mean() * 100.0) if len(part) else np.nan,
                    "source_positive_rate_pct": float(source_pnl.gt(0).mean() * 100.0) if len(source_pnl) else np.nan,
                }
            )
    return pd.DataFrame(rows)


def _key_breakdown(frame: pd.DataFrame, group_col: str, labels: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for label in labels:
        selected = frame[_boolify(frame[label])].copy()
        grouped = (
            selected.groupby(group_col, dropna=False)
            .agg(
                lot_rows=("lot_id", "count"),
                event_count=("event_key", "nunique"),
                realized_pnl=("realized_pnl", "sum"),
                avg_pnl_per_lot=("realized_pnl", "mean"),
                win_rate_pct=("realized_pnl", lambda s: float(pd.Series(s).gt(0).mean() * 100.0)),
            )
            .reset_index()
        )
        grouped.insert(0, "label", label)
        rows.extend(grouped.to_dict("records"))
    return pd.DataFrame(rows)


def _plot(summary: pd.DataFrame, complements: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(18, 11), constrained_layout=True)

    top = summary.head(12).copy()
    ax = axes[0, 0]
    ax.barh(top["label"][::-1], top["realized_pnl"][::-1], color="#2563eb")
    ax.set_title("Stage032 Label Realized PnL")
    ax.set_xlabel("realized pnl")
    ax.grid(True, axis="x", alpha=0.25)

    ax = axes[0, 1]
    ax.scatter(summary["lot_rows"], summary["avg_pnl_per_lot"], s=80, color="#f97316")
    for _, row in summary.head(8).iterrows():
        ax.annotate(str(row["label"]).replace("label_", ""), (row["lot_rows"], row["avg_pnl_per_lot"]), fontsize=8)
    ax.set_title("Density vs Coverage")
    ax.set_xlabel("lot rows")
    ax.set_ylabel("avg pnl per lot")
    ax.grid(True, alpha=0.25)

    ax = axes[1, 0]
    pivot = complements[complements["label"].isin(KEY_LABELS[:5])].pivot(
        index="label", columns="side", values="realized_pnl"
    )
    pivot = pivot.reindex([label for label in KEY_LABELS[:5] if label in pivot.index])
    x = np.arange(len(pivot))
    width = 0.35
    ax.bar(x - width / 2, pivot.get("selected", pd.Series(0, index=pivot.index)), width, label="selected")
    ax.bar(x + width / 2, pivot.get("not_selected", pd.Series(0, index=pivot.index)), width, label="not_selected")
    ax.set_xticks(x)
    ax.set_xticklabels(pivot.index, rotation=35, ha="right", fontsize=8)
    ax.set_title("Selected vs Not Selected PnL")
    ax.legend()
    ax.grid(True, axis="y", alpha=0.25)

    ax = axes[1, 1]
    stable = summary.head(12).copy()
    ax.bar(stable["label"], stable["source_positive_rate_pct"], color="#16a34a")
    ax.set_ylim(0, 105)
    ax.set_title("Source Positive Rate")
    ax.set_ylabel("%")
    ax.tick_params(axis="x", rotation=45, labelsize=8)
    ax.grid(True, axis="y", alpha=0.25)

    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _decision(frame: pd.DataFrame, summary: pd.DataFrame, complements: pd.DataFrame) -> dict[str, Any]:
    base_pnl = float(frame["realized_pnl"].sum())
    base_events = int(frame["event_key"].nunique())
    base_lots = int(len(frame))

    def metric(label: str, column: str) -> float:
        rows = summary[summary["label"].eq(label)]
        if rows.empty:
            return 0.0
        return float(rows.iloc[0][column])

    entry_or_first_pnl = metric("tag_entry_or_first_aligned", "realized_pnl")
    entry_or_first_lots = int(metric("tag_entry_or_first_aligned", "lot_rows"))
    entry_or_first_source_rate = metric("tag_entry_or_first_aligned", "source_positive_rate_pct")
    core_pnl = metric("label_rank_1_9_and_entry_or_first_aligned", "realized_pnl")
    core_lots = int(metric("label_rank_1_9_and_entry_or_first_aligned", "lot_rows"))
    preentry_pnl = metric("label_preentry_core", "realized_pnl")
    oi_pnl = metric("oi_price_confirm_passed", "realized_pnl")
    consensus_lots = int(metric("stage032_consensus_top8_full_market", "lot_rows"))
    consensus_years = int(metric("stage032_consensus_top8_full_market", "year_count"))
    consensus_pnl = metric("stage032_consensus_top8_full_market", "realized_pnl")

    conclusion = (
        "Stage032 找到强开仓日早段质量证据：entry_or_first_aligned 只覆盖约半数 lot，却几乎覆盖全部 Stage031 恢复右尾。"
        "但纯入场前标签没有达标：OI confirm 明显为负，full-market consensus 密度高但样本少且年份集中；"
        "因此本阶段不生成真实引擎候选，只允许下一步验证“开仓后早段确认再加风险”的真实路径。"
    )
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "decision": "stage032_early_quality_right_tail_found_preentry_failed_no_engine_candidate",
        "conclusion": conclusion,
        "external_research_judgment": EXTERNAL_RESEARCH_JUDGMENT,
        "overfit_reflection_before": OVERFIT_REFLECTION_BEFORE,
        "continue_value_before": CONTINUE_VALUE_BEFORE,
        "overfit_reflection_after": (
            "否。Stage032 没有按结果写交易规则；但若把 lc/SM/2024-2025 或 consensus 的小样本直接交易化，会明显过拟合。"
        ),
        "continue_value_after": (
            "有。开仓日早段质量标签足够强，值得写一个冻结真实引擎验证；纯入场前 OI/consensus 路线暂不值得晋级。"
        ),
        "metrics": {
            "base_lot_rows": base_lots,
            "base_event_count": base_events,
            "base_realized_pnl": base_pnl,
            "entry_or_first_aligned_lot_rows": entry_or_first_lots,
            "entry_or_first_aligned_pnl": entry_or_first_pnl,
            "entry_or_first_aligned_pnl_share": entry_or_first_pnl / base_pnl if base_pnl else np.nan,
            "entry_or_first_aligned_source_positive_rate_pct": entry_or_first_source_rate,
            "rank_1_9_entry_or_first_lot_rows": core_lots,
            "rank_1_9_entry_or_first_pnl": core_pnl,
            "rank_1_9_entry_or_first_pnl_share": core_pnl / base_pnl if base_pnl else np.nan,
            "preentry_core_pnl": preentry_pnl,
            "oi_confirm_pnl": oi_pnl,
            "consensus_top8_lot_rows": consensus_lots,
            "consensus_top8_year_count": consensus_years,
            "consensus_top8_pnl": consensus_pnl,
        },
        "outputs": {
            "lot_labels": str(LOT_LABELS_PATH),
            "label_summary": str(LABEL_SUMMARY_PATH),
            "label_complement_summary": str(LABEL_COMPLEMENT_PATH),
            "key_source_summary": str(KEY_SOURCE_SUMMARY_PATH),
            "key_year_summary": str(KEY_YEAR_SUMMARY_PATH),
            "key_product_summary": str(KEY_PRODUCT_SUMMARY_PATH),
            "chart": str(CHART_PATH),
            "report": str(REPORT_PATH),
            "decision": str(DECISION_PATH),
        },
    }


def _write_report(
    decision: dict[str, Any],
    summary: pd.DataFrame,
    complements: pd.DataFrame,
    source_summary: pd.DataFrame,
    year_summary: pd.DataFrame,
    product_summary: pd.DataFrame,
) -> None:
    metrics = decision["metrics"]
    lines = [
        "# Stage032 恢复段高质量标签只读审计",
        "",
        f"- 生成时间：`{decision['generated_at']}`",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        "- 阶段性质：只读审计；不生成真实引擎候选、不改官方 live config、不连接 CTP、不调用下单。",
        f"- 复用 Stage031 滞后匹配窗口：`0-{MAX_MATCH_LAG_DAYS}` 自然日。",
        "",
        "## 外部调研判断",
        "",
        f"- {EXTERNAL_RESEARCH_JUDGMENT}",
        "",
        "## 核心结论",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 结论：{decision['conclusion']}",
        f"- Stage031 恢复集合 lot/event/PNL：`{metrics['base_lot_rows']}` / `{metrics['base_event_count']}` / `{metrics['base_realized_pnl']:.2f}`。",
        f"- `tag_entry_or_first_aligned` lot/PNL/PNL占比/source正率：`{metrics['entry_or_first_aligned_lot_rows']}` / `{metrics['entry_or_first_aligned_pnl']:.2f}` / `{metrics['entry_or_first_aligned_pnl_share']:.4f}` / `{metrics['entry_or_first_aligned_source_positive_rate_pct']:.2f}%`。",
        f"- `rank_1_9_and_entry_or_first` lot/PNL/PNL占比：`{metrics['rank_1_9_entry_or_first_lot_rows']}` / `{metrics['rank_1_9_entry_or_first_pnl']:.2f}` / `{metrics['rank_1_9_entry_or_first_pnl_share']:.4f}`。",
        f"- 纯入场前 `preentry_core` PNL：`{metrics['preentry_core_pnl']:.2f}`；`OI confirm` PNL：`{metrics['oi_confirm_pnl']:.2f}`。",
        f"- full-market consensus top8 lot/year/PNL：`{metrics['consensus_top8_lot_rows']}` / `{metrics['consensus_top8_year_count']}` / `{metrics['consensus_top8_pnl']:.2f}`。",
        "",
        "## 标签总表",
        "",
        _md_table(summary, max_rows=30),
        "",
        "## 选中/未选中对比",
        "",
        _md_table(complements, max_rows=40),
        "",
        "## Key Source 稳定性",
        "",
        _md_table(
            source_summary[source_summary["label"].isin(KEY_LABELS[:4])].sort_values(
                ["label", "realized_pnl"], ascending=[True, False]
            ),
            max_rows=80,
        ),
        "",
        "## Key Year 稳定性",
        "",
        _md_table(year_summary.sort_values(["label", "entry_year"]), max_rows=80),
        "",
        "## Key Product Top",
        "",
        _md_table(product_summary.sort_values(["label", "realized_pnl"], ascending=[True, False]).head(80)),
        "",
        "## 判断",
        "",
        f"- 过拟合反思：{decision['overfit_reflection_after']}",
        f"- 继续价值反思：{decision['continue_value_after']}",
        "- 下一步：只允许冻结一个“开仓日早段确认后加风险”的真实引擎验证；不得按产品、月份、年份或 consensus 小样本直接写豁免。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_stage_record(decision: dict[str, Any]) -> Path:
    metrics = decision["metrics"]
    path = STAGE_RECORD_DIR / "20260701_1732_stage032_recovery_quality_label_audit.md"
    lines = [
        "# Stage032 - 恢复段高质量标签只读审计",
        "",
        f"- 时间：`{decision['generated_at']}`",
        "- 是否重要突破版本：否；这是只读审计，不是候选策略。",
        "- 新增参数：无。",
        "- 修改参数：无。",
        "- 删除参数：无。",
        "- 新增回测结果：无新增真实回测；复用 Stage006/007/021/030/031 产物做标签归因。",
        "- 修改回测结果：无。",
        "- 删除回测结果：无。",
        f"- Stage031 恢复集合 lot/event/PNL：`{metrics['base_lot_rows']}` / `{metrics['base_event_count']}` / `{metrics['base_realized_pnl']:.2f}`。",
        f"- `tag_entry_or_first_aligned` lot/PNL/PNL占比/source正率：`{metrics['entry_or_first_aligned_lot_rows']}` / `{metrics['entry_or_first_aligned_pnl']:.2f}` / `{metrics['entry_or_first_aligned_pnl_share']:.4f}` / `{metrics['entry_or_first_aligned_source_positive_rate_pct']:.2f}%`。",
        f"- `rank_1_9_and_entry_or_first` lot/PNL/PNL占比：`{metrics['rank_1_9_entry_or_first_lot_rows']}` / `{metrics['rank_1_9_entry_or_first_pnl']:.2f}` / `{metrics['rank_1_9_entry_or_first_pnl_share']:.4f}`。",
        f"- 纯入场前 `preentry_core` PNL：`{metrics['preentry_core_pnl']:.2f}`；`OI confirm` PNL：`{metrics['oi_confirm_pnl']:.2f}`。",
        f"- full-market consensus top8 lot/year/PNL：`{metrics['consensus_top8_lot_rows']}` / `{metrics['consensus_top8_year_count']}` / `{metrics['consensus_top8_pnl']:.2f}`。",
        "- 胜率：不新增策略胜率；详见 label_summary。",
        f"- 过拟合反思：{decision['overfit_reflection_after']}",
        f"- 继续价值反思：{decision['continue_value_after']}",
        "- 后续规划：冻结验证开仓日早段确认后加风险真实引擎；不得按产品/日期/年份/small consensus 样本交易化。",
        "",
        "## 输出",
        "",
        f"- 报告：`{REPORT_PATH}`",
        f"- 决策：`{DECISION_PATH}`",
        f"- 图表：`{CHART_PATH}`",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _append_back_log(decision: dict[str, Any], stage_record: Path) -> None:
    marker = "`futures_trend_rebuilt_c9_15w_optimization` Stage032"
    existing = BACK_LOG_PATH.read_text(encoding="utf-8") if BACK_LOG_PATH.exists() else ""
    if marker in existing:
        return
    metrics = decision["metrics"]
    line = (
        f"\n{decision['generated_at'].replace('T', ' ')} CST：`futures_trend_rebuilt_c9_15w_optimization` "
        "Stage032 完成 Stage031 恢复段高质量标签只读审计，决策 "
        f"`{decision['decision']}`。本阶段只读复用 Stage006/007/021/030/031 产物，不改正式配置、不连接 CTP、不调用订单 API。"
        f"Stage031 恢复集合 lot/event/PNL 为 `{metrics['base_lot_rows']}` / `{metrics['base_event_count']}` / `{metrics['base_realized_pnl']:.2f}`；"
        f"`tag_entry_or_first_aligned` 覆盖 `{metrics['entry_or_first_aligned_lot_rows']}` 笔、PNL `{metrics['entry_or_first_aligned_pnl']:.2f}`、"
        f"PNL占比 `{metrics['entry_or_first_aligned_pnl_share']:.4f}`、source正率 `{metrics['entry_or_first_aligned_source_positive_rate_pct']:.2f}%`；"
        f"`rank_1_9_and_entry_or_first` PNL `{metrics['rank_1_9_entry_or_first_pnl']:.2f}`；"
        f"纯入场前 `preentry_core` PNL `{metrics['preentry_core_pnl']:.2f}`、`OI confirm` PNL `{metrics['oi_confirm_pnl']:.2f}`。"
        "结论：开仓日早段质量标签很强，但纯入场前标签失败或样本不足；下一步只允许冻结验证“开仓日早段确认后加风险”真实引擎，不能按产品/日期/小样本 consensus 交易化。"
        f"记录 `{stage_record}`，报告 `{REPORT_PATH}`。\n"
    )
    with BACK_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(line)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGE_RECORD_DIR.mkdir(parents=True, exist_ok=True)

    lot_labels = _label_lots()
    summary = _label_summary(lot_labels)
    complements = _label_complements(
        lot_labels,
        [
            "label_candidate_ai_rank_1_9",
            "tag_entry_or_first_aligned",
            "label_rank_1_9_and_entry_or_first_aligned",
            "label_preentry_core",
            "stage032_consensus_top8_full_market",
        ],
    )
    source_summary = _key_breakdown(lot_labels, "requested_start_month", KEY_LABELS)
    year_summary = _key_breakdown(lot_labels, "entry_year", KEY_LABELS)
    product_summary = _key_breakdown(lot_labels, "product_vt_symbol", KEY_LABELS)
    decision = _decision(lot_labels, summary, complements)

    lot_labels.to_csv(LOT_LABELS_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(LABEL_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    complements.to_csv(LABEL_COMPLEMENT_PATH, index=False, encoding="utf-8-sig")
    source_summary.to_csv(KEY_SOURCE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    year_summary.to_csv(KEY_YEAR_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    product_summary.to_csv(KEY_PRODUCT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _plot(summary, complements)
    _write_report(decision, summary, complements, source_summary, year_summary, product_summary)
    stage_record = _write_stage_record(decision)
    _append_back_log(decision, stage_record)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
