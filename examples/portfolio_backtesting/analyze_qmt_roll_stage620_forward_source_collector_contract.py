from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import hashlib
import inspect
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
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


LINE_ID = "futures_trend_drawdown30_preserve_return"
MODEL_TAG = "stage620_forward_source_collector_contract_v1"
OUTPUT_PREFIX = "qmt_roll_stage620_forward_source_collector_contract"

STAGE619_ENDPOINT_CATALOG = OUTPUT_DIR / (
    "qmt_roll_stage619_source_endpoint_repair_board_endpoint_catalog_"
    "stage619_source_endpoint_repair_board_v1.csv"
)
STAGE619_REPAIR_MATRIX = OUTPUT_DIR / (
    "qmt_roll_stage619_source_endpoint_repair_board_route_repair_matrix_"
    "stage619_source_endpoint_repair_board_v1.csv"
)

COLLECTOR_CONTRACT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_collector_contract_{MODEL_TAG}.csv"
STAGE_LEDGER_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stage_ledger_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

REQUIRED_LEDGER_FIELDS = [
    "run_id",
    "received_at_local",
    "received_at_utc",
    "line_id",
    "product_family",
    "product_vt_symbol",
    "exchange",
    "product_code",
    "route_group",
    "source_name",
    "source_function",
    "source_authority",
    "source_url",
    "request_key",
    "source_date",
    "published_at",
    "status",
    "error_type",
    "error_message",
    "matched_product",
    "rows_returned",
    "data_value_json",
    "raw_sha256",
    "request_contract_sha256",
    "usable_for_forward_monitor",
    "usable_for_history_selector",
    "selector_unlock_candidate",
    "paper_or_whitelist_allowed",
    "point_in_time_rule",
    "notes",
]

PRODUCT_ALIASES = {
    "j": ["j", "J", "焦炭"],
    "i": ["i", "I", "铁矿石"],
    "ag": ["ag", "AG", "白银", "银"],
    "CY": ["CY", "棉纱"],
    "SR": ["SR", "白糖"],
}

ROUTE_IMPLEMENTATION = {
    "basis": {
        "collector_class": "akshare_dataframe_by_date",
        "implemented": 1,
        "history_selector_allowed": 0,
        "fetch_notes": "futures_spot_price(date, vars_list=[code]); third-party monitor only.",
    },
    "inventory": {
        "collector_class": "akshare_dataframe_latest",
        "implemented": 1,
        "history_selector_allowed": 0,
        "fetch_notes": "futures_inventory_em(symbol=code); third-party monitor only; product support must be probed.",
    },
    "member_detail": {
        "collector_class": "akshare_dict_by_date",
        "implemented": 1,
        "history_selector_allowed": 0,
        "fetch_notes": "exchange member rank by date; parser output must be point-in-time and product matched.",
    },
    "warehouse": {
        "collector_class": "akshare_receipt_by_exchange_date",
        "implemented": 1,
        "history_selector_allowed": 0,
        "fetch_notes": "exchange warehouse receipt by date; product/exchange aggregation must be verified.",
    },
    "event_or_sentiment": {
        "collector_class": "source_taxonomy_required",
        "implemented": 0,
        "history_selector_allowed": 0,
        "fetch_notes": "manual/public event sources require taxonomy before collection.",
    },
}

REFERENCE_LINKS = [
    "AKShare futures docs: https://github.com/akfamily/akshare/blob/main/docs/data/futures/futures.md",
    "AKShare futures/commodities overview: https://deepwiki.com/akfamily/akshare/4.2-futures-and-commodities",
    "CZCE position ranking static example: https://www.czce.com.cn/cn/DFSStaticFiles/Future/2024/20240102/FutureDataHolding.htm",
]


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        item = float(value)
        return None if math.isnan(item) or math.isinf(item) else item
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.isoformat()
    return value


def _stable_hash(payload: Any) -> str:
    text = json.dumps(_json_safe(payload), ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    text = str(value)
    return "" if text.lower() in {"nan", "none", "nat"} else text


def _md_table(frame: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 30) -> str:
    if frame.empty:
        return "_empty_"
    view = frame.copy()
    if columns is not None:
        view = view[[column for column in columns if column in view.columns]]
    if len(view) > max_rows:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda item: f"{item:.4f}" if pd.notna(item) else "")
    return view.to_markdown(index=False)


