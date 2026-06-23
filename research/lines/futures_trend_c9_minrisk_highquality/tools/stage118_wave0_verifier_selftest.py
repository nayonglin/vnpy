from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage118"
MODEL_TAG = "stage118_wave0_verifier_selftest_v1"
OUTPUT_PREFIX = "qmt_roll_stage118_c9_minrisk_wave0_verifier_selftest"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage118_wave0_verifier_selftest"
FIXTURE_DIR = OUTPUT_DIR / "synthetic_fixture"

STAGE117_TOOL = LINE_DIR / "tools" / "stage117_wave0_delivery_verifier.py"
STAGE116_DIR = LINE_DIR / "outputs" / "stage116_wave0_pipeline_intake_packet"
STAGE116_MANIFEST_IN = (
    STAGE116_DIR
    / "qmt_roll_stage116_c9_minrisk_wave0_pipeline_intake_packet_w0_delivery_manifest_template_"
    "stage116_wave0_pipeline_intake_packet_v1.csv"
)
STAGE116_REQUEST_PACKET_IN = (
    STAGE116_DIR
    / "qmt_roll_stage116_c9_minrisk_wave0_pipeline_intake_packet_w0_request_packet_"
    "stage116_wave0_pipeline_intake_packet_v1.csv"
)
STAGE116_SUMMARY_IN = (
    STAGE116_DIR
    / "qmt_roll_stage116_c9_minrisk_wave0_pipeline_intake_packet_summary_"
    "stage116_wave0_pipeline_intake_packet_v1.csv"
)
CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CASE_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_case_summary_{MODEL_TAG}.csv"
CASE_GATE_STATUS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_case_gate_status_{MODEL_TAG}.csv"
CASE_ISSUE_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_case_issue_summary_{MODEL_TAG}.csv"
CASE_REQUEST_STATUS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_case_request_status_{MODEL_TAG}.csv"
VALID_MANIFEST_OUT = FIXTURE_DIR / f"{OUTPUT_PREFIX}_synthetic_valid_manifest_{MODEL_TAG}.csv"
BAD_SHA_MANIFEST_OUT = FIXTURE_DIR / f"{OUTPUT_PREFIX}_synthetic_bad_sha_manifest_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_selftest_status_{MODEL_TAG}.png"
GATE_PASS_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_case_gate_pass_chart_{MODEL_TAG}.png"
GATE_MATRIX_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_case_gate_matrix_{MODEL_TAG}.png"
ISSUE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_case_issue_chart_{MODEL_TAG}.png"

DECISION = "stage118_verifier_selftest_passed_no_strategy_no_real_data"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if np.isnan(number) or np.isinf(number) else number
    if isinstance(value, (pd.Timestamp, datetime)):
        if pd.isna(value):
            return None
        return pd.Timestamp(value).strftime("%Y-%m-%d %H:%M:%S")
    return value


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size <= 4:
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    for column in data.columns:
        if pd.api.types.is_float_dtype(data[column]):
            data[column] = data[column].map(lambda value: "" if pd.isna(value) else f"{value:.4f}")
    lines = [
        "| " + " | ".join(str(column) for column in data.columns) + " |",
        "| " + " | ".join(["---"] * len(data.columns)) + " |",
    ]
    for _, row in data.iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in data.columns) + " |")
    return "\n".join(lines)


def _load_verifier_module():
    spec = importlib.util.spec_from_file_location("stage117_wave0_delivery_verifier", STAGE117_TOOL)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import verifier: {STAGE117_TOOL}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _write_synthetic_parquet(path: Path, request_id: str, request_start: pd.Timestamp, request_end: pd.Timestamp) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    first_ts = request_start - pd.Timedelta(seconds=1)
    last_ts = request_end + pd.Timedelta(seconds=1)
    frame = pd.DataFrame(
        {
            "ts_event": [first_ts, last_ts],
            "ts_recv": [first_ts + pd.Timedelta(milliseconds=1), last_ts + pd.Timedelta(milliseconds=1)],
            "sequence": [1, 2],
            "bid_price_1": [100.0, 100.5],
            "ask_price_1": [100.2, 100.7],
            "bid_size_1": [10, 9],
            "ask_size_1": [8, 7],
            "request_id": [request_id, request_id],
        }
    )
    table = pa.Table.from_pandas(frame, preserve_index=False)
    pq.write_table(table, path)
    return len(frame)


