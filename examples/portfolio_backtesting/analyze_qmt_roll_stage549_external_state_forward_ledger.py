from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import multiprocessing as mp
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
LEDGER_DIR = OUTPUT_DIR / "external_state_forward_ledger"

MODEL_TAG = "stage549_external_state_forward_ledger_v1"
OUTPUT_PREFIX = "qmt_roll_stage549_external_state_forward_ledger"
LINE_ID = "futures_trend_drawdown30_preserve_return"

STAGE548_TAG = "stage548_external_source_alternative_probe_v1"
STAGE548_PREFIX = "qmt_roll_stage548_external_source_alternative_probe"
STAGE548_MATRIX_IN = OUTPUT_DIR / f"{STAGE548_PREFIX}_product_source_matrix_{STAGE548_TAG}.csv"

SNAPSHOT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_snapshot_{MODEL_TAG}.csv"
ROUTE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_route_summary_{MODEL_TAG}.csv"
PRODUCT_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_summary_{MODEL_TAG}.csv"
MASTER_LEDGER_PATH = LEDGER_DIR / "external_state_forward_ledger.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

SOURCE_TIMEOUT_SECONDS = 6
LOOKBACK_DAYS = 5
MAX_RECORDS_PER_PROBE = 600
MAX_DICT_ITEM_RECORDS = 300
MEMBER_ATTEMPTS_BY_EXCHANGE = {"SHFE": 4, "INE": 4, "DCE": 1, "CZCE": 2}
WAREHOUSE_ATTEMPTS_BY_EXCHANGE = {"SHFE": 2, "DCE": 1, "CZCE": 1, "GFEX": 1}
MAX_BASIS_AGE_DAYS = 7
MAX_MEMBER_AGE_DAYS = 7
MAX_INVENTORY_AGE_DAYS = 7
MAX_WAREHOUSE_AGE_DAYS = 7

ORACLE6_CODES = {"AL", "AO", "C", "LU", "V", "Y"}
FINANCIAL_EXCHANGES = {"CFFEX"}
INVENTORY_SYMBOL_FALLBACKS = {
    "AO": ["ao", "氧化铝"],
    "AL": ["al", "沪铝"],
    "LU": ["lu", "低硫燃料油"],
    "C": ["c", "玉米"],
    "V": ["v", "PVC"],
    "Y": ["y", "豆油"],
}


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


def _run_id(now_local: datetime) -> str:
    return now_local.strftime("stage549_%Y%m%d_%H%M%S")


def _candidate_dates(now_local: datetime) -> list[str]:
    dates: list[str] = []
    day = pd.Timestamp(now_local.date())
    for offset in range(LOOKBACK_DAYS + 1):
        dates.append((day - pd.Timedelta(days=offset)).strftime("%Y%m%d"))
    return dates


