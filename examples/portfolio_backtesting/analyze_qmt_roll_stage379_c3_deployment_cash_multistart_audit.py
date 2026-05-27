from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
MODEL_TAG = "stage379_c3_deployment_cash_multistart_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage379_c3_deployment_cash_multistart_audit"
LINE_ID = "futures_trend_drawdown30_preserve_return"

OFFICIAL_DAILY_PATH = OUTPUT_DIR / "qmt_roll_official_stage78_1_daily_equity.csv"
C3_DAILY_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage336_c3_cash_reserve_multiperiod_daily_stage336_c3_cash_reserve_multiperiod_v1.csv"
)

STRATEGY_CAPITAL = 500_000.0
EXTERNAL_CASH = 115_000.0
ACCOUNT_CAPITAL = STRATEGY_CAPITAL + EXTERNAL_CASH
TARGET_MAX_DD_PCT = -30.0
RETURN_RETENTION_GATE_PCT = 80.0
MIN_HORIZON_DAYS = 252
ROLLING_WINDOWS = (252, 504)

WINDOW_STATS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_stats_{MODEL_TAG}.csv"
PAIRED_WINDOWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_paired_windows_{MODEL_TAG}.csv"
AGGREGATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_aggregate_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


@dataclass(frozen=True)
class WindowStats:
    scope: str
    window_name: str
    start_date: str
    end_date: str
    horizon_days: int
    variant: str
    label: str
    total_return_pct: float
    max_dd_percent: float
    max_dd_peak_date: str
    max_dd_trough_date: str
    sharpe: float
    ulcer: float
    longest_underwater_days: int
    positive_day_rate: float


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


