"""Pure data-contract logic for the PIT full-market source rebuild."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
import hashlib
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ALLOWED_EXCHANGES: tuple[str, ...] = ("CZCE", "DCE", "GFEX", "INE", "SHFE")


class SourceContractError(RuntimeError):
    """Raised when a source artifact violates the frozen rebuild contract."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_columns(frame: pd.DataFrame, required: set[str], name: str) -> None:
    if missing := sorted(required - set(frame.columns)):
        raise SourceContractError(f"{name}_columns_missing:{','.join(missing)}")


def _normalise_product(product: str, exchange: str) -> str:
    return str(product).upper() if exchange in {"CZCE", "CFFEX"} else str(product).lower()


def _split_tq_symbol(tq_symbol: str) -> tuple[str, str]:
    exchange, separator, symbol = str(tq_symbol).partition(".")
    if not separator or not exchange or not symbol:
        raise SourceContractError(f"tq_symbol_invalid:{tq_symbol}")
    return exchange.upper(), symbol


def tq_to_vt_symbol(tq_symbol: str) -> str:
    exchange, symbol = _split_tq_symbol(tq_symbol)
    return f"{symbol}.{exchange}"


def _normalise_date_series(values: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(values):
        return pd.to_datetime(values, unit="ns", errors="raise", utc=True).dt.tz_convert(
            "Asia/Shanghai"
        ).dt.tz_localize(None).dt.normalize()
    parsed = pd.to_datetime(values, errors="raise", utc=True)
    return parsed.dt.tz_convert("Asia/Shanghai").dt.tz_localize(None).dt.normalize()


def _normalise_expire_datetime(values: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    parsed = pd.to_datetime(numeric, unit="s", errors="coerce", utc=True)
    return parsed.dt.tz_convert("Asia/Shanghai").dt.tz_localize(None).dt.normalize()


def normalise_catalog(
    raw: pd.DataFrame,
    *,
    catalog_as_of: pd.Timestamp,
    source_start: pd.Timestamp,
    cutoff: pd.Timestamp,
    allowed_exchanges: Sequence[str] = ALLOWED_EXCHANGES,
) -> pd.DataFrame:
    """Normalise one as-of-cutoff TqSdk contract catalog."""

    start = pd.Timestamp(source_start).normalize()
    end = pd.Timestamp(cutoff).normalize()
    observed = pd.Timestamp(catalog_as_of).normalize()
    if start > end:
        raise SourceContractError("source_range_invalid")
    if observed > end:
        raise SourceContractError("catalog_asof_after_cutoff")
    if observed != end:
        raise SourceContractError("catalog_asof_not_cutoff")

    frame = raw.copy()
    if "instrument_id" not in frame.columns and frame.index.name == "instrument_id":
        frame = frame.reset_index()
    required = {
        "instrument_id",
        "ins_class",
        "exchange_id",
        "product_id",
        "expired",
        "expire_datetime",
        "delivery_year",
        "delivery_month",
        "price_tick",
        "volume_multiple",
    }
    _require_columns(frame, required, "catalog")
    frame = frame.loc[:, sorted(required)].copy()
    frame["instrument_id"] = frame["instrument_id"].astype(str).str.strip()
    frame["ins_class"] = frame["ins_class"].astype(str).str.strip().str.upper()
    frame["exchange_id"] = frame["exchange_id"].astype(str).str.strip().str.upper()
    frame["product_id"] = frame["product_id"].astype(str).str.strip()
    frame = frame[
        frame["ins_class"].eq("FUTURE")
        & frame["exchange_id"].isin(tuple(str(value).upper() for value in allowed_exchanges))
    ].copy()
    if frame.empty:
        raise SourceContractError("catalog_commodity_future_empty")

    split_values = frame["instrument_id"].map(_split_tq_symbol)
    frame["symbol_exchange"] = split_values.map(lambda value: value[0])
    frame["symbol"] = split_values.map(lambda value: value[1])
    if not frame["symbol_exchange"].eq(frame["exchange_id"]).all():
        raise SourceContractError("catalog_exchange_identity_mismatch")
    monthly_average = frame["exchange_id"].eq("DCE") & frame["symbol"].str.fullmatch(
        r"[A-Za-z]+[0-9]{3,4}F"
    )
    excluded_monthly_average = sorted(frame.loc[monthly_average, "instrument_id"].tolist())
    frame = frame.loc[~monthly_average].copy()
    if not frame["symbol"].str.fullmatch(r"[A-Za-z]+[0-9]{3,4}").all():
        invalid = frame.loc[
            ~frame["symbol"].str.fullmatch(r"[A-Za-z]+[0-9]{3,4}"), "instrument_id"
        ].iloc[0]
        raise SourceContractError(f"catalog_contract_symbol_invalid:{invalid}")

    frame["expired_asof"] = frame["expired"].map(bool)
    frame["expire_date"] = _normalise_expire_datetime(frame["expire_datetime"])
    frame["delivery_year"] = pd.to_numeric(frame["delivery_year"], errors="coerce").astype("Int64")
    frame["delivery_month"] = pd.to_numeric(frame["delivery_month"], errors="coerce").astype("Int64")
    frame["price_tick"] = pd.to_numeric(frame["price_tick"], errors="coerce")
    frame["volume_multiple"] = pd.to_numeric(frame["volume_multiple"], errors="coerce")
    if frame["price_tick"].le(0).any() or frame["volume_multiple"].le(0).any():
        raise SourceContractError("catalog_contract_spec_nonpositive")

    # Contracts that expired before the requested source window cannot contribute bars or mapping.
    frame = frame[frame["expire_date"].isna() | frame["expire_date"].ge(start)].copy()
    frame["tq_symbol"] = frame["instrument_id"]
    frame["vt_symbol"] = frame["tq_symbol"].map(tq_to_vt_symbol)
    frame["product"] = [
        _normalise_product(product, exchange)
        for product, exchange in zip(frame["product_id"], frame["exchange_id"], strict=True)
    ]
    frame["product_vt_symbol"] = frame["product"] + "." + frame["exchange_id"]
    frame["catalog_as_of"] = observed
    if frame.duplicated("tq_symbol").any():
        raise SourceContractError("catalog_contract_duplicate")
    columns = [
        "tq_symbol",
        "vt_symbol",
        "symbol",
        "exchange_id",
        "product",
        "product_vt_symbol",
        "expired_asof",
        "expire_date",
        "delivery_year",
        "delivery_month",
        "price_tick",
        "volume_multiple",
        "catalog_as_of",
    ]
    result = frame[columns].sort_values("tq_symbol", kind="mergesort").reset_index(drop=True)
    result.attrs["excluded_dce_monthly_average_symbols"] = excluded_monthly_average
    return result


def _continuous_identity(tq_symbol: str) -> tuple[str, str, str]:
    prefix = "KQ.m@"
    if not str(tq_symbol).startswith(prefix):
        raise SourceContractError(f"continuous_symbol_invalid:{tq_symbol}")
    exchange, product = _split_tq_symbol(str(tq_symbol)[len(prefix) :])
    product = _normalise_product(product, exchange)
    return exchange, product, f"{product}.{exchange}"


def calendar_to_mapping(
    calendar: pd.DataFrame,
    catalog: pd.DataFrame,
    *,
    source_start: pd.Timestamp,
    cutoff: pd.Timestamp,
) -> pd.DataFrame:
    """Convert an exact-range TqContCalendar frame to the frozen long mapping."""

    _require_columns(calendar, {"date"}, "calendar")
    _require_columns(catalog, {"tq_symbol", "product_vt_symbol"}, "catalog")
    start = pd.Timestamp(source_start).normalize()
    end = pd.Timestamp(cutoff).normalize()
    frame = calendar.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="raise").dt.normalize()
    if frame["date"].lt(start).any():
        raise SourceContractError("calendar_before_source_start")
    if frame["date"].gt(end).any():
        raise SourceContractError("calendar_after_cutoff")
    if "trading" in frame.columns:
        frame = frame[frame["trading"].astype(bool)].copy()
    continuous_symbols = sorted(column for column in frame.columns if str(column).startswith("KQ.m@"))
    if not continuous_symbols:
        raise SourceContractError("calendar_continuous_symbols_empty")

    catalog_symbols = set(catalog["tq_symbol"].astype(str))
    catalog_products = set(catalog["product_vt_symbol"].astype(str))
    rows: list[dict[str, Any]] = []
    for continuous_symbol in continuous_symbols:
        exchange, product, product_vt = _continuous_identity(continuous_symbol)
        if product_vt not in catalog_products:
            raise SourceContractError(f"calendar_product_not_in_catalog:{continuous_symbol}")
        for item in frame[["date", continuous_symbol]].itertuples(index=False, name=None):
            date_value, raw_contract = item
            calendar_main_contract_tq = "" if pd.isna(raw_contract) else str(raw_contract).strip()
            if not calendar_main_contract_tq:
                main_contract_tq = ""
                resolution = "vendor_blank"
            elif calendar_main_contract_tq not in catalog_symbols:
                main_contract_tq = ""
                resolution = "unresolved_not_in_asof_catalog"
            else:
                main_contract_tq = calendar_main_contract_tq
                resolution = "resolved"
            rows.append(
                {
                    "date": pd.Timestamp(date_value).normalize(),
                    "product": product,
                    "exchange": exchange,
                    "continuous_symbol_tq": continuous_symbol,
                    "continuous_symbol_vt": product_vt,
                    "calendar_main_contract_tq": calendar_main_contract_tq,
                    "main_contract_tq": main_contract_tq,
                    "main_contract_vt": tq_to_vt_symbol(main_contract_tq)
                    if main_contract_tq
                    else "",
                    "mapping_resolution": resolution,
                }
            )
    mapping = pd.DataFrame(rows)
    if mapping.duplicated(["date", "continuous_symbol_vt"]).any():
        raise SourceContractError("mapping_date_product_duplicate")
    return mapping.sort_values(
        ["date", "continuous_symbol_vt"], kind="mergesort"
    ).reset_index(drop=True)


def build_acquisition_plan(
    catalog: pd.DataFrame,
    inventory: pd.DataFrame,
    *,
    required_contracts: set[str],
    source_start: pd.Timestamp,
    cutoff: pd.Timestamp,
) -> pd.DataFrame:
    """Choose archive reuse versus an exact-cutoff fetch without inspecting outcomes."""

    _require_columns(catalog, {"tq_symbol", "expired_asof", "expire_date"}, "catalog")
    inventory_columns = {"tq_symbol", "status", "rows", "min_date", "max_date", "path", "sha256"}
    _require_columns(inventory, inventory_columns, "inventory")
    if inventory.duplicated("tq_symbol").any():
        raise SourceContractError("inventory_contract_duplicate")
    start = pd.Timestamp(source_start).normalize()
    end = pd.Timestamp(cutoff).normalize()
    by_symbol = inventory.set_index("tq_symbol", drop=False)
    rows: list[dict[str, Any]] = []
    for contract in catalog.sort_values("tq_symbol", kind="mergesort").itertuples(index=False):
        tq_symbol = str(contract.tq_symbol)
        required = tq_symbol in required_contracts
        archived = by_symbol.loc[tq_symbol] if tq_symbol in by_symbol.index else None
        archive_available = bool(
            archived is not None
            and str(archived["status"]) == "available"
            and int(archived["rows"]) > 0
            and str(archived["path"])
        )
        if bool(contract.expired_asof) and archive_available:
            action = "reuse_archive"
        elif not bool(contract.expired_asof) or required:
            action = "fetch_asof_history"
        else:
            action = "skip_unreferenced_expired_missing"
        expire_date = pd.Timestamp(contract.expire_date).normalize() if pd.notna(contract.expire_date) else end
        fetch_end = min(end, expire_date) if action == "fetch_asof_history" else pd.NaT
        rows.append(
            {
                "tq_symbol": tq_symbol,
                "action": action,
                "required_by_mapping": required,
                "expired_asof": bool(contract.expired_asof),
                "fetch_start": start if action == "fetch_asof_history" else pd.NaT,
                "fetch_end": fetch_end,
                "archive_status": str(archived["status"]) if archived is not None else "missing",
                "archive_rows": int(archived["rows"]) if archived is not None else 0,
                "archive_path": str(archived["path"]) if archived is not None else "",
                "archive_sha256": str(archived["sha256"]) if archived is not None else "",
            }
        )
    return pd.DataFrame(rows)


def scan_archive_inventory(catalog: pd.DataFrame, archive_root: Path) -> pd.DataFrame:
    """Inspect line-relevant archive files instead of trusting a stale status ledger."""

    _require_columns(catalog, {"tq_symbol"}, "catalog")
    root = Path(archive_root).resolve()
    rows: list[dict[str, Any]] = []
    for tq_symbol in sorted(catalog["tq_symbol"].astype(str).unique()):
        exchange, symbol = _split_tq_symbol(tq_symbol)
        path = root / exchange / f"{symbol}.csv"
        if not path.is_file() or path.stat().st_size == 0:
            rows.append(
                {
                    "tq_symbol": tq_symbol,
                    "status": "missing",
                    "rows": 0,
                    "min_date": pd.NaT,
                    "max_date": pd.NaT,
                    "path": "",
                    "sha256": "",
                }
            )
            continue
        try:
            dates = pd.read_csv(path, usecols=["trade_date"], encoding="utf-8-sig")
            dates["trade_date"] = pd.to_datetime(dates["trade_date"], errors="raise").dt.normalize()
        except Exception as exc:
            raise SourceContractError(f"archive_file_unreadable:{tq_symbol}:{exc!r}") from exc
        if dates["trade_date"].duplicated().any():
            raise SourceContractError(f"archive_bar_date_duplicate:{tq_symbol}")
        rows.append(
            {
                "tq_symbol": tq_symbol,
                "status": "available" if len(dates) else "empty",
                "rows": int(len(dates)),
                "min_date": dates["trade_date"].min() if len(dates) else pd.NaT,
                "max_date": dates["trade_date"].max() if len(dates) else pd.NaT,
                "path": str(path),
                "sha256": sha256_file(path),
            }
        )
    return pd.DataFrame(rows)


def normalise_raw_bars(
    raw: pd.DataFrame,
    *,
    tq_symbol: str,
    source_start: pd.Timestamp,
    cutoff: pd.Timestamp,
    source_kind: str,
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Normalise one TqSdk daily frame and clip it to the declared source window."""

    date_column = "trade_date" if "trade_date" in raw.columns else "datetime"
    oi_column = "open_oi" if "open_oi" in raw.columns else "open_interest"
    _require_columns(raw, {date_column, "close", "volume", oi_column}, "raw_bars")
    exchange, symbol = _split_tq_symbol(tq_symbol)
    frame = raw.copy()
    frame["date"] = _normalise_date_series(frame[date_column])
    start = pd.Timestamp(source_start).normalize()
    end = pd.Timestamp(cutoff).normalize()
    diagnostics = {
        "source_rows": int(len(frame)),
        "rows_before_start_dropped": int(frame["date"].lt(start).sum()),
        "rows_after_cutoff_dropped": int(frame["date"].gt(end).sum()),
        "normalised_rows": 0,
    }
    frame = frame[frame["date"].between(start, end)].copy()
    frame["close_price"] = pd.to_numeric(frame["close"], errors="coerce")
    frame["volume"] = pd.to_numeric(frame["volume"], errors="coerce")
    frame["open_interest"] = pd.to_numeric(frame[oi_column], errors="coerce")
    frame = frame[
        frame["close_price"].notna()
        & frame["close_price"].gt(0)
        & frame["volume"].notna()
        & frame["volume"].ge(0)
        & frame["open_interest"].notna()
        & frame["open_interest"].ge(0)
    ].copy()
    if frame.duplicated("date").any():
        raise SourceContractError(f"raw_bar_date_duplicate:{tq_symbol}")
    frame["datetime"] = frame["date"]
    frame["symbol"] = symbol
    frame["exchange"] = exchange
    frame["interval"] = "d"
    frame["source_kind"] = str(source_kind)
    columns = [
        "datetime",
        "symbol",
        "exchange",
        "interval",
        "close_price",
        "volume",
        "open_interest",
        "source_kind",
    ]
    result = frame[columns].sort_values("datetime", kind="mergesort").reset_index(drop=True)
    diagnostics["normalised_rows"] = int(len(result))
    return result, diagnostics


def _numeric_rows_equal(left: pd.Series, right: pd.Series) -> bool:
    return all(
        bool(np.isclose(float(left[column]), float(right[column]), equal_nan=True))
        for column in ("close_price", "volume", "open_interest")
    )


def merge_bar_sources(frames: Iterable[pd.DataFrame]) -> pd.DataFrame:
    """Merge normalised bars and reject source disagreement on the same contract date."""

    materialised = [frame.copy() for frame in frames if not frame.empty]
    columns = [
        "datetime",
        "symbol",
        "exchange",
        "interval",
        "close_price",
        "volume",
        "open_interest",
        "source_kind",
    ]
    if not materialised:
        return pd.DataFrame(columns=columns)
    for frame in materialised:
        _require_columns(frame, set(columns), "normalised_bars")
    combined = pd.concat(materialised, ignore_index=True)
    keys = ["datetime", "symbol", "exchange", "interval"]
    kept: list[pd.Series] = []
    for _, group in combined.groupby(keys, sort=False, dropna=False):
        first = group.iloc[0].copy()
        for index in range(1, len(group)):
            if not _numeric_rows_equal(first, group.iloc[index]):
                identity = ":".join(str(first[column]) for column in keys)
                raise SourceContractError(f"bar_duplicate_conflict:{identity}")
        first["source_kind"] = "+".join(sorted(set(group["source_kind"].astype(str))))
        kept.append(first)
    result = pd.DataFrame(kept, columns=columns)
    return result.sort_values(keys, kind="mergesort").reset_index(drop=True)


def build_invariant_product_metadata(
    catalog: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, list[str]]]:
    """Publish product metadata only when all observed contract specs agree."""

    _require_columns(
        catalog,
        {"product_vt_symbol", "price_tick", "volume_multiple"},
        "catalog",
    )
    rows: list[dict[str, Any]] = []
    variant_products: list[str] = []
    invalid_products: list[str] = []
    for product, group in catalog.groupby("product_vt_symbol", sort=True):
        specs = group[["price_tick", "volume_multiple"]].apply(pd.to_numeric, errors="coerce")
        specs = specs[
            specs["price_tick"].notna()
            & specs["price_tick"].gt(0)
            & specs["volume_multiple"].notna()
            & specs["volume_multiple"].gt(0)
        ].drop_duplicates()
        if specs.empty:
            invalid_products.append(str(product))
            continue
        if len(specs) != 1:
            variant_products.append(str(product))
            continue
        rows.append(
            {
                "vt_symbol": str(product),
                "symbol_kind": "product_cont",
                "price_tick": float(specs.iloc[0]["price_tick"]),
                "volume_multiple": float(specs.iloc[0]["volume_multiple"]),
            }
        )
    metadata = pd.DataFrame(
        rows,
        columns=["vt_symbol", "symbol_kind", "price_tick", "volume_multiple"],
    ).sort_values("vt_symbol", kind="mergesort").reset_index(drop=True)
    return metadata, {
        "variant_products": sorted(variant_products),
        "invalid_products": sorted(invalid_products),
    }


def assert_line_local_output(line_dir: Path, candidate: Path) -> Path:
    """Resolve an output path and reject writes outside the owning research line."""

    root = Path(line_dir).resolve()
    path = Path(candidate).resolve()
    if not path.is_relative_to(root) or path == root:
        raise SourceContractError(f"output_path_outside_line:{path}")
    return path
