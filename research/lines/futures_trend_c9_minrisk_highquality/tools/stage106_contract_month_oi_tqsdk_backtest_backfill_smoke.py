from __future__ import annotations

from datetime import datetime
import hashlib
import json
import logging
import os
from pathlib import Path
import time
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage106"
MODEL_TAG = "stage106_contract_month_oi_tqsdk_backtest_backfill_smoke_v1"
OUTPUT_PREFIX = "qmt_roll_stage106_c9_minrisk_contract_month_oi_tqsdk_backtest_backfill_smoke"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage106_contract_month_oi_tqsdk_backtest_backfill_smoke"
RAW_ROOT = OUTPUT_DIR / "raw_daily_backtest"

STAGE105_DIR = LINE_DIR / "outputs" / "stage105_contract_month_oi_gap_repair_manifest"
REPAIR_MANIFEST_IN = (
    STAGE105_DIR
    / "qmt_roll_stage105_c9_minrisk_contract_month_oi_gap_repair_manifest_repair_manifest_"
    "stage105_contract_month_oi_gap_repair_manifest_v1.csv"
)
GAP_ROWS_IN = (
    STAGE105_DIR
    / "qmt_roll_stage105_c9_minrisk_contract_month_oi_gap_repair_manifest_gap_rows_"
    "stage105_contract_month_oi_gap_repair_manifest_v1.csv"
)
SUMMARY105_IN = (
    STAGE105_DIR
    / "qmt_roll_stage105_c9_minrisk_contract_month_oi_gap_repair_manifest_summary_"
    "stage105_contract_month_oi_gap_repair_manifest_v1.csv"
)
CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)

PLAN_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_download_plan_{MODEL_TAG}.csv"
AVAILABILITY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_query_availability_{MODEL_TAG}.csv"
STATUS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_backtest_status_{MODEL_TAG}.csv"
PROVENANCE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_raw_provenance_{MODEL_TAG}.csv"
GAP_RECHECK_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gap_recheck_{MODEL_TAG}.csv"
PRODUCT_YEAR_RECHECK_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_year_recheck_{MODEL_TAG}.csv"
PROMOTION_GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_promotion_gate_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_backfill_recheck_{MODEL_TAG}.png"
PRODUCT_YEAR_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_year_backfill_heatmap_{MODEL_TAG}.png"
RAW_ROWS_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_raw_rows_by_contract_{MODEL_TAG}.png"
GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_promotion_gate_{MODEL_TAG}.png"

MAX_CONTRACTS = int(os.getenv("STAGE106_MAX_CONTRACTS", "0"))
MAX_SECONDS_PER_CONTRACT = int(os.getenv("STAGE106_MAX_SECONDS_PER_CONTRACT", "45"))
FORCE_REFRESH = os.getenv("STAGE106_FORCE_REFRESH", "0").strip() == "1"

REQUIRED_RAW_COLUMNS = [
    "trade_date",
    "bar_datetime",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "open_oi",
    "close_oi",
]


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        out = float(value)
        return None if np.isnan(out) or np.isinf(out) else out
    if isinstance(value, (pd.Timestamp, datetime)):
        if pd.isna(value):
            return None
        return pd.Timestamp(value).isoformat()
    return value


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    display = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    for column in display.columns:
        if pd.api.types.is_float_dtype(display[column]):
            display[column] = display[column].map(lambda value: "" if pd.isna(value) else f"{value:.4f}")
    lines = [
        "| " + " | ".join(str(column) for column in display.columns) + " |",
        "| " + " | ".join(["---"] * len(display.columns)) + " |",
    ]
    for _, row in display.iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in display.columns) + " |")
    return "\n".join(lines)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _schema_hash(columns: list[str]) -> str:
    return hashlib.sha256(",".join(columns).encode("utf-8")).hexdigest()


def _load_curve() -> pd.DataFrame:
    curve = _read_csv(CURVE_IN)
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]:
        curve[column] = pd.to_numeric(curve[column], errors="coerce")
    return curve[curve["date"].notna()].sort_values("date").reset_index(drop=True)


def _raw_path(row: Any) -> Path:
    exchange = str(row.exchange)
    target_contract = str(row.target_contract)
    first_value = getattr(row, "download_start_date", row.required_start_date)
    last_value = getattr(row, "download_end_date", row.required_end_date)
    first = pd.Timestamp(first_value).strftime("%Y%m%d")
    last = pd.Timestamp(last_value).strftime("%Y%m%d")
    return RAW_ROOT / exchange / f"{target_contract}_{first}_{last}_daily_backtest.csv"


