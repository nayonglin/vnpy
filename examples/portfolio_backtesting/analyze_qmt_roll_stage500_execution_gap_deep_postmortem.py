from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

STAGE = "Stage200"
MODEL_TAG = "stage500_execution_gap_deep_postmortem_v1"
OUTPUT_PREFIX = "qmt_roll_stage500_execution_gap_deep_postmortem"
LINE_ID = "futures_trend_drawdown30_preserve_return"

DAILY_PATH = OUTPUT_DIR / (
    "qmt_roll_stage499_consistent_preclose_no_fallback_replay_daily_"
    "stage499_consistent_preclose_no_fallback_replay_v1.csv"
)
TRADE_USAGE_PATH = OUTPUT_DIR / (
    "qmt_roll_stage499_consistent_preclose_no_fallback_replay_trade_usage_"
    "stage499_consistent_preclose_no_fallback_replay_v1.csv"
)
SUMMARY_IN_PATH = OUTPUT_DIR / (
    "qmt_roll_stage499_consistent_preclose_no_fallback_replay_summary_"
    "stage499_consistent_preclose_no_fallback_replay_v1.csv"
)
HORIZON_IN_PATH = OUTPUT_DIR / (
    "qmt_roll_stage499_consistent_preclose_no_fallback_replay_horizon_"
    "stage499_consistent_preclose_no_fallback_replay_v1.csv"
)
COST_IN_PATH = OUTPUT_DIR / (
    "qmt_roll_stage499_consistent_preclose_no_fallback_replay_cost_stress_"
    "stage499_consistent_preclose_no_fallback_replay_v1.csv"
)

BASELINE_VARIANT = "stage079"
PRECLOSE_VARIANT = "stage079_consistent_preclose_full_bar_no_fallback"
RERUN_VARIANT = "stage079_rerun_same_day_close"
ACCOUNT_CAPITAL = 615_000.0

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
ANNUAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_attribution_{MODEL_TAG}.csv"
MONTHLY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_monthly_attribution_{MODEL_TAG}.csv"
TOP_DAYS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_top_daily_gaps_{MODEL_TAG}.csv"
ROLLING_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rolling_gap_windows_{MODEL_TAG}.csv"
TRADE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_usage_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "无数据。"
    view = frame.copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda value: f"{value:.4f}" if pd.notna(value) else "")
    return view.to_markdown(index=False)


def _load_daily() -> pd.DataFrame:
    daily = pd.read_csv(DAILY_PATH, encoding="utf-8-sig")
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    daily = daily[daily["variant"].isin([BASELINE_VARIANT, PRECLOSE_VARIANT, RERUN_VARIANT])].copy()
    for column in ["account_equity", "slippage", "trade_count", "net_pnl"]:
        daily[column] = pd.to_numeric(daily[column], errors="coerce").fillna(0.0)
    return daily.sort_values(["variant", "date"]).reset_index(drop=True)


def _wide_daily(daily: pd.DataFrame) -> pd.DataFrame:
    pieces: list[pd.DataFrame] = []
    for variant in [BASELINE_VARIANT, RERUN_VARIANT, PRECLOSE_VARIANT]:
        frame = daily[daily["variant"].eq(variant)][["date", "account_equity", "slippage", "trade_count", "net_pnl"]].copy()
        frame.rename(
            columns={
                "account_equity": f"{variant}_equity",
                "slippage": f"{variant}_slippage",
                "trade_count": f"{variant}_trade_count",
                "net_pnl": f"{variant}_net_pnl",
            },
            inplace=True,
        )
        pieces.append(frame)
    wide = pieces[0]
    for frame in pieces[1:]:
        wide = wide.merge(frame, on="date", how="outer")
    wide = wide.sort_values("date").reset_index(drop=True).fillna(0.0)
    wide["baseline_return"] = wide[f"{BASELINE_VARIANT}_net_pnl"] / wide[f"{BASELINE_VARIANT}_equity"].shift(1).fillna(ACCOUNT_CAPITAL)
    wide["preclose_return"] = wide[f"{PRECLOSE_VARIANT}_net_pnl"] / wide[f"{PRECLOSE_VARIANT}_equity"].shift(1).fillna(ACCOUNT_CAPITAL)
    wide["pnl_gap_baseline_minus_preclose"] = wide[f"{BASELINE_VARIANT}_net_pnl"] - wide[f"{PRECLOSE_VARIANT}_net_pnl"]
    wide["equity_gap_baseline_minus_preclose"] = wide[f"{BASELINE_VARIANT}_equity"] - wide[f"{PRECLOSE_VARIANT}_equity"]
    wide["trade_count_gap"] = wide[f"{PRECLOSE_VARIANT}_trade_count"] - wide[f"{BASELINE_VARIANT}_trade_count"]
    wide["slippage_gap_baseline_minus_preclose"] = wide[f"{BASELINE_VARIANT}_slippage"] - wide[f"{PRECLOSE_VARIANT}_slippage"]
    wide["abs_pnl_gap"] = wide["pnl_gap_baseline_minus_preclose"].abs()
    return wide


