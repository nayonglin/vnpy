from __future__ import annotations

import importlib.util
import json
import math
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from analyze_qmt_roll_stage324_true_combo_capital_margin import (
    TOTAL_CAPITAL as FUTURES_CAPITAL,
    _c3_overrides,
    _to_builtin,
)
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy
from qmt_universe import END_DT, PRELOAD_START_DT, START_DT
from run_qmt_alignment_backtest import OUTPUT_DIR
from run_qmt_roll_backtest import (
    build_backtest_engine,
    build_roll_setting,
    compute_round_trip_win_ratio,
)
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


PROJECT_DIR = Path(__file__).resolve().parent
STAGE087_SCRIPT = PROJECT_DIR / "analyze_qmt_roll_stage387_stage079_short_holding_candidates.py"
MODEL_TAG = "stage395_stage079_product_direction_failure_cooldown_v1"
OUTPUT_PREFIX = "qmt_roll_stage395_stage079_product_direction_failure_cooldown"
LINE_ID = "futures_trend_drawdown30_preserve_return"

ACCOUNT_CAPITAL = 615_000.0
STAGE079_CASH = 115_000.0
BASELINE_VARIANT = "stage079"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_{MODEL_TAG}.csv"
SCORE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_score_{MODEL_TAG}.csv"
CONSTRAINT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_constraints_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
PROMOTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_promotion_{MODEL_TAG}.csv"
TRIGGER_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cooldown_triggers_{MODEL_TAG}.csv"
DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_equity_drawdown_{MODEL_TAG}.png"


