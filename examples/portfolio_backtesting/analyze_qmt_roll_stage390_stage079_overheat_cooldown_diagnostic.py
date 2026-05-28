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
MODEL_TAG = "stage390_stage079_overheat_cooldown_diagnostic_v1"
OUTPUT_PREFIX = "qmt_roll_stage390_stage079_overheat_cooldown_diagnostic"

STAGE383_DAILY_PATH = OUTPUT_DIR / "qmt_roll_stage383_three_version_deep_audit_daily_stage383_three_version_deep_audit_v1.csv"
C3_DAILY_RAW_PATH = OUTPUT_DIR / "qmt_roll_stage336_c3_cash_reserve_multiperiod_daily_stage336_c3_cash_reserve_multiperiod_v1.csv"

ACCOUNT_CAPITAL = 615_000.0
FUTURES_CAPITAL = 500_000.0
BASELINE_VARIANT = "stage079"
TARGET_DD_PCT = -30.0

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_{MODEL_TAG}.csv"
CONSTRAINT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_constraints_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
SCORE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_score_{MODEL_TAG}.csv"
PROMOTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_promotion_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _load_stage087_module():
    spec = importlib.util.spec_from_file_location("stage087_gate_for_stage090", STAGE087_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {STAGE087_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["stage087_gate_for_stage090"] = module
    spec.loader.exec_module(module)
    return module


s087 = _load_stage087_module()


@dataclass(frozen=True)
class Candidate:
    variant: str
    label: str
    equity: pd.Series
    c3_delta_factor: pd.Series
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
    return curves.reindex(calendar).ffill().dropna(subset=["c3", BASELINE_VARIANT])


def _load_c3_slippage(calendar: pd.DatetimeIndex) -> pd.Series:
    raw = pd.read_csv(C3_DAILY_RAW_PATH, encoding="utf-8-sig")
    raw = raw[raw["profile"].eq("c3_active100_cash0") & raw["window_name"].eq("start_2020")].copy()
    raw["date"] = pd.to_datetime(raw["date"], errors="coerce").dt.normalize()
    raw["active_slippage"] = pd.to_numeric(raw["active_slippage"], errors="coerce").fillna(0.0)
    return raw.dropna(subset=["date"]).groupby("date")["active_slippage"].sum().reindex(calendar).fillna(0.0)


def _build_equity(c3_pnl: pd.Series, delta: pd.Series) -> pd.Series:
    return ACCOUNT_CAPITAL + ((1.0 + delta) * c3_pnl).cumsum()


def _as_stage087_candidate(candidate: Candidate):
    return s087.Candidate(
        variant=candidate.variant,
        label=candidate.label,
        equity=candidate.equity,
        capital_used=ACCOUNT_CAPITAL,
        candidate_class="pnl_level_overheat_cooldown",
        eligible_for_promotion=candidate.eligible_for_promotion,
        note=candidate.note,
    )


def _build_candidates(curves: pd.DataFrame) -> list[Candidate]:
    calendar = curves.index
    c3 = curves["c3"].astype(float)
    c3_pnl = c3.diff().fillna(0.0)
    c3_dd = c3 / c3.cummax() - 1.0
    ret20 = c3.pct_change(20)
    ret60 = c3.pct_change(60)
    prior = lambda cond: cond.shift(1).fillna(False).astype(float)

    near_high = c3_dd >= -0.05
    hot20_50 = prior((ret20 > 0.50) & near_high)
    hot20_75 = prior((ret20 > 0.75) & near_high)
    hot20_50_or_hot60_75 = prior(((ret20 > 0.50) | (ret60 > 0.75)) & near_high)
    recovery = prior((c3_dd <= -0.15) & (ret20 > 0.0))
    zero = pd.Series(0.0, index=calendar)

    specs = [
        (BASELINE_VARIANT, "Stage079基准：50万C3+11.5万现金", zero, True, "唯一基准。"),
        (
            "hot20_75_brake100",
            "诊断：近高位20日涨幅>75%后冷却减10万风险",
            -hot20_75 * (100_000.0 / FUTURES_CAPITAL),
            False,
            "归因线索来自最差短窗口启动前的暴涨状态；PnL层诊断。",
        ),
        (
            "hot20_50_brake100_recovery50",
            "诊断：近高位20日涨幅>50%冷却减10万 + 深回撤恢复加5万",
            -hot20_50 * (100_000.0 / FUTURES_CAPITAL) + recovery * (50_000.0 / FUTURES_CAPITAL),
            False,
            "强诊断形状；需真实引擎验证和额外OOS后才可能晋级。",
        ),
        (
            "hot20_50_or60_75_brake100_recovery50",
            "诊断：近高位20日>50%或60日>75%冷却减10万 + 恢复加5万",
            -hot20_50_or_hot60_75 * (100_000.0 / FUTURES_CAPITAL) + recovery * (50_000.0 / FUTURES_CAPITAL),
            False,
            "最强PnL层诊断；同时测试短中两类过热。",
        ),
    ]
    return [
        Candidate(
            variant=variant,
            label=label,
            equity=_build_equity(c3_pnl, delta.astype(float).reindex(calendar).fillna(0.0)),
            c3_delta_factor=delta.astype(float).reindex(calendar).fillna(0.0),
            eligible_for_promotion=eligible,
            note=note,
        )
        for variant, label, delta, eligible, note in specs
    ]


def _cost_stress(candidates: list[Candidate], c3_pnl: pd.Series, c3_slippage: pd.Series) -> pd.DataFrame:
    baseline_dd: dict[float, float] = {}
    rows: list[dict[str, Any]] = []
    for multiplier in (1.0, 2.0, 3.0, 5.0):
        stressed_pnl = c3_pnl - (multiplier - 1.0) * c3_slippage
        for candidate in candidates:
            equity = ACCOUNT_CAPITAL + ((1.0 + candidate.c3_delta_factor) * stressed_pnl).cumsum()
            nav = equity / ACCOUNT_CAPITAL
            max_dd = s087._max_drawdown(nav)
            if candidate.variant == BASELINE_VARIANT:
                baseline_dd[multiplier] = max_dd
            rows.append(
                {
                    "variant": candidate.variant,
                    "label": candidate.label,
                    "slippage_multiplier": multiplier,
                    "total_return_pct": float((nav.iloc[-1] - 1.0) * 100.0),
                    "max_dd_pct": max_dd,
                }
            )
    result = pd.DataFrame(rows)
    result["baseline_stage079_max_dd_pct"] = result["slippage_multiplier"].map(baseline_dd)
    result["not_worse_than_stage079_stress"] = (result["max_dd_pct"] >= result["baseline_stage079_max_dd_pct"] - 1e-9).astype(int)
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
                "hard_constraint_pass_ignoring_diagnostic": int(all(v for k, v in checks.items() if k != "eligible_not_diagnostic")),
                "failed_constraints": ",".join([name for name, flag in checks.items() if not flag]),
            }
        )
    return pd.DataFrame(rows)


