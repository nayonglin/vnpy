from __future__ import annotations

from dataclasses import dataclass
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
STAGE = "Stage261"
MODEL_TAG = "stage261_outside_account_governance_boundary_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage261_c9_minrisk_outside_account_governance_boundary_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage261_outside_account_governance_boundary_audit"

STAGE017_DIR = LINE_DIR / "outputs" / "stage017_account_layer_cppi_tipp_audit"
STAGE020_DIR = LINE_DIR / "outputs" / "stage020_balanced_tranche_profit_lock_proxy"
STAGE251_DIR = LINE_DIR / "outputs" / "stage251_dd30_account_floor_true_engine"
STAGE259_DIR = LINE_DIR / "outputs" / "stage259_remaining_route_exhaustion_audit"
STAGE260_DIR = LINE_DIR / "outputs" / "stage260_execution_replay_source_inventory_audit"

STAGE017_PREFIX = "qmt_roll_stage017_c9_minrisk_account_layer_cppi_tipp_audit"
STAGE020_PREFIX = "qmt_roll_stage020_c9_minrisk_balanced_tranche_profit_lock_proxy"
STAGE251_PREFIX = "qmt_roll_stage251_c9_minrisk_dd30_account_floor_true_engine"
STAGE259_PREFIX = "qmt_roll_stage259_c9_minrisk_remaining_route_exhaustion_audit"
STAGE260_PREFIX = "qmt_roll_stage260_c9_minrisk_execution_replay_source_inventory_audit"

STAGE017_TAG = "stage017_account_layer_cppi_tipp_audit_v1"
STAGE020_TAG = "stage020_balanced_tranche_profit_lock_proxy_v1"
STAGE251_TAG = "stage251_dd30_account_floor_true_engine_v1"
STAGE259_TAG = "stage259_remaining_route_exhaustion_audit_v1"
STAGE260_TAG = "stage260_execution_replay_source_inventory_audit_v1"

STAGE017_SUMMARY_IN = STAGE017_DIR / f"{STAGE017_PREFIX}_summary_{STAGE017_TAG}.csv"
STAGE020_SUMMARY_IN = STAGE020_DIR / f"{STAGE020_PREFIX}_summary_{STAGE020_TAG}.csv"
STAGE251_CURVE_IN = STAGE251_DIR / f"{STAGE251_PREFIX}_curve_{STAGE251_TAG}.csv"
STAGE251_SUMMARY_IN = STAGE251_DIR / f"{STAGE251_PREFIX}_summary_{STAGE251_TAG}.csv"
STAGE259_NEXT_ACTION_IN = STAGE259_DIR / f"{STAGE259_PREFIX}_next_action_queue_{STAGE259_TAG}.csv"
STAGE260_SUMMARY_IN = STAGE260_DIR / f"{STAGE260_PREFIX}_summary_{STAGE260_TAG}.csv"

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
POLICY_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_policy_summary_{MODEL_TAG}.csv"
LEDGER_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_ledger_{MODEL_TAG}.csv"
TRANSFER_EVENTS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_transfer_events_{MODEL_TAG}.csv"
INVARIANT_GATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_invariant_gate_{MODEL_TAG}.csv"
PRIOR_EVIDENCE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_prior_evidence_{MODEL_TAG}.csv"
NEXT_ACTION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_next_action_queue_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_vs_total_wealth_path_{MODEL_TAG}.png"
BUCKET_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_layer_chart_{MODEL_TAG}.png"
DRAWDOWN_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_drawdown_invariance_chart_{MODEL_TAG}.png"
FRONTIER_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_return_drawdown_frontier_{MODEL_TAG}.png"
GATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_invariant_gate_chart_{MODEL_TAG}.png"

CAPITAL = 150_000.0
TRADING_DAYS_PER_YEAR = 252
EPS = 1e-6


@dataclass(frozen=True)
class TransferPolicy:
    policy_id: str
    cadence: str
    sweep_rule: str
    sweep_start: float
    sweep_ratio: float
    lock_ratio: float
    reserve_ratio: float
    refill_floor: float
    description: str


