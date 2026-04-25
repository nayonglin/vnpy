from __future__ import annotations

import json
import math
import sys
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd

from analyze_qmt_roll_stage105_margin_constraint_surface import _to_markdown_table
from qmt_roll_official_stage78_config import (
    OFFICIAL_STAGE78_CAPITAL,
    OFFICIAL_STAGE78_VERSION,
    build_official_stage78_overrides,
    build_official_stage78_paths,
)
from qmt_universe import END_DT, START_DT
from run_qmt_roll_backtest import START_YEAR_WINDOWS, build_summary_row, run_backtest
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage133_ai_pool_update_cadence_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage133_ai_pool_update_cadence"

ELIGIBILITY_PREFIX: str = f"{OUTPUT_PREFIX}_eligibility"
SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
START_YEAR_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_start_year_{MODEL_TAG}.csv"
AGGREGATE_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_start_year_aggregate_{MODEL_TAG}.csv"
ELIGIBILITY_SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_eligibility_summary_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


@dataclass(frozen=True)
class CadenceSpec:
    profile_name: str
    cadence_months: int
    description: str


CADENCE_SPECS: tuple[CadenceSpec, ...] = (
    CadenceSpec("stage78_ai_pool_monthly", 1, "Current Stage78 monthly AI pool update cadence."),
    CadenceSpec("stage133_ai_pool_2m_hold", 2, "Hold every AI product pool signal for about two months."),
    CadenceSpec("stage133_ai_pool_3m_hold", 3, "Hold every AI product pool signal for about one quarter."),
    CadenceSpec("stage133_ai_pool_6m_hold", 6, "Hold every AI product pool signal for about half a year."),
)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or math.isinf(result):
        return default
    return result


def _build_cadence_eligibility(source_path: Path, spec: CadenceSpec) -> tuple[Path, dict[str, Any]]:
    source = pd.read_csv(source_path)
    source["eval_date"] = pd.to_datetime(source["eval_date"]).dt.normalize()
    source.sort_values(["eval_date", "score_rank", "product_vt_symbol"], inplace=True)

    pre_signal = source[source["eval_date"] < pd.Timestamp("2022-01-01")].copy()
    post_signal = source[source["eval_date"] >= pd.Timestamp("2022-01-01")].copy()
    post_dates = sorted(pd.Timestamp(value) for value in post_signal["eval_date"].unique())
    selected_dates = set(post_dates[:: max(1, int(spec.cadence_months))])

    selected = post_signal[post_signal["eval_date"].isin(selected_dates)].copy()
    cadence = pd.concat([pre_signal, selected], ignore_index=True)
    cadence["strategy"] = spec.profile_name
    cadence["eval_date"] = cadence["eval_date"].dt.date.astype(str)
    cadence.sort_values(["eval_date", "score_rank", "product_vt_symbol"], inplace=True)

    output_path = OUTPUT_DIR / f"{ELIGIBILITY_PREFIX}_{spec.profile_name}_{MODEL_TAG}.csv"
    cadence.to_csv(output_path, index=False, encoding="utf-8-sig")

    post_selected_dates = sorted(pd.Timestamp(value) for value in selected["eval_date"].unique())
    summary = {
        "profile_name": spec.profile_name,
        "cadence_months": spec.cadence_months,
        "description": spec.description,
        "eligibility_path": str(output_path),
        "source_eligibility_path": str(source_path),
        "pre_signal_row_count": int(len(pre_signal)),
        "post_signal_row_count": int(len(selected)),
        "source_post_signal_date_count": int(len(post_dates)),
        "selected_post_signal_date_count": int(len(post_selected_dates)),
        "first_post_signal_date": post_selected_dates[0].date().isoformat() if post_selected_dates else "",
        "last_post_signal_date": post_selected_dates[-1].date().isoformat() if post_selected_dates else "",
    }
    return output_path, summary


def _strategy_overrides(eligibility_path: Path, profile_name: str) -> dict[str, Any]:
    overrides = build_official_stage78_overrides()
    overrides["ai_product_pool_eligibility_path"] = str(eligibility_path)
    overrides["ai_product_pool_strategy"] = profile_name
    return overrides


def _run_full(profile_name: str, strategy_overrides: dict[str, Any], spec: CadenceSpec) -> dict[str, Any]:
    print(f"[stage133-ai-pool-cadence] full {profile_name}", flush=True)
    log_buffer = StringIO()
    try:
        with redirect_stdout(log_buffer), redirect_stderr(log_buffer):
            _, _, statistics = run_backtest(
                risk_ratio=BASE_RISK_RATIO,
                strategy_overrides=strategy_overrides,
                analysis_start=START_DT,
                analysis_end=END_DT,
                capital=OFFICIAL_STAGE78_CAPITAL,
                save_artifacts=False,
                include_start_year_sweep=False,
            )
    except Exception:
        sys.stderr.write(log_buffer.getvalue())
        raise

    return build_summary_row(
        statistics,
        analysis_start=START_DT,
        analysis_end=END_DT,
        profile_name=profile_name,
        base_version=OFFICIAL_STAGE78_VERSION,
        cadence_months=spec.cadence_months,
        description=spec.description,
        capital=OFFICIAL_STAGE78_CAPITAL,
    )


