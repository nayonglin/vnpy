from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage649_ec_ine_futures_proxy_freshness_forensic_v1"
OUTPUT_PREFIX = "qmt_roll_stage649_ec_ine_futures_proxy_freshness_forensic"

LOCAL_INE_ROOT = PROJECT_DIR / "downloaded_futures" / "tqsdk_daily_2010_2026_04" / "INE"
STAGE633_PRODUCT_MAP = (
    OUTPUT_DIR
    / "qmt_roll_stage633_independent_risk_slot_correlation_map_product_map_stage633_independent_risk_slot_correlation_map_v1.csv"
)
STAGE647_PRODUCT_EVIDENCE = (
    OUTPUT_DIR / "qmt_roll_stage647_ec_ine_second_slot_source_probe_product_evidence_stage647_ec_ine_second_slot_source_probe_v1.csv"
)
SCFIS_MASTER_LEDGER = OUTPUT_DIR / "qmt_roll_ec_ine_scfis_master_pit_ledger.csv"

LOCAL_CONTRACTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_local_contracts_{MODEL_TAG}.csv"
OFFICIAL_GAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_contract_gap_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

OFFICIAL_REFERENCE_DATE = "2026-06-03"
LOCAL_DUMP_LABEL = "tqsdk_daily_2010_2026_04"

# Read-only AKShare/INE probe performed on 2026-06-04 after sandbox DNS failed.
# Source route: ak.futures_contract_info_ine(date="20260603").
OFFICIAL_EC_CONTRACTS_20260603: tuple[dict[str, Any], ...] = (
    {"contract": "ec2606", "listed_date": "2025-07-01", "expiry_date": "2026-06-29", "baseline_price": 1169.0},
    {"contract": "ec2607", "listed_date": "2026-02-10", "expiry_date": "2026-07-27", "baseline_price": 1537.3},
    {"contract": "ec2608", "listed_date": "2025-08-26", "expiry_date": "2026-08-31", "baseline_price": 1451.3},
    {"contract": "ec2609", "listed_date": "2026-02-10", "expiry_date": "2026-09-28", "baseline_price": 1609.5},
    {"contract": "ec2610", "listed_date": "2025-10-28", "expiry_date": "2026-10-26", "baseline_price": 1484.6},
    {"contract": "ec2611", "listed_date": "2026-05-26", "expiry_date": "2026-11-30", "baseline_price": 1891.0},
    {"contract": "ec2612", "listed_date": "2025-12-30", "expiry_date": "2026-12-28", "baseline_price": 1052.9},
    {"contract": "ec2703", "listed_date": "2026-03-31", "expiry_date": "2027-03-29", "baseline_price": 1840.7},
)

OFFICIAL_SOURCE_NOTES = (
    "INE EC product page confirms EC is SCFIS Europe futures and refers current index to Shanghai Shipping Exchange.",
    "INE English contract spec reports EC multiplier, trading hours, margin and cash settlement route.",
    "AKShare GitHub docs expose futures_contract_info_ine for INE contract reference data.",
    "GitHub search did not find a reliable dedicated SCFIS historical Python package; custom official raw-hash ledger remains required.",
)


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def _num(frame: pd.DataFrame, column: str, default: float = np.nan) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce").fillna(default)


def _date_string(value: Any) -> str:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return ""
    return ts.date().isoformat()


