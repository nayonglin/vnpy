from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

SOURCE_MODEL_TAG = "stage719_official_winner_trade_forensics_v1"
SOURCE_PREFIX = "qmt_roll_stage719_official_winner_trade_forensics"
SOURCE_CLOSED_LOTS_PATH = OUTPUT_DIR / f"{SOURCE_PREFIX}_closed_lots_{SOURCE_MODEL_TAG}.csv"

MODEL_TAG = "stage720_winner_feature_oos_validation_v1"
OUTPUT_PREFIX = "qmt_roll_stage720_winner_feature_oos_validation"
LINE_ID = "futures_trend_winner_trade_forensics"

FEATURE_RELIABILITY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_reliability_{MODEL_TAG}.csv"
FEATURE_YEAR_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_year_{MODEL_TAG}.csv"
SUITE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_suite_summary_{MODEL_TAG}.csv"
SUITE_YEAR_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_suite_year_{MODEL_TAG}.csv"
SELECTOR_FEATURES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_selector_features_{MODEL_TAG}.csv"
SELECTOR_YEAR_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_selector_year_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

MIN_SELECTOR_TRAIN_COUNT = 12
MIN_SELECTOR_TRAIN_YEARS = 2
MIN_SELECTOR_YEAR_POSITIVE_RATE = 0.60
MIN_SELECTOR_AVG_R_EDGE = 0.25
MAX_SELECTOR_TRAIN_CAPTURE = 0.75
MAX_SELECTOR_FEATURES = 6

UNIVERSAL_SELECTOR_COLUMNS = [
    "direction",
    "signal",
    "risk_mode",
    "entry_context",
    "layer_kind",
    "risk_multiplier_bucket",
    "loss_streak_bucket",
    "active_positions_bucket",
    "ai_rank_bucket",
    "rsi_bucket",
    "stop_distance_bucket",
    "recovery_bucket",
    "streak_recovery_bucket",
    "breakout_bucket",
]


@dataclass(frozen=True)
class FeatureSpec:
    feature_key: str
    feature_col: str
    feature_value: str
    family: str
    note: str


PREDECLARED_FEATURES = [
    FeatureSpec("loss_streak_1_2", "loss_streak_bucket", "loss_streak_1_2", "positive_candidate", "Stage719 strongest account-state clue"),
    FeatureSpec("risk_normal", "risk_multiplier_bucket", "risk_normal", "broad_state", "Broad normal-risk state, not a standalone quality trigger"),
    FeatureSpec("stop_1_2pct", "stop_distance_bucket", "stop_1_2pct", "positive_candidate", "Moderate initial stop distance"),
    FeatureSpec("active_0", "active_positions_bucket", "active_0", "positive_candidate", "Clean low-concurrency entry state"),
    FeatureSpec("long_rsi_60_70", "rsi_bucket", "long_rsi_60_70", "positive_candidate", "Long side strong but not extreme RSI"),
    FeatureSpec("rollover_reopen", "signal", "rollover_reopen", "small_sample_watch", "Potential continuation/reopen behavior with small sample"),
    FeatureSpec("long_case3", "signal", "long_case3", "stress_test_candidate", "High in early years but suspected unstable"),
    FeatureSpec("ai_rank_1_3", "ai_rank_bucket", "rank_1_3", "stress_test_candidate", "Tests whether top AI rank is monotonic"),
    FeatureSpec("risk_floor_01", "risk_multiplier_bucket", "risk_floor_01", "negative_control", "0.1 risk floor state"),
    FeatureSpec("loss_streak_ge3", "loss_streak_bucket", "loss_streak_ge3", "negative_control", "Three or more consecutive losses"),
    FeatureSpec("recovery", "recovery_bucket", "recovery", "negative_control", "Recovery sleeve state"),
]


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if np.isnan(value) or np.isinf(value):
            return None
        return float(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if pd.isna(value):
        return None
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    data = data.fillna("")
    headers = [str(column) for column in data.columns]
    rows = [[str(value) for value in row] for row in data.to_numpy()]
    widths = [len(header) for header in headers]
    for row in rows:
        widths = [max(width, len(cell)) for width, cell in zip(widths, row)]
    line = "| " + " | ".join(header.ljust(width) for header, width in zip(headers, widths)) + " |"
    sep = "| " + " | ".join("-" * width for width in widths) + " |"
    body = ["| " + " | ".join(cell.ljust(width) for cell, width in zip(row, widths)) + " |" for row in rows]
    return "\n".join([line, sep, *body])


def _read_closed_lots() -> pd.DataFrame:
    if not SOURCE_CLOSED_LOTS_PATH.exists():
        raise FileNotFoundError(SOURCE_CLOSED_LOTS_PATH)
    frame = pd.read_csv(SOURCE_CLOSED_LOTS_PATH, encoding="utf-8-sig")
    raw_count = len(frame)
    for column in ["entry_date", "exit_date"]:
        if column in frame.columns:
            frame[column] = pd.to_datetime(frame[column], errors="coerce")
    numeric_columns = [
        "entry_year",
        "realized_pnl",
        "risk_amount",
        "r_multiple",
        "winner",
        "big_winner",
        "quality_winner",
    ]
    for column in numeric_columns:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["entry_year", "r_multiple"]).copy()
    frame.attrs["source_closed_lot_count"] = raw_count
    frame.attrs["excluded_no_r_count"] = raw_count - len(frame)
    frame["entry_year"] = frame["entry_year"].astype(int)
    for column in ["winner", "big_winner", "quality_winner"]:
        frame[column] = frame[column].fillna(0).astype(int)
    return frame


