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
import analyze_qmt_roll_stage405_stage079_reversal_protection_scout as s405  # noqa: E402
import analyze_qmt_roll_stage407_stage079_cffex_rates_true_overlay as s407  # noqa: E402


MODEL_TAG = "stage429_stage103_cffex_curve_spread_overlay_v1"
OUTPUT_PREFIX = "qmt_roll_stage429_stage103_cffex_curve_spread_overlay"
LINE_ID = "futures_trend_drawdown30_preserve_return"

BASELINE_VARIANT = s405.BASELINE_VARIANT
STAGE103_VARIANT = s405.STAGE103_VARIANT
CURVE_VARIANT = "stage103_plus_cffex_tf_t_curve_mr120_2tf1t_guard"

LOOKBACK_DAYS = 120
ENTRY_Z = 1.0
BROKER10_MULTIPLIER = s405.BROKER10_MULTIPLIER
ACCOUNT_CAPITAL = s405.ACCOUNT_CAPITAL

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_{MODEL_TAG}.csv"
SCORE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_score_{MODEL_TAG}.csv"
FRESH_START_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_fresh_start_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
MARGIN_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_margin_audit_{MODEL_TAG}.csv"
BAD_WINDOW_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bad_window_contribution_{MODEL_TAG}.csv"
GATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_{MODEL_TAG}.csv"
DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
OVERLAY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_overlay_daily_{MODEL_TAG}.csv"
FEATURE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_features_{MODEL_TAG}.csv"
RATES_PANEL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rates_panel_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


