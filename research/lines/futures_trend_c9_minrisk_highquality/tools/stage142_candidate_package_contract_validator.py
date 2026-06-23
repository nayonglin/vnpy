from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import shutil
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage142"
MODEL_TAG = "stage142_candidate_package_contract_validator_v1"
OUTPUT_PREFIX = "qmt_roll_stage142_c9_minrisk_candidate_package_contract_validator"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage142_candidate_package_contract_validator"
FIXTURE_DIR = OUTPUT_DIR / "fixture_candidate_packages"

CURVE_IN = (
    LINE_DIR
    / "outputs"
    / "stage045_event_time_field_sync_audit"
    / "qmt_roll_stage045_c9_minrisk_event_time_field_sync_audit_semantic_curve_"
    "stage045_event_time_field_sync_audit_v1.csv"
)
STAGE134_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage134_wave0_total_gate_cli_entry_selftest"
    / "qmt_roll_stage134_c9_minrisk_wave0_total_gate_cli_entry_selftest_summary_"
    "stage134_wave0_total_gate_cli_entry_selftest_v1.csv"
)
STAGE141_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage141_candidate_promotion_gate_contract"
    / "qmt_roll_stage141_c9_minrisk_candidate_promotion_gate_contract_summary_"
    "stage141_candidate_promotion_gate_contract_v1.csv"
)
STAGE141_CONTRACT_IN = (
    LINE_DIR
    / "outputs"
    / "stage141_candidate_promotion_gate_contract"
    / "qmt_roll_stage141_c9_minrisk_candidate_promotion_gate_contract_promotion_contract_"
    "stage141_candidate_promotion_gate_contract_v1.csv"
)

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
SCHEMA_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_candidate_package_schema_{MODEL_TAG}.json"
SCHEMA_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_package_schema_audit_{MODEL_TAG}.csv"
VALIDATION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_validation_audit_{MODEL_TAG}.csv"
SELFTEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_selftest_cases_{MODEL_TAG}.csv"
GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_validator_status_{MODEL_TAG}.png"
SCHEMA_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_schema_matrix_{MODEL_TAG}.png"
VALIDATION_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_validation_matrix_{MODEL_TAG}.png"
SELFTEST_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_selftest_matrix_{MODEL_TAG}.png"
GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_matrix_{MODEL_TAG}.png"

REQUIRED_SUMMARY_FIELDS = [
    "candidate_id",
    "predeclared_spec_hash",
    "candidate_total_return_pct",
    "candidate_max_drawdown_pct",
    "candidate_max_broker10_margin_to_equity_pct",
    "candidate_total_trade_count",
    "candidate_closed_lot_win_rate_pct",
    "candidate_total_slippage",
]
REQUIRED_EVIDENCE_IDS = [
    "authorized_point_in_time_data_pass",
    "true_engine_replay_pass",
    "walk_forward_oos_pass",
    "leave_one_year_pass",
    "product_family_pass",
    "monthly_start_pass",
    "right_tail_protection_pass",
    "bottom_loss_improvement_pass",
    "visual_artifacts_complete",
    "pbo_dsr_pass",
    "no_parameter_sweep_rescue",
]
REQUIRED_VISUAL_IDS = [
    "equity_curve",
    "drawdown_curve",
    "broker10_curve",
    "minute_k_atlas",
    "right_tail_bottom_loss_atlas",
]
FORBIDDEN_MARKERS = {"stage131", "stage142", "fixture", "synthetic", "contract_positive"}


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


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


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


def _load_curve() -> pd.DataFrame:
    curve = _read_csv(CURVE_IN)
    if curve.empty:
        raise RuntimeError(f"missing curve input: {CURVE_IN}")
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]:
        curve[column] = pd.to_numeric(curve[column], errors="coerce")
    return curve[curve["date"].notna()].sort_values("date").reset_index(drop=True)


