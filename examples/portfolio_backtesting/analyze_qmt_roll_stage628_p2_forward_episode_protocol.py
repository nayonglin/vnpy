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
MODEL_TAG = "stage628_p2_forward_episode_protocol_v1"
OUTPUT_PREFIX = "qmt_roll_stage628_p2_forward_episode_protocol"

STAGE625_RAW_LEDGER = OUTPUT_DIR / (
    "qmt_roll_stage625_public_source_raw_text_probe_raw_fetch_ledger_"
    "stage625_public_source_raw_text_probe_v1.csv"
)
STAGE625_PRODUCT_SUMMARY = OUTPUT_DIR / (
    "qmt_roll_stage625_public_source_raw_text_probe_product_summary_"
    "stage625_public_source_raw_text_probe_v1.csv"
)
STAGE627_FAMILY_REPRIORITIZATION = OUTPUT_DIR / (
    "qmt_roll_stage627_post_source_probe_slot_reprioritization_family_reprioritization_"
    "stage627_post_source_probe_slot_reprioritization_v1.csv"
)
STAGE627_SOURCE_DELTA = OUTPUT_DIR / (
    "qmt_roll_stage627_post_source_probe_slot_reprioritization_source_delta_"
    "stage627_post_source_probe_slot_reprioritization_v1.csv"
)

PRODUCT_PROTOCOL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_protocol_{MODEL_TAG}.csv"
FAMILY_PROTOCOL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_family_protocol_{MODEL_TAG}.csv"
EPISODE_RULES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_episode_rules_{MODEL_TAG}.csv"
PROMOTION_GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_promotion_gates_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

REQUIRED_PIT_DATES = 20
REQUIRED_PIT_MONTHS = 12
REQUIRED_EPISODES_PER_FAMILY = 3
REQUIRED_LIVE_TCA_PER_PRODUCT = 3
REQUIRED_WALK_FORWARD_SPLITS = 3
REQUIRED_LEFT_TAIL_WINDOWS = 2
PREFERRED_SINGLE_SLOT_RISK_PCT = 15.0

REFERENCE_LINKS = [
    "Look-ahead bias / point-in-time data: https://www.pfolio.io/academy/look-ahead-bias",
    "Purged cross-validation overview: https://ml4trading.io/docs/diagnostic/methods/cpcv/",
    "Walk-forward validation overview: https://docs.skelfresearch.com/sigc/backtesting/walk-forward/",
    "Aspect Capital diversification in trend following: https://www.aspectcapital.com/insight/diversification-trend-following/",
    "Commodity trend-following diversification paper: https://papers.ssrn.com/sol3/Delivery.cfm/4871376.pdf?abstractid=4871376",
]


def _now_cst() -> datetime:
    return datetime.now(timezone(timedelta(hours=8)))


