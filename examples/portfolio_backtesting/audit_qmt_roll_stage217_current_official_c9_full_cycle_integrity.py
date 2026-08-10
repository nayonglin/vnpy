from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine as s847
import analyze_qmt_roll_stage861_stage860_full_visual_atlas as s861
import audit_qmt_roll_stage900_c9_deep_trade_forensics as s900
import analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow as s901
from main_contract_mapping import ALL_FUTURES_MAPPING_PATH
from qmt_backtest_runtime_guard import EXPECTED_DATABASE_PATH
from qmt_roll_official_live_config import (
    OFFICIAL_LIVE_AI_ELIGIBILITY_PATH,
    OFFICIAL_LIVE_ALIAS,
    OFFICIAL_LIVE_CAPITAL,
    OFFICIAL_LIVE_CAPITAL_LABEL,
    OFFICIAL_LIVE_PROFILE_NAME,
    OFFICIAL_LIVE_VERSION,
    build_official_live_strategy_overrides,
)


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage217"
MODEL_TAG = "stage217_current_official_c9_full_cycle_integrity_v1"
OUTPUT_PREFIX = "qmt_roll_stage217_current_official_c9_full_cycle_integrity"

ANALYSIS_START = pd.Timestamp("2018-01-01")
ANALYSIS_END = pd.Timestamp("2026-06-30")

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CHECKS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_checks_{MODEL_TAG}.csv"
DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
TRADES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{MODEL_TAG}.csv"
ENTRY_EXECUTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_execution_{MODEL_TAG}.csv"
STOP_RETRY_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stop_retry_events_{MODEL_TAG}.csv"
SAME_BAR_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_same_reentry_bar_audit_{MODEL_TAG}.csv"
EVENT_PRICE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_price_audit_{MODEL_TAG}.csv"
COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_day_coverage_by_year_{MODEL_TAG}.csv"
INPUT_MANIFEST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_input_manifest_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

STAGE153_SUMMARY_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage153_c9_live_15w_annual_starts_to_20260630_summary_"
    "stage153_c9_live_15w_annual_starts_to_20260630_v1.csv"
)


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normal_date(value: Any) -> pd.Timestamp:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return pd.NaT
    ts = pd.Timestamp(ts)
    if ts.tzinfo is not None:
        ts = ts.tz_localize(None)
    return ts.normalize()


def _normal_offset(value: Any) -> str:
    text = str(value).strip().lower()
    if text in {"open", "开", "offset.open"}:
        return "open"
    if text in {"close", "平", "平今", "平昨", "offset.close", "offset.closetoday", "offset.closeyesterday"}:
        return "close"
    return text


def _normal_direction(value: Any) -> str:
    text = str(value).strip().lower()
    if text in {"long", "多", "direction.long", "buy"}:
        return "long"
    if text in {"short", "空", "direction.short", "sell"}:
        return "short"
    return text


def _metrics(curve: pd.DataFrame) -> dict[str, Any]:
    frame = curve.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    equity = pd.to_numeric(frame["account_equity"], errors="coerce").ffill()
    net_pnl = pd.to_numeric(frame.get("net_pnl", 0.0), errors="coerce").fillna(0.0)
    returns = equity.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    drawdown = equity / equity.cummax().replace(0.0, np.nan) - 1.0
    std = float(returns.std(ddof=1)) if len(returns) else 0.0
    rebuilt_equity = float(OFFICIAL_LIVE_CAPITAL) + net_pnl.cumsum()
    return {
        "actual_start": frame["date"].iloc[0].date().isoformat(),
        "actual_end": frame["date"].iloc[-1].date().isoformat(),
        "trading_days": int(len(frame)),
        "end_equity": float(equity.iloc[-1]),
        "total_return_pct": float((equity.iloc[-1] / OFFICIAL_LIVE_CAPITAL - 1.0) * 100.0),
        "max_dd_pct": float(drawdown.min() * 100.0),
        "sharpe": float(returns.mean() / std * np.sqrt(252.0)) if std > 0.0 else 0.0,
        "total_slippage": float(pd.to_numeric(frame.get("slippage", 0.0), errors="coerce").fillna(0.0).sum()),
        "total_commission": float(pd.to_numeric(frame.get("commission", 0.0), errors="coerce").fillna(0.0).sum()),
        "total_trade_count": float(pd.to_numeric(frame.get("trade_count", 0.0), errors="coerce").fillna(0.0).sum()),
        "nonzero_daily_win_rate_pct": float((returns[returns.ne(0.0)] > 0.0).mean() * 100.0) if returns.ne(0.0).any() else 0.0,
        "max_broker10_margin_to_equity_pct": float(
            pd.to_numeric(frame.get("broker10_margin_to_equity_pct", 0.0), errors="coerce").fillna(0.0).max()
        ),
        "equity_rebuild_max_abs_diff": float((equity - rebuilt_equity).abs().max()),
        "daily_net_pnl_sum": float(net_pnl.sum()),
    }


