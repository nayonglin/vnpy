from __future__ import annotations

from datetime import datetime
import json
import math
import multiprocessing as mp
import os
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage548_external_source_alternative_probe_v1"
OUTPUT_PREFIX = "qmt_roll_stage548_external_source_alternative_probe"
LINE_ID = "futures_trend_drawdown30_preserve_return"

STAGE543_TAG = "stage543_ex_ante_product_selector_diagnostic_v1"
STAGE543_PREFIX = "qmt_roll_stage543_ex_ante_product_selector_diagnostic"
STAGE543_SCORED_IN = OUTPUT_DIR / f"{STAGE543_PREFIX}_scored_samples_{STAGE543_TAG}.csv"

STAGE544_TAG = "stage544_family_constrained_selector_diagnostic_v1"
STAGE544_PREFIX = "qmt_roll_stage544_family_constrained_selector_diagnostic"
STAGE544_FAMILY_MAP_IN = OUTPUT_DIR / f"{STAGE544_PREFIX}_family_map_{STAGE544_TAG}.csv"

STAGE547_TAG = "stage547_noncore_basis_monthly_selector_diagnostic_v1"
STAGE547_PREFIX = "qmt_roll_stage547_noncore_basis_monthly_selector_diagnostic"
STAGE547_BASIS_COVERAGE_IN = OUTPUT_DIR / f"{STAGE547_PREFIX}_coverage_{STAGE547_TAG}.csv"

PRODUCT_SOURCE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_source_matrix_{MODEL_TAG}.csv"
ROUTE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_route_summary_{MODEL_TAG}.csv"
PROBE_DETAIL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_probe_detail_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

PROBE_DAY = "20260417"
SOURCE_TIMEOUT_SECONDS = 18
INVENTORY_ASOF_MAX_AGE_DAYS = 7

ORACLE6_CODES = {"AL", "AO", "C", "LU", "V", "Y"}
FINANCIAL_EXCHANGES = {"CFFEX"}
INE_CODES = {"LU", "SC", "NR", "BC", "EC"}

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


def _product_code(vt_symbol: str) -> str:
    return str(vt_symbol).split(".", 1)[0].upper()


def _exchange(vt_symbol: str) -> str:
    parts = str(vt_symbol).split(".", 1)
    return parts[1].upper() if len(parts) == 2 else ""


def _load_products() -> pd.DataFrame:
    samples = pd.read_csv(STAGE543_SCORED_IN, encoding="utf-8-sig")
    samples["product_vt_symbol"] = samples["product_vt_symbol"].astype(str)
    samples["product_code"] = samples["product_vt_symbol"].map(_product_code)
    samples["exchange"] = samples["product_vt_symbol"].map(_exchange)
    samples["is_oracle6"] = pd.to_numeric(samples["is_oracle6"], errors="coerce").fillna(0).astype(int)

    products = (
        samples[["product_vt_symbol", "product_code", "exchange", "is_oracle6"]]
        .drop_duplicates()
        .sort_values("product_vt_symbol")
        .reset_index(drop=True)
    )
    family = pd.read_csv(STAGE544_FAMILY_MAP_IN, encoding="utf-8-sig")
    family["product_vt_symbol"] = family["product_vt_symbol"].astype(str)
    products = products.merge(
        family[["product_vt_symbol", "product_family", "family_note"]],
        on="product_vt_symbol",
        how="left",
    )
    products["product_family"] = products["product_family"].fillna("unknown")
    products["family_note"] = products["family_note"].fillna("未分类")
    products["external_state_applicable"] = ~products["exchange"].isin(FINANCIAL_EXCHANGES)
    return products


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
                        "head": result.head(20).to_dict("records"),
                    }
                )
            elif isinstance(result, dict):
                shapes: dict[str, Any] = {}
                for key, item in result.items():
                    if isinstance(item, pd.DataFrame):
                        shapes[str(key)] = {
                            "rows": int(len(item)),
                            "columns": list(item.columns),
                            "head": item.head(3).to_dict("records"),
                        }
                    else:
                        shapes[str(key)] = {"type": type(item).__name__, "repr": str(item)[:200]}
                queue.put(
                    {
                        "status": "ok",
                        "kind": "dict",
                        "keys": list(result.keys()),
                        "shapes": shapes,
                    }
                )
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


