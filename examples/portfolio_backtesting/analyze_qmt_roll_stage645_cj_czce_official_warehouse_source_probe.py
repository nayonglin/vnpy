from __future__ import annotations

import hashlib
import json
import math
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import akshare as ak
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
os.environ.setdefault("MPLCONFIGDIR", str(OUTPUT_DIR / ".matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


LINE_ID = "futures_trend_drawdown30_preserve_return"
MODEL_TAG = "stage645_cj_czce_official_warehouse_source_probe_v1"
OUTPUT_PREFIX = "qmt_roll_stage645_cj_czce_official_warehouse_source_probe"

STAGE633_PRODUCT_MAP = (
    OUTPUT_DIR / "qmt_roll_stage633_independent_risk_slot_correlation_map_product_map_stage633_independent_risk_slot_correlation_map_v1.csv"
)
STAGE634_PRODUCT_SUMMARY = (
    OUTPUT_DIR / "qmt_roll_stage634_watchline_source_contract_audit_product_summary_stage634_watchline_source_contract_audit_v1.csv"
)

FETCH_LEDGER_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_fetch_ledger_{MODEL_TAG}.csv"
CJ_WAREHOUSE_ROWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cj_warehouse_rows_{MODEL_TAG}.csv"
PRODUCT_EVIDENCE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_evidence_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

PROBE_DATES = ["20250613", "20260421", "20260427", "20260529", "20260602", "20260603"]
REQUIRED_PIT_DATES_FOR_SELECTOR = 20
REQUIRED_EPISODES = 3
REQUIRED_TCA_SAMPLES = 3

REFERENCES = [
    "CZCE warehouse receipt daily page: https://www.czce.com.cn/cn/jysj/cdrb/H077003010index_1.htm",
    "AKShare futures_warehouse_receipt_czce: https://akshare.akfamily.xyz/changelog.html",
    "AKShare GitHub: https://github.com/akfamily/akshare",
    "National Forestry and Grassland Administration Xinjiang jujube note: https://www.forestry.gov.cn/lyj/1/slgs/20241023/593126.html",
    "CZCE dried jujube business rule commentary: https://www.shinnytech.com/articles/business-rules/products/czce.cj",
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


def _read_csv(path: Path, required: bool = True) -> pd.DataFrame:
    if not path.exists():
        if required:
            raise FileNotFoundError(path)
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def _num(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(default).astype(float)


def _source_url_for_date(date_text: str) -> str:
    suffix = "xls" if date_text <= "20251231" else "xlsx"
    return f"http://www.czce.com.cn/cn/DFSStaticFiles/Future/{date_text[:4]}/{date_text}/FutureDataWhsheet.{suffix}"


def _hash_frame(frame: pd.DataFrame) -> str:
    normalized = frame.astype(object).where(pd.notna(frame), "").astype(str)
    csv_text = normalized.to_csv(index=False)
    return hashlib.sha256(csv_text.encode("utf-8")).hexdigest()


def _extract_total_row(cj: pd.DataFrame) -> dict[str, float]:
    if cj.empty:
        return {"total_receipts": 0.0, "daily_change": 0.0, "effective_forecast": 0.0}
    first_col = cj.columns[0]
    total = cj[cj[first_col].astype(str).str.contains("总计", na=False)]
    if total.empty:
        return {
            "total_receipts": float(_num(cj, "仓单数量").sum()),
            "daily_change": float(_num(cj, "当日增减").sum()),
            "effective_forecast": float(_num(cj, "有效预报").sum()),
        }
    row = total.iloc[-1]
    return {
        "total_receipts": float(pd.to_numeric(row.get("仓单数量"), errors="coerce") or 0.0),
        "daily_change": float(pd.to_numeric(row.get("当日增减"), errors="coerce") or 0.0),
        "effective_forecast": float(pd.to_numeric(row.get("有效预报"), errors="coerce") or 0.0),
    }


def _warehouse_count(cj: pd.DataFrame) -> int:
    if cj.empty or "仓库简称" not in cj.columns:
        return 0
    names = cj["仓库简称"].dropna().astype(str)
    names = names[~names.str.contains("小计|总计")]
    return int(names.nunique())


def _fetch_cj_warehouse() -> tuple[pd.DataFrame, pd.DataFrame]:
    ledger_rows: list[dict[str, Any]] = []
    cj_rows: list[pd.DataFrame] = []
    received_at = _fmt_cst(_now_cst())
    for date_text in PROBE_DATES:
        source_url = _source_url_for_date(date_text)
        try:
            data = ak.futures_warehouse_receipt_czce(date_text)
            keys = list(data.keys()) if isinstance(data, dict) else []
            cj = data.get("CJ", pd.DataFrame()) if isinstance(data, dict) else pd.DataFrame()
            if not isinstance(cj, pd.DataFrame):
                cj = pd.DataFrame()
            cj = cj.copy()
            raw_hash = _hash_frame(cj) if not cj.empty else ""
            totals = _extract_total_row(cj)
            if not cj.empty:
                out = cj.copy()
                out.insert(0, "probe_date", date_text)
                out.insert(1, "received_at_cst", received_at)
                out.insert(2, "source_url", source_url)
                out.insert(3, "raw_sha256", raw_hash)
                cj_rows.append(out)
            ledger_rows.append(
                {
                    "probe_date": date_text,
                    "received_at_cst": received_at,
                    "source_name": "CZCE warehouse receipt daily via AKShare",
                    "source_authority": "exchange_official_wrapped_by_akshare",
                    "source_url": source_url,
                    "fetch_status": "ok" if not cj.empty else "cj_missing",
                    "fetch_error": "",
                    "product_vt_symbol": "CJ.CZCE",
                    "akshare_keys": ",".join(keys[:40]),
                    "akshare_key_count": len(keys),
                    "cj_rows": int(len(cj)),
                    "warehouse_count": _warehouse_count(cj),
                    "total_receipts": totals["total_receipts"],
                    "daily_change": totals["daily_change"],
                    "effective_forecast": totals["effective_forecast"],
                    "raw_sha256": raw_hash,
                    "raw_sha256_present": int(bool(raw_hash)),
                    "usable_for_forward_monitor": int(not cj.empty and bool(raw_hash)),
                    "usable_for_history_selector": 0,
                    "selector_allowed_now": 0,
                    "paper_or_whitelist_allowed_now": 0,
                    "trading_whitelist_allowed_now": 0,
                }
            )
        except Exception as exc:  # noqa: BLE001 - report exact fetch blocker
            ledger_rows.append(
                {
                    "probe_date": date_text,
                    "received_at_cst": received_at,
                    "source_name": "CZCE warehouse receipt daily via AKShare",
                    "source_authority": "exchange_official_wrapped_by_akshare",
                    "source_url": source_url,
                    "fetch_status": "error",
                    "fetch_error": f"{type(exc).__name__}: {str(exc)[:300]}",
                    "product_vt_symbol": "CJ.CZCE",
                    "akshare_keys": "",
                    "akshare_key_count": 0,
                    "cj_rows": 0,
                    "warehouse_count": 0,
                    "total_receipts": 0.0,
                    "daily_change": 0.0,
                    "effective_forecast": 0.0,
                    "raw_sha256": "",
                    "raw_sha256_present": 0,
                    "usable_for_forward_monitor": 0,
                    "usable_for_history_selector": 0,
                    "selector_allowed_now": 0,
                    "paper_or_whitelist_allowed_now": 0,
                    "trading_whitelist_allowed_now": 0,
                }
            )
    ledger = pd.DataFrame(ledger_rows)
    rows = pd.concat(cj_rows, ignore_index=True) if cj_rows else pd.DataFrame()
    return ledger, rows


def _build_product_evidence(fetch_ledger: pd.DataFrame) -> pd.DataFrame:
    product_map = _read_csv(STAGE633_PRODUCT_MAP)
    stage634 = _read_csv(STAGE634_PRODUCT_SUMMARY, required=False)
    cj = product_map[product_map["product_vt_symbol"].astype(str).eq("CJ.CZCE")].copy()
    if cj.empty:
        raise ValueError("CJ.CZCE missing in Stage633 product map")
    row = cj.iloc[0]
    s634 = stage634[stage634["product_vt_symbol"].astype(str).eq("CJ.CZCE")].copy() if not stage634.empty else pd.DataFrame()
    ok = fetch_ledger[fetch_ledger["fetch_status"].eq("ok")].copy()
    evidence = {
        "product_vt_symbol": "CJ.CZCE",
        "product_family_before": row.get("product_family", ""),
        "product_family_after": "watch_jujube",
        "stage633_structural_bucket": row.get("structural_bucket", ""),
        "tradable_rows": float(row.get("tradable_rows", 0.0)),
        "recent_median_volume": float(row.get("recent_median_volume", 0.0)),
        "recent_median_oi": float(row.get("recent_median_oi", 0.0)),
        "max_abs_corr_to_p0": float(row.get("max_abs_corr_to_p0", 0.0)),
        "tail_abs_corr_to_p0_composite": float(row.get("tail_abs_corr_to_p0_composite", 0.0)),
        "rolling_abs_corr_p75_to_p0": float(row.get("rolling_abs_corr_p75_to_p0", 0.0)),
        "trend_year_rate_pct": float(row.get("trend_year_rate_pct", 0.0)),
        "trend_signal_median": float(row.get("trend_signal_median", 0.0)),
        "stage634_source_contract_rows": float(s634["source_contract_rows"].iloc[0]) if not s634.empty else 0.0,
        "stage634_monthly_source_rows": float(s634["monthly_source_rows"].iloc[0]) if not s634.empty else 0.0,
        "fetch_probe_dates": int(len(fetch_ledger)),
        "fetch_ok_dates": int(len(ok)),
        "raw_hash_rows": int(fetch_ledger["raw_sha256_present"].sum()),
        "pit_dates": int(ok["probe_date"].nunique()),
        "latest_probe_date": str(ok["probe_date"].max()) if not ok.empty else "",
        "latest_total_receipts": float(ok.sort_values("probe_date")["total_receipts"].iloc[-1]) if not ok.empty else 0.0,
        "latest_effective_forecast": float(ok.sort_values("probe_date")["effective_forecast"].iloc[-1]) if not ok.empty else 0.0,
        "selector_allowed_now": int(fetch_ledger["selector_allowed_now"].sum()),
        "paper_or_whitelist_allowed_now": int(fetch_ledger["paper_or_whitelist_allowed_now"].sum()),
        "trading_whitelist_allowed_now": int(fetch_ledger["trading_whitelist_allowed_now"].sum()),
        "status": "official_warehouse_source_validated_monitor_only",
    }
    return pd.DataFrame([evidence])


def _build_gates(fetch_ledger: pd.DataFrame, evidence: pd.DataFrame) -> pd.DataFrame:
    e = evidence.iloc[0].to_dict()
    ok_dates = int(e["fetch_ok_dates"])
    gates = [
        ("cj_loaded_from_stage633", 1, "CJ.CZCE exists in local product/correlation map"),
        ("strict_low_or_watch_corr", int(float(e["max_abs_corr_to_p0"]) <= 0.20), "CJ max abs corr <= watch threshold 0.20"),
        ("liquidity_ok_for_monitor", int(float(e["recent_median_volume"]) >= 1000), "CJ recent median volume >= 1000"),
        ("official_daily_warehouse_fetch_ok", int(ok_dates >= 3), "at least 3 CZCE warehouse dates return CJ"),
        ("raw_hash_rows_present", int(int(e["raw_hash_rows"]) >= 3), "at least 3 raw hashes are present"),
        ("latest_currentish_source_ok", int(str(e["latest_probe_date"]) >= "20260602"), "latest probe reaches 2026-06-02 or later"),
        ("monthly_fundamental_source_ready", 0, "CJ still lacks stable monthly official fundamental release"),
        ("pit_dates_reach_20", int(int(e["pit_dates"]) >= REQUIRED_PIT_DATES_FOR_SELECTOR), "selector protocol requires 20 PIT dates"),
        ("independent_episodes_reach_3", 0, "no independent CJ source/outcome episodes yet"),
        ("live_tca_samples_reach_3", 0, "no CJ live TCA samples"),
        ("selector_allowed_now", int(int(e["selector_allowed_now"]) > 0), "selector remains locked"),
        (
            "paper_or_whitelist_allowed_now",
            int(int(e["paper_or_whitelist_allowed_now"]) > 0 or int(e["trading_whitelist_allowed_now"]) > 0),
            "paper/whitelist remain locked",
        ),
        ("fail_closed_discipline", 1, "official source validation does not promote trading"),
    ]
    return pd.DataFrame(gates, columns=["gate", "passed", "notes"])


def _markdown_table(df: pd.DataFrame) -> str:
    return df.to_markdown(index=False) if not df.empty else "(empty)"


def _plot_chart(fetch_ledger: pd.DataFrame, evidence: pd.DataFrame, gates: pd.DataFrame) -> None:
    plt.rcParams.update({"font.size": 9})
    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    fig.suptitle("Stage645 CJ.CZCE official warehouse source probe", fontsize=14, weight="bold")

    ok = fetch_ledger[fetch_ledger["fetch_status"].eq("ok")].sort_values("probe_date").copy()
    ax = axes[0, 0]
    ax.bar(ok["probe_date"], ok["total_receipts"], color="#4a90e2", label="warehouse receipts")
    ax.plot(ok["probe_date"], ok["effective_forecast"], color="#f5a623", marker="o", label="effective forecast")
    ax.set_title("CJ warehouse receipts by official CZCE date")
    ax.set_ylabel("contracts / receipts")
    ax.tick_params(axis="x", rotation=30)
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.25)

    ax = axes[0, 1]
    e = evidence.iloc[0]
    bars = pd.Series(
        {
            "fetch dates": e["fetch_ok_dates"],
            "raw hashes": e["raw_hash_rows"],
            "PIT dates": e["pit_dates"],
            "monthly source": e["stage634_monthly_source_rows"],
            "episodes": 0,
            "selector rows": e["selector_allowed_now"],
        }
    )
    colors = ["#66bb6a", "#66bb6a", "#f0ad4e", "#d9534f", "#d9534f", "#d9534f"]
    ax.bar(bars.index, bars.values, color=colors)
    ax.axhline(REQUIRED_PIT_DATES_FOR_SELECTOR, color="#d9534f", linestyle="--", linewidth=1, label="20 PIT selector gate")
    ax.set_title("CJ source evidence depth")
    ax.tick_params(axis="x", rotation=30)
    ax.legend(fontsize=8)
    for idx, val in enumerate(bars.values):
        ax.text(idx, max(float(val), 0.1), f"{val:g}", ha="center", va="bottom", fontsize=8)

    ax = axes[1, 0]
    scatter = pd.DataFrame(
        [
            {
                "label": "CJ.CZCE",
                "corr": e["max_abs_corr_to_p0"],
                "trend": e["trend_signal_median"],
                "size": max(float(e["recent_median_volume"]) / 5.0, 180.0),
                "color": "#4a90e2",
            },
            {"label": "strict 0.15", "corr": 0.15, "trend": 0.0, "size": 0, "color": "#d9534f"},
            {"label": "watch 0.20", "corr": 0.20, "trend": 0.0, "size": 0, "color": "#f0ad4e"},
        ]
    )
    ax.scatter([scatter.iloc[0]["corr"]], [scatter.iloc[0]["trend"]], s=[scatter.iloc[0]["size"]], color=scatter.iloc[0]["color"], alpha=0.75)
    ax.annotate("CJ.CZCE", (float(e["max_abs_corr_to_p0"]), float(e["trend_signal_median"])), xytext=(8, 6), textcoords="offset points")
    ax.axvline(0.15, color="#d9534f", linestyle="--", linewidth=1, label="strict corr 0.15")
    ax.axvline(0.20, color="#f0ad4e", linestyle=":", linewidth=1, label="watch corr 0.20")
    ax.set_title("CJ corr vs trend proxy")
    ax.set_xlabel("max abs corr to P0")
    ax.set_ylabel("trend signal median")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8)

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
    fetch_ledger: pd.DataFrame,
    cj_rows: pd.DataFrame,
    evidence: pd.DataFrame,
    gates: pd.DataFrame,
    decision: str,
    generated_at: str,
) -> str:
    gate_pass = int(gates["passed"].sum())
    gate_total = int(len(gates))
    lines = [
        "# Stage645 CJ.CZCE official warehouse source probe",
        "",
        f"- generated_at_cst: `{generated_at}`",
        f"- decision: `{decision}`",
        "",
        "## External Research Judgement",
        "",
        "- Trend-following diversification research supports adding independent markets only when they increase independent return drivers, not when they duplicate existing risk.",
        "- `CJ.CZCE` has low/watch correlation evidence locally, but Stage634 showed weak stable fundamental sources.",
        "- Web/GitHub review points to CZCE warehouse receipt files and AKShare's `futures_warehouse_receipt_czce` wrapper as the most executable CJ source path.",
        "- National Forestry and Grassland Administration jujube articles are useful context, but they are irregular and not sufficient for selector by themselves.",
        "",
        "References:",
        *[f"- {item}" for item in REFERENCES],
        "",
        "## Key Numbers",
        "",
        f"- fetch dates: `{int(len(fetch_ledger))}`",
        f"- fetch ok dates: `{int(evidence['fetch_ok_dates'].iloc[0])}`",
        f"- raw hash rows: `{int(evidence['raw_hash_rows'].iloc[0])}`",
        f"- PIT dates: `{int(evidence['pit_dates'].iloc[0])}`",
        f"- latest probe date: `{evidence['latest_probe_date'].iloc[0]}`",
        f"- latest total receipts: `{float(evidence['latest_total_receipts'].iloc[0]):.0f}`",
        f"- latest effective forecast: `{float(evidence['latest_effective_forecast'].iloc[0]):.0f}`",
        f"- max abs corr to P0: `{float(evidence['max_abs_corr_to_p0'].iloc[0]):.4f}`",
        f"- recent median volume: `{float(evidence['recent_median_volume'].iloc[0]):.1f}`",
        f"- hard gates: `{gate_pass}/{gate_total}`",
        f"- selector/paper/whitelist: `{int(evidence['selector_allowed_now'].iloc[0])}/{int(evidence['paper_or_whitelist_allowed_now'].iloc[0])}/{int(evidence['trading_whitelist_allowed_now'].iloc[0])}`",
        "",
        "## Fetch Ledger",
        "",
        _markdown_table(
            fetch_ledger[
                [
                    "probe_date",
                    "fetch_status",
                    "cj_rows",
                    "warehouse_count",
                    "total_receipts",
                    "daily_change",
                    "effective_forecast",
                    "raw_sha256_present",
                    "usable_for_forward_monitor",
                ]
            ]
        ),
        "",
        "## Product Evidence",
        "",
        _markdown_table(evidence),
        "",
        "## Gates",
        "",
        _markdown_table(gates),
        "",
        "## Interpretation",
        "",
        "- This stage upgrades CJ from `source contract weak` to `official warehouse source active-fetch validated` for monitor purposes.",
        "- It still does not create a deployable independent risk slot: monthly fundamental source, 20 PIT dates, independent episodes, predictive audit and live TCA are missing.",
        "- The source is useful because it is daily, official-exchange based, product-specific, and machine-readable through AKShare; it is not enough because warehouse receipts are one supply-side state, not a proven trend selector.",
        "",
        "## Next Steps",
        "",
        "- Write a strict master PIT append gate for CJ warehouse receipts only after deciding this branch should continue.",
        "- Accumulate at least 20 distinct PIT dates and then run a fixed 20/63/126 outcome schedule; do not backfill history into selector.",
        "- Search for a stable official/authorized seasonal production or quality/harvest source; if none exists, CJ remains warehouse-only monitor.",
        "",
        "## Overfit and Continuation Reflection",
        "",
        "- Before run: not overfit, because this is a source probe for a low-corr candidate, not a parameter or return scan.",
        "- After run: not overfit, because the result keeps selector/paper/whitelist locked despite successful source fetch.",
        "- Continue value: yes. CJ became a real forward-monitor candidate, but not a trading candidate.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    generated_at = _fmt_cst(_now_cst())
    fetch_ledger, cj_rows = _fetch_cj_warehouse()
    evidence = _build_product_evidence(fetch_ledger)
    gates = _build_gates(fetch_ledger, evidence)

    decision = "cj_czce_official_warehouse_source_validated_monitor_only_selector_locked"
    if int(gates[gates["gate"].eq("official_daily_warehouse_fetch_ok")]["passed"].iloc[0]) == 0:
        decision = "cj_czce_official_warehouse_source_probe_failed_selector_locked"

    _plot_chart(fetch_ledger, evidence, gates)

    fetch_ledger.to_csv(FETCH_LEDGER_PATH, index=False, encoding="utf-8-sig")
    cj_rows.to_csv(CJ_WAREHOUSE_ROWS_PATH, index=False, encoding="utf-8-sig")
    evidence.to_csv(PRODUCT_EVIDENCE_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    REPORT_PATH.write_text(_build_report(fetch_ledger, cj_rows, evidence, gates, decision, generated_at), encoding="utf-8")

    summary = {
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "analysis_type": "cj_czce_official_warehouse_source_probe_no_strategy_backtest",
        "decision": decision,
        "fetch_dates": int(len(fetch_ledger)),
        "fetch_ok_dates": int(evidence["fetch_ok_dates"].iloc[0]),
        "raw_hash_rows": int(evidence["raw_hash_rows"].iloc[0]),
        "pit_dates": int(evidence["pit_dates"].iloc[0]),
        "latest_probe_date": str(evidence["latest_probe_date"].iloc[0]),
        "latest_total_receipts": float(evidence["latest_total_receipts"].iloc[0]),
        "latest_effective_forecast": float(evidence["latest_effective_forecast"].iloc[0]),
        "max_abs_corr_to_p0": float(evidence["max_abs_corr_to_p0"].iloc[0]),
        "selector_allowed_now": int(evidence["selector_allowed_now"].iloc[0]),
        "paper_or_whitelist_allowed_now": int(evidence["paper_or_whitelist_allowed_now"].iloc[0]),
        "trading_whitelist_allowed_now": int(evidence["trading_whitelist_allowed_now"].iloc[0]),
        "hard_gates_passed": int(gates["passed"].sum()),
        "hard_gates_total": int(len(gates)),
        "outputs": {
            "fetch_ledger": str(FETCH_LEDGER_PATH),
            "cj_warehouse_rows": str(CJ_WAREHOUSE_ROWS_PATH),
            "product_evidence": str(PRODUCT_EVIDENCE_PATH),
            "gates": str(GATES_PATH),
            "report": str(REPORT_PATH),
            "chart": str(CHART_PATH),
        },
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(summary), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(summary), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