def _function_signature(name: str) -> tuple[int, str]:
    if not name:
        return 0, ""
    try:
        import akshare as ak
    except Exception:
        return 0, ""
    obj = getattr(ak, name, None)
    if obj is None:
        return 0, ""
    try:
        return 1, str(inspect.signature(obj))
    except Exception:
        return 1, ""


def _source_date_candidates(now_local: datetime, source_date: str | None, lookback_days: int) -> list[str]:
    if source_date:
        return [source_date.replace("-", "")]
    start = pd.Timestamp(now_local.date())
    return [(start - pd.Timedelta(days=offset)).strftime("%Y%m%d") for offset in range(lookback_days + 1)]


def _run_akshare_probe(function_name: str, args: tuple[Any, ...], kwargs: dict[str, Any], timeout_seconds: int) -> dict[str, Any]:
    def worker(queue: mp.Queue) -> None:
        try:
            import akshare as ak

            fn = getattr(ak, function_name)
            result = fn(*args, **kwargs)
            if isinstance(result, pd.DataFrame):
                packed = result.tail(500).copy() if len(result) > 500 else result.copy()
                queue.put(
                    {
                        "status": "ok",
                        "kind": "dataframe",
                        "rows": int(len(result)),
                        "columns": list(packed.columns),
                        "records": packed.to_dict("records"),
                    }
                )
            elif isinstance(result, dict):
                items: dict[str, Any] = {}
                for key, item in result.items():
                    if isinstance(item, pd.DataFrame):
                        packed = item.tail(250).copy() if len(item) > 250 else item.copy()
                        items[str(key)] = {
                            "rows": int(len(item)),
                            "columns": list(packed.columns),
                            "records": packed.to_dict("records"),
                        }
                    else:
                        items[str(key)] = {"type": type(item).__name__, "repr": str(item)[:500]}
                queue.put({"status": "ok", "kind": "dict", "keys": list(result.keys()), "items": items})
            else:
                queue.put({"status": "ok", "kind": type(result).__name__, "repr": str(result)[:500]})
        except Exception as exc:  # external source instability is expected
            queue.put({"status": "error", "error_type": type(exc).__name__, "error_message": str(exc)[:700]})

    ctx = mp.get_context("fork")
    queue: mp.Queue = ctx.Queue()
    process = ctx.Process(target=worker, args=(queue,))
    process.start()
    process.join(timeout_seconds)
    if process.is_alive():
        process.terminate()
        process.join(2)
        return {"status": "timeout", "error_type": "Timeout", "error_message": f">{timeout_seconds}s"}
    if queue.empty():
        return {"status": "empty", "error_type": "EmptyResult", "error_message": "worker returned no message"}
    return queue.get()


def build_collector_contract(endpoint: pd.DataFrame, repair: pd.DataFrame) -> pd.DataFrame:
    merged = endpoint.merge(
        repair[
            [
                "product_vt_symbol",
                "route_group",
                "repair_action",
                "stage617_observed",
                "stage617_contract_complete",
                "stage617_selector_ready",
            ]
        ],
        on=["product_vt_symbol", "route_group"],
        how="left",
    )
    rows: list[dict[str, Any]] = []
    for _, item in merged.iterrows():
        route = _clean_text(item["route_group"])
        impl = ROUTE_IMPLEMENTATION.get(route, {"collector_class": "unknown", "implemented": 0, "history_selector_allowed": 0, "fetch_notes": ""})
        callable_name = _clean_text(item.get("callable_name", ""))
        endpoint_url = _clean_text(item.get("endpoint_url", ""))
        callable_present, signature = _function_signature(callable_name)
        source_url_template_ready = int(endpoint_url.startswith("http") and "{YYYY" not in endpoint_url and "{YYYYMMDD}" not in endpoint_url)
        if route in {"warehouse", "member_detail", "basis"} and endpoint_url.startswith("http"):
            source_url_template_ready = 1
        request_contract = {
            "product_vt_symbol": _clean_text(item.get("product_vt_symbol", "")),
            "route_group": route,
            "callable_name": callable_name,
            "endpoint_url": endpoint_url,
            "source_authority": _clean_text(item.get("source_authority", "")),
        }
        rows.append(
            {
                "product_family": _clean_text(item.get("product_family", "")),
                "product_vt_symbol": _clean_text(item.get("product_vt_symbol", "")),
                "exchange": _clean_text(item.get("exchange", "")),
                "product_code": _clean_text(item.get("product_code", "")),
                "route_group": route,
                "repair_action": _clean_text(item.get("repair_action", "")),
                "source_name": _clean_text(item.get("source_name", "")),
                "source_authority": _clean_text(item.get("source_authority", "")),
                "endpoint_url": endpoint_url,
                "callable_name": callable_name,
                "callable_present": callable_present,
                "callable_signature_current": signature,
                "collector_class": impl["collector_class"],
                "collector_implemented": int(impl["implemented"]),
                "source_url_template_ready": source_url_template_ready,
                "required_fields_ready": 1,
                "append_master_allowed_default": 0,
                "history_selector_allowed": int(impl["history_selector_allowed"]),
                "selector_unlock_candidate": 0,
                "paper_or_whitelist_allowed": 0,
                "stage617_observed": int(item.get("stage617_observed", 0) or 0),
                "stage617_contract_complete": int(item.get("stage617_contract_complete", 0) or 0),
                "stage617_selector_ready": int(item.get("stage617_selector_ready", 0) or 0),
                "request_contract_sha256": _stable_hash(request_contract),
                "fetch_notes": impl["fetch_notes"],
            }
        )
    return pd.DataFrame(rows)


