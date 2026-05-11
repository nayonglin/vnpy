from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from qmt_roll_official_stage78_config import (
    OFFICIAL_STAGE78_CAPITAL,
    OFFICIAL_STAGE78_SHORT_ALIAS,
    OFFICIAL_STAGE78_VERSION,
    build_official_stage78_manifest,
)
from run_qmt_alignment_backtest import OUTPUT_DIR
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


MODEL_TAG = "stage236_signal_quality_path_aware_v1"
OUTPUT_PREFIX = "qmt_roll_stage236_signal_quality_path_aware"
STAGE234_PREFIX = "qmt_roll_stage234_signal_quality_ai_feasibility"
STAGE234_TAG = "stage234_signal_quality_ai_feasibility_v1"
OFFICIAL_PREFIX = "qmt_roll_official_stage78_1"

SAMPLES_INPUT_PATH = OUTPUT_DIR / f"{STAGE234_PREFIX}_samples_{STAGE234_TAG}.csv"
POSITION_CHANGES_PATH = OUTPUT_DIR / f"{OFFICIAL_PREFIX}_position_changes_2020_2026_04.csv"

SAMPLES_ENRICHED_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_samples_enriched_{MODEL_TAG}.csv"
WINDOW_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_summary_{MODEL_TAG}.csv"
BUCKET_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_summary_{MODEL_TAG}.csv"
FEATURE_TABLE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_quality_table_{MODEL_TAG}.csv"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
MANIFEST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_manifest_{MODEL_TAG}.json"

HORIZONS = (10, 20)
QUALITY_LABEL_MIN_MFE_R = 2.0
QUALITY_LABEL_MIN_MAE_R = -1.0
EVENTUAL_BIG_WINNER_R = 2.0
EVENTUAL_FAILURE_R = -1.0
EMBARGO_DAYS = 20

FEATURE_COLS = [
    "direction_key",
    "signal",
    "pairwise_rank_bucket",
    "ai_rank_bucket",
    "rsi_bucket",
    "portfolio_dd_bucket",
    "corr_bucket",
    "active_positions_bucket",
    "breakout_bucket",
    "risk_mode_bucket",
]

WALK_FORWARD_WINDOWS = [
    {"window_name": "wf_2022_train_2020_2021", "train_start": "2020-01-01", "test_start": "2022-01-01", "test_end": "2022-12-31"},
    {"window_name": "wf_2023_train_2020_2022", "train_start": "2020-01-01", "test_start": "2023-01-01", "test_end": "2023-12-31"},
    {"window_name": "wf_2024_train_2020_2023", "train_start": "2020-01-01", "test_start": "2024-01-01", "test_end": "2024-12-31"},
    {"window_name": "wf_2025_train_2020_2024", "train_start": "2020-01-01", "test_start": "2025-01-01", "test_end": "2025-12-31"},
    {"window_name": "wf_2026_train_2020_2025", "train_start": "2020-01-01", "test_start": "2026-01-01", "test_end": "2026-12-31"},
]


def _to_markdown(df: pd.DataFrame, max_rows: int = 40) -> str:
    if df.empty:
        return "_empty_"
    return df.head(max_rows).to_markdown(index=False)


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or np.isinf(result):
        return default
    return result


def _clean_bucket(series: pd.Series, fallback: str = "missing") -> pd.Series:
    return series.astype(str).replace({"nan": fallback, "None": fallback, "": fallback}).fillna(fallback)


def _bucket_drawdown(value: Any) -> str:
    drawdown = _safe_float(value)
    if pd.isna(drawdown):
        return "missing"
    drawdown_pct = drawdown * 100.0 if abs(drawdown) <= 1.0 else drawdown
    if drawdown_pct <= 5:
        return "dd_0_5"
    if drawdown_pct <= 15:
        return "dd_5_15"
    return "dd_gt_15"


def _bucket_corr(value: Any) -> str:
    corr = _safe_float(value)
    if pd.isna(corr):
        return "missing"
    if corr < 0.4:
        return "corr_lt_04"
    if corr < 0.7:
        return "corr_04_07"
    return "corr_gt_07"