def _promotion(horizon: pd.DataFrame, score: pd.DataFrame, constraints: pd.DataFrame) -> pd.DataFrame:
    baseline_h = horizon[horizon["variant"].eq(BASELINE_VARIANT)].set_index("horizon_days")
    rows: list[dict[str, Any]] = []
    metrics = [
        ("return_p05_pct", "higher"),
        ("return_median_pct", "higher"),
        ("positive_return_rate", "higher"),
        ("annualized_below_5pct_rate", "lower"),
        ("max_dd_worst_pct", "higher"),
        ("dd20_breach_rate", "lower"),
        ("ulcer_p95_pct", "lower"),
        ("longest_underwater_p95_days", "lower"),
    ]
    for _, row in horizon.iterrows():
        base = baseline_h.loc[int(row["horizon_days"])]
        improved = 0
        improved_names: list[str] = []
        for metric, direction in metrics:
            candidate_value = _safe_float(row[metric])
            baseline_value = _safe_float(base[metric])
            flag = candidate_value > baseline_value if direction == "higher" else candidate_value < baseline_value
            improved += int(flag)
            if flag:
                improved_names.append(metric)
        rows.append(
            {
                "variant": row["variant"],
                "label": row["label"],
                "horizon_days": int(row["horizon_days"]),
                "improved_8_count": improved,
                "improved_8_metrics": "|".join(improved_names),
            }
        )
    improved = pd.DataFrame(rows)
    improved_p = improved.pivot(index=["variant", "label"], columns="horizon_days", values="improved_8_count").reset_index()
    improved_p.columns = ["variant", "label", "improved8_90d", "improved8_180d"]
    score_one = score.drop_duplicates(["variant", "label"])[["variant", "label", "score_90d", "score_180d", "short_holding_score"]]
    result = constraints.merge(score_one, on=["variant", "label"], how="left").merge(improved_p, on=["variant", "label"], how="left")
    baseline_scores = result[result["variant"].eq(BASELINE_VARIANT)].iloc[0]
    result["score90_improve_ge10pct"] = (result["score_90d"] >= float(baseline_scores["score_90d"]) * 1.10).astype(int)
    result["score180_improve_ge10pct"] = (result["score_180d"] >= float(baseline_scores["score_180d"]) * 1.10).astype(int)
    result["improved_5of8_each"] = ((result["improved8_90d"] >= 5) & (result["improved8_180d"] >= 5)).astype(int)
    result["diagnostic_gate_pass"] = (
        result["hard_constraint_pass_ignoring_diagnostic"].eq(1)
        & result["score90_improve_ge10pct"].eq(1)
        & result["score180_improve_ge10pct"].eq(1)
        & result["improved_5of8_each"].eq(1)
    ).astype(int)
    result["promotion_pass"] = (
        result["hard_constraint_pass"].eq(1)
        & result["score90_improve_ge10pct"].eq(1)
        & result["score180_improve_ge10pct"].eq(1)
        & result["improved_5of8_each"].eq(1)
    ).astype(int)
    return result.sort_values(["promotion_pass", "diagnostic_gate_pass", "short_holding_score"], ascending=[False, False, False])


