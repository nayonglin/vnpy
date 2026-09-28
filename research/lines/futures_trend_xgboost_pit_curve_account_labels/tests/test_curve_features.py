from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools/curve_features.py"
SPEC = importlib.util.spec_from_file_location("curve_features", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def _snapshots() -> pd.DataFrame:
    rows = []
    for product, price_shift, oi, volume in [
        ("anchor.X", 0.0, [4.0, 3.0, 2.0], [3.0, 2.0, 1.0]),
        ("candidate.X", 0.02, [6.0, 2.0, 1.0], [5.0, 3.0, 1.0]),
    ]:
        for index, maturity in enumerate(["2024-03-01", "2024-06-01", "2024-09-01"]):
            offset = [2.0, 5.0, 8.0][index] * 365.25 / 12.0
            curvature = price_shift * [0.0, 1.0, -0.5][index]
            log_price = 8.0 + price_shift - (0.001 + price_shift / 100.0) * offset + curvature
            rows.append(
                {
                    "eval_date": "2024-01-31",
                    "feature_date": "2024-01-31",
                    "product_vt_symbol": product,
                    "contract_vt_symbol": f"{product.split('.')[0]}24{[3, 6, 9][index]:02d}.X",
                    "contract_maturity": maturity,
                    "close_price": float(np.exp(log_price)),
                    "open_interest": oi[index],
                    "volume": volume[index],
                }
            )
    return pd.DataFrame(rows)


def _panel() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "eval_date": ["2024-01-31", "2024-01-31"],
            "product_vt_symbol": ["anchor.X", "candidate.X"],
            "pit_logistic_probability": [0.6, 0.4],
            "window_id": ["wf_01", "wf_01"],
            "a_rank": [10, 11],
            "role": ["a_rank10", "challenger"],
        }
    )


def test_compute_curve_descriptors_uses_full_curve_without_thresholds() -> None:
    descriptors = module.compute_curve_descriptors(_snapshots(), minimum_contracts=3)
    anchor = descriptors.set_index("product_vt_symbol").loc["anchor.X"]

    assert np.isclose(anchor["front_next_basis_annualized"], 0.365, atol=1e-10)
    assert np.isclose(anchor["full_curve_backwardation_slope"], 0.365, atol=1e-10)
    assert np.isclose(anchor["full_curve_fit_rmse"], 0.0, atol=1e-12)
    assert np.isclose(anchor["open_interest_hhi"], (16 + 9 + 4) / 81)
    assert np.isclose(anchor["volume_hhi"], (9 + 4 + 1) / 36)
    assert np.isclose(
        anchor["oi_weighted_maturity_days"],
        (4 * 2 + 3 * 5 + 2 * 8) / 9 * 365.25 / 12.0,
    )
    assert anchor["threshold_features_created"] == 0


def test_candidate_features_are_mechanical_deltas_with_exact_zero_anchor() -> None:
    descriptors = module.compute_curve_descriptors(_snapshots(), minimum_contracts=3)
    features = module.build_candidate_feature_matrix(_panel(), descriptors, anchor_rank=10)

    anchor = features.set_index("a_rank").loc[10]
    challenger = features.set_index("a_rank").loc[11]
    assert np.array_equal(anchor[module.MODEL_FEATURES].to_numpy(float), np.zeros(8))
    assert np.isclose(challenger["formal_probability_delta_vs_rank10"], -0.2)
    assert challenger["formal_rank_distance"] == 1.0
    assert challenger["open_interest_hhi_delta_vs_rank10"] > 0.0
    assert set(features["role"]) == {"a_rank10", "challenger"}


def test_feature_assessment_requires_nonzero_curve_deltas_in_each_fold() -> None:
    first_panel = _panel()
    second_panel = _panel().copy()
    second_panel["eval_date"] = "2024-02-29"
    second_panel["window_id"] = "wf_02"
    first_snapshots = _snapshots()
    second_snapshots = _snapshots().copy()
    second_snapshots["eval_date"] = "2024-02-29"
    second_snapshots["feature_date"] = "2024-02-29"
    second_snapshots["contract_maturity"] = [
        "2024-04-01",
        "2024-07-01",
        "2024-10-01",
    ] * 2
    panel = pd.concat([first_panel, second_panel], ignore_index=True)
    snapshots = pd.concat([first_snapshots, second_snapshots], ignore_index=True)
    descriptors = module.compute_curve_descriptors(snapshots, minimum_contracts=3)
    features = module.build_candidate_feature_matrix(panel, descriptors, anchor_rank=10)
    summary, diagnostics = module.assess_curve_features(
        panel,
        descriptors,
        features,
        expected_rows=4,
        expected_months=2,
        expected_anchor_rows=2,
        expected_challenger_rows=2,
        expected_folds=2,
        anchor_rank=10,
    )

    assert summary["decision"] == "stage002_curve_features_pass_ready_for_account_label_contract"
    assert summary["all_gates_passed"] is True
    assert diagnostics["challenger_unique_values"].ge(1).all()
    assert diagnostics.set_index("feature").loc[
        module.CURVE_DELTA_FEATURES, "folds_with_nonzero_challenger"
    ].eq(2).all()

    broken = features.copy()
    mask = broken["window_id"].eq("wf_02")
    broken.loc[mask, module.CURVE_DELTA_FEATURES] = 0.0
    failed, _ = module.assess_curve_features(
        panel,
        descriptors,
        broken,
        expected_rows=4,
        expected_months=2,
        expected_anchor_rows=2,
        expected_challenger_rows=2,
        expected_folds=2,
        anchor_rank=10,
    )
    assert failed["decision"] == "stage002_curve_features_fail_stop_no_labels"
    assert failed["gates"]["curve_features_nonzero_in_every_fold"] is False
