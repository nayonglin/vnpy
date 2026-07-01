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
PORTFOLIO_DIR = PROJECT_DIR / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

import analyze_qmt_roll_stage167_c9_live_15w_multiperiod_ai_audit as s167
import analyze_qmt_roll_stage719_official_winner_trade_forensics as s719
import analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow as s901
from qmt_roll_official_live_config import (
    OFFICIAL_LIVE_ALIAS,
    OFFICIAL_LIVE_CAPITAL,
    OFFICIAL_LIVE_PROFILE_NAME,
    OFFICIAL_LIVE_VERSION,
)


LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage006"
MODEL_TAG = "stage006_current_quality_feature_binder_v1"
OUTPUT_PREFIX = "rebuilt_c9_stage006_current_quality_feature_binder"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage006_current_quality_feature_binder"
BT_OUTPUT_DIR = PORTFOLIO_DIR / "backtest_outputs"

REQUESTED_START = pd.Timestamp("2018-01-01")
REQUESTED_END = pd.Timestamp("2026-06-30")

MINUTE_BARS_PATH = (
    BT_OUTPUT_DIR
    / "qmt_roll_stage861_stage860_full_visual_atlas_full_minute_bars_"
    "stage861_stage860_full_visual_atlas_v1.csv"
)

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
ENTRY_CANDIDATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidates_{MODEL_TAG}.csv"
TRADES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{MODEL_TAG}.csv"
ENTRY_RISK_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_{MODEL_TAG}.csv"
TRADE_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_events_{MODEL_TAG}.csv"
INTRADAY_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_intraday_events_{MODEL_TAG}.csv"
CLOSED_LOTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_closed_lots_{MODEL_TAG}.csv"
QUALITY_FEATURES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_quality_features_{MODEL_TAG}.csv"
QUALITY_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_quality_summary_{MODEL_TAG}.csv"
ANNUAL_QUALITY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_quality_{MODEL_TAG}.csv"
ABSOLUTE_EQUITY_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_absolute_equity_chart_{MODEL_TAG}.png"
QUALITY_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_quality_chart_{MODEL_TAG}.png"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _json_safe(value: Any) -> Any:
    return s167._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s167._md_table(frame, max_rows=max_rows)


def _date_text(value: Any) -> str:
    return pd.Timestamp(value).date().isoformat()


def _start_month_text(value: Any) -> str:
    return pd.Timestamp(value).strftime("%Y-%m")


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if np.isfinite(number) else default


def _direction_sign(direction: Any) -> float:
    return 1.0 if str(direction) == "long" else -1.0


def _bucket_rank(value: Any) -> str:
    rank = _safe_float(value)
    if np.isnan(rank) or rank <= 0:
        return "missing"
    if rank <= 3:
        return "rank_1_3"
    if rank <= 6:
        return "rank_4_6"
    if rank <= 9:
        return "rank_7_9"
    return "rank_gt9"


def _relation_bucket(value: Any, prefix: str) -> str:
    number = _safe_float(value)
    if np.isnan(number):
        return f"{prefix}_missing"
    if number > 0:
        return f"{prefix}_aligned"
    if number < 0:
        return f"{prefix}_adverse"
    return f"{prefix}_flat"


def _body_bucket(value: Any) -> str:
    number = _safe_float(value)
    if np.isnan(number):
        return "first_body_missing"
    if number > 0:
        return "first_body_aligned"
    if number < 0:
        return "first_body_adverse"
    return "first_body_flat"


def _adverse_wick_bucket(value: Any) -> str:
    number = _safe_float(value)
    if np.isnan(number):
        return "first_adverse_wick_missing"
    return "first_adverse_wick_present" if number > 0 else "first_adverse_wick_none"


