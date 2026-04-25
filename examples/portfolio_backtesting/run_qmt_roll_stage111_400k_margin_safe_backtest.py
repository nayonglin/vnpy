from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from qmt_roll_stage111_400k_margin_safe_config import (
    STAGE111_CAPITAL,
    STAGE111_EXPERIMENT_TAG,
    STAGE111_FORMAL_PREFIX,
    STAGE111_QUARTERLY_VALIDATION,
    STAGE111_REFERENCE_METRICS,
    STAGE111_REJECTED_ALTERNATIVES,
    STAGE111_RESEARCH_SWITCH_POLICY,
    STAGE111_ROLE,
    STAGE111_VERSION,
    build_stage111_manifest,
    build_stage111_overrides,
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

MANIFEST_PATH: Path = OUTPUT_DIR / f"{STAGE111_EXPERIMENT_TAG}_manifest.json"
MANIFEST_REPORT_PATH: Path = OUTPUT_DIR / f"{STAGE111_EXPERIMENT_TAG}_manifest.md"
SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{STAGE111_EXPERIMENT_TAG}_summary.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{STAGE111_EXPERIMENT_TAG}_summary.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{STAGE111_EXPERIMENT_TAG}_report.md"


def _safe_float(value: Any) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def build_manifest_report(manifest: dict[str, Any]) -> str:
    full = manifest["reference_metrics"]["full_2020_2026_400k"]
    policy = manifest["research_switch_policy"]
    return "\n".join(
        [
            f"# {STAGE111_VERSION}",
            "",
            "## Role",
            "",
            f"- Role: `{manifest['role']}`",
            f"- Base version: `{manifest['base_version']}`",
            f"- Profile: `{manifest['profile_name']}`",
            f"- Capital: `{manifest['capital']:,.0f}`",
            f"- Base risk ratio: `{manifest['base_risk_ratio']}`",
            f"- Margin profile: `{manifest['margin_profile']}`",
            f"- Product universe: `{manifest['product_universe_csv_path']}`",
            f"- AI eligibility: `{manifest['ai_product_pool_eligibility_path']}`",
            "",
            "## Reference Metrics",
            "",
            (
                f"- Full cycle 400k: end balance `{full['end_balance']:,.0f}`, "
                f"return `{full['total_return_pct']:.4f}%`, "
                f"max drawdown `{full['max_dd_percent']:.4f}%`, "
                f"Sharpe `{full['sharpe_ratio']:.4f}`, "
                f"slippage `{full['total_slippage']:,.0f}`, "
                f"trades `{full['total_trade_count']:,.0f}`, "
                f"max margin / balance `{full['max_total_margin_to_balance_pct']:.4f}%`."
            ),
            "",
            "## Quarterly Validation",
            "",
            json.dumps(manifest["quarterly_validation"], ensure_ascii=False, indent=2),
            "",
            "## Rejected Alternatives",
            "",
            json.dumps(manifest["rejected_alternatives"], ensure_ascii=False, indent=2),
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
    manifest = build_stage111_manifest()
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    MANIFEST_REPORT_PATH.write_text(build_manifest_report(manifest), encoding="utf-8")
    return manifest


def run_stage111_backtests(*, run_cycles: bool) -> pd.DataFrame:
    strategy_overrides = build_stage111_overrides()
    windows: tuple[dict[str, Any], ...]
    if run_cycles:
        windows = CYCLE_WINDOWS
    else:
        windows = (
            {
                "window_name": "full_2020_2026_400k",
                "display_label": "full_400k",
                "analysis_start": START_DT,
                "analysis_end": END_DT,
            },
        )

    rows: list[dict[str, Any]] = []
    for window in windows:
        window_name = str(window["window_name"])
        analysis_start = window["analysis_start"]
        analysis_end = window["analysis_end"]
        save_artifacts = window_name == "full_2020_2026_400k"
        print(f"[stage111-400k-margin-safe] {window_name}: {analysis_start.date()} -> {analysis_end.date()}")
        _, _, statistics = run_backtest(
            risk_ratio=BASE_RISK_RATIO,
            strategy_overrides=strategy_overrides,
            analysis_start=analysis_start,
            analysis_end=analysis_end,
            capital=STAGE111_CAPITAL,
            save_artifacts=save_artifacts,
            include_start_year_sweep=False,
            file_prefix=STAGE111_FORMAL_PREFIX if save_artifacts else f"{STAGE111_FORMAL_PREFIX}_{window_name}",
            chart_title="QMT Roll Stage111 400k Margin Safe Candidate" if save_artifacts else None,
        )
        rows.append(
            build_summary_row(
                statistics,
                analysis_start=analysis_start,
                analysis_end=analysis_end,
                official_version=STAGE111_VERSION,
                official_role=STAGE111_ROLE,
                window_name=window_name,
                display_label=str(window["display_label"]),
                strategy_overrides_json=json.dumps(strategy_overrides, ensure_ascii=False, sort_keys=True),
                capital=STAGE111_CAPITAL,
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
        "version": STAGE111_VERSION,
        "role": STAGE111_ROLE,
        "capital": STAGE111_CAPITAL,
        "run_cycles": run_cycles,
        "reference_metrics": STAGE111_REFERENCE_METRICS,
        "quarterly_validation": STAGE111_QUARTERLY_VALIDATION,
        "rejected_alternatives": STAGE111_REJECTED_ALTERNATIVES,
        "research_switch_policy": STAGE111_RESEARCH_SWITCH_POLICY,
        "experiments": summary.to_dict(orient="records"),
    }
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(build_backtest_report(summary, payload), encoding="utf-8")
    return summary


def build_backtest_report(summary: pd.DataFrame, payload: dict[str, Any]) -> str:
    full = summary[summary["window_name"].astype(str) == "full_2020_2026_400k"].copy()
    lines = [
        f"# {STAGE111_VERSION} Backtest",
        "",
        f"- Role: `{STAGE111_ROLE}`",
        f"- Capital: `{STAGE111_CAPITAL:,.0f}`",
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
        reference = STAGE111_REFERENCE_METRICS["full_2020_2026_400k"]
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
            "- Stage111 is the current best 400k deployment candidate from the Stage105 family.",
            "- It gives up raw Stage105 return to control quarterly cold-start margin risk.",
            "- It should stay opt-in for deployment research, not the default for independent alpha discovery.",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Stage111 400k margin-safe candidate backtest.")
    parser.add_argument("--cycles", action="store_true", help="Run predefined cycle windows in addition to full window.")
    args = parser.parse_args()
    manifest = write_manifest()
    summary = run_stage111_backtests(run_cycles=args.cycles)
    print(json.dumps({"manifest": manifest, "summary": summary.to_dict(orient="records")}, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