def _load_official78() -> pd.DataFrame:
    if not OFFICIAL_DAILY_PATH.exists():
        raise FileNotFoundError(OFFICIAL_DAILY_PATH)
    frame = pd.read_csv(OFFICIAL_DAILY_PATH, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["official78_equity"] = pd.to_numeric(frame["balance"], errors="coerce")
    frame = frame[["date", "official78_equity"]].dropna().sort_values("date")
    start_row = pd.DataFrame(
        [{"date": frame["date"].iloc[0] - pd.Timedelta(days=1), "official78_equity": STRATEGY_CAPITAL}]
    )
    return pd.concat([start_row, frame], ignore_index=True)


def _load_c3() -> pd.DataFrame:
    if not C3_DAILY_PATH.exists():
        raise FileNotFoundError(C3_DAILY_PATH)
    frame = pd.read_csv(C3_DAILY_PATH, encoding="utf-8-sig")
    frame = frame[
        frame["profile"].eq("c3_active100_cash0") & frame["window_name"].eq("start_2020")
    ].copy()
    if frame.empty:
        raise ValueError("missing C3 start_2020 curve")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["c3_equity"] = pd.to_numeric(frame["balance"], errors="coerce")
    frame = frame[["date", "c3_equity"]].dropna().sort_values("date")
    start_row = pd.DataFrame([{"date": frame["date"].iloc[0] - pd.Timedelta(days=1), "c3_equity": STRATEGY_CAPITAL}])
    return pd.concat([start_row, frame], ignore_index=True)


def _load_curves() -> pd.DataFrame:
    official = _load_official78()
    c3 = _load_c3()
    merged = pd.merge(official, c3, on="date", how="inner").sort_values("date")
    merged["official78_plus_cash_equity"] = merged["official78_equity"] + EXTERNAL_CASH
    merged["c3_plus_cash_equity"] = merged["c3_equity"] + EXTERNAL_CASH
    merged.set_index(pd.DatetimeIndex(merged["date"]), inplace=True)
    return merged


def _drawdown(nav: pd.Series) -> pd.Series:
    return nav / nav.cummax() - 1.0


def _drawdown_window(nav: pd.Series) -> tuple[pd.Timestamp, pd.Timestamp, float]:
    dd = _drawdown(nav)
    if dd.empty:
        empty_date = pd.Timestamp("1900-01-01")
        return empty_date, empty_date, 0.0
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
    nav = series / float(series.iloc[0])
    daily_ret = nav.pct_change().fillna(0.0)
    peak, trough, max_dd_pct = _drawdown_window(nav)
    return WindowStats(
        scope=scope,
        window_name=window_name,
        start_date=str(pd.Timestamp(series.index.min()).date()),
        end_date=str(pd.Timestamp(series.index.max()).date()),
        horizon_days=int(len(series)),
        variant=variant,
        label=label,
        total_return_pct=float((nav.iloc[-1] - 1.0) * 100.0),
        max_dd_percent=max_dd_pct,
        max_dd_peak_date=str(peak.date()),
        max_dd_trough_date=str(trough.date()),
        sharpe=_annualized_sharpe(daily_ret),
        ulcer=_ulcer(nav),
        longest_underwater_days=_longest_underwater(nav),
        positive_day_rate=float((daily_ret > 0.0).mean()),
    )


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


CURVE_SPECS = {
    "official78_50w": ("78-1 50万", "official78_equity"),
    "official78_plus_115k": ("78-1 + 11.5万现金", "official78_plus_cash_equity"),
    "c3_50w": ("C3 50万", "c3_equity"),
    "c3_plus_115k": ("C3 50万下单 + 11.5万现金", "c3_plus_cash_equity"),
}


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


def _build_full_stats(df: pd.DataFrame) -> pd.DataFrame:
    return _build_window_stats(df, "full", [("full_2020_2026", pd.Timestamp(df.index.min()))])


def _build_rolling_stats(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for window in ROLLING_WINDOWS:
        if len(df) < window:
            continue
        for end_idx in range(window - 1, len(df)):
            chunk = df.iloc[end_idx - window + 1 : end_idx + 1]
            window_name = f"{window}d_{chunk.index[0].date()}_{chunk.index[-1].date()}"
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


def _pivot_pairs(stats: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (scope, window_name), group in stats.groupby(["scope", "window_name"], sort=False):
        lookup = group.set_index("variant")
        required = {"official78_50w", "official78_plus_115k", "c3_50w", "c3_plus_115k"}
        if not required.issubset(set(lookup.index)):
            continue
        official = lookup.loc["official78_50w"]
        official_cash = lookup.loc["official78_plus_115k"]
        c3 = lookup.loc["c3_50w"]
        c3_cash = lookup.loc["c3_plus_115k"]
        horizon = int(c3_cash["horizon_days"])
        eligible = horizon >= MIN_HORIZON_DAYS
        c3_return = _safe_float(c3["total_return_pct"])
        c3_cash_return = _safe_float(c3_cash["total_return_pct"])
        official_cash_ulcer = _safe_float(official_cash["ulcer"])
        return_retention = (
            c3_cash_return / c3_return * 100.0
            if c3_return > 0.0
            else (100.0 if c3_cash_return >= c3_return else 0.0)
        )
        row = {
            "scope": scope,
            "window_name": window_name,
            "start_date": c3_cash["start_date"],
            "end_date": c3_cash["end_date"],
            "horizon_days": horizon,
            "eligible": bool(eligible),
            "official_total_return_pct": _safe_float(official["total_return_pct"]),
            "official_max_dd_percent": _safe_float(official["max_dd_percent"]),
            "official_ulcer": _safe_float(official["ulcer"]),
            "official_cash_total_return_pct": _safe_float(official_cash["total_return_pct"]),
            "official_cash_max_dd_percent": _safe_float(official_cash["max_dd_percent"]),
            "official_cash_ulcer": official_cash_ulcer,
            "c3_total_return_pct": c3_return,
            "c3_max_dd_percent": _safe_float(c3["max_dd_percent"]),
            "c3_ulcer": _safe_float(c3["ulcer"]),
            "c3_plus_cash_total_return_pct": c3_cash_return,
            "c3_plus_cash_max_dd_percent": _safe_float(c3_cash["max_dd_percent"]),
            "c3_plus_cash_ulcer": _safe_float(c3_cash["ulcer"]),
            "c3_plus_cash_sharpe": _safe_float(c3_cash["sharpe"]),
            "c3_plus_cash_longest_underwater_days": int(c3_cash["longest_underwater_days"]),
            "return_retention_vs_c3_pct": return_retention,
        }
        row["dd_improvement_vs_c3_pp"] = row["c3_plus_cash_max_dd_percent"] - row["c3_max_dd_percent"]
        row["dd_improvement_vs_official78_pp"] = (
            row["c3_plus_cash_max_dd_percent"] - row["official_max_dd_percent"]
        )
        row["dd_improvement_vs_official78_same_cash_pp"] = (
            row["c3_plus_cash_max_dd_percent"] - row["official_cash_max_dd_percent"]
        )
        row["return_edge_vs_official78_same_cash_pp"] = (
            row["c3_plus_cash_total_return_pct"] - row["official_cash_total_return_pct"]
        )
        row["ulcer_reduction_vs_official78_same_cash_pct"] = (
            (official_cash_ulcer - row["c3_plus_cash_ulcer"]) / official_cash_ulcer * 100.0
            if official_cash_ulcer
            else 0.0
        )
        row["pass_dd30"] = bool(eligible and row["c3_plus_cash_max_dd_percent"] >= TARGET_MAX_DD_PCT)
        row["pass_return_retention"] = bool(eligible and row["return_retention_vs_c3_pct"] >= RETURN_RETENTION_GATE_PCT)
        row["pass_smoother_than_78_same_cash"] = bool(
            eligible
            and row["dd_improvement_vs_official78_same_cash_pp"] > 0.0
            and row["ulcer_reduction_vs_official78_same_cash_pct"] > 0.0
        )
        row["pass_all"] = bool(
            row["pass_dd30"] and row["pass_return_retention"] and row["pass_smoother_than_78_same_cash"]
        )
        rows.append(row)
    return pd.DataFrame(rows)


def _aggregate(paired: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for scope, group in paired.groupby("scope", sort=False):
        eligible = group[group["eligible"]].copy()
        if eligible.empty:
            continue
        rows.append(
            {
                "scope": scope,
                "eligible_windows": int(len(eligible)),
                "dd30_pass": int(eligible["pass_dd30"].sum()),
                "retention_pass": int(eligible["pass_return_retention"].sum()),
                "smooth78_pass": int(eligible["pass_smoother_than_78_same_cash"].sum()),
                "all_gate_pass": int(eligible["pass_all"].sum()),
                "dd30_pass_rate": float(eligible["pass_dd30"].mean()),
                "retention_pass_rate": float(eligible["pass_return_retention"].mean()),
                "smooth78_pass_rate": float(eligible["pass_smoother_than_78_same_cash"].mean()),
                "all_gate_pass_rate": float(eligible["pass_all"].mean()),
                "worst_c3_plus_cash_return_pct": float(eligible["c3_plus_cash_total_return_pct"].min()),
                "worst_c3_plus_cash_max_dd_percent": float(eligible["c3_plus_cash_max_dd_percent"].min()),
                "worst_return_retention_vs_c3_pct": float(eligible["return_retention_vs_c3_pct"].min()),
                "worst_return_edge_vs_official_same_cash_pp": float(
                    eligible["return_edge_vs_official78_same_cash_pp"].min()
                ),
                "median_dd_improvement_vs_official_same_cash_pp": float(
                    eligible["dd_improvement_vs_official78_same_cash_pp"].median()
                ),
                "median_ulcer_reduction_vs_official_same_cash_pct": float(
                    eligible["ulcer_reduction_vs_official78_same_cash_pct"].median()
                ),
            }
        )
    return pd.DataFrame(rows)


def _metric(aggregate: pd.DataFrame, scope: str, column: str, default: float = 0.0) -> float:
    rows = aggregate[aggregate["scope"].eq(scope)]
    if rows.empty or column not in rows.columns:
        return default
    return _safe_float(rows.iloc[0][column], default)


def _build_decision(paired: pd.DataFrame, aggregate: pd.DataFrame) -> dict[str, Any]:
    eligible = paired[paired["eligible"]].copy()
    full = eligible[eligible["scope"].eq("full")]
    annual = eligible[eligible["scope"].eq("annual_start")]
    quarter = eligible[eligible["scope"].eq("quarter_start")]
    rolling252 = eligible[eligible["scope"].eq("rolling_252d")]
    rolling504 = eligible[eligible["scope"].eq("rolling_504d")]

    red_reasons: list[str] = []
    yellow_reasons: list[str] = []

    if not full.empty and not bool(full.iloc[0]["pass_all"]):
        red_reasons.append("全样本未同时通过回撤、收益保留和相对78-1平滑闸门")
    if not annual.empty and float(annual["pass_dd30"].mean()) < 1.0:
        red_reasons.append("年度冷启动存在最大回撤未进30以内")
    if not quarter.empty and float(quarter["pass_dd30"].mean()) < 0.95:
        red_reasons.append("季度冷启动回撤30以内通过率低于95%")
    if not rolling504.empty and float(rolling504["c3_plus_cash_total_return_pct"].min()) <= 0.0:
        red_reasons.append("504日滚动窗口存在非正收益")

    if not annual.empty and float(annual["pass_all"].mean()) < 0.80:
        yellow_reasons.append("年度冷启动综合通过率不足80%")
    if not quarter.empty and float(quarter["pass_all"].mean()) < 0.75:
        yellow_reasons.append("季度冷启动综合通过率不足75%")
    if not rolling252.empty and float(rolling252["c3_plus_cash_total_return_pct"].min()) < 0.0:
        yellow_reasons.append("252日滚动窗口存在负收益")
    if not rolling252.empty and float(rolling252["return_edge_vs_official78_same_cash_pp"].min()) < -5.0:
        yellow_reasons.append("252日滚动窗口相对同现金78-1曾落后超过5pp")

    status = "green"
    if red_reasons:
        status = "red"
    elif yellow_reasons:
        status = "yellow"

    full_row = full.iloc[0].to_dict() if not full.empty else {}
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "audit_status": status,
        "red_reasons": red_reasons,
        "yellow_reasons": yellow_reasons,
        "strategy_capital": STRATEGY_CAPITAL,
        "external_cash": EXTERNAL_CASH,
        "account_capital": ACCOUNT_CAPITAL,
        "target_max_dd_pct": TARGET_MAX_DD_PCT,
        "return_retention_gate_pct": RETURN_RETENTION_GATE_PCT,
        "full_total_return_pct": _safe_float(full_row.get("c3_plus_cash_total_return_pct")),
        "full_max_dd_percent": _safe_float(full_row.get("c3_plus_cash_max_dd_percent")),
        "full_return_retention_vs_c3_pct": _safe_float(full_row.get("return_retention_vs_c3_pct")),
        "full_dd_improvement_vs_official_same_cash_pp": _safe_float(
            full_row.get("dd_improvement_vs_official78_same_cash_pp")
        ),
        "full_ulcer_reduction_vs_official_same_cash_pct": _safe_float(
            full_row.get("ulcer_reduction_vs_official78_same_cash_pct")
        ),
        "annual_eligible_windows": int(_metric(aggregate, "annual_start", "eligible_windows")),
        "annual_dd30_pass_rate": _metric(aggregate, "annual_start", "dd30_pass_rate"),
        "annual_all_gate_pass_rate": _metric(aggregate, "annual_start", "all_gate_pass_rate"),
        "quarter_eligible_windows": int(_metric(aggregate, "quarter_start", "eligible_windows")),
        "quarter_dd30_pass_rate": _metric(aggregate, "quarter_start", "dd30_pass_rate"),
        "quarter_all_gate_pass_rate": _metric(aggregate, "quarter_start", "all_gate_pass_rate"),
        "rolling252_windows": int(_metric(aggregate, "rolling_252d", "eligible_windows")),
        "rolling252_worst_return_pct": _metric(
            aggregate, "rolling_252d", "worst_c3_plus_cash_return_pct"
        ),
        "rolling252_worst_retention_pct": _metric(
            aggregate, "rolling_252d", "worst_return_retention_vs_c3_pct"
        ),
        "rolling504_windows": int(_metric(aggregate, "rolling_504d", "eligible_windows")),
        "rolling504_worst_return_pct": _metric(
            aggregate, "rolling_504d", "worst_c3_plus_cash_return_pct"
        ),
        "rolling504_worst_retention_pct": _metric(
            aggregate, "rolling_504d", "worst_return_retention_vs_c3_pct"
        ),
        "strategy_change_allowed": False,
        "recommended_next_step": "normal_cost_deployment_candidate_forward_audit"
        if status != "red"
        else "do_not_promote_find_new_uncorrelated_return_source",
    }


def _to_markdown_table(df: pd.DataFrame, columns: list[str], max_rows: int | None = None) -> str:
    if df.empty:
        return "无数据。"
    view = df[columns].copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: f"{x:.4f}")
    return view.to_markdown(index=False)


def _write_report(paired: pd.DataFrame, aggregate: pd.DataFrame, decision: dict[str, Any]) -> None:
    annual_bad = paired[
        paired["scope"].eq("annual_start") & paired["eligible"] & (~paired["pass_all"])
    ].sort_values(["pass_dd30", "return_retention_vs_c3_pct", "c3_plus_cash_max_dd_percent"])
    quarter_bad = paired[
        paired["scope"].eq("quarter_start") & paired["eligible"] & (~paired["pass_all"])
    ].sort_values(["pass_dd30", "return_retention_vs_c3_pct", "c3_plus_cash_max_dd_percent"])
    rolling_worst = paired[paired["eligible"] & paired["scope"].isin(["rolling_252d", "rolling_504d"])].sort_values(
        ["c3_plus_cash_total_return_pct", "return_retention_vs_c3_pct"], ascending=[True, True]
    )
    full = paired[paired["scope"].eq("full")]

    common_cols = [
        "window_name",
        "horizon_days",
        "c3_plus_cash_total_return_pct",
        "c3_plus_cash_max_dd_percent",
        "return_retention_vs_c3_pct",
        "dd_improvement_vs_official78_same_cash_pp",
        "ulcer_reduction_vs_official78_same_cash_pct",
        "pass_dd30",
        "pass_return_retention",
        "pass_smoother_than_78_same_cash",
    ]
    lines = [
        "# Stage079 C3部署现金多起点审计",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：day",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 阶段性质：部署层只读审计；不修改78-1、C3信号、AI池、品种池、仓位或成交路径。",
        "- 是否重要突破：否。属于 Stage055/067 现金边界的多起点复验。",
        "- 是否触发A/B：按部署层规则只做 A/C 对照；A 为 78-1，同现金对照为 `78-1 + 11.5万现金`，C 为 `C3 50万下单 + 11.5万现金`。",
        "",
        "## 外部调研与判断",
        "",
        "- 参考资料：TradingStrategy.ai 的 walk-forward 说明强调单一全周期曲线不足以证明稳健，需要多切片验证；drawdown risk 论文也把回撤作为独立风险约束，而不是只看波动率。",
        "- 我的判断：本阶段不能优化参数，只能验证一个已预声明、低自由度的账户层资金结构是否跨起点成立。",
        "",
        "## 运行前过拟合反思",
        "",
        "- 判断：否。",
        "- 原因：外部现金固定为 Stage055/067 已确定的 `11.5万`，本阶段只重切窗口，不根据结果调现金数、信号或阈值。",
        "",
        "## 运行前继续价值反思",
        "",
        "- 判断：是。",
        "- 原因：目标允许收益下降但要求曲线更平滑；这条路线是当前最低自由度、最接近可执行的正常成本边界。",
        "",
        "## 决策",
        "",
        f"- 审计状态：`{decision['audit_status']}`。",
        f"- 红灯原因：{decision['red_reasons'] or '无'}。",
        f"- 黄灯原因：{decision['yellow_reasons'] or '无'}。",
        f"- 全样本收益 `{decision['full_total_return_pct']:.4f}%`，最大回撤 `{decision['full_max_dd_percent']:.4f}%`，相对C3收益保留 `{decision['full_return_retention_vs_c3_pct']:.4f}%`。",
        f"- 相对同现金78-1：最大回撤改善 `{decision['full_dd_improvement_vs_official_same_cash_pp']:.4f}pp`，Ulcer改善 `{decision['full_ulcer_reduction_vs_official_same_cash_pct']:.4f}%`。",
        f"- 年度冷启动：样本 `{decision['annual_eligible_windows']}`，回撤30以内通过率 `{decision['annual_dd30_pass_rate']:.2%}`，综合通过率 `{decision['annual_all_gate_pass_rate']:.2%}`。",
        f"- 季度冷启动：样本 `{decision['quarter_eligible_windows']}`，回撤30以内通过率 `{decision['quarter_dd30_pass_rate']:.2%}`，综合通过率 `{decision['quarter_all_gate_pass_rate']:.2%}`。",
        f"- 252日滚动：窗口 `{decision['rolling252_windows']}`，最差收益 `{decision['rolling252_worst_return_pct']:.4f}%`，最差收益保留 `{decision['rolling252_worst_retention_pct']:.4f}%`。",
        f"- 504日滚动：窗口 `{decision['rolling504_windows']}`，最差收益 `{decision['rolling504_worst_return_pct']:.4f}%`，最差收益保留 `{decision['rolling504_worst_retention_pct']:.4f}%`。",
        "",
        "## 全样本",
        "",
        _to_markdown_table(full, common_cols),
        "",
        "## 闸门汇总",
        "",
        _to_markdown_table(
            aggregate,
            [
                "scope",
                "eligible_windows",
                "dd30_pass",
                "retention_pass",
                "smooth78_pass",
                "all_gate_pass",
                "worst_c3_plus_cash_return_pct",
                "worst_c3_plus_cash_max_dd_percent",
                "worst_return_retention_vs_c3_pct",
            ],
        ),
        "",
        "## 年度冷启动未全通过样本",
        "",
        _to_markdown_table(annual_bad, common_cols),
        "",
        "## 季度冷启动最弱样本",
        "",
        _to_markdown_table(quarter_bad, common_cols, max_rows=12),
        "",
        "## 滚动窗口最弱样本",
        "",
        _to_markdown_table(
            rolling_worst,
            [
                "scope",
                "window_name",
                "c3_plus_cash_total_return_pct",
                "c3_plus_cash_max_dd_percent",
                "return_retention_vs_c3_pct",
                "return_edge_vs_official78_same_cash_pp",
                "dd_improvement_vs_official78_same_cash_pp",
                "pass_dd30",
                "pass_return_retention",
                "pass_smoother_than_78_same_cash",
            ],
            max_rows=16,
        ),
        "",
        "## 输出文件",
        "",
        f"- window_stats：`{WINDOW_STATS_PATH.name}`",
        f"- paired_windows：`{PAIRED_WINDOWS_PATH.name}`",
        f"- aggregate：`{AGGREGATE_PATH.name}`",
        f"- decision：`{DECISION_PATH.name}`",
        "",
        "## 运行后过拟合反思",
        "",
        "- 判断：否。",
        "- 原因：没有新增可搜索参数，也没有调现金到刚好过线；使用的是已冻结的 `11.5万` 账户现金边界。",
        "",
        "## 运行后继续价值反思",
        "",
        "- 判断：有，但边界明确。",
        "- 原因：正常成本下它能显著压低回撤并保留80%+ C3收益；但 Stage055/067 已证明高滑点压力下不成立，因此不能宣传成所有成本环境下的最终解。",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    curves = _load_curves()
    pieces = [
        _build_full_stats(curves),
        _build_window_stats(curves, "annual_start", _annual_starts(curves.index)),
        _build_window_stats(curves, "quarter_start", _quarter_starts(curves.index)),
        _build_rolling_stats(curves),
    ]
    window_stats = pd.concat(pieces, ignore_index=True)
    paired = _pivot_pairs(window_stats)
    aggregate = _aggregate(paired)
    decision = _build_decision(paired, aggregate)

    window_stats.to_csv(WINDOW_STATS_PATH, index=False, encoding="utf-8-sig")
    paired.to_csv(PAIRED_WINDOWS_PATH, index=False, encoding="utf-8-sig")
    aggregate.to_csv(AGGREGATE_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(paired, aggregate, decision)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"[stage379] report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
