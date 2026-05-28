from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

import analyze_qmt_roll_stage395_stage079_product_direction_failure_cooldown as s095
from analyze_qmt_roll_stage324_true_combo_capital_margin import _to_builtin
from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage428_stage079_weighted_env_gate_true_engine_v1"
OUTPUT_PREFIX = "qmt_roll_stage428_stage079_weighted_env_gate_true_engine"
LINE_ID = "futures_trend_drawdown30_preserve_return"

ACCOUNT_CAPITAL = 615_000.0
BASELINE_VARIANT = "stage079"
ENV_GATE_VARIANT = "stage079_weighted_env_gate_default_floor035_true_engine"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_{MODEL_TAG}.csv"
SCORE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_score_{MODEL_TAG}.csv"
CONSTRAINT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_constraints_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
PROMOTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_promotion_{MODEL_TAG}.csv"
CANDIDATE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_candidate_summary_{MODEL_TAG}.csv"
DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_equity_drawdown_{MODEL_TAG}.png"


@dataclass(frozen=True)
class Profile:
    variant: str
    label: str
    overrides: dict[str, Any]
    note: str


def _weighted_env_gate_default_overrides() -> dict[str, Any]:
    return {
        "enable_weighted_env_gate": True,
        "weighted_env_gate_close_position_good_max": 0.25,
        "weighted_env_gate_close_position_bad_min": 0.60,
        "weighted_env_gate_range_good_min": 0.60,
        "weighted_env_gate_range_bad_max": 0.00,
        "weighted_env_gate_selected_rate_good_max": 0.35,
        "weighted_env_gate_selected_rate_bad_min": 0.75,
        "weighted_env_gate_weight_floor": 0.35,
    }


PROFILES: tuple[Profile, ...] = (
    Profile(
        BASELINE_VARIANT,
        "Stage079真实引擎基准：50万C3下单+11.5万现金",
        {},
        "C3真实引擎日权益外加11.5万现金，作为唯一硬约束基准。",
    ),
    Profile(
        ENV_GATE_VARIANT,
        "真实引擎：Stage079 weighted_env_gate 默认形状 floor0.35",
        _weighted_env_gate_default_overrides(),
        "复用Stage096 no-op探针已存在的环境门控；只测默认阈值和floor0.35，不扫环境阈值或权重。",
    ),
)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s095._md_table(frame, max_rows=max_rows)


def _calendar_equity(daily: pd.DataFrame, variant: str) -> pd.Series:
    frame = daily[daily["variant"].eq(variant) & daily["slippage_multiplier"].eq(1.0)].copy()
    frame = frame.sort_values("date").drop_duplicates("date", keep="last")
    equity = pd.Series(frame["equity"].to_numpy(dtype=float), index=pd.to_datetime(frame["date"]))
    calendar = pd.date_range(equity.index.min(), equity.index.max(), freq="D")
    return equity.reindex(calendar).ffill().dropna()


def _as_candidate(profile: Profile, equity: pd.Series) -> Any:
    return s095.s087.Candidate(
        variant=profile.variant,
        label=profile.label,
        equity=equity,
        capital_used=ACCOUNT_CAPITAL,
        candidate_class="true_engine_weighted_env_gate",
        eligible_for_promotion=True,
        note=profile.note,
    )


def _run_engine(profile: Profile, slippage_multiplier: float) -> tuple[pd.DataFrame, dict[str, Any], pd.DataFrame]:
    stage095_profile = s095.Profile(profile.variant, profile.label, profile.overrides, profile.note)
    preload_start = max(s095.PRELOAD_START_DT, s095.START_DT - s095.timedelta(days=365))
    print(f"[stage428] run {profile.variant} slippage={slippage_multiplier:g}", flush=True)
    overrides = s095._profile_overrides(stage095_profile)
    engine, metadata = s095.build_backtest_engine(
        preload_start=preload_start,
        backtest_end=s095.END_DT,
        capital=s095.FUTURES_CAPITAL,
        product_universe_csv_path=str(overrides.get("product_universe_csv_path", "") or ""),
    )
    if slippage_multiplier != 1.0:
        engine.slippages = {
            vt_symbol: float(value) * float(slippage_multiplier)
            for vt_symbol, value in getattr(engine, "slippages", {}).items()
        }

    setting = s095.build_roll_setting(
        metadata["margin_ratios"],
        risk_ratio=s095.BASE_RISK_RATIO,
        strategy_overrides=overrides,
    )
    setting["capital_base"] = s095.FUTURES_CAPITAL
    engine.add_strategy(s095.QmtRollPortfolioStrategy, setting)
    engine.load_data()
    engine.run_backtesting()
    daily_df = engine.calculate_result()
    if daily_df is None:
        raise RuntimeError(f"empty daily result for {profile.variant}")
    analysis_df = daily_df.copy()
    analysis_df = analysis_df.loc[
        (analysis_df.index >= s095.START_DT.date())
        & (analysis_df.index <= s095.END_DT.date())
    ]
    statistics = dict(engine.calculate_statistics(analysis_df))
    win_ratio_pct, win_count, round_trip_count = s095.compute_round_trip_win_ratio(engine)
    statistics["win_ratio"] = win_ratio_pct
    statistics["win_count"] = win_count
    statistics["round_trip_count"] = round_trip_count

    strategy = getattr(engine, "strategy", None)
    candidates = pd.DataFrame(getattr(strategy, "entry_candidate_snapshots", []) if strategy else [])
    if not candidates.empty:
        candidates["variant"] = profile.variant
        candidates["slippage_multiplier"] = slippage_multiplier
    return analysis_df, statistics, candidates


