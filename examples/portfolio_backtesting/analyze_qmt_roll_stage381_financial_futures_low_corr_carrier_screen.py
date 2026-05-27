from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import (
    to_markdown_table,
)


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
CONTRACT_ROOT = PROJECT_DIR / "downloaded_futures" / "tqsdk_daily_2010_2026_04"
MAPPING_PATH = OUTPUT_DIR / "tqsdk_all_futures_main_contract_mapping_2010_2026_04.csv"
C3_DAILY_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage336_c3_cash_reserve_multiperiod_daily_"
    "stage336_c3_cash_reserve_multiperiod_v1.csv"
)

MODEL_TAG = "stage381_financial_futures_low_corr_carrier_screen_v1"
OUTPUT_PREFIX = "qmt_roll_stage381_financial_futures_low_corr_carrier_screen"
LINE_ID = "futures_trend_drawdown30_preserve_return"

START_CAPITAL = 500_000.0
TRADING_DAYS_PER_YEAR = 252.0
COST_BPS = 2.0
TSMOM_HORIZONS = (20, 60, 120)
COMBO_C3_WEIGHTS = (0.80, 0.90, 0.95)
TARGET_MAX_DD_PCT = -30.0
RETURN_RETENTION_GATE_PCT = 80.0

FINANCIAL_PRODUCTS = ("IF", "IC", "IH", "IM", "T", "TF", "TS", "TL")
RATE_PRODUCTS = ("T", "TF", "TS", "TL")
EQUITY_INDEX_PRODUCTS = ("IF", "IC", "IH", "IM")

PRODUCT_DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_daily_{MODEL_TAG}.csv"
PRODUCT_METRICS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_metrics_{MODEL_TAG}.csv"
BASKET_DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_basket_daily_{MODEL_TAG}.csv"
BASKET_METRICS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_basket_metrics_{MODEL_TAG}.csv"
COMBO_WINDOW_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_combo_window_metrics_{MODEL_TAG}.csv"
COMBO_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_combo_summary_{MODEL_TAG}.csv"
COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coverage_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _md_table(df: pd.DataFrame, max_rows: int = 20) -> str:
    if df.empty:
        return ""
    limited = df.head(max_rows).copy()
    return to_markdown_table(limited)


@dataclass(frozen=True)
class Window:
    name: str
    label: str
    start: str
    end: str


WINDOWS: tuple[Window, ...] = (
    Window("full_2020_2026", "2020起点至今", "2020-01-01", "2026-04-30"),
    Window("since_2021", "2021起点至今", "2021-01-01", "2026-04-30"),
    Window("since_2022", "2022起点至今", "2022-01-01", "2026-04-30"),
    Window("since_2023", "2023起点至今", "2023-01-01", "2026-04-30"),
    Window("since_2024", "2024起点至今", "2024-01-01", "2026-04-30"),
    Window("weak_2021_dd", "2021已知回撤窗口", "2021-05-12", "2021-07-02"),
    Window("weak_2022_path", "2022弱路径窗口", "2022-03-09", "2022-12-07"),
    Window("ytd_2026", "2026年初至今", "2026-01-01", "2026-04-30"),
)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


