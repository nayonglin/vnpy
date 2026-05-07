from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, pct


SOURCE_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_30w_residual_source_attribution_2018_2026"
).expanduser().resolve()
SOURCE_PREFIX: str = "stock_range_reversion_liquid_q3_30w_residual_source_attribution_v1"

OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_30w_residual_stress_validation_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_30w_residual_stress_validation_v1"

ACCOUNT_SIZE_CNY: float = 300_000.0
USER_RETURN_TARGET: float = 1.0
USER_MAX_DRAWDOWN_LIMIT: float = -0.20

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "Short-term residual reversal",
        "https://www.sciencedirect.com/science/article/pii/S1386418112000468",
    ),
    (
        "Residual reversal and liquidity provision",
        "https://www.efmaefm.org/0EFMSYMPOSIUM/2012/papers/017_update.pdf",
    ),
    (
        "Portfolio performance attribution overview",
        "https://en.wikipedia.org/wiki/Performance_attribution",
    ),
    (
        "Cross-sectional mean reversion implementation",
        "https://teddykoker.com/2019/04/backtesting-a-cross-sectional-mean-reversion-strategy-in-python/",
    ),
    (
        "GitHub mean-reversion-trading topics",
        "https://github.com/topics/mean-reversion-trading",
    ),
)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def compound_return(values: pd.Series | np.ndarray | list[float]) -> float:
    clean = pd.Series(values).dropna().astype(float)
    if clean.empty:
        return 0.0
    return float((1.0 + clean).prod() - 1.0)


def max_drawdown_from_returns(values: pd.Series | np.ndarray | list[float]) -> float:
    clean = pd.Series(values).dropna().astype(float)
    if clean.empty:
        return 0.0
    equity = (1.0 + clean).cumprod()
    high = equity.cummax()
    return float((equity / high - 1.0).min())


def annualized_sharpe(values: pd.Series | np.ndarray | list[float]) -> float:
    clean = pd.Series(values).dropna().astype(float)
    if len(clean) < 2:
        return 0.0
    std = clean.std(ddof=1)
    if std == 0 or pd.isna(std):
        return 0.0
    return float(clean.mean() / std * np.sqrt(252.0))


def markdown_table(frame: pd.DataFrame, columns: list[str], limit: int = 30) -> str:
    if frame.empty:
        return "\n无数据。\n"
    existing = [col for col in columns if col in frame.columns]
    if not existing:
        return "\n无匹配列。\n"
    return frame[existing].head(limit).to_markdown(index=False)