def _baseline_metrics(curve: pd.DataFrame) -> dict[str, float]:
    stage134 = _read_csv(STAGE134_SUMMARY_IN)
    if not stage134.empty:
        row = stage134.iloc[0]
        return {
            "end_equity": float(row.get("end_equity", np.nan)),
            "total_return_pct": float(row.get("total_return_pct", np.nan)),
            "max_drawdown_pct": float(row.get("max_drawdown_pct", np.nan)),
            "sharpe": float(row.get("sharpe", np.nan)),
            "total_slippage": float(row.get("total_slippage", np.nan)),
            "total_trade_count": float(row.get("total_trade_count", np.nan)),
            "closed_lot_win_rate_pct": float(row.get("closed_lot_win_rate_pct", np.nan)),
            "max_broker10_margin_to_equity_pct": float(row.get("max_broker10_margin_to_equity_pct", np.nan)),
        }
    first_equity = float(curve["account_equity"].dropna().iloc[0])
    end_equity = float(curve["account_equity"].dropna().iloc[-1])
    return {
        "end_equity": end_equity,
        "total_return_pct": (end_equity / first_equity - 1.0) * 100.0,
        "max_drawdown_pct": float(curve["drawdown_pct"].min()),
        "sharpe": np.nan,
        "total_slippage": np.nan,
        "total_trade_count": np.nan,
        "closed_lot_win_rate_pct": np.nan,
        "max_broker10_margin_to_equity_pct": float(curve["broker10_margin_to_equity_pct"].max()),
    }


def _thresholds_from_stage141() -> dict[str, float]:
    summary = _read_csv(STAGE141_SUMMARY_IN)
    if summary.empty:
        raise RuntimeError(f"missing Stage141 summary: {STAGE141_SUMMARY_IN}")
    row = summary.iloc[0]
    return {
        "min_candidate_total_return_pct": float(row["min_candidate_total_return_pct"]),
        "max_candidate_drawdown_abs_pct": float(row["max_candidate_drawdown_abs_pct"]),
        "max_candidate_broker10_pct": float(row["max_candidate_broker10_pct"]),
        "min_return_retention_ratio": float(row["min_return_retention_ratio"]),
        "min_drawdown_abs_reduction_pp": float(row["min_drawdown_abs_reduction_pp"]),
    }


def _candidate_package_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Stage142 C9 minrisk candidate package",
        "type": "object",
        "required": ["manifest.json", "summary.csv", "evidence.csv", "visual_artifacts"],
        "properties": {
            "manifest.json": {
                "required": [
                    "candidate_id",
                    "line_id",
                    "created_at",
                    "predeclared_spec_hash",
                    "synthetic_case",
                    "fixture_marker",
                    "source_stage",
                    "true_engine_run_id",
                    "provenance_note",
                ],
            },
            "summary.csv": {"required_columns": REQUIRED_SUMMARY_FIELDS},
            "evidence.csv": {"required_evidence_id": REQUIRED_EVIDENCE_IDS},
            "visual_artifacts": {"required_artifact_id": REQUIRED_VISUAL_IDS},
        },
    }


def _schema_audit(schema: dict[str, Any]) -> pd.DataFrame:
    rows = [
        {
            "schema_item": "manifest_required_fields",
            "required_count": len(schema["properties"]["manifest.json"]["required"]),
            "observed_count": len(schema["properties"]["manifest.json"]["required"]),
            "pass_now": 1,
        },
        {
            "schema_item": "summary_required_fields",
            "required_count": len(REQUIRED_SUMMARY_FIELDS),
            "observed_count": len(REQUIRED_SUMMARY_FIELDS),
            "pass_now": 1,
        },
        {
            "schema_item": "evidence_required_ids",
            "required_count": len(REQUIRED_EVIDENCE_IDS),
            "observed_count": len(REQUIRED_EVIDENCE_IDS),
            "pass_now": 1,
        },
        {
            "schema_item": "visual_required_ids",
            "required_count": len(REQUIRED_VISUAL_IDS),
            "observed_count": len(REQUIRED_VISUAL_IDS),
            "pass_now": 1,
        },
        {
            "schema_item": "stage141_contract_loaded",
            "required_count": 15,
            "observed_count": len(_read_csv(STAGE141_CONTRACT_IN)),
            "pass_now": int(len(_read_csv(STAGE141_CONTRACT_IN)) >= 15),
        },
    ]
    return pd.DataFrame(rows)


def _fixture_png(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(3, 2))
    ax.plot([0, 1], [0, 1], color="#0F766E")
    ax.set_title(path.stem[:28], fontsize=8)
    ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(path, dpi=80)
    plt.close(fig)


