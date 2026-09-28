"""Qualify a fixed XGBoost/logistic ensemble against the frozen live AI model."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path
from types import ModuleType
from typing import Any, NamedTuple

import numpy as np
import pandas as pd
import sklearn
import xgboost
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier


LINE = Path(__file__).resolve().parents[1]
OUT = LINE / "artifacts/stage001_qualification"
MATERIALS = Path("/Users/bytedance/Desktop/person/vnpy_production_live/official_strategy_materials")
FORMAL_RELEASE_ID = "m0004_20260831T112631+0800_2485073e9594"
FORMAL = MATERIALS / "ai_top10_plus_fu_official_live_v1/releases" / FORMAL_RELEASE_ID
ORIGINAL = MATERIALS / (
    "official_live_stage847_c9_15w_stage819_05r_stop_retry_once/"
    "releases/m0015_20260825T205121+0800_c097d7836dd4"
)
FROZEN_CODE = FORMAL / "payload/examples/portfolio_backtesting"
ORIGINAL_METADATA = ORIGINAL / "payload/ai/stage182/summary.json"
PARITY_PANEL = (
    LINE.parent
    / "futures_trend_ai_score_attribution/artifacts/stage001_20260731/training_samples.csv"
)

DATE_COLUMN = "eval_date"
PRODUCT_COLUMN = "product_vt_symbol"
TARGET_COLUMN = "target_future_top_half_60d"
WEIGHT_COLUMN = "sample_weight_future_rank_60d"
FUTURE_PNL_COLUMN = "future_net_pnl_60d"
FUTURE_RANK_COLUMN = "future_rank_centered_60d"
MIN_TRAIN_MONTHS = 24
LABEL_GAP_DAYS = 92
TOP_N = 10
RANDOM_STATE = 42

XGBOOST_PARAMS: dict[str, Any] = {
    "objective": "binary:logistic",
    "eval_metric": "logloss",
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
    "random_state": RANDOM_STATE,
    "n_jobs": 1,
}


class MonthlySplit(NamedTuple):
    train_dates: pd.DatetimeIndex
    test_date: pd.Timestamp


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def file_identity(path: Path) -> dict[str, Any]:
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise RuntimeError(f"file changed while hashing: {path}")
    return {"path": str(path), "size": after.st_size, "sha256": digest.hexdigest()}


def build_monthly_splits(
    frame: pd.DataFrame,
    min_train_months: int = MIN_TRAIN_MONTHS,
    label_gap_days: int = LABEL_GAP_DAYS,
) -> list[MonthlySplit]:
    dates = pd.DatetimeIndex(sorted(pd.to_datetime(frame[DATE_COLUMN]).dt.normalize().unique()))
    splits: list[MonthlySplit] = []
    for test_date in dates:
        eligible = dates[dates <= test_date - pd.Timedelta(days=label_gap_days)]
        if len(eligible) >= min_train_months:
            splits.append(MonthlySplit(train_dates=eligible, test_date=pd.Timestamp(test_date)))
    return splits


def add_rank_fusion(
    frame: pd.DataFrame,
    score_a: str,
    score_b: str,
    weight_a: float = 0.5,
) -> pd.DataFrame:
    if not 0.0 <= weight_a <= 1.0:
        raise ValueError("weight_a must be in [0, 1]")
    result = frame.copy()
    result["score_a_percentile"] = result.groupby(DATE_COLUMN)[score_a].rank(
        method="average", pct=True, ascending=True
    )
    result["score_b_percentile"] = result.groupby(DATE_COLUMN)[score_b].rank(
        method="average", pct=True, ascending=True
    )
    result["score_fused"] = (
        weight_a * result["score_a_percentile"]
        + (1.0 - weight_a) * result["score_b_percentile"]
    )
    return result


def mean_topn_turnover(selected: dict[pd.Timestamp, tuple[str, ...]]) -> float:
    dates = sorted(selected)
    if len(dates) < 2:
        return 0.0
    values: list[float] = []
    for previous_date, current_date in zip(dates, dates[1:]):
        previous = set(selected[previous_date])
        current = set(selected[current_date])
        denominator = max(1, len(current))
        values.append(len(current - previous) / denominator)
    return float(np.mean(values))


def evaluate_promotion_gates(summary: dict[str, Any]) -> dict[str, Any]:
    gates = {
        "identity_and_determinism": bool(summary["identity_pass"] and summary["determinism_pass"]),
        "oos_months_ge_45": int(summary["oos_months"]) >= 45,
        "mean_rank_ic_strictly_better": float(summary["c_mean_rank_ic"]) > float(summary["a_mean_rank_ic"]),
        "median_rank_ic_noninferior": float(summary["c_median_rank_ic"]) >= float(summary["a_median_rank_ic"]),
        "top10_mean_future_pnl_strictly_better": float(summary["c_top10_mean_future_pnl"])
        > float(summary["a_top10_mean_future_pnl"]),
        "top10_p10_future_pnl_noninferior": float(summary["c_top10_p10_future_pnl"])
        >= float(summary["a_top10_p10_future_pnl"]),
        "top10_top_half_rate_noninferior": float(summary["c_top10_top_half_rate"])
        >= float(summary["a_top10_top_half_rate"]),
        "top10_turnover_le_105pct": float(summary["c_top10_turnover"])
        <= 1.05 * float(summary["a_top10_turnover"]) + 1e-12,
        "yearly_rank_ic_wins_ge_3": int(summary["yearly_c_wins"]) >= 3,
        "worst_year_rank_ic_delta_ge_minus_003": float(summary["worst_year_rank_ic_delta"]) >= -0.03,
    }
    return {"passed": all(gates.values()), "gates": gates}


def _load_frozen_model_code(vt_symbols: list[str]):
    sys.path.insert(0, str(FROZEN_CODE))
    module_path = FROZEN_CODE / "analyze_qmt_roll_ai_product_suitability_walkforward.py"
    spec = importlib.util.spec_from_file_location("frozen_ai_model_code", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load frozen model code: {module_path}")
    universe = ModuleType("qmt_universe")
    universe.VT_SYMBOLS = list(vt_symbols)
    previous_universe = sys.modules.get("qmt_universe")
    sys.modules["qmt_universe"] = universe
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        if previous_universe is None:
            sys.modules.pop("qmt_universe", None)
        else:
            sys.modules["qmt_universe"] = previous_universe
    return module


def _prepare_features(frame: pd.DataFrame, feature_columns: list[str]) -> pd.DataFrame:
    return (
        frame[feature_columns]
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0.0)
        .astype("float64")
    )


def _train_logistic(train: pd.DataFrame, feature_columns: list[str]) -> Pipeline:
    model = Pipeline(
        [
            ("scaler", StandardScaler()),
            (
                "classifier",
                LogisticRegression(
                    C=0.20,
                    solver="lbfgs",
                    max_iter=3000,
                    random_state=RANDOM_STATE,
                ),
            ),
        ]
    )
    model.fit(
        _prepare_features(train, feature_columns),
        train[TARGET_COLUMN].astype("int64"),
        classifier__sample_weight=train[WEIGHT_COLUMN].astype("float64"),
    )
    return model


def _train_xgboost(train: pd.DataFrame, feature_columns: list[str]) -> XGBClassifier:
    model = XGBClassifier(**XGBOOST_PARAMS)
    model.fit(
        _prepare_features(train, feature_columns),
        train[TARGET_COLUMN].astype("int64"),
        sample_weight=train[WEIGHT_COLUMN].astype("float64"),
        verbose=False,
    )
    return model


def _sorted_top(group: pd.DataFrame, score_column: str) -> pd.DataFrame:
    return group.sort_values(
        [score_column, PRODUCT_COLUMN], ascending=[False, True], kind="mergesort"
    ).head(TOP_N)


def _metric_rows(predictions: pd.DataFrame, score_columns: dict[str, str]) -> tuple[pd.DataFrame, dict[str, dict[pd.Timestamp, tuple[str, ...]]]]:
    rows: list[dict[str, Any]] = []
    selections: dict[str, dict[pd.Timestamp, tuple[str, ...]]] = {name: {} for name in score_columns}
    for eval_date, group in predictions.groupby(DATE_COLUMN, sort=True):
        for name, score_column in score_columns.items():
            score = group[score_column].astype("float64")
            rank_ic = score.corr(group[FUTURE_RANK_COLUMN], method="spearman")
            top = _sorted_top(group, score_column)
            selections[name][pd.Timestamp(eval_date)] = tuple(top[PRODUCT_COLUMN].astype(str))
            rows.append(
                {
                    "eval_date": pd.Timestamp(eval_date),
                    "year": int(pd.Timestamp(eval_date).year),
                    "arm": name,
                    "rank_ic": float(rank_ic),
                    "top10_products": ",".join(top[PRODUCT_COLUMN].astype(str)),
                    "top10_total_future_net_pnl_60d": float(top[FUTURE_PNL_COLUMN].sum()),
                    "top10_mean_future_net_pnl_60d": float(top[FUTURE_PNL_COLUMN].mean()),
                    "top10_future_top_half_rate": float(top[TARGET_COLUMN].mean()),
                }
            )
    return pd.DataFrame(rows), selections


def probability_metrics(
    actual: pd.Series,
    score: pd.Series,
    *,
    is_probability: bool,
) -> dict[str, float | None]:
    values = score.astype("float64")
    return {
        "roc_auc": float(roc_auc_score(actual.astype("int64"), values)),
        "log_loss": (
            float(log_loss(actual.astype("int64"), values.clip(1e-6, 1 - 1e-6), labels=[0, 1]))
            if is_probability
            else None
        ),
    }


def _arm_summary(
    predictions: pd.DataFrame,
    monthly: pd.DataFrame,
    selections: dict[str, dict[pd.Timestamp, tuple[str, ...]]],
    arm: str,
    score_column: str,
    is_probability: bool,
) -> dict[str, Any]:
    rows = monthly[monthly["arm"].eq(arm)]
    y = predictions[TARGET_COLUMN].astype("int64")
    score = predictions[score_column].astype("float64")
    probability = probability_metrics(y, score, is_probability=is_probability)
    return {
        "rows": int(len(predictions)),
        "months": int(rows[DATE_COLUMN].nunique()),
        "mean_rank_ic": float(rows["rank_ic"].mean()),
        "median_rank_ic": float(rows["rank_ic"].median()),
        "top10_mean_monthly_total_future_pnl": float(rows["top10_total_future_net_pnl_60d"].mean()),
        "top10_p10_monthly_total_future_pnl": float(rows["top10_total_future_net_pnl_60d"].quantile(0.10)),
        "top10_mean_selected_product_future_pnl": float(rows["top10_mean_future_net_pnl_60d"].mean()),
        "top10_top_half_rate": float(rows["top10_future_top_half_rate"].mean()),
        "top10_turnover": mean_topn_turnover(selections[arm]),
        **probability,
    }


def _render_report(summary: dict[str, Any]) -> str:
    arms = summary["arms"]
    gates = summary["promotion"]["gates"]
    lines = [
        "# Stage001 XGBoost融合预测资格报告",
        "",
        f"- 决策：`{summary['decision']}`",
        f"- OOS月份：`{summary['oos_months']}`",
        f"- 训练面板：`{summary['panel']['rows']}`行 / `{summary['panel']['months']}`个月 / `{summary['panel']['features']}`项特征",
        f"- 标签隔离：`{summary['configuration']['label_gap_days']}`自然日",
        "- 本阶段不是策略回测，不产生期末权益、收益率、最大回撤或Sharpe结论。",
        "",
        "## A/B/C结果",
        "",
        "| 臂 | 月均Rank IC | Rank IC中位数 | Top10月均未来净利润合计 | Top10未来净利润10%分位 | Top10上半区命中率 | Top10换入率 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for arm in ("A_logistic", "B_xgboost", "C_fusion"):
        value = arms[arm]
        lines.append(
            f"| {arm} | {value['mean_rank_ic']:.6f} | {value['median_rank_ic']:.6f} | "
            f"{value['top10_mean_monthly_total_future_pnl']:.2f} | "
            f"{value['top10_p10_monthly_total_future_pnl']:.2f} | "
            f"{value['top10_top_half_rate']:.4%} | {value['top10_turnover']:.4%} |"
        )
    lines.extend(["", "## 预声明门槛", ""])
    for name, passed in gates.items():
        lines.append(f"- `{'PASS' if passed else 'FAIL'}` `{name}`")
    lines.extend(
        [
            "",
            "## 解释边界",
            "",
            "- 未来净利润来自现有单品种策略标签，只是组合收益代理，不含真实Top10组合的资金、保证金、相关性和执行路径。",
            "- 尾部10%分位只是回撤代理，不能替代真引擎最大回撤。",
            "- 只有全部资格门通过，才允许进入Stage002 A/C策略回测。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    current_path = MATERIALS / "CURRENT.json"
    current = read_json(current_path)
    if current.get("release_id") != FORMAL_RELEASE_ID:
        raise RuntimeError("active formal release changed; refuse to move the research target silently")

    metadata = read_json(ORIGINAL_METADATA)
    source_paths = [Path(metadata["source_paths"][key]) for key in ("position_changes", "entry_candidate_snapshots")]
    frozen_model_path = FROZEN_CODE / "analyze_qmt_roll_ai_product_suitability_walkforward.py"
    frozen_universe_path = FROZEN_CODE / "qmt_universe.py"
    tracked_paths = [
        current_path,
        ORIGINAL_METADATA,
        frozen_model_path,
        frozen_universe_path,
        PARITY_PANEL,
        *source_paths,
        Path(__file__).resolve(),
    ]
    identities_before = {str(path): file_identity(path) for path in tracked_paths}
    for key, source_path in zip(("position_changes", "entry_candidate_snapshots"), source_paths):
        expected = metadata["source_identities"][key]
        actual = identities_before[str(source_path)]
        if actual["sha256"] != expected["sha256"] or actual["size"] != expected["size"]:
            raise RuntimeError(f"source identity mismatch: {key}")

    parity = pd.read_csv(PARITY_PANEL, parse_dates=[DATE_COLUMN]).sort_values([DATE_COLUMN, PRODUCT_COLUMN]).reset_index(drop=True)
    verified_vt_symbols = sorted(parity[PRODUCT_COLUMN].astype(str).unique())
    if len(verified_vt_symbols) != 18:
        raise RuntimeError("verified model universe changed")
    model_code = _load_frozen_model_code(verified_vt_symbols)
    model_code.POSITION_CHANGES_PATH = source_paths[0]
    model_code.ENTRY_SNAPSHOTS_PATH = source_paths[1]
    daily = model_code.build_product_daily()
    if pd.Timestamp(daily["date"].max()).date().isoformat() != metadata["source_max_date"]:
        raise RuntimeError("source max date mismatch")
    featured = model_code.add_rolling_features(daily)
    samples, feature_columns = model_code.build_monthly_samples(featured)
    cutoff = pd.Timestamp(metadata["training_label_cutoff"]).normalize()
    panel = samples[pd.to_datetime(samples[DATE_COLUMN]).dt.normalize() <= cutoff].copy()
    panel[DATE_COLUMN] = pd.to_datetime(panel[DATE_COLUMN]).dt.normalize()
    panel.sort_values([DATE_COLUMN, PRODUCT_COLUMN], inplace=True)
    panel.reset_index(drop=True, inplace=True)

    parity_columns = [DATE_COLUMN, PRODUCT_COLUMN, TARGET_COLUMN, WEIGHT_COLUMN, *feature_columns]
    if len(feature_columns) != 108 or len(panel) != 1368 or panel[DATE_COLUMN].nunique() != 76:
        raise RuntimeError("frozen panel shape changed")
    if not panel[parity_columns[:2]].equals(parity[parity_columns[:2]]):
        raise RuntimeError("panel date/product identity mismatch")
    numeric_error = float(
        np.max(
            np.abs(
                panel[parity_columns[2:]].to_numpy(dtype="float64")
                - parity[parity_columns[2:]].to_numpy(dtype="float64")
            )
        )
    )
    if numeric_error > 1e-10:
        raise RuntimeError(f"panel parity error: {numeric_error}")

    splits = build_monthly_splits(panel)
    predictions: list[pd.DataFrame] = []
    feature_importances: list[np.ndarray] = []
    determinism_error = 0.0
    for index, split in enumerate(splits, start=1):
        train = panel[panel[DATE_COLUMN].isin(split.train_dates)].copy()
        test = panel[panel[DATE_COLUMN].eq(split.test_date)].copy()
        if train[TARGET_COLUMN].nunique() != 2 or len(test) != 18:
            raise RuntimeError(f"invalid fold at {split.test_date.date()}")
        logistic = _train_logistic(train, feature_columns)
        boosted = _train_xgboost(train, feature_columns)
        x_test = _prepare_features(test, feature_columns)
        test["score_logistic"] = logistic.predict_proba(x_test)[:, 1]
        test["score_xgboost"] = boosted.predict_proba(x_test)[:, 1]
        feature_importances.append(np.asarray(boosted.feature_importances_, dtype="float64"))
        if index == len(splits):
            repeated = _train_xgboost(train, feature_columns).predict_proba(x_test)[:, 1]
            determinism_error = float(np.max(np.abs(repeated - test["score_xgboost"].to_numpy())))
        test["fold_train_start"] = split.train_dates.min()
        test["fold_train_end"] = split.train_dates.max()
        test["fold_train_months"] = len(split.train_dates)
        test["label_gap_days_actual"] = (split.test_date - split.train_dates.max()).days
        predictions.append(test)

    prediction_frame = pd.concat(predictions, ignore_index=True)
    prediction_frame = add_rank_fusion(prediction_frame, "score_logistic", "score_xgboost", weight_a=0.5)
    score_columns = {
        "A_logistic": "score_logistic",
        "B_xgboost": "score_xgboost",
        "C_fusion": "score_fused",
    }
    monthly, selections = _metric_rows(prediction_frame, score_columns)
    arms = {
        arm: _arm_summary(
            prediction_frame,
            monthly,
            selections,
            arm,
            score_column,
            is_probability=arm != "C_fusion",
        )
        for arm, score_column in score_columns.items()
    }
    yearly = monthly.groupby(["year", "arm"], as_index=False).agg(
        mean_rank_ic=("rank_ic", "mean"),
        mean_top10_total_future_net_pnl_60d=("top10_total_future_net_pnl_60d", "mean"),
        mean_top10_future_top_half_rate=("top10_future_top_half_rate", "mean"),
        months=(DATE_COLUMN, "nunique"),
    )
    rank_years = yearly.pivot(index="year", columns="arm", values="mean_rank_ic")
    yearly_delta = rank_years["C_fusion"] - rank_years["A_logistic"]
    gate_inputs = {
        "identity_pass": True,
        "determinism_pass": determinism_error <= 1e-12,
        "oos_months": int(prediction_frame[DATE_COLUMN].nunique()),
        "a_mean_rank_ic": arms["A_logistic"]["mean_rank_ic"],
        "c_mean_rank_ic": arms["C_fusion"]["mean_rank_ic"],
        "a_median_rank_ic": arms["A_logistic"]["median_rank_ic"],
        "c_median_rank_ic": arms["C_fusion"]["median_rank_ic"],
        "a_top10_mean_future_pnl": arms["A_logistic"]["top10_mean_monthly_total_future_pnl"],
        "c_top10_mean_future_pnl": arms["C_fusion"]["top10_mean_monthly_total_future_pnl"],
        "a_top10_p10_future_pnl": arms["A_logistic"]["top10_p10_monthly_total_future_pnl"],
        "c_top10_p10_future_pnl": arms["C_fusion"]["top10_p10_monthly_total_future_pnl"],
        "a_top10_top_half_rate": arms["A_logistic"]["top10_top_half_rate"],
        "c_top10_top_half_rate": arms["C_fusion"]["top10_top_half_rate"],
        "a_top10_turnover": arms["A_logistic"]["top10_turnover"],
        "c_top10_turnover": arms["C_fusion"]["top10_turnover"],
        "yearly_c_wins": int((yearly_delta > 0).sum()),
        "worst_year_rank_ic_delta": float(yearly_delta.min()),
    }
    promotion = evaluate_promotion_gates(gate_inputs)
    identities_after = {str(path): file_identity(path) for path in tracked_paths}
    source_unchanged = identities_before == identities_after
    if not source_unchanged:
        raise RuntimeError("source changed during qualification")

    mean_importance = np.mean(np.vstack(feature_importances), axis=0)
    importance = pd.DataFrame({"feature": feature_columns, "mean_gain_importance": mean_importance}).sort_values(
        ["mean_gain_importance", "feature"], ascending=[False, True]
    )
    decision = "stage001_prediction_qualification_pass_allow_stage002" if promotion["passed"] else "stage001_prediction_qualification_fail_stop_no_backtest"
    summary = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "decision": decision,
        "formal_release_id": FORMAL_RELEASE_ID,
        "panel": {
            "rows": int(len(panel)),
            "months": int(panel[DATE_COLUMN].nunique()),
            "products_per_month": 18,
            "features": len(feature_columns),
            "start": panel[DATE_COLUMN].min().date().isoformat(),
            "end": panel[DATE_COLUMN].max().date().isoformat(),
            "parity_max_abs_error": numeric_error,
        },
        "configuration": {
            "min_train_months": MIN_TRAIN_MONTHS,
            "label_gap_days": LABEL_GAP_DAYS,
            "top_n": TOP_N,
            "fusion_weight_logistic": 0.5,
            "fusion_weight_xgboost": 0.5,
            "logistic_c": 0.20,
            "xgboost": XGBOOST_PARAMS,
        },
        "oos_months": int(prediction_frame[DATE_COLUMN].nunique()),
        "oos_start": prediction_frame[DATE_COLUMN].min().date().isoformat(),
        "oos_end": prediction_frame[DATE_COLUMN].max().date().isoformat(),
        "minimum_actual_label_gap_days": int(prediction_frame["label_gap_days_actual"].min()),
        "determinism_max_abs_error": determinism_error,
        "arms": arms,
        "yearly_c_wins": gate_inputs["yearly_c_wins"],
        "worst_year_rank_ic_delta": gate_inputs["worst_year_rank_ic_delta"],
        "promotion": promotion,
        "identities": identities_before,
        "source_unchanged": source_unchanged,
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
            "https://xgboost.readthedocs.io/en/stable/parameter.html",
            "https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html",
            "https://scikit-learn.org/stable/modules/calibration.html",
        ],
    }
    prediction_columns = [
        DATE_COLUMN,
        PRODUCT_COLUMN,
        TARGET_COLUMN,
        WEIGHT_COLUMN,
        FUTURE_PNL_COLUMN,
        FUTURE_RANK_COLUMN,
        "score_logistic",
        "score_xgboost",
        "score_a_percentile",
        "score_b_percentile",
        "score_fused",
        "fold_train_start",
        "fold_train_end",
        "fold_train_months",
        "label_gap_days_actual",
    ]
    prediction_frame[prediction_columns].to_csv(OUT / "oos_predictions.csv", index=False)
    monthly.to_csv(OUT / "monthly_metrics.csv", index=False)
    yearly.to_csv(OUT / "yearly_metrics.csv", index=False)
    importance.to_csv(OUT / "xgboost_feature_importance.csv", index=False)
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    (OUT / "report.md").write_text(_render_report(summary))
    print(json.dumps({"decision": decision, "oos_months": summary["oos_months"], "arms": arms, "promotion": promotion}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
