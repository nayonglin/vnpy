from __future__ import annotations

import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd

from qmt_roll_official_stage78_config import OFFICIAL_STAGE78_ROLE, OFFICIAL_STAGE78_VERSION
from run_qmt_roll_backtest import build_summary_row, run_backtest
from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import (
    AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME,
    AI_TOP8_ELIGIBILITY_PATH,
    CYCLE_WINDOWS,
    FU_PRODUCT,
    STRUCTURAL_UNIVERSE_PATH,
    load_static_products,
    to_markdown_table,
)
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import (
    BASE_RISK_RATIO,
    CORR20_06_08_FLOOR35_OVERRIDES,
)


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

EXPERIMENT_TAG: str = "qmt_roll_official_stage78_fu_sn_satellite_candidate"
MODEL_TAG: str = "stage78_fu_sn_satellite_candidate_v1"
EXPERIMENT_NAME: str = "stage78_plus_fu_sn_satellite_post_signal_profit_shield"

UNIVERSE_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_universe_{MODEL_TAG}.csv"
ELIGIBILITY_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_eligibility_{MODEL_TAG}.csv"
SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_summary_{MODEL_TAG}.csv"
COMPARISON_CSV_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_comparison_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{EXPERIMENT_TAG}_report_{MODEL_TAG}.md"

STAGE78_REFERENCE_SUMMARY_PATH: Path = (
    OUTPUT_DIR / "qmt_roll_official_stage78_sizing_cap_multicycle_summary_stage78_sizing_cap_multicycle_v1.csv"
)

CAPITAL: float = 200_000.0
SIZING_EQUITY_CAP: float = 1_000_000.0
SN_PRODUCT: str = "sn.SHFE"
SATELLITE_PRODUCTS: tuple[str, ...] = (FU_PRODUCT, SN_PRODUCT)
EXCLUSION_MODE: str = "profit_only"
WINDOW_NAMES: tuple[str, ...] = (
    "full_2020_2026",
    "post_signal_2022_2026",
    "early_ai_2022_2023",
    "trend_rich_2024_2025",
    "latest_2026",
)


def _safe_float(value: Any) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def target_windows() -> tuple[dict[str, Any], ...]:
    by_name = {str(window["window_name"]): window for window in CYCLE_WINDOWS}
    return tuple(by_name[name] for name in WINDOW_NAMES)


def build_static18_plus_fu_sn_universe() -> Path:
    if not STRUCTURAL_UNIVERSE_PATH.exists():
        raise FileNotFoundError(STRUCTURAL_UNIVERSE_PATH)
    df = pd.read_csv(STRUCTURAL_UNIVERSE_PATH)
    df["product_vt_symbol"] = df["product_vt_symbol"].astype(str)
    df["is_static_strategy_product"] = pd.to_numeric(
        df["is_static_strategy_product"],
        errors="coerce",
    ).fillna(0).astype(int)
    selected_products = set(load_static_products()) | set(SATELLITE_PRODUCTS)
    missing = sorted(selected_products - set(df["product_vt_symbol"].astype(str)))
    if missing:
        raise ValueError(f"satellite products missing from structural universe: {missing}")
    universe = df[df["product_vt_symbol"].isin(selected_products)].copy()
    universe.sort_values(["exchange", "product_vt_symbol"], inplace=True)
    universe.to_csv(UNIVERSE_PATH, index=False, encoding="utf-8-sig")
    return UNIVERSE_PATH


