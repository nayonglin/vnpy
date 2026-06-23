from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage120"
MODEL_TAG = "stage120_wave0_schema_contract_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage120_c9_minrisk_wave0_schema_contract_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage120_wave0_schema_contract_audit"

CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)
STAGE116_DIR = LINE_DIR / "outputs" / "stage116_wave0_pipeline_intake_packet"
STAGE116_SUMMARY_IN = (
    STAGE116_DIR
    / "qmt_roll_stage116_c9_minrisk_wave0_pipeline_intake_packet_summary_"
    "stage116_wave0_pipeline_intake_packet_v1.csv"
)
STAGE116_REQUEST_PACKET_IN = (
    STAGE116_DIR
    / "qmt_roll_stage116_c9_minrisk_wave0_pipeline_intake_packet_w0_request_packet_"
    "stage116_wave0_pipeline_intake_packet_v1.csv"
)
STAGE116_MANIFEST_TEMPLATE_IN = (
    STAGE116_DIR
    / "qmt_roll_stage116_c9_minrisk_wave0_pipeline_intake_packet_w0_delivery_manifest_template_"
    "stage116_wave0_pipeline_intake_packet_v1.csv"
)
STAGE119_SYNTHETIC_MANIFEST_IN = (
    LINE_DIR
    / "outputs"
    / "stage119_wave0_drop_manifest_builder"
    / "qmt_roll_stage119_c9_minrisk_wave0_drop_manifest_builder_synthetic_drop_positive_built_manifest_"
    "stage119_wave0_drop_manifest_builder_v1.csv"
)

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CONTRACT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_canonical_field_contract_{MODEL_TAG}.csv"
REQUEST_SCHEMA_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_w0_request_schema_status_{MODEL_TAG}.csv"
MANIFEST_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_manifest_schema_audit_{MODEL_TAG}.csv"
GATE_STATUS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_schema_contract_gate_status_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_schema_status_{MODEL_TAG}.png"
CONTRACT_MATRIX_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_contract_field_matrix_{MODEL_TAG}.png"
REQUEST_MATRIX_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_request_schema_exchange_matrix_{MODEL_TAG}.png"
SCHEMA_GAP_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_synthetic_schema_gap_chart_{MODEL_TAG}.png"

DECISION = "stage120_schema_contract_built_real_w0_missing_no_strategy"
PASS_DECISION = "stage120_schema_contract_real_manifest_passed_no_strategy_no_stage112_yet"
MBP10 = "authorized_mbp10_l2_minimum"
MBO = "authorized_mbo_l3_preferred"


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


def _clean(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none", "nat"} else text


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


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_curve() -> pd.DataFrame:
    curve = _read_csv(CURVE_IN)
    if curve.empty:
        raise RuntimeError(f"missing curve input: {CURVE_IN}")
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]:
        curve[column] = pd.to_numeric(curve[column], errors="coerce")
    return curve[curve["date"].notna()].sort_values("date").reset_index(drop=True)


