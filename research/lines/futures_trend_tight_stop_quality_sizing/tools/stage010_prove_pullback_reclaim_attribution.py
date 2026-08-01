from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any, Mapping

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import stage009_minute_opening_structure_attribution as s009


LINE_ID = "futures_trend_tight_stop_quality_sizing"
STAGE = "Stage010"
MODEL_TAG = "stage010_prove_pullback_reclaim_attribution_v1"
OUTPUT_PREFIX = "tight_stop_quality_stage010"

ROOT = Path(__file__).resolve().parents[4]
LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage010_prove_pullback_reclaim_attribution"
TOOL_PATH = Path(__file__).resolve()
TEST_PATH = LINE_DIR / "tests" / "test_stage010_prove_pullback_reclaim_attribution.py"
PREDECL_PATH = LINE_DIR / "stages" / "20260714_1649_stage010_prove_pullback_reclaim_attribution_predecl.md"
STAGE009_RESULT_PATH = (
    LINE_DIR / "stages" / "20260714_1647_stage009_minute_opening_structure_attribution_result.md"
)

DISCOVERY_EVENTS_PATH = OUT / f"{OUTPUT_PREFIX}_discovery_events_{MODEL_TAG}.csv.gz"
DISCOVERY_CANDIDATES_PATH = OUT / f"{OUTPUT_PREFIX}_discovery_candidates_{MODEL_TAG}.csv"
SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_discovery_summary_{MODEL_TAG}.csv"
YEARLY_PATH = OUT / f"{OUTPUT_PREFIX}_discovery_yearly_{MODEL_TAG}.csv"
STATUS_PATH = OUT / f"{OUTPUT_PREFIX}_status_aggregate_{MODEL_TAG}.csv"
FUTURE_SEAL_PATH = OUT / f"{OUTPUT_PREFIX}_historical_locked_feature_seal_{MODEL_TAG}.json"
INPUT_MANIFEST_PATH = OUT / f"{OUTPUT_PREFIX}_input_manifest_{MODEL_TAG}.csv"
OUTPUT_MANIFEST_PATH = OUT / f"{OUTPUT_PREFIX}_output_manifest_{MODEL_TAG}.csv"
CHART_PATH = OUT / f"{OUTPUT_PREFIX}_discovery_attribution_{MODEL_TAG}.png"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

DISCOVERY_YEARS = {2020, 2021, 2022}
PROOF_R = 0.5
FAIL_R = 0.5
MIN_COMPLETED_MINUTES = 30
MAX_MICRO_RISK_RATIO = 0.5
TWO_R_BREAKEVEN = 1.0 / 3.0

OUTCOME_COLUMNS = (
    "micro_first_touch_1r",
    "micro_first_touch_1r_bar_index",
    "micro_first_touch_1r_time",
    "micro_first_touch_2r",
    "micro_first_touch_2r_bar_index",
    "micro_first_touch_2r_time",
    "return_5m_micro_r",
    "return_15m_micro_r",
    "return_60m_micro_r",
    "baseline_realized_pnl",
    "baseline_r_multiple",
)

FEATURE_SEAL_COLUMNS = (
    "open_trade_id",
    "vt_symbol",
    "product",
    "direction",
    "entry_date",
    "sample_segment",
    "candidate_status",
    "session_start",
    "session_bar_count",
    "planned_entry_price",
    "actual_entry_price",
    "planned_stop_distance",
    "actual_stop_distance",
    "effective_pricetick",
    "pricetick_rule",
    "proof_price",
    "half_r_stop_price",
    "proof_bar_index",
    "proof_time",
    "proof_excursion_actual_r",
    "retest_bar_index",
    "retest_time",
    "retest_depth_actual_r",
    "reclaim_bar_index",
    "reclaim_time",
    "retest_duration_bars",
    "reclaim_close_distance_actual_r",
    "reclaim_directional_body_actual_r",
    "reclaim_close_location",
    "completed_minutes_before_decision",
    "decision_time",
    "counterfactual_entry_bar_index",
    "counterfactual_entry_time",
    "counterfactual_entry_price",
    "structural_stop_price",
    "micro_stop_distance",
    "micro_stop_actual_risk_ratio",
    "feature_future_violation",
)

