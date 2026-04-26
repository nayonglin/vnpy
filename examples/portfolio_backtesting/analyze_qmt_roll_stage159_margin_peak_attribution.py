from __future__ import annotations

import json
import math
import sys
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from analyze_qmt_roll_stage105_margin_constraint_surface import (
    _calculate_daily_risk,
    _calculate_margin_path,
    _product_from_contract,
    _to_markdown_table,
)
from qmt_roll_official_stage78_config import (
    OFFICIAL_STAGE78_CAPITAL,
    OFFICIAL_STAGE78_ROLE,
    OFFICIAL_STAGE78_VERSION,
    build_official_stage78_overrides,
)
from qmt_universe import END_DT, START_DT
from run_qmt_alignment_backtest import build_entry_candidate_snapshots_df, build_positions_df
from run_qmt_roll_backtest import run_backtest
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO
from run_qmt_roll_stage158_dynamic_sizing_soft_cap_backtest import PROFILE as STAGE158_PROFILE
from run_qmt_roll_stage158_dynamic_sizing_soft_cap_backtest import _profile_overrides as stage158_overrides


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage159_margin_peak_attribution_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage159_margin_peak_attribution"

DAILY_MARGIN_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_margin_{MODEL_TAG}.csv"
PEAK_DAYS_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_peak_days_{MODEL_TAG}.csv"
PRODUCT_CONTRIBUTION_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_contribution_{MODEL_TAG}.csv"
CANDIDATE_DAILY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_candidate_daily_{MODEL_TAG}.csv"
POSITION_DAILY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_position_daily_{MODEL_TAG}.csv"
SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

MARGIN_EXTREME_THRESHOLD: float = 80.0
MARGIN_REJECT_THRESHOLD: float = 100.0


@dataclass(frozen=True)
class ProfileSpec:
    profile_name: str
    role: str
    strategy_overrides: dict[str, Any]


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or math.isinf(result):
        return default
    return result


def _normalize_date_series(values: Any) -> pd.Series:
    return (
        pd.to_datetime(values, errors="coerce", utc=True)
        .dt.tz_convert("Asia/Shanghai")
        .dt.tz_localize(None)
        .dt.normalize()
    )


def _to_date_series(frame: pd.DataFrame) -> pd.Series:
    if "datetime" in frame.columns:
        return _normalize_date_series(frame["datetime"])
    if "date" in frame.columns:
        return _normalize_date_series(frame["date"])
    return pd.Series(pd.NaT, index=frame.index)


def _run_profile(profile: ProfileSpec) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    print(f"[stage159-margin-peak] run {profile.profile_name}: {START_DT.date()} -> {END_DT.date()}", flush=True)
    log_buffer = StringIO()
    try:
        with redirect_stdout(log_buffer), redirect_stderr(log_buffer):
            engine, daily, statistics = run_backtest(
                risk_ratio=BASE_RISK_RATIO,
                strategy_overrides=profile.strategy_overrides,
                analysis_start=START_DT,
                analysis_end=END_DT,
                capital=OFFICIAL_STAGE78_CAPITAL,
                save_artifacts=False,
                include_start_year_sweep=False,
            )
    except Exception:
        sys.stderr.write(log_buffer.getvalue())
        raise

    daily_df = daily.copy() if daily is not None else pd.DataFrame()
    if not daily_df.empty:
        daily_df.sort_index(inplace=True)

    positions = build_positions_df(engine)
    candidates = build_entry_candidate_snapshots_df(engine)
    daily_risk = _calculate_daily_risk(daily_df, OFFICIAL_STAGE78_CAPITAL)
    daily_margin, product_daily = _calculate_margin_path(positions, daily_risk, capital=OFFICIAL_STAGE78_CAPITAL)

    for frame in (positions, candidates, daily_margin, product_daily):
        if not frame.empty:
            frame.insert(0, "profile_name", profile.profile_name)
            frame.insert(1, "profile_role", profile.role)

    summary = {
        "profile_name": profile.profile_name,
        "profile_role": profile.role,
        "base_version": OFFICIAL_STAGE78_VERSION,
        "end_balance": _safe_float(statistics.get("end_balance")),
        "total_return_pct": _safe_float(statistics.get("total_return")),
        "max_dd_percent": _safe_float(statistics.get("max_ddpercent")),
        "sharpe_ratio": _safe_float(statistics.get("sharpe_ratio")),
        "total_slippage": _safe_float(statistics.get("total_slippage")),
        "total_trade_count": int(_safe_float(statistics.get("total_trade_count"))),
        "win_ratio_pct": _safe_float(statistics.get("win_ratio")),
    }
    return summary, daily_margin, product_daily, candidates, positions


