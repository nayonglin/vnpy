from __future__ import annotations

from datetime import datetime
import json

import numpy as np
import pandas as pd

import analyze_qmt_roll_stage815_stage813_top40_loss_kline_atlas as atlas
import qmt_roll_official_candidate_stage813_config as stage813_cfg


MODEL_TAG = "stage816_stage813_top50_loss_kline_atlas_v1"
OUTPUT_PREFIX = "qmt_roll_stage816_stage813_top50_loss_kline_atlas"
SOURCE_TAG = "stage815_stage813_top40_loss_kline_atlas_v1"
SOURCE_PREFIX = "qmt_roll_stage815_stage813_top40_loss_kline_atlas"
TOP_N = 50

SUMMARY_SOURCE_PATH = atlas.OUTPUT_DIR / f"{SOURCE_PREFIX}_summary_{SOURCE_TAG}.csv"
CLOSED_LOTS_SOURCE_PATH = atlas.OUTPUT_DIR / f"{SOURCE_PREFIX}_closed_lots_{SOURCE_TAG}.csv"

SUMMARY_PATH = atlas.OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
TOP_LOSSES_PATH = atlas.OUTPUT_DIR / f"{OUTPUT_PREFIX}_top50_losses_{MODEL_TAG}.csv"
REPORT_PATH = atlas.OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = atlas.OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
CHART_PATH_TEMPLATE = atlas.OUTPUT_DIR / f"{OUTPUT_PREFIX}_page{{page:02d}}_{MODEL_TAG}.png"


def _configure_atlas() -> None:
    atlas.MODEL_TAG = MODEL_TAG
    atlas.OUTPUT_PREFIX = OUTPUT_PREFIX
    atlas.TOP_N = TOP_N
    atlas.SUMMARY_PATH = SUMMARY_PATH
    atlas.TOP_LOSSES_PATH = TOP_LOSSES_PATH
    atlas.REPORT_PATH = REPORT_PATH
    atlas.DECISION_PATH = DECISION_PATH
    atlas.CHART_PATH_TEMPLATE = CHART_PATH_TEMPLATE


def _read_sources() -> tuple[pd.DataFrame, pd.DataFrame]:
    if not SUMMARY_SOURCE_PATH.exists():
        raise FileNotFoundError(f"missing summary source: {SUMMARY_SOURCE_PATH}")
    if not CLOSED_LOTS_SOURCE_PATH.exists():
        raise FileNotFoundError(f"missing closed lots source: {CLOSED_LOTS_SOURCE_PATH}")
    summary = pd.read_csv(SUMMARY_SOURCE_PATH, encoding="utf-8-sig")
    closed = pd.read_csv(CLOSED_LOTS_SOURCE_PATH, encoding="utf-8-sig")
    for column in ["entry_date", "exit_date"]:
        if column in closed.columns:
            closed[column] = pd.to_datetime(closed[column], errors="coerce").dt.normalize()
    return summary, closed


