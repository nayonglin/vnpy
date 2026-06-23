from __future__ import annotations

from datetime import datetime
from io import BytesIO, StringIO
import json
from pathlib import Path
import sys
from typing import Any
import zipfile

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage063"
MODEL_TAG = "stage063_dce_official_http_direct_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage063_c9_minrisk_dce_official_http_direct_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
if str(EXAMPLE_DIR) not in sys.path:
    sys.path.insert(0, str(EXAMPLE_DIR))

from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
STAGE005_DIR = LINE_DIR / "outputs" / "stage005_signal_quality_visual_forensics"
STAGE028_DIR = LINE_DIR / "outputs" / "stage028_member_rank_position_forensics"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage063_dce_official_http_direct_audit"

FEATURES_IN = (
    STAGE028_DIR
    / "qmt_roll_stage028_c9_minrisk_member_rank_position_forensics_features_"
    "stage028_member_rank_position_forensics_v1.csv"
)
OFFICIAL_CURVE_IN = (
    STAGE005_DIR
    / "qmt_roll_stage005_c9_minrisk_signal_quality_visual_forensics_official_curve_"
    "stage005_signal_quality_visual_forensics_v1.csv"
)

HTTP_PROBE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_http_probe_{MODEL_TAG}.csv"
GATES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
ROUTE_STATUS_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_route_status_chart_{MODEL_TAG}.png"
DCE_MISSING_CONTEXT_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_dce_missing_context_chart_{MODEL_TAG}.png"

PROBE_DATES = ["20240603", "20210301", "20251028"]
HTTP_TIMEOUT = 12

DCE_LANDING_URL = "http://www.dce.com.cn/dalianshangpin/xqsj/tjsj26/rtj/rcjccpm/index.html"
DCE_BATCH_URL = "http://www.dce.com.cn/dcereport/publicweb/dailystat/memberDealPosi/batchDownload"
DCE_LEGACY_URL = "http://portal.dce.com.cn/publicweb/quotesdata/memberDealPosiQuotes.html"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if np.isnan(number) or np.isinf(number) else number
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _md_table(frame: pd.DataFrame, max_rows: int = 30) -> str:
    if frame.empty:
        return "_empty_"
    view = frame.head(max_rows).copy()
    return view.to_markdown(index=False)


def _probe(
    *,
    probe_id: str,
    route_type: str,
    method: str,
    url: str,
    date: str,
    expected_kind: str,
    json_payload: dict[str, Any] | None = None,
    data_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "probe_id": probe_id,
        "route_type": route_type,
        "method": method,
        "url": url,
        "date": date,
        "expected_kind": expected_kind,
        "status": "error",
        "http_status": np.nan,
        "content_type": "",
        "content_bytes": 0,
        "is_zip": 0,
        "zip_member_count": 0,
        "zip_sample_members": "",
        "html_table_count": 0,
        "html_selbox_count": 0,
        "html_title": "",
        "data_ready": 0,
        "error_type": "",
        "error_message": "",
    }
    try:
        if method.upper() == "GET":
            response = requests.get(url, timeout=HTTP_TIMEOUT)
        else:
            response = requests.post(url, json=json_payload, data=data_payload, timeout=HTTP_TIMEOUT)
        row["http_status"] = int(response.status_code)
        row["content_type"] = str(response.headers.get("content-type", ""))
        row["content_bytes"] = int(len(response.content))

        is_zip = zipfile.is_zipfile(BytesIO(response.content))
        row["is_zip"] = int(is_zip)
        if is_zip:
            with zipfile.ZipFile(BytesIO(response.content), mode="r") as zf:
                names = zf.namelist()
            row["zip_member_count"] = int(len(names))
            row["zip_sample_members"] = "|".join(names[:8])

        text = response.text if "html" in row["content_type"].lower() or response.content else ""
        if text:
            soup = BeautifulSoup(text, "lxml")
            title = soup.find("title")
            row["html_title"] = title.get_text(" ", strip=True)[:200] if title else ""
            row["html_selbox_count"] = int(len(soup.find_all(attrs={"class": "selBox"})))
            try:
                tables = pd.read_html(StringIO(text))
                row["html_table_count"] = int(len(tables))
            except ValueError:
                row["html_table_count"] = 0

        if expected_kind == "zip":
            row["data_ready"] = int(is_zip and row["zip_member_count"] > 0)
        elif expected_kind == "html_table":
            row["data_ready"] = int(row["html_table_count"] > 0)
        else:
            row["data_ready"] = int(200 <= int(response.status_code) < 300)

        row["status"] = "ok" if row["data_ready"] else "response_no_data"
        if int(response.status_code) >= 400:
            row["status"] = "http_error"
            if not row["error_type"]:
                row["error_type"] = f"HTTP{response.status_code}"
                row["error_message"] = row["html_title"] or str(response.content[:120])
    except Exception as exc:  # noqa: BLE001
        row["status"] = "network_error"
        row["error_type"] = type(exc).__name__
        row["error_message"] = str(exc)[:500]
    return row


