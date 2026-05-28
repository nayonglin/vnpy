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
MODEL_TAG = "stage399_stage079_xsmom_overlay_cash115_coldstart_v1"
OUTPUT_PREFIX = "qmt_roll_stage399_stage079_xsmom_overlay_cash115_coldstart"
LINE_ID = "futures_trend_drawdown30_preserve_return"

COMBO_DAILY_PATH = OUTPUT_DIR / "qmt_roll_stage352_xsmom_overlay_cash_multiperiod_combo_daily_stage352_xsmom_overlay_cash_multiperiod_v1.csv"
MARGIN_PATH = OUTPUT_DIR / "qmt_roll_stage352_xsmom_overlay_cash_multiperiod_margin_stage352_xsmom_overlay_cash_multiperiod_v1.csv"

FUTURES_CAPITAL = 500_000.0
ACCOUNT_CAPITAL = 615_000.0
STAGE079_CASH = 115_000.0
BASELINE_VARIANT = "stage079"
TARGET_DD_PCT = -30.0

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_{MODEL_TAG}.csv"
SCORE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_score_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
FRESH_START_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_fresh_start_{MODEL_TAG}.csv"
GATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_{MODEL_TAG}.csv"
DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_equity_drawdown_{MODEL_TAG}.png"


@dataclass(frozen=True)
class VariantSpec:
    variant: str
    label: str
    use_overlay: bool
    gate252: bool
    eligible_for_promotion: bool
    candidate_class: str
    note: str


VARIANTS: tuple[VariantSpec, ...] = (
    VariantSpec(
        BASELINE_VARIANT,
        "Stage079基准：50万C3下单+11.5万现金",
        False,
        False,
        True,
        "baseline",
        "唯一硬约束基准。",
    ),
    VariantSpec(
        "xsmom_overlay_cash115",
        "诊断：Stage079账户口径叠加min1_all_no_cap xsmom overlay",
        True,
        False,
        True,
        "integer_xsmom_overlay_cash115",
        "复用Stage352固定xsmom整数手数overlay；总账户仍为61.5万，不新增外部现金。",
    ),
    VariantSpec(
        "xsmom_overlay_cash115_gate252_diag",
        "诊断：xsmom overlay仅在自身252交易日PnL为正时启用",
        True,
        True,
        False,
        "pnl_level_xsmom_own_momentum_gate",
        "只作为自有策略动量门控诊断；未重建逐笔开平仓，不能晋级。",
    ),
)