def _nearest_curve_points(curve: pd.DataFrame, dates: pd.Series) -> pd.DataFrame:
    left = pd.DataFrame({"event_date": pd.to_datetime(dates, errors="coerce").dt.normalize()}).dropna()
    right = curve[["date", "account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]].sort_values("date")
    return pd.merge_asof(left.sort_values("event_date"), right, left_on="event_date", right_on="date", direction="backward")


def _contract_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = [
        {
            "canonical_field": "ts_event",
            "semantic_group": "time",
            "required_for_mbp10": 1,
            "required_for_mbo": 1,
            "accepted_aliases": "ts_event,event_time,exchange_ts,matching_engine_ts",
            "description": "Matching-engine event timestamp, point-in-time sort key for market state.",
        },
        {
            "canonical_field": "ts_recv",
            "semantic_group": "time",
            "required_for_mbp10": 1,
            "required_for_mbo": 1,
            "accepted_aliases": "ts_recv,recv_time,capture_ts,server_recv_ts",
            "description": "Capture-server receive timestamp; used to audit latency and historical filtering semantics.",
        },
        {
            "canonical_field": "sequence",
            "semantic_group": "continuity",
            "required_for_mbp10": 1,
            "required_for_mbo": 1,
            "accepted_aliases": "sequence,seq,sequence_number,msg_seq",
            "description": "Venue or normalized event sequence, paired with proof that sequence_gap_count is zero.",
        },
    ]
    for level in range(1, 11):
        zero = level - 1
        for side in ["bid", "ask"]:
            rows.append(
                {
                    "canonical_field": f"{side}_price_{level}",
                    "semantic_group": "mbp10_price_ladder",
                    "required_for_mbp10": 1,
                    "required_for_mbo": 0,
                    "accepted_aliases": f"{side}_price_{level},{side}_px_{level},{side}_px_{zero:02d},levels",
                    "description": f"Top-ten market-by-price {side} price level {level}. Nested levels are accepted only as a normalized MBP-10 ladder.",
                }
            )
            rows.append(
                {
                    "canonical_field": f"{side}_size_{level}",
                    "semantic_group": "mbp10_size_ladder",
                    "required_for_mbp10": 1,
                    "required_for_mbo": 0,
                    "accepted_aliases": f"{side}_size_{level},{side}_sz_{level},{side}_qty_{level},{side}_sz_{zero:02d},levels",
                    "description": f"Top-ten market-by-price {side} aggregate size level {level}.",
                }
            )
    rows.extend(
        [
            {
                "canonical_field": "action",
                "semantic_group": "mbo_order_event",
                "required_for_mbp10": 0,
                "required_for_mbo": 1,
                "accepted_aliases": "action,event_action,event_type,type",
                "description": "Order-book event action such as add, cancel, modify, clear, trade, or fill.",
            },
            {
                "canonical_field": "side",
                "semantic_group": "mbo_order_event",
                "required_for_mbp10": 0,
                "required_for_mbo": 1,
                "accepted_aliases": "side,direction,aggressor_side",
                "description": "Bid/ask side or aggressor side as provided by the data schema.",
            },
            {
                "canonical_field": "price",
                "semantic_group": "mbo_order_event",
                "required_for_mbp10": 0,
                "required_for_mbo": 1,
                "accepted_aliases": "price,px,order_price",
                "description": "Order or event price in normalized contract price units.",
            },
            {
                "canonical_field": "size",
                "semantic_group": "mbo_order_event",
                "required_for_mbp10": 0,
                "required_for_mbo": 1,
                "accepted_aliases": "size,qty,quantity,order_size",
                "description": "Order or event quantity.",
            },
            {
                "canonical_field": "order_id",
                "semantic_group": "mbo_order_event",
                "required_for_mbp10": 0,
                "required_for_mbo": 1,
                "accepted_aliases": "order_id,orderid,oid,venue_order_id",
                "description": "Venue order identifier required for L3 state reconstruction.",
            },
        ]
    )
    return rows


def _build_contract() -> pd.DataFrame:
    contract = pd.DataFrame(_contract_rows())
    contract["hard_required_any_schema"] = (
        contract[["required_for_mbp10", "required_for_mbo"]].max(axis=1).astype(int)
    )
    contract["contract_version"] = MODEL_TAG
    contract["source_basis"] = "Databento-style MBO/MBP10 plus vendor-neutral normalized parquet contract"
    fields_for_hash = contract[
        [
            "canonical_field",
            "semantic_group",
            "required_for_mbp10",
            "required_for_mbo",
            "accepted_aliases",
        ]
    ].to_dict(orient="records")
    contract_hash = _sha256_text(json.dumps(fields_for_hash, sort_keys=True, ensure_ascii=False))
    contract["contract_hash"] = contract_hash
    return contract


def _required_fields(schema_request: str, contract: pd.DataFrame) -> list[str]:
    schema = schema_request if schema_request in {MBP10, MBO} else MBP10
    required_column = "required_for_mbo" if schema == MBO else "required_for_mbp10"
    return contract.loc[contract[required_column].eq(1), "canonical_field"].tolist()


def _schema_status(requests: pd.DataFrame, contract: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in requests.iterrows():
        schema = _clean(row.get("required_schema_request"))
        required = _required_fields(schema, contract)
        rows.append(
            {
                "request_id": row["request_id"],
                "batch_id": row["batch_id"],
                "wave_id": row["wave_id"],
                "required_schema_request": schema,
                "schema_contract_mapped": int(schema in {MBP10, MBO}),
                "required_canonical_field_count": len(required),
                "exchange": row["exchange"],
                "product": row["product"],
                "vt_symbol": row["vt_symbol"],
                "trading_day": row["trading_day"],
                "request_start": row["request_start"],
                "request_end": row["request_end"],
                "right_tail_window_count": int(row.get("right_tail_window_count", 0)),
                "bottom_loss_window_count": int(row.get("bottom_loss_window_count", 0)),
                "maxdd_context_window_count": int(row.get("maxdd_context_window_count", 0)),
                "strategy_use_allowed_now": 0,
                "rule_preflight_allowed_now": 0,
            }
        )
    return pd.DataFrame(rows)


def _parquet_fields(path_text: str, manifest_dir: Path) -> tuple[set[str], str, int, str]:
    text = _clean(path_text)
    if not text:
        return set(), "", 0, "normalized_parquet_file_missing"
    path = Path(text).expanduser()
    if not path.is_absolute():
        path = (manifest_dir / path).resolve()
    if not path.exists():
        return set(), "", 0, "normalized_parquet_file_not_found"
    try:
        import pyarrow.parquet as pq

        metadata = pq.read_metadata(path)
        fields = set(str(name) for name in metadata.schema.names)
        return fields, ";".join(sorted(fields)), int(metadata.num_rows), ""
    except Exception as exc:  # pragma: no cover - depends on delivered parquet backend.
        return set(), "", 0, type(exc).__name__


def _field_satisfied(canonical_field: str, fields: set[str], aliases: str) -> bool:
    fields_lower = {field.lower() for field in fields}
    alias_set = {alias.strip().lower() for alias in aliases.split(",") if alias.strip()}
    if canonical_field.lower() in fields_lower:
        return True
    if fields_lower.intersection(alias_set):
        return True
    return False


def _audit_manifest_schema(manifest: pd.DataFrame, manifest_label: str, contract: pd.DataFrame, manifest_path: Path) -> pd.DataFrame:
    rows = []
    manifest_dir = manifest_path.parent
    for _, row in manifest.iterrows():
        schema_request = _clean(row.get("required_schema_request"))
        schema_delivered = _clean(row.get("schema_delivered")) or schema_request
        required_fields = _required_fields(schema_request, contract)
        parquet_fields, field_text, row_count, parquet_error = _parquet_fields(row.get("normalized_parquet_file", ""), manifest_dir)
        missing = []
        matched = []
        for field in required_fields:
            contract_row = contract.loc[contract["canonical_field"].eq(field)].iloc[0]
            if _field_satisfied(field, parquet_fields, str(contract_row["accepted_aliases"])):
                matched.append(field)
            else:
                missing.append(field)
        synthetic_like = int(
            _clean(row.get("vendor")).startswith("synthetic")
            or "synthetic" in _clean(row.get("dataset"))
            or "synthetic" in _clean(row.get("notes"))
        )
        schema_structural_pass = int(not parquet_error and len(missing) == 0 and len(required_fields) > 0)
        real_schema_contract_accept_now = int(schema_structural_pass and not synthetic_like)
        rows.append(
            {
                "manifest_label": manifest_label,
                "request_id": _clean(row.get("request_id")),
                "required_schema_request": schema_request,
                "schema_delivered": schema_delivered,
                "vendor": _clean(row.get("vendor")),
                "dataset": _clean(row.get("dataset")),
                "vt_symbol": _clean(row.get("vt_symbol")),
                "trading_day": _clean(row.get("trading_day")),
                "normalized_parquet_file": _clean(row.get("normalized_parquet_file")),
                "parquet_error": parquet_error,
                "parquet_row_count": row_count,
                "parquet_schema_fields": field_text,
                "required_field_count": len(required_fields),
                "matched_field_count": len(matched),
                "missing_field_count": len(missing),
                "missing_fields": ";".join(missing),
                "schema_structural_pass": schema_structural_pass,
                "synthetic_like": synthetic_like,
                "real_schema_contract_accept_now": real_schema_contract_accept_now,
                "strategy_use_allowed_now": 0,
                "rule_preflight_allowed_now": 0,
            }
        )
    return pd.DataFrame(rows)


def _build_gates(request_schema: pd.DataFrame, manifest_audit: pd.DataFrame, contract: pd.DataFrame) -> pd.DataFrame:
    request_count = len(request_schema)
    mapped_count = int(request_schema["schema_contract_mapped"].sum())
    real_audit = manifest_audit[manifest_audit["synthetic_like"].eq(0)]
    synthetic_audit = manifest_audit[manifest_audit["synthetic_like"].eq(1)]
    mbp_contract = contract[contract["required_for_mbp10"].eq(1)]
    mbo_contract = contract[contract["required_for_mbo"].eq(1)]
    universal_fields = {"ts_event", "ts_recv", "sequence"}
    universal_defined = universal_fields.issubset(set(contract["canonical_field"]))
    synthetic_blocked = int(
        len(synthetic_audit) == 0
        or (
            synthetic_audit["real_schema_contract_accept_now"].sum() == 0
            and synthetic_audit["synthetic_like"].sum() == len(synthetic_audit)
        )
    )
    real_pass_count = int(real_audit["schema_structural_pass"].sum()) if not real_audit.empty else 0
    real_manifest_file_count = (
        int(real_audit["normalized_parquet_file"].astype(str).str.strip().ne("").sum())
        if not real_audit.empty
        else 0
    )
    gates = [
        {
            "gate_id": "w0_request_schema_mapped",
            "observed": f"{mapped_count}/{request_count}",
            "required": f"{request_count}/{request_count}",
            "pass_now": int(mapped_count == request_count and request_count > 0),
            "severity": "planning_hard",
        },
        {
            "gate_id": "universal_time_sequence_contract_defined",
            "observed": ";".join(sorted(set(contract["canonical_field"]).intersection(universal_fields))),
            "required": "ts_event;ts_recv;sequence",
            "pass_now": int(universal_defined),
            "severity": "planning_hard",
        },
        {
            "gate_id": "mbp10_top10_ladder_contract_defined",
            "observed": str(len(mbp_contract)),
            "required": "43 hard fields: time/sequence + 10 bid/ask price/size levels",
            "pass_now": int(len(mbp_contract) == 43),
            "severity": "planning_hard",
        },
        {
            "gate_id": "mbo_l3_order_event_contract_defined",
            "observed": str(len(mbo_contract)),
            "required": "8 hard fields: time/sequence + action/side/price/size/order_id",
            "pass_now": int(len(mbo_contract) == 8),
            "severity": "planning_hard",
        },
        {
            "gate_id": "synthetic_fixture_blocked_from_real_contract",
            "observed": f"synthetic_rows={len(synthetic_audit)} accept_now={int(synthetic_audit['real_schema_contract_accept_now'].sum()) if len(synthetic_audit) else 0}",
            "required": "all synthetic rows accept_now=0",
            "pass_now": synthetic_blocked,
            "severity": "anti_selection_hard",
        },
        {
            "gate_id": "strategy_locks_zero",
            "observed": "strategy_use_allowed_now=0; rule_preflight_allowed_now=0",
            "required": "0",
            "pass_now": 1,
            "severity": "anti_selection_hard",
        },
        {
            "gate_id": "real_w0_manifest_delivered",
            "observed": f"{real_manifest_file_count}/{request_count}",
            "required": f"{request_count}/{request_count}",
            "pass_now": int(real_manifest_file_count == request_count and request_count > 0),
            "severity": "data_hard",
        },
        {
            "gate_id": "real_w0_schema_contract_pass",
            "observed": f"{real_pass_count}/{request_count}",
            "required": f"{request_count}/{request_count}",
            "pass_now": int(real_pass_count == request_count and request_count > 0),
            "severity": "data_hard",
        },
    ]
    return pd.DataFrame(gates)


def _plot_official_path(curve: pd.DataFrame, request_schema: pd.DataFrame) -> None:
    colors = {MBP10: "#0F766E", MBO: "#7C2D12"}
    fig, axes = plt.subplots(3, 1, figsize=(16, 10), sharex=True)
    axes[0].plot(curve["date"], curve["account_equity"] / 1_000_000, color="#202939", linewidth=1.1)
    axes[1].plot(curve["date"], curve["drawdown_pct"], color="#DC2626", linewidth=1.0)
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#0369A1", linewidth=1.0)
    axes[2].axhline(100, color="#B91C1C", linestyle="--", linewidth=0.9)
    for idx, schema in enumerate([MBP10, MBO]):
        rows = request_schema[request_schema["required_schema_request"].eq(schema)]
        points = _nearest_curve_points(curve, rows["trading_day"])
        offset = (idx - 0.5) * 0.35
        axes[0].scatter(points["date"], points["account_equity"] / 1_000_000 + offset, color=colors[schema], s=42, alpha=0.7, label=schema)
        axes[1].scatter(points["date"], points["drawdown_pct"] + offset, color=colors[schema], s=42, alpha=0.7)
        axes[2].scatter(points["date"], points["broker10_margin_to_equity_pct"] + offset, color=colors[schema], s=42, alpha=0.7)
    axes[0].set_ylabel("equity (m)")
    axes[1].set_ylabel("drawdown %")
    axes[2].set_ylabel("broker10 %")
    for ax in axes:
        ax.grid(alpha=0.25)
    axes[0].legend(loc="upper left", fontsize=8)
    fig.suptitle("Stage120 W0 schema contract coverage on official path; real W0 remains missing")
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_contract_matrix(contract: pd.DataFrame) -> None:
    matrix = contract.set_index("canonical_field")[["required_for_mbp10", "required_for_mbo"]]
    fig, ax = plt.subplots(figsize=(9, 14))
    image = ax.imshow(matrix.to_numpy(), aspect="auto", cmap="YlGnBu", vmin=0, vmax=1)
    ax.set_xticks(range(len(matrix.columns)))
    ax.set_xticklabels(["MBP-10 minimum", "MBO L3 preferred"], rotation=20, ha="right")
    ax.set_yticks(range(len(matrix.index)))
    ax.set_yticklabels(matrix.index, fontsize=7)
    for y in range(len(matrix.index)):
        for x in range(len(matrix.columns)):
            if int(matrix.iloc[y, x]):
                ax.text(x, y, "R", ha="center", va="center", color="#F8FAFC", fontsize=7, fontweight="bold")
    ax.set_title("Stage120 canonical field requirement matrix")
    fig.colorbar(image, ax=ax, shrink=0.7)
    fig.tight_layout()
    fig.savefig(CONTRACT_MATRIX_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_request_schema_matrix(request_schema: pd.DataFrame) -> None:
    pivot = request_schema.pivot_table(index="exchange", columns="required_schema_request", values="request_id", aggfunc="count", fill_value=0)
    for column in [MBP10, MBO]:
        if column not in pivot.columns:
            pivot[column] = 0
    pivot = pivot[[MBP10, MBO]].sort_index()
    fig, ax = plt.subplots(figsize=(9, 5.5))
    image = ax.imshow(pivot.to_numpy(), aspect="auto", cmap="PuBuGn")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(["MBP-10 minimum", "MBO L3 preferred"], rotation=20, ha="right")
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    for y in range(len(pivot.index)):
        for x in range(len(pivot.columns)):
            ax.text(x, y, str(int(pivot.iloc[y, x])), ha="center", va="center", color="#111827")
    ax.set_title("Stage120 W0 request schema by exchange")
    fig.colorbar(image, ax=ax, shrink=0.75)
    fig.tight_layout()
    fig.savefig(REQUEST_MATRIX_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_schema_gap(manifest_audit: pd.DataFrame) -> None:
    synthetic = manifest_audit[manifest_audit["synthetic_like"].eq(1)]
    if synthetic.empty:
        chart = pd.DataFrame(
            {
                "required_schema_request": [MBP10, MBO],
                "count": [0, 0],
                "mean": [0.0, 0.0],
                "max": [0.0, 0.0],
            }
        )
    else:
        chart = (
            synthetic.groupby("required_schema_request")["missing_field_count"]
            .agg(["count", "mean", "max"])
            .reindex([MBP10, MBO])
            .fillna(0)
            .reset_index()
        )
    x = np.arange(len(chart))
    fig, ax1 = plt.subplots(figsize=(9, 5))
    ax1.bar(x - 0.18, chart["mean"], width=0.36, color="#B45309", label="mean missing fields")
    ax1.bar(x + 0.18, chart["max"], width=0.36, color="#B91C1C", label="max missing fields")
    ax1.set_xticks(x)
    ax1.set_xticklabels(chart["required_schema_request"], rotation=20, ha="right")
    ax1.set_ylabel("missing canonical fields")
    ax1.grid(axis="y", alpha=0.25)
    ax2 = ax1.twinx()
    ax2.plot(x, chart["count"], color="#0F766E", marker="o", linewidth=1.3, label="request count")
    ax2.set_ylabel("request count")
    ax1.set_title("Stage120 synthetic fixture schema gaps; synthetic is not real W0")
    lines, labels = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines + lines2, labels + labels2, loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(SCHEMA_GAP_CHART_OUT, dpi=160)
    plt.close(fig)


def _write_report(summary: pd.DataFrame, contract: pd.DataFrame, request_schema: pd.DataFrame, manifest_audit: pd.DataFrame, gates: pd.DataFrame) -> None:
    row = summary.iloc[0]
    request_agg = request_schema.groupby("required_schema_request").size().reset_index(name="request_count")
    audit_agg = (
        manifest_audit.groupby(["manifest_label", "required_schema_request"])
        .agg(
            request_count=("request_id", "count"),
            schema_structural_pass=("schema_structural_pass", "sum"),
            mean_missing_fields=("missing_field_count", "mean"),
            max_missing_fields=("missing_field_count", "max"),
            real_schema_contract_accept_now=("real_schema_contract_accept_now", "sum"),
        )
        .reset_index()
    )
    report = f"""# Stage120 W0 schema contract audit

## Decision

- decision: `{row['decision']}`
- nature: schema contract and visual audit only; no strategy rule, no true engine, no A/B, no CTP connection, no order API, no external download.
- contract hash: `{row['contract_hash']}`

## Baseline Path

- end equity: `{row['end_equity']:,.2f}`
- total return: `{row['total_return_pct']:.4f}%`
- max drawdown: `{row['max_drawdown_pct']:.4f}%`
- Sharpe: `{row['sharpe']:.4f}`
- total slippage: `{row['total_slippage']:,.0f}`
- total trade count: `{row['total_trade_count']:,.0f}`
- closed lot win rate: `{row['closed_lot_win_rate_pct']:.4f}%`

## Request Schema Summary

{_md_table(request_agg)}

## Contract Summary

{_md_table(contract.groupby('semantic_group').agg(field_count=('canonical_field', 'count'), mbp10_required=('required_for_mbp10', 'sum'), mbo_required=('required_for_mbo', 'sum')).reset_index())}

## Manifest Schema Audit

{_md_table(audit_agg)}

## Gate Status

{_md_table(gates)}

## Visual Outputs

- official path schema status: `{PATH_CHART_OUT}`
- canonical field matrix: `{CONTRACT_MATRIX_CHART_OUT}`
- request schema exchange matrix: `{REQUEST_MATRIX_CHART_OUT}`
- synthetic schema gap chart: `{SCHEMA_GAP_CHART_OUT}`

## Judgment

Stage120 fixes the W0 schema contract before real data arrives. Synthetic fixtures remain blocked from real schema acceptance and strategy research. Real W0 remains missing, so Stage112/113 and any rule preflight are still not allowed.
"""
    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUT.write_text(report, encoding="utf-8")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit a W0 delivery manifest against the Stage120 canonical microstructure schema contract."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Optional manifest CSV to audit. If omitted, Stage116 empty template is audited.",
    )
    parser.add_argument(
        "--manifest-label",
        default=None,
        help="Label for --manifest rows in outputs. Defaults to cli_manifest or stage116_empty_template.",
    )
    parser.add_argument(
        "--skip-synthetic-selftest",
        action="store_true",
        help="Skip the Stage119 synthetic fixture audit. Real manifests should normally keep the synthetic selftest enabled.",
    )
    return parser.parse_args()


def main(manifest_path: Path | None = None, manifest_label: str | None = None, include_synthetic_selftest: bool = True) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    requests = _read_csv(STAGE116_REQUEST_PACKET_IN)
    stage116_summary = _read_csv(STAGE116_SUMMARY_IN)
    if requests.empty:
        raise RuntimeError("missing Stage116 W0 request packet")
    manifest_specs: list[tuple[str, Path]] = []
    if manifest_path is None:
        manifest_specs.append(("stage116_empty_template", STAGE116_MANIFEST_TEMPLATE_IN))
    else:
        manifest_specs.append((manifest_label or "cli_manifest", manifest_path))
    if include_synthetic_selftest:
        manifest_specs.append(("stage119_synthetic_fixture", STAGE119_SYNTHETIC_MANIFEST_IN))

    manifests: list[tuple[str, Path, pd.DataFrame]] = []
    for label, path in manifest_specs:
        manifest = _read_csv(path)
        if manifest.empty:
            raise RuntimeError(f"manifest is empty or missing: {path}")
        manifests.append((label, path, manifest))

    for frame in [requests, *[manifest for _, _, manifest in manifests]]:
        for column in ["trading_day", "request_start", "request_end"]:
            if column in frame.columns:
                frame[column] = pd.to_datetime(frame[column], errors="coerce")

    contract = _build_contract()
    request_schema = _schema_status(requests, contract)
    manifest_audit = pd.concat(
        [
            _audit_manifest_schema(manifest, label, contract, path)
            for label, path, manifest in manifests
        ],
        ignore_index=True,
    )
    gates = _build_gates(request_schema, manifest_audit, contract)

    base = stage116_summary.iloc[0] if not stage116_summary.empty else pd.Series(dtype=object)
    contract_hash = str(contract["contract_hash"].iloc[0])
    request_count = int(len(request_schema))
    mbp10_request_count = int(request_schema["required_schema_request"].eq(MBP10).sum())
    mbo_request_count = int(request_schema["required_schema_request"].eq(MBO).sum())
    synthetic_structural_pass = int(manifest_audit.loc[manifest_audit["synthetic_like"].eq(1), "schema_structural_pass"].sum())
    real_structural_pass = int(manifest_audit.loc[manifest_audit["synthetic_like"].eq(0), "schema_structural_pass"].sum())
    real_accept_count = int(manifest_audit.loc[manifest_audit["synthetic_like"].eq(0), "real_schema_contract_accept_now"].sum())
    real_manifest_file_count = int(
        manifest_audit.loc[manifest_audit["synthetic_like"].eq(0), "normalized_parquet_file"].astype(str).str.strip().ne("").sum()
    )
    real_schema_contract_pass = int(real_accept_count == request_count and request_count > 0)
    decision_text = PASS_DECISION if real_schema_contract_pass else DECISION
    summary = pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "decision": decision_text,
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "request_count": request_count,
                "mbp10_minimum_request_count": mbp10_request_count,
                "mbo_preferred_request_count": mbo_request_count,
                "contract_field_count": int(len(contract)),
                "mbp10_hard_field_count": int(contract["required_for_mbp10"].sum()),
                "mbo_hard_field_count": int(contract["required_for_mbo"].sum()),
                "contract_hash": contract_hash,
                "planning_gate_pass_count": int(gates[gates["severity"].eq("planning_hard")]["pass_now"].sum()),
                "planning_gate_count": int(gates["severity"].eq("planning_hard").sum()),
                "data_hard_gate_pass_count": int(gates[gates["severity"].eq("data_hard")]["pass_now"].sum()),
                "data_hard_gate_count": int(gates["severity"].eq("data_hard").sum()),
                "synthetic_schema_structural_pass_count": synthetic_structural_pass,
                "real_w0_schema_structural_pass_count": real_structural_pass,
                "real_w0_data_delivered": int(real_manifest_file_count == request_count and request_count > 0),
                "real_w0_schema_contract_pass": real_schema_contract_pass,
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
    _write_csv(contract, CONTRACT_OUT)
    _write_csv(request_schema, REQUEST_SCHEMA_OUT)
    _write_csv(manifest_audit, MANIFEST_AUDIT_OUT)
    _write_csv(gates, GATE_STATUS_OUT)

    curve = _load_curve()
    _plot_official_path(curve, request_schema)
    _plot_contract_matrix(contract)
    _plot_request_schema_matrix(request_schema)
    _plot_schema_gap(manifest_audit)
    _write_report(summary, contract, request_schema, manifest_audit, gates)

    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "decision": decision_text,
        "summary_path": SUMMARY_OUT,
        "contract_path": CONTRACT_OUT,
        "request_schema_status_path": REQUEST_SCHEMA_OUT,
        "manifest_audit_path": MANIFEST_AUDIT_OUT,
        "gate_status_path": GATE_STATUS_OUT,
        "report_path": REPORT_OUT,
        "charts": [
            PATH_CHART_OUT,
            CONTRACT_MATRIX_CHART_OUT,
            REQUEST_MATRIX_CHART_OUT,
            SCHEMA_GAP_CHART_OUT,
        ],
        "contract_hash": contract_hash,
        "real_w0_data_delivered": int(real_manifest_file_count == request_count and request_count > 0),
        "real_w0_schema_contract_pass": real_schema_contract_pass,
        "real_stage112_intake_allowed_now": 0,
        "true_engine_allowed": 0,
        "strategy_feature_usable": 0,
        "order_api_called": 0,
        "ctp_connected": 0,
    }
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(_json_safe(decision), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    args = _parse_args()
    main(
        manifest_path=args.manifest,
        manifest_label=args.manifest_label,
        include_synthetic_selftest=not args.skip_synthetic_selftest,
    )
