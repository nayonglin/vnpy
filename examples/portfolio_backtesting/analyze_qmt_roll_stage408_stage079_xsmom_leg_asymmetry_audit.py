from __future__ import annotations

import json
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

sys.path.insert(0, str(PROJECT_DIR.resolve()))
import analyze_qmt_roll_stage402_stage079_xsmom_volmanaged_true_integer as s402  # noqa: E402
import analyze_qmt_roll_stage403_stage079_xsmom_execution_margin_audit as s403  # noqa: E402


MODEL_TAG = "stage408_stage079_xsmom_leg_asymmetry_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage408_stage079_xsmom_leg_asymmetry_audit"
LINE_ID = "futures_trend_drawdown30_preserve_return"

BASELINE_VARIANT = s403.BASELINE_VARIANT
STAGE103_VARIANT = s403.GUARD_VARIANT
LONG_ONLY_VARIANT = "xsmom_vt10_q_momq_long_only_round_half_broker10_guard"
SHORT_ONLY_VARIANT = "xsmom_vt10_q_momq_short_only_round_half_broker10_guard"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_{MODEL_TAG}.csv"
SCORE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_score_{MODEL_TAG}.csv"
FRESH_START_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_fresh_start_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
MARGIN_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_margin_audit_{MODEL_TAG}.csv"
GATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_{MODEL_TAG}.csv"
DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
SATELLITE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_satellite_daily_{MODEL_TAG}.csv"
LEG_ATTRIBUTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_leg_attribution_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


VARIANTS: tuple[s403.AuditVariant, ...] = (
    s403.AuditVariant(BASELINE_VARIANT, "A Stage079基准", "baseline", "50万C3下单+11.5万现金。"),
    s403.AuditVariant(
        STAGE103_VARIANT,
        "C0 Stage103 xsmom多空双边",
        "both_guard",
        "固定Stage103：scale>=0.5执行xsmom多空整篮子，并受1.10倍保证金闸门约束。",
    ),
    s403.AuditVariant(
        LONG_ONLY_VARIANT,
        "C1 Stage103 xsmom只保留多头腿",
        "long_only_guard",
        "固定Stage103的scale、0.5阈值、63日动量和1.10倍保证金闸门，只删除xsmom空头腿。",
    ),
    s403.AuditVariant(
        SHORT_ONLY_VARIANT,
        "C2 Stage103 xsmom只保留空头腿",
        "short_only_guard",
        "固定Stage103的scale、0.5阈值、63日动量和1.10倍保证金闸门，只删除xsmom多头腿。",
    ),
)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def _safe_metric(value: Any, default: float = 0.0) -> float:
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


def _filter_desired(
    desired: list[tuple[str, str, int, float]],
    side: str,
) -> list[tuple[str, str, int, float]]:
    if side == "long":
        return [item for item in desired if int(item[2]) > 0]
    if side == "short":
        return [item for item in desired if int(item[2]) < 0]
    return desired