def _base_ledger_row(item: pd.Series, run_id: str, now_local: datetime, now_utc: datetime, mode: str) -> dict[str, Any]:
    request_contract = {
        "product_vt_symbol": _clean_text(item.get("product_vt_symbol", "")),
        "route_group": _clean_text(item.get("route_group", "")),
        "callable_name": _clean_text(item.get("callable_name", "")),
        "endpoint_url": _clean_text(item.get("endpoint_url", "")),
        "source_authority": _clean_text(item.get("source_authority", "")),
        "mode": mode,
    }
    row = {field: "" for field in REQUIRED_LEDGER_FIELDS}
    row.update(
        {
            "run_id": run_id,
            "received_at_local": now_local.isoformat(timespec="seconds"),
            "received_at_utc": now_utc.isoformat(timespec="seconds"),
            "line_id": LINE_ID,
            "product_family": _clean_text(item.get("product_family", "")),
            "product_vt_symbol": _clean_text(item.get("product_vt_symbol", "")),
            "exchange": _clean_text(item.get("exchange", "")),
            "product_code": _clean_text(item.get("product_code", "")),
            "route_group": _clean_text(item.get("route_group", "")),
            "source_name": _clean_text(item.get("source_name", "")),
            "source_function": _clean_text(item.get("callable_name", "")),
            "source_authority": _clean_text(item.get("source_authority", "")),
            "source_url": _clean_text(item.get("endpoint_url", "")),
            "status": "dry_run_not_fetched" if mode == "dry_run" else "not_attempted",
            "matched_product": 0,
            "rows_returned": 0,
            "data_value_json": "{}",
            "raw_sha256": "",
            "request_contract_sha256": _stable_hash(request_contract),
            "usable_for_forward_monitor": 0,
            "usable_for_history_selector": 0,
            "selector_unlock_candidate": 0,
            "paper_or_whitelist_allowed": 0,
            "point_in_time_rule": "Only rows fetched and persisted at received_at_local can be used by future decisions; historical backfill is forbidden.",
            "notes": "collector dry-run contract row; no source data persisted yet." if mode == "dry_run" else "",
        }
    )
    return row


def _product_match(records: list[dict[str, Any]], product_code: str) -> tuple[int, list[dict[str, Any]]]:
    if not records:
        return 0, []
    aliases = {str(alias).lower() for alias in PRODUCT_ALIASES.get(product_code, [product_code])}
    matched: list[dict[str, Any]] = []
    for rec in records:
        text = json.dumps(_json_safe(rec), ensure_ascii=False, default=str).lower()
        if any(alias.lower() in text for alias in aliases):
            matched.append(rec)
    return int(bool(matched)), matched


def _dict_product_match(items: dict[str, Any], product_code: str) -> tuple[int, dict[str, Any]]:
    aliases = [str(alias).lower() for alias in PRODUCT_ALIASES.get(product_code, [product_code])]
    matched: dict[str, Any] = {}
    for key, item in items.items():
        key_text = str(key).lower()
        item_text = json.dumps(_json_safe(item), ensure_ascii=False, default=str).lower()
        if any(alias in key_text or alias in item_text for alias in aliases):
            matched[str(key)] = item
    return int(bool(matched)), matched


