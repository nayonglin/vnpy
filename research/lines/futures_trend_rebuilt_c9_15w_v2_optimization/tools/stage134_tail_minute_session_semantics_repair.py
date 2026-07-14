from __future__ import annotations

from datetime import datetime, time
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
from types import SimpleNamespace
from typing import Any, Mapping

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage134"
MODEL_TAG = "stage134_tail_minute_session_semantics_repair_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage134_tail_minute_session_semantics_repair"

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage134_tail_minute_session_semantics_repair"
TMP_ROOT = OUT / "tmp_downloads"
QUARANTINE_ROOT = OUT / "quarantine"
STAGES_DIR = LINE_DIR / "stages"

STAGE052_SCRIPT = LINE_DIR / "tools" / "stage052_tqsdk_jd_minute_backfill.py"
STAGE112_SCRIPT = LINE_DIR / "tools" / "stage112_strict_minute_content_gate.py"
STAGE020_PRODUCT_RETURNS = (
    LINE_DIR
    / "outputs"
    / "stage020_sqlite_jd_repair_xsmom_inputs"
    / "rebuilt_c9_v2_stage020_sqlite_jd_repair_xsmom_inputs_product_returns_stage020_sqlite_jd_repair_xsmom_inputs_v1.csv"
)
BACKFILL_ROOT = (
    ROOT
    / "examples"
    / "portfolio_backtesting"
    / "downloaded_futures"
    / "tqsdk_stage052_jd_minute_gap_backfill"
)

PLAN_PATH = OUT / f"{OUTPUT_PREFIX}_plan_{MODEL_TAG}.csv"
STATUS_PATH = OUT / f"{OUTPUT_PREFIX}_download_status_{MODEL_TAG}.csv"
TEMP_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_temp_audit_{MODEL_TAG}.csv"
PUBLISH_PATH = OUT / f"{OUTPUT_PREFIX}_publish_manifest_{MODEL_TAG}.csv"
POST_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_post_publish_audit_{MODEL_TAG}.csv"
SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
INPUT_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_input_audit_{MODEL_TAG}.csv"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

FIXED_CONTRACTS = (
    "cu2607.SHFE",
    "au2608.SHFE",
    "lh2609.DCE",
    "SM609.CZCE",
    "SH609.CZCE",
    "cu2608.SHFE",
)

ENABLE_DOWNLOAD = os.getenv("STAGE134_ENABLE_DOWNLOAD", "0").strip() == "1"
MAX_SECONDS_PER_SYMBOL = int(os.getenv("STAGE134_MAX_SECONDS_PER_SYMBOL", "900"))

SOURCE_LINKS = {
    "tqsdk_data_downloader": "https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.tools.download.html",
    "tqsdk_backtest": "https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.backtest.html",
    "vnpy_bardata": "https://github.com/vnpy/vnpy/blob/master/vnpy/trader/object.py",
}

REQUIRED_COLUMNS = (
    "vt_symbol",
    "bar_datetime",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "open_oi",
    "close_oi",
)


class IntegrityError(RuntimeError):
    pass


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if not np.isfinite(number) else number
    if isinstance(value, float):
        return None if not np.isfinite(value) else value
    if isinstance(value, (pd.Timestamp, datetime)):
        return "" if pd.isna(value) else value.isoformat()
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_无记录_"
    view = frame.head(max_rows).copy() if max_rows else frame.copy()
    return view.to_markdown(index=False)


def _normalised_dates(values: Any) -> pd.DatetimeIndex:
    dates = pd.to_datetime(pd.Series(list(values)), errors="coerce").dropna().dt.normalize()
    return pd.DatetimeIndex(sorted(dates.drop_duplicates().tolist()))


def load_expected_trade_dates(
    product_returns_path: Path = STAGE020_PRODUCT_RETURNS,
) -> tuple[dict[str, pd.DatetimeIndex], pd.DatetimeIndex]:
    data = pd.read_csv(product_returns_path, encoding="utf-8-sig")
    required = {"date", "main_contract_vt"}
    missing = required.difference(data.columns)
    if missing:
        raise IntegrityError(f"Stage020 product returns missing columns: {sorted(missing)}")
    data = data.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    data = data.dropna(subset=["date"])
    global_dates = _normalised_dates(data["date"])
    expected: dict[str, pd.DatetimeIndex] = {}
    for contract in FIXED_CONTRACTS:
        dates = _normalised_dates(data.loc[data["main_contract_vt"].astype(str).eq(contract), "date"])
        if dates.empty:
            raise IntegrityError(f"no Stage020 expected dates for {contract}")
        expected[contract] = dates
    return expected, global_dates


