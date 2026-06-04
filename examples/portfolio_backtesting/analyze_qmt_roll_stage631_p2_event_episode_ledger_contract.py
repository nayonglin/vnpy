from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
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
MODEL_TAG = "stage631_p2_event_episode_ledger_contract_v1"
OUTPUT_PREFIX = "qmt_roll_stage631_p2_event_episode_ledger_contract"

MASTER_PIT_LEDGER_PATH = OUTPUT_DIR / "qmt_roll_p2_public_source_master_pit_ledger.csv"
EVENT_SEED_LEDGER_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_seed_ledger_{MODEL_TAG}.csv"
EPISODE_CONTRACT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_episode_contract_{MODEL_TAG}.csv"
PRODUCT_PROGRESS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_episode_progress_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

REQUIRED_PIT_DATES = 20
REQUIRED_PIT_MONTHS = 12
REQUIRED_INDEPENDENT_EPISODES_PER_FAMILY = 3
REQUIRED_WALK_FORWARD_SPLITS = 3
REQUIRED_LIVE_TCA_PER_PRODUCT = 3
REQUIRED_LEFT_TAIL_WINDOWS = 2

EVENT_SEED_CLASSES = {
    "public_html_event_release_page",
}
EVENT_SEED_TYPES = {
    "crop_progress_release_page",
    "cotton_wool_outlook_release_page",
    "wasde_esmis_release_page",
}
METHODOLOGY_TYPES = {
    "crop_progress_methodology_page",
    "esmis_api_documentation",
}
PRODUCTS_IN_SCOPE = ["ag.SHFE", "CY.CZCE", "SR.CZCE"]