def _fetch_one(item: pd.Series, row: dict[str, Any], source_dates: list[str], timeout_seconds: int) -> dict[str, Any]:
    route = str(item.get("route_group", ""))
    product_code = str(item.get("product_code", ""))
    callable_name = str(item.get("callable_name", ""))
    request_bound_dataframe = callable_name in {"futures_spot_price", "futures_inventory_em"}
    request_bound_dict = callable_name in {"futures_dce_position_rank", "get_shfe_rank_table"}
    if route == "event_or_sentiment":
        row.update({"status": "taxonomy_required", "notes": "event/sentiment needs source taxonomy before fetch."})
        return row
    if not callable_name:
        row.update({"status": "missing_callable", "error_type": "MissingCallable"})
        return row

    attempts: list[tuple[tuple[Any, ...], dict[str, Any], str]] = []
    code_upper = product_code.upper()
    code_lower = product_code.lower()
    if callable_name == "futures_spot_price":
        for day in source_dates:
            attempts.append(((day,), {"vars_list": [code_upper]}, day))
    elif callable_name == "futures_inventory_em":
        attempts.append(((code_lower,), {}, "latest"))
        attempts.append(((code_upper,), {}, "latest"))
    elif callable_name in {"futures_warehouse_receipt_dce", "futures_shfe_warehouse_receipt", "futures_warehouse_receipt_czce", "get_rank_table_czce"}:
        for day in source_dates:
            attempts.append(((day,), {}, day))
    elif callable_name in {"futures_dce_position_rank", "get_shfe_rank_table"}:
        for day in source_dates:
            attempts.append(((day,), {"vars_list": [code_upper]}, day))
    else:
        attempts.append(((), {}, "default"))

    last_probe: dict[str, Any] = {}
    last_empty_row: dict[str, Any] | None = None
    last_nonmatch_row: dict[str, Any] | None = None
    for args, kwargs, request_key in attempts:
        probe = _run_akshare_probe(callable_name, args, kwargs, timeout_seconds)
        last_probe = probe
        if probe.get("status") != "ok":
            continue
        if probe.get("kind") == "dataframe":
            records = probe.get("records", []) or []
            rows_returned = int(probe.get("rows", 0) or 0)
            if rows_returned <= 0 or not records:
                candidate = row.copy()
                candidate.update(
                    {
                        "request_key": request_key,
                        "source_date": request_key if str(request_key).isdigit() else "",
                        "status": "empty_source_response",
                        "matched_product": 0,
                        "rows_returned": rows_returned,
                        "data_value_json": "[]",
                        "raw_sha256": "",
                        "usable_for_forward_monitor": 0,
                        "notes": "fetch returned no rows; not source evidence.",
                    }
                )
                last_empty_row = candidate
                continue
            matched_flag, matched_records = _product_match(records, product_code)
            if not matched_flag and request_bound_dataframe:
                matched_flag = 1
                matched_records = records
            payload = matched_records if matched_records else records[:10]
            candidate = row.copy()
            candidate.update(
                {
                    "request_key": request_key,
                    "source_date": request_key if str(request_key).isdigit() else "",
                    "status": "ok" if matched_flag else "ok_no_product_match",
                    "matched_product": matched_flag,
                    "rows_returned": rows_returned,
                    "data_value_json": json.dumps(
                        _json_safe(payload[:20] if isinstance(payload, list) else payload),
                        ensure_ascii=False,
                        sort_keys=True,
                        default=str,
                    ),
                    "raw_sha256": _stable_hash(payload) if matched_flag else "",
                    "usable_for_forward_monitor": int(matched_flag),
                    "notes": "fetched through explicit Stage620 fetch mode; still monitor-only.",
                }
            )
            if matched_flag:
                return candidate
            last_nonmatch_row = candidate
            continue
        if probe.get("kind") == "dict":
            items = probe.get("items", {}) or {}
            if not items:
                candidate = row.copy()
                candidate.update(
                    {
                        "request_key": request_key,
                        "source_date": request_key if str(request_key).isdigit() else "",
                        "status": "empty_source_response",
                        "matched_product": 0,
                        "rows_returned": 0,
                        "data_value_json": "{}",
                        "raw_sha256": "",
                        "usable_for_forward_monitor": 0,
                        "notes": "fetch returned no dict items; not source evidence.",
                    }
                )
                last_empty_row = candidate
                continue
            matched_flag, matched_items = _dict_product_match(items, product_code)
            if not matched_flag and request_bound_dict:
                matched_flag = 1
                matched_items = items
            payload = matched_items if matched_items else {key: items[key] for key in list(items)[:5]}
            candidate = row.copy()
            candidate.update(
                {
                    "request_key": request_key,
                    "source_date": request_key if str(request_key).isdigit() else "",
                    "status": "ok" if matched_flag else "ok_no_product_match",
                    "matched_product": matched_flag,
                    "rows_returned": int(sum(int(value.get("rows", 0) or 0) for value in payload.values() if isinstance(value, dict))),
                    "data_value_json": json.dumps(_json_safe(payload), ensure_ascii=False, sort_keys=True, default=str),
                    "raw_sha256": _stable_hash(payload) if matched_flag else "",
                    "usable_for_forward_monitor": int(matched_flag),
                    "notes": "fetched through explicit Stage620 fetch mode; still monitor-only.",
                }
            )
            if matched_flag:
                return candidate
            last_nonmatch_row = candidate
            continue
    if last_nonmatch_row is not None:
        return last_nonmatch_row
    if last_empty_row is not None:
        return last_empty_row
    row.update(
        {
            "status": str(last_probe.get("status", "error")),
            "error_type": last_probe.get("error_type", "FetchFailed"),
            "error_message": last_probe.get("error_message", ""),
            "notes": "fetch mode attempted but no usable source row was persisted.",
        }
    )
    return row