VARIANTS: tuple[s405.VariantSpec, ...] = (
    s405.VariantSpec(
        BASELINE_VARIANT,
        "A Stage079基准",
        "baseline",
        "none",
        0,
        0,
        0,
        "50万C3下单+11.5万现金。",
    ),
    s405.VariantSpec(
        STAGE103_VARIANT,
        "C0 Stage103 broker10_guard",
        "stage103",
        "none",
        0,
        0,
        0,
        "当前主执行相对候选。",
    ),
    s405.VariantSpec(
        CURVE_VARIANT,
        "C1 Stage103+中金所TF/T曲线中性MR120",
        "cffex_curve_spread_overlay",
        "curve_mr",
        LOOKBACK_DAYS,
        1,
        1,
        "只做TF/T一组国债曲线相对价值：2手TF对1手T，120日z-score超过1时做均值回归，并受10%保证金缓冲约束。",
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


def _build_curve_features(rates_panel: pd.DataFrame) -> pd.DataFrame:
    base = rates_panel[rates_panel["horizon_days"].eq(60) & rates_panel["product"].isin(["TF", "T"])].copy()
    if base.empty:
        return pd.DataFrame(columns=["date", "spread", "spread_z", "direction", "abs_z"])
    base["date"] = pd.to_datetime(base["date"], errors="coerce").dt.normalize()
    nav = base.pivot_table(index="date", columns="product", values="adjusted_nav", aggfunc="last").sort_index()
    if "TF" not in nav.columns or "T" not in nav.columns:
        return pd.DataFrame(columns=["date", "spread", "spread_z", "direction", "abs_z"])
    spread = 2.0 * np.log(nav["TF"].replace(0.0, np.nan)) - np.log(nav["T"].replace(0.0, np.nan))
    prior = spread.shift(1)
    mean = spread.rolling(LOOKBACK_DAYS, min_periods=LOOKBACK_DAYS).mean().shift(1)
    std = spread.rolling(LOOKBACK_DAYS, min_periods=LOOKBACK_DAYS).std(ddof=1).shift(1)
    z = (prior - mean) / std.replace(0.0, np.nan)
    result = pd.DataFrame({"date": z.index, "spread": prior.to_numpy(dtype=float), "spread_z": z.to_numpy(dtype=float)})
    result["direction"] = np.where(result["spread_z"].ge(ENTRY_Z), -1, np.where(result["spread_z"].le(-ENTRY_Z), 1, 0))
    result["abs_z"] = result["spread_z"].abs()
    return result.dropna(subset=["date", "spread_z"]).sort_values("date")


def _simulate_curve_overlay(
    window_name: str,
    window_frame: pd.DataFrame,
    margin_frame: pd.DataFrame,
    xsmom_satellite: pd.DataFrame,
    rates_panel: pd.DataFrame,
    curve_features: pd.DataFrame,
) -> pd.DataFrame:
    start = pd.Timestamp(window_frame["date"].min()).normalize()
    end = pd.Timestamp(window_frame["date"].max()).normalize()
    trading_dates = (
        pd.to_datetime(window_frame["date"], errors="coerce")
        .dropna()
        .dt.normalize()
        .drop_duplicates()
        .sort_values()
    )
    rates = rates_panel[
        rates_panel["horizon_days"].eq(60)
        & rates_panel["product"].isin(["TF", "T"])
        & rates_panel["date"].between(start, end)
    ].copy()
    if rates.empty:
        return s405._empty_overlay(window_name, CURVE_VARIANT)
    rates["date"] = pd.to_datetime(rates["date"], errors="coerce").dt.normalize()
    rate_by_date_product = {(row.date, row.product): row for row in rates.itertuples(index=False)}
    contract_to_product = (
        rates.drop_duplicates(["date", "main_contract_vt"])
        .set_index(["date", "main_contract_vt"])["product"]
        .to_dict()
    )
    feature_by_date = {
        row.date: row for row in curve_features[curve_features["date"].between(start, end)].itertuples(index=False)
    }
    c3_pnl_by_date = window_frame.set_index("date")["c3_net_pnl"].astype(float).to_dict()
    c3_margin_by_date = margin_frame.set_index("date")["c3_margin"].astype(float).to_dict()
    xsmom = xsmom_satellite.copy()
    if xsmom.empty:
        xsmom_by_date: dict[pd.Timestamp, dict[str, float]] = {}
    else:
        xsmom["date"] = pd.to_datetime(xsmom["date"], errors="coerce").dt.normalize()
        xsmom_by_date = {
            row.date: {
                "pnl": _safe_float(getattr(row, "satellite_daily_pnl", 0.0)),
                "margin": _safe_float(getattr(row, "satellite_margin", 0.0)),
            }
            for row in xsmom.itertuples(index=False)
        }

    prev_positions: dict[str, int] = {}
    prev_contract_specs: dict[str, float] = {}
    prev_equity = ACCOUNT_CAPITAL
    rows: list[dict[str, Any]] = []
    for date in trading_dates:
        date = pd.Timestamp(date).normalize()
        feature = feature_by_date.get(date)
        direction = int(getattr(feature, "direction", 0)) if feature is not None else 0
        product_targets: dict[str, int] = {}
        if direction != 0:
            product_targets = {"TF": 2 * direction, "T": -1 * direction}

        targets: dict[str, int] = {}
        proposed_margin = 0.0
        desired_signal_count = 0
        for product, lots in product_targets.items():
            rate_row = rate_by_date_product.get((date, product))
            if rate_row is None or lots == 0:
                continue
            contract = str(getattr(rate_row, "main_contract_vt", ""))
            margin = _safe_float(getattr(rate_row, "margin_per_contract", 0.0))
            if not contract or margin <= 0.0:
                continue
            targets[contract] = targets.get(contract, 0) + int(lots)
            proposed_margin += abs(int(lots)) * margin
            desired_signal_count = 1

        x_state = xsmom_by_date.get(date, {"pnl": 0.0, "margin": 0.0})
        base_margin = float(c3_margin_by_date.get(date, 0.0)) + float(x_state["margin"])
        margin_gate_skipped = int(bool(targets) and (base_margin + proposed_margin) * BROKER10_MULTIPLIER > prev_equity)
        if margin_gate_skipped:
            targets = {}
            proposed_margin = 0.0

        pnl = 0.0
        for contract, lots in targets.items():
            product = contract_to_product.get((date, contract))
            rate_row = rate_by_date_product.get((date, product)) if product else None
            if rate_row is None:
                continue
            close = _safe_float(getattr(rate_row, "close", 0.0))
            product_return = _safe_float(getattr(rate_row, "product_return", 0.0))
            quote_multiplier = _safe_float(getattr(rate_row, "quote_multiplier", 0.0))
            if close <= 0.0 or product_return <= -0.999999 or quote_multiplier <= 0.0:
                continue
            prev_close = close / (1.0 + product_return) if abs(product_return) > 1e-12 else close
            pnl += int(lots) * prev_close * product_return * quote_multiplier

        turnover = 0
        slippage_cost = 0.0
        current_contract_specs: dict[str, float] = {}
        for contract in targets:
            product = contract_to_product.get((date, contract))
            rate_row = rate_by_date_product.get((date, product)) if product else None
            if rate_row is not None:
                current_contract_specs[contract] = _safe_float(getattr(rate_row, "tick_value", 0.0))
        for contract in set(prev_positions) | set(targets):
            delta = abs(targets.get(contract, 0) - prev_positions.get(contract, 0))
            if delta <= 0:
                continue
            turnover += delta
            slippage_cost += delta * current_contract_specs.get(contract, prev_contract_specs.get(contract, 0.0))

        overlay_pnl = pnl - slippage_cost
        rows.append(
            {
                "date": date,
                "window_name": window_name,
                "variant": CURVE_VARIANT,
                "overlay_daily_pnl": overlay_pnl,
                "overlay_slippage_cost": slippage_cost,
                "overlay_margin": proposed_margin,
                "overlay_turnover_contracts": turnover,
                "overlay_held_contract_count": len([value for value in targets.values() if value != 0]),
                "overlay_desired_product_count": desired_signal_count,
                "overlay_rebalance": 1,
                "overlay_margin_gate_skipped": margin_gate_skipped,
                "curve_spread_z": _safe_float(getattr(feature, "spread_z", np.nan), np.nan) if feature is not None else np.nan,
                "curve_direction": direction,
            }
        )
        prev_positions = targets
        prev_contract_specs = current_contract_specs
        prev_equity += float(c3_pnl_by_date.get(date, 0.0)) + float(x_state["pnl"]) + overlay_pnl

    return pd.DataFrame(rows)


def _plot(daily: pd.DataFrame, overlay: pd.DataFrame, horizon: pd.DataFrame, gate: pd.DataFrame) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:  # pragma: no cover
        print(f"[stage429] skip chart: {exc}", flush=True)
        return

    variants = [spec.variant for spec in VARIANTS]
    labels = [v.replace("stage103_plus_", "+").replace("_guard", "") for v in variants]
    full = daily[daily["window_name"].eq("start_2020")]
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    for variant, frame in full.groupby("variant", sort=False):
        frame = frame.sort_values("date")
        nav = pd.Series(frame["equity"].to_numpy(dtype=float), index=pd.to_datetime(frame["date"])) / ACCOUNT_CAPITAL
        axes[0, 0].plot(nav.index, nav, label=variant, linewidth=1.05)
        axes[1, 0].plot(nav.index, (nav / nav.cummax() - 1.0) * 100.0, label=variant, linewidth=0.95)
    axes[0, 0].set_title("Full-period NAV")
    axes[0, 0].set_ylabel("NAV")
    axes[0, 0].legend(fontsize=7)
    axes[1, 0].set_title("Drawdown")
    axes[1, 0].set_ylabel("Drawdown %")
    axes[1, 0].axhline(-30.0, color="red", linestyle="--", linewidth=1.0)
    axes[1, 0].legend(fontsize=7)

    x = np.arange(len(variants))
    width = 0.36
    h90 = horizon[horizon["horizon_days"].eq(90)].set_index("variant").reindex(variants)
    h180 = horizon[horizon["horizon_days"].eq(180)].set_index("variant").reindex(variants)
    axes[0, 1].bar(x - width / 2, h90["return_p05_pct"].to_numpy(dtype=float), width, label="90d p05")
    axes[0, 1].bar(x + width / 2, h180["return_p05_pct"].to_numpy(dtype=float), width, label="180d p05")
    axes[0, 1].axhline(0.0, color="#333333", linewidth=0.8)
    axes[0, 1].set_title("Forward holding return left tail")
    axes[0, 1].set_ylabel("Return p05 %")
    axes[0, 1].set_xticks(x)
    axes[0, 1].set_xticklabels(labels, rotation=25, ha="right", fontsize=7)
    axes[0, 1].legend(fontsize=8)

    full_overlay = overlay[overlay["window_name"].eq("start_2020")].sort_values("date")
    if not full_overlay.empty:
        axes[1, 1].plot(
            pd.to_datetime(full_overlay["date"]),
            full_overlay["overlay_daily_pnl"].cumsum(),
            label="curve overlay cumulative PnL",
            linewidth=1.0,
        )
        axes[1, 1].legend(fontsize=8)
    axes[1, 1].set_title("TF/T curve overlay cumulative PnL")
    axes[1, 1].set_ylabel("CNY")
    fig.suptitle("Stage129 CFFEX TF/T curve spread overlay", fontsize=14)
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
    bad_windows: pd.DataFrame,
    gate: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    report = [
        "# Stage129 Stage103中金所TF/T曲线价差Overlay审计",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：固定低自由度利率曲线相对价值风险源；不改C3、Stage079、Stage103交易规则。",
        f"- 固定参数：`LOOKBACK_DAYS={LOOKBACK_DAYS}`，`ENTRY_Z={ENTRY_Z}`，`TF:T=2:1`，`BROKER10_MULTIPLIER={BROKER10_MULTIPLIER}`。",
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
        _md_table(score[["variant", "horizon_days", "experience_score", "score_90d", "score_180d", "short_holding_score", "improved_metric_count"]]),
        "",
        "## 多起点",
        "",
        _md_table(
            fresh[
                [
                    "window_name",
                    "variant",
                    "total_return_pct",
                    "max_dd_pct",
                    "dd30_pass",
                    "overlay_turnover",
                    "max_overlay_margin",
                    "overlay_gate_skipped_days",
                    "broker10_max_margin_to_equity_pct",
                    "broker10_reject_days",
                ]
            ],
            max_rows=120,
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
                    "stage079_max_dd_pct",
                    "stage103_max_dd_pct",
                    "not_worse_than_stage079_stress",
                    "not_worse_than_stage103_stress",
                ]
            ]
        ),
        "",
        "## Stage104底部5%坏窗口贡献",
        "",
        _md_table(bad_windows),
        "",
        "## 晋级闸门",
        "",
        _md_table(
            gate[
                [
                    "variant",
                    "metric_hard_pass_stage079",
                    "metric_incremental_pass_stage103",
                    "target_pass_3m6m_vs_stage079",
                    "short_score_not_lower_than_stage103",
                    "bad_window_not_worse_than_stage103",
                    "research_promotion_pass",
                    "execution_relative_pass",
                    "deployment_absolute_margin_pass",
                    "score_90d",
                    "score_180d",
                    "objective_improved_8_count_90d",
                    "objective_improved_8_count_180d",
                    "failed_stage079_metric_checks",
                    "failed_stage103_incremental_checks",
                ]
            ]
        ),
        "",
        "## 反过拟合说明",
        "",
        "- 只测试一个预声明曲线价差：TF/T，固定2:1，固定120日z-score，固定1倍阈值。",
        "- 不按结果扫描TF/T比例、窗口、阈值、单边国债动量或TS/TL组合。",
        "- 若不能通过Stage079硬闸门和Stage103增量闸门，本形状停止。",
    ]
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    old_variants = s405.VARIANTS
    s405.VARIANTS = VARIANTS
    try:
        combo = s402._load_combo_daily()
        margin = s402._load_margin()
        full_frame = combo[combo["window_name"].eq("start_2020")].sort_values("date").drop_duplicates("date", keep="last")
        scale_by_date = s402._build_stage101_scale(full_frame)
        price_frame = s402._build_price_frame()
        price_frame["date"] = pd.to_datetime(price_frame["date"], errors="coerce").dt.normalize()
        signals = s402._load_signal_daily()
        signals["date"] = pd.to_datetime(signals["date"], errors="coerce").dt.normalize()
        rates_panel = s407._build_rates_panel()
        rates_panel["date"] = pd.to_datetime(rates_panel["date"], errors="coerce").dt.normalize()
        curve_features = _build_curve_features(rates_panel)

        xsmom_by_window: dict[str, pd.DataFrame] = {}
        overlay_by_window_variant: dict[tuple[str, str], pd.DataFrame] = {}
        daily_by_window_variant: dict[tuple[str, str], pd.DataFrame] = {}
        overlay_full_by_variant: dict[str, pd.DataFrame] = {}
        candidates: list[Any] = []
        full_daily_parts: list[pd.DataFrame] = []
        overlay_parts: list[pd.DataFrame] = []

        for window_name, frame in combo.groupby("window_name", sort=True):
            frame = frame.sort_values("date").drop_duplicates("date", keep="last")
            margin_frame = margin[margin["window_name"].eq(window_name)].sort_values("date").drop_duplicates("date", keep="last")
            xsmom = s403._simulate_guarded_round_half(window_name, frame, margin_frame, price_frame, signals, scale_by_date)
            xsmom_by_window[window_name] = xsmom
            for spec in VARIANTS:
                if spec.variant in {BASELINE_VARIANT, STAGE103_VARIANT}:
                    overlay = s405._empty_overlay(window_name, spec.variant)
                else:
                    overlay = _simulate_curve_overlay(window_name, frame, margin_frame, xsmom, rates_panel, curve_features)
                    overlay_parts.append(overlay)
                overlay_by_window_variant[(window_name, spec.variant)] = overlay
                use_xsmom = s405._empty_xsmom(window_name) if spec.variant == BASELINE_VARIANT else xsmom
                daily = s405._combine_daily(frame, use_xsmom, overlay, spec.variant, 1.0)
                daily["window_name"] = window_name
                daily_by_window_variant[(window_name, spec.variant)] = daily
                if window_name == "start_2020":
                    overlay_full_by_variant[spec.variant] = overlay

        for spec in VARIANTS:
            daily = daily_by_window_variant[("start_2020", spec.variant)]
            full_daily_parts.append(daily)
            equity = s402._calendarize(pd.Series(daily["equity"].to_numpy(dtype=float), index=daily["date"]))
            candidates.append(s405._candidate(spec, equity))

        full_daily = pd.concat(full_daily_parts, ignore_index=True)
        overlay_all = pd.concat(overlay_parts, ignore_index=True) if overlay_parts else pd.DataFrame()
        summary = pd.DataFrame([s402.s087._stats(candidate) for candidate in candidates])
        horizon = pd.DataFrame(
            [s402.s087._horizon_metrics(candidate, days) for candidate in candidates for days in (90, 180)]
        )
        score = s402.s087._score_horizons(horizon)
        margin_audit = s405._margin_audit(combo, margin, xsmom_by_window, overlay_by_window_variant, daily_by_window_variant)
        fresh = s405._fresh_start(combo, xsmom_by_window, overlay_by_window_variant, daily_by_window_variant, margin_audit)
        cost = s405._cost_stress(full_frame, xsmom_by_window["start_2020"], overlay_full_by_variant)
        bad_windows = s405._bad_window_contribution(
            {spec.variant: daily_by_window_variant[("start_2020", spec.variant)] for spec in VARIANTS}
        )
        gate = s405._gate(summary, horizon, score, cost, fresh, margin_audit, bad_windows)
    finally:
        s405.VARIANTS = old_variants

    execution_ready = gate[gate["execution_relative_pass"].eq(1) & gate["variant"].eq(CURVE_VARIANT)]
    research_ready = gate[gate["research_promotion_pass"].eq(1) & gate["variant"].eq(CURVE_VARIANT)]
    decision = {
        "stage": "Stage129",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": "stage103_upgrade_candidate"
        if len(execution_ready)
        else ("research_candidate_only" if len(research_ready) else "no_new_promotion"),
        "stage103_upgrade_variants": execution_ready["variant"].tolist(),
        "research_ready_variants": research_ready["variant"].tolist(),
        "best_by_gate": str(gate.iloc[0]["variant"]) if not gate.empty else "",
        "chart": str(CHART_PATH),
        "judgement": "TF/T曲线价差若不能在固定2:1、固定120日z-score、固定1阈值和10%保证金缓冲下通过，不继续扫参救援。",
    }

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon.to_csv(HORIZON_PATH, index=False, encoding="utf-8-sig")
    score.to_csv(SCORE_PATH, index=False, encoding="utf-8-sig")
    fresh.to_csv(FRESH_START_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    margin_audit.to_csv(MARGIN_AUDIT_PATH, index=False, encoding="utf-8-sig")
    bad_windows.to_csv(BAD_WINDOW_PATH, index=False, encoding="utf-8-sig")
    gate.to_csv(GATE_PATH, index=False, encoding="utf-8-sig")
    full_daily.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    overlay_all.to_csv(OVERLAY_PATH, index=False, encoding="utf-8-sig")
    curve_features.to_csv(FEATURE_PATH, index=False, encoding="utf-8-sig")
    rates_panel.to_csv(RATES_PANEL_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _plot(full_daily, overlay_all, horizon, gate)
    _write_report(summary, horizon, score, fresh, cost, margin_audit, bad_windows, gate, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"[stage429] report={REPORT_PATH}")
    print(f"[stage429] chart={CHART_PATH}")


if __name__ == "__main__":
    main()