def _simulate_guarded_side(
    side: str,
    window_name: str,
    window_frame: pd.DataFrame,
    margin_frame: pd.DataFrame,
    price_frame: pd.DataFrame,
    signals: pd.DataFrame,
    scale_by_date: pd.Series,
) -> pd.DataFrame:
    start = window_frame["date"].min()
    end = window_frame["date"].max()
    window_signals = signals[signals["date"].between(start, end)].copy()
    if window_signals.empty:
        return s403._empty_satellite(window_name)

    c3_pnl_by_date = window_frame.set_index("date")["c3_net_pnl"].astype(float).to_dict()
    c3_margin_by_date = margin_frame.set_index("date")["c3_margin"].astype(float).to_dict()
    price_by_date_product = {
        (row.date, row.product_vt_symbol): row
        for row in price_frame[price_frame["date"].between(start, end)].itertuples(index=False)
    }
    contract_to_product = (
        price_frame[price_frame["date"].between(start, end)]
        .drop_duplicates(["date", "main_contract_vt"])
        .set_index(["date", "main_contract_vt"])["product_vt_symbol"]
        .to_dict()
    )
    prev_positions: dict[str, int] = {}
    rows: list[dict[str, Any]] = []
    prev_equity = s402.ACCOUNT_CAPITAL

    for signal_row in window_signals.sort_values("date").itertuples(index=False):
        date = pd.Timestamp(signal_row.date).normalize()
        scale = float(scale_by_date.get(date, 0.0))
        day_prices = price_frame[price_frame["date"].eq(date)]
        price_by_product = {str(row.product_vt_symbol): row for row in day_prices.itertuples(index=False)}
        desired_all = s402._desired_contracts(signal_row, price_by_product)
        desired = _filter_desired(desired_all, side)
        targets, required_min1_margin = s402._target_lots("round_half", scale, desired)

        proposed_margin = 0.0
        for contract in targets:
            product = contract_to_product.get((date, contract))
            price_row = price_by_date_product.get((date, product)) if product else None
            if price_row is not None:
                proposed_margin += s402._safe_float(getattr(price_row, "margin_per_contract", 0.0))

        c3_margin = float(c3_margin_by_date.get(date, 0.0))
        margin_gate_skipped = int(
            bool(targets) and (c3_margin + proposed_margin) * s403.BROKER10_MULTIPLIER > prev_equity
        )
        if margin_gate_skipped:
            targets = {}
            proposed_margin = 0.0

        pnl = 0.0
        margin = 0.0
        for contract, lots in targets.items():
            product = contract_to_product.get((date, contract))
            price_row = price_by_date_product.get((date, product)) if product else None
            if price_row is None:
                continue
            pnl += lots * s402._safe_float(getattr(price_row, "prev_main_close", 0.0)) * s402._safe_float(
                getattr(price_row, "size", 1.0)
            ) * s402._safe_float(getattr(price_row, "product_return", 0.0))
            margin += abs(lots) * s402._safe_float(getattr(price_row, "margin_per_contract", 0.0))

        turnover = 0
        slippage_cost = 0.0
        for contract in set(prev_positions) | set(targets):
            delta = abs(targets.get(contract, 0) - prev_positions.get(contract, 0))
            if delta <= 0:
                continue
            turnover += delta
            product = contract_to_product.get((date, contract))
            price_row = price_by_date_product.get((date, product)) if product else None
            if price_row is not None:
                slippage_cost += delta * s402._safe_float(getattr(price_row, "slippage", 0.0)) * s402._safe_float(
                    getattr(price_row, "size", 1.0)
                )

        sat_daily_pnl = pnl - slippage_cost
        rows.append(
            {
                "date": date,
                "window_name": window_name,
                "satellite_daily_pnl": sat_daily_pnl,
                "satellite_slippage_cost": slippage_cost,
                "satellite_margin": margin,
                "satellite_turnover_contracts": turnover,
                "held_contract_count": len(targets),
                "desired_signal_count": len(desired),
                "desired_signal_count_all": len(desired_all),
                "required_min1_margin": required_min1_margin,
                "stage101_scale": scale,
                "margin_gate_skipped": margin_gate_skipped,
            }
        )
        prev_positions = targets
        prev_equity += float(c3_pnl_by_date.get(date, 0.0)) + sat_daily_pnl

    return pd.DataFrame(rows)


