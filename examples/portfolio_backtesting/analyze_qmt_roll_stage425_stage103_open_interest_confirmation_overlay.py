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


MODEL_TAG = "stage425_stage103_open_interest_confirmation_overlay_v1"
OUTPUT_PREFIX = "qmt_roll_stage425_stage103_open_interest_confirmation_overlay"
LINE_ID = "futures_trend_drawdown30_preserve_return"

BASELINE_VARIANT = s405.BASELINE_VARIANT
STAGE103_VARIANT = s405.STAGE103_VARIANT
ACCOUNT_CAPITAL = s405.ACCOUNT_CAPITAL
TARGET_DD_PCT = -30.0
LOOKBACK_DAYS = 63
REBALANCE_EVERY = 5

OI_BEST1_VARIANT = "stage103_plus_oi_confirm63_best1_weekly_guard"
OI_TOP3_VARIANT = "stage103_plus_oi_confirm63_top3_weekly_guard"

FEATURE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_features_{MODEL_TAG}.csv"
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
    VariantSpec(
        BASELINE_VARIANT,
        "A Stage079 baseline",
        "baseline",
        "none",
        0,
        0,
        0,
        "50万C3下单+11.5万现金。",
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
    ),
    VariantSpec(
        OI_BEST1_VARIANT,
        "C1 Stage103+OI确认63日动量best1",
        "open_interest_confirmation_overlay",
        "momentum",
        LOOKBACK_DAYS,
        1,
        REBALANCE_EVERY,
        "63日价格动量必须被63日总持仓增长确认，周频取最强多头和最弱空头各1个品种，每品种1手。",
    ),
    VariantSpec(
        OI_TOP3_VARIANT,
        "C2 Stage103+OI确认63日动量top3",
        "open_interest_confirmation_overlay",
        "momentum",
        LOOKBACK_DAYS,
        3,
        REBALANCE_EVERY,
        "63日价格动量必须被63日总持仓增长确认，周频取最强多头和最弱空头各3个品种，每品种1手。",
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


def _load_total_open_interest(products: list[str]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    raw_dir = s345.RAW_CONTRACT_DIR
    for product_vt in sorted(products):
        symbol, exchange = product_vt.split(".", 1)
        product_dir = raw_dir / exchange
        for path in sorted(product_dir.glob(f"{symbol}*.csv")):
            try:
                frame = pd.read_csv(path, usecols=["trade_date", "open_oi", "volume"], encoding="utf-8-sig")
            except (FileNotFoundError, ValueError, pd.errors.EmptyDataError):
                continue
            if frame.empty:
                continue
            frame["date"] = pd.to_datetime(frame["trade_date"], errors="coerce").dt.normalize()
            frame["product_vt_symbol"] = product_vt
            frame["open_oi"] = pd.to_numeric(frame["open_oi"], errors="coerce").fillna(0.0)
            frame["volume"] = pd.to_numeric(frame["volume"], errors="coerce").fillna(0.0)
            frames.append(frame[["date", "product_vt_symbol", "open_oi", "volume"]])
    if not frames:
        return pd.DataFrame(columns=["date", "product_vt_symbol", "total_open_oi", "total_volume"])
    result = (
        pd.concat(frames, ignore_index=True)
        .dropna(subset=["date"])
        .groupby(["date", "product_vt_symbol"], as_index=False)
        .agg(total_open_oi=("open_oi", "sum"), total_volume=("volume", "sum"))
    )
    return result.sort_values(["date", "product_vt_symbol"]).reset_index(drop=True)


def _build_rank_tables(price_frame: pd.DataFrame) -> dict[str, pd.DataFrame]:
    products = sorted(price_frame["product_vt_symbol"].dropna().astype(str).unique().tolist())
    total_oi = _load_total_open_interest(products)
    features = price_frame[["date", "product_vt_symbol", "product_return"]].copy()
    features["date"] = pd.to_datetime(features["date"], errors="coerce").dt.normalize()
    features = features.merge(total_oi, on=["date", "product_vt_symbol"], how="left")
    features["product_return"] = pd.to_numeric(features["product_return"], errors="coerce").fillna(0.0)
    features["total_open_oi"] = pd.to_numeric(features["total_open_oi"], errors="coerce")
    features["total_volume"] = pd.to_numeric(features["total_volume"], errors="coerce")

    ret_wide = (
        features.pivot_table(index="date", columns="product_vt_symbol", values="product_return", aggfunc="last")
        .sort_index()
        .fillna(0.0)
    )
    oi_wide = (
        features.pivot_table(index="date", columns="product_vt_symbol", values="total_open_oi", aggfunc="last")
        .sort_index()
        .reindex(ret_wide.index)
    )
    log_ret = np.log1p(ret_wide.clip(lower=-0.999999))
    price_mom = np.expm1(log_ret.rolling(LOOKBACK_DAYS, min_periods=LOOKBACK_DAYS).sum()).shift(1)
    log_oi = np.log(oi_wide.replace(0.0, np.nan))
    oi_growth = log_oi.diff(LOOKBACK_DAYS).shift(1)

    score = price_mom.where(oi_growth > 0.0) * oi_growth.where(oi_growth > 0.0)
    score = score.replace([np.inf, -np.inf], np.nan)

    long_feature = score.reset_index().melt(id_vars="date", var_name="product_vt_symbol", value_name="oi_confirm_score")
    price_long = price_mom.reset_index().melt(id_vars="date", var_name="product_vt_symbol", value_name="price_mom_63")
    oi_long = oi_growth.reset_index().melt(id_vars="date", var_name="product_vt_symbol", value_name="oi_growth_63")
    feature_out = long_feature.merge(price_long, on=["date", "product_vt_symbol"], how="left").merge(
        oi_long, on=["date", "product_vt_symbol"], how="left"
    )
    feature_out["has_confirmed_signal"] = feature_out["oi_confirm_score"].notna().astype(int)
    feature_out.to_csv(FEATURE_PATH, index=False, encoding="utf-8-sig")

    return {
        BASELINE_VARIANT: pd.DataFrame(),
        STAGE103_VARIANT: pd.DataFrame(),
        OI_BEST1_VARIANT: score,
        OI_TOP3_VARIANT: score,
    }


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
                rows.append(
                    {
                        "candidate_variant": candidate_variant,
                        "comparator_variant": comparator_variant,
                        "removed_top_positive_edge_days": n,
                        "removed_edge_pnl": float(edge.head(n).sum()) if n > 0 else 0.0,
                        "candidate_adjusted_total_return_pct": (float(nav[-1]) - 1.0) * 100.0,
                        "candidate_adjusted_max_dd_pct": float(_drawdown(nav).min() * 100.0),
                        "candidate_adjusted_ulcer_pct": _ulcer(nav),
                        "comparator_total_return_pct": b_return,
                        "comparator_max_dd_pct": b_maxdd,
                        "comparator_ulcer_pct": b_ulcer,
                        "adjusted_return_delta_pp": (float(nav[-1]) - 1.0) * 100.0 - b_return,
                    }
                )
    return pd.DataFrame(rows)


def _plot(full_daily: pd.DataFrame, score: pd.DataFrame, pairwise: pd.DataFrame) -> None:
    variants = [spec.variant for spec in VARIANTS]
    labels = ["Stage079", "Stage103", "+OI best1", "+OI top3"]
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

    fig.suptitle("Stage125 open interest confirmation overlay", fontsize=14)
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
        "# Stage125 Stage103 Open Interest确认动量审计",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：外部先验驱动的低自由度结构验证；不改C3、Stage079、Stage103交易规则，不增加账户资金，不扫窗口和阈值。",
        "- A/B/C：A=Stage079；C0=Stage103；C1=Stage103+OI确认63日动量best1；C2=Stage103+OI确认63日动量top3。",
        "- 候选假设：总持仓增长代表新资金/套保需求进入，价格动量被总持仓增长确认时更可能延续，可能减少短期假突破和启动左尾。",
        "- 固定口径：价格动量与总持仓增长均为63日、shift一日；只有总持仓增长为正的品种进入排名；每5个交易日再平衡；每品种1手；沿用10%经纪商保证金闸门。",
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
        "- 本阶段只测试固定63日OI确认动量，不根据坏窗口、品种、年份或结果调窗口、阈值、top_n相邻小数。",
        "- OI不是方向圣杯，只作为价格动量的资金承诺确认；如果冷启动、成本或任意启动失败，则不晋级。",
        "- 若失败，不继续扫 `21/42/84/126`、OI增长阈值、成交量阈值、品种过滤或再平衡频率。",
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
    rank_tables = _build_rank_tables(price_frame)
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
                    overlay = s405._empty_overlay(window_name, spec.variant)
                else:
                    overlay = s405._simulate_overlay(
                        spec, window_name, frame, margin_frame, xsmom, price_frame, rank_tables[spec.variant]
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
        "stage": "Stage125",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": decision_code,
        "execution_relative_ready_variants_by_stage405_gate": execution_ready["variant"].tolist(),
        "research_ready_variants_by_stage405_gate": research_ready["variant"].tolist(),
        "best_by_gate_order": str(best_gate["variant"]) if best_gate is not None else "",
        "weak_pairwise_vs_stage103_count": int(len(weak_pairwise)),
        "fragile_after_one_top_edge_day_count": int(len(fragile_after_one_day)),
        "chart": str(CHART_PATH),
        "judgement": "OI确认若不能改善冷启动、成本和任意启动体验，则不晋级，不继续扫OI窗口或阈值。",
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