def _bucket_active_positions(value: Any) -> str:
    active = _safe_float(value)
    if pd.isna(active):
        return "missing"
    if active <= 2:
        return "active_0_2"
    if active <= 5:
        return "active_3_5"
    return "active_gt_5"


def load_stage234_samples() -> pd.DataFrame:
    samples = pd.read_csv(SAMPLES_INPUT_PATH)
    date_cols = ["entry_date", "first_exit_date", "last_exit_date"]
    for col in date_cols:
        if col in samples.columns:
            samples[col] = pd.to_datetime(samples[col].astype(str).str.slice(0, 10), errors="coerce").dt.normalize()
    numeric_cols = [
        "realized_pnl",
        "risk_reward_proxy",
        "portfolio_drawdown_pct",
        "same_direction_correlation_max_corr",
        "active_positions_before",
        "breakout",
        "planned_entry_price",
        "stop_distance",
    ]
    for col in numeric_cols:
        if col in samples.columns:
            samples[col] = pd.to_numeric(samples[col], errors="coerce")
    samples["entry_year"] = samples["entry_date"].dt.year
    samples["entry_risk_pct"] = np.where(
        pd.to_numeric(samples.get("planned_entry_price"), errors="coerce").fillna(0.0) > 0,
        pd.to_numeric(samples.get("stop_distance"), errors="coerce").fillna(0.0)
        / pd.to_numeric(samples.get("planned_entry_price"), errors="coerce").replace(0, np.nan)
        * 100.0,
        np.nan,
    )
    samples["portfolio_dd_bucket"] = samples.get("portfolio_drawdown_pct", pd.Series(index=samples.index)).map(_bucket_drawdown)
    samples["corr_bucket"] = samples.get("same_direction_correlation_max_corr", pd.Series(index=samples.index)).map(_bucket_corr)
    samples["active_positions_bucket"] = samples.get("active_positions_before", pd.Series(index=samples.index)).map(_bucket_active_positions)
    samples["breakout_bucket"] = np.where(pd.to_numeric(samples.get("breakout"), errors="coerce").fillna(0).astype(int).eq(1), "breakout", "non_breakout")
    samples["risk_mode_bucket"] = _clean_bucket(samples.get("risk_mode", pd.Series(index=samples.index)).fillna("missing"))
    for col in FEATURE_COLS:
        samples[col] = _clean_bucket(samples[col])
    return samples


def load_price_frames() -> dict[str, pd.DataFrame]:
    prices = pd.read_csv(POSITION_CHANGES_PATH, usecols=["date", "vt_symbol", "close_price"])
    prices["date"] = pd.to_datetime(prices["date"], errors="coerce").dt.normalize()
    prices["close_price"] = pd.to_numeric(prices["close_price"], errors="coerce")
    prices = prices[prices["close_price"].fillna(0.0) > 0].copy()
    frames: dict[str, pd.DataFrame] = {}
    for vt_symbol, group in prices.groupby("vt_symbol"):
        frames[str(vt_symbol)] = group.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    return frames


