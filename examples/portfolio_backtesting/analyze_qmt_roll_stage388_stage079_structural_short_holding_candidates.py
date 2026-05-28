from __future__ import annotations

import importlib.util
import json
import math
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
STAGE087_SCRIPT = PROJECT_DIR / "analyze_qmt_roll_stage387_stage079_short_holding_candidates.py"
MODEL_TAG = "stage388_stage079_structural_short_holding_candidates_v1"
OUTPUT_PREFIX = "qmt_roll_stage388_stage079_structural_short_holding_candidates"

STAGE383_DAILY_PATH = OUTPUT_DIR / "qmt_roll_stage383_three_version_deep_audit_daily_stage383_three_version_deep_audit_v1.csv"
C3_DAILY_RAW_PATH = OUTPUT_DIR / "qmt_roll_stage336_c3_cash_reserve_multiperiod_daily_stage336_c3_cash_reserve_multiperiod_v1.csv"
RANGE_100K_DAILY_PATH = OUTPUT_DIR / "qmt_roll_stage324_true_combo_capital_margin_satellite_100k_full_2020_2026_daily.csv"

ACCOUNT_CAPITAL = 615_000.0
FUTURES_CAPITAL = 500_000.0
STAGE079_CASH = 115_000.0
TARGET_DD_PCT = -30.0
BASELINE_VARIANT = "stage079"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_{MODEL_TAG}.csv"
CONSTRAINT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_constraints_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
SCORE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_score_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _load_stage087_module():
    spec = importlib.util.spec_from_file_location("stage087_gate", STAGE087_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {STAGE087_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["stage087_gate"] = module
    spec.loader.exec_module(module)
    return module


s087 = _load_stage087_module()


@dataclass(frozen=True)
class StructuralCandidate:
    variant: str
    label: str
    equity: pd.Series
    c3_delta_factor: pd.Series
    satellite_pnl: pd.Series
    capital_used: float
    candidate_class: str
    eligible_for_promotion: bool
    note: str


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


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


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


def _load_curves() -> pd.DataFrame:
    frame = pd.read_csv(STAGE383_DAILY_PATH, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["equity"] = pd.to_numeric(frame["equity"], errors="coerce")
    curves = frame.dropna(subset=["date", "variant", "equity"]).pivot(index="date", columns="variant", values="equity").sort_index()
    calendar = pd.date_range(curves.index.min(), curves.index.max(), freq="D")
    return curves.reindex(calendar).ffill().dropna(subset=["c3", "stage079"])


def _load_c3_slippage(calendar: pd.DatetimeIndex) -> pd.Series:
    raw = pd.read_csv(C3_DAILY_RAW_PATH, encoding="utf-8-sig")
    raw = raw[raw["profile"].eq("c3_active100_cash0") & raw["window_name"].eq("start_2020")].copy()
    raw["date"] = pd.to_datetime(raw["date"], errors="coerce").dt.normalize()
    raw["active_slippage"] = pd.to_numeric(raw["active_slippage"], errors="coerce").fillna(0.0)
    return raw.dropna(subset=["date"]).groupby("date")["active_slippage"].sum().reindex(calendar).fillna(0.0)


def _load_range_100k_pnl(calendar: pd.DatetimeIndex) -> pd.Series:
    frame = pd.read_csv(RANGE_100K_DAILY_PATH, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["balance"] = pd.to_numeric(frame["balance"], errors="coerce")
    balance = frame.dropna(subset=["date", "balance"]).sort_values("date").set_index("date")["balance"]
    balance = balance.reindex(calendar).ffill().fillna(100_000.0)
    return (balance - 100_000.0).rename("range100_pnl")


def _build_equity(c3_pnl: pd.Series, c3_delta_factor: pd.Series, satellite_pnl: pd.Series) -> pd.Series:
    return (ACCOUNT_CAPITAL + ((1.0 + c3_delta_factor) * c3_pnl).cumsum() + satellite_pnl).rename("equity")


def _as_stage087_candidate(candidate: StructuralCandidate):
    return s087.Candidate(
        variant=candidate.variant,
        label=candidate.label,
        equity=candidate.equity,
        capital_used=candidate.capital_used,
        candidate_class=candidate.candidate_class,
        eligible_for_promotion=candidate.eligible_for_promotion,
        note=candidate.note,
    )


def _build_candidates(curves: pd.DataFrame) -> list[StructuralCandidate]:
    calendar = curves.index
    c3 = curves["c3"].astype(float)
    c3_pnl = c3.diff().fillna(0.0)
    c3_drawdown = c3 / c3.cummax() - 1.0
    c3_ret20 = c3.pct_change(20)
    zeros = pd.Series(0.0, index=calendar)
    range100_pnl = _load_range_100k_pnl(calendar)

    recovery_confirmed = ((c3_drawdown <= -0.15) & (c3_ret20 > 0.0)).shift(1).fillna(False).astype(float)
    falling_drawdown = ((c3_drawdown <= -0.10) & (c3_ret20 < 0.0)).shift(1).fillna(False).astype(float)

    specs: list[dict[str, Any]] = [
        {
            "variant": BASELINE_VARIANT,
            "label": "Stage079基准：50万C3+11.5万现金",
            "delta": zeros,
            "satellite_pnl": zeros,
            "candidate_class": "baseline",
            "eligible": True,
            "note": "唯一基准。",
        },
        {
            "variant": "range100_cash15",
            "label": "50万C3+10万真实震荡卫星+1.5万现金",
            "delta": zeros,
            "satellite_pnl": range100_pnl,
            "candidate_class": "real_range_satellite",
            "eligible": True,
            "note": "只读复用Stage324独立10万震荡卫星日权益，不修改震荡策略或趋势策略。",
        },
        {
            "variant": "recovery_rerisk_25k",
            "label": "诊断：C3深回撤恢复确认后动用2.5万备用风险预算",
            "delta": recovery_confirmed * (25_000.0 / FUTURES_CAPITAL),
            "satellite_pnl": zeros,
            "candidate_class": "pnl_level_recovery_rerisk",
            "eligible": False,
            "note": "诊断项，需真实引擎验证后才可能晋级。",
        },
        {
            "variant": "recovery_rerisk_50k",
            "label": "诊断：C3深回撤恢复确认后动用5万备用风险预算",
            "delta": recovery_confirmed * (50_000.0 / FUTURES_CAPITAL),
            "satellite_pnl": zeros,
            "candidate_class": "pnl_level_recovery_rerisk",
            "eligible": False,
            "note": "诊断项，低自由度恢复再风险结构。",
        },
        {
            "variant": "storm_brake25_recovery50",
            "label": "诊断：下跌段减2.5万风险+恢复确认加5万风险",
            "delta": recovery_confirmed * (50_000.0 / FUTURES_CAPITAL) - falling_drawdown * (25_000.0 / FUTURES_CAPITAL),
            "satellite_pnl": zeros,
            "candidate_class": "pnl_level_storm_brake_recovery",
            "eligible": False,
            "note": "诊断项，测试下跌刹车是否能改善3个月左尾。",
        },
        {
            "variant": "storm_brake50_recovery50",
            "label": "诊断：下跌段减5万风险+恢复确认加5万风险",
            "delta": recovery_confirmed * (50_000.0 / FUTURES_CAPITAL) - falling_drawdown * (50_000.0 / FUTURES_CAPITAL),
            "satellite_pnl": zeros,
            "candidate_class": "pnl_level_storm_brake_recovery",
            "eligible": False,
            "note": "诊断项，若全周期收益或Sharpe劣化则反证该刹车形状。",
        },
        {
            "variant": "range100_cash0_recovery15",
            "label": "诊断：10万震荡卫星+1.5万恢复再风险",
            "delta": recovery_confirmed * (15_000.0 / FUTURES_CAPITAL),
            "satellite_pnl": range100_pnl,
            "candidate_class": "hybrid_range_recovery",
            "eligible": False,
            "note": "诊断项，同时占用11.5万现金缓冲，不增加账户资金。",
        },
    ]

    candidates: list[StructuralCandidate] = []
    for spec in specs:
        delta = spec["delta"].astype(float).reindex(calendar).fillna(0.0)
        sat = spec["satellite_pnl"].astype(float).reindex(calendar).fillna(0.0)
        candidates.append(
            StructuralCandidate(
                variant=spec["variant"],
                label=spec["label"],
                equity=_build_equity(c3_pnl, delta, sat),
                c3_delta_factor=delta,
                satellite_pnl=sat,
                capital_used=ACCOUNT_CAPITAL,
                candidate_class=spec["candidate_class"],
                eligible_for_promotion=bool(spec["eligible"]),
                note=spec["note"],
            )
        )
    return candidates


def _cost_stress(candidates: list[StructuralCandidate], c3_pnl: pd.Series, c3_slippage: pd.Series) -> pd.DataFrame:
    baseline_rows: dict[float, float] = {}
    rows: list[dict[str, Any]] = []
    for multiplier in (1.0, 2.0, 3.0, 5.0):
        stressed_pnl = c3_pnl - (multiplier - 1.0) * c3_slippage
        for candidate in candidates:
            equity = ACCOUNT_CAPITAL + ((1.0 + candidate.c3_delta_factor) * stressed_pnl).cumsum() + candidate.satellite_pnl
            nav = equity / ACCOUNT_CAPITAL
            max_dd = s087._max_drawdown(nav)
            total_return = float((nav.iloc[-1] - 1.0) * 100.0)
            if candidate.variant == BASELINE_VARIANT:
                baseline_rows[multiplier] = max_dd
            rows.append(
                {
                    "variant": candidate.variant,
                    "label": candidate.label,
                    "slippage_multiplier": multiplier,
                    "total_return_pct": total_return,
                    "max_dd_pct": max_dd,
                }
            )
    result = pd.DataFrame(rows)
    result["baseline_stage079_max_dd_pct"] = result["slippage_multiplier"].map(baseline_rows)
    result["not_worse_than_stage079_stress"] = (
        result["max_dd_pct"] >= result["baseline_stage079_max_dd_pct"] - 1e-9
    ).astype(int)
    return result


def _constraints(summary: pd.DataFrame, cost: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, row in summary.iterrows():
        variant = row["variant"]
        c = cost[cost["variant"].eq(variant)]
        checks = {
            "total_return_not_lower": _safe_float(row["total_return_pct"]) >= 4947.2602 - 1e-4,
            "max_dd_not_worse": _safe_float(row["max_dd_pct"]) >= -29.7007 - 1e-4,
            "max_dd_below_30": _safe_float(row["max_dd_pct"]) >= TARGET_DD_PCT,
            "sharpe_not_lower": _safe_float(row["sharpe"]) >= 1.3182 - 1e-4,
            "ulcer_not_higher": _safe_float(row["ulcer_pct"]) <= 15.0931 + 1e-4,
            "rolling252_dd30_zero": _safe_float(row["rolling252_dd30_breach_rate"]) == 0.0,
            "rolling504_dd30_zero": _safe_float(row["rolling504_dd30_breach_rate"]) == 0.0,
            "annual_dd30_pass_100": _safe_float(row["annual_cold_start_dd30_pass_rate"]) == 1.0,
            "quarter_dd30_pass_100": _safe_float(row["quarter_cold_start_dd30_pass_rate"]) == 1.0,
            "capital_not_increased": _safe_float(row["capital_used"]) <= ACCOUNT_CAPITAL,
            "cost_stress_not_worse": bool(c["not_worse_than_stage079_stress"].eq(1).all()) if not c.empty else False,
            "eligible_not_diagnostic": bool(int(row["eligible_for_promotion"]) == 1),
        }
        rows.append(
            {
                "variant": variant,
                "label": row["label"],
                **{name: int(flag) for name, flag in checks.items()},
                "hard_constraint_pass": int(all(checks.values())),
                "failed_constraints": ",".join([name for name, flag in checks.items() if not flag]),
            }
        )
    return pd.DataFrame(rows)


def _promotion(score: pd.DataFrame, constraints: pd.DataFrame) -> pd.DataFrame:
    score_one = score.drop_duplicates(["variant", "label"])[["variant", "label", "score_90d", "score_180d", "short_holding_score"]]
    improved = score.groupby(["variant", "label", "horizon_days"])["improved_metric_count"].first().reset_index()
    improved_p = improved.pivot(index=["variant", "label"], columns="horizon_days", values="improved_metric_count").reset_index()
    improved_p.columns = ["variant", "label", "improved_count_90d", "improved_count_180d"]
    result = constraints.merge(score_one, on=["variant", "label"], how="left").merge(improved_p, on=["variant", "label"], how="left")
    baseline_scores = result[result["variant"].eq(BASELINE_VARIANT)].iloc[0]
    result["score90_improve_ge10pct"] = (result["score_90d"] >= float(baseline_scores["score_90d"]) * 1.10).astype(int)
    result["score180_improve_ge10pct"] = (result["score_180d"] >= float(baseline_scores["score_180d"]) * 1.10).astype(int)
    result["improved_5of8_each"] = ((result["improved_count_90d"] >= 5) & (result["improved_count_180d"] >= 5)).astype(int)
    result["promotion_pass"] = (
        result["hard_constraint_pass"].eq(1)
        & result["score90_improve_ge10pct"].eq(1)
        & result["score180_improve_ge10pct"].eq(1)
        & result["improved_5of8_each"].eq(1)
    ).astype(int)
    return result.sort_values(["promotion_pass", "short_holding_score"], ascending=[False, False])


def _write_report(
    summary: pd.DataFrame,
    horizon: pd.DataFrame,
    cost: pd.DataFrame,
    promotion: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    report = [
        "# Stage088 Stage079结构性短持有体验候选门禁",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：低自由度结构候选诊断与真实现金占用候选复核；不修改C3和震荡策略代码。",
        "- 基准：Stage079 = `50万C3下单 + 11.5万外部现金`。",
        "",
        "## 外部调研判断",
        "",
        "- 趋势策略短期体验改善通常依赖低相关收益源、波动/风险预算管理、以及严谨的滚动窗口评估。",
        "- 本阶段只测试有明确经济语义的粗结构：真实震荡卫星、深回撤恢复再风险、下跌刹车+恢复再风险；不扫相邻小数。",
        "",
        "## 全周期核心指标",
        "",
        _md_table(
            summary[
                [
                    "variant",
                    "label",
                    "candidate_class",
                    "eligible_for_promotion",
                    "total_return_pct",
                    "max_dd_pct",
                    "sharpe",
                    "ulcer_pct",
                    "rolling252_dd30_breach_rate",
                    "rolling504_dd30_breach_rate",
                ]
            ]
        ),
        "",
        "## 3个月/6个月体验",
        "",
        _md_table(
            horizon[
                [
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
            ].sort_values(["variant", "horizon_days"])
        ),
        "",
        "## 硬约束与晋级门禁",
        "",
        _md_table(
            promotion[
                [
                    "variant",
                    "hard_constraint_pass",
                    "score_90d",
                    "score_180d",
                    "short_holding_score",
                    "improved_count_90d",
                    "improved_count_180d",
                    "score90_improve_ge10pct",
                    "score180_improve_ge10pct",
                    "improved_5of8_each",
                    "promotion_pass",
                    "failed_constraints",
                ]
            ]
        ),
        "",
        "## 成本压力",
        "",
        _md_table(
            cost[
                [
                    "variant",
                    "slippage_multiplier",
                    "total_return_pct",
                    "max_dd_pct",
                    "baseline_stage079_max_dd_pct",
                    "not_worse_than_stage079_stress",
                ]
            ].sort_values(["variant", "slippage_multiplier"])
        ),
        "",
        "## 决策",
        "",
        f"- 晋级候选数：`{decision['promotion_pass_count']}`。",
        f"- 最佳非基准候选：`{decision['best_non_baseline_variant']}`。",
        f"- 结论：`{decision['decision']}`。",
        "",
        "## 过拟合与继续价值反思",
        "",
        "- 运行后判断：本阶段不是过拟合。原因是候选来自粗结构和既有独立曲线，失败/通过都用预声明门禁判断，没有按3个月或6个月结果继续调小数。",
        "- 继续价值判断：仍有价值，但当前这批结构没有正式晋级；下一步应优先寻找更强低相关承载或真实外生状态变量，而不是继续救这些刹车/再风险金额。",
        "",
    ]
    REPORT_PATH.write_text("\n".join(report), encoding="utf-8")


def main() -> None:
    curves = _load_curves()
    calendar = curves.index
    c3_pnl = curves["c3"].astype(float).diff().fillna(0.0)
    c3_slippage = _load_c3_slippage(calendar)
    candidates = _build_candidates(curves)
    stage087_candidates = [_as_stage087_candidate(c) for c in candidates]

    summary = pd.DataFrame([s087._stats(c) for c in stage087_candidates])
    horizon = pd.DataFrame([s087._horizon_metrics(c, h) for c in stage087_candidates for h in (90, 180)])
    score = s087._score_horizons(horizon)
    cost = _cost_stress(candidates, c3_pnl, c3_slippage)
    constraints = _constraints(summary, cost)
    promotion = _promotion(score, constraints)

    non_baseline = promotion[~promotion["variant"].eq(BASELINE_VARIANT)]
    best_non_baseline = non_baseline.iloc[0]["variant"] if not non_baseline.empty else None
    decision = {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "baseline": BASELINE_VARIANT,
        "promotion_pass_count": int(promotion["promotion_pass"].sum()),
        "best_non_baseline_variant": best_non_baseline,
        "decision": "no_candidate_promoted_stage079_remains_baseline"
        if int(promotion["promotion_pass"].sum()) == 0
        else "candidate_requires_real_engine_and_ab_review",
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "horizon": str(HORIZON_PATH),
            "constraints": str(CONSTRAINT_PATH),
            "cost": str(COST_PATH),
            "score": str(SCORE_PATH),
            "report": str(REPORT_PATH),
        },
    }

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon.to_csv(HORIZON_PATH, index=False, encoding="utf-8-sig")
    constraints.to_csv(CONSTRAINT_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    score.to_csv(SCORE_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(summary, horizon, cost, promotion, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
