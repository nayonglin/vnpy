"""Qualify a monthly XGBRanker on a fixed return/drawdown objective."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import sklearn
import xgboost
from xgboost import XGBRanker


LINE = Path(__file__).resolve().parents[1]
OUT = LINE / "artifacts/stage002_dual_objective_ranker"
STAGE001_PATH = LINE / "tools/stage001_xgboost_qualification.py"

DATE_COLUMN = "eval_date"
PRODUCT_COLUMN = "product_vt_symbol"
FUTURE_PNL_COLUMN = "future_net_pnl_60d"
FUTURE_DRAWDOWN_COLUMN = "future_max_drawdown_60d"
DUAL_UTILITY_COLUMN = "future_dual_utility_60d"
DUAL_RELEVANCE_COLUMN = "dual_relevance_60d"
FUTURE_HORIZON = 60
TOP_N = 10
DUAL_PNL_WEIGHT = 0.5
DUAL_DRAWDOWN_WEIGHT = 0.5
RANDOM_STATE = 42

XGBRANKER_PARAMS: dict[str, Any] = {
    "objective": "rank:ndcg",
    "eval_metric": "ndcg@10",
    "n_estimators": 120,
    "max_depth": 2,
    "learning_rate": 0.03,
    "min_child_weight": 12.0,
    "gamma": 0.10,
    "subsample": 0.80,
    "colsample_bytree": 0.60,
    "reg_alpha": 1.0,
    "reg_lambda": 10.0,
    "tree_method": "hist",
    "lambdarank_pair_method": "topk",
    "lambdarank_num_pair_per_sample": 10,
    "random_state": RANDOM_STATE,
    "n_jobs": 1,
}


def _load_stage001_module():
    spec = importlib.util.spec_from_file_location("stage001_for_stage002", STAGE001_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load Stage001 module: {STAGE001_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def forward_path_metrics(values: np.ndarray, horizon: int = FUTURE_HORIZON) -> tuple[np.ndarray, np.ndarray]:
    values = np.asarray(values, dtype="float64")
    future_sum = np.full(values.shape, np.nan, dtype="float64")
    future_drawdown = np.full(values.shape, np.nan, dtype="float64")
    for index in range(len(values)):
        if index + horizon >= len(values):
            continue
        path = values[index + 1 : index + 1 + horizon]
        cumulative = np.concatenate(([0.0], np.cumsum(path, dtype="float64")))
        drawdown = cumulative - np.maximum.accumulate(cumulative)
        future_sum[index] = float(path.sum())
        future_drawdown[index] = float(drawdown.min())
    return future_sum, future_drawdown


def add_future_path_metrics(daily: pd.DataFrame, horizon: int = FUTURE_HORIZON) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for _, group in daily.groupby(PRODUCT_COLUMN, sort=False):
        ordered = group.sort_values("date").copy()
        future_sum, future_drawdown = forward_path_metrics(
            ordered["net_pnl"].to_numpy(dtype="float64"), horizon=horizon
        )
        ordered["future_path_net_pnl_60d"] = future_sum
        ordered[FUTURE_DRAWDOWN_COLUMN] = future_drawdown
        frames.append(ordered)
    return pd.concat(frames, ignore_index=True)


def add_dual_objective_labels(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result[DATE_COLUMN] = pd.to_datetime(result[DATE_COLUMN]).dt.normalize()
    result.sort_values([DATE_COLUMN, PRODUCT_COLUMN], inplace=True)
    if result[[FUTURE_PNL_COLUMN, FUTURE_DRAWDOWN_COLUMN]].isna().any().any():
        raise ValueError("dual objective labels require complete future paths")
    result["future_pnl_percentile_60d"] = result.groupby(DATE_COLUMN)[FUTURE_PNL_COLUMN].rank(
        method="average", pct=True, ascending=True
    )
    result["future_drawdown_percentile_60d"] = result.groupby(DATE_COLUMN)[FUTURE_DRAWDOWN_COLUMN].rank(
        method="average", pct=True, ascending=True
    )
    result[DUAL_UTILITY_COLUMN] = (
        DUAL_PNL_WEIGHT * result["future_pnl_percentile_60d"]
        + DUAL_DRAWDOWN_WEIGHT * result["future_drawdown_percentile_60d"]
    )
    result[DUAL_RELEVANCE_COLUMN] = (
        result.groupby(DATE_COLUMN)[DUAL_UTILITY_COLUMN]
        .rank(method="first", ascending=True)
        .astype("int64")
        - 1
    )
    return result.reset_index(drop=True)


def _prepare_features(frame: pd.DataFrame, feature_columns: list[str]) -> pd.DataFrame:
    return (
        frame[feature_columns]
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0.0)
        .astype("float64")
    )


def ranker_training_arrays(
    frame: pd.DataFrame,
    feature_columns: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame, np.ndarray, np.ndarray]:
    ordered = frame.sort_values([DATE_COLUMN, PRODUCT_COLUMN]).reset_index(drop=True)
    x = _prepare_features(ordered, feature_columns)
    y = ordered[DUAL_RELEVANCE_COLUMN].to_numpy(dtype="int64")
    qid = pd.factorize(ordered[DATE_COLUMN], sort=True)[0].astype("int64")
    if np.any(np.diff(qid) < 0):
        raise RuntimeError("ranker qid groups are not contiguous")
    return ordered, x, y, qid


def train_ranker(train: pd.DataFrame, feature_columns: list[str]) -> XGBRanker:
    _, x, y, qid = ranker_training_arrays(train, feature_columns)
    model = XGBRanker(**XGBRANKER_PARAMS)
    model.fit(x, y, qid=qid, verbose=False)
    return model


def portfolio_forward_metrics(
    daily: pd.DataFrame,
    *,
    eval_date: pd.Timestamp,
    products: tuple[str, ...],
    horizon: int = FUTURE_HORIZON,
) -> dict[str, float | int]:
    eval_date = pd.Timestamp(eval_date).normalize()
    future_dates = pd.DatetimeIndex(
        sorted(pd.to_datetime(daily.loc[pd.to_datetime(daily["date"]) > eval_date, "date"]).dt.normalize().unique())
    )[:horizon]
    if len(future_dates) != horizon:
        raise RuntimeError(f"incomplete portfolio future path: {eval_date.date()}:{len(future_dates)}")
    selected = daily[
        daily[PRODUCT_COLUMN].astype(str).isin(products)
        & pd.to_datetime(daily["date"]).dt.normalize().isin(future_dates)
    ].copy()
    path = (
        selected.groupby(pd.to_datetime(selected["date"]).dt.normalize())["net_pnl"]
        .sum()
        .reindex(future_dates, fill_value=0.0)
        .to_numpy(dtype="float64")
    )
    cumulative = np.concatenate(([0.0], np.cumsum(path, dtype="float64")))
    drawdown = cumulative - np.maximum.accumulate(cumulative)
    return {
        "future_net_pnl": float(path.sum()),
        "future_max_drawdown": float(drawdown.min()),
        "trading_days": int(len(path)),
    }


def evaluate_candidate_gates(summary: dict[str, Any]) -> dict[str, Any]:
    gates = {
        "identity_path_and_determinism": bool(
            summary["identity_pass"]
            and summary["determinism_pass"]
            and summary["path_parity_pass"]
        ),
        "oos_months_ge_45": int(summary["oos_months"]) >= 45,
        "mean_dual_rank_ic_strictly_better": float(summary["candidate_mean_dual_rank_ic"])
        > float(summary["a_mean_dual_rank_ic"]),
        "median_dual_rank_ic_noninferior": float(summary["candidate_median_dual_rank_ic"])
        >= float(summary["a_median_dual_rank_ic"]),
        "top10_mean_future_pnl_strictly_better": float(summary["candidate_top10_mean_future_pnl"])
        > float(summary["a_top10_mean_future_pnl"]),
        "top10_p10_future_pnl_noninferior": float(summary["candidate_top10_p10_future_pnl"])
        >= float(summary["a_top10_p10_future_pnl"]),
        "top10_mean_future_drawdown_strictly_better": float(summary["candidate_top10_mean_future_drawdown"])
        > float(summary["a_top10_mean_future_drawdown"]),
        "top10_p10_future_drawdown_noninferior": float(summary["candidate_top10_p10_future_drawdown"])
        >= float(summary["a_top10_p10_future_drawdown"]),
        "top10_turnover_le_105pct": float(summary["candidate_top10_turnover"])
        <= 1.05 * float(summary["a_top10_turnover"]) + 1e-12,
        "yearly_dual_rank_ic_wins_ge_3": int(summary["yearly_candidate_wins"]) >= 3,
        "worst_year_dual_rank_ic_delta_ge_minus_003": float(summary["worst_year_dual_rank_ic_delta"])
        >= -0.03,
    }
    return {"passed": all(gates.values()), "gates": gates}


def _sorted_top(group: pd.DataFrame, score_column: str) -> pd.DataFrame:
    return group.sort_values(
        [score_column, PRODUCT_COLUMN], ascending=[False, True], kind="mergesort"
    ).head(TOP_N)


def _mean_turnover(selected: dict[pd.Timestamp, tuple[str, ...]]) -> float:
    dates = sorted(selected)
    values = [
        len(set(selected[current]) - set(selected[previous])) / max(1, len(selected[current]))
        for previous, current in zip(dates, dates[1:])
    ]
    return float(np.mean(values)) if values else 0.0


def build_metric_rows(
    predictions: pd.DataFrame,
    daily: pd.DataFrame,
    score_columns: dict[str, str],
) -> tuple[pd.DataFrame, dict[str, dict[pd.Timestamp, tuple[str, ...]]]]:
    rows: list[dict[str, Any]] = []
    selections: dict[str, dict[pd.Timestamp, tuple[str, ...]]] = {arm: {} for arm in score_columns}
    for eval_date, group in predictions.groupby(DATE_COLUMN, sort=True):
        for arm, score_column in score_columns.items():
            top = _sorted_top(group, score_column)
            products = tuple(top[PRODUCT_COLUMN].astype(str))
            path = portfolio_forward_metrics(
                daily,
                eval_date=pd.Timestamp(eval_date),
                products=products,
            )
            selections[arm][pd.Timestamp(eval_date)] = products
            rows.append(
                {
                    DATE_COLUMN: pd.Timestamp(eval_date),
                    "year": int(pd.Timestamp(eval_date).year),
                    "arm": arm,
                    "dual_rank_ic": float(
                        group[score_column].corr(group[DUAL_UTILITY_COLUMN], method="spearman")
                    ),
                    "top10_products": ",".join(products),
                    "top10_future_net_pnl_60d": float(path["future_net_pnl"]),
                    "top10_future_max_drawdown_60d": float(path["future_max_drawdown"]),
                }
            )
    return pd.DataFrame(rows), selections


def summarize_arm(
    monthly: pd.DataFrame,
    selections: dict[str, dict[pd.Timestamp, tuple[str, ...]]],
    arm: str,
) -> dict[str, Any]:
    rows = monthly[monthly["arm"].eq(arm)]
    return {
        "months": int(rows[DATE_COLUMN].nunique()),
        "mean_dual_rank_ic": float(rows["dual_rank_ic"].mean()),
        "median_dual_rank_ic": float(rows["dual_rank_ic"].median()),
        "top10_mean_future_net_pnl_60d": float(rows["top10_future_net_pnl_60d"].mean()),
        "top10_p10_future_net_pnl_60d": float(rows["top10_future_net_pnl_60d"].quantile(0.10)),
        "top10_mean_future_max_drawdown_60d": float(rows["top10_future_max_drawdown_60d"].mean()),
        "top10_p10_future_max_drawdown_60d": float(rows["top10_future_max_drawdown_60d"].quantile(0.10)),
        "top10_turnover": _mean_turnover(selections[arm]),
    }


def build_gate_inputs(
    arms: dict[str, dict[str, Any]],
    yearly: pd.DataFrame,
    candidate: str,
    *,
    identity_pass: bool,
    determinism_pass: bool,
    path_parity_pass: bool,
    oos_months: int,
) -> dict[str, Any]:
    baseline = arms["A_logistic"]
    challenger = arms[candidate]
    pivot = yearly.pivot(index="year", columns="arm", values="mean_dual_rank_ic")
    delta = pivot[candidate] - pivot["A_logistic"]
    return {
        "identity_pass": identity_pass,
        "determinism_pass": determinism_pass,
        "path_parity_pass": path_parity_pass,
        "oos_months": oos_months,
        "a_mean_dual_rank_ic": baseline["mean_dual_rank_ic"],
        "candidate_mean_dual_rank_ic": challenger["mean_dual_rank_ic"],
        "a_median_dual_rank_ic": baseline["median_dual_rank_ic"],
        "candidate_median_dual_rank_ic": challenger["median_dual_rank_ic"],
        "a_top10_mean_future_pnl": baseline["top10_mean_future_net_pnl_60d"],
        "candidate_top10_mean_future_pnl": challenger["top10_mean_future_net_pnl_60d"],
        "a_top10_p10_future_pnl": baseline["top10_p10_future_net_pnl_60d"],
        "candidate_top10_p10_future_pnl": challenger["top10_p10_future_net_pnl_60d"],
        "a_top10_mean_future_drawdown": baseline["top10_mean_future_max_drawdown_60d"],
        "candidate_top10_mean_future_drawdown": challenger["top10_mean_future_max_drawdown_60d"],
        "a_top10_p10_future_drawdown": baseline["top10_p10_future_max_drawdown_60d"],
        "candidate_top10_p10_future_drawdown": challenger["top10_p10_future_max_drawdown_60d"],
        "a_top10_turnover": baseline["top10_turnover"],
        "candidate_top10_turnover": challenger["top10_turnover"],
        "yearly_candidate_wins": int((delta > 0).sum()),
        "worst_year_dual_rank_ic_delta": float(delta.min()),
    }


def _file_identity(path: Path) -> dict[str, Any]:
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise RuntimeError(f"file changed while hashing: {path}")
    return {"path": str(path), "size": after.st_size, "sha256": digest.hexdigest()}


def _render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Stage002 收益/回撤双目标XGBRanker资格报告",
        "",
        f"- 决策：`{summary['decision']}`",
        f"- 晋级臂：`{summary['qualified_arm'] or '无'}`",
        f"- OOS月份：`{summary['oos_months']}`",
        f"- 路径净利润复算最大误差：`{summary['path_parity_max_abs_error']:.3g}`",
        "- 本阶段仍是预测资格赛，不是策略回测。",
        "",
        "## A/B/C指标",
        "",
        "| 臂 | 双目标Rank IC均值 | 中位数 | Top10月均未来净利润 | 净利润10%分位 | Top10月均未来最大回撤 | 回撤10%分位 | 换入率 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for arm in ("A_logistic", "B_ranker", "C_fusion"):
        value = summary["arms"][arm]
        lines.append(
            f"| {arm} | {value['mean_dual_rank_ic']:.6f} | {value['median_dual_rank_ic']:.6f} | "
            f"{value['top10_mean_future_net_pnl_60d']:.2f} | {value['top10_p10_future_net_pnl_60d']:.2f} | "
            f"{value['top10_mean_future_max_drawdown_60d']:.2f} | {value['top10_p10_future_max_drawdown_60d']:.2f} | "
            f"{value['top10_turnover']:.4%} |"
        )
    for candidate in ("B_ranker", "C_fusion"):
        lines.extend(["", f"## {candidate}相对A门槛", ""])
        for name, passed in summary["qualification"][candidate]["gates"].items():
            lines.append(f"- `{'PASS' if passed else 'FAIL'}` `{name}`")
    lines.extend(
        [
            "",
            "## 边界",
            "",
            "- 聚合路径来自现有单品种策略每日净利润求和，是进入真引擎前的资格代理。",
            "- 固定fu、保证金竞争、相关性门、整数手和实际交易成本只能由后续真引擎确认。",
            "- 资格失败不得通过修改双目标权重、rank参数或TopN救援。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    stage001 = _load_stage001_module()
    OUT.mkdir(parents=True, exist_ok=True)
    current_path = stage001.MATERIALS / "CURRENT.json"
    current = stage001.read_json(current_path)
    if current.get("release_id") != stage001.FORMAL_RELEASE_ID:
        raise RuntimeError("active formal release changed; refuse silent target drift")
    metadata = stage001.read_json(stage001.ORIGINAL_METADATA)
    source_paths = [
        Path(metadata["source_paths"][key])
        for key in ("position_changes", "entry_candidate_snapshots")
    ]
    tracked_paths = [
        current_path,
        stage001.ORIGINAL_METADATA,
        stage001.FROZEN_CODE / "analyze_qmt_roll_ai_product_suitability_walkforward.py",
        stage001.FROZEN_CODE / "qmt_universe.py",
        stage001.PARITY_PANEL,
        STAGE001_PATH,
        *source_paths,
        Path(__file__).resolve(),
    ]
    identities_before = {str(path): _file_identity(path) for path in tracked_paths}
    for key, source_path in zip(("position_changes", "entry_candidate_snapshots"), source_paths):
        expected = metadata["source_identities"][key]
        actual = identities_before[str(source_path)]
        if actual["sha256"] != expected["sha256"] or actual["size"] != expected["size"]:
            raise RuntimeError(f"source identity mismatch: {key}")

    parity = pd.read_csv(stage001.PARITY_PANEL, parse_dates=[DATE_COLUMN]).sort_values(
        [DATE_COLUMN, PRODUCT_COLUMN]
    ).reset_index(drop=True)
    products = sorted(parity[PRODUCT_COLUMN].astype(str).unique())
    model_code = stage001._load_frozen_model_code(products)
    model_code.POSITION_CHANGES_PATH = source_paths[0]
    model_code.ENTRY_SNAPSHOTS_PATH = source_paths[1]
    daily = model_code.build_product_daily()
    featured = model_code.add_rolling_features(daily)
    samples, feature_columns = model_code.build_monthly_samples(featured)
    cutoff = pd.Timestamp(metadata["training_label_cutoff"]).normalize()
    panel = samples[pd.to_datetime(samples[DATE_COLUMN]).dt.normalize() <= cutoff].copy()
    panel[DATE_COLUMN] = pd.to_datetime(panel[DATE_COLUMN]).dt.normalize()
    panel.sort_values([DATE_COLUMN, PRODUCT_COLUMN], inplace=True)
    panel.reset_index(drop=True, inplace=True)
    parity_columns = [
        DATE_COLUMN,
        PRODUCT_COLUMN,
        stage001.TARGET_COLUMN,
        stage001.WEIGHT_COLUMN,
        *feature_columns,
    ]
    if len(panel) != 1368 or panel[DATE_COLUMN].nunique() != 76 or len(feature_columns) != 108:
        raise RuntimeError("verified panel shape changed")
    if not panel[parity_columns[:2]].equals(parity[parity_columns[:2]]):
        raise RuntimeError("panel identity mismatch")
    panel_parity_error = float(
        np.max(
            np.abs(
                panel[parity_columns[2:]].to_numpy(dtype="float64")
                - parity[parity_columns[2:]].to_numpy(dtype="float64")
            )
        )
    )
    if panel_parity_error > 1e-10:
        raise RuntimeError(f"panel parity error: {panel_parity_error}")

    path_daily = add_future_path_metrics(daily)
    path_labels = path_daily.rename(columns={"date": DATE_COLUMN})[
        [DATE_COLUMN, PRODUCT_COLUMN, "future_path_net_pnl_60d", FUTURE_DRAWDOWN_COLUMN]
    ]
    panel = panel.merge(path_labels, on=[DATE_COLUMN, PRODUCT_COLUMN], how="left", validate="one_to_one")
    path_parity_error = float(
        np.max(
            np.abs(
                panel[FUTURE_PNL_COLUMN].to_numpy(dtype="float64")
                - panel["future_path_net_pnl_60d"].to_numpy(dtype="float64")
            )
        )
    )
    if not np.isfinite(path_parity_error) or path_parity_error > 1e-10:
        raise RuntimeError(f"future path pnl parity failed: {path_parity_error}")
    panel = add_dual_objective_labels(panel)
    for _, group in panel.groupby(DATE_COLUMN):
        if sorted(group[DUAL_RELEVANCE_COLUMN].tolist()) != list(range(18)):
            raise RuntimeError("monthly relevance labels are incomplete")

    splits = stage001.build_monthly_splits(panel)
    prediction_rows: list[pd.DataFrame] = []
    importances: list[np.ndarray] = []
    determinism_error = 0.0
    for index, split in enumerate(splits, start=1):
        train = panel[panel[DATE_COLUMN].isin(split.train_dates)].copy()
        test = panel[panel[DATE_COLUMN].eq(split.test_date)].copy()
        logistic = stage001._train_logistic(train, feature_columns)
        ranker = train_ranker(train, feature_columns)
        x_test = _prepare_features(test, feature_columns)
        test["score_logistic"] = logistic.predict_proba(x_test)[:, 1]
        test["score_ranker"] = ranker.predict(x_test)
        importances.append(np.asarray(ranker.feature_importances_, dtype="float64"))
        if index == len(splits):
            repeated = train_ranker(train, feature_columns).predict(x_test)
            determinism_error = float(np.max(np.abs(repeated - test["score_ranker"].to_numpy())))
        test["fold_train_start"] = split.train_dates.min()
        test["fold_train_end"] = split.train_dates.max()
        test["fold_train_months"] = len(split.train_dates)
        test["label_gap_days_actual"] = (split.test_date - split.train_dates.max()).days
        prediction_rows.append(test)

    predictions = pd.concat(prediction_rows, ignore_index=True)
    predictions = stage001.add_rank_fusion(
        predictions, "score_logistic", "score_ranker", weight_a=0.5
    )
    score_columns = {
        "A_logistic": "score_logistic",
        "B_ranker": "score_ranker",
        "C_fusion": "score_fused",
    }
    monthly, selections = build_metric_rows(predictions, daily, score_columns)
    arms = {arm: summarize_arm(monthly, selections, arm) for arm in score_columns}
    yearly = monthly.groupby(["year", "arm"], as_index=False).agg(
        mean_dual_rank_ic=("dual_rank_ic", "mean"),
        mean_top10_future_net_pnl_60d=("top10_future_net_pnl_60d", "mean"),
        mean_top10_future_max_drawdown_60d=("top10_future_max_drawdown_60d", "mean"),
        months=(DATE_COLUMN, "nunique"),
    )
    oos_months = int(predictions[DATE_COLUMN].nunique())
    qualification: dict[str, dict[str, Any]] = {}
    gate_inputs: dict[str, dict[str, Any]] = {}
    for candidate in ("B_ranker", "C_fusion"):
        inputs = build_gate_inputs(
            arms,
            yearly,
            candidate,
            identity_pass=True,
            determinism_pass=determinism_error <= 1e-12,
            path_parity_pass=path_parity_error <= 1e-10,
            oos_months=oos_months,
        )
        gate_inputs[candidate] = inputs
        qualification[candidate] = evaluate_candidate_gates(inputs)
    qualified_arm = (
        "C_fusion"
        if qualification["C_fusion"]["passed"]
        else "B_ranker"
        if qualification["B_ranker"]["passed"]
        else None
    )
    decision = (
        f"stage002_qualification_pass_{qualified_arm}_allow_true_engine"
        if qualified_arm
        else "stage002_dual_objective_ranker_fail_stop_no_backtest"
    )

    identities_after = {str(path): _file_identity(path) for path in tracked_paths}
    if identities_before != identities_after:
        raise RuntimeError("source changed during Stage002")
    importance = pd.DataFrame(
        {
            "feature": feature_columns,
            "mean_gain_importance": np.mean(np.vstack(importances), axis=0),
        }
    ).sort_values(["mean_gain_importance", "feature"], ascending=[False, True])
    summary = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "decision": decision,
        "qualified_arm": qualified_arm,
        "formal_release_id": stage001.FORMAL_RELEASE_ID,
        "panel": {
            "rows": int(len(panel)),
            "months": int(panel[DATE_COLUMN].nunique()),
            "products_per_month": 18,
            "features": len(feature_columns),
            "panel_parity_max_abs_error": panel_parity_error,
        },
        "configuration": {
            "future_horizon_trading_days": FUTURE_HORIZON,
            "dual_pnl_weight": DUAL_PNL_WEIGHT,
            "dual_drawdown_weight": DUAL_DRAWDOWN_WEIGHT,
            "min_train_months": stage001.MIN_TRAIN_MONTHS,
            "label_gap_days": stage001.LABEL_GAP_DAYS,
            "top_n": TOP_N,
            "fusion_weight_logistic": 0.5,
            "fusion_weight_ranker": 0.5,
            "xgboost_ranker": XGBRANKER_PARAMS,
        },
        "oos_months": oos_months,
        "oos_start": predictions[DATE_COLUMN].min().date().isoformat(),
        "oos_end": predictions[DATE_COLUMN].max().date().isoformat(),
        "minimum_actual_label_gap_days": int(predictions["label_gap_days_actual"].min()),
        "path_parity_max_abs_error": path_parity_error,
        "determinism_max_abs_error": determinism_error,
        "arms": arms,
        "gate_inputs": gate_inputs,
        "qualification": qualification,
        "identities": identities_before,
        "source_unchanged": True,
        "versions": {
            "python": sys.version,
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "sklearn": sklearn.__version__,
            "xgboost": xgboost.__version__,
        },
        "safety": {
            "runs_strategy_backtest": False,
            "writes_production": False,
            "ctp_connected": False,
            "order_api_called_count": 0,
            "send_order_api_called_count": 0,
            "cancel_order_api_called_count": 0,
        },
        "references": [
            "https://github.com/dmlc/xgboost/blob/master/doc/tutorials/learning_to_rank.rst",
            "https://github.com/dmlc/xgboost/blob/master/doc/parameter.rst",
            "https://academic.oup.com/rfs/advance-article/doi/10.1093/rfs/hhag022/8524346",
        ],
    }
    prediction_columns = [
        DATE_COLUMN,
        PRODUCT_COLUMN,
        FUTURE_PNL_COLUMN,
        FUTURE_DRAWDOWN_COLUMN,
        DUAL_UTILITY_COLUMN,
        DUAL_RELEVANCE_COLUMN,
        "score_logistic",
        "score_ranker",
        "score_a_percentile",
        "score_b_percentile",
        "score_fused",
        "fold_train_start",
        "fold_train_end",
        "fold_train_months",
        "label_gap_days_actual",
    ]
    predictions[prediction_columns].to_csv(OUT / "oos_predictions.csv", index=False)
    monthly.to_csv(OUT / "monthly_metrics.csv", index=False)
    yearly.to_csv(OUT / "yearly_metrics.csv", index=False)
    importance.to_csv(OUT / "xgboost_ranker_feature_importance.csv", index=False)
    panel[
        [
            DATE_COLUMN,
            PRODUCT_COLUMN,
            FUTURE_PNL_COLUMN,
            FUTURE_DRAWDOWN_COLUMN,
            "future_pnl_percentile_60d",
            "future_drawdown_percentile_60d",
            DUAL_UTILITY_COLUMN,
            DUAL_RELEVANCE_COLUMN,
        ]
    ].to_csv(OUT / "dual_objective_labels.csv", index=False)
    (OUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )
    (OUT / "report.md").write_text(_render_report(summary))
    print(
        json.dumps(
            {
                "decision": decision,
                "qualified_arm": qualified_arm,
                "oos_months": oos_months,
                "arms": arms,
                "qualification": qualification,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