def _previous_global_date(value: pd.Timestamp, global_dates: pd.DatetimeIndex) -> pd.Timestamp:
    value = pd.Timestamp(value).normalize()
    prior = global_dates[global_dates < value]
    if prior.empty:
        raise IntegrityError(f"no previous global trading day before {value.date()}")
    return pd.Timestamp(prior[-1]).normalize()


def _optional_previous_global_date(
    value: pd.Timestamp,
    global_dates: pd.DatetimeIndex,
) -> pd.Timestamp | None:
    value = pd.Timestamp(value).normalize()
    prior = global_dates[global_dates < value]
    if prior.empty:
        return None
    return pd.Timestamp(prior[-1]).normalize()


def _session_bounds(
    expected_dates: pd.DatetimeIndex,
    global_dates: pd.DatetimeIndex,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    if expected_dates.empty:
        raise IntegrityError("expected trade dates are empty")
    first_date = pd.Timestamp(expected_dates[0]).normalize()
    signal_date = _optional_previous_global_date(first_date, global_dates)
    start = (
        first_date + pd.Timedelta(hours=8, minutes=55)
        if signal_date is None
        else signal_date + pd.Timedelta(hours=20, minutes=55)
    )
    end = pd.Timestamp(expected_dates[-1]).normalize() + pd.Timedelta(hours=15, minutes=15)
    return start, end


def _temp_path(contract_vt: str, root: Path = TMP_ROOT) -> Path:
    symbol, exchange = str(contract_vt).split(".", 1)
    return root / exchange / f"{symbol}_minute_backtest.csv"


def _final_path(contract_vt: str, root: Path = BACKFILL_ROOT) -> Path:
    symbol, exchange = str(contract_vt).split(".", 1)
    return root / exchange / f"{symbol}_minute_backtest.csv"


def build_session_plan(
    before_manifest: pd.DataFrame,
    expected_by_contract: Mapping[str, pd.DatetimeIndex],
    global_dates: pd.DatetimeIndex,
    temp_root: Path = TMP_ROOT,
    final_root: Path = BACKFILL_ROOT,
) -> pd.DataFrame:
    if "contract_vt" not in before_manifest.columns:
        raise IntegrityError("before manifest missing contract_vt")
    indexed = before_manifest.drop_duplicates("contract_vt", keep="last").set_index("contract_vt")
    rows: list[dict[str, Any]] = []
    for contract in FIXED_CONTRACTS:
        if contract not in indexed.index:
            raise IntegrityError(f"fixed contract missing from manifest: {contract}")
        if contract not in expected_by_contract:
            raise IntegrityError(f"fixed contract missing expected dates: {contract}")
        source = indexed.loc[contract]
        expected = _normalised_dates(expected_by_contract[contract])
        start, end = _session_bounds(expected, global_dates)
        symbol, exchange = contract.split(".", 1)
        rows.append(
            {
                "contract_vt": contract,
                "product_vt_symbol": str(source.get("product_vt_symbol", "")),
                "tq_symbol": f"{exchange}.{symbol}",
                "request_start_date": expected[0].date().isoformat(),
                "request_end_date": expected[-1].date().isoformat(),
                "download_start_datetime": start.strftime("%Y-%m-%d %H:%M:%S"),
                "download_end_datetime": end.strftime("%Y-%m-%d %H:%M:%S"),
                "expected_trade_date_count": int(len(expected)),
                "expected_trade_dates_json": json.dumps(
                    [value.date().isoformat() for value in expected], ensure_ascii=False
                ),
                "priority": str(source.get("priority", "P1_tail_contract_gap")),
                "output_path": str(_temp_path(contract, temp_root)),
                "final_output_path": str(_final_path(contract, final_root)),
            }
        )
    plan = pd.DataFrame(rows)
    if tuple(plan["contract_vt"].tolist()) != FIXED_CONTRACTS:
        raise IntegrityError("fixed contract order drift")
    return plan


def _empty_audit(row: Any, path: Path) -> dict[str, Any]:
    return {
        "contract_vt": str(row.contract_vt),
        "product_vt_symbol": str(getattr(row, "product_vt_symbol", "")),
        "temp_path": str(path),
        "final_output_path": str(getattr(row, "final_output_path", "")),
        "file_exists": path.exists(),
        "sha256": "",
        "read_error": "",
        "rows": 0,
        "expected_trade_date_count": 0,
        "natural_date_count": 0,
        "day_session_trade_date_count": 0,
        "day_session_dates_exact": False,
        "day_session_dates": "",
        "missing_day_session_dates": "",
        "extra_day_session_dates": "",
        "night_window_ready_count": 0,
        "day_window_ready_count": 0,
        "fill_window_coverage_count": 0,
        "fill_window_missing_dates": "",
        "unique_vt_symbol_count": 0,
        "first_bar_datetime": "",
        "last_bar_datetime": "",
        "out_of_bounds_row_count": 0,
        "ohlc_null_count": 0,
        "volume_null_count": 0,
        "oi_null_count": 0,
        "duplicate_key_count": 0,
        "monotonic_datetime": False,
        "ohlc_relation_error_count": 0,
        "negative_volume_count": 0,
        "negative_oi_count": 0,
        "strict_ready": False,
        "blocking_reason": "",
    }


def audit_session_file(
    row: Any,
    path: Path,
    expected_dates: pd.DatetimeIndex,
    global_dates: pd.DatetimeIndex,
) -> dict[str, Any]:
    result = _empty_audit(row, path)
    expected = _normalised_dates(expected_dates)
    result["expected_trade_date_count"] = int(len(expected))
    if not path.exists():
        result["blocking_reason"] = "missing_file"
        return result
    result["sha256"] = sha256_path(path)
    try:
        data = pd.read_csv(path, encoding="utf-8-sig")
    except Exception as exc:
        result["read_error"] = repr(exc)
        result["blocking_reason"] = "read_error"
        return result
    missing_columns = [column for column in REQUIRED_COLUMNS if column not in data.columns]
    if missing_columns:
        result["blocking_reason"] = "missing_columns:" + ",".join(missing_columns)
        return result
    if data.empty:
        result["blocking_reason"] = "empty_file"
        return result

    data = data.copy()
    data["bar_datetime_ts"] = pd.to_datetime(data["bar_datetime"], errors="coerce")
    for column in ("open", "high", "low", "close", "volume", "open_oi", "close_oi"):
        data[column] = pd.to_numeric(data[column], errors="coerce")

    result["rows"] = int(len(data))
    result["unique_vt_symbol_count"] = int(data["vt_symbol"].astype(str).nunique(dropna=True))
    valid_time = data["bar_datetime_ts"].dropna()
    if not valid_time.empty:
        result["first_bar_datetime"] = str(valid_time.min())
        result["last_bar_datetime"] = str(valid_time.max())
        result["natural_date_count"] = int(valid_time.dt.normalize().nunique())

    start = pd.Timestamp(row.download_start_datetime)
    end = pd.Timestamp(row.download_end_datetime)
    in_bounds = data["bar_datetime_ts"].ge(start) & data["bar_datetime_ts"].lt(end)
    result["out_of_bounds_row_count"] = int((~in_bounds).sum())

    clock = data["bar_datetime_ts"].dt.time
    day_mask = clock.ge(time(9, 0)) & clock.lt(time(15, 0))
    day_dates = _normalised_dates(data.loc[day_mask, "bar_datetime_ts"])
    expected_set = {pd.Timestamp(value).normalize() for value in expected}
    day_set = {pd.Timestamp(value).normalize() for value in day_dates}
    missing_day = sorted(expected_set.difference(day_set))
    extra_day = sorted(day_set.difference(expected_set))
    result["day_session_trade_date_count"] = int(len(day_dates))
    result["day_session_dates_exact"] = bool(day_set == expected_set)
    result["day_session_dates"] = "|".join(value.date().isoformat() for value in sorted(day_set))
    result["missing_day_session_dates"] = "|".join(value.date().isoformat() for value in missing_day)
    result["extra_day_session_dates"] = "|".join(value.date().isoformat() for value in extra_day)

    night_ready = 0
    day_ready = 0
    fill_ready = 0
    missing_fill: list[str] = []
    for fill_date in expected:
        fill_date = pd.Timestamp(fill_date).normalize()
        signal_date = _optional_previous_global_date(fill_date, global_dates)
        day_start = fill_date + pd.Timedelta(hours=9)
        day_end = day_start + pd.Timedelta(minutes=5)
        if signal_date is None:
            night_available = False
        else:
            night_start = signal_date + pd.Timedelta(hours=21)
            night_end = night_start + pd.Timedelta(minutes=5)
            night_available = bool(
                (data["bar_datetime_ts"].ge(night_start) & data["bar_datetime_ts"].lt(night_end)).any()
            )
        day_available = bool(
            (data["bar_datetime_ts"].ge(day_start) & data["bar_datetime_ts"].lt(day_end)).any()
        )
        night_ready += int(night_available)
        day_ready += int(day_available)
        fill_ready += int(night_available or day_available)
        if not (night_available or day_available):
            missing_fill.append(fill_date.date().isoformat())
    result["night_window_ready_count"] = int(night_ready)
    result["day_window_ready_count"] = int(day_ready)
    result["fill_window_coverage_count"] = int(fill_ready)
    result["fill_window_missing_dates"] = "|".join(missing_fill)

    result["ohlc_null_count"] = int(data[["open", "high", "low", "close"]].isna().any(axis=1).sum())
    result["volume_null_count"] = int(data["volume"].isna().sum())
    result["oi_null_count"] = int(data[["open_oi", "close_oi"]].isna().any(axis=1).sum())
    result["duplicate_key_count"] = int(data.duplicated(["vt_symbol", "bar_datetime_ts"]).sum())
    sorted_index = data.sort_values(["vt_symbol", "bar_datetime_ts"], kind="mergesort").index
    result["monotonic_datetime"] = bool(sorted_index.equals(data.index))
    high_ref = data[["open", "low", "close"]].max(axis=1)
    low_ref = data[["open", "high", "close"]].min(axis=1)
    result["ohlc_relation_error_count"] = int((data["high"].lt(high_ref) | data["low"].gt(low_ref)).sum())
    result["negative_volume_count"] = int(data["volume"].lt(0).sum())
    result["negative_oi_count"] = int(data[["open_oi", "close_oi"]].lt(0).any(axis=1).sum())

    checks = {
        "rows": result["rows"] > 0,
        "unique_vt_symbol": result["unique_vt_symbol_count"] == 1
        and str(data["vt_symbol"].dropna().astype(str).iloc[0]) == str(row.contract_vt),
        "day_session_dates": result["day_session_dates_exact"],
        "fill_window_coverage": result["fill_window_coverage_count"] == len(expected),
        "out_of_bounds": result["out_of_bounds_row_count"] == 0,
        "ohlc_null": result["ohlc_null_count"] == 0,
        "volume_null": result["volume_null_count"] == 0,
        "oi_null": result["oi_null_count"] == 0,
        "duplicate_key": result["duplicate_key_count"] == 0,
        "monotonic_datetime": result["monotonic_datetime"],
        "ohlc_relation": result["ohlc_relation_error_count"] == 0,
        "negative_volume": result["negative_volume_count"] == 0,
        "negative_oi": result["negative_oi_count"] == 0,
    }
    failed = [name for name, passed in checks.items() if not bool(passed)]
    result["strict_ready"] = not failed
    result["blocking_reason"] = "" if not failed else "strict_failed:" + ",".join(failed)
    return result


def audit_downloads(
    plan: pd.DataFrame,
    status: pd.DataFrame,
    expected_by_contract: Mapping[str, pd.DatetimeIndex],
    global_dates: pd.DatetimeIndex,
) -> pd.DataFrame:
    status_index = status.set_index("contract_vt").to_dict("index") if not status.empty else {}
    rows: list[dict[str, Any]] = []
    for row in plan.itertuples(index=False):
        contract = str(row.contract_vt)
        path = Path(str(row.output_path))
        audit = audit_session_file(row, path, expected_by_contract[contract], global_dates)
        status_row = status_index.get(contract, {})
        audit["download_status"] = str(status_row.get("status", ""))
        audit["download_rows"] = int(
            pd.to_numeric(pd.Series([status_row.get("rows", 0)]), errors="coerce").fillna(0).iloc[0]
        )
        audit["download_message"] = str(status_row.get("message", ""))
        if audit["download_status"] != "downloaded":
            audit["strict_ready"] = False
            extra = "download_status"
            reason = str(audit["blocking_reason"])
            audit["blocking_reason"] = f"{reason},{extra}" if reason else f"strict_failed:{extra}"
        rows.append(audit)
    return pd.DataFrame(rows)


def _quarantine_target(root: Path, category: str, contract_vt: str, source: Path) -> Path:
    _, exchange = str(contract_vt).split(".", 1)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return root / category / exchange / f"{source.stem}_{stamp}{source.suffix}"


def publish_verified(audit: pd.DataFrame, quarantine_root: Path = QUARANTINE_ROOT) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in audit.itertuples(index=False):
        contract = str(row.contract_vt)
        temp_path = Path(str(row.temp_path))
        final_path = Path(str(row.final_output_path))
        previous_backup = ""
        rejected_path = ""
        device_match = False
        old_final_preserved = final_path.exists()
        action = "no_temp_file"
        reason = str(row.blocking_reason)

        if temp_path.exists() and bool(row.strict_ready):
            final_path.parent.mkdir(parents=True, exist_ok=True)
            device_match = temp_path.stat().st_dev == final_path.parent.stat().st_dev
            hash_matches = sha256_path(temp_path) == str(row.sha256)
            if not device_match or not hash_matches:
                category = "cross_device_rejected" if not device_match else "hash_mismatch_rejected"
                target = _quarantine_target(quarantine_root, category, contract, temp_path)
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(temp_path, target)
                rejected_path = str(target)
                action = "quarantined"
                reason = category
            else:
                if final_path.exists():
                    backup = _quarantine_target(quarantine_root, "replaced_previous", contract, final_path)
                    backup.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(final_path, backup)
                    if sha256_path(backup) != sha256_path(final_path):
                        raise IntegrityError(f"previous file backup hash mismatch: {contract}")
                    previous_backup = str(backup)
                    os.replace(temp_path, final_path)
                    action = "replaced"
                else:
                    os.replace(temp_path, final_path)
                    action = "published"
                old_final_preserved = bool(previous_backup) or action == "published"
        elif temp_path.exists():
            target = _quarantine_target(quarantine_root, "strict_rejected", contract, temp_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(temp_path, target)
            rejected_path = str(target)
            action = "quarantined"
        rows.append(
            {
                "contract_vt": contract,
                "strict_ready": bool(row.strict_ready),
                "action": action,
                "temp_path": str(temp_path),
                "final_output_path": str(final_path),
                "previous_backup_path": previous_backup,
                "rejected_path": rejected_path,
                "publish_device_match": bool(device_match),
                "old_final_preserved_or_backed_up": bool(old_final_preserved),
                "published_exists": final_path.exists(),
                "published_sha256": sha256_path(final_path) if final_path.exists() else "",
                "blocking_reason": reason,
            }
        )
    return pd.DataFrame(rows)


def _build_file_index(root: Path = BACKFILL_ROOT) -> tuple[dict[str, Path], dict[str, list[str]]]:
    candidates: dict[str, list[Path]] = {}
    for path in root.glob("*/*_minute_backtest.csv"):
        exchange = path.parent.name
        symbol = path.name.replace("_completed_minute_backtest.csv", "").replace("_minute_backtest.csv", "")
        if symbol:
            candidates.setdefault(f"{symbol}.{exchange}", []).append(path)
    index: dict[str, Path] = {}
    conflicts: dict[str, list[str]] = {}
    for contract, paths in candidates.items():
        ordered = sorted(paths)
        if len(ordered) == 1:
            index[contract] = ordered[0]
        else:
            conflicts[contract] = [str(path) for path in ordered]
    return index, conflicts


def audit_final_universe(
    manifest: pd.DataFrame,
    product_returns_path: Path,
    global_dates: pd.DatetimeIndex,
    root: Path = BACKFILL_ROOT,
) -> pd.DataFrame:
    returns = pd.read_csv(product_returns_path, encoding="utf-8-sig")
    returns["date"] = pd.to_datetime(returns["date"], errors="coerce").dt.normalize()
    index, conflicts = _build_file_index(root)
    rows: list[dict[str, Any]] = []
    for source in manifest.itertuples(index=False):
        contract = str(source.contract_vt)
        expected = _normalised_dates(
            returns.loc[returns["main_contract_vt"].astype(str).eq(contract), "date"]
        )
        if expected.empty:
            rows.append(
                {
                    "contract_vt": contract,
                    "strict_ready": False,
                    "blocking_reason": "missing_expected_trade_dates",
                    "temp_path": "",
                    "final_output_path": "",
                }
            )
            continue
        start, end = _session_bounds(expected, global_dates)
        path = index.get(contract)
        row = SimpleNamespace(
            contract_vt=contract,
            product_vt_symbol=str(source.product_vt_symbol),
            download_start_datetime=start,
            download_end_datetime=end,
            final_output_path=str(path or ""),
        )
        if conflicts.get(contract):
            result = _empty_audit(row, Path(""))
            result["blocking_reason"] = "source_conflict"
            result["source_conflict_paths"] = "|".join(conflicts[contract])
        else:
            result = audit_session_file(row, path or Path("__missing__"), expected, global_dates)
            result["source_conflict_paths"] = ""
        result["temp_path"] = ""
        result["final_output_path"] = str(path or "")
        rows.append(result)
    return pd.DataFrame(rows)


def _empty_status() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "contract_vt",
            "tq_symbol",
            "download_start_datetime",
            "download_end_datetime",
            "status",
            "rows",
            "first_bar_datetime",
            "last_bar_datetime",
            "elapsed_seconds",
            "output_path",
            "sha256",
            "message",
        ]
    )


