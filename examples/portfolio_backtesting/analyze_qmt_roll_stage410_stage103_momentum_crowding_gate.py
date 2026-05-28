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


MODEL_TAG = "stage410_stage103_momentum_crowding_gate_v1"
OUTPUT_PREFIX = "qmt_roll_stage410_stage103_momentum_crowding_gate"
LINE_ID = "futures_trend_drawdown30_preserve_return"

BASELINE_VARIANT = s405.BASELINE_VARIANT
STAGE103_VARIANT = s405.STAGE103_VARIANT
ACCOUNT_CAPITAL = s405.ACCOUNT_CAPITAL
BROKER10_MULTIPLIER = s405.BROKER10_MULTIPLIER

HOT20_THRESHOLD = 0.50
HOT60_THRESHOLD = 0.75

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
        "stage103_plus_mom60_weekly_min1_guard",
        "C1 Stage103+60日商品动量周频",
        "positive_control",
        "momentum",
        60,
        3,
        5,
        "Stage106强收益但冷启动失败的商品横截面动量袖子，作为未加拥挤闸门对照。",
    ),
    s405.VariantSpec(
        "stage103_plus_mom60_weekly_hot_crowding_gate",
        "C2 Stage103+60日商品动量周频+急涨拥挤闸门",
        "momentum_crowding_gate_scout",
        "momentum",
        60,
        3,
        5,
        "固定规则：若上一交易日可知的Stage079权益20日涨幅>50%或60日涨幅>75%，则当日不叠加第二个商品动量袖子。",
    ),
    s405.VariantSpec(
        "stage103_plus_mom120_monthly_hot_crowding_gate",
        "C3 Stage103+120日商品动量月频+急涨拥挤闸门",
        "momentum_crowding_gate_scout",
        "momentum",
        120,
        3,
        20,
        "同一急涨拥挤闸门，但用120日排序、20交易日换仓，检验低换手长期商品动量是否更稳。",
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


def _hot_gate_by_date(window_frame: pd.DataFrame) -> dict[pd.Timestamp, int]:
    frame = window_frame.sort_values("date").drop_duplicates("date", keep="last").copy()
    frame["stage079_equity"] = ACCOUNT_CAPITAL + frame["c3_net_pnl"].astype(float).cumsum()
    known_equity = frame["stage079_equity"].shift(1)
    hot20 = known_equity / known_equity.shift(20) - 1.0
    hot60 = known_equity / known_equity.shift(60) - 1.0
    gate = ((hot20 > HOT20_THRESHOLD) | (hot60 > HOT60_THRESHOLD)).fillna(False).astype(int)
    return {pd.Timestamp(date).normalize(): int(value) for date, value in zip(frame["date"], gate)}


def _simulate_overlay_with_hot_gate(
    spec: s405.VariantSpec,
    window_name: str,
    window_frame: pd.DataFrame,
    margin_frame: pd.DataFrame,
    xsmom_sat: pd.DataFrame,
    price_frame: pd.DataFrame,
    rank_table: pd.DataFrame | None,
) -> pd.DataFrame:
    if spec.direction == "none" or rank_table is None:
        return s405._empty_overlay(window_name, spec.variant)

    start = window_frame["date"].min()
    end = window_frame["date"].max()
    window_prices = price_frame[price_frame["date"].between(start, end)].copy()
    if window_prices.empty:
        return s405._empty_overlay(window_name, spec.variant)

    c3_pnl = window_frame.set_index("date")["c3_net_pnl"].astype(float).to_dict()
    c3_margin = margin_frame.set_index("date")["c3_margin"].astype(float).to_dict()
    xsmom_by_date = (
        xsmom_sat.set_index("date")
        if not xsmom_sat.empty
        else pd.DataFrame(columns=["satellite_daily_pnl", "satellite_margin"])
    )
    xsmom_pnl = xsmom_by_date.get("satellite_daily_pnl", pd.Series(dtype=float)).astype(float).to_dict()
    xsmom_margin = xsmom_by_date.get("satellite_margin", pd.Series(dtype=float)).astype(float).to_dict()
    hot_gate = _hot_gate_by_date(window_frame)

    price_by_date_product = {
        (row.date, row.product_vt_symbol): row for row in window_prices.itertuples(index=False)
    }
    date_prices: dict[pd.Timestamp, dict[str, Any]] = {}
    for row in window_prices.itertuples(index=False):
        date_prices.setdefault(pd.Timestamp(row.date).normalize(), {})[str(row.product_vt_symbol)] = row

    prev_contract_positions: dict[str, int] = {}
    prev_contract_product: dict[str, str] = {}
    product_targets: dict[str, int] = {}
    rows: list[dict[str, Any]] = []
    prev_equity = ACCOUNT_CAPITAL
    trading_dates = list(window_frame["date"].sort_values())

    for day_idx, date in enumerate(trading_dates):
        date = pd.Timestamp(date).normalize()
        prices = date_prices.get(date, {})
        rebalance = int(day_idx % spec.rebalance_every == 0)
        if rebalance:
            product_targets = s405._select_products(rank_table.loc[date], prices, spec) if date in rank_table.index else {}

        hot_gate_skipped = int(bool(product_targets) and bool(hot_gate.get(date, 0)))
        targets: dict[str, int] = {}
        contract_product: dict[str, str] = {}
        proposed_margin = 0.0
        if not hot_gate_skipped:
            for product, direction in product_targets.items():
                price_row = prices.get(product)
                if price_row is None:
                    continue
                contract = str(getattr(price_row, "main_contract_vt", ""))
                margin = s402._safe_float(getattr(price_row, "margin_per_contract", 0.0))
                if not contract or margin <= 0.0:
                    continue
                targets[contract] = int(direction)
                contract_product[contract] = product
                proposed_margin += margin

        required_margin = (
            float(c3_margin.get(date, 0.0)) + float(xsmom_margin.get(date, 0.0)) + proposed_margin
        ) * BROKER10_MULTIPLIER
        margin_gate_skipped = int(bool(targets) and required_margin > prev_equity)
        if margin_gate_skipped:
            targets = {}
            contract_product = {}
            proposed_margin = 0.0

        pnl = 0.0
        held_margin = 0.0
        for contract, lots in targets.items():
            product = contract_product.get(contract)
            price_row = price_by_date_product.get((date, product)) if product else None
            if price_row is None:
                continue
            pnl += lots * s402._safe_float(getattr(price_row, "prev_main_close", 0.0)) * s402._safe_float(
                getattr(price_row, "size", 1.0)
            ) * s402._safe_float(getattr(price_row, "product_return", 0.0))
            held_margin += abs(lots) * s402._safe_float(getattr(price_row, "margin_per_contract", 0.0))

        turnover = 0
        slippage_cost = 0.0
        for contract in set(prev_contract_positions) | set(targets):
            delta = abs(targets.get(contract, 0) - prev_contract_positions.get(contract, 0))
            if delta <= 0:
                continue
            turnover += delta
            product = contract_product.get(contract) or prev_contract_product.get(contract)
            price_row = price_by_date_product.get((date, product)) if product else None
            if price_row is not None:
                slippage_cost += delta * s402._safe_float(getattr(price_row, "slippage", 0.0)) * s402._safe_float(
                    getattr(price_row, "size", 1.0)
                )

        overlay_daily_pnl = pnl - slippage_cost
        rows.append(
            {
                "date": date,
                "window_name": window_name,
                "variant": spec.variant,
                "overlay_daily_pnl": overlay_daily_pnl,
                "overlay_slippage_cost": slippage_cost,
                "overlay_margin": held_margin,
                "overlay_turnover_contracts": turnover,
                "overlay_held_contract_count": len(targets),
                "overlay_desired_product_count": len(product_targets),
                "overlay_rebalance": rebalance,
                "overlay_margin_gate_skipped": margin_gate_skipped,
                "overlay_hot_gate_skipped": hot_gate_skipped,
            }
        )
        prev_contract_positions = targets
        prev_contract_product = contract_product
        prev_equity += float(c3_pnl.get(date, 0.0)) + float(xsmom_pnl.get(date, 0.0)) + overlay_daily_pnl

    return pd.DataFrame(rows)


def _plot(daily: pd.DataFrame, horizon: pd.DataFrame, gate: pd.DataFrame) -> None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:  # pragma: no cover
        print(f"[stage410] skip chart: {exc}", flush=True)
        return
    full = daily[daily["window_name"].eq("start_2020")]
    variants = [spec.variant for spec in VARIANTS]
    labels = [v.replace("stage103_plus_", "+").replace("_min1_guard", "").replace("_hot_crowding_gate", "+hot") for v in variants]
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    for variant, frame in full.groupby("variant", sort=False):
        frame = frame.sort_values("date")
        nav = pd.Series(frame["equity"].to_numpy(dtype=float), index=pd.to_datetime(frame["date"])) / ACCOUNT_CAPITAL
        axes[0, 0].plot(nav.index, nav, label=variant, linewidth=1.0)
        axes[1, 0].plot(nav.index, (nav / nav.cummax() - 1.0) * 100.0, label=variant, linewidth=0.9)
    axes[0, 0].set_title("Full-period NAV")
    axes[0, 0].legend(fontsize=7)
    axes[1, 0].set_title("Drawdown")
    axes[1, 0].axhline(-30.0, color="red", linestyle="--", linewidth=1.0)
    axes[1, 0].legend(fontsize=7)

    x = np.arange(len(variants))
    width = 0.35
    h90 = horizon[horizon["horizon_days"].eq(90)].set_index("variant").reindex(variants)
    h180 = horizon[horizon["horizon_days"].eq(180)].set_index("variant").reindex(variants)
    axes[0, 1].bar(x - width / 2, h90["return_p05_pct"].to_numpy(dtype=float), width, label="90d p05")
    axes[0, 1].bar(x + width / 2, h180["return_p05_pct"].to_numpy(dtype=float), width, label="180d p05")
    axes[0, 1].axhline(0.0, color="#333333", linewidth=0.8)
    axes[0, 1].set_title("Holding return left tail")
    axes[0, 1].set_ylabel("Return p05 %")
    axes[0, 1].set_xticks(x)
    axes[0, 1].set_xticklabels(labels, rotation=25, ha="right", fontsize=7)
    axes[0, 1].legend(fontsize=8)

    g = gate.set_index("variant").reindex(variants)
    axes[1, 1].bar(x - width / 2, g["score_90d"].to_numpy(dtype=float), width, label="90d score")
    axes[1, 1].bar(x + width / 2, g["score_180d"].to_numpy(dtype=float), width, label="180d score")
    axes[1, 1].axhline(110.0, color="red", linestyle="--", linewidth=1.0)
    axes[1, 1].set_title("Short holding score")
    axes[1, 1].set_xticks(x)
    axes[1, 1].set_xticklabels(labels, rotation=25, ha="right", fontsize=7)
    axes[1, 1].legend(fontsize=8)
    fig.suptitle("Stage110 momentum crowding gate scout", fontsize=14)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    horizon: pd.DataFrame,
    score: pd.DataFrame,
    fresh: pd.DataFrame,
    cost: pd.DataFrame,
    gate: pd.DataFrame,
    overlay: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    hot_gate_summary = (
        overlay.groupby("variant", dropna=False)
        .agg(
            hot_gate_days=("overlay_hot_gate_skipped", "sum"),
            overlay_turnover=("overlay_turnover_contracts", "sum"),
            overlay_slippage=("overlay_slippage_cost", "sum"),
            overlay_pnl=("overlay_daily_pnl", "sum"),
            max_overlay_margin=("overlay_margin", "max"),
        )
        .reset_index()
        if "overlay_hot_gate_skipped" in overlay.columns
        else pd.DataFrame()
    )
    report = [
        "# Stage110 Stage103商品动量拥挤闸门Scout",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：结构性风险叠加审计；固定 Stage103，不修改 C3 交易规则。",
        f"- 固定急涨闸门：上一交易日可知的Stage079权益20日涨幅>{HOT20_THRESHOLD:.0%}或60日涨幅>{HOT60_THRESHOLD:.0%}时，不叠加第二个商品动量袖子。",
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
        "## 体验评分与晋级闸门",
        "",
        _md_table(
            gate[
                [
                    "variant",
                    "metric_hard_pass_stage079",
                    "metric_incremental_pass_stage103",
                    "target_pass_3m6m_vs_stage079",
                    "research_promotion_pass",
                    "execution_relative_pass",
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
        "## 多起点冷启动",
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
        "## 急涨闸门与袖子归因",
        "",
        _md_table(hot_gate_summary),
        "",
        "## 反过拟合说明",
        "",
        "- 本阶段不扫描阈值，只复用 Stage090 已暴露但未能直接用于C3减仓的急涨状态，改为限制额外同类动量袖子的叠加。",
        "- 若仍失败，说明商品动量袖子的问题不是简单拥挤闸门能修复，后续不应继续围绕商品动量窗口、换手和急涨阈值救援。",
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
        ranks = s405._build_rank_tables(price_frame, {spec.lookback_days for spec in VARIANTS if spec.lookback_days > 0})
        signals = s402._load_signal_daily()
        signals["date"] = pd.to_datetime(signals["date"], errors="coerce").dt.normalize()

        xsmom_by_window: dict[str, pd.DataFrame] = {}
        overlay_by_window_variant: dict[tuple[str, str], pd.DataFrame] = {}
        daily_by_window_variant: dict[tuple[str, str], pd.DataFrame] = {}
        overlay_full_by_variant: dict[str, pd.DataFrame] = {}
        candidates: list[Any] = []
        full_daily_parts: list[pd.DataFrame] = []

        for window_name, frame in combo.groupby("window_name", sort=True):
            frame = frame.sort_values("date").drop_duplicates("date", keep="last")
            margin_frame = margin[margin["window_name"].eq(window_name)].sort_values("date").drop_duplicates(
                "date", keep="last"
            )
            xsmom = s403._simulate_guarded_round_half(window_name, frame, margin_frame, price_frame, signals, scale_by_date)
            xsmom_by_window[window_name] = xsmom
            for spec in VARIANTS:
                if spec.variant in {BASELINE_VARIANT, STAGE103_VARIANT}:
                    overlay = s405._empty_overlay(window_name, spec.variant)
                elif spec.variant == "stage103_plus_mom60_weekly_min1_guard":
                    overlay = s405._simulate_overlay(
                        spec, window_name, frame, margin_frame, xsmom, price_frame, ranks[spec.lookback_days]
                    )
                else:
                    overlay = _simulate_overlay_with_hot_gate(
                        spec, window_name, frame, margin_frame, xsmom, price_frame, ranks[spec.lookback_days]
                    )
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
    decision = {
        "stage": "Stage110",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": "execution_relative_candidate"
        if len(execution_ready)
        else ("research_candidate_only" if len(research_ready) else "no_new_promotion"),
        "execution_relative_ready_variants": execution_ready["variant"].tolist(),
        "research_ready_variants": research_ready["variant"].tolist(),
        "hot_gate": {
            "hot20_threshold": HOT20_THRESHOLD,
            "hot60_threshold": HOT60_THRESHOLD,
            "uses_only_prior_known_equity": True,
        },
        "judgement": "固定急涨拥挤闸门若无法让额外商品动量袖子通过Stage079/Stage103双重约束，则停止该路线。",
        "chart": str(CHART_PATH),
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
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _plot(full_daily, horizon, gate)
    _write_report(summary, horizon, score, fresh, cost, gate, overlay_all, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"report={REPORT_PATH}")


if __name__ == "__main__":
    main()
