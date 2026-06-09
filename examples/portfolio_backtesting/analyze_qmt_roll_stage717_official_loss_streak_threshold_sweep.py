from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage660_stage653_multiperiod_live_audit as s660
from qmt_roll_official_live_config import OFFICIAL_LIVE_CAPITAL, OFFICIAL_LIVE_PROFILE_NAME, OFFICIAL_LIVE_VERSION


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage717_official_loss_streak_threshold_sweep_v1"
OUTPUT_PREFIX = "qmt_roll_stage717_official_loss_streak_threshold_sweep"
LINE_ID = "futures_trend_loss_streak_threshold_sweep"

THRESHOLDS = tuple(range(3, 13))
FLOOR_MULTIPLIER = 0.1
ANALYSIS_START = pd.Timestamp("2020-01-01")
ANALYSIS_END = pd.Timestamp("2026-04-30")

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
ANNUAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_equity_curves_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    values = pd.to_numeric(equity, errors="coerce").ffill().fillna(OFFICIAL_LIVE_CAPITAL)
    peak = values.cummax()
    return (values / peak.replace(0.0, np.nan) - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0) * 100.0


def _sharpe(equity: pd.Series) -> float:
    returns = pd.to_numeric(equity, errors="coerce").ffill().pct_change().replace([np.inf, -np.inf], np.nan).fillna(0.0)
    std = float(returns.std(ddof=1))
    if std <= 0:
        return 0.0
    return float(returns.mean() / std * np.sqrt(252.0))


def _streak_multipliers(threshold: int) -> str:
    if threshold < 1:
        raise ValueError("threshold must be positive")
    return ",".join(["1.0"] * threshold + [f"{FLOOR_MULTIPLIER:.1f}"])


def _variant_name(threshold: int) -> str:
    return f"{OFFICIAL_LIVE_PROFILE_NAME}_lossstreak{threshold:02d}_floor01_stage717"


def _threshold_spec(base: s660.s653.ForcedVariant, threshold: int) -> s660.s653.ForcedVariant:
    capital = replace(
        base.capital,
        variant=_variant_name(threshold),
        label=f"loss streak >= {threshold} -> 0.1",
        note=(
            "Official Stage372/20w unchanged except the loss-streak threshold for reducing new-entry "
            f"risk multiplier to {FLOOR_MULTIPLIER:.1f} is set to {threshold} consecutive losses."
        ),
    )
    overrides = {
        **base.overrides,
        "streak_risk_multipliers": _streak_multipliers(threshold),
    }
    return replace(
        base,
        capital=capital,
        overrides=overrides,
        profile=f"official_stage372_loss_streak_ge{threshold}_floor01_stage717",
    )


def _metric_row(frame: pd.DataFrame, forced_events: pd.DataFrame, threshold: int, spec: s660.s653.ForcedVariant) -> dict[str, Any]:
    ordered = frame.sort_values("date").reset_index(drop=True)
    ordered["date"] = pd.to_datetime(ordered["date"], errors="coerce").dt.normalize()
    equity = pd.to_numeric(ordered["account_equity"], errors="coerce").ffill().fillna(OFFICIAL_LIVE_CAPITAL)
    net_pnl = pd.to_numeric(ordered.get("net_pnl", 0.0), errors="coerce").fillna(0.0)
    slippage = pd.to_numeric(ordered.get("total_slippage", ordered.get("slippage", 0.0)), errors="coerce").fillna(0.0)
    trade_count = pd.to_numeric(ordered.get("trade_count", 0.0), errors="coerce").fillna(0.0)
    margin_exact = pd.to_numeric(ordered.get("broker10_total_margin_exact", 0.0), errors="coerce").fillna(0.0)
    margin = (margin_exact / equity.replace(0.0, np.nan) * 100.0).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    dd = _drawdown_pct(equity)
    nonzero_pnl = net_pnl[net_pnl.abs().gt(1e-12)]

    event_count = 0
    event_volume = 0.0
    if not forced_events.empty:
        event_count = int(len(forced_events))
        event_volume = float(pd.to_numeric(forced_events.get("reduce_volume", 0.0), errors="coerce").fillna(0.0).sum())

    return {
        "threshold": int(threshold),
        "variant": spec.capital.variant,
        "label": spec.capital.label,
        "streak_risk_multipliers": _streak_multipliers(threshold),
        "analysis_start": pd.Timestamp(ordered["date"].iloc[0]).date().isoformat(),
        "analysis_end": pd.Timestamp(ordered["date"].iloc[-1]).date().isoformat(),
        "trading_days": int(len(ordered)),
        "end_equity": float(equity.iloc[-1]),
        "total_return_pct": float((equity.iloc[-1] / OFFICIAL_LIVE_CAPITAL - 1.0) * 100.0),
        "max_dd_pct": float(dd.min()),
        "sharpe": _sharpe(equity),
        "min_equity": float(equity.min()),
        "max_broker10_margin_to_equity_pct": float(margin.max()),
        "p95_broker10_margin_to_equity_pct": float(margin.quantile(0.95)),
        "days_over_90pct": int(margin.gt(90.0 + 1e-9).sum()),
        "days_over_100pct": int(margin.gt(100.0 + 1e-9).sum()),
        "total_slippage": float(slippage.sum()),
        "total_trade_count": float(trade_count.sum()),
        "nonzero_daily_win_rate_pct": float(nonzero_pnl.gt(0.0).mean() * 100.0) if len(nonzero_pnl) else 0.0,
        "forced_margin_deleverage_count": event_count,
        "forced_margin_deleverage_closed_volume": event_volume,
        "dd30_pass": int(float(dd.min()) >= -30.0),
        "dd40_pass": int(float(dd.min()) >= -40.0),
        "broker10_100_pass": int(margin.max() <= 100.0 + 1e-9),
    }