def _to_builtin(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _to_builtin(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_builtin(v) for v in value]
    if isinstance(value, tuple):
        return [_to_builtin(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def _path_metrics_from_returns(returns: pd.Series, start_capital: float = START_CAPITAL) -> dict[str, float]:
    clean = pd.to_numeric(returns, errors="coerce").fillna(0.0).astype(float)
    if clean.empty:
        return {
            "end_balance": start_capital,
            "total_return_pct": 0.0,
            "max_dd_percent": 0.0,
            "sharpe_ratio": 0.0,
            "ulcer_index_pct": 0.0,
            "longest_underwater_days": 0,
        }

    nav = (1.0 + clean).cumprod()
    balance = nav * start_capital
    high = np.maximum.accumulate(balance.to_numpy(dtype=float))
    drawdown_pct = np.divide(
        balance.to_numpy(dtype=float) - high,
        high,
        out=np.zeros(len(balance), dtype=float),
        where=high != 0.0,
    ) * 100.0
    std = float(clean.std(ddof=1)) if len(clean) > 1 else 0.0
    sharpe = float(clean.mean() / std * np.sqrt(TRADING_DAYS_PER_YEAR)) if std > 0.0 else 0.0
    underwater = balance.to_numpy(dtype=float) < high
    longest = 0
    current = 0
    for flag in underwater:
        if flag:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return {
        "end_balance": float(balance.iloc[-1]),
        "total_return_pct": float((nav.iloc[-1] - 1.0) * 100.0),
        "max_dd_percent": float(drawdown_pct.min()) if len(drawdown_pct) else 0.0,
        "sharpe_ratio": sharpe,
        "ulcer_index_pct": float(np.sqrt(np.mean(np.square(drawdown_pct)))) if len(drawdown_pct) else 0.0,
        "longest_underwater_days": int(longest),
    }


def _window_slice(series: pd.Series, window: Window) -> pd.Series:
    start = pd.Timestamp(window.start)
    end = pd.Timestamp(window.end)
    return series[(series.index >= start) & (series.index <= end)].copy()


def _read_c3_returns() -> pd.Series:
    df = pd.read_csv(C3_DAILY_PATH, encoding="utf-8-sig")
    df = df[(df["profile"].eq("c3_active100_cash0")) & (df["window_name"].eq("start_2020"))].copy()
    if df.empty:
        raise RuntimeError("C3 daily curve is empty.")
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df["balance"] = pd.to_numeric(df["balance"], errors="coerce")
    df = df.dropna(subset=["date", "balance"]).sort_values("date").drop_duplicates("date", keep="last")
    returns = df.set_index("date")["balance"].pct_change().fillna(0.0)
    returns.name = "c3_return"
    return returns


def _read_contract_bar(exchange: str, contract_symbol: str) -> pd.DataFrame:
    path = CONTRACT_ROOT / exchange / f"{contract_symbol}.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path, encoding="utf-8-sig")
    if df.empty:
        return pd.DataFrame()
    df["date"] = pd.to_datetime(df["trade_date"], errors="coerce").dt.normalize()
    df["contract_vt_symbol"] = f"{contract_symbol}.{exchange}"
    for col in ("open", "high", "low", "close", "volume", "open_oi", "close_oi"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df[["date", "contract_vt_symbol", "open", "high", "low", "close", "volume", "open_oi", "close_oi"]]


def _build_main_product_series(product: str) -> pd.DataFrame:
    mapping = pd.read_csv(MAPPING_PATH, encoding="utf-8-sig")
    mapping = mapping[(mapping["exchange"].eq("CFFEX")) & (mapping["product"].eq(product))].copy()
    mapping["date"] = pd.to_datetime(mapping["date"], errors="coerce").dt.normalize()
    mapping["main_contract_vt"] = mapping["main_contract_vt"].fillna("").astype(str)
    mapping = mapping[mapping["main_contract_vt"].ne("")].copy()
    if mapping.empty:
        return pd.DataFrame()

    bars: list[pd.DataFrame] = []
    for vt_symbol in sorted(mapping["main_contract_vt"].dropna().unique()):
        contract_symbol, exchange = vt_symbol.split(".", 1)
        bar = _read_contract_bar(exchange, contract_symbol)
        if not bar.empty:
            bars.append(bar)
    if not bars:
        return pd.DataFrame()

    bars_df = pd.concat(bars, ignore_index=True).drop_duplicates(["date", "contract_vt_symbol"], keep="last")
    merged = mapping.merge(
        bars_df,
        left_on=["date", "main_contract_vt"],
        right_on=["date", "contract_vt_symbol"],
        how="left",
    )
    merged = merged.dropna(subset=["date", "close"]).sort_values("date").drop_duplicates("date", keep="last")
    if merged.empty:
        return pd.DataFrame()

    same_contract = merged["main_contract_vt"].eq(merged["main_contract_vt"].shift(1))
    raw_ret = pd.to_numeric(merged["close"], errors="coerce").pct_change()
    merged["product_return"] = raw_ret.where(same_contract, 0.0).fillna(0.0)
    merged["adjusted_nav"] = (1.0 + merged["product_return"]).cumprod()
    merged["product"] = product
    merged["product_vt_symbol"] = f"{product}.CFFEX"
    merged["roll_event"] = (~same_contract).astype(int)
    if not merged.empty:
        merged.loc[merged.index[0], "roll_event"] = 0
    return merged[
        [
            "date",
            "product",
            "product_vt_symbol",
            "main_contract_vt",
            "close",
            "volume",
            "close_oi",
            "product_return",
            "adjusted_nav",
            "roll_event",
        ]
    ].copy()


def _build_product_daily() -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for product in FINANCIAL_PRODUCTS:
        series = _build_main_product_series(product)
        if series.empty:
            continue
        for horizon in TSMOM_HORIZONS:
            part = series.copy()
            momentum = part["adjusted_nav"] / part["adjusted_nav"].shift(horizon) - 1.0
            signal = np.sign(momentum).replace([np.inf, -np.inf], np.nan).fillna(0.0)
            part["horizon_days"] = horizon
            part["position"] = signal.shift(1).fillna(0.0)
            part["turnover"] = part["position"].diff().abs().fillna(part["position"].abs())
            part["cost_return"] = part["turnover"] * COST_BPS / 10_000.0
            part["strategy_return"] = part["position"] * part["product_return"] - part["cost_return"]
            part["strategy_nav"] = (1.0 + part["strategy_return"].fillna(0.0)).cumprod()
            frames.append(part)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    out.sort_values(["product", "horizon_days", "date"], inplace=True)
    return out


def _product_metrics(product_daily: pd.DataFrame, c3_returns: pd.Series) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (product, horizon), group in product_daily.groupby(["product", "horizon_days"], sort=True):
        returns = group.set_index("date")["strategy_return"].sort_index()
        aligned = pd.concat([returns.rename("satellite_return"), c3_returns], axis=1).dropna()
        metrics = _path_metrics_from_returns(returns)
        rows.append(
            {
                "product": product,
                "horizon_days": int(horizon),
                "first_date": returns.index.min().date().isoformat(),
                "last_date": returns.index.max().date().isoformat(),
                "active_days": int((group["position"].abs() > 0).sum()),
                "turnover_sum": float(group["turnover"].sum()),
                "cost_return_sum_pct": float(group["cost_return"].sum() * 100.0),
                "corr_with_c3": float(aligned["satellite_return"].corr(aligned["c3_return"])) if len(aligned) > 3 else np.nan,
                **metrics,
            }
        )
    return pd.DataFrame(rows)


def _basket_components(product_daily: pd.DataFrame, products: tuple[str, ...], horizons: tuple[int, ...]) -> pd.DataFrame:
    sub = product_daily[product_daily["product"].isin(products) & product_daily["horizon_days"].isin(horizons)].copy()
    if sub.empty:
        return pd.DataFrame()
    sub["component"] = sub["product"] + "_h" + sub["horizon_days"].astype(str)
    pivot = sub.pivot_table(index="date", columns="component", values="strategy_return", aggfunc="last").sort_index()
    active = pivot.notna().sum(axis=1)
    returns = pivot.mean(axis=1, skipna=True).fillna(0.0)
    return pd.DataFrame({"date": returns.index, "basket_return": returns.to_numpy(dtype=float), "active_components": active.to_numpy(dtype=int)})


def _build_baskets(product_daily: pd.DataFrame) -> pd.DataFrame:
    basket_defs: tuple[tuple[str, str, tuple[str, ...], tuple[int, ...]], ...] = (
        ("rates_tsmom60", "国债期货60日时间序列动量", RATE_PRODUCTS, (60,)),
        ("rates_tsmom120", "国债期货120日时间序列动量", RATE_PRODUCTS, (120,)),
        ("rates_tsmom20_60_120", "国债期货20/60/120日等权动量", RATE_PRODUCTS, TSMOM_HORIZONS),
        ("equity_index_tsmom60", "股指期货60日时间序列动量", EQUITY_INDEX_PRODUCTS, (60,)),
        ("equity_index_tsmom120", "股指期货120日时间序列动量", EQUITY_INDEX_PRODUCTS, (120,)),
        ("financial_all_tsmom60", "金融期货全篮子60日时间序列动量", FINANCIAL_PRODUCTS, (60,)),
    )
    frames: list[pd.DataFrame] = []
    for basket_name, basket_label, products, horizons in basket_defs:
        basket = _basket_components(product_daily, products, horizons)
        if basket.empty:
            continue
        basket["basket_name"] = basket_name
        basket["basket_label"] = basket_label
        basket["products"] = ",".join(products)
        basket["horizons"] = ",".join(str(item) for item in horizons)
        basket["basket_nav"] = (1.0 + basket["basket_return"]).cumprod()
        frames.append(basket)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    out.sort_values(["basket_name", "date"], inplace=True)
    return out


def _basket_metrics(basket_daily: pd.DataFrame, c3_returns: pd.Series) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for basket_name, group in basket_daily.groupby("basket_name", sort=True):
        group = group.sort_values("date")
        returns = group.set_index("date")["basket_return"]
        aligned = pd.concat([returns.rename("satellite_return"), c3_returns], axis=1).dropna()
        metrics = _path_metrics_from_returns(returns)
        rows.append(
            {
                "basket_name": basket_name,
                "basket_label": str(group["basket_label"].iloc[0]),
                "products": str(group["products"].iloc[0]),
                "horizons": str(group["horizons"].iloc[0]),
                "first_date": returns.index.min().date().isoformat(),
                "last_date": returns.index.max().date().isoformat(),
                "avg_active_components": float(group["active_components"].mean()),
                "corr_with_c3": float(aligned["satellite_return"].corr(aligned["c3_return"])) if len(aligned) > 3 else np.nan,
                **metrics,
            }
        )
    return pd.DataFrame(rows)


def _combo_window_metrics(basket_daily: pd.DataFrame, c3_returns: pd.Series) -> tuple[pd.DataFrame, pd.DataFrame]:
    window_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    for basket_name, group in basket_daily.groupby("basket_name", sort=True):
        returns = group.sort_values("date").set_index("date")["basket_return"]
        for c3_weight in COMBO_C3_WEIGHTS:
            candidate_name = f"c3_{int(c3_weight * 100)}_{basket_name}_{int((1.0 - c3_weight) * 100)}"
            for window in WINDOWS:
                c3_win = _window_slice(c3_returns, window)
                sat_win = _window_slice(returns, window).reindex(c3_win.index).fillna(0.0)
                if c3_win.empty:
                    continue
                combo_ret = c3_weight * c3_win + (1.0 - c3_weight) * sat_win
                cash_ret = c3_weight * c3_win
                c3_metrics = _path_metrics_from_returns(c3_win)
                sat_metrics = _path_metrics_from_returns(sat_win)
                combo_metrics = _path_metrics_from_returns(combo_ret)
                cash_metrics = _path_metrics_from_returns(cash_ret)
                retention = (
                    combo_metrics["total_return_pct"] / c3_metrics["total_return_pct"] * 100.0
                    if c3_metrics["total_return_pct"] > 0.0
                    else 0.0
                )
                cash_retention = (
                    cash_metrics["total_return_pct"] / c3_metrics["total_return_pct"] * 100.0
                    if c3_metrics["total_return_pct"] > 0.0
                    else 0.0
                )
                row = {
                    "candidate": candidate_name,
                    "basket_name": basket_name,
                    "basket_label": str(group["basket_label"].iloc[0]),
                    "c3_weight": c3_weight,
                    "satellite_weight": 1.0 - c3_weight,
                    "window_name": window.name,
                    "window_label": window.label,
                    "start": window.start,
                    "end": window.end,
                    "c3_return_pct": c3_metrics["total_return_pct"],
                    "c3_max_dd_percent": c3_metrics["max_dd_percent"],
                    "satellite_return_pct": sat_metrics["total_return_pct"],
                    "satellite_max_dd_percent": sat_metrics["max_dd_percent"],
                    "combo_return_pct": combo_metrics["total_return_pct"],
                    "combo_max_dd_percent": combo_metrics["max_dd_percent"],
                    "combo_sharpe_ratio": combo_metrics["sharpe_ratio"],
                    "combo_ulcer_index_pct": combo_metrics["ulcer_index_pct"],
                    "cash_return_pct": cash_metrics["total_return_pct"],
                    "cash_max_dd_percent": cash_metrics["max_dd_percent"],
                    "return_retention_vs_c3_pct": retention,
                    "cash_return_retention_vs_c3_pct": cash_retention,
                    "combo_minus_cash_return_pp": combo_metrics["total_return_pct"] - cash_metrics["total_return_pct"],
                    "combo_minus_cash_dd_improvement_pp": combo_metrics["max_dd_percent"] - cash_metrics["max_dd_percent"],
                    "dd30_pass": int(combo_metrics["max_dd_percent"] >= TARGET_MAX_DD_PCT),
                    "retention80_pass": int(retention >= RETURN_RETENTION_GATE_PCT),
                    "beats_cash_return": int(combo_metrics["total_return_pct"] > cash_metrics["total_return_pct"]),
                    "beats_cash_dd": int(combo_metrics["max_dd_percent"] >= cash_metrics["max_dd_percent"]),
                }
                row["objective_pass"] = int(
                    row["dd30_pass"]
                    and row["retention80_pass"]
                    and row["beats_cash_return"]
                    and row["beats_cash_dd"]
                )
                window_rows.append(row)

    window_df = pd.DataFrame(window_rows)
    if window_df.empty:
        return window_df, pd.DataFrame()

    for candidate, group in window_df.groupby("candidate", sort=False):
        full = group[group["window_name"].eq("full_2020_2026")]
        full_row = full.iloc[0] if not full.empty else group.iloc[0]
        positive = group[group["c3_return_pct"] > 0.0]
        summary_rows.append(
            {
                "candidate": candidate,
                "basket_name": str(full_row["basket_name"]),
                "basket_label": str(full_row["basket_label"]),
                "c3_weight": float(full_row["c3_weight"]),
                "satellite_weight": float(full_row["satellite_weight"]),
                "positive_window_count": int(len(positive)),
                "objective_pass_count": int(positive["objective_pass"].sum()),
                "dd30_pass_count": int(positive["dd30_pass"].sum()),
                "retention80_pass_count": int(positive["retention80_pass"].sum()),
                "beats_cash_return_count": int(positive["beats_cash_return"].sum()),
                "beats_cash_dd_count": int(positive["beats_cash_dd"].sum()),
                "min_return_retention_vs_c3_pct": float(positive["return_retention_vs_c3_pct"].min()) if not positive.empty else 0.0,
                "worst_combo_max_dd_percent": float(positive["combo_max_dd_percent"].min()) if not positive.empty else 0.0,
                "full_combo_return_pct": float(full_row["combo_return_pct"]),
                "full_combo_max_dd_percent": float(full_row["combo_max_dd_percent"]),
                "full_combo_sharpe_ratio": float(full_row["combo_sharpe_ratio"]),
                "full_combo_ulcer_index_pct": float(full_row["combo_ulcer_index_pct"]),
                "full_return_retention_vs_c3_pct": float(full_row["return_retention_vs_c3_pct"]),
                "full_combo_minus_cash_return_pp": float(full_row["combo_minus_cash_return_pp"]),
                "full_combo_minus_cash_dd_improvement_pp": float(full_row["combo_minus_cash_dd_improvement_pp"]),
            }
        )
    summary_df = pd.DataFrame(summary_rows)
    if not summary_df.empty:
        summary_df["all_objective_pass"] = (
            summary_df["objective_pass_count"].eq(summary_df["positive_window_count"])
            & summary_df["positive_window_count"].gt(0)
        ).astype(int)
        summary_df = summary_df.sort_values(
            [
                "all_objective_pass",
                "objective_pass_count",
                "full_return_retention_vs_c3_pct",
                "full_combo_minus_cash_return_pp",
                "worst_combo_max_dd_percent",
            ],
            ascending=[False, False, False, False, False],
        )
    return window_df, summary_df


def _coverage(product_daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for product, group in product_daily.groupby("product", sort=True):
        base = group[group["horizon_days"].eq(TSMOM_HORIZONS[0])].copy()
        rows.append(
            {
                "product": product,
                "first_date": base["date"].min().date().isoformat(),
                "last_date": base["date"].max().date().isoformat(),
                "days": int(base["date"].nunique()),
                "contracts": int(base["main_contract_vt"].nunique()),
                "roll_events": int(base["roll_event"].sum()),
                "avg_volume": float(base["volume"].mean()),
                "avg_close_oi": float(base["close_oi"].mean()),
            }
        )
    return pd.DataFrame(rows)


def _decision(product_metrics: pd.DataFrame, basket_metrics: pd.DataFrame, combo_summary: pd.DataFrame) -> dict[str, Any]:
    if combo_summary.empty:
        return {
            "decision": "fail_no_financial_futures_combo_result",
            "line_id": LINE_ID,
            "model_tag": MODEL_TAG,
        }

    full_candidates = combo_summary[
        combo_summary["full_combo_max_dd_percent"].ge(TARGET_MAX_DD_PCT)
        & combo_summary["full_return_retention_vs_c3_pct"].ge(RETURN_RETENTION_GATE_PCT)
        & combo_summary["full_combo_minus_cash_return_pp"].gt(0.0)
        & combo_summary["full_combo_minus_cash_dd_improvement_pp"].ge(0.0)
    ].copy()
    robust_candidates = combo_summary[combo_summary["all_objective_pass"].eq(1)].copy()
    independent_positive_baskets = basket_metrics[basket_metrics["total_return_pct"].gt(0.0)].copy()

    if not robust_candidates.empty:
        decision = "screen_candidate_requires_real_engine_and_margin_audit"
        best = robust_candidates.iloc[0].to_dict()
    elif not full_candidates.empty:
        decision = "partial_full_sample_candidate_requires_multiperiod_rejection_check"
        best = full_candidates.iloc[0].to_dict()
    elif not independent_positive_baskets.empty:
        decision = "diagnostic_only_independent_leg_positive_but_combo_gate_failed"
        best = combo_summary.iloc[0].to_dict()
    else:
        decision = "fail_financial_futures_current_shape_not_better_than_cash"
        best = combo_summary.iloc[0].to_dict()

    return {
        "decision": decision,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "cost_bps": COST_BPS,
        "horizons": list(TSMOM_HORIZONS),
        "combo_c3_weights": list(COMBO_C3_WEIGHTS),
        "product_positive_count": int(product_metrics["total_return_pct"].gt(0.0).sum()) if not product_metrics.empty else 0,
        "basket_positive_count": int(independent_positive_baskets.shape[0]),
        "full_candidate_count": int(full_candidates.shape[0]),
        "robust_candidate_count": int(robust_candidates.shape[0]),
        "best": _to_builtin(best),
    }


def _build_report(
    coverage_df: pd.DataFrame,
    product_metrics: pd.DataFrame,
    basket_metrics: pd.DataFrame,
    combo_summary: pd.DataFrame,
    combo_window: pd.DataFrame,
    decision: dict[str, Any],
) -> str:
    lines: list[str] = [
        "# Stage081 金融期货低相关承载只读筛查",
        "",
        "## 目标",
        "",
        "- 不修改第78-1、C3、AI池、商品品种池、入场或退出逻辑。",
        "- 只检查 CFFEX 金融期货是否可能成为低相关、正收益、可继续真实引擎验证的承载来源。",
        "- 时间序列动量只用预声明 `20/60/120` 三个标准窗口；组合只用 `80/90/95%` C3 粗权重，并与同权重现金稀释比较。",
        "",
        "## 外部调研与判断",
        "",
        "- CTA/managed futures 的常见结构并不局限于商品；债券、利率、股指等金融期货通常是分散风险的重要资产类别。",
        "- 本阶段因此先看金融期货是否提供独立低相关收益源，而不是继续调商品内部阈值。",
        "",
        "## 数据覆盖",
        "",
    ]
    lines.append(_md_table(coverage_df, max_rows=20))
    lines.extend(["", "## 独立品种表现", ""])
    product_cols = [
        "product",
        "horizon_days",
        "total_return_pct",
        "max_dd_percent",
        "sharpe_ratio",
        "corr_with_c3",
        "turnover_sum",
        "cost_return_sum_pct",
    ]
    if product_metrics.empty:
        lines.append("- 无有效独立品种结果。")
    else:
        lines.append(_md_table(product_metrics.sort_values("total_return_pct", ascending=False)[product_cols], max_rows=30))

    lines.extend(["", "## 篮子表现", ""])
    basket_cols = [
        "basket_name",
        "basket_label",
        "total_return_pct",
        "max_dd_percent",
        "sharpe_ratio",
        "ulcer_index_pct",
        "corr_with_c3",
        "avg_active_components",
    ]
    if basket_metrics.empty:
        lines.append("- 无有效篮子结果。")
    else:
        lines.append(_md_table(basket_metrics.sort_values("total_return_pct", ascending=False)[basket_cols], max_rows=20))

    lines.extend(["", "## C3组合筛查", ""])
    summary_cols = [
        "candidate",
        "all_objective_pass",
        "objective_pass_count",
        "positive_window_count",
        "full_combo_return_pct",
        "full_combo_max_dd_percent",
        "full_return_retention_vs_c3_pct",
        "full_combo_minus_cash_return_pp",
        "full_combo_minus_cash_dd_improvement_pp",
        "worst_combo_max_dd_percent",
    ]
    if combo_summary.empty:
        lines.append("- 无有效组合结果。")
    else:
        lines.append(_md_table(combo_summary[summary_cols], max_rows=30))

    lines.extend(["", "## 最优候选窗口明细", ""])
    if not combo_summary.empty and not combo_window.empty:
        best_candidate = str(combo_summary.iloc[0]["candidate"])
        detail = combo_window[combo_window["candidate"].eq(best_candidate)].copy()
        detail_cols = [
            "window_name",
            "combo_return_pct",
            "combo_max_dd_percent",
            "return_retention_vs_c3_pct",
            "cash_return_pct",
            "cash_max_dd_percent",
            "combo_minus_cash_return_pp",
            "combo_minus_cash_dd_improvement_pp",
            "objective_pass",
        ]
        lines.append(_md_table(detail[detail_cols], max_rows=20))
    else:
        lines.append("- 无。")

    lines.extend(
        [
            "",
            "## 判定",
            "",
            f"- 决策：`{decision.get('decision')}`",
            f"- 独立正收益品种数：`{decision.get('product_positive_count')}`",
            f"- 独立正收益篮子数：`{decision.get('basket_positive_count')}`",
            f"- 全样本组合候选数：`{decision.get('full_candidate_count')}`",
            f"- 多窗口稳健候选数：`{decision.get('robust_candidate_count')}`",
            "",
            "## 结论",
            "",
        ]
    )
    if str(decision.get("decision", "")).startswith("screen_candidate"):
        lines.append("- 当前金融期货形状出现多窗口候选，但仍只是净值层/只读筛查，下一步必须做真实合约、保证金、整数手数、滑点和权限约束。")
    elif str(decision.get("decision", "")).startswith("partial"):
        lines.append("- 当前金融期货形状只在全样本层面有候选，尚未证明多窗口稳健，不能晋级。")
    elif str(decision.get("decision", "")).startswith("diagnostic"):
        lines.append("- 当前金融期货独立腿有正收益线索，但组合闸门不通过，只能保留为诊断线索。")
    else:
        lines.append("- 当前金融期货时间序列动量形状没有优于现金稀释，不能作为回撤30以内主路径。")

    lines.extend(
        [
            "",
            "## 过拟合反思",
            "",
            "- 运行前判断：不是过拟合。资产类别、动量窗口、组合权重和现金对照均预先固定，没有按收益挑品种或调小数。",
            "- 运行后判断：是否过拟合取决于后续动作；如果失败后继续调窗口、权重或只挑某个金融品种，就是过拟合。本阶段只读筛查本身不是。",
            "",
            "## 继续价值反思",
            "",
            "- 运行前判断：有价值。现有商品内部路线和供需路线已接近边界，低相关金融期货是合理的新承载来源。",
            "- 运行后判断：以本阶段判定为准；只有出现独立正收益且优于现金稀释的候选，才值得进入真实引擎验证。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    c3_returns = _read_c3_returns()
    product_daily = _build_product_daily()
    if product_daily.empty:
        raise RuntimeError("No product daily data built.")

    product_daily.to_csv(PRODUCT_DAILY_PATH, index=False, encoding="utf-8-sig")
    product_metrics = _product_metrics(product_daily, c3_returns)
    product_metrics.to_csv(PRODUCT_METRICS_PATH, index=False, encoding="utf-8-sig")

    basket_daily = _build_baskets(product_daily)
    basket_daily.to_csv(BASKET_DAILY_PATH, index=False, encoding="utf-8-sig")
    basket_metrics = _basket_metrics(basket_daily, c3_returns)
    basket_metrics.to_csv(BASKET_METRICS_PATH, index=False, encoding="utf-8-sig")

    combo_window, combo_summary = _combo_window_metrics(basket_daily, c3_returns)
    combo_window.to_csv(COMBO_WINDOW_PATH, index=False, encoding="utf-8-sig")
    combo_summary.to_csv(COMBO_SUMMARY_PATH, index=False, encoding="utf-8-sig")

    coverage_df = _coverage(product_daily)
    coverage_df.to_csv(COVERAGE_PATH, index=False, encoding="utf-8-sig")

    decision = _decision(product_metrics, basket_metrics, combo_summary)
    DECISION_PATH.write_text(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2), encoding="utf-8")

    report = _build_report(coverage_df, product_metrics, basket_metrics, combo_summary, combo_window, decision)
    REPORT_PATH.write_text(report, encoding="utf-8")

    print(f"product_daily: {PRODUCT_DAILY_PATH}")
    print(f"product_metrics: {PRODUCT_METRICS_PATH}")
    print(f"basket_daily: {BASKET_DAILY_PATH}")
    print(f"basket_metrics: {BASKET_METRICS_PATH}")
    print(f"combo_window: {COMBO_WINDOW_PATH}")
    print(f"combo_summary: {COMBO_SUMMARY_PATH}")
    print(f"coverage: {COVERAGE_PATH}")
    print(f"decision: {DECISION_PATH}")
    print(f"report: {REPORT_PATH}")
    print(f"decision_label: {decision['decision']}")


if __name__ == "__main__":
    main()
