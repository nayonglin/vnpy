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
MODEL_TAG = "stage375_independent_300k_stock_combo_v1"
OUTPUT_PREFIX = "qmt_roll_stage375_independent_300k_stock_combo"

C3_CURVES_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage359_c3_backfilled_supply_signal_validation_curves_stage359_c3_backfilled_supply_signal_validation_v1.csv"
)
C3_SUMMARY_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage359_c3_backfilled_supply_signal_validation_summary_stage359_c3_backfilled_supply_signal_validation_v1.csv"
)
STOCK_300K_DAILY_PATH = (
    PROJECT_DIR.parent
    / "alpha_research"
    / "native_results"
    / "stock_range_reversion_liquid_q3_300k_lot_feasibility_2018_2026"
    / "stock_range_reversion_liquid_q3_300k_lot_feasibility_v1_daily.csv"
)
STOCK_300K_SUMMARY_PATH = (
    PROJECT_DIR.parent
    / "alpha_research"
    / "native_results"
    / "stock_range_reversion_liquid_q3_300k_lot_feasibility_2018_2026"
    / "stock_range_reversion_liquid_q3_300k_lot_feasibility_v1_summary.json"
)

FUTURES_CAPITAL = 500_000.0
STOCK_CAPITAL = 300_000.0
TOTAL_CAPITAL = FUTURES_CAPITAL + STOCK_CAPITAL
TARGET_MAX_DD = -30.0
MIN_COMBO_RETURN_EDGE_VS_CASH = 20.0
C3_VARIANT = "C3_existing_2023plus"
C3_WINDOW = "full_2020_2026"
ROLLING_WINDOWS = (252, 504)
WINDOW_STARTS = {
    "full_2020_common": "2020-01-01",
    "start_2021": "2021-01-01",
    "start_2022": "2022-01-01",
    "start_2023": "2023-01-01",
    "start_2024": "2024-01-01",
    "start_2025": "2025-01-01",
    "ytd_2026": "2026-01-01",
}


@dataclass(frozen=True)
class CurveSpec:
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


def _max_drawdown(nav: pd.Series) -> float:
    if nav.empty:
        return 0.0
    return float((nav / nav.cummax() - 1.0).min())


def _ulcer(nav: pd.Series) -> float:
    if nav.empty:
        return 0.0
    dd_pct = (nav / nav.cummax() - 1.0) * 100.0
    return float(np.sqrt(np.mean(np.square(np.minimum(dd_pct, 0.0)))))


def _longest_underwater(nav: pd.Series) -> int:
    longest = 0
    current = 0
    for value in nav / nav.cummax() - 1.0:
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


def _stats_from_equity(
    variant: str,
    label: str,
    equity: pd.Series,
    initial_capital: float,
    window_name: str,
) -> dict[str, Any]:
    equity = equity.dropna().astype(float)
    if equity.empty:
        return {
            "variant": variant,
            "label": label,
            "window_name": window_name,
            "days": 0,
            "total_return_pct": 0.0,
            "max_dd_percent": 0.0,
            "sharpe": 0.0,
            "ulcer": 0.0,
            "longest_underwater_days": 0,
        }
    nav = equity / initial_capital
    daily_ret = nav.pct_change().fillna(nav.iloc[0] - 1.0)
    result = {
        "variant": variant,
        "label": label,
        "window_name": window_name,
        "days": int(len(equity)),
        "start_date": str(equity.index.min().date()),
        "end_date": str(equity.index.max().date()),
        "initial_capital": float(initial_capital),
        "end_equity": float(equity.iloc[-1]),
        "end_nav": float(nav.iloc[-1]),
        "total_return_pct": float((nav.iloc[-1] - 1.0) * 100.0),
        "max_dd_percent": _max_drawdown(nav) * 100.0,
        "sharpe": _annualized_sharpe(daily_ret),
        "ulcer": _ulcer(nav),
        "longest_underwater_days": _longest_underwater(nav),
        "positive_day_rate": float((daily_ret > 0.0).mean()),
    }
    for window in ROLLING_WINDOWS:
        if len(nav) >= window:
            result[f"worst_{window}d_return_pct"] = float((nav / nav.shift(window) - 1.0).min() * 100.0)
        else:
            result[f"worst_{window}d_return_pct"] = np.nan
    return result


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _load_c3_ret() -> pd.Series:
    if not C3_CURVES_PATH.exists():
        raise FileNotFoundError(C3_CURVES_PATH)
    df = pd.read_csv(C3_CURVES_PATH)
    df = df[(df["variant"] == C3_VARIANT) & (df["window_name"] == C3_WINDOW)].copy()
    if df.empty:
        raise ValueError(f"missing {C3_VARIANT}/{C3_WINDOW} in {C3_CURVES_PATH}")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df[df["date"].notna()].sort_values("date")
    balance = pd.to_numeric(df["balance"], errors="coerce").ffill()
    ret = balance.pct_change()
    ret.iloc[0] = balance.iloc[0] / FUTURES_CAPITAL - 1.0
    ret.index = pd.DatetimeIndex(df["date"])
    return ret.astype(float)