def _run_start_year(
    profile_name: str,
    strategy_overrides: dict[str, Any],
    spec: CadenceSpec,
    existing_rows: list[dict[str, Any]],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for window_name, display_label, analysis_start, analysis_end in START_YEAR_WINDOWS:
        print(f"[stage133-ai-pool-cadence] start-year {profile_name} / {window_name}", flush=True)
        log_buffer = StringIO()
        try:
            with redirect_stdout(log_buffer), redirect_stderr(log_buffer):
                _, _, statistics = run_backtest(
                    risk_ratio=BASE_RISK_RATIO,
                    strategy_overrides=strategy_overrides,
                    analysis_start=analysis_start,
                    analysis_end=analysis_end,
                    capital=OFFICIAL_STAGE78_CAPITAL,
                    save_artifacts=False,
                    include_start_year_sweep=False,
                )
        except Exception:
            sys.stderr.write(log_buffer.getvalue())
            raise
        row = build_summary_row(
            statistics,
            analysis_start=analysis_start,
            analysis_end=analysis_end,
            profile_name=profile_name,
            base_version=OFFICIAL_STAGE78_VERSION,
            cadence_months=spec.cadence_months,
            description=spec.description,
            window_name=window_name,
            display_label=display_label,
            capital=OFFICIAL_STAGE78_CAPITAL,
        )
        rows.append(row)
        pd.DataFrame([*existing_rows, *rows]).to_csv(START_YEAR_CSV_PATH, index=False, encoding="utf-8-sig")
    return pd.DataFrame(rows)


def _build_aggregate(start_year: pd.DataFrame, summary: pd.DataFrame) -> pd.DataFrame:
    monthly = start_year[start_year["profile_name"] == "stage78_ai_pool_monthly"].set_index("window_name")
    rows: list[dict[str, Any]] = []
    for profile_name, group in start_year.groupby("profile_name", sort=False):
        profile = group.set_index("window_name")
        joined = profile.join(monthly, lsuffix="", rsuffix="_monthly", how="inner")
        if joined.empty:
            continue
        full_row = summary[summary["profile_name"] == profile_name].iloc[0].to_dict()
        rows.append(
            {
                "profile_name": profile_name,
                "cadence_months": int(full_row["cadence_months"]),
                "full_end_balance": _safe_float(full_row["end_balance"]),
                "full_total_return_pct": _safe_float(full_row["total_return_pct"]),
                "full_max_dd_percent": _safe_float(full_row["max_dd_percent"]),
                "full_sharpe_ratio": _safe_float(full_row["sharpe_ratio"]),
                "full_total_trade_count": int(_safe_float(full_row["total_trade_count"])),
                "full_total_slippage": _safe_float(full_row["total_slippage"]),
                "start_year_positive_rate_pct": float((group["total_return_pct"] > 0).mean() * 100.0),
                "start_year_return_win_rate_vs_monthly_pct": float(
                    (joined["total_return_pct"] > joined["total_return_pct_monthly"]).mean() * 100.0
                ),
                "start_year_sharpe_win_rate_vs_monthly_pct": float(
                    (joined["sharpe_ratio"] > joined["sharpe_ratio_monthly"]).mean() * 100.0
                ),
                "start_year_dd_win_rate_vs_monthly_pct": float(
                    (joined["max_dd_percent"] > joined["max_dd_percent_monthly"]).mean() * 100.0
                ),
                "worst_start_year_return_pct": _safe_float(group["total_return_pct"].min()),
                "worst_start_year_max_dd_percent": _safe_float(group["max_dd_percent"].min()),
                "median_start_year_return_delta_vs_monthly": _safe_float(
                    (joined["total_return_pct"] - joined["total_return_pct_monthly"]).median()
                ),
                "median_start_year_sharpe_delta_vs_monthly": _safe_float(
                    (joined["sharpe_ratio"] - joined["sharpe_ratio_monthly"]).median()
                ),
            }
        )
    return pd.DataFrame(rows).sort_values(["full_end_balance", "full_sharpe_ratio"], ascending=False).reset_index(drop=True)


def _build_report(
    summary: pd.DataFrame,
    aggregate: pd.DataFrame,
    start_year: pd.DataFrame,
    eligibility_summary: pd.DataFrame,
) -> str:
    summary_columns = [
        "profile_name",
        "cadence_months",
        "end_balance",
        "total_return_pct",
        "max_dd_percent",
        "sharpe_ratio",
        "total_slippage",
        "total_trade_count",
        "win_ratio_pct",
    ]
    aggregate_columns = [
        "profile_name",
        "cadence_months",
        "full_end_balance",
        "full_total_return_pct",
        "full_max_dd_percent",
        "full_sharpe_ratio",
        "start_year_return_win_rate_vs_monthly_pct",
        "start_year_sharpe_win_rate_vs_monthly_pct",
        "start_year_dd_win_rate_vs_monthly_pct",
        "worst_start_year_return_pct",
    ]
    eligibility_columns = [
        "profile_name",
        "cadence_months",
        "selected_post_signal_date_count",
        "first_post_signal_date",
        "last_post_signal_date",
    ]
    weak_columns = [
        "profile_name",
        "window_name",
        "end_balance",
        "total_return_pct",
        "max_dd_percent",
        "sharpe_ratio",
        "total_trade_count",
    ]
    weak = start_year[start_year["window_name"].isin(["since_2024", "since_2025", "since_2026"])].copy()
    return "\n".join(
        [
            "# Stage133 AI Product Pool Update Cadence",
            "",
            "## Design",
            "",
            "- Keep Stage78 model scores, Top8+FU satellite, universe, entry logic and risk controls unchanged.",
            "- Only reduce how often the AI pool is refreshed: monthly, 2-month, 3-month and 6-month holds.",
            "- The cadence uses deterministic `eval_date[::N]`, not hand-picked calendar months.",
            "",
            "## Eligibility",
            "",
            _to_markdown_table(eligibility_summary, eligibility_columns, max_rows=20),
            "",
            "## Full Window",
            "",
            _to_markdown_table(summary, summary_columns, max_rows=20),
            "",
            "## Start-Year Aggregate",
            "",
            _to_markdown_table(aggregate, aggregate_columns, max_rows=20),
            "",
            "## Recent Start Windows",
            "",
            _to_markdown_table(weak, weak_columns, max_rows=30),
            "",
        ]
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _, source_eligibility_path = build_official_stage78_paths()

    eligibility_rows: list[dict[str, Any]] = []
    profile_payloads: list[tuple[CadenceSpec, Path, dict[str, Any]]] = []
    for spec in CADENCE_SPECS:
        eligibility_path, eligibility_summary = _build_cadence_eligibility(source_eligibility_path, spec)
        eligibility_rows.append(eligibility_summary)
        profile_payloads.append((spec, eligibility_path, _strategy_overrides(eligibility_path, spec.profile_name)))
    pd.DataFrame(eligibility_rows).to_csv(ELIGIBILITY_SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")

    full_rows: list[dict[str, Any]] = []
    start_year_rows: list[dict[str, Any]] = []
    start_year_frames: list[pd.DataFrame] = []
    for spec, _, overrides in profile_payloads:
        full_rows.append(_run_full(spec.profile_name, overrides, spec))
        pd.DataFrame(full_rows).to_csv(SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
        start_year_df = _run_start_year(spec.profile_name, overrides, spec, start_year_rows)
        start_year_frames.append(start_year_df)
        start_year_rows.extend(start_year_df.to_dict(orient="records"))

    summary = pd.DataFrame(full_rows).sort_values(["end_balance", "sharpe_ratio"], ascending=False).reset_index(drop=True)
    start_year = pd.concat(start_year_frames, ignore_index=True).sort_values(
        ["profile_name", "analysis_start"]
    ).reset_index(drop=True)
    aggregate = _build_aggregate(start_year, summary)
    eligibility_summary = pd.DataFrame(eligibility_rows)

    summary.to_csv(SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    start_year.to_csv(START_YEAR_CSV_PATH, index=False, encoding="utf-8-sig")
    aggregate.to_csv(AGGREGATE_CSV_PATH, index=False, encoding="utf-8-sig")
    eligibility_summary.to_csv(ELIGIBILITY_SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")

    payload = {
        "model_tag": MODEL_TAG,
        "base_version": OFFICIAL_STAGE78_VERSION,
        "capital": OFFICIAL_STAGE78_CAPITAL,
        "source_eligibility_path": str(source_eligibility_path),
        "cadence_specs": [spec.__dict__ for spec in CADENCE_SPECS],
        "eligibility_summary": eligibility_summary.to_dict(orient="records"),
        "summary": summary.to_dict(orient="records"),
        "start_year": start_year.to_dict(orient="records"),
        "aggregate": aggregate.to_dict(orient="records"),
        "outputs": {
            "summary": str(SUMMARY_CSV_PATH),
            "start_year": str(START_YEAR_CSV_PATH),
            "aggregate": str(AGGREGATE_CSV_PATH),
            "eligibility_summary": str(ELIGIBILITY_SUMMARY_CSV_PATH),
            "report": str(REPORT_PATH),
        },
    }
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(_build_report(summary, aggregate, start_year, eligibility_summary), encoding="utf-8")

    print(f"[stage133-ai-pool-cadence] summary: {SUMMARY_CSV_PATH}")
    print(f"[stage133-ai-pool-cadence] start-year: {START_YEAR_CSV_PATH}")
    print(f"[stage133-ai-pool-cadence] aggregate: {AGGREGATE_CSV_PATH}")
    print(f"[stage133-ai-pool-cadence] report: {REPORT_PATH}")
    print(summary.to_string(index=False))
    print(aggregate.to_string(index=False))


if __name__ == "__main__":
    main()
