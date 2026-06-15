from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage858"
MODEL_TAG = "stage858_stage857_coverage_bias_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage858_stage857_coverage_bias_audit"

STAGE855_PREFIX = "qmt_roll_stage855_stage854_local_raw_import"
STAGE855_TAG = "stage855_stage854_local_raw_import_v1"
STAGE856_PREFIX = "qmt_roll_stage856_stage855_remaining_gap_download"
STAGE856_TAG = "stage856_stage855_remaining_gap_download_v1"
STAGE857_PREFIX = "qmt_roll_stage857_stage855_patch_visual_atlas"
STAGE857_TAG = "stage857_stage855_patch_visual_atlas_v1"
STAGE849_PREFIX = "qmt_roll_stage849_stage848_pressure_path_forensics"
STAGE849_TAG = "stage849_stage848_pressure_path_forensics_v1"

STAGE825_COVERAGE_AFTER_PATCH_PATH = (
    OUTPUT_DIR / f"{STAGE855_PREFIX}_stage825_coverage_after_patch_{STAGE855_TAG}.csv"
)
STAGE825_YEAR_COVERAGE_AFTER_PATCH_PATH = (
    OUTPUT_DIR / f"{STAGE855_PREFIX}_stage825_year_coverage_after_patch_{STAGE855_TAG}.csv"
)
REMAINING_GAP_REQUESTS_PATH = (
    OUTPUT_DIR / f"{STAGE856_PREFIX}_remaining_gap_requests_{STAGE856_TAG}.csv"
)
PATCH_ENTRY_FEATURES_PATH = (
    OUTPUT_DIR / f"{STAGE857_PREFIX}_patch_entry_lot_features_{STAGE857_TAG}.csv"
)
PRESSURE_COVERAGE_AFTER_PATCH_PATH = (
    OUTPUT_DIR / f"{STAGE855_PREFIX}_stage849_pressure_coverage_after_patch_{STAGE855_TAG}.csv"
)
PRESSURE_LOT_PAIRS_PATH = (
    OUTPUT_DIR / f"{STAGE849_PREFIX}_episode_lot_pairs_{STAGE849_TAG}.csv"
)
PRESSURE_EPISODE_SUMMARY_PATH = (
    OUTPUT_DIR / f"{STAGE849_PREFIX}_episode_summary_{STAGE849_TAG}.csv"
)

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COVERAGE_BY_YEAR_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coverage_by_year_{MODEL_TAG}.csv"
COVERAGE_BY_PRODUCT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coverage_by_product_{MODEL_TAG}.csv"
COVERAGE_BY_DIRECTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coverage_by_direction_{MODEL_TAG}.csv"
COVERAGE_BY_OUTCOME_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coverage_by_outcome_{MODEL_TAG}.csv"
PNL_DISTRIBUTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pnl_distribution_{MODEL_TAG}.csv"
TOP_MISSING_LOTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_top_missing_lots_{MODEL_TAG}.csv"
PRESSURE_COVERAGE_BIAS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pressure_coverage_bias_{MODEL_TAG}.csv"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bias_chart_{MODEL_TAG}.png"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "无数据。"
    view = frame.copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda item: f"{item:.4f}" if pd.notna(item) else "")
    return view.to_markdown(index=False)


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"Missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _numeric(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for column in columns:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def _normal_date_text(value: Any) -> str:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return ""
    return str(pd.Timestamp(ts).date())


def _normal_float(value: Any) -> float:
    number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(number):
        return np.nan
    return float(number)


def _product_from_vt(vt_symbol: Any) -> str:
    text = str(vt_symbol)
    if "." not in text:
        return text
    contract, exchange = text.split(".", 1)
    letters = "".join(ch for ch in contract if ch.isalpha())
    return f"{letters}.{exchange}" if letters else text


