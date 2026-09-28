"""Frozen A/B/C development OOS test for ALFRED sector residual features."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import shutil
import sys
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from uuid import UUID

import numpy as np
import pandas as pd
import sklearn
import xgboost
from sklearn.metrics import log_loss
from xgboost import XGBClassifier


LINE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[4]
MODEL_RANKED_LINE = (
    REPO_ROOT / "research/lines/futures_trend_lr_xgboost_base_margin_model_ranked"
)
MODEL_RANKED_TOOLS = MODEL_RANKED_LINE / "tools"
if str(MODEL_RANKED_TOOLS) not in sys.path:
    sys.path.insert(0, str(MODEL_RANKED_TOOLS))

import stage001_model_ranked_contract as model_contract
import stage001_alfred_global_risk_contract as alfred_stage001


PREREGISTRATION_PATH = (
    LINE_DIR
    / "stages/20260904_2124_stage002_alfred_global_risk_development_oos_preregistration.md"
)
TEST_PATH = (
    LINE_DIR / "tests/test_stage002_alfred_global_risk_development_oos.py"
)
AUTHORIZATION_PATH = (
    LINE_DIR / "stages/20260904_stage002_execution_authorization.json"
)
STAGE001_DIR = LINE_DIR / "artifacts/stage001_alfred_global_risk_contract"
STAGE001_SUMMARY_PATH = STAGE001_DIR / "summary.json"
STAGE001_MANIFEST_PATH = STAGE001_DIR / "artifact_manifest.json"
STAGE001_FOLD_PLAN_PATH = STAGE001_DIR / "copied_fold_plan.csv"
STAGE001_INTERACTION_PANEL_PATH = STAGE001_DIR / "interaction_panel.csv"
STAGE001_FEATURE_CONTRACT_PATH = STAGE001_DIR / "feature_contract.json"
FORMAL_FEATURE_CONTRACT_PATH = (
    MODEL_RANKED_LINE / "artifacts/stage001_model_ranked_contract/feature_contract.json"
)
FINAL_OUTPUT_DIR = LINE_DIR / "artifacts/stage002_alfred_global_risk_development_oos"
EXECUTION_MARKER_PATH = (
    LINE_DIR / "artifacts/stage002_alfred_global_risk_development_oos_execution.json"
)

PASS_DECISION = (
    "stage002_alfred_global_risk_development_oos_pass_"
    "require_independent_review_before_true_engine"
)
FAIL_DECISION = (
    "stage002_alfred_global_risk_development_oos_fail_close_no_true_engine"
)

TOP_N = 10
HORIZON = 60
EXPECTED_RELEASE_ID = alfred_stage001.EXPECTED_RELEASE_ID
EXPECTED_STRATEGY_ID = alfred_stage001.EXPECTED_STRATEGY_ID
EXPECTED_XGBOOST_VERSION = "3.2.0"
EXPECTED_SKLEARN_VERSION = "1.8.0"
EXPECTED_STAGE001_HASHES: dict[Path, str] = {
    STAGE001_SUMMARY_PATH: (
        "64c8b9903750e3600dfae0fabec74f6b611656a0b271321521984f0fb7154619"
    ),
    STAGE001_MANIFEST_PATH: (
        "94161cb2e7a300c9a60e770f2a5cbc7426d26e734b461d7ded541a8a73eb447f"
    ),
    STAGE001_FOLD_PLAN_PATH: (
        "a14fbde27943e1c73eaa8c1e2ea14834e212616e82fe024ba193697369a25e6c"
    ),
    STAGE001_INTERACTION_PANEL_PATH: (
        "3837f272d24e573431b0be145d49b5b71b4384fc930e5ca05d28213be7a617ee"
    ),
    STAGE001_FEATURE_CONTRACT_PATH: (
        "a13e5252f0cc7c4d8fc1d28ec288675d12f35b1a701a57f42be4cf7d99bfdfc7"
    ),
}
EXPECTED_STATE_FEATURES = (
    "cny_depreciation_shock_20d",
    "broad_usd_shock_20d",
    "vix_stress_percentile_252d",
    "cny_depreciation_shock_20d_x_metals",
    "cny_depreciation_shock_20d_x_ferrous",
    "cny_depreciation_shock_20d_x_agriculture",
    "cny_depreciation_shock_20d_x_chemicals_materials",
    "broad_usd_shock_20d_x_metals",
    "broad_usd_shock_20d_x_ferrous",
    "broad_usd_shock_20d_x_agriculture",
    "broad_usd_shock_20d_x_chemicals_materials",
    "vix_stress_percentile_252d_x_metals",
    "vix_stress_percentile_252d_x_ferrous",
    "vix_stress_percentile_252d_x_agriculture",
    "vix_stress_percentile_252d_x_chemicals_materials",
)
REQUIRED_BINDING_NAMES = {
    "stage002_preregistration",
    "stage002_runner",
    "stage002_tests",
    "stage001_runner",
    "stage001_summary",
    "stage001_manifest",
    "stage001_fold_plan",
    "stage001_interaction_panel",
    "stage001_feature_contract",
    "model_ranked_stage001_runner",
    "causal_formal_features",
    "predecessor_stage001_runner",
    "formal_current",
    "formal_release_manifest",
    "formal_lr_model",
    "formal_qmt_universe",
    "formal_stage182_summary",
    "stage183_position_changes",
    "stage183_entry_snapshots",
    "historical_feature_panel",
    "formal_feature_contract",
}
CANONICAL_BINDING_PATHS: dict[str, Path] = {
    "stage002_preregistration": PREREGISTRATION_PATH,
    "stage002_runner": Path(__file__).resolve(),
    "stage002_tests": TEST_PATH,
    "stage001_runner": LINE_DIR / "tools/stage001_alfred_global_risk_contract.py",
    "stage001_summary": STAGE001_SUMMARY_PATH,
    "stage001_manifest": STAGE001_MANIFEST_PATH,
    "stage001_fold_plan": STAGE001_FOLD_PLAN_PATH,
    "stage001_interaction_panel": STAGE001_INTERACTION_PANEL_PATH,
    "stage001_feature_contract": STAGE001_FEATURE_CONTRACT_PATH,
    "model_ranked_stage001_runner": MODEL_RANKED_TOOLS
    / "stage001_model_ranked_contract.py",
    "causal_formal_features": model_contract.PREDECESSOR_CAUSAL_TOOL,
    "predecessor_stage001_runner": model_contract.PREDECESSOR_RUNNER_TOOL,
    "formal_current": model_contract.base.CURRENT_PATH,
    "formal_release_manifest": model_contract.base.MANIFEST_PATH,
    "formal_lr_model": model_contract.base.MODEL_PATH,
    "formal_qmt_universe": alfred_stage001.QMT_UNIVERSE_PATH,
    "formal_stage182_summary": model_contract.base.STAGE182_SUMMARY_PATH,
    "stage183_position_changes": model_contract.base.POSITION_CHANGES_PATH,
    "stage183_entry_snapshots": model_contract.base.ENTRY_SNAPSHOTS_PATH,
    "historical_feature_panel": model_contract.base.HISTORICAL_PANEL_PATH,
    "formal_feature_contract": FORMAL_FEATURE_CONTRACT_PATH,
}
STATIC_BINDING_HASHES: dict[str, str] = {
    "stage001_runner": (
        "4083cdfe4dc9d54dd5180f509c4d180255a097a55b03432de940db42228c8ce1"
    ),
    "stage001_summary": EXPECTED_STAGE001_HASHES[STAGE001_SUMMARY_PATH],
    "stage001_manifest": EXPECTED_STAGE001_HASHES[STAGE001_MANIFEST_PATH],
    "stage001_fold_plan": EXPECTED_STAGE001_HASHES[STAGE001_FOLD_PLAN_PATH],
    "stage001_interaction_panel": EXPECTED_STAGE001_HASHES[
        STAGE001_INTERACTION_PANEL_PATH
    ],
    "stage001_feature_contract": EXPECTED_STAGE001_HASHES[
        STAGE001_FEATURE_CONTRACT_PATH
    ],
    "model_ranked_stage001_runner": (
        "b05799b8f0c8001f8719f1de7ef0790e1806913d7467a8404a8ecbd306de38f8"
    ),
    "causal_formal_features": (
        "930c81fca2de049983c75c7470873e781b086a208993f9817fb04fd3649ef15f"
    ),
    "predecessor_stage001_runner": (
        "6f315ecb5ca63f0fbf83495119226c65da397c2a5dbbf7ef8cefa80a9c34c2bd"
    ),
    "formal_current": (
        "f17c0f6bfeea4a08ec7c22a1eb63d4b51e4cfb2472f1ce07fac8ce2cc570b219"
    ),
    "formal_release_manifest": (
        "d62e58d01284e30b28054387592604862ffeff6e55a13c63192793e95bc55c21"
    ),
    "formal_lr_model": (
        "7734d1768728a4e591b80e98da2b5bac90636904dad82e0fed5f331a6eb45de4"
    ),
    "formal_qmt_universe": (
        "8a149c49075d85d25f27146a8f3c2de3bea1971e3bd0d20a36ed9104b636997f"
    ),
    "formal_stage182_summary": (
        "e119fcdaddb16d173bf8737edd39e3241dc2b277ea96f908d6eeb71bf9bdd5c3"
    ),
    "stage183_position_changes": (
        "17c81f2dbb30f836b544161c3fc4d4bd6415151d89b8f8937378739e868c21aa"
    ),
    "stage183_entry_snapshots": (
        "f838186527b1453923635bda31ec8e1656a0bdacfec633a6b85f2cda8e3b26a0"
    ),
    "historical_feature_panel": (
        "92f36b6647cae9d8db04b0a1351749f9103a1988799dbb8dff0ad1d350d1d431"
    ),
    "formal_feature_contract": (
        "64909eeca4d84348c9adea29062430d8010b0e194ab87edd37169752facfb182"
    ),
}
XGBOOST_PARAMS: dict[str, Any] = {
    "objective": "binary:logistic",
    "eval_metric": "logloss",
    "n_estimators": 32,
    "max_depth": 1,
    "learning_rate": 0.03,
    "min_child_weight": 20,
    "gamma": 0.1,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "reg_alpha": 1.0,
    "reg_lambda": 20.0,
    "max_delta_step": 1.0,
    "tree_method": "hist",
    "random_state": 42,
    "n_jobs": 1,
}


class Stage002Error(RuntimeError):
    pass


@dataclass(frozen=True)
class StandaloneFitResult:
    probability: np.ndarray
    repeat_max_abs_error: float
    split_nodes: int


@dataclass(frozen=True)
class ResidualFitResult:
    probability: np.ndarray
    raw_correction: np.ndarray
    repeat_max_abs_error: float
    split_nodes: int


def _sha256(path: Path) -> tuple[int, int, str]:
    source = path.expanduser().resolve(strict=True)
    before = source.stat()
    digest = hashlib.sha256()
    with source.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    after = source.stat()
    if (before.st_size, before.st_mtime_ns) != (
        after.st_size,
        after.st_mtime_ns,
    ):
        raise Stage002Error(f"file_changed_while_hashing:{source}")
    return int(after.st_size), int(after.st_mtime_ns), digest.hexdigest()


def _logit(probability: np.ndarray) -> np.ndarray:
    clipped = np.clip(
        np.asarray(probability, dtype="float64"),
        1e-12,
        1.0 - 1e-12,
    )
    return np.log(clipped / (1.0 - clipped))


def _new_xgboost_model() -> XGBClassifier:
    return XGBClassifier(**XGBOOST_PARAMS)


def _split_nodes(model: XGBClassifier) -> int:
    frame = model.get_booster().trees_to_dataframe()
    return int(frame["Feature"].ne("Leaf").sum())


def fit_standalone_xgboost(
    *,
    x_train: Any,
    y_train: np.ndarray,
    sample_weight: np.ndarray,
    x_test: Any,
) -> StandaloneFitResult:
    model = _new_xgboost_model()
    model.fit(x_train, y_train, sample_weight=sample_weight, verbose=False)
    probability = np.asarray(model.predict_proba(x_test)[:, 1], dtype="float64")

    repeated = _new_xgboost_model()
    repeated.fit(x_train, y_train, sample_weight=sample_weight, verbose=False)
    repeated_probability = np.asarray(
        repeated.predict_proba(x_test)[:, 1],
        dtype="float64",
    )
    return StandaloneFitResult(
        probability=probability,
        repeat_max_abs_error=float(
            np.max(np.abs(probability - repeated_probability))
        ),
        split_nodes=_split_nodes(model),
    )


def fit_base_margin_residual(
    *,
    x_train: Any,
    y_train: np.ndarray,
    sample_weight: np.ndarray,
    train_margin: np.ndarray,
    x_test: Any,
    test_margin: np.ndarray,
) -> ResidualFitResult:
    model = _new_xgboost_model()
    model.fit(
        x_train,
        y_train,
        sample_weight=sample_weight,
        base_margin=train_margin,
        verbose=False,
    )
    probability = np.asarray(
        model.predict_proba(x_test, base_margin=test_margin)[:, 1],
        dtype="float64",
    )

    repeated = _new_xgboost_model()
    repeated.fit(
        x_train,
        y_train,
        sample_weight=sample_weight,
        base_margin=train_margin,
        verbose=False,
    )
    repeated_probability = np.asarray(
        repeated.predict_proba(x_test, base_margin=test_margin)[:, 1],
        dtype="float64",
    )
    return ResidualFitResult(
        probability=probability,
        raw_correction=_logit(probability)
        - np.asarray(test_margin, dtype="float64"),
        repeat_max_abs_error=float(
            np.max(np.abs(probability - repeated_probability))
        ),
        split_nodes=_split_nodes(model),
    )


def join_state_features(
    formal_panel: pd.DataFrame,
    state_panel: pd.DataFrame,
    feature_columns: Sequence[str],
) -> tuple[pd.DataFrame, dict[str, int]]:
    keys = ["eval_date", "product_vt_symbol"]
    features = list(feature_columns)
    required_formal = set(keys)
    required_state = {*keys, *features}
    missing_formal = sorted(required_formal - set(formal_panel.columns))
    missing_state = sorted(required_state - set(state_panel.columns))
    if missing_formal:
        raise Stage002Error(
            f"formal_panel_column_missing:{','.join(missing_formal)}"
        )
    if missing_state:
        raise Stage002Error(f"state_panel_column_missing:{','.join(missing_state)}")

    formal = formal_panel.copy()
    state = state_panel[keys + features].copy()
    for frame in (formal, state):
        frame["eval_date"] = pd.to_datetime(frame["eval_date"]).dt.normalize()
        frame["product_vt_symbol"] = frame["product_vt_symbol"].astype(str)
    if formal.duplicated(keys, keep=False).any():
        raise Stage002Error("formal_panel_duplicate_key")
    duplicate_rows = int(state.duplicated(keys, keep=False).sum())
    if duplicate_rows:
        raise Stage002Error(f"state_panel_duplicate_key:{duplicate_rows}")
    state[features] = state[features].apply(pd.to_numeric, errors="coerce")
    if not np.isfinite(state[features].to_numpy(dtype="float64")).all():
        raise Stage002Error("state_panel_nonfinite_feature")

    formal["_formal_order"] = np.arange(len(formal), dtype="int64")
    joined = formal.merge(
        state,
        on=keys,
        how="left",
        validate="one_to_one",
        indicator=True,
        sort=False,
    )
    missing_rows = int(joined["_merge"].ne("both").sum())
    if missing_rows:
        raise Stage002Error(f"state_panel_join_missing:{missing_rows}")
    joined.sort_values("_formal_order", inplace=True)
    joined.reset_index(drop=True, inplace=True)

    state_indexed = state.set_index(keys)[features]
    joined_keys = pd.MultiIndex.from_frame(joined[keys])
    expected = state_indexed.reindex(joined_keys).to_numpy(dtype="float64")
    actual = joined[features].to_numpy(dtype="float64")
    modified_cells = int((expected != actual).sum())
    joined.drop(columns=["_formal_order", "_merge"], inplace=True)
    return joined, {
        "state_panel_join_missing_rows": missing_rows,
        "state_panel_duplicate_key_rows": duplicate_rows,
        "state_feature_modified_cell_count": modified_cells,
    }


def select_frozen_feature_rows(
    featured_daily: pd.DataFrame,
    frozen_keys: pd.DataFrame,
) -> pd.DataFrame:
    required_featured = {"date", "product_vt_symbol"}
    required_keys = {"eval_date", "product_vt_symbol"}
    missing_featured = sorted(required_featured - set(featured_daily.columns))
    missing_keys = sorted(required_keys - set(frozen_keys.columns))
    if missing_featured:
        raise Stage002Error(
            f"featured_column_missing:{','.join(missing_featured)}"
        )
    if missing_keys:
        raise Stage002Error(f"frozen_key_column_missing:{','.join(missing_keys)}")
    featured = featured_daily.copy()
    featured["date"] = pd.to_datetime(featured["date"]).dt.normalize()
    featured["product_vt_symbol"] = featured["product_vt_symbol"].astype(str)
    keys = frozen_keys[["eval_date", "product_vt_symbol"]].copy()
    keys["eval_date"] = pd.to_datetime(keys["eval_date"]).dt.normalize()
    keys["product_vt_symbol"] = keys["product_vt_symbol"].astype(str)
    if featured.duplicated(["date", "product_vt_symbol"], keep=False).any():
        raise Stage002Error("featured_duplicate_product_date")
    if keys.duplicated(["eval_date", "product_vt_symbol"], keep=False).any():
        raise Stage002Error("frozen_key_duplicate")
    keys.rename(columns={"eval_date": "date"}, inplace=True)
    keys["_frozen_order"] = np.arange(len(keys), dtype="int64")
    selected = keys.merge(
        featured,
        on=["date", "product_vt_symbol"],
        how="left",
        validate="one_to_one",
        indicator=True,
        sort=False,
    )
    missing_rows = int(selected["_merge"].ne("both").sum())
    if missing_rows:
        raise Stage002Error(f"frozen_feature_key_missing:{missing_rows}")
    selected.sort_values("_frozen_order", inplace=True)
    selected.drop(columns=["_frozen_order", "_merge"], inplace=True)
    selected.reset_index(drop=True, inplace=True)
    return selected


def build_frozen_label_table(
    daily: pd.DataFrame,
    frozen_keys: pd.DataFrame,
    *,
    horizon: int = HORIZON,
) -> pd.DataFrame:
    required_daily = {"date", "product_vt_symbol", "net_pnl"}
    required_keys = {"eval_date", "product_vt_symbol"}
    if missing := sorted(required_daily - set(daily.columns)):
        raise Stage002Error(f"label_daily_column_missing:{','.join(missing)}")
    if missing := sorted(required_keys - set(frozen_keys.columns)):
        raise Stage002Error(f"label_key_column_missing:{','.join(missing)}")
    if horizon <= 0:
        raise Stage002Error("label_horizon_must_be_positive")
    frame = daily[["date", "product_vt_symbol", "net_pnl"]].copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    frame["product_vt_symbol"] = frame["product_vt_symbol"].astype(str)
    frame["net_pnl"] = pd.to_numeric(frame["net_pnl"], errors="coerce")
    if frame.duplicated(["date", "product_vt_symbol"], keep=False).any():
        raise Stage002Error("label_daily_duplicate_product_date")
    if not np.isfinite(frame["net_pnl"].to_numpy(dtype="float64")).all():
        raise Stage002Error("label_daily_nonfinite_net_pnl")
    keys = frozen_keys[["eval_date", "product_vt_symbol"]].copy()
    keys["eval_date"] = pd.to_datetime(keys["eval_date"]).dt.normalize()
    keys["product_vt_symbol"] = keys["product_vt_symbol"].astype(str)
    if keys.duplicated(["eval_date", "product_vt_symbol"], keep=False).any():
        raise Stage002Error("label_key_duplicate")

    global_dates = pd.DatetimeIndex(frame["date"].unique()).sort_values()
    positions = {
        pd.Timestamp(date): index for index, date in enumerate(global_dates)
    }
    product_values = {
        str(product): group.set_index("date")["net_pnl"].sort_index()
        for product, group in frame.groupby("product_vt_symbol", sort=True)
    }
    rows: list[dict[str, Any]] = []
    for row in keys.itertuples(index=False):
        eval_date = pd.Timestamp(row.eval_date)
        product = str(row.product_vt_symbol)
        if eval_date not in positions:
            raise Stage002Error(f"label_eval_date_not_global:{eval_date.date()}")
        if product not in product_values:
            raise Stage002Error(f"label_product_missing:{product}")
        start = positions[eval_date] + 1
        expected_dates = global_dates[start : start + int(horizon)]
        if len(expected_dates) != int(horizon):
            raise Stage002Error(
                f"label_horizon_incomplete:{eval_date.date()}:{len(expected_dates)}"
            )
        path = product_values[product].reindex(expected_dates)
        if path.isna().any():
            raise Stage002Error(
                f"label_global_date_missing:{product}:{eval_date.date()}"
            )
        rows.append(
            {
                "eval_date": eval_date,
                "product_vt_symbol": product,
                "future_net_pnl_60d": float(path.to_numpy(dtype="float64").sum()),
                "label_end": pd.Timestamp(expected_dates[-1]),
            }
        )
    return pd.DataFrame(rows)


def build_future_path_table(
    daily: pd.DataFrame,
    eval_dates: Iterable[pd.Timestamp],
    *,
    horizon: int = HORIZON,
) -> pd.DataFrame:
    required = {"date", "product_vt_symbol", "net_pnl"}
    missing = sorted(required - set(daily.columns))
    if missing:
        raise ValueError(f"future_path_columns_missing:{','.join(missing)}")
    if horizon <= 0:
        raise ValueError("future_path_horizon_must_be_positive")
    frame = daily[["date", "product_vt_symbol", "net_pnl"]].copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    frame["product_vt_symbol"] = frame["product_vt_symbol"].astype(str)
    frame["net_pnl"] = pd.to_numeric(frame["net_pnl"], errors="coerce")
    if frame.duplicated(["date", "product_vt_symbol"], keep=False).any():
        raise ValueError("future_path_duplicate_product_date")
    if not np.isfinite(frame["net_pnl"].to_numpy(dtype="float64")).all():
        raise ValueError("future_path_nonfinite_net_pnl")
    tests = (
        pd.DatetimeIndex(pd.to_datetime(list(eval_dates)))
        .normalize()
        .unique()
        .sort_values()
    )
    global_dates = pd.DatetimeIndex(frame["date"].unique()).sort_values()
    global_positions = {
        pd.Timestamp(date): index for index, date in enumerate(global_dates)
    }
    product_paths = {
        str(product): group.set_index("date")[["net_pnl"]].sort_index()
        for product, group in frame.groupby("product_vt_symbol", sort=True)
    }
    rows: list[pd.DataFrame] = []
    for eval_date in tests:
        if eval_date not in global_positions:
            raise ValueError(
                f"future_path_eval_date_not_global:{eval_date.date().isoformat()}"
            )
        start = global_positions[eval_date] + 1
        expected_dates = global_dates[start : start + int(horizon)]
        if len(expected_dates) != int(horizon):
            raise ValueError(
                "future_path_global_horizon_incomplete:"
                f"{eval_date.date().isoformat()}:{len(expected_dates)}"
            )
        for product, indexed in product_paths.items():
            if eval_date not in indexed.index:
                raise ValueError(
                    "future_path_eval_date_missing:"
                    f"{product}:{eval_date.date().isoformat()}"
                )
            path = indexed.reindex(expected_dates)
            if path["net_pnl"].isna().any():
                raise ValueError(
                    "future_path_global_date_missing:"
                    f"{product}:{eval_date.date().isoformat()}"
                )
            path = path.rename_axis("date").reset_index()
            path.insert(0, "eval_date", pd.Timestamp(eval_date))
            path.insert(1, "product_vt_symbol", str(product))
            path.insert(2, "path_step", np.arange(1, int(horizon) + 1))
            rows.append(path)
    result = pd.concat(rows, ignore_index=True)
    result.sort_values(
        ["eval_date", "product_vt_symbol", "path_step"],
        inplace=True,
    )
    result.reset_index(drop=True, inplace=True)
    return result


def path_metrics(net_pnl: np.ndarray) -> dict[str, float]:
    values = np.asarray(net_pnl, dtype="float64")
    if values.ndim != 1 or values.size == 0 or not np.isfinite(values).all():
        raise ValueError("path_values_invalid")
    equity = np.concatenate(([0.0], np.cumsum(values)))
    drawdown = equity - np.maximum.accumulate(equity)
    return {
        "total_net_pnl": float(values.sum()),
        "max_drawdown": float(drawdown.min()),
    }


def stable_top_n(
    frame: pd.DataFrame,
    *,
    score_column: str,
    top_n: int = TOP_N,
) -> list[str]:
    ranked = frame.sort_values(
        [score_column, "product_vt_symbol"],
        ascending=[False, True],
        kind="mergesort",
    )
    return ranked.head(int(top_n))["product_vt_symbol"].astype(str).tolist()


def _selected_path_metrics(
    paths: pd.DataFrame,
    products: list[str],
) -> dict[str, float]:
    selected = paths[paths["product_vt_symbol"].isin(products)].copy()
    if selected["product_vt_symbol"].nunique() != len(products):
        raise ValueError("selected_path_product_missing")
    expected_steps = int(selected["path_step"].max())
    counts = selected.groupby("product_vt_symbol")["path_step"].nunique()
    if not counts.eq(expected_steps).all():
        raise ValueError("selected_path_step_incomplete")
    aggregate = (
        selected.groupby("path_step", sort=True)["net_pnl"]
        .sum()
        .reindex(range(1, expected_steps + 1))
    )
    if aggregate.isna().any():
        raise ValueError("selected_path_step_gap")
    return path_metrics(aggregate.to_numpy(dtype="float64"))


def build_monthly_effects(
    predictions: pd.DataFrame,
    future_paths: pd.DataFrame,
    *,
    top_n: int = TOP_N,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    effect_rows: list[dict[str, Any]] = []
    selection_rows: list[dict[str, Any]] = []
    frame = predictions.copy()
    frame["eval_date"] = pd.to_datetime(frame["eval_date"]).dt.normalize()
    paths = future_paths.copy()
    paths["eval_date"] = pd.to_datetime(paths["eval_date"]).dt.normalize()
    for eval_date, month in frame.groupby("eval_date", sort=True):
        selected_a = stable_top_n(month, score_column="score_a", top_n=top_n)
        selected_c = stable_top_n(month, score_column="score_c", top_n=top_n)
        month_paths = paths[paths["eval_date"].eq(eval_date)]
        metrics_a = _selected_path_metrics(month_paths, selected_a)
        metrics_c = _selected_path_metrics(month_paths, selected_c)
        for arm, products in (("A", selected_a), ("C", selected_c)):
            for rank, product in enumerate(products, start=1):
                selection_rows.append(
                    {
                        "eval_date": pd.Timestamp(eval_date),
                        "arm": arm,
                        "selection_rank": rank,
                        "product_vt_symbol": product,
                    }
                )
        return_delta = metrics_c["total_net_pnl"] - metrics_a["total_net_pnl"]
        drawdown_improvement = (
            metrics_c["max_drawdown"] - metrics_a["max_drawdown"]
        )
        effect_rows.append(
            {
                "eval_date": pd.Timestamp(eval_date),
                "selected_a": ",".join(selected_a),
                "selected_c": ",".join(selected_c),
                "changed": set(selected_a) != set(selected_c),
                "a_future_net_pnl_60d": metrics_a["total_net_pnl"],
                "c_future_net_pnl_60d": metrics_c["total_net_pnl"],
                "a_future_max_drawdown_60d": metrics_a["max_drawdown"],
                "c_future_max_drawdown_60d": metrics_c["max_drawdown"],
                "return_delta": return_delta,
                "drawdown_improvement": drawdown_improvement,
                "joint_positive": (
                    return_delta > 0.0 and drawdown_improvement > 0.0
                ),
            }
        )
    return pd.DataFrame(effect_rows), pd.DataFrame(selection_rows)


def summarize_effects(
    monthly_effects: pd.DataFrame,
) -> tuple[dict[str, Any], pd.DataFrame]:
    effects = monthly_effects.copy()
    effects["eval_date"] = pd.to_datetime(effects["eval_date"]).dt.normalize()
    changed = effects[effects["changed"].astype(bool)].copy()
    if changed.empty:
        yearly = pd.DataFrame(
            columns=[
                "year",
                "changed_months",
                "return_delta",
                "drawdown_improvement",
            ]
        )
        return {
            "changed_months": 0,
            "changed_years": 0,
            "sum_return_delta": 0.0,
            "sum_drawdown_improvement": 0.0,
            "leave_best_return_delta": 0.0,
            "leave_best_drawdown_improvement": 0.0,
            "joint_positive_ratio": 0.0,
            "minimum_year_return_delta": 0.0,
            "minimum_year_drawdown_improvement": 0.0,
        }, yearly
    changed["joint_positive"] = (
        changed["return_delta"].gt(0.0)
        & changed["drawdown_improvement"].gt(0.0)
    )
    changed["year"] = changed["eval_date"].dt.year
    yearly = (
        changed.groupby("year", as_index=False)
        .agg(
            changed_months=("eval_date", "size"),
            return_delta=("return_delta", "sum"),
            drawdown_improvement=("drawdown_improvement", "sum"),
        )
        .sort_values("year")
        .reset_index(drop=True)
    )
    return_sum = float(changed["return_delta"].sum())
    drawdown_sum = float(changed["drawdown_improvement"].sum())
    return {
        "changed_months": int(len(changed)),
        "changed_years": int(changed["year"].nunique()),
        "sum_return_delta": return_sum,
        "sum_drawdown_improvement": drawdown_sum,
        "leave_best_return_delta": float(
            return_sum - changed["return_delta"].max()
        ),
        "leave_best_drawdown_improvement": float(
            drawdown_sum - changed["drawdown_improvement"].max()
        ),
        "joint_positive_ratio": float(changed["joint_positive"].mean()),
        "minimum_year_return_delta": float(yearly["return_delta"].min()),
        "minimum_year_drawdown_improvement": float(
            yearly["drawdown_improvement"].min()
        ),
    }, yearly


def audit_oos_path_consistency(
    predictions: pd.DataFrame,
    future_paths: pd.DataFrame,
    fold_plan: pd.DataFrame,
    *,
    tolerance: float = 1e-8,
) -> dict[str, Any]:
    keys = ["eval_date", "product_vt_symbol"]
    required_predictions = {*keys, "future_net_pnl_60d"}
    required_paths = {*keys, "date", "path_step", "net_pnl"}
    if missing := sorted(required_predictions - set(predictions.columns)):
        raise Stage002Error(
            f"path_audit_prediction_column_missing:{','.join(missing)}"
        )
    if missing := sorted(required_paths - set(future_paths.columns)):
        raise Stage002Error(f"path_audit_path_column_missing:{','.join(missing)}")
    if missing := sorted(
        {"test_eval_date", "test_label_end"} - set(fold_plan.columns)
    ):
        raise Stage002Error(f"path_audit_fold_column_missing:{','.join(missing)}")
    if tolerance < 0.0:
        raise Stage002Error("path_audit_tolerance_negative")

    expected = predictions[keys + ["future_net_pnl_60d"]].copy()
    expected["eval_date"] = pd.to_datetime(expected["eval_date"]).dt.normalize()
    expected["product_vt_symbol"] = expected["product_vt_symbol"].astype(str)
    paths = future_paths.copy()
    paths["eval_date"] = pd.to_datetime(paths["eval_date"]).dt.normalize()
    paths["date"] = pd.to_datetime(paths["date"]).dt.normalize()
    paths["product_vt_symbol"] = paths["product_vt_symbol"].astype(str)
    aggregate = (
        paths.groupby(keys, as_index=False)
        .agg(
            path_net_pnl=("net_pnl", "sum"),
            path_label_end=("date", "max"),
            path_steps=("path_step", "nunique"),
        )
    )
    fold_ends = fold_plan[["test_eval_date", "test_label_end"]].copy()
    fold_ends["test_eval_date"] = pd.to_datetime(
        fold_ends["test_eval_date"]
    ).dt.normalize()
    fold_ends["test_label_end"] = pd.to_datetime(
        fold_ends["test_label_end"]
    ).dt.normalize()
    fold_ends.rename(
        columns={
            "test_eval_date": "eval_date",
            "test_label_end": "expected_label_end",
        },
        inplace=True,
    )
    audited = expected.merge(
        aggregate,
        on=keys,
        how="left",
        validate="one_to_one",
    ).merge(
        fold_ends,
        on="eval_date",
        how="left",
        validate="many_to_one",
    )
    missing_rows = int(
        audited[
            ["path_net_pnl", "path_label_end", "path_steps", "expected_label_end"]
        ]
        .isna()
        .any(axis=1)
        .sum()
    )
    differences = (
        pd.to_numeric(audited["path_net_pnl"], errors="coerce")
        - pd.to_numeric(audited["future_net_pnl_60d"], errors="coerce")
    ).abs()
    finite_differences = differences[np.isfinite(differences)]
    max_error = (
        float(finite_differences.max()) if not finite_differences.empty else float("inf")
    )
    sum_mismatches = int(differences.gt(float(tolerance)).fillna(True).sum())
    end_mismatches = int(
        (
            audited["path_label_end"].isna()
            | audited["expected_label_end"].isna()
            | audited["path_label_end"].ne(audited["expected_label_end"])
        ).sum()
    )
    return {
        "oos_path_missing_rows": missing_rows,
        "oos_path_label_sum_mismatch_rows": sum_mismatches,
        "oos_path_label_sum_max_abs_error": max_error,
        "oos_path_label_end_mismatch_rows": end_mismatches,
    }


def summarize_model_metrics(predictions: pd.DataFrame) -> dict[str, float]:
    target = predictions["target"].to_numpy(dtype="int64")
    weight = predictions["sample_weight"].to_numpy(dtype="float64")
    result: dict[str, float] = {}
    for arm in ("a", "b", "c"):
        score_column = f"score_{arm}"
        score = np.clip(
            predictions[score_column].to_numpy(dtype="float64"),
            1e-12,
            1.0 - 1e-12,
        )
        result[f"weighted_logloss_{arm}"] = float(
            log_loss(target, score, sample_weight=weight, labels=[0, 1])
        )
        rank_ic = (
            predictions.groupby("eval_date", sort=True)
            .apply(
                lambda group: group[score_column].corr(
                    group["future_rank"],
                    method="spearman",
                ),
                include_groups=False,
            )
            .replace([np.inf, -np.inf], np.nan)
            .fillna(0.0)
        )
        result[f"mean_monthly_rank_ic_{arm}"] = float(rank_ic.mean())
    return result


def assess_gates(metrics: Mapping[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    if not (
        metrics.get("current_release_id") == EXPECTED_RELEASE_ID
        and metrics.get("current_strategy_id") == EXPECTED_STRATEGY_ID
        and int(metrics.get("input_identity_mismatch_count", -1)) == 0
        and bool(metrics.get("authorization_valid", False))
        and bool(metrics.get("stage001_manifest_valid", False))
        and bool(metrics.get("formal_feature_contract_match", False))
    ):
        failures.append("identity_authorization")
    if not (
        int(metrics.get("fold_count", -1)) == 50
        and int(metrics.get("prediction_rows", -1)) == 900
        and int(metrics.get("minimum_products_per_test_month", -1)) == 18
        and int(metrics.get("maximum_products_per_test_month", -1)) == 18
        and int(metrics.get("formal_feature_count", -1)) == 108
        and int(metrics.get("state_feature_count", -1)) == 15
        and int(metrics.get("logistic_fit_count", -1)) == 50
        and int(metrics.get("scaler_fit_count", -1)) == 50
        and int(metrics.get("standalone_xgboost_fit_count", -1)) == 100
        and int(metrics.get("residual_xgboost_fit_count", -1)) == 100
        and int(metrics.get("xgboost_fit_count", -1)) == 200
    ):
        failures.append("fold_and_fit_contract")
    if not (
        int(metrics.get("state_panel_row_count", -1)) == 1386
        and int(metrics.get("state_panel_join_missing_rows", -1)) == 0
        and int(metrics.get("state_panel_duplicate_key_rows", -1)) == 0
        and int(metrics.get("state_feature_modified_cell_count", -1)) == 0
    ):
        failures.append("state_panel_join_contract")
    if not (
        int(metrics.get("pit_violation_rows", -1)) == 0
        and int(metrics.get("pit_violation_folds", -1)) == 0
        and int(metrics.get("sealed_holdout_rows", -1)) == 0
        and int(metrics.get("fixed_fu_model_rows", -1)) == 0
    ):
        failures.append("pit_and_scope_integrity")
    if not (
        int(metrics.get("nonfinite_output_cells", -1)) == 0
        and int(metrics.get("nonpositive_score_std_months_a", -1)) == 0
        and int(metrics.get("nonpositive_score_std_months_b", -1)) == 0
        and int(metrics.get("nonpositive_score_std_months_c", -1)) == 0
    ):
        failures.append("finite_nonconstant_predictions")
    if not (
        float(
            metrics.get("repeat_prediction_max_abs_error_b", float("inf"))
        )
        == 0.0
        and float(
            metrics.get("repeat_prediction_max_abs_error_c", float("inf"))
        )
        == 0.0
    ):
        failures.append("deterministic_repeat")
    if not (
        int(metrics.get("xgboost_split_nodes_b", 0)) > 0
        and int(metrics.get("xgboost_split_nodes_c", 0)) > 0
        and int(metrics.get("xgboost_folds_with_splits_b", -1)) == 50
        and int(metrics.get("xgboost_folds_with_splits_c", -1)) == 50
    ):
        failures.append("xgboost_non_degenerate")
    median_correction = float(
        metrics.get("median_abs_correction_c", float("inf"))
    )
    max_correction = float(metrics.get("max_abs_correction_c", float("inf")))
    if not (1e-6 < median_correction <= 0.5 and max_correction <= 2.0):
        failures.append("bounded_residual_correction")
    if not (
        float(metrics.get("weighted_logloss_c", float("inf")))
        < float(metrics.get("weighted_logloss_a", -float("inf")))
        and float(metrics.get("mean_monthly_rank_ic_c", -float("inf")))
        > float(metrics.get("mean_monthly_rank_ic_a", float("inf")))
    ):
        failures.append("candidate_quality_increment")
    if not (
        int(metrics.get("changed_months", -1)) >= 8
        and int(metrics.get("changed_years", -1)) >= 3
    ):
        failures.append("minimum_action_coverage")
    if not (
        float(metrics.get("sum_return_delta", -float("inf"))) > 0.0
        and float(metrics.get("sum_drawdown_improvement", -float("inf"))) > 0.0
    ):
        failures.append("joint_return_drawdown_effect")
    if not (
        float(metrics.get("leave_best_return_delta", -float("inf"))) > 0.0
        and float(
            metrics.get("leave_best_drawdown_improvement", -float("inf"))
        )
        > 0.0
    ):
        failures.append("leave_best_robustness")
    if float(metrics.get("joint_positive_ratio", -float("inf"))) < 0.55:
        failures.append("joint_positive_rate")
    if not (
        float(metrics.get("minimum_year_return_delta", -float("inf"))) > 0.0
        and float(
            metrics.get("minimum_year_drawdown_improvement", -float("inf"))
        )
        > 0.0
    ):
        failures.append("yearly_robustness")
    if not (
        int(metrics.get("label_value_rows_read", -1)) == 1386
        and int(metrics.get("development_oos_label_rows_used", -1)) == 900
        and int(metrics.get("label_generated_row_count", -1)) == 1386
        and int(metrics.get("label_generated_missing_key_count", -1)) == 0
        and int(metrics.get("label_generated_extra_key_count", -1)) == 0
    ):
        failures.append("label_scope_contract")
    if not (
        int(metrics.get("oos_path_missing_rows", -1)) == 0
        and int(metrics.get("oos_path_label_sum_mismatch_rows", -1)) == 0
        and float(
            metrics.get("oos_path_label_sum_max_abs_error", float("inf"))
        )
        <= 1e-8
        and int(metrics.get("oos_path_label_end_mismatch_rows", -1)) == 0
    ):
        failures.append("path_label_consistency")
    side_effect_fields = (
        "true_engine_run_count",
        "ctp_connection_count",
        "order_api_call_count",
        "production_write_count",
    )
    if any(int(metrics.get(field, -1)) != 0 for field in side_effect_fields):
        failures.append("forbidden_side_effect")
    failures = list(dict.fromkeys(failures))
    return {
        "all_gates_passed": not failures,
        "failures": failures,
        "decision": PASS_DECISION if not failures else FAIL_DECISION,
    }


def validate_authorization_receipt(receipt_path: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        raw_receipt = receipt_path.read_bytes()
        receipt = json.loads(raw_receipt.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {"valid": False, "errors": ["authorization_receipt_unreadable"]}
    receipt_sha256 = hashlib.sha256(raw_receipt).hexdigest()
    if receipt.get("authorized") is not True:
        errors.append("authorization_not_granted")
    if (
        receipt.get("authorization_scope")
        != "single_stage002_alfred_development_oos"
    ):
        errors.append("authorization_scope_invalid")
    if int(receipt.get("allowed_run_count", -1)) != 1:
        errors.append("authorization_run_count_invalid")
    nonce = str(receipt.get("authorization_nonce", ""))
    try:
        parsed_nonce = UUID(nonce)
    except (ValueError, AttributeError):
        errors.append("authorization_nonce_invalid")
    else:
        if str(parsed_nonce) != nonce.lower():
            errors.append("authorization_nonce_invalid")
    bindings = receipt.get("bindings", {})
    if not isinstance(bindings, dict) or not bindings:
        errors.append("authorization_bindings_missing")
    else:
        for name, binding in bindings.items():
            try:
                path = Path(str(binding["path"]))
                _, _, actual = _sha256(path)
            except (KeyError, OSError, Stage002Error):
                errors.append(f"binding_unreadable:{name}")
                continue
            if actual != str(binding.get("sha256", "")):
                errors.append(f"binding_sha256_mismatch:{name}")
    return {
        "valid": not errors,
        "errors": errors,
        "receipt": receipt,
        "receipt_sha256": receipt_sha256,
    }


def validate_canonical_bindings(receipt: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    bindings = receipt.get("bindings", {})
    if not isinstance(bindings, Mapping):
        return {"valid": False, "errors": ["canonical_bindings_missing"]}
    expected_names = set(CANONICAL_BINDING_PATHS)
    actual_names = set(str(name) for name in bindings)
    for name in sorted(expected_names - actual_names):
        errors.append(f"required_binding_missing:{name}")
    for name in sorted(actual_names - expected_names):
        errors.append(f"unexpected_binding:{name}")
    for name in sorted(expected_names & actual_names):
        binding = bindings[name]
        try:
            actual_path = Path(str(binding["path"])).expanduser().resolve()
        except (KeyError, OSError):
            errors.append(f"binding_path_invalid:{name}")
            continue
        expected_path = CANONICAL_BINDING_PATHS[name].expanduser().resolve()
        if actual_path != expected_path:
            errors.append(f"binding_path_mismatch:{name}")
        static_expected = STATIC_BINDING_HASHES.get(name)
        if static_expected is not None and str(binding.get("sha256", "")) != static_expected:
            errors.append(f"binding_expected_sha256_mismatch:{name}")
    return {"valid": not errors, "errors": errors}


def claim_execution_marker(path: Path, payload: Mapping[str, Any]) -> None:
    content = (
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            default=alfred_stage001._json_default,
        )
        + "\n"
    ).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
    except FileExistsError as exc:
        raise Stage002Error(f"execution_marker_exists:{path}") from exc
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            path.unlink()
        except OSError:
            pass
        raise


def _read_fold_plan() -> pd.DataFrame:
    frame = pd.read_csv(STAGE001_FOLD_PLAN_PATH)
    for column in (
        "test_eval_date",
        "test_label_end",
        "train_start",
        "train_end",
        "train_label_end_max",
    ):
        frame[column] = pd.to_datetime(frame[column]).dt.normalize()
    return frame


def _parse_train_dates(value: object) -> pd.DatetimeIndex:
    raw = [item for item in str(value).split(",") if item]
    return pd.DatetimeIndex(pd.to_datetime(raw)).normalize()


def _input_identities(receipt: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for name, binding in receipt.get("bindings", {}).items():
        path = Path(str(binding["path"]))
        size, mtime_ns, digest = _sha256(path)
        result[str(name)] = {
            "path": str(path.resolve()),
            "size": size,
            "mtime_ns": mtime_ns,
            "sha256": digest,
            "expected_sha256": str(binding["sha256"]),
            "matches_expected": digest == str(binding["sha256"]),
        }
    return result


def _pit_audit(
    fold_plan: pd.DataFrame,
    label_calendar: pd.DataFrame,
) -> tuple[int, int]:
    label_end_by_date = label_calendar.set_index("eval_date")["label_end"]
    violation_rows = 0
    violation_folds = 0
    for row in fold_plan.itertuples(index=False):
        train_dates = _parse_train_dates(row.train_eval_dates)
        label_ends = label_end_by_date.reindex(train_dates)
        invalid = label_ends.isna() | label_ends.gt(pd.Timestamp(row.test_eval_date))
        count = int(invalid.sum())
        violation_rows += count
        violation_folds += int(count > 0)
    return violation_rows, violation_folds


def _verify_frozen_stage001_hashes() -> list[str]:
    errors: list[str] = []
    for path, expected in EXPECTED_STAGE001_HASHES.items():
        try:
            _, _, actual = _sha256(path)
        except (OSError, Stage002Error):
            errors.append(f"stage001_input_unreadable:{path.name}")
            continue
        if actual != expected:
            errors.append(f"stage001_sha256_mismatch:{path.name}")
    return errors


def _preflight_with_authorization(
    authorization: Mapping[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    if FINAL_OUTPUT_DIR.exists():
        errors.append(f"final_output_exists:{FINAL_OUTPUT_DIR}")
    if EXECUTION_MARKER_PATH.exists():
        errors.append(f"execution_marker_exists:{EXECUTION_MARKER_PATH}")
    if not authorization.get("valid", False):
        errors.extend(authorization.get("errors", []))
        bindings: set[str] = set()
    else:
        bindings = set(authorization["receipt"].get("bindings", {}))
        canonical = validate_canonical_bindings(authorization["receipt"])
        errors.extend(canonical["errors"])
    errors.extend(_verify_frozen_stage001_hashes())
    try:
        stage001_manifest = alfred_stage001.verify_artifact_bundle(STAGE001_DIR)
    except (OSError, alfred_stage001.Stage001Error) as exc:
        stage001_manifest = {"artifact_bundle_valid": False, "error": str(exc)}
        errors.append("stage001_manifest_invalid")
    try:
        stage001_summary = json.loads(
            STAGE001_SUMMARY_PATH.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        stage001_summary = {}
        errors.append("stage001_summary_unreadable")
    if stage001_summary.get("decision") != alfred_stage001.PASS_DECISION:
        errors.append("stage001_decision_not_pass")
    try:
        stage001_features = tuple(
            json.loads(
                STAGE001_FEATURE_CONTRACT_PATH.read_text(encoding="utf-8")
            )["model_features"]
        )
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        stage001_features = ()
    if stage001_features != EXPECTED_STATE_FEATURES:
        errors.append("stage001_feature_contract_mismatch")
    if xgboost.__version__ != EXPECTED_XGBOOST_VERSION:
        errors.append("xgboost_version_mismatch")
    if sklearn.__version__ != EXPECTED_SKLEARN_VERSION:
        errors.append("sklearn_version_mismatch")
    return {
        "valid": not errors,
        "errors": errors,
        "authorization_valid": bool(authorization.get("valid", False)),
        "authorization_binding_count": len(bindings),
        "stage001_manifest": stage001_manifest,
        "stage001_decision": stage001_summary.get("decision"),
        "xgboost_version": xgboost.__version__,
        "sklearn_version": sklearn.__version__,
        "label_value_read_count": 0,
        "model_fit_count": 0,
        "output_write_count": 0,
    }


def preflight() -> dict[str, Any]:
    authorization = validate_authorization_receipt(AUTHORIZATION_PATH)
    return _preflight_with_authorization(authorization)


def _write_dataframe(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def _publish_output(
    *,
    summary: Mapping[str, Any],
    identities: Mapping[str, Any],
    predictions: pd.DataFrame,
    fold_diagnostics: pd.DataFrame,
    monthly_effects: pd.DataFrame,
    yearly_effects: pd.DataFrame,
    selections: pd.DataFrame,
    authorization: Mapping[str, Any],
) -> None:
    final = FINAL_OUTPUT_DIR.resolve()
    if final.exists():
        raise Stage002Error(f"final_output_exists:{final}")
    final.parent.mkdir(parents=True, exist_ok=True)
    temporary = final.parent / f".{final.name}.tmp.{secrets.token_hex(16)}"
    temporary.mkdir(parents=False, exist_ok=False)
    try:
        alfred_stage001._atomic_write_json(temporary / "summary.json", summary)
        alfred_stage001._atomic_write_json(
            temporary / "input_identities.json",
            identities,
        )
        alfred_stage001._atomic_write_json(
            temporary / "model_params.json",
            {
                "formal_logistic": {
                    "C": 0.20,
                    "solver": "lbfgs",
                    "max_iter": 3000,
                    "random_state": 42,
                    "feature_count": 108,
                },
                "standalone_b": {
                    "features": list(EXPECTED_STATE_FEATURES),
                    "base_margin": False,
                    "candidate": False,
                },
                "residual_c": {
                    "features": list(EXPECTED_STATE_FEATURES),
                    "base_margin": "formal_lr_raw_margin",
                    "candidate": True,
                },
                "xgboost": XGBOOST_PARAMS,
                "xgboost_version": xgboost.__version__,
                "sklearn_version": sklearn.__version__,
                "top_n": TOP_N,
                "future_horizon_trading_days": HORIZON,
            },
        )
        alfred_stage001._atomic_write_json(
            temporary / "authorization_receipt.json",
            authorization,
        )
        _write_dataframe(temporary / "oos_predictions.csv", predictions)
        _write_dataframe(temporary / "fold_diagnostics.csv", fold_diagnostics)
        _write_dataframe(temporary / "monthly_effects.csv", monthly_effects)
        _write_dataframe(temporary / "yearly_effects.csv", yearly_effects)
        _write_dataframe(temporary / "top10_selections.csv", selections)
        (temporary / "report.md").write_text(
            "\n".join(
                [
                    "# Stage002 ALFRED global-risk development OOS",
                    "",
                    f"- Decision: `{summary['decision']}`",
                    f"- Folds/predictions: `{summary['fold_count']}/{summary['prediction_rows']}`",
                    f"- Changed A/C months: `{summary['changed_months']}`",
                    f"- C-A return delta: `{summary['sum_return_delta']}`",
                    "- C-A drawdown improvement: "
                    f"`{summary['sum_drawdown_improvement']}`",
                    f"- Failures: `{','.join(summary['failures']) or 'none'}`",
                    "- B is diagnostic only. Effects compare candidate C with formal A.",
                    "- This is a product-contribution proxy, not a true portfolio backtest.",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        alfred_stage001.write_artifact_manifest(temporary)
        alfred_stage001.verify_artifact_bundle(temporary)
        os.replace(temporary, final)
        alfred_stage001.verify_artifact_bundle(final)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def verify_output_bundle(
    directory: Path = FINAL_OUTPUT_DIR,
) -> dict[str, object]:
    return alfred_stage001.verify_artifact_bundle(directory)


def _publish_failure_bundle(
    *,
    run_nonce: str,
    error: Exception,
    partial_summary: Mapping[str, Any] | None,
) -> Path:
    failure = FINAL_OUTPUT_DIR.parent / (
        f"{FINAL_OUTPUT_DIR.name}_failure_{run_nonce[:16]}"
    )
    if failure.exists():
        raise Stage002Error(f"failure_output_exists:{failure}") from error
    temporary = failure.parent / f".{failure.name}.tmp.{secrets.token_hex(8)}"
    temporary.mkdir(parents=False, exist_ok=False)
    try:
        marker = json.loads(EXECUTION_MARKER_PATH.read_text(encoding="utf-8"))
        alfred_stage001._atomic_write_json(
            temporary / "execution_marker.json",
            marker,
        )
        alfred_stage001._atomic_write_json(
            temporary / "technical_failure.json",
            {
                "run_nonce": run_nonce,
                "error_type": type(error).__name__,
                "error": str(error),
                "traceback": traceback.format_exc(),
                "partial_summary": partial_summary,
                "rerun_allowed": False,
            },
        )
        alfred_stage001.write_artifact_manifest(temporary)
        alfred_stage001.verify_artifact_bundle(temporary)
        os.replace(temporary, failure)
        alfred_stage001.verify_artifact_bundle(failure)
        return failure
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def run_stage002() -> dict[str, Any]:
    authorization_result = validate_authorization_receipt(AUTHORIZATION_PATH)
    preflight_result = _preflight_with_authorization(authorization_result)
    if not preflight_result["valid"]:
        raise Stage002Error(
            f"stage002_preflight_failed:{','.join(preflight_result['errors'])}"
        )
    receipt = authorization_result["receipt"]
    run_nonce = secrets.token_hex(32)
    marker: dict[str, Any] = {
        "schema_version": 1,
        "line_id": "futures_trend_xgboost_alfred_global_risk_sector_residual",
        "stage": "Stage002",
        "run_nonce": run_nonce,
        "status": "started",
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "authorization_nonce": str(receipt["authorization_nonce"]),
        "authorization_receipt_sha256": authorization_result[
            "receipt_sha256"
        ],
        "label_read_started": False,
        "rerun_allowed": False,
    }
    claim_execution_marker(EXECUTION_MARKER_PATH, marker)
    partial_summary: dict[str, Any] | None = None
    try:
        identities_before = _input_identities(receipt)
        initial_mismatches = sum(
            not bool(identity["matches_expected"])
            for identity in identities_before.values()
        )
        if initial_mismatches:
            raise Stage002Error(
                f"input_identity_mismatch_before:{initial_mismatches}"
            )

        current, _, stage182 = model_contract.base._load_current_identity()
        formal = model_contract.base._load_formal_model_module()
        daily = formal.build_product_daily()
        feature_contract = json.loads(
            STAGE001_FEATURE_CONTRACT_PATH.read_text(encoding="utf-8")
        )
        state_features = list(feature_contract["model_features"])
        if tuple(state_features) != EXPECTED_STATE_FEATURES:
            raise Stage002Error("state_feature_contract_mismatch")
        state_panel = pd.read_csv(
            STAGE001_INTERACTION_PANEL_PATH,
            usecols=["eval_date", "product_vt_symbol", *state_features],
        )
        if (
            len(state_panel) != 1386
            or pd.to_datetime(state_panel["eval_date"]).nunique() != 77
            or state_panel["product_vt_symbol"].nunique() != 18
        ):
            raise Stage002Error("state_panel_shape_contract_failed")
        formal_feature_contract = json.loads(
            FORMAL_FEATURE_CONTRACT_PATH.read_text(encoding="utf-8")
        )
        expected_formal_features = list(formal_feature_contract["features"])
        if len(expected_formal_features) != 108:
            raise Stage002Error("formal_feature_contract_count_mismatch")

        featured = model_contract.causal.build_causal_rolling_features(daily)
        frozen_featured = select_frozen_feature_rows(
            featured,
            state_panel[["eval_date", "product_vt_symbol"]],
        )
        marker["label_read_started"] = True
        marker["label_read_started_at_utc"] = datetime.now(timezone.utc).isoformat()
        marker["authorized_label_key_count"] = int(len(state_panel))
        alfred_stage001._atomic_write_json(EXECUTION_MARKER_PATH, marker)
        label_table = build_frozen_label_table(
            daily,
            state_panel[["eval_date", "product_vt_symbol"]],
            horizon=HORIZON,
        )
        frozen_featured.rename(columns={"date": "eval_date"}, inplace=True)
        frozen_featured["eval_date"] = pd.to_datetime(
            frozen_featured["eval_date"]
        ).dt.normalize()
        formal_features = model_contract.causal.formal_feature_columns()
        formal_panel = frozen_featured.merge(
            label_table,
            on=["eval_date", "product_vt_symbol"],
            how="inner",
            validate="one_to_one",
        )
        formal_panel["cross_section_count"] = formal_panel.groupby(
            "eval_date"
        )["product_vt_symbol"].transform("size")
        formal_panel["future_rank_pct_60d"] = formal_panel.groupby(
            "eval_date"
        )["future_net_pnl_60d"].rank(method="average", pct=True)
        formal_panel["future_rank_centered_60d"] = (
            formal_panel["future_rank_pct_60d"] - 0.5
        )
        formal_panel[formal.TARGET_COLUMN] = (
            formal_panel["future_rank_centered_60d"] > 0.0
        ).astype("int64")
        formal_panel[formal.WEIGHT_COLUMN] = (
            formal_panel["future_rank_centered_60d"]
            .abs()
            .clip(lower=0.20, upper=0.60)
        )
        formal_panel[formal_features] = (
            formal_panel[formal_features]
            .replace([np.inf, -np.inf], np.nan)
            .fillna(0.0)
            .astype("float64")
        )
        formal_panel["eval_date"] = pd.to_datetime(
            formal_panel["eval_date"]
        ).dt.normalize()
        formal_panel["product_vt_symbol"] = formal_panel[
            "product_vt_symbol"
        ].astype(str)
        formal_panel.sort_values(
            ["eval_date", "product_vt_symbol"],
            inplace=True,
        )
        formal_panel.reset_index(drop=True, inplace=True)
        frozen_key_set = set(
            map(
                tuple,
                state_panel.assign(
                    eval_date=pd.to_datetime(state_panel["eval_date"]).dt.normalize(),
                    product_vt_symbol=state_panel["product_vt_symbol"].astype(str),
                )[["eval_date", "product_vt_symbol"]].itertuples(
                    index=False,
                    name=None,
                ),
            )
        )
        generated_key_set = set(
            label_table[["eval_date", "product_vt_symbol"]].itertuples(
                index=False,
                name=None,
            )
        )
        label_generated_missing_key_count = len(
            frozen_key_set - generated_key_set
        )
        label_generated_extra_key_count = len(
            generated_key_set - frozen_key_set
        )
        cutoff = pd.Timestamp(stage182["training_label_cutoff"]).normalize()
        formal_feature_contract_match = formal_features == expected_formal_features
        if (
            len(formal_panel) != 1386
            or formal_panel["eval_date"].nunique() != 77
            or formal_panel["product_vt_symbol"].nunique() != 18
            or not formal_panel["cross_section_count"].eq(18).all()
            or formal_panel["eval_date"].max() > cutoff
            or label_generated_missing_key_count != 0
            or label_generated_extra_key_count != 0
            or not formal_feature_contract_match
        ):
            raise Stage002Error("formal_labeled_panel_contract_failed")
        panel, join_audit = join_state_features(
            formal_panel,
            state_panel,
            state_features,
        )

        fold_plan = _read_fold_plan()
        if len(fold_plan) != 50:
            raise Stage002Error(f"fold_count_mismatch:{len(fold_plan)}")
        label_calendar = label_table[["eval_date", "label_end"]].drop_duplicates(
            "eval_date"
        )
        pit_rows, pit_folds = _pit_audit(fold_plan, label_calendar)

        prediction_frames: list[pd.DataFrame] = []
        fold_rows: list[dict[str, Any]] = []
        repeat_errors_b: list[float] = []
        repeat_errors_c: list[float] = []
        split_nodes_b = 0
        split_nodes_c = 0
        folds_with_splits_b = 0
        folds_with_splits_c = 0
        for fold in fold_plan.itertuples(index=False):
            train_dates = _parse_train_dates(fold.train_eval_dates)
            test_date = pd.Timestamp(fold.test_eval_date)
            train = panel[panel["eval_date"].isin(train_dates)].copy()
            test = panel[panel["eval_date"].eq(test_date)].copy()
            if len(train) != len(train_dates) * 18 or len(test) != 18:
                raise Stage002Error(f"fold_row_contract_failed:{fold.fold_id}")

            logistic = formal.train_model(train, formal_features)
            x_train_formal = formal.prepare_x(train, formal_features)
            x_test_formal = formal.prepare_x(test, formal_features)
            train_margin = np.asarray(
                logistic.decision_function(x_train_formal),
                dtype="float64",
            )
            test_margin = np.asarray(
                logistic.decision_function(x_test_formal),
                dtype="float64",
            )
            score_a = np.asarray(
                logistic.predict_proba(x_test_formal)[:, 1],
                dtype="float64",
            )
            x_train_state = train[state_features]
            x_test_state = test[state_features]
            target = train[formal.TARGET_COLUMN].to_numpy(dtype="int64")
            sample_weight = train[formal.WEIGHT_COLUMN].to_numpy(dtype="float64")
            standalone = fit_standalone_xgboost(
                x_train=x_train_state,
                y_train=target,
                sample_weight=sample_weight,
                x_test=x_test_state,
            )
            residual = fit_base_margin_residual(
                x_train=x_train_state,
                y_train=target,
                sample_weight=sample_weight,
                train_margin=train_margin,
                x_test=x_test_state,
                test_margin=test_margin,
            )
            repeat_errors_b.append(standalone.repeat_max_abs_error)
            repeat_errors_c.append(residual.repeat_max_abs_error)
            split_nodes_b += standalone.split_nodes
            split_nodes_c += residual.split_nodes
            folds_with_splits_b += int(standalone.split_nodes > 0)
            folds_with_splits_c += int(residual.split_nodes > 0)

            scored = test[
                [
                    "eval_date",
                    "product_vt_symbol",
                    formal.TARGET_COLUMN,
                    formal.WEIGHT_COLUMN,
                    "future_rank_centered_60d",
                    "future_net_pnl_60d",
                ]
            ].copy()
            scored.rename(
                columns={
                    formal.TARGET_COLUMN: "target",
                    formal.WEIGHT_COLUMN: "sample_weight",
                    "future_rank_centered_60d": "future_rank",
                },
                inplace=True,
            )
            scored["fold_id"] = str(fold.fold_id)
            scored["train_months"] = int(fold.train_months)
            scored["train_label_end_max"] = pd.Timestamp(
                fold.train_label_end_max
            )
            scored["score_a"] = score_a
            scored["score_b"] = standalone.probability
            scored["score_c"] = residual.probability
            scored["raw_margin_a"] = test_margin
            scored["raw_correction_c"] = residual.raw_correction
            prediction_frames.append(scored)
            fold_rows.append(
                {
                    "fold_id": str(fold.fold_id),
                    "test_eval_date": test_date,
                    "train_months": int(fold.train_months),
                    "train_rows": int(len(train)),
                    "test_rows": int(len(test)),
                    "train_label_end_max": pd.Timestamp(
                        fold.train_label_end_max
                    ),
                    "repeat_prediction_max_abs_error_b": (
                        standalone.repeat_max_abs_error
                    ),
                    "repeat_prediction_max_abs_error_c": (
                        residual.repeat_max_abs_error
                    ),
                    "split_nodes_b": standalone.split_nodes,
                    "split_nodes_c": residual.split_nodes,
                    "median_abs_correction_c": float(
                        np.median(np.abs(residual.raw_correction))
                    ),
                    "max_abs_correction_c": float(
                        np.max(np.abs(residual.raw_correction))
                    ),
                }
            )

        predictions = pd.concat(prediction_frames, ignore_index=True)
        predictions.sort_values(
            ["eval_date", "product_vt_symbol"],
            inplace=True,
        )
        predictions.reset_index(drop=True, inplace=True)
        fold_diagnostics = pd.DataFrame(fold_rows)
        future_paths = build_future_path_table(
            daily[["date", "product_vt_symbol", "net_pnl"]],
            predictions["eval_date"].unique(),
            horizon=HORIZON,
        )
        path_label_audit = audit_oos_path_consistency(
            predictions,
            future_paths,
            fold_plan,
            tolerance=1e-8,
        )
        monthly_effects, selections = build_monthly_effects(
            predictions,
            future_paths,
            top_n=TOP_N,
        )
        effect_summary, yearly_effects = summarize_effects(monthly_effects)
        model_summary = summarize_model_metrics(predictions)

        numeric_columns = [
            "target",
            "sample_weight",
            "future_rank",
            "future_net_pnl_60d",
            "score_a",
            "score_b",
            "score_c",
            "raw_margin_a",
            "raw_correction_c",
        ]
        nonfinite_output_cells = int(
            (~np.isfinite(predictions[numeric_columns].to_numpy(dtype="float64"))).sum()
        )
        score_stds = predictions.groupby("eval_date")[[
            "score_a",
            "score_b",
            "score_c",
        ]].std()
        products_per_test = predictions.groupby("eval_date")[
            "product_vt_symbol"
        ].nunique()
        abs_correction = predictions["raw_correction_c"].abs()

        identities_after = _input_identities(receipt)
        mismatch_count = sum(
            not bool(identity["matches_expected"])
            for identity in identities_before.values()
        ) + sum(
            identities_before[name]["sha256"]
            != identities_after[name]["sha256"]
            for name in identities_before
        )
        metrics: dict[str, Any] = {
            "current_release_id": current.get("release_id"),
            "current_strategy_id": current.get("strategy_version"),
            "xgboost_version": xgboost.__version__,
            "sklearn_version": sklearn.__version__,
            "input_identity_mismatch_count": int(mismatch_count),
            "authorization_valid": True,
            "stage001_manifest_valid": True,
            "formal_feature_contract_match": formal_feature_contract_match,
            "formal_feature_names_sha256": hashlib.sha256(
                json.dumps(
                    formal_features,
                    ensure_ascii=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest(),
            "stage001_source_aggregate_sha256": (
                "7d312d36015af3e6e09d0e6b3157f2a766bbb0a31ff26b20309161784404d20f"
            ),
            "fold_count": int(len(fold_plan)),
            "prediction_rows": int(len(predictions)),
            "minimum_products_per_test_month": int(products_per_test.min()),
            "maximum_products_per_test_month": int(products_per_test.max()),
            "formal_feature_count": int(len(formal_features)),
            "state_feature_count": int(len(state_features)),
            "logistic_fit_count": int(len(fold_plan)),
            "scaler_fit_count": int(len(fold_plan)),
            "standalone_xgboost_fit_count": int(len(fold_plan) * 2),
            "residual_xgboost_fit_count": int(len(fold_plan) * 2),
            "xgboost_fit_count": int(len(fold_plan) * 4),
            "state_panel_row_count": int(len(state_panel)),
            **join_audit,
            "label_generated_row_count": int(len(formal_panel)),
            "label_generated_missing_key_count": int(
                label_generated_missing_key_count
            ),
            "label_generated_extra_key_count": int(
                label_generated_extra_key_count
            ),
            "pit_violation_rows": int(pit_rows),
            "pit_violation_folds": int(pit_folds),
            "sealed_holdout_rows": int(label_generated_extra_key_count),
            "fixed_fu_model_rows": int(
                predictions["product_vt_symbol"].astype(str).eq("fu.SHFE").sum()
            ),
            "nonfinite_output_cells": nonfinite_output_cells,
            "nonpositive_score_std_months_a": int(
                score_stds["score_a"].le(0).sum()
            ),
            "nonpositive_score_std_months_b": int(
                score_stds["score_b"].le(0).sum()
            ),
            "nonpositive_score_std_months_c": int(
                score_stds["score_c"].le(0).sum()
            ),
            "repeat_prediction_max_abs_error_b": float(max(repeat_errors_b)),
            "repeat_prediction_max_abs_error_c": float(max(repeat_errors_c)),
            "xgboost_split_nodes_b": int(split_nodes_b),
            "xgboost_split_nodes_c": int(split_nodes_c),
            "xgboost_folds_with_splits_b": int(folds_with_splits_b),
            "xgboost_folds_with_splits_c": int(folds_with_splits_c),
            "median_abs_correction_c": float(abs_correction.median()),
            "max_abs_correction_c": float(abs_correction.max()),
            **model_summary,
            **effect_summary,
            **path_label_audit,
            "label_value_rows_read": int(len(formal_panel)),
            "development_oos_label_rows_used": int(len(predictions)),
            "true_engine_run_count": 0,
            "ctp_connection_count": 0,
            "order_api_call_count": 0,
            "production_write_count": 0,
        }
        gate_result = assess_gates(metrics)
        partial_summary = {**metrics, **gate_result}
        identities = {"before": identities_before, "after": identities_after}
        _publish_output(
            summary=partial_summary,
            identities=identities,
            predictions=predictions,
            fold_diagnostics=fold_diagnostics,
            monthly_effects=monthly_effects,
            yearly_effects=yearly_effects,
            selections=selections,
            authorization=receipt,
        )
        marker.update(
            {
                "status": "completed",
                "finished_at_utc": datetime.now(timezone.utc).isoformat(),
                "decision": partial_summary["decision"],
                "output_path": str(FINAL_OUTPUT_DIR.resolve()),
            }
        )
        alfred_stage001._atomic_write_json(EXECUTION_MARKER_PATH, marker)
        return partial_summary
    except Exception as exc:
        marker.update(
            {
                "status": "failed",
                "finished_at_utc": datetime.now(timezone.utc).isoformat(),
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
        )
        alfred_stage001._atomic_write_json(EXECUTION_MARKER_PATH, marker)
        failure = _publish_failure_bundle(
            run_nonce=run_nonce,
            error=exc,
            partial_summary=partial_summary,
        )
        raise Stage002Error(
            f"stage002_technical_failure:{failure}:{type(exc).__name__}:{exc}"
        ) from exc


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preflight-only", action="store_true")
    mode.add_argument("--authorized-development-oos", action="store_true")
    mode.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.preflight_only:
        result = preflight()
        if not result["valid"]:
            raise Stage002Error(
                f"stage002_preflight_failed:{','.join(result['errors'])}"
            )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if args.verify_only:
        result = verify_output_bundle()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    summary = run_stage002()
    print(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
            default=alfred_stage001._json_default,
        )
    )


if __name__ == "__main__":
    main()
