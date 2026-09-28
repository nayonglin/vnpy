from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pandas as pd


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "tools/stage003_feature_contract_fix.py"
)
SPEC = importlib.util.spec_from_file_location("stage003_feature_contract_fix", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
stage003 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = stage003
SPEC.loader.exec_module(stage003)


def test_freeze_raw_feature_contract_ignores_derived_pit_labels() -> None:
    raw = pd.DataFrame(columns=["a_sum_20d", "b_mean_60d"])
    conditional = pd.DataFrame(
        columns=[
            "a_sum_20d",
            "b_mean_60d",
            "pit_future_rank_centered_60d",
            "pit_target_future_top_half_60d",
        ]
    )

    features = stage003.freeze_raw_feature_contract(
        raw, conditional, expected_count=2
    )

    assert features == ["a_sum_20d", "b_mean_60d"]