def _scan_file(path: Path) -> dict[str, Any]:
    try:
        frame = pd.read_csv(path, encoding="utf-8-sig")
    except Exception as exc:
        return {
            "contract": path.stem,
            "file_path": str(path),
            "read_ok": 0,
            "message": repr(exc),
            "raw_rows": 0,
            "tradable_rows": 0,
            "first_trade_date": "",
            "last_trade_date": "",
            "last_tradable_date": "",
            "sum_volume": 0.0,
            "max_volume": 0.0,
            "last_close": np.nan,
        }
    frame["trade_date"] = pd.to_datetime(frame.get("trade_date"), errors="coerce")
    frame["close"] = _num(frame, "close")
    frame["volume"] = _num(frame, "volume", 0.0)
    frame["close_oi"] = _num(frame, "close_oi", _num(frame, "open_interest", 0.0))
    frame = frame.dropna(subset=["trade_date", "close"]).copy()
    frame = frame[frame["close"].gt(0)]
    tradable = frame[(frame["volume"].gt(0)) | (frame["close_oi"].gt(0))].copy()
    return {
        "contract": path.stem,
        "file_path": str(path),
        "read_ok": 1,
        "message": "",
        "raw_rows": int(len(frame)),
        "tradable_rows": int(len(tradable)),
        "first_trade_date": _date_string(frame["trade_date"].min()) if not frame.empty else "",
        "last_trade_date": _date_string(frame["trade_date"].max()) if not frame.empty else "",
        "last_tradable_date": _date_string(tradable["trade_date"].max()) if not tradable.empty else "",
        "sum_volume": float(frame["volume"].sum()) if not frame.empty else 0.0,
        "max_volume": float(frame["volume"].max()) if not frame.empty else 0.0,
        "last_close": float(frame.sort_values("trade_date")["close"].iloc[-1]) if not frame.empty else np.nan,
    }


def _scan_local_ine_root() -> tuple[pd.DataFrame, str]:
    rows = []
    max_dates = []
    for path in sorted(LOCAL_INE_ROOT.glob("*.csv")):
        row = _scan_file(path)
        rows.append(row)
        ts = pd.to_datetime(row.get("last_tradable_date"), errors="coerce")
        if pd.notna(ts):
            max_dates.append(ts)
    root_max = max(max_dates).date().isoformat() if max_dates else ""
    return pd.DataFrame(rows), root_max


def _load_stage633_ec() -> dict[str, Any]:
    frame = _read_csv(STAGE633_PRODUCT_MAP)
    if frame.empty or "product_vt_symbol" not in frame.columns:
        return {}
    target = frame[frame["product_vt_symbol"].astype(str).eq("ec.INE")].copy()
    if target.empty:
        return {}
    return target.iloc[0].to_dict()


def _load_stage647_ec() -> dict[str, Any]:
    frame = _read_csv(STAGE647_PRODUCT_EVIDENCE)
    if frame.empty:
        return {}
    return frame.iloc[0].to_dict()


def _load_scfis_master_stats() -> dict[str, Any]:
    frame = _read_csv(SCFIS_MASTER_LEDGER)
    if frame.empty:
        return {"master_rows": 0, "collection_pit_dates": 0, "scfis_dates": 0, "latest_scfis_date": ""}
    pit_column = "collection_date_local" if "collection_date_local" in frame.columns else "received_pit_date"
    return {
        "master_rows": int(len(frame)),
        "collection_pit_dates": int(frame.get(pit_column, pd.Series(dtype=str)).astype(str).nunique()),
        "scfis_dates": int(frame.get("scfis_date", pd.Series(dtype=str)).astype(str).nunique()),
        "latest_scfis_date": str(frame.get("scfis_date", pd.Series(dtype=str)).astype(str).max()),
    }


