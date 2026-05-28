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
import analyze_qmt_roll_stage345_cross_sectional_momentum_satellite as s345  # noqa: E402
import analyze_qmt_roll_stage402_stage079_xsmom_volmanaged_true_integer as s402  # noqa: E402
import analyze_qmt_roll_stage403_stage079_xsmom_execution_margin_audit as s403  # noqa: E402
import analyze_qmt_roll_stage405_stage079_reversal_protection_scout as s405  # noqa: E402


MODEL_TAG = "stage424_stage103_precious_hedge_overlay_v1"
OUTPUT_PREFIX = "qmt_roll_stage424_stage103_precious_hedge_overlay"
LINE_ID = "futures_trend_drawdown30_preserve_return"

BASELINE_VARIANT = s405.BASELINE_VARIANT
STAGE103_VARIANT = s405.STAGE103_VARIANT
ACCOUNT_CAPITAL = s405.ACCOUNT_CAPITAL
TARGET_DD_PCT = -30.0
BROKER10_MULTIPLIER = 1.10

AU_VARIANT = "stage103_plus_au1_long_guard"
AG_VARIANT = "stage103_plus_ag1_long_guard"
AU_AG_VARIANT = "stage103_plus_au1_ag1_long_guard"

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
    products: tuple[str, ...]


VARIANTS: tuple[VariantSpec, ...] = (
    VariantSpec(
        BASELINE_VARIANT,
        "A Stage079 baseline",
        "baseline",
        "none",
        0,
        0,
        0,
        "50万C3下单+11.5万现金。",
        (),
    ),
    VariantSpec(
        STAGE103_VARIANT,
        "C0 Stage103 broker10_guard",
        "stage103",
        "none",
        0,
        0,
        0,
        "当前主执行相对候选。",
        (),
    ),
    VariantSpec(
        AU_VARIANT,
        "C1 Stage103+1手黄金多头",
        "precious_hedge_overlay",
        "fixed_long",
        0,
        0,
        1,
        "固定持有1手au.SHFE多头，受10%经纪商保证金缓冲闸门约束。",
        ("au.SHFE",),
    ),
    VariantSpec(
        AG_VARIANT,
        "C2 Stage103+1手白银多头",
        "precious_hedge_overlay",
        "fixed_long",
        0,
        0,
        1,
        "固定持有1手ag.SHFE多头，受10%经纪商保证金缓冲闸门约束；白银为当前池外固定避险腿。",
        ("ag.SHFE",),
    ),
    VariantSpec(
        AU_AG_VARIANT,
        "C3 Stage103+黄金白银各1手",
        "precious_hedge_overlay",
        "fixed_long",
        0,
        0,
        1,
        "固定持有1手au.SHFE+1手ag.SHFE多头，受10%经纪商保证金缓冲闸门约束。",
        ("au.SHFE", "ag.SHFE"),
    ),
)


PRECIOUS_SPECS = {
    "au.SHFE": {"size": 1000.0, "slippage": 0.02, "margin_ratio": 0.10},
    "ag.SHFE": {"size": 15.0, "slippage": 1.0, "margin_ratio": 0.12},
}


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
    return s405._safe_metric(value, default)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s405._md_table(frame, max_rows)


def _candidate(spec: VariantSpec, equity: pd.Series) -> Any:
    return s402.s087.Candidate(
        variant=spec.variant,
        label=spec.label,
        equity=equity,
        capital_used=ACCOUNT_CAPITAL,
        candidate_class=spec.role,
        eligible_for_promotion=spec.variant != BASELINE_VARIANT,
        note=spec.note,
    )


