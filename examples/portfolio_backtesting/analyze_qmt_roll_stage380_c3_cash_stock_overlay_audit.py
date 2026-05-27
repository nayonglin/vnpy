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


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
MODEL_TAG = "stage380_c3_cash_stock_overlay_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage380_c3_cash_stock_overlay_audit"
LINE_ID = "futures_trend_drawdown30_preserve_return"

OFFICIAL_DAILY_PATH = OUTPUT_DIR / "qmt_roll_official_stage78_1_daily_equity.csv"
C3_DAILY_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage336_c3_cash_reserve_multiperiod_daily_stage336_c3_cash_reserve_multiperiod_v1.csv"
)
STAGE075_DAILY_PATH = (
    OUTPUT_DIR / "qmt_roll_stage375_independent_300k_stock_combo_daily_stage375_independent_300k_stock_combo_v1.csv"
)

FUTURES_CAPITAL = 500_000.0
STOCK_CAPITAL = 300_000.0
EXTERNAL_CASH = 115_000.0
TOTAL_CAPITAL = FUTURES_CAPITAL + STOCK_CAPITAL + EXTERNAL_CASH
SAME_CAPITAL_CASH = STOCK_CAPITAL + EXTERNAL_CASH
TARGET_MAX_DD_PCT = -30.0
ROLLING_WINDOWS = (252, 504)
MIN_HORIZON_DAYS = 252

WINDOW_STATS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_stats_{MODEL_TAG}.csv"
PAIRED_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_paired_windows_{MODEL_TAG}.csv"
AGGREGATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_aggregate_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
HTML_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.html"


@dataclass(frozen=True)
class WindowStats:
    scope: str
    window_name: str
    start_date: str
    end_date: str
    horizon_days: int
    variant: str
    label: str
    initial_capital: float
    end_equity: float
    total_return_pct: float
    absolute_profit: float
    max_dd_percent: float
    max_dd_peak_date: str
    max_dd_trough_date: str
    sharpe: float
    ulcer: float
    longest_underwater_days: int
    positive_day_rate: float
    worst_252d_return_pct: float | None
    worst_504d_return_pct: float | None


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


def _drawdown(nav: pd.Series) -> pd.Series:
    return nav / nav.cummax() - 1.0


def _drawdown_window(nav: pd.Series) -> tuple[pd.Timestamp, pd.Timestamp, float]:
    dd = _drawdown(nav)
    if dd.empty:
        empty = pd.Timestamp("1900-01-01")
        return empty, empty, 0.0
    trough = pd.Timestamp(dd.idxmin())
    peak = pd.Timestamp(nav.loc[:trough].idxmax())
    return peak, trough, float(dd.loc[trough] * 100.0)


def _ulcer(nav: pd.Series) -> float:
    if nav.empty:
        return 0.0
    dd_pct = _drawdown(nav) * 100.0
    return float(np.sqrt(np.mean(np.square(np.minimum(dd_pct, 0.0)))))


def _longest_underwater(nav: pd.Series) -> int:
    longest = 0
    current = 0
    for value in _drawdown(nav):
        if value < -1e-12:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return int(longest)


def _annualized_sharpe(daily_ret: pd.Series) -> float:
    daily_ret = daily_ret.dropna().astype(float)
    if len(daily_ret) < 2:
        return 0.0
    std = float(daily_ret.std(ddof=1))
    if std <= 0.0:
        return 0.0
    return float(daily_ret.mean() / std * math.sqrt(252.0))


def _stats_from_equity(
    equity: pd.Series,
    *,
    scope: str,
    window_name: str,
    variant: str,
    label: str,
) -> WindowStats:
    series = equity.dropna().astype(float)
    if series.empty:
        raise ValueError(f"empty equity series: {scope}/{window_name}/{variant}")
    initial = float(series.iloc[0])
    nav = series / initial
    daily_ret = nav.pct_change().fillna(0.0)
    peak, trough, max_dd_pct = _drawdown_window(nav)
    rolling: dict[int, float] = {}
    for window in ROLLING_WINDOWS:
        if len(nav) > window:
            rolling[window] = float((nav / nav.shift(window) - 1.0).min() * 100.0)
        else:
            rolling[window] = np.nan
    return WindowStats(
        scope=scope,
        window_name=window_name,
        start_date=str(pd.Timestamp(series.index.min()).date()),
        end_date=str(pd.Timestamp(series.index.max()).date()),
        horizon_days=int(len(series)),
        variant=variant,
        label=label,
        initial_capital=initial,
        end_equity=float(series.iloc[-1]),
        total_return_pct=float((nav.iloc[-1] - 1.0) * 100.0),
        absolute_profit=float(series.iloc[-1] - initial),
        max_dd_percent=max_dd_pct,
        max_dd_peak_date=str(peak.date()),
        max_dd_trough_date=str(trough.date()),
        sharpe=_annualized_sharpe(daily_ret),
        ulcer=_ulcer(nav),
        longest_underwater_days=_longest_underwater(nav),
        positive_day_rate=float((daily_ret > 0.0).mean()),
        worst_252d_return_pct=rolling[252],
        worst_504d_return_pct=rolling[504],
    )


