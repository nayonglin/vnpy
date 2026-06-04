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
MODEL_TAG = "stage561_selector_predictive_audit_protocol_v1"
OUTPUT_PREFIX = "qmt_roll_stage561_selector_predictive_audit_protocol"

MASTER_LEDGER_PATH = LEDGER_DIR / "external_state_forward_ledger.csv"
STAGE560_DECISION_PATH = OUTPUT_DIR / "qmt_roll_stage560_forward_collection_run_gate_decision_stage560_forward_collection_run_gate_v1.json"
STAGE558_FEATURE_PRIOR_PATH = OUTPUT_DIR / "qmt_roll_stage558_external_state_selector_readiness_audit_feature_prior_stage558_external_state_selector_readiness_audit_v1.csv"
SENTIMENT_TEMPLATE_GLOB = "sentiment_news_forward_ledger_template_*.csv"
SENTIMENT_REAL_GLOBS = ("sentiment_news_forward_ledger*.csv", "sentiment_news_manual_event_forward_ledger*.csv")

DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
PROTOCOL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_protocol_{MODEL_TAG}.json"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
FEATURE_SPEC_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_spec_{MODEL_TAG}.csv"
LABEL_SPEC_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_label_spec_{MODEL_TAG}.csv"
TEST_PLAN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_test_plan_{MODEL_TAG}.csv"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

LOCAL_TZ = ZoneInfo("Asia/Shanghai")

MIN_FORWARD_RUNS = 20
MIN_FORWARD_DATES = 20
MIN_ACTIVE_ROUTES = 2
MIN_REAL_SENTIMENT_LEDGERS = 1
MIN_PRODUCTS_PER_ROUTE = 20
MIN_EVAL_DATES_FOR_IC = 20
MIN_POSITIVE_IC_RATE_PCT = 60.0
MIN_MEAN_SPEARMAN_IC = 0.05
MIN_TOP_BUCKET_EDGE_63D = 0.0
MIN_TOP_BUCKET_EDGE_126D = 0.0
MAX_SELECTOR_TRIALS_BEFORE_REVIEW = 6
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


def _gate(name: str, passed: bool, current, required, severity: str, note: str) -> dict:
    return {
        "gate": name,
        "passed": bool(passed),
        "current": current,
        "required": required,
        "severity": severity,
        "note": note,
    }


def _load_ledger() -> pd.DataFrame:
    if not MASTER_LEDGER_PATH.exists():
        return pd.DataFrame()
    ledger = pd.read_csv(MASTER_LEDGER_PATH, encoding="utf-8-sig")
    if "received_at_local" in ledger.columns:
        ledger["received_at_local_ts"] = pd.to_datetime(ledger["received_at_local"], errors="coerce")
        ledger["received_date"] = ledger["received_at_local_ts"].dt.date.astype(str)
    for column in ["usable_for_forward_monitor", "usable_for_history_selector", "source_age_days"]:
        if column in ledger.columns:
            ledger[column] = pd.to_numeric(ledger[column], errors="coerce")
    return ledger


def _sentiment_counts() -> tuple[int, int]:
    templates = list(LEDGER_DIR.glob(SENTIMENT_TEMPLATE_GLOB))
    candidates: list[Path] = []
    for pattern in SENTIMENT_REAL_GLOBS:
        candidates.extend(LEDGER_DIR.glob(pattern))
    real = []
    for path in sorted(set(candidates)):
        name = path.name.lower()
        if "template" in name or "schema" in name or path.stat().st_size <= 0:
            continue
        try:
            frame = pd.read_csv(path, encoding="utf-8-sig")
        except (OSError, pd.errors.ParserError, UnicodeDecodeError):
            continue
        if frame.empty or not SENTIMENT_REQUIRED_COLUMNS.issubset(set(frame.columns)):
            continue
        received_ok = pd.to_datetime(frame["received_at_local"], errors="coerce").notna().any()
        source_ok = frame["source_url"].fillna("").astype(str).str.startswith("http").any()
        product_ok = frame["product_vt_symbol"].fillna("").astype(str).ne("").any()
        hash_ok = frame["raw_text_hash"].fillna("").astype(str).str.fullmatch(r"[0-9a-f]{64}").any()
        if received_ok and source_ok and product_ok and hash_ok:
            real.append(path)
    return len(templates), len(real)


