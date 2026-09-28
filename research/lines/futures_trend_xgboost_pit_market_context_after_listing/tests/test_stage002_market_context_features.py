from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pandas as pd


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools/stage002_market_context_features.py"
SPEC = importlib.util.spec_from_file_location("stage002_market_context_features", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_inputs(root: Path) -> tuple[dict[str, Path], dict[str, str]]:
    root.mkdir(parents=True)
    eval_date = pd.Timestamp("2024-01-08")
    products = ["t1.X", "t2.X", "b.X", "c.X", "d.X"]
    ranked = pd.DataFrame(
        {
            "eval_date": [eval_date] * 5,
            "product_vt_symbol": products,
            "window_id": ["wf_01"] * 5,
            "pit_logistic_probability": [0.9, 0.8, 0.7, 0.6, 0.5],
            "a_rank": [1, 2, 3, 4, 5],
            "role": ["top9", "top9", "a_rank10", "challenger", "challenger"],
            "future_net_pnl_60d": ["must_not_be_read"] * 5,
        }
    )
    ranked_path = root / "ranked.csv"
    ranked.to_csv(ranked_path, index=False)

    coverage = ranked.drop(columns=["future_net_pnl_60d"]).copy()
    coverage["valid_return_count"] = 6
    coverage["required_return_count"] = 6
    coverage["window_complete"] = True
    coverage["context_eligible"] = coverage["role"].isin(["a_rank10", "challenger"])
    coverage_path = root / "coverage.csv"
    coverage.to_csv(coverage_path, index=False)

    months = pd.DataFrame(
        {
            "eval_date": [eval_date],
            "window_id": ["wf_01"],
            "window_start": ["2024-01-03"],
            "window_end": [eval_date],
            "window_date_count": [6],
            "overlay_active": [True],
        }
    )
    months_path = root / "months.csv"
    months.to_csv(months_path, index=False)

    dates = pd.date_range("2024-01-03", periods=6, freq="D")
    values = {
        "t1.X": [-0.02, -0.01, 0.01, 0.02, -0.015, 0.025],
        "t2.X": [-0.01, -0.02, 0.02, 0.01, -0.025, 0.015],
        "b.X": [0.01, -0.02, 0.015, -0.005, 0.02, -0.01],
        "c.X": [0.03, -0.01, -0.02, 0.01, -0.005, 0.02],
        "d.X": [-0.025, 0.03, -0.005, -0.02, 0.015, 0.01],
    }
    return_rows = []
    for product, product_values in values.items():
        for date, value in zip(dates, product_values, strict=True):
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
    stage001_manifest = root / "stage001_manifest.json"
    stage001_manifest.write_text("{}\n", encoding="utf-8")
    return_manifest = root / "return_manifest.json"
    return_manifest.write_text("{}\n", encoding="utf-8")
    spec = root / "spec.md"
    spec.write_text("frozen\n", encoding="utf-8")
    paths = {
        "ranked_a_panel": ranked_path,
        "coverage": coverage_path,
        "month_audit": months_path,
        "stage001_manifest": stage001_manifest,
        "product_returns": returns_path,
        "return_manifest": return_manifest,
        "spec": spec,
    }
    return paths, {name: _sha256(path) for name, path in paths.items()}


def test_stage002_uses_whitelisted_inputs_and_publishes_deterministically(tmp_path: Path) -> None:
    paths, hashes = _write_inputs(tmp_path / "inputs")
    kwargs = {
        "input_paths": paths,
        "expected_sha256": hashes,
        "window_days": 6,
        "top_rank_count": 2,
        "minimum_downside_days": 3,
        "expected_rows": 3,
        "expected_months": 1,
        "expected_anchor_rows": 1,
        "expected_challenger_rows": 2,
        "expected_min_rows_per_month": 3,
        "expected_max_rows_per_month": 3,
        "expected_fold_count": 1,
        "minimum_unique_challenger_values": 2,
    }
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"

    first = module.run_stage002(first_dir, **kwargs)
    second = module.run_stage002(second_dir, **kwargs)

    assert first["decision"] == "stage002_market_context_features_pass_ready_for_ranker_preregistration"
    assert first["feature_count"] == 6
    assert first["label_columns_read"] == []
    assert first["label_values_read"] is False
    assert first["trains_model"] is False
    assert first["strategy_backtest_runs"] == 0
    assert json.loads((first_dir / "artifact_manifest.json").read_text()) == json.loads(
        (second_dir / "artifact_manifest.json").read_text()
    )
    assert len(pd.read_csv(first_dir / "market_context_feature_panel.csv")) == 3