def _run_probe(function_name: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
    def worker(queue: mp.Queue) -> None:
        try:
            import akshare as ak

            result = getattr(ak, function_name)(*args, **kwargs)
            if isinstance(result, pd.DataFrame):
                packed_frame = result.tail(MAX_RECORDS_PER_PROBE).copy() if len(result) > MAX_RECORDS_PER_PROBE else result.copy()
                queue.put(
                    {
                        "status": "ok",
                        "kind": "dataframe",
                        "rows": int(len(result)),
                        "columns": list(packed_frame.columns),
                        "records": packed_frame.to_dict("records"),
                        "records_limited": int(len(result) > MAX_RECORDS_PER_PROBE),
                    }
                )
            elif isinstance(result, dict):
                packed: dict[str, Any] = {}
                for key, item in result.items():
                    if isinstance(item, pd.DataFrame):
                        packed_frame = item.tail(MAX_DICT_ITEM_RECORDS).copy() if len(item) > MAX_DICT_ITEM_RECORDS else item.copy()
                        packed[str(key)] = {
                            "rows": int(len(item)),
                            "columns": list(packed_frame.columns),
                            "records": packed_frame.to_dict("records"),
                            "records_limited": int(len(item) > MAX_DICT_ITEM_RECORDS),
                        }
                    else:
                        packed[str(key)] = {"type": type(item).__name__, "repr": str(item)[:500]}
                queue.put({"status": "ok", "kind": "dict", "keys": list(result.keys()), "items": packed})
            else:
                queue.put({"status": "ok", "kind": type(result).__name__, "repr": str(result)[:500]})
        except Exception as exc:  # pragma: no cover - external source instability
            queue.put({"status": "error", "error_type": type(exc).__name__, "error_message": str(exc)[:500]})

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


def _load_universe() -> pd.DataFrame:
    matrix = pd.read_csv(STAGE548_MATRIX_IN, encoding="utf-8-sig")
    matrix["product_vt_symbol"] = matrix["product_vt_symbol"].astype(str)
    matrix["product_code"] = matrix["product_code"].astype(str).str.upper()
    matrix["exchange"] = matrix["exchange"].astype(str).str.upper()
    matrix["is_oracle6"] = pd.to_numeric(matrix["is_oracle6"], errors="coerce").fillna(0).astype(int)
    matrix["external_state_applicable"] = ~matrix["exchange"].isin(FINANCIAL_EXCHANGES)
    return matrix[matrix["external_state_applicable"].astype(bool)].copy().sort_values("product_vt_symbol")


def _row_base(run_id: str, now_local: datetime, now_utc: datetime, product: pd.Series, route: str) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "received_at_local": now_local.isoformat(timespec="seconds"),
        "received_at_utc": now_utc.isoformat(timespec="seconds"),
        "line_id": LINE_ID,
        "route": route,
        "product_vt_symbol": product["product_vt_symbol"],
        "product_code": product["product_code"],
        "exchange": product["exchange"],
        "product_family": product.get("product_family", ""),
        "is_oracle6": int(product.get("is_oracle6", 0)),
        "source_name": "",
        "source_function": "",
        "request_date": "",
        "source_date": "",
        "source_key": "",
        "status": "missing",
        "error_type": "",
        "error_message": "",
        "source_age_days": np.nan,
        "usable_for_forward_monitor": 0,
        "usable_for_history_selector": 0,
        "data_value_json": "{}",
        "raw_sha256": "",
        "point_in_time_rule": "Only data received_at_local or earlier may be used by future paper/live decisions.",
        "notes": "",
    }


def _latest_success_date(
    probe_func: str,
    dates: list[str],
    *args_prefix: Any,
    max_attempts: int | None = None,
    **kwargs: Any,
) -> tuple[str, dict[str, Any]]:
    trial_dates = dates if max_attempts is None else dates[:max_attempts]
    probe: dict[str, Any] = {"status": "not_attempted", "error_type": "NoAttempt", "error_message": "no date attempted"}
    for day in trial_dates:
        probe = _run_probe(probe_func, day, *args_prefix, **kwargs)
        if probe.get("status") == "ok":
            rows = int(probe.get("rows", 0) or 0)
            keys = len(probe.get("keys", []) or [])
            if rows > 0 or keys > 0:
                return day, probe
    return trial_dates[0] if trial_dates else dates[0], probe


def _collect_basis(universe: pd.DataFrame, run_id: str, now_local: datetime, now_utc: datetime) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    codes = sorted(universe["product_code"].dropna().astype(str).str.upper().unique())
    request_date, probe = _latest_success_date("futures_spot_price", _candidate_dates(now_local), codes)
    records = probe.get("records", []) if probe.get("kind") == "dataframe" else []
    frame = pd.DataFrame(records)
    if not frame.empty:
        frame["symbol"] = frame["symbol"].astype(str).str.upper()
    for _, product in universe.iterrows():
        row = _row_base(run_id, now_local, now_utc, product, "basis")
        row.update({"source_name": "AKShare 生意社基差", "source_function": "futures_spot_price", "request_date": request_date})
        if probe.get("status") != "ok":
            row.update({"status": str(probe.get("status")), "error_type": probe.get("error_type", ""), "error_message": probe.get("error_message", "")})
            rows.append(row)
            continue
        matched = frame[frame["symbol"].eq(str(product["product_code"]).upper())] if not frame.empty else pd.DataFrame()
        if matched.empty:
            row.update({"status": "missing_product", "notes": "source returned no row for product"})
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
                "source_key": str(rec.get("dominant_contract", rec.get("symbol", ""))),
                "status": "ok",
                "source_age_days": float(age),
                "usable_for_forward_monitor": int(age <= MAX_BASIS_AGE_DAYS),
                "usable_for_history_selector": 0,
                "data_value_json": json.dumps(_json_safe(value), ensure_ascii=False, sort_keys=True),
                "raw_sha256": _stable_hash(rec),
                "notes": "history selector disabled unless long point-in-time ledger is accumulated",
            }
        )
        rows.append(row)
    return rows