EXTERNAL_RESEARCH = (
    {
        "source": "Stop Distance, Exit Methodology, and Signal Preservation in Intraday Value Area Breakouts",
        "url": "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6350238",
        "judgment": "浅回踩可优于深回踩，但价格止损可能破坏信号，且前30分钟事件更差；只作为假设和反证先验。",
    },
    {
        "source": "The Significance of Trading Frequency and Stop Loss in Trend Following Strategies",
        "url": "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2349848",
        "judgment": "更高交易频率未显著改善同一趋势模型，普通损失区间的止损价值不明确。",
    },
    {
        "source": "backtesting.py order execution semantics",
        "url": "https://github.com/kernc/backtesting.py/blob/master/backtesting/backtesting.py",
        "judgment": "确认 bar 与下一 bar 开盘市价成交必须分离。",
    },
    {
        "source": "backtesting.py breakout same-bar discussion",
        "url": "https://github.com/kernc/backtesting.py/discussions/1295",
        "judgment": "OHLC 无法恢复同 bar 内触发顺序，必须保守排序。",
    },
    {
        "source": "QuantDinger breakout-retest state-machine example",
        "url": "https://github.com/brokermr810/QuantDinger/blob/main/docs/STRATEGY_DEV_GUIDE_CN.md",
        "judgment": "仅参考状态机表达，不复制其可调参数或收益声明。",
    },
)


def _safe_float(value: Any, default: float = np.nan) -> float:
    return s009._safe_float(value, default=default)


def _json_safe(value: Any) -> Any:
    return s009._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s009._md_table(frame, max_rows=max_rows)


def _blank_result(
    event: Mapping[str, Any],
    data: pd.DataFrame,
    *,
    tick: float,
    pricetick_rule: str,
    proof_price: float,
    half_r_stop_price: float,
) -> dict[str, Any]:
    return {
        "open_trade_id": str(event.get("open_trade_id", "")),
        "vt_symbol": str(event.get("vt_symbol", "")),
        "product": str(event.get("product", "")),
        "direction": str(event.get("direction", "")).lower(),
        "entry_date": pd.Timestamp(event.get("entry_date")).normalize(),
        "sample_segment": str(event.get("sample_segment", "")),
        "candidate_status": "",
        "session_start": pd.Timestamp(data.iloc[0]["bar_datetime"]),
        "session_end": pd.Timestamp(data.iloc[-1]["bar_datetime"]),
        "session_bar_count": int(len(data)),
        "planned_entry_price": _safe_float(event.get("planned_entry_price")),
        "actual_entry_price": _safe_float(event.get("actual_entry_price")),
        "planned_stop_distance": _safe_float(event.get("planned_stop_distance")),
        "actual_stop_distance": _safe_float(event.get("actual_stop_distance")),
        "effective_pricetick": tick,
        "pricetick_rule": pricetick_rule,
        "proof_price": proof_price,
        "half_r_stop_price": half_r_stop_price,
        "proof_bar_index": np.nan,
        "proof_time": pd.NaT,
        "proof_excursion_actual_r": np.nan,
        "retest_bar_index": np.nan,
        "retest_time": pd.NaT,
        "retest_depth_actual_r": np.nan,
        "reclaim_bar_index": np.nan,
        "reclaim_time": pd.NaT,
        "retest_duration_bars": np.nan,
        "reclaim_close_distance_actual_r": np.nan,
        "reclaim_directional_body_actual_r": np.nan,
        "reclaim_close_location": np.nan,
        "completed_minutes_before_decision": np.nan,
        "decision_time": pd.NaT,
        "counterfactual_entry_bar_index": np.nan,
        "counterfactual_entry_time": pd.NaT,
        "counterfactual_entry_price": np.nan,
        "structural_stop_price": np.nan,
        "micro_stop_distance": np.nan,
        "micro_stop_actual_risk_ratio": np.nan,
        "feature_future_violation": 0,
        "micro_first_touch_1r": "",
        "micro_first_touch_1r_bar_index": np.nan,
        "micro_first_touch_1r_time": pd.NaT,
        "micro_first_touch_2r": "",
        "micro_first_touch_2r_bar_index": np.nan,
        "micro_first_touch_2r_time": pd.NaT,
        "return_5m_micro_r": np.nan,
        "return_15m_micro_r": np.nan,
        "return_60m_micro_r": np.nan,
        "baseline_realized_pnl": _safe_float(event.get("baseline_realized_pnl")),
        "baseline_r_multiple": _safe_float(event.get("baseline_r_multiple")),
    }


def _stop_hit(row: Any, direction: str, price: float) -> bool:
    return float(row.low) <= price if direction == "long" else float(row.high) >= price


