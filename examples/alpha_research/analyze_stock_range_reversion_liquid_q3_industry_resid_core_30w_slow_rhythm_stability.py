from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import polars as pl

import analyze_stock_range_reversion_liquid_q3_industry_resid_core_30w_slow_rhythm_replay as rhythm_replay
from analyze_stock_range_reversion_layer_attribution import load_panels
from analyze_stock_range_reversion_liquid_q3_30w_high_return_shape_grid import MAX_DRAWDOWN_LIMIT, to_float
from analyze_stock_range_reversion_liquid_q3_industry_resid_core_30w_loss_sample_attribution import (
    FOCUS_SCENARIOS,
    read_csv_with_symbol,
)
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, pct
from generate_stock_range_reversion_liquid_q3_paper_tracking import markdown_table
from generate_stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality import build_exec_info


SOURCE_DIR: Path = rhythm_replay.SOURCE_DIR
SOURCE_PREFIX: str = rhythm_replay.SOURCE_PREFIX
BASE_RHYTHM_DIR: Path = rhythm_replay.OUTPUT_DIR
BASE_RHYTHM_PREFIX: str = rhythm_replay.PREFIX

OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_industry_resid_core_30w_slow_rhythm_stability_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_industry_resid_core_30w_slow_rhythm_stability_v1"

LOOKBACK_DAYS: tuple[int, ...] = (40, 60, 80)
UP_THRESHOLDS: tuple[float, ...] = (0.03, 0.05, 0.08)
ACTION_SCALE: float = 0.0
CANDIDATE_BASE_SCENARIO: str = "industry_resid_core_h10_top5_gross70_ind1"


@dataclass(frozen=True)
class StabilityRule:
    lookback_days: int
    up_threshold: float
    action_scale: float = ACTION_SCALE

    @property
    def name(self) -> str:
        threshold_bp = int(round(self.up_threshold * 10000))
        return f"lookback{self.lookback_days}_up{threshold_bp}bp_zero"

    @property
    def description(self) -> str:
        return (
            f"若本变体前一日自身{self.lookback_days}日收益>={self.up_threshold:.0%}，"
            f"下一目标日目标权重乘{self.action_scale:.2f}。"
        )


RULES: tuple[StabilityRule, ...] = tuple(
    StabilityRule(lookback, threshold) for lookback in LOOKBACK_DAYS for threshold in UP_THRESHOLDS
)

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = rhythm_replay.RESEARCH_SOURCES


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def calc_prev_return(equity_history: list[float], lookback_days: int) -> float | None:
    if len(equity_history) < lookback_days + 1:
        return None
    base = equity_history[-lookback_days - 1]
    if base <= 0:
        return None
    return equity_history[-1] / base - 1.0


def bucket_return(value: float | None, up_threshold: float) -> str:
    if value is None or value != value:
        return "missing"
    if value >= up_threshold:
        return "ret60_up"
    if value >= -up_threshold:
        return "ret60_flat"
    return "ret60_down"


def load_base_summary() -> pl.DataFrame:
    path = BASE_RHYTHM_DIR / f"{BASE_RHYTHM_PREFIX}_summary.csv"
    return pl.read_csv(path).filter(pl.col("slow_rhythm_name") == "base_rerun")


def patch_replay_rule(rule: StabilityRule) -> tuple[Callable[..., Any], Callable[..., Any], Callable[..., Any]]:
    original_calc = rhythm_replay.calc_prev_ret60
    original_bucket = rhythm_replay.bucket_ret60
    original_scale = rhythm_replay.scale_for_rhythm

    def patched_calc(equity_history: list[float]) -> float | None:
        return calc_prev_return(equity_history, rule.lookback_days)

    def patched_bucket(value: float | None) -> str:
        return bucket_return(value, rule.up_threshold)

    def patched_scale(_rhythm_name: str, prev_strategy_ret60_state: str) -> float:
        return rule.action_scale if prev_strategy_ret60_state == "ret60_up" else 1.0

    rhythm_replay.calc_prev_ret60 = patched_calc
    rhythm_replay.bucket_ret60 = patched_bucket
    rhythm_replay.scale_for_rhythm = patched_scale
    return original_calc, original_bucket, original_scale


def restore_replay_rule(originals: tuple[Callable[..., Any], Callable[..., Any], Callable[..., Any]]) -> None:
    rhythm_replay.calc_prev_ret60, rhythm_replay.bucket_ret60, rhythm_replay.scale_for_rhythm = originals


