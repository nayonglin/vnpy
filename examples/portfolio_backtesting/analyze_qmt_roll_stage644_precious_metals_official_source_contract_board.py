from __future__ import annotations

import io
import json
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
CFTC_CACHE_DIR = OUTPUT_DIR / "external_cftc_cot_cache"

MODEL_TAG = "stage644_precious_metals_official_source_contract_board_v1"
OUTPUT_PREFIX = "qmt_roll_stage644_precious_metals_official_source_contract_board"
LINE_ID = "futures_trend_drawdown30_preserve_return"

STAGE313_BUCKET = OUTPUT_DIR / "qmt_roll_stage313_cftc_cot_external_quality_probe_bucket_summary_stage313_cftc_cot_external_quality_probe_v1.csv"
STAGE629_PRODUCT = OUTPUT_DIR / "qmt_roll_stage629_p2_public_source_monitor_run_product_status_stage629_p2_public_source_monitor_run_v1.csv"
STAGE631_PROGRESS = OUTPUT_DIR / "qmt_roll_stage631_p2_event_episode_ledger_contract_product_episode_progress_stage631_p2_event_episode_ledger_contract_v1.csv"
STAGE633_PRODUCTS = OUTPUT_DIR / "qmt_roll_stage633_independent_risk_slot_correlation_map_product_map_stage633_independent_risk_slot_correlation_map_v1.csv"

SOURCE_OPTIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_options_{MODEL_TAG}.csv"
PRODUCT_EVIDENCE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_evidence_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


@dataclass(frozen=True)
class SourceOption:
    source_name: str
    product_vt_symbol: str
    source_authority: str
    source_url: str
    frequency: str
    official_or_authorized: int
    public_or_owned_access: int
    machine_readable: int
    point_in_time_rule_defined: int
    local_payload_ready: int
    active_probe_ready: int
    china_contract_relevance: float
    prior_alpha_quality_failed: int
    event_seed_ready: int
    selector_allowed_now: int
    paper_or_whitelist_allowed_now: int
    allowed_use: str
    blocker: str
    local_rows: int = 0
    last_report_date: str = ""
    active_probe_note: str = ""


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def _markdown_table(df: pd.DataFrame, max_rows: int | None = None) -> str:
    if df.empty:
        return "(empty)"
    view = df.copy()
    if max_rows is not None:
        view = view.head(max_rows)
    return view.to_markdown(index=False)


def _load_cftc_precious_rows() -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    columns = [
        "Market_and_Exchange_Names",
        "Report_Date_as_YYYY-MM-DD",
        "Open_Interest_All",
        "M_Money_Positions_Long_All",
        "M_Money_Positions_Short_All",
        "Change_in_M_Money_Long_All",
        "Change_in_M_Money_Short_All",
    ]
    for zip_path in sorted(CFTC_CACHE_DIR.glob("fut_disagg_txt_*.zip")):
        with zipfile.ZipFile(zip_path) as archive:
            member = archive.namelist()[0]
            raw = archive.read(member)
        frame = pd.read_csv(io.BytesIO(raw), usecols=columns, low_memory=False)
        frame["source_zip"] = zip_path.name
        frames.append(frame)
    if not frames:
        return pd.DataFrame(columns=columns + ["source_zip"])
    data = pd.concat(frames, ignore_index=True)
    market = data["Market_and_Exchange_Names"].astype(str)
    mask = market.str.contains("SILVER - COMMODITY EXCHANGE INC.", regex=False) | market.str.contains(
        "GOLD - COMMODITY EXCHANGE INC.", regex=False
    )
    data = data[mask].copy()
    data["Report_Date_as_YYYY-MM-DD"] = pd.to_datetime(data["Report_Date_as_YYYY-MM-DD"], errors="coerce")
    data = data[data["Report_Date_as_YYYY-MM-DD"].notna()].copy()
    return data