def _load_official78() -> pd.DataFrame:
    if not OFFICIAL_DAILY_PATH.exists():
        raise FileNotFoundError(OFFICIAL_DAILY_PATH)
    frame = pd.read_csv(OFFICIAL_DAILY_PATH, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["official78_equity"] = pd.to_numeric(frame["balance"], errors="coerce")
    frame = frame[["date", "official78_equity"]].dropna().sort_values("date")
    start_row = pd.DataFrame(
        [{"date": frame["date"].iloc[0] - pd.Timedelta(days=1), "official78_equity": FUTURES_CAPITAL}]
    )
    return pd.concat([start_row, frame], ignore_index=True)


def _load_c3() -> pd.DataFrame:
    if not C3_DAILY_PATH.exists():
        raise FileNotFoundError(C3_DAILY_PATH)
    frame = pd.read_csv(C3_DAILY_PATH, encoding="utf-8-sig")
    frame = frame[frame["profile"].eq("c3_active100_cash0") & frame["window_name"].eq("start_2020")].copy()
    if frame.empty:
        raise ValueError("missing C3 start_2020 curve")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["c3_equity"] = pd.to_numeric(frame["balance"], errors="coerce")
    frame = frame[["date", "c3_equity"]].dropna().sort_values("date")
    start_row = pd.DataFrame([{"date": frame["date"].iloc[0] - pd.Timedelta(days=1), "c3_equity": FUTURES_CAPITAL}])
    return pd.concat([start_row, frame], ignore_index=True)


def _load_stock_300k() -> pd.DataFrame:
    if not STAGE075_DAILY_PATH.exists():
        raise FileNotFoundError(STAGE075_DAILY_PATH)
    frame = pd.read_csv(STAGE075_DAILY_PATH, encoding="utf-8-sig")
    frame = frame[
        frame["window_name"].eq("full_2020_common") & frame["variant"].eq("B_stock_30w")
    ].copy()
    if frame.empty:
        raise ValueError("missing Stage075 stock 300k curve")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["stock_300k_equity"] = pd.to_numeric(frame["equity"], errors="coerce")
    frame = frame[["date", "stock_300k_equity"]].dropna().sort_values("date")
    start_row = pd.DataFrame(
        [{"date": frame["date"].iloc[0] - pd.Timedelta(days=1), "stock_300k_equity": STOCK_CAPITAL}]
    )
    return pd.concat([start_row, frame], ignore_index=True)


def _load_curves() -> pd.DataFrame:
    official = _load_official78()
    c3 = _load_c3()
    stock = _load_stock_300k()
    merged = pd.merge(official, c3, on="date", how="inner").sort_values("date")
    end_date = min(pd.Timestamp(merged["date"].max()), pd.Timestamp(stock["date"].max()))
    merged = merged[merged["date"] <= end_date].copy()
    stock = stock[stock["date"] <= end_date].copy()
    merged = pd.merge_asof(
        merged.sort_values("date"),
        stock.sort_values("date"),
        on="date",
        direction="backward",
    )
    merged["stock_300k_equity"] = merged["stock_300k_equity"].ffill().fillna(STOCK_CAPITAL)

    merged["official78_plus_415k_cash_equity"] = merged["official78_equity"] + SAME_CAPITAL_CASH
    merged["c3_plus_415k_cash_equity"] = merged["c3_equity"] + SAME_CAPITAL_CASH
    merged["c3_plus_115k_cash_equity"] = merged["c3_equity"] + EXTERNAL_CASH
    merged["c3_plus_300k_stock_equity"] = merged["c3_equity"] + merged["stock_300k_equity"]
    merged["c3_plus_300k_stock_115k_cash_equity"] = (
        merged["c3_equity"] + merged["stock_300k_equity"] + EXTERNAL_CASH
    )
    merged.set_index(pd.DatetimeIndex(merged["date"]), inplace=True)
    return merged


CURVE_SPECS = {
    "official78_50w": ("78-1 50万", "official78_equity"),
    "official78_plus_415k_cash": ("78-1 50万 + 41.5万现金", "official78_plus_415k_cash_equity"),
    "c3_50w": ("C3 50万", "c3_equity"),
    "c3_plus_415k_cash": ("C3 50万 + 41.5万现金", "c3_plus_415k_cash_equity"),
    "c3_plus_115k_cash": ("C3 50万 + 11.5万现金", "c3_plus_115k_cash_equity"),
    "stock_300k": ("30万股票账户", "stock_300k_equity"),
    "c3_plus_300k_stock": ("C3 50万 + 30万股票账户", "c3_plus_300k_stock_equity"),
    "c3_plus_300k_stock_115k_cash": (
        "C3 50万 + 30万股票账户 + 11.5万现金",
        "c3_plus_300k_stock_115k_cash_equity",
    ),
}


def _first_available_date(index: pd.DatetimeIndex, target: pd.Timestamp) -> pd.Timestamp | None:
    candidates = index[index >= target]
    if len(candidates) == 0:
        return None
    return pd.Timestamp(candidates[0])


def _annual_starts(index: pd.DatetimeIndex) -> list[tuple[str, pd.Timestamp]]:
    rows: list[tuple[str, pd.Timestamp]] = []
    for year in range(int(index.min().year), int(index.max().year) + 1):
        start = _first_available_date(index, pd.Timestamp(year=year, month=1, day=1))
        if start is not None:
            rows.append((f"start_{year}", start))
    return rows


def _quarter_starts(index: pd.DatetimeIndex) -> list[tuple[str, pd.Timestamp]]:
    rows: list[tuple[str, pd.Timestamp]] = []
    first = pd.Timestamp(index.min()).to_period("Q")
    last = pd.Timestamp(index.max()).to_period("Q")
    for period in pd.period_range(first, last, freq="Q"):
        start = _first_available_date(index, period.start_time)
        if start is not None:
            rows.append((f"{period.year}Q{period.quarter}", start))
    return rows


def _build_window_stats(df: pd.DataFrame, scope: str, starts: list[tuple[str, pd.Timestamp]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for window_name, start in starts:
        chunk = df[df.index >= start]
        if chunk.empty:
            continue
        for variant, (label, column) in CURVE_SPECS.items():
            stats = _stats_from_equity(
                chunk[column],
                scope=scope,
                window_name=window_name,
                variant=variant,
                label=label,
            )
            rows.append(stats.__dict__)
    return pd.DataFrame(rows)


def _build_rolling_stats(df: pd.DataFrame, window: int) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    index = pd.DatetimeIndex(df.index)
    for start_pos in range(0, max(0, len(index) - window + 1)):
        start = index[start_pos]
        end = index[start_pos + window - 1]
        chunk = df[(df.index >= start) & (df.index <= end)]
        window_name = f"{window}d_{start.date()}_{end.date()}"
        for variant, (label, column) in CURVE_SPECS.items():
            stats = _stats_from_equity(
                chunk[column],
                scope=f"rolling_{window}d",
                window_name=window_name,
                variant=variant,
                label=label,
            )
            rows.append(stats.__dict__)
    return pd.DataFrame(rows)


def _build_paired(stats: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    candidate_key = "c3_plus_300k_stock_115k_cash"
    cash_key = "c3_plus_415k_cash"
    c3_cash_key = "c3_plus_115k_cash"
    official_cash_key = "official78_plus_415k_cash"
    c3_key = "c3_50w"
    for (scope, window_name), group in stats.groupby(["scope", "window_name"], sort=False):
        lookup = group.set_index("variant")
        required = {candidate_key, cash_key, c3_cash_key, official_cash_key, c3_key}
        if not required.issubset(set(lookup.index)):
            continue
        candidate = lookup.loc[candidate_key]
        cash = lookup.loc[cash_key]
        c3_cash = lookup.loc[c3_cash_key]
        official_cash = lookup.loc[official_cash_key]
        c3 = lookup.loc[c3_key]
        c3_profit = float(c3["absolute_profit"])
        candidate_profit = float(candidate["absolute_profit"])
        rows.append(
            {
                "scope": scope,
                "window_name": window_name,
                "start_date": candidate["start_date"],
                "end_date": candidate["end_date"],
                "horizon_days": int(candidate["horizon_days"]),
                "candidate_return_pct": float(candidate["total_return_pct"]),
                "candidate_max_dd_pct": float(candidate["max_dd_percent"]),
                "candidate_ulcer": float(candidate["ulcer"]),
                "candidate_abs_profit": candidate_profit,
                "profit_retention_vs_c3_pct": candidate_profit / c3_profit * 100.0 if c3_profit > 0 else np.nan,
                "return_edge_vs_same_cap_cash_pp": float(candidate["total_return_pct"])
                - float(cash["total_return_pct"]),
                "dd_edge_vs_same_cap_cash_pp": float(candidate["max_dd_percent"]) - float(cash["max_dd_percent"]),
                "ulcer_reduction_vs_same_cap_cash_pct": (
                    (float(cash["ulcer"]) - float(candidate["ulcer"])) / float(cash["ulcer"]) * 100.0
                    if float(cash["ulcer"]) > 0
                    else np.nan
                ),
                "return_edge_vs_stage079_pp": float(candidate["total_return_pct"])
                - float(c3_cash["total_return_pct"]),
                "dd_edge_vs_stage079_pp": float(candidate["max_dd_percent"]) - float(c3_cash["max_dd_percent"]),
                "ulcer_edge_vs_stage079_pct": (
                    (float(c3_cash["ulcer"]) - float(candidate["ulcer"])) / float(c3_cash["ulcer"]) * 100.0
                    if float(c3_cash["ulcer"]) > 0
                    else np.nan
                ),
                "return_edge_vs_official_same_cap_pp": float(candidate["total_return_pct"])
                - float(official_cash["total_return_pct"]),
                "dd_improvement_vs_official_same_cap_pp": float(candidate["max_dd_percent"])
                - float(official_cash["max_dd_percent"]),
                "dd30_pass": bool(float(candidate["max_dd_percent"]) >= TARGET_MAX_DD_PCT),
                "beats_same_cap_cash_return": bool(
                    float(candidate["total_return_pct"]) > float(cash["total_return_pct"])
                ),
                "smoother_than_same_cap_cash": bool(float(candidate["ulcer"]) < float(cash["ulcer"])),
                "smoother_than_stage079": bool(float(candidate["ulcer"]) < float(c3_cash["ulcer"])),
                "smoother_than_official_same_cap": bool(float(candidate["ulcer"]) < float(official_cash["ulcer"])),
            }
        )
    return pd.DataFrame(rows)


def _aggregate(paired: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for scope, group in paired.groupby("scope", sort=False):
        eligible = group[group["horizon_days"] >= MIN_HORIZON_DAYS].copy()
        if eligible.empty:
            continue
        rows.append(
            {
                "scope": scope,
                "eligible_windows": int(len(eligible)),
                "dd30_pass_windows": int(eligible["dd30_pass"].sum()),
                "dd30_pass_rate": float(eligible["dd30_pass"].mean()),
                "same_cap_cash_return_win_count": int(eligible["beats_same_cap_cash_return"].sum()),
                "same_cap_cash_return_win_rate": float(eligible["beats_same_cap_cash_return"].mean()),
                "smoother_than_stage079_count": int(eligible["smoother_than_stage079"].sum()),
                "smoother_than_stage079_rate": float(eligible["smoother_than_stage079"].mean()),
                "smoother_than_official_same_cap_count": int(eligible["smoother_than_official_same_cap"].sum()),
                "smoother_than_official_same_cap_rate": float(
                    eligible["smoother_than_official_same_cap"].mean()
                ),
                "worst_return_pct": float(eligible["candidate_return_pct"].min()),
                "worst_max_dd_pct": float(eligible["candidate_max_dd_pct"].min()),
                "worst_return_edge_vs_same_cap_cash_pp": float(
                    eligible["return_edge_vs_same_cap_cash_pp"].min()
                ),
                "worst_return_edge_vs_stage079_pp": float(eligible["return_edge_vs_stage079_pp"].min()),
                "worst_profit_retention_vs_c3_pct": float(eligible["profit_retention_vs_c3_pct"].min()),
            }
        )
    return pd.DataFrame(rows)


def _build_decision(paired: pd.DataFrame, aggregate: pd.DataFrame) -> dict[str, Any]:
    full = paired[(paired["scope"] == "full") & (paired["window_name"] == "full_2020_2026")]
    full_row = full.iloc[0].to_dict() if not full.empty else {}
    annual = aggregate[aggregate["scope"] == "annual_start"]
    quarter = aggregate[aggregate["scope"] == "quarter_start"]
    rolling252 = aggregate[aggregate["scope"] == "rolling_252d"]
    rolling504 = aggregate[aggregate["scope"] == "rolling_504d"]

    red_reasons: list[str] = []
    yellow_reasons: list[str] = []
    if full_row and not bool(full_row["dd30_pass"]):
        red_reasons.append("全样本最大回撤未压入30以内")
    if full_row and full_row["return_edge_vs_same_cap_cash_pp"] <= 0:
        red_reasons.append("全样本未跑赢同资金现金对照")
    if full_row and full_row["return_edge_vs_stage079_pp"] < -1500:
        yellow_reasons.append("相对Stage079正常成本现金边界的收益率下降过大")
    if not annual.empty and float(annual.iloc[0]["dd30_pass_rate"]) < 1.0:
        red_reasons.append("年度冷启动存在回撤超过30%的窗口")
    if not quarter.empty and float(quarter.iloc[0]["dd30_pass_rate"]) < 1.0:
        yellow_reasons.append("季度冷启动存在回撤超过30%的窗口")
    if not rolling252.empty and float(rolling252.iloc[0]["dd30_pass_rate"]) < 1.0:
        yellow_reasons.append("252日滚动窗口存在回撤超过30%的窗口")
    if not rolling504.empty and float(rolling504.iloc[0]["dd30_pass_rate"]) < 1.0:
        yellow_reasons.append("504日滚动窗口存在回撤超过30%的窗口")
    if not rolling252.empty and float(rolling252.iloc[0]["worst_return_edge_vs_same_cap_cash_pp"]) < 0:
        yellow_reasons.append("252日滚动窗口曾落后同资金现金对照")

    if red_reasons:
        status = "red"
    elif yellow_reasons:
        status = "yellow"
    else:
        status = "green"

    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "audit_status": status,
        "red_reasons": red_reasons,
        "yellow_reasons": yellow_reasons,
        "futures_capital": FUTURES_CAPITAL,
        "stock_capital": STOCK_CAPITAL,
        "external_cash": EXTERNAL_CASH,
        "total_capital": TOTAL_CAPITAL,
        "full_candidate_return_pct": full_row.get("candidate_return_pct"),
        "full_candidate_max_dd_pct": full_row.get("candidate_max_dd_pct"),
        "full_return_edge_vs_same_cap_cash_pp": full_row.get("return_edge_vs_same_cap_cash_pp"),
        "full_dd_edge_vs_same_cap_cash_pp": full_row.get("dd_edge_vs_same_cap_cash_pp"),
        "full_return_edge_vs_stage079_pp": full_row.get("return_edge_vs_stage079_pp"),
        "full_dd_edge_vs_stage079_pp": full_row.get("dd_edge_vs_stage079_pp"),
        "full_profit_retention_vs_c3_pct": full_row.get("profit_retention_vs_c3_pct"),
        "annual_dd30_pass_rate": None if annual.empty else float(annual.iloc[0]["dd30_pass_rate"]),
        "quarter_dd30_pass_rate": None if quarter.empty else float(quarter.iloc[0]["dd30_pass_rate"]),
        "rolling252_dd30_pass_rate": None if rolling252.empty else float(rolling252.iloc[0]["dd30_pass_rate"]),
        "rolling504_dd30_pass_rate": None if rolling504.empty else float(rolling504.iloc[0]["dd30_pass_rate"]),
        "recommended_next_step": (
            "do_not_promote_capital_heavy_stack"
            if status == "red"
            else "paper_only_if_user_accepts_lower_return_and_915k_capital"
        ),
    }


def _write_report(decision: dict[str, Any], aggregate: pd.DataFrame, paired: pd.DataFrame) -> None:
    full = paired[(paired["scope"] == "full") & (paired["window_name"] == "full_2020_2026")]
    full_row = full.iloc[0].to_dict() if not full.empty else {}
    lines = [
        "# Stage080 C3现金边界叠加30万股票账户审计",
        "",
        f"- 生成时间：`{decision['created_at']}`",
        f"- 研究线：`{LINE_ID}`",
        f"- 候选：`50万C3下单 + 30万股票账户 + 11.5万外部现金`，账户总资金 `91.5万`。",
        "- 目的：只验证固定组合层叠加是否明显改善平滑度；不修改任何策略参数、品种、AI池、止损或仓位规则。",
        "",
        "## 全样本结论",
        "",
    ]
    if full_row:
        lines.extend(
            [
                f"- 候选总收益：`{full_row['candidate_return_pct']:.4f}%`。",
                f"- 候选最大回撤：`{full_row['candidate_max_dd_pct']:.4f}%`。",
                f"- 相对同资金现金对照收益差：`{full_row['return_edge_vs_same_cap_cash_pp']:.4f}pp`。",
                f"- 相对同资金现金对照回撤差：`{full_row['dd_edge_vs_same_cap_cash_pp']:.4f}pp`。",
                f"- 相对 Stage079 现金边界收益差：`{full_row['return_edge_vs_stage079_pp']:.4f}pp`。",
                f"- 相对 Stage079 现金边界回撤差：`{full_row['dd_edge_vs_stage079_pp']:.4f}pp`。",
                f"- 绝对利润相对 C3 保留：`{full_row['profit_retention_vs_c3_pct']:.4f}%`。",
            ]
        )
    lines.extend(
        [
            "",
            "## 多起点摘要",
            "",
            aggregate.to_markdown(index=False, floatfmt=".4f"),
            "",
            "## 决策",
            "",
            f"- 状态：`{decision['audit_status']}`。",
            f"- 红灯原因：`{decision['red_reasons']}`。",
            f"- 黄灯原因：`{decision['yellow_reasons']}`。",
            f"- 推荐下一步：`{decision['recommended_next_step']}`。",
            "",
            "## 过拟合与继续价值",
            "",
            "- 过拟合反思：本阶段不是过拟合，因为只叠加两个已冻结候选和固定现金，不调权重、不调参数、不挑窗口。",
            "- 继续价值反思：若结果只来自增加资金导致的机械平滑，不能作为正式路线；只有在显著优于同资金现金对照且多窗口稳定时才值得继续。",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_html(df: pd.DataFrame) -> None:
    full = df.copy()
    fig = go.Figure()
    for variant in [
        "official78_plus_415k_cash",
        "c3_plus_415k_cash",
        "c3_plus_115k_cash",
        "c3_plus_300k_stock",
        "c3_plus_300k_stock_115k_cash",
    ]:
        label, column = CURVE_SPECS[variant]
        nav = full[column] / float(full[column].iloc[0])
        fig.add_trace(go.Scatter(x=full["date"], y=nav, mode="lines", name=label))
    fig.update_layout(
        title="Stage080 固定组合层叠加审计 - 全样本净值",
        xaxis_title="日期",
        yaxis_title="净值",
        template="plotly_white",
        height=760,
    )
    HTML_PATH.write_text(fig.to_html(include_plotlyjs="cdn", full_html=True), encoding="utf-8")


def main() -> None:
    curves = _load_curves()
    starts = [("full_2020_2026", pd.Timestamp(curves.index.min()))]
    stats_parts = [
        _build_window_stats(curves, "full", starts),
        _build_window_stats(curves, "annual_start", _annual_starts(pd.DatetimeIndex(curves.index))),
        _build_window_stats(curves, "quarter_start", _quarter_starts(pd.DatetimeIndex(curves.index))),
    ]
    for window in ROLLING_WINDOWS:
        stats_parts.append(_build_rolling_stats(curves, window))
    stats = pd.concat(stats_parts, ignore_index=True)
    paired = _build_paired(stats)
    aggregate = _aggregate(paired)
    decision = _build_decision(paired, aggregate)

    WINDOW_STATS_PATH.write_text(stats.to_csv(index=False), encoding="utf-8")
    PAIRED_PATH.write_text(paired.to_csv(index=False), encoding="utf-8")
    AGGREGATE_PATH.write_text(aggregate.to_csv(index=False), encoding="utf-8")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(decision, aggregate, paired)
    _write_html(curves)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"wrote {WINDOW_STATS_PATH}")
    print(f"wrote {PAIRED_PATH}")
    print(f"wrote {AGGREGATE_PATH}")
    print(f"wrote {DECISION_PATH}")
    print(f"wrote {REPORT_PATH}")
    print(f"wrote {HTML_PATH}")


if __name__ == "__main__":
    main()
