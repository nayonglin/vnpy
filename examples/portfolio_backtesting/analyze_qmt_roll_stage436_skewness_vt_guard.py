from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

sys.path.insert(0, str(PROJECT_DIR.resolve()))
import analyze_qmt_roll_stage402_stage079_xsmom_volmanaged_true_integer as s402  # noqa: E402
import analyze_qmt_roll_stage403_stage079_xsmom_execution_margin_audit as s403  # noqa: E402
import analyze_qmt_roll_stage405_stage079_reversal_protection_scout as s405  # noqa: E402
import analyze_qmt_roll_stage425_stage103_open_interest_confirmation_overlay as s425  # noqa: E402


MODEL_TAG = "stage436_skewness_vt_guard_v1"
OUTPUT_PREFIX = "qmt_roll_stage436_skewness_vt_guard"
LINE_ID = "futures_trend_drawdown30_preserve_return"

BASELINE_VARIANT = s405.BASELINE_VARIANT
STAGE103_VARIANT = s405.STAGE103_VARIANT
ACCOUNT_CAPITAL = s405.ACCOUNT_CAPITAL
TARGET_DD_PCT = s405.TARGET_DD_PCT
SKEW_LOOKBACK_DAYS = 252
REBALANCE_EVERY = 20
VOL_LOOKBACK_DAYS = 63
TARGET_VOL = 0.10
ROUND_HALF_THRESHOLD = 0.5

SKEW_BEST1_VT_VARIANT = "stage103_plus_low_skew252_best1_vt10_mom63_round_half_guard"
SKEW_TOP3_VT_VARIANT = "stage103_plus_low_skew252_top3_vt10_mom63_round_half_guard"

FEATURE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_features_{MODEL_TAG}.csv"
SHADOW_SCALE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_shadow_scale_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
HORIZON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_{MODEL_TAG}.csv"
SCORE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_score_{MODEL_TAG}.csv"
FRESH_START_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_fresh_start_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
MARGIN_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_margin_audit_{MODEL_TAG}.csv"
BAD_WINDOW_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bad_window_contribution_{MODEL_TAG}.csv"
PAIRWISE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pairwise_rolling_{MODEL_TAG}.csv"
TOPDAY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_top_edge_day_ablation_{MODEL_TAG}.csv"
GATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_{MODEL_TAG}.csv"
DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
OVERLAY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_overlay_daily_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


@dataclass(frozen=True)
class VariantSpec:
    variant: str
    label: str
    role: str
    direction: str
    lookback_days: int
    top_n: int
    rebalance_every: int
    note: str


VARIANTS: tuple[VariantSpec, ...] = (
    VariantSpec(BASELINE_VARIANT, "A Stage079 baseline", "baseline", "none", 0, 0, 0, "50万C3下单+11.5万现金。"),
    VariantSpec(STAGE103_VARIANT, "C0 Stage103 broker10_guard", "stage103", "none", 0, 0, 0, "当前主执行相对候选。"),
    VariantSpec(
        SKEW_BEST1_VT_VARIANT,
        "C1 低偏度best1 + vt10/mom63/round_half",
        "commodity_skewness_vt_guard",
        "reversal",
        SKEW_LOOKBACK_DAYS,
        1,
        REBALANCE_EVERY,
        "Stage135 best1的固定低偏度信号，叠加Stage101同源的63日自有PnL动量和10%波动目标，scale>=0.5才执行1手。",
    ),
    VariantSpec(
        SKEW_TOP3_VT_VARIANT,
        "C2 低偏度top3 + vt10/mom63/round_half",
        "commodity_skewness_vt_guard",
        "reversal",
        SKEW_LOOKBACK_DAYS,
        3,
        REBALANCE_EVERY,
        "Stage135 top3的固定低偏度信号，叠加Stage101同源的63日自有PnL动量和10%波动目标，scale>=0.5才执行整篮子。",
    ),
)


RAW_VARIANT_BY_VT = {
    SKEW_BEST1_VT_VARIANT: "raw_low_skew252_monthly_best1",
    SKEW_TOP3_VT_VARIANT: "raw_low_skew252_monthly_top3",
}


def _json_safe(value: Any) -> Any:
    return s405._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s405._md_table(frame, max_rows=max_rows)


