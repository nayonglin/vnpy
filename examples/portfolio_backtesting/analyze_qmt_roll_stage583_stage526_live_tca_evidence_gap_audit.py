from __future__ import annotations

from datetime import datetime
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
MODEL_TAG = "stage583_stage526_live_tca_evidence_gap_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage583_stage526_live_tca_evidence_gap_audit"

STAGE575_TAG = "stage575_stage526_live_execution_p0_watchlist_v1"
STAGE575_PREFIX = "qmt_roll_stage575_stage526_live_execution_p0_watchlist"
STAGE575_WATCHLIST = OUTPUT_DIR / f"{STAGE575_PREFIX}_watchlist_{STAGE575_TAG}.csv"
STAGE575_TEMPLATE = OUTPUT_DIR / f"{STAGE575_PREFIX}_live_p0_evidence_template_{STAGE575_TAG}.csv"
STAGE568_TEMPLATE = OUTPUT_DIR / (
    "qmt_roll_stage568_stage526_execution_quality_ledger_audit_"
    "live_execution_ledger_template_stage568_stage526_execution_quality_ledger_audit_v1.csv"
)

EVIDENCE_INVENTORY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_evidence_inventory_{MODEL_TAG}.csv"
P0_CLOSE_GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_p0_close_gates_{MODEL_TAG}.csv"
FIELD_COMPLETENESS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_field_completeness_{MODEL_TAG}.csv"
GATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

REQUIRED_VALID_SAMPLES_PER_P0 = 3
MAX_VWAP_COST_BPS = 50.0
MAX_IMPLEMENTATION_SHORTFALL_BPS = 75.0
MAX_PARTICIPATION_PCT = 25.0

REQUIRED_EVIDENCE_FIELDS = [
    "signal_generated_at",
    "signal_price",
    "order_submit_at",
    "order_submit_price",
    "order_type",
    "fill_first_at",
    "fill_last_at",
    "avg_fill_price",
    "filled_volume",
    "unfilled_volume",
    "actual_implementation_shortfall_bps",
    "actual_vs_window_vwap_bps",
]

OPTIONAL_STRONG_FIELDS = [
    "cancelled_volume",
    "commission_cash",
    "actual_slippage_cash",
    "account_equity_before",
    "broker_margin_before",
    "broker_reject_or_filter",
    "actual_participation_pct",
    "independent_full_day_minute_source",
]

REFERENCE_LINKS = [
    "CME Transaction Cost Analysis for Futures: https://www.cmegroup.com/education/files/TCA-4.pdf",
    "tcapy open-source TCA library: https://github.com/cuemacro/tcapy",
    "Optimality of VWAP Execution Strategies under General Shaped Market Impact Functions: https://arxiv.org/abs/1605.03683",
    "Execution and block trade pricing with optimal constant rate of participation: https://arxiv.org/abs/1210.7608",
]


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


def _num(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(default).astype(float)


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
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _md_table(frame: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 20) -> str:
    if frame.empty:
        return "_empty_"
    view = frame.copy()
    if columns is not None:
        view = view[[col for col in columns if col in view.columns]]
    if len(view) > max_rows:
        view = view.head(max_rows)
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda item: f"{item:.4f}" if pd.notna(item) else "")
    return view.to_markdown(index=False)