def _frame_with_run_columns(frame: pd.DataFrame, start: pd.Timestamp) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    result = frame.copy()
    result["stage"] = STAGE
    result["model_tag"] = MODEL_TAG
    result["line_id"] = LINE_ID
    result["official_live_version"] = OFFICIAL_LIVE_VERSION
    result["official_live_alias"] = OFFICIAL_LIVE_ALIAS
    result["requested_start"] = _date_text(start)
    result["requested_start_month"] = _start_month_text(start)
    result["requested_end"] = _date_text(REQUESTED_END)
    return result


def _run_rebuilt_multistart() -> dict[str, pd.DataFrame]:
    metadata = s901.s513._metadata()
    starts = s167._build_start_dates()
    summary_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    candidate_frames: list[pd.DataFrame] = []
    trade_frames: list[pd.DataFrame] = []
    entry_risk_frames: list[pd.DataFrame] = []
    trade_event_frames: list[pd.DataFrame] = []
    intraday_event_frames: list[pd.DataFrame] = []
    closed_lot_frames: list[pd.DataFrame] = []

    for idx, start in enumerate(starts, start=1):
        print(f"[stage006] running {idx}/{len(starts)} start={_date_text(start)}", flush=True)
        combined, frames, _spec = s901._run_live_c9(metadata, start, REQUESTED_END)

        curve = combined.copy()
        curve["stage"] = STAGE
        curve["model_tag"] = MODEL_TAG
        curve["line_id"] = LINE_ID
        curve["official_live_version"] = OFFICIAL_LIVE_VERSION
        curve["official_live_alias"] = OFFICIAL_LIVE_ALIAS
        curve["requested_start"] = _date_text(start)
        curve["requested_start_month"] = _start_month_text(start)
        curve["requested_end"] = _date_text(REQUESTED_END)
        curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
        curve = curve.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
        curve["nav"] = pd.to_numeric(curve["account_equity"], errors="coerce") / float(OFFICIAL_LIVE_CAPITAL)
        curve["absolute_equity"] = pd.to_numeric(curve["account_equity"], errors="coerce")
        curve["drawdown_pct"] = s167._drawdown_pct(pd.to_numeric(curve["account_equity"], errors="coerce"))
        curve["days_since_start"] = np.arange(len(curve), dtype=int)
        curve_frames.append(curve)
        summary_rows.append(s167._summarize_curve(curve, start))

        candidates = _frame_with_run_columns(frames.get("entry_candidates", pd.DataFrame()), start)
        trades = _frame_with_run_columns(frames.get("trades", pd.DataFrame()), start)
        entry_risk = _frame_with_run_columns(frames.get("entry_risk", pd.DataFrame()), start)
        trade_events = _frame_with_run_columns(frames.get("trade_events", pd.DataFrame()), start)
        intraday_events = _frame_with_run_columns(frames.get("intraday_events", pd.DataFrame()), start)

        if not candidates.empty:
            candidate_frames.append(candidates)
        if not trades.empty:
            trade_frames.append(trades)
        if not entry_risk.empty:
            entry_risk_frames.append(entry_risk)
        if not trade_events.empty:
            trade_event_frames.append(trade_events)
        if not intraday_events.empty:
            intraday_event_frames.append(intraday_events)

        closed = s719._build_closed_lots(
            frames.get("trades", pd.DataFrame()),
            frames.get("entry_risk", pd.DataFrame()),
            frames.get("entry_candidates", pd.DataFrame()),
            metadata,
        )
        closed = _frame_with_run_columns(closed, start)
        if not closed.empty:
            closed_lot_frames.append(closed)

    summary = pd.DataFrame(summary_rows).sort_values("requested_start").reset_index(drop=True)
    return {
        "summary": summary,
        "curves": pd.concat(curve_frames, ignore_index=True, sort=False) if curve_frames else pd.DataFrame(),
        "entry_candidates": pd.concat(candidate_frames, ignore_index=True, sort=False) if candidate_frames else pd.DataFrame(),
        "trades": pd.concat(trade_frames, ignore_index=True, sort=False) if trade_frames else pd.DataFrame(),
        "entry_risk": pd.concat(entry_risk_frames, ignore_index=True, sort=False) if entry_risk_frames else pd.DataFrame(),
        "trade_events": pd.concat(trade_event_frames, ignore_index=True, sort=False) if trade_event_frames else pd.DataFrame(),
        "intraday_events": (
            pd.concat(intraday_event_frames, ignore_index=True, sort=False) if intraday_event_frames else pd.DataFrame()
        ),
        "closed_lots": pd.concat(closed_lot_frames, ignore_index=True, sort=False) if closed_lot_frames else pd.DataFrame(),
    }


