from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow as s901
from qmt_roll_official_live_config import (
    OFFICIAL_LIVE_AI_ELIGIBILITY_PATH,
    OFFICIAL_LIVE_ALIAS,
    OFFICIAL_LIVE_CAPITAL,
    OFFICIAL_LIVE_PROFILE_NAME,
    OFFICIAL_LIVE_REFERENCE_METRICS,
    OFFICIAL_LIVE_VERSION,
)


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage939"
MODEL_TAG = "stage939_c9_live_15w_stage128_recorded_pool_horizon_compare_v1"
OUTPUT_PREFIX = "qmt_roll_stage939_c9_live_15w_stage128_recorded_pool_horizon_compare"

REQUESTED_START = pd.Timestamp("2020-01-01")
LATEST_COMPLETE_DATA_DATE = pd.Timestamp("2026-06-15")
START_MONTHS = (1, 7)
HORIZONS = (("half_year", 6, "半年"), ("one_year", 12, "一年"))

AI_STRATEGY = "ai_top8_plus_fu_satellite_post_signal_entry_filter"
RECORDED_LATEST_EVAL_DATE = "2026-05-29"
RECORDED_LATEST_POOL = (
    "SA.CZCE",
    "si.GFEX",
    "FG.CZCE",
    "MA.CZCE",
    "OI.CZCE",
    "jm.DCE",
    "AP.CZCE",
    "rb.SHFE",
    "fu.SHFE",
)

RECORDED_STAGE128_STATS: dict[str, dict[str, Any]] = {
    "half_year": {
        "sample_count": 12,
        "positive_count": 11,
        "min_return_pct": -6.8463,
        "median_return_pct": 18.7133,
        "max_return_pct": 149.1644,
    },
    "one_year": {
        "sample_count": 11,
        "positive_count": 11,
        "min_return_pct": 16.6550,
        "median_return_pct": 46.6351,
        "max_return_pct": 641.3979,
    },
}

CURRENT_STAGE936_DETAIL_PATH = (
    OUTPUT_DIR / "qmt_roll_stage936_c9_live_15w_halfyear_start_horizon_returns_detail_"
    "stage936_c9_live_15w_halfyear_start_horizon_returns_v1.csv"
)

FROZEN_POOL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stage128_recorded_latest_pool_{MODEL_TAG}.csv"
DETAIL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_detail_{MODEL_TAG}.csv"
STATS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stats_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _date_text(value: Any) -> str:
    return pd.Timestamp(value).date().isoformat()


def _start_month_text(value: pd.Timestamp) -> str:
    return value.strftime("%Y-%m")


def _build_start_dates() -> list[pd.Timestamp]:
    starts: list[pd.Timestamp] = []
    for year in range(REQUESTED_START.year, LATEST_COMPLETE_DATA_DATE.year + 1):
        for month in START_MONTHS:
            start = pd.Timestamp(year=year, month=month, day=1)
            if REQUESTED_START <= start <= LATEST_COMPLETE_DATA_DATE:
                starts.append(start)
    return starts


def _max_complete_horizon_months(start: pd.Timestamp) -> int:
    complete = [
        months
        for _key, months, _label in HORIZONS
        if start + pd.DateOffset(months=months) <= LATEST_COMPLETE_DATA_DATE
    ]
    return max(complete) if complete else 0


def _horizon_row(curve: pd.DataFrame, target_date: pd.Timestamp) -> pd.Series | None:
    frame = curve.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame[frame["date"].le(target_date.normalize())].dropna(subset=["date"]).sort_values("date")
    if frame.empty:
        return None
    return frame.iloc[-1]


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    values = pd.to_numeric(equity, errors="coerce").ffill()
    peak = values.cummax()
    return (values / peak.replace(0.0, np.nan) - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0) * 100.0


