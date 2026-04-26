from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage136_ai_pool_switch_stability_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage136_ai_pool_switch_stability"

ELIGIBILITY_PATH: Path = (
    OUTPUT_DIR
    / "qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_ai_top8_plus_fu_satellite_post_signal_eligibility.csv"
)
DAILY_PATH: Path = OUTPUT_DIR / "qmt_roll_official_stage78_defensive_formal_daily.csv"
POSITION_CHANGES_PATH: Path = OUTPUT_DIR / "qmt_roll_official_stage78_defensive_formal_position_changes_2020_2026_04.csv"
CANDIDATES_PATH: Path = OUTPUT_DIR / "qmt_roll_official_stage78_defensive_formal_entry_candidate_snapshots_2020_2026_04.csv"
SUMMARY_PATH: Path = OUTPUT_DIR / "qmt_roll_official_stage78_defensive_summary.json"

SIGNAL_PERIOD_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_signal_period_summary_{MODEL_TAG}.csv"
TRANSITION_EVENTS_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_transition_events_{MODEL_TAG}.csv"
TRANSITION_TYPE_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_transition_type_summary_{MODEL_TAG}.csv"
PRODUCT_TRANSITION_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_transition_summary_{MODEL_TAG}.csv"
TURNOVER_BUCKET_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_turnover_bucket_summary_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _require(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"missing required artifact: {path}")


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


def _product_from_contract(vt_symbol: object) -> str:
    raw = str(vt_symbol)
    if "." not in raw:
        return raw
    symbol, exchange = raw.split(".", 1)
    match = re.match(r"^([A-Za-z]+)", symbol)
    product = match.group(1) if match else symbol
    return f"{product}.{exchange}"


def _transition_type(product: str, current_set: set[str], previous_set: set[str]) -> str:
    in_current = product in current_set
    in_previous = product in previous_set
    if in_current and in_previous:
        return "retained"
    if in_current and not in_previous:
        return "added"
    if not in_current and in_previous:
        return "dropped"
    return "out_of_pool"


def _turnover_bucket(add_count: int) -> str:
    if add_count <= 2:
        return "low_1_2_adds"
    if add_count == 3:
        return "normal_3_adds"
    return "high_4_plus_adds"