def _quarantine_stale_temp(plan: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    for row in plan.itertuples(index=False):
        path = Path(str(row.output_path))
        if not path.exists():
            continue
        target = _quarantine_target(QUARANTINE_ROOT, "stale_pre_run", str(row.contract_vt), path)
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(path, target)
        rows.append({"contract_vt": str(row.contract_vt), "source_path": str(path), "quarantine_path": str(target)})
    return pd.DataFrame(rows)


def _input_audit(paths: list[Path]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for path in paths:
        if path.exists():
            stat = path.stat()
            rows.append(
                {
                    "path": str(path),
                    "exists": True,
                    "bytes": int(stat.st_size),
                    "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                    "sha256": sha256_path(path),
                }
            )
        else:
            rows.append({"path": str(path), "exists": False, "bytes": 0, "mtime": "", "sha256": ""})
    return pd.DataFrame(rows)


def make_decision(
    download_enabled: bool,
    plan: pd.DataFrame,
    status: pd.DataFrame,
    temp_audit: pd.DataFrame,
    publish: pd.DataFrame,
    post_audit: pd.DataFrame,
    margin_ready: bool,
    margin_decision: str,
) -> dict[str, Any]:
    downloaded = int(status["status"].astype(str).eq("downloaded").sum()) if not status.empty else 0
    strict_ready = int(temp_audit["strict_ready"].astype(bool).sum()) if not temp_audit.empty else 0
    publish_ok = (
        int(publish["action"].astype(str).isin(["published", "replaced"]).sum()) if not publish.empty else 0
    )
    post_ready = int(post_audit["strict_ready"].astype(bool).sum()) if not post_audit.empty else 0
    post_total = int(len(post_audit))
    ready_no_jd = bool(
        download_enabled
        and len(plan) == len(FIXED_CONTRACTS)
        and strict_ready == len(FIXED_CONTRACTS)
        and publish_ok == len(FIXED_CONTRACTS)
        and post_total > 0
        and post_ready == post_total
    )
    if not download_enabled:
        decision = "stage134_session_semantics_plan_only"
    elif ready_no_jd and margin_ready:
        decision = "stage134_session_semantics_full_stage208_data_ready"
    elif ready_no_jd:
        decision = "stage134_session_semantics_minutes_ready_jd_margin_still_blocked"
    elif publish_ok > 0:
        decision = "stage134_session_semantics_partial_keep_blocked"
    else:
        decision = "stage134_session_semantics_failed_keep_blocked"
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "decision": decision,
        "download_enabled": bool(download_enabled),
        "fixed_contract_count": len(FIXED_CONTRACTS),
        "planned_contract_count": int(len(plan)),
        "downloaded_status_count": downloaded,
        "temp_strict_ready_count": strict_ready,
        "published_or_replaced_count": publish_ok,
        "post_publish_manifest_count": post_total,
        "post_publish_strict_ready_count": post_ready,
        "post_publish_strict_failed_count": post_total - post_ready,
        "jd_margin_history_ready": bool(margin_ready),
        "stage091_decision": str(margin_decision),
        "ready_for_no_jd_degraded_replay": bool(ready_no_jd),
        "ready_for_full_stage208_true_ledger": bool(ready_no_jd and margin_ready),
        "strategy_rule_created": False,
        "official_live_strategy_changed": False,
        "true_engine_run": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "formal_ab_triggered": False,
        "source_links": SOURCE_LINKS,
        "external_research_judgment": (
            "TqSdk 可按 datetime 推进分钟历史；Stage134 不把自然日数当交易日数，"
            "而是用 Stage020 交易日集合和 Stage208 固定成交窗口做准入。"
        ),
        "overfit_reflection_before": "否。固定修复 session 数据语义，不读取策略收益或按品种绩效筛选。",
        "overfit_reflection_after": "否。结果只改变数据是否可进入账本，不产生或优化策略绩效。",
        "continue_value_before": "有。Stage120 的三个 SHFE 失败已定位为可复现的自然日/交易日语义错误。",
        "continue_value_after": (
            "若 39/39 通过，可进入明确降级的 no-JD Stage208 一次性证伪；"
            "含 JD 的正式真账本仍需精确逐日保证金。"
        ),
        "outputs": {
            "plan": str(PLAN_PATH),
            "status": str(STATUS_PATH),
            "temp_audit": str(TEMP_AUDIT_PATH),
            "publish_manifest": str(PUBLISH_PATH),
            "post_publish_audit": str(POST_AUDIT_PATH),
            "summary": str(SUMMARY_PATH),
            "input_audit": str(INPUT_AUDIT_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }


def _write_report(
    decision: dict[str, Any],
    plan: pd.DataFrame,
    temp_audit: pd.DataFrame,
    publish: pd.DataFrame,
    post_audit: pd.DataFrame,
) -> None:
    failures = post_audit[~post_audit["strict_ready"].astype(bool)].copy() if not post_audit.empty else pd.DataFrame()
    lines = [
        "# Stage134 tail minute session semantics repair",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- 生成时间：`{decision['generated_at']}`",
        f"- 决策：`{decision['decision']}`",
        "- 阶段性质：修复夜盘自然日/交易日验收并原子补数；不回测收益、不改策略、不连接 CTP、不调用订单 API。",
        "",
        "## 外部调研与判断",
        "",
        "- TqSdk 官方支持 datetime 边界的历史分钟回放；成交推进语义仍需由本地数据合同约束。",
        "- 我的判断：自然日计数不能验证跨午夜夜盘；应使用 Stage020 实际交易日和 Stage208 固定成交窗口。",
        "",
        "## Gate",
        "",
        f"- temp_strict_ready_count：`{decision['temp_strict_ready_count']}/6`",
        f"- published_or_replaced_count：`{decision['published_or_replaced_count']}/6`",
        f"- post_publish_strict_ready_count：`{decision['post_publish_strict_ready_count']}/{decision['post_publish_manifest_count']}`",
        f"- ready_for_no_jd_degraded_replay：`{decision['ready_for_no_jd_degraded_replay']}`",
        f"- ready_for_full_stage208_true_ledger：`{decision['ready_for_full_stage208_true_ledger']}`",
        "",
        "## Plan",
        "",
        _md_table(plan, 20),
        "",
        "## Temp Audit",
        "",
        _md_table(temp_audit, 20),
        "",
        "## Publish",
        "",
        _md_table(publish, 20),
        "",
        "## Post Failures",
        "",
        _md_table(failures, 80),
        "",
        "## 反思",
        "",
        f"- 运行前过拟合反思：{decision['overfit_reflection_before']}",
        f"- 运行后过拟合反思：{decision['overfit_reflection_after']}",
        f"- 运行前继续价值反思：{decision['continue_value_before']}",
        f"- 运行后继续价值反思：{decision['continue_value_after']}",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_stage_record(decision: dict[str, Any]) -> Path:
    path = STAGES_DIR / f"{datetime.now():%Y%m%d_%H%M}_stage134_tail_minute_session_semantics_repair.md"
    text = f"""# Stage134 tail minute session semantics repair

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{decision['generated_at']}
- 阶段性质：修复夜盘自然日/交易日验收并原子补数；不回测收益、不改官方 live config、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发 A/B：否

## 外部调研与判断

- TqSdk 官方支持 datetime 边界的分钟历史回放；本阶段以 Stage020 实际交易日和 Stage208 固定成交窗口定义数据准入。
- 我的判断：Stage120 的 SHFE 失败是 session 语义 bug，不是行情缺失；不能通过放宽自然日计数解决。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage134_tail_minute_session_semantics_repair.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage134_tail_minute_session_semantics_repair.py`
- 新增参数：`STAGE134_ENABLE_DOWNLOAD`、`STAGE134_MAX_SECONDS_PER_SYMBOL`
- 修改参数：无正式策略参数修改
- 删除参数：无

## 结果

- decision：`{decision['decision']}`
- planned_contract_count：`{decision['planned_contract_count']}`
- downloaded_status_count：`{decision['downloaded_status_count']}`
- temp_strict_ready_count：`{decision['temp_strict_ready_count']}`
- published_or_replaced_count：`{decision['published_or_replaced_count']}`
- post_publish_strict_ready_count：`{decision['post_publish_strict_ready_count']}/{decision['post_publish_manifest_count']}`
- jd_margin_history_ready：`{decision['jd_margin_history_ready']}`
- ready_for_no_jd_degraded_replay：`{decision['ready_for_no_jd_degraded_replay']}`
- ready_for_full_stage208_true_ledger：`{decision['ready_for_full_stage208_true_ledger']}`
- 策略变更：`False`
- true engine run：`False`
- order API：`0`
- CTP：`False`

## 回测记录字段

- 本阶段不新增回测，因此不新增期末权益、总收益、最大回撤、Sharpe、滑点、交易次数、胜率。

## 过拟合反思

- 运行前：{decision['overfit_reflection_before']}
- 运行后：{decision['overfit_reflection_after']}

## 继续价值反思

- 运行前：{decision['continue_value_before']}
- 运行后：{decision['continue_value_after']}

## 输出

- report：`{REPORT_PATH}`
- decision：`{DECISION_PATH}`
- post_publish_audit：`{POST_AUDIT_PATH}`
"""
    path.write_text(text, encoding="utf-8")
    return path


def run(enable_download: bool | None = None) -> dict[str, Any]:
    enabled = ENABLE_DOWNLOAD if enable_download is None else bool(enable_download)
    mod052 = _load_module(STAGE052_SCRIPT, "stage052_for_stage134")
    mod112 = _load_module(STAGE112_SCRIPT, "stage112_for_stage134")
    OUT.mkdir(parents=True, exist_ok=True)
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    QUARANTINE_ROOT.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)

    expected, global_dates = load_expected_trade_dates()
    before_manifest = mod112.build_strict_manifest()
    plan = build_session_plan(before_manifest, expected, global_dates)
    stale = _quarantine_stale_temp(plan)
    if enabled:
        status, _ = mod052.run_backfill_download(plan, MAX_SECONDS_PER_SYMBOL)
    else:
        status = _empty_status()
    temp_audit = audit_downloads(plan, status, expected, global_dates)
    publish = publish_verified(temp_audit) if enabled else pd.DataFrame()
    post_audit = audit_final_universe(
        before_manifest,
        STAGE020_PRODUCT_RETURNS,
        global_dates,
    )
    margin_ready, margin_decision = mod112._stage091_margin_ready()
    decision = make_decision(
        enabled,
        plan,
        status,
        temp_audit,
        publish,
        post_audit,
        margin_ready,
        margin_decision,
    )
    summary = pd.DataFrame(
        [
            {
                "planned_contract_count": len(plan),
                "stale_temp_quarantined_count": len(stale),
                "downloaded_status_count": decision["downloaded_status_count"],
                "temp_strict_ready_count": decision["temp_strict_ready_count"],
                "published_or_replaced_count": decision["published_or_replaced_count"],
                "post_publish_manifest_count": decision["post_publish_manifest_count"],
                "post_publish_strict_ready_count": decision["post_publish_strict_ready_count"],
                "jd_margin_history_ready": decision["jd_margin_history_ready"],
            }
        ]
    )
    input_audit = _input_audit(
        [
            STAGE052_SCRIPT,
            STAGE112_SCRIPT,
            STAGE020_PRODUCT_RETURNS,
            *[Path(value) for value in plan["final_output_path"].astype(str)],
        ]
    )

    plan.to_csv(PLAN_PATH, index=False, encoding="utf-8-sig")
    status.to_csv(STATUS_PATH, index=False, encoding="utf-8-sig")
    temp_audit.to_csv(TEMP_AUDIT_PATH, index=False, encoding="utf-8-sig")
    publish.to_csv(PUBLISH_PATH, index=False, encoding="utf-8-sig")
    post_audit.to_csv(POST_AUDIT_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    input_audit.to_csv(INPUT_AUDIT_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(
        json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _write_report(decision, plan, temp_audit, publish, post_audit)
    stage_path = _write_stage_record(decision)
    decision["outputs"]["stage_record"] = str(stage_path)
    DECISION_PATH.write_text(
        json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    return decision


if __name__ == "__main__":
    run()
