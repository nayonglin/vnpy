from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage121_stage78_cap55_single25_safety_margin_audit_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage78_cap55_single25_safety_margin_audit"
PROFILE_NAME: str = "stage78_cap55_single25"
CAPITAL: float = 400_000.0
MARGIN_REDLINE_PCT: float = 80.0

STAGE120_FULL_COMPARISON_PATH: Path = (
    OUTPUT_DIR
    / "qmt_roll_stage78_400k_decoupled_margin_surface_full_comparison_"
    "stage120_stage78_400k_decoupled_margin_surface_v1.csv"
)
STAGE120_HORIZON_SUMMARY_PATH: Path = (
    OUTPUT_DIR
    / "qmt_roll_stage78_400k_decoupled_margin_surface_horizon_summary_"
    "stage120_stage78_400k_decoupled_margin_surface_v1.csv"
)
STAGE120_HORIZON_COMPARISON_PATH: Path = (
    OUTPUT_DIR
    / "qmt_roll_stage78_400k_decoupled_margin_surface_horizon_comparison_"
    "stage120_stage78_400k_decoupled_margin_surface_v1.csv"
)

MARGIN_STRESS_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_margin_stress_{MODEL_TAG}.csv"
EQUITY_HAIRCUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_equity_haircut_{MODEL_TAG}.csv"
SLIPPAGE_STRESS_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_slippage_stress_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _to_markdown_table(df: pd.DataFrame, columns: list[str], max_rows: int = 40) -> str:
    if df.empty:
        return "_No rows._"
    view = df.loc[:, [column for column in columns if column in df.columns]].head(max_rows).copy()
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda value: f"{value:.4f}")
    return "\n".join(
        [
            "| " + " | ".join(view.columns) + " |",
            "| " + " | ".join(["---"] * len(view.columns)) + " |",
            *["| " + " | ".join(map(str, row)) + " |" for row in view.to_numpy()],
        ]
    )


def _load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    missing = [
        path
        for path in (
            STAGE120_FULL_COMPARISON_PATH,
            STAGE120_HORIZON_SUMMARY_PATH,
            STAGE120_HORIZON_COMPARISON_PATH,
        )
        if not path.exists()
    ]
    if missing:
        raise FileNotFoundError("missing Stage120 outputs: " + ", ".join(str(path) for path in missing))
    full = pd.read_csv(STAGE120_FULL_COMPARISON_PATH)
    horizon = pd.read_csv(STAGE120_HORIZON_SUMMARY_PATH)
    comparison = pd.read_csv(STAGE120_HORIZON_COMPARISON_PATH)
    return full, horizon, comparison


