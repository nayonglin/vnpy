from __future__ import annotations

from datetime import datetime
import importlib.util
import json
import math
import os
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
os.environ.setdefault("MPLCONFIGDIR", str(OUTPUT_DIR / ".matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_drawdown30_preserve_return"
MODEL_TAG = "stage623_authorized_source_event_taxonomy_board_v1"
OUTPUT_PREFIX = "qmt_roll_stage623_authorized_source_event_taxonomy_board"

STAGE620_LEDGER = OUTPUT_DIR / (
    "qmt_roll_stage620_forward_source_collector_contract_stage_ledger_"
    "stage620_forward_source_collector_contract_v1.csv"
)
STAGE620_DECISION = OUTPUT_DIR / (
    "qmt_roll_stage620_forward_source_collector_contract_decision_"
    "stage620_forward_source_collector_contract_v1.json"
)

SOURCE_LANE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_lane_catalog_{MODEL_TAG}.csv"
PRODUCT_ROUTE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_route_status_{MODEL_TAG}.csv"
EVENT_TAXONOMY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_taxonomy_catalog_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

MONITOR_PRODUCTS = ["j.DCE", "i.DCE", "ag.SHFE", "CY.CZCE", "SR.CZCE"]
ROUTES = ["basis", "inventory", "member_detail", "warehouse", "event_or_sentiment"]

REFERENCES = [
    "DCE API SDK (PyPI dceapi, requires DCE_API_KEY/DCE_SECRET): https://pypi.org/project/dceapi/",
    "DCE API Rust docs (delivery/member/news services): https://docs.rs/dceapi-rs/latest/dceapi_rs/",
    "ICE DCE market data catalog (licensed vendor route): https://developer.ice.com/fixed-income-data-services/catalog/dalian-commodity-exchange-dce",
    "AKShare futures docs / source routes: https://github.com/akfamily/akshare/blob/main/docs/data/futures/futures.md",
    "SHFE daily data page / daily warrant and ranking templates: https://tsite.shfe.com.cn/eng/reports/statistical/daily/index.html",
    "CZCE static holding example: https://www.czce.com.cn/cn/DFSStaticFiles/Future/2024/20240102/FutureDataHolding.htm",
]

PRODUCT_FAMILY = {
    "j.DCE": "black_ferrous",
    "i.DCE": "black_ferrous",
    "ag.SHFE": "precious_metals",
    "CY.CZCE": "soft_agri",
    "SR.CZCE": "soft_agri",
}

PRODUCT_CODE = {item: item.split(".")[0] for item in MONITOR_PRODUCTS}
EXCHANGE = {item: item.split(".")[1] for item in MONITOR_PRODUCTS}


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
        number = float(value)
        return None if math.isnan(number) or math.isinf(number) else number
    return value


def _md_table(frame: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 40) -> str:
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


def _env_present(name: str) -> int:
    return int(bool(os.environ.get(name, "")))


def _stage620_success(row: pd.Series) -> int:
    status = str(row.get("status", ""))
    raw_hash = str(row.get("raw_sha256", "") or "")
    matched = int(pd.to_numeric(pd.Series([row.get("matched_product", 0)]), errors="coerce").fillna(0).iloc[0])
    return int(status == "ok" and matched == 1 and len(raw_hash) > 0)


def build_product_route_status(ledger: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for product in MONITOR_PRODUCTS:
        for route in ROUTES:
            subset = ledger[ledger["product_vt_symbol"].astype(str).eq(product) & ledger["route_group"].astype(str).eq(route)]
            if subset.empty:
                status = "missing"
                raw_hash = ""
                source_url = ""
                matched = 0
                rows_returned = 0
            else:
                item = subset.iloc[-1]
                status = str(item.get("status", ""))
                raw_hash = str(item.get("raw_sha256", "") or "")
                source_url = str(item.get("source_url", "") or "")
                matched = int(pd.to_numeric(pd.Series([item.get("matched_product", 0)]), errors="coerce").fillna(0).iloc[0])
                rows_returned = int(pd.to_numeric(pd.Series([item.get("rows_returned", 0)]), errors="coerce").fillna(0).iloc[0])
            fetch_ok = int(status == "ok" and matched == 1 and len(raw_hash) > 0)
            if fetch_ok:
                evidence_state = "forward_monitor_ok"
            elif route == "event_or_sentiment":
                evidence_state = "taxonomy_required"
            elif status in {"error", "timeout", "empty_source_response", "ok_no_product_match"}:
                evidence_state = "fetch_failed"
            else:
                evidence_state = "not_ready"
            rows.append(
                {
                    "product_family": PRODUCT_FAMILY[product],
                    "product_vt_symbol": product,
                    "exchange": EXCHANGE[product],
                    "product_code": PRODUCT_CODE[product],
                    "route_group": route,
                    "stage620_status": status,
                    "stage620_fetch_ok": fetch_ok,
                    "matched_product": matched,
                    "rows_returned": rows_returned,
                    "raw_sha256_present": int(len(raw_hash) > 0),
                    "source_url": source_url,
                    "evidence_state": evidence_state,
                    "usable_for_forward_monitor": fetch_ok,
                    "usable_for_selector_now": 0,
                }
            )
    return pd.DataFrame(rows)


def _lane(
    product: str,
    route: str,
    lane_type: str,
    source_name: str,
    source_url: str,
    authority: str,
    current_state: str,
    monitor_allowed: int,
    selector_allowed: int,
    requires_credentials: int,
    credentials_present: int,
    auto_fetch_now: int,
    blocker: str,
    next_action: str,
) -> dict[str, Any]:
    actual_credentials_present = int(credentials_present) if int(requires_credentials) else 0
    access_requirement_satisfied = int((not int(requires_credentials)) or bool(credentials_present))
    return {
        "product_family": PRODUCT_FAMILY[product],
        "product_vt_symbol": product,
        "exchange": EXCHANGE[product],
        "product_code": PRODUCT_CODE[product],
        "route_group": route,
        "lane_type": lane_type,
        "source_name": source_name,
        "source_url": source_url,
        "source_authority": authority,
        "current_state": current_state,
        "monitor_allowed": int(monitor_allowed),
        "selector_allowed_now": int(selector_allowed),
        "requires_credentials": int(requires_credentials),
        "credentials_present": actual_credentials_present,
        "access_requirement_satisfied": access_requirement_satisfied,
        "auto_fetch_now": int(auto_fetch_now),
        "blocker": blocker,
        "next_action": next_action,
    }


def build_source_lane_catalog(route_status: pd.DataFrame) -> pd.DataFrame:
    dce_creds = int(_env_present("DCE_API_KEY") and _env_present("DCE_SECRET"))
    dceapi_installed = int(importlib.util.find_spec("dceapi") is not None)
    lanes: list[dict[str, Any]] = []

    for _, row in route_status.iterrows():
        product = str(row["product_vt_symbol"])
        route = str(row["route_group"])
        fetch_ok = int(row["stage620_fetch_ok"])
        if route in {"basis", "inventory"} and fetch_ok:
            lanes.append(
                _lane(
                    product,
                    route,
                    "current_third_party_forward",
                    "AKShare/third-party point-in-time row",
                    str(row["source_url"]),
                    "third_party_forward",
                    "ok_raw_hash_product_matched",
                    1,
                    0,
                    0,
                    1,
                    1,
                    "not official enough for history selector; use monitor only",
                    "accumulate 20 PIT dates; never backfill into history selector",
                )
            )

    for product in ["j.DCE", "i.DCE"]:
        for route in ["member_detail", "warehouse", "event_or_sentiment"]:
            lanes.append(
                _lane(
                    product,
                    route,
                    "authorized_dce_api_candidate",
                    "DCE API SDK / official authorized service",
                    "https://pypi.org/project/dceapi/",
                    "authorized_exchange_api_candidate",
                    "requires_credentials" if not dce_creds else "credentials_present_not_validated",
                    0,
                    0,
                    1,
                    dce_creds,
                    0,
                    f"DCE_API_KEY/DCE_SECRET missing; dceapi_installed={dceapi_installed}",
                    "obtain authorized credentials or vendor contract; then run read-only endpoint probe",
                )
            )
        lanes.append(
            _lane(
                product,
                "market_data",
                "licensed_vendor_candidate",
                "ICE DCE market data catalog",
                "https://developer.ice.com/fixed-income-data-services/catalog/dalian-commodity-exchange-dce",
                "licensed_vendor",
                "contract_required",
                0,
                0,
                1,
                0,
                0,
                "licensed market data route may not include member/warehouse fundamentals",
                "treat as TCA/market-data vendor candidate, not as current fundamental selector source",
            )
        )

    for product in ["ag.SHFE"]:
        lanes.append(
            _lane(
                product,
                "member_detail",
                "current_official_forward",
                "SHFE ranking via tsite/AKShare",
                "https://tsite.shfe.com.cn/statements/dataview.html?paramid=kx",
                "official_exchange",
                "ok_raw_hash_product_matched",
                1,
                0,
                0,
                1,
                1,
                "single successful route only; still needs PIT depth",
                "accumulate 20 PIT dates and validate product mapping",
            )
        )
        lanes.append(
            _lane(
                product,
                "warehouse",
                "official_route_repair_required",
                "SHFE daily warrant route",
                "https://tsite.shfe.com.cn/eng/reports/statistical/daily/index.html",
                "official_exchange",
                "stage620_error",
                0,
                0,
                0,
                1,
                0,
                "Stage620 warehouse route failed; likely parser/date/product contract issue",
                "repair SHFE warrant parser before any selector claim",
            )
        )

    for product in ["CY.CZCE", "SR.CZCE"]:
        for route in ["member_detail", "warehouse"]:
            lanes.append(
                _lane(
                    product,
                    route,
                    "official_static_file_repair_required",
                    "CZCE static future data files",
                    "https://www.czce.com.cn/cn/DFSStaticFiles/Future/{YYYY}/{YYYYMMDD}/",
                    "official_exchange",
                    "stage620_empty_or_timeout",
                    0,
                    0,
                    0,
                    1,
                    0,
                    "Stage620 empty/timeout; static date fallback and file availability need repair",
                    "probe trading-date static files with strict timeout and raw hash persistence",
                )
            )

    for product in MONITOR_PRODUCTS:
        lanes.append(
            _lane(
                product,
                "event_or_sentiment",
                "manual_public_event_taxonomy_contract",
                "exchange notices + public macro/industry event catalog",
                "product-specific source list in event taxonomy catalog",
                "public_manual_or_official",
                "taxonomy_contract_only",
                0,
                0,
                0,
                1,
                0,
                "taxonomy can be defined but no automated raw-text monitor is validated",
                "start with raw_text_hash ledger; selector remains locked until PIT depth and predictive audit",
            )
        )

    return pd.DataFrame(lanes)


def build_event_taxonomy_catalog() -> pd.DataFrame:
    rows = [
        {
            "product_vt_symbol": "j.DCE",
            "product_family": "black_ferrous",
            "event_family": "exchange_notice_delivery_margin",
            "source_candidates": "DCE official notices; DCE API news service if authorized",
            "source_url": "https://pypi.org/project/dceapi/",
            "mapping_keywords": "焦炭,coke,交割,仓单,保证金,限仓,会员持仓",
            "automation_state": "requires_authorized_dce_api_or_manual_raw_hash",
            "selector_allowed_now": 0,
            "notes": "Do not use scraped DCE pages as production source while 412/WAF route is unresolved.",
        },
        {
            "product_vt_symbol": "i.DCE",
            "product_family": "black_ferrous",
            "event_family": "exchange_notice_delivery_margin",
            "source_candidates": "DCE official notices; DCE API news service if authorized",
            "source_url": "https://pypi.org/project/dceapi/",
            "mapping_keywords": "铁矿石,iron ore,交割,仓单,保证金,限仓,会员持仓",
            "automation_state": "requires_authorized_dce_api_or_manual_raw_hash",
            "selector_allowed_now": 0,
            "notes": "Authorized API is a cleaner path than trying to bypass DCE public-web protections.",
        },
        {
            "product_vt_symbol": "ag.SHFE",
            "product_family": "precious_metals",
            "event_family": "exchange_notice_warehouse_macro",
            "source_candidates": "SHFE daily data and notices; public precious-metals inventory references",
            "source_url": "https://tsite.shfe.com.cn/eng/reports/statistical/daily/index.html",
            "mapping_keywords": "白银,silver,仓单,库存,交割,保证金,贵金属",
            "automation_state": "official_daily_data_partly_validated_member_only",
            "selector_allowed_now": 0,
            "notes": "Member detail succeeded; warehouse route still needs parser repair before source-rich status.",
        },
        {
            "product_vt_symbol": "CY.CZCE",
            "product_family": "soft_agri",
            "event_family": "crop_supply_exchange_notice",
            "source_candidates": "CZCE static files; USDA/NASS cotton crop reports; exchange notices",
            "source_url": "https://www.czce.com.cn/cn/DFSStaticFiles/Future/{YYYY}/{YYYYMMDD}/",
            "mapping_keywords": "棉纱,cotton yarn,cotton,棉花,仓单,持仓,天气,种植进度",
            "automation_state": "taxonomy_only_static_files_need_repair",
            "selector_allowed_now": 0,
            "notes": "Cotton external event mapping is plausible but must remain forward-only and manually hashed first.",
        },
        {
            "product_vt_symbol": "SR.CZCE",
            "product_family": "soft_agri",
            "event_family": "crop_supply_exchange_notice",
            "source_candidates": "CZCE static files; USDA/WASDE sugar reports; exchange notices",
            "source_url": "https://www.czce.com.cn/cn/DFSStaticFiles/Future/{YYYY}/{YYYYMMDD}/",
            "mapping_keywords": "白糖,sugar,甘蔗,甜菜,仓单,持仓,天气,产量",
            "automation_state": "taxonomy_only_static_files_need_repair",
            "selector_allowed_now": 0,
            "notes": "Sugar event mapping is weaker than exchange data; use only as forward monitor after raw_text_hash ledger starts.",
        },
    ]
    return pd.DataFrame(rows)


def build_gates(route_status: pd.DataFrame, source_lanes: pd.DataFrame, taxonomy: pd.DataFrame, stage620_decision: dict[str, Any]) -> pd.DataFrame:
    ok_routes = int(route_status["stage620_fetch_ok"].sum())
    dce_authorized_rows = source_lanes[source_lanes["lane_type"].eq("authorized_dce_api_candidate")]
    dce_creds_present = int(dce_authorized_rows["credentials_present"].sum() > 0) if not dce_authorized_rows.empty else 0
    event_taxonomy_contract_rows = int(len(taxonomy))
    event_auto_monitor_rows = int((source_lanes["route_group"].eq("event_or_sentiment") & source_lanes["auto_fetch_now"].eq(1)).sum())
    selector_rows = int(source_lanes["selector_allowed_now"].sum())
    gates = [
        {
            "gate": "stage620_fetch_probe_loaded",
            "passed": int(stage620_decision.get("decision", "") == "forward_source_fetch_probe_stage_scoped_rows_collected_selector_locked"),
            "actual": str(stage620_decision.get("decision", "")),
            "threshold": "Stage620 fetch rows collected decision",
            "judgement": "必须建立在真实 fetch ledger 上，而不是 dry-run 合同上。",
        },
        {
            "gate": "current_forward_monitor_routes_exist",
            "passed": int(ok_routes >= 10),
            "actual": ok_routes,
            "threshold": ">=10 route rows with raw hash",
            "judgement": "basis/inventory/partial member route 可进入 monitor 证据。",
        },
        {
            "gate": "dce_authorized_credentials_present",
            "passed": dce_creds_present,
            "actual": dce_creds_present,
            "threshold": "DCE_API_KEY and DCE_SECRET present",
            "judgement": "无授权凭证时不能把 DCE API SDK 路线计为可执行。",
        },
        {
            "gate": "event_taxonomy_contract_defined",
            "passed": int(event_taxonomy_contract_rows == len(MONITOR_PRODUCTS)),
            "actual": event_taxonomy_contract_rows,
            "threshold": f"{len(MONITOR_PRODUCTS)} products",
            "judgement": "事件分类先定义语义和来源，但不是自动 monitor。",
        },
        {
            "gate": "event_auto_monitor_validated",
            "passed": int(event_auto_monitor_rows > 0),
            "actual": event_auto_monitor_rows,
            "threshold": ">0 automated raw-text event rows",
            "judgement": "本阶段没有验证自动事件抓取，selector 继续锁定。",
        },
        {
            "gate": "selector_unlocked_now",
            "passed": int(selector_rows > 0),
            "actual": selector_rows,
            "threshold": ">0 selector-allowed rows",
            "judgement": "本阶段不得解锁 selector、paper 或白名单。",
        },
    ]
    return pd.DataFrame(gates)


def make_chart(route_status: pd.DataFrame, source_lanes: pd.DataFrame, taxonomy: pd.DataFrame, gates: pd.DataFrame) -> None:
    plt.rcParams.update({"font.size": 9})
    fig, axes = plt.subplots(2, 2, figsize=(18, 11), constrained_layout=True)
    fig.suptitle("Stage623 authorized source and event taxonomy board: source progress without selector unlock", fontsize=15)

    ax = axes[0, 0]
    matrix = (
        route_status.assign(
            state=np.where(
                route_status["stage620_fetch_ok"].eq(1),
                3,
                np.where(route_status["route_group"].eq("event_or_sentiment"), 1, 0),
            )
        )
        .pivot(index="product_vt_symbol", columns="route_group", values="state")
        .reindex(index=MONITOR_PRODUCTS, columns=ROUTES)
        .fillna(0)
        .astype(int)
    )
    labels = {0: "FAIL", 1: "TAX", 2: "AUTH", 3: "OK"}
    cmap = matplotlib.colors.ListedColormap(["#C62828", "#7B1FA2", "#F9A825", "#2E7D32"])
    ax.imshow(matrix.values, aspect="auto", cmap=cmap, vmin=0, vmax=3)
    ax.set_xticks(range(len(matrix.columns)))
    ax.set_xticklabels(matrix.columns, rotation=25, ha="right")
    ax.set_yticks(range(len(matrix.index)))
    ax.set_yticklabels(matrix.index)
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            ax.text(j, i, labels[int(matrix.iloc[i, j])], ha="center", va="center", color="white", fontweight="bold", fontsize=8)
    ax.set_title("Current Stage620 route evidence")

    ax = axes[0, 1]
    lane_counts = source_lanes.groupby("lane_type").size().sort_values()
    colors = [
        "#2E7D32" if "current" in lane else "#F9A825" if "authorized" in lane or "licensed" in lane else "#7B1FA2"
        for lane in lane_counts.index
    ]
    ax.barh(lane_counts.index, lane_counts.values, color=colors)
    ax.set_title("Source lane inventory")
    ax.set_xlabel("rows")
    ax.grid(axis="x", alpha=0.25)

    ax = axes[1, 0]
    event_state_counts = taxonomy["automation_state"].value_counts().sort_values()
    ax.barh(event_state_counts.index, event_state_counts.values, color="#7B1FA2")
    ax.set_title("Event taxonomy states")
    ax.set_xlabel("products")
    ax.grid(axis="x", alpha=0.25)

    ax = axes[1, 1]
    y = np.arange(len(gates))
    colors = ["#2E7D32" if bool(value) else "#C62828" for value in gates["passed"]]
    ax.barh(y, [1] * len(gates), color=colors)
    ax.set_yticks(y)
    ax.set_yticklabels(gates["gate"])
    ax.set_xlim(0, 1)
    for idx, row in gates.iterrows():
        ax.text(0.02, idx, "PASS" if bool(row["passed"]) else "BLOCK", va="center", color="white", fontweight="bold", fontsize=8)
    ax.set_title("Promotion and source gates")
    ax.set_xlabel("gate status")

    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def write_report(decision: dict[str, Any], source_lanes: pd.DataFrame, route_status: pd.DataFrame, taxonomy: pd.DataFrame, gates: pd.DataFrame) -> None:
    lines = [
        "# Stage623 Authorized Source and Event Taxonomy Board",
        "",
        "## Decision",
        "",
        f"- decision: `{decision['decision']}`",
        f"- stage620_raw_hash_rows: `{decision['stage620_raw_hash_rows']}`",
        f"- dce_authorized_credentials_present: `{decision['dce_authorized_credentials_present']}`",
        f"- event_taxonomy_contract_rows: `{decision['event_taxonomy_contract_rows']}`",
        f"- selector_unlocked_now: `{decision['selector_unlocked_now']}`",
        "",
        "## Product Route Status",
        "",
        _md_table(route_status, ["product_vt_symbol", "route_group", "stage620_status", "stage620_fetch_ok", "evidence_state"], max_rows=40),
        "",
        "## Source Lane Catalog",
        "",
        _md_table(
            source_lanes,
            ["product_vt_symbol", "route_group", "lane_type", "source_authority", "current_state", "monitor_allowed", "requires_credentials", "credentials_present", "access_requirement_satisfied", "auto_fetch_now", "blocker"],
            max_rows=60,
        ),
        "",
        "## Event Taxonomy",
        "",
        _md_table(taxonomy, ["product_vt_symbol", "event_family", "source_candidates", "automation_state", "selector_allowed_now", "notes"], max_rows=20),
        "",
        "## Gates",
        "",
        _md_table(gates, ["gate", "passed", "actual", "threshold", "judgement"], max_rows=20),
        "",
        "## Interpretation",
        "",
        "- Current third-party basis/inventory rows are useful for forward monitoring, not for historical selector backfill.",
        "- DCE member/warehouse/event routes should move through authorized credentials or a vendor contract, not public-web bypass attempts.",
        "- Event taxonomy is now explicit for the five monitor products, but no automated raw-text event monitor is validated in this stage.",
        "- Selector, paper, A/B, and trading whitelist remain locked.",
        "",
        "## References",
        "",
    ]
    lines.extend([f"- {item}" for item in REFERENCES])
    lines.extend(
        [
            "",
            "## Overfit Reflection",
            "",
            "- Run-start judgement: not overfit. This stage classifies source executability and event taxonomy, with no return labels.",
            "- Run-end judgement: not overfit. It keeps selector_allowed_now=0 and marks credential or parser gaps as blockers.",
            "",
            "## Continue Value Reflection",
            "",
            "- Worth continuing because it converts the vague event/source blocker into concrete credential, parser, and taxonomy work items.",
            "- Next work should be credentials/authorized-route probe or raw-text event ledger bootstrap, not wide-pool return backtests.",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ledger = _read_csv(STAGE620_LEDGER)
    stage620_decision = _read_json(STAGE620_DECISION)

    route_status = build_product_route_status(ledger)
    source_lanes = build_source_lane_catalog(route_status)
    taxonomy = build_event_taxonomy_catalog()
    gates = build_gates(route_status, source_lanes, taxonomy, stage620_decision)

    raw_hash_rows = int(route_status["stage620_fetch_ok"].sum())
    dce_creds = int(_env_present("DCE_API_KEY") and _env_present("DCE_SECRET"))
    selector_unlocked = int(source_lanes["selector_allowed_now"].sum())
    decision_name = (
        "authorized_source_event_taxonomy_contract_ready_selector_locked"
        if len(taxonomy) == len(MONITOR_PRODUCTS) and raw_hash_rows >= 10
        else "authorized_source_event_taxonomy_incomplete_selector_locked"
    )
    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at_cst": datetime.now().strftime("%Y-%m-%d %H:%M:%S CST"),
        "decision": decision_name,
        "new_backtest_run": False,
        "strategy_changed": False,
        "master_ledger_appended": False,
        "promotion_allowed": False,
        "paper_selector_allowed": False,
        "trading_whitelist_allowed": False,
        "stage620_raw_hash_rows": raw_hash_rows,
        "source_lane_rows": int(len(source_lanes)),
        "event_taxonomy_contract_rows": int(len(taxonomy)),
        "dce_authorized_credentials_present": dce_creds,
        "dceapi_python_installed": int(importlib.util.find_spec("dceapi") is not None),
        "event_auto_monitor_validated": int((source_lanes["route_group"].eq("event_or_sentiment") & source_lanes["auto_fetch_now"].eq(1)).sum()),
        "selector_unlocked_now": selector_unlocked,
        "hard_gates_passed": int(gates["passed"].astype(bool).sum()),
        "hard_gates_total": int(len(gates)),
        "next_priority": "obtain_authorized_dce_or_start_manual_raw_text_event_ledger_before_any_selector",
        "overfit_reflection": "Not overfit: source authorization and event taxonomy only; no returns, no selector, no whitelist.",
        "continue_value_reflection": "Worth continuing: turns event/source gaps into credential/parser/raw-text-ledger work items.",
        "references": REFERENCES,
        "outputs": {
            "source_lane_catalog": str(SOURCE_LANE_PATH),
            "product_route_status": str(PRODUCT_ROUTE_PATH),
            "event_taxonomy_catalog": str(EVENT_TAXONOMY_PATH),
            "gates": str(GATES_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
            "chart": str(CHART_PATH),
        },
    }

    source_lanes.to_csv(SOURCE_LANE_PATH, index=False, encoding="utf-8-sig")
    route_status.to_csv(PRODUCT_ROUTE_PATH, index=False, encoding="utf-8-sig")
    taxonomy.to_csv(EVENT_TAXONOMY_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    make_chart(route_status, source_lanes, taxonomy, gates)
    write_report(decision, source_lanes, route_status, taxonomy, gates)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