def build_fu_sn_satellite_post_signal_eligibility() -> Path:
    if not AI_TOP8_ELIGIBILITY_PATH.exists():
        raise FileNotFoundError(AI_TOP8_ELIGIBILITY_PATH)
    df = pd.read_csv(AI_TOP8_ELIGIBILITY_PATH)
    top8 = df[df["strategy"].astype(str) == "ai_top8_entry_filter"].copy()
    if top8.empty:
        raise ValueError("ai_top8_entry_filter eligibility is empty")

    satellite = top8.copy()
    satellite["strategy"] = AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME
    satellite["score_type"] = "ai_top8_plus_fixed_fu_sn_satellite"
    satellite["top_n"] = 10

    satellite_rows: list[dict[str, Any]] = []
    for eval_date, group in satellite.groupby("eval_date", sort=True):
        products = set(group["product_vt_symbol"].astype(str))
        min_score = pd.to_numeric(group["score"], errors="coerce").min()
        base_score = float(min_score) if pd.notna(min_score) else 0.0
        max_rank = int(pd.to_numeric(group["score_rank"], errors="coerce").fillna(0).max())
        for offset, product in enumerate(SATELLITE_PRODUCTS, start=1):
            if product in products:
                continue
            satellite_rows.append(
                {
                    "strategy": AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME,
                    "score_type": "ai_top8_plus_fixed_fu_sn_satellite",
                    "eval_date": eval_date,
                    "product_vt_symbol": product,
                    "score": base_score - 1e-6 * offset,
                    "score_rank": max_rank + offset,
                    "top_n": 10,
                }
            )

    static_products = load_static_products()
    pre_signal_rows = [
        {
            "strategy": AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME,
            "score_type": "static18_pre_ai_boundary",
            "eval_date": "2019-12-31",
            "product_vt_symbol": product,
            "score": 0.0,
            "score_rank": rank,
            "top_n": len(static_products),
        }
        for rank, product in enumerate(static_products, start=1)
    ]
    if satellite_rows:
        satellite = pd.concat([satellite, pd.DataFrame(satellite_rows)], ignore_index=True)
    satellite = pd.concat([pd.DataFrame(pre_signal_rows), satellite], ignore_index=True)
    satellite.sort_values(["eval_date", "score_rank", "product_vt_symbol"], inplace=True)
    satellite.to_csv(ELIGIBILITY_PATH, index=False, encoding="utf-8-sig")
    return ELIGIBILITY_PATH


def build_strategy_overrides() -> dict[str, Any]:
    universe_path = build_static18_plus_fu_sn_universe()
    eligibility_path = build_fu_sn_satellite_post_signal_eligibility()
    return {
        **CORR20_06_08_FLOOR35_OVERRIDES,
        "product_universe_csv_path": str(universe_path),
        "enable_ai_product_pool_filter": True,
        "ai_product_pool_eligibility_path": str(eligibility_path),
        "ai_product_pool_strategy": AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME,
        "streak_risk_state_excluded_products": ",".join(SATELLITE_PRODUCTS),
        "streak_risk_state_exclusion_mode": EXCLUSION_MODE,
        "sizing_equity_cap": SIZING_EQUITY_CAP,
    }


def run_candidate_backtests() -> pd.DataFrame:
    strategy_overrides = build_strategy_overrides()
    rows: list[dict[str, Any]] = []
    for window in target_windows():
        window_name = str(window["window_name"])
        analysis_start: datetime = window["analysis_start"]
        analysis_end: datetime = window["analysis_end"]
        print(
            f"[stage78-fu-sn-satellite] {window_name}: "
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
                    capital=CAPITAL,
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
                experiment_name=EXPERIMENT_NAME,
                window_name=window_name,
                display_label=str(window["display_label"]),
                capital=CAPITAL,
                sizing_equity_cap=SIZING_EQUITY_CAP,
                satellite_products=",".join(SATELLITE_PRODUCTS),
                universe_path=str(UNIVERSE_PATH),
                ai_product_pool_eligibility_path=str(ELIGIBILITY_PATH),
                ai_product_pool_strategy=AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME,
                streak_risk_state_excluded_products=",".join(SATELLITE_PRODUCTS),
                streak_risk_state_exclusion_mode=EXCLUSION_MODE,
                strategy_overrides_json=json.dumps(strategy_overrides, ensure_ascii=False, sort_keys=True),
                total_net_pnl=float(statistics.get("total_net_pnl", 0) or 0),
                total_slippage=float(statistics.get("total_slippage", 0) or 0),
                total_commission=float(statistics.get("total_commission", 0) or 0),
                profit_days=int(statistics.get("profit_days", 0) or 0),
                loss_days=int(statistics.get("loss_days", 0) or 0),
            )
        )
    return pd.DataFrame(rows).sort_values("analysis_start").reset_index(drop=True)


