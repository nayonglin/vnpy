from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools/pit_contract_returns.py"
SPEC = importlib.util.spec_from_file_location("pit_contract_returns", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def _bars(rows: list[tuple[object, ...]]) -> pd.DataFrame:
    return pd.DataFrame(
        rows,
        columns=[
            "datetime",
            "symbol",
            "exchange",
            "close_price",
            "open_interest",
            "volume",
        ],
    )


def test_contract_match_rejects_continuous_and_option_symbols() -> None:
    products = ["rb.SHFE", "AP.CZCE", "lc.GFEX"]

    assert module.match_contract_to_product("rb2501", "SHFE", products) == "rb.SHFE"
    assert module.match_contract_to_product("AP501", "CZCE", products) == "AP.CZCE"
    assert module.match_contract_to_product("lc2501", "GFEX", products) == "lc.GFEX"
    assert module.match_contract_to_product("rb8888", "SHFE", products) is None
    assert module.match_contract_to_product("rb99", "SHFE", products) is None
    assert module.match_contract_to_product("rb2513", "SHFE", products) is None
    assert module.match_contract_to_product("rb2501C3500", "SHFE", products) is None


def test_return_day_uses_previous_day_oi_and_same_contract_close() -> None:
    bars = _bars(
        [
            ("2024-01-02", "rb2405", "SHFE", 100.0, 100.0, 10.0),
            ("2024-01-02", "rb2410", "SHFE", 200.0, 90.0, 100.0),
            ("2024-01-03", "rb2405", "SHFE", 110.0, 1.0, 10.0),
            ("2024-01-03", "rb2410", "SHFE", 220.0, 1000.0, 100.0),
            ("2024-01-04", "rb2405", "SHFE", 111.0, 1.0, 10.0),
            ("2024-01-04", "rb2410", "SHFE", 242.0, 1000.0, 100.0),
        ]
    )

    result = module.build_lagged_oi_returns(bars, ["rb.SHFE"])

    assert result["selected_contract_vt"].tolist() == ["rb2405.SHFE", "rb2410.SHFE"]
    assert result["selection_date"].dt.strftime("%Y-%m-%d").tolist() == [
        "2024-01-02",
        "2024-01-03",
    ]
    assert result["return_date"].dt.strftime("%Y-%m-%d").tolist() == [
        "2024-01-03",
        "2024-01-04",
    ]
    assert np.allclose(result["product_return"], [0.10, 0.10])
    assert result["status"].tolist() == ["ok", "ok"]
    assert not result["fallback_used"].any()
    assert not result["cross_contract_price_used"].any()


def test_selection_tie_breaks_on_lagged_volume_then_contract_name() -> None:
    bars = _bars(
        [
            ("2024-01-02", "rb2405", "SHFE", 100.0, 100.0, 10.0),
            ("2024-01-02", "rb2410", "SHFE", 200.0, 100.0, 20.0),
            ("2024-01-03", "rb2405", "SHFE", 101.0, 100.0, 10.0),
            ("2024-01-03", "rb2410", "SHFE", 202.0, 100.0, 20.0),
        ]
    )

    result = module.build_lagged_oi_returns(bars, ["rb.SHFE"])

    assert result.loc[0, "selected_contract_vt"] == "rb2410.SHFE"
    assert result.loc[0, "selection_open_interest"] == 100.0
    assert result.loc[0, "selection_volume"] == 20.0


def test_missing_selected_contract_close_does_not_fallback() -> None:
    bars = _bars(
        [
            ("2024-01-02", "rb2405", "SHFE", 100.0, 100.0, 10.0),
            ("2024-01-02", "rb2410", "SHFE", 200.0, 90.0, 100.0),
            ("2024-01-03", "rb2410", "SHFE", 220.0, 1000.0, 100.0),
        ]
    )

    result = module.build_lagged_oi_returns(bars, ["rb.SHFE"])

    assert len(result) == 1
    assert result.loc[0, "selected_contract_vt"] == "rb2405.SHFE"
    assert result.loc[0, "status"] == "selected_contract_close_missing"
    assert np.isnan(result.loc[0, "product_return"])
    assert not bool(result.loc[0, "fallback_used"])


def _formal_ranking() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "eval_date": ["2024-01-05"] * 3,
            "product_vt_symbol": ["a.X", "b.X", "c.X"],
            "score_rank": [1, 2, 3],
        }
    )


