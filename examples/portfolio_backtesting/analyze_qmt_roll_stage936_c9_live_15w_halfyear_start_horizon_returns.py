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
    OFFICIAL_LIVE_VERSION,
)


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage936"
MODEL_TAG = "stage936_c9_live_15w_halfyear_start_horizon_returns_v1"
OUTPUT_PREFIX = "qmt_roll_stage936_c9_live_15w_halfyear_start_horizon_returns"

REQUESTED_START = pd.Timestamp("2020-01-01")
LATEST_COMPLETE_DATA_DATE = pd.Timestamp("2026-06-15")
START_MONTHS = (1, 7)
HORIZONS = (("half_year", 6, "半年"), ("one_year", 12, "一年"))

DETAIL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_detail_{MODEL_TAG}.csv"
STATS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stats_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
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
    account_capital = float(pd.to_numeric(pd.Series([row.get("account_capital", OFFICIAL_LIVE_CAPITAL)]), errors="coerce").iloc[0])
    end_equity = float(pd.to_numeric(pd.Series([row.get("account_equity", np.nan)]), errors="coerce").iloc[0])
    return_pct = (end_equity / account_capital - 1.0) * 100.0
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "official_live_profile_name": OFFICIAL_LIVE_PROFILE_NAME,
        "ai_pool_path": str(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH),
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


def _stats(detail: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for horizon_key, group in detail.groupby("horizon_key", sort=False):
        returns = pd.to_numeric(group["return_pct"], errors="coerce")
        min_idx = returns.idxmin()
        max_idx = returns.idxmax()
        rows.append(
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "line_id": LINE_ID,
                "official_live_version": OFFICIAL_LIVE_VERSION,
                "official_live_alias": OFFICIAL_LIVE_ALIAS,
                "horizon_key": horizon_key,
                "horizon_label": str(group["horizon_label"].iloc[0]),
                "horizon_months": int(group["horizon_months"].iloc[0]),
                "sample_count": int(len(group)),
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


def _write_report(detail: pd.DataFrame, stats: pd.DataFrame, decision: dict[str, Any]) -> None:
    view_detail = detail[
        [
            "requested_start_month",
            "horizon_label",
            "target_date",
            "actual_end",
            "trading_days",
            "end_equity",
            "return_pct",
            "max_dd_pct_to_horizon",
            "max_broker10_margin_to_equity_pct",
        ]
    ].copy()
    view_stats = stats[
        [
            "horizon_label",
            "sample_count",
            "min_return_pct",
            "median_return_pct",
            "max_return_pct",
            "min_return_start",
            "max_return_start",
            "worst_max_dd_pct_to_horizon",
            "peak_broker10_margin_to_equity_pct",
        ]
    ].copy()
    lines = [
        "# Stage936 C9 当前实盘 15万 半年起点 horizon 收益统计",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 当前实盘版本：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`。",
        f"- 当前实盘 profile：`{OFFICIAL_LIVE_PROFILE_NAME}`，账户资金 `{OFFICIAL_LIVE_CAPITAL:,.0f}`。",
        f"- AI 池：`{OFFICIAL_LIVE_AI_ELIGIBILITY_PATH}`。",
        f"- 起点：从 `{REQUESTED_START.date()}` 起，每年 `1月1日` 和 `7月1日`。",
        f"- 数据终点：`{LATEST_COMPLETE_DATA_DATE.date()}`；只统计完整半年/一年 horizon。",
        "- horizon 取值：周年日当天若非交易日，取周年日之前或当天的最后一个交易日，不向后看。",
        "- 不连接 CTP，不读取账户，不调用订单 API。",
        "",
        "## 统计结论",
        "",
        _md_table(view_stats, max_rows=10),
        "",
        "## 明细",
        "",
        _md_table(view_detail, max_rows=80),
        "",
        "## 判断",
        "",
        f"- 决策：`{decision['decision']}`",
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
        f"[stage936] current live={OFFICIAL_LIVE_VERSION} starts={REQUESTED_START.date()} "
        f"data_end={LATEST_COMPLETE_DATA_DATE.date()}",
        flush=True,
    )
    metadata = s901.s513._metadata()
    starts = _build_start_dates()
    detail_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    skipped: list[dict[str, Any]] = []

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
            f"[stage936] running {idx}/{len(starts)} start={_date_text(start)} "
            f"run_end={_date_text(run_end)}",
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
        curve["nav"] = pd.to_numeric(curve["account_equity"], errors="coerce") / float(OFFICIAL_LIVE_CAPITAL)
        curve["drawdown_pct"] = _drawdown_pct(pd.to_numeric(curve["account_equity"], errors="coerce"))
        curve_frames.append(curve)
        for horizon_key, months, label in HORIZONS:
            row = _detail_for_horizon(curve, start, horizon_key, months, label)
            if row is not None:
                detail_rows.append(row)

    detail = pd.DataFrame(detail_rows).sort_values(["horizon_months", "requested_start"]).reset_index(drop=True)
    curves = pd.concat(curve_frames, ignore_index=True, sort=False) if curve_frames else pd.DataFrame()
    stats = _stats(detail) if not detail.empty else pd.DataFrame()
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "official_live_profile_name": OFFICIAL_LIVE_PROFILE_NAME,
        "capital": OFFICIAL_LIVE_CAPITAL,
        "ai_pool_path": str(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH),
        "requested_start": REQUESTED_START.date().isoformat(),
        "start_schedule": "Jan 1 and Jul 1 every year",
        "latest_complete_data_date": LATEST_COMPLETE_DATA_DATE.date().isoformat(),
        "horizon_rule": "last trading day on or before the calendar 6m/12m anniversary",
        "detail_count": int(len(detail)),
        "stats": stats.to_dict(orient="records") if not stats.empty else [],
        "skipped_starts": skipped,
        "decision": "stage936_live_c9_15w_horizon_distribution_measured_no_order_api",
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "overfit_reflection_before": (
            "否。起点计划、资金、当前 live override 和半年/一年 horizon 都是预先固定，未调任何策略参数。"
        ),
        "continue_value_before": (
            "是。这个统计直接衡量 15万实盘账户在不同启动时点的短中期路径分布。"
        ),
        "overfit_reflection_after": (
            "否。本次只是对固定 live 口径做启动时点敏感性统计；但样本数量有限，不能用结果反向优化 C9 参数。"
        ),
        "continue_value_after": (
            "是。半年/一年分布能辅助实盘心理预期和风控沟通；后续应继续观察真实成交/TCA，而不是按这些窗口救参。"
        ),
        "outputs": {
            "detail": str(DETAIL_PATH),
            "stats": str(STATS_PATH),
            "curves": str(CURVES_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }

    detail.to_csv(DETAIL_PATH, index=False, encoding="utf-8-sig")
    stats.to_csv(STATS_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(detail, stats, decision)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    if not stats.empty:
        print("stats")
        print(stats.to_string(index=False))
    if not detail.empty:
        print("detail")
        print(
            detail[
                [
                    "requested_start_month",
                    "horizon_label",
                    "target_date",
                    "actual_end",
                    "trading_days",
                    "end_equity",
                    "return_pct",
                    "max_dd_pct_to_horizon",
                    "max_broker10_margin_to_equity_pct",
                ]
            ].to_string(index=False)
        )


if __name__ == "__main__":
    main()