def load_stage78_reference() -> pd.DataFrame:
    if not STAGE78_REFERENCE_SUMMARY_PATH.exists():
        raise FileNotFoundError(STAGE78_REFERENCE_SUMMARY_PATH)
    reference = pd.read_csv(STAGE78_REFERENCE_SUMMARY_PATH)
    reference = reference[
        (reference["profile_name"].astype(str) == "stage78_capped_1m")
        & reference["window_name"].astype(str).isin(WINDOW_NAMES)
    ].copy()
    reference["experiment_name"] = "official_stage78_defensive_v1"
    return reference


def build_comparison(candidate: pd.DataFrame, reference: pd.DataFrame) -> pd.DataFrame:
    value_columns = [
        "end_balance",
        "total_return_pct",
        "max_dd_percent",
        "sharpe_ratio",
        "total_slippage",
        "total_trade_count",
    ]
    merged = reference[["window_name", *value_columns]].merge(
        candidate[["window_name", *value_columns]],
        on="window_name",
        suffixes=("_stage78", "_candidate"),
        how="inner",
    )
    for column in value_columns:
        merged[f"{column}_diff"] = merged[f"{column}_candidate"] - merged[f"{column}_stage78"]
    return merged.sort_values("window_name").reset_index(drop=True)


def build_report(candidate: pd.DataFrame, reference: pd.DataFrame, comparison: pd.DataFrame) -> str:
    return "\n".join(
        [
            "# Stage78 + fu/sn Satellite Candidate",
            "",
            "## Purpose",
            "",
            "- Test whether the next best full-market candidate (`sn.SHFE`) adds value after Stage78 already captured `fu.SHFE`.",
            "- This is a falsification test for full-market product expansion, not a new optimized pool.",
            "",
            "## Parameters",
            "",
            f"- Capital: `{CAPITAL:,.0f}`",
            f"- Sizing equity cap: `{SIZING_EQUITY_CAP:,.0f}`",
            f"- Base risk ratio: `{BASE_RISK_RATIO}`",
            f"- Satellite products: `{', '.join(SATELLITE_PRODUCTS)}`",
            f"- Streak exclusion mode: `{EXCLUSION_MODE}`",
            "",
            "## Candidate",
            "",
            to_markdown_table(
                candidate[
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
            "",
            "## Stage78 Reference",
            "",
            to_markdown_table(
                reference[
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
            "",
            "## Candidate Diff",
            "",
            to_markdown_table(
                comparison[
                    [
                        "window_name",
                        "end_balance_diff",
                        "total_return_pct_diff",
                        "max_dd_percent_diff",
                        "sharpe_ratio_diff",
                        "total_slippage_diff",
                        "total_trade_count_diff",
                    ]
                ]
            ),
            "",
            "## Judgement Rules",
            "",
            "- A new satellite is valuable only if it improves full and post-signal results without damaging latest tail.",
            "- If it only raises turnover or worsens Sharpe, full-market expansion should stop at Stage78 for now.",
            "- `sn.SHFE` is the strongest remaining discrete candidate from prior ablation, so failing here is meaningful evidence against further broad expansion.",
        ]
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    candidate = run_candidate_backtests()
    reference = load_stage78_reference()
    comparison = build_comparison(candidate, reference)
    candidate.to_csv(SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_CSV_PATH, index=False, encoding="utf-8-sig")
    payload = {
        "model_tag": MODEL_TAG,
        "official_version": OFFICIAL_STAGE78_VERSION,
        "official_role": OFFICIAL_STAGE78_ROLE,
        "base_risk_ratio": BASE_RISK_RATIO,
        "capital": CAPITAL,
        "sizing_equity_cap": SIZING_EQUITY_CAP,
        "satellite_products": list(SATELLITE_PRODUCTS),
        "candidate": candidate.to_dict(orient="records"),
        "reference": reference.to_dict(orient="records"),
        "comparison": comparison.to_dict(orient="records"),
        "outputs": {
            "universe": str(UNIVERSE_PATH),
            "eligibility": str(ELIGIBILITY_PATH),
            "summary_csv": str(SUMMARY_CSV_PATH),
            "comparison_csv": str(COMPARISON_CSV_PATH),
            "summary_json": str(SUMMARY_JSON_PATH),
            "report": str(REPORT_PATH),
        },
    }
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(build_report(candidate, reference, comparison), encoding="utf-8")
    print(comparison.to_string(index=False))
    print(f"[stage78-fu-sn-satellite] summary: {SUMMARY_CSV_PATH}")
    print(f"[stage78-fu-sn-satellite] report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