def _detail_for_horizon(
    curve: pd.DataFrame,
    requested_start: pd.Timestamp,
    horizon_key: str,
    horizon_months: int,
    horizon_label: str,
) -> dict[str, Any] | None:
    target_date = requested_start + pd.DateOffset(months=horizon_months)
    if target_date > LATEST_COMPLETE_DATA_DATE:
        return None
    row = _horizon_row(curve, target_date)
    if row is None:
        return None

    dated = curve.copy()
    dated["date"] = pd.to_datetime(dated["date"], errors="coerce").dt.normalize()
    dated = dated[dated["date"].le(pd.Timestamp(row["date"]).normalize())].dropna(subset=["date"])
    equity = pd.to_numeric(dated["account_equity"], errors="coerce")
    drawdown = _drawdown_pct(equity)
    account_capital = float(
        pd.to_numeric(pd.Series([row.get("account_capital", OFFICIAL_LIVE_CAPITAL)]), errors="coerce").iloc[0]
    )
    end_equity = float(pd.to_numeric(pd.Series([row.get("account_equity", np.nan)]), errors="coerce").iloc[0])
    return_pct = (end_equity / account_capital - 1.0) * 100.0
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "official_live_profile_name": OFFICIAL_LIVE_PROFILE_NAME,
        "ai_pool_path": str(FROZEN_POOL_PATH),
        "requested_start": _date_text(requested_start),
        "requested_start_month": _start_month_text(requested_start),
        "actual_start": _date_text(dated["date"].min()),
        "horizon_key": horizon_key,
        "horizon_label": horizon_label,
        "horizon_months": int(horizon_months),
        "target_date": _date_text(target_date),
        "actual_end": _date_text(row["date"]),
        "actual_end_rule": "last_trading_day_on_or_before_calendar_horizon",
        "trading_days": int(len(dated)),
        "account_capital": account_capital,
        "end_equity": end_equity,
        "return_pct": float(return_pct),
        "max_dd_pct_to_horizon": float(drawdown.min()) if len(drawdown) else np.nan,
        "min_equity_to_horizon": float(equity.min()) if len(equity) else np.nan,
        "trade_count_to_horizon": float(pd.to_numeric(dated.get("trade_count", 0.0), errors="coerce").fillna(0.0).sum()),
        "slippage_to_horizon": float(pd.to_numeric(dated.get("slippage", 0.0), errors="coerce").fillna(0.0).sum()),
        "max_broker10_margin_to_equity_pct": float(
            pd.to_numeric(dated.get("broker10_margin_to_equity_pct", 0.0), errors="coerce").fillna(0.0).max()
        ),
    }


