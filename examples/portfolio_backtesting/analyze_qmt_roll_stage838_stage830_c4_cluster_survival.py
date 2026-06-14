from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from datetime import datetime
import json
import math
import os
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage825_stage819_intraday_rule_forensics as s825
import analyze_qmt_roll_stage827_stage819_intraday_c2_engine_ac as s827
import analyze_qmt_roll_stage830_stage827_c2_broker10_margin_cap as s830
import analyze_qmt_roll_stage832_stage831_c4_stress_forensics as s832
import analyze_qmt_roll_stage833_stage830_c4_forced_survival as s833
import qmt_roll_official_candidate_stage819_30w_config as stage819_cfg


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage838"
MODEL_TAG = "stage838_stage830_c4_cluster_survival_v1"
OUTPUT_PREFIX = "qmt_roll_stage838_stage830_c4_cluster_survival"

BASE_ARM = s830.BASE_ARM
C4_ARM = s830.CAP_ARM
C6_ARM = "stage838_stage819_c2_broker10_cap_cluster_survival"
DATA_END = pd.Timestamp("2026-05-29")
STRESS_STARTS = ("2018-01", "2019-01", "2020-01", "2021-01")

CLUSTER_TRIGGER_RATIO = 1.00
CLUSTER_TARGET_RATIO = 0.95
CLUSTER_BROKER_MULTIPLIER = float(s830.BROKER_MARGIN_MULTIPLIER)
TOP3_SHARE_MIN = 0.75
DIRECTION_SHARE_MIN = 0.75
MAX_REDUCTIONS_PER_DAY = 100
MAX_WORKERS = max(1, min(2, int(os.environ.get("STAGE838_MAX_WORKERS", "2"))))

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
AGGREGATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_aggregate_{MODEL_TAG}.csv"
TRADE_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_events_{MODEL_TAG}.csv"
INTRADAY_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_intraday_events_{MODEL_TAG}.csv"
CLUSTER_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cluster_events_{MODEL_TAG}.csv"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

_WORKER_STATE: dict[str, Any] = {}


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _month_text(value: Any) -> str:
    return pd.Timestamp(value).strftime("%Y-%m")


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if np.isfinite(number) else default


def _ensure_worker_state() -> dict[str, Any]:
    if _WORKER_STATE:
        return _WORKER_STATE
    metadata = s832.s513._metadata()
    vt_symbols = set(str(item) for item in metadata["vt_symbols"])
    minute_bars = s825._load_minute_bars(vt_symbols)
    s827._GLOBAL_MINUTE_BY_SYMBOL = s825._minute_groups(minute_bars)
    _WORKER_STATE["metadata"] = metadata
    return _WORKER_STATE


