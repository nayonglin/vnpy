from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable

import polars as pl

import analyze_stock_range_reversion_liquid_q3_industry_resid_core_30w_slow_rhythm_replay as rhythm_replay
from analyze_stock_range_reversion_layer_attribution import load_panels
from analyze_stock_range_reversion_liquid_q3_30w_high_return_shape_grid import (
    HIGH_RETURN_TARGET,
    MAX_DRAWDOWN_LIMIT,
    to_float,
)
from analyze_stock_range_reversion_liquid_q3_industry_resid_core_30w_loss_sample_attribution import (
    FOCUS_SCENARIOS,
    read_csv_with_symbol,
)
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, TRADING_DAYS, pct
from generate_stock_range_reversion_liquid_q3_paper_tracking import markdown_table
from generate_stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality import build_exec_info


SOURCE_DIR: Path = rhythm_replay.SOURCE_DIR
SOURCE_PREFIX: str = rhythm_replay.SOURCE_PREFIX
BASE_RHYTHM_DIR: Path = rhythm_replay.OUTPUT_DIR
BASE_RHYTHM_PREFIX: str = rhythm_replay.PREFIX

OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_industry_resid_core_30w_smooth_risk_budget_replay_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_industry_resid_core_30w_smooth_risk_budget_replay_v1"

CANDIDATE_BASE_SCENARIO: str = "industry_resid_core_h10_top5_gross70_ind1"
SEGMENT_DRAWDOWN_START: date = date(2022, 3, 3)
SEGMENT_RECOVERY_START: date = date(2024, 9, 21)

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "Volatility Managed Portfolios",
        "https://conference.nber.org/confer/2016/LTAMs16/Moreira_Muir.pdf",
    ),
    (
        "Smoothing volatility targeting",
        "https://arxiv.org/abs/2212.07288",
    ),
    (
        "Volatility Targeting - Risk Management in Python",
        "https://hypercode.alexisbouchez.com/risk-management/lessons/volatility-targeting",
    ),
    (
        "Backtesting a Cross-Sectional Mean Reversion Strategy in Python",
        "https://teddykoker.com/2019/04/backtesting-a-cross-sectional-mean-reversion-strategy-in-python/",
    ),
    (
        "GitHub risk-parity topic",
        "https://github.com/topics/risk-parity",
    ),
)


@dataclass(frozen=True)
class SmoothRiskBudgetRule:
    name: str
    lookback_days: int
    taper_start: float
    taper_end: float
    min_scale: float
    description: str

    def scale(self, prev_return: float | None) -> float:
        if prev_return is None or prev_return != prev_return:
            return 1.0
        if prev_return <= self.taper_start:
            return 1.0
        if prev_return >= self.taper_end:
            return self.min_scale
        progress = (prev_return - self.taper_start) / (self.taper_end - self.taper_start)
        return 1.0 - progress * (1.0 - self.min_scale)

    def state(self, prev_return: float | None) -> str:
        if prev_return is None or prev_return != prev_return:
            return "missing"
        if prev_return <= self.taper_start:
            return "full_budget"
        if prev_return >= self.taper_end:
            return "floor_budget"
        return "taper_budget"


SMOOTH_RULES: tuple[SmoothRiskBudgetRule, ...] = (
    SmoothRiskBudgetRule(
        name="smooth60_soft0to10_floor50",
        lookback_days=60,
        taper_start=0.00,
        taper_end=0.10,
        min_scale=0.50,
        description="用自身60日收益做连续风险预算：<=0%满仓，0%-10%线性降到50%，之后保持50%。",
    ),
    SmoothRiskBudgetRule(
        name="smooth60_soft0to10_floor30",
        lookback_days=60,
        taper_start=0.00,
        taper_end=0.10,
        min_scale=0.30,
        description="用自身60日收益做连续风险预算：<=0%满仓，0%-10%线性降到30%，之后保持30%。",
    ),
    SmoothRiskBudgetRule(
        name="smooth80_soft0to12_floor50",
        lookback_days=80,
        taper_start=0.00,
        taper_end=0.12,
        min_scale=0.50,
        description="用自身80日收益做连续风险预算：<=0%满仓，0%-12%线性降到50%，之后保持50%。",
    ),
)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def calc_prev_return(equity_history: list[float], lookback_days: int) -> float | None:
    if len(equity_history) < lookback_days + 1:
        return None
    base = equity_history[-lookback_days - 1]
    if base <= 0:
        return None
    return equity_history[-1] / base - 1.0