def _load_stage087_module():
    spec = importlib.util.spec_from_file_location("stage087_gate_for_stage395", STAGE087_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {STAGE087_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["stage087_gate_for_stage395"] = module
    spec.loader.exec_module(module)
    return module


s087 = _load_stage087_module()


@dataclass(frozen=True)
class Profile:
    variant: str
    label: str
    overrides: dict[str, Any]
    note: str


def _merge(*items: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for item in items:
        merged.update(item)
    return merged


def _failure_cooldown_overrides() -> dict[str, Any]:
    return {
        "enable_product_direction_failure_cooldown": True,
        "product_direction_failure_cooldown_lookback_days": 252,
        "product_direction_failure_cooldown_min_consecutive_failures": 3,
        "product_direction_failure_cooldown_days": 90,
        "product_direction_failure_cooldown_entry_contexts": "flat_entry",
    }


PROFILES: tuple[Profile, ...] = (
    Profile(
        BASELINE_VARIANT,
        "Stage079真实引擎基准：50万C3下单+11.5万现金",
        {},
        "C3真实引擎日权益外加11.5万现金，作为唯一硬约束基准。",
    ),
    Profile(
        "pd_fail3_252d_cool90_true_engine",
        "真实引擎：同品种同方向252日内3连亏后flat entry冷却90日",
        _failure_cooldown_overrides(),
        "Stage094固定后续候选；只验证3次/252日/90日，不扫次数和天数小数。",
    ),
)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "无数据。"
    view = frame.copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: f"{x:.4f}" if pd.notna(x) else "")
    return view.to_markdown(index=False)


def _profile_overrides(profile: Profile) -> dict[str, Any]:
    return _merge(_c3_overrides(START_DT), profile.overrides)


def _run_engine(
    profile: Profile,
    slippage_multiplier: float = 1.0,
) -> tuple[pd.DataFrame, dict[str, Any], pd.DataFrame]:
    preload_start = max(PRELOAD_START_DT, START_DT - timedelta(days=365))
    print(f"[stage395] run {profile.variant} slippage={slippage_multiplier:g}", flush=True)
    overrides = _profile_overrides(profile)
    engine, metadata = build_backtest_engine(
        preload_start=preload_start,
        backtest_end=END_DT,
        capital=FUTURES_CAPITAL,
        product_universe_csv_path=str(overrides.get("product_universe_csv_path", "") or ""),
    )
    if slippage_multiplier != 1.0:
        engine.slippages = {
            vt_symbol: float(value) * float(slippage_multiplier)
            for vt_symbol, value in getattr(engine, "slippages", {}).items()
        }

    setting = build_roll_setting(
        metadata["margin_ratios"],
        risk_ratio=BASE_RISK_RATIO,
        strategy_overrides=overrides,
    )
    setting["capital_base"] = FUTURES_CAPITAL
    engine.add_strategy(QmtRollPortfolioStrategy, setting)
    engine.load_data()
    engine.run_backtesting()
    daily_df = engine.calculate_result()
    if daily_df is None:
        raise RuntimeError(f"empty daily result for {profile.variant}")
    analysis_df = daily_df.copy()
    analysis_df = analysis_df.loc[
        (analysis_df.index >= START_DT.date())
        & (analysis_df.index <= END_DT.date())
    ]
    statistics = dict(engine.calculate_statistics(analysis_df))
    win_ratio_pct, win_count, round_trip_count = compute_round_trip_win_ratio(engine)
    statistics["win_ratio"] = win_ratio_pct
    statistics["win_count"] = win_count
    statistics["round_trip_count"] = round_trip_count

    strategy = getattr(engine, "strategy", None)
    trigger_rows = getattr(strategy, "product_direction_failure_cooldown_events", []) if strategy else []
    triggers = pd.DataFrame(trigger_rows)
    if not triggers.empty:
        triggers["date"] = pd.to_datetime(triggers["date"], errors="coerce").dt.normalize()
        triggers["variant"] = profile.variant
        triggers["slippage_multiplier"] = slippage_multiplier
        triggers["cooldown_count_total"] = int(getattr(strategy, "product_direction_failure_cooldown_count", 0))

    return analysis_df, statistics, triggers


def _daily_equity(profile: Profile, analysis_df: pd.DataFrame, slippage_multiplier: float) -> pd.DataFrame:
    frame = analysis_df.copy().reset_index().rename(columns={"index": "date"})
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame.dropna(subset=["date"]).sort_values("date").drop_duplicates("date", keep="last")
    frame["active_balance"] = pd.to_numeric(frame.get("balance", FUTURES_CAPITAL), errors="coerce").ffill().fillna(FUTURES_CAPITAL)
    frame["active_net_pnl"] = pd.to_numeric(frame.get("net_pnl", 0.0), errors="coerce").fillna(0.0)
    frame["active_slippage"] = pd.to_numeric(frame.get("slippage", 0.0), errors="coerce").fillna(0.0)
    frame["equity"] = frame["active_balance"] + STAGE079_CASH
    frame["variant"] = profile.variant
    frame["label"] = profile.label
    frame["slippage_multiplier"] = slippage_multiplier
    return frame[["date", "variant", "label", "slippage_multiplier", "active_balance", "active_net_pnl", "active_slippage", "equity"]]


def _calendar_equity(daily: pd.DataFrame, variant: str) -> pd.Series:
    frame = daily[daily["variant"].eq(variant) & daily["slippage_multiplier"].eq(1.0)].copy()
    frame = frame.sort_values("date").drop_duplicates("date", keep="last")
    equity = pd.Series(frame["equity"].to_numpy(dtype=float), index=pd.to_datetime(frame["date"]))
    calendar = pd.date_range(equity.index.min(), equity.index.max(), freq="D")
    return equity.reindex(calendar).ffill().dropna()


def _as_stage087_candidate(profile: Profile, equity: pd.Series) -> Any:
    return s087.Candidate(
        variant=profile.variant,
        label=profile.label,
        equity=equity,
        capital_used=ACCOUNT_CAPITAL,
        candidate_class="true_engine_product_direction_failure_cooldown",
        eligible_for_promotion=True,
        note=profile.note,
    )


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
            max_dd = s087._max_drawdown(nav)
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


def _trigger_summary(triggers: pd.DataFrame) -> pd.DataFrame:
    if triggers.empty:
        return pd.DataFrame()
    normal = triggers[triggers["slippage_multiplier"].eq(1.0)].copy()
    if normal.empty:
        return pd.DataFrame()
    return (
        normal.groupby("variant", as_index=False)
        .agg(
            blocked_count=("date", "size"),
            product_count=("product_vt_symbol", "nunique"),
            first_block_date=("date", "min"),
            last_block_date=("date", "max"),
            max_consecutive_failures=("consecutive_failures", "max"),
        )
        .sort_values(["blocked_count", "variant"], ascending=[False, True])
    )


def _plot_equity_drawdown(daily: pd.DataFrame) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:  # pragma: no cover
        print(f"[stage395] skip chart: {exc}", flush=True)
        return

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
    axes[0].set_title("Stage095 product-direction failure cooldown account NAV")
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
    constraints: pd.DataFrame,
    promotion: pd.DataFrame,
    triggers: pd.DataFrame,
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
    trigger_summary = _trigger_summary(triggers)

    report = [
        "# Stage095 Stage079同品种同方向失败冷却真实引擎验证",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：Stage094固定后续候选的真实引擎 A/C 验证；不扫次数、不扫冷却天数。",
        f"- 图表：`{CHART_PATH}`",
        "",
        "## 外部调研与判断",
        "",
        "- 趋势跟随和突破策略的主要风险之一是 whipsaw / false breakout；公开资料通常把反复假突破视为震荡或低趋势性状态，而不是加仓信号。",
        "- 因此本阶段把 Stage094 的胜率线索转成冷却候选，而不是连续失败后加仓。",
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
        "## 晋级闸门",
        "",
        _md_table(promotion[focus_promotion]),
        "",
        "## 冷却触发摘要",
        "",
        _md_table(trigger_summary),
        "",
        "## 反过拟合说明",
        "",
        "- 候选固定为 `3次连续已执行亏损 / 252日 / 90日冷却 / flat_entry`，不做邻近扫描。",
        "- 只使用已完成交易结果和入场日前历史，不使用未来收益。",
        "- 若不通过硬约束或3/6个月门禁，不继续用次数、天数或品种做救援。",
    ]
    REPORT_PATH.write_text("\n".join(report), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    normal_daily_parts: list[pd.DataFrame] = []
    cost_daily_parts: list[pd.DataFrame] = []
    trigger_parts: list[pd.DataFrame] = []
    normal_stats: dict[str, dict[str, Any]] = {}

    for multiplier in (1.0, 2.0, 3.0, 5.0):
        for profile in PROFILES:
            analysis_df, statistics, triggers = _run_engine(profile, multiplier)
            daily = _daily_equity(profile, analysis_df, multiplier)
            cost_daily_parts.append(daily)
            if not triggers.empty:
                trigger_parts.append(triggers)
            if multiplier == 1.0:
                normal_daily_parts.append(daily)
                normal_stats[profile.variant] = statistics

    normal_daily = pd.concat(normal_daily_parts, ignore_index=True)
    cost_daily = pd.concat(cost_daily_parts, ignore_index=True)
    triggers = pd.concat(trigger_parts, ignore_index=True) if trigger_parts else pd.DataFrame()

    candidates = [
        _as_stage087_candidate(profile, _calendar_equity(normal_daily, profile.variant))
        for profile in PROFILES
    ]
    summary = pd.DataFrame([s087._stats(candidate) for candidate in candidates])
    for profile in PROFILES:
        stats = normal_stats.get(profile.variant, {})
        mask = summary["variant"].eq(profile.variant)
        summary.loc[mask, "total_slippage"] = float(stats.get("total_slippage", 0.0) or 0.0)
        summary.loc[mask, "total_commission"] = float(stats.get("total_commission", 0.0) or 0.0)
        summary.loc[mask, "total_trade_count"] = int(stats.get("total_trade_count", 0) or 0)
        summary.loc[mask, "win_ratio"] = float(stats.get("win_ratio", 0.0) or 0.0)
    horizon = pd.DataFrame([s087._horizon_metrics(candidate, horizon_days) for candidate in candidates for horizon_days in (90, 180)])
    score = s087._score_horizons(horizon)
    cost = _cost_stress(cost_daily)
    constraints = s087._constraints(summary, cost)
    promotion = s087._promotion(score, horizon, constraints)

    promoted = promotion[promotion["promotion_pass"].eq(1)]
    experience_gate = promotion[
        promotion["score90_improve_ge10pct"].eq(1)
        & promotion["score180_improve_ge10pct"].eq(1)
        & promotion["improved_5of8_each"].eq(1)
    ]
    decision = {
        "stage": "Stage095",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": "promote" if not promoted.empty else "no_promotion",
        "promoted_variants": promoted["variant"].tolist(),
        "experience_gate_variants": experience_gate["variant"].tolist(),
        "best_by_short_holding_score": promotion.iloc[0]["variant"] if not promotion.empty else "",
        "normal_cost_chart": str(CHART_PATH),
        "trigger_count_normal_cost": int(len(triggers[triggers["slippage_multiplier"].eq(1.0)])) if not triggers.empty else 0,
        "note": "真实引擎验证；若无promotion，则同品种同方向失败冷却仅保留为诊断经验。",
    }

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon.to_csv(HORIZON_PATH, index=False, encoding="utf-8-sig")
    score.to_csv(SCORE_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    constraints.to_csv(CONSTRAINT_PATH, index=False, encoding="utf-8-sig")
    promotion.to_csv(PROMOTION_PATH, index=False, encoding="utf-8-sig")
    normal_daily.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    if not triggers.empty:
        triggers.to_csv(TRIGGER_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _plot_equity_drawdown(normal_daily)
    _write_report(summary, horizon, score, cost, constraints, promotion, triggers, decision)

    print(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2), flush=True)
    print(f"[stage395] report={REPORT_PATH}", flush=True)
    print(f"[stage395] chart={CHART_PATH}", flush=True)


if __name__ == "__main__":
    main()