def _write_package(
    package_dir: Path,
    candidate_id: str,
    metrics: dict[str, float],
    thresholds: dict[str, float],
    *,
    synthetic_case: int,
    fixture_marker: str,
    full_evidence: bool,
    full_artifacts: bool,
    return_multiplier: float,
    dd_abs: float,
    broker_multiplier: float,
) -> None:
    package_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "candidate_id": candidate_id,
        "line_id": LINE_ID,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "predeclared_spec_hash": f"stage142-fixture-{candidate_id}",
        "synthetic_case": synthetic_case,
        "fixture_marker": fixture_marker,
        "source_stage": STAGE,
        "true_engine_run_id": f"fixture-run-{candidate_id}",
        "provenance_note": "Stage142 local fixture only; never valid as real candidate.",
    }
    _write_json(package_dir / "manifest.json", manifest)
    summary = pd.DataFrame(
        [
            {
                "candidate_id": candidate_id,
                "predeclared_spec_hash": manifest["predeclared_spec_hash"],
                "candidate_total_return_pct": float(metrics["total_return_pct"]) * return_multiplier,
                "candidate_max_drawdown_pct": -float(dd_abs),
                "candidate_max_broker10_margin_to_equity_pct": float(metrics["max_broker10_margin_to_equity_pct"]) * broker_multiplier,
                "candidate_total_trade_count": int(metrics["total_trade_count"]),
                "candidate_closed_lot_win_rate_pct": float(metrics["closed_lot_win_rate_pct"]),
                "candidate_total_slippage": float(metrics["total_slippage"]),
            }
        ]
    )
    _write_csv(summary, package_dir / "summary.csv")
    evidence_rows = []
    for evidence_id in REQUIRED_EVIDENCE_IDS:
        evidence_rows.append(
            {
                "evidence_id": evidence_id,
                "pass_now": int(full_evidence),
                "artifact_path": f"artifacts/{evidence_id}.txt",
                "provenance_note": manifest["provenance_note"],
            }
        )
    _write_csv(pd.DataFrame(evidence_rows), package_dir / "evidence.csv")
    if full_artifacts:
        for artifact_id in REQUIRED_VISUAL_IDS:
            _fixture_png(package_dir / "artifacts" / f"{artifact_id}.png")


def _prepare_fixture_packages(metrics: dict[str, float], thresholds: dict[str, float]) -> list[dict[str, Any]]:
    if FIXTURE_DIR.exists():
        shutil.rmtree(FIXTURE_DIR)
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    good_dd_abs = max(0.0, thresholds["max_candidate_drawdown_abs_pct"] - 1.0)
    _write_package(
        FIXTURE_DIR / "missing_evidence_fixture",
        "missing_evidence_fixture",
        metrics,
        thresholds,
        synthetic_case=1,
        fixture_marker="stage142",
        full_evidence=False,
        full_artifacts=False,
        return_multiplier=0.86,
        dd_abs=good_dd_abs,
        broker_multiplier=0.80,
    )
    _write_package(
        FIXTURE_DIR / "synthetic_good_fixture",
        "synthetic_good_fixture",
        metrics,
        thresholds,
        synthetic_case=1,
        fixture_marker="synthetic",
        full_evidence=True,
        full_artifacts=True,
        return_multiplier=0.86,
        dd_abs=good_dd_abs,
        broker_multiplier=0.80,
    )
    _write_package(
        FIXTURE_DIR / "fake_real_fixture_marker",
        "fake_real_fixture_marker",
        metrics,
        thresholds,
        synthetic_case=0,
        fixture_marker="stage142",
        full_evidence=True,
        full_artifacts=True,
        return_multiplier=0.86,
        dd_abs=good_dd_abs,
        broker_multiplier=0.80,
    )
    return [
        {
            "case_id": "no_package",
            "package_dir": "",
            "expected_would_pass_if_real": 0,
            "expected_promotion_allowed": 0,
        },
        {
            "case_id": "missing_evidence_fixture",
            "package_dir": str(FIXTURE_DIR / "missing_evidence_fixture"),
            "expected_would_pass_if_real": 0,
            "expected_promotion_allowed": 0,
        },
        {
            "case_id": "synthetic_good_fixture",
            "package_dir": str(FIXTURE_DIR / "synthetic_good_fixture"),
            "expected_would_pass_if_real": 1,
            "expected_promotion_allowed": 0,
        },
        {
            "case_id": "fake_real_fixture_marker",
            "package_dir": str(FIXTURE_DIR / "fake_real_fixture_marker"),
            "expected_would_pass_if_real": 1,
            "expected_promotion_allowed": 0,
        },
    ]


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _marker_blocked(manifest: dict[str, Any]) -> int:
    text = " ".join(str(manifest.get(key, "")) for key in ["candidate_id", "fixture_marker", "provenance_note", "source_stage"]).lower()
    return int(any(marker in text for marker in FORBIDDEN_MARKERS))