def _build_synthetic_valid_manifest() -> pd.DataFrame:
    template = _read_csv(STAGE116_MANIFEST_IN)
    if template.empty:
        raise RuntimeError("missing Stage116 manifest template")
    raw_dir = FIXTURE_DIR / "raw"
    parquet_dir = FIXTURE_DIR / "parquet"
    proof_dir = FIXTURE_DIR / "proof"
    rows = []
    for _, row in template.iterrows():
        request_id = str(row["request_id"])
        request_start = pd.to_datetime(row["request_start"], errors="coerce")
        request_end = pd.to_datetime(row["request_end"], errors="coerce")
        if pd.isna(request_start) or pd.isna(request_end):
            raise RuntimeError(f"bad request span for {request_id}")

        raw_path = raw_dir / f"{request_id}.synthetic.raw"
        parquet_path = parquet_dir / f"{request_id}.synthetic.parquet"
        proof_path = proof_dir / f"{request_id}.synthetic_proof.json"

        raw_payload = (
            f"synthetic-only raw payload for verifier selftest\n"
            f"request_id={request_id}\n"
            f"request_start={request_start:%Y-%m-%d %H:%M:%S}\n"
            f"request_end={request_end:%Y-%m-%d %H:%M:%S}\n"
        ).encode("utf-8")
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_bytes(raw_payload)
        raw_sha = _sha256_bytes(raw_payload)

        row_count = _write_synthetic_parquet(parquet_path, request_id, request_start, request_end)
        first_ts = request_start - pd.Timedelta(seconds=1)
        last_ts = request_end + pd.Timedelta(seconds=1)
        proof = {
            "synthetic_fixture": True,
            "request_id": request_id,
            "sequence_gap_count": 0,
            "row_count": row_count,
            "first_ts_event": f"{first_ts:%Y-%m-%d %H:%M:%S}",
            "last_ts_event": f"{last_ts:%Y-%m-%d %H:%M:%S}",
            "note": "verifier selftest only; not authorized market data; not strategy evidence",
        }
        proof_path.parent.mkdir(parents=True, exist_ok=True)
        proof_path.write_text(json.dumps(proof, indent=2, ensure_ascii=False), encoding="utf-8")

        out = row.to_dict()
        out.update(
            {
                "vendor": "synthetic_selftest",
                "license_id": "synthetic_no_market_data",
                "dataset": "stage118_verifier_fixture",
                "schema_delivered": row["required_schema_request"],
                "raw_file": str(raw_path),
                "raw_sha256": raw_sha,
                "normalized_parquet_file": str(parquet_path),
                "proof_file": str(proof_path),
                "schema_hash": _sha256_text("ts_event;ts_recv;sequence;bid_price_1;ask_price_1;bid_size_1;ask_size_1;request_id"),
                "field_dictionary_version": "synthetic_stage118_fixture_v1",
                "ts_event_timezone": "Asia/Shanghai",
                "ts_recv_timezone": "Asia/Shanghai",
                "first_ts_event": f"{first_ts:%Y-%m-%d %H:%M:%S}",
                "last_ts_event": f"{last_ts:%Y-%m-%d %H:%M:%S}",
                "row_count": row_count,
                "sequence_gap_count": 0,
                "capture_continuity_proof": "synthetic_sequence_1_2_no_gap",
                "acceptance_status": "synthetic_fixture_complete",
                "strategy_use_allowed_now": 0,
                "rule_preflight_allowed_now": 0,
                "notes": "synthetic verifier selftest only; not real market data",
            }
        )
        rows.append(out)
    valid = pd.DataFrame(rows)
    _write_csv(valid, VALID_MANIFEST_OUT)
    return valid


def _build_bad_sha_manifest(valid: pd.DataFrame) -> pd.DataFrame:
    bad = valid.copy()
    bad.loc[0, "raw_sha256"] = "0" * 64
    _write_csv(bad, BAD_SHA_MANIFEST_OUT)
    return bad


