"""Point-in-time coverage audit for concrete futures contract curves."""

from __future__ import annotations

import re
from typing import Any

import numpy as np
import pandas as pd


PASS_DECISION = "stage001_curve_coverage_pass_ready_for_feature_preregistration"
FAIL_DECISION = "stage001_curve_coverage_fail_stop_no_labels"


class CurveCoverageError(RuntimeError):
    """Raised when the frozen curve coverage contract cannot be evaluated."""


def _required_columns(frame: pd.DataFrame, columns: set[str], name: str) -> None:
    if missing := sorted(columns - set(frame.columns)):
        raise CurveCoverageError(f"{name}_columns_missing:{','.join(missing)}")


def _month_serial(value: pd.Timestamp) -> int:
    return int(value.year * 12 + value.month)


def infer_delivery_month(symbol: Any, exchange: Any, eval_date: Any) -> pd.Timestamp | pd.NaT:
    """Infer a concrete Chinese futures delivery month without future metadata."""
    text = str(symbol).strip()
    match = re.fullmatch(r"([A-Za-z]+)([0-9]{3,4})", text)
    if match is None:
        return pd.NaT
    digits = match.group(2)
    if len(set(digits)) == 1 and digits[0] in {"8", "9"}:
        return pd.NaT

    eval_ts = pd.Timestamp(eval_date).normalize()
    if pd.isna(eval_ts):
        return pd.NaT
    eval_month = pd.Timestamp(eval_ts.year, eval_ts.month, 1)
    month = int(digits[-2:])
    if not 1 <= month <= 12:
        return pd.NaT

    if len(digits) == 4:
        maturity = pd.Timestamp(2000 + int(digits[:2]), month, 1)
        month_distance = _month_serial(maturity) - _month_serial(eval_month)
        return maturity if 0 <= month_distance <= 48 else pd.NaT

    if str(exchange).strip().upper() != "CZCE":
        return pd.NaT
    year_digit = int(digits[0])
    candidates = [
        pd.Timestamp(decade + year_digit, month, 1)
        for decade in (2000, 2010, 2020, 2030, 2040)
    ]
    plausible = [
        candidate
        for candidate in candidates
        if 0 <= _month_serial(candidate) - _month_serial(eval_month) <= 48
    ]
    return plausible[0] if len(plausible) == 1 else pd.NaT


def normalise_ranked_panel(panel: pd.DataFrame) -> pd.DataFrame:
    required = {
        "eval_date",
        "product_vt_symbol",
        "pit_logistic_probability",
        "window_id",
        "a_rank",
        "role",
    }
    _required_columns(panel, required, "panel")
    frame = panel.loc[:, sorted(required)].copy()
    frame["eval_date"] = pd.to_datetime(frame["eval_date"], errors="raise").dt.normalize()
    frame["product_vt_symbol"] = frame["product_vt_symbol"].astype(str).str.strip()
    frame["window_id"] = frame["window_id"].astype(str).str.strip()
    frame["role"] = frame["role"].astype(str).str.strip()
    frame["a_rank"] = pd.to_numeric(frame["a_rank"], errors="raise").astype(int)
    frame["pit_logistic_probability"] = pd.to_numeric(
        frame["pit_logistic_probability"], errors="raise"
    ).astype(float)
    if not np.isfinite(frame["pit_logistic_probability"].to_numpy(float)).all():
        raise CurveCoverageError("panel_probability_nonfinite")
    if frame["product_vt_symbol"].eq("").any() or frame["window_id"].eq("").any():
        raise CurveCoverageError("panel_identity_empty")
    if frame.duplicated(["eval_date", "product_vt_symbol"]).any():
        raise CurveCoverageError("panel_eval_product_duplicate")
    if frame.duplicated(["eval_date", "a_rank"]).any():
        raise CurveCoverageError("panel_eval_rank_duplicate")
    if frame[["eval_date", "window_id"]].drop_duplicates().duplicated("eval_date").any():
        raise CurveCoverageError("panel_eval_window_duplicate")

    for _, month in frame.groupby("eval_date", sort=True):
        ranks = sorted(month["a_rank"].astype(int).tolist())
        if ranks != list(range(1, len(month) + 1)):
            raise CurveCoverageError("panel_rank_not_contiguous")
    return frame.sort_values(["eval_date", "a_rank"], kind="mergesort").reset_index(drop=True)