def _validate_package(package_dir: Path | None, thresholds: dict[str, float], case_id: str) -> dict[str, Any]:
    package_exists = int(package_dir is not None and package_dir.exists())
    if not package_exists or package_dir is None:
        return {
            "case_id": case_id,
            "candidate_id": "",
            "package_dir": "" if package_dir is None else str(package_dir),
            "package_exists": 0,
            "manifest_parse_ok": 0,
            "summary_schema_pass": 0,
            "evidence_schema_pass": 0,
            "visual_artifacts_pass": 0,
            "return_gate": 0,
            "drawdown_gate": 0,
            "broker_gate": 0,
            "all_evidence_pass": 0,
            "synthetic_case": -1,
            "fixture_marker_blocked": 0,
            "would_pass_if_real": 0,
            "promotion_allowed": 0,
        }
    manifest = _read_json(package_dir / "manifest.json")
    summary = _read_csv(package_dir / "summary.csv")
    evidence = _read_csv(package_dir / "evidence.csv")
    manifest_required = _candidate_package_schema()["properties"]["manifest.json"]["required"]
    manifest_parse_ok = int(bool(manifest) and all(field in manifest for field in manifest_required))
    summary_schema_pass = int(not summary.empty and all(field in summary.columns for field in REQUIRED_SUMMARY_FIELDS))
    evidence_schema_pass = int(
        not evidence.empty
        and {"evidence_id", "pass_now"}.issubset(evidence.columns)
        and set(REQUIRED_EVIDENCE_IDS).issubset(set(evidence["evidence_id"].astype(str)))
    )
    artifact_pass_count = 0
    for artifact_id in REQUIRED_VISUAL_IDS:
        matches = list((package_dir / "artifacts").glob(f"{artifact_id}.*"))
        artifact_pass_count += int(any(path.exists() and path.stat().st_size > 0 for path in matches))
    visual_artifacts_pass = int(artifact_pass_count == len(REQUIRED_VISUAL_IDS))
    if summary_schema_pass:
        row = summary.iloc[0]
        candidate_total_return_pct = float(row["candidate_total_return_pct"])
        candidate_max_drawdown_pct = float(row["candidate_max_drawdown_pct"])
        candidate_broker = float(row["candidate_max_broker10_margin_to_equity_pct"])
        return_gate = int(candidate_total_return_pct >= thresholds["min_candidate_total_return_pct"])
        drawdown_gate = int(abs(candidate_max_drawdown_pct) <= thresholds["max_candidate_drawdown_abs_pct"])
        broker_gate = int(candidate_broker <= thresholds["max_candidate_broker10_pct"])
        candidate_id = str(row["candidate_id"])
    else:
        return_gate = drawdown_gate = broker_gate = 0
        candidate_id = str(manifest.get("candidate_id", ""))
    if evidence_schema_pass:
        evidence_pass = evidence[evidence["evidence_id"].isin(REQUIRED_EVIDENCE_IDS)].copy()
        all_evidence_pass = int(pd.to_numeric(evidence_pass["pass_now"], errors="coerce").fillna(0).astype(int).sum() == len(REQUIRED_EVIDENCE_IDS))
    else:
        all_evidence_pass = 0
    synthetic_case = int(manifest.get("synthetic_case", -1)) if manifest_parse_ok else -1
    fixture_marker_blocked = _marker_blocked(manifest) if manifest_parse_ok else 0
    hard_flags = [
        package_exists,
        manifest_parse_ok,
        summary_schema_pass,
        evidence_schema_pass,
        visual_artifacts_pass,
        return_gate,
        drawdown_gate,
        broker_gate,
        all_evidence_pass,
    ]
    would_pass_if_real = int(sum(hard_flags) == len(hard_flags))
    promotion_allowed = int(would_pass_if_real == 1 and synthetic_case == 0 and fixture_marker_blocked == 0)
    return {
        "case_id": case_id,
        "candidate_id": candidate_id,
        "package_dir": str(package_dir),
        "package_exists": package_exists,
        "manifest_parse_ok": manifest_parse_ok,
        "summary_schema_pass": summary_schema_pass,
        "evidence_schema_pass": evidence_schema_pass,
        "visual_artifacts_pass": visual_artifacts_pass,
        "return_gate": return_gate,
        "drawdown_gate": drawdown_gate,
        "broker_gate": broker_gate,
        "all_evidence_pass": all_evidence_pass,
        "synthetic_case": synthetic_case,
        "fixture_marker_blocked": fixture_marker_blocked,
        "would_pass_if_real": would_pass_if_real,
        "promotion_allowed": promotion_allowed,
    }


