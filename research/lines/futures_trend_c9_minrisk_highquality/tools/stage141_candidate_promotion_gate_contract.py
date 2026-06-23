from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage141"
MODEL_TAG = "stage141_candidate_promotion_gate_contract_v1"
OUTPUT_PREFIX = "qmt_roll_stage141_c9_minrisk_candidate_promotion_gate_contract"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage141_candidate_promotion_gate_contract"

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
STAGE140_SUMMARY_IN = (
    LINE_DIR
    / "outputs"
    / "stage140_wave0_unattended_watch_preinstall_status_panel"
    / "qmt_roll_stage140_c9_minrisk_wave0_unattended_watch_preinstall_status_panel_summary_"
    "stage140_wave0_unattended_watch_preinstall_status_panel_v1.csv"
)

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CONTRACT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_promotion_contract_{MODEL_TAG}.csv"
SELFTEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_contract_selftest_cases_{MODEL_TAG}.csv"
GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_{MODEL_TAG}.csv"
INPUT_SCHEMA_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_future_candidate_input_schema_{MODEL_TAG}.md"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

THRESHOLD_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_thresholds_{MODEL_TAG}.png"
CONTRACT_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_promotion_contract_matrix_{MODEL_TAG}.png"
SELFTEST_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_contract_selftest_matrix_{MODEL_TAG}.png"
OVERFIT_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_anti_overfit_layers_{MODEL_TAG}.png"
GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_matrix_{MODEL_TAG}.png"


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


def _thresholds(metrics: dict[str, float]) -> dict[str, float]:
    baseline_return = float(metrics["total_return_pct"])
    baseline_dd_abs = abs(float(metrics["max_drawdown_pct"]))
    baseline_broker = float(metrics["max_broker10_margin_to_equity_pct"])
    return {
        "min_return_retention_ratio": 0.80,
        "min_candidate_total_return_pct": baseline_return * 0.80,
        "baseline_max_drawdown_abs_pct": baseline_dd_abs,
        "min_drawdown_abs_reduction_pp": 5.0,
        "max_candidate_drawdown_abs_pct": max(0.0, baseline_dd_abs - 5.0),
        "max_candidate_broker10_pct": baseline_broker,
        "preferred_broker10_pct": 100.0,
        "min_visual_artifact_count": 5.0,
        "min_oos_gate_count": 4.0,
        "max_pbo_allowed": 0.10,
        "min_dsr_required": 0.00,
    }


