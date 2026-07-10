#!/usr/bin/env python3
"""Stage001: dated, same-day-aware marginal covariance risk budget A/C.

This research-only candidate runs after the current C9 candidate planning
pipeline.  It uses 63 date-aligned returns from the engine's daily history and
removes only the positive covariance portion of a new candidate's incremental
variance.  Earlier accepted candidates on the same day are included in the
temporary portfolio.  Existing holdings and all exit logic remain unchanged.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf


ROOT = Path(__file__).resolve().parents[4]
PORTFOLIO_DIR = ROOT / "examples" / "portfolio_backtesting"
PREVIOUS_TOOLS_DIR = ROOT / "research" / "lines" / "futures_trend_signed_covariance_risk_budget" / "tools"
SOURCE_TOOLS_DIR = ROOT / "research" / "lines" / "futures_trend_full_market_ai_filter_002risk" / "tools"
for item in (PORTFOLIO_DIR, PREVIOUS_TOOLS_DIR, SOURCE_TOOLS_DIR):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import stage001_signed_covariance_budget_engine as previous  # noqa: E402
from qmt_roll_official_live_config import OFFICIAL_LIVE_AI_ELIGIBILITY_PATH  # noqa: E402


s006 = previous.s006

LINE_ID = "futures_trend_marginal_covariance_risk_budget"
STAGE_ID = "stage001_dated_marginal_covariance_budget_engine"
STAGE_LABEL = "Stage001"
MODEL_TAG = f"{STAGE_ID}_v1"
OUTPUT_PREFIX = f"marginal_cov_budget_{STAGE_ID}"

REQUESTED_START = pd.Timestamp("2020-01-01")
REQUESTED_END = pd.Timestamp("2026-06-30")
START_MONTH = "2020-01"
CAPITAL = float(s006.base.CAPITAL)

LOOKBACK_RETURNS = 63
MIN_PRESERVED_VOLUME = 1
RETURN_RETENTION_MIN = 0.70
FULL_DD_IMPROVEMENT_MIN_PP = 3.0
YEAR_2022_DD_IMPROVEMENT_MIN_PP = 5.0
STRESS_DD_IMPROVEMENT_MIN_PP = 3.0
MIN_POTENTIAL_COVERAGE = 0.80

YEAR_2022_START = pd.Timestamp("2022-01-01")
YEAR_2022_END = pd.Timestamp("2022-12-31")
STRESS_START = pd.Timestamp("2022-07-15")
STRESS_END = pd.Timestamp("2024-05-10")

A_VERSION = "current_official_ai_c9_control"
C_VERSION = "current_official_ai_c9_dated_marginal_covariance_budget"
A_STRATEGY = "stage001_marginal_cov_control_official_ai"
C_STRATEGY = "stage001_marginal_cov_candidate_official_ai"
A_SCORE_TYPE = "current_official_ai_control"
C_SCORE_TYPE = "current_official_ai_dated_marginal_covariance_budget"

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / STAGE_ID
STAGES_DIR = LINE_DIR / "stages"
STAGE_RECORD_PATH = STAGES_DIR / "20260710_1804_stage001_dated_marginal_covariance_budget_engine.md"

A_ELIGIBILITY_PATH = OUT / f"{OUTPUT_PREFIX}_a_eligibility_{MODEL_TAG}.csv"
C_ELIGIBILITY_PATH = OUT / f"{OUTPUT_PREFIX}_c_eligibility_{MODEL_TAG}.csv"
A_DAILY_PATH = OUT / f"{OUTPUT_PREFIX}_a_daily_{MODEL_TAG}.csv.gz"
C_DAILY_PATH = OUT / f"{OUTPUT_PREFIX}_c_daily_{MODEL_TAG}.csv.gz"
A_ENTRY_PATH = OUT / f"{OUTPUT_PREFIX}_a_entry_candidates_{MODEL_TAG}.csv.gz"
C_ENTRY_PATH = OUT / f"{OUTPUT_PREFIX}_c_entry_candidates_{MODEL_TAG}.csv.gz"
A_RISK_PATH = OUT / f"{OUTPUT_PREFIX}_a_entry_risk_{MODEL_TAG}.csv.gz"
C_RISK_PATH = OUT / f"{OUTPUT_PREFIX}_c_entry_risk_{MODEL_TAG}.csv.gz"
A_TRADES_PATH = OUT / f"{OUTPUT_PREFIX}_a_trades_{MODEL_TAG}.csv.gz"
C_TRADES_PATH = OUT / f"{OUTPUT_PREFIX}_c_trades_{MODEL_TAG}.csv.gz"
A_TRADE_EVENTS_PATH = OUT / f"{OUTPUT_PREFIX}_a_trade_events_{MODEL_TAG}.csv.gz"
C_TRADE_EVENTS_PATH = OUT / f"{OUTPUT_PREFIX}_c_trade_events_{MODEL_TAG}.csv.gz"
A_STOP_RETRY_PATH = OUT / f"{OUTPUT_PREFIX}_a_stop_retry_events_{MODEL_TAG}.csv.gz"
C_STOP_RETRY_PATH = OUT / f"{OUTPUT_PREFIX}_c_stop_retry_events_{MODEL_TAG}.csv.gz"
A_CLOSED_PATH = OUT / f"{OUTPUT_PREFIX}_a_closed_lots_{MODEL_TAG}.csv.gz"
C_CLOSED_PATH = OUT / f"{OUTPUT_PREFIX}_c_closed_lots_{MODEL_TAG}.csv.gz"
CURVES_PATH = OUT / f"{OUTPUT_PREFIX}_ac_curves_{MODEL_TAG}.csv.gz"
SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_ac_summary_{MODEL_TAG}.csv"
STRESS_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_stress_summary_{MODEL_TAG}.csv"
MARGINAL_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_marginal_audit_{MODEL_TAG}.csv"
AI_PARITY_PATH = OUT / f"{OUTPUT_PREFIX}_ai_parity_{MODEL_TAG}.csv"
AI_USAGE_PATH = OUT / f"{OUTPUT_PREFIX}_ai_usage_{MODEL_TAG}.csv"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUT / f"{OUTPUT_PREFIX}_equity_drawdown_stress_{MODEL_TAG}.png"

CUSTOM_FIELDS = (
    "marginal_covariance_budget_enabled",
    "marginal_covariance_available",
    "marginal_covariance_sequence",
    "marginal_covariance_existing_leg_count",
    "marginal_covariance_same_day_leg_count",
    "marginal_covariance_contracts",
    "marginal_covariance_lookback_returns",
    "marginal_covariance_observations",
    "marginal_covariance_common_start_date",
    "marginal_covariance_common_end_date",
    "marginal_covariance_asof_date",
    "marginal_covariance_last_date_lag_days",
    "marginal_covariance_future_date_violation",
    "marginal_covariance_current_variance",
    "marginal_covariance_standalone_variance",
    "marginal_covariance_cross_term",
    "marginal_covariance_full_incremental_variance",
    "marginal_covariance_after_incremental_variance",
    "marginal_covariance_full_incremental_to_standalone",
    "marginal_covariance_diversifying",
    "marginal_covariance_weight",
    "marginal_covariance_selected_volume_before",
    "marginal_covariance_selected_volume_after",
    "marginal_covariance_volume_reduced",
)


class QmtRollPortfolioStrategyDatedMarginalCovarianceBudget(
    s006.base.s847.QmtRollPortfolioStrategyStage847C9StopRetry
):
    enable_dated_marginal_covariance_budget: bool = True
    marginal_covariance_lookback_returns: int = LOOKBACK_RETURNS

    parameters = s006.base.s847.QmtRollPortfolioStrategyStage847C9StopRetry.parameters + [
        "enable_dated_marginal_covariance_budget",
        "marginal_covariance_lookback_returns",
    ]

    def __init__(self, strategy_engine, strategy_name: str, vt_symbols: list[str], setting: dict) -> None:
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)
        self._dated_close_cache: dict[str, pd.Series] | None = None

    @staticmethod
    def _naive_normalized_date(value: Any) -> pd.Timestamp:
        result = pd.Timestamp(value)
        if result.tzinfo is not None:
            result = result.tz_localize(None)
        return result.normalize()

    @staticmethod
    def _direction_sign_text(direction: str) -> float:
        return 1.0 if str(direction).lower() == "long" else -1.0

    def _build_dated_close_cache(self) -> dict[str, pd.Series]:
        if self._dated_close_cache is not None:
            return self._dated_close_cache
        raw: dict[str, dict[pd.Timestamp, float]] = {}
        history_data = getattr(self.strategy_engine, "history_data", {}) or {}
        for key, bar in history_data.items():
            try:
                key_dt, key_symbol = key
            except (TypeError, ValueError):
                continue
            symbol = str(getattr(bar, "vt_symbol", "") or key_symbol)
            try:
                bar_date = self._naive_normalized_date(getattr(bar, "datetime", key_dt))
                close = float(getattr(bar, "close_price", np.nan))
            except (TypeError, ValueError):
                continue
            if not symbol or not np.isfinite(close) or close <= 0.0:
                continue
            raw.setdefault(symbol, {})[bar_date] = close
        self._dated_close_cache = {
            symbol: pd.Series(values, dtype="float64").sort_index()
            for symbol, values in raw.items()
            if values
        }
        return self._dated_close_cache

    def _active_legs(self) -> list[dict[str, Any]]:
        legs: list[dict[str, Any]] = []
        for state in self.states.values():
            contract = str(state.contract_vt_symbol or "")
            if not contract:
                continue
            volume = abs(int(self.get_pos(contract)))
            if volume <= 0:
                continue
            legs.append(
                {
                    "contract_vt_symbol": contract,
                    "direction": str(state.direction),
                    "volume": volume,
                    "source": "existing",
                }
            )
        return legs

    def _default_snapshot(self, selected_volume: int, sequence: int, active_legs: list[dict[str, Any]]) -> dict[str, Any]:
        existing_count = sum(1 for leg in active_legs if leg.get("source") == "existing")
        same_day_count = sum(1 for leg in active_legs if leg.get("source") == "same_day")
        return {
            "marginal_covariance_budget_enabled": int(bool(self.enable_dated_marginal_covariance_budget)),
            "marginal_covariance_available": 0,
            "marginal_covariance_sequence": int(sequence),
            "marginal_covariance_existing_leg_count": existing_count,
            "marginal_covariance_same_day_leg_count": same_day_count,
            "marginal_covariance_contracts": "",
            "marginal_covariance_lookback_returns": int(self.marginal_covariance_lookback_returns),
            "marginal_covariance_observations": 0,
            "marginal_covariance_common_start_date": "",
            "marginal_covariance_common_end_date": "",
            "marginal_covariance_asof_date": "",
            "marginal_covariance_last_date_lag_days": 0,
            "marginal_covariance_future_date_violation": 0,
            "marginal_covariance_current_variance": 0.0,
            "marginal_covariance_standalone_variance": 0.0,
            "marginal_covariance_cross_term": 0.0,
            "marginal_covariance_full_incremental_variance": 0.0,
            "marginal_covariance_after_incremental_variance": 0.0,
            "marginal_covariance_full_incremental_to_standalone": 1.0,
            "marginal_covariance_diversifying": 0,
            "marginal_covariance_weight": 1.0,
            "marginal_covariance_selected_volume_before": max(0, int(selected_volume)),
            "marginal_covariance_selected_volume_after": max(0, int(selected_volume)),
            "marginal_covariance_volume_reduced": 0,
        }

    def _dated_directional_returns(
        self,
        legs: list[dict[str, Any]],
        asof: pd.Timestamp,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        cache = self._build_dated_close_cache()
        close_parts: list[pd.Series] = []
        for index, leg in enumerate(legs):
            contract = str(leg["contract_vt_symbol"])
            close = cache.get(contract, pd.Series(dtype="float64"))
            if close.empty:
                return pd.DataFrame(), pd.DataFrame()
            visible = close[close.index <= asof].copy()
            if visible.empty:
                return pd.DataFrame(), pd.DataFrame()
            close_parts.append(visible.rename(f"leg_{index}"))
        common_close = pd.concat(close_parts, axis=1, join="inner").dropna().sort_index()
        common_close = common_close[~common_close.index.duplicated(keep="last")]
        required_closes = int(self.marginal_covariance_lookback_returns) + 1
        if len(common_close) < required_closes:
            return pd.DataFrame(), common_close
        common_close = common_close.tail(required_closes)
        returns = common_close.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
        if len(returns) != int(self.marginal_covariance_lookback_returns):
            return pd.DataFrame(), common_close
        for index, leg in enumerate(legs):
            returns.iloc[:, index] = returns.iloc[:, index] * self._direction_sign_text(str(leg["direction"]))
        return returns, common_close

    def _marginal_snapshot(
        self,
        *,
        plan: dict[str, Any],
        active_legs: list[dict[str, Any]],
        sequence: int,
    ) -> dict[str, Any]:
        selected_volume = max(0, int(plan.get("volume") or plan.get("sizing", {}).get("selected_volume") or 0))
        result = self._default_snapshot(selected_volume, sequence, active_legs)
        if not self.enable_dated_marginal_covariance_budget or selected_volume <= 0:
            return result

        asof = self._naive_normalized_date(plan["target_bar"].datetime)
        candidate_leg = {
            "contract_vt_symbol": str(plan["target_contract"]),
            "direction": str(plan["direction"]),
            "volume": selected_volume,
            "source": "candidate",
        }
        legs = [dict(item) for item in active_legs] + [candidate_leg]
        returns, common_close = self._dated_directional_returns(legs, asof)
        result["marginal_covariance_asof_date"] = asof.date().isoformat()
        result["marginal_covariance_contracts"] = "/".join(str(item["contract_vt_symbol"]) for item in legs)
        if returns.empty or common_close.empty:
            return result

        common_start = self._naive_normalized_date(returns.index.min())
        common_end = self._naive_normalized_date(returns.index.max())
        last_lag = int((asof - common_end).days)
        future_violation = int(common_end > asof)
        result.update(
            {
                "marginal_covariance_observations": int(len(returns)),
                "marginal_covariance_common_start_date": common_start.date().isoformat(),
                "marginal_covariance_common_end_date": common_end.date().isoformat(),
                "marginal_covariance_last_date_lag_days": last_lag,
                "marginal_covariance_future_date_violation": future_violation,
            }
        )
        if future_violation or last_lag != 0:
            return result
        matrix = returns.to_numpy(dtype="float64")
        if not np.isfinite(matrix).all():
            return result
        covariance = LedoitWolf().fit(matrix).covariance_
        if covariance.shape != (len(legs), len(legs)) or not np.isfinite(covariance).all():
            return result

        prices = common_close.iloc[-1].to_numpy(dtype="float64")
        notionals = np.asarray(
            [
                float(item["volume"])
                * float(self.get_size(str(item["contract_vt_symbol"])))
                * float(prices[index])
                for index, item in enumerate(legs)
            ],
            dtype="float64",
        )
        active_notional = notionals[:-1]
        candidate_notional = float(notionals[-1])
        current_variance = (
            float(active_notional @ covariance[:-1, :-1] @ active_notional)
            if len(active_notional)
            else 0.0
        )
        standalone_variance = float(candidate_notional * candidate_notional * covariance[-1, -1])
        cross_term = (
            float(candidate_notional * np.dot(active_notional, covariance[:-1, -1]))
            if len(active_notional)
            else 0.0
        )
        if standalone_variance <= 1e-12 or current_variance < -1e-9:
            return result

        full_incremental = standalone_variance + 2.0 * cross_term
        if cross_term <= 0.0:
            weight = 1.0
        else:
            weight = (
                -cross_term + math.sqrt(cross_term * cross_term + standalone_variance * standalone_variance)
            ) / standalone_variance
            weight = min(1.0, max(0.0, weight))

        selected_after = int(math.floor(selected_volume * weight + 0.5))
        selected_after = max(MIN_PRESERVED_VOLUME, min(selected_volume, selected_after))
        actual_weight = selected_after / max(1.0, float(selected_volume))
        after_incremental = (
            standalone_variance * actual_weight * actual_weight
            + 2.0 * cross_term * actual_weight
        )

        result.update(
            {
                "marginal_covariance_available": 1,
                "marginal_covariance_current_variance": current_variance,
                "marginal_covariance_standalone_variance": standalone_variance,
                "marginal_covariance_cross_term": cross_term,
                "marginal_covariance_full_incremental_variance": full_incremental,
                "marginal_covariance_after_incremental_variance": after_incremental,
                "marginal_covariance_full_incremental_to_standalone": (
                    full_incremental / standalone_variance
                ),
                "marginal_covariance_diversifying": int(cross_term <= 0.0),
                "marginal_covariance_weight": actual_weight,
                "marginal_covariance_selected_volume_before": selected_volume,
                "marginal_covariance_selected_volume_after": selected_after,
                "marginal_covariance_volume_reduced": selected_volume - selected_after,
            }
        )
        return result

    def _plan_flat_entry_candidates(self, day_contexts) -> dict[str, dict[str, Any]]:
        plans = super()._plan_flat_entry_candidates(day_contexts)
        active_legs = self._active_legs()
        sequence = 0
        for plan in plans.values():
            sizing = dict(plan.get("sizing") or {})
            selected_volume = max(0, int(plan.get("volume") or sizing.get("selected_volume") or 0))
            snapshot = self._default_snapshot(selected_volume, sequence, active_legs)
            if plan.get("candidate_status") == "opened" and selected_volume > 0:
                sequence += 1
                snapshot = self._marginal_snapshot(plan=plan, active_legs=active_legs, sequence=sequence)
                selected_after = int(snapshot["marginal_covariance_selected_volume_after"])
                sizing.update(snapshot)
                sizing["selected_volume"] = selected_after
                plan["sizing"] = sizing
                plan["volume"] = selected_after
                active_legs.append(
                    {
                        "contract_vt_symbol": str(plan["target_contract"]),
                        "direction": str(plan["direction"]),
                        "volume": selected_after,
                        "source": "same_day",
                    }
                )
            else:
                sizing.update(snapshot)
                plan["sizing"] = sizing
        return plans

    def _record_entry_candidate_snapshot(self, **kwargs: Any) -> None:
        sizing_snapshot = dict(kwargs.get("sizing_snapshot") or {})
        super()._record_entry_candidate_snapshot(**kwargs)
        if not self.entry_candidate_snapshots:
            return
        self.entry_candidate_snapshots[-1].update(
            {
                field: sizing_snapshot.get(
                    field,
                    "" if field.endswith(("contracts", "date")) else 0,
                )
                for field in CUSTOM_FIELDS
            }
        )


def _sha16(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def _normalized_ai_hash(frame: pd.DataFrame) -> str:
    return previous._normalized_ai_hash(frame)


def _metadata() -> dict[str, Any]:
    return s006._metadata()


def _profile(
    metadata: dict[str, Any],
    *,
    version: str,
    strategy_name: str,
    eligibility_path: Path,
    label: str,
    candidate: bool,
) -> dict[str, Any]:
    profile = s006._profile(
        metadata,
        version=version,
        strategy_name=strategy_name,
        eligibility_path=eligibility_path,
        label=label,
    )
    if not candidate:
        return profile
    spec = profile["spec"]
    overrides = {
        **spec.overrides,
        "enable_dated_marginal_covariance_budget": True,
        "marginal_covariance_lookback_returns": LOOKBACK_RETURNS,
    }
    result = dict(profile)
    result["profile"] = version
    result["strategy_cls"] = QmtRollPortfolioStrategyDatedMarginalCovarianceBudget
    result["spec"] = replace(spec, overrides=overrides, profile=version)
    return result


def _run(
    metadata: dict[str, Any], profile: dict[str, Any], version: str
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    daily, frames, _ = s006._run_profile(metadata, profile, version)
    daily = daily.copy()
    daily["stage"] = STAGE_LABEL
    daily["model_tag"] = MODEL_TAG
    daily["line_id"] = LINE_ID
    daily["requested_start_month"] = START_MONTH
    for frame in frames.values():
        if frame.empty:
            continue
        frame["stage"] = STAGE_LABEL
        frame["model_tag"] = MODEL_TAG
        frame["line_id"] = LINE_ID
        frame["start_month"] = START_MONTH
    return daily, frames


def _closed_lots(frames: dict[str, pd.DataFrame], metadata: dict[str, Any]) -> pd.DataFrame:
    return previous._closed_lots(frames, metadata)


def _save_frames(frames: dict[str, pd.DataFrame], paths: dict[str, Path]) -> None:
    previous._save_frames(frames, paths)


def _summary_row(curve: pd.DataFrame, closed: pd.DataFrame) -> dict[str, Any]:
    row = s006._summarize_curve(curve)
    row["stage"] = STAGE_LABEL
    row["model_tag"] = MODEL_TAG
    row["line_id"] = LINE_ID
    row["requested_start_month"] = START_MONTH
    realized = pd.to_numeric(closed.get("realized_pnl", pd.Series(dtype=float)), errors="coerce").dropna()
    row["closed_lot_count"] = int(len(realized))
    row["closed_lot_win_rate_pct"] = float((realized > 0.0).mean() * 100.0) if len(realized) else 0.0
    return row


def _longest_true_streak(values: pd.Series) -> int:
    flags = values.fillna(False).astype(bool)
    if flags.empty:
        return 0
    groups = flags.ne(flags.shift()).cumsum()
    lengths = flags.groupby(groups).sum()
    return int(lengths.max()) if len(lengths) else 0


def _window_metrics(
    daily: pd.DataFrame,
    *,
    version: str,
    window: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> dict[str, Any]:
    data = daily.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    data = data.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    equity_all = pd.to_numeric(data["account_equity"], errors="coerce").ffill()
    prior = data[data["date"] < start]
    seed_equity = float(pd.to_numeric(prior["account_equity"], errors="coerce").iloc[-1]) if len(prior) else CAPITAL
    part = data[(data["date"] >= start) & (data["date"] <= end)].copy().reset_index(drop=True)
    if part.empty:
        return {"version": version, "window": window, "rows": 0}
    equity = pd.to_numeric(part["account_equity"], errors="coerce").ffill().reset_index(drop=True)
    seeded = pd.concat([pd.Series([seed_equity]), equity], ignore_index=True)
    hwm = seeded.cummax().iloc[1:].reset_index(drop=True)
    drawdown = (equity / hwm - 1.0) * 100.0
    trough_idx = int(drawdown.idxmin())
    return {
        "version": version,
        "window": window,
        "window_start": start.date().isoformat(),
        "window_end": end.date().isoformat(),
        "actual_start": part["date"].iloc[0].date().isoformat(),
        "actual_end": part["date"].iloc[-1].date().isoformat(),
        "rows": int(len(part)),
        "start_equity": seed_equity,
        "end_equity": float(equity.iloc[-1]),
        "window_return_pct": float((equity.iloc[-1] / seed_equity - 1.0) * 100.0),
        "window_max_drawdown_pct": float(drawdown.min()),
        "window_trough_date": part.loc[trough_idx, "date"].date().isoformat(),
        "underwater_days": int((drawdown < 0.0).sum()),
        "longest_underwater_days": _longest_true_streak(drawdown < 0.0),
    }


def _stress_summary(daily_by_version: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for version, daily in daily_by_version.items():
        rows.append(
            _window_metrics(
                daily,
                version=version,
                window="year_2022",
                start=YEAR_2022_START,
                end=YEAR_2022_END,
            )
        )
        rows.append(
            _window_metrics(
                daily,
                version=version,
                window="main_2022_2024_stress",
                start=STRESS_START,
                end=STRESS_END,
            )
        )
    return pd.DataFrame(rows)


def _marginal_audit(entries: pd.DataFrame) -> pd.DataFrame:
    if entries.empty:
        return pd.DataFrame([{"sample": "all_candidates", "rows": 0}])
    data = entries.copy()
    numeric_fields = [field for field in CUSTOM_FIELDS if not field.endswith(("contracts", "date"))]
    for column in numeric_fields:
        data[column] = pd.to_numeric(data.get(column, 0), errors="coerce").fillna(0.0)
    data["selected_volume"] = pd.to_numeric(data.get("selected_volume", 0), errors="coerce").fillna(0.0)
    opened = pd.to_numeric(data.get("is_opened", 0), errors="coerce").fillna(0).astype(int).eq(1)
    potential = opened & data["marginal_covariance_existing_leg_count"].add(
        data["marginal_covariance_same_day_leg_count"]
    ).gt(0)
    available = data["marginal_covariance_available"].eq(1)
    reduced = data["marginal_covariance_volume_reduced"].gt(0)
    rows: list[dict[str, Any]] = []
    for sample, mask in (
        ("all_candidates", pd.Series(True, index=data.index)),
        ("opened", opened),
        ("potential_opened", potential),
        ("available", available),
        ("reduced", reduced),
        ("diversifying", available & data["marginal_covariance_diversifying"].eq(1)),
    ):
        part = data[mask]
        potential_rows = int((mask & potential).sum())
        available_potential = int((mask & potential & available).sum())
        rows.append(
            {
                "sample": sample,
                "rows": int(len(part)),
                "potential_rows": potential_rows,
                "available_rows": int((mask & available).sum()),
                "available_potential_rows": available_potential,
                "potential_coverage_ratio": (
                    available_potential / potential_rows if potential_rows else 1.0
                ),
                "reduced_rows": int((mask & reduced).sum()),
                "volume_before_sum": float(part["marginal_covariance_selected_volume_before"].sum()),
                "volume_after_sum": float(part["marginal_covariance_selected_volume_after"].sum()),
                "volume_reduced_sum": float(part["marginal_covariance_volume_reduced"].sum()),
                "weight_min": float(part["marginal_covariance_weight"].min()) if len(part) else 1.0,
                "weight_median": float(part["marginal_covariance_weight"].median()) if len(part) else 1.0,
                "observation_min": int(part.loc[part["marginal_covariance_available"].eq(1), "marginal_covariance_observations"].min()) if (part["marginal_covariance_available"].eq(1).any()) else 0,
                "observation_max": int(part["marginal_covariance_observations"].max()) if len(part) else 0,
                "future_date_violation_count": int(part["marginal_covariance_future_date_violation"].sum()),
                "last_date_lag_max": int(part["marginal_covariance_last_date_lag_days"].max()) if len(part) else 0,
                "final_gt_before_count": int(
                    (part["selected_volume"] > part["marginal_covariance_selected_volume_before"]).sum()
                ),
                "positive_before_zero_after_count": int(
                    (
                        part["marginal_covariance_selected_volume_before"].gt(0)
                        & part["selected_volume"].eq(0)
                    ).sum()
                ),
                "diversifying_reduced_count": int(
                    (
                        part["marginal_covariance_diversifying"].eq(1)
                        & part["marginal_covariance_volume_reduced"].gt(0)
                    ).sum()
                ),
                "same_day_visible_rows": int(part["marginal_covariance_same_day_leg_count"].gt(0).sum()),
                "max_same_day_leg_count": int(part["marginal_covariance_same_day_leg_count"].max()) if len(part) else 0,
            }
        )
    return pd.DataFrame(rows)


def _decision(
    summary: pd.DataFrame,
    stress: pd.DataFrame,
    audit: pd.DataFrame,
    ai_parity: pd.DataFrame,
) -> dict[str, Any]:
    a = summary[summary["version"].eq(A_VERSION)].iloc[0].to_dict()
    c = summary[summary["version"].eq(C_VERSION)].iloc[0].to_dict()
    a_2022 = stress[(stress["version"].eq(A_VERSION)) & (stress["window"].eq("year_2022"))].iloc[0]
    c_2022 = stress[(stress["version"].eq(C_VERSION)) & (stress["window"].eq("year_2022"))].iloc[0]
    a_stress = stress[(stress["version"].eq(A_VERSION)) & (stress["window"].eq("main_2022_2024_stress"))].iloc[0]
    c_stress = stress[(stress["version"].eq(C_VERSION)) & (stress["window"].eq("main_2022_2024_stress"))].iloc[0]
    potential = audit[audit["sample"].eq("potential_opened")].iloc[0]
    available = audit[audit["sample"].eq("available")].iloc[0]
    all_rows = audit[audit["sample"].eq("all_candidates")].iloc[0]

    retention = float(c["total_return_pct"] / a["total_return_pct"]) if float(a["total_return_pct"]) else 0.0
    full_dd_delta = float(c["max_drawdown_pct"] - a["max_drawdown_pct"])
    year_2022_dd_delta = float(c_2022["window_max_drawdown_pct"] - a_2022["window_max_drawdown_pct"])
    stress_dd_delta = float(c_stress["window_max_drawdown_pct"] - a_stress["window_max_drawdown_pct"])
    broker_delta = float(c["max_broker10_margin_to_equity_pct"] - a["max_broker10_margin_to_equity_pct"])
    # Same-day prior legs use accepted plan volume before the official end-of-day
    # forced-margin preview.  That is executable and conservative, but it does
    # not satisfy this stage's stronger "final official target" declaration.
    same_day_final_target_semantics_ok = False
    semantics_ok = (
        bool(ai_parity["normalized_equal"].all())
        and int(available["observation_min"]) == LOOKBACK_RETURNS
        and int(available["observation_max"]) == LOOKBACK_RETURNS
        and int(all_rows["future_date_violation_count"]) == 0
        and int(available["last_date_lag_max"]) == 0
        and int(all_rows["final_gt_before_count"]) == 0
        and int(all_rows["positive_before_zero_after_count"]) == 0
        and int(all_rows["diversifying_reduced_count"]) == 0
        and float(potential["potential_coverage_ratio"]) >= MIN_POTENTIAL_COVERAGE
        and same_day_final_target_semantics_ok
    )
    performance_ok = (
        float(c["total_return_pct"]) > 0.0
        and retention >= RETURN_RETENTION_MIN
        and full_dd_delta >= FULL_DD_IMPROVEMENT_MIN_PP
        and year_2022_dd_delta >= YEAR_2022_DD_IMPROVEMENT_MIN_PP
        and stress_dd_delta >= STRESS_DD_IMPROVEMENT_MIN_PP
        and broker_delta <= 1e-9
    )
    decision = (
        "stage001_continue_to_halfyear_if_independent_review_passes"
        if semantics_ok and performance_ok
        else "stage001_stop_no_parameter_rescue"
    )
    return {
        "stage": STAGE_LABEL,
        "stage_id": STAGE_ID,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S CST"),
        "requested_start": REQUESTED_START.date().isoformat(),
        "requested_end": REQUESTED_END.date().isoformat(),
        "lookback_returns": LOOKBACK_RETURNS,
        "a_control": a,
        "c_candidate": c,
        "a_year_2022": a_2022.to_dict(),
        "c_year_2022": c_2022.to_dict(),
        "a_main_stress": a_stress.to_dict(),
        "c_main_stress": c_stress.to_dict(),
        "return_retention_ratio": retention,
        "return_delta_pct": float(c["total_return_pct"] - a["total_return_pct"]),
        "full_drawdown_delta_pct": full_dd_delta,
        "year_2022_drawdown_delta_pct": year_2022_dd_delta,
        "main_stress_drawdown_delta_pct": stress_dd_delta,
        "sharpe_delta": float(c["sharpe"] - a["sharpe"]),
        "broker10_peak_delta_pct": broker_delta,
        "same_day_final_target_semantics_ok": same_day_final_target_semantics_ok,
        "semantics_ok": bool(semantics_ok),
        "performance_ok": bool(performance_ok),
        "decision": decision,
        "overfit_before": "low_to_medium: one frozen marginal-risk formula, fixed 63 aligned returns, no product/date/threshold tuning.",
        "overfit_after": "low: frozen one-shot test; no parameter rescue after failure",
        "continue_value_before": "yes: directly fixes prior P1 issues and targets correlated portfolio drawdown without deleting AI opportunities.",
        "continue_value_after": "no for this shape: performance failed and final-target same-day semantics has P1",
    }


def _plot(curves: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(16, 9))
    labels = {A_VERSION: "A current C9", C_VERSION: "C dated marginal covariance"}
    colors = {A_VERSION: "#111827", C_VERSION: "#0f766e"}
    for version, group in curves.groupby("version", sort=False):
        data = group.sort_values("date").copy()
        data["date"] = pd.to_datetime(data["date"], errors="coerce")
        equity = pd.to_numeric(data["account_equity_for_metrics"], errors="coerce").ffill()
        axes[0, 0].plot(data["date"], equity, label=labels.get(version, version), color=colors[version], linewidth=1.1)
        axes[1, 0].plot(data["date"], s006.base._drawdown_pct(equity), label=labels.get(version, version), color=colors[version], linewidth=1.0)

        stress = data[(data["date"] >= YEAR_2022_START) & (data["date"] <= STRESS_END)].copy()
        stress_equity = pd.to_numeric(stress["account_equity_for_metrics"], errors="coerce").ffill()
        if len(stress_equity):
            rebased = stress_equity / float(stress_equity.iloc[0])
            axes[0, 1].plot(stress["date"], rebased, label=labels.get(version, version), color=colors[version], linewidth=1.15)
            axes[1, 1].plot(stress["date"], s006.base._drawdown_pct(stress_equity), label=labels.get(version, version), color=colors[version], linewidth=1.0)

    axes[0, 0].axhline(CAPITAL, color="#64748b", linestyle="--", linewidth=0.8)
    axes[0, 0].set_title("Full-period absolute equity")
    axes[1, 0].set_title("Full-period drawdown")
    axes[0, 1].set_title("2022-01 to 2024-05 rebased equity")
    axes[1, 1].set_title("2022-01 to 2024-05 local drawdown")
    for axis in axes.flat:
        axis.grid(alpha=0.25)
        axis.legend(loc="best")
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=170)
    plt.close(fig)


def _append_once(path: Path, marker: str, content: str) -> None:
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if marker not in existing:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(content)


def _write_records(
    summary: pd.DataFrame,
    stress: pd.DataFrame,
    audit: pd.DataFrame,
    ai_parity: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    a = summary[summary["version"].eq(A_VERSION)].iloc[0]
    c = summary[summary["version"].eq(C_VERSION)].iloc[0]
    summary_view = summary[
        [
            "version",
            "end_equity",
            "total_return_pct",
            "max_drawdown_pct",
            "sharpe",
            "total_slippage",
            "total_trade_count",
            "nonzero_daily_win_rate_pct",
            "closed_lot_count",
            "closed_lot_win_rate_pct",
            "max_broker10_margin_to_equity_pct",
        ]
    ]
    report = f"""# Stage001 日期对齐边际协方差风险预算 A/C 真引擎

- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`
- line_id：`{LINE_ID}`
- 区间：`{REQUESTED_START.date()} -> {REQUESTED_END.date()}`；账户 `150,000`。
- A：当前官方 AI + 当前 C9/15w。
- C：A + 63 个日期对齐收益、同日批量感知、只消除正协方差额外风险的候选边际预算。
- 外部判断：Euler 风险贡献支持用候选与当前组合的协方差定义边际风险；Ledoit-Wolf 只负责协方差稳健性，真实裁决仍由本地真引擎完成。

## 全周期结果

{s006.base._md_table(summary_view)}

## 2022 与主压力窗

{s006.base._md_table(stress)}

## 边际风险语义审计

{s006.base._md_table(audit)}

## AI 同口径审计

{s006.base._md_table(ai_parity)}

## 决策

- 决策：`{decision['decision']}`
- 收益保留率：`{decision['return_retention_ratio']:.4f}`，门槛 `>= {RETURN_RETENTION_MIN:.2f}`。
- 全周期回撤变化：`{decision['full_drawdown_delta_pct']:.4f}`pp，门槛 `>= {FULL_DD_IMPROVEMENT_MIN_PP:.1f}`pp。
- 2022 年内回撤变化：`{decision['year_2022_drawdown_delta_pct']:.4f}`pp，门槛 `>= {YEAR_2022_DD_IMPROVEMENT_MIN_PP:.1f}`pp。
- 主压力窗回撤变化：`{decision['main_stress_drawdown_delta_pct']:.4f}`pp，门槛 `>= {STRESS_DD_IMPROVEMENT_MIN_PP:.1f}`pp。
- broker10 峰值变化：`{decision['broker10_peak_delta_pct']:.4f}`pp。
- semantics_ok：`{decision['semantics_ok']}`；performance_ok：`{decision['performance_ok']}`。
- 运行后过拟合判断：等待独立 agent review；不允许结果后救窗口、阈值或 floor。
- 运行后继续价值判断：等待独立 agent review。
"""
    REPORT_PATH.write_text(report, encoding="utf-8")

    stage_record = f"""# Stage001 日期对齐边际协方差风险预算 A/C 真引擎

- line_id：`{LINE_ID}`
- 当前模式：`day`
- 记录时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`
- 工作区/分支：当前共享工作区；研究目录隔离
- 阶段性质：最小 A/C 真引擎验证
- 是否重要突破：等待独立 review
- 是否触发A/B：是；A=当前 C9，C=A+日期对齐边际协方差风险预算