def _collect_inventory(universe: pd.DataFrame, run_id: str, now_local: datetime, now_utc: datetime) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for _, product in universe.iterrows():
        code = str(product["product_code"]).upper()
        symbols = INVENTORY_SYMBOL_FALLBACKS.get(code, [code.lower()])
        row = _row_base(run_id, now_local, now_utc, product, "inventory")
        row.update({"source_name": "东方财富期货库存", "source_function": "futures_inventory_em"})
        last_probe: dict[str, Any] = {}
        matched_frame = pd.DataFrame()
        symbol_used = ""
        for symbol in symbols:
            probe = _run_probe("futures_inventory_em", symbol)
            last_probe = probe
            if probe.get("status") == "ok" and int(probe.get("rows", 0) or 0) > 0:
                matched_frame = pd.DataFrame(probe.get("records", []))
                symbol_used = str(symbol)
                break
        if matched_frame.empty:
            row.update(
                {
                    "status": str(last_probe.get("status", "missing")),
                    "error_type": last_probe.get("error_type", ""),
                    "error_message": last_probe.get("error_message", "no inventory record"),
                    "source_key": symbol_used,
                }
            )
            rows.append(row)
            continue
        date_col = "日期" if "日期" in matched_frame.columns else matched_frame.columns[0]
        matched_frame["_date"] = pd.to_datetime(matched_frame[date_col], errors="coerce")
        matched_frame = matched_frame[matched_frame["_date"].notna()].sort_values("_date")
        rec = matched_frame.iloc[-1].to_dict()
        source_date = pd.Timestamp(rec["_date"]).strftime("%Y%m%d")
        age = (pd.Timestamp(now_local.date()) - pd.Timestamp(source_date)).days
        inventory_value = rec.get("库存", rec.get("inventory"))
        change_value = rec.get("增减", rec.get("change"))
        value = {
            "inventory": inventory_value,
            "change": change_value,
            "symbol_used": symbol_used,
            "rows": int(len(matched_frame)),
            "min_date": pd.Timestamp(matched_frame["_date"].min()).strftime("%Y-%m-%d"),
            "max_date": pd.Timestamp(matched_frame["_date"].max()).strftime("%Y-%m-%d"),
        }
        row.update(
            {
                "request_date": now_local.strftime("%Y%m%d"),
                "source_date": source_date,
                "source_key": symbol_used,
                "status": "ok",
                "source_age_days": float(age),
                "usable_for_forward_monitor": int(age <= MAX_INVENTORY_AGE_DAYS),
                "usable_for_history_selector": 0,
                "data_value_json": json.dumps(_json_safe(value), ensure_ascii=False, sort_keys=True),
                "raw_sha256": _stable_hash(rec),
                "notes": "inventory history depth currently too short for 2022-2026 selector backtest",
            }
        )
        rows.append(row)
    return rows


def _aggregate_member_items(items: dict[str, Any], code: str) -> tuple[str, dict[str, Any] | None]:
    code_lower = code.lower()
    matched_keys = [key for key in items if str(key).lower().startswith(code_lower)]
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
    if value.get("long_open_interest_sum") is not None and value.get("short_open_interest_sum") is not None:
        value["top_member_net_long_sum"] = float(value["long_open_interest_sum"] - value["short_open_interest_sum"])
    return ",".join(matched_keys[:8]), value