def _write_report(
    summary: pd.DataFrame,
    closed: pd.DataFrame,
    top_with_chart: pd.DataFrame,
    chart_paths: list,
    chart_records: pd.DataFrame,
) -> None:
    row = summary.iloc[0].to_dict()
    display_cols = [
        "loss_rank",
        "lot_id",
        "vt_symbol",
        "direction",
        "entry_date",
        "exit_date",
        "theory_loss_pct",
        "realized_pnl",
        "r_multiple",
        "risk_multiplier",
        "oi_price_confirm_risk_restore_applied",
        "signal",
        "exit_reason",
        "chart_page",
        "bar_source",
    ]
    top_loss = float(top_with_chart["theory_loss_pct"].max()) if len(top_with_chart) else np.nan
    rank_n_loss = float(top_with_chart["theory_loss_pct"].iloc[-1]) if len(top_with_chart) else np.nan
    top_pnl = float(pd.to_numeric(top_with_chart["realized_pnl"], errors="coerce").sum()) if len(top_with_chart) else 0.0
    oi_hit_count = (
        int(
            pd.to_numeric(top_with_chart["oi_price_confirm_risk_restore_applied"], errors="coerce")
            .fillna(0)
            .eq(1)
            .sum()
        )
        if len(top_with_chart)
        else 0
    )
    missing_bar_lots = int(chart_records["missing_bars"].sum()) if len(chart_records) else 0
    minute_lots = (
        int(chart_records["bar_source"].eq("minute_aggregated").sum())
        if len(chart_records) and "bar_source" in chart_records
        else 0
    )
    early_lots = (
        int(chart_records["bar_source"].eq("tushare_early_daily").sum())
        if len(chart_records) and "bar_source" in chart_records
        else 0
    )

    lines = [
        "# Stage816 Stage813亏损比例Top50 K线图谱",
        "",
        f"- line_id：`{atlas.LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 源版本：`{stage813_cfg.OFFICIAL_CANDIDATE_STAGE813_VERSION}`",
        f"- 数据来源：复用 `{SOURCE_TAG}` 已落盘的 closed_lots 与 summary，不重跑策略。",
        f"- 区间：`{atlas.START.date()}` 到 `{atlas.END.date()}`",
        "- 排序指标：`theory_loss_pct = -directional(entry->exit return pct)`。",
        "- 图形：每笔开仓前50根、平仓后50根；蓝色入场、紫色出场、红色背景为持仓亏损段；下方面板为成交量和OI。",
        "",
        "## Full-Period Result",
        "",
        atlas._md_table(
            pd.DataFrame(
                [
                    {
                        "end_equity": row.get("end_equity"),
                        "total_return_pct": row.get("total_return_pct"),
                        "max_dd_pct": row.get("max_dd_pct"),
                        "sharpe": row.get("sharpe"),
                        "total_slippage": row.get("total_slippage"),
                        "total_trade_count": row.get("total_trade_count"),
                        "win_rate_pct": row.get("nonzero_daily_win_rate_pct"),
                    }
                ]
            ),
            max_rows=5,
        ),
        "",
        "## Top50 Summary",
        "",
        atlas._md_table(
            pd.DataFrame(
                [
                    {
                        "closed_lots": len(closed),
                        "loser_lots": int(pd.to_numeric(closed["theory_return_pct"], errors="coerce").lt(0).sum()),
                        "top_n": len(top_with_chart),
                        "worst_theory_loss_pct": top_loss,
                        "rank50_theory_loss_pct": rank_n_loss,
                        "top50_realized_pnl": top_pnl,
                        "oi_hit_count": oi_hit_count,
                        "missing_bar_lots": missing_bar_lots,
                        "minute_aggregated_lots": minute_lots,
                        "tushare_early_daily_lots": early_lots,
                    }
                ]
            ),
            max_rows=5,
        ),
        "",
        "## Top50 Trades",
        "",
        atlas._md_table(top_with_chart[[column for column in display_cols if column in top_with_chart.columns]], max_rows=60),
        "",
        "## Charts",
        "",
        *[f"- `{path}`" for path in chart_paths],
        "",
        "## Judgment",
        "",
        "- 本阶段只读复盘，不新增交易规则，不修改策略参数。",
        "- 过拟合判断：画图本身不过拟合；若从这50笔直接倒推出过滤规则，会有高过拟合风险。",
        "- 继续价值判断：有价值。第41-50笔可以检查左尾结构是否延续 Top40 的 OI放大、趋势末端假突破、短周期急反或特定退出类型集中。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    _configure_atlas()
    atlas.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary, closed = _read_sources()
    top = atlas._select_top_losses(closed)
    chart_paths, chart_records = atlas._plot_pages(top)
    top_with_chart = top.merge(chart_records, on="lot_id", how="left")

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    top_with_chart.to_csv(TOP_LOSSES_PATH, index=False, encoding="utf-8-sig")
    _write_report(summary, closed, top_with_chart, chart_paths, chart_records)

    summary_row = summary.iloc[0].to_dict()
    decision = {
        "stage": "Stage816",
        "line_id": atlas.LINE_ID,
        "model_tag": MODEL_TAG,
        "task": "Stage813 official candidate full-period top 50 theoretical loss K-line atlas",
        "strategy_changed": False,
        "backtest_rerun": False,
        "source_closed_lots": str(CLOSED_LOTS_SOURCE_PATH),
        "source_summary": str(SUMMARY_SOURCE_PATH),
        "source_version": stage813_cfg.OFFICIAL_CANDIDATE_STAGE813_VERSION,
        "start": atlas.START.date().isoformat(),
        "end": atlas.END.date().isoformat(),
        "ranking_metric": "theory_loss_pct = -directional(entry->exit return pct)",
        "full_period_result": {
            "end_equity": summary_row.get("end_equity"),
            "total_return_pct": summary_row.get("total_return_pct"),
            "max_dd_pct": summary_row.get("max_dd_pct"),
            "sharpe": summary_row.get("sharpe"),
            "total_slippage": summary_row.get("total_slippage"),
            "total_trade_count": summary_row.get("total_trade_count"),
            "win_rate_pct": summary_row.get("nonzero_daily_win_rate_pct"),
        },
        "top50_summary": {
            "closed_lots": int(len(closed)),
            "loser_lots": int(pd.to_numeric(closed["theory_return_pct"], errors="coerce").lt(0).sum()),
            "top_n": int(len(top_with_chart)),
            "worst_theory_loss_pct": float(top_with_chart["theory_loss_pct"].max()) if len(top_with_chart) else np.nan,
            "rank50_theory_loss_pct": float(top_with_chart["theory_loss_pct"].iloc[-1]) if len(top_with_chart) else np.nan,
            "top50_realized_pnl": float(pd.to_numeric(top_with_chart["realized_pnl"], errors="coerce").sum())
            if len(top_with_chart)
            else 0.0,
            "oi_hit_count": int(
                pd.to_numeric(top_with_chart["oi_price_confirm_risk_restore_applied"], errors="coerce")
                .fillna(0)
                .eq(1)
                .sum()
            )
            if len(top_with_chart)
            else 0,
            "missing_bar_lots": int(chart_records["missing_bars"].sum()) if len(chart_records) else 0,
            "minute_aggregated_lots": int(chart_records["bar_source"].eq("minute_aggregated").sum())
            if len(chart_records) and "bar_source" in chart_records
            else 0,
            "tushare_early_daily_lots": int(chart_records["bar_source"].eq("tushare_early_daily").sum())
            if len(chart_records) and "bar_source" in chart_records
            else 0,
        },
        "overfit_reflection": (
            "Low for chart generation because no strategy rule or parameter is changed. "
            "High only if thresholds are inferred from these 50 examples without predeclared multi-start validation."
        ),
        "continue_value": "Yes for visual left-tail forensics; no parameter tuning from the charts alone.",
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "top_losses": str(TOP_LOSSES_PATH),
            "report": str(REPORT_PATH),
            "charts": [str(path) for path in chart_paths],
        },
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    DECISION_PATH.write_text(json.dumps(atlas._json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(atlas._json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
