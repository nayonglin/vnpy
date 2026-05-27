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
MODEL_TAG = "stage378_stage075_combo_multistart_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage378_stage075_combo_multistart_audit"

STAGE377_DAILY_MONITOR_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage377_stage075_combo_forward_paper_monitor_daily_monitor_stage377_stage075_combo_forward_paper_monitor_v1.csv"
)
STAGE377_DECISION_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage377_stage075_combo_forward_paper_monitor_decision_stage377_stage075_combo_forward_paper_monitor_v1.json"
)

LINE_ID = "futures_trend_drawdown30_preserve_return"
TOTAL_CAPITAL = 800_000.0
FUTURES_CAPITAL = 500_000.0
STOCK_CAPITAL = 300_000.0

TARGET_MAX_DD_PCT = -30.0
CASH_DD_TOLERANCE_PP = -0.75
MIN_HORIZON_DAYS = 252
ROLLING_WINDOWS = (252, 504)

CURVE_SPECS = {
    "combo": ("50万C3 + 30万股票账户", "combo_equity", TOTAL_CAPITAL, "#16a34a"),
    "cash_control": ("50万C3 + 30万现金", "cash_control_equity", TOTAL_CAPITAL, "#64748b"),
    "official78_plus_cash": ("78-1 + 30万现金", "official78_plus_cash_equity", TOTAL_CAPITAL, "#ef4444"),
    "c3": ("50万C3期货账户", "c3_equity", FUTURES_CAPITAL, "#2563eb"),
    "stock": ("30万股票整手账户", "stock_equity", STOCK_CAPITAL, "#f97316"),
}


@dataclass(frozen=True)
class WindowStats:
    scope: str
    window_name: str
    start_date: pd.Timestamp
    end_date: pd.Timestamp
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


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _load_monitor() -> pd.DataFrame:
    if not STAGE377_DAILY_MONITOR_PATH.exists():
        raise FileNotFoundError(f"missing Stage377 daily monitor: {STAGE377_DAILY_MONITOR_PATH}")
    df = pd.read_csv(STAGE377_DAILY_MONITOR_PATH)
    df.columns = [str(col).lstrip("\ufeff") for col in df.columns]
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df[df["date"].notna()].copy()
    df.sort_values("date", inplace=True)
    df.set_index(pd.DatetimeIndex(df["date"]), inplace=True)
    for _, column, _, _ in CURVE_SPECS.values():
        df[column] = pd.to_numeric(df[column], errors="coerce").ffill()
    return df


def _drawdown(nav: pd.Series) -> pd.Series:
    return nav / nav.cummax() - 1.0


def _drawdown_window(nav: pd.Series) -> tuple[pd.Timestamp, pd.Timestamp, float]:
    dd = _drawdown(nav)
    if dd.empty:
        empty_date = pd.Timestamp("1900-01-01")
        return empty_date, empty_date, 0.0
    trough = dd.idxmin()
    peak = nav.loc[:trough].idxmax()
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
        start_date=pd.Timestamp(series.index.min()),
        end_date=pd.Timestamp(series.index.max()),
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


def _annual_start_dates(index: pd.DatetimeIndex) -> list[tuple[str, pd.Timestamp]]:
    result: list[tuple[str, pd.Timestamp]] = []
    first_year = int(index.min().year)
    last_year = int(index.max().year)
    for year in range(first_year, last_year + 1):
        start = _first_available_date(index, pd.Timestamp(year=year, month=1, day=1))
        if start is not None:
            result.append((f"start_{year}", start))
    return result


def _quarter_start_dates(index: pd.DatetimeIndex) -> list[tuple[str, pd.Timestamp]]:
    result: list[tuple[str, pd.Timestamp]] = []
    first = pd.Timestamp(index.min()).to_period("Q")
    last = pd.Timestamp(index.max()).to_period("Q")
    for period in pd.period_range(first, last, freq="Q"):
        start = _first_available_date(index, period.start_time)
        if start is not None:
            result.append((f"{period.year}Q{period.quarter}", start))
    return result