def _collect_members(universe: pd.DataFrame, run_id: str, now_local: datetime, now_utc: datetime) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    dates = _candidate_dates(now_local)
    shfe_like = universe[universe["exchange"].isin(["SHFE", "INE"])]["product_code"].dropna().astype(str).str.upper().unique().tolist()
    dce = universe[universe["exchange"].eq("DCE")]["product_code"].dropna().astype(str).str.upper().unique().tolist()
    czce = universe[universe["exchange"].eq("CZCE")]["product_code"].dropna().astype(str).str.upper().unique().tolist()

    shfe_date, shfe_probe = _latest_success_date(
        "get_shfe_rank_table",
        dates,
        vars_list=sorted(shfe_like),
        max_attempts=MEMBER_ATTEMPTS_BY_EXCHANGE["SHFE"],
    )
    dce_date, dce_probe = _latest_success_date(
        "get_dce_rank_table",
        dates,
        vars_list=sorted(dce),
        max_attempts=MEMBER_ATTEMPTS_BY_EXCHANGE["DCE"],
    )
    dce_alt_date, dce_alt_probe = _latest_success_date(
        "futures_dce_position_rank",
        dates,
        vars_list=sorted(dce),
        max_attempts=MEMBER_ATTEMPTS_BY_EXCHANGE["DCE"],
    )
    czce_date, czce_probe = _latest_success_date(
        "get_rank_table_czce",
        dates,
        max_attempts=MEMBER_ATTEMPTS_BY_EXCHANGE["CZCE"],
    )
    exchange_probe = {
        "SHFE": (shfe_date, shfe_probe),
        "INE": (shfe_date, shfe_probe),
        "DCE": (dce_date if dce_probe.get("status") == "ok" else dce_alt_date, dce_probe if dce_probe.get("status") == "ok" else dce_alt_probe),
        "CZCE": (czce_date, czce_probe),
    }
    for _, product in universe.iterrows():
        row = _row_base(run_id, now_local, now_utc, product, "member_detail")
        exchange = str(product["exchange"]).upper()
        code = str(product["product_code"]).upper()
        request_date, probe = exchange_probe.get(exchange, (dates[0], {"status": "not_applicable"}))
        func_name = {
            "SHFE": "get_shfe_rank_table",
            "INE": "get_shfe_rank_table",
            "DCE": "get_dce_rank_table/futures_dce_position_rank",
            "CZCE": "get_rank_table_czce",
        }.get(exchange, "not_applicable")
        row.update({"source_name": "交易所会员持仓排名明细", "source_function": func_name, "request_date": request_date})
        if probe.get("status") != "ok":
            row.update({"status": str(probe.get("status")), "error_type": probe.get("error_type", ""), "error_message": probe.get("error_message", "")})
            rows.append(row)
            continue
        items = probe.get("items", {}) if probe.get("kind") == "dict" else {}
        source_key, value = _aggregate_member_items(items, code)
        if value is None:
            row.update({"status": "missing_product", "source_key": "", "notes": "exchange source returned no product contract key"})
            rows.append(row)
            continue
        age = (pd.Timestamp(now_local.date()) - pd.Timestamp(request_date)).days
        row.update(
            {
                "source_date": request_date,
                "source_key": source_key,
                "status": "ok",
                "source_age_days": float(age),
                "usable_for_forward_monitor": int(age <= MAX_MEMBER_AGE_DAYS),
                "usable_for_history_selector": 0,
                "data_value_json": json.dumps(_json_safe(value), ensure_ascii=False, sort_keys=True),
                "raw_sha256": _stable_hash(value),
                "notes": "member detail is forward monitor only until continuous received_at ledger exists",
            }
        )
        rows.append(row)
    return rows


def _aggregate_warehouse_item(item: dict[str, Any]) -> dict[str, Any] | None:
    records = item.get("records", []) if isinstance(item, dict) else []
    if not records:
        return None
    frame = pd.DataFrame(records)
    value: dict[str, Any] = {"row_count": int(len(frame))}
    for candidates, output in [
        (["今日仓单量", "仓单数量"], "warehouse_receipt_quantity"),
        (["增减", "当日增减"], "warehouse_receipt_change"),
        (["有效预报"], "valid_forecast"),
    ]:
        for column in candidates:
            if column in frame.columns:
                value[output] = float(pd.to_numeric(frame[column], errors="coerce").fillna(0.0).sum())
                break
    return value


