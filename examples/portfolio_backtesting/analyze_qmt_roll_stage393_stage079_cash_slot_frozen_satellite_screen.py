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
MODEL_TAG = "stage393_stage079_cash_slot_frozen_satellite_screen_v1"
OUTPUT_PREFIX = "qmt_roll_stage393_stage079_cash_slot_frozen_satellite_screen"

STAGE383_DAILY_PATH = OUTPUT_DIR / "qmt_roll_stage383_three_version_deep_audit_daily_stage383_three_version_deep_audit_v1.csv"
C3_DAILY_RAW_PATH = OUTPUT_DIR / "qmt_roll_stage336_c3_cash_reserve_multiperiod_daily_stage336_c3_cash_reserve_multiperiod_v1.csv"
FU_SN_DAILY_PATH = OUTPUT_DIR / "qmt_roll_stage105_fu_sn_satellite_successor_candidate_daily_equity.csv"
XSMOM_DAILY_PATH = OUTPUT_DIR / "qmt_roll_stage345_cross_sectional_momentum_satellite_satellite_daily_stage345_cross_sectional_momentum_satellite_v1.csv"
RANGE_100K_DAILY_PATH = OUTPUT_DIR / "qmt_roll_stage324_true_combo_capital_margin_satellite_100k_full_2020_2026_daily_equity.csv"

ACCOUNT_CAPITAL = 615_000.0
FUTURES_CAPITAL = 500_000.0
STAGE079_CASH = 115_000.0
BASELINE_VARIANT = "stage079"
TARGET_DD_PCT = -30.0

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_{MODEL_TAG}.csv"
SCORE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_score_{MODEL_TAG}.csv"
GATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"


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
class CashSlotCandidate:
    variant: str
    label: str
    equity: pd.Series
    satellite_pnl: pd.Series
    satellite_slippage: pd.Series
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


def _stage087_candidate(candidate: CashSlotCandidate):
    return s087.Candidate(
        variant=candidate.variant,
        label=candidate.label,
        equity=candidate.equity,
        capital_used=candidate.capital_used,
        candidate_class=candidate.candidate_class,
        eligible_for_promotion=candidate.eligible_for_promotion,
        note=candidate.note,
    )