def _with_contract_fields(frame: pd.DataFrame, product: str) -> pd.DataFrame:
    result = frame.copy()
    result["date"] = pd.to_datetime(result["date"], errors="coerce").dt.normalize()
    result["main_close"] = pd.to_numeric(result["main_close"], errors="coerce")
    result["product_return"] = pd.to_numeric(result["product_return"], errors="coerce").fillna(0.0)
    result = result.sort_values(["product_vt_symbol", "date"]).reset_index(drop=True)
    result["prev_main_close"] = result.groupby("product_vt_symbol")["main_close"].shift(1)
    result["prev_contract"] = result.groupby("product_vt_symbol")["main_contract_vt"].shift(1)
    result["same_contract"] = result["main_contract_vt"].eq(result["prev_contract"])
    result["prev_main_close"] = np.where(
        result["same_contract"] & (result["prev_main_close"] > 0.0),
        result["prev_main_close"],
        result["main_close"],
    )
    spec = PRECIOUS_SPECS[product]
    result["size"] = float(spec["size"])
    result["margin_ratio"] = float(spec["margin_ratio"])
    result["slippage"] = float(spec["slippage"])
    result["margin_per_contract"] = result["main_close"] * result["size"] * result["margin_ratio"]
    return result[
        [
            "date",
            "product_vt_symbol",
            "main_contract_vt",
            "main_close",
            "product_return",
            "prev_main_close",
            "prev_contract",
            "same_contract",
            "size",
            "margin_ratio",
            "slippage",
            "margin_per_contract",
        ]
    ]


def _build_precious_price_frame() -> pd.DataFrame:
    base = s402._build_price_frame()
    base["date"] = pd.to_datetime(base["date"], errors="coerce").dt.normalize()
    parts = [base]
    if not base["product_vt_symbol"].astype(str).eq("ag.SHFE").any():
        ag = s345._load_main_product_returns(["ag.SHFE"])
        if not ag.empty:
            parts.append(_with_contract_fields(ag, "ag.SHFE"))
    result = pd.concat(parts, ignore_index=True)
    result = result.drop_duplicates(["date", "product_vt_symbol"], keep="last").sort_values(
        ["date", "product_vt_symbol"]
    )
    return result.reset_index(drop=True)


def _empty_overlay(window_name: str, variant: str) -> pd.DataFrame:
    return s405._empty_overlay(window_name, variant)


def _simulate_fixed_precious_overlay(
    spec: VariantSpec,
    window_name: str,
    window_frame: pd.DataFrame,
    margin_frame: pd.DataFrame,
    xsmom_sat: pd.DataFrame,
    price_frame: pd.DataFrame,
) -> pd.DataFrame:
    if not spec.products:
        return _empty_overlay(window_name, spec.variant)

    start = window_frame["date"].min()
    end = window_frame["date"].max()
    window_prices = price_frame[
        price_frame["date"].between(start, end) & price_frame["product_vt_symbol"].isin(spec.products)
    ].copy()
    if window_prices.empty:
        return _empty_overlay(window_name, spec.variant)

    c3_pnl = window_frame.set_index("date")["c3_net_pnl"].astype(float).to_dict()
    c3_margin = margin_frame.set_index("date")["c3_margin"].astype(float).to_dict()
    xsmom_by_date = (
        xsmom_sat.set_index("date")
        if not xsmom_sat.empty
        else pd.DataFrame(columns=["satellite_daily_pnl", "satellite_margin", "satellite_slippage_cost"])
    )
    xsmom_pnl = xsmom_by_date.get("satellite_daily_pnl", pd.Series(dtype=float)).astype(float).to_dict()
    xsmom_margin = xsmom_by_date.get("satellite_margin", pd.Series(dtype=float)).astype(float).to_dict()

    price_by_date_product = {
        (row.date, row.product_vt_symbol): row for row in window_prices.itertuples(index=False)
    }
    date_prices: dict[pd.Timestamp, dict[str, Any]] = {}
    for row in window_prices.itertuples(index=False):
        date_prices.setdefault(pd.Timestamp(row.date).normalize(), {})[str(row.product_vt_symbol)] = row

    prev_contract_positions: dict[str, int] = {}
    prev_contract_product: dict[str, str] = {}
    rows: list[dict[str, Any]] = []
    prev_equity = ACCOUNT_CAPITAL
    trading_dates = list(window_frame["date"].sort_values())

    for raw_date in trading_dates:
        date = pd.Timestamp(raw_date).normalize()
        prices = date_prices.get(date, {})
        targets: dict[str, int] = {}
        contract_product: dict[str, str] = {}
        proposed_margin = 0.0
        desired_count = 0
        for product in spec.products:
            price_row = prices.get(product)
            if price_row is None:
                continue
            contract = str(getattr(price_row, "main_contract_vt", ""))
            margin = s402._safe_float(getattr(price_row, "margin_per_contract", 0.0))
            prev_close = s402._safe_float(getattr(price_row, "prev_main_close", 0.0))
            if not contract or margin <= 0.0 or prev_close <= 0.0:
                continue
            desired_count += 1
            targets[contract] = 1
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
                "overlay_desired_product_count": desired_count,
                "overlay_rebalance": 1,
                "overlay_margin_gate_skipped": margin_gate_skipped,
            }
        )
        prev_contract_positions = targets
        prev_contract_product = contract_product
        prev_equity += float(c3_pnl.get(date, 0.0)) + float(xsmom_pnl.get(date, 0.0)) + overlay_daily_pnl

    return pd.DataFrame(rows)