def _curve_frame(frame: pd.DataFrame, threshold: int, spec: s660.s653.ForcedVariant) -> pd.DataFrame:
    ordered = frame.sort_values("date").reset_index(drop=True)
    ordered["date"] = pd.to_datetime(ordered["date"], errors="coerce").dt.normalize()
    equity = pd.to_numeric(ordered["account_equity"], errors="coerce").ffill().fillna(OFFICIAL_LIVE_CAPITAL)
    return pd.DataFrame(
        {
            "date": ordered["date"],
            "threshold": int(threshold),
            "variant": spec.capital.variant,
            "label": spec.capital.label,
            "account_equity": equity,
            "drawdown_pct": _drawdown_pct(equity),
            "net_pnl": pd.to_numeric(ordered.get("net_pnl", 0.0), errors="coerce").fillna(0.0),
            "trade_count": pd.to_numeric(ordered.get("trade_count", 0.0), errors="coerce").fillna(0.0),
            "total_slippage": pd.to_numeric(
                ordered.get("total_slippage", ordered.get("slippage", 0.0)), errors="coerce"
            ).fillna(0.0),
        }
    )


def _annual(curves: pd.DataFrame) -> pd.DataFrame:
    data = curves.copy()
    data["year"] = pd.to_datetime(data["date"], errors="coerce").dt.year
    rows: list[dict[str, Any]] = []
    for (threshold, year), group in data.groupby(["threshold", "year"], sort=True):
        ordered = group.sort_values("date")
        equity = pd.to_numeric(ordered["account_equity"], errors="coerce").ffill()
        start_equity = float(equity.iloc[0] - pd.to_numeric(ordered["net_pnl"], errors="coerce").fillna(0.0).iloc[0])
        path = pd.Series([start_equity] + equity.tolist())
        dd = _drawdown_pct(path)
        rows.append(
            {
                "threshold": int(threshold),
                "year": int(year),
                "period_start_equity": start_equity,
                "period_end_equity": float(equity.iloc[-1]),
                "period_pnl": float(pd.to_numeric(ordered["net_pnl"], errors="coerce").fillna(0.0).sum()),
                "period_return_pct": float((equity.iloc[-1] / max(start_equity, 1e-9) - 1.0) * 100.0),
                "period_max_dd_pct": float(dd.min()),
                "total_trade_count": float(pd.to_numeric(ordered["trade_count"], errors="coerce").fillna(0.0).sum()),
                "total_slippage": float(pd.to_numeric(ordered["total_slippage"], errors="coerce").fillna(0.0).sum()),
            }
        )
    return pd.DataFrame(rows)


def _plot(curves: pd.DataFrame) -> None:
    if curves.empty:
        return
    fig, axes = plt.subplots(2, 1, figsize=(16, 10), sharex=True, gridspec_kw={"height_ratios": [3, 1]})
    colors = plt.cm.tab10(np.linspace(0, 1, len(THRESHOLDS)))
    for color, threshold in zip(colors, THRESHOLDS):
        group = curves[curves["threshold"].eq(threshold)].sort_values("date")
        axes[0].plot(
            group["date"],
            group["account_equity"],
            label=f"L{threshold}->0.1",
            linewidth=1.35 if threshold != 3 else 2.2,
            color=color,
        )
        axes[1].plot(
            group["date"],
            group["drawdown_pct"],
            label=f"L{threshold}->0.1",
            linewidth=1.0 if threshold != 3 else 1.8,
            color=color,
        )
    axes[0].axhline(OFFICIAL_LIVE_CAPITAL, color="#94a3b8", linestyle="--", linewidth=0.9)
    axes[0].set_title("Stage717 Official Stage372 Loss-Streak Threshold Sweep: Full Equity Curves")
    axes[0].set_ylabel("Account equity")
    axes[1].set_ylabel("Drawdown %")
    axes[1].set_xlabel("Date")
    for ax in axes:
        ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.35)
        ax.legend(loc="best", ncol=5, fontsize=9)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=170)
    plt.close(fig)