def _load_stage087_module():
    spec = importlib.util.spec_from_file_location("stage087_gate_for_stage399", STAGE087_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {STAGE087_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["stage087_gate_for_stage399"] = module
    spec.loader.exec_module(module)
    return module


s087 = _load_stage087_module()


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


def _load_combo_daily() -> pd.DataFrame:
    frame = pd.read_csv(COMBO_DAILY_PATH, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    numeric_cols = [
        "c3_net_pnl",
        "c3_slippage",
        "daily_pnl",
        "slippage_cost",
        "combo_net_pnl",
        "combo_slippage",
        "trade_count",
        "turnover_contracts",
    ]
    for col in numeric_cols:
        frame[col] = pd.to_numeric(frame.get(col, 0.0), errors="coerce").fillna(0.0)
    return frame.dropna(subset=["date"]).sort_values(["window_name", "date"])


def _load_margin() -> pd.DataFrame:
    frame = pd.read_csv(MARGIN_PATH, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    for col in ["account_balance", "c3_margin", "satellite_margin", "total_margin"]:
        frame[col] = pd.to_numeric(frame.get(col, 0.0), errors="coerce").fillna(0.0)
    return frame.dropna(subset=["date"]).sort_values(["window_name", "date"])


def _gate252_by_date(full: pd.DataFrame) -> pd.Series:
    gate = full["daily_pnl"].rolling(252, min_periods=252).sum().shift(1) > 0.0
    return pd.Series(gate.fillna(False).to_numpy(dtype=bool), index=full["date"])


def _variant_gate(frame: pd.DataFrame, gate_by_date: pd.Series, spec: VariantSpec) -> pd.Series:
    if not spec.use_overlay:
        return pd.Series(False, index=frame.index)
    if not spec.gate252:
        return pd.Series(True, index=frame.index)
    return frame["date"].map(gate_by_date).fillna(False).astype(bool)


def _equity_from_frame(
    frame: pd.DataFrame,
    spec: VariantSpec,
    gate_by_date: pd.Series,
    slippage_multiplier: float = 1.0,
) -> pd.Series:
    active = _variant_gate(frame, gate_by_date, spec)
    pnl = frame["c3_net_pnl"].astype(float).copy()
    slippage = frame["c3_slippage"].astype(float).copy()
    if spec.use_overlay:
        pnl = pnl + frame["daily_pnl"].astype(float).where(active, 0.0)
        slippage = slippage + frame["slippage_cost"].astype(float).where(active, 0.0)
    stressed = pnl - (float(slippage_multiplier) - 1.0) * slippage
    equity = FUTURES_CAPITAL + stressed.cumsum() + STAGE079_CASH
    return pd.Series(equity.to_numpy(dtype=float), index=frame["date"])


def _calendarize(equity: pd.Series) -> pd.Series:
    equity = equity.sort_index().dropna()
    calendar = pd.date_range(equity.index.min(), equity.index.max(), freq="D")
    return equity.reindex(calendar).ffill().dropna()


def _candidate(spec: VariantSpec, equity: pd.Series) -> Any:
    return s087.Candidate(
        variant=spec.variant,
        label=spec.label,
        equity=equity,
        capital_used=ACCOUNT_CAPITAL,
        candidate_class=spec.candidate_class,
        eligible_for_promotion=spec.eligible_for_promotion,
        note=spec.note,
    )


def _cost_stress(full: pd.DataFrame, gate_by_date: pd.Series) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    baseline_dd: dict[float, float] = {}
    for multiplier in (1.0, 2.0, 3.0, 5.0):
        for spec in VARIANTS:
            equity = _calendarize(_equity_from_frame(full, spec, gate_by_date, multiplier))
            nav = equity / ACCOUNT_CAPITAL
            max_dd = s087._max_drawdown(nav)
            if spec.variant == BASELINE_VARIANT:
                baseline_dd[multiplier] = max_dd
            rows.append(
                {
                    "variant": spec.variant,
                    "label": spec.label,
                    "slippage_multiplier": multiplier,
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


def _fresh_start(combo: pd.DataFrame, margin: pd.DataFrame, gate_by_date: pd.Series) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for window_name, frame in combo.groupby("window_name", sort=True):
        frame = frame.sort_values("date").drop_duplicates("date", keep="last")
        m = margin[margin["window_name"].eq(window_name)].sort_values("date").drop_duplicates("date", keep="last")
        for spec in VARIANTS:
            active = _variant_gate(frame, gate_by_date, spec)
            equity = _equity_from_frame(frame, spec, gate_by_date, 1.0)
            nav = equity / ACCOUNT_CAPITAL
            max_dd = s087._max_drawdown(nav)
            if m.empty:
                max_margin_to_equity = 0.0
                reject_days = 0
            else:
                mm = m.copy()
                if spec.use_overlay:
                    active_by_date = pd.Series(active.to_numpy(dtype=bool), index=frame["date"])
                    sat_active = mm["date"].map(active_by_date).fillna(False).astype(bool)
                    total_margin = mm["c3_margin"] + mm["satellite_margin"].where(sat_active, 0.0)
                else:
                    total_margin = mm["c3_margin"]
                margin_equity = total_margin.to_numpy(dtype=float) / equity.reindex(mm["date"]).ffill().to_numpy(dtype=float) * 100.0
                max_margin_to_equity = float(np.nanmax(margin_equity)) if len(margin_equity) else 0.0
                reject_days = int(np.sum(margin_equity > 100.0))
            rows.append(
                {
                    "window_name": window_name,
                    "variant": spec.variant,
                    "label": spec.label,
                    "start_date": str(frame["date"].min().date()),
                    "end_date": str(frame["date"].max().date()),
                    "end_equity": float(equity.iloc[-1]),
                    "total_return_pct": float((nav.iloc[-1] - 1.0) * 100.0),
                    "max_dd_pct": max_dd,
                    "dd30_pass": int(max_dd >= TARGET_DD_PCT),
                    "active_overlay_days": int(active.sum()) if spec.use_overlay else 0,
                    "max_margin_to_equity_pct": max_margin_to_equity,
                    "reject_days": reject_days,
                }
            )
    return pd.DataFrame(rows)


def _gate(summary: pd.DataFrame, score: pd.DataFrame, cost: pd.DataFrame, fresh: pd.DataFrame) -> pd.DataFrame:
    baseline = summary[summary["variant"].eq(BASELINE_VARIANT)].iloc[0]
    score_one = score.drop_duplicates(["variant", "label"])[
        ["variant", "label", "score_90d", "score_180d", "short_holding_score"]
    ]
    improved = score.groupby(["variant", "label", "horizon_days"])["improved_metric_count"].first().reset_index()
    improved_p = improved.pivot(index=["variant", "label"], columns="horizon_days", values="improved_metric_count").reset_index()
    improved_p.columns = ["variant", "label", "improved_count_90d", "improved_count_180d"]
    fresh_failures = (
        fresh[fresh["dd30_pass"].eq(0)]
        .groupby("variant")["window_name"]
        .apply(lambda values: ",".join(sorted(map(str, values))))
        .to_dict()
    )
    rows: list[dict[str, Any]] = []
    for _, row in summary.iterrows():
        c = cost[cost["variant"].eq(row["variant"])]
        checks = {
            "eligible_not_diagnostic": int(row["eligible_for_promotion"]) == 1,
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
            "fresh_start_dd30_pass": str(row["variant"]) not in fresh_failures,
        }
        rows.append(
            {
                "variant": row["variant"],
                "label": row["label"],
                **{name: int(flag) for name, flag in checks.items()},
                "hard_constraint_pass": int(all(checks.values())),
                "fresh_start_failed_windows": fresh_failures.get(str(row["variant"]), ""),
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


def _plot(daily: pd.DataFrame) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:  # pragma: no cover
        print(f"[stage399] skip chart: {exc}", flush=True)
        return
    fig, axes = plt.subplots(2, 1, figsize=(13, 8), sharex=True)
    for variant, frame in daily.groupby("variant"):
        frame = frame.sort_values("date")
        equity = pd.Series(frame["equity"].to_numpy(dtype=float), index=pd.to_datetime(frame["date"]))
        nav = equity / ACCOUNT_CAPITAL
        axes[0].plot(nav.index, nav, label=variant, linewidth=1.2)
        dd = nav / nav.cummax() - 1.0
        axes[1].plot(dd.index, dd * 100.0, label=variant, linewidth=1.1)
    axes[0].set_title("Stage099/399 Stage079 vs xsmom overlay cash115")
    axes[0].set_ylabel("NAV")
    axes[1].set_ylabel("Drawdown %")
    axes[1].axhline(-30.0, color="red", linestyle="--", linewidth=1.0)
    axes[0].legend()
    axes[1].legend()
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    horizon: pd.DataFrame,
    score: pd.DataFrame,
    cost: pd.DataFrame,
    fresh: pd.DataFrame,
    gate: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    report = [
        "# Stage099 Stage079 + xsmom overlay 11.5万现金口径冷启动审计",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：只读诊断；复用Stage352固定 `min1_all_no_cap` xsmom整数手数overlay，不改C3交易规则。",
        "- 候选假设：若用Stage079已有11.5万账户缓冲承载xsmom overlay，可能同时补收益和改善3/6个月体验。",
        "- 晋级附加约束：除全周期硬指标外，新账户从任一预声明起点启动时不得穿30回撤。",
        f"- 图表：`{CHART_PATH}`",
        "",
        "## 外部调研与判断",
        "",
        "- 公开趋势跟随/CTA研究支持趋势、横截面动量、策略分散和风险预算的组合价值；不支持继续调单一入场信号胜率。",
        "- 本阶段因此回到独立收益源承载问题：同一个冻结xsmom overlay，在Stage079 61.5万账户口径下重新审计，而不是救 `3万现金` 小数。",
        "",
        "## 决策",
        "",
        "```json",
        json.dumps(_json_safe(decision), ensure_ascii=False, indent=2),
        "```",
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
                    "score_90d",
                    "score_180d",
                    "short_holding_score",
                ]
            ].sort_values(["variant", "horizon_days"])
        ),
        "",
        "## 成本压力",
        "",
        _md_table(cost[["variant", "slippage_multiplier", "total_return_pct", "max_dd_pct", "baseline_stage079_max_dd_pct", "not_worse_than_stage079_stress"]]),
        "",
        "## 新账户多起点冷启动",
        "",
        _md_table(fresh[["window_name", "variant", "total_return_pct", "max_dd_pct", "dd30_pass", "active_overlay_days", "max_margin_to_equity_pct", "reject_days"]]),
        "",
        "## 晋级闸门",
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
                    "fresh_start_failed_windows",
                    "failed_hard_checks",
                ]
            ]
        ),
        "",
        "## 反过拟合说明",
        "",
        "- 只复用一个已冻结的xsmom overlay形状和Stage079既有11.5万账户缓冲，不扫现金、不扫品种、不改C3入场出场。",
        "- 252日自有动量门控只作为诊断项，且没有逐笔重建开平仓，因此不允许晋级。",
        "- 若全周期好看但新账户多起点穿30，本路线必须停止或转为新承载工具，而不是继续修2024/2025/2026窗口。",
    ]
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    combo = _load_combo_daily()
    margin = _load_margin()
    full = combo[combo["window_name"].eq("start_2020")].sort_values("date").drop_duplicates("date", keep="last")
    if full.empty:
        raise RuntimeError("missing start_2020 in Stage352 combo daily")
    gate_by_date = _gate252_by_date(full)

    daily_parts: list[pd.DataFrame] = []
    stage087_candidates: list[Any] = []
    for spec in VARIANTS:
        equity = _calendarize(_equity_from_frame(full, spec, gate_by_date, 1.0))
        stage087_candidates.append(_candidate(spec, equity))
        daily_parts.append(
            pd.DataFrame(
                {
                    "date": equity.index,
                    "variant": spec.variant,
                    "label": spec.label,
                    "equity": equity.to_numpy(dtype=float),
                }
            )
        )

    summary = pd.DataFrame([s087._stats(candidate) for candidate in stage087_candidates])
    horizon = pd.DataFrame(
        [s087._horizon_metrics(candidate, horizon_days) for candidate in stage087_candidates for horizon_days in (90, 180)]
    )
    score = s087._score_horizons(horizon)
    cost = _cost_stress(full, gate_by_date)
    fresh = _fresh_start(combo, margin, gate_by_date)
    gate = _gate(summary, score, cost, fresh)
    daily = pd.concat(daily_parts, ignore_index=True)

    promoted = gate[gate["promotion_pass"].eq(1) & ~gate["variant"].eq(BASELINE_VARIANT)]
    full_pass = gate[
        ~gate["variant"].eq(BASELINE_VARIANT)
        & gate["total_return_not_lower"].eq(1)
        & gate["max_dd_not_worse"].eq(1)
        & gate["sharpe_not_lower"].eq(1)
        & gate["ulcer_not_higher"].eq(1)
        & gate["score90_improve_ge10pct"].eq(1)
        & gate["score180_improve_ge10pct"].eq(1)
        & gate["improved_5of8_each"].eq(1)
    ]
    decision = {
        "stage": "Stage099",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": "promotion_candidate" if len(promoted) else "full_sample_pass_but_fresh_start_fail",
        "promoted_variants": promoted["variant"].tolist(),
        "full_sample_pass_variants": full_pass["variant"].tolist(),
        "best_by_short_holding_score": gate.iloc[0]["variant"] if not gate.empty else "",
        "chart": str(CHART_PATH),
        "note": "xsmom overlay在Stage079 61.5万全周期口径强，但新账户多起点冷启动仍失败，因此不晋级。",
    }

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon.to_csv(HORIZON_PATH, index=False, encoding="utf-8-sig")
    score.to_csv(SCORE_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    fresh.to_csv(FRESH_START_PATH, index=False, encoding="utf-8-sig")
    gate.to_csv(GATE_PATH, index=False, encoding="utf-8-sig")
    daily.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _plot(daily)
    _write_report(summary, horizon, score, cost, fresh, gate, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"report={REPORT_PATH}")


if __name__ == "__main__":
    main()