def _prepare_lots() -> pd.DataFrame:
    lots = _load_csv(STAGE825_COVERAGE_AFTER_PATCH_PATH).copy()
    lots = _numeric(
        lots,
        [
            "lot_id",
            "realized_pnl",
            "r_multiple",
            "risk_amount",
            "volume",
            "entry_price",
            "exit_price",
            "entry_year",
            "winner",
            "big_winner",
            "original_entry_day_covered",
            "stage855_patch_covered",
            "after_patch_entry_day_covered",
            "entry_day_minute_bars",
        ],
    )
    lots["entry_date_text"] = lots["entry_date"].map(_normal_date_text)
    lots["exit_date_text"] = lots["exit_date"].map(_normal_date_text)
    lots["entry_year"] = lots["entry_year"].fillna(
        pd.to_datetime(lots["entry_date"], errors="coerce").dt.year
    )
    lots["entry_year"] = lots["entry_year"].astype("Int64")
    lots["product"] = lots.get("product", lots["vt_symbol"].map(_product_from_vt)).fillna(
        lots["vt_symbol"].map(_product_from_vt)
    )
    lots["covered_after_patch"] = lots["after_patch_entry_day_covered"].fillna(0).astype(int).eq(1)
    lots["coverage_bucket"] = np.where(lots["covered_after_patch"], "covered", "missing")
    lots["abs_pnl"] = lots["realized_pnl"].abs()
    lots["winner_flag"] = lots["realized_pnl"].fillna(0.0).gt(0)
    lots["loser_flag"] = lots["realized_pnl"].fillna(0.0).lt(0)
    lots["big_winner_flag"] = lots["big_winner"].fillna(0).astype(float).gt(0)
    lots["patch_covered_flag"] = lots["stage855_patch_covered"].fillna(0).astype(int).eq(1)
    lots["original_covered_flag"] = lots["original_entry_day_covered"].fillna(0).astype(int).eq(1)
    return _mark_pressure_lots(lots)


PressureKey = tuple[str, str, str, str, float, float, str]


def _pressure_key_map() -> dict[PressureKey, str]:
    if not PRESSURE_LOT_PAIRS_PATH.exists():
        return {}
    pairs = _load_csv(PRESSURE_LOT_PAIRS_PATH)
    mapping: dict[PressureKey, str] = {}
    for _, row in pairs.iterrows():
        key = (
            str(row.get("vt_symbol", "")),
            str(row.get("direction", "")),
            _normal_date_text(row.get("entry_date")),
            _normal_date_text(row.get("exit_date")),
            round(_normal_float(row.get("entry_price")), 8),
            round(_normal_float(row.get("exit_price")), 8),
            str(row.get("exit_reason", "")),
        )
        mapping[key] = str(row.get("episode_id", ""))
    return mapping


def _mark_pressure_lots(lots: pd.DataFrame) -> pd.DataFrame:
    key_map = _pressure_key_map()
    if not key_map:
        lots["pressure_pair_lot"] = False
        lots["pressure_episode_id"] = ""
        return lots
    lot_keys = []
    for _, row in lots.iterrows():
        lot_keys.append(
            (
                str(row.get("vt_symbol", "")),
                str(row.get("direction", "")),
                row.get("entry_date_text", ""),
                row.get("exit_date_text", ""),
                round(_normal_float(row.get("entry_price")), 8),
                round(_normal_float(row.get("exit_price")), 8),
                str(row.get("exit_reason", "")),
            )
        )
    lots["pressure_episode_id"] = [key_map.get(key, "") for key in lot_keys]
    lots["pressure_pair_lot"] = lots["pressure_episode_id"].astype(str).ne("")
    return lots


