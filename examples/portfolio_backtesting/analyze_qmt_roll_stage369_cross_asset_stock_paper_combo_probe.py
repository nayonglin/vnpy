from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
MODEL_TAG = "stage369_cross_asset_stock_paper_combo_probe_v1"
OUTPUT_PREFIX = "qmt_roll_stage369_cross_asset_stock_paper_combo_probe"

C3_DAILY_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage336_c3_cash_reserve_multiperiod_daily_stage336_c3_cash_reserve_multiperiod_v1.csv"
)
OFFICIAL78_DAILY_PATH = OUTPUT_DIR / "qmt_roll_official_stage78_1_daily_equity.csv"
STOCK_DAILY_PATH = (
    PROJECT_DIR.parent
    / "alpha_research"
    / "native_results"
    / "stock_range_reversion_liquid_q3_paper_ledger_2018_2026"
    / "stock_range_reversion_liquid_q3_paper_ledger_v1_daily_ledger.csv"
)

INITIAL_CAPITAL = 500_000.0
BASE_PROFILE = "c3_active100_cash0"
BASE_WINDOW = "start_2020"
COMBO_WEIGHTS = (0.95, 0.90, 0.85, 0.80, 0.70)
ROLLING_WINDOWS = (252, 504)


@dataclass(frozen=True)
class SeriesSpec:
    name: str
    label: str
    daily_ret: pd.Series
    c3_weight_pct: int | None = None
    stock_weight_pct: int | None = None
    cash_weight_pct: int | None = None


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
    peak = nav.cummax()
    dd = nav / peak - 1.0
    return float(dd.min())


def _ulcer(nav: pd.Series) -> float:
    if nav.empty:
        return 0.0
    dd_pct = (nav / nav.cummax() - 1.0) * 100.0
    return float(np.sqrt(np.mean(np.square(np.minimum(dd_pct, 0.0)))))


def _longest_underwater(nav: pd.Series) -> int:
    if nav.empty:
        return 0
    dd = nav / nav.cummax() - 1.0
    longest = 0
    current = 0
    for value in dd:
        if value < -1e-12:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return int(longest)


def _annualized_sharpe(daily_ret: pd.Series) -> float:
    daily_ret = daily_ret.dropna()
    if daily_ret.empty:
        return 0.0
    std = float(daily_ret.std(ddof=1))
    if std <= 0:
        return 0.0
    return float(daily_ret.mean() / std * math.sqrt(252.0))


def _stats(name: str, label: str, daily_ret: pd.Series) -> dict[str, Any]:
    daily_ret = daily_ret.fillna(0.0).astype(float)
    nav = (1.0 + daily_ret).cumprod()
    if nav.empty:
        return {
            "variant": name,
            "label": label,
            "days": 0,
            "total_return_pct": 0.0,
            "max_dd_percent": 0.0,
            "sharpe": 0.0,
            "ulcer": 0.0,
            "longest_underwater_days": 0,
            "positive_day_rate": 0.0,
        }
    rolling = {}
    for window in ROLLING_WINDOWS:
        if len(daily_ret) >= window:
            rolling_nav = nav / nav.shift(window)
            rolling[f"worst_{window}d_return_pct"] = float((rolling_nav - 1.0).min() * 100.0)
        else:
            rolling[f"worst_{window}d_return_pct"] = np.nan
    result = {
        "variant": name,
        "label": label,
        "days": int(len(daily_ret)),
        "start_date": str(daily_ret.index.min().date()),
        "end_date": str(daily_ret.index.max().date()),
        "end_nav": float(nav.iloc[-1]),
        "total_return_pct": float((nav.iloc[-1] - 1.0) * 100.0),
        "max_dd_percent": _max_drawdown(nav) * 100.0,
        "sharpe": _annualized_sharpe(daily_ret),
        "ulcer": _ulcer(nav),
        "longest_underwater_days": _longest_underwater(nav),
        "positive_day_rate": float((daily_ret > 0).mean()),
    }
    result.update(rolling)
    return result