def _load_first_minute_lookup(closed_lots: pd.DataFrame) -> pd.DataFrame:
    needed = closed_lots[["vt_symbol", "entry_date"]].copy()
    needed["entry_date"] = pd.to_datetime(needed["entry_date"], errors="coerce").dt.date.astype(str)
    needed = needed.dropna().drop_duplicates()
    if needed.empty:
        return pd.DataFrame()

    bars = pd.read_csv(
        MINUTE_BARS_PATH,
        encoding="utf-8-sig",
        usecols=[
            "vt_symbol",
            "bar_datetime",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "open_oi",
            "close_oi",
            "bar_date",
            "minute_source",
        ],
    )
    bars["bar_date"] = bars["bar_date"].astype(str)
    bars = bars.merge(needed.rename(columns={"entry_date": "bar_date"}), on=["vt_symbol", "bar_date"], how="inner")
    if bars.empty:
        return bars
    bars["bar_datetime"] = pd.to_datetime(bars["bar_datetime"], errors="coerce")
    bars = bars.dropna(subset=["bar_datetime"]).sort_values(["vt_symbol", "bar_date", "bar_datetime"])
    first = bars.groupby(["vt_symbol", "bar_date"], as_index=False).first()
    first.rename(
        columns={
            "bar_date": "entry_date_key",
            "bar_datetime": "entry_first_bar_time",
            "open": "first_open",
            "high": "first_high",
            "low": "first_low",
            "close": "first_close",
            "volume": "first_volume",
            "open_oi": "first_open_oi",
            "close_oi": "first_close_oi",
            "minute_source": "first_minute_source",
        },
        inplace=True,
    )
    return first


