from __future__ import annotations

from datetime import datetime, timedelta, timezone
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
MODEL_TAG = "stage634_watchline_source_contract_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage634_watchline_source_contract_audit"

STAGE633_PRODUCT_MAP = (
    OUTPUT_DIR / "qmt_roll_stage633_independent_risk_slot_correlation_map_product_map_stage633_independent_risk_slot_correlation_map_v1.csv"
)
STAGE604_SLOT_INVENTORY = (
    OUTPUT_DIR / "qmt_roll_stage604_low_single_risk_slot_allocator_audit_slot_inventory_stage604_low_single_risk_slot_allocator_audit_v1.csv"
)

SOURCE_CONTRACT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_contract_{MODEL_TAG}.csv"
PRODUCT_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_summary_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

WATCH_PRODUCTS = ["CJ.CZCE", "lh.DCE"]
REQUIRED_PIT_DATES_FOR_SELECTOR = 20
REQUIRED_LIVE_TCA_SAMPLES = 3
REQUIRED_NON_OVERLAP_EPISODES = 3

REFERENCES = [
    "CZCE dried jujube futures contract overview: https://english.zce.cn/en/index.htm",
    "CZCE detailed rules for dried jujube futures: https://english.czce.com.cn/en/Rulebook/DetailedRules/webinfo/2025/08/1750864479605262.htm",
    "National Forestry and Grassland Administration Xinjiang jujube industry note: https://www.forestry.gov.cn/lyj/1/slgs/20241023/593126.html",
    "MOA live hog product monthly data example: https://www.moa.gov.cn/ztzl/szcpxx/jdsj/2025/202501/",
    "MOA/NAHS monthly livestock and feed price bulletin example: https://www.nahs.org.cn/jcyj/scxs/202601/t20260115_469255.htm",
    "DCE investor education material: https://www.dce.com.cn/dceg/file/2025-05-25/1748165285051ff8080819701ddb3518019706c554bb21f7.pdf",
]


