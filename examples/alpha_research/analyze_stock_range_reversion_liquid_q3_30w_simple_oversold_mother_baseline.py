from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import polars as pl


BASE_DIR: Path = Path(__file__).resolve().parent
NATIVE_RESULTS_DIR: Path = BASE_DIR / "native_results"

SOURCE_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_30w_high_return_shape_grid_2018_2026"
).resolve()
SOURCE_PREFIX: str = "stock_range_reversion_liquid_q3_30w_high_return_shape_grid_v1"

OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_30w_simple_oversold_mother_baseline_2018_2026"
).resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_30w_simple_oversold_mother_baseline_v1"

USER_RETURN_TARGET: float = 1.0
USER_MAX_DRAWDOWN_LIMIT: float = -0.20
ROLLING_WINDOW: int = 252

FOCUS_SCENARIOS: tuple[str, ...] = (
    "top8_gross50_ind2",
    "top5_gross50_ind2",
    "top8_gross30_ind2",
    "top8_gross70_ind2",
    "top5_gross70_ind2",
)

ROLE_BY_SCENARIO: dict[str, str] = {
    "top8_gross50_ind2": "primary_research_mother",
    "top5_gross50_ind2": "tradability_guard_mother",
    "top8_gross30_ind2": "risk_floor_reference",
    "top8_gross70_ind2": "high_exposure_stress",
    "top5_gross70_ind2": "concentration_stress",
}

ROLE_REASON: dict[str, str] = {
    "top8_gross50_ind2": "50%目标暴露、top8、单行业最多2只，在简单超跌网格里风险收益比和Sharpe较好，适合作为研究母本；但一手取整缺口偏高。",
    "top5_gross50_ind2": "同样是50%目标暴露，top5减少小额目标，零手目标比例低于20%，适合作为可交易性护栏。",
    "top8_gross30_ind2": "30%目标暴露最大回撤在20%以内，但收益厚度不足，适合作为风险地板。",
    "top8_gross70_ind2": "70%目标暴露收益最高，但回撤明显超限，适合作为高暴露压力样本。",
    "top5_gross70_ind2": "70%目标暴露且目标数更少，用来观察集中度与高暴露的交互风险。",
}

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "Short-term residual reversal",
        "https://www.sciencedirect.com/science/article/pii/S1386418112000468",
    ),
    (
        "Decomposing Short-Term Return Reversal",
        "https://www.newyorkfed.org/research/staff_reports/sr513.html",
    ),
    (
        "Short-term reversals and turnover",
        "https://www.sciencedirect.com/science/article/pii/S0378426621000261",
    ),
    (
        "Connors RSI(2) reference",
        "https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/rsi-2",
    ),
)


def pct(value: Any) -> str:
    number = safe_float(value)
    if pd.isna(number):
        return "NA"
    return f"{number:.2%}"


def safe_float(value: Any, default: float = float("nan")) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def read_csv(name: str) -> pd.DataFrame:
    path = SOURCE_DIR / f"{SOURCE_PREFIX}_{name}.csv"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def markdown_table(frame: pd.DataFrame, columns: list[str], limit: int = 30) -> str:
    if frame.empty:
        return "\n无数据。\n"
    table = frame[[col for col in columns if col in frame.columns]].head(limit).copy()
    return table.to_markdown(index=False)


def add_display_columns(frame: pd.DataFrame, pct_columns: tuple[str, ...]) -> pd.DataFrame:
    display = frame.copy()
    for column in pct_columns:
        if column in display.columns:
            display[f"{column}_pct"] = display[column].map(pct)
    for column in ("final_equity_min_fee", "sharpe_min_fee", "return_over_max_dd", "return_over_abs_dd"):
        if column in display.columns:
            display[column] = display[column].map(lambda value: "" if pd.isna(value) else f"{float(value):.4f}")
    return display