def _probe_inventory(products: pd.DataFrame) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    details: list[dict[str, Any]] = []
    for _, product in products.iterrows():
        code = str(product["product_code"]).upper()
        if not bool(product["external_state_applicable"]):
            rows.append(
                {
                    "product_vt_symbol": product["product_vt_symbol"],
                    "inventory_em_status": "not_applicable",
                    "inventory_em_rows": 0,
                    "inventory_em_min_date": "",
                    "inventory_em_max_date": "",
                    "inventory_em_covers_probe_day": 0,
                    "inventory_em_asof_age_days": np.nan,
                    "inventory_em_symbol_used": "",
                }
            )
            continue

        symbols = INVENTORY_SYMBOL_FALLBACKS.get(code, [code.lower()])
        best: dict[str, Any] | None = None
        symbol_used = ""
        for symbol in symbols:
            probe = _run_probe("futures_inventory_em", symbol)
            details.append(
                {
                    "route": "inventory_em",
                    "product_vt_symbol": product["product_vt_symbol"],
                    "function": "futures_inventory_em",
                    "args": symbol,
                    "status": probe.get("status"),
                    "error_type": probe.get("error_type", ""),
                    "rows": probe.get("rows", 0),
                }
            )
            if probe.get("status") == "ok" and int(probe.get("rows", 0) or 0) > 0:
                best = probe
                symbol_used = str(symbol)
                break
        if best is None:
            rows.append(
                {
                    "product_vt_symbol": product["product_vt_symbol"],
                    "inventory_em_status": "missing_or_error",
                    "inventory_em_rows": 0,
                    "inventory_em_min_date": "",
                    "inventory_em_max_date": "",
                    "inventory_em_covers_probe_day": 0,
                    "inventory_em_asof_age_days": np.nan,
                    "inventory_em_symbol_used": "",
                }
            )
            continue

        frame = pd.DataFrame(best.get("head", []))
        # The probe head is not enough for history depth, fetch again directly in this process after success.
        try:
            import akshare as ak

            full = ak.futures_inventory_em(symbol_used)
        except Exception:
            full = frame
        date_col = "日期" if "日期" in full.columns else full.columns[0]
        dates = pd.to_datetime(full[date_col], errors="coerce").dropna().dt.normalize()
        probe_ts = pd.Timestamp(PROBE_DAY).normalize()
        asof_dates = dates[dates <= probe_ts]
        asof_age = np.nan
        covers_probe = 0
        if not asof_dates.empty:
            latest = asof_dates.max()
            asof_age = float((probe_ts - latest).days)
            covers_probe = int(asof_age <= INVENTORY_ASOF_MAX_AGE_DAYS)
        rows.append(
            {
                "product_vt_symbol": product["product_vt_symbol"],
                "inventory_em_status": "ok",
                "inventory_em_rows": int(len(full)),
                "inventory_em_min_date": dates.min().strftime("%Y-%m-%d") if not dates.empty else "",
                "inventory_em_max_date": dates.max().strftime("%Y-%m-%d") if not dates.empty else "",
                "inventory_em_covers_probe_day": covers_probe,
                "inventory_em_asof_age_days": asof_age,
                "inventory_em_symbol_used": symbol_used,
            }
        )
    return pd.DataFrame(rows), details


def _keys_have_code(keys: list[Any], code: str) -> bool:
    code_lower = code.lower()
    return any(str(key).lower().startswith(code_lower) for key in keys)


