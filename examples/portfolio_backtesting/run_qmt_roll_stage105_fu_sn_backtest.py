from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from qmt_roll_stage105_fu_sn_config import (
    STAGE105_CAPITAL,
    STAGE105_EXPERIMENT_TAG,
    STAGE105_FORMAL_PREFIX,
    STAGE105_REFERENCE_METRICS,
    STAGE105_RESEARCH_SWITCH_POLICY,
    STAGE105_ROBUSTNESS_EVIDENCE,
    STAGE105_ROLE,
    STAGE105_VERSION,
    build_stage105_manifest,
    build_stage105_overrides,
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

MANIFEST_PATH: Path = OUTPUT_DIR / f"{STAGE105_EXPERIMENT_TAG}_manifest.json"
MANIFEST_REPORT_PATH: Path = OUTPUT_DIR / f"{STAGE105_EXPERIMENT_TAG}_manifest.md"
SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{STAGE105_EXPERIMENT_TAG}_summary.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{STAGE105_EXPERIMENT_TAG}_summary.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{STAGE105_EXPERIMENT_TAG}_report.md"


def _safe_float(value: Any) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def build_manifest_report(manifest: dict[str, Any]) -> str:
    full = manifest["reference_metrics"]["full_2020_2026"]
    latest = manifest["reference_metrics"]["latest_2026"]
    policy = manifest["research_switch_policy"]
    evidence = manifest["robustness_evidence"]
    return "\n".join(
        [
            f"# {STAGE105_VERSION}",
            "",
            "## Role",
            "",
            f"- Role: `{manifest['role']}`",
            f"- Base version: `{manifest['base_version']}`",
            f"- Profile: `{manifest['profile_name']}`",
            f"- Base risk ratio: `{manifest['base_risk_ratio']}`",
            f"- Product universe: `{manifest['product_universe_csv_path']}`",
            f"- AI eligibility: `{manifest['ai_product_pool_eligibility_path']}`",
            f"- Satellite products: `{', '.join(manifest['satellite_products'])}`",
            "",
            "## Reference Metrics",
            "",
            (
                f"- Full cycle: end balance `{full['end_balance']:,.0f}`, "
                f"return `{full['total_return_pct']:.4f}%`, "
                f"max drawdown `{full['max_dd_percent']:.4f}%`, "
                f"Sharpe `{full['sharpe_ratio']:.4f}`, "
                f"slippage `{full['total_slippage']:,.0f}`, "
                f"trades `{full['total_trade_count']:,.0f}`."
            ),
            (
                f"- Latest 2026: end balance `{latest['end_balance']:,.0f}`, "
                f"return `{latest['total_return_pct']:.4f}%`, "
                f"max drawdown `{latest['max_dd_percent']:.4f}%`, "
                f"Sharpe `{latest['sharpe_ratio']:.4f}`, "
                f"slippage `{latest['total_slippage']:,.0f}`, "
                f"trades `{latest['total_trade_count']:,.0f}`."
            ),
            "",
            "## Robustness Evidence",
            "",
            f"- `sn` net pnl: `{evidence['sn_total_net_pnl']:,.0f}`",
            f"- `sn` trades: `{evidence['sn_total_trade_count']:,.0f}`",
            f"- `sn` negative years: `{evidence['sn_negative_years']}`",
            f"- Fair slippage 5x end-balance diff vs Stage78: `{evidence['fair_slippage_5x_end_balance_diff_vs_stage78']:,.0f}`",
            f"- Start-year positive diff count: `{evidence['start_year_end_balance_diff_positive_count']}/{evidence['start_year_window_count']}`",
            "",
            "## Research Switch Policy",
            "",
            f"- Default for independent new research: `{policy['default_for_new_independent_research']}`",
            f"- Use when: {policy['use_when']}",
            f"- Do not use when: {policy['do_not_use_when']}",
            f"- Comparison rule: {policy['comparison_rule']}",
        ]
    )


def write_manifest() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = build_stage105_manifest()
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    MANIFEST_REPORT_PATH.write_text(build_manifest_report(manifest), encoding="utf-8")
    return manifest


def run_stage105_backtests(*, run_cycles: bool) -> pd.DataFrame:
    strategy_overrides = build_stage105_overrides()
    windows: tuple[dict[str, Any], ...]
    if run_cycles:
        windows = CYCLE_WINDOWS
    else:
        windows = (
            {
                "window_name": "full_2020_2026",
                "display_label": "full",
                "analysis_start": START_DT,
                "analysis_end": END_DT,
            },
        )

    rows: list[dict[str, Any]] = []
    for window in windows:
        window_name = str(window["window_name"])
        analysis_start = window["analysis_start"]
        analysis_end = window["analysis_end"]
        save_artifacts = window_name == "full_2020_2026"
        print(f"[stage105-fu-sn] {window_name}: {analysis_start.date()} -> {analysis_end.date()}")
        _, _, statistics = run_backtest(
            risk_ratio=BASE_RISK_RATIO,
            strategy_overrides=strategy_overrides,
            analysis_start=analysis_start,
            analysis_end=analysis_end,
            capital=STAGE105_CAPITAL,
            save_artifacts=save_artifacts,
            include_start_year_sweep=False,
            file_prefix=STAGE105_FORMAL_PREFIX if save_artifacts else None,
            chart_title="QMT Roll Stage105 Fu/Sn Successor Candidate" if save_artifacts else None,
        )
        rows.append(
            build_summary_row(
                statistics,
                analysis_start=analysis_start,
                analysis_end=analysis_end,
                official_version=STAGE105_VERSION,
                official_role=STAGE105_ROLE,
                window_name=window_name,
                display_label=str(window["display_label"]),
                strategy_overrides_json=json.dumps(strategy_overrides, ensure_ascii=False, sort_keys=True),
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
        "version": STAGE105_VERSION,
        "role": STAGE105_ROLE,
        "run_cycles": run_cycles,
        "reference_metrics": STAGE105_REFERENCE_METRICS,
        "robustness_evidence": STAGE105_ROBUSTNESS_EVIDENCE,
        "research_switch_policy": STAGE105_RESEARCH_SWITCH_POLICY,
        "experiments": summary.to_dict(orient="records"),
    }
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(build_backtest_report(summary, payload), encoding="utf-8")
    return summary


def build_backtest_report(summary: pd.DataFrame, payload: dict[str, Any]) -> str:
    full = summary[summary["window_name"].astype(str) == "full_2020_2026"].copy()
    lines = [
        f"# {STAGE105_VERSION} Backtest",
        "",
        f"- Role: `{STAGE105_ROLE}`",
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
        reference = STAGE105_REFERENCE_METRICS["full_2020_2026"]
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
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run or inspect the Stage105 fu/sn successor candidate profile.")
    parser.add_argument("--manifest-only", action="store_true", help="Only write the Stage105 candidate manifest.")
    parser.add_argument("--cycles", action="store_true", help="Run all cycle windows instead of only full cycle.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = write_manifest()
    print(f"[stage105-fu-sn] manifest: {MANIFEST_PATH}")
    print(f"[stage105-fu-sn] manifest report: {MANIFEST_REPORT_PATH}")
    if args.manifest_only:
        print(json.dumps({"version": manifest["version"], "role": manifest["role"]}, ensure_ascii=False, indent=2))
        return
    summary = run_stage105_backtests(run_cycles=bool(args.cycles))
    print(f"[stage105-fu-sn] summary csv: {SUMMARY_CSV_PATH}")
    print(f"[stage105-fu-sn] summary json: {SUMMARY_JSON_PATH}")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
