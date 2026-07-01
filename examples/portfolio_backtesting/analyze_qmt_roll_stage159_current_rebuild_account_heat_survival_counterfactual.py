from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage156_current_rebuild_three_arm_annual_baseline as s156
import analyze_qmt_roll_stage157_current_rebuild_c9_stop_retry_attribution as s157


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage159"
MODEL_TAG = "stage159_current_rebuild_account_heat_survival_counterfactual_v1"
OUTPUT_PREFIX = "qmt_roll_stage159_current_rebuild_account_heat_survival_counterfactual"

DAILY_DELTA_PATH = s157.DAILY_DELTA_PATH

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
AGG_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_aggregate_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

CAPITAL = float(s156.CAPITAL)


@dataclass(frozen=True)
class OverlayVariant:
    arm: str
    source: str
    heat_cap: float | None = None
    peak_guard_min_peak_multiple: float | None = None
    peak_guard_drawdown_trigger_pct: float | None = None
    peak_guard_scale: float | None = None
    note: str = ""


VARIANTS: tuple[OverlayVariant, ...] = (
    OverlayVariant(
        arm="c4_reference_broker10_cap",
        source="c4",
        note="Stage819/C4 broker10 cap reference from Stage157 daily output.",
    ),
    OverlayVariant(
        arm="c9_baseline_stop_retry",
        source="c9",
        note="Stage847/C9 stop retry baseline from Stage157 daily output.",
    ),
    OverlayVariant(
        arm="c9_heat90_nextday_soft_scale",
        source="c9",
        heat_cap=90.0,
        note=(
            "Proxy: if previous simulated broker10 heat is above 90%, scale the next day's C9 PnL "
            "and estimated margin by 90/previous_heat."
        ),
    ),
    OverlayVariant(
        arm="c9_heat80_nextday_soft_scale",
        source="c9",
        heat_cap=80.0,
        note=(
            "Proxy: if previous simulated broker10 heat is above 80%, scale the next day's C9 PnL "
            "and estimated margin by 80/previous_heat."
        ),
    ),
    OverlayVariant(
        arm="c9_heat90_peak_dd10_scale70",
        source="c9",
        heat_cap=90.0,
        peak_guard_min_peak_multiple=2.0,
        peak_guard_drawdown_trigger_pct=-10.0,
        peak_guard_scale=0.70,
        note=(
            "Proxy: heat90 plus high-water giveback guard; once equity peak exceeds 2x capital and "
            "current drawdown is worse than -10%, cap next-day scale at 70%."
        ),
    ),
)


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    values = pd.to_numeric(equity, errors="coerce").ffill()
    peak = values.cummax()
    return (values / peak.replace(0.0, np.nan) - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0) * 100.0


def _daily_sharpe(equity: pd.Series) -> float:
    returns = pd.to_numeric(equity, errors="coerce").pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    if returns.empty:
        return 0.0
    std = float(returns.std(ddof=1))
    if std <= 0.0 or np.isnan(std):
        return 0.0
    return float(returns.mean() / std * np.sqrt(252.0))


def _source_columns(source: str) -> tuple[str, str, str, str, str]:
    return (
        f"account_equity_{source}",
        f"net_pnl_{source}",
        f"broker10_margin_to_equity_pct_{source}",
        f"trade_count_{source}",
        f"slippage_{source}",
    )


def _prepared_source(group: pd.DataFrame, source: str) -> pd.DataFrame:
    equity_col, pnl_col, heat_col, trade_col, slip_col = _source_columns(source)
    frame = group[
        [
            "date",
            "requested_start",
            "requested_start_month",
            "requested_end",
            equity_col,
            pnl_col,
            heat_col,
            trade_col,
            slip_col,
        ]
    ].copy()
    frame = frame.rename(
        columns={
            equity_col: "raw_equity",
            pnl_col: "raw_net_pnl",
            heat_col: "raw_broker10_margin_to_equity_pct",
            trade_col: "raw_trade_count",
            slip_col: "raw_slippage",
        }
    )
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    for column in [
        "raw_equity",
        "raw_net_pnl",
        "raw_broker10_margin_to_equity_pct",
        "raw_trade_count",
        "raw_slippage",
    ]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)
    return frame