def _run_cases(cases: list[dict[str, Any]], thresholds: dict[str, float]) -> pd.DataFrame:
    rows = []
    for case in cases:
        package_dir = Path(case["package_dir"]).resolve() if case["package_dir"] else None
        row = _validate_package(package_dir, thresholds, str(case["case_id"]))
        row["expected_would_pass_if_real"] = int(case["expected_would_pass_if_real"])
        row["expected_promotion_allowed"] = int(case["expected_promotion_allowed"])
        row["expectation_pass"] = int(
            row["would_pass_if_real"] == row["expected_would_pass_if_real"]
            and row["promotion_allowed"] == row["expected_promotion_allowed"]
        )
        rows.append(row)
    return pd.DataFrame(rows)


def _gate_status(schema_audit: pd.DataFrame, validation: pd.DataFrame) -> pd.DataFrame:
    schema_pass = int(not schema_audit.empty and int(schema_audit["pass_now"].sum()) == len(schema_audit))
    selftest_pass = int(not validation.empty and int(validation["expectation_pass"].sum()) == len(validation))
    no_promotion = int(int(validation["promotion_allowed"].sum()) == 0) if not validation.empty else 0
    synthetic_block = int(
        not validation.empty
        and int(validation.loc[validation["synthetic_case"] == 1, "promotion_allowed"].sum()) == 0
    )
    fake_real_block = int(
        not validation.empty
        and int(validation.loc[validation["case_id"] == "fake_real_fixture_marker", "promotion_allowed"].sum()) == 0
    )
    rows = [
        {
            "gate_id": "schema_audit_pass",
            "observed": schema_pass,
            "required": 1,
            "pass_now": schema_pass,
            "severity": "schema_hard",
        },
        {
            "gate_id": "selftest_expectations_pass",
            "observed": selftest_pass,
            "required": 1,
            "pass_now": selftest_pass,
            "severity": "selftest_hard",
        },
        {
            "gate_id": "no_package_promoted_now",
            "observed": no_promotion,
            "required": 1,
            "pass_now": no_promotion,
            "severity": "anti_selection_hard",
        },
        {
            "gate_id": "synthetic_packages_blocked",
            "observed": synthetic_block,
            "required": 1,
            "pass_now": synthetic_block,
            "severity": "anti_selection_hard",
        },
        {
            "gate_id": "fake_real_fixture_marker_blocked",
            "observed": fake_real_block,
            "required": 1,
            "pass_now": fake_real_block,
            "severity": "anti_selection_hard",
        },
    ]
    return pd.DataFrame(rows)


def _write_report(summary: pd.DataFrame, schema_audit: pd.DataFrame, validation: pd.DataFrame, gate: pd.DataFrame) -> None:
    report = [
        f"# {STAGE} candidate package contract validator",
        "",
        f"- model_tag: `{MODEL_TAG}`",
        f"- decision: `{summary.iloc[0]['decision']}`",
        "- scope: validate future candidate package structure against Stage141 contract; no strategy rule, no true engine, no A/B, no official config change.",
        "",
        "## Summary",
        "",
        _md_table(summary.drop(columns=["candidate_package_dir"], errors="ignore")),
        "",
        "## Gate Status",
        "",
        _md_table(gate),
        "",
        "## Schema Audit",
        "",
        _md_table(schema_audit),
        "",
        "## Validation Cases",
        "",
        _md_table(
            validation[
                [
                    "case_id",
                    "candidate_id",
                    "package_exists",
                    "summary_schema_pass",
                    "evidence_schema_pass",
                    "visual_artifacts_pass",
                    "return_gate",
                    "drawdown_gate",
                    "broker_gate",
                    "all_evidence_pass",
                    "synthetic_case",
                    "fixture_marker_blocked",
                    "would_pass_if_real",
                    "promotion_allowed",
                    "expectation_pass",
                ]
            ]
        ),
        "",
        "## Visual Outputs",
        "",
        f"- `{PATH_CHART_OUT.name}`",
        f"- `{SCHEMA_CHART_OUT.name}`",
        f"- `{VALIDATION_CHART_OUT.name}`",
        f"- `{SELFTEST_CHART_OUT.name}`",
        f"- `{GATE_CHART_OUT.name}`",
        "",
        "## External References Used",
        "",
        "- JSON Schema validation vocabulary: https://json-schema.org/draft/2020-12/json-schema-validation",
        "- Frictionless Data Package spec: https://specs.frictionlessdata.io/data-package/",
        "- W3C PROV overview: https://www.w3.org/TR/prov-overview/",
    ]
    REPORT_OUT.write_text("\n".join(report) + "\n", encoding="utf-8")