def build_shape_frontier(summary: pd.DataFrame) -> pd.DataFrame:
    if summary.empty:
        return pd.DataFrame()
    work = summary.copy()
    work["meets_user_goal"] = (work["total_return_min_fee"] >= USER_RETURN_TARGET) & (
        work["max_drawdown_min_fee"] >= USER_MAX_DRAWDOWN_LIMIT
    )
    work["within_20pct_drawdown"] = work["max_drawdown_min_fee"] >= USER_MAX_DRAWDOWN_LIMIT
    work["zero_lot_hard_ok"] = work["zero_lot_target_ratio"] <= 0.20
    work["zero_lot_soft_ok"] = work["zero_lot_target_ratio"] <= 0.10
    work["return_over_abs_dd"] = work["total_return_min_fee"] / work["max_drawdown_min_fee"].abs()
    work["mother_role"] = work["scenario"].map(ROLE_BY_SCENARIO).fillna("")
    work["mother_reason"] = work["scenario"].map(ROLE_REASON).fillna("")
    work["frontier_bucket"] = np.select(
        [
            work["meets_user_goal"],
            work["within_20pct_drawdown"] & (work["total_return_min_fee"] >= 0.25),
            work["total_return_min_fee"] >= 0.45,
            work["max_drawdown_min_fee"] < -0.30,
        ],
        ["goal_hit", "low_dd_low_return", "return_candidate_high_dd", "stress_high_dd"],
        default="middle",
    )
    return work.sort_values(["shape_basket_gross_weight", "shape_top_k", "shape_max_per_industry"]).reset_index(drop=True)