def _probe_member(products: pd.DataFrame) -> tuple[pd.DataFrame, list[dict[str, Any]], pd.DataFrame]:
    product_rows = products[products["external_state_applicable"].astype(bool)].copy()
    exchange_calls: list[dict[str, Any]] = []
    details: list[dict[str, Any]] = []

    shfe_codes = sorted(
        product_rows.loc[product_rows["exchange"].isin(["SHFE", "INE"]), "product_code"].astype(str).str.upper().unique()
    )
    dce_codes = sorted(product_rows.loc[product_rows["exchange"].eq("DCE"), "product_code"].astype(str).str.upper().unique())
    czce_codes = sorted(product_rows.loc[product_rows["exchange"].eq("CZCE"), "product_code"].astype(str).str.upper().unique())
    gfex_codes = sorted(product_rows.loc[product_rows["exchange"].eq("GFEX"), "product_code"].astype(str).str.upper().unique())

    call_specs = [
        ("SHFE_OR_INE", "get_shfe_rank_table", {"date": PROBE_DAY, "vars_list": shfe_codes}),
        ("DCE", "get_dce_rank_table", {"date": PROBE_DAY, "vars_list": dce_codes}),
        ("DCE_ALT", "futures_dce_position_rank", {"date": PROBE_DAY, "vars_list": dce_codes}),
        ("CZCE", "get_rank_table_czce", {"date": PROBE_DAY}),
        ("GFEX", "futures_gfex_position_rank", {"date": PROBE_DAY, "vars_list": gfex_codes}),
    ]
    exchange_keys: dict[str, list[Any]] = {}
    for exchange, function_name, kwargs in call_specs:
        if not kwargs.get("vars_list", [1]) and function_name != "get_rank_table_czce":
            probe = {"status": "not_applicable", "keys": [], "error_type": "", "rows": 0}
        else:
            probe = _run_probe(function_name, **kwargs)
        keys = probe.get("keys", []) if probe.get("kind") == "dict" else []
        exchange_keys[exchange] = list(keys)
        exchange_calls.append(
            {
                "route": "member_detail",
                "exchange_group": exchange,
                "function": function_name,
                "status": probe.get("status"),
                "error_type": probe.get("error_type", ""),
                "error_message": probe.get("error_message", ""),
                "key_count": len(keys),
                "row_count": probe.get("rows", 0),
            }
        )
        details.append(exchange_calls[-1])

    call_frame = pd.DataFrame(exchange_calls)
    rows: list[dict[str, Any]] = []
    for _, product in products.iterrows():
        code = str(product["product_code"]).upper()
        exchange = str(product["exchange"]).upper()
        if not bool(product["external_state_applicable"]):
            status = "not_applicable"
            key_count = 0
        elif exchange in {"SHFE", "INE"}:
            status = call_frame.loc[call_frame["exchange_group"].eq("SHFE_OR_INE"), "status"].iloc[0]
            # Re-run key extraction from detail is not possible from compact frame, so use status and source known availability.
            probe = _run_probe("get_shfe_rank_table", date=PROBE_DAY, vars_list=[code])
            keys = probe.get("keys", []) if probe.get("kind") == "dict" else []
            if probe.get("status") == "ok" and _keys_have_code(keys, code):
                status = "ok"
            elif probe.get("status") == "ok":
                status = "no_product_key"
            else:
                status = str(probe.get("status"))
            key_count = len(keys)
            details.append(
                {
                    "route": "member_detail_product_confirm",
                    "product_vt_symbol": product["product_vt_symbol"],
                    "function": "get_shfe_rank_table",
                    "status": probe.get("status"),
                    "error_type": probe.get("error_type", ""),
                    "rows": probe.get("rows", 0),
                    "key_count": len(keys),
                }
            )
        elif exchange == "DCE":
            dce_ok = call_frame.loc[call_frame["exchange_group"].eq("DCE"), "status"].iloc[0] == "ok" and _keys_have_code(
                exchange_keys.get("DCE", []), code
            )
            dce_alt_ok = call_frame.loc[call_frame["exchange_group"].eq("DCE_ALT"), "status"].iloc[0] == "ok" and _keys_have_code(
                exchange_keys.get("DCE_ALT", []), code
            )
            status = "ok" if dce_ok or dce_alt_ok else "error"
            key_count = 0
        elif exchange == "CZCE":
            exchange_status = str(call_frame.loc[call_frame["exchange_group"].eq("CZCE"), "status"].iloc[0])
            if exchange_status == "ok" and _keys_have_code(exchange_keys.get("CZCE", []), code):
                status = "ok"
            elif exchange_status == "ok":
                status = "no_product_key"
            else:
                status = exchange_status
            key_count = int(call_frame.loc[call_frame["exchange_group"].eq("CZCE"), "key_count"].iloc[0])
        elif exchange == "GFEX":
            exchange_status = str(call_frame.loc[call_frame["exchange_group"].eq("GFEX"), "status"].iloc[0])
            if exchange_status == "ok" and _keys_have_code(exchange_keys.get("GFEX", []), code):
                status = "ok"
            elif exchange_status == "ok":
                status = "no_product_key"
            else:
                status = exchange_status
            key_count = int(call_frame.loc[call_frame["exchange_group"].eq("GFEX"), "key_count"].iloc[0])
        else:
            status = "unknown_exchange"
            key_count = 0
        rows.append(
            {
                "product_vt_symbol": product["product_vt_symbol"],
                "member_detail_status": status,
                "member_detail_key_count": int(key_count),
                "member_detail_live_ready": int(status == "ok"),
            }
        )
    return pd.DataFrame(rows), details, call_frame