def _drawdown(nav: np.ndarray) -> np.ndarray:
    if len(nav) == 0:
        return np.asarray([], dtype=float)
    high = np.maximum.accumulate(nav)
    return np.divide(nav, high, out=np.zeros_like(nav), where=high != 0.0) - 1.0


def _ulcer(nav: np.ndarray) -> float:
    dd = np.minimum(_drawdown(nav), 0.0) * 100.0
    return float(np.sqrt(np.mean(dd * dd))) if len(dd) else 0.0


def _calendarize_daily(daily: pd.DataFrame) -> pd.DataFrame:
    raw = daily.sort_values("date").drop_duplicates("date", keep="last")
    calendar = pd.DataFrame({"date": pd.date_range(raw["date"].min(), raw["date"].max(), freq="D")})
    merged = calendar.merge(raw, on="date", how="left")
    merged["equity"] = pd.to_numeric(merged["equity"], errors="coerce").ffill()
    for col in ["c3_net_pnl", "satellite_daily_pnl", "overlay_daily_pnl", "combo_slippage"]:
        merged[col] = pd.to_numeric(merged.get(col, 0.0), errors="coerce").fillna(0.0)
    return merged


def _candidate_variants() -> list[str]:
    return [spec.variant for spec in VARIANTS if spec.variant not in {BASELINE_VARIANT, STAGE103_VARIANT}]


def _rolling_pairwise(full_daily: pd.DataFrame) -> pd.DataFrame:
    windows = (90, 180, 252, 504)
    by_variant = {
        variant: _calendarize_daily(frame[frame["window_name"].eq("start_2020")])
        for variant, frame in full_daily.groupby("variant", sort=False)
    }
    rows: list[dict[str, Any]] = []
    for candidate_variant in _candidate_variants():
        candidate = by_variant.get(candidate_variant)
        if candidate is None or candidate.empty:
            continue
        candidate = candidate.set_index("date")
        for comparator_variant in [BASELINE_VARIANT, STAGE103_VARIANT]:
            comparator = by_variant.get(comparator_variant)
            if comparator is None or comparator.empty:
                continue
            comparator = comparator.set_index("date")
            common = candidate[["equity"]].rename(columns={"equity": "candidate_equity"}).join(
                comparator[["equity"]].rename(columns={"equity": "comparator_equity"}),
                how="inner",
            )
            for window_days in windows:
                return_deltas: list[float] = []
                maxdd_not_worse: list[int] = []
                ulcer_not_worse: list[int] = []
                for start_date in common.index:
                    end_date = start_date + pd.Timedelta(days=window_days)
                    if end_date > common.index.max():
                        continue
                    sub = common.loc[start_date:end_date]
                    if len(sub) < 2:
                        continue
                    c_nav = sub["candidate_equity"].to_numpy(dtype=float) / float(sub["candidate_equity"].iloc[0])
                    b_nav = sub["comparator_equity"].to_numpy(dtype=float) / float(sub["comparator_equity"].iloc[0])
                    c_ret = (float(c_nav[-1]) - 1.0) * 100.0
                    b_ret = (float(b_nav[-1]) - 1.0) * 100.0
                    c_dd = float(_drawdown(c_nav).min() * 100.0)
                    b_dd = float(_drawdown(b_nav).min() * 100.0)
                    c_ulcer = _ulcer(c_nav)
                    b_ulcer = _ulcer(b_nav)
                    return_deltas.append(c_ret - b_ret)
                    maxdd_not_worse.append(int(c_dd >= b_dd - 1e-12))
                    ulcer_not_worse.append(int(c_ulcer <= b_ulcer + 1e-12))
                deltas = np.asarray(return_deltas, dtype=float)
                rows.append(
                    {
                        "candidate_variant": candidate_variant,
                        "comparator_variant": comparator_variant,
                        "window_days": window_days,
                        "count": int(len(deltas)),
                        "return_win_rate": float(np.mean(deltas >= -1e-12)) if len(deltas) else np.nan,
                        "return_delta_median_pp": float(np.median(deltas)) if len(deltas) else np.nan,
                        "return_delta_p05_pp": float(np.percentile(deltas, 5)) if len(deltas) else np.nan,
                        "maxdd_not_worse_rate": float(np.mean(maxdd_not_worse)) if maxdd_not_worse else np.nan,
                        "ulcer_not_worse_rate": float(np.mean(ulcer_not_worse)) if ulcer_not_worse else np.nan,
                    }
                )
    return pd.DataFrame(rows)