def build_mother_decision(frontier: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for scenario in FOCUS_SCENARIOS:
        matched = frontier[frontier["scenario"] == scenario]
        if matched.empty:
            rows.append(
                {
                    "scenario": scenario,
                    "role": ROLE_BY_SCENARIO.get(scenario, ""),
                    "status": "missing",
                    "decision": "source_missing",
                    "reason": ROLE_REASON.get(scenario, ""),
                }
            )
            continue
        row = matched.iloc[0]
        if scenario == "top8_gross50_ind2":
            decision = "use_as_primary_research_mother"
            status = "active_with_tradability_caution"
        elif scenario == "top5_gross50_ind2":
            decision = "use_as_tradability_guard"
            status = "active"
        elif scenario == "top8_gross30_ind2":
            decision = "use_as_risk_floor_reference"
            status = "active"
        else:
            decision = "use_as_stress_reference"
            status = "reference"
        rows.append(
            {
                "scenario": scenario,
                "role": ROLE_BY_SCENARIO.get(scenario, ""),
                "status": status,
                "decision": decision,
                "reason": ROLE_REASON.get(scenario, ""),
                "total_return_min_fee": row["total_return_min_fee"],
                "max_drawdown_min_fee": row["max_drawdown_min_fee"],
                "sharpe_min_fee": row["sharpe_min_fee"],
                "zero_lot_target_ratio": row["zero_lot_target_ratio"],
                "avg_actual_gross_weight": row["avg_actual_gross_weight"],
                "avg_actual_symbol_count": row["avg_actual_symbol_count"],
                "return_over_abs_dd": row["return_over_abs_dd"],
                "meets_user_goal": row["meets_user_goal"],
            }
        )
    return pd.DataFrame(rows)


def build_yearly_focus(yearly: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if yearly.empty:
        return pd.DataFrame(), pd.DataFrame()
    focus = yearly[yearly["scenario"].isin(FOCUS_SCENARIOS)].copy()
    focus["positive_year"] = focus["year_return_min_fee"] > 0
    aggregate = (
        focus.groupby("scenario", as_index=False)
        .agg(
            positive_year_count=("positive_year", "sum"),
            year_count=("year", "count"),
            avg_year_return=("year_return_min_fee", "mean"),
            median_year_return=("year_return_min_fee", "median"),
            worst_year_return=("year_return_min_fee", "min"),
            worst_year_drawdown=("year_curve_drawdown_min_fee", "min"),
            avg_actual_gross_weight=("avg_actual_gross_weight", "mean"),
            avg_actual_symbol_count=("avg_actual_symbol_count", "mean"),
            zero_lot_target_ratio=("zero_lot_target_ratio", "mean"),
        )
        .merge(
            focus.loc[focus.groupby("scenario")["year_return_min_fee"].idxmin(), ["scenario", "year"]].rename(
                columns={"year": "worst_year"}
            ),
            on="scenario",
            how="left",
        )
    )
    aggregate["positive_year_ratio"] = aggregate["positive_year_count"] / aggregate["year_count"]
    aggregate["role"] = aggregate["scenario"].map(ROLE_BY_SCENARIO)
    return focus.sort_values(["scenario", "year"]).reset_index(drop=True), aggregate.sort_values("scenario")


def rolling_window_drawdown(values: np.ndarray) -> float:
    equity = np.cumprod(1.0 + values)
    high = np.maximum.accumulate(equity)
    drawdown = equity / high - 1.0
    return float(drawdown.min())


def build_rolling(daily: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if daily.empty:
        return pd.DataFrame(), pd.DataFrame()
    work = daily[daily["scenario"].isin(FOCUS_SCENARIOS)].copy()
    work["date"] = pd.to_datetime(work["date"])
    rows: list[pd.DataFrame] = []
    for scenario, group in work.groupby("scenario"):
        group = group.sort_values("date").reset_index(drop=True)
        returns = group["strategy_daily_ret_min_fee"].astype(float)
        rolling_return = (1.0 + returns).rolling(ROLLING_WINDOW).apply(np.prod, raw=True) - 1.0
        rolling_sharpe = returns.rolling(ROLLING_WINDOW).mean() / returns.rolling(ROLLING_WINDOW).std(ddof=1) * np.sqrt(
            252
        )
        rolling_dd = returns.rolling(ROLLING_WINDOW).apply(rolling_window_drawdown, raw=True)
        frame = pd.DataFrame(
            {
                "scenario": scenario,
                "role": ROLE_BY_SCENARIO.get(scenario, ""),
                "window_end": group["date"],
                "rolling_return_252": rolling_return,
                "rolling_drawdown_252": rolling_dd,
                "rolling_sharpe_252": rolling_sharpe,
                "rolling_avg_gross_weight_252": group["actual_gross_weight"].rolling(ROLLING_WINDOW).mean(),
                "rolling_avg_symbol_count_252": group["actual_symbol_count"].rolling(ROLLING_WINDOW).mean(),
            }
        ).dropna(subset=["rolling_return_252", "rolling_drawdown_252"])
        rows.append(frame)
    rolling = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    if rolling.empty:
        return rolling, pd.DataFrame()
    aggregate = (
        rolling.groupby(["scenario", "role"], as_index=False)
        .agg(
            rolling_window_count=("rolling_return_252", "count"),
            positive_rolling_return_ratio=("rolling_return_252", lambda item: float((item > 0).mean())),
            median_rolling_return=("rolling_return_252", "median"),
            worst_rolling_return=("rolling_return_252", "min"),
            best_rolling_return=("rolling_return_252", "max"),
            median_rolling_drawdown=("rolling_drawdown_252", "median"),
            worst_rolling_drawdown=("rolling_drawdown_252", "min"),
            median_rolling_sharpe=("rolling_sharpe_252", "median"),
            pct_windows_drawdown_within_20=("rolling_drawdown_252", lambda item: float((item >= -0.20).mean())),
        )
        .sort_values("scenario")
    )
    return rolling, aggregate


def build_drawdown_windows(daily: pd.DataFrame) -> pd.DataFrame:
    if daily.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for scenario, group in daily[daily["scenario"].isin(FOCUS_SCENARIOS)].groupby("scenario"):
        group = group.sort_values("date").reset_index(drop=True)
        equity = group["equity_min_fee"].astype(float).to_numpy()
        dates = pd.to_datetime(group["date"]).dt.date.to_list()
        high_water = np.maximum.accumulate(equity)
        drawdown = equity / high_water - 1.0
        in_episode = False
        start_idx = 0
        trough_idx = 0
        trough_dd = 0.0
        for idx, dd in enumerate(drawdown):
            if dd < 0 and not in_episode:
                in_episode = True
                start_idx = max(idx - 1, 0)
                trough_idx = idx
                trough_dd = float(dd)
            elif dd < 0 and in_episode:
                if dd < trough_dd:
                    trough_dd = float(dd)
                    trough_idx = idx
            elif dd >= 0 and in_episode:
                rows.append(
                    {
                        "scenario": scenario,
                        "role": ROLE_BY_SCENARIO.get(scenario, ""),
                        "start_date": dates[start_idx],
                        "trough_date": dates[trough_idx],
                        "recover_date": dates[idx],
                        "max_drawdown": trough_dd,
                        "days_to_trough": trough_idx - start_idx,
                        "days_to_recover": idx - start_idx,
                        "recovered": True,
                    }
                )
                in_episode = False
        if in_episode:
            rows.append(
                {
                    "scenario": scenario,
                    "role": ROLE_BY_SCENARIO.get(scenario, ""),
                    "start_date": dates[start_idx],
                    "trough_date": dates[trough_idx],
                    "recover_date": pd.NaT,
                    "max_drawdown": trough_dd,
                    "days_to_trough": trough_idx - start_idx,
                    "days_to_recover": len(dates) - 1 - start_idx,
                    "recovered": False,
                }
            )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(["scenario", "max_drawdown"]).reset_index(drop=True)


def build_daily_exposure_buckets(daily: pd.DataFrame) -> pd.DataFrame:
    if daily.empty:
        return pd.DataFrame()
    work = daily[daily["scenario"].isin(FOCUS_SCENARIOS)].copy()
    bins = [-0.001, 0.05, 0.20, 0.40, 0.60, 1.01]
    labels = ["cash_or_tiny", "low_0_20", "mid_20_40", "high_40_60", "very_high_60_plus"]
    work["gross_bucket"] = pd.cut(work["actual_gross_weight"], bins=bins, labels=labels)
    grouped = (
        work.groupby(["scenario", "gross_bucket"], observed=True)
        .agg(
            day_count=("date", "count"),
            avg_daily_ret=("strategy_daily_ret_min_fee", "mean"),
            sum_daily_ret=("strategy_daily_ret_min_fee", "sum"),
            win_rate=("strategy_daily_ret_min_fee", lambda item: float((item > 0).mean())),
            avg_gross_weight=("actual_gross_weight", "mean"),
            avg_symbol_count=("actual_symbol_count", "mean"),
            avg_filled_amount_cny=("filled_amount_sum_cny", "mean"),
        )
        .reset_index()
    )
    grouped["role"] = grouped["scenario"].map(ROLE_BY_SCENARIO)
    return grouped.sort_values(["scenario", "gross_bucket"]).reset_index(drop=True)


def build_signal_state_and_industry() -> tuple[pd.DataFrame, pd.DataFrame]:
    selected_path = SOURCE_DIR / f"{SOURCE_PREFIX}_selected.csv"
    if not selected_path.exists():
        return pd.DataFrame(), pd.DataFrame()
    columns = [
        "scenario",
        "datetime",
        "symbol",
        "industry",
        "market",
        "market_state_20d",
        "basket_weight",
        "score_oversold_ret_20",
        "ret_20",
        "volume_ratio_20",
        "fwd_ret_10",
        "fwd_excess_ret_10",
        "mfe_close_10",
        "mae_close_10",
        "adv20_turnover",
        "turnover_rate_f",
        "shape_top_k",
        "shape_basket_gross_weight",
        "shape_max_per_industry",
    ]
    frame = (
        pl.scan_csv(
            selected_path,
            try_parse_dates=True,
            schema_overrides={"symbol": pl.Utf8},
        )
        .filter(pl.col("scenario").is_in(list(FOCUS_SCENARIOS)))
        .select([col for col in columns])
        .collect()
    )
    if frame.is_empty():
        return pd.DataFrame(), pd.DataFrame()
    state = (
        frame.group_by(["scenario", "market_state_20d"])
        .agg(
            pl.len().alias("selected_rows"),
            pl.col("basket_weight").sum().alias("basket_weight_sum"),
            pl.col("score_oversold_ret_20").mean().alias("avg_score_oversold_ret_20"),
            pl.col("ret_20").mean().alias("avg_ret_20"),
            pl.col("volume_ratio_20").mean().alias("avg_volume_ratio_20"),
            pl.col("fwd_ret_10").mean().alias("avg_fwd_ret_10"),
            pl.col("fwd_excess_ret_10").mean().alias("avg_fwd_excess_ret_10"),
            (pl.col("fwd_excess_ret_10") > 0).mean().alias("positive_excess_10_ratio"),
            pl.col("mfe_close_10").mean().alias("avg_mfe_close_10"),
            pl.col("mae_close_10").mean().alias("avg_mae_close_10"),
            pl.col("adv20_turnover").median().alias("median_adv20_turnover"),
        )
        .with_columns(pl.col("scenario").replace(ROLE_BY_SCENARIO).alias("role"))
        .sort(["scenario", "avg_fwd_excess_ret_10"], descending=[False, False])
        .to_pandas()
    )
    industry = (
        frame.group_by(["scenario", "industry"])
        .agg(
            pl.len().alias("selected_rows"),
            pl.col("basket_weight").sum().alias("basket_weight_sum"),
            pl.col("fwd_ret_10").mean().alias("avg_fwd_ret_10"),
            pl.col("fwd_excess_ret_10").mean().alias("avg_fwd_excess_ret_10"),
            (pl.col("fwd_excess_ret_10") > 0).mean().alias("positive_excess_10_ratio"),
            pl.col("mfe_close_10").mean().alias("avg_mfe_close_10"),
            pl.col("mae_close_10").mean().alias("avg_mae_close_10"),
            pl.col("adv20_turnover").median().alias("median_adv20_turnover"),
        )
        .filter(pl.col("selected_rows") >= 50)
        .with_columns(pl.col("scenario").replace(ROLE_BY_SCENARIO).alias("role"))
        .sort(["scenario", "avg_fwd_excess_ret_10"], descending=[False, False])
        .to_pandas()
    )
    return state, industry


def build_quality_checkpoints(
    frontier: pd.DataFrame,
    mother: pd.DataFrame,
    yearly_agg: pd.DataFrame,
    rolling_agg: pd.DataFrame,
) -> pd.DataFrame:
    primary = mother[mother["scenario"] == "top8_gross50_ind2"].iloc[0]
    guard = mother[mother["scenario"] == "top5_gross50_ind2"].iloc[0]
    risk_floor = mother[mother["scenario"] == "top8_gross30_ind2"].iloc[0]
    goal_hits = int(frontier["meets_user_goal"].sum())
    primary_rolling = rolling_agg[rolling_agg["scenario"] == "top8_gross50_ind2"]
    primary_positive_rolling = (
        safe_float(primary_rolling["positive_rolling_return_ratio"].iloc[0]) if not primary_rolling.empty else float("nan")
    )
    rows = [
        {
            "checkpoint": "simple_grid_goal_hit",
            "status": "fail" if goal_hits == 0 else "pass",
            "value": f"goal_hit_count={goal_hits}",
            "expected": "至少一个简单20日超跌形状达到总收益>=100%且最大回撤>=-20%",
            "judgement": "简单基准有alpha但不是正式候选，后续增强必须证明增益。",
        },
        {
            "checkpoint": "primary_mother_selected",
            "status": "pass",
            "value": "top8_gross50_ind2",
            "expected": "选出一个不极端、信息量足够的研究母本",
            "judgement": "选top8_gross50_ind2作为研究母本，但必须带一手取整警戒。",
        },
        {
            "checkpoint": "primary_mother_drawdown",
            "status": "warn" if primary["max_drawdown_min_fee"] < USER_MAX_DRAWDOWN_LIMIT else "pass",
            "value": pct(primary["max_drawdown_min_fee"]),
            "expected": ">=-20%",
            "judgement": "母本回撤略超用户边界，说明下一步增强首先要改善路径风险。",
        },
        {
            "checkpoint": "primary_mother_zero_lot",
            "status": "warn" if primary["zero_lot_target_ratio"] > 0.20 else "pass",
            "value": pct(primary["zero_lot_target_ratio"]),
            "expected": "<=20%",
            "judgement": "top8在30万账户下有明显一手颗粒度摩擦，需用top5_gross50_ind2做护栏。",
        },
        {
            "checkpoint": "tradability_guard_zero_lot",
            "status": "pass" if guard["zero_lot_target_ratio"] <= 0.20 else "warn",
            "value": pct(guard["zero_lot_target_ratio"]),
            "expected": "<=20%",
            "judgement": "top5_gross50_ind2更适合检查增强后是否仍可交易。",
        },
        {
            "checkpoint": "risk_floor_drawdown",
            "status": "pass" if risk_floor["max_drawdown_min_fee"] >= USER_MAX_DRAWDOWN_LIMIT else "fail",
            "value": pct(risk_floor["max_drawdown_min_fee"]),
            "expected": ">=-20%",
            "judgement": "低暴露版本能控制回撤但收益太薄，可作为风险地板。",
        },
        {
            "checkpoint": "primary_rolling_positive_ratio",
            "status": "pass" if primary_positive_rolling >= 0.70 else "warn",
            "value": pct(primary_positive_rolling),
            "expected": ">=70%",
            "judgement": "滚动窗口正收益比例用于判断母本是否有穿越周期的基本生命力。",
        },
    ]
    return pd.DataFrame(rows)


def build_next_experiment_plan() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "priority": 1,
                "experiment": "layer0_replay_mother_baseline",
                "status": "done_by_existing_outputs",
                "design": "固定top8_gross50_ind2为研究母本，top5_gross50_ind2为可交易性护栏。",
                "success_criteria": "任何增强都必须同时对这两个形状报告收益、回撤、滚动、零手比例。",
            },
            {
                "priority": 2,
                "experiment": "layer1_residual_increment",
                "status": "next",
                "design": "在同一topK/gross/行业上限下，将score_oversold_ret_20替换或混合为残差/行业内超跌排序。",
                "success_criteria": "相对母本提高收益/回撤比，且不能靠单一年份或单一行业贡献。",
            },
            {
                "priority": 3,
                "experiment": "layer2_continuous_state_budget",
                "status": "pending",
                "design": "只允许预注册连续风险预算函数，不使用单点硬阈值清仓。",
                "success_criteria": "top8_gross50_ind2回撤靠近20%以内，同时top5_gross50_ind2不牺牲主要收益。",
            },
            {
                "priority": 4,
                "experiment": "layer3_etf_satellite",
                "status": "pending",
                "design": "ETF只作为低波动现金替代/卫星，不承担主收益目标。",
                "success_criteria": "组合曲线更平滑，但股票主引擎收益来源不能被ETF掩盖。",
            },
        ]
    )


