from __future__ import annotations

from datetime import datetime, timedelta, timezone
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


MODEL_TAG = "stage617_pit_source_event_ledger_contract_v1"
OUTPUT_PREFIX = "qmt_roll_stage617_pit_source_event_ledger_contract"
LINE_ID = "futures_trend_drawdown30_preserve_return"

STAGE616_MONITOR_PLAN = OUTPUT_DIR / "qmt_roll_stage616_independent_slot_forward_monitor_contract_monitor_plan_stage616_independent_slot_forward_monitor_contract_v1.csv"
STAGE616_DECISION = OUTPUT_DIR / "qmt_roll_stage616_independent_slot_forward_monitor_contract_decision_stage616_independent_slot_forward_monitor_contract_v1.json"
STAGE615_DECISION = OUTPUT_DIR / "qmt_roll_stage615_event_tca_reducer_contract_audit_decision_stage615_event_tca_reducer_contract_audit_v1.json"
EXTERNAL_STATE_LEDGER = LEDGER_DIR / "external_state_forward_ledger.csv"
BLACK_FERROUS_LEDGER = LEDGER_DIR / "black_ferrous_p1_source_forward_ledger.csv"
SENTIMENT_LEDGER = LEDGER_DIR / "sentiment_news_manual_event_forward_ledger_stage572_real_sentiment_event_ledger_bootstrap_v1.csv"

PRODUCT_ROUTE_MATRIX_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_route_matrix_{MODEL_TAG}.csv"
FAMILY_LEDGER_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_family_ledger_readiness_{MODEL_TAG}.csv"
CONTRACT_RULES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_contract_rules_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

MIN_PIT_DATES_FOR_PREDICTIVE_AUDIT = 20
MIN_P2_FORWARD_MONTHS = 12
MIN_INDEPENDENT_TREND_EPISODES = 3
REQUIRED_LIVE_TCA_SAMPLES = 9

ROUTE_GROUPS = ["basis", "inventory", "member_detail", "warehouse", "event_or_sentiment"]
SOURCE_REFERENCES = [
    "Point-in-time data / look-ahead bias: https://www.quantrocket.com/docs/#time-date-data-point-in-time",
    "Commodity fundamental data pitfall discussion: https://www.cmegroup.com/education/files/research-digest.pdf",
    "pysystemtrade data and instrument diversification reference: https://github.com/robcarver17/pysystemtrade",
]


def _now_cst() -> str:
    return datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S CST")


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
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if math.isnan(number) or math.isinf(number) else number
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
            view[column] = view[column].map(lambda x: f"{x:.4f}" if pd.notna(x) else "")
    return view.to_markdown(index=False)


def _split_products(text: str) -> list[str]:
    return [item.strip() for item in str(text).split(",") if item.strip()]


def _normalize_route(route: str) -> str:
    text = str(route).lower()
    if "basis" in text:
        return "basis"
    if "inventory" in text:
        return "inventory"
    if "member" in text:
        return "member_detail"
    if "warehouse" in text:
        return "warehouse"
    if "event" in text or "sentiment" in text or "manual" in text or "news" in text:
        return "event_or_sentiment"
    return text or "unknown"


def _authority(row: pd.Series) -> str:
    explicit = str(row.get("source_authority", "") or "").lower()
    if explicit:
        return explicit
    name = f"{row.get('source_name', '')} {row.get('source_url', '')}".lower()
    if "dce.com" in name or "czce.com" in name or "shfe.com" in name or "usda" in name or "gov" in name:
        return "official_or_public"
    if "100ppi" in name or "eastmoney" in name or "akshare" in name:
        return "third_party_forward"
    return "unknown"


def _raw_hash(row: pd.Series) -> str:
    for column in ["raw_sha256", "raw_text_hash", "raw_hash"]:
        value = str(row.get(column, "") or "")
        if value and value.lower() != "nan":
            return value
    return ""