POLICIES = [
    TransferPolicy(
        policy_id="A_official_no_transfer",
        cadence="none",
        sweep_rule="none",
        sweep_start=np.inf,
        sweep_ratio=0.0,
        lock_ratio=0.0,
        reserve_ratio=0.0,
        refill_floor=CAPITAL,
        description="Official path with no external bucket transfer.",
    ),
    TransferPolicy(
        policy_id="B_monthly_5m_half_lock60_reserve40_transfer_only",
        cadence="month_end",
        sweep_rule="production_surplus_above_start",
        sweep_start=5_000_000.0,
        sweep_ratio=0.50,
        lock_ratio=0.60,
        reserve_ratio=0.40,
        refill_floor=CAPITAL,
        description="Stage020 shape replayed as pure treasury transfer; production PnL is not scaled.",
    ),
    TransferPolicy(
        policy_id="C_monthly_new_hwm_10pct_lockbox",
        cadence="month_end",
        sweep_rule="new_total_hwm_profit",
        sweep_start=CAPITAL,
        sweep_ratio=0.10,
        lock_ratio=1.00,
        reserve_ratio=0.00,
        refill_floor=CAPITAL,
        description="Universal new-high profit skim; no change to official holdings.",
    ),
    TransferPolicy(
        policy_id="D_quarter_end_profit_20pct_reserve",
        cadence="quarter_end",
        sweep_rule="new_total_hwm_profit",
        sweep_start=CAPITAL,
        sweep_ratio=0.20,
        lock_ratio=0.50,
        reserve_ratio=0.50,
        refill_floor=CAPITAL,
        description="Quarterly profit reserve split; no change to official holdings.",
    ),
    TransferPolicy(
        policy_id="E_year_end_profit_30pct_lockbox",
        cadence="year_end",
        sweep_rule="new_total_hwm_profit",
        sweep_start=CAPITAL,
        sweep_ratio=0.30,
        lock_ratio=1.00,
        reserve_ratio=0.00,
        refill_floor=CAPITAL,
        description="Annual profit lockbox; no change to official holdings.",
    ),
]


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        number = float(value)
        return number if np.isfinite(number) else None
    if isinstance(value, (pd.Timestamp, datetime)):
        if pd.isna(value):
            return None
        return pd.Timestamp(value).strftime("%Y-%m-%d")
    if pd.isna(value):
        return None
    return value


def _read_csv(path: Path, required: bool = True) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size <= 4:
        if required:
            raise RuntimeError(f"missing required input: {path}")
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _row(frame: pd.DataFrame) -> dict[str, Any]:
    return frame.iloc[0].to_dict() if not frame.empty else {}


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if np.isfinite(number) else default


def _to_int(value: Any, default: int = 0) -> int:
    try:
        if pd.isna(value):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _safe_div(num: float, den: float) -> float:
    return float(num) / float(den) if abs(float(den)) > 1e-12 else np.nan


def _drawdown_pct(values: pd.Series | np.ndarray) -> pd.Series:
    series = pd.Series(values, dtype="float64")
    hwm = series.cummax()
    return (series / hwm - 1.0) * 100.0


def _sharpe(equity: pd.Series) -> float:
    returns = equity.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    if returns.empty or returns.std(ddof=0) <= 1e-12:
        return np.nan
    return float(returns.mean() / returns.std(ddof=0) * np.sqrt(TRADING_DAYS_PER_YEAR))


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


def _load_inputs() -> dict[str, Any]:
    return {
        "stage017_summary": _read_csv(STAGE017_SUMMARY_IN, required=False),
        "stage020_summary": _read_csv(STAGE020_SUMMARY_IN, required=False),
        "stage251_curve": _read_csv(STAGE251_CURVE_IN),
        "stage251_summary": _read_csv(STAGE251_SUMMARY_IN),
        "stage259_next_action": _read_csv(STAGE259_NEXT_ACTION_IN, required=False),
        "stage260_summary": _read_csv(STAGE260_SUMMARY_IN, required=False),
    }