def _load_minute() -> pd.DataFrame:
    data = pd.read_csv(s861.FULL_MINUTE_BARS_PATH, encoding="utf-8-sig")
    data["bar_datetime"] = pd.to_datetime(data["bar_datetime"], errors="coerce")
    data["bar_date"] = pd.to_datetime(data.get("bar_date", data["bar_datetime"]), errors="coerce").dt.normalize()
    for column in ["open", "high", "low", "close", "volume"]:
        data[column] = pd.to_numeric(data.get(column), errors="coerce")
    return data.dropna(subset=["vt_symbol", "bar_datetime", "bar_date", "open", "high", "low", "close"]).copy()


def _same_reentry_bar_audit(events: pd.DataFrame, minute: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    minute_key = minute.copy()
    minute_key["key_time"] = minute_key["bar_datetime"].dt.floor("min")
    bar_map = {
        (str(row.vt_symbol), pd.Timestamp(row.key_time)): row
        for row in minute_key.itertuples(index=False)
    }
    rows: list[dict[str, Any]] = []
    for event in events.itertuples(index=False):
        reentry_time = pd.to_datetime(getattr(event, "reentry_time", ""), errors="coerce")
        if pd.isna(reentry_time):
            continue
        bar = bar_map.get((str(event.vt_symbol), pd.Timestamp(reentry_time).floor("min")))
        if bar is None:
            rows.append(
                {
                    "trade_id": str(event.trade_id),
                    "vt_symbol": str(event.vt_symbol),
                    "direction": _normal_direction(event.direction),
                    "reentry_time": str(event.reentry_time),
                    "bar_found": 0,
                    "same_reentry_bar_stop_hit": 0,
                    "current_final_state": str(event.final_state),
                }
            )
            continue
        direction = _normal_direction(event.direction)
        stop_price = float(event.stop_price)
        stop_hit = float(bar.low) <= stop_price if direction == "long" else float(bar.high) >= stop_price
        threshold_observed = (
            float(bar.low) <= float(event.entry_price) <= float(bar.high)
        )
        rows.append(
            {
                "trade_id": str(event.trade_id),
                "vt_symbol": str(event.vt_symbol),
                "direction": direction,
                "reentry_time": pd.Timestamp(reentry_time).isoformat(),
                "bar_found": 1,
                "bar_open": float(bar.open),
                "bar_high": float(bar.high),
                "bar_low": float(bar.low),
                "bar_close": float(bar.close),
                "entry_price": float(event.entry_price),
                "stop_price": stop_price,
                "reentry_threshold_observed_inside_bar": int(threshold_observed),
                "same_reentry_bar_stop_hit": int(stop_hit),
                "current_retry_failed": int(event.retry_failed),
                "current_retry_failed_time": str(event.retry_failed_time),
                "current_final_state": str(event.final_state),
                "volume": float(event.volume),
            }
        )
    return pd.DataFrame(rows)


class QmtRollPortfolioStrategyStage217ConservativeSameBar(
    s847.QmtRollPortfolioStrategyStage847C9StopRetry
):
    """Diagnostic only: a retry bar touching entry and stop is closed conservatively on that bar."""

    def _stage847_stop_retry_event_after_open_trade(self, trade):
        event = super()._stage847_stop_retry_event_after_open_trade(trade)
        if not event or int(event.get("reentry_bar_index", -1)) < 0:
            return event
        bars = self.stage827_minute_by_symbol.get(str(trade.vt_symbol), pd.DataFrame())
        trade_date = s847.s827._normalize_date(trade.datetime)
        entry_day = bars[bars["bar_date"].eq(trade_date)].copy().reset_index(drop=True)
        reentry_idx = int(event["reentry_bar_index"])
        if reentry_idx < 0 or reentry_idx >= len(entry_day):
            return event
        bar = entry_day.iloc[reentry_idx]
        direction = str(event["direction"])
        stop_price = float(event["stop_price"])
        same_bar_stop = float(bar["low"]) <= stop_price if direction == "long" else float(bar["high"]) >= stop_price
        if not same_bar_stop:
            return event

        reentry_time = str(event["reentry_time"])
        sequence = event.get("synthetic_trades")
        if not isinstance(sequence, list):
            sequence = []
            event["synthetic_trades"] = sequence

        if str(event.get("final_state")) == "open_after_reentry":
            state = self._find_state_by_contract(trade.vt_symbol)
            if state is not None and state.layers:
                self._close_all_layers_and_set_flat_target(
                    state,
                    stop_price,
                    execution_price_override=stop_price,
                    exit_reason="stage217_conservative_same_reentry_bar_stop",
                )
            sequence.append(
                {
                    "action": "close",
                    "source": "stage217_conservative_same_reentry_bar_stop",
                    "price": stop_price,
                    "volume": int(event["volume"]),
                    "time": reentry_time,
                }
            )
        elif str(event.get("final_state")) == "flat_retry_failed" and sequence:
            sequence[-1]["time"] = reentry_time
            sequence[-1]["source"] = "stage217_conservative_same_reentry_bar_stop"

        event["retry_failed"] = 1
        event["retry_failed_time"] = reentry_time
        event["retry_failed_bar_index"] = reentry_idx
        event["final_state"] = "flat_retry_failed"
        event["final_exit_price"] = stop_price
        event["exit_reason"] = "stage217_conservative_same_reentry_bar_stop"
        event["stage217_same_reentry_bar_stop"] = 1
        return event


class QmtRollPortfolioStrategyStage217GapAwareFill(
    s847.QmtRollPortfolioStrategyStage847C9StopRetry
):
    """Diagnostic only: threshold fills use the minute open when already beyond the trigger."""

    def _stage847_stop_retry_event_after_open_trade(self, trade):
        event = super()._stage847_stop_retry_event_after_open_trade(trade)
        if not event:
            return event
        bars = self.stage827_minute_by_symbol.get(str(trade.vt_symbol), pd.DataFrame())
        trade_date = s847.s827._normalize_date(trade.datetime)
        entry_day = bars[bars["bar_date"].eq(trade_date)].copy().reset_index(drop=True)
        sequence = event.get("synthetic_trades")
        if entry_day.empty or not isinstance(sequence, list):
            return event

        direction = str(event["direction"])
        specs = [
            ("close", int(event.get("first_stop_bar_index", -1))),
            ("open", int(event.get("reentry_bar_index", -1))),
            ("close", int(event.get("retry_failed_bar_index", -1))),
        ]
        adjusted = 0
        for item, (expected_action, bar_index) in zip(sequence, specs, strict=False):
            if str(item.get("action")) != expected_action or bar_index < 0 or bar_index >= len(entry_day):
                continue
            threshold = float(item["price"])
            minute_open = float(entry_day.iloc[bar_index]["open"])
            if expected_action == "close":
                execution_price = min(threshold, minute_open) if direction == "long" else max(threshold, minute_open)
            else:
                execution_price = max(threshold, minute_open) if direction == "long" else min(threshold, minute_open)
            if abs(execution_price - threshold) > 1e-12:
                item["price"] = execution_price
                item["source"] = f"stage217_gap_aware_{item.get('source', expected_action)}"
                adjusted += 1
        event["stage217_gap_aware_adjusted_trade_count"] = adjusted
        if sequence and str(sequence[-1].get("action")) == "close":
            event["final_exit_price"] = float(sequence[-1]["price"])
        return event


def _run_with_strategy(metadata: dict[str, Any], strategy_cls: type) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], Any]:
    original_start = s847.START
    original_end = s847.END
    original_minute_by_symbol = s847.s827._GLOBAL_MINUTE_BY_SYMBOL
    s901._ensure_c9_minute_bars(metadata)
    try:
        s847.START = ANALYSIS_START
        s847.END = ANALYSIS_END
        profile = s847._c9_profile(metadata)
        spec = profile["spec"]
        capital = replace(
            spec.capital,
            variant=f"{OFFICIAL_LIVE_PROFILE_NAME}_stage217_diagnostic",
            label=f"{OFFICIAL_LIVE_CAPITAL_LABEL} {OFFICIAL_LIVE_ALIAS} Stage217 diagnostic audit",
            account_capital=OFFICIAL_LIVE_CAPITAL,
            c3_capital=OFFICIAL_LIVE_CAPITAL,
            note=f"{spec.capital.note} | Stage217 diagnostic counterfactual; no official configuration change.",
        )
        live_profile = dict(profile)
        live_profile["profile"] = f"{OFFICIAL_LIVE_PROFILE_NAME}_stage217_diagnostic"
        live_profile["strategy_cls"] = strategy_cls
        live_profile["spec"] = replace(
            spec,
            capital=capital,
            overrides={**spec.overrides, **build_official_live_strategy_overrides()},
            profile=live_profile["profile"],
        )
        combined, frames = s847._run_profile(live_profile, metadata)
        return combined, frames, live_profile["spec"]
    finally:
        s847.START = original_start
        s847.END = original_end
        s847.s827._GLOBAL_MINUTE_BY_SYMBOL = original_minute_by_symbol