def _build_margin_stress(horizon_comparison: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    profile = horizon_comparison[horizon_comparison["profile_name"].astype(str).eq(PROFILE_NAME)].copy()
    for _, row in profile.iterrows():
        max_margin = float(row.get("max_margin_to_balance_pct", 0.0) or 0.0)
        for multiplier in (1.001, 1.005, 1.01, 1.03, 1.05, 1.10):
            stressed = max_margin * multiplier
            rows.append(
                {
                    "profile_name": PROFILE_NAME,
                    "horizon": row["horizon"],
                    "base_max_margin_to_balance_pct": max_margin,
                    "margin_multiplier": multiplier,
                    "stressed_max_margin_to_balance_pct": stressed,
                    "breaks_80pct": int(stressed > MARGIN_REDLINE_PCT),
                    "buffer_to_80pct_pp": MARGIN_REDLINE_PCT - max_margin,
                    "relative_margin_buffer_to_80pct_pct": (MARGIN_REDLINE_PCT / max_margin - 1.0) * 100.0
                    if max_margin > 0
                    else np.nan,
                }
            )
    return pd.DataFrame(rows)


def _build_equity_haircut_stress(horizon_comparison: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    profile = horizon_comparison[horizon_comparison["profile_name"].astype(str).eq(PROFILE_NAME)].copy()
    for _, row in profile.iterrows():
        max_margin = float(row.get("max_margin_to_balance_pct", 0.0) or 0.0)
        for haircut in (0.001, 0.005, 0.01, 0.03, 0.05, 0.10):
            stressed = max_margin / max(1.0 - haircut, 1e-9)
            rows.append(
                {
                    "profile_name": PROFILE_NAME,
                    "horizon": row["horizon"],
                    "base_max_margin_to_balance_pct": max_margin,
                    "equity_haircut_pct": haircut * 100.0,
                    "stressed_max_margin_to_balance_pct": stressed,
                    "breaks_80pct": int(stressed > MARGIN_REDLINE_PCT),
                }
            )
    return pd.DataFrame(rows)


def _summarize_slippage_stress(horizon_summary: pd.DataFrame) -> pd.DataFrame:
    profile = horizon_summary[
        horizon_summary["profile_name"].astype(str).eq(PROFILE_NAME)
        & horizon_summary["complete_horizon"].astype(bool)
    ].copy()
    rows: list[dict[str, Any]] = []
    for multiplier in (1.0, 1.5, 2.0, 3.0):
        stressed = profile.copy()
        extra_slippage = (multiplier - 1.0) * pd.to_numeric(stressed["total_slippage"], errors="coerce").fillna(0.0)
        stressed["stressed_total_return_pct"] = (
            pd.to_numeric(stressed["total_return_pct"], errors="coerce").fillna(0.0) - extra_slippage / CAPITAL * 100.0
        )
        aggregate = (
            stressed.groupby("horizon", as_index=False)
            .agg(
                window_count=("window_name", "count"),
                positive_return_count=("stressed_total_return_pct", lambda s: int((s > 0).sum())),
                median_return_pct=("stressed_total_return_pct", "median"),
                worst_return_pct=("stressed_total_return_pct", "min"),
                median_trade_count=("total_trade_count", "median"),
                median_slippage=("total_slippage", "median"),
            )
            .sort_values("horizon")
        )
        aggregate["positive_return_rate_pct"] = aggregate["positive_return_count"] / aggregate["window_count"] * 100.0
        aggregate["slippage_multiplier"] = multiplier
        rows.extend(aggregate.to_dict(orient="records"))
    return pd.DataFrame(rows)


def _build_report(
    full_row: pd.Series,
    margin_stress: pd.DataFrame,
    equity_haircut: pd.DataFrame,
    slippage_stress: pd.DataFrame,
) -> str:
    tight_margin = margin_stress[
        (margin_stress["horizon"].astype(str).eq("63d"))
        & (margin_stress["margin_multiplier"].isin([1.001, 1.005, 1.01]))
    ].copy()
    tight_equity = equity_haircut[
        (equity_haircut["horizon"].astype(str).eq("63d"))
        & (equity_haircut["equity_haircut_pct"].isin([0.1, 0.5, 1.0]))
    ].copy()
    return "\n".join(
        [
            "# Stage121 Stage78 Cap55 Single25 Safety Margin Audit",
            "",
            "## Baseline",
            "",
            f"- Profile: `{PROFILE_NAME}`",
            f"- End balance: `{float(full_row['end_balance']):,.0f}`",
            f"- Total return: `{float(full_row['total_return_pct']):.4f}%`",
            f"- Max drawdown: `{float(full_row['max_dd_percent']):.4f}%`",
            f"- Sharpe: `{float(full_row['sharpe_ratio']):.4f}`",
            f"- Full-window max margin/balance: `{float(full_row['max_margin_to_balance_pct']):.4f}%`",
            "",
            "## Margin Multiplier Stress",
            "",
            _to_markdown_table(
                tight_margin,
                [
                    "horizon",
                    "base_max_margin_to_balance_pct",
                    "margin_multiplier",
                    "stressed_max_margin_to_balance_pct",
                    "breaks_80pct",
                    "buffer_to_80pct_pp",
                    "relative_margin_buffer_to_80pct_pct",
                ],
                max_rows=12,
            ),
            "",
            "## Equity Haircut Stress",
            "",
            _to_markdown_table(
                tight_equity,
                [
                    "horizon",
                    "base_max_margin_to_balance_pct",
                    "equity_haircut_pct",
                    "stressed_max_margin_to_balance_pct",
                    "breaks_80pct",
                ],
                max_rows=12,
            ),
            "",
            "## Slippage Stress",
            "",
            _to_markdown_table(
                slippage_stress,
                [
                    "slippage_multiplier",
                    "horizon",
                    "window_count",
                    "positive_return_rate_pct",
                    "median_return_pct",
                    "worst_return_pct",
                ],
                max_rows=40,
            ),
            "",
            "## Judgement",
            "",
            "- The profile has alpha value, but its quarterly margin buffer is too thin for formal deployment.",
            "- A 0.1% margin multiplier or a 0.1% equity haircut is already enough to break the 80% redline.",
            "- Treat it as a research candidate, not as a strategy version to freeze.",
        ]
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    full, horizon_summary, horizon_comparison = _load_inputs()
    full_profile = full[full["profile_name"].astype(str).eq(PROFILE_NAME)].copy()
    if full_profile.empty:
        raise ValueError(f"missing full row for {PROFILE_NAME}")
    full_row = full_profile.iloc[0]

    margin_stress = _build_margin_stress(horizon_comparison)
    equity_haircut = _build_equity_haircut_stress(horizon_comparison)
    slippage_stress = _summarize_slippage_stress(horizon_summary)

    margin_stress.to_csv(MARGIN_STRESS_PATH, index=False, encoding="utf-8-sig")
    equity_haircut.to_csv(EQUITY_HAIRCUT_PATH, index=False, encoding="utf-8-sig")
    slippage_stress.to_csv(SLIPPAGE_STRESS_PATH, index=False, encoding="utf-8-sig")

    summary = {
        "model_tag": MODEL_TAG,
        "profile_name": PROFILE_NAME,
        "baseline": full_row.to_dict(),
        "min_relative_margin_buffer_to_80pct_pct": float(
            margin_stress["relative_margin_buffer_to_80pct_pct"].min()
        ),
        "breaks_80pct_at_0_1pct_margin_multiplier": bool(
            margin_stress[
                (margin_stress["margin_multiplier"].eq(1.001)) & (margin_stress["breaks_80pct"].eq(1))
            ].shape[0]
        ),
        "breaks_80pct_at_0_1pct_equity_haircut": bool(
            equity_haircut[
                (equity_haircut["equity_haircut_pct"].eq(0.1)) & (equity_haircut["breaks_80pct"].eq(1))
            ].shape[0]
        ),
        "output_paths": {
            "margin_stress": str(MARGIN_STRESS_PATH),
            "equity_haircut": str(EQUITY_HAIRCUT_PATH),
            "slippage_stress": str(SLIPPAGE_STRESS_PATH),
            "report": str(REPORT_PATH),
        },
    }
    SUMMARY_JSON_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(_build_report(full_row, margin_stress, equity_haircut, slippage_stress), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"[stage121-safety-margin] report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