def max_drawdown_from_returns(values: list[float]) -> float:
    equity = 1.0
    peak = 1.0
    worst = 0.0
    for value in values:
        equity *= 1.0 + value
        peak = max(peak, equity)
        worst = min(worst, equity / peak - 1.0)
    return worst


def annualized_sharpe(values: list[float]) -> float:
    clean = [value for value in values if value == value]
    if len(clean) < 2:
        return 0.0
    mean = sum(clean) / len(clean)
    variance = sum((value - mean) ** 2 for value in clean) / (len(clean) - 1)
    if variance <= 0:
        return 0.0
    return mean / (variance**0.5) * (TRADING_DAYS**0.5)


def to_pydate(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(str(value)[:10]).date()


def segment_name(value: Any) -> str:
    current = to_pydate(value)
    if current < SEGMENT_DRAWDOWN_START:
        return "2018_2022_pre_drawdown"
    if current < SEGMENT_RECOVERY_START:
        return "2022_2024_drawdown_stress"
    return "2024_2026_recovery_recent"


def load_base_summary() -> pl.DataFrame:
    path = BASE_RHYTHM_DIR / f"{BASE_RHYTHM_PREFIX}_summary.csv"
    return pl.read_csv(path).filter(pl.col("slow_rhythm_name") == "base_rerun")


def load_base_daily() -> pl.DataFrame:
    path = BASE_RHYTHM_DIR / f"{BASE_RHYTHM_PREFIX}_daily.csv"
    return (
        pl.read_csv(path, try_parse_dates=True)
        .filter((pl.col("base_scenario").is_in(FOCUS_SCENARIOS)) & (pl.col("slow_rhythm_name") == "base_rerun"))
        .with_columns(
            pl.lit(None).cast(pl.Int64).alias("lookback_days"),
            pl.lit(None).cast(pl.Float64).alias("taper_start"),
            pl.lit(None).cast(pl.Float64).alias("taper_end"),
            pl.lit(None).cast(pl.Float64).alias("min_scale"),
            pl.col("rhythm_scale").alias("budget_scale"),
        )
    )


def patch_replay_rule(
    rule: SmoothRiskBudgetRule,
) -> tuple[Callable[..., Any], Callable[..., Any], Callable[..., Any]]:
    original_calc = rhythm_replay.calc_prev_ret60
    original_bucket = rhythm_replay.bucket_ret60
    original_scale = rhythm_replay.scale_for_rhythm

    def patched_calc(equity_history: list[float]) -> float | None:
        return calc_prev_return(equity_history, rule.lookback_days)

    def patched_bucket(value: float | None) -> str:
        state = rule.state(value)
        scale = rule.scale(value)
        return f"{state}|scale={scale:.8f}"

    def patched_scale(_rhythm_name: str, prev_strategy_ret60_state: str) -> float:
        if "scale=" not in prev_strategy_ret60_state:
            return 1.0
        return float(prev_strategy_ret60_state.rsplit("scale=", maxsplit=1)[-1])

    rhythm_replay.calc_prev_ret60 = patched_calc
    rhythm_replay.bucket_ret60 = patched_bucket
    rhythm_replay.scale_for_rhythm = patched_scale
    return original_calc, original_bucket, original_scale


def restore_replay_rule(originals: tuple[Callable[..., Any], Callable[..., Any], Callable[..., Any]]) -> None:
    rhythm_replay.calc_prev_ret60, rhythm_replay.bucket_ret60, rhythm_replay.scale_for_rhythm = originals


def add_rule_fields_to_summary(
    summary: dict[str, Any],
    rule: SmoothRiskBudgetRule,
    daily: pl.DataFrame,
) -> dict[str, Any]:
    reduced_days = daily.filter(pl.col("rhythm_scale") < 0.999999).height
    floor_days = daily.filter(pl.col("rhythm_scale") <= rule.min_scale + 1e-9).height
    summary.update(
        {
            "lookback_days": rule.lookback_days,
            "taper_start": rule.taper_start,
            "taper_end": rule.taper_end,
            "min_scale": rule.min_scale,
            "avg_budget_scale": to_float(daily["rhythm_scale"].mean()) if not daily.is_empty() else 1.0,
            "min_observed_budget_scale": to_float(daily["rhythm_scale"].min()) if not daily.is_empty() else 1.0,
            "risk_reduced_days": reduced_days,
            "risk_reduced_day_ratio": reduced_days / daily.height if daily.height else 0.0,
            "floor_budget_days": floor_days,
            "floor_budget_day_ratio": floor_days / daily.height if daily.height else 0.0,
        }
    )
    return summary


def build_segment_summary(daily: pl.DataFrame) -> pl.DataFrame:
    if daily.is_empty():
        return pl.DataFrame()

    segment_daily = daily.with_columns(
        pl.col("date").map_elements(segment_name, return_dtype=pl.Utf8).alias("segment")
    ).sort(["base_scenario", "slow_rhythm_name", "date"])
    rows: list[dict[str, Any]] = []
    groups = segment_daily.partition_by(["base_scenario", "slow_rhythm_name", "scenario", "segment"], as_dict=True)
    for key, frame in groups.items():
        base_scenario, rule_name, scenario, segment = key
        returns = [float(value) for value in frame["strategy_daily_ret_min_fee"].to_list()]
        rows.append(
            {
                "base_scenario": base_scenario,
                "slow_rhythm_name": rule_name,
                "scenario": scenario,
                "segment": segment,
                "start_date": str(frame["date"].min())[:10],
                "end_date": str(frame["date"].max())[:10],
                "days": frame.height,
                "segment_return_min_fee": (pl.Series(returns) + 1.0).product() - 1.0 if returns else 0.0,
                "segment_max_drawdown_min_fee": max_drawdown_from_returns(returns),
                "segment_sharpe_min_fee": annualized_sharpe(returns),
                "avg_actual_gross_weight": to_float(frame["actual_gross_weight"].mean()),
                "avg_actual_symbol_count": to_float(frame["actual_symbol_count"].mean()),
                "avg_budget_scale": to_float(frame["rhythm_scale"].mean()),
                "risk_reduced_day_ratio": frame.filter(pl.col("rhythm_scale") < 0.999999).height / frame.height,
                "worst_daily_ret_min_fee": min(returns) if returns else 0.0,
                "cost_drag_sum": to_float(frame["turnover_cost_ret_min_fee"].sum()),
            }
        )

    segment = pl.DataFrame(rows, infer_schema_length=None)
    base = (
        segment.filter(pl.col("slow_rhythm_name") == "base_rerun")
        .select(
            "base_scenario",
            "segment",
            pl.col("segment_return_min_fee").alias("base_segment_return_min_fee"),
            pl.col("segment_max_drawdown_min_fee").alias("base_segment_max_drawdown_min_fee"),
            pl.col("segment_sharpe_min_fee").alias("base_segment_sharpe_min_fee"),
        )
    )
    return (
        segment.join(base, on=["base_scenario", "segment"], how="left")
        .with_columns(
            (pl.col("segment_return_min_fee") - pl.col("base_segment_return_min_fee")).alias(
                "delta_segment_return_min_fee"
            ),
            (pl.col("segment_max_drawdown_min_fee") - pl.col("base_segment_max_drawdown_min_fee")).alias(
                "delta_segment_max_drawdown_min_fee"
            ),
            (pl.col("segment_sharpe_min_fee") - pl.col("base_segment_sharpe_min_fee")).alias(
                "delta_segment_sharpe_min_fee"
            ),
        )
        .drop(
            [
                "base_segment_return_min_fee",
                "base_segment_max_drawdown_min_fee",
                "base_segment_sharpe_min_fee",
            ]
        )
        .sort(["base_scenario", "slow_rhythm_name", "segment"])
    )


def build_quality(summary: pl.DataFrame, segment: pl.DataFrame, daily: pl.DataFrame) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []

    def add(checkpoint: str, status: str, value: Any, expected: Any, note: str) -> None:
        rows.append(
            {
                "checkpoint": checkpoint,
                "status": status,
                "value": "" if value is None else str(value),
                "expected": "" if expected is None else str(expected),
                "note": note,
            }
        )

    stress = summary.filter(pl.col("slow_rhythm_name") != "base_rerun")
    candidate = stress.filter(pl.col("base_scenario") == CANDIDATE_BASE_SCENARIO)
    improve_both = stress.filter(
        (pl.col("delta_total_return_min_fee") > 0) & (pl.col("delta_max_drawdown_min_fee") > 0)
    )
    candidate_improve_both = candidate.filter(
        (pl.col("delta_total_return_min_fee") > 0) & (pl.col("delta_max_drawdown_min_fee") > 0)
    )
    candidate_within_20 = candidate.filter(pl.col("max_drawdown_min_fee") >= MAX_DRAWDOWN_LIMIT)
    candidate_stress_segment = segment.filter(
        (pl.col("base_scenario") == CANDIDATE_BASE_SCENARIO)
        & (pl.col("slow_rhythm_name") != "base_rerun")
        & (pl.col("segment") == "2022_2024_drawdown_stress")
    )
    candidate_stress_segment_improved_dd = candidate_stress_segment.filter(
        pl.col("delta_segment_max_drawdown_min_fee") > 0
    )

    add(
        "focus_scenario_count",
        "pass" if summary["base_scenario"].n_unique() == len(FOCUS_SCENARIOS) else "fail",
        summary["base_scenario"].n_unique(),
        len(FOCUS_SCENARIOS),
        "固定四个第316-321阶段代表形状，不扩散扫参。",
    )
    add(
        "smooth_rule_count",
        "pass" if stress["slow_rhythm_name"].n_unique() == len(SMOOTH_RULES) else "fail",
        stress["slow_rhythm_name"].n_unique(),
        len(SMOOTH_RULES),
        "只运行预注册的三个平滑风险预算函数。",
    )
    add(
        "base_summary_count",
        "pass" if summary.filter(pl.col("slow_rhythm_name") == "base_rerun").height == len(FOCUS_SCENARIOS) else "fail",
        summary.filter(pl.col("slow_rhythm_name") == "base_rerun").height,
        len(FOCUS_SCENARIOS),
        "基准来自第320阶段base复现结果。",
    )
    add(
        "no_zero_budget_scale",
        "pass" if daily.filter(pl.col("rhythm_scale") <= 0.0).is_empty() else "fail",
        to_float(daily["rhythm_scale"].min()) if not daily.is_empty() else None,
        ">0",
        "本阶段验证平滑风险预算，不允许硬清仓。",
    )
    add(
        "any_smooth_improves_return_and_drawdown",
        "pass" if not improve_both.is_empty() else "warn",
        improve_both.height,
        ">0",
        "若没有任何平滑规则同向改善，慢节奏只能降级为监控指标。",
    )
    add(
        "candidate_smooth_improves_return_and_drawdown",
        "pass" if not candidate_improve_both.is_empty() else "warn",
        f"{candidate_improve_both.height}/{candidate.height}",
        ">0",
        "重点检查第320候选形状在平滑规则下是否仍有同向改善。",
    )
    add(
        "candidate_smooth_within_20pct",
        "pass" if not candidate_within_20.is_empty() else "warn",
        f"{candidate_within_20.height}/{candidate.height}",
        ">0",
        "用户目标允许20%以内回撤，平滑规则应至少有一个候选进入该约束。",
    )
    add(
        "candidate_drawdown_segment_dd_improved",
        "pass" if candidate_stress_segment_improved_dd.height == candidate_stress_segment.height else "warn",
        f"{candidate_stress_segment_improved_dd.height}/{candidate_stress_segment.height}",
        "all",
        "若只改善全样本、不改善2022-2024压力段，则更可能是路径偶然。",
    )
    add(
        "no_new_signal_search",
        "pass",
        "target exposure scaling only",
        "target exposure scaling only",
        "本阶段不改变alpha、持有期、top_k、行业上限和成交约束。",
    )
    return pl.DataFrame(rows)


def write_report(summary: pl.DataFrame, segment: pl.DataFrame, quality: pl.DataFrame, paths: dict[str, Path]) -> Path:
    failed = quality.filter(pl.col("status") == "fail")
    warned = quality.filter(pl.col("status") == "warn")
    stress = summary.filter(pl.col("slow_rhythm_name") != "base_rerun")
    candidate = stress.filter(pl.col("base_scenario") == CANDIDATE_BASE_SCENARIO)
    best_total = stress.sort(["total_return_min_fee", "max_drawdown_min_fee"], descending=[True, True]).row(
        0, named=True
    )
    best_dd = stress.sort(["max_drawdown_min_fee", "total_return_min_fee"], descending=[True, True]).row(0, named=True)
    best_candidate = candidate.sort(["max_drawdown_min_fee", "total_return_min_fee"], descending=[True, True]).row(
        0, named=True
    )
    improve_both_count = stress.filter(
        (pl.col("delta_total_return_min_fee") > 0) & (pl.col("delta_max_drawdown_min_fee") > 0)
    ).height
    candidate_improve_both_count = candidate.filter(
        (pl.col("delta_total_return_min_fee") > 0) & (pl.col("delta_max_drawdown_min_fee") > 0)
    ).height
    candidate_within_20_count = candidate.filter(pl.col("max_drawdown_min_fee") >= MAX_DRAWDOWN_LIMIT).height

    lines = [
        "# 股票震荡industry_resid_core 30万平滑风险预算/分段反证 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前模式：day。",
        "- 当前研究线：股票震荡30万industry_resid_core独立研究线，不接入第78。",
        "- 本阶段性质：第321阶段之后，把`硬阈值清仓`改为`连续风险预算`，并做2018-2022、2022-2024、2024-2026分段反证。",
        f"- 账户规模：`{rhythm_replay.ACCOUNT_SIZE_CNY:,.0f}`元；用户回撤目标：`20%`以内；高收益参考目标：`{pct(HIGH_RETURN_TARGET)}`以上。",
        "- A/B判断：独立研究线的归因/稳健性阶段，不触发第78 A/B。",
        "",
        "## 外部调研判断",
        "",
        "- Moreira/Muir 的波动管理思想强调按可观测风险状态调节暴露，但不能把样本内某个状态直接变成单点开关。",
        "- Smoothing volatility targeting 的核心启发是：平滑暴露可以减少极端缩放和换手，实盘上通常比0/1切换更可信。",
        "- GitHub和公开示例里的风险平价/波动目标实现多以连续权重或风险预算为中心；均值回归系统也常把风控做成组合层overlay，而不是重写alpha。",
        "- 因此本阶段的判断标准不是找最高点，而是看连续缩放是否跨场景、跨压力段改善回撤，同时不明显牺牲收益。",
        "",
        "参考资料：",
        *[f"- [{title}]({url})" for title, url in RESEARCH_SOURCES],
        "",
        "## 核心摘要",
        "",
        f"- 全部平滑变体同向改善收益和回撤：`{improve_both_count}/{stress.height}`。",
        f"- 第320候选形状同向改善收益和回撤：`{candidate_improve_both_count}/{candidate.height}`。",
        f"- 第320候选形状进入20%以内回撤：`{candidate_within_20_count}/{candidate.height}`。",
        f"- 全部平滑变体总收益最高：`{best_total['scenario']}`，总收益`{pct(best_total['total_return_min_fee'])}`，最大回撤`{pct(best_total['max_drawdown_min_fee'])}`，Sharpe `{best_total['sharpe_min_fee']:.3f}`。",
        f"- 全部平滑变体回撤最浅：`{best_dd['scenario']}`，总收益`{pct(best_dd['total_return_min_fee'])}`，最大回撤`{pct(best_dd['max_drawdown_min_fee'])}`，Sharpe `{best_dd['sharpe_min_fee']:.3f}`。",
        f"- 候选形状回撤最浅：`{best_candidate['slow_rhythm_name']}`，总收益`{pct(best_candidate['total_return_min_fee'])}`，最大回撤`{pct(best_candidate['max_drawdown_min_fee'])}`，Sharpe `{best_candidate['sharpe_min_fee']:.3f}`。",
        f"- 质量检查：fail `{failed.height}`项，warn `{warned.height}`项。",
        "",
        "## 总览",
        "",
        markdown_table(
            summary,
            [
                "base_scenario",
                "slow_rhythm_name",
                "lookback_days",
                "taper_start",
                "taper_end",
                "min_scale",
                "total_return_min_fee",
                "max_drawdown_min_fee",
                "delta_total_return_min_fee",
                "delta_max_drawdown_min_fee",
                "sharpe_min_fee",
                "avg_actual_gross_weight",
                "avg_budget_scale",
                "risk_reduced_day_ratio",
                "floor_budget_day_ratio",
            ],
            max_rows=120,
        ),
        "",
        "## 候选形状",
        "",
        markdown_table(
            candidate,
            [
                "base_scenario",
                "slow_rhythm_name",
                "total_return_min_fee",
                "max_drawdown_min_fee",
                "delta_total_return_min_fee",
                "delta_max_drawdown_min_fee",
                "sharpe_min_fee",
                "avg_actual_gross_weight",
                "avg_budget_scale",
                "risk_reduced_day_ratio",
                "floor_budget_day_ratio",
            ],
            max_rows=40,
        ),
        "",
        "## 分段反证",
        "",
        markdown_table(
            segment,
            [
                "base_scenario",
                "slow_rhythm_name",
                "segment",
                "segment_return_min_fee",
                "segment_max_drawdown_min_fee",
                "delta_segment_return_min_fee",
                "delta_segment_max_drawdown_min_fee",
                "segment_sharpe_min_fee",
                "avg_actual_gross_weight",
                "avg_budget_scale",
                "risk_reduced_day_ratio",
            ],
            max_rows=220,
        ),
        "",
        "## 质量检查",
        "",
        markdown_table(quality, ["checkpoint", "status", "value", "expected", "note"], max_rows=80),
        "",
        "## 结论",
        "",
        "- 若平滑规则能改善压力段回撤但收益不过百，说明它更像风险预算overlay，不应单独作为高收益候选。",
        "- 若平滑规则仍能进入20%以内回撤且总收益接近或超过100%，下一步才值得做滚动窗口和paper订单复验。",
        "- 若只有硬清仓能达标、平滑达不到，说明第320更可能是硬阈值样本内偶然，应降级为监控线索。",
        "",
        "## 运行前过拟合反思",
        "",
        "- 判断：否。",
        "- 原因：本阶段不搜索信号，只把第321暴露出的硬阈值风险改成三个预注册连续函数，并要求分段反证。",
        "",
        "## 运行后过拟合反思",
        "",
        "- 判断：看质量检查与分段结果；若同向改善只存在全样本或单一规则，仍不能升级。",
        "- 原因：策略自身收益节奏是样本内发现的二级状态，必须证明不是2022-2024单段巧合。",
        "",
        "## 运行前继续价值反思",
        "",
        "- 判断：是。",
        "- 原因：第319-321已经说明慢节奏有真实风险信息，但硬清仓过敏；连续缩放是更接近实盘的检验。",
        "",
        "## 运行后继续价值反思",
        "",
        "- 判断：取决于是否在压力段改善回撤且不显著毁掉收益。",
        "- 原因：30万账户需要高收益，但不能靠单点清仓阈值维持漂亮曲线。",
        "",
        "## 输出文件",
        "",
    ]
    for name, path in paths.items():
        lines.append(f"- `{name}`：`{path}`")
    paths["report"].write_text("\n".join(lines) + "\n", encoding="utf-8")
    return paths["report"]


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.csv",
        "segment": OUTPUT_DIR / f"{PREFIX}_segment.csv",
        "daily": OUTPUT_DIR / f"{PREFIX}_daily.csv",
        "quality": OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    base_summary = load_base_summary()
    base_daily = load_base_daily()
    target_weights = read_csv_with_symbol(SOURCE_DIR / f"{SOURCE_PREFIX}_target_weights.csv").filter(
        pl.col("scenario").is_in(FOCUS_SCENARIOS)
    )
    stock_df, benchmark_df = load_panels()
    exec_info = build_exec_info(stock_df)

    summary_rows: list[dict[str, Any]] = []
    daily_frames: list[pl.DataFrame] = []

    for base_scenario in FOCUS_SCENARIOS:
        scenario_targets = target_weights.filter(pl.col("scenario") == base_scenario).drop("scenario")
        target_maps = rhythm_replay.lot.build_target_maps(scenario_targets)
        dates = rhythm_replay.lot.build_tracking_dates(scenario_targets, benchmark_df)
        for rule in SMOOTH_RULES:
            rhythm = rhythm_replay.SlowRhythm(rule.name, rule.description)
            originals = patch_replay_rule(rule)
            try:
                orders, daily, _curves, scaled_targets = rhythm_replay.replay_lot_account_with_slow_rhythm(
                    base_scenario,
                    rhythm,
                    target_maps,
                    dates,
                    exec_info,
                )
            finally:
                restore_replay_rule(originals)
            daily = daily.with_columns(
                pl.lit(rule.lookback_days).alias("lookback_days"),
                pl.lit(rule.taper_start).alias("taper_start"),
                pl.lit(rule.taper_end).alias("taper_end"),
                pl.lit(rule.min_scale).alias("min_scale"),
                pl.col("rhythm_scale").alias("budget_scale"),
            )
            summary = rhythm_replay.summarize_variant(base_scenario, rhythm, orders, daily, scaled_targets)
            summary_rows.append(add_rule_fields_to_summary(summary, rule, daily))
            daily_frames.append(daily)

    stress_summary = pl.DataFrame(summary_rows, infer_schema_length=None)
    summary = rhythm_replay.add_base_deltas(
        pl.concat([base_summary, stress_summary], how="diagonal_relaxed")
    ).sort(["base_scenario", "slow_rhythm_name"])
    smooth_daily = pl.concat(daily_frames, how="diagonal_relaxed") if daily_frames else pl.DataFrame()
    daily_all = pl.concat([base_daily, smooth_daily], how="diagonal_relaxed")
    segment = build_segment_summary(daily_all)
    quality = build_quality(summary, segment, daily_all)

    report_path = write_report(summary, segment, quality, paths)
    summary.write_csv(paths["summary"])
    segment.write_csv(paths["segment"])
    daily_all.write_csv(paths["daily"])
    quality.write_csv(paths["quality"])
    write_json(
        paths["meta"],
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "source_dir": str(SOURCE_DIR),
            "source_prefix": SOURCE_PREFIX,
            "base_rhythm_dir": str(BASE_RHYTHM_DIR),
            "base_rhythm_prefix": BASE_RHYTHM_PREFIX,
            "focus_scenarios": FOCUS_SCENARIOS,
            "candidate_base_scenario": CANDIDATE_BASE_SCENARIO,
            "segment_drawdown_start": SEGMENT_DRAWDOWN_START.isoformat(),
            "segment_recovery_start": SEGMENT_RECOVERY_START.isoformat(),
            "smooth_rules": [
                {
                    "name": item.name,
                    "lookback_days": item.lookback_days,
                    "taper_start": item.taper_start,
                    "taper_end": item.taper_end,
                    "min_scale": item.min_scale,
                    "description": item.description,
                }
                for item in SMOOTH_RULES
            ],
            "research_sources": RESEARCH_SOURCES,
            "outputs": {key: str(path) for key, path in paths.items()},
        },
    )
    print(f"report={report_path}")
    print(quality)
    print(
        summary.filter(pl.col("base_scenario") == CANDIDATE_BASE_SCENARIO).select(
            [
                "slow_rhythm_name",
                "total_return_min_fee",
                "max_drawdown_min_fee",
                "delta_total_return_min_fee",
                "delta_max_drawdown_min_fee",
                "sharpe_min_fee",
                "avg_budget_scale",
                "risk_reduced_day_ratio",
            ]
        )
    )


if __name__ == "__main__":
    main()