class QmtRollPortfolioStrategyStage838ClusterSurvival(s830.QmtRollPortfolioStrategyStage830C2Broker10MarginCap):
    enable_stage838_cluster_survival: bool = False
    stage838_cluster_survival_trigger_ratio: float = CLUSTER_TRIGGER_RATIO
    stage838_cluster_survival_target_ratio: float = CLUSTER_TARGET_RATIO
    stage838_cluster_survival_broker_multiplier: float = CLUSTER_BROKER_MULTIPLIER
    stage838_cluster_survival_top3_share_min: float = TOP3_SHARE_MIN
    stage838_cluster_survival_direction_share_min: float = DIRECTION_SHARE_MIN
    stage838_cluster_survival_max_reductions_per_day: int = MAX_REDUCTIONS_PER_DAY

    parameters = s830.QmtRollPortfolioStrategyStage830C2Broker10MarginCap.parameters + [
        "enable_stage838_cluster_survival",
        "stage838_cluster_survival_trigger_ratio",
        "stage838_cluster_survival_target_ratio",
        "stage838_cluster_survival_broker_multiplier",
        "stage838_cluster_survival_top3_share_min",
        "stage838_cluster_survival_direction_share_min",
        "stage838_cluster_survival_max_reductions_per_day",
    ]
    variables = s830.QmtRollPortfolioStrategyStage830C2Broker10MarginCap.variables + [
        "stage838_cluster_survival_event_count",
    ]

    def __init__(self, strategy_engine, strategy_name: str, vt_symbols: list[str], setting: dict) -> None:
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)
        self.stage838_cluster_survival_event_count = 0
        self.stage838_cluster_survival_events: list[dict[str, Any]] = []
        self.stage838_cluster_survival_monitor_events: list[dict[str, Any]] = []
        self.stage838_cluster_survival_max_ratio: float = 0.0

    def _stage838_position_rows(self, bars: dict[str, Any]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for state in self.states.values():
            if not state.layers or not state.contract_vt_symbol:
                continue
            bar = bars.get(state.contract_vt_symbol)
            if bar is None:
                continue
            volume = int(state.active_volume())
            if volume <= 0:
                continue
            size = self.get_size(state.contract_vt_symbol)
            close_price = float(bar.close_price)
            margin_ratio = self._margin_ratio_for_symbol(state.contract_vt_symbol)
            margin_per_contract = max(0.0, close_price * size * margin_ratio)
            if margin_per_contract <= 0:
                continue
            unrealized_pnl = 0.0
            for layer in state.layers:
                if layer.direction == "long":
                    unrealized_pnl += (close_price - float(layer.entry_price)) * size * int(layer.volume)
                else:
                    unrealized_pnl += (float(layer.entry_price) - close_price) * size * int(layer.volume)
            rows.append(
                {
                    "state": state,
                    "bar": bar,
                    "product_vt_symbol": state.product_vt_symbol,
                    "contract_vt_symbol": state.contract_vt_symbol,
                    "direction": state.direction,
                    "volume": volume,
                    "margin_per_contract": margin_per_contract,
                    "margin": margin_per_contract * volume,
                    "unrealized_pnl": unrealized_pnl,
                }
            )
        return rows

    def _stage838_cluster_snapshot(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        total_margin = sum(float(row["margin"]) for row in rows)
        if total_margin <= 0:
            return {
                "total_margin": 0.0,
                "top3_share": 0.0,
                "direction_share": 0.0,
                "dominant_direction": "",
                "top_keys": set(),
                "top_clusters": "",
            }
        grouped: dict[tuple[str, str], float] = {}
        direction_margin: dict[str, float] = {}
        for row in rows:
            key = (str(row["product_vt_symbol"]), str(row["direction"]))
            grouped[key] = grouped.get(key, 0.0) + float(row["margin"])
            direction = str(row["direction"])
            direction_margin[direction] = direction_margin.get(direction, 0.0) + float(row["margin"])
        sorted_clusters = sorted(grouped.items(), key=lambda item: item[1], reverse=True)
        top3 = sorted_clusters[:3]
        top3_share = sum(value for _, value in top3) / total_margin
        dominant_direction, dominant_margin = max(direction_margin.items(), key=lambda item: item[1])
        direction_share = dominant_margin / total_margin
        top_keys = set(key for key, _ in top3)
        top_clusters = ",".join(f"{product} {direction}:{value / total_margin * 100.0:.2f}%" for (product, direction), value in top3)
        return {
            "total_margin": total_margin,
            "top3_share": top3_share,
            "direction_share": direction_share,
            "dominant_direction": dominant_direction,
            "top_keys": top_keys,
            "top_clusters": top_clusters,
        }

    def _stage838_sorted_candidates(
        self,
        rows: list[dict[str, Any]],
        snapshot: dict[str, Any],
    ) -> list[dict[str, Any]]:
        top_keys = snapshot.get("top_keys", set())
        dominant_direction = str(snapshot.get("dominant_direction") or "")

        def rank(row: dict[str, Any]) -> tuple[int, int, float, float]:
            key = (str(row["product_vt_symbol"]), str(row["direction"]))
            return (
                0 if key in top_keys else 1,
                0 if str(row["direction"]) == dominant_direction else 1,
                -float(row["margin"]),
                float(row["unrealized_pnl"]),
            )

        candidates = list(rows)
        candidates.sort(key=rank)
        return candidates

    def _stage838_record_monitor_event(
        self,
        rows: list[dict[str, Any]],
        snapshot: dict[str, Any],
        current_ratio: float,
        reason: str,
        trigger_ratio: float,
    ) -> None:
        if not rows:
            return
        bar = rows[0]["bar"]
        event = {
            "datetime": bar.datetime,
            "date": bar.datetime.date(),
            "vt_symbol": "",
            "product_vt_symbol": "",
            "direction": "",
            "position_direction": "",
            "offset": "RiskMonitor",
            "reason": reason,
            "volume": 0,
            "price": float(getattr(bar, "close_price", 0.0) or 0.0),
            "current_ratio": current_ratio,
            "trigger_ratio": trigger_ratio,
            "top3_share": float(snapshot["top3_share"]),
            "direction_share": float(snapshot["direction_share"]),
            "dominant_direction": str(snapshot["dominant_direction"]),
            "top_clusters": str(snapshot["top_clusters"]),
        }
        self.stage838_cluster_survival_monitor_events.append(event)
        diagnostics = getattr(self, "trade_event_diagnostics", None)
        if diagnostics is not None:
            diagnostics.append(event)

    def _process_forced_margin_deleverage(self, bars: dict[str, Any]) -> None:
        if not bool(self.enable_stage838_cluster_survival):
            return super()._process_forced_margin_deleverage(bars)
        if not bars:
            return

        trigger_ratio = max(0.0, float(self.stage838_cluster_survival_trigger_ratio or 0.0))
        target_ratio = max(0.0, float(self.stage838_cluster_survival_target_ratio or 0.0))
        if trigger_ratio <= 0.0 or target_ratio <= 0.0:
            return
        target_ratio = min(target_ratio, trigger_ratio)
        broker_multiplier = max(0.0, float(self.stage838_cluster_survival_broker_multiplier or 1.0))
        if broker_multiplier <= 0.0:
            return

        equity = max(1e-9, float(self.estimated_equity or self.base_capital))
        max_reductions = max(1, int(self.stage838_cluster_survival_max_reductions_per_day or 1))
        top3_min = max(0.0, float(self.stage838_cluster_survival_top3_share_min or 0.0))
        direction_min = max(0.0, float(self.stage838_cluster_survival_direction_share_min or 0.0))
        reductions = 0

        while reductions < max_reductions:
            rows = self._stage838_position_rows(bars)
            current_margin = sum(float(row["margin"]) for row in rows)
            current_ratio = current_margin * broker_multiplier / equity
            self.forced_margin_deleverage_ratio = current_ratio
            self.forced_margin_deleverage_max_observed_ratio = max(
                self.forced_margin_deleverage_max_observed_ratio,
                current_ratio,
            )
            snapshot = self._stage838_cluster_snapshot(rows)
            if current_ratio > self.stage838_cluster_survival_max_ratio + 1e-12:
                self.stage838_cluster_survival_max_ratio = current_ratio
                self._stage838_record_monitor_event(
                    rows,
                    snapshot,
                    current_ratio,
                    "stage838_cluster_survival_monitor_new_max",
                    trigger_ratio,
                )
            if current_ratio <= trigger_ratio + 1e-12:
                break
            if (
                float(snapshot["top3_share"]) < top3_min
                or float(snapshot["direction_share"]) < direction_min
            ):
                if current_ratio > trigger_ratio + 1e-12:
                    self._stage838_record_monitor_event(
                        rows,
                        snapshot,
                        current_ratio,
                        "stage838_cluster_survival_skip_concentration",
                        trigger_ratio,
                    )
                break

            candidates = self._stage838_sorted_candidates(rows, snapshot)
            if not candidates:
                break
            target_margin = equity * target_ratio / broker_multiplier
            margin_to_release = max(0.0, current_margin - target_margin)
            candidate = candidates[0]
            state = candidate["state"]
            bar = candidate["bar"]
            volume = int(candidate["volume"])
            margin_per_contract = max(1e-9, float(candidate["margin_per_contract"]))
            reduce_volume = min(volume, max(1, int(math.ceil(margin_to_release / margin_per_contract))))
            target_volume = max(0, volume - reduce_volume)
            close_price = float(bar.close_price)
            contract_vt_symbol = str(candidate["contract_vt_symbol"])
            product_vt_symbol = str(candidate["product_vt_symbol"])
            direction = str(candidate["direction"])
            reason = "stage838_cluster_survival_deleverage"
            diagnostics = getattr(self, "trade_event_diagnostics", None)
            before_len = len(diagnostics) if diagnostics is not None else 0
            self._record_trade_event(
                bar=bar,
                contract_vt_symbol=contract_vt_symbol,
                product_vt_symbol=product_vt_symbol,
                position_direction=direction,
                offset="Close",
                reason=reason,
                volume=reduce_volume,
                price=close_price,
            )
            ratio_before = current_ratio
            self._reduce_position_to_target(state, target_volume, close_price)
            if state.layers:
                self._apply_state_target(state, execution_price_override=close_price)
            else:
                if close_price > 0:
                    self.execution_price_overrides[contract_vt_symbol] = close_price
                self.set_target(contract_vt_symbol, 0)

            margin_after = self._estimate_margin_usage(bars)
            ratio_after = margin_after * broker_multiplier / equity
            reductions += 1
            self.stage838_cluster_survival_event_count += 1
            self.forced_margin_deleverage_count += 1
            self.forced_margin_deleverage_closed_volume += reduce_volume
            self.forced_margin_deleverage_ratio = ratio_after
            event = {
                "datetime": bar.datetime,
                "date": bar.datetime.date(),
                "vt_symbol": contract_vt_symbol,
                "product_vt_symbol": product_vt_symbol,
                "direction": direction,
                "reason": reason,
                "priority": "top3_product_direction_then_dominant_direction",
                "trigger_ratio": trigger_ratio,
                "target_ratio": target_ratio,
                "broker_multiplier": broker_multiplier,
                "top3_share": float(snapshot["top3_share"]),
                "direction_share": float(snapshot["direction_share"]),
                "dominant_direction": str(snapshot["dominant_direction"]),
                "top_clusters": str(snapshot["top_clusters"]),
                "equity": equity,
                "margin_before": current_margin,
                "ratio_before": ratio_before,
                "margin_per_contract": margin_per_contract,
                "reduce_volume": reduce_volume,
                "volume_before": volume,
                "volume_after": target_volume,
                "price": close_price,
                "margin_after": margin_after,
                "ratio_after": ratio_after,
            }
            self.forced_margin_deleverage_events.append(event)
            self.stage838_cluster_survival_events.append(event)
            if diagnostics is not None and len(diagnostics) > before_len:
                diagnostics[-1].update(event)


def _profile_c6(metadata: dict[str, Any], start: pd.Timestamp) -> dict[str, Any]:
    start_text = _month_text(start)
    profile = s830._cap_profile(metadata)
    spec = profile["spec"]
    capital = replace(
        spec.capital,
        variant=f"stage838_{C6_ARM}_{start_text.replace('-', '_')}",
        label=f"Stage838 C6 C4 + cluster survival {start_text}",
        note=(
            f"{spec.capital.note} | Stage838 C6: C4 plus concentration-aware holding survival. "
            "After mark-to-market, if runtime-calibrated broker10 margin/equity exceeds 100% and product-direction concentration "
            "is high, reduce the dominant product-direction cluster toward a 95% buffer."
        ),
    )
    overrides = {
        **spec.overrides,
        "enable_stage827_intraday_c2_stop": True,
        "enable_stage830_broker10_margin_cap": True,
        "stage830_broker_margin_multiplier": s830.BROKER_MARGIN_MULTIPLIER,
        "stage830_projected_broker10_margin_to_equity_cap": s830.PROJECTED_BROKER10_MARGIN_TO_EQUITY_CAP,
        "enable_forced_margin_deleverage": False,
        "enable_stage838_cluster_survival": True,
        "stage838_cluster_survival_trigger_ratio": CLUSTER_TRIGGER_RATIO,
        "stage838_cluster_survival_target_ratio": CLUSTER_TARGET_RATIO,
        "stage838_cluster_survival_broker_multiplier": CLUSTER_BROKER_MULTIPLIER,
        "stage838_cluster_survival_top3_share_min": TOP3_SHARE_MIN,
        "stage838_cluster_survival_direction_share_min": DIRECTION_SHARE_MIN,
        "stage838_cluster_survival_max_reductions_per_day": MAX_REDUCTIONS_PER_DAY,
    }
    result = dict(profile)
    result["profile"] = C6_ARM
    result["strategy_cls"] = QmtRollPortfolioStrategyStage838ClusterSurvival
    result["spec"] = replace(spec, capital=capital, overrides=overrides, profile=C6_ARM)
    return result


def _run_c6(start_text: str) -> dict[str, pd.DataFrame]:
    state = _ensure_worker_state()
    metadata = state["metadata"]
    start = pd.Timestamp(f"{start_text}-01").normalize()
    original_start = s827.START
    original_end = s827.END
    try:
        s827.START = start
        s827.END = DATA_END
        profile = _profile_c6(metadata, start)
        combined, frames = s827._run_profile(profile, metadata)
        summary, curve = s827._metric(profile, combined)
        for frame in [summary, curve]:
            frame["arm"] = C6_ARM
            frame["requested_start_month"] = start_text
            frame["start_month"] = start_text
            frame["start_year"] = int(start.year)
            frame["analysis_start"] = start.strftime("%Y-%m-%d")
            frame["analysis_end"] = DATA_END.strftime("%Y-%m-%d")

        trade_events = frames.get("trade_events", pd.DataFrame()).copy()
        intraday_events = frames.get("intraday_events", pd.DataFrame()).copy()
        for frame in [trade_events, intraday_events]:
            if frame.empty:
                continue
            frame["arm"] = C6_ARM
            frame["requested_start_month"] = start_text
            frame["start_month"] = start_text
            frame["start_year"] = int(start.year)
            frame["analysis_start"] = start.strftime("%Y-%m-%d")
            frame["analysis_end"] = DATA_END.strftime("%Y-%m-%d")

        cluster_events = pd.DataFrame()
        monitor_events = pd.DataFrame()
        if not trade_events.empty and "reason" in trade_events.columns:
            cluster_events = trade_events[trade_events["reason"].astype(str).eq("stage838_cluster_survival_deleverage")].copy()
            monitor_events = trade_events[
                trade_events["reason"].astype(str).isin(
                    [
                        "stage838_cluster_survival_monitor_new_max",
                        "stage838_cluster_survival_skip_concentration",
                    ]
                )
            ].copy()

        summary["stage827_intraday_event_count"] = int(len(intraday_events))
        summary["stage827_intraday_event_volume"] = (
            float(pd.to_numeric(intraday_events.get("volume", 0), errors="coerce").fillna(0.0).sum())
            if not intraday_events.empty
            else 0.0
        )
        if not trade_events.empty and "reason" in trade_events.columns:
            cap_events = trade_events[trade_events["reason"].astype(str).str.startswith("broker10_margin_cap", na=False)].copy()
        else:
            cap_events = pd.DataFrame()
        summary["stage830_cap_event_count"] = int(len(cap_events))
        summary["stage830_cap_reduced_volume"] = (
            float(pd.to_numeric(cap_events.get("reduced_volume", 0), errors="coerce").fillna(0.0).sum())
            if not cap_events.empty
            else 0.0
        )
        summary["stage838_cluster_event_count"] = int(len(cluster_events))
        summary["stage838_cluster_closed_volume"] = (
            float(pd.to_numeric(cluster_events.get("reduce_volume", cluster_events.get("volume", 0)), errors="coerce").fillna(0.0).sum())
            if not cluster_events.empty
            else 0.0
        )
        summary["stage838_monitor_event_count"] = int(len(monitor_events))
        summary["stage838_runtime_max_ratio"] = (
            float(pd.to_numeric(monitor_events.get("current_ratio", np.nan), errors="coerce").max())
            if not monitor_events.empty
            else 0.0
        )
        summary["stage838_runtime_max_top3_share"] = (
            float(pd.to_numeric(monitor_events.get("top3_share", np.nan), errors="coerce").max())
            if not monitor_events.empty
            else 0.0
        )
        summary["stage838_runtime_max_direction_share"] = (
            float(pd.to_numeric(monitor_events.get("direction_share", np.nan), errors="coerce").max())
            if not monitor_events.empty
            else 0.0
        )
        summary["stage838_runtime_over_trigger_count"] = (
            int(pd.to_numeric(monitor_events.get("current_ratio", np.nan), errors="coerce").gt(CLUSTER_TRIGGER_RATIO).sum())
            if not monitor_events.empty
            else 0
        )
        return {
            "summary": summary,
            "curves": curve,
            "trade_events": trade_events,
            "intraday_events": intraday_events,
            "cluster_events": cluster_events,
        }
    finally:
        s827.START = original_start
        s827.END = original_end


def _concat(results: list[dict[str, pd.DataFrame]], key: str) -> pd.DataFrame:
    frames = [item.get(key, pd.DataFrame()) for item in results if not item.get(key, pd.DataFrame()).empty]
    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()


def _metric_value(row: pd.Series, column: str) -> float:
    return float(pd.to_numeric(pd.Series([row.get(column, np.nan)]), errors="coerce").iloc[0])


def _comparison(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    metric_cols = [
        "end_equity",
        "total_return_pct",
        "max_dd_pct",
        "sharpe",
        "total_slippage",
        "total_trade_count",
        "nonzero_daily_win_rate_pct",
        "max_broker10_margin_to_equity_pct",
        "p95_broker10_margin_to_equity_pct",
        "days_over_100pct",
        "days_over_90pct",
        "dd40_fail",
        "dd50_fail",
        "stage827_intraday_event_count",
        "stage827_intraday_event_volume",
        "stage830_cap_event_count",
        "stage830_cap_reduced_volume",
        "stage838_cluster_event_count",
        "stage838_cluster_closed_volume",
        "stage838_monitor_event_count",
        "stage838_runtime_max_ratio",
        "stage838_runtime_max_top3_share",
        "stage838_runtime_max_direction_share",
        "stage838_runtime_over_trigger_count",
    ]
    for start_month, group in summary.groupby("start_month", sort=True):
        indexed = group.set_index("arm")
        if BASE_ARM not in indexed.index or C4_ARM not in indexed.index or C6_ARM not in indexed.index:
            continue
        row: dict[str, Any] = {"start_month": start_month}
        for arm, label in [(BASE_ARM, "A"), (C4_ARM, "C4"), (C6_ARM, "C6")]:
            source = indexed.loc[arm]
            for column in metric_cols:
                row[f"{column}_{label}"] = _metric_value(source, column)
        row["end_equity_delta_C6_vs_A"] = row["end_equity_C6"] - row["end_equity_A"]
        row["end_equity_delta_C6_vs_C4"] = row["end_equity_C6"] - row["end_equity_C4"]
        row["return_delta_C6_vs_A_pp"] = row["total_return_pct_C6"] - row["total_return_pct_A"]
        row["return_delta_C6_vs_C4_pp"] = row["total_return_pct_C6"] - row["total_return_pct_C4"]
        row["dd_delta_C6_vs_A_pp"] = row["max_dd_pct_C6"] - row["max_dd_pct_A"]
        row["dd_delta_C6_vs_C4_pp"] = row["max_dd_pct_C6"] - row["max_dd_pct_C4"]
        row["broker10_delta_C6_vs_C4_pp"] = (
            row["max_broker10_margin_to_equity_pct_C6"] - row["max_broker10_margin_to_equity_pct_C4"]
        )
        row["C6_return_win_vs_A"] = int(row["total_return_pct_C6"] > row["total_return_pct_A"])
        row["C6_dd_win_vs_A"] = int(row["max_dd_pct_C6"] > row["max_dd_pct_A"])
        row["C6_dd_win_vs_C4"] = int(row["max_dd_pct_C6"] > row["max_dd_pct_C4"])
        row["C6_broker100_fail"] = int(row["max_broker10_margin_to_equity_pct_C6"] > 100.0)
        row["C4_broker100_fail"] = int(row["max_broker10_margin_to_equity_pct_C4"] > 100.0)
        rows.append(row)
    return pd.DataFrame(rows).sort_values("start_month").reset_index(drop=True)


def _aggregate(comparison: pd.DataFrame) -> pd.DataFrame:
    if comparison.empty:
        return pd.DataFrame()
    return pd.DataFrame(
        [
            {
                "bucket": "stress_starts",
                "window_count": int(len(comparison)),
                "C6_return_win_vs_A_count": int(comparison["C6_return_win_vs_A"].sum()),
                "C6_dd_win_vs_A_count": int(comparison["C6_dd_win_vs_A"].sum()),
                "C6_dd_win_vs_C4_count": int(comparison["C6_dd_win_vs_C4"].sum()),
                "A_dd50_fail_count": int(comparison["dd50_fail_A"].sum()),
                "C4_dd50_fail_count": int(comparison["dd50_fail_C4"].sum()),
                "C6_dd50_fail_count": int(comparison["dd50_fail_C6"].sum()),
                "A_broker100_fail_count": int((comparison["max_broker10_margin_to_equity_pct_A"] > 100.0).sum()),
                "C4_broker100_fail_count": int(comparison["C4_broker100_fail"].sum()),
                "C6_broker100_fail_count": int(comparison["C6_broker100_fail"].sum()),
                "median_return_delta_C6_vs_A_pp": float(comparison["return_delta_C6_vs_A_pp"].median()),
                "median_return_delta_C6_vs_C4_pp": float(comparison["return_delta_C6_vs_C4_pp"].median()),
                "median_dd_delta_C6_vs_A_pp": float(comparison["dd_delta_C6_vs_A_pp"].median()),
                "median_dd_delta_C6_vs_C4_pp": float(comparison["dd_delta_C6_vs_C4_pp"].median()),
                "max_broker10_C6": float(comparison["max_broker10_margin_to_equity_pct_C6"].max()),
                "cluster_event_count": int(comparison["stage838_cluster_event_count_C6"].sum()),
                "cluster_closed_volume": float(comparison["stage838_cluster_closed_volume_C6"].sum()),
                "max_runtime_ratio_C6": float(comparison["stage838_runtime_max_ratio_C6"].max()),
                "runtime_over_trigger_count": int(comparison["stage838_runtime_over_trigger_count_C6"].sum()),
            }
        ]
    )


def _plot(comparison: pd.DataFrame) -> None:
    if comparison.empty:
        return
    x = np.arange(len(comparison))
    labels = comparison["start_month"].astype(str).tolist()
    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True, constrained_layout=True)
    width = 0.25
    for ax, metric, title in [
        (axes[0], "total_return_pct", "Total return pct"),
        (axes[1], "max_dd_pct", "Max drawdown pct"),
        (axes[2], "max_broker10_margin_to_equity_pct", "Max broker10 margin/equity pct"),
    ]:
        ax.bar(x - width, comparison[f"{metric}_A"], width=width, label="A", color="#2563eb")
        ax.bar(x, comparison[f"{metric}_C4"], width=width, label="C4", color="#16a34a")
        ax.bar(x + width, comparison[f"{metric}_C6"], width=width, label="C6", color="#f59e0b")
        if metric == "max_broker10_margin_to_equity_pct":
            ax.axhline(100.0, color="#111827", linestyle="--", linewidth=1.0)
        if metric == "max_dd_pct":
            ax.axhline(-50.0, color="#111827", linestyle="--", linewidth=1.0)
        ax.set_title(title)
        ax.grid(True, axis="y", alpha=0.25)
        ax.legend(loc="best")
    axes[-1].set_xticks(x)
    axes[-1].set_xticklabels(labels, rotation=25, ha="right")
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _decision(aggregate: pd.DataFrame, comparison: pd.DataFrame) -> dict[str, Any]:
    row = aggregate.iloc[0].to_dict() if not aggregate.empty else {}
    broker_fixed = int(row.get("C6_broker100_fail_count", 999)) == 0
    dd_not_worse_than_c4 = int(row.get("C6_dd_win_vs_C4_count", 0)) >= 3
    return_retention = float(row.get("median_return_delta_C6_vs_C4_pp", -1e9)) > -500.0
    decision_label = (
        "stage838_c6_cluster_survival_candidate_needs_yearly"
        if broker_fixed and dd_not_worse_than_c4 and return_retention
        else "stage838_c6_cluster_survival_not_enough"
    )
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "source_candidate": stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "strategy_changed": True,
        "formal_ab_triggered": False,
        "ctp_connected": False,
        "order_api_called": False,
        "arms": {"A": BASE_ARM, "C4": C4_ARM, "C6": C6_ARM},
        "stress_starts": list(STRESS_STARTS),
        "frozen_parameters": {
            "stage827_intraday_c2_stop_r": s827.STOP_R,
            "stage827_intraday_c2_confirm_r": s827.CONFIRM_R,
            "stage830_broker_margin_multiplier": s830.BROKER_MARGIN_MULTIPLIER,
            "stage830_projected_broker10_margin_to_equity_cap": s830.PROJECTED_BROKER10_MARGIN_TO_EQUITY_CAP,
            "cluster_trigger_ratio": CLUSTER_TRIGGER_RATIO,
            "cluster_target_ratio": CLUSTER_TARGET_RATIO,
            "cluster_broker_multiplier": CLUSTER_BROKER_MULTIPLIER,
            "top3_share_min": TOP3_SHARE_MIN,
            "direction_share_min": DIRECTION_SHARE_MIN,
            "priority": "top3_product_direction_then_dominant_direction",
        },
        "aggregate": aggregate.to_dict("records"),
        "comparison": comparison.to_dict("records"),
        "decision": decision_label,
        "judgment": (
            "Stage838 tests the Stage837 cluster-pressure shape as a stress-start survival rule. "
            "It is still not a formal candidate or official A/B."
        ),
        "overfit_reflection": (
            "Medium. The rule shape comes from broad margin-risk mechanics and all Stage832 stress anchors, "
            "but the validation set is still the known stress-start subset. Product-specific conclusions would overfit."
        ),
        "continue_value": (
            "Continue only if C6 removes broker100 without materially damaging C4 return or drawdown. "
            "Otherwise stop the C4 survival branch instead of scanning trigger/target thresholds."
        ),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "curves": str(CURVES_PATH),
            "comparison": str(COMPARISON_PATH),
            "aggregate": str(AGGREGATE_PATH),
            "trade_events": str(TRADE_EVENTS_PATH),
            "intraday_events": str(INTRADAY_EVENTS_PATH),
            "cluster_events": str(CLUSTER_EVENTS_PATH),
            "report": str(REPORT_PATH),
            "chart": str(CHART_PATH),
            "decision": str(DECISION_PATH),
        },
    }