def _probe_warehouse(products: pd.DataFrame) -> tuple[pd.DataFrame, list[dict[str, Any]], pd.DataFrame]:
    call_specs = [
        ("SHFE", "futures_shfe_warehouse_receipt", (PROBE_DAY,), {}),
        ("DCE", "futures_warehouse_receipt_dce", (PROBE_DAY,), {}),
        ("CZCE", "futures_warehouse_receipt_czce", (PROBE_DAY,), {}),
        ("GFEX", "futures_gfex_warehouse_receipt", (PROBE_DAY,), {}),
        ("AGGREGATE_RECEIPT_ORACLE6", "get_receipt", (), {"start_date": PROBE_DAY, "end_date": PROBE_DAY, "vars_list": sorted(ORACLE6_CODES)}),
    ]
    calls: list[dict[str, Any]] = []
    probes: dict[str, dict[str, Any]] = {}
    for exchange, function_name, args, kwargs in call_specs:
        probe = _run_probe(function_name, *args, **kwargs)
        probes[exchange] = probe
        keys = probe.get("keys", []) if probe.get("kind") == "dict" else []
        calls.append(
            {
                "route": "warehouse_or_receipt",
                "exchange_group": exchange,
                "function": function_name,
                "status": probe.get("status"),
                "error_type": probe.get("error_type", ""),
                "error_message": probe.get("error_message", ""),
                "key_count": len(keys),
                "row_count": probe.get("rows", 0),
            }
        )

    rows: list[dict[str, Any]] = []
    for _, product in products.iterrows():
        code = str(product["product_code"]).upper()
        exchange = str(product["exchange"]).upper()
        if not bool(product["external_state_applicable"]):
            status = "not_applicable"
            found = 0
        elif exchange in {"SHFE", "INE"}:
            status = str(probes["SHFE"].get("status"))
            keys = probes["SHFE"].get("keys", []) if probes["SHFE"].get("kind") == "dict" else []
            found = int(_keys_have_code(keys, code))
        elif exchange == "DCE":
            status = str(probes["DCE"].get("status"))
            found = int(status == "ok")
        elif exchange == "CZCE":
            status = str(probes["CZCE"].get("status"))
            keys = probes["CZCE"].get("keys", []) if probes["CZCE"].get("kind") == "dict" else []
            found = int(code in {str(key).upper() for key in keys})
        elif exchange == "GFEX":
            status = str(probes["GFEX"].get("status"))
            keys = probes["GFEX"].get("keys", []) if probes["GFEX"].get("kind") == "dict" else []
            found = int(code in {str(key).upper() for key in keys})
        else:
            status = "unknown_exchange"
            found = 0
        rows.append(
            {
                "product_vt_symbol": product["product_vt_symbol"],
                "exchange_warehouse_status": status,
                "exchange_warehouse_product_found": found,
                "exchange_warehouse_live_ready": int(status == "ok" and found == 1),
            }
        )
    return pd.DataFrame(rows), calls, pd.DataFrame(calls)