def add_pct_columns(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = frame.copy()
    for column in columns:
        if column in out.columns:
            out[f"{column}_pct"] = out[column].map(lambda value: pct(safe_float(value, float("nan"))))
    return out


def read_source_csv(name: str, parse_dates: list[str] | None = None) -> pd.DataFrame:
    path = SOURCE_DIR / f"{SOURCE_PREFIX}_{name}.csv"
    return pd.read_csv(path, parse_dates=parse_dates or [])


def period_definitions(min_date: pd.Timestamp, max_date: pd.Timestamp) -> list[tuple[str, str, Callable[[pd.Series], pd.Series]]]:
    return [
        ("full_sample", f"{min_date:%Y-%m-%d}到{max_date:%Y-%m-%d}全样本", lambda date: date.notna()),
        ("holdout_2018", "只看2018年留出压力段", lambda date: date.dt.year.eq(2018)),
        ("exclude_2018", "剔除2018年", lambda date: ~date.dt.year.eq(2018)),
        ("post_2019", "2019年至今", lambda date: date.dt.year.ge(2019)),
        ("post_2020", "2020年至今", lambda date: date.dt.year.ge(2020)),
        ("recent_2024_2026", "2024年至今近端样本", lambda date: date.dt.year.ge(2024)),
    ]


def build_period_stress(pair_daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    min_date = pair_daily["date"].min()
    max_date = pair_daily["date"].max()
    for period_id, period_desc, mask_func in period_definitions(min_date, max_date):
        period_mask = mask_func(pair_daily["date"])
        for pair_id, group in pair_daily[period_mask].groupby("pair_id"):
            if group.empty:
                continue
            first = group.iloc[0]
            base_ret = compound_return(group["strategy_daily_ret_min_fee_base"])
            variant_ret = compound_return(group["strategy_daily_ret_min_fee_variant"])
            base_dd = max_drawdown_from_returns(group["strategy_daily_ret_min_fee_base"])
            variant_dd = max_drawdown_from_returns(group["strategy_daily_ret_min_fee_variant"])
            base_sharpe = annualized_sharpe(group["strategy_daily_ret_min_fee_base"])
            variant_sharpe = annualized_sharpe(group["strategy_daily_ret_min_fee_variant"])
            rows.append(
                {
                    "period_id": period_id,
                    "period_desc": period_desc,
                    "pair_id": pair_id,
                    "shape_id": first["shape_id"],
                    "variant_label": first["variant_label"],
                    "trade_days": int(len(group)),
                    "start_date": group["date"].min(),
                    "end_date": group["date"].max(),
                    "base_total_return": base_ret,
                    "variant_total_return": variant_ret,
                    "delta_total_return": variant_ret - base_ret,
                    "base_max_drawdown": base_dd,
                    "variant_max_drawdown": variant_dd,
                    "delta_max_drawdown": variant_dd - base_dd,
                    "base_sharpe": base_sharpe,
                    "variant_sharpe": variant_sharpe,
                    "delta_sharpe": variant_sharpe - base_sharpe,
                    "positive_delta_day_ratio": float((group["daily_ret_delta"] > 0).mean()),
                    "daily_delta_sum": group["daily_ret_delta"].sum(),
                    "avg_daily_ret_delta": group["daily_ret_delta"].mean(),
                    "worst_daily_ret_delta": group["daily_ret_delta"].min(),
                    "best_daily_ret_delta": group["daily_ret_delta"].max(),
                    "avg_actual_gross_weight_delta": group["actual_gross_weight_delta"].mean(),
                    "avg_actual_symbol_count_delta": group["actual_symbol_count_delta"].mean(),
                    "avg_zero_lot_target_count_delta": group["zero_lot_target_count_delta"].mean(),
                    "return_improved": variant_ret > base_ret,
                    "drawdown_improved": variant_dd >= base_dd,
                    "sharpe_improved": variant_sharpe > base_sharpe,
                    "return_and_drawdown_improved": (variant_ret > base_ret) and (variant_dd >= base_dd),
                    "full_goal_hit_if_full_sample": (
                        period_id == "full_sample"
                        and variant_ret >= USER_RETURN_TARGET
                        and variant_dd >= USER_MAX_DRAWDOWN_LIMIT
                    ),
                }
            )
    return pd.DataFrame(rows).sort_values(["pair_id", "period_id"]).reset_index(drop=True)


def build_yearly_stress(yearly: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for pair_id, group in yearly.groupby("pair_id"):
        first = group.iloc[0]
        for bucket_id, bucket_desc, bucket in (
            ("all_years", "全部年度", group),
            ("exclude_2018_years", "剔除2018年度", group[group["year"].ne(2018)]),
            ("post_2019_years", "2019年至今年度", group[group["year"].ge(2019)]),
            ("recent_2024_2026_years", "2024年至今年度", group[group["year"].ge(2024)]),
        ):
            if bucket.empty:
                continue
            both = bucket["return_and_drawdown_improved"].astype(bool)
            rows.append(
                {
                    "bucket_id": bucket_id,
                    "bucket_desc": bucket_desc,
                    "pair_id": pair_id,
                    "shape_id": first["shape_id"],
                    "variant_label": first["variant_label"],
                    "years": int(len(bucket)),
                    "return_improved_years": int(bucket["return_improved"].astype(bool).sum()),
                    "drawdown_improved_years": int(bucket["drawdown_improved"].astype(bool).sum()),
                    "return_and_drawdown_improved_years": int(both.sum()),
                    "return_and_drawdown_improved_ratio": float(both.mean()),
                    "avg_delta_year_return": bucket["delta_year_return"].mean(),
                    "avg_delta_year_drawdown": bucket["delta_year_drawdown"].mean(),
                    "worst_delta_year_return": bucket["delta_year_return"].min(),
                    "worst_delta_year_drawdown": bucket["delta_year_drawdown"].min(),
                    "best_delta_year_return": bucket["delta_year_return"].max(),
                    "best_delta_year_drawdown": bucket["delta_year_drawdown"].max(),
                }
            )
    return pd.DataFrame(rows).sort_values(["pair_id", "bucket_id"]).reset_index(drop=True)


def classify_windows(drawdown_windows: pd.DataFrame) -> pd.DataFrame:
    work = drawdown_windows.copy()
    date_cols = ["base_peak_date", "base_start_date", "base_trough_date", "base_recovery_date"]
    for col in date_cols:
        if col in work.columns:
            work[col] = pd.to_datetime(work[col])
    work["touches_2018"] = (
        work["base_peak_date"].dt.year.eq(2018)
        | work["base_start_date"].dt.year.eq(2018)
        | work["base_trough_date"].dt.year.eq(2018)
    )
    work["is_major_window"] = work["base_episode_max_drawdown"] <= -0.05
    work["segment_return_improved"] = work["delta_segment_return"] > 0
    work["segment_drawdown_improved"] = work["delta_segment_drawdown"] >= 0
    work["segment_return_and_drawdown_improved"] = (
        work["segment_return_improved"] & work["segment_drawdown_improved"]
    )
    return work


def build_window_bucket_stress(drawdown_windows: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    work = classify_windows(drawdown_windows)
    rows: list[dict[str, Any]] = []
    bucket_specs = (
        ("all_base_drawdown_windows", "全部基准回撤窗口", lambda frame: frame.index == frame.index),
        ("windows_touching_2018", "触及2018的基准回撤窗口", lambda frame: frame["touches_2018"]),
        ("non2018_windows", "非2018基准回撤窗口", lambda frame: ~frame["touches_2018"]),
        (
            "non2018_major_windows",
            "非2018且基准回撤超过5%的主要窗口",
            lambda frame: (~frame["touches_2018"]) & frame["is_major_window"],
        ),
    )
    for bucket_id, bucket_desc, mask_func in bucket_specs:
        bucket_all = work[mask_func(work)].copy()
        for pair_id, group in bucket_all.groupby("pair_id"):
            if group.empty:
                continue
            first = group.iloc[0]
            both = group["segment_return_and_drawdown_improved"].astype(bool)
            rows.append(
                {
                    "bucket_id": bucket_id,
                    "bucket_desc": bucket_desc,
                    "pair_id": pair_id,
                    "shape_id": first["shape_id"],
                    "variant_label": first["variant_label"],
                    "window_count": int(len(group)),
                    "avg_base_episode_max_drawdown": group["base_episode_max_drawdown"].mean(),
                    "avg_delta_segment_return": group["delta_segment_return"].mean(),
                    "avg_delta_segment_drawdown": group["delta_segment_drawdown"].mean(),
                    "worst_delta_segment_return": group["delta_segment_return"].min(),
                    "worst_delta_segment_drawdown": group["delta_segment_drawdown"].min(),
                    "best_delta_segment_return": group["delta_segment_return"].max(),
                    "best_delta_segment_drawdown": group["delta_segment_drawdown"].max(),
                    "segment_return_improved_count": int(group["segment_return_improved"].sum()),
                    "segment_drawdown_improved_count": int(group["segment_drawdown_improved"].sum()),
                    "segment_return_and_drawdown_improved_count": int(both.sum()),
                    "segment_return_and_drawdown_improved_ratio": float(both.mean()),
                    "avg_daily_delta_sum": group["daily_delta_sum"].mean(),
                    "avg_positive_delta_day_ratio": group["positive_delta_day_ratio"].mean(),
                    "avg_actual_gross_weight_delta": group["avg_actual_gross_weight_delta"].mean(),
                    "avg_actual_symbol_count_delta": group["avg_actual_symbol_count_delta"].mean(),
                    "avg_zero_lot_target_count_delta": group["avg_zero_lot_target_count_delta"].mean(),
                }
            )
    summary = pd.DataFrame(rows).sort_values(["pair_id", "bucket_id"]).reset_index(drop=True)
    non2018_major = work[(~work["touches_2018"]) & work["is_major_window"]].copy()
    return summary, non2018_major.sort_values(["pair_id", "base_episode_max_drawdown"]).reset_index(drop=True)


def single_row(frame: pd.DataFrame, **conditions: str) -> pd.Series | None:
    mask = pd.Series(True, index=frame.index)
    for column, value in conditions.items():
        mask &= frame[column].eq(value)
    matched = frame[mask]
    if matched.empty:
        return None
    return matched.iloc[0]


def build_quality(period_stress: pd.DataFrame, yearly_stress: pd.DataFrame, window_stress: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    def add(checkpoint: str, status: str, value: Any, expected: str, judgement: str) -> None:
        rows.append(
            {
                "checkpoint": checkpoint,
                "status": status,
                "value": value,
                "expected": expected,
                "judgement": judgement,
            }
        )

    full_top8 = single_row(period_stress, pair_id="top8_blend_vs_simple", period_id="full_sample")
    if full_top8 is not None:
        add(
            "top8_blend_full_sample",
            "pass" if bool(full_top8["return_and_drawdown_improved"]) else "fail",
            f"return_delta={pct(full_top8['delta_total_return'])}, dd_delta={pct(full_top8['delta_max_drawdown'])}",
            "全样本收益和回撤同向改善",
            "确认Stage333全样本改善仍存在。" if bool(full_top8["return_and_drawdown_improved"]) else "全样本改善不成立。",
        )

    holdout_2018 = single_row(period_stress, pair_id="top8_blend_vs_simple", period_id="holdout_2018")
    if holdout_2018 is not None:
        add(
            "top8_blend_2018_holdout",
            "pass" if bool(holdout_2018["return_and_drawdown_improved"]) else "fail",
            f"return_delta={pct(holdout_2018['delta_total_return'])}, dd_delta={pct(holdout_2018['delta_max_drawdown'])}",
            "2018留出压力段收益和回撤同向改善",
            "残差层确实抓住了2018型风险段。" if bool(holdout_2018["return_and_drawdown_improved"]) else "残差层连2018压力段也未成立。",
        )

    exclude_2018 = single_row(period_stress, pair_id="top8_blend_vs_simple", period_id="exclude_2018")
    if exclude_2018 is not None:
        add(
            "top8_blend_exclude_2018",
            "pass" if bool(exclude_2018["return_and_drawdown_improved"]) else "fail",
            f"return_delta={pct(exclude_2018['delta_total_return'])}, dd_delta={pct(exclude_2018['delta_max_drawdown'])}",
            "剔除2018后仍收益和回撤同向改善",
            "可考虑进入状态预算输入。" if bool(exclude_2018["return_and_drawdown_improved"]) else "剔除2018后优势消失，不能当广谱排序因子。",
        )

    post_2019 = single_row(period_stress, pair_id="top8_blend_vs_simple", period_id="post_2019")
    if post_2019 is not None:
        add(
            "top8_blend_post_2019",
            "pass" if bool(post_2019["return_and_drawdown_improved"]) else "fail",
            f"return_delta={pct(post_2019['delta_total_return'])}, dd_delta={pct(post_2019['delta_max_drawdown'])}",
            "2019年至今仍收益和回撤同向改善",
            "后2018样本仍有效。" if bool(post_2019["return_and_drawdown_improved"]) else "后2018样本不支持直接升级。",
        )

    annual_top8 = single_row(yearly_stress, pair_id="top8_blend_vs_simple", bucket_id="exclude_2018_years")
    if annual_top8 is not None:
        ratio = safe_float(annual_top8["return_and_drawdown_improved_ratio"])
        add(
            "top8_blend_ex2018_yearly_breadth",
            "pass" if ratio >= 0.50 else "fail",
            f"both_improved_years={int(annual_top8['return_and_drawdown_improved_years'])}/{int(annual_top8['years'])}",
            "剔除2018后至少半数年度收益和回撤同向改善",
            "年度广度足够。" if ratio >= 0.50 else "年度广度不足，改善太集中。",
        )

    window_top8 = single_row(window_stress, pair_id="top8_blend_vs_simple", bucket_id="non2018_major_windows")
    if window_top8 is not None:
        ratio = safe_float(window_top8["segment_return_and_drawdown_improved_ratio"])
        avg_return = safe_float(window_top8["avg_delta_segment_return"])
        avg_dd = safe_float(window_top8["avg_delta_segment_drawdown"])
        add(
            "top8_blend_non2018_major_windows",
            "pass" if ratio >= 0.50 and avg_return > 0 and avg_dd >= 0 else "fail",
            (
                f"both_improved_windows={int(window_top8['segment_return_and_drawdown_improved_count'])}/"
                f"{int(window_top8['window_count'])}, avg_return_delta={pct(avg_return)}, avg_dd_delta={pct(avg_dd)}"
            ),
            "非2018主要回撤窗口多数同向改善且均值为正",
            "可以作为跨风险段预算输入。" if ratio >= 0.50 and avg_return > 0 and avg_dd >= 0 else "非2018窗口不稳，残差层更像2018风险段解释器。",
        )

    top5_ex2018 = single_row(period_stress, pair_id="top5_blend_vs_simple", period_id="exclude_2018")
    if top5_ex2018 is not None:
        status = "pass" if bool(top5_ex2018["return_and_drawdown_improved"]) else "warn"
        add(
            "top5_guard_exclude_2018",
            status,
            f"return_delta={pct(top5_ex2018['delta_total_return'])}, dd_delta={pct(top5_ex2018['delta_max_drawdown'])}",
            "top5护栏剔除2018后不恶化",
            "护栏同步确认。" if status == "pass" else "top5护栏不同步，不能只看top8。",
        )

    final_decision_status = "warn"
    final_decision = "downgrade_to_monitor_or_state_budget"
    if (
        exclude_2018 is not None
        and bool(exclude_2018["return_and_drawdown_improved"])
        and window_top8 is not None
        and safe_float(window_top8["segment_return_and_drawdown_improved_ratio"]) >= 0.50
    ):
        final_decision_status = "pass"
        final_decision = "can_test_as_continuous_state_budget_input"
    add(
        "residual_layer_decision",
        final_decision_status,
        final_decision,
        "只有剔除2018和非2018回撤窗口都成立，才允许升级",
        "不继续扫残差排序参数；下一步应转向连续风险预算/监控分层。",
    )

    return pd.DataFrame(rows)


def build_report(
    period_stress: pd.DataFrame,
    yearly_stress: pd.DataFrame,
    window_stress: pd.DataFrame,
    non2018_major_windows: pd.DataFrame,
    quality: pd.DataFrame,
    meta: dict[str, Any],
) -> str:
    pct_cols_period = [
        "base_total_return",
        "variant_total_return",
        "delta_total_return",
        "base_max_drawdown",
        "variant_max_drawdown",
        "delta_max_drawdown",
        "positive_delta_day_ratio",
        "avg_actual_gross_weight_delta",
    ]
    pct_cols_yearly = [
        "return_and_drawdown_improved_ratio",
        "avg_delta_year_return",
        "avg_delta_year_drawdown",
        "worst_delta_year_return",
        "worst_delta_year_drawdown",
    ]
    pct_cols_window = [
        "avg_base_episode_max_drawdown",
        "avg_delta_segment_return",
        "avg_delta_segment_drawdown",
        "worst_delta_segment_return",
        "worst_delta_segment_drawdown",
        "segment_return_and_drawdown_improved_ratio",
    ]
    pct_cols_window_detail = [
        "base_episode_max_drawdown",
        "base_segment_return_to_trough",
        "variant_segment_return_same_window",
        "delta_segment_return",
        "base_segment_drawdown",
        "variant_segment_drawdown_same_window",
        "delta_segment_drawdown",
        "positive_delta_day_ratio",
    ]

    period_fmt = add_pct_columns(period_stress, pct_cols_period)
    yearly_fmt = add_pct_columns(yearly_stress, pct_cols_yearly)
    window_fmt = add_pct_columns(window_stress, pct_cols_window)
    non2018_fmt = add_pct_columns(non2018_major_windows, pct_cols_window_detail)

    focus_periods = period_fmt[
        period_fmt["period_id"].isin(["full_sample", "holdout_2018", "exclude_2018", "post_2019"])
    ].copy()
    focus_periods = focus_periods.sort_values(["pair_id", "period_id"])

    lines = [
        "# 第335阶段：残差层2018留出/剔除压力验证",
        "",
        "## 结论摘要",
        "",
        "- 本阶段不新增交易信号、不改参数、不重新跑交易引擎，只读取第334阶段已经生成的日度配对、年度和回撤窗口归因结果。",
        "- 验证目标是判断第333/334阶段残差层改善是否具有跨时期生命力，还是主要由2018型大风险段贡献。",
        "- 若剔除2018后收益和回撤不再同向改善，残差层不应作为正式排序主因子继续扫参；更适合降级为风险监控或连续风险预算候选输入。",
        "",
        "## 元信息",
        "",
        f"- 生成时间：{meta['generated_at']}",
        f"- 输入目录：`{SOURCE_DIR}`",
        f"- 输出目录：`{OUTPUT_DIR}`",
        f"- 账户规模：{ACCOUNT_SIZE_CNY:,.0f} CNY",
        f"- 用户目标：总收益≥{pct(USER_RETURN_TARGET)}，最大回撤≥{pct(USER_MAX_DRAWDOWN_LIMIT)}",
        "",
        "## 外部参考与判断",
        "",
        "- 短期残差反转文献支持“残差/特质收益”可能携带均值回归信息，但不能替代样本外和分段压力验证。",
        "- 组合归因框架支持把全样本收益拆成时间段、行业和风险窗口贡献；当前阶段优先用时间留出判断是否存在单一年份依赖。",
        "- 横截面均值回归实现经验提示：信号有效性应靠多时期、不同市场状态复验，而不是只看一段漂亮净值。",
        "",
        "## 质量检查",
        "",
        markdown_table(quality, ["checkpoint", "status", "value", "expected", "judgement"], limit=20),
        "",
        "## 分段压力结果",
        "",
        markdown_table(
            focus_periods,
            [
                "pair_id",
                "period_id",
                "trade_days",
                "base_total_return_pct",
                "variant_total_return_pct",
                "delta_total_return_pct",
                "base_max_drawdown_pct",
                "variant_max_drawdown_pct",
                "delta_max_drawdown_pct",
                "base_sharpe",
                "variant_sharpe",
                "delta_sharpe",
                "return_and_drawdown_improved",
            ],
            limit=40,
        ),
        "",
        "## 年度广度压力",
        "",
        markdown_table(
            yearly_fmt[yearly_fmt["bucket_id"].isin(["all_years", "exclude_2018_years"])],
            [
                "pair_id",
                "bucket_id",
                "years",
                "return_improved_years",
                "drawdown_improved_years",
                "return_and_drawdown_improved_years",
                "return_and_drawdown_improved_ratio_pct",
                "avg_delta_year_return_pct",
                "avg_delta_year_drawdown_pct",
                "worst_delta_year_return_pct",
                "worst_delta_year_drawdown_pct",
            ],
            limit=30,
        ),
        "",
        "## 回撤窗口压力",
        "",
        markdown_table(
            window_fmt,
            [
                "pair_id",
                "bucket_id",
                "window_count",
                "avg_base_episode_max_drawdown_pct",
                "avg_delta_segment_return_pct",
                "avg_delta_segment_drawdown_pct",
                "worst_delta_segment_return_pct",
                "worst_delta_segment_drawdown_pct",
                "segment_return_and_drawdown_improved_count",
                "segment_return_and_drawdown_improved_ratio_pct",
            ],
            limit=40,
        ),
        "",
        "## 非2018主要回撤窗口明细",
        "",
        markdown_table(
            non2018_fmt,
            [
                "pair_id",
                "base_start_date",
                "base_trough_date",
                "base_episode_max_drawdown_pct",
                "delta_segment_return_pct",
                "delta_segment_drawdown_pct",
                "days_to_trough",
                "positive_delta_day_ratio_pct",
            ],
            limit=40,
        ),
        "",
        "## 研究判断",
        "",
        "- 过拟合判断：否。本阶段没有搜索新阈值，也没有用结果反向改规则；它是在做旧结果的反证压力测试。",
        "- 继续价值判断：有。若残差层只解释2018，需要把它从排序核心降级；若能跨非2018窗口成立，才值得进入连续风险预算试验。",
        "- 当前动作不触发A/B实验，不修改第78，不修改`stock_range_paper_v1`。",
        "",
        "## 产物",
        "",
        f"- `{PREFIX}_period_stress.csv`",
        f"- `{PREFIX}_yearly_stress.csv`",
        f"- `{PREFIX}_window_bucket_stress.csv`",
        f"- `{PREFIX}_non2018_major_windows.csv`",
        f"- `{PREFIX}_quality_checkpoints.csv`",
        f"- `{PREFIX}_meta.json`",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    pair_daily = read_source_csv("pair_daily", parse_dates=["date"])
    yearly = read_source_csv("yearly")
    drawdown_windows = read_source_csv(
        "drawdown_windows",
        parse_dates=["base_peak_date", "base_start_date", "base_trough_date", "base_recovery_date"],
    )

    period_stress = build_period_stress(pair_daily)
    yearly_stress = build_yearly_stress(yearly)
    window_stress, non2018_major_windows = build_window_bucket_stress(drawdown_windows)
    quality = build_quality(period_stress, yearly_stress, window_stress)

    meta: dict[str, Any] = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_dir": str(SOURCE_DIR),
        "source_prefix": SOURCE_PREFIX,
        "output_dir": str(OUTPUT_DIR),
        "prefix": PREFIX,
        "account_size_cny": ACCOUNT_SIZE_CNY,
        "user_return_target": USER_RETURN_TARGET,
        "user_max_drawdown_limit": USER_MAX_DRAWDOWN_LIMIT,
        "research_sources": [{"title": title, "url": url} for title, url in RESEARCH_SOURCES],
        "input_rows": {
            "pair_daily": int(len(pair_daily)),
            "yearly": int(len(yearly)),
            "drawdown_windows": int(len(drawdown_windows)),
        },
        "quality_status_counts": quality["status"].value_counts().to_dict() if not quality.empty else {},
    }

    period_stress.to_csv(OUTPUT_DIR / f"{PREFIX}_period_stress.csv", index=False)
    yearly_stress.to_csv(OUTPUT_DIR / f"{PREFIX}_yearly_stress.csv", index=False)
    window_stress.to_csv(OUTPUT_DIR / f"{PREFIX}_window_bucket_stress.csv", index=False)
    non2018_major_windows.to_csv(OUTPUT_DIR / f"{PREFIX}_non2018_major_windows.csv", index=False)
    quality.to_csv(OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv", index=False)
    write_json(OUTPUT_DIR / f"{PREFIX}_meta.json", meta)

    report = build_report(period_stress, yearly_stress, window_stress, non2018_major_windows, quality, meta)
    (OUTPUT_DIR / f"{PREFIX}_report.md").write_text(report, encoding="utf-8")

    print(json.dumps(meta, ensure_ascii=False, indent=2))
    print("\nquality:")
    print(quality.to_string(index=False))


if __name__ == "__main__":
    main()