## 外部调研与判断

- 参考资料：Euler marginal risk contribution、Active Risk Budgeting、Ledoit-Wolf、pysystemtrade 组合构建。
- 我的判断：边际风险必须只看候选给现有组合增加的协方差风险；上一版绝对 inflation 不满足该语义。本阶段冻结一次，不扫参数。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/{Path(__file__).name}`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无。
- 新增参数：`63` 个日期对齐收益、Ledoit-Wolf、解析边际缩放、同日候选批量感知、至少 1 手。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：`{REQUESTED_START.date()} -> {REQUESTED_END.date()}`。
- 账户规模：`{CAPITAL:,.0f}`。
- 成本口径：当前 C9 真引擎滑点、手续费、broker10 保证金和下一真实开盘代理。
- 样本过滤：当前官方 AI 月池；A/C eligibility 归一化一致。
- 策略口径：正式 candidate planning 完成后缩手；不改退出、止损重试、换月、已有仓或加仓。

## 结果

- A：期末权益 `{a['end_equity']:,.2f}`；总收益 `{a['total_return_pct']:.4f}%`；最大回撤 `{a['max_drawdown_pct']:.4f}%`；Sharpe `{a['sharpe']:.4f}`；总滑点 `{a['total_slippage']:,.2f}`；总交易 `{a['total_trade_count']:,.0f}`；非零日胜率 `{a['nonzero_daily_win_rate_pct']:.4f}%`；逐笔胜率 `{a['closed_lot_win_rate_pct']:.4f}%`。
- C：期末权益 `{c['end_equity']:,.2f}`；总收益 `{c['total_return_pct']:.4f}%`；最大回撤 `{c['max_drawdown_pct']:.4f}%`；Sharpe `{c['sharpe']:.4f}`；总滑点 `{c['total_slippage']:,.2f}`；总交易 `{c['total_trade_count']:,.0f}`；非零日胜率 `{c['nonzero_daily_win_rate_pct']:.4f}%`；逐笔胜率 `{c['closed_lot_win_rate_pct']:.4f}%`。
- 收益保留：`{decision['return_retention_ratio']:.4f}`。
- 全周期/2022/主压力窗回撤变化：`{decision['full_drawdown_delta_pct']:.4f}` / `{decision['year_2022_drawdown_delta_pct']:.4f}` / `{decision['main_stress_drawdown_delta_pct']:.4f}`pp。
- broker10 峰值变化：`{decision['broker10_peak_delta_pct']:.4f}`pp。
- semantics_ok：`{decision['semantics_ok']}`；performance_ok：`{decision['performance_ok']}`。

## 输出文件

- report：`{REPORT_PATH}`
- summary：`{SUMMARY_PATH}`
- stress：`{STRESS_SUMMARY_PATH}`
- daily：`{A_DAILY_PATH}` / `{C_DAILY_PATH}`
- quality：`{MARGINAL_AUDIT_PATH}` / `{AI_PARITY_PATH}`
- chart：`{CHART_PATH}`

## 结论

- 本阶段结论：`{decision['decision']}`。
- 是否进入下一步：等待独立 agent review。
- 下一步：只有全部硬门槛通过且 review 无 P0/P1 才扩展逐半年；否则关闭本线。

## 过拟合反思

- 运行前判断：低到中等；一次冻结结构，不按 2022 品种/方向/日期调规则。
- 运行后判断：等待独立 review；无论结果如何不扫窗口、阈值、floor 或整数规则。
- 原因：2022 是预声明压力窗，不是拟合标签。

## 继续价值反思

- 运行前判断：有价值；直接修复上一版两个 P1，并针对组合相关风险而不删除 AI 机会。
- 运行后判断：等待独立 review。
- 原因：由 70% 收益保留、全周期/2022 回撤和语义审计共同决定。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：待独立 review 后统一更新。
- 是否追加根目录 `memory.md/back_log.md`：按 A/B 规范追加 `back_log.md`；不更新 `memory.md`。
"""
    STAGE_RECORD_PATH.write_text(stage_record, encoding="utf-8")

    line_marker = "## Stage001 结果"
    line_append = f"""

{line_marker}

- 时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`
- 决策：`{decision['decision']}`
- A：`{a['end_equity']:,.2f}` / `{a['total_return_pct']:.4f}%` / `{a['max_drawdown_pct']:.4f}%` / Sharpe `{a['sharpe']:.4f}`。
- C：`{c['end_equity']:,.2f}` / `{c['total_return_pct']:.4f}%` / `{c['max_drawdown_pct']:.4f}%` / Sharpe `{c['sharpe']:.4f}`。
- 收益保留：`{decision['return_retention_ratio']:.4f}`；全周期/2022/主压力窗回撤变化：`{decision['full_drawdown_delta_pct']:.4f}` / `{decision['year_2022_drawdown_delta_pct']:.4f}` / `{decision['main_stress_drawdown_delta_pct']:.4f}`pp；等待独立 review。
"""
    _append_once(LINE_DIR / "LINE.md", line_marker, line_append)

    back_marker = f"`{LINE_ID}` Stage001 完成日期对齐边际协方差风险预算"
    back_append = f"""