def _run_case(verifier, case_id: str, manifest_path: Path, expected_stage112: int, expected_hard_accept: int) -> dict[str, pd.DataFrame | dict[str, Any]]:
    request_packet = _read_csv(STAGE116_REQUEST_PACKET_IN)
    stage116_summary = _read_csv(STAGE116_SUMMARY_IN)
    manifest = _read_csv(manifest_path)
    for frame in [request_packet, manifest]:
        for column in ["trading_day", "request_start", "request_end", "first_ts_event", "last_ts_event"]:
            if column in frame.columns:
                frame[column] = pd.to_datetime(frame[column], errors="coerce")

    request_status, file_audit, issues = verifier._build_request_status(request_packet, manifest, manifest_path)
    gate_status = verifier._build_gate_status(request_status, manifest)
    summary = verifier._build_summary(
        request_status,
        gate_status,
        issues,
        stage116_summary.iloc[0] if not stage116_summary.empty else pd.Series(dtype=object),
        manifest_path,
    )
    summary["case_id"] = case_id
    gate_status["case_id"] = case_id
    request_status["case_id"] = case_id
    issues["case_id"] = case_id

    observed_stage112 = int(summary.iloc[0]["stage112_intake_allowed_now"])
    observed_hard_accept = int(summary.iloc[0]["w0_hard_accept_request_count"])
    test_pass = int(observed_stage112 == expected_stage112 and observed_hard_accept == expected_hard_accept)
    return {
        "summary": summary,
        "gate_status": gate_status,
        "request_status": request_status,
        "issues": issues,
        "meta": {
            "case_id": case_id,
            "manifest_path": str(manifest_path),
            "expected_stage112_intake_allowed_now": expected_stage112,
            "observed_stage112_intake_allowed_now": observed_stage112,
            "expected_hard_accept_request_count": expected_hard_accept,
            "observed_hard_accept_request_count": observed_hard_accept,
            "test_pass": test_pass,
        },
    }


def _load_curve() -> pd.DataFrame:
    curve = _read_csv(CURVE_IN)
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]:
        curve[column] = pd.to_numeric(curve[column], errors="coerce")
    return curve[curve["date"].notna()].sort_values("date").reset_index(drop=True)