def _add_stage103_relative_gate(gate: pd.DataFrame, summary: pd.DataFrame, cost: pd.DataFrame) -> pd.DataFrame:
    result = gate.copy()
    stage103_summary = summary[summary["variant"].eq(STAGE103_VARIANT)].iloc[0]
    stage103_score = result[result["variant"].eq(STAGE103_VARIANT)].iloc[0]
    stage103_dd = (
        cost[cost["variant"].eq(STAGE103_VARIANT)]
        .set_index("slippage_multiplier")["max_dd_pct"]
        .astype(float)
        .to_dict()
    )
    rows: list[dict[str, Any]] = []
    for _, row in summary.iterrows():
        variant = str(row["variant"])
        c = cost[cost["variant"].eq(variant)]
        incremental_checks = {
            "total_return_not_lower_than_stage103": _safe_metric(row["total_return_pct"]) >= _safe_metric(
                stage103_summary["total_return_pct"]
            )
            - 1e-4,
            "max_dd_not_worse_than_stage103": _safe_metric(row["max_dd_pct"]) >= _safe_metric(
                stage103_summary["max_dd_pct"]
            )
            - 1e-4,
            "sharpe_not_lower_than_stage103": _safe_metric(row["sharpe"]) >= _safe_metric(stage103_summary["sharpe"]) - 1e-4,
            "ulcer_not_higher_than_stage103": _safe_metric(row["ulcer_pct"]) <= _safe_metric(stage103_summary["ulcer_pct"]) + 1e-4,
            "cost_stress_not_worse_than_stage103": bool(
                all(
                    _safe_metric(cost_row.max_dd_pct) >= _safe_metric(stage103_dd.get(cost_row.slippage_multiplier)) - 1e-9
                    for cost_row in c.itertuples(index=False)
                )
            )
            if not c.empty
            else False,
        }
        rows.append(
            {
                "variant": variant,
                **{key: int(value) for key, value in incremental_checks.items()},
                "metric_incremental_pass_stage103": int(all(incremental_checks.values())),
                "failed_stage103_incremental_checks": ",".join(
                    [key for key, value in incremental_checks.items() if not value]
                ),
            }
        )
    incr = pd.DataFrame(rows)
    result = result.merge(incr, on="variant", how="left")
    result["short_score_not_lower_than_stage103"] = (
        result["short_holding_score"] >= _safe_metric(stage103_score["short_holding_score"]) - 1e-4
    ).astype(int)
    result["stage103_relative_promotion_pass"] = (
        result["execution_relative_pass"].eq(1)
        & result["metric_incremental_pass_stage103"].eq(1)
        & result["short_score_not_lower_than_stage103"].eq(1)
    ).astype(int)
    return result.sort_values(
        ["stage103_relative_promotion_pass", "execution_relative_pass", "short_holding_score"],
        ascending=[False, False, False],
    )