def _scale_for_next_day(
    *,
    variant: OverlayVariant,
    previous_heat: float,
    previous_equity: float,
    previous_peak: float,
) -> float:
    scale = 1.0
    if variant.heat_cap is not None and previous_heat > variant.heat_cap > 0.0:
        scale = min(scale, max(0.0, variant.heat_cap / previous_heat))
    if (
        variant.peak_guard_min_peak_multiple is not None
        and variant.peak_guard_drawdown_trigger_pct is not None
        and variant.peak_guard_scale is not None
        and previous_peak >= CAPITAL * variant.peak_guard_min_peak_multiple
        and previous_peak > 0.0
    ):
        previous_dd = (previous_equity / previous_peak - 1.0) * 100.0
        if previous_dd <= variant.peak_guard_drawdown_trigger_pct:
            scale = min(scale, max(0.0, min(1.0, variant.peak_guard_scale)))
    return float(scale)


def _simulate_variant(group: pd.DataFrame, variant: OverlayVariant) -> pd.DataFrame:
    raw = _prepared_source(group, variant.source)
    if raw.empty:
        return pd.DataFrame()

    adjusted_equity: list[float] = []
    adjusted_heat: list[float] = []
    applied_scale: list[float] = []
    heat_signal: list[float] = []

    equity = CAPITAL
    peak = CAPITAL
    previous_heat = 0.0
    for idx, row in raw.iterrows():
        if idx == 0:
            scale = 1.0
            pnl = float(row["raw_equity"]) - CAPITAL
        else:
            scale = _scale_for_next_day(
                variant=variant,
                previous_heat=previous_heat,
                previous_equity=equity,
                previous_peak=peak,
            )
            pnl = float(row["raw_net_pnl"]) * scale
        equity = float(equity + pnl)
        peak = max(peak, equity)

        raw_equity = max(float(row["raw_equity"]), 1e-9)
        raw_margin = float(row["raw_broker10_margin_to_equity_pct"]) / 100.0 * raw_equity
        scaled_margin = raw_margin * scale
        heat = float(scaled_margin / max(equity, 1e-9) * 100.0)

        adjusted_equity.append(equity)
        adjusted_heat.append(heat)
        applied_scale.append(scale)
        heat_signal.append(previous_heat)
        previous_heat = heat

    result = raw.copy()
    result["stage"] = STAGE
    result["model_tag"] = MODEL_TAG
    result["line_id"] = LINE_ID
    result["arm"] = variant.arm
    result["source"] = variant.source
    result["adjusted_equity"] = adjusted_equity
    result["adjusted_broker10_margin_to_equity_pct"] = adjusted_heat
    result["applied_scale"] = applied_scale
    result["previous_adjusted_heat_signal"] = heat_signal
    result["adjusted_net_pnl"] = result["adjusted_equity"].diff().fillna(result["adjusted_equity"] - CAPITAL)
    result["adjusted_trade_count_proxy"] = result["raw_trade_count"] * result["applied_scale"]
    result["adjusted_slippage_proxy"] = result["raw_slippage"] * result["applied_scale"]
    result["drawdown_pct"] = _drawdown_pct(result["adjusted_equity"])
    return result


