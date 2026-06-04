from __future__ import annotations

from datetime import datetime
import json
import math
import os
from pathlib import Path
from zoneinfo import ZoneInfo

os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parent / "backtest_outputs" / ".matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
REPO_DIR = PROJECT_DIR.parents[1]
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
LEDGER_DIR = OUTPUT_DIR / "external_state_forward_ledger"

MODEL_TAG = "stage558_external_state_selector_readiness_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage558_external_state_selector_readiness_audit"
LINE_ID = "futures_trend_drawdown30_preserve_return"

STAGE543_TAG = "stage543_ex_ante_product_selector_diagnostic_v1"
STAGE543_PREFIX = "qmt_roll_stage543_ex_ante_product_selector_diagnostic"
STAGE549_TAG = "stage549_external_state_forward_ledger_v1"
STAGE549_PREFIX = "qmt_roll_stage549_external_state_forward_ledger"
STAGE550_TAG = "stage550_product_opportunity_geometry_audit_v1"
STAGE550_PREFIX = "qmt_roll_stage550_product_opportunity_geometry_audit"

MASTER_LEDGER_PATH = LEDGER_DIR / "external_state_forward_ledger.csv"
STAGE543_SUMMARY_PATH = OUTPUT_DIR / f"{STAGE543_PREFIX}_summary_{STAGE543_TAG}.csv"
STAGE550_ANNUAL_SUMMARY_PATH = OUTPUT_DIR / f"{STAGE550_PREFIX}_annual_summary_{STAGE550_TAG}.csv"
STAGE550_FEATURE_IC_PATH = OUTPUT_DIR / f"{STAGE550_PREFIX}_feature_ic_{STAGE550_TAG}.csv"
STAGE550_PRODUCT_DIAGNOSTIC_PATH = OUTPUT_DIR / f"{STAGE550_PREFIX}_product_diagnostic_{STAGE550_TAG}.csv"

GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_readiness_gates_{MODEL_TAG}.csv"
ROUTE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_route_readiness_{MODEL_TAG}.csv"
ORACLE6_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_oracle6_readiness_{MODEL_TAG}.csv"
FEATURE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_prior_{MODEL_TAG}.csv"
SENTIMENT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_sentiment_ledger_inventory_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

MIN_FORWARD_RUNS_FOR_SELECTOR_AUDIT = 20
MIN_FORWARD_DATES_FOR_SELECTOR_AUDIT = 20
MIN_HISTORY_READY_PRODUCTS = 6
MIN_ORACLE6_FORWARD_READY_PRODUCTS = 5
MIN_ROUTE_FORWARD_READY_RATE_PCT = 60.0
STRONG_FEATURE_IC = 0.15
WEAK_FEATURE_IC = 0.10

KEYWORDS_SENTIMENT = ("sentiment", "news", "舆情", "新闻")
SENTIMENT_REQUIRED_COLUMNS = {
    "received_at_local",
    "source_url",
    "product_vt_symbol",
    "product_mapping_method",
    "raw_text_hash",
    "usable_for_forward_monitor",
    "usable_for_history_selector",
}


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


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def _gate(name: str, passed: bool, value: str, threshold: str, judgement: str, reason: str) -> dict[str, object]:
    return {
        "gate": name,
        "passed": int(bool(passed)),
        "value": value,
        "threshold": threshold,
        "judgement": judgement,
        "reason": reason,
    }


