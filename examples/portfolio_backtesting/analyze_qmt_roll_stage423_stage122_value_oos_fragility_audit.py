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

MODEL_TAG = "stage423_stage122_value_oos_fragility_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage423_stage122_value_oos_fragility_audit"
SOURCE_TAG = "stage422_stage103_long_value_proxy_overlay_v1"
SOURCE_PREFIX = "qmt_roll_stage422_stage103_long_value_proxy_overlay"
LINE_ID = "futures_trend_drawdown30_preserve_return"

ACCOUNT_CAPITAL = 615_000.0
BASELINE_VARIANT = "stage079"
STAGE103_VARIANT = "xsmom_vt10_q_momq_round_half_true_broker10_guard"
VALUE756_VARIANT = "stage103_plus_value_proxy756_monthly_guard"
VALUE504_VARIANT = "stage103_plus_value_proxy504_monthly_guard"

STAGE079_RETURN = 4947.260163
STAGE079_MAX_DD = -29.700717
STAGE079_SHARPE = 1.3182
STAGE079_ULCER = 15.0931

DAILY_IN = OUTPUT_DIR / f"{SOURCE_PREFIX}_daily_{SOURCE_TAG}.csv"
OVERLAY_IN = OUTPUT_DIR / f"{SOURCE_PREFIX}_overlay_daily_{SOURCE_TAG}.csv"
VALUE_SCORE_IN = OUTPUT_DIR / f"{SOURCE_PREFIX}_value_scores_{SOURCE_TAG}.csv"
MARGIN_IN = OUTPUT_DIR / f"{SOURCE_PREFIX}_margin_audit_{SOURCE_TAG}.csv"
FRESH_IN = OUTPUT_DIR / f"{SOURCE_PREFIX}_fresh_start_{SOURCE_TAG}.csv"
TOPDAY_IN = OUTPUT_DIR / f"{SOURCE_PREFIX}_top_edge_day_ablation_{SOURCE_TAG}.csv"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
ACTIVATION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_activation_coverage_{MODEL_TAG}.csv"
ACTIVE_PAIRWISE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_active_pairwise_{MODEL_TAG}.csv"
YEAR_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_contribution_{MODEL_TAG}.csv"
ABLATION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_ablation_{MODEL_TAG}.csv"
BOOTSTRAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bootstrap_{MODEL_TAG}.csv"
MARGIN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_margin_fragility_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


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
        return "_空_"
    show = frame if max_rows is None else frame.head(max_rows)
    return show.to_markdown(index=False)


def _drawdown(nav: np.ndarray) -> np.ndarray:
    return nav / np.maximum.accumulate(nav) - 1.0


def _ulcer(nav: np.ndarray) -> float:
    dd_pct = np.minimum(_drawdown(nav), 0.0) * 100.0
    return float(np.sqrt(np.mean(dd_pct**2))) if len(dd_pct) else np.nan


def _stats_from_equity(equity: pd.Series, label: str, base_equity: float | None = None) -> dict[str, Any]:
    equity = equity.dropna().astype(float)
    if equity.empty:
        return {"label": label}
    base = float(equity.iloc[0]) if base_equity is None else float(base_equity)
    nav = equity.to_numpy(dtype=float) / base
    daily_ret = equity.pct_change().dropna()
    sharpe = np.nan
    if len(daily_ret) and float(daily_ret.std(ddof=0)) > 0:
        sharpe = float(daily_ret.mean() / daily_ret.std(ddof=0) * math.sqrt(252.0))
    return {
        "label": label,
        "start_date": equity.index.min().date().isoformat(),
        "end_date": equity.index.max().date().isoformat(),
        "days": int(len(equity)),
        "base_equity": base,
        "start_equity": float(equity.iloc[0]),
        "end_equity": float(equity.iloc[-1]),
        "total_return_pct": (float(equity.iloc[-1]) / base - 1.0) * 100.0,
        "max_dd_pct": float(_drawdown(nav).min() * 100.0),
        "sharpe": sharpe,
        "ulcer_pct": _ulcer(nav),
    }