def _build_official_gap(local_ec: pd.DataFrame, local_root_max_date: str) -> pd.DataFrame:
    official = pd.DataFrame(OFFICIAL_EC_CONTRACTS_20260603).copy()
    official["official_reference_date"] = OFFICIAL_REFERENCE_DATE
    official["listed_date"] = pd.to_datetime(official["listed_date"])
    official["expiry_date"] = pd.to_datetime(official["expiry_date"])
    local_lookup = local_ec.set_index("contract").to_dict("index") if not local_ec.empty else {}
    root_max = pd.to_datetime(local_root_max_date, errors="coerce")
    ref = pd.Timestamp(OFFICIAL_REFERENCE_DATE)

    rows = []
    for row in official.itertuples(index=False):
        local = local_lookup.get(row.contract, {})
        local_file_exists = int(bool(local))
        last_local = pd.to_datetime(local.get("last_tradable_date", ""), errors="coerce")
        listed_by_local_root_max = int(pd.notna(root_max) and row.listed_date <= root_max)
        if pd.notna(last_local):
            calendar_gap_to_ref = int((ref - last_local).days)
        else:
            calendar_gap_to_ref = 9999
        rows.append(
            {
                "contract": row.contract,
                "listed_date": row.listed_date.date().isoformat(),
                "expiry_date": row.expiry_date.date().isoformat(),
                "baseline_price": float(row.baseline_price),
                "official_reference_date": OFFICIAL_REFERENCE_DATE,
                "local_file_exists": local_file_exists,
                "local_last_tradable_date": _date_string(last_local),
                "local_tradable_rows": int(local.get("tradable_rows", 0) or 0),
                "calendar_gap_to_reference": calendar_gap_to_ref,
                "listed_by_local_root_max": listed_by_local_root_max,
                "missing_despite_listed_by_local_root_max": int(local_file_exists == 0 and listed_by_local_root_max == 1),
            }
        )
    return pd.DataFrame(rows)


def _build_gates(decision: dict[str, Any]) -> pd.DataFrame:
    rows = [
        ("official_ec_contract_list_obtained", 1, decision["official_active_contracts"], 1, "AKShare/INE read-only contract list was obtained."),
        ("local_ec_files_exist", int(decision["local_ec_contract_files"] > 0), decision["local_ec_contract_files"], 1, "Local EC files exist."),
        (
            "active_contract_file_coverage_ge_50pct",
            int(decision["active_contract_file_coverage_pct"] >= 50.0),
            round(decision["active_contract_file_coverage_pct"], 4),
            50.0,
            "At least half of current official EC contracts should have local files.",
        ),
        (
            "post_feb_2026_contract_downloaded",
            int(decision["post_feb_2026_local_contract_files"] > 0),
            decision["post_feb_2026_local_contract_files"],
            1,
            "Revised/post-Feb EC contracts must be present before proxy freshness can pass.",
        ),
        (
            "local_proxy_fresh_within_10d_reference",
            int(decision["calendar_gap_latest_local_ec_to_official_ref"] <= 10),
            decision["calendar_gap_latest_local_ec_to_official_ref"],
            10,
            "Local EC proxy should be within 10 calendar days of official reference date.",
        ),
        (
            "stage633_data_pass",
            int(decision["stage633_data_pass"] == 1),
            decision["stage633_data_pass"],
            1,
            "Stage633 data gate must pass.",
        ),
        (
            "stage633_watch_corr_pass",
            int(decision["stage633_watch_corr_pass"] == 1),
            decision["stage633_watch_corr_pass"],
            1,
            "EC remains only a watch-corr candidate, not strict low-corr.",
        ),
        (
            "scfis_master_pit_exists",
            int(decision["scfis_master_rows"] >= 1),
            decision["scfis_master_rows"],
            1,
            "SCFIS current index master PIT ledger exists.",
        ),
        (
            "selector_locked_fail_closed",
            int(decision["selector_rows"] == 0 and decision["paper_rows"] == 0 and decision["trading_whitelist_rows"] == 0),
            0,
            0,
            "No selector/paper/trading whitelist is allowed from this audit.",
        ),
    ]
    return pd.DataFrame(rows, columns=["gate", "passed", "current", "required", "note"])


