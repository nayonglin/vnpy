"""Build and audit a line-local full-market TqSdk source as of 2026-06-30."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from datetime import datetime
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import time
from typing import Any, Final

import numpy as np
import pandas as pd


TOOL_DIR = Path(__file__).resolve().parent
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

import full_market_source_rebuild as core  # noqa: E402


LINE_DIR = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
SOURCE_START: Final = pd.Timestamp("2021-01-18")
CUTOFF: Final = pd.Timestamp("2026-06-30")
LINE_ID: Final = "futures_trend_xgboost_pit_full_market_source_rebuild"
PASS_DECISION: Final = (
    "stage001_source_rebuild_coverage_pass_allow_new_model_preregistration_only"
)
FAIL_DECISION: Final = "stage001_source_rebuild_coverage_fail_close_no_model"

FORMAL_RANKING_PATH = (
    WORKSPACE_ROOT
    / "research/lines/futures_trend_ai_xgboost_ensemble/artifacts/"
    "stage009_formal_full_ranking_recovery/formal_full_ranking.csv"
)
ARCHIVE_ROOT = (
    WORKSPACE_ROOT
    / "examples/portfolio_backtesting/downloaded_futures/tqsdk_daily_2010_2026_04"
)
PRIOR_LINE_DIR = (
    WORKSPACE_ROOT / "research/lines/futures_trend_xgboost_pit_full_market_one_slot"
)
COVERAGE_CORE_PATH = PRIOR_LINE_DIR / "tools/full_market_coverage.py"
SPEC_PATH = (
    LINE_DIR
    / "stages/20260904_1117_stage000_full_market_source_rebuild_preregistration.md"
)

INPUT_PATHS: Final = {
    "formal_ranking": FORMAL_RANKING_PATH,
    "archive_symbols": ARCHIVE_ROOT / "_symbols.csv",
    "archive_status": ARCHIVE_ROOT / "_download_status.csv",
    "archive_summary": ARCHIVE_ROOT / "_download_summary.json",
    "legacy_mapping": WORKSPACE_ROOT
    / "examples/portfolio_backtesting/backtest_outputs/"
    "tqsdk_all_futures_main_contract_mapping_2010_2026_04.csv",
    "prior_coverage_summary": PRIOR_LINE_DIR
    / "artifacts/stage001_full_market_coverage/stage001_summary.json",
    "prior_fail_record": PRIOR_LINE_DIR
    / "stages/20260903_2058_stage001_full_market_coverage_fail_stop.md",
    "coverage_core": COVERAGE_CORE_PATH,
}
EXPECTED_SHA256: Final = {
    "formal_ranking": "b2cb417b6c57a7679ae43a1e564c1e79683ca9644b3434cb6a3bfc9e039fcfc0",
    "archive_symbols": "620f6af9aeddcb9c575c82f28c76dcde2beaabc36199a9d778d3c7912163ea2d",
    "archive_status": "710b28800f8134c25a786d62bc696cdbe858a7a7f75debe2fa92cb6261b8920f",
    "archive_summary": "754b5bd227da5b410a5cc80ce977ca75c0f3e8b5b961659432f95ddc46fa032d",
    "legacy_mapping": "1fa32afab0bc9a490711aa66a716fa78fd52ebbb2c1680d77ce20eadcad617c2",
    "prior_coverage_summary": "7d1ea1bae0472243e6c9b9b6ad88a52b522a593dacbb840a84cc5b71a9632b93",
    "prior_fail_record": "248234d195068ef3de16bf22e0a90acf4218a8bd001c525aa686621769a8cb3e",
    "coverage_core": "f5751bea61b736d89848b228eee03959465a0be82ee007614eb4e80ecf072194",
}

FORMAL_COLUMNS: Final = ["eval_date", "product_vt_symbol", "score_rank", "score_type"]
EXPECTED_UNRESOLVED_CALENDAR_CONTRACTS: Final = {"CZCE.LR605", "DCE.bb2101"}


class Stage001Error(RuntimeError):
    """Raised when Stage001 must stop without publishing a successful receipt."""


def sha256_file(path: Path) -> str:
    return core.sha256_file(path)


def require_authorization(authorized: bool) -> None:
    if not authorized:
        raise Stage001Error("explicit_data_rebuild_authorization_required")


def verify_input_identities(
    paths: Mapping[str, Path], expected_sha256: Mapping[str, str]
) -> dict[str, dict[str, Any]]:
    if set(paths) != set(expected_sha256):
        raise Stage001Error("input_identity_keys_mismatch")
    identities: dict[str, dict[str, Any]] = {}
    for name in sorted(paths):
        path = Path(paths[name])
        if not path.is_file():
            raise Stage001Error(f"input_missing:{name}")
        digest = sha256_file(path)
        if digest != str(expected_sha256[name]):
            raise Stage001Error(f"input_sha256_drift:{name}")
        identities[name] = {
            "path": str(path.resolve()),
            "size": int(path.stat().st_size),
            "sha256": digest,
        }
    return identities


def serial_to_raw_frame(
    serial: pd.DataFrame,
    *,
    tq_symbol: str,
    source_start: pd.Timestamp,
    cutoff: pd.Timestamp,
) -> pd.DataFrame:
    """Convert one as-of backtest serial to a bounded, resumable raw CSV frame."""

    required = {"datetime", "open", "high", "low", "close", "volume", "open_oi", "close_oi"}
    if missing := sorted(required - set(serial.columns)):
        raise Stage001Error(f"fetched_bar_columns_missing:{tq_symbol}:{','.join(missing)}")
    frame = serial.loc[:, sorted(required)].copy()
    frame["datetime_local"] = pd.to_datetime(
        pd.to_numeric(frame["datetime"], errors="coerce"),
        unit="ns",
        errors="coerce",
        utc=True,
    ).dt.tz_convert("Asia/Shanghai")
    frame = frame[frame["datetime_local"].notna()].copy()
    frame["date"] = frame["datetime_local"].dt.tz_localize(None).dt.normalize()
    start = pd.Timestamp(source_start).normalize()
    end = pd.Timestamp(cutoff).normalize()
    if frame["date"].gt(end).any():
        raise Stage001Error(f"fetched_bar_after_cutoff:{tq_symbol}")
    frame = frame[frame["date"].between(start, end)].copy()
    for column in ("open", "high", "low", "close", "volume", "open_oi", "close_oi"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame[
        np.isfinite(frame["close"])
        & frame["close"].gt(0)
        & np.isfinite(frame["volume"])
        & frame["volume"].ge(0)
        & np.isfinite(frame["open_oi"])
        & frame["open_oi"].ge(0)
    ].copy()
    if frame.duplicated("date").any():
        raise Stage001Error(f"fetched_bar_date_duplicate:{tq_symbol}")
    frame["trade_date"] = frame["date"].dt.strftime("%Y-%m-%d")
    frame["datetime"] = frame["datetime_local"].astype(str)
    columns = [
        "trade_date",
        "datetime",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "open_oi",
        "close_oi",
    ]
    return frame[columns].sort_values("trade_date", kind="mergesort").reset_index(drop=True)


def build_output_paths(line_dir: Path = LINE_DIR) -> dict[str, Path]:
    output_dir = Path(line_dir) / "artifacts" / "stage001_full_market_source_rebuild"
    paths = {
        "output_dir": output_dir,
        "incremental_root": output_dir / "raw_incremental",
        "catalog": output_dir / "asof_contract_catalog.csv.gz",
        "mapping": output_dir / "pit_main_contract_mapping.csv.gz",
        "archive_inventory": output_dir / "archive_inventory.csv.gz",
        "acquisition_plan": output_dir / "acquisition_plan.csv",
        "prepare_receipt": output_dir / "prepare_receipt.json",
        "incremental_status": output_dir / "incremental_status.csv",
        "normalised_bars": output_dir / "normalised_daily_bars.csv.gz",
        "metadata": output_dir / "invariant_product_metadata.csv",
        "coverage": output_dir / "coverage_by_eval_product.csv.gz",
        "monthly_coverage": output_dir / "monthly_coverage.csv",
        "rejected": output_dir / "rejected_rows.csv.gz",
        "summary": output_dir / "stage001_summary.json",
        "report": output_dir / "report.md",
        "artifact_manifest": output_dir / "artifact_manifest.json",
    }
    return {
        name: core.assert_line_local_output(Path(line_dir), path)
        for name, path in paths.items()
    }


def continuous_symbols_from_catalog(catalog: pd.DataFrame) -> list[str]:
    required = {"product", "exchange_id", "product_vt_symbol"}
    if missing := sorted(required - set(catalog.columns)):
        raise Stage001Error(f"catalog_columns_missing:{','.join(missing)}")
    identities = catalog[["product", "exchange_id", "product_vt_symbol"]].drop_duplicates()
    if identities.duplicated("product_vt_symbol").any():
        raise Stage001Error("catalog_product_identity_ambiguous")
    return sorted(
        f"KQ.m@{str(row.exchange_id)}.{str(row.product)}"
        for row in identities.itertuples(index=False)
    )


def inspect_incremental_raw(
    path: Path,
    *,
    tq_symbol: str,
    source_start: pd.Timestamp,
    cutoff: pd.Timestamp,
) -> dict[str, Any]:
    file_path = Path(path)
    if not file_path.is_file() or file_path.stat().st_size == 0:
        raise Stage001Error(f"incremental_file_missing:{tq_symbol}")
    try:
        frame = pd.read_csv(file_path, encoding="utf-8-sig")
    except Exception as exc:
        raise Stage001Error(f"incremental_file_unreadable:{tq_symbol}:{exc!r}") from exc
    required = {
        "trade_date",
        "datetime",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "open_oi",
        "close_oi",
    }
    if missing := sorted(required - set(frame.columns)):
        raise Stage001Error(f"incremental_columns_missing:{tq_symbol}:{','.join(missing)}")
    dates = pd.to_datetime(frame["trade_date"], errors="raise").dt.normalize()
    start = pd.Timestamp(source_start).normalize()
    end = pd.Timestamp(cutoff).normalize()
    if dates.lt(start).any():
        raise Stage001Error(f"incremental_bar_before_source_start:{tq_symbol}")
    if dates.gt(end).any():
        raise Stage001Error(f"incremental_bar_after_cutoff:{tq_symbol}")
    if dates.duplicated().any():
        raise Stage001Error(f"incremental_bar_date_duplicate:{tq_symbol}")
    return {
        "tq_symbol": tq_symbol,
        "status": "fetched" if len(frame) else "empty",
        "rows": int(len(frame)),
        "min_date": dates.min().date().isoformat() if len(dates) else "",
        "max_date": dates.max().date().isoformat() if len(dates) else "",
        "path": str(file_path.resolve()),
        "sha256": sha256_file(file_path),
        "message": "",
    }


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if math.isnan(number) or math.isinf(number) else number
    if isinstance(value, (pd.Timestamp, datetime)):
        return None if pd.isna(value) else value.isoformat()
    if value is pd.NaT:
        return None
    return value


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    temp = path.with_name(f"{path.name}.tmp")
    temp.write_text(
        json.dumps(_json_safe(dict(payload)), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    temp.replace(path)


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    temp = path.with_name(f"{path.name}.tmp")
    options: dict[str, Any] = {
        "index": False,
        "encoding": "utf-8-sig",
        "date_format": "%Y-%m-%d",
        "float_format": "%.17g",
    }
    if path.suffix == ".gz":
        options["compression"] = {"method": "gzip", "compresslevel": 6, "mtime": 0}
    frame.to_csv(temp, **options)
    temp.replace(path)


def _credentials() -> tuple[str, str]:
    from vnpy.trader.setting import SETTINGS

    username = str(SETTINGS["datafeed.username"] or "")
    password = str(SETTINGS["datafeed.password"] or "")
    if not username or not password:
        raise Stage001Error("tqsdk_credentials_missing")
    return username, password


def credential_status() -> dict[str, Any]:
    username, password = _credentials()
    return {
        "datafeed_configured": True,
        "username_length": len(username),
        "password_length": len(password),
        "secret_values_persisted": False,
    }


def query_asof_catalog(
    *, cutoff: pd.Timestamp = CUTOFF, chunk_size: int = 80
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Query only commodity contracts visible to TqSdk at the frozen cutoff."""

    from tqsdk import TqApi, TqAuth, TqBacktest, TqSim

    username, password = _credentials()
    started = time.time()
    api = TqApi(
        TqSim(),
        backtest=TqBacktest(start_dt=cutoff.date(), end_dt=cutoff.date()),
        auth=TqAuth(username, password),
    )
    try:
        symbols = sorted(
            set(
                api.query_quotes(
                    ins_class="FUTURE", exchange_id=list(core.ALLOWED_EXCHANGES)
                )
            )
        )
        if not symbols:
            raise Stage001Error("asof_catalog_symbols_empty")
        frames: list[pd.DataFrame] = []
        for offset in range(0, len(symbols), chunk_size):
            chunk = symbols[offset : offset + chunk_size]
            info = pd.DataFrame(api.query_symbol_info(chunk)).copy()
            if "instrument_id" not in info.columns:
                if len(info) != len(chunk):
                    raise Stage001Error("catalog_info_identity_unavailable")
                info = info.reset_index(drop=True)
                info["instrument_id"] = chunk
            frames.append(info)
            if offset == 0 or offset + chunk_size >= len(symbols) or offset % 800 == 0:
                print(
                    f"[prepare] catalog metadata {min(offset + chunk_size, len(symbols))}/{len(symbols)}",
                    flush=True,
                )
        raw = pd.concat(frames, ignore_index=True)
    finally:
        api.close()
    receipt = {
        "query_mode": "TqBacktest_cutoff_day_contract_service",
        "catalog_as_of": cutoff.date().isoformat(),
        "raw_symbol_count": len(symbols),
        "raw_metadata_rows": len(raw),
        "chunk_size": chunk_size,
        "elapsed_seconds": round(time.time() - started, 3),
    }
    return raw, receipt


