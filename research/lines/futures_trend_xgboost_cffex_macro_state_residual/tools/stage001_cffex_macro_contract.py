"""Label-free CFFEX macro-state source and feature contract."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import secrets
import shutil
import threading
import time
import traceback
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Sequence

import numpy as np
import pandas as pd
import requests


CORE_ROOTS = ("IF", "IH", "IC", "T", "TF", "TS")
EQUITY_ROOTS = ("IF", "IH", "IC")
RATES_ROOTS = ("T", "TF", "TS")

MACRO_FEATURES = (
    "cffex_equity_momentum_60d",
    "cffex_rates_momentum_60d",
    "cffex_equity_vol_ratio_20_120",
    "cffex_rates_vol_ratio_20_120",
    "cffex_equity_rates_corr_60d",
    "cffex_equity_breadth_60d",
    "cffex_equity_dispersion_60d",
)

SECTOR_PRODUCTS = {
    "metals": ("au.SHFE", "cu.SHFE", "lc.GFEX", "si.GFEX"),
    "ferrous": ("SM.CZCE", "rb.SHFE", "jm.DCE", "hc.SHFE"),
    "agriculture": ("OI.CZCE", "AP.CZCE", "CF.CZCE", "lh.DCE"),
    "chemicals_materials": (
        "MA.CZCE",
        "SA.CZCE",
        "FG.CZCE",
        "SH.CZCE",
        "ru.SHFE",
        "sp.SHFE",
    ),
}
FORMAL_PRODUCTS = tuple(
    product for products in SECTOR_PRODUCTS.values() for product in products
)
SECTOR_COLUMNS = tuple(f"sector_{sector}" for sector in SECTOR_PRODUCTS)

EXPECTED_RELEASE_ID = "m0005_20260901T165450+0800_1961d98ccb2b"
EXPECTED_STRATEGY_ID = "ai_top10_plus_fu_official_live_v1"
EXPECTED_SOURCE_AGGREGATE_SHA256 = (
    "6309d58c005e4409d9961c2197ae67e2a31a9c1c7904a1254f5656ddd00e5e39"
)
PASS_DECISION = (
    "stage001_cffex_macro_contract_pass_allow_stage002_preregistration_only"
)
FAIL_DECISION = "stage001_cffex_macro_contract_fail_close_no_labels"
CFFEX_ARCHIVE_URL = "http://www.cffex.com.cn/sj/historysj/{month}/zip/{month}.zip"

LINE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[4]
PREDECESSOR_LINE = (
    REPO_ROOT / "research/lines/futures_trend_lr_xgboost_base_margin_model_ranked"
)
PREDECESSOR_STAGE001_DIR = PREDECESSOR_LINE / "artifacts/stage001_model_ranked_contract"
FOLD_PLAN_PATH = PREDECESSOR_STAGE001_DIR / "fold_plan.csv"
PRODUCTION_ROOT = Path("/Users/bytedance/Desktop/person/vnpy_production_live")
MATERIALS_ROOT = PRODUCTION_ROOT / "official_strategy_materials"
CURRENT_PATH = MATERIALS_ROOT / "CURRENT.json"
RELEASE_DIR = (
    MATERIALS_ROOT
    / EXPECTED_STRATEGY_ID
    / "releases"
    / EXPECTED_RELEASE_ID
)
RELEASE_MANIFEST_PATH = RELEASE_DIR / "manifest.json"
FORMAL_LR_CODE_PATH = (
    RELEASE_DIR
    / "payload/examples/portfolio_backtesting/"
    "analyze_qmt_roll_ai_product_suitability_walkforward.py"
)
QMT_UNIVERSE_PATH = (
    RELEASE_DIR / "payload/examples/portfolio_backtesting/qmt_universe.py"
)
FINAL_OUTPUT_DIR = LINE_DIR / "artifacts/stage001_cffex_macro_contract"

EXPECTED_INPUT_HASHES: dict[str, tuple[Path, str]] = {
    "formal_current_pointer": (
        CURRENT_PATH,
        "f17c0f6bfeea4a08ec7c22a1eb63d4b51e4cfb2472f1ce07fac8ce2cc570b219",
    ),
    "formal_release_manifest": (
        RELEASE_MANIFEST_PATH,
        "d62e58d01284e30b28054387592604862ffeff6e55a13c63192793e95bc55c21",
    ),
    "formal_lr_code": (
        FORMAL_LR_CODE_PATH,
        "7734d1768728a4e591b80e98da2b5bac90636904dad82e0fed5f331a6eb45de4",
    ),
    "formal_qmt_universe": (
        QMT_UNIVERSE_PATH,
        "8a149c49075d85d25f27146a8f3c2de3bea1971e3bd0d20a36ed9104b636997f",
    ),
    "predecessor_fold_plan": (
        FOLD_PLAN_PATH,
        "a14fbde27943e1c73eaa8c1e2ea14834e212616e82fe024ba193697369a25e6c",
    ),
    "predecessor_stage001_summary": (
        PREDECESSOR_STAGE001_DIR / "summary.json",
        "63c63d729d693ac7cecb44ff3cefac2100c10dea7a2a4a13a2b3d550fffa0aa1",
    ),
    "predecessor_stage001_manifest": (
        PREDECESSOR_STAGE001_DIR / "artifact_manifest.json",
        "9d24f6e62ecf315af8dd3b08a7f0d444705fbfcba2752581f0942e08ad498c2d",
    ),
    "predecessor_xgboost_implementation": (
        PREDECESSOR_LINE / "tools/stage002_base_margin_development_oos.py",
        "782d76b8620db93a5a760ba9e838333e237439b2b99ae0b65989115f99a8a1c4",
    ),
}


class Stage001Error(RuntimeError):
    pass


def month_range(start: str, end: str) -> list[str]:
    if not re.fullmatch(r"\d{6}", start) or not re.fullmatch(r"\d{6}", end):
        raise Stage001Error("invalid_month_format")
    start_period = pd.Period(start, freq="M")
    end_period = pd.Period(end, freq="M")
    if start_period > end_period:
        raise Stage001Error("invalid_month_range")
    return [period.strftime("%Y%m") for period in pd.period_range(start_period, end_period, freq="M")]


SOURCE_MONTHS = tuple(month_range("201906", "202605"))


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _sha256_file(path: Path) -> tuple[int, int, str]:
    source = path.expanduser().resolve(strict=True)
    before = source.stat()
    digest = hashlib.sha256()
    with source.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    after = source.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise Stage001Error(f"file_changed_while_hashing:{source}")
    return int(after.st_size), int(after.st_mtime_ns), digest.hexdigest()


def _json_default(value: object) -> object:
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"not_json_serializable:{type(value).__name__}")


def _atomic_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}.{threading.get_ident()}")
    try:
        with temporary.open("wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _atomic_write_json(path: Path, payload: object) -> None:
    content = (
        json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default) + "\n"
    ).encode("utf-8")
    _atomic_write_bytes(path, content)


def _read_cffex_csv(content: bytes, filename: str) -> pd.DataFrame:
    errors: list[str] = []
    for encoding in ("gb18030", "utf-8-sig"):
        try:
            return pd.read_csv(io.BytesIO(content), encoding=encoding, dtype=str)
        except (UnicodeDecodeError, pd.errors.ParserError) as exc:
            errors.append(f"{encoding}:{type(exc).__name__}")
    raise Stage001Error(f"daily_csv_parse_failed:{filename}:{'|'.join(errors)}")


def _resolve_column(frame: pd.DataFrame, aliases: tuple[str, ...], field: str) -> str:
    normalized = {str(column).lstrip("\ufeff").strip(): str(column) for column in frame.columns}
    for alias in aliases:
        if alias in normalized:
            return normalized[alias]
    raise Stage001Error(f"daily_csv_column_missing:{field}")


def _numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.astype(str).str.strip().str.replace(",", "", regex=False),
        errors="coerce",
    )


def parse_month_archive(month: str, content: bytes) -> tuple[pd.DataFrame, list[str]]:
    if not re.fullmatch(r"\d{6}", month):
        raise Stage001Error(f"invalid_month:{month}")
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except (zipfile.BadZipFile, OSError) as exc:
        raise Stage001Error(f"archive_invalid:{month}") from exc

    with archive:
        names = sorted(
            name
            for name in archive.namelist()
            if re.fullmatch(r"\d{8}_1\.csv", PurePosixPath(name).name)
        )
        if not names:
            raise Stage001Error(f"archive_daily_files_missing:{month}")
        frames: list[pd.DataFrame] = []
        raw_rows = 0
        for name in names:
            basename = PurePosixPath(name).name
            date_token = basename[:8]
            if date_token[:6] != month:
                raise Stage001Error(f"archive_daily_file_month_mismatch:{month}:{basename}")
            daily = _read_cffex_csv(archive.read(name), basename)
            raw_rows += len(daily)
            symbol_column = _resolve_column(
                daily,
                ("合约代码", "合约", "instrument_id", "instrument", "symbol"),
                "symbol",
            )
            close_column = _resolve_column(
                daily,
                ("今收盘", "收盘价", "close", "close_price"),
                "close",
            )
            volume_column = _resolve_column(
                daily,
                ("成交量", "volume"),
                "volume",
            )
            oi_column = _resolve_column(
                daily,
                ("持仓量", "open_interest"),
                "open_interest",
            )
            symbol = daily[symbol_column].astype(str).str.strip().str.upper()
            root = symbol.str.extract(r"^([A-Z]+)", expand=False)
            normalized = pd.DataFrame(
                {
                    "date": pd.Timestamp(date_token),
                    "root": root,
                    "symbol": symbol,
                    "close": _numeric(daily[close_column]),
                    "volume": _numeric(daily[volume_column]),
                    "open_interest": _numeric(daily[oi_column]),
                }
            )
            exact_future = normalized["symbol"].str.fullmatch(
                rf"(?:{'|'.join(CORE_ROOTS)})\d+",
                na=False,
            )
            normalized = normalized[exact_future & normalized["root"].isin(CORE_ROOTS)]
            normalized = normalized.dropna(subset=["close", "volume", "open_interest"])
            frames.append(normalized)

    bars = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if bars.duplicated(["date", "root", "symbol"]).any():
        raise Stage001Error(f"duplicate_contract_day:{month}")
    bars.sort_values(["date", "root", "symbol"], inplace=True)
    bars.reset_index(drop=True, inplace=True)
    bars.attrs["raw_row_count"] = int(raw_rows)
    return bars, [PurePosixPath(name).name for name in names]


def build_prior_oi_main_series(bars: pd.DataFrame) -> pd.DataFrame:
    required = {"date", "root", "symbol", "close", "volume", "open_interest"}
    missing = sorted(required - set(bars.columns))
    if missing:
        raise Stage001Error(f"bar_columns_missing:{','.join(missing)}")
    frame = bars[list(required)].copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    frame["root"] = frame["root"].astype(str).str.upper().str.strip()
    frame["symbol"] = frame["symbol"].astype(str).str.upper().str.strip()
    for column in ("close", "volume", "open_interest"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if frame.duplicated(["date", "root", "symbol"]).any():
        raise Stage001Error("duplicate_contract_day")
    if frame[["close", "volume", "open_interest"]].isna().any().any():
        raise Stage001Error("non_numeric_contract_bar")
    if not np.isfinite(frame[["close", "volume", "open_interest"]].to_numpy()).all():
        raise Stage001Error("nonfinite_contract_bar")

    dates = sorted(frame["date"].unique())
    roots = sorted(frame["root"].unique())
    if len(dates) < 2 or not roots:
        raise Stage001Error("insufficient_contract_history")

    selections: list[dict[str, object]] = []
    for date_index in range(1, len(dates)):
        date = pd.Timestamp(dates[date_index])
        expected_prior_date = pd.Timestamp(dates[date_index - 1])
        for root in roots:
            current = frame[(frame["date"].eq(date)) & (frame["root"].eq(root))]
            prior = frame[
                (frame["date"].eq(expected_prior_date)) & (frame["root"].eq(root))
            ][["symbol", "date", "open_interest", "volume"]].rename(
                columns={
                    "date": "prior_date",
                    "open_interest": "prior_open_interest",
                    "volume": "prior_volume",
                }
            )
            eligible = current.merge(prior, on="symbol", how="inner", validate="one_to_one")
            if eligible.empty:
                raise Stage001Error(
                    f"stale_prior_date:{root}:{date.date()}:{expected_prior_date.date()}"
                )
            eligible.sort_values(
                ["prior_open_interest", "prior_volume", "symbol"],
                ascending=[False, False, True],
                kind="mergesort",
                inplace=True,
            )
            chosen = eligible.iloc[0]
            selections.append(
                {
                    "date": date,
                    "root": root,
                    "symbol": chosen["symbol"],
                    "close": float(chosen["close"]),
                    "volume": float(chosen["volume"]),
                    "open_interest": float(chosen["open_interest"]),
                    "prior_date": pd.Timestamp(chosen["prior_date"]),
                    "prior_open_interest": float(chosen["prior_open_interest"]),
                    "prior_volume": float(chosen["prior_volume"]),
                    "expected_prior_date": expected_prior_date,
                }
            )

    selected = pd.DataFrame(selections).sort_values(["root", "date"]).reset_index(drop=True)
    previous_symbol = selected.groupby("root", sort=False)["symbol"].shift(1)
    previous_close = selected.groupby("root", sort=False)["close"].shift(1)
    has_previous = previous_symbol.notna()
    selected["same_contract"] = has_previous & selected["symbol"].eq(previous_symbol)
    selected["roll_event"] = (has_previous & ~selected["same_contract"]).astype(int)
    selected["product_return"] = 0.0
    same = selected["same_contract"]
    selected.loc[same, "product_return"] = (
        selected.loc[same, "close"] / previous_close.loc[same] - 1.0
    )
    selected.sort_values(["date", "root"], inplace=True)
    selected.reset_index(drop=True, inplace=True)
    return selected


def _rolling_compound(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window, min_periods=window).apply(
        lambda values: float(np.prod(1.0 + values) - 1.0),
        raw=True,
    )


def build_daily_factors(selected: pd.DataFrame) -> pd.DataFrame:
    required = {"date", "root", "product_return"}
    missing = sorted(required - set(selected.columns))
    if missing:
        raise Stage001Error(f"selected_columns_missing:{','.join(missing)}")
    frame = selected[list(required)].copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    frame["root"] = frame["root"].astype(str).str.upper().str.strip()
    frame["product_return"] = pd.to_numeric(frame["product_return"], errors="coerce")
    if frame.duplicated(["date", "root"]).any():
        raise Stage001Error("duplicate_selected_root_day")
    if set(frame["root"].unique()) != set(CORE_ROOTS):
        raise Stage001Error("selected_root_contract_mismatch")
    pivot = frame.pivot(index="date", columns="root", values="product_return").sort_index()
    pivot = pivot.reindex(columns=CORE_ROOTS)
    if pivot.isna().any().any():
        raise Stage001Error("selected_root_day_missing")
    if not np.isfinite(pivot.to_numpy()).all():
        raise Stage001Error("selected_return_nonfinite")

    equity_return = pivot[list(EQUITY_ROOTS)].mean(axis=1)
    rates_return = pivot[list(RATES_ROOTS)].mean(axis=1)
    equity_root_momentum = pd.DataFrame(
        {root: _rolling_compound(pivot[root], 60) for root in EQUITY_ROOTS},
        index=pivot.index,
    )
    equity_vol_20 = equity_return.rolling(20, min_periods=20).std(ddof=1)
    equity_vol_120 = equity_return.rolling(120, min_periods=120).std(ddof=1)
    rates_vol_20 = rates_return.rolling(20, min_periods=20).std(ddof=1)
    rates_vol_120 = rates_return.rolling(120, min_periods=120).std(ddof=1)
    complete_root_momentum = equity_root_momentum.notna().all(axis=1)

    factors = pd.DataFrame(index=pivot.index)
    factors.index.name = "date"
    factors["observations_since_start"] = np.arange(1, len(factors) + 1)
    for root in CORE_ROOTS:
        factors[f"{root}_return"] = pivot[root]
    factors["equity_return"] = equity_return
    factors["rates_return"] = rates_return
    factors["cffex_equity_momentum_60d"] = _rolling_compound(equity_return, 60)
    factors["cffex_rates_momentum_60d"] = _rolling_compound(rates_return, 60)
    factors["cffex_equity_vol_ratio_20_120"] = equity_vol_20 / equity_vol_120
    factors["cffex_rates_vol_ratio_20_120"] = rates_vol_20 / rates_vol_120
    factors["cffex_equity_rates_corr_60d"] = equity_return.rolling(
        60,
        min_periods=60,
    ).corr(rates_return)
    factors["cffex_equity_breadth_60d"] = (
        equity_root_momentum.gt(0.0).mean(axis=1).where(complete_root_momentum)
    )
    factors["cffex_equity_dispersion_60d"] = equity_root_momentum.std(
        axis=1,
        ddof=1,
    ).where(complete_root_momentum)
    return factors.reset_index()


def build_monthly_macro_features(
    factors: pd.DataFrame,
    eval_dates: list[pd.Timestamp] | tuple[pd.Timestamp, ...],
) -> pd.DataFrame:
    required = {"date", "observations_since_start", *MACRO_FEATURES}
    missing = sorted(required - set(factors.columns))
    if missing:
        raise Stage001Error(f"daily_factor_columns_missing:{','.join(missing)}")
    frame = factors[list(required)].copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    if frame["date"].duplicated().any():
        raise Stage001Error("duplicate_factor_date")
    frame.set_index("date", inplace=True)

    normalized_dates = [pd.Timestamp(value).normalize() for value in eval_dates]
    if len(normalized_dates) != len(set(normalized_dates)):
        raise Stage001Error("duplicate_eval_date")
    missing_dates = [date for date in normalized_dates if date not in frame.index]
    if missing_dates:
        raise Stage001Error(
            "eval_date_missing:" + ",".join(date.strftime("%Y-%m-%d") for date in missing_dates)
        )
    selected = frame.loc[normalized_dates].copy()
    incomplete = selected["observations_since_start"].lt(120)
    if incomplete.any():
        dates = selected.index[incomplete]
        raise Stage001Error(
            "window_incomplete:" + ",".join(date.strftime("%Y-%m-%d") for date in dates)
        )
    values = selected[list(MACRO_FEATURES)].apply(pd.to_numeric, errors="coerce")
    if values.isna().any().any() or not np.isfinite(values.to_numpy()).all():
        raise Stage001Error("monthly_macro_nonfinite")
    values.insert(0, "eval_date", selected.index)
    values.reset_index(drop=True, inplace=True)
    return values


def build_interaction_panel(
    monthly: pd.DataFrame,
    products: tuple[str, ...] | list[str],
) -> tuple[pd.DataFrame, list[str]]:
    required = {"eval_date", *MACRO_FEATURES}
    missing = sorted(required - set(monthly.columns))
    if missing:
        raise Stage001Error(f"monthly_macro_columns_missing:{','.join(missing)}")
    product_list = [str(product) for product in products]
    if len(product_list) != len(set(product_list)):
        raise Stage001Error("duplicate_formal_product")
    product_to_sector = {
        product: sector
        for sector, sector_products in SECTOR_PRODUCTS.items()
        for product in sector_products
    }
    unknown = [product for product in product_list if product not in product_to_sector]
    if unknown:
        raise Stage001Error(f"product_sector_missing:{','.join(unknown)}")

    macro = monthly[["eval_date", *MACRO_FEATURES]].copy()
    macro["eval_date"] = pd.to_datetime(macro["eval_date"]).dt.normalize()
    if macro["eval_date"].duplicated().any():
        raise Stage001Error("duplicate_monthly_eval_date")
    macro_values = macro[list(MACRO_FEATURES)].apply(pd.to_numeric, errors="coerce")
    if macro_values.isna().any().any() or not np.isfinite(macro_values.to_numpy()).all():
        raise Stage001Error("monthly_macro_nonfinite")
    macro[list(MACRO_FEATURES)] = macro_values

    rows: list[dict[str, object]] = []
    for record in macro.to_dict("records"):
        for product in product_list:
            sector = product_to_sector[product]
            row = {
                "eval_date": record["eval_date"],
                "product_vt_symbol": product,
                "sector": sector,
            }
            for feature in MACRO_FEATURES:
                row[feature] = float(record[feature])
            for candidate_sector in SECTOR_PRODUCTS:
                indicator = float(candidate_sector == sector)
                row[f"sector_{candidate_sector}"] = indicator
                for feature in MACRO_FEATURES:
                    row[f"{feature}_x_{candidate_sector}"] = float(record[feature]) * indicator
            rows.append(row)

    interaction_columns = [
        f"{feature}_x_{sector}"
        for sector in SECTOR_PRODUCTS
        for feature in MACRO_FEATURES
    ]
    feature_columns = [*MACRO_FEATURES, *SECTOR_COLUMNS, *interaction_columns]
    panel = pd.DataFrame(rows)
    return panel[["eval_date", "product_vt_symbol", "sector", *feature_columns]], feature_columns


def acquire_archives(
    raw_dir: Path,
    fetcher: Callable[[str], bytes],
    *,
    months: Sequence[str] | None = None,
    max_workers: int = 4,
    on_event: Callable[[str, dict[str, Any]], None] | None = None,
) -> tuple[list[dict[str, object]], pd.DataFrame]:
    month_list = list(SOURCE_MONTHS if months is None else months)
    if not month_list or len(month_list) != len(set(month_list)):
        raise Stage001Error("archive_month_contract_invalid")
    if any(not re.fullmatch(r"\d{6}", month) for month in month_list):
        raise Stage001Error("archive_month_contract_invalid")
    directory = Path(raw_dir)
    directory.mkdir(parents=True, exist_ok=True)

    def acquire_one(month: str) -> tuple[dict[str, object], pd.DataFrame]:
        path = directory / f"{month}.zip"
        if path.exists():
            try:
                content = path.read_bytes()
                bars, daily_files = parse_month_archive(month, content)
            except (OSError, Stage001Error) as exc:
                raise Stage001Error(f"existing_archive_invalid:{month}:{exc}") from exc
            source = "existing"
        else:
            last_error: Exception | None = None
            content = b""
            bars = pd.DataFrame()
            daily_files: list[str] = []
            for attempt in range(1, 4):
                try:
                    fetched = fetcher(month)
                    if not isinstance(fetched, bytes) or not fetched:
                        raise Stage001Error("archive_fetch_payload_invalid")
                    content = fetched
                    bars, daily_files = parse_month_archive(month, content)
                    _atomic_write_bytes(path, content)
                    break
                except Exception as exc:  # bounded acquisition captures transport and format errors
                    last_error = exc
                    if on_event is not None:
                        on_event(
                            "archive_attempt_failed",
                            {
                                "month": month,
                                "attempt": attempt,
                                "error": f"{type(exc).__name__}:{exc}",
                            },
                        )
                    if attempt < 3:
                        time.sleep(0.5 * attempt)
            else:
                raise Stage001Error(
                    f"archive_download_failed:{month}:{type(last_error).__name__}:{last_error}"
                ) from last_error
            source = "downloaded"
        record: dict[str, object] = {
            "month": month,
            "url": CFFEX_ARCHIVE_URL.format(month=month),
            "source": source,
            "archive_bytes": len(content),
            "daily_file_count": len(daily_files),
            "raw_row_count": int(bars.attrs.get("raw_row_count", 0)),
            "core_row_count": int(len(bars)),
            "sha256": _sha256_bytes(content),
        }
        if on_event is not None:
            on_event("archive_validated", record)
        return record, bars

    completed: dict[str, tuple[dict[str, object], pd.DataFrame]] = {}
    workers = max(1, min(int(max_workers), len(month_list)))
    executor = ThreadPoolExecutor(max_workers=workers)
    remaining = iter(month_list)
    futures = {}
    for _ in range(workers):
        try:
            month = next(remaining)
        except StopIteration:
            break
        futures[executor.submit(acquire_one, month)] = month
    try:
        while futures:
            future = next(as_completed(futures))
            month = futures.pop(future)
            completed[month] = future.result()
            try:
                next_month = next(remaining)
            except StopIteration:
                continue
            futures[executor.submit(acquire_one, next_month)] = next_month
    except Exception:
        for future in futures:
            future.cancel()
        executor.shutdown(wait=True, cancel_futures=True)
        raise
    else:
        executor.shutdown(wait=True)

    records = [completed[month][0] for month in sorted(month_list)]
    frames = [completed[month][1] for month in sorted(month_list)]
    bars = pd.concat(frames, ignore_index=True)
    if bars.duplicated(["date", "root", "symbol"]).any():
        raise Stage001Error("duplicate_contract_day_across_archives")
    bars.sort_values(["date", "root", "symbol"], inplace=True)
    bars.reset_index(drop=True, inplace=True)
    return records, bars


def aggregate_archive_hash(records: Sequence[dict[str, object]]) -> str:
    digest = hashlib.sha256()
    months: set[str] = set()
    for record in sorted(records, key=lambda item: str(item["month"])):
        month = str(record["month"])
        archive_digest = str(record["sha256"])
        if month in months or not re.fullmatch(r"\d{6}", month):
            raise Stage001Error("archive_identity_month_invalid")
        if not re.fullmatch(r"[0-9a-f]{64}", archive_digest):
            raise Stage001Error(f"archive_identity_sha_invalid:{month}")
        months.add(month)
        digest.update(month.encode("ascii"))
        digest.update(bytes.fromhex(archive_digest))
    return digest.hexdigest()


def load_fold_eval_dates(path: Path) -> tuple[list[pd.Timestamp], list[pd.Timestamp]]:
    frame = pd.read_csv(
        path,
        usecols=["test_eval_date", "train_eval_dates"],
        dtype=str,
    )
    oos_dates = sorted(
        {pd.Timestamp(value).normalize() for value in frame["test_eval_date"]}
    )
    train_dates: set[pd.Timestamp] = set()
    for value in frame["train_eval_dates"].fillna(""):
        train_dates.update(
            pd.Timestamp(token.strip()).normalize()
            for token in value.split(",")
            if token.strip()
        )
    return sorted(train_dates | set(oos_dates)), oos_dates


def evaluate_gates(metrics: dict[str, object]) -> tuple[dict[str, bool], list[str]]:
    side_effect_fields = (
        "label_value_read_count",
        "model_fit_count",
        "model_predict_count",
        "strategy_backtest_count",
        "holdout_read_count",
        "ctp_connection_count",
        "order_api_call_count",
        "production_write_count",
    )
    gates = {
        "identity_contract": bool(
            int(metrics.get("input_identity_mismatch_count", -1)) == 0
            and metrics.get("current_release_id") == EXPECTED_RELEASE_ID
            and metrics.get("current_strategy_id") == EXPECTED_STRATEGY_ID
            and bool(metrics.get("current_pointer_matches_release", False))
        ),
        "source_contract": bool(
            int(metrics.get("source_month_count", -1)) == 84
            and int(metrics.get("source_daily_file_count", -1)) == 1695
            and int(metrics.get("source_archive_bytes", -1)) == 26_066_955
            and int(metrics.get("source_raw_row_count", -1)) == 847_781
            and int(metrics.get("source_core_row_count", -1)) == 35_595
            and int(metrics.get("source_duplicate_key_count", -1)) == 0
            and metrics.get("source_aggregate_sha256")
            == EXPECTED_SOURCE_AGGREGATE_SHA256
            and metrics.get("source_first_date") == "2019-06-03"
            and metrics.get("source_last_date") == "2026-05-29"
        ),
        "pit_contract": bool(
            int(metrics.get("pit_root_count", -1)) == 6
            and int(metrics.get("pit_min_selected_days", -1)) == 1694
            and int(metrics.get("pit_max_selected_days", -1)) == 1694
            and metrics.get("pit_first_date") == "2019-06-04"
            and metrics.get("pit_last_date") == "2026-05-29"
            and bool(metrics.get("pit_all_roots_date_contract_match", False))
            and int(metrics.get("pit_future_row_count", -1)) == 0
            and int(metrics.get("pit_stale_prior_row_count", -1)) == 0
            and int(metrics.get("pit_fallback_row_count", -1)) == 0
            and int(metrics.get("pit_roll_nonzero_return_count", -1)) == 0
        ),
        "eval_contract": bool(
            int(metrics.get("eval_date_count", -1)) == 77
            and int(metrics.get("oos_eval_date_count", -1)) == 50
            and int(metrics.get("eval_exact_count", -1)) == 77
            and int(metrics.get("eval_complete_120_count", -1)) == 77
            and int(metrics.get("oos_exact_count", -1)) == 50
            and int(metrics.get("oos_complete_120_count", -1)) == 50
        ),
        "feature_contract": bool(
            int(metrics.get("monthly_macro_row_count", -1)) == 77
            and int(metrics.get("macro_feature_count", -1)) == 7
            and int(metrics.get("interaction_panel_row_count", -1)) == 1386
            and int(metrics.get("formal_product_count", -1)) == 18
            and int(metrics.get("interaction_feature_count", -1)) == 39
            and int(metrics.get("minimum_products_per_month", -1)) == 18
            and int(metrics.get("maximum_products_per_month", -1)) == 18
            and int(metrics.get("nonfinite_feature_cell_count", -1)) == 0
        ),
        "expression_contract": bool(
            int(metrics.get("minimum_macro_unique_count", -1)) >= 20
            and float(metrics.get("minimum_macro_std", 0.0)) > 0.0
            and bool(metrics.get("sector_count_contract_match", False))
            and int(metrics.get("one_hot_violation_count", -1)) == 0
            and int(metrics.get("interaction_mismatch_cell_count", -1)) == 0
        ),
        "side_effect_contract": bool(
            all(int(metrics.get(field, -1)) == 0 for field in side_effect_fields)
        ),
        "durability_contract": bool(
            bool(metrics.get("execution_receipt_exists", False))
            and int(metrics.get("event_ledger_event_count", 0)) > 0
            and bool(metrics.get("atomic_publish_ready", False))
        ),
    }
    failures = [name for name, passed in gates.items() if not passed]
    return gates, failures


class DurableEventLedger:
    def __init__(self, path: Path, run_nonce: str) -> None:
        if not isinstance(run_nonce, str) or not re.fullmatch(r"[0-9a-f]{64}", run_nonce):
            raise Stage001Error("run_nonce_invalid")
        self.path = Path(path)
        self.run_nonce = run_nonce
        self._lock = threading.Lock()
        self._sequence = 0
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            for raw_line in self.path.read_text(encoding="utf-8").splitlines():
                event = json.loads(raw_line)
                self._sequence += 1
                if (
                    event.get("sequence") != self._sequence
                    or event.get("run_nonce") != self.run_nonce
                ):
                    raise Stage001Error("event_ledger_existing_invalid")

    @property
    def event_count(self) -> int:
        return self._sequence

    def record(self, event_type: str, **details: object) -> int:
        if not re.fullmatch(r"[a-z][a-z0-9_]*", event_type):
            raise Stage001Error(f"event_type_invalid:{event_type}")
        if any(key in {"sequence", "event_type", "run_nonce", "timestamp_utc"} for key in details):
            raise Stage001Error("event_reserved_field")
        with self._lock:
            sequence = self._sequence + 1
            event = {
                "sequence": sequence,
                "event_type": event_type,
                "run_nonce": self.run_nonce,
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                **details,
            }
            encoded = (
                json.dumps(event, ensure_ascii=False, sort_keys=True, default=_json_default)
                + "\n"
            ).encode("utf-8")
            with self.path.open("ab") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            self._sequence = sequence
            return sequence


def _manifest_files(directory: Path) -> dict[str, dict[str, object]]:
    root = directory.resolve()
    files: dict[str, dict[str, object]] = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise Stage001Error(f"manifest_symlink_forbidden:{path}")
        if not path.is_file() or path.name == "artifact_manifest.json":
            continue
        relative = path.relative_to(root).as_posix()
        size, _, digest = _sha256_file(path)
        files[relative] = {"size": size, "sha256": digest}
    return files


def write_artifact_manifest(directory: Path) -> dict[str, object]:
    root = Path(directory)
    if not root.is_dir():
        raise Stage001Error(f"artifact_directory_missing:{root}")
    manifest: dict[str, object] = {
        "schema_version": 1,
        "files": _manifest_files(root),
    }
    _atomic_write_json(root / "artifact_manifest.json", manifest)
    return manifest


def verify_artifact_bundle(directory: Path) -> dict[str, object]:
    root = Path(directory)
    manifest_path = root / "artifact_manifest.json"
    if not manifest_path.is_file():
        raise Stage001Error("manifest_missing")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Stage001Error("manifest_unreadable") from exc
    expected = manifest.get("files")
    if manifest.get("schema_version") != 1 or not isinstance(expected, dict):
        raise Stage001Error("manifest_schema_invalid")
    actual_names = set(_manifest_files(root))
    expected_names = set(expected)
    unmanifested = sorted(actual_names - expected_names)
    if unmanifested:
        raise Stage001Error(f"unmanifested_file:{','.join(unmanifested)}")
    missing = sorted(expected_names - actual_names)
    if missing:
        raise Stage001Error(f"manifest_mismatch:file_missing:{','.join(missing)}")
    mismatches: list[str] = []
    for name in sorted(expected_names):
        path = root / name
        size, _, digest = _sha256_file(path)
        item = expected[name]
        if size != int(item.get("size", -1)) or digest != str(item.get("sha256", "")):
            mismatches.append(name)
    if mismatches:
        raise Stage001Error(f"manifest_mismatch:{','.join(mismatches)}")
    return {
        "artifact_bundle_valid": True,
        "manifest_mismatch_count": 0,
        "manifested_file_count": len(expected_names),
    }


def publish_staged_directory(staging: Path, final: Path) -> None:
    staged = Path(staging)
    destination = Path(final)
    if destination.exists():
        raise Stage001Error(f"final_output_exists:{destination}")
    verify_artifact_bundle(staged)
    destination.parent.mkdir(parents=True, exist_ok=True)
    os.replace(staged, destination)
    verify_artifact_bundle(destination)


def _collect_input_identities() -> dict[str, dict[str, object]]:
    identities: dict[str, dict[str, object]] = {}
    for name, (path, expected_sha256) in EXPECTED_INPUT_HASHES.items():
        size, mtime_ns, actual_sha256 = _sha256_file(path)
        identities[name] = {
            "path": str(path.resolve()),
            "size": size,
            "mtime_ns": mtime_ns,
            "sha256": actual_sha256,
            "expected_sha256": expected_sha256,
            "matches_expected": actual_sha256 == expected_sha256,
        }
    return identities


def _load_formal_identity() -> tuple[dict[str, object], dict[str, object]]:
    current = json.loads(CURRENT_PATH.read_text(encoding="utf-8"))
    release_manifest = json.loads(RELEASE_MANIFEST_PATH.read_text(encoding="utf-8"))
    return current, release_manifest


def _official_fetch_month(month: str) -> bytes:
    url = CFFEX_ARCHIVE_URL.format(month=month)
    response = requests.get(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 Chrome/126.0 Safari/537.36"
            ),
            "Referer": "https://www.cffex.com.cn/lssjxz/",
            "Accept": "application/zip,application/octet-stream,*/*",
        },
        timeout=(15, 90),
    )
    if response.status_code != 200:
        raise Stage001Error(f"cffex_http_status:{month}:{response.status_code}")
    return bytes(response.content)


def _write_dataframe(path: Path, frame: pd.DataFrame, *, gzip: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    try:
        compression: object = {"method": "gzip", "mtime": 0} if gzip else None
        frame.to_csv(
            temporary,
            index=False,
            date_format="%Y-%m-%d",
            compression=compression,
        )
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _build_metrics(
    *,
    records: list[dict[str, object]],
    bars: pd.DataFrame,
    selected: pd.DataFrame,
    factors: pd.DataFrame,
    monthly: pd.DataFrame,
    panel: pd.DataFrame,
    feature_columns: list[str],
    eval_dates: list[pd.Timestamp],
    oos_dates: list[pd.Timestamp],
    identities_before: dict[str, dict[str, object]],
    identities_after: dict[str, dict[str, object]],
    current: dict[str, object],
    release_manifest: dict[str, object],
    ledger_event_count: int,
) -> dict[str, object]:
    identity_mismatches = sum(
        not bool(identity["matches_expected"])
        for identity in identities_before.values()
    )
    identity_mismatches += sum(
        not bool(identity["matches_expected"])
        for identity in identities_after.values()
    )
    identity_mismatches += sum(
        identities_before[name]["sha256"] != identities_after[name]["sha256"]
        for name in identities_before
    )

    root_stats = selected.groupby("root")["date"].agg(["size", "min", "max"])
    root_date_contract = bool(
        set(root_stats.index) == set(CORE_ROOTS)
        and root_stats["size"].eq(1694).all()
        and root_stats["min"].eq(pd.Timestamp("2019-06-04")).all()
        and root_stats["max"].eq(pd.Timestamp("2026-05-29")).all()
    )
    factor_frame = factors.copy()
    factor_frame["date"] = pd.to_datetime(factor_frame["date"]).dt.normalize()
    factor_frame.set_index("date", inplace=True)
    finite_by_date = pd.Series(False, index=factor_frame.index)
    factor_values = factor_frame[list(MACRO_FEATURES)].apply(pd.to_numeric, errors="coerce")
    finite_by_date.loc[:] = np.isfinite(factor_values.to_numpy()).all(axis=1)
    complete_by_date = factor_frame["observations_since_start"].ge(120) & finite_by_date
    eval_index = pd.DatetimeIndex(eval_dates)
    oos_index = pd.DatetimeIndex(oos_dates)
    eval_exact = eval_index.isin(factor_frame.index)
    oos_exact = oos_index.isin(factor_frame.index)
    eval_complete = sum(
        bool(complete_by_date.get(date, False)) for date in eval_index
    )
    oos_complete = sum(
        bool(complete_by_date.get(date, False)) for date in oos_index
    )

    products_per_month = panel.groupby("eval_date")["product_vt_symbol"].nunique()
    panel_values = panel[feature_columns].to_numpy(dtype="float64")
    unique_counts = monthly[list(MACRO_FEATURES)].nunique(dropna=True)
    standard_deviations = monthly[list(MACRO_FEATURES)].std(ddof=1)
    expected_sector_counts = {
        sector: len(products) for sector, products in SECTOR_PRODUCTS.items()
    }
    observed_sector_counts = (
        panel.groupby(["eval_date", "sector"]).size().unstack(fill_value=0)
    )
    sector_contract = bool(
        set(observed_sector_counts.columns) == set(expected_sector_counts)
        and all(
            observed_sector_counts[sector].eq(count).all()
            for sector, count in expected_sector_counts.items()
        )
    )
    one_hot_violations = int(
        (
            ~np.isclose(
                panel[list(SECTOR_COLUMNS)].sum(axis=1).to_numpy(dtype="float64"),
                1.0,
                rtol=0.0,
                atol=0.0,
            )
        ).sum()
    )
    interaction_mismatches = 0
    for sector in SECTOR_PRODUCTS:
        indicator = panel[f"sector_{sector}"].to_numpy(dtype="float64")
        for feature in MACRO_FEATURES:
            expected = panel[feature].to_numpy(dtype="float64") * indicator
            actual = panel[f"{feature}_x_{sector}"].to_numpy(dtype="float64")
            interaction_mismatches += int(
                (~np.isclose(actual, expected, rtol=0.0, atol=1e-12)).sum()
            )

    current_release = current.get("release_id")
    current_strategy = current.get("strategy_version")
    pointer_matches = bool(
        current_release == release_manifest.get("release_id") == EXPECTED_RELEASE_ID
        and current_strategy
        == release_manifest.get("strategy_version")
        == EXPECTED_STRATEGY_ID
    )
    metrics: dict[str, object] = {
        "input_identity_mismatch_count": int(identity_mismatches),
        "current_release_id": current_release,
        "current_strategy_id": current_strategy,
        "current_pointer_matches_release": pointer_matches,
        "source_month_count": len(records),
        "source_daily_file_count": int(sum(int(row["daily_file_count"]) for row in records)),
        "source_archive_bytes": int(sum(int(row["archive_bytes"]) for row in records)),
        "source_raw_row_count": int(sum(int(row["raw_row_count"]) for row in records)),
        "source_core_row_count": int(len(bars)),
        "source_duplicate_key_count": int(
            bars.duplicated(["date", "root", "symbol"]).sum()
        ),
        "source_aggregate_sha256": aggregate_archive_hash(records),
        "source_first_date": pd.Timestamp(bars["date"].min()).strftime("%Y-%m-%d"),
        "source_last_date": pd.Timestamp(bars["date"].max()).strftime("%Y-%m-%d"),
        "pit_root_count": int(selected["root"].nunique()),
        "pit_selected_days_by_root": {
            str(root): int(count)
            for root, count in selected.groupby("root").size().sort_index().items()
        },
        "pit_min_selected_days": int(root_stats["size"].min()),
        "pit_max_selected_days": int(root_stats["size"].max()),
        "pit_first_date": pd.Timestamp(selected["date"].min()).strftime("%Y-%m-%d"),
        "pit_last_date": pd.Timestamp(selected["date"].max()).strftime("%Y-%m-%d"),
        "pit_all_roots_date_contract_match": root_date_contract,
        "pit_future_row_count": int(selected["prior_date"].ge(selected["date"]).sum()),
        "pit_stale_prior_row_count": int(
            selected["prior_date"].ne(selected["expected_prior_date"]).sum()
        ),
        "pit_fallback_row_count": 0,
        "pit_roll_nonzero_return_count": int(
            (
                selected["roll_event"].eq(1)
                & selected["product_return"].abs().gt(1e-15)
            ).sum()
        ),
        "eval_date_count": len(eval_dates),
        "oos_eval_date_count": len(oos_dates),
        "eval_exact_count": int(eval_exact.sum()),
        "eval_complete_120_count": int(eval_complete),
        "oos_exact_count": int(oos_exact.sum()),
        "oos_complete_120_count": int(oos_complete),
        "monthly_macro_row_count": int(len(monthly)),
        "macro_feature_count": len(MACRO_FEATURES),
        "interaction_panel_row_count": int(len(panel)),
        "formal_product_count": len(FORMAL_PRODUCTS),
        "interaction_feature_count": len(feature_columns),
        "minimum_products_per_month": int(products_per_month.min()),
        "maximum_products_per_month": int(products_per_month.max()),
        "nonfinite_feature_cell_count": int((~np.isfinite(panel_values)).sum()),
        "macro_unique_counts": {str(key): int(value) for key, value in unique_counts.items()},
        "macro_standard_deviations": {
            str(key): float(value) for key, value in standard_deviations.items()
        },
        "minimum_macro_unique_count": int(unique_counts.min()),
        "minimum_macro_std": float(standard_deviations.min()),
        "sector_counts_per_month": expected_sector_counts,
        "sector_count_contract_match": sector_contract,
        "one_hot_violation_count": one_hot_violations,
        "interaction_mismatch_cell_count": int(interaction_mismatches),
        "label_value_read_count": 0,
        "model_fit_count": 0,
        "model_predict_count": 0,
        "strategy_backtest_count": 0,
        "holdout_read_count": 0,
        "ctp_connection_count": 0,
        "order_api_call_count": 0,
        "production_write_count": 0,
        "execution_receipt_exists": True,
        "event_ledger_event_count": int(ledger_event_count),
        "atomic_publish_ready": True,
    }
    return metrics


def _build_report(summary: dict[str, object]) -> str:
    failures = summary.get("failures", [])
    return "\n".join(
        [
            "# Stage001 CFFEX宏观状态无标签合同",
            "",
            f"- 决策：`{summary.get('decision', '')}`",
            f"- 官方源：`{summary.get('source_month_count', 0)}`月 / `{summary.get('source_daily_file_count', 0)}`日文件 / `{summary.get('source_core_row_count', 0)}`核心行。",
            f"- PIT主力：六根最少/最多 `{summary.get('pit_min_selected_days', 0)}/{summary.get('pit_max_selected_days', 0)}` 日。",
            f"- 正式月末：`{summary.get('eval_exact_count', 0)}/{summary.get('eval_date_count', 0)}`；OOS：`{summary.get('oos_exact_count', 0)}/{summary.get('oos_eval_date_count', 0)}`。",
            f"- 特征：`{summary.get('monthly_macro_row_count', 0)}`月 / `{summary.get('interaction_panel_row_count', 0)}`行 / `{summary.get('interaction_feature_count', 0)}`列。",
            f"- 失败门：`{','.join(str(item) for item in failures) or 'none'}`。",
            "- 标签值、模型fit/predict、策略回测、holdout、CTP、订单和生产写入均为0。",
            "",
        ]
    )


def _publish_technical_failure(
    staging: Path,
    *,
    run_nonce: str,
    receipt: dict[str, object],
    ledger: DurableEventLedger,
    error: Exception,
) -> Path:
    ledger.record(
        "technical_failure",
        error_type=type(error).__name__,
        error_message=str(error),
    )
    receipt.update(
        {
            "status": "technical_failure",
            "finished_at_utc": datetime.now(timezone.utc).isoformat(),
            "error_type": type(error).__name__,
            "error_message": str(error),
        }
    )
    _atomic_write_json(staging / "execution_receipt.json", receipt)
    _atomic_write_json(
        staging / "technical_failure.json",
        {
            "run_nonce": run_nonce,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "traceback": traceback.format_exc(),
            "labels_read": False,
            "models_fit": False,
            "backtests_run": False,
            "production_writes": 0,
        },
    )
    write_artifact_manifest(staging)
    failure_dir = (
        FINAL_OUTPUT_DIR.parent
        / f"stage001_cffex_macro_contract_failure_{run_nonce[:16]}"
    )
    publish_staged_directory(staging, failure_dir)
    return failure_dir


def run_stage001() -> dict[str, object]:
    if FINAL_OUTPUT_DIR.exists():
        raise Stage001Error(f"final_output_exists:{FINAL_OUTPUT_DIR}")
    FINAL_OUTPUT_DIR.parent.mkdir(parents=True, exist_ok=True)
    run_nonce = secrets.token_hex(32)
    staging = FINAL_OUTPUT_DIR.parent / f".{FINAL_OUTPUT_DIR.name}.tmp.{run_nonce}"
    if staging.exists():
        raise Stage001Error(f"staging_output_exists:{staging}")
    staging.mkdir(parents=True)
    receipt: dict[str, object] = {
        "schema_version": 1,
        "line_id": "futures_trend_xgboost_cffex_macro_state_residual",
        "stage": "Stage001",
        "scope": "single_authorized_label_free_cffex_source_and_feature_contract",
        "authorization_mode": "explicit_user_default_authorization_current_thread",
        "run_nonce": run_nonce,
        "status": "started",
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "network_started": False,
        "label_values_allowed": False,
        "model_execution_allowed": False,
        "backtest_allowed": False,
        "production_write_allowed": False,
        "runner_sha256": _sha256_file(Path(__file__))[2],
    }
    _atomic_write_json(staging / "execution_receipt.json", receipt)
    ledger = DurableEventLedger(staging / "event_ledger.ndjson", run_nonce)
    ledger.record("run_started", scope=receipt["scope"])

    try:
        identities_before = _collect_input_identities()
        initial_mismatches = sum(
            not bool(identity["matches_expected"])
            for identity in identities_before.values()
        )
        if initial_mismatches:
            raise Stage001Error(f"input_identity_mismatch:{initial_mismatches}")
        current, release_manifest = _load_formal_identity()
        ledger.record("input_identities_verified", identity_count=len(identities_before))

        receipt["network_started"] = True
        receipt["network_started_at_utc"] = datetime.now(timezone.utc).isoformat()
        receipt["input_identities_before"] = identities_before
        _atomic_write_json(staging / "execution_receipt.json", receipt)
        progress_lock = threading.Lock()
        progress = {"validated": 0}

        def archive_event(event_type: str, details: dict[str, Any]) -> None:
            ledger.record(event_type, **details)
            if event_type == "archive_attempt_failed":
                print(
                    f"[stage001] retry {details.get('month')} attempt={details.get('attempt')}",
                    flush=True,
                )
                return
            if event_type == "archive_validated":
                with progress_lock:
                    progress["validated"] += 1
                    completed = progress["validated"]
                if completed == 1 or completed % 10 == 0 or completed == len(SOURCE_MONTHS):
                    print(
                        f"[stage001] validated {completed}/{len(SOURCE_MONTHS)} archives",
                        flush=True,
                    )

        records, bars = acquire_archives(
            staging / "raw_archives",
            _official_fetch_month,
            months=SOURCE_MONTHS,
            max_workers=4,
            on_event=archive_event,
        )
        ledger.record(
            "archive_acquisition_completed",
            month_count=len(records),
            archive_bytes=sum(int(row["archive_bytes"]) for row in records),
        )

        selected = build_prior_oi_main_series(bars)
        factors = build_daily_factors(selected)
        eval_dates, oos_dates = load_fold_eval_dates(FOLD_PLAN_PATH)
        monthly = build_monthly_macro_features(factors, eval_dates)
        panel, feature_columns = build_interaction_panel(monthly, list(FORMAL_PRODUCTS))
        ledger.record(
            "transformations_completed",
            selected_rows=len(selected),
            monthly_rows=len(monthly),
            panel_rows=len(panel),
            feature_count=len(feature_columns),
        )

        _write_dataframe(staging / "source_archives.csv", pd.DataFrame(records))
        _write_dataframe(
            staging / "normalised_core_contract_bars.csv.gz",
            bars,
            gzip=True,
        )
        _write_dataframe(staging / "pit_main_series.csv.gz", selected, gzip=True)
        _write_dataframe(staging / "daily_factors.csv.gz", factors, gzip=True)
        _write_dataframe(staging / "monthly_macro_features.csv", monthly)
        _write_dataframe(staging / "interaction_panel.csv.gz", panel, gzip=True)
        shutil.copy2(FOLD_PLAN_PATH, staging / "copied_fold_plan.csv")
        ledger.record("data_artifacts_written", data_file_count=7)

        identities_after = _collect_input_identities()
        metrics = _build_metrics(
            records=records,
            bars=bars,
            selected=selected,
            factors=factors,
            monthly=monthly,
            panel=panel,
            feature_columns=feature_columns,
            eval_dates=eval_dates,
            oos_dates=oos_dates,
            identities_before=identities_before,
            identities_after=identities_after,
            current=current,
            release_manifest=release_manifest,
            ledger_event_count=ledger.event_count + 1,
        )
        gates, failures = evaluate_gates(metrics)
        decision = PASS_DECISION if not failures else FAIL_DECISION
        ledger.record("gates_evaluated", decision=decision, failures=failures)
        metrics["event_ledger_event_count"] = ledger.event_count
        gates, failures = evaluate_gates(metrics)
        decision = PASS_DECISION if not failures else FAIL_DECISION
        summary: dict[str, object] = {
            **metrics,
            "gates": gates,
            "all_gates_passed": not failures,
            "failures": failures,
            "decision": decision,
        }
        feature_contract = {
            "schema_version": 1,
            "source_months": list(SOURCE_MONTHS),
            "source_aggregate_sha256": EXPECTED_SOURCE_AGGREGATE_SHA256,
            "core_roots": list(CORE_ROOTS),
            "selection_rule": (
                "exact_previous_cffex_trading_day_open_interest_desc_"
                "then_volume_desc_then_symbol_asc"
            ),
            "roll_and_first_day_return": 0.0,
            "macro_features": list(MACRO_FEATURES),
            "sector_products": {
                sector: list(products) for sector, products in SECTOR_PRODUCTS.items()
            },
            "model_feature_count": len(feature_columns),
            "model_features": feature_columns,
            "labels_read": False,
            "models_fit": False,
            "predictions_generated": False,
            "backtests_run": False,
        }
        receipt.update(
            {
                "status": "completed",
                "finished_at_utc": datetime.now(timezone.utc).isoformat(),
                "decision": decision,
                "input_identities_after": identities_after,
            }
        )
        _atomic_write_json(staging / "execution_receipt.json", receipt)
        _atomic_write_json(
            staging / "input_identities.json",
            {"before": identities_before, "after": identities_after},
        )
        _atomic_write_json(staging / "feature_contract.json", feature_contract)
        _atomic_write_json(staging / "summary.json", summary)
        (staging / "report.md").write_text(_build_report(summary), encoding="utf-8")
        write_artifact_manifest(staging)
        publish_staged_directory(staging, FINAL_OUTPUT_DIR)
        return summary
    except Exception as exc:
        if staging.exists():
            failure_dir = _publish_technical_failure(
                staging,
                run_nonce=run_nonce,
                receipt=receipt,
                ledger=ledger,
                error=exc,
            )
            raise Stage001Error(
                f"stage001_technical_failure:{failure_dir}:{type(exc).__name__}:{exc}"
            ) from exc
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--authorized-label-free-audit", action="store_true")
    mode.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        result = verify_artifact_bundle(FINAL_OUTPUT_DIR)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    summary = run_stage001()
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=_json_default))


if __name__ == "__main__":
    main()
