from __future__ import annotations

import json
import math
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
MODEL_TAG = "stage412_stage111_liquidity_robustness_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage412_stage111_liquidity_robustness_audit"
LINE_ID = "futures_trend_drawdown30_preserve_return"

ACCOUNT_CAPITAL = 615_000.0
STAGE079_VARIANT = "stage079"
STAGE103_VARIANT = "xsmom_vt10_q_momq_round_half_true_broker10_guard"
CASHYIELD_VARIANT = "stage103_cash_yield_2pct"
STAGE111_VARIANT = "stage103_stock_lot_50000_cash_65000_yield2"
STOCK_CAPITAL = 50_000.0

STAGE411_PREFIX = "qmt_roll_stage411_stage103_stock_cashslot_audit"
STAGE411_TAG = "stage411_stage103_stock_cashslot_audit_v1"
STAGE403_PREFIX = "qmt_roll_stage403_stage079_xsmom_execution_margin_audit"
STAGE403_TAG = "stage403_stage079_xsmom_execution_margin_audit_v1"
STAGE352_MARGIN_PATH = (
    OUTPUT_DIR / "qmt_roll_stage352_xsmom_overlay_cash_multiperiod_margin_stage352_xsmom_overlay_cash_multiperiod_v1.csv"
)
STAGE370_STOCK_PATH = (
    OUTPUT_DIR / "qmt_roll_stage370_cross_asset_stock_paper_realism_audit_account_daily_stage370_cross_asset_stock_paper_realism_audit_v1.csv"
)

DAILY_PATH = OUTPUT_DIR / f"{STAGE411_PREFIX}_daily_{STAGE411_TAG}.csv"
SUMMARY_SOURCE_PATH = OUTPUT_DIR / f"{STAGE411_PREFIX}_summary_{STAGE411_TAG}.csv"
GATE_SOURCE_PATH = OUTPUT_DIR / f"{STAGE411_PREFIX}_gate_{STAGE411_TAG}.csv"
SCORE_SOURCE_PATH = OUTPUT_DIR / f"{STAGE411_PREFIX}_score_{STAGE411_TAG}.csv"
SATELLITE_SOURCE_PATH = OUTPUT_DIR / f"{STAGE403_PREFIX}_satellite_daily_{STAGE403_TAG}.csv"

ROLLING_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rolling_{MODEL_TAG}.csv"
PAIRWISE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pairwise_{MODEL_TAG}.csv"
BOOTSTRAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_block_bootstrap_{MODEL_TAG}.csv"
LIQUIDITY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_liquidity_margin_{MODEL_TAG}.csv"
TOPDAY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_top_edge_day_ablation_{MODEL_TAG}.csv"
YEAR_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_yearly_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

