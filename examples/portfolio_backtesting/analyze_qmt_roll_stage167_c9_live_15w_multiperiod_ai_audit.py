from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
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
STAGE = "Stage167"
MODEL_TAG = "stage167_c9_live_15w_multiperiod_ai_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage167_c9_live_15w_multiperiod_ai_audit"

REQUESTED_START = pd.Timestamp("2018-01-01")
REQUESTED_END = pd.Timestamp("2026-06-30")
START_MONTHS = (1, 7)

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
STATS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stats_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
ENTRY_CANDIDATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidates_{MODEL_TAG}.csv"
AI_MONTH_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_ai_month_audit_{MODEL_TAG}.csv"
AI_POOL_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_ai_pool_audit_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
PERFORMANCE_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_performance_chart_{MODEL_TAG}.png"
AI_AUDIT_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_ai_audit_chart_{MODEL_TAG}.png"


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
    for year in range(REQUESTED_START.year, REQUESTED_END.year + 1):
        for month in START_MONTHS:
            start = pd.Timestamp(year=year, month=month, day=1)
            if REQUESTED_START <= start <= REQUESTED_END:
                starts.append(start)
    return starts


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    values = pd.to_numeric(equity, errors="coerce").ffill()
    peak = values.cummax()
    return (values / peak.replace(0.0, np.nan) - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0) * 100.0


def _safe_sum(frame: pd.DataFrame, column: str) -> float:
    if column not in frame.columns:
        return 0.0
    return float(pd.to_numeric(frame[column], errors="coerce").fillna(0.0).sum())


def _safe_max(frame: pd.DataFrame, column: str) -> float:
    if column not in frame.columns:
        return 0.0
    series = pd.to_numeric(frame[column], errors="coerce").dropna()
    return float(series.max()) if len(series) else 0.0


def _daily_sharpe(nav: pd.Series) -> float:
    returns = pd.to_numeric(nav, errors="coerce").pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    if returns.empty:
        return 0.0
    std = float(returns.std(ddof=1))
    if std <= 0.0 or np.isnan(std):
        return 0.0
    return float(returns.mean() / std * np.sqrt(252.0))


def _nonzero_daily_win_rate_pct(nav: pd.Series) -> float:
    returns = pd.to_numeric(nav, errors="coerce").pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    nonzero = returns[returns.ne(0.0)]
    if nonzero.empty:
        return 0.0
    return float((nonzero > 0.0).mean() * 100.0)


def _summarize_curve(curve: pd.DataFrame, requested_start: pd.Timestamp) -> dict[str, Any]:
    frame = curve.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    if frame.empty:
        raise RuntimeError(f"empty curve for start {requested_start.date().isoformat()}")

    equity = pd.to_numeric(frame["account_equity"], errors="coerce").ffill()
    nav = equity / float(OFFICIAL_LIVE_CAPITAL)
    drawdown = _drawdown_pct(equity)
    end_equity = float(equity.iloc[-1])
    return_pct = (end_equity / float(OFFICIAL_LIVE_CAPITAL) - 1.0) * 100.0
    elapsed_days = max(1, int((frame["date"].iloc[-1] - frame["date"].iloc[0]).days))
    cagr_pct = ((end_equity / float(OFFICIAL_LIVE_CAPITAL)) ** (365.25 / elapsed_days) - 1.0) * 100.0

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
        "requested_end": _date_text(REQUESTED_END),
        "actual_start": _date_text(frame["date"].iloc[0]),
        "actual_end": _date_text(frame["date"].iloc[-1]),
        "trading_days": int(len(frame)),
        "calendar_days": int(elapsed_days + 1),
        "account_capital": float(OFFICIAL_LIVE_CAPITAL),
        "end_equity": end_equity,
        "total_return_pct": float(return_pct),
        "cagr_pct": float(cagr_pct),
        "max_dd_pct": float(drawdown.min()) if len(drawdown) else 0.0,
        "min_equity": float(equity.min()) if len(equity) else end_equity,
        "max_equity": float(equity.max()) if len(equity) else end_equity,
        "sharpe": _daily_sharpe(nav),
        "total_slippage": _safe_sum(frame, "slippage"),
        "total_trade_count": _safe_sum(frame, "trade_count"),
        "nonzero_daily_win_rate_pct": _nonzero_daily_win_rate_pct(nav),
        "max_broker10_margin_to_equity_pct": _safe_max(frame, "broker10_margin_to_equity_pct"),
        "final_nav": float(nav.iloc[-1]),
        "min_nav": float(nav.min()) if len(nav) else float(nav.iloc[-1]),
        "max_nav": float(nav.max()) if len(nav) else float(nav.iloc[-1]),
    }