def _build_start_window_stats(df: pd.DataFrame, scope: str, starts: list[tuple[str, pd.Timestamp]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for window_name, start in starts:
        chunk = df[df.index >= start]
        if chunk.empty:
            continue
        for variant, (label, column, _, _) in CURVE_SPECS.items():
            stats = _stats_from_equity(chunk[column], scope, window_name, variant, label)
            rows.append(stats.__dict__)
    return pd.DataFrame(rows)


def _pivot_variant_stats(stats: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (scope, window_name), group in stats.groupby(["scope", "window_name"], sort=False):
        lookup = group.set_index("variant")
        if not {"combo", "cash_control", "official78_plus_cash", "c3"}.issubset(lookup.index):
            continue
        combo = lookup.loc["combo"]
        cash = lookup.loc["cash_control"]
        official = lookup.loc["official78_plus_cash"]
        c3 = lookup.loc["c3"]
        horizon = int(combo["horizon_days"])
        eligible = horizon >= MIN_HORIZON_DAYS
        row = {
            "scope": scope,
            "window_name": window_name,
            "start_date": combo["start_date"],
            "end_date": combo["end_date"],
            "horizon_days": horizon,
            "eligible": bool(eligible),
            "combo_total_return_pct": _safe_float(combo["total_return_pct"]),
            "combo_max_dd_percent": _safe_float(combo["max_dd_percent"]),
            "combo_ulcer": _safe_float(combo["ulcer"]),
            "combo_sharpe": _safe_float(combo["sharpe"]),
            "combo_longest_underwater_days": int(combo["longest_underwater_days"]),
            "cash_total_return_pct": _safe_float(cash["total_return_pct"]),
            "cash_max_dd_percent": _safe_float(cash["max_dd_percent"]),
            "cash_ulcer": _safe_float(cash["ulcer"]),
            "official_total_return_pct": _safe_float(official["total_return_pct"]),
            "official_max_dd_percent": _safe_float(official["max_dd_percent"]),
            "official_ulcer": _safe_float(official["ulcer"]),
            "c3_total_return_pct": _safe_float(c3["total_return_pct"]),
            "c3_max_dd_percent": _safe_float(c3["max_dd_percent"]),
        }
        row["combo_vs_cash_return_edge_pp"] = row["combo_total_return_pct"] - row["cash_total_return_pct"]
        row["combo_vs_cash_dd_gap_pp"] = row["combo_max_dd_percent"] - row["cash_max_dd_percent"]
        row["combo_vs_official_return_edge_pp"] = (
            row["combo_total_return_pct"] - row["official_total_return_pct"]
        )
        row["combo_vs_official_dd_improvement_pp"] = (
            row["combo_max_dd_percent"] - row["official_max_dd_percent"]
        )
        row["combo_vs_official_ulcer_improvement_pct"] = (
            (row["official_ulcer"] - row["combo_ulcer"]) / row["official_ulcer"] * 100.0
            if row["official_ulcer"]
            else 0.0
        )
        row["combo_vs_c3_dd_improvement_pp"] = row["combo_max_dd_percent"] - row["c3_max_dd_percent"]
        row["pass_dd30"] = bool(eligible and row["combo_max_dd_percent"] >= TARGET_MAX_DD_PCT)
        row["pass_cash_return"] = bool(eligible and row["combo_vs_cash_return_edge_pp"] > 0.0)
        row["pass_cash_dd"] = bool(eligible and row["combo_vs_cash_dd_gap_pp"] >= CASH_DD_TOLERANCE_PP)
        row["pass_smoother_than_official"] = bool(
            eligible
            and row["combo_vs_official_dd_improvement_pp"] > 0.0
            and row["combo_vs_official_ulcer_improvement_pct"] > 0.0
        )
        row["pass_all"] = bool(
            row["pass_dd30"]
            and row["pass_cash_return"]
            and row["pass_cash_dd"]
            and row["pass_smoother_than_official"]
        )
        rows.append(row)
    return pd.DataFrame(rows)


def _rolling_window_stats(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    index = df.index
    for window in ROLLING_WINDOWS:
        if len(index) < window:
            continue
        for end_idx in range(window - 1, len(index)):
            chunk = df.iloc[end_idx - window + 1 : end_idx + 1]
            window_name = f"{window}d_{chunk.index[0].date()}_{chunk.index[-1].date()}"
            for variant, (label, column, _, _) in CURVE_SPECS.items():
                stats = _stats_from_equity(chunk[column], f"rolling_{window}d", window_name, variant, label)
                rows.append(stats.__dict__)
    all_stats = pd.DataFrame(rows)
    paired = _pivot_variant_stats(all_stats) if not all_stats.empty else pd.DataFrame()
    return all_stats, paired


def _aggregate_gate_table(paired: pd.DataFrame) -> pd.DataFrame:
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
                "cash_return_pass": int(eligible["pass_cash_return"].sum()),
                "cash_dd_pass": int(eligible["pass_cash_dd"].sum()),
                "smooth_official_pass": int(eligible["pass_smoother_than_official"].sum()),
                "all_gate_pass": int(eligible["pass_all"].sum()),
                "dd30_pass_rate": float(eligible["pass_dd30"].mean()),
                "all_gate_pass_rate": float(eligible["pass_all"].mean()),
                "worst_combo_return_pct": float(eligible["combo_total_return_pct"].min()),
                "worst_combo_max_dd_percent": float(eligible["combo_max_dd_percent"].min()),
                "worst_combo_vs_cash_return_edge_pp": float(
                    eligible["combo_vs_cash_return_edge_pp"].min()
                ),
                "worst_combo_vs_cash_dd_gap_pp": float(eligible["combo_vs_cash_dd_gap_pp"].min()),
                "median_combo_vs_official_dd_improvement_pp": float(
                    eligible["combo_vs_official_dd_improvement_pp"].median()
                ),
                "median_combo_vs_official_ulcer_improvement_pct": float(
                    eligible["combo_vs_official_ulcer_improvement_pct"].median()
                ),
            }
        )
    return pd.DataFrame(rows)


def _build_decision(aggregate: pd.DataFrame, paired: pd.DataFrame) -> dict[str, Any]:
    stage377 = _load_json(STAGE377_DECISION_PATH)
    eligible = paired[paired["eligible"]].copy()
    annual = eligible[eligible["scope"].eq("annual_start")]
    quarterly = eligible[eligible["scope"].eq("quarter_start")]
    rolling_252 = eligible[eligible["scope"].eq("rolling_252d")]
    rolling_504 = eligible[eligible["scope"].eq("rolling_504d")]

    red_reasons: list[str] = []
    yellow_reasons: list[str] = []
    if not annual.empty and int(annual["pass_dd30"].sum()) < len(annual):
        red_reasons.append("年度冷启动存在组合最大回撤未进30以内")
    if not quarterly.empty and float(quarterly["pass_dd30"].mean()) < 0.90:
        red_reasons.append("季度冷启动回撤30以内通过率低于90%")
    if not rolling_504.empty and float(rolling_504["combo_total_return_pct"].min()) <= 0.0:
        red_reasons.append("504日滚动窗口存在非正收益")
    if not rolling_252.empty and float(rolling_252["combo_vs_cash_return_edge_pp"].min()) <= -10.0:
        red_reasons.append("252日滚动窗口相对现金落后超过10pp")

    if not quarterly.empty and float(quarterly["pass_all"].mean()) < 0.75:
        yellow_reasons.append("季度冷启动相对现金/78-1综合闸门通过率不足75%")
    if not rolling_252.empty and float(rolling_252["combo_vs_cash_return_edge_pp"].min()) < -5.0:
        yellow_reasons.append("252日滚动窗口相对现金曾落后超过5pp")
    if not rolling_252.empty and float(rolling_252["combo_total_return_pct"].min()) < 0.0:
        yellow_reasons.append("252日滚动窗口存在负收益，但504日窗口仍为正")
    if not annual.empty and float(annual["pass_cash_return"].mean()) < 0.80:
        yellow_reasons.append("年度冷启动相对现金收益通过率不足80%")

    status = "green"
    if red_reasons:
        status = "red"
    elif yellow_reasons:
        status = "yellow"

    def metric(scope: str, column: str, default: float = 0.0) -> float:
        rows = aggregate[aggregate["scope"].eq(scope)]
        if rows.empty or column not in rows.columns:
            return default
        return _safe_float(rows.iloc[0][column], default)

    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "audit_status": status,
        "red_reasons": red_reasons,
        "yellow_reasons": yellow_reasons,
        "stage377_status": stage377.get("monitor_status"),
        "stage377_decision": stage377,
        "annual_eligible_windows": int(metric("annual_start", "eligible_windows")),
        "annual_dd30_pass_rate": metric("annual_start", "dd30_pass_rate"),
        "annual_all_gate_pass_rate": metric("annual_start", "all_gate_pass_rate"),
        "quarter_eligible_windows": int(metric("quarter_start", "eligible_windows")),
        "quarter_dd30_pass_rate": metric("quarter_start", "dd30_pass_rate"),
        "quarter_all_gate_pass_rate": metric("quarter_start", "all_gate_pass_rate"),
        "rolling252_windows": int(metric("rolling_252d", "eligible_windows")),
        "rolling252_worst_return_pct": metric("rolling_252d", "worst_combo_return_pct"),
        "rolling252_worst_cash_edge_pp": metric("rolling_252d", "worst_combo_vs_cash_return_edge_pp"),
        "rolling504_windows": int(metric("rolling_504d", "eligible_windows")),
        "rolling504_worst_return_pct": metric("rolling_504d", "worst_combo_return_pct"),
        "rolling504_worst_cash_edge_pp": metric("rolling_504d", "worst_combo_vs_cash_return_edge_pp"),
        "strategy_change_allowed": False,
        "recommended_next_step": "keep_forward_paper_and_do_no_parameter_rescue"
        if status != "red"
        else "downgrade_combo_candidate_or_find_new_independent_return_source",
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


def _write_report(
    aggregate: pd.DataFrame,
    annual: pd.DataFrame,
    quarter: pd.DataFrame,
    rolling_paired: pd.DataFrame,
    decision: dict[str, Any],
    paths: dict[str, Path],
) -> None:
    annual_bad = annual[annual["eligible"] & (~annual["pass_all"])].sort_values(
        ["pass_dd30", "combo_vs_cash_return_edge_pp", "combo_max_dd_percent"],
        ascending=[True, True, True],
    )
    quarter_bad = quarter[quarter["eligible"] & (~quarter["pass_all"])].sort_values(
        ["pass_dd30", "combo_vs_cash_return_edge_pp", "combo_max_dd_percent"],
        ascending=[True, True, True],
    )
    rolling_worst = rolling_paired[rolling_paired["eligible"]].sort_values(
        ["combo_total_return_pct", "combo_vs_cash_return_edge_pp"], ascending=[True, True]
    )

    lines = [
        "# Stage078 Stage075组合多起点与滚动窗口审计",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：day",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 阶段性质：只读稳健性审计；不修改78-1、C3、股票账户参数或组合权重。",
        "- 是否重要突破：否。本阶段验证候选是否被单一起点美化。",
        "- 是否触发A/B：否。当前不是新策略合入，只审计既有组合候选。",
        "",
        "## 外部调研与判断",
        "",
        "- 参考资料：GitHub walk-forward-analysis 主题、QuantStats GitHub 组合分析工具、以及滚动/Walk-forward 验证资料都强调，单条全周期曲线不足以证明稳健，必须检查多起点、滚动窗口、回撤和相对基准。",
        "- 我的判断：Stage075/077 只证明全样本明显更平滑；本阶段要验证季度冷启动和滚动窗口是否也保持回撤30以内，并且是否优于现金稀释。",
        "",
        "## 运行前过拟合反思",
        "",
        "- 判断：否。",
        "- 原因：本阶段只重切已有净值曲线，不新增交易参数，不调股票权重，不筛选品种。",
        "",
        "## 运行前继续价值反思",
        "",
        "- 判断：是。",
        "- 原因：目标是回撤30以内且曲线更平滑，多起点和滚动窗口是判定是否可继续paper的必要证据。",
        "",
        "## 决策",
        "",
        f"- 审计状态：`{decision['audit_status']}`。",
        f"- 红灯原因：{decision['red_reasons'] or '无'}。",
        f"- 黄灯原因：{decision['yellow_reasons'] or '无'}。",
        f"- 年度冷启动：符合样本 `{decision['annual_eligible_windows']}` 个，回撤30以内通过率 `{decision['annual_dd30_pass_rate']:.2%}`，综合通过率 `{decision['annual_all_gate_pass_rate']:.2%}`。",
        f"- 季度冷启动：符合样本 `{decision['quarter_eligible_windows']}` 个，回撤30以内通过率 `{decision['quarter_dd30_pass_rate']:.2%}`，综合通过率 `{decision['quarter_all_gate_pass_rate']:.2%}`。",
        f"- 252日滚动最差收益 `{decision['rolling252_worst_return_pct']:.4f}%`，最差相对现金 `{decision['rolling252_worst_cash_edge_pp']:.4f}pp`。",
        f"- 504日滚动最差收益 `{decision['rolling504_worst_return_pct']:.4f}%`，最差相对现金 `{decision['rolling504_worst_cash_edge_pp']:.4f}pp`。",
        "",
        "## 闸门汇总",
        "",
        _to_markdown_table(
            aggregate,
            [
                "scope",
                "eligible_windows",
                "dd30_pass",
                "cash_return_pass",
                "cash_dd_pass",
                "smooth_official_pass",
                "all_gate_pass",
                "worst_combo_return_pct",
                "worst_combo_max_dd_percent",
                "worst_combo_vs_cash_return_edge_pp",
            ],
        ),
        "",
        "## 年度冷启动未全通过样本",
        "",
        _to_markdown_table(
            annual_bad,
            [
                "window_name",
                "horizon_days",
                "combo_total_return_pct",
                "combo_max_dd_percent",
                "combo_vs_cash_return_edge_pp",
                "combo_vs_cash_dd_gap_pp",
                "combo_vs_official_dd_improvement_pp",
                "pass_dd30",
                "pass_cash_return",
                "pass_cash_dd",
                "pass_smoother_than_official",
            ],
        ),
        "",
        "## 季度冷启动最弱样本",
        "",
        _to_markdown_table(
            quarter_bad,
            [
                "window_name",
                "horizon_days",
                "combo_total_return_pct",
                "combo_max_dd_percent",
                "combo_vs_cash_return_edge_pp",
                "combo_vs_cash_dd_gap_pp",
                "combo_vs_official_dd_improvement_pp",
                "pass_dd30",
                "pass_cash_return",
                "pass_cash_dd",
                "pass_smoother_than_official",
            ],
            max_rows=12,
        ),
        "",
        "## 滚动窗口最弱样本",
        "",
        _to_markdown_table(
            rolling_worst,
            [
                "scope",
                "window_name",
                "combo_total_return_pct",
                "combo_max_dd_percent",
                "combo_vs_cash_return_edge_pp",
                "combo_vs_cash_dd_gap_pp",
                "combo_vs_official_dd_improvement_pp",
            ],
            max_rows=12,
        ),
        "",
        "## 运行后过拟合反思",
        "",
        "- 判断：否。",
        "- 原因：审计只暴露候选在不同起点下的真实表现，没有根据失败窗口调参救援。",
        "",
        "## 运行后继续价值反思",
        "",
        "- 判断：有价值。",
        "- 原因：若多起点证明仍能大幅改善78-1平滑度，候选可继续paper；若相对现金不稳，则应限制为黄灯观察而非正式策略。",
        "",
        "## 下一步",
        "",
        "- 若为绿灯：继续forward paper并接真实双账户对账。",
        "- 若为黄灯：只做只读归因，不调股票权重或参数。",
        "- 若为红灯：降级该组合候选，转向新的独立收益源或承载工具。",
        "",
        "## 输出文件",
        "",
    ]
    for name, path in paths.items():
        lines.append(f"- `{name}`：`{path.name}`")
    paths["report"].write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_html(
    df: pd.DataFrame,
    aggregate: pd.DataFrame,
    annual: pd.DataFrame,
    quarter: pd.DataFrame,
    rolling_paired: pd.DataFrame,
    decision: dict[str, Any],
    paths: dict[str, Path],
) -> None:
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        subplot_titles=("固定候选净值", "固定候选回撤"),
    )
    for variant in ["official78_plus_cash", "cash_control", "combo", "c3", "stock"]:
        label, column, capital, color = CURVE_SPECS[variant]
        nav = pd.to_numeric(df[column], errors="coerce").ffill() / capital
        dd = _drawdown(nav) * 100.0
        fig.add_trace(
            go.Scatter(x=df.index, y=nav, mode="lines", name=label, line=dict(color=color, width=2)),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=dd,
                mode="lines",
                name=f"{label}回撤",
                showlegend=False,
                line=dict(color=color, width=1.4),
            ),
            row=2,
            col=1,
        )
    fig.update_layout(
        template="plotly_white",
        height=850,
        title="Stage078 多起点与滚动窗口审计",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(l=70, r=40, t=110, b=50),
    )
    fig.update_yaxes(title_text="净值", row=1, col=1)
    fig.update_yaxes(title_text="回撤 %", row=2, col=1)

    quarter_view = quarter[quarter["eligible"]].sort_values(
        ["pass_all", "combo_vs_cash_return_edge_pp"], ascending=[True, True]
    )
    rolling_view = rolling_paired[rolling_paired["eligible"]].sort_values(
        ["combo_total_return_pct", "combo_vs_cash_return_edge_pp"], ascending=[True, True]
    )

    def html_table(frame: pd.DataFrame, columns: list[str], rows: int | None = None) -> str:
        view = frame[columns].copy()
        if rows is not None:
            view = view.head(rows)
        return view.round(4).to_html(index=False)

    html = [
        "<!doctype html><html><head><meta charset='utf-8'>",
        "<title>多起点与滚动窗口审计</title>",
        "<style>body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;margin:24px;background:#f8fafc;color:#0f172a}.card{background:white;border:1px solid #e2e8f0;border-radius:8px;padding:16px;margin:14px 0}table{border-collapse:collapse;width:100%;font-size:13px}th,td{border:1px solid #e2e8f0;padding:7px;text-align:right}th:first-child,td:first-child{text-align:left}.status{font-size:24px;font-weight:700}</style>",
        "</head><body>",
        "<h1>多起点与滚动窗口审计</h1>",
        f"<div class='card'><div class='status'>状态：{decision['audit_status']}</div><p>只读审计，不调权重，不改策略参数。</p></div>",
        fig.to_html(full_html=False, include_plotlyjs="cdn"),
        "<div class='card'><h2>闸门汇总</h2>",
        aggregate.round(4).to_html(index=False),
        "</div>",
        "<div class='card'><h2>年度冷启动</h2>",
        html_table(
            annual,
            [
                "window_name",
                "eligible",
                "combo_total_return_pct",
                "combo_max_dd_percent",
                "combo_vs_cash_return_edge_pp",
                "combo_vs_official_dd_improvement_pp",
                "pass_all",
            ],
        ),
        "</div>",
        "<div class='card'><h2>季度冷启动最弱样本</h2>",
        html_table(
            quarter_view,
            [
                "window_name",
                "combo_total_return_pct",
                "combo_max_dd_percent",
                "combo_vs_cash_return_edge_pp",
                "combo_vs_cash_dd_gap_pp",
                "combo_vs_official_dd_improvement_pp",
                "pass_all",
            ],
            rows=16,
        ),
        "</div>",
        "<div class='card'><h2>滚动窗口最弱样本</h2>",
        html_table(
            rolling_view,
            [
                "scope",
                "window_name",
                "combo_total_return_pct",
                "combo_max_dd_percent",
                "combo_vs_cash_return_edge_pp",
                "combo_vs_official_dd_improvement_pp",
            ],
            rows=16,
        ),
        "</div>",
        "</body></html>",
    ]
    paths["html"].write_text("\n".join(html), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    monitor = _load_monitor()
    annual_stats = _build_start_window_stats(monitor, "annual_start", _annual_start_dates(monitor.index))
    quarter_stats = _build_start_window_stats(monitor, "quarter_start", _quarter_start_dates(monitor.index))
    annual = _pivot_variant_stats(annual_stats)
    quarter = _pivot_variant_stats(quarter_stats)
    rolling_stats, rolling_paired = _rolling_window_stats(monitor)
    paired = pd.concat([annual, quarter, rolling_paired], ignore_index=True)
    aggregate = _aggregate_gate_table(paired)
    decision = _build_decision(aggregate, paired)

    paths = {
        "annual_start": OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_start_{MODEL_TAG}.csv",
        "quarter_start": OUTPUT_DIR / f"{OUTPUT_PREFIX}_quarter_start_{MODEL_TAG}.csv",
        "rolling_detail": OUTPUT_DIR / f"{OUTPUT_PREFIX}_rolling_detail_{MODEL_TAG}.csv",
        "rolling_paired": OUTPUT_DIR / f"{OUTPUT_PREFIX}_rolling_paired_{MODEL_TAG}.csv",
        "aggregate": OUTPUT_DIR / f"{OUTPUT_PREFIX}_aggregate_{MODEL_TAG}.csv",
        "decision": OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json",
        "report": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md",
        "html": OUTPUT_DIR / f"{OUTPUT_PREFIX}_dashboard_{MODEL_TAG}.html",
    }
    annual.to_csv(paths["annual_start"], index=False, encoding="utf-8-sig")
    quarter.to_csv(paths["quarter_start"], index=False, encoding="utf-8-sig")
    rolling_stats.to_csv(paths["rolling_detail"], index=False, encoding="utf-8-sig")
    rolling_paired.to_csv(paths["rolling_paired"], index=False, encoding="utf-8-sig")
    aggregate.to_csv(paths["aggregate"], index=False, encoding="utf-8-sig")
    paths["decision"].write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(aggregate, annual, quarter, rolling_paired, decision, paths)
    _write_html(monitor, aggregate, annual, quarter, rolling_paired, decision, paths)
    print(json.dumps(decision, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
