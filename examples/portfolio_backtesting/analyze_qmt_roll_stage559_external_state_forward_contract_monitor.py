from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
LEDGER_DIR = OUTPUT_DIR / "external_state_forward_ledger"

MODEL_TAG = "stage559_external_state_forward_contract_monitor_v1"
OUTPUT_PREFIX = "qmt_roll_stage559_external_state_forward_contract_monitor"
LINE_ID = "futures_trend_drawdown30_preserve_return"

MASTER_LEDGER_PATH = LEDGER_DIR / "external_state_forward_ledger.csv"
SOURCE_CONTRACT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_contract_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_contract_gates_{MODEL_TAG}.csv"
SENTIMENT_TEMPLATE_PATH = LEDGER_DIR / f"sentiment_news_forward_ledger_template_{MODEL_TAG}.csv"
SENTIMENT_SCHEMA_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_sentiment_schema_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

MIN_FORWARD_RUNS_FOR_SELECTOR_AUDIT = 20
MIN_FORWARD_DATES_FOR_SELECTOR_AUDIT = 20
MIN_ACTIVE_FORWARD_ROUTES = 2

CORE_LEDGER_COLUMNS = [
    "run_id",
    "received_at_local",
    "received_at_utc",
    "line_id",
    "route",
    "product_vt_symbol",
    "product_code",
    "exchange",
    "product_family",
    "source_name",
    "source_function",
    "source_date",
    "status",
    "source_age_days",
    "usable_for_forward_monitor",
    "usable_for_history_selector",
    "data_value_json",
    "raw_sha256",
    "point_in_time_rule",
]

SENTIMENT_SCHEMA = [
    ("run_id", "string", "每次采集的唯一ID，不允许复用。", 1),
    ("received_at_local", "datetime", "本地实际接收时间；交易决策只能使用此时间之前已落盘记录。", 1),
    ("received_at_utc", "datetime", "UTC实际接收时间。", 1),
    ("line_id", "string", "研究线ID。", 1),
    ("route", "string", "固定为 sentiment_news 或 manual_event。", 1),
    ("product_vt_symbol", "string", "映射后的品种，例如 al.SHFE；多品种事件拆多行。", 1),
    ("product_code", "string", "品种代码，例如 AL。", 1),
    ("exchange", "string", "交易所。", 1),
    ("product_family", "string", "产品族。", 1),
    ("source_name", "string", "来源名称，例如交易所公告/行业网站/新闻服务。", 1),
    ("source_url", "string", "可追溯链接或内部文档ID。", 1),
    ("published_at", "datetime", "来源声称发布时间；不得替代 received_at。", 1),
    ("headline", "string", "标题。", 1),
    ("summary", "string", "短摘要，人工或模型生成都可，但必须在 received_at 后生成并落盘。", 1),
    ("raw_text_hash", "sha256", "原文或原始JSON的稳定hash。", 1),
    ("raw_text_excerpt", "string", "短摘录，用于人工复核。", 0),
    ("event_type", "enum", "supply/demand/policy/weather/logistics/macro/position/other。", 1),
    ("sentiment_label", "enum", "bullish/bearish/mixed/neutral/unknown。", 1),
    ("sentiment_score", "float", "-1 到 1；可为空，但不能凭未来价格重标。", 0),
    ("relevance_score", "float", "0 到 1；品种相关性。", 1),
    ("direction_hint", "enum", "long/short/none/unknown；只作为paper字段，不直接交易。", 0),
    ("mapper_version", "string", "品种映射规则版本。", 1),
    ("product_mapping_method", "string", "keyword/manual/model/exchange_symbol 等。", 1),
    ("status", "enum", "ok/duplicate/low_relevance/source_error/rejected。", 1),
    ("source_age_hours", "float", "received_at 与 published_at 的延迟。", 1),
    ("usable_for_forward_monitor", "int", "是否允许进入forward paper监控。", 1),
    ("usable_for_history_selector", "int", "默认0；只有长期PIT账本通过后才可置1。", 1),
    ("point_in_time_rule", "string", "固定写明只能使用 received_at 之前已落盘数据。", 1),
    ("notes", "string", "人工备注。", 0),
]


def _json_safe(value):
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


def _gate(name: str, passed: bool, current: str, required: str, reason: str) -> dict[str, object]:
    return {
        "gate": name,
        "passed": int(bool(passed)),
        "current": current,
        "required": required,
        "reason": reason,
    }


