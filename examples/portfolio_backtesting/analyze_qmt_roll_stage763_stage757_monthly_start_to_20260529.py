from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
import numpy as np
import pandas as pd
from concurrent.futures import ProcessPoolExecutor, as_completed

import analyze_qmt_roll_stage759_stage757_monthly_start as s759


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage763_stage757_monthly_start_to_20260529_v1"
OUTPUT_PREFIX = "qmt_roll_stage763_stage757_monthly_start_to_20260529"
LINE_ID = "futures_trend_winner_trade_forensics"

ANALYSIS_END = pd.Timestamp("2026-05-29")
MONTH_STARTS = tuple(pd.date_range("2020-01-01", ANALYSIS_END.normalize(), freq="MS"))

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
CHECKS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_checks_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
RETURN_HEATMAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_return_heatmap_{MODEL_TAG}.png"


def _patch_stage759_globals() -> None:
    s759.MODEL_TAG = MODEL_TAG
    s759.OUTPUT_PREFIX = OUTPUT_PREFIX
    s759.ANALYSIS_END = ANALYSIS_END
    s759.MONTH_STARTS = MONTH_STARTS
    s759.SUMMARY_PATH = SUMMARY_PATH
    s759.CANDIDATE_SUMMARY_PATH = SUMMARY_PATH
    s759.COST_PATH = COST_PATH
    s759.CURVES_PATH = CURVES_PATH
    s759.CHECKS_PATH = CHECKS_PATH
    s759.DECISION_PATH = DECISION_PATH
    s759.REPORT_PATH = REPORT_PATH
    s759.RETURN_HEATMAP_PATH = RETURN_HEATMAP_PATH
    s759.MAX_WORKERS = max(1, min(4, s759.MAX_WORKERS))


def _candidate_stats(label: str, frame: pd.DataFrame) -> dict[str, Any]:
    returns = pd.to_numeric(frame["rebased_total_return_pct"], errors="coerce")
    dd = pd.to_numeric(frame["rebased_max_dd_pct"], errors="coerce")
    return {
        "bucket": label,
        "start_count": int(len(frame)),
        "positive_count": int((returns > 0.0).sum()),
        "positive_rate_pct": float((returns > 0.0).mean() * 100.0),
        "median_return_pct": float(returns.median()),
        "p10_return_pct": float(returns.quantile(0.10)),
        "min_return_pct": float(returns.min()),
        "max_return_pct": float(returns.max()),
        "worst_return_start": str(frame.loc[returns.idxmin(), "start_month"]),
        "best_return_start": str(frame.loc[returns.idxmax(), "start_month"]),
        "median_max_dd_pct": float(dd.median()),
        "worst_max_dd_pct": float(dd.min()),
        "dd30_fail_count": int((dd < -30.0).sum()),
        "dd40_fail_count": int((dd < -40.0).sum()),
    }


def _checks(stage757: pd.DataFrame) -> pd.DataFrame:
    rows = [
        _candidate_stats("stage757_all_monthly_starts_to_20260529", stage757),
        _candidate_stats("stage757_mature_ge63_trading_days", stage757[stage757["mature_63d"].eq(1)]),
        _candidate_stats("stage757_mature_ge126_trading_days", stage757[stage757["mature_126d"].eq(1)]),
        _candidate_stats("stage757_mature_ge252_trading_days", stage757[stage757["mature_252d"].eq(1)]),
    ]
    for year, group in stage757.groupby("start_year", sort=True):
        rows.append(_candidate_stats(f"stage757_start_year_{int(year)}", group))
    return pd.DataFrame(rows)