VARIANT_ORDER = [STAGE079_VARIANT, STAGE103_VARIANT, CASHYIELD_VARIANT, STAGE111_VARIANT]
LABELS = {
    STAGE079_VARIANT: "Stage079",
    STAGE103_VARIANT: "Stage103",
    CASHYIELD_VARIANT: "Stage103+Cash2%",
    STAGE111_VARIANT: "Stage111 Stock50k+Y",
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


def _max_drawdown(nav: np.ndarray) -> float:
    if len(nav) == 0:
        return 0.0
    peak = np.maximum.accumulate(nav)
    return float(np.min(nav / peak - 1.0) * 100.0)


def _ulcer(nav: np.ndarray) -> float:
    if len(nav) == 0:
        return 0.0
    peak = np.maximum.accumulate(nav)
    dd = np.minimum(nav / peak - 1.0, 0.0) * 100.0
    return float(np.sqrt(np.mean(dd**2)))


def _longest_underwater(nav: np.ndarray) -> int:
    if len(nav) == 0:
        return 0
    high = np.maximum.accumulate(nav)
    underwater = nav < high
    best = 0
    current = 0
    for item in underwater:
        if bool(item):
            current += 1
            best = max(best, current)
        else:
            current = 0
    return int(best)


def _metrics_from_returns(returns: np.ndarray) -> dict[str, float]:
    nav = ACCOUNT_CAPITAL * np.concatenate([[1.0], np.cumprod(1.0 + np.asarray(returns, dtype=float))])
    daily = np.asarray(returns, dtype=float)
    std = float(np.std(daily, ddof=1)) if len(daily) > 1 else 0.0
    sharpe = float(np.mean(daily) / std * math.sqrt(252.0)) if std > 0 else 0.0
    return {
        "total_return_pct": float((nav[-1] / ACCOUNT_CAPITAL - 1.0) * 100.0),
        "max_dd_pct": _max_drawdown(nav),
        "sharpe": sharpe,
        "ulcer_pct": _ulcer(nav),
    }


def _load_nav() -> pd.DataFrame:
    frame = pd.read_csv(DAILY_PATH, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    pivot = frame[frame["variant"].isin(VARIANT_ORDER)].pivot_table(
        index="date", columns="variant", values="nav", aggfunc="last"
    )
    pivot = pivot.sort_index().ffill()
    return pivot[VARIANT_ORDER].dropna()


def _segment_metrics(nav: pd.Series, start: int, window: int) -> dict[str, Any]:
    segment = nav.iloc[start : start + window + 1].to_numpy(dtype=float)
    rel = segment / segment[0]
    total = float((rel[-1] - 1.0) * 100.0)
    annualized = (1.0 + total / 100.0) ** (365.0 / window) - 1.0 if total > -100.0 else -1.0
    return {
        "return_pct": total,
        "annualized_return_pct": annualized * 100.0,
        "max_dd_pct": _max_drawdown(rel),
        "ulcer_pct": _ulcer(rel),
        "longest_underwater_days": _longest_underwater(rel),
    }


def _rolling(nav: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    windows = [21, 63, 90, 126, 180, 252, 504]
    rolling_rows: list[dict[str, Any]] = []
    pairwise_rows: list[dict[str, Any]] = []
    cache: dict[tuple[str, int], pd.DataFrame] = {}
    for variant in VARIANT_ORDER:
        series = nav[variant]
        for window in windows:
            rows: list[dict[str, Any]] = []
            for start in range(0, len(series) - window):
                metrics = _segment_metrics(series, start, window)
                rows.append(
                    {
                        "start_date": series.index[start],
                        "end_date": series.index[start + window],
                        "window_days": window,
                        **metrics,
                    }
                )
            frame = pd.DataFrame(rows)
            cache[(variant, window)] = frame
            rolling_rows.append(
                {
                    "variant": variant,
                    "label": LABELS[variant],
                    "window_days": window,
                    "count": len(frame),
                    "return_p01_pct": float(frame["return_pct"].quantile(0.01)),
                    "return_p05_pct": float(frame["return_pct"].quantile(0.05)),
                    "return_median_pct": float(frame["return_pct"].median()),
                    "positive_return_rate": float((frame["return_pct"] > 0.0).mean()),
                    "annualized_below_5pct_rate": float((frame["annualized_return_pct"] < 5.0).mean()),
                    "max_dd_worst_pct": float(frame["max_dd_pct"].min()),
                    "dd20_breach_rate": float((frame["max_dd_pct"] < -20.0).mean()),
                    "dd30_breach_rate": float((frame["max_dd_pct"] < -30.0).mean()),
                    "ulcer_p95_pct": float(frame["ulcer_pct"].quantile(0.95)),
                    "longest_underwater_p95_days": float(frame["longest_underwater_days"].quantile(0.95)),
                }
            )
    for window in windows:
        for reference in [STAGE079_VARIANT, STAGE103_VARIANT, CASHYIELD_VARIANT]:
            ref = cache[(reference, window)]
            cand = cache[(STAGE111_VARIANT, window)]
            pairwise_rows.append(
                {
                    "reference": reference,
                    "window_days": window,
                    "count": len(cand),
                    "return_win_rate": float((cand["return_pct"] > ref["return_pct"]).mean()),
                    "return_delta_median_pp": float((cand["return_pct"] - ref["return_pct"]).median()),
                    "return_delta_p05_pp": float((cand["return_pct"] - ref["return_pct"]).quantile(0.05)),
                    "maxdd_not_worse_rate": float((cand["max_dd_pct"] >= ref["max_dd_pct"]).mean()),
                    "ulcer_not_worse_rate": float((cand["ulcer_pct"] <= ref["ulcer_pct"]).mean()),
                    "underwater_not_worse_rate": float(
                        (cand["longest_underwater_days"] <= ref["longest_underwater_days"]).mean()
                    ),
                    "return_and_risk_not_worse_rate": float(
                        (
                            (cand["return_pct"] > ref["return_pct"])
                            & (cand["max_dd_pct"] >= ref["max_dd_pct"])
                            & (cand["ulcer_pct"] <= ref["ulcer_pct"])
                        ).mean()
                    ),
                }
            )
    return pd.DataFrame(rolling_rows), pd.DataFrame(pairwise_rows)


def _block_bootstrap(nav: pd.DataFrame) -> pd.DataFrame:
    returns = nav.pct_change().dropna()
    rng = np.random.default_rng(412111)
    rows: list[dict[str, Any]] = []
    n = len(returns)
    sims = 2000
    for block_len in [20, 60, 120]:
        samples: list[dict[str, Any]] = []
        for _ in range(sims):
            starts = rng.integers(0, max(n - block_len + 1, 1), size=int(math.ceil(n / block_len)))
            index = np.concatenate([np.arange(start, min(start + block_len, n)) for start in starts])[:n]
            sample: dict[str, Any] = {}
            for variant in VARIANT_ORDER:
                metrics = _metrics_from_returns(returns[variant].to_numpy(dtype=float)[index])
                sample[f"{variant}_return_pct"] = metrics["total_return_pct"]
                sample[f"{variant}_max_dd_pct"] = metrics["max_dd_pct"]
                sample[f"{variant}_ulcer_pct"] = metrics["ulcer_pct"]
            samples.append(sample)
        frame = pd.DataFrame(samples)
        for reference in [STAGE079_VARIANT, STAGE103_VARIANT, CASHYIELD_VARIANT]:
            rows.append(
                {
                    "reference": reference,
                    "block_len_days": block_len,
                    "sims": sims,
                    "return_win_rate": float((frame[f"{STAGE111_VARIANT}_return_pct"] > frame[f"{reference}_return_pct"]).mean()),
                    "maxdd_not_worse_rate": float((frame[f"{STAGE111_VARIANT}_max_dd_pct"] >= frame[f"{reference}_max_dd_pct"]).mean()),
                    "ulcer_not_worse_rate": float((frame[f"{STAGE111_VARIANT}_ulcer_pct"] <= frame[f"{reference}_ulcer_pct"]).mean()),
                    "return_delta_p05_pp": float(
                        (frame[f"{STAGE111_VARIANT}_return_pct"] - frame[f"{reference}_return_pct"]).quantile(0.05)
                    ),
                    "return_delta_median_pp": float(
                        (frame[f"{STAGE111_VARIANT}_return_pct"] - frame[f"{reference}_return_pct"]).median()
                    ),
                }
            )
    return pd.DataFrame(rows)


def _load_stock_equity(calendar: pd.DatetimeIndex) -> pd.Series:
    frame = pd.read_csv(STAGE370_STOCK_PATH, encoding="utf-8-sig")
    frame = frame[np.isclose(pd.to_numeric(frame["account_size_cny"], errors="coerce"), STOCK_CAPITAL)].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["equity_min_fee"] = pd.to_numeric(frame["equity_min_fee"], errors="coerce")
    equity = frame.dropna(subset=["date", "equity_min_fee"]).sort_values("date").set_index("date")["equity_min_fee"]
    nav = equity.reindex(calendar).ffill().fillna(1.0).astype(float)
    start_nav = float(nav.iloc[0])
    if start_nav <= 0.0:
        raise ValueError(f"invalid stock start nav {start_nav}")
    return nav / start_nav * STOCK_CAPITAL


def _liquidity_audit(nav: pd.DataFrame) -> pd.DataFrame:
    stage411_daily = pd.read_csv(DAILY_PATH, encoding="utf-8-sig")
    stage411_daily["date"] = pd.to_datetime(stage411_daily["date"], errors="coerce").dt.normalize()
    equity = stage411_daily.pivot_table(index="date", columns="variant", values="equity", aggfunc="last").sort_index().ffill()

    margin = pd.read_csv(STAGE352_MARGIN_PATH, encoding="utf-8-sig")
    margin["date"] = pd.to_datetime(margin["date"], errors="coerce").dt.normalize()
    margin = margin[margin["window_name"].eq("start_2020")].sort_values("date").drop_duplicates("date", keep="last")
    satellite = pd.read_csv(SATELLITE_SOURCE_PATH, encoding="utf-8-sig")
    satellite["date"] = pd.to_datetime(satellite["date"], errors="coerce").dt.normalize()
    satellite = satellite[
        satellite["window_name"].eq("start_2020") & satellite["variant"].eq(STAGE103_VARIANT)
    ].sort_values("date").drop_duplicates("date", keep="last")
    sat_margin = satellite.set_index("date")["satellite_margin"].astype(float)
    dates = pd.DatetimeIndex(margin["date"])
    base_margin = margin["c3_margin"].to_numpy(dtype=float) + sat_margin.reindex(dates).fillna(0.0).to_numpy(dtype=float)
    stock_equity = _load_stock_equity(dates)

    rows: list[dict[str, Any]] = []
    for variant in [STAGE103_VARIANT, CASHYIELD_VARIANT, STAGE111_VARIANT]:
        total_equity = equity[variant].reindex(dates).ffill().to_numpy(dtype=float)
        locked_stock = stock_equity.to_numpy(dtype=float) if variant == STAGE111_VARIANT else np.zeros(len(dates))
        liquid_equity = total_equity - locked_stock
        for multiplier in [1.00, 1.02, 1.05, 1.10]:
            required_margin = base_margin * multiplier
            total_ratio = required_margin / total_equity * 100.0
            liquid_ratio = required_margin / liquid_equity * 100.0
            liquid_over = liquid_ratio > 100.0
            total_over = total_ratio > 100.0
            first_liquid_reject = ""
            if bool(np.any(liquid_over)):
                first_liquid_reject = str(pd.Timestamp(dates[np.argmax(liquid_over)]).date())
            rows.append(
                {
                    "variant": variant,
                    "label": LABELS[variant],
                    "margin_multiplier": multiplier,
                    "stock_locked_not_marginable": int(variant == STAGE111_VARIANT),
                    "max_margin_to_total_equity_pct": float(np.nanmax(total_ratio)),
                    "max_margin_to_liquid_equity_pct": float(np.nanmax(liquid_ratio)),
                    "p95_margin_to_liquid_equity_pct": float(np.nanpercentile(liquid_ratio, 95)),
                    "total_equity_reject_days": int(np.sum(total_over)),
                    "liquid_equity_reject_days": int(np.sum(liquid_over)),
                    "first_liquid_reject_date": first_liquid_reject,
                    "required_extra_liquid_cash_for_no_reject": float(np.nanmax(np.maximum(required_margin - liquid_equity, 0.0))),
                    "min_liquid_free_cash_pct": float(100.0 - np.nanmax(liquid_ratio)),
                }
            )
    return pd.DataFrame(rows)


def _top_edge_day_ablation(nav: pd.DataFrame) -> pd.DataFrame:
    returns = nav.pct_change().dropna()
    delta = returns[STAGE111_VARIANT] - returns[STAGE103_VARIANT]
    top_dates = delta.sort_values(ascending=False).index
    rows: list[dict[str, Any]] = []
    stage103_metrics = _metrics_from_returns(returns[STAGE103_VARIANT].to_numpy(dtype=float))
    for remove_n in [0, 1, 3, 5, 10, 20, 40, 80, 120]:
        adjusted = returns[STAGE111_VARIANT].copy()
        if remove_n > 0:
            adjusted.loc[top_dates[:remove_n]] = returns.loc[top_dates[:remove_n], STAGE103_VARIANT]
        metrics = _metrics_from_returns(adjusted.to_numpy(dtype=float))
        rows.append(
            {
                "removed_top_relative_days": remove_n,
                "candidate_total_return_pct": metrics["total_return_pct"],
                "stage103_total_return_pct": stage103_metrics["total_return_pct"],
                "candidate_minus_stage103_return_pp": metrics["total_return_pct"] - stage103_metrics["total_return_pct"],
                "candidate_max_dd_pct": metrics["max_dd_pct"],
                "candidate_ulcer_pct": metrics["ulcer_pct"],
                "still_above_stage103_return": int(metrics["total_return_pct"] >= stage103_metrics["total_return_pct"]),
            }
        )
    return pd.DataFrame(rows)


def _yearly(nav: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for year, frame in nav.groupby(nav.index.year):
        if len(frame) < 2:
            continue
        for variant in VARIANT_ORDER:
            rel = frame[variant].to_numpy(dtype=float) / float(frame[variant].iloc[0])
            rows.append(
                {
                    "year": int(year),
                    "variant": variant,
                    "label": LABELS[variant],
                    "return_pct": float((rel[-1] - 1.0) * 100.0),
                    "max_dd_pct": _max_drawdown(rel),
                    "ulcer_pct": _ulcer(rel),
                }
            )
    result = pd.DataFrame(rows)
    base = result[result["variant"].eq(STAGE103_VARIANT)].set_index("year")
    result["return_delta_vs_stage103_pp"] = result.apply(
        lambda row: row["return_pct"] - _safe_float(base.loc[int(row["year"]), "return_pct"]) if int(row["year"]) in base.index else np.nan,
        axis=1,
    )
    return result


def _plot(pairwise: pd.DataFrame, bootstrap: pd.DataFrame, liquidity: pd.DataFrame, topday: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    focus = pairwise[pairwise["reference"].eq(STAGE103_VARIANT)].sort_values("window_days")
    axes[0, 0].plot(focus["window_days"], focus["return_win_rate"], marker="o", label="return win")
    axes[0, 0].plot(focus["window_days"], focus["maxdd_not_worse_rate"], marker="o", label="maxDD not worse")
    axes[0, 0].plot(focus["window_days"], focus["ulcer_not_worse_rate"], marker="o", label="Ulcer not worse")
    axes[0, 0].axhline(0.5, color="red", linestyle="--", linewidth=1)
    axes[0, 0].set_title("Stage111 vs Stage103 rolling rates")
    axes[0, 0].set_xlabel("Holding days")
    axes[0, 0].legend(fontsize=8)

    boot = bootstrap[bootstrap["reference"].eq(STAGE103_VARIANT)].sort_values("block_len_days")
    axes[0, 1].bar(boot["block_len_days"].astype(str), boot["return_win_rate"], color="#4c78a8")
    axes[0, 1].axhline(0.5, color="red", linestyle="--", linewidth=1)
    axes[0, 1].set_title("Bootstrap return win vs Stage103")

    liq = liquidity[liquidity["variant"].isin([STAGE103_VARIANT, STAGE111_VARIANT])]
    for variant, frame in liq.groupby("variant"):
        axes[1, 0].plot(frame["margin_multiplier"], frame["max_margin_to_liquid_equity_pct"], marker="o", label=LABELS[variant])
    axes[1, 0].axhline(100, color="red", linestyle="--", linewidth=1)
    axes[1, 0].set_title("Max margin / liquid futures equity")
    axes[1, 0].legend(fontsize=8)

    axes[1, 1].plot(topday["removed_top_relative_days"], topday["candidate_minus_stage103_return_pp"], marker="o")
    axes[1, 1].axhline(0, color="red", linestyle="--", linewidth=1)
    axes[1, 1].set_title("Top relative day ablation")
    axes[1, 1].set_xlabel("Removed days")
    axes[1, 1].set_ylabel("Return pp vs Stage103")
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(
    rolling: pd.DataFrame,
    pairwise: pd.DataFrame,
    bootstrap: pd.DataFrame,
    liquidity: pd.DataFrame,
    topday: pd.DataFrame,
    yearly: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    report = [
        "# Stage112 Stage111流动性与鲁棒性审计",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：只读审计；不修改 Stage079、Stage103 或股票策略。",
        "- 核心问题：Stage111 指标好，但股票槽位不能默认当作期货可用保证金。",
        f"- 图表：`{CHART_PATH}`",
        "",
        "## 决策",
        "",
        "```json",
        json.dumps(_json_safe(decision), ensure_ascii=False, indent=2),
        "```",
        "",
        "## Rolling 任意启动窗口",
        "",
        _md_table(rolling[rolling["variant"].isin([STAGE103_VARIANT, CASHYIELD_VARIANT, STAGE111_VARIANT])]),
        "",
        "## Stage111 Pairwise 胜率",
        "",
        _md_table(pairwise),
        "",
        "## Block Bootstrap",
        "",
        _md_table(bootstrap),
        "",
        "## 流动性保证金审计",
        "",
        _md_table(liquidity),
        "",
        "## 顶部相对贡献日剔除",
        "",
        _md_table(topday),
        "",
        "## 年度路径",
        "",
        _md_table(yearly[yearly["variant"].isin([STAGE103_VARIANT, STAGE111_VARIANT])]),
        "",
        "## 反过拟合判断",
        "",
        "- 本阶段不新增候选、不调股票金额、不调现金收益率，只拆解 Stage111 既有候选。",
        "- 若流动性口径失败，不能因为全周期指标漂亮而直接晋级。",
        "- 若继续研究股票槽位，只能固定 10 万 paper 做真实执行复核，不扫相邻金额。",
    ]
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    nav = _load_nav()
    rolling, pairwise = _rolling(nav)
    bootstrap = _block_bootstrap(nav)
    liquidity = _liquidity_audit(nav)
    topday = _top_edge_day_ablation(nav)
    yearly = _yearly(nav)

    liq_1x = liquidity[(liquidity["variant"].eq(STAGE111_VARIANT)) & (liquidity["margin_multiplier"].eq(1.0))].iloc[0]
    liq_110 = liquidity[(liquidity["variant"].eq(STAGE111_VARIANT)) & (liquidity["margin_multiplier"].eq(1.1))].iloc[0]
    roll_90_vs103 = pairwise[(pairwise["reference"].eq(STAGE103_VARIANT)) & (pairwise["window_days"].eq(90))].iloc[0]
    roll_180_vs103 = pairwise[(pairwise["reference"].eq(STAGE103_VARIANT)) & (pairwise["window_days"].eq(180))].iloc[0]
    boot60_vs103 = bootstrap[(bootstrap["reference"].eq(STAGE103_VARIANT)) & (bootstrap["block_len_days"].eq(60))].iloc[0]
    decision = {
        "stage": "Stage112",
        "line_id": LINE_ID,
        "decision": "retain_paper_research_candidate_but_reject_deployment_promotion",
        "reason": "Stage111 corrected best variant has stable risk/Ulcer edge but unstable return edge versus Stage103, and conservative liquid-futures-equity margin fails under broker10 because 5万股票不能默认当作期货保证金。",
        "stage111_liquid_1x_reject_days": int(liq_1x["liquid_equity_reject_days"]),
        "stage111_liquid_1x_required_extra_cash": _safe_float(liq_1x["required_extra_liquid_cash_for_no_reject"]),
        "stage111_liquid_110_reject_days": int(liq_110["liquid_equity_reject_days"]),
        "stage111_liquid_110_required_extra_cash": _safe_float(liq_110["required_extra_liquid_cash_for_no_reject"]),
        "roll90_return_win_vs_stage103": _safe_float(roll_90_vs103["return_win_rate"]),
        "roll180_return_win_vs_stage103": _safe_float(roll_180_vs103["return_win_rate"]),
        "bootstrap60_return_win_vs_stage103": _safe_float(boot60_vs103["return_win_rate"]),
        "chart": str(CHART_PATH),
    }

    rolling.to_csv(ROLLING_PATH, index=False, encoding="utf-8-sig")
    pairwise.to_csv(PAIRWISE_PATH, index=False, encoding="utf-8-sig")
    bootstrap.to_csv(BOOTSTRAP_PATH, index=False, encoding="utf-8-sig")
    liquidity.to_csv(LIQUIDITY_PATH, index=False, encoding="utf-8-sig")
    topday.to_csv(TOPDAY_PATH, index=False, encoding="utf-8-sig")
    yearly.to_csv(YEAR_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _plot(pairwise, bootstrap, liquidity, topday)
    _write_report(rolling, pairwise, bootstrap, liquidity, topday, yearly, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"report={REPORT_PATH}")


if __name__ == "__main__":
    main()
