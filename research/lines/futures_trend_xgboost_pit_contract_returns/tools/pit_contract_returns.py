"""Point-in-time daily futures return construction and coverage audit."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd


PASS_DECISION = "stage001_pit_contract_return_coverage_pass_ready_for_feature_design"
FAIL_DECISION = "stage001_pit_contract_return_coverage_fail_stop_no_features"


class ContractReturnError(RuntimeError):
    """Raised when the point-in-time return contract is violated."""


def match_contract_to_product(
    symbol: object,
    exchange: object,
    formal_products: Sequence[str],
) -> str | None:
    match = re.fullmatch(r"([A-Za-z]+)([0-9]{3,4})", str(symbol))
    if match is None:
        return None
    code, delivery = match.groups()
    if len(set(delivery)) == 1 and delivery[0] in {"8", "9"}:
        return None
    if not 1 <= int(delivery[-2:]) <= 12:
        return None

    exchange_text = str(exchange)
    matches = []
    for product in formal_products:
        product_code, separator, product_exchange = str(product).partition(".")
        if (
            separator
            and product_exchange == exchange_text
            and product_code.lower() == code.lower()
        ):
            matches.append(str(product))
    if len(matches) > 1:
        raise ContractReturnError("contract_product_match_ambiguous")
    return matches[0] if matches else None


def _normalise_bars(
    bars: pd.DataFrame,
    formal_products: Sequence[str],
) -> pd.DataFrame:
    required = {
        "datetime",
        "symbol",
        "exchange",
        "close_price",
        "open_interest",
        "volume",
    }
    if missing := sorted(required - set(bars.columns)):
        raise ContractReturnError(f"bar_columns_missing:{','.join(missing)}")
    products = [str(product) for product in formal_products]
    if not products or len(products) != len(set(products)):
        raise ContractReturnError("formal_products_invalid")

    frame = bars.loc[:, sorted(required)].copy()
    frame["date"] = pd.to_datetime(frame["datetime"], errors="raise").dt.normalize()
    for column in ["close_price", "open_interest", "volume"]:
        frame[column] = pd.to_numeric(frame[column], errors="raise").astype(float)
    if not np.isfinite(frame[["close_price", "open_interest", "volume"]].to_numpy(float)).all():
        raise ContractReturnError("bar_numeric_value_nonfinite")
    frame["product_vt_symbol"] = [
        match_contract_to_product(symbol, exchange, products)
        for symbol, exchange in zip(frame["symbol"], frame["exchange"], strict=True)
    ]
    frame = frame[frame["product_vt_symbol"].notna()].copy()
    frame["contract_vt_symbol"] = frame["symbol"].astype(str) + "." + frame["exchange"].astype(str)
    if frame.duplicated(["date", "contract_vt_symbol"]).any():
        raise ContractReturnError("bar_date_contract_duplicate")
    return frame.sort_values(
        ["product_vt_symbol", "date", "contract_vt_symbol"],
        kind="mergesort",
    ).reset_index(drop=True)


def build_lagged_oi_returns(
    bars: pd.DataFrame,
    formal_products: Sequence[str],
) -> pd.DataFrame:
    frame = _normalise_bars(bars, formal_products)
    rows: list[dict[str, Any]] = []
    for product in map(str, formal_products):
        product_bars = frame[frame["product_vt_symbol"].eq(product)].copy()
        dates = pd.DatetimeIndex(sorted(product_bars["date"].unique()))
        for selection_date, return_date in zip(dates[:-1], dates[1:], strict=True):
            lagged = product_bars[product_bars["date"].eq(selection_date)].copy()
            eligible = lagged[
                lagged["close_price"].gt(0.0)
                & lagged["open_interest"].gt(0.0)
                & lagged["volume"].ge(0.0)
            ].sort_values(
                ["open_interest", "volume", "contract_vt_symbol"],
                ascending=[False, False, True],
                kind="mergesort",
            )
            base: dict[str, Any] = {
                "product_vt_symbol": product,
                "selection_date": pd.Timestamp(selection_date),
                "return_date": pd.Timestamp(return_date),
                "selected_contract_vt": "",
                "eligible_contract_count": int(len(eligible)),
                "selection_open_interest": np.nan,
                "selection_volume": np.nan,
                "previous_close": np.nan,
                "current_close": np.nan,
                "product_return": np.nan,
                "status": "no_lagged_eligible_contract",
                "fallback_used": False,
                "cross_contract_price_used": False,
            }
            if eligible.empty:
                rows.append(base)
                continue

            selected = eligible.iloc[0]
            contract = str(selected["contract_vt_symbol"])
            base.update(
                {
                    "selected_contract_vt": contract,
                    "selection_open_interest": float(selected["open_interest"]),
                    "selection_volume": float(selected["volume"]),
                    "previous_close": float(selected["close_price"]),
                }
            )
            current = product_bars[
                product_bars["date"].eq(return_date)
                & product_bars["contract_vt_symbol"].eq(contract)
            ]
            if current.empty or float(current.iloc[0]["close_price"]) <= 0.0:
                base["status"] = "selected_contract_close_missing"
                rows.append(base)
                continue

            current_close = float(current.iloc[0]["close_price"])
            product_return = current_close / float(selected["close_price"]) - 1.0
            if not np.isfinite(product_return):
                raise ContractReturnError("product_return_nonfinite")
            base.update(
                {
                    "current_close": current_close,
                    "product_return": float(product_return),
                    "status": "ok",
                }
            )
            rows.append(base)
    return pd.DataFrame(rows)


def audit_feature_windows(
    base_panel: pd.DataFrame,
    formal_ranking: pd.DataFrame,
    product_returns: pd.DataFrame,
    *,
    window_days: int,
    top_rank_count: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if window_days <= 0 or top_rank_count <= 0:
        raise ContractReturnError("window_contract_invalid")
    for frame, required, prefix in [
        (base_panel, {"eval_date", "product_vt_symbol", "score_rank"}, "base_panel"),
        (formal_ranking, {"eval_date", "product_vt_symbol", "score_rank"}, "formal_ranking"),
        (
            product_returns,
            {
                "product_vt_symbol",
                "selection_date",
                "return_date",
                "product_return",
                "status",
            },
            "product_returns",
        ),
    ]:
        if missing := sorted(required - set(frame.columns)):
            raise ContractReturnError(f"{prefix}_columns_missing:{','.join(missing)}")

    base = base_panel.copy()
    ranking = formal_ranking.copy()
    returns = product_returns.copy()
    base["eval_date"] = pd.to_datetime(base["eval_date"], errors="raise").dt.normalize()
    ranking["eval_date"] = pd.to_datetime(ranking["eval_date"], errors="raise").dt.normalize()
    returns["selection_date"] = pd.to_datetime(returns["selection_date"], errors="raise").dt.normalize()
    returns["return_date"] = pd.to_datetime(returns["return_date"], errors="raise").dt.normalize()
    returns["product_return"] = pd.to_numeric(returns["product_return"], errors="coerce")
    if returns.duplicated(["return_date", "product_vt_symbol"]).any():
        raise ContractReturnError("product_return_date_product_duplicate")

    coverage_rows: list[dict[str, Any]] = []
    missing_rows: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []
    all_dates = pd.DatetimeIndex(sorted(returns["return_date"].unique()))
    for eval_date, month_base in base.groupby("eval_date", sort=True):
        month_ranking = ranking[ranking["eval_date"].eq(eval_date)].sort_values("score_rank")
        ranks = month_ranking["score_rank"].astype(int).tolist()
        if ranks != list(range(1, len(month_ranking) + 1)):
            raise ContractReturnError("formal_ranking_month_ranks_not_contiguous")
        top_products = month_ranking.head(top_rank_count)["product_vt_symbol"].astype(str).tolist()
        candidate_products = month_base.sort_values("score_rank")["product_vt_symbol"].astype(str).tolist()
        if set(top_products) & set(candidate_products):
            raise ContractReturnError("top_candidate_product_overlap")
        ranked_by_rank = dict(
            zip(month_ranking["score_rank"].astype(int), month_ranking["product_vt_symbol"].astype(str), strict=True)
        )
        for row in month_base.itertuples(index=False):
            if ranked_by_rank.get(int(row.score_rank)) != str(row.product_vt_symbol):
                raise ContractReturnError("base_panel_formal_ranking_identity_mismatch")

        eligible_dates = all_dates[all_dates <= eval_date]
        window_dates = eligible_dates[-window_days:]
        month_complete: dict[tuple[str, str], bool] = {}
        for role, products in [("top", top_products), ("candidate", candidate_products)]:
            for product in products:
                source = returns[
                    returns["return_date"].isin(window_dates)
                    & returns["product_vt_symbol"].eq(product)
                ].set_index("return_date")
                valid_count = 0
                for return_date in window_dates:
                    if return_date not in source.index:
                        status = "return_row_missing"
                        value = np.nan
                    else:
                        item = source.loc[return_date]
                        status = str(item["status"])
                        value = float(item["product_return"])
                    valid = status == "ok" and np.isfinite(value)
                    valid_count += int(valid)
                    if not valid:
                        missing_rows.append(
                            {
                                "eval_date": eval_date,
                                "return_date": return_date,
                                "product_vt_symbol": product,
                                "role": role,
                                "status": status,
                            }
                        )
                complete = len(window_dates) == window_days and valid_count == window_days
                month_complete[(role, product)] = complete
                coverage_rows.append(
                    {
                        "eval_date": eval_date,
                        "product_vt_symbol": product,
                        "role": role,
                        "valid_return_count": valid_count,
                        "required_return_count": window_days,
                        "window_complete": complete,
                    }
                )
        audit_rows.append(
            {
                "eval_date": eval_date,
                "window_start": window_dates.min() if len(window_dates) else pd.NaT,
                "window_end": window_dates.max() if len(window_dates) else pd.NaT,
                "window_date_count": int(len(window_dates)),
                "top_count": int(len(top_products)),
                "candidate_count": int(len(candidate_products)),
                "top_windows_complete": int(sum(month_complete[("top", product)] for product in top_products)),
                "candidate_windows_complete": int(
                    sum(month_complete[("candidate", product)] for product in candidate_products)
                ),
                "future_return_rows_used": 0,
            }
        )
    return pd.DataFrame(coverage_rows), pd.DataFrame(missing_rows), pd.DataFrame(audit_rows)


def assess_coverage(
    coverage: pd.DataFrame,
    missing: pd.DataFrame,
    audit: pd.DataFrame,
    product_returns: pd.DataFrame,
    *,
    expected_candidate_rows: int,
    window_days: int,
) -> dict[str, Any]:
    candidate = coverage[coverage["role"].eq("candidate")]
    top = coverage[coverage["role"].eq("top")]
    complete_candidate = int(candidate["window_complete"].astype(bool).sum())
    complete_top = int(top["window_complete"].astype(bool).sum())
    pit_violations = int(
        (pd.to_datetime(product_returns["selection_date"]) >= pd.to_datetime(product_returns["return_date"])).sum()
    )
    fallback_rows = int(product_returns.get("fallback_used", False).astype(bool).sum())
    cross_contract_rows = int(product_returns.get("cross_contract_price_used", False).astype(bool).sum())
    ok_nonfinite_rows = int(
        (
            product_returns["status"].eq("ok")
            & ~np.isfinite(pd.to_numeric(product_returns["product_return"], errors="coerce"))
        ).sum()
    )
    expected_top_rows = int(audit["top_count"].sum())
    gates = {
        "candidate_row_count": int(len(candidate)) == int(expected_candidate_rows),
        "candidate_windows_complete": complete_candidate == int(expected_candidate_rows),
        "top_windows_complete": complete_top == expected_top_rows,
        "window_dates_complete": bool(audit["window_date_count"].eq(window_days).all()),
        "missing_required_cells_zero": len(missing) == 0,
        "pit_violations_zero": pit_violations == 0,
        "fallback_rows_zero": fallback_rows == 0,
        "cross_contract_rows_zero": cross_contract_rows == 0,
        "ok_nonfinite_rows_zero": ok_nonfinite_rows == 0,
    }
    passed = all(gates.values())
    return {
        "decision": PASS_DECISION if passed else FAIL_DECISION,
        "all_gates_passed": bool(passed),
        "gates": gates,
        "candidate_rows": int(len(candidate)),
        "expected_candidate_rows": int(expected_candidate_rows),
        "complete_candidate_windows": complete_candidate,
        "complete_top_windows": complete_top,
        "expected_top_windows": expected_top_rows,
        "missing_required_cells": int(len(missing)),
        "pit_violations": pit_violations,
        "fallback_rows": fallback_rows,
        "cross_contract_rows": cross_contract_rows,
        "ok_nonfinite_rows": ok_nonfinite_rows,
    }