def _official_summary(stage251_summary: pd.DataFrame) -> dict[str, Any]:
    official = stage251_summary[stage251_summary.get("arm", pd.Series(dtype=str)).astype(str).eq("A_official_stage847_c9_15w")]
    return _row(official) if not official.empty else _row(stage251_summary)


def _official_curve(stage251_curve: pd.DataFrame) -> pd.DataFrame:
    curve = stage251_curve.copy()
    official = curve[curve.get("arm", pd.Series(dtype=str)).astype(str).eq("A_official_stage847_c9_15w")].copy()
    if official.empty:
        official = curve.copy()
    official["date"] = pd.to_datetime(official["date"], errors="coerce")
    official = official[official["date"].notna()].sort_values("date").reset_index(drop=True)
    for column in ["account_equity", "net_pnl", "total_margin_exact", "broker10_total_margin_exact", "broker10_margin_to_equity_pct"]:
        official[column] = pd.to_numeric(official.get(column, 0.0), errors="coerce").fillna(0.0)
    official["official_drawdown_pct"] = _drawdown_pct(official["account_equity"]).to_numpy()
    return official


def _is_transfer_day(dates: pd.Series, idx: int, cadence: str) -> bool:
    if cadence == "none":
        return False
    current = dates.iloc[idx]
    if idx >= len(dates) - 1:
        return True
    nxt = dates.iloc[idx + 1]
    if cadence == "month_end":
        return current.month != nxt.month or current.year != nxt.year
    if cadence == "quarter_end":
        return (current.quarter != nxt.quarter) or current.year != nxt.year
    if cadence == "year_end":
        return current.year != nxt.year
    raise RuntimeError(f"unsupported cadence: {cadence}")


def _simulate_policy(official: pd.DataFrame, policy: TransferPolicy) -> tuple[pd.DataFrame, pd.DataFrame]:
    production = CAPITAL
    locked = 0.0
    reserve = 0.0
    last_total_hwm_swept = CAPITAL
    transfer_rows: list[dict[str, Any]] = []
    ledger_rows: list[dict[str, Any]] = []
    dates = official["date"]

    for idx, row in official.iterrows():
        date = pd.Timestamp(row["date"])
        production += float(row["net_pnl"])
        refill = 0.0
        if production < policy.refill_floor and reserve > 0:
            refill = min(policy.refill_floor - production, reserve)
            reserve -= refill
            production += refill

        sweep = 0.0
        lock_add = 0.0
        reserve_add = 0.0
        total_before = production + locked + reserve
        if _is_transfer_day(dates, idx, policy.cadence):
            if policy.sweep_rule == "production_surplus_above_start":
                eligible = max(0.0, production - policy.sweep_start)
            elif policy.sweep_rule == "new_total_hwm_profit":
                eligible = max(0.0, total_before - max(policy.sweep_start, last_total_hwm_swept))
            elif policy.sweep_rule == "none":
                eligible = 0.0
            else:
                raise RuntimeError(f"unsupported sweep rule: {policy.sweep_rule}")
            max_sweep = max(0.0, production - policy.refill_floor)
            sweep = min(max_sweep, eligible * policy.sweep_ratio)
            if sweep > 0:
                production -= sweep
                lock_add = sweep * policy.lock_ratio
                reserve_add = sweep * policy.reserve_ratio
                locked += lock_add
                reserve += reserve_add
                last_total_hwm_swept = max(last_total_hwm_swept, total_before)

        total_wealth = production + locked + reserve
        broker10_margin = float(row["broker10_total_margin_exact"])
        broker10_prod_pct = broker10_margin / production * 100.0 if production > 0 else np.inf
        broker10_total_pct = broker10_margin / total_wealth * 100.0 if total_wealth > 0 else np.inf
        official_equity = float(row["account_equity"])
        invariant_diff = total_wealth - official_equity
        ledger_rows.append(
            {
                "date": date,
                "policy_id": policy.policy_id,
                "official_equity": official_equity,
                "net_pnl_unchanged": float(row["net_pnl"]),
                "production_equity": production,
                "locked_equity": locked,
                "reserve_equity": reserve,
                "total_wealth": total_wealth,
                "invariant_diff": invariant_diff,
                "broker10_total_margin_exact": broker10_margin,
                "broker10_margin_to_production_pct": broker10_prod_pct,
                "broker10_margin_to_total_wealth_pct": broker10_total_pct,
                "official_broker10_margin_to_equity_pct": float(row["broker10_margin_to_equity_pct"]),
                "sweep_amount": sweep,
                "refill_amount": refill,
            }
        )
        if sweep > 0 or refill > 0:
            transfer_rows.append(
                {
                    "date": date,
                    "policy_id": policy.policy_id,
                    "sweep_amount": sweep,
                    "locked_add": lock_add,
                    "reserve_add": reserve_add,
                    "refill_amount": refill,
                    "production_after": production,
                    "locked_after": locked,
                    "reserve_after": reserve,
                    "total_after": total_wealth,
                }
            )

    ledger = pd.DataFrame(ledger_rows)
    ledger["total_drawdown_pct"] = _drawdown_pct(ledger["total_wealth"]).to_numpy()
    ledger["production_drawdown_pct"] = _drawdown_pct(ledger["production_equity"]).to_numpy()
    transfer_events = pd.DataFrame(transfer_rows)
    return ledger, transfer_events


