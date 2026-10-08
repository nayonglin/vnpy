from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage660_stage653_multiperiod_live_audit as s660
import analyze_qmt_roll_stage746_half_risk_no_streak_multiperiod as s746


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage748_half_risk_no_streak_500k_v1"
OUTPUT_PREFIX = "qmt_roll_stage748_half_risk_no_streak_500k"
LINE_ID = "futures_trend_quarter_risk_no_streak"

CAPITAL_500K = 500_000.0
CANDIDATE_500K_VARIANT = "stage526_500k_force95_to80_r040_pc25_maxpos4_no_streak_no_recovery_stage748"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
COMPARISON_20W_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_20w_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
ANNUAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_{MODEL_TAG}.csv"
MONTHLY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_monthly_{MODEL_TAG}.csv"
CHECKS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_checks_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    return s746.s745.s707._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s746.s745.s707._md_table(frame, max_rows=max_rows)


def _candidate_500k_spec(metadata: dict[str, Any]) -> s746.s745.s707.s653.ForcedVariant:
    base = s746._candidate_spec(metadata)
    capital = replace(
        base.capital,
        variant=CANDIDATE_500K_VARIANT,
        label="Stage748 500k half formal risk, no loss-streak throttle",
        account_capital=CAPITAL_500K,
        c3_capital=CAPITAL_500K,
        note=(
            "Stage746 C logic unchanged, but account/c3 capital is 500k. "
            "Risk multiplier remains 0.40 and loss-streak/recovery sleeves remain disabled."
        ),
    )
    return replace(base, capital=capital, profile="official_stage372_r040_no_streak_500k_stage748")


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    values = pd.to_numeric(equity, errors="coerce").ffill()
    peak = values.cummax()
    return (values / peak.replace(0.0, np.nan) - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0) * 100.0


def _sharpe(equity: pd.Series) -> float:
    returns = pd.to_numeric(equity, errors="coerce").ffill().pct_change().replace([np.inf, -np.inf], np.nan).fillna(0.0)
    std = float(returns.std(ddof=1))
    if std <= 0.0:
        return 0.0
    return float(returns.mean() / std * np.sqrt(252.0))


def _cagr_pct(equity: pd.Series, dates: pd.Series) -> float:
    if len(equity) < 2:
        return 0.0
    start_value = float(equity.iloc[0])
    end_value = float(equity.iloc[-1])
    if start_value <= 0.0 or end_value <= 0.0:
        return 0.0
    days = max((pd.Timestamp(dates.iloc[-1]) - pd.Timestamp(dates.iloc[0])).days, 1)
    return float((end_value / start_value) ** (365.25 / days) - 1.0) * 100.0