def build_quality(summary: pl.DataFrame) -> pl.DataFrame:
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
    candidate_stress = stress.filter(pl.col("base_scenario") == CANDIDATE_BASE_SCENARIO)
    improve_both = stress.filter(
        (pl.col("delta_total_return_min_fee") > 0) & (pl.col("delta_max_drawdown_min_fee") > 0)
    )
    candidate_improve_both = candidate_stress.filter(
        (pl.col("delta_total_return_min_fee") > 0) & (pl.col("delta_max_drawdown_min_fee") > 0)
    )
    candidate_within_20 = candidate_stress.filter(pl.col("max_drawdown_min_fee") >= MAX_DRAWDOWN_LIMIT)
    original_candidate = summary.filter(
        (pl.col("base_scenario") == CANDIDATE_BASE_SCENARIO)
        & (pl.col("slow_rhythm_name") == "lookback60_up500bp_zero")
    )
    add(
        "stress_variant_count",
        "pass" if stress.height == len(FOCUS_SCENARIOS) * len(RULES) else "fail",
        stress.height,
        len(FOCUS_SCENARIOS) * len(RULES),
        "四个代表场景乘以9个邻域规则。",
    )
    add(
        "base_summary_count",
        "pass" if summary.filter(pl.col("slow_rhythm_name") == "base_rerun").height == len(FOCUS_SCENARIOS) else "fail",
        summary.filter(pl.col("slow_rhythm_name") == "base_rerun").height,
        len(FOCUS_SCENARIOS),
        "基准来自第320阶段base复现结果。",
    )
    add(
        "original_candidate_present",
        "pass" if original_candidate.height == 1 else "fail",
        original_candidate.height,
        1,
        "必须包含第320候选对应的60日/5%/清仓点。",
    )
    add(
        "all_stress_improve_both_ratio",
        "pass" if improve_both.height / max(stress.height, 1) >= 0.75 else "warn",
        f"{improve_both.height}/{stress.height}",
        ">=75%",
        "若大多数邻域都同向改善，说明不是单点悬崖。",
    )
    add(
        "candidate_neighborhood_improve_both_ratio",
        "pass" if candidate_improve_both.height >= 7 else "warn",
        f"{candidate_improve_both.height}/{candidate_stress.height}",
        ">=7/9",
        "候选形状附近至少大部分参数同向改善。",
    )
    add(
        "candidate_neighborhood_within_20pct_count",
        "pass" if candidate_within_20.height >= 3 else "warn",
        f"{candidate_within_20.height}/{candidate_stress.height}",
        ">=3/9",
        "回撤20%以内不能只靠单个参数点。",
    )
    best_candidate_dd = candidate_stress.select(pl.col("max_drawdown_min_fee").max()).item()
    best_candidate_return = candidate_stress.select(pl.col("total_return_min_fee").max()).item()
    add(
        "candidate_best_dd",
        "pass" if best_candidate_dd >= MAX_DRAWDOWN_LIMIT else "warn",
        pct(best_candidate_dd),
        ">=-20%",
        "候选邻域内最浅回撤。",
    )
    add(
        "candidate_best_return",
        "pass" if best_candidate_return >= 1.0 else "warn",
        pct(best_candidate_return),
        ">=100%",
        "候选邻域内最高收益。",
    )
    add(
        "no_new_signal_search",
        "pass",
        "stress only",
        "stress only",
        "本阶段只做邻域反证，不从中替换候选。",
    )
    return pl.DataFrame(rows)


def summarize_parameter_grid(summary: pl.DataFrame) -> pl.DataFrame:
    stress = summary.filter(pl.col("slow_rhythm_name") != "base_rerun")
    return (
        stress.group_by(["base_scenario", "lookback_days", "up_threshold"])
        .agg(
            pl.col("total_return_min_fee").first().alias("total_return_min_fee"),
            pl.col("max_drawdown_min_fee").first().alias("max_drawdown_min_fee"),
            pl.col("delta_total_return_min_fee").first().alias("delta_total_return_min_fee"),
            pl.col("delta_max_drawdown_min_fee").first().alias("delta_max_drawdown_min_fee"),
            pl.col("sharpe_min_fee").first().alias("sharpe_min_fee"),
            pl.col("avg_actual_gross_weight").first().alias("avg_actual_gross_weight"),
            pl.col("scaled_target_day_ratio").first().alias("scaled_target_day_ratio"),
        )
        .sort(["base_scenario", "lookback_days", "up_threshold"])
    )


