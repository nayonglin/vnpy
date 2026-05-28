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
import analyze_qmt_roll_stage381_financial_futures_low_corr_carrier_screen as s381  # noqa: E402
import analyze_qmt_roll_stage402_stage079_xsmom_volmanaged_true_integer as s402  # noqa: E402
import analyze_qmt_roll_stage403_stage079_xsmom_execution_margin_audit as s403  # noqa: E402
import analyze_qmt_roll_stage405_stage079_reversal_protection_scout as s405  # noqa: E402


MODEL_TAG = "stage407_stage079_cffex_rates_true_overlay_v2"
OUTPUT_PREFIX = "qmt_roll_stage407_stage079_cffex_rates_true_overlay"
LINE_ID = "futures_trend_drawdown30_preserve_return"

BASELINE_VARIANT = s405.BASELINE_VARIANT
STAGE103_VARIANT = s405.STAGE103_VARIANT
ACCOUNT_CAPITAL = s405.ACCOUNT_CAPITAL
BROKER10_MULTIPLIER = s405.BROKER10_MULTIPLIER

RATE_PRODUCTS = ("TS", "TF", "T", "TL")
RATE_PRODUCT_SPECS = {
    "TS": {"face_value": 2_000_000.0, "margin_ratio": 0.005, "tick_size": 0.005},
    "TF": {"face_value": 1_000_000.0, "margin_ratio": 0.010, "tick_size": 0.005},
    "T": {"face_value": 1_000_000.0, "margin_ratio": 0.020, "tick_size": 0.005},
    "TL": {"face_value": 1_000_000.0, "margin_ratio": 0.035, "tick_size": 0.010},
}
TS_TICK_CHANGE_DATE = pd.Timestamp("2023-11-07")
TS_TICK_SIZE_AFTER_CHANGE = 0.002

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
        "当前最强执行相对候选。",
    ),
    s405.VariantSpec(
        "stage103_plus_cffex_rates_tsmom60_min1_guard",
        "C1 Stage103+中金所国债60日动量真实一手",
        "rates_true_overlay",
        "rates_tsmom",
        60,
        0,
        0,
        "TS/TF/T/TL 四个国债期货主力合约按60日时间序列动量，各品种最多1手，并受1.10倍保证金闸门约束。",
    ),
    s405.VariantSpec(
        "stage103_plus_cffex_rates_tsmom120_min1_guard",
        "C2 Stage103+中金所国债120日动量真实一手",
        "rates_true_overlay",
        "rates_tsmom",
        120,
        0,
        0,
        "TS/TF/T/TL 四个国债期货主力合约按120日时间序列动量，各品种最多1手，并受1.10倍保证金闸门约束。",
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


def _build_rates_panel() -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for product in RATE_PRODUCTS:
        series = s381._build_main_product_series(product)
        if series.empty:
            continue
        spec = RATE_PRODUCT_SPECS[product]
        series = series.copy()
        series["face_value"] = spec["face_value"]
        series["quote_multiplier"] = spec["face_value"] / 100.0
        series["margin_ratio"] = spec["margin_ratio"]
        series["tick_size"] = spec["tick_size"]
        if product == "TS":
            trade_dates = pd.to_datetime(series["date"], errors="coerce").dt.normalize()
            series["tick_size"] = np.where(
                trade_dates.ge(TS_TICK_CHANGE_DATE),
                TS_TICK_SIZE_AFTER_CHANGE,
                spec["tick_size"],
            )
        series["tick_value"] = series["tick_size"] * spec["face_value"] / 100.0
        series["contract_value"] = pd.to_numeric(series["close"], errors="coerce") * series["quote_multiplier"]
        series["margin_per_contract"] = series["contract_value"] * series["margin_ratio"]
        for horizon in (60, 120):
            part = series.copy()
            momentum = part["adjusted_nav"] / part["adjusted_nav"].shift(horizon) - 1.0
            signal = np.sign(momentum).replace([np.inf, -np.inf], np.nan).fillna(0.0)
            part["horizon_days"] = horizon
            part["position"] = signal.shift(1).fillna(0.0)
            frames.append(part)
    if not frames:
        return pd.DataFrame()
    panel = pd.concat(frames, ignore_index=True)
    panel["date"] = pd.to_datetime(panel["date"], errors="coerce").dt.normalize()
    numeric_cols = [
        "close",
        "product_return",
        "adjusted_nav",
        "face_value",
        "quote_multiplier",
        "margin_ratio",
        "tick_size",
        "tick_value",
        "contract_value",
        "margin_per_contract",
        "position",
    ]
    for col in numeric_cols:
        panel[col] = pd.to_numeric(panel[col], errors="coerce").fillna(0.0)
    return panel.dropna(subset=["date"]).sort_values(["horizon_days", "product", "date"])


def _simulate_rates_overlay(
    spec: s405.VariantSpec,
    window_name: str,
    window_frame: pd.DataFrame,
    margin_frame: pd.DataFrame,
    xsmom_sat: pd.DataFrame,
    rates_panel: pd.DataFrame,
) -> pd.DataFrame:
    if spec.direction != "rates_tsmom":
        return s405._empty_overlay(window_name, spec.variant)

    start = window_frame["date"].min()
    end = window_frame["date"].max()
    rates = rates_panel[
        rates_panel["horizon_days"].eq(spec.lookback_days) & rates_panel["date"].between(start, end)
    ].copy()
    if rates.empty:
        return s405._empty_overlay(window_name, spec.variant)

    c3_pnl = window_frame.set_index("date")["c3_net_pnl"].astype(float).to_dict()
    c3_margin = margin_frame.set_index("date")["c3_margin"].astype(float).to_dict()
    xsmom_by_date = xsmom_sat.set_index("date") if not xsmom_sat.empty else pd.DataFrame()
    xsmom_pnl = xsmom_by_date.get("satellite_daily_pnl", pd.Series(dtype=float)).astype(float).to_dict()
    xsmom_margin = xsmom_by_date.get("satellite_margin", pd.Series(dtype=float)).astype(float).to_dict()
    by_date: dict[pd.Timestamp, list[Any]] = {}
    for row in rates.itertuples(index=False):
        by_date.setdefault(pd.Timestamp(row.date).normalize(), []).append(row)

    prev_positions: dict[str, int] = {}
    prev_contract_specs: dict[str, tuple[str, float]] = {}
    rows: list[dict[str, Any]] = []
    prev_equity = ACCOUNT_CAPITAL

    for date in window_frame["date"].sort_values():
        date = pd.Timestamp(date).normalize()
        targets: dict[str, int] = {}
        contract_specs: dict[str, tuple[str, float]] = {}
        desired_count = 0
        proposed_margin = 0.0
        pnl = 0.0
        for rate_row in by_date.get(date, []):
            lots = int(np.sign(float(getattr(rate_row, "position", 0.0))))
            if lots == 0:
                continue
            contract = str(getattr(rate_row, "main_contract_vt", ""))
            if not contract:
                continue
            margin_per_contract = float(getattr(rate_row, "margin_per_contract", 0.0))
            if margin_per_contract <= 0.0:
                continue
            desired_count += 1
            targets[contract] = lots
            contract_specs[contract] = (str(getattr(rate_row, "product", "")), float(getattr(rate_row, "tick_value", 0.0)))
            proposed_margin += margin_per_contract
            close = float(getattr(rate_row, "close", 0.0))
            product_return = float(getattr(rate_row, "product_return", 0.0))
            if product_return <= -0.999999 or close <= 0.0:
                continue
            prev_close = close / (1.0 + product_return) if abs(product_return) > 1e-12 else close
            pnl += lots * prev_close * product_return * float(getattr(rate_row, "quote_multiplier", 0.0))

        required_margin = (
            float(c3_margin.get(date, 0.0)) + float(xsmom_margin.get(date, 0.0)) + proposed_margin
        ) * BROKER10_MULTIPLIER
        margin_gate_skipped = int(bool(targets) and required_margin > prev_equity)
        if margin_gate_skipped:
            targets = {}
            contract_specs = {}
            proposed_margin = 0.0
            pnl = 0.0

        turnover = 0
        slippage_cost = 0.0
        for contract in set(prev_positions) | set(targets):
            delta = abs(targets.get(contract, 0) - prev_positions.get(contract, 0))
            if delta <= 0:
                continue
            turnover += delta
            _product, tick_value = contract_specs.get(contract, prev_contract_specs.get(contract, ("", 0.0)))
            slippage_cost += delta * tick_value

        overlay_daily_pnl = pnl - slippage_cost
        rows.append(
            {
                "date": date,
                "window_name": window_name,
                "variant": spec.variant,
                "overlay_daily_pnl": overlay_daily_pnl,
                "overlay_slippage_cost": slippage_cost,
                "overlay_margin": proposed_margin,
                "overlay_turnover_contracts": turnover,
                "overlay_held_contract_count": len(targets),
                "overlay_desired_product_count": desired_count,
                "overlay_rebalance": 1,
                "overlay_margin_gate_skipped": margin_gate_skipped,
            }
        )
        prev_positions = targets
        prev_contract_specs = contract_specs
        prev_equity += float(c3_pnl.get(date, 0.0)) + float(xsmom_pnl.get(date, 0.0)) + overlay_daily_pnl

    return pd.DataFrame(rows)


def _plot(daily: pd.DataFrame, horizon: pd.DataFrame, cost: pd.DataFrame, gate: pd.DataFrame) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:  # pragma: no cover
        print(f"[stage407] skip chart: {exc}", flush=True)
        return
    variants = [spec.variant for spec in VARIANTS]
    labels = [
        spec.variant.replace("stage103_plus_cffex_", "+").replace("_min1_guard", "").replace("_", "\n")
        for spec in VARIANTS
    ]
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

    c5 = cost[cost["slippage_multiplier"].eq(5.0)].set_index("variant").reindex(variants)
    axes[1, 1].bar(x, c5["max_dd_pct"].to_numpy(dtype=float), color="#9ecae1")
    axes[1, 1].axhline(-30.0, color="red", linestyle="--", linewidth=1.0)
    axes[1, 1].set_title("5x slippage stress max drawdown")
    axes[1, 1].set_ylabel("Max DD %")
    axes[1, 1].set_xticks(x)
    axes[1, 1].set_xticklabels(labels, rotation=25, ha="right", fontsize=7)
    fig.suptitle("Stage107 CFFEX rates true overlay", fontsize=14)
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
        "# Stage107 Stage079中金所国债真实一手Overlay",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：不同资产风险源真实整数手 scout；不改 C3/Stage079 规则，不增加账户资金。",
        "- A/B/C：A=Stage079；C0=Stage103；C1=Stage103+国债60日动量真实一手；C2=Stage103+国债120日动量真实一手。",
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
        "## Stage104底部5%坏窗口贡献",
        "",
        _md_table(bad_windows),
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
                    "overlay_turnover",
                    "overlay_gate_skipped_days",
                    "broker10_max_margin_to_equity_pct",
                    "broker10_reject_days",
                ]
            ],
            max_rows=90,
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
        "## 合约与反过拟合说明",
        "",
        "- 国债期货合约乘数按中金所合约面值计算：TS为200万面值，TF/T/TL为100万面值；保证金按交易所最低比例并在组合闸门中再乘 `1.10`。",
        "- 合约规格按公开资料校正：TF最低保证金用 `1%`；TS最小变动价位在 `2023-11-07` 起由 `0.005` 切换为 `0.002`。",
        "- 只测试 Stage081 已出现但未落地的国债60日/120日动量真实一手形状；不按结果挑单个合约、调保证金小数、调窗口或调品种组合。",
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
        rates_panel = _build_rates_panel()

        xsmom_by_window: dict[str, pd.DataFrame] = {}
        overlay_by_window_variant: dict[tuple[str, str], pd.DataFrame] = {}
        daily_by_window_variant: dict[tuple[str, str], pd.DataFrame] = {}
        overlay_full_by_variant: dict[str, pd.DataFrame] = {}
        candidates: list[Any] = []
        full_daily_parts: list[pd.DataFrame] = []

        for window_name, frame in combo.groupby("window_name", sort=True):
            frame = frame.sort_values("date").drop_duplicates("date", keep="last")
            margin_frame = margin[margin["window_name"].eq(window_name)].sort_values("date").drop_duplicates("date", keep="last")
            xsmom = s403._simulate_guarded_round_half(window_name, frame, margin_frame, price_frame, signals, scale_by_date)
            xsmom_by_window[window_name] = xsmom
            for spec in VARIANTS:
                if spec.variant in {BASELINE_VARIANT, STAGE103_VARIANT}:
                    overlay = s405._empty_overlay(window_name, spec.variant)
                else:
                    overlay = _simulate_rates_overlay(spec, window_name, frame, margin_frame, xsmom, rates_panel)
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
        overlay_all = pd.concat([frame for frame in overlay_by_window_variant.values() if not frame.empty], ignore_index=True)
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

    execution_ready = gate[gate["execution_relative_pass"].eq(1) & ~gate["variant"].isin([BASELINE_VARIANT, STAGE103_VARIANT])]
    research_ready = gate[gate["research_promotion_pass"].eq(1) & ~gate["variant"].isin([BASELINE_VARIANT, STAGE103_VARIANT])]
    best = gate.iloc[0] if not gate.empty else None
    decision = {
        "stage": "Stage107",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": "execution_relative_candidate"
        if len(execution_ready)
        else ("research_candidate_only" if len(research_ready) else "no_new_promotion"),
        "execution_relative_ready_variants": execution_ready["variant"].tolist(),
        "research_ready_variants": research_ready["variant"].tolist(),
        "best_by_gate_order": str(best["variant"]) if best is not None else "",
        "chart": str(CHART_PATH),
        "judgement": "若国债真实一手overlay不能同时通过Stage079硬闸门、Stage103增量不劣化、坏窗口和成本/保证金约束，则不晋级。",
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
    rates_panel.to_csv(RATES_PANEL_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _plot(full_daily, horizon, cost, gate)
    _write_report(summary, horizon, score, fresh, cost, margin_audit, bad_windows, gate, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"report={REPORT_PATH}")


if __name__ == "__main__":
    main()