def _aggregate_by(
    lots: pd.DataFrame,
    column: str,
    *,
    sort_by_missing_abs: bool = True,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for value, group in lots.groupby(column, dropna=False):
        covered = group[group["covered_after_patch"]]
        missing = group[~group["covered_after_patch"]]
        total = len(group)
        rows.append(
            {
                column: "" if pd.isna(value) else value,
                "lots": total,
                "covered_lots": int(len(covered)),
                "missing_lots": int(len(missing)),
                "coverage_rate": float(len(covered) / total) if total else 0.0,
                "total_pnl": float(group["realized_pnl"].sum()),
                "covered_pnl": float(covered["realized_pnl"].sum()),
                "missing_pnl": float(missing["realized_pnl"].sum()),
                "missing_abs_pnl": float(missing["abs_pnl"].sum()),
                "missing_abs_pnl_share_in_group": float(missing["abs_pnl"].sum() / group["abs_pnl"].sum())
                if float(group["abs_pnl"].sum()) > 0
                else 0.0,
                "big_winner_lots": int(group["big_winner_flag"].sum()),
                "missing_big_winner_lots": int(missing["big_winner_flag"].sum()),
                "pressure_pair_lots": int(group["pressure_pair_lot"].sum()),
                "missing_pressure_pair_lots": int(missing["pressure_pair_lot"].sum()),
            }
        )
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    if sort_by_missing_abs:
        return result.sort_values(
            ["missing_abs_pnl", "missing_lots", column],
            ascending=[False, False, True],
        ).reset_index(drop=True)
    return result.sort_values(column).reset_index(drop=True)


def _coverage_by_year(lots: pd.DataFrame) -> pd.DataFrame:
    result = _aggregate_by(lots, "entry_year", sort_by_missing_abs=False)
    if STAGE825_YEAR_COVERAGE_AFTER_PATCH_PATH.exists() and not result.empty:
        baseline = _load_csv(STAGE825_YEAR_COVERAGE_AFTER_PATCH_PATH)
        baseline = _numeric(
            baseline,
            [
                "entry_year",
                "original_covered_lots",
                "stage855_patch_covered_lots",
                "after_patch_covered_lots",
                "after_patch_missing_lots",
                "original_coverage_rate",
                "after_patch_coverage_rate",
            ],
        )
        result = result.merge(
            baseline[
                [
                    "entry_year",
                    "original_covered_lots",
                    "stage855_patch_covered_lots",
                    "after_patch_covered_lots",
                    "after_patch_missing_lots",
                    "original_coverage_rate",
                    "after_patch_coverage_rate",
                ]
            ],
            on="entry_year",
            how="left",
        )
    return result


def _coverage_by_outcome(lots: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for bucket, group in lots.groupby("coverage_bucket", dropna=False):
        count = len(group)
        rows.append(
            {
                "coverage_bucket": bucket,
                "lots": count,
                "pnl_sum": float(group["realized_pnl"].sum()),
                "pnl_mean": float(group["realized_pnl"].mean()) if count else 0.0,
                "pnl_median": float(group["realized_pnl"].median()) if count else 0.0,
                "abs_pnl_sum": float(group["abs_pnl"].sum()),
                "win_lots": int(group["winner_flag"].sum()),
                "loss_lots": int(group["loser_flag"].sum()),
                "win_rate": float(group["winner_flag"].mean()) if count else 0.0,
                "big_winner_lots": int(group["big_winner_flag"].sum()),
                "big_winner_pnl": float(group.loc[group["big_winner_flag"], "realized_pnl"].sum()),
                "pressure_pair_lots": int(group["pressure_pair_lot"].sum()),
            }
        )
    return pd.DataFrame(rows).sort_values("coverage_bucket").reset_index(drop=True)


def _pnl_distribution(lots: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    quantiles = [0.0, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 1.0]
    for bucket, group in lots.groupby("coverage_bucket", dropna=False):
        pnl = group["realized_pnl"].dropna()
        abs_pnl = group["abs_pnl"].dropna()
        row: dict[str, Any] = {
            "coverage_bucket": bucket,
            "lots": int(len(group)),
            "pnl_sum": float(pnl.sum()) if not pnl.empty else 0.0,
            "abs_pnl_sum": float(abs_pnl.sum()) if not abs_pnl.empty else 0.0,
        }
        for quantile in quantiles:
            suffix = str(int(quantile * 100)).zfill(2)
            row[f"pnl_q{suffix}"] = float(pnl.quantile(quantile)) if not pnl.empty else np.nan
            row[f"abs_pnl_q{suffix}"] = float(abs_pnl.quantile(quantile)) if not abs_pnl.empty else np.nan
        rows.append(row)
    return pd.DataFrame(rows).sort_values("coverage_bucket").reset_index(drop=True)


def _top_missing_lots(lots: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "lot_id",
        "vt_symbol",
        "product",
        "direction",
        "entry_date",
        "exit_date",
        "realized_pnl",
        "abs_pnl",
        "r_multiple",
        "big_winner",
        "exit_reason",
        "signal",
        "pressure_pair_lot",
        "coverage_state_after_patch",
    ]
    existing = [column for column in columns if column in lots.columns]
    return (
        lots[~lots["covered_after_patch"]][existing]
        .sort_values(["abs_pnl", "lot_id"], ascending=[False, True])
        .head(40)
        .reset_index(drop=True)
    )


def _remaining_gap_summary() -> dict[str, Any]:
    if not REMAINING_GAP_REQUESTS_PATH.exists():
        return {}
    gap = _load_csv(REMAINING_GAP_REQUESTS_PATH)
    gap = _numeric(gap, ["priority_abs_pnl", "realized_pnl", "big_winner", "entry_year"])
    return {
        "remaining_gap_requests": int(len(gap)),
        "remaining_gap_priority_abs_pnl": float(gap["priority_abs_pnl"].sum()),
        "remaining_gap_big_winner_requests": int(gap["big_winner"].fillna(0).astype(float).gt(0).sum()),
        "remaining_gap_products": int(gap["product"].astype(str).nunique()) if "product" in gap.columns else 0,
        "remaining_gap_symbols": int(gap["vt_symbol"].astype(str).nunique()) if "vt_symbol" in gap.columns else 0,
    }


def _patch_entry_summary() -> dict[str, Any]:
    if not PATCH_ENTRY_FEATURES_PATH.exists():
        return {}
    patch = _load_csv(PATCH_ENTRY_FEATURES_PATH)
    patch = _numeric(patch, ["realized_pnl", "big_winner"])
    return {
        "stage857_patch_entry_lots": int(len(patch)),
        "stage857_patch_entry_pnl": float(patch["realized_pnl"].sum()) if "realized_pnl" in patch else 0.0,
        "stage857_patch_entry_big_winner_lots": int(
            patch["big_winner"].fillna(0).astype(float).gt(0).sum()
        )
        if "big_winner" in patch
        else 0,
    }


def _pressure_coverage_bias(lots: pd.DataFrame) -> pd.DataFrame:
    if not PRESSURE_COVERAGE_AFTER_PATCH_PATH.exists():
        return pd.DataFrame()
    pressure_dates = _load_csv(PRESSURE_COVERAGE_AFTER_PATCH_PATH)
    pressure_dates = _numeric(
        pressure_dates,
        [
            "after_patch_minute_bars",
            "covered_after_patch",
            "stage855_patch_bars",
            "original_minute_bars",
        ],
    )
    episode_summary = (
        _load_csv(PRESSURE_EPISODE_SUMMARY_PATH)
        if PRESSURE_EPISODE_SUMMARY_PATH.exists()
        else pd.DataFrame()
    )
    if not episode_summary.empty:
        episode_summary = _numeric(
            episode_summary,
            [
                "paired_lots",
                "paired_volume_delta_C9_minus_C4",
                "paired_risk_delta_C9_minus_C4",
                "paired_pnl_delta_C9_minus_C4",
                "max_broker10_delta_C9_minus_C4",
            ],
        )

    pressure_lots = lots[lots["pressure_pair_lot"]].copy()
    rows: list[dict[str, Any]] = []
    for episode_id, group in pressure_dates.groupby("episode_id", dropna=False):
        covered = group["covered_after_patch"].fillna(0).astype(int).eq(1)
        lot_group = pressure_lots[pressure_lots["pressure_episode_id"].astype(str).eq(str(episode_id))]
        summary_row = (
            episode_summary[episode_summary["episode_id"].astype(str).eq(str(episode_id))]
            if not episode_summary.empty
            else pd.DataFrame()
        )
        rows.append(
            {
                "episode_id": str(episode_id),
                "vt_symbol": ",".join(sorted(set(group["vt_symbol"].astype(str)))),
                "direction": ",".join(sorted(set(group["direction"].astype(str)))) if "direction" in group else "",
                "key_dates": int(len(group)),
                "covered_key_dates": int(covered.sum()),
                "missing_key_dates": int((~covered).sum()),
                "coverage_rate": float(covered.mean()) if len(group) else 0.0,
                "patch_covered_key_dates": int(group["stage855_patch_bars"].fillna(0).gt(0).sum())
                if "stage855_patch_bars" in group
                else 0,
                "pressure_pair_lots_in_stage825": int(len(lot_group)),
                "missing_pressure_pair_lots_in_stage825": int((~lot_group["covered_after_patch"]).sum())
                if not lot_group.empty
                else 0,
                "pressure_pair_pnl_in_stage825": float(lot_group["realized_pnl"].sum())
                if not lot_group.empty
                else 0.0,
                "paired_lots_stage849": int(summary_row["paired_lots"].iloc[0])
                if not summary_row.empty and pd.notna(summary_row["paired_lots"].iloc[0])
                else 0,
                "paired_pnl_delta_C9_minus_C4": float(summary_row["paired_pnl_delta_C9_minus_C4"].iloc[0])
                if not summary_row.empty and pd.notna(summary_row["paired_pnl_delta_C9_minus_C4"].iloc[0])
                else np.nan,
                "max_broker10_delta_C9_minus_C4": float(summary_row["max_broker10_delta_C9_minus_C4"].iloc[0])
                if not summary_row.empty and pd.notna(summary_row["max_broker10_delta_C9_minus_C4"].iloc[0])
                else np.nan,
            }
        )
    return pd.DataFrame(rows).sort_values(["coverage_rate", "episode_id"]).reset_index(drop=True)


def _bias_flags(
    lots: pd.DataFrame,
    by_year: pd.DataFrame,
    pressure_bias: pd.DataFrame,
) -> dict[str, Any]:
    total_abs_pnl = float(lots["abs_pnl"].sum())
    missing = lots[~lots["covered_after_patch"]]
    missing_abs_pnl = float(missing["abs_pnl"].sum())
    zero_coverage_years = by_year[
        by_year["lots"].fillna(0).astype(float).ge(20)
        & by_year["coverage_rate"].fillna(0).astype(float).le(0.0)
    ]
    pressure_key_dates = int(pressure_bias["key_dates"].sum()) if not pressure_bias.empty else 0
    pressure_covered_dates = int(pressure_bias["covered_key_dates"].sum()) if not pressure_bias.empty else 0
    pressure_coverage_rate = (
        float(pressure_covered_dates / pressure_key_dates) if pressure_key_dates else np.nan
    )
    flags = {
        "zero_coverage_years_with_20plus_lots": int(len(zero_coverage_years)),
        "zero_coverage_year_list": ",".join(str(int(item)) for item in zero_coverage_years["entry_year"].dropna()),
        "missing_big_winner_lots": int(missing["big_winner_flag"].sum()),
        "missing_abs_pnl_share": float(missing_abs_pnl / total_abs_pnl) if total_abs_pnl > 0 else 0.0,
        "pressure_key_date_coverage_rate": pressure_coverage_rate,
        "pressure_missing_key_dates": int(pressure_key_dates - pressure_covered_dates) if pressure_key_dates else 0,
        "missing_pressure_pair_lots": int((~lots.loc[lots["pressure_pair_lot"], "covered_after_patch"]).sum())
        if lots["pressure_pair_lot"].any()
        else 0,
    }
    flag_count = 0
    flag_count += int(flags["zero_coverage_years_with_20plus_lots"] > 0)
    flag_count += int(flags["missing_big_winner_lots"] > 0)
    flag_count += int(flags["missing_abs_pnl_share"] >= 0.20)
    if not np.isnan(flags["pressure_key_date_coverage_rate"]):
        flag_count += int(flags["pressure_key_date_coverage_rate"] < 0.80)
    flag_count += int(flags["missing_pressure_pair_lots"] > 0)
    flags["bias_flag_count"] = flag_count
    flags["severe_bias"] = bool(flag_count >= 2)
    return flags


def _summary_row(
    lots: pd.DataFrame,
    by_year: pd.DataFrame,
    pressure_bias: pd.DataFrame,
) -> dict[str, Any]:
    covered = lots[lots["covered_after_patch"]]
    missing = lots[~lots["covered_after_patch"]]
    total = len(lots)
    original_covered = int(lots["original_covered_flag"].sum())
    patch_covered = int(lots["patch_covered_flag"].sum())
    flags = _bias_flags(lots, by_year, pressure_bias)
    row: dict[str, Any] = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "total_closed_lots": total,
        "original_covered_lots": original_covered,
        "stage855_patch_covered_lots": patch_covered,
        "after_patch_covered_lots": int(len(covered)),
        "after_patch_missing_lots": int(len(missing)),
        "after_patch_coverage_rate": float(len(covered) / total) if total else 0.0,
        "covered_pnl": float(covered["realized_pnl"].sum()),
        "missing_pnl": float(missing["realized_pnl"].sum()),
        "covered_abs_pnl": float(covered["abs_pnl"].sum()),
        "missing_abs_pnl": float(missing["abs_pnl"].sum()),
        "total_big_winner_lots": int(lots["big_winner_flag"].sum()),
        "covered_big_winner_lots": int(covered["big_winner_flag"].sum()),
        "missing_big_winner_lots": int(missing["big_winner_flag"].sum()),
        "covered_win_rate": float(covered["winner_flag"].mean()) if len(covered) else 0.0,
        "missing_win_rate": float(missing["winner_flag"].mean()) if len(missing) else 0.0,
        "pressure_pair_lots": int(lots["pressure_pair_lot"].sum()),
        "covered_pressure_pair_lots": int(lots.loc[lots["pressure_pair_lot"], "covered_after_patch"].sum())
        if lots["pressure_pair_lot"].any()
        else 0,
        "missing_pressure_pair_lots": int((~lots.loc[lots["pressure_pair_lot"], "covered_after_patch"]).sum())
        if lots["pressure_pair_lot"].any()
        else 0,
    }
    row.update(flags)
    row.update(_remaining_gap_summary())
    row.update(_patch_entry_summary())
    row["decision"] = (
        "stage858_coverage_bias_severe_no_rule"
        if flags["severe_bias"]
        else "stage858_coverage_bias_tolerable_but_still_no_rule"
    )
    return row


def _draw_chart(
    lots: pd.DataFrame,
    by_year: pd.DataFrame,
    by_product: pd.DataFrame,
    pressure_bias: pd.DataFrame,
    summary: dict[str, Any],
) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))

    year_view = by_year.sort_values("entry_year")
    axes[0, 0].bar(year_view["entry_year"].astype(str), year_view["coverage_rate"], color="#2f6f9f")
    axes[0, 0].set_ylim(0, 1.05)
    axes[0, 0].set_title("Entry-day minute coverage by year")
    axes[0, 0].set_ylabel("coverage rate")
    axes[0, 0].tick_params(axis="x", rotation=45)
    for idx, row in year_view.iterrows():
        axes[0, 0].text(
            list(year_view.index).index(idx),
            min(float(row["coverage_rate"]) + 0.03, 1.02),
            f"{int(row['covered_lots'])}/{int(row['lots'])}",
            ha="center",
            fontsize=8,
        )

    product_view = by_product.head(12).sort_values("missing_abs_pnl", ascending=True)
    axes[0, 1].barh(product_view["product"].astype(str), product_view["missing_abs_pnl"], color="#c75b39")
    axes[0, 1].set_title("Top missing abs PnL by product")
    axes[0, 1].set_xlabel("missing abs PnL")

    covered_pnl = lots.loc[lots["covered_after_patch"], "realized_pnl"].dropna().to_numpy(dtype=float)
    missing_pnl = lots.loc[~lots["covered_after_patch"], "realized_pnl"].dropna().to_numpy(dtype=float)
    axes[1, 0].boxplot(
        [covered_pnl, missing_pnl],
        tick_labels=["covered", "missing"],
        showfliers=False,
    )
    axes[1, 0].axhline(0.0, color="#333333", linewidth=0.8)
    axes[1, 0].set_title("PnL distribution by coverage bucket")
    axes[1, 0].set_ylabel("realized PnL")

    labels = [
        "missing lots",
        "missing big winners",
        "missing pressure dates",
        "zero-cover years",
    ]
    values = [
        int(summary.get("after_patch_missing_lots", 0)),
        int(summary.get("missing_big_winner_lots", 0)),
        int(summary.get("pressure_missing_key_dates", 0) or 0),
        int(summary.get("zero_coverage_years_with_20plus_lots", 0)),
    ]
    colors = ["#7f7f7f", "#8f3f71", "#d9912b", "#4b6f44"]
    axes[1, 1].bar(labels, values, color=colors)
    axes[1, 1].set_title("Bias red flags")
    axes[1, 1].tick_params(axis="x", rotation=20)
    for index, value in enumerate(values):
        axes[1, 1].text(index, value + max(values + [1]) * 0.02, str(value), ha="center", fontsize=9)

    note = (
        f"coverage={summary.get('after_patch_coverage_rate', 0.0):.2%}, "
        f"missing_abs_share={summary.get('missing_abs_pnl_share', 0.0):.2%}, "
        f"pressure_date_cov={summary.get('pressure_key_date_coverage_rate', np.nan):.2%}"
    )
    fig.suptitle(f"{STAGE} coverage bias audit - {note}", fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(
    summary: dict[str, Any],
    by_year: pd.DataFrame,
    by_product: pd.DataFrame,
    by_direction: pd.DataFrame,
    by_outcome: pd.DataFrame,
    pnl_distribution: pd.DataFrame,
    pressure_bias: pd.DataFrame,
    top_missing: pd.DataFrame,
) -> None:
    decision = summary["decision"]
    severe_text = "是" if summary.get("severe_bias") else "否"
    lines = [
        f"# {STAGE} Stage857后覆盖偏差审计",
        "",
        "## 外部调研与判断",
        "",
        "- 参考 TqSdk DataDownloader 官方文档：历史数据下载是独立能力；Stage856 的失败信息指向账号历史数据下载权限不足，而不是脚本逻辑可通过重复下载解决。",
        "- 参考 vnpy_tqsdk GitHub 项目：vn.py 接入 TqSdk 能作为行情源通路，但不能绕过上游账号历史下载权限。",
        "- 回测方法论判断：当分钟K缺失集中在早期年份、特定合约和大赢家/压力段时，已覆盖样本会有选择偏差；不能把 covered subset 的图谱结论外推为全周期分钟级交易规则。",
        "",
        "## 审计结论",
        "",
        f"- 决策：`{decision}`。",
        f"- 覆盖偏差是否严重：{severe_text}。",
        f"- Stage855后入场日分钟K覆盖：`{summary['after_patch_covered_lots']}/{summary['total_closed_lots']} = {summary['after_patch_coverage_rate']:.4%}`。",
        f"- 未覆盖样本：`{summary['after_patch_missing_lots']}` 笔，未覆盖绝对PnL：`{summary['missing_abs_pnl']:.0f}`，占全样本绝对PnL `{summary['missing_abs_pnl_share']:.4%}`。",
        f"- 未覆盖 big winner：`{summary['missing_big_winner_lots']}/{summary['total_big_winner_lots']}`。",
        f"- 压力 key date 覆盖率：`{summary['pressure_key_date_coverage_rate']:.4%}`，仍缺 `{summary['pressure_missing_key_dates']}` 个 key dates。",
        f"- 零覆盖且样本数不少于20笔的年份：`{summary['zero_coverage_year_list'] or '无'}`。",
        "",
        "## 年份覆盖",
        "",
        _md_table(by_year, max_rows=20),
        "",
        "## 品种缺口影响Top",
        "",
        _md_table(by_product, max_rows=20),
        "",
        "## 方向覆盖",
        "",
        _md_table(by_direction, max_rows=10),
        "",
        "## 覆盖/未覆盖结果分布",
        "",
        _md_table(by_outcome, max_rows=10),
        "",
        "## PnL分位数",
        "",
        _md_table(pnl_distribution, max_rows=10),
        "",
        "## 压力段覆盖偏差",
        "",
        _md_table(pressure_bias, max_rows=20),
        "",
        "## 高影响未覆盖lot",
        "",
        _md_table(top_missing, max_rows=25),
        "",
        "## 判断",
        "",
        "- 本阶段不产生新交易规则、不接真实引擎、不触发A/B。",
        "- 当前样本不是随机缺失：2018/2019 两个早期年份完全缺 entry-day 分钟K，同时未覆盖样本仍包含右尾和压力关键日期。",
        "- 继续价值在补数或替代分钟源；若短期无法补数，只能把后续视觉/规则研究限制为 `2020+ covered subset` 的局部假设，并明确不能声称全周期成立。",
        "",
        "## 输出文件",
        "",
        f"- summary：`{SUMMARY_PATH.name}`",
        f"- coverage_by_year：`{COVERAGE_BY_YEAR_PATH.name}`",
        f"- coverage_by_product：`{COVERAGE_BY_PRODUCT_PATH.name}`",
        f"- coverage_by_direction：`{COVERAGE_BY_DIRECTION_PATH.name}`",
        f"- coverage_by_outcome：`{COVERAGE_BY_OUTCOME_PATH.name}`",
        f"- pnl_distribution：`{PNL_DISTRIBUTION_PATH.name}`",
        f"- top_missing_lots：`{TOP_MISSING_LOTS_PATH.name}`",
        f"- pressure_coverage_bias：`{PRESSURE_COVERAGE_BIAS_PATH.name}`",
        f"- chart：`{CHART_PATH.name}`",
        f"- decision：`{DECISION_PATH.name}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    lots = _prepare_lots()
    by_year = _coverage_by_year(lots)
    by_product = _aggregate_by(lots, "product")
    by_direction = _aggregate_by(lots, "direction")
    by_outcome = _coverage_by_outcome(lots)
    pnl_distribution = _pnl_distribution(lots)
    top_missing = _top_missing_lots(lots)
    pressure_bias = _pressure_coverage_bias(lots)
    summary = _summary_row(lots, by_year, pressure_bias)

    summary_frame = pd.DataFrame([summary])
    summary_frame.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    by_year.to_csv(COVERAGE_BY_YEAR_PATH, index=False, encoding="utf-8-sig")
    by_product.to_csv(COVERAGE_BY_PRODUCT_PATH, index=False, encoding="utf-8-sig")
    by_direction.to_csv(COVERAGE_BY_DIRECTION_PATH, index=False, encoding="utf-8-sig")
    by_outcome.to_csv(COVERAGE_BY_OUTCOME_PATH, index=False, encoding="utf-8-sig")
    pnl_distribution.to_csv(PNL_DISTRIBUTION_PATH, index=False, encoding="utf-8-sig")
    top_missing.to_csv(TOP_MISSING_LOTS_PATH, index=False, encoding="utf-8-sig")
    pressure_bias.to_csv(PRESSURE_COVERAGE_BIAS_PATH, index=False, encoding="utf-8-sig")
    _draw_chart(lots, by_year, by_product, pressure_bias, summary)

    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "decision": summary["decision"],
        "metrics": summary,
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "coverage_by_year": str(COVERAGE_BY_YEAR_PATH),
            "coverage_by_product": str(COVERAGE_BY_PRODUCT_PATH),
            "coverage_by_direction": str(COVERAGE_BY_DIRECTION_PATH),
            "coverage_by_outcome": str(COVERAGE_BY_OUTCOME_PATH),
            "pnl_distribution": str(PNL_DISTRIBUTION_PATH),
            "top_missing_lots": str(TOP_MISSING_LOTS_PATH),
            "pressure_coverage_bias": str(PRESSURE_COVERAGE_BIAS_PATH),
            "chart": str(CHART_PATH),
            "report": str(REPORT_PATH),
        },
        "allow_new_rule": False,
        "allow_engine": False,
        "allow_ab": False,
        "reason": (
            "Coverage is materially biased by year/right-tail/pressure-date gaps; "
            "continue data repair or restrict any next analysis to explicitly scoped covered subsets."
        ),
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(
        summary,
        by_year,
        by_product,
        by_direction,
        by_outcome,
        pnl_distribution,
        pressure_bias,
        top_missing,
    )

    print(json.dumps(_json_safe(summary), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