def _simulate_all(official: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    ledgers = []
    transfers = []
    for policy in POLICIES:
        ledger, events = _simulate_policy(official, policy)
        ledgers.append(ledger)
        if not events.empty:
            transfers.append(events)
    transfer_frame = pd.concat(transfers, ignore_index=True) if transfers else pd.DataFrame()
    return pd.concat(ledgers, ignore_index=True), transfer_frame


def _build_policy_summary(ledger: pd.DataFrame, official_row: dict[str, Any]) -> pd.DataFrame:
    official_return = _to_float(official_row.get("total_return_pct"))
    official_dd = _to_float(official_row.get("max_dd_pct"))
    official_broker10_peak = _to_float(official_row.get("max_broker10_margin_to_equity_pct"))
    rows: list[dict[str, Any]] = []
    descriptions = {policy.policy_id: policy.description for policy in POLICIES}
    for policy_id, group in ledger.groupby("policy_id", sort=False):
        end_total = float(group["total_wealth"].iloc[-1])
        end_prod = float(group["production_equity"].iloc[-1])
        end_locked = float(group["locked_equity"].iloc[-1])
        end_reserve = float(group["reserve_equity"].iloc[-1])
        total_return = (end_total / CAPITAL - 1.0) * 100.0
        total_dd = float(group["total_drawdown_pct"].min())
        prod_dd = float(group["production_drawdown_pct"].min())
        max_diff = float(group["invariant_diff"].abs().max())
        max_prod_broker10 = float(group["broker10_margin_to_production_pct"].replace([np.inf, -np.inf], np.nan).max())
        max_total_broker10 = float(group["broker10_margin_to_total_wealth_pct"].replace([np.inf, -np.inf], np.nan).max())
        return_retention = _safe_div(total_return, official_return)
        total_dd_improvement = abs(official_dd) - abs(total_dd)
        production_safety_not_worse = int(max_prod_broker10 <= official_broker10_peak + 1e-8 and group["production_equity"].min() > 0)
        consolidated_dd_better = int(total_dd_improvement >= 5.0)
        return80 = int(return_retention >= 0.80)
        invariant_pass = int(max_diff <= 1e-6)
        candidate_ready = int(return80 and consolidated_dd_better and invariant_pass and production_safety_not_worse)
        rows.append(
            {
                "policy_id": policy_id,
                "description": descriptions.get(policy_id, ""),
                "end_total_wealth": end_total,
                "end_production_equity": end_prod,
                "end_locked_equity": end_locked,
                "end_reserve_equity": end_reserve,
                "total_return_pct": total_return,
                "return_retention": return_retention,
                "total_max_dd_pct": total_dd,
                "total_dd_improvement_pp": total_dd_improvement,
                "production_max_dd_pct": prod_dd,
                "max_broker10_to_production_pct": max_prod_broker10,
                "max_broker10_to_total_wealth_pct": max_total_broker10,
                "min_production_equity": float(group["production_equity"].min()),
                "total_swept": float(group["sweep_amount"].sum()),
                "total_refilled": float(group["refill_amount"].sum()),
                "sweep_event_count": int(group["sweep_amount"].gt(0).sum()),
                "refill_event_count": int(group["refill_amount"].gt(0).sum()),
                "total_wealth_invariant_max_abs_diff": max_diff,
                "return80_pass": return80,
                "total_dd_improvement5_pass": consolidated_dd_better,
                "invariant_pass": invariant_pass,
                "production_safety_not_worse_pass": production_safety_not_worse,
                "candidate_ready": candidate_ready,
                "decision_note": (
                    "official baseline"
                    if policy_id == "A_official_no_transfer"
                    else "pure transfer leaves consolidated wealth drawdown unchanged; no strategy candidate"
                ),
            }
        )
    return pd.DataFrame(rows)


def _build_prior_evidence(inputs: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    s017 = _row(inputs["stage017_summary"])
    s020 = inputs["stage020_summary"]
    s260 = _row(inputs["stage260_summary"])
    rows.append(
        {
            "evidence_id": "stage017_cppi_tipp",
            "state": "closed",
            "key_metric": str(s017.get("decision", "stage017_account_layer_cppi_tipp_proxy_no_candidate")),
            "reason": "CPPI/TIPP or fixed weight either barely improves drawdown or fails return retention / deployability.",
        }
    )
    if not s020.empty:
        policy = s020[s020.get("policy", pd.Series(dtype=str)).astype(str).str.contains("monthly_profit_tranche", na=False)]
        row = _row(policy) if not policy.empty else _row(s020)
        rows.append(
            {
                "evidence_id": "stage020_profit_tranche",
                "state": "closed",
                "key_metric": f"return_retention_pct={_to_float(row.get('return_retention_pct')):.4f}; total_wealth_max_dd_pct={_to_float(row.get('total_wealth_max_dd_pct')):.4f}",
                "reason": "Actual risk scaling / production account split improves total drawdown but fails 80% return retention.",
            }
        )
    rows.append(
        {
            "evidence_id": "stage260_execution_replay_gap",
            "state": "blocked_external_data",
            "key_metric": f"same_source_execution_replay_missing={_to_int(s260.get('same_source_execution_replay_missing_order_count'), 219)}/219",
            "reason": "No local same-source execution replay to support minute microstructure rule.",
        }
    )
    return pd.DataFrame(rows)


def _build_gate(policy_summary: pd.DataFrame, inputs: dict[str, Any]) -> pd.DataFrame:
    non_official = policy_summary[~policy_summary["policy_id"].eq("A_official_no_transfer")]
    non_official_safety_pass = int(non_official["production_safety_not_worse_pass"].max()) if not non_official.empty else 0
    rows = [
        {
            "gate_id": "no_official_config_or_order_side_effect",
            "required": 1,
            "observed": 1,
            "pass_now": 1,
            "reason": "Stage261 is read-only treasury accounting audit.",
        },
        {
            "gate_id": "consolidated_total_wealth_dd_improves_5pp",
            "required": 1,
            "observed": int(policy_summary["total_dd_improvement5_pass"].max()),
            "pass_now": int(policy_summary["total_dd_improvement5_pass"].max()),
            "reason": "Pure transfers do not change consolidated wealth path.",
        },
        {
            "gate_id": "return_retention_at_least_80pct",
            "required": 1,
            "observed": int(policy_summary["return80_pass"].max()),
            "pass_now": int(policy_summary["return80_pass"].max()),
            "reason": "Return is retained only because PnL path is unchanged; this does not reduce consolidated drawdown.",
        },
        {
            "gate_id": "production_safety_not_worse",
            "required": 1,
            "observed": non_official_safety_pass,
            "pass_now": non_official_safety_pass,
            "reason": "All non-official transfer policies thin the production account and worsen broker10 stress.",
        },
        {
            "gate_id": "strategy_alpha_or_signal_quality",
            "required": 1,
            "observed": 0,
            "pass_now": 0,
            "reason": "Outside-account transfers contain no minute-K or signal-quality information.",
        },
        {
            "gate_id": "stage259_local_route_reopened",
            "required": 1,
            "observed": 0,
            "pass_now": 0,
            "reason": "Stage259/260 still require external orderflow or broker replay for strategy progress.",
        },
    ]
    return pd.DataFrame(rows)


def _build_next_action(inputs: dict[str, Any]) -> pd.DataFrame:
    stage259 = inputs["stage259_next_action"].copy()
    rows: list[dict[str, Any]] = []
    if not stage259.empty:
        for _, row in stage259.iterrows():
            action_id = str(row.get("next_action_id", ""))
            rows.append(
                {
                    "rank": _to_int(row.get("rank"), len(rows) + 1),
                    "next_action_id": action_id,
                    "can_start_without_external_state": _to_int(row.get("can_start_without_external_state")),
                    "actionable_after_stage261": int(action_id in {"procure_or_capture_authorized_orderflow", "import_broker_or_production_execution_replay"}),
                    "strategy_rule_allowed_now": 0,
                    "true_engine_allowed_now": 0,
                    "stage261_judgment": (
                        "only_path_to_strategy_progress"
                        if action_id in {"procure_or_capture_authorized_orderflow", "import_broker_or_production_execution_replay"}
                        else "not_enough_for_strategy_candidate"
                    ),
                    "reason": row.get("reason", ""),
                }
            )
    rows.append(
        {
            "rank": max([row["rank"] for row in rows], default=0) + 1,
            "next_action_id": "do_not_count_pure_transfer_as_drawdown_alpha",
            "can_start_without_external_state": 1,
            "actionable_after_stage261": 1,
            "strategy_rule_allowed_now": 0,
            "true_engine_allowed_now": 0,
            "stage261_judgment": "closed_to_avoid_metric_illusion",
            "reason": "Internal transfers preserve consolidated wealth path if holdings/PnL path is unchanged.",
        }
    )
    return pd.DataFrame(rows).sort_values("rank").reset_index(drop=True)


def _build_summary(policy_summary: pd.DataFrame, gate: pd.DataFrame, inputs: dict[str, Any]) -> dict[str, Any]:
    official = _official_summary(inputs["stage251_summary"])
    non_official = policy_summary[~policy_summary["policy_id"].eq("A_official_no_transfer")]
    best_dd = non_official.sort_values("total_dd_improvement_pp", ascending=False).head(1)
    best_row = _row(best_dd)
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "line_id": LINE_ID,
        "decision": "stage261_pure_outside_account_transfer_invariant_no_alpha_no_candidate",
        "stage_nature": "read_only_outside_account_governance_boundary_audit",
        "official_config_changed": 0,
        "strategy_rule_created": 0,
        "true_engine_run": 0,
        "ab_triggered": 0,
        "order_api_called": 0,
        "ctp_or_simnow_connected": 0,
        "policy_count": int(len(policy_summary)),
        "candidate_ready_count": int(policy_summary["candidate_ready"].sum()),
        "best_nonofficial_total_dd_improvement_pp": _to_float(best_row.get("total_dd_improvement_pp")),
        "best_nonofficial_return_retention": _to_float(best_row.get("return_retention")),
        "max_total_wealth_invariant_abs_diff": _to_float(policy_summary["total_wealth_invariant_max_abs_diff"].max()),
        "pure_transfer_total_dd_changed_count": int(non_official["total_dd_improvement_pp"].abs().gt(1e-8).sum()),
        "gate_count": int(len(gate)),
        "gate_pass_count": int(gate["pass_now"].sum()),
        "official_end_equity": _to_float(official.get("end_equity")),
        "official_total_return_pct": _to_float(official.get("total_return_pct")),
        "official_max_dd_pct": _to_float(official.get("max_dd_pct")),
        "official_sharpe": _to_float(official.get("sharpe")),
        "official_total_slippage": _to_float(official.get("total_slippage")),
        "official_total_trade_count": _to_float(official.get("total_trade_count")),
        "official_win_rate_pct": _to_float(official.get("nonzero_daily_win_rate_pct")),
        "official_broker10_peak_pct": _to_float(official.get("max_broker10_margin_to_equity_pct")),
        "visual_file_count": 5,
    }


def _plot_path(ledger: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(13, 6))
    official = ledger[ledger["policy_id"].eq("A_official_no_transfer")]
    ax.plot(official["date"], official["official_equity"], color="#1f4e79", linewidth=2.0, label="official equity")
    for policy_id, group in ledger.groupby("policy_id", sort=False):
        if policy_id == "A_official_no_transfer":
            continue
        ax.plot(group["date"], group["total_wealth"], linewidth=1.0, alpha=0.65, label=policy_id[:24])
    ax.set_title("Stage261 consolidated wealth equals official path when holdings/PnL are unchanged")
    ax.set_ylabel("Consolidated wealth")
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend(fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_bucket_layers(ledger: pd.DataFrame) -> None:
    policy_id = "B_monthly_5m_half_lock60_reserve40_transfer_only"
    group = ledger[ledger["policy_id"].eq(policy_id)].copy()
    fig, ax = plt.subplots(figsize=(13, 6))
    ax.stackplot(
        group["date"],
        group["production_equity"],
        group["locked_equity"],
        group["reserve_equity"],
        labels=["production", "locked", "reserve"],
        colors=["#4c78a8", "#72b7b2", "#f58518"],
        alpha=0.85,
    )
    ax.plot(group["date"], group["official_equity"], color="#111111", linewidth=1.2, label="official/consolidated")
    ax.set_title("Stage261 bucket layers: transfer changes buckets, not consolidated wealth")
    ax.set_ylabel("Equity")
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(BUCKET_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_drawdown(ledger: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(13, 6))
    for policy_id, group in ledger.groupby("policy_id", sort=False):
        ax.plot(group["date"], group["total_drawdown_pct"], linewidth=1.2, label=policy_id[:28])
    ax.set_title("Stage261 total drawdown invariance")
    ax.set_ylabel("Total drawdown %")
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend(fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(DRAWDOWN_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_frontier(policy_summary: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(9, 6))
    colors = ["#1f4e79" if ready else "#c44e52" for ready in policy_summary["candidate_ready"]]
    ax.scatter(policy_summary["return_retention"], policy_summary["total_dd_improvement_pp"], s=90, c=colors)
    for _, row in policy_summary.iterrows():
        ax.text(row["return_retention"] + 0.002, row["total_dd_improvement_pp"] + 0.02, str(row["policy_id"]).split("_")[0], fontsize=8)
    ax.axvline(0.80, color="#666666", linestyle="--", linewidth=1)
    ax.axhline(5.0, color="#666666", linestyle="--", linewidth=1)
    ax.axhline(0.0, color="#999999", linestyle=":", linewidth=1)
    ax.set_xlabel("Return retention")
    ax.set_ylabel("Consolidated DD improvement pp")
    ax.set_title("Stage261 objective frontier: pure transfers cannot improve total drawdown")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(FRONTIER_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_gate(gate: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(10, 4.8))
    data = gate[["required", "observed", "pass_now"]].to_numpy(dtype=float)
    ax.imshow(data, aspect="auto", cmap="RdYlGn", vmin=0, vmax=max(1.0, float(np.nanmax(data))))
    ax.set_yticks(range(len(gate)))
    ax.set_yticklabels(gate["gate_id"].astype(str), fontsize=8)
    ax.set_xticks(range(3))
    ax.set_xticklabels(["required", "observed", "pass"], rotation=20, ha="right")
    for y in range(data.shape[0]):
        for x in range(data.shape[1]):
            ax.text(x, y, str(int(data[y, x])), ha="center", va="center", fontsize=8)
    ax.set_title("Stage261 invariant gate")
    fig.tight_layout()
    fig.savefig(GATE_CHART_OUT, dpi=160)
    plt.close(fig)


def _write_report(
    summary: dict[str, Any],
    policy_summary: pd.DataFrame,
    prior_evidence: pd.DataFrame,
    gate: pd.DataFrame,
    next_action: pd.DataFrame,
) -> None:
    report = f"""# Stage261 Outside Account Governance Boundary Audit

- line_id: `{LINE_ID}`
- created_at: `{summary['created_at']}`
- decision: `{summary['decision']}`
- nature: read-only treasury/accounting boundary audit. No strategy rule, no true engine, no order API, no CTP/SimNow connection.

## First-Principle Result

If official holdings and daily PnL are unchanged, moving money between production, reserve, and lockbox buckets is an internal transfer. The consolidated investor wealth is therefore identical to the official equity curve. It can change bucket optics and production-account fragility, but it cannot reduce consolidated max drawdown.

## Summary

- policy_count: `{summary['policy_count']}`
- candidate_ready_count: `{summary['candidate_ready_count']}`
- best non-official total DD improvement: `{summary['best_nonofficial_total_dd_improvement_pp']:.6f}pp`
- best non-official return retention: `{summary['best_nonofficial_return_retention']:.6f}`
- max total-wealth invariant absolute diff: `{summary['max_total_wealth_invariant_abs_diff']:.10f}`
- gate: `{summary['gate_pass_count']}/{summary['gate_count']}`

## Prior Evidence

{_md_table(prior_evidence)}

## Policy Summary

{_md_table(policy_summary)}

## Gate

{_md_table(gate)}

## Next Action

{_md_table(next_action)}

## Files

- `{SUMMARY_OUT}`
- `{POLICY_SUMMARY_OUT}`
- `{LEDGER_OUT}`
- `{TRANSFER_EVENTS_OUT}`
- `{INVARIANT_GATE_OUT}`
- `{PATH_CHART_OUT}`
- `{BUCKET_CHART_OUT}`
- `{DRAWDOWN_CHART_OUT}`
- `{FRONTIER_CHART_OUT}`
- `{GATE_CHART_OUT}`
"""
    _write_text(REPORT_OUT, report)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    inputs = _load_inputs()
    official = _official_curve(inputs["stage251_curve"])
    official_row = _official_summary(inputs["stage251_summary"])
    ledger, transfers = _simulate_all(official)
    policy_summary = _build_policy_summary(ledger, official_row)
    prior_evidence = _build_prior_evidence(inputs)
    gate = _build_gate(policy_summary, inputs)
    next_action = _build_next_action(inputs)
    summary = _build_summary(policy_summary, gate, inputs)

    _write_csv(pd.DataFrame([summary]), SUMMARY_OUT)
    _write_csv(policy_summary, POLICY_SUMMARY_OUT)
    _write_csv(ledger, LEDGER_OUT)
    _write_csv(transfers, TRANSFER_EVENTS_OUT)
    _write_csv(prior_evidence, PRIOR_EVIDENCE_OUT)
    _write_csv(gate, INVARIANT_GATE_OUT)
    _write_csv(next_action, NEXT_ACTION_OUT)
    _write_json(DECISION_OUT, summary)
    _write_report(summary, policy_summary, prior_evidence, gate, next_action)

    _plot_path(ledger)
    _plot_bucket_layers(ledger)
    _plot_drawdown(ledger)
    _plot_frontier(policy_summary)
    _plot_gate(gate)

    print(json.dumps(_json_safe(summary), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