def _stats(summary: pd.DataFrame) -> pd.DataFrame:
    returns = pd.to_numeric(summary["total_return_pct"], errors="coerce")
    dds = pd.to_numeric(summary["max_dd_pct"], errors="coerce")
    sharpes = pd.to_numeric(summary["sharpe"], errors="coerce")
    end_equity = pd.to_numeric(summary["end_equity"], errors="coerce")
    broker10 = pd.to_numeric(summary["max_broker10_margin_to_equity_pct"], errors="coerce")
    min_idx = returns.idxmin()
    max_idx = returns.idxmax()
    worst_dd_idx = dds.idxmin()
    return pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "line_id": LINE_ID,
                "official_live_version": OFFICIAL_LIVE_VERSION,
                "sample_count": int(len(summary)),
                "requested_start": REQUESTED_START.date().isoformat(),
                "requested_end": REQUESTED_END.date().isoformat(),
                "positive_count": int((returns > 0.0).sum()),
                "positive_rate_pct": float((returns > 0.0).mean() * 100.0) if len(summary) else 0.0,
                "min_end_equity": float(end_equity.min()),
                "median_end_equity": float(end_equity.median()),
                "max_end_equity": float(end_equity.max()),
                "min_return_pct": float(returns.min()),
                "median_return_pct": float(returns.median()),
                "max_return_pct": float(returns.max()),
                "min_return_start": str(summary.loc[min_idx, "requested_start_month"]),
                "max_return_start": str(summary.loc[max_idx, "requested_start_month"]),
                "worst_max_dd_pct": float(dds.min()),
                "worst_max_dd_start": str(summary.loc[worst_dd_idx, "requested_start_month"]),
                "median_max_dd_pct": float(dds.median()),
                "min_sharpe": float(sharpes.min()),
                "median_sharpe": float(sharpes.median()),
                "max_sharpe": float(sharpes.max()),
                "peak_broker10_margin_to_equity_pct": float(broker10.max()),
                "median_broker10_margin_to_equity_pct": float(broker10.median()),
                "total_slippage_sum": float(pd.to_numeric(summary["total_slippage"], errors="coerce").fillna(0.0).sum()),
                "total_trade_count_sum": float(
                    pd.to_numeric(summary["total_trade_count"], errors="coerce").fillna(0.0).sum()
                ),
                "median_win_rate_pct": float(
                    pd.to_numeric(summary["nonzero_daily_win_rate_pct"], errors="coerce").median()
                ),
                "dd30_fail_count": int((dds < -30.0).sum()),
                "dd40_fail_count": int((dds < -40.0).sum()),
                "dd50_fail_count": int((dds < -50.0).sum()),
                "broker100_fail_count": int((broker10 > 100.0).sum()),
            }
        ]
    )


def _load_ai_pool() -> tuple[pd.DataFrame, dict[str, Any]]:
    if not OFFICIAL_LIVE_AI_ELIGIBILITY_PATH.exists():
        raise FileNotFoundError(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH)
    raw = OFFICIAL_LIVE_AI_ELIGIBILITY_PATH.read_bytes()
    pool = pd.read_csv(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH)
    pool["eval_date"] = pd.to_datetime(pool["eval_date"], errors="coerce").dt.normalize()
    audit = {
        "path": str(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH),
        "exists": True,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "rows": int(len(pool)),
        "columns": list(pool.columns),
        "min_eval_date": _date_text(pool["eval_date"].min()),
        "max_eval_date": _date_text(pool["eval_date"].max()),
        "unique_eval_dates": int(pool["eval_date"].nunique()),
        "strategies": sorted(pool["strategy"].astype(str).dropna().unique().tolist()),
    }
    return pool, audit


