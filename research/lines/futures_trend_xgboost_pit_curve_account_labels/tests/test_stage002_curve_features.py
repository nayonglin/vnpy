from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools/stage002_curve_features.py"
SPEC = importlib.util.spec_from_file_location("stage002_curve_features", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_inputs(root: Path) -> tuple[dict[str, Path], dict[str, str]]:
    root.mkdir(parents=True)
    panel_rows = []
    snapshot_rows = []
    coverage_rows = []
    for month_index, (eval_date, window_id) in enumerate(
        [("2024-01-31", "wf_01"), ("2024-02-29", "wf_02")]
    ):
        products = ["top.X", "anchor.X", "candidate.X"]
        for rank, product in enumerate(products, start=1):
            panel_rows.append(
                {
                    "eval_date": eval_date,
                    "product_vt_symbol": product,
                    "pit_logistic_probability": 0.9 - rank * 0.1,
                    "window_id": window_id,
                    "a_rank": rank,
                    "role": "top9" if rank == 1 else ("a_rank10" if rank == 2 else "challenger"),
                    "future_label": "must_not_be_read",
                }
            )
            coverage_rows.append(
                {
                    "eval_date": eval_date,
                    "product_vt_symbol": product,
                    "curve_complete": True,
                }
            )
            for contract_index, maturity_month in enumerate([3, 6, 9]):
                maturity = pd.Timestamp(2024, maturity_month + month_index, 1)
                offset = (maturity.year * 12 + maturity.month) - (
                    pd.Timestamp(eval_date).year * 12 + pd.Timestamp(eval_date).month
                )
                product_shift = {"top.X": 0.0, "anchor.X": 0.01, "candidate.X": 0.03}[product]
                curvature = product_shift * [0.0, 1.0, -0.5][contract_index]
                log_price = (
                    8.0
                    + product_shift
                    - (0.001 + product_shift / 100) * offset * 365.25 / 12
                    + curvature
                )
                snapshot_rows.append(
                    {
                        "eval_date": eval_date,
                        "feature_date": eval_date,
                        "product_vt_symbol": product,
                        "contract_vt_symbol": f"{product.split('.')[0]}{maturity:%y%m}.X",
                        "contract_maturity": maturity,
                        "close_price": float(np.exp(log_price)),
                        "open_interest": [10.0, 7.0, 4.0][contract_index] + rank,
                        "volume": [8.0, 5.0, 2.0][contract_index] + rank,
                    }
                )
    panel = root / "ranked.csv"
    pd.DataFrame(panel_rows).to_csv(panel, index=False)
    snapshots = root / "snapshots.csv.gz"
    pd.DataFrame(snapshot_rows).to_csv(
        snapshots, index=False, compression={"method": "gzip", "mtime": 0}
    )
    coverage = root / "coverage.csv"
    pd.DataFrame(coverage_rows).to_csv(coverage, index=False)
    stage001_summary = root / "stage001_summary.json"
    stage001_summary.write_text(
        json.dumps(
            {
                "decision": "stage001_curve_coverage_pass_ready_for_feature_preregistration",
                "all_gates_passed": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    stage001_manifest = root / "stage001_manifest.json"
    stage001_manifest.write_text("{}\n", encoding="utf-8")
    spec = root / "spec.md"
    spec.write_text("frozen\n", encoding="utf-8")
    paths = {
        "ranked_panel": panel,
        "curve_snapshot": snapshots,
        "coverage": coverage,
        "stage001_summary": stage001_summary,
        "stage001_manifest": stage001_manifest,
        "spec": spec,
    }
    return paths, {name: _sha256(path) for name, path in paths.items()}


def test_stage002_publishes_deterministic_label_free_features(tmp_path: Path) -> None:
    paths, hashes = _write_inputs(tmp_path / "inputs")
    kwargs = {
        "input_paths": paths,
        "expected_sha256": hashes,
        "expected_rows": 4,
        "expected_months": 2,
        "expected_anchor_rows": 2,
        "expected_challenger_rows": 2,
        "expected_folds": 2,
        "minimum_contracts": 3,
        "anchor_rank": 2,
    }
    first = module.run_stage002(tmp_path / "first", **kwargs)
    second = module.run_stage002(tmp_path / "second", **kwargs)

    assert first["decision"] == "stage002_curve_features_pass_ready_for_account_label_contract"
    assert first["feature_columns"] == module.core.MODEL_FEATURES
    assert first["label_columns_read"] == []
    assert first["label_values_read"] is False
    assert first["trains_model"] is False
    assert first["strategy_backtest_runs"] == 0
    assert json.loads((tmp_path / "first/artifact_manifest.json").read_text()) == json.loads(
        (tmp_path / "second/artifact_manifest.json").read_text()
    )
    assert len(pd.read_csv(tmp_path / "first/candidate_curve_feature_panel.csv")) == 4
