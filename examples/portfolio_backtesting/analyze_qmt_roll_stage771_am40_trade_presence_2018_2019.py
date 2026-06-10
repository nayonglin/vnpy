from __future__ import annotations

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
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy
from vnpy.trader.utility import ArrayManager


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage771_am40_trade_presence_2018_2019_v1"
OUTPUT_PREFIX = "qmt_roll_stage771_am40_trade_presence_2018_2019"
LINE_ID = "futures_trend_2019_data_extension"

ANALYSIS_END = pd.Timestamp("2020-12-31")
STARTS = (
    pd.Timestamp("2018-01-01"),
    pd.Timestamp("2019-01-01"),
)

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
YEAR_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_summary_{MODEL_TAG}.csv"
DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
TRADES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{MODEL_TAG}.csv"
ENTRY_CANDIDATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidates_{MODEL_TAG}.csv"
ENTRY_RISK_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


class QmtRollPortfolioStrategyExactAm(QmtRollPortfolioStrategy):
    """Research-only strategy wrapper that replaces AM size after normal init."""

    research_exact_array_manager_size: int = 0
    parameters = [
        *QmtRollPortfolioStrategy.parameters,
        "research_exact_array_manager_size",
    ]

    def __init__(self, strategy_engine: Any, strategy_name: str, vt_symbols: list[str], setting: dict[str, Any]) -> None:
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)
        exact_size = int(self.research_exact_array_manager_size or 0)
        if exact_size > 0:
            self.ams = {vt_symbol: ArrayManager(exact_size) for vt_symbol in self.vt_symbols}


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _date_series(frame: pd.DataFrame, column: str) -> pd.Series:
    if frame.empty or column not in frame.columns:
        return pd.Series(dtype="datetime64[ns]")
    return pd.to_datetime(frame[column], errors="coerce").dt.tz_localize(None).dt.normalize()


def _preload_for_start(start: pd.Timestamp) -> pd.Timestamp:
    return (start - pd.Timedelta(days=365)).normalize()


def _effective_legacy_am_size(overrides: dict[str, Any]) -> int:
    ma_extra_long = int(overrides.get("ma_extra_long", QmtRollPortfolioStrategy.ma_extra_long))
    donchian_entry_period = int(overrides.get("donchian_entry_period", QmtRollPortfolioStrategy.donchian_entry_period))
    floor = int(overrides.get("array_manager_size_floor", QmtRollPortfolioStrategy.array_manager_size_floor) or 140)
    return max(ma_extra_long + donchian_entry_period + 20, max(floor, 1))


def _profiles() -> tuple[dict[str, Any], ...]:
    return (
        {
            "profile": "A_floor40_legacy_formula_effective80",
            "strategy_cls": QmtRollPortfolioStrategy,
            "overrides": {"array_manager_size_floor": 40},
            "declared_am_size": 80,
            "note": "Only lower array_manager_size_floor to 40; legacy formula still requires 40+20+20=80 bars.",
        },
        {
            "profile": "B_exact40_signal_min41",
            "strategy_cls": QmtRollPortfolioStrategyExactAm,
            "overrides": {
                "array_manager_size_floor": 40,
                "research_exact_array_manager_size": 41,
            },
            "declared_am_size": 41,
            "note": "Research-only exact-40 signal minimum: AM=41 because signal compares current and previous MA40.",
        },
    )


