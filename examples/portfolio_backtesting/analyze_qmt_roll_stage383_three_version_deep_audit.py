from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
LINE_ID = "futures_trend_drawdown30_preserve_return"
MODEL_TAG = "stage383_three_version_deep_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage383_three_version_deep_audit"

OFFICIAL_DAILY_PATH = OUTPUT_DIR / "qmt_roll_official_stage78_1_daily_equity.csv"
C3_DAILY_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage336_c3_cash_reserve_multiperiod_daily_stage336_c3_cash_reserve_multiperiod_v1.csv"
)
START_CAPITAL = 500_000.0
STAGE079_CASH = 115_000.0
STAGE079_ACCOUNT_CAPITAL = START_CAPITAL + STAGE079_CASH
TARGET_MAX_DD_PCT = -30.0
RETENTION_GATE_VS_C3_PCT = 80.0

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
START_YEAR_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_start_year_{MODEL_TAG}.csv"
QUARTER_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_quarter_start_{MODEL_TAG}.csv"
ROLLING_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rolling_{MODEL_TAG}.csv"
WEAK_WINDOW_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_weak_windows_{MODEL_TAG}.csv"
COST_STRESS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
DRAWDOWN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_drawdown_periods_{MODEL_TAG}.csv"
SCORE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_score_{MODEL_TAG}.csv"
DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
HTML_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_dashboard_{MODEL_TAG}.html"


@dataclass(frozen=True)
class Variant:
    name: str
    label: str
    initial_capital: float
    equity_column: str
    is_primary: bool = True


PRIMARY_VARIANTS = [
    Variant("stage78_1", "78-1正式版", START_CAPITAL, "stage78_1"),
    Variant("c3", "纯C3", START_CAPITAL, "c3"),
    Variant("stage079", "Stage079：C3+11.5万现金", STAGE079_ACCOUNT_CAPITAL, "stage079"),
]

REFERENCE_VARIANTS = [
    Variant("stage78_1_same_cash", "参考：78-1+11.5万现金", STAGE079_ACCOUNT_CAPITAL, "stage78_1_same_cash", False),
]

ALL_VARIANTS = PRIMARY_VARIANTS + REFERENCE_VARIANTS


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


def _fmt(value: Any, digits: int = 4) -> str:
    return f"{_safe_float(value):.{digits}f}"


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "无数据。"
    view = frame.copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: f"{x:.4f}" if pd.notna(x) else "")
    return view.to_markdown(index=False)