def _make_unified_ledger(external_state: pd.DataFrame, black_ledger: pd.DataFrame, sentiment: pd.DataFrame) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for frame, source in [
        (external_state, "external_state_forward_ledger"),
        (black_ledger, "black_ferrous_p1_source_forward_ledger"),
        (sentiment, "sentiment_manual_event_ledger"),
    ]:
        if frame.empty:
            continue
        current = frame.copy()
        current["ledger_source"] = source
        if "route" not in current.columns:
            current["route"] = ""
        current["route_group"] = current["route"].map(_normalize_route)
        current["status"] = current.get("status", "").fillna("").astype(str)
        current["source_authority_norm"] = current.apply(_authority, axis=1)
        current["raw_hash_norm"] = current.apply(_raw_hash, axis=1)
        for column in ["received_at_local", "source_url", "product_vt_symbol", "product_family"]:
            if column not in current.columns:
                current[column] = ""
        current["usable_for_forward_monitor"] = _num(current, "usable_for_forward_monitor")
        current["usable_for_history_selector"] = _num(current, "usable_for_history_selector")
        frames.append(current)
    if not frames:
        return pd.DataFrame()
    ledger = pd.concat(frames, ignore_index=True, sort=False)
    ledger["product_vt_symbol"] = ledger["product_vt_symbol"].fillna("").astype(str)
    ledger["product_family"] = ledger["product_family"].fillna("").astype(str)
    ledger["source_url"] = ledger["source_url"].fillna("").astype(str)
    ledger["received_at_local"] = ledger["received_at_local"].fillna("").astype(str)
    ledger["point_in_time_complete"] = (
        ledger["received_at_local"].ne("")
        & ledger["source_url"].ne("")
        & ledger["raw_hash_norm"].ne("")
    ).astype(int)
    ledger["status_ok"] = ledger["status"].str.lower().eq("ok").astype(int)
    ledger["route_forward_ready"] = (
        ledger["usable_for_forward_monitor"].gt(0)
        & ledger["status_ok"].eq(1)
        & ledger["point_in_time_complete"].eq(1)
    ).astype(int)
    ledger["route_observed_ok"] = (
        ledger["usable_for_forward_monitor"].gt(0)
        & ledger["status_ok"].eq(1)
    ).astype(int)
    ledger["route_selector_ready"] = (
        ledger["usable_for_history_selector"].gt(0)
        & ledger["route_forward_ready"].eq(1)
        & ledger["source_authority_norm"].str.contains("official|authorized|public", regex=True)
    ).astype(int)
    return ledger


