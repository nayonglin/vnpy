"""Re-run the current baseline deterministically before evaluating Stage003 C."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


LINE = Path(__file__).resolve().parents[1]
STAGE004_TOOL = LINE / "tools/stage004_fullperiod_true_engine.py"
OUT = LINE / "artifacts/stage005_current_snapshot_true_engine"
CHECKPOINT_DIR = OUT / "checkpoints"
STAGE004_OUT = LINE / "artifacts/stage004_fullperiod_true_engine"
STAGE004_A_DIR = STAGE004_OUT / "checkpoints/A"
STAGE004_DECISION = STAGE004_OUT / "decision.json"
STAGE004_CANDIDATE = STAGE004_OUT / "stage004_candidate_eligibility.csv"

EXPECTED_SHA256 = {
    "a_summary": "7539744c13d3833865572901bd774d6a77f5b1d544321e03f4310897987c1027",
    "a_curve": "3c9dda989806382d0dc4e25209e79a15a37506c96a5408806032129b4c84d616",
    "a_trades": "b72dede2e45416ca07fe038b7fef48426a45032df0b69a7aa8de52f5dfceac9a",
    "candidate": "68ac10394a6c66bb14eaf21592786c90df7d1b2c2bdef853095e082657cd75ab",
    "database": "ecbe812bd092ec8cedbd00d8b4b3ec2b1fa9311034dc8379fc6981033405eaf3",
}
SUMMARY_PAYLOAD_COLUMNS = [
    "end_equity",
    "total_return_pct",
    "max_dd_pct",
    "sharpe",
    "total_slippage",
    "total_trade_count",
    "nonzero_daily_win_rate_pct",
    "max_broker10_margin_to_equity_pct",
    "days_over_100pct",
    "account_survival_pass",
]
CURVE_PAYLOAD_COLUMNS = [
    "date",
    "account_equity",
    "nav",
    "drawdown_pct",
    "broker10_margin_to_equity_pct",
    "net_pnl",
    "trade_count",
    "total_slippage",
    "rebased_equity",
    "rebased_nav",
    "broker10_margin_to_rebased_equity_pct",
]
TRADE_IDENTITY_COLUMNS = {"profile", "variant", "experiment_arm", "arm", "label"}
FLOAT_TOLERANCE = 1e-9


def _load_stage004():
    spec = importlib.util.spec_from_file_location("stage004_for_stage005", STAGE004_TOOL)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable_to_load_stage004:{STAGE004_TOOL}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _required_columns(frame: pd.DataFrame, columns: list[str], context: str) -> None:
    missing = set(columns) - set(frame.columns)
    if missing:
        raise RuntimeError(f"{context}_columns_missing:{sorted(missing)}")


def _numeric_frame_equal(
    left: pd.DataFrame,
    right: pd.DataFrame,
    *,
    columns: list[str],
    text_columns: set[str] = frozenset(),
) -> tuple[bool, float]:
    _required_columns(left, columns, "left_payload")
    _required_columns(right, columns, "right_payload")
    if len(left) != len(right):
        return False, float("inf")
    max_error = 0.0
    for column in columns:
        a = left[column].reset_index(drop=True)
        b = right[column].reset_index(drop=True)
        if column in text_columns:
            if not a.fillna("").astype(str).equals(b.fillna("").astype(str)):
                return False, float("inf")
            continue
        a_numeric = pd.to_numeric(a, errors="coerce").to_numpy(dtype=float)
        b_numeric = pd.to_numeric(b, errors="coerce").to_numpy(dtype=float)
        if not np.array_equal(np.isnan(a_numeric), np.isnan(b_numeric)):
            return False, float("inf")
        finite = np.isfinite(a_numeric) & np.isfinite(b_numeric)
        error = (
            float(np.max(np.abs(a_numeric[finite] - b_numeric[finite])))
            if finite.any()
            else 0.0
        )
        max_error = max(max_error, error)
        if error > FLOAT_TOLERANCE:
            return False, max_error
    return True, max_error


def _trade_payload_equal(left: pd.DataFrame, right: pd.DataFrame) -> bool:
    columns = [column for column in left.columns if column not in TRADE_IDENTITY_COLUMNS]
    if set(columns) != set(right.columns) - TRADE_IDENTITY_COLUMNS or len(left) != len(right):
        return False
    for column in columns:
        a = left[column].reset_index(drop=True)
        b = right[column].reset_index(drop=True)
        if pd.api.types.is_numeric_dtype(a) and pd.api.types.is_numeric_dtype(b):
            av = pd.to_numeric(a, errors="coerce").to_numpy(dtype=float)
            bv = pd.to_numeric(b, errors="coerce").to_numpy(dtype=float)
            if not np.array_equal(np.isnan(av), np.isnan(bv)):
                return False
            finite = np.isfinite(av) & np.isfinite(bv)
            if finite.any() and float(np.max(np.abs(av[finite] - bv[finite]))) > FLOAT_TOLERANCE:
                return False
        elif not a.fillna("").astype(str).equals(b.fillna("").astype(str)):
            return False
    return True


def compare_baseline_repeat(
    reference_summary: pd.DataFrame,
    repeat_summary: pd.DataFrame,
    reference_curve: pd.DataFrame,
    repeat_curve: pd.DataFrame,
    reference_trades: pd.DataFrame,
    repeat_trades: pd.DataFrame,
) -> dict[str, Any]:
    summary_equal, summary_max_error = _numeric_frame_equal(
        reference_summary,
        repeat_summary,
        columns=SUMMARY_PAYLOAD_COLUMNS,
    )
    curve_equal, curve_max_error = _numeric_frame_equal(
        reference_curve,
        repeat_curve,
        columns=CURVE_PAYLOAD_COLUMNS,
        text_columns={"date"},
    )
    gates = {
        "summary_payload_within_1e_9": summary_equal,
        "curve_payload_exact": curve_equal,
        "trade_payload_exact": _trade_payload_equal(reference_trades, repeat_trades),
        "summary_row_count_exact": len(reference_summary) == len(repeat_summary) == 1,
        "curve_row_count_exact": len(reference_curve) == len(repeat_curve) == 2101,
        "trade_row_count_exact": len(reference_trades) == len(repeat_trades) == 798,
    }
    # Unit fixtures intentionally use shorter frames; row-count gates apply only to real payloads.
    if len(reference_curve) != 2101:
        gates["curve_row_count_exact"] = len(reference_curve) == len(repeat_curve)
    if len(reference_trades) != 798:
        gates["trade_row_count_exact"] = len(reference_trades) == len(repeat_trades)
    return {
        "passed": all(gates.values()),
        "gates": gates,
        "summary_max_abs_error": summary_max_error,
        "curve_max_abs_error": curve_max_error,
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _assert_frozen_inputs() -> None:
    paths = {
        "a_summary": STAGE004_A_DIR / "summary.csv",
        "a_curve": STAGE004_A_DIR / "curve.csv",
        "a_trades": STAGE004_A_DIR / "trades.csv",
        "candidate": STAGE004_CANDIDATE,
    }
    for name, path in paths.items():
        actual = _sha256(path)
        if actual != EXPECTED_SHA256[name]:
            raise RuntimeError(f"stage005_frozen_input_drift:{name}:{actual}")
    decision = json.loads(STAGE004_DECISION.read_text())
    if decision.get("decision") != "stage004_invalid_baseline_reproduction_stop_before_candidate":
        raise RuntimeError("stage004_decision_drift")


def _report(
    summary: pd.DataFrame,
    repeat: dict[str, Any],
    qualification: dict[str, Any],
) -> str:
    indexed = summary.set_index("experiment_arm")
    lines = [
        "# Stage005 当前线上快照A/A2与XGBoost C",
        "",
        f"- 决策：`{'PASS' if qualification['passed'] else 'FAIL'}`",
        f"- A/A2逐日逐笔确定性：`{'PASS' if repeat['passed'] else 'FAIL'}`",
        "- A使用Stage004冻结结果；A2和C为本阶段独立真引擎运行。",
        "",
        "| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 交易次数 | 胜率 | broker10峰值 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for arm, label in (("A", "A当前正式池"), ("C", "C两月确认XGBoost池")):
        row = indexed.loc[arm]
        lines.append(
            f"| {label} | {row['end_equity']:,.2f} | {row['total_return_pct']:.4f}% | "
            f"{row['max_dd_pct']:.4f}% | {row['sharpe']:.6f} | "
            f"{row['total_slippage']:,.0f} | {int(row['total_trade_count'])} | "
            f"{row['nonzero_daily_win_rate_pct']:.4f}% | "
            f"{row['max_broker10_margin_to_equity_pct']:.4f}% |"
        )
    lines.extend(["", "## 全周期门", ""])
    for name, passed in qualification["gates"].items():
        lines.append(f"- `{'PASS' if passed else 'FAIL'}` `{name}`")
    lines.extend(
        [
            "",
            "- 离线研究；未连接CTP，未调用订单API，未修改生产目录，未自动晋升。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    stage004 = _load_stage004()
    if Path.cwd().resolve() != stage004.RUNTIME_ROOT.resolve():
        raise RuntimeError(f"stage005_wrong_runtime:{Path.cwd().resolve()}")
    if os.environ.get("QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR") != "1":
        raise RuntimeError("stage005_runtime_guard_override_missing")
    _assert_frozen_inputs()
    OUT.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

    a_summary = pd.read_csv(STAGE004_A_DIR / "summary.csv")
    a_curve = pd.read_csv(STAGE004_A_DIR / "curve.csv")
    a_trades = pd.read_csv(STAGE004_A_DIR / "trades.csv")
    candidate = pd.read_csv(STAGE004_CANDIDATE)
    candidate_audit = pd.read_csv(STAGE004_OUT / "stage004_membership_audit.csv")
    stage004_predictions = pd.read_csv(stage004.STAGE003_PREDICTIONS)
    rebuilt, _ = stage004.build_candidate_eligibility(
        pd.read_csv(stage004.FORMAL_ELIGIBILITY),
        stage004_predictions,
    )
    if not rebuilt.equals(candidate):
        raise RuntimeError("stage005_candidate_rebuild_drift")

    live_cfg, s513, s827, s901 = stage004._load_production_modules()
    if live_cfg.OFFICIAL_LIVE_MATERIAL_RELEASE_ID != stage004.FORMAL_RELEASE_ID:
        raise RuntimeError("stage005_active_release_drift")
    if _sha256(stage004.RUNTIME_DATABASE) != EXPECTED_SHA256["database"]:
        raise RuntimeError("stage005_runtime_database_drift")
    if _sha256(stage004.PRODUCTION_ROOT / ".vntrader/database.db") != EXPECTED_SHA256["database"]:
        raise RuntimeError("stage005_production_database_drift")

    tracked = {
        "formal_current": stage004.FORMAL_CURRENT,
        "formal_eligibility": stage004.FORMAL_ELIGIBILITY,
        "stage003_summary": stage004.STAGE003_SUMMARY,
        "stage003_predictions": stage004.STAGE003_PREDICTIONS,
        "candidate_eligibility": STAGE004_CANDIDATE,
        "stage004_a_summary": STAGE004_A_DIR / "summary.csv",
        "stage004_a_curve": STAGE004_A_DIR / "curve.csv",
        "stage004_a_trades": STAGE004_A_DIR / "trades.csv",
        "stage005_runner": Path(__file__).resolve(),
        "production_live_config": stage004.PORTFOLIO_DIR / "qmt_roll_official_live_config.py",
        "production_strategy": stage004.PORTFOLIO_DIR / "qmt_roll_portfolio_strategy.py",
        "production_universe": stage004.PORTFOLIO_DIR / "qmt_universe.py",
        "production_database": stage004.PRODUCTION_ROOT / ".vntrader/database.db",
        "runtime_database": stage004.RUNTIME_DATABASE,
    }
    before = {name: stage004._identity(path) for name, path in tracked.items()}
    metadata = s513._metadata()
    official_builder = live_cfg.build_official_live_strategy_overrides
    stage004.CHECKPOINT_DIR = CHECKPOINT_DIR

    a2_contract = stage004._contract_sha256("A2", before)
    a2_summary, a2_curve, a2_trades = stage004._run_arm(
        "A2",
        metadata=metadata,
        s827=s827,
        s901=s901,
        override_builder=official_builder,
        contract_sha256=a2_contract,
    )
    repeat = compare_baseline_repeat(
        a_summary,
        a2_summary,
        a_curve,
        a2_curve,
        a_trades,
        a2_trades,
    )
    (OUT / "baseline_repeat.json").write_text(
        json.dumps(repeat, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )
    if not repeat["passed"]:
        decision = {
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "decision": "stage005_current_baseline_nondeterministic_stop_before_candidate",
            "baseline_repeat": repeat,
            "safety": {
                "writes_production": False,
                "ctp_connected": False,
                "order_api_called_count": 0,
            },
        }
        (OUT / "decision.json").write_text(
            json.dumps(decision, ensure_ascii=False, indent=2) + "\n"
        )
        raise RuntimeError("stage005_baseline_repeat_failed")

    def candidate_builder() -> dict[str, Any]:
        overrides = dict(official_builder())
        overrides["ai_product_pool_eligibility_path"] = str(STAGE004_CANDIDATE.resolve())
        overrides["ai_product_pool_strategy"] = stage004.OFFICIAL_STRATEGY
        return overrides

    c_contract = stage004._contract_sha256("C", before)
    c_summary, c_curve, c_trades = stage004._run_arm(
        "C",
        metadata=metadata,
        s827=s827,
        s901=s901,
        override_builder=candidate_builder,
        contract_sha256=c_contract,
    )
    c_summary["experiment_arm"] = "C"
    c_curve["experiment_arm"] = "C"
    c_trades["experiment_arm"] = "C"
    a_summary = a_summary.copy()
    a_curve = a_curve.copy()
    a_trades = a_trades.copy()
    a_summary["experiment_arm"] = "A"
    a_curve["experiment_arm"] = "A"
    a_trades["experiment_arm"] = "A"
    summary = pd.concat([a_summary, c_summary], ignore_index=True)
    curve = pd.concat([a_curve, c_curve], ignore_index=True)
    trades = pd.concat([a_trades, c_trades], ignore_index=True)
    coverage = stage004._coverage({"A": a_curve, "C": c_curve})
    after = {name: stage004._identity(path) for name, path in tracked.items()}
    identity_pass = before == after
    indexed = summary.set_index("experiment_arm")
    qualification = stage004.evaluate_fullperiod_gates(
        indexed.loc["A"],
        indexed.loc["C"],
        baseline_reproduction_pass=repeat["passed"],
        coverage_pass=coverage["passed"],
        input_identity_pass=identity_pass,
    )
    decision_name = (
        "stage005_current_snapshot_fullperiod_pass_allow_multicycle"
        if qualification["passed"]
        else "stage005_current_snapshot_fullperiod_fail_stop_candidate"
    )
    metrics = {
        arm: {
            key: float(indexed.loc[arm, key])
            for key in SUMMARY_PAYLOAD_COLUMNS
        }
        for arm in ("A", "C")
    }
    decision = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "decision": decision_name,
        "formal_release_id": stage004.FORMAL_RELEASE_ID,
        "current_snapshot": {
            "production_checkout": "1961d98ccb2b9129e35fe982b7330ae4217dcde6",
            "database_sha256": EXPECTED_SHA256["database"],
            "candidate_eligibility_sha256": EXPECTED_SHA256["candidate"],
        },
        "baseline_repeat": repeat,
        "coverage": coverage,
        "qualification": qualification,
        "metrics": metrics,
        "candidate_pool": {
            "oos_months": int(candidate_audit["source"].eq("stage003_oos").sum()),
            "mean_changed_member_count_vs_formal": float(
                candidate_audit.loc[
                    candidate_audit["source"].eq("stage003_oos"), "changed_member_count"
                ].mean()
            ),
        },
        "input_identity_pass": identity_pass,
        "identities": before,
        "safety": {
            "strategy_backtest_ran": True,
            "writes_production": False,
            "ctp_connected": False,
            "order_api_called_count": 0,
            "send_order_api_called_count": 0,
            "cancel_order_api_called_count": 0,
            "automatic_promotion": False,
        },
    }
    summary.to_csv(OUT / "summary.csv", index=False)
    curve.to_csv(OUT / "equity_curve.csv", index=False)
    trades.to_csv(OUT / "trades.csv", index=False)
    candidate_audit.to_csv(OUT / "membership_audit.csv", index=False)
    (OUT / "decision.json").write_text(
        json.dumps(decision, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )
    (OUT / "report.md").write_text(_report(summary, repeat, qualification))
    print(
        json.dumps(
            {
                "decision": decision_name,
                "baseline_repeat": repeat,
                "metrics": metrics,
                "qualification": qualification,
            },
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