def _stage560_snapshot() -> dict:
    if not STAGE560_DECISION_PATH.exists():
        return {}
    return json.loads(STAGE560_DECISION_PATH.read_text(encoding="utf-8"))


def _feature_prior_snapshot() -> pd.DataFrame:
    if not STAGE558_FEATURE_PRIOR_PATH.exists():
        return pd.DataFrame()
    return pd.read_csv(STAGE558_FEATURE_PRIOR_PATH, encoding="utf-8-sig")


def _route_latest_health(ledger: pd.DataFrame) -> pd.DataFrame:
    if ledger.empty or "route" not in ledger.columns:
        return pd.DataFrame(columns=["route", "latest_forward_products", "latest_ok_products", "latest_date"])
    rows = []
    for route, group in ledger.groupby("route"):
        latest_date = group["received_date"].dropna().max() if "received_date" in group.columns else ""
        latest = group[group["received_date"] == latest_date].copy() if latest_date else group.iloc[0:0].copy()
        latest_ok = latest[latest["status"] == "ok"] if "status" in latest.columns else latest.iloc[0:0]
        latest_forward = (
            latest[latest["usable_for_forward_monitor"].fillna(0).astype(int) == 1]
            if "usable_for_forward_monitor" in latest.columns
            else latest.iloc[0:0]
        )
        rows.append(
            {
                "route": route,
                "latest_forward_products": int(latest_forward["product_vt_symbol"].nunique())
                if "product_vt_symbol" in latest_forward.columns
                else 0,
                "latest_ok_products": int(latest_ok["product_vt_symbol"].nunique())
                if "product_vt_symbol" in latest_ok.columns
                else 0,
                "latest_date": latest_date,
            }
        )
    return pd.DataFrame(rows).sort_values("route").reset_index(drop=True)


def _feature_spec() -> pd.DataFrame:
    rows = [
        {
            "feature_group": "basis",
            "source_route": "basis",
            "allowed_fields": "dom_basis_rate,near_basis_rate,dom_basis,near_contract,dominant_contract,source_age_days,status",
            "availability_rule": "row.received_at_local <= selector_eval_time and usable_for_forward_monitor=1",
            "history_backfill_allowed": 0,
            "normalization": "cross_sectional_rank_by_received_date; missing -> missing bucket, not zero",
            "role": "candidate explanatory/selector input after 20-date PIT gate",
        },
        {
            "feature_group": "inventory",
            "source_route": "inventory",
            "allowed_fields": "inventory level/change fields from data_value_json,source_age_days,status",
            "availability_rule": "row.received_at_local <= selector_eval_time and usable_for_forward_monitor=1",
            "history_backfill_allowed": 0,
            "normalization": "cross_sectional_rank_by_received_date; winsorize within date only after frozen config",
            "role": "candidate explanatory/selector input after 20-date PIT gate",
        },
        {
            "feature_group": "sentiment_news",
            "source_route": "sentiment_news/manual_event",
            "allowed_fields": "event_type,sentiment_label,sentiment_score,relevance_score,direction_hint,source_age_hours,status",
            "availability_rule": "real ledger row received_at_local <= selector_eval_time; raw_text_hash/source_url required",
            "history_backfill_allowed": 0,
            "normalization": "event count and weighted sentiment by product/date; no relabeling from future prices",
            "role": "required audit input before any news/sentiment selector test",
        },
        {
            "feature_group": "market_state_guardrail",
            "source_route": "local market data",
            "allowed_fields": "recent liquidity, product_family, exchange, margin estimate, core_corr_252d if computed as-of date",
            "availability_rule": "must be computed only from bars fully known before selector_eval_time",
            "history_backfill_allowed": 0,
            "normalization": "fixed transformations only; no threshold tuning after labels are seen",
            "role": "risk/capacity guardrail, not alpha unless separately audited",
        },
        {
            "feature_group": "forbidden_hindsight",
            "source_route": "stage541/stage543 future columns",
            "allowed_fields": "future_* labels, oracle6, hindsight top products, future realized PnL",
            "availability_rule": "never available at selector_eval_time",
            "history_backfill_allowed": 0,
            "normalization": "not applicable",
            "role": "forbidden for selector features; only evaluation labels after maturity",
        },
    ]
    return pd.DataFrame(rows)