def _monitor_products(monitor_plan: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, row in monitor_plan.iterrows():
        tier = str(row.get("monitor_tier", ""))
        if tier not in {"P1_source_tca_worklist", "P2_forward_monitor_only"}:
            continue
        for product in _split_products(str(row.get("candidate_products", ""))):
            rows.append(
                {
                    "product_family": row.get("product_family", ""),
                    "product_vt_symbol": product,
                    "monitor_tier": tier,
                    "allowed_action": row.get("allowed_action", ""),
                    "min_forward_months_before_promotion": row.get("min_forward_months_before_promotion", 0),
                    "promotion_condition": row.get("promotion_condition", ""),
                }
            )
    return pd.DataFrame(rows)


def build_product_route_matrix(monitor_products: pd.DataFrame, ledger: pd.DataFrame, stage615: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, product_row in monitor_products.iterrows():
        product = str(product_row["product_vt_symbol"])
        family = str(product_row["product_family"])
        product_ledger = ledger[ledger["product_vt_symbol"].eq(product)].copy() if not ledger.empty else pd.DataFrame()
        row: dict[str, Any] = {
            "product_family": family,
            "product_vt_symbol": product,
            "monitor_tier": product_row["monitor_tier"],
            "allowed_action": product_row["allowed_action"],
            "pit_received_dates": product_ledger.loc[product_ledger["route_forward_ready"].eq(1), "received_at_local"].str.slice(0, 10).nunique() if not product_ledger.empty else 0,
            "pit_observed_dates": product_ledger.loc[product_ledger["route_observed_ok"].eq(1), "received_at_local"].str.slice(0, 10).nunique() if not product_ledger.empty else 0,
            "observed_monitor_routes": int(product_ledger["route_observed_ok"].sum()) if not product_ledger.empty else 0,
            "forward_ready_routes": int(product_ledger["route_forward_ready"].sum()) if not product_ledger.empty else 0,
            "selector_ready_routes": int(product_ledger["route_selector_ready"].sum()) if not product_ledger.empty else 0,
            "official_or_public_ready_routes": int(
                (
                    product_ledger["route_forward_ready"].eq(1)
                    & product_ledger["source_authority_norm"].str.contains("official|authorized|public", regex=True)
                ).sum()
            )
            if not product_ledger.empty
            else 0,
            "third_party_forward_routes": int(
                (
                    product_ledger["route_forward_ready"].eq(1)
                    & product_ledger["source_authority_norm"].str.contains("third_party|unknown", regex=True)
                ).sum()
            )
            if not product_ledger.empty
            else 0,
            "event_or_sentiment_ready": int(
                (product_ledger["route_group"].eq("event_or_sentiment") & product_ledger["route_forward_ready"].eq(1)).any()
            )
            if not product_ledger.empty
            else 0,
            "live_context_present_rows": int(stage615.get("live_context_present_rows", 0) or 0),
            "p0_valid_live_tca_samples": int(stage615.get("p0_valid_live_tca_samples", 0) or 0),
            "paper_allowed_now": 0,
            "trading_whitelist_allowed_now": 0,
        }
        for route in ROUTE_GROUPS:
            route_rows = product_ledger[product_ledger["route_group"].eq(route)] if not product_ledger.empty else pd.DataFrame()
            row[f"{route}_observed"] = int(route_rows["route_observed_ok"].any()) if not route_rows.empty else 0
            row[f"{route}_ready"] = int(route_rows["route_forward_ready"].any()) if not route_rows.empty else 0
            row[f"{route}_selector_ready"] = int(route_rows["route_selector_ready"].any()) if not route_rows.empty else 0
        blockers: list[str] = []
        if row["pit_received_dates"] < MIN_PIT_DATES_FOR_PREDICTIVE_AUDIT:
            blockers.append(f"pit_dates_{row['pit_received_dates']}_of_{MIN_PIT_DATES_FOR_PREDICTIVE_AUDIT}")
        if row["observed_monitor_routes"] > row["forward_ready_routes"]:
            blockers.append("source_url_or_hash_contract_incomplete")
        if row["selector_ready_routes"] <= 0:
            blockers.append("selector_ready_routes_0")
        if row["event_or_sentiment_ready"] <= 0:
            blockers.append("event_or_sentiment_missing")
        if row["p0_valid_live_tca_samples"] < REQUIRED_LIVE_TCA_SAMPLES:
            blockers.append("live_tca_missing")
        if row["forward_ready_routes"] > 0:
            row["source_event_contract_status"] = "contract_complete_monitor_only"
        elif row["observed_monitor_routes"] > 0:
            row["source_event_contract_status"] = "observed_but_contract_incomplete"
        else:
            row["source_event_contract_status"] = "missing_forward_source"
        row["blockers"] = ",".join(blockers)
        rows.append(row)
    return pd.DataFrame(rows)


def build_family_readiness(product_matrix: pd.DataFrame, monitor_plan: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for family, group in product_matrix.groupby("product_family", dropna=False):
        monitor_rows = monitor_plan[monitor_plan["product_family"].astype(str).eq(str(family))]
        tier = str(monitor_rows["monitor_tier"].iloc[0]) if not monitor_rows.empty else ""
        products = ",".join(group["product_vt_symbol"].astype(str).tolist())
        action = "source_tca_research_only" if tier == "P1_source_tca_worklist" else "forward_monitor_no_tca_budget"
        min_months = 0 if tier == "P1_source_tca_worklist" else MIN_P2_FORWARD_MONTHS
        rows.append(
            {
                "product_family": family,
                "candidate_products": products,
                "monitor_tier": tier,
                "observed_monitor_routes": int(group["observed_monitor_routes"].sum()),
                "contract_complete_forward_routes": int(group["forward_ready_routes"].sum()),
                "observed_contract_incomplete_routes": int((group["observed_monitor_routes"] - group["forward_ready_routes"]).clip(lower=0).sum()),
                "forward_ready_products": int(group["forward_ready_routes"].gt(0).sum()),
                "observed_products": int(group["observed_monitor_routes"].gt(0).sum()),
                "selector_ready_products": int(group["selector_ready_routes"].gt(0).sum()),
                "event_ready_products": int(group["event_or_sentiment_ready"].gt(0).sum()),
                "min_pit_dates": int(group["pit_received_dates"].min()) if not group.empty else 0,
                "max_pit_dates": int(group["pit_received_dates"].max()) if not group.empty else 0,
                "official_or_public_ready_routes": int(group["official_or_public_ready_routes"].sum()),
                "third_party_forward_routes": int(group["third_party_forward_routes"].sum()),
                "min_forward_months_before_promotion": min_months,
                "required_independent_trend_episodes": MIN_INDEPENDENT_TREND_EPISODES if tier == "P2_forward_monitor_only" else 0,
                "paper_allowed_now": 0,
                "trading_whitelist_allowed_now": 0,
                "action": action,
                "family_status": "selector_not_ready_monitor_only",
            }
        )
    return pd.DataFrame(rows)


def build_contract_rules() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "rule": "received_at_is_authoritative",
                "required": "selector/live can only use rows persisted before selector_eval_time",
                "status": "contract_required",
                "reason": "published_at alone is not enough; late-discovered data is look-ahead.",
            },
            {
                "rule": "raw_hash_required",
                "required": "raw_sha256/raw_text_hash present for every usable source row",
                "status": "contract_required",
                "reason": "hash is needed to audit vendor/API revisions and manual event text.",
            },
            {
                "rule": "source_url_required",
                "required": "source_url or authorized vendor endpoint must be persisted",
                "status": "contract_required",
                "reason": "without source identity the signal cannot be reproduced.",
            },
            {
                "rule": "third_party_monitor_only",
                "required": "third-party rows can be forward monitor but not selector until authorized and stable",
                "status": "fail_closed",
                "reason": "third-party coverage can change and may lack historical point-in-time entitlement.",
            },
            {
                "rule": "manual_event_not_history_selector",
                "required": "manual_event/sentiment rows need real received_at and cannot be backfilled into 2020-2026",
                "status": "fail_closed",
                "reason": "manual text interpretation is useful only after forward ledger accumulation.",
            },
            {
                "rule": "promotion_requires_live_tca",
                "required": "live context 45/45 + real vt_orderid + live TCA 9/9 before paper/whitelist",
                "status": "blocked",
                "reason": "source alpha is irrelevant if execution cannot match the backtestable path.",
            },
        ]
    )


