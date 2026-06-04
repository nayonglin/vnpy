from __future__ import annotations

from datetime import date, datetime, timedelta
import json
import math
import os
from pathlib import Path
from zoneinfo import ZoneInfo

Path("/private/tmp/vnpy_mplconfig").mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/vnpy_mplconfig")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
LEDGER_DIR = OUTPUT_DIR / "external_state_forward_ledger"

LINE_ID = "futures_trend_drawdown30_preserve_return"
MODEL_TAG = "stage560_forward_collection_run_gate_v1"
OUTPUT_PREFIX = "qmt_roll_stage560_forward_collection_run_gate"

MASTER_LEDGER_PATH = LEDGER_DIR / "external_state_forward_ledger.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
COLLECTION_GATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_collection_gate_{MODEL_TAG}.csv"
ROUTE_HEALTH_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_route_latest_health_{MODEL_TAG}.csv"
DATE_PROGRESS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_date_progress_{MODEL_TAG}.csv"
RUN_QUALITY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_run_quality_{MODEL_TAG}.csv"
RUNBOOK_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_runbook_{MODEL_TAG}.md"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

MIN_FORWARD_RUNS_FOR_SELECTOR_AUDIT = 20
MIN_FORWARD_DATES_FOR_SELECTOR_AUDIT = 20
MIN_ACTIVE_FORWARD_ROUTES = 2
MIN_FORWARD_READY_PRODUCTS_PER_ROUTE = 20
LOCAL_TZ = ZoneInfo("Asia/Shanghai")

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
    "usable_for_forward_monitor",
    "usable_for_history_selector",
    "data_value_json",
    "raw_sha256",
    "point_in_time_rule",
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
    if isinstance(value, (pd.Timestamp, datetime, date)):
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


def _gate(name: str, passed: bool, current, required, note: str) -> dict:
    return {
        "gate": name,
        "passed": bool(passed),
        "current": current,
        "required": required,
        "note": note,
    }


def _load_ledger() -> tuple[pd.DataFrame, list[str]]:
    missing: list[str] = []
    if not MASTER_LEDGER_PATH.exists():
        return pd.DataFrame(), CORE_LEDGER_COLUMNS.copy()
    ledger = pd.read_csv(MASTER_LEDGER_PATH, encoding="utf-8-sig")
    missing = [column for column in CORE_LEDGER_COLUMNS if column not in ledger.columns]
    if "received_at_local" in ledger.columns:
        ledger["received_at_local_ts"] = pd.to_datetime(ledger["received_at_local"], errors="coerce")
        ledger["received_date"] = ledger["received_at_local_ts"].dt.date.astype(str)
    else:
        ledger["received_at_local_ts"] = pd.NaT
        ledger["received_date"] = ""
    for column in ["usable_for_forward_monitor", "usable_for_history_selector"]:
        if column in ledger.columns:
            ledger[column] = pd.to_numeric(ledger[column], errors="coerce").fillna(0).astype(int)
    return ledger, missing


def _sentiment_files() -> tuple[list[Path], list[Path]]:
    templates = sorted(LEDGER_DIR.glob("sentiment_news_forward_ledger_template_*.csv"))
    candidates = sorted(LEDGER_DIR.glob("sentiment_news_forward_ledger*.csv"))
    real_ledgers = [
        path
        for path in candidates
        if "template" not in path.name and path.stat().st_size > 0
    ]
    return templates, real_ledgers