def _build_candidate_daily(candidates: pd.DataFrame) -> pd.DataFrame:
    if candidates.empty:
        return pd.DataFrame()

    frame = candidates.copy()
    frame["date"] = _to_date_series(frame)
    frame = frame[frame["date"].notna()].copy()
    if frame.empty:
        return pd.DataFrame()

    for column in [
        "selected_volume",
        "effective_sizing_equity_cap",
        "dynamic_sizing_equity_soft_cap_base",
        "dynamic_sizing_equity_soft_cap_release_weight",
        "dynamic_sizing_equity_soft_cap_enabled",
    ]:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)

    frame["is_flat_entry"] = frame.get("entry_context", "").astype(str).eq("flat_entry").astype(int)
    frame["is_opened"] = frame.get("candidate_status", "").astype(str).eq("opened").astype(int)
    frame["is_skipped"] = frame.get("candidate_status", "").astype(str).eq("skipped").astype(int)
    frame["is_expanded_cap"] = (
        frame["effective_sizing_equity_cap"] > frame["dynamic_sizing_equity_soft_cap_base"] + 1e-9
    ).astype(int)
    frame["is_expanded_opened"] = ((frame["is_expanded_cap"] > 0) & (frame["is_opened"] > 0)).astype(int)

    flat = frame[frame["is_flat_entry"] > 0].copy()
    if flat.empty:
        return pd.DataFrame()

    return (
        flat.groupby(["profile_name", "profile_role", "date"], as_index=False)
        .agg(
            flat_candidate_count=("is_flat_entry", "sum"),
            opened_flat_entry_count=("is_opened", "sum"),
            skipped_flat_entry_count=("is_skipped", "sum"),
            expanded_cap_candidate_count=("is_expanded_cap", "sum"),
            expanded_cap_opened_count=("is_expanded_opened", "sum"),
            max_effective_sizing_equity_cap=("effective_sizing_equity_cap", "max"),
            median_release_weight=("dynamic_sizing_equity_soft_cap_release_weight", "median"),
            opened_product_count=("product_vt_symbol", lambda s: int(flat.loc[s.index, "is_opened"].mul(1).where(flat.loc[s.index, "is_opened"] > 0).dropna().count())),
        )
        .sort_values(["profile_name", "date"])
        .reset_index(drop=True)
    )


def _build_position_daily(positions: pd.DataFrame) -> pd.DataFrame:
    if positions.empty:
        return pd.DataFrame()

    frame = positions.copy()
    frame["date"] = _normalize_date_series(frame["date"])
    frame = frame[frame["date"].notna()].copy()
    frame["product_vt_symbol"] = frame["vt_symbol"].map(_product_from_contract)
    for column in ["start_pos", "end_pos", "pos_change", "trade_count", "slippage", "net_pnl"]:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)

    frame["abs_start_pos"] = frame["start_pos"].abs()
    frame["abs_end_pos"] = frame["end_pos"].abs()
    frame["new_position_product"] = ((frame["abs_start_pos"] <= 1e-9) & (frame["abs_end_pos"] > 1e-9)).astype(int)
    frame["increased_position_product"] = (frame["abs_end_pos"] > frame["abs_start_pos"] + 1e-9).astype(int)
    frame["active_product"] = (frame["abs_end_pos"] > 1e-9).astype(int)
    frame["traded_product"] = (frame["trade_count"] > 0).astype(int)

    return (
        frame.groupby(["profile_name", "profile_role", "date"], as_index=False)
        .agg(
            new_position_product_count=("new_position_product", "sum"),
            increased_position_product_count=("increased_position_product", "sum"),
            active_product_count_from_positions=("active_product", "sum"),
            traded_product_count=("traded_product", "sum"),
            total_position_trade_count=("trade_count", "sum"),
            total_position_slippage=("slippage", "sum"),
            total_position_net_pnl=("net_pnl", "sum"),
        )
        .sort_values(["profile_name", "date"])
        .reset_index(drop=True)
    )


