#!/usr/bin/env python3
"""Stage006: frozen Stage013 gate using reconciled account equity."""

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
import pandas as pd
from vnpy.trader.constant import Direction


ROOT = Path(__file__).resolve().parents[4]
TOOLS_DIR = Path(__file__).resolve().parent
PORTFOLIO_DIR = ROOT / "examples" / "portfolio_backtesting"
for item in (TOOLS_DIR, PORTFOLIO_DIR):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import stage001_stage013_current_ai_engine as stage001  # noqa: E402
from qmt_roll_official_live_config import OFFICIAL_LIVE_AI_ELIGIBILITY_PATH  # noqa: E402


LINE_ID = "futures_trend_stage013_current_ai_revalidation"
STAGE_ID = "stage006_stage013_reconciled_equity_engine"
STAGE_LABEL = "Stage006"
MODEL_TAG = f"{STAGE_ID}_v1"
OUTPUT_PREFIX = f"stage013_current_ai_{STAGE_ID}"

A_VERSION = stage001.A_VERSION
C_VERSION = "c_current_ai_stage013_reconciled_equity"
A_STRATEGY = stage001.A_STRATEGY
C_STRATEGY = "stage006_stage013_reconciled_equity"
VERSIONS = (A_VERSION, C_VERSION)

RETURN_RETENTION_MIN = stage001.RETURN_RETENTION_MIN
FULL_DD_IMPROVEMENT_MIN_PP = stage001.FULL_DD_IMPROVEMENT_MIN_PP
YEAR_2022_DD_IMPROVEMENT_MIN_PP = stage001.YEAR_2022_DD_IMPROVEMENT_MIN_PP
STRESS_DD_IMPROVEMENT_MIN_PP = stage001.STRESS_DD_IMPROVEMENT_MIN_PP
RECONCILIATION_TOLERANCE = 1e-8

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / STAGE_ID
SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
STRESS_PATH = OUT / f"{OUTPUT_PREFIX}_stress_{MODEL_TAG}.csv"
CURVES_PATH = OUT / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv.gz"
RECONCILIATION_PATH = OUT / f"{OUTPUT_PREFIX}_equity_reconciliation_{MODEL_TAG}.csv"
PILOT_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_pilot_audit_{MODEL_TAG}.csv"
AI_PARITY_PATH = OUT / f"{OUTPUT_PREFIX}_ai_parity_{MODEL_TAG}.csv"
AI_USAGE_PATH = OUT / f"{OUTPUT_PREFIX}_ai_usage_{MODEL_TAG}.csv"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
LINEAGE_PATH = OUT / f"{OUTPUT_PREFIX}_lineage_{MODEL_TAG}.json"
MANIFEST_PATH = OUT / f"{OUTPUT_PREFIX}_manifest_{MODEL_TAG}.csv"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUT / f"{OUTPUT_PREFIX}_equity_drawdown_stress_{MODEL_TAG}.png"

DAILY_REASON = "stage006_authoritative_equity_daily"
CORRECTION_REASON = "stage006_trade_duplicate_equity_correction"
SAVE_FRAME_NAMES = (
    "entry_candidates",
    "entry_risk",
    "trades",
    "positions",
    "trade_events",
    "intraday_events",
    "c2_events",
    "stop_retry_events",
    "pending_orders",
    "pilot_gate_events",
    "stage006_equity_daily",
    "stage006_trade_corrections",
)


def _close_to_close_duplicate_pnl(
    *,
    signed_volume: float,
    previous_close: float,
    current_close: float,
    contract_size: float,
) -> float:
    return (
        float(signed_volume)
        * (float(current_close) - float(previous_close))
        * float(contract_size)
    )


def _reconciled_equity_from_legacy(
    legacy_equity: float, cumulative_duplicate_pnl: float
) -> float:
    return float(legacy_equity) - float(cumulative_duplicate_pnl)