def _metric_row(
    frame: pd.DataFrame,
    *,
    spec: s746.s745.s707.s653.ForcedVariant,
    window_name: str,
    window_label: str,
    window_group: str,
    forced_events: pd.DataFrame,
) -> tuple[dict[str, Any], pd.DataFrame, list[dict[str, Any]]]:
    ordered = frame.sort_values("date").reset_index(drop=True)
    if ordered.empty:
        raise ValueError(f"empty window frame: {window_name}")
    ordered["date"] = pd.to_datetime(ordered["date"], errors="coerce").dt.normalize()
    capital = float(spec.capital.account_capital)
    equity = pd.to_numeric(ordered["account_equity"], errors="coerce").ffill().fillna(capital)
    net_pnl = pd.to_numeric(ordered["net_pnl"], errors="coerce").fillna(0.0)
    slippage = pd.to_numeric(ordered.get("total_slippage", ordered.get("slippage", 0.0)), errors="coerce").fillna(0.0)
    trade_count = pd.to_numeric(ordered.get("trade_count", 0.0), errors="coerce").fillna(0.0)
    margin_exact = pd.to_numeric(ordered.get("broker10_total_margin_exact", 0.0), errors="coerce").fillna(0.0)
    margin = (margin_exact / equity.replace(0.0, np.nan) * 100.0).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    dd = _drawdown_pct(equity)
    nonzero_pnl = net_pnl[net_pnl.abs().gt(1e-12)]

    events = forced_events.copy()
    event_count = 0
    event_volume = 0.0
    if not events.empty:
        events["date"] = pd.to_datetime(events["date"], errors="coerce").dt.normalize()
        events = events[
            events["variant"].astype(str).eq(spec.capital.variant)
            & events["date"].ge(ordered["date"].min())
            & events["date"].le(ordered["date"].max())
        ]
        event_count = int(len(events))
        event_volume = float(pd.to_numeric(events.get("reduce_volume", 0.0), errors="coerce").fillna(0.0).sum())

    row = {
        "variant": spec.capital.variant,
        "label": spec.capital.label,
        "profile": spec.profile,
        "window_name": window_name,
        "window_label": window_label,
        "window_group": window_group,
        "analysis_start": pd.Timestamp(ordered["date"].iloc[0]).date().isoformat(),
        "analysis_end": pd.Timestamp(ordered["date"].iloc[-1]).date().isoformat(),
        "account_capital": capital,
        "c3_capital": float(spec.capital.c3_capital),
        "risk_multiplier": float(spec.capital.risk_multiplier),
        "trading_days": int(len(ordered)),
        "end_equity": float(equity.iloc[-1]),
        "total_return_pct": float((equity.iloc[-1] / capital - 1.0) * 100.0),
        "cagr_pct": _cagr_pct(equity, ordered["date"]),
        "max_dd_pct": float(dd.min()),
        "ulcer_pct": float(np.sqrt(np.mean(np.square(np.minimum(dd.to_numpy(dtype=float), 0.0))))),
        "sharpe": _sharpe(equity),
        "min_equity": float(equity.min()),
        "max_broker10_margin_to_equity_pct": float(margin.max()),
        "p95_broker10_margin_to_equity_pct": float(margin.quantile(0.95)),
        "days_over_100pct": int(margin.gt(100.0 + 1e-9).sum()),
        "days_over_90pct": int(margin.gt(90.0 + 1e-9).sum()),
        "days_equity_below_zero": int(equity.le(0.0).sum()),
        "total_slippage": float(slippage.sum()),
        "total_trade_count": float(trade_count.sum()),
        "nonzero_daily_win_rate_pct": float(nonzero_pnl.gt(0.0).mean() * 100.0) if len(nonzero_pnl) else 0.0,
        "forced_margin_deleverage_count": event_count,
        "forced_margin_deleverage_closed_volume": event_volume,
        "dd30_pass": int(float(dd.min()) >= -30.0),
        "dd40_pass": int(float(dd.min()) >= -40.0),
        "broker10_100_pass": int(margin.max() <= 100.0 + 1e-9),
        "account_survival_pass": int(equity.min() > 0.0),
        "deployable_pass": int(float(dd.min()) >= -40.0 and margin.max() <= 100.0 + 1e-9 and equity.min() > 0.0),
    }

    curve = pd.DataFrame(
        {
            "date": ordered["date"],
            "variant": spec.capital.variant,
            "label": spec.capital.label,
            "window_name": window_name,
            "window_label": window_label,
            "window_group": window_group,
            "account_capital": capital,
            "account_equity": equity,
            "nav": equity / capital,
            "drawdown_pct": dd,
            "broker10_margin_to_equity_pct": margin,
            "net_pnl": net_pnl,
            "trade_count": trade_count,
            "total_slippage": slippage,
        }
    )

    cost_rows: list[dict[str, Any]] = []
    for multiplier in (1.0, 2.0, 3.0):
        stressed = equity - slippage.cumsum() * max(0.0, multiplier - 1.0)
        stressed_dd = _drawdown_pct(stressed)
        stressed_margin = (margin_exact / stressed.replace(0.0, np.nan) * 100.0).replace(
            [np.inf, -np.inf], np.nan
        ).fillna(0.0)
        cost_rows.append(
            {
                "variant": spec.capital.variant,
                "label": spec.capital.label,
                "window_name": window_name,
                "cost_multiplier": multiplier,
                "account_capital": capital,
                "end_equity": float(stressed.iloc[-1]),
                "total_return_pct": float((stressed.iloc[-1] / capital - 1.0) * 100.0),
                "max_dd_pct": float(stressed_dd.min()),
                "sharpe": _sharpe(stressed),
                "max_broker10_margin_to_equity_pct": float(stressed_margin.max()),
                "days_over_100pct": int(stressed_margin.gt(100.0 + 1e-9).sum()),
                "account_survival_pass": int(stressed.min() > 0.0),
                "deployable_pass": int(
                    stressed_dd.min() >= -40.0
                    and stressed_margin.max() <= 100.0 + 1e-9
                    and stressed.min() > 0.0
                ),
            }
        )
    return row, curve, cost_rows


def _load_stage746_20w_summary() -> pd.DataFrame:
    if not s746.SUMMARY_PATH.exists():
        raise FileNotFoundError(f"missing Stage746 summary: {s746.SUMMARY_PATH}")
    frame = pd.read_csv(s746.SUMMARY_PATH, encoding="utf-8-sig")
    return frame[frame["variant"].astype(str).eq(s746.CANDIDATE_VARIANT)].copy()


