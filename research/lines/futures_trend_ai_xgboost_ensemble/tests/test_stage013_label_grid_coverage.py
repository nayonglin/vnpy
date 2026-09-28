from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools/stage013_label_grid_coverage.py"


def load_module():
    assert MODULE_PATH.exists(), "Stage013 label-grid coverage tool is not implemented"
    spec = importlib.util.spec_from_file_location("stage013_label_grid_coverage", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sample_panel() -> pd.DataFrame:
    rows = []
    for eval_date in ("2022-01-31", "2022-02-28"):
        for rank in range(10, 19):
            rows.append(
                {
                    "eval_date": eval_date,
                    "next_eval_date": "2022-03-31",
                    "score_rank": rank,
                    "product_vt_symbol": f"p{rank}.TEST",
                    "t18_open_trade_count": int(
                        (eval_date == "2022-01-31" and rank in {10, 12})
                        or (eval_date == "2022-02-28" and rank == 13)
                    ),
                }
            )
    return pd.DataFrame(rows)


def test_full_grid_never_prunes_on_future_activity() -> None:
    module = load_module()
    plan = module.build_full_grid_label_plan(sample_panel())

    assert len(plan) == 18
    assert plan["label_run_required"].all()
    assert not plan["future_activity_used_for_pruning"].any()
    assert plan.groupby("eval_date")["score_rank"].apply(list).tolist() == [
        list(range(10, 19)),
        list(range(10, 19)),
    ]


def test_coverage_reports_activity_without_treating_it_as_label() -> None:
    module = load_module()
    summary = module.summarize_coverage(sample_panel())

    assert summary["months"] == 2
    assert summary["full_grid_runs"] == 18
    assert summary["rank10_active_months"] == 1
    assert summary["active_challenger_rows"] == 2
    assert summary["months_with_active_challenger"] == 2
    assert summary["months_with_two_active_challengers"] == 0


def test_rejects_incomplete_month_rank_shape() -> None:
    module = load_module()
    malformed = sample_panel().iloc[:-1].copy()

    with pytest.raises(RuntimeError, match="month_rank_shape"):
        module.build_full_grid_label_plan(malformed)