def _basis_coverage(products: pd.DataFrame) -> pd.DataFrame:
    if not STAGE547_BASIS_COVERAGE_IN.exists():
        return pd.DataFrame(
            {
                "product_vt_symbol": products["product_vt_symbol"],
                "basis_coverage_rate_pct": 0.0,
                "basis_months": 0,
                "basis_hist_ready": 0,
            }
        )
    coverage = pd.read_csv(STAGE547_BASIS_COVERAGE_IN, encoding="utf-8-sig")
    coverage["product_vt_symbol"] = coverage["product_vt_symbol"].astype(str)
    result = products[["product_vt_symbol"]].merge(
        coverage[["product_vt_symbol", "basis_coverage_rate_pct", "basis_months"]],
        on="product_vt_symbol",
        how="left",
    )
    result["basis_coverage_rate_pct"] = pd.to_numeric(result["basis_coverage_rate_pct"], errors="coerce").fillna(0.0)
    result["basis_months"] = pd.to_numeric(result["basis_months"], errors="coerce").fillna(0).astype(int)
    result["basis_hist_ready"] = (result["basis_coverage_rate_pct"] >= 80.0).astype(int)
    return result


def _build_matrix() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    products = _load_products()
    basis = _basis_coverage(products)
    inventory, inventory_details = _probe_inventory(products)
    member, member_details, member_call_summary = _probe_member(products)
    warehouse, warehouse_details, warehouse_call_summary = _probe_warehouse(products)

    matrix = products.merge(basis, on="product_vt_symbol", how="left")
    matrix = matrix.merge(inventory, on="product_vt_symbol", how="left")
    matrix = matrix.merge(member, on="product_vt_symbol", how="left")
    matrix = matrix.merge(warehouse, on="product_vt_symbol", how="left")

    matrix["inventory_recent_ready"] = (matrix["inventory_em_status"].eq("ok") & matrix["inventory_em_rows"].gt(0)).astype(int)
    matrix["inventory_backtest_depth_ready"] = (
        pd.to_datetime(matrix["inventory_em_min_date"], errors="coerce") <= pd.Timestamp("2022-01-01")
    ).fillna(False).astype(int)
    matrix["any_live_external_state"] = (
        matrix[["inventory_recent_ready", "member_detail_live_ready", "exchange_warehouse_live_ready"]].fillna(0).sum(axis=1) > 0
    ).astype(int)
    matrix["all_core_external_state_ready"] = (
        matrix[["basis_hist_ready", "inventory_backtest_depth_ready", "member_detail_live_ready"]].fillna(0).sum(axis=1) >= 3
    ).astype(int)

    applicable = matrix[matrix["external_state_applicable"].astype(bool)].copy()
    oracle = matrix[matrix["is_oracle6"].eq(1)].copy()
    route_rows = []
    for label, column in [
        ("basis_hist_ready", "basis_hist_ready"),
        ("inventory_recent_ready", "inventory_recent_ready"),
        ("inventory_probe_day_ready", "inventory_em_covers_probe_day"),
        ("inventory_backtest_depth_ready", "inventory_backtest_depth_ready"),
        ("member_detail_live_ready", "member_detail_live_ready"),
        ("exchange_warehouse_live_ready", "exchange_warehouse_live_ready"),
        ("any_live_external_state", "any_live_external_state"),
        ("all_core_external_state_ready", "all_core_external_state_ready"),
    ]:
        route_rows.append(
            {
                "route": label,
                "applicable_products": int(len(applicable)),
                "applicable_ready_count": int(pd.to_numeric(applicable[column], errors="coerce").fillna(0).sum()),
                "applicable_ready_rate_pct": float(pd.to_numeric(applicable[column], errors="coerce").fillna(0).mean() * 100.0)
                if len(applicable)
                else 0.0,
                "oracle6_products": int(len(oracle)),
                "oracle6_ready_count": int(pd.to_numeric(oracle[column], errors="coerce").fillna(0).sum()),
                "oracle6_ready_rate_pct": float(pd.to_numeric(oracle[column], errors="coerce").fillna(0).mean() * 100.0)
                if len(oracle)
                else 0.0,
            }
        )
    route_summary = pd.DataFrame(route_rows)
    probe_details = pd.DataFrame(inventory_details + member_details + warehouse_details)
    return matrix, route_summary, probe_details


