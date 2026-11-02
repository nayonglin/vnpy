from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from build_qmt_roll_ai_candidate_selection_pairwise_samples import choose_left_right
from build_qmt_roll_ai_candidate_selection_pairwise_samples_v2 import FEATURE_COLUMNS_V2, build_pair_row_v2
from build_qmt_roll_ai_candidate_training_samples import add_candidate_cross_section_feature_columns
from build_qmt_roll_ai_position_training_samples import extract_market_features, load_contract_bars


PROJECT_DIR: Path = Path(__file__).resolve().parent
DEFAULT_MODEL_TAG: str = "selection_pairwise_v2_risk_weighted"
DEFAULT_MODEL_PATH: Path = (
    PROJECT_DIR / "backtest_outputs" / f"qmt_roll_ai_candidate_selection_pairwise_classifier_{DEFAULT_MODEL_TAG}.joblib"
)
DEFAULT_SUMMARY_PATH: Path = (
    PROJECT_DIR / "backtest_outputs" / f"qmt_roll_ai_candidate_selection_pairwise_classifier_summary_{DEFAULT_MODEL_TAG}.json"
)

PREDICTION_COLUMN: str = "predicted_pairwise_score"


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or np.isinf(result):
        return default
    return result


def build_runtime_feature_row(
    *,
    history: pd.DataFrame,
    contract_vt_symbol: str | None,
    candidate_date: pd.Timestamp,
    direction: str,
    signal: str,
    risk_mode: str,
    risk_ratio: float,
    remaining_position_slots: int,
    estimated_equity: float,
    margin_per_contract: float,
) -> dict[str, Any]:
    bars_df = pd.DataFrame()
    candidate_dt = pd.Timestamp(candidate_date).tz_localize(None).normalize()

    if contract_vt_symbol:
        contract_bars = load_contract_bars(str(contract_vt_symbol))
        if not contract_bars.empty:
            contract_dates = pd.to_datetime(contract_bars["date"], errors="coerce").dt.date
            bars_df = contract_bars.loc[contract_dates <= candidate_dt.date()].copy()

    if bars_df.empty:
        if history is None or history.empty:
            return {}
        bars_df = history.copy()
        bars_df = bars_df.reset_index(drop=True)
        bars_df["date"] = pd.date_range(end=candidate_dt, periods=len(bars_df), freq="D")
        open_interest = pd.to_numeric(
            bars_df.get("open_interest", pd.Series(0.0, index=bars_df.index)), errors="coerce"
        ).fillna(0.0)
        bars_df["close_oi"] = open_interest.astype("float64")
        bars_df["open_oi"] = bars_df["close_oi"].shift(1).fillna(bars_df["close_oi"])

    feature_row = extract_market_features(
        bars_df,
        entry_date=pd.Timestamp(bars_df["date"].iloc[-1]),
        direction=direction,
        signal=signal,
        risk_mode=risk_mode,
    )
    if not feature_row:
        return {}

    feature_row.update(
        {
            "candidate_date": pd.Timestamp(candidate_date).date().isoformat(),
            "risk_ratio": _safe_float(risk_ratio),
            "remaining_position_slots": int(remaining_position_slots),
            "feature_margin_per_contract_to_equity": (
                _safe_float(margin_per_contract) / max(_safe_float(estimated_equity), 1e-9)
            ),
        }
    )
    return feature_row