def _write_report(summary: pd.DataFrame, horizon: pd.DataFrame, cost: pd.DataFrame, promotion: pd.DataFrame, decision: dict[str, Any]) -> None:
    report = [
        "# Stage090 Stage079暴涨冷却诊断",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：由 Stage089 短窗口失败归因引出的 PnL 层结构诊断；不修改真实引擎。",
        "",
        "## 全周期核心指标",
        "",
        _md_table(summary[["variant", "label", "eligible_for_promotion", "total_return_pct", "max_dd_pct", "sharpe", "ulcer_pct", "rolling252_dd30_breach_rate", "rolling504_dd30_breach_rate"]]),
        "",
        "## 3个月/6个月体验",
        "",
        _md_table(horizon[["variant", "horizon_days", "return_p05_pct", "return_median_pct", "positive_return_rate", "annualized_below_5pct_rate", "max_dd_worst_pct", "dd20_breach_rate", "dd30_breach_rate", "ulcer_p95_pct", "longest_underwater_p95_days"]]),
        "",
        "## 门禁",
        "",
        _md_table(promotion[["variant", "hard_constraint_pass_ignoring_diagnostic", "hard_constraint_pass", "score_90d", "score_180d", "short_holding_score", "improved8_90d", "improved8_180d", "score90_improve_ge10pct", "score180_improve_ge10pct", "improved_5of8_each", "diagnostic_gate_pass", "promotion_pass", "failed_constraints"]]),
        "",
        "## 成本压力",
        "",
        _md_table(cost[["variant", "slippage_multiplier", "total_return_pct", "max_dd_pct", "baseline_stage079_max_dd_pct", "not_worse_than_stage079_stress"]]),
        "",
        "## 决策",
        "",
        f"- 诊断门禁通过数：`{decision['diagnostic_gate_pass_count']}`。",
        f"- 正式晋级数：`{decision['promotion_pass_count']}`。",
        f"- 结论：`{decision['decision']}`。",
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
    promotion = _promotion(horizon, score, constraints)
    decision = {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "diagnostic_gate_pass_count": int(promotion["diagnostic_gate_pass"].sum()),
        "promotion_pass_count": int(promotion["promotion_pass"].sum()),
        "best_diagnostic_variant": promotion[promotion["variant"].ne(BASELINE_VARIANT)].iloc[0]["variant"],
        "decision": "strong_pnl_diagnostic_requires_real_engine_not_promoted",
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "horizon": str(HORIZON_PATH),
            "constraints": str(CONSTRAINT_PATH),
            "cost": str(COST_PATH),
            "score": str(SCORE_PATH),
            "promotion": str(PROMOTION_PATH),
            "report": str(REPORT_PATH),
        },
    }
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon.to_csv(HORIZON_PATH, index=False, encoding="utf-8-sig")
    constraints.to_csv(CONSTRAINT_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    score.to_csv(SCORE_PATH, index=False, encoding="utf-8-sig")
    promotion.to_csv(PROMOTION_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(summary, horizon, cost, promotion, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
