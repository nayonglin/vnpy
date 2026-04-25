from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from qmt_roll_stage115_200k_granularity_safe_config import (
    STAGE115_CAPITAL,
    STAGE115_EXPERIMENT_TAG,
    STAGE115_FORMAL_PREFIX,
    STAGE115_PROFILE_NAME,
    STAGE115_QUARTERLY_VALIDATION,
    STAGE115_REFERENCE_METRICS,
    STAGE115_REJECTED_BASELINE,
    STAGE115_RESEARCH_SWITCH_POLICY,
    STAGE115_ROLE,
    STAGE115_SINGLE_CONTRACT_MARGIN_LIMIT_PCT,
    STAGE115_VERSION,
    build_stage115_manifest,
    build_stage115_overrides,
)
from qmt_universe import END_DT, START_DT
from run_qmt_roll_backtest import build_summary_row, run_backtest
from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import (
    CYCLE_WINDOWS,
    to_markdown_table,
)
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MANIFEST_PATH: Path = OUTPUT_DIR / f"{STAGE115_EXPERIMENT_TAG}_manifest.json"
MANIFEST_REPORT_PATH: Path = OUTPUT_DIR / f"{STAGE115_EXPERIMENT_TAG}_manifest.md"
SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{STAGE115_EXPERIMENT_TAG}_summary.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{STAGE115_EXPERIMENT_TAG}_summary.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{STAGE115_EXPERIMENT_TAG}_report.md"


def _safe_float(value: Any) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def build_manifest_report(manifest: dict[str, Any]) -> str:
    full = manifest["reference_metrics"]["full_2020_2026_200k"]
    policy = manifest["research_switch_policy"]
    return "\n".join(
        [
            f"# {STAGE115_VERSION}",
            "",
            "## Role",
            "",
            f"- Role: `{manifest['role']}`",
            f"- Base version: `{manifest['base_version']}`",
            f"- Profile: `{manifest['profile_name']}`",
            f"- Capital: `{manifest['capital']:,.0f}`",
            f"- Base risk ratio: `{manifest['base_risk_ratio']}`",
            f"- Single-contract margin limit: `{manifest['single_contract_margin_limit_pct']:.2f}%`",
            f"- Product universe: `{manifest['product_universe_csv_path']}`",
            "",
            "## Reference Metrics",
            "",
            (
                f"- Full cycle 200k: end balance `{full['end_balance']:,.0f}`, "
                f"return `{full['total_return_pct']:.4f}%`, "
                f"max drawdown `{full['max_dd_percent']:.4f}%`, "
                f"Sharpe `{full['sharpe_ratio']:.4f}`, "
                f"slippage `{full['total_slippage']:,.0f}`, "
                f"trades `{full['total_trade_count']:,.0f}`, "
                f"win rate `{full['win_ratio_pct']:.4f}%`, "
                f"max margin / balance `{full['max_margin_to_balance_pct']:.4f}%`."
            ),
            "",
            "## Quarterly Validation",
            "",
            json.dumps(manifest["quarterly_validation"], ensure_ascii=False, indent=2),
            "",
            "## Rejected Baseline",
            "",
            json.dumps(manifest["rejected_baseline"], ensure_ascii=False, indent=2),
            "",
            "## Research Switch Policy",
            "",
            f"- Default for independent new research: `{policy['default_for_new_independent_research']}`",
            f"- Use when: {policy['use_when']}",
            f"- Do not use when: {policy['do_not_use_when']}",
            f"- Comparison rule: {policy['comparison_rule']}",
            "",
            "## Promotion Boundary",
            "",
            json.dumps(manifest["promotion_boundary"], ensure_ascii=False, indent=2),
        ]
    )


def write_manifest() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = build_stage115_manifest()
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    MANIFEST_REPORT_PATH.write_text(build_manifest_report(manifest), encoding="utf-8")
    return manifest