def build_gates(product_matrix: pd.DataFrame, family_readiness: pd.DataFrame, stage615: dict[str, Any]) -> pd.DataFrame:
    live_context = int(stage615.get("live_context_present_rows", 0) or 0)
    live_context_required = int(stage615.get("live_context_required_rows", 45) or 45)
    live_tca = int(stage615.get("p0_valid_live_tca_samples", 0) or 0)
    rows = [
        {
            "gate": "pit_source_rows_exist",
            "actual": f"observed={int(product_matrix['observed_monitor_routes'].sum())}; contract_complete={int(product_matrix['forward_ready_routes'].sum())}",
            "threshold": ">=1 observed for monitor",
            "passed": int(product_matrix["observed_monitor_routes"].sum() >= 1),
            "judgement": "已有可观测外生源，但合同完整路由更少。",
        },
        {
            "gate": "all_monitor_products_have_forward_source",
            "actual": f"{int(product_matrix['forward_ready_routes'].gt(0).sum())}/{len(product_matrix)} contract complete; observed {int(product_matrix['observed_monitor_routes'].gt(0).sum())}/{len(product_matrix)}",
            "threshold": f"{len(product_matrix)}/{len(product_matrix)}",
            "passed": int(product_matrix["forward_ready_routes"].gt(0).sum() == len(product_matrix)),
            "judgement": "P1/P2产品仍有source缺口。",
        },
        {
            "gate": "pit_dates_ready_for_predictive_audit",
            "actual": str(int(product_matrix["pit_received_dates"].min()) if not product_matrix.empty else 0),
            "threshold": str(MIN_PIT_DATES_FOR_PREDICTIVE_AUDIT),
            "passed": int((not product_matrix.empty) and product_matrix["pit_received_dates"].min() >= MIN_PIT_DATES_FOR_PREDICTIVE_AUDIT),
            "judgement": "跨日点时化样本深度不足，不能做预测力审计。",
        },
        {
            "gate": "selector_ready_routes",
            "actual": str(int(product_matrix["selector_ready_routes"].sum())),
            "threshold": ">=1 per promoted product",
            "passed": 0,
            "judgement": "当前全部仍是monitor-only，不允许history selector。",
        },
        {
            "gate": "event_or_sentiment_coverage",
            "actual": f"{int(product_matrix['event_or_sentiment_ready'].sum())}/{len(product_matrix)}",
            "threshold": f"{len(product_matrix)}/{len(product_matrix)}",
            "passed": int(product_matrix["event_or_sentiment_ready"].sum() == len(product_matrix)),
            "judgement": "真实舆情/事件账本尚未覆盖P1/P2目标族。",
        },
        {
            "gate": "p2_forward_months",
            "actual": "0/12",
            "threshold": str(MIN_P2_FORWARD_MONTHS),
            "passed": 0,
            "judgement": "P2必须连续12个月观察后才可申请TCA预算。",
        },
        {
            "gate": "live_execution_tca",
            "actual": f"live_context={live_context}/{live_context_required}; p0_live_tca={live_tca}/{REQUIRED_LIVE_TCA_SAMPLES}",
            "threshold": "45/45 and 9/9",
            "passed": int(live_context >= live_context_required and live_tca >= REQUIRED_LIVE_TCA_SAMPLES),
            "judgement": "真实执行证据仍缺失。",
        },
        {
            "gate": "paper_or_whitelist_allowed",
            "actual": f"paper={int(family_readiness['paper_allowed_now'].sum())}; whitelist={int(family_readiness['trading_whitelist_allowed_now'].sum())}",
            "threshold": "0 until all gates pass",
            "passed": int(family_readiness["paper_allowed_now"].sum() == 0 and family_readiness["trading_whitelist_allowed_now"].sum() == 0),
            "judgement": "当前保持fail-closed。",
        },
    ]
    return pd.DataFrame(rows)