def _top_edge_day_ablation(full_daily: pd.DataFrame) -> pd.DataFrame:
    remove_counts = (0, 1, 3, 5, 10, 20)
    full = full_daily[full_daily["window_name"].eq("start_2020")].copy()
    by_variant = {variant: _calendarize_daily(frame) for variant, frame in full.groupby("variant", sort=False)}
    rows: list[dict[str, Any]] = []
    for candidate_variant in _candidate_variants():
        candidate = by_variant.get(candidate_variant)
        if candidate is None or candidate.empty:
            continue
        candidate = candidate.set_index("date")
        c_pnl = candidate["equity"].diff().fillna(candidate["equity"].iloc[0] - ACCOUNT_CAPITAL)
        for comparator_variant in [BASELINE_VARIANT, STAGE103_VARIANT]:
            comparator = by_variant.get(comparator_variant)
            if comparator is None or comparator.empty:
                continue
            comparator = comparator.set_index("date")
            b_pnl = comparator["equity"].diff().fillna(comparator["equity"].iloc[0] - ACCOUNT_CAPITAL)
            edge = (c_pnl - b_pnl).sort_values(ascending=False)
            b_nav = comparator["equity"].to_numpy(dtype=float) / ACCOUNT_CAPITAL
            b_return = (float(b_nav[-1]) - 1.0) * 100.0
            b_maxdd = float(_drawdown(b_nav).min() * 100.0)
            b_ulcer = _ulcer(b_nav)
            for n in remove_counts:
                adjusted_pnl = c_pnl.copy()
                if n > 0:
                    adjusted_pnl.loc[edge.head(n).index] -= edge.head(n)
                adjusted_equity = ACCOUNT_CAPITAL + adjusted_pnl.cumsum()
                nav = adjusted_equity.to_numpy(dtype=float) / ACCOUNT_CAPITAL
                adjusted_return = (float(nav[-1]) - 1.0) * 100.0
                adjusted_maxdd = float(_drawdown(nav).min() * 100.0)
                adjusted_ulcer = _ulcer(nav)
                rows.append(
                    {
                        "candidate_variant": candidate_variant,
                        "comparator_variant": comparator_variant,
                        "removed_top_positive_edge_days": n,
                        "removed_edge_pnl": float(edge.head(n).sum()) if n > 0 else 0.0,
                        "candidate_adjusted_total_return_pct": adjusted_return,
                        "candidate_adjusted_max_dd_pct": adjusted_maxdd,
                        "candidate_adjusted_ulcer_pct": adjusted_ulcer,
                        "comparator_total_return_pct": b_return,
                        "comparator_max_dd_pct": b_maxdd,
                        "comparator_ulcer_pct": b_ulcer,
                        "adjusted_return_delta_pp": adjusted_return - b_return,
                        "adjusted_maxdd_delta_pp": adjusted_maxdd - b_maxdd,
                        "adjusted_ulcer_delta_pp": adjusted_ulcer - b_ulcer,
                    }
                )
    return pd.DataFrame(rows)


