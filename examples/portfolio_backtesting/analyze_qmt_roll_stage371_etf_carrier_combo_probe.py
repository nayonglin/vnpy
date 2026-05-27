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
ALPHA_RESULTS_DIR = PROJECT_DIR.parent / "alpha_research" / "native_results"

MODEL_TAG = "stage371_etf_carrier_combo_probe_v1"
OUTPUT_PREFIX = "qmt_roll_stage371_etf_carrier_combo_probe"

C3_DAILY_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage336_c3_cash_reserve_multiperiod_daily_stage336_c3_cash_reserve_multiperiod_v1.csv"
)
OFFICIAL78_DAILY_PATH = OUTPUT_DIR / "qmt_roll_official_stage78_1_daily_equity.csv"
ETF_SIGNAL_DAILY_PATH = (
    ALPHA_RESULTS_DIR
    / "stock_range_reversion_broad_etf_signal_sleeve_2018_2026"
    / "stock_range_reversion_broad_etf_signal_sleeve_v1_daily.csv"
)
ETF_FIXED_DAILY_PATH = (
    ALPHA_RESULTS_DIR
    / "stock_range_reversion_broad_etf_fixed_index_sleeve_2018_2026"
    / "stock_range_reversion_broad_etf_fixed_index_sleeve_v1_daily.csv"
)

INITIAL_CAPITAL = 500_000.0
BASE_PROFILE = "c3_active100_cash0"
BASE_WINDOW = "start_2020"
COMBO_WEIGHTS = (0.95, 0.90)
PASS_MAX_DD = -30.0
PASS_RETURN_RETENTION = 80.0

# Predeclared, low-degree ETF carriers. They were not selected by C3 combo results.
ETF_SIGNAL_CANDIDATES = (
    "primary_core_liquid_p10_50000__connors_rsi2_ma200__sleeve10__cap50__cost20bp",
    "primary_core_liquid_p10_50000__connors_rsi2_ma200__sleeve10__cap30__cost20bp",
    "primary_core_liquid_p10_50000__connors_rsi2_ma200__sleeve5__cap30__cost20bp",
    "primary_long_all__connors_rsi2_ma200__sleeve10__cap50__cost20bp",
)
ETF_FIXED_CANDIDATES = (
    ("510300.SH", "bollinger20_2_ma200", 0.10, 20.0),
    ("510300.SH", "bollinger20_2_ma200", 0.05, 20.0),
    ("515810.SH", "bollinger20_2_ma200", 0.10, 20.0),
)


@dataclass(frozen=True)
class SeriesSpec:
    name: str
    label: str
    daily_ret: pd.Series
    carrier_name: str | None = None
    c3_weight_pct: int | None = None
    carrier_weight_pct: int | None = None
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
    return float((nav / nav.cummax() - 1.0).min())


def _ulcer(nav: pd.Series) -> float:
    if nav.empty:
        return 0.0
    drawdown_pct = (nav / nav.cummax() - 1.0) * 100.0
    return float(np.sqrt(np.mean(np.square(np.minimum(drawdown_pct, 0.0)))))


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
    if std <= 0.0:
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
        }
    return {
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
        "positive_day_rate": float((daily_ret > 0.0).mean()),
    }


def _load_c3_daily_ret() -> pd.Series:
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
    df = pd.read_csv(OFFICIAL78_DAILY_PATH)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df[df["date"].notna()].sort_values("date")
    balance = pd.to_numeric(df["balance"], errors="coerce").ffill()
    ret = balance.pct_change()
    ret.iloc[0] = balance.iloc[0] / INITIAL_CAPITAL - 1.0
    ret.index = pd.DatetimeIndex(df["date"])
    return ret.astype(float)


def _load_etf_signal_candidates() -> dict[str, pd.Series]:
    df = pd.read_csv(ETF_SIGNAL_DAILY_PATH)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df[df["date"].notna()].copy()
    result: dict[str, pd.Series] = {}
    for portfolio in ETF_SIGNAL_CANDIDATES:
        sub = df[df["portfolio"].eq(portfolio)].sort_values("date")
        if sub.empty:
            continue
        ret = pd.to_numeric(sub["strategy_daily_ret"], errors="coerce").fillna(0.0)
        ret.index = pd.DatetimeIndex(sub["date"])
        result[f"signal:{portfolio}"] = ret.astype(float)
    return result