def _input_manifest(minute: pd.DataFrame) -> pd.DataFrame:
    paths = [
        PROJECT_DIR / "qmt_roll_official_live_config.py",
        PROJECT_DIR / "qmt_roll_official_candidate_stage847_c9_config.py",
        PROJECT_DIR / "analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine.py",
        PROJECT_DIR / "analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow.py",
        s861.FULL_MINUTE_BARS_PATH,
        OFFICIAL_LIVE_AI_ELIGIBILITY_PATH,
        ALL_FUTURES_MAPPING_PATH,
        EXPECTED_DATABASE_PATH,
    ]
    rows: list[dict[str, Any]] = []
    for path in paths:
        rows.append(
            {
                "path": str(path),
                "exists": int(path.exists()),
                "size_bytes": int(path.stat().st_size) if path.exists() else 0,
                "mtime": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds") if path.exists() else "",
                "sha256": _sha256(path) if path.exists() else "",
            }
        )
    rows.append(
        {
            "path": "minute_frame_semantics",
            "exists": 1,
            "size_bytes": int(len(minute)),
            "mtime": f"{minute['bar_datetime'].min()} -> {minute['bar_datetime'].max()}",
            "sha256": f"symbols={minute['vt_symbol'].nunique()}; duplicates={minute.duplicated(['vt_symbol', 'bar_datetime']).sum()}",
        }
    )
    return pd.DataFrame(rows)