def _leg_attribution(satellite_full_by_variant: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for variant, frame in satellite_full_by_variant.items():
        if frame.empty:
            continue
        rows.append(
            {
                "variant": variant,
                "satellite_pnl": float(frame["satellite_daily_pnl"].sum()),
                "satellite_slippage": float(frame["satellite_slippage_cost"].sum()),
                "satellite_turnover": float(frame["satellite_turnover_contracts"].sum()),
                "active_rate": float((frame["satellite_margin"] > 0.0).mean()),
                "mean_held_contracts": float(frame["held_contract_count"].mean()),
                "max_margin": float(frame["satellite_margin"].max()),
                "margin_gate_skipped_days": int(frame.get("margin_gate_skipped", pd.Series(dtype=float)).sum()),
            }
        )
    return pd.DataFrame(rows)


def _plot(daily: pd.DataFrame, horizon: pd.DataFrame, gate: pd.DataFrame) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:  # pragma: no cover
        print(f"[stage408] skip chart: {exc}", flush=True)
        return
    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    full = daily[daily["window_name"].eq("start_2020")]
    for variant, frame in full.groupby("variant"):
        frame = frame.sort_values("date")
        nav = pd.Series(frame["equity"].to_numpy(dtype=float), index=pd.to_datetime(frame["date"])) / s402.ACCOUNT_CAPITAL
        axes[0, 0].plot(nav.index, nav, label=variant, linewidth=1.0)
        axes[1, 0].plot(nav.index, (nav / nav.cummax() - 1.0) * 100.0, label=variant, linewidth=1.0)
    axes[0, 0].set_title("Stage108 NAV")
    axes[1, 0].set_title("Drawdown")
    axes[1, 0].axhline(-30.0, color="red", linestyle="--", linewidth=1.0)
    axes[0, 0].legend(fontsize=7)
    axes[1, 0].legend(fontsize=7)

    view = horizon.pivot(index="variant", columns="horizon_days", values="return_p05_pct").reindex(
        [spec.variant for spec in VARIANTS]
    )
    x = np.arange(len(view))
    width = 0.35
    axes[0, 1].bar(x - width / 2, view[90].to_numpy(dtype=float), width, label="90d p05")
    axes[0, 1].bar(x + width / 2, view[180].to_numpy(dtype=float), width, label="180d p05")
    axes[0, 1].axhline(0.0, color="black", linewidth=0.8)
    axes[0, 1].set_title("Bottom 5% Holding Return")
    axes[0, 1].set_xticks(x)
    axes[0, 1].set_xticklabels(view.index, rotation=25, ha="right", fontsize=7)
    axes[0, 1].legend(fontsize=8)

    g = gate.set_index("variant").reindex([spec.variant for spec in VARIANTS])
    axes[1, 1].bar(x - width / 2, g["score_90d"].to_numpy(dtype=float), width, label="90d score")
    axes[1, 1].bar(x + width / 2, g["score_180d"].to_numpy(dtype=float), width, label="180d score")
    axes[1, 1].axhline(110.0, color="red", linestyle="--", linewidth=1.0)
    axes[1, 1].set_title("Experience Scores")
    axes[1, 1].set_xticks(x)
    axes[1, 1].set_xticklabels(g.index, rotation=25, ha="right", fontsize=7)
    axes[1, 1].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    horizon: pd.DataFrame,
    score: pd.DataFrame,
    fresh: pd.DataFrame,
    cost: pd.DataFrame,
    margin_audit: pd.DataFrame,
    leg: pd.DataFrame,
    gate: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    report = [
        "# Stage108 Stage079 xsmom多空腿不对称审计",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：结构拆解，不调 Stage103 的 `0.5/10%/63日/broker10_guard`。",
        "- A/B/C：A=Stage079；C0=Stage103 xsmom多空双边；C1=只保留xsmom多头腿；C2=只保留xsmom空头腿。",
        f"- 图表：`{CHART_PATH}`",
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
            ]
        ),
        "",
        "## 体验评分",
        "",
        _md_table(score[["variant", "horizon_days", "experience_score", "score_90d", "score_180d", "short_holding_score"]]),
        "",
        "## 多起点与10%保证金缓冲",
        "",
        _md_table(
            fresh[
                [
                    "window_name",
                    "variant",
                    "total_return_pct",
                    "max_dd_pct",
                    "dd30_pass",
                    "satellite_turnover",
                    "margin_gate_skipped_days",
                    "broker10_max_margin_to_equity_pct",
                    "broker10_reject_days",
                ]
            ],
            max_rows=80,
        ),
        "",
        "## 卫星腿归因",
        "",
        _md_table(leg),
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
            ]
        ),
        "",
        "## 晋级闸门",
        "",
        _md_table(
            gate[
                [
                    "variant",
                    "metric_hard_pass",
                    "target_pass_3m6m",
                    "research_promotion_pass",
                    "execution_relative_pass",
                    "metric_incremental_pass_stage103",
                    "short_score_not_lower_than_stage103",
                    "stage103_relative_promotion_pass",
                    "score_90d",
                    "score_180d",
                    "objective_improved_8_count_90d",
                    "objective_improved_8_count_180d",
                    "failed_metric_checks",
                    "failed_stage103_incremental_checks",
                ]
            ]
        ),
        "",
        "## 反过拟合说明",
        "",
        "- 只做多空腿结构拆解，不扫阈值、窗口、品种、月份或现金数额。",
        "- 测试依据来自动量 crash 研究中的短腿反弹风险假设；若结果不通过，不继续用日期或单品种补丁救援。",
    ]
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    old_variants = s403.VARIANTS
    s403.VARIANTS = VARIANTS
    try:
        combo = s402._load_combo_daily()
        margin = s402._load_margin()
        full = combo[combo["window_name"].eq("start_2020")].sort_values("date").drop_duplicates("date", keep="last")
        scale_by_date = s402._build_stage101_scale(full)
        price_frame = s402._build_price_frame()
        price_frame["date"] = pd.to_datetime(price_frame["date"], errors="coerce").dt.normalize()
        signals = s402._load_signal_daily()
        signals["date"] = pd.to_datetime(signals["date"], errors="coerce").dt.normalize()

        satellite_by_window_variant: dict[tuple[str, str], pd.DataFrame] = {}
        daily_by_window_variant: dict[tuple[str, str], pd.DataFrame] = {}
        satellite_full_by_variant: dict[str, pd.DataFrame] = {}
        candidates: list[Any] = []
        daily_parts: list[pd.DataFrame] = []

        for window_name, frame in combo.groupby("window_name", sort=True):
            frame = frame.sort_values("date").drop_duplicates("date", keep="last")
            margin_frame = margin[margin["window_name"].eq(window_name)].sort_values("date").drop_duplicates("date", keep="last")
            for spec in VARIANTS:
                if spec.variant == BASELINE_VARIANT:
                    sat = s403._empty_satellite(window_name)
                elif spec.variant == STAGE103_VARIANT:
                    sat = s403._simulate_guarded_round_half(window_name, frame, margin_frame, price_frame, signals, scale_by_date)
                elif spec.variant == LONG_ONLY_VARIANT:
                    sat = _simulate_guarded_side("long", window_name, frame, margin_frame, price_frame, signals, scale_by_date)
                elif spec.variant == SHORT_ONLY_VARIANT:
                    sat = _simulate_guarded_side("short", window_name, frame, margin_frame, price_frame, signals, scale_by_date)
                else:
                    raise ValueError(f"unknown variant {spec.variant}")
                satellite_by_window_variant[(window_name, spec.variant)] = sat
                daily = s402._combine_daily(frame, sat, spec.variant, 1.0)
                daily["window_name"] = window_name
                daily_by_window_variant[(window_name, spec.variant)] = daily
                if window_name == "start_2020":
                    satellite_full_by_variant[spec.variant] = sat

        full_frame = combo[combo["window_name"].eq("start_2020")].sort_values("date").drop_duplicates("date", keep="last")
        for spec in VARIANTS:
            daily = daily_by_window_variant[("start_2020", spec.variant)]
            daily_parts.append(daily)
            equity = s402._calendarize(pd.Series(daily["equity"].to_numpy(dtype=float), index=daily["date"]))
            candidates.append(s403._candidate(spec, equity))

        daily_all = pd.concat(daily_parts, ignore_index=True)
        satellite_all = pd.concat(
            [
                frame.assign(variant=variant)
                for (window_name, variant), frame in satellite_by_window_variant.items()
                if variant != BASELINE_VARIANT and not frame.empty
            ],
            ignore_index=True,
        )
        summary = pd.DataFrame([s402.s087._stats(candidate) for candidate in candidates])
        horizon = pd.DataFrame(
            [s402.s087._horizon_metrics(candidate, days) for candidate in candidates for days in (90, 180)]
        )
        score = s402.s087._score_horizons(horizon)
        margin_audit = s403._margin_audit(combo, margin, satellite_by_window_variant, daily_by_window_variant)
        fresh = s403._fresh_start(combo, margin, satellite_by_window_variant, daily_by_window_variant, margin_audit)
        cost = s403._cost_stress(full_frame, satellite_full_by_variant)
        gate = s403._gate(summary, horizon, score, cost, fresh, margin_audit)
        gate = _add_stage103_relative_gate(gate, summary, cost)
        leg = _leg_attribution(satellite_full_by_variant)
        _plot(daily_all, horizon, gate)

        stage103_relative = gate[
            gate["stage103_relative_promotion_pass"].eq(1)
            & ~gate["variant"].isin([BASELINE_VARIANT, STAGE103_VARIANT])
        ]
        execution_ready = gate[
            gate["execution_relative_pass"].eq(1) & ~gate["variant"].eq(BASELINE_VARIANT)
        ]
        decision = {
            "stage": "Stage108",
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "decision": "stage103_relative_promotion"
            if len(stage103_relative)
            else ("execution_relative_candidate_exists" if len(execution_ready) else "no_new_promotion"),
            "stage103_relative_ready_variants": stage103_relative["variant"].tolist(),
            "execution_relative_ready_variants": execution_ready["variant"].tolist(),
            "best_by_stage103_relative_gate": str(gate.iloc[0]["variant"]) if not gate.empty else "",
            "chart": str(CHART_PATH),
            "judgement": "只做xsmom多空腿结构拆解；若拆腿不能优于Stage103并通过冷启动/成本闸门，则不晋级。",
        }

        summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
        horizon.to_csv(HORIZON_PATH, index=False, encoding="utf-8-sig")
        score.to_csv(SCORE_PATH, index=False, encoding="utf-8-sig")
        fresh.to_csv(FRESH_START_PATH, index=False, encoding="utf-8-sig")
        cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
        margin_audit.to_csv(MARGIN_AUDIT_PATH, index=False, encoding="utf-8-sig")
        gate.to_csv(GATE_PATH, index=False, encoding="utf-8-sig")
        daily_all.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
        satellite_all.to_csv(SATELLITE_PATH, index=False, encoding="utf-8-sig")
        leg.to_csv(LEG_ATTRIBUTION_PATH, index=False, encoding="utf-8-sig")
        DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
        _write_report(summary, horizon, score, fresh, cost, margin_audit, leg, gate, decision)
        print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
        print(f"report={REPORT_PATH}")
    finally:
        s403.VARIANTS = old_variants


if __name__ == "__main__":
    main()