def _base_panel() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "eval_date": ["2024-01-05"],
            "product_vt_symbol": ["c.X"],
            "score_rank": [3],
            "split": ["development"],
        }
    )


def _returns(*, missing_candidate_date: str | None = None) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for product in ["a.X", "b.X", "c.X"]:
        for index, date in enumerate(["2024-01-03", "2024-01-04", "2024-01-05"]):
            missing = product == "c.X" and date == missing_candidate_date
            rows.append(
                {
                    "product_vt_symbol": product,
                    "selection_date": pd.Timestamp(date) - pd.Timedelta(days=1),
                    "return_date": pd.Timestamp(date),
                    "selected_contract_vt": f"{product.split('.')[0]}2401.X",
                    "product_return": np.nan if missing else 0.01 * (index + 1),
                    "status": "selected_contract_close_missing" if missing else "ok",
                    "fallback_used": False,
                    "cross_contract_price_used": False,
                }
            )
    rows.append(
        {
            "product_vt_symbol": "c.X",
            "selection_date": pd.Timestamp("2024-01-05"),
            "return_date": pd.Timestamp("2024-01-06"),
            "selected_contract_vt": "c2401.X",
            "product_return": 9.99,
            "status": "ok",
            "fallback_used": False,
            "cross_contract_price_used": False,
        }
    )
    return pd.DataFrame(rows)


def test_window_coverage_uses_only_dates_not_after_eval_date() -> None:
    coverage, missing, audit = module.audit_feature_windows(
        _base_panel(),
        _formal_ranking(),
        _returns(),
        window_days=3,
        top_rank_count=2,
    )

    assert missing.empty
    assert set(coverage["valid_return_count"]) == {3}
    assert audit.loc[0, "window_end"] == pd.Timestamp("2024-01-05")
    assert audit.loc[0, "future_return_rows_used"] == 0
    assert audit.loc[0, "candidate_windows_complete"] == 1
    assert audit.loc[0, "top_windows_complete"] == 2


def test_window_coverage_exposes_missing_candidate_cell() -> None:
    coverage, missing, audit = module.audit_feature_windows(
        _base_panel(),
        _formal_ranking(),
        _returns(missing_candidate_date="2024-01-04"),
        window_days=3,
        top_rank_count=2,
    )

    candidate = coverage[coverage["product_vt_symbol"].eq("c.X")].iloc[0]
    assert candidate["valid_return_count"] == 2
    assert candidate["required_return_count"] == 3
    assert missing[["eval_date", "return_date", "product_vt_symbol", "role"]].to_dict("records") == [
        {
            "eval_date": pd.Timestamp("2024-01-05"),
            "return_date": pd.Timestamp("2024-01-04"),
            "product_vt_symbol": "c.X",
            "role": "candidate",
        }
    ]
    assert audit.loc[0, "candidate_windows_complete"] == 0


def test_coverage_decision_fails_closed_on_any_missing_or_pit_violation() -> None:
    coverage, missing, audit = module.audit_feature_windows(
        _base_panel(),
        _formal_ranking(),
        _returns(missing_candidate_date="2024-01-04"),
        window_days=3,
        top_rank_count=2,
    )
    summary = module.assess_coverage(
        coverage,
        missing,
        audit,
        _returns(missing_candidate_date="2024-01-04"),
        expected_candidate_rows=1,
        window_days=3,
    )

    assert summary["decision"] == "stage001_pit_contract_return_coverage_fail_stop_no_features"
    assert summary["missing_required_cells"] == 1
    assert summary["complete_candidate_windows"] == 0
    assert summary["all_gates_passed"] is False


def test_coverage_decision_passes_only_complete_panel() -> None:
    returns = _returns()
    coverage, missing, audit = module.audit_feature_windows(
        _base_panel(),
        _formal_ranking(),
        returns,
        window_days=3,
        top_rank_count=2,
    )
    summary = module.assess_coverage(
        coverage,
        missing,
        audit,
        returns,
        expected_candidate_rows=1,
        window_days=3,
    )

    assert summary["decision"] == "stage001_pit_contract_return_coverage_pass_ready_for_feature_design"
    assert summary["all_gates_passed"] is True
    assert summary["complete_candidate_windows"] == 1
    assert summary["complete_top_windows"] == 2
