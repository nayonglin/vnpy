from __future__ import annotations

from collections import Counter
from dataclasses import replace
from datetime import datetime, timedelta
import json
from pathlib import Path
from typing import Any

import pandas as pd

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage653_stage526_200k_forced_margin_deleverage as s653
import analyze_qmt_roll_stage719_official_winner_trade_forensics as s719
import analyze_qmt_roll_stage757_c50_oi_confirm_risk_restore as s757
import analyze_qmt_roll_stage768_2018_start_stage757_stage764 as s768
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage769_2018_trade_count_forensics_v1"
OUTPUT_PREFIX = "qmt_roll_stage769_2018_trade_count_forensics"
LINE_ID = "futures_trend_2019_data_extension"

ANALYSIS_END = pd.Timestamp("2026-05-29")
STARTS = (
    pd.Timestamp("2018-01-01"),
    pd.Timestamp("2019-01-01"),
    pd.Timestamp("2020-01-01"),
)

DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
TRADES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{MODEL_TAG}.csv"
TRADE_USAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_usage_{MODEL_TAG}.csv"
TRADE_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_events_{MODEL_TAG}.csv"
ENTRY_RISK_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_{MODEL_TAG}.csv"
ENTRY_CANDIDATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidates_{MODEL_TAG}.csv"
YEAR_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_summary_{MODEL_TAG}.csv"
START_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_start_summary_{MODEL_TAG}.csv"
PAIR_COMPARE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pair_compare_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _date_series(frame: pd.DataFrame, column: str) -> pd.Series:
    if frame.empty or column not in frame.columns:
        return pd.Series(dtype="datetime64[ns]")
    return pd.to_datetime(frame[column], errors="coerce").dt.tz_localize(None).dt.normalize()


def _preload_for_start(start: pd.Timestamp) -> pd.Timestamp:
    if start < pd.Timestamp("2020-01-01"):
        return (start - pd.Timedelta(days=365)).normalize()
    return pd.Timestamp(s653.s517.PRELOAD_START_DT).normalize()


def _run_engine_for_start(
    start: pd.Timestamp,
    metadata: dict[str, Any],
    spec: s653.ForcedVariant,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], pd.DataFrame]:
    original_start = s653.s517.START_DT
    original_end = s653.s517.END_DT
    original_preload = s653.s517.PRELOAD_START_DT
    try:
        s653.s517.START_DT = start.to_pydatetime()
        s653.s517.END_DT = ANALYSIS_END.to_pydatetime()
        s653.s517.PRELOAD_START_DT = _preload_for_start(start).to_pydatetime()

        s653.s517.assert_stage196_database_sentinels()
        s653.s517.s506._patch_stage506_raw_roots()
        c3_overrides = s513._c3_overrides(s653.s517.START_DT)
        preload_start = max(s653.s517.PRELOAD_START_DT, s653.s517.START_DT - timedelta(days=365))
        _, open_map = s653.s517.s506.s501._seed_proxy_maps()
        engine = s653.s517.s506.s502.ConfirmedDailyNextRealOpenEngine(open_map)
        engine.output = lambda msg: None
        engine.set_parameters(
            vt_symbols=metadata["vt_symbols"],
            interval=s653.s517.Interval.DAILY,
            start=preload_start,
            end=s653.s517.END_DT,
            rates=metadata["rates"],
            slippages=metadata["slippages"],
            sizes=metadata["sizes"],
            priceticks=metadata["priceticks"],
            capital=spec.capital.c3_capital,
        )
        setting = s653.s517.build_roll_setting(
            metadata["margin_ratios"],
            risk_ratio=s653.s517.BASE_RISK_RATIO * float(spec.capital.risk_multiplier),
            strategy_overrides=c3_overrides,
        )
        setting["capital_base"] = spec.capital.c3_capital
        setting.update(spec.overrides)
        engine.add_strategy(QmtRollPortfolioStrategy, setting)
        engine.load_data()
        engine.run_backtesting()
        daily_df = engine.calculate_result()
        if daily_df is None or daily_df.empty:
            raise RuntimeError(f"empty daily result for {start.date()}")

        daily = daily_df.copy()
        daily = daily.loc[(daily.index >= start.date()) & (daily.index <= ANALYSIS_END.date())].reset_index()
        daily.rename(columns={"index": "date"}, inplace=True)
        daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
        for column in ["net_pnl", "trade_count", "slippage", "commission", "turnover"]:
            daily[column] = pd.to_numeric(daily.get(column, 0.0), errors="coerce").fillna(0.0)
        daily["c3_equity"] = float(spec.capital.c3_capital) + daily["net_pnl"].cumsum()
        daily["requested_start_month"] = start.strftime("%Y-%m")
        daily["preload_start"] = preload_start.date().isoformat()

        frames = s719._extract_raw_frames(engine, spec)
        usage = pd.DataFrame(getattr(engine, "trade_usage_rows", []))
    finally:
        s653.s517.START_DT = original_start
        s653.s517.END_DT = original_end
        s653.s517.PRELOAD_START_DT = original_preload

    return daily, frames, usage