def _load_stock_ret() -> pd.Series:
    if not STOCK_300K_DAILY_PATH.exists():
        raise FileNotFoundError(STOCK_300K_DAILY_PATH)
    df = pd.read_csv(STOCK_300K_DAILY_PATH)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df[df["date"].notna()].sort_values("date")
    ret = pd.to_numeric(df["strategy_daily_ret_min_fee"], errors="coerce").fillna(0.0)
    ret.index = pd.DatetimeIndex(df["date"])
    return ret.astype(float)


def _align_returns(c3_ret: pd.Series, stock_ret: pd.Series) -> pd.DataFrame:
    start = max(c3_ret.index.min(), stock_ret.index.min(), pd.Timestamp("2020-01-01"))
    end = min(c3_ret.index.max(), stock_ret.index.max())
    index = pd.date_range(start=start, end=end, freq="D")
    frame = pd.DataFrame(index=index)
    frame["c3_ret"] = c3_ret.groupby(level=0).sum().reindex(index).fillna(0.0)
    frame["stock_ret"] = stock_ret.groupby(level=0).sum().reindex(index).fillna(0.0)
    return frame


def _curves_for_window(aligned: pd.DataFrame, start_day: str) -> list[CurveSpec]:
    window = aligned[aligned.index >= pd.Timestamp(start_day)].copy()
    if window.empty:
        return []
    c3_nav = (1.0 + window["c3_ret"]).cumprod()
    stock_nav = (1.0 + window["stock_ret"]).cumprod()
    c3_equity = FUTURES_CAPITAL * c3_nav
    stock_equity = STOCK_CAPITAL * stock_nav
    cash_control = c3_equity + STOCK_CAPITAL
    combo = c3_equity + stock_equity
    return [
        CurveSpec("A_c3_50w", "50万C3期货账户", FUTURES_CAPITAL, c3_equity),
        CurveSpec("B_stock_30w", "30万股票整手账户", STOCK_CAPITAL, stock_equity),
        CurveSpec("cash_50w_c3_plus_30w_cash", "50万C3 + 30万现金", TOTAL_CAPITAL, cash_control),
        CurveSpec("C_50w_c3_plus_30w_stock", "50万C3 + 30万股票账户", TOTAL_CAPITAL, combo),
    ]


