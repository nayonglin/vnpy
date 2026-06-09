from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path
from typing import Any

import pandas as pd

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage653_stage526_200k_forced_margin_deleverage as s653
import analyze_qmt_roll_stage659_stage653_2026_ytd_latest_ai_shadow as s659
import analyze_qmt_roll_stage660_stage653_multiperiod_live_audit as s660
from qmt_roll_official_live_config import OFFICIAL_LIVE_PROFILE_NAME, OFFICIAL_LIVE_VERSION


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage671_stage372_no_maxpos4_multiperiod_v1"
OUTPUT_PREFIX = "qmt_roll_stage671_stage372_no_maxpos4_multiperiod"
LINE_ID = "futures_trend_drawdown30_preserve_return"

BASE_VARIANT = OFFICIAL_LIVE_PROFILE_NAME
CANDIDATE_VARIANT = "stage372_20w_recovery_sleeve_r080_pc25_maxpos10"
NO_MAXPOS_LIMIT = 10
YTD_TARGET_DATE = "2026-06-05"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
ROLLING_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rolling_{MODEL_TAG}.csv"
MARGIN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_margin_usage_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _candidate_spec(metadata: dict[str, Any]) -> s653.ForcedVariant:
    base = s660._official_spec(metadata)
    capital = replace(
        base.capital,
        variant=CANDIDATE_VARIANT,
        label="20w Stage372 recovery sleeve maxpos10",
        max_concurrent_positions=NO_MAXPOS_LIMIT,
        note=(
            "Stage671 candidate: keep Stage372 force95->80 and recovery sleeve, "
            "but relax max_concurrent_positions from 4 to strategy default 10."
        ),
    )
    overrides = {**base.overrides, "max_concurrent_positions": NO_MAXPOS_LIMIT}
    return replace(base, capital=capital, overrides=overrides, profile="stage372_recovery_sleeve_maxpos10")


def _forced_events_for_metrics(events: pd.DataFrame) -> pd.DataFrame:
    """s660 metrics filter forced events by official variant; normalize for A/C counts."""
    if events.empty:
        return events
    normalized = events.copy()
    normalized["variant"] = OFFICIAL_LIVE_PROFILE_NAME
    return normalized