def _collect_warehouse(universe: pd.DataFrame, run_id: str, now_local: datetime, now_utc: datetime) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    dates = _candidate_dates(now_local)
    exchange_specs = {
        "SHFE": "futures_shfe_warehouse_receipt",
        "DCE": "futures_warehouse_receipt_dce",
        "CZCE": "futures_warehouse_receipt_czce",
        "GFEX": "futures_gfex_warehouse_receipt",
    }
    probes: dict[str, tuple[str, dict[str, Any]]] = {}
    for exchange, func in exchange_specs.items():
        probes[exchange] = _latest_success_date(func, dates, max_attempts=WAREHOUSE_ATTEMPTS_BY_EXCHANGE.get(exchange, 1))
    for _, product in universe.iterrows():
        row = _row_base(run_id, now_local, now_utc, product, "warehouse")
        exchange = str(product["exchange"]).upper()
        code = str(product["product_code"]).upper()
        request_date, probe = probes.get(exchange, (dates[0], {"status": "not_applicable"}))
        row.update({"source_name": "交易所仓单日报", "source_function": exchange_specs.get(exchange, "not_applicable"), "request_date": request_date})
        if probe.get("status") != "ok":
            row.update({"status": str(probe.get("status")), "error_type": probe.get("error_type", ""), "error_message": probe.get("error_message", "")})
            rows.append(row)
            continue
        value = None
        source_key = ""
        if probe.get("kind") == "dict":
            items = probe.get("items", {})
            key_map = {str(key).upper(): key for key in items}
            key = key_map.get(code)
            if key is not None:
                source_key = str(key)
                value = _aggregate_warehouse_item(items[key])
        elif probe.get("kind") == "dataframe":
            records = probe.get("records", [])
            if records:
                value = {"row_count": len(records)}
                source_key = exchange
        if value is None:
            row.update({"status": "missing_product", "notes": "warehouse source returned no product key"})
            rows.append(row)
            continue
        age = (pd.Timestamp(now_local.date()) - pd.Timestamp(request_date)).days
        row.update(
            {
                "source_date": request_date,
                "source_key": source_key,
                "status": "ok",
                "source_age_days": float(age),
                "usable_for_forward_monitor": int(age <= MAX_WAREHOUSE_AGE_DAYS),
                "usable_for_history_selector": 0,
                "data_value_json": json.dumps(_json_safe(value), ensure_ascii=False, sort_keys=True),
                "raw_sha256": _stable_hash(value),
                "notes": "warehouse history remains fragmented; forward ledger only",
            }
        )
        rows.append(row)
    return rows


def _build_snapshot() -> tuple[pd.DataFrame, dict[str, Any]]:
    now_local = datetime.now().astimezone()
    now_utc = now_local.astimezone(timezone.utc)
    run_id = _run_id(now_local)
    universe = _load_universe()
    rows: list[dict[str, Any]] = []
    rows.extend(_collect_basis(universe, run_id, now_local, now_utc))
    rows.extend(_collect_inventory(universe, run_id, now_local, now_utc))
    rows.extend(_collect_members(universe, run_id, now_local, now_utc))
    rows.extend(_collect_warehouse(universe, run_id, now_local, now_utc))
    snapshot = pd.DataFrame(rows)
    meta = {
        "run_id": run_id,
        "received_at_local": now_local.isoformat(timespec="seconds"),
        "received_at_utc": now_utc.isoformat(timespec="seconds"),
        "universe_products": int(universe["product_vt_symbol"].nunique()),
    }
    return snapshot, meta