def _equity_pnl_from_daily_equity(
    path: Path,
    calendar: pd.DatetimeIndex,
    source_capital: float,
    target_capital: float,
    start_cash_before_available: bool = True,
) -> tuple[pd.Series, pd.Series]:
    frame = pd.read_csv(path, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["balance"] = pd.to_numeric(frame["balance"], errors="coerce")
    frame["slippage"] = pd.to_numeric(frame.get("slippage", 0.0), errors="coerce").fillna(0.0)
    frame = frame.dropna(subset=["date", "balance"]).sort_values("date")
    scale = target_capital / source_capital
    pnl = (frame.set_index("date")["balance"] - source_capital) * scale
    slippage = frame.set_index("date")["slippage"] * scale
    pnl = pnl.reindex(calendar).ffill()
    slippage = slippage.reindex(calendar).fillna(0.0)
    if start_cash_before_available:
        pnl = pnl.fillna(0.0)
    return pnl.astype(float), slippage.astype(float)


def _xsmom_pnl(calendar: pd.DatetimeIndex, target_capital: float) -> tuple[pd.Series, pd.Series]:
    frame = pd.read_csv(XSMOM_DAILY_PATH, encoding="utf-8-sig")
    frame = frame[frame["spec"].eq("mom_12m_skip1m")].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    for col in ("satellite_return_cost0bps", "satellite_return_cost20bps"):
        frame[col] = pd.to_numeric(frame[col], errors="coerce").fillna(0.0)
    frame = frame.dropna(subset=["date"]).sort_values("date").set_index("date")
    returns_20 = frame["satellite_return_cost20bps"].reindex(calendar).fillna(0.0)
    returns_0 = frame["satellite_return_cost0bps"].reindex(calendar).fillna(0.0)
    nav = (1.0 + returns_20).cumprod()
    pnl = (nav - 1.0) * target_capital
    daily_cost = (returns_0 - returns_20).clip(lower=0.0) * target_capital
    return pnl.astype(float), daily_cost.astype(float)


def _build_candidates(curves: pd.DataFrame) -> list[CashSlotCandidate]:
    calendar = curves.index
    c3 = curves["c3"].astype(float)
    stage079 = curves["stage079"].astype(float)
    zeros = pd.Series(0.0, index=calendar)

    fu_pnl, fu_slip = _equity_pnl_from_daily_equity(FU_SN_DAILY_PATH, calendar, 200_000.0, STAGE079_CASH)
    xsmom_pnl, xsmom_slip = _xsmom_pnl(calendar, STAGE079_CASH)
    range_pnl, range_slip = _equity_pnl_from_daily_equity(RANGE_100K_DAILY_PATH, calendar, 100_000.0, STAGE079_CASH)

    return [
        CashSlotCandidate(
            BASELINE_VARIANT,
            "Stage079基准：50万C3+11.5万现金",
            stage079,
            zeros,
            zeros,
            ACCOUNT_CAPITAL,
            "baseline",
            True,
            "唯一基准。",
        ),
        CashSlotCandidate(
            "cashslot_fu_sn_satellite_scaled",
            "诊断：11.5万现金槽位缩放既有fu/sn趋势卫星",
            c3 + STAGE079_CASH + fu_pnl,
            fu_pnl,
            fu_slip,
            ACCOUNT_CAPITAL,
            "scaled_frozen_trend_satellite",
            False,
            "诊断项；源曲线为20万账户，11.5万缩放不等于真实整数手数可执行版本。",
        ),
        CashSlotCandidate(
            "cashslot_xsmom_12m_cost20",
            "诊断：11.5万现金槽位承载12-1月横截面动量卫星cost20bps",
            c3 + STAGE079_CASH + xsmom_pnl,
            xsmom_pnl,
            xsmom_slip,
            ACCOUNT_CAPITAL,
            "net_value_xsmom_satellite",
            False,
            "诊断项；Stage045净值层卫星，尚未真实引擎/整数手数复核。",
        ),
        CashSlotCandidate(
            "cashslot_range100_scaled",
            "诊断：11.5万现金槽位缩放既有震荡卫星",
            c3 + STAGE079_CASH + range_pnl,
            range_pnl,
            range_slip,
            ACCOUNT_CAPITAL,
            "scaled_frozen_range_satellite",
            False,
            "诊断项；真实10万震荡卫星已在Stage088几乎无改善，本处只看全现金槽位缩放边界。",
        ),
        CashSlotCandidate(
            "cashslot_equal_fu_xsmom",
            "诊断：11.5万现金槽位等分fu/sn趋势卫星与12-1月横截面动量",
            c3 + STAGE079_CASH + 0.5 * fu_pnl + 0.5 * xsmom_pnl,
            0.5 * fu_pnl + 0.5 * xsmom_pnl,
            0.5 * fu_slip + 0.5 * xsmom_slip,
            ACCOUNT_CAPITAL,
            "equal_scaled_satellite_basket",
            False,
            "诊断项；等权二卫星组合用于检验分散边界，不作为实盘可执行候选。",
        ),
    ]


def _load_c3_raw(calendar: pd.DatetimeIndex) -> tuple[pd.Series, pd.Series]:
    raw = pd.read_csv(C3_DAILY_RAW_PATH, encoding="utf-8-sig")
    raw = raw[raw["profile"].eq("c3_active100_cash0") & raw["window_name"].eq("start_2020")].copy()
    raw["date"] = pd.to_datetime(raw["date"], errors="coerce").dt.normalize()
    raw["active_net_pnl"] = pd.to_numeric(raw["active_net_pnl"], errors="coerce").fillna(0.0)
    raw["active_slippage"] = pd.to_numeric(raw["active_slippage"], errors="coerce").fillna(0.0)
    raw = raw.dropna(subset=["date"]).sort_values("date").set_index("date")
    return raw["active_net_pnl"].reindex(calendar).fillna(0.0), raw["active_slippage"].reindex(calendar).fillna(0.0)


def _cost_stress(candidates: list[CashSlotCandidate], c3_pnl: pd.Series, c3_slippage: pd.Series) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    baseline_dd: dict[float, float] = {}
    calendar = candidates[0].equity.index
    for multiplier in (1.0, 2.0, 3.0, 5.0):
        c3_stressed = FUTURES_CAPITAL + (c3_pnl - (multiplier - 1.0) * c3_slippage).cumsum()
        for candidate in candidates:
            satellite_stressed = candidate.satellite_pnl - ((multiplier - 1.0) * candidate.satellite_slippage).cumsum()
            equity = c3_stressed + STAGE079_CASH + satellite_stressed
            equity = equity.reindex(calendar).ffill()
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
                    "baseline_stage079_max_dd_pct": baseline_dd.get(multiplier, np.nan),
                }
            )
    result = pd.DataFrame(rows)
    result["baseline_stage079_max_dd_pct"] = result["slippage_multiplier"].map(baseline_dd)
    result["not_worse_than_stage079_stress"] = (
        result["max_dd_pct"] >= result["baseline_stage079_max_dd_pct"] - 1e-9
    ).astype(int)
    return result