def _summarize_cftc_market(data: pd.DataFrame, market_name: str) -> dict[str, Any]:
    subset = data[data["Market_and_Exchange_Names"].astype(str).eq(market_name)].copy()
    if subset.empty:
        return {"rows": 0, "last_report_date": "", "first_report_date": "", "latest_open_interest": 0.0}
    subset.sort_values("Report_Date_as_YYYY-MM-DD", inplace=True)
    latest = subset.iloc[-1]
    return {
        "rows": int(len(subset)),
        "first_report_date": subset["Report_Date_as_YYYY-MM-DD"].min().date().isoformat(),
        "last_report_date": subset["Report_Date_as_YYYY-MM-DD"].max().date().isoformat(),
        "latest_open_interest": float(pd.to_numeric(latest.get("Open_Interest_All"), errors="coerce")),
    }


def _stage313_quality_failed() -> dict[str, Any]:
    bucket = _read_csv(STAGE313_BUCKET)
    if bucket.empty:
        return {"decision": "unknown_stage313_missing", "test_low_20d_r": None, "test_high_20d_r": None}
    test = bucket[bucket["样本切分"].astype(str).eq("test")].copy()
    low = test[test["external_quality_bucket"].astype(str).eq("低分")]
    high = test[test["external_quality_bucket"].astype(str).eq("高分")]
    low_r = float(low["平均20日R"].iloc[0]) if not low.empty else None
    high_r = float(high["平均20日R"].iloc[0]) if not high.empty else None
    failed = int(high_r is None or low_r is None or high_r <= low_r)
    return {
        "decision": "fail_quality_score_not_monotonic_on_oos_forward_r" if failed else "pass",
        "test_low_20d_r": low_r,
        "test_high_20d_r": high_r,
    }


