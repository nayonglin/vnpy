from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pandas as pd


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools/stage003_stacked_xgboost_ranker.py"
SPEC = importlib.util.spec_from_file_location("stage003_stacked_xgboost_ranker", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_inputs(root: Path) -> tuple[dict[str, Path], dict[str, str]]:
    root.mkdir(parents=True)
    eval_dates = pd.to_datetime(
        ["2024-01-31", "2024-02-29", "2024-03-31", "2024-04-30", "2024-05-31"]
    )
    feature_rows = []
    ranked_rows = []
    label_rows = []
    for eval_date in eval_dates:
        for product, a_rank, probability, feature_value, pnl in [
            ("t1.X", 1, 0.9, None, 0.0),
            ("t2.X", 2, 0.8, None, 0.0),
            ("b.X", 3, 0.7, 0.0, -100.0),
            ("c.X", 4, 0.6, 1.0, 100.0),
            ("d.X", 5, 0.5, -1.0, 0.0),
        ]:
            ranked_rows.append(
                {
                    "eval_date": eval_date,
                    "product_vt_symbol": product,
                    "window_id": "wf_01",
                    "pit_logistic_probability": probability,
                    "a_rank": a_rank,
                    "role": "top9" if a_rank <= 2 else ("a_rank10" if a_rank == 3 else "challenger"),
                }
            )
            label_rows.append(
                {
                    "eval_date": eval_date,
                    "product_vt_symbol": product,
                    "future_net_pnl_60d": pnl,
                    "future_label_end_date": eval_date + pd.Timedelta(days=10),
                    "full_horizon_label": True,
                }
            )
            if feature_value is not None:
                row = ranked_rows[-1].copy()
                row.update({feature: feature_value for feature in module.core.FEATURE_COLUMNS})
                feature_rows.append(row)
    feature_path = root / "features.csv"
    pd.DataFrame(feature_rows).to_csv(feature_path, index=False)
    ranked_path = root / "ranked.csv"
    pd.DataFrame(ranked_rows).to_csv(ranked_path, index=False)
    labels_path = root / "labels.csv"
    labels = pd.DataFrame(label_rows)
    labels["sealed_holdout_marker"] = "must_not_be_read"
    labels.to_csv(labels_path, index=False)

    return_rows = []
    dates = pd.date_range("2024-01-01", "2024-07-31", freq="D")
    for product in ["t1.X", "t2.X", "b.X", "c.X", "d.X"]:
        value = -0.10 if product == "b.X" else 0.0
        for date in dates:
            return_rows.append(
                {
                    "product_vt_symbol": product,
                    "selection_date": date - pd.Timedelta(days=1),
                    "return_date": date,
                    "selected_contract_vt": f"{product.split('.')[0]}2401.X",
                    "product_return": value,
                    "status": "ok",
                    "fallback_used": False,
                    "cross_contract_price_used": False,
                }
            )
    returns_path = root / "returns.csv.gz"
    pd.DataFrame(return_rows).to_csv(
        returns_path,
        index=False,
        compression={"method": "gzip", "mtime": 0},
    )
    stage002_manifest = root / "stage002_manifest.json"
    stage002_manifest.write_text("{}\n", encoding="utf-8")
    return_manifest = root / "return_manifest.json"
    return_manifest.write_text("{}\n", encoding="utf-8")
    spec_path = root / "spec.md"
    spec_path.write_text("frozen\n", encoding="utf-8")
    core_path = root / "core.py"
    core_path.write_text("frozen\n", encoding="utf-8")
    paths = {
        "feature_panel": feature_path,
        "stage002_manifest": stage002_manifest,
        "ranked_a_panel": ranked_path,
        "conditional_samples": labels_path,
        "product_returns": returns_path,
        "return_manifest": return_manifest,
        "spec": spec_path,
        "ranker_core": core_path,
    }
    return paths, {name: _sha256(path) for name, path in paths.items()}


def test_stage003_runs_real_ranker_twice_and_publishes_no_backtest_result(tmp_path: Path) -> None:
    paths, hashes = _write_inputs(tmp_path / "inputs")
    output = tmp_path / "output"

    summary = module.run_stage003(
        output,
        input_paths=paths,
        expected_sha256=hashes,
        top_rank_count=2,
        minimum_train_months=2,
        minimum_train_rows=6,
        expected_feature_rows=15,
        expected_feature_months=5,
        expected_min_test_months=3,
        minimum_test_months_by_year={2024: 3},
        minimum_replacement_months=1,
        future_market_horizon=3,
        expected_fold_count=1,
        model_params={
            **module.core.RANKER_PARAMS,
            "min_child_weight": 0.0,
            "reg_alpha": 0.0,
            "reg_lambda": 1.0,
        },
    )

    assert summary["decision"] == "stage003_stacked_ranker_pass_allow_engine_preregistration"
    assert summary["test_months"] == 3
    assert summary["xgboost_training_runs"] == 6
    assert summary["repeat_prediction_max_abs_diff"] == 0.0
    assert summary["repeat_dump_sha_match"] is True
    assert summary["label_columns_read"] == [
        "eval_date",
        "product_vt_symbol",
        "future_net_pnl_60d",
        "future_label_end_date",
        "full_horizon_label",
    ]
    assert summary["strategy_backtest_runs"] == 0
    assert json.loads((output / "artifact_manifest.json").read_text())["oos_predictions.csv"]