def _product_lookup(panel: pd.DataFrame) -> dict[tuple[str, str], str]:
    lookup: dict[tuple[str, str], str] = {}
    for product in sorted(panel["product_vt_symbol"].unique()):
        code, separator, exchange = str(product).partition(".")
        if not separator or not code or not exchange:
            raise CurveCoverageError(f"panel_product_invalid:{product}")
        key = (code.lower(), exchange.upper())
        if key in lookup and lookup[key] != product:
            raise CurveCoverageError("panel_product_mapping_ambiguous")
        lookup[key] = str(product)
    return lookup


def build_exact_curve_snapshots(
    panel: pd.DataFrame,
    bars: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Keep only exact-decision-date, active, concrete contracts."""
    ranked = normalise_ranked_panel(panel)
    required = {
        "symbol",
        "exchange",
        "datetime",
        "interval",
        "close_price",
        "open_interest",
        "volume",
    }
    _required_columns(bars, required, "bars")
    frame = bars.loc[:, sorted(required)].copy()
    frame["feature_date"] = pd.to_datetime(frame["datetime"], errors="raise").dt.normalize()
    frame["exchange"] = frame["exchange"].astype(str).str.strip().str.upper()
    frame["symbol"] = frame["symbol"].astype(str).str.strip()
    frame["interval"] = frame["interval"].astype(str).str.strip()
    frame = frame[
        frame["interval"].eq("d")
        & frame["feature_date"].isin(ranked["eval_date"].unique())
    ].copy()

    lookup = _product_lookup(ranked)
    product_values: list[str | None] = []
    symbol_matches: list[re.Match[str] | None] = []
    for symbol, exchange in zip(frame["symbol"], frame["exchange"], strict=True):
        match = re.fullmatch(r"([A-Za-z]+)([0-9]{3,4})", str(symbol))
        symbol_matches.append(match)
        product_values.append(
            lookup.get((match.group(1).lower(), str(exchange))) if match is not None else None
        )
    frame["product_vt_symbol"] = product_values
    frame = frame[frame["product_vt_symbol"].notna()].copy()
    frame["eval_date"] = frame["feature_date"]
    expected_pairs = ranked[["eval_date", "product_vt_symbol"]].drop_duplicates()
    frame = frame.merge(expected_pairs, on=["eval_date", "product_vt_symbol"], how="inner")
    frame["contract_vt_symbol"] = frame["symbol"] + "." + frame["exchange"]
    if frame.duplicated(["eval_date", "contract_vt_symbol"]).any():
        raise CurveCoverageError("contract_snapshot_duplicate")

    rejected_rows: list[dict[str, Any]] = []
    snapshot_rows: list[dict[str, Any]] = []
    for item in frame.itertuples(index=False):
        symbol = str(item.symbol)
        match = re.fullmatch(r"([A-Za-z]+)([0-9]{3,4})", symbol)
        digits = match.group(2) if match is not None else ""
        maturity = infer_delivery_month(symbol, item.exchange, item.eval_date)
        if pd.isna(maturity):
            reason = (
                "synthetic_contract"
                if digits and len(set(digits)) == 1 and digits[0] in {"8", "9"}
                else "invalid_contract_code_or_maturity"
            )
            rejected_rows.append(
                {
                    "eval_date": pd.Timestamp(item.eval_date),
                    "product_vt_symbol": str(item.product_vt_symbol),
                    "contract_vt_symbol": str(item.contract_vt_symbol),
                    "reason": reason,
                }
            )
            continue

        close_price = float(item.close_price)
        open_interest = float(item.open_interest)
        volume = float(item.volume)
        if not np.isfinite([close_price, open_interest, volume]).all():
            reason = "nonfinite_price_or_activity"
        elif close_price <= 0.0 or open_interest <= 0.0 or volume <= 0.0:
            reason = "nonpositive_price_or_activity"
        else:
            reason = ""
        if reason:
            rejected_rows.append(
                {
                    "eval_date": pd.Timestamp(item.eval_date),
                    "product_vt_symbol": str(item.product_vt_symbol),
                    "contract_vt_symbol": str(item.contract_vt_symbol),
                    "reason": reason,
                }
            )
            continue
        snapshot_rows.append(
            {
                "eval_date": pd.Timestamp(item.eval_date),
                "feature_date": pd.Timestamp(item.feature_date),
                "product_vt_symbol": str(item.product_vt_symbol),
                "contract_vt_symbol": str(item.contract_vt_symbol),
                "contract_maturity": pd.Timestamp(maturity),
                "close_price": close_price,
                "open_interest": open_interest,
                "volume": volume,
            }
        )

    snapshot_columns = [
        "eval_date",
        "feature_date",
        "product_vt_symbol",
        "contract_vt_symbol",
        "contract_maturity",
        "close_price",
        "open_interest",
        "volume",
    ]
    snapshots = pd.DataFrame(snapshot_rows, columns=snapshot_columns).sort_values(
        ["eval_date", "product_vt_symbol", "contract_maturity", "contract_vt_symbol"],
        kind="mergesort",
    ).reset_index(drop=True)
    if snapshots.duplicated(["eval_date", "product_vt_symbol", "contract_maturity"]).any():
        raise CurveCoverageError("delivery_month_duplicate")
    rejected = pd.DataFrame(
        rejected_rows,
        columns=["eval_date", "product_vt_symbol", "contract_vt_symbol", "reason"],
    ).sort_values(
        ["eval_date", "product_vt_symbol", "contract_vt_symbol"], kind="mergesort"
    ).reset_index(drop=True)
    return snapshots, rejected


def audit_curve_coverage(
    panel: pd.DataFrame,
    snapshots: pd.DataFrame,
    *,
    minimum_contracts: int,
) -> pd.DataFrame:
    if minimum_contracts < 2:
        raise CurveCoverageError("minimum_contracts_invalid")
    ranked = normalise_ranked_panel(panel)
    rows: list[dict[str, Any]] = []
    for item in ranked.itertuples(index=False):
        curve = snapshots[
            snapshots["eval_date"].eq(item.eval_date)
            & snapshots["product_vt_symbol"].eq(item.product_vt_symbol)
        ].sort_values(["contract_maturity", "contract_vt_symbol"], kind="mergesort")
        count = int(len(curve))
        exact_same_day = bool(count and curve["feature_date"].eq(item.eval_date).all())
        if count >= 2:
            front = pd.Timestamp(curve.iloc[0]["contract_maturity"])
            second = pd.Timestamp(curve.iloc[1]["contract_maturity"])
            front_next_gap = _month_serial(second) - _month_serial(front)
        else:
            front = pd.NaT
            second = pd.NaT
            front_next_gap = 0
        complete = count >= minimum_contracts and exact_same_day and front_next_gap > 0
        if count < minimum_contracts:
            status = "eligible_contract_count_below_minimum"
        elif not exact_same_day:
            status = "feature_date_not_exact_eval_date"
        elif front_next_gap <= 0:
            status = "front_next_month_gap_invalid"
        else:
            status = "ok"
        rows.append(
            {
                "eval_date": pd.Timestamp(item.eval_date),
                "product_vt_symbol": str(item.product_vt_symbol),
                "window_id": str(item.window_id),
                "a_rank": int(item.a_rank),
                "role": str(item.role),
                "eligible_contract_count": count,
                "front_contract_maturity": front,
                "second_contract_maturity": second,
                "front_next_month_gap": int(front_next_gap),
                "exact_same_day": exact_same_day,
                "curve_complete": bool(complete),
                "status": status,
                "fallback_used": False,
                "future_label_rows_read": 0,
            }
        )
    return pd.DataFrame(rows)


def assess_curve_coverage(
    panel: pd.DataFrame,
    snapshots: pd.DataFrame,
    rejected: pd.DataFrame,
    coverage: pd.DataFrame,
    *,
    expected_rows: int,
    expected_months: int,
    expected_products: int,
    minimum_contracts: int,
) -> dict[str, Any]:
    ranked = normalise_ranked_panel(panel)
    complete_rows = int(coverage["curve_complete"].astype(bool).sum())
    minimum_eligible = int(coverage["eligible_contract_count"].min()) if len(coverage) else 0
    pit_violations = int(
        (pd.to_datetime(snapshots["feature_date"]) > pd.to_datetime(snapshots["eval_date"])).sum()
    )
    same_day_mismatches = int(
        (pd.to_datetime(snapshots["feature_date"]) != pd.to_datetime(snapshots["eval_date"])).sum()
    )
    invalid_contract_rows = int(
        rejected["reason"].eq("invalid_contract_code_or_maturity").sum()
    ) if len(rejected) else 0
    nonpositive_rejections = int(
        rejected["reason"].isin(
            ["nonfinite_price_or_activity", "nonpositive_price_or_activity"]
        ).sum()
    ) if len(rejected) else 0
    gates = {
        "panel_row_count": len(ranked) == int(expected_rows),
        "panel_month_count": ranked["eval_date"].nunique() == int(expected_months),
        "panel_product_count": ranked["product_vt_symbol"].nunique() == int(expected_products),
        "coverage_row_count": len(coverage) == int(expected_rows),
        "all_panel_rows_complete": complete_rows == int(expected_rows),
        "minimum_contract_count": minimum_eligible >= int(minimum_contracts),
        "exact_same_day": same_day_mismatches == 0,
        "pit_violation_rows_zero": pit_violations == 0,
        "invalid_contract_rows_zero": invalid_contract_rows == 0,
        "front_next_gap_positive": bool(coverage["front_next_month_gap"].gt(0).all()),
        "fallback_rows_zero": bool(~coverage["fallback_used"].astype(bool).any()),
        "future_label_rows_read_zero": int(coverage["future_label_rows_read"].sum()) == 0,
    }
    passed = bool(all(gates.values()))
    return {
        "decision": PASS_DECISION if passed else FAIL_DECISION,
        "all_gates_passed": passed,
        "gates": gates,
        "panel_rows": int(len(ranked)),
        "oos_months": int(ranked["eval_date"].nunique()),
        "products": int(ranked["product_vt_symbol"].nunique()),
        "curve_snapshot_rows": int(len(snapshots)),
        "complete_rows": complete_rows,
        "incomplete_rows": int(len(coverage) - complete_rows),
        "minimum_eligible_contracts": minimum_eligible,
        "median_eligible_contracts": float(coverage["eligible_contract_count"].median()),
        "maximum_eligible_contracts": int(coverage["eligible_contract_count"].max()),
        "pit_violation_rows": pit_violations,
        "same_day_mismatch_rows": same_day_mismatches,
        "invalid_contract_rows": invalid_contract_rows,
        "synthetic_contract_rows_rejected": int(
            rejected["reason"].eq("synthetic_contract").sum()
        ) if len(rejected) else 0,
        "nonpositive_contract_rows_rejected": nonpositive_rejections,
        "fallback_rows": int(coverage["fallback_used"].astype(bool).sum()),
        "future_label_rows_read": int(coverage["future_label_rows_read"].sum()),
    }