def _tag_frame(frame: pd.DataFrame, start: pd.Timestamp) -> pd.DataFrame:
    data = frame.copy()
    data["requested_start_month"] = start.strftime("%Y-%m")
    data["preload_start"] = _preload_for_start(start).date().isoformat()
    return data


def _first_date(frame: pd.DataFrame, column: str) -> str:
    dates = _date_series(frame, column).dropna()
    if dates.empty:
        return ""
    return dates.min().date().isoformat()


def _first_equity_change(daily: pd.DataFrame) -> str:
    if daily.empty:
        return ""
    equity = pd.to_numeric(daily["c3_equity"], errors="coerce").ffill()
    changed = daily[equity.ne(float(equity.iloc[0]))].copy()
    if changed.empty:
        return ""
    return pd.Timestamp(changed["date"].iloc[0]).date().isoformat()


def _first_nonzero_trade_count(daily: pd.DataFrame) -> str:
    if daily.empty:
        return ""
    nonzero = daily[pd.to_numeric(daily["trade_count"], errors="coerce").fillna(0.0).gt(0.0)].copy()
    if nonzero.empty:
        return ""
    return pd.Timestamp(nonzero["date"].iloc[0]).date().isoformat()


def _start_summary(
    start: pd.Timestamp,
    daily: pd.DataFrame,
    frames: dict[str, pd.DataFrame],
    usage: pd.DataFrame,
) -> dict[str, Any]:
    trades = frames.get("trades", pd.DataFrame())
    candidates = frames.get("entry_candidates", pd.DataFrame())
    entry_risk = frames.get("entry_risk", pd.DataFrame())
    trade_events = frames.get("trade_events", pd.DataFrame())
    return {
        "requested_start_month": start.strftime("%Y-%m"),
        "preload_start": _preload_for_start(start).date().isoformat(),
        "daily_first_date": pd.Timestamp(daily["date"].min()).date().isoformat() if not daily.empty else "",
        "daily_last_date": pd.Timestamp(daily["date"].max()).date().isoformat() if not daily.empty else "",
        "daily_rows": int(len(daily)),
        "first_equity_change_date": _first_equity_change(daily),
        "first_nonzero_daily_trade_count_date": _first_nonzero_trade_count(daily),
        "first_trade_fill_date": _first_date(trades, "datetime"),
        "first_trade_signal_date": _first_date(usage, "signal_date"),
        "first_trade_usage_fill_date": _first_date(usage, "fill_date"),
        "first_entry_candidate_date": _first_date(candidates, "datetime"),
        "first_open_entry_risk_date": _first_date(entry_risk, "datetime"),
        "first_trade_event_date": _first_date(trade_events, "datetime"),
        "total_daily_trade_count": float(pd.to_numeric(daily.get("trade_count", 0.0), errors="coerce").fillna(0.0).sum()),
        "trade_rows": int(len(trades)),
        "trade_usage_rows": int(len(usage)),
        "entry_candidate_rows": int(len(candidates)),
        "entry_candidate_opened_rows": int(candidates["candidate_status"].astype(str).eq("opened").sum()) if not candidates.empty and "candidate_status" in candidates.columns else 0,
        "entry_candidate_skipped_rows": int(candidates["candidate_status"].astype(str).eq("skipped").sum()) if not candidates.empty and "candidate_status" in candidates.columns else 0,
        "entry_risk_rows": int(len(entry_risk)),
        "trade_event_rows": int(len(trade_events)),
        "end_equity": float(pd.to_numeric(daily["c3_equity"], errors="coerce").iloc[-1]) if not daily.empty else 0.0,
    }