def _build_outputs(aligned: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    summary_rows: list[dict[str, Any]] = []
    daily_frames: list[pd.DataFrame] = []
    for window_name, start_day in WINDOW_STARTS.items():
        for spec in _curves_for_window(aligned, start_day):
            stats = _stats_from_equity(spec.variant, spec.label, spec.equity, spec.initial_capital, window_name)
            summary_rows.append(stats)
            nav = spec.equity / spec.initial_capital
            daily = pd.DataFrame(
                {
                    "date": spec.equity.index,
                    "window_name": window_name,
                    "variant": spec.variant,
                    "label": spec.label,
                    "equity": spec.equity.values,
                    "nav": nav.values,
                    "drawdown_pct": (nav / nav.cummax() - 1.0).values * 100.0,
                    "daily_ret": nav.pct_change().fillna(nav.iloc[0] - 1.0).values,
                }
            )
            daily_frames.append(daily)
    summary = pd.DataFrame(summary_rows)
    daily_all = pd.concat(daily_frames, ignore_index=True)
    return summary, daily_all


def _build_window_compare(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for window_name, group in summary.groupby("window_name", sort=False):
        lookup = group.set_index("variant")
        if "C_50w_c3_plus_30w_stock" not in lookup.index or "cash_50w_c3_plus_30w_cash" not in lookup.index:
            continue
        c = lookup.loc["C_50w_c3_plus_30w_stock"]
        cash = lookup.loc["cash_50w_c3_plus_30w_cash"]
        c3 = lookup.loc["A_c3_50w"]
        rows.append(
            {
                "window_name": window_name,
                "combo_total_return_pct": _safe_float(c["total_return_pct"]),
                "cash_total_return_pct": _safe_float(cash["total_return_pct"]),
                "c3_total_return_pct": _safe_float(c3["total_return_pct"]),
                "combo_max_dd_percent": _safe_float(c["max_dd_percent"]),
                "cash_max_dd_percent": _safe_float(cash["max_dd_percent"]),
                "c3_max_dd_percent": _safe_float(c3["max_dd_percent"]),
                "combo_return_edge_vs_cash_pct": _safe_float(c["total_return_pct"])
                - _safe_float(cash["total_return_pct"]),
                "combo_dd_edge_vs_cash_pp": _safe_float(c["max_dd_percent"])
                - _safe_float(cash["max_dd_percent"]),
                "combo_dd_improvement_vs_c3_pp": _safe_float(c["max_dd_percent"])
                - _safe_float(c3["max_dd_percent"]),
                "combo_underwater_edge_vs_cash_days": int(cash["longest_underwater_days"])
                - int(c["longest_underwater_days"]),
                "combo_pass_dd30": _safe_float(c["max_dd_percent"]) >= TARGET_MAX_DD,
                "combo_beats_cash_return": _safe_float(c["total_return_pct"])
                > _safe_float(cash["total_return_pct"]),
                "combo_not_worse_than_cash_dd": _safe_float(c["max_dd_percent"])
                >= _safe_float(cash["max_dd_percent"]) - 0.50,
            }
        )
    return pd.DataFrame(rows)


def _build_decision(summary: pd.DataFrame, window_compare: pd.DataFrame) -> dict[str, Any]:
    full = window_compare[window_compare["window_name"] == "full_2020_common"].iloc[0]
    stock_summary = _load_json(STOCK_300K_SUMMARY_PATH)
    windows = window_compare.to_dict(orient="records")
    fail_windows = [
        row["window_name"]
        for row in windows
        if not (
            bool(row["combo_pass_dd30"])
            and bool(row["combo_beats_cash_return"])
            and bool(row["combo_not_worse_than_cash_dd"])
        )
    ]
    if (
        bool(full["combo_pass_dd30"])
        and bool(full["combo_beats_cash_return"])
        and _safe_float(full["combo_return_edge_vs_cash_pct"]) >= MIN_COMBO_RETURN_EDGE_VS_CASH
        and len(fail_windows) <= 1
    ):
        decision = "candidate_combo_layer_worth_forward_paper"
    elif bool(full["combo_pass_dd30"]) and bool(full["combo_beats_cash_return"]):
        decision = "conditional_combo_layer_better_than_cash_but_needs_more_robustness"
    else:
        decision = "fail_independent_stock_combo_not_better_than_cash_control"
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "line_id": "futures_trend_drawdown30_preserve_return",
        "model_tag": MODEL_TAG,
        "decision": decision,
        "futures_capital": FUTURES_CAPITAL,
        "stock_capital": STOCK_CAPITAL,
        "total_capital": TOTAL_CAPITAL,
        "common_start": str(summary["start_date"].min()),
        "common_end": str(summary["end_date"].max()),
        "target_max_dd_pct": TARGET_MAX_DD,
        "min_combo_return_edge_vs_cash_pct": MIN_COMBO_RETURN_EDGE_VS_CASH,
        "full_combo_total_return_pct": _safe_float(full["combo_total_return_pct"]),
        "full_combo_max_dd_percent": _safe_float(full["combo_max_dd_percent"]),
        "full_cash_total_return_pct": _safe_float(full["cash_total_return_pct"]),
        "full_cash_max_dd_percent": _safe_float(full["cash_max_dd_percent"]),
        "full_c3_total_return_pct": _safe_float(full["c3_total_return_pct"]),
        "full_c3_max_dd_percent": _safe_float(full["c3_max_dd_percent"]),
        "full_combo_return_edge_vs_cash_pct": _safe_float(full["combo_return_edge_vs_cash_pct"]),
        "full_combo_dd_edge_vs_cash_pp": _safe_float(full["combo_dd_edge_vs_cash_pp"]),
        "full_combo_dd_improvement_vs_c3_pp": _safe_float(full["combo_dd_improvement_vs_c3_pp"]),
        "fail_windows": fail_windows,
        "stock_source_total_return_min_fee": stock_summary.get("total_return_min_fee"),
        "stock_source_max_drawdown_min_fee": stock_summary.get("max_drawdown_min_fee"),
        "stock_source_zero_lot_target_ratio": stock_summary.get("zero_lot_target_ratio"),
        "strategy_change_allowed": False,
        "recommended_next_step": "forward_paper_combo_layer_or_find_stronger_independent_return_source",
    }


def _write_report(
    summary: pd.DataFrame,
    window_compare: pd.DataFrame,
    decision: dict[str, Any],
    paths: dict[str, Path],
) -> None:
    full_summary = summary[summary["window_name"] == "full_2020_common"].copy()
    lines = [
        "# Stage075 独立30万股票账户组合层验证",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        f"- 模型标签：`{MODEL_TAG}`",
        "- 阶段性质：组合层验证；不新增期货信号、不修改C3参数、不扫股票权重。",
        "- 假设：如果股票震荡账户是低相关独立收益源，那么`50万C3 + 30万股票账户`应优于`50万C3 + 30万现金`，且全周期最大回撤进入30%以内。",
        "- 外部调研结论：组合分散的有效性来自低相关与左尾不同步；同源趋势补丁和小阈值优化不能提供这种结构性分散。",
        "",
        "## 运行前过拟合反思",
        "",
        "- 判断：否。",
        "- 原因：固定使用既有C3曲线和既有30万股票整手账户，不新增参数、不调整权重、不按结果挑股票版本。",
        "",
        "## 运行前继续价值反思",
        "",
        "- 判断：是。",
        "- 原因：当前期货内部补丁多次失败，独立账户组合层是低过拟合且真实可执行的下一条路径。",
        "",
        "## 决策",
        "",
        f"- 决策：`{decision['decision']}`。",
        f"- 全周期组合收益：`{decision['full_combo_total_return_pct']:.4f}%`；最大回撤：`{decision['full_combo_max_dd_percent']:.4f}%`。",
        f"- 现金对照收益：`{decision['full_cash_total_return_pct']:.4f}%`；最大回撤：`{decision['full_cash_max_dd_percent']:.4f}%`。",
        f"- 单独C3收益：`{decision['full_c3_total_return_pct']:.4f}%`；最大回撤：`{decision['full_c3_max_dd_percent']:.4f}%`。",
        f"- 组合相对现金多收益：`{decision['full_combo_return_edge_vs_cash_pct']:.4f}pp`；相对现金回撤变化：`{decision['full_combo_dd_edge_vs_cash_pp']:.4f}pp`。",
        f"- 组合相对单独C3回撤改善：`{decision['full_combo_dd_improvement_vs_c3_pp']:.4f}pp`。",
        f"- 未完全通过窗口：`{', '.join(decision['fail_windows']) if decision['fail_windows'] else '无'}`。",
        "",
        "## 全周期对比",
        "",
        full_summary[
            [
                "variant",
                "label",
                "initial_capital",
                "total_return_pct",
                "max_dd_percent",
                "sharpe",
                "ulcer",
                "longest_underwater_days",
                "worst_252d_return_pct",
                "worst_504d_return_pct",
            ]
        ].to_markdown(index=False),
        "",
        "## 多起点窗口",
        "",
        window_compare.to_markdown(index=False),
        "",
        "## 运行后过拟合反思",
        "",
        "- 判断：否。",
        "- 原因：结果仅用于判断独立账户组合层是否优于现金对照，没有继续扫股票权重或挑窗口救结果。",
        "",
        "## 运行后继续价值反思",
        "",
        "- 判断：有价值。",
        "- 原因：该路径直接检验低相关独立收益源能否改善全账户路径；如果通过，应进入影子组合层paper，而不是马上改期货策略。",
        "",
        "## 下一步",
        "",
        "- 若判定为候选：做组合层forward paper，对齐真实股票账户成交、可买一手、停牌/ST/涨跌停限制。",
        "- 若未通过：保留为低相关思路证据，继续寻找更强独立收益源，不回到小阈值扫参。",
        "",
        "## 输出",
        "",
    ]
    for name, path in paths.items():
        lines.append(f"- `{name}`：`{path.name}`")
    paths["report"].write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_html(daily: pd.DataFrame, summary: pd.DataFrame, paths: dict[str, Path]) -> None:
    full_daily = daily[daily["window_name"] == "full_2020_common"].copy()
    full_summary = summary[summary["window_name"] == "full_2020_common"].copy()
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        subplot_titles=("全周期权益曲线", "全周期回撤"),
    )
    order = [
        "A_c3_50w",
        "cash_50w_c3_plus_30w_cash",
        "C_50w_c3_plus_30w_stock",
        "B_stock_30w",
    ]
    labels = full_daily.drop_duplicates("variant").set_index("variant")["label"].to_dict()
    colors = {
        "A_c3_50w": "#2563eb",
        "cash_50w_c3_plus_30w_cash": "#64748b",
        "C_50w_c3_plus_30w_stock": "#16a34a",
        "B_stock_30w": "#f97316",
    }
    for variant in order:
        chunk = full_daily[full_daily["variant"] == variant]
        if chunk.empty:
            continue
        fig.add_trace(
            go.Scatter(
                x=chunk["date"],
                y=chunk["nav"],
                mode="lines",
                name=labels.get(variant, variant),
                line=dict(width=2, color=colors.get(variant)),
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=chunk["date"],
                y=chunk["drawdown_pct"],
                mode="lines",
                name=f"{labels.get(variant, variant)} 回撤",
                showlegend=False,
                line=dict(width=1.5, color=colors.get(variant)),
            ),
            row=2,
            col=1,
        )
    table = full_summary[
        [
            "label",
            "initial_capital",
            "total_return_pct",
            "max_dd_percent",
            "sharpe",
            "ulcer",
            "longest_underwater_days",
        ]
    ].round(4)
    fig.update_layout(
        title="Stage075 独立30万股票账户组合层验证",
        template="plotly_white",
        height=880,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(l=70, r=40, t=110, b=50),
    )
    fig.update_yaxes(title_text="净值", row=1, col=1)
    fig.update_yaxes(title_text="回撤 %", row=2, col=1)
    html = [
        "<!doctype html><html><head><meta charset='utf-8'>",
        "<title>Stage075 独立30万股票账户组合层验证</title>",
        "<style>body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;margin:24px;background:#f8fafc;color:#0f172a}table{border-collapse:collapse;width:100%;background:white}th,td{border:1px solid #e2e8f0;padding:8px;text-align:right}th:first-child,td:first-child{text-align:left}h1,h2{margin-top:28px}.note{background:white;border:1px solid #e2e8f0;border-radius:8px;padding:14px;margin:12px 0}</style>",
        "</head><body>",
        "<h1>独立30万股票账户组合层验证</h1>",
        "<div class='note'>固定口径：50万C3期货账户、30万股票整手账户、30万现金对照；不调权重，不挑窗口。</div>",
        fig.to_html(full_html=False, include_plotlyjs="cdn"),
        "<h2>全周期指标</h2>",
        table.to_html(index=False),
        "</body></html>",
    ]
    paths["html"].write_text("\n".join(html), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    c3_ret = _load_c3_ret()
    stock_ret = _load_stock_ret()
    aligned = _align_returns(c3_ret, stock_ret)
    summary, daily = _build_outputs(aligned)
    window_compare = _build_window_compare(summary)
    decision = _build_decision(summary, window_compare)

    paths = {
        "summary": OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv",
        "daily": OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv",
        "window_compare": OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_compare_{MODEL_TAG}.csv",
        "decision": OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json",
        "report": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md",
        "html": OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.html",
    }
    summary.to_csv(paths["summary"], index=False, encoding="utf-8-sig")
    daily.to_csv(paths["daily"], index=False, encoding="utf-8-sig")
    window_compare.to_csv(paths["window_compare"], index=False, encoding="utf-8-sig")
    paths["decision"].write_text(json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(summary, window_compare, decision, paths)
    _write_html(daily, summary, paths)

    print(json.dumps(decision, ensure_ascii=False, indent=2))
    print(f"report={paths['report']}")
    print(f"html={paths['html']}")


if __name__ == "__main__":
    main()