def _gate(summary: pd.DataFrame, score: pd.DataFrame, cost: pd.DataFrame) -> pd.DataFrame:
    baseline = summary[summary["variant"].eq(BASELINE_VARIANT)].iloc[0]
    score_one = score.drop_duplicates(["variant", "label"])[
        ["variant", "label", "score_90d", "score_180d", "short_holding_score"]
    ]
    improved = score.groupby(["variant", "label", "horizon_days"])["improved_metric_count"].first().reset_index()
    improved_p = improved.pivot(index=["variant", "label"], columns="horizon_days", values="improved_metric_count").reset_index()
    improved_p.columns = ["variant", "label", "improved_count_90d", "improved_count_180d"]
    rows: list[dict[str, Any]] = []
    for _, row in summary.iterrows():
        c = cost[cost["variant"].eq(row["variant"])]
        checks = {
            "eligible_not_diagnostic": bool(int(row["eligible_for_promotion"]) == 1),
            "total_return_not_lower": _safe_float(row["total_return_pct"]) >= _safe_float(baseline["total_return_pct"]) - 1e-4,
            "max_dd_not_worse": _safe_float(row["max_dd_pct"]) >= _safe_float(baseline["max_dd_pct"]) - 1e-4,
            "max_dd_below_30": _safe_float(row["max_dd_pct"]) >= TARGET_DD_PCT,
            "sharpe_not_lower": _safe_float(row["sharpe"]) >= _safe_float(baseline["sharpe"]) - 1e-4,
            "ulcer_not_higher": _safe_float(row["ulcer_pct"]) <= _safe_float(baseline["ulcer_pct"]) + 1e-4,
            "rolling252_dd30_zero": _safe_float(row["rolling252_dd30_breach_rate"]) == 0.0,
            "rolling504_dd30_zero": _safe_float(row["rolling504_dd30_breach_rate"]) == 0.0,
            "annual_dd30_pass_100": _safe_float(row["annual_cold_start_dd30_pass_rate"]) == 1.0,
            "quarter_dd30_pass_100": _safe_float(row["quarter_cold_start_dd30_pass_rate"]) == 1.0,
            "capital_not_increased": _safe_float(row["capital_used"]) <= ACCOUNT_CAPITAL,
            "cost_stress_not_worse": bool(c["not_worse_than_stage079_stress"].eq(1).all()) if not c.empty else False,
        }
        rows.append(
            {
                "variant": row["variant"],
                "label": row["label"],
                **{name: int(flag) for name, flag in checks.items()},
                "hard_constraint_pass": int(all(checks.values())),
                "failed_hard_checks": ",".join([name for name, flag in checks.items() if not flag]),
            }
        )
    result = pd.DataFrame(rows).merge(score_one, on=["variant", "label"], how="left").merge(
        improved_p, on=["variant", "label"], how="left"
    )
    result["score90_improve_ge10pct"] = (result["score_90d"] >= 110.0).astype(int)
    result["score180_improve_ge10pct"] = (result["score_180d"] >= 110.0).astype(int)
    result["improved_5of8_each"] = ((result["improved_count_90d"] >= 5) & (result["improved_count_180d"] >= 5)).astype(int)
    result["promotion_pass"] = (
        result["hard_constraint_pass"].eq(1)
        & result["score90_improve_ge10pct"].eq(1)
        & result["score180_improve_ge10pct"].eq(1)
        & result["improved_5of8_each"].eq(1)
    ).astype(int)
    return result.sort_values(["promotion_pass", "short_holding_score"], ascending=[False, False])