def _build_source_options(cftc_data: pd.DataFrame, stage629: pd.DataFrame, stage631: pd.DataFrame) -> pd.DataFrame:
    quality = _stage313_quality_failed()
    silver = _summarize_cftc_market(cftc_data, "SILVER - COMMODITY EXCHANGE INC.")
    gold = _summarize_cftc_market(cftc_data, "GOLD - COMMODITY EXCHANGE INC.")

    ag629 = stage629[stage629["product_vt_symbol"].astype(str).eq("ag.SHFE")] if not stage629.empty else pd.DataFrame()
    ag631 = stage631[stage631["product_vt_symbol"].astype(str).eq("ag.SHFE")] if not stage631.empty else pd.DataFrame()
    shfe_monitor_rows = int(float(ag629["monitor_ok_rows"].iloc[0])) if not ag629.empty else 0
    shfe_pit_dates = int(float(ag629["pit_received_dates"].iloc[0])) if not ag629.empty else 0
    shfe_event_rows = int(float(ag631["event_seed_rows"].iloc[0])) if not ag631.empty else 0

    rows = [
        SourceOption(
            source_name="CFTC COT Disaggregated Futures Only Silver",
            product_vt_symbol="ag.SHFE",
            source_authority="CFTC official",
            source_url="https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm",
            frequency="weekly",
            official_or_authorized=1,
            public_or_owned_access=1,
            machine_readable=1,
            point_in_time_rule_defined=1,
            local_payload_ready=int(silver["rows"] > 0),
            active_probe_ready=1,
            china_contract_relevance=0.70,
            prior_alpha_quality_failed=int(quality["decision"].startswith("fail")),
            event_seed_ready=0,
            selector_allowed_now=0,
            paper_or_whitelist_allowed_now=0,
            allowed_use="monitor_only_temperature_source",
            blocker="prior Stage014 COT quality failed; weekly US COMEX proxy is not China onshore selector",
            local_rows=int(silver["rows"]),
            last_report_date=str(silver["last_report_date"]),
            active_probe_note="2026-06-04 external probe: CFTC 2026 zip HTTP 200 application/zip",
        ),
        SourceOption(
            source_name="CFTC COT Disaggregated Futures Only Gold",
            product_vt_symbol="au.SHFE",
            source_authority="CFTC official",
            source_url="https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalCompressed/index.htm",
            frequency="weekly",
            official_or_authorized=1,
            public_or_owned_access=1,
            machine_readable=1,
            point_in_time_rule_defined=1,
            local_payload_ready=int(gold["rows"] > 0),
            active_probe_ready=1,
            china_contract_relevance=0.75,
            prior_alpha_quality_failed=int(quality["decision"].startswith("fail")),
            event_seed_ready=0,
            selector_allowed_now=0,
            paper_or_whitelist_allowed_now=0,
            allowed_use="monitor_only_temperature_source",
            blocker="Stage014 included au and failed OOS monotonicity; keep as context only",
            local_rows=int(gold["rows"]),
            last_report_date=str(gold["last_report_date"]),
            active_probe_note="2026-06-04 external probe: CFTC 2026 zip HTTP 200 application/zip",
        ),
        SourceOption(
            source_name="CME COMEX Silver Warehouse Stocks",
            product_vt_symbol="ag.SHFE",
            source_authority="CME official",
            source_url="https://www.cmegroup.com/delivery_reports/Silver_stocks.xls",
            frequency="daily_or_periodic",
            official_or_authorized=1,
            public_or_owned_access=1,
            machine_readable=1,
            point_in_time_rule_defined=0,
            local_payload_ready=0,
            active_probe_ready=0,
            china_contract_relevance=0.55,
            prior_alpha_quality_failed=0,
            event_seed_ready=0,
            selector_allowed_now=0,
            paper_or_whitelist_allowed_now=0,
            allowed_use="source_backlog_probe_required",
            blocker="official page exposes Silver Stocks link, but 2026-06-04 direct payload probe timed out",
            active_probe_note="2026-06-04 external probe: urllib timeout, curl timeout/internal_error",
        ),
        SourceOption(
            source_name="SHFE Daily Data Silver Page Monitor",
            product_vt_symbol="ag.SHFE",
            source_authority="SHFE official",
            source_url="https://www.shfe.cn/eng/reports/StatisticalData/DailyData/",
            frequency="exchange_daily",
            official_or_authorized=1,
            public_or_owned_access=1,
            machine_readable=0,
            point_in_time_rule_defined=1,
            local_payload_ready=int(shfe_monitor_rows > 0),
            active_probe_ready=int(shfe_monitor_rows > 0),
            china_contract_relevance=0.90,
            prior_alpha_quality_failed=0,
            event_seed_ready=int(shfe_event_rows > 0),
            selector_allowed_now=0,
            paper_or_whitelist_allowed_now=0,
            allowed_use="forward_monitor_only",
            blocker=f"stage629 pit_dates={shfe_pit_dates}; stage631 event_seed_rows={shfe_event_rows}",
            local_rows=shfe_monitor_rows,
            active_probe_note="Stage629 active public monitor ok; no event seed or selector payload",
        ),
        SourceOption(
            source_name="LBMA Silver Price and London Vault Data",
            product_vt_symbol="ag.SHFE",
            source_authority="LBMA/IBA authorized benchmark",
            source_url="https://www.lbma.org.uk/prices-and-data/lbma-silver-price",
            frequency="daily_or_monthly",
            official_or_authorized=1,
            public_or_owned_access=0,
            machine_readable=0,
            point_in_time_rule_defined=0,
            local_payload_ready=0,
            active_probe_ready=0,
            china_contract_relevance=0.45,
            prior_alpha_quality_failed=0,
            event_seed_ready=0,
            selector_allowed_now=0,
            paper_or_whitelist_allowed_now=0,
            allowed_use="licensed_source_candidate_only",
            blocker="usage/licensing and machine feed not owned; price benchmark is not independent selector evidence",
        ),
        SourceOption(
            source_name="Generic precious-metals news/social sentiment",
            product_vt_symbol="ag.SHFE",
            source_authority="mixed unofficial",
            source_url="",
            frequency="continuous",
            official_or_authorized=0,
            public_or_owned_access=0,
            machine_readable=0,
            point_in_time_rule_defined=0,
            local_payload_ready=0,
            active_probe_ready=0,
            china_contract_relevance=0.25,
            prior_alpha_quality_failed=0,
            event_seed_ready=0,
            selector_allowed_now=0,
            paper_or_whitelist_allowed_now=0,
            allowed_use="reject_for_now",
            blocker="not official, weak audit trail, high narrative overfit risk",
        ),
    ]
    source_df = pd.DataFrame([asdict(row) for row in rows])
    source_df["readiness_score"] = (
        source_df["official_or_authorized"]
        + source_df["public_or_owned_access"]
        + source_df["machine_readable"]
        + source_df["point_in_time_rule_defined"]
        + source_df["local_payload_ready"]
        + source_df["active_probe_ready"]
        + source_df["event_seed_ready"]
        - source_df["prior_alpha_quality_failed"]
    )
    return source_df