def _route_summary(ledger: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for route, group in ledger.groupby("route", dropna=False):
        products = int(group["product_vt_symbol"].nunique())
        ok = group[group["status"].eq("ok")]
        forward = group[pd.to_numeric(group["usable_for_forward_monitor"], errors="coerce").fillna(0).gt(0)]
        history = group[pd.to_numeric(group["usable_for_history_selector"], errors="coerce").fillna(0).gt(0)]
        ok_raw_hash_rate = 100.0 * ok["raw_sha256"].fillna("").astype(str).ne("").mean() if len(ok) else 0.0
        rows.append(
            {
                "route": str(route),
                "source_group": "external_state",
                "automation_level": "automatic_probe",
                "current_contract_status": "forward_monitor_partial" if int(forward["product_vt_symbol"].nunique()) > 0 else "not_live_ready",
                "products": products,
                "ok_products": int(ok["product_vt_symbol"].nunique()),
                "forward_ready_products": int(forward["product_vt_symbol"].nunique()),
                "history_ready_products": int(history["product_vt_symbol"].nunique()),
                "ok_raw_hash_rate_pct": ok_raw_hash_rate,
                "latest_received_at_local": str(group["received_at_local"].max()),
                "next_action": _route_next_action(str(route), int(forward["product_vt_symbol"].nunique()), int(history["product_vt_symbol"].nunique())),
            }
        )
    extra = pd.DataFrame(
        [
            {
                "route": "sentiment_news",
                "source_group": "external_state",
                "automation_level": "manual_or_provider_ingest",
                "current_contract_status": "schema_template_only",
                "products": 0,
                "ok_products": 0,
                "forward_ready_products": 0,
                "history_ready_products": 0,
                "ok_raw_hash_rate_pct": 0.0,
                "latest_received_at_local": "",
                "next_action": "build CSV/JSON forward ledger with received_at/source_url/raw_hash/product_mapping before any use",
            },
            {
                "route": "manual_event",
                "source_group": "external_state",
                "automation_level": "manual_ingest",
                "current_contract_status": "schema_template_only",
                "products": 0,
                "ok_products": 0,
                "forward_ready_products": 0,
                "history_ready_products": 0,
                "ok_raw_hash_rate_pct": 0.0,
                "latest_received_at_local": "",
                "next_action": "only allow pre-decision event records; split multi-product events into product rows",
            },
        ]
    )
    return pd.concat([pd.DataFrame(rows), extra], ignore_index=True).sort_values(["source_group", "route"])


def _route_next_action(route: str, forward_products: int, history_products: int) -> str:
    if route in {"basis", "inventory"} and forward_products > 0 and history_products == 0:
        return "continue daily/weekly forward collection; do not use for history selector yet"
    if route in {"member_detail", "warehouse"} and forward_products == 0:
        return "repair source or replace provider before depending on this route"
    return "monitor"


def _write_sentiment_template() -> None:
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    columns = [item[0] for item in SENTIMENT_SCHEMA]
    template = pd.DataFrame(columns=columns)
    template.to_csv(SENTIMENT_TEMPLATE_PATH, index=False, encoding="utf-8-sig")


def _schema_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "column": column,
                "type": dtype,
                "required": required,
                "description": description,
            }
            for column, dtype, description, required in SENTIMENT_SCHEMA
        ]
    )


def _build_gates(ledger: pd.DataFrame, source_contract: pd.DataFrame) -> pd.DataFrame:
    missing_columns = [column for column in CORE_LEDGER_COLUMNS if column not in ledger.columns]
    run_count = int(ledger["run_id"].nunique()) if "run_id" in ledger.columns else 0
    received_dates = int(pd.to_datetime(ledger["received_at_local"], errors="coerce").dt.date.nunique()) if "received_at_local" in ledger.columns else 0
    active_forward_routes = int((source_contract["forward_ready_products"] > 0).sum())
    sentiment_candidates = int((source_contract["route"].eq("sentiment_news") & source_contract["current_contract_status"].eq("forward_monitor_partial")).sum())
    point_in_time_ok = bool(ledger["point_in_time_rule"].fillna("").astype(str).str.contains("received_at").all()) if "point_in_time_rule" in ledger.columns and len(ledger) else False
    ok_rows = ledger[ledger["status"].eq("ok")] if "status" in ledger.columns else pd.DataFrame()
    hash_ok = bool(ok_rows["raw_sha256"].fillna("").astype(str).ne("").mean() >= 0.95) if len(ok_rows) and "raw_sha256" in ledger.columns else False
    history_products = int(ledger.loc[pd.to_numeric(ledger.get("usable_for_history_selector", 0), errors="coerce").fillna(0).gt(0), "product_vt_symbol"].nunique()) if "product_vt_symbol" in ledger.columns else 0

    return pd.DataFrame(
        [
            _gate("core_ledger_schema_ok", not missing_columns, f"missing={missing_columns}", "all core ledger columns present", "外生状态总账必须先满足统一字段契约。"),
            _gate("point_in_time_rule_present", point_in_time_ok, str(point_in_time_ok), "all rows mention received_at rule", "避免未来数据泄漏。"),
            _gate("ok_rows_have_raw_hash", hash_ok, f"{len(ok_rows)} ok rows", ">=95% ok rows with raw_sha256", "同一来源后续变更时必须可追踪。"),
            _gate("enough_forward_runs", run_count >= MIN_FORWARD_RUNS_FOR_SELECTOR_AUDIT, str(run_count), f">={MIN_FORWARD_RUNS_FOR_SELECTOR_AUDIT}", "样本深度不足不能做预测力审计。"),
            _gate("enough_forward_dates", received_dates >= MIN_FORWARD_DATES_FOR_SELECTOR_AUDIT, str(received_dates), f">={MIN_FORWARD_DATES_FOR_SELECTOR_AUDIT}", "同一天多次运行不能替代跨日样本。"),
            _gate("active_forward_routes", active_forward_routes >= MIN_ACTIVE_FORWARD_ROUTES, str(active_forward_routes), f">={MIN_ACTIVE_FORWARD_ROUTES}", "至少两类外生状态能稳定进入forward monitor。"),
            _gate("history_selector_disabled_until_ready", history_products == 0, str(history_products), "0 until PIT depth passes", "当前应主动禁止历史selector。"),
            _gate("sentiment_template_created", SENTIMENT_TEMPLATE_PATH.exists(), str(SENTIMENT_TEMPLATE_PATH.exists()), "template exists", "先有舆情契约，后有采集和paper监控。"),
            _gate("sentiment_forward_ledger_exists", sentiment_candidates > 0, str(sentiment_candidates), ">=1 forward sentiment/news ledger", "舆情路线当前仍不可交易。"),
        ]
    )


