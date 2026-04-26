from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage135_stage78_live_review_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage135_stage78_live_review"
FORMAL_PREFIX: str = "qmt_roll_official_stage78_defensive_formal"
CAPITAL: float = 200_000.0

DAILY_PATH: Path = OUTPUT_DIR / f"{FORMAL_PREFIX}_daily.csv"
TRADES_PATH: Path = OUTPUT_DIR / f"{FORMAL_PREFIX}_trades_2020_2026_04.csv"
CANDIDATES_PATH: Path = OUTPUT_DIR / f"{FORMAL_PREFIX}_entry_candidate_snapshots_2020_2026_04.csv"
SUMMARY_PATH: Path = OUTPUT_DIR / "qmt_roll_official_stage78_defensive_summary.json"

DRAWDDOWN_EPISODE_PATH: Path = (
    OUTPUT_DIR
    / "qmt_roll_stage127_stage78_profit_drawdown_attribution_drawdown_episode_summary_stage127_stage78_profit_drawdown_attribution_v1.csv"
)
PROFIT_WINDOW_PATH: Path = (
    OUTPUT_DIR
    / "qmt_roll_stage127_stage78_profit_drawdown_attribution_profit_window_summary_stage127_stage78_profit_drawdown_attribution_v1.csv"
)
FULL_PRODUCT_PATH: Path = (
    OUTPUT_DIR
    / "qmt_roll_stage127_stage78_profit_drawdown_attribution_full_product_attribution_stage127_stage78_profit_drawdown_attribution_v1.csv"
)
FULL_DIRECTION_PATH: Path = (
    OUTPUT_DIR
    / "qmt_roll_stage127_stage78_profit_drawdown_attribution_full_direction_attribution_stage127_stage78_profit_drawdown_attribution_v1.csv"
)
DAILY_BUCKET_PATH: Path = (
    OUTPUT_DIR
    / "qmt_roll_stage78_concurrency_quality_attribution_daily_bucket_summary_stage124_stage78_concurrency_quality_attribution_v1.csv"
)
ENTRY_BUCKET_PATH: Path = (
    OUTPUT_DIR
    / "qmt_roll_stage78_concurrency_quality_attribution_entry_quality_by_active_before_stage124_stage78_concurrency_quality_attribution_v1.csv"
)
WORST_20D_PATH: Path = (
    OUTPUT_DIR
    / "qmt_roll_stage78_concurrency_quality_attribution_worst_20d_windows_stage124_stage78_concurrency_quality_attribution_v1.csv"
)

DASHBOARD_PATH: Path = OUTPUT_DIR / f"{FORMAL_PREFIX}_professional_dashboard.html"
TRADE_REVIEW_PATH: Path = OUTPUT_DIR / f"{FORMAL_PREFIX}_trade_review.html"

MONTHLY_SUMMARY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_monthly_summary_{MODEL_TAG}.csv"
YEARLY_SUMMARY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_yearly_summary_{MODEL_TAG}.csv"
CANDIDATE_FUNNEL_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_candidate_funnel_{MODEL_TAG}.csv"
LIVE_CHECKLIST_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_live_checklist_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _require(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"missing required Stage78 artifact: {path}")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or math.isinf(result):
        return default
    return result


def _fmt(value: Any, digits: int = 4) -> str:
    if isinstance(value, (int, np.integer)):
        return f"{int(value):,}"
    numeric = _safe_float(value, default=float("nan"))
    if math.isnan(numeric):
        return str(value)
    if abs(numeric) >= 1000:
        return f"{numeric:,.0f}"
    return f"{numeric:.{digits}f}"


