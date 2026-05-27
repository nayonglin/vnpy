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
MODEL_TAG = "stage376_stage075_smoothness_robustness_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage376_stage075_smoothness_robustness_audit"

OFFICIAL78_DAILY_PATH = OUTPUT_DIR / "qmt_roll_official_stage78_1_daily_equity.csv"
STAGE075_DAILY_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage375_independent_300k_stock_combo_daily_stage375_independent_300k_stock_combo_v1.csv"
)
STAGE075_DECISION_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage375_independent_300k_stock_combo_decision_stage375_independent_300k_stock_combo_v1.json"
)

FUTURES_CAPITAL = 500_000.0
STOCK_CAPITAL = 300_000.0
TOTAL_CAPITAL = FUTURES_CAPITAL + STOCK_CAPITAL
TARGET_MAX_DD = -30.0
ROLLING_WINDOWS = (252, 504)


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


def _ulcer(nav: pd.Series) -> float:
    if nav.empty:
        return 0.0
    dd_pct = (nav / nav.cummax() - 1.0) * 100.0
    return float(np.sqrt(np.mean(np.square(np.minimum(dd_pct, 0.0)))))


def _underwater_series(nav: pd.Series) -> pd.Series:
    return nav / nav.cummax() - 1.0


def _longest_underwater(nav: pd.Series) -> int:
    longest = 0
    current = 0
    for value in _underwater_series(nav):
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
    if std <= 0:
        return 0.0
    return float(daily_ret.mean() / std * math.sqrt(252.0))


def _drawdown_window(nav: pd.Series) -> tuple[pd.Timestamp, pd.Timestamp, float]:
    dd = _underwater_series(nav)
    if dd.empty:
        today = pd.Timestamp("1900-01-01")
        return today, today, 0.0
    trough = dd.idxmin()
    peak = nav.loc[:trough].idxmax()
    return peak, trough, float(dd.loc[trough] * 100.0)


def _rolling_return(nav: pd.Series, window: int) -> pd.Series:
    return nav / nav.shift(window) - 1.0


def _stats(curve: Curve, window_name: str = "full_common") -> dict[str, Any]:
    equity = curve.equity.dropna().astype(float)
    nav = equity / curve.initial_capital
    daily_ret = nav.pct_change().fillna(nav.iloc[0] - 1.0)
    peak, trough, dd_pct = _drawdown_window(nav)
    result = {
        "variant": curve.variant,
        "label": curve.label,
        "window_name": window_name,
        "days": int(len(nav)),
        "start_date": str(nav.index.min().date()),
        "end_date": str(nav.index.max().date()),
        "initial_capital": float(curve.initial_capital),
        "end_equity": float(equity.iloc[-1]),
        "end_nav": float(nav.iloc[-1]),
        "total_return_pct": float((nav.iloc[-1] - 1.0) * 100.0),
        "max_dd_percent": dd_pct,
        "max_dd_peak_date": str(peak.date()),
        "max_dd_trough_date": str(trough.date()),
        "sharpe": _annualized_sharpe(daily_ret),
        "ulcer": _ulcer(nav),
        "longest_underwater_days": _longest_underwater(nav),
        "underwater_day_ratio": float((_underwater_series(nav) < -1e-12).mean()),
        "positive_day_rate": float((daily_ret > 0.0).mean()),
        "return_to_ulcer": float(((nav.iloc[-1] - 1.0) * 100.0) / _ulcer(nav)) if _ulcer(nav) else 0.0,
        "return_to_max_dd": float(((nav.iloc[-1] - 1.0) * 100.0) / abs(dd_pct)) if dd_pct else 0.0,
    }
    for window in ROLLING_WINDOWS:
        rr = _rolling_return(nav, window).dropna()
        result[f"worst_{window}d_return_pct"] = float(rr.min() * 100.0) if not rr.empty else np.nan
        result[f"nonpositive_{window}d_windows"] = int((rr <= 0.0).sum()) if not rr.empty else 0
        result[f"nonpositive_{window}d_window_ratio"] = float((rr <= 0.0).mean()) if not rr.empty else 0.0
    return result


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
    chunk = chunk.sort_values("date")
    equity = pd.to_numeric(chunk["equity"], errors="coerce").ffill()
    equity.index = pd.DatetimeIndex(chunk["date"])
    return Curve(variant, label, initial_capital, equity)