def _append_year_rows(
    rows: list[dict[str, Any]],
    start: pd.Timestamp,
    name: str,
    frame: pd.DataFrame,
    date_column: str,
    extra_group_columns: list[str] | None = None,
) -> None:
    if frame.empty or date_column not in frame.columns:
        return
    data = frame.copy()
    data["_year"] = _date_series(data, date_column).dt.year
    data = data[data["_year"].notna()].copy()
    if data.empty:
        return
    groups = ["_year"] + list(extra_group_columns or [])
    for group_key, group in data.groupby(groups, dropna=False, sort=True):
        if not isinstance(group_key, tuple):
            group_key = (group_key,)
        row = {
            "requested_start_month": start.strftime("%Y-%m"),
            "dataset": name,
            "year": int(group_key[0]),
            "rows": int(len(group)),
        }
        for column, value in zip(groups[1:], group_key[1:], strict=False):
            row[column] = str(value)
        rows.append(row)


def _year_summary(start: pd.Timestamp, daily: pd.DataFrame, frames: dict[str, pd.DataFrame], usage: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not daily.empty:
        data = daily.copy()
        data["_year"] = pd.to_datetime(data["date"], errors="coerce").dt.year
        for year, group in data.groupby("_year", sort=True):
            rows.append(
                {
                    "requested_start_month": start.strftime("%Y-%m"),
                    "dataset": "daily",
                    "year": int(year),
                    "rows": int(len(group)),
                    "trade_count_sum": float(pd.to_numeric(group["trade_count"], errors="coerce").fillna(0.0).sum()),
                    "net_pnl_sum": float(pd.to_numeric(group["net_pnl"], errors="coerce").fillna(0.0).sum()),
                    "nonzero_trade_days": int(pd.to_numeric(group["trade_count"], errors="coerce").fillna(0.0).gt(0.0).sum()),
                }
            )
    _append_year_rows(rows, start, "trades_by_fill", frames.get("trades", pd.DataFrame()), "datetime", ["direction", "offset"])
    _append_year_rows(rows, start, "trade_events_by_signal_bar", frames.get("trade_events", pd.DataFrame()), "datetime", ["position_direction", "offset", "reason"])
    _append_year_rows(rows, start, "entry_candidates", frames.get("entry_candidates", pd.DataFrame()), "datetime", ["candidate_status", "skip_reason"])
    _append_year_rows(rows, start, "entry_risk", frames.get("entry_risk", pd.DataFrame()), "datetime", ["direction", "signal"])
    _append_year_rows(rows, start, "trade_usage_by_signal", usage, "signal_date", ["direction", "offset", "price_source"])
    _append_year_rows(rows, start, "trade_usage_by_fill", usage, "fill_date", ["direction", "offset", "price_source"])
    return rows


def _signature_rows(trades: pd.DataFrame, min_date: str | None = None) -> list[tuple[Any, ...]]:
    if trades.empty:
        return []
    data = trades.copy()
    data["date_norm"] = _date_series(data, "datetime")
    if min_date:
        data = data[data["date_norm"].ge(pd.Timestamp(min_date).normalize())].copy()
    signatures: list[tuple[Any, ...]] = []
    for row in data.sort_values(["date_norm", "vt_symbol", "direction", "offset", "price", "volume"]).itertuples(index=False):
        signatures.append(
            (
                pd.Timestamp(row.date_norm).date().isoformat(),
                str(row.vt_symbol),
                str(row.direction),
                str(row.offset),
                round(float(row.price), 6),
                round(float(row.volume), 6),
            )
        )
    return signatures


def _pair_compare(all_trades: dict[str, pd.DataFrame]) -> pd.DataFrame:
    pairs = [
        ("2018-01", "2019-01", "2019-01-01"),
        ("2019-01", "2020-01", "2020-01-01"),
        ("2018-01", "2020-01", "2020-01-01"),
    ]
    rows: list[dict[str, Any]] = []
    for left, right, min_date in pairs:
        left_sig = _signature_rows(all_trades.get(left, pd.DataFrame()), min_date=min_date)
        right_sig = _signature_rows(all_trades.get(right, pd.DataFrame()), min_date=min_date)
        left_counter = Counter(left_sig)
        right_counter = Counter(right_sig)
        common = left_counter & right_counter
        only_left = left_counter - right_counter
        only_right = right_counter - left_counter
        same_order = left_sig == right_sig
        first_diff = ""
        for left_item, right_item in zip(left_sig, right_sig, strict=False):
            if left_item != right_item:
                first_diff = f"{left_item} != {right_item}"
                break
        if not first_diff and len(left_sig) != len(right_sig):
            first_diff = f"length {len(left_sig)} != {len(right_sig)}"
        rows.append(
            {
                "left_start": left,
                "right_start": right,
                "compare_from": min_date,
                "left_trade_rows": int(sum(left_counter.values())),
                "right_trade_rows": int(sum(right_counter.values())),
                "common_trade_rows": int(sum(common.values())),
                "only_left_trade_rows": int(sum(only_left.values())),
                "only_right_trade_rows": int(sum(only_right.values())),
                "same_ordered_signature": int(same_order),
                "first_difference": first_diff,
            }
        )
    return pd.DataFrame(rows)


def _write_report(start_summary: pd.DataFrame, year_summary: pd.DataFrame, pair_compare: pd.DataFrame, decision: dict[str, Any]) -> None:
    daily_year = year_summary[year_summary["dataset"].eq("daily")].copy()
    candidates = year_summary[year_summary["dataset"].eq("entry_candidates")].copy()
    lines = [
        "# Stage769 2018/2019/2020 交易笔数法证复盘",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        "- 本阶段只读复盘，不修改策略参数、不补伪造数据、不连接 CTP。",
        "",
        "## 起点级核对",
        "",
        _md_table(start_summary, max_rows=20),
        "",
        "## 日线年度交易计数",
        "",
        _md_table(daily_year, max_rows=40),
        "",
        "## 候选年度分布",
        "",
        _md_table(candidates, max_rows=80),
        "",
        "## 成交集合对比",
        "",
        _md_table(pair_compare, max_rows=10),
        "",
        "## 结论",
        "",
        f"- 数据问题判断：`{decision['data_issue_judgment']}`",
        f"- 交易笔数相近原因：`{decision['trade_count_explanation']}`",
        f"- 过拟合判断：`{decision['overfit_judgment']}`",
        f"- 继续价值：`{decision['continue_value']}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    metadata = s513._metadata()
    spec = s757._candidate_spec(metadata)

    daily_frames: list[pd.DataFrame] = []
    trades_frames: list[pd.DataFrame] = []
    usage_frames: list[pd.DataFrame] = []
    events_frames: list[pd.DataFrame] = []
    entry_risk_frames: list[pd.DataFrame] = []
    candidate_frames: list[pd.DataFrame] = []
    start_rows: list[dict[str, Any]] = []
    year_rows: list[dict[str, Any]] = []
    trades_by_start: dict[str, pd.DataFrame] = {}

    for start in STARTS:
        print(f"[stage769] running {start.strftime('%Y-%m')}", flush=True)
        daily, frames, usage = _run_engine_for_start(start, metadata, replace(spec))
        start_key = start.strftime("%Y-%m")
        trades_by_start[start_key] = frames.get("trades", pd.DataFrame()).copy()
        start_rows.append(_start_summary(start, daily, frames, usage))
        year_rows.extend(_year_summary(start, daily, frames, usage))
        daily_frames.append(daily)
        if not frames.get("trades", pd.DataFrame()).empty:
            trades_frames.append(_tag_frame(frames["trades"], start))
        if not usage.empty:
            usage_frames.append(_tag_frame(usage, start))
        if not frames.get("trade_events", pd.DataFrame()).empty:
            events_frames.append(_tag_frame(frames["trade_events"], start))
        if not frames.get("entry_risk", pd.DataFrame()).empty:
            entry_risk_frames.append(_tag_frame(frames["entry_risk"], start))
        if not frames.get("entry_candidates", pd.DataFrame()).empty:
            candidate_frames.append(_tag_frame(frames["entry_candidates"], start))

    daily_all = pd.concat(daily_frames, ignore_index=True, sort=False)
    trades_all = pd.concat(trades_frames, ignore_index=True, sort=False) if trades_frames else pd.DataFrame()
    usage_all = pd.concat(usage_frames, ignore_index=True, sort=False) if usage_frames else pd.DataFrame()
    events_all = pd.concat(events_frames, ignore_index=True, sort=False) if events_frames else pd.DataFrame()
    entry_risk_all = pd.concat(entry_risk_frames, ignore_index=True, sort=False) if entry_risk_frames else pd.DataFrame()
    candidate_all = pd.concat(candidate_frames, ignore_index=True, sort=False) if candidate_frames else pd.DataFrame()
    start_summary = pd.DataFrame(start_rows)
    year_summary = pd.DataFrame(year_rows)
    pair_compare = _pair_compare(trades_by_start)

    decision = {
        "stage": "Stage769",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "data_issue_judgment": (
            "not_evidence_of_reused_data: 2018 and 2019 ordered trade signatures are identical only from 2019 onward, "
            "because 2018 has zero candidates/trades/equity changes"
        ),
        "trade_count_explanation": (
            "2018-start equals 2019-start because no trade candidate appears before 2019-02-11/12; "
            "2020-start is close because it removes only the 2019 trades and the later strategy path remains largely shared"
        ),
        "overfit_judgment": "low: forensic rerun only; no strategy parameter or data-filling rule is changed",
        "continue_value": (
            "yes for a narrower 2018 no-candidate root-cause audit; no for parameter changes designed to force 2018 trades"
        ),
        "outputs": {
            "daily": str(DAILY_PATH),
            "trades": str(TRADES_PATH),
            "trade_usage": str(TRADE_USAGE_PATH),
            "trade_events": str(TRADE_EVENTS_PATH),
            "entry_risk": str(ENTRY_RISK_PATH),
            "entry_candidates": str(ENTRY_CANDIDATES_PATH),
            "year_summary": str(YEAR_SUMMARY_PATH),
            "start_summary": str(START_SUMMARY_PATH),
            "pair_compare": str(PAIR_COMPARE_PATH),
            "report": str(REPORT_PATH),
            "decision": str(DECISION_PATH),
        },
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }

    daily_all.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    trades_all.to_csv(TRADES_PATH, index=False, encoding="utf-8-sig")
    usage_all.to_csv(TRADE_USAGE_PATH, index=False, encoding="utf-8-sig")
    events_all.to_csv(TRADE_EVENTS_PATH, index=False, encoding="utf-8-sig")
    entry_risk_all.to_csv(ENTRY_RISK_PATH, index=False, encoding="utf-8-sig")
    candidate_all.to_csv(ENTRY_CANDIDATES_PATH, index=False, encoding="utf-8-sig")
    start_summary.to_csv(START_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    year_summary.to_csv(YEAR_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    pair_compare.to_csv(PAIR_COMPARE_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(start_summary, year_summary, pair_compare, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