def _comparison_20w(summary_500k: pd.DataFrame) -> pd.DataFrame:
    c20 = _load_stage746_20w_summary()
    keep20 = [
        "window_name",
        "end_equity",
        "total_return_pct",
        "max_dd_pct",
        "sharpe",
        "max_broker10_margin_to_equity_pct",
        "p95_broker10_margin_to_equity_pct",
        "total_slippage",
        "total_trade_count",
        "nonzero_daily_win_rate_pct",
    ]
    keep50 = keep20 + ["window_group", "account_capital", "trading_days"]
    left = c20[keep20].copy().add_prefix("c20_")
    right = summary_500k[keep50].copy().add_prefix("c50_")
    merged = left.merge(right, left_on="c20_window_name", right_on="c50_window_name", how="inner")
    merged["window_name"] = merged["c50_window_name"]
    merged["window_group"] = merged["c50_window_group"]
    merged["return_delta_pct"] = merged["c50_total_return_pct"] - merged["c20_total_return_pct"]
    merged["dd_delta_pp"] = merged["c50_max_dd_pct"] - merged["c20_max_dd_pct"]
    merged["sharpe_delta"] = merged["c50_sharpe"] - merged["c20_sharpe"]
    merged["trade_count_delta"] = merged["c50_total_trade_count"] - merged["c20_total_trade_count"]
    merged["slippage_delta"] = merged["c50_total_slippage"] - merged["c20_total_slippage"]
    return merged