def _empty_stats() -> dict[str, Any]:
    return {
        "count": 0,
        "win_rate_pct": np.nan,
        "big_winner_rate_pct": np.nan,
        "quality_winner_rate_pct": np.nan,
        "avg_r": np.nan,
        "median_r": np.nan,
        "total_r": 0.0,
        "total_pnl": 0.0,
        "years_count": 0,
        "years_positive": 0,
        "years_positive_rate_pct": np.nan,
        "product_count": 0,
        "dominant_product": "",
        "dominant_product_share_pct": np.nan,
        "direction_count": 0,
        "dominant_direction": "",
        "dominant_direction_share_pct": np.nan,
    }


def _stats(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return _empty_stats()
    year_r = frame.groupby("entry_year", dropna=False)["r_multiple"].sum()
    product_share = frame["product"].value_counts(normalize=True) if "product" in frame.columns else pd.Series(dtype=float)
    direction_share = frame["direction"].value_counts(normalize=True) if "direction" in frame.columns else pd.Series(dtype=float)
    dominant_product = str(product_share.index[0]) if not product_share.empty else ""
    dominant_direction = str(direction_share.index[0]) if not direction_share.empty else ""
    return {
        "count": int(len(frame)),
        "win_rate_pct": float(frame["winner"].mean() * 100.0),
        "big_winner_rate_pct": float(frame["big_winner"].mean() * 100.0),
        "quality_winner_rate_pct": float(frame["quality_winner"].mean() * 100.0),
        "avg_r": float(frame["r_multiple"].mean()),
        "median_r": float(frame["r_multiple"].median()),
        "total_r": float(frame["r_multiple"].sum()),
        "total_pnl": float(frame["realized_pnl"].sum()),
        "years_count": int(len(year_r)),
        "years_positive": int((year_r > 0).sum()),
        "years_positive_rate_pct": float((year_r > 0).mean() * 100.0) if len(year_r) else np.nan,
        "product_count": int(frame["product"].nunique()) if "product" in frame.columns else 0,
        "dominant_product": dominant_product,
        "dominant_product_share_pct": float(product_share.iloc[0] * 100.0) if not product_share.empty else np.nan,
        "direction_count": int(frame["direction"].nunique()) if "direction" in frame.columns else 0,
        "dominant_direction": dominant_direction,
        "dominant_direction_share_pct": float(direction_share.iloc[0] * 100.0) if not direction_share.empty else np.nan,
    }


def _feature_mask(frame: pd.DataFrame, spec: FeatureSpec) -> pd.Series:
    return frame[spec.feature_col].astype(str).eq(spec.feature_value)


def _classify_feature(row: pd.Series, baseline_avg_r: float) -> str:
    if row["family"] == "negative_control":
        if row["avg_r"] < 0 and row["years_positive_rate_pct"] <= 30:
            return "stable_negative_control"
        return "negative_control_mixed"
    if row["feature_key"] == "risk_normal":
        return "broad_risk_baseline_not_quality_trigger"
    if row["count"] < 30 and row["years_positive_rate_pct"] >= 80 and row["avg_r"] > baseline_avg_r:
        return "small_sample_positive_watch"
    if (
        row["count"] >= 50
        and row["years_positive_rate_pct"] >= 80
        and row["avg_r"] >= baseline_avg_r + 0.40
        and row["product_count"] >= 8
        and row["dominant_product_share_pct"] <= 20
    ):
        return "relatively_reliable_positive_state"
    if row["count"] >= 50 and row["years_positive_rate_pct"] >= 65 and row["avg_r"] > baseline_avg_r:
        return "positive_watch_needs_oos_gate"
    return "not_reliable_enough"


def build_feature_reliability(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    baseline_avg_r = float(frame["r_multiple"].mean())
    feature_rows: list[dict[str, Any]] = []
    year_rows: list[dict[str, Any]] = []
    for spec in PREDECLARED_FEATURES:
        selected = frame[_feature_mask(frame, spec)]
        stats = _stats(selected)
        row = {
            "feature_key": spec.feature_key,
            "feature_col": spec.feature_col,
            "feature_value": spec.feature_value,
            "family": spec.family,
            "note": spec.note,
            **stats,
        }
        row["baseline_avg_r"] = baseline_avg_r
        row["classification"] = _classify_feature(pd.Series(row), baseline_avg_r)
        feature_rows.append(row)

        for year, group in selected.groupby("entry_year", dropna=False):
            year_stats = _stats(group)
            year_rows.append(
                {
                    "feature_key": spec.feature_key,
                    "entry_year": int(year),
                    "count": year_stats["count"],
                    "total_r": year_stats["total_r"],
                    "avg_r": year_stats["avg_r"],
                    "total_pnl": year_stats["total_pnl"],
                    "win_rate_pct": year_stats["win_rate_pct"],
                }
            )

    reliability = pd.DataFrame(feature_rows).sort_values(
        ["classification", "avg_r", "count"],
        ascending=[True, False, False],
    )
    feature_year = pd.DataFrame(year_rows)
    return reliability, feature_year


def _suite_masks(frame: pd.DataFrame) -> dict[str, pd.Series]:
    risk_normal = frame["risk_multiplier_bucket"].astype(str).eq("risk_normal")
    loss12 = frame["loss_streak_bucket"].astype(str).eq("loss_streak_1_2")
    active0 = frame["active_positions_bucket"].astype(str).eq("active_0")
    stop12 = frame["stop_distance_bucket"].astype(str).eq("stop_1_2pct")
    long_rsi6070 = frame["rsi_bucket"].astype(str).eq("long_rsi_60_70")
    rollover = frame["signal"].astype(str).eq("rollover_reopen")
    negative = (
        frame["risk_multiplier_bucket"].astype(str).eq("risk_floor_01")
        | frame["loss_streak_bucket"].astype(str).eq("loss_streak_ge3")
        | frame["recovery_bucket"].astype(str).eq("recovery")
    )
    return {
        "all_lots": pd.Series(True, index=frame.index),
        "loss_streak_1_2": loss12,
        "risk_normal": risk_normal,
        "risk_normal_and_loss_streak_1_2": risk_normal & loss12,
        "risk_normal_any_stage719_positive": risk_normal & (loss12 | active0 | stop12 | long_rsi6070 | rollover),
        "negative_floor_ge3_recovery": negative,
        "not_negative_floor_ge3_recovery": ~negative,
    }


def build_suite_tables(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    summary_rows: list[dict[str, Any]] = []
    year_rows: list[dict[str, Any]] = []
    for suite, mask in _suite_masks(frame).items():
        selected = frame[mask]
        summary_rows.append({"suite": suite, **_stats(selected)})
        for year, group in selected.groupby("entry_year", dropna=False):
            year_stats = _stats(group)
            year_rows.append(
                {
                    "suite": suite,
                    "entry_year": int(year),
                    "count": year_stats["count"],
                    "total_r": year_stats["total_r"],
                    "avg_r": year_stats["avg_r"],
                    "total_pnl": year_stats["total_pnl"],
                    "win_rate_pct": year_stats["win_rate_pct"],
                }
            )
    return pd.DataFrame(summary_rows), pd.DataFrame(year_rows)


def _candidate_feature_stats(train: pd.DataFrame) -> pd.DataFrame:
    baseline = _stats(train)
    rows: list[dict[str, Any]] = []
    for column in UNIVERSAL_SELECTOR_COLUMNS:
        if column not in train.columns:
            continue
        for value, group in train.groupby(column, dropna=False):
            label = "missing" if pd.isna(value) or str(value) == "" else str(value)
            if label in {"missing", "nan", ""}:
                continue
            stats = _stats(group)
            year_r = group.groupby("entry_year")["r_multiple"].sum()
            rows.append(
                {
                    "feature_col": column,
                    "feature_value": label,
                    "train_capture_rate_pct": stats["count"] / len(train) * 100.0,
                    "train_years_positive_rate_pct": float((year_r > 0).mean() * 100.0) if len(year_r) else np.nan,
                    "baseline_avg_r": baseline["avg_r"],
                    "baseline_big_winner_rate_pct": baseline["big_winner_rate_pct"],
                    "baseline_quality_winner_rate_pct": baseline["quality_winner_rate_pct"],
                    **{f"train_{key}": value for key, value in stats.items()},
                }
            )
    return pd.DataFrame(rows)


def _select_features(train: pd.DataFrame) -> pd.DataFrame:
    candidates = _candidate_feature_stats(train)
    if candidates.empty:
        return candidates
    selected = candidates[
        (candidates["train_count"] >= MIN_SELECTOR_TRAIN_COUNT)
        & (candidates["train_years_count"] >= MIN_SELECTOR_TRAIN_YEARS)
        & (candidates["train_years_positive_rate_pct"] >= MIN_SELECTOR_YEAR_POSITIVE_RATE * 100.0)
        & (candidates["train_avg_r"] >= candidates["baseline_avg_r"] + MIN_SELECTOR_AVG_R_EDGE)
        & (
            (candidates["train_big_winner_rate_pct"] >= candidates["baseline_big_winner_rate_pct"])
            | (candidates["train_quality_winner_rate_pct"] >= candidates["baseline_quality_winner_rate_pct"])
        )
        & (candidates["train_capture_rate_pct"] <= MAX_SELECTOR_TRAIN_CAPTURE * 100.0)
    ].copy()
    if selected.empty:
        return selected
    selected["selection_score"] = (
        selected["train_avg_r"]
        + 0.02 * selected["train_years_positive_rate_pct"]
        + 0.03 * selected["train_big_winner_rate_pct"]
        + 0.01 * selected["train_quality_winner_rate_pct"]
    )
    selected = selected.sort_values(["selection_score", "train_count"], ascending=[False, False]).head(MAX_SELECTOR_FEATURES)
    return selected


def build_chronological_selector(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    feature_rows: list[dict[str, Any]] = []
    year_rows: list[dict[str, Any]] = []
    years = sorted(int(year) for year in frame["entry_year"].dropna().unique())

    for target_year in years:
        train = frame[frame["entry_year"] < target_year]
        test = frame[frame["entry_year"] == target_year]
        if train["entry_year"].nunique() < MIN_SELECTOR_TRAIN_YEARS or test.empty:
            continue

        selected_features = _select_features(train)
        selected_mask = pd.Series(False, index=test.index)
        for rank, (_, row) in enumerate(selected_features.iterrows(), start=1):
            selected_mask |= test[row["feature_col"]].astype(str).eq(str(row["feature_value"]))
            feature_rows.append(
                {
                    "target_year": target_year,
                    "rank": rank,
                    "feature_col": row["feature_col"],
                    "feature_value": row["feature_value"],
                    "selection_score": row["selection_score"],
                    "train_count": row["train_count"],
                    "train_avg_r": row["train_avg_r"],
                    "train_total_r": row["train_total_r"],
                    "train_years_positive": row["train_years_positive"],
                    "train_years_count": row["train_years_count"],
                    "train_capture_rate_pct": row["train_capture_rate_pct"],
                }
            )

        selected_test = test[selected_mask]
        rest_test = test[~selected_mask]
        all_stats = _stats(test)
        selected_stats = _stats(selected_test)
        rest_stats = _stats(rest_test)
        year_rows.append(
            {
                "target_year": target_year,
                "train_start_year": int(train["entry_year"].min()),
                "train_end_year": int(train["entry_year"].max()),
                "selected_feature_count": int(len(selected_features)),
                "test_count": all_stats["count"],
                "selected_count": selected_stats["count"],
                "rest_count": rest_stats["count"],
                "all_avg_r": all_stats["avg_r"],
                "selected_avg_r": selected_stats["avg_r"],
                "rest_avg_r": rest_stats["avg_r"],
                "all_total_r": all_stats["total_r"],
                "selected_total_r": selected_stats["total_r"],
                "rest_total_r": rest_stats["total_r"],
                "all_total_pnl": all_stats["total_pnl"],
                "selected_total_pnl": selected_stats["total_pnl"],
                "rest_total_pnl": rest_stats["total_pnl"],
                "selected_outperform_all": int(selected_stats["avg_r"] > all_stats["avg_r"]) if selected_stats["count"] else 0,
                "selected_positive_r": int(selected_stats["total_r"] > 0) if selected_stats["count"] else 0,
            }
        )

    return pd.DataFrame(feature_rows), pd.DataFrame(year_rows)


def plot_chart(
    feature_reliability: pd.DataFrame,
    feature_year: pd.DataFrame,
    suite_year: pd.DataFrame,
    selector_year: pd.DataFrame,
) -> None:
    plt.rcParams["font.family"] = "DejaVu Sans"
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))

    top = feature_reliability.sort_values("avg_r", ascending=False).head(8)
    colors = ["#2f855a" if "negative" not in cls else "#c53030" for cls in top["classification"]]
    axes[0, 0].barh(top["feature_key"], top["avg_r"], color=colors)
    axes[0, 0].axvline(float(feature_reliability["baseline_avg_r"].iloc[0]), color="#4a5568", linestyle="--", linewidth=1.0)
    axes[0, 0].set_title("Predeclared feature avg R")
    axes[0, 0].set_xlabel("avg R")
    axes[0, 0].invert_yaxis()

    heat_features = ["loss_streak_1_2", "risk_normal", "stop_1_2pct", "active_0", "long_rsi_60_70", "rollover_reopen", "loss_streak_ge3", "risk_floor_01"]
    pivot = feature_year[feature_year["feature_key"].isin(heat_features)].pivot_table(
        index="feature_key",
        columns="entry_year",
        values="total_r",
        aggfunc="sum",
    ).reindex(heat_features)
    image = axes[0, 1].imshow(pivot.fillna(0.0), cmap="RdYlGn", aspect="auto")
    axes[0, 1].set_title("Feature total R by entry year")
    axes[0, 1].set_yticks(range(len(pivot.index)))
    axes[0, 1].set_yticklabels(pivot.index)
    axes[0, 1].set_xticks(range(len(pivot.columns)))
    axes[0, 1].set_xticklabels(pivot.columns)
    fig.colorbar(image, ax=axes[0, 1], fraction=0.046, pad=0.04)

    if not selector_year.empty:
        x = np.arange(len(selector_year))
        width = 0.25
        axes[1, 0].bar(x - width, selector_year["all_avg_r"], width, label="all", color="#718096")
        axes[1, 0].bar(x, selector_year["selected_avg_r"], width, label="selected", color="#2b6cb0")
        axes[1, 0].bar(x + width, selector_year["rest_avg_r"], width, label="rest", color="#dd6b20")
        axes[1, 0].axhline(0.0, color="#4a5568", linewidth=1.0)
        axes[1, 0].set_title("Chronological selector OOS avg R")
        axes[1, 0].set_xticks(x)
        axes[1, 0].set_xticklabels(selector_year["target_year"])
        axes[1, 0].legend()

    suite_focus = suite_year[suite_year["suite"].isin(["loss_streak_1_2", "risk_normal_any_stage719_positive", "negative_floor_ge3_recovery"])]
    for suite, group in suite_focus.groupby("suite"):
        axes[1, 1].plot(group["entry_year"], group["total_r"], marker="o", label=suite)
    axes[1, 1].axhline(0.0, color="#4a5568", linewidth=1.0)
    axes[1, 1].set_title("Suite total R by entry year")
    axes[1, 1].set_xlabel("entry year")
    axes[1, 1].set_ylabel("total R")
    axes[1, 1].legend(fontsize=8)

    fig.suptitle("Stage720 Winner Feature OOS Validation", fontsize=16)
    fig.tight_layout(rect=[0, 0.02, 1, 0.96])
    CHART_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def build_report(
    frame: pd.DataFrame,
    feature_reliability: pd.DataFrame,
    suite_summary: pd.DataFrame,
    selector_year: pd.DataFrame,
    selector_features: pd.DataFrame,
    decision: dict[str, Any],
) -> str:
    key_columns = [
        "feature_key",
        "family",
        "count",
        "avg_r",
        "total_r",
        "win_rate_pct",
        "big_winner_rate_pct",
        "years_positive",
        "years_count",
        "product_count",
        "dominant_product_share_pct",
        "classification",
    ]
    suite_columns = [
        "suite",
        "count",
        "avg_r",
        "total_r",
        "total_pnl",
        "win_rate_pct",
        "years_positive",
        "years_count",
        "dominant_product_share_pct",
    ]
    selector_columns = [
        "target_year",
        "selected_feature_count",
        "test_count",
        "selected_count",
        "all_avg_r",
        "selected_avg_r",
        "rest_avg_r",
        "all_total_r",
        "selected_total_r",
        "rest_total_r",
        "selected_outperform_all",
        "selected_positive_r",
    ]
    selected_feature_columns = [
        "target_year",
        "rank",
        "feature_col",
        "feature_value",
        "train_count",
        "train_avg_r",
        "train_years_positive",
        "train_years_count",
        "train_capture_rate_pct",
    ]

    lines = [
        "# Stage720 Winner Feature OOS Validation",
        "",
        f"- line_id: `{LINE_ID}`",
        f"- generated_at: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`",
        f"- source: `{SOURCE_CLOSED_LOTS_PATH}`",
        f"- source_closed_lots: `{frame.attrs.get('source_closed_lot_count', len(frame))}`",
        f"- analyzable_closed_lots: `{len(frame)}`",
        f"- excluded_no_r_multiple: `{frame.attrs.get('excluded_no_r_count', 0)}`",
        f"- decision: `{decision['decision']}`",
        "",
        "## Method",
        "",
        "- Read-only validation on Stage719 closed lots; no official strategy config is changed.",
        "- Predeclared Stage719 candidate features are checked by year, product concentration, direction concentration, and R-multiple.",
        "- A stricter chronological selector trains only on prior years, excludes product names, and tests the selected feature union on the next entry year.",
        "- This is still forensic validation, not a trading rule or A/B candidate.",
        "",
        "## Predeclared Feature Reliability",
        "",
        _md_table(feature_reliability[key_columns], max_rows=20),
        "",
        "## Suite Summary",
        "",
        _md_table(suite_summary[suite_columns], max_rows=20),
        "",
        "## Chronological Selector OOS",
        "",
        _md_table(selector_year[selector_columns], max_rows=20),
        "",
        "## Selected Features By Target Year",
        "",
        _md_table(selector_features[selected_feature_columns], max_rows=40),
        "",
        "## Interpretation",
        "",
        "- The strongest positive state is `loss_streak_1_2`: broad enough across products, positive in 6/7 entry years, and far better than the account baseline.",
        "- `risk_normal` is useful as a broad state baseline, but it is too broad to be a standalone quality trigger.",
        "- `rollover_reopen` is positive in 6/6 available years but has only 22 lots, so it remains a small-sample watch item.",
        "- `stop_1_2pct`, `active_0`, and `long_rsi_60_70` are positive watch features, but they do not survive every weak year.",
        "- The chronological selector improves 2025 and 2026 but fails to outperform in 2022 and 2024, so the positive feature set is not reliable enough to become a direct rule.",
        "- Negative controls are much more stable: `loss_streak_ge3`, `risk_floor_01`, and `recovery` are poor states and support the existing 0.1 floor as risk control.",
        "",
        "## External Research Takeaway",
        "",
        "- Walk-forward validation is the relevant standard for reducing parameter and feature overfitting.",
        "- R-multiple and MFE/MAE are the right trade-forensic units because raw PnL hides risk distance and contract-size effects.",
        "- GitHub/open-source references are useful for workflow discipline, but no commodity-futures implementation was copied into this repo.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    frame = _read_closed_lots()
    feature_reliability, feature_year = build_feature_reliability(frame)
    suite_summary, suite_year = build_suite_tables(frame)
    selector_features, selector_year = build_chronological_selector(frame)

    selector_years = int(len(selector_year))
    selector_outperform = int(selector_year["selected_outperform_all"].sum()) if selector_years else 0
    selector_positive = int(selector_year["selected_positive_r"].sum()) if selector_years else 0
    loss12 = feature_reliability[feature_reliability["feature_key"].eq("loss_streak_1_2")].iloc[0].to_dict()
    negative = feature_reliability[feature_reliability["family"].eq("negative_control")]

    decision = {
        "model_tag": MODEL_TAG,
        "source_model_tag": SOURCE_MODEL_TAG,
        "line_id": LINE_ID,
        "decision": "positive_state_watch_negative_filter_confirmed_no_trade_rule_promotion",
        "source_closed_lot_count": int(frame.attrs.get("source_closed_lot_count", len(frame))),
        "analyzable_closed_lot_count": int(len(frame)),
        "excluded_no_r_count": int(frame.attrs.get("excluded_no_r_count", 0)),
        "selector_outperform_years": selector_outperform,
        "selector_years": selector_years,
        "selector_positive_years": selector_positive,
        "loss_streak_1_2": {
            "count": loss12["count"],
            "avg_r": loss12["avg_r"],
            "total_r": loss12["total_r"],
            "years_positive": loss12["years_positive"],
            "years_count": loss12["years_count"],
            "classification": loss12["classification"],
        },
        "negative_control_summary": negative[
            ["feature_key", "count", "avg_r", "total_r", "years_positive", "years_count", "classification"]
        ].to_dict(orient="records"),
        "next_step": "If trading logic is explored, use loss_streak_1_2 as a cautious quality-state component and keep loss_streak_ge3/risk_floor/recovery as a veto or low-risk state; do not promote the full positive selector.",
    }

    feature_reliability.to_csv(FEATURE_RELIABILITY_PATH, index=False, encoding="utf-8-sig")
    feature_year.to_csv(FEATURE_YEAR_PATH, index=False, encoding="utf-8-sig")
    suite_summary.to_csv(SUITE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    suite_year.to_csv(SUITE_YEAR_PATH, index=False, encoding="utf-8-sig")
    selector_features.to_csv(SELECTOR_FEATURES_PATH, index=False, encoding="utf-8-sig")
    selector_year.to_csv(SELECTOR_YEAR_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    plot_chart(feature_reliability, feature_year, suite_year, selector_year)
    REPORT_PATH.write_text(
        build_report(frame, feature_reliability, suite_summary, selector_year, selector_features, decision),
        encoding="utf-8",
    )

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