def _build_quality_features(closed_lots: pd.DataFrame) -> pd.DataFrame:
    if closed_lots.empty:
        return pd.DataFrame()
    features = closed_lots.copy()
    features["entry_date"] = pd.to_datetime(features["entry_date"], errors="coerce").dt.normalize()
    features["entry_date_key"] = features["entry_date"].dt.date.astype(str)
    first = _load_first_minute_lookup(features)
    features = features.merge(first, on=["vt_symbol", "entry_date_key"], how="left")

    for column in [
        "entry_price",
        "risk_amount",
        "volume",
        "size",
        "first_open",
        "first_high",
        "first_low",
        "first_close",
        "first_open_oi",
        "first_close_oi",
        "ai_product_pool_rank",
        "realized_pnl",
        "r_multiple",
    ]:
        if column in features.columns:
            features[column] = pd.to_numeric(features[column], errors="coerce")

    risk_price_distance = features["risk_amount"] / (features["volume"] * features["size"]).replace(0.0, np.nan)
    stop_distance = pd.to_numeric(features.get("stop_distance", np.nan), errors="coerce")
    features["planned_stop_distance_price"] = stop_distance.where(stop_distance.gt(0), risk_price_distance)
    features["direction_sign"] = features["direction"].map(_direction_sign)
    sign = features["direction_sign"]
    risk = features["planned_stop_distance_price"].replace(0.0, np.nan)
    entry = features["entry_price"]

    features["entry_open_gap_r"] = sign * (features["first_open"] - entry) / risk
    features["first_bar_directional_r"] = sign * (features["first_close"] - entry) / risk
    features["first_bar_body_directional_r"] = sign * (features["first_close"] - features["first_open"]) / risk
    long_mfe = features["first_high"] - entry
    short_mfe = entry - features["first_low"]
    long_mae = entry - features["first_low"]
    short_mae = features["first_high"] - entry
    features["first_bar_mfe_r"] = np.where(features["direction"].astype(str).eq("long"), long_mfe, short_mfe) / risk
    features["first_bar_mae_r"] = np.where(features["direction"].astype(str).eq("long"), long_mae, short_mae) / risk
    features["first_bar_oi_change"] = features["first_close_oi"] - features["first_open_oi"]

    features["entry_open_relation_bucket"] = features["entry_open_gap_r"].map(
        lambda value: _relation_bucket(value, "entry_open")
    )
    features["first_bar_relation_bucket"] = features["first_bar_directional_r"].map(
        lambda value: _relation_bucket(value, "first_bar")
    )
    features["first_bar_body_bucket"] = features["first_bar_body_directional_r"].map(_body_bucket)
    features["first_bar_adverse_wick_bucket"] = features["first_bar_mae_r"].map(_adverse_wick_bucket)
    features["ai_rank_bucket"] = features["ai_product_pool_rank"].map(_bucket_rank)

    features["tag_entry_open_aligned"] = features["entry_open_relation_bucket"].eq("entry_open_aligned")
    features["tag_first_bar_aligned"] = features["first_bar_relation_bucket"].eq("first_bar_aligned")
    features["tag_entry_or_first_aligned"] = features["tag_entry_open_aligned"] | features["tag_first_bar_aligned"]
    features["tag_entry_and_first_aligned"] = features["tag_entry_open_aligned"] & features["tag_first_bar_aligned"]
    ai4_6 = features["ai_rank_bucket"].eq("rank_4_6")
    features["tag_ai4_6_entry_open_aligned"] = ai4_6 & features["tag_entry_open_aligned"]
    features["tag_ai4_6_first_bar_aligned"] = ai4_6 & features["tag_first_bar_aligned"]
    features["tag_ai4_6_entry_or_first_aligned"] = ai4_6 & features["tag_entry_or_first_aligned"]
    features["tag_ai4_6_entry_and_first_aligned"] = ai4_6 & features["tag_entry_and_first_aligned"]
    features["tag_ai4_6_not_aligned"] = ai4_6 & ~features["tag_entry_or_first_aligned"]
    features["tag_aligned_not_ai4_6"] = ~ai4_6 & features["tag_entry_or_first_aligned"]
    features["tag_not_ai4_6_or_not_aligned"] = ~features["tag_ai4_6_entry_or_first_aligned"]
    features["entry_first_bar_available"] = features["entry_first_bar_time"].notna()
    features["winner"] = features["realized_pnl"].gt(0.0).astype(int)
    features["entry_year"] = features["entry_date"].dt.year
    return features.sort_values(["requested_start_month", "entry_date", "lot_id"]).reset_index(drop=True)


