from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools/curve_coverage.py"
SPEC = importlib.util.spec_from_file_location("curve_coverage", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def _panel() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "eval_date": ["2024-01-31", "2024-01-31"],
            "product_vt_symbol": ["MA.CZCE", "rb.SHFE"],
            "pit_logistic_probability": [0.8, 0.7],
            "window_id": ["wf_01", "wf_01"],
            "a_rank": [1, 2],
            "role": ["top9", "a_rank10"],
        }
    )


def _bars(*, omit: tuple[str, str] | None = None) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    contracts = {
        "MA.CZCE": [("MA403", "CZCE", 2400.0), ("MA405", "CZCE", 2420.0), ("MA409", "CZCE", 2450.0)],
        "rb.SHFE": [("rb2403", "SHFE", 3800.0), ("rb2405", "SHFE", 3820.0), ("rb2410", "SHFE", 3860.0)],
    }
    for product, items in contracts.items():
        for index, (symbol, exchange, close) in enumerate(items):
            if omit == (product, symbol):
                continue
            rows.append(
                {
                    "symbol": symbol,
                    "exchange": exchange,
                    "datetime": "2024-01-31 00:00:00",
                    "interval": "d",
                    "close_price": close,
                    "open_interest": 1000.0 - index * 100,
                    "volume": 500.0 - index * 50,
                }
            )
    rows.extend(
        [
            {
                "symbol": "MA888",
                "exchange": "CZCE",
                "datetime": "2024-01-31 00:00:00",
                "interval": "d",
                "close_price": 2500.0,
                "open_interest": 999999.0,
                "volume": 999999.0,
            },
            {
                "symbol": "rb9999",
                "exchange": "SHFE",
                "datetime": "2024-01-31 00:00:00",
                "interval": "d",
                "close_price": 3900.0,
                "open_interest": 999999.0,
                "volume": 999999.0,
            },
            {
                "symbol": "rb2501",
                "exchange": "SHFE",
                "datetime": "2024-02-01 00:00:00",
                "interval": "d",
                "close_price": 3900.0,
                "open_interest": 100.0,
                "volume": 100.0,
            },
        ]
    )
    return pd.DataFrame(rows)


def test_infer_delivery_month_handles_czce_decade_and_rejects_synthetic() -> None:
    assert module.infer_delivery_month("MA905", "CZCE", "2019-01-31") == pd.Timestamp("2019-05-01")
    assert module.infer_delivery_month("FG101", "CZCE", "2020-12-31") == pd.Timestamp("2021-01-01")
    assert module.infer_delivery_month("MA601", "CZCE", "2025-11-28") == pd.Timestamp("2026-01-01")
    assert module.infer_delivery_month("rb2410", "SHFE", "2024-01-31") == pd.Timestamp("2024-10-01")
    assert pd.isna(module.infer_delivery_month("MA888", "CZCE", "2024-01-31"))
    assert pd.isna(module.infer_delivery_month("rb9999", "SHFE", "2024-01-31"))
    assert pd.isna(module.infer_delivery_month("rb401", "SHFE", "2024-01-31"))


def test_build_exact_curve_snapshots_excludes_synthetic_and_future_dates() -> None:
    panel = module.normalise_ranked_panel(_panel())
    snapshots, rejected = module.build_exact_curve_snapshots(panel, _bars())

    assert len(snapshots) == 6
    assert set(snapshots["contract_vt_symbol"]) == {
        "MA403.CZCE",
        "MA405.CZCE",
        "MA409.CZCE",
        "rb2403.SHFE",
        "rb2405.SHFE",
        "rb2410.SHFE",
    }
    assert snapshots["feature_date"].eq(pd.Timestamp("2024-01-31")).all()
    assert snapshots.groupby(["eval_date", "product_vt_symbol"])["contract_maturity"].nunique().eq(3).all()
    assert rejected["reason"].value_counts().to_dict() == {"synthetic_contract": 2}
    assert not snapshots["contract_vt_symbol"].eq("rb2501.SHFE").any()


def test_audit_requires_three_contracts_without_fallback() -> None:
    panel = module.normalise_ranked_panel(_panel())
    snapshots, rejected = module.build_exact_curve_snapshots(
        panel,
        _bars(omit=("rb.SHFE", "rb2410")),
    )
    coverage = module.audit_curve_coverage(panel, snapshots, minimum_contracts=3)
    summary = module.assess_curve_coverage(
        panel,
        snapshots,
        rejected,
        coverage,
        expected_rows=2,
        expected_months=1,
        expected_products=2,
        minimum_contracts=3,
    )

    rb = coverage.set_index("product_vt_symbol").loc["rb.SHFE"]
    assert rb["eligible_contract_count"] == 2
    assert bool(rb["curve_complete"]) is False
    assert rb["status"] == "eligible_contract_count_below_minimum"
    assert summary["decision"] == "stage001_curve_coverage_fail_stop_no_labels"
    assert summary["fallback_rows"] == 0


def test_assessment_passes_only_on_complete_exact_same_day_panel() -> None:
    panel = module.normalise_ranked_panel(_panel())
    snapshots, rejected = module.build_exact_curve_snapshots(panel, _bars())
    coverage = module.audit_curve_coverage(panel, snapshots, minimum_contracts=3)
    summary = module.assess_curve_coverage(
        panel,
        snapshots,
        rejected,
        coverage,
        expected_rows=2,
        expected_months=1,
        expected_products=2,
        minimum_contracts=3,
    )

    assert summary["decision"] == "stage001_curve_coverage_pass_ready_for_feature_preregistration"
    assert summary["all_gates_passed"] is True
    assert summary["complete_rows"] == 2
    assert summary["minimum_eligible_contracts"] == 3
    assert summary["pit_violation_rows"] == 0
    assert summary["future_label_rows_read"] == 0


def test_duplicate_delivery_month_fails_closed() -> None:
    bars = _bars()
    duplicate = bars.iloc[[0]].copy()
    duplicate.loc[:, "symbol"] = "MA2403"
    bars = pd.concat([bars, duplicate], ignore_index=True)
    panel = module.normalise_ranked_panel(_panel())

    with pytest.raises(module.CurveCoverageError, match="delivery_month_duplicate"):
        module.build_exact_curve_snapshots(panel, bars)