def _plot(full_daily: pd.DataFrame, score: pd.DataFrame, pairwise: pd.DataFrame) -> None:
    variants = [spec.variant for spec in VARIANTS]
    labels = ["Stage079", "Stage103", "+AU1", "+AG1", "+AU1+AG1"]
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

    fig.suptitle("Stage124 fixed precious metals hedge overlay", fontsize=14)
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
        "# Stage124 Stage103固定贵金属避险小腿审计",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：低自由度固定结构验证；不改C3、Stage079、Stage103交易规则，不增加账户资金，不扫日期、品种权重或保证金小数。",
        "- A/B/C：A=Stage079；C0=Stage103；C1=Stage103+1手黄金；C2=Stage103+1手白银；C3=Stage103+黄金白银各1手。",
        "- 候选假设：黄金在部分危机/压力期可能具备safe-haven/hedge属性；白银有贵金属属性但更偏工业周期，因此只做固定1手验证。",
        "- 数据口径：au.SHFE沿用现有连续主力价格框架；ag.SHFE不在当前交易池内，本阶段仅用同一主力映射和TQSDK日线补入，规格固定为15吨/手、1元滑点、12%保证金。",
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
        _md_table(
            pairwise[
                [
                    "candidate_variant",
                    "comparator_variant",
                    "window_days",
                    "return_win_rate",
                    "return_delta_median_pp",
                    "return_delta_p05_pp",
                    "maxdd_not_worse_rate",
                    "ulcer_not_worse_rate",
                ]
            ]
        ),
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
        "- 本阶段只测固定1手黄金/白银/黄金+白银，不根据结果修改方向、权重、月份、阈值或保证金缓冲。",
        "- 若贵金属只提高全周期收益但恶化任意启动、短持有体验或保证金压力，则不晋级。",
        "- 若结论失败，本路线只保留经验，不继续扫白银规格、黄金白银比例、入场日期或危机过滤条件。",
    ]
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    combo = s402._load_combo_daily()
    margin = s402._load_margin()
    full_frame = combo[combo["window_name"].eq("start_2020")].sort_values("date").drop_duplicates("date", keep="last")
    scale_by_date = s402._build_stage101_scale(full_frame)
    price_frame = _build_precious_price_frame()
    price_frame["date"] = pd.to_datetime(price_frame["date"], errors="coerce").dt.normalize()
    signals = s402._load_signal_daily()
    signals["date"] = pd.to_datetime(signals["date"], errors="coerce").dt.normalize()

    old_variants = s405.VARIANTS
    s405.VARIANTS = VARIANTS
    try:
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
                    overlay = _empty_overlay(window_name, spec.variant)
                else:
                    overlay = _simulate_fixed_precious_overlay(spec, window_name, frame, margin_frame, xsmom, price_frame)
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
        pairwise = _rolling_pairwise(full_daily)
        topday = _top_edge_day_ablation(full_daily)
    finally:
        s405.VARIANTS = old_variants

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
    decision_code = (
        "execution_relative_candidate"
        if len(execution_ready) and weak_pairwise.empty and fragile_after_one_day.empty
        else ("research_candidate_only" if len(research_ready) else "no_new_promotion")
    )
    if len(execution_ready) and (not weak_pairwise.empty or not fragile_after_one_day.empty):
        decision_code = "fixed_path_pass_but_robustness_gap_do_not_promote"
    decision = {
        "stage": "Stage124",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": decision_code,
        "execution_relative_ready_variants_by_stage405_gate": execution_ready["variant"].tolist(),
        "research_ready_variants_by_stage405_gate": research_ready["variant"].tolist(),
        "best_by_gate_order": str(best_gate["variant"]) if best_gate is not None else "",
        "weak_pairwise_vs_stage103_count": int(len(weak_pairwise)),
        "fragile_after_one_top_edge_day_count": int(len(fragile_after_one_day)),
        "chart": str(CHART_PATH),
        "judgement": "贵金属固定小腿若不能同时改善Stage103相对任意启动与保证金/成本路径，则不晋级；不继续扫比例或危机过滤。",
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
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _plot(full_daily, score, pairwise)
    _write_report(summary, horizon, score, fresh, cost, margin_audit, bad_windows, gate, pairwise, topday, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"report={REPORT_PATH}")


if __name__ == "__main__":
    main()