def _build_product_contribution(product_daily: pd.DataFrame, daily_margin: pd.DataFrame) -> pd.DataFrame:
    if product_daily.empty or daily_margin.empty:
        return pd.DataFrame()

    products = product_daily.copy()
    products["date"] = _normalize_date_series(products["date"])
    daily = daily_margin[
        [
            "profile_name",
            "date",
            "balance",
            "total_margin",
            "total_margin_to_balance_pct",
            "active_product_count",
        ]
    ].copy()
    daily["date"] = _normalize_date_series(daily["date"])
    merged = products.merge(daily, on=["profile_name", "date"], how="left", suffixes=("", "_daily"))
    merged["product_margin_to_balance_pct"] = (
        pd.to_numeric(merged["product_margin"], errors="coerce")
        / pd.to_numeric(merged["balance"], errors="coerce").replace(0.0, np.nan)
        * 100.0
    ).fillna(0.0)
    merged["product_margin_share"] = (
        pd.to_numeric(merged["product_margin"], errors="coerce")
        / pd.to_numeric(merged["total_margin"], errors="coerce").replace(0.0, np.nan)
    ).fillna(0.0)
    merged = merged[
        (pd.to_numeric(merged["total_margin_to_balance_pct"], errors="coerce") > MARGIN_EXTREME_THRESHOLD)
        & (pd.to_numeric(merged["product_margin"], errors="coerce") > 0.0)
    ]
    if merged.empty:
        return pd.DataFrame()
    merged["product_margin_rank"] = (
        merged.groupby(["profile_name", "date"])["product_margin"].rank(method="first", ascending=False).astype(int)
    )
    return merged.sort_values(["profile_name", "date", "product_margin_rank"]).reset_index(drop=True)


def _classify_peak_day(row: pd.Series) -> str:
    new_products = _safe_float(row.get("new_position_product_count"))
    increased_products = _safe_float(row.get("increased_position_product_count"))
    active_products = _safe_float(row.get("active_product_count"))
    top1_share = _safe_float(row.get("top1_product_margin_share"))
    margin_to_initial = _safe_float(row.get("total_margin_to_initial_capital_pct"))
    margin_to_balance = _safe_float(row.get("total_margin_to_balance_pct"))
    balance = _safe_float(row.get("balance"))

    if new_products >= 2:
        return "same_day_multi_new_positions"
    if increased_products >= 2:
        return "same_day_multi_position_increase"
    if top1_share >= 0.50:
        return "single_product_concentration"
    if active_products >= 6:
        return "multi_product_concurrency"
    if margin_to_balance > margin_to_initial + 10.0 and balance < OFFICIAL_STAGE78_CAPITAL:
        return "equity_denominator_pressure"
    return "mixed_holding_pressure"


def _build_peak_days(
    daily_margin: pd.DataFrame,
    product_contribution: pd.DataFrame,
    candidate_daily: pd.DataFrame,
    position_daily: pd.DataFrame,
) -> pd.DataFrame:
    if daily_margin.empty:
        return pd.DataFrame()

    daily = daily_margin.copy()
    daily["date"] = _normalize_date_series(daily["date"])
    peaks = daily[pd.to_numeric(daily["total_margin_to_balance_pct"], errors="coerce") > MARGIN_EXTREME_THRESHOLD].copy()
    if peaks.empty:
        return pd.DataFrame()

    top_products = product_contribution[product_contribution["product_margin_rank"] <= 3].copy()
    if not top_products.empty:
        top_products["product_label"] = (
            top_products["product_vt_symbol"].astype(str)
            + ":"
            + top_products["product_margin_to_balance_pct"].map(lambda value: f"{_safe_float(value):.2f}%")
        )
        top_list = (
            top_products.groupby(["profile_name", "date"], as_index=False)
            .agg(top_products=("product_label", lambda s: ", ".join(map(str, s))))
        )
        top1 = top_products[top_products["product_margin_rank"] == 1][
            ["profile_name", "date", "product_vt_symbol", "product_margin_share", "product_margin_to_balance_pct"]
        ].rename(
            columns={
                "product_vt_symbol": "top1_product",
                "product_margin_share": "top1_product_margin_share",
                "product_margin_to_balance_pct": "top1_product_margin_to_balance_pct",
            }
        )
        peaks = peaks.merge(top_list, on=["profile_name", "date"], how="left")
        peaks = peaks.merge(top1, on=["profile_name", "date"], how="left")

    for frame in (candidate_daily, position_daily):
        if not frame.empty:
            frame = frame.copy()
            frame["date"] = _normalize_date_series(frame["date"])
            peaks = peaks.merge(frame.drop(columns=["profile_role"], errors="ignore"), on=["profile_name", "date"], how="left")

    fill_zero = [
        "flat_candidate_count",
        "opened_flat_entry_count",
        "expanded_cap_candidate_count",
        "expanded_cap_opened_count",
        "new_position_product_count",
        "increased_position_product_count",
        "traded_product_count",
        "total_position_trade_count",
    ]
    for column in fill_zero:
        peaks[column] = pd.to_numeric(peaks.get(column, 0.0), errors="coerce").fillna(0.0)
    peaks["top1_product_margin_share"] = pd.to_numeric(
        peaks.get("top1_product_margin_share", 0.0),
        errors="coerce",
    ).fillna(0.0)
    peaks["peak_severity"] = np.where(
        pd.to_numeric(peaks["total_margin_to_balance_pct"], errors="coerce") > MARGIN_REJECT_THRESHOLD,
        "reject_gt_100",
        "extreme_gt_80",
    )
    peaks["peak_cause"] = peaks.apply(_classify_peak_day, axis=1)

    return peaks.sort_values(["profile_name", "date"]).reset_index(drop=True)