def _summarize_daily(daily: pd.DataFrame, variant: OverlayVariant) -> dict[str, Any]:
    if daily.empty:
        raise RuntimeError(f"empty daily for {variant.arm}")
    equity = pd.to_numeric(daily["adjusted_equity"], errors="coerce").ffill()
    dd = _drawdown_pct(equity)
    heat = pd.to_numeric(daily["adjusted_broker10_margin_to_equity_pct"], errors="coerce").fillna(0.0)
    scale = pd.to_numeric(daily["applied_scale"], errors="coerce").fillna(1.0)
    start = str(daily["requested_start"].iloc[0])
    start_month = str(daily["requested_start_month"].iloc[0])
    end_equity = float(equity.iloc[-1])
    elapsed_days = max(1, int((daily["date"].iloc[-1] - daily["date"].iloc[0]).days))
    scaled_days = scale.lt(0.999999).sum()
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "arm": variant.arm,
        "source": variant.source,
        "requested_start": start,
        "requested_start_month": start_month,
        "requested_end": str(daily["requested_end"].iloc[0]),
        "actual_start": pd.Timestamp(daily["date"].iloc[0]).date().isoformat(),
        "actual_end": pd.Timestamp(daily["date"].iloc[-1]).date().isoformat(),
        "trading_days": int(len(daily)),
        "calendar_days": int(elapsed_days + 1),
        "account_capital": CAPITAL,
        "end_equity": end_equity,
        "total_return_pct": float((end_equity / CAPITAL - 1.0) * 100.0),
        "cagr_pct": float((end_equity / CAPITAL) ** (365.25 / elapsed_days) - 1.0) * 100.0,
        "max_dd_pct": float(dd.min()) if len(dd) else 0.0,
        "min_equity": float(equity.min()) if len(equity) else end_equity,
        "max_equity": float(equity.max()) if len(equity) else end_equity,
        "sharpe": _daily_sharpe(equity),
        "max_broker10_margin_to_equity_pct": float(heat.max()) if len(heat) else 0.0,
        "days_over_100pct": int(heat.gt(100.0).sum()),
        "days_over_90pct": int(heat.gt(90.0).sum()),
        "days_over_80pct": int(heat.gt(80.0).sum()),
        "days_scaled": int(scaled_days),
        "mean_applied_scale": float(scale.mean()),
        "median_scale_on_scaled_days": float(scale[scale.lt(0.999999)].median()) if int(scaled_days) else 1.0,
        "total_trade_count_proxy": float(daily["adjusted_trade_count_proxy"].sum()),
        "total_slippage_proxy": float(daily["adjusted_slippage_proxy"].sum()),
        "dd30_fail": int(float(dd.min()) < -30.0) if len(dd) else 0,
        "dd40_fail": int(float(dd.min()) < -40.0) if len(dd) else 0,
        "dd50_fail": int(float(dd.min()) < -50.0) if len(dd) else 0,
        "broker100_fail": int(float(heat.max()) > 100.0) if len(heat) else 0,
        "note": variant.note,
    }


def _aggregate(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for arm, group in summary.groupby("arm", sort=False):
        returns = pd.to_numeric(group["total_return_pct"], errors="coerce")
        dds = pd.to_numeric(group["max_dd_pct"], errors="coerce")
        sharpes = pd.to_numeric(group["sharpe"], errors="coerce")
        heat = pd.to_numeric(group["max_broker10_margin_to_equity_pct"], errors="coerce")
        rows.append(
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "line_id": LINE_ID,
                "arm": arm,
                "sample_count": int(len(group)),
                "positive_count": int(returns.gt(0.0).sum()),
                "min_return_pct": float(returns.min()),
                "median_return_pct": float(returns.median()),
                "max_return_pct": float(returns.max()),
                "worst_max_dd_pct": float(dds.min()),
                "median_max_dd_pct": float(dds.median()),
                "median_sharpe": float(sharpes.median()),
                "min_sharpe": float(sharpes.min()),
                "peak_broker10_margin_to_equity_pct": float(heat.max()),
                "dd30_fail_count": int(pd.to_numeric(group["dd30_fail"], errors="coerce").fillna(0).sum()),
                "dd40_fail_count": int(pd.to_numeric(group["dd40_fail"], errors="coerce").fillna(0).sum()),
                "dd50_fail_count": int(pd.to_numeric(group["dd50_fail"], errors="coerce").fillna(0).sum()),
                "broker100_fail_count": int(pd.to_numeric(group["broker100_fail"], errors="coerce").fillna(0).sum()),
                "days_over_100_sum": int(pd.to_numeric(group["days_over_100pct"], errors="coerce").fillna(0).sum()),
                "days_over_90_sum": int(pd.to_numeric(group["days_over_90pct"], errors="coerce").fillna(0).sum()),
                "days_over_80_sum": int(pd.to_numeric(group["days_over_80pct"], errors="coerce").fillna(0).sum()),
                "days_scaled_sum": int(pd.to_numeric(group["days_scaled"], errors="coerce").fillna(0).sum()),
                "mean_applied_scale_median": float(
                    pd.to_numeric(group["mean_applied_scale"], errors="coerce").median()
                ),
            }
        )
    return pd.DataFrame(rows)


