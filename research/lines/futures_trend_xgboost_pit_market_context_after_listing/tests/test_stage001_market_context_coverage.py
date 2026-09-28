from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pandas as pd


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools/stage001_market_context_coverage.py"
SPEC = importlib.util.spec_from_file_location("stage001_market_context_coverage", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_inputs(root: Path) -> tuple[dict[str, Path], dict[str, str]]:
    root.mkdir(parents=True)
    score_rows = []
    for eval_date, window_id in [("2024-01-05", "wf_01"), ("2024-02-05", "wf_02")]:
        for product, probability in zip(
            ["a.X", "b.X", "c.X", "d.X", "e.X"],
            [0.9, 0.8, 0.7, 0.6, 0.5],
            strict=True,
        ):
            score_rows.append(
                {
                    "eval_date": eval_date,
                    "product_vt_symbol": product,
                    "pit_logistic_probability": probability,
                    "window_id": window_id,
                    "future_net_pnl_60d": "must_not_be_read",
                }
            )
    oos = root / "oos.csv"
    pd.DataFrame(score_rows).to_csv(oos, index=False)

    fold = root / "fold.csv"
    pd.DataFrame(
        {
            "window_id": ["wf_01", "wf_02", "wf_rejected"],
            "accepted": [True, True, False],
            "reject_reason": ["", "", "test_rows_below_minimum"],
        }
    ).to_csv(fold, index=False)

    returns_rows = []
    for product in ["a.X", "b.X", "c.X", "d.X", "e.X"]:
        for return_date in ["2024-01-04", "2024-01-05", "2024-02-02", "2024-02-05"]:
            date = pd.Timestamp(return_date)
            returns_rows.append(
                {
                    "product_vt_symbol": product,
                    "selection_date": date - pd.Timedelta(days=1),
                    "return_date": date,
                    "selected_contract_vt": f"{product.split('.')[0]}2401.X",
                    "product_return": 0.01,
                    "status": "ok",
                    "fallback_used": False,
                    "cross_contract_price_used": False,
                }
            )
    returns = root / "returns.csv.gz"
    pd.DataFrame(returns_rows).to_csv(
        returns,
        index=False,
        compression={"method": "gzip", "mtime": 0},
    )

    stage003_manifest = root / "stage003_manifest.json"
    stage003_manifest.write_text("{}\n", encoding="utf-8")
    return_manifest = root / "return_manifest.json"
    return_manifest.write_text("{}\n", encoding="utf-8")
    spec_path = root / "spec.md"
    spec_path.write_text("frozen\n", encoding="utf-8")
    paths = {
        "oos_predictions": oos,
        "fold_audit": fold,
        "stage003_manifest": stage003_manifest,
        "product_returns": returns,
        "return_manifest": return_manifest,
        "spec": spec_path,
    }
    return paths, {name: _sha256(path) for name, path in paths.items()}


def test_stage001_reads_only_score_columns_and_publishes_deterministically(tmp_path: Path) -> None:
    paths, hashes = _write_inputs(tmp_path / "inputs")
    first_output = tmp_path / "first"
    second_output = tmp_path / "second"
    kwargs = {
        "input_paths": paths,
        "expected_sha256": hashes,
        "window_days": 2,
        "top_rank_count": 2,
        "minimum_complete_challengers": 2,
        "expected_rows": 10,
        "expected_months": 2,
        "expected_min_products": 5,
        "expected_max_products": 5,
        "expected_top_rows": 4,
        "expected_anchor_rows": 2,
        "expected_challenger_rows": 4,
        "expected_accepted_folds": 2,
        "minimum_active_months": 2,
        "minimum_active_months_by_year": {2024: 2},
        "minimum_active_months_per_fold": 1,
    }

    first = module.run_stage001(first_output, **kwargs)
    second = module.run_stage001(second_output, **kwargs)

    assert first["decision"] == "stage001_market_context_coverage_pass_ready_for_feature_preregistration"
    assert first["score_columns_read"] == [
        "eval_date",
        "product_vt_symbol",
        "pit_logistic_probability",
        "window_id",
    ]
    assert first["label_columns_read"] == []
    assert first["label_values_read"] is False
    assert first["strategy_backtest_runs"] == 0
    assert first["trains_model"] is False
    assert json.loads((first_output / "artifact_manifest.json").read_text()) == json.loads(
        (second_output / "artifact_manifest.json").read_text()
    )
    assert len(pd.read_csv(first_output / "ranked_a_panel.csv")) == 10