def _summarize_profiles(
    run_summaries: list[dict[str, Any]],
    peak_days: pd.DataFrame,
    product_contribution: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for summary in run_summaries:
        profile_name = str(summary["profile_name"])
        profile_peaks = peak_days[peak_days["profile_name"].astype(str).eq(profile_name)].copy()
        profile_products = product_contribution[product_contribution["profile_name"].astype(str).eq(profile_name)].copy()
        top_product = ""
        if not profile_products.empty:
            product_totals = (
                profile_products.groupby("product_vt_symbol", as_index=False)["product_margin"].sum()
                .sort_values("product_margin", ascending=False)
                .reset_index(drop=True)
            )
            top_product = str(product_totals.iloc[0]["product_vt_symbol"]) if not product_totals.empty else ""
        cause_counts = (
            profile_peaks["peak_cause"].value_counts().to_dict() if not profile_peaks.empty and "peak_cause" in profile_peaks else {}
        )
        max_margin_row = (
            profile_peaks.loc[profile_peaks["total_margin_to_balance_pct"].idxmax()].to_dict()
            if not profile_peaks.empty
            else {}
        )
        rows.append(
            {
                **summary,
                "peak_days_gt_80pct": int(len(profile_peaks)),
                "peak_days_gt_100pct": int((pd.to_numeric(profile_peaks.get("total_margin_to_balance_pct", 0), errors="coerce") > 100.0).sum())
                if not profile_peaks.empty
                else 0,
                "max_margin_to_balance_pct": _safe_float(max_margin_row.get("total_margin_to_balance_pct")),
                "max_margin_date": str(max_margin_row.get("date", ""))[:10],
                "max_margin_active_product_count": int(_safe_float(max_margin_row.get("active_product_count"))),
                "max_margin_top_products": str(max_margin_row.get("top_products", "")),
                "dominant_peak_cause": max(cause_counts, key=cause_counts.get) if cause_counts else "",
                "peak_cause_counts_json": json.dumps(cause_counts, ensure_ascii=False, sort_keys=True),
                "top_peak_margin_product": top_product,
            }
        )
    return pd.DataFrame(rows)


def _build_report(summary: pd.DataFrame, peak_days: pd.DataFrame, product_contribution: pd.DataFrame) -> str:
    top_product_view = pd.DataFrame()
    if not product_contribution.empty:
        top_product_view = (
            product_contribution.groupby(["profile_name", "product_vt_symbol"], as_index=False)
            .agg(
                peak_day_product_margin_sum=("product_margin", "sum"),
                peak_day_count=("date", "nunique"),
                max_product_margin_to_balance_pct=("product_margin_to_balance_pct", "max"),
            )
            .sort_values(["profile_name", "peak_day_product_margin_sum"], ascending=[True, False])
            .groupby("profile_name")
            .head(8)
            .reset_index(drop=True)
        )
    peak_view_columns = [
        "profile_name",
        "date",
        "peak_severity",
        "total_margin_to_balance_pct",
        "active_product_count",
        "balance",
        "new_position_product_count",
        "increased_position_product_count",
        "top_products",
        "peak_cause",
    ]
    return "\n".join(
        [
            "# Stage159 Margin Peak Attribution",
            "",
            "## Boundary",
            "",
            "- This is an attribution audit, not a new strategy version.",
            "- A = frozen `official_stage78_defensive_v1`.",
            "- C = Stage158 dynamic sizing soft-cap candidate, kept rejected and default-off.",
            "- The script reruns A and C only to extract daily positions, product-level margin and candidate snapshots.",
            "- No parameters are optimized and no trading rule is changed.",
            "",
            "## Profile Summary",
            "",
            _to_markdown_table(
                summary,
                [
                    "profile_name",
                    "end_balance",
                    "total_return_pct",
                    "max_dd_percent",
                    "sharpe_ratio",
                    "total_slippage",
                    "total_trade_count",
                    "win_ratio_pct",
                    "peak_days_gt_80pct",
                    "peak_days_gt_100pct",
                    "max_margin_to_balance_pct",
                    "max_margin_date",
                    "dominant_peak_cause",
                    "top_peak_margin_product",
                ],
            ),
            "",
            "## Peak Days",
            "",
            _to_markdown_table(peak_days, peak_view_columns, max_rows=40),
            "",
            "## Top Product Contributions On Peak Days",
            "",
            _to_markdown_table(
                top_product_view,
                [
                    "profile_name",
                    "product_vt_symbol",
                    "peak_day_product_margin_sum",
                    "peak_day_count",
                    "max_product_margin_to_balance_pct",
                ],
                max_rows=30,
            ),
            "",
            "## Judgement Rule",
            "",
            "- If peak days are broad multi-product concurrency, a future rule must reduce portfolio-level peak exposure before expanding cap.",
            "- If peak days are one-off products or dates, do not patch them into strategy rules.",
            "- If C has the same peak structure as A, dynamic cap expansion did not solve the deployability problem.",
        ]
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    profiles = (
        ProfileSpec(
            profile_name="A_official_stage78",
            role=OFFICIAL_STAGE78_ROLE,
            strategy_overrides=build_official_stage78_overrides(),
        ),
        ProfileSpec(
            profile_name="C_stage158_dynamic_soft_cap",
            role="rejected_dynamic_sizing_soft_cap_candidate",
            strategy_overrides=stage158_overrides(STAGE158_PROFILE),
        ),
    )

    run_summaries: list[dict[str, Any]] = []
    daily_margin_frames: list[pd.DataFrame] = []
    product_frames: list[pd.DataFrame] = []
    candidate_frames: list[pd.DataFrame] = []
    position_frames: list[pd.DataFrame] = []

    for profile in profiles:
        summary, daily_margin, product_daily, candidates, positions = _run_profile(profile)
        run_summaries.append(summary)
        if not daily_margin.empty:
            daily_margin_frames.append(daily_margin)
        if not product_daily.empty:
            product_frames.append(product_daily)
        if not candidates.empty:
            candidate_frames.append(candidates)
        if not positions.empty:
            position_frames.append(positions)

    daily_margin_all = pd.concat(daily_margin_frames, ignore_index=True, sort=False) if daily_margin_frames else pd.DataFrame()
    product_daily_all = pd.concat(product_frames, ignore_index=True, sort=False) if product_frames else pd.DataFrame()
    candidates_all = pd.concat(candidate_frames, ignore_index=True, sort=False) if candidate_frames else pd.DataFrame()
    positions_all = pd.concat(position_frames, ignore_index=True, sort=False) if position_frames else pd.DataFrame()

    candidate_daily = _build_candidate_daily(candidates_all)
    position_daily = _build_position_daily(positions_all)
    product_contribution = _build_product_contribution(product_daily_all, daily_margin_all)
    peak_days = _build_peak_days(daily_margin_all, product_contribution, candidate_daily, position_daily)
    summary = _summarize_profiles(run_summaries, peak_days, product_contribution)

    daily_margin_all.to_csv(DAILY_MARGIN_PATH, index=False, encoding="utf-8-sig")
    peak_days.to_csv(PEAK_DAYS_PATH, index=False, encoding="utf-8-sig")
    product_contribution.to_csv(PRODUCT_CONTRIBUTION_PATH, index=False, encoding="utf-8-sig")
    candidate_daily.to_csv(CANDIDATE_DAILY_PATH, index=False, encoding="utf-8-sig")
    position_daily.to_csv(POSITION_DAILY_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    payload = {
        "model_tag": MODEL_TAG,
        "base_version": OFFICIAL_STAGE78_VERSION,
        "capital": OFFICIAL_STAGE78_CAPITAL,
        "margin_extreme_threshold": MARGIN_EXTREME_THRESHOLD,
        "margin_reject_threshold": MARGIN_REJECT_THRESHOLD,
        "summary": summary.to_dict(orient="records"),
        "output_paths": {
            "daily_margin": str(DAILY_MARGIN_PATH),
            "peak_days": str(PEAK_DAYS_PATH),
            "product_contribution": str(PRODUCT_CONTRIBUTION_PATH),
            "candidate_daily": str(CANDIDATE_DAILY_PATH),
            "position_daily": str(POSITION_DAILY_PATH),
            "summary": str(SUMMARY_CSV_PATH),
            "report": str(REPORT_PATH),
        },
    }
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    REPORT_PATH.write_text(_build_report(summary, peak_days, product_contribution), encoding="utf-8")

    print(f"[stage159-margin-peak] summary: {SUMMARY_CSV_PATH}")
    print(f"[stage159-margin-peak] report: {REPORT_PATH}")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
