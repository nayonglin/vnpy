from __future__ import annotations

from datetime import datetime
import inspect
import json
import math
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
MODEL_TAG = "stage619_source_endpoint_repair_board_v1"
OUTPUT_PREFIX = "qmt_roll_stage619_source_endpoint_repair_board"

STAGE617_PRODUCT_MATRIX = OUTPUT_DIR / "qmt_roll_stage617_pit_source_event_ledger_contract_product_route_matrix_stage617_pit_source_event_ledger_contract_v1.csv"
STAGE617_FAMILY = OUTPUT_DIR / "qmt_roll_stage617_pit_source_event_ledger_contract_family_ledger_readiness_stage617_pit_source_event_ledger_contract_v1.csv"
STAGE617_DECISION = OUTPUT_DIR / "qmt_roll_stage617_pit_source_event_ledger_contract_decision_stage617_pit_source_event_ledger_contract_v1.json"
EXTERNAL_STATE_LEDGER = LEDGER_DIR / "external_state_forward_ledger.csv"
BLACK_FERROUS_LEDGER = LEDGER_DIR / "black_ferrous_p1_source_forward_ledger.csv"
SENTIMENT_LEDGER = LEDGER_DIR / "sentiment_news_manual_event_forward_ledger_stage572_real_sentiment_event_ledger_bootstrap_v1.csv"

ENDPOINT_CATALOG_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_endpoint_catalog_{MODEL_TAG}.csv"
REPAIR_MATRIX_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_route_repair_matrix_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

ROUTE_GROUPS = ["basis", "inventory", "member_detail", "warehouse", "event_or_sentiment"]
MONITOR_PRODUCTS = ["j.DCE", "i.DCE", "ag.SHFE", "CY.CZCE", "SR.CZCE"]

REFERENCE_LINKS = [
    "AKShare futures docs / source target URLs: https://github.com/akfamily/akshare/blob/main/docs/data/futures/futures.md",
    "CZCE warehouse receipt daily page: https://www.czce.com.cn/cn/jysj/cdrb/H077003010index_1.htm",
    "CZCE position ranking page: https://www.czce.com.cn/cn/jysj/ccpm/H077003004index_1.htm",
    "SHFE standard warehouse warrant guide: https://www.shfe.com.cn/services/delivery/warehousewarrant1/",
    "DCE position rank endpoint via AKShare docs: http://www.dce.com.cn/dalianshangpin/xqsj/tjsj26/rtj/rcjccpm/index.html",
]