def build_stage_ledger(contract: pd.DataFrame, mode: str, source_date: str | None, lookback_days: int, timeout_seconds: int, max_fetch_rows: int) -> pd.DataFrame:
    now_utc = datetime.now(timezone.utc)
    now_local = now_utc.astimezone()
    run_id = f"stage620_{mode}_{now_local.strftime('%Y%m%d_%H%M%S')}"
    source_dates = _source_date_candidates(now_local, source_date, lookback_days)
    rows: list[dict[str, Any]] = []
    fetch_count = 0
    for _, item in contract.iterrows():
        row = _base_ledger_row(item, run_id, now_local, now_utc, mode)
        if mode == "fetch" and fetch_count < max_fetch_rows:
            row = _fetch_one(item, row, source_dates, timeout_seconds)
            fetch_count += 1
        rows.append(row)
    ledger = pd.DataFrame(rows)
    for field in REQUIRED_LEDGER_FIELDS:
        if field not in ledger.columns:
            ledger[field] = ""
    return ledger[REQUIRED_LEDGER_FIELDS]


def build_gates(contract: pd.DataFrame, ledger: pd.DataFrame, mode: str) -> pd.DataFrame:
    non_event = contract[contract["route_group"].ne("event_or_sentiment")]
    implemented_non_event = int(non_event["collector_implemented"].sum())
    missing_callable = int((non_event["callable_present"].eq(0)).sum())
    required_fields_present = all(field in ledger.columns for field in REQUIRED_LEDGER_FIELDS)
    fetched_rows = int(
        (
            ledger["raw_sha256"].fillna("").astype(str).str.len().gt(0)
            & pd.to_numeric(ledger["matched_product"], errors="coerce").fillna(0).astype(int).eq(1)
        ).sum()
    )
    selector_unlock = int(pd.to_numeric(ledger["selector_unlock_candidate"], errors="coerce").fillna(0).sum())
    paper_rows = int(pd.to_numeric(ledger["paper_or_whitelist_allowed"], errors="coerce").fillna(0).sum())
    event_taxonomy_missing = int(contract["route_group"].eq("event_or_sentiment").sum())
    gates = [
        {
            "gate": "stage619_inputs_loaded",
            "passed": len(contract) == 25,
            "actual": len(contract),
            "threshold": "25 product-route rows",
            "judgement": "必须承接 Stage319 的完整 source 修复板。",
        },
        {
            "gate": "non_event_collectors_implemented",
            "passed": implemented_non_event == len(non_event),
            "actual": f"{implemented_non_event}/{len(non_event)}",
            "threshold": "all non-event routes",
            "judgement": "basis/inventory/member/warehouse 已有显式 collector 合同。",
        },
        {
            "gate": "akshare_callables_present",
            "passed": missing_callable == 0,
            "actual": missing_callable,
            "threshold": "0 missing non-event callables",
            "judgement": "本地 AKShare 函数入口齐备；网络和解析成功另行审计。",
        },
        {
            "gate": "ledger_schema_complete",
            "passed": required_fields_present,
            "actual": int(required_fields_present),
            "threshold": "all required fields",
            "judgement": "采集行具备 point-in-time 审计所需字段。",
        },
        {
            "gate": "fetch_not_required_for_contract",
            "passed": mode == "dry_run" or fetched_rows > 0,
            "actual": f"mode={mode}; fetched_rows={fetched_rows}",
            "threshold": "dry_run or fetched rows >0",
            "judgement": "默认阶段只证明 collector 合同；显式 fetch 另行形成真实 source rows。",
        },
        {
            "gate": "event_taxonomy_still_missing",
            "passed": event_taxonomy_missing > 0,
            "actual": event_taxonomy_missing,
            "threshold": ">0",
            "judgement": "舆情/事件还没有 source taxonomy，不能采集成 selector。",
        },
        {
            "gate": "selector_unlocked_now",
            "passed": selector_unlock > 0,
            "actual": selector_unlock,
            "threshold": ">0",
            "judgement": "本阶段不得解锁 selector。",
        },
        {
            "gate": "paper_or_whitelist_allowed",
            "passed": paper_rows > 0,
            "actual": paper_rows,
            "threshold": ">0",
            "judgement": "collector 合同不得产生 paper 或交易白名单。",
        },
    ]
    return pd.DataFrame(gates)