def _build_product_evidence(cftc_data: pd.DataFrame, source_options: pd.DataFrame) -> pd.DataFrame:
    product_map = _read_csv(STAGE633_PRODUCTS)
    stage629 = _read_csv(STAGE629_PRODUCT)
    stage631 = _read_csv(STAGE631_PROGRESS)
    quality = _stage313_quality_failed()

    cftc_summary = {
        "ag.SHFE": _summarize_cftc_market(cftc_data, "SILVER - COMMODITY EXCHANGE INC."),
        "au.SHFE": _summarize_cftc_market(cftc_data, "GOLD - COMMODITY EXCHANGE INC."),
    }
    rows: list[dict[str, Any]] = []
    for product in ["ag.SHFE", "au.SHFE"]:
        p = product_map[product_map["product_vt_symbol"].astype(str).eq(product)] if not product_map.empty else pd.DataFrame()
        s629 = stage629[stage629["product_vt_symbol"].astype(str).eq(product)] if not stage629.empty else pd.DataFrame()
        s631 = stage631[stage631["product_vt_symbol"].astype(str).eq(product)] if not stage631.empty else pd.DataFrame()
        source_product = source_options[source_options["product_vt_symbol"].astype(str).eq(product)]
        rows.append(
            {
                "product_vt_symbol": product,
                "product_family": p["product_family"].iloc[0] if not p.empty else "precious_metals",
                "stage633_structural_bucket": p["structural_bucket"].iloc[0] if not p.empty else "",
                "max_abs_corr_to_p0": float(p["max_abs_corr_to_p0"].iloc[0]) if not p.empty else None,
                "tail_abs_corr_to_p0_composite": float(p["tail_abs_corr_to_p0_composite"].iloc[0]) if not p.empty and pd.notna(p["tail_abs_corr_to_p0_composite"].iloc[0]) else None,
                "rolling_abs_corr_p75_to_p0": float(p["rolling_abs_corr_p75_to_p0"].iloc[0]) if not p.empty else None,
                "recent_median_volume": float(p["recent_median_volume"].iloc[0]) if not p.empty else None,
                "trend_year_rate_pct": float(p["trend_year_rate_pct"].iloc[0]) if not p.empty else None,
                "trend_signal_median": float(p["trend_signal_median"].iloc[0]) if not p.empty else None,
                "stage629_monitor_ok_rows": float(s629["monitor_ok_rows"].iloc[0]) if not s629.empty else 0.0,
                "stage629_pit_dates": int(float(s629["pit_received_dates"].iloc[0])) if not s629.empty else 0,
                "stage631_event_seed_rows": int(float(s631["event_seed_rows"].iloc[0])) if not s631.empty else 0,
                "stage631_verified_episodes": int(float(s631["verified_independent_episodes"].iloc[0])) if not s631.empty else 0,
                "cftc_local_rows": int(cftc_summary[product]["rows"]),
                "cftc_last_report_date": str(cftc_summary[product]["last_report_date"]),
                "source_options_count": int(len(source_product)),
                "source_options_active_probe_ready": int(source_product["active_probe_ready"].sum()) if not source_product.empty else 0,
                "source_options_selector_allowed": int(source_product["selector_allowed_now"].sum()) if not source_product.empty else 0,
                "stage313_test_low_20d_r": quality["test_low_20d_r"],
                "stage313_test_high_20d_r": quality["test_high_20d_r"],
                "promotion_status": "monitor_only_selector_locked",
            }
        )
    return pd.DataFrame(rows)