def _read_csv(path: Path, required: bool = True) -> pd.DataFrame:
    if not path.exists():
        if required:
            raise FileNotFoundError(path)
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _num(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return (
        pd.to_numeric(frame[column], errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
        .fillna(default)
        .astype(float)
    )


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
    return value


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


def _route_to_observed_column(route: str) -> str:
    return f"{route}_observed"


def _route_to_ready_column(route: str) -> str:
    return f"{route}_ready"


def _route_to_selector_column(route: str) -> str:
    return f"{route}_selector_ready"


def _product_exchange(product: str) -> str:
    return product.split(".")[-1] if "." in product else ""


def _product_code(product: str) -> str:
    return product.split(".")[0] if "." in product else product


def _product_family(product: str, product_matrix: pd.DataFrame) -> str:
    rows = product_matrix[product_matrix["product_vt_symbol"].eq(product)]
    if rows.empty:
        return ""
    return str(rows.iloc[0].get("product_family", ""))


def _function_signature(name: str) -> tuple[bool, str]:
    try:
        import akshare as ak
    except Exception:
        return False, ""
    obj = getattr(ak, name, None)
    if obj is None:
        return False, ""
    try:
        return True, str(inspect.signature(obj))
    except Exception:
        return True, ""


def build_endpoint_catalog(product_matrix: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    def add(
        route: str,
        products: list[str],
        source_name: str,
        source_authority: str,
        endpoint_url: str,
        callable_name: str,
        repair_type: str,
        selector_eligible_after_collection: int,
        notes: str,
    ) -> None:
        fn_present, signature = _function_signature(callable_name) if callable_name else (False, "")
        for product in products:
            rows.append(
                {
                    "product_family": _product_family(product, product_matrix),
                    "product_vt_symbol": product,
                    "exchange": _product_exchange(product),
                    "product_code": _product_code(product),
                    "route_group": route,
                    "source_name": source_name,
                    "source_authority": source_authority,
                    "endpoint_url": endpoint_url,
                    "callable_name": callable_name,
                    "callable_present": int(fn_present),
                    "callable_signature": signature,
                    "repair_type": repair_type,
                    "selector_eligible_after_collection": int(selector_eligible_after_collection),
                    "notes": notes,
                }
            )

    add(
        "basis",
        MONITOR_PRODUCTS,
        "100ppi spot/basis via AKShare futures_spot_price",
        "third_party_forward",
        "https://www.100ppi.com/sf/day-{YYYY-MM-DD}.html",
        "futures_spot_price",
        "future_rows_add_source_url_authority",
        0,
        "Current external_state ledger basis rows lack source_url; repair only future rows, keep monitor-only.",
    )
    add(
        "inventory",
        MONITOR_PRODUCTS,
        "Eastmoney inventory via AKShare futures_inventory_em",
        "third_party_forward",
        "https://datacenter-web.eastmoney.com/api/data/v1/get",
        "futures_inventory_em",
        "future_rows_add_source_url_authority_and_probe_support",
        0,
        "Third-party inventory can monitor; product support must be proven per product and PIT row.",
    )
    add(
        "warehouse",
        ["ag.SHFE"],
        "SHFE daily warehouse receipt",
        "official_exchange",
        "https://www.shfe.com.cn/data/tradedata/future/dailydata/{YYYYMMDD}dailystock.dat",
        "futures_shfe_warehouse_receipt",
        "build_official_forward_collector",
        0,
        "Official route candidate for ag warehouse receipts; needs forward collection and raw hash.",
    )
    add(
        "warehouse",
        ["CY.CZCE", "SR.CZCE"],
        "CZCE warehouse receipt daily file",
        "official_exchange",
        "http://www.czce.com.cn/cn/DFSStaticFiles/Future/{YYYY}/{YYYYMMDD}/FutureDataWhsheet.xlsx",
        "futures_warehouse_receipt_czce",
        "build_official_forward_collector",
        0,
        "Official route candidate for CZCE warehouse receipts; needs forward collection and raw hash.",
    )
    add(
        "warehouse",
        ["j.DCE", "i.DCE"],
        "DCE warehouse receipt quote endpoint",
        "official_exchange",
        "http://www.dce.com.cn/dcereport/publicweb/dailystat/wbillWeeklyQuotes",
        "futures_warehouse_receipt_dce",
        "build_official_forward_collector",
        0,
        "Official route candidate; actual product availability must be tested forward.",
    )
    add(
        "member_detail",
        ["j.DCE", "i.DCE"],
        "DCE member position rank",
        "official_exchange",
        "http://www.dce.com.cn/dcereport/publicweb/dailystat/memberDealPosi/batchDownload",
        "futures_dce_position_rank",
        "repair_parser_or_fallback_other",
        0,
        "Stage598 saw BadZipFile; parser or endpoint response needs forensic repair before monitor-ready.",
    )
    add(
        "member_detail",
        ["CY.CZCE", "SR.CZCE"],
        "CZCE position ranking static file",
        "official_exchange",
        "http://www.czce.com.cn/cn/DFSStaticFiles/Future/{YYYY}/{YYYYMMDD}/FutureDataHolding.htm",
        "get_rank_table_czce",
        "build_official_forward_collector",
        0,
        "Official route candidate for CZCE position rank; monitor-only until PIT sample depth and selector protocol pass.",
    )
    add(
        "member_detail",
        ["ag.SHFE"],
        "SHFE member rank table",
        "official_exchange",
        "https://tsite.shfe.com.cn/statements/dataview.html?paramid=kx",
        "get_shfe_rank_table",
        "build_official_forward_collector",
        0,
        "Official route candidate; SHFE may be contract-level rather than product total.",
    )
    add(
        "event_or_sentiment",
        ["j.DCE", "i.DCE"],
        "DCE announcements / steel-chain manual event ledger",
        "public_event_discovery",
        "https://www.dce.com.cn/",
        "",
        "manual_event_source_discovery_required",
        0,
        "Needs concrete received_at/source_url/raw_text_hash/product mapping; no selector from manual backfill.",
    )
    add(
        "event_or_sentiment",
        ["ag.SHFE"],
        "SHFE announcements / precious-metals event ledger",
        "public_event_discovery",
        "https://www.shfe.com.cn/",
        "",
        "manual_event_source_discovery_required",
        0,
        "Needs concrete source taxonomy; event interpretation remains monitor-only until forward samples exist.",
    )
    add(
        "event_or_sentiment",
        ["CY.CZCE", "SR.CZCE"],
        "CZCE announcements / cotton-yarn and sugar event ledger",
        "public_event_discovery",
        "https://www.czce.com.cn/",
        "",
        "manual_event_source_discovery_required",
        0,
        "Needs recurring official/public event source and product mapping; no history selector.",
    )
    return pd.DataFrame(rows)


def _ledger_union() -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for path, source in [
        (EXTERNAL_STATE_LEDGER, "external_state"),
        (BLACK_FERROUS_LEDGER, "black_ferrous"),
        (SENTIMENT_LEDGER, "sentiment_event"),
    ]:
        frame = _read_csv(path, required=False)
        if frame.empty:
            continue
        frame = frame.copy()
        frame["ledger_source"] = source
        if "source_url" not in frame.columns:
            frame["source_url"] = ""
        if "source_authority" not in frame.columns:
            frame["source_authority"] = ""
        if "raw_sha256" not in frame.columns and "raw_text_hash" in frame.columns:
            frame["raw_sha256"] = frame["raw_text_hash"]
        if "raw_sha256" not in frame.columns:
            frame["raw_sha256"] = ""
        frames.append(frame)
    if not frames:
        return pd.DataFrame()
    ledger = pd.concat(frames, ignore_index=True, sort=False)
    for column in ["product_vt_symbol", "route", "status", "source_url", "source_authority", "received_at_local", "raw_sha256"]:
        if column not in ledger.columns:
            ledger[column] = ""
        ledger[column] = ledger[column].fillna("").astype(str)
    ledger["usable_for_forward_monitor"] = _num(ledger, "usable_for_forward_monitor")
    ledger["usable_for_history_selector"] = _num(ledger, "usable_for_history_selector")
    return ledger


def build_repair_matrix(product_matrix: pd.DataFrame, endpoint_catalog: pd.DataFrame, ledger: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    product_by = {str(row["product_vt_symbol"]): row for _, row in product_matrix.iterrows()}
    for product in MONITOR_PRODUCTS:
        pm_row = product_by.get(product)
        if pm_row is None:
            continue
        for route in ROUTE_GROUPS:
            observed_col = _route_to_observed_column(route)
            ready_col = _route_to_ready_column(route)
            selector_col = _route_to_selector_column(route)
            observed = int(pm_row.get(observed_col, 0) or 0) if observed_col in pm_row.index else 0
            ready = int(pm_row.get(ready_col, 0) or 0) if ready_col in pm_row.index else 0
            selector_ready = int(pm_row.get(selector_col, 0) or 0) if selector_col in pm_row.index else 0
            product_route_ledger = ledger[
                ledger["product_vt_symbol"].eq(product) & ledger["route"].astype(str).str.contains(route.replace("_detail", ""), case=False, regex=False)
            ].copy() if not ledger.empty else pd.DataFrame()
            if route == "event_or_sentiment":
                product_route_ledger = ledger[
                    ledger["product_vt_symbol"].eq(product)
                    & ledger["route"].astype(str).str.contains("event|sentiment|manual|news", case=False, regex=True)
                ].copy() if not ledger.empty else pd.DataFrame()

            ok_rows = product_route_ledger[product_route_ledger["status"].str.lower().eq("ok")] if not product_route_ledger.empty else pd.DataFrame()
            ok_missing_source_url = int(ok_rows["source_url"].eq("").sum()) if not ok_rows.empty else 0
            ok_missing_hash = int(ok_rows["raw_sha256"].eq("").sum()) if not ok_rows.empty else 0
            candidate = endpoint_catalog[
                endpoint_catalog["product_vt_symbol"].eq(product) & endpoint_catalog["route_group"].eq(route)
            ].copy()
            official_candidates = int(candidate["source_authority"].astype(str).str.contains("official", case=False).sum()) if not candidate.empty else 0
            third_party_candidates = int(candidate["source_authority"].astype(str).str.contains("third_party", case=False).sum()) if not candidate.empty else 0
            callable_candidates = int(candidate["callable_present"].sum()) if not candidate.empty and "callable_present" in candidate.columns else 0

            if route == "event_or_sentiment" and not selector_ready and not ready:
                action = "manual_event_source_discovery_required"
            elif selector_ready:
                action = "selector_ready_keep_auditing"
            elif ready:
                action = "monitor_ready_collect_pit_depth"
            elif observed and (ok_missing_source_url or ok_missing_hash):
                action = "repair_future_source_url_or_hash"
            elif observed:
                action = "observed_but_contract_incomplete_forensic"
            elif official_candidates:
                action = "build_official_forward_collector"
            elif third_party_candidates:
                action = "probe_third_party_forward_support"
            else:
                action = "source_discovery_required"

            rows.append(
                {
                    "product_family": str(pm_row.get("product_family", "")),
                    "product_vt_symbol": product,
                    "monitor_tier": str(pm_row.get("monitor_tier", "")),
                    "route_group": route,
                    "stage617_observed": observed,
                    "stage617_contract_complete": ready,
                    "stage617_selector_ready": selector_ready,
                    "current_ok_rows": int(len(ok_rows)),
                    "current_ok_missing_source_url": ok_missing_source_url,
                    "current_ok_missing_hash": ok_missing_hash,
                    "endpoint_candidates": int(len(candidate)),
                    "official_endpoint_candidates": official_candidates,
                    "third_party_endpoint_candidates": third_party_candidates,
                    "callable_candidates_present": callable_candidates,
                    "repair_action": action,
                    "selector_unlocked_by_this_stage": 0,
                    "paper_or_whitelist_allowed": 0,
                    "note": "; ".join(candidate["notes"].astype(str).head(2).tolist()) if not candidate.empty else "No candidate endpoint catalogued yet.",
                }
            )
    return pd.DataFrame(rows)


def build_gates(repair: pd.DataFrame, endpoint_catalog: pd.DataFrame, stage617_decision: dict[str, Any]) -> pd.DataFrame:
    official_candidates = int(repair["official_endpoint_candidates"].sum()) if not repair.empty else 0
    source_url_repairs = int((repair["repair_action"].eq("repair_future_source_url_or_hash")).sum()) if not repair.empty else 0
    selector_unlocked = int(repair["selector_unlocked_by_this_stage"].sum()) if not repair.empty else 0
    callable_missing = int((endpoint_catalog["callable_present"].eq(0) & endpoint_catalog["callable_name"].astype(str).ne("")).sum()) if not endpoint_catalog.empty else 0
    event_discovery = int((repair["route_group"].eq("event_or_sentiment") & repair["repair_action"].str.contains("discovery", case=False)).sum()) if not repair.empty else 0
    gates = [
        {
            "gate": "stage617_blocker_reproduced",
            "passed": stage617_decision.get("decision") == "pit_source_event_contract_ready_selector_not_ready",
            "actual": stage617_decision.get("decision"),
            "threshold": "selector_not_ready",
            "judgement": "必须先复现上一阶段阻塞，避免错口径推进。",
        },
        {
            "gate": "official_endpoint_candidates_catalogued",
            "passed": official_candidates >= 5,
            "actual": official_candidates,
            "threshold": ">=5",
            "judgement": "官方/交易所候选源存在，值得进入 forward collector 合同。",
        },
        {
            "gate": "future_source_url_repair_needed",
            "passed": source_url_repairs > 0,
            "actual": source_url_repairs,
            "threshold": ">0",
            "judgement": "P2 OBS 的主要修复点是未来行补 source_url/authority，而不是回填历史。",
        },
        {
            "gate": "akshare_callable_inventory_present",
            "passed": callable_missing == 0,
            "actual": callable_missing,
            "threshold": "0 missing callable",
            "judgement": "本地函数入口齐备，但仍需要 forward 采集和 parser 验证。",
        },
        {
            "gate": "event_source_discovery_still_needed",
            "passed": event_discovery > 0,
            "actual": event_discovery,
            "threshold": ">0",
            "judgement": "事件/舆情仍缺真实产品族覆盖，不能做 selector。",
        },
        {
            "gate": "selector_unlocked_now",
            "passed": selector_unlocked > 0,
            "actual": selector_unlocked,
            "threshold": ">0",
            "judgement": "本阶段只修源目录，不允许解锁 selector。",
        },
        {
            "gate": "paper_or_whitelist_allowed",
            "passed": int(repair["paper_or_whitelist_allowed"].sum()) > 0 if not repair.empty else False,
            "actual": int(repair["paper_or_whitelist_allowed"].sum()) if not repair.empty else 0,
            "threshold": ">0",
            "judgement": "source repair board 不能产生 paper 或交易白名单。",
        },
    ]
    return pd.DataFrame(gates)


def make_chart(repair: pd.DataFrame, endpoint_catalog: pd.DataFrame, gates: pd.DataFrame) -> None:
    plt.rcParams.update({"font.size": 10})
    fig, axes = plt.subplots(2, 2, figsize=(18, 11), constrained_layout=True)
    fig.suptitle("Stage619 source endpoint repair board: endpoint candidates exist, selector remains locked", fontsize=15)

    ax = axes[0, 0]
    pivot = repair.pivot(index="product_vt_symbol", columns="route_group", values="repair_action").reindex(index=MONITOR_PRODUCTS, columns=ROUTE_GROUPS)
    status_map = {
        "monitor_ready_collect_pit_depth": 3,
        "repair_future_source_url_or_hash": 2,
        "observed_but_contract_incomplete_forensic": 2,
        "build_official_forward_collector": 1,
        "probe_third_party_forward_support": 1,
        "source_discovery_required": 0,
        "manual_event_source_discovery_required": 0,
        "selector_ready_keep_auditing": 4,
    }
    label_map = {
        4: "SEL",
        3: "OK",
        2: "REPAIR",
        1: "BUILD",
        0: "DISC",
    }
    matrix = pivot.apply(lambda column: column.map(status_map)).fillna(0).astype(int)
    cmap = matplotlib.colors.ListedColormap(["#C62828", "#F9A825", "#EF6C00", "#2E7D32", "#1565C0"])
    ax.imshow(matrix.values, aspect="auto", cmap=cmap, vmin=0, vmax=4)
    ax.set_xticks(range(len(matrix.columns)))
    ax.set_xticklabels(matrix.columns, rotation=25, ha="right")
    ax.set_yticks(range(len(matrix.index)))
    ax.set_yticklabels(matrix.index)
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            ax.text(j, i, label_map[int(matrix.iloc[i, j])], ha="center", va="center", color="white", fontsize=8, fontweight="bold")
    ax.set_title("Route action matrix")

    ax = axes[0, 1]
    route_counts = (
        repair.groupby("route_group")
        .agg(
            observed=("stage617_observed", "sum"),
            contract_complete=("stage617_contract_complete", "sum"),
            endpoint_candidates=("endpoint_candidates", "sum"),
            official_candidates=("official_endpoint_candidates", "sum"),
        )
        .reindex(ROUTE_GROUPS)
        .fillna(0)
    )
    x = np.arange(len(route_counts.index))
    width = 0.2
    ax.bar(x - 1.5 * width, route_counts["observed"], width=width, label="observed", color="#7E57C2")
    ax.bar(x - 0.5 * width, route_counts["contract_complete"], width=width, label="contract complete", color="#2E7D32")
    ax.bar(x + 0.5 * width, route_counts["endpoint_candidates"], width=width, label="endpoint candidates", color="#F9A825")
    ax.bar(x + 1.5 * width, route_counts["official_candidates"], width=width, label="official candidates", color="#1565C0")
    ax.set_xticks(x)
    ax.set_xticklabels(route_counts.index, rotation=25, ha="right")
    ax.set_title("Observed vs repairable route coverage")
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.25)

    ax = axes[1, 0]
    product_debt = (
        repair.assign(
            repair_needed=repair["repair_action"].isin(["repair_future_source_url_or_hash", "observed_but_contract_incomplete_forensic"]).astype(int),
            build_needed=repair["repair_action"].isin(["build_official_forward_collector", "probe_third_party_forward_support"]).astype(int),
            discovery_needed=repair["repair_action"].str.contains("discovery", case=False, regex=False).astype(int),
        )
        .groupby("product_vt_symbol")[["repair_needed", "build_needed", "discovery_needed"]]
        .sum()
        .reindex(MONITOR_PRODUCTS)
        .fillna(0)
    )
    left = np.zeros(len(product_debt))
    colors = ["#EF6C00", "#F9A825", "#C62828"]
    for idx, column in enumerate(["repair_needed", "build_needed", "discovery_needed"]):
        ax.barh(product_debt.index, product_debt[column], left=left, label=column, color=colors[idx], alpha=0.85)
        left += product_debt[column].values
    ax.set_title("Repair debt by product")
    ax.set_xlabel("route count")
    ax.legend(fontsize=8)
    ax.grid(axis="x", alpha=0.25)

    ax = axes[1, 1]
    gate_view = gates.copy()
    gate_view["passed_int"] = gate_view["passed"].astype(int)
    gate_colors = ["#2E7D32" if item else "#C62828" for item in gate_view["passed_int"]]
    y = np.arange(len(gate_view))
    ax.barh(y, [1] * len(gate_view), color=gate_colors, alpha=0.9)
    ax.set_yticks(y)
    ax.set_yticklabels(gate_view["gate"])
    ax.set_xlim(0, 1)
    for idx, row in gate_view.iterrows():
        ax.text(0.02, idx, "PASS" if row["passed"] else "BLOCK", va="center", ha="left", color="white", fontweight="bold", fontsize=8)
    ax.set_title("Promotion gates")
    ax.set_xlabel("gate status")

    CHART_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def write_report(decision: dict[str, Any], endpoint: pd.DataFrame, repair: pd.DataFrame, gates: pd.DataFrame) -> None:
    lines = [
        "# Stage619 Source Endpoint Repair Board",
        "",
        "## Decision",
        "",
        f"- decision: `{decision['decision']}`",
        f"- promotion_allowed: `{decision['promotion_allowed']}`",
        f"- selector_unlocked_now: `{decision['selector_unlocked_now']}`",
        f"- official_endpoint_candidates: `{decision['official_endpoint_candidates']}`",
        f"- future_source_url_repairs: `{decision['future_source_url_repairs']}`",
        "",
        "## Route Repair Matrix",
        "",
        _md_table(repair, ["product_vt_symbol", "route_group", "stage617_observed", "stage617_contract_complete", "endpoint_candidates", "official_endpoint_candidates", "repair_action"], max_rows=40),
        "",
        "## Endpoint Catalog",
        "",
        _md_table(endpoint, ["product_vt_symbol", "route_group", "source_authority", "callable_name", "callable_present", "repair_type", "endpoint_url"], max_rows=60),
        "",
        "## Gates",
        "",
        _md_table(gates, ["gate", "passed", "actual", "threshold", "judgement"], max_rows=20),
        "",
        "## Interpretation",
        "",
        "- `REPAIR` means an observed row exists but future ledger rows need `source_url/source_authority/raw_hash` contract repair; historical rows are not retroactively upgraded.",
        "- `BUILD` means a callable official/third-party endpoint is catalogued but no PIT-complete monitor row exists yet.",
        "- `DISC` means event/sentiment source taxonomy is still missing; manual backfill remains prohibited.",
        "- This stage can move source engineering forward, but it does not unlock selector, paper, A/B, or whitelist.",
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
            "- Run-start judgement: not overfit. This stage only catalogues endpoints and source contracts; no return labels, no parameter sweep, no historical event backfill.",
            "- Run-end judgement: not overfit. Selector remains locked and all repair actions are forward-only.",
            "",
            "## Continue Value Reflection",
            "",
            "- Worth continuing because Stage317 blockers are source-contract blockers, not alpha failures.",
            "- The next valuable step is to implement forward collectors that persist `received_at/source_url/raw_hash/status`, then accumulate PIT dates.",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    product_matrix = _read_csv(STAGE617_PRODUCT_MATRIX)
    stage617_decision = _read_json(STAGE617_DECISION)
    endpoint = build_endpoint_catalog(product_matrix)
    ledger = _ledger_union()
    repair = build_repair_matrix(product_matrix, endpoint, ledger)
    gates = build_gates(repair, endpoint, stage617_decision)

    official_endpoint_candidates = int(repair["official_endpoint_candidates"].sum())
    future_source_url_repairs = int(repair["repair_action"].eq("repair_future_source_url_or_hash").sum())
    build_official_collectors = int(repair["repair_action"].eq("build_official_forward_collector").sum())
    event_discovery_routes = int((repair["route_group"].eq("event_or_sentiment") & repair["repair_action"].str.contains("discovery", case=False)).sum())
    selector_unlocked = int(repair["selector_unlocked_by_this_stage"].sum())

    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at_cst": datetime.now().strftime("%Y-%m-%d %H:%M:%S CST"),
        "decision": "source_endpoint_repair_board_ready_selector_still_locked",
        "new_backtest_run": False,
        "strategy_changed": False,
        "promotion_allowed": False,
        "paper_selector_allowed": False,
        "trading_whitelist_allowed": False,
        "selector_unlocked_now": selector_unlocked,
        "monitor_products": MONITOR_PRODUCTS,
        "route_rows": int(len(repair)),
        "endpoint_catalog_rows": int(len(endpoint)),
        "official_endpoint_candidates": official_endpoint_candidates,
        "future_source_url_repairs": future_source_url_repairs,
        "build_official_collectors": build_official_collectors,
        "event_discovery_routes": event_discovery_routes,
        "callable_present_rows": int(endpoint["callable_present"].sum()),
        "hard_gates_passed": int(gates["passed"].astype(bool).sum()),
        "hard_gates_total": int(len(gates)),
        "stage617_decision": stage617_decision.get("decision", ""),
        "next_priority": "implement_forward_source_collectors_no_history_backfill_then_accumulate_20_pit_dates",
        "overfit_reflection": "Not overfit: endpoint/source repair only, no return labels, no selector, no history backfill.",
        "continue_value_reflection": "Worth continuing: Stage317 source blockers can be repaired forward-only without changing strategy alpha.",
        "references": REFERENCE_LINKS,
        "outputs": {
            "endpoint_catalog": str(ENDPOINT_CATALOG_PATH),
            "route_repair_matrix": str(REPAIR_MATRIX_PATH),
            "gates": str(GATES_PATH),
            "report": str(REPORT_PATH),
            "chart": str(CHART_PATH),
        },
    }

    endpoint.to_csv(ENDPOINT_CATALOG_PATH, index=False, encoding="utf-8-sig")
    repair.to_csv(REPAIR_MATRIX_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    make_chart(repair, endpoint, gates)
    write_report(decision, endpoint, repair, gates)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
