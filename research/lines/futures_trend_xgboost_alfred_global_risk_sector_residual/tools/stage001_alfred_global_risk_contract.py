"""Label-free ALFRED global-risk source and feature contract."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import secrets
import shutil
import subprocess
import threading
import time
import traceback
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode

import numpy as np
import pandas as pd


SERIES_IDS = ("DEXCHUS", "DTWEXBGS", "VIXCLS")
STATE_FEATURES = (
    "cny_depreciation_shock_20d",
    "broad_usd_shock_20d",
    "vix_stress_percentile_252d",
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

EXPECTED_RELEASE_ID = "m0005_20260901T165450+0800_1961d98ccb2b"
EXPECTED_STRATEGY_ID = "ai_top10_plus_fu_official_live_v1"
EXPECTED_SOURCE_AGGREGATE_SHA256 = (
    "7d312d36015af3e6e09d0e6b3157f2a766bbb0a31ff26b20309161784404d20f"
)
EXPECTED_SOURCE_TOTAL_BYTES = 4_624_211
EXPECTED_STATE_UNIQUE_COUNTS = {
    "cny_depreciation_shock_20d": 77,
    "broad_usd_shock_20d": 77,
    "vix_stress_percentile_252d": 62,
}
EXPECTED_MAX_LAG_DAYS = {"DEXCHUS": 10, "DTWEXBGS": 10, "VIXCLS": 3}
ALFRED_SNAPSHOT_ENDPOINT = "https://alfred.stlouisfed.org/graph/alfredgraph.csv"
PASS_DECISION = (
    "stage001_alfred_global_risk_contract_pass_allow_stage002_preregistration_only"
)
FAIL_DECISION = "stage001_alfred_global_risk_contract_fail_close_no_labels"

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
FINAL_OUTPUT_DIR = LINE_DIR / "artifacts/stage001_alfred_global_risk_contract"

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


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _sha256_file(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
    return size, digest.hexdigest()


def _json_default(value: object) -> object:
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    raise TypeError(f"not_json_serializable:{type(value).__name__}")


def _atomic_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(
        f".{path.name}.tmp.{os.getpid()}.{threading.get_ident()}"
    )
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


class DurableEventLedger:
    def __init__(self, path: Path, run_nonce: str) -> None:
        if not re.fullmatch(r"[0-9a-f]{64}", run_nonce):
            raise Stage001Error("run_nonce_invalid")
        self.path = path
        self.run_nonce = run_nonce
        self._sequence = 0
        self._lock = threading.Lock()
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.stat().st_size:
            raise Stage001Error(f"event_ledger_exists:{path}")

    @property
    def event_count(self) -> int:
        return self._sequence

    def record(self, event: str, **fields: object) -> None:
        with self._lock:
            self._sequence += 1
            payload = {
                "sequence": self._sequence,
                "run_nonce": self.run_nonce,
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "event": event,
                **fields,
            }
            line = (
                json.dumps(payload, ensure_ascii=False, default=_json_default) + "\n"
            ).encode("utf-8")
            with self.path.open("ab") as handle:
                handle.write(line)
                handle.flush()
                os.fsync(handle.fileno())


def _normalize_eval_date(value: object) -> pd.Timestamp:
    date = pd.Timestamp(value)
    if date.tzinfo is not None:
        date = date.tz_convert(None)
    return date.normalize()


def parse_snapshot(
    series_id: str,
    eval_date: pd.Timestamp,
    content: bytes,
) -> pd.DataFrame:
    if series_id not in SERIES_IDS:
        raise Stage001Error(f"series_id_invalid:{series_id}")
    normalized_date = _normalize_eval_date(eval_date)
    expected_value_column = f"{series_id}_{normalized_date:%Y%m%d}"
    try:
        frame = pd.read_csv(io.BytesIO(content), encoding="utf-8-sig", dtype=str)
    except (UnicodeDecodeError, pd.errors.ParserError) as exc:
        raise Stage001Error(f"snapshot_parse_failed:{series_id}") from exc
    if list(frame.columns) != ["observation_date", expected_value_column]:
        raise Stage001Error(
            f"snapshot_column_mismatch:{series_id}:{list(frame.columns)}"
        )

    dates = pd.to_datetime(frame["observation_date"], errors="coerce")
    if dates.isna().any():
        raise Stage001Error(f"snapshot_date_invalid:{series_id}")
    if dates.duplicated().any():
        raise Stage001Error(f"snapshot_duplicate_date:{series_id}")
    if dates.ge(normalized_date).any():
        raise Stage001Error(f"snapshot_future_observation:{series_id}")

    values = pd.to_numeric(frame[expected_value_column], errors="coerce")
    parsed = pd.DataFrame({"observation_date": dates, "value": values}).dropna()
    if parsed.empty:
        raise Stage001Error(f"snapshot_no_valid_value:{series_id}")
    if (~np.isfinite(parsed["value"])).any():
        raise Stage001Error(f"snapshot_nonfinite_value:{series_id}")
    if parsed["value"].le(0.0).any():
        raise Stage001Error(f"snapshot_nonpositive_value:{series_id}")
    return parsed.sort_values("observation_date").reset_index(drop=True)


def _fx_shock(values: pd.Series, series_id: str) -> float:
    if len(values) < 253:
        raise Stage001Error(f"snapshot_window_incomplete:{series_id}:{len(values)}")
    log_returns = np.log(values / values.shift(1)).dropna()
    volatility = float(log_returns.iloc[-252:].std(ddof=1))
    if not np.isfinite(volatility) or volatility <= 0.0:
        raise Stage001Error(f"fx_volatility_nonpositive:{series_id}")
    shock = float(
        np.log(values.iloc[-1] / values.iloc[-21])
        / (volatility * np.sqrt(20.0))
    )
    if not np.isfinite(shock):
        raise Stage001Error(f"state_feature_nonfinite:{series_id}")
    return shock


def build_state_features(
    snapshots: Mapping[tuple[pd.Timestamp, str], pd.DataFrame],
    eval_dates: Sequence[pd.Timestamp],
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for raw_eval_date in eval_dates:
        eval_date = _normalize_eval_date(raw_eval_date)
        series_frames: dict[str, pd.DataFrame] = {}
        for series_id in SERIES_IDS:
            key = (eval_date, series_id)
            if key not in snapshots:
                raise Stage001Error(f"snapshot_missing:{eval_date.date()}:{series_id}")
            frame = snapshots[key].sort_values("observation_date").reset_index(drop=True)
            if len(frame) < 253:
                raise Stage001Error(
                    f"snapshot_window_incomplete:{series_id}:{len(frame)}"
                )
            series_frames[series_id] = frame

        vix = series_frames["VIXCLS"]["value"].iloc[-252:]
        row = {
            "eval_date": eval_date,
            "cny_depreciation_shock_20d": _fx_shock(
                series_frames["DEXCHUS"]["value"],
                "DEXCHUS",
            ),
            "broad_usd_shock_20d": _fx_shock(
                series_frames["DTWEXBGS"]["value"],
                "DTWEXBGS",
            ),
            "vix_stress_percentile_252d": float((vix <= vix.iloc[-1]).mean()),
        }
        if not all(np.isfinite(float(row[column])) for column in STATE_FEATURES):
            raise Stage001Error(f"state_feature_nonfinite:{eval_date.date()}")
        rows.append(row)
    return pd.DataFrame(rows, columns=["eval_date", *STATE_FEATURES])


def _sector_for_product(product: str) -> str:
    matches = [
        sector for sector, products in SECTOR_PRODUCTS.items() if product in products
    ]
    if len(matches) != 1:
        raise Stage001Error(f"product_sector_missing:{product}")
    return matches[0]


def build_interaction_panel(
    monthly: pd.DataFrame,
    products: Sequence[str],
) -> tuple[pd.DataFrame, list[str]]:
    product_list = list(products)
    if len(product_list) != len(set(product_list)):
        raise Stage001Error("duplicate_formal_product")
    product_sectors = {
        product: _sector_for_product(product) for product in product_list
    }
    required = {"eval_date", *STATE_FEATURES}
    missing = sorted(required.difference(monthly.columns))
    if missing:
        raise Stage001Error(f"monthly_feature_missing:{','.join(missing)}")

    interaction_columns = [
        f"{feature}_x_{sector}"
        for feature in STATE_FEATURES
        for sector in SECTOR_PRODUCTS
    ]
    feature_columns = [*STATE_FEATURES, *interaction_columns]
    rows: list[dict[str, object]] = []
    for monthly_row in monthly.to_dict("records"):
        for product in product_list:
            sector = product_sectors[product]
            row: dict[str, object] = {
                "eval_date": _normalize_eval_date(monthly_row["eval_date"]),
                "product_vt_symbol": product,
                "sector": sector,
            }
            for feature in STATE_FEATURES:
                value = float(monthly_row[feature])
                row[feature] = value
                for candidate_sector in SECTOR_PRODUCTS:
                    row[f"{feature}_x_{candidate_sector}"] = (
                        value if candidate_sector == sector else 0.0
                    )
            rows.append(row)
    panel = pd.DataFrame(
        rows,
        columns=["eval_date", "product_vt_symbol", "sector", *feature_columns],
    )
    return panel, feature_columns


def reconstruct_eval_dates(
    fold_plan: pd.DataFrame,
) -> tuple[list[pd.Timestamp], list[pd.Timestamp]]:
    required = {"test_eval_date", "train_eval_dates"}
    missing = sorted(required.difference(fold_plan.columns))
    if missing:
        raise Stage001Error(f"fold_plan_column_missing:{','.join(missing)}")
    oos = {
        _normalize_eval_date(value)
        for value in fold_plan["test_eval_date"].dropna().tolist()
    }
    all_dates = set(oos)
    for raw in fold_plan["train_eval_dates"].dropna():
        for value in str(raw).split(","):
            stripped = value.strip()
            if stripped:
                all_dates.add(_normalize_eval_date(stripped))
    return sorted(all_dates), sorted(oos)


def build_snapshot_url(series_id: str, eval_date: pd.Timestamp) -> str:
    if series_id not in SERIES_IDS:
        raise Stage001Error(f"series_id_invalid:{series_id}")
    normalized_date = _normalize_eval_date(eval_date)
    query = urlencode(
        {
            "id": series_id,
            "cosd": "2019-01-01",
            "coed": (normalized_date - pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
            "vintage_date": normalized_date.strftime("%Y-%m-%d"),
        }
    )
    return f"{ALFRED_SNAPSHOT_ENDPOINT}?{query}"


def _official_fetch_snapshot(url: str) -> bytes:
    if not url.startswith(f"{ALFRED_SNAPSHOT_ENDPOINT}?"):
        raise Stage001Error("snapshot_url_not_alfred")
    command = [
        "/usr/bin/curl",
        "--http1.1",
        "--fail",
        "--location",
        "--silent",
        "--show-error",
        "--max-time",
        "30",
        "--connect-timeout",
        "15",
        url,
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            check=False,
            timeout=45,
        )
    except subprocess.TimeoutExpired as exc:
        raise Stage001Error("alfred_curl_timeout") from exc
    if result.returncode != 0:
        stderr = bytes(result.stderr).decode("utf-8", errors="replace").strip()
        raise Stage001Error(
            f"alfred_curl_failed:{result.returncode}:{stderr[-500:]}"
        )
    content = bytes(result.stdout)
    if not content:
        raise Stage001Error("alfred_curl_empty_response")
    return content


def _snapshot_record(
    series_id: str,
    eval_date: pd.Timestamp,
    url: str,
    content: bytes,
    frame: pd.DataFrame,
    attempts: int,
    reused: bool,
) -> dict[str, object]:
    latest = pd.Timestamp(frame["observation_date"].max())
    return {
        "eval_date": eval_date.strftime("%Y-%m-%d"),
        "series_id": series_id,
        "url": url,
        "snapshot_bytes": len(content),
        "sha256": _sha256_bytes(content),
        "valid_row_count": len(frame),
        "first_observation_date": pd.Timestamp(
            frame["observation_date"].min()
        ).strftime("%Y-%m-%d"),
        "latest_observation_date": latest.strftime("%Y-%m-%d"),
        "latest_lag_days": int((eval_date - latest).days),
        "attempts": attempts,
        "reused": reused,
    }


def acquire_snapshots(
    raw_dir: Path,
    fetcher: Callable[[str], bytes],
    *,
    eval_dates: Sequence[pd.Timestamp],
    series_ids: Sequence[str] = SERIES_IDS,
    max_workers: int = 4,
    max_attempts: int = 5,
    retry_sleep_seconds: float = 1.0,
    ledger: DurableEventLedger | None = None,
) -> tuple[
    list[dict[str, object]],
    dict[tuple[pd.Timestamp, str], pd.DataFrame],
]:
    if max_workers < 1 or max_attempts < 1 or retry_sleep_seconds < 0.0:
        raise Stage001Error("acquisition_parameter_invalid")
    normalized_dates = sorted({_normalize_eval_date(value) for value in eval_dates})
    normalized_series = list(series_ids)
    if len(normalized_series) != len(set(normalized_series)):
        raise Stage001Error("duplicate_series_id")
    for series_id in normalized_series:
        if series_id not in SERIES_IDS:
            raise Stage001Error(f"series_id_invalid:{series_id}")
    raw_dir.mkdir(parents=True, exist_ok=True)
    items = [
        (eval_date, series_id)
        for eval_date in normalized_dates
        for series_id in normalized_series
    ]

    def acquire_one(
        item: tuple[pd.Timestamp, str],
    ) -> tuple[
        tuple[pd.Timestamp, str],
        dict[str, object],
        pd.DataFrame,
    ]:
        eval_date, series_id = item
        url = build_snapshot_url(series_id, eval_date)
        path = raw_dir / f"{eval_date:%Y-%m-%d}_{series_id}.csv"
        if path.exists():
            content = path.read_bytes()
            try:
                frame = parse_snapshot(series_id, eval_date, content)
            except Stage001Error as exc:
                raise Stage001Error(
                    f"existing_snapshot_invalid:{eval_date.date()}:{series_id}:{exc}"
                ) from exc
            if ledger is not None:
                ledger.record(
                    "snapshot_reused",
                    eval_date=eval_date,
                    series_id=series_id,
                    sha256=_sha256_bytes(content),
                )
            return (
                item,
                _snapshot_record(series_id, eval_date, url, content, frame, 0, True),
                frame,
            )

        last_error: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            if ledger is not None:
                ledger.record(
                    "snapshot_fetch_attempt",
                    eval_date=eval_date,
                    series_id=series_id,
                    attempt=attempt,
                    url=url,
                )
            try:
                content = fetcher(url)
                frame = parse_snapshot(series_id, eval_date, content)
                _atomic_write_bytes(path, content)
                if ledger is not None:
                    ledger.record(
                        "snapshot_persisted",
                        eval_date=eval_date,
                        series_id=series_id,
                        attempt=attempt,
                        sha256=_sha256_bytes(content),
                    )
                return (
                    item,
                    _snapshot_record(
                        series_id,
                        eval_date,
                        url,
                        content,
                        frame,
                        attempt,
                        False,
                    ),
                    frame,
                )
            except Exception as exc:  # network and semantic failures share retry budget
                last_error = exc
                if ledger is not None:
                    ledger.record(
                        "snapshot_fetch_failed",
                        eval_date=eval_date,
                        series_id=series_id,
                        attempt=attempt,
                        error_type=type(exc).__name__,
                        error=str(exc),
                    )
                if attempt < max_attempts and retry_sleep_seconds:
                    time.sleep(retry_sleep_seconds * attempt)
        raise Stage001Error(
            f"snapshot_download_failed:{eval_date.date()}:{series_id}:"
            f"{type(last_error).__name__}:{last_error}"
        )

    records: list[dict[str, object]] = []
    snapshots: dict[tuple[pd.Timestamp, str], pd.DataFrame] = {}
    item_iterator = iter(items)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        pending: dict[Any, tuple[pd.Timestamp, str]] = {}
        for _ in range(min(max_workers, len(items))):
            item = next(item_iterator, None)
            if item is None:
                break
            pending[executor.submit(acquire_one, item)] = item
        while pending:
            completed, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in completed:
                pending.pop(future)
                try:
                    key, record, frame = future.result()
                except Exception:
                    for other in pending:
                        other.cancel()
                    raise
                records.append(record)
                snapshots[key] = frame
                item = next(item_iterator, None)
                if item is not None:
                    pending[executor.submit(acquire_one, item)] = item

    records.sort(key=lambda row: (str(row["eval_date"]), str(row["series_id"])))
    return records, snapshots


def aggregate_snapshot_hash(records: Sequence[Mapping[str, object]]) -> str:
    digest = hashlib.sha256()
    ordered = sorted(
        records,
        key=lambda row: (str(row["eval_date"]), str(row["series_id"])),
    )
    for row in ordered:
        identity = f"{row['eval_date']}|{row['series_id']}|".encode("utf-8")
        raw_digest = str(row["sha256"])
        if not re.fullmatch(r"[0-9a-f]{64}", raw_digest):
            raise Stage001Error("snapshot_sha256_invalid")
        digest.update(identity)
        digest.update(bytes.fromhex(raw_digest))
    return digest.hexdigest()


def evaluate_gates(
    metrics: Mapping[str, object],
) -> tuple[dict[str, bool], list[str]]:
    identity_contract = (
        metrics.get("input_identity_mismatch_count") == 0
        and metrics.get("current_release_id") == EXPECTED_RELEASE_ID
        and metrics.get("current_strategy_id") == EXPECTED_STRATEGY_ID
        and metrics.get("current_pointer_matches_release") is True
    )
    source_contract = (
        metrics.get("source_snapshot_count") == 231
        and metrics.get("source_series_count") == 3
        and metrics.get("source_min_snapshots_per_series") == 77
        and metrics.get("source_max_snapshots_per_series") == 77
        and metrics.get("source_total_bytes") == EXPECTED_SOURCE_TOTAL_BYTES
        and metrics.get("source_aggregate_sha256")
        == EXPECTED_SOURCE_AGGREGATE_SHA256
        and int(metrics.get("source_min_valid_level_count", -1)) >= 253
        and metrics.get("source_future_row_count") == 0
        and metrics.get("source_duplicate_identity_count") == 0
        and metrics.get("source_current_fred_fallback_count") == 0
        and metrics.get("source_third_party_fallback_count") == 0
        and metrics.get("source_max_lag_days") == EXPECTED_MAX_LAG_DAYS
    )
    eval_contract = (
        metrics.get("eval_date_count") == 77
        and metrics.get("oos_eval_date_count") == 50
    )
    feature_contract = (
        metrics.get("monthly_state_row_count") == 77
        and metrics.get("state_feature_count") == 3
        and metrics.get("state_unique_counts") == EXPECTED_STATE_UNIQUE_COUNTS
        and float(metrics.get("minimum_state_std", 0.0)) > 0.0
        and metrics.get("interaction_panel_row_count") == 1386
        and metrics.get("formal_product_count") == 18
        and metrics.get("interaction_feature_count") == 15
        and metrics.get("minimum_products_per_month") == 18
        and metrics.get("maximum_products_per_month") == 18
        and metrics.get("effective_month_sector_state_count") == 308
        and metrics.get("nonfinite_feature_cell_count") == 0
        and metrics.get("sector_count_contract_match") is True
    )
    expression_contract = (
        metrics.get("static_sector_one_hot_column_count") == 0
        and metrics.get("interaction_mismatch_cell_count") == 0
    )
    side_effect_contract = all(
        metrics.get(field) == 0
        for field in (
            "label_value_read_count",
            "model_fit_count",
            "model_predict_count",
            "strategy_backtest_count",
            "holdout_read_count",
            "ctp_connection_count",
            "order_api_call_count",
            "production_write_count",
        )
    )
    durability_contract = (
        metrics.get("execution_receipt_exists") is True
        and int(metrics.get("event_ledger_event_count", 0)) > 0
        and metrics.get("atomic_publish_ready") is True
    )
    gates = {
        "identity_contract": identity_contract,
        "source_contract": source_contract,
        "eval_contract": eval_contract,
        "feature_contract": feature_contract,
        "expression_contract": expression_contract,
        "side_effect_contract": side_effect_contract,
        "durability_contract": durability_contract,
    }
    return gates, [name for name, passed in gates.items() if not passed]


MANIFEST_NAME = "artifact_manifest.json"


def write_artifact_manifest(bundle: Path) -> Path:
    if not bundle.is_dir():
        raise Stage001Error(f"artifact_bundle_missing:{bundle}")
    files: list[dict[str, object]] = []
    for path in sorted(bundle.rglob("*")):
        if not path.is_file() or path.name == MANIFEST_NAME:
            continue
        size, digest = _sha256_file(path)
        files.append(
            {
                "path": path.relative_to(bundle).as_posix(),
                "bytes": size,
                "sha256": digest,
            }
        )
    manifest_path = bundle / MANIFEST_NAME
    _atomic_write_json(
        manifest_path,
        {"schema_version": 1, "file_count": len(files), "files": files},
    )
    return manifest_path


def verify_artifact_bundle(bundle: Path) -> dict[str, object]:
    manifest_path = bundle / MANIFEST_NAME
    if not manifest_path.is_file():
        raise Stage001Error(f"artifact_manifest_missing:{bundle}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise Stage001Error("artifact_manifest_invalid") from exc
    expected_rows = manifest.get("files")
    if not isinstance(expected_rows, list):
        raise Stage001Error("artifact_manifest_invalid")
    expected = {str(row["path"]): row for row in expected_rows}
    actual = {
        path.relative_to(bundle).as_posix(): path
        for path in bundle.rglob("*")
        if path.is_file() and path.name != MANIFEST_NAME
    }
    unmanifested = sorted(set(actual).difference(expected))
    missing = sorted(set(expected).difference(actual))
    if unmanifested:
        raise Stage001Error(f"unmanifested_file:{unmanifested[0]}")
    if missing:
        raise Stage001Error(f"manifest_missing_file:{missing[0]}")
    mismatches: list[str] = []
    for relative, row in expected.items():
        size, digest = _sha256_file(actual[relative])
        if size != int(row["bytes"]) or digest != str(row["sha256"]):
            mismatches.append(relative)
    if mismatches:
        raise Stage001Error(f"manifest_mismatch:{mismatches[0]}")
    if int(manifest.get("file_count", -1)) != len(expected):
        raise Stage001Error("manifest_file_count_mismatch")
    return {
        "artifact_bundle_valid": True,
        "manifest_file_count": len(expected),
        "manifest_mismatch_count": 0,
        "unmanifested_file_count": 0,
    }


def publish_staged_directory(staging: Path, final: Path) -> None:
    if final.exists():
        raise Stage001Error(f"final_output_exists:{final}")
    verify_artifact_bundle(staging)
    final.parent.mkdir(parents=True, exist_ok=True)
    os.replace(staging, final)
    verify_artifact_bundle(final)


def _file_identity(path: Path, expected_sha256: str) -> dict[str, object]:
    source = path.expanduser().resolve(strict=True)
    before = source.stat()
    size, digest = _sha256_file(source)
    after = source.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise Stage001Error(f"file_changed_while_hashing:{source}")
    return {
        "path": str(source),
        "size": size,
        "mtime_ns": int(after.st_mtime_ns),
        "sha256": digest,
        "expected_sha256": expected_sha256,
        "matches_expected": digest == expected_sha256,
    }


def _collect_input_identities() -> dict[str, dict[str, object]]:
    return {
        name: _file_identity(path, expected_sha256)
        for name, (path, expected_sha256) in EXPECTED_INPUT_HASHES.items()
    }


def _load_formal_identity() -> tuple[dict[str, object], dict[str, object]]:
    try:
        current = json.loads(CURRENT_PATH.read_text(encoding="utf-8"))
        release_manifest = json.loads(
            RELEASE_MANIFEST_PATH.read_text(encoding="utf-8")
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Stage001Error("formal_identity_unreadable") from exc
    return current, release_manifest


def _write_dataframe(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    try:
        frame.to_csv(temporary, index=False, date_format="%Y-%m-%d")
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _build_metrics(
    *,
    records: list[dict[str, object]],
    monthly: pd.DataFrame,
    panel: pd.DataFrame,
    feature_columns: list[str],
    eval_dates: Sequence[pd.Timestamp],
    oos_dates: Sequence[pd.Timestamp],
    identities_before: Mapping[str, Mapping[str, object]],
    identities_after: Mapping[str, Mapping[str, object]],
    current: Mapping[str, object],
    release_manifest: Mapping[str, object],
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
    record_frame = pd.DataFrame(records)
    if record_frame.empty:
        raise Stage001Error("source_records_empty")
    duplicate_identity_count = int(
        record_frame.duplicated(["eval_date", "series_id"]).sum()
    )
    snapshots_per_series = record_frame.groupby("series_id").size()
    max_lags = {
        str(series_id): int(value)
        for series_id, value in record_frame.groupby("series_id")[
            "latest_lag_days"
        ].max().sort_index().items()
    }

    products_per_month = panel.groupby("eval_date")["product_vt_symbol"].nunique()
    panel_values = panel[feature_columns].to_numpy(dtype="float64")
    unique_counts = monthly[list(STATE_FEATURES)].nunique(dropna=True)
    standard_deviations = monthly[list(STATE_FEATURES)].std(ddof=1)
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
    interaction_mismatches = 0
    for sector in SECTOR_PRODUCTS:
        member = panel["sector"].eq(sector).to_numpy()
        for feature in STATE_FEATURES:
            expected = np.where(
                member,
                panel[feature].to_numpy(dtype="float64"),
                0.0,
            )
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
    return {
        "input_identity_mismatch_count": int(identity_mismatches),
        "current_release_id": current_release,
        "current_strategy_id": current_strategy,
        "current_pointer_matches_release": pointer_matches,
        "source_snapshot_count": int(len(record_frame)),
        "source_series_count": int(record_frame["series_id"].nunique()),
        "source_snapshots_per_series": {
            str(key): int(value) for key, value in snapshots_per_series.items()
        },
        "source_min_snapshots_per_series": int(snapshots_per_series.min()),
        "source_max_snapshots_per_series": int(snapshots_per_series.max()),
        "source_total_bytes": int(record_frame["snapshot_bytes"].sum()),
        "source_aggregate_sha256": aggregate_snapshot_hash(records),
        "source_min_valid_level_count": int(record_frame["valid_row_count"].min()),
        "source_max_valid_level_count": int(record_frame["valid_row_count"].max()),
        "source_future_row_count": int(
            record_frame.get("future_row_count", pd.Series(0, index=record_frame.index)).sum()
        ),
        "source_duplicate_identity_count": duplicate_identity_count,
        "source_current_fred_fallback_count": 0,
        "source_third_party_fallback_count": 0,
        "source_max_lag_days": max_lags,
        "source_retry_count": int(
            (record_frame["attempts"].fillna(0).astype(int) - 1).clip(lower=0).sum()
        )
        if "attempts" in record_frame
        else 0,
        "source_reused_count": int(record_frame.get("reused", False).sum())
        if "reused" in record_frame
        else 0,
        "eval_date_count": len(eval_dates),
        "oos_eval_date_count": len(oos_dates),
        "monthly_state_row_count": int(len(monthly)),
        "state_feature_count": len(STATE_FEATURES),
        "state_unique_counts": {
            str(key): int(value) for key, value in unique_counts.items()
        },
        "state_standard_deviations": {
            str(key): float(value) for key, value in standard_deviations.items()
        },
        "minimum_state_std": float(standard_deviations.min()),
        "interaction_panel_row_count": int(len(panel)),
        "formal_product_count": len(FORMAL_PRODUCTS),
        "interaction_feature_count": len(feature_columns),
        "minimum_products_per_month": int(products_per_month.min()),
        "maximum_products_per_month": int(products_per_month.max()),
        "effective_month_sector_state_count": int(
            panel[["eval_date", "sector"]].drop_duplicates().shape[0]
        ),
        "nonfinite_feature_cell_count": int((~np.isfinite(panel_values)).sum()),
        "sector_counts_per_month": expected_sector_counts,
        "sector_count_contract_match": sector_contract,
        "static_sector_one_hot_column_count": sum(
            column.startswith("sector_") for column in feature_columns
        ),
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


def _build_report(summary: Mapping[str, object]) -> str:
    failures = summary.get("failures", [])
    return "\n".join(
        [
            "# Stage001 ALFRED全球风险状态无标签合同",
            "",
            f"- 决策：`{summary.get('decision', '')}`。",
            (
                f"- PIT源：`{summary.get('source_snapshot_count', 0)}`份快照 / "
                f"`{summary.get('source_total_bytes', 0)}`字节 / "
                f"重试`{summary.get('source_retry_count', 0)}`次。"
            ),
            (
                f"- 正式月末：`{summary.get('eval_date_count', 0)}`；"
                f"OOS测试月：`{summary.get('oos_eval_date_count', 0)}`。"
            ),
            (
                f"- 特征：`{summary.get('monthly_state_row_count', 0)}`月 / "
                f"`{summary.get('interaction_panel_row_count', 0)}`产品行 / "
                f"`{summary.get('interaction_feature_count', 0)}`列 / "
                f"`{summary.get('effective_month_sector_state_count', 0)}`个有效月板块状态。"
            ),
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
            "label_value_read_count": 0,
            "model_fit_count": 0,
            "model_predict_count": 0,
            "strategy_backtest_count": 0,
            "holdout_read_count": 0,
            "ctp_connection_count": 0,
            "order_api_call_count": 0,
            "production_write_count": 0,
        },
    )
    write_artifact_manifest(staging)
    failure_dir = (
        FINAL_OUTPUT_DIR.parent
        / f"stage001_alfred_global_risk_contract_failure_{run_nonce[:16]}"
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
        "line_id": "futures_trend_xgboost_alfred_global_risk_sector_residual",
        "stage": "Stage001",
        "scope": "single_authorized_label_free_alfred_source_and_feature_contract",
        "authorization_mode": "explicit_user_default_authorization_current_thread",
        "run_nonce": run_nonce,
        "status": "started",
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "network_started": False,
        "label_values_allowed": False,
        "model_execution_allowed": False,
        "backtest_allowed": False,
        "production_write_allowed": False,
        "runner_sha256": _sha256_file(Path(__file__))[1],
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
        fold_plan_dates = pd.read_csv(
            FOLD_PLAN_PATH,
            usecols=["test_eval_date", "train_eval_dates"],
        )
        eval_dates, oos_dates = reconstruct_eval_dates(fold_plan_dates)
        if len(eval_dates) != 77 or len(oos_dates) != 50:
            raise Stage001Error(
                f"fold_date_contract_mismatch:{len(eval_dates)}:{len(oos_dates)}"
            )
        ledger.record(
            "input_identities_verified",
            identity_count=len(identities_before),
            eval_date_count=len(eval_dates),
            oos_eval_date_count=len(oos_dates),
        )

        receipt.update(
            {
                "network_started": True,
                "network_started_at_utc": datetime.now(timezone.utc).isoformat(),
                "input_identities_before": identities_before,
            }
        )
        _atomic_write_json(staging / "execution_receipt.json", receipt)
        records, snapshots = acquire_snapshots(
            staging / "raw_snapshots",
            _official_fetch_snapshot,
            eval_dates=eval_dates,
            series_ids=SERIES_IDS,
            max_workers=4,
            max_attempts=5,
            retry_sleep_seconds=1.0,
            ledger=ledger,
        )
        ledger.record(
            "snapshot_acquisition_completed",
            snapshot_count=len(records),
            snapshot_bytes=sum(int(row["snapshot_bytes"]) for row in records),
            retry_count=sum(
                max(int(row["attempts"]) - 1, 0) for row in records
            ),
        )

        monthly = build_state_features(snapshots, eval_dates)
        panel, feature_columns = build_interaction_panel(
            monthly,
            list(FORMAL_PRODUCTS),
        )
        ledger.record(
            "transformations_completed",
            monthly_rows=len(monthly),
            panel_rows=len(panel),
            feature_count=len(feature_columns),
            effective_month_sector_states=int(
                panel[["eval_date", "sector"]].drop_duplicates().shape[0]
            ),
        )

        _write_dataframe(staging / "source_snapshots.csv", pd.DataFrame(records))
        _write_dataframe(staging / "monthly_state_features.csv", monthly)
        _write_dataframe(staging / "interaction_panel.csv", panel)
        shutil.copy2(FOLD_PLAN_PATH, staging / "copied_fold_plan.csv")
        ledger.record("data_artifacts_written", data_file_count=4)

        identities_after = _collect_input_identities()
        metrics = _build_metrics(
            records=records,
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
        metrics["event_ledger_event_count"] = ledger.event_count + 1
        gates, failures = evaluate_gates(metrics)
        decision = PASS_DECISION if not failures else FAIL_DECISION
        ledger.record("run_completed", decision=decision, failures=failures)
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
            "series_ids": list(SERIES_IDS),
            "snapshot_count": 231,
            "snapshot_url_template": (
                f"{ALFRED_SNAPSHOT_ENDPOINT}?id={{series}}&cosd=2019-01-01&"
                "coed={eval_date_minus_one}&vintage_date={eval_date}"
            ),
            "source_aggregate_sha256": EXPECTED_SOURCE_AGGREGATE_SHA256,
            "state_features": list(STATE_FEATURES),
            "sector_products": {
                sector: list(products) for sector, products in SECTOR_PRODUCTS.items()
            },
            "static_sector_one_hot_columns": [],
            "model_feature_count": len(feature_columns),
            "model_features": feature_columns,
            "effective_month_sector_state_count": 308,
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
        _atomic_write_bytes(
            staging / "report.md",
            _build_report(summary).encode("utf-8"),
        )
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
                f"stage001_technical_failure:{failure_dir}:"
                f"{type(exc).__name__}:{exc}"
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
