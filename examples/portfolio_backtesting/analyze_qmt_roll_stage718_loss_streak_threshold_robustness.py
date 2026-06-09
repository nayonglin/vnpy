from __future__ import annotations

from dataclasses import dataclass, replace
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
import analyze_qmt_roll_stage717_official_loss_streak_threshold_sweep as s717
from qmt_roll_official_live_config import OFFICIAL_LIVE_CAPITAL, OFFICIAL_LIVE_PROFILE_NAME, OFFICIAL_LIVE_VERSION


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage718_loss_streak_threshold_robustness_v1"
OUTPUT_PREFIX = "qmt_roll_stage718_loss_streak_threshold_robustness"
LINE_ID = "futures_trend_loss_streak_threshold_sweep"

THRESHOLDS = (3, 4, 6)
BASE_THRESHOLD = 3
FLOOR_MULTIPLIER = 0.1
ANALYSIS_END = pd.Timestamp("2026-04-30")

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_vs_threshold3_{MODEL_TAG}.csv"
ROBUSTNESS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_robustness_{MODEL_TAG}.csv"
WINNER_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_winner_by_window_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


@dataclass(frozen=True)
class Window:
    name: str
    label: str
    group: str
    start: str
    end: str


def _quarter_label(start: pd.Timestamp) -> str:
    return f"{start.year}Q{((start.month - 1) // 3) + 1}"


def _windows() -> tuple[Window, ...]:
    rows: list[Window] = []
    for start in pd.date_range("2020-01-01", "2026-01-01", freq="QS"):
        label = _quarter_label(start)
        rows.append(
            Window(
                name=f"qstart_{label.lower()}",
                label=f"{label} 独立启动至 2026-04-30",
                group="quarterly_start",
                start=start.strftime("%Y-%m-%d"),
                end=ANALYSIS_END.strftime("%Y-%m-%d"),
            )
        )
    rows.extend(
        [
            Window("phase_2020_2021", "2020-2021 独立阶段", "phase", "2020-01-01", "2021-12-31"),
            Window("phase_2022_2023", "2022-2023 独立阶段", "phase", "2022-01-01", "2023-12-31"),
            Window("phase_2024_2025", "2024-2025 独立阶段", "phase", "2024-01-01", "2025-12-31"),
            Window("phase_2026_latest", "2026 独立阶段至 2026-04-30", "phase", "2026-01-01", "2026-04-30"),
            Window("weak_2021_drawdown", "2021 核心回撤窗口", "weak", "2021-05-01", "2021-07-31"),
            Window("weak_2022_path", "2022 弱路径窗口", "weak", "2022-03-09", "2022-12-07"),
            Window("diagnostic_2025_redbox", "2025 红框诊断窗口", "diagnostic", "2025-04-16", "2025-07-25"),
        ]
    )
    return tuple(rows)


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    return s717._drawdown_pct(equity)


def _sharpe(equity: pd.Series) -> float:
    return s717._sharpe(equity)


def _variant_name(threshold: int) -> str:
    return f"{OFFICIAL_LIVE_PROFILE_NAME}_lossstreak{threshold:02d}_floor01_stage718"


def _threshold_spec(base: s660.s653.ForcedVariant, threshold: int) -> s660.s653.ForcedVariant:
    source = s717._threshold_spec(base, threshold)
    capital = replace(
        source.capital,
        variant=_variant_name(threshold),
        label=f"L{threshold}->0.1 robustness",
        note=(
            "Official Stage372/20w robustness validation for loss-streak threshold "
            f"{threshold}; all other official settings unchanged."
        ),
    )
    return replace(source, capital=capital, profile=f"official_stage372_lossstreak{threshold:02d}_robustness_stage718")