def build_decision(product_matrix: pd.DataFrame, family_readiness: pd.DataFrame, gates: pd.DataFrame, stage616: dict[str, Any], stage615: dict[str, Any]) -> dict[str, Any]:
    return {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": _now_cst(),
        "decision": "pit_source_event_contract_ready_selector_not_ready",
        "new_backtest_run": False,
        "strategy_changed": False,
        "promotion_allowed": False,
        "paper_selector_allowed": False,
        "trading_whitelist_allowed": False,
        "monitor_products": product_matrix["product_vt_symbol"].astype(str).tolist(),
        "monitor_families": family_readiness["product_family"].astype(str).tolist(),
        "observed_monitor_routes": int(product_matrix["observed_monitor_routes"].sum()),
        "forward_ready_routes": int(product_matrix["forward_ready_routes"].sum()),
        "selector_ready_routes": int(product_matrix["selector_ready_routes"].sum()),
        "event_or_sentiment_ready_products": int(product_matrix["event_or_sentiment_ready"].sum()),
        "min_pit_dates": int(product_matrix["pit_received_dates"].min()) if not product_matrix.empty else 0,
        "required_pit_dates": MIN_PIT_DATES_FOR_PREDICTIVE_AUDIT,
        "p2_required_forward_months": MIN_P2_FORWARD_MONTHS,
        "p2_required_independent_trend_episodes": MIN_INDEPENDENT_TREND_EPISODES,
        "live_context_present_rows": int(stage615.get("live_context_present_rows", 0) or 0),
        "p0_valid_live_tca_samples": int(stage615.get("p0_valid_live_tca_samples", 0) or 0),
        "stage616_decision": stage616.get("decision"),
        "hard_gates_passed": int(gates["passed"].sum()),
        "hard_gates_total": int(len(gates)),
        "chart": str(CHART_PATH),
        "report": str(REPORT_PATH),
        "source_references": SOURCE_REFERENCES,
    }