def _proof_hit(row: Any, direction: str, price: float) -> bool:
    return float(row.high) >= price if direction == "long" else float(row.low) <= price


def _retest_hit(row: Any, direction: str, planned_entry: float) -> bool:
    return float(row.low) <= planned_entry if direction == "long" else float(row.high) >= planned_entry


def _reclaim_hit(row: Any, direction: str, planned_entry: float) -> bool:
    return float(row.close) > planned_entry if direction == "long" else float(row.close) < planned_entry


def _entry_holds_reclaim(entry_price: float, direction: str, planned_entry: float) -> bool:
    return entry_price > planned_entry if direction == "long" else entry_price < planned_entry


def compute_pullback_reclaim_event(
    event: Mapping[str, Any],
    session: pd.DataFrame,
    *,
    pricetick: float,
    pricetick_rule: str,
    compute_outcomes: bool,
) -> dict[str, Any]:
    data = s009._validate_session(session)
    direction = str(event.get("direction", "")).lower()
    if direction not in {"long", "short"}:
        raise ValueError(f"unsupported direction: {direction}")
    sign = 1.0 if direction == "long" else -1.0
    tick = _safe_float(pricetick)
    actual_entry = _safe_float(event.get("actual_entry_price"))
    planned_entry = _safe_float(event.get("planned_entry_price"))
    actual_risk = _safe_float(event.get("actual_stop_distance"))
    planned_risk = _safe_float(event.get("planned_stop_distance"))
    if tick <= 0 or actual_entry <= 0 or planned_entry <= 0 or actual_risk <= 0 or planned_risk <= 0:
        raise ValueError("invalid tick or entry risk geometry")

    proof_price = actual_entry + sign * PROOF_R * actual_risk
    half_r_stop_price = actual_entry - sign * FAIL_R * actual_risk
    result = _blank_result(
        event,
        data,
        tick=tick,
        pricetick_rule=pricetick_rule,
        proof_price=proof_price,
        half_r_stop_price=half_r_stop_price,
    )

    proof_index: int | None = None
    for index, row in enumerate(data.itertuples(index=False)):
        if _stop_hit(row, direction, half_r_stop_price):
            result["candidate_status"] = "prior_half_r_stop"
            return result
        if _proof_hit(row, direction, proof_price):
            proof_index = index
            result["proof_bar_index"] = index
            result["proof_time"] = pd.Timestamp(row.bar_datetime)
            proof_extreme = float(row.high) if direction == "long" else float(row.low)
            result["proof_excursion_actual_r"] = sign * (proof_extreme - actual_entry) / actual_risk
            break
    if proof_index is None:
        result["candidate_status"] = "no_proof"
        return result

    retest_index: int | None = None
    adverse_extreme = np.nan
    for index in range(proof_index + 1, len(data)):
        row = data.iloc[index]
        row_view = next(data.iloc[index : index + 1].itertuples(index=False))
        if _stop_hit(row_view, direction, half_r_stop_price):
            result["candidate_status"] = "prior_half_r_stop"
            return result

        if retest_index is None:
            if not _retest_hit(row_view, direction, planned_entry):
                continue
            retest_index = index
            adverse_extreme = float(row["low"] if direction == "long" else row["high"])
            result["retest_bar_index"] = index
            result["retest_time"] = pd.Timestamp(row["bar_datetime"])
        else:
            current_extreme = float(row["low"] if direction == "long" else row["high"])
            adverse_extreme = min(adverse_extreme, current_extreme) if direction == "long" else max(
                adverse_extreme, current_extreme
            )

        depth = max(0.0, planned_entry - adverse_extreme) if direction == "long" else max(
            0.0, adverse_extreme - planned_entry
        )
        result["retest_depth_actual_r"] = depth / actual_risk
        if not _reclaim_hit(row_view, direction, planned_entry):
            continue

        result["reclaim_bar_index"] = index
        result["reclaim_time"] = pd.Timestamp(row["bar_datetime"])
        result["decision_time"] = pd.Timestamp(row["bar_datetime"])
        result["retest_duration_bars"] = int(index - retest_index + 1)
        result["completed_minutes_before_decision"] = int(index + 1)
        result["reclaim_close_distance_actual_r"] = sign * (float(row["close"]) - planned_entry) / actual_risk
        result["reclaim_directional_body_actual_r"] = sign * (
            float(row["close"]) - float(row["open"])
        ) / actual_risk
        bar_range = float(row["high"] - row["low"])
        result["reclaim_close_location"] = (
            (float(row["close"]) - float(row["low"])) / bar_range
            if direction == "long" and bar_range > 0
            else (float(row["high"]) - float(row["close"])) / bar_range
            if direction == "short" and bar_range > 0
            else 0.5
        )

        if index + 1 < MIN_COMPLETED_MINUTES:
            result["candidate_status"] = "early_reclaim"
            return result
        if index + 1 >= len(data):
            result["candidate_status"] = "no_next_bar"
            return result

        entry_index = index + 1
        entry_row = data.iloc[entry_index]
        entry_price = float(entry_row["open"])
        structural_stop = adverse_extreme - tick if direction == "long" else adverse_extreme + tick
        micro_risk = sign * (entry_price - structural_stop)
        result["counterfactual_entry_bar_index"] = entry_index
        result["counterfactual_entry_time"] = pd.Timestamp(entry_row["bar_datetime"])
        result["counterfactual_entry_price"] = entry_price
        result["structural_stop_price"] = structural_stop
        result["micro_stop_distance"] = micro_risk
        result["micro_stop_actual_risk_ratio"] = micro_risk / actual_risk
        result["feature_future_violation"] = int(
            pd.Timestamp(result["reclaim_time"]) >= pd.Timestamp(result["counterfactual_entry_time"])
        )

        if not _entry_holds_reclaim(entry_price, direction, planned_entry):
            result["candidate_status"] = "next_open_lost_reclaim"
            return result
        if micro_risk < tick - 1e-12:
            result["candidate_status"] = "gap_beyond_stop"
            return result
        if micro_risk > MAX_MICRO_RISK_RATIO * actual_risk + 1e-12:
            result["candidate_status"] = "micro_stop_too_wide"
            return result

        result["candidate_status"] = "candidate"
        if not compute_outcomes:
            return result
        after = data.iloc[entry_index:].reset_index(drop=True)
        first1, first1_index, first1_time = s009._first_touch(
            after,
            direction=direction,
            entry_price=entry_price,
            risk_distance=micro_risk,
            reward_multiple=1.0,
        )
        first2, first2_index, first2_time = s009._first_touch(
            after,
            direction=direction,
            entry_price=entry_price,
            risk_distance=micro_risk,
            reward_multiple=2.0,
        )
        result.update(
            {
                "micro_first_touch_1r": first1,
                "micro_first_touch_1r_bar_index": first1_index,
                "micro_first_touch_1r_time": first1_time,
                "micro_first_touch_2r": first2,
                "micro_first_touch_2r_bar_index": first2_index,
                "micro_first_touch_2r_time": first2_time,
                "return_5m_micro_r": s009._window_return_micro_r(
                    after,
                    direction=direction,
                    entry_price=entry_price,
                    risk_distance=micro_risk,
                    count=5,
                ),
                "return_15m_micro_r": s009._window_return_micro_r(
                    after,
                    direction=direction,
                    entry_price=entry_price,
                    risk_distance=micro_risk,
                    count=15,
                ),
                "return_60m_micro_r": s009._window_return_micro_r(
                    after,
                    direction=direction,
                    entry_price=entry_price,
                    risk_distance=micro_risk,
                    count=60,
                ),
            }
        )
        return result

    result["candidate_status"] = "no_retest" if retest_index is None else "no_reclaim"
    return result