def _metric_rows(
    frame: pd.DataFrame,
    forced_events: pd.DataFrame,
    *,
    threshold: int,
    window: Window,
    spec: s660.s653.ForcedVariant,
) -> tuple[dict[str, Any], list[dict[str, Any]], pd.DataFrame]:
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

    row = {
        "threshold": int(threshold),
        "variant": spec.capital.variant,
        "label": spec.capital.label,
        "streak_risk_multipliers": s717._streak_multipliers(threshold),
        "window_name": window.name,
        "window_label": window.label,
        "window_group": window.group,
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
        "positive_return": int(float(equity.iloc[-1]) > OFFICIAL_LIVE_CAPITAL),
        "dd30_pass": int(float(dd.min()) >= -30.0),
        "dd40_pass": int(float(dd.min()) >= -40.0),
        "broker10_100_pass": int(margin.max() <= 100.0 + 1e-9),
    }

    cost_rows: list[dict[str, Any]] = []
    for multiplier in (1.0, 2.0, 3.0):
        stressed = equity - slippage.cumsum() * max(0.0, multiplier - 1.0)
        stressed_dd = _drawdown_pct(stressed)
        stressed_margin = (margin_exact / stressed.replace(0.0, np.nan) * 100.0).replace(
            [np.inf, -np.inf], np.nan
        ).fillna(0.0)
        cost_rows.append(
            {
                "threshold": int(threshold),
                "variant": spec.capital.variant,
                "window_name": window.name,
                "window_group": window.group,
                "cost_multiplier": float(multiplier),
                "end_equity": float(stressed.iloc[-1]),
                "total_return_pct": float((stressed.iloc[-1] / OFFICIAL_LIVE_CAPITAL - 1.0) * 100.0),
                "max_dd_pct": float(stressed_dd.min()),
                "sharpe": _sharpe(stressed),
                "max_broker10_margin_to_equity_pct": float(stressed_margin.max()),
                "account_survival_pass": int(stressed.min() > 0.0),
                "dd40_pass": int(float(stressed_dd.min()) >= -40.0),
                "broker10_100_pass": int(float(stressed_margin.max()) <= 100.0 + 1e-9),
            }
        )

    curve = pd.DataFrame(
        {
            "date": ordered["date"],
            "threshold": int(threshold),
            "variant": spec.capital.variant,
            "window_name": window.name,
            "window_group": window.group,
            "account_equity": equity,
            "drawdown_pct": dd,
            "net_pnl": net_pnl,
            "trade_count": trade_count,
            "total_slippage": slippage,
        }
    )
    return row, cost_rows, curve


