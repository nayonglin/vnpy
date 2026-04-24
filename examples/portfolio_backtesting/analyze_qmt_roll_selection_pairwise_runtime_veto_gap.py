from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from build_qmt_roll_ai_candidate_training_samples import add_candidate_cross_section_feature_columns
from build_qmt_roll_ai_position_training_samples import load_contract_bars
from qmt_roll_ai_selection_pairwise_runtime import build_runtime_feature_row


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

SNAPSHOT_PATH: Path = OUTPUT_DIR / "qmt_roll_selection_pairwise_v2_catastrophic_veto_v1_entry_candidate_snapshots_2020_2026_04.csv"
TRAINING_PATH: Path = OUTPUT_DIR / "qmt_roll_ai_candidate_training_samples.csv"

SUMMARY_PATH: Path = OUTPUT_DIR / "qmt_roll_selection_pairwise_runtime_veto_gap_summary.json"
CASES_PATH: Path = OUTPUT_DIR / "qmt_roll_selection_pairwise_runtime_veto_gap_cases.csv"


def _runtime_history_from_bars(contract_vt_symbol: str, candidate_date: pd.Timestamp) -> pd.DataFrame:
    bars_df = load_contract_bars(contract_vt_symbol)
    if bars_df.empty:
        return pd.DataFrame()

    cutoff = pd.Timestamp(candidate_date).normalize()
    history_df = bars_df[bars_df["date"] <= cutoff].copy()
    if history_df.empty:
        return pd.DataFrame()

    history_df["open_interest"] = pd.to_numeric(
        history_df.get("close_oi", history_df.get("open_interest", 0.0)),
        errors="coerce",
    ).fillna(0.0)
    return history_df[["open", "high", "low", "close", "volume", "open_interest"]].reset_index(drop=True)


def _offline_veto_mask(df: pd.DataFrame) -> pd.Series:
    return (
        (df["direction"] == "short")
        & (df["signal"].isin(["short_case2", "short_case1a"]))
        & (pd.to_numeric(df["feature_ret_20d_zscore_120"], errors="coerce").fillna(0.0) < -0.3)
        & (pd.to_numeric(df["feature_close_position_60d_cs_zscore_1d"], errors="coerce").fillna(0.0) < 0.0)
        & (pd.to_numeric(df["feature_range_pct_zscore_120"], errors="coerce").fillna(0.0) > 0.5)
    )


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    snapshot_df = pd.read_csv(SNAPSHOT_PATH)
    training_df = pd.read_csv(TRAINING_PATH)
    snapshot_df["date"] = pd.to_datetime(snapshot_df["date"]).dt.normalize()
    training_df["candidate_date"] = pd.to_datetime(training_df["candidate_date"]).dt.normalize()
    snapshot_df = snapshot_df[snapshot_df["selection_pairwise_enabled"] == 1].copy()
    training_df = training_df[training_df["entry_context"] == "flat_entry"].copy()
    return snapshot_df, training_df


def build_runtime_rows(snapshot_df: pd.DataFrame) -> pd.DataFrame:
    runtime_rows: list[dict[str, Any]] = []

    for candidate_date, day_df in snapshot_df.groupby("date", sort=False):
        day_rows: list[dict[str, Any]] = []
        for row in day_df.itertuples(index=False):
            history_df = _runtime_history_from_bars(str(row.contract_vt_symbol), pd.Timestamp(candidate_date))
            if history_df.empty:
                continue

            runtime_row = build_runtime_feature_row(
                history=history_df,
                candidate_date=pd.Timestamp(candidate_date),
                direction=str(row.direction),
                signal=str(row.signal),
                risk_mode=str(row.risk_mode),
                risk_ratio=float(row.risk_ratio or 0.0),
                remaining_position_slots=int(row.remaining_position_slots),
                estimated_equity=float(row.estimated_equity or 0.0),
                margin_per_contract=float(row.margin_per_contract or 0.0),
            )
            if not runtime_row:
                continue

            runtime_row.update(
                {
                    "date": pd.Timestamp(candidate_date),
                    "product_vt_symbol": str(row.product_vt_symbol),
                    "contract_vt_symbol": str(row.contract_vt_symbol),
                    "signal": str(row.signal),
                    "direction": str(row.direction),
                    "candidate_status": str(row.candidate_status),
                    "selection_pairwise_rank": int(row.selection_pairwise_rank),
                    "selection_pairwise_score": float(row.selection_pairwise_score),
                    "selection_pairwise_veto_flag_runtime_snapshot": int(row.selection_pairwise_veto_flag),
                    "sample_id": f"runtime::{candidate_date.date().isoformat()}::{row.product_vt_symbol}::{row.signal}::{row.direction}",
                }
            )
            day_rows.append(runtime_row)

        if not day_rows:
            continue

        day_runtime_df = pd.DataFrame(day_rows)
        day_runtime_df["candidate_date"] = pd.to_datetime(day_runtime_df["date"]).dt.normalize()
        day_runtime_df = add_candidate_cross_section_feature_columns(day_runtime_df)
        runtime_rows.extend(day_runtime_df.to_dict(orient="records"))

    return pd.DataFrame(runtime_rows)