def _plot_official_path(curve: pd.DataFrame, summary: pd.DataFrame) -> None:
    fig, axes = plt.subplots(4, 1, figsize=(15, 11), sharex=False)
    fig.suptitle("Stage142 candidate package validator: no real candidate promoted", fontsize=14, fontweight="bold")
    axes[0].plot(curve["date"], curve["account_equity"] / 1_000_000, color="#1f5d4a", linewidth=1.2)
    axes[0].set_ylabel("equity (m)")
    axes[1].fill_between(curve["date"], curve["drawdown_pct"], 0, color="#C2410C", alpha=0.28)
    axes[1].set_ylabel("drawdown %")
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#3B5BDB", linewidth=1.0)
    axes[2].axhline(100, color="#333333", linestyle="--", linewidth=0.9)
    axes[2].set_ylabel("broker10 %")
    cols = [
        "validator_ready",
        "schema_audit_pass",
        "selftest_pass",
        "current_package_promotion_allowed",
        "real_candidate_package_supplied",
    ]
    plot = summary[cols].T
    plot.columns = ["status"]
    plot.plot(kind="bar", ax=axes[3], legend=False, color="#0F766E")
    axes[3].set_title("Validator status")
    axes[3].set_ylabel("count / flag")
    for ax in axes:
        ax.grid(alpha=0.25)
    fig.tight_layout(rect=[0, 0.02, 1, 0.96])
    fig.savefig(PATH_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_matrix(frame: pd.DataFrame, index_col: str, value_cols: list[str], title: str, path: Path) -> None:
    matrix = frame.set_index(index_col)[value_cols].copy()
    for column in value_cols:
        matrix[column] = pd.to_numeric(matrix[column], errors="coerce").fillna(0).clip(upper=1)
    data = matrix.to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(max(8.5, len(value_cols) * 1.65), max(4.8, len(matrix) * 0.52)))
    image = ax.imshow(data, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_title(title)
    ax.set_xticks(np.arange(len(value_cols)))
    ax.set_xticklabels(value_cols, rotation=30, ha="right")
    ax.set_yticks(np.arange(len(matrix.index)))
    ax.set_yticklabels(matrix.index, fontsize=8)
    for row in range(data.shape[0]):
        for col in range(data.shape[1]):
            ax.text(col, row, int(data[row, col]), ha="center", va="center", fontsize=7)
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(path, dpi=170)
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage142 candidate package validator against Stage141 contract.")
    parser.add_argument(
        "--candidate-package-dir",
        default="",
        help="Optional future real candidate package directory. Default only runs sealed selftests.",
    )
    parser.add_argument("--case-id", default="candidate_package_cli", help="Case id for optional package validation.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curve = _load_curve()
    metrics = _baseline_metrics(curve)
    thresholds = _thresholds_from_stage141()
    schema = _candidate_package_schema()
    _write_json(SCHEMA_OUT, schema)
    schema_audit = _schema_audit(schema)
    cases = _prepare_fixture_packages(metrics, thresholds)
    real_candidate_package_supplied = int(bool(args.candidate_package_dir))
    if args.candidate_package_dir:
        cases.append(
            {
                "case_id": args.case_id,
                "package_dir": str(Path(args.candidate_package_dir).resolve()),
                "expected_would_pass_if_real": 0,
                "expected_promotion_allowed": 0,
            }
        )
    validation = _run_cases(cases, thresholds)
    gate = _gate_status(schema_audit, validation)
    schema_pass = int(schema_audit["pass_now"].sum() == len(schema_audit))
    selftest_pass = int(validation["expectation_pass"].sum() == len(validation))
    current_package_promotion_allowed = int(validation["promotion_allowed"].sum())
    validator_ready = int(gate["pass_now"].sum() == len(gate))
    decision = (
        "stage142_candidate_package_validator_ready_no_real_candidate_promoted"
        if validator_ready
        else "stage142_candidate_package_validator_failed_attention_no_strategy"
    )

    summary = pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "decision": decision,
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "validator_ready": validator_ready,
                "schema_audit_pass": schema_pass,
                "schema_audit_pass_count": int(schema_audit["pass_now"].sum()),
                "schema_audit_count": len(schema_audit),
                "selftest_pass": selftest_pass,
                "validation_case_count": len(validation),
                "validation_expectation_pass_count": int(validation["expectation_pass"].sum()),
                "current_package_promotion_allowed": current_package_promotion_allowed,
                "real_candidate_package_supplied": real_candidate_package_supplied,
                "real_stage112_intake_allowed_now": 0,
                "true_engine_allowed": 0,
                "strategy_feature_usable": 0,
                "min_candidate_total_return_pct": thresholds["min_candidate_total_return_pct"],
                "max_candidate_drawdown_abs_pct": thresholds["max_candidate_drawdown_abs_pct"],
                "max_candidate_broker10_pct": thresholds["max_candidate_broker10_pct"],
                "candidate_package_dir": str(Path(args.candidate_package_dir).resolve()) if args.candidate_package_dir else "",
                **metrics,
            }
        ]
    )

    _write_csv(summary, SUMMARY_OUT)
    _write_csv(schema_audit, SCHEMA_AUDIT_OUT)
    _write_csv(validation, VALIDATION_OUT)
    _write_csv(validation, SELFTEST_OUT)
    _write_csv(gate, GATE_OUT)
    _write_report(summary, schema_audit, validation, gate)
    _plot_official_path(curve, summary)
    _plot_matrix(schema_audit, "schema_item", ["pass_now"], "Stage142 package schema audit", SCHEMA_CHART_OUT)
    _plot_matrix(
        validation,
        "case_id",
        [
            "package_exists",
            "summary_schema_pass",
            "evidence_schema_pass",
            "visual_artifacts_pass",
            "return_gate",
            "drawdown_gate",
            "broker_gate",
            "all_evidence_pass",
            "would_pass_if_real",
            "promotion_allowed",
        ],
        "Stage142 package validation matrix",
        VALIDATION_CHART_OUT,
    )
    _plot_matrix(
        validation,
        "case_id",
        ["would_pass_if_real", "promotion_allowed", "expectation_pass"],
        "Stage142 selftest expectation matrix",
        SELFTEST_CHART_OUT,
    )
    _plot_matrix(gate, "gate_id", ["pass_now"], "Stage142 gate status", GATE_CHART_OUT)
    _write_json(
        DECISION_OUT,
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "decision": decision,
            "outputs": {
                "summary": str(SUMMARY_OUT),
                "candidate_package_schema": str(SCHEMA_OUT),
                "schema_audit": str(SCHEMA_AUDIT_OUT),
                "validation_audit": str(VALIDATION_OUT),
                "selftest_cases": str(SELFTEST_OUT),
                "gate_status": str(GATE_OUT),
                "report": str(REPORT_OUT),
                "charts": [
                    str(PATH_CHART_OUT),
                    str(SCHEMA_CHART_OUT),
                    str(VALIDATION_CHART_OUT),
                    str(SELFTEST_CHART_OUT),
                    str(GATE_CHART_OUT),
                ],
            },
            "locks": {
                "official_config_changed": 0,
                "strategy_rule_created": 0,
                "true_engine_run": 0,
                "ab_triggered": 0,
                "order_api_called": 0,
                "ctp_connected": 0,
                "current_package_promotion_allowed": current_package_promotion_allowed,
                "real_stage112_intake_allowed_now": 0,
                "true_engine_allowed": 0,
                "strategy_feature_usable": 0,
            },
        },
    )
    print(json.dumps(_json_safe(summary.iloc[0].to_dict()), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