def _build_gates(source_options: pd.DataFrame, product_evidence: pd.DataFrame) -> pd.DataFrame:
    ag = product_evidence[product_evidence["product_vt_symbol"].eq("ag.SHFE")]
    ag_row = ag.iloc[0].to_dict() if not ag.empty else {}
    cftc_ag = source_options[source_options["source_name"].str.contains("CFTC COT Disaggregated Futures Only Silver")]
    cme = source_options[source_options["source_name"].str.contains("CME COMEX Silver")]
    rows = [
        ("official_source_exists", 1, "CFTC/SHFE/CME/LBMA official or authorized routes identified"),
        ("cftc_machine_readable_public", int(not cftc_ag.empty and int(cftc_ag["machine_readable"].iloc[0]) == 1), "CFTC zip/PRE supports machine ingestion"),
        ("cftc_current_probe_ok", int(not cftc_ag.empty and int(cftc_ag["active_probe_ready"].iloc[0]) == 1), "2026-06-04 CFTC 2026 zip HTTP 200"),
        ("ag_correlation_watch_not_strict_low", int(float(ag_row.get("max_abs_corr_to_p0", 9.0)) <= 0.20), "ag is watch-level but not strict low-corr under 0.15"),
        ("ag_liquidity_ok", int(float(ag_row.get("recent_median_volume", 0.0)) >= 5000), "ag recent median volume is sufficient"),
        ("shfe_forward_monitor_exists", int(float(ag_row.get("stage629_monitor_ok_rows", 0.0)) > 0), "Stage629 SHFE page monitor ok"),
        ("cme_payload_validated", int(not cme.empty and int(cme["active_probe_ready"].iloc[0]) == 1), "CME direct Silver_stocks.xls payload timed out"),
        ("ag_event_seed_ready", int(int(ag_row.get("stage631_event_seed_rows", 0)) > 0), "Stage631 ag event_seed_rows remains 0"),
        ("pit_dates_reach_20", int(int(ag_row.get("stage629_pit_dates", 0)) >= 20), "P2 protocol requires 20 PIT dates"),
        ("episodes_reach_3", int(int(ag_row.get("stage631_verified_episodes", 0)) >= 3), "P2 protocol requires 3 independent episodes"),
        ("prior_cot_quality_not_failed", 0, "Stage014 COT quality failed OOS monotonicity"),
        ("selector_allowed_now", int(source_options["selector_allowed_now"].sum() > 0), "selector remains locked"),
        ("paper_or_whitelist_allowed_now", int(source_options["paper_or_whitelist_allowed_now"].sum() > 0), "paper/whitelist remain locked"),
        ("fail_closed_discipline", 1, "source evidence can be monitored without promotion"),
    ]
    return pd.DataFrame(rows, columns=["gate", "passed", "notes"])