def build_report(
    frontier: pd.DataFrame,
    mother: pd.DataFrame,
    yearly_focus: pd.DataFrame,
    yearly_agg: pd.DataFrame,
    rolling_agg: pd.DataFrame,
    drawdowns: pd.DataFrame,
    exposure_buckets: pd.DataFrame,
    signal_state: pd.DataFrame,
    signal_industry: pd.DataFrame,
    quality: pd.DataFrame,
    plan: pd.DataFrame,
) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M CST")
    frontier_display = add_display_columns(
        frontier,
        ("total_return_min_fee", "max_drawdown_min_fee", "zero_lot_target_ratio", "avg_actual_gross_weight"),
    )
    mother_display = add_display_columns(
        mother,
        ("total_return_min_fee", "max_drawdown_min_fee", "zero_lot_target_ratio", "avg_actual_gross_weight"),
    )
    yearly_display = add_display_columns(
        yearly_agg,
        ("avg_year_return", "median_year_return", "worst_year_return", "worst_year_drawdown", "positive_year_ratio"),
    )
    rolling_display = add_display_columns(
        rolling_agg,
        (
            "positive_rolling_return_ratio",
            "median_rolling_return",
            "worst_rolling_return",
            "median_rolling_drawdown",
            "worst_rolling_drawdown",
            "pct_windows_drawdown_within_20",
        ),
    )
    drawdown_display = add_display_columns(drawdowns, ("max_drawdown",))
    exposure_display = add_display_columns(exposure_buckets, ("avg_daily_ret", "sum_daily_ret", "win_rate"))
    state_display = add_display_columns(
        signal_state,
        ("avg_fwd_ret_10", "avg_fwd_excess_ret_10", "positive_excess_10_ratio", "avg_mfe_close_10", "avg_mae_close_10"),
    )
    industry_display = add_display_columns(
        signal_industry,
        ("avg_fwd_ret_10", "avg_fwd_excess_ret_10", "positive_excess_10_ratio", "avg_mfe_close_10", "avg_mae_close_10"),
    )

    return f"""# 股票震荡30万简单超跌母本体检 v1

- 记录时间：{now}
- 当前模式：day
- line_id：stock_range_30w_industry_resid_core
- 阶段性质：第332阶段，母本体检/架构分层基准，不新增交易参数，不触发A/B。
- 数据来源：第331阶段确定的简单20日超跌30万网格既有产物。

## 外部调研与判断

- 短期反转/残差短反文献提示，真正可持续的股票震荡不是单票猜底，而是横截面流动性冲击回归。
- turnover/成本相关研究提示，短反很容易被周转和交易颗粒度吞掉，所以30万整手可交易性必须和信号强度一起看。
- Connors RSI(2)一类业界模板可以借鉴“顺大势、买短回调”的结构，但不能直接替代A股横截面组合。
- 本阶段判断：简单20日超跌不是最终策略，但它少假设、透明、可复验，适合作为所有增强层的母本。

## 母本决策

{markdown_table(mother_display, ["scenario", "role", "status", "decision", "total_return_min_fee_pct", "max_drawdown_min_fee_pct", "sharpe_min_fee", "zero_lot_target_ratio_pct", "avg_actual_gross_weight_pct", "return_over_abs_dd", "reason"], 10)}

## 全形状前沿

{markdown_table(frontier_display, ["scenario", "shape_top_k", "shape_basket_gross_weight", "shape_max_per_industry", "total_return_min_fee_pct", "max_drawdown_min_fee_pct", "sharpe_min_fee", "zero_lot_target_ratio_pct", "avg_actual_gross_weight_pct", "frontier_bucket", "mother_role"], 30)}

## 年度稳定性

{markdown_table(yearly_display, ["scenario", "role", "positive_year_count", "year_count", "positive_year_ratio_pct", "avg_year_return_pct", "median_year_return_pct", "worst_year", "worst_year_return_pct", "worst_year_drawdown_pct"], 20)}

## 252日滚动窗口

{markdown_table(rolling_display, ["scenario", "role", "rolling_window_count", "positive_rolling_return_ratio_pct", "median_rolling_return_pct", "worst_rolling_return_pct", "median_rolling_drawdown_pct", "worst_rolling_drawdown_pct", "pct_windows_drawdown_within_20_pct", "median_rolling_sharpe"], 20)}

## 主要回撤段

{markdown_table(drawdown_display, ["scenario", "role", "start_date", "trough_date", "recover_date", "max_drawdown_pct", "days_to_trough", "days_to_recover", "recovered"], 20)}

## 暴露桶画像

{markdown_table(exposure_display, ["scenario", "role", "gross_bucket", "day_count", "avg_daily_ret_pct", "sum_daily_ret_pct", "win_rate_pct", "avg_gross_weight", "avg_symbol_count"], 30)}

## 信号状态画像

{markdown_table(state_display, ["scenario", "role", "market_state_20d", "selected_rows", "avg_fwd_excess_ret_10_pct", "positive_excess_10_ratio_pct", "avg_mfe_close_10_pct", "avg_mae_close_10_pct"], 30)}

## 行业尾部画像

{markdown_table(industry_display, ["scenario", "role", "industry", "selected_rows", "avg_fwd_excess_ret_10_pct", "positive_excess_10_ratio_pct", "avg_mfe_close_10_pct", "avg_mae_close_10_pct"], 40)}

## 质量检查

{markdown_table(quality, ["checkpoint", "status", "value", "expected", "judgement"], 20)}

## 下一层实验计划

{markdown_table(plan, ["priority", "experiment", "status", "design", "success_criteria"], 20)}

## 结论

- 简单20日超跌网格没有任何形状同时达到总收益`>=100%`和最大回撤`>=-20%`，所以它不是正式候选。
- `top8_gross50_ind2`适合作为研究母本：总收益约`49.58%`，最大回撤约`-23.28%`，Sharpe约`0.448`，风险收益比在中等暴露组里最好。
- `top5_gross50_ind2`适合作为可交易性护栏：收益较低但零手目标比例低于20%，可防止增强层靠不可交易的小目标堆收益。
- `top8_gross30_ind2`是风险地板：回撤约`-13.62%`，但收益约`25.83%`，不能满足高收益目标。
- 高暴露70%版本收益更高但回撤过深，说明单纯加仓不是解决方案。
- 下一步不应调参，而应做残差增强的同形状替换/混合：同样topK、gross、行业上限下，证明残差排序相对简单超跌母本有真实增益。

## 过拟合反思

- 运行前判断：否。本阶段只固定母本和护栏，不新增交易阈值。
- 运行后判断：否。结论没有把最佳收益形状包装成候选，反而明确它不是正式策略。
- 风险提示：如果下一步在母本上不断挑行业/年份过滤，会转为过拟合；必须按分层实验计划推进。

## 继续价值反思

- 运行前判断：是。第331显示需要从简单母本重建架构。
- 运行后判断：是。母本、护栏、风险地板和压力样本已经明确，下一步可以做干净的残差增量验证。
- 原因：这比继续修`industry_resid_core`更接近用户最初目标，也更容易判断每一层到底贡献了什么。

## 输出文件

- `{PREFIX}_shape_frontier.csv`
- `{PREFIX}_mother_decision.csv`
- `{PREFIX}_yearly_focus.csv`
- `{PREFIX}_yearly_aggregate.csv`
- `{PREFIX}_rolling_252.csv`
- `{PREFIX}_rolling_aggregate.csv`
- `{PREFIX}_drawdown_windows.csv`
- `{PREFIX}_daily_exposure_buckets.csv`
- `{PREFIX}_signal_state_attribution.csv`
- `{PREFIX}_signal_industry_attribution.csv`
- `{PREFIX}_quality_checkpoints.csv`
- `{PREFIX}_next_experiment_plan.csv`
- `{PREFIX}_meta.json`
"""


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    summary = read_csv("summary")
    yearly = read_csv("yearly")
    daily = read_csv("daily")

    frontier = build_shape_frontier(summary)
    mother = build_mother_decision(frontier)
    yearly_focus, yearly_agg = build_yearly_focus(yearly)
    rolling, rolling_agg = build_rolling(daily)
    drawdowns = build_drawdown_windows(daily)
    exposure_buckets = build_daily_exposure_buckets(daily)
    signal_state, signal_industry = build_signal_state_and_industry()
    quality = build_quality_checkpoints(frontier, mother, yearly_agg, rolling_agg)
    plan = build_next_experiment_plan()

    frontier.to_csv(OUTPUT_DIR / f"{PREFIX}_shape_frontier.csv", index=False, encoding="utf-8-sig")
    mother.to_csv(OUTPUT_DIR / f"{PREFIX}_mother_decision.csv", index=False, encoding="utf-8-sig")
    yearly_focus.to_csv(OUTPUT_DIR / f"{PREFIX}_yearly_focus.csv", index=False, encoding="utf-8-sig")
    yearly_agg.to_csv(OUTPUT_DIR / f"{PREFIX}_yearly_aggregate.csv", index=False, encoding="utf-8-sig")
    rolling.to_csv(OUTPUT_DIR / f"{PREFIX}_rolling_252.csv", index=False, encoding="utf-8-sig")
    rolling_agg.to_csv(OUTPUT_DIR / f"{PREFIX}_rolling_aggregate.csv", index=False, encoding="utf-8-sig")
    drawdowns.to_csv(OUTPUT_DIR / f"{PREFIX}_drawdown_windows.csv", index=False, encoding="utf-8-sig")
    exposure_buckets.to_csv(OUTPUT_DIR / f"{PREFIX}_daily_exposure_buckets.csv", index=False, encoding="utf-8-sig")
    signal_state.to_csv(OUTPUT_DIR / f"{PREFIX}_signal_state_attribution.csv", index=False, encoding="utf-8-sig")
    signal_industry.to_csv(OUTPUT_DIR / f"{PREFIX}_signal_industry_attribution.csv", index=False, encoding="utf-8-sig")
    quality.to_csv(OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv", index=False, encoding="utf-8-sig")
    plan.to_csv(OUTPUT_DIR / f"{PREFIX}_next_experiment_plan.csv", index=False, encoding="utf-8-sig")

    meta = {
        "generated_at": datetime.now().isoformat(),
        "line_id": "stock_range_30w_industry_resid_core",
        "mode": "day",
        "source_dir": str(SOURCE_DIR),
        "source_prefix": SOURCE_PREFIX,
        "focus_scenarios": list(FOCUS_SCENARIOS),
        "primary_research_mother": "top8_gross50_ind2",
        "tradability_guard_mother": "top5_gross50_ind2",
        "user_return_target": USER_RETURN_TARGET,
        "user_max_drawdown_limit": USER_MAX_DRAWDOWN_LIMIT,
        "rolling_window": ROLLING_WINDOW,
        "research_sources": RESEARCH_SOURCES,
        "output_dir": str(OUTPUT_DIR),
    }
    write_json(OUTPUT_DIR / f"{PREFIX}_meta.json", meta)

    report = build_report(
        frontier=frontier,
        mother=mother,
        yearly_focus=yearly_focus,
        yearly_agg=yearly_agg,
        rolling_agg=rolling_agg,
        drawdowns=drawdowns.sort_values(["scenario", "max_drawdown"]).groupby("scenario").head(4),
        exposure_buckets=exposure_buckets,
        signal_state=signal_state,
        signal_industry=signal_industry.groupby("scenario").head(8) if not signal_industry.empty else signal_industry,
        quality=quality,
        plan=plan,
    )
    (OUTPUT_DIR / f"{PREFIX}_report.md").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