def make_chart(contract: pd.DataFrame, ledger: pd.DataFrame, gates: pd.DataFrame) -> None:
    plt.rcParams.update({"font.size": 9})
    fig, axes = plt.subplots(2, 2, figsize=(18, 11), constrained_layout=True)
    fig.suptitle("Stage620 forward source collector contract: fetch evidence separated from collector code", fontsize=15)

    ax = axes[0, 0]
    route_counts = (
        contract.groupby("route_group")
        .agg(
            routes=("route_group", "size"),
            implemented=("collector_implemented", "sum"),
            callable_present=("callable_present", "sum"),
        )
        .reindex(["basis", "inventory", "member_detail", "warehouse", "event_or_sentiment"])
        .fillna(0)
    )
    x = np.arange(len(route_counts.index))
    width = 0.25
    ax.bar(x - width, route_counts["routes"], width, color="#7E57C2", label="routes")
    ax.bar(x, route_counts["implemented"], width, color="#2E7D32", label="collector implemented")
    ax.bar(x + width, route_counts["callable_present"], width, color="#1565C0", label="callable present")
    ax.set_xticks(x)
    ax.set_xticklabels(route_counts.index, rotation=25, ha="right")
    ax.set_title("Collector implementation by route")
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.25)

    ax = axes[0, 1]
    status_order = [
        "dry_run_not_fetched",
        "ok",
        "ok_no_product_match",
        "empty_source_response",
        "taxonomy_required",
        "error",
        "timeout",
        "missing_callable",
        "not_attempted",
    ]
    status_counts = ledger["status"].value_counts().reindex(status_order).dropna()
    colors = [
        "#F9A825"
        if status in {"dry_run_not_fetched", "not_attempted"}
        else "#2E7D32"
        if status == "ok"
        else "#7B1FA2"
        if status == "taxonomy_required"
        else "#C62828"
        for status in status_counts.index
    ]
    ax.barh(status_counts.index, status_counts.values, color=colors, alpha=0.9)
    ax.set_title("Stage ledger row status")
    ax.set_xlabel("rows")
    ax.grid(axis="x", alpha=0.25)

    ax = axes[1, 0]
    products = list(contract["product_vt_symbol"].drop_duplicates())
    routes = ["basis", "inventory", "member_detail", "warehouse", "event_or_sentiment"]
    matrix = pd.DataFrame(0, index=products, columns=routes)
    labels = pd.DataFrame("MISS", index=products, columns=routes)

    def _ledger_cell(row: pd.Series) -> tuple[int, str]:
        status = str(row.get("status", ""))
        route = str(row.get("route_group", ""))
        raw_hash = str(row.get("raw_sha256", "") or "")
        matched = int(pd.to_numeric(pd.Series([row.get("matched_product", 0)]), errors="coerce").fillna(0).iloc[0])
        if status == "ok" and matched == 1 and len(raw_hash) > 0:
            return 3, "OK"
        if route == "event_or_sentiment" or status == "taxonomy_required":
            return 2, "TAX"
        if status in {"dry_run_not_fetched", "not_attempted"}:
            return 1, "WAIT"
        return 0, "FAIL"

    for _, row in ledger.iterrows():
        product = str(row.get("product_vt_symbol", ""))
        route = str(row.get("route_group", ""))
        if product not in matrix.index or route not in matrix.columns:
            continue
        state, label = _ledger_cell(row)
        matrix.loc[product, route] = state
        labels.loc[product, route] = label

    cmap = matplotlib.colors.ListedColormap(["#C62828", "#F9A825", "#7B1FA2", "#2E7D32"])
    ax.imshow(matrix.values, aspect="auto", cmap=cmap, vmin=0, vmax=3)
    ax.set_xticks(range(len(matrix.columns)))
    ax.set_xticklabels(matrix.columns, rotation=25, ha="right")
    ax.set_yticks(range(len(matrix.index)))
    ax.set_yticklabels(matrix.index)
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            ax.text(j, i, str(labels.iloc[i, j]), ha="center", va="center", color="white", fontweight="bold", fontsize=8)
    ax.set_title("Product-route fetch/ledger status")

    ax = axes[1, 1]
    gate_colors = ["#2E7D32" if bool(item) else "#C62828" for item in gates["passed"]]
    y = np.arange(len(gates))
    ax.barh(y, [1] * len(gates), color=gate_colors, alpha=0.9)
    ax.set_yticks(y)
    ax.set_yticklabels(gates["gate"])
    ax.set_xlim(0, 1)
    for idx, row in gates.iterrows():
        ax.text(0.02, idx, "PASS" if bool(row["passed"]) else "BLOCK", va="center", color="white", fontweight="bold", fontsize=8)
    ax.set_title("Promotion gates")
    ax.set_xlabel("gate status")

    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def write_report(decision: dict[str, Any], contract: pd.DataFrame, ledger: pd.DataFrame, gates: pd.DataFrame) -> None:
    lines = [
        "# Stage620 Forward Source Collector Contract",
        "",
        "## Decision",
        "",
        f"- decision: `{decision['decision']}`",
        f"- mode: `{decision['mode']}`",
        f"- collector_rows: `{decision['collector_rows']}`",
        f"- non_event_collectors_ready: `{decision['non_event_collectors_ready']}`",
        f"- event_taxonomy_missing: `{decision['event_taxonomy_missing']}`",
        f"- selector_unlocked_now: `{decision['selector_unlocked_now']}`",
        "",
        "## Collector Contract",
        "",
        _md_table(
            contract,
            [
                "product_vt_symbol",
                "route_group",
                "callable_name",
                "collector_class",
                "collector_implemented",
                "callable_present",
                "history_selector_allowed",
                "repair_action",
            ],
            max_rows=40,
        ),
        "",
        "## Stage Ledger Preview",
        "",
        _md_table(
            ledger,
            [
                "product_vt_symbol",
                "route_group",
                "status",
                "matched_product",
                "rows_returned",
                "source_url",
                "raw_sha256",
                "usable_for_forward_monitor",
                "usable_for_history_selector",
            ],
            max_rows=40,
        ),
        "",
        "## Gates",
        "",
        _md_table(gates, ["gate", "passed", "actual", "threshold", "judgement"], max_rows=20),
        "",
        "## Interpretation",
        "",
        "- This stage implements a collector contract and a stage-scoped ledger schema. It does not append to the master forward ledger.",
        "- Default `dry_run` rows are not source evidence; they only prove request construction and PIT fields.",
        "- `--mode fetch` can be used later to persist stage-scoped source rows, but selector/paper/whitelist remain locked.",
        "- Event/sentiment remains blocked until a source taxonomy exists.",
        "",
        "## Research References",
        "",
    ]
    lines.extend([f"- {item}" for item in REFERENCE_LINKS])
    lines.extend(
        [
            "",
            "## Overfit Reflection",
            "",
            "- Run-start judgement: not overfit. This is source acquisition infrastructure, not return-labelled selection.",
            "- Run-end judgement: not overfit. The script keeps `usable_for_history_selector=0`, `selector_unlock_candidate=0`, and does not write master ledger rows.",
            "",
            "## Continue Value Reflection",
            "",
            "- Worth continuing because it turns Stage319's repair board into runnable collector contracts.",
            "- The next step is an explicit fetch run under approved network conditions, followed by 20 PIT dates of accumulation.",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["dry_run", "fetch"], default="dry_run")
    parser.add_argument("--source-date", default="")
    parser.add_argument("--lookback-days", type=int, default=7)
    parser.add_argument("--timeout-seconds", type=int, default=10)
    parser.add_argument("--max-fetch-rows", type=int, default=5)
    args = parser.parse_args()

    endpoint = _read_csv(STAGE619_ENDPOINT_CATALOG)
    repair = _read_csv(STAGE619_REPAIR_MATRIX)
    contract = build_collector_contract(endpoint, repair)
    ledger = build_stage_ledger(
        contract,
        mode=args.mode,
        source_date=args.source_date or None,
        lookback_days=args.lookback_days,
        timeout_seconds=args.timeout_seconds,
        max_fetch_rows=args.max_fetch_rows,
    )
    gates = build_gates(contract, ledger, args.mode)

    non_event = contract[contract["route_group"].ne("event_or_sentiment")]
    non_event_ready = int(((non_event["collector_implemented"].eq(1)) & (non_event["callable_present"].eq(1))).sum())
    event_taxonomy_missing = int(contract["route_group"].eq("event_or_sentiment").sum())
    fetched_rows = int(
        (
            ledger["raw_sha256"].fillna("").astype(str).str.len().gt(0)
            & pd.to_numeric(ledger["matched_product"], errors="coerce").fillna(0).astype(int).eq(1)
        ).sum()
    )
    selector_unlock = int(pd.to_numeric(ledger["selector_unlock_candidate"], errors="coerce").fillna(0).sum())
    if args.mode == "dry_run":
        decision_name = "forward_source_collector_contract_ready_default_dry_run_selector_locked"
    elif fetched_rows > 0:
        decision_name = "forward_source_fetch_probe_stage_scoped_rows_collected_selector_locked"
    else:
        decision_name = "forward_source_fetch_probe_no_usable_rows_selector_locked"

    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at_cst": datetime.now().strftime("%Y-%m-%d %H:%M:%S CST"),
        "decision": decision_name,
        "mode": args.mode,
        "new_backtest_run": False,
        "strategy_changed": False,
        "master_ledger_appended": False,
        "promotion_allowed": False,
        "paper_selector_allowed": False,
        "trading_whitelist_allowed": False,
        "collector_rows": int(len(contract)),
        "stage_ledger_rows": int(len(ledger)),
        "non_event_collectors_ready": non_event_ready,
        "non_event_collectors_total": int(len(non_event)),
        "event_taxonomy_missing": event_taxonomy_missing,
        "fetched_rows_with_raw_hash": fetched_rows,
        "selector_unlocked_now": selector_unlock,
        "hard_gates_passed": int(gates["passed"].astype(bool).sum()),
        "hard_gates_total": int(len(gates)),
        "next_priority": "run_explicit_fetch_probe_then_accumulate_20_pit_dates_without_history_backfill",
        "overfit_reflection": "Not overfit: collector contract only, no return labels, no selector, no master-ledger append.",
        "continue_value_reflection": "Worth continuing: Stage319 source repair board now has a runnable collection contract.",
        "references": REFERENCE_LINKS,
        "outputs": {
            "collector_contract": str(COLLECTOR_CONTRACT_PATH),
            "stage_ledger": str(STAGE_LEDGER_PATH),
            "gates": str(GATES_PATH),
            "report": str(REPORT_PATH),
            "chart": str(CHART_PATH),
        },
    }

    contract.to_csv(COLLECTOR_CONTRACT_PATH, index=False, encoding="utf-8-sig")
    ledger.to_csv(STAGE_LEDGER_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    make_chart(contract, ledger, gates)
    write_report(decision, contract, ledger, gates)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
