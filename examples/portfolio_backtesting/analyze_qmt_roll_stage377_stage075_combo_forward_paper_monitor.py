from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
MODEL_TAG = "stage377_stage075_combo_forward_paper_monitor_v1"
OUTPUT_PREFIX = "qmt_roll_stage377_stage075_combo_forward_paper_monitor"

OFFICIAL78_DAILY_PATH = OUTPUT_DIR / "qmt_roll_official_stage78_1_daily_equity.csv"
STAGE075_DAILY_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage375_independent_300k_stock_combo_daily_stage375_independent_300k_stock_combo_v1.csv"
)
STAGE076_DECISION_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage376_stage075_smoothness_robustness_audit_decision_stage376_stage075_smoothness_robustness_audit_v1.json"
)

LINE_ID = "futures_trend_drawdown30_preserve_return"
FUTURES_CAPITAL = 500_000.0
STOCK_CAPITAL = 300_000.0
TOTAL_CAPITAL = FUTURES_CAPITAL + STOCK_CAPITAL

TARGET_MAX_DD_PCT = -30.0
CASH_DD_TOLERANCE_PP = -0.75
MIN_COMBO_EDGE_VS_CASH_PP = 20.0
MIN_504D_RETURN_PCT = 0.0
ROLLING_EXCESS_YELLOW_PP = -5.0
ROLLING_EXCESS_RED_PP = -10.0
ROLLING_WINDOWS = (63, 126, 252, 504)


@dataclass(frozen=True)
class Curve:
    variant: str
    label: str
    initial_capital: float
    equity: pd.Series


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


def _max_drawdown(nav: pd.Series) -> float:
    if nav.empty:
        return 0.0
    return float((nav / nav.cummax() - 1.0).min())


def _drawdown(nav: pd.Series) -> pd.Series:
    return nav / nav.cummax() - 1.0


def _drawdown_window(nav: pd.Series) -> tuple[pd.Timestamp, pd.Timestamp, float]:
    dd = _drawdown(nav)
    if dd.empty:
        today = pd.Timestamp("1900-01-01")
        return today, today, 0.0
    trough = dd.idxmin()
    peak = nav.loc[:trough].idxmax()
    return peak, trough, float(dd.loc[trough] * 100.0)


def _ulcer(nav: pd.Series) -> float:
    if nav.empty:
        return 0.0
    dd_pct = _drawdown(nav) * 100.0
    return float(np.sqrt(np.mean(np.square(np.minimum(dd_pct, 0.0)))))