def partition_outputs(events: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    if "sample_segment" not in events.columns:
        raise ValueError("Stage010 events missing sample_segment")
    discovery = events.loc[events["sample_segment"].astype(str).eq("discovery")].copy()
    future = events.loc[~events["sample_segment"].astype(str).eq("discovery")].copy()
    feature_only = future.reindex(columns=FEATURE_SEAL_COLUMNS)
    future_outcomes_computed = False
    for column in ("micro_first_touch_1r", "micro_first_touch_2r"):
        if column in future.columns and future[column].astype(str).isin(["target_first", "stop_first", "no_touch"]).any():
            future_outcomes_computed = True
    seal = {
        "row_count": int(len(feature_only)),
        "feature_only_sha256": s009.s008._frame_sha256(feature_only),
        "feature_hash_contract": s009.s008.FRAME_HASH_CONTRACT,
        "segments": feature_only["sample_segment"].value_counts().sort_index().to_dict(),
        "candidate_status_counts": feature_only["candidate_status"].value_counts().sort_index().to_dict(),
        "feature_columns": list(FEATURE_SEAL_COLUMNS),
        "feature_allowlist_enforced": True,
        "future_row_data_exported": False,
        "future_outcomes_computed": future_outcomes_computed,
        "true_oos_claim": False,
        "purpose": "后段只冻结 Stage010 因果候选特征，不计算或落盘 first-touch 结果。",
    }
    return discovery, seal


def _candidate_yearly(candidates: pd.DataFrame) -> pd.DataFrame:
    if candidates.empty:
        return pd.DataFrame()
    frame = candidates.copy()
    frame["entry_year"] = pd.to_datetime(frame["entry_date"]).dt.year
    rows = []
    for year, group in frame.groupby("entry_year", sort=True):
        rows.append({"entry_year": int(year), **s009._group_summary(group)})
    return pd.DataFrame(rows)


def evaluate_discovery_gate(candidates: pd.DataFrame) -> dict[str, Any]:
    summary = s009._group_summary(candidates) if not candidates.empty else {}
    yearly = _candidate_yearly(candidates)
    years = set(pd.to_datetime(candidates.get("entry_date", pd.Series(dtype="datetime64[ns]"))).dt.year.dropna())
    coverage_gate = bool(
        len(candidates) >= 30
        and candidates.get("product", pd.Series(dtype=str)).nunique() >= 8
        and candidates.get("direction", pd.Series(dtype=str)).nunique() >= 2
        and DISCOVERY_YEARS.issubset(years)
    )
    overall_rate = _safe_float(summary.get("target_first_2r_rate"))
    overall_low = _safe_float(summary.get("target_first_2r_wilson_low"))
    yearly_rates = (
        pd.to_numeric(yearly.get("target_first_2r_rate", pd.Series(dtype=float)), errors="coerce")
        if not yearly.empty
        else pd.Series(dtype=float)
    )
    first_touch_gate = bool(
        coverage_gate
        and overall_rate > TWO_R_BREAKEVEN
        and overall_low > TWO_R_BREAKEVEN
        and len(yearly_rates) == 3
        and yearly_rates.gt(TWO_R_BREAKEVEN).all()
    )
    yearly_r = (
        pd.to_numeric(yearly.get("baseline_total_r", pd.Series(dtype=float)), errors="coerce")
        if not yearly.empty
        else pd.Series(dtype=float)
    )
    baseline_gate = bool(coverage_gate and len(yearly_r) == 3 and yearly_r.gt(0.0).all())
    allowed = bool(coverage_gate and first_touch_gate and baseline_gate)
    return {
        "coverage_gate_pass": coverage_gate,
        "first_touch_gate_pass": first_touch_gate,
        "baseline_right_tail_gate_pass": baseline_gate,
        "stage011_real_engine_predecl_allowed": allowed,
        "candidate_count": int(len(candidates)),
        "product_count": int(candidates.get("product", pd.Series(dtype=str)).nunique()),
        "direction_count": int(candidates.get("direction", pd.Series(dtype=str)).nunique()),
        "year_count": int(len(years)),
        "target_first_2r_rate": overall_rate,
        "target_first_2r_wilson_low": overall_low,
        "target_first_2r_breakeven": TWO_R_BREAKEVEN,
        "summary": summary,
        "yearly": yearly.to_dict("records"),
    }


def _verify_manifest(manifest_path: Path) -> None:
    if not manifest_path.exists():
        raise RuntimeError(f"missing upstream manifest: {manifest_path}")
    manifest = pd.read_csv(manifest_path)
    required = {"path", "bytes", "sha256"}
    if not required.issubset(manifest.columns):
        raise RuntimeError(f"invalid upstream manifest schema: {manifest_path}")
    failures = []
    for row in manifest.itertuples(index=False):
        path = Path(str(row.path))
        if not path.exists() or path.stat().st_size != int(row.bytes) or s009._sha256(path) != str(row.sha256):
            failures.append(str(path))
    if failures:
        raise RuntimeError(f"upstream manifest hash mismatch: {failures[:10]}")


def _load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    _verify_manifest(s009.INPUT_MANIFEST_PATH)
    _verify_manifest(s009.OUTPUT_MANIFEST_PATH)
    if not STAGE009_RESULT_PATH.exists():
        raise RuntimeError("missing Stage009 independent-review result record")
    stage009_result = STAGE009_RESULT_PATH.read_text(encoding="utf-8")
    required_fragments = (
        "P0/P1/P2/P3 = 0/0/0/0",
        "stage010_attribution_allowed = true",
        "stage010_real_engine_allowed = false",
    )
    if not all(fragment in stage009_result for fragment in required_fragments):
        raise RuntimeError("Stage009 review record does not allow Stage010 attribution")
    closed, lineage, minute, _, _ = s009._load_inputs()
    events, aggregate_audit = s009._event_inputs(closed, lineage)
    actual_entry = pd.to_numeric(events["actual_entry_price"], errors="coerce")
    stop_price = pd.to_numeric(events["stop_price"], errors="coerce")
    actual_stop = pd.to_numeric(events["actual_stop_distance"], errors="coerce")
    recomputed = (actual_entry - stop_price).abs()
    if actual_stop.isna().any() or actual_stop.le(0.0).any():
        raise RuntimeError("event actual stop distance is missing or invalid")
    if not np.allclose(actual_stop, recomputed, rtol=0.0, atol=1e-8):
        raise RuntimeError("actual stop distance disagrees with actual fill-to-stop geometry")
    return events, minute, lineage, aggregate_audit


def _compute_all_events(
    events: pd.DataFrame,
    minute: pd.DataFrame,
    priceticks: Mapping[str, float],
) -> pd.DataFrame:
    data = minute.copy()
    data["bar_date"] = pd.to_datetime(data["bar_date"], errors="coerce").dt.normalize()
    data["bar_datetime"] = pd.to_datetime(data["bar_datetime"], errors="coerce").dt.tz_localize(None)
    groups = {
        (str(symbol), pd.Timestamp(date).normalize()): group.copy()
        for (symbol, date), group in data.groupby(["vt_symbol", "bar_date"], sort=False)
    }
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for event in events.to_dict("records"):
        symbol = str(event["vt_symbol"])
        entry_date = pd.Timestamp(event["entry_date"]).normalize()
        key = (symbol, entry_date)
        session = groups.get(key)
        if session is None:
            failures.append({"open_trade_id": event["open_trade_id"], "error": "missing_session"})
            continue
        if symbol not in priceticks:
            failures.append({"open_trade_id": event["open_trade_id"], "error": "missing_pricetick"})
            continue
        try:
            tick, tick_rule = s009.effective_pricetick(symbol, entry_date, float(priceticks[symbol]))
            first_open = _safe_float(session.sort_values("bar_datetime").iloc[0]["open"])
            if not np.isclose(first_open, _safe_float(event["actual_entry_price"]), rtol=0.0, atol=1e-8):
                raise ValueError("root fill does not equal first session minute open")
            rows.append(
                compute_pullback_reclaim_event(
                    event,
                    session,
                    pricetick=tick,
                    pricetick_rule=tick_rule,
                    compute_outcomes=str(event["sample_segment"]) == "discovery",
                )
            )
        except Exception as exc:
            failures.append({"open_trade_id": event["open_trade_id"], "error": str(exc)})
    if failures:
        raise RuntimeError(f"Stage010 event computation failed: {failures[:10]}")
    result = pd.DataFrame(rows)
    if len(result) != len(events) or result["open_trade_id"].nunique() != len(events):
        raise RuntimeError("Stage010 root event count is not conserved")
    if pd.to_numeric(result["feature_future_violation"], errors="coerce").fillna(1).ne(0).any():
        raise RuntimeError("Stage010 candidate feature uses a future bar")
    return result


def _status_aggregate(events: pd.DataFrame) -> pd.DataFrame:
    return (
        events.groupby(["sample_segment", "candidate_status"], as_index=False)
        .agg(
            event_count=("open_trade_id", "size"),
            product_count=("product", "nunique"),
            direction_count=("direction", "nunique"),
        )
        .sort_values(["sample_segment", "candidate_status"])
        .reset_index(drop=True)
    )


def _plot_attribution(
    discovery: pd.DataFrame,
    candidates: pd.DataFrame,
    yearly: pd.DataFrame,
) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(13, 13), constrained_layout=True)
    status = discovery["candidate_status"].value_counts().sort_values(ascending=True)
    axes[0].barh(status.index, status.values, color="#4c78a8")
    axes[0].set_title("Stage010 discovery: deterministic state-machine outcomes")
    axes[0].set_xlabel("root event count")
    axes[0].grid(alpha=0.2, axis="x")

    if yearly.empty:
        axes[1].text(0.5, 0.5, "No discovery candidates", ha="center", va="center")
        axes[2].text(0.5, 0.5, "No discovery candidates", ha="center", va="center")
    else:
        years = yearly["entry_year"].astype(int).to_numpy()
        axes[1].plot(years, yearly["target_first_1r_rate"], marker="o", label="+1R target first")
        axes[1].plot(years, yearly["target_first_2r_rate"], marker="o", label="+2R target first")
        axes[1].axhline(0.5, color="#6b7280", linestyle="--", linewidth=0.8, label="1R break-even")
        axes[1].axhline(TWO_R_BREAKEVEN, color="#b91c1c", linestyle="--", linewidth=0.8, label="2R break-even")
        axes[1].set_ylim(0.0, 1.0)
        axes[1].set_xticks(years)
        axes[1].set_ylabel("target-first rate")
        axes[1].set_title("Discovery candidate first-touch by year")
        axes[1].legend(loc="best")
        axes[1].grid(alpha=0.2)

        axes[2].bar(years, yearly["baseline_total_r"], color="#2e7d32")
        axes[2].axhline(0.0, color="#111827", linewidth=0.8)
        axes[2].set_xticks(years)
        axes[2].set_ylabel("baseline total R")
        axes[2].set_title("Same parent events: original strategy right-tail preservation")
        axes[2].grid(alpha=0.2, axis="y")
    fig.suptitle("Stage010 prove-pullback-reclaim attribution (discovery only)", fontsize=14)
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _input_paths() -> list[Path]:
    universe_path = Path(
        str(
            s009.s008.strict.s901.s513._c3_overrides(s009.s008.strict.s901.s513.START_DT).get(
                "product_universe_csv_path", ""
            )
        )
    ).expanduser()
    paths = [
        s009.s008.CLOSED_LOTS_PATH,
        s009.s008.OPEN_LINEAGE_PATH,
        s009.s008.DECISION_PATH,
        s009.MINUTE_PATCH_PATH,
        s009.MINUTE_AUDIT_PATH,
        s009.STAGE000_DECISION_PATH,
        s009.STAGE009_TOOL_PATH,
        s009.STAGE009_TEST_PATH,
        s009.STAGE009_PREDECL_PATH,
        s009.DECISION_PATH,
        s009.INPUT_MANIFEST_PATH,
        s009.OUTPUT_MANIFEST_PATH,
        STAGE009_RESULT_PATH,
        TOOL_PATH,
        TEST_PATH,
        PREDECL_PATH,
        s009.CONTRACT_METADATA_PATH,
        s009.MAIN_MAPPING_PATH,
        universe_path,
    ]
    return paths


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    print("[stage010] prove-pullback-reclaim attribution start", flush=True)
    events, minute, _, aggregate_audit = _load_inputs()
    metadata = s009.s008.strict.s901.s513._metadata()
    all_events = _compute_all_events(events, minute, metadata["priceticks"])
    discovery, future_seal = partition_outputs(all_events)
    if future_seal["future_outcomes_computed"]:
        raise RuntimeError("Stage010 historical locked future outcomes were computed")

    expected_segments = {"discovery": 171, "validation": 78, "holdout": 51}
    actual_segments = all_events["sample_segment"].value_counts().sort_index().to_dict()
    if actual_segments != expected_segments:
        raise RuntimeError(f"unexpected Stage010 segment counts: {actual_segments}")
    candidates = discovery.loc[discovery["candidate_status"].eq("candidate")].copy()
    summary = s009._group_summary(candidates) if not candidates.empty else pd.Series(dtype=float).to_dict()
    yearly = _candidate_yearly(candidates)
    gate = evaluate_discovery_gate(candidates)
    status = _status_aggregate(all_events)

    input_paths = _input_paths()
    s009._manifest(input_paths).to_csv(INPUT_MANIFEST_PATH, index=False)
    discovery.to_csv(DISCOVERY_EVENTS_PATH, index=False, compression="gzip")
    candidates.to_csv(DISCOVERY_CANDIDATES_PATH, index=False)
    pd.DataFrame([summary]).to_csv(SUMMARY_PATH, index=False)
    yearly.to_csv(YEARLY_PATH, index=False)
    status.to_csv(STATUS_PATH, index=False)
    FUTURE_SEAL_PATH.write_text(
        json.dumps(_json_safe(future_seal), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _plot_attribution(discovery, candidates, yearly)

    allowed = bool(gate["stage011_real_engine_predecl_allowed"])
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "decision": (
            "stage010_attribution_gate_pass_stage011_real_engine_predecl_allowed_pending_review"
            if allowed
            else "stage010_attribution_gate_failed_close_minute_tight_stop_branch_pending_review"
        ),
        "independent_review_complete": False,
        "strategy_changed": False,
        "new_ai_feature_count": 0,
        "stage011_real_engine_predecl_allowed": False,
        "stage011_pre_review_numeric_gate_pass": allowed,
        "fixed_contract": {
            "proof_r": PROOF_R,
            "fail_r": FAIL_R,
            "minimum_completed_minutes": MIN_COMPLETED_MINUTES,
            "maximum_micro_actual_risk_ratio": MAX_MICRO_RISK_RATIO,
            "same_bar_ordering": "stop_first",
            "execution": "next_real_minute_open",
            "two_r_breakeven": TWO_R_BREAKEVEN,
        },
        "event_count": int(len(all_events)),
        "segment_counts": actual_segments,
        "discovery_status_counts": discovery["candidate_status"].value_counts().sort_index().to_dict(),
        "all_status_aggregate": status.to_dict("records"),
        "discovery_gate": gate,
        "future_feature_seal": future_seal,
        "historical_pricetick_rule_counts": all_events["pricetick_rule"].value_counts().sort_index().to_dict(),
        "aggregate_audit": aggregate_audit,
        "true_oos_available": False,
        "evaluation_scope": "predeclared discovery attribution; historical locked future features only",
        "external_research": EXTERNAL_RESEARCH,
        "overfit_before": "高：在 Stage009 失败后提出第二个分钟结构；已冻结唯一状态机和全部硬门。",
        "overfit_after": (
            "仍高；数值门暂时通过也必须等待独立复核，且没有真正 OOS。"
            if allowed
            else "仍高；预声明硬门失败，不允许通过修改分钟/R/风险阈值救参。"
        ),
        "continue_before": "有且仅有一次归因价值：检验与立即追价不同的证明-回踩-收复机制。",
        "continue_after": (
            "仅在独立复核无结果影响问题后，才可预声明唯一真实引擎。"
            if allowed
            else "当前分钟紧止损方向无继续价值，应关闭而不是换参数。"
        ),
    }
    DECISION_PATH.write_text(
        json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    REPORT_PATH.write_text(
        "\n".join(
            [
                "# Stage010 趋势证明-回踩-再确认紧止损归因",
                "",
                f"- 生成时间：`{decision['generated_at']}`",
                f"- 决策：`{decision['decision']}`",
                "- 不改变策略、不新增 AI 特征、不输出组合收益。",
                "- 2023-2026 只计算候选特征并 seal，未计算 first-touch 结果。",
                "",
                "## 固定合同",
                "",
                f"- `{json.dumps(_json_safe(decision['fixed_contract']), ensure_ascii=False)}`",
                "",
                "## Discovery 状态",
                "",
                _md_table(
                    status.loc[status["sample_segment"].eq("discovery")],
                ),
                "",
                "## Discovery 候选总表",
                "",
                _md_table(pd.DataFrame([summary])),
                "",
                "## Discovery 年度分解",
                "",
                _md_table(yearly),
                "",
                "## 硬门",
                "",
                f"- `{json.dumps(_json_safe(gate), ensure_ascii=False)}`",
                "",
                "## 完整性",
                "",
                f"- 根事件守恒：`{json.dumps(_json_safe(aggregate_audit), ensure_ascii=False)}`",
                f"- 后段 seal：`{json.dumps(_json_safe(future_seal), ensure_ascii=False)}`",
                f"- 历史 tick：`{json.dumps(_json_safe(decision['historical_pricetick_rule_counts']), ensure_ascii=False)}`",
                "",
                "## 调研判断",
                "",
                "- 浅回踩仅是待证假设；已有期货证据同时警告价格止损和开盘早段可能毁损信号。",
                "- 本阶段用下一分钟 open 与同 bar 止损优先，避免把不可知的分钟内路径写成乐观成交。",
                "",
                "## 反思",
                "",
                f"- 过拟合：`{decision['overfit_after']}`",
                f"- 继续价值：`{decision['continue_after']}`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    output_paths = [
        DISCOVERY_EVENTS_PATH,
        DISCOVERY_CANDIDATES_PATH,
        SUMMARY_PATH,
        YEARLY_PATH,
        STATUS_PATH,
        FUTURE_SEAL_PATH,
        INPUT_MANIFEST_PATH,
        CHART_PATH,
        DECISION_PATH,
        REPORT_PATH,
    ]
    s009._manifest(output_paths).to_csv(OUTPUT_MANIFEST_PATH, index=False)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