def _candidate(spec: VariantSpec, equity: pd.Series) -> Any:
    return s402.s087.Candidate(
        variant=spec.variant,
        label=spec.label,
        equity=equity,
        capital_used=ACCOUNT_CAPITAL,
        candidate_class=spec.role,
        eligible_for_promotion=spec.variant not in {BASELINE_VARIANT, STAGE103_VARIANT},
        note=spec.note,
    )


def _build_skewness_rank_tables(price_frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    returns = (
        price_frame.pivot_table(index="date", columns="product_vt_symbol", values="product_return", aggfunc="last")
        .sort_index()
        .fillna(0.0)
    )
    skew = returns.rolling(SKEW_LOOKBACK_DAYS, min_periods=SKEW_LOOKBACK_DAYS).skew().shift(1)
    feature = skew.reset_index().melt(id_vars="date", var_name="product_vt_symbol", value_name="skew252")
    feature["date"] = pd.to_datetime(feature["date"], errors="coerce").dt.normalize()
    feature["has_skew_signal"] = feature["skew252"].notna().astype(int)
    feature.to_csv(FEATURE_PATH, index=False, encoding="utf-8-sig")
    return {
        BASELINE_VARIANT: pd.DataFrame(),
        STAGE103_VARIANT: pd.DataFrame(),
        SKEW_BEST1_VT_VARIANT: skew,
        SKEW_TOP3_VT_VARIANT: skew,
    }


def _raw_spec_for(spec: VariantSpec) -> VariantSpec:
    return VariantSpec(
        RAW_VARIANT_BY_VT[spec.variant],
        f"raw shadow for {spec.label}",
        "shadow",
        spec.direction,
        spec.lookback_days,
        spec.top_n,
        spec.rebalance_every,
        "只用于点时化shadow scale计算，不作为真实候选。",
    )


def _build_shadow_scale(raw_overlay: pd.DataFrame, variant: str) -> pd.DataFrame:
    frame = raw_overlay.sort_values("date").drop_duplicates("date", keep="last").copy()
    pnl = pd.to_numeric(frame["overlay_daily_pnl"], errors="coerce").fillna(0.0)
    ret = pnl / ACCOUNT_CAPITAL
    vol = ret.rolling(VOL_LOOKBACK_DAYS, min_periods=VOL_LOOKBACK_DAYS).std(ddof=1).shift(1) * math.sqrt(252.0)
    momentum = (pnl.rolling(VOL_LOOKBACK_DAYS, min_periods=VOL_LOOKBACK_DAYS).sum().shift(1) > 0.0).astype(float)
    base_scale = (TARGET_VOL / vol).replace([np.inf, -np.inf], np.nan).clip(lower=0.0, upper=1.0).fillna(0.0)
    scale = base_scale * momentum
    result = pd.DataFrame(
        {
            "date": pd.to_datetime(frame["date"], errors="coerce").dt.normalize(),
            "variant": variant,
            "shadow_pnl": pnl,
            "shadow_vol63": vol,
            "shadow_mom63": momentum,
            "shadow_scale": scale,
            "shadow_round_half_active": (scale >= ROUND_HALF_THRESHOLD).astype(int),
        }
    )
    return result


def _simulate_vt_overlay(
    spec: VariantSpec,
    window_name: str,
    window_frame: pd.DataFrame,
    margin_frame: pd.DataFrame,
    xsmom_sat: pd.DataFrame,
    price_frame: pd.DataFrame,
    rank_table: pd.DataFrame | None,
    shadow_scale: pd.DataFrame,
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
        else pd.DataFrame(columns=["satellite_daily_pnl", "satellite_margin", "satellite_slippage_cost"])
    )
    xsmom_pnl = xsmom_by_date.get("satellite_daily_pnl", pd.Series(dtype=float)).astype(float).to_dict()
    xsmom_margin = xsmom_by_date.get("satellite_margin", pd.Series(dtype=float)).astype(float).to_dict()

    scale_frame = shadow_scale[shadow_scale["variant"].eq(spec.variant)].copy()
    scale_by_date = scale_frame.set_index("date")["shadow_scale"].astype(float).to_dict()
    vol_by_date = scale_frame.set_index("date")["shadow_vol63"].astype(float).to_dict()
    mom_by_date = scale_frame.set_index("date")["shadow_mom63"].astype(float).to_dict()

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

        scale = float(scale_by_date.get(date, 0.0))
        active_by_scale = int(scale >= ROUND_HALF_THRESHOLD)
        effective_product_targets = product_targets if active_by_scale else {}

        targets: dict[str, int] = {}
        contract_product: dict[str, str] = {}
        proposed_margin = 0.0
        for product, direction in effective_product_targets.items():
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
        ) * s405.BROKER10_MULTIPLIER
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
                "overlay_shadow_scale": scale,
                "overlay_shadow_vol63": float(vol_by_date.get(date, np.nan)),
                "overlay_shadow_mom63": float(mom_by_date.get(date, 0.0)),
                "overlay_scale_active": active_by_scale,
            }
        )
        prev_contract_positions = targets
        prev_contract_product = contract_product
        prev_equity += float(c3_pnl.get(date, 0.0)) + float(xsmom_pnl.get(date, 0.0)) + overlay_daily_pnl

    return pd.DataFrame(rows)


