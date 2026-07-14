from __future__ import annotations

import hashlib
from io import StringIO
import json
import math
import os
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_ai_rank_year_jackknife_qualification"
STAGE_ID = "stage001_year_jackknife_qualification"
LINE_DIR = ROOT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / STAGE_ID

UNIVERSE_PATH = (
    ROOT_DIR
    / "examples"
    / "portfolio_backtesting"
    / "backtest_outputs"
    / "qmt_roll_full_market_tradable_universe_eligible_full_market_tradable_universe_v1.csv"
)
OLD_FEATURES_PATH = (
    ROOT_DIR
    / "examples"
    / "portfolio_backtesting"
    / "backtest_outputs"
    / "qmt_roll_ai_product_suitability_full_market_walkforward_samples_"
    "product_suitability_full_market_wf_v1.csv"
)
CALENDAR_PATH = (
    ROOT_DIR
    / "examples"
    / "portfolio_backtesting"
    / "backtest_outputs"
    / "qmt_roll_stage167_c9_live_15w_multiperiod_ai_audit_curves_"
    "stage167_c9_live_15w_multiperiod_ai_audit_v1.csv"
)
BASE_PANEL_PATH = (
    ROOT_DIR
    / "research"
    / "lines"
    / "futures_trend_full_market_ai_filter_002risk"
    / "outputs"
    / "stage001_full_market_pit_ai_risk002_engine"
    / "full_market_ai002_stage001_full_market_pit_ai_risk002_engine_feature_panel_"
    "stage001_full_market_pit_ai_risk002_engine_v2_rankfix.csv.gz"
)
BASE_TOOL_PATH = (
    ROOT_DIR
    / "research"
    / "lines"
    / "futures_trend_full_market_ai_filter_002risk"
    / "tools"
    / "stage001_full_market_pit_ai_risk002_engine.py"
)
DAILY_DIR = (
    ROOT_DIR
    / "research"
    / "lines"
    / "futures_trend_rebuilt_c9_15w_v2_optimization"
    / "outputs"
    / "stage124_full_market_single_product_c9_replay"
    / "daily_by_product"
)

EXPECTED_UNIVERSE_SHA256 = "7d97dd4c112721a577eb89c4007606fc444fcc16173f1c11a9538a73490c2bac"
EXPECTED_OLD_FEATURES_SHA256 = "fc0b62d42c0c8551b241bb8dabd15373fa3acec354c10cf8d72ef265b352c83b"
EXPECTED_CALENDAR_SHA256 = "72130cbb9260973bdfda6bf3119503a242db451516fbb7472a6165134ac379fd"
EXPECTED_BASE_PANEL_SHA256 = "dccd393bed6509a42f8642445313432a00b656fd599ee491da08877c1c4a5efa"
EXPECTED_BASE_TOOL_SHA256 = "f1164633ec925d9c97ee68ceccbb0ead76b78fd7c44a2c0a8511b7256d1921a9"
EXPECTED_DAILY_MANIFEST_SHA256 = "6827ebbae5fa395ab96f4b3d8d9f533210293fb082ebe6c95607ca400dcddb0d"
EXPECTED_UNIVERSE_COUNT = 57
EXPECTED_DAILY_FILE_COUNT = 57
EXPECTED_DAILY_ROW_COUNT = 73_251
EXPECTED_BASE_PANEL_ROW_COUNT = 4_446
EXPECTED_BASE_EVAL_COUNT = 78
EXPECTED_BASE_SELECTED_COUNT = 608

TOP_N = 8
ALL_CYCLE_WEIGHT = 0.24
QUALIFICATION_START = pd.Timestamp("2022-01-01")
HORIZON_DAYS = 60
MIN_COMPLETE_MONTHS = 42
MIN_SWAP_MONTHS = 24
MIN_SWAPS_PER_ACTIVE_YEAR = 3
MIN_POSITIVE_YEARS = 4
MAX_BEST_YEAR_POSITIVE_EDGE_SHARE = 0.60


class IntegrityError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    if value is None:
        return None
    try:
        return None if pd.isna(value) else value
    except (TypeError, ValueError):
        return value


def _atomic_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_bytes(payload)
    os.replace(temporary, path)