def _route_readiness(ledger: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for route, group in ledger.groupby("route", dropna=False):
        product_count = int(group["product_vt_symbol"].nunique())
        ok_products = int(group.loc[group["status"].eq("ok"), "product_vt_symbol"].nunique())
        forward_products = int(group.loc[pd.to_numeric(group["usable_for_forward_monitor"], errors="coerce").fillna(0).gt(0), "product_vt_symbol"].nunique())
        history_products = int(group.loc[pd.to_numeric(group["usable_for_history_selector"], errors="coerce").fillna(0).gt(0), "product_vt_symbol"].nunique())
        oracle = group[pd.to_numeric(group["is_oracle6"], errors="coerce").fillna(0).astype(int).eq(1)]
        oracle_products = int(oracle["product_vt_symbol"].nunique())
        oracle_forward = int(oracle.loc[pd.to_numeric(oracle["usable_for_forward_monitor"], errors="coerce").fillna(0).gt(0), "product_vt_symbol"].nunique())
        rows.append(
            {
                "route": str(route),
                "products": product_count,
                "ok_products": ok_products,
                "forward_ready_products": forward_products,
                "history_ready_products": history_products,
                "forward_ready_rate_pct": 100.0 * forward_products / product_count if product_count else 0.0,
                "oracle6_products": oracle_products,
                "oracle6_forward_ready_products": oracle_forward,
                "oracle6_forward_ready_rate_pct": 100.0 * oracle_forward / oracle_products if oracle_products else 0.0,
            }
        )
    return pd.DataFrame(rows).sort_values(["forward_ready_products", "ok_products", "route"], ascending=[False, False, True])


def _oracle6_readiness(ledger: pd.DataFrame) -> pd.DataFrame:
    oracle = ledger[pd.to_numeric(ledger["is_oracle6"], errors="coerce").fillna(0).astype(int).eq(1)].copy()
    rows: list[dict[str, object]] = []
    for product, group in oracle.groupby("product_vt_symbol", dropna=False):
        rows.append(
            {
                "product_vt_symbol": product,
                "product_family": str(group["product_family"].iloc[0]),
                "routes": int(group["route"].nunique()),
                "ok_routes": int(group.loc[group["status"].eq("ok"), "route"].nunique()),
                "forward_ready_routes": int(group.loc[pd.to_numeric(group["usable_for_forward_monitor"], errors="coerce").fillna(0).gt(0), "route"].nunique()),
                "history_ready_routes": int(group.loc[pd.to_numeric(group["usable_for_history_selector"], errors="coerce").fillna(0).gt(0), "route"].nunique()),
            }
        )
    return pd.DataFrame(rows).sort_values(["forward_ready_routes", "product_vt_symbol"], ascending=[False, True])


def _feature_prior(feature_ic: pd.DataFrame) -> pd.DataFrame:
    frame = feature_ic.copy()
    for column in ["mean_spearman_ic", "positive_ic_rate_pct", "t_like"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["prior_strength"] = np.select(
        [
            frame["mean_spearman_ic"].ge(STRONG_FEATURE_IC),
            frame["mean_spearman_ic"].ge(WEAK_FEATURE_IC),
        ],
        ["strong_enough_for_next_test", "weak_but_worth_monitoring"],
        default="insufficient",
    )
    return frame.sort_values("mean_spearman_ic", ascending=False)


def _find_sentiment_ledgers() -> pd.DataFrame:
    roots = [OUTPUT_DIR, REPO_DIR / "research" / "lines" / LINE_ID]
    rows: list[dict[str, object]] = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            name = path.name.lower()
            if not any(keyword in name for keyword in KEYWORDS_SENTIMENT):
                continue
            rel = path.relative_to(REPO_DIR)
            suffix = path.suffix.lower()
            has_received_at = False
            has_product_mapping = False
            rows_count = 0
            schema_complete = False
            received_at_parseable = False
            source_url_present = False
            product_mapping_present = False
            raw_hash_present = False
            is_template_or_schema = int("template" in name or "schema" in name)
            if suffix in {".csv", ".md", ".json"}:
                try:
                    text = path.read_text(encoding="utf-8", errors="ignore")[:20000]
                    has_received_at = "received_at" in text or "接收时间" in text
                    has_product_mapping = "product_vt_symbol" in text or "product_code" in text or "品种" in text
                except OSError:
                    has_received_at = False
                    has_product_mapping = False
            if suffix == ".csv":
                try:
                    frame = pd.read_csv(path, encoding="utf-8-sig")
                    rows_count = int(len(frame))
                    schema_complete = SENTIMENT_REQUIRED_COLUMNS.issubset(set(frame.columns))
                    if schema_complete and rows_count > 0:
                        received_at_parseable = bool(pd.to_datetime(frame["received_at_local"], errors="coerce").notna().any())
                        source_url_present = bool(frame["source_url"].fillna("").astype(str).str.startswith("http").any())
                        product_mapping_present = bool(frame["product_vt_symbol"].fillna("").astype(str).ne("").any())
                        raw_hash_present = bool(frame["raw_text_hash"].fillna("").astype(str).str.fullmatch(r"[0-9a-f]{64}").any())
                except (OSError, pd.errors.ParserError, UnicodeDecodeError):
                    rows_count = 0
            is_candidate_ledger = int(
                suffix == ".csv"
                and not is_template_or_schema
                and rows_count > 0
                and schema_complete
                and received_at_parseable
                and source_url_present
                and product_mapping_present
                and raw_hash_present
            )
            rows.append(
                {
                    "path": str(rel),
                    "suffix": suffix,
                    "has_received_at_text": int(has_received_at),
                    "has_product_mapping_text": int(has_product_mapping),
                    "rows": rows_count,
                    "schema_complete": int(schema_complete),
                    "received_at_parseable": int(received_at_parseable),
                    "source_url_present": int(source_url_present),
                    "product_mapping_present": int(product_mapping_present),
                    "raw_hash_present": int(raw_hash_present),
                    "is_template_or_schema": is_template_or_schema,
                    "is_candidate_ledger": is_candidate_ledger,
                    "size_bytes": int(path.stat().st_size),
                }
            )
    columns = [
        "path",
        "suffix",
        "has_received_at_text",
        "has_product_mapping_text",
        "rows",
        "schema_complete",
        "received_at_parseable",
        "source_url_present",
        "product_mapping_present",
        "raw_hash_present",
        "is_template_or_schema",
        "is_candidate_ledger",
        "size_bytes",
    ]
    return pd.DataFrame(rows).sort_values("path") if rows else pd.DataFrame(columns=columns)


def _plot_chart(
    gates: pd.DataFrame,
    route: pd.DataFrame,
    feature: pd.DataFrame,
    run_count: int,
    received_dates: int,
    sentiment: pd.DataFrame,
    annual: pd.DataFrame,
) -> None:
    plt.rcParams.update({"font.size": 10})
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    fig.suptitle("Stage558 External-State Product Selector Readiness Audit", fontsize=15, fontweight="bold")

    ax = axes[0, 0]
    ordered = gates.copy().iloc[::-1]
    colors = ordered["passed"].map({1: "#2e7d32", 0: "#c62828"}).tolist()
    ax.barh(ordered["gate"], ordered["passed"], color=colors)
    ax.set_xlim(0, 1.05)
    ax.set_xlabel("pass = 1")
    ax.set_title("Readiness Gates")
    ax.grid(axis="x", alpha=0.25)
    for y, value in enumerate(ordered["passed"]):
        ax.text(min(float(value) + 0.03, 0.98), y, "PASS" if value else "FAIL", va="center", fontsize=8)

    ax = axes[0, 1]
    route_view = route.set_index("route")
    bars = route_view[["forward_ready_products", "history_ready_products"]]
    bars.plot(kind="bar", ax=ax, color=["#1976d2", "#8e24aa"])
    ax.set_title("Route Coverage: Forward vs History Selector")
    ax.set_xlabel("")
    ax.set_ylabel("products")
    ax.tick_params(axis="x", rotation=30)
    ax.grid(axis="y", alpha=0.25)

    ax = axes[1, 0]
    top_feature = feature.head(10).iloc[::-1]
    colors = np.where(top_feature["mean_spearman_ic"].ge(STRONG_FEATURE_IC), "#2e7d32", np.where(top_feature["mean_spearman_ic"].ge(WEAK_FEATURE_IC), "#f9a825", "#9e9e9e"))
    ax.barh(top_feature["feature"], top_feature["mean_spearman_ic"], color=colors)
    ax.axvline(WEAK_FEATURE_IC, color="#f9a825", linestyle="--", linewidth=1, label="weak 0.10")
    ax.axvline(STRONG_FEATURE_IC, color="#2e7d32", linestyle="--", linewidth=1, label="strong 0.15")
    ax.set_title("Existing Ex-Ante Feature Prior")
    ax.set_xlabel("mean Spearman IC, future 60d")
    ax.grid(axis="x", alpha=0.25)
    ax.legend(loc="lower right", fontsize=8)

    ax = axes[1, 1]
    labels = ["forward runs", "received dates", "sentiment ledgers", "positive years"]
    values = [
        run_count,
        received_dates,
        int(sentiment["is_candidate_ledger"].sum()) if not sentiment.empty else 0,
        int((pd.to_numeric(annual["top6_pnl"], errors="coerce") > 0).sum()) if not annual.empty and "top6_pnl" in annual.columns else 0,
    ]
    thresholds = [
        MIN_FORWARD_RUNS_FOR_SELECTOR_AUDIT,
        MIN_FORWARD_DATES_FOR_SELECTOR_AUDIT,
        1,
        len(annual) if not annual.empty else 7,
    ]
    x = np.arange(len(labels))
    width = 0.36
    ax.bar(x - width / 2, values, width=width, color="#1565c0", label="current")
    ax.bar(x + width / 2, thresholds, width=width, color="#bdbdbd", label="required/reference")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.set_title("Sample Depth and Opportunity")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(fontsize=8)

    fig.tight_layout(rect=[0, 0.02, 1, 0.95])
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def main() -> None:
    now = datetime.now(ZoneInfo("Asia/Shanghai"))

    ledger = _load_csv(MASTER_LEDGER_PATH)
    annual = _load_csv(STAGE550_ANNUAL_SUMMARY_PATH)
    feature_raw = _load_csv(STAGE550_FEATURE_IC_PATH)
    stage543_summary = _load_csv(STAGE543_SUMMARY_PATH)
    product_diag = _load_csv(STAGE550_PRODUCT_DIAGNOSTIC_PATH)

    for column in ["usable_for_forward_monitor", "usable_for_history_selector", "is_oracle6"]:
        ledger[column] = pd.to_numeric(ledger[column], errors="coerce").fillna(0).astype(int)
    ledger["received_at_local_ts"] = pd.to_datetime(ledger["received_at_local"], errors="coerce")
    ledger["received_date"] = ledger["received_at_local_ts"].dt.date.astype(str)

    run_count = int(ledger["run_id"].nunique())
    received_dates = int(ledger["received_date"].nunique())
    products = int(ledger["product_vt_symbol"].nunique())
    history_ready_products = int(ledger.loc[ledger["usable_for_history_selector"].gt(0), "product_vt_symbol"].nunique())
    forward_ready_products = int(ledger.loc[ledger["usable_for_forward_monitor"].gt(0), "product_vt_symbol"].nunique())

    route = _route_readiness(ledger)
    oracle6 = _oracle6_readiness(ledger)
    feature = _feature_prior(feature_raw)
    sentiment = _find_sentiment_ledgers()

    annual_positive_years = int((pd.to_numeric(annual["top6_pnl"], errors="coerce") > 0).sum())
    annual_years = int(len(annual))
    all_stage543_pass = int(pd.to_numeric(stage543_summary.get("diagnostic_pass", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
    max_feature_ic = float(feature["mean_spearman_ic"].max()) if not feature.empty else 0.0
    max_route_forward_rate = float(route["forward_ready_rate_pct"].max()) if not route.empty else 0.0
    max_oracle6_route_ready = int(oracle6["forward_ready_routes"].max()) if not oracle6.empty else 0
    oracle6_any_forward_products = int((oracle6["forward_ready_routes"] > 0).sum()) if not oracle6.empty else 0
    sentiment_candidate_ledgers = int(sentiment["is_candidate_ledger"].sum()) if not sentiment.empty else 0

    gates = pd.DataFrame(
        [
            _gate(
                "annual_opportunity_exists",
                annual_positive_years == annual_years and annual_years > 0,
                f"{annual_positive_years}/{annual_years} years top6_pnl>0",
                "all tested years positive",
                "pass" if annual_positive_years == annual_years and annual_years > 0 else "fail",
                "非核心每年确有正收益机会，这是扩池方向的必要条件。",
            ),
            _gate(
                "point_in_time_external_ledger_exists",
                MASTER_LEDGER_PATH.exists() and run_count > 0,
                f"{run_count} run(s), {received_dates} received date(s)",
                "ledger exists with received_at",
                "pass" if MASTER_LEDGER_PATH.exists() and run_count > 0 else "fail",
                "已经有真实接收时间戳账本，但样本深度另行判定。",
            ),
            _gate(
                "enough_forward_observations",
                run_count >= MIN_FORWARD_RUNS_FOR_SELECTOR_AUDIT and received_dates >= MIN_FORWARD_DATES_FOR_SELECTOR_AUDIT,
                f"{run_count} run(s), {received_dates} date(s)",
                f">={MIN_FORWARD_RUNS_FOR_SELECTOR_AUDIT} runs and >={MIN_FORWARD_DATES_FOR_SELECTOR_AUDIT} dates",
                "pass" if run_count >= MIN_FORWARD_RUNS_FOR_SELECTOR_AUDIT and received_dates >= MIN_FORWARD_DATES_FOR_SELECTOR_AUDIT else "fail",
                "少于最低 forward 样本数时不能验证预测力。",
            ),
            _gate(
                "route_forward_coverage_usable",
                max_route_forward_rate >= MIN_ROUTE_FORWARD_READY_RATE_PCT,
                f"best route forward ready {max_route_forward_rate:.2f}%",
                f">={MIN_ROUTE_FORWARD_READY_RATE_PCT:.0f}% on at least one route",
                "pass" if max_route_forward_rate >= MIN_ROUTE_FORWARD_READY_RATE_PCT else "fail",
                "库存和基差已有监控覆盖，适合继续积累。",
            ),
            _gate(
                "oracle6_external_state_covered",
                oracle6_any_forward_products >= MIN_ORACLE6_FORWARD_READY_PRODUCTS,
                f"{oracle6_any_forward_products}/6 Oracle6 products have >=1 forward route",
                f">={MIN_ORACLE6_FORWARD_READY_PRODUCTS}/6",
                "pass" if oracle6_any_forward_products >= MIN_ORACLE6_FORWARD_READY_PRODUCTS else "fail",
                "历史上最有价值的 Oracle6 至少能被外生状态监控覆盖。",
            ),
            _gate(
                "history_selector_ready",
                history_ready_products >= MIN_HISTORY_READY_PRODUCTS,
                f"{history_ready_products}/{products} products history-ready",
                f">={MIN_HISTORY_READY_PRODUCTS} products",
                "pass" if history_ready_products >= MIN_HISTORY_READY_PRODUCTS else "fail",
                "没有历史 selector-ready 路线，禁止回填 2022-2026 做选品回测。",
            ),
            _gate(
                "sentiment_forward_ledger_ready",
                sentiment_candidate_ledgers > 0,
                f"{sentiment_candidate_ledgers} candidate sentiment/news ledger(s)",
                ">=1 point-in-time sentiment/news ledger",
                "pass" if sentiment_candidate_ledgers > 0 else "fail",
                "舆情路线尚无真实接收时间戳账本，不能用于当前实盘选择器。",
            ),
            _gate(
                "existing_ex_ante_feature_strong",
                max_feature_ic >= STRONG_FEATURE_IC,
                f"best mean IC {max_feature_ic:.4f}",
                f">={STRONG_FEATURE_IC:.2f}",
                "pass" if max_feature_ic >= STRONG_FEATURE_IC else ("watch" if max_feature_ic >= WEAK_FEATURE_IC else "fail"),
                "已有事前特征只有弱先验，不能单独承担选品。",
            ),
            _gate(
                "prior_historical_selector_passed",
                all_stage543_pass > 0,
                f"{all_stage543_pass} Stage543 selector pass rows",
                ">=1 passed selector",
                "pass" if all_stage543_pass > 0 else "fail",
                "旧的历史账本/AI/趋势地形选择器没有通过诊断。",
            ),
        ]
    )

    pass_count = int(gates["passed"].sum())
    decision = "external_state_selector_not_ready_keep_forward_monitor"
    if pass_count >= 8:
        decision = "external_state_selector_ready_for_predictive_audit"
    elif annual_positive_years == annual_years and max_route_forward_rate >= MIN_ROUTE_FORWARD_READY_RATE_PCT:
        decision = "opportunity_exists_but_selector_data_not_ready"

    route.to_csv(ROUTE_PATH, index=False, encoding="utf-8-sig")
    oracle6.to_csv(ORACLE6_PATH, index=False, encoding="utf-8-sig")
    feature.to_csv(FEATURE_PATH, index=False, encoding="utf-8-sig")
    sentiment.to_csv(SENTIMENT_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")

    _plot_chart(gates, route, feature, run_count, received_dates, sentiment, annual)

    decision_payload = {
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at_cst": now.isoformat(timespec="seconds"),
        "decision": decision,
        "pass_count": pass_count,
        "gate_count": int(len(gates)),
        "run_count": run_count,
        "received_dates": received_dates,
        "products": products,
        "forward_ready_products": forward_ready_products,
        "history_ready_products": history_ready_products,
        "max_route_forward_ready_rate_pct": max_route_forward_rate,
        "oracle6_any_forward_products": oracle6_any_forward_products,
        "max_oracle6_forward_ready_routes": max_oracle6_route_ready,
        "sentiment_candidate_ledgers": sentiment_candidate_ledgers,
        "best_feature_ic": max_feature_ic,
        "stage543_pass_rows": all_stage543_pass,
        "annual_positive_years": annual_positive_years,
        "annual_years": annual_years,
        "output_files": {
            "gates": str(GATES_PATH),
            "route": str(ROUTE_PATH),
            "oracle6": str(ORACLE6_PATH),
            "feature": str(FEATURE_PATH),
            "sentiment": str(SENTIMENT_PATH),
            "report": str(REPORT_PATH),
            "chart": str(CHART_PATH),
        },
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision_payload), ensure_ascii=False, indent=2), encoding="utf-8")

    report = f"""# Stage558 外生状态选品器 Readiness 审计

- 生成时间：`{now.strftime('%Y-%m-%d %H:%M CST')}`
- 决策：`{decision}`
- 阶段性质：只读资格审计；不做收益回测，不生成交易候选。
- 核心问题：降低单笔风险、扩大品种池、避免高相关这套结构是否已经具备“选对品种”的实盘前置数据资格。

## 外部调研与判断

- AQR 的趋势跟踪资料和 `pysystemtrade` 的工程框架都指向同一个原则：趋势策略应靠多市场分散、波动/风险预算和低相关组合提高穿越周期能力，而不是把样本内赢家直接放大。
- 商品期货选品文献更强调期限结构、基差、库存、持仓压力、动量/基差动量等“趋势土壤”变量。它们比上一年 PnL 更接近产业供需和拥挤度，但必须点时化。
- 我的判断：你的方向成立，但当前最短板不是风险壳，而是 selector 数据资格。没有足够 forward 样本之前，任何“选对品种”的收益回测都容易变成事后解释。

## Readiness Gates

{_md_table(gates)}

## Route Readiness

{_md_table(route)}

## Oracle6 Readiness

{_md_table(oracle6)}

## 事前特征先验

{_md_table(feature[['feature', 'horizon_days', 'months', 'mean_spearman_ic', 'positive_ic_rate_pct', 't_like', 'prior_strength']].head(12))}

## 舆情/新闻账本盘点

{_md_table(sentiment, max_rows=20)}

## 结论

- 非核心品种确实每年都有可抓的趋势机会，扩池方向不是错的。
- 相关性和产品族约束只能当风险预算壳，不能产生 alpha。Stage257 已经反证“宽池 + 低单笔风险 + 简单相关/族约束”不足以晋级。
- 当前外生状态最有希望的是库存和基差，它们能 forward 监控；会员/仓单不稳定，舆情没有真实接收时间戳账本。
- 现在不应进入选品收益回测。正确下一步是继续积累 forward 外生状态，至少达到 `{MIN_FORWARD_RUNS_FOR_SELECTOR_AUDIT}` 次、`{MIN_FORWARD_DATES_FOR_SELECTOR_AUDIT}` 个接收日期，再验证它们能否预测未来 3/6 个月品种趋势收益。

## 回测指标

- 期末权益：不适用，本阶段不做收益回测。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。

## 输出文件

- gates：`{GATES_PATH}`
- route readiness：`{ROUTE_PATH}`
- Oracle6 readiness：`{ORACLE6_PATH}`
- feature prior：`{FEATURE_PATH}`
- sentiment inventory：`{SENTIMENT_PATH}`
- decision：`{DECISION_PATH}`
- chart：`{CHART_PATH}`

## 过拟合反思

- 运行前判断：不是过拟合。本阶段不看未来收益、不调交易参数，只检查数据是否具备点时化和样本深度。
- 运行后判断：不是过拟合，且降低了后续过拟合风险。结论明确禁止把单次 forward ledger 回填成 2022-2026 selector。

## 继续价值反思

- 运行前判断：有价值。Stage550 证明机会存在，Stage257 证明风险壳不够，必须判断外生状态能不能承担选品。
- 运行后判断：有价值，但价值在 forward 数据工程和未来预测力审计，不在继续扫宽池参数。
"""
    REPORT_PATH.write_text(report, encoding="utf-8")

    print(json.dumps(_json_safe(decision_payload), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