def _to_markdown_table(df: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 20) -> str:
    if df.empty:
        return "_No rows._"
    view = df.copy()
    if columns is not None:
        view = view.loc[:, [column for column in columns if column in view.columns]]
    view = view.head(max_rows).copy()
    for column in view.columns:
        if pd.api.types.is_numeric_dtype(view[column]):
            view[column] = view[column].map(_fmt)
    return "\n".join(
        [
            "| " + " | ".join(view.columns) + " |",
            "| " + " | ".join(["---"] * len(view.columns)) + " |",
            *["| " + " | ".join(map(str, row)) + " |" for row in view.to_numpy()],
        ]
    )


def _read_csv(path: Path) -> pd.DataFrame:
    _require(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def _load_daily() -> pd.DataFrame:
    daily = _read_csv(DAILY_PATH)
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    daily = daily.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    numeric_columns = [
        "trade_count",
        "turnover",
        "commission",
        "slippage",
        "trading_pnl",
        "holding_pnl",
        "total_pnl",
        "net_pnl",
        "balance",
        "return",
        "highlevel",
        "drawdown",
        "ddpercent",
    ]
    for column in numeric_columns:
        daily[column] = pd.to_numeric(daily.get(column, 0.0), errors="coerce").fillna(0.0)
    daily["prev_balance"] = daily["balance"].shift(1).fillna(CAPITAL)
    daily["daily_return_pct"] = daily["net_pnl"] / daily["prev_balance"].replace(0.0, np.nan) * 100.0
    daily["daily_return_pct"] = daily["daily_return_pct"].fillna(0.0)
    daily["year"] = daily["date"].dt.year.astype(str)
    daily["month"] = daily["date"].dt.to_period("M").astype(str)
    daily["profit_day"] = daily["net_pnl"] > 0
    daily["loss_day"] = daily["net_pnl"] < 0
    daily["rolling_20d_net_pnl"] = daily["net_pnl"].rolling(20, min_periods=5).sum()
    daily["rolling_63d_net_pnl"] = daily["net_pnl"].rolling(63, min_periods=20).sum()
    return daily


def _period_summary(daily: pd.DataFrame, period_column: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for period, group in daily.groupby(period_column, sort=True):
        group = group.sort_values("date")
        start_balance = float(group["prev_balance"].iloc[0])
        end_balance = float(group["balance"].iloc[-1])
        net_pnl = float(group["net_pnl"].sum())
        rows.append(
            {
                "period": str(period),
                "start_date": group["date"].iloc[0].date().isoformat(),
                "end_date": group["date"].iloc[-1].date().isoformat(),
                "start_balance": start_balance,
                "end_balance": end_balance,
                "net_pnl": net_pnl,
                "return_pct": net_pnl / max(start_balance, 1e-9) * 100.0,
                "max_ddpercent": float(group["ddpercent"].min()),
                "trade_count": int(group["trade_count"].sum()),
                "slippage": float(group["slippage"].sum()),
                "profit_days": int(group["profit_day"].sum()),
                "loss_days": int(group["loss_day"].sum()),
            }
        )
    return pd.DataFrame(rows)


def _ai_rank_bucket(value: Any) -> str:
    rank = _safe_float(value, default=0.0)
    if rank <= 0:
        return "unknown"
    if rank <= 3:
        return "ai_rank_1_3"
    if rank <= 8:
        return "ai_rank_4_8"
    return "satellite_or_rank_9_plus"


def _active_bucket(value: Any) -> str:
    active = _safe_float(value, default=0.0)
    if active <= 0:
        return "0"
    if active <= 2:
        return "1-2"
    if active <= 4:
        return "3-4"
    if active <= 6:
        return "5-6"
    return "7+"


def _build_candidate_funnel(candidates: pd.DataFrame) -> pd.DataFrame:
    frame = candidates.copy()
    for column in ["ai_product_pool_rank", "active_positions_before", "selected_volume"]:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    frame["ai_rank_bucket"] = frame["ai_product_pool_rank"].map(_ai_rank_bucket)
    frame["active_before_bucket"] = frame["active_positions_before"].map(_active_bucket)
    frame["is_opened"] = frame["candidate_status"].astype(str).eq("opened")

    status_summary = (
        frame.groupby(["candidate_status"], as_index=False)
        .agg(candidate_count=("candidate_index", "count"))
        .sort_values("candidate_count", ascending=False)
    )
    status_summary["scope"] = "status"
    status_summary["bucket"] = status_summary["candidate_status"].astype(str)
    status_summary = status_summary[["scope", "bucket", "candidate_count"]]

    skip_summary = (
        frame[~frame["is_opened"]]
        .assign(skip_reason=lambda x: x["skip_reason"].fillna("").replace("", "unknown"))
        .groupby("skip_reason", as_index=False)
        .agg(candidate_count=("candidate_index", "count"))
        .sort_values("candidate_count", ascending=False)
        .head(12)
    )
    skip_summary["scope"] = "skip_reason"
    skip_summary["bucket"] = skip_summary["skip_reason"].astype(str)
    skip_summary = skip_summary[["scope", "bucket", "candidate_count"]]

    ai_bucket = (
        frame[frame["is_opened"]]
        .groupby("ai_rank_bucket", as_index=False)
        .agg(candidate_count=("candidate_index", "count"), median_selected_volume=("selected_volume", "median"))
        .sort_values("ai_rank_bucket")
    )
    ai_bucket["scope"] = "opened_ai_rank_bucket"
    ai_bucket["bucket"] = ai_bucket["ai_rank_bucket"].astype(str)
    ai_bucket = ai_bucket[["scope", "bucket", "candidate_count", "median_selected_volume"]]

    active_bucket = (
        frame[frame["is_opened"]]
        .groupby("active_before_bucket", as_index=False)
        .agg(candidate_count=("candidate_index", "count"), median_selected_volume=("selected_volume", "median"))
        .sort_values("active_before_bucket")
    )
    active_bucket["scope"] = "opened_active_before_bucket"
    active_bucket["bucket"] = active_bucket["active_before_bucket"].astype(str)
    active_bucket = active_bucket[["scope", "bucket", "candidate_count", "median_selected_volume"]]

    return pd.concat([status_summary, skip_summary, ai_bucket, active_bucket], ignore_index=True).fillna("")


def _build_live_checklist(
    *,
    daily: pd.DataFrame,
    monthly: pd.DataFrame,
    drawdowns: pd.DataFrame,
    products: pd.DataFrame,
    daily_bucket: pd.DataFrame,
    entry_bucket: pd.DataFrame,
    candidate_funnel: pd.DataFrame,
    official_metrics: dict[str, Any],
) -> pd.DataFrame:
    latest = daily.iloc[-1]
    worst_month = monthly.sort_values("net_pnl").iloc[0]
    best_month = monthly.sort_values("net_pnl", ascending=False).iloc[0]
    worst_drawdown = drawdowns.sort_values("max_dd_percent").iloc[0]
    top_product = products.sort_values("full_net_pnl", ascending=False).iloc[0]
    worst_product = products.sort_values("full_net_pnl").iloc[0]
    opened = candidate_funnel[
        (candidate_funnel["scope"] == "status") & (candidate_funnel["bucket"] == "opened")
    ]
    total_candidates = candidate_funnel[candidate_funnel["scope"] == "status"]["candidate_count"].astype(float).sum()
    opened_count = _safe_float(opened["candidate_count"].iloc[0]) if not opened.empty else 0.0
    opened_rate = opened_count / max(total_candidates, 1.0) * 100.0
    high_concurrency = daily_bucket[daily_bucket["start_active_product_bucket"].astype(str).eq("7+")]
    high_concurrency_pnl = _safe_float(high_concurrency["total_net_pnl"].iloc[0]) if not high_concurrency.empty else 0.0
    active_56 = entry_bucket[entry_bucket["active_before_bucket"].astype(str).eq("5-6")]
    active_56_20d = _safe_float(active_56["total_forward_20d_product_net_pnl"].iloc[0]) if not active_56.empty else 0.0

    rows = [
        {
            "cadence": "daily",
            "topic": "equity_drawdown",
            "stage78_evidence": (
                f"最新日期{latest['date'].date().isoformat()}，权益{_fmt(latest['balance'])}，"
                f"当前回撤{_fmt(latest['ddpercent'])}%；历史最大回撤{_fmt(official_metrics['max_dd_percent'])}%"
            ),
            "warning_logic": "回撤进入-20%以下先复盘持仓来源，接近-30%必须复核是否处于历史极端段。",
            "action": "只做风险复盘，不直接改开仓规则。",
        },
        {
            "cadence": "weekly",
            "topic": "rolling_loss_window",
            "stage78_evidence": (
                f"最差月度{worst_month['period']}净损益{_fmt(worst_month['net_pnl'])}；"
                f"最大回撤段{worst_drawdown['start_date']}到{worst_drawdown['trough_date']}，谷底亏损{_fmt(worst_drawdown['trough_loss_amount'])}"
            ),
            "warning_logic": "连续20日亏损要看是否来自趋势反转后的同方向暴露，而不是先找单品种黑名单。",
            "action": "优先做归因，避免弱窗口补丁。",
        },
        {
            "cadence": "monthly",
            "topic": "profit_source",
            "stage78_evidence": (
                f"最佳月度{best_month['period']}净损益{_fmt(best_month['net_pnl'])}；"
                f"第一贡献品种{top_product['product_vt_symbol']}净利润{_fmt(top_product['full_net_pnl'])}"
            ),
            "warning_logic": "趋势系统利润集中是正常现象，不能因为集中就做均匀化。",
            "action": "保留大趋势暴露，后续只审计执行和换手质量。",
        },
        {
            "cadence": "monthly",
            "topic": "product_risk",
            "stage78_evidence": f"最差品种{worst_product['product_vt_symbol']}净利润{_fmt(worst_product['full_net_pnl'])}",
            "warning_logic": "单品种全周期亏损不足以删除，必须看其是否改善组合尾部或提供非相关暴露。",
            "action": "禁止按亏损黑名单删品种。",
        },
        {
            "cadence": "daily",
            "topic": "concurrency",
            "stage78_evidence": f"7+并发历史样本总净利润{_fmt(high_concurrency_pnl)}；5-6并发开仓20日代理收益{_fmt(active_56_20d)}",
            "warning_logic": "高并发不天然低质量，简单砍并发会伤害趋势利润。",
            "action": "若研究降并发，只能过滤低质量增量仓，不做硬上限。",
        },
        {
            "cadence": "post_trade",
            "topic": "candidate_funnel",
            "stage78_evidence": f"候选开仓率约{opened_rate:.2f}%，总候选{_fmt(total_candidates)}，开仓{_fmt(opened_count)}",
            "warning_logic": "开仓率变化异常时，先检查AI池、相关性门控、资金约束是否共同收紧。",
            "action": "记录漏斗变化，不按单日漏斗调参数。",
        },
        {
            "cadence": "monthly",
            "topic": "execution_cost",
            "stage78_evidence": (
                f"全周期滑点{_fmt(official_metrics['total_slippage'])}，交易{_fmt(official_metrics['total_trade_count'])}，"
                f"平均每笔滑点{_fmt(official_metrics['total_slippage'] / max(official_metrics['total_trade_count'], 1.0))}"
            ),
            "warning_logic": "实盘滑点超过回测口径时，先压执行质量和品种流动性，不优先改信号。",
            "action": "建立月度滑点/成交复盘。",
        },
    ]
    return pd.DataFrame(rows)


def build_payload() -> dict[str, Any]:
    for path in (
        DAILY_PATH,
        TRADES_PATH,
        CANDIDATES_PATH,
        SUMMARY_PATH,
        DRAWDDOWN_EPISODE_PATH,
        PROFIT_WINDOW_PATH,
        FULL_PRODUCT_PATH,
        FULL_DIRECTION_PATH,
        DAILY_BUCKET_PATH,
        ENTRY_BUCKET_PATH,
        WORST_20D_PATH,
    ):
        _require(path)

    daily = _load_daily()
    trades = _read_csv(TRADES_PATH)
    candidates = _read_csv(CANDIDATES_PATH)
    drawdowns = _read_csv(DRAWDDOWN_EPISODE_PATH)
    profits = _read_csv(PROFIT_WINDOW_PATH)
    products = _read_csv(FULL_PRODUCT_PATH)
    directions = _read_csv(FULL_DIRECTION_PATH)
    daily_bucket = _read_csv(DAILY_BUCKET_PATH)
    entry_bucket = _read_csv(ENTRY_BUCKET_PATH)
    worst_20d = _read_csv(WORST_20D_PATH)
    summary_payload = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    official_metrics = dict(summary_payload["reference_metrics"]["full_2020_2026"])
    official_metrics["win_ratio_pct"] = summary_payload["experiments"][0].get("win_ratio_pct", 0.0)

    monthly = _period_summary(daily, "month")
    yearly = _period_summary(daily, "year")
    candidate_funnel = _build_candidate_funnel(candidates)
    live_checklist = _build_live_checklist(
        daily=daily,
        monthly=monthly,
        drawdowns=drawdowns,
        products=products,
        daily_bucket=daily_bucket,
        entry_bucket=entry_bucket,
        candidate_funnel=candidate_funnel,
        official_metrics=official_metrics,
    )

    monthly.to_csv(MONTHLY_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    yearly.to_csv(YEARLY_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    candidate_funnel.to_csv(CANDIDATE_FUNNEL_PATH, index=False, encoding="utf-8-sig")
    live_checklist.to_csv(LIVE_CHECKLIST_PATH, index=False, encoding="utf-8-sig")

    trades["offset"] = trades.get("offset", "").astype(str)
    exit_reason_counts = (
        trades[trades["offset"].str.lower().eq("close")]
        .assign(exit_reason=lambda x: x["exit_reason"].fillna("").replace("", "unknown"))
        .groupby("exit_reason", as_index=False)
        .agg(trade_count=("trade_id", "count"))
        .sort_values("trade_count", ascending=False)
    )

    payload = {
        "model_tag": MODEL_TAG,
        "base_version": summary_payload.get("official_version", "official_stage78_defensive_v1"),
        "analysis_type": "live_review_attribution_only",
        "overfit_judgement": "NO",
        "continue_value_judgement": "YES",
        "official_metrics": official_metrics,
        "yearly_summary": yearly.to_dict(orient="records"),
        "worst_months": monthly.sort_values("net_pnl").head(8).to_dict(orient="records"),
        "best_months": monthly.sort_values("net_pnl", ascending=False).head(8).to_dict(orient="records"),
        "worst_drawdowns": drawdowns.sort_values("max_dd_percent").head(8).to_dict(orient="records"),
        "top_profit_windows": profits.sort_values("segment_net_pnl", ascending=False).head(8).to_dict(orient="records"),
        "top_products": products.sort_values("full_net_pnl", ascending=False).head(12).to_dict(orient="records"),
        "bottom_products": products.sort_values("full_net_pnl").head(8).to_dict(orient="records"),
        "directions": directions.to_dict(orient="records"),
        "daily_bucket": daily_bucket.to_dict(orient="records"),
        "entry_bucket": entry_bucket.to_dict(orient="records"),
        "worst_20d_windows": worst_20d.head(12).to_dict(orient="records"),
        "candidate_funnel": candidate_funnel.to_dict(orient="records"),
        "exit_reason_counts": exit_reason_counts.head(12).to_dict(orient="records"),
        "live_checklist": live_checklist.to_dict(orient="records"),
        "artifacts": {
            "monthly_summary": str(MONTHLY_SUMMARY_PATH),
            "yearly_summary": str(YEARLY_SUMMARY_PATH),
            "candidate_funnel": str(CANDIDATE_FUNNEL_PATH),
            "live_checklist": str(LIVE_CHECKLIST_PATH),
            "summary": str(SUMMARY_JSON_PATH),
            "report": str(REPORT_PATH),
            "dashboard": str(DASHBOARD_PATH),
            "trade_review": str(TRADE_REVIEW_PATH),
        },
    }
    return payload


def build_report(payload: dict[str, Any]) -> str:
    metrics = payload["official_metrics"]
    yearly = pd.DataFrame(payload["yearly_summary"])
    worst_months = pd.DataFrame(payload["worst_months"])
    best_months = pd.DataFrame(payload["best_months"])
    drawdowns = pd.DataFrame(payload["worst_drawdowns"])
    profits = pd.DataFrame(payload["top_profit_windows"])
    top_products = pd.DataFrame(payload["top_products"])
    bottom_products = pd.DataFrame(payload["bottom_products"])
    directions = pd.DataFrame(payload["directions"])
    daily_bucket = pd.DataFrame(payload["daily_bucket"])
    entry_bucket = pd.DataFrame(payload["entry_bucket"])
    worst_20d = pd.DataFrame(payload["worst_20d_windows"])
    candidate_funnel = pd.DataFrame(payload["candidate_funnel"])
    exit_reasons = pd.DataFrame(payload["exit_reason_counts"])
    live_checklist = pd.DataFrame(payload["live_checklist"])

    return "\n".join(
        [
            f"# {MODEL_TAG}",
            "",
            "## 边界",
            "",
            f"- 基准版本：`{payload['base_version']}`。",
            "- 本阶段是准实盘复盘体系，不修改策略、不新增参数、不做回测优化。",
            "- 目标是把Stage78的收益来源、风险来源、执行成本、候选漏斗和日常检查项放到一张地图里。",
            "",
            "## 核心结论",
            "",
            "- Stage78可以作为正式防守基准继续使用，但它不是低回撤平滑曲线；它的收益和回撤都来自趋势暴露。",
            "- 高并发不是天然问题，历史上高并发区间也贡献利润；下一步不能做简单最大持仓砍仓。",
            "- 准实盘最应该盯三件事：回撤是否进入历史极端区、AI池/月度候选漏斗是否异常收紧、实盘滑点是否偏离回测口径。",
            "- 不建议根据亏损品种、单月亏损或单个弱窗口做黑名单和阈值补丁。",
            "",
            "## 正式基准指标",
            "",
            f"- 期末权益：`{_fmt(metrics['end_balance'])}`",
            f"- 总收益：`{float(metrics['total_return_pct']):.4f}%`",
            f"- 最大回撤：`{float(metrics['max_dd_percent']):.4f}%`",
            f"- Sharpe：`{float(metrics['sharpe_ratio']):.4f}`",
            f"- 总滑点：`{_fmt(metrics['total_slippage'])}`",
            f"- 总交易次数：`{int(float(metrics['total_trade_count'])):,}`",
            f"- 胜率：`{float(metrics['win_ratio_pct']):.4f}%`",
            "",
            "## 年度复盘",
            "",
            _to_markdown_table(
                yearly,
                ["period", "start_balance", "end_balance", "net_pnl", "return_pct", "max_ddpercent", "trade_count", "slippage"],
            ),
            "",
            "## 最差月度",
            "",
            _to_markdown_table(
                worst_months,
                ["period", "start_balance", "end_balance", "net_pnl", "return_pct", "max_ddpercent", "trade_count", "slippage"],
            ),
            "",
            "## 最好月度",
            "",
            _to_markdown_table(
                best_months,
                ["period", "start_balance", "end_balance", "net_pnl", "return_pct", "max_ddpercent", "trade_count", "slippage"],
            ),
            "",
            "## 最大回撤段",
            "",
            _to_markdown_table(
                drawdowns,
                [
                    "segment_id",
                    "start_date",
                    "trough_date",
                    "end_date",
                    "trading_days",
                    "trough_loss_amount",
                    "max_dd_percent",
                    "total_trade_count",
                ],
            ),
            "",
            "## 主要利润窗口",
            "",
            _to_markdown_table(
                profits,
                [
                    "segment_id",
                    "start_date",
                    "end_date",
                    "segment_net_pnl",
                    "segment_return_on_start_balance_pct",
                    "min_ddpercent",
                    "total_trade_count",
                ],
            ),
            "",
            "## 品种贡献",
            "",
            "### 主要盈利品种",
            "",
            _to_markdown_table(top_products, ["product_vt_symbol", "full_net_pnl", "trade_count", "slippage", "active_days", "pnl_rank"], max_rows=12),
            "",
            "### 主要亏损品种",
            "",
            _to_markdown_table(bottom_products, ["product_vt_symbol", "full_net_pnl", "trade_count", "slippage", "active_days", "pnl_rank"], max_rows=8),
            "",
            "## 方向贡献",
            "",
            _to_markdown_table(directions, ["position_direction", "full_net_pnl", "trade_count", "slippage"]),
            "",
            "## 并发和开仓质量",
            "",
            "### 日度并发桶",
            "",
            _to_markdown_table(
                daily_bucket,
                [
                    "start_active_product_bucket",
                    "day_count",
                    "total_net_pnl",
                    "median_daily_return_pct",
                    "loss_day_rate_pct",
                    "worst_daily_net_pnl",
                    "median_start_margin_to_balance_pct",
                    "max_start_margin_to_balance_pct",
                    "min_ddpercent",
                ],
            ),
            "",
            "### 开仓质量桶",
            "",
            _to_markdown_table(
                entry_bucket,
                [
                    "active_before_bucket",
                    "entry_count",
                    "median_forward_20d_product_net_pnl",
                    "total_forward_20d_product_net_pnl",
                    "forward_20d_positive_rate_pct",
                    "median_forward_63d_product_net_pnl",
                    "total_forward_63d_product_net_pnl",
                    "forward_63d_positive_rate_pct",
                ],
            ),
            "",
            "## 最差20日滚动窗口",
            "",
            _to_markdown_table(
                worst_20d,
                [
                    "date",
                    "rolling_20d_net_pnl",
                    "rolling_20d_avg_start_active_product",
                    "rolling_20d_max_start_margin_pct",
                    "balance",
                    "ddpercent",
                ],
            ),
            "",
            "## 候选漏斗",
            "",
            _to_markdown_table(candidate_funnel, ["scope", "bucket", "candidate_count", "median_selected_volume"], max_rows=40),
            "",
            "## 平仓原因分布",
            "",
            _to_markdown_table(exit_reasons, ["exit_reason", "trade_count"], max_rows=12),
            "",
            "## 准实盘检查清单",
            "",
            _to_markdown_table(live_checklist, ["cadence", "topic", "stage78_evidence", "warning_logic", "action"], max_rows=20),
            "",
            "## 后续判断",
            "",
            "- 如果继续优化Stage78，优先做“AI池切换稳定性/换手约束”，不是慢更新，也不是亏损黑名单。",
            "- 如果研究资金安全，以Stage111为40万部署候选对照，不把Stage78的Alpha基准和资金安全基准混用。",
            "- 如果研究降低并发，只能研究低质量增量仓过滤；简单砍最大持仓会破坏趋势系统收益来源。",
        ]
    ) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = build_payload()
    REPORT_PATH.write_text(build_report(payload), encoding="utf-8")
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(
        json.dumps(
            {
                "model_tag": MODEL_TAG,
                "base_version": payload["base_version"],
                "analysis_type": payload["analysis_type"],
                "overfit_judgement": payload["overfit_judgement"],
                "continue_value_judgement": payload["continue_value_judgement"],
                "report": str(REPORT_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