def _build_curves() -> list[Curve]:
    official_ret = _load_official78_ret()
    stage075 = _load_stage075_daily()
    start = max(pd.Timestamp("2020-01-02"), official_ret.index.min(), stage075["date"].min())
    end = min(official_ret.index.max(), stage075["date"].max())
    index = pd.date_range(start=start, end=end, freq="D")
    official_daily_ret = official_ret.groupby(level=0).sum().reindex(index).fillna(0.0)
    official_equity = FUTURES_CAPITAL * (1.0 + official_daily_ret).cumprod()

    c3 = _curve_from_stage075(stage075, "A_c3_50w", "50万C3期货账户", FUTURES_CAPITAL)
    stock = _curve_from_stage075(stage075, "B_stock_30w", "30万股票整手账户", STOCK_CAPITAL)
    cash_combo = _curve_from_stage075(
        stage075,
        "cash_50w_c3_plus_30w_cash",
        "50万C3 + 30万现金",
        TOTAL_CAPITAL,
    )
    stock_combo = _curve_from_stage075(
        stage075,
        "C_50w_c3_plus_30w_stock",
        "50万C3 + 30万股票账户",
        TOTAL_CAPITAL,
    )
    aligned_curves = [
        Curve("official78_50w", "78-1正式基准50万", FUTURES_CAPITAL, official_equity),
        Curve(
            "official78_50w_plus_30w_cash",
            "78-1正式基准50万 + 30万现金",
            TOTAL_CAPITAL,
            official_equity + STOCK_CAPITAL,
        ),
        c3,
        cash_combo,
        stock_combo,
        stock,
    ]
    result: list[Curve] = []
    for curve in aligned_curves:
        equity = curve.equity.reindex(index).ffill().dropna()
        result.append(Curve(curve.variant, curve.label, curve.initial_capital, equity))
    return result