def _comparison(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for window_name, group in summary.groupby("window_name", sort=False):
        base = group[group["threshold"].eq(BASE_THRESHOLD)]
        if base.empty:
            continue
        b = base.iloc[0]
        for _, c in group[group["threshold"].ne(BASE_THRESHOLD)].iterrows():
            base_ret = float(b["total_return_pct"])
            cand_ret = float(c["total_return_pct"])
            rows.append(
                {
                    "window_name": window_name,
                    "window_group": str(c["window_group"]),
                    "candidate_threshold": int(c["threshold"]),
                    "base_threshold": BASE_THRESHOLD,
                    "base_total_return_pct": base_ret,
                    "candidate_total_return_pct": cand_ret,
                    "return_retention_pct": cand_ret / base_ret * 100.0 if base_ret > 0 else np.nan,
                    "return_delta_pct": cand_ret - base_ret,
                    "base_max_dd_pct": float(b["max_dd_pct"]),
                    "candidate_max_dd_pct": float(c["max_dd_pct"]),
                    "delta_max_dd_pct": float(c["max_dd_pct"]) - float(b["max_dd_pct"]),
                    "base_sharpe": float(b["sharpe"]),
                    "candidate_sharpe": float(c["sharpe"]),
                    "delta_sharpe": float(c["sharpe"]) - float(b["sharpe"]),
                    "candidate_return_wins": int(cand_ret > base_ret),
                    "candidate_dd_wins": int(float(c["max_dd_pct"]) >= float(b["max_dd_pct"])),
                    "candidate_both_wins": int(cand_ret > base_ret and float(c["max_dd_pct"]) >= float(b["max_dd_pct"])),
                }
            )
    return pd.DataFrame(rows)


def _winner_by_window(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for window_name, group in summary.groupby("window_name", sort=False):
        ret = group.sort_values(["total_return_pct", "max_dd_pct", "sharpe"], ascending=[False, False, False]).iloc[0]
        dd = group.sort_values(["max_dd_pct", "total_return_pct", "sharpe"], ascending=[False, False, False]).iloc[0]
        rows.append(
            {
                "window_name": window_name,
                "window_group": str(ret["window_group"]),
                "return_winner_threshold": int(ret["threshold"]),
                "return_winner_total_return_pct": float(ret["total_return_pct"]),
                "return_winner_max_dd_pct": float(ret["max_dd_pct"]),
                "dd_winner_threshold": int(dd["threshold"]),
                "dd_winner_total_return_pct": float(dd["total_return_pct"]),
                "dd_winner_max_dd_pct": float(dd["max_dd_pct"]),
            }
        )
    return pd.DataFrame(rows)


def _robustness(summary: pd.DataFrame, cost: pd.DataFrame, comparison: pd.DataFrame, winners: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    cost2 = cost[cost["cost_multiplier"].eq(2.0)].copy()
    for threshold, group in summary.groupby("threshold", sort=True):
        group = group.copy()
        q = group[group["window_group"].eq("quarterly_start")]
        c2 = cost2[cost2["threshold"].eq(threshold)]
        q_c2 = c2[c2["window_group"].eq("quarterly_start")]
        comp = comparison[comparison["candidate_threshold"].eq(threshold)]
        qcomp = comp[comp["window_group"].eq("quarterly_start")]
        row = {
            "threshold": int(threshold),
            "window_count": int(len(group)),
            "quarterly_count": int(len(q)),
            "positive_return_count": int(group["positive_return"].sum()),
            "quarterly_positive_return_count": int(q["positive_return"].sum()),
            "dd30_pass_count": int(group["dd30_pass"].sum()),
            "dd40_pass_count": int(group["dd40_pass"].sum()),
            "quarterly_dd40_pass_count": int(q["dd40_pass"].sum()),
            "cost2_dd40_pass_count": int(c2["dd40_pass"].sum()) if not c2.empty else 0,
            "quarterly_cost2_dd40_pass_count": int(q_c2["dd40_pass"].sum()) if not q_c2.empty else 0,
            "best_return_count": int(winners["return_winner_threshold"].eq(threshold).sum()),
            "quarterly_best_return_count": int(
                winners[winners["window_group"].eq("quarterly_start")]["return_winner_threshold"].eq(threshold).sum()
            ),
            "best_dd_count": int(winners["dd_winner_threshold"].eq(threshold).sum()),
            "quarterly_best_dd_count": int(
                winners[winners["window_group"].eq("quarterly_start")]["dd_winner_threshold"].eq(threshold).sum()
            ),
            "median_return_pct": float(group["total_return_pct"].median()),
            "p10_return_pct": float(group["total_return_pct"].quantile(0.10)),
            "worst_return_pct": float(group["total_return_pct"].min()),
            "median_max_dd_pct": float(group["max_dd_pct"].median()),
            "worst_max_dd_pct": float(group["max_dd_pct"].min()),
            "mean_sharpe": float(group["sharpe"].mean()),
        }
        if threshold == BASE_THRESHOLD:
            row.update(
                {
                    "median_retention_vs_threshold3": 100.0,
                    "quarterly_return_wins_vs_threshold3": np.nan,
                    "quarterly_dd_wins_vs_threshold3": np.nan,
                    "quarterly_both_wins_vs_threshold3": np.nan,
                }
            )
        else:
            row.update(
                {
                    "median_retention_vs_threshold3": float(comp["return_retention_pct"].median()) if not comp.empty else np.nan,
                    "quarterly_return_wins_vs_threshold3": int(qcomp["candidate_return_wins"].sum()) if not qcomp.empty else 0,
                    "quarterly_dd_wins_vs_threshold3": int(qcomp["candidate_dd_wins"].sum()) if not qcomp.empty else 0,
                    "quarterly_both_wins_vs_threshold3": int(qcomp["candidate_both_wins"].sum()) if not qcomp.empty else 0,
                }
            )
        rows.append(row)
    return pd.DataFrame(rows)


def _decision(robustness: pd.DataFrame, comparison: pd.DataFrame, winners: pd.DataFrame) -> dict[str, Any]:
    base = robustness[robustness["threshold"].eq(BASE_THRESHOLD)].iloc[0].to_dict()
    qstart = winners[winners["window_group"].eq("quarterly_start")]
    base_q_return_wins = int(qstart["return_winner_threshold"].eq(BASE_THRESHOLD).sum())
    base_q_dd_wins = int(qstart["dd_winner_threshold"].eq(BASE_THRESHOLD).sum())
    challenger_return_wins = {
        int(row.threshold): int(row.quarterly_return_wins_vs_threshold3)
        for row in robustness[robustness["threshold"].ne(BASE_THRESHOLD)].itertuples(index=False)
    }
    challenger_dd_wins = {
        int(row.threshold): int(row.quarterly_dd_wins_vs_threshold3)
        for row in robustness[robustness["threshold"].ne(BASE_THRESHOLD)].itertuples(index=False)
    }
    gates = {
        "threshold3_quarterly_return_winner_share_ge50": base_q_return_wins >= 13,
        "threshold3_quarterly_dd_winner_share_ge40": base_q_dd_wins >= 10,
        "no_challenger_quarterly_return_wins_ge_threshold3": all(value < 13 for value in challenger_return_wins.values()),
        "threshold3_all_quarterly_positive": int(base["quarterly_positive_return_count"]) == int(base["quarterly_count"]),
        "threshold3_all_quarterly_dd40_pass": int(base["quarterly_dd40_pass_count"]) == int(base["quarterly_count"]),
        "threshold3_cost2_quarterly_dd40_pass_ge80": int(base["quarterly_cost2_dd40_pass_count"]) >= int(0.8 * base["quarterly_count"]),
    }
    return {
        "stage": "Stage002",
        "script_stage": "Stage718",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "baseline_profile": OFFICIAL_LIVE_PROFILE_NAME,
        "thresholds": list(THRESHOLDS),
        "base_threshold": BASE_THRESHOLD,
        "decision": "threshold3_supported_by_robustness_not_proven" if all(gates.values()) else "threshold3_not_fully_proven",
        "gates": gates,
        "threshold3_quarterly_return_wins": base_q_return_wins,
        "threshold3_quarterly_dd_wins": base_q_dd_wins,
        "challenger_return_wins_vs_threshold3": challenger_return_wins,
        "challenger_dd_wins_vs_threshold3": challenger_dd_wins,
        "overfit_judgement": (
            "Robustness validation reduces curve-fit risk, but historical validation cannot prove universality. "
            "Forward/paper observation remains necessary."
        ),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "cost": str(COST_PATH),
            "comparison": str(COMPARISON_PATH),
            "robustness": str(ROBUSTNESS_PATH),
            "winner_by_window": str(WINNER_PATH),
            "curves": str(CURVES_PATH),
            "report": str(REPORT_PATH),
            "chart": str(CHART_PATH),
            "decision": str(DECISION_PATH),
        },
    }


def _plot(summary: pd.DataFrame, comparison: pd.DataFrame, robustness: pd.DataFrame, winners: pd.DataFrame) -> None:
    q = summary[summary["window_group"].eq("quarterly_start")].copy()
    if q.empty:
        return
    q["quarter"] = q["window_name"].str.replace("qstart_", "", regex=False).str.upper()
    quarters = list(dict.fromkeys(q["quarter"].tolist()))
    x = np.arange(len(quarters))
    colors = {3: "#2563eb", 4: "#ea580c", 6: "#16a34a"}

    fig, axes = plt.subplots(4, 1, figsize=(16, 13), sharex=False)
    for threshold in THRESHOLDS:
        group = q[q["threshold"].eq(threshold)].set_index("quarter").reindex(quarters)
        axes[0].plot(x, group["total_return_pct"], label=f"L{threshold}->0.1", color=colors[threshold], linewidth=1.6)
        axes[1].plot(x, group["max_dd_pct"], label=f"L{threshold}->0.1", color=colors[threshold], linewidth=1.6)
    axes[0].axhline(0, color="#475569", linewidth=0.8)
    axes[0].set_title("Quarterly independent starts: total return")
    axes[0].set_ylabel("Return %")
    axes[1].axhline(-40, color="#ef4444", linestyle="--", linewidth=0.9)
    axes[1].axhline(-30, color="#f97316", linestyle=":", linewidth=0.9)
    axes[1].set_title("Quarterly independent starts: max drawdown")
    axes[1].set_ylabel("Max DD %")
    for ax in axes[:2]:
        ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.35)
        ax.legend(loc="best", ncol=3)

    qcomp = comparison[comparison["window_group"].eq("quarterly_start")].copy()
    for idx, threshold in enumerate((4, 6)):
        group = qcomp[qcomp["candidate_threshold"].eq(threshold)].copy()
        group["quarter"] = group["window_name"].str.replace("qstart_", "", regex=False).str.upper()
        aligned = group.set_index("quarter").reindex(quarters)
        axes[2].bar(x + (idx - 0.5) * 0.32, aligned["return_retention_pct"], width=0.32, label=f"L{threshold}/L3")
    axes[2].axhline(100, color="#64748b", linestyle=":", linewidth=0.9)
    axes[2].axhline(70, color="#f97316", linestyle="--", linewidth=0.9)
    axes[2].set_title("Quarterly retention vs threshold 3")
    axes[2].set_ylabel("Retention %")
    axes[2].grid(True, axis="y", linestyle="--", linewidth=0.5, alpha=0.35)
    axes[2].legend(loc="best")

    axes[3].bar(
        robustness["threshold"].astype(str),
        robustness["quarterly_best_return_count"],
        color=[colors[int(threshold)] for threshold in robustness["threshold"]],
    )
    axes[3].set_title("Quarterly best-return count by threshold")
    axes[3].set_ylabel("Best-return windows")
    axes[3].set_xlabel("Threshold")
    axes[3].grid(True, axis="y", linestyle="--", linewidth=0.5, alpha=0.35)

    axes[2].set_xticks(x)
    axes[2].set_xticklabels(quarters, rotation=45, ha="right")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(quarters, rotation=45, ha="right")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(quarters, rotation=45, ha="right")
    fig.suptitle("Stage718 Loss-Streak Threshold Robustness: L3 vs L4 vs L6")
    fig.tight_layout(rect=[0, 0.02, 1, 0.98])
    fig.savefig(CHART_PATH, dpi=170)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    cost: pd.DataFrame,
    comparison: pd.DataFrame,
    robustness: pd.DataFrame,
    winners: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    summary_cols = [
        "threshold",
        "window_name",
        "window_group",
        "total_return_pct",
        "max_dd_pct",
        "sharpe",
        "total_slippage",
        "total_trade_count",
        "forced_margin_deleverage_count",
        "forced_margin_deleverage_closed_volume",
    ]
    comparison_cols = [
        "window_name",
        "window_group",
        "candidate_threshold",
        "return_retention_pct",
        "return_delta_pct",
        "delta_max_dd_pct",
        "delta_sharpe",
        "candidate_return_wins",
        "candidate_dd_wins",
    ]
    lines = [
        "# Stage002 / Script718 Loss-Streak Threshold Robustness",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 当前 official live：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_PROFILE_NAME}`",
        f"- 阈值：`{','.join(str(item) for item in THRESHOLDS)}`；触发后风险倍率 `{FLOOR_MULTIPLIER}`。",
        "- 窗口：25 个季度独立启动 + 4 个阶段窗口 + 2 个弱窗口 + 1 个红框诊断窗口。",
        "- 红框窗口仅作诊断，不作为普适性通过依据。",
        "- 不修改正式配置、不连接 CTP、不调用下单。",
        "",
        "## Decision",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- gates：`{json.dumps(decision['gates'], ensure_ascii=False)}`",
        "",
        "## Robustness",
        "",
        _md_table(robustness, max_rows=20),
        "",
        "## Winner By Window",
        "",
        _md_table(winners, max_rows=60),
        "",
        "## Comparison Vs Threshold 3",
        "",
        _md_table(comparison[comparison_cols], max_rows=80),
        "",
        "## Summary",
        "",
        _md_table(summary[summary_cols], max_rows=120),
        "",
        "## Cost Stress",
        "",
        _md_table(cost, max_rows=120),
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    metadata = s513._metadata()
    base = s660._official_spec(metadata)
    specs = {threshold: _threshold_spec(base, threshold) for threshold in THRESHOLDS}

    summary_rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    windows = _windows()
    total_runs = len(windows) * len(THRESHOLDS)
    run_index = 0
    for window in windows:
        start = pd.Timestamp(window.start)
        end = pd.Timestamp(window.end)
        for threshold in THRESHOLDS:
            run_index += 1
            spec = specs[threshold]
            print(
                f"[stage718] {run_index}/{total_runs} {window.name} threshold={threshold}",
                flush=True,
            )
            daily, forced_events = s660._run_independent_window(
                spec=spec,
                metadata=metadata,
                analysis_start=start,
                analysis_end=end,
            )
            row, costs, curve = _metric_rows(daily, forced_events, threshold=threshold, window=window, spec=spec)
            summary_rows.append(row)
            cost_rows.extend(costs)
            curve_frames.append(curve)

    summary = pd.DataFrame(summary_rows)
    cost = pd.DataFrame(cost_rows)
    curves = pd.concat(curve_frames, ignore_index=True, sort=False)
    comparison = _comparison(summary)
    winners = _winner_by_window(summary)
    robustness = _robustness(summary, cost, comparison, winners)
    decision = _decision(robustness, comparison, winners)

    _plot(summary, comparison, robustness, winners)
    _write_report(summary, cost, comparison, robustness, winners, decision)
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    robustness.to_csv(ROBUSTNESS_PATH, index=False, encoding="utf-8-sig")
    winners.to_csv(WINNER_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"chart={CHART_PATH}")


if __name__ == "__main__":
    main()