def _write_chart(local_ec: pd.DataFrame, official_gap: pd.DataFrame, gates: pd.DataFrame, decision: dict[str, Any]) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    fig.suptitle("Stage649 ec.INE futures proxy freshness forensic: missing revised EC contracts", fontsize=15, weight="bold")

    ax = axes[0, 0]
    gap = official_gap.copy()
    gap["listed_dt"] = pd.to_datetime(gap["listed_date"])
    gap["expiry_dt"] = pd.to_datetime(gap["expiry_date"])
    y = np.arange(len(gap))
    for idx, row in gap.iterrows():
        color = "#5b8ff9" if row["local_file_exists"] else "#d9e6ff"
        ax.barh(
            idx,
            (row["expiry_dt"] - row["listed_dt"]).days,
            left=row["listed_dt"],
            height=0.55,
            color=color,
            edgecolor="#2f5597",
            alpha=0.85,
        )
        if row["local_file_exists"]:
            ax.scatter(pd.Timestamp(row["local_last_tradable_date"]), idx, color="#168038", marker="o", s=55, zorder=3)
        else:
            ax.scatter(pd.Timestamp(OFFICIAL_REFERENCE_DATE), idx, color="#d93025", marker="x", s=65, zorder=3)
    ax.axvline(pd.Timestamp(decision["latest_local_ec_tradable_date"]), color="#d93025", linestyle="--", linewidth=1.3, label="latest local EC")
    ax.axvline(pd.Timestamp(decision["local_root_max_tradable_date"]), color="#f5a623", linestyle="--", linewidth=1.1, label="local root max")
    ax.axvline(pd.Timestamp(OFFICIAL_REFERENCE_DATE), color="#333333", linestyle=":", linewidth=1.3, label="official ref")
    ax.set_yticks(y)
    ax.set_yticklabels(gap["contract"])
    ax.set_title("Official active EC contracts vs local files")
    ax.legend(loc="lower right", fontsize=8)
    ax.grid(axis="x", alpha=0.18)

    ax = axes[0, 1]
    metrics = pd.DataFrame(
        [
            ("active coverage %", decision["active_contract_file_coverage_pct"]),
            ("gap to official ref days", decision["calendar_gap_latest_local_ec_to_official_ref"]),
            ("Stage633 days behind", decision["stage633_days_behind_latest_tradable"]),
            ("missing listed contracts", decision["missing_listed_by_local_root_max_contracts"]),
        ],
        columns=["metric", "value"],
    )
    colors = ["#d93025", "#d93025", "#f5a623", "#d93025"]
    ax.bar(metrics["metric"], metrics["value"], color=colors)
    for idx, row in metrics.iterrows():
        ax.text(idx, row["value"] + max(metrics["value"]) * 0.02, f"{row['value']:.0f}", ha="center", fontsize=9)
    ax.set_title("Freshness gap is contract-manifest driven")
    ax.tick_params(axis="x", rotation=18)
    ax.grid(axis="y", alpha=0.2)

    ax = axes[1, 0]
    corr_metrics = pd.DataFrame(
        [
            ("max abs corr", decision["stage633_max_abs_corr_to_p0"], 0.15, 0.20),
            ("rolling p75", decision["stage633_rolling_abs_corr_p75_to_p0"], 0.15, 0.25),
            ("tail corr", np.nan if decision["stage633_tail_abs_corr_to_p0_composite"] is None else decision["stage633_tail_abs_corr_to_p0_composite"], 0.20, 0.30),
        ],
        columns=["metric", "value", "strict", "watch"],
    )
    values = corr_metrics["value"].fillna(0.0)
    bar_colors = ["#f5a623", "#f5a623", "#d93025"]
    ax.bar(corr_metrics["metric"], values, color=bar_colors)
    ax.axhline(0.15, color="#168038", linestyle="--", linewidth=1, label="strict 0.15")
    ax.axhline(0.20, color="#f5a623", linestyle="--", linewidth=1, label="watch 0.20")
    ax.text(2, 0.025, "missing", ha="center", color="#d93025", fontsize=9)
    ax.set_ylim(0, max(0.30, float(values.max()) + 0.05))
    ax.set_title("Correlation evidence remains watch-level/incomplete")
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.2)

    ax = axes[1, 1]
    gates_plot = gates.copy()
    gate_colors = np.where(gates_plot["passed"].eq(1), "#168038", "#d93025")
    ax.barh(gates_plot["gate"], gates_plot["passed"], color=gate_colors)
    ax.set_xlim(0, 1.05)
    ax.set_title(f"Fail-closed gates: {int(gates_plot['passed'].sum())}/{len(gates_plot)}")
    ax.set_xlabel("passed")
    ax.grid(axis="x", alpha=0.2)

    fig.tight_layout(rect=[0, 0.01, 1, 0.95])
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _build_report(
    local_ec: pd.DataFrame,
    official_gap: pd.DataFrame,
    gates: pd.DataFrame,
    decision: dict[str, Any],
) -> str:
    missing_contracts = ", ".join(official_gap[official_gap["local_file_exists"].eq(0)]["contract"].astype(str).tolist())
    lines = [
        "# Stage649 ec.INE Futures Proxy Freshness Forensic Report",
        "",
        "## Purpose",
        "",
        "- Audit why Stage633 marked `ec.INE` local futures proxy stale.",
        "- This is a data/execution-readiness forensic, not a trading backtest.",
        "- No selector, paper sleeve, A/B, or trading whitelist is generated.",
        "",
        "## External Research Judgment",
        "",
    ]
    lines.extend([f"- {item}" for item in OFFICIAL_SOURCE_NOTES])
    lines.extend(
        [
            "",
            "## Key Findings",
            "",
            f"- decision: `{decision['decision']}`",
            f"- official reference date: `{OFFICIAL_REFERENCE_DATE}`",
            f"- local EC contract files: `{decision['local_ec_contract_files']}`",
            f"- official active EC contracts: `{decision['official_active_contracts']}`",
            f"- active contract local coverage: `{decision['active_contract_file_coverage_pct']:.2f}%`",
            f"- latest local EC tradable date: `{decision['latest_local_ec_tradable_date']}`",
            f"- local root max tradable date: `{decision['local_root_max_tradable_date']}`",
            f"- Stage633 days behind latest tradable: `{decision['stage633_days_behind_latest_tradable']}`",
            f"- local EC gap to official reference: `{decision['calendar_gap_latest_local_ec_to_official_ref']}` calendar days",
            f"- missing official active contracts in local dump: `{missing_contracts}`",
            f"- missing contracts already listed by local root max: `{decision['missing_listed_by_local_root_max_contracts']}`",
            f"- max abs corr to P0: `{decision['stage633_max_abs_corr_to_p0']:.4f}`",
            f"- rolling abs corr p75 to P0: `{decision['stage633_rolling_abs_corr_p75_to_p0']:.4f}`",
            f"- tail abs corr to P0 composite: `{decision['stage633_tail_abs_corr_to_p0_composite']}`",
            f"- SCFIS master rows: `{decision['scfis_master_rows']}`",
            f"- hard gates: `{decision['hard_gate_passed']}/{decision['hard_gate_total']}`",
            "",
            "## Official Contract Gap",
            "",
            official_gap[
                [
                    "contract",
                    "listed_date",
                    "expiry_date",
                    "local_file_exists",
                    "local_last_tradable_date",
                    "listed_by_local_root_max",
                    "missing_despite_listed_by_local_root_max",
                ]
            ].to_markdown(index=False),
            "",
            "## Gate Board",
            "",
            gates.to_markdown(index=False),
            "",
            "## Conclusion",
            "",
            "- `ec.INE` stale proxy is primarily a contract-manifest/download coverage issue after the EC listing schedule changed.",
            "- The local dump has EC history through `ec2602`, but none of the current official active EC contracts on 2026-06-03 are present locally.",
            "- This means current Stage633 correlation/trend evidence is usable only as a historical watch signal, not as deployable slot evidence.",
            "- Practical next step: add a read-only EC contract discovery + daily-bar repair collector for `ec2606/ec2607/ec2608/ec2609/ec2610/ec2612/ec2703` first; `ec2611` can only be expected after a post-May data refresh.",
            "- Selector/paper/trading whitelist remain locked until local futures proxy freshness, tail/rolling corr, PIT/outcome samples, and live TCA all pass.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    all_ine, local_root_max = _scan_local_ine_root()
    local_ec = all_ine[all_ine["contract"].astype(str).str.startswith("ec")].copy()
    local_ec = local_ec.sort_values("contract").reset_index(drop=True)
    local_ec.to_csv(LOCAL_CONTRACTS_PATH, index=False, encoding="utf-8-sig")

    stage633 = _load_stage633_ec()
    stage647 = _load_stage647_ec()
    scfis_stats = _load_scfis_master_stats()
    official_gap = _build_official_gap(local_ec, local_root_max)
    official_gap.to_csv(OFFICIAL_GAP_PATH, index=False, encoding="utf-8-sig")

    latest_local_ec = pd.to_datetime(local_ec["last_tradable_date"], errors="coerce").max() if not local_ec.empty else pd.NaT
    ref = pd.Timestamp(OFFICIAL_REFERENCE_DATE)
    active_coverage_pct = float(official_gap["local_file_exists"].mean() * 100.0) if not official_gap.empty else 0.0
    post_feb_files = int(local_ec[pd.to_datetime(local_ec["first_trade_date"], errors="coerce").ge(pd.Timestamp("2026-02-10"))].shape[0])
    tail_corr_raw = stage633.get("tail_abs_corr_to_p0_composite", np.nan)
    tail_corr = None if pd.isna(tail_corr_raw) else float(tail_corr_raw)

    decision = {
        "decision": "ec_ine_futures_proxy_stale_due_missing_revised_contracts_selector_locked",
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "official_reference_date": OFFICIAL_REFERENCE_DATE,
        "local_dump_label": LOCAL_DUMP_LABEL,
        "local_ine_root": str(LOCAL_INE_ROOT),
        "local_root_max_tradable_date": local_root_max,
        "local_ec_contract_files": int(len(local_ec)),
        "official_active_contracts": int(len(official_gap)),
        "active_contract_file_coverage_pct": active_coverage_pct,
        "post_feb_2026_local_contract_files": post_feb_files,
        "latest_local_ec_tradable_date": _date_string(latest_local_ec),
        "calendar_gap_latest_local_ec_to_official_ref": int((ref - latest_local_ec).days) if pd.notna(latest_local_ec) else 9999,
        "missing_official_active_contracts": int(official_gap["local_file_exists"].eq(0).sum()),
        "missing_listed_by_local_root_max_contracts": int(official_gap["missing_despite_listed_by_local_root_max"].sum()),
        "stage633_last_tradable_date": str(stage633.get("last_tradable_date", "")),
        "stage633_days_behind_latest_tradable": int(float(stage633.get("days_behind_latest_tradable", 9999) or 9999)),
        "stage633_data_pass": int(float(stage633.get("data_pass", 0) or 0)),
        "stage633_watch_corr_pass": int(float(stage633.get("watch_corr_pass", 0) or 0)),
        "stage633_low_corr_pass": int(float(stage633.get("low_corr_pass", 0) or 0)),
        "stage633_max_abs_corr_to_p0": float(stage633.get("max_abs_corr_to_p0", np.nan)),
        "stage633_rolling_abs_corr_p75_to_p0": float(stage633.get("rolling_abs_corr_p75_to_p0", np.nan)),
        "stage633_tail_abs_corr_to_p0_composite": tail_corr,
        "stage647_source_probe_decision": str(stage647.get("decision", stage647.get("status", ""))),
        "scfis_master_rows": int(scfis_stats["master_rows"]),
        "scfis_collection_pit_dates": int(scfis_stats["collection_pit_dates"]),
        "scfis_dates": int(scfis_stats["scfis_dates"]),
        "latest_scfis_date": str(scfis_stats["latest_scfis_date"]),
        "selector_rows": 0,
        "paper_rows": 0,
        "trading_whitelist_rows": 0,
        "promotion_allowed": False,
        "paper_allowed": False,
        "trading_whitelist_allowed": False,
        "next_action": "build_readonly_ec_contract_discovery_and_daily_bar_repair_collector_before_any_selector",
    }
    gates = _build_gates(decision)
    decision["hard_gate_passed"] = int(gates["passed"].sum())
    decision["hard_gate_total"] = int(len(gates))

    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(_build_report(local_ec, official_gap, gates, decision), encoding="utf-8")
    _write_chart(local_ec, official_gap, gates, decision)

    print(json.dumps(decision, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