def _plot_chart(source_options: pd.DataFrame, product_evidence: pd.DataFrame, gates: pd.DataFrame) -> None:
    plt.rcParams.update({"font.size": 9})
    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    fig.suptitle("Stage644 precious metals official source contract board", fontsize=14, weight="bold")

    ax = axes[0, 0]
    score_cols = [
        "official_or_authorized",
        "public_or_owned_access",
        "machine_readable",
        "point_in_time_rule_defined",
        "local_payload_ready",
        "active_probe_ready",
        "event_seed_ready",
    ]
    plot_df = source_options.copy()
    plot_df["label"] = plot_df["source_name"].str.replace("CFTC COT Disaggregated Futures Only ", "CFTC ", regex=False)
    bottom = pd.Series([0] * len(plot_df), index=plot_df.index, dtype=float)
    colors = ["#3b7ddd", "#4caf50", "#7e57c2", "#26a69a", "#ffb74d", "#66bb6a", "#8d6e63"]
    for col, color in zip(score_cols, colors):
        ax.barh(plot_df["label"], plot_df[col], left=bottom, color=color, label=col)
        bottom += plot_df[col].astype(float)
    fail = plot_df["prior_alpha_quality_failed"].astype(float)
    ax.barh(plot_df["label"], -fail, color="#d9534f", label="prior_alpha_failed")
    ax.set_title("Source readiness components")
    ax.set_xlabel("ready components (red = prior alpha fail)")
    ax.legend(fontsize=7, loc="lower right")

    ax = axes[0, 1]
    p = product_evidence.copy()
    bubble = (p["recent_median_volume"].fillna(0) / max(p["recent_median_volume"].fillna(0).max(), 1.0)) * 700 + 120
    ax.scatter(p["max_abs_corr_to_p0"], p["trend_signal_median"], s=bubble, color=["#f5a623", "#4a90e2"], alpha=0.75)
    for _, row in p.iterrows():
        ax.annotate(row["product_vt_symbol"], (row["max_abs_corr_to_p0"], row["trend_signal_median"]), xytext=(5, 5), textcoords="offset points")
    ax.axvline(0.15, color="#d9534f", linestyle="--", linewidth=1, label="strict corr 0.15")
    ax.axvline(0.20, color="#f0ad4e", linestyle=":", linewidth=1, label="watch corr 0.20")
    ax.set_title("Precious products: corr vs trend proxy")
    ax.set_xlabel("max abs corr to P0")
    ax.set_ylabel("trend signal median")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.25)

    ax = axes[1, 0]
    ag = product_evidence[product_evidence["product_vt_symbol"].eq("ag.SHFE")].iloc[0]
    evidence = pd.Series(
        {
            "SHFE monitor rows": ag["stage629_monitor_ok_rows"],
            "CFTC silver rows": ag["cftc_local_rows"],
            "PIT dates": ag["stage629_pit_dates"],
            "event seeds": ag["stage631_event_seed_rows"],
            "episodes": ag["stage631_verified_episodes"],
            "selector rows": ag["source_options_selector_allowed"],
        }
    )
    colors_e = ["#66bb6a", "#66bb6a", "#f0ad4e", "#d9534f", "#d9534f", "#d9534f"]
    ax.bar(evidence.index, evidence.values, color=colors_e)
    ax.set_yscale("symlog")
    ax.set_title("ag.SHFE evidence ledger state")
    ax.tick_params(axis="x", rotation=30)
    for idx, val in enumerate(evidence.values):
        ax.text(idx, max(float(val), 0.1), f"{val:g}", ha="center", va="bottom", fontsize=8)

    ax = axes[1, 1]
    gates_plot = gates.copy()
    gates_plot["color"] = gates_plot["passed"].map({1: "#66bb6a", 0: "#d9534f"})
    ax.barh(gates_plot["gate"], [1.0] * len(gates_plot), color=gates_plot["color"])
    ax.set_xlim(0, 1.05)
    ax.set_title("Hard gates")
    ax.set_xlabel("status")
    for idx, row in gates_plot.iterrows():
        ax.text(0.02, idx, "PASS" if row["passed"] else "FAIL", va="center", ha="left", color="white", fontsize=8, weight="bold")

    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _build_report(
    source_options: pd.DataFrame,
    product_evidence: pd.DataFrame,
    gates: pd.DataFrame,
    decision: str,
) -> str:
    quality = _stage313_quality_failed()
    passed_gates = int(gates["passed"].sum())
    total_gates = int(len(gates))
    lines = [
        "# Stage644 precious metals official source contract board",
        "",
        "## Positioning",
        "",
        "- Scope: precious_metals / ag.SHFE and au.SHFE source contract audit.",
        "- No strategy replay, no parameter scan, no selector, no paper, no whitelist, no CTP connection.",
        "- Purpose: decide whether precious metals can become a source/PIT/TCA workstream for lower single-risk expansion.",
        "",
        "## External research judgement",
        "",
        "- CFTC COT is official, weekly, public, machine-readable, and has both current comma-delimited reports and historical compressed yearly files.",
        "- GitHub research found public COT ETL code patterns that download official CFTC ZIP archives directly and cache/read them in memory.",
        "- LBMA silver price/data is authoritative but usage/licensing and benchmark-price nature make it a weak free selector source.",
        "- CME exposes official COMEX warehouse/depository stock links, but this run could not validate the direct Silver_stocks.xls payload.",
        "",
        "## Decision",
        "",
        f"- `{decision}`",
        f"- hard gates: `{passed_gates}/{total_gates}`",
        f"- Stage014 COT OOS quality: low bucket 20dR `{quality['test_low_20d_r']}`, high bucket 20dR `{quality['test_high_20d_r']}`.",
        "",
        "## Source options",
        "",
        _markdown_table(
            source_options[
                [
                    "source_name",
                    "product_vt_symbol",
                    "official_or_authorized",
                    "machine_readable",
                    "local_payload_ready",
                    "active_probe_ready",
                    "prior_alpha_quality_failed",
                    "event_seed_ready",
                    "selector_allowed_now",
                    "allowed_use",
                    "local_rows",
                    "last_report_date",
                ]
            ]
        ),
        "",
        "## Product evidence",
        "",
        _markdown_table(product_evidence),
        "",
        "## Gates",
        "",
        _markdown_table(gates),
        "",
        "## Interpretation",
        "",
        "- ag.SHFE is useful as a P2 monitor target, not as a deployable new risk slot.",
        "- The strongest executable source is CFTC COT Silver, but Stage014 already disproved COT as a trading-quality factor.",
        "- SHFE forward monitor exists but has only one PIT date and no event seed.",
        "- CME inventory remains valuable source backlog, but direct current payload must be validated before it can enter a PIT ledger.",
        "- Therefore precious metals do not unlock lower single-trade-risk expansion yet.",
        "",
        "## Next steps",
        "",
        "- If continuing this branch, create a CFTC weekly monitor append gate for ag/au as context-only PIT evidence.",
        "- Separately retry CME Silver_stocks.xls with a browser/session or official data channel; do not treat timeout route as usable source.",
        "- Do not run a precious-metals selector or A/B until 20 PIT dates, 3 independent episodes, predictive audit, and live TCA exist.",
        "",
        "## Overfit and continuation reflection",
        "",
        "- Before run: not overfit, because this audits source contracts and prior failed evidence rather than tuning trading parameters.",
        "- After run: not overfit, because the result keeps selector locked despite official CFTC source availability.",
        "- Continue value: yes, but only as monitor/source accumulation. It is not worth sweeping precious-metals trading filters now.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cftc_data = _load_cftc_precious_rows()
    stage629 = _read_csv(STAGE629_PRODUCT)
    stage631 = _read_csv(STAGE631_PROGRESS)
    source_options = _build_source_options(cftc_data, stage629, stage631)
    product_evidence = _build_product_evidence(cftc_data, source_options)
    gates = _build_gates(source_options, product_evidence)

    decision = "precious_metals_official_cftc_source_validated_monitor_only_selector_locked"
    if int(gates[gates["gate"].eq("selector_allowed_now")]["passed"].iloc[0]) == 1:
        decision = "unexpected_selector_unlocked_manual_review_required"

    _plot_chart(source_options, product_evidence, gates)

    source_options.to_csv(SOURCE_OPTIONS_PATH, index=False, encoding="utf-8-sig")
    product_evidence.to_csv(PRODUCT_EVIDENCE_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    REPORT_PATH.write_text(_build_report(source_options, product_evidence, gates, decision), encoding="utf-8")

    summary = {
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "analysis_type": "precious_metals_official_source_contract_board_no_strategy_backtest",
        "decision": decision,
        "source_options": int(len(source_options)),
        "official_or_authorized_sources": int(source_options["official_or_authorized"].sum()),
        "machine_readable_sources": int(source_options["machine_readable"].sum()),
        "active_probe_ready_sources": int(source_options["active_probe_ready"].sum()),
        "cftc_silver_rows": int(product_evidence.loc[product_evidence["product_vt_symbol"].eq("ag.SHFE"), "cftc_local_rows"].iloc[0]),
        "ag_pit_dates": int(product_evidence.loc[product_evidence["product_vt_symbol"].eq("ag.SHFE"), "stage629_pit_dates"].iloc[0]),
        "ag_event_seed_rows": int(product_evidence.loc[product_evidence["product_vt_symbol"].eq("ag.SHFE"), "stage631_event_seed_rows"].iloc[0]),
        "selector_allowed_now": int(source_options["selector_allowed_now"].sum()),
        "paper_or_whitelist_allowed_now": int(source_options["paper_or_whitelist_allowed_now"].sum()),
        "hard_gates_passed": int(gates["passed"].sum()),
        "hard_gates_total": int(len(gates)),
        "outputs": {
            "source_options": str(SOURCE_OPTIONS_PATH),
            "product_evidence": str(PRODUCT_EVIDENCE_PATH),
            "gates": str(GATES_PATH),
            "report": str(REPORT_PATH),
            "chart": str(CHART_PATH),
        },
    }
    DECISION_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