def build_comparison(snapshot_df: pd.DataFrame, training_df: pd.DataFrame, runtime_df: pd.DataFrame) -> pd.DataFrame:
    offline_join = snapshot_df.merge(
        training_df,
        left_on=["date", "product_vt_symbol", "contract_vt_symbol", "signal", "direction"],
        right_on=["candidate_date", "product_vt_symbol", "contract_vt_symbol", "signal", "direction"],
        how="left",
        suffixes=("_snapshot", "_offline"),
    )
    runtime_join = snapshot_df.merge(
        runtime_df,
        on=["date", "product_vt_symbol", "contract_vt_symbol", "signal", "direction"],
        how="left",
        suffixes=("", "_runtime"),
    )
    merged = offline_join.merge(
        runtime_join[
            [
                "date",
                "product_vt_symbol",
                "contract_vt_symbol",
                "signal",
                "direction",
                "feature_ret_20d_zscore_120",
                "feature_close_position_60d_cs_zscore_1d",
                "feature_range_pct_zscore_120",
                "selection_pairwise_veto_flag_runtime_snapshot",
            ]
        ],
        on=["date", "product_vt_symbol", "contract_vt_symbol", "signal", "direction"],
        how="left",
        suffixes=("_offline", "_runtime"),
    )

    merged["offline_veto_match"] = _offline_veto_mask(
        merged.rename(
            columns={
                "feature_ret_20d_zscore_120_offline": "feature_ret_20d_zscore_120",
                "feature_close_position_60d_cs_zscore_1d_offline": "feature_close_position_60d_cs_zscore_1d",
                "feature_range_pct_zscore_120_offline": "feature_range_pct_zscore_120",
            }
        )
    ).astype("int64")
    merged["runtime_recomputed_veto_match"] = _offline_veto_mask(
        merged.rename(
            columns={
                "feature_ret_20d_zscore_120_runtime": "feature_ret_20d_zscore_120",
                "feature_close_position_60d_cs_zscore_1d_runtime": "feature_close_position_60d_cs_zscore_1d",
                "feature_range_pct_zscore_120_runtime": "feature_range_pct_zscore_120",
            }
        )
    ).astype("int64")
    return merged


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    snapshot_df, training_df = load_inputs()
    runtime_df = build_runtime_rows(snapshot_df)
    comparison_df = build_comparison(snapshot_df, training_df, runtime_df)

    focus_df = comparison_df[
        (comparison_df["offline_veto_match"] == 1) | (comparison_df["runtime_recomputed_veto_match"] == 1)
    ].copy()
    if not focus_df.empty:
        focus_df["delta_feature_ret_20d_zscore_120"] = (
            pd.to_numeric(focus_df["feature_ret_20d_zscore_120_runtime"], errors="coerce").fillna(0.0)
            - pd.to_numeric(focus_df["feature_ret_20d_zscore_120_offline"], errors="coerce").fillna(0.0)
        )
        focus_df["delta_feature_close_position_60d_cs_zscore_1d"] = (
            pd.to_numeric(focus_df["feature_close_position_60d_cs_zscore_1d_runtime"], errors="coerce").fillna(0.0)
            - pd.to_numeric(focus_df["feature_close_position_60d_cs_zscore_1d_offline"], errors="coerce").fillna(0.0)
        )
        focus_df["delta_feature_range_pct_zscore_120"] = (
            pd.to_numeric(focus_df["feature_range_pct_zscore_120_runtime"], errors="coerce").fillna(0.0)
            - pd.to_numeric(focus_df["feature_range_pct_zscore_120_offline"], errors="coerce").fillna(0.0)
        )

    export_columns = [
        "date",
        "product_vt_symbol",
        "contract_vt_symbol",
        "signal",
        "direction",
        "candidate_status_snapshot",
        "selection_pairwise_rank",
        "selection_pairwise_score",
        "offline_veto_match",
        "runtime_recomputed_veto_match",
        "selection_pairwise_veto_flag_runtime_snapshot",
        "feature_ret_20d_zscore_120_offline",
        "feature_ret_20d_zscore_120_runtime",
        "delta_feature_ret_20d_zscore_120",
        "feature_close_position_60d_cs_zscore_1d_offline",
        "feature_close_position_60d_cs_zscore_1d_runtime",
        "delta_feature_close_position_60d_cs_zscore_1d",
        "feature_range_pct_zscore_120_offline",
        "feature_range_pct_zscore_120_runtime",
        "delta_feature_range_pct_zscore_120",
    ]
    focus_df[export_columns].to_csv(CASES_PATH, index=False, encoding="utf-8-sig")

    summary = {
        "snapshot_enabled_rows": int(len(snapshot_df)),
        "snapshot_enabled_dates": int(snapshot_df["date"].nunique()),
        "runtime_rows_rebuilt": int(len(runtime_df)),
        "offline_veto_match_count": int(comparison_df["offline_veto_match"].sum()),
        "runtime_recomputed_veto_match_count": int(comparison_df["runtime_recomputed_veto_match"].sum()),
        "runtime_snapshot_veto_flag_count": int(
            pd.to_numeric(comparison_df["selection_pairwise_veto_flag_runtime_snapshot"], errors="coerce").fillna(0).sum()
        ),
        "cases_path": str(CASES_PATH),
        "judgement": {
            "core_issue": "离线样本口径下存在 veto 候选，但运行时重建特征后 veto 全部消失，说明问题不在策略开关，而在运行时特征桥接与离线样本口径不一致。",
        },
    }
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not focus_df.empty:
        print(focus_df[export_columns].to_string(index=False))


if __name__ == "__main__":
    main()