def _heat_values(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    return (
        frame.pivot_table(index="start_year", columns="start_month_num", values=column, aggfunc="first")
        .sort_index()
        .reindex(columns=list(range(1, 13)))
    )


def _plot_return_heatmap(stage757: pd.DataFrame) -> None:
    table = _heat_values(stage757, "rebased_total_return_pct")
    values = table.to_numpy(dtype=float)
    finite = values[np.isfinite(values)]
    vmax = max(float(np.nanpercentile(finite, 95)), 100.0) if finite.size else 100.0
    vmin = min(float(np.nanpercentile(finite, 5)), -30.0) if finite.size else -30.0
    norm = TwoSlopeNorm(vmin=vmin, vcenter=0.0, vmax=vmax)

    fig, ax = plt.subplots(figsize=(17, 5.8))
    image = ax.imshow(values, aspect="auto", cmap="RdYlGn", norm=norm)
    ax.set_title("Stage757 return heatmap by start year/month to 2026-05-29")
    ax.set_yticks(np.arange(len(table.index)))
    ax.set_yticklabels([str(int(item)) for item in table.index])
    ax.set_xticks(np.arange(12))
    ax.set_xticklabels([str(i) for i in range(1, 13)])
    ax.set_xlabel("Start month")
    ax.set_ylabel("Start year")
    for y in range(values.shape[0]):
        for x in range(values.shape[1]):
            value = values[y, x]
            if not np.isfinite(value):
                continue
            text_color = "white" if abs(value) > max(abs(vmin), abs(vmax)) * 0.45 else "#111827"
            ax.text(x, y, f"{value:.0f}", ha="center", va="center", fontsize=8, color=text_color)
    fig.colorbar(image, ax=ax, fraction=0.018, pad=0.01, label="Return %")
    fig.tight_layout()
    fig.savefig(RETURN_HEATMAP_PATH, dpi=170)
    plt.close(fig)


def _decision(summary: pd.DataFrame, checks: pd.DataFrame) -> dict[str, Any]:
    all_row = checks[checks["bucket"].eq("stage757_all_monthly_starts_to_20260529")].iloc[0]
    mature = checks[checks["bucket"].eq("stage757_mature_ge252_trading_days")].iloc[0]
    hard_fail: list[str] = []
    watch: list[str] = []
    if int(mature["dd40_fail_count"]) > 0:
        hard_fail.append("mature252_stage757_dd40_fail_exists")
    if int(all_row["positive_count"]) < int(all_row["start_count"]) * 0.90:
        watch.append("stage757_all_positive_rate_lt90pct")
    if int(mature["positive_count"]) < int(mature["start_count"]):
        watch.append("mature252_not_all_positive")
    return {
        "stage": "Stage763",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "stage757_variant": s759.s757.CANDIDATE_VARIANT,
        "analysis_start_first": MONTH_STARTS[0].strftime("%Y-%m-%d"),
        "analysis_start_last": MONTH_STARTS[-1].strftime("%Y-%m-%d"),
        "analysis_end": ANALYSIS_END.strftime("%Y-%m-%d"),
        "monthly_start_count": int(len(summary)),
        "decision": "stage757_monthly_start_to_20260529_not_promoted" if hard_fail else "stage757_monthly_start_to_20260529_watch",
        "hard_fail_checks": hard_fail,
        "watch_checks": watch,
        "change": {
            "official_config_changed": False,
            "ctp_connected": False,
            "order_api_called": False,
            "stage757_account_capital": s759.s748.CAPITAL_500K,
            "stage757_base_risk_multiplier": 0.40,
            "stage757_restored_risk_multiplier": 0.80,
            "streak_risk_multipliers": "1.0,1.0,1.0,1.0",
            "enable_recovery_sleeve": False,
            "enable_oi_price_confirm_risk_restore": True,
            "causal_timing": "latest_completed_daily_bar",
        },
        "checks": checks.to_dict("records"),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "cost": str(COST_PATH),
            "curves": str(CURVES_PATH),
            "checks": str(CHECKS_PATH),
            "return_heatmap": str(RETURN_HEATMAP_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }


def _write_report(summary: pd.DataFrame, checks: pd.DataFrame, decision: dict[str, Any]) -> None:
    all_row = checks[checks["bucket"].eq("stage757_all_monthly_starts_to_20260529")].iloc[0]
    mature = checks[checks["bucket"].eq("stage757_mature_ge252_trading_days")].iloc[0]
    lines = [
        "# Stage763 Stage757 月度启动更新至 2026-05-29",
        "",
        "## Scope",
        "",
        "- 只更新 Stage757 月度启动审计终点，不改策略、不改正式配置、不连接 CTP、不调用下单。",
        "- 回测终点：2026-05-29。",
        "",
        "## Key Metrics",
        "",
        f"- 全部启动：{int(all_row['positive_count'])}/{int(all_row['start_count'])} 正收益，"
        f"中位收益 {float(all_row['median_return_pct']):.4f}%，"
        f"最差 {all_row['worst_return_start']}={float(all_row['min_return_pct']):.4f}%，"
        f"DD40失败 {int(all_row['dd40_fail_count'])}/{int(all_row['start_count'])}。",
        f"- 成熟>=252交易日：{int(mature['positive_count'])}/{int(mature['start_count'])} 正收益，"
        f"中位收益 {float(mature['median_return_pct']):.4f}%，"
        f"DD40失败 {int(mature['dd40_fail_count'])}/{int(mature['start_count'])}。",
        "",
        "## Decision",
        "",
        f"- {decision['decision']}",
        f"- hard_fail: {', '.join(decision['hard_fail_checks']) if decision['hard_fail_checks'] else 'none'}",
        "",
        "## Outputs",
        "",
        f"- heatmap: `{RETURN_HEATMAP_PATH}`",
        f"- summary: `{SUMMARY_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _run_candidate_monthly_with_retry() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    metadata = s759.s744.s513._metadata()
    spec = s759.s757._candidate_spec(metadata)
    base_c3_overrides = dict(s759.s749.ORIGINAL_C3_OVERRIDES(MONTH_STARTS[0].to_pydatetime()))
    start_items = [start.strftime("%Y-%m-%d") for start in MONTH_STARTS]

    summary_rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    failed: list[tuple[str, str]] = []

    print(f"[stage763] launching {len(start_items)} Stage757 monthly starts with workers={s759.MAX_WORKERS}", flush=True)
    if s759.MAX_WORKERS == 1:
        iterator = enumerate(start_items, start=1)
        for idx, start_iso in iterator:
            try:
                row, costs, curve = s759._run_candidate_month(start_iso, metadata, spec, base_c3_overrides)
            except Exception as exc:  # noqa: BLE001
                failed.append((start_iso, repr(exc)))
                print(f"[stage763] failed {idx}/{len(start_items)} {start_iso}: {exc!r}", flush=True)
                continue
            summary_rows.append(row)
            cost_rows.extend(costs)
            curve_frames.append(curve)
            print(f"[stage763] completed {idx}/{len(start_items)} {start_iso}", flush=True)
    else:
        with ProcessPoolExecutor(max_workers=s759.MAX_WORKERS) as executor:
            futures = {
                executor.submit(s759._run_candidate_month, start_iso, metadata, spec, base_c3_overrides): start_iso
                for start_iso in start_items
            }
            for idx, future in enumerate(as_completed(futures), start=1):
                start_iso = futures[future]
                try:
                    row, costs, curve = future.result()
                except Exception as exc:  # noqa: BLE001
                    failed.append((start_iso, repr(exc)))
                    print(f"[stage763] failed {idx}/{len(start_items)} {start_iso}: {exc!r}", flush=True)
                    continue
                summary_rows.append(row)
                cost_rows.extend(costs)
                curve_frames.append(curve)
                print(f"[stage763] completed {idx}/{len(start_items)} {start_iso}", flush=True)

    if failed:
        print(f"[stage763] retrying {len(failed)} failed starts serially", flush=True)
    still_failed: list[tuple[str, str]] = []
    completed_months = {str(row.get("start_month", "")) for row in summary_rows}
    for start_iso, _reason in failed:
        start_month = pd.Timestamp(start_iso).strftime("%Y-%m")
        if start_month in completed_months:
            continue
        try:
            row, costs, curve = s759._run_candidate_month(start_iso, metadata, spec, base_c3_overrides)
        except Exception as exc:  # noqa: BLE001
            still_failed.append((start_iso, repr(exc)))
            print(f"[stage763] retry failed {start_iso}: {exc!r}", flush=True)
            continue
        summary_rows.append(row)
        cost_rows.extend(costs)
        curve_frames.append(curve)
        completed_months.add(start_month)
        print(f"[stage763] retry completed {start_iso}", flush=True)

    if still_failed:
        raise RuntimeError(f"Stage763 starts still failed: {still_failed}")

    candidate = s759._add_month_fields(pd.DataFrame(summary_rows)).sort_values("start_month").reset_index(drop=True)
    cost = pd.DataFrame(cost_rows).sort_values(["start_month", "cost_multiplier"]).reset_index(drop=True)
    curves = (
        pd.concat(curve_frames, ignore_index=True, sort=False)
        .sort_values(["start_month", "date"])
        .reset_index(drop=True)
    )
    return candidate, cost, curves


def main() -> None:
    _patch_stage759_globals()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary, cost, curves = _run_candidate_monthly_with_retry()
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    checks = _checks(summary)
    checks.to_csv(CHECKS_PATH, index=False, encoding="utf-8-sig")
    _plot_return_heatmap(summary)
    decision = _decision(summary, checks)
    DECISION_PATH.write_text(s759.json.dumps(s759._json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(summary, checks, decision)

    print("SUMMARY")
    print(summary[["start_month", "rebased_total_return_pct", "rebased_max_dd_pct", "rebased_sharpe"]].tail(12).to_string(index=False))
    print("\nCHECKS")
    print(checks.to_string(index=False))
    print("\nDECISION")
    print(s759.json.dumps(s759._json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