def _comparison(summary: pd.DataFrame) -> pd.DataFrame:
    base = summary[summary["arm"].eq("c9_baseline_stop_retry")].copy()
    rows: list[dict[str, Any]] = []
    for arm, group in summary.groupby("arm", sort=False):
        if arm == "c9_baseline_stop_retry":
            continue
        merged = group.merge(
            base[
                [
                    "requested_start_month",
                    "end_equity",
                    "total_return_pct",
                    "max_dd_pct",
                    "sharpe",
                    "max_broker10_margin_to_equity_pct",
                    "days_over_100pct",
                    "days_over_90pct",
                ]
            ],
            on="requested_start_month",
            suffixes=("", "_baseline_c9"),
        )
        for row in merged.itertuples(index=False):
            base_profit = max(float(row.end_equity_baseline_c9) - CAPITAL, 1e-9)
            current_profit = float(row.end_equity) - CAPITAL
            rows.append(
                {
                    "arm": arm,
                    "requested_start_month": row.requested_start_month,
                    "return_pct": row.total_return_pct,
                    "baseline_return_pct": row.total_return_pct_baseline_c9,
                    "return_delta_pp": row.total_return_pct - row.total_return_pct_baseline_c9,
                    "profit_retention_pct": current_profit / base_profit * 100.0,
                    "max_dd_pct": row.max_dd_pct,
                    "baseline_max_dd_pct": row.max_dd_pct_baseline_c9,
                    "dd_delta_pp": row.max_dd_pct - row.max_dd_pct_baseline_c9,
                    "sharpe": row.sharpe,
                    "baseline_sharpe": row.sharpe_baseline_c9,
                    "sharpe_delta": row.sharpe - row.sharpe_baseline_c9,
                    "max_broker10": row.max_broker10_margin_to_equity_pct,
                    "baseline_max_broker10": row.max_broker10_margin_to_equity_pct_baseline_c9,
                    "max_broker10_delta_pp": (
                        row.max_broker10_margin_to_equity_pct
                        - row.max_broker10_margin_to_equity_pct_baseline_c9
                    ),
                    "days_over_100_delta": row.days_over_100pct - row.days_over_100pct_baseline_c9,
                    "days_over_90_delta": row.days_over_90pct - row.days_over_90pct_baseline_c9,
                    "days_scaled": row.days_scaled,
                }
            )
    return pd.DataFrame(rows)


def _decision(summary: pd.DataFrame, aggregate: pd.DataFrame, comparison: pd.DataFrame) -> dict[str, Any]:
    baseline = aggregate[aggregate["arm"].eq("c9_baseline_stop_retry")].iloc[0].to_dict()
    non_ref = comparison[comparison["arm"].astype(str).str.startswith("c9_")].copy()
    candidate_rows: list[dict[str, Any]] = []
    for arm, group in non_ref.groupby("arm", sort=False):
        dd_win = int(pd.to_numeric(group["dd_delta_pp"], errors="coerce").gt(0.0).sum())
        return_win = int(pd.to_numeric(group["return_delta_pp"], errors="coerce").gt(0.0).sum())
        sharpe_win = int(pd.to_numeric(group["sharpe_delta"], errors="coerce").gt(0.0).sum())
        retention = float(pd.to_numeric(group["profit_retention_pct"], errors="coerce").median())
        heat_reduction = float(pd.to_numeric(group["max_broker10_delta_pp"], errors="coerce").median())
        candidate_rows.append(
            {
                "arm": arm,
                "dd_win_count": dd_win,
                "return_win_count": return_win,
                "sharpe_win_count": sharpe_win,
                "median_profit_retention_pct": retention,
                "median_max_broker10_delta_pp": heat_reduction,
                "stage159_proxy_candidate": bool(dd_win >= 6 and retention >= 85.0 and sharpe_win >= 4),
            }
        )
    candidate_summary = pd.DataFrame(candidate_rows)
    proxy_candidates = (
        candidate_summary[candidate_summary["stage159_proxy_candidate"]]["arm"].astype(str).tolist()
        if not candidate_summary.empty
        else []
    )
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_daily_delta": str(DAILY_DELTA_PATH),
        "sample_count": int(summary["requested_start_month"].nunique()),
        "variant_count": int(summary["arm"].nunique()),
        "baseline_c9_aggregate": baseline,
        "candidate_summary": candidate_summary.to_dict(orient="records"),
        "proxy_candidates": proxy_candidates,
        "decision": (
            "stage159_proxy_candidate_found_require_order_level_backtest"
            if proxy_candidates
            else "stage159_no_proxy_candidate_do_not_promote_account_overlay"
        ),
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "external_research_judgment": (
            "Skipped external search per operator constraint; local-only counterfactual based on Stage157 outputs."
        ),
        "bug_review": (
            "Stage159 verifies net_pnl_c9 equals account_equity_c9 daily diff within float tolerance before use; "
            "the overlay remains a daily proxy and cannot prove order-level fill/margin behavior."
        ),
        "overfit_reflection_before": (
            "否。预声明少数账户层形状，只测 heat/high-water 机制，不按品种、日期或方向筛选。"
        ),
        "continue_value_before": (
            "是。Stage158 指向保证金热度和峰值回吐，账户层反事实是延续 Stage372/C4 治理思路的低过拟合方向。"
        ),
        "overfit_reflection_after": (
            "否。无论结果好坏，本阶段只允许产生是否值得订单级复测的结论，不直接形成正式规则。"
        ),
        "continue_value_after": (
            "由输出决定：若 heat/high-water 代理能稳定改善回撤且保留收益，再进入订单级正式回测；否则停止该形状。"
        ),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "aggregate": str(AGG_PATH),
            "comparison": str(COMPARISON_PATH),
            "daily": str(DAILY_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }


def _write_report(summary: pd.DataFrame, aggregate: pd.DataFrame, comparison: pd.DataFrame, decision: dict[str, Any]) -> None:
    summary_cols = [
        "arm",
        "requested_start_month",
        "end_equity",
        "total_return_pct",
        "max_dd_pct",
        "sharpe",
        "max_broker10_margin_to_equity_pct",
        "days_over_100pct",
        "days_scaled",
    ]
    comparison_cols = [
        "arm",
        "requested_start_month",
        "return_delta_pp",
        "profit_retention_pct",
        "dd_delta_pp",
        "sharpe_delta",
        "max_broker10_delta_pp",
        "days_over_100_delta",
        "days_scaled",
    ]
    lines = [
        "# Stage159 当前重建版账户层 heat/survival 反事实",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 输入：`{DAILY_DELTA_PATH}`",
        "- 性质：只读日级代理反事实；不重跑策略，不连接 CTP，不调用订单 API。",
        "- 限制：该阶段只能判断账户层形状是否值得订单级回测，不能替代真实订单级回测。",
        "",
        "## Aggregate",
        "",
        _md_table(aggregate, max_rows=20),
        "",
        "## Summary",
        "",
        _md_table(summary[summary_cols], max_rows=120),
        "",
        "## Comparison vs C9 Baseline",
        "",
        _md_table(comparison[comparison_cols], max_rows=160),
        "",
        "## Candidate Summary",
        "",
        _md_table(pd.DataFrame(decision["candidate_summary"]), max_rows=20),
        "",
        "## Decision",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 候选：`{decision['proxy_candidates']}`",
        f"- bug review：{decision['bug_review']}",
        f"- 过拟合反思：{decision['overfit_reflection_after']}",
        f"- 继续价值反思：{decision['continue_value_after']}",
        "",
        "## Outputs",
        "",
    ]
    for key, path in decision["outputs"].items():
        lines.append(f"- {key}: `{path}`")
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    if not DAILY_DELTA_PATH.exists():
        raise FileNotFoundError(f"missing Stage157 daily delta: {DAILY_DELTA_PATH}")
    daily_delta = pd.read_csv(DAILY_DELTA_PATH, encoding="utf-8-sig")
    daily_delta["date"] = pd.to_datetime(daily_delta["date"], errors="coerce").dt.normalize()

    rows: list[dict[str, Any]] = []
    daily_rows: list[pd.DataFrame] = []
    for _, group in daily_delta.groupby("requested_start_month", sort=True):
        group = group.sort_values("date").reset_index(drop=True)
        equity = pd.to_numeric(group["account_equity_c9"], errors="coerce")
        pnl = pd.to_numeric(group["net_pnl_c9"], errors="coerce")
        diff = equity.diff().fillna(equity.iloc[0] - CAPITAL)
        max_pnl_mismatch = float((diff - pnl).abs().max())
        if max_pnl_mismatch > 1e-6:
            raise RuntimeError(
                f"net_pnl/account_equity mismatch for {group['requested_start_month'].iloc[0]}: "
                f"{max_pnl_mismatch}"
            )
        for variant in VARIANTS:
            simulated = _simulate_variant(group, variant)
            rows.append(_summarize_daily(simulated, variant))
            daily_rows.append(simulated)

    summary = pd.DataFrame(rows)
    daily = pd.concat(daily_rows, ignore_index=True)
    aggregate = _aggregate(summary)
    comparison = _comparison(summary)
    decision = _decision(summary, aggregate, comparison)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    aggregate.to_csv(AGG_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    daily.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(summary, aggregate, comparison, decision)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print("aggregate")
    print(aggregate.to_string(index=False))
    print("candidate_summary")
    print(pd.DataFrame(decision["candidate_summary"]).to_string(index=False))


if __name__ == "__main__":
    main()