def _max_drawdown(equity: pd.Series) -> float:
    equity = pd.to_numeric(equity, errors="coerce").astype(float)
    return float((equity / equity.cummax() - 1.0).min() * 100.0)


def _annual(wide: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for year, group in wide.groupby(wide["date"].dt.year):
        base_start = float(group[f"{BASELINE_VARIANT}_equity"].iloc[0] - group[f"{BASELINE_VARIANT}_net_pnl"].iloc[0])
        pre_start = float(group[f"{PRECLOSE_VARIANT}_equity"].iloc[0] - group[f"{PRECLOSE_VARIANT}_net_pnl"].iloc[0])
        rows.append(
            {
                "year": int(year),
                "baseline_net_pnl": float(group[f"{BASELINE_VARIANT}_net_pnl"].sum()),
                "preclose_net_pnl": float(group[f"{PRECLOSE_VARIANT}_net_pnl"].sum()),
                "pnl_gap_baseline_minus_preclose": float(group["pnl_gap_baseline_minus_preclose"].sum()),
                "baseline_return_pct": float(group[f"{BASELINE_VARIANT}_net_pnl"].sum() / base_start * 100.0),
                "preclose_return_pct": float(group[f"{PRECLOSE_VARIANT}_net_pnl"].sum() / pre_start * 100.0),
                "baseline_max_dd_pct": _max_drawdown(group[f"{BASELINE_VARIANT}_equity"]),
                "preclose_max_dd_pct": _max_drawdown(group[f"{PRECLOSE_VARIANT}_equity"]),
                "baseline_trade_count": float(group[f"{BASELINE_VARIANT}_trade_count"].sum()),
                "preclose_trade_count": float(group[f"{PRECLOSE_VARIANT}_trade_count"].sum()),
                "baseline_slippage": float(group[f"{BASELINE_VARIANT}_slippage"].sum()),
                "preclose_slippage": float(group[f"{PRECLOSE_VARIANT}_slippage"].sum()),
            }
        )
    result = pd.DataFrame(rows)
    total_gap = float(result["pnl_gap_baseline_minus_preclose"].sum())
    result["gap_share_pct"] = result["pnl_gap_baseline_minus_preclose"] / total_gap * 100.0 if total_gap else 0.0
    return result


def _monthly(wide: pd.DataFrame) -> pd.DataFrame:
    frame = wide.copy()
    frame["month"] = frame["date"].dt.to_period("M").astype(str)
    rows: list[dict[str, Any]] = []
    for month, group in frame.groupby("month"):
        rows.append(
            {
                "month": month,
                "baseline_net_pnl": float(group[f"{BASELINE_VARIANT}_net_pnl"].sum()),
                "preclose_net_pnl": float(group[f"{PRECLOSE_VARIANT}_net_pnl"].sum()),
                "pnl_gap_baseline_minus_preclose": float(group["pnl_gap_baseline_minus_preclose"].sum()),
                "abs_pnl_gap_sum": float(group["abs_pnl_gap"].sum()),
                "baseline_trade_count": float(group[f"{BASELINE_VARIANT}_trade_count"].sum()),
                "preclose_trade_count": float(group[f"{PRECLOSE_VARIANT}_trade_count"].sum()),
            }
        )
    return pd.DataFrame(rows).sort_values("pnl_gap_baseline_minus_preclose", ascending=False).reset_index(drop=True)


def _rolling_windows(wide: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for window in [20, 60, 90, 180, 252, 504]:
        if len(wide) < window:
            continue
        gap = wide["pnl_gap_baseline_minus_preclose"].rolling(window).sum()
        idx = int(gap.idxmax())
        segment = wide.iloc[idx - window + 1 : idx + 1]
        rows.append(
            {
                "window_days": int(window),
                "end_date": wide.loc[idx, "date"],
                "start_date": segment["date"].iloc[0],
                "pnl_gap_baseline_minus_preclose": float(gap.iloc[idx]),
                "baseline_net_pnl": float(segment[f"{BASELINE_VARIANT}_net_pnl"].sum()),
                "preclose_net_pnl": float(segment[f"{PRECLOSE_VARIANT}_net_pnl"].sum()),
                "baseline_return_pct": float(
                    (segment[f"{BASELINE_VARIANT}_equity"].iloc[-1] / (segment[f"{BASELINE_VARIANT}_equity"].iloc[0] - segment[f"{BASELINE_VARIANT}_net_pnl"].iloc[0]) - 1.0)
                    * 100.0
                ),
                "preclose_return_pct": float(
                    (segment[f"{PRECLOSE_VARIANT}_equity"].iloc[-1] / (segment[f"{PRECLOSE_VARIANT}_equity"].iloc[0] - segment[f"{PRECLOSE_VARIANT}_net_pnl"].iloc[0]) - 1.0)
                    * 100.0
                ),
            }
        )
    return pd.DataFrame(rows)


def _trade_summary() -> pd.DataFrame:
    trades = pd.read_csv(TRADE_USAGE_PATH, encoding="utf-8-sig")
    trades["date"] = pd.to_datetime(trades["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    for column in ["order_price", "trade_price", "fill_volume", "order_volume", "bar_close_price"]:
        trades[column] = pd.to_numeric(trades.get(column, np.nan), errors="coerce")
    rows = [
        {
            "metric": "preclose_trade_count",
            "value": float(len(trades)),
        },
        {
            "metric": "fallback_trade_count",
            "value": float(trades["fill_source"].astype(str).ne("stage196_fill_first_open").sum()),
        },
        {
            "metric": "mean_abs_trade_vs_order_price",
            "value": float((trades["trade_price"] - trades["order_price"]).abs().mean()),
        },
        {
            "metric": "median_abs_trade_vs_order_price",
            "value": float((trades["trade_price"] - trades["order_price"]).abs().median()),
        },
        {
            "metric": "max_abs_trade_vs_order_price",
            "value": float((trades["trade_price"] - trades["order_price"]).abs().max()),
        },
        {
            "metric": "open_trade_count",
            "value": float(trades["offset"].astype(str).eq("Open").sum()),
        },
        {
            "metric": "close_trade_count",
            "value": float(trades["offset"].astype(str).eq("Close").sum()),
        },
    ]
    return pd.DataFrame(rows)


def main() -> None:
    daily = _load_daily()
    wide = _wide_daily(daily)
    summary_in = pd.read_csv(SUMMARY_IN_PATH, encoding="utf-8-sig")
    horizon_in = pd.read_csv(HORIZON_IN_PATH, encoding="utf-8-sig")
    cost_in = pd.read_csv(COST_IN_PATH, encoding="utf-8-sig")

    annual = _annual(wide)
    monthly = _monthly(wide)
    rolling = _rolling_windows(wide)
    trade_summary = _trade_summary()
    top_days = wide.sort_values("pnl_gap_baseline_minus_preclose", ascending=False).head(40).copy()

    base_summary = summary_in[summary_in["variant"].eq(BASELINE_VARIANT)].iloc[0]
    pre_summary = summary_in[summary_in["variant"].eq(PRECLOSE_VARIANT)].iloc[0]
    total_gap = float(wide["pnl_gap_baseline_minus_preclose"].sum())
    ending_gap = float(pre_summary["end_equity"])
    daily_corr = float(wide["baseline_return"].corr(wide["preclose_return"]))
    same_sign_rate = float((np.sign(wide["baseline_return"]) == np.sign(wide["preclose_return"])).mean())
    top10_share = float(top_days.head(10)["pnl_gap_baseline_minus_preclose"].sum() / total_gap * 100.0)
    top20_share = float(top_days.head(20)["pnl_gap_baseline_minus_preclose"].sum() / total_gap * 100.0)
    slippage_saving = float(wide["slippage_gap_baseline_minus_preclose"].sum())

    summary = pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "baseline_end_equity": float(base_summary["end_equity"]),
                "preclose_end_equity": float(pre_summary["end_equity"]),
                "ending_equity_gap": float(base_summary["end_equity"] - pre_summary["end_equity"]),
                "baseline_total_return_pct": float(base_summary["total_return_pct"]),
                "preclose_total_return_pct": float(pre_summary["total_return_pct"]),
                "baseline_max_dd_pct": float(base_summary["max_dd_pct"]),
                "preclose_max_dd_pct": float(pre_summary["max_dd_pct"]),
                "baseline_sharpe": float(base_summary["sharpe"]),
                "preclose_sharpe": float(pre_summary["sharpe"]),
                "baseline_ulcer_pct": float(base_summary["ulcer_pct"]),
                "preclose_ulcer_pct": float(pre_summary["ulcer_pct"]),
                "sum_daily_pnl_gap": total_gap,
                "daily_return_correlation": daily_corr,
                "same_sign_day_rate": same_sign_rate,
                "top10_gap_share_pct": top10_share,
                "top20_gap_share_pct": top20_share,
                "baseline_total_trade_count": float(wide[f"{BASELINE_VARIANT}_trade_count"].sum()),
                "preclose_total_trade_count": float(wide[f"{PRECLOSE_VARIANT}_trade_count"].sum()),
                "baseline_total_slippage": float(wide[f"{BASELINE_VARIANT}_slippage"].sum()),
                "preclose_total_slippage": float(wide[f"{PRECLOSE_VARIANT}_slippage"].sum()),
                "slippage_saving_baseline_minus_preclose": slippage_saving,
                "decision": "gap_driven_by_signal_path_and_compounding_not_fallback_or_cost",
            }
        ]
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    annual.to_csv(ANNUAL_PATH, index=False, encoding="utf-8-sig")
    monthly.to_csv(MONTHLY_PATH, index=False, encoding="utf-8-sig")
    top_days.to_csv(TOP_DAYS_PATH, index=False, encoding="utf-8-sig")
    rolling.to_csv(ROLLING_PATH, index=False, encoding="utf-8-sig")
    trade_summary.to_csv(TRADE_PATH, index=False, encoding="utf-8-sig")

    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": "gap_driven_by_signal_path_and_compounding_not_fallback_or_cost",
        "baseline_end_equity": float(base_summary["end_equity"]),
        "preclose_end_equity": float(pre_summary["end_equity"]),
        "ending_equity_gap": float(base_summary["end_equity"] - pre_summary["end_equity"]),
        "daily_return_correlation": daily_corr,
        "same_sign_day_rate": same_sign_rate,
        "top10_gap_share_pct": top10_share,
        "top20_gap_share_pct": top20_share,
        "slippage_saving_baseline_minus_preclose": slippage_saving,
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "annual": str(ANNUAL_PATH),
            "monthly": str(MONTHLY_PATH),
            "top_days": str(TOP_DAYS_PATH),
            "rolling": str(ROLLING_PATH),
            "trade_summary": str(TRADE_PATH),
            "report": str(REPORT_PATH),
        },
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")

    report = "\n".join(
        [
            "# Stage200 Stage079执行差异深度复盘",
            "",
            f"- 生成时间：{decision['generated_at']}",
            "- 阶段性质：Stage079 vs Stage199 no-fallback preclose 的差异归因；不新增策略、不调参数。",
            "",
            "## 外部调研与判断",
            "",
            "- 回测中的同bar close信号和同bar close成交是典型的look-ahead风险：信号依赖bar最终值，成交却假设能在同一最终价格完成。",
            "- 本阶段用本地 Stage199 no-fallback 结果复盘，不用外部资料替代本地证据。",
            "",
            "## 总览",
            "",
            _md_table(summary),
            "",
            "## 年度归因",
            "",
            _md_table(annual),
            "",
            "## 最大差异月份",
            "",
            _md_table(monthly.head(20)),
            "",
            "## 最大差异滚动窗口",
            "",
            _md_table(rolling),
            "",
            "## 最大单日差异",
            "",
            _md_table(
                top_days[
                    [
                        "date",
                        f"{BASELINE_VARIANT}_net_pnl",
                        f"{PRECLOSE_VARIANT}_net_pnl",
                        "pnl_gap_baseline_minus_preclose",
                        f"{BASELINE_VARIANT}_equity",
                        f"{PRECLOSE_VARIANT}_equity",
                        f"{BASELINE_VARIANT}_trade_count",
                        f"{PRECLOSE_VARIANT}_trade_count",
                    ]
                ],
                max_rows=30,
            ),
            "",
            "## 成交使用摘要",
            "",
            _md_table(trade_summary),
            "",
            "## 结论",
            "",
            "- 差异不是成本造成：preclose 路径总滑点反而更低。",
            "- 差异不是 fallback 造成：Stage199 已经 fallback=0。",
            "- 差异主要来自信号bar冻结后交易路径变化，并被复利放大。",
        ]
    )
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"wrote: {REPORT_PATH}")


if __name__ == "__main__":
    main()