def add_forward_path_metrics(samples: pd.DataFrame, price_frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in samples.to_dict(orient="records"):
        result = dict(row)
        vt_symbol = str(row.get("vt_symbol", ""))
        frame = price_frames.get(vt_symbol)
        entry_price = _safe_float(row.get("planned_entry_price"))
        direction = str(row.get("direction_key", "")).lower()
        sign = 1.0 if direction == "long" else -1.0
        if frame is None or frame.empty or pd.isna(entry_price) or entry_price <= 0:
            for horizon in HORIZONS:
                result[f"complete_{horizon}d"] = 0
                result[f"return_{horizon}d_pct"] = np.nan
                result[f"mfe_{horizon}d_pct"] = np.nan
                result[f"mae_{horizon}d_pct"] = np.nan
            rows.append(result)
            continue
        dates = frame["date"].to_numpy(dtype="datetime64[ns]")
        closes = frame["close_price"].to_numpy(dtype=float)
        entry_date = np.datetime64(pd.Timestamp(row["entry_date"]).to_datetime64())
        start_idx = int(np.searchsorted(dates, entry_date, side="left"))
        if start_idx >= len(frame) or dates[start_idx] != entry_date:
            start_idx = int(np.searchsorted(dates, entry_date, side="right")) - 1
        for horizon in HORIZONS:
            target_idx = start_idx + horizon
            if start_idx < 0 or target_idx >= len(frame):
                result[f"complete_{horizon}d"] = 0
                result[f"return_{horizon}d_pct"] = np.nan
                result[f"mfe_{horizon}d_pct"] = np.nan
                result[f"mae_{horizon}d_pct"] = np.nan
                continue
            path = closes[start_idx + 1 : target_idx + 1]
            if len(path) < horizon:
                result[f"complete_{horizon}d"] = 0
                result[f"return_{horizon}d_pct"] = np.nan
                result[f"mfe_{horizon}d_pct"] = np.nan
                result[f"mae_{horizon}d_pct"] = np.nan
                continue
            directional_path = (path / entry_price - 1.0) * sign * 100.0
            result[f"complete_{horizon}d"] = 1
            result[f"return_{horizon}d_pct"] = float(directional_path[-1])
            result[f"mfe_{horizon}d_pct"] = float(np.nanmax(directional_path))
            result[f"mae_{horizon}d_pct"] = float(np.nanmin(directional_path))
        rows.append(result)
    enriched = pd.DataFrame(rows)
    for horizon in HORIZONS:
        enriched[f"mfe_{horizon}d_r"] = enriched[f"mfe_{horizon}d_pct"] / enriched["entry_risk_pct"]
        enriched[f"mae_{horizon}d_r"] = enriched[f"mae_{horizon}d_pct"] / enriched["entry_risk_pct"]
        enriched[f"return_{horizon}d_r"] = enriched[f"return_{horizon}d_pct"] / enriched["entry_risk_pct"]
    return enriched


def add_labels(samples: pd.DataFrame) -> pd.DataFrame:
    samples = samples.copy()
    samples["quality_label"] = (
        samples["complete_20d"].fillna(0).astype(int).eq(1)
        & samples["mfe_20d_r"].ge(QUALITY_LABEL_MIN_MFE_R)
        & samples["mae_10d_r"].ge(QUALITY_LABEL_MIN_MAE_R)
    ).astype(int)
    samples["eventual_big_winner_label"] = samples["risk_reward_proxy"].ge(EVENTUAL_BIG_WINNER_R).fillna(False).astype(int)
    samples["eventual_failure_label"] = samples["risk_reward_proxy"].le(EVENTUAL_FAILURE_R).fillna(False).astype(int)
    return samples


def build_feature_quality_table(train: pd.DataFrame, shrinkage: float = 20.0, min_count: int = 12) -> pd.DataFrame:
    base_quality = float(train["quality_label"].mean())
    base_big_winner = float(train["eventual_big_winner_label"].mean())
    base_failure = float(train["eventual_failure_label"].mean())
    base_rr = float(train["risk_reward_proxy"].replace([np.inf, -np.inf], np.nan).mean())
    if np.isnan(base_rr):
        base_rr = 0.0

    rows: list[dict[str, Any]] = []
    for feature in FEATURE_COLS:
        grouped = (
            train.groupby(feature, dropna=False)
            .agg(
                sample_count=("quality_label", "size"),
                quality_rate=("quality_label", "mean"),
                big_winner_rate=("eventual_big_winner_label", "mean"),
                failure_rate=("eventual_failure_label", "mean"),
                avg_risk_reward_proxy=("risk_reward_proxy", "mean"),
            )
            .reset_index()
            .rename(columns={feature: "feature_value"})
        )
        for _, row in grouped.iterrows():
            count = float(row["sample_count"])
            quality_rate = float(row["quality_rate"])
            big_winner_rate = float(row["big_winner_rate"])
            failure_rate = float(row["failure_rate"])
            avg_rr = float(row["avg_risk_reward_proxy"])
            if np.isnan(avg_rr):
                avg_rr = base_rr
            shrunk_quality = (quality_rate * count + base_quality * shrinkage) / (count + shrinkage)
            shrunk_big_winner = (big_winner_rate * count + base_big_winner * shrinkage) / (count + shrinkage)
            shrunk_failure = (failure_rate * count + base_failure * shrinkage) / (count + shrinkage)
            shrunk_rr = (avg_rr * count + base_rr * shrinkage) / (count + shrinkage)
            support_weight = min(1.0, count / float(min_count))
            score = (
                (shrunk_quality - base_quality)
                + 0.8 * (shrunk_big_winner - base_big_winner)
                - 0.8 * (shrunk_failure - base_failure)
                + 0.06 * np.tanh(shrunk_rr)
            )
            score *= support_weight
            rows.append(
                {
                    "feature_name": feature,
                    "feature_value": str(row["feature_value"]),
                    "sample_count": int(row["sample_count"]),
                    "quality_rate_pct": quality_rate * 100.0,
                    "big_winner_rate_pct": big_winner_rate * 100.0,
                    "failure_rate_pct": failure_rate * 100.0,
                    "avg_risk_reward_proxy": avg_rr,
                    "shrunk_quality_rate_pct": shrunk_quality * 100.0,
                    "shrunk_big_winner_rate_pct": shrunk_big_winner * 100.0,
                    "shrunk_failure_rate_pct": shrunk_failure * 100.0,
                    "support_weight": support_weight,
                    "quality_score": score,
                }
            )
    return pd.DataFrame(rows)


def score_test_samples(test: pd.DataFrame, feature_quality: pd.DataFrame) -> pd.DataFrame:
    score_maps = {
        feature: dict(zip(group["feature_value"].astype(str), group["quality_score"]))
        for feature, group in feature_quality.groupby("feature_name")
    }
    scored = test.copy()
    score_components: list[pd.Series] = []
    for feature in FEATURE_COLS:
        component = scored[feature].astype(str).map(score_maps.get(feature, {})).fillna(0.0)
        scored[f"score_{feature}"] = component
        score_components.append(component)
    scored["quality_score"] = np.vstack([s.to_numpy(dtype=float) for s in score_components]).mean(axis=0)
    if len(scored) >= 3 and scored["quality_score"].nunique() >= 3:
        ranked = scored["quality_score"].rank(method="first", ascending=True)
        scored["score_bucket"] = pd.qcut(ranked, q=3, labels=["low", "mid", "high"]).astype(str)
    else:
        scored["score_bucket"] = "all"
    return scored


def build_purged_train(samples: pd.DataFrame, test_start: pd.Timestamp) -> pd.DataFrame:
    embargo_cutoff = test_start - pd.Timedelta(days=EMBARGO_DAYS)
    train = samples[samples["entry_date"] < embargo_cutoff].copy()
    # Purge labels whose lifecycle overlaps with the test start.
    if "last_exit_date" in train.columns:
        train = train[train["last_exit_date"].fillna(train["entry_date"]) < test_start].copy()
    return train


def summarize_bucket(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    grouped = (
        df.groupby(group_cols, dropna=False)
        .agg(
            sample_count=("quality_label", "size"),
            quality_rate_pct=("quality_label", lambda s: float(s.mean() * 100.0)),
            big_winner_rate_pct=("eventual_big_winner_label", lambda s: float(s.mean() * 100.0)),
            failure_rate_pct=("eventual_failure_label", lambda s: float(s.mean() * 100.0)),
            avg_realized_pnl=("realized_pnl", "mean"),
            avg_risk_reward_proxy=("risk_reward_proxy", "mean"),
            avg_quality_score=("quality_score", "mean"),
        )
        .reset_index()
    )
    return grouped


def run_walk_forward(samples: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    scored_rows: list[pd.DataFrame] = []
    window_rows: list[dict[str, Any]] = []
    bucket_rows: list[pd.DataFrame] = []
    feature_tables: list[pd.DataFrame] = []

    for window in WALK_FORWARD_WINDOWS:
        test_start = pd.Timestamp(window["test_start"])
        test_end = pd.Timestamp(window["test_end"])
        test = samples[(samples["entry_date"] >= test_start) & (samples["entry_date"] <= test_end)].copy()
        train = build_purged_train(samples, test_start)
        if train.empty or test.empty:
            continue

        feature_quality = build_feature_quality_table(train)
        feature_quality["window_name"] = window["window_name"]
        feature_tables.append(feature_quality)

        scored = score_test_samples(test, feature_quality)
        scored["window_name"] = window["window_name"]
        scored_rows.append(scored)

        bucket = summarize_bucket(scored, ["window_name", "score_bucket"])
        bucket_rows.append(bucket)

        high = scored[scored["score_bucket"].eq("high")]
        low = scored[scored["score_bucket"].eq("low")]
        all_big_winners = int(scored["eventual_big_winner_label"].sum())
        high_big_winners = int(high["eventual_big_winner_label"].sum()) if not high.empty else 0
        window_rows.append(
            {
                "window_name": window["window_name"],
                "train_sample_count": int(len(train)),
                "test_sample_count": int(len(scored)),
                "all_quality_rate_pct": float(scored["quality_label"].mean() * 100.0),
                "high_quality_rate_pct": float(high["quality_label"].mean() * 100.0) if not high.empty else np.nan,
                "low_quality_rate_pct": float(low["quality_label"].mean() * 100.0) if not low.empty else np.nan,
                "high_minus_low_quality_pct": (
                    float(high["quality_label"].mean() * 100.0 - low["quality_label"].mean() * 100.0)
                    if not high.empty and not low.empty
                    else np.nan
                ),
                "all_big_winner_rate_pct": float(scored["eventual_big_winner_label"].mean() * 100.0),
                "high_big_winner_rate_pct": float(high["eventual_big_winner_label"].mean() * 100.0) if not high.empty else np.nan,
                "low_big_winner_rate_pct": float(low["eventual_big_winner_label"].mean() * 100.0) if not low.empty else np.nan,
                "all_failure_rate_pct": float(scored["eventual_failure_label"].mean() * 100.0),
                "high_failure_rate_pct": float(high["eventual_failure_label"].mean() * 100.0) if not high.empty else np.nan,
                "low_failure_rate_pct": float(low["eventual_failure_label"].mean() * 100.0) if not low.empty else np.nan,
                "all_avg_rr": float(scored["risk_reward_proxy"].mean()),
                "high_avg_rr": float(high["risk_reward_proxy"].mean()) if not high.empty else np.nan,
                "low_avg_rr": float(low["risk_reward_proxy"].mean()) if not low.empty else np.nan,
                "all_big_winner_count": all_big_winners,
                "high_big_winner_count": high_big_winners,
                "high_big_winner_capture_pct": (high_big_winners / all_big_winners * 100.0) if all_big_winners else 0.0,
            }
        )

    scored_samples = pd.concat(scored_rows, ignore_index=True) if scored_rows else pd.DataFrame()
    window_summary = pd.DataFrame(window_rows)
    bucket_summary = pd.concat(bucket_rows, ignore_index=True) if bucket_rows else pd.DataFrame()
    feature_quality = pd.concat(feature_tables, ignore_index=True) if feature_tables else pd.DataFrame()
    return scored_samples, window_summary, bucket_summary, feature_quality


def build_report(
    samples: pd.DataFrame,
    scored_samples: pd.DataFrame,
    window_summary: pd.DataFrame,
    bucket_summary: pd.DataFrame,
    feature_quality: pd.DataFrame,
) -> str:
    top_features = feature_quality.sort_values("quality_score", ascending=False).head(20) if not feature_quality.empty else pd.DataFrame()
    lines = [
        "# Stage236 Path-aware 信号质量验证",
        "",
        "## 口径",
        "",
        f"- 基准：`{OFFICIAL_STAGE78_SHORT_ALIAS}` / `{OFFICIAL_STAGE78_VERSION}`",
        "- 方法：在 Stage234 真实开仓样本基础上，补充 10d/20d MFE/MAE 路径指标，构造更贴近“是否值得加注”的路径标签。",
        f"- 路径标签：`quality_label = (mfe_20d_r >= {QUALITY_LABEL_MIN_MFE_R}) and (mae_10d_r >= {QUALITY_LABEL_MIN_MAE_R})`。",
        f"- 大赢家标签：`risk_reward_proxy >= {EVENTUAL_BIG_WINNER_R}`；失败标签：`risk_reward_proxy <= {EVENTUAL_FAILURE_R}`。",
        f"- 验证：purged expanding walk-forward，训练集对测试起点做 `{EMBARGO_DAYS}` 天 embargo，并剔除与测试起点标签区间重叠的训练样本。",
        "",
        "## 全样本标签概况",
        "",
        f"- 样本数：`{len(samples)}`。",
        f"- 路径高质量标签占比：`{samples['quality_label'].mean() * 100.0:.2f}%`。",
        f"- 最终大赢家占比：`{samples['eventual_big_winner_label'].mean() * 100.0:.2f}%`。",
        f"- 最终失败占比：`{samples['eventual_failure_label'].mean() * 100.0:.2f}%`。",
        "",
        "## Walk-forward 窗口结果",
        "",
        _to_markdown(window_summary, max_rows=20),
        "",
        "## 分桶结果",
        "",
        _to_markdown(bucket_summary, max_rows=80),
        "",
        "## 训练期高质量特征桶样例",
        "",
        _to_markdown(top_features, max_rows=20),
        "",
        "## 初步判断",
        "",
        f"- OOS scored samples：`{len(scored_samples)}`。",
        "- 若高分桶同时提升 `quality_label`、提升 `big_winner_rate`、降低 `failure_rate`，且不丢失太多大赢家，则说明方向更接近可用。",
        "- 若这些指标仍不能稳定同向改善，则说明当前可见特征仍不足以支撑信号质量加注。",
        "",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    samples = load_stage234_samples()
    price_frames = load_price_frames()
    samples = add_forward_path_metrics(samples, price_frames)
    samples = add_labels(samples)
    scored_samples, window_summary, bucket_summary, feature_quality = run_walk_forward(samples)

    samples.to_csv(SAMPLES_ENRICHED_PATH, index=False, encoding="utf-8-sig")
    scored_samples.to_csv(OUTPUT_DIR / f"{OUTPUT_PREFIX}_scored_samples_{MODEL_TAG}.csv", index=False, encoding="utf-8-sig")
    window_summary.to_csv(WINDOW_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    bucket_summary.to_csv(BUCKET_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    feature_quality.to_csv(FEATURE_TABLE_PATH, index=False, encoding="utf-8-sig")
    REPORT_PATH.write_text(build_report(samples, scored_samples, window_summary, bucket_summary, feature_quality), encoding="utf-8")
    MANIFEST_PATH.write_text(
        json.dumps(
            {
                "model_tag": MODEL_TAG,
                "official_manifest": build_official_stage78_manifest(),
                "base_risk_ratio": BASE_RISK_RATIO,
                "capital": OFFICIAL_STAGE78_CAPITAL,
                "label_definition": {
                    "quality_label_min_mfe_r": QUALITY_LABEL_MIN_MFE_R,
                    "quality_label_min_mae_r": QUALITY_LABEL_MIN_MAE_R,
                    "eventual_big_winner_r": EVENTUAL_BIG_WINNER_R,
                    "eventual_failure_r": EVENTUAL_FAILURE_R,
                    "embargo_days": EMBARGO_DAYS,
                },
                "feature_cols": FEATURE_COLS,
                "walk_forward_windows": WALK_FORWARD_WINDOWS,
                "paths": {
                    "input_samples": str(SAMPLES_INPUT_PATH.resolve()),
                    "position_changes": str(POSITION_CHANGES_PATH.resolve()),
                    "samples_enriched": str(SAMPLES_ENRICHED_PATH.resolve()),
                    "window_summary": str(WINDOW_SUMMARY_PATH.resolve()),
                    "bucket_summary": str(BUCKET_SUMMARY_PATH.resolve()),
                    "feature_quality_table": str(FEATURE_TABLE_PATH.resolve()),
                    "report": str(REPORT_PATH.resolve()),
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(REPORT_PATH.resolve())
    print(window_summary.to_string(index=False))
    print(bucket_summary.to_string(index=False))


if __name__ == "__main__":
    main()