def _annual_table(curves: list[Curve]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for curve in curves:
        nav = curve.equity / curve.initial_capital
        by_year = nav.groupby(nav.index.year)
        for year, group in by_year:
            if group.empty:
                continue
            start_value = float(group.iloc[0])
            end_value = float(group.iloc[-1])
            year_nav = group / start_value
            rows.append(
                {
                    "variant": curve.variant,
                    "label": curve.label,
                    "year": int(year),
                    "annual_return_pct": (end_value / start_value - 1.0) * 100.0,
                    "annual_max_dd_percent": _max_drawdown(year_nav) * 100.0,
                    "annual_ulcer": _ulcer(year_nav),
                    "annual_new_high_days": int((_underwater_series(year_nav).abs() < 1e-12).sum()),
                }
            )
    return pd.DataFrame(rows)


def _relative_table(summary: pd.DataFrame) -> pd.DataFrame:
    lookup = summary.set_index("variant")
    official = lookup.loc["official78_50w"]
    c3 = lookup.loc["A_c3_50w"]
    cash = lookup.loc["cash_50w_c3_plus_30w_cash"]
    combo = lookup.loc["C_50w_c3_plus_30w_stock"]
    rows = []
    for base_name, base in [("official78_50w", official), ("A_c3_50w", c3), ("cash_50w_c3_plus_30w_cash", cash)]:
        rows.append(
            {
                "candidate": "C_50w_c3_plus_30w_stock",
                "baseline": base_name,
                "return_delta_pp": combo["total_return_pct"] - base["total_return_pct"],
                "max_dd_improvement_pp": combo["max_dd_percent"] - base["max_dd_percent"],
                "ulcer_improvement_pct": (base["ulcer"] - combo["ulcer"]) / base["ulcer"] * 100.0
                if base["ulcer"]
                else 0.0,
                "longest_underwater_improvement_days": int(base["longest_underwater_days"])
                - int(combo["longest_underwater_days"]),
                "worst_252d_improvement_pp": combo["worst_252d_return_pct"]
                - base["worst_252d_return_pct"],
                "worst_504d_improvement_pp": combo["worst_504d_return_pct"]
                - base["worst_504d_return_pct"],
            }
        )
    return pd.DataFrame(rows)


def _correlation_and_tail(curves: list[Curve]) -> dict[str, Any]:
    lookup = {curve.variant: curve for curve in curves}
    c3_nav = lookup["A_c3_50w"].equity / lookup["A_c3_50w"].initial_capital
    stock_nav = lookup["B_stock_30w"].equity / lookup["B_stock_30w"].initial_capital
    frame = pd.DataFrame(
        {
            "c3_ret": c3_nav.pct_change().fillna(c3_nav.iloc[0] - 1.0),
            "stock_ret": stock_nav.pct_change().fillna(stock_nav.iloc[0] - 1.0),
        }
    ).dropna()
    tail_threshold = frame["c3_ret"].quantile(0.05)
    tail = frame[frame["c3_ret"] <= tail_threshold]
    return {
        "daily_return_corr_c3_stock": float(frame["c3_ret"].corr(frame["stock_ret"])),
        "c3_left_tail_5pct_threshold": float(tail_threshold),
        "stock_avg_ret_on_c3_left_tail_5pct": float(tail["stock_ret"].mean()) if not tail.empty else 0.0,
        "stock_positive_rate_on_c3_left_tail_5pct": float((tail["stock_ret"] > 0).mean()) if not tail.empty else 0.0,
        "tail_days": int(len(tail)),
    }


def _start_2024_attribution() -> tuple[pd.DataFrame, dict[str, Any]]:
    df = pd.read_csv(STAGE075_DAILY_PATH)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df[df["date"].notna()].copy()
    piv = (
        df[df["window_name"] == "start_2024"]
        .pivot_table(index="date", columns="variant", values="equity", aggfunc="last")
        .sort_index()
    )
    required = [
        "A_c3_50w",
        "B_stock_30w",
        "cash_50w_c3_plus_30w_cash",
        "C_50w_c3_plus_30w_stock",
    ]
    missing = [col for col in required if col not in piv.columns]
    if missing:
        raise ValueError(f"missing start_2024 variants: {missing}")
    combo_nav = piv["C_50w_c3_plus_30w_stock"] / TOTAL_CAPITAL
    combo_peak, combo_trough, combo_dd_pct = _drawdown_window(combo_nav)
    cash_nav = piv["cash_50w_c3_plus_30w_cash"] / TOTAL_CAPITAL
    cash_peak, cash_trough, cash_dd_pct = _drawdown_window(cash_nav)

    rows = []
    for name, label in [
        ("A_c3_50w", "C3期货腿"),
        ("B_stock_30w", "股票腿"),
        ("cash_50w_c3_plus_30w_cash", "C3+现金对照"),
        ("C_50w_c3_plus_30w_stock", "C3+股票组合"),
    ]:
        peak_value = _safe_float(piv.loc[combo_peak, name])
        trough_value = _safe_float(piv.loc[combo_trough, name])
        rows.append(
            {
                "component": name,
                "label": label,
                "combo_peak_date": str(combo_peak.date()),
                "combo_trough_date": str(combo_trough.date()),
                "equity_at_combo_peak": peak_value,
                "equity_at_combo_trough": trough_value,
                "delta_cny": trough_value - peak_value,
                "delta_pct_of_total_capital": (trough_value - peak_value) / TOTAL_CAPITAL * 100.0,
            }
        )
    detail = {
        "combo_peak_date": str(combo_peak.date()),
        "combo_trough_date": str(combo_trough.date()),
        "combo_max_dd_percent": combo_dd_pct,
        "cash_peak_date": str(cash_peak.date()),
        "cash_trough_date": str(cash_trough.date()),
        "cash_max_dd_percent": cash_dd_pct,
        "combo_vs_cash_dd_gap_pp": combo_dd_pct - cash_dd_pct,
    }
    return pd.DataFrame(rows), detail


def _build_decision(summary: pd.DataFrame, relative: pd.DataFrame, tail: dict[str, Any], weak: dict[str, Any]) -> dict[str, Any]:
    lookup = summary.set_index("variant")
    official = lookup.loc["official78_50w"]
    combo = lookup.loc["C_50w_c3_plus_30w_stock"]
    cash = lookup.loc["cash_50w_c3_plus_30w_cash"]
    c3 = lookup.loc["A_c3_50w"]
    is_smoother_than_78 = (
        _safe_float(combo["max_dd_percent"]) >= TARGET_MAX_DD
        and _safe_float(combo["ulcer"]) < _safe_float(official["ulcer"]) * 0.75
        and _safe_float(combo["worst_252d_return_pct"]) > _safe_float(official["worst_252d_return_pct"])
        and _safe_float(combo["worst_504d_return_pct"]) >= _safe_float(official["worst_504d_return_pct"])
    )
    beats_cash = (
        _safe_float(combo["total_return_pct"]) > _safe_float(cash["total_return_pct"])
        and _safe_float(combo["max_dd_percent"]) >= _safe_float(cash["max_dd_percent"]) - 0.75
    )
    if is_smoother_than_78 and beats_cash:
        decision = "stage075_combo_smoother_than_78_but_forward_paper_required"
    elif beats_cash:
        decision = "stage075_combo_beats_cash_but_smoothness_not_conclusive"
    else:
        decision = "stage075_combo_not_enough_vs_cash"
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "line_id": "futures_trend_drawdown30_preserve_return",
        "model_tag": MODEL_TAG,
        "decision": decision,
        "stage075_decision": _load_json(STAGE075_DECISION_PATH).get("decision"),
        "official78_total_return_pct": _safe_float(official["total_return_pct"]),
        "official78_max_dd_percent": _safe_float(official["max_dd_percent"]),
        "official78_ulcer": _safe_float(official["ulcer"]),
        "official78_longest_underwater_days": int(official["longest_underwater_days"]),
        "official78_worst_252d_return_pct": _safe_float(official["worst_252d_return_pct"]),
        "official78_worst_504d_return_pct": _safe_float(official["worst_504d_return_pct"]),
        "c3_total_return_pct": _safe_float(c3["total_return_pct"]),
        "c3_max_dd_percent": _safe_float(c3["max_dd_percent"]),
        "combo_total_return_pct": _safe_float(combo["total_return_pct"]),
        "combo_max_dd_percent": _safe_float(combo["max_dd_percent"]),
        "combo_ulcer": _safe_float(combo["ulcer"]),
        "combo_longest_underwater_days": int(combo["longest_underwater_days"]),
        "combo_worst_252d_return_pct": _safe_float(combo["worst_252d_return_pct"]),
        "combo_worst_504d_return_pct": _safe_float(combo["worst_504d_return_pct"]),
        "combo_vs_official78_return_delta_pp": _safe_float(combo["total_return_pct"])
        - _safe_float(official["total_return_pct"]),
        "combo_vs_official78_dd_improvement_pp": _safe_float(combo["max_dd_percent"])
        - _safe_float(official["max_dd_percent"]),
        "combo_vs_official78_ulcer_improvement_pct": (_safe_float(official["ulcer"]) - _safe_float(combo["ulcer"]))
        / _safe_float(official["ulcer"])
        * 100.0
        if _safe_float(official["ulcer"])
        else 0.0,
        "combo_vs_cash_return_delta_pp": _safe_float(combo["total_return_pct"])
        - _safe_float(cash["total_return_pct"]),
        "combo_vs_cash_dd_gap_pp": _safe_float(combo["max_dd_percent"]) - _safe_float(cash["max_dd_percent"]),
        "daily_return_corr_c3_stock": tail["daily_return_corr_c3_stock"],
        "stock_avg_ret_on_c3_left_tail_5pct": tail["stock_avg_ret_on_c3_left_tail_5pct"],
        "stock_positive_rate_on_c3_left_tail_5pct": tail["stock_positive_rate_on_c3_left_tail_5pct"],
        "start_2024_combo_vs_cash_dd_gap_pp": weak["combo_vs_cash_dd_gap_pp"],
        "strategy_change_allowed": False,
        "recommended_next_step": "stage075_forward_paper_and_start_2024_readonly_attribution",
    }