def _route_health(ledger: pd.DataFrame) -> pd.DataFrame:
    if ledger.empty or "route" not in ledger.columns:
        return pd.DataFrame(
            columns=[
                "route",
                "rows",
                "products",
                "ok_products",
                "forward_ready_products",
                "history_ready_products",
                "latest_received_date",
                "latest_rows",
                "latest_ok_products",
                "latest_forward_ready_products",
                "latest_history_ready_products",
                "raw_hash_ok_rate",
            ]
        )
    rows = []
    for route, group in ledger.groupby("route", dropna=False):
        route_text = str(route)
        latest_date = group["received_date"].dropna().max() if "received_date" in group.columns else ""
        latest = group[group["received_date"] == latest_date].copy() if latest_date else group.iloc[0:0].copy()
        ok = group[group.get("status", "") == "ok"] if "status" in group.columns else group.iloc[0:0]
        latest_ok = latest[latest.get("status", "") == "ok"] if "status" in latest.columns else latest.iloc[0:0]
        raw_ok = (
            ok["raw_sha256"].fillna("").astype(str).str.len().gt(0).mean()
            if not ok.empty and "raw_sha256" in ok.columns
            else 0.0
        )
        rows.append(
            {
                "route": route_text,
                "rows": int(len(group)),
                "products": int(group["product_vt_symbol"].nunique()) if "product_vt_symbol" in group.columns else 0,
                "ok_products": int(ok["product_vt_symbol"].nunique()) if "product_vt_symbol" in ok.columns else 0,
                "forward_ready_products": int(
                    group.loc[group["usable_for_forward_monitor"] == 1, "product_vt_symbol"].nunique()
                )
                if "product_vt_symbol" in group.columns and "usable_for_forward_monitor" in group.columns
                else 0,
                "history_ready_products": int(
                    group.loc[group["usable_for_history_selector"] == 1, "product_vt_symbol"].nunique()
                )
                if "product_vt_symbol" in group.columns and "usable_for_history_selector" in group.columns
                else 0,
                "latest_received_date": latest_date,
                "latest_rows": int(len(latest)),
                "latest_ok_products": int(latest_ok["product_vt_symbol"].nunique())
                if "product_vt_symbol" in latest_ok.columns
                else 0,
                "latest_forward_ready_products": int(
                    latest.loc[latest["usable_for_forward_monitor"] == 1, "product_vt_symbol"].nunique()
                )
                if "product_vt_symbol" in latest.columns and "usable_for_forward_monitor" in latest.columns
                else 0,
                "latest_history_ready_products": int(
                    latest.loc[latest["usable_for_history_selector"] == 1, "product_vt_symbol"].nunique()
                )
                if "product_vt_symbol" in latest.columns and "usable_for_history_selector" in latest.columns
                else 0,
                "raw_hash_ok_rate": float(raw_ok),
            }
        )
    return pd.DataFrame(rows).sort_values("route").reset_index(drop=True)


def _date_progress(ledger: pd.DataFrame) -> pd.DataFrame:
    if ledger.empty or "received_date" not in ledger.columns:
        return pd.DataFrame(columns=["received_date", "run_count", "row_count", "route_count", "ok_rows"])
    progress = (
        ledger.groupby("received_date", dropna=False)
        .agg(
            run_count=("run_id", "nunique"),
            row_count=("run_id", "size"),
            route_count=("route", "nunique"),
            ok_rows=("status", lambda item: int((item == "ok").sum())),
        )
        .reset_index()
        .sort_values("received_date")
    )
    return progress


def _run_quality(ledger: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "run_id",
        "received_date",
        "rows",
        "ok_rows",
        "active_forward_routes",
        "qualified_for_selector_depth",
        "route_ready_detail",
    ]
    if ledger.empty or "run_id" not in ledger.columns:
        return pd.DataFrame(columns=columns)
    rows = []
    for (run_id, received_date), group in ledger.groupby(["run_id", "received_date"], dropna=False):
        route_parts = []
        active_routes = 0
        for route, route_group in group.groupby("route", dropna=False):
            ready_products = int(
                route_group.loc[
                    route_group["usable_for_forward_monitor"] == 1,
                    "product_vt_symbol",
                ].nunique()
            )
            if ready_products >= MIN_FORWARD_READY_PRODUCTS_PER_ROUTE:
                active_routes += 1
            route_parts.append(f"{route}:{ready_products}")
        qualified = active_routes >= MIN_ACTIVE_FORWARD_ROUTES
        rows.append(
            {
                "run_id": str(run_id),
                "received_date": str(received_date),
                "rows": int(len(group)),
                "ok_rows": int(group["status"].eq("ok").sum()) if "status" in group.columns else 0,
                "active_forward_routes": active_routes,
                "qualified_for_selector_depth": int(qualified),
                "route_ready_detail": ";".join(sorted(route_parts)),
            }
        )
    return pd.DataFrame(rows, columns=columns).sort_values(["received_date", "run_id"]).reset_index(drop=True)