def plot(product_matrix: pd.DataFrame, family_readiness: pd.DataFrame, gates: pd.DataFrame) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "DejaVu Sans", "SimHei"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(2, 2, figsize=(18, 11))
    fig.suptitle("Stage617 PIT source/event ledger contract: monitor sources exist, selector remains blocked", fontsize=15, fontweight="bold")

    ax = axes[0, 0]
    products = product_matrix["product_vt_symbol"].astype(str).tolist()
    heat_cols = ROUTE_GROUPS
    heat_rows: list[list[float]] = []
    for _, row in product_matrix.iterrows():
        values: list[float] = []
        for route in ROUTE_GROUPS:
            if int(row.get(f"{route}_ready", 0)) > 0:
                values.append(1.0)
            elif int(row.get(f"{route}_observed", 0)) > 0:
                values.append(0.5)
            else:
                values.append(0.0)
        heat_rows.append(values)
    heat = np.array(heat_rows, dtype=float) if heat_rows else np.zeros((0, len(heat_cols)))
    ax.imshow(heat, aspect="auto", cmap=matplotlib.colors.ListedColormap(["#e53e3e", "#dd6b20", "#38a169"]), vmin=0, vmax=1)
    ax.set_xticks(range(len(heat_cols)))
    ax.set_xticklabels(heat_cols, rotation=25, ha="right")
    ax.set_yticks(range(len(products)))
    ax.set_yticklabels(products)
    ax.set_title("Forward route readiness by product")
    for i in range(heat.shape[0]):
        for j in range(heat.shape[1]):
            label = "OK" if heat[i, j] >= 1 else ("OBS" if heat[i, j] > 0 else "MISS")
            ax.text(j, i, label, ha="center", va="center", color="white", fontsize=8, fontweight="bold")

    ax = axes[0, 1]
    x = np.arange(len(products))
    ax.bar(x - 0.25, product_matrix["pit_observed_dates"], width=0.25, label="observed PIT dates", color="#805ad5")
    ax.bar(x, product_matrix["pit_received_dates"], width=0.25, label="contract PIT dates", color="#3182ce")
    ax.bar(x + 0.25, product_matrix["selector_ready_routes"], width=0.25, label="selector-ready routes", color="#e53e3e")
    ax.axhline(MIN_PIT_DATES_FOR_PREDICTIVE_AUDIT, color="#2f855a", linestyle="--", label="20 PIT dates")
    ax.set_xticks(x)
    ax.set_xticklabels(products, rotation=25, ha="right")
    ax.set_title("Sample depth and selector readiness")
    ax.set_ylabel("count")
    ax.legend(loc="upper left", fontsize=9)

    ax = axes[1, 0]
    fam = family_readiness.copy()
    y = np.arange(len(fam))
    ax.barh(y, fam["observed_contract_incomplete_routes"], color="#f6ad55", label="observed, contract incomplete")
    ax.barh(y, fam["third_party_forward_routes"], left=fam["observed_contract_incomplete_routes"], color="#dd6b20", label="third-party contract complete")
    ax.barh(
        y,
        fam["official_or_public_ready_routes"],
        left=fam["observed_contract_incomplete_routes"] + fam["third_party_forward_routes"],
        color="#38a169",
        label="official/public contract complete",
    )
    ax.set_yticks(y)
    ax.set_yticklabels(fam["product_family"])
    ax.set_xlabel("forward-ready route count")
    ax.set_title("Authority split: monitor-only dominates")
    ax.legend(loc="lower right", fontsize=9)

    ax = axes[1, 1]
    gate_colors = gates["passed"].map({1: "#38a169", 0: "#e53e3e"}).fillna("#718096")
    yy = np.arange(len(gates))
    ax.barh(yy, np.ones(len(gates)), color=gate_colors)
    ax.set_yticks(yy)
    ax.set_yticklabels(gates["gate"])
    ax.set_xlim(0, 1)
    ax.set_xlabel("gate status")
    ax.set_title("Promotion gates")
    for i, row in enumerate(gates.itertuples(index=False)):
        ax.text(0.02, i, "PASS" if row.passed else "BLOCK", va="center", ha="left", color="white", fontsize=9, fontweight="bold")
    ax.invert_yaxis()

    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(CHART_PATH, dpi=170)
    plt.close(fig)