def _pool_audit_frame(pool: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for eval_date, group in pool.sort_values(["eval_date", "score_rank"]).groupby("eval_date", dropna=False):
        rows.append(
            {
                "eval_date": _date_text(eval_date),
                "strategy_count": int(group["strategy"].nunique()),
                "row_count": int(len(group)),
                "top_n_max": int(pd.to_numeric(group["top_n"], errors="coerce").max()),
                "products": "/".join(group.sort_values("score_rank")["product_vt_symbol"].astype(str).tolist()),
            }
        )
    return pd.DataFrame(rows)


def _candidate_bool(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0).astype(int).eq(1)


def _text_present(series: pd.Series) -> pd.Series:
    text = series.fillna("").astype(str).str.strip()
    return text.ne("") & ~text.str.lower().isin({"nan", "nat", "none"})


def _ai_month_audit(candidates: pd.DataFrame, summary: pd.DataFrame, pool: pd.DataFrame) -> pd.DataFrame:
    first_eval = pd.to_datetime(pool["eval_date"], errors="coerce").min()
    rows: list[dict[str, Any]] = []
    if candidates.empty:
        for _, item in summary.iterrows():
            rows.append(
                {
                    "requested_start_month": item["requested_start_month"],
                    "covered_month": "",
                    "calendar_month_count": int(
                        len(pd.period_range(item["actual_start"], item["actual_end"], freq="M"))
                    ),
                    "candidate_month": 0,
                    "candidate_count": 0,
                    "ai_enabled_count": 0,
                    "ai_allowed_count": 0,
                    "ai_blocked_count": 0,
                    "missing_signal_date_count": 0,
                    "status": "NO_CANDIDATES",
                    "note": "No entry candidates in this window.",
                }
            )
        return pd.DataFrame(rows)

    temp = candidates.copy()
    temp["candidate_date"] = pd.to_datetime(temp.get("date", temp.get("datetime")), errors="coerce").dt.normalize()
    temp["covered_month"] = temp["candidate_date"].dt.to_period("M").astype(str)
    temp["ai_enabled_flag"] = _candidate_bool(temp.get("ai_product_pool_enabled", pd.Series(dtype=float)))
    temp["ai_allowed_flag"] = _candidate_bool(temp.get("ai_product_pool_allowed", pd.Series(dtype=float)))
    temp["is_ai_blocked"] = temp.get("skip_reason", "").astype(str).eq("ai_product_pool_blocked")
    temp["signal_date_text"] = temp.get("ai_product_pool_signal_date", pd.Series("", index=temp.index))
    temp["signal_date_present"] = _text_present(temp["signal_date_text"])
    temp["post_first_pool_candidate"] = temp["candidate_date"].gt(first_eval) if pd.notna(first_eval) else True
    temp["pre_first_pool_candidate"] = ~temp["post_first_pool_candidate"]
    temp["post_ai_missing_signal"] = temp["post_first_pool_candidate"] & ~temp["signal_date_present"]

    grouped = (
        temp.groupby(["requested_start_month", "covered_month"], dropna=False)
        .agg(
            candidate_count=("candidate_index", "size"),
            opened_count=("is_opened", lambda s: int(pd.to_numeric(s, errors="coerce").fillna(0).sum())),
            candidate_min_date=("candidate_date", "min"),
            candidate_max_date=("candidate_date", "max"),
            ai_enabled_count=("ai_enabled_flag", "sum"),
            ai_allowed_count=("ai_allowed_flag", "sum"),
            ai_blocked_count=("is_ai_blocked", "sum"),
            missing_signal_date_count=("signal_date_present", lambda s: int((~s).sum())),
            missing_post_ai_signal_date_count=("post_ai_missing_signal", "sum"),
            pre_ai_candidate_count=("pre_first_pool_candidate", "sum"),
            post_ai_candidate_count=("post_first_pool_candidate", "sum"),
            unique_signal_dates=(
                "signal_date_text",
                lambda s: "/".join(sorted(v for v in set(s.fillna("").astype(str)) if v.strip())),
            ),
            unique_ai_products=("product_vt_symbol", lambda s: "/".join(sorted(set(s.astype(str))))),
        )
        .reset_index()
    )
    for _, row in grouped.iterrows():
        all_enabled = int(row["ai_enabled_count"]) == int(row["candidate_count"])
        pre_ai_candidate_count = int(row["pre_ai_candidate_count"])
        post_ai_candidate_count = int(row["post_ai_candidate_count"])
        missing_post_ai_signal_date_count = int(row["missing_post_ai_signal_date_count"])
        if post_ai_candidate_count == 0 and all_enabled:
            status = "PRE_AI_HISTORY"
            note = (
                "On or before the first Stage182 eval_date; strategy code keeps the original "
                "pre-AI behavior until a completed snapshot is available."
            )
        elif all_enabled and missing_post_ai_signal_date_count == 0:
            status = "PASS"
            note = "All post-first-snapshot candidates carried AI enabled flag and signal-date metadata."
        else:
            status = "FAIL"
            note = (
                f"AI audit failed: all_enabled={int(all_enabled)}, "
                f"post_ai_candidate_count={post_ai_candidate_count}, "
                f"missing_post_ai_signal_date_count={missing_post_ai_signal_date_count}."
            )
        row_dict = row.to_dict()
        for column in ["candidate_min_date", "candidate_max_date"]:
            row_dict[column] = _date_text(row_dict[column]) if pd.notna(row_dict[column]) else ""
        rows.append(
            {
                **row_dict,
                "candidate_month": 1,
                "first_ai_eval_date": _date_text(first_eval),
                "before_first_pool_month": int(post_ai_candidate_count == 0),
                "pre_ai_candidate_count": pre_ai_candidate_count,
                "post_ai_candidate_count": post_ai_candidate_count,
                "missing_post_ai_signal_date_count": missing_post_ai_signal_date_count,
                "status": status,
                "note": note,
            }
        )

    present_keys = set(zip(grouped["requested_start_month"].astype(str), grouped["covered_month"].astype(str)))
    for _, item in summary.iterrows():
        months = pd.period_range(item["actual_start"], item["actual_end"], freq="M").astype(str)
        for month in months:
            key = (str(item["requested_start_month"]), str(month))
            if key in present_keys:
                continue
            month_ts = pd.Timestamp(f"{month}-01")
            before_first_pool = pd.notna(first_eval) and month_ts < first_eval.to_period("M").to_timestamp()
            rows.append(
                {
                    "requested_start_month": item["requested_start_month"],
                    "covered_month": month,
                    "candidate_count": 0,
                    "opened_count": 0,
                    "ai_enabled_count": 0,
                    "ai_allowed_count": 0,
                    "ai_blocked_count": 0,
                    "missing_signal_date_count": 0,
                    "unique_signal_dates": "",
                    "unique_ai_products": "",
                    "candidate_month": 0,
                    "first_ai_eval_date": _date_text(first_eval),
                    "before_first_pool_month": int(before_first_pool),
                    "status": "NO_CANDIDATE_MONTH",
                    "note": "No entry candidate generated in this calendar month.",
                }
            )
    return pd.DataFrame(rows).sort_values(["requested_start_month", "covered_month"]).reset_index(drop=True)


def _plot_performance(summary: pd.DataFrame, curves: pd.DataFrame) -> None:
    plot_summary = summary.copy()
    plot_summary["requested_start_month"] = plot_summary["requested_start_month"].astype(str)
    fig, axes = plt.subplots(2, 2, figsize=(18, 11), constrained_layout=True)
    ax = axes[0, 0]
    colors = np.where(plot_summary["total_return_pct"] >= 0, "#2563eb", "#dc2626")
    ax.bar(plot_summary["requested_start_month"], plot_summary["total_return_pct"], color=colors)
    ax.set_title("Total Return By Cold Start")
    ax.set_ylabel("return %")
    ax.tick_params(axis="x", rotation=55)
    ax.grid(True, axis="y", alpha=0.25)

    ax = axes[0, 1]
    ax.bar(plot_summary["requested_start_month"], plot_summary["max_dd_pct"], color="#f97316")
    ax.axhline(-30, color="#dc2626", linestyle="--", linewidth=0.9)
    ax.axhline(-40, color="#991b1b", linestyle="--", linewidth=0.9)
    ax.set_title("Max Drawdown By Cold Start")
    ax.set_ylabel("drawdown %")
    ax.tick_params(axis="x", rotation=55)
    ax.grid(True, axis="y", alpha=0.25)

    ax = axes[1, 0]
    ax.bar(plot_summary["requested_start_month"], plot_summary["sharpe"], color="#16a34a")
    ax.set_title("Sharpe By Cold Start")
    ax.tick_params(axis="x", rotation=55)
    ax.grid(True, axis="y", alpha=0.25)

    ax = axes[1, 1]
    for start, group in curves.groupby("requested_start_month"):
        group = group.sort_values("days_since_start")
        ax.plot(group["days_since_start"], group["nav"], linewidth=0.9, alpha=0.78, label=str(start))
    ax.set_title("NAV Paths Rebased To 150k")
    ax.set_xlabel("trading days since start")
    ax.set_ylabel("NAV")
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=6, ncol=2, loc="best")
    fig.savefig(PERFORMANCE_CHART_PATH, dpi=150)
    plt.close(fig)