def _write_chart(
    decision: dict,
    route_health: pd.DataFrame,
    gates: pd.DataFrame,
    date_progress: pd.DataFrame,
) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "PingFang SC", "Heiti TC", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    fig.suptitle("Stage560 Forward采集运行闸门", fontsize=18, fontweight="bold")

    ax = axes[0, 0]
    progress_values = [
        decision["sample_depth"]["forward_runs"],
        decision["sample_depth"]["forward_dates"],
    ]
    targets = [
        MIN_FORWARD_RUNS_FOR_SELECTOR_AUDIT,
        MIN_FORWARD_DATES_FOR_SELECTOR_AUDIT,
    ]
    labels = ["runs", "dates"]
    x = np.arange(len(labels))
    ax.bar(x - 0.18, progress_values, width=0.36, label="current", color="#4C78A8")
    ax.bar(x + 0.18, targets, width=0.36, label="required", color="#E0E0E0", edgecolor="#555555")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("count")
    ax.set_title("跨日样本进度")
    ax.legend(loc="upper left")
    for i, value in enumerate(progress_values):
        ax.text(i - 0.18, value + 0.25, f"{value}", ha="center", va="bottom", fontsize=11)
    for i, value in enumerate(targets):
        ax.text(i + 0.18, value + 0.25, f"{value}", ha="center", va="bottom", fontsize=11)
    ax.set_ylim(0, max(targets) * 1.25)

    ax = axes[0, 1]
    if route_health.empty:
        ax.text(0.5, 0.5, "无route数据", ha="center", va="center", fontsize=14)
        ax.axis("off")
    else:
        plot = route_health.sort_values("latest_forward_ready_products", ascending=True)
        y = np.arange(len(plot))
        ax.barh(y - 0.18, plot["latest_forward_ready_products"], height=0.36, label="forward", color="#59A14F")
        ax.barh(y + 0.18, plot["latest_history_ready_products"], height=0.36, label="history", color="#B07AA1")
        ax.set_yticks(y)
        ax.set_yticklabels(plot["route"])
        ax.set_xlabel("products")
        ax.set_title("最新route健康度")
        ax.legend(loc="lower right")
        for yi, value in enumerate(plot["latest_forward_ready_products"]):
            ax.text(value + 0.25, yi - 0.18, str(int(value)), va="center", fontsize=10)
        for yi, value in enumerate(plot["latest_history_ready_products"]):
            ax.text(value + 0.25, yi + 0.18, str(int(value)), va="center", fontsize=10)
        ax.set_xlim(0, max(1, int(plot["latest_forward_ready_products"].max()) + 8))

    ax = axes[1, 0]
    gate_plot = gates.copy()
    gate_plot["score"] = gate_plot["passed"].map({True: 1, False: 0})
    colors = gate_plot["passed"].map({True: "#59A14F", False: "#E15759"}).tolist()
    y = np.arange(len(gate_plot))
    ax.barh(y, gate_plot["score"], color=colors)
    ax.set_yticks(y)
    ax.set_yticklabels(gate_plot["gate"])
    ax.set_xlim(0, 1.2)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["FAIL", "PASS"])
    ax.set_title("运行闸门")
    for yi, (_, row) in enumerate(gate_plot.iterrows()):
        ax.text(1.03 if row["passed"] else 0.03, yi, "PASS" if row["passed"] else "FAIL", va="center", fontsize=10)

    ax = axes[1, 1]
    ax.axis("off")
    action_short = (
        "same-day skip; smoke only"
        if decision["recommended_action"] == "skip_same_day_for_selector_depth_allow_operator_smoke_only"
        else "collect new distinct day"
    )
    action_lines = [
        f"today: {decision['clock']['today_local']}",
        f"latest ledger date: {decision['clock']['latest_received_date']}",
        f"next eligible date: {decision['clock']['next_eligible_collection_date']}",
        f"action: {action_short}",
        f"qualified runs: {decision['sample_depth']['qualified_forward_runs']}",
        f"remaining dates: {decision['sample_depth']['remaining_forward_dates']}",
        f"sentiment ledger: {decision['sentiment']['real_ledger_count']}",
    ]
    ax.text(
        0.02,
        0.92,
        "\n".join(action_lines),
        ha="left",
        va="top",
        fontsize=13,
        family="monospace",
        bbox={"boxstyle": "round,pad=0.5", "facecolor": "#F7F7F7", "edgecolor": "#CCCCCC"},
    )
    if not date_progress.empty:
        duplicate_dates = date_progress.loc[date_progress["run_count"] > 1, "received_date"].tolist()
        dup_text = "duplicate dates: " + (", ".join(duplicate_dates) if duplicate_dates else "none")
        ax.text(0.02, 0.25, dup_text, ha="left", va="top", fontsize=12)

    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def main() -> None:
    now = datetime.now(LOCAL_TZ)
    today = now.date()
    ledger, missing_columns = _load_ledger()
    route_health = _route_health(ledger)
    date_progress = _date_progress(ledger)
    run_quality = _run_quality(ledger)
    sentiment_templates, sentiment_ledgers = _sentiment_files()

    raw_forward_runs = int(ledger["run_id"].nunique()) if not ledger.empty and "run_id" in ledger.columns else 0
    raw_forward_dates = int(ledger["received_date"].nunique()) if not ledger.empty and "received_date" in ledger.columns else 0
    qualified_by_date = (
        run_quality.loc[run_quality["qualified_for_selector_depth"].eq(1)]
        .drop_duplicates("received_date", keep="first")
        if not run_quality.empty
        else pd.DataFrame()
    )
    qualified_runs = int(len(qualified_by_date))
    qualified_dates = int(qualified_by_date["received_date"].nunique()) if not qualified_by_date.empty else 0
    extra_qualified_same_day_runs = (
        int(run_quality.loc[run_quality["qualified_for_selector_depth"].eq(1)].shape[0] - qualified_runs)
        if not run_quality.empty
        else 0
    )
    latest_received_date_text = (
        str(ledger["received_date"].dropna().max()) if not ledger.empty and "received_date" in ledger.columns else ""
    )
    latest_received_date = (
        datetime.strptime(latest_received_date_text, "%Y-%m-%d").date()
        if latest_received_date_text
        else None
    )
    next_eligible_date = (
        max(today, latest_received_date + timedelta(days=1)) if latest_received_date is not None else today
    )
    new_calendar_date_available = latest_received_date is None or today > latest_received_date
    same_day_run_count = (
        int(ledger.loc[ledger["received_date"] == today.isoformat(), "run_id"].nunique())
        if not ledger.empty and "received_date" in ledger.columns and "run_id" in ledger.columns
        else 0
    )
    duplicate_date_count = int((date_progress["run_count"] > 1).sum()) if not date_progress.empty else 0
    active_forward_routes = int((route_health["latest_forward_ready_products"] > 0).sum()) if not route_health.empty else 0
    history_ready_products = int(route_health["latest_history_ready_products"].sum()) if not route_health.empty else 0
    sample_depth_increment_allowed = bool(new_calendar_date_available)
    recommended_action = (
        "run_stage549_collect_new_distinct_date"
        if sample_depth_increment_allowed
        else "skip_same_day_for_selector_depth_allow_operator_smoke_only"
    )

    gates = pd.DataFrame(
        [
            _gate("master_ledger_exists", MASTER_LEDGER_PATH.exists(), int(MASTER_LEDGER_PATH.exists()), 1, str(MASTER_LEDGER_PATH)),
            _gate("core_schema_ok", not missing_columns, len(CORE_LEDGER_COLUMNS) - len(missing_columns), len(CORE_LEDGER_COLUMNS), ",".join(missing_columns)),
            _gate("new_calendar_date_available", new_calendar_date_available, today.isoformat(), f">{latest_received_date_text}", "same-date run must not increment selector sample depth"),
            _gate("same_day_duplicate_policy_ok", not sample_depth_increment_allowed and same_day_run_count >= 1 or sample_depth_increment_allowed, recommended_action, "skip/smoke on same day", "policy blocks counting same-day reruns"),
            _gate("enough_forward_runs", qualified_runs >= MIN_FORWARD_RUNS_FOR_SELECTOR_AUDIT, qualified_runs, MIN_FORWARD_RUNS_FOR_SELECTOR_AUDIT, "selector audit requires qualified forward runs, not failed/smoke runs"),
            _gate("enough_forward_dates", qualified_dates >= MIN_FORWARD_DATES_FOR_SELECTOR_AUDIT, qualified_dates, MIN_FORWARD_DATES_FOR_SELECTOR_AUDIT, "selector audit requires qualified cross-day observations"),
            _gate("minimum_active_forward_routes", active_forward_routes >= MIN_ACTIVE_FORWARD_ROUTES, active_forward_routes, MIN_ACTIVE_FORWARD_ROUTES, "basis/inventory are the current active routes"),
            _gate("history_selector_still_disabled", history_ready_products == 0, history_ready_products, 0, "forward ledger is not history selector data yet"),
            _gate("sentiment_template_exists", len(sentiment_templates) >= 1, len(sentiment_templates), 1, "template is schema only"),
            _gate("sentiment_real_ledger_exists", len(sentiment_ledgers) >= 1, len(sentiment_ledgers), 1, "real sentiment/news ledger is required before predictive audit"),
        ]
    )
    ready_for_predictive_audit = bool(
        qualified_runs >= MIN_FORWARD_RUNS_FOR_SELECTOR_AUDIT
        and qualified_dates >= MIN_FORWARD_DATES_FOR_SELECTOR_AUDIT
        and active_forward_routes >= MIN_ACTIVE_FORWARD_ROUTES
        and len(sentiment_ledgers) >= 1
        and history_ready_products == 0
    )
    gates = pd.concat(
        [
            gates,
            pd.DataFrame(
                [
                    _gate(
                        "ready_for_predictive_audit",
                        ready_for_predictive_audit,
                        "yes" if ready_for_predictive_audit else "no",
                        "yes",
                        "only then test fixed 3m/6m selector predictive power",
                    )
                ]
            ),
        ],
        ignore_index=True,
    )

    decision = {
        "decision": "same_day_collection_not_counted_selector_still_not_ready"
        if not ready_for_predictive_audit
        else "selector_predictive_audit_ready",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "created_at_local": now.isoformat(),
        "recommended_action": recommended_action,
        "sample_depth_increment_allowed": sample_depth_increment_allowed,
        "clock": {
            "today_local": today.isoformat(),
            "latest_received_date": latest_received_date_text,
            "next_eligible_collection_date": next_eligible_date.isoformat(),
            "same_day_run_count": same_day_run_count,
            "duplicate_date_count": duplicate_date_count,
        },
        "sample_depth": {
            "forward_runs": qualified_runs,
            "forward_dates": qualified_dates,
            "qualified_forward_runs": qualified_runs,
            "qualified_forward_dates": qualified_dates,
            "raw_forward_runs": raw_forward_runs,
            "raw_forward_dates": raw_forward_dates,
            "extra_qualified_same_day_runs": extra_qualified_same_day_runs,
            "required_forward_runs": MIN_FORWARD_RUNS_FOR_SELECTOR_AUDIT,
            "required_forward_dates": MIN_FORWARD_DATES_FOR_SELECTOR_AUDIT,
            "remaining_forward_runs": max(0, MIN_FORWARD_RUNS_FOR_SELECTOR_AUDIT - qualified_runs),
            "remaining_forward_dates": max(0, MIN_FORWARD_DATES_FOR_SELECTOR_AUDIT - qualified_dates),
        },
        "route_health": {
            "active_forward_routes": active_forward_routes,
            "minimum_active_forward_routes": MIN_ACTIVE_FORWARD_ROUTES,
            "history_ready_products": history_ready_products,
        },
        "sentiment": {
            "template_count": len(sentiment_templates),
            "real_ledger_count": len(sentiment_ledgers),
            "template_files": [str(path) for path in sentiment_templates],
            "real_ledger_files": [str(path) for path in sentiment_ledgers],
        },
        "outputs": {
            "decision": str(DECISION_PATH),
            "collection_gate": str(COLLECTION_GATE_PATH),
            "route_health": str(ROUTE_HEALTH_PATH),
            "date_progress": str(DATE_PROGRESS_PATH),
            "run_quality": str(RUN_QUALITY_PATH),
            "runbook": str(RUNBOOK_PATH),
            "report": str(REPORT_PATH),
            "chart": str(CHART_PATH),
        },
    }

    runbook = f"""# Stage560 Forward采集运行闸门 Runbook

## 当前动作

- 推荐动作：`{recommended_action}`
- 今日日期：`{today.isoformat()}`
- 最新账本日期：`{latest_received_date_text}`
- 下一次可计入 selector 样本深度的日期：`{next_eligible_date.isoformat()}`
- 同日重复运行策略：允许作为 operator smoke / 源修复验证，但不得增加 `20` 个跨日样本计数。

## 执行纪律

1. 每个自然日最多只有一次合格落盘可计入 selector 样本深度；合格定义为同一 `run_id` 至少 `{MIN_ACTIVE_FORWARD_ROUTES}` 条 route 各自覆盖 `>={MIN_FORWARD_READY_PRODUCTS_PER_ROUTE}` 个 forward-ready 产品。
2. 当天重复跑 Stage549，只能记录为 smoke、修源或覆盖率排查，不能触发新的收益回测。
3. 舆情/新闻必须使用 Stage559 模板，写入 `received_at/source_url/published_at/raw_text_hash/product_mapping/status`。
4. 未满足 `20` runs、`20` dates、真实 sentiment ledger 前，不允许做新的历史 selector 收益回测。

## 下一步

- 若今天是最新账本同一天：等待下一自然日或下一次真实采集窗口。
- 若已经到下一自然日：运行 Stage549 追加账本，再运行 Stage559/Stage560 复核样本深度和契约。
"""

    report = f"""# Stage560 Forward采集运行闸门

- line_id：`{LINE_ID}`
- 生成时间：`{now.strftime('%Y-%m-%d %H:%M:%S %Z')}`
- 阶段性质：外生状态采集运行闸门；不做收益回测，不生成交易候选。
- 决策：`{decision['decision']}`
- 推荐动作：`{recommended_action}`

## 核心结论

- 当前 forward ledger 原始计数为 `{raw_forward_runs}` 个 run、`{raw_forward_dates}` 个 received date；按质量闸门计数只有 `{qualified_runs}` 个合格 run、`{qualified_dates}` 个合格 received date，距离 selector 预测力审计要求 `{MIN_FORWARD_RUNS_FOR_SELECTOR_AUDIT}` / `{MIN_FORWARD_DATES_FOR_SELECTOR_AUDIT}` 仍差 `{decision['sample_depth']['remaining_forward_runs']}` / `{decision['sample_depth']['remaining_forward_dates']}`。
- 最新账本日期是 `{latest_received_date_text}`，当前日期是 `{today.isoformat()}`。如果同日重复运行，只能算 operator smoke 或源修复验证，不能让 selector 样本数加一。
- 当前 active forward route 为 `{active_forward_routes}`，basis/inventory 仍是可用主线；history selector ready 产品为 `{history_ready_products}`，所以外生账本仍不能回填历史选品。
- sentiment template 数为 `{len(sentiment_templates)}`，真实 sentiment/news ledger 数为 `{len(sentiment_ledgers)}`。舆情/新闻仍未具备预测力审计资格。

## 闸门

{_md_table(gates)}

## Route健康度

{_md_table(route_health)}

## 日期进度

{_md_table(date_progress)}

## Run质量

{_md_table(run_quality)}

## 过拟合反思

- 运行前判断：不是过拟合。本阶段不读取未来收益、不调交易参数，只建立采集样本闸门。
- 运行后判断：不是过拟合。它反而防止把同日重复采集、回填新闻或单次外生状态误当成样本外证据。

## 继续价值反思

- 运行前判断：有价值。Stage258/259 的瓶颈是点时样本深度和舆情账本，而不是收益回测不足。
- 运行后判断：仍有价值，但下一步必须是跨日采集和舆情账本落盘；未达标前不做选品收益回测。
"""

    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    gates.to_csv(COLLECTION_GATE_PATH, index=False, encoding="utf-8-sig")
    route_health.to_csv(ROUTE_HEALTH_PATH, index=False, encoding="utf-8-sig")
    date_progress.to_csv(DATE_PROGRESS_PATH, index=False, encoding="utf-8-sig")
    run_quality.to_csv(RUN_QUALITY_PATH, index=False, encoding="utf-8-sig")
    RUNBOOK_PATH.write_text(runbook, encoding="utf-8")
    REPORT_PATH.write_text(report, encoding="utf-8")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_chart(decision, route_health, gates, date_progress)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