def _check_row(check_id: str, status: str, severity: str, value: Any, detail: str) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "status": status,
        "severity": severity,
        "value": value,
        "detail": detail,
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[stage217] baseline {ANALYSIS_START.date()} -> {ANALYSIS_END.date()} {OFFICIAL_LIVE_VERSION}", flush=True)
    metadata = s901.s513._metadata()
    baseline, frames, _spec = s901._run_live_c9(metadata, ANALYSIS_START, ANALYSIS_END)
    baseline_metrics = _metrics(baseline)
    minute = _load_minute()

    trades = frames.get("trades", pd.DataFrame()).copy()
    entry_risk = frames.get("entry_risk", pd.DataFrame()).copy()
    entry_candidates = frames.get("entry_candidates", pd.DataFrame()).copy()
    intraday_events = frames.get("intraday_events", pd.DataFrame()).copy()
    stop_events = frames.get("stop_retry_events", pd.DataFrame()).copy()

    original_opens = trades.copy()
    if not original_opens.empty:
        original_opens["offset_norm"] = original_opens["offset"].map(_normal_offset)
        original_opens["open_date"] = original_opens["datetime"].map(_normal_date)
        original_opens = original_opens[
            original_opens["offset_norm"].eq("open")
            & ~original_opens["order_id"].astype(str).str.contains("stage847_c9", na=False)
        ].copy()
    coverage_keys = set(zip(minute["vt_symbol"].astype(str), minute["bar_date"], strict=False))
    if not original_opens.empty:
        original_opens["minute_entry_day_covered"] = [
            int((str(row.vt_symbol), row.open_date) in coverage_keys)
            for row in original_opens.itertuples(index=False)
        ]
    missing_opens = original_opens[original_opens.get("minute_entry_day_covered", 0).eq(0)].copy() if not original_opens.empty else pd.DataFrame()
    coverage_by_year = pd.DataFrame()
    if not original_opens.empty:
        original_opens["open_year"] = pd.to_datetime(original_opens["open_date"], errors="coerce").dt.year
        coverage_by_year = (
            original_opens.groupby("open_year", dropna=False)["minute_entry_day_covered"]
            .agg(open_count="size", covered_count="sum")
            .reset_index()
        )
        coverage_by_year["missing_count"] = coverage_by_year["open_count"] - coverage_by_year["covered_count"]
        coverage_by_year["coverage_pct"] = coverage_by_year["covered_count"] / coverage_by_year["open_count"] * 100.0

    # Reuse the prior forensic matcher after adapting only the profile label.
    audit_trades = trades.copy()
    audit_entry_risk = entry_risk.copy()
    audit_intraday = intraday_events.copy()
    audit_stop = stop_events.copy()
    for frame in [audit_trades, audit_entry_risk, audit_intraday, audit_stop]:
        if not frame.empty:
            frame["profile"] = s900.C9_ARM
    entry_execution = s900._entry_execution_audit(audit_trades, audit_entry_risk, minute)
    event_price = s900._event_price_audit(audit_intraday, audit_stop, minute)
    same_bar = _same_reentry_bar_audit(stop_events, minute)

    stage859_minute = minute[
        minute.get("minute_source", pd.Series("", index=minute.index)).astype(str).str.contains("stage859", case=False, na=False)
    ].copy()
    stage859_degenerate_zero_volume = stage859_minute[
        stage859_minute["open"].eq(stage859_minute["high"])
        & stage859_minute["high"].eq(stage859_minute["low"])
        & stage859_minute["low"].eq(stage859_minute["close"])
        & pd.to_numeric(stage859_minute["volume"], errors="coerce").fillna(0.0).eq(0.0)
    ].copy()
    stage859_event_count = int(
        event_price.get("minute_source", pd.Series("", index=event_price.index))
        .astype(str).str.contains("stage859", case=False, na=False).sum()
    ) if not event_price.empty else 0
    stage859_initial_stop_event_count = int(
        (
            event_price.get("minute_source", pd.Series("", index=event_price.index)).astype(str).str.contains("stage859", case=False, na=False)
            & event_price.get("event_type", pd.Series("", index=event_price.index)).isin(["c9_first_05r_stop", "c9_inherited_c2_1r_stop"])
        ).sum()
    ) if not event_price.empty else 0

    same_bar_hits = same_bar[same_bar.get("same_reentry_bar_stop_hit", 0).eq(1)].copy() if not same_bar.empty else pd.DataFrame()
    optimistic_open_hits = same_bar_hits[same_bar_hits.get("current_final_state", "").eq("open_after_reentry")].copy() if not same_bar_hits.empty else pd.DataFrame()
    night_opens = entry_execution[
        entry_execution.get("proxy_source", pd.Series("", index=entry_execution.index)).astype(str).str.contains("night", case=False, na=False)
    ].copy() if not entry_execution.empty else pd.DataFrame()
    fallback_opens = entry_execution[
        entry_execution.get("fallback_execution", pd.Series(0, index=entry_execution.index)).eq(1)
    ].copy() if not entry_execution.empty else pd.DataFrame()
    late_natural_date_events = pd.DataFrame()
    raw_night_late_retry_events = pd.DataFrame()
    if not event_price.empty:
        late_natural_date_events = event_price.copy()
        late_natural_date_events["event_time_ts"] = pd.to_datetime(late_natural_date_events["event_time"], errors="coerce")
        late_natural_date_events = late_natural_date_events[late_natural_date_events["event_time_ts"].dt.hour.ge(21)].copy()
        late_natural_date_events = late_natural_date_events.merge(
            entry_execution[["trade_id", "proxy_source", "fallback_execution"]],
            left_on="event_id",
            right_on="trade_id",
            how="left",
        )
        raw_night_late_retry_events = late_natural_date_events[
            late_natural_date_events["event_type"].astype(str).eq("c9_retry_failed_stop")
            & late_natural_date_events["proxy_source"].astype(str).str.contains("raw_night", case=False, na=False)
        ].copy()

    prior_metrics: dict[str, Any] = {}
    if STAGE153_SUMMARY_PATH.exists():
        prior = pd.read_csv(STAGE153_SUMMARY_PATH, encoding="utf-8-sig")
        prior = prior[prior["requested_start"].astype(str).eq("2018-01-01")]
        if not prior.empty:
            prior_metrics = prior.iloc[0].to_dict()

    ai_future_count = 0
    ai_equal_count = 0
    if not entry_candidates.empty and "ai_product_pool_signal_date" in entry_candidates.columns:
        candidate_date = pd.to_datetime(entry_candidates["date"], errors="coerce").dt.normalize()
        ai_date = pd.to_datetime(entry_candidates["ai_product_pool_signal_date"], errors="coerce").dt.normalize()
        ai_future_count = int((ai_date > candidate_date).fillna(False).sum())
        ai_equal_count = int((ai_date == candidate_date).fillna(False).sum())

    checks: list[dict[str, Any]] = []
    checks.append(_check_row(
        "official_identity",
        "PASS" if OFFICIAL_LIVE_VERSION.endswith("15w_stage819_05r_stop_retry_once") else "FAIL",
        "P0",
        OFFICIAL_LIVE_VERSION,
        "现场解析正式配置；资金15万、C2、broker10、0.5R和retry-once均由live override启用。",
    ))
    checks.append(_check_row(
        "equity_accounting_rebuild",
        "PASS" if baseline_metrics["equity_rebuild_max_abs_diff"] <= 1e-6 else "FAIL",
        "P0",
        baseline_metrics["equity_rebuild_max_abs_diff"],
        "独立以15万本金加逐日net_pnl累加，核对account_equity。",
    ))
    checks.append(_check_row(
        "trade_count_matches_trade_ledger",
        "PASS" if abs(baseline_metrics["total_trade_count"] - len(trades)) <= 1e-9 else "FAIL",
        "P0",
        f"daily={baseline_metrics['total_trade_count']} ledger={len(trades)}",
        "逐日trade_count与成交账本行数核对。",
    ))
    checks.append(_check_row(
        "entry_day_minute_coverage",
        "PASS" if len(missing_opens) == 0 else "FAIL",
        "P0",
        f"covered={len(original_opens)-len(missing_opens)}/{len(original_opens)} missing={len(missing_opens)} minute_max={minute['bar_datetime'].max()}",
        "缺分钟时Stage847/C2直接return None，止损逻辑静默失效；全周期结果不能宣称每笔均执行0.5R。",
    ))
    checks.append(_check_row(
        "stage859_incomplete_minute_bars",
        "FAIL" if len(stage859_degenerate_zero_volume) else "PASS",
        "P0",
        f"invalid={len(stage859_degenerate_zero_volume)}/{len(stage859_minute)}; dependent_events={stage859_event_count}; initial_stop_events={stage859_initial_stop_event_count}",
        "Stage859在TqSdk分钟datetime变化时立即保存iloc[-1]新生K；当前该源全部O=H=L=C且volume=0，不能代表完成分钟。",
    ))
    checks.append(_check_row(
        "same_reentry_bar_stop_semantics",
        "PASS" if len(same_bar_hits) == 0 else ("FAIL" if len(optimistic_open_hits) else "WARN"),
        "P0" if len(optimistic_open_hits) else "P1",
        f"same_bar_hits={len(same_bar_hits)} optimistic_open_after_reentry={len(optimistic_open_hits)}",
        "当前代码从reentry_idx+1才检查二次止损；本样本有一笔被延迟到后续分钟平仓，但最终仍为flat，未改变头部指标。",
    ))
    checks.append(_check_row(
        "night_session_entry_day_semantics",
        "FAIL" if len(raw_night_late_retry_events) else ("WARN" if len(night_opens) else "PASS"),
        "P0" if len(raw_night_late_retry_events) else "P1",
        f"night_proxy_opens={len(night_opens)} fill_date_21plus_events={len(late_natural_date_events)} unique_opens={late_natural_date_events['event_id'].nunique() if not late_natural_date_events.empty else 0} raw_night_late_retry={len(raw_night_late_retry_events)}",
        "Stage847按自然日而非交易日扫描：漏掉signal_date 21点后的入场夜盘，并错误纳入fill_date 21点后的下一交易夜盘；已有两笔raw-night重进仓被错误止损。",
    ))
    checks.append(_check_row(
        "fallback_entry_execution",
        "WARN" if len(fallback_opens) else "PASS",
        "P1",
        len(fallback_opens),
        "fallback_daily_next_open不是同源分钟开盘代理，成交真实性较弱。",
    ))
    checks.append(_check_row(
        "ai_pool_point_in_time",
        "PASS" if ai_future_count == 0 and ai_equal_count == 0 else "FAIL",
        "P0",
        f"future={ai_future_count} equal_day={ai_equal_count}",
        "候选快照中AI signal_date必须严格早于决策日；源码采用searchsorted(side=left)-1。",
    ))
    event_missing = int((event_price.get("minute_bar_found", pd.Series(dtype=int)) == 0).sum()) if not event_price.empty else 0
    trigger_failed = int((event_price.get("event_trigger_condition_met", pd.Series(dtype=int)) == 0).sum()) if not event_price.empty else 0
    checks.append(_check_row(
        "recorded_event_price_trigger",
        "PASS" if event_missing == 0 and trigger_failed == 0 else "FAIL",
        "P1",
        f"events={len(event_price)} missing_bar={event_missing} trigger_failed={trigger_failed}",
        "只验证已经被记录的事件确实被对应分钟OHLC触发；不能替代缺失事件审计。",
    ))
    threshold_not_observed = int(event_price.get("threshold_not_observed_inside_bar", pd.Series(dtype=int)).fillna(0).sum()) if not event_price.empty else 0
    checks.append(_check_row(
        "threshold_fill_execution_realism",
        "FAIL" if threshold_not_observed else "PASS",
        "P0",
        f"threshold_not_observed={threshold_not_observed}/{len(event_price)}",
        "Stage847在OHLC越过阈值时一律按理论stop/entry阈值成交；若分钟开盘已跳过阈值，会得到不可成交的乐观价格。",
    ))
    nonzero_rate_count = int(sum(float(value) != 0.0 for value in metadata["rates"].values()))
    checks.append(_check_row(
        "commission_cost_model",
        "WARN" if nonzero_rate_count == 0 else "PASS",
        "P1",
        f"nonzero_rate_contracts={nonzero_rate_count}/{len(metadata['rates'])}; total_commission={baseline_metrics['total_commission']:.2f}",
        "正式回测已计滑点，但全部合约手续费率为0；因此净值不是完整交易成本后的净收益。",
    ))
    if prior_metrics:
        equity_delta = baseline_metrics["end_equity"] - float(prior_metrics["end_equity"])
        trade_delta = baseline_metrics["total_trade_count"] - float(prior_metrics["total_trade_count"])
        checks.append(_check_row(
            "historical_result_reproducibility",
            "FAIL" if abs(equity_delta) > 1e-6 or abs(trade_delta) > 1e-9 else "PASS",
            "P0",
            f"stage153_end={float(prior_metrics['end_equity']):.2f} current_end={baseline_metrics['end_equity']:.2f} delta={equity_delta:.2f}; trade_delta={trade_delta:.0f}",
            "同版本、同窗口、同本金重跑已漂移；Stage153之后代码、Stage182 combined AI池、mapping和数据库均继续变化，旧结果未绑定完整输入hash，不能单归因某一文件。",
        ))

    counter_metrics: dict[str, Any] | None = None
    if len(optimistic_open_hits) > 0:
        print(f"[stage217] running conservative same-reentry-bar counterfactual hits={len(optimistic_open_hits)}", flush=True)
        counter_curve, _counter_frames, _counter_spec = _run_with_strategy(
            metadata,
            QmtRollPortfolioStrategyStage217ConservativeSameBar,
        )
        counter_metrics = _metrics(counter_curve)
        checks.append(_check_row(
            "same_bar_counterfactual_materiality",
            "FAIL" if abs(counter_metrics["end_equity"] - baseline_metrics["end_equity"]) > 1.0 else "PASS",
            "P0",
            f"end_equity_delta={counter_metrics['end_equity']-baseline_metrics['end_equity']:.2f}; return_delta_pp={counter_metrics['total_return_pct']-baseline_metrics['total_return_pct']:.6f}; dd_delta_pp={counter_metrics['max_dd_pct']-baseline_metrics['max_dd_pct']:.6f}",
            "诊断反事实仅把重进K同根触止损按保守顺序处理，不修改0.5R、重试次数、AI池或其他参数。",
        ))

    gap_fill_metrics: dict[str, Any] | None = None
    if threshold_not_observed > 0:
        print(f"[stage217] running gap-aware threshold-fill counterfactual events={threshold_not_observed}", flush=True)
        gap_curve, _gap_frames, _gap_spec = _run_with_strategy(
            metadata,
            QmtRollPortfolioStrategyStage217GapAwareFill,
        )
        gap_fill_metrics = _metrics(gap_curve)
        checks.append(_check_row(
            "gap_aware_fill_counterfactual_materiality",
            "FAIL" if abs(gap_fill_metrics["end_equity"] - baseline_metrics["end_equity"]) > 1.0 else "PASS",
            "P0",
            f"end_equity_delta={gap_fill_metrics['end_equity']-baseline_metrics['end_equity']:.2f}; return_delta_pp={gap_fill_metrics['total_return_pct']-baseline_metrics['total_return_pct']:.6f}; dd_delta_pp={gap_fill_metrics['max_dd_pct']-baseline_metrics['max_dd_pct']:.6f}",
            "诊断反事实仅修Stage847阈值成交，不修C2两笔越阈值、Stage859未完成K事件顺序、缺分钟、交易日错位和手续费；不是修正后真值。",
        ))

    summary_rows = [
        {"arm": "current_official_baseline", **baseline_metrics},
    ]
    if counter_metrics is not None:
        summary_rows.append({"arm": "diagnostic_conservative_same_reentry_bar", **counter_metrics})
    if gap_fill_metrics is not None:
        summary_rows.append({"arm": "diagnostic_gap_aware_threshold_fill", **gap_fill_metrics})
    summary = pd.DataFrame(summary_rows)
    checks_frame = pd.DataFrame(checks)
    manifest = _input_manifest(minute)

    hard_fail = checks_frame[checks_frame["severity"].eq("P0") & checks_frame["status"].eq("FAIL")]
    decision_label = "current_official_full_cycle_not_verified_has_p0_integrity_failures" if len(hard_fail) else "current_official_full_cycle_verified_no_p0_integrity_failure"
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "analysis_start": ANALYSIS_START.date().isoformat(),
        "analysis_end": ANALYSIS_END.date().isoformat(),
        "baseline_metrics": baseline_metrics,
        "counterfactual_metrics": counter_metrics,
        "gap_aware_fill_metrics": gap_fill_metrics,
        "stage153_prior_metrics": prior_metrics,
        "original_open_count": int(len(original_opens)),
        "missing_entry_day_minute_open_count": int(len(missing_opens)),
        "minute_max_datetime": pd.Timestamp(minute["bar_datetime"].max()).isoformat(),
        "stop_retry_event_count": int(len(stop_events)),
        "same_reentry_bar_stop_hit_count": int(len(same_bar_hits)),
        "optimistic_open_after_reentry_count": int(len(optimistic_open_hits)),
        "night_proxy_open_count": int(len(night_opens)),
        "fallback_open_count": int(len(fallback_opens)),
        "stage859_invalid_minute_count": int(len(stage859_degenerate_zero_volume)),
        "stage859_dependent_event_count": stage859_event_count,
        "fill_date_21plus_event_count": int(len(late_natural_date_events)),
        "raw_night_late_retry_failed_event_count": int(len(raw_night_late_retry_events)),
        "threshold_not_observed_event_count": threshold_not_observed,
        "commission_nonzero_rate_contract_count": nonzero_rate_count,
        "p0_fail_count": int(len(hard_fail)),
        "decision": decision_label,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "overfit_reflection_before": "否。固定当前正式配置和既有全周期窗口，只做复现与bug审计，不调参数。",
        "overfit_reflection_after": "否。反事实只执行预先声明的同根K顺序与gap-aware成交诊断，用于测bug量级，不能据此优化R倍数或重试次数。",
        "continue_value_before": "是。0.5R状态机一旦fail-open或同根顺序乐观，会直接影响正式回测可信度。",
        "continue_value_after": "是。应先补齐分钟数据并修复/冻结成交语义，再重跑正式全周期；在此之前继续调alpha没有价值。",
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "checks": str(CHECKS_PATH),
            "daily": str(DAILY_PATH),
            "trades": str(TRADES_PATH),
            "entry_execution": str(ENTRY_EXECUTION_PATH),
            "stop_retry_events": str(STOP_RETRY_EVENTS_PATH),
            "same_bar_audit": str(SAME_BAR_PATH),
            "event_price_audit": str(EVENT_PRICE_PATH),
            "entry_day_coverage_by_year": str(COVERAGE_PATH),
            "input_manifest": str(INPUT_MANIFEST_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    checks_frame.to_csv(CHECKS_PATH, index=False, encoding="utf-8-sig")
    baseline.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    trades.to_csv(TRADES_PATH, index=False, encoding="utf-8-sig")
    entry_execution.to_csv(ENTRY_EXECUTION_PATH, index=False, encoding="utf-8-sig")
    stop_events.to_csv(STOP_RETRY_EVENTS_PATH, index=False, encoding="utf-8-sig")
    same_bar.to_csv(SAME_BAR_PATH, index=False, encoding="utf-8-sig")
    event_price.to_csv(EVENT_PRICE_PATH, index=False, encoding="utf-8-sig")
    coverage_by_year.to_csv(COVERAGE_PATH, index=False, encoding="utf-8-sig")
    manifest.to_csv(INPUT_MANIFEST_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report_lines = [
        "# Stage217 当前正式C9/15万全周期完整性审计",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- 正式版本：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`",
        f"- 窗口：`{ANALYSIS_START.date()}` -> `{ANALYSIS_END.date()}`；资金 `{OFFICIAL_LIVE_CAPITAL:,.0f}`。",
        "- 性质：离线回测、逐笔法证和诊断反事实；不连接CTP、不调用订单API、不修改正式配置。",
        "",
        "## 汇总",
        "",
        _md_table(summary, max_rows=10),
        "",
        "## 完整性检查",
        "",
        _md_table(checks_frame, max_rows=30),
        "",
        "## 缺分钟开仓",
        "",
        _md_table(coverage_by_year, max_rows=20),
        "",
        _md_table(missing_opens[[column for column in ["trade_id", "datetime", "vt_symbol", "direction", "price", "volume", "open_date"] if column in missing_opens.columns]], max_rows=100),
        "",
        "## 重进K同根止损",
        "",
        _md_table(same_bar_hits, max_rows=100),
        "",
        "## 自然日/交易日错位事件",
        "",
        _md_table(late_natural_date_events, max_rows=100),
        "",
        "## 输入清单",
        "",
        _md_table(manifest, max_rows=30),
        "",
        "## 结论",
        "",
        f"- 决策：`{decision_label}`",
        f"- P0失败数：`{len(hard_fail)}`。",
        f"- 当前重跑相对Stage153：期末权益变化 `{baseline_metrics['end_equity']-float(prior_metrics.get('end_equity', baseline_metrics['end_equity'])):,.2f}`，交易数变化 `{baseline_metrics['total_trade_count']-float(prior_metrics.get('total_trade_count', baseline_metrics['total_trade_count'])):.0f}`。",
        "- 汇总账本是否自洽与0.5R成交语义是否可信是两件事；只有两者都通过，才能把全周期收益当作正式真实基准。",
        "- gap-aware反事实只量化已记录Stage847事件的阈值成交影响，不是修正后真值；它没有修复未完成分钟K、缺分钟开仓、交易日边界和手续费。",
        "- 过拟合反思：否；本次不调参。",
        "- 继续价值：是；先补分钟数据、修状态机、同口径重跑，再讨论收益。",
    ]
    REPORT_PATH.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