def _quality_summary(features: pd.DataFrame) -> pd.DataFrame:
    if features.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    masks = {
        "all_closed_lots": pd.Series(True, index=features.index),
        "entry_open_aligned": features["tag_entry_open_aligned"],
        "first_bar_aligned": features["tag_first_bar_aligned"],
        "entry_or_first_aligned": features["tag_entry_or_first_aligned"],
        "ai_rank_4_6": features["ai_rank_bucket"].eq("rank_4_6"),
        "ai4_6_entry_or_first_aligned": features["tag_ai4_6_entry_or_first_aligned"],
        "ai4_6_not_aligned": features["tag_ai4_6_not_aligned"],
        "aligned_not_ai4_6": features["tag_aligned_not_ai4_6"],
        "missing_first_bar": ~features["entry_first_bar_available"],
    }
    total_pnl = float(features["realized_pnl"].sum())
    total_positive = float(features.loc[features["realized_pnl"].gt(0), "realized_pnl"].sum())
    total_negative_abs = abs(float(features.loc[features["realized_pnl"].lt(0), "realized_pnl"].sum()))
    for bucket, mask in masks.items():
        subset = features[mask.fillna(False)].copy()
        positive = float(subset.loc[subset["realized_pnl"].gt(0), "realized_pnl"].sum()) if len(subset) else 0.0
        negative_abs = abs(float(subset.loc[subset["realized_pnl"].lt(0), "realized_pnl"].sum())) if len(subset) else 0.0
        yearly = subset.groupby("entry_year", dropna=True)["realized_pnl"].sum() if len(subset) else pd.Series(dtype=float)
        rows.append(
            {
                "bucket": bucket,
                "lot_count": int(len(subset)),
                "product_count": int(subset["product"].nunique()) if "product" in subset.columns else 0,
                "year_count": int(subset["entry_year"].nunique()) if "entry_year" in subset.columns else 0,
                "pnl_sum": float(subset["realized_pnl"].sum()) if len(subset) else 0.0,
                "pnl_share_pct": float(subset["realized_pnl"].sum() / total_pnl * 100.0) if total_pnl else np.nan,
                "positive_pnl_share_pct": float(positive / total_positive * 100.0) if total_positive else np.nan,
                "negative_abs_share_pct": float(negative_abs / total_negative_abs * 100.0) if total_negative_abs else np.nan,
                "win_rate_pct": float(subset["winner"].mean() * 100.0) if len(subset) else np.nan,
                "median_r": float(subset["r_multiple"].median()) if len(subset) else np.nan,
                "positive_year_count": int(yearly.gt(0).sum()) if len(yearly) else 0,
                "negative_year_count": int(yearly.lt(0).sum()) if len(yearly) else 0,
            }
        )
    return pd.DataFrame(rows)


def _annual_quality(features: pd.DataFrame) -> pd.DataFrame:
    if features.empty:
        return pd.DataFrame()
    rows: list[pd.DataFrame] = []
    for bucket in [
        "tag_entry_or_first_aligned",
        "tag_ai4_6_entry_or_first_aligned",
        "tag_ai4_6_not_aligned",
        "tag_not_ai4_6_or_not_aligned",
    ]:
        grouped = (
            features.groupby(["requested_start_month", "entry_year"], dropna=False)
            .agg(
                lot_count=("lot_id", "count"),
                bucket_count=(bucket, "sum"),
                total_pnl=("realized_pnl", "sum"),
                bucket_pnl=("realized_pnl", lambda s, bucket=bucket: float(s[features.loc[s.index, bucket].fillna(False)].sum())),
            )
            .reset_index()
        )
        grouped["bucket"] = bucket
        rows.append(grouped)
    return pd.concat(rows, ignore_index=True, sort=False) if rows else pd.DataFrame()


def _plot_absolute_equity(curves: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(18, 9), constrained_layout=True)
    for start, group in curves.groupby("requested_start_month"):
        group = group.sort_values("date")
        ax.plot(group["date"], group["absolute_equity"], linewidth=0.95, alpha=0.78, label=str(start))
    ax.axhline(OFFICIAL_LIVE_CAPITAL, color="#111827", linestyle="--", linewidth=0.9, label="initial 150k")
    ax.set_title("Stage006 Rebuilt C9/15w Absolute Account Equity By Cold Start")
    ax.set_xlabel("date")
    ax.set_ylabel("account equity")
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=7, ncol=3, loc="best")
    fig.savefig(ABSOLUTE_EQUITY_CHART_PATH, dpi=160)
    plt.close(fig)