def _plot(full_daily: pd.DataFrame, score: pd.DataFrame, pairwise: pd.DataFrame) -> None:
    variants = [spec.variant for spec in VARIANTS]
    labels = ["Stage079", "Stage103", "+skew vt best1", "+skew vt top3"]
    full = full_daily[full_daily["window_name"].eq("start_2020")].copy()
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))

    for variant, frame in full.groupby("variant", sort=False):
        frame = frame.sort_values("date")
        nav = pd.Series(frame["equity"].to_numpy(dtype=float), index=pd.to_datetime(frame["date"])) / ACCOUNT_CAPITAL
        axes[0, 0].plot(nav.index, nav, label=variant, linewidth=1.0)
        axes[1, 0].plot(nav.index, (nav / nav.cummax() - 1.0) * 100.0, label=variant, linewidth=0.9)
    axes[0, 0].set_title("Full-period NAV")
    axes[0, 0].legend(fontsize=6)
    axes[1, 0].set_title("Drawdown")
    axes[1, 0].axhline(TARGET_DD_PCT, color="red", linestyle="--", linewidth=1.0)
    axes[1, 0].legend(fontsize=6)

    x = np.arange(len(variants))
    s90 = score[score["horizon_days"].eq(90)].set_index("variant").reindex(variants)
    s180 = score[score["horizon_days"].eq(180)].set_index("variant").reindex(variants)
    axes[0, 1].bar(x - 0.18, s90["experience_score"].to_numpy(dtype=float), 0.36, label="90d score")
    axes[0, 1].bar(x + 0.18, s180["experience_score"].to_numpy(dtype=float), 0.36, label="180d score")
    axes[0, 1].axhline(110.0, color="#777777", linestyle="--", linewidth=0.8)
    axes[0, 1].set_title("Short holding scores")
    axes[0, 1].set_xticks(x)
    axes[0, 1].set_xticklabels(labels, rotation=20, ha="right", fontsize=8)
    axes[0, 1].legend(fontsize=8)

    pw = pairwise[
        pairwise["comparator_variant"].eq(STAGE103_VARIANT) & pairwise["window_days"].isin([90, 180, 252, 504])
    ]
    for variant, frame in pw.groupby("candidate_variant", sort=False):
        axes[1, 1].plot(frame["window_days"], frame["return_win_rate"], marker="o", label=variant)
    axes[1, 1].axhline(0.5, color="#777777", linestyle="--", linewidth=0.8)
    axes[1, 1].set_title("Rolling return win rate vs Stage103")
    axes[1, 1].set_ylim(0, 1)
    axes[1, 1].legend(fontsize=6)

    fig.suptitle("Stage136 skewness volatility/self-momentum guard", fontsize=14)
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
    pairwise: pd.DataFrame,
    topday: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    report = [
        "# Stage136 Stage135偏度overlay波动目标与自有动量闸门审计",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：固定通用承载闸门验证；不改C3、Stage079、Stage103交易规则，不增加账户资金。",
        "- A/B/C：A=Stage079；C0=Stage103；C1=低偏度best1+vt10/mom63/round_half；C2=低偏度top3+vt10/mom63/round_half。",
        "- 候选假设：Stage135偏度收益源真实但尾部冷启动脆弱；沿用Stage101的63日自有PnL动量与10%波动目标，只在shadow scale>=0.5时执行，避免高波动阶段强行最小一手。",
        "- 固定口径：252日偏度、20交易日再平衡、63日shadow PnL波动目标、目标年化10%、scale>=0.5执行最小1手；不按2026日期或品种补丁。",
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
        "## 任意启动滚动胜率",
        "",
        _md_table(pairwise),
        "",
        "## 最大贡献日剔除",
        "",
        _md_table(topday, max_rows=80),
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
        "- 本阶段没有改偏度窗口、没有调目标波动、没有调scale阈值；`10%/63日/0.5`沿用Stage101/102已冻结承载语义。",
        "- 闸门基于shadow paper PnL的点时化波动和自有动量，不使用未来收益、坏窗口日期、品种黑名单或2026补丁。",
        "- 若仍不能通过硬约束，不继续扫 `8%/12%`、`42/84日`、`0.4/0.6` 或偏度窗口救援。",
    ]
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    combo = s402._load_combo_daily()
    margin = s402._load_margin()
    full_frame = combo[combo["window_name"].eq("start_2020")].sort_values("date").drop_duplicates("date", keep="last")
    scale_by_date = s402._build_stage101_scale(full_frame)
    price_frame = s402._build_price_frame()
    price_frame["date"] = pd.to_datetime(price_frame["date"], errors="coerce").dt.normalize()
    rank_tables = _build_skewness_rank_tables(price_frame)
    signals = s402._load_signal_daily()
    signals["date"] = pd.to_datetime(signals["date"], errors="coerce").dt.normalize()

    old_s405_variants = s405.VARIANTS
    old_s425_variants = s425.VARIANTS
    s405.VARIANTS = VARIANTS
    s425.VARIANTS = VARIANTS
    try:
        xsmom_by_window: dict[str, pd.DataFrame] = {}
        overlay_by_window_variant: dict[tuple[str, str], pd.DataFrame] = {}
        daily_by_window_variant: dict[tuple[str, str], pd.DataFrame] = {}
        overlay_full_by_variant: dict[str, pd.DataFrame] = {}
        candidates: list[Any] = []
        full_daily_parts: list[pd.DataFrame] = []

        start_frame = combo[combo["window_name"].eq("start_2020")].sort_values("date").drop_duplicates("date", keep="last")
        start_margin = margin[margin["window_name"].eq("start_2020")].sort_values("date").drop_duplicates("date", keep="last")
        start_xsmom = s403._simulate_guarded_round_half("start_2020", start_frame, start_margin, price_frame, signals, scale_by_date)
        shadow_scale_parts: list[pd.DataFrame] = []
        for spec in VARIANTS:
            if spec.variant in {BASELINE_VARIANT, STAGE103_VARIANT}:
                continue
            raw_overlay = s405._simulate_overlay(
                _raw_spec_for(spec),
                "start_2020",
                start_frame,
                start_margin,
                start_xsmom,
                price_frame,
                rank_tables[spec.variant],
            )
            shadow_scale_parts.append(_build_shadow_scale(raw_overlay, spec.variant))
        shadow_scale = pd.concat(shadow_scale_parts, ignore_index=True) if shadow_scale_parts else pd.DataFrame()

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
                else:
                    overlay = _simulate_vt_overlay(
                        spec,
                        window_name,
                        frame,
                        margin_frame,
                        xsmom,
                        price_frame,
                        rank_tables[spec.variant],
                        shadow_scale,
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
            candidates.append(_candidate(spec, equity))

        full_daily = pd.concat(full_daily_parts, ignore_index=True)
        overlay_all = pd.concat(
            [frame for frame in overlay_by_window_variant.values() if not frame.empty],
            ignore_index=True,
        )
        summary = pd.DataFrame([s402.s087._stats(candidate) for candidate in candidates])
        horizon = pd.DataFrame([s402.s087._horizon_metrics(candidate, days) for candidate in candidates for days in (90, 180)])
        score = s402.s087._score_horizons(horizon)
        margin_audit = s405._margin_audit(combo, margin, xsmom_by_window, overlay_by_window_variant, daily_by_window_variant)
        fresh = s405._fresh_start(combo, xsmom_by_window, overlay_by_window_variant, daily_by_window_variant, margin_audit)
        cost = s405._cost_stress(full_frame, xsmom_by_window["start_2020"], overlay_full_by_variant)
        bad_windows = s405._bad_window_contribution(
            {spec.variant: daily_by_window_variant[("start_2020", spec.variant)] for spec in VARIANTS}
        )
        gate = s405._gate(summary, horizon, score, cost, fresh, margin_audit, bad_windows)
        pairwise = s425._rolling_pairwise(full_daily)
        topday = s425._top_edge_day_ablation(full_daily)
    finally:
        s405.VARIANTS = old_s405_variants
        s425.VARIANTS = old_s425_variants

    execution_ready = gate[gate["execution_relative_pass"].eq(1) & ~gate["variant"].isin([BASELINE_VARIANT, STAGE103_VARIANT])]
    research_ready = gate[gate["research_promotion_pass"].eq(1) & ~gate["variant"].isin([BASELINE_VARIANT, STAGE103_VARIANT])]
    pairwise_vs_stage103 = pairwise[pairwise["comparator_variant"].eq(STAGE103_VARIANT)]
    weak_pairwise = pairwise_vs_stage103[
        (pairwise_vs_stage103["window_days"].isin([90, 180, 252, 504]))
        & (pairwise_vs_stage103["return_win_rate"].fillna(0.0) < 0.5)
    ]
    fragile_after_one_day = topday[
        topday["comparator_variant"].eq(STAGE103_VARIANT)
        & topday["removed_top_positive_edge_days"].eq(1)
        & (topday["adjusted_return_delta_pp"] < 0.0)
    ]
    best_gate = gate.iloc[0] if not gate.empty else None
    if len(execution_ready) and weak_pairwise.empty and fragile_after_one_day.empty:
        decision_code = "execution_relative_candidate"
    elif len(execution_ready):
        decision_code = "fixed_path_pass_but_robustness_gap_promote_to_engineering_paper_candidate"
    elif len(research_ready):
        decision_code = "research_candidate_only"
    else:
        decision_code = "no_new_promotion"

    decision = {
        "stage": "Stage136",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": decision_code,
        "execution_relative_ready_variants_by_stage405_gate": execution_ready["variant"].tolist(),
        "research_ready_variants_by_stage405_gate": research_ready["variant"].tolist(),
        "best_by_gate_order": str(best_gate["variant"]) if best_gate is not None else "",
        "weak_pairwise_vs_stage103_count": int(len(weak_pairwise)),
        "fragile_after_one_top_edge_day_count": int(len(fragile_after_one_day)),
        "chart": str(CHART_PATH),
        "report": str(REPORT_PATH),
        "judgement": "若Stage101同源波动目标/自有动量闸门不能把偏度overlay变成硬约束候选，则停止该救援，不继续扫目标波动、窗口或scale阈值。",
    }

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon.to_csv(HORIZON_PATH, index=False, encoding="utf-8-sig")
    score.to_csv(SCORE_PATH, index=False, encoding="utf-8-sig")
    fresh.to_csv(FRESH_START_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    margin_audit.to_csv(MARGIN_AUDIT_PATH, index=False, encoding="utf-8-sig")
    bad_windows.to_csv(BAD_WINDOW_PATH, index=False, encoding="utf-8-sig")
    pairwise.to_csv(PAIRWISE_PATH, index=False, encoding="utf-8-sig")
    topday.to_csv(TOPDAY_PATH, index=False, encoding="utf-8-sig")
    gate.to_csv(GATE_PATH, index=False, encoding="utf-8-sig")
    full_daily.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    overlay_all.to_csv(OVERLAY_PATH, index=False, encoding="utf-8-sig")
    shadow_scale.to_csv(SHADOW_SCALE_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _plot(full_daily, score, pairwise)
    _write_report(summary, horizon, score, fresh, cost, margin_audit, bad_windows, gate, pairwise, topday, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"report={REPORT_PATH}")


if __name__ == "__main__":
    main()