def _normalize_tqsdk_datetime(value: Any) -> pd.Timestamp:
    if pd.isna(value):
        return pd.NaT
    if isinstance(value, (int, float, np.integer, np.floating)):
        return pd.to_datetime(value, unit="ns", errors="coerce", utc=True).tz_convert(
            "Asia/Shanghai"
        ).tz_localize(None)
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return pd.NaT
    if parsed.tzinfo is not None:
        return parsed.tz_convert("Asia/Shanghai").tz_localize(None)
    return pd.Timestamp(parsed)


def _load_repair_manifest() -> pd.DataFrame:
    manifest = _read_csv(REPAIR_MANIFEST_IN).copy()
    manifest["required_start_date"] = pd.to_datetime(manifest["required_start_date"], errors="coerce")
    manifest["required_end_date"] = pd.to_datetime(manifest["required_end_date"], errors="coerce")
    manifest["first_entry_date"] = pd.to_datetime(manifest["first_entry_date"], errors="coerce")
    manifest["last_entry_date"] = pd.to_datetime(manifest["last_entry_date"], errors="coerce")
    manifest["linked_gap_order_count"] = pd.to_numeric(
        manifest["linked_gap_order_count"], errors="coerce"
    ).fillna(0).astype(int)
    manifest["pnl_sum"] = pd.to_numeric(manifest["pnl_sum"], errors="coerce").fillna(0.0)
    manifest = manifest.sort_values(
        ["repair_action", "first_entry_date", "vt_symbol"], ascending=[True, True, True]
    ).reset_index(drop=True)
    manifest["selection_rank"] = np.arange(1, len(manifest) + 1)
    if MAX_CONTRACTS > 0:
        manifest = manifest.head(MAX_CONTRACTS).copy()
    return manifest


def _augment_plan_with_source_dates(plan: pd.DataFrame, gap_rows: pd.DataFrame) -> pd.DataFrame:
    augmented = plan.copy()
    source_dates = (
        gap_rows.groupby("vt_symbol", dropna=False)["source_date"]
        .agg(min_source_date="min", max_source_date="max")
        .reset_index()
    )
    augmented = augmented.merge(source_dates, on="vt_symbol", how="left")
    augmented["download_start_date"] = augmented[["required_start_date", "min_source_date"]].min(axis=1)
    augmented["download_end_date"] = augmented[["required_end_date", "max_source_date"]].max(axis=1)
    augmented["raw_path"] = augmented.apply(lambda row: str(_raw_path(row)), axis=1)
    return augmented


def _load_gap_rows() -> pd.DataFrame:
    gap = _read_csv(GAP_ROWS_IN).copy()
    for column in ["official_open_date", "source_date"]:
        gap[column] = pd.to_datetime(gap[column], errors="coerce").dt.normalize()
    for column in ["order_realized_pnl", "right_tail_visual", "bottom_loss_visual"]:
        gap[column] = pd.to_numeric(gap[column], errors="coerce").fillna(0.0)
    return gap


def _credential_audit() -> dict[str, Any]:
    try:
        from vnpy.trader.setting import SETTINGS
    except Exception as exc:
        return {
            "settings_imported": 0,
            "username_present": 0,
            "username_len": 0,
            "password_present": 0,
            "password_len": 0,
            "message": repr(exc)[:500],
        }
    username = str(SETTINGS.get("datafeed.username", "") or "")
    password = str(SETTINGS.get("datafeed.password", "") or "")
    return {
        "settings_imported": 1,
        "username_present": int(bool(username)),
        "username_len": len(username),
        "password_present": int(bool(password)),
        "password_len": len(password),
        "message": "",
    }