def write_report(
    summary: pl.DataFrame,
    parameter_grid: pl.DataFrame,
    yearly: pl.DataFrame,
    quality: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    report_path = paths["report"]
    failed = quality.filter(pl.col("status") == "fail")
    warned = quality.filter(pl.col("status") == "warn")
    stress = summary.filter(pl.col("slow_rhythm_name") != "base_rerun")
    candidate_stress = stress.filter(pl.col("base_scenario") == CANDIDATE_BASE_SCENARIO)
    best_candidate_dd = candidate_stress.sort(
        ["max_drawdown_min_fee", "total_return_min_fee"], descending=[True, True]
    ).row(0, named=True)
    best_candidate_return = candidate_stress.sort(
        ["total_return_min_fee", "max_drawdown_min_fee"], descending=[True, True]
    ).row(0, named=True)
    original_candidate = candidate_stress.filter(pl.col("slow_rhythm_name") == "lookback60_up500bp_zero").row(
        0, named=True
    )
    improve_both_count = stress.filter(
        (pl.col("delta_total_return_min_fee") > 0) & (pl.col("delta_max_drawdown_min_fee") > 0)
    ).height
    candidate_improve_count = candidate_stress.filter(
        (pl.col("delta_total_return_min_fee") > 0) & (pl.col("delta_max_drawdown_min_fee") > 0)
    ).height
    candidate_within20_count = candidate_stress.filter(pl.col("max_drawdown_min_fee") >= MAX_DRAWDOWN_LIMIT).height
    lines = [
        "# 股票震荡industry_resid_core 30万慢节奏邻域稳健性反证 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前模式：day。",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：第320候选后的邻域稳健性反证，不从邻域中挑新最优。",
        f"- 邻域：lookback `{LOOKBACK_DAYS}`，阈值 `{UP_THRESHOLDS}`，动作 scale `{ACTION_SCALE}`。",
        "",
        "## 外部调研判断",
        "",
        "- 业界风险预算/波动目标类方法最怕参数点刚好贴合样本，因此候选出现后必须做邻域反证。",
        "- 本阶段不改变alpha、不换组合形状、不选择新最优，只检查第320的`60日/5%/清仓`是否是孤点。",
        "",
        "参考资料：",
        *[f"- [{title}]({url})" for title, url in RESEARCH_SOURCES],
        "",
        "## 核心摘要",
        "",
        f"- 全部邻域变体同时改善收益和回撤：`{improve_both_count}/{stress.height}`。",
        f"- 候选形状邻域同时改善收益和回撤：`{candidate_improve_count}/{candidate_stress.height}`。",
        f"- 候选形状邻域进入20%以内回撤：`{candidate_within20_count}/{candidate_stress.height}`。",
        f"- 第320原候选点：`{original_candidate['slow_rhythm_name']}`，总收益`{pct(original_candidate['total_return_min_fee'])}`，最大回撤`{pct(original_candidate['max_drawdown_min_fee'])}`，Sharpe `{original_candidate['sharpe_min_fee']:.3f}`。",
        f"- 候选邻域最大回撤最浅：`{best_candidate_dd['slow_rhythm_name']}`，总收益`{pct(best_candidate_dd['total_return_min_fee'])}`，最大回撤`{pct(best_candidate_dd['max_drawdown_min_fee'])}`。",
        f"- 候选邻域收益最高：`{best_candidate_return['slow_rhythm_name']}`，总收益`{pct(best_candidate_return['total_return_min_fee'])}`，最大回撤`{pct(best_candidate_return['max_drawdown_min_fee'])}`。",
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
                "up_threshold",
                "total_return_min_fee",
                "max_drawdown_min_fee",
                "delta_total_return_min_fee",
                "delta_max_drawdown_min_fee",
                "sharpe_min_fee",
                "avg_actual_gross_weight",
                "scaled_target_day_ratio",
            ],
            max_rows=160,
        ),
        "",
        "## 候选形状邻域",
        "",
        markdown_table(
            parameter_grid.filter(pl.col("base_scenario") == CANDIDATE_BASE_SCENARIO),
            parameter_grid.columns,
            max_rows=80,
        ),
        "",
        "## 候选形状年度拆分",
        "",
        markdown_table(
            yearly.filter(pl.col("base_scenario") == CANDIDATE_BASE_SCENARIO),
            [
                "base_scenario",
                "slow_rhythm_name",
                "year",
                "year_return_min_fee",
                "year_curve_drawdown_min_fee",
                "avg_actual_gross_weight",
                "avg_rhythm_scale",
                "scaled_day_ratio",
            ],
            max_rows=160,
        ),
        "",
        "## 质量检查",
        "",
        markdown_table(quality, ["checkpoint", "status", "value", "expected", "note"], max_rows=80),
        "",
        "## 结论",
        "",
        "- 若候选邻域大部分仍改善收益和回撤，说明第320不是明显悬崖点；下一步应做分段/滚动反证。",
        "- 若只有原候选点满足20%回撤，也要保持谨慎：实盘前仍需纸面监控与订单生成验证。",
        "",
        "## 运行前过拟合反思",
        "",
        "- 判断：否，但这是候选出现后的必要反证。",
        "- 原因：本阶段预先固定邻域，不从结果里替换候选。",
        "",
        "## 运行后过拟合反思",
        "",
        "- 判断：取决于邻域覆盖率；若大部分邻域同向改善，过拟合疑虑下降但不消失。",
        "- 原因：慢节奏规则仍基于样本内发现，需要后续分段和纸面监控。",
        "",
        "## 运行前继续价值反思",
        "",
        "- 判断：是。",
        "- 原因：第320首次出现满足目标候选，必须验证是否为参数孤点。",
        "",
        "## 运行后继续价值反思",
        "",
        "- 判断：若邻域稳定，则继续；若不稳定，则降级为研究线索。",
        "- 原因：实盘候选不能建立在单点舒适参数上。",
        "",
        "## 输出文件",
        "",
    ]
    for name, path in paths.items():
        lines.append(f"- `{name}`：`{path}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = {
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.csv",
        "parameter_grid": OUTPUT_DIR / f"{PREFIX}_parameter_grid.csv",
        "yearly": OUTPUT_DIR / f"{PREFIX}_yearly.csv",
        "daily": OUTPUT_DIR / f"{PREFIX}_daily.csv",
        "quality": OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    base_summary = load_base_summary()
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
        for rule in RULES:
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
            summary = rhythm_replay.summarize_variant(base_scenario, rhythm, orders, daily, scaled_targets)
            summary["lookback_days"] = rule.lookback_days
            summary["up_threshold"] = rule.up_threshold
            summary["action_scale"] = rule.action_scale
            summary_rows.append(summary)
            daily_frames.append(
                daily.with_columns(
                    pl.lit(rule.lookback_days).alias("lookback_days"),
                    pl.lit(rule.up_threshold).alias("up_threshold"),
                    pl.lit(rule.action_scale).alias("action_scale"),
                )
            )

    stress_summary = pl.DataFrame(summary_rows, infer_schema_length=None)
    summary = rhythm_replay.add_base_deltas(
        pl.concat([base_summary, stress_summary], how="diagonal_relaxed")
    ).sort(["base_scenario", "slow_rhythm_name"])
    daily_all = pl.concat(daily_frames, how="diagonal_relaxed") if daily_frames else pl.DataFrame()
    yearly = rhythm_replay.build_yearly(daily_all)
    parameter_grid = summarize_parameter_grid(summary)
    quality = build_quality(summary)
    report_path = write_report(summary, parameter_grid, yearly, quality, paths)

    summary.write_csv(paths["summary"])
    parameter_grid.write_csv(paths["parameter_grid"])
    yearly.write_csv(paths["yearly"])
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
            "lookback_days": LOOKBACK_DAYS,
            "up_thresholds": UP_THRESHOLDS,
            "action_scale": ACTION_SCALE,
            "candidate_base_scenario": CANDIDATE_BASE_SCENARIO,
            "rules": [(item.name, item.description) for item in RULES],
            "research_sources": RESEARCH_SOURCES,
            "outputs": {key: str(path) for key, path in paths.items()},
        },
    )
    print(f"report={report_path}")
    print(quality)
    print(
        parameter_grid.filter(pl.col("base_scenario") == CANDIDATE_BASE_SCENARIO).select(
            [
                "lookback_days",
                "up_threshold",
                "total_return_min_fee",
                "max_drawdown_min_fee",
                "delta_total_return_min_fee",
                "delta_max_drawdown_min_fee",
                "sharpe_min_fee",
            ]
        )
    )


if __name__ == "__main__":
    main()