def _rolling_ulcer(nav: pd.Series, window: int) -> pd.Series:
    dd_pct = _drawdown(nav) * 100.0

    def calc(values: np.ndarray) -> float:
        return float(np.sqrt(np.mean(np.square(np.minimum(values, 0.0)))))

    return dd_pct.rolling(window=window, min_periods=max(5, window // 4)).apply(calc, raw=True)


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


def _load_official78_ret() -> pd.Series:
    df = pd.read_csv(OFFICIAL78_DAILY_PATH)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df[df["date"].notna()].sort_values("date")
    balance = pd.to_numeric(df["balance"], errors="coerce").ffill()
    ret = balance.pct_change()
    ret.iloc[0] = balance.iloc[0] / FUTURES_CAPITAL - 1.0
    ret.index = pd.DatetimeIndex(df["date"])
    return ret.astype(float)


def _load_stage075_daily() -> pd.DataFrame:
    df = pd.read_csv(STAGE075_DAILY_PATH)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df[df["date"].notna()].copy()
    return df


def _curve_from_stage075(df: pd.DataFrame, variant: str, label: str, initial_capital: float) -> Curve:
    chunk = df[(df["window_name"] == "full_2020_common") & (df["variant"] == variant)].copy()
    if chunk.empty:
        raise ValueError(f"missing Stage075 variant={variant}")
    chunk.sort_values("date", inplace=True)
    equity = pd.to_numeric(chunk["equity"], errors="coerce").ffill()
    equity.index = pd.DatetimeIndex(chunk["date"])
    return Curve(variant, label, initial_capital, equity.astype(float))


def _build_curves() -> dict[str, Curve]:
    official_ret = _load_official78_ret()
    stage075 = _load_stage075_daily()
    start = max(pd.Timestamp("2020-01-02"), official_ret.index.min(), stage075["date"].min())
    end = min(official_ret.index.max(), stage075["date"].max())
    index = pd.date_range(start=start, end=end, freq="D")

    official_daily_ret = official_ret.groupby(level=0).sum().reindex(index).fillna(0.0)
    official_equity = FUTURES_CAPITAL * (1.0 + official_daily_ret).cumprod()

    raw = [
        Curve("official78_50w", "78-1正式基准50万", FUTURES_CAPITAL, official_equity),
        Curve(
            "official78_50w_plus_30w_cash",
            "78-1正式基准50万 + 30万现金",
            TOTAL_CAPITAL,
            official_equity + STOCK_CAPITAL,
        ),
        _curve_from_stage075(stage075, "A_c3_50w", "50万C3期货账户", FUTURES_CAPITAL),
        _curve_from_stage075(stage075, "B_stock_30w", "30万股票整手账户", STOCK_CAPITAL),
        _curve_from_stage075(
            stage075,
            "cash_50w_c3_plus_30w_cash",
            "50万C3 + 30万现金",
            TOTAL_CAPITAL,
        ),
        _curve_from_stage075(
            stage075,
            "C_50w_c3_plus_30w_stock",
            "50万C3 + 30万股票账户",
            TOTAL_CAPITAL,
        ),
    ]
    curves: dict[str, Curve] = {}
    for curve in raw:
        equity = curve.equity.reindex(index).ffill().dropna()
        curves[curve.variant] = Curve(curve.variant, curve.label, curve.initial_capital, equity)
    return curves


def _curve_stats(curve: Curve) -> dict[str, Any]:
    equity = curve.equity.dropna().astype(float)
    nav = equity / curve.initial_capital
    daily_ret = nav.pct_change().fillna(nav.iloc[0] - 1.0)
    peak, trough, dd_pct = _drawdown_window(nav)
    row: dict[str, Any] = {
        "variant": curve.variant,
        "label": curve.label,
        "start_date": str(nav.index.min().date()),
        "end_date": str(nav.index.max().date()),
        "days": int(len(nav)),
        "initial_capital": float(curve.initial_capital),
        "end_equity": float(equity.iloc[-1]),
        "total_return_pct": float((nav.iloc[-1] - 1.0) * 100.0),
        "max_dd_percent": dd_pct,
        "max_dd_peak_date": str(peak.date()),
        "max_dd_trough_date": str(trough.date()),
        "sharpe": _annualized_sharpe(daily_ret),
        "ulcer": _ulcer(nav),
        "longest_underwater_days": _longest_underwater(nav),
        "latest_drawdown_pct": float(_drawdown(nav).iloc[-1] * 100.0),
    }
    for window in ROLLING_WINDOWS:
        rr = nav / nav.shift(window) - 1.0
        row[f"latest_{window}d_return_pct"] = _safe_float(rr.iloc[-1] * 100.0, np.nan)
        row[f"worst_{window}d_return_pct"] = _safe_float(rr.min() * 100.0, np.nan)
        row[f"nonpositive_{window}d_windows"] = int((rr.dropna() <= 0.0).sum())
        row[f"latest_{window}d_ulcer"] = _safe_float(_rolling_ulcer(nav, window).iloc[-1], np.nan)
    return row


def _monitor_daily(curves: dict[str, Curve]) -> pd.DataFrame:
    combo = curves["C_50w_c3_plus_30w_stock"]
    cash = curves["cash_50w_c3_plus_30w_cash"]
    official = curves["official78_50w_plus_30w_cash"]
    c3 = curves["A_c3_50w"]
    stock = curves["B_stock_30w"]
    index = combo.equity.index

    frame = pd.DataFrame(index=index)
    frame["date"] = index
    frame["c3_equity"] = c3.equity.reindex(index).ffill().values
    frame["stock_equity"] = stock.equity.reindex(index).ffill().values
    frame["combo_equity"] = combo.equity.values
    frame["cash_control_equity"] = cash.equity.reindex(index).ffill().values
    frame["official78_plus_cash_equity"] = official.equity.reindex(index).ffill().values

    for prefix, capital in [
        ("combo", TOTAL_CAPITAL),
        ("cash_control", TOTAL_CAPITAL),
        ("official78_plus_cash", TOTAL_CAPITAL),
        ("c3", FUTURES_CAPITAL),
        ("stock", STOCK_CAPITAL),
    ]:
        equity = pd.Series(frame[f"{prefix}_equity"].values, index=index)
        nav = equity / capital
        frame[f"{prefix}_nav"] = nav.values
        frame[f"{prefix}_drawdown_pct"] = (_drawdown(nav) * 100.0).values
        frame[f"{prefix}_daily_ret"] = nav.pct_change().fillna(nav.iloc[0] - 1.0).values
        for window in ROLLING_WINDOWS:
            frame[f"{prefix}_{window}d_return_pct"] = ((nav / nav.shift(window) - 1.0) * 100.0).values
            frame[f"{prefix}_{window}d_ulcer"] = _rolling_ulcer(nav, window).values

    frame["combo_vs_cash_total_return_edge_pp"] = (frame["combo_nav"] - frame["cash_control_nav"]) * 100.0
    frame["combo_vs_official_total_return_edge_pp"] = (
        frame["combo_nav"] - frame["official78_plus_cash_nav"]
    ) * 100.0
    frame["combo_vs_cash_drawdown_gap_pp"] = (
        frame["combo_drawdown_pct"] - frame["cash_control_drawdown_pct"]
    )
    for window in ROLLING_WINDOWS:
        frame[f"combo_vs_cash_{window}d_return_edge_pp"] = (
            frame[f"combo_{window}d_return_pct"] - frame[f"cash_control_{window}d_return_pct"]
        )
        frame[f"combo_vs_official_{window}d_return_edge_pp"] = (
            frame[f"combo_{window}d_return_pct"] - frame[f"official78_plus_cash_{window}d_return_pct"]
        )

    return frame.reset_index(drop=True)


def _threshold_table() -> pd.DataFrame:
    rows = [
        {
            "gate": "最大回撤硬闸门",
            "green": "组合最大回撤 >= -30%",
            "yellow": "接近 -30% 或仍优于78-1但未充分优于现金",
            "red": "组合最大回撤 < -30%",
            "reason": "目标要求最大回撤进入30以内",
        },
        {
            "gate": "现金对照收益闸门",
            "green": "组合全周期收益比现金对照高 >= 20pp",
            "yellow": "组合收益高于现金但不足20pp",
            "red": "组合收益不高于现金",
            "reason": "验证股票账户不是只靠30万现金稀释",
        },
        {
            "gate": "现金对照回撤闸门",
            "green": "组合最大回撤不比现金对照差0.75pp以上",
            "yellow": "组合局部窗口比现金对照差0.75pp以上",
            "red": "组合全周期最大回撤比现金对照差0.75pp以上",
            "reason": "防止增加独立账户后只是增加路径压力",
        },
        {
            "gate": "两年停滞闸门",
            "green": "504日滚动收益始终为正",
            "yellow": "252日相对现金滚动收益低于 -5pp",
            "red": "504日滚动收益 <= 0 或252日相对现金低于 -10pp",
            "reason": "对应用户关心的长时间几乎不增长问题",
        },
    ]
    return pd.DataFrame(rows)


def _status(summary: pd.DataFrame, monitor: pd.DataFrame) -> dict[str, Any]:
    lookup = summary.set_index("variant")
    combo = lookup.loc["C_50w_c3_plus_30w_stock"]
    cash = lookup.loc["cash_50w_c3_plus_30w_cash"]
    official = lookup.loc["official78_50w"]
    last = monitor.iloc[-1]

    combo_return_edge_cash = _safe_float(combo["total_return_pct"]) - _safe_float(cash["total_return_pct"])
    combo_dd_gap_cash = _safe_float(combo["max_dd_percent"]) - _safe_float(cash["max_dd_percent"])
    combo_dd_improve_official = _safe_float(combo["max_dd_percent"]) - _safe_float(official["max_dd_percent"])
    combo_ulcer_improve_official = (
        (_safe_float(official["ulcer"]) - _safe_float(combo["ulcer"])) / _safe_float(official["ulcer"]) * 100.0
        if _safe_float(official["ulcer"])
        else 0.0
    )
    worst_504 = _safe_float(combo["worst_504d_return_pct"], np.nan)
    latest_252_excess_cash = _safe_float(last.get("combo_vs_cash_252d_return_edge_pp"), np.nan)
    worst_252_excess_cash = _safe_float(monitor["combo_vs_cash_252d_return_edge_pp"].min(), np.nan)
    worst_504_combo = _safe_float(monitor["combo_504d_return_pct"].min(), np.nan)

    red_reasons: list[str] = []
    yellow_reasons: list[str] = []
    if _safe_float(combo["max_dd_percent"]) < TARGET_MAX_DD_PCT:
        red_reasons.append("组合最大回撤跌破30%硬闸门")
    if combo_return_edge_cash <= 0.0:
        red_reasons.append("组合全周期收益没有超过30万现金对照")
    if combo_dd_gap_cash < CASH_DD_TOLERANCE_PP:
        red_reasons.append("组合全周期回撤显著差于现金对照")
    if not math.isnan(worst_504_combo) and worst_504_combo <= MIN_504D_RETURN_PCT:
        red_reasons.append("组合出现504日滚动收益非正窗口")
    if not math.isnan(worst_252_excess_cash) and worst_252_excess_cash < ROLLING_EXCESS_RED_PP:
        red_reasons.append("组合252日相对现金收益低于红线")

    if combo_return_edge_cash < MIN_COMBO_EDGE_VS_CASH_PP:
        yellow_reasons.append("组合相对现金收益优势不足20pp")
    if not math.isnan(latest_252_excess_cash) and latest_252_excess_cash < ROLLING_EXCESS_YELLOW_PP:
        yellow_reasons.append("最新252日相对现金收益偏弱")
    if not math.isnan(worst_252_excess_cash) and worst_252_excess_cash < ROLLING_EXCESS_YELLOW_PP:
        yellow_reasons.append("历史252日相对现金收益曾偏弱")

    if red_reasons:
        monitor_status = "red"
    elif yellow_reasons:
        monitor_status = "yellow"
    else:
        monitor_status = "green"

    next_paper_date = pd.Timestamp(last["date"]).date() + timedelta(days=1)
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "monitor_status": monitor_status,
        "red_reasons": red_reasons,
        "yellow_reasons": yellow_reasons,
        "latest_date": str(pd.Timestamp(last["date"]).date()),
        "next_paper_date": str(next_paper_date),
        "combo_total_return_pct": _safe_float(combo["total_return_pct"]),
        "combo_max_dd_percent": _safe_float(combo["max_dd_percent"]),
        "combo_ulcer": _safe_float(combo["ulcer"]),
        "combo_longest_underwater_days": int(combo["longest_underwater_days"]),
        "combo_worst_504d_return_pct": worst_504,
        "combo_latest_252d_return_pct": _safe_float(last.get("combo_252d_return_pct"), np.nan),
        "combo_latest_504d_return_pct": _safe_float(last.get("combo_504d_return_pct"), np.nan),
        "cash_total_return_pct": _safe_float(cash["total_return_pct"]),
        "cash_max_dd_percent": _safe_float(cash["max_dd_percent"]),
        "combo_return_edge_vs_cash_pp": combo_return_edge_cash,
        "combo_dd_gap_vs_cash_pp": combo_dd_gap_cash,
        "combo_latest_252d_edge_vs_cash_pp": latest_252_excess_cash,
        "combo_worst_252d_edge_vs_cash_pp": worst_252_excess_cash,
        "official78_total_return_pct": _safe_float(official["total_return_pct"]),
        "official78_max_dd_percent": _safe_float(official["max_dd_percent"]),
        "combo_dd_improvement_vs_official78_pp": combo_dd_improve_official,
        "combo_ulcer_improvement_vs_official78_pct": combo_ulcer_improve_official,
        "stage076_decision": _load_json(STAGE076_DECISION_PATH).get("decision"),
        "strategy_change_allowed": False,
        "recommended_next_step": "rerun_after_each_new_trading_day_and_compare_with_real_account_fills",
    }


def _write_report(
    summary: pd.DataFrame,
    thresholds: pd.DataFrame,
    status: dict[str, Any],
    paths: dict[str, Path],
) -> None:
    focus = summary[
        summary["variant"].isin(
            [
                "official78_50w",
                "A_c3_50w",
                "cash_50w_c3_plus_30w_cash",
                "C_50w_c3_plus_30w_stock",
                "B_stock_30w",
            ]
        )
    ].copy()
    lines = [
        "# Stage077 Stage075组合层forward paper监控入口",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：day",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 阶段性质：monitor-only；不修改78-1、C3、股票账户参数或组合权重。",
        "- 是否重要突破：否。本阶段把既有候选接入日常验证，不产生新策略版本。",
        "- 是否触发A/B：否。按A/B技能，监控、dashboard、post-mortem不运行A/B/C。",
        "",
        "## 外部调研与判断",
        "",
        "- 参考资料：QuantStats 的组合绩效报告包含回撤、滚动统计和Ulcer Index；PortfoliosLab/pfolio 对Ulcer Index的说明强调其同时衡量回撤深度和持续时间；forward testing/paper trading 的核心是实时记录信号、成交、PnL和回撤，而不是继续优化历史参数。",
        "- 我的判断：Stage075/076已经显示组合比78-1明显平滑，但不能直接晋级；应先把它作为组合层paper监控对象，固定绿/黄/红闸门，避免再用历史弱窗口调参。",
        "",
        "## 本次变更",
        "",
        "- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage377_stage075_combo_forward_paper_monitor.py`",
        "- 修改脚本：无",
        "- 删除脚本：无",
        "- 新增参数：只新增监控阈值，不新增交易参数。",
        f"  - 最大回撤硬闸门：`{TARGET_MAX_DD_PCT:.2f}%`",
        f"  - 现金对照收益优势：`{MIN_COMBO_EDGE_VS_CASH_PP:.2f}pp`",
        f"  - 现金对照回撤容忍：`{CASH_DD_TOLERANCE_PP:.2f}pp`",
        f"  - 两年停滞闸门：504日滚动收益必须 `> {MIN_504D_RETURN_PCT:.2f}%`",
        "- 修改参数：无",
        "- 删除参数：无",
        "",
        "## 运行前过拟合反思",
        "",
        "- 判断：否。",
        "- 原因：本阶段只把已有候选变成复跑监控，不调策略阈值、股票权重或品种池。",
        "",
        "## 运行前继续价值反思",
        "",
        "- 判断：有价值。",
        "- 原因：目标不是历史表格好看，而是确认组合能不能在后续paper阶段继续保持回撤30以内和更平滑路径。",
        "",
        "## 监控状态",
        "",
        f"- 当前状态：`{status['monitor_status']}`。",
        f"- 最新日期：`{status['latest_date']}`；下一次paper复跑日期：`{status['next_paper_date']}`。",
        f"- 组合收益：`{status['combo_total_return_pct']:.4f}%`；最大回撤：`{status['combo_max_dd_percent']:.4f}%`；Ulcer：`{status['combo_ulcer']:.4f}`。",
        f"- 相对78-1：回撤改善 `{status['combo_dd_improvement_vs_official78_pp']:.4f}pp`，Ulcer改善 `{status['combo_ulcer_improvement_vs_official78_pct']:.2f}%`。",
        f"- 相对现金：收益优势 `{status['combo_return_edge_vs_cash_pp']:.4f}pp`，最大回撤差 `{status['combo_dd_gap_vs_cash_pp']:.4f}pp`。",
        f"- 最新252日相对现金收益：`{status['combo_latest_252d_edge_vs_cash_pp']:.4f}pp`；历史最差252日相对现金收益：`{status['combo_worst_252d_edge_vs_cash_pp']:.4f}pp`。",
        f"- 504日最差滚动收益：`{status['combo_worst_504d_return_pct']:.4f}%`。",
        f"- 红灯原因：{'; '.join(status['red_reasons']) if status['red_reasons'] else '无'}。",
        f"- 黄灯原因：{'; '.join(status['yellow_reasons']) if status['yellow_reasons'] else '无'}。",
        "",
        "## 核心指标",
        "",
        focus[
            [
                "variant",
                "label",
                "total_return_pct",
                "max_dd_percent",
                "sharpe",
                "ulcer",
                "longest_underwater_days",
                "worst_252d_return_pct",
                "worst_504d_return_pct",
                "nonpositive_504d_windows",
            ]
        ]
        .round(4)
        .to_markdown(index=False),
        "",
        "## 闸门定义",
        "",
        thresholds.to_markdown(index=False),
        "",
        "## 运行后过拟合反思",
        "",
        "- 判断：否。",
        "- 原因：输出只是监控状态，没有因为状态去修改候选参数；若后续黄灯/红灯后调权重救结果，才会转为过拟合。",
        "",
        "## 运行后继续价值反思",
        "",
        "- 判断：有价值。",
        "- 原因：该候选已经满足历史回撤和平滑度目标的一部分，forward paper是验证能否进入真实部署评估的必要步骤。",
        "",
        "## 下一步",
        "",
        "- 每个新交易日更新期货和股票paper数据后复跑本脚本。",
        "- 若连续paper仍为绿灯，再接真实双账户持仓/成交对账。",
        "- 若黄灯，先做只读归因；不得调整股票权重或参数救窗口。",
        "- 若红灯，候选降级，继续寻找真正独立收益源或费用敏感度更低的承载工具。",
        "",
        "## 输出文件",
        "",
    ]
    for name, path in paths.items():
        lines.append(f"- `{name}`：`{path.name}`")
    paths["report"].write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_html(
    monitor: pd.DataFrame,
    summary: pd.DataFrame,
    thresholds: pd.DataFrame,
    status: dict[str, Any],
    paths: dict[str, Path],
) -> None:
    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.07,
        subplot_titles=("净值曲线", "回撤曲线", "252日相对现金收益差"),
    )
    colors = {
        "combo": "#16a34a",
        "cash_control": "#64748b",
        "official78_plus_cash": "#ef4444",
        "c3": "#2563eb",
        "stock": "#f97316",
    }
    label_map = {
        "combo": "50万C3 + 30万股票账户",
        "cash_control": "50万C3 + 30万现金",
        "official78_plus_cash": "78-1 + 30万现金",
        "c3": "50万C3期货账户",
        "stock": "30万股票整手账户",
    }
    for prefix in ["combo", "cash_control", "official78_plus_cash", "c3", "stock"]:
        fig.add_trace(
            go.Scatter(
                x=monitor["date"],
                y=monitor[f"{prefix}_nav"],
                mode="lines",
                name=label_map[prefix],
                line=dict(width=2, color=colors[prefix]),
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=monitor["date"],
                y=monitor[f"{prefix}_drawdown_pct"],
                mode="lines",
                name=f"{label_map[prefix]} 回撤",
                showlegend=False,
                line=dict(width=1.5, color=colors[prefix]),
            ),
            row=2,
            col=1,
        )
    fig.add_trace(
        go.Scatter(
            x=monitor["date"],
            y=monitor["combo_vs_cash_252d_return_edge_pp"],
            mode="lines",
            name="组合252日相对现金收益差",
            line=dict(width=2, color="#7c3aed"),
        ),
        row=3,
        col=1,
    )
    fig.add_hline(y=TARGET_MAX_DD_PCT, line_dash="dash", line_color="#ef4444", row=2, col=1)
    fig.add_hline(y=0.0, line_dash="dot", line_color="#64748b", row=3, col=1)
    fig.add_hline(y=ROLLING_EXCESS_YELLOW_PP, line_dash="dash", line_color="#f59e0b", row=3, col=1)
    fig.add_hline(y=ROLLING_EXCESS_RED_PP, line_dash="dash", line_color="#ef4444", row=3, col=1)
    fig.update_layout(
        title="Stage077 组合层Forward Paper监控",
        template="plotly_white",
        height=1050,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(l=70, r=40, t=120, b=50),
    )
    fig.update_yaxes(title_text="净值", row=1, col=1)
    fig.update_yaxes(title_text="回撤 %", row=2, col=1)
    fig.update_yaxes(title_text="pp", row=3, col=1)

    table = summary[
        [
            "label",
            "total_return_pct",
            "max_dd_percent",
            "ulcer",
            "longest_underwater_days",
            "worst_252d_return_pct",
            "worst_504d_return_pct",
        ]
    ].round(4)
    status_color = {"green": "#dcfce7", "yellow": "#fef9c3", "red": "#fee2e2"}.get(
        status["monitor_status"],
        "#f8fafc",
    )
    html = [
        "<!doctype html><html><head><meta charset='utf-8'>",
        "<title>Stage077 组合层Forward Paper监控</title>",
        "<style>body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;margin:24px;background:#f8fafc;color:#0f172a}table{border-collapse:collapse;width:100%;background:white;margin:12px 0}th,td{border:1px solid #e2e8f0;padding:8px;text-align:right}th:first-child,td:first-child{text-align:left}.card{background:white;border:1px solid #e2e8f0;border-radius:8px;padding:14px;margin:12px 0}.status{border-radius:8px;padding:14px;margin:12px 0;background:"
        + status_color
        + "}</style>",
        "</head><body>",
        "<h1>组合层Forward Paper监控</h1>",
        f"<div class='status'><b>当前状态：</b>{status['monitor_status']} &nbsp; <b>最新日期：</b>{status['latest_date']} &nbsp; <b>下一次复跑：</b>{status['next_paper_date']}</div>",
        "<div class='card'>固定既有候选：50万C3期货账户 + 30万独立股票账户。此页只监控，不调参数，不修改交易逻辑。</div>",
        fig.to_html(full_html=False, include_plotlyjs="cdn"),
        "<h2>核心指标</h2>",
        table.to_html(index=False),
        "<h2>闸门定义</h2>",
        thresholds.to_html(index=False),
        "</body></html>",
    ]
    paths["html"].write_text("\n".join(html), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curves = _build_curves()
    summary = pd.DataFrame([_curve_stats(curve) for curve in curves.values()])
    monitor = _monitor_daily(curves)
    thresholds = _threshold_table()
    status = _status(summary, monitor)

    paths = {
        "summary": OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv",
        "daily_monitor": OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_monitor_{MODEL_TAG}.csv",
        "thresholds": OUTPUT_DIR / f"{OUTPUT_PREFIX}_thresholds_{MODEL_TAG}.csv",
        "decision": OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json",
        "report": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md",
        "html": OUTPUT_DIR / f"{OUTPUT_PREFIX}_dashboard_{MODEL_TAG}.html",
    }
    summary.to_csv(paths["summary"], index=False, encoding="utf-8-sig")
    monitor.to_csv(paths["daily_monitor"], index=False, encoding="utf-8-sig")
    thresholds.to_csv(paths["thresholds"], index=False, encoding="utf-8-sig")
    paths["decision"].write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(summary, thresholds, status, paths)
    _write_html(monitor, summary, thresholds, status, paths)

    print(json.dumps(status, ensure_ascii=False, indent=2))
    print(f"report={paths['report']}")
    print(f"html={paths['html']}")


if __name__ == "__main__":
    main()
