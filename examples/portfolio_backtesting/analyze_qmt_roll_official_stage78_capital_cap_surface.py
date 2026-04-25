from __future__ import annotations

import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd

from qmt_roll_official_stage78_config import (
    OFFICIAL_STAGE78_ROLE,
    OFFICIAL_STAGE78_VERSION,
    build_official_stage78_overrides,
)
from run_qmt_roll_backtest import build_summary_row, run_backtest
from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import CYCLE_WINDOWS
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage78_capital_cap_surface_v1"
OUTPUT_PREFIX: str = "qmt_roll_official_stage78_capital_cap_surface"

SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COMPARISON_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

CAPITAL_LEVELS: tuple[float, ...] = (200_000.0, 400_000.0)
CAP_MULTIPLIERS: tuple[float, ...] = (2.5, 5.0, 7.5, 10.0, 0.0)
WINDOW_NAMES: tuple[str, ...] = ("full_2020_2026", "post_signal_2022_2026", "latest_2026")
FORMAL_FIXED_CAP: float = 1_000_000.0


def _safe_float(value: Any) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def cap_label(multiplier: float) -> str:
    if multiplier <= 0:
        return "cap_off"
    text = f"{multiplier:g}".replace(".", "_")
    return f"cap_{text}x"


def sizing_cap(capital: float, multiplier: float) -> float:
    if multiplier <= 0:
        return 0.0
    return float(capital) * float(multiplier)


def target_windows() -> tuple[dict[str, Any], ...]:
    by_name = {str(window["window_name"]): window for window in CYCLE_WINDOWS}
    return tuple(by_name[name] for name in WINDOW_NAMES)


def build_profiles(capital: float) -> tuple[dict[str, Any], ...]:
    profiles: list[dict[str, Any]] = []
    official_overrides = build_official_stage78_overrides()
    for multiplier in CAP_MULTIPLIERS:
        cap = sizing_cap(capital, multiplier)
        label = cap_label(multiplier)
        profiles.append(
            {
                "profile_name": f"capital_{int(capital / 10_000)}w_{label}",
                "cap_multiplier": multiplier,
                "sizing_equity_cap": cap,
                "strategy_overrides": {
                    **official_overrides,
                    "sizing_equity_cap": cap,
                },
            }
        )
    return tuple(profiles)