def run_http_probes() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    rows.append(
        _probe(
            probe_id="dce_official_landing_get",
            route_type="landing",
            method="GET",
            url=DCE_LANDING_URL,
            date="current",
            expected_kind="html",
        )
    )
    for date in PROBE_DATES:
        rows.append(
            _probe(
                probe_id=f"batch_json_source_payload_{date}",
                route_type="batch_download_json_source_payload",
                method="POST",
                url=DCE_BATCH_URL,
                date=date,
                expected_kind="zip",
                json_payload={
                    "tradeDate": date,
                    "varietyId": "a",
                    "contractId": "a2601",
                    "tradeType": "1",
                    "lang": "zh",
                },
            )
        )
        rows.append(
            _probe(
                probe_id=f"batch_form_jm_all_{date}",
                route_type="batch_download_form_jm_all",
                method="POST",
                url=DCE_BATCH_URL,
                date=date,
                expected_kind="zip",
                data_payload={
                    "tradeDate": date,
                    "varietyId": "jm",
                    "contractId": "all",
                    "tradeType": "1",
                    "lang": "zh",
                },
            )
        )
        year = int(date[:4])
        month_zero_based = int(date[4:6]) - 1
        day = int(date[6:8])
        rows.append(
            _probe(
                probe_id=f"legacy_html_jm_all_{date}",
                route_type="legacy_html_jm_all",
                method="POST",
                url=DCE_LEGACY_URL,
                date=date,
                expected_kind="html_table",
                data_payload={
                    "memberDealPosiQuotes.variety": "jm",
                    "memberDealPosiQuotes.trade_type": "0",
                    "year": year,
                    "month": month_zero_based,
                    "day": str(day).zfill(2),
                    "contract.contract_id": "all",
                    "contract.variety_id": "jm",
                    "contract": "",
                },
            )
        )
    return pd.DataFrame(rows)


def load_context() -> tuple[pd.DataFrame, pd.DataFrame]:
    features = pd.read_csv(FEATURES_IN)
    curve = pd.read_csv(OFFICIAL_CURVE_IN)
    features["exit_date_ts"] = pd.to_datetime(features["exit_date"])
    features["member_ready"] = features["member_feature_ready_stage028"].fillna(False).astype(bool)
    features["member_missing"] = ~features["member_ready"]
    features["exchange"] = features["exchange"].fillna("").astype(str)
    curve["date"] = pd.to_datetime(curve["date"])
    return features, curve