def _decision(summary: pd.DataFrame) -> dict[str, Any]:
    ranked_return = summary.sort_values("end_equity", ascending=False).reset_index(drop=True)
    ranked_dd = summary.sort_values(["max_dd_pct", "end_equity"], ascending=[False, False]).reset_index(drop=True)
    baseline = summary[summary["threshold"].eq(3)].iloc[0].to_dict()
    return {
        "stage": "Stage001",
        "script_stage": "Stage717",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "baseline_profile": OFFICIAL_LIVE_PROFILE_NAME,
        "thresholds": list(THRESHOLDS),
        "floor_multiplier": FLOOR_MULTIPLIER,
        "analysis_start": ANALYSIS_START.date().isoformat(),
        "analysis_end": ANALYSIS_END.date().isoformat(),
        "decision": "loss_streak_threshold_sweep_full_period_only_no_promotion",
        "best_by_end_equity": ranked_return.head(3).to_dict("records"),
        "best_by_max_dd": ranked_dd.head(3).to_dict("records"),
        "baseline_threshold3": baseline,
        "overfit_judgement": (
            "Full-period threshold ranking is path-dependent. Do not promote without start-year, quarterly, "
            "weak-window and cost-stress validation."
        ),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "curves": str(CURVES_PATH),
            "annual": str(ANNUAL_PATH),
            "report": str(REPORT_PATH),
            "chart": str(CHART_PATH),
            "decision": str(DECISION_PATH),
        },
    }


def _write_report(summary: pd.DataFrame, annual: pd.DataFrame, decision: dict[str, Any]) -> None:
    display_cols = [
        "threshold",
        "end_equity",
        "total_return_pct",
        "max_dd_pct",
        "sharpe",
        "total_slippage",
        "total_trade_count",
        "nonzero_daily_win_rate_pct",
        "max_broker10_margin_to_equity_pct",
        "forced_margin_deleverage_count",
        "forced_margin_deleverage_closed_volume",
    ]
    lines = [
        "# Stage001 / Script717 Loss-Streak Threshold Sweep",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 当前 official live：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_PROFILE_NAME}`",
        f"- 扫描阈值：`{','.join(str(item) for item in THRESHOLDS)}`",
        f"- 触发后风险倍率：`{FLOOR_MULTIPLIER}`",
        "- 其余正式配置不变，包括 AI 池、品种池、recovery_sleeve、maxpos4、强制减仓规则。",
        "- 不连接 CTP，不调用下单。",
        "",
        "## Summary",
        "",
        _md_table(summary[display_cols].sort_values("threshold"), max_rows=30),
        "",
        "## Annual",
        "",
        _md_table(annual, max_rows=120),
        "",
        "## Decision",
        "",
        f"- 决策：`{decision['decision']}`",
        "- 本阶段只做全周期曲线和参数敏感性，不做正式晋级。",
        "- 若要继续，只能对全周期较强阈值补多起点、季度冷启动、弱窗口和成本压力反证。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    metadata = s513._metadata()
    base = s660._official_spec(metadata)

    summary_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    for threshold in THRESHOLDS:
        spec = _threshold_spec(base, threshold)
        print(f"[stage717] running loss_streak>={threshold} floor {FLOOR_MULTIPLIER}", flush=True)
        daily, forced_events = s660._run_independent_window(
            spec=spec,
            metadata=metadata,
            analysis_start=ANALYSIS_START,
            analysis_end=ANALYSIS_END,
        )
        summary_rows.append(_metric_row(daily, forced_events, threshold, spec))
        curve_frames.append(_curve_frame(daily, threshold, spec))

    summary = pd.DataFrame(summary_rows).sort_values("threshold").reset_index(drop=True)
    curves = pd.concat(curve_frames, ignore_index=True, sort=False)
    annual = _annual(curves)
    decision = _decision(summary)

    _plot(curves)
    _write_report(summary, annual, decision)
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    annual.to_csv(ANNUAL_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"chart={CHART_PATH}")


if __name__ == "__main__":
    main()