def _window_masks(index: pd.DatetimeIndex) -> dict[str, pd.Series]:
    return {
        "full_2020_2026_common": pd.Series(True, index=index),
        "start_2021": pd.Series(index >= pd.Timestamp("2021-01-01"), index=index),
        "start_2022": pd.Series(index >= pd.Timestamp("2022-01-01"), index=index),
        "start_2023": pd.Series(index >= pd.Timestamp("2023-01-01"), index=index),
        "start_2024": pd.Series(index >= pd.Timestamp("2024-01-01"), index=index),
        "ytd_2026": pd.Series(index >= pd.Timestamp("2026-01-01"), index=index),
        "c3_2021_peak_to_trough": pd.Series(
            (index >= pd.Timestamp("2021-05-12")) & (index <= pd.Timestamp("2021-07-02")),
            index=index,
        ),
    }


def _load_c3_daily_ret() -> pd.Series:
    if not C3_DAILY_PATH.exists():
        raise FileNotFoundError(C3_DAILY_PATH)
    df = pd.read_csv(C3_DAILY_PATH)
    df = df[(df["profile"] == BASE_PROFILE) & (df["window_name"] == BASE_WINDOW)].copy()
    if df.empty:
        raise ValueError(f"missing {BASE_PROFILE}/{BASE_WINDOW} in {C3_DAILY_PATH}")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df[df["date"].notna()].sort_values("date")
    balance = pd.to_numeric(df["balance"], errors="coerce").ffill()
    ret = balance.pct_change()
    ret.iloc[0] = balance.iloc[0] / INITIAL_CAPITAL - 1.0
    ret.index = pd.DatetimeIndex(df["date"])
    return ret.astype(float)


def _load_official78_daily_ret() -> pd.Series:
    if not OFFICIAL78_DAILY_PATH.exists():
        raise FileNotFoundError(OFFICIAL78_DAILY_PATH)
    df = pd.read_csv(OFFICIAL78_DAILY_PATH)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df[df["date"].notna()].sort_values("date")
    balance = pd.to_numeric(df["balance"], errors="coerce").ffill()
    ret = balance.pct_change()
    ret.iloc[0] = balance.iloc[0] / INITIAL_CAPITAL - 1.0
    ret.index = pd.DatetimeIndex(df["date"])
    return ret.astype(float)


def _load_stock_daily_ret() -> pd.Series:
    if not STOCK_DAILY_PATH.exists():
        raise FileNotFoundError(STOCK_DAILY_PATH)
    df = pd.read_csv(STOCK_DAILY_PATH)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df[df["date"].notna()].sort_values("date")
    ret = pd.to_numeric(df["strategy_daily_ret"], errors="coerce").fillna(0.0)
    ret.index = pd.DatetimeIndex(df["date"])
    return ret.astype(float)


def _align_returns(c3_ret: pd.Series, stock_ret: pd.Series, official78_ret: pd.Series) -> pd.DataFrame:
    start = max(c3_ret.index.min(), stock_ret.index.min(), official78_ret.index.min(), pd.Timestamp("2020-01-01"))
    end = min(c3_ret.index.max(), stock_ret.index.max(), official78_ret.index.max())
    index = pd.date_range(start=start, end=end, freq="D")
    aligned = pd.DataFrame(index=index)
    aligned["official78_ret"] = official78_ret.groupby(level=0).sum().reindex(index).fillna(0.0)
    aligned["c3_ret"] = c3_ret.groupby(level=0).sum().reindex(index).fillna(0.0)
    aligned["stock_paper_ret"] = stock_ret.groupby(level=0).sum().reindex(index).fillna(0.0)
    return aligned