def build_gates(probes: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
    batch_ready = int(
        probes["route_type"].astype(str).str.startswith("batch_download").astype(bool).to_numpy().dot(
            probes["data_ready"].astype(int).to_numpy()
        )
        > 0
    )
    legacy_ready = int(
        ((probes["route_type"].eq("legacy_html_jm_all")) & probes["data_ready"].eq(1)).any()
    )
    landing_ready = int(((probes["route_type"].eq("landing")) & probes["data_ready"].eq(1)).any())
    dce = features[features["exchange"].eq("DCE")]
    gates = [
        {
            "gate": "dce_official_landing_reachable",
            "required": "DCE official rank page returns HTML",
            "value": landing_ready,
            "threshold": 1,
            "passed": landing_ready,
            "hard_gate": 0,
        },
        {
            "gate": "dce_batch_download_returns_zip",
            "required": "batchDownload returns a parseable zip for at least one probe date",
            "value": batch_ready,
            "threshold": 1,
            "passed": batch_ready,
            "hard_gate": 1,
        },
        {
            "gate": "dce_legacy_html_returns_table",
            "required": "legacy portal returns parseable member-rank HTML table for at least one probe date",
            "value": legacy_ready,
            "threshold": 1,
            "passed": legacy_ready,
            "hard_gate": 1,
        },
        {
            "gate": "dce_member_missing_not_small",
            "required": "DCE missing lot count is material, so direct route must work before strategy research",
            "value": int(len(dce[dce["member_missing"]])),
            "threshold": 1,
            "passed": int(len(dce[dce["member_missing"]]) > 0),
            "hard_gate": 1,
        },
        {
            "gate": "no_strategy_backtest_or_parameter_search",
            "required": "stage is data-route forensic only",
            "value": 1,
            "threshold": 1,
            "passed": 1,
            "hard_gate": 1,
        },
    ]
    return pd.DataFrame(gates)


def plot_route_status(probes: pd.DataFrame) -> None:
    view = probes[~probes["route_type"].eq("landing")].copy()
    if view.empty:
        return
    route_order = list(dict.fromkeys(view["route_type"].tolist()))
    date_order = list(dict.fromkeys(view["date"].tolist()))
    matrix = np.zeros((len(route_order), len(date_order)))
    for i, route in enumerate(route_order):
        for j, date in enumerate(date_order):
            row = view[(view["route_type"].eq(route)) & (view["date"].eq(date))]
            if row.empty:
                matrix[i, j] = np.nan
                continue
            item = row.iloc[0]
            if int(item.get("data_ready", 0)) == 1:
                matrix[i, j] = 1.0
            elif str(item.get("status", "")) == "response_no_data":
                matrix[i, j] = 0.5
            else:
                matrix[i, j] = 0.0
    fig, ax = plt.subplots(figsize=(10, 4.8))
    image = ax.imshow(matrix, aspect="auto", vmin=0, vmax=1, cmap="RdYlGn")
    ax.set_xticks(range(len(date_order)))
    ax.set_xticklabels(date_order, rotation=0)
    ax.set_yticks(range(len(route_order)))
    ax.set_yticklabels(route_order)
    ax.set_title("Stage063 DCE direct official-route data readiness")
    for i in range(len(route_order)):
        for j in range(len(date_order)):
            value = matrix[i, j]
            if np.isnan(value):
                label = "NA"
            elif value == 1:
                label = "data"
            elif value == 0.5:
                label = "html"
            else:
                label = "fail"
            ax.text(j, i, label, ha="center", va="center", fontsize=9, color="black")
    fig.colorbar(image, ax=ax, fraction=0.045, pad=0.04)
    fig.tight_layout()
    fig.savefig(ROUTE_STATUS_CHART_OUT, dpi=150)
    plt.close(fig)


def plot_dce_context(features: pd.DataFrame, curve: pd.DataFrame) -> None:
    dce_missing = features[features["exchange"].eq("DCE") & features["member_missing"]].copy()
    dce_missing = dce_missing.sort_values("exit_date_ts")
    context_curve = curve[["date", "account_equity", "drawdown_pct"]].copy()
    cashflow = dce_missing.groupby("exit_date_ts")["realized_pnl"].sum().sort_index().cumsum()
    context_curve["dce_missing_cum_pnl"] = context_curve["date"].map(cashflow).ffill().fillna(0.0)
    fig, axes = plt.subplots(3, 1, figsize=(15, 9), sharex=True)
    axes[0].plot(context_curve["date"], context_curve["account_equity"], color="#1f77b4", lw=1.4)
    axes[0].set_yscale("log")
    axes[0].set_title("Stage063 official equity with DCE member-rank missing context")
    axes[0].grid(True, alpha=0.25)
    axes[1].plot(context_curve["date"], context_curve["drawdown_pct"], color="#d62728", lw=1.1)
    axes[1].axhline(-40, color="#7f7f7f", lw=0.8, ls="--")
    axes[1].set_ylabel("drawdown %")
    axes[1].grid(True, alpha=0.25)
    axes[2].plot(context_curve["date"], context_curve["dce_missing_cum_pnl"], color="#9467bd", lw=1.4)
    axes[2].axhline(0, color="#7f7f7f", lw=0.8)
    axes[2].set_ylabel("DCE missing cum PnL")
    axes[2].grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(DCE_MISSING_CONTEXT_CHART_OUT, dpi=150)
    plt.close(fig)


def build_summary(probes: pd.DataFrame, gates: pd.DataFrame, features: pd.DataFrame) -> dict[str, Any]:
    dce = features[features["exchange"].eq("DCE")].copy()
    dce_missing = dce[dce["member_missing"]]
    data_ready_count = int(probes["data_ready"].sum())
    batch_zip_count = int((probes["route_type"].astype(str).str.startswith("batch_download") & probes["is_zip"].eq(1)).sum())
    legacy_table_count = int((probes["route_type"].eq("legacy_html_jm_all") & (probes["html_table_count"] > 0)).sum())
    hard_gates = gates[gates["hard_gate"].eq(1)]
    repair_ready = int(
        (
            gates[gates["gate"].eq("dce_batch_download_returns_zip")]["passed"].iloc[0] == 1
            or gates[gates["gate"].eq("dce_legacy_html_returns_table")]["passed"].iloc[0] == 1
        )
    )
    decision = (
        "stage063_dce_direct_official_http_not_repair_ready"
        if not repair_ready
        else "stage063_dce_direct_official_http_repair_possible_data_engineering_only"
    )
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "decision": decision,
        "candidate_like": False,
        "ab_triggered": False,
        "strategy_rule_created": False,
        "probe_date_count": len(PROBE_DATES),
        "http_probe_count": int(len(probes)),
        "data_ready_count": data_ready_count,
        "batch_zip_count": batch_zip_count,
        "legacy_table_count": legacy_table_count,
        "hard_gate_passed_count": int(hard_gates["passed"].sum()),
        "hard_gate_count": int(len(hard_gates)),
        "direct_repair_ready": bool(repair_ready),
        "dce_lot_count": int(len(dce)),
        "dce_member_missing_count": int(len(dce_missing)),
        "dce_member_missing_net_pnl": float(dce_missing["realized_pnl"].sum()),
        "dce_member_missing_positive_pnl": float(dce_missing[dce_missing["realized_pnl"] > 0]["realized_pnl"].sum()),
        "dce_member_missing_negative_pnl": float(dce_missing[dce_missing["realized_pnl"] < 0]["realized_pnl"].sum()),
        "next_action": (
            "Do not continue DCE/member-rank strategy research from current public routes. "
            "Use a vendor/authorized dataset or build a separate browser/manual collector proof before rebinding."
            if not repair_ready
            else "Keep this as data engineering only; no strategy rule until full historical point-in-time backfill is proven."
        ),
    }