def run_surface() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for capital in CAPITAL_LEVELS:
        for window in target_windows():
            window_name = str(window["window_name"])
            display_label = str(window["display_label"])
            analysis_start: datetime = window["analysis_start"]
            analysis_end: datetime = window["analysis_end"]
            for profile in build_profiles(capital):
                profile_name = str(profile["profile_name"])
                strategy_overrides = dict(profile["strategy_overrides"])
                print(
                    f"[stage78-capital-cap-surface] {window_name} / {profile_name}: "
                    f"capital={capital:,.0f}, cap={float(profile['sizing_equity_cap']):,.0f}, "
                    f"{analysis_start.date()} -> {analysis_end.date()}"
                )
                log_buffer = StringIO()
                try:
                    with redirect_stdout(log_buffer), redirect_stderr(log_buffer):
                        _, _, statistics = run_backtest(
                            risk_ratio=BASE_RISK_RATIO,
                            strategy_overrides=strategy_overrides,
                            analysis_start=analysis_start,
                            analysis_end=analysis_end,
                            capital=capital,
                            save_artifacts=False,
                            include_start_year_sweep=False,
                        )
                except Exception:
                    sys.stderr.write(log_buffer.getvalue())
                    raise
                rows.append(
                    build_summary_row(
                        statistics,
                        analysis_start=analysis_start,
                        analysis_end=analysis_end,
                        official_version=OFFICIAL_STAGE78_VERSION,
                        official_role=OFFICIAL_STAGE78_ROLE,
                        window_name=window_name,
                        display_label=display_label,
                        profile_name=profile_name,
                        capital=capital,
                        cap_multiplier=float(profile["cap_multiplier"]),
                        sizing_equity_cap=float(profile["sizing_equity_cap"]),
                        strategy_overrides_json=json.dumps(
                            strategy_overrides,
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                        total_net_pnl=float(statistics.get("total_net_pnl", 0) or 0),
                        total_slippage=float(statistics.get("total_slippage", 0) or 0),
                        total_commission=float(statistics.get("total_commission", 0) or 0),
                        profit_days=int(statistics.get("profit_days", 0) or 0),
                        loss_days=int(statistics.get("loss_days", 0) or 0),
                    )
                )
    return pd.DataFrame(rows).sort_values(["capital", "analysis_start", "cap_multiplier"]).reset_index(drop=True)


def reference_multiplier_for_capital(capital: float) -> float:
    return FORMAL_FIXED_CAP / float(capital)


def build_comparison(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (capital, window_name), group in summary.groupby(["capital", "window_name"], sort=False):
        reference_multiplier = reference_multiplier_for_capital(float(capital))
        reference_rows = group[(group["cap_multiplier"] - reference_multiplier).abs() < 1e-9]
        if reference_rows.empty:
            continue
        reference = reference_rows.iloc[0]
        for _, candidate in group.iterrows():
            rows.append(
                {
                    "capital": float(capital),
                    "window_name": window_name,
                    "reference_cap_multiplier": reference_multiplier,
                    "reference_sizing_equity_cap": _safe_float(reference["sizing_equity_cap"]),
                    "candidate_profile_name": str(candidate["profile_name"]),
                    "candidate_cap_multiplier": _safe_float(candidate["cap_multiplier"]),
                    "candidate_sizing_equity_cap": _safe_float(candidate["sizing_equity_cap"]),
                    "reference_end_balance": _safe_float(reference["end_balance"]),
                    "candidate_end_balance": _safe_float(candidate["end_balance"]),
                    "end_balance_diff": _safe_float(candidate["end_balance"]) - _safe_float(reference["end_balance"]),
                    "reference_total_return_pct": _safe_float(reference["total_return_pct"]),
                    "candidate_total_return_pct": _safe_float(candidate["total_return_pct"]),
                    "total_return_pct_diff": _safe_float(candidate["total_return_pct"])
                    - _safe_float(reference["total_return_pct"]),
                    "reference_max_dd_percent": _safe_float(reference["max_dd_percent"]),
                    "candidate_max_dd_percent": _safe_float(candidate["max_dd_percent"]),
                    "max_dd_percent_diff": _safe_float(candidate["max_dd_percent"])
                    - _safe_float(reference["max_dd_percent"]),
                    "reference_sharpe": _safe_float(reference["sharpe_ratio"]),
                    "candidate_sharpe": _safe_float(candidate["sharpe_ratio"]),
                    "sharpe_diff": _safe_float(candidate["sharpe_ratio"]) - _safe_float(reference["sharpe_ratio"]),
                    "reference_total_slippage": _safe_float(reference["total_slippage"]),
                    "candidate_total_slippage": _safe_float(candidate["total_slippage"]),
                    "total_slippage_diff": _safe_float(candidate["total_slippage"])
                    - _safe_float(reference["total_slippage"]),
                    "reference_trade_count": int(_safe_float(reference["total_trade_count"])),
                    "candidate_trade_count": int(_safe_float(candidate["total_trade_count"])),
                    "trade_count_diff": int(
                        _safe_float(candidate["total_trade_count"]) - _safe_float(reference["total_trade_count"])
                    ),
                }
            )
    return pd.DataFrame(rows)


def to_markdown_table(df: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 40) -> str:
    if df.empty:
        return "_empty_"
    view = df[columns].copy() if columns else df.copy()
    view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda value: f"{value:.4f}")
    header = "| " + " | ".join(view.columns) + " |"
    separator = "| " + " | ".join(["---"] * len(view.columns)) + " |"
    rows = ["| " + " | ".join(map(str, row)) + " |" for row in view.to_numpy()]
    return "\n".join([header, separator, *rows])


def build_report(summary: pd.DataFrame, comparison: pd.DataFrame) -> str:
    full = summary[summary["window_name"].astype(str) == "full_2020_2026"].copy()
    post = summary[summary["window_name"].astype(str) == "post_signal_2022_2026"].copy()
    latest = summary[summary["window_name"].astype(str) == "latest_2026"].copy()
    material_comparison = comparison[
        comparison["candidate_cap_multiplier"].isin([2.5, 5.0, 7.5, 10.0, 0.0])
    ].copy()
    return "\n".join(
        [
            f"# {OFFICIAL_STAGE78_VERSION} Capital Cap Surface",
            "",
            "## Purpose",
            "",
            "- Test whether the fixed 1,000,000 sizing-equity cap should become a capital multiple.",
            "- This is a low-dimensional structure test, not a parameter optimization.",
            "",
            "## Parameters",
            "",
            f"- Base risk ratio: `{BASE_RISK_RATIO}`",
            f"- Capital levels: `{', '.join(f'{value:,.0f}' for value in CAPITAL_LEVELS)}`",
            f"- Cap multipliers: `{', '.join(cap_label(value) for value in CAP_MULTIPLIERS)}`",
            f"- Windows: `{', '.join(WINDOW_NAMES)}`",
            "- Reference inside each capital level is the old fixed 1,000,000 cap equivalent.",
            "",
            "## Full Cycle",
            "",
            to_markdown_table(
                full[
                    [
                        "capital",
                        "profile_name",
                        "sizing_equity_cap",
                        "end_balance",
                        "total_return_pct",
                        "max_dd_percent",
                        "sharpe_ratio",
                        "total_slippage",
                        "total_trade_count",
                    ]
                ]
            ),
            "",
            "## Post Signal",
            "",
            to_markdown_table(
                post[
                    [
                        "capital",
                        "profile_name",
                        "sizing_equity_cap",
                        "end_balance",
                        "total_return_pct",
                        "max_dd_percent",
                        "sharpe_ratio",
                        "total_slippage",
                        "total_trade_count",
                    ]
                ]
            ),
            "",
            "## Latest 2026",
            "",
            to_markdown_table(
                latest[
                    [
                        "capital",
                        "profile_name",
                        "sizing_equity_cap",
                        "end_balance",
                        "total_return_pct",
                        "max_dd_percent",
                        "sharpe_ratio",
                        "total_slippage",
                        "total_trade_count",
                    ]
                ]
            ),
            "",
            "## Diff Versus Fixed 1m Equivalent",
            "",
            to_markdown_table(
                material_comparison[
                    [
                        "capital",
                        "window_name",
                        "candidate_profile_name",
                        "end_balance_diff",
                        "total_return_pct_diff",
                        "max_dd_percent_diff",
                        "sharpe_diff",
                        "total_slippage_diff",
                        "trade_count_diff",
                    ]
                ],
                max_rows=60,
            ),
            "",
            "## Judgement Rules",
            "",
            "- If higher cap improves only full-cycle equity but hurts Sharpe or latest tail, it is leverage expansion, not edge.",
            "- If 400,000 capital works materially better at 5x than 2.5x without tail deterioration, fixed 1m should be questioned.",
            "- A promotion still requires quarterly walk-forward on the best candidate; this surface only finds whether a candidate deserves that test.",
        ]
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = run_surface()
    comparison = build_comparison(summary)
    summary.to_csv(SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_CSV_PATH, index=False, encoding="utf-8-sig")
    payload = {
        "model_tag": MODEL_TAG,
        "official_version": OFFICIAL_STAGE78_VERSION,
        "official_role": OFFICIAL_STAGE78_ROLE,
        "base_risk_ratio": BASE_RISK_RATIO,
        "capital_levels": list(CAPITAL_LEVELS),
        "cap_multipliers": list(CAP_MULTIPLIERS),
        "formal_fixed_cap": FORMAL_FIXED_CAP,
        "windows": list(WINDOW_NAMES),
        "summary": summary.to_dict(orient="records"),
        "comparison": comparison.to_dict(orient="records"),
        "outputs": {
            "summary_csv": str(SUMMARY_CSV_PATH),
            "comparison_csv": str(COMPARISON_CSV_PATH),
            "summary_json": str(SUMMARY_JSON_PATH),
            "report": str(REPORT_PATH),
        },
    }
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(build_report(summary, comparison), encoding="utf-8")
    print(summary.to_string(index=False))
    print(f"[stage78-capital-cap-surface] comparison: {COMPARISON_CSV_PATH}")
    print(f"[stage78-capital-cap-surface] report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