def _load_etf_fixed_candidates() -> dict[str, pd.Series]:
    df = pd.read_csv(ETF_FIXED_DAILY_PATH)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df[df["date"].notna()].copy()
    result: dict[str, pd.Series] = {}
    for ts_code, strategy, sleeve_weight, cost_bps in ETF_FIXED_CANDIDATES:
        sub = df[
            df["ts_code"].eq(ts_code)
            & df["strategy"].eq(strategy)
            & np.isclose(pd.to_numeric(df["sleeve_weight"], errors="coerce"), sleeve_weight)
            & np.isclose(pd.to_numeric(df["roundtrip_cost_bps"], errors="coerce"), cost_bps)
        ].sort_values("date")
        if sub.empty:
            continue
        ret = pd.to_numeric(sub["strategy_daily_ret"], errors="coerce").fillna(0.0)
        ret.index = pd.DatetimeIndex(sub["date"])
        name = f"fixed:{ts_code}:{strategy}:sleeve{int(sleeve_weight * 100)}:cost{int(cost_bps)}"
        result[name] = ret.astype(float)
    return result


def _align_returns(returns: dict[str, pd.Series]) -> pd.DataFrame:
    start = max(series.index.min() for series in returns.values())
    end = min(series.index.max() for series in returns.values())
    start = max(start, pd.Timestamp("2020-01-01"))
    index = pd.date_range(start=start, end=end, freq="D")
    aligned = pd.DataFrame(index=index)
    for name, series in returns.items():
        aligned[name] = series.groupby(level=0).sum().reindex(index).fillna(0.0)
    return aligned