def _build_series(aligned: pd.DataFrame) -> list[SeriesSpec]:
    series = [
        SeriesSpec("O_official78_100", "正式78-1 100%", aligned["official78_ret"]),
        SeriesSpec("A_c3_100", "C3 100%", aligned["c3_ret"]),
        SeriesSpec("B_stock_paper_100", "股票paper 100%", aligned["stock_paper_ret"]),
    ]
    for w in COMBO_WEIGHTS:
        stock_w = 1.0 - w
        c3_pct = int(round(w * 100))
        stock_pct = int(round(stock_w * 100))
        series.append(
            SeriesSpec(
                f"C_c3_{c3_pct:02d}_stock_{stock_pct:02d}",
                f"C3 {w:.0%} + 股票paper {stock_w:.0%}",
                w * aligned["c3_ret"] + stock_w * aligned["stock_paper_ret"],
                c3_weight_pct=c3_pct,
                stock_weight_pct=stock_pct,
            )
        )
        series.append(
            SeriesSpec(
                f"cash_control_c3_{c3_pct:02d}_cash_{stock_pct:02d}",
                f"C3 {w:.0%} + 现金 {stock_w:.0%}",
                w * aligned["c3_ret"],
                c3_weight_pct=c3_pct,
                cash_weight_pct=stock_pct,
            )
        )
    return series