def run_stage115_backtests(*, run_cycles: bool) -> pd.DataFrame:
    strategy_overrides = build_stage115_overrides()
    windows: tuple[dict[str, Any], ...]
    if run_cycles:
        windows = CYCLE_WINDOWS
    else:
        windows = (
            {
                "window_name": "full_2020_2026_200k",
                "display_label": "full_200k",
                "analysis_start": START_DT,
                "analysis_end": END_DT,
            },
        )

    rows: list[dict[str, Any]] = []
    for window in windows:
        window_name = str(window["window_name"])
        analysis_start = window["analysis_start"]
        analysis_end = window["analysis_end"]
        save_artifacts = window_name == "full_2020_2026_200k"
        print(f"[stage115-200k-granularity-safe] {window_name}: {analysis_start.date()} -> {analysis_end.date()}")
        _, _, statistics = run_backtest(
            risk_ratio=BASE_RISK_RATIO,
            strategy_overrides=strategy_overrides,
            analysis_start=analysis_start,
            analysis_end=analysis_end,
            capital=STAGE115_CAPITAL,
            save_artifacts=save_artifacts,
            include_start_year_sweep=False,
            file_prefix=STAGE115_FORMAL_PREFIX if save_artifacts else f"{STAGE115_FORMAL_PREFIX}_{window_name}",
            chart_title="QMT Roll Stage115 200k Granularity Safe Candidate" if save_artifacts else None,
        )
        rows.append(
            build_summary_row(
                statistics,
                analysis_start=analysis_start,
                analysis_end=analysis_end,
                official_version=STAGE115_VERSION,
                official_role=STAGE115_ROLE,
                window_name=window_name,
                display_label=str(window["display_label"]),
                strategy_overrides_json=json.dumps(strategy_overrides, ensure_ascii=False, sort_keys=True),
                capital=STAGE115_CAPITAL,
                total_net_pnl=float(statistics.get("total_net_pnl", 0) or 0),
                total_slippage=float(statistics.get("total_slippage", 0) or 0),
                total_commission=float(statistics.get("total_commission", 0) or 0),
                profit_days=int(statistics.get("profit_days", 0) or 0),
                loss_days=int(statistics.get("loss_days", 0) or 0),
            )
        )

    summary = pd.DataFrame(rows)
    summary.to_csv(SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    payload = {
        "version": STAGE115_VERSION,
        "role": STAGE115_ROLE,
        "profile_name": STAGE115_PROFILE_NAME,
        "capital": STAGE115_CAPITAL,
        "single_contract_margin_limit_pct": STAGE115_SINGLE_CONTRACT_MARGIN_LIMIT_PCT,
        "run_cycles": run_cycles,
        "reference_metrics": STAGE115_REFERENCE_METRICS,
        "quarterly_validation": STAGE115_QUARTERLY_VALIDATION,
        "rejected_baseline": STAGE115_REJECTED_BASELINE,
        "research_switch_policy": STAGE115_RESEARCH_SWITCH_POLICY,
        "experiments": summary.to_dict(orient="records"),
    }
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(build_backtest_report(summary, payload), encoding="utf-8")
    return summary


def build_backtest_report(summary: pd.DataFrame, payload: dict[str, Any]) -> str:
    full = summary[summary["window_name"].astype(str) == "full_2020_2026_200k"].copy()
    lines = [
        f"# {STAGE115_VERSION} Backtest",
        "",
        f"- Role: `{STAGE115_ROLE}`",
        f"- Profile: `{STAGE115_PROFILE_NAME}`",
        f"- Capital: `{STAGE115_CAPITAL:,.0f}`",
        f"- Single-contract margin limit: `{STAGE115_SINGLE_CONTRACT_MARGIN_LIMIT_PCT:.2f}%`",
        f"- Run cycles: `{payload['run_cycles']}`",
        "",
        "## Results",
        "",
        to_markdown_table(
            summary[
                [
                    "window_name",
                    "end_balance",
                    "total_return_pct",
                    "max_dd_percent",
                    "sharpe_ratio",
                    "total_slippage",
                    "total_trade_count",
                ]
            ]
        ),
    ]
    if not full.empty:
        row = full.iloc[0]
        reference = STAGE115_REFERENCE_METRICS["full_2020_2026_200k"]
        lines.extend(
            [
                "",
                "## Reference Check",
                "",
                f"- End balance diff vs frozen reference: `{_safe_float(row['end_balance']) - reference['end_balance']:,.0f}`",
                f"- Sharpe diff vs frozen reference: `{_safe_float(row['sharpe_ratio']) - reference['sharpe_ratio']:.4f}`",
                f"- Slippage diff vs frozen reference: `{_safe_float(row['total_slippage']) - reference['total_slippage']:,.0f}`",
            ]
        )
    lines.extend(
        [
            "",
            "## Judgement",
            "",
            "- Stage115 is a 200k research candidate, not a formal deployment version.",
            "- It fixes the raw Stage111-200k single-contract granularity blocker by filtering products structurally.",
            "- The remaining weakness is quarterly cold-start hit rate, so future work should improve stability before promotion.",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Stage115 200k granularity-safe candidate backtest.")
    parser.add_argument("--cycles", action="store_true", help="Run predefined cycle windows in addition to full window.")
    args = parser.parse_args()
    manifest = write_manifest()
    summary = run_stage115_backtests(run_cycles=args.cycles)
    print(json.dumps({"manifest": manifest, "summary": summary.to_dict(orient="records")}, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