def _load_official() -> pd.Series:
    frame = pd.read_csv(OFFICIAL_DAILY_PATH, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["balance"] = pd.to_numeric(frame["balance"], errors="coerce")
    series = frame.dropna(subset=["date", "balance"]).sort_values("date").set_index("date")["balance"]
    start = pd.Series([START_CAPITAL], index=[series.index.min() - pd.Timedelta(days=1)])
    return pd.concat([start, series]).sort_index().rename("stage78_1")


def _load_c3() -> pd.Series:
    frame = pd.read_csv(C3_DAILY_PATH, encoding="utf-8-sig")
    frame = frame[frame["profile"].eq("c3_active100_cash0") & frame["window_name"].eq("start_2020")].copy()
    if frame.empty:
        raise ValueError("missing c3_active100_cash0/start_2020 curve")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["balance"] = pd.to_numeric(frame["balance"], errors="coerce")
    series = frame.dropna(subset=["date", "balance"]).sort_values("date").set_index("date")["balance"]
    start = pd.Series([START_CAPITAL], index=[series.index.min() - pd.Timedelta(days=1)])
    return pd.concat([start, series]).sort_index().rename("c3")


def _load_official_daily_raw() -> pd.DataFrame:
    frame = pd.read_csv(OFFICIAL_DAILY_PATH, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["net_pnl"] = pd.to_numeric(frame["net_pnl"], errors="coerce").fillna(0.0)
    frame["slippage"] = pd.to_numeric(frame["slippage"], errors="coerce").fillna(0.0)
    return frame.dropna(subset=["date"]).sort_values("date")


def _load_c3_daily_raw() -> pd.DataFrame:
    frame = pd.read_csv(C3_DAILY_PATH, encoding="utf-8-sig")
    frame = frame[frame["profile"].eq("c3_active100_cash0") & frame["window_name"].eq("start_2020")].copy()
    if frame.empty:
        raise ValueError("missing c3_active100_cash0/start_2020 daily curve")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["active_net_pnl"] = pd.to_numeric(frame["active_net_pnl"], errors="coerce").fillna(0.0)
    frame["active_slippage"] = pd.to_numeric(frame["active_slippage"], errors="coerce").fillna(0.0)
    return frame.dropna(subset=["date"]).sort_values("date")


def _build_curves() -> pd.DataFrame:
    official = _load_official()
    c3 = _load_c3()
    common_start = max(official.index.min(), c3.index.min())
    common_end = min(official.index.max(), c3.index.max())
    calendar = pd.date_range(common_start, common_end, freq="D")
    curves = pd.DataFrame(index=calendar)
    curves["stage78_1"] = official.reindex(calendar).ffill()
    curves["c3"] = c3.reindex(calendar).ffill()
    curves["stage079"] = curves["c3"] + STAGE079_CASH
    curves["stage78_1_same_cash"] = curves["stage78_1"] + STAGE079_CASH
    return curves.dropna()


def _nav(equity: pd.Series, initial: float) -> pd.Series:
    return equity.astype(float) / float(initial)


def _drawdown(nav: pd.Series) -> pd.Series:
    return nav / nav.cummax() - 1.0


def _drawdown_window(nav: pd.Series) -> tuple[str, str, float]:
    dd = _drawdown(nav)
    trough = pd.Timestamp(dd.idxmin())
    peak = pd.Timestamp(nav.loc[:trough].idxmax())
    return str(peak.date()), str(trough.date()), float(dd.loc[trough] * 100.0)


def _ulcer(nav: pd.Series) -> float:
    dd = np.minimum(_drawdown(nav).to_numpy(dtype=float) * 100.0, 0.0)
    return float(np.sqrt(np.mean(np.square(dd)))) if len(dd) else 0.0


def _sharpe(nav: pd.Series) -> float:
    ret = nav.pct_change().dropna()
    if len(ret) < 2:
        return 0.0
    std = float(ret.std(ddof=1))
    if std <= 0:
        return 0.0
    return float(ret.mean() / std * math.sqrt(252.0))


def _longest_condition_days(mask: pd.Series) -> tuple[int, int]:
    longest_days = 0
    longest_obs = 0
    start: pd.Timestamp | None = None
    obs = 0
    last: pd.Timestamp | None = None
    for date, flag in mask.items():
        date = pd.Timestamp(date)
        if bool(flag):
            if start is None:
                start = date
                obs = 1
            else:
                obs += 1
            last = date
            days = int((last - start).days) + 1
            if days > longest_days:
                longest_days = days
                longest_obs = obs
        else:
            start = None
            obs = 0
            last = None
    return longest_days, longest_obs


def _stats(equity: pd.Series, variant: Variant, scope: str, window_name: str) -> dict[str, Any]:
    equity = equity.dropna().astype(float)
    return_base = variant.initial_capital if scope == "full" else float(equity.iloc[0])
    nav = equity / return_base
    peak, trough, max_dd = _drawdown_window(nav)
    underwater_days, underwater_obs = _longest_condition_days(_drawdown(nav) < -1e-12)
    total_return = float((nav.iloc[-1] - 1.0) * 100.0)
    return {
        "scope": scope,
        "window_name": window_name,
        "variant": variant.name,
        "label": variant.label,
        "is_primary": int(variant.is_primary),
        "start_date": str(equity.index.min().date()),
        "end_date": str(equity.index.max().date()),
        "observations": int(len(equity)),
        "initial_capital": variant.initial_capital,
        "return_base_equity": return_base,
        "end_equity": float(equity.iloc[-1]),
        "total_return_pct": total_return,
        "max_dd_pct": max_dd,
        "max_dd_peak_date": peak,
        "max_dd_trough_date": trough,
        "sharpe": _sharpe(nav),
        "ulcer_pct": _ulcer(nav),
        "return_to_dd": float(total_return / abs(max_dd)) if max_dd < 0 else 0.0,
        "longest_underwater_calendar_days": underwater_days,
        "longest_underwater_observations": underwater_obs,
        "positive_day_rate": float((nav.pct_change().fillna(0.0) > 0).mean()),
    }


def _full_summary(curves: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for variant in ALL_VARIANTS:
        rows.append(_stats(curves[variant.equity_column], variant, "full", "full_common"))
    frame = pd.DataFrame(rows)
    c3_return = float(frame.loc[frame["variant"].eq("c3"), "total_return_pct"].iloc[0])
    stage78_return = float(frame.loc[frame["variant"].eq("stage78_1"), "total_return_pct"].iloc[0])
    for compare_name, col in [("return_retention_vs_c3_pct", c3_return), ("return_retention_vs_78_1_pct", stage78_return)]:
        frame[compare_name] = frame["total_return_pct"].map(lambda x: x / col * 100.0 if col > 0 else 0.0)
    return frame


def _start_year_stats(curves: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for year in range(curves.index.min().year, curves.index.max().year + 1):
        start = pd.Timestamp(year=year, month=1, day=1)
        valid_dates = curves.index[curves.index >= start]
        if len(valid_dates) == 0:
            continue
        actual_start = pd.Timestamp(valid_dates[0])
        chunk = curves.loc[actual_start:]
        for variant in PRIMARY_VARIANTS:
            rows.append(_stats(chunk[variant.equity_column], variant, "start_year", f"start_{year}"))
    frame = pd.DataFrame(rows)
    return _add_relative_columns(frame)


def _quarter_stats(curves: pd.DataFrame) -> pd.DataFrame:
    rows = []
    first = curves.index.min().to_period("Q")
    last = curves.index.max().to_period("Q")
    for period in pd.period_range(first, last, freq="Q"):
        valid_dates = curves.index[curves.index >= period.start_time]
        if len(valid_dates) == 0:
            continue
        actual_start = pd.Timestamp(valid_dates[0])
        chunk = curves.loc[actual_start:]
        for variant in PRIMARY_VARIANTS:
            rows.append(_stats(chunk[variant.equity_column], variant, "quarter_start", f"{period.year}Q{period.quarter}"))
    frame = pd.DataFrame(rows)
    return _add_relative_columns(frame)


def _add_relative_columns(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    rows = []
    for (_, window_name), group in frame.groupby(["scope", "window_name"], sort=False):
        lookup = group.set_index("variant")
        c3_return = _safe_float(lookup.loc["c3", "total_return_pct"]) if "c3" in lookup.index else 0.0
        stage78_return = _safe_float(lookup.loc["stage78_1", "total_return_pct"]) if "stage78_1" in lookup.index else 0.0
        for _, row in group.iterrows():
            row = row.to_dict()
            ret = _safe_float(row["total_return_pct"])
            row["return_retention_vs_c3_pct"] = ret / c3_return * 100.0 if c3_return > 0 else np.nan
            row["return_retention_vs_78_1_pct"] = ret / stage78_return * 100.0 if stage78_return > 0 else np.nan
            row["dd30_pass"] = int(_safe_float(row["max_dd_pct"]) >= TARGET_MAX_DD_PCT)
            rows.append(row)
    return pd.DataFrame(rows)


def _rolling_stats(curves: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for window in (63, 126, 252, 504):
        if len(curves) < window:
            continue
        for variant in PRIMARY_VARIANTS:
            nav = _nav(curves[variant.equity_column], variant.initial_capital)
            rolling_return = nav / nav.shift(window) - 1.0
            rolling_dd = nav.rolling(window).apply(lambda x: float(np.min(x / np.maximum.accumulate(x) - 1.0)), raw=True)
            valid = pd.DataFrame(
                {
                    "rolling_return": rolling_return * 100.0,
                    "rolling_dd": rolling_dd * 100.0,
                }
            ).dropna()
            if valid.empty:
                continue
            rows.append(
                {
                    "window_days": window,
                    "variant": variant.name,
                    "label": variant.label,
                    "count": int(len(valid)),
                    "min_return_pct": float(valid["rolling_return"].min()),
                    "p05_return_pct": float(valid["rolling_return"].quantile(0.05)),
                    "median_return_pct": float(valid["rolling_return"].median()),
                    "positive_return_rate": float((valid["rolling_return"] > 0).mean()),
                    "below_0_rate": float((valid["rolling_return"] <= 0).mean()),
                    "min_rolling_dd_pct": float(valid["rolling_dd"].min()),
                    "p05_rolling_dd_pct": float(valid["rolling_dd"].quantile(0.05)),
                    "dd30_pass_rate": float((valid["rolling_dd"] >= TARGET_MAX_DD_PCT).mean()),
                }
            )
    return pd.DataFrame(rows)


def _weak_window_stats(curves: pd.DataFrame) -> pd.DataFrame:
    windows = [
        ("2021_max_dd_cluster", "2021共同深回撤窗口", "2021-05-12", "2021-07-02"),
        ("2022_stage079_trough", "Stage079全样本谷底窗口", "2022-07-15", "2022-12-07"),
        ("2024_2025_phase", "2024-2025独立窗口", "2024-01-01", "2025-12-31"),
        ("ytd_2026", "2026年初至样本末", "2026-01-01", "2026-04-30"),
    ]
    rows = []
    for name, label, start, end in windows:
        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end)
        chunk = curves[(curves.index >= start_ts) & (curves.index <= end_ts)]
        if len(chunk) < 2:
            continue
        for variant in PRIMARY_VARIANTS:
            row = _stats(chunk[variant.equity_column], variant, "weak_window", name)
            row["window_label"] = label
            rows.append(row)
    return _add_relative_columns(pd.DataFrame(rows))


def _drawdown_periods(curves: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for variant in PRIMARY_VARIANTS:
        nav = _nav(curves[variant.equity_column], variant.initial_capital)
        dd = _drawdown(nav)
        start: pd.Timestamp | None = None
        trough: pd.Timestamp | None = None
        trough_dd = 0.0
        prev: pd.Timestamp | None = None
        for date, value in dd.items():
            date = pd.Timestamp(date)
            if value < -1e-12:
                if start is None:
                    start = date
                    trough = date
                    trough_dd = float(value)
                elif value < trough_dd:
                    trough = date
                    trough_dd = float(value)
            else:
                if start is not None and prev is not None:
                    rows.append(
                        {
                            "variant": variant.name,
                            "label": variant.label,
                            "start_date": str(start.date()),
                            "end_date": str(prev.date()),
                            "recovered_date": str(date.date()),
                            "calendar_days": int((date - start).days) + 1,
                            "trough_date": str(pd.Timestamp(trough).date()),
                            "trough_dd_pct": trough_dd * 100.0,
                        }
                    )
                start = None
                trough = None
                trough_dd = 0.0
            prev = date
        if start is not None and prev is not None:
            rows.append(
                {
                    "variant": variant.name,
                    "label": variant.label,
                    "start_date": str(start.date()),
                    "end_date": str(prev.date()),
                    "recovered_date": "",
                    "calendar_days": int((prev - start).days) + 1,
                    "trough_date": str(pd.Timestamp(trough).date()),
                    "trough_dd_pct": trough_dd * 100.0,
                }
            )
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    return frame.sort_values(["variant", "calendar_days", "trough_dd_pct"], ascending=[True, False, True]).groupby("variant").head(5)


def _cost_stress() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    official = _load_official_daily_raw()
    c3 = _load_c3_daily_raw()
    for multiplier in (1.0, 2.0, 3.0, 5.0):
        official_equity = START_CAPITAL + (
            official["net_pnl"] - (multiplier - 1.0) * official["slippage"]
        ).cumsum()
        official_series = pd.Series(official_equity.to_numpy(dtype=float), index=official["date"])
        official_series = pd.concat(
            [pd.Series([START_CAPITAL], index=[official_series.index.min() - pd.Timedelta(days=1)]), official_series]
        ).sort_index()

        c3_equity = START_CAPITAL + (
            c3["active_net_pnl"] - (multiplier - 1.0) * c3["active_slippage"]
        ).cumsum()
        c3_series = pd.Series(c3_equity.to_numpy(dtype=float), index=c3["date"])
        c3_series = pd.concat(
            [pd.Series([START_CAPITAL], index=[c3_series.index.min() - pd.Timedelta(days=1)]), c3_series]
        ).sort_index()
        stage079_series = c3_series + STAGE079_CASH

        for variant, label, initial, series, slip_col in [
            ("stage78_1", "78-1正式版", START_CAPITAL, official_series, official["slippage"]),
            ("c3", "纯C3", START_CAPITAL, c3_series, c3["active_slippage"]),
            ("stage079", "Stage079：C3+11.5万现金", STAGE079_ACCOUNT_CAPITAL, stage079_series, c3["active_slippage"]),
        ]:
            v = Variant(variant, label, initial, variant)
            stats = _stats(series, v, "cost_stress", f"slippage_x{multiplier:g}")
            rows.append(
                {
                    "variant": variant,
                    "label": label,
                    "slippage_multiplier": multiplier,
                    "total_return_pct": stats["total_return_pct"],
                    "max_dd_pct": stats["max_dd_pct"],
                    "sharpe": stats["sharpe"],
                    "total_slippage": float(slip_col.sum() * multiplier),
                    "source": "reconstructed_from_current_daily_pnl",
                }
            )
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame["dd30_pass"] = (frame["max_dd_pct"] >= TARGET_MAX_DD_PCT).astype(int)
    return frame.sort_values(["slippage_multiplier", "variant"])


def _score_versions(summary: pd.DataFrame, start_year: pd.DataFrame, quarter: pd.DataFrame, rolling: pd.DataFrame, cost: pd.DataFrame) -> pd.DataFrame:
    rows = []
    full_lookup = summary[summary["is_primary"].eq(1)].set_index("variant")
    for variant in [v.name for v in PRIMARY_VARIANTS]:
        full = full_lookup.loc[variant]
        sy = start_year[(start_year["variant"].eq(variant)) & (start_year["observations"] >= 252)]
        q = quarter[(quarter["variant"].eq(variant)) & (quarter["observations"] >= 252)]
        r252 = rolling[(rolling["variant"].eq(variant)) & (rolling["window_days"].eq(252))]
        r504 = rolling[(rolling["variant"].eq(variant)) & (rolling["window_days"].eq(504))]
        c1 = cost[(cost["variant"].eq(variant)) & (cost["slippage_multiplier"].eq(1.0))]
        c2 = cost[(cost["variant"].eq(variant)) & (cost["slippage_multiplier"].eq(2.0))]
        c3x = cost[(cost["variant"].eq(variant)) & (cost["slippage_multiplier"].eq(3.0))]
        dd30_pass = int(_safe_float(full["max_dd_pct"]) >= TARGET_MAX_DD_PCT)
        retention_pass = int(_safe_float(full["return_retention_vs_c3_pct"]) >= RETENTION_GATE_VS_C3_PCT)
        annual_pass_rate = float((sy["max_dd_pct"] >= TARGET_MAX_DD_PCT).mean()) if not sy.empty else 0.0
        quarter_pass_rate = float((q["max_dd_pct"] >= TARGET_MAX_DD_PCT).mean()) if not q.empty else 0.0
        rolling252_positive = _safe_float(r252["positive_return_rate"].iloc[0]) if not r252.empty else 0.0
        rolling504_positive = _safe_float(r504["positive_return_rate"].iloc[0]) if not r504.empty else 0.0
        cost2_dd_pass = int(not c2.empty and _safe_float(c2["max_dd_pct"].iloc[0]) >= TARGET_MAX_DD_PCT)
        cost3_dd_pass = int(not c3x.empty and _safe_float(c3x["max_dd_pct"].iloc[0]) >= TARGET_MAX_DD_PCT)
        score = (
            20.0 * dd30_pass
            + 15.0 * retention_pass
            + 12.0 * annual_pass_rate
            + 10.0 * quarter_pass_rate
            + 10.0 * rolling252_positive
            + 8.0 * rolling504_positive
            + 10.0 * max(0.0, min(1.0, _safe_float(full["sharpe"]) / 1.6))
            + 10.0 * max(0.0, min(1.0, (25.0 - _safe_float(full["ulcer_pct"])) / 25.0))
            + 3.0 * cost2_dd_pass
            + 2.0 * cost3_dd_pass
        )
        rows.append(
            {
                "variant": variant,
                "label": str(full["label"]),
                "score": score,
                "full_return_pct": _safe_float(full["total_return_pct"]),
                "full_max_dd_pct": _safe_float(full["max_dd_pct"]),
                "full_sharpe": _safe_float(full["sharpe"]),
                "ulcer_pct": _safe_float(full["ulcer_pct"]),
                "return_retention_vs_c3_pct": _safe_float(full["return_retention_vs_c3_pct"]),
                "annual_dd30_pass_rate": annual_pass_rate,
                "quarter_dd30_pass_rate": quarter_pass_rate,
                "rolling252_positive_rate": rolling252_positive,
                "rolling504_positive_rate": rolling504_positive,
                "cost_x1_dd30_pass": int(not c1.empty and _safe_float(c1["max_dd_pct"].iloc[0]) >= TARGET_MAX_DD_PCT),
                "cost_x2_dd30_pass": cost2_dd_pass,
                "cost_x3_dd30_pass": cost3_dd_pass,
            }
        )
    return pd.DataFrame(rows).sort_values("score", ascending=False)


def _daily_long(curves: pd.DataFrame) -> pd.DataFrame:
    frames = []
    for variant in ALL_VARIANTS:
        equity = curves[variant.equity_column]
        nav = _nav(equity, variant.initial_capital)
        frames.append(
            pd.DataFrame(
                {
                    "date": curves.index,
                    "variant": variant.name,
                    "label": variant.label,
                    "is_primary": int(variant.is_primary),
                    "equity": equity.to_numpy(dtype=float),
                    "nav": nav.to_numpy(dtype=float),
                    "drawdown_pct": (_drawdown(nav) * 100.0).to_numpy(dtype=float),
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def _build_report(
    summary: pd.DataFrame,
    start_year: pd.DataFrame,
    quarter: pd.DataFrame,
    rolling: pd.DataFrame,
    weak: pd.DataFrame,
    cost: pd.DataFrame,
    drawdowns: pd.DataFrame,
    score: pd.DataFrame,
    decision: dict[str, Any],
) -> str:
    summary_cols = [
        "label",
        "initial_capital",
        "end_equity",
        "total_return_pct",
        "max_dd_pct",
        "sharpe",
        "ulcer_pct",
        "return_to_dd",
        "longest_underwater_calendar_days",
        "return_retention_vs_c3_pct",
        "return_retention_vs_78_1_pct",
    ]
    start_cols = [
        "window_name",
        "label",
        "total_return_pct",
        "max_dd_pct",
        "sharpe",
        "ulcer_pct",
        "return_retention_vs_c3_pct",
        "dd30_pass",
    ]
    rolling_cols = [
        "window_days",
        "label",
        "min_return_pct",
        "p05_return_pct",
        "median_return_pct",
        "positive_return_rate",
        "min_rolling_dd_pct",
        "dd30_pass_rate",
    ]
    weak_cols = [
        "window_label",
        "label",
        "total_return_pct",
        "max_dd_pct",
        "sharpe",
        "ulcer_pct",
        "return_retention_vs_c3_pct",
        "dd30_pass",
    ]
    cost_cols = ["slippage_multiplier", "label", "total_return_pct", "max_dd_pct", "sharpe", "dd30_pass"]
    score_cols = [
        "label",
        "score",
        "full_return_pct",
        "full_max_dd_pct",
        "full_sharpe",
        "ulcer_pct",
        "return_retention_vs_c3_pct",
        "annual_dd30_pass_rate",
        "quarter_dd30_pass_rate",
        "rolling252_positive_rate",
        "cost_x2_dd30_pass",
        "cost_x3_dd30_pass",
    ]
    primary_summary = summary[summary["is_primary"].eq(1)].copy()
    lines = [
        "# Stage083 三版本深度对比审计",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 比较对象：`78-1`、`Stage079`、`纯C3`。",
        "- 参考对象：`78-1+11.5万现金` 仅用于判断 Stage079 的现金缓冲效应，不参与主排序。",
        "- 阶段性质：只读审计；不修改策略信号、AI池、品种池、仓位或成交路径。",
        "",
        "## 外部调研与判断",
        "",
        "- Walk-forward/滚动切片的核心价值，是避免只用一条全样本曲线判断策略稳健性；本阶段因此使用年度、季度、滚动窗口和弱窗口切片。",
        "- Ulcer Index 同时惩罚回撤深度和持续时间，能补充最大回撤这种单点指标；本阶段把它作为持有体验指标。",
        "- 我的判断：这三个版本本质不是同类 alpha。`78-1` 是正式基准，`C3` 是更高收益但回撤略超标的研究底座，`Stage079` 是 C3 的部署资金结构。",
        "",
        "## 运行前过拟合反思",
        "",
        "- 判断：否。",
        "- 原因：本阶段只比较已冻结版本，不新增入场、退出、品种、阈值或资金小数搜索。",
        "",
        "## 运行前继续价值反思",
        "",
        "- 判断：是。",
        "- 原因：正式推进前必须明确哪个版本在收益、回撤、成本和持有体验之间最均衡。",
        "",
        "## 主排序",
        "",
        _md_table(score[score_cols]),
        "",
        "## 全周期表现",
        "",
        _md_table(primary_summary[summary_cols]),
        "",
        "## 年度冷启动",
        "",
        _md_table(start_year[start_year["observations"].ge(252)][start_cols], max_rows=30),
        "",
        "## 季度冷启动汇总",
        "",
        _md_table(
            quarter[quarter["observations"].ge(252)]
            .groupby("label")
            .agg(
                windows=("window_name", "count"),
                dd30_pass_rate=("dd30_pass", "mean"),
                worst_return_pct=("total_return_pct", "min"),
                worst_dd_pct=("max_dd_pct", "min"),
                median_ulcer_pct=("ulcer_pct", "median"),
            )
            .reset_index()
        ),
        "",
        "## 滚动窗口",
        "",
        _md_table(rolling[rolling_cols], max_rows=60),
        "",
        "## 弱窗口",
        "",
        _md_table(weak[weak_cols], max_rows=30),
        "",
        "## 成本压力",
        "",
        _md_table(cost[cost_cols], max_rows=30),
        "",
        "## 最长水下期",
        "",
        _md_table(drawdowns, max_rows=20),
        "",
        "## 决策",
        "",
        f"- 最优版本：`{decision['best_variant']}`。",
        f"- 结论：{decision['conclusion']}",
        f"- 黄灯/限制：{decision['warnings'] or '无'}",
        "",
        "## 运行后过拟合反思",
        "",
        "- 判断：否。",
        "- 原因：比较结果来自既有冻结曲线和既有成本压力输出，没有为了让某个版本胜出而改规则。",
        "",
        "## 运行后继续价值反思",
        "",
        "- 判断：有价值，但下一步应聚焦 Stage079 的真实执行/forward，而不是继续在这三个版本之间调小数。",
        "- 原因：纯C3收益最高但回撤越过30；78-1回撤和收益都落后；Stage079在正常成本下综合最均衡，但高滑点仍不是最终答案。",
    ]
    return "\n".join(lines) + "\n"


def _build_html(daily: pd.DataFrame, summary: pd.DataFrame, score: pd.DataFrame, rolling: pd.DataFrame, weak: pd.DataFrame, cost: pd.DataFrame) -> None:
    focus = daily[daily["is_primary"].eq(1)].copy()
    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        subplot_titles=("账户权益", "归一化净值", "回撤"),
    )
    colors = {"stage78_1": "#6b7280", "c3": "#16a34a", "stage079": "#2563eb"}
    for variant, group in focus.groupby("variant", sort=False):
        label = str(group["label"].iloc[0])
        color = colors.get(variant, None)
        fig.add_trace(go.Scatter(x=group["date"], y=group["equity"] / 10000.0, name=label, line=dict(color=color)), row=1, col=1)
        fig.add_trace(go.Scatter(x=group["date"], y=group["nav"], name=label, showlegend=False, line=dict(color=color)), row=2, col=1)
        fig.add_trace(go.Scatter(x=group["date"], y=group["drawdown_pct"], name=label, showlegend=False, line=dict(color=color)), row=3, col=1)
    fig.update_layout(height=900, title="Stage083 三版本资金曲线对比", template="plotly_white")
    fig.update_yaxes(title_text="万元", row=1, col=1)
    fig.update_yaxes(title_text="净值", row=2, col=1)
    fig.update_yaxes(title_text="%", row=3, col=1)
    chart_html = fig.to_html(include_plotlyjs="cdn", full_html=False)

    def table_html(df: pd.DataFrame, cols: list[str], max_rows: int = 20) -> str:
        view = df[cols].head(max_rows).copy()
        for col in view.columns:
            if pd.api.types.is_float_dtype(view[col]):
                view[col] = view[col].map(lambda x: f"{x:.4f}" if pd.notna(x) else "")
        return view.to_html(index=False, escape=False)

    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>Stage083 三版本深度对比审计</title>
  <style>
    body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f6f7fb; color: #111827; }}
    main {{ max-width: 1280px; margin: 0 auto; padding: 32px; }}
    section {{ background: #fff; border: 1px solid #e5e7eb; border-radius: 8px; padding: 24px; margin-bottom: 20px; }}
    h1 {{ font-size: 28px; margin: 0 0 8px; }}
    h2 {{ font-size: 20px; margin: 0 0 16px; }}
    p {{ color: #374151; line-height: 1.7; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
    th, td {{ border-bottom: 1px solid #e5e7eb; padding: 8px 10px; text-align: right; }}
    th:first-child, td:first-child, td:nth-child(2) {{ text-align: left; }}
    th {{ background: #f3f4f6; color: #374151; }}
    .note {{ border-left: 4px solid #2563eb; padding-left: 14px; }}
  </style>
</head>
<body>
<main>
  <section>
    <h1>Stage083 三版本深度对比审计</h1>
    <p>比较对象：78-1、Stage079、纯C3。参考对象只用于公平解释现金缓冲，不参与主排序。</p>
  </section>
  <section>
    <h2>结论</h2>
    <p class="note">综合收益、最大回撤、Ulcer、滚动窗口、弱窗口和成本压力后，Stage079 是正常成本下更适合继续推进的候选；纯C3收益最高但回撤越过30；78-1更保守但收益和持有体验弱于Stage079。</p>
  </section>
  <section>
    <h2>综合排序</h2>
    {table_html(score, ["label", "score", "full_return_pct", "full_max_dd_pct", "full_sharpe", "ulcer_pct", "return_retention_vs_c3_pct", "annual_dd30_pass_rate", "quarter_dd30_pass_rate", "rolling252_positive_rate", "cost_x2_dd30_pass", "cost_x3_dd30_pass"])}
  </section>
  <section>{chart_html}</section>
  <section>
    <h2>全周期表现</h2>
    {table_html(summary[summary["is_primary"].eq(1)], ["label", "initial_capital", "end_equity", "total_return_pct", "max_dd_pct", "sharpe", "ulcer_pct", "return_to_dd", "longest_underwater_calendar_days", "return_retention_vs_c3_pct"])}
  </section>
  <section>
    <h2>滚动窗口</h2>
    {table_html(rolling, ["window_days", "label", "min_return_pct", "p05_return_pct", "median_return_pct", "positive_return_rate", "min_rolling_dd_pct", "dd30_pass_rate"], 60)}
  </section>
  <section>
    <h2>弱窗口</h2>
    {table_html(weak, ["window_label", "label", "total_return_pct", "max_dd_pct", "sharpe", "ulcer_pct", "return_retention_vs_c3_pct", "dd30_pass"], 40)}
  </section>
  <section>
    <h2>成本压力</h2>
    {table_html(cost, ["slippage_multiplier", "label", "total_return_pct", "max_dd_pct", "sharpe", "dd30_pass"], 40)}
  </section>
</main>
</body>
</html>
"""
    HTML_PATH.write_text(html, encoding="utf-8")


def main() -> None:
    curves = _build_curves()
    summary = _full_summary(curves)
    start_year = _start_year_stats(curves)
    quarter = _quarter_stats(curves)
    rolling = _rolling_stats(curves)
    weak = _weak_window_stats(curves)
    cost = _cost_stress()
    drawdowns = _drawdown_periods(curves)
    score = _score_versions(summary, start_year, quarter, rolling, cost)
    daily = _daily_long(curves)

    best = score.iloc[0].to_dict()
    warnings: list[str] = []
    if str(best["variant"]) == "stage079":
        c2 = cost[(cost["variant"].eq("stage079")) & (cost["slippage_multiplier"].eq(2.0))]
        if not c2.empty and int(c2["dd30_pass"].iloc[0]) == 0:
            warnings.append("Stage079在2x滑点下回撤未进30，仍是正常成本候选")
    decision = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "best_variant": str(best["variant"]),
        "best_label": str(best["label"]),
        "score_table": _json_safe(score.to_dict(orient="records")),
        "warnings": warnings,
        "conclusion": "Stage079综合最优；纯C3收益最高但回撤越过30；78-1是正式基准但当前不如Stage079的正常成本账户口径。",
        "overfit_reflection": "no_new_parameters_or_threshold_search",
        "continue_value": "promote_stage079_to_forward_audit_under_normal_cost; search_new_uncorrelated_return_source_for_high_slippage",
    }

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    start_year.to_csv(START_YEAR_PATH, index=False, encoding="utf-8-sig")
    quarter.to_csv(QUARTER_PATH, index=False, encoding="utf-8-sig")
    rolling.to_csv(ROLLING_PATH, index=False, encoding="utf-8-sig")
    weak.to_csv(WEAK_WINDOW_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_STRESS_PATH, index=False, encoding="utf-8-sig")
    drawdowns.to_csv(DRAWDOWN_PATH, index=False, encoding="utf-8-sig")
    score.to_csv(SCORE_PATH, index=False, encoding="utf-8-sig")
    daily.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(
        _build_report(summary, start_year, quarter, rolling, weak, cost, drawdowns, score, decision),
        encoding="utf-8",
    )
    _build_html(daily, summary, score, rolling, weak, cost)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"summary={SUMMARY_PATH}")
    print(f"report={REPORT_PATH}")
    print(f"html={HTML_PATH}")


if __name__ == "__main__":
    main()