class QmtRollPortfolioStrategyStage006ReconciledEquity(
    stage001.stage013.QmtRollPortfolioStrategyStage013AccountStatePilotGate
):
    variables = (
        stage001.stage013.QmtRollPortfolioStrategyStage013AccountStatePilotGate.variables
        + [
            "stage006_authoritative_equity",
            "stage006_authoritative_high_water",
            "stage006_authoritative_drawdown_pct",
            "stage006_cumulative_duplicate_pnl",
        ]
    )

    def __init__(
        self,
        strategy_engine: Any,
        strategy_name: str,
        vt_symbols: list[str],
        setting: dict[str, Any],
    ) -> None:
        self.stage006_cumulative_duplicate_pnl = 0.0
        self.stage006_future_trade_violation_count = 0
        self.stage006_duplicate_date_count = 0
        self.stage006_processed_dates: set[str] = set()
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)
        self.stage006_authoritative_equity = float(self.base_capital)
        self.stage006_authoritative_high_water = float(self.base_capital)
        self.stage006_authoritative_drawdown_pct = 0.0
        self.stage006_legacy_equity_at_close = float(self.base_capital)

    @staticmethod
    def _normalized_date(value: Any) -> pd.Timestamp:
        result = pd.Timestamp(value)
        if result.tzinfo is not None:
            result = result.tz_localize(None)
        return result.normalize()

    def update_trade(self, trade: Any) -> None:
        engine_bars = getattr(self.strategy_engine, "bars", {}) or {}
        bar = engine_bars.get(str(trade.vt_symbol))
        current_close = float(
            getattr(bar, "close_price", 0.0) or getattr(trade, "price", 0.0) or 0.0
        )
        previous_close = float(
            self.last_close_prices.get(str(trade.vt_symbol), current_close)
        )
        contract_size = float(self.get_size(str(trade.vt_symbol)))
        signed_volume = (
            float(trade.volume)
            if trade.direction == Direction.LONG
            else -float(trade.volume)
        )
        duplicate_pnl = _close_to_close_duplicate_pnl(
            signed_volume=signed_volume,
            previous_close=previous_close,
            current_close=current_close,
            contract_size=contract_size,
        )
        engine_datetime = getattr(self.strategy_engine, "datetime", trade.datetime)
        future_violation = int(
            self._normalized_date(trade.datetime)
            > self._normalized_date(engine_datetime)
        )

        super().update_trade(trade)

        self.stage006_cumulative_duplicate_pnl += duplicate_pnl
        self.stage006_future_trade_violation_count += future_violation
        self.trade_event_diagnostics.append(
            {
                "datetime": trade.datetime,
                "date": self._normalized_date(trade.datetime).date(),
                "vt_symbol": str(trade.vt_symbol),
                "product_vt_symbol": str(
                    self.source_symbol_by_contract.get(str(trade.vt_symbol), "")
                ),
                "direction": str(getattr(trade.direction, "value", trade.direction)),
                "offset": "Audit",
                "reason": CORRECTION_REASON,
                "volume": float(trade.volume),
                "price": float(trade.price),
                "stage006_trade_id": str(getattr(trade, "vt_tradeid", "")),
                "stage006_signed_volume": signed_volume,
                "stage006_previous_close": previous_close,
                "stage006_current_close": current_close,
                "stage006_contract_size": contract_size,
                "stage006_duplicate_pnl": duplicate_pnl,
                "stage006_cumulative_duplicate_pnl": self.stage006_cumulative_duplicate_pnl,
                "stage006_future_trade_violation": future_violation,
            }
        )

    def _stage006_refresh_authoritative_equity(
        self, bars: dict[str, Any]
    ) -> None:
        if not bars:
            return
        first_bar = next(iter(bars.values()))
        current_date = self._normalized_date(first_bar.datetime)
        date_text = current_date.date().isoformat()
        if date_text in self.stage006_processed_dates:
            self.stage006_duplicate_date_count += 1
            raise RuntimeError(f"duplicate Stage006 equity date: {date_text}")
        self.stage006_processed_dates.add(date_text)

        engine_bars = dict(getattr(self.strategy_engine, "bars", {}) or bars)
        legacy_equity = float(self._estimate_equity(engine_bars))
        authoritative_equity = _reconciled_equity_from_legacy(
            legacy_equity, self.stage006_cumulative_duplicate_pnl
        )
        self.stage006_legacy_equity_at_close = legacy_equity
        self.stage006_authoritative_equity = authoritative_equity
        self.stage006_authoritative_high_water = max(
            float(self.base_capital),
            float(self.stage006_authoritative_high_water),
            authoritative_equity,
        )
        if self.stage006_authoritative_high_water > 0.0:
            self.stage006_authoritative_drawdown_pct = max(
                0.0,
                (
                    self.stage006_authoritative_high_water - authoritative_equity
                )
                / self.stage006_authoritative_high_water,
            )
        else:
            self.stage006_authoritative_drawdown_pct = 0.0
        self.trade_event_diagnostics.append(
            {
                "datetime": first_bar.datetime,
                "date": current_date.date(),
                "vt_symbol": "",
                "product_vt_symbol": "",
                "direction": "",
                "offset": "Audit",
                "reason": DAILY_REASON,
                "volume": 0,
                "price": 0.0,
                "stage006_legacy_equity": legacy_equity,
                "stage006_cumulative_duplicate_pnl": self.stage006_cumulative_duplicate_pnl,
                "stage006_authoritative_equity": authoritative_equity,
                "stage006_authoritative_high_water": self.stage006_authoritative_high_water,
                "stage006_authoritative_drawdown_pct": self.stage006_authoritative_drawdown_pct,
                "stage006_future_trade_violation_count": self.stage006_future_trade_violation_count,
                "stage006_duplicate_date_count": self.stage006_duplicate_date_count,
            }
        )

    def on_bars(self, bars: dict[str, Any]) -> None:
        self._stage006_refresh_authoritative_equity(bars)
        super().on_bars(bars)

    def _plan_flat_entry_candidates(
        self, day_contexts: list[Any]
    ) -> dict[str, dict[str, Any]]:
        base_class = (
            stage001.stage013.s847.QmtRollPortfolioStrategyStage847C9StopRetry
        )
        plans = base_class._plan_flat_entry_candidates(self, day_contexts)
        if not self.enable_stage013_account_state_pilot_gate:
            return plans

        for product_vt_symbol, plan in plans.items():
            if str(plan.get("candidate_status") or "") != "opened":
                continue
            sizing = dict(plan.get("sizing") or {})
            legacy_drawdown = stage001.stage013._normalize_drawdown_ratio(
                sizing.get("portfolio_drawdown_pct", 0.0)
            )
            gate_sizing = dict(sizing)
            gate_sizing["portfolio_drawdown_pct"] = float(
                self.stage006_authoritative_drawdown_pct
            )
            selected_after, fields = (
                stage001.stage013._stage013_apply_account_state_pilot_gate(
                    sizing=gate_sizing,
                    entry_context="flat_entry",
                    active_positions_before=int(
                        plan.get("active_positions_before") or 0
                    ),
                    min_position_size=int(
                        getattr(self, "min_position_size", 1) or 1
                    ),
                    enabled=bool(self.enable_stage013_account_state_pilot_gate),
                    drawdown_trigger_pct=float(
                        self.stage013_pilot_drawdown_trigger_pct
                    ),
                    active_positions_max=int(
                        self.stage013_pilot_active_positions_max
                    ),
                    pilot_min_volume=int(self.stage013_pilot_min_volume),
                )
            )
            fields.update(
                {
                    "stage006_authoritative_equity": float(
                        self.stage006_authoritative_equity
                    ),
                    "stage006_authoritative_high_water": float(
                        self.stage006_authoritative_high_water
                    ),
                    "stage006_authoritative_drawdown_pct": float(
                        self.stage006_authoritative_drawdown_pct
                    ),
                    "stage006_legacy_equity": float(
                        self.stage006_legacy_equity_at_close
                    ),
                    "stage006_legacy_drawdown_pct": float(legacy_drawdown),
                    "stage006_cumulative_duplicate_pnl": float(
                        self.stage006_cumulative_duplicate_pnl
                    ),
                }
            )
            sizing.update(fields)
            if int(fields["stage013_pilot_gate_applied"]) != 1:
                plan["sizing"] = sizing
                continue

            sizing["selected_volume"] = selected_after
            plan["sizing"] = sizing
            plan["volume"] = selected_after
            if selected_after <= 0:
                plan["candidate_status"] = "skipped"
                plan["skip_reason"] = "stage013_account_state_pilot_gate_zero"

            event = self._stage013_event_from_plan(
                str(product_vt_symbol), plan, fields
            )
            self.stage013_pilot_gate_events.append(event)
            self.trade_event_diagnostics.append(event)
            self.stage013_pilot_gate_count += 1
            self.stage013_pilot_gate_reduced_volume += int(
                fields["stage013_pilot_gate_reduced_volume"]
            )
        return plans


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _mapping_hash(values: dict[str, Any]) -> str:
    payload = json.dumps(
        {str(key): values[key] for key in sorted(values)},
        ensure_ascii=True,
        default=str,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def _eligibility(
    strategy_name: str, score_type: str, version: str
) -> tuple[pd.DataFrame, Path]:
    frame = stage001.source.s006._official_eligibility_for_strategy(
        strategy_name, score_type
    )
    path = OUT / f"{OUTPUT_PREFIX}_{version}_eligibility_{MODEL_TAG}.csv"
    frame.to_csv(path, index=False, encoding="utf-8-sig")
    return frame, path


def _candidate_profile(
    metadata: dict[str, Any], eligibility_path: Path
) -> dict[str, Any]:
    profile = stage001._c_profile(metadata, eligibility_path)
    spec = profile["spec"]
    capital = replace(
        spec.capital,
        variant=C_VERSION,
        label="C current AI Stage013 reconciled equity",
    )
    overrides = {
        **spec.overrides,
        "ai_product_pool_strategy": C_STRATEGY,
    }
    result = dict(profile)
    result["profile"] = C_VERSION
    result["strategy_cls"] = QmtRollPortfolioStrategyStage006ReconciledEquity
    result["spec"] = replace(
        spec,
        capital=capital,
        overrides=overrides,
        profile=C_VERSION,
    )
    return result


def _run(
    metadata: dict[str, Any], profile: dict[str, Any], version: str
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    daily, frames = stage001._run(metadata, profile, version)
    daily = daily.copy()
    daily["stage"] = STAGE_LABEL
    daily["model_tag"] = MODEL_TAG
    daily["line_id"] = LINE_ID
    trade_events = frames.get("trade_events", pd.DataFrame()).copy()
    if version == C_VERSION and not trade_events.empty:
        reason = trade_events.get("reason", pd.Series(dtype=str)).astype(str)
        frames["stage006_equity_daily"] = trade_events[reason.eq(DAILY_REASON)].copy()
        frames["stage006_trade_corrections"] = trade_events[
            reason.eq(CORRECTION_REASON)
        ].copy()
        frames["pilot_gate_events"] = trade_events[
            reason.eq("stage013_account_state_pilot_gate")
        ].copy()
    else:
        frames["stage006_equity_daily"] = pd.DataFrame()
        frames["stage006_trade_corrections"] = pd.DataFrame()
        frames["pilot_gate_events"] = pd.DataFrame()
    for name, frame in list(frames.items()):
        frame = frame.copy()
        if not frame.empty:
            frame["stage"] = STAGE_LABEL
            frame["model_tag"] = MODEL_TAG
            frame["line_id"] = LINE_ID
        frames[name] = frame
    return daily, frames


def _save_arm(
    version: str,
    daily: pd.DataFrame,
    frames: dict[str, pd.DataFrame],
    closed: pd.DataFrame,
) -> None:
    prefix = f"{OUTPUT_PREFIX}_{version}"
    daily.to_csv(
        OUT / f"{prefix}_daily_{MODEL_TAG}.csv.gz",
        index=False,
        encoding="utf-8-sig",
    )
    if not closed.empty:
        closed.to_csv(
            OUT / f"{prefix}_closed_lots_{MODEL_TAG}.csv.gz",
            index=False,
            encoding="utf-8-sig",
        )
    for name in SAVE_FRAME_NAMES:
        frame = frames.get(name, pd.DataFrame())
        if frame.empty:
            continue
        frame.to_csv(
            OUT / f"{prefix}_{name}_{MODEL_TAG}.csv.gz",
            index=False,
            encoding="utf-8-sig",
        )


def _summary_row(
    version: str,
    daily: pd.DataFrame,
    frames: dict[str, pd.DataFrame],
    metadata: dict[str, Any],
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    closed = stage001.source._closed_lots(frames, metadata)
    curve = stage001.source.s006.base._curve_for_metrics(daily, version)
    row = stage001.source.s006._summarize_curve(curve)
    realized = pd.to_numeric(
        closed.get("realized_pnl", pd.Series(dtype=float)), errors="coerce"
    ).dropna()
    row.update(
        {
            "stage": STAGE_LABEL,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "closed_lot_count": int(len(realized)),
            "closed_lot_win_rate_pct": (
                float((realized > 0.0).mean() * 100.0) if len(realized) else 0.0
            ),
        }
    )
    curve["stage"] = STAGE_LABEL
    curve["model_tag"] = MODEL_TAG
    curve["line_id"] = LINE_ID
    return row, curve, closed


def _daily_equity_frame(daily: pd.DataFrame) -> pd.DataFrame:
    result = daily[["date", "account_equity"]].copy()
    result["date"] = pd.to_datetime(result["date"], errors="coerce").dt.normalize()
    result["official_equity"] = pd.to_numeric(
        result.pop("account_equity"), errors="coerce"
    )
    result = result.dropna(subset=["date", "official_equity"]).sort_values("date")
    result["official_high_water"] = result["official_equity"].cummax()
    result["official_drawdown_pct"] = (
        1.0 - result["official_equity"] / result["official_high_water"]
    )
    return result


def _equity_reconciliation(
    daily: pd.DataFrame, frames: dict[str, pd.DataFrame]
) -> pd.DataFrame:
    official = _daily_equity_frame(daily)
    audit = frames.get("stage006_equity_daily", pd.DataFrame()).copy()
    corrections = frames.get("stage006_trade_corrections", pd.DataFrame()).copy()
    if audit.empty:
        return pd.DataFrame(
            [
                {
                    "sample": "all",
                    "official_rows": int(len(official)),
                    "audit_rows": 0,
                    "raw_audit_rows": 0,
                    "pre_start_audit_count": 0,
                    "pre_start_invalid_count": 0,
                    "in_range_extra_audit_count": 0,
                    "post_end_audit_count": 0,
                    "missing_date_count": int(len(official)),
                    "duplicate_date_count": 0,
                    "max_equity_abs_diff": float("inf"),
                    "max_high_water_abs_diff": float("inf"),
                    "max_drawdown_abs_diff": float("inf"),
                    "correction_sum_abs_diff": float("inf"),
                    "future_trade_violation_count": 0,
                    "reconciliation_pass": False,
                }
            ]
        )
    audit["date"] = pd.to_datetime(audit["date"], errors="coerce").dt.normalize()
    raw_audit_rows = int(len(audit))
    official_start = pd.Timestamp(official["date"].min())
    official_end = pd.Timestamp(official["date"].max())
    official_dates = set(official["date"])
    pre_start = audit[audit["date"] < official_start].copy()
    post_end = audit[audit["date"] > official_end].copy()
    in_range_extra = audit[
        audit["date"].between(official_start, official_end)
        & ~audit["date"].isin(official_dates)
    ].copy()
    if pre_start.empty:
        pre_start_invalid = 0
    else:
        pre_equity = pd.to_numeric(
            pre_start["stage006_authoritative_equity"], errors="coerce"
        )
        pre_drawdown = pd.to_numeric(
            pre_start["stage006_authoritative_drawdown_pct"], errors="coerce"
        )
        pre_correction = pd.to_numeric(
            pre_start["stage006_cumulative_duplicate_pnl"], errors="coerce"
        )
        pre_start_invalid = int(
            (
                (pre_equity - float(stage001.CAPITAL)).abs()
                > RECONCILIATION_TOLERANCE
            ).sum()
            + (pre_drawdown.abs() > RECONCILIATION_TOLERANCE).sum()
            + (pre_correction.abs() > RECONCILIATION_TOLERANCE).sum()
        )
    audit = audit[audit["date"].isin(official_dates)].copy()
    duplicate_dates = int(audit["date"].duplicated(keep=False).sum())
    merged = official.merge(audit, on="date", how="outer", indicator=True)
    missing_dates = int(merged["_merge"].ne("both").sum())
    equity_diff = (
        pd.to_numeric(merged["official_equity"], errors="coerce")
        - pd.to_numeric(merged["stage006_authoritative_equity"], errors="coerce")
    ).abs()
    high_water_diff = (
        pd.to_numeric(merged["official_high_water"], errors="coerce")
        - pd.to_numeric(
            merged["stage006_authoritative_high_water"], errors="coerce"
        )
    ).abs()
    drawdown_diff = (
        pd.to_numeric(merged["official_drawdown_pct"], errors="coerce")
        - pd.to_numeric(
            merged["stage006_authoritative_drawdown_pct"], errors="coerce"
        )
    ).abs()
    correction_sum = float(
        pd.to_numeric(
            corrections.get("stage006_duplicate_pnl", pd.Series(dtype=float)),
            errors="coerce",
        ).sum()
    )
    final_correction = float(
        pd.to_numeric(
            audit["stage006_cumulative_duplicate_pnl"], errors="coerce"
        ).iloc[-1]
    )
    correction_diff = abs(correction_sum - final_correction)
    future_violations = int(
        pd.to_numeric(
            corrections.get(
                "stage006_future_trade_violation", pd.Series(dtype=float)
            ),
            errors="coerce",
        )
        .fillna(0)
        .sum()
    )
    max_equity = float(equity_diff.max()) if equity_diff.notna().any() else float("inf")
    max_hwm = (
        float(high_water_diff.max())
        if high_water_diff.notna().any()
        else float("inf")
    )
    max_dd = (
        float(drawdown_diff.max())
        if drawdown_diff.notna().any()
        else float("inf")
    )
    passed = (
        len(audit) == len(official)
        and missing_dates == 0
        and duplicate_dates == 0
        and pre_start_invalid == 0
        and len(in_range_extra) == 0
        and len(post_end) == 0
        and max_equity <= RECONCILIATION_TOLERANCE
        and max_hwm <= RECONCILIATION_TOLERANCE
        and max_dd <= RECONCILIATION_TOLERANCE
        and correction_diff <= RECONCILIATION_TOLERANCE
        and future_violations == 0
    )
    return pd.DataFrame(
        [
            {
                "sample": "all",
                "official_rows": int(len(official)),
                "audit_rows": int(len(audit)),
                "raw_audit_rows": raw_audit_rows,
                "pre_start_audit_count": int(len(pre_start)),
                "pre_start_invalid_count": pre_start_invalid,
                "in_range_extra_audit_count": int(len(in_range_extra)),
                "post_end_audit_count": int(len(post_end)),
                "missing_date_count": missing_dates,
                "duplicate_date_count": duplicate_dates,
                "max_equity_abs_diff": max_equity,
                "max_high_water_abs_diff": max_hwm,
                "max_drawdown_abs_diff": max_dd,
                "trade_correction_rows": int(len(corrections)),
                "trade_correction_sum": correction_sum,
                "final_cumulative_correction": final_correction,
                "correction_sum_abs_diff": correction_diff,
                "future_trade_violation_count": future_violations,
                "reconciliation_pass": bool(passed),
            }
        ]
    )


def _pilot_audit(
    daily: pd.DataFrame, frames: dict[str, pd.DataFrame]
) -> pd.DataFrame:
    official = _daily_equity_frame(daily)
    events = frames.get("pilot_gate_events", pd.DataFrame()).copy()
    if events.empty:
        return pd.DataFrame(
            [
                {
                    "sample": "all",
                    "rows": 0,
                    "official_dd_below_trigger_count": 0,
                    "authoritative_dd_below_trigger_count": 0,
                    "non_flat_entry_count": 0,
                    "not_applied_count": 0,
                    "wrong_reason_count": 0,
                    "not_opened_count": 0,
                    "after_not_one_count": 0,
                    "above_active_limit_count": 0,
                    "event_equity_mismatch_count": 0,
                }
            ]
        )
    events["date"] = pd.to_datetime(events["date"], errors="coerce").dt.normalize()
    events = events.merge(official, on="date", how="left")
    numeric_columns = (
        "stage013_pilot_gate_selected_volume_before",
        "stage013_pilot_gate_selected_volume_after",
        "stage013_pilot_gate_reduced_volume",
        "stage013_pilot_gate_drawdown_pct",
        "stage013_pilot_gate_drawdown_trigger_pct",
        "stage013_pilot_gate_active_positions_before",
        "stage013_pilot_gate_active_positions_max",
        "stage013_pilot_gate_applied",
        "stage006_authoritative_equity",
        "stage006_authoritative_drawdown_pct",
    )
    for column in numeric_columns:
        events[column] = pd.to_numeric(events[column], errors="coerce")
    rows = []
    samples = [("all", pd.Series(True, index=events.index))]
    samples.extend(
        (
            str(year),
            events["date"].dt.year.eq(year),
        )
        for year in sorted(events["date"].dt.year.dropna().unique())
    )
    for sample, mask in samples:
        part = events[mask].copy()
        trigger = part["stage013_pilot_gate_drawdown_trigger_pct"]
        equity_diff = (
            part["stage006_authoritative_equity"] - part["official_equity"]
        ).abs()
        rows.append(
            {
                "sample": sample,
                "rows": int(len(part)),
                "reduced_volume_sum": float(
                    part["stage013_pilot_gate_reduced_volume"].sum()
                ),
                "official_dd_min": float(part["official_drawdown_pct"].min()),
                "official_dd_max": float(part["official_drawdown_pct"].max()),
                "authoritative_dd_min": float(
                    part["stage006_authoritative_drawdown_pct"].min()
                ),
                "official_dd_below_trigger_count": int(
                    (part["official_drawdown_pct"] < trigger - 1e-12).sum()
                ),
                "authoritative_dd_below_trigger_count": int(
                    (
                        part["stage006_authoritative_drawdown_pct"]
                        < trigger - 1e-12
                    ).sum()
                ),
                "non_flat_entry_count": int(
                    part["entry_context"].astype(str).ne("flat_entry").sum()
                ),
                "not_applied_count": int(
                    part["stage013_pilot_gate_applied"].ne(1).sum()
                ),
                "wrong_reason_count": int(
                    part["stage013_pilot_gate_reason"]
                    .astype(str)
                    .ne("stage013_deep_drawdown_low_active_flat_entry_pilot")
                    .sum()
                ),
                "not_opened_count": int(
                    part["candidate_status_after"].astype(str).ne("opened").sum()
                ),
                "after_not_one_count": int(
                    part["stage013_pilot_gate_selected_volume_after"].ne(1).sum()
                ),
                "above_active_limit_count": int(
                    (
                        part["stage013_pilot_gate_active_positions_before"]
                        > part["stage013_pilot_gate_active_positions_max"]
                    ).sum()
                ),
                "event_equity_mismatch_count": int(
                    (equity_diff > RECONCILIATION_TOLERANCE).sum()
                ),
            }
        )
    return pd.DataFrame(rows)


def _metric(frame: pd.DataFrame, version: str) -> dict[str, Any]:
    return frame[frame["version"].eq(version)].iloc[0].to_dict()


def _window(frame: pd.DataFrame, version: str, window: str) -> dict[str, Any]:
    return frame[
        frame["version"].eq(version) & frame["window"].eq(window)
    ].iloc[0].to_dict()


def _decision(
    summary: pd.DataFrame,
    stress: pd.DataFrame,
    reconciliation: pd.DataFrame,
    pilot: pd.DataFrame,
    ai_parity: pd.DataFrame,
) -> dict[str, Any]:
    a = _metric(summary, A_VERSION)
    c = _metric(summary, C_VERSION)
    a22 = _window(stress, A_VERSION, "year_2022")
    c22 = _window(stress, C_VERSION, "year_2022")
    ast = _window(stress, A_VERSION, "main_2022_2024_stress")
    cst = _window(stress, C_VERSION, "main_2022_2024_stress")
    retention = float(c["total_return_pct"] / a["total_return_pct"])
    full_dd = float(c["max_drawdown_pct"] - a["max_drawdown_pct"])
    year_dd = float(
        c22["window_max_drawdown_pct"] - a22["window_max_drawdown_pct"]
    )
    stress_dd = float(
        cst["window_max_drawdown_pct"] - ast["window_max_drawdown_pct"]
    )
    broker_delta = float(
        c["max_broker10_margin_to_equity_pct"]
        - a["max_broker10_margin_to_equity_pct"]
    )
    all_pilot = pilot[pilot["sample"].astype(str).eq("all")].iloc[0]
    pilot_semantics_ok = bool(
        int(all_pilot["rows"]) > 0
        and all(
            int(all_pilot[column]) == 0
            for column in (
                "official_dd_below_trigger_count",
                "authoritative_dd_below_trigger_count",
                "non_flat_entry_count",
                "not_applied_count",
                "wrong_reason_count",
                "not_opened_count",
                "after_not_one_count",
                "above_active_limit_count",
                "event_equity_mismatch_count",
            )
        )
    )
    reconciliation_ok = bool(reconciliation["reconciliation_pass"].all())
    ai_ok = bool(ai_parity["all_normalized_equal"].all())
    semantics_ok = reconciliation_ok and pilot_semantics_ok and ai_ok
    performance_ok = bool(
        float(c["total_return_pct"]) > 0.0
        and retention >= RETURN_RETENTION_MIN
        and full_dd >= FULL_DD_IMPROVEMENT_MIN_PP
        and year_dd >= YEAR_2022_DD_IMPROVEMENT_MIN_PP
        and stress_dd >= STRESS_DD_IMPROVEMENT_MIN_PP
        and broker_delta <= 1e-9
    )
    return {
        "stage": STAGE_LABEL,
        "stage_id": STAGE_ID,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S CST"),
        "a_control": a,
        "c_candidate": c,
        "return_retention_ratio": retention,
        "full_drawdown_improvement_pct": full_dd,
        "year_2022_drawdown_improvement_pct": year_dd,
        "main_stress_drawdown_improvement_pct": stress_dd,
        "broker10_peak_delta_pct": broker_delta,
        "reconciliation_ok": reconciliation_ok,
        "pilot_semantics_ok": pilot_semantics_ok,
        "ai_parity_ok": ai_ok,
        "semantics_ok": semantics_ok,
        "performance_ok": performance_ok,
        "decision": (
            "stage006_continue_halfyear_if_independent_review_passes"
            if semantics_ok and performance_ok
            else "stage006_close_no_parameter_rescue"
        ),
        "overfit_before": "no: accounting identity repair without parameter search",
        "overfit_after": "pending_independent_review",
        "continue_value_before": "yes: restore Stage013 account-state semantics",
        "continue_value_after": "pending_independent_review",
    }


def _plot(curves: pd.DataFrame) -> None:
    labels = {A_VERSION: "A current C9", C_VERSION: "C reconciled Stage013"}
    colors = {A_VERSION: "#111827", C_VERSION: "#0f766e"}
    fig, axes = plt.subplots(2, 2, figsize=(16, 9))
    for version in VERSIONS:
        group = curves[curves["version"].eq(version)].sort_values("date").copy()
        dates = pd.to_datetime(group["date"], errors="coerce")
        equity = pd.to_numeric(
            group["account_equity_for_metrics"], errors="coerce"
        ).ffill()
        axes[0, 0].plot(
            dates, equity, label=labels[version], color=colors[version], linewidth=1.0
        )
        axes[1, 0].plot(
            dates,
            stage001.source.s006.base._drawdown_pct(equity),
            label=labels[version],
            color=colors[version],
            linewidth=0.9,
        )
        for axis, start, end in (
            (axes[0, 1], stage001.source.YEAR_2022_START, stage001.source.YEAR_2022_END),
            (axes[1, 1], stage001.source.STRESS_START, stage001.source.STRESS_END),
        ):
            mask = dates.between(start, end)
            part = equity[mask].reset_index(drop=True)
            part_dates = dates[mask].reset_index(drop=True)
            if len(part):
                axis.plot(
                    part_dates,
                    part / float(part.iloc[0]),
                    label=labels[version],
                    color=colors[version],
                    linewidth=1.0,
                )
    axes[0, 0].axhline(stage001.CAPITAL, color="#64748b", linestyle="--", linewidth=0.7)
    axes[0, 0].set_title("Absolute account equity")
    axes[1, 0].set_title("Full-period drawdown")
    axes[0, 1].set_title("2022 normalized equity")
    axes[1, 1].set_title("2022-07-15 to 2024-05-10 normalized equity")
    axes[1, 0].set_ylabel("drawdown %")
    for axis in axes.flat:
        axis.grid(True, alpha=0.22)
        axis.legend(fontsize=8)
    fig.suptitle("Stage006 Stage013 reconciled account equity A/C")
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=170, bbox_inches="tight")
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    stress: pd.DataFrame,
    reconciliation: pd.DataFrame,
    pilot: pd.DataFrame,
    ai_parity: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    REPORT_PATH.write_text(
        f"""# Stage006 Stage013 权威权益对账 A/C

- 生成时间：`{decision['generated_at']}`
- 决策：`{decision['decision']}`
- 逐日权益对账：`{decision['reconciliation_ok']}`
- Pilot 语义：`{decision['pilot_semantics_ok']}`
- AI 一致：`{decision['ai_parity_ok']}`
- 收益保留：`{decision['return_retention_ratio']:.6f}`
- 全周期/2022/压力窗回撤改善：`{decision['full_drawdown_improvement_pct']:.4f}` / `{decision['year_2022_drawdown_improvement_pct']:.4f}` / `{decision['main_stress_drawdown_improvement_pct']:.4f}` pp
- broker10 变化：`{decision['broker10_peak_delta_pct']:.4f}` pp
- 独立 review：待完成。

## 全周期

{summary.to_markdown(index=False)}

## 压力窗口

{stress.to_markdown(index=False)}

## 权益对账

{reconciliation.to_markdown(index=False)}

## Pilot 事件

{pilot.to_markdown(index=False)}

## AI 一致性

{ai_parity.to_markdown(index=False)}
""",
        encoding="utf-8",
    )


def _lineage(metadata: dict[str, Any]) -> dict[str, Any]:
    paths = {
        "stage006_tool": Path(__file__).resolve(),
        "stage006_test": TOOLS_DIR / "test_stage006_stage013_reconciled_equity_engine.py",
        "stage001_tool": Path(stage001.__file__).resolve(),
        "stage013_source": Path(stage001.stage013.__file__).resolve(),
        "qmt_roll_portfolio_strategy": PORTFOLIO_DIR / "qmt_roll_portfolio_strategy.py",
        "stage847_engine": Path(stage001.stage013.s847.__file__).resolve(),
        "vnpy_portfolio_backtesting": ROOT
        / ".py311"
        / "lib"
        / "python3.11"
        / "site-packages"
        / "vnpy_portfoliostrategy"
        / "backtesting.py",
        "official_ai": OFFICIAL_LIVE_AI_ELIGIBILITY_PATH,
    }
    live_overrides = dict(
        stage001.source.s006.base.build_official_live_strategy_overrides()
    )
    for key, value in live_overrides.items():
        if "path" not in str(key).lower() or not value:
            continue
        path = Path(str(value)).expanduser()
        if path.is_file():
            paths[f"live_override_{key}"] = path.resolve()
    result: dict[str, Any] = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S CST"),
        "inputs": {},
        "metadata_hashes": {},
        "history_database_snapshot_complete": False,
        "history_database_residual_risk": "database content is sentinel-checked by the engine but not fully hashed",
    }
    for name, path in paths.items():
        result["inputs"][name] = {
            "path": str(path),
            "sha256": _sha256(path),
            "bytes": int(path.stat().st_size),
        }
    for key in (
        "vt_symbols",
        "rates",
        "slippages",
        "sizes",
        "priceticks",
        "margin_ratios",
    ):
        value = metadata.get(key, {})
        if isinstance(value, list):
            value = {str(index): item for index, item in enumerate(value)}
        result["metadata_hashes"][key] = {
            "rows": int(len(value)),
            "sha256": _mapping_hash(dict(value)),
        }
    return result


def _manifest() -> pd.DataFrame:
    rows = []
    for path in sorted(OUT.iterdir()):
        if not path.is_file() or path == MANIFEST_PATH:
            continue
        rows.append(
            {
                "file": path.name,
                "bytes": int(path.stat().st_size),
                "sha256": _sha256(path),
            }
        )
    return pd.DataFrame(rows)


def build() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    metadata = stage001.source._metadata()
    a_eligibility, a_path = _eligibility(A_STRATEGY, A_VERSION, A_VERSION)
    c_eligibility, c_path = _eligibility(C_STRATEGY, C_VERSION, C_VERSION)
    profiles = {
        A_VERSION: stage001._a_profile(metadata, a_path),
        C_VERSION: _candidate_profile(metadata, c_path),
    }
    eligibility = {A_VERSION: a_eligibility, C_VERSION: c_eligibility}
    daily_by_version: dict[str, pd.DataFrame] = {}
    frames_by_version: dict[str, dict[str, pd.DataFrame]] = {}
    summary_rows = []
    curves = []
    for version in VERSIONS:
        daily, frames = _run(metadata, profiles[version], version)
        row, curve, closed = _summary_row(
            version, daily, frames, metadata
        )
        _save_arm(version, daily, frames, closed)
        daily_by_version[version] = daily
        frames_by_version[version] = frames
        summary_rows.append(row)
        curves.append(curve)

    summary = pd.DataFrame(summary_rows)
    curve_frame = pd.concat(curves, ignore_index=True, sort=False)
    stress = stage001._stress(daily_by_version)
    stress["stage"] = STAGE_LABEL
    stress["model_tag"] = MODEL_TAG
    stress["line_id"] = LINE_ID
    reconciliation = _equity_reconciliation(
        daily_by_version[C_VERSION], frames_by_version[C_VERSION]
    )
    pilot = _pilot_audit(
        daily_by_version[C_VERSION], frames_by_version[C_VERSION]
    )
    ai_parity = stage001._ai_parity(eligibility)
    ai_usage = stage001.source.s006._ai_usage_audit(frames_by_version)
    decision = _decision(summary, stress, reconciliation, pilot, ai_parity)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    stress.to_csv(STRESS_PATH, index=False, encoding="utf-8-sig")
    curve_frame.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    reconciliation.to_csv(RECONCILIATION_PATH, index=False, encoding="utf-8-sig")
    pilot.to_csv(PILOT_AUDIT_PATH, index=False, encoding="utf-8-sig")
    ai_parity.to_csv(AI_PARITY_PATH, index=False, encoding="utf-8-sig")
    ai_usage.to_csv(AI_USAGE_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(
        json.dumps(
            stage001.source.s006.base._json_safe(decision),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    LINEAGE_PATH.write_text(
        json.dumps(_lineage(metadata), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _plot(curve_frame)
    _write_report(
        summary, stress, reconciliation, pilot, ai_parity, decision
    )
    _manifest().to_csv(MANIFEST_PATH, index=False, encoding="utf-8-sig")
    return {
        "summary": summary,
        "stress": stress,
        "reconciliation": reconciliation,
        "pilot": pilot,
        "decision": decision,
    }


if __name__ == "__main__":
    result = build()
    print(result["summary"].to_string(index=False))
    print(result["reconciliation"].to_string(index=False))
    print(result["pilot"].to_string(index=False))
    print(
        json.dumps(
            stage001.source.s006.base._json_safe(result["decision"]),
            ensure_ascii=False,
            indent=2,
        )
    )