REFERENCES = [
    "Event window methodology: https://eventstudy.de/docs/window-selection",
    "Event data preparation: https://eventstudy.de/docs/data-preparation",
    "Overlapping event window correlation: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3167271",
    "Purged cross-validation overview: https://en.wikipedia.org/wiki/Purged_cross-validation",
    "USDA WASDE release process: https://www.usda.gov/about-usda/general-information/staff-offices/office-chief-economist/world-agricultural-outlook-board/wasde-report",
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


def _split_products(value: Any) -> list[str]:
    return [item.strip() for item in str(value).split(",") if item.strip()]


def _hash_short(text: str, length: int = 12) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


def _prepare_master(master: pd.DataFrame) -> pd.DataFrame:
    frame = master.copy()
    for column in [
        "product_vt_symbol",
        "product_family",
        "source_name",
        "source_url",
        "final_url",
        "source_class",
        "event_family",
        "event_type",
        "monitor_frequency",
        "received_at_utc",
        "received_at_local",
        "raw_sha256",
        "linked_text_sha256",
        "hash_combo",
        "dedupe_key",
    ]:
        frame[column] = _str(frame, column)
    for column in [
        "event_auto_monitor_validated",
        "usable_for_forward_monitor",
        "usable_for_history_selector",
        "event_signal_ready",
        "paper_or_whitelist_allowed",
        "any_raw_hash_present",
    ]:
        frame[column] = _num(frame, column).astype(int)
    frame["pit_date"] = frame["received_at_utc"].str.slice(0, 10)
    frame["pit_month"] = frame["received_at_utc"].str.slice(0, 7)
    frame["is_event_seed"] = (
        frame["usable_for_forward_monitor"].eq(1)
        & frame["any_raw_hash_present"].eq(1)
        & frame["event_auto_monitor_validated"].eq(1)
        & frame["source_class"].isin(EVENT_SEED_CLASSES)
        & frame["event_type"].isin(EVENT_SEED_TYPES)
        & frame["usable_for_history_selector"].eq(0)
        & frame["paper_or_whitelist_allowed"].eq(0)
    ).astype(int)
    frame["is_methodology_support"] = (
        frame["usable_for_forward_monitor"].eq(1)
        & frame["any_raw_hash_present"].eq(1)
        & frame["event_type"].isin(METHODOLOGY_TYPES)
    ).astype(int)
    return frame


def _build_event_seed_ledger(master: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    seed_rows = master[master["is_event_seed"].eq(1)].copy()
    for _, row in seed_rows.iterrows():
        for product in _split_products(row["product_vt_symbol"]):
            event_key = "||".join(
                [
                    product,
                    row["event_type"],
                    row["received_at_utc"],
                    row["hash_combo"],
                ]
            )
            rows.append(
                {
                    "event_id": f"evt_{_hash_short(event_key)}",
                    "line_id": LINE_ID,
                    "product_family": row["product_family"],
                    "product_vt_symbol": product,
                    "source_name": row["source_name"],
                    "source_url": row["source_url"],
                    "final_url": row["final_url"],
                    "source_class": row["source_class"],
                    "event_family": row["event_family"],
                    "event_type": row["event_type"],
                    "monitor_frequency": row["monitor_frequency"],
                    "received_at_utc": row["received_at_utc"],
                    "received_at_local": row["received_at_local"],
                    "pit_date": row["pit_date"],
                    "pit_month": row["pit_month"],
                    "raw_sha256": row["raw_sha256"],
                    "linked_text_sha256": row["linked_text_sha256"],
                    "hash_combo": row["hash_combo"],
                    "master_dedupe_key": row["dedupe_key"],
                    "event_seed_status": "seed_only_not_verified_episode",
                    "entry_clock_rule": "next_tradable_session_after_received_at_utc",
                    "episode_window_rule": "evaluate post-event 20/63/126 trading-day windows after enough forward history exists",
                    "estimation_window_rule": "use 120-250 trading days ending 10-30 trading days before event when predictive audit starts",
                    "non_overlap_rule": "same product/event family windows must be purged or manually de-duplicated before independent episode count",
                    "selector_allowed": 0,
                    "paper_or_whitelist_allowed": 0,
                    "verified_independent_episode": 0,
                    "ready_for_predictive_audit": 0,
                }
            )
    return pd.DataFrame(rows)


def _build_episode_contract(event_seed: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    contract_items = [
        ("pit_depth", f">={REQUIRED_PIT_DATES} PIT dates and >={REQUIRED_PIT_MONTHS} months per product/family"),
        ("event_seed", "official/public event release source with raw hash and received_at"),
        ("event_window", "post-event 20/63/126 trading-day outcome windows; no same-day hindsight entry"),
        ("estimation_window", "120-250 trading-day pre-event window ending 10-30 trading days before event"),
        ("overlap_purge", "purge overlapping same-product/event-family windows and apply embargo before model validation"),
        ("independent_episode", f">={REQUIRED_INDEPENDENT_EPISODES_PER_FAMILY} non-overlapping trend episodes per family"),
        ("walk_forward", f">={REQUIRED_WALK_FORWARD_SPLITS} purged walk-forward splits"),
        ("left_tail", f">={REQUIRED_LEFT_TAIL_WINDOWS} left-tail windows must not deteriorate"),
        ("live_tca", f">={REQUIRED_LIVE_TCA_PER_PRODUCT} valid live/independent TCA samples per product"),
        ("selector_lock", "history selector, paper and trading whitelist remain zero until all gates pass"),
    ]
    for order, (gate, rule) in enumerate(contract_items, start=1):
        rows.append(
            {
                "contract_order": order,
                "contract_gate": gate,
                "rule": rule,
                "current_status": "contract_defined_not_satisfied" if gate not in {"event_seed", "selector_lock"} else "satisfied_for_seed_or_lock",
                "evidence_source": "Stage631 event seed ledger" if gate == "event_seed" else "future audits",
            }
        )
    if event_seed.empty:
        rows.append(
            {
                "contract_order": len(rows) + 1,
                "contract_gate": "seed_absent",
                "rule": "no event seed rows found; cannot proceed to episode ledger",
                "current_status": "failed",
                "evidence_source": "Stage330 master PIT ledger",
            }
        )
    return pd.DataFrame(rows)


def _product_progress(master: pd.DataFrame, event_seed: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for product in PRODUCTS_IN_SCOPE:
        product_master_parts = []
        for _, row in master.iterrows():
            if product in _split_products(row["product_vt_symbol"]):
                product_master_parts.append(row)
        product_master = pd.DataFrame(product_master_parts)
        product_seed = event_seed[event_seed["product_vt_symbol"].eq(product)] if not event_seed.empty else pd.DataFrame()
        family = product_master["product_family"].iloc[0] if not product_master.empty else ""
        pit_dates = int(product_master["pit_date"].nunique()) if not product_master.empty else 0
        pit_months = int(product_master["pit_month"].nunique()) if not product_master.empty else 0
        event_seed_rows = int(len(product_seed))
        event_families = int(product_seed["event_family"].nunique()) if not product_seed.empty else 0
        methodology_support_rows = int(product_master["is_methodology_support"].sum()) if not product_master.empty else 0
        verified_episodes = int(product_seed["verified_independent_episode"].sum()) if not product_seed.empty else 0
        same_day_groups = int(product_seed.groupby(["pit_date"]).size().gt(1).sum()) if not product_seed.empty else 0
        same_family_groups = int(product_seed.groupby(["pit_date", "event_family"]).size().gt(1).sum()) if not product_seed.empty else 0
        overlap_groups = max(same_day_groups, same_family_groups)
        progress_pct = (
            min(pit_dates / REQUIRED_PIT_DATES, 1.0) * 25
            + min(pit_months / REQUIRED_PIT_MONTHS, 1.0) * 15
            + min(event_seed_rows / 1, 1.0) * 25
            + min(methodology_support_rows / 1, 1.0) * 10
            + min(verified_episodes / REQUIRED_INDEPENDENT_EPISODES_PER_FAMILY, 1.0) * 25
        )
        missing = []
        if pit_dates < REQUIRED_PIT_DATES:
            missing.append(f"pit_dates {pit_dates}/{REQUIRED_PIT_DATES}")
        if pit_months < REQUIRED_PIT_MONTHS:
            missing.append(f"pit_months {pit_months}/{REQUIRED_PIT_MONTHS}")
        if event_seed_rows == 0:
            missing.append("event_seed")
        if verified_episodes < REQUIRED_INDEPENDENT_EPISODES_PER_FAMILY:
            missing.append(f"verified_episodes {verified_episodes}/{REQUIRED_INDEPENDENT_EPISODES_PER_FAMILY}")
        missing.extend(["predictive_audit", "live_tca"])
        rows.append(
            {
                "product_family": family,
                "product_vt_symbol": product,
                "pit_dates": pit_dates,
                "pit_months": pit_months,
                "event_seed_rows": event_seed_rows,
                "event_families": event_families,
                "methodology_support_rows": methodology_support_rows,
                "overlap_groups": overlap_groups,
                "same_day_event_groups": same_day_groups,
                "same_family_event_groups": same_family_groups,
                "verified_independent_episodes": verified_episodes,
                "required_independent_episodes": REQUIRED_INDEPENDENT_EPISODES_PER_FAMILY,
                "progress_pct": round(progress_pct, 4),
                "selector_rows": 0,
                "paper_or_whitelist_rows": 0,
                "missing_for_promotion": ",".join(missing),
                "status": "event_seed_contract_ready_selector_locked" if event_seed_rows > 0 else "event_seed_missing_selector_locked",
            }
        )
    return pd.DataFrame(rows)


def _gates(master: pd.DataFrame, event_seed: pd.DataFrame, progress: pd.DataFrame) -> pd.DataFrame:
    event_products = int(progress.loc[progress["event_seed_rows"].gt(0), "product_vt_symbol"].nunique()) if not progress.empty else 0
    min_pit_dates = int(progress["pit_dates"].min()) if not progress.empty else 0
    verified_episode_total = int(progress["verified_independent_episodes"].sum()) if not progress.empty else 0
    selector_rows = int(progress["selector_rows"].sum()) if not progress.empty else 0
    paper_rows = int(progress["paper_or_whitelist_rows"].sum()) if not progress.empty else 0
    overlap_groups = int(progress["overlap_groups"].sum()) if not progress.empty else 0
    rows = [
        {
            "gate": "master_pit_ledger_present",
            "passed": int(not master.empty),
            "current": len(master),
            "required": ">0",
            "note": "Stage330 master PIT ledger is required.",
        },
        {
            "gate": "event_seed_rows_present",
            "passed": int(len(event_seed) > 0),
            "current": len(event_seed),
            "required": ">0",
            "note": "event seeds are source evidence, not alpha.",
        },
        {
            "gate": "soft_agri_event_products_covered",
            "passed": int(event_products >= 2),
            "current": event_products,
            "required": 2,
            "note": "CY/SR should have event seeds.",
        },
        {
            "gate": "ag_event_seed_missing_documented",
            "passed": int(progress.loc[progress["product_vt_symbol"].eq("ag.SHFE"), "event_seed_rows"].sum() == 0),
            "current": int(progress.loc[progress["product_vt_symbol"].eq("ag.SHFE"), "event_seed_rows"].sum()) if not progress.empty else 0,
            "required": 0,
            "note": "ag has source monitor but no event seed; keep it out of event selector.",
        },
        {
            "gate": "selector_rows_zero",
            "passed": int(selector_rows == 0),
            "current": selector_rows,
            "required": 0,
            "note": "event seeds must not enter selector.",
        },
        {
            "gate": "paper_whitelist_rows_zero",
            "passed": int(paper_rows == 0),
            "current": paper_rows,
            "required": 0,
            "note": "no paper or trading whitelist allowed.",
        },
        {
            "gate": "pit_dates_below_threshold_fail_closed",
            "passed": int(min_pit_dates < REQUIRED_PIT_DATES),
            "current": min_pit_dates,
            "required": f"<{REQUIRED_PIT_DATES}",
            "note": "one PIT date is not enough for predictive audit.",
        },
        {
            "gate": "verified_episodes_zero_fail_closed",
            "passed": int(verified_episode_total == 0),
            "current": verified_episode_total,
            "required": 0,
            "note": "no independent episode is verified yet.",
        },
        {
            "gate": "overlap_groups_not_independent",
            "passed": int(overlap_groups >= 0),
            "current": overlap_groups,
            "required": "tracked",
            "note": "overlap groups are tracked and cannot be counted as independent episodes.",
        },
    ]
    return pd.DataFrame(rows)


def _write_chart(event_seed: pd.DataFrame, progress: pd.DataFrame, gates: pd.DataFrame, contract: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    fig.suptitle("Stage631 P2 event episode contract: seeds exist, episodes not verified", fontsize=16)

    ax = axes[0, 0]
    x = np.arange(len(progress))
    ax.bar(x - 0.2, progress["event_seed_rows"], width=0.2, label="event seeds")
    ax.bar(x, progress["verified_independent_episodes"], width=0.2, label="verified episodes")
    ax.bar(x + 0.2, progress["pit_dates"], width=0.2, label="PIT dates")
    ax.axhline(REQUIRED_INDEPENDENT_EPISODES_PER_FAMILY, color="tab:red", linestyle="--", linewidth=1, label="3 episode gate")
    ax.set_xticks(x)
    ax.set_xticklabels(progress["product_vt_symbol"])
    ax.set_title("Event seed vs verified episode")
    ax.set_ylabel("count")
    ax.legend(loc="upper left", fontsize=8)

    ax = axes[0, 1]
    if event_seed.empty:
        ax.text(0.5, 0.5, "No event seeds", ha="center", va="center")
        ax.set_axis_off()
    else:
        seed_pivot = (
            event_seed.assign(value=1)
            .pivot_table(index="event_type", columns="product_vt_symbol", values="value", aggfunc="sum", fill_value=0)
            .reindex(columns=PRODUCTS_IN_SCOPE, fill_value=0)
        )
        image = ax.imshow(seed_pivot.values, aspect="auto", cmap="Greens", vmin=0, vmax=max(1, seed_pivot.values.max()))
        ax.set_xticks(np.arange(len(seed_pivot.columns)))
        ax.set_xticklabels(seed_pivot.columns)
        ax.set_yticks(np.arange(len(seed_pivot.index)))
        ax.set_yticklabels(seed_pivot.index, fontsize=8)
        ax.set_title("Event seed type coverage")
        for i in range(seed_pivot.shape[0]):
            for j in range(seed_pivot.shape[1]):
                ax.text(j, i, str(int(seed_pivot.values[i, j])), ha="center", va="center", fontsize=8)
        fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)

    ax = axes[1, 0]
    contract_view = contract.copy()
    contract_view["satisfied_flag"] = contract_view["current_status"].eq("satisfied_for_seed_or_lock").astype(int)
    colors = ["tab:green" if item == 1 else "tab:orange" for item in contract_view["satisfied_flag"]]
    ax.barh(contract_view["contract_gate"], contract_view["satisfied_flag"], color=colors)
    ax.set_xlim(0, 1)
    ax.set_title("Episode promotion contract status")
    ax.tick_params(axis="y", labelsize=8)

    ax = axes[1, 1]
    colors = ["tab:green" if int(item) == 1 else "tab:red" for item in gates["passed"]]
    ax.barh(gates["gate"], gates["passed"], color=colors)
    ax.set_xlim(0, 1)
    ax.set_title("Gates: green includes fail-closed locks")
    ax.set_xlabel("passed")
    ax.tick_params(axis="y", labelsize=8)
    for i, row in gates.iterrows():
        ax.text(0.02, i, str(row["current"]), va="center", ha="left", fontsize=8, color="white")

    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _write_report(
    generated_at: datetime,
    event_seed: pd.DataFrame,
    contract: pd.DataFrame,
    progress: pd.DataFrame,
    gates: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    lines = [
        "# Stage631 P2 Event Episode Ledger Contract Report",
        "",
        f"- generated_at_cst: `{_fmt_cst(generated_at)}`",
        f"- decision: `{decision['decision']}`",
        f"- master_pit_ledger: `{MASTER_PIT_LEDGER_PATH}`",
        "",
        "## External Research Judgement",
        "",
        "Event evidence must be separated from predictive labels. A USDA/ESMIS/ERS event seed only proves that a source was available at a timestamp; it does not prove an independent trend episode. Episode promotion requires non-overlapping windows, purged validation, left-tail checks and live TCA.",
        "",
        "References:",
        *[f"- {item}" for item in REFERENCES],
        "",
        "## Key Numbers",
        "",
        f"- event seed rows: `{decision['event_seed_rows']}`",
        f"- event products covered: `{decision['event_products_covered']}`",
        f"- verified independent episodes: `{decision['verified_independent_episodes']}`",
        f"- selector rows: `{decision['selector_rows']}`",
        f"- paper/whitelist rows: `{decision['paper_or_whitelist_rows']}`",
        f"- hard gates: `{decision['hard_gates_passed']}/{decision['hard_gates_total']}`",
        "",
        "## Product Progress",
        "",
        _md_table(progress),
        "",
        "## Event Seed Ledger",
        "",
        _md_table(event_seed, columns=["event_id", "product_vt_symbol", "event_type", "received_at_utc", "event_seed_status", "selector_allowed"]),
        "",
        "## Episode Contract",
        "",
        _md_table(contract),
        "",
        "## Gates",
        "",
        _md_table(gates),
        "",
        "## Interpretation",
        "",
        "- CY/SR have event seed evidence; ag still has no event seed.",
        "- Seed rows remain outside selector and paper.",
        "- Verified independent episodes remain zero because no post-event non-overlapping outcome/TCA audit has happened.",
        "- This stage is a contract bridge from source evidence to future predictive audit, not an alpha result.",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    generated_at = _now_cst()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    master = _prepare_master(_read_csv(MASTER_PIT_LEDGER_PATH))
    event_seed = _build_event_seed_ledger(master)
    contract = _build_episode_contract(event_seed)
    progress = _product_progress(master, event_seed)
    gates = _gates(master, event_seed, progress)

    event_seed.to_csv(EVENT_SEED_LEDGER_PATH, index=False, encoding="utf-8-sig")
    contract.to_csv(EPISODE_CONTRACT_PATH, index=False, encoding="utf-8-sig")
    progress.to_csv(PRODUCT_PROGRESS_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")

    event_products = int(progress.loc[progress["event_seed_rows"].gt(0), "product_vt_symbol"].nunique())
    verified_episodes = int(progress["verified_independent_episodes"].sum())
    selector_rows = int(progress["selector_rows"].sum())
    paper_rows = int(progress["paper_or_whitelist_rows"].sum())
    hard_gates_passed = int(gates["passed"].sum())
    hard_gates_total = int(len(gates))
    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at_cst": _fmt_cst(generated_at),
        "decision": "p2_event_episode_seed_contract_ready_selector_locked",
        "promotion_allowed": False,
        "paper_selector_allowed": False,
        "trading_whitelist_allowed": False,
        "event_seed_rows": int(len(event_seed)),
        "event_products_covered": event_products,
        "verified_independent_episodes": verified_episodes,
        "required_independent_episodes_per_family": REQUIRED_INDEPENDENT_EPISODES_PER_FAMILY,
        "selector_rows": selector_rows,
        "paper_or_whitelist_rows": paper_rows,
        "hard_gates_passed": hard_gates_passed,
        "hard_gates_total": hard_gates_total,
        "summary": "CY/SR public event seeds were converted into an episode ledger contract while ag remains event-missing and all selector/paper/trading paths remain locked.",
    }

    _write_chart(event_seed, progress, gates, contract)
    _write_report(generated_at, event_seed, contract, progress, gates, decision)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
