"""Rebuild the frozen ranker experiment with actual forward-label end purging."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, NamedTuple

import numpy as np
import pandas as pd


LINE = Path(__file__).resolve().parents[1]
OUT = LINE / "artifacts/stage006_pit_corrected_ranker"
STAGE002_PATH = LINE / "tools/stage002_dual_objective_ranker.py"
STAGE003_PATH = LINE / "tools/stage003_two_month_confirmed_ranker.py"
STAGE002_OLD_PREDICTIONS = LINE / "artifacts/stage002_dual_objective_ranker/oos_predictions.csv"
STAGE003_OLD_PREDICTIONS = (
    LINE / "artifacts/stage003_two_month_confirmed_ranker/confirmed_predictions.csv"
)
PREREGISTRATION_PATH = LINE / "stages/20260901_1612_stage006_pit_corrected_ranker.md"
REVIEW_PATH = LINE / "reviews/20260901_stage004_stage005_independent_review.md"

DATE_COLUMN = "eval_date"
PRODUCT_COLUMN = "product_vt_symbol"
FUTURE_LABEL_END_COLUMN = "future_label_end_60d"

_STAGE002_MODULE = None
_STAGE003_MODULE = None


def _load_stage002_module():
    global _STAGE002_MODULE
    if _STAGE002_MODULE is not None:
        return _STAGE002_MODULE
    spec = importlib.util.spec_from_file_location("stage002_for_stage006", STAGE002_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load Stage002 module: {STAGE002_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _STAGE002_MODULE = module
    return module


stage002 = _load_stage002_module()
XGBRANKER_PARAMS = stage002.XGBRANKER_PARAMS
DUAL_PNL_WEIGHT = stage002.DUAL_PNL_WEIGHT
DUAL_DRAWDOWN_WEIGHT = stage002.DUAL_DRAWDOWN_WEIGHT
TOP_N = stage002.TOP_N
evaluate_candidate_gates = stage002.evaluate_candidate_gates


def _load_stage003_module():
    global _STAGE003_MODULE
    if _STAGE003_MODULE is not None:
        return _STAGE003_MODULE
    spec = importlib.util.spec_from_file_location("stage003_for_stage006", STAGE003_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load Stage003 module: {STAGE003_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    _STAGE003_MODULE = module
    return module


class PitMonthlySplit(NamedTuple):
    train_dates: pd.DatetimeIndex
    test_date: pd.Timestamp
    train_label_end_max: pd.Timestamp
    purged_dates: pd.DatetimeIndex


def add_future_path_metrics_and_label_end(
    daily: pd.DataFrame,
    *,
    horizon: int = stage002.FUTURE_HORIZON,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for _, group in daily.groupby(PRODUCT_COLUMN, sort=False):
        ordered = group.sort_values("date").copy()
        future_sum, future_drawdown = stage002.forward_path_metrics(
            ordered["net_pnl"].to_numpy(dtype="float64"), horizon=horizon
        )
        ordered["future_path_net_pnl_60d"] = future_sum
        ordered[stage002.FUTURE_DRAWDOWN_COLUMN] = future_drawdown
        ordered[FUTURE_LABEL_END_COLUMN] = pd.to_datetime(ordered["date"]).shift(-horizon)
        frames.append(ordered)
    return pd.concat(frames, ignore_index=True)


def build_pit_monthly_splits(
    frame: pd.DataFrame,
    *,
    min_train_months: int = 24,
) -> list[PitMonthlySplit]:
    required = {DATE_COLUMN, PRODUCT_COLUMN, FUTURE_LABEL_END_COLUMN}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"missing PIT columns: {sorted(missing)}")
    panel = frame[list(required)].copy()
    panel[DATE_COLUMN] = pd.to_datetime(panel[DATE_COLUMN]).dt.normalize()
    panel[FUTURE_LABEL_END_COLUMN] = pd.to_datetime(panel[FUTURE_LABEL_END_COLUMN]).dt.normalize()
    dates = pd.DatetimeIndex(sorted(panel[DATE_COLUMN].unique()))
    grouped = panel.groupby(DATE_COLUMN)[FUTURE_LABEL_END_COLUMN]
    month_max = grouped.max()
    month_complete = grouped.count().eq(grouped.size())
    splits: list[PitMonthlySplit] = []
    for test_date in dates:
        prior = dates[dates < test_date]
        eligible = pd.DatetimeIndex(
            [
                date
                for date in prior
                if bool(month_complete.loc[date]) and month_max.loc[date] <= test_date
            ]
        )
        if len(eligible) < min_train_months:
            continue
        purged = prior.difference(eligible, sort=False)
        splits.append(
            PitMonthlySplit(
                train_dates=eligible,
                test_date=pd.Timestamp(test_date),
                train_label_end_max=pd.Timestamp(month_max.loc[eligible].max()),
                purged_dates=purged,
            )
        )
    return splits


def audit_pit_splits(
    frame: pd.DataFrame,
    splits: list[PitMonthlySplit],
) -> dict[str, Any]:
    panel = frame.copy()
    panel[DATE_COLUMN] = pd.to_datetime(panel[DATE_COLUMN]).dt.normalize()
    panel[FUTURE_LABEL_END_COLUMN] = pd.to_datetime(panel[FUTURE_LABEL_END_COLUMN]).dt.normalize()
    violation_rows = 0
    violation_folds = 0
    violating_train_months: set[pd.Timestamp] = set()
    max_future_days = 0
    for split in splits:
        train = panel[panel[DATE_COLUMN].isin(split.train_dates)]
        invalid = train[FUTURE_LABEL_END_COLUMN].isna() | (
            train[FUTURE_LABEL_END_COLUMN] > split.test_date
        )
        count = int(invalid.sum())
        if count:
            violation_rows += count
            violation_folds += 1
            violating_train_months.update(
                pd.Timestamp(value)
                for value in train.loc[invalid, DATE_COLUMN].dropna().unique()
            )
            deltas = (
                train.loc[invalid & train[FUTURE_LABEL_END_COLUMN].notna(), FUTURE_LABEL_END_COLUMN]
                - split.test_date
            ).dt.days
            if not deltas.empty:
                max_future_days = max(max_future_days, int(deltas.max()))
    return {
        "folds": len(splits),
        "violation_rows": violation_rows,
        "violation_train_months": len(violating_train_months),
        "violation_folds": violation_folds,
        "max_future_days": max_future_days,
    }


def stage006_decision(qualification: dict[str, Any], pit_audit: dict[str, Any]) -> str:
    if int(pit_audit["violation_rows"]) or int(pit_audit["violation_folds"]):
        return "stage006_pit_invalid_stop_no_backtest"
    if bool(qualification["passed"]):
        return "stage006_pit_corrected_confirmed_pass_development_only"
    return "stage006_pit_corrected_confirmed_fail_stop_no_backtest"


def _identity(path: Path) -> dict[str, Any]:
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise RuntimeError(f"file changed while hashing: {path}")
    return {"path": str(path), "size": after.st_size, "sha256": digest.hexdigest()}


def _join_dates(dates: pd.DatetimeIndex) -> str:
    return ",".join(pd.Timestamp(date).date().isoformat() for date in dates)


def build_split_audit_rows(
    panel: pd.DataFrame,
    corrected_splits: list[PitMonthlySplit],
    calendar_splits: list[Any],
) -> pd.DataFrame:
    frame = panel.copy()
    frame[DATE_COLUMN] = pd.to_datetime(frame[DATE_COLUMN]).dt.normalize()
    frame[FUTURE_LABEL_END_COLUMN] = pd.to_datetime(
        frame[FUTURE_LABEL_END_COLUMN]
    ).dt.normalize()
    month_max = frame.groupby(DATE_COLUMN)[FUTURE_LABEL_END_COLUMN].max()
    calendar_by_test = {pd.Timestamp(split.test_date): split for split in calendar_splits}
    rows: list[dict[str, Any]] = []
    for split in corrected_splits:
        old = calendar_by_test[split.test_date]
        added = split.train_dates.difference(old.train_dates, sort=False)
        removed = old.train_dates.difference(split.train_dates, sort=False)
        old_max = pd.Timestamp(month_max.loc[old.train_dates].max())
        rows.append(
            {
                "test_date": split.test_date,
                "calendar_train_months": len(old.train_dates),
                "pit_train_months": len(split.train_dates),
                "calendar_train_end": old.train_dates.max(),
                "pit_train_end": split.train_dates.max(),
                "calendar_train_label_end_max": old_max,
                "pit_train_label_end_max": split.train_label_end_max,
                "added_valid_months_count": len(added),
                "added_valid_months": _join_dates(added),
                "removed_leaking_months_count": len(removed),
                "removed_leaking_months": _join_dates(removed),
            }
        )
    return pd.DataFrame(rows)


def _old_calendar_audit(
    panel: pd.DataFrame,
    calendar_splits: list[Any],
) -> dict[str, Any]:
    label_ends = panel.groupby(DATE_COLUMN)[FUTURE_LABEL_END_COLUMN].max()
    converted = [
        PitMonthlySplit(
            train_dates=split.train_dates,
            test_date=pd.Timestamp(split.test_date),
            train_label_end_max=pd.Timestamp(label_ends.loc[split.train_dates].max()),
            purged_dates=pd.DatetimeIndex([]),
        )
        for split in calendar_splits
    ]
    return audit_pit_splits(panel, converted)


def _add_top10_flags(
    frame: pd.DataFrame,
    *,
    score_column: str,
    output_column: str,
) -> None:
    frame[output_column] = False
    for eval_date, month in frame.groupby(DATE_COLUMN, sort=True):
        selected = month.sort_values(
            [score_column, PRODUCT_COLUMN],
            ascending=[False, True],
            kind="mergesort",
        ).head(TOP_N).index
        frame.loc[selected, output_column] = True


def build_old_prediction_diff(corrected: pd.DataFrame) -> pd.DataFrame:
    old_stage002 = pd.read_csv(STAGE002_OLD_PREDICTIONS, parse_dates=[DATE_COLUMN])
    old_stage003 = pd.read_csv(STAGE003_OLD_PREDICTIONS, parse_dates=[DATE_COLUMN])
    old = old_stage002[
        [DATE_COLUMN, PRODUCT_COLUMN, "score_logistic", "score_ranker", "score_fused"]
    ].merge(
        old_stage003[[DATE_COLUMN, PRODUCT_COLUMN, "score_two_month_confirmed"]],
        on=[DATE_COLUMN, PRODUCT_COLUMN],
        how="left",
        validate="one_to_one",
    )
    old.rename(
        columns={
            "score_logistic": "old_score_logistic",
            "score_ranker": "old_score_ranker",
            "score_fused": "old_score_fused",
            "score_two_month_confirmed": "old_score_two_month_confirmed",
        },
        inplace=True,
    )
    new = corrected[
        [DATE_COLUMN, PRODUCT_COLUMN, "score_logistic", "score_ranker", "score_fused",
         "score_two_month_confirmed"]
    ].rename(
        columns={
            "score_logistic": "new_score_logistic",
            "score_ranker": "new_score_ranker",
            "score_fused": "new_score_fused",
            "score_two_month_confirmed": "new_score_two_month_confirmed",
        }
    )
    diff = old.merge(
        new,
        on=[DATE_COLUMN, PRODUCT_COLUMN],
        how="outer",
        validate="one_to_one",
        indicator=True,
    )
    if not diff["_merge"].eq("both").all():
        raise RuntimeError("old and corrected prediction panels differ")
    diff.drop(columns="_merge", inplace=True)
    for name in ("logistic", "ranker", "fused", "two_month_confirmed"):
        diff[f"score_abs_diff_{name}"] = (
            diff[f"new_score_{name}"] - diff[f"old_score_{name}"]
        ).abs()
    _add_top10_flags(diff, score_column="old_score_logistic", output_column="old_a_top10")
    _add_top10_flags(diff, score_column="new_score_logistic", output_column="new_a_top10")
    _add_top10_flags(
        diff,
        score_column="old_score_two_month_confirmed",
        output_column="old_c3_top10",
    )
    _add_top10_flags(
        diff,
        score_column="new_score_two_month_confirmed",
        output_column="new_c3_top10",
    )
    diff["a_top10_changed"] = diff["old_a_top10"] != diff["new_a_top10"]
    diff["c3_top10_changed"] = diff["old_c3_top10"] != diff["new_c3_top10"]
    return diff.sort_values([DATE_COLUMN, PRODUCT_COLUMN]).reset_index(drop=True)


def _render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Stage006 真实标签结束日修正报告",
        "",
        f"- 决策：`{summary['decision']}`",
        f"- 修正OOS月份：`{summary['oos_months']}`",
        f"- 旧92日切分违规：`{summary['calendar_proxy_audit']['violation_rows']}`条 / "
        f"`{summary['calendar_proxy_audit']['violation_folds']}`折",
        f"- 新PIT切分违规：`{summary['pit_audit']['violation_rows']}`条 / "
        f"`{summary['pit_audit']['violation_folds']}`折",
        "- 这些月份已被前序阶段自适应使用，因此只能称为开发时间外样本。",
        "",
        "| 臂 | 双目标Rank IC均值 | 中位数 | Top10月均未来净利润 | 净利润10%分位 | "
        "Top10月均未来最大回撤 | 回撤10%分位 | 换入率 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for arm in ("A_logistic", "B_ranker", "C_fusion", "C3_confirmed"):
        value = summary["arms"][arm]
        lines.append(
            f"| {arm} | {value['mean_dual_rank_ic']:.6f} | "
            f"{value['median_dual_rank_ic']:.6f} | "
            f"{value['top10_mean_future_net_pnl_60d']:.2f} | "
            f"{value['top10_p10_future_net_pnl_60d']:.2f} | "
            f"{value['top10_mean_future_max_drawdown_60d']:.2f} | "
            f"{value['top10_p10_future_max_drawdown_60d']:.2f} | "
            f"{value['top10_turnover']:.4%} |"
        )
    lines.extend(["", "## C3原11项门槛", ""])
    for name, passed in summary["qualification"]["C3_confirmed"]["gates"].items():
        lines.append(f"- `{'PASS' if passed else 'FAIL'}` `{name}`")
    lines.extend(
        [
            "",
            "## 边界",
            "",
            "- 本阶段没有运行策略真引擎，代理收益和聚合路径回撤不是账户权益结论。",
            "- 即使资格通过，也必须补充未触碰样本或新增前向shadow，才能讨论部署。",
            "- 失败后不得修改模型参数、融合权重、确认月数、TopN或门槛救援。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    stage003 = _load_stage003_module()
    stage001 = stage002._load_stage001_module()
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
        stage001.STAGE001_PATH if hasattr(stage001, "STAGE001_PATH") else stage002.STAGE001_PATH,
        STAGE002_PATH,
        STAGE003_PATH,
        STAGE002_OLD_PREDICTIONS,
        STAGE003_OLD_PREDICTIONS,
        PREREGISTRATION_PATH,
        REVIEW_PATH,
        *source_paths,
        Path(__file__).resolve(),
    ]
    identities_before = {str(path): _identity(path) for path in tracked_paths}
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

    path_daily = add_future_path_metrics_and_label_end(daily)
    path_labels = path_daily.rename(columns={"date": DATE_COLUMN})[
        [
            DATE_COLUMN,
            PRODUCT_COLUMN,
            "future_path_net_pnl_60d",
            stage002.FUTURE_DRAWDOWN_COLUMN,
            FUTURE_LABEL_END_COLUMN,
        ]
    ]
    panel = panel.merge(
        path_labels,
        on=[DATE_COLUMN, PRODUCT_COLUMN],
        how="left",
        validate="one_to_one",
    )
    path_parity_error = float(
        np.max(
            np.abs(
                panel[stage002.FUTURE_PNL_COLUMN].to_numpy(dtype="float64")
                - panel["future_path_net_pnl_60d"].to_numpy(dtype="float64")
            )
        )
    )
    if not np.isfinite(path_parity_error) or path_parity_error > 1e-10:
        raise RuntimeError(f"future path pnl parity failed: {path_parity_error}")
    if panel[FUTURE_LABEL_END_COLUMN].isna().any():
        raise RuntimeError("verified panel contains incomplete future label ends")
    panel = stage002.add_dual_objective_labels(panel)
    for _, group in panel.groupby(DATE_COLUMN):
        if sorted(group[stage002.DUAL_RELEVANCE_COLUMN].tolist()) != list(range(18)):
            raise RuntimeError("monthly relevance labels are incomplete")

    calendar_splits = stage001.build_monthly_splits(panel)
    calendar_proxy_audit = _old_calendar_audit(panel, calendar_splits)
    if calendar_proxy_audit != {
        "folds": 49,
        "violation_rows": 18,
        "violation_train_months": 1,
        "violation_folds": 1,
        "max_future_days": 1,
    }:
        raise RuntimeError(f"reviewed calendar-proxy leak changed: {calendar_proxy_audit}")
    splits = build_pit_monthly_splits(panel, min_train_months=stage001.MIN_TRAIN_MONTHS)
    pit_audit = audit_pit_splits(panel, splits)
    if len(splits) != 49 or pit_audit["violation_rows"] or pit_audit["violation_folds"]:
        raise RuntimeError(f"PIT split qualification failed: {pit_audit}")
    split_audit = build_split_audit_rows(panel, splits, calendar_splits)

    old_by_test = {pd.Timestamp(split.test_date): split for split in calendar_splits}
    prediction_rows: list[pd.DataFrame] = []
    importances: list[np.ndarray] = []
    determinism_error = 0.0
    for index, split in enumerate(splits, start=1):
        train = panel[panel[DATE_COLUMN].isin(split.train_dates)].copy()
        test = panel[panel[DATE_COLUMN].eq(split.test_date)].copy()
        logistic = stage001._train_logistic(train, feature_columns)
        ranker = stage002.train_ranker(train, feature_columns)
        x_test = stage002._prepare_features(test, feature_columns)
        test["score_logistic"] = logistic.predict_proba(x_test)[:, 1]
        test["score_ranker"] = ranker.predict(x_test)
        importances.append(np.asarray(ranker.feature_importances_, dtype="float64"))
        if index == len(splits):
            repeated = stage002.train_ranker(train, feature_columns).predict(x_test)
            determinism_error = float(
                np.max(np.abs(repeated - test["score_ranker"].to_numpy(dtype="float64")))
            )
        old = old_by_test[split.test_date]
        added = split.train_dates.difference(old.train_dates, sort=False)
        removed = old.train_dates.difference(split.train_dates, sort=False)
        test["fold_train_start"] = split.train_dates.min()
        test["fold_train_end"] = split.train_dates.max()
        test["fold_train_months"] = len(split.train_dates)
        test["fold_train_label_end_max"] = split.train_label_end_max
        test["fold_calendar_train_months"] = len(old.train_dates)
        test["fold_added_valid_months"] = _join_dates(added)
        test["fold_removed_leaking_months"] = _join_dates(removed)
        prediction_rows.append(test)

    predictions = pd.concat(prediction_rows, ignore_index=True)
    predictions = stage001.add_rank_fusion(
        predictions,
        "score_logistic",
        "score_ranker",
        weight_a=0.5,
    )
    candidate = stage003.add_two_month_confirmed_scores(predictions)
    score_columns = {
        "A_logistic": "score_logistic",
        "B_ranker": "score_ranker",
        "C_fusion": "score_fused",
        "C3_confirmed": "score_two_month_confirmed",
    }
    monthly, selections = stage002.build_metric_rows(candidate, daily, score_columns)
    arms = {arm: stage002.summarize_arm(monthly, selections, arm) for arm in score_columns}
    yearly = monthly.groupby(["year", "arm"], as_index=False).agg(
        mean_dual_rank_ic=("dual_rank_ic", "mean"),
        mean_top10_future_net_pnl_60d=("top10_future_net_pnl_60d", "mean"),
        mean_top10_future_max_drawdown_60d=("top10_future_max_drawdown_60d", "mean"),
        months=(DATE_COLUMN, "nunique"),
    )
    oos_months = int(candidate[DATE_COLUMN].nunique())
    qualification: dict[str, dict[str, Any]] = {}
    gate_inputs: dict[str, dict[str, Any]] = {}
    for arm in ("B_ranker", "C_fusion", "C3_confirmed"):
        inputs = stage002.build_gate_inputs(
            arms,
            yearly,
            arm,
            identity_pass=True,
            determinism_pass=determinism_error <= 1e-12,
            path_parity_pass=path_parity_error <= 1e-10,
            oos_months=oos_months,
        )
        gate_inputs[arm] = inputs
        qualification[arm] = evaluate_candidate_gates(inputs)
    decision = stage006_decision(qualification["C3_confirmed"], pit_audit)

    identities_after = {str(path): _identity(path) for path in tracked_paths}
    if identities_before != identities_after:
        raise RuntimeError("source changed during Stage006")
    importance = pd.DataFrame(
        {
            "feature": feature_columns,
            "mean_gain_importance": np.mean(np.vstack(importances), axis=0),
        }
    ).sort_values(["mean_gain_importance", "feature"], ascending=[False, True])
    old_diff = build_old_prediction_diff(candidate)
    changed_months_a = int(
        old_diff.loc[old_diff["a_top10_changed"], DATE_COLUMN].nunique()
    )
    changed_months_c3 = int(
        old_diff.loc[old_diff["c3_top10_changed"], DATE_COLUMN].nunique()
    )
    confirmed_by_month = candidate.groupby(DATE_COLUMN, as_index=False)["confirmed_count"].first()
    summary = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "decision": decision,
        "formal_release_id": stage001.FORMAL_RELEASE_ID,
        "status_scope": "development_only_not_independent_final_oos",
        "adaptive_reuse_warning": (
            "Stage001-003 used the same 49 months to change objectives and overlay rules; "
            "promotion requires untouched or new forward shadow months"
        ),
        "panel": {
            "rows": int(len(panel)),
            "months": int(panel[DATE_COLUMN].nunique()),
            "products_per_month": 18,
            "features": len(feature_columns),
            "panel_parity_max_abs_error": panel_parity_error,
        },
        "configuration": {
            "future_horizon_trading_days": stage002.FUTURE_HORIZON,
            "split_rule": "all_month_product_label_end_lte_inference_eod",
            "min_train_months": stage001.MIN_TRAIN_MONTHS,
            "dual_pnl_weight": DUAL_PNL_WEIGHT,
            "dual_drawdown_weight": DUAL_DRAWDOWN_WEIGHT,
            "top_n": TOP_N,
            "fusion_weight_logistic": 0.5,
            "fusion_weight_ranker": 0.5,
            "confirmation_months": 2,
            "xgboost_ranker": XGBRANKER_PARAMS,
        },
        "oos_months": oos_months,
        "oos_start": candidate[DATE_COLUMN].min().date().isoformat(),
        "oos_end": candidate[DATE_COLUMN].max().date().isoformat(),
        "calendar_proxy_audit": calendar_proxy_audit,
        "pit_audit": pit_audit,
        "split_changes": {
            "folds_with_added_valid_months": int(
                split_audit["added_valid_months_count"].gt(0).sum()
            ),
            "total_added_valid_months": int(split_audit["added_valid_months_count"].sum()),
            "folds_with_removed_leaking_months": int(
                split_audit["removed_leaking_months_count"].gt(0).sum()
            ),
            "total_removed_leaking_months": int(
                split_audit["removed_leaking_months_count"].sum()
            ),
            "minimum_pit_train_months": int(split_audit["pit_train_months"].min()),
            "maximum_pit_train_months": int(split_audit["pit_train_months"].max()),
        },
        "path_parity_max_abs_error": path_parity_error,
        "determinism_max_abs_error": determinism_error,
        "arms": arms,
        "gate_inputs": gate_inputs,
        "qualification": qualification,
        "confirmation": {
            "mean_confirmed_count": float(confirmed_by_month["confirmed_count"].mean()),
            "median_confirmed_count": float(confirmed_by_month["confirmed_count"].median()),
            "minimum_confirmed_count": int(confirmed_by_month["confirmed_count"].min()),
            "maximum_confirmed_count": int(confirmed_by_month["confirmed_count"].max()),
        },
        "old_prediction_comparison": {
            "a_top10_changed_months": changed_months_a,
            "c3_top10_changed_months": changed_months_c3,
            "max_abs_score_diff_logistic": float(old_diff["score_abs_diff_logistic"].max()),
            "max_abs_score_diff_ranker": float(old_diff["score_abs_diff_ranker"].max()),
            "max_abs_score_diff_fused": float(old_diff["score_abs_diff_fused"].max()),
        },
        "identities": identities_before,
        "source_unchanged": True,
        "versions": {
            "python": sys.version,
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "sklearn": stage002.sklearn.__version__,
            "xgboost": stage002.xgboost.__version__,
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
            "https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html",
            "https://github.com/dmlc/xgboost/blob/master/doc/tutorials/learning_to_rank.rst",
            "https://github.com/dmlc/xgboost/blob/master/doc/parameter.rst",
        ],
    }
    prediction_columns = [
        DATE_COLUMN,
        PRODUCT_COLUMN,
        stage002.FUTURE_PNL_COLUMN,
        stage002.FUTURE_DRAWDOWN_COLUMN,
        FUTURE_LABEL_END_COLUMN,
        stage002.DUAL_UTILITY_COLUMN,
        stage002.DUAL_RELEVANCE_COLUMN,
        "score_logistic",
        "score_ranker",
        "score_a_percentile",
        "score_b_percentile",
        "score_fused",
        "score_two_month_confirmed",
        "confirmed_by_two_months",
        "confirmed_count",
        "fold_train_start",
        "fold_train_end",
        "fold_train_months",
        "fold_train_label_end_max",
        "fold_calendar_train_months",
        "fold_added_valid_months",
        "fold_removed_leaking_months",
    ]
    candidate[prediction_columns].to_csv(OUT / "oos_predictions.csv", index=False)
    monthly.to_csv(OUT / "monthly_metrics.csv", index=False)
    yearly.to_csv(OUT / "yearly_metrics.csv", index=False)
    split_audit.to_csv(OUT / "split_audit.csv", index=False)
    old_diff.to_csv(OUT / "old_prediction_diff.csv", index=False)
    importance.to_csv(OUT / "xgboost_ranker_feature_importance.csv", index=False)
    confirmed_by_month.to_csv(OUT / "confirmed_count_by_month.csv", index=False)
    panel[
        [
            DATE_COLUMN,
            PRODUCT_COLUMN,
            stage002.FUTURE_PNL_COLUMN,
            stage002.FUTURE_DRAWDOWN_COLUMN,
            FUTURE_LABEL_END_COLUMN,
            stage002.DUAL_UTILITY_COLUMN,
            stage002.DUAL_RELEVANCE_COLUMN,
        ]
    ].to_csv(OUT / "dual_objective_labels_with_end.csv", index=False)
    (OUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )
    (OUT / "report.md").write_text(_render_report(summary))
    print(
        json.dumps(
            {
                "decision": decision,
                "calendar_proxy_audit": calendar_proxy_audit,
                "pit_audit": pit_audit,
                "split_changes": summary["split_changes"],
                "arms": arms,
                "c3_qualification": qualification["C3_confirmed"],
                "old_prediction_comparison": summary["old_prediction_comparison"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