def _stats(detail: pd.DataFrame, *, stage_label: str, source: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if detail.empty:
        return pd.DataFrame()
    for horizon_key, group in detail.groupby("horizon_key", sort=False):
        returns = pd.to_numeric(group["return_pct"], errors="coerce")
        min_idx = returns.idxmin()
        max_idx = returns.idxmax()
        rows.append(
            {
                "source": source,
                "stage": stage_label,
                "horizon_key": horizon_key,
                "horizon_label": str(group["horizon_label"].iloc[0]),
                "horizon_months": int(group["horizon_months"].iloc[0]),
                "sample_count": int(len(group)),
                "positive_count": int((returns > 0.0).sum()),
                "min_return_pct": float(returns.min()),
                "median_return_pct": float(returns.median()),
                "max_return_pct": float(returns.max()),
                "min_return_start": str(group.loc[min_idx, "requested_start_month"]),
                "max_return_start": str(group.loc[max_idx, "requested_start_month"]),
                "min_return_actual_end": str(group.loc[min_idx, "actual_end"]),
                "max_return_actual_end": str(group.loc[max_idx, "actual_end"]),
                "worst_max_dd_pct_to_horizon": float(pd.to_numeric(group["max_dd_pct_to_horizon"], errors="coerce").min()),
                "peak_broker10_margin_to_equity_pct": float(
                    pd.to_numeric(group["max_broker10_margin_to_equity_pct"], errors="coerce").max()
                ),
            }
        )
    return pd.DataFrame(rows)


def _build_stage128_recorded_latest_pool() -> pd.DataFrame:
    source = pd.read_csv(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH)
    source["eval_date"] = source["eval_date"].astype(str)
    source["strategy"] = source["strategy"].astype(str)
    source["product_vt_symbol"] = source["product_vt_symbol"].astype(str)

    latest_mask = source["strategy"].eq(AI_STRATEGY) & source["eval_date"].eq(RECORDED_LATEST_EVAL_DATE)
    latest = source[latest_mask].copy()
    by_product = {str(row.product_vt_symbol): row._asdict() for row in latest.itertuples(index=False)}
    score_fallback = {
        "rb.SHFE": 0.504513,
    }

    replacement_rows: list[dict[str, Any]] = []
    for rank, product in enumerate(RECORDED_LATEST_POOL, start=1):
        existing = by_product.get(product, {})
        score = float(existing.get("score", score_fallback.get(product, max(0.0, 0.75 - rank * 0.02))))
        if product == "fu.SHFE":
            score_type = "stage182_live_fixed_fu_satellite"
        elif product in by_product:
            score_type = str(existing.get("score_type") or "stage182_live_monthly_ai_probability")
        else:
            score_type = "stage128_recorded_latest_pool_membership_replay"
        replacement_rows.append(
            {
                "strategy": AI_STRATEGY,
                "score_type": score_type,
                "eval_date": RECORDED_LATEST_EVAL_DATE,
                "product_vt_symbol": product,
                "score": score,
                "score_rank": rank,
                "top_n": len(RECORDED_LATEST_POOL),
            }
        )

    frozen = pd.concat([source[~latest_mask], pd.DataFrame(replacement_rows)], ignore_index=True, sort=False)
    frozen["eval_date_sort"] = pd.to_datetime(frozen["eval_date"], errors="coerce")
    frozen = (
        frozen.sort_values(["strategy", "eval_date_sort", "score_rank", "product_vt_symbol"])
        .drop(columns=["eval_date_sort"])
        .reset_index(drop=True)
    )
    frozen.to_csv(FROZEN_POOL_PATH, index=False, encoding="utf-8-sig")
    return pd.DataFrame(replacement_rows)


def _run_horizons_with_frozen_pool() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list[dict[str, Any]]]:
    metadata = s901.s513._metadata()
    starts = _build_start_dates()
    detail_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    skipped: list[dict[str, Any]] = []

    original_builder = s901.build_official_live_strategy_overrides

    def _stage128_recorded_pool_builder() -> dict[str, Any]:
        overrides = original_builder()
        overrides["ai_product_pool_eligibility_path"] = str(FROZEN_POOL_PATH)
        return overrides

    s901.build_official_live_strategy_overrides = _stage128_recorded_pool_builder
    try:
        for idx, start in enumerate(starts, start=1):
            max_months = _max_complete_horizon_months(start)
            if max_months <= 0:
                skipped.append(
                    {
                        "requested_start": _date_text(start),
                        "reason": "no_complete_half_year_or_one_year_horizon",
                    }
                )
                continue
            run_end = start + pd.DateOffset(months=max_months)
            print(
                f"[stage939] running {idx}/{len(starts)} start={_date_text(start)} "
                f"run_end={_date_text(run_end)} frozen_pool={FROZEN_POOL_PATH.name}",
                flush=True,
            )
            combined, _frames, _spec = s901._run_live_c9(metadata, start, run_end)
            curve = combined.copy()
            curve["stage"] = STAGE
            curve["model_tag"] = MODEL_TAG
            curve["line_id"] = LINE_ID
            curve["official_live_version"] = OFFICIAL_LIVE_VERSION
            curve["official_live_alias"] = OFFICIAL_LIVE_ALIAS
            curve["requested_start"] = _date_text(start)
            curve["requested_start_month"] = _start_month_text(start)
            curve["requested_run_end"] = _date_text(run_end)
            curve["ai_pool_path"] = str(FROZEN_POOL_PATH)
            curve["nav"] = pd.to_numeric(curve["account_equity"], errors="coerce") / float(OFFICIAL_LIVE_CAPITAL)
            curve["drawdown_pct"] = _drawdown_pct(pd.to_numeric(curve["account_equity"], errors="coerce"))
            curve_frames.append(curve)
            for horizon_key, months, label in HORIZONS:
                row = _detail_for_horizon(curve, start, horizon_key, months, label)
                if row is not None:
                    detail_rows.append(row)
    finally:
        s901.build_official_live_strategy_overrides = original_builder

    detail = pd.DataFrame(detail_rows).sort_values(["horizon_months", "requested_start"]).reset_index(drop=True)
    curves = pd.concat(curve_frames, ignore_index=True, sort=False) if curve_frames else pd.DataFrame()
    stats = _stats(detail, stage_label=STAGE, source="stage939_replay_stage128_latest_pool")
    return detail, stats, curves, skipped