class SelectionPairwiseRuntimeModel:
    def __init__(
        self,
        *,
        model_path: str | Path = DEFAULT_MODEL_PATH,
        summary_path: str | Path = DEFAULT_SUMMARY_PATH,
        enable_catastrophic_veto: bool = False,
        catastrophic_veto_penalty: float = 1.5,
    ) -> None:
        self.model_path = Path(model_path)
        self.summary_path = Path(summary_path)
        summary = json.loads(self.summary_path.read_text(encoding="utf-8"))
        metadata = summary.get("model_metadata", {})
        self.feature_columns: list[str] = list(metadata.get("feature_columns", FEATURE_COLUMNS_V2))
        self.model = joblib.load(self.model_path)
        self.model_tag: str = str(summary.get("model_tag", DEFAULT_MODEL_TAG))
        self.enable_catastrophic_veto = bool(enable_catastrophic_veto)
        self.catastrophic_veto_penalty = float(catastrophic_veto_penalty)

    def _predict_daily_scores(self, candidate_df: pd.DataFrame) -> pd.DataFrame:
        scored_df = candidate_df.copy()
        scored_df[PREDICTION_COLUMN] = 0.0
        if len(scored_df) < 2:
            return scored_df

        ordered_rows = list(scored_df.itertuples(index=False, name="CandidateRow"))
        pair_rows: list[dict[str, Any]] = []
        pair_mappings: list[tuple[str, str]] = []
        for pair_index in range(len(ordered_rows)):
            for right_index in range(pair_index + 1, len(ordered_rows)):
                row_a = pd.Series(ordered_rows[pair_index]._asdict())
                row_b = pd.Series(ordered_rows[right_index]._asdict())
                left_row, right_row = choose_left_right(row_a, row_b)
                pair_rows.append(build_pair_row_v2(f"runtime__{pair_index:03d}_{right_index:03d}", left_row, right_row))
                pair_mappings.append((str(left_row["sample_id"]), str(right_row["sample_id"])))

        pair_df = pd.DataFrame(pair_rows)
        x = pair_df[self.feature_columns].copy()
        for column in self.feature_columns:
            x[column] = pd.to_numeric(x[column], errors="coerce").fillna(0.0)
        probabilities = np.asarray(self.model.predict_proba(x)[:, 1], dtype="float64")
        score_map = {str(sample_id): 0.0 for sample_id in scored_df["sample_id"].tolist()}
        for probability, (left_id, right_id) in zip(probabilities, pair_mappings):
            score_map[left_id] += float(probability)
            score_map[right_id] += float(1.0 - probability)
        scored_df[PREDICTION_COLUMN] = scored_df["sample_id"].map(score_map).astype("float64")
        return scored_df

    def _apply_catastrophic_veto(self, scored_df: pd.DataFrame) -> pd.DataFrame:
        veto_df = scored_df.copy()
        veto_mask = (
            (veto_df["direction"] == "short")
            & (veto_df["signal"].isin(["short_case2", "short_case1a"]))
            & (pd.to_numeric(veto_df["feature_ret_20d_zscore_120"], errors="coerce").fillna(0.0) < -0.3)
            & (pd.to_numeric(veto_df["feature_close_position_60d_cs_zscore_1d"], errors="coerce").fillna(0.0) < 0.0)
            & (pd.to_numeric(veto_df["feature_range_pct_zscore_120"], errors="coerce").fillna(0.0) > 0.5)
        )
        veto_df["selection_pairwise_veto_flag"] = veto_mask.astype("int64")
        veto_df.loc[veto_mask, PREDICTION_COLUMN] = (
            veto_df.loc[veto_mask, PREDICTION_COLUMN] - self.catastrophic_veto_penalty
        )
        return veto_df

    def score_candidate_pool(self, candidate_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not candidate_rows:
            return []

        candidate_df = pd.DataFrame(candidate_rows)
        candidate_df = add_candidate_cross_section_feature_columns(candidate_df)
        scored_df = self._predict_daily_scores(candidate_df)
        scored_df["selection_pairwise_veto_flag"] = 0
        if self.enable_catastrophic_veto:
            scored_df = self._apply_catastrophic_veto(scored_df)

        scored_df["selection_pairwise_rank"] = (
            scored_df[PREDICTION_COLUMN].rank(method="first", ascending=False).astype("int64")
        )
        scored_df["selection_pairwise_model_tag"] = self.model_tag
        scored_df["selection_pairwise_enabled"] = 1
        scored_df["selection_pairwise_veto_penalty"] = (
            self.catastrophic_veto_penalty if self.enable_catastrophic_veto else 0.0
        )
        return scored_df.to_dict(orient="records")