def write_report(summary: dict[str, Any], probes: pd.DataFrame, gates: pd.DataFrame) -> None:
    lines = [
        "# Stage063 DCE official HTTP direct audit",
        "",
        "## Decision",
        "",
        f"- decision: `{summary['decision']}`",
        f"- direct repair ready: `{summary['direct_repair_ready']}`",
        f"- data-ready probes: `{summary['data_ready_count']}/{summary['http_probe_count']}`",
        f"- batch zip count: `{summary['batch_zip_count']}`",
        f"- legacy html table count: `{summary['legacy_table_count']}`",
        f"- DCE member missing: `{summary['dce_member_missing_count']}/{summary['dce_lot_count']}`",
        f"- DCE member missing net PnL: `{summary['dce_member_missing_net_pnl']:.2f}`",
        f"- next action: {summary['next_action']}",
        "",
        "## Gates",
        "",
        _md_table(gates),
        "",
        "## HTTP Probes",
        "",
        _md_table(
            probes[
                [
                    "probe_id",
                    "route_type",
                    "date",
                    "status",
                    "http_status",
                    "content_type",
                    "content_bytes",
                    "is_zip",
                    "zip_member_count",
                    "html_table_count",
                    "html_selbox_count",
                    "error_type",
                    "error_message",
                ]
            ],
            max_rows=50,
        ),
        "",
        "## Visual Outputs",
        "",
        f"- route status: `{ROUTE_STATUS_CHART_OUT}`",
        f"- DCE missing context: `{DCE_MISSING_CONTEXT_CHART_OUT}`",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    probes = run_http_probes()
    features, curve = load_context()
    gates = build_gates(probes, features)
    summary = build_summary(probes, gates, features)

    probes.to_csv(HTTP_PROBE_OUT, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_OUT, index=False, encoding="utf-8-sig")
    pd.DataFrame([summary]).to_csv(SUMMARY_OUT, index=False, encoding="utf-8-sig")
    DECISION_OUT.write_text(json.dumps(_json_safe(summary), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    plot_route_status(probes)
    plot_dce_context(features, curve)
    write_report(summary, probes, gates)
    print(json.dumps(_json_safe(summary), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