def _make_chart(matrix: pd.DataFrame, route_summary: pd.DataFrame, decision: dict[str, Any]) -> None:
    oracle = matrix[matrix["is_oracle6"].eq(1)].copy().sort_values("product_vt_symbol")
    heat_cols = [
        "basis_hist_ready",
        "inventory_recent_ready",
        "inventory_em_covers_probe_day",
        "inventory_backtest_depth_ready",
        "member_detail_live_ready",
        "exchange_warehouse_live_ready",
        "all_core_external_state_ready",
    ]
    heat = oracle[heat_cols].apply(pd.to_numeric, errors="coerce").fillna(0).to_numpy(dtype=float)

    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    fig.suptitle(f"Stage548 decision: {decision['decision']}", fontsize=13)

    ax = axes[0, 0]
    im = ax.imshow(heat, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_title("Oracle6 external source readiness")
    ax.set_yticks(np.arange(len(oracle)))
    ax.set_yticklabels(oracle["product_vt_symbol"].tolist())
    ax.set_xticks(np.arange(len(heat_cols)))
    ax.set_xticklabels(
        ["basis", "inv recent", "inv asof", "inv 2022+", "member", "warehouse", "all core"],
        rotation=35,
        ha="right",
    )
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    ax = axes[0, 1]
    summary_view = route_summary[route_summary["route"].isin(heat_cols[:-1] + ["any_live_external_state"])].copy()
    x = np.arange(len(summary_view))
    ax.bar(x - 0.18, summary_view["applicable_ready_rate_pct"], width=0.36, label="all applicable")
    ax.bar(x + 0.18, summary_view["oracle6_ready_rate_pct"], width=0.36, label="Oracle6")
    ax.set_title("Ready rate by route")
    ax.set_ylabel("%")
    ax.set_ylim(0, 105)
    ax.set_xticks(x)
    ax.set_xticklabels(summary_view["route"].tolist(), rotation=35, ha="right")
    ax.legend()
    ax.grid(axis="y", alpha=0.25)

    ax = axes[1, 0]
    inv = oracle.sort_values("inventory_em_rows", ascending=True)
    ax.barh(inv["product_vt_symbol"], inv["inventory_em_rows"].fillna(0), color="#2b6cb0")
    ax.set_title("Oracle6 inventory_em history row count")
    ax.set_xlabel("rows")
    for idx, (_, row) in enumerate(inv.iterrows()):
        label = f"{row.get('inventory_em_min_date', '')}..{row.get('inventory_em_max_date', '')}"
        ax.text(float(row.get("inventory_em_rows", 0) or 0) + 1, idx, label, va="center", fontsize=8)

    ax = axes[1, 1]
    member_by_exchange = (
        matrix[matrix["external_state_applicable"].astype(bool)]
        .groupby("exchange")["member_detail_live_ready"]
        .agg(["sum", "count"])
        .reset_index()
        .sort_values("exchange")
    )
    member_by_exchange["rate"] = member_by_exchange["sum"] / member_by_exchange["count"].replace(0, np.nan) * 100.0
    ax.bar(member_by_exchange["exchange"], member_by_exchange["rate"].fillna(0), color="#2f855a")
    ax.set_title("Member-detail live ready by exchange")
    ax.set_ylabel("%")
    ax.set_ylim(0, 105)
    for _, row in member_by_exchange.iterrows():
        ax.text(row["exchange"], row["rate"] + 2, f"{int(row['sum'])}/{int(row['count'])}", ha="center", fontsize=9)
    ax.grid(axis="y", alpha=0.25)

    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _decision(matrix: pd.DataFrame, route_summary: pd.DataFrame) -> dict[str, Any]:
    oracle = matrix[matrix["is_oracle6"].eq(1)].copy()
    all_core_ready = int(oracle["all_core_external_state_ready"].sum())
    inventory_recent = int(oracle["inventory_recent_ready"].sum())
    inventory_backtest = int(oracle["inventory_backtest_depth_ready"].sum())
    member_ready = int(oracle["member_detail_live_ready"].sum())
    warehouse_ready = int(oracle["exchange_warehouse_live_ready"].sum())
    basis_ready = int(oracle["basis_hist_ready"].sum())

    if all_core_ready == len(oracle):
        label = "external_sources_ready_for_selector_build"
    elif inventory_recent == len(oracle) and inventory_backtest == 0:
        label = "alternative_sources_partial_live_ready_not_backtest_ready"
    else:
        label = "alternative_sources_still_fragmented"

    return {
        "stage": "Stage248",
        "script_stage": "Stage548",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "probe_day": PROBE_DAY,
        "decision": label,
        "oracle6": {
            "product_count": int(len(oracle)),
            "basis_hist_ready": basis_ready,
            "inventory_recent_ready": inventory_recent,
            "inventory_probe_day_ready": int(oracle["inventory_em_covers_probe_day"].sum()),
            "inventory_backtest_depth_ready": inventory_backtest,
            "member_detail_live_ready": member_ready,
            "exchange_warehouse_live_ready": warehouse_ready,
            "all_core_external_state_ready": all_core_ready,
        },
        "route_summary": route_summary.to_dict(orient="records"),
        "tushare": {
            "installed": _safe_import_tushare()[0],
            "token_present": bool(os.environ.get("TUSHARE_TOKEN")),
            "smoke_status": _safe_import_tushare()[1],
        },
        "overfit_boundary": (
            "This stage probes source availability and history depth only. It does not use selector returns "
            "to tune data sources, weights, product lists, or thresholds."
        ),
        "next_step": (
            "Do not build a historical selector from inventory_em because its current history depth starts in 2026. "
            "Member detail can be explored for SHFE/INE products only; DCE and exchange warehouse remain blockers."
        ),
    }


def _safe_import_tushare() -> tuple[bool, str]:
    try:
        import tushare as ts  # type: ignore
    except Exception:
        return False, "not_installed"
    token = os.environ.get("TUSHARE_TOKEN")
    if not token:
        return True, "missing_token"
    try:
        pro = ts.pro_api(token)
        sample = pro.fut_basic(exchange="DCE", fields="ts_code,symbol,name,list_date,delist_date")
        return True, f"ok_rows_{len(sample)}"
    except Exception as exc:  # pragma: no cover - depends on external credential
        return True, f"failed_{type(exc).__name__}"


def _write_report(matrix: pd.DataFrame, route_summary: pd.DataFrame, decision: dict[str, Any]) -> None:
    oracle_cols = [
        "product_vt_symbol",
        "product_family",
        "basis_coverage_rate_pct",
        "inventory_em_status",
        "inventory_em_rows",
        "inventory_em_min_date",
        "inventory_em_max_date",
        "inventory_em_covers_probe_day",
        "member_detail_status",
        "exchange_warehouse_status",
        "all_core_external_state_ready",
    ]
    oracle = matrix[matrix["is_oracle6"].eq(1)][oracle_cols].sort_values("product_vt_symbol")
    lines = [
        "# Stage548 外生状态替代源探针",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- 决策：`{decision['decision']}`。",
        "- 阶段性质：数据源可执行性与历史深度审计；不做收益回测，不生成交易候选。",
        "- 核心问题：basis 单因子失败后，库存/仓单/会员明细等替代源能否支撑非核心扩池选品。",
        "",
        "## Route Summary",
        "",
        _md_table(route_summary),
        "",
        "## Oracle6 Source Matrix",
        "",
        _md_table(oracle),
        "",
        "## 判断",
        "",
        "- `futures_inventory_em` 对 Oracle6 当前均能取到近期库存，并覆盖本次探针日附近，但历史深度只有近期样本，不能支撑 2022-2026 的选择器回测。",
        "- `get_shfe_rank_table` 可以绕过 `get_rank_sum_daily` 的汇总 BadZipFile 问题，至少对 SHFE/INE 的 `AL/AO/LU` 有明细会员持仓入口。",
        "- DCE 会员明细与 SHFE/DCE 交易所仓单在本机/当前网络下仍失败或超时，不能作为当前非核心全池 selector 输入。",
        "- 舆情仍没有真实接收时间戳账本，不能进入历史回测。",
        "",
        "## 输出文件",
        "",
        f"- product source matrix：`{PRODUCT_SOURCE_PATH}`",
        f"- route summary：`{ROUTE_SUMMARY_PATH}`",
        f"- probe detail：`{PROBE_DETAIL_PATH}`",
        f"- decision：`{DECISION_PATH}`",
        f"- chart：`{CHART_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    matrix, route_summary, probe_details = _build_matrix()
    decision = _decision(matrix, route_summary)

    matrix.to_csv(PRODUCT_SOURCE_PATH, index=False, encoding="utf-8-sig")
    route_summary.to_csv(ROUTE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    probe_details.to_csv(PROBE_DETAIL_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(matrix, route_summary, decision)
    _make_chart(matrix, route_summary, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