def query_exact_cont_calendar(
    continuous_symbols: list[str],
    *,
    source_start: pd.Timestamp = SOURCE_START,
    cutoff: pd.Timestamp = CUTOFF,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    from tqsdk import TqAuth
    from tqsdk.calendar import TqContCalendar

    username, password = _credentials()
    started = time.time()
    auth = TqAuth(username, password)
    auth.login()
    calendar = TqContCalendar(
        start_dt=source_start.date(),
        end_dt=cutoff.date(),
        symbols=continuous_symbols,
        headers=auth._base_headers,
    )
    frame = calendar.df.copy()
    receipt = {
        "query_mode": "TqContCalendar_exact_range",
        "source_start": source_start.date().isoformat(),
        "cutoff": cutoff.date().isoformat(),
        "continuous_symbol_count": len(continuous_symbols),
        "calendar_rows": len(frame),
        "elapsed_seconds": round(time.time() - started, 3),
    }
    return frame, receipt


def run_prepare(paths: Mapping[str, Path] | None = None) -> dict[str, Any]:
    output_paths = dict(paths or build_output_paths())
    output_dir = output_paths["output_dir"]
    output_dir.mkdir(parents=True, mode=0o700, exist_ok=True)
    os.chmod(output_dir, 0o700)
    output_paths["incremental_root"].mkdir(parents=True, mode=0o700, exist_ok=True)
    if output_paths["prepare_receipt"].exists():
        raise Stage001Error("prepare_receipt_already_exists")

    before = verify_input_identities(INPUT_PATHS, EXPECTED_SHA256)
    raw_catalog, catalog_receipt = query_asof_catalog()
    catalog = core.normalise_catalog(
        raw_catalog,
        catalog_as_of=CUTOFF,
        source_start=SOURCE_START,
        cutoff=CUTOFF,
    )
    continuous_symbols = continuous_symbols_from_catalog(catalog)
    raw_calendar, calendar_receipt = query_exact_cont_calendar(continuous_symbols)
    mapping = core.calendar_to_mapping(
        raw_calendar,
        catalog,
        source_start=SOURCE_START,
        cutoff=CUTOFF,
    )
    unresolved_contracts = set(
        mapping.loc[
            mapping["mapping_resolution"].eq("unresolved_not_in_asof_catalog"),
            "calendar_main_contract_tq",
        ].astype(str)
    )
    if unresolved_contracts != EXPECTED_UNRESOLVED_CALENDAR_CONTRACTS:
        raise Stage001Error(
            "unresolved_calendar_contract_identity_mismatch:"
            + ",".join(sorted(unresolved_contracts))
        )
    inventory = core.scan_archive_inventory(catalog, ARCHIVE_ROOT)
    required_contracts = set(mapping.loc[mapping["main_contract_tq"].ne(""), "main_contract_tq"])
    plan = core.build_acquisition_plan(
        catalog,
        inventory,
        required_contracts=required_contracts,
        source_start=SOURCE_START,
        cutoff=CUTOFF,
    )
    after = verify_input_identities(INPUT_PATHS, EXPECTED_SHA256)
    if before != after:
        raise Stage001Error("input_identity_changed_during_prepare")

    _write_csv(catalog, output_paths["catalog"])
    _write_csv(mapping, output_paths["mapping"])
    _write_csv(inventory, output_paths["archive_inventory"])
    _write_csv(plan, output_paths["acquisition_plan"])
    receipt = {
        "line_id": LINE_ID,
        "stage": "Stage001.prepare",
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source_start": SOURCE_START.date().isoformat(),
        "cutoff": CUTOFF.date().isoformat(),
        "catalog": catalog_receipt,
        "calendar": calendar_receipt,
        "normalised_contracts": len(catalog),
        "normalised_products": int(catalog["product_vt_symbol"].nunique()),
        "catalog_exclusions": {
            "dce_monthly_average_contracts": catalog.attrs.get(
                "excluded_dce_monthly_average_symbols", []
            )
        },
        "mapping_rows": len(mapping),
        "mapping_products": int(mapping["continuous_symbol_vt"].nunique()),
        "unresolved_calendar_rows": int(
            mapping["mapping_resolution"].eq("unresolved_not_in_asof_catalog").sum()
        ),
        "unresolved_calendar_contracts": sorted(unresolved_contracts),
        "required_mapping_contracts": len(required_contracts),
        "archive_inventory_status": {
            str(key): int(value)
            for key, value in inventory["status"].value_counts().sort_index().items()
        },
        "acquisition_actions": {
            str(key): int(value)
            for key, value in plan["action"].value_counts().sort_index().items()
        },
        "input_identities_before": before,
        "input_identities_after": after,
        "credential_status": credential_status(),
        "label_values_read": False,
        "model_fit_count": 0,
        "strategy_backtest_runs": 0,
        "production_files_written": 0,
    }
    _write_json(output_paths["prepare_receipt"], receipt)
    return receipt


def _incremental_path(root: Path, tq_symbol: str) -> Path:
    exchange, symbol = tq_symbol.split(".", 1)
    path = Path(root) / exchange / f"{symbol}.csv.gz"
    return core.assert_line_local_output(LINE_DIR, path)


def _write_incremental_raw(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    _write_csv(frame, path)


def fetch_asof_history_batch(
    symbols: list[str],
    *,
    source_start: pd.Timestamp = SOURCE_START,
    cutoff: pd.Timestamp = CUTOFF,
) -> tuple[dict[str, pd.DataFrame], dict[str, str]]:
    """Fetch full daily serials from a one-day cutoff backtest session."""

    from tqsdk import TqApi, TqAuth, TqBacktest, TqSim

    username, password = _credentials()
    data_length = min(
        10_000,
        max(1_000, int((cutoff - source_start).days * 5 / 7) + 500),
    )
    api = TqApi(
        TqSim(),
        backtest=TqBacktest(start_dt=cutoff.date(), end_dt=cutoff.date()),
        auth=TqAuth(username, password),
    )
    frames: dict[str, pd.DataFrame] = {}
    errors: dict[str, str] = {}
    try:
        for tq_symbol in symbols:
            try:
                serial = api.get_kline_serial(
                    tq_symbol, duration_seconds=86_400, data_length=data_length
                )
                frames[tq_symbol] = serial_to_raw_frame(
                    serial.copy(deep=True),
                    tq_symbol=tq_symbol,
                    source_start=source_start,
                    cutoff=cutoff,
                )
            except Exception as exc:
                errors[tq_symbol] = repr(exc)
    finally:
        api.close()
    return frames, errors


def _read_status(path: Path) -> pd.DataFrame:
    columns = [
        "tq_symbol",
        "status",
        "rows",
        "min_date",
        "max_date",
        "path",
        "sha256",
        "message",
        "attempts",
        "updated_at",
    ]
    if not path.is_file():
        return pd.DataFrame(columns=columns)
    frame = pd.read_csv(path, encoding="utf-8-sig").fillna("")
    for column in columns:
        if column not in frame.columns:
            frame[column] = ""
    return frame[columns]


def _upsert_status(status: pd.DataFrame, receipt: Mapping[str, Any]) -> pd.DataFrame:
    row = dict(receipt)
    row.setdefault("attempts", 1)
    row["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    existing_attempts = 0
    if not status.empty and status["tq_symbol"].astype(str).eq(str(row["tq_symbol"])).any():
        mask = status["tq_symbol"].astype(str).eq(str(row["tq_symbol"]))
        existing_attempts = int(pd.to_numeric(status.loc[mask, "attempts"], errors="coerce").fillna(0).max())
        status = status.loc[~mask].copy()
    row["attempts"] = max(int(row.get("attempts", 1)), existing_attempts + 1)
    return pd.concat([status, pd.DataFrame([row])], ignore_index=True).sort_values(
        "tq_symbol", kind="mergesort"
    ).reset_index(drop=True)


def run_acquire(
    paths: Mapping[str, Path] | None = None,
    *,
    batch_size: int = 20,
) -> dict[str, Any]:
    output_paths = dict(paths or build_output_paths())
    if batch_size <= 0:
        raise Stage001Error("batch_size_invalid")
    if not output_paths["prepare_receipt"].is_file():
        raise Stage001Error("prepare_receipt_missing")
    plan = pd.read_csv(output_paths["acquisition_plan"], encoding="utf-8-sig")
    fetch_symbols = sorted(
        plan.loc[plan["action"].eq("fetch_asof_history"), "tq_symbol"].astype(str)
    )
    status = _read_status(output_paths["incremental_status"])

    pending: list[str] = []
    for tq_symbol in fetch_symbols:
        raw_path = _incremental_path(output_paths["incremental_root"], tq_symbol)
        if raw_path.is_file():
            receipt = inspect_incremental_raw(
                raw_path,
                tq_symbol=tq_symbol,
                source_start=SOURCE_START,
                cutoff=CUTOFF,
            )
            receipt["message"] = "resume_revalidated"
            status = _upsert_status(status, receipt)
        else:
            pending.append(tq_symbol)
    _write_csv(status, output_paths["incremental_status"])

    total = len(pending)
    for offset in range(0, total, batch_size):
        batch = pending[offset : offset + batch_size]
        frames, errors = fetch_asof_history_batch(batch)
        for tq_symbol in batch:
            raw_path = _incremental_path(output_paths["incremental_root"], tq_symbol)
            if tq_symbol in frames:
                _write_incremental_raw(frames[tq_symbol], raw_path)
                receipt = inspect_incremental_raw(
                    raw_path,
                    tq_symbol=tq_symbol,
                    source_start=SOURCE_START,
                    cutoff=CUTOFF,
                )
            else:
                receipt = {
                    "tq_symbol": tq_symbol,
                    "status": "failed",
                    "rows": 0,
                    "min_date": "",
                    "max_date": "",
                    "path": str(raw_path),
                    "sha256": "",
                    "message": errors.get(tq_symbol, "unknown_fetch_failure"),
                }
            status = _upsert_status(status, receipt)
        _write_csv(status, output_paths["incremental_status"])
        print(
            f"[acquire] {min(offset + batch_size, total)}/{total} "
            f"status={status['status'].value_counts().to_dict()}",
            flush=True,
        )

    failed = status[status["status"].eq("failed") & status["tq_symbol"].isin(fetch_symbols)]
    if not failed.empty:
        retry_symbols = sorted(failed["tq_symbol"].astype(str).tolist())
        print(f"[acquire] retrying {len(retry_symbols)} failed contracts one by one", flush=True)
        for tq_symbol in retry_symbols:
            frames, errors = fetch_asof_history_batch([tq_symbol])
            raw_path = _incremental_path(output_paths["incremental_root"], tq_symbol)
            if tq_symbol in frames:
                _write_incremental_raw(frames[tq_symbol], raw_path)
                receipt = inspect_incremental_raw(
                    raw_path,
                    tq_symbol=tq_symbol,
                    source_start=SOURCE_START,
                    cutoff=CUTOFF,
                )
            else:
                receipt = {
                    "tq_symbol": tq_symbol,
                    "status": "failed",
                    "rows": 0,
                    "min_date": "",
                    "max_date": "",
                    "path": str(raw_path),
                    "sha256": "",
                    "message": errors.get(tq_symbol, "unknown_fetch_failure"),
                }
            status = _upsert_status(status, receipt)
            _write_csv(status, output_paths["incremental_status"])

    relevant = status[status["tq_symbol"].isin(fetch_symbols)].copy()
    summary = {
        "line_id": LINE_ID,
        "stage": "Stage001.acquire",
        "planned_fetch_contracts": len(fetch_symbols),
        "status_counts": {
            str(key): int(value)
            for key, value in relevant["status"].value_counts().sort_index().items()
        },
        "failed_contracts": sorted(
            relevant.loc[relevant["status"].eq("failed"), "tq_symbol"].astype(str).tolist()
        ),
        "label_values_read": False,
        "model_fit_count": 0,
        "strategy_backtest_runs": 0,
        "production_files_written": 0,
    }
    return summary


def _load_coverage_core() -> Any:
    spec = importlib.util.spec_from_file_location("frozen_full_market_coverage", COVERAGE_CORE_PATH)
    if spec is None or spec.loader is None:
        raise Stage001Error("coverage_core_import_spec_missing")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _coverage_config(coverage_core: Any) -> Any:
    return coverage_core.CoverageConfig(
        eval_start=pd.Timestamp("2022-01-28"),
        eval_end=CUTOFF,
        expected_months=54,
        expected_ranks_per_month=18,
        expected_static_products=18,
        replacement_rank=10,
        minimum_mapping_days=252,
        minimum_valid_close_days=241,
        activity_window_days=60,
        minimum_activity_ratio=0.90,
        minimum_curve_contracts=2,
        minimum_total_eligible=30,
        minimum_action_months=36,
        minimum_challengers=10,
        capital=150_000.0,
        conservative_margin_ratio=0.15,
    )


def _load_source_bars(
    plan: pd.DataFrame,
    status: pd.DataFrame,
    *,
    incremental_root: Path,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    status_by_symbol = status.set_index("tq_symbol", drop=False) if not status.empty else status
    frames: list[pd.DataFrame] = []
    source_rows = 0
    before_dropped = 0
    after_dropped = 0
    missing_required: list[str] = []
    source_files: list[dict[str, Any]] = []
    for row in plan.sort_values("tq_symbol", kind="mergesort").itertuples(index=False):
        tq_symbol = str(row.tq_symbol)
        action = str(row.action)
        if action == "skip_unreferenced_expired_missing":
            continue
        if action == "reuse_archive":
            path = Path(str(row.archive_path))
            if not path.is_file() or sha256_file(path) != str(row.archive_sha256):
                raise Stage001Error(f"archive_identity_drift:{tq_symbol}")
            source_kind = "archive_tqsdk_expired_snapshot"
        else:
            path = _incremental_path(incremental_root, tq_symbol)
            if tq_symbol not in status_by_symbol.index:
                if bool(row.required_by_mapping):
                    missing_required.append(tq_symbol)
                continue
            status_row = status_by_symbol.loc[tq_symbol]
            if isinstance(status_row, pd.DataFrame):
                raise Stage001Error(f"incremental_status_duplicate:{tq_symbol}")
            if str(status_row["status"]) not in {"fetched", "empty"}:
                if bool(row.required_by_mapping):
                    missing_required.append(tq_symbol)
                continue
            if not path.is_file() or sha256_file(path) != str(status_row["sha256"]):
                raise Stage001Error(f"incremental_identity_drift:{tq_symbol}")
            source_kind = "incremental_tqsdk_cutoff_backtest"
        raw = pd.read_csv(path, encoding="utf-8-sig")
        bars, diagnostics = core.normalise_raw_bars(
            raw,
            tq_symbol=tq_symbol,
            source_start=SOURCE_START,
            cutoff=CUTOFF,
            source_kind=source_kind,
        )
        frames.append(bars)
        source_rows += int(diagnostics["source_rows"])
        before_dropped += int(diagnostics["rows_before_start_dropped"])
        after_dropped += int(diagnostics["rows_after_cutoff_dropped"])
        source_files.append(
            {
                "tq_symbol": tq_symbol,
                "source_kind": source_kind,
                "path": str(path.resolve()),
                "sha256": sha256_file(path),
                "normalised_rows": int(len(bars)),
            }
        )
    if missing_required:
        raise Stage001Error(
            "required_mapping_contract_source_missing:" + ",".join(sorted(set(missing_required)))
        )
    bars = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    keys = ["datetime", "symbol", "exchange", "interval"]
    if not bars.empty and bars.duplicated(keys).any():
        raise Stage001Error("normalised_bar_duplicate")
    if not bars.empty:
        bars = bars.sort_values(keys, kind="mergesort").reset_index(drop=True)
    return bars, {
        "source_file_count": len(source_files),
        "source_rows": source_rows,
        "normalised_rows": len(bars),
        "rows_before_start_dropped": before_dropped,
        "rows_after_cutoff_dropped": after_dropped,
        "source_files": source_files,
    }


def _assert_repeat_exact(first: Any, second: Any) -> None:
    pd.testing.assert_frame_equal(first.coverage, second.coverage, check_exact=True)
    pd.testing.assert_frame_equal(first.monthly, second.monthly, check_exact=True)
    pd.testing.assert_frame_equal(first.rejected, second.rejected, check_exact=True)
    if first.diagnostics != second.diagnostics:
        raise Stage001Error("repeat_diagnostics_mismatch")


def run_audit(paths: Mapping[str, Path] | None = None) -> dict[str, Any]:
    output_paths = dict(paths or build_output_paths())
    if output_paths["summary"].exists():
        raise Stage001Error("stage001_summary_already_exists")
    before = verify_input_identities(INPUT_PATHS, EXPECTED_SHA256)
    catalog = pd.read_csv(output_paths["catalog"], encoding="utf-8-sig")
    mapping = pd.read_csv(output_paths["mapping"], encoding="utf-8-sig")
    plan = pd.read_csv(output_paths["acquisition_plan"], encoding="utf-8-sig")
    status = _read_status(output_paths["incremental_status"])
    bars, source_diagnostics = _load_source_bars(
        plan,
        status,
        incremental_root=output_paths["incremental_root"],
    )
    metadata, metadata_diagnostics = core.build_invariant_product_metadata(catalog)
    ranking = pd.read_csv(
        FORMAL_RANKING_PATH,
        usecols=FORMAL_COLUMNS,
        encoding="utf-8-sig",
    )
    coverage_core = _load_coverage_core()
    config = _coverage_config(coverage_core)
    first = coverage_core.build_coverage(ranking, mapping, bars, metadata, config)
    second = coverage_core.build_coverage(ranking, mapping, bars, metadata, config)
    _assert_repeat_exact(first, second)
    assessment = coverage_core.assess_coverage(first, config)

    fetch_symbols = set(
        plan.loc[plan["action"].eq("fetch_asof_history"), "tq_symbol"].astype(str)
    )
    relevant_status = status[status["tq_symbol"].isin(fetch_symbols)]
    source_gates = {
        "catalog_asof_exact_cutoff": bool(
            pd.to_datetime(catalog["catalog_as_of"], errors="raise")
            .dt.normalize()
            .eq(CUTOFF)
            .all()
        ),
        "mapping_future_rows_zero": bool(
            pd.to_datetime(mapping["date"], errors="raise").dt.normalize().le(CUTOFF).all()
        ),
        "bar_future_rows_zero": bool(
            pd.to_datetime(bars["datetime"], errors="raise").dt.normalize().le(CUTOFF).all()
        ),
        "raw_rows_after_cutoff_dropped_zero": source_diagnostics[
            "rows_after_cutoff_dropped"
        ]
        == 0,
        "fetch_status_complete": len(relevant_status) == len(fetch_symbols),
        "fetch_failed_zero": int(relevant_status["status"].eq("failed").sum()) == 0,
        "normalised_bar_duplicates_zero": not bars.duplicated(
            ["datetime", "symbol", "exchange", "interval"]
        ).any(),
        "mapping_contracts_in_catalog": set(
            mapping.loc[mapping["main_contract_tq"].fillna("").ne(""), "main_contract_tq"]
        ).issubset(set(catalog["tq_symbol"])),
        "label_values_read_zero": True,
        "model_fit_zero": True,
        "strategy_backtest_zero": True,
        "production_writes_zero": True,
    }
    all_passed = bool(all(source_gates.values()) and assessment["all_gates_passed"])
    assessment["original_coverage_decision"] = assessment["decision"]
    assessment["decision"] = PASS_DECISION if all_passed else FAIL_DECISION
    assessment["all_gates_passed"] = all_passed
    assessment["source_gates"] = source_gates

    after = verify_input_identities(INPUT_PATHS, EXPECTED_SHA256)
    if before != after:
        raise Stage001Error("input_identity_changed_during_audit")
    _write_csv(bars, output_paths["normalised_bars"])
    _write_csv(metadata, output_paths["metadata"])
    _write_csv(first.coverage, output_paths["coverage"])
    _write_csv(first.monthly, output_paths["monthly_coverage"])
    _write_csv(first.rejected, output_paths["rejected"])

    summary = {
        **assessment,
        "line_id": LINE_ID,
        "stage": "Stage001",
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "evidence_scope": "source_rebuild_and_coverage_only_no_labels_no_backtest",
        "source_start": SOURCE_START.date().isoformat(),
        "cutoff": CUTOFF.date().isoformat(),
        "catalog_contracts": len(catalog),
        "catalog_products": int(catalog["product_vt_symbol"].nunique()),
        "mapping_rows": len(mapping),
        "mapping_products": int(mapping["continuous_symbol_vt"].nunique()),
        "mapping_contracts": int(mapping["main_contract_tq"].replace("", np.nan).nunique()),
        "source_diagnostics": {
            key: value
            for key, value in source_diagnostics.items()
            if key != "source_files"
        },
        "metadata_diagnostics": metadata_diagnostics,
        "coverage_diagnostics": first.diagnostics,
        "acquisition_status_counts": {
            str(key): int(value)
            for key, value in relevant_status["status"].value_counts().sort_index().items()
        },
        "config": {
            "eval_start": pd.Timestamp(config.eval_start).date().isoformat(),
            "eval_end": pd.Timestamp(config.eval_end).date().isoformat(),
            "expected_months": config.expected_months,
            "minimum_mapping_days": config.minimum_mapping_days,
            "minimum_valid_close_days": config.minimum_valid_close_days,
            "activity_window_days": config.activity_window_days,
            "minimum_activity_ratio": config.minimum_activity_ratio,
            "minimum_curve_contracts": config.minimum_curve_contracts,
            "minimum_total_eligible": config.minimum_total_eligible,
            "minimum_action_months": config.minimum_action_months,
            "minimum_challengers": config.minimum_challengers,
            "capital": config.capital,
            "conservative_margin_ratio": config.conservative_margin_ratio,
        },
        "input_identities_before": before,
        "input_identities_after": after,
        "spec_identity": {
            "path": str(SPEC_PATH.resolve()),
            "sha256": sha256_file(SPEC_PATH) if SPEC_PATH.is_file() else "",
        },
        "implementation_identities": {
            "source_core": sha256_file(TOOL_DIR / "full_market_source_rebuild.py"),
            "runner": sha256_file(Path(__file__)),
            "frozen_coverage_core": sha256_file(COVERAGE_CORE_PATH),
        },
        "repeat_exact": True,
        "formal_columns_read": FORMAL_COLUMNS,
        "label_columns_read": [],
        "label_values_read": False,
        "sealed_holdout_files_read": [],
        "model_fit_count": 0,
        "model_predict_count": 0,
        "strategy_backtest_runs": 0,
        "ctp_connected": False,
        "order_api_called_count": 0,
        "production_files_written": 0,
        "independent_reviewer_required": False,
        "independent_reviewer_reason": "no_backtest_results_produced",
    }
    _write_json(output_paths["summary"], summary)
    report = (
        "# Stage001 全市场PIT数据源重建与覆盖审计\n\n"
        f"- 决策：`{summary['decision']}`。\n"
        f"- 截止日目录：`{summary['catalog_contracts']}`个合约、"
        f"`{summary['catalog_products']}`个商品品种。\n"
        f"- 映射：`{summary['mapping_rows']}`行、`{summary['mapping_products']}`个品种、"
        f"`{summary['mapping_contracts']}`个具体主力合约。\n"
        f"- 日线：`{summary['source_diagnostics']['normalised_rows']}`行；"
        f"截止日之后丢弃行=`{summary['source_diagnostics']['rows_after_cutoff_dropped']}`。\n"
        f"- 覆盖行/合格行/池外挑战行：`{summary['coverage_rows']}/"
        f"{summary['eligible_rows']}/{summary['challenger_rows']}`。\n"
        f"- 每月合格品种最小/中位/最大：`{summary['minimum_eligible_products']}` / "
        f"`{summary['median_eligible_products']:.1f}` / "
        f"`{summary['maximum_eligible_products']}`。\n"
        f"- A-rank10合格月/动作就绪月：`{summary['formal_replacement_eligible_months']}` / "
        f"`{summary['action_ready_months']}`；合格月池外挑战者最小值="
        f"`{summary['minimum_challengers_on_eligible_baseline_month']}`。\n"
        f"- source gates：`{json.dumps(source_gates, ensure_ascii=False, sort_keys=True)}`。\n"
        f"- coverage gates：`{json.dumps(summary['gates'], ensure_ascii=False, sort_keys=True)}`。\n"
        "- 未读取收益标签，未fit/predict，未运行策略回测，未连接CTP，未调用订单API，"
        "未写生产文件。\n"
        "- 即使通过，也只允许另立模型预注册，不自动授权XGBoost、真实引擎或上线。\n"
    )
    output_paths["report"].write_text(report, encoding="utf-8")

    artifact_names = [
        "catalog",
        "mapping",
        "archive_inventory",
        "acquisition_plan",
        "prepare_receipt",
        "incremental_status",
        "normalised_bars",
        "metadata",
        "coverage",
        "monthly_coverage",
        "rejected",
        "summary",
        "report",
    ]
    manifest = {
        "artifacts": {
            name: {
                "path": str(output_paths[name].resolve()),
                "size": int(output_paths[name].stat().st_size),
                "sha256": sha256_file(output_paths[name]),
            }
            for name in artifact_names
        },
        "source_files": source_diagnostics["source_files"],
    }
    _write_json(output_paths["artifact_manifest"], manifest)
    return summary


def run_stage001(*, phase: str, authorized: bool, batch_size: int) -> dict[str, Any]:
    require_authorization(authorized)
    if not SPEC_PATH.is_file():
        raise Stage001Error("stage000_preregistration_missing")
    if phase == "prepare":
        return run_prepare()
    if phase == "acquire":
        return run_acquire(batch_size=batch_size)
    if phase == "audit":
        return run_audit()
    if phase == "all":
        prepare = run_prepare()
        acquire = run_acquire(batch_size=batch_size)
        audit = run_audit()
        return {"prepare": prepare, "acquire": acquire, "audit": audit}
    raise Stage001Error(f"phase_invalid:{phase}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--phase", choices=("prepare", "acquire", "audit", "all"), default="all"
    )
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--authorized-data-rebuild", action="store_true")
    args = parser.parse_args()
    result = run_stage001(
        phase=args.phase,
        authorized=args.authorized_data_rebuild,
        batch_size=args.batch_size,
    )
    print(json.dumps(_json_safe(result), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