def _load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    for path in (ELIGIBILITY_PATH, DAILY_PATH, POSITION_CHANGES_PATH, CANDIDATES_PATH, SUMMARY_PATH):
        _require(path)
    eligibility = _read_csv(ELIGIBILITY_PATH)
    eligibility["eval_date"] = pd.to_datetime(eligibility["eval_date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    eligibility = eligibility.dropna(subset=["eval_date"]).sort_values(["eval_date", "score_rank", "product_vt_symbol"]).reset_index(drop=True)
    for column in ["score", "score_rank", "top_n"]:
        eligibility[column] = pd.to_numeric(eligibility.get(column, 0.0), errors="coerce").fillna(0.0)

    daily = _read_csv(DAILY_PATH)
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    daily = daily.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    for column in ["net_pnl", "balance", "ddpercent", "trade_count", "slippage"]:
        daily[column] = pd.to_numeric(daily.get(column, 0.0), errors="coerce").fillna(0.0)

    positions = _read_csv(POSITION_CHANGES_PATH)
    positions["date"] = pd.to_datetime(positions["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    positions = positions.dropna(subset=["date"]).copy()
    positions["product_vt_symbol"] = positions["vt_symbol"].map(_product_from_contract)
    for column in ["net_pnl", "trade_count", "slippage"]:
        positions[column] = pd.to_numeric(positions.get(column, 0.0), errors="coerce").fillna(0.0)

    candidates = _read_csv(CANDIDATES_PATH)
    candidates["date"] = pd.to_datetime(candidates["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    candidates["ai_product_pool_signal_date"] = pd.to_datetime(
        candidates["ai_product_pool_signal_date"], errors="coerce"
    ).dt.tz_localize(None).dt.normalize()
    for column in ["selected_volume", "ai_product_pool_rank", "ai_product_pool_score", "ai_product_pool_allowed", "is_opened"]:
        candidates[column] = pd.to_numeric(candidates.get(column, 0.0), errors="coerce").fillna(0.0)
    candidates["skip_reason"] = candidates["skip_reason"].fillna("")

    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    return eligibility, daily, positions, candidates, summary


def _build_product_daily(positions: pd.DataFrame) -> pd.DataFrame:
    return (
        positions.groupby(["date", "product_vt_symbol"], as_index=False)
        .agg(product_net_pnl=("net_pnl", "sum"), product_trade_count=("trade_count", "sum"), product_slippage=("slippage", "sum"))
        .sort_values(["date", "product_vt_symbol"])
    )


def _candidate_stats(candidates: pd.DataFrame, signal_date: pd.Timestamp, product: str) -> dict[str, Any]:
    subset = candidates[
        candidates["ai_product_pool_signal_date"].eq(signal_date)
        & candidates["product_vt_symbol"].astype(str).eq(product)
    ].copy()
    if subset.empty:
        return {
            "candidate_count": 0,
            "opened_count": 0,
            "ai_blocked_count": 0,
            "median_selected_volume": 0.0,
        }
    opened = subset[subset["candidate_status"].astype(str).eq("opened")]
    return {
        "candidate_count": int(len(subset)),
        "opened_count": int(len(opened)),
        "ai_blocked_count": int((subset["skip_reason"].astype(str) == "ai_product_pool_blocked").sum()),
        "median_selected_volume": _safe_float(opened["selected_volume"].median()) if not opened.empty else 0.0,
    }


def _period_product_pnl(product_daily: pd.DataFrame, start_date: pd.Timestamp, end_date: pd.Timestamp, product: str) -> dict[str, Any]:
    subset = product_daily[
        (product_daily["date"] > start_date)
        & (product_daily["date"] <= end_date)
        & (product_daily["product_vt_symbol"].astype(str) == product)
    ]
    if subset.empty:
        return {"period_product_net_pnl": 0.0, "period_product_trade_count": 0, "period_product_slippage": 0.0}
    return {
        "period_product_net_pnl": float(subset["product_net_pnl"].sum()),
        "period_product_trade_count": int(subset["product_trade_count"].sum()),
        "period_product_slippage": float(subset["product_slippage"].sum()),
    }


def _build_transition_tables(
    eligibility: pd.DataFrame,
    daily: pd.DataFrame,
    product_daily: pd.DataFrame,
    candidates: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = sorted(pd.Timestamp(value) for value in eligibility["eval_date"].unique())
    max_daily_date = pd.Timestamp(daily["date"].max())
    period_rows: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []

    previous_set: set[str] = set()
    previous_date: pd.Timestamp | None = None
    for index, signal_date in enumerate(dates):
        current = eligibility[eligibility["eval_date"].eq(signal_date)].copy()
        current_set = set(current["product_vt_symbol"].astype(str))
        next_signal_date = pd.Timestamp(dates[index + 1]) if index + 1 < len(dates) else max_daily_date
        if signal_date < pd.Timestamp("2022-01-01"):
            previous_set = current_set
            previous_date = signal_date
            continue

        union_set = current_set | previous_set
        retained = current_set & previous_set
        added = current_set - previous_set
        dropped = previous_set - current_set
        signal_candidates = candidates[candidates["ai_product_pool_signal_date"].eq(signal_date)].copy()
        period_daily = daily[(daily["date"] > signal_date) & (daily["date"] <= next_signal_date)].copy()
        period_products = product_daily[(product_daily["date"] > signal_date) & (product_daily["date"] <= next_signal_date)].copy()

        current_index = current.set_index("product_vt_symbol")
        previous = eligibility[eligibility["eval_date"].eq(previous_date)].copy() if previous_date is not None else pd.DataFrame()
        previous_index = previous.set_index("product_vt_symbol") if not previous.empty else pd.DataFrame()

        for product in sorted(union_set):
            transition = _transition_type(product, current_set, previous_set)
            pnl_stats = _period_product_pnl(product_daily, signal_date, next_signal_date, product)
            cand_stats = _candidate_stats(candidates, signal_date, product)
            current_row = current_index.loc[product] if product in current_index.index else None
            previous_row = previous_index.loc[product] if not previous_index.empty and product in previous_index.index else None
            event_rows.append(
                {
                    "signal_date": signal_date.date().isoformat(),
                    "next_signal_date": next_signal_date.date().isoformat(),
                    "previous_signal_date": previous_date.date().isoformat() if previous_date is not None else "",
                    "is_static_to_ai_boundary": bool(previous_date is not None and previous_date < pd.Timestamp("2022-01-01")),
                    "product_vt_symbol": product,
                    "transition_type": transition,
                    "current_rank": _safe_float(current_row["score_rank"]) if current_row is not None else 0.0,
                    "previous_rank": _safe_float(previous_row["score_rank"]) if previous_row is not None else 0.0,
                    "current_score": _safe_float(current_row["score"]) if current_row is not None else 0.0,
                    "current_score_type": str(current_row["score_type"]) if current_row is not None else "",
                    **pnl_stats,
                    **cand_stats,
                }
            )

        def transition_pnl(kind: str) -> float:
            if period_products.empty:
                return 0.0
            products = {
                "added": added,
                "retained": retained,
                "dropped": dropped,
            }.get(kind, set())
            return float(period_products[period_products["product_vt_symbol"].isin(products)]["product_net_pnl"].sum())

        period_rows.append(
            {
                "signal_date": signal_date.date().isoformat(),
                "next_signal_date": next_signal_date.date().isoformat(),
                "previous_signal_date": previous_date.date().isoformat() if previous_date is not None else "",
                "is_static_to_ai_boundary": bool(previous_date is not None and previous_date < pd.Timestamp("2022-01-01")),
                "pool_size": int(len(current_set)),
                "retained_count": int(len(retained)),
                "added_count": int(len(added)),
                "dropped_count": int(len(dropped)),
                "jaccard_similarity": len(retained) / max(len(current_set | previous_set), 1),
                "turnover_bucket": _turnover_bucket(len(added)),
                "period_net_pnl": float(period_daily["net_pnl"].sum()) if not period_daily.empty else 0.0,
                "period_trade_count": int(period_daily["trade_count"].sum()) if not period_daily.empty else 0,
                "period_slippage": float(period_daily["slippage"].sum()) if not period_daily.empty else 0.0,
                "added_product_net_pnl": transition_pnl("added"),
                "retained_product_net_pnl": transition_pnl("retained"),
                "dropped_product_net_pnl": transition_pnl("dropped"),
                "candidate_count": int(len(signal_candidates)),
                "opened_count": int(signal_candidates["candidate_status"].astype(str).eq("opened").sum()),
                "ai_blocked_count": int((signal_candidates["skip_reason"].astype(str) == "ai_product_pool_blocked").sum()),
                "added_products": ",".join(sorted(added)),
                "dropped_products": ",".join(sorted(dropped)),
            }
        )
        previous_set = current_set
        previous_date = signal_date

    return pd.DataFrame(period_rows), pd.DataFrame(event_rows)


def _summarize_transition_types(events: pd.DataFrame) -> pd.DataFrame:
    steady = events[~events["is_static_to_ai_boundary"].astype(bool)].copy()
    if steady.empty:
        return pd.DataFrame()
    grouped = (
        steady.groupby("transition_type", as_index=False)
        .agg(
            event_count=("product_vt_symbol", "count"),
            total_product_net_pnl=("period_product_net_pnl", "sum"),
            median_product_net_pnl=("period_product_net_pnl", "median"),
            positive_event_rate_pct=("period_product_net_pnl", lambda s: float((s > 0).mean() * 100.0)),
            total_trade_count=("period_product_trade_count", "sum"),
            total_slippage=("period_product_slippage", "sum"),
            candidate_count=("candidate_count", "sum"),
            opened_count=("opened_count", "sum"),
            ai_blocked_count=("ai_blocked_count", "sum"),
        )
        .sort_values("total_product_net_pnl", ascending=False)
    )
    grouped["opened_rate_pct"] = grouped["opened_count"] / grouped["candidate_count"].replace(0, np.nan) * 100.0
    grouped["opened_rate_pct"] = grouped["opened_rate_pct"].fillna(0.0)
    return grouped


def _summarize_products(events: pd.DataFrame) -> pd.DataFrame:
    steady = events[~events["is_static_to_ai_boundary"].astype(bool)].copy()
    if steady.empty:
        return pd.DataFrame()
    grouped = (
        steady.groupby(["product_vt_symbol", "transition_type"], as_index=False)
        .agg(
            event_count=("signal_date", "count"),
            total_product_net_pnl=("period_product_net_pnl", "sum"),
            median_product_net_pnl=("period_product_net_pnl", "median"),
            positive_event_rate_pct=("period_product_net_pnl", lambda s: float((s > 0).mean() * 100.0)),
            candidate_count=("candidate_count", "sum"),
            opened_count=("opened_count", "sum"),
        )
        .sort_values("total_product_net_pnl", ascending=False)
    )
    return grouped


def _summarize_turnover(periods: pd.DataFrame) -> pd.DataFrame:
    steady = periods[~periods["is_static_to_ai_boundary"].astype(bool)].copy()
    if steady.empty:
        return pd.DataFrame()
    grouped = (
        steady.groupby("turnover_bucket", as_index=False)
        .agg(
            period_count=("signal_date", "count"),
            mean_added_count=("added_count", "mean"),
            mean_jaccard_similarity=("jaccard_similarity", "mean"),
            total_period_net_pnl=("period_net_pnl", "sum"),
            mean_period_net_pnl=("period_net_pnl", "mean"),
            total_added_product_net_pnl=("added_product_net_pnl", "sum"),
            total_retained_product_net_pnl=("retained_product_net_pnl", "sum"),
            total_dropped_product_net_pnl=("dropped_product_net_pnl", "sum"),
            mean_ai_blocked_count=("ai_blocked_count", "mean"),
            mean_opened_count=("opened_count", "mean"),
        )
        .sort_values("mean_added_count")
    )
    return grouped


def build_payload() -> dict[str, Any]:
    eligibility, daily, positions, candidates, summary = _load_inputs()
    product_daily = _build_product_daily(positions)
    periods, events = _build_transition_tables(eligibility, daily, product_daily, candidates)
    transition_type = _summarize_transition_types(events)
    product_summary = _summarize_products(events)
    turnover_bucket = _summarize_turnover(periods)
    steady_periods = periods[~periods["is_static_to_ai_boundary"].astype(bool)].copy()

    periods.to_csv(SIGNAL_PERIOD_PATH, index=False, encoding="utf-8-sig")
    events.to_csv(TRANSITION_EVENTS_PATH, index=False, encoding="utf-8-sig")
    transition_type.to_csv(TRANSITION_TYPE_PATH, index=False, encoding="utf-8-sig")
    product_summary.to_csv(PRODUCT_TRANSITION_PATH, index=False, encoding="utf-8-sig")
    turnover_bucket.to_csv(TURNOVER_BUCKET_PATH, index=False, encoding="utf-8-sig")

    correlations: dict[str, float] = {}
    if len(steady_periods) >= 3:
        corr_columns = [
            "period_net_pnl",
            "added_count",
            "dropped_count",
            "jaccard_similarity",
            "added_product_net_pnl",
            "retained_product_net_pnl",
            "ai_blocked_count",
            "opened_count",
        ]
        corr = steady_periods[corr_columns].corr(numeric_only=True)["period_net_pnl"].dropna()
        correlations = {str(key): float(value) for key, value in corr.items()}

    official_metrics = dict(summary["reference_metrics"]["full_2020_2026"])
    official_metrics["win_ratio_pct"] = summary["experiments"][0].get("win_ratio_pct", 0.0)
    steady_totals = {
        "steady_period_count": int(len(steady_periods)),
        "total_period_net_pnl": float(steady_periods["period_net_pnl"].sum()) if not steady_periods.empty else 0.0,
        "total_added_product_net_pnl": float(steady_periods["added_product_net_pnl"].sum()) if not steady_periods.empty else 0.0,
        "total_retained_product_net_pnl": float(steady_periods["retained_product_net_pnl"].sum()) if not steady_periods.empty else 0.0,
        "total_dropped_product_net_pnl": float(steady_periods["dropped_product_net_pnl"].sum()) if not steady_periods.empty else 0.0,
        "mean_added_count": float(steady_periods["added_count"].mean()) if not steady_periods.empty else 0.0,
        "mean_jaccard_similarity": float(steady_periods["jaccard_similarity"].mean()) if not steady_periods.empty else 0.0,
    }

    judgement = {
        "pool_level_stability_rule": "STOP_FOR_NOW",
        "reason": (
            "历史上新增品种和高换手月份贡献显著，降低全局换手或强行保留旧池容易伤害趋势响应；"
            "后续若继续，只能研究新增品种质量审计，而不是池级慢更新或硬稳定规则。"
        ),
    }

    return {
        "model_tag": MODEL_TAG,
        "base_version": summary.get("official_version", "official_stage78_defensive_v1"),
        "analysis_type": "ai_pool_switch_stability_attribution_only",
        "official_metrics": official_metrics,
        "steady_totals": steady_totals,
        "correlations_vs_period_net_pnl": correlations,
        "judgement": judgement,
        "signal_period_summary": periods.to_dict(orient="records"),
        "transition_type_summary": transition_type.to_dict(orient="records"),
        "product_transition_summary_top": product_summary.head(30).to_dict(orient="records"),
        "product_transition_summary_bottom": product_summary.sort_values("total_product_net_pnl").head(20).to_dict(orient="records"),
        "turnover_bucket_summary": turnover_bucket.to_dict(orient="records"),
        "artifacts": {
            "signal_period_summary": str(SIGNAL_PERIOD_PATH),
            "transition_events": str(TRANSITION_EVENTS_PATH),
            "transition_type_summary": str(TRANSITION_TYPE_PATH),
            "product_transition_summary": str(PRODUCT_TRANSITION_PATH),
            "turnover_bucket_summary": str(TURNOVER_BUCKET_PATH),
            "summary": str(SUMMARY_JSON_PATH),
            "report": str(REPORT_PATH),
        },
    }


def build_report(payload: dict[str, Any]) -> str:
    metrics = payload["official_metrics"]
    totals = payload["steady_totals"]
    periods = pd.DataFrame(payload["signal_period_summary"])
    steady_periods = periods[~periods["is_static_to_ai_boundary"].astype(bool)].copy() if not periods.empty else periods
    transition_type = pd.DataFrame(payload["transition_type_summary"])
    turnover_bucket = pd.DataFrame(payload["turnover_bucket_summary"])
    top_products = pd.DataFrame(payload["product_transition_summary_top"])
    bottom_products = pd.DataFrame(payload["product_transition_summary_bottom"])
    correlations = pd.DataFrame(
        [{"metric": key, "corr_vs_period_net_pnl": value} for key, value in payload["correlations_vs_period_net_pnl"].items()]
    ).sort_values("corr_vs_period_net_pnl", ascending=False)

    worst_periods = steady_periods.sort_values("period_net_pnl").head(10) if not steady_periods.empty else pd.DataFrame()
    best_periods = steady_periods.sort_values("period_net_pnl", ascending=False).head(10) if not steady_periods.empty else pd.DataFrame()

    return "\n".join(
        [
            f"# {MODEL_TAG}",
            "",
            "## 边界",
            "",
            f"- 基准版本：`{payload['base_version']}`。",
            "- 本阶段只做AI品种池切换归因，不修改TopN、不训练模型、不新增交易规则、不跑新策略回测。",
            "- 自然观察期定义为每个AI池`eval_date`到下一个`eval_date`之间，避免按结果挑月份。",
            "",
            "## 结论",
            "",
            "- 池级“降低换手/强行稳定”暂时停止，不建议作为下一条正式研究线。",
            "- 原因不是它一定无效，而是历史证据相反：新增品种和高换手月份贡献了大量利润，强行稳定可能削弱趋势地形变化的响应速度。",
            "- 这也解释了Stage133慢更新为什么失败：问题不是月更太频繁，而是不能用低频持有替代趋势系统对新地形的响应。",
            "- 后续如果继续AI池方向，应研究“新增品种质量审计/执行约束”，不是全局慢更新或旧池保留。",
            "",
            "## Stage78正式基准",
            "",
            f"- 期末权益：`{_fmt(metrics['end_balance'])}`",
            f"- 总收益：`{float(metrics['total_return_pct']):.4f}%`",
            f"- 最大回撤：`{float(metrics['max_dd_percent']):.4f}%`",
            f"- Sharpe：`{float(metrics['sharpe_ratio']):.4f}`",
            f"- 总滑点：`{_fmt(metrics['total_slippage'])}`",
            f"- 总交易次数：`{int(float(metrics['total_trade_count'])):,}`",
            f"- 胜率：`{float(metrics['win_ratio_pct']):.4f}%`",
            "",
            "## 稳态AI切换总览",
            "",
            f"- 稳态信号期数量：`{totals['steady_period_count']}`",
            f"- 信号期总净损益：`{_fmt(totals['total_period_net_pnl'])}`",
            f"- 新增品种贡献：`{_fmt(totals['total_added_product_net_pnl'])}`",
            f"- 保留品种贡献：`{_fmt(totals['total_retained_product_net_pnl'])}`",
            f"- 剔除品种在后续期间贡献：`{_fmt(totals['total_dropped_product_net_pnl'])}`",
            f"- 平均每期新增品种数：`{totals['mean_added_count']:.2f}`",
            f"- 平均Jaccard稳定度：`{totals['mean_jaccard_similarity']:.4f}`",
            "",
            "## 换手桶表现",
            "",
            _to_markdown_table(
                turnover_bucket,
                [
                    "turnover_bucket",
                    "period_count",
                    "mean_added_count",
                    "mean_jaccard_similarity",
                    "total_period_net_pnl",
                    "mean_period_net_pnl",
                    "total_added_product_net_pnl",
                    "total_retained_product_net_pnl",
                    "total_dropped_product_net_pnl",
                ],
            ),
            "",
            "## 切换类型表现",
            "",
            _to_markdown_table(
                transition_type,
                [
                    "transition_type",
                    "event_count",
                    "total_product_net_pnl",
                    "median_product_net_pnl",
                    "positive_event_rate_pct",
                    "total_trade_count",
                    "total_slippage",
                    "candidate_count",
                    "opened_count",
                    "opened_rate_pct",
                ],
            ),
            "",
            "## 相关性诊断",
            "",
            _to_markdown_table(correlations, ["metric", "corr_vs_period_net_pnl"]),
            "",
            "## 最好信号期",
            "",
            _to_markdown_table(
                best_periods,
                [
                    "signal_date",
                    "next_signal_date",
                    "added_count",
                    "dropped_count",
                    "jaccard_similarity",
                    "period_net_pnl",
                    "added_product_net_pnl",
                    "retained_product_net_pnl",
                    "added_products",
                ],
            ),
            "",
            "## 最差信号期",
            "",
            _to_markdown_table(
                worst_periods,
                [
                    "signal_date",
                    "next_signal_date",
                    "added_count",
                    "dropped_count",
                    "jaccard_similarity",
                    "period_net_pnl",
                    "added_product_net_pnl",
                    "retained_product_net_pnl",
                    "added_products",
                ],
            ),
            "",
            "## 主要正贡献切换事件",
            "",
            _to_markdown_table(
                top_products,
                [
                    "product_vt_symbol",
                    "transition_type",
                    "event_count",
                    "total_product_net_pnl",
                    "median_product_net_pnl",
                    "positive_event_rate_pct",
                    "candidate_count",
                    "opened_count",
                ],
                max_rows=15,
            ),
            "",
            "## 主要负贡献切换事件",
            "",
            _to_markdown_table(
                bottom_products,
                [
                    "product_vt_symbol",
                    "transition_type",
                    "event_count",
                    "total_product_net_pnl",
                    "median_product_net_pnl",
                    "positive_event_rate_pct",
                    "candidate_count",
                    "opened_count",
                ],
                max_rows=15,
            ),
            "",
            "## 判断",
            "",
            "- 不要做池级稳定规则：例如新增品种冷却、旧品种强制保留、全局降低换手，这些都容易重演Stage133的问题。",
            "- 也不要反向过拟合成“高换手越高越好”：相关性只是描述，不是可交易因果。",
            "- 最低过拟合的下一步是做新增品种质量审计：只观察新增品种在开仓前的分数跳变、成交量、相关性、候选漏斗和实盘滑点，不直接改TopN。",
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
                "analysis_type": payload["analysis_type"],
                "pool_level_stability_rule": payload["judgement"]["pool_level_stability_rule"],
                "steady_totals": payload["steady_totals"],
                "report": str(REPORT_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