def _write_report(
    summary: pd.DataFrame,
    annual: pd.DataFrame,
    relative: pd.DataFrame,
    weak_rows: pd.DataFrame,
    weak_detail: dict[str, Any],
    tail: dict[str, Any],
    decision: dict[str, Any],
    paths: dict[str, Path],
) -> None:
    summary_display = summary[
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
    ].copy()
    annual_focus = annual[
        annual["variant"].isin(["official78_50w", "A_c3_50w", "C_50w_c3_plus_30w_stock"])
    ].copy()
    lines = [
        "# Stage076 Stage075平滑度与弱窗口审计",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        f"- 模型标签：`{MODEL_TAG}`",
        "- 阶段性质：只读审计；不修改78-1、C3或股票账户参数。",
        "- 外部调研结论：平滑度不能只看最大回撤，还要看回撤持续时间、Ulcer Index、滚动一年/两年收益和是否优于现金对照。",
        "",
        "## 运行前过拟合反思",
        "",
        "- 判断：否。",
        "- 原因：本阶段只比较既有曲线，指标预先固定，没有调权重、阈值或股票版本。",
        "",
        "## 运行前继续价值反思",
        "",
        "- 判断：是。",
        "- 原因：Stage075已是候选，但需要证明它是不是比78-1明显平滑，以及是否只是现金稀释。",
        "",
        "## 决策",
        "",
        f"- 决策：`{decision['decision']}`。",
        f"- 78-1：收益`{decision['official78_total_return_pct']:.4f}%`，最大回撤`{decision['official78_max_dd_percent']:.4f}%`，Ulcer `{decision['official78_ulcer']:.4f}`。",
        f"- Stage075组合：收益`{decision['combo_total_return_pct']:.4f}%`，最大回撤`{decision['combo_max_dd_percent']:.4f}%`，Ulcer `{decision['combo_ulcer']:.4f}`。",
        f"- 相对78-1：收益差`{decision['combo_vs_official78_return_delta_pp']:.4f}pp`，回撤改善`{decision['combo_vs_official78_dd_improvement_pp']:.4f}pp`，Ulcer改善`{decision['combo_vs_official78_ulcer_improvement_pct']:.2f}%`。",
        f"- 相对现金对照：收益差`{decision['combo_vs_cash_return_delta_pp']:.4f}pp`，回撤差`{decision['combo_vs_cash_dd_gap_pp']:.4f}pp`。",
        "",
        "## 平滑度指标",
        "",
        summary_display.round(4).to_markdown(index=False),
        "",
        "## 年度视角",
        "",
        annual_focus[
            [
                "variant",
                "year",
                "annual_return_pct",
                "annual_max_dd_percent",
                "annual_ulcer",
                "annual_new_high_days",
            ]
        ]
        .round(4)
        .to_markdown(index=False),
        "",
        "## 相对改善",
        "",
        relative.round(4).to_markdown(index=False),
        "",
        "## C3与股票腿相关性",
        "",
        f"- 日收益相关系数：`{tail['daily_return_corr_c3_stock']:.4f}`。",
        f"- C3最差5%日里，股票腿平均日收益：`{tail['stock_avg_ret_on_c3_left_tail_5pct']:.6f}`。",
        f"- C3最差5%日里，股票腿上涨比例：`{tail['stock_positive_rate_on_c3_left_tail_5pct']:.4f}`。",
        "",
        "## 2024弱窗口归因",
        "",
        f"- 组合最大回撤窗口：`{weak_detail['combo_peak_date']}` 至 `{weak_detail['combo_trough_date']}`，回撤 `{weak_detail['combo_max_dd_percent']:.4f}%`。",
        f"- 现金对照最大回撤：`{weak_detail['cash_max_dd_percent']:.4f}%`；组合相对现金回撤差 `{weak_detail['combo_vs_cash_dd_gap_pp']:.4f}pp`。",
        "",
        weak_rows.round(4).to_markdown(index=False),
        "",
        "## 运行后过拟合反思",
        "",
        "- 判断：否。",
        "- 原因：审计发现2024窗口仍有缺口，但没有据此调权重或改规则，只把候选限制为forward paper。",
        "",
        "## 运行后继续价值反思",
        "",
        "- 判断：有价值。",
        "- 原因：Stage075相对78-1平滑度改善明显，且略优于现金对照；但需要真实执行和2024弱窗口继续验证。",
        "",
        "## 下一步",
        "",
        "- 不升级正式策略；先做组合层forward paper。",
        "- 对2024弱窗口只做归因，不做股票权重或参数救援。",
        "- 若forward paper持续优于现金对照，再进入实盘前双账户部署评估。",
        "",
        "## 输出",
        "",
    ]
    for name, path in paths.items():
        lines.append(f"- `{name}`：`{path.name}`")
    paths["report"].write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_html(curves: list[Curve], summary: pd.DataFrame, paths: dict[str, Path]) -> None:
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        subplot_titles=("净值曲线", "回撤曲线"),
    )
    colors = {
        "official78_50w": "#ef4444",
        "A_c3_50w": "#2563eb",
        "cash_50w_c3_plus_30w_cash": "#64748b",
        "C_50w_c3_plus_30w_stock": "#16a34a",
        "B_stock_30w": "#f97316",
    }
    show_order = [
        "official78_50w",
        "A_c3_50w",
        "cash_50w_c3_plus_30w_cash",
        "C_50w_c3_plus_30w_stock",
        "B_stock_30w",
    ]
    lookup = {curve.variant: curve for curve in curves}
    for variant in show_order:
        curve = lookup[variant]
        nav = curve.equity / curve.initial_capital
        dd = _underwater_series(nav) * 100.0
        fig.add_trace(
            go.Scatter(
                x=nav.index,
                y=nav,
                mode="lines",
                name=curve.label,
                line=dict(width=2, color=colors.get(variant)),
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=dd.index,
                y=dd,
                mode="lines",
                name=f"{curve.label} 回撤",
                showlegend=False,
                line=dict(width=1.5, color=colors.get(variant)),
            ),
            row=2,
            col=1,
        )
    fig.update_layout(
        title="Stage076 平滑度与回撤审计",
        template="plotly_white",
        height=900,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(l=70, r=40, t=110, b=50),
    )
    fig.update_yaxes(title_text="净值", row=1, col=1)
    fig.update_yaxes(title_text="回撤 %", row=2, col=1)
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
    html = [
        "<!doctype html><html><head><meta charset='utf-8'>",
        "<title>Stage076 平滑度与回撤审计</title>",
        "<style>body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;margin:24px;background:#f8fafc;color:#0f172a}table{border-collapse:collapse;width:100%;background:white}th,td{border:1px solid #e2e8f0;padding:8px;text-align:right}th:first-child,td:first-child{text-align:left}.note{background:white;border:1px solid #e2e8f0;border-radius:8px;padding:14px;margin:12px 0}</style>",
        "</head><body>",
        "<h1>平滑度与回撤审计</h1>",
        "<div class='note'>固定既有曲线，只做只读审计；不调权重，不改策略参数。</div>",
        fig.to_html(full_html=False, include_plotlyjs="cdn"),
        "<h2>核心指标</h2>",
        table.to_html(index=False),
        "</body></html>",
    ]
    paths["html"].write_text("\n".join(html), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curves = _build_curves()
    summary = pd.DataFrame([_stats(curve) for curve in curves])
    annual = _annual_table(curves)
    relative = _relative_table(summary)
    tail = _correlation_and_tail(curves)
    weak_rows, weak_detail = _start_2024_attribution()
    decision = _build_decision(summary, relative, tail, weak_detail)

    paths = {
        "summary": OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv",
        "annual": OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_{MODEL_TAG}.csv",
        "relative": OUTPUT_DIR / f"{OUTPUT_PREFIX}_relative_{MODEL_TAG}.csv",
        "tail": OUTPUT_DIR / f"{OUTPUT_PREFIX}_tail_{MODEL_TAG}.json",
        "weak_2024": OUTPUT_DIR / f"{OUTPUT_PREFIX}_weak_2024_{MODEL_TAG}.csv",
        "decision": OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json",
        "report": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md",
        "html": OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.html",
    }
    summary.to_csv(paths["summary"], index=False, encoding="utf-8-sig")
    annual.to_csv(paths["annual"], index=False, encoding="utf-8-sig")
    relative.to_csv(paths["relative"], index=False, encoding="utf-8-sig")
    paths["tail"].write_text(json.dumps(tail, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    weak_rows.to_csv(paths["weak_2024"], index=False, encoding="utf-8-sig")
    paths["decision"].write_text(json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(summary, annual, relative, weak_rows, weak_detail, tail, decision, paths)
    _write_html(curves, summary, paths)

    print(json.dumps(decision, ensure_ascii=False, indent=2))
    print(f"report={paths['report']}")
    print(f"html={paths['html']}")


if __name__ == "__main__":
    main()