def _run_engine(
    *,
    start: pd.Timestamp,
    metadata: dict[str, Any],
    spec: s653.ForcedVariant,
    profile: dict[str, Any],
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
        setting.update(dict(profile["overrides"]))
        engine.add_strategy(profile["strategy_cls"], setting)
        engine.load_data()
        engine.run_backtesting()
        daily_df = engine.calculate_result()
        if daily_df is None or daily_df.empty:
            raise RuntimeError(f"empty daily result: {profile['profile']} {start.date()}")

        daily = daily_df.copy()
        daily = daily.loc[(daily.index >= start.date()) & (daily.index <= ANALYSIS_END.date())].reset_index()
        daily.rename(columns={"index": "date"}, inplace=True)
        daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
        for column in ["net_pnl", "trade_count", "slippage", "commission", "turnover"]:
            daily[column] = pd.to_numeric(daily.get(column, 0.0), errors="coerce").fillna(0.0)
        daily["c3_equity"] = float(spec.capital.c3_capital) + daily["net_pnl"].cumsum()
        daily["requested_start_month"] = start.strftime("%Y-%m")
        daily["profile"] = str(profile["profile"])
        daily["declared_am_size"] = int(profile["declared_am_size"])

        frames = s719._extract_raw_frames(engine, spec)
        usage = pd.DataFrame(getattr(engine, "trade_usage_rows", []))
    finally:
        s653.s517.START_DT = original_start
        s653.s517.END_DT = original_end
        s653.s517.PRELOAD_START_DT = original_preload

    return daily, frames, usage


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


def _tag(frame: pd.DataFrame, start: pd.Timestamp, profile: dict[str, Any]) -> pd.DataFrame:
    data = frame.copy()
    data["requested_start_month"] = start.strftime("%Y-%m")
    data["profile"] = str(profile["profile"])
    data["declared_am_size"] = int(profile["declared_am_size"])
    return data


def _summary_row(
    *,
    start: pd.Timestamp,
    profile: dict[str, Any],
    daily: pd.DataFrame,
    frames: dict[str, pd.DataFrame],
    usage: pd.DataFrame,
) -> dict[str, Any]:
    trades = frames.get("trades", pd.DataFrame())
    candidates = frames.get("entry_candidates", pd.DataFrame())
    entry_risk = frames.get("entry_risk", pd.DataFrame())
    first_2018_trade = ""
    first_2019_trade = ""
    if not trades.empty:
        fill_dates = _date_series(trades, "datetime")
        trades_tmp = trades.copy()
        trades_tmp["_fill_date"] = fill_dates
        y2018 = trades_tmp[trades_tmp["_fill_date"].dt.year.eq(2018)]
        y2019 = trades_tmp[trades_tmp["_fill_date"].dt.year.eq(2019)]
        first_2018_trade = pd.Timestamp(y2018["_fill_date"].min()).date().isoformat() if not y2018.empty else ""
        first_2019_trade = pd.Timestamp(y2019["_fill_date"].min()).date().isoformat() if not y2019.empty else ""
    return {
        "profile": str(profile["profile"]),
        "requested_start_month": start.strftime("%Y-%m"),
        "declared_am_size": int(profile["declared_am_size"]),
        "profile_note": str(profile["note"]),
        "daily_rows": int(len(daily)),
        "first_equity_change_date": _first_equity_change(daily),
        "first_trade_fill_date": _first_date(trades, "datetime"),
        "first_trade_signal_date": _first_date(usage, "signal_date"),
        "first_entry_candidate_date": _first_date(candidates, "datetime"),
        "first_open_entry_risk_date": _first_date(entry_risk, "datetime"),
        "first_2018_trade_fill_date": first_2018_trade,
        "first_2019_trade_fill_date": first_2019_trade,
        "total_daily_trade_count": float(pd.to_numeric(daily["trade_count"], errors="coerce").fillna(0.0).sum()),
        "trade_rows": int(len(trades)),
        "entry_candidate_rows": int(len(candidates)),
        "entry_candidate_opened_rows": int(candidates["candidate_status"].astype(str).eq("opened").sum()) if not candidates.empty and "candidate_status" in candidates.columns else 0,
        "entry_candidate_skipped_rows": int(candidates["candidate_status"].astype(str).eq("skipped").sum()) if not candidates.empty and "candidate_status" in candidates.columns else 0,
        "entry_risk_rows": int(len(entry_risk)),
        "end_equity": float(pd.to_numeric(daily["c3_equity"], errors="coerce").iloc[-1]) if not daily.empty else 0.0,
    }


def _year_rows(start: pd.Timestamp, profile: dict[str, Any], daily: pd.DataFrame, frames: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    daily_tmp = daily.copy()
    daily_tmp["year"] = pd.to_datetime(daily_tmp["date"], errors="coerce").dt.year
    for year, group in daily_tmp.groupby("year", sort=True):
        rows.append(
            {
                "profile": str(profile["profile"]),
                "requested_start_month": start.strftime("%Y-%m"),
                "year": int(year),
                "dataset": "daily",
                "rows": int(len(group)),
                "trade_count_sum": float(pd.to_numeric(group["trade_count"], errors="coerce").fillna(0.0).sum()),
                "net_pnl_sum": float(pd.to_numeric(group["net_pnl"], errors="coerce").fillna(0.0).sum()),
                "nonzero_trade_days": int(pd.to_numeric(group["trade_count"], errors="coerce").fillna(0.0).gt(0.0).sum()),
            }
        )
    for dataset, frame, date_column in [
        ("trades_by_fill", frames.get("trades", pd.DataFrame()), "datetime"),
        ("entry_candidates", frames.get("entry_candidates", pd.DataFrame()), "datetime"),
        ("entry_risk", frames.get("entry_risk", pd.DataFrame()), "datetime"),
    ]:
        if frame.empty or date_column not in frame.columns:
            continue
        tmp = frame.copy()
        tmp["year"] = _date_series(tmp, date_column).dt.year
        for year, group in tmp[tmp["year"].notna()].groupby("year", sort=True):
            rows.append(
                {
                    "profile": str(profile["profile"]),
                    "requested_start_month": start.strftime("%Y-%m"),
                    "year": int(year),
                    "dataset": dataset,
                    "rows": int(len(group)),
                }
            )
    return rows


def _write_report(summary: pd.DataFrame, year_summary: pd.DataFrame, decision: dict[str, Any]) -> None:
    lines = [
        "# Stage771 AM40 2018/2019 是否有交易",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        "- 本阶段隔离降低 AM 预热门槛，不修改正式策略默认参数。",
        "",
        "## 起点结果",
        "",
        _md_table(summary, max_rows=20),
        "",
        "## 年度分布",
        "",
        _md_table(year_summary, max_rows=80),
        "",
        "## 结论",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 过拟合判断：`{decision['overfit_judgment']}`",
        f"- 继续价值：`{decision['continue_value']}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    metadata = s513._metadata()
    spec = s757._candidate_spec(metadata)

    summary_rows: list[dict[str, Any]] = []
    year_rows: list[dict[str, Any]] = []
    daily_frames: list[pd.DataFrame] = []
    trade_frames: list[pd.DataFrame] = []
    candidate_frames: list[pd.DataFrame] = []
    entry_risk_frames: list[pd.DataFrame] = []

    for profile in _profiles():
        if profile["profile"] == "A_floor40_legacy_formula_effective80":
            effective = _effective_legacy_am_size({**profile["overrides"]})
            profile["declared_am_size"] = effective
        for start in STARTS:
            print(f"[stage771] {profile['profile']} start={start.strftime('%Y-%m')}", flush=True)
            daily, frames, usage = _run_engine(
                start=start,
                metadata=metadata,
                spec=replace(spec),
                profile=profile,
            )
            summary_rows.append(_summary_row(start=start, profile=profile, daily=daily, frames=frames, usage=usage))
            year_rows.extend(_year_rows(start, profile, daily, frames))
            daily_frames.append(daily)
            for source, collector in [
                (frames.get("trades", pd.DataFrame()), trade_frames),
                (frames.get("entry_candidates", pd.DataFrame()), candidate_frames),
                (frames.get("entry_risk", pd.DataFrame()), entry_risk_frames),
            ]:
                if not source.empty:
                    collector.append(_tag(source, start, profile))

    summary = pd.DataFrame(summary_rows)
    year_summary = pd.DataFrame(year_rows)
    daily_all = pd.concat(daily_frames, ignore_index=True, sort=False) if daily_frames else pd.DataFrame()
    trades_all = pd.concat(trade_frames, ignore_index=True, sort=False) if trade_frames else pd.DataFrame()
    candidates_all = pd.concat(candidate_frames, ignore_index=True, sort=False) if candidate_frames else pd.DataFrame()
    entry_risk_all = pd.concat(entry_risk_frames, ignore_index=True, sort=False) if entry_risk_frames else pd.DataFrame()

    has_2018_trade = bool(summary["first_2018_trade_fill_date"].astype(str).str.len().gt(0).any())
    has_2019_trade = bool(summary["first_2019_trade_fill_date"].astype(str).str.len().gt(0).any())
    decision = {
        "stage": "Stage771",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "decision": (
            "am40_generates_early_trades" if has_2018_trade or has_2019_trade else "am40_does_not_generate_early_trades"
        ),
        "has_2018_trade": has_2018_trade,
        "has_2019_trade": has_2019_trade,
        "analysis_end": ANALYSIS_END.date().isoformat(),
        "overfit_judgment": (
            "medium-low: this is a predeclared engineering-gate audit, but exact AM40 is research-only and must not be promoted from early-year behavior alone"
        ),
        "continue_value": (
            "yes if AM40 materially restores candidate visibility without creating noisy 2018 churn; next step is full-cycle/monthly-start metrics"
        ),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "year_summary": str(YEAR_PATH),
            "daily": str(DAILY_PATH),
            "trades": str(TRADES_PATH),
            "entry_candidates": str(ENTRY_CANDIDATES_PATH),
            "entry_risk": str(ENTRY_RISK_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    year_summary.to_csv(YEAR_PATH, index=False, encoding="utf-8-sig")
    daily_all.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    trades_all.to_csv(TRADES_PATH, index=False, encoding="utf-8-sig")
    candidates_all.to_csv(ENTRY_CANDIDATES_PATH, index=False, encoding="utf-8-sig")
    entry_risk_all.to_csv(ENTRY_RISK_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(summary, year_summary, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
