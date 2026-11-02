from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import analyze_qmt_roll_stage752_theoretical_winner_kline_atlas as s752


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
LINE_ID = "futures_trend_winner_trade_forensics"
SOURCE_CLOSED_LOTS = s752.SOURCE_CLOSED_LOTS

OUTPUT_PREFIX = "qmt_roll_stage754_entry_oi_change_winner_loser"
MODEL_TAG = "stage754_entry_oi_change_winner_loser_v1"
ENRICHED_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_enriched_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
GROUP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_group_stats_{MODEL_TAG}.csv"
YEAR_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_stats_{MODEL_TAG}.csv"
FEATURE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_quality_{MODEL_TAG}.csv"
DIRECTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_direction_stats_{MODEL_TAG}.csv"
TOP_CONTRAST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_top_contrast_{MODEL_TAG}.csv"


def _safe_float(value: Any) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return float("nan")
    if np.isnan(result) or np.isinf(result):
        return float("nan")
    return result


def _entry_window_features(row: pd.Series) -> dict[str, Any]:
    bars = s752._read_contract_bars(row["vt_symbol"])
    empty = {
        "oi_available": 0,
        "entry_bar_index": np.nan,
        "entry_close": np.nan,
        "entry_close_prev1": np.nan,
        "entry_close_prev2": np.nan,
        "entry_oi": np.nan,
        "entry_oi_prev1": np.nan,
        "entry_oi_prev2": np.nan,
        "entry_oi_chg1": np.nan,
        "entry_oi_chg2": np.nan,
        "entry_oi_chg1_pct": np.nan,
        "entry_oi_chg2_pct": np.nan,
        "entry_oi_gt_prev1": np.nan,
        "entry_oi_gt_prev2": np.nan,
        "prev1_oi_gt_prev2": np.nan,
        "recent2_any_oi_up": np.nan,
        "recent2_both_oi_up": np.nan,
        "recent2_net_oi_up": np.nan,
        "entry_price_direction_aligned": np.nan,
        "entry_oi_price_confirm": np.nan,
    }
    if bars.empty or "close_oi" not in bars.columns:
        return empty
    entry_idx = s752._event_index(bars, pd.Timestamp(row["entry_date"]))
    if entry_idx < 2:
        return empty | {"entry_bar_index": entry_idx}

    d0 = bars.iloc[entry_idx]
    d1 = bars.iloc[entry_idx - 1]
    d2 = bars.iloc[entry_idx - 2]
    oi0 = _safe_float(d0.get("close_oi"))
    oi1 = _safe_float(d1.get("close_oi"))
    oi2 = _safe_float(d2.get("close_oi"))
    close0 = _safe_float(d0.get("close"))
    close1 = _safe_float(d1.get("close"))
    close2 = _safe_float(d2.get("close"))
    if np.isnan(oi0) or np.isnan(oi1) or np.isnan(oi2) or oi1 <= 0 or oi2 <= 0:
        return empty | {
            "entry_bar_index": entry_idx,
            "entry_close": close0,
            "entry_close_prev1": close1,
            "entry_close_prev2": close2,
            "entry_oi": oi0,
            "entry_oi_prev1": oi1,
            "entry_oi_prev2": oi2,
        }

    chg1 = oi0 - oi1
    chg2 = oi0 - oi2
    gt1 = oi0 > oi1
    gt2 = oi0 > oi2
    prev_gt = oi1 > oi2
    direction = str(row.get("direction", ""))
    price_aligned = (
        close0 > close1
        if direction == "long"
        else close0 < close1
        if direction == "short"
        else False
    )
    return {
        "oi_available": 1,
        "entry_bar_index": entry_idx,
        "entry_close": close0,
        "entry_close_prev1": close1,
        "entry_close_prev2": close2,
        "entry_oi": oi0,
        "entry_oi_prev1": oi1,
        "entry_oi_prev2": oi2,
        "entry_oi_chg1": chg1,
        "entry_oi_chg2": chg2,
        "entry_oi_chg1_pct": chg1 / oi1 * 100.0,
        "entry_oi_chg2_pct": chg2 / oi2 * 100.0,
        "entry_oi_gt_prev1": int(gt1),
        "entry_oi_gt_prev2": int(gt2),
        "prev1_oi_gt_prev2": int(prev_gt),
        "recent2_any_oi_up": int(gt1 or prev_gt),
        "recent2_both_oi_up": int(gt1 and prev_gt),
        "recent2_net_oi_up": int(gt2),
        "entry_price_direction_aligned": int(price_aligned),
        "entry_oi_price_confirm": int(gt1 and price_aligned),
    }