def _label_spec() -> pd.DataFrame:
    rows = [
        {
            "label_name": "future_product_trend_pnl_63d",
            "holding_experience": "3个月",
            "horizon_trading_days": 63,
            "label_start": "first trading session after selector_eval_time",
            "label_end": "63rd completed trading day after label_start",
            "source": "future frozen single-product or sleeve ledger produced after the horizon matures",
            "maturity_rule": "label_end_date <= available_market_data_last_date",
            "overlap_rule": "eval dates used for final OOS IC must be at least 63 trading days apart, or use purged grouping by month",
        },
        {
            "label_name": "future_product_trend_pnl_126d",
            "holding_experience": "6个月",
            "horizon_trading_days": 126,
            "label_start": "first trading session after selector_eval_time",
            "label_end": "126th completed trading day after label_start",
            "source": "future frozen single-product or sleeve ledger produced after the horizon matures",
            "maturity_rule": "label_end_date <= available_market_data_last_date",
            "overlap_rule": "eval dates used for final OOS IC must be at least 126 trading days apart, or use purged grouping by quarter",
        },
    ]
    return pd.DataFrame(rows)


def _test_plan() -> pd.DataFrame:
    rows = [
        {
            "step_id": 1,
            "step_name": "data_qualification",
            "action": "verify 20 runs, 20 dates, active basis+inventory routes, real sentiment/news ledger, no same-day sample inflation",
            "pass_rule": "all hard data gates PASS",
            "failure_action": "stop; collect more PIT data",
        },
        {
            "step_id": 2,
            "step_name": "feature_freeze",
            "action": "materialize allowed features by received_date/product from only received_at-known rows",
            "pass_rule": "feature schema and missing-data policy match this Stage561 protocol",
            "failure_action": "stop; schema migration stage required before predictive audit",
        },
        {
            "step_id": 3,
            "step_name": "label_maturity",
            "action": "wait until 63d/126d labels are complete for qualified eval dates",
            "pass_rule": "label_end_date <= data_last_date for every row used in that horizon",
            "failure_action": "stop; do paper monitoring only",
        },
        {
            "step_id": 4,
            "step_name": "fixed_ic_audit",
            "action": "compute monthly cross-sectional Spearman IC for each frozen feature family and horizon",
            "pass_rule": f"mean IC >= {MIN_MEAN_SPEARMAN_IC:.2f} and positive IC rate >= {MIN_POSITIVE_IC_RATE_PCT:.0f}%",
            "failure_action": "do not form trading selector; keep explanatory monitor only",
        },
        {
            "step_id": 5,
            "step_name": "fixed_bucket_audit",
            "action": "test predeclared top/bottom bucket edge on 63d and 126d labels",
            "pass_rule": "top bucket edge > 0 on both 63d and 126d, with no single date/product dominance",
            "failure_action": "do not form trading selector",
        },
        {
            "step_id": 6,
            "step_name": "paper_sleeve_replay",
            "action": "only if IC/bucket pass, run one frozen low-risk sleeve replay without TopN/risk/corr small-grid sweep",
            "pass_rule": "must improve 3m/6m left-tail and not worsen Stage526 DD/cost gates materially",
            "failure_action": "selector remains paper/monitor only",
        },
    ]
    return pd.DataFrame(rows)