def _cost_stress(cost_daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    baseline_dd: dict[float, float] = {}
    for multiplier in sorted(cost_daily["slippage_multiplier"].unique()):
        one = cost_daily[cost_daily["slippage_multiplier"].eq(multiplier)]
        for profile in PROFILES:
            frame = one[one["variant"].eq(profile.variant)].sort_values("date")
            equity = pd.Series(frame["equity"].to_numpy(dtype=float), index=pd.to_datetime(frame["date"]))
            calendar = pd.date_range(equity.index.min(), equity.index.max(), freq="D")
            equity = equity.reindex(calendar).ffill().dropna()
            nav = equity / ACCOUNT_CAPITAL
            max_dd = s095.s087._max_drawdown(nav)
            if profile.variant == BASELINE_VARIANT:
                baseline_dd[float(multiplier)] = max_dd
            rows.append(
                {
                    "variant": profile.variant,
                    "label": profile.label,
                    "slippage_multiplier": float(multiplier),
                    "total_return_pct": float((nav.iloc[-1] - 1.0) * 100.0),
                    "max_dd_pct": max_dd,
                }
            )
    result = pd.DataFrame(rows)
    result["baseline_stage079_max_dd_pct"] = result["slippage_multiplier"].map(baseline_dd)
    result["not_worse_than_stage079_stress"] = (
        result["max_dd_pct"] >= result["baseline_stage079_max_dd_pct"] - 1e-9
    ).astype(int)
    return result


def _candidate_summary(profile: Profile, candidates: pd.DataFrame) -> dict[str, Any]:
    base = {
        "variant": profile.variant,
        "flat_candidate_count": 0,
        "opened_flat_entry_count": 0,
        "env_gate_enabled_count": 0,
        "env_gate_scaled_count": 0,
        "env_gate_zeroed_count": 0,
        "env_gate_avg_weight": 0.0,
        "env_gate_min_weight": 0.0,
        "env_gate_median_weight": 0.0,
        "env_gate_avg_candidate_count": 0.0,
        "env_gate_avg_close_position_60d": 0.0,
        "env_gate_avg_range_pct_zscore_120": 0.0,
        "opened_median_selected_volume": 0.0,
        "opened_median_ungated_volume": 0.0,
    }
    if candidates.empty:
        return base

    flat = candidates[candidates["entry_context"].astype(str).eq("flat_entry")].copy()
    if flat.empty:
        return base

    numeric_columns = [
        "env_gate_enabled",
        "env_gate_weight",
        "env_candidate_count",
        "env_avg_close_position_60d",
        "env_avg_range_pct_zscore_120",
        "selected_volume",
        "selected_volume_ungated",
    ]
    for column in numeric_columns:
        flat[column] = pd.to_numeric(flat.get(column, 0.0), errors="coerce").fillna(0.0)

    opened = flat[flat["candidate_status"].astype(str).eq("opened")]
    enabled = flat[flat["env_gate_enabled"].gt(0)]
    scaled = enabled[enabled["selected_volume"].lt(enabled["selected_volume_ungated"])]
    zeroed = scaled[scaled["selected_volume"].eq(0)]

    def median_or_zero(frame: pd.DataFrame, column: str) -> float:
        value = frame[column].median() if not frame.empty else 0.0
        return float(value) if pd.notna(value) else 0.0

    def mean_or_zero(frame: pd.DataFrame, column: str) -> float:
        value = frame[column].mean() if not frame.empty else 0.0
        return float(value) if pd.notna(value) else 0.0

    base.update(
        {
            "flat_candidate_count": int(len(flat)),
            "opened_flat_entry_count": int(len(opened)),
            "env_gate_enabled_count": int(len(enabled)),
            "env_gate_scaled_count": int(len(scaled)),
            "env_gate_zeroed_count": int(len(zeroed)),
            "env_gate_avg_weight": mean_or_zero(enabled, "env_gate_weight"),
            "env_gate_min_weight": float(enabled["env_gate_weight"].min()) if not enabled.empty else 0.0,
            "env_gate_median_weight": median_or_zero(enabled, "env_gate_weight"),
            "env_gate_avg_candidate_count": mean_or_zero(enabled, "env_candidate_count"),
            "env_gate_avg_close_position_60d": mean_or_zero(enabled, "env_avg_close_position_60d"),
            "env_gate_avg_range_pct_zscore_120": mean_or_zero(enabled, "env_avg_range_pct_zscore_120"),
            "opened_median_selected_volume": median_or_zero(opened, "selected_volume"),
            "opened_median_ungated_volume": median_or_zero(opened, "selected_volume_ungated"),
        }
    )
    return base


def _plot_equity_drawdown(daily: pd.DataFrame) -> None:
    one = daily[daily["slippage_multiplier"].eq(1.0)].copy()
    fig, axes = plt.subplots(2, 1, figsize=(13, 8), sharex=True)
    for profile in PROFILES:
        frame = one[one["variant"].eq(profile.variant)].sort_values("date")
        equity = pd.Series(frame["equity"].to_numpy(dtype=float), index=pd.to_datetime(frame["date"]))
        calendar = pd.date_range(equity.index.min(), equity.index.max(), freq="D")
        equity = equity.reindex(calendar).ffill().dropna()
        nav = equity / ACCOUNT_CAPITAL
        dd = nav / nav.cummax() - 1.0
        axes[0].plot(equity.index, nav, label=profile.variant, linewidth=1.4)
        axes[1].plot(dd.index, dd * 100.0, label=profile.variant, linewidth=1.1)
    axes[0].set_title("Stage128 weighted env gate account NAV")
    axes[0].set_ylabel("NAV")
    axes[0].grid(alpha=0.25)
    axes[0].legend(fontsize=8)
    axes[1].set_title("Drawdown")
    axes[1].set_ylabel("Drawdown %")
    axes[1].grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    horizon: pd.DataFrame,
    score: pd.DataFrame,
    cost: pd.DataFrame,
    promotion: pd.DataFrame,
    candidate_summary: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    focus_summary = [
        "variant",
        "total_return_pct",
        "max_dd_pct",
        "sharpe",
        "ulcer_pct",
        "rolling252_dd30_breach_rate",
        "rolling504_dd30_breach_rate",
        "total_trade_count",
        "win_ratio",
    ]
    focus_horizon = [
        "variant",
        "horizon_days",
        "return_p05_pct",
        "return_median_pct",
        "positive_return_rate",
        "annualized_below_5pct_rate",
        "max_dd_worst_pct",
        "dd20_breach_rate",
        "dd30_breach_rate",
        "ulcer_p95_pct",
        "longest_underwater_p95_days",
    ]
    focus_score = ["variant", "score_90d", "score_180d", "short_holding_score"]
    focus_cost = ["variant", "slippage_multiplier", "total_return_pct", "max_dd_pct", "not_worse_than_stage079_stress"]
    focus_promotion = [
        "variant",
        "promotion_pass",
        "score90_improve_ge10pct",
        "score180_improve_ge10pct",
        "improved_5of8_each",
        "failed_constraints",
    ]
    report = [
        "# Stage128 Stage079 Weighted Env Gate真实引擎验证",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：固定环境质量门控 A/C 验证；不改入场信号、不改品种池、不扫环境阈值。",
        f"- 图表：`{CHART_PATH}`",
        "",
        "## 外部调研与判断",
        "",
        "- 时间序列动量/趋势跟随研究指出强趋势后可能出现反转风险，趋势强度和波动状态是常见风险管理变量。",
        "- GitHub 与公开期货趋势框架常见做法是用波动、趋势强度、仓位环境过滤交易，但必须用真实引擎验证，不能只看诊断曲线。",
        "- 本阶段只验证仓库内已存在且默认关闭的 `weighted_env_gate` 默认形状；若失败，不继续调 `0.25/0.60/0.35` 等阈值。",
        "",
        "## 候选定义",
        "",
        "- A：Stage079，`50万C3下单 + 11.5万现金`。",
        "- C：A + `enable_weighted_env_gate=True`，默认 close-position/range/selected-rate 三组件，`weight_floor=0.35`，只影响 `flat_entry`。",
        "",
        "## 决策",
        "",
        "```json",
        json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2),
        "```",
        "",
        "## 全周期硬指标",
        "",
        _md_table(summary[focus_summary]),
        "",
        "## 3个月/6个月任意启动体验",
        "",
        _md_table(horizon[focus_horizon].sort_values(["variant", "horizon_days"])),
        "",
        "## 持有体验评分",
        "",
        _md_table(score[focus_score].drop_duplicates("variant")),
        "",
        "## 成本压力",
        "",
        _md_table(cost[focus_cost].sort_values(["variant", "slippage_multiplier"])),
        "",
        "## 候选归因",
        "",
        _md_table(candidate_summary),
        "",
        "## 晋级闸门",
        "",
        _md_table(promotion[focus_promotion]),
        "",
        "## 反过拟合说明",
        "",
        "- 只验证一个仓库已存在的默认形状，不新增相邻参数扫描。",
        "- 特征只使用入场日前可见的候选环境，不使用未来收益、亏损窗口或品种名单。",
        "- 若硬约束失败，本路线停止；不通过调 floor、close position、range zscore 或 selected rate 救援。",
    ]
    REPORT_PATH.write_text("\n".join(report), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    normal_daily_parts: list[pd.DataFrame] = []
    cost_daily_parts: list[pd.DataFrame] = []
    candidate_summary_rows: list[dict[str, Any]] = []
    normal_stats: dict[str, dict[str, Any]] = {}

    for multiplier in (1.0, 2.0, 3.0, 5.0):
        for profile in PROFILES:
            analysis_df, statistics, candidates_frame = _run_engine(profile, multiplier)
            stage095_profile = s095.Profile(profile.variant, profile.label, profile.overrides, profile.note)
            daily = s095._daily_equity(stage095_profile, analysis_df, multiplier)
            cost_daily_parts.append(daily)
            if multiplier == 1.0:
                normal_daily_parts.append(daily)
                normal_stats[profile.variant] = statistics
                candidate_summary_rows.append(_candidate_summary(profile, candidates_frame))

    normal_daily = pd.concat(normal_daily_parts, ignore_index=True)
    cost_daily = pd.concat(cost_daily_parts, ignore_index=True)

    candidates = [_as_candidate(profile, _calendar_equity(normal_daily, profile.variant)) for profile in PROFILES]
    summary = pd.DataFrame([s095.s087._stats(candidate) for candidate in candidates])
    for profile in PROFILES:
        stats = normal_stats.get(profile.variant, {})
        mask = summary["variant"].eq(profile.variant)
        summary.loc[mask, "total_slippage"] = float(stats.get("total_slippage", 0.0) or 0.0)
        summary.loc[mask, "total_commission"] = float(stats.get("total_commission", 0.0) or 0.0)
        summary.loc[mask, "total_trade_count"] = int(stats.get("total_trade_count", 0) or 0)
        summary.loc[mask, "win_ratio"] = float(stats.get("win_ratio", 0.0) or 0.0)

    horizon = pd.DataFrame(
        [s095.s087._horizon_metrics(candidate, horizon_days) for candidate in candidates for horizon_days in (90, 180)]
    )
    score = s095.s087._score_horizons(horizon)
    cost = _cost_stress(cost_daily)
    constraints = s095.s087._constraints(summary, cost)
    promotion = s095.s087._promotion(score, horizon, constraints)
    candidate_summary = pd.DataFrame(candidate_summary_rows)

    promoted = promotion[promotion["promotion_pass"].eq(1)]
    decision = {
        "stage": "Stage128",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": "promote" if not promoted.empty else "no_promotion",
        "promoted_variants": promoted["variant"].tolist(),
        "best_by_short_holding_score": str(promotion.iloc[0]["variant"]) if not promotion.empty else "",
        "normal_cost_chart": str(CHART_PATH),
        "judgement": "若默认weighted_env_gate不能通过，不继续扫环境阈值或weight_floor救援。",
    }

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon.to_csv(HORIZON_PATH, index=False, encoding="utf-8-sig")
    score.to_csv(SCORE_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    constraints.to_csv(CONSTRAINT_PATH, index=False, encoding="utf-8-sig")
    promotion.to_csv(PROMOTION_PATH, index=False, encoding="utf-8-sig")
    candidate_summary.to_csv(CANDIDATE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    normal_daily.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _plot_equity_drawdown(normal_daily)
    _write_report(summary, horizon, score, cost, promotion, candidate_summary, decision)

    print(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2), flush=True)
    print(f"[stage428] report={REPORT_PATH}", flush=True)
    print(f"[stage428] chart={CHART_PATH}", flush=True)


if __name__ == "__main__":
    main()