def _full_stats_from_pnl(pnl: pd.Series, label: str) -> dict[str, Any]:
    pnl = pnl.fillna(0.0).astype(float)
    equity = ACCOUNT_CAPITAL + pnl.cumsum()
    return _stats_from_equity(equity, label, ACCOUNT_CAPITAL)


def _calendarize(frame: pd.DataFrame) -> pd.DataFrame:
    clean = frame[["date", "equity"]].copy()
    clean["date"] = pd.to_datetime(clean["date"]).dt.normalize()
    clean = clean.sort_values("date").drop_duplicates("date", keep="last").set_index("date")
    idx = pd.date_range(clean.index.min(), clean.index.max(), freq="D")
    clean = clean.reindex(idx).ffill()
    clean.index.name = "date"
    return clean.reset_index()


def _daily_pnl(frame: pd.DataFrame) -> pd.Series:
    ordered = frame.sort_index()
    return ordered["equity"].diff().fillna(ordered["equity"].iloc[0] - ACCOUNT_CAPITAL)


def _load_inputs() -> dict[str, pd.DataFrame]:
    required = [DAILY_IN, OVERLAY_IN, VALUE_SCORE_IN, MARGIN_IN, FRESH_IN, TOPDAY_IN]
    missing = [path for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(f"missing Stage422 outputs: {missing}")
    daily = pd.read_csv(DAILY_IN, parse_dates=["date"])
    overlay = pd.read_csv(OVERLAY_IN, parse_dates=["date"])
    scores = pd.read_csv(VALUE_SCORE_IN, parse_dates=["date"])
    margin = pd.read_csv(MARGIN_IN)
    fresh = pd.read_csv(FRESH_IN)
    topday = pd.read_csv(TOPDAY_IN)
    for frame in (daily, overlay, scores):
        frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    return {
        "daily": daily,
        "overlay": overlay,
        "scores": scores,
        "margin": margin,
        "fresh": fresh,
        "topday": topday,
    }


def _activation_coverage(scores: pd.DataFrame, overlay: pd.DataFrame) -> tuple[pd.DataFrame, pd.Timestamp]:
    value_scores = scores[scores["variant"].eq(VALUE756_VARIANT)].copy()
    coverage = (
        value_scores.groupby("date")
        .agg(
            valid_product_count=("value_score", lambda s: int(s.notna().sum())),
            total_product_count=("product_vt_symbol", "nunique"),
        )
        .reset_index()
        .sort_values("date")
    )
    coverage["has_top_bottom_3"] = (coverage["valid_product_count"] >= 6).astype(int)
    active = overlay[
        overlay["variant"].eq(VALUE756_VARIANT)
        & overlay["window_name"].eq("start_2020")
        & (
            overlay["overlay_daily_pnl"].ne(0)
            | overlay["overlay_turnover_contracts"].ne(0)
            | overlay["overlay_held_contract_count"].ne(0)
            | overlay["overlay_margin"].ne(0)
        )
    ].copy()
    active_start = pd.Timestamp(active["date"].min())
    active_end = pd.Timestamp(active["date"].max())
    coverage["year"] = coverage["date"].dt.year
    by_year = (
        coverage.groupby("year")
        .agg(
            score_days=("date", "count"),
            days_with_6plus_products=("has_top_bottom_3", "sum"),
            min_valid_products=("valid_product_count", "min"),
            median_valid_products=("valid_product_count", "median"),
            max_valid_products=("valid_product_count", "max"),
        )
        .reset_index()
    )
    by_year["candidate_variant"] = VALUE756_VARIANT
    by_year["active_start"] = active_start.date().isoformat()
    by_year["active_end"] = active_end.date().isoformat()
    by_year["lookback_days"] = 756
    by_year["coverage_6plus_rate"] = by_year["days_with_6plus_products"] / by_year["score_days"]
    return by_year, active_start


def _active_pairwise(daily: pd.DataFrame, active_start: pd.Timestamp) -> pd.DataFrame:
    full = daily[daily["window_name"].eq("start_2020")].copy()
    by_variant = {
        variant: _calendarize(frame).set_index("date")
        for variant, frame in full[full["variant"].isin([BASELINE_VARIANT, STAGE103_VARIANT, VALUE756_VARIANT])].groupby(
            "variant"
        )
    }
    rows: list[dict[str, Any]] = []
    candidate = by_variant[VALUE756_VARIANT]
    for comparator_variant in [BASELINE_VARIANT, STAGE103_VARIANT]:
        comparator = by_variant[comparator_variant]
        common = candidate[["equity"]].rename(columns={"equity": "candidate_equity"}).join(
            comparator[["equity"]].rename(columns={"equity": "comparator_equity"}),
            how="inner",
        )
        common = common[common.index >= active_start]
        for window_days in (90, 180, 252, 504):
            deltas: list[float] = []
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
                deltas.append(c_ret - b_ret)
                maxdd_not_worse.append(int(c_dd >= b_dd - 1e-12))
                ulcer_not_worse.append(int(c_ulcer <= b_ulcer + 1e-12))
            arr = np.asarray(deltas, dtype=float)
            rows.append(
                {
                    "candidate_variant": VALUE756_VARIANT,
                    "comparator_variant": comparator_variant,
                    "window_days": window_days,
                    "active_start_filter": active_start.date().isoformat(),
                    "count": int(len(arr)),
                    "return_win_rate": float(np.mean(arr >= -1e-12)) if len(arr) else np.nan,
                    "return_delta_median_pp": float(np.median(arr)) if len(arr) else np.nan,
                    "return_delta_p05_pp": float(np.percentile(arr, 5)) if len(arr) else np.nan,
                    "maxdd_not_worse_rate": float(np.mean(maxdd_not_worse)) if maxdd_not_worse else np.nan,
                    "ulcer_not_worse_rate": float(np.mean(ulcer_not_worse)) if ulcer_not_worse else np.nan,
                }
            )
    return pd.DataFrame(rows)


def _edge_series(daily: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    full = daily[daily["window_name"].eq("start_2020")].copy()
    frames = {}
    for variant in (STAGE103_VARIANT, VALUE756_VARIANT):
        frame = full[full["variant"].eq(variant)].copy()
        frame = frame.sort_values("date").drop_duplicates("date", keep="last").set_index("date")
        frames[variant] = frame
    common = frames[VALUE756_VARIANT][["equity"]].rename(columns={"equity": "candidate_equity"}).join(
        frames[STAGE103_VARIANT][["equity"]].rename(columns={"equity": "stage103_equity"}), how="inner"
    )
    c_pnl = _daily_pnl(frames[VALUE756_VARIANT])
    b_pnl = _daily_pnl(frames[STAGE103_VARIANT])
    edge = c_pnl.reindex(common.index).fillna(0.0) - b_pnl.reindex(common.index).fillna(0.0)
    common["candidate_pnl"] = c_pnl.reindex(common.index).fillna(0.0)
    common["stage103_pnl"] = b_pnl.reindex(common.index).fillna(0.0)
    common["edge_pnl"] = edge
    common["year"] = common.index.year
    return common, edge


def _summary(daily: pd.DataFrame, active_start: pd.Timestamp) -> pd.DataFrame:
    full = daily[daily["window_name"].eq("start_2020")].copy()
    rows = []
    for variant in (BASELINE_VARIANT, STAGE103_VARIANT, VALUE756_VARIANT):
        frame = full[full["variant"].eq(variant)].copy().sort_values("date").set_index("date")
        rows.append({"variant": variant, "sample": "full", **_full_stats_from_pnl(_daily_pnl(frame), variant)})
        active = frame[frame.index >= active_start]
        rows.append({"variant": variant, "sample": "post_value_active", **_stats_from_equity(active["equity"], variant)})
    return pd.DataFrame(rows)


def _year_contribution(daily: pd.DataFrame, overlay: pd.DataFrame, active_start: pd.Timestamp) -> pd.DataFrame:
    common, edge = _edge_series(daily)
    active = common[common.index >= active_start].copy()
    overlay_full = overlay[
        overlay["window_name"].eq("start_2020") & overlay["variant"].eq(VALUE756_VARIANT)
    ].copy()
    overlay_full = overlay_full.set_index("date")
    active["overlay_slippage"] = overlay_full["overlay_slippage_cost"].reindex(active.index).fillna(0.0)
    active["overlay_turnover"] = overlay_full["overlay_turnover_contracts"].reindex(active.index).fillna(0.0)
    active["active_position_day"] = (
        overlay_full["overlay_held_contract_count"].reindex(active.index).fillna(0.0).gt(0).astype(int)
    )
    total_edge = float(active["edge_pnl"].sum())
    rows = []
    for year, frame in active.groupby("year"):
        rows.append(
            {
                "year": int(year),
                "calendar_days": int(len(frame)),
                "active_position_days": int(frame["active_position_day"].sum()),
                "edge_pnl": float(frame["edge_pnl"].sum()),
                "edge_pnl_share": float(frame["edge_pnl"].sum() / total_edge) if total_edge else np.nan,
                "positive_edge_day_rate": float((frame["edge_pnl"] > 0).mean()),
                "overlay_slippage": float(frame["overlay_slippage"].sum()),
                "overlay_turnover": float(frame["overlay_turnover"].sum()),
            }
        )
    return pd.DataFrame(rows)


def _year_ablation(daily: pd.DataFrame, active_start: pd.Timestamp) -> pd.DataFrame:
    common, edge = _edge_series(daily)
    candidate_pnl = common["candidate_pnl"].copy()
    stage103_stats = _full_stats_from_pnl(common["stage103_pnl"], "stage103")
    masks: dict[str, pd.Series] = {}
    for year in sorted(common.loc[common.index >= active_start, "year"].unique()):
        masks[f"remove_{int(year)}"] = common["year"].eq(year)
    masks["remove_2024_2025"] = common["year"].isin([2024, 2025])
    masks["remove_first_12m_after_activation"] = (common.index >= active_start) & (
        common.index < active_start + pd.DateOffset(months=12)
    )
    rows = []
    for label, mask in masks.items():
        adjusted_pnl = candidate_pnl.copy()
        adjusted_pnl.loc[mask] = adjusted_pnl.loc[mask] - edge.loc[mask]
        stats = _full_stats_from_pnl(adjusted_pnl, label)
        rows.append(
            {
                "ablation": label,
                **stats,
                "removed_edge_pnl": float(edge.loc[mask].sum()),
                "return_delta_vs_stage103_pp": float(stats["total_return_pct"] - stage103_stats["total_return_pct"]),
                "hard_pass_stage079_core": int(
                    stats["total_return_pct"] >= STAGE079_RETURN - 1e-9
                    and stats["max_dd_pct"] >= STAGE079_MAX_DD - 1e-9
                    and stats["sharpe"] >= STAGE079_SHARPE - 1e-9
                    and stats["ulcer_pct"] <= STAGE079_ULCER + 1e-9
                ),
            }
        )
    return pd.DataFrame(rows)


def _bootstrap(edge: pd.Series, active_start: pd.Timestamp) -> pd.DataFrame:
    active = edge[edge.index >= active_start].astype(float)
    values = active.to_numpy(dtype=float)
    rng = np.random.default_rng(423)
    rows = []
    if len(values) == 0:
        return pd.DataFrame()
    for block_len in (20, 60, 120):
        sims = []
        for _ in range(3000):
            pieces = []
            while sum(len(piece) for piece in pieces) < len(values):
                start = int(rng.integers(0, max(1, len(values) - block_len + 1)))
                pieces.append(values[start : start + block_len])
            sampled = np.concatenate(pieces)[: len(values)]
            sims.append(float(sampled.sum()))
        arr = np.asarray(sims, dtype=float)
        rows.append(
            {
                "block_len_days": block_len,
                "sim_count": int(len(arr)),
                "observed_edge_pnl": float(values.sum()),
                "prob_positive_edge": float(np.mean(arr > 0)),
                "p01_edge_pnl": float(np.percentile(arr, 1)),
                "p05_edge_pnl": float(np.percentile(arr, 5)),
                "median_edge_pnl": float(np.median(arr)),
                "p95_edge_pnl": float(np.percentile(arr, 95)),
            }
        )
    return pd.DataFrame(rows)


def _margin_fragility(margin: pd.DataFrame) -> pd.DataFrame:
    focus = margin[
        margin["window_name"].isin(
            ["start_2020", "start_2021", "start_2022", "start_2023", "start_2024", "start_2025", "phase_2024_2025"]
        )
        & margin["variant"].isin([STAGE103_VARIANT, VALUE756_VARIANT])
        & margin["margin_multiplier"].eq(1.10)
    ].copy()
    stage = focus[focus["variant"].eq(STAGE103_VARIANT)].set_index("window_name")
    value = focus[focus["variant"].eq(VALUE756_VARIANT)].set_index("window_name")
    rows = []
    for window in sorted(set(stage.index) & set(value.index)):
        s = stage.loc[window]
        v = value.loc[window]
        rows.append(
            {
                "window_name": window,
                "stage103_max_margin_to_equity_pct": float(s["max_margin_to_equity_pct"]),
                "value756_max_margin_to_equity_pct": float(v["max_margin_to_equity_pct"]),
                "stage103_reject_days": int(s["reject_days_over_100pct"]),
                "value756_reject_days": int(v["reject_days_over_100pct"]),
                "reject_days_delta": int(v["reject_days_over_100pct"]) - int(s["reject_days_over_100pct"]),
                "stage103_required_extra_cash": float(s["required_extra_cash_for_no_reject"]),
                "value756_required_extra_cash": float(v["required_extra_cash_for_no_reject"]),
                "extra_cash_delta": float(v["required_extra_cash_for_no_reject"])
                - float(s["required_extra_cash_for_no_reject"]),
                "value_worse_than_stage103": int(
                    int(v["reject_days_over_100pct"]) > int(s["reject_days_over_100pct"])
                    or float(v["required_extra_cash_for_no_reject"]) > float(s["required_extra_cash_for_no_reject"]) + 1e-9
                ),
            }
        )
    return pd.DataFrame(rows)


def _top_concentration(topday: pd.DataFrame) -> pd.DataFrame:
    focus = topday[
        topday["candidate_variant"].eq(VALUE756_VARIANT) & topday["comparator_variant"].eq(STAGE103_VARIANT)
    ].copy()
    base_delta = float(focus[focus["removed_top_positive_edge_days"].eq(0)]["adjusted_return_delta_pp"].iloc[0])
    focus["base_return_delta_pp"] = base_delta
    focus["delta_retention_rate"] = focus["adjusted_return_delta_pp"] / base_delta if base_delta else np.nan
    return focus


def _make_decision(
    activation: pd.DataFrame,
    active_pairwise: pd.DataFrame,
    year_contrib: pd.DataFrame,
    ablation: pd.DataFrame,
    bootstrap: pd.DataFrame,
    margin_fragility: pd.DataFrame,
    active_start: pd.Timestamp,
) -> dict[str, Any]:
    active_days = int(year_contrib["calendar_days"].sum())
    effective_position_days = int(year_contrib["active_position_days"].sum())
    years_with_120_active_days = int((year_contrib["active_position_days"] >= 120).sum())
    data_sufficiency_pass = bool(effective_position_days >= 756 and years_with_120_active_days >= 3)
    pw_stage103 = active_pairwise[active_pairwise["comparator_variant"].eq(STAGE103_VARIANT)]
    active_rolling_return_pass = bool(
        not pw_stage103.empty
        and pw_stage103[pw_stage103["window_days"].isin([90, 180, 252])]["return_win_rate"].min() >= 0.60
    )
    oos_years = year_contrib[year_contrib["year"].isin([2024, 2025])]
    oos_year_pass = bool(len(oos_years) == 2 and (oos_years["edge_pnl"] > 0).all())
    ablation_pass = bool((ablation["return_delta_vs_stage103_pp"] > 0).all())
    bootstrap_pass = bool((bootstrap["p05_edge_pnl"] > 0).all())
    margin_no_worse_pass = bool(margin_fragility["value_worse_than_stage103"].sum() == 0)
    if data_sufficiency_pass and active_rolling_return_pass and oos_year_pass and bootstrap_pass and margin_no_worse_pass:
        decision = "advance_to_execution_reaudit"
    elif active_rolling_return_pass and oos_year_pass and ablation_pass:
        decision = "retain_research_candidate_reject_execution_promotion"
    else:
        decision = "downgrade_to_research_memory"
    return {
        "stage": "Stage123",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "candidate": VALUE756_VARIANT,
        "decision": decision,
        "active_start": active_start.date().isoformat(),
        "active_days": active_days,
        "effective_position_days": effective_position_days,
        "years_with_120_active_days": years_with_120_active_days,
        "data_sufficiency_pass": data_sufficiency_pass,
        "active_rolling_return_pass": active_rolling_return_pass,
        "oos_year_pass": oos_year_pass,
        "ablation_pass": ablation_pass,
        "bootstrap_p05_positive_pass": bootstrap_pass,
        "margin_no_worse_than_stage103_pass": margin_no_worse_pass,
        "judgement": "value756有真实研究增量，但有效样本和broker10保证金尚不足以执行晋级。",
        "chart": str(CHART_PATH),
    }


def _plot(year: pd.DataFrame, active_pairwise: pd.DataFrame, margin_fragility: pd.DataFrame, edge: pd.Series) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(15, 9))
    active_edge = edge[edge != 0].copy()
    cum = edge.cumsum()
    axes[0, 0].plot(cum.index, cum.values, linewidth=1.2)
    axes[0, 0].axhline(0, color="#777777", linestyle="--", linewidth=0.8)
    axes[0, 0].set_title("Cumulative edge pnl vs Stage103")

    axes[0, 1].bar(year["year"].astype(str), year["edge_pnl"])
    axes[0, 1].axhline(0, color="#777777", linestyle="--", linewidth=0.8)
    axes[0, 1].set_title("Edge pnl by year")

    pw = active_pairwise[active_pairwise["comparator_variant"].eq(STAGE103_VARIANT)]
    axes[1, 0].plot(pw["window_days"], pw["return_win_rate"], marker="o", label="return win")
    axes[1, 0].plot(pw["window_days"], pw["maxdd_not_worse_rate"], marker="o", label="maxDD not worse")
    axes[1, 0].plot(pw["window_days"], pw["ulcer_not_worse_rate"], marker="o", label="Ulcer not worse")
    axes[1, 0].axhline(0.5, color="#777777", linestyle="--", linewidth=0.8)
    axes[1, 0].set_ylim(0, 1.05)
    axes[1, 0].set_title("Active-period rolling vs Stage103")
    axes[1, 0].legend(fontsize=8)

    margin_show = margin_fragility.sort_values("window_name")
    x = np.arange(len(margin_show))
    axes[1, 1].bar(x - 0.18, margin_show["stage103_reject_days"], width=0.36, label="Stage103")
    axes[1, 1].bar(x + 0.18, margin_show["value756_reject_days"], width=0.36, label="Value756")
    axes[1, 1].set_xticks(x)
    axes[1, 1].set_xticklabels(margin_show["window_name"], rotation=35, ha="right", fontsize=8)
    axes[1, 1].set_title("Broker10 reject days")
    axes[1, 1].legend(fontsize=8)
    fig.suptitle("Stage123 value756 OOS and fragility audit", fontsize=14)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    activation: pd.DataFrame,
    active_pairwise: pd.DataFrame,
    year: pd.DataFrame,
    ablation: pd.DataFrame,
    bootstrap: pd.DataFrame,
    margin_fragility: pd.DataFrame,
    top_concentration: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    report = [
        "# Stage123 Stage122 Value756 OOS与脆弱性审计",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：固定 Stage122 的 `value756` 做反证审计；不新增策略参数，不扫 lookback、top_n、调仓频率、品种或日期。",
        "- 审计目标：确认 Stage122 的收益增量是否来自足够长、足够分散、保证金可执行的样本，而不是后半段单一路径。",
        "- 外部依据：长期 value/contrarian 是期货策略族中的可解释方向，但商品长期反转文献并不稳定；PBO/CSCV 研究提示最优回测必须做 OOS 和组合切分反证。",
        f"- 图表：`{CHART_PATH}`",
        "",
        "## 决策",
        "",
        "```json",
        json.dumps(_json_safe(decision), ensure_ascii=False, indent=2),
        "```",
        "",
        "## 全样本与激活后样本",
        "",
        _md_table(summary),
        "",
        "## value756信号覆盖",
        "",
        _md_table(activation),
        "",
        "## 激活后任意启动滚动窗口",
        "",
        _md_table(active_pairwise),
        "",
        "## 年度边际贡献",
        "",
        _md_table(year),
        "",
        "## 年份贡献剔除",
        "",
        _md_table(ablation),
        "",
        "## Block Bootstrap边际贡献",
        "",
        _md_table(bootstrap),
        "",
        "## Broker10保证金脆弱性",
        "",
        _md_table(margin_fragility),
        "",
        "## 顶部贡献日集中度",
        "",
        _md_table(top_concentration),
        "",
        "## 反过拟合判断",
        "",
        "- 本阶段不是过拟合，因为没有新增规则或二次调参，只拆解固定候选的样本覆盖、OOS、贡献集中度和保证金脆弱性。",
        "- 当前不能执行晋级，因为有效激活样本少于一个756日完整周期，且 `start_2020` broker10 相对 Stage103 更脆弱。",
        "- 继续围绕 `504/756/1008`、top_n、调仓频率、日期/品种过滤或保证金小数救援会转向过拟合。",
    ]
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    data = _load_inputs()
    activation, active_start = _activation_coverage(data["scores"], data["overlay"])
    active_pairwise = _active_pairwise(data["daily"], active_start)
    summary = _summary(data["daily"], active_start)
    year = _year_contribution(data["daily"], data["overlay"], active_start)
    ablation = _year_ablation(data["daily"], active_start)
    common, edge = _edge_series(data["daily"])
    bootstrap = _bootstrap(edge, active_start)
    margin_fragility = _margin_fragility(data["margin"])
    top_concentration = _top_concentration(data["topday"])
    decision = _make_decision(
        activation,
        active_pairwise,
        year,
        ablation,
        bootstrap,
        margin_fragility,
        active_start,
    )
    _plot(year, active_pairwise, margin_fragility, edge)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    activation.to_csv(ACTIVATION_PATH, index=False, encoding="utf-8-sig")
    active_pairwise.to_csv(ACTIVE_PAIRWISE_PATH, index=False, encoding="utf-8-sig")
    year.to_csv(YEAR_PATH, index=False, encoding="utf-8-sig")
    ablation.to_csv(ABLATION_PATH, index=False, encoding="utf-8-sig")
    bootstrap.to_csv(BOOTSTRAP_PATH, index=False, encoding="utf-8-sig")
    margin_fragility.to_csv(MARGIN_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(summary, activation, active_pairwise, year, ablation, bootstrap, margin_fragility, top_concentration, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"report={REPORT_PATH}")


if __name__ == "__main__":
    main()