def _present(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(False, index=frame.index)
    series = frame[column]
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce").notna()
    return series.fillna("").astype(str).str.strip().ne("")


def _matching_files() -> list[Path]:
    keys = ("live", "evidence", "execution", "fill", "ledger", "shadow", "simnow", "ctp")
    paths: list[Path] = []
    for path in OUTPUT_DIR.glob("*.csv"):
        lower = path.name.lower()
        if any(key in lower for key in keys):
            paths.append(path)
    return sorted(set(paths))


def load_p0_watchlist() -> pd.DataFrame:
    watch = _read_csv(STAGE575_WATCHLIST)
    p0 = watch[watch["watch_priority"].fillna("").astype(str).str.startswith("P0")].copy()
    p0["event_id"] = _num(p0, "event_id").astype(int)
    p0["order_volume"] = _num(p0, "order_volume")
    p0["target_close_window_volume"] = _num(p0, "target_close_window_volume")
    p0["required_valid_samples"] = REQUIRED_VALID_SAMPLES_PER_P0
    return p0.sort_values(["risk_score", "date"], ascending=[False, True]).reset_index(drop=True)


def _match_p0_rows(frame: pd.DataFrame, p0: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    out = frame.copy()
    if "event_id" in out.columns:
        out["event_id"] = pd.to_numeric(out["event_id"], errors="coerce")
        matched = out[out["event_id"].isin(p0["event_id"].astype(float).tolist())].copy()
        if not matched.empty:
            return matched
    if {"date", "vt_symbol"}.issubset(out.columns):
        keys = p0[["date", "vt_symbol"]].astype(str).drop_duplicates()
        out["_date_key"] = out["date"].astype(str).str.slice(0, 10)
        out["_vt_key"] = out["vt_symbol"].astype(str)
        key_set = set((row["date"], row["vt_symbol"]) for _, row in keys.iterrows())
        matched = out[out.apply(lambda row: (str(row["_date_key"]), str(row["_vt_key"])) in key_set, axis=1)].copy()
        matched = matched.drop(columns=[col for col in ["_date_key", "_vt_key"] if col in matched.columns])
        return matched
    return out.iloc[0:0].copy()


def _participation_pct(row: pd.Series, p0_row: pd.Series) -> float | None:
    if "actual_participation_pct" in row.index:
        value = pd.to_numeric(pd.Series([row.get("actual_participation_pct")]), errors="coerce").iloc[0]
        if pd.notna(value):
            return float(value)
    target_volume = float(p0_row.get("target_close_window_volume", 0.0) or 0.0)
    filled = pd.to_numeric(pd.Series([row.get("filled_volume")]), errors="coerce").iloc[0]
    if pd.notna(filled) and target_volume > 0.0:
        return float(filled) / target_volume * 100.0
    return None


def _reject_ok(row: pd.Series) -> bool | None:
    if "broker_reject_or_filter" not in row.index:
        return None
    text = str(row.get("broker_reject_or_filter", "")).strip().lower()
    if text in {"", "0", "false", "none", "no", "n"}:
        return True
    return False


def _valid_sample(row: pd.Series, p0_row: pd.Series) -> tuple[bool, list[str], dict[str, Any]]:
    blockers: list[str] = []
    metrics: dict[str, Any] = {}
    for field in REQUIRED_EVIDENCE_FIELDS:
        if field not in row.index or pd.isna(row.get(field)) or str(row.get(field)).strip() == "":
            blockers.append(f"missing_{field}")

    order_volume = float(p0_row.get("order_volume", 0.0) or 0.0)
    filled = pd.to_numeric(pd.Series([row.get("filled_volume")]), errors="coerce").iloc[0]
    unfilled = pd.to_numeric(pd.Series([row.get("unfilled_volume")]), errors="coerce").iloc[0]
    avg_fill = pd.to_numeric(pd.Series([row.get("avg_fill_price")]), errors="coerce").iloc[0]
    vwap_bps = pd.to_numeric(pd.Series([row.get("actual_vs_window_vwap_bps")]), errors="coerce").iloc[0]
    is_bps = pd.to_numeric(pd.Series([row.get("actual_implementation_shortfall_bps")]), errors="coerce").iloc[0]

    if not pd.notna(avg_fill) or float(avg_fill) <= 0.0:
        blockers.append("avg_fill_price_not_positive")
    if not pd.notna(filled) or float(filled) <= 0.0:
        blockers.append("filled_volume_not_positive")
    elif order_volume > 0.0 and float(filled) < order_volume:
        blockers.append("filled_less_than_order_volume")
    if not pd.notna(unfilled) or float(unfilled) != 0.0:
        blockers.append("unfilled_volume_not_zero")
    if not pd.notna(vwap_bps) or float(vwap_bps) > MAX_VWAP_COST_BPS:
        blockers.append("actual_vs_window_vwap_bps_missing_or_gt50")
    if not pd.notna(is_bps) or float(is_bps) > MAX_IMPLEMENTATION_SHORTFALL_BPS:
        blockers.append("actual_implementation_shortfall_missing_or_gt75")

    participation = _participation_pct(row, p0_row)
    if participation is None or participation > MAX_PARTICIPATION_PCT:
        blockers.append("participation_missing_or_gt25pct")

    reject_ok = _reject_ok(row)
    if reject_ok is None:
        blockers.append("broker_reject_or_filter_unproven")
    elif not reject_ok:
        blockers.append("broker_reject_or_filter_present")

    metrics.update(
        {
            "filled_volume": float(filled) if pd.notna(filled) else None,
            "unfilled_volume": float(unfilled) if pd.notna(unfilled) else None,
            "avg_fill_price": float(avg_fill) if pd.notna(avg_fill) else None,
            "actual_vs_window_vwap_bps": float(vwap_bps) if pd.notna(vwap_bps) else None,
            "actual_implementation_shortfall_bps": float(is_bps) if pd.notna(is_bps) else None,
            "actual_participation_pct": participation,
            "broker_reject_ok": reject_ok,
        }
    )
    return len(blockers) == 0, sorted(set(blockers)), metrics


def build_evidence_inventory(p0: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    inventory_rows: list[dict[str, Any]] = []
    candidate_rows: list[pd.DataFrame] = []
    for path in _matching_files():
        try:
            frame = _read_csv(path)
        except Exception as exc:  # noqa: BLE001 - inventory should continue through bad files.
            inventory_rows.append(
                {
                    "path": str(path),
                    "file_name": path.name,
                    "read_ok": 0,
                    "error": type(exc).__name__,
                    "row_count": 0,
                    "required_field_count": 0,
                    "optional_field_count": 0,
                    "p0_matched_rows": 0,
                    "p0_rows_with_avg_fill": 0,
                    "p0_rows_with_complete_fill": 0,
                    "valid_live_tca_samples": 0,
                }
            )
            continue
        matched = _match_p0_rows(frame, p0)
        required_count = sum(col in frame.columns for col in REQUIRED_EVIDENCE_FIELDS)
        optional_count = sum(col in frame.columns for col in OPTIONAL_STRONG_FIELDS)
        p0_avg_fill = int((_num(matched, "avg_fill_price") > 0).sum()) if not matched.empty else 0
        p0_complete = int(((_num(matched, "filled_volume") > 0) & (_num(matched, "unfilled_volume") == 0)).sum()) if not matched.empty else 0
        valid_count = 0
        if not matched.empty:
            candidate = matched.copy()
            candidate["evidence_source_file"] = path.name
            candidate_rows.append(candidate)
            for _, row in matched.iterrows():
                event_id = int(pd.to_numeric(pd.Series([row.get("event_id")]), errors="coerce").fillna(-1).iloc[0])
                p0_row = p0[p0["event_id"].eq(event_id)]
                if p0_row.empty and "vt_symbol" in row.index and "date" in row.index:
                    p0_row = p0[p0["vt_symbol"].astype(str).eq(str(row.get("vt_symbol"))) & p0["date"].astype(str).eq(str(row.get("date"))[:10])]
                if p0_row.empty:
                    continue
                valid, _, _ = _valid_sample(row, p0_row.iloc[0])
                valid_count += int(valid)
        inventory_rows.append(
            {
                "path": str(path),
                "file_name": path.name,
                "read_ok": 1,
                "error": "",
                "row_count": int(len(frame)),
                "required_field_count": int(required_count),
                "optional_field_count": int(optional_count),
                "p0_matched_rows": int(len(matched)),
                "p0_rows_with_avg_fill": p0_avg_fill,
                "p0_rows_with_complete_fill": p0_complete,
                "valid_live_tca_samples": int(valid_count),
            }
        )
    inventory = pd.DataFrame(inventory_rows).sort_values(
        ["valid_live_tca_samples", "p0_rows_with_complete_fill", "p0_matched_rows", "required_field_count"],
        ascending=[False, False, False, False],
    )
    candidates = pd.concat(candidate_rows, ignore_index=True, sort=False) if candidate_rows else pd.DataFrame()
    return inventory, candidates


def build_p0_close_gates(p0: pd.DataFrame, candidates: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, item in p0.iterrows():
        event_id = int(item["event_id"])
        event_rows = candidates[candidates.get("event_id", pd.Series(dtype=float)).pipe(pd.to_numeric, errors="coerce").eq(event_id)].copy() if not candidates.empty else pd.DataFrame()
        valid_count = 0
        blocker_counts: dict[str, int] = {}
        source_files: set[str] = set()
        best_metrics: dict[str, Any] = {}
        for _, row in event_rows.iterrows():
            source_files.add(str(row.get("evidence_source_file", "")))
            valid, blockers, metrics = _valid_sample(row, item)
            valid_count += int(valid)
            for blocker in blockers:
                blocker_counts[blocker] = blocker_counts.get(blocker, 0) + 1
            if metrics:
                best_metrics = metrics
        remaining = max(REQUIRED_VALID_SAMPLES_PER_P0 - valid_count, 0)
        rows.append(
            {
                "event_id": event_id,
                "date": str(item["date"]),
                "vt_symbol": str(item["vt_symbol"]),
                "watch_priority": str(item["watch_priority"]),
                "risk_types": str(item["risk_types"]),
                "order_volume": float(item["order_volume"]),
                "target_close_window_volume": float(item.get("target_close_window_volume", 0.0)),
                "daily_order_volume_pct": float(item.get("daily_order_volume_pct", 0.0)),
                "matched_evidence_rows": int(len(event_rows)),
                "valid_live_tca_samples": int(valid_count),
                "required_valid_samples": REQUIRED_VALID_SAMPLES_PER_P0,
                "remaining_valid_samples": int(remaining),
                "close_gate_passed": int(remaining == 0),
                "evidence_source_files": ";".join(sorted(file for file in source_files if file)),
                "top_blockers": ";".join(f"{key}:{value}" for key, value in sorted(blocker_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:8]),
                "latest_avg_fill_price": best_metrics.get("avg_fill_price"),
                "latest_vwap_bps": best_metrics.get("actual_vs_window_vwap_bps"),
                "latest_implementation_shortfall_bps": best_metrics.get("actual_implementation_shortfall_bps"),
                "latest_participation_pct": best_metrics.get("actual_participation_pct"),
            }
        )
    return pd.DataFrame(rows).sort_values(["close_gate_passed", "remaining_valid_samples", "event_id"], ascending=[True, False, True])


def build_field_completeness(p0: pd.DataFrame, candidates: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    fields = REQUIRED_EVIDENCE_FIELDS + OPTIONAL_STRONG_FIELDS
    for _, item in p0.iterrows():
        event_id = int(item["event_id"])
        event_rows = candidates[candidates.get("event_id", pd.Series(dtype=float)).pipe(pd.to_numeric, errors="coerce").eq(event_id)].copy() if not candidates.empty else pd.DataFrame()
        row: dict[str, Any] = {
            "event_id": event_id,
            "vt_symbol": str(item["vt_symbol"]),
            "matched_evidence_rows": int(len(event_rows)),
        }
        for field in fields:
            row[field] = int(_present(event_rows, field).any()) if not event_rows.empty else 0
        rows.append(row)
    return pd.DataFrame(rows)


def build_gates(p0: pd.DataFrame, inventory: pd.DataFrame, p0_close: pd.DataFrame, field_complete: pd.DataFrame) -> pd.DataFrame:
    p0_valid_sum = int(p0_close["valid_live_tca_samples"].sum()) if not p0_close.empty else 0
    required_sum = int(p0_close["required_valid_samples"].sum()) if not p0_close.empty else 0
    complete_p0 = int(p0_close["close_gate_passed"].sum()) if not p0_close.empty else 0
    required_field_rate = 0.0
    if not field_complete.empty:
        required_field_values = field_complete[REQUIRED_EVIDENCE_FIELDS].to_numpy(dtype=float)
        required_field_rate = float(required_field_values.mean()) if required_field_values.size else 0.0
    candidate_files = int((inventory["p0_matched_rows"] > 0).sum()) if not inventory.empty else 0
    rows = [
        {
            "gate": "p0_watchlist_loaded",
            "passed": int(len(p0) == 3),
            "actual": f"{len(p0)} P0 events",
            "required": "3 P0 residual execution events",
            "severity": "hard",
            "judgement": "Stage575 P0 watchlist is available.",
        },
        {
            "gate": "evidence_files_scanned",
            "passed": int(len(inventory) > 0),
            "actual": f"{len(inventory)} files scanned, {candidate_files} with P0 rows",
            "required": "scan live/evidence/execution/fill/ledger candidates",
            "severity": "hard",
            "judgement": "Evidence inventory exists, but file presence is not proof of fills.",
        },
        {
            "gate": "required_actual_fields_present_somewhere",
            "passed": int(required_field_rate > 0.0),
            "actual": f"{required_field_rate:.2%} P0 required field event coverage",
            "required": "field coverage across P0 evidence rows",
            "severity": "hard",
            "judgement": "Templates contain fields; actual values still matter.",
        },
        {
            "gate": "valid_live_tca_samples_complete",
            "passed": int(p0_valid_sum >= required_sum and required_sum > 0),
            "actual": f"{p0_valid_sum}/{required_sum} valid P0 samples",
            "required": f"{REQUIRED_VALID_SAMPLES_PER_P0} valid samples per P0",
            "severity": "hard",
            "judgement": "Real fill evidence is not complete.",
        },
        {
            "gate": "all_p0_close_gates_passed",
            "passed": int(complete_p0 == len(p0) and len(p0) > 0),
            "actual": f"{complete_p0}/{len(p0)} P0 close gates",
            "required": "all P0 events closed",
            "severity": "hard",
            "judgement": "Each P0 class needs comparable live or independent evidence.",
        },
        {
            "gate": "stage526_zero_execution_bias_claim_allowed",
            "passed": 0,
            "actual": "not allowed",
            "required": "all P0 close gates pass and no broker reject/filter",
            "severity": "hard",
            "judgement": "Stage526 cannot claim zero live execution bias yet.",
        },
    ]
    return pd.DataFrame(rows)


def write_chart(p0_close: pd.DataFrame, field_complete: pd.DataFrame, inventory: pd.DataFrame, gates: pd.DataFrame) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(2, 2, figsize=(16, 11))
    fig.suptitle("Stage583 Stage526 live TCA evidence gap", fontsize=15, fontweight="bold")

    ax = axes[0, 0]
    labels = p0_close["vt_symbol"].astype(str)
    ax.bar(labels, p0_close["valid_live_tca_samples"], color="#2f9e44", label="valid samples")
    ax.bar(labels, p0_close["remaining_valid_samples"], bottom=p0_close["valid_live_tca_samples"], color="#e03131", label="remaining")
    ax.axhline(REQUIRED_VALID_SAMPLES_PER_P0, color="#111827", linestyle="--", linewidth=1)
    ax.set_title("P0 evidence samples vs required")
    ax.set_ylabel("sample count")
    ax.tick_params(axis="x", rotation=20)
    ax.legend(fontsize=8)

    ax = axes[0, 1]
    fields = REQUIRED_EVIDENCE_FIELDS
    if not field_complete.empty:
        matrix = field_complete.set_index("vt_symbol")[fields].astype(float)
        im = ax.imshow(matrix.values, vmin=0, vmax=1, cmap="RdYlGn")
        ax.set_xticks(range(len(fields)))
        ax.set_xticklabels(fields, rotation=65, ha="right", fontsize=7)
        ax.set_yticks(range(len(matrix.index)))
        ax.set_yticklabels(matrix.index)
        for i in range(matrix.shape[0]):
            for j in range(matrix.shape[1]):
                ax.text(j, i, int(matrix.iloc[i, j]), ha="center", va="center", fontsize=8)
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    ax.set_title("Required TCA field value coverage")

    ax = axes[1, 0]
    top_inventory = inventory.head(10).copy()
    y = np.arange(len(top_inventory))
    ax.barh(y, top_inventory["p0_matched_rows"], color="#4dabf7", label="P0 matched rows")
    ax.barh(y, top_inventory["valid_live_tca_samples"], color="#2f9e44", label="valid live samples")
    ax.set_yticks(y)
    ax.set_yticklabels(top_inventory["file_name"], fontsize=7)
    ax.invert_yaxis()
    ax.set_title("Evidence inventory top files")
    ax.legend(fontsize=8)

    ax = axes[1, 1]
    gate_colors = np.where(gates["passed"].astype(int).eq(1), "#2f9e44", "#e03131")
    ax.barh(gates["gate"], np.ones(len(gates)), color=gate_colors)
    ax.set_xlim(0, 1)
    ax.set_xticks([])
    for idx, row in gates.iterrows():
        ax.text(0.03, idx, row["actual"], va="center", fontsize=8, color="white" if int(row["passed"]) else "black")
    ax.set_title(f"Evidence gates pass {int(gates['passed'].sum())}/{len(gates)}")

    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def write_report(
    p0: pd.DataFrame,
    inventory: pd.DataFrame,
    p0_close: pd.DataFrame,
    field_complete: pd.DataFrame,
    gates: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    text = f"""# Stage583 Stage526 live TCA evidence gap audit

Generated: {decision["generated_at_cst"]} CST

## Decision

- decision: `{decision["decision"]}`
- gate: `{decision["gate_pass_count"]}/{decision["gate_count"]}`
- valid live TCA samples: `{decision["valid_live_tca_samples"]}/{decision["required_live_tca_samples"]}`
- P0 events closed: `{decision["p0_close_pass_count"]}/{decision["p0_count"]}`

## Research judgement

本阶段不改策略、不新增交易版本、不做收益回测。它只扫描已有 `live/evidence/execution/fill/ledger` 候选文件，并按 Stage277 的 P0 close condition 计算真实 TCA 证据缺口。

外部调研支持这个处理方式：TCA 应该把 order/fill 与行情合并，至少同时看 arrival price / VWAP / implementation shortfall / participation，而不是只用回测假定滑点。

参考：

""" + "\n".join(f"- {link}" for link in REFERENCE_LINKS) + f"""

## P0 close gates

{_md_table(p0_close, [
    "event_id",
    "date",
    "vt_symbol",
    "watch_priority",
    "matched_evidence_rows",
    "valid_live_tca_samples",
    "required_valid_samples",
    "remaining_valid_samples",
    "close_gate_passed",
    "top_blockers",
], 20)}

## Evidence inventory

{_md_table(inventory, [
    "file_name",
    "row_count",
    "required_field_count",
    "optional_field_count",
    "p0_matched_rows",
    "p0_rows_with_avg_fill",
    "p0_rows_with_complete_fill",
    "valid_live_tca_samples",
], 20)}

## Field completeness

{_md_table(field_complete, max_rows=20)}

## Gates

{_md_table(gates, max_rows=20)}

## Visual review

- 左上：三个 P0 的有效 TCA 样本都是 `0/3`，红色剩余样本柱没有缩短，说明 live 证据没有实质进展。
- 右上：模板字段虽然存在，但 P0 required field value coverage 几乎全红，证明“模板存在”不等于“成交证据存在”。
- 左下：库存里能匹配 P0 的主要是 Stage568/575 模板/代理文件，valid live samples 仍为 `0`；没有发现能直接关账的真实 fill 文件。
- 右下：闸门只通过 watchlist 与 inventory 扫描类项目，所有真实成交关账项失败。

## Conclusion

Stage526 仍不能声明“真实交易不存在偏差”。当前正确表述是：正常成本下 Stage526 是主候选，但 P0 live TCA evidence gap 未关账；需要对 `fu2509/lc2505/AP505` 分别累计 `3` 个可比真实 fill 或独立全日分钟证据，且满足 filled=100%、unfilled=0、VWAP cost <=50bps、implementation shortfall <=75bps、participation <=25%、无券商拒单/过滤。
"""
    REPORT_PATH.write_text(text, encoding="utf-8")


def main() -> None:
    p0 = load_p0_watchlist()
    inventory, candidates = build_evidence_inventory(p0)
    p0_close = build_p0_close_gates(p0, candidates)
    field_complete = build_field_completeness(p0, candidates)
    gates = build_gates(p0, inventory, p0_close, field_complete)

    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at_cst": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": "live_tca_evidence_gap_not_closed",
        "p0_count": int(len(p0)),
        "p0_symbols": p0["vt_symbol"].astype(str).tolist(),
        "gate_pass_count": int(gates["passed"].sum()),
        "gate_count": int(len(gates)),
        "valid_live_tca_samples": int(p0_close["valid_live_tca_samples"].sum()),
        "required_live_tca_samples": int(p0_close["required_valid_samples"].sum()),
        "p0_close_pass_count": int(p0_close["close_gate_passed"].sum()),
        "evidence_files_scanned": int(len(inventory)),
        "evidence_files_with_p0_rows": int((inventory["p0_matched_rows"] > 0).sum()) if not inventory.empty else 0,
        "strategy_changed": False,
        "backtest_rerun": False,
        "promotion_allowed": False,
        "zero_execution_bias_claim_allowed": False,
        "overfit_assessment": "not overfit: this is a fixed evidence audit with no strategy or parameter changes",
        "continue_value": "yes: real fill or independent minute evidence is required before claiming live execution has no bias",
        "references": REFERENCE_LINKS,
        "outputs": {
            "evidence_inventory": str(EVIDENCE_INVENTORY_PATH),
            "p0_close_gates": str(P0_CLOSE_GATES_PATH),
            "field_completeness": str(FIELD_COMPLETENESS_PATH),
            "gates": str(GATES_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
            "chart": str(CHART_PATH),
        },
    }

    inventory.to_csv(EVIDENCE_INVENTORY_PATH, index=False, encoding="utf-8-sig")
    p0_close.to_csv(P0_CLOSE_GATES_PATH, index=False, encoding="utf-8-sig")
    field_complete.to_csv(FIELD_COMPLETENESS_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    write_chart(p0_close, field_complete, inventory, gates)
    write_report(p0, inventory, p0_close, field_complete, gates, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