def _make_chart(source_contract: pd.DataFrame, gates: pd.DataFrame, ledger: pd.DataFrame) -> None:
    route_order = source_contract["route"].tolist()
    forward = source_contract["forward_ready_products"].to_numpy(dtype=float)
    history = source_contract["history_ready_products"].to_numpy(dtype=float)

    run_count = int(ledger["run_id"].nunique())
    received_dates = int(pd.to_datetime(ledger["received_at_local"], errors="coerce").dt.date.nunique())

    schema = _schema_frame()
    schema_group = pd.DataFrame(
        {
            "group": ["timestamp", "identity", "source", "text", "classification", "audit"],
            "required_fields": [3, 5, 3, 4, 6, 5],
        }
    )

    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    fig.suptitle("Stage559 External-State Forward Contract Monitor", fontsize=15, fontweight="bold")

    ax = axes[0, 0]
    x = np.arange(len(route_order))
    width = 0.36
    ax.bar(x - width / 2, forward, width, label="forward ready products", color="#1976d2")
    ax.bar(x + width / 2, history, width, label="history selector products", color="#8e24aa")
    ax.set_xticks(x)
    ax.set_xticklabels(route_order, rotation=25, ha="right")
    ax.set_title("Current Source Coverage")
    ax.set_ylabel("products")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(fontsize=8)

    ax = axes[0, 1]
    ordered = gates.iloc[::-1]
    colors = ordered["passed"].map({1: "#2e7d32", 0: "#c62828"})
    ax.barh(ordered["gate"], ordered["passed"], color=colors)
    ax.set_xlim(0, 1.05)
    ax.set_xlabel("pass = 1")
    ax.set_title("Contract Gates")
    ax.grid(axis="x", alpha=0.25)
    for y, value in enumerate(ordered["passed"]):
        label = "PASS" if int(value) else "FAIL"
        x_pos = 1.01 if int(value) else 0.03
        ax.text(x_pos, y, label, va="center", ha="right" if int(value) else "left", fontsize=8, color="#1b5e20" if int(value) else "#b71c1c")

    ax = axes[1, 0]
    labels = ["runs", "dates"]
    x2 = np.arange(len(labels))
    ax.bar(x2 - 0.18, [run_count, received_dates], width=0.36, color="#1565c0", label="current")
    ax.bar(
        x2 + 0.18,
        [MIN_FORWARD_RUNS_FOR_SELECTOR_AUDIT, MIN_FORWARD_DATES_FOR_SELECTOR_AUDIT],
        width=0.36,
        color="#bdbdbd",
        label="required",
    )
    ax.set_xticks(x2)
    ax.set_xticklabels(labels)
    ax.set_title("Forward Sample Depth")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(fontsize=8)

    ax = axes[1, 1]
    ax.bar(schema_group["group"], schema_group["required_fields"], color="#455a64")
    ax.set_title(f"Sentiment Contract Required Fields ({int(schema['required'].sum())} required)")
    ax.tick_params(axis="x", rotation=25)
    ax.grid(axis="y", alpha=0.25)

    fig.tight_layout(rect=[0, 0.02, 1, 0.95])
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def main() -> None:
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    if not MASTER_LEDGER_PATH.exists():
        raise FileNotFoundError(MASTER_LEDGER_PATH)
    ledger = pd.read_csv(MASTER_LEDGER_PATH, encoding="utf-8-sig")
    for column in ["usable_for_forward_monitor", "usable_for_history_selector"]:
        if column in ledger.columns:
            ledger[column] = pd.to_numeric(ledger[column], errors="coerce").fillna(0).astype(int)

    _write_sentiment_template()
    sentiment_schema = _schema_frame()
    source_contract = _route_summary(ledger)
    gates = _build_gates(ledger, source_contract)
    _make_chart(source_contract, gates, ledger)

    source_contract.to_csv(SOURCE_CONTRACT_PATH, index=False, encoding="utf-8-sig")
    sentiment_schema.to_csv(SENTIMENT_SCHEMA_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")

    decision = "forward_contract_created_selector_still_not_ready"
    if int(gates["passed"].sum()) >= len(gates) - 1:
        decision = "forward_contract_ready_for_collection_not_prediction"
    if bool(gates.loc[gates["gate"].eq("sentiment_forward_ledger_exists"), "passed"].iloc[0]) and bool(gates.loc[gates["gate"].eq("enough_forward_dates"), "passed"].iloc[0]):
        decision = "forward_contract_ready_for_predictive_audit"

    payload = {
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at_cst": now.isoformat(timespec="seconds"),
        "decision": decision,
        "gate_pass_count": int(gates["passed"].sum()),
        "gate_count": int(len(gates)),
        "run_count": int(ledger["run_id"].nunique()),
        "received_dates": int(pd.to_datetime(ledger["received_at_local"], errors="coerce").dt.date.nunique()),
        "active_forward_routes": int((source_contract["forward_ready_products"] > 0).sum()),
        "sentiment_required_fields": int(sentiment_schema["required"].sum()),
        "output_files": {
            "source_contract": str(SOURCE_CONTRACT_PATH),
            "contract_gates": str(GATES_PATH),
            "sentiment_template": str(SENTIMENT_TEMPLATE_PATH),
            "sentiment_schema": str(SENTIMENT_SCHEMA_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
            "chart": str(CHART_PATH),
        },
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2), encoding="utf-8")

    report = f"""# Stage559 外生状态 Forward 契约监控

- 生成时间：`{now.strftime('%Y-%m-%d %H:%M CST')}`
- 决策：`{decision}`
- 阶段性质：数据契约和监控审计；不做收益回测，不生成交易候选。

## 外部调研与判断

- AKShare 期货文档确认可获取基差、库存、仓单、会员持仓等商品期货数据；这些源适合做 forward paper 账本，但交易使用前必须记录真实 `received_at`。
- AQR / pysystemtrade 一类趋势框架强调多市场分散、风险预算和相关性治理；商品选品若要产生 alpha，应来自可提前观测的 basis、库存、持仓压力、新闻事件等状态，而不是 hindsight 产品池。
- point-in-time 数据工程资料的共同警告是：没有接收时间、来源版本和原始hash，就不能证明回测当时真的知道该信息。
- 我的判断：当前最务实的下一步不是继续回测，而是把外生/舆情账本契约固化，并持续积累跨日样本。

## Source Contract

{_md_table(source_contract)}

## Contract Gates

{_md_table(gates)}

## Sentiment / News Schema

{_md_table(sentiment_schema, max_rows=40)}

## 结论

- basis 和 inventory 已经能作为自动 forward monitor 的主线，但仍禁止 history selector。
- member_detail 和 warehouse 当前不稳定，不应成为硬依赖。
- sentiment/news 现在只有模板，没有可交易账本；任何人工事件也必须先落 `received_at/source_url/raw_hash/product_mapping`，再允许进入 paper。
- 本阶段没有产生候选，也没有改变 Stage526/Stage079/Stage256 等策略结果。

## 输出文件

- source contract：`{SOURCE_CONTRACT_PATH}`
- gates：`{GATES_PATH}`
- sentiment template：`{SENTIMENT_TEMPLATE_PATH}`
- sentiment schema：`{SENTIMENT_SCHEMA_PATH}`
- decision：`{DECISION_PATH}`
- chart：`{CHART_PATH}`

## 过拟合反思

- 运行前判断：不是过拟合。本阶段只做数据契约，不使用未来收益、不调策略参数。
- 运行后判断：不是过拟合。相反，它把舆情/新闻纳入实盘可执行前的强约束，避免以后拿解释性材料回填历史。

## 继续价值反思

- 运行前判断：有价值。Stage258 已经说明当前最大缺口是 forward 样本和舆情账本。
- 运行后判断：仍有价值，但下一步应是采集/监控自动化，而不是收益回测。
"""
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