def _plot_ai_audit(month_audit: pd.DataFrame, pool_audit: pd.DataFrame) -> None:
    audit = month_audit.copy()
    fig, axes = plt.subplots(2, 1, figsize=(18, 10), constrained_layout=True)
    candidate_months = (
        audit[audit["candidate_month"].astype(int).eq(1)]
        .groupby("covered_month", dropna=False)
        .agg(
            candidates=("candidate_count", "sum"),
            allowed=("ai_allowed_count", "sum"),
            blocked=("ai_blocked_count", "sum"),
            fail_months=("status", lambda s: int(s.astype(str).eq("FAIL").sum())),
        )
        .reset_index()
        .sort_values("covered_month")
    )
    ax = axes[0]
    if not candidate_months.empty:
        x = np.arange(len(candidate_months))
        ax.bar(x, candidate_months["allowed"], label="AI allowed", color="#2563eb")
        ax.bar(x, candidate_months["blocked"], bottom=candidate_months["allowed"], label="AI blocked", color="#f97316")
        ax.scatter(x, candidate_months["fail_months"], color="#dc2626", s=18, label="FAIL month count")
        step = max(1, len(x) // 18)
        ax.set_xticks(x[::step])
        ax.set_xticklabels(candidate_months["covered_month"].iloc[::step], rotation=55, ha="right")
    ax.set_title("AI Candidate Decisions By Calendar Month")
    ax.set_ylabel("candidate count")
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend(loc="best")

    pool_plot = pool_audit.tail(24).copy()
    ax = axes[1]
    if not pool_plot.empty:
        x = np.arange(len(pool_plot))
        ax.bar(x, pool_plot["row_count"], color="#16a34a")
        ax.set_xticks(x)
        ax.set_xticklabels(pool_plot["eval_date"], rotation=55, ha="right")
    ax.set_title("Stage182 Pool Rows By Eval Date, Last 24 Snapshots")
    ax.set_ylabel("rows")
    ax.grid(True, axis="y", alpha=0.25)
    fig.savefig(AI_AUDIT_CHART_PATH, dpi=150)
    plt.close(fig)


def _write_report(summary: pd.DataFrame, stats: pd.DataFrame, ai_month_audit: pd.DataFrame, decision: dict[str, Any]) -> None:
    view_summary = summary[
        [
            "requested_start_month",
            "actual_start",
            "actual_end",
            "trading_days",
            "end_equity",
            "total_return_pct",
            "max_dd_pct",
            "sharpe",
            "max_broker10_margin_to_equity_pct",
            "total_trade_count",
        ]
    ].copy()
    ai_status = (
        ai_month_audit.groupby("status", dropna=False)
        .size()
        .reset_index(name="month_rows")
        .sort_values("status")
    )
    lines = [
        "# Stage167 C9 15w 多周期回测与 AI 池审计",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 当前线上版本：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`。",
        f"- 当前线上 profile：`{OFFICIAL_LIVE_PROFILE_NAME}`，资金 `{OFFICIAL_LIVE_CAPITAL:,.0f}`。",
        f"- AI 池：`{OFFICIAL_LIVE_AI_ELIGIBILITY_PATH}`。",
        f"- 起点：从 `{REQUESTED_START.date()}` 起每半年一个独立冷启动起点。",
        f"- 统一结束日：`{REQUESTED_END.date()}`。",
        "- 不连接 CTP，不读取账户，不调用订单 API。",
        "",
        "## 汇总统计",
        "",
        _md_table(stats, max_rows=5),
        "",
        "## 起点明细",
        "",
        _md_table(view_summary, max_rows=80),
        "",
        "## AI 月度审计状态",
        "",
        _md_table(ai_status, max_rows=20),
        "",
        "## 图表",
        "",
        f"- performance chart：`{PERFORMANCE_CHART_PATH}`",
        f"- AI audit chart：`{AI_AUDIT_CHART_PATH}`",
        "",
        "## 判断",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- AI 审计：{decision['ai_audit_summary']['judgment']}",
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
    pool, pool_audit = _load_ai_pool()
    pool_audit_frame = _pool_audit_frame(pool)
    print(
        f"[stage167] live={OFFICIAL_LIVE_VERSION} starts={REQUESTED_START.date()} "
        f"end={REQUESTED_END.date()} ai_eval_max={pool_audit['max_eval_date']}",
        flush=True,
    )
    metadata = s901.s513._metadata()
    starts = _build_start_dates()
    summary_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    candidate_frames: list[pd.DataFrame] = []

    for idx, start in enumerate(starts, start=1):
        print(f"[stage167] running {idx}/{len(starts)} start={_date_text(start)}", flush=True)
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
        curve["drawdown_pct"] = _drawdown_pct(pd.to_numeric(curve["account_equity"], errors="coerce"))
        curve["days_since_start"] = np.arange(len(curve), dtype=int)
        curve_frames.append(curve)
        summary_rows.append(_summarize_curve(curve, start))

        candidates = frames.get("entry_candidates", pd.DataFrame()).copy()
        if not candidates.empty:
            candidates["stage"] = STAGE
            candidates["model_tag"] = MODEL_TAG
            candidates["line_id"] = LINE_ID
            candidates["official_live_version"] = OFFICIAL_LIVE_VERSION
            candidates["official_live_alias"] = OFFICIAL_LIVE_ALIAS
            candidates["requested_start"] = _date_text(start)
            candidates["requested_start_month"] = _start_month_text(start)
            candidates["requested_end"] = _date_text(REQUESTED_END)
            candidate_frames.append(candidates)

    summary = pd.DataFrame(summary_rows).sort_values("requested_start").reset_index(drop=True)
    curves = pd.concat(curve_frames, ignore_index=True, sort=False) if curve_frames else pd.DataFrame()
    candidates_all = pd.concat(candidate_frames, ignore_index=True, sort=False) if candidate_frames else pd.DataFrame()
    stats = _stats(summary) if not summary.empty else pd.DataFrame()
    ai_month_audit = _ai_month_audit(candidates_all, summary, pool)

    candidate_fail_rows = int(ai_month_audit["status"].astype(str).eq("FAIL").sum()) if not ai_month_audit.empty else 0
    candidate_month_rows = int(ai_month_audit["candidate_month"].astype(int).sum()) if not ai_month_audit.empty else 0
    pre_ai_rows = int(ai_month_audit["status"].astype(str).eq("PRE_AI_HISTORY").sum()) if not ai_month_audit.empty else 0
    ai_judgment = (
        "PASS: every candidate month with an available Stage182 snapshot carried AI enabled metadata."
        if candidate_fail_rows == 0
        else "FAIL: at least one candidate month missed AI enabled/signal-date metadata."
    )
    if pre_ai_rows:
        ai_judgment += " Months before the first 2019-12-31 snapshot are explicitly marked PRE_AI_HISTORY."

    _plot_performance(summary, curves)
    _plot_ai_audit(ai_month_audit, pool_audit_frame)

    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "official_live_profile_name": OFFICIAL_LIVE_PROFILE_NAME,
        "capital": OFFICIAL_LIVE_CAPITAL,
        "ai_pool_audit": pool_audit,
        "requested_start": REQUESTED_START.date().isoformat(),
        "requested_end": REQUESTED_END.date().isoformat(),
        "start_schedule": "Jan 1 and Jul 1 every year",
        "sample_count": int(len(summary)),
        "stats": stats.to_dict(orient="records") if not stats.empty else [],
        "ai_audit_summary": {
            "candidate_month_rows": candidate_month_rows,
            "fail_rows": candidate_fail_rows,
            "pre_ai_history_rows": pre_ai_rows,
            "candidate_rows": int(len(candidates_all)),
            "pool_eval_date_min": pool_audit["min_eval_date"],
            "pool_eval_date_max": pool_audit["max_eval_date"],
            "pool_unique_eval_dates": pool_audit["unique_eval_dates"],
            "judgment": ai_judgment,
        },
        "decision": "stage167_live_c9_15w_multiperiod_ai_audit_measured_no_order_api",
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "external_research_judgment": (
            "No external strategy search; this is a fixed live-profile replay and AI audit. "
            "Use the existing Stage901 live wrapper to preserve C9 path-dependent semantics."
        ),
        "overfit_reflection_before": (
            "否。起点、结束日、资金、C9 规则和 Stage182 AI 池均预先固定，不根据结果调参数。"
        ),
        "continue_value_before": (
            "是。用户关心当前线上版本和 AI 选品是否仍按月生效，多周期回放加 AI 审计能直接回答。"
        ),
        "overfit_reflection_after": (
            "否。本次只做固定线上版本多起点回放和 AI 元数据审计，没有修改 AI 池、TopN、品种或 C9 参数。"
        ),
        "continue_value_after": (
            "是。结果可作为当前线上路径风险基准；后续若要提升，应先处理风险尾归因，不应按本次起点表现救参。"
        ),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "stats": str(STATS_PATH),
            "curves": str(CURVES_PATH),
            "entry_candidates": str(ENTRY_CANDIDATES_PATH),
            "ai_month_audit": str(AI_MONTH_AUDIT_PATH),
            "ai_pool_audit": str(AI_POOL_AUDIT_PATH),
            "performance_chart": str(PERFORMANCE_CHART_PATH),
            "ai_audit_chart": str(AI_AUDIT_CHART_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    stats.to_csv(STATS_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    candidates_all.to_csv(ENTRY_CANDIDATES_PATH, index=False, encoding="utf-8-sig")
    ai_month_audit.to_csv(AI_MONTH_AUDIT_PATH, index=False, encoding="utf-8-sig")
    pool_audit_frame.to_csv(AI_POOL_AUDIT_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(summary, stats, ai_month_audit, decision)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    if not stats.empty:
        print("stats")
        print(stats.to_string(index=False))
    if not summary.empty:
        print("summary")
        print(
            summary[
                [
                    "requested_start_month",
                    "actual_start",
                    "actual_end",
                    "trading_days",
                    "end_equity",
                    "total_return_pct",
                    "max_dd_pct",
                    "sharpe",
                    "max_broker10_margin_to_equity_pct",
                ]
            ].to_string(index=False)
        )


if __name__ == "__main__":
    main()