def _rate(frame: pd.DataFrame, column: str) -> float:
    values = pd.to_numeric(frame[column], errors="coerce").dropna()
    if values.empty:
        return np.nan
    return float(values.mean() * 100.0)


def _mean(frame: pd.DataFrame, column: str) -> float:
    values = pd.to_numeric(frame[column], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if values.empty:
        return np.nan
    return float(values.mean())


def _median(frame: pd.DataFrame, column: str) -> float:
    values = pd.to_numeric(frame[column], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if values.empty:
        return np.nan
    return float(values.median())


def _group_stats(data: pd.DataFrame, outcome_col: str, label: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    valid = data[data["oi_available"].eq(1)].copy()
    for outcome in ["profit", "loss"]:
        group = valid[valid[outcome_col].eq(outcome)].copy()
        rows.append(
            {
                "outcome_basis": label,
                "outcome": outcome,
                "rows": int(len(group)),
                "products": int(group["product"].nunique()) if "product" in group.columns else int(group["vt_symbol"].nunique()),
                "years": int(pd.to_datetime(group["entry_date"]).dt.year.nunique()) if not group.empty else 0,
                "entry_oi_gt_prev1_rate_pct": _rate(group, "entry_oi_gt_prev1"),
                "entry_oi_gt_prev2_rate_pct": _rate(group, "entry_oi_gt_prev2"),
                "recent2_any_oi_up_rate_pct": _rate(group, "recent2_any_oi_up"),
                "recent2_both_oi_up_rate_pct": _rate(group, "recent2_both_oi_up"),
                "recent2_net_oi_up_rate_pct": _rate(group, "recent2_net_oi_up"),
                "entry_oi_price_confirm_rate_pct": _rate(group, "entry_oi_price_confirm"),
                "entry_oi_chg1_pct_mean": _mean(group, "entry_oi_chg1_pct"),
                "entry_oi_chg1_pct_median": _median(group, "entry_oi_chg1_pct"),
                "entry_oi_chg2_pct_mean": _mean(group, "entry_oi_chg2_pct"),
                "entry_oi_chg2_pct_median": _median(group, "entry_oi_chg2_pct"),
                "theory_return_pct_mean": _mean(group, "theory_return_pct"),
                "r_multiple_mean": _mean(group, "r_multiple"),
            }
        )
    return rows


def _feature_quality(data: pd.DataFrame) -> pd.DataFrame:
    valid = data[data["oi_available"].eq(1)].copy()
    feature_cols = [
        "entry_oi_gt_prev1",
        "entry_oi_gt_prev2",
        "recent2_any_oi_up",
        "recent2_both_oi_up",
        "recent2_net_oi_up",
        "entry_oi_price_confirm",
    ]
    base_profit = float(valid["theory_outcome"].eq("profit").mean() * 100.0) if len(valid) else np.nan
    rows: list[dict[str, Any]] = []
    for feature in feature_cols:
        subset = valid[pd.to_numeric(valid[feature], errors="coerce").eq(1)].copy()
        complement = valid[pd.to_numeric(valid[feature], errors="coerce").eq(0)].copy()
        rows.append(
            {
                "feature": feature,
                "rows": int(len(subset)),
                "share_pct": float(len(subset) / len(valid) * 100.0) if len(valid) else np.nan,
                "profit_rate_pct": float(subset["theory_outcome"].eq("profit").mean() * 100.0) if len(subset) else np.nan,
                "profit_rate_lift_pp": (
                    float(subset["theory_outcome"].eq("profit").mean() * 100.0 - base_profit)
                    if len(subset)
                    else np.nan
                ),
                "avg_theory_return_pct": _mean(subset, "theory_return_pct"),
                "median_theory_return_pct": _median(subset, "theory_return_pct"),
                "complement_rows": int(len(complement)),
                "complement_profit_rate_pct": (
                    float(complement["theory_outcome"].eq("profit").mean() * 100.0)
                    if len(complement)
                    else np.nan
                ),
                "complement_avg_theory_return_pct": _mean(complement, "theory_return_pct"),
                "years": int(pd.to_datetime(subset["entry_date"]).dt.year.nunique()) if len(subset) else 0,
                "products": int(subset["product"].nunique()) if "product" in subset.columns and len(subset) else 0,
                "max_product_share_pct": (
                    float(subset["product"].value_counts(normalize=True).iloc[0] * 100.0)
                    if "product" in subset.columns and len(subset)
                    else np.nan
                ),
            }
        )
    return pd.DataFrame(rows)


def _year_stats(data: pd.DataFrame) -> pd.DataFrame:
    valid = data[data["oi_available"].eq(1)].copy()
    valid["entry_year"] = pd.to_datetime(valid["entry_date"]).dt.year
    rows: list[dict[str, Any]] = []
    for year, group in valid.groupby("entry_year"):
        profit = group[group["theory_outcome"].eq("profit")]
        loss = group[group["theory_outcome"].eq("loss")]
        rows.append(
            {
                "entry_year": int(year),
                "rows": int(len(group)),
                "profit_rows": int(len(profit)),
                "loss_rows": int(len(loss)),
                "profit_entry_oi_gt_prev1_rate_pct": _rate(profit, "entry_oi_gt_prev1"),
                "loss_entry_oi_gt_prev1_rate_pct": _rate(loss, "entry_oi_gt_prev1"),
                "diff_profit_minus_loss_entry_oi_gt_prev1_pp": _rate(profit, "entry_oi_gt_prev1") - _rate(loss, "entry_oi_gt_prev1"),
                "profit_recent2_any_oi_up_rate_pct": _rate(profit, "recent2_any_oi_up"),
                "loss_recent2_any_oi_up_rate_pct": _rate(loss, "recent2_any_oi_up"),
                "diff_profit_minus_loss_recent2_any_pp": _rate(profit, "recent2_any_oi_up") - _rate(loss, "recent2_any_oi_up"),
            }
        )
    return pd.DataFrame(rows)


def _direction_stats(data: pd.DataFrame) -> pd.DataFrame:
    valid = data[data["oi_available"].eq(1)].copy()
    rows: list[dict[str, Any]] = []
    for direction, direction_group in valid.groupby("direction"):
        for outcome in ["profit", "loss"]:
            group = direction_group[direction_group["theory_outcome"].eq(outcome)].copy()
            rows.append(
                {
                    "direction": direction,
                    "outcome": outcome,
                    "rows": int(len(group)),
                    "entry_oi_gt_prev1_rate_pct": _rate(group, "entry_oi_gt_prev1"),
                    "entry_oi_gt_prev2_rate_pct": _rate(group, "entry_oi_gt_prev2"),
                    "recent2_any_oi_up_rate_pct": _rate(group, "recent2_any_oi_up"),
                    "recent2_both_oi_up_rate_pct": _rate(group, "recent2_both_oi_up"),
                    "entry_oi_price_confirm_rate_pct": _rate(group, "entry_oi_price_confirm"),
                    "entry_oi_chg1_pct_median": _median(group, "entry_oi_chg1_pct"),
                    "theory_return_pct_mean": _mean(group, "theory_return_pct"),
                }
            )
    return pd.DataFrame(rows)


def _top_contrast(data: pd.DataFrame) -> pd.DataFrame:
    valid = data[data["oi_available"].eq(1)].copy()
    profit = valid[valid["theory_return_pct"].gt(0.0)].sort_values("theory_return_pct", ascending=False)
    loss = valid[valid["theory_return_pct"].lt(0.0)].sort_values("theory_return_pct")
    rows: list[dict[str, Any]] = []
    for target in [29, 50, 100]:
        for group_name, group in [("top_profit", profit.head(target)), ("worst_loss", loss.head(target))]:
            rows.append(
                {
                    "n_target": target,
                    "group": group_name,
                    "rows": int(len(group)),
                    "entry_oi_gt_prev1_rate_pct": _rate(group, "entry_oi_gt_prev1"),
                    "entry_oi_gt_prev2_rate_pct": _rate(group, "entry_oi_gt_prev2"),
                    "recent2_any_oi_up_rate_pct": _rate(group, "recent2_any_oi_up"),
                    "recent2_both_oi_up_rate_pct": _rate(group, "recent2_both_oi_up"),
                    "entry_oi_price_confirm_rate_pct": _rate(group, "entry_oi_price_confirm"),
                    "entry_oi_chg1_pct_median": _median(group, "entry_oi_chg1_pct"),
                    "entry_oi_chg2_pct_median": _median(group, "entry_oi_chg2_pct"),
                    "theory_return_pct_mean": _mean(group, "theory_return_pct"),
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    lots = pd.read_csv(SOURCE_CLOSED_LOTS)
    lots["entry_date"] = pd.to_datetime(lots["entry_date"], errors="coerce").dt.normalize()
    lots["exit_date"] = pd.to_datetime(lots["exit_date"], errors="coerce").dt.normalize()
    lots["entry_price"] = pd.to_numeric(lots["entry_price"], errors="coerce")
    lots["exit_price"] = pd.to_numeric(lots["exit_price"], errors="coerce")
    direction_sign = np.where(lots["direction"].astype(str).eq("long"), 1.0, -1.0)
    lots["theory_return_pct"] = (
        direction_sign * (lots["exit_price"] - lots["entry_price"]) / lots["entry_price"] * 100.0
    )
    lots["theory_outcome"] = np.where(
        lots["theory_return_pct"].gt(0),
        "profit",
        np.where(lots["theory_return_pct"].lt(0), "loss", "flat"),
    )
    lots["realized_outcome"] = np.where(
        pd.to_numeric(lots["realized_pnl"], errors="coerce").gt(0),
        "profit",
        np.where(pd.to_numeric(lots["realized_pnl"], errors="coerce").lt(0), "loss", "flat"),
    )

    feature_rows = [_entry_window_features(row) for _, row in lots.iterrows()]
    enriched = pd.concat([lots.reset_index(drop=True), pd.DataFrame(feature_rows)], axis=1)
    enriched.to_csv(ENRICHED_PATH, index=False, encoding="utf-8-sig")

    group = pd.DataFrame(
        _group_stats(enriched, "theory_outcome", "theory_return")
        + _group_stats(enriched, "realized_outcome", "realized_pnl")
    )
    group.to_csv(GROUP_PATH, index=False, encoding="utf-8-sig")

    year_stats = _year_stats(enriched)
    year_stats.to_csv(YEAR_PATH, index=False, encoding="utf-8-sig")

    feature_quality = _feature_quality(enriched)
    feature_quality.to_csv(FEATURE_PATH, index=False, encoding="utf-8-sig")

    direction_stats = _direction_stats(enriched)
    direction_stats.to_csv(DIRECTION_PATH, index=False, encoding="utf-8-sig")

    top_contrast = _top_contrast(enriched)
    top_contrast.to_csv(TOP_CONTRAST_PATH, index=False, encoding="utf-8-sig")

    summary = pd.DataFrame(
        [
            {
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "source_closed_lots": str(SOURCE_CLOSED_LOTS),
                "total_lots": int(len(enriched)),
                "oi_available_lots": int(enriched["oi_available"].sum()),
                "oi_missing_lots": int(len(enriched) - enriched["oi_available"].sum()),
                "theory_profit_lots": int(enriched["theory_outcome"].eq("profit").sum()),
                "theory_loss_lots": int(enriched["theory_outcome"].eq("loss").sum()),
                "theory_profit_oi_available": int(
                    enriched[enriched["theory_outcome"].eq("profit")]["oi_available"].sum()
                ),
                "theory_loss_oi_available": int(
                    enriched[enriched["theory_outcome"].eq("loss")]["oi_available"].sum()
                ),
                "entry_oi_gt_prev1_profit_minus_loss_pp": float(
                    group[
                        (group["outcome_basis"].eq("theory_return")) & (group["outcome"].eq("profit"))
                    ]["entry_oi_gt_prev1_rate_pct"].iloc[0]
                    - group[
                        (group["outcome_basis"].eq("theory_return")) & (group["outcome"].eq("loss"))
                    ]["entry_oi_gt_prev1_rate_pct"].iloc[0]
                ),
                "recent2_any_oi_up_profit_minus_loss_pp": float(
                    group[
                        (group["outcome_basis"].eq("theory_return")) & (group["outcome"].eq("profit"))
                    ]["recent2_any_oi_up_rate_pct"].iloc[0]
                    - group[
                        (group["outcome_basis"].eq("theory_return")) & (group["outcome"].eq("loss"))
                    ]["recent2_any_oi_up_rate_pct"].iloc[0]
                ),
                "decision": "entry_oi_change_readonly_validation",
                "enriched_path": str(ENRICHED_PATH),
                "group_path": str(GROUP_PATH),
                "feature_path": str(FEATURE_PATH),
                "year_path": str(YEAR_PATH),
                "direction_path": str(DIRECTION_PATH),
                "top_contrast_path": str(TOP_CONTRAST_PATH),
            }
        ]
    )
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")

    print("SUMMARY")
    print(summary.to_string(index=False))
    print("\nGROUP_STATS")
    print(group.to_string(index=False))
    print("\nFEATURE_QUALITY")
    print(feature_quality.to_string(index=False))
    print("\nYEAR_STATS")
    print(year_stats.to_string(index=False))
    print("\nDIRECTION_STATS")
    print(direction_stats.to_string(index=False))
    print("\nTOP_CONTRAST")
    print(top_contrast.to_string(index=False))


if __name__ == "__main__":
    main()