SOURCE_ROWS = [
    {
        "product_vt_symbol": "CJ.CZCE",
        "product_family": "watch_jujube",
        "source_name": "CZCE dried jujube contract overview",
        "source_url": "https://english.zce.cn/en/index.htm",
        "source_authority": "exchange_official",
        "source_class": "contract_spec_reference",
        "cadence": "rule_static_or_as_announced",
        "signal_family": "contract_delivery_context",
        "expected_fields": "contract_unit,margin,delivery_month,last_trading_day,delivery_method",
        "history_selector_allowed": 0,
        "forward_monitor_allowed_after_fetch_probe": 1,
        "active_fetch_validated_now": 0,
        "raw_hash_present_now": 0,
        "pit_dates_now": 0,
        "event_signal_ready_now": 0,
        "paper_or_whitelist_allowed": 0,
        "route_risk": "contract page found by web research but no stage fetch/raw-hash validation yet",
    },
    {
        "product_vt_symbol": "CJ.CZCE",
        "product_family": "watch_jujube",
        "source_name": "CZCE detailed rules for dried jujube futures",
        "source_url": "https://english.czce.com.cn/en/Rulebook/DetailedRules/webinfo/2025/08/1750864479605262.htm",
        "source_authority": "exchange_official",
        "source_class": "delivery_rule_reference",
        "cadence": "rule_static_or_as_announced",
        "signal_family": "delivery_quality_and_warehouse_context",
        "expected_fields": "delivery_rules,warehouse_receipt_rules,quality_standard,delivery_procedure",
        "history_selector_allowed": 0,
        "forward_monitor_allowed_after_fetch_probe": 1,
        "active_fetch_validated_now": 0,
        "raw_hash_present_now": 0,
        "pit_dates_now": 0,
        "event_signal_ready_now": 0,
        "paper_or_whitelist_allowed": 0,
        "route_risk": "CZCE routes have prior 412/404 blocker; must fetch-probe before use",
    },
    {
        "product_vt_symbol": "CJ.CZCE",
        "product_family": "watch_jujube",
        "source_name": "Xinjiang jujube industry public note",
        "source_url": "https://www.forestry.gov.cn/lyj/1/slgs/20241023/593126.html",
        "source_authority": "government_public",
        "source_class": "spot_industry_reference",
        "cadence": "irregular_public_article",
        "signal_family": "production_region_context",
        "expected_fields": "production_area,acreage_reform,yield_range,industry_policy_context",
        "history_selector_allowed": 0,
        "forward_monitor_allowed_after_fetch_probe": 1,
        "active_fetch_validated_now": 0,
        "raw_hash_present_now": 0,
        "pit_dates_now": 0,
        "event_signal_ready_now": 0,
        "paper_or_whitelist_allowed": 0,
        "route_risk": "not a stable release calendar; context only until repeated PIT samples exist",
    },
    {
        "product_vt_symbol": "lh.DCE",
        "product_family": "livestock",
        "source_name": "MOA live hog product monthly data",
        "source_url": "https://www.moa.gov.cn/ztzl/szcpxx/jdsj/2025/202501/",
        "source_authority": "government_official",
        "source_class": "monthly_supply_demand_release",
        "cadence": "monthly",
        "signal_family": "sow_inventory_slaughter_price_supply_demand",
        "expected_fields": "sow_inventory,slaughter_volume,piglet_price,pork_price,corn_feed_price",
        "history_selector_allowed": 0,
        "forward_monitor_allowed_after_fetch_probe": 1,
        "active_fetch_validated_now": 0,
        "raw_hash_present_now": 0,
        "pit_dates_now": 0,
        "event_signal_ready_now": 0,
        "paper_or_whitelist_allowed": 0,
        "route_risk": "promising official monthly source; must build parser and raw-hash ledger",
    },
    {
        "product_vt_symbol": "lh.DCE",
        "product_family": "livestock",
        "source_name": "MOA/NAHS monthly livestock and feed price bulletin",
        "source_url": "https://www.nahs.org.cn/jcyj/scxs/202601/t20260115_469255.htm",
        "source_authority": "government_official",
        "source_class": "monthly_price_release",
        "cadence": "monthly",
        "signal_family": "hog_price_feed_price_pig_grain_ratio",
        "expected_fields": "hog_price,pork_price,piglet_price,corn_price,soymeal_price,pig_grain_ratio",
        "history_selector_allowed": 0,
        "forward_monitor_allowed_after_fetch_probe": 1,
        "active_fetch_validated_now": 0,
        "raw_hash_present_now": 0,
        "pit_dates_now": 0,
        "event_signal_ready_now": 0,
        "paper_or_whitelist_allowed": 0,
        "route_risk": "promising official monthly price source; current row is example, not ledger",
    },
    {
        "product_vt_symbol": "lh.DCE",
        "product_family": "livestock",
        "source_name": "DCE live hog contract and delivery rules reference",
        "source_url": "https://www.dce.com.cn/dceg/file/2025-05-25/1748165285051ff8080819701ddb3518019706c554bb21f7.pdf",
        "source_authority": "exchange_official",
        "source_class": "contract_delivery_reference",
        "cadence": "rule_static_or_as_announced",
        "signal_family": "contract_delivery_context",
        "expected_fields": "contract_unit,delivery_unit,delivery_method,delivery_quality,member_delivery_process",
        "history_selector_allowed": 0,
        "forward_monitor_allowed_after_fetch_probe": 1,
        "active_fetch_validated_now": 0,
        "raw_hash_present_now": 0,
        "pit_dates_now": 0,
        "event_signal_ready_now": 0,
        "paper_or_whitelist_allowed": 0,
        "route_risk": "DCE official routes previously blocked for some datasets; PDF/reference must be hashed before use",
    },
]


def _now_cst() -> datetime:
    return datetime.now(timezone(timedelta(hours=8)))


