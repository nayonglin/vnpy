from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import inspect
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
os.environ.setdefault("MPLCONFIGDIR", str(OUTPUT_DIR / ".matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


MODEL_TAG = "stage594_p0_external_endpoint_probe_v1"
OUTPUT_PREFIX = "qmt_roll_stage594_p0_external_endpoint_probe"
LINE_ID = "futures_trend_drawdown30_preserve_return"

STAGE593_PREFIX = "qmt_roll_stage593_p0_external_route_source_catalog"
STAGE593_TAG = "stage593_p0_external_route_source_catalog_v1"
STAGE593_CATALOG = OUTPUT_DIR / f"{STAGE593_PREFIX}_source_catalog_{STAGE593_TAG}.csv"
STAGE593_MATRIX = OUTPUT_DIR / f"{STAGE593_PREFIX}_product_route_matrix_{STAGE593_TAG}.csv"

ENDPOINT_MATRIX_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_endpoint_matrix_{MODEL_TAG}.csv"
PRODUCT_READINESS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_readiness_{MODEL_TAG}.csv"
FUNCTION_SIGNATURES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_function_signatures_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
NEXT_ACTIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_next_actions_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

P0_PRODUCTS = ["y.DCE", "c.DCE", "v.DCE", "ao.SHFE", "lu.INE"]
GAP_PRODUCTS = ["v.DCE", "ao.SHFE", "lu.INE"]
MISSING_BASIS_SUBSTITUTE_PRODUCTS = ["ao.SHFE", "lu.INE"]
MISSING_EVENT_PRODUCTS = ["v.DCE", "ao.SHFE", "lu.INE"]

SOURCE_TIMEOUT_SECONDS = 8
LOOKBACK_DAYS = 6
MAX_AGE_DAYS_FORWARD = 5

PRODUCT_NAMES = {
    "Y": "豆油",
    "C": "玉米",
    "V": "PVC",
    "AO": "氧化铝",
    "LU": "低硫燃料油",
}
INVENTORY_SYMBOLS = {
    "Y": ["豆油", "y"],
    "C": ["玉米", "c"],
    "V": ["PVC", "v"],
    "AO": ["氧化铝", "ao"],
    "LU": ["低硫燃料油", "lu"],
}
ROUTE_ORDER = ["basis_3p", "inventory_3p", "warehouse_official", "event_official"]


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _stable_hash(payload: Any) -> str:
    text = json.dumps(_json_safe(payload), ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "无数据。"
    view = frame.copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda item: f"{item:.4f}" if pd.notna(item) else "")
    return view.to_markdown(index=False)


def _run_probe(function_name: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
    def worker(queue: mp.Queue) -> None:
        try:
            import akshare as ak

            result = getattr(ak, function_name)(*args, **kwargs)
            if isinstance(result, pd.DataFrame):
                queue.put(
                    {
                        "status": "ok",
                        "kind": "dataframe",
                        "rows": int(len(result)),
                        "columns": list(result.columns),
                        "records": result.tail(800).to_dict("records"),
                    }
                )
            elif isinstance(result, dict):
                packed: dict[str, Any] = {}
                for key, item in result.items():
                    if isinstance(item, pd.DataFrame):
                        packed[str(key)] = {
                            "rows": int(len(item)),
                            "columns": list(item.columns),
                            "records": item.tail(300).to_dict("records"),
                        }
                    else:
                        packed[str(key)] = {"type": type(item).__name__, "repr": str(item)[:500]}
                queue.put({"status": "ok", "kind": "dict", "keys": list(result.keys()), "items": packed})
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


def _candidate_dates(now_local: datetime) -> list[str]:
    start = pd.Timestamp(now_local.date())
    return [(start - pd.Timedelta(days=offset)).strftime("%Y%m%d") for offset in range(LOOKBACK_DAYS + 1)]


def _latest_ok(function_name: str, dates: list[str], *extra_args: Any) -> tuple[str, dict[str, Any]]:
    last = {"status": "not_attempted", "error_type": "NoAttempt", "error_message": "no candidate date"}
    for day in dates:
        probe = _run_probe(function_name, day, *extra_args)
        last = probe
        if probe.get("status") == "ok":
            if probe.get("kind") == "dataframe" and int(probe.get("rows", 0) or 0) > 0:
                return day, probe
            if probe.get("kind") == "dict" and len(probe.get("keys", []) or []) > 0:
                return day, probe
    return dates[0], last


def _base_row(now_local: datetime, now_utc: datetime, product: pd.Series, route: str) -> dict[str, Any]:
    code = str(product["product_code"]).upper()
    return {
        "run_id": now_local.strftime("stage594_%Y%m%d_%H%M%S"),
        "received_at_local": now_local.isoformat(timespec="seconds"),
        "received_at_utc": now_utc.isoformat(timespec="seconds"),
        "line_id": LINE_ID,
        "product_vt_symbol": product["product_vt_symbol"],
        "product_code": code,
        "exchange": product["exchange"],
        "product_family": product["product_family"],
        "route": route,
        "source_name": "",
        "source_function": "",
        "source_url": "",
        "source_authority": "",
        "request_key": "",
        "source_date": "",
        "source_age_days": np.nan,
        "probe_status": "missing",
        "matched_product": 0,
        "rows_returned": 0,
        "raw_sha256": "",
        "data_value_json": "{}",
        "published_at": "",
        "headline": "",
        "status_detail": "",
        "usable_for_forward_monitor": 0,
        "usable_for_history_selector": 0,
        "official_auto_monitor_ready": 0,
        "third_party_forward_ready": 0,
        "catalog_only": 0,
        "notes": "",
    }


def _load_p0() -> tuple[pd.DataFrame, pd.DataFrame]:
    matrix = pd.read_csv(STAGE593_MATRIX, encoding="utf-8-sig")
    catalog = pd.read_csv(STAGE593_CATALOG, encoding="utf-8-sig")
    p0 = matrix[matrix["product_vt_symbol"].isin(P0_PRODUCTS)].copy()
    p0["product_code"] = p0["product_vt_symbol"].str.split(".").str[0].str.upper()
    p0["exchange"] = p0["product_vt_symbol"].str.split(".").str[1].str.upper()
    return p0.sort_values("product_vt_symbol"), catalog


def _function_signatures() -> pd.DataFrame:
    import akshare as ak

    names = [
        "futures_inventory_em",
        "futures_spot_price",
        "futures_warehouse_receipt_dce",
        "futures_shfe_warehouse_receipt",
        "futures_stock_shfe_js",
        "futures_to_spot_dce",
        "futures_to_spot_shfe",
    ]
    rows: list[dict[str, Any]] = []
    for name in names:
        fn = getattr(ak, name, None)
        if fn is None:
            rows.append({"function_name": name, "available": 0, "signature": "", "doc_head": ""})
            continue
        try:
            signature = str(inspect.signature(fn))
        except Exception as exc:  # pragma: no cover
            signature = f"signature_error:{type(exc).__name__}"
        doc = inspect.getdoc(fn) or ""
        rows.append({"function_name": name, "available": 1, "signature": signature, "doc_head": doc[:500].replace("\n", " | ")})
    return pd.DataFrame(rows)


def _probe_basis(p0: pd.DataFrame, now_local: datetime, now_utc: datetime) -> list[dict[str, Any]]:
    codes = sorted(p0["product_code"].unique().tolist())
    dates = _candidate_dates(now_local)
    request_date, probe = _latest_ok("futures_spot_price", dates, codes)
    frame = pd.DataFrame(probe.get("records", [])) if probe.get("kind") == "dataframe" else pd.DataFrame()
    if not frame.empty and "symbol" in frame.columns:
        frame["symbol"] = frame["symbol"].astype(str).str.upper()
    rows: list[dict[str, Any]] = []
    for _, product in p0.iterrows():
        row = _base_row(now_local, now_utc, product, "basis_3p")
        row.update(
            {
                "source_name": "AKShare futures_spot_price / 生意社基差",
                "source_function": "futures_spot_price",
                "source_url": "https://www.100ppi.com/",
                "source_authority": "third_party",
                "request_key": request_date,
                "probe_status": str(probe.get("status")),
                "status_detail": probe.get("error_message", ""),
            }
        )
        if probe.get("status") != "ok":
            rows.append(row)
            continue
        matched = frame[frame["symbol"].eq(str(product["product_code"]).upper())] if not frame.empty else pd.DataFrame()
        if matched.empty:
            row.update({"probe_status": "missing_product", "rows_returned": int(len(frame)), "status_detail": "source returned no product row"})
            rows.append(row)
            continue
        rec = matched.iloc[-1].to_dict()
        source_date = str(rec.get("date", request_date)).replace("-", "")
        age = (pd.Timestamp(now_local.date()) - pd.Timestamp(source_date)).days
        row.update(
            {
                "source_date": source_date,
                "source_age_days": float(age),
                "probe_status": "ok",
                "matched_product": 1,
                "rows_returned": int(len(matched)),
                "raw_sha256": _stable_hash(rec),
                "data_value_json": json.dumps(_json_safe(rec), ensure_ascii=False, sort_keys=True),
                "usable_for_forward_monitor": int(age <= MAX_AGE_DAYS_FORWARD),
                "third_party_forward_ready": int(age <= MAX_AGE_DAYS_FORWARD),
                "notes": "third-party basis; forward monitor only, never history selector in this stage",
            }
        )
        rows.append(row)
    return rows


def _probe_inventory(p0: pd.DataFrame, now_local: datetime, now_utc: datetime) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for _, product in p0.iterrows():
        code = str(product["product_code"]).upper()
        row = _base_row(now_local, now_utc, product, "inventory_3p")
        row.update(
            {
                "source_name": "AKShare futures_inventory_em / 东方财富库存",
                "source_function": "futures_inventory_em",
                "source_url": "https://data.eastmoney.com/ifdata/kcsj.html",
                "source_authority": "third_party",
            }
        )
        last_probe: dict[str, Any] = {}
        used_symbol = ""
        frame = pd.DataFrame()
        for symbol in INVENTORY_SYMBOLS.get(code, [code.lower()]):
            probe = _run_probe("futures_inventory_em", symbol)
            last_probe = probe
            used_symbol = symbol
            if probe.get("status") == "ok" and int(probe.get("rows", 0) or 0) > 0:
                frame = pd.DataFrame(probe.get("records", []))
                break
        row.update({"request_key": used_symbol, "probe_status": str(last_probe.get("status")), "status_detail": last_probe.get("error_message", "")})
        if frame.empty:
            rows.append(row)
            continue
        date_col = "日期" if "日期" in frame.columns else frame.columns[0]
        frame["_date"] = pd.to_datetime(frame[date_col], errors="coerce")
        frame = frame[frame["_date"].notna()].sort_values("_date")
        if frame.empty:
            row.update({"probe_status": "date_parse_failed"})
            rows.append(row)
            continue
        rec = frame.iloc[-1].to_dict()
        source_date = pd.Timestamp(rec["_date"]).strftime("%Y%m%d")
        age = (pd.Timestamp(now_local.date()) - pd.Timestamp(source_date)).days
        value = {
            "symbol_used": used_symbol,
            "inventory": rec.get("库存"),
            "change": rec.get("增减"),
            "rows": int(len(frame)),
            "min_date": pd.Timestamp(frame["_date"].min()).strftime("%Y-%m-%d"),
            "max_date": pd.Timestamp(frame["_date"].max()).strftime("%Y-%m-%d"),
        }
        row.update(
            {
                "source_date": source_date,
                "source_age_days": float(age),
                "probe_status": "ok",
                "matched_product": 1,
                "rows_returned": int(len(frame)),
                "raw_sha256": _stable_hash(value),
                "data_value_json": json.dumps(_json_safe(value), ensure_ascii=False, sort_keys=True),
                "usable_for_forward_monitor": int(age <= MAX_AGE_DAYS_FORWARD),
                "third_party_forward_ready": int(age <= MAX_AGE_DAYS_FORWARD),
                "notes": "third-party inventory; useful as forward evidence but not an official exchange endpoint",
            }
        )
        rows.append(row)
    return rows


def _match_warehouse_dict(probe: dict[str, Any], code: str) -> tuple[str, dict[str, Any] | None]:
    target_names = {PRODUCT_NAMES.get(code, ""), code.lower(), code.upper()}
    items = probe.get("items", {}) if probe.get("kind") == "dict" else {}
    for key, item in items.items():
        if str(key) not in target_names:
            continue
        records = item.get("records", []) if isinstance(item, dict) else []
        if not records:
            continue
        frame = pd.DataFrame(records)
        value = {"source_key": str(key), "row_count": int(len(frame))}
        for col in ["WRTWGHTS", "今日仓单量", "仓单数量"]:
            if col in frame.columns:
                value["warehouse_receipt_quantity"] = float(pd.to_numeric(frame[col], errors="coerce").fillna(0).sum())
                break
        for col in ["WRTCHANGE", "增减", "当日增减"]:
            if col in frame.columns:
                value["warehouse_receipt_change"] = float(pd.to_numeric(frame[col], errors="coerce").fillna(0).sum())
                break
        return str(key), value
    return "", None


def _probe_warehouse(p0: pd.DataFrame, now_local: datetime, now_utc: datetime) -> list[dict[str, Any]]:
    dates = _candidate_dates(now_local)
    dce_date, dce_probe = _latest_ok("futures_warehouse_receipt_dce", dates)
    shfe_date, shfe_probe = _latest_ok("futures_shfe_warehouse_receipt", dates)
    rows: list[dict[str, Any]] = []
    for _, product in p0.iterrows():
        code = str(product["product_code"]).upper()
        exchange = str(product["exchange"]).upper()
        row = _base_row(now_local, now_utc, product, "warehouse_official")
        if exchange == "DCE":
            function_name = "futures_warehouse_receipt_dce"
            request_date, probe = dce_date, dce_probe
            source_url = "http://www.dce.com.cn/dce/channel/list/187.html"
        elif exchange == "SHFE":
            function_name = "futures_shfe_warehouse_receipt"
            request_date, probe = shfe_date, shfe_probe
            source_url = "https://tsite.shfe.com.cn/statements/dataview.html?paramid=dailystock"
        elif exchange == "INE":
            function_name = "not_available_in_local_akshare"
            request_date, probe = dates[0], {"status": "missing_function", "error_message": "No dedicated INE warehouse/inventory weekly function in local probe set"}
            source_url = "https://www.ine.cn/index.html"
        else:
            function_name = "not_applicable"
            request_date, probe = dates[0], {"status": "not_applicable"}
            source_url = ""
        row.update(
            {
                "source_name": "Exchange warehouse receipt endpoint via AKShare",
                "source_function": function_name,
                "source_url": source_url,
                "source_authority": "official_exchange",
                "request_key": request_date,
                "probe_status": str(probe.get("status")),
                "status_detail": probe.get("error_message", ""),
            }
        )
        if probe.get("status") != "ok":
            rows.append(row)
            continue
        source_key, value = _match_warehouse_dict(probe, code)
        if value is None:
            row.update({"probe_status": "missing_product", "status_detail": f"returned keys do not include {PRODUCT_NAMES.get(code, code)}"})
            rows.append(row)
            continue
        age = (pd.Timestamp(now_local.date()) - pd.Timestamp(request_date)).days
        row.update(
            {
                "source_date": request_date,
                "source_age_days": float(age),
                "probe_status": "ok",
                "matched_product": 1,
                "rows_returned": int(value.get("row_count", 0)),
                "request_key": source_key,
                "raw_sha256": _stable_hash(value),
                "data_value_json": json.dumps(_json_safe(value), ensure_ascii=False, sort_keys=True),
                "usable_for_forward_monitor": int(age <= MAX_AGE_DAYS_FORWARD),
                "official_auto_monitor_ready": int(age <= MAX_AGE_DAYS_FORWARD),
                "notes": "official exchange source via library parser; must still freeze exact endpoint semantics before alpha use",
            }
        )
        rows.append(row)
    return rows


def _probe_weekly_stock(p0: pd.DataFrame, now_local: datetime, now_utc: datetime) -> list[dict[str, Any]]:
    dates = _candidate_dates(now_local)
    request_date, probe = _latest_ok("futures_stock_shfe_js", dates)
    frame = pd.DataFrame(probe.get("records", [])) if probe.get("kind") == "dataframe" else pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for _, product in p0[p0["product_vt_symbol"].isin(["ao.SHFE", "lu.INE"])].iterrows():
        code = str(product["product_code"]).upper()
        row = _base_row(now_local, now_utc, product, "weekly_stock_3p")
        row.update(
            {
                "source_name": "AKShare futures_stock_shfe_js / Jin10 SHFE weekly stock",
                "source_function": "futures_stock_shfe_js",
                "source_url": "https://datacenter.jin10.com/reportType/dc_shfe_weekly_stock",
                "source_authority": "third_party",
                "request_key": request_date,
                "probe_status": str(probe.get("status")),
                "status_detail": probe.get("error_message", ""),
            }
        )
        if probe.get("status") != "ok" or frame.empty:
            row.update({"probe_status": "empty" if probe.get("status") == "ok" else str(probe.get("status"))})
            rows.append(row)
            continue
        text = frame.astype(str).agg(" ".join, axis=1)
        matched = frame[text.str.contains(PRODUCT_NAMES.get(code, code), regex=False, na=False)]
        if matched.empty:
            row.update({"probe_status": "missing_product", "rows_returned": int(len(frame))})
            rows.append(row)
            continue
        rec = matched.iloc[-1].to_dict()
        row.update(
            {
                "source_date": request_date,
                "source_age_days": float((pd.Timestamp(now_local.date()) - pd.Timestamp(request_date)).days),
                "probe_status": "ok",
                "matched_product": 1,
                "rows_returned": int(len(matched)),
                "raw_sha256": _stable_hash(rec),
                "data_value_json": json.dumps(_json_safe(rec), ensure_ascii=False, sort_keys=True),
                "usable_for_forward_monitor": 1,
                "third_party_forward_ready": 1,
            }
        )
        rows.append(row)
    return rows


def _catalog_event_rows(catalog: pd.DataFrame, p0: pd.DataFrame, now_local: datetime, now_utc: datetime) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    events = catalog[catalog["route"].astype(str).str.contains("event", na=False)].copy()
    for _, event in events.iterrows():
        product_symbol = str(event["product_vt_symbol"])
        match = p0[p0["product_vt_symbol"].eq(product_symbol)]
        if match.empty:
            continue
        product = match.iloc[0]
        row = _base_row(now_local, now_utc, product, "event_official")
        row.update(
            {
                "source_name": event.get("source_name", ""),
                "source_function": "catalog_only_no_parser",
                "source_url": event.get("source_url", ""),
                "source_authority": "official_catalog" if int(event.get("official_source", 0) or 0) else "third_party_catalog",
                "probe_status": "catalog_only_not_monitor_wired",
                "catalog_only": 1,
                "usable_for_forward_monitor": 0,
                "usable_for_history_selector": 0,
                "official_auto_monitor_ready": 0,
                "notes": event.get("notes", ""),
            }
        )
        rows.append(row)
    return rows


def _build_outputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    now_local = datetime.now().astimezone()
    now_utc = now_local.astimezone(timezone.utc)
    p0, catalog = _load_p0()
    rows: list[dict[str, Any]] = []
    rows.extend(_probe_basis(p0, now_local, now_utc))
    rows.extend(_probe_inventory(p0, now_local, now_utc))
    rows.extend(_probe_warehouse(p0, now_local, now_utc))
    rows.extend(_probe_weekly_stock(p0, now_local, now_utc))
    rows.extend(_catalog_event_rows(catalog, p0, now_local, now_utc))
    endpoint = pd.DataFrame(rows)
    sigs = _function_signatures()
    product = _product_readiness(endpoint, p0)
    gates = _gates(endpoint, product, sigs)
    next_actions = _next_actions(product, endpoint)
    decision = _decision(endpoint, product, gates, sigs, now_local, now_utc)
    return endpoint, product, sigs, gates, next_actions, decision


def _product_readiness(endpoint: pd.DataFrame, p0: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, product in p0.iterrows():
        symbol = str(product["product_vt_symbol"])
        frame = endpoint[endpoint["product_vt_symbol"].eq(symbol)]
        rows.append(
            {
                "product_vt_symbol": symbol,
                "product_family": product["product_family"],
                "current_two_route_ready": int(product.get("current_two_route_ready", 0) or 0),
                "current_event_ready": int(product.get("current_event_ready", 0) or 0),
                "current_primary_gap": product.get("current_primary_gap", ""),
                "third_party_forward_routes": int(pd.to_numeric(frame["third_party_forward_ready"], errors="coerce").fillna(0).sum()),
                "official_forward_routes": int(pd.to_numeric(frame["official_auto_monitor_ready"], errors="coerce").fillna(0).sum()),
                "catalog_event_rows": int((frame["route"].eq("event_official") & frame["catalog_only"].eq(1)).sum()),
                "event_auto_monitor_ready": int((frame["route"].eq("event_official") & frame["official_auto_monitor_ready"].eq(1)).sum()),
                "any_forward_monitor": int(pd.to_numeric(frame["usable_for_forward_monitor"], errors="coerce").fillna(0).sum() > 0),
                "history_selector_ready_routes": int(pd.to_numeric(frame["usable_for_history_selector"], errors="coerce").fillna(0).sum()),
                "stage294_role": _role_for_product(symbol, frame),
            }
        )
    return pd.DataFrame(rows)


def _role_for_product(symbol: str, frame: pd.DataFrame) -> str:
    official = int(pd.to_numeric(frame["official_auto_monitor_ready"], errors="coerce").fillna(0).sum())
    third_party = int(pd.to_numeric(frame["third_party_forward_ready"], errors="coerce").fillna(0).sum())
    event_ready = int((frame["route"].eq("event_official") & frame["official_auto_monitor_ready"].eq(1)).sum())
    if symbol in MISSING_EVENT_PRODUCTS and event_ready == 0:
        return "forward_data_partial_event_monitor_blocked"
    if symbol in MISSING_BASIS_SUBSTITUTE_PRODUCTS and official == 0:
        return "third_party_only_official_route_blocked"
    if third_party > 0 or official > 0:
        return "forward_monitor_supported_not_selector"
    return "endpoint_blocked"


def _gates(endpoint: pd.DataFrame, product: pd.DataFrame, sigs: pd.DataFrame) -> pd.DataFrame:
    def pass_row(name: str, passed: bool, value: Any, threshold: str, hard: int, note: str) -> dict[str, Any]:
        return {"gate": name, "passed": int(bool(passed)), "value": value, "threshold": threshold, "hard_gate": hard, "notes": note}

    gap = product[product["product_vt_symbol"].isin(GAP_PRODUCTS)]
    missing_basis = product[product["product_vt_symbol"].isin(MISSING_BASIS_SUBSTITUTE_PRODUCTS)]
    missing_event = product[product["product_vt_symbol"].isin(MISSING_EVENT_PRODUCTS)]
    required_funcs = [
        "futures_inventory_em",
        "futures_spot_price",
        "futures_warehouse_receipt_dce",
        "futures_shfe_warehouse_receipt",
        "futures_stock_shfe_js",
    ]
    rows = [
        pass_row("akshare_required_functions_available", bool(sigs[sigs["function_name"].isin(required_funcs)]["available"].min()), int(sigs[sigs["function_name"].isin(required_funcs)]["available"].sum()), f"{len(required_funcs)}/{len(required_funcs)}", 1, "local dependency exposes the needed functions"),
        pass_row("all_p0_have_any_forward_probe", bool((product["any_forward_monitor"] == 1).all()), int(product["any_forward_monitor"].sum()), f"{len(product)}/{len(product)}", 1, "third-party forward data can cover every P0 product"),
        pass_row("gap_products_have_any_forward_probe", bool((gap["any_forward_monitor"] == 1).all()), int(gap["any_forward_monitor"].sum()), f"{len(gap)}/{len(gap)}", 1, "this is necessary but not sufficient because most probes are third-party"),
        pass_row("ao_lu_have_official_substitute_endpoint", bool((missing_basis["official_forward_routes"] >= 1).all()), int((missing_basis["official_forward_routes"] >= 1).sum()), f"{len(missing_basis)}/{len(missing_basis)}", 1, "ao/lu still need official warehouse/inventory/basis endpoint"),
        pass_row("missing_event_products_have_auto_monitor", bool((missing_event["event_auto_monitor_ready"] >= 1).all()), int((missing_event["event_auto_monitor_ready"] >= 1).sum()), f"{len(missing_event)}/{len(missing_event)}", 1, "event catalog exists but no parser/monitor is wired"),
        pass_row("all_forward_rows_have_hash", bool((endpoint[endpoint["usable_for_forward_monitor"].eq(1)]["raw_sha256"].astype(str).str.len() > 0).all()), int((endpoint[endpoint["usable_for_forward_monitor"].eq(1)]["raw_sha256"].astype(str).str.len() > 0).sum()), "all forward rows", 1, "point-in-time ledger hash requirement"),
        pass_row("history_selector_disabled", bool(endpoint["usable_for_history_selector"].eq(0).all()), int(endpoint["usable_for_history_selector"].sum()), "0", 1, "no backfilled selector use is allowed"),
        pass_row("paper_selector_allowed", False, 0, "true only after official/event/forward-depth gates", 1, "not allowed in Stage294"),
        pass_row("trading_whitelist_allowed", False, 0, "true only after paper selector and TCA gates", 1, "not allowed in Stage294"),
    ]
    return pd.DataFrame(rows)


def _next_actions(product: pd.DataFrame, endpoint: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, item in product.iterrows():
        symbol = str(item["product_vt_symbol"])
        if symbol == "v.DCE":
            rows.append({"priority": "P0", "product_vt_symbol": symbol, "action": "freeze_exact_dce_pvc_notice_or_warehouse_url", "reason": "DCE warehouse parser failed and event monitor is catalog-only"})
        elif symbol == "ao.SHFE":
            rows.append({"priority": "P0", "product_vt_symbol": symbol, "action": "wire_official_shfe_ao_daily_warrant_or_inventory_endpoint", "reason": "third-party inventory works, but SHFE warehouse probe did not return AO"})
        elif symbol == "lu.INE":
            rows.append({"priority": "P0", "product_vt_symbol": symbol, "action": "wire_ine_lu_inventory_weekly_or_warrant_endpoint", "reason": "third-party inventory works, but no local official INE endpoint is wired"})
        elif symbol in ["y.DCE", "c.DCE"]:
            rows.append({"priority": "P1", "product_vt_symbol": symbol, "action": "keep_same_family_top1_only", "reason": "route/event already ready; main risk is same-family co-loading"})
    rows.append({"priority": "P0", "product_vt_symbol": "all", "action": "accumulate_20_forward_dates_before_ic_or_bucket_tests", "reason": "current probe is one received_at snapshot, not predictive evidence"})
    return pd.DataFrame(rows)


def _decision(
    endpoint: pd.DataFrame,
    product: pd.DataFrame,
    gates: pd.DataFrame,
    sigs: pd.DataFrame,
    now_local: datetime,
    now_utc: datetime,
) -> dict[str, Any]:
    hard = gates[gates["hard_gate"].eq(1)]
    hard_pass = int(hard["passed"].sum())
    decision = "p0_endpoint_probe_partial_third_party_forward_ready_official_event_blocked"
    if bool((product["official_forward_routes"] >= 1).all()) and bool((product["event_auto_monitor_ready"] >= 1).all()):
        decision = "p0_endpoint_probe_official_forward_ready_not_history_selector"
    return {
        "stage": "Stage294",
        "script_stage": "Stage594",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at_local": now_local.isoformat(timespec="seconds"),
        "generated_at_utc": now_utc.isoformat(timespec="seconds"),
        "decision": decision,
        "promotion_allowed": False,
        "paper_selector_allowed": False,
        "trading_whitelist_allowed": False,
        "endpoint_rows": int(len(endpoint)),
        "p0_products": int(product["product_vt_symbol"].nunique()),
        "hard_gates_passed": hard_pass,
        "hard_gates_total": int(len(hard)),
        "third_party_forward_product_count": int((product["third_party_forward_routes"] >= 1).sum()),
        "official_forward_product_count": int((product["official_forward_routes"] >= 1).sum()),
        "event_auto_monitor_product_count": int((product["event_auto_monitor_ready"] >= 1).sum()),
        "history_selector_ready_routes": int(product["history_selector_ready_routes"].sum()),
        "akshare_functions": sigs.to_dict(orient="records"),
        "overfit_boundary": "Live endpoint probing only; no realized PnL, no product whitelist tuning, no history selector use.",
        "next_step": "Freeze official endpoints for v/ao/lu event/warehouse routes, then accumulate 20 forward dates before predictive tests.",
    }


def _make_chart(endpoint: pd.DataFrame, product: pd.DataFrame, gates: pd.DataFrame, decision: dict[str, Any]) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(17, 11))
    fig.suptitle(f"Stage594 P0 endpoint probe: {decision['decision']}", fontsize=12)

    ax = axes[0, 0]
    pivot = (
        endpoint[endpoint["route"].isin(ROUTE_ORDER)]
        .pivot_table(index="product_vt_symbol", columns="route", values="usable_for_forward_monitor", aggfunc="max", fill_value=0)
        .reindex(index=P0_PRODUCTS)
        .reindex(columns=ROUTE_ORDER, fill_value=0)
    )
    catalog = (
        endpoint[endpoint["route"].isin(ROUTE_ORDER)]
        .pivot_table(index="product_vt_symbol", columns="route", values="catalog_only", aggfunc="max", fill_value=0)
        .reindex(index=P0_PRODUCTS)
        .reindex(columns=ROUTE_ORDER, fill_value=0)
    )
    heat = pivot.to_numpy(dtype=float) + 0.45 * catalog.to_numpy(dtype=float)
    ax.imshow(heat, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_title("Forward-ready heatmap (1=ready, 0.45=catalog)")
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index.tolist())
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns.tolist(), rotation=30, ha="right")
    for i in range(heat.shape[0]):
        for j in range(heat.shape[1]):
            label = "F" if pivot.iloc[i, j] >= 1 else ("C" if catalog.iloc[i, j] >= 1 else "-")
            ax.text(j, i, label, ha="center", va="center", fontsize=9, color="black")

    ax = axes[0, 1]
    x = np.arange(len(product))
    ax.bar(x - 0.25, product["third_party_forward_routes"], width=0.25, label="third-party forward")
    ax.bar(x, product["official_forward_routes"], width=0.25, label="official forward")
    ax.bar(x + 0.25, product["event_auto_monitor_ready"], width=0.25, label="event monitor")
    ax.set_title("Product readiness layers")
    ax.set_xticks(x)
    ax.set_xticklabels(product["product_vt_symbol"].tolist(), rotation=20, ha="right")
    ax.set_ylabel("ready routes")
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.25)

    ax = axes[1, 0]
    status = endpoint.groupby(["route", "probe_status"]).size().reset_index(name="count")
    routes = endpoint["route"].drop_duplicates().tolist()
    bottom = np.zeros(len(routes))
    for status_name in sorted(status["probe_status"].unique()):
        values = []
        for route in routes:
            match = status[(status["route"].eq(route)) & (status["probe_status"].eq(status_name))]
            values.append(int(match["count"].iloc[0]) if not match.empty else 0)
        ax.bar(routes, values, bottom=bottom, label=status_name)
        bottom += np.asarray(values)
    ax.set_title("Endpoint probe status by route")
    ax.set_xticks(np.arange(len(routes)))
    ax.set_xticklabels(routes, rotation=30, ha="right")
    ax.legend(fontsize=7)
    ax.grid(axis="y", alpha=0.25)

    ax = axes[1, 1]
    hard = gates[gates["hard_gate"].eq(1)].copy()
    short_labels = {
        "akshare_required_functions_available": "functions",
        "all_p0_have_any_forward_probe": "P0 any\nforward",
        "gap_products_have_any_forward_probe": "gap any\nforward",
        "ao_lu_have_official_substitute_endpoint": "AO/LU\nofficial",
        "missing_event_products_have_auto_monitor": "event\nmonitor",
        "all_forward_rows_have_hash": "hashes",
        "history_selector_disabled": "history\nzero",
        "paper_selector_allowed": "paper\nallowed",
        "trading_whitelist_allowed": "trading\nallowed",
    }
    hard["label"] = hard["gate"].map(short_labels).fillna(hard["gate"])
    colors = np.where(hard["passed"].eq(1), "#2f855a", "#c53030")
    y = np.arange(len(hard))
    ax.barh(y, hard["passed"], color=colors)
    ax.set_yticks(y)
    ax.set_yticklabels(hard["label"].tolist(), fontsize=8)
    ax.set_xlim(0, 1)
    ax.set_title("Hard gates")
    ax.set_xlabel("pass")
    ax.grid(axis="x", alpha=0.25)

    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(
    endpoint: pd.DataFrame,
    product: pd.DataFrame,
    sigs: pd.DataFrame,
    gates: pd.DataFrame,
    next_actions: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    hard = gates[gates["hard_gate"].eq(1)]
    lines = [
        "# Stage594 P0 外生 endpoint probe 审计",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- 决策：`{decision['decision']}`",
        "- 阶段性质：联网探测 P0 外生源可执行性；不做收益回测，不新增交易候选。",
        "- 关键纪律：所有 `usable_for_history_selector` 保持 `0`；第三方源只能作为 forward monitor 辅助证据。",
        "",
        "## Product Readiness",
        "",
        _md_table(product),
        "",
        "## Hard Gates",
        "",
        _md_table(hard),
        "",
        "## Function Signatures",
        "",
        _md_table(sigs),
        "",
        "## Endpoint Matrix",
        "",
        _md_table(
            endpoint[
                [
                    "product_vt_symbol",
                    "route",
                    "source_authority",
                    "source_function",
                    "request_key",
                    "source_date",
                    "source_age_days",
                    "probe_status",
                    "matched_product",
                    "usable_for_forward_monitor",
                    "official_auto_monitor_ready",
                    "third_party_forward_ready",
                    "status_detail",
                ]
            ],
            max_rows=80,
        ),
        "",
        "## Next Actions",
        "",
        _md_table(next_actions),
        "",
        "## 判断",
        "",
        "- `v/ao/lu` 的第三方库存 forward probe 可用，但这不是官方 endpoint，因此只能算监控辅助，不算选品 alpha 闭环。",
        "- `ao/lu` 官方仓单/库存替代路线未闭合：当前本地函数没有返回可匹配 AO/LU 的最新官方数据。",
        "- `v/ao/lu` 事件源仍是 catalog-only，没有 parser、published_at 和 raw hash，不能算 event_ready。",
        "- 本阶段没有改变 Stage526/Stage079/78-1 的任何交易逻辑。",
        "",
        "## 输出文件",
        "",
        f"- endpoint matrix：`{ENDPOINT_MATRIX_PATH}`",
        f"- product readiness：`{PRODUCT_READINESS_PATH}`",
        f"- function signatures：`{FUNCTION_SIGNATURES_PATH}`",
        f"- gates：`{GATES_PATH}`",
        f"- next actions：`{NEXT_ACTIONS_PATH}`",
        f"- decision：`{DECISION_PATH}`",
        f"- chart：`{CHART_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    endpoint, product, sigs, gates, next_actions, decision = _build_outputs()
    endpoint.to_csv(ENDPOINT_MATRIX_PATH, index=False, encoding="utf-8-sig")
    product.to_csv(PRODUCT_READINESS_PATH, index=False, encoding="utf-8-sig")
    sigs.to_csv(FUNCTION_SIGNATURES_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    next_actions.to_csv(NEXT_ACTIONS_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(endpoint, product, sigs, gates, next_actions, decision)
    _make_chart(endpoint, product, gates, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
