from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
import re
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
LEDGER_DIR = OUTPUT_DIR / "external_state_forward_ledger"
os.environ.setdefault("MPLCONFIGDIR", str(OUTPUT_DIR / ".matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


MODEL_TAG = "stage598_black_ferrous_p1_source_ledger_bootstrap_v1"
OUTPUT_PREFIX = "qmt_roll_stage598_black_ferrous_p1_source_ledger_bootstrap"
LINE_ID = "futures_trend_drawdown30_preserve_return"

STAGE597_PRODUCT_WORKLIST = OUTPUT_DIR / (
    "qmt_roll_stage597_new_family_source_tca_worklist_product_worklist_"
    "stage597_new_family_source_tca_worklist_v1.csv"
)
STAGE597_GATES = OUTPUT_DIR / (
    "qmt_roll_stage597_new_family_source_tca_worklist_gates_"
    "stage597_new_family_source_tca_worklist_v1.csv"
)
STAGE571_SOURCE_PRIORITY = OUTPUT_DIR / (
    "qmt_roll_stage571_external_selector_source_priority_audit_source_priority_"
    "stage571_external_selector_source_priority_audit_v1.csv"
)

SNAPSHOT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_snapshot_{MODEL_TAG}.csv"
ROUTE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_route_summary_{MODEL_TAG}.csv"
PRODUCT_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_summary_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
NEXT_ACTIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_next_actions_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

SCOPED_MASTER_LEDGER_PATH = LEDGER_DIR / "black_ferrous_p1_source_forward_ledger.csv"

P1_PRODUCTS = ["j.DCE", "i.DCE"]
PRODUCT_META = {
    "j.DCE": {
        "product_code": "J",
        "exchange": "DCE",
        "product_family": "black_ferrous",
        "cn_name": "焦炭",
        "inventory_symbols": ["j", "焦炭"],
    },
    "i.DCE": {
        "product_code": "I",
        "exchange": "DCE",
        "product_family": "black_ferrous",
        "cn_name": "铁矿石",
        "inventory_symbols": ["i", "铁矿石"],
    },
}

SOURCE_TIMEOUT_SECONDS = 8
LOOKBACK_DAYS = 7
MAX_RECORDS_PER_PROBE = 600
MAX_DICT_ITEM_RECORDS = 300
MAX_SOURCE_AGE_DAYS = 7
MIN_FORWARD_DATES = 20
MIN_TCA_PER_PRODUCT = 3
MIN_FORWARD_READY_ROUTES_PER_PRODUCT = 2
REQUIRED_ROUTES = ["basis", "inventory", "member_detail", "warehouse", "event_catalog"]

REFERENCE_LINKS = [
    "AKShare futures_dce_position_rank / get_dce_rank_table / futures_warehouse_receipt_dce",
    "Dalian Commodity Exchange official website: http://www.dce.com.cn",
    "Man Group trend-following market mix research: https://www.man.com/insights/trend-following-optimal-market-mix",
]


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if math.isnan(number) or math.isinf(number) else number
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _stable_hash(payload: Any) -> str:
    text = json.dumps(_json_safe(payload), ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _md_table(frame: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 30) -> str:
    if frame.empty:
        return "_empty_"
    view = frame.copy()
    if columns is not None:
        view = view[[col for col in columns if col in view.columns]]
    if len(view) > max_rows:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda item: f"{item:.4f}" if pd.notna(item) else "")
    return view.to_markdown(index=False)


def _num(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(default).astype(float)


def _candidate_dates(now_local: datetime) -> list[str]:
    day = pd.Timestamp(now_local.date())
    return [(day - pd.Timedelta(days=offset)).strftime("%Y%m%d") for offset in range(LOOKBACK_DAYS + 1)]


def _run_probe(function_name: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
    def worker(queue: mp.Queue) -> None:
        try:
            import akshare as ak

            fn = getattr(ak, function_name)
            result = fn(*args, **kwargs)
            if isinstance(result, pd.DataFrame):
                packed = result.tail(MAX_RECORDS_PER_PROBE).copy() if len(result) > MAX_RECORDS_PER_PROBE else result.copy()
                queue.put(
                    {
                        "status": "ok",
                        "kind": "dataframe",
                        "rows": int(len(result)),
                        "columns": list(packed.columns),
                        "records": packed.to_dict("records"),
                        "records_limited": int(len(result) > MAX_RECORDS_PER_PROBE),
                    }
                )
            elif isinstance(result, dict):
                packed_items: dict[str, Any] = {}
                for key, item in result.items():
                    if isinstance(item, pd.DataFrame):
                        packed = item.tail(MAX_DICT_ITEM_RECORDS).copy() if len(item) > MAX_DICT_ITEM_RECORDS else item.copy()
                        packed_items[str(key)] = {
                            "rows": int(len(item)),
                            "columns": list(packed.columns),
                            "records": packed.to_dict("records"),
                            "records_limited": int(len(item) > MAX_DICT_ITEM_RECORDS),
                        }
                    else:
                        packed_items[str(key)] = {"type": type(item).__name__, "repr": str(item)[:500]}
                queue.put({"status": "ok", "kind": "dict", "keys": list(result.keys()), "items": packed_items})
            else:
                queue.put({"status": "ok", "kind": type(result).__name__, "repr": str(result)[:500]})
        except Exception as exc:  # pragma: no cover - external endpoints are unstable
            queue.put({"status": "error", "error_type": type(exc).__name__, "error_message": str(exc)[:700]})

    ctx = mp.get_context("fork")
    queue: mp.Queue = ctx.Queue()
    process = ctx.Process(target=worker, args=(queue,))
    process.start()
    process.join(SOURCE_TIMEOUT_SECONDS)
    if process.is_alive():
        process.terminate()
        process.join(2)
        return {"status": "timeout", "error_type": "Timeout", "error_message": f">{SOURCE_TIMEOUT_SECONDS}s"}
    if queue.empty():
        return {"status": "empty", "error_type": "EmptyResult", "error_message": "worker returned no message"}
    return queue.get()


def _latest_success(function_name: str, dates: list[str], *args: Any, max_attempts: int | None = None, **kwargs: Any) -> tuple[str, dict[str, Any]]:
    trial_dates = dates if max_attempts is None else dates[:max_attempts]
    last: dict[str, Any] = {"status": "not_attempted", "error_type": "NoAttempt", "error_message": "no candidate date"}
    for day in trial_dates:
        probe = _run_probe(function_name, day, *args, **kwargs)
        last = probe
        if probe.get("status") == "ok":
            rows = int(probe.get("rows", 0) or 0)
            keys = len(probe.get("keys", []) or [])
            if rows > 0 or keys > 0:
                return day, probe
    return trial_dates[0] if trial_dates else dates[0], last


def _base_row(run_id: str, now_local: datetime, now_utc: datetime, symbol: str, route: str) -> dict[str, Any]:
    meta = PRODUCT_META[symbol]
    return {
        "run_id": run_id,
        "received_at_local": now_local.isoformat(timespec="seconds"),
        "received_at_utc": now_utc.isoformat(timespec="seconds"),
        "line_id": LINE_ID,
        "route": route,
        "product_vt_symbol": symbol,
        "product_code": meta["product_code"],
        "exchange": meta["exchange"],
        "product_family": meta["product_family"],
        "source_name": "",
        "source_function": "",
        "source_authority": "",
        "source_url": "",
        "request_key": "",
        "source_date": "",
        "published_at": "",
        "source_age_days": np.nan,
        "status": "missing",
        "error_type": "",
        "error_message": "",
        "source_key": "",
        "matched_product": 0,
        "rows_returned": 0,
        "usable_for_forward_monitor": 0,
        "usable_for_history_selector": 0,
        "official_auto_monitor_ready": 0,
        "third_party_forward_ready": 0,
        "data_value_json": "{}",
        "raw_sha256": "",
        "point_in_time_rule": "Only data persisted by received_at_local can be used by future paper/live decisions; never backfill.",
        "notes": "",
    }


def _collect_basis(run_id: str, now_local: datetime, now_utc: datetime) -> list[dict[str, Any]]:
    dates = _candidate_dates(now_local)
    codes = [PRODUCT_META[symbol]["product_code"] for symbol in P1_PRODUCTS]
    request_date, probe = _latest_success("futures_spot_price", dates, codes)
    frame = pd.DataFrame(probe.get("records", [])) if probe.get("kind") == "dataframe" else pd.DataFrame()
    if not frame.empty and "symbol" in frame.columns:
        frame["symbol"] = frame["symbol"].astype(str).str.upper()

    rows: list[dict[str, Any]] = []
    for symbol in P1_PRODUCTS:
        meta = PRODUCT_META[symbol]
        row = _base_row(run_id, now_local, now_utc, symbol, "basis")
        row.update(
            {
                "source_name": "AKShare futures_spot_price / 生意社基差",
                "source_function": "futures_spot_price",
                "source_authority": "third_party",
                "source_url": "https://www.100ppi.com/",
                "request_key": request_date,
                "status": str(probe.get("status")),
                "error_type": probe.get("error_type", ""),
                "error_message": probe.get("error_message", ""),
            }
        )
        if probe.get("status") != "ok":
            rows.append(row)
            continue
        matched = frame[frame["symbol"].eq(str(meta["product_code"]).upper())] if not frame.empty else pd.DataFrame()
        if matched.empty:
            row.update({"status": "missing_product", "rows_returned": int(len(frame)), "notes": "source returned no product row"})
            rows.append(row)
            continue
        rec = matched.iloc[-1].to_dict()
        source_date = str(rec.get("date", request_date)).replace("-", "")
        age = (pd.Timestamp(now_local.date()) - pd.Timestamp(source_date)).days
        value = {
            "spot_price": rec.get("spot_price"),
            "dominant_contract": rec.get("dominant_contract"),
            "dominant_contract_price": rec.get("dominant_contract_price"),
            "dom_basis": rec.get("dom_basis"),
            "dom_basis_rate": rec.get("dom_basis_rate"),
            "near_contract": rec.get("near_contract"),
            "near_basis_rate": rec.get("near_basis_rate"),
        }
        row.update(
            {
                "source_date": source_date,
                "source_age_days": float(age),
                "source_key": str(rec.get("dominant_contract", rec.get("symbol", ""))),
                "status": "ok",
                "matched_product": 1,
                "rows_returned": int(len(matched)),
                "usable_for_forward_monitor": int(age <= MAX_SOURCE_AGE_DAYS),
                "third_party_forward_ready": int(age <= MAX_SOURCE_AGE_DAYS),
                "data_value_json": json.dumps(_json_safe(value), ensure_ascii=False, sort_keys=True),
                "raw_sha256": _stable_hash(rec),
                "notes": "basis is a third-party forward monitor; not history selector.",
            }
        )
        rows.append(row)
    return rows


def _collect_inventory(run_id: str, now_local: datetime, now_utc: datetime) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for symbol in P1_PRODUCTS:
        meta = PRODUCT_META[symbol]
        row = _base_row(run_id, now_local, now_utc, symbol, "inventory")
        row.update(
            {
                "source_name": "AKShare futures_inventory_em / 东方财富库存",
                "source_function": "futures_inventory_em",
                "source_authority": "third_party",
                "source_url": "https://data.eastmoney.com/ifdata/kcsj.html",
            }
        )
        last_probe: dict[str, Any] = {}
        used_symbol = ""
        frame = pd.DataFrame()
        for source_symbol in meta["inventory_symbols"]:
            probe = _run_probe("futures_inventory_em", source_symbol)
            last_probe = probe
            used_symbol = str(source_symbol)
            if probe.get("status") == "ok" and int(probe.get("rows", 0) or 0) > 0:
                frame = pd.DataFrame(probe.get("records", []))
                break
        row.update({"request_key": used_symbol, "status": str(last_probe.get("status")), "error_type": last_probe.get("error_type", ""), "error_message": last_probe.get("error_message", "")})
        if frame.empty:
            rows.append(row)
            continue
        date_col = "日期" if "日期" in frame.columns else frame.columns[0]
        frame["_date"] = pd.to_datetime(frame[date_col], errors="coerce")
        frame = frame[frame["_date"].notna()].sort_values("_date")
        if frame.empty:
            row.update({"status": "date_parse_failed"})
            rows.append(row)
            continue
        rec = frame.iloc[-1].to_dict()
        source_date = pd.Timestamp(rec["_date"]).strftime("%Y%m%d")
        age = (pd.Timestamp(now_local.date()) - pd.Timestamp(source_date)).days
        value = {
            "symbol_used": used_symbol,
            "inventory": rec.get("库存", rec.get("inventory")),
            "change": rec.get("增减", rec.get("change")),
            "rows": int(len(frame)),
            "min_date": pd.Timestamp(frame["_date"].min()).strftime("%Y-%m-%d"),
            "max_date": pd.Timestamp(frame["_date"].max()).strftime("%Y-%m-%d"),
        }
        row.update(
            {
                "source_date": source_date,
                "source_age_days": float(age),
                "source_key": used_symbol,
                "status": "ok",
                "matched_product": 1,
                "rows_returned": int(len(frame)),
                "usable_for_forward_monitor": int(age <= MAX_SOURCE_AGE_DAYS),
                "third_party_forward_ready": int(age <= MAX_SOURCE_AGE_DAYS),
                "data_value_json": json.dumps(_json_safe(value), ensure_ascii=False, sort_keys=True),
                "raw_sha256": _stable_hash(value),
                "notes": "inventory is a third-party forward monitor; not history selector.",
            }
        )
        rows.append(row)
    return rows


def _contract_key_matches(key: str, code: str) -> bool:
    text = str(key).lower()
    code_text = code.lower()
    return bool(re.match(rf"^{re.escape(code_text)}\d", text))


def _aggregate_member_items(items: dict[str, Any], code: str) -> tuple[str, dict[str, Any] | None]:
    matched_keys = [key for key in items if _contract_key_matches(str(key), code)]
    frames: list[pd.DataFrame] = []
    for key in matched_keys:
        item = items.get(key, {})
        records = item.get("records", []) if isinstance(item, dict) else []
        if records:
            frames.append(pd.DataFrame(records))
    if not frames:
        return "", None
    frame = pd.concat(frames, ignore_index=True)
    value: dict[str, Any] = {"contract_keys": matched_keys, "row_count": int(len(frame))}
    for column in [
        "long_open_interest",
        "short_open_interest",
        "long_open_interest_chg",
        "short_open_interest_chg",
        "vol",
        "vol_chg",
    ]:
        if column in frame.columns:
            value[column + "_sum"] = float(pd.to_numeric(frame[column], errors="coerce").fillna(0.0).sum())
    if "long_open_interest_sum" in value and "short_open_interest_sum" in value:
        value["top_member_net_long_sum"] = float(value["long_open_interest_sum"] - value["short_open_interest_sum"])
    return ",".join(map(str, matched_keys[:8])), value


def _collect_member_detail(run_id: str, now_local: datetime, now_utc: datetime) -> list[dict[str, Any]]:
    dates = _candidate_dates(now_local)
    codes = [PRODUCT_META[symbol]["product_code"] for symbol in P1_PRODUCTS]
    date_a, probe_a = _latest_success("get_dce_rank_table", dates, vars_list=sorted(codes), max_attempts=2)
    date_b, probe_b = _latest_success("futures_dce_position_rank", dates, vars_list=sorted(codes), max_attempts=2)
    request_date, probe, source_function = (
        (date_a, probe_a, "get_dce_rank_table")
        if probe_a.get("status") == "ok"
        else (date_b, probe_b, "futures_dce_position_rank")
    )
    items = probe.get("items", {}) if probe.get("kind") == "dict" else {}
    rows: list[dict[str, Any]] = []
    for symbol in P1_PRODUCTS:
        meta = PRODUCT_META[symbol]
        row = _base_row(run_id, now_local, now_utc, symbol, "member_detail")
        row.update(
            {
                "source_name": "DCE member position rank via AKShare",
                "source_function": source_function,
                "source_authority": "official_exchange_via_library",
                "source_url": "http://www.dce.com.cn/",
                "request_key": request_date,
                "status": str(probe.get("status")),
                "error_type": probe.get("error_type", ""),
                "error_message": probe.get("error_message", ""),
            }
        )
        if probe.get("status") != "ok":
            rows.append(row)
            continue
        source_key, value = _aggregate_member_items(items, meta["product_code"])
        if value is None:
            row.update({"status": "missing_product", "notes": f"source returned no exact contract key for {meta['product_code']}"})
            rows.append(row)
            continue
        age = (pd.Timestamp(now_local.date()) - pd.Timestamp(request_date)).days
        row.update(
            {
                "source_date": request_date,
                "source_age_days": float(age),
                "source_key": source_key,
                "status": "ok",
                "matched_product": 1,
                "rows_returned": int(value.get("row_count", 0)),
                "usable_for_forward_monitor": int(age <= MAX_SOURCE_AGE_DAYS),
                "official_auto_monitor_ready": int(age <= MAX_SOURCE_AGE_DAYS),
                "data_value_json": json.dumps(_json_safe(value), ensure_ascii=False, sort_keys=True),
                "raw_sha256": _stable_hash(value),
                "notes": "official exchange member detail via parser; forward monitor only.",
            }
        )
        rows.append(row)
    return rows


def _aggregate_warehouse_value(records: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not records:
        return None
    frame = pd.DataFrame(records)
    value: dict[str, Any] = {"row_count": int(len(frame))}
    for candidates, output in [
        (["今日仓单量", "仓单数量", "WRTWGHTS"], "warehouse_receipt_quantity"),
        (["增减", "当日增减", "WRTCHANGE"], "warehouse_receipt_change"),
        (["有效预报"], "valid_forecast"),
    ]:
        for column in candidates:
            if column in frame.columns:
                value[output] = float(pd.to_numeric(frame[column], errors="coerce").fillna(0.0).sum())
                break
    return value


def _collect_warehouse(run_id: str, now_local: datetime, now_utc: datetime) -> list[dict[str, Any]]:
    dates = _candidate_dates(now_local)
    request_date, probe = _latest_success("futures_warehouse_receipt_dce", dates, max_attempts=2)
    items = probe.get("items", {}) if probe.get("kind") == "dict" else {}
    key_lookup = {str(key).upper(): key for key in items}
    cn_lookup = {PRODUCT_META[symbol]["cn_name"]: symbol for symbol in P1_PRODUCTS}

    rows: list[dict[str, Any]] = []
    for symbol in P1_PRODUCTS:
        meta = PRODUCT_META[symbol]
        row = _base_row(run_id, now_local, now_utc, symbol, "warehouse")
        row.update(
            {
                "source_name": "DCE warehouse receipt daily via AKShare",
                "source_function": "futures_warehouse_receipt_dce",
                "source_authority": "official_exchange_via_library",
                "source_url": "http://www.dce.com.cn/",
                "request_key": request_date,
                "status": str(probe.get("status")),
                "error_type": probe.get("error_type", ""),
                "error_message": probe.get("error_message", ""),
            }
        )
        if probe.get("status") != "ok":
            rows.append(row)
            continue
        item_key = key_lookup.get(meta["product_code"]) or key_lookup.get(meta["cn_name"].upper())
        if item_key is None:
            for key in items:
                if str(key) == meta["cn_name"]:
                    item_key = key
                    break
        records = items.get(item_key, {}).get("records", []) if item_key is not None else []
        value = _aggregate_warehouse_value(records)
        if value is None:
            row.update({"status": "missing_product", "notes": f"warehouse source did not include {meta['product_code']}/{meta['cn_name']}"})
            rows.append(row)
            continue
        age = (pd.Timestamp(now_local.date()) - pd.Timestamp(request_date)).days
        row.update(
            {
                "source_date": request_date,
                "source_age_days": float(age),
                "source_key": str(item_key),
                "status": "ok",
                "matched_product": 1,
                "rows_returned": int(value.get("row_count", 0)),
                "usable_for_forward_monitor": int(age <= MAX_SOURCE_AGE_DAYS),
                "official_auto_monitor_ready": int(age <= MAX_SOURCE_AGE_DAYS),
                "data_value_json": json.dumps(_json_safe(value), ensure_ascii=False, sort_keys=True),
                "raw_sha256": _stable_hash(value),
                "notes": "official warehouse route via parser; forward monitor only.",
            }
        )
        rows.append(row)
    return rows


def _catalog_event_rows(run_id: str, now_local: datetime, now_utc: datetime) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    catalog = [
        {
            "symbol": "j.DCE",
            "source_name": "DCE coke futures notices / delivery rules entry",
            "notes": "catalog only; exact notice monitor not wired.",
        },
        {
            "symbol": "i.DCE",
            "source_name": "DCE iron ore futures notices / delivery rules entry",
            "notes": "catalog only; exact notice monitor not wired.",
        },
    ]
    for item in catalog:
        symbol = item["symbol"]
        row = _base_row(run_id, now_local, now_utc, symbol, "event_catalog")
        row.update(
            {
                "source_name": item["source_name"],
                "source_function": "catalog_only_no_parser",
                "source_authority": "official_exchange_catalog",
                "source_url": "http://www.dce.com.cn/",
                "request_key": "",
                "status": "catalog_only_not_monitor_wired",
                "matched_product": 1,
                "rows_returned": 0,
                "usable_for_forward_monitor": 0,
                "usable_for_history_selector": 0,
                "official_auto_monitor_ready": 0,
                "third_party_forward_ready": 0,
                "raw_sha256": _stable_hash({"source_url": "http://www.dce.com.cn/", "symbol": symbol, "route": "event_catalog"}),
                "notes": item["notes"],
            }
        )
        rows.append(row)
    return rows


def _build_snapshot() -> pd.DataFrame:
    now_local = datetime.now().astimezone()
    now_utc = now_local.astimezone(timezone.utc)
    run_id = now_local.strftime("stage598_%Y%m%d_%H%M%S")
    rows: list[dict[str, Any]] = []
    rows.extend(_collect_basis(run_id, now_local, now_utc))
    rows.extend(_collect_inventory(run_id, now_local, now_utc))
    rows.extend(_collect_member_detail(run_id, now_local, now_utc))
    rows.extend(_collect_warehouse(run_id, now_local, now_utc))
    rows.extend(_catalog_event_rows(run_id, now_local, now_utc))
    return pd.DataFrame(rows)


def _append_scoped_master(snapshot: pd.DataFrame) -> pd.DataFrame:
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    if SCOPED_MASTER_LEDGER_PATH.exists() and SCOPED_MASTER_LEDGER_PATH.stat().st_size > 0:
        existing = pd.read_csv(SCOPED_MASTER_LEDGER_PATH, encoding="utf-8-sig")
        combined = pd.concat([existing, snapshot], ignore_index=True, sort=False)
    else:
        combined = snapshot.copy()
    received = pd.to_datetime(combined["received_at_local"], errors="coerce")
    combined["_received_date"] = received.dt.date.astype(str)
    combined = combined.drop_duplicates(["_received_date", "product_vt_symbol", "route"], keep="last")
    combined = combined.drop(columns=["_received_date"])
    combined.to_csv(SCOPED_MASTER_LEDGER_PATH, index=False, encoding="utf-8-sig")
    return combined


def _route_summary(snapshot: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for route, frame in snapshot.groupby("route", sort=True):
        rows.append(
            {
                "route": route,
                "rows": int(len(frame)),
                "ok_rows": int(frame["status"].eq("ok").sum()),
                "forward_ready_rows": int(_num(frame, "usable_for_forward_monitor").sum()),
                "official_ready_rows": int(_num(frame, "official_auto_monitor_ready").sum()),
                "third_party_ready_rows": int(_num(frame, "third_party_forward_ready").sum()),
                "hash_ready_rows": int(frame["raw_sha256"].astype(str).str.len().gt(0).sum()),
                "history_ready_rows": int(_num(frame, "usable_for_history_selector").sum()),
            }
        )
    return pd.DataFrame(rows).sort_values("route")


def _product_summary(snapshot: pd.DataFrame, master: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for symbol in P1_PRODUCTS:
        frame = snapshot[snapshot["product_vt_symbol"].eq(symbol)].copy()
        master_frame = master[master["product_vt_symbol"].eq(symbol)].copy() if not master.empty else pd.DataFrame()
        dates = pd.to_datetime(master_frame.get("received_at_local", pd.Series(dtype=str)), errors="coerce").dropna()
        qualified_dates = int(dates.dt.date.nunique()) if not dates.empty else 0
        ready_routes = int(_num(frame, "usable_for_forward_monitor").sum())
        official_routes = int(_num(frame, "official_auto_monitor_ready").sum())
        third_party_routes = int(_num(frame, "third_party_forward_ready").sum())
        rows.append(
            {
                "product_vt_symbol": symbol,
                "product_family": PRODUCT_META[symbol]["product_family"],
                "routes": int(frame["route"].nunique()),
                "ok_routes": int(frame["status"].eq("ok").sum()),
                "forward_ready_routes": ready_routes,
                "official_ready_routes": official_routes,
                "third_party_ready_routes": third_party_routes,
                "event_monitor_ready": int((frame["route"].eq("event_catalog") & _num(frame, "official_auto_monitor_ready").gt(0)).sum()),
                "history_ready_routes": int(_num(frame, "usable_for_history_selector").sum()),
                "hash_ready_routes": int(frame["raw_sha256"].astype(str).str.len().gt(0).sum()),
                "qualified_received_dates": qualified_dates,
                "ready_for_predictive_audit": int(
                    ready_routes >= MIN_FORWARD_READY_ROUTES_PER_PRODUCT
                    and qualified_dates >= MIN_FORWARD_DATES
                    and int(_num(frame, "usable_for_history_selector").sum()) == 0
                ),
            }
        )
    return pd.DataFrame(rows)


def _existing_stage597_metrics() -> dict[str, Any]:
    if not STAGE597_PRODUCT_WORKLIST.exists():
        return {}
    frame = pd.read_csv(STAGE597_PRODUCT_WORKLIST, encoding="utf-8-sig")
    p1 = frame[frame["tier"].astype(str).eq("P1_new_family_candidate") & frame["product_family"].astype(str).eq("black_ferrous")]
    return {
        "p1_products": int(len(p1)),
        "p1_positive_pnl": float(_num(p1, "total_pnl").clip(lower=0).sum()) if not p1.empty else 0.0,
        "p1_max_core_corr": float(_num(p1, "abs_core_daily_pnl_corr").max()) if not p1.empty else np.nan,
    }


def _source_priority_depth() -> tuple[int, int]:
    if not STAGE571_SOURCE_PRIORITY.exists():
        return 0, 0
    frame = pd.read_csv(STAGE571_SOURCE_PRIORITY, encoding="utf-8-sig")
    runs = int(pd.to_numeric(frame.get("qualified_forward_runs", pd.Series([0])), errors="coerce").fillna(0).max())
    dates = int(pd.to_numeric(frame.get("qualified_forward_dates", pd.Series([0])), errors="coerce").fillna(0).max())
    return runs, dates


def _build_gates(snapshot: pd.DataFrame, route_summary: pd.DataFrame, product_summary: pd.DataFrame) -> pd.DataFrame:
    p1_metrics = _existing_stage597_metrics()
    runs, dates = _source_priority_depth()
    all_products_ready_routes = bool((product_summary["forward_ready_routes"] >= MIN_FORWARD_READY_ROUTES_PER_PRODUCT).all())
    all_official_member_warehouse = bool(
        (
            product_summary["official_ready_routes"]
            >= 2
        ).all()
    )
    hash_forward = snapshot[snapshot["usable_for_forward_monitor"].eq(1)]["raw_sha256"].astype(str).str.len().gt(0)
    history_disabled = bool(snapshot["usable_for_history_selector"].eq(0).all())
    rows = [
        {
            "gate": "stage597_p1_scope_loaded",
            "actual": f"{p1_metrics.get('p1_products', 0)} products, pnl={p1_metrics.get('p1_positive_pnl', 0.0):.2f}, max_corr={p1_metrics.get('p1_max_core_corr', np.nan):.4f}",
            "threshold": "j/i P1 scope exists and low corr",
            "passed": int(p1_metrics.get("p1_products", 0) == 2 and float(p1_metrics.get("p1_max_core_corr", 1.0)) <= 0.10),
            "hard_gate": 1,
            "judgement": "Stage597 scope is available and remains a source/TCA worklist, not whitelist.",
        },
        {
            "gate": "current_snapshot_forward_routes",
            "actual": f"{int(product_summary['forward_ready_routes'].min())} min ready routes per product",
            "threshold": f">={MIN_FORWARD_READY_ROUTES_PER_PRODUCT}",
            "passed": int(all_products_ready_routes),
            "hard_gate": 1,
            "judgement": "Each product needs at least two current forward-ready routes.",
        },
        {
            "gate": "official_member_warehouse_ready",
            "actual": f"{int(product_summary['official_ready_routes'].min())} min official ready routes per product",
            "threshold": ">=2 member+warehouse preferred",
            "passed": int(all_official_member_warehouse),
            "hard_gate": 0,
            "judgement": "Official routes are required before treating this as more than third-party monitor.",
        },
        {
            "gate": "event_monitor_ready",
            "actual": f"{int(product_summary['event_monitor_ready'].sum())}/2 products",
            "threshold": "2/2 exact event monitors",
            "passed": int(product_summary["event_monitor_ready"].sum() == len(P1_PRODUCTS)),
            "hard_gate": 0,
            "judgement": "DCE event route is still catalog-only.",
        },
        {
            "gate": "forward_hash_ready",
            "actual": f"{int(hash_forward.sum())}/{int(len(hash_forward))} forward rows hashed",
            "threshold": "all forward-ready rows",
            "passed": int(hash_forward.all()) if len(hash_forward) else 0,
            "hard_gate": 1,
            "judgement": "Raw hash is required to prevent silent source edits.",
        },
        {
            "gate": "history_selector_disabled",
            "actual": f"{int(snapshot['usable_for_history_selector'].sum())} history-ready rows",
            "threshold": "0",
            "passed": int(history_disabled),
            "hard_gate": 1,
            "judgement": "Forward snapshot must not be backfilled into historical selector tests.",
        },
        {
            "gate": "black_ferrous_scoped_dates",
            "actual": f"{int(product_summary['qualified_received_dates'].min())} min scoped received dates",
            "threshold": f">={MIN_FORWARD_DATES}",
            "passed": int((product_summary["qualified_received_dates"] >= MIN_FORWARD_DATES).all()),
            "hard_gate": 1,
            "judgement": "Stage598 starts or extends the ledger; it does not satisfy 20-date predictive gate yet.",
        },
        {
            "gate": "global_forward_sample_depth",
            "actual": f"runs={runs}, dates={dates}",
            "threshold": f"runs>={MIN_FORWARD_DATES}, dates>={MIN_FORWARD_DATES}",
            "passed": int(runs >= MIN_FORWARD_DATES and dates >= MIN_FORWARD_DATES),
            "hard_gate": 1,
            "judgement": "Global source-depth gate remains blocked.",
        },
        {
            "gate": "new_family_live_tca_samples",
            "actual": "0/6 inferred valid samples",
            "threshold": f">={len(P1_PRODUCTS) * MIN_TCA_PER_PRODUCT}",
            "passed": 0,
            "hard_gate": 1,
            "judgement": "Source ledger does not replace live/independent TCA evidence.",
        },
        {
            "gate": "paper_selector_allowed",
            "actual": "false",
            "threshold": "all hard gates and fixed IC/bucket audit",
            "passed": 0,
            "hard_gate": 1,
            "judgement": "No PnL replay or paper sleeve allowed from this snapshot.",
        },
    ]
    return pd.DataFrame(rows)


def _build_next_actions(product_summary: pd.DataFrame, gates: pd.DataFrame) -> pd.DataFrame:
    rows = [
        {
            "priority": 1,
            "scope": "black_ferrous_source",
            "targets": "j.DCE,i.DCE",
            "action": "每日复跑本脚本，只计一个 received_at 日期；累计20日后再做固定IC/bucket审计。",
            "done_condition": "qualified_received_dates>=20 且 history_selector_ready=0",
        },
        {
            "priority": 2,
            "scope": "dce_official_routes",
            "targets": "j.DCE,i.DCE",
            "action": "若 member/warehouse 仍缺，优先冻结 DCE 官方 endpoint/AKShare parser 的 exact source_url 与 raw payload。",
            "done_condition": "member_detail + warehouse 对 j/i 均 official_auto_monitor_ready=1",
        },
        {
            "priority": 3,
            "scope": "event_monitor",
            "targets": "j.DCE,i.DCE",
            "action": "补 DCE 焦炭/铁矿石公告与交割规则事件 monitor；catalog-only 不计 event_ready。",
            "done_condition": "event_monitor_ready=2/2 with published_at/source_url/raw_sha256",
        },
        {
            "priority": 4,
            "scope": "tca",
            "targets": "j.DCE,i.DCE",
            "action": "每品种至少补3个真实或独立分钟证据TCA样本。",
            "done_condition": "valid_live_or_independent_tca_samples>=6",
        },
    ]
    for _, gate in gates[(gates["hard_gate"].eq(1)) & (gates["passed"].eq(0))].iterrows():
        rows.append(
            {
                "priority": 5,
                "scope": str(gate["gate"]),
                "targets": "j.DCE,i.DCE",
                "action": str(gate["judgement"]),
                "done_condition": str(gate["threshold"]),
            }
        )
    return pd.DataFrame(rows).sort_values(["priority", "scope"]).reset_index(drop=True)


def _build_decision(snapshot: pd.DataFrame, product_summary: pd.DataFrame, gates: pd.DataFrame, master: pd.DataFrame) -> dict[str, Any]:
    hard = gates[gates["hard_gate"].eq(1)]
    decision = "black_ferrous_p1_source_ledger_started_no_paper"
    if int(hard["passed"].sum()) <= 2:
        decision = "black_ferrous_p1_source_ledger_blocked_no_paper"
    return {
        "stage": "Stage298",
        "script_stage": "Stage598",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at_local": datetime.now().astimezone().isoformat(timespec="seconds"),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "decision": decision,
        "promotion_allowed": False,
        "paper_selector_allowed": False,
        "trading_whitelist_allowed": False,
        "snapshot_rows": int(len(snapshot)),
        "scoped_master_rows": int(len(master)),
        "min_forward_ready_routes": int(product_summary["forward_ready_routes"].min()),
        "min_scoped_received_dates": int(product_summary["qualified_received_dates"].min()),
        "hard_gates_passed": int(hard["passed"].sum()),
        "hard_gates_total": int(len(hard)),
        "main_judgement": "j/i source ledger can be started/extended, but it is still forward evidence only and cannot support paper or whitelist.",
        "overfit_boundary": "No return replay, no product selection by realized PnL, all history selector flags remain 0.",
        "next_step": "Keep daily point-in-time collection and add 3 TCA samples per P1 product before any fixed sleeve test.",
    }


def _plot(snapshot: pd.DataFrame, route_summary: pd.DataFrame, product_summary: pd.DataFrame, gates: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    fig.suptitle("Stage598 black_ferrous P1 source ledger bootstrap", fontsize=15)

    ax = axes[0, 0]
    readiness = snapshot.pivot_table(
        index="product_vt_symbol",
        columns="route",
        values="usable_for_forward_monitor",
        aggfunc="max",
        fill_value=0,
    ).reindex(index=P1_PRODUCTS).reindex(columns=REQUIRED_ROUTES, fill_value=0)
    im = ax.imshow(readiness.to_numpy(dtype=float), vmin=0, vmax=1, cmap="RdYlGn", aspect="auto")
    ax.set_title("Current forward readiness")
    ax.set_xticks(np.arange(len(readiness.columns)))
    ax.set_xticklabels(readiness.columns, rotation=25, ha="right")
    ax.set_yticks(np.arange(len(readiness.index)))
    ax.set_yticklabels(readiness.index)
    for i in range(readiness.shape[0]):
        for j in range(readiness.shape[1]):
            ax.text(j, i, int(readiness.iloc[i, j]), ha="center", va="center", fontsize=9)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    ax = axes[0, 1]
    x = np.arange(len(route_summary))
    width = 0.25
    ax.bar(x - width, route_summary["ok_rows"], width, label="ok", color="#2ca02c")
    ax.bar(x, route_summary["official_ready_rows"], width, label="official", color="#1f77b4")
    ax.bar(x + width, route_summary["third_party_ready_rows"], width, label="third-party", color="#ffbf00")
    ax.set_title("Route status by source authority")
    ax.set_xticks(x)
    ax.set_xticklabels(route_summary["route"], rotation=25, ha="right")
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.25)

    ax = axes[1, 0]
    labels = product_summary["product_vt_symbol"]
    x = np.arange(len(labels))
    ax.bar(x - width, product_summary["forward_ready_routes"], width, label="ready routes")
    ax.bar(x, product_summary["official_ready_routes"], width, label="official ready")
    ax.bar(x + width, product_summary["qualified_received_dates"], width, label="received dates")
    ax.axhline(MIN_FORWARD_DATES, color="red", linestyle="--", linewidth=1, label="20 dates")
    ax.set_title("Product readiness and sample depth")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.25)

    ax = axes[1, 1]
    gate_view = gates.copy()
    gate_view["passed"] = gate_view["passed"].astype(int)
    colors = np.where(gate_view["passed"].eq(1), "#2ca02c", "#d62728")
    ax.barh(gate_view["gate"], np.ones(len(gate_view)), color=colors, alpha=0.88)
    for idx, passed in enumerate(gate_view["passed"]):
        ax.text(0.5, idx, "PASS" if passed else "FAIL", color="white", ha="center", va="center", fontsize=8, fontweight="bold")
    ax.set_xlim(0, 1)
    ax.set_xticks([])
    ax.set_title("Gates: source ledger only")

    fig.tight_layout(rect=[0, 0.02, 1, 0.95])
    fig.savefig(CHART_PATH, dpi=150)
    plt.close(fig)


def _build_report(
    decision: dict[str, Any],
    snapshot: pd.DataFrame,
    route_summary: pd.DataFrame,
    product_summary: pd.DataFrame,
    gates: pd.DataFrame,
    next_actions: pd.DataFrame,
) -> str:
    return f"""# Stage598 黑色族 P1 source ledger bootstrap

- 生成时间：`{decision["generated_at_local"]}`
- 决策：`{decision["decision"]}`
- 阶段性质：只读采集/审计；不做收益回测，不改策略，不生成白名单。
- 调研参考：
{chr(10).join(f"  - {item}" for item in REFERENCE_LINKS)}

## 核心判断

- 本阶段只验证 `j.DCE/i.DCE` 是否能进入 point-in-time forward source 账本。
- 任何 snapshot 都只能作为未来实盘 monitor，`usable_for_history_selector` 必须保持 `0`。
- 即使 basis/inventory/member/warehouse 当前可抓，也不能跳过 `20` 个 received_at 日期、固定 IC/bucket 审计和每品种 `3` 个 TCA 样本。

## Product Summary

{_md_table(product_summary)}

## Route Summary

{_md_table(route_summary)}

## Gates

{_md_table(gates)}

## Next Actions

{_md_table(next_actions)}

## Snapshot Detail

{_md_table(snapshot, [
    "product_vt_symbol",
    "route",
    "status",
    "source_authority",
    "source_function",
    "source_date",
    "source_age_days",
    "matched_product",
    "usable_for_forward_monitor",
    "official_auto_monitor_ready",
    "third_party_forward_ready",
    "usable_for_history_selector",
    "notes",
], max_rows=20)}

## 输出

- snapshot：`{SNAPSHOT_PATH}`
- scoped master ledger：`{SCOPED_MASTER_LEDGER_PATH}`
- route summary：`{ROUTE_SUMMARY_PATH}`
- product summary：`{PRODUCT_SUMMARY_PATH}`
- gates：`{GATES_PATH}`
- next actions：`{NEXT_ACTIONS_PATH}`
- decision：`{DECISION_PATH}`
- chart：`{CHART_PATH}`
"""


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = _build_snapshot()
    master = _append_scoped_master(snapshot)
    route_summary = _route_summary(snapshot)
    product_summary = _product_summary(snapshot, master)
    gates = _build_gates(snapshot, route_summary, product_summary)
    next_actions = _build_next_actions(product_summary, gates)
    decision = _build_decision(snapshot, product_summary, gates, master)
    report = _build_report(decision, snapshot, route_summary, product_summary, gates, next_actions)

    snapshot.to_csv(SNAPSHOT_PATH, index=False, encoding="utf-8-sig")
    route_summary.to_csv(ROUTE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    product_summary.to_csv(PRODUCT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    next_actions.to_csv(NEXT_ACTIONS_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(report, encoding="utf-8")
    _plot(snapshot, route_summary, product_summary, gates)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