{datetime.now().strftime('%Y-%m-%d %H:%M CST')}：{back_marker} A/C 真引擎，决策 `{decision['decision']}`。新增脚本 `research/lines/{LINE_ID}/tools/{Path(__file__).name}`；新增参数 `63个日期对齐收益/Ledoit-Wolf/解析边际缩放/同日批量感知/至少1手`，修改参数无，删除参数无。A 期末权益 `{a['end_equity']:,.2f}`、总收益 `{a['total_return_pct']:.4f}%`、最大回撤 `{a['max_drawdown_pct']:.4f}%`、Sharpe `{a['sharpe']:.4f}`、总滑点 `{a['total_slippage']:,.2f}`、总交易 `{a['total_trade_count']:,.0f}`、非零日胜率 `{a['nonzero_daily_win_rate_pct']:.4f}%`、逐笔胜率 `{a['closed_lot_win_rate_pct']:.4f}%`；C 期末权益 `{c['end_equity']:,.2f}`、总收益 `{c['total_return_pct']:.4f}%`、最大回撤 `{c['max_drawdown_pct']:.4f}%`、Sharpe `{c['sharpe']:.4f}`、总滑点 `{c['total_slippage']:,.2f}`、总交易 `{c['total_trade_count']:,.0f}`、非零日胜率 `{c['nonzero_daily_win_rate_pct']:.4f}%`、逐笔胜率 `{c['closed_lot_win_rate_pct']:.4f}%`。新增结果：收益保留 `{decision['return_retention_ratio']:.4f}`，全周期/2022/主压力窗回撤变化 `{decision['full_drawdown_delta_pct']:.4f}/{decision['year_2022_drawdown_delta_pct']:.4f}/{decision['main_stress_drawdown_delta_pct']:.4f}`pp，broker10 峰值变化 `{decision['broker10_peak_delta_pct']:.4f}`pp，semantics_ok `{decision['semantics_ok']}`，performance_ok `{decision['performance_ok']}`；修改/删除回测结果无。运行前过拟合判断：低到中等，一次冻结且不按 2022 品种/方向/日期调参；运行后过拟合判断：待独立 review，不允许救窗口/阈值/floor。运行前继续价值判断：有；运行后继续价值判断：待独立 review。report `{REPORT_PATH}`，summary `{SUMMARY_PATH}`。
"""
    _append_once(ROOT / "back_log.md", back_marker, back_append)


def build() -> dict[str, pd.DataFrame]:
    OUT.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)

    a_eligibility = s006._official_eligibility_for_strategy(A_STRATEGY, A_SCORE_TYPE)
    c_eligibility = s006._official_eligibility_for_strategy(C_STRATEGY, C_SCORE_TYPE)
    a_eligibility.to_csv(A_ELIGIBILITY_PATH, index=False, encoding="utf-8-sig")
    c_eligibility.to_csv(C_ELIGIBILITY_PATH, index=False, encoding="utf-8-sig")
    ai_parity = pd.DataFrame(
        [
            {
                "official_ai_path": str(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH),
                "official_ai_sha16": _sha16(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH),
                "a_file_sha16": _sha16(A_ELIGIBILITY_PATH),
                "c_file_sha16": _sha16(C_ELIGIBILITY_PATH),
                "a_normalized_sha16": _normalized_ai_hash(a_eligibility),
                "c_normalized_sha16": _normalized_ai_hash(c_eligibility),
                "normalized_equal": int(_normalized_ai_hash(a_eligibility) == _normalized_ai_hash(c_eligibility)),
                "a_rows": int(len(a_eligibility)),
                "c_rows": int(len(c_eligibility)),
            }
        ]
    )

    metadata = _metadata()
    a_profile = _profile(
        metadata,
        version=A_VERSION,
        strategy_name=A_STRATEGY,
        eligibility_path=A_ELIGIBILITY_PATH,
        label="A current official AI C9 control",
        candidate=False,
    )
    c_profile = _profile(
        metadata,
        version=C_VERSION,
        strategy_name=C_STRATEGY,
        eligibility_path=C_ELIGIBILITY_PATH,
        label="C current official AI C9 plus dated marginal covariance budget",
        candidate=True,
    )

    a_daily, a_frames = _run(metadata, a_profile, A_VERSION)
    c_daily, c_frames = _run(metadata, c_profile, C_VERSION)
    a_closed = _closed_lots(a_frames, metadata)
    c_closed = _closed_lots(c_frames, metadata)

    a_daily.to_csv(A_DAILY_PATH, index=False, encoding="utf-8-sig")
    c_daily.to_csv(C_DAILY_PATH, index=False, encoding="utf-8-sig")
    _save_frames(
        a_frames,
        {
            "entry_candidates": A_ENTRY_PATH,
            "entry_risk": A_RISK_PATH,
            "trades": A_TRADES_PATH,
            "trade_events": A_TRADE_EVENTS_PATH,
            "stop_retry_events": A_STOP_RETRY_PATH,
        },
    )
    _save_frames(
        c_frames,
        {
            "entry_candidates": C_ENTRY_PATH,
            "entry_risk": C_RISK_PATH,
            "trades": C_TRADES_PATH,
            "trade_events": C_TRADE_EVENTS_PATH,
            "stop_retry_events": C_STOP_RETRY_PATH,
        },
    )
    if not a_closed.empty:
        a_closed.to_csv(A_CLOSED_PATH, index=False, encoding="utf-8-sig")
    if not c_closed.empty:
        c_closed.to_csv(C_CLOSED_PATH, index=False, encoding="utf-8-sig")

    a_curve = s006.base._curve_for_metrics(a_daily, A_VERSION)
    c_curve = s006.base._curve_for_metrics(c_daily, C_VERSION)
    curves = pd.concat([a_curve, c_curve], ignore_index=True, sort=False)
    curves["stage"] = STAGE_LABEL
    curves["model_tag"] = MODEL_TAG
    curves["line_id"] = LINE_ID
    summary = pd.DataFrame([_summary_row(a_curve, a_closed), _summary_row(c_curve, c_closed)])
    stress = _stress_summary({A_VERSION: a_daily, C_VERSION: c_daily})
    c_entries = c_frames.get("entry_candidates", pd.DataFrame()).copy()
    audit = _marginal_audit(c_entries)
    ai_usage = s006._ai_usage_audit({A_VERSION: a_frames, C_VERSION: c_frames})
    decision = _decision(summary, stress, audit, ai_parity)

    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    stress.to_csv(STRESS_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    audit.to_csv(MARGINAL_AUDIT_PATH, index=False, encoding="utf-8-sig")
    ai_parity.to_csv(AI_PARITY_PATH, index=False, encoding="utf-8-sig")
    ai_usage.to_csv(AI_USAGE_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(s006.base._json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _plot(curves)
    _write_records(summary, stress, audit, ai_parity, decision)
    return {
        "summary": summary,
        "stress": stress,
        "audit": audit,
        "ai_parity": ai_parity,
        "ai_usage": ai_usage,
        "curves": curves,
    }


def main() -> None:
    outputs = build()
    print(outputs["summary"].to_string(index=False))
    print(outputs["stress"].to_string(index=False))
    print(outputs["audit"].to_string(index=False))
    print(outputs["ai_parity"].to_string(index=False))
    print(f"report={REPORT_PATH}")
    print(f"chart={CHART_PATH}")


if __name__ == "__main__":
    main()
