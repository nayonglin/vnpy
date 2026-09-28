from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import stage001_v2_contract_requalification as stage001


def _liquidity_fixture() -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = pd.bdate_range("2024-01-02", periods=60)
    rows: list[dict[str, object]] = []
    patterns = {
        "only20.EX": [1.0] * 40 + [0.0] * 3 + [1.0] * 17,
        "only60.EX": [0.0] * 7 + [1.0] * 53,
        "both.EX": [0.0] * 4 + [1.0] * 36 + [0.0] * 3 + [1.0] * 17,
        "pass.EX": [1.0] * 60,
    }
    for product, values in patterns.items():
        for date, value in zip(dates, values, strict=True):
            rows.append(
                {
                    "date": date,
                    "product_vt_symbol": product,
                    "volume": value,
                    "open_interest": 1.0,
                }
            )
    base = pd.DataFrame(
        {
            "query_date": [dates[-1]] * len(patterns),
            "product_vt_symbol": list(patterns),
        }
    )
    return pd.DataFrame(rows), base


def test_liquidity_diagnostics_use_union_not_long_window_count() -> None:
    history, base = _liquidity_fixture()

    result = stage001.compute_liquidity_coverage_diagnostics(history, base)

    assert result["volume"] == {
        "fail_20": 2,
        "fail_60": 2,
        "only_20": 1,
        "only_60": 1,
        "both": 1,
        "union": 3,
    }
    assert result["open_interest"]["union"] == 0


def _corrected_contract() -> dict[str, object]:
    return {
        "all_gates_passed": True,
        "decision": stage001.UPSTREAM_CORRECTED_PASS_DECISION,
        "future_close_value_reads": 0,
        "future_return_calculations": 0,
        "label_value_reads": 0,
        "model_fit_count": 0,
        "model_predict_count": 0,
        "strategy_backtest_runs": 0,
        "ctp_connection_count": 0,
        "order_api_called_count": 0,
        "production_files_written": 0,
    }


def _frozen_diagnostics() -> dict[str, dict[str, int]]:
    return {
        "volume": {
            "fail_20": 273,
            "fail_60": 420,
            "only_20": 40,
            "only_60": 187,
            "both": 233,
            "union": 460,
        },
        "open_interest": {
            "fail_20": 21,
            "fail_60": 80,
            "only_20": 0,
            "only_60": 59,
            "both": 21,
            "union": 80,
        },
    }


def test_v2_assessment_passes_only_corrected_manifested_zero_effect_contract() -> None:
    result = stage001.assess_v2_contract(
        _corrected_contract(),
        _frozen_diagnostics(),
        upstream_verified=True,
        input_identity_stable=True,
    )

    assert result["all_gates_passed"] is True
    assert result["decision"] == stage001.PASS_DECISION


def test_v2_assessment_rejects_old_420_union() -> None:
    diagnostics = _frozen_diagnostics()
    diagnostics["volume"]["union"] = 420

    result = stage001.assess_v2_contract(
        _corrected_contract(),
        diagnostics,
        upstream_verified=True,
        input_identity_stable=True,
    )

    assert result["all_gates_passed"] is False
    assert result["gates"]["liquidity_union_gate"] is False
    assert result["decision"] == stage001.FAIL_DECISION
