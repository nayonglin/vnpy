from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from qmt_roll_ai_selection_pairwise_runtime import build_runtime_feature_row


PROJECT_DIR: Path = Path(__file__).resolve().parent
DEFAULT_MODEL_TAG: str = "stage163_ai_pure_path_damage_feasibility_v1"
DEFAULT_MODEL_PATH: Path = (
    PROJECT_DIR
    / "backtest_outputs"
    / "qmt_roll_stage163_ai_pure_path_damage_feasibility_model_stage163_ai_pure_path_damage_feasibility_v1.joblib"
)
DEFAULT_SUMMARY_PATH: Path = (
    PROJECT_DIR
    / "backtest_outputs"
    / "qmt_roll_stage163_ai_pure_path_damage_feasibility_summary_stage163_ai_pure_path_damage_feasibility_v1.json"
)

PREDICTION_COLUMN: str = "predicted_pure_path_damage_bad_probability"


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or np.isinf(result):
        return default
    return result


def build_path_damage_runtime_feature_row(
    *,
    history: pd.DataFrame,
    contract_vt_symbol: str | None,
    candidate_date: pd.Timestamp,
    direction: str,
    signal: str,
    risk_mode: str,
    risk_ratio: float,
    risk_multiplier: float,
    active_positions_before: int,
    remaining_position_slots: int,
    loss_streak: int,
    estimated_equity: float,
    margin_per_contract: float,
    risk_amount: float,
    allowed_capital: float,
    single_trade_capital_limit: float,
    feature_candidate_cross_section_count_1d: int,
) -> dict[str, Any]:
    feature_row = build_runtime_feature_row(
        history=history,
        contract_vt_symbol=contract_vt_symbol,
        candidate_date=candidate_date,
        direction=direction,
        signal=signal,
        risk_mode=risk_mode,
        risk_ratio=risk_ratio,
        remaining_position_slots=remaining_position_slots,
        estimated_equity=estimated_equity,
        margin_per_contract=margin_per_contract,
    )
    if not feature_row:
        return {}

    equity = max(_safe_float(estimated_equity), 1e-9)
    feature_row.update(
        {
            "active_positions_before": int(active_positions_before),
            "remaining_position_slots": int(remaining_position_slots),
            "loss_streak": int(loss_streak),
            "risk_ratio": _safe_float(risk_ratio),
            "risk_multiplier": _safe_float(risk_multiplier),
            "feature_target_risk_to_equity": _safe_float(risk_amount) / equity,
            "feature_allowed_capital_to_equity": _safe_float(allowed_capital) / equity,
            "feature_single_trade_capital_limit_to_equity": _safe_float(single_trade_capital_limit) / equity,
            "feature_candidate_cross_section_count_1d": int(feature_candidate_cross_section_count_1d),
        }
    )
    return feature_row


class PathDamageRuntimeModel:
    def __init__(
        self,
        *,
        model_path: str | Path = DEFAULT_MODEL_PATH,
        summary_path: str | Path = DEFAULT_SUMMARY_PATH,
    ) -> None:
        self.model_path = Path(model_path)
        self.summary_path = Path(summary_path)
        summary = json.loads(self.summary_path.read_text(encoding="utf-8"))
        self.model = joblib.load(self.model_path)
        self.model_tag: str = str(summary.get("model_tag", DEFAULT_MODEL_TAG))
        self.feature_columns: list[str] = list(summary.get("feature_columns", []))

    def score_candidate_pool(self, candidate_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not candidate_rows:
            return []

        scored_df = pd.DataFrame(candidate_rows)
        scored_df[PREDICTION_COLUMN] = 0.0
        if not self.feature_columns:
            scored_df["ai_path_damage_model_tag"] = self.model_tag
            return scored_df.to_dict(orient="records")

        x = scored_df.reindex(columns=self.feature_columns).copy()
        for column in self.feature_columns:
            x[column] = pd.to_numeric(x[column], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
        scored_df[PREDICTION_COLUMN] = np.asarray(self.model.predict_proba(x)[:, 1], dtype="float64")
        scored_df["ai_path_damage_model_tag"] = self.model_tag
        return scored_df.to_dict(orient="records")
