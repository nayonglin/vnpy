from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools/stage014_prelabel_feature_contract.py"


def load_module():
    assert MODULE_PATH.exists(), "Stage014 prelabel feature contract is not implemented"
    spec = importlib.util.spec_from_file_location("stage014_prelabel_feature_contract", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_feature_contract_is_fixed_and_low_dimensional() -> None:
    module = load_module()

    assert module.MODEL_FEATURE_COLUMNS == [
        "formal_probability_delta_vs_rank10",
        "formal_rank_distance",
        "pnl120_z_delta_vs_rank10",
        "pnl60_z_delta_vs_rank10",
        "sharpe60_z_delta_vs_rank10",
        "positive_day60_z_delta_vs_rank10",
        "opened60_z_delta_vs_rank10",
        "slippage60_z_delta_vs_rank10",
        "drawdown60_z_delta_vs_rank10",
    ]
    assert len(module.MODEL_FEATURE_COLUMNS) == 9


def test_pairwise_features_are_deltas_from_rank10() -> None:
    module = load_module()
    rows = []
    for rank, probability in ((10, 0.7), (11, 0.5), (12, 0.2)):
        row = {
            "eval_date": "2022-01-31",
            "product_vt_symbol": f"p{rank}.TEST",
            "score_rank": rank,
            "score": probability,
            "score_type": "ai_probability_top19_plus_fixed_fu",
        }
        for index, source in enumerate(module.STRUCTURAL_SOURCE_COLUMNS, start=1):
            row[source] = float(rank * index)
        rows.append(row)

    result = module.build_pairwise_feature_panel(pd.DataFrame(rows))
    baseline = result[result["score_rank"].eq(10)].iloc[0]
    challenger = result[result["score_rank"].eq(12)].iloc[0]

    assert all(float(baseline[column]) == 0.0 for column in module.MODEL_FEATURE_COLUMNS)
    assert np.isclose(challenger["formal_probability_delta_vs_rank10"], -0.5)
    assert challenger["formal_rank_distance"] == 2.0
    assert challenger["pnl120_z_delta_vs_rank10"] > 0.0


def test_membership_locked_probability_is_missing_not_reinterpreted() -> None:
    module = load_module()
    rows = []
    for rank in (10, 11):
        row = {
            "eval_date": "2026-04-30",
            "product_vt_symbol": f"p{rank}.TEST",
            "score_rank": rank,
            "score": 0.5,
            "score_type": "membership_locked_top19_plus_fixed_fu",
        }
        row.update({column: float(rank) for column in module.STRUCTURAL_SOURCE_COLUMNS})
        rows.append(row)

    result = module.build_pairwise_feature_panel(pd.DataFrame(rows))

    assert result["formal_probability_delta_vs_rank10"].isna().all()


def test_last_twelve_months_are_sealed_holdout() -> None:
    module = load_module()
    dates = pd.date_range("2022-01-31", periods=20, freq="ME")

    split = module.build_month_split(dates, holdout_months=12)

    assert (split["split"] == "development").sum() == 8
    assert (split["split"] == "sealed_holdout").sum() == 12
    assert split.loc[split["split"].eq("sealed_holdout"), "label_values_read_allowed"].eq(False).all()