def _window_masks(index: pd.DatetimeIndex) -> dict[str, pd.Series]:
    return {
        "full_common": pd.Series(True, index=index),
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


def _short_name(carrier_name: str) -> str:
    clean = (
        carrier_name.replace("signal:", "sig_")
        .replace("fixed:", "fix_")
        .replace("primary_core_liquid_p10_50000", "core")
        .replace("primary_long_all", "longall")
        .replace("connors_rsi2_ma200", "connors")
        .replace("bollinger20_2_ma200", "boll")
        .replace("__", "_")
        .replace(":", "_")
        .replace(".", "")
    )
    return clean[:120]


def _label(carrier_name: str) -> str:
    if carrier_name.startswith("signal:"):
        return carrier_name.replace("signal:", "ETF信号篮子 ")
    return carrier_name.replace("fixed:", "固定指数ETF ")


def _build_series(aligned: pd.DataFrame, carrier_names: list[str]) -> list[SeriesSpec]:
    series: list[SeriesSpec] = [
        SeriesSpec("O_official78_100", "正式78-1 100%", aligned["official78"]),
        SeriesSpec("A_c3_100", "C3 100%", aligned["c3"]),
    ]
    cash_controls_added: set[tuple[int, int]] = set()
    for carrier_name in carrier_names:
        short = _short_name(carrier_name)
        carrier_label = _label(carrier_name)
        series.append(SeriesSpec(f"B_{short}_100", f"{carrier_label} 100%", aligned[carrier_name], carrier_name))
        for c3_weight in COMBO_WEIGHTS:
            carrier_weight = 1.0 - c3_weight
            c3_pct = int(round(c3_weight * 100))
            carrier_pct = int(round(carrier_weight * 100))
            series.append(
                SeriesSpec(
                    f"C_c3_{c3_pct:02d}_etf_{carrier_pct:02d}_{short}",
                    f"C3 {c3_pct}% + {carrier_label} {carrier_pct}%",
                    c3_weight * aligned["c3"] + carrier_weight * aligned[carrier_name],
                    carrier_name=carrier_name,
                    c3_weight_pct=c3_pct,
                    carrier_weight_pct=carrier_pct,
                )
            )
            cash_key = (c3_pct, carrier_pct)
            if cash_key not in cash_controls_added:
                cash_controls_added.add(cash_key)
                series.append(
                    SeriesSpec(
                        f"cash_control_c3_{c3_pct:02d}_cash_{carrier_pct:02d}",
                        f"C3 {c3_pct}% + 现金 {carrier_pct}%",
                        c3_weight * aligned["c3"],
                        c3_weight_pct=c3_pct,
                        cash_weight_pct=carrier_pct,
                    )
                )
    return series


def _build_daily_frame(series: list[SeriesSpec]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for spec in series:
        ret = spec.daily_ret.fillna(0.0).astype(float)
        nav = (1.0 + ret).cumprod()
        frames.append(
            pd.DataFrame(
                {
                    "date": ret.index,
                    "variant": spec.name,
                    "label": spec.label,
                    "carrier_name": spec.carrier_name,
                    "daily_ret": ret.values,
                    "nav": nav.values,
                    "drawdown": (nav / nav.cummax() - 1.0).values,
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def _build_summary(series: list[SeriesSpec]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for spec in series:
        row = _stats(spec.name, spec.label, spec.daily_ret)
        row["carrier_name"] = spec.carrier_name
        row["c3_weight_pct"] = spec.c3_weight_pct
        row["carrier_weight_pct"] = spec.carrier_weight_pct
        row["cash_weight_pct"] = spec.cash_weight_pct
        rows.append(row)
    summary = pd.DataFrame(rows)
    c3_return = _safe_float(summary.loc[summary["variant"].eq("A_c3_100"), "total_return_pct"].iloc[0])
    summary["return_retention_vs_c3_pct"] = summary["total_return_pct"].apply(
        lambda value: _safe_float(value) / c3_return * 100.0 if c3_return else np.nan
    )
    summary.loc[summary["variant"].eq("A_c3_100"), "return_retention_vs_c3_pct"] = 100.0
    return summary


def _build_window_summary(series: list[SeriesSpec], index: pd.DatetimeIndex) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    masks = _window_masks(index)
    for window_name, mask in masks.items():
        window_index = mask[mask].index
        for spec in series:
            ret = spec.daily_ret.loc[window_index]
            if ret.empty:
                continue
            row = _stats(spec.name, spec.label, ret)
            row["window_name"] = window_name
            row["carrier_name"] = spec.carrier_name
            rows.append(row)
    frame = pd.DataFrame(rows)
    for window_name, group in frame.groupby("window_name"):
        c3 = group[group["variant"].eq("A_c3_100")]
        if c3.empty:
            continue
        c3_return = _safe_float(c3["total_return_pct"].iloc[0])
        idx = frame["window_name"].eq(window_name)
        frame.loc[idx, "return_retention_vs_c3_pct"] = frame.loc[idx, "total_return_pct"].apply(
            lambda value: _safe_float(value) / c3_return * 100.0 if c3_return else np.nan
        )
    return frame


def _build_annual_summary(series: list[SeriesSpec]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for spec in series:
        ret = spec.daily_ret.fillna(0.0).astype(float)
        for year, group in ret.groupby(ret.index.year):
            row = _stats(spec.name, spec.label, group)
            row["year"] = int(year)
            row["carrier_name"] = spec.carrier_name
            rows.append(row)
    return pd.DataFrame(rows)


def _decision(summary: pd.DataFrame, window_summary: pd.DataFrame) -> dict[str, Any]:
    c3 = summary[summary["variant"].eq("A_c3_100")].iloc[0].to_dict()
    combo_rows = summary[summary["variant"].str.startswith("C_c3_")].copy()
    cash_rows = summary[summary["variant"].str.startswith("cash_control_")].drop_duplicates("variant")
    cash_map = cash_rows.set_index("variant").to_dict(orient="index")
    decisions: list[dict[str, Any]] = []
    for _, row in combo_rows.iterrows():
        variant = str(row["variant"])
        c3_pct = int(_safe_float(row["c3_weight_pct"]))
        carrier_pct = int(_safe_float(row["carrier_weight_pct"]))
        cash_variant = f"cash_control_c3_{c3_pct:02d}_cash_{carrier_pct:02d}"
        cash_row = cash_map.get(cash_variant, {})
        cash_return = _safe_float(cash_row.get("total_return_pct"), np.nan)
        cash_dd = _safe_float(cash_row.get("max_dd_percent"), np.nan)
        cash_ulcer = _safe_float(cash_row.get("ulcer"), np.nan)
        carrier_name = str(row["carrier_name"])
        carrier_variant = f"B_{_short_name(carrier_name)}_100"
        carrier_row = summary[summary["variant"].eq(carrier_variant)]
        carrier_return = _safe_float(carrier_row["total_return_pct"].iloc[0]) if not carrier_row.empty else np.nan

        fail_windows: list[dict[str, Any]] = []
        for _, win_row in window_summary[window_summary["variant"].eq(variant)].iterrows():
            window_name = str(win_row["window_name"])
            c3_window = window_summary[
                window_summary["window_name"].eq(window_name) & window_summary["variant"].eq("A_c3_100")
            ]
            if c3_window.empty:
                continue
            c3_ret = _safe_float(c3_window["total_return_pct"].iloc[0])
            win_ret = _safe_float(win_row["total_return_pct"])
            win_dd = _safe_float(win_row["max_dd_percent"])
            if win_dd < PASS_MAX_DD:
                fail_windows.append(
                    {
                        "window_name": window_name,
                        "reason": "max_drawdown_below_30",
                        "candidate_return_pct": win_ret,
                        "candidate_max_dd_percent": win_dd,
                        "c3_return_pct": c3_ret,
                    }
                )
            elif c3_ret > 0.0 and win_ret / c3_ret * 100.0 < PASS_RETURN_RETENTION:
                fail_windows.append(
                    {
                        "window_name": window_name,
                        "reason": "positive_window_return_retention_below_80",
                        "candidate_return_pct": win_ret,
                        "candidate_max_dd_percent": win_dd,
                        "c3_return_pct": c3_ret,
                        "return_retention_vs_c3_pct": win_ret / c3_ret * 100.0,
                    }
                )
            elif c3_ret <= 0.0 and win_ret < c3_ret:
                fail_windows.append(
                    {
                        "window_name": window_name,
                        "reason": "negative_window_worse_than_c3",
                        "candidate_return_pct": win_ret,
                        "candidate_max_dd_percent": win_dd,
                        "c3_return_pct": c3_ret,
                    }
                )

        beats_cash_return = _safe_float(row["total_return_pct"]) > cash_return
        beats_cash_dd = _safe_float(row["max_dd_percent"]) >= cash_dd
        beats_cash_ulcer = _safe_float(row["ulcer"]) <= cash_ulcer
        pass_gate = (
            _safe_float(row["max_dd_percent"]) >= PASS_MAX_DD
            and _safe_float(row["return_retention_vs_c3_pct"]) >= PASS_RETURN_RETENTION
            and beats_cash_return
            and beats_cash_dd
            and beats_cash_ulcer
            and carrier_return > 0.0
            and not fail_windows
        )
        decisions.append(
            {
                "variant": variant,
                "carrier_name": carrier_name,
                "c3_weight_pct": c3_pct,
                "carrier_weight_pct": carrier_pct,
                "total_return_pct": _safe_float(row["total_return_pct"]),
                "max_dd_percent": _safe_float(row["max_dd_percent"]),
                "return_retention_vs_c3_pct": _safe_float(row["return_retention_vs_c3_pct"]),
                "sharpe": _safe_float(row["sharpe"]),
                "ulcer": _safe_float(row["ulcer"]),
                "cash_control_total_return_pct": cash_return,
                "cash_control_max_dd_percent": cash_dd,
                "cash_control_ulcer": cash_ulcer,
                "carrier_standalone_total_return_pct": carrier_return,
                "beats_same_weight_cash_return": bool(beats_cash_return),
                "beats_same_weight_cash_dd": bool(beats_cash_dd),
                "beats_same_weight_cash_ulcer": bool(beats_cash_ulcer),
                "fail_window_count": int(len(fail_windows)),
                "fail_windows": fail_windows,
                "pass_gate": bool(pass_gate),
            }
        )
    decision_df = pd.DataFrame(decisions)
    pass_df = decision_df[decision_df["pass_gate"]]
    if pass_df.empty:
        label = "fail_etf_carrier_not_better_than_cash_control"
        best = decision_df.sort_values(
            ["beats_same_weight_cash_return", "beats_same_weight_cash_ulcer", "max_dd_percent", "total_return_pct"],
            ascending=[False, False, False, False],
        ).head(1)
    else:
        label = "candidate_etf_carrier_requires_real_execution_review"
        best = pass_df.sort_values(["ulcer", "return_retention_vs_c3_pct"], ascending=[True, False]).head(1)
    return {
        "decision": label,
        "baseline": c3,
        "best_variant": best.iloc[0].to_dict() if not best.empty else {},
        "predeclared_gates": {
            "max_drawdown_percent_min": PASS_MAX_DD,
            "return_retention_vs_c3_percent_min": PASS_RETURN_RETENTION,
            "must_beat_same_weight_cash_return": True,
            "must_not_worsen_same_weight_cash_drawdown": True,
            "must_not_worsen_same_weight_cash_ulcer": True,
            "standalone_carrier_return_must_be_positive": True,
            "all_windows_must_pass": True,
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
    best_variant = str(decision.get("best_variant", {}).get("variant", ""))
    show_variants = [
        "O_official78_100",
        "A_c3_100",
        best_variant,
    ]
    if best_variant.startswith("C_c3_"):
        c3_pct = int(_safe_float(decision["best_variant"].get("c3_weight_pct")))
        carrier_pct = int(_safe_float(decision["best_variant"].get("carrier_weight_pct")))
        show_variants.append(f"cash_control_c3_{c3_pct:02d}_cash_{carrier_pct:02d}")
    show_variants = [variant for variant in show_variants if variant]
    lines = [
        "# Stage071 ETF/指数类小资金承载组合探针",
        "",
        "## 结论先行",
        "",
        f"- 决策：`{decision['decision']}`。",
        "- 本阶段不修改78-1或C3交易逻辑，只用已有ETF/指数类策略日收益做组合层探针。",
        "- 固定只测 `95%C3+5%ETF` 与 `90%C3+10%ETF`；每个组合必须优于同权重现金稀释，才算有新增价值。",
        "",
        "## 外部调研与判断",
        "",
        "- 趋势跟随/managed futures 研究支持跨市场、跨资产分散可改善组合路径，但收益和回撤改善必须经真实组合检验。",
        "- ETF均值回归或指数类卫星理论上有更小资金承载优势，但本地必须证明它不是现金稀释的替代品。",
        "",
        "## 预声明闸门",
        "",
        "- 全样本最大回撤不低于 `-30%`。",
        "- 全样本收益保留不低于 C3 的 `80%`。",
        "- 同权重下必须同时优于现金对照：收益更高、回撤不更差、Ulcer不更差。",
        "- ETF/指数类独立腿必须为正收益。",
        "- 多起点和弱窗口不能失败。",
        "",
        "## 全样本摘要",
        "",
        summary[top_cols].sort_values("total_return_pct", ascending=False).head(30).to_markdown(
            index=False, floatfmt=".4f"
        ),
        "",
        "## 关键候选与现金对照",
        "",
        summary[summary["variant"].isin(show_variants)][top_cols].to_markdown(index=False, floatfmt=".4f"),
        "",
        "## 多窗口结果",
        "",
        window_summary[window_summary["variant"].isin(show_variants)][
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
        "## 年度结果",
        "",
        annual_summary[annual_summary["variant"].isin(show_variants)][
            ["year", "variant", "total_return_pct", "max_dd_percent", "ulcer", "longest_underwater_days"]
        ].to_markdown(index=False, floatfmt=".4f"),
        "",
        "## 过拟合反思",
        "",
        "- 运行前判断：不是过拟合。ETF候选来自既有独立研究结果和流动性/指数代表性，不按C3结果选。",
        "- 运行后判断：若未通过，不继续扫ETF权重或挑单一指数救援；若通过，也只进入真实执行和OOS复核。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前判断：有价值。Stage070证明2.5万个股腿不可承载，ETF是小资金承载更合理的下一层。",
        "- 运行后判断：以本阶段决策为准；通过则查真实ETF成交/费用，不通过则停止当前ETF小腿。",
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
    best_variant = str(decision.get("best_variant", {}).get("variant", ""))
    show_variants = ["O_official78_100", "A_c3_100", best_variant]
    if best_variant.startswith("C_c3_"):
        c3_pct = int(_safe_float(decision["best_variant"].get("c3_weight_pct")))
        carrier_pct = int(_safe_float(decision["best_variant"].get("carrier_weight_pct")))
        show_variants.append(f"cash_control_c3_{c3_pct:02d}_cash_{carrier_pct:02d}")
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
        title=f"Stage071 ETF/指数类小资金承载组合探针 | 决策: {decision['decision']}",
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
    official78_ret = _load_official78_daily_ret()
    carrier_returns = {}
    carrier_returns.update(_load_etf_signal_candidates())
    carrier_returns.update(_load_etf_fixed_candidates())
    if not carrier_returns:
        raise ValueError("no ETF carrier returns loaded")
    returns = {"c3": c3_ret, "official78": official78_ret, **carrier_returns}
    aligned = _align_returns(returns)
    if aligned.empty:
        raise ValueError("no overlapping return dates")

    carrier_names = list(carrier_returns)
    series = _build_series(aligned, carrier_names)
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