def _write_report(summary: pd.DataFrame, horizon: pd.DataFrame, score: pd.DataFrame, cost: pd.DataFrame, gate: pd.DataFrame, decision: dict[str, Any]) -> None:
    report = [
        "# Stage093 Stage079现金槽位冻结卫星筛查",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：只读诊断；不修改C3交易规则，不增加61.5万账户资金，不扫小数权重。",
        "- A：Stage079；C：Stage079的11.5万现金槽位替换为已有冻结卫星曲线。",
        "",
        "## 外部调研判断",
        "",
        "- 趋势策略短持有体验改善更可能来自独立收益源、因子分散和风险预算，而不是继续调同源趋势阈值。",
        "- 本阶段只测试已有冻结曲线和等权组合边界；所有缩放到11.5万的期货卫星先标为诊断项，不直接晋级。",
        "",
        "## 全周期核心指标",
        "",
        _md_table(
            summary[
                [
                    "variant",
                    "total_return_pct",
                    "max_dd_pct",
                    "sharpe",
                    "ulcer_pct",
                    "rolling252_dd30_breach_rate",
                    "rolling504_dd30_breach_rate",
                    "annual_cold_start_dd30_pass_rate",
                    "quarter_cold_start_dd30_pass_rate",
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
        "## 体验评分",
        "",
        _md_table(
            score[
                [
                    "variant",
                    "horizon_days",
                    "experience_score",
                    "improved_metric_count",
                    "target_hit_count",
                    "score_90d",
                    "score_180d",
                    "short_holding_score",
                ]
            ].sort_values(["variant", "horizon_days"])
        ),
        "",
        "## 成本压力",
        "",
        _md_table(cost[["variant", "slippage_multiplier", "max_dd_pct", "baseline_stage079_max_dd_pct", "not_worse_than_stage079_stress"]]),
        "",
        "## 硬门禁与晋级",
        "",
        _md_table(
            gate[
                [
                    "variant",
                    "hard_constraint_pass",
                    "score_90d",
                    "score_180d",
                    "short_holding_score",
                    "improved_count_90d",
                    "improved_count_180d",
                    "promotion_pass",
                    "failed_hard_checks",
                ]
            ]
        ),
        "",
        "## 决策",
        "",
        "```json",
        json.dumps(_json_safe(decision), ensure_ascii=False, indent=2),
        "```",
        "",
        "## 过拟合与继续价值反思",
        "",
        "- 运行前判断：不是参数过拟合；本阶段不新增阈值、不按坏窗口调权重，只测试已有冻结曲线。但缩放期货卫星有真实可执行性风险。",
        "- 运行后判断：若有高分诊断项，也不能直接晋级，必须先证明11.5万现金槽位真实整数手数、保证金和滑点可承载。",
        "- 继续价值判断：若所有诊断项仍过不了硬约束或真实可执行性，现金槽位卫星路线应降级，继续寻找外生状态或新低相关承载。",
    ]
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curves = _load_curves()
    candidates = _build_candidates(curves)
    calendar = curves.index
    c3_pnl, c3_slippage = _load_c3_raw(calendar)

    stage087_candidates = [_stage087_candidate(candidate) for candidate in candidates]
    summary = pd.DataFrame([s087._stats(candidate) for candidate in stage087_candidates])
    horizon = pd.DataFrame(
        [s087._horizon_metrics(candidate, horizon_days) for candidate in stage087_candidates for horizon_days in (90, 180)]
    )
    score = s087._score_horizons(horizon)
    cost = _cost_stress(candidates, c3_pnl, c3_slippage)
    gate = _gate(summary, score, cost)

    daily_rows: list[pd.DataFrame] = []
    for candidate in candidates:
        daily_rows.append(
            pd.DataFrame(
                {
                    "date": candidate.equity.index,
                    "variant": candidate.variant,
                    "label": candidate.label,
                    "equity": candidate.equity.to_numpy(dtype=float),
                    "satellite_pnl": candidate.satellite_pnl.to_numpy(dtype=float),
                    "satellite_slippage": candidate.satellite_slippage.to_numpy(dtype=float),
                }
            )
        )
    daily = pd.concat(daily_rows, ignore_index=True)

    promoted = gate[gate["promotion_pass"].eq(1) & ~gate["variant"].eq(BASELINE_VARIANT)]
    non_base = gate[~gate["variant"].eq(BASELINE_VARIANT)]
    best = non_base.sort_values("short_holding_score", ascending=False).iloc[0] if not non_base.empty else None
    decision = {
        "stage": "Stage093",
        "model_tag": MODEL_TAG,
        "line_id": "futures_trend_drawdown30_preserve_return",
        "decision": "promotion_candidate_requires_true_feasibility" if len(promoted) else "no_promotable_candidate",
        "promoted_variants": promoted["variant"].tolist(),
        "best_non_baseline_variant": None if best is None else str(best["variant"]),
        "best_non_baseline_short_holding_score": None if best is None else float(best["short_holding_score"]),
        "note": "所有现金槽位缩放期货卫星均先按诊断项处理；不满足eligible_not_diagnostic时不能晋级。",
    }

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon.to_csv(HORIZON_PATH, index=False, encoding="utf-8-sig")
    score.to_csv(SCORE_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    gate.to_csv(GATE_PATH, index=False, encoding="utf-8-sig")
    daily.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(summary, horizon, score, cost, gate, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"report={REPORT_PATH}")


if __name__ == "__main__":
    main()