def _plot_quality(summary: pd.DataFrame) -> None:
    plot = summary.copy()
    fig, axes = plt.subplots(1, 2, figsize=(18, 7), constrained_layout=True)
    ax = axes[0]
    x = np.arange(len(plot))
    ax.bar(x, plot["pnl_sum"], color=np.where(plot["pnl_sum"].ge(0), "#2563eb", "#dc2626"))
    ax.set_xticks(x)
    ax.set_xticklabels(plot["bucket"], rotation=45, ha="right")
    ax.set_title("Closed-Lot PnL By Read-Only Quality Bucket")
    ax.set_ylabel("realized pnl")
    ax.grid(True, axis="y", alpha=0.25)

    ax = axes[1]
    ax.bar(x, plot["lot_count"], color="#16a34a")
    ax.set_xticks(x)
    ax.set_xticklabels(plot["bucket"], rotation=45, ha="right")
    ax.set_title("Closed-Lot Count By Bucket")
    ax.set_ylabel("lots")
    ax.grid(True, axis="y", alpha=0.25)
    fig.savefig(QUALITY_CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    quality_summary: pd.DataFrame,
    features: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    coverage = {
        "closed_lots": int(len(features)),
        "entry_first_bar_available": int(features["entry_first_bar_available"].sum()) if not features.empty else 0,
        "entry_first_bar_missing": int((~features["entry_first_bar_available"]).sum()) if not features.empty else 0,
        "coverage_pct": float(features["entry_first_bar_available"].mean() * 100.0) if len(features) else 0.0,
    }
    lines = [
        f"# {STAGE} 当前重建版质量特征绑定器",
        "",
        f"- 生成时间：`{decision['generated_at']}`",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 线上版本：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_PROFILE_NAME}`",
        f"- 回测区间：`{REQUESTED_START.date()}` 到 `{REQUESTED_END.date()}`；起点为每年 `01-01/07-01`。",
        "- 阶段性质：只读重跑保存 frames，不改策略参数、不连接 CTP、不调用下单 API。",
        "",
        "## 外部调研判断",
        "",
        "- Deflated Sharpe Ratio / PBO 框架提示：多次回测和多候选会制造样本内虚假发现，本阶段只做固定口径数据闭环，不根据结果筛参数。",
        "- Hurst/Ooi/Pedersen 长期趋势跟随研究提示：趋势策略价值在跨市场右尾和分散化；质量标签只能先证明稳定性，不能直接砍右尾。",
        "- Meta-labeling/triple-barrier 思路可作为“主信号不变、二级质量标签只调仓位”的方向参考；但本阶段尚未写 meta-rule。",
        "",
        "## 多起点基准复跑摘要",
        "",
        _md_table(
            summary[
                [
                    "requested_start_month",
                    "end_equity",
                    "total_return_pct",
                    "max_dd_pct",
                    "sharpe",
                    "total_trade_count",
                    "max_broker10_margin_to_equity_pct",
                ]
            ],
            max_rows=30,
        ),
        "",
        "## 当前质量绑定覆盖",
        "",
        _md_table(pd.DataFrame([coverage]), max_rows=5),
        "",
        "## 质量桶只读统计",
        "",
        _md_table(quality_summary, max_rows=30),
        "",
        "## 图表",
        "",
        f"- 绝对权益资金曲线：`{ABSOLUTE_EQUITY_CHART_PATH}`",
        f"- 质量桶图：`{QUALITY_CHART_PATH}`",
        "",
        "## 判断",
        "",
        f"- 决策：`{decision['decision']}`",
        "- 过拟合反思：否。本阶段只按固定线上版本、固定起点、固定 Stage861 分钟源绑定标签，没有调 AI 池、TopN、R 倍数、品种、年份或方向。",
        "- 继续价值反思：有。现在当前重建版 closed-lot/outcome 与 entry/first-minute 标签已经可审计，下一步才有条件做冻结的非挤占小风险代理或 meta-label 只读验证。",
        "",
        "## 输出文件",
        "",
    ]
    for key, path in decision["outputs"].items():
        lines.append(f"- {key}: `{path}`")
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    frames = _run_rebuilt_multistart()
    summary = frames["summary"]
    curves = frames["curves"]
    closed_lots = frames["closed_lots"]
    features = _build_quality_features(closed_lots)
    qsummary = _quality_summary(features)
    annual_quality = _annual_quality(features)

    _plot_absolute_equity(curves)
    _plot_quality(qsummary)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    frames["entry_candidates"].to_csv(ENTRY_CANDIDATES_PATH, index=False, encoding="utf-8-sig")
    frames["trades"].to_csv(TRADES_PATH, index=False, encoding="utf-8-sig")
    frames["entry_risk"].to_csv(ENTRY_RISK_PATH, index=False, encoding="utf-8-sig")
    frames["trade_events"].to_csv(TRADE_EVENTS_PATH, index=False, encoding="utf-8-sig")
    frames["intraday_events"].to_csv(INTRADAY_EVENTS_PATH, index=False, encoding="utf-8-sig")
    closed_lots.to_csv(CLOSED_LOTS_PATH, index=False, encoding="utf-8-sig")
    features.to_csv(QUALITY_FEATURES_PATH, index=False, encoding="utf-8-sig")
    qsummary.to_csv(QUALITY_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    annual_quality.to_csv(ANNUAL_QUALITY_PATH, index=False, encoding="utf-8-sig")

    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "official_live_profile_name": OFFICIAL_LIVE_PROFILE_NAME,
        "capital": OFFICIAL_LIVE_CAPITAL,
        "requested_start": REQUESTED_START.date().isoformat(),
        "requested_end": REQUESTED_END.date().isoformat(),
        "start_schedule": "Jan 1 and Jul 1 every year",
        "sample_count": int(len(summary)),
        "closed_lots": int(len(closed_lots)),
        "entry_first_bar_available": int(features["entry_first_bar_available"].sum()) if not features.empty else 0,
        "entry_first_bar_coverage_pct": (
            float(features["entry_first_bar_available"].mean() * 100.0) if len(features) else 0.0
        ),
        "decision": "stage006_current_rebuilt_quality_binder_ready_for_readonly_proxy_no_engine_change",
        "strategy_changed": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "external_research_judgment": (
            "Used DSR/PBO and trend-following persistence as guardrails: this stage is data binding, not parameter search. "
            "Meta-labeling is relevant only after current labels are auditable."
        ),
        "overfit_reflection_before": (
            "否。目标是补当前重建版逐笔/分钟标签缺口，不调规则、不筛参数、不按结果挑品种。"
        ),
        "continue_value_before": (
            "是。Stage005 已确认缺 closed-lot/outcome 和 entry/first-minute 标签；不补齐就无法判断后续优化是否可靠。"
        ),
        "overfit_reflection_after": (
            "否。本阶段只读重跑同口径 17 个起点并绑定固定分钟标签，没有修改 C9、AI 池或任何交易阈值。"
        ),
        "continue_value_after": (
            "是。当前重建版质量标签已能和逐笔结果绑定，下一步可做冻结代理或 meta-label 只读验证；仍不能直接上线。"
        ),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "curves": str(CURVES_PATH),
            "entry_candidates": str(ENTRY_CANDIDATES_PATH),
            "trades": str(TRADES_PATH),
            "entry_risk": str(ENTRY_RISK_PATH),
            "trade_events": str(TRADE_EVENTS_PATH),
            "intraday_events": str(INTRADAY_EVENTS_PATH),
            "closed_lots": str(CLOSED_LOTS_PATH),
            "quality_features": str(QUALITY_FEATURES_PATH),
            "quality_summary": str(QUALITY_SUMMARY_PATH),
            "annual_quality": str(ANNUAL_QUALITY_PATH),
            "absolute_equity_chart": str(ABSOLUTE_EQUITY_CHART_PATH),
            "quality_chart": str(QUALITY_CHART_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }
    _write_report(summary, qsummary, features, decision)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print("quality_summary")
    print(qsummary.to_string(index=False))
    print("summary")
    print(
        summary[
            [
                "requested_start_month",
                "end_equity",
                "total_return_pct",
                "max_dd_pct",
                "sharpe",
                "total_trade_count",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