def _write_chart(
    gates: pd.DataFrame,
    route_health: pd.DataFrame,
    label_spec: pd.DataFrame,
    feature_spec: pd.DataFrame,
    protocol_summary: dict,
) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "PingFang SC", "Heiti TC", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    fig.suptitle("Stage561 选品预测力审计协议冻结", fontsize=18, fontweight="bold")

    ax = axes[0, 0]
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
    ax.set_title("当前是否可启动预测力审计")
    for yi, (_, row) in enumerate(gate_plot.iterrows()):
        ax.text(1.02 if row["passed"] else 0.03, yi, "PASS" if row["passed"] else "FAIL", va="center", fontsize=10)

    ax = axes[0, 1]
    progress = protocol_summary["current_progress"]
    current = [progress["forward_runs"], progress["forward_dates"], progress["real_sentiment_ledgers"]]
    required = [MIN_FORWARD_RUNS, MIN_FORWARD_DATES, MIN_REAL_SENTIMENT_LEDGERS]
    labels = ["runs", "dates", "sentiment"]
    x = np.arange(len(labels))
    ax.bar(x - 0.18, current, width=0.36, label="current", color="#4C78A8")
    ax.bar(x + 0.18, required, width=0.36, label="required", color="#E0E0E0", edgecolor="#555555")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_title("数据资格进度")
    ax.set_ylabel("count")
    ax.legend(loc="upper left")
    ax.set_ylim(0, max(required) * 1.25)
    for i, value in enumerate(current):
        ax.text(i - 0.18, value + 0.25, str(value), ha="center", fontsize=10)
    for i, value in enumerate(required):
        ax.text(i + 0.18, value + 0.25, str(value), ha="center", fontsize=10)

    ax = axes[1, 0]
    if route_health.empty:
        ax.text(0.5, 0.5, "无route数据", ha="center", va="center")
        ax.axis("off")
    else:
        plot = route_health.sort_values("latest_forward_products", ascending=True)
        y = np.arange(len(plot))
        ax.barh(y, plot["latest_forward_products"], color="#59A14F")
        ax.axvline(MIN_PRODUCTS_PER_ROUTE, color="#E15759", linestyle="--", label=f"min {MIN_PRODUCTS_PER_ROUTE}")
        ax.set_yticks(y)
        ax.set_yticklabels(plot["route"])
        ax.set_xlabel("latest forward products")
        ax.set_title("Route产品覆盖")
        ax.legend(loc="lower right")
        for yi, value in enumerate(plot["latest_forward_products"]):
            ax.text(value + 0.25, yi, str(int(value)), va="center", fontsize=10)
        ax.set_xlim(0, max(MIN_PRODUCTS_PER_ROUTE + 10, int(plot["latest_forward_products"].max()) + 8))

    ax = axes[1, 1]
    ax.axis("off")
    label_lines = [
        "labels:",
        *[
            f"- {'3m' if int(row['horizon_trading_days']) == 63 else '6m'}: {int(row['horizon_trading_days'])} trading days"
            for _, row in label_spec.iterrows()
        ],
        "",
        "allowed feature groups:",
        *[f"- {name}" for name in feature_spec.loc[feature_spec["feature_group"] != "forbidden_hindsight", "feature_group"]],
        "",
        f"max selector trials: {MAX_SELECTOR_TRIALS_BEFORE_REVIEW}",
    ]
    ax.text(
        0.02,
        0.96,
        "\n".join(label_lines),
        ha="left",
        va="top",
        fontsize=12,
        family="monospace",
        bbox={"boxstyle": "round,pad=0.5", "facecolor": "#F7F7F7", "edgecolor": "#CCCCCC"},
    )

    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def main() -> None:
    now = datetime.now(LOCAL_TZ)
    ledger = _load_ledger()
    stage560 = _stage560_snapshot()
    feature_prior = _feature_prior_snapshot()
    route_health = _route_latest_health(ledger)
    feature_spec = _feature_spec()
    label_spec = _label_spec()
    test_plan = _test_plan()
    sentiment_template_count, real_sentiment_count = _sentiment_counts()

    sample_depth = stage560.get("sample_depth", {}) if stage560 else {}
    raw_forward_runs = int(ledger["run_id"].nunique()) if not ledger.empty and "run_id" in ledger.columns else 0
    raw_forward_dates = int(ledger["received_date"].nunique()) if not ledger.empty and "received_date" in ledger.columns else 0
    forward_runs = int(sample_depth.get("qualified_forward_runs", sample_depth.get("forward_runs", raw_forward_runs)))
    forward_dates = int(sample_depth.get("qualified_forward_dates", sample_depth.get("forward_dates", raw_forward_dates)))
    active_routes = int((route_health["latest_forward_products"] >= MIN_PRODUCTS_PER_ROUTE).sum()) if not route_health.empty else 0
    latest_received_date = str(ledger["received_date"].dropna().max()) if not ledger.empty and "received_date" in ledger.columns else ""
    raw_duplicate_dates = (
        int((ledger.groupby("received_date")["run_id"].nunique() > 1).sum())
        if not ledger.empty and "received_date" in ledger.columns and "run_id" in ledger.columns
        else 0
    )
    extra_qualified_same_day_runs = int(sample_depth.get("extra_qualified_same_day_runs", 0))
    sample_depth_inflation_absent = extra_qualified_same_day_runs == 0
    history_ready_products = (
        int(ledger.loc[ledger["usable_for_history_selector"].fillna(0).astype(int) == 1, "product_vt_symbol"].nunique())
        if not ledger.empty and "usable_for_history_selector" in ledger.columns and "product_vt_symbol" in ledger.columns
        else 0
    )
    today = now.date()
    next_eligible_date = (
        stage560.get("clock", {}).get("next_eligible_collection_date")
        if stage560
        else (today + timedelta(days=1)).isoformat()
    )

    gates = pd.DataFrame(
        [
            _gate("protocol_file_created", True, 1, 1, "hard", "this run freezes the audit protocol"),
            _gate("forward_runs_ready", forward_runs >= MIN_FORWARD_RUNS, forward_runs, MIN_FORWARD_RUNS, "hard", "do not audit selector before enough distinct runs"),
            _gate("forward_dates_ready", forward_dates >= MIN_FORWARD_DATES, forward_dates, MIN_FORWARD_DATES, "hard", "do not audit selector before enough cross-day samples"),
            _gate("same_day_inflation_absent", sample_depth_inflation_absent, extra_qualified_same_day_runs, 0, "hard", "same received_date reruns cannot increase qualified sample depth"),
            _gate("active_routes_ready", active_routes >= MIN_ACTIVE_ROUTES, active_routes, MIN_ACTIVE_ROUTES, "hard", f"each active route must have >= {MIN_PRODUCTS_PER_ROUTE} products"),
            _gate("sentiment_real_ledger_ready", real_sentiment_count >= MIN_REAL_SENTIMENT_LEDGERS, real_sentiment_count, MIN_REAL_SENTIMENT_LEDGERS, "hard", "news/sentiment cannot be used until real ledger exists"),
            _gate("history_selector_disabled", history_ready_products == 0, history_ready_products, 0, "hard", "forward data must not be reclassified as historical selector data"),
            _gate("label_protocol_frozen", True, "63d/126d", "63d/126d", "hard", "3m/6m labels are fixed before future outcomes are available"),
            _gate("max_trials_predeclared", True, MAX_SELECTOR_TRIALS_BEFORE_REVIEW, f"<= {MAX_SELECTOR_TRIALS_BEFORE_REVIEW}", "soft", "prevents endless selector grid search"),
        ]
    )
    ready_for_predictive_audit = bool(
        forward_runs >= MIN_FORWARD_RUNS
        and forward_dates >= MIN_FORWARD_DATES
        and sample_depth_inflation_absent
        and active_routes >= MIN_ACTIVE_ROUTES
        and real_sentiment_count >= MIN_REAL_SENTIMENT_LEDGERS
        and history_ready_products == 0
    )
    decision_label = "protocol_frozen_predictive_audit_not_ready"
    if ready_for_predictive_audit:
        decision_label = "protocol_frozen_predictive_audit_data_ready_wait_label_maturity"

    protocol = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "created_at_local": now.isoformat(),
        "decision": decision_label,
        "purpose": "Freeze the future point-in-time product selector predictive audit before enough forward outcomes exist.",
        "current_progress": {
            "forward_runs": forward_runs,
            "forward_dates": forward_dates,
            "raw_forward_runs": raw_forward_runs,
            "raw_forward_dates": raw_forward_dates,
            "latest_received_date": latest_received_date,
            "next_eligible_collection_date": next_eligible_date,
            "raw_duplicate_received_dates": raw_duplicate_dates,
            "extra_qualified_same_day_runs": extra_qualified_same_day_runs,
            "active_routes": active_routes,
            "real_sentiment_ledgers": real_sentiment_count,
            "sentiment_templates": sentiment_template_count,
            "history_ready_products": history_ready_products,
        },
        "hard_requirements_before_predictive_audit": {
            "min_forward_runs": MIN_FORWARD_RUNS,
            "min_forward_dates": MIN_FORWARD_DATES,
            "min_active_routes": MIN_ACTIVE_ROUTES,
            "min_products_per_route": MIN_PRODUCTS_PER_ROUTE,
            "min_real_sentiment_ledgers": MIN_REAL_SENTIMENT_LEDGERS,
            "extra_qualified_same_day_runs": 0,
            "history_selector_ready_products": 0,
        },
        "fixed_pass_rules_after_labels_mature": {
            "min_eval_dates_for_ic": MIN_EVAL_DATES_FOR_IC,
            "min_mean_spearman_ic": MIN_MEAN_SPEARMAN_IC,
            "min_positive_ic_rate_pct": MIN_POSITIVE_IC_RATE_PCT,
            "min_top_bucket_edge_63d": MIN_TOP_BUCKET_EDGE_63D,
            "min_top_bucket_edge_126d": MIN_TOP_BUCKET_EDGE_126D,
            "max_selector_trials_before_review": MAX_SELECTOR_TRIALS_BEFORE_REVIEW,
        },
        "forbidden_actions": [
            "Do not use Stage541/Stage543 future columns as features.",
            "Do not count same-day collection reruns as new selector samples.",
            "Do not backfill news/sentiment labels after seeing future returns.",
            "Do not sweep TopN/risk/corr/family thresholds after seeing 63d/126d outcomes.",
            "Do not create a trading selector until fixed IC, bucket, and paper sleeve audits all pass.",
        ],
    }
    decision = {
        **protocol,
        "outputs": {
            "decision": str(DECISION_PATH),
            "protocol": str(PROTOCOL_PATH),
            "gates": str(GATES_PATH),
            "feature_spec": str(FEATURE_SPEC_PATH),
            "label_spec": str(LABEL_SPEC_PATH),
            "test_plan": str(TEST_PLAN_PATH),
            "report": str(REPORT_PATH),
            "chart": str(CHART_PATH),
        },
    }

    feature_prior_summary = "无 Stage558 feature prior 文件。"
    if not feature_prior.empty:
        feature_prior_summary = _md_table(
            feature_prior[["feature", "horizon_days", "months", "mean_spearman_ic", "positive_ic_rate_pct", "prior_strength"]].head(8)
        )

    report = f"""# Stage561 选品预测力审计协议冻结

- line_id：`{LINE_ID}`
- 生成时间：`{now.strftime('%Y-%m-%d %H:%M:%S %Z')}`
- 阶段性质：未来 selector 预测力审计预注册；不做收益回测，不生成交易候选。
- 决策：`{decision_label}`

## 核心结论

- 本阶段冻结未来外生/舆情选品器的 3个月/6个月预测力审计协议，避免等 `20` 个样本到位后按结果倒调指标。
- 当前数据仍未达标：质量闸门计数 `runs={forward_runs}/{MIN_FORWARD_RUNS}`、`dates={forward_dates}/{MIN_FORWARD_DATES}`；raw 账本计数 `runs={raw_forward_runs}`、`dates={raw_forward_dates}`；真实 sentiment/news ledger `{real_sentiment_count}/{MIN_REAL_SENTIMENT_LEDGERS}`。
- 当前可用 route：basis/inventory 具备 forward 覆盖；member_detail/warehouse 暂不达标。active routes 以每条 route 至少 `{MIN_PRODUCTS_PER_ROUTE}` 个 latest forward-ready 产品计数，当前为 `{active_routes}/{MIN_ACTIVE_ROUTES}`。
- 未来正式标签固定为 `63` 和 `126` 个交易日的产品趋势收益，不允许临时换成更好看的窗口。
- Stage541/Stage543 的 `future_*`、`oracle6`、hindsight top 产品只允许作为历史研究背景和未来标签参考，禁止作为 selector 特征。

## 当前闸门

{_md_table(gates)}

## Feature Spec

{_md_table(feature_spec)}

## Label Spec

{_md_table(label_spec)}

## Test Plan

{_md_table(test_plan)}

## Stage558 历史先验参考

{feature_prior_summary}

## 过拟合反思

- 运行前判断：不是过拟合。本阶段在未来结果出现前冻结协议，不读取新收益标签，不调交易参数。
- 运行后判断：不是过拟合，且降低未来过拟合风险。原因是协议明确禁止同日样本膨胀、新闻回填、hindsight 产品池和 TopN/阈值事后救援。

## 继续价值反思

- 运行前判断：有价值。Stage257 证明简单宽池失败，Stage258-260 证明外生方向卡在数据资格。
- 运行后判断：仍有价值，但下一步仍不是收益回测，而是跨日采集、真实舆情账本和标签成熟后的一次固定审计。
"""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    feature_spec.to_csv(FEATURE_SPEC_PATH, index=False, encoding="utf-8-sig")
    label_spec.to_csv(LABEL_SPEC_PATH, index=False, encoding="utf-8-sig")
    test_plan.to_csv(TEST_PLAN_PATH, index=False, encoding="utf-8-sig")
    PROTOCOL_PATH.write_text(json.dumps(_json_safe(protocol), ensure_ascii=False, indent=2), encoding="utf-8")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(report, encoding="utf-8")
    _write_chart(gates, route_health, label_spec, feature_spec, protocol)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