def _recorded_stats_frame() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for key, payload in RECORDED_STAGE128_STATS.items():
        rows.append(
            {
                "source": "recorded_stage128_line_md",
                "stage": "Stage128_record",
                "horizon_key": key,
                "horizon_label": "半年" if key == "half_year" else "一年",
                "horizon_months": 6 if key == "half_year" else 12,
                "sample_count": payload["sample_count"],
                "positive_count": payload["positive_count"],
                "min_return_pct": payload["min_return_pct"],
                "median_return_pct": payload["median_return_pct"],
                "max_return_pct": payload["max_return_pct"],
            }
        )
    return pd.DataFrame(rows)


def _current_stage936_stats_frame() -> pd.DataFrame:
    if not CURRENT_STAGE936_DETAIL_PATH.exists():
        return pd.DataFrame()
    detail = pd.read_csv(CURRENT_STAGE936_DETAIL_PATH)
    return _stats(detail, stage_label="Stage936_current_rebuilt", source="current_rebuilt_stage936")


def _build_comparison(replay_stats: pd.DataFrame) -> pd.DataFrame:
    frames = [_recorded_stats_frame(), _current_stage936_stats_frame(), replay_stats]
    combined = pd.concat([frame for frame in frames if not frame.empty], ignore_index=True, sort=False)
    if combined.empty:
        return combined

    recorded = combined[combined["source"].eq("recorded_stage128_line_md")].set_index("horizon_key")
    for metric in ["min_return_pct", "median_return_pct", "max_return_pct"]:
        combined[f"{metric}_delta_vs_stage128_record"] = combined.apply(
            lambda row: float(row[metric]) - float(recorded.loc[row["horizon_key"], metric])
            if row["horizon_key"] in recorded.index and pd.notna(row.get(metric))
            else np.nan,
            axis=1,
        )
    combined["positive_count_delta_vs_stage128_record"] = combined.apply(
        lambda row: int(row["positive_count"]) - int(recorded.loc[row["horizon_key"], "positive_count"])
        if row["horizon_key"] in recorded.index and pd.notna(row.get("positive_count"))
        else np.nan,
        axis=1,
    )
    return combined.sort_values(["horizon_months", "source"]).reset_index(drop=True)


def _max_stage128_diff(comparison: pd.DataFrame) -> float:
    replay = comparison[comparison["source"].eq("stage939_replay_stage128_latest_pool")]
    if replay.empty:
        return float("nan")
    diff_cols = [
        "min_return_pct_delta_vs_stage128_record",
        "median_return_pct_delta_vs_stage128_record",
        "max_return_pct_delta_vs_stage128_record",
    ]
    return float(replay[diff_cols].abs().max().max())