def _fmt_cst(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S CST")


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
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def _num(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return (
        pd.to_numeric(frame[column], errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
        .fillna(default)
        .astype(float)
    )


def _str(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series("", index=frame.index, dtype=str)
    return frame[column].fillna("").astype(str).str.strip()


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


def _source_contract() -> pd.DataFrame:
    frame = pd.DataFrame(SOURCE_ROWS)
    for column in [
        "history_selector_allowed",
        "forward_monitor_allowed_after_fetch_probe",
        "active_fetch_validated_now",
        "raw_hash_present_now",
        "pit_dates_now",
        "event_signal_ready_now",
        "paper_or_whitelist_allowed",
    ]:
        frame[column] = _num(frame, column).astype(int)
    frame["contract_complete_for_future_probe"] = (
        _str(frame, "source_url").ne("")
        & _str(frame, "source_authority").ne("")
        & _str(frame, "source_class").ne("")
        & _str(frame, "cadence").ne("")
        & _str(frame, "expected_fields").ne("")
    ).astype(int)
    frame["monitor_status"] = np.where(
        frame["active_fetch_validated_now"].eq(1) & frame["raw_hash_present_now"].eq(1),
        "fetch_validated",
        "contract_only_fetch_probe_required",
    )
    return frame


def _product_summary(source: pd.DataFrame) -> pd.DataFrame:
    product_map = _read_csv(STAGE633_PRODUCT_MAP)
    product_map["product_vt_symbol"] = _str(product_map, "product_vt_symbol")
    product_map = product_map[product_map["product_vt_symbol"].isin(WATCH_PRODUCTS)].copy()
    for column in [
        "tradable_rows",
        "recent_median_volume",
        "max_abs_corr_to_p0",
        "tail_abs_corr_to_p0_composite",
        "rolling_abs_corr_p75_to_p0",
        "trend_years",
        "trend_year_rate_pct",
        "data_pass",
        "liquidity_pass",
        "watch_corr_pass",
        "low_corr_pass",
    ]:
        product_map[column] = _num(product_map, column)

    agg = source.groupby("product_vt_symbol").agg(
        source_contract_rows=("source_name", "count"),
        official_source_rows=("source_authority", lambda item: int(pd.Series(item).astype(str).str.contains("official|government", regex=True).sum())),
        government_source_rows=("source_authority", lambda item: int(pd.Series(item).astype(str).str.contains("government", regex=True).sum())),
        exchange_source_rows=("source_authority", lambda item: int(pd.Series(item).astype(str).str.contains("exchange", regex=True).sum())),
        monthly_source_rows=("cadence", lambda item: int(pd.Series(item).astype(str).str.contains("monthly", regex=True).sum())),
        active_fetch_validated_rows=("active_fetch_validated_now", "sum"),
        raw_hash_rows=("raw_hash_present_now", "sum"),
        pit_dates_now=("pit_dates_now", "max"),
        event_signal_ready_rows=("event_signal_ready_now", "sum"),
        paper_or_whitelist_rows=("paper_or_whitelist_allowed", "sum"),
        contract_complete_rows=("contract_complete_for_future_probe", "sum"),
    ).reset_index()
    frame = product_map.merge(agg, on="product_vt_symbol", how="left")
    for column in [
        "source_contract_rows",
        "official_source_rows",
        "government_source_rows",
        "exchange_source_rows",
        "monthly_source_rows",
        "active_fetch_validated_rows",
        "raw_hash_rows",
        "pit_dates_now",
        "event_signal_ready_rows",
        "paper_or_whitelist_rows",
        "contract_complete_rows",
    ]:
        frame[column] = _num(frame, column).astype(int)

    frame["source_contract_score"] = (
        0.25 * frame["source_contract_rows"].clip(upper=3) / 3
        + 0.25 * frame["official_source_rows"].clip(upper=2) / 2
        + 0.20 * frame["monthly_source_rows"].clip(upper=2) / 2
        + 0.15 * frame["contract_complete_rows"].clip(upper=3) / 3
        + 0.15 * frame["active_fetch_validated_rows"].clip(upper=1)
    )
    frame["readiness_score"] = (
        0.20 * frame["data_pass"]
        + 0.20 * frame["liquidity_pass"]
        + 0.15 * frame["watch_corr_pass"]
        + 0.10 * frame["low_corr_pass"]
        + 0.20 * frame["source_contract_score"]
        + 0.15 * frame["raw_hash_rows"].clip(upper=1)
    )
    frame["promotion_allowed"] = 0
    frame["paper_allowed"] = 0
    frame["trading_whitelist_allowed"] = 0
    frame["next_action"] = np.where(
        frame["product_vt_symbol"].eq("lh.DCE"),
        "build monthly MOA/NAHS raw-hash fetch probe before any selector test",
        "classify CJ family and probe CZCE/jujube public sources; no selector test",
    )
    frame["status"] = np.where(
        frame["product_vt_symbol"].eq("lh.DCE"),
        "watchline_source_contract_promising_fetch_probe_required",
        "watchline_source_contract_weak_fetch_probe_required",
    )
    return frame.sort_values(["readiness_score", "product_vt_symbol"], ascending=[False, True]).reset_index(drop=True)


def _gates(source: pd.DataFrame, product: pd.DataFrame) -> pd.DataFrame:
    active_fetch = int(source["active_fetch_validated_now"].sum())
    raw_hash = int(source["raw_hash_present_now"].sum())
    pit_dates = int(product["pit_dates_now"].max()) if not product.empty else 0
    paper_rows = int(product["paper_allowed"].sum() + product["trading_whitelist_allowed"].sum()) if not product.empty else 0
    promotion_rows = int(product["promotion_allowed"].sum()) if not product.empty else 0
    rows = [
        {
            "gate": "watch_products_loaded",
            "passed": int(set(WATCH_PRODUCTS).issubset(set(product["product_vt_symbol"]))),
            "current": int(product["product_vt_symbol"].nunique()),
            "required": len(WATCH_PRODUCTS),
            "note": "CJ/lh must be present in Stage633 product map.",
        },
        {
            "gate": "price_data_and_liquidity_pass",
            "passed": int(product["data_pass"].sum() == len(WATCH_PRODUCTS) and product["liquidity_pass"].sum() == len(WATCH_PRODUCTS)),
            "current": f"data={int(product['data_pass'].sum())},liq={int(product['liquidity_pass'].sum())}",
            "required": f"{len(WATCH_PRODUCTS)}/{len(WATCH_PRODUCTS)}",
            "note": "Both products must be tradable enough for source work.",
        },
        {
            "gate": "watch_corr_pass",
            "passed": int(product["watch_corr_pass"].sum() == len(WATCH_PRODUCTS)),
            "current": int(product["watch_corr_pass"].sum()),
            "required": len(WATCH_PRODUCTS),
            "note": "Both are only watch-line, not strict low-corr slots.",
        },
        {
            "gate": "source_contract_rows_present",
            "passed": int(len(source) >= 6),
            "current": len(source),
            "required": ">=6",
            "note": "Source contracts exist before fetch probe.",
        },
        {
            "gate": "lh_has_monthly_official_sources",
            "passed": int(product.loc[product["product_vt_symbol"].eq("lh.DCE"), "monthly_source_rows"].sum() >= 2),
            "current": int(product.loc[product["product_vt_symbol"].eq("lh.DCE"), "monthly_source_rows"].sum()),
            "required": ">=2",
            "note": "lh has promising official monthly MOA/NAHS source candidates.",
        },
        {
            "gate": "cj_source_weaker_documented",
            "passed": int(product.loc[product["product_vt_symbol"].eq("CJ.CZCE"), "monthly_source_rows"].sum() == 0),
            "current": int(product.loc[product["product_vt_symbol"].eq("CJ.CZCE"), "monthly_source_rows"].sum()),
            "required": 0,
            "note": "CJ lacks stable monthly official fundamental release in current contract.",
        },
        {
            "gate": "fetch_not_validated_fail_closed",
            "passed": int(active_fetch == 0 and raw_hash == 0 and pit_dates == 0),
            "current": f"fetch={active_fetch},hash={raw_hash},pit={pit_dates}",
            "required": "0/0/0",
            "note": "No source is allowed into selector before raw-hash PIT fetch probe.",
        },
        {
            "gate": "no_paper_or_whitelist",
            "passed": int(paper_rows == 0 and promotion_rows == 0),
            "current": f"promotion={promotion_rows},paper_or_whitelist={paper_rows}",
            "required": "0/0",
            "note": "Contract audit cannot promote products.",
        },
        {
            "gate": "selector_requirements_unmet_fail_closed",
            "passed": int(pit_dates < REQUIRED_PIT_DATES_FOR_SELECTOR and active_fetch == 0),
            "current": pit_dates,
            "required": f">={REQUIRED_PIT_DATES_FOR_SELECTOR}",
            "note": "Need PIT dates, independent episodes and TCA before selector.",
        },
    ]
    return pd.DataFrame(rows)


def _write_chart(source: pd.DataFrame, product: pd.DataFrame, gates: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    fig.suptitle("Stage634 watchline source contract audit: CJ/lh remain monitor-only", fontsize=16)

    ax = axes[0, 0]
    metrics = [
        "data_pass",
        "liquidity_pass",
        "watch_corr_pass",
        "source_contract_score",
        "active_fetch_validated_rows",
        "raw_hash_rows",
    ]
    metric_labels = ["data", "liquidity", "watch corr", "source contract", "fetch", "raw hash"]
    x = np.arange(len(product))
    width = 0.12
    for idx, metric in enumerate(metrics):
        values = product[metric].astype(float).clip(0.0, 1.0)
        ax.bar(x + (idx - 2.5) * width, values, width=width, label=metric_labels[idx])
    ax.set_xticks(x)
    ax.set_xticklabels(product["product_vt_symbol"])
    ax.set_ylim(0, 1.05)
    ax.set_title("Product readiness layers")
    ax.set_ylabel("normalized readiness")
    ax.legend(loc="upper right", fontsize=8)

    ax = axes[0, 1]
    pivot = (
        source.assign(value=1)
        .pivot_table(index="source_class", columns="product_vt_symbol", values="value", aggfunc="sum", fill_value=0)
        .reindex(columns=WATCH_PRODUCTS, fill_value=0)
    )
    image = ax.imshow(pivot.values, aspect="auto", cmap="Greens", vmin=0, vmax=max(1, int(pivot.values.max())))
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns)
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=8)
    ax.set_title("Source contract classes")
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            ax.text(j, i, str(int(pivot.values[i, j])), ha="center", va="center", fontsize=8)
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)

    ax = axes[1, 0]
    status_counts = source.groupby(["product_vt_symbol", "monitor_status"]).size().unstack(fill_value=0).reindex(WATCH_PRODUCTS, fill_value=0)
    status_counts.plot(kind="bar", stacked=True, ax=ax, color=["tab:orange", "tab:green"])
    ax.set_title("Monitor status: contract exists, fetch not validated")
    ax.set_ylabel("source rows")
    ax.tick_params(axis="x", rotation=0)
    ax.legend(loc="upper right", fontsize=8)

    ax = axes[1, 1]
    colors = ["tab:green" if int(item) == 1 else "tab:red" for item in gates["passed"]]
    ax.barh(gates["gate"], gates["passed"], color=colors)
    ax.set_xlim(0, 1)
    ax.set_title("Hard gates: green includes fail-closed locks")
    ax.tick_params(axis="y", labelsize=8)
    for i, row in gates.iterrows():
        ax.text(0.02, i, str(row["current"]), va="center", ha="left", fontsize=8, color="white")

    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _write_report(
    generated_at: datetime,
    source: pd.DataFrame,
    product: pd.DataFrame,
    gates: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    lines = [
        "# Stage634 Watchline Source Contract Audit Report",
        "",
        f"- generated_at_cst: `{_fmt_cst(generated_at)}`",
        f"- decision: `{decision['decision']}`",
        "",
        "## External Research Judgement",
        "",
        "`CJ.CZCE/lh.DCE` 都在 Stage633 的相关性观察线附近，但扩池的下一步不能直接做收益回测。`lh.DCE` 的官方基本面源更强，农业农村部/畜牧总站有月度生猪产品、能繁母猪、屠宰量、价格、猪粮比等公开口径；`CJ.CZCE` 目前主要是郑商所合约/交割规则和新疆红枣产业资料，稳定、月度、可自动化的基本面源更弱。两者都必须先做 raw-hash/PIT fetch probe，不能进入 selector。",
        "",
        "References:",
        *[f"- {item}" for item in REFERENCES],
        "",
        "## Key Numbers",
        "",
        f"- watch products: `{decision['watch_products']}`",
        f"- source contract rows: `{decision['source_contract_rows']}`",
        f"- lh monthly official source rows: `{decision['lh_monthly_official_source_rows']}`",
        f"- CJ monthly official source rows: `{decision['cj_monthly_official_source_rows']}`",
        f"- active fetch validated rows: `{decision['active_fetch_validated_rows']}`",
        f"- raw hash rows: `{decision['raw_hash_rows']}`",
        f"- PIT dates now: `{decision['pit_dates_now']}`",
        f"- promotion rows: `{decision['promotion_rows']}`",
        f"- paper/whitelist rows: `{decision['paper_or_whitelist_rows']}`",
        f"- hard gates: `{decision['hard_gates_passed']}/{decision['hard_gates_total']}`",
        "",
        "## Product Summary",
        "",
        _md_table(
            product,
            columns=[
                "product_vt_symbol",
                "product_family",
                "structural_bucket",
                "tradable_rows",
                "last_tradable_date",
                "recent_median_volume",
                "max_abs_corr_to_p0",
                "tail_abs_corr_to_p0_composite",
                "watch_corr_pass",
                "source_contract_rows",
                "monthly_source_rows",
                "active_fetch_validated_rows",
                "raw_hash_rows",
                "readiness_score",
                "status",
                "next_action",
            ],
        ),
        "",
        "## Source Contract",
        "",
        _md_table(
            source,
            columns=[
                "product_vt_symbol",
                "source_name",
                "source_authority",
                "source_class",
                "cadence",
                "signal_family",
                "active_fetch_validated_now",
                "raw_hash_present_now",
                "monitor_status",
                "route_risk",
            ],
        ),
        "",
        "## Gates",
        "",
        _md_table(gates),
        "",
        "## Interpretation",
        "",
        "- `lh.DCE` 比 `CJ.CZCE` 更适合进入下一步 fetch probe，因为官方月度数据源更明确。",
        "- `CJ.CZCE` 仍需要先补产品族定义和 CZCE/红枣公开源自动化取证；当前只能观察。",
        "- 两个产品都没有 raw hash、PIT 日期、独立 episode 或 live TCA，因此不能 paper、A/B 或白名单。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    generated_at = _now_cst()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    source = _source_contract()
    product = _product_summary(source)
    gates = _gates(source, product)
    decision = {
        "decision": "watchline_source_contract_ready_fetch_probe_required_no_promotion",
        "generated_at_cst": _fmt_cst(generated_at),
        "line_id": LINE_ID,
        "watch_products": int(product["product_vt_symbol"].nunique()),
        "source_contract_rows": int(len(source)),
        "lh_monthly_official_source_rows": int(product.loc[product["product_vt_symbol"].eq("lh.DCE"), "monthly_source_rows"].sum()),
        "cj_monthly_official_source_rows": int(product.loc[product["product_vt_symbol"].eq("CJ.CZCE"), "monthly_source_rows"].sum()),
        "active_fetch_validated_rows": int(source["active_fetch_validated_now"].sum()),
        "raw_hash_rows": int(source["raw_hash_present_now"].sum()),
        "pit_dates_now": int(product["pit_dates_now"].max()) if not product.empty else 0,
        "promotion_rows": int(product["promotion_allowed"].sum()) if not product.empty else 0,
        "paper_or_whitelist_rows": int(product["paper_allowed"].sum() + product["trading_whitelist_allowed"].sum()) if not product.empty else 0,
        "hard_gates_passed": int(gates["passed"].sum()),
        "hard_gates_total": int(len(gates)),
        "source_contract_path": str(SOURCE_CONTRACT_PATH),
        "product_summary_path": str(PRODUCT_SUMMARY_PATH),
        "chart_path": str(CHART_PATH),
    }

    source.to_csv(SOURCE_CONTRACT_PATH, index=False, encoding="utf-8-sig")
    product.to_csv(PRODUCT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_report(generated_at, source, product, gates, decision)
    _write_chart(source, product, gates)
    print(json.dumps(_json_safe(decision), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