def _atomic_json(path: Path, payload: Any) -> None:
    data = (
        json.dumps(_json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    ).encode("utf-8")
    _atomic_bytes(path, data)


def _csv_bytes(frame: pd.DataFrame) -> bytes:
    buffer = StringIO()
    frame.to_csv(buffer, index=False, lineterminator="\n")
    return buffer.getvalue().encode("utf-8")


def _atomic_csv(path: Path, frame: pd.DataFrame) -> None:
    _atomic_bytes(path, _csv_bytes(frame))


def rank_pct(values: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan)
    if numeric.notna().sum() <= 1:
        return pd.Series(0.5, index=values.index, dtype="float64")
    filled = numeric.fillna(numeric.median())
    return filled.rank(method="average", pct=True, ascending=True).astype("float64")


def _slug(product_vt_symbol: str) -> str:
    return str(product_vt_symbol).replace(".", "_").replace("/", "_")


def build_daily_manifest(directory: Path = DAILY_DIR) -> tuple[pd.DataFrame, str]:
    rows: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*_daily.csv.gz"), key=lambda item: item.name):
        rows.append(
            {
                "file": path.name,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    manifest = pd.DataFrame(rows, columns=["file", "bytes", "sha256"])
    canonical = "".join(
        f"{row['file']},{int(row['bytes'])},{row['sha256']}\n"
        for row in manifest.to_dict("records")
    ).encode("utf-8")
    return manifest, hashlib.sha256(canonical).hexdigest()


def load_base_panel(path: Path = BASE_PANEL_PATH) -> tuple[pd.DataFrame, dict[str, Any]]:
    frame = pd.read_csv(path)
    required = {
        "eval_date",
        "product_vt_symbol",
        "data_available",
        "cumulative_net_pnl_to_date",
        "rank_all_cycle_profit",
        "score_before_history_gate",
        "score",
        "selected_topn",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise IntegrityError(f"base panel missing columns: {missing}")
    frame["eval_date"] = pd.to_datetime(frame["eval_date"], errors="raise").dt.normalize()
    frame["product_vt_symbol"] = frame["product_vt_symbol"].astype(str)
    frame.sort_values(["eval_date", "product_vt_symbol"], inplace=True, kind="mergesort")
    frame.reset_index(drop=True, inplace=True)
    duplicate_rows = int(frame.duplicated(["eval_date", "product_vt_symbol"], keep=False).sum())
    source_hash = sha256_file(path)
    audit = {
        "base_panel_path": str(path),
        "base_panel_sha256": source_hash,
        "base_panel_hash_ok": source_hash == EXPECTED_BASE_PANEL_SHA256,
        "base_panel_rows": int(len(frame)),
        "base_panel_row_count_ok": len(frame) == EXPECTED_BASE_PANEL_ROW_COUNT,
        "base_eval_count": int(frame["eval_date"].nunique()),
        "base_eval_count_ok": frame["eval_date"].nunique() == EXPECTED_BASE_EVAL_COUNT,
        "base_product_count": int(frame["product_vt_symbol"].nunique()),
        "base_product_count_ok": frame["product_vt_symbol"].nunique() == EXPECTED_UNIVERSE_COUNT,
        "base_selected_count": int(pd.to_numeric(frame["selected_topn"], errors="coerce").fillna(0).sum()),
        "base_selected_count_ok": int(pd.to_numeric(frame["selected_topn"], errors="coerce").fillna(0).sum())
        == EXPECTED_BASE_SELECTED_COUNT,
        "base_duplicate_key_rows": duplicate_rows,
    }
    return frame, audit


def load_global_dates(path: Path = CALENDAR_PATH) -> tuple[pd.DatetimeIndex, dict[str, Any]]:
    frame = pd.read_csv(path, usecols=["date", "requested_start_month"])
    frame = frame[frame["requested_start_month"].astype(str).eq("2020-01")].copy()
    dates = pd.to_datetime(frame["date"], format="mixed", errors="raise").dt.normalize()
    dates = pd.DatetimeIndex(sorted(dates.unique()))
    source_hash = sha256_file(path)
    return dates, {
        "calendar_path": str(path),
        "calendar_sha256": source_hash,
        "calendar_hash_ok": source_hash == EXPECTED_CALENDAR_SHA256,
        "global_date_count": int(len(dates)),
        "global_first_date": dates.min().date().isoformat(),
        "global_last_date": dates.max().date().isoformat(),
    }


def load_daily_by_product(
    products: Iterable[str], directory: Path = DAILY_DIR
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame, dict[str, Any]]:
    daily_manifest, manifest_hash = build_daily_manifest(directory)
    result: dict[str, pd.DataFrame] = {}
    audit_rows: list[dict[str, Any]] = []
    total_rows = 0
    for product in sorted(set(str(item) for item in products)):
        path = directory / f"{_slug(product)}_daily.csv.gz"
        if not path.is_file():
            audit_rows.append(
                {
                    "product_vt_symbol": product,
                    "path": str(path),
                    "rows": 0,
                    "duplicate_date_rows": 0,
                    "first_date": "",
                    "last_date": "",
                    "status": "missing",
                }
            )
            result[product] = pd.DataFrame(columns=["date", "net_pnl"])
            continue
        frame = pd.read_csv(path, usecols=lambda column: column in {"date", "net_pnl"})
        if set(frame.columns) != {"date", "net_pnl"}:
            raise IntegrityError(f"daily schema mismatch: {path}")
        frame["date"] = pd.to_datetime(frame["date"], errors="raise").dt.normalize()
        frame["net_pnl"] = pd.to_numeric(frame["net_pnl"], errors="coerce")
        duplicate_rows = int(frame.duplicated(["date"], keep=False).sum())
        nonfinite = int((~np.isfinite(frame["net_pnl"].to_numpy(dtype=float))).sum())
        if duplicate_rows or nonfinite:
            raise IntegrityError(
                f"daily integrity failed for {product}: duplicates={duplicate_rows}, nonfinite={nonfinite}"
            )
        frame.sort_values("date", inplace=True, kind="mergesort")
        frame.reset_index(drop=True, inplace=True)
        result[product] = frame
        total_rows += len(frame)
        audit_rows.append(
            {
                "product_vt_symbol": product,
                "path": str(path),
                "rows": int(len(frame)),
                "duplicate_date_rows": duplicate_rows,
                "first_date": frame["date"].min().date().isoformat() if len(frame) else "",
                "last_date": frame["date"].max().date().isoformat() if len(frame) else "",
                "status": "ok",
            }
        )
    audit = {
        "daily_file_count": int(len(daily_manifest)),
        "daily_file_count_ok": len(daily_manifest) == EXPECTED_DAILY_FILE_COUNT,
        "daily_manifest_sha256": manifest_hash,
        "daily_manifest_hash_ok": manifest_hash == EXPECTED_DAILY_MANIFEST_SHA256,
        "loaded_product_count": int(len(result)),
        "loaded_product_count_ok": len(result) == EXPECTED_UNIVERSE_COUNT,
        "daily_row_count": int(total_rows),
        "daily_row_count_ok": total_rows == EXPECTED_DAILY_ROW_COUNT,
    }
    return result, pd.DataFrame(audit_rows), audit


def build_annual_pnl(daily_by_product: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for product, frame in daily_by_product.items():
        if frame.empty:
            continue
        data = frame.copy()
        data["year"] = data["date"].dt.year.astype(int)
        grouped = data.groupby("year", as_index=False)["net_pnl"].sum()
        grouped["product_vt_symbol"] = product
        rows.append(grouped[["product_vt_symbol", "year", "net_pnl"]])
    if not rows:
        return pd.DataFrame(columns=["product_vt_symbol", "year", "net_pnl"])
    return pd.concat(rows, ignore_index=True).sort_values(
        ["product_vt_symbol", "year"], kind="mergesort"
    ).reset_index(drop=True)


def build_variant_ranking(
    month: pd.DataFrame,
    *,
    annual_pnl: pd.DataFrame,
    omitted_year: int | None,
    top_n: int = TOP_N,
) -> pd.DataFrame:
    eval_dates = (
        pd.to_datetime(month["eval_date"], errors="raise").dt.normalize().unique()
    )
    if len(eval_dates) != 1:
        raise IntegrityError("variant ranking requires exactly one eval_date")
    eval_date = pd.Timestamp(eval_dates[0]).normalize()
    if omitted_year is not None and int(omitted_year) >= int(eval_date.year):
        raise IntegrityError("omitted year must be a completed year before eval year")
    data = month.copy()
    data["product_vt_symbol"] = data["product_vt_symbol"].astype(str)
    data.sort_values("product_vt_symbol", inplace=True, kind="mergesort")
    data.reset_index(drop=True, inplace=True)
    data["cumulative_net_pnl_variant"] = pd.to_numeric(
        data["cumulative_net_pnl_to_date"], errors="coerce"
    )
    if omitted_year is not None:
        omitted = annual_pnl.copy()
        if "eval_date" in omitted.columns:
            omitted_eval = pd.to_datetime(omitted["eval_date"], errors="coerce").dt.normalize()
            omitted = omitted[omitted_eval.eq(eval_date)].copy()
        omitted = omitted[pd.to_numeric(omitted["year"], errors="coerce").eq(int(omitted_year))]
        omitted_sum = (
            omitted.groupby("product_vt_symbol")["net_pnl"].sum()
            if not omitted.empty
            else pd.Series(dtype=float)
        )
        data["omitted_year_net_pnl"] = data["product_vt_symbol"].map(omitted_sum).fillna(0.0)
        data["cumulative_net_pnl_variant"] -= data["omitted_year_net_pnl"]
    else:
        data["omitted_year_net_pnl"] = 0.0
    data["rank_all_cycle_profit_variant"] = rank_pct(data["cumulative_net_pnl_variant"])
    base_raw = pd.to_numeric(data["score_before_history_gate"], errors="coerce")
    base_rank = pd.to_numeric(data["rank_all_cycle_profit"], errors="coerce")
    data["score_before_history_gate_variant"] = (
        base_raw
        - ALL_CYCLE_WEIGHT * base_rank
        + ALL_CYCLE_WEIGHT * data["rank_all_cycle_profit_variant"]
    )
    available = pd.to_numeric(data["data_available"], errors="coerce").fillna(0).astype(int).eq(1)
    data["score_variant"] = np.where(
        available,
        data["score_before_history_gate_variant"],
        data["score_before_history_gate_variant"] * 0.25,
    )
    eligible = data[available].copy()
    eligible.sort_values(
        ["score_variant", "product_vt_symbol"],
        ascending=[False, True],
        inplace=True,
        kind="mergesort",
    )
    eligible["ordinal_rank"] = np.arange(1, len(eligible) + 1, dtype=int)
    eligible["selected_variant"] = eligible["ordinal_rank"].le(int(top_n))
    eligible["variant"] = "baseline" if omitted_year is None else f"drop_{int(omitted_year)}"
    eligible["omitted_year"] = np.nan if omitted_year is None else int(omitted_year)
    eligible["eval_date"] = eval_date
    return eligible.reset_index(drop=True)


def build_consensus_selection(variants: pd.DataFrame, *, top_n: int = TOP_N) -> pd.DataFrame:
    required = {"variant", "product_vt_symbol", "ordinal_rank"}
    missing = sorted(required - set(variants.columns))
    if missing:
        raise IntegrityError(f"variant ranks missing columns: {missing}")
    duplicate_rows = int(
        variants.duplicated(["variant", "product_vt_symbol"], keep=False).sum()
    )
    if duplicate_rows:
        raise IntegrityError(f"duplicate variant-product rows: {duplicate_rows}")
    consensus = (
        variants.groupby("product_vt_symbol", as_index=False)
        .agg(
            mean_ordinal_rank=("ordinal_rank", "mean"),
            rank_std=("ordinal_rank", "std"),
            variant_count=("variant", "nunique"),
            selection_frequency=("selected_variant", "mean")
            if "selected_variant" in variants.columns
            else ("ordinal_rank", lambda values: float("nan")),
        )
    )
    consensus["rank_std"] = consensus["rank_std"].fillna(0.0)
    consensus.sort_values(
        ["mean_ordinal_rank", "product_vt_symbol"],
        ascending=[True, True],
        inplace=True,
        kind="mergesort",
    )
    consensus["consensus_rank"] = np.arange(1, len(consensus) + 1, dtype=int)
    consensus["selected_consensus"] = consensus["consensus_rank"].le(int(top_n))
    return consensus.reset_index(drop=True)


def build_future60_labels(
    *,
    eval_date: Any,
    products: Iterable[str],
    global_dates: pd.DatetimeIndex,
    daily_by_product: dict[str, pd.DataFrame],
    horizon: int = HORIZON_DAYS,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    eval_ts = pd.Timestamp(eval_date).normalize()
    future_dates = pd.DatetimeIndex(global_dates[global_dates > eval_ts][: int(horizon)])
    window_complete = len(future_dates) == int(horizon)
    expected_set = set(future_dates)
    rows: list[dict[str, Any]] = []
    eval_date_in_label_count = 0
    for product in sorted(set(str(item) for item in products)):
        frame = daily_by_product.get(product, pd.DataFrame(columns=["date", "net_pnl"])).copy()
        if not frame.empty:
            frame["date"] = pd.to_datetime(frame["date"], errors="raise").dt.normalize()
            selected = frame[frame["date"].isin(expected_set)].copy()
        else:
            selected = frame
        eval_date_in_label_count += int(selected.get("date", pd.Series(dtype="datetime64[ns]")).eq(eval_ts).sum())
        observed_dates = set(selected.get("date", pd.Series(dtype="datetime64[ns]")))
        complete = bool(
            window_complete
            and len(selected) == int(horizon)
            and observed_dates == expected_set
            and not selected.get("date", pd.Series(dtype="datetime64[ns]")).duplicated().any()
        )
        pnl = pd.to_numeric(selected.get("net_pnl", pd.Series(dtype=float)), errors="coerce")
        finite = bool(len(pnl) == len(selected) and np.isfinite(pnl.to_numpy(dtype=float)).all())
        complete = complete and finite
        rows.append(
            {
                "eval_date": eval_ts,
                "product_vt_symbol": product,
                "label_start_date": future_dates[0] if len(future_dates) else pd.NaT,
                "label_end_date": future_dates[-1] if len(future_dates) else pd.NaT,
                "expected_date_count": int(horizon),
                "observed_date_count": int(len(selected)),
                "label_complete": complete,
                "future60_net_pnl": float(pnl.sum()) if complete else np.nan,
            }
        )
    labels = pd.DataFrame(rows)
    labels["future60_percentile"] = np.nan
    complete_mask = labels["label_complete"].astype(bool)
    if complete_mask.any():
        labels.loc[complete_mask, "future60_percentile"] = rank_pct(
            labels.loc[complete_mask, "future60_net_pnl"]
        )
    audit = {
        "eval_date": eval_ts,
        "label_window_complete": window_complete,
        "future_global_date_count": int(len(future_dates)),
        "label_start_date": future_dates[0] if len(future_dates) else pd.NaT,
        "label_end_date": future_dates[-1] if len(future_dates) else pd.NaT,
        "complete_product_count": int(complete_mask.sum()),
        "incomplete_product_count": int((~complete_mask).sum()),
        "eval_date_in_label_count": int(eval_date_in_label_count),
    }
    return labels, audit


def compare_selections(
    *,
    eval_date: Any,
    baseline: set[str],
    consensus: set[str],
    labels: pd.DataFrame,
) -> dict[str, Any]:
    eval_ts = pd.Timestamp(eval_date).normalize()
    added = sorted(consensus - baseline)
    removed = sorted(baseline - consensus)
    shared = sorted(baseline & consensus)
    union = sorted(baseline | consensus)
    swap_conservation = len(added) == len(removed) and len(baseline) == len(consensus)
    indexed = labels.set_index("product_vt_symbol", drop=False)
    missing_label_products = [product for product in union if product not in indexed.index]
    union_complete = bool(
        not missing_label_products
        and all(bool(indexed.loc[product, "label_complete"]) for product in union)
    )
    has_swap = len(added) > 0
    eligible = bool(has_swap and swap_conservation and union_complete)
    raw_edge = float("nan")
    percentile_edge = float("nan")
    if eligible:
        added_raw = sum(float(indexed.loc[product, "future60_net_pnl"]) for product in added)
        removed_raw = sum(float(indexed.loc[product, "future60_net_pnl"]) for product in removed)
        raw_edge = added_raw - removed_raw
        added_pct = np.mean(
            [float(indexed.loc[product, "future60_percentile"]) for product in added]
        )
        removed_pct = np.mean(
            [float(indexed.loc[product, "future60_percentile"]) for product in removed]
        )
        percentile_edge = float(added_pct - removed_pct)
    return {
        "eval_date": eval_ts,
        "eval_year": int(eval_ts.year),
        "baseline_count": int(len(baseline)),
        "consensus_count": int(len(consensus)),
        "shared_count": int(len(shared)),
        "union_count": int(len(union)),
        "jaccard": float(len(shared) / len(union)) if union else 1.0,
        "added_count": int(len(added)),
        "removed_count": int(len(removed)),
        "swap_count": int(len(added)),
        "swap_conservation_pass": bool(swap_conservation),
        "label_window_complete": bool(union_complete),
        "missing_label_product_count": int(len(missing_label_products)),
        "comparison_eligible": eligible,
        "raw_edge": raw_edge,
        "percentile_edge": percentile_edge,
        "baseline_products": "|".join(sorted(baseline)),
        "consensus_products": "|".join(sorted(consensus)),
        "shared_products": "|".join(shared),
        "added_products": "|".join(added),
        "removed_products": "|".join(removed),
    }


def build_decision(
    monthly: pd.DataFrame,
    *,
    upstream_pass: bool = True,
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    data = monthly.copy()
    data["eval_date"] = pd.to_datetime(data["eval_date"], errors="raise").dt.normalize()
    data["eval_year"] = data["eval_date"].dt.year.astype(int)
    complete = data[data["label_window_complete"].astype(bool)].copy()
    swaps = data[data["comparison_eligible"].astype(bool)].copy()
    yearly = (
        swaps.groupby("eval_year", as_index=False)
        .agg(
            swap_month_count=("eval_date", "count"),
            raw_edge_sum=("raw_edge", "sum"),
            raw_edge_median=("raw_edge", "median"),
            percentile_edge_median=("percentile_edge", "median"),
        )
        if not swaps.empty
        else pd.DataFrame(
            columns=[
                "eval_year",
                "swap_month_count",
                "raw_edge_sum",
                "raw_edge_median",
                "percentile_edge_median",
            ]
        )
    )
    active_years = yearly[yearly["swap_month_count"].gt(0)].copy()
    effective_years = yearly[
        yearly["swap_month_count"].ge(MIN_SWAPS_PER_ACTIVE_YEAR)
    ].copy()
    partial_active_year_count = int(
        ((active_years["swap_month_count"] > 0) & (active_years["swap_month_count"] < MIN_SWAPS_PER_ACTIVE_YEAR)).sum()
    )
    total_raw_edge = float(pd.to_numeric(swaps.get("raw_edge"), errors="coerce").sum()) if not swaps.empty else 0.0
    median_raw_edge = float(pd.to_numeric(swaps.get("raw_edge"), errors="coerce").median()) if not swaps.empty else float("nan")
    median_percentile_edge = (
        float(pd.to_numeric(swaps.get("percentile_edge"), errors="coerce").median())
        if not swaps.empty
        else float("nan")
    )
    positive_years = int(effective_years["raw_edge_sum"].gt(0).sum())
    negative_years = int(effective_years["raw_edge_sum"].lt(0).sum())
    early_edge = float(
        swaps.loc[swaps["eval_year"].between(2022, 2023), "raw_edge"].sum()
    )
    late_edge = float(
        swaps.loc[swaps["eval_year"].between(2024, 2026), "raw_edge"].sum()
    )
    positive_edge_total = float(effective_years.loc[effective_years["raw_edge_sum"].gt(0), "raw_edge_sum"].sum())
    best_year_share = (
        float(effective_years["raw_edge_sum"].max() / positive_edge_total)
        if positive_edge_total > 0 and not effective_years.empty
        else float("inf")
    )
    gate_rows = [
        ("upstream_integrity", bool(upstream_pass), int(bool(upstream_pass)), 1),
        ("complete_month_count", len(complete) >= MIN_COMPLETE_MONTHS, len(complete), MIN_COMPLETE_MONTHS),
        ("swap_month_count", len(swaps) >= MIN_SWAP_MONTHS, len(swaps), MIN_SWAP_MONTHS),
        (
            "effective_year_min_swap_months",
            partial_active_year_count == 0,
            partial_active_year_count,
            0,
        ),
        ("total_raw_edge_positive", total_raw_edge > 0, total_raw_edge, 0.0),
        ("median_monthly_raw_edge_positive", median_raw_edge > 0, median_raw_edge, 0.0),
        (
            "median_monthly_percentile_edge_positive",
            median_percentile_edge > 0,
            median_percentile_edge,
            0.0,
        ),
        ("positive_effective_year_count", positive_years >= MIN_POSITIVE_YEARS, positive_years, MIN_POSITIVE_YEARS),
        ("negative_effective_year_count", negative_years == 0, negative_years, 0),
        ("early_2022_2023_edge_positive", early_edge > 0, early_edge, 0.0),
        ("late_2024_2026_edge_positive", late_edge > 0, late_edge, 0.0),
        (
            "best_year_positive_edge_share",
            best_year_share <= MAX_BEST_YEAR_POSITIVE_EDGE_SHARE,
            best_year_share,
            MAX_BEST_YEAR_POSITIVE_EDGE_SHARE,
        ),
    ]
    gates = pd.DataFrame(gate_rows, columns=["gate", "pass", "actual", "required"])
    hard_pass = bool(gates["pass"].all())
    decision = {
        "decision": (
            "ALLOW_STAGE002_FOUR_ANCHOR_CANARY_PREDECL_ONLY"
            if hard_pass
            else "CLOSE_LINE_YEAR_JACKKNIFE_RANK_INELIGIBLE"
        ),
        "hard_gate_pass": hard_pass,
        "complete_month_count": int(len(complete)),
        "swap_month_count": int(len(swaps)),
        "active_year_count": int(len(active_years)),
        "effective_year_count": int(len(effective_years)),
        "partial_active_year_count": partial_active_year_count,
        "total_raw_edge": total_raw_edge,
        "median_monthly_raw_edge": median_raw_edge,
        "median_monthly_percentile_edge": median_percentile_edge,
        "positive_effective_year_count": positive_years,
        "negative_effective_year_count": negative_years,
        "early_2022_2023_edge": early_edge,
        "late_2024_2026_edge": late_edge,
        "best_year_positive_edge_share": best_year_share,
        "ready_for_backtest": False,
        "ready_for_live": False,
        "backtest_executed": False,
        "trade_count": 0,
    }
    return decision, yearly, gates


def _validate_cumulative_pnl(
    base_panel: pd.DataFrame, daily_by_product: dict[str, pd.DataFrame]
) -> dict[str, Any]:
    mismatches = 0
    max_abs_error = 0.0
    for row in base_panel[["eval_date", "product_vt_symbol", "cumulative_net_pnl_to_date"]].itertuples(index=False):
        daily = daily_by_product[str(row.product_vt_symbol)]
        actual = float(daily.loc[daily["date"].le(pd.Timestamp(row.eval_date)), "net_pnl"].sum())
        expected = float(row.cumulative_net_pnl_to_date)
        error = abs(actual - expected)
        max_abs_error = max(max_abs_error, error)
        if error > 1e-8:
            mismatches += 1
    return {
        "cumulative_recompute_rows": int(len(base_panel)),
        "cumulative_recompute_mismatch_rows": int(mismatches),
        "cumulative_recompute_max_abs_error": float(max_abs_error),
        "cumulative_recompute_pass": mismatches == 0,
    }


def _input_audit() -> tuple[
    pd.DataFrame,
    pd.DatetimeIndex,
    dict[str, pd.DataFrame],
    pd.DataFrame,
    pd.DataFrame,
    dict[str, Any],
]:
    universe_hash = sha256_file(UNIVERSE_PATH)
    old_hash = sha256_file(OLD_FEATURES_PATH)
    tool_hash = sha256_file(BASE_TOOL_PATH)
    universe = pd.read_csv(UNIVERSE_PATH)
    eligible = universe[pd.to_numeric(universe["eligible"], errors="coerce").fillna(0).astype(int).eq(1)].copy()
    products = sorted(eligible["product_vt_symbol"].astype(str).unique().tolist())
    panel, panel_audit = load_base_panel()
    dates, calendar_audit = load_global_dates()
    daily, daily_audit_frame, daily_audit = load_daily_by_product(products)
    daily_manifest, daily_manifest_hash = build_daily_manifest()
    cumulative_audit = _validate_cumulative_pnl(panel, daily)
    audit = {
        "universe_path": str(UNIVERSE_PATH),
        "universe_sha256": universe_hash,
        "universe_hash_ok": universe_hash == EXPECTED_UNIVERSE_SHA256,
        "eligible_product_count": int(len(products)),
        "eligible_product_count_ok": len(products) == EXPECTED_UNIVERSE_COUNT,
        "old_features_path": str(OLD_FEATURES_PATH),
        "old_features_sha256": old_hash,
        "old_features_hash_ok": old_hash == EXPECTED_OLD_FEATURES_SHA256,
        "base_tool_path": str(BASE_TOOL_PATH),
        "base_tool_sha256": tool_hash,
        "base_tool_hash_ok": tool_hash == EXPECTED_BASE_TOOL_SHA256,
        **panel_audit,
        **calendar_audit,
        **daily_audit,
        **cumulative_audit,
    }
    bool_checks = [value for key, value in audit.items() if key.endswith("_ok") or key.endswith("_pass")]
    audit["input_integrity_pass"] = bool(bool_checks and all(bool(value) for value in bool_checks))
    if daily_manifest_hash != EXPECTED_DAILY_MANIFEST_SHA256:
        audit["input_integrity_pass"] = False
    return panel, dates, daily, daily_audit_frame, daily_manifest, audit


def run_qualification() -> dict[str, Any]:
    panel, global_dates, daily_by_product, daily_audit, daily_manifest, input_audit = _input_audit()
    annual_pnl = build_annual_pnl(daily_by_product)
    if not input_audit["input_integrity_pass"]:
        raise IntegrityError(f"input integrity failed: {input_audit}")

    variant_parts: list[pd.DataFrame] = []
    consensus_parts: list[pd.DataFrame] = []
    label_parts: list[pd.DataFrame] = []
    monthly_rows: list[dict[str, Any]] = []
    baseline_reproduction_mismatch_months = 0
    baseline_score_max_abs_error = 0.0
    future_eval_leak_count = 0

    eligible_panel = panel[panel["eval_date"].ge(QUALIFICATION_START)].copy()
    for eval_date, month in eligible_panel.groupby("eval_date", sort=True):
        eval_ts = pd.Timestamp(eval_date).normalize()
        baseline_variant = build_variant_ranking(
            month,
            annual_pnl=annual_pnl,
            omitted_year=None,
        )
        stored_baseline = set(
            month.loc[pd.to_numeric(month["selected_topn"], errors="coerce").fillna(0).astype(int).eq(1), "product_vt_symbol"].astype(str)
        )
        recomputed_baseline = set(
            baseline_variant.loc[baseline_variant["selected_variant"], "product_vt_symbol"].astype(str)
        )
        if stored_baseline != recomputed_baseline:
            baseline_reproduction_mismatch_months += 1
        score_compare = month.set_index("product_vt_symbol")["score"].astype(float).reindex(
            baseline_variant["product_vt_symbol"]
        )
        baseline_score_max_abs_error = max(
            baseline_score_max_abs_error,
            float(
                np.max(
                    np.abs(
                        score_compare.to_numpy(dtype=float)
                        - baseline_variant["score_variant"].to_numpy(dtype=float)
                    )
                )
            ),
        )
        variants = [baseline_variant]
        for omitted_year in range(2020, int(eval_ts.year)):
            variants.append(
                build_variant_ranking(
                    month,
                    annual_pnl=annual_pnl,
                    omitted_year=omitted_year,
                )
            )
        variant_frame = pd.concat(variants, ignore_index=True)
        variant_parts.append(variant_frame)
        consensus = build_consensus_selection(variant_frame)
        consensus["eval_date"] = eval_ts
        consensus_parts.append(consensus)
        consensus_set = set(
            consensus.loc[consensus["selected_consensus"], "product_vt_symbol"].astype(str)
        )
        labels, label_audit = build_future60_labels(
            eval_date=eval_ts,
            products=month["product_vt_symbol"].astype(str).tolist(),
            global_dates=global_dates,
            daily_by_product=daily_by_product,
        )
        label_parts.append(labels)
        future_eval_leak_count += int(label_audit["eval_date_in_label_count"])
        comparison = compare_selections(
            eval_date=eval_ts,
            baseline=stored_baseline,
            consensus=consensus_set,
            labels=labels,
        )
        comparison.update(
            {
                "variant_count": int(variant_frame["variant"].nunique()),
                "omitted_year_count": int(variant_frame["variant"].nunique() - 1),
                "complete_product_label_count": int(label_audit["complete_product_count"]),
                "global_label_window_complete": bool(label_audit["label_window_complete"]),
                "baseline_reproduction_pass": stored_baseline == recomputed_baseline,
            }
        )
        monthly_rows.append(comparison)

    variants_all = pd.concat(variant_parts, ignore_index=True)
    consensus_all = pd.concat(consensus_parts, ignore_index=True)
    labels_all = pd.concat(label_parts, ignore_index=True)
    monthly = pd.DataFrame(monthly_rows).sort_values("eval_date").reset_index(drop=True)
    reproduction_audit = {
        "qualification_eval_count": int(monthly["eval_date"].nunique()),
        "baseline_reproduction_mismatch_months": int(baseline_reproduction_mismatch_months),
        "baseline_score_max_abs_error": float(baseline_score_max_abs_error),
        "future_eval_date_leak_count": int(future_eval_leak_count),
        "baseline_reproduction_pass": baseline_reproduction_mismatch_months == 0
        and baseline_score_max_abs_error <= 1e-12,
        "future_label_boundary_pass": future_eval_leak_count == 0,
        "variant_duplicate_key_rows": int(
            variants_all.duplicated(["eval_date", "variant", "product_vt_symbol"], keep=False).sum()
        ),
        "consensus_duplicate_key_rows": int(
            consensus_all.duplicated(["eval_date", "product_vt_symbol"], keep=False).sum()
        ),
        "label_duplicate_key_rows": int(
            labels_all.duplicated(["eval_date", "product_vt_symbol"], keep=False).sum()
        ),
    }
    reproduction_audit["qualification_integrity_pass"] = bool(
        reproduction_audit["baseline_reproduction_pass"]
        and reproduction_audit["future_label_boundary_pass"]
        and reproduction_audit["variant_duplicate_key_rows"] == 0
        and reproduction_audit["consensus_duplicate_key_rows"] == 0
        and reproduction_audit["label_duplicate_key_rows"] == 0
        and monthly["swap_conservation_pass"].astype(bool).all()
    )
    upstream_pass = bool(
        input_audit["input_integrity_pass"]
        and reproduction_audit["qualification_integrity_pass"]
    )
    decision, yearly, gates = build_decision(monthly, upstream_pass=upstream_pass)
    decision.update(
        {
            "line_id": LINE_ID,
            "stage_id": STAGE_ID,
            "generated_at": pd.Timestamp.now(tz="Asia/Shanghai").isoformat(),
            "producer_sha256": sha256_file(Path(__file__).resolve()),
            "input_audit": input_audit,
            "reproduction_audit": reproduction_audit,
        }
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    outputs = {
        "daily_source_manifest.csv": daily_manifest,
        "daily_source_audit.csv": daily_audit,
        "annual_product_pnl.csv": annual_pnl,
        "variant_rankings.csv.gz": variants_all,
        "consensus_rankings.csv": consensus_all,
        "future60_labels.csv": labels_all,
        "monthly_comparison.csv": monthly,
        "yearly_comparison.csv": yearly,
        "gates.csv": gates,
    }
    for name, frame in outputs.items():
        path = OUTPUT_DIR / name
        if name.endswith(".gz"):
            temporary = path.with_name(f".{path.name}.tmp")
            frame.to_csv(temporary, index=False, compression="gzip")
            os.replace(temporary, path)
        else:
            _atomic_csv(path, frame)
    _atomic_json(OUTPUT_DIR / "input_audit.json", input_audit)
    _atomic_json(OUTPUT_DIR / "reproduction_audit.json", reproduction_audit)
    _atomic_json(OUTPUT_DIR / "decision.json", decision)
    _atomic_bytes(
        OUTPUT_DIR / "report.md",
        _build_report(decision, monthly, yearly, gates).encode("utf-8"),
    )
    manifest = _output_manifest(OUTPUT_DIR)
    _atomic_csv(OUTPUT_DIR / "manifest.csv", manifest)
    _atomic_bytes(
        OUTPUT_DIR / "manifest.sha256",
        f"{sha256_file(OUTPUT_DIR / 'manifest.csv')}  manifest.csv\n".encode("ascii"),
    )
    return decision


def _output_manifest(directory: Path) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for path in sorted(directory.iterdir(), key=lambda item: item.name):
        if not path.is_file() or path.name in {"manifest.csv", "manifest.sha256"}:
            continue
        rows.append(
            {"file": path.name, "bytes": path.stat().st_size, "sha256": sha256_file(path)}
        )
    return pd.DataFrame(rows, columns=["file", "bytes", "sha256"])


def _build_report(
    decision: dict[str, Any],
    monthly: pd.DataFrame,
    yearly: pd.DataFrame,
    gates: pd.DataFrame,
) -> str:
    yearly_table = yearly.to_markdown(index=False, floatfmt=".6f") if not yearly.empty else "_无有效年_"
    gate_table = gates.to_markdown(index=False, floatfmt=".6f")
    recent = monthly.tail(18)[
        [
            "eval_date",
            "variant_count",
            "shared_count",
            "swap_count",
            "jaccard",
            "comparison_eligible",
            "raw_edge",
            "percentile_edge",
        ]
    ].to_markdown(index=False, floatfmt=".6f")
    return f"""# Stage001 AI 排名年度 Jackknife 资格审计

- 决策：`{decision['decision']}`
- 完整比较月：`{decision['complete_month_count']}`
- 实际换仓月：`{decision['swap_month_count']}`
- total raw edge：`{decision['total_raw_edge']:.6f}`
- median monthly raw edge：`{decision['median_monthly_raw_edge']:.6f}`
- median percentile edge：`{decision['median_monthly_percentile_edge']:.6f}`
- 正/负有效年份：`{decision['positive_effective_year_count']} / {decision['negative_effective_year_count']}`
- early/late edge：`{decision['early_2022_2023_edge']:.6f} / {decision['late_2024_2026_edge']:.6f}`
- 回测/实盘 ready：`False / False`

## 年度结果

{yearly_table}

## 机械硬门

{gate_table}

## 最近18个评估月

{recent}

## 口径边界

- 本阶段只审计固定评分对过去单一完整年份的敏感性，不是策略资金曲线回测。
- future60 只作资格标签，没有写回 score；通过也只能进入四锚点 canary 预声明。
- 失败后禁止修改24%权重、Top8、年度块、平均名次、60日标签或年份门救参。
"""


def main() -> None:
    decision = run_qualification()
    print(
        json.dumps(
            {
                "decision": decision["decision"],
                "complete_month_count": decision["complete_month_count"],
                "swap_month_count": decision["swap_month_count"],
                "total_raw_edge": decision["total_raw_edge"],
                "positive_effective_year_count": decision[
                    "positive_effective_year_count"
                ],
                "negative_effective_year_count": decision[
                    "negative_effective_year_count"
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