def _write_report(
    latest_pool: pd.DataFrame,
    detail: pd.DataFrame,
    stats: pd.DataFrame,
    comparison: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    view_pool = latest_pool[["eval_date", "product_vt_symbol", "score_rank", "score", "score_type"]].copy()
    view_stats = stats[
        [
            "horizon_label",
            "sample_count",
            "positive_count",
            "min_return_pct",
            "median_return_pct",
            "max_return_pct",
            "min_return_start",
            "max_return_start",
            "worst_max_dd_pct_to_horizon",
            "peak_broker10_margin_to_equity_pct",
        ]
    ].copy()
    view_compare = comparison[
        [
            "source",
            "horizon_label",
            "sample_count",
            "positive_count",
            "min_return_pct",
            "median_return_pct",
            "max_return_pct",
            "min_return_pct_delta_vs_stage128_record",
            "median_return_pct_delta_vs_stage128_record",
            "max_return_pct_delta_vs_stage128_record",
            "positive_count_delta_vs_stage128_record",
        ]
    ].copy()
    view_detail = detail[
        [
            "requested_start_month",
            "horizon_label",
            "target_date",
            "actual_end",
            "end_equity",
            "return_pct",
            "max_dd_pct_to_horizon",
            "max_broker10_margin_to_equity_pct",
        ]
    ].copy()
    reference_20260615 = OFFICIAL_LIVE_REFERENCE_METRICS.get("full_20180102_20260615_stage847_c9_live15w", {})
    lines = [
        "# Stage939 C9 15万 Stage128 旧最新 AI 池 membership replay",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 当前实盘版本：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`。",
        f"- 当前实盘 profile：`{OFFICIAL_LIVE_PROFILE_NAME}`，账户资金 `{OFFICIAL_LIVE_CAPITAL:,.0f}`。",
        f"- 原始当前 AI 池文件：`{OFFICIAL_LIVE_AI_ELIGIBILITY_PATH}`。",
        f"- 冻结对照 AI 池文件：`{FROZEN_POOL_PATH}`。",
        f"- 冻结范围：只替换 `{RECORDED_LATEST_EVAL_DATE}` 最新 eval_date 的 membership 为 Stage128 记录的 `{', '.join(RECORDED_LATEST_POOL)}`。",
        f"- 回测口径：Stage936 旧口径，`{REQUESTED_START.date()}` 起每年 `1月1日/7月1日`，数据终点 `{LATEST_COMPLETE_DATA_DATE.date()}`，只统计完整半年/一年 horizon。",
        "- 注意：这不是当时 Stage182 文件的字节级恢复；rank/score 仅用于审计展示，策略实际拦截只看该 eval_date 下是否存在品种行。",
        "- 不连接 CTP，不读取账户，不调用订单 API。",
        "",
        "## 冻结后的最新池",
        "",
        _md_table(view_pool, max_rows=20),
        "",
        "## Stage939 复跑统计",
        "",
        _md_table(view_stats, max_rows=10),
        "",
        "## 与旧记录/当前重建对比",
        "",
        _md_table(view_compare, max_rows=20),
        "",
        "## 明细",
        "",
        _md_table(view_detail, max_rows=80),
        "",
        "## 全周期正式基准记录",
        "",
        "- `back_log.md` 多处旧研究 A 臂和官方配置都记录了完整窗口 `2018-01-01 -> 2026-06-15`、资金 `150000` 的 C9/15w 基准：",
        (
            f"  期末权益 `{reference_20260615.get('end_equity', 39176437.60):,.2f}`，"
            f"总收益 `{reference_20260615.get('total_return_pct', 26017.6251):.4f}%`，"
            f"最大回撤 `{reference_20260615.get('max_dd_pct', -45.0827):.4f}%`，"
            f"Sharpe `{reference_20260615.get('sharpe', 1.6331):.4f}`，"
            f"总滑点 `{reference_20260615.get('total_slippage', 2730130.0):,.0f}`，"
            f"总交易次数 `{reference_20260615.get('total_trade_count', 787.0):,.0f}`，"
            f"胜率 `{reference_20260615.get('win_rate_pct', 53.2560):.4f}%`。"
        ),
        "- 这个全周期基准和 Stage936 半年/一年 horizon 是两种口径，不能直接拿收益数互相比。",
        "",
        "## 判断",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 是否与 Stage128 记录一致：`{decision['consistent_with_stage128_record']}`",
        f"- 最大核心收益统计差异：`{decision['max_abs_return_stat_diff_vs_stage128_record_pct']}` pct",
        f"- 过拟合反思：{decision['overfit_reflection_after']}",
        f"- 继续价值反思：{decision['continue_value_after']}",
        "",
        "## 输出文件",
        "",
    ]
    for key, path in decision["outputs"].items():
        lines.append(f"- {key}: `{path}`")
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(
        f"[stage939] current live={OFFICIAL_LIVE_VERSION} stage128_latest_pool="
        f"{'/'.join(product.split('.')[0] for product in RECORDED_LATEST_POOL)}",
        flush=True,
    )
    latest_pool = _build_stage128_recorded_latest_pool()
    detail, stats, curves, skipped = _run_horizons_with_frozen_pool()
    comparison = _build_comparison(stats)
    max_diff = _max_stage128_diff(comparison)
    consistent = bool(np.isfinite(max_diff) and max_diff <= 0.01)

    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "official_live_profile_name": OFFICIAL_LIVE_PROFILE_NAME,
        "capital": OFFICIAL_LIVE_CAPITAL,
        "source_ai_pool_path": str(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH),
        "frozen_ai_pool_path": str(FROZEN_POOL_PATH),
        "recorded_latest_eval_date": RECORDED_LATEST_EVAL_DATE,
        "recorded_latest_pool": list(RECORDED_LATEST_POOL),
        "requested_start": REQUESTED_START.date().isoformat(),
        "latest_complete_data_date": LATEST_COMPLETE_DATA_DATE.date().isoformat(),
        "horizon_rule": "last trading day on or before the calendar 6m/12m anniversary",
        "detail_count": int(len(detail)),
        "stats": stats.to_dict(orient="records") if not stats.empty else [],
        "comparison": comparison.to_dict(orient="records") if not comparison.empty else [],
        "skipped_starts": skipped,
        "consistent_with_stage128_record": consistent,
        "max_abs_return_stat_diff_vs_stage128_record_pct": None if not np.isfinite(max_diff) else max_diff,
        "decision": (
            "stage939_recorded_latest_pool_replay_consistent"
            if consistent
            else "stage939_recorded_latest_pool_replay_not_consistent_need_original_artifacts"
        ),
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "limitation": (
            "Only the latest eval_date membership recorded in LINE.md is replayed. "
            "This is not a byte-level restoration of the historical Stage182/Stage861/Stage149 artifacts."
        ),
        "overfit_reflection_before": (
            "否。本次固定旧记录 membership、旧 Stage936 起点和 horizon，只做一致性审计，不调任何策略参数。"
        ),
        "continue_value_before": (
            "是。它能拆分当前不一致到底有多少来自最新 AI 池 SM/rb membership 差异。"
        ),
        "overfit_reflection_after": (
            "否。本次没有根据结果挑品种或改参数；但如果继续用结果反推替换品种、扫旧池组合，就是过拟合。"
        ),
        "continue_value_after": (
            "是。若仍不一致，应继续找当时原始 Stage182/Stage861/Stage149 产物或 hash；若一致，则说明主要差异来自最新 AI 池 membership 漂移。"
        ),
        "outputs": {
            "frozen_ai_pool": str(FROZEN_POOL_PATH),
            "detail": str(DETAIL_PATH),
            "stats": str(STATS_PATH),
            "curves": str(CURVES_PATH),
            "comparison": str(COMPARISON_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }

    detail.to_csv(DETAIL_PATH, index=False, encoding="utf-8-sig")
    stats.to_csv(STATS_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(latest_pool, detail, stats, comparison, decision)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    if not comparison.empty:
        print("comparison")
        print(
            comparison[
                [
                    "source",
                    "horizon_label",
                    "sample_count",
                    "positive_count",
                    "min_return_pct",
                    "median_return_pct",
                    "max_return_pct",
                    "min_return_pct_delta_vs_stage128_record",
                    "median_return_pct_delta_vs_stage128_record",
                    "max_return_pct_delta_vs_stage128_record",
                ]
            ].to_string(index=False)
        )


if __name__ == "__main__":
    main()