def _write_report(
    comparison: pd.DataFrame,
    aggregate: pd.DataFrame,
    cluster_events: pd.DataFrame,
    monitor_events: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    display_cols = [
        "start_month",
        "total_return_pct_A",
        "total_return_pct_C4",
        "total_return_pct_C6",
        "return_delta_C6_vs_C4_pp",
        "max_dd_pct_A",
        "max_dd_pct_C4",
        "max_dd_pct_C6",
        "dd_delta_C6_vs_C4_pp",
        "max_broker10_margin_to_equity_pct_A",
        "max_broker10_margin_to_equity_pct_C4",
        "max_broker10_margin_to_equity_pct_C6",
        "stage838_cluster_event_count_C6",
        "stage838_cluster_closed_volume_C6",
        "stage838_runtime_max_ratio_C6",
        "stage838_runtime_max_top3_share_C6",
        "stage838_runtime_max_direction_share_C6",
        "stage838_runtime_over_trigger_count_C6",
    ]
    event_display = cluster_events.copy()
    if not event_display.empty:
        event_display = event_display[
            [
                "start_month",
                "date",
                "vt_symbol",
                "product_vt_symbol",
                "direction",
                "reduce_volume",
                "ratio_before",
                "ratio_after",
                "top3_share",
                "direction_share",
                "dominant_direction",
                "top_clusters",
            ]
        ].sort_values(["start_month", "date", "product_vt_symbol"])
    monitor_display = monitor_events.copy()
    if not monitor_display.empty:
        monitor_display = monitor_display[
            [
                "start_month",
                "date",
                "reason",
                "current_ratio",
                "trigger_ratio",
                "top3_share",
                "direction_share",
                "dominant_direction",
                "top_clusters",
            ]
        ].sort_values(["start_month", "date", "current_ratio"], ascending=[True, True, False])
    lines = [
        "# Stage838 C4叠加集中簇持仓生存线压力起点验证",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 源候选：`{stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION}`",
        "- 阶段性质：冻结 C6 stress-start 验证；不改正式策略、不连接 CTP、不调用下单。",
        "- A：Stage819 baseline。",
        "- C4：Stage827 C2 日内实时止损 + Stage830 broker10 100% flat-entry 保证金入口闸门。",
        "- C6：C4 + 持仓后 concentration-aware survival。runtime-calibrated broker10 口径 `>100%` 且 top3 产品方向簇、方向集中同时高时，按主导产品方向簇优先减仓到 `95%` buffer。",
        f"- runtime 口径说明：输出曲线 broker10 使用 `{s650.BROKER_MARGIN_MULTIPLIER:.2f} * exact_margin / equity`；策略内 `_estimate_margin_usage` 低于 exact_margin，因此 C6 沿用 Stage830/Stage833 的 `{CLUSTER_BROKER_MULTIPLIER:.2f}` runtime 校准倍数。",
        "- 本阶段不扫描 `1R`、entry cap、trigger/target、broker multiplier、冷却天数、品种过滤或年份过滤。",
        "",
        "## External Research Judgment",
        "",
        "- CME/Euronext/FINRA 等资料都把 futures 风险管理落到合约手数、margin、concentration 和 intraday/EOD 监控；这支持账户/持仓层生存线，而不是继续扫分钟止损参数。",
        "- GitHub/开源回测参考多停留在 margin call 或最大保证金控制，较少直接处理产品方向簇集中；因此本阶段只借鉴风控原则，不复制复杂框架。",
        "",
        "## Aggregate",
        "",
        _md_table(aggregate, max_rows=10),
        "",
        "## Stress Start Comparison",
        "",
        _md_table(comparison[display_cols], max_rows=20),
        "",
        "## Cluster Events",
        "",
        _md_table(event_display, max_rows=80),
        "",
        "## Monitor Events",
        "",
        _md_table(monitor_display, max_rows=80),
        "",
        "## Decision",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 判断：{decision['judgment']}",
        "",
        "## Charts",
        "",
        f"- chart：`{CHART_PATH}`",
        "",
        "## Overfit / Continue",
        "",
        f"- 过拟合反思：{decision['overfit_reflection']}",
        f"- 继续价值：{decision['continue_value']}",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    reference_summary, reference_curves = s833._load_stage832_reference()
    results: list[dict[str, pd.DataFrame]] = []
    print(f"[stage838] launching {len(STRESS_STARTS)} C6 stress-start runs workers={MAX_WORKERS}", flush=True)
    if MAX_WORKERS == 1:
        for index, start in enumerate(STRESS_STARTS, start=1):
            print(f"[stage838] running {index}/{len(STRESS_STARTS)} {start}", flush=True)
            results.append(_run_c6(start))
    else:
        with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_map = {executor.submit(_run_c6, start): start for start in STRESS_STARTS}
            for index, future in enumerate(as_completed(future_map), start=1):
                start = future_map[future]
                results.append(future.result())
                print(f"[stage838] completed {index}/{len(STRESS_STARTS)} {start}", flush=True)

    c6_summary = _concat(results, "summary")
    c6_curves = _concat(results, "curves")
    trade_events = _concat(results, "trade_events")
    intraday_events = _concat(results, "intraday_events")
    cluster_events = _concat(results, "cluster_events")
    monitor_events = (
        trade_events[
            trade_events["reason"].astype(str).isin(
                [
                    "stage838_cluster_survival_monitor_new_max",
                    "stage838_cluster_survival_skip_concentration",
                ]
            )
        ].copy()
        if not trade_events.empty and "reason" in trade_events.columns
        else pd.DataFrame()
    )

    summary = pd.concat([reference_summary, c6_summary], ignore_index=True, sort=False)
    curves = pd.concat([reference_curves, c6_curves], ignore_index=True, sort=False)
    comparison = _comparison(summary)
    aggregate = _aggregate(comparison)
    decision = _decision(aggregate, comparison)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    aggregate.to_csv(AGGREGATE_PATH, index=False, encoding="utf-8-sig")
    trade_events.to_csv(TRADE_EVENTS_PATH, index=False, encoding="utf-8-sig")
    intraday_events.to_csv(INTRADAY_EVENTS_PATH, index=False, encoding="utf-8-sig")
    cluster_events.to_csv(CLUSTER_EVENTS_PATH, index=False, encoding="utf-8-sig")
    _plot(comparison)
    _write_report(comparison, aggregate, cluster_events, monitor_events, decision)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), flush=True)
    print("aggregate", flush=True)
    print(aggregate.to_string(index=False), flush=True)
    print("comparison", flush=True)
    print(comparison.to_string(index=False), flush=True)
    print("cluster_events", flush=True)
    print(cluster_events.to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