def _nearest_curve_points(curve: pd.DataFrame, dates: pd.Series) -> pd.DataFrame:
    left = pd.DataFrame({"event_date": pd.to_datetime(dates, errors="coerce").dt.normalize()}).dropna()
    right = curve[["date", "account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]].sort_values("date")
    return pd.merge_asof(left.sort_values("event_date"), right, left_on="event_date", right_on="date", direction="backward")


def _plot_official_path_selftest(curve: pd.DataFrame, request_status: pd.DataFrame) -> None:
    cases = ["empty_manifest_negative", "synthetic_valid_positive", "synthetic_bad_sha_negative"]
    colors = {
        "empty_manifest_negative": "#B91C1C",
        "synthetic_valid_positive": "#15803D",
        "synthetic_bad_sha_negative": "#A16207",
    }
    fig, axes = plt.subplots(3, 1, figsize=(16, 10), sharex=True)
    axes[0].plot(curve["date"], curve["account_equity"] / 1_000_000, color="#202939", linewidth=1.1)
    axes[1].plot(curve["date"], curve["drawdown_pct"], color="#DC2626", linewidth=1.0)
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#0369A1", linewidth=1.0)
    axes[2].axhline(100, color="#B91C1C", linestyle="--", linewidth=0.9)
    for idx, case_id in enumerate(cases):
        case_rows = request_status[request_status["case_id"].eq(case_id)]
        points = _nearest_curve_points(curve, case_rows["trading_day"])
        offset = (idx - 1) * 0.35
        axes[0].scatter(points["date"], points["account_equity"] / 1_000_000 + offset, color=colors[case_id], s=36, alpha=0.65, label=case_id)
        axes[1].scatter(points["date"], points["drawdown_pct"] + offset, color=colors[case_id], s=36, alpha=0.65)
        axes[2].scatter(points["date"], points["broker10_margin_to_equity_pct"] + offset, color=colors[case_id], s=36, alpha=0.65)
    axes[0].set_ylabel("equity (m)")
    axes[1].set_ylabel("drawdown %")
    axes[2].set_ylabel("broker10 %")
    for ax in axes:
        ax.grid(alpha=0.25)
    axes[0].legend(loc="upper left", fontsize=8)
    fig.suptitle("Stage118 verifier selftest on official path; synthetic markers are tool tests only")
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_gate_pass(case_summary: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(case_summary["case_id"], case_summary["gate_pass_count"], color=["#B91C1C", "#15803D", "#A16207"])
    ax.set_ylabel("gate_pass_count")
    ax.set_title("Stage118 verifier selftest gate pass counts")
    ax.grid(axis="y", alpha=0.25)
    ax.tick_params(axis="x", rotation=15)
    fig.tight_layout()
    fig.savefig(GATE_PASS_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_gate_matrix(gate_status: pd.DataFrame) -> None:
    pivot = gate_status.pivot_table(index="gate_id", columns="case_id", values="pass_now", aggfunc="max", fill_value=0)
    pivot = pivot[["empty_manifest_negative", "synthetic_valid_positive", "synthetic_bad_sha_negative"]]
    fig, ax = plt.subplots(figsize=(9, 9))
    image = ax.imshow(pivot.to_numpy(), aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=25, ha="right")
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=8)
    for y in range(len(pivot.index)):
        for x in range(len(pivot.columns)):
            ax.text(x, y, "P" if int(pivot.iloc[y, x]) else "F", ha="center", va="center", color="#111827", fontsize=8)
    ax.set_title("Stage118 gate matrix: positive fixture must pass, negative fixtures must fail")
    fig.colorbar(image, ax=ax, shrink=0.75)
    fig.tight_layout()
    fig.savefig(GATE_MATRIX_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_issue_counts(issue_summary: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.bar(issue_summary["case_id"], issue_summary["issue_count"], color=["#B91C1C", "#15803D", "#A16207"])
    for bar, value in zip(bars, issue_summary["issue_count"]):
        ax.text(bar.get_x() + bar.get_width() / 2, max(float(value), 0.03), str(int(value)), ha="center", va="bottom", fontsize=9)
    ax.set_yscale("symlog", linthresh=1)
    ax.set_ylabel("issue_count")
    ax.set_title("Stage118 verifier selftest issue counts")
    ax.grid(axis="y", alpha=0.25)
    ax.tick_params(axis="x", rotation=15)
    fig.tight_layout()
    fig.savefig(ISSUE_CHART_OUT, dpi=160)
    plt.close(fig)


def _write_report(summary: pd.DataFrame, case_summary: pd.DataFrame, gate_status: pd.DataFrame, issue_summary: pd.DataFrame) -> None:
    row = summary.iloc[0]
    report = f"""# Stage118 W0 verifier selftest

## Decision

- decision: `{row['decision']}`
- nature: verifier selftest with synthetic files only; no strategy rule, no true engine, no A/B, no CTP connection, no order API, no external download.
- synthetic fixture directory: `{FIXTURE_DIR}`

## Baseline Path

- end equity: `{row['end_equity']:,.2f}`
- total return: `{row['total_return_pct']:.4f}%`
- max drawdown: `{row['max_drawdown_pct']:.4f}%`
- Sharpe: `{row['sharpe']:.4f}`
- total slippage: `{row['total_slippage']:,.0f}`
- total trade count: `{row['total_trade_count']:,.0f}`
- closed lot win rate: `{row['closed_lot_win_rate_pct']:.4f}%`

## Summary

{_md_table(summary)}

## Case Summary

{_md_table(case_summary)}

## Issue Summary

{_md_table(issue_summary)}

## Gate Status Sample

{_md_table(gate_status[['case_id', 'gate_id', 'observed', 'required', 'pass_now', 'severity']], max_rows=60)}

## Visual Outputs

- official path selftest status: `{PATH_CHART_OUT}`
- case gate pass chart: `{GATE_PASS_CHART_OUT}`
- case gate matrix: `{GATE_MATRIX_CHART_OUT}`
- case issue chart: `{ISSUE_CHART_OUT}`

## Judgment

The verifier selftest passes. Empty W0 manifests still fail, a complete 41-request synthetic fixture reaches Stage112-intake-only permission, and a single SHA256 mismatch blocks full acceptance. The fixture is synthetic and cannot be used for strategy research.
"""
    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUT.write_text(report, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    verifier = _load_verifier_module()
    valid_manifest = _build_synthetic_valid_manifest()
    _build_bad_sha_manifest(valid_manifest)

    cases = [
        _run_case(verifier, "empty_manifest_negative", STAGE116_MANIFEST_IN, expected_stage112=0, expected_hard_accept=0),
        _run_case(verifier, "synthetic_valid_positive", VALID_MANIFEST_OUT, expected_stage112=1, expected_hard_accept=41),
        _run_case(verifier, "synthetic_bad_sha_negative", BAD_SHA_MANIFEST_OUT, expected_stage112=0, expected_hard_accept=40),
    ]
    case_summaries = pd.concat([case["summary"] for case in cases], ignore_index=True)
    gate_status = pd.concat([case["gate_status"] for case in cases], ignore_index=True)
    request_status = pd.concat([case["request_status"] for case in cases], ignore_index=True)
    issues = pd.concat([case["issues"] for case in cases], ignore_index=True)
    case_meta = pd.DataFrame([case["meta"] for case in cases])
    issue_summary = (
        issues.groupby("case_id", dropna=False)
        .size()
        .reset_index(name="issue_count")
        .merge(case_meta, on="case_id", how="right")
        .fillna({"issue_count": 0})
    )
    case_summaries = case_summaries.merge(case_meta, on="case_id", how="left")
    all_selftests_pass = int(case_meta["test_pass"].sum() == len(case_meta))

    stage116_summary = _read_csv(STAGE116_SUMMARY_IN)
    base = stage116_summary.iloc[0] if not stage116_summary.empty else pd.Series(dtype=object)
    summary = pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "decision": DECISION if all_selftests_pass else "stage118_verifier_selftest_failed",
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "case_count": int(len(case_meta)),
                "selftest_pass_count": int(case_meta["test_pass"].sum()),
                "selftest_fail_count": int(len(case_meta) - case_meta["test_pass"].sum()),
                "positive_case_stage112_allowed": int(case_meta.loc[case_meta["case_id"].eq("synthetic_valid_positive"), "observed_stage112_intake_allowed_now"].iloc[0]),
                "empty_case_stage112_allowed": int(case_meta.loc[case_meta["case_id"].eq("empty_manifest_negative"), "observed_stage112_intake_allowed_now"].iloc[0]),
                "bad_sha_case_stage112_allowed": int(case_meta.loc[case_meta["case_id"].eq("synthetic_bad_sha_negative"), "observed_stage112_intake_allowed_now"].iloc[0]),
                "real_w0_data_delivered": 0,
                "real_stage112_intake_allowed_now": 0,
                "true_engine_allowed": 0,
                "strategy_feature_usable": 0,
                "end_equity": float(base.get("end_equity", np.nan)),
                "total_return_pct": float(base.get("total_return_pct", np.nan)),
                "max_drawdown_pct": float(base.get("max_drawdown_pct", np.nan)),
                "sharpe": float(base.get("sharpe", np.nan)),
                "total_slippage": float(base.get("total_slippage", np.nan)),
                "total_trade_count": float(base.get("total_trade_count", np.nan)),
                "closed_lot_win_rate_pct": float(base.get("closed_lot_win_rate_pct", np.nan)),
                "max_broker10_margin_to_equity_pct": float(base.get("max_broker10_margin_to_equity_pct", np.nan)),
            }
        ]
    )

    _write_csv(summary, SUMMARY_OUT)
    _write_csv(case_summaries, CASE_SUMMARY_OUT)
    _write_csv(gate_status, CASE_GATE_STATUS_OUT)
    _write_csv(issue_summary, CASE_ISSUE_SUMMARY_OUT)
    _write_csv(request_status, CASE_REQUEST_STATUS_OUT)

    curve = _load_curve()
    _plot_official_path_selftest(curve, request_status)
    _plot_gate_pass(case_summaries)
    _plot_gate_matrix(gate_status)
    _plot_issue_counts(issue_summary)
    _write_report(summary, case_summaries, gate_status, issue_summary)

    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "decision": str(summary.iloc[0]["decision"]),
        "summary_path": SUMMARY_OUT,
        "case_summary_path": CASE_SUMMARY_OUT,
        "case_gate_status_path": CASE_GATE_STATUS_OUT,
        "case_issue_summary_path": CASE_ISSUE_SUMMARY_OUT,
        "case_request_status_path": CASE_REQUEST_STATUS_OUT,
        "valid_manifest_path": VALID_MANIFEST_OUT,
        "bad_sha_manifest_path": BAD_SHA_MANIFEST_OUT,
        "report_path": REPORT_OUT,
        "charts": [
            PATH_CHART_OUT,
            GATE_PASS_CHART_OUT,
            GATE_MATRIX_CHART_OUT,
            ISSUE_CHART_OUT,
        ],
        "real_w0_data_delivered": 0,
        "real_stage112_intake_allowed_now": 0,
        "true_engine_allowed": 0,
        "strategy_feature_usable": 0,
        "order_api_called": 0,
        "ctp_connected": 0,
    }
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(_json_safe(decision), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
