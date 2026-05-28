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
from qmt_roll_official_stage78_config import OFFICIAL_STAGE78_ROLE, OFFICIAL_STAGE78_VERSION
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy
from qmt_universe import END_DT, PRELOAD_START_DT, START_DT
from run_qmt_alignment_backtest import OUTPUT_DIR
from run_qmt_roll_backtest import (
    build_backtest_engine,
    build_roll_setting,
    build_summary_row,
    compute_round_trip_win_ratio,
)
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


PROJECT_DIR = Path(__file__).resolve().parent
STAGE087_SCRIPT = PROJECT_DIR / "analyze_qmt_roll_stage387_stage079_short_holding_candidates.py"
MODEL_TAG = "stage391_stage079_overheat_cooldown_true_engine_validation_v1"
OUTPUT_PREFIX = "qmt_roll_stage391_stage079_overheat_cooldown_true_engine_validation"
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
SCALE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_scale_history_{MODEL_TAG}.csv"
DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_equity_drawdown_{MODEL_TAG}.png"


def _load_stage087_module():
    spec = importlib.util.spec_from_file_location("stage087_gate_for_stage391", STAGE087_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {STAGE087_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["stage087_gate_for_stage391"] = module
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


def _overheat_overrides(*, hot60_threshold: float) -> dict[str, Any]:
    return {
        "enable_portfolio_overheat_cooldown": True,
        "portfolio_overheat_cooldown_near_high_drawdown_pct": 0.05,
        "portfolio_overheat_cooldown_hot20_threshold": 0.50,
        "portfolio_overheat_cooldown_hot60_threshold": hot60_threshold,
        "portfolio_overheat_cooldown_brake_scale": 0.80,
        "portfolio_overheat_cooldown_recovery_drawdown_pct": 0.15,
        "portfolio_overheat_cooldown_recovery_ret20_threshold": 0.0,
        "portfolio_overheat_cooldown_recovery_scale": 1.10,
        "portfolio_overheat_cooldown_entry_contexts": "flat_entry,reverse_entry,rollover_reopen,regular_add,donchian_add",
        "enable_portfolio_overheat_cooldown_deleverage": True,
    }


PROFILES: tuple[Profile, ...] = (
    Profile(
        BASELINE_VARIANT,
        "Stage079真实引擎基准：50万C3下单+11.5万现金",
        {},
        "C3真实引擎日权益外加11.5万现金，作为唯一硬约束基准。",
    ),
    Profile(
        "hot20_50_or60_75_brake100_recovery50_true_engine",
        "真实引擎：近高位20日>50%或60日>75%冷却，深回撤20日转正恢复",
        _overheat_overrides(hot60_threshold=0.75),
        "Stage090最强PnL层诊断的真实引擎落地；固定规则，不扫阈值。",
    ),
    Profile(
        "hot20_50_brake100_recovery50_true_engine",
        "真实引擎：近高位20日>50%冷却，深回撤20日转正恢复",
        _overheat_overrides(hot60_threshold=-1.0),
        "Stage090简化形状的真实引擎落地；用于检查线索是否依赖60日条件。",
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


def _run_engine(profile: Profile, slippage_multiplier: float = 1.0) -> tuple[pd.DataFrame, dict[str, Any], pd.DataFrame]:
    preload_start = max(PRELOAD_START_DT, START_DT - timedelta(days=365))
    print(f"[stage391] run {profile.variant} slippage={slippage_multiplier:g}", flush=True)
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
    scale_rows = getattr(strategy, "portfolio_overheat_cooldown_scale_history", []) if strategy else []
    scale = pd.DataFrame(scale_rows)
    if not scale.empty:
        scale["date"] = pd.to_datetime(scale["date"], errors="coerce").dt.normalize()
        scale["variant"] = profile.variant
        scale["slippage_multiplier"] = slippage_multiplier
        scale["deleverage_count"] = int(getattr(strategy, "portfolio_overheat_cooldown_deleverage_count", 0))

    return analysis_df, statistics, scale


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
        candidate_class="true_engine_overheat_cooldown",
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


def _plot_equity_drawdown(daily: pd.DataFrame) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:  # pragma: no cover - optional visual artifact
        print(f"[stage391] skip chart: {exc}", flush=True)
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
    axes[0].set_title("Stage091 true-engine account NAV")
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
    scale: pd.DataFrame,
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
    if not scale.empty:
        scale_summary = (
            scale[scale["slippage_multiplier"].eq(1.0)]
            .groupby("variant", as_index=False)
            .agg(
                scaled_days=("scale", lambda x: int((pd.to_numeric(x, errors="coerce") != 1.0).sum())),
                brake_days=("scale", lambda x: int((pd.to_numeric(x, errors="coerce") < 0.999).sum())),
                recovery_days=("scale", lambda x: int((pd.to_numeric(x, errors="coerce") > 1.001).sum())),
                min_scale=("scale", "min"),
                max_scale=("scale", "max"),
                deleverage_count=("deleverage_count", "max"),
            )
        )
    else:
        scale_summary = pd.DataFrame()

    report = [
        "# Stage091 Stage079过热冷却真实引擎验证",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：固定规则真实引擎验证；不扫阈值，不改变Stage079默认口径。",
        f"- 图表：`{CHART_PATH}`",
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
        "## 真实引擎触发摘要",
        "",
        _md_table(scale_summary),
        "",
        "## 反过拟合说明",
        "",
        "- 本阶段只验证 Stage090 已固定的两个候选，不新增相邻阈值或金额扫描。",
        "- 触发条件只使用引擎已记录的历史账户权益，非当日未来收益。",
        "- 若真实引擎无法复制PnL层改善，则降级为诊断线索，不晋级。",
    ]
    REPORT_PATH.write_text("\n".join(report), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    normal_daily_parts: list[pd.DataFrame] = []
    cost_daily_parts: list[pd.DataFrame] = []
    scale_parts: list[pd.DataFrame] = []
    normal_stats: dict[str, dict[str, Any]] = {}

    for multiplier in (1.0, 2.0, 3.0, 5.0):
        for profile in PROFILES:
            analysis_df, statistics, scale = _run_engine(profile, multiplier)
            daily = _daily_equity(profile, analysis_df, multiplier)
            cost_daily_parts.append(daily)
            if multiplier == 1.0:
                normal_daily_parts.append(daily)
                normal_stats[profile.variant] = statistics
                if not scale.empty:
                    scale_parts.append(scale)

    normal_daily = pd.concat(normal_daily_parts, ignore_index=True)
    cost_daily = pd.concat(cost_daily_parts, ignore_index=True)
    scale = pd.concat(scale_parts, ignore_index=True) if scale_parts else pd.DataFrame()

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
    horizon = pd.DataFrame([s087._horizon_metrics(candidate, horizon) for candidate in candidates for horizon in (90, 180)])
    score = s087._score_horizons(horizon)
    cost = _cost_stress(cost_daily)
    constraints = s087._constraints(summary, cost)
    promotion = s087._promotion(score, horizon, constraints)

    promoted = promotion[promotion["promotion_pass"].eq(1)]
    diagnostic = promotion[
        promotion["score90_improve_ge10pct"].eq(1)
        & promotion["score180_improve_ge10pct"].eq(1)
        & promotion["improved_5of8_each"].eq(1)
    ]
    decision = {
        "stage": "Stage091",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": "promote" if not promoted.empty else "no_promotion",
        "promoted_variants": promoted["variant"].tolist(),
        "experience_gate_variants": diagnostic["variant"].tolist(),
        "best_by_short_holding_score": promotion.iloc[0]["variant"] if not promotion.empty else "",
        "normal_cost_chart": str(CHART_PATH),
        "note": "真实引擎验证；若无promotion，则Stage090仅保留为PnL层诊断。",
    }

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon.to_csv(HORIZON_PATH, index=False, encoding="utf-8-sig")
    score.to_csv(SCORE_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    constraints.to_csv(CONSTRAINT_PATH, index=False, encoding="utf-8-sig")
    promotion.to_csv(PROMOTION_PATH, index=False, encoding="utf-8-sig")
    normal_daily.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    if not scale.empty:
        scale.to_csv(SCALE_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _plot_equity_drawdown(normal_daily)
    _write_report(summary, horizon, score, cost, constraints, promotion, scale, decision)

    print(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2), flush=True)
    print(f"[stage391] report={REPORT_PATH}", flush=True)
    print(f"[stage391] chart={CHART_PATH}", flush=True)


if __name__ == "__main__":
    main()