def _run_latest_ytd(spec: s653.ForcedVariant, metadata: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    daily, positions, _usage, forced_events = s659._run_variant_dynamic(
        spec,
        metadata,
        datetime.strptime("2026-01-01", "%Y-%m-%d"),
        datetime.strptime(YTD_TARGET_DATE, "%Y-%m-%d"),
        s659.DEFAULT_AI_ELIGIBILITY_PATH.resolve(),
    )
    daily["account_capital"] = spec.capital.account_capital
    daily["c3_capital"] = spec.capital.c3_capital
    daily["profile"] = spec.profile
    positions["account_capital"] = spec.capital.account_capital
    positions["c3_capital"] = spec.capital.c3_capital
    c3_margin_daily, _product_margin = s513._position_margin(positions, metadata)
    combined = s650._combine_daily(daily, c3_margin_daily, spec.capital)
    combined["profile"] = spec.profile
    for column in [
        "forced_margin_deleverage_count",
        "forced_margin_deleverage_closed_volume",
        "forced_margin_deleverage_ratio",
        "forced_margin_deleverage_max_observed_ratio",
    ]:
        combined[column] = daily[column].iloc[0] if column in daily.columns and not daily.empty else 0
    return combined, forced_events


def _add_variant_to_outputs(
    *,
    row: dict[str, Any],
    curve: pd.DataFrame,
    costs: list[dict[str, Any]],
    variant: str,
) -> tuple[dict[str, Any], pd.DataFrame, list[dict[str, Any]]]:
    row = dict(row)
    row["variant"] = variant
    curve = curve.copy()
    curve["variant"] = variant
    out_costs: list[dict[str, Any]] = []
    for cost in costs:
        item = dict(cost)
        item["variant"] = variant
        out_costs.append(item)
    return row, curve, out_costs


def _rolling_metrics(curves: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for variant, frame in curves[curves["window_name"].eq("full_2020_20260430")].groupby("variant", sort=True):
        ordered = frame.sort_values("date").reset_index(drop=True)
        for holding_days in (63, 126, 252):
            returns: list[float] = []
            dds: list[float] = []
            starts: list[str] = []
            ends: list[str] = []
            for start in range(0, len(ordered) - holding_days + 1):
                window = ordered.iloc[start : start + holding_days].copy()
                equity = window["rebased_equity"].astype(float).reset_index(drop=True)
                if len(equity) < 2 or float(equity.iloc[0]) <= 0:
                    continue
                ret = float((equity.iloc[-1] / equity.iloc[0] - 1.0) * 100.0)
                dd = float(s660._drawdown_pct(equity).min())
                returns.append(ret)
                dds.append(dd)
                starts.append(pd.Timestamp(window["date"].iloc[0]).date().isoformat())
                ends.append(pd.Timestamp(window["date"].iloc[-1]).date().isoformat())
            if not returns:
                continue
            ret_series = pd.Series(returns)
            worst_idx = int(ret_series.idxmin())
            rows.append(
                {
                    "variant": variant,
                    "holding_days": holding_days,
                    "sample_count": int(len(returns)),
                    "min_return_pct": float(ret_series.min()),
                    "p05_return_pct": float(ret_series.quantile(0.05)),
                    "median_return_pct": float(ret_series.median()),
                    "positive_rate_pct": float(ret_series.gt(0.0).mean() * 100.0),
                    "min_window_dd_pct": float(min(dds)),
                    "worst_return_start": starts[worst_idx],
                    "worst_return_end": ends[worst_idx],
                }
            )
    return pd.DataFrame(rows)


def _comparison(summary: pd.DataFrame, cost: pd.DataFrame) -> pd.DataFrame:
    base = summary[summary["variant"].eq(BASE_VARIANT)].set_index("window_name")
    cand = summary[summary["variant"].eq(CANDIDATE_VARIANT)].set_index("window_name")
    base_cost = cost[(cost["variant"].eq(BASE_VARIANT)) & (cost["cost_multiplier"].eq(2.0))].set_index("window_name")
    cand_cost = cost[
        (cost["variant"].eq(CANDIDATE_VARIANT)) & (cost["cost_multiplier"].eq(2.0))
    ].set_index("window_name")
    rows: list[dict[str, Any]] = []
    for name in cand.index:
        if name not in base.index:
            continue
        b = base.loc[name]
        c = cand.loc[name]
        row = {
            "window_name": name,
            "window_label": c["window_label"],
            "base_return_pct": float(b["rebased_total_return_pct"]),
            "candidate_return_pct": float(c["rebased_total_return_pct"]),
            "delta_return_pct": float(c["rebased_total_return_pct"] - b["rebased_total_return_pct"]),
            "base_max_dd_pct": float(b["rebased_max_dd_pct"]),
            "candidate_max_dd_pct": float(c["rebased_max_dd_pct"]),
            "delta_max_dd_pct": float(c["rebased_max_dd_pct"] - b["rebased_max_dd_pct"]),
            "base_sharpe": float(b["rebased_sharpe"]),
            "candidate_sharpe": float(c["rebased_sharpe"]),
            "delta_sharpe": float(c["rebased_sharpe"] - b["rebased_sharpe"]),
            "base_trades": float(b["total_trade_count"]),
            "candidate_trades": float(c["total_trade_count"]),
            "delta_trades": float(c["total_trade_count"] - b["total_trade_count"]),
            "base_slippage": float(b["total_slippage"]),
            "candidate_slippage": float(c["total_slippage"]),
            "delta_slippage": float(c["total_slippage"] - b["total_slippage"]),
            "base_margin_peak_pct": float(b["max_broker10_margin_to_rebased_equity_pct"]),
            "candidate_margin_peak_pct": float(c["max_broker10_margin_to_rebased_equity_pct"]),
            "delta_margin_peak_pct": float(
                c["max_broker10_margin_to_rebased_equity_pct"]
                - b["max_broker10_margin_to_rebased_equity_pct"]
            ),
        }
        if name in base_cost.index and name in cand_cost.index:
            row["base_2x_max_dd_pct"] = float(base_cost.loc[name, "max_dd_pct"])
            row["candidate_2x_max_dd_pct"] = float(cand_cost.loc[name, "max_dd_pct"])
            row["delta_2x_max_dd_pct"] = float(cand_cost.loc[name, "max_dd_pct"] - base_cost.loc[name, "max_dd_pct"])
        rows.append(row)
    return pd.DataFrame(rows)


def _margin_usage(curves: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    full = curves[curves["window_name"].eq("full_2020_20260430")]
    for variant, frame in full.groupby("variant", sort=True):
        margin = pd.to_numeric(frame["broker10_margin_to_rebased_equity_pct"], errors="coerce").fillna(0.0)
        active = margin.gt(1e-9)
        rows.append(
            {
                "variant": variant,
                "active_days": int(active.sum()),
                "active_rate_pct": float(active.mean() * 100.0),
                "avg_margin_all_days_pct": float(margin.mean()),
                "avg_margin_active_days_pct": float(margin[active].mean()) if int(active.sum()) else 0.0,
                "p95_margin_pct": float(margin.quantile(0.95)),
                "max_margin_pct": float(margin.max()),
                "days_gt_30pct": int(margin.gt(30.0).sum()),
                "days_gt_50pct": int(margin.gt(50.0).sum()),
                "days_gt_70pct": int(margin.gt(70.0).sum()),
                "days_gt_90pct": int(margin.gt(90.0).sum()),
                "days_gt_100pct": int(margin.gt(100.0).sum()),
            }
        )
    return pd.DataFrame(rows)


def _decision(summary: pd.DataFrame, cost: pd.DataFrame, comparison: pd.DataFrame, rolling: pd.DataFrame) -> dict[str, Any]:
    full_cmp = comparison[comparison["window_name"].eq("full_2020_20260430")].iloc[0]
    ytd_cmp = comparison[comparison["window_name"].eq("ytd_2026_latest_ai")]
    candidate_full = summary[
        (summary["variant"].eq(CANDIDATE_VARIANT)) & (summary["window_name"].eq("full_2020_20260430"))
    ].iloc[0]
    candidate_cost2 = cost[
        (cost["variant"].eq(CANDIDATE_VARIANT))
        & (cost["window_name"].eq("full_2020_20260430"))
        & (cost["cost_multiplier"].eq(2.0))
    ].iloc[0]

    checks: list[dict[str, Any]] = []

    def add(name: str, status: str, value: float, threshold: str, comment: str) -> None:
        checks.append({"check_name": name, "status": status, "value": value, "threshold": threshold, "comment": comment})

    add(
        "candidate_full_dd40",
        "pass" if float(candidate_full["rebased_max_dd_pct"]) >= -40.0 else "fail",
        float(candidate_full["rebased_max_dd_pct"]),
        ">= -40",
        "候选全周期正常成本最大回撤。",
    )
    add(
        "candidate_margin100",
        "pass" if int(candidate_full["days_over_100pct"]) == 0 else "fail",
        float(candidate_full["days_over_100pct"]),
        "0 days",
        "候选 broker10 保证金不穿100%。",
    )
    add(
        "candidate_2x_dd_not_worse",
        "pass" if float(full_cmp.get("delta_2x_max_dd_pct", -999.0)) >= -2.0 else "fail",
        float(full_cmp.get("delta_2x_max_dd_pct", -999.0)),
        ">= -2pp vs A",
        "候选2x成本回撤不能明显劣于当前正式版。",
    )
    add(
        "candidate_return_improves",
        "pass" if float(full_cmp["delta_return_pct"]) > 0 else "fail",
        float(full_cmp["delta_return_pct"]),
        "> 0",
        "关闭maxpos4至少应提升全周期收益。",
    )
    add(
        "candidate_margin_peak_not_much_worse",
        "pass" if float(full_cmp["delta_margin_peak_pct"]) <= 10.0 else "fail",
        float(full_cmp["delta_margin_peak_pct"]),
        "<= +10pp",
        "并发放开后保证金峰值不能显著恶化。",
    )
    add(
        "candidate_2x_cost_dd40",
        "pass" if float(candidate_cost2["max_dd_pct"]) >= -40.0 else "watch",
        float(candidate_cost2["max_dd_pct"]),
        ">= -40 preferred",
        "候选2x成本压力回撤。",
    )
    if not ytd_cmp.empty:
        row = ytd_cmp.iloc[0]
        add(
            "latest_ytd_not_materially_worse",
            "pass" if float(row["delta_return_pct"]) >= -2.0 and float(row["delta_max_dd_pct"]) >= -2.0 else "fail",
            float(row["delta_return_pct"]),
            "return/dd delta >= -2pp",
            "最新AI池YTD不应明显弱于当前正式版。",
        )
    candidate_rolling = rolling[rolling["variant"].eq(CANDIDATE_VARIANT)]
    if not candidate_rolling.empty:
        add(
            "rolling_p05_return_min",
            "watch" if float(candidate_rolling["p05_return_pct"].min()) < 0.0 else "pass",
            float(candidate_rolling["p05_return_pct"].min()),
            ">= 0 preferred",
            "任意启动短周期左尾。",
        )

    check_frame = pd.DataFrame(checks)
    hard_fail = check_frame[check_frame["status"].eq("fail")]["check_name"].astype(str).tolist()
    watch = check_frame[check_frame["status"].eq("watch")]["check_name"].astype(str).tolist()
    decision = (
        "stage372_no_maxpos4_rejected"
        if hard_fail
        else "stage372_no_maxpos4_watch_not_auto_promote"
    )
    return {
        "stage": "Stage383",
        "script_stage": "Stage671",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "baseline": BASE_VARIANT,
        "candidate": CANDIDATE_VARIANT,
        "candidate_change": {
            "max_concurrent_positions_before": 4,
            "max_concurrent_positions_after": NO_MAXPOS_LIMIT,
            "official_config_changed": False,
        },
        "decision": decision,
        "hard_fail_checks": hard_fail,
        "watch_checks": watch,
        "checks": checks,
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "cost": str(COST_PATH),
            "comparison": str(COMPARISON_PATH),
            "rolling": str(ROLLING_PATH),
            "margin": str(MARGIN_PATH),
            "curves": str(CURVES_PATH),
            "report": str(REPORT_PATH),
            "decision": str(DECISION_PATH),
        },
    }


def _write_report(
    summary: pd.DataFrame,
    cost: pd.DataFrame,
    comparison: pd.DataFrame,
    rolling: pd.DataFrame,
    margin_usage: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    checks = pd.DataFrame(decision["checks"])
    lines = [
        "# Stage671 Stage372 关闭 maxpos4 多周期审计",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 当前 official live：`{OFFICIAL_LIVE_VERSION}` / `{BASE_VARIANT}`",
        f"- 候选：`{CANDIDATE_VARIANT}`，只把 `max_concurrent_positions` 从 `4` 放宽到 `{NO_MAXPOS_LIMIT}`。",
        "- 其它保持不变：20万、`risk_multiplier=0.80`、单品种保证金cap25%、95%->80%强制降保证金、恢复仓 sleeve。",
        "- 本阶段不修改正式配置、不连接 CTP、不调用下单。",
        "",
        "## 决策检查",
        "",
        _md_table(checks),
        "",
        "## A/C 全窗口结果",
        "",
        _md_table(
            summary[
                [
                    "variant",
                    "window_name",
                    "rebased_end_equity",
                    "rebased_total_return_pct",
                    "rebased_max_dd_pct",
                    "rebased_sharpe",
                    "max_broker10_margin_to_rebased_equity_pct",
                    "days_over_100pct",
                    "days_over_90pct",
                    "total_slippage",
                    "total_trade_count",
                    "nonzero_daily_win_rate_pct",
                    "forced_margin_deleverage_count",
                    "forced_margin_deleverage_closed_volume",
                    "deployable_pass",
                ]
            ],
            max_rows=120,
        ),
        "",
        "## C vs A",
        "",
        _md_table(comparison, max_rows=80),
        "",
        "## 资金占用",
        "",
        _md_table(margin_usage),
        "",
        "## 成本压力",
        "",
        _md_table(cost, max_rows=120),
        "",
        "## 滚动窗口",
        "",
        _md_table(rolling),
        "",
        "## 决策",
        "",
        f"- 决策：`{decision['decision']}`。",
        f"- 硬失败项：`{', '.join(decision['hard_fail_checks']) or '无'}`。",
        f"- 观察项：`{', '.join(decision['watch_checks']) or '无'}`。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    metadata = s513._metadata()
    specs = [s660._official_spec(metadata), _candidate_spec(metadata)]

    summary_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    cost_rows: list[dict[str, Any]] = []

    for spec in specs:
        for window_name, window_label, group, start, end in s660.WINDOWS:
            analysis_start = pd.Timestamp(start)
            analysis_end = pd.Timestamp(end) if end else pd.Timestamp("2026-04-30")
            print(
                f"[stage671] running {spec.capital.variant} {window_name}: "
                f"{analysis_start.date()} -> {analysis_end.date()}",
                flush=True,
            )
            frame, forced_events = s660._run_independent_window(
                spec=spec,
                metadata=metadata,
                analysis_start=analysis_start,
                analysis_end=analysis_end,
            )
            row, curve, costs = s660._window_metrics(
                frame,
                window_name=window_name,
                window_label=window_label,
                group=group,
                source_name=f"{spec.capital.variant}_independent_window",
                caveat="历史窗口独立重跑，20万 fresh capital；本阶段只比较max_concurrent_positions。",
                forced_events=_forced_events_for_metrics(forced_events),
            )
            row, curve, costs = _add_variant_to_outputs(
                row=row,
                curve=curve,
                costs=costs,
                variant=spec.capital.variant,
            )
            summary_rows.append(row)
            curve_frames.append(curve)
            cost_rows.extend(costs)

        ytd_frame, ytd_forced = _run_latest_ytd(spec, metadata)
        ytd_row, ytd_curve, ytd_costs = s660._window_metrics(
            ytd_frame,
            window_name="ytd_2026_latest_ai",
            window_label=f"2026年初至{YTD_TARGET_DATE}最新AI池",
            group="latest_ytd",
            source_name=f"{spec.capital.variant}_latest_ai_ytd",
            caveat="最新AI池独立年初至今影子盘；本阶段只比较max_concurrent_positions。",
            forced_events=_forced_events_for_metrics(ytd_forced),
        )
        ytd_row, ytd_curve, ytd_costs = _add_variant_to_outputs(
            row=ytd_row,
            curve=ytd_curve,
            costs=ytd_costs,
            variant=spec.capital.variant,
        )
        summary_rows.append(ytd_row)
        curve_frames.append(ytd_curve)
        cost_rows.extend(ytd_costs)

    summary = pd.DataFrame(summary_rows)
    curves = pd.concat(curve_frames, ignore_index=True, sort=False)
    cost = pd.DataFrame(cost_rows)
    comparison = _comparison(summary, cost)
    rolling = _rolling_metrics(curves)
    margin_usage = _margin_usage(curves)
    decision = _decision(summary, cost, comparison, rolling)

    _write_report(summary, cost, comparison, rolling, margin_usage, decision)
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    rolling.to_csv(ROLLING_PATH, index=False, encoding="utf-8-sig")
    margin_usage.to_csv(MARGIN_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