def _annual_monthly(curves: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    full = curves[curves["window_name"].eq("full_2020_20260430")].copy()
    if full.empty:
        return pd.DataFrame(), pd.DataFrame()
    full["date"] = pd.to_datetime(full["date"], errors="coerce").dt.normalize()
    full["year"] = full["date"].dt.year
    full["month"] = full["date"].dt.strftime("%Y-%m")
    rows_annual: list[dict[str, Any]] = []
    rows_monthly: list[dict[str, Any]] = []
    for year, group in full.groupby("year", sort=True):
        rows_annual.append(_period_row(group, "year", int(year)))
    for month, group in full.groupby("month", sort=True):
        rows_monthly.append(_period_row(group, "month", month))
    return pd.DataFrame(rows_annual), pd.DataFrame(rows_monthly)


def _period_row(group: pd.DataFrame, key_name: str, key_value: Any) -> dict[str, Any]:
    ordered = group.sort_values("date")
    equity = pd.to_numeric(ordered["account_equity"], errors="coerce").ffill()
    pnl = pd.to_numeric(ordered["net_pnl"], errors="coerce").fillna(0.0)
    start_equity = float(equity.iloc[0] - pnl.iloc[0])
    path = pd.Series([start_equity] + equity.tolist())
    dd = _drawdown_pct(path)
    return {
        key_name: key_value,
        "period_start_equity": start_equity,
        "period_end_equity": float(equity.iloc[-1]),
        "period_pnl": float(pnl.sum()),
        "period_return_pct": float((equity.iloc[-1] / max(start_equity, 1e-9) - 1.0) * 100.0),
        "period_max_dd_pct": float(dd.min()),
        "total_trade_count": float(pd.to_numeric(ordered["trade_count"], errors="coerce").fillna(0.0).sum()),
        "total_slippage": float(pd.to_numeric(ordered["total_slippage"], errors="coerce").fillna(0.0).sum()),
    }


def _checks(summary: pd.DataFrame, cost: pd.DataFrame, comparison: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    def add(name: str, status: str, value: float, threshold: str, comment: str) -> None:
        rows.append({"check_name": name, "status": status, "value": value, "threshold": threshold, "comment": comment})

    full = summary[summary["window_name"].eq("full_2020_20260430")].iloc[0]
    full_cost2 = cost[(cost["window_name"].eq("full_2020_20260430")) & (cost["cost_multiplier"].eq(2.0))].iloc[0]
    start_years = summary[summary["window_group"].eq("start_year")].copy()
    phases = summary[summary["window_group"].eq("phase")].copy()
    full_compare = comparison[comparison["window_name"].eq("full_2020_20260430")].iloc[0]

    add("full_dd40_pass", "pass" if int(full["dd40_pass"]) == 1 else "fail", float(full["max_dd_pct"]), ">= -40%", "全周期生存线。")
    add("full_dd30_watch", "pass" if float(full["max_dd_pct"]) >= -30.0 else "watch", float(full["max_dd_pct"]), ">= -30% preferred", "低风险体验观察项。")
    add("full_broker10_100_pass", "pass" if int(full["broker10_100_pass"]) == 1 else "fail", float(full["max_broker10_margin_to_equity_pct"]), "<= 100%", "保证金不能穿线。")
    add("cost2_full_dd40_pass", "pass" if int(full_cost2["deployable_pass"]) == 1 else "fail", float(full_cost2["max_dd_pct"]), "2x cost deployable", "2x成本不能穿DD40或broker100。")
    add("full_return_vs_20w_positive", "pass" if float(full_compare["return_delta_pct"]) > 0.0 else "watch", float(full_compare["return_delta_pct"]), "> 0pp", "50万应至少改善20万C的收益率，否则资金粒度没有帮助。")
    add("start_years_dd40_all_pass", "pass" if int(start_years["dd40_pass"].min()) == 1 else "fail", float(start_years["max_dd_pct"].min()), "all >= -40%", "逐年冷启动生存线。")
    add("start_years_min_return_positive_watch", "pass" if float(start_years["total_return_pct"].min()) > 0.0 else "watch", float(start_years["total_return_pct"].min()), "> 0 preferred", "短样本允许观察，但负收益说明路径不稳。")
    add("phase_dd40_all_pass", "pass" if int(phases["dd40_pass"].min()) == 1 else "fail", float(phases["max_dd_pct"].min()), "all >= -40%", "阶段窗口生存线。")
    return pd.DataFrame(rows)


def _decision(summary: pd.DataFrame, cost: pd.DataFrame, comparison: pd.DataFrame, checks: pd.DataFrame) -> dict[str, Any]:
    hard_fail = checks[checks["status"].eq("fail")]["check_name"].astype(str).tolist()
    watch = checks[checks["status"].eq("watch")]["check_name"].astype(str).tolist()
    label = "half_risk_no_streak_500k_watch" if not hard_fail else "half_risk_no_streak_500k_not_promoted"
    return {
        "stage": "Stage437",
        "script_stage": "Stage748",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "baseline_20w_candidate": s746.CANDIDATE_VARIANT,
        "candidate_500k": CANDIDATE_500K_VARIANT,
        "decision": label,
        "hard_fail_checks": hard_fail,
        "watch_checks": watch,
        "change": {
            "official_config_changed": False,
            "ctp_connected": False,
            "order_api_called": False,
            "account_capital_before": 200_000.0,
            "account_capital_after": CAPITAL_500K,
            "c3_capital_before": 200_000.0,
            "c3_capital_after": CAPITAL_500K,
            "risk_multiplier": s746.HALF_FORMAL_RISK_MULTIPLIER,
            "streak_risk_multipliers": s746.NO_STREAK_MULTIPLIERS,
            "enable_streak_entry_structure_risk_recovery": False,
            "enable_recovery_sleeve": False,
        },
        "checks": checks.to_dict("records"),
        "summary": summary.to_dict("records"),
        "comparison_20w": comparison.to_dict("records"),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "cost": str(COST_PATH),
            "comparison_20w": str(COMPARISON_20W_PATH),
            "curves": str(CURVES_PATH),
            "annual": str(ANNUAL_PATH),
            "monthly": str(MONTHLY_PATH),
            "checks": str(CHECKS_PATH),
            "report": str(REPORT_PATH),
            "chart": str(CHART_PATH),
            "decision": str(DECISION_PATH),
        },
    }


def _plot(curves_500k: pd.DataFrame) -> None:
    c20_path = s746.CURVES_PATH
    if not c20_path.exists():
        return
    c20 = pd.read_csv(c20_path, encoding="utf-8-sig")
    c20 = c20[c20["variant"].astype(str).eq(s746.CANDIDATE_VARIANT)].copy()
    c20["account_capital"] = 200_000.0
    c20["nav"] = pd.to_numeric(c20["account_equity"], errors="coerce") / 200_000.0

    c50 = curves_500k.copy()
    plot_windows = ["full_2020_20260430", "since_2023", "phase_2024_2025"]
    labels = {s746.CANDIDATE_VARIANT: "C 20w", CANDIDATE_500K_VARIANT: "C 50w"}
    colors = {s746.CANDIDATE_VARIANT: "#2563eb", CANDIDATE_500K_VARIANT: "#059669"}

    fig, axes = plt.subplots(3, 1, figsize=(14, 11), sharex=False)
    for ax, window_name in zip(axes, plot_windows):
        for frame in (c20[c20["window_name"].eq(window_name)], c50[c50["window_name"].eq(window_name)]):
            if frame.empty:
                continue
            variant = str(frame["variant"].iloc[0])
            frame = frame.sort_values("date")
            ax.plot(
                pd.to_datetime(frame["date"], errors="coerce"),
                pd.to_numeric(frame["nav"], errors="coerce"),
                label=labels.get(variant, variant),
                color=colors.get(variant),
                linewidth=1.5,
            )
        ax.axhline(1.0, color="#94a3b8", linestyle="--", linewidth=0.8)
        ax.set_title(f"{window_name} NAV comparison")
        ax.set_ylabel("NAV")
        ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.35)
        ax.legend(loc="upper left")
    fig.suptitle("Stage748 C 50w vs Stage746 C 20w, same logic, NAV comparison", fontsize=14)
    fig.tight_layout(rect=(0, 0, 1, 0.965))
    fig.savefig(CHART_PATH, dpi=170)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    cost: pd.DataFrame,
    comparison: pd.DataFrame,
    annual: pd.DataFrame,
    checks: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    key_cols = [
        "window_name",
        "c20_total_return_pct",
        "c50_total_return_pct",
        "return_delta_pct",
        "c20_max_dd_pct",
        "c50_max_dd_pct",
        "dd_delta_pp",
        "c20_sharpe",
        "c50_sharpe",
        "sharpe_delta",
        "c20_total_trade_count",
        "c50_total_trade_count",
        "trade_count_delta",
    ]
    lines = [
        "# Stage437 / Script748 C版50万资金口径验证",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        f"- C20：`{s746.CANDIDATE_VARIANT}`，20万。",
        f"- C50：`{CANDIDATE_500K_VARIANT}`，50万。",
        "- 信号、AI池、品种池、`maxpos4`、`risk_multiplier=0.40`、关闭连败缩放和 recovery sleeve 均不变。",
        "- 不修改正式配置、不连接 CTP、不调用下单。",
        "",
        "## 外部调研判断",
        "",
        "- Fixed fractional / fixed risk sizing 的核心是按账户权益比例和止损距离决定合约数；资金规模会影响最小一手粒度和复利路径。",
        "- 本阶段只改资金规模，不按窗口或品种补丁，因此是资金口径敏感性验证，不是参数优化。",
        "",
        "## Checks",
        "",
        _md_table(checks, max_rows=40),
        "",
        "## C50 Summary",
        "",
        _md_table(summary, max_rows=40),
        "",
        "## C50 vs C20",
        "",
        _md_table(comparison[key_cols], max_rows=40),
        "",
        "## Cost Stress",
        "",
        _md_table(cost, max_rows=80),
        "",
        "## Annual Full Path",
        "",
        _md_table(annual, max_rows=20),
        "",
        "## Decision",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- hard_fail_checks：`{', '.join(decision['hard_fail_checks']) or '无'}`",
        f"- watch_checks：`{', '.join(decision['watch_checks']) or '无'}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    metadata = s746.s745.s707.s513._metadata()
    spec = _candidate_500k_spec(metadata)
    summary_rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []

    for window_name, window_label, window_group, start, end in s746.s745.s707.WINDOWS:
        print(f"[stage748] running {window_name} {CANDIDATE_500K_VARIANT}", flush=True)
        frame, forced_events = s660._run_independent_window(
            spec=spec,
            metadata=metadata,
            analysis_start=pd.Timestamp(start),
            analysis_end=pd.Timestamp(end),
        )
        row, curve, costs = _metric_row(
            frame,
            spec=spec,
            window_name=window_name,
            window_label=window_label,
            window_group=window_group,
            forced_events=forced_events,
        )
        summary_rows.append(row)
        curve_frames.append(curve)
        cost_rows.extend(costs)

    summary = pd.DataFrame(summary_rows)
    cost = pd.DataFrame(cost_rows)
    curves = pd.concat(curve_frames, ignore_index=True, sort=False)
    comparison = _comparison_20w(summary)
    annual, monthly = _annual_monthly(curves)
    checks = _checks(summary, cost, comparison)
    decision = _decision(summary, cost, comparison, checks)

    _plot(curves)
    _write_report(summary, cost, comparison, annual, checks, decision)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_20W_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    annual.to_csv(ANNUAL_PATH, index=False, encoding="utf-8-sig")
    monthly.to_csv(MONTHLY_PATH, index=False, encoding="utf-8-sig")
    checks.to_csv(CHECKS_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