def _promotion_contract(metrics: dict[str, float], thresholds: dict[str, float]) -> pd.DataFrame:
    rows = [
        {
            "gate_id": "predeclared_spec_before_backtest",
            "category": "anti_overfit",
            "hard_required": 1,
            "threshold": "predeclared_spec_hash present before true engine",
            "rationale": "No post-hoc rule rescue or threshold mining.",
        },
        {
            "gate_id": "authorized_point_in_time_data",
            "category": "data_integrity",
            "hard_required": 1,
            "threshold": "Stage112/113 or equivalent raw provenance and coverage pass",
            "rationale": "Minute/orderflow rules must not use synthetic, smoke, or local fixture data.",
        },
        {
            "gate_id": "true_engine_replay_only",
            "category": "execution_integrity",
            "hard_required": 1,
            "threshold": "true engine replay, fallback/no-proxy samples keep official path",
            "rationale": "Proxy labels and residual samples cannot become trading rules.",
        },
        {
            "gate_id": "return_retention_80pct",
            "category": "performance",
            "hard_required": 1,
            "threshold": f"total_return_pct >= {thresholds['min_candidate_total_return_pct']:.4f}",
            "rationale": "User target: keep at least 80 percent of baseline return.",
        },
        {
            "gate_id": "drawdown_reduction_min_5pp",
            "category": "performance",
            "hard_required": 1,
            "threshold": f"abs(max_drawdown_pct) <= {thresholds['max_candidate_drawdown_abs_pct']:.4f}",
            "rationale": "Cosmetic drawdown improvement is not enough.",
        },
        {
            "gate_id": "margin_stress_not_worse",
            "category": "risk",
            "hard_required": 1,
            "threshold": f"max_broker10_margin_to_equity_pct <= {thresholds['max_candidate_broker10_pct']:.4f}",
            "rationale": "Lower drawdown must not hide more leverage stress.",
        },
        {
            "gate_id": "walk_forward_oos_pass",
            "category": "anti_overfit",
            "hard_required": 1,
            "threshold": "walk-forward and/or purged OOS evidence pass",
            "rationale": "Avoid time-series leakage and winner-picking.",
        },
        {
            "gate_id": "leave_one_year_pass",
            "category": "cycle_robustness",
            "hard_required": 1,
            "threshold": "leave-one-year or equivalent year-block stability pass",
            "rationale": "Rule must cross regimes, not one calendar episode.",
        },
        {
            "gate_id": "product_family_pass",
            "category": "universality",
            "hard_required": 1,
            "threshold": "no single product/exchange/family drives the result",
            "rationale": "Avoid product/year patching.",
        },
        {
            "gate_id": "monthly_start_pass",
            "category": "cycle_robustness",
            "hard_required": 1,
            "threshold": "monthly-start or rolling-start audit pass",
            "rationale": "Avoid lucky initial capital path.",
        },
        {
            "gate_id": "right_tail_protection_pass",
            "category": "right_tail",
            "hard_required": 1,
            "threshold": "right-tail winners visually and numerically protected",
            "rationale": "Do not cut the C9 compounding base.",
        },
        {
            "gate_id": "bottom_loss_improvement_pass",
            "category": "drawdown_quality",
            "hard_required": 1,
            "threshold": "bottom-loss and maxDD episodes improve without label leakage",
            "rationale": "Drawdown reduction must come from ex-ante structure.",
        },
        {
            "gate_id": "visual_artifacts_complete",
            "category": "visual",
            "hard_required": 1,
            "threshold": "equity, drawdown, broker10, minute K atlas, right-tail/bottom-loss atlas",
            "rationale": "Every study must be visually inspected, not just metric-driven.",
        },
        {
            "gate_id": "pbo_dsr_pass",
            "category": "anti_overfit",
            "hard_required": 1,
            "threshold": f"PBO <= {thresholds['max_pbo_allowed']:.2f} and DSR > {thresholds['min_dsr_required']:.2f} if multiple variants were explored",
            "rationale": "Correct for multiple testing and non-normal returns.",
        },
        {
            "gate_id": "no_parameter_sweep_rescue",
            "category": "anti_overfit",
            "hard_required": 1,
            "threshold": "no threshold/window/product/year rescue after failure",
            "rationale": "A failed first-principles shape is closed, not tuned until it passes.",
        },
    ]
    contract = pd.DataFrame(rows)
    contract["baseline_total_return_pct"] = float(metrics["total_return_pct"])
    contract["baseline_max_drawdown_pct"] = float(metrics["max_drawdown_pct"])
    contract["baseline_max_broker10_pct"] = float(metrics["max_broker10_margin_to_equity_pct"])
    return contract


def _candidate_cases(metrics: dict[str, float], thresholds: dict[str, float]) -> pd.DataFrame:
    base_return = float(metrics["total_return_pct"])
    base_dd = float(metrics["max_drawdown_pct"])
    base_broker = float(metrics["max_broker10_margin_to_equity_pct"])
    improved_dd = -max(0.0, abs(base_dd) - 6.0)
    rows = [
        {
            "candidate_id": "current_no_candidate",
            "synthetic_case": 0,
            "candidate_total_return_pct": np.nan,
            "candidate_max_drawdown_pct": np.nan,
            "candidate_max_broker10_pct": np.nan,
            "all_evidence_flags": 0,
            "expected_would_pass_if_real": 0,
        },
        {
            "candidate_id": "official_baseline_as_candidate",
            "synthetic_case": 1,
            "candidate_total_return_pct": base_return,
            "candidate_max_drawdown_pct": base_dd,
            "candidate_max_broker10_pct": base_broker,
            "all_evidence_flags": 1,
            "expected_would_pass_if_real": 0,
        },
        {
            "candidate_id": "high_return_no_drawdown_improvement",
            "synthetic_case": 1,
            "candidate_total_return_pct": base_return * 0.95,
            "candidate_max_drawdown_pct": base_dd + 1.0,
            "candidate_max_broker10_pct": base_broker * 0.95,
            "all_evidence_flags": 1,
            "expected_would_pass_if_real": 0,
        },
        {
            "candidate_id": "drawdown_improved_return_too_low",
            "synthetic_case": 1,
            "candidate_total_return_pct": base_return * 0.55,
            "candidate_max_drawdown_pct": improved_dd,
            "candidate_max_broker10_pct": base_broker * 0.80,
            "all_evidence_flags": 1,
            "expected_would_pass_if_real": 0,
        },
        {
            "candidate_id": "looks_good_missing_oos_evidence",
            "synthetic_case": 1,
            "candidate_total_return_pct": base_return * 0.85,
            "candidate_max_drawdown_pct": improved_dd,
            "candidate_max_broker10_pct": base_broker * 0.85,
            "all_evidence_flags": 0,
            "expected_would_pass_if_real": 0,
        },
        {
            "candidate_id": "synthetic_contract_positive",
            "synthetic_case": 1,
            "candidate_total_return_pct": base_return * 0.86,
            "candidate_max_drawdown_pct": improved_dd,
            "candidate_max_broker10_pct": base_broker * 0.82,
            "all_evidence_flags": 1,
            "expected_would_pass_if_real": 1,
        },
    ]
    return pd.DataFrame(rows)