def _summaries(snapshot: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    route_rows: list[dict[str, Any]] = []
    for route, frame in snapshot.groupby("route", sort=True):
        oracle = frame[frame["is_oracle6"].eq(1)]
        route_rows.append(
            {
                "route": route,
                "rows": int(len(frame)),
                "ok_rows": int(frame["status"].eq("ok").sum()),
                "forward_ready_rows": int(pd.to_numeric(frame["usable_for_forward_monitor"], errors="coerce").fillna(0).sum()),
                "history_ready_rows": int(pd.to_numeric(frame["usable_for_history_selector"], errors="coerce").fillna(0).sum()),
                "ok_rate_pct": float(frame["status"].eq("ok").mean() * 100.0) if len(frame) else 0.0,
                "oracle6_rows": int(len(oracle)),
                "oracle6_ok_rows": int(oracle["status"].eq("ok").sum()),
                "oracle6_forward_ready_rows": int(pd.to_numeric(oracle["usable_for_forward_monitor"], errors="coerce").fillna(0).sum()),
            }
        )
    route_summary = pd.DataFrame(route_rows).sort_values("route")

    product = (
        snapshot.groupby(["product_vt_symbol", "product_code", "exchange", "product_family", "is_oracle6"], dropna=False)
        .agg(
            routes=("route", "nunique"),
            ok_routes=("status", lambda item: int((item == "ok").sum())),
            forward_ready_routes=("usable_for_forward_monitor", lambda item: int(pd.to_numeric(item, errors="coerce").fillna(0).sum())),
            history_ready_routes=("usable_for_history_selector", lambda item: int(pd.to_numeric(item, errors="coerce").fillna(0).sum())),
        )
        .reset_index()
        .sort_values(["is_oracle6", "forward_ready_routes", "product_vt_symbol"], ascending=[False, False, True])
    )
    return route_summary, product


def _append_master(snapshot: pd.DataFrame) -> None:
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    if MASTER_LEDGER_PATH.exists() and MASTER_LEDGER_PATH.stat().st_size > 0:
        existing = pd.read_csv(MASTER_LEDGER_PATH, encoding="utf-8-sig")
        combined = pd.concat([existing, snapshot], ignore_index=True, sort=False)
    else:
        combined = snapshot.copy()
    combined.to_csv(MASTER_LEDGER_PATH, index=False, encoding="utf-8-sig")


def _decision(snapshot: pd.DataFrame, route_summary: pd.DataFrame, product_summary: pd.DataFrame, meta: dict[str, Any]) -> dict[str, Any]:
    oracle = product_summary[product_summary["is_oracle6"].eq(1)]
    all_oracle_have_forward = bool((oracle["forward_ready_routes"] >= 1).all()) if not oracle.empty else False
    all_oracle_have_history = bool((oracle["history_ready_routes"] >= 1).all()) if not oracle.empty else False
    if all_oracle_have_forward and not all_oracle_have_history:
        label = "forward_external_ledger_initialized_not_selector_ready"
    elif all_oracle_have_forward and all_oracle_have_history:
        label = "forward_external_ledger_ready_for_predictive_audit"
    else:
        label = "forward_external_ledger_incomplete"
    return {
        "stage": "Stage249",
        "script_stage": "Stage549",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": label,
        "meta": meta,
        "snapshot_rows": int(len(snapshot)),
        "route_summary": route_summary.to_dict(orient="records"),
        "oracle6": oracle.to_dict(orient="records"),
        "master_ledger_path": str(MASTER_LEDGER_PATH),
        "overfit_boundary": "Forward ledger records received_at timestamps and does not use realized returns or tune any selector.",
        "next_step": "Accumulate multiple received_at snapshots before any predictive use; sentiment must follow the same timestamp ledger rule.",
    }


def _make_chart(snapshot: pd.DataFrame, route_summary: pd.DataFrame, product_summary: pd.DataFrame, decision: dict[str, Any]) -> None:
    oracle_snapshot = snapshot[snapshot["is_oracle6"].eq(1)].copy()
    pivot = (
        oracle_snapshot.pivot_table(
            index="product_vt_symbol",
            columns="route",
            values="usable_for_forward_monitor",
            aggfunc="max",
            fill_value=0,
        )
        .reindex(index=sorted(oracle_snapshot["product_vt_symbol"].unique()))
        .reindex(columns=["basis", "inventory", "member_detail", "warehouse"], fill_value=0)
    )

    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    fig.suptitle(f"Stage549 decision: {decision['decision']}", fontsize=13)

    ax = axes[0, 0]
    im = ax.imshow(pivot.to_numpy(dtype=float), aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_title("Oracle6 forward readiness by route")
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index.tolist())
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns.tolist(), rotation=30, ha="right")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    ax = axes[0, 1]
    x = np.arange(len(route_summary))
    ax.bar(x - 0.18, route_summary["ok_rate_pct"], width=0.36, label="ok rate")
    ax.bar(
        x + 0.18,
        route_summary["forward_ready_rows"] / route_summary["rows"].replace(0, np.nan) * 100.0,
        width=0.36,
        label="forward ready",
    )
    ax.set_title("Route collection quality")
    ax.set_ylim(0, 105)
    ax.set_ylabel("%")
    ax.set_xticks(x)
    ax.set_xticklabels(route_summary["route"].tolist(), rotation=30, ha="right")
    ax.legend()
    ax.grid(axis="y", alpha=0.25)

    ax = axes[1, 0]
    dist = product_summary.groupby("forward_ready_routes")["product_vt_symbol"].count().reset_index()
    ax.bar(dist["forward_ready_routes"].astype(str), dist["product_vt_symbol"], color="#2b6cb0")
    ax.set_title("Products by forward-ready route count")
    ax.set_xlabel("ready routes")
    ax.set_ylabel("products")
    ax.grid(axis="y", alpha=0.25)

    ax = axes[1, 1]
    status = snapshot.groupby(["route", "status"]).size().reset_index(name="count")
    routes = route_summary["route"].tolist()
    bottom = np.zeros(len(routes))
    for status_name in sorted(status["status"].unique()):
        values = []
        for route in routes:
            match = status[(status["route"].eq(route)) & (status["status"].eq(status_name))]
            values.append(int(match["count"].iloc[0]) if not match.empty else 0)
        ax.bar(routes, values, bottom=bottom, label=status_name)
        bottom += np.asarray(values)
    ax.set_title("Route status counts")
    ax.set_xticks(np.arange(len(routes)))
    ax.set_xticklabels(routes, rotation=30, ha="right")
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.25)

    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(route_summary: pd.DataFrame, product_summary: pd.DataFrame, decision: dict[str, Any]) -> None:
    oracle = product_summary[product_summary["is_oracle6"].eq(1)].copy()
    lines = [
        "# Stage549 外生状态 Forward Ledger",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- 决策：`{decision['decision']}`。",
        "- 阶段性质：实盘可执行数据账本初始化；不做收益回测，不生成交易候选。",
        "- 关键纪律：任何未来 selector 只能使用 `received_at_local` 之前已经写入账本的数据。",
        "",
        "## Route Summary",
        "",
        _md_table(route_summary),
        "",
        "## Oracle6 Product Summary",
        "",
        _md_table(oracle),
        "",
        "## 判断",
        "",
        "- 已建立带 `received_at_local/received_at_utc`、`source_date`、`source_function`、`raw_sha256` 的 forward 外生状态账本。",
        "- Oracle6 至少都有一个 forward-ready 外生状态，但没有任何历史 selector-ready 路线。",
        "- 当前只能做 paper 监控和积累，不允许拿本账本回填 2022-2026 回测。",
        "- 舆情后续如果接入，必须用同一账本格式记录接收时间、来源链接、摘要 hash 和品种映射。",
        "",
        "## 输出文件",
        "",
        f"- snapshot：`{SNAPSHOT_PATH}`",
        f"- master ledger：`{MASTER_LEDGER_PATH}`",
        f"- route summary：`{ROUTE_SUMMARY_PATH}`",
        f"- product summary：`{PRODUCT_SUMMARY_PATH}`",
        f"- decision：`{DECISION_PATH}`",
        f"- chart：`{CHART_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot, meta = _build_snapshot()
    route_summary, product_summary = _summaries(snapshot)
    decision = _decision(snapshot, route_summary, product_summary, meta)

    snapshot.to_csv(SNAPSHOT_PATH, index=False, encoding="utf-8-sig")
    route_summary.to_csv(ROUTE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    product_summary.to_csv(PRODUCT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    _append_master(snapshot)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(route_summary, product_summary, decision)
    _make_chart(snapshot, route_summary, product_summary, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