def _build_daily_frame(series: list[SeriesSpec]) -> pd.DataFrame:
    frames = []
    for spec in series:
        ret = spec.daily_ret.fillna(0.0).astype(float)
        nav = (1.0 + ret).cumprod()
        frames.append(
            pd.DataFrame(
                {
                    "date": ret.index,
                    "variant": spec.name,
                    "label": spec.label,
                    "daily_ret": ret.values,
                    "nav": nav.values,
                    "drawdown": (nav / nav.cummax() - 1.0).values,
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def _build_summary(series: list[SeriesSpec]) -> pd.DataFrame:
    rows = []
    for spec in series:
        rows.append(_stats(spec.name, spec.label, spec.daily_ret))
    summary = pd.DataFrame(rows)
    c3_return = _safe_float(summary.loc[summary["variant"] == "A_c3_100", "total_return_pct"].iloc[0])
    for idx, row in summary.iterrows():
        if row["variant"] == "A_c3_100":
            summary.loc[idx, "return_retention_vs_c3_pct"] = 100.0
        else:
            summary.loc[idx, "return_retention_vs_c3_pct"] = (
                _safe_float(row["total_return_pct"]) / c3_return * 100.0 if c3_return else np.nan
            )
    return summary


def _build_window_summary(series: list[SeriesSpec], index: pd.DatetimeIndex) -> pd.DataFrame:
    rows = []
    masks = _window_masks(index)
    for window_name, mask in masks.items():
        for spec in series:
            ret = spec.daily_ret.loc[mask[mask].index]
            if ret.empty:
                continue
            row = _stats(spec.name, spec.label, ret)
            row["window_name"] = window_name
            rows.append(row)
    frame = pd.DataFrame(rows)
    for window_name, group in frame.groupby("window_name"):
        c3 = group[group["variant"] == "A_c3_100"]
        if c3.empty:
            continue
        c3_return = _safe_float(c3["total_return_pct"].iloc[0])
        idxs = frame["window_name"].eq(window_name)
        frame.loc[idxs, "return_retention_vs_c3_pct"] = frame.loc[idxs, "total_return_pct"].apply(
            lambda x: _safe_float(x) / c3_return * 100.0 if c3_return else np.nan
        )
    return frame


def _build_annual_summary(series: list[SeriesSpec]) -> pd.DataFrame:
    rows = []
    for spec in series:
        ret = spec.daily_ret.fillna(0.0).astype(float)
        for year, group in ret.groupby(ret.index.year):
            if group.empty:
                continue
            row = _stats(spec.name, spec.label, group)
            row["year"] = int(year)
            rows.append(row)
    return pd.DataFrame(rows)


def _decision(summary: pd.DataFrame, window_summary: pd.DataFrame) -> dict[str, Any]:
    c3 = summary[summary["variant"] == "A_c3_100"].iloc[0].to_dict()
    combos = summary[summary["variant"].str.startswith("C_c3_")].copy()
    decisions: list[dict[str, Any]] = []
    for _, row in combos.iterrows():
        variant = str(row["variant"])
        c3_pct = variant.split("_c3_")[-1].split("_stock_")[0]
        stock_pct = variant.split("_stock_")[-1]
        cash_variant = f"cash_control_c3_{c3_pct}_cash_{stock_pct}"
        cash_row = summary[summary["variant"] == cash_variant]
        same_cash_return = _safe_float(cash_row["total_return_pct"].iloc[0]) if not cash_row.empty else np.nan
        same_cash_dd = _safe_float(cash_row["max_dd_percent"].iloc[0]) if not cash_row.empty else np.nan
        windows = window_summary[window_summary["variant"] == variant].copy()
        window_failures: list[dict[str, Any]] = []
        for _, win_row in windows.iterrows():
            window_name = str(win_row["window_name"])
            c3_window = window_summary[
                (window_summary["window_name"].eq(window_name))
                & (window_summary["variant"].eq("A_c3_100"))
            ]
            c3_window_return = _safe_float(c3_window["total_return_pct"].iloc[0]) if not c3_window.empty else np.nan
            candidate_return = _safe_float(win_row["total_return_pct"])
            candidate_dd = _safe_float(win_row["max_dd_percent"])
            if candidate_dd < -30.0:
                window_failures.append(
                    {
                        "window_name": window_name,
                        "reason": "max_drawdown_below_30",
                        "candidate_return_pct": candidate_return,
                        "candidate_max_dd_percent": candidate_dd,
                        "c3_return_pct": c3_window_return,
                    }
                )
                continue
            if c3_window_return > 0.0:
                retention = candidate_return / c3_window_return * 100.0
                if retention < 80.0:
                    window_failures.append(
                        {
                            "window_name": window_name,
                            "reason": "positive_window_return_retention_below_80",
                            "candidate_return_pct": candidate_return,
                            "candidate_max_dd_percent": candidate_dd,
                            "c3_return_pct": c3_window_return,
                            "return_retention_vs_c3_pct": retention,
                        }
                    )
            elif candidate_return < c3_window_return:
                window_failures.append(
                    {
                        "window_name": window_name,
                        "reason": "negative_window_worse_than_c3",
                        "candidate_return_pct": candidate_return,
                        "candidate_max_dd_percent": candidate_dd,
                        "c3_return_pct": c3_window_return,
                    }
                )
        pass_gate = (
            _safe_float(row["max_dd_percent"]) >= -30.0
            and _safe_float(row["return_retention_vs_c3_pct"]) >= 80.0
            and _safe_float(row["total_return_pct"]) > same_cash_return
            and not window_failures
        )
        decisions.append(
            {
                "variant": variant,
                "stock_weight_pct": stock_pct,
                "max_dd_percent": _safe_float(row["max_dd_percent"]),
                "total_return_pct": _safe_float(row["total_return_pct"]),
                "return_retention_vs_c3_pct": _safe_float(row["return_retention_vs_c3_pct"]),
                "ulcer": _safe_float(row["ulcer"]),
                "cash_control_total_return_pct": same_cash_return,
                "cash_control_max_dd_percent": same_cash_dd,
                "beats_same_weight_cash": bool(_safe_float(row["total_return_pct"]) > same_cash_return),
                "fail_window_count": int(len(window_failures)),
                "fail_windows": window_failures,
                "pass_gate": bool(pass_gate),
            }
        )
    decision_df = pd.DataFrame(decisions)
    pass_df = decision_df[decision_df["pass_gate"]]
    if pass_df.empty:
        label = "fail_cross_asset_stock_paper_not_promoted"
        best = decision_df.sort_values(["max_dd_percent", "return_retention_vs_c3_pct"], ascending=[False, False]).head(1)
    else:
        label = "candidate_requires_oos_and_real_capital_review"
        best = pass_df.sort_values(["ulcer", "return_retention_vs_c3_pct"], ascending=[True, False]).head(1)
    return {
        "decision": label,
        "baseline": c3,
        "best_variant": best.iloc[0].to_dict() if not best.empty else {},
        "predeclared_gates": {
            "max_drawdown_percent_min": -30.0,
            "return_retention_vs_c3_percent_min": 80.0,
            "must_beat_same_weight_cash_dilution": True,
            "all_start_windows_must_pass": True,
            "paper_stock_not_formal_live_candidate": True,
        },
        "combo_decisions": decisions,
    }


def _write_report(
    summary: pd.DataFrame,
    window_summary: pd.DataFrame,
    annual_summary: pd.DataFrame,
    decision: dict[str, Any],
    paths: dict[str, Path],
) -> None:
    combo = summary[
        summary["variant"].str.startswith("A_")
        | summary["variant"].str.startswith("B_")
        | summary["variant"].str.startswith("C_")
        | summary["variant"].str.startswith("O_")
        | summary["variant"].str.startswith("cash_control_")
    ].copy()
    top_cols = [
        "variant",
        "label",
        "total_return_pct",
        "max_dd_percent",
        "return_retention_vs_c3_pct",
        "sharpe",
        "ulcer",
        "longest_underwater_days",
    ]
    lines = [
        "# Stage369 跨资产股票paper组合探针",
        "",
        "## 结论先行",
        "",
        f"- 决策：`{decision['decision']}`。",
        "- 本阶段只读取已有 C3 日度曲线和股票震荡 paper 日账本，不改期货策略、不改股票信号、不调权重小数。",
        "- 股票paper只能作为跨资产组合层平滑器探针；由于仍是 paper 监控线，不能直接升级为实盘候选。",
        "",
        "## 外部调研与判断",
        "",
        "- 趋势跟随研究普遍强调跨市场/跨资产分散是平滑路径的核心来源之一。",
        "- 但本地目标不是证明跨资产一定有效，而是要求新增承载必须优于同权重现金稀释，否则只是拿收益换回撤。",
        "",
        "## 预声明闸门",
        "",
        "- 全样本最大回撤必须进入 `-30%` 以内。",
        "- 全样本收益保留必须不低于 C3 的 `80%`。",
        "- 同权重下必须优于 `C3 + 现金` 稀释对照。",
        "- 起始年份/弱窗口不能靠单一时期获胜。",
        "",
        "## 全样本结果",
        "",
        combo[top_cols].to_markdown(index=False, floatfmt=".4f"),
        "",
        "## 年度收益与平滑度参照",
        "",
        annual_summary[
            annual_summary["variant"].isin(
                [
                    "O_official78_100",
                    "A_c3_100",
                    "C_c3_95_stock_05",
                    "cash_control_c3_95_cash_05",
                ]
            )
        ][
            [
                "year",
                "variant",
                "total_return_pct",
                "max_dd_percent",
                "ulcer",
                "longest_underwater_days",
            ]
        ].to_markdown(index=False, floatfmt=".4f"),
        "",
        "## 多窗口结果",
        "",
        window_summary[
            window_summary["variant"].str.startswith("C_")
            | window_summary["variant"].eq("A_c3_100")
            | window_summary["variant"].eq("O_official78_100")
        ][
            [
                "window_name",
                "variant",
                "total_return_pct",
                "max_dd_percent",
                "return_retention_vs_c3_pct",
                "ulcer",
                "longest_underwater_days",
            ]
        ].to_markdown(index=False, floatfmt=".4f"),
        "",
        "## 过拟合反思",
        "",
        "- 运行前判断：不是过拟合。原因是先验来自跨资产低相关与独立承载，不是为某个亏损窗口补丁。",
        "- 运行后判断：若候选未通过，不继续调股票权重小数救援；若通过，也只能进入 OOS/真实资本约束复核。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前判断：有价值。当前期货内部多条卫星已反证，检验独立承载是合理下一步。",
        "- 运行后判断：以本阶段决策为准；若未通过，继续价值应转向其他独立收益源，而不是继续压股票paper权重。",
        "",
        "## 输出",
        "",
        f"- summary：`{paths['summary'].name}`",
        f"- window_summary：`{paths['window_summary'].name}`",
        f"- annual_summary：`{paths['annual_summary'].name}`",
        f"- daily：`{paths['daily'].name}`",
        f"- decision：`{paths['decision'].name}`",
        f"- html：`{paths['html'].name}`",
    ]
    paths["report"].write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_html(daily: pd.DataFrame, summary: pd.DataFrame, decision: dict[str, Any], path: Path) -> None:
    show_variants = [
        "O_official78_100",
        "A_c3_100",
        "C_c3_95_stock_05",
        "cash_control_c3_95_cash_05",
        "B_stock_paper_100",
    ]
    labels = summary.set_index("variant")["label"].to_dict()
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        subplot_titles=("净值曲线", "回撤曲线"),
    )
    for variant in show_variants:
        sub = daily[daily["variant"].eq(variant)].copy()
        if sub.empty:
            continue
        fig.add_trace(
            go.Scatter(
                x=sub["date"],
                y=sub["nav"],
                mode="lines",
                name=labels.get(variant, variant),
                hovertemplate="%{x|%Y-%m-%d}<br>净值=%{y:.4f}<extra></extra>",
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=sub["date"],
                y=sub["drawdown"] * 100.0,
                mode="lines",
                name=labels.get(variant, variant),
                showlegend=False,
                hovertemplate="%{x|%Y-%m-%d}<br>回撤=%{y:.2f}%<extra></extra>",
            ),
            row=2,
            col=1,
        )
    fig.add_hline(y=-30.0, line_dash="dash", line_color="#ef4444", row=2, col=1)
    fig.update_layout(
        title=(
            "Stage369 跨资产股票paper组合探针"
            f" | 决策: {decision['decision']}"
        ),
        template="plotly_white",
        height=900,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.04, xanchor="left", x=0),
        margin=dict(l=60, r=30, t=110, b=50),
    )
    fig.update_yaxes(title_text="净值倍数", row=1, col=1)
    fig.update_yaxes(title_text="回撤(%)", row=2, col=1)
    fig.update_xaxes(title_text="日期", row=2, col=1)
    path.write_text(fig.to_html(include_plotlyjs="cdn", full_html=True), encoding="utf-8")


def main() -> None:
    c3_ret = _load_c3_daily_ret()
    stock_ret = _load_stock_daily_ret()
    official78_ret = _load_official78_daily_ret()
    aligned = _align_returns(c3_ret, stock_ret, official78_ret)
    if aligned.empty:
        raise ValueError("no overlapping dates between C3 and stock paper returns")

    series = _build_series(aligned)
    daily = _build_daily_frame(series)
    summary = _build_summary(series)
    window_summary = _build_window_summary(series, aligned.index)
    annual_summary = _build_annual_summary(series)
    decision = _decision(summary, window_summary)

    paths = {
        "summary": OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv",
        "window_summary": OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_summary_{MODEL_TAG}.csv",
        "annual_summary": OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_summary_{MODEL_TAG}.csv",
        "daily": OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv",
        "decision": OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json",
        "report": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md",
        "html": OUTPUT_DIR / f"{OUTPUT_PREFIX}_equity_drawdown_{MODEL_TAG}.html",
    }

    summary.to_csv(paths["summary"], index=False)
    window_summary.to_csv(paths["window_summary"], index=False)
    annual_summary.to_csv(paths["annual_summary"], index=False)
    daily.to_csv(paths["daily"], index=False)
    paths["decision"].write_text(
        json.dumps(decision, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    _write_report(summary, window_summary, annual_summary, decision, paths)
    _write_html(daily, summary, decision, paths["html"])

    print(json.dumps({"decision": decision["decision"], "best_variant": decision["best_variant"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