def _fmt_cst(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S CST")


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
        number = float(value)
        return None if math.isnan(number) or math.isinf(number) else number
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
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


def _split_csv_cell(value: Any) -> list[str]:
    if pd.isna(value):
        return []
    return [item.strip() for item in str(value).split(",") if item.strip()]


def _safe_ratio(current: float, required: float) -> float:
    if required <= 0:
        return 1.0 if current >= required else 0.0
    return max(0.0, min(1.0, float(current) / float(required)))


def _months_observed(raw: pd.DataFrame, product: str) -> int:
    if raw.empty or "received_at_local" not in raw.columns:
        return 0
    product_raw = raw[raw["product_vt_symbol"].astype(str).eq(product)].copy()
    if product_raw.empty:
        return 0
    parsed = pd.to_datetime(product_raw["received_at_local"].astype(str).str.replace(" CST", "", regex=False), errors="coerce")
    months = parsed.dt.strftime("%Y-%m").dropna().unique()
    return int(len(months))


def _family_products(family_rows: pd.DataFrame, product_summary: pd.DataFrame) -> dict[str, list[str]]:
    products_by_family: dict[str, list[str]] = {}
    for _, row in family_rows.iterrows():
        family = str(row["product_family"])
        products = _split_csv_cell(row.get("candidate_products", ""))
        if not products:
            products = product_summary.loc[
                product_summary["product_family"].astype(str).eq(family),
                "product_vt_symbol",
            ].astype(str).tolist()
        products_by_family[family] = products
    return products_by_family


def build_product_protocol(
    raw: pd.DataFrame,
    product_summary: pd.DataFrame,
    source_delta: pd.DataFrame,
    p2_families: pd.DataFrame,
) -> pd.DataFrame:
    product_summary = product_summary.copy()
    source_delta = source_delta.copy()
    p2_family_names = set(p2_families["product_family"].astype(str))
    product_summary = product_summary[product_summary["product_family"].astype(str).isin(p2_family_names)].copy()

    for column in [
        "fetched_ok_rows",
        "event_auto_monitor_rows",
        "history_selector_rows",
        "event_signal_ready_rows",
        "total_bytes",
        "pit_received_dates",
    ]:
        product_summary[column] = _num(product_summary, column)
    for column in [
        "stage626_route_ready_rows",
        "stage626_http_412_rows",
        "stage626_http_404_rows",
    ]:
        source_delta[column] = _num(source_delta, column)

    merged = product_summary.merge(
        source_delta[
            [
                "product_vt_symbol",
                "stage626_route_ready_rows",
                "stage626_http_412_rows",
                "stage626_http_404_rows",
                "source_blocker",
            ]
        ],
        on="product_vt_symbol",
        how="left",
    )
    for column in [
        "stage626_route_ready_rows",
        "stage626_http_412_rows",
        "stage626_http_404_rows",
    ]:
        merged[column] = _num(merged, column)
    merged["source_blocker"] = merged["source_blocker"].fillna("PIT_depth/live_TCA/predictive_signal")

    rows: list[dict[str, Any]] = []
    for _, row in merged.iterrows():
        product = str(row["product_vt_symbol"])
        family = str(row["product_family"])
        months_observed = _months_observed(raw, product)
        pit_dates = int(row["pit_received_dates"])
        event_rows = int(row["event_auto_monitor_rows"])
        fetched_rows = int(row["fetched_ok_rows"])
        selector_rows = int(row["history_selector_rows"] + row["event_signal_ready_rows"])
        czce_block_rows = int(row["stage626_http_412_rows"] + row["stage626_http_404_rows"])

        current_progress = {
            "pit_dates_progress": _safe_ratio(pit_dates, REQUIRED_PIT_DATES),
            "pit_months_progress": _safe_ratio(months_observed, REQUIRED_PIT_MONTHS),
            "event_monitor_progress": _safe_ratio(event_rows, 1),
            "episode_progress": 0.0,
            "walk_forward_progress": 0.0,
            "left_tail_progress": 0.0,
            "live_tca_progress": 0.0,
            "selector_progress": _safe_ratio(selector_rows, 1),
        }
        blocker_parts = []
        if pit_dates < REQUIRED_PIT_DATES:
            blocker_parts.append(f"PIT_dates {pit_dates}/{REQUIRED_PIT_DATES}")
        if months_observed < REQUIRED_PIT_MONTHS:
            blocker_parts.append(f"PIT_months {months_observed}/{REQUIRED_PIT_MONTHS}")
        if event_rows <= 0:
            blocker_parts.append("event_monitor_missing")
        if czce_block_rows > 0:
            blocker_parts.append(f"CZCE_blocked_rows={czce_block_rows}")
        blocker_parts.extend(["episodes 0/3", "walk_forward 0/3", "live_TCA 0/3", "selector 0"])

        rows.append(
            {
                "product_family": family,
                "product_vt_symbol": product,
                "source_rows": int(row["rows"]),
                "fetched_ok_rows": fetched_rows,
                "event_auto_monitor_rows": event_rows,
                "raw_bytes": int(row["total_bytes"]),
                "pit_received_dates": pit_dates,
                "pit_months_observed": months_observed,
                "required_pit_dates": REQUIRED_PIT_DATES,
                "required_pit_months": REQUIRED_PIT_MONTHS,
                "verified_independent_episodes": 0,
                "required_independent_episodes": REQUIRED_EPISODES_PER_FAMILY,
                "walk_forward_splits_passed": 0,
                "required_walk_forward_splits": REQUIRED_WALK_FORWARD_SPLITS,
                "left_tail_windows_passed": 0,
                "required_left_tail_windows": REQUIRED_LEFT_TAIL_WINDOWS,
                "live_tca_samples": 0,
                "required_live_tca_samples": REQUIRED_LIVE_TCA_PER_PRODUCT,
                "history_selector_rows": int(row["history_selector_rows"]),
                "event_signal_ready_rows": int(row["event_signal_ready_rows"]),
                "czce_route_ready_rows": int(row["stage626_route_ready_rows"]),
                "czce_block_rows": czce_block_rows,
                "promotion_ready": 0,
                "paper_or_whitelist_allowed": 0,
                "allowed_incremental_budget_pct": 0.0,
                "protocol_progress_pct": round(float(np.mean(list(current_progress.values()))) * 100.0, 4),
                "primary_blockers": "; ".join(blocker_parts),
            }
        )
    return pd.DataFrame(rows)


def build_family_protocol(product_protocol: pd.DataFrame, p2_families: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    p2 = p2_families.copy()
    for column in ["max_abs_core_corr", "slot_total_pnl_sum"]:
        p2[column] = _num(p2, column)
    for _, family_row in p2.iterrows():
        family = str(family_row["product_family"])
        group = product_protocol[product_protocol["product_family"].astype(str).eq(family)]
        if group.empty:
            continue
        min_pit_dates = int(group["pit_received_dates"].min())
        min_pit_months = int(group["pit_months_observed"].min())
        total_event_rows = int(group["event_auto_monitor_rows"].sum())
        total_czce_blocks = int(group["czce_block_rows"].sum())
        min_progress = float(group["protocol_progress_pct"].min())
        rows.append(
            {
                "product_family": family,
                "candidate_products": str(family_row["candidate_products"]),
                "updated_priority": str(family_row["updated_priority"]),
                "max_abs_core_corr": float(family_row["max_abs_core_corr"]),
                "slot_total_pnl_sum": float(family_row["slot_total_pnl_sum"]),
                "family_pit_dates_min": min_pit_dates,
                "family_pit_months_min": min_pit_months,
                "family_event_auto_monitor_rows": total_event_rows,
                "family_czce_block_rows": total_czce_blocks,
                "verified_independent_episodes": 0,
                "required_independent_episodes": REQUIRED_EPISODES_PER_FAMILY,
                "selector_protocol_ready": 0,
                "live_tca_ready": 0,
                "promotion_ready": 0,
                "allowed_incremental_budget_pct": 0.0,
                "family_protocol_progress_pct": min_progress,
                "next_evidence_unit": "future received_at raw_hash + independent trend episode + TCA",
            }
        )
    return pd.DataFrame(rows)


def build_episode_rules() -> pd.DataFrame:
    rows = [
        {
            "rule_id": "pit_source_integrity",
            "required": f">={REQUIRED_PIT_DATES} received_at dates and >={REQUIRED_PIT_MONTHS} calendar months",
            "why": "avoid backfilled/revised fundamental or sentiment data leaking into history.",
            "current_status": "not_met",
            "promotion_effect": "without this, no selector or paper.",
        },
        {
            "rule_id": "independent_trend_episode",
            "required": f">={REQUIRED_EPISODES_PER_FAMILY} non-overlapping episodes per family",
            "why": "one lucky commodity move is not an independent risk slot.",
            "current_status": "not_met",
            "promotion_effect": "only after episodes can P2 request P1 review.",
        },
        {
            "rule_id": "fixed_protocol_before_signal",
            "required": "event definition, direction mapping, hold windows and embargo frozen before scoring",
            "why": "prevent choosing event windows after seeing price outcomes.",
            "current_status": "not_met",
            "promotion_effect": "required before any predictive audit.",
        },
        {
            "rule_id": "purged_walk_forward_selector",
            "required": f">={REQUIRED_WALK_FORWARD_SPLITS} walk-forward splits with event-window purge/embargo",
            "why": "avoid overlapping event labels inflating selector IC.",
            "current_status": "not_met",
            "promotion_effect": "required before paper selector.",
        },
        {
            "rule_id": "holding_experience_left_tail",
            "required": f"63d and 126d p10 not worse than Stage526 across >={REQUIRED_LEFT_TAIL_WINDOWS} windows",
            "why": "the goal is better any-start 3/6 month experience, not just total return.",
            "current_status": "not_met",
            "promotion_effect": "required before risk budget.",
        },
        {
            "rule_id": "live_tca_samples",
            "required": f">={REQUIRED_LIVE_TCA_PER_PRODUCT} live/independent TCA samples per product",
            "why": "source edge is irrelevant if the product cannot be traded without execution bias.",
            "current_status": "not_met",
            "promotion_effect": "required before paper or whitelist.",
        },
        {
            "rule_id": "fail_closed_budget",
            "required": "incremental budget = 0 until all previous gates pass",
            "why": "monitoring evidence must not become implicit trading permission.",
            "current_status": "met",
            "promotion_effect": "keeps research safe while evidence accumulates.",
        },
    ]
    return pd.DataFrame(rows)


def build_promotion_gates(product_protocol: pd.DataFrame, family_protocol: pd.DataFrame) -> pd.DataFrame:
    min_pit_dates = int(product_protocol["pit_received_dates"].min()) if not product_protocol.empty else 0
    min_pit_months = int(product_protocol["pit_months_observed"].min()) if not product_protocol.empty else 0
    min_event_monitor = int(product_protocol["event_auto_monitor_rows"].min()) if not product_protocol.empty else 0
    max_budget = float(product_protocol["allowed_incremental_budget_pct"].max()) if not product_protocol.empty else 0.0
    total_episodes = int(family_protocol["verified_independent_episodes"].sum()) if not family_protocol.empty else 0
    total_live_tca = int(product_protocol["live_tca_samples"].sum()) if not product_protocol.empty else 0
    total_selector_rows = int(
        product_protocol["history_selector_rows"].sum() + product_protocol["event_signal_ready_rows"].sum()
    ) if not product_protocol.empty else 0
    total_ready = int(family_protocol["promotion_ready"].sum()) if not family_protocol.empty else 0

    rows = [
        {
            "gate": "pit_dates_reach_20",
            "passed": int(min_pit_dates >= REQUIRED_PIT_DATES),
            "current": min_pit_dates,
            "required": REQUIRED_PIT_DATES,
            "note": "minimum across P2 products.",
        },
        {
            "gate": "pit_months_reach_12",
            "passed": int(min_pit_months >= REQUIRED_PIT_MONTHS),
            "current": min_pit_months,
            "required": REQUIRED_PIT_MONTHS,
            "note": "calendar span matters more than same-day rows.",
        },
        {
            "gate": "all_products_have_event_monitor",
            "passed": int(min_event_monitor >= 1),
            "current": min_event_monitor,
            "required": ">=1 per product",
            "note": "ag currently has only daily data, not event monitor.",
        },
        {
            "gate": "independent_episodes_reach_3_per_family",
            "passed": int(total_episodes >= REQUIRED_EPISODES_PER_FAMILY * len(family_protocol)),
            "current": total_episodes,
            "required": REQUIRED_EPISODES_PER_FAMILY * len(family_protocol),
            "note": "future evidence only; no historical promotion.",
        },
        {
            "gate": "selector_rows_still_zero",
            "passed": int(total_selector_rows == 0),
            "current": total_selector_rows,
            "required": 0,
            "note": "lock discipline: source rows are not selector rows.",
        },
        {
            "gate": "live_tca_samples_reach_product_minimum",
            "passed": int(total_live_tca >= REQUIRED_LIVE_TCA_PER_PRODUCT * len(product_protocol)),
            "current": total_live_tca,
            "required": REQUIRED_LIVE_TCA_PER_PRODUCT * len(product_protocol),
            "note": "required before any paper/whitelist.",
        },
        {
            "gate": "promotion_ready_families_zero_now",
            "passed": int(total_ready == 0),
            "current": total_ready,
            "required": 0,
            "note": "P2 must remain monitor-only now.",
        },
        {
            "gate": "incremental_budget_zero_now",
            "passed": int(max_budget == 0.0),
            "current": f"{max_budget:.2f}%",
            "required": "0%",
            "note": "no hidden risk budget allocation.",
        },
    ]
    return pd.DataFrame(rows)


def write_report(
    generated_at: datetime,
    product_protocol: pd.DataFrame,
    family_protocol: pd.DataFrame,
    episode_rules: pd.DataFrame,
    gates: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    lines = [
        "# Stage628 P2 Forward Episode Protocol",
        "",
        f"- line_id: `{LINE_ID}`",
        f"- generated_at: `{_fmt_cst(generated_at)}`",
        f"- decision: `{decision['decision']}`",
        "- stage nature: protocol and current-gap audit only; no strategy replay, no selector, no paper whitelist, no CTP/order path.",
        "",
        "## External Research And Judgement",
        "",
        "References:",
        *[f"- {item}" for item in REFERENCE_LINKS],
        "",
        "Judgement:",
        "- PIT source rows must be accumulated before any historical selector is tested.",
        "- Event and trend episodes must be non-overlapping and scored with frozen definitions.",
        "- P2 can become an independent risk slot only after edge, holding experience and live TCA evidence all pass.",
        "",
        "## Key Results",
        "",
        f"- protocol products: `{decision['protocol_products']}`",
        f"- protocol families: `{decision['protocol_families']}`",
        f"- promotion ready families now: `{decision['promotion_ready_families_now']}`",
        f"- deployable budget now: `{decision['deployable_budget_now_pct']:.2f}%`",
        f"- hard gates: `{decision['hard_gates_passed']}/{decision['hard_gates_total']}`",
        "",
        "## Product Protocol Board",
        "",
        _md_table(
            product_protocol,
            [
                "product_family",
                "product_vt_symbol",
                "fetched_ok_rows",
                "event_auto_monitor_rows",
                "pit_received_dates",
                "pit_months_observed",
                "verified_independent_episodes",
                "live_tca_samples",
                "protocol_progress_pct",
                "primary_blockers",
            ],
            max_rows=20,
        ),
        "",
        "## Family Protocol Board",
        "",
        _md_table(family_protocol, max_rows=20),
        "",
        "## Episode Rules",
        "",
        _md_table(episode_rules, max_rows=20),
        "",
        "## Gates",
        "",
        _md_table(gates, max_rows=20),
        "",
        "## Visual Review Checklist",
        "",
        "- Product heatmap should show source/PIT progress separately from episode/TCA/selector zeros.",
        "- Family progress bars should make the gap to 100% visible rather than implying readiness.",
        "- Gate panel should show true promotion blockers in red and lock-discipline gates in green.",
        "- Product source bars should expose ag's event-monitor gap and soft_agri's CZCE route block.",
        "",
        "## Output Files",
        "",
        f"- product protocol: `{PRODUCT_PROTOCOL_PATH}`",
        f"- family protocol: `{FAMILY_PROTOCOL_PATH}`",
        f"- episode rules: `{EPISODE_RULES_PATH}`",
        f"- promotion gates: `{PROMOTION_GATES_PATH}`",
        f"- decision: `{DECISION_PATH}`",
        f"- chart: `{CHART_PATH}`",
        "",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def plot_chart(product_protocol: pd.DataFrame, family_protocol: pd.DataFrame, gates: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(18, 12), constrained_layout=True)
    fig.suptitle("Stage628 P2 forward episode protocol: source monitor only, promotion locked", fontsize=16)

    ax = axes[0, 0]
    metric_cols = [
        ("pit_dates", "pit_received_dates", REQUIRED_PIT_DATES),
        ("pit_months", "pit_months_observed", REQUIRED_PIT_MONTHS),
        ("event_monitor", "event_auto_monitor_rows", 1),
        ("episodes", "verified_independent_episodes", REQUIRED_EPISODES_PER_FAMILY),
        ("selector", "history_selector_rows", 1),
        ("live_tca", "live_tca_samples", REQUIRED_LIVE_TCA_PER_PRODUCT),
    ]
    matrix = []
    products = product_protocol["product_vt_symbol"].astype(str).tolist()
    for _, row in product_protocol.iterrows():
        matrix.append([_safe_ratio(float(row[col]), float(req)) for _, col, req in metric_cols])
    matrix_arr = np.array(matrix, dtype=float)
    im = ax.imshow(matrix_arr, cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(np.arange(len(metric_cols)))
    ax.set_xticklabels([label for label, _, _ in metric_cols], rotation=30, ha="right")
    ax.set_yticks(np.arange(len(products)))
    ax.set_yticklabels(products)
    for i in range(matrix_arr.shape[0]):
        for j in range(matrix_arr.shape[1]):
            ax.text(j, i, f"{matrix_arr[i, j]*100:.0f}%", ha="center", va="center", fontsize=8)
    ax.set_title("Product evidence progress vs protocol")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)

    ax = axes[0, 1]
    family_protocol = family_protocol.sort_values("family_protocol_progress_pct")
    colors = ["#f58518" if value > 0 else "#e45756" for value in family_protocol["family_protocol_progress_pct"]]
    ax.barh(family_protocol["product_family"], family_protocol["family_protocol_progress_pct"], color=colors)
    ax.axvline(100, color="#54a24b", linestyle="--", linewidth=1.2)
    for idx, row in family_protocol.reset_index(drop=True).iterrows():
        ax.text(row["family_protocol_progress_pct"] + 1, idx, f"{row['family_protocol_progress_pct']:.1f}%", va="center", fontsize=9)
    ax.set_xlim(0, 105)
    ax.set_xlabel("protocol progress %")
    ax.set_title("Family progress: low source progress is not promotion")

    ax = axes[1, 0]
    x = np.arange(len(products))
    width = 0.22
    ax.bar(x - width, product_protocol["fetched_ok_rows"], width, label="fetched ok", color="#54a24b")
    ax.bar(x, product_protocol["event_auto_monitor_rows"], width, label="event monitor", color="#4c78a8")
    ax.bar(x + width, product_protocol["czce_block_rows"], width, label="CZCE blocked", color="#e45756")
    ax.set_xticks(x)
    ax.set_xticklabels(products)
    ax.set_ylabel("rows")
    ax.set_title("Source health: monitor rows and route blockers")
    ax.legend(loc="upper left")

    ax = axes[1, 1]
    gate_colors = ["#54a24b" if bool(row["passed"]) else "#e45756" for _, row in gates.iterrows()]
    ax.barh(gates["gate"], [1] * len(gates), color=gate_colors)
    for idx, row in gates.reset_index(drop=True).iterrows():
        ax.text(0.02, idx, str(row["current"]), va="center", ha="left", color="white", fontsize=9, fontweight="bold")
    ax.set_xlim(0, 1)
    ax.set_xticks([])
    ax.set_title("Promotion gates: red = missing evidence, green = lock held")

    CHART_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def main() -> None:
    generated_at = _now_cst()
    raw = _read_csv(STAGE625_RAW_LEDGER)
    product_summary = _read_csv(STAGE625_PRODUCT_SUMMARY)
    family_reprioritization = _read_csv(STAGE627_FAMILY_REPRIORITIZATION)
    source_delta = _read_csv(STAGE627_SOURCE_DELTA)

    p2_families = family_reprioritization[
        family_reprioritization["updated_priority"].astype(str).str.startswith("P2")
    ].copy()
    product_protocol = build_product_protocol(raw, product_summary, source_delta, p2_families)
    family_protocol = build_family_protocol(product_protocol, p2_families)
    episode_rules = build_episode_rules()
    gates = build_promotion_gates(product_protocol, family_protocol)

    promotion_ready_families_now = int(_num(family_protocol, "promotion_ready").sum())
    deployable_budget_now_pct = float(_num(product_protocol, "allowed_incremental_budget_pct").max()) if not product_protocol.empty else 0.0
    hard_gates_passed = int(_num(gates, "passed").sum())
    hard_gates_total = int(len(gates))
    decision_label = "p2_forward_episode_protocol_ready_current_evidence_insufficient"
    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at_cst": _fmt_cst(generated_at),
        "decision": decision_label,
        "promotion_allowed": False,
        "paper_selector_allowed": False,
        "trading_whitelist_allowed": False,
        "protocol_products": int(len(product_protocol)),
        "protocol_families": int(len(family_protocol)),
        "promotion_ready_families_now": promotion_ready_families_now,
        "deployable_budget_now_pct": deployable_budget_now_pct,
        "required_pit_dates": REQUIRED_PIT_DATES,
        "required_pit_months": REQUIRED_PIT_MONTHS,
        "required_episodes_per_family": REQUIRED_EPISODES_PER_FAMILY,
        "required_live_tca_per_product": REQUIRED_LIVE_TCA_PER_PRODUCT,
        "hard_gates_passed": hard_gates_passed,
        "hard_gates_total": hard_gates_total,
        "summary": (
            "P2+source families now have an explicit forward episode protocol, but current evidence is only one PIT date, "
            "zero verified episodes and zero live TCA; no paper or risk budget is allowed."
        ),
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    product_protocol.to_csv(PRODUCT_PROTOCOL_PATH, index=False, encoding="utf-8-sig")
    family_protocol.to_csv(FAMILY_PROTOCOL_PATH, index=False, encoding="utf-8-sig")
    episode_rules.to_csv(EPISODE_RULES_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(PROMOTION_GATES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(generated_at, product_protocol, family_protocol, episode_rules, gates, decision)
    plot_chart(product_protocol, family_protocol, gates)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