def _evaluate_cases(cases: pd.DataFrame, metrics: dict[str, float], thresholds: dict[str, float]) -> pd.DataFrame:
    evaluated = cases.copy()
    evaluated["return_retention_ratio"] = evaluated["candidate_total_return_pct"] / float(metrics["total_return_pct"])
    evaluated["drawdown_abs_reduction_pp"] = abs(float(metrics["max_drawdown_pct"])) - evaluated["candidate_max_drawdown_pct"].abs()
    evaluated["return_gate"] = (evaluated["return_retention_ratio"] >= thresholds["min_return_retention_ratio"]).astype(int)
    evaluated["drawdown_gate"] = (evaluated["drawdown_abs_reduction_pp"] >= thresholds["min_drawdown_abs_reduction_pp"]).astype(int)
    evaluated["broker_gate"] = (evaluated["candidate_max_broker10_pct"] <= thresholds["max_candidate_broker10_pct"]).astype(int)
    evaluated.loc[evaluated["candidate_total_return_pct"].isna(), ["return_gate", "drawdown_gate", "broker_gate"]] = 0
    evidence_cols = [
        "predeclared_spec_pass",
        "authorized_data_pass",
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
    for column in evidence_cols:
        evaluated[column] = evaluated["all_evidence_flags"].astype(int)
    hard_cols = ["return_gate", "drawdown_gate", "broker_gate", *evidence_cols]
    evaluated["contract_logic_pass"] = (evaluated[hard_cols].sum(axis=1) == len(hard_cols)).astype(int)
    evaluated["would_pass_if_real"] = evaluated["contract_logic_pass"]
    evaluated["promotion_allowed_now"] = ((evaluated["contract_logic_pass"] == 1) & (evaluated["synthetic_case"] == 0)).astype(int)
    evaluated["selftest_expectation_pass"] = (
        evaluated["would_pass_if_real"].astype(int) == evaluated["expected_would_pass_if_real"].astype(int)
    ).astype(int)
    return evaluated


def _gate_status(contract: pd.DataFrame, evaluated: pd.DataFrame, stage140_summary: pd.DataFrame) -> pd.DataFrame:
    contract_complete = int(len(contract) >= 15 and int(contract["hard_required"].sum()) == len(contract))
    selftest_pass = int(not evaluated.empty and int(evaluated["selftest_expectation_pass"].sum()) == len(evaluated))
    positive_logic = int(
        not evaluated.empty
        and int(evaluated.loc[evaluated["candidate_id"] == "synthetic_contract_positive", "would_pass_if_real"].sum()) == 1
    )
    synthetic_not_promoted = int(int(evaluated["promotion_allowed_now"].sum()) == 0)
    stage140_still_locked = int(
        not stage140_summary.empty
        and int(stage140_summary.iloc[0].get("real_w0_data_delivered", -1)) == 0
        and int(stage140_summary.iloc[0].get("stage133_release_allowed_now", -1)) == 0
    )
    rows = [
        {
            "gate_id": "promotion_contract_all_hard_gates_defined",
            "observed": contract_complete,
            "required": 1,
            "pass_now": contract_complete,
            "severity": "contract_hard",
        },
        {
            "gate_id": "contract_selftest_expectations_pass",
            "observed": selftest_pass,
            "required": 1,
            "pass_now": selftest_pass,
            "severity": "selftest_hard",
        },
        {
            "gate_id": "positive_control_would_pass_if_real",
            "observed": positive_logic,
            "required": 1,
            "pass_now": positive_logic,
            "severity": "selftest_hard",
        },
        {
            "gate_id": "synthetic_cases_not_promoted",
            "observed": synthetic_not_promoted,
            "required": 1,
            "pass_now": synthetic_not_promoted,
            "severity": "anti_selection_hard",
        },
        {
            "gate_id": "stage140_still_blocks_strategy_without_real_w0",
            "observed": stage140_still_locked,
            "required": 1,
            "pass_now": stage140_still_locked,
            "severity": "data_hard",
        },
    ]
    return pd.DataFrame(rows)


def _write_input_schema(thresholds: dict[str, float]) -> None:
    lines = [
        "# Stage141 future candidate input schema",
        "",
        "A future minute/market-microstructure candidate must provide these fields before promotion is considered.",
        "",
        "## Required scalar metrics",
        "",
        "- `candidate_id`",
        "- `predeclared_spec_hash`",
        "- `candidate_total_return_pct`",
        "- `candidate_max_drawdown_pct`",
        "- `candidate_max_broker10_margin_to_equity_pct`",
        "- `candidate_total_trade_count`",
        "- `candidate_closed_lot_win_rate_pct`",
        "- `candidate_total_slippage`",
        "",
        "## Required hard evidence flags",
        "",
        "- `authorized_point_in_time_data_pass`",
        "- `true_engine_replay_pass`",
        "- `walk_forward_oos_pass`",
        "- `leave_one_year_pass`",
        "- `product_family_pass`",
        "- `monthly_start_pass`",
        "- `right_tail_protection_pass`",
        "- `bottom_loss_improvement_pass`",
        "- `visual_artifacts_complete`",
        "- `pbo_dsr_pass`",
        "- `no_parameter_sweep_rescue`",
        "",
        "## Required visual artifacts",
        "",
        "- Equity curve vs official baseline",
        "- Drawdown curve vs official baseline",
        "- Broker10/margin stress curve vs official baseline",
        "- Minute K atlas for candidate-triggered entries/exits",
        "- Right-tail and bottom-loss atlas proving no systematic right-tail cut",
        "",
        "## Current hard thresholds",
        "",
        f"- Minimum return retention: `{thresholds['min_return_retention_ratio']:.2%}`",
        f"- Minimum candidate total return: `{thresholds['min_candidate_total_return_pct']:.4f}%`",
        f"- Maximum candidate absolute drawdown: `{thresholds['max_candidate_drawdown_abs_pct']:.4f}%`",
        f"- Maximum candidate broker10 stress: `{thresholds['max_candidate_broker10_pct']:.4f}%`",
        f"- Maximum PBO if multiple variants exist: `{thresholds['max_pbo_allowed']:.2f}`",
        f"- Minimum DSR if multiple variants exist: `>{thresholds['min_dsr_required']:.2f}`",
        "",
    ]
    INPUT_SCHEMA_OUT.write_text("\n".join(lines), encoding="utf-8")


def _write_report(summary: pd.DataFrame, contract: pd.DataFrame, evaluated: pd.DataFrame, gate: pd.DataFrame) -> None:
    report = [
        f"# {STAGE} candidate promotion gate contract",
        "",
        f"- model_tag: `{MODEL_TAG}`",
        f"- decision: `{summary.iloc[0]['decision']}`",
        "- scope: define non-negotiable promotion gates for any future minute/microstructure candidate; no strategy rule, no true engine, no A/B, no official config change.",
        "",
        "## Summary",
        "",
        _md_table(summary.drop(columns=["input_schema_path"], errors="ignore")),
        "",
        "## Gate Status",
        "",
        _md_table(gate),
        "",
        "## Promotion Contract",
        "",
        _md_table(contract[["gate_id", "category", "hard_required", "threshold"]]),
        "",
        "## Contract Selftest Cases",
        "",
        _md_table(
            evaluated[
                [
                    "candidate_id",
                    "synthetic_case",
                    "return_gate",
                    "drawdown_gate",
                    "broker_gate",
                    "all_evidence_flags",
                    "would_pass_if_real",
                    "promotion_allowed_now",
                    "selftest_expectation_pass",
                ]
            ]
        ),
        "",
        "## Visual Outputs",
        "",
        f"- `{THRESHOLD_CHART_OUT.name}`",
        f"- `{CONTRACT_CHART_OUT.name}`",
        f"- `{SELFTEST_CHART_OUT.name}`",
        f"- `{OVERFIT_CHART_OUT.name}`",
        f"- `{GATE_CHART_OUT.name}`",
        "",
        "## External References Used",
        "",
        "- Bailey et al., The Probability of Backtest Overfitting: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253",
        "- Bailey and Lopez de Prado, Deflated Sharpe Ratio: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551",
        "- Journal of Computational Finance page on PBO: https://www.risk.net/journal-of-computational-finance/2471206/the-probability-of-backtest-overfitting",
    ]
    REPORT_OUT.write_text("\n".join(report) + "\n", encoding="utf-8")


def _plot_thresholds(curve: pd.DataFrame, metrics: dict[str, float], thresholds: dict[str, float]) -> None:
    fig, axes = plt.subplots(4, 1, figsize=(15, 11), sharex=False)
    fig.suptitle("Stage141 promotion thresholds: baseline path and non-negotiable candidate bars", fontsize=14, fontweight="bold")
    axes[0].plot(curve["date"], curve["account_equity"] / 1_000_000, color="#1f5d4a", linewidth=1.2)
    axes[0].set_ylabel("equity (m)")
    axes[1].fill_between(curve["date"], curve["drawdown_pct"], 0, color="#C2410C", alpha=0.28)
    axes[1].axhline(-thresholds["max_candidate_drawdown_abs_pct"], color="#111827", linestyle="--", linewidth=1.0, label="future candidate max abs DD")
    axes[1].legend(loc="lower left")
    axes[1].set_ylabel("drawdown %")
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#3B5BDB", linewidth=1.0)
    axes[2].axhline(thresholds["max_candidate_broker10_pct"], color="#111827", linestyle="--", linewidth=1.0, label="not worse than baseline")
    axes[2].axhline(thresholds["preferred_broker10_pct"], color="#9A3412", linestyle=":", linewidth=1.0, label="preferred <=100")
    axes[2].legend(loc="upper right")
    axes[2].set_ylabel("broker10 %")
    labels = ["baseline_return", "min_candidate_return", "baseline_abs_dd", "max_candidate_abs_dd"]
    values = [
        float(metrics["total_return_pct"]),
        thresholds["min_candidate_total_return_pct"],
        abs(float(metrics["max_drawdown_pct"])),
        thresholds["max_candidate_drawdown_abs_pct"],
    ]
    axes[3].bar(labels, values, color=["#1f5d4a", "#0F766E", "#B91C1C", "#F97316"])
    axes[3].set_title("Promotion thresholds")
    axes[3].tick_params(axis="x", rotation=20)
    for ax in axes:
        ax.grid(alpha=0.25)
    fig.tight_layout(rect=[0, 0.02, 1, 0.96])
    fig.savefig(THRESHOLD_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_matrix(frame: pd.DataFrame, index_col: str, value_cols: list[str], title: str, path: Path) -> None:
    matrix = frame.set_index(index_col)[value_cols].copy()
    for column in value_cols:
        matrix[column] = pd.to_numeric(matrix[column], errors="coerce").fillna(0).clip(upper=1)
    data = matrix.to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(max(8.5, len(value_cols) * 1.7), max(4.8, len(matrix) * 0.46)))
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


def _plot_overfit_layers(contract: pd.DataFrame) -> None:
    counts = contract.groupby("category")["hard_required"].sum().sort_values(ascending=False)
    fig, ax = plt.subplots(figsize=(12, 6))
    counts.plot(kind="bar", ax=ax, color="#0F766E")
    ax.set_title("Stage141 anti-overfit and promotion hard-gate layers")
    ax.set_ylabel("hard gate count")
    ax.tick_params(axis="x", rotation=30)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(OVERFIT_CHART_OUT, dpi=170)
    plt.close(fig)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curve = _load_curve()
    metrics = _baseline_metrics(curve)
    thresholds = _thresholds(metrics)
    contract = _promotion_contract(metrics, thresholds)
    cases = _candidate_cases(metrics, thresholds)
    evaluated = _evaluate_cases(cases, metrics, thresholds)
    stage140_summary = _read_csv(STAGE140_SUMMARY_IN)
    gate = _gate_status(contract, evaluated, stage140_summary)
    _write_input_schema(thresholds)

    contract_ready = int(gate["pass_now"].sum() == len(gate))
    decision = (
        "stage141_candidate_promotion_contract_ready_no_candidate_no_strategy"
        if contract_ready
        else "stage141_candidate_promotion_contract_failed_attention_no_strategy"
    )
    current_candidate_promotion_allowed = int(evaluated["promotion_allowed_now"].sum())
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
                "contract_ready": contract_ready,
                "hard_gate_count": len(contract),
                "contract_selftest_case_count": len(evaluated),
                "contract_selftest_pass_count": int(evaluated["selftest_expectation_pass"].sum()),
                "current_candidate_promotion_allowed": current_candidate_promotion_allowed,
                "synthetic_promotion_allowed": 0,
                "real_w0_data_delivered": int(stage140_summary.iloc[0].get("real_w0_data_delivered", 0)) if not stage140_summary.empty else 0,
                "stage133_release_allowed_now": int(stage140_summary.iloc[0].get("stage133_release_allowed_now", 0)) if not stage140_summary.empty else 0,
                "real_stage112_intake_allowed_now": 0,
                "true_engine_allowed": 0,
                "strategy_feature_usable": 0,
                "min_return_retention_ratio": thresholds["min_return_retention_ratio"],
                "min_candidate_total_return_pct": thresholds["min_candidate_total_return_pct"],
                "min_drawdown_abs_reduction_pp": thresholds["min_drawdown_abs_reduction_pp"],
                "max_candidate_drawdown_abs_pct": thresholds["max_candidate_drawdown_abs_pct"],
                "max_candidate_broker10_pct": thresholds["max_candidate_broker10_pct"],
                "input_schema_path": str(INPUT_SCHEMA_OUT),
                **metrics,
            }
        ]
    )

    _write_csv(summary, SUMMARY_OUT)
    _write_csv(contract, CONTRACT_OUT)
    _write_csv(evaluated, SELFTEST_OUT)
    _write_csv(gate, GATE_OUT)
    _write_report(summary, contract, evaluated, gate)
    _plot_thresholds(curve, metrics, thresholds)
    _plot_matrix(contract, "gate_id", ["hard_required"], "Stage141 promotion contract hard gates", CONTRACT_CHART_OUT)
    _plot_matrix(
        evaluated,
        "candidate_id",
        ["return_gate", "drawdown_gate", "broker_gate", "all_evidence_flags", "would_pass_if_real", "promotion_allowed_now"],
        "Stage141 contract selftest cases",
        SELFTEST_CHART_OUT,
    )
    _plot_overfit_layers(contract)
    _plot_matrix(gate, "gate_id", ["pass_now"], "Stage141 gate status", GATE_CHART_OUT)
    _write_json(
        DECISION_OUT,
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "decision": decision,
            "outputs": {
                "summary": str(SUMMARY_OUT),
                "promotion_contract": str(CONTRACT_OUT),
                "contract_selftest_cases": str(SELFTEST_OUT),
                "gate_status": str(GATE_OUT),
                "input_schema": str(INPUT_SCHEMA_OUT),
                "report": str(REPORT_OUT),
                "charts": [
                    str(THRESHOLD_CHART_OUT),
                    str(CONTRACT_CHART_OUT),
                    str(SELFTEST_CHART_OUT),
                    str(OVERFIT_CHART_OUT),
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
                "current_candidate_promotion_allowed": current_candidate_promotion_allowed,
                "real_stage112_intake_allowed_now": 0,
                "true_engine_allowed": 0,
                "strategy_feature_usable": 0,
            },
        },
    )
    print(json.dumps(_json_safe(summary.iloc[0].to_dict()), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