def _query_availability(plan: pd.DataFrame, credential: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if not credential["username_present"] or not credential["password_present"]:
        for row in plan.itertuples(index=False):
            rows.append(
                {
                    "vt_symbol": str(row.vt_symbol),
                    "download_symbol": str(row.download_symbol),
                    "query_quotes_symbol_available": 0,
                    "query_quotes_success": 0,
                    "message": "missing_credentials",
                }
            )
        return pd.DataFrame(rows)

    try:
        from tqsdk import TqApi, TqAuth
        from vnpy.trader.setting import SETTINGS
    except Exception as exc:
        for row in plan.itertuples(index=False):
            rows.append(
                {
                    "vt_symbol": str(row.vt_symbol),
                    "download_symbol": str(row.download_symbol),
                    "query_quotes_symbol_available": 0,
                    "query_quotes_success": 0,
                    "message": repr(exc)[:500],
                }
            )
        return pd.DataFrame(rows)

    api = None
    symbols: set[str] = set()
    message = ""
    success = 0
    try:
        api = TqApi(
            auth=TqAuth(
                str(SETTINGS.get("datafeed.username", "") or ""),
                str(SETTINGS.get("datafeed.password", "") or ""),
            )
        )
        symbols = set(api.query_quotes(ins_class="FUTURE", expired=True))
        success = 1
    except Exception as exc:
        message = repr(exc)[:500]
    finally:
        if api is not None:
            api.close()

    for row in plan.itertuples(index=False):
        download_symbol = str(row.download_symbol)
        rows.append(
            {
                "vt_symbol": str(row.vt_symbol),
                "download_symbol": download_symbol,
                "query_quotes_symbol_available": int(download_symbol in symbols),
                "query_quotes_success": success,
                "query_symbol_count": len(symbols),
                "message": message,
            }
        )
    return pd.DataFrame(rows)


def _read_raw(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size <= 0:
        return pd.DataFrame()
    try:
        raw = pd.read_csv(path, encoding="utf-8-sig")
    except Exception:
        return pd.DataFrame()
    if "trade_date" in raw.columns:
        raw["trade_date"] = pd.to_datetime(raw["trade_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    return raw


def _raw_covers_required_dates(raw: pd.DataFrame, required_dates: set[str]) -> bool:
    if raw.empty or not required_dates or "trade_date" not in raw.columns:
        return False
    available = set(raw["trade_date"].dropna().astype(str))
    return required_dates.issubset(available)


def _extract_daily_backtest(row: Any, required_source_dates: set[str], credential: dict[str, Any]) -> dict[str, Any]:
    raw_path = _raw_path(row)
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    status = {
        "selection_rank": int(row.selection_rank),
        "vt_symbol": str(row.vt_symbol),
        "download_symbol": str(row.download_symbol),
        "repair_action": str(row.repair_action),
        "required_start_date": pd.Timestamp(row.required_start_date).strftime("%Y-%m-%d"),
        "required_end_date": pd.Timestamp(row.required_end_date).strftime("%Y-%m-%d"),
        "download_start_date": pd.Timestamp(row.download_start_date).strftime("%Y-%m-%d"),
        "download_end_date": pd.Timestamp(row.download_end_date).strftime("%Y-%m-%d"),
        "required_source_dates": "|".join(sorted(required_source_dates)),
        "raw_path": str(raw_path),
        "status": "unknown",
        "rows": 0,
        "source_dates_covered": 0,
        "open_oi_ready": 0,
        "close_oi_ready": 0,
        "date_min": "",
        "date_max": "",
        "elapsed_seconds": 0.0,
        "message": "",
    }
    if not credential["username_present"] or not credential["password_present"]:
        status["status"] = "missing_credentials"
        return status

    if raw_path.exists() and raw_path.stat().st_size > 0 and not FORCE_REFRESH:
        cached = _read_raw(raw_path)
        status["status"] = "cached_raw"
        status["rows"] = int(len(cached))
        status["source_dates_covered"] = int(_raw_covers_required_dates(cached, required_source_dates))
        status["open_oi_ready"] = int("open_oi" in cached.columns and cached["open_oi"].notna().any())
        status["close_oi_ready"] = int("close_oi" in cached.columns and cached["close_oi"].notna().any())
        if not cached.empty and "trade_date" in cached.columns:
            status["date_min"] = str(min(cached["trade_date"].dropna().astype(str), default=""))
            status["date_max"] = str(max(cached["trade_date"].dropna().astype(str), default=""))
        return status

    if FORCE_REFRESH and raw_path.exists():
        raw_path.unlink()

    try:
        from tqsdk import BacktestFinished, TqApi, TqAuth, TqBacktest, TqSim
        from vnpy.trader.setting import SETTINGS
    except Exception as exc:
        status["status"] = "import_failed"
        status["message"] = repr(exc)[:500]
        return status

    logging.getLogger().setLevel(logging.WARNING)
    logging.getLogger("tqsdk").setLevel(logging.WARNING)

    username = str(SETTINGS.get("datafeed.username", "") or "")
    password = str(SETTINGS.get("datafeed.password", "") or "")
    start_dt = pd.Timestamp(row.download_start_date).to_pydatetime()
    end_dt = pd.Timestamp(row.download_end_date).to_pydatetime()
    api = None
    started = time.time()
    rows: list[dict[str, Any]] = []
    seen_datetimes: set[str] = set()
    try:
        api = TqApi(
            TqSim(),
            backtest=TqBacktest(start_dt=start_dt, end_dt=end_dt),
            auth=TqAuth(username, password),
            disable_print=True,
        )
        klines = api.get_kline_serial(str(row.download_symbol), duration_seconds=60 * 60 * 24, data_length=500)
        while True:
            if time.time() - started > MAX_SECONDS_PER_CONTRACT:
                status["status"] = "timeout"
                status["message"] = f"timeout_after_{MAX_SECONDS_PER_CONTRACT}s"
                break
            api.wait_update()
            latest = klines.iloc[-1].to_dict()
            bar_dt = _normalize_tqsdk_datetime(latest.get("datetime"))
            if pd.isna(bar_dt):
                continue
            key = pd.Timestamp(bar_dt).isoformat()
            if key in seen_datetimes:
                continue
            seen_datetimes.add(key)
            values = {
                "vt_symbol": str(row.vt_symbol),
                "download_symbol": str(row.download_symbol),
                "trade_date": pd.Timestamp(bar_dt).strftime("%Y-%m-%d"),
                "bar_datetime": pd.Timestamp(bar_dt).strftime("%Y-%m-%d %H:%M:%S"),
                "open": latest.get("open", np.nan),
                "high": latest.get("high", np.nan),
                "low": latest.get("low", np.nan),
                "close": latest.get("close", np.nan),
                "volume": latest.get("volume", np.nan),
                "open_oi": latest.get("open_oi", np.nan),
                "close_oi": latest.get("close_oi", np.nan),
            }
            rows.append(values)
    except BacktestFinished:
        if status["status"] == "unknown":
            status["status"] = "downloaded"
    except Exception as exc:
        status["status"] = "failed"
        status["message"] = repr(exc)[:500]
    finally:
        if api is not None:
            api.close()

    raw = pd.DataFrame(rows)
    if not raw.empty:
        for column in ["open", "high", "low", "close", "volume", "open_oi", "close_oi"]:
            raw[column] = pd.to_numeric(raw[column], errors="coerce")
        raw = raw.dropna(subset=["trade_date"])
        raw = raw.drop_duplicates(["download_symbol", "trade_date"]).sort_values(["download_symbol", "trade_date"])
        raw = raw[REQUIRED_RAW_COLUMNS[:2] + ["vt_symbol", "download_symbol"] + REQUIRED_RAW_COLUMNS[2:]]
        raw.to_csv(raw_path, index=False, encoding="utf-8-sig")

    loaded = _read_raw(raw_path)
    if status["status"] == "unknown":
        status["status"] = "downloaded" if not loaded.empty else "empty"
    status["rows"] = int(len(loaded))
    status["source_dates_covered"] = int(_raw_covers_required_dates(loaded, required_source_dates))
    status["open_oi_ready"] = int("open_oi" in loaded.columns and loaded["open_oi"].notna().any())
    status["close_oi_ready"] = int("close_oi" in loaded.columns and loaded["close_oi"].notna().any())
    if not loaded.empty and "trade_date" in loaded.columns:
        dates = sorted(loaded["trade_date"].dropna().astype(str).unique())
        status["date_min"] = dates[0] if dates else ""
        status["date_max"] = dates[-1] if dates else ""
    status["elapsed_seconds"] = round(time.time() - started, 2)
    return status


def _download_all(plan: pd.DataFrame, gap_rows: pd.DataFrame, credential: dict[str, Any]) -> pd.DataFrame:
    if plan.empty:
        return pd.DataFrame()
    source_date_map: dict[str, set[str]] = {}
    for vt_symbol, group in gap_rows.groupby("vt_symbol"):
        dates = set(group["source_date"].dropna().dt.strftime("%Y-%m-%d").astype(str))
        source_date_map[str(vt_symbol)] = dates

    statuses: list[dict[str, Any]] = []
    for row in plan.itertuples(index=False):
        required_dates = source_date_map.get(str(row.vt_symbol), set())
        status = _extract_daily_backtest(row, required_dates, credential)
        statuses.append(status)
        pd.DataFrame(statuses).to_csv(STATUS_OUT, index=False, encoding="utf-8-sig")
        print(
            f"[{len(statuses)}/{len(plan)}] {status['download_symbol']} "
            f"{status['status']} rows={status['rows']} covered={status['source_dates_covered']}",
            flush=True,
        )
    return pd.DataFrame(statuses)


def _build_provenance(status: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for item in status.itertuples(index=False):
        raw_path = Path(str(item.raw_path))
        frame = _read_raw(raw_path)
        columns = list(frame.columns) if not frame.empty else []
        rows.append(
            {
                "vt_symbol": str(item.vt_symbol),
                "download_symbol": str(item.download_symbol),
                "raw_path": str(raw_path),
                "raw_exists": int(raw_path.exists() and raw_path.stat().st_size > 0),
                "raw_bytes": int(raw_path.stat().st_size) if raw_path.exists() else 0,
                "sha256": _sha256(raw_path) if raw_path.exists() and raw_path.stat().st_size > 0 else "",
                "schema_columns": ",".join(columns),
                "schema_hash": _schema_hash(columns) if columns else "",
                "row_count": int(len(frame)),
                "has_open_oi": int("open_oi" in columns),
                "has_close_oi": int("close_oi" in columns),
                "date_min": str(item.date_min),
                "date_max": str(item.date_max),
                "source_method": "tqsdk_backtest_get_kline_serial_86400",
                "duration_seconds": 86400,
                "raw_merge_to_primary_root": 0,
            }
        )
    return pd.DataFrame(rows)


def _build_gap_recheck(gap_rows: pd.DataFrame, status: pd.DataFrame) -> pd.DataFrame:
    status_by_symbol = status.set_index("vt_symbol").to_dict(orient="index") if not status.empty else {}
    rows: list[dict[str, Any]] = []
    for _, row in gap_rows.iterrows():
        action = str(row["repair_action"])
        vt_symbol = str(row["vt_symbol"])
        status_row = status_by_symbol.get(vt_symbol, {})
        if action == "calendar_holiday_gap_accept_with_trading_day_gate":
            raw_status = "calendar_adjacent_no_download_needed"
            raw_source_date_covered = 1
            raw_oi_ready = 1
        elif action.startswith("backfill_") or action.startswith("download_or_refresh_"):
            raw_path = Path(str(status_row.get("raw_path", "")))
            frame = _read_raw(raw_path)
            source_date = row["source_date"]
            source_text = "" if pd.isna(source_date) else pd.Timestamp(source_date).strftime("%Y-%m-%d")
            available = set(frame["trade_date"].dropna().astype(str)) if not frame.empty and "trade_date" in frame else set()
            raw_source_date_covered = int(bool(source_text) and source_text in available)
            raw_oi_ready = int(
                not frame.empty
                and "open_oi" in frame.columns
                and "close_oi" in frame.columns
                and frame[["open_oi", "close_oi"]].notna().any().all()
            )
            raw_status = str(status_row.get("status", "missing_status"))
        else:
            raw_status = "unsupported_repair_action"
            raw_source_date_covered = 0
            raw_oi_ready = 0
        rows.append(
            {
                "candidate_index": row["candidate_index"],
                "vt_symbol": vt_symbol,
                "download_symbol": status_row.get("download_symbol", ""),
                "exchange": row["exchange"],
                "entry_year": int(row["entry_year"]),
                "official_open_date": pd.Timestamp(row["official_open_date"]).strftime("%Y-%m-%d"),
                "source_date": pd.Timestamp(row["source_date"]).strftime("%Y-%m-%d")
                if pd.notna(row["source_date"])
                else "",
                "repair_action": action,
                "order_realized_pnl": float(row["order_realized_pnl"]),
                "right_tail_visual": int(row["right_tail_visual"]),
                "bottom_loss_visual": int(row["bottom_loss_visual"]),
                "raw_status": raw_status,
                "raw_source_date_covered": raw_source_date_covered,
                "raw_oi_ready": raw_oi_ready,
                "gap_resolved_by_stage106_raw": int(raw_source_date_covered and raw_oi_ready),
                "strategy_rule_allowed": 0,
            }
        )
    return pd.DataFrame(rows)


def _build_product_year_recheck(gap_recheck: pd.DataFrame) -> pd.DataFrame:
    if gap_recheck.empty:
        return pd.DataFrame()
    frame = gap_recheck.copy()
    frame["product"] = frame["vt_symbol"].str.extract(r"^([A-Za-z]+)")
    grouped = (
        frame.groupby(["product", "entry_year"], dropna=False)
        .agg(
            gap_row_count=("vt_symbol", "size"),
            resolved_gap_row_count=("gap_resolved_by_stage106_raw", "sum"),
            pnl_sum=("order_realized_pnl", "sum"),
            bottom_loss_count=("bottom_loss_visual", "sum"),
            right_tail_count=("right_tail_visual", "sum"),
        )
        .reset_index()
    )
    grouped["resolved_rate"] = grouped["resolved_gap_row_count"] / grouped["gap_row_count"].replace(0, np.nan)
    return grouped


def _nearest_curve_points(curve: pd.DataFrame, event_dates: pd.Series) -> pd.DataFrame:
    if curve.empty or event_dates.empty:
        return pd.DataFrame()
    left = pd.DataFrame({"event_date": pd.to_datetime(event_dates, errors="coerce").dt.normalize()}).dropna()
    right = curve[["date", "account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]].sort_values("date")
    return pd.merge_asof(left.sort_values("event_date"), right, left_on="event_date", right_on="date", direction="backward")


def _plot_path_chart(curve: pd.DataFrame, gap_recheck: pd.DataFrame) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(13, 9), sharex=True)
    axes[0].plot(curve["date"], curve["account_equity"] / 1_000_000, color="#1f2937", lw=1.2)
    axes[0].set_ylabel("equity (m)")
    axes[0].set_title("Stage106 official path with isolated OI backfill recheck")
    axes[1].plot(curve["date"], curve["drawdown_pct"], color="#b91c1c", lw=1.1)
    axes[1].set_ylabel("drawdown %")
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#0369a1", lw=1.1)
    axes[2].axhline(100, color="#991b1b", ls="--", lw=0.8, alpha=0.7)
    axes[2].set_ylabel("broker10 %")

    if not gap_recheck.empty:
        events = gap_recheck.copy()
        events["event_date"] = pd.to_datetime(events["official_open_date"], errors="coerce").dt.normalize()
        merged = _nearest_curve_points(curve, events["event_date"])
        events = events.sort_values("event_date").reset_index(drop=True)
        merged = merged.reset_index(drop=True)
        if len(events) == len(merged):
            events = pd.concat([events, merged[["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]]], axis=1)
            colors = np.where(events["gap_resolved_by_stage106_raw"].eq(1), "#15803d", "#dc2626")
            axes[0].scatter(events["event_date"], events["account_equity"] / 1_000_000, c=colors, s=34, edgecolor="white", lw=0.4)
            axes[1].scatter(events["event_date"], events["drawdown_pct"], c=colors, s=34, edgecolor="white", lw=0.4)
            axes[2].scatter(
                events["event_date"],
                events["broker10_margin_to_equity_pct"],
                c=colors,
                s=34,
                edgecolor="white",
                lw=0.4,
            )
    for ax in axes:
        ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_product_year(product_year: pd.DataFrame) -> None:
    if product_year.empty:
        return
    pivot = product_year.pivot(index="product", columns="entry_year", values="resolved_rate").sort_index()
    fig, ax = plt.subplots(figsize=(10, max(4.5, 0.35 * len(pivot))))
    image = ax.imshow(pivot.fillna(np.nan), vmin=0, vmax=1, cmap="RdYlGn", aspect="auto")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels([str(col) for col in pivot.columns], rotation=45, ha="right")
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    for y, product in enumerate(pivot.index):
        for x, year in enumerate(pivot.columns):
            value = pivot.loc[product, year]
            if pd.isna(value):
                continue
            row = product_year[(product_year["product"] == product) & (product_year["entry_year"] == year)].iloc[0]
            ax.text(x, y, f"{int(row.resolved_gap_row_count)}/{int(row.gap_row_count)}", ha="center", va="center", fontsize=8)
    ax.set_title("Stage106 product-year raw backfill resolved rate")
    fig.colorbar(image, ax=ax, fraction=0.025, pad=0.02)
    fig.tight_layout()
    fig.savefig(PRODUCT_YEAR_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_raw_rows(status: pd.DataFrame) -> None:
    if status.empty:
        return
    frame = status.sort_values("rows", ascending=True).copy()
    colors = np.where(
        frame["repair_action"].str.contains("near_endpoint", na=False),
        "#0f766e",
        "#7c3aed",
    )
    fig, ax = plt.subplots(figsize=(11, max(5, 0.32 * len(frame))))
    ax.barh(frame["download_symbol"], frame["rows"], color=colors, alpha=0.88)
    for y, row in enumerate(frame.itertuples(index=False)):
        ax.text(float(row.rows) + 0.5, y, str(row.status), va="center", fontsize=8)
    ax.set_xlabel("raw daily rows")
    ax.set_title("Stage106 raw daily rows by missing contract")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(RAW_ROWS_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_gate(gate: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(10, max(4.5, 0.45 * len(gate))))
    colors = np.where(gate["pass"].eq(1), "#15803d", "#dc2626")
    ax.barh(gate["gate"], gate["pass"], color=colors, alpha=0.9)
    ax.set_xlim(0, 1.05)
    ax.set_xlabel("pass")
    ax.set_title("Stage106 promotion gates")
    for y, (_, row) in enumerate(gate.iterrows()):
        passed = int(row["pass"])
        ax.text(0.03, y, str(row["detail"]), va="center", fontsize=8, color="white" if passed else "#111827")
    fig.tight_layout()
    fig.savefig(GATE_CHART_OUT, dpi=160)
    plt.close(fig)


def _build_gate(summary: dict[str, Any]) -> pd.DataFrame:
    rows = [
        {
            "gate": "credentials_present",
            "pass": int(summary["tqsdk_credentials_present"] == 1),
            "detail": f"user_len={summary['tqsdk_username_len']}, pass_len={summary['tqsdk_password_len']}",
        },
        {
            "gate": "query_or_backtest_route_available",
            "pass": int(summary["backtest_downloaded_or_cached_count"] > 0),
            "detail": f"raw={summary['backtest_downloaded_or_cached_count']}/{summary['repair_contract_count']}",
        },
        {
            "gate": "all_missing_contract_raw_files_ready",
            "pass": int(summary["backtest_downloaded_or_cached_count"] == summary["repair_contract_count"]),
            "detail": f"{summary['backtest_downloaded_or_cached_count']}/{summary['repair_contract_count']}",
        },
        {
            "gate": "all_missing_gap_source_dates_covered",
            "pass": int(summary["missing_gap_rows_resolved_by_stage106_raw_count"] == summary["missing_target_contract_file_gap_row_count"]),
            "detail": f"{summary['missing_gap_rows_resolved_by_stage106_raw_count']}/{summary['missing_target_contract_file_gap_row_count']}",
        },
        {
            "gate": "raw_provenance_complete",
            "pass": int(summary["raw_provenance_complete_count"] == summary["repair_contract_count"]),
            "detail": f"{summary['raw_provenance_complete_count']}/{summary['repair_contract_count']}",
        },
        {
            "gate": "primary_daily_root_merged",
            "pass": 0,
            "detail": "intentionally_not_merged",
        },
        {
            "gate": "stage104_stage105_reaudit_completed_after_merge",
            "pass": 0,
            "detail": "next_stage_required",
        },
        {
            "gate": "true_engine_or_ab_allowed",
            "pass": 0,
            "detail": "data_engineering_only",
        },
    ]
    return pd.DataFrame(rows)


def _write_report(
    summary: dict[str, Any],
    availability: pd.DataFrame,
    status: pd.DataFrame,
    provenance: pd.DataFrame,
    gap_recheck: pd.DataFrame,
    gate: pd.DataFrame,
) -> None:
    query_brief = (
        availability.groupby("query_quotes_symbol_available", dropna=False)
        .size()
        .reset_index(name="contract_count")
        .sort_values("query_quotes_symbol_available")
    )
    status_brief = (
        status.groupby(["repair_action", "status"], dropna=False)
        .agg(contract_count=("vt_symbol", "size"), rows_sum=("rows", "sum"), source_dates_covered=("source_dates_covered", "sum"))
        .reset_index()
    )
    unresolved = gap_recheck[gap_recheck["gap_resolved_by_stage106_raw"].eq(0)].copy()
    lines = [
        f"# {STAGE} contract-month OI TqSdk backtest backfill smoke",
        "",
        "## Decision",
        "",
        f"- decision: `{summary['decision']}`",
        "- This stage is isolated data backfill/provenance only. It does not merge raw files into the primary daily root and does not create a trading rule.",
        "",
        "## Key Metrics",
        "",
        _md_table(pd.DataFrame([summary])),
        "",
        "## Query Availability",
        "",
        _md_table(query_brief),
        "",
        "## Backtest Raw Status",
        "",
        _md_table(status_brief),
        "",
        "## Promotion Gates",
        "",
        _md_table(gate),
        "",
        "## Unresolved Gap Rows",
        "",
        _md_table(
            unresolved[
                [
                    "vt_symbol",
                    "official_open_date",
                    "source_date",
                    "repair_action",
                    "raw_status",
                    "raw_source_date_covered",
                    "raw_oi_ready",
                ]
            ],
            max_rows=30,
        ),
        "",
        "## Raw Provenance Sample",
        "",
        _md_table(
            provenance[
                [
                    "download_symbol",
                    "row_count",
                    "date_min",
                    "date_max",
                    "raw_bytes",
                    "sha256",
                    "schema_hash",
                    "raw_merge_to_primary_root",
                ]
            ],
            max_rows=25,
        ),
        "",
        "## Visual Outputs",
        "",
        f"- `{PATH_CHART_OUT}`",
        f"- `{PRODUCT_YEAR_CHART_OUT}`",
        f"- `{RAW_ROWS_CHART_OUT}`",
        f"- `{GATE_CHART_OUT}`",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_ROOT.mkdir(parents=True, exist_ok=True)

    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    gap_rows = _load_gap_rows()
    plan = _augment_plan_with_source_dates(_load_repair_manifest(), gap_rows)
    curve = _load_curve()
    summary105 = _read_csv(SUMMARY105_IN).iloc[0].to_dict()

    plan.to_csv(PLAN_OUT, index=False, encoding="utf-8-sig")

    credential = _credential_audit()
    availability = _query_availability(plan, credential)
    availability.to_csv(AVAILABILITY_OUT, index=False, encoding="utf-8-sig")

    status = _download_all(plan, gap_rows, credential)
    status.to_csv(STATUS_OUT, index=False, encoding="utf-8-sig")

    provenance = _build_provenance(status)
    provenance.to_csv(PROVENANCE_OUT, index=False, encoding="utf-8-sig")

    gap_recheck = _build_gap_recheck(gap_rows, status)
    gap_recheck.to_csv(GAP_RECHECK_OUT, index=False, encoding="utf-8-sig")

    product_year = _build_product_year_recheck(gap_recheck)
    product_year.to_csv(PRODUCT_YEAR_RECHECK_OUT, index=False, encoding="utf-8-sig")

    repair_contract_count = int(len(plan))
    raw_ready_mask = status["status"].isin(["downloaded", "cached_raw"]) if not status.empty else pd.Series(dtype=bool)
    raw_provenance_complete = int(
        (
            provenance["raw_exists"].eq(1)
            & provenance["sha256"].astype(str).ne("")
            & provenance["schema_hash"].astype(str).ne("")
            & provenance["has_open_oi"].eq(1)
            & provenance["has_close_oi"].eq(1)
        ).sum()
    )
    missing_file_gap = gap_recheck[
        gap_recheck["repair_action"].str.startswith("backfill_")
        | gap_recheck["repair_action"].str.startswith("download_or_refresh_")
    ]
    resolved_missing = int(missing_file_gap["gap_resolved_by_stage106_raw"].sum())
    total_missing = int(len(missing_file_gap))
    calendar_resolved = int(
        gap_recheck["repair_action"].eq("calendar_holiday_gap_accept_with_trading_day_gate").sum()
    )
    potential_ready = int(float(summary105.get("stage104_target_panel_ready_count", 0))) + calendar_resolved + resolved_missing
    timestamp_ready = int(float(summary105.get("timestamp_ready_order_count", 0)))

    summary: dict[str, Any] = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "created_at": created_at,
        "line_id": LINE_ID,
        "decision": "stage106_isolated_tqsdk_backtest_raw_backfill_all_gap_dates_covered_no_merge_no_rule"
        if resolved_missing == total_missing
        else "stage106_isolated_tqsdk_backtest_raw_backfill_partial_gap_dates_no_merge_no_rule",
        "official_config_changed": 0,
        "strategy_rule_created": 0,
        "true_engine_run": 0,
        "ab_triggered": 0,
        "order_api_called": 0,
        "ctp_connected": 0,
        "tqsdk_credentials_present": int(credential["username_present"] and credential["password_present"]),
        "tqsdk_username_len": int(credential["username_len"]),
        "tqsdk_password_len": int(credential["password_len"]),
        "repair_contract_count": repair_contract_count,
        "query_quotes_symbol_available_count": int(availability["query_quotes_symbol_available"].sum())
        if not availability.empty
        else 0,
        "query_quotes_symbol_unavailable_count": int(
            len(availability) - availability["query_quotes_symbol_available"].sum()
        )
        if not availability.empty
        else 0,
        "backtest_downloaded_or_cached_count": int(raw_ready_mask.sum()) if len(raw_ready_mask) else 0,
        "backtest_failed_or_empty_count": int((~raw_ready_mask).sum()) if len(raw_ready_mask) else repair_contract_count,
        "raw_provenance_complete_count": raw_provenance_complete,
        "missing_target_contract_file_gap_row_count": total_missing,
        "missing_gap_rows_resolved_by_stage106_raw_count": resolved_missing,
        "calendar_holiday_adjacent_reclassifiable_count": calendar_resolved,
        "potential_panel_ready_after_stage106_raw_count": potential_ready,
        "potential_panel_ready_after_stage106_raw_rate_pct": potential_ready / timestamp_ready * 100.0
        if timestamp_ready
        else np.nan,
        "primary_daily_root_merged": 0,
        "stage104_reaudit_done_after_merge": 0,
        "promotion_gate_count": 8,
        "promotion_gate_pass_count": 0,
        "panel_feature_rule_allowed": 0,
        "true_engine_allowed": 0,
        "strategy_feature_usable": 0,
        "end_equity": float(summary105.get("end_equity", np.nan)),
        "total_return_pct": float(summary105.get("total_return_pct", np.nan)),
        "max_drawdown_pct": float(summary105.get("max_drawdown_pct", np.nan)),
        "sharpe": float(summary105.get("sharpe", np.nan)),
        "total_slippage": float(summary105.get("total_slippage", np.nan)),
        "total_trade_count": float(summary105.get("total_trade_count", np.nan)),
        "closed_lot_win_rate_pct": float(summary105.get("closed_lot_win_rate_pct", np.nan)),
        "max_broker10_margin_to_equity_pct": float(summary105.get("max_broker10_margin_to_equity_pct", np.nan)),
    }

    gate = _build_gate(summary)
    summary["promotion_gate_pass_count"] = int(gate["pass"].sum())
    gate.to_csv(PROMOTION_GATE_OUT, index=False, encoding="utf-8-sig")

    pd.DataFrame([summary]).to_csv(SUMMARY_OUT, index=False, encoding="utf-8-sig")
    DECISION_OUT.write_text(json.dumps(_json_safe(summary), ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    _plot_path_chart(curve, gap_recheck)
    _plot_product_year(product_year)
    _plot_raw_rows(status)
    _plot_gate(gate)

    _write_report(summary, availability, status, provenance, gap_recheck, gate)
    print(json.dumps(_json_safe(summary), ensure_ascii=True, indent=2), flush=True)


if __name__ == "__main__":
    main()