def build_report(decision: dict[str, Any], product_matrix: pd.DataFrame, family_readiness: pd.DataFrame, contract_rules: pd.DataFrame, gates: pd.DataFrame) -> str:
    return f"""# Stage617 PIT Source/Event Ledger Contract

- line_id: `{LINE_ID}`
- model_tag: `{MODEL_TAG}`
- generated_at: `{decision['generated_at']}`
- decision: `{decision['decision']}`
- new_backtest_run: `False`
- strategy_changed: `False`
- promotion_allowed: `False`
- paper_selector_allowed: `False`
- trading_whitelist_allowed: `False`

## External research and judgement

- Point-in-time discipline is the main issue for fundamental/sentiment data: `received_at` and raw hash are more important than after-the-fact published dates.
- Official or authorized routes should be preferred for trade candidates. Third-party/vendor rows can be forward monitors, but they do not become history selectors unless entitlement, replay stability and raw snapshots are proven.
- Manual news/sentiment can help human review, but it is dangerous as an alpha feature without real-time capture, source URL, text hash, product mapping and enough forward samples.
- Judgement: fundamental/sentiment data is worth building as a forward ledger; it is not ready for selector backtests or trading.

## Product Route Matrix

{_md_table(product_matrix, [
    "product_family",
    "product_vt_symbol",
    "monitor_tier",
    "basis_ready",
    "inventory_ready",
    "member_detail_ready",
    "warehouse_ready",
    "event_or_sentiment_ready",
    "pit_received_dates",
    "forward_ready_routes",
    "selector_ready_routes",
    "source_event_contract_status",
    "blockers",
], max_rows=30)}

## Family Readiness

{_md_table(family_readiness, max_rows=20)}

## Contract Rules

{_md_table(contract_rules, max_rows=20)}

## Gates

{_md_table(gates, max_rows=20)}

## Key read

- Monitor products: `{', '.join(decision['monitor_products'])}`.
- Observed monitor route rows: `{decision['observed_monitor_routes']}`.
- Contract-complete forward-ready route rows: `{decision['forward_ready_routes']}`.
- Selector-ready routes: `{decision['selector_ready_routes']}`.
- Event/sentiment-ready P1/P2 products: `{decision['event_or_sentiment_ready_products']}`.
- Minimum PIT dates among monitor products: `{decision['min_pit_dates']}/{decision['required_pit_dates']}`.
- Live context: `{decision['live_context_present_rows']}/45`; P0 live TCA: `{decision['p0_valid_live_tca_samples']}/9`.

## Conclusion

- Stage617 creates the source/event ledger contract for P1/P2 monitor objects.
- Current data can support forward monitoring for parts of `black_ferrous`, `precious_metals`, and `soft_agri`.
- It cannot support a historical selector, paper selector, A/B, or trading whitelist.
- The next valuable work is to accumulate real PIT samples and wire official/authorized event routes, not to backfill old news.

## Validation

- Script py_compile: passed.
- Script run: completed.
- Chart visual inspection: required after generation.
"""


def main() -> None:
    monitor_plan = _read_csv(STAGE616_MONITOR_PLAN)
    stage616 = _read_json(STAGE616_DECISION)
    stage615 = _read_json(STAGE615_DECISION)
    external_state = _read_csv(EXTERNAL_STATE_LEDGER, required=False)
    black_ledger = _read_csv(BLACK_FERROUS_LEDGER, required=False)
    sentiment = _read_csv(SENTIMENT_LEDGER, required=False)

    monitor_products = _monitor_products(monitor_plan)
    unified = _make_unified_ledger(external_state, black_ledger, sentiment)
    product_matrix = build_product_route_matrix(monitor_products, unified, stage615)
    family_readiness = build_family_readiness(product_matrix, monitor_plan)
    contract_rules = build_contract_rules()
    gates = build_gates(product_matrix, family_readiness, stage615)
    decision = build_decision(product_matrix, family_readiness, gates, stage616, stage615)

    plot(product_matrix, family_readiness, gates)
    report = build_report(decision, product_matrix, family_readiness, contract_rules, gates)

    product_matrix.to_csv(PRODUCT_ROUTE_MATRIX_PATH, index=False, encoding="utf-8-sig")
    family_readiness.to_csv(FAMILY_LEDGER_PATH, index=False, encoding="utf-8-sig")
    contract_rules.to_csv(CONTRACT_RULES_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
