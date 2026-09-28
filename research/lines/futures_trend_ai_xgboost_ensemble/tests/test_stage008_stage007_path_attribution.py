from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools/stage008_stage007_path_attribution.py"


def load_module():
    spec = importlib.util.spec_from_file_location("stage008_stage007_path_attribution", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_future_account_paths_exclude_eval_day_and_compound_next_days() -> None:
    module = load_module()
    dates = pd.date_range("2026-01-01", periods=5, freq="D")
    curves = pd.DataFrame(
        {
            "date": list(dates) * 2,
            "experiment_arm": ["A1"] * 5 + ["C"] * 5,
            "account_equity": [100, 110, 99, 108, 120, 100, 90, 99, 88, 95],
        }
    )

    result = module.future_account_paths(
        curves,
        pd.DatetimeIndex([dates[0]]),
        horizon=3,
    ).set_index("experiment_arm")

    assert abs(result.loc["A1", "future_return"] - 0.08) < 1e-12
    assert abs(result.loc["A1", "future_max_drawdown"] - (-0.10)) < 1e-12
    assert abs(result.loc["C", "future_return"] - (-0.12)) < 1e-12
    assert abs(result.loc["C", "future_max_drawdown"] - (-0.12)) < 1e-12


def test_drawdown_episode_reports_peak_trough_and_first_recovery() -> None:
    module = load_module()
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=6, freq="D"),
            "account_equity": [100, 120, 90, 80, 110, 121],
        }
    )

    result = module.drawdown_episode(frame)

    assert result["peak_date"] == "2026-01-02"
    assert result["trough_date"] == "2026-01-04"
    assert result["recovery_date"] == "2026-01-06"
    assert abs(result["max_drawdown"] - (80 / 120 - 1)) < 1e-12


def test_trade_overlap_uses_payload_multiset_and_ignores_ids() -> None:
    module = load_module()
    columns = {
        "datetime": ["2026-01-01", "2026-01-02"],
        "vt_symbol": ["au2606.SHFE", "rb2605.SHFE"],
        "direction": ["Long", "Short"],
        "offset": ["Open", "Close"],
        "price": [100.0, 200.0],
        "volume": [1.0, 2.0],
        "exit_reason": ["", "stop"],
    }
    a = pd.DataFrame({"trade_id": ["a1", "a2"], **columns})
    c = pd.DataFrame(
        {
            "trade_id": ["c1", "c3"],
            **{key: [value[0], value[0]] for key, value in columns.items()},
        }
    )

    result = module.trade_multiset_overlap(a, c)

    assert result["a_trades"] == result["c_trades"] == 2
    assert result["common_trades"] == 1
    assert result["a_only_trades"] == result["c_only_trades"] == 1


def test_contract_symbol_maps_to_product_vt_symbol() -> None:
    module = load_module()

    assert module.contract_to_product("au1806.SHFE") == "au.SHFE"
    assert module.contract_to_product("AP205.CZCE") == "AP.CZCE"


def test_formal_proxy_membership_audit_detects_nonidentical_baseline_pool() -> None:
    module = load_module()
    formal = pd.DataFrame(
        {
            "eval_date": ["2026-01-30"] * 3,
            "product_vt_symbol": ["a.X", "b.X", "fu.SHFE"],
            "score_rank": [1, 2, 3],
        }
    )
    predictions = pd.DataFrame(
        {
            "eval_date": ["2026-01-30"] * 3,
            "product_vt_symbol": ["a.X", "b.X", "c.X"],
            "score_logistic": [3.0, 1.0, 2.0],
            "score_two_month_confirmed": [1.0, 3.0, 2.0],
        }
    )

    result = module.formal_proxy_membership_audit(formal, predictions, top_n=2).iloc[0]

    assert result["formal_vs_proxy_a_swap_count"] == 1
    assert result["formal_vs_c3_swap_count"] == 1
    assert bool(result["formal_equals_proxy_a"]) is False
