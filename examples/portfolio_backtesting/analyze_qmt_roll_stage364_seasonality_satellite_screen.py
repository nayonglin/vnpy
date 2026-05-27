from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from analyze_qmt_roll_stage324_true_combo_capital_margin import _to_builtin, _to_markdown_table
from main_contract_mapping import load_mapping_df
from qmt_universe import END_DT, START_DT, VT_SYMBOLS
from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage364_seasonality_satellite_screen_v1"
OUTPUT_PREFIX = "qmt_roll_stage364_seasonality_satellite_screen"
LINE_ID = "futures_trend_drawdown30_preserve_return"

RAW_CONTRACT_DIR = Path(__file__).resolve().parent / "downloaded_futures" / "tqsdk_daily_2010_2026_04"
C3_DAILY_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage336_c3_cash_reserve_multiperiod_daily_"
    "stage336_c3_cash_reserve_multiperiod_v1.csv"
)
C3_PROFILE = "c3_active100_cash0"
TOTAL_CAPITAL = 500_000.0

HISTORY_START_DT = datetime(2015, 1, 1)
LOOKBACK_YEARS = 5
MIN_HISTORY_YEARS = 3
TOP_N = 3
BOTTOM_N = 3
MIN_VALID_PRODUCTS = 8
COST_BPS = 20.0
SATELLITE_WEIGHTS = (0.10, 0.20, 0.30)
TARGET_MAX_DD_PCT = -30.0
RETURN_RETENTION_GATE_PCT = 80.0

PRODUCT_RETURN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_returns_{MODEL_TAG}.csv"
FEATURE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_features_{MODEL_TAG}.csv"
SATELLITE_DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_satellite_daily_{MODEL_TAG}.csv"
COMBO_DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_combo_daily_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
WINDOW_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


@dataclass(frozen=True)
class Window:
    name: str
    label: str
    start: datetime
    end: datetime


WINDOWS: tuple[Window, ...] = (
    Window("full_2020_2026", "2020起点至今", START_DT, END_DT),
    Window("since_2021", "2021起点至今", datetime(2021, 1, 1), END_DT),
    Window("since_2022", "2022起点至今", datetime(2022, 1, 1), END_DT),
    Window("since_2023", "2023起点至今", datetime(2023, 1, 1), END_DT),
    Window("since_2024", "2024起点至今", datetime(2024, 1, 1), END_DT),
    Window("phase_2024_2025", "2024-2025独立启动", datetime(2024, 1, 1), datetime(2025, 12, 31)),
    Window("ytd_2026", "2026年初至今", datetime(2026, 1, 1), END_DT),
)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or math.isinf(result):
        return default
    return result


def _path_metrics(balance: pd.Series, start_capital: float) -> dict[str, float]:
    values = pd.to_numeric(balance, errors="coerce").ffill().fillna(start_capital).to_numpy(dtype=float)
    if len(values) == 0:
        return {
            "end_balance": start_capital,
            "total_return_pct": 0.0,
            "max_dd_percent": 0.0,
            "sharpe_ratio": 0.0,
        }
    high = np.maximum.accumulate(values)
    drawdown = values - high
    dd_pct = np.divide(drawdown, high, out=np.zeros_like(drawdown), where=high != 0.0) * 100.0
    returns = pd.Series(values).pct_change().fillna(0.0).to_numpy(dtype=float)
    std = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.0
    sharpe = float(np.mean(returns) / std * np.sqrt(252.0)) if std > 0 else 0.0
    return {
        "end_balance": float(values[-1]),
        "total_return_pct": float((values[-1] / start_capital - 1.0) * 100.0),
        "max_dd_percent": float(dd_pct.min()),
        "sharpe_ratio": sharpe,
    }


def _weight_label(weight: float) -> str:
    return f"{weight * 100:g}".replace(".", "p")


def _contract_path(vt_symbol: str) -> Path:
    symbol, exchange = vt_symbol.split(".", 1)
    return RAW_CONTRACT_DIR / exchange / f"{symbol}.csv"


def _load_contract_closes(vt_symbols: list[str]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for vt_symbol in sorted(vt_symbols):
        path = _contract_path(vt_symbol)
        if not path.exists():
            continue
        try:
            frame = pd.read_csv(path, usecols=["trade_date", "close"], encoding="utf-8-sig")
        except ValueError:
            continue
        if frame.empty:
            continue
        frame["date"] = pd.to_datetime(frame["trade_date"]).dt.normalize()
        frame["contract_vt_symbol"] = vt_symbol
        frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
        frame = frame[
            (frame["date"] >= pd.Timestamp(HISTORY_START_DT))
            & (frame["date"] <= pd.Timestamp(END_DT))
            & (frame["close"] > 0)
        ].copy()
        if not frame.empty:
            frames.append(frame[["date", "contract_vt_symbol", "close"]])
    if not frames:
        return pd.DataFrame(columns=["date", "contract_vt_symbol", "close"])
    return pd.concat(frames, ignore_index=True).drop_duplicates(["date", "contract_vt_symbol"], keep="last")


def _load_main_product_returns(products: list[str]) -> pd.DataFrame:
    mapping = load_mapping_df()
    mapping["date"] = pd.to_datetime(mapping["date"]).dt.normalize()
    mapping = mapping[mapping["continuous_symbol_vt"].isin(products)].copy()
    mapping = mapping[(mapping["date"] >= HISTORY_START_DT) & (mapping["date"] <= END_DT)].copy()
    mapping = mapping[mapping["main_contract_vt"].astype(str).ne("")].copy()
    contract_symbols = sorted(mapping["main_contract_vt"].dropna().astype(str).unique().tolist())
    closes = _load_contract_closes(contract_symbols)
    merged = mapping.merge(
        closes,
        left_on=["date", "main_contract_vt"],
        right_on=["date", "contract_vt_symbol"],
        how="left",
    )
    merged = merged[["date", "continuous_symbol_vt", "main_contract_vt", "close"]].rename(
        columns={"continuous_symbol_vt": "product_vt_symbol", "close": "main_close"}
    )
    merged = merged.sort_values(["product_vt_symbol", "date"]).reset_index(drop=True)
    merged["prev_close"] = merged.groupby("product_vt_symbol")["main_close"].shift(1)
    merged["prev_contract"] = merged.groupby("product_vt_symbol")["main_contract_vt"].shift(1)
    same_contract = merged["main_contract_vt"].eq(merged["prev_contract"])
    merged["product_return"] = np.where(
        same_contract & (merged["prev_close"] > 0.0),
        merged["main_close"] / merged["prev_close"] - 1.0,
        0.0,
    )
    merged["product_return"] = pd.to_numeric(merged["product_return"], errors="coerce").fillna(0.0)
    return merged[["date", "product_vt_symbol", "main_contract_vt", "main_close", "product_return"]]


def _build_monthly_returns(product_returns: pd.DataFrame) -> pd.DataFrame:
    frame = product_returns.copy()
    frame["year"] = frame["date"].dt.year
    frame["month"] = frame["date"].dt.month
    rows: list[dict[str, Any]] = []
    for (product, year, month), group in frame.groupby(["product_vt_symbol", "year", "month"], sort=True):
        returns = pd.to_numeric(group["product_return"], errors="coerce").fillna(0.0)
        rows.append(
            {
                "product_vt_symbol": product,
                "year": int(year),
                "month": int(month),
                "monthly_return": float((1.0 + returns).prod() - 1.0),
                "trading_days": int(len(returns)),
            }
        )
    return pd.DataFrame(rows).sort_values(["product_vt_symbol", "year", "month"]).reset_index(drop=True)


def _build_seasonality_features(product_returns: pd.DataFrame) -> pd.DataFrame:
    if product_returns.empty:
        return pd.DataFrame()
    monthly = _build_monthly_returns(product_returns)
    trade_dates = (
        product_returns[product_returns["date"].between(pd.Timestamp(START_DT), pd.Timestamp(END_DT))]["date"]
        .drop_duplicates()
        .sort_values()
        .tolist()
    )
    first_dates = pd.Series(trade_dates).groupby([pd.Series(trade_dates).dt.year, pd.Series(trade_dates).dt.month]).min()
    rows: list[dict[str, Any]] = []
    for signal_date in first_dates.tolist():
        signal_date = pd.Timestamp(signal_date)
        current_year = int(signal_date.year)
        current_month = int(signal_date.month)
        history = monthly[
            (monthly["month"].eq(current_month))
            & (monthly["year"] < current_year)
            & (monthly["year"] >= current_year - LOOKBACK_YEARS)
        ].copy()
        if history.empty:
            continue
        grouped = history.groupby("product_vt_symbol", sort=True)
        scored = grouped.agg(
            seasonality_score=("monthly_return", "mean"),
            seasonality_std=("monthly_return", "std"),
            positive_rate=("monthly_return", lambda values: float((pd.Series(values) > 0).mean())),
            history_years=("year", "nunique"),
        ).reset_index()
        scored = scored[scored["history_years"] >= MIN_HISTORY_YEARS].copy()
        if len(scored) < MIN_VALID_PRODUCTS:
            continue
        for row in scored.itertuples(index=False):
            rows.append(
                {
                    "signal_date": signal_date,
                    "effective_year": current_year,
                    "effective_month": current_month,
                    "product_vt_symbol": row.product_vt_symbol,
                    "seasonality_score": float(row.seasonality_score),
                    "seasonality_std": _safe_float(row.seasonality_std),
                    "positive_rate": float(row.positive_rate),
                    "history_years": int(row.history_years),
                }
            )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(["signal_date", "product_vt_symbol"]).reset_index(drop=True)


def _rebalance_targets(feature_slice: pd.DataFrame) -> dict[str, float]:
    clean = feature_slice.dropna(subset=["seasonality_score"]).copy()
    clean = clean.sort_values("seasonality_score", ascending=False)
    if len(clean) < MIN_VALID_PRODUCTS:
        return {}
    longs = clean.head(TOP_N)["product_vt_symbol"].tolist()
    shorts = clean.tail(BOTTOM_N)["product_vt_symbol"].tolist()
    symbols = [*longs, *shorts]
    if not symbols:
        return {}
    unit = 1.0 / len(symbols)
    targets = {symbol: unit for symbol in longs}
    targets.update({symbol: -unit for symbol in shorts})
    return targets


def _build_satellite_returns(features: pd.DataFrame, product_returns: pd.DataFrame) -> pd.DataFrame:
    if features.empty or product_returns.empty:
        return pd.DataFrame()
    all_dates = sorted(
        product_returns[product_returns["date"].between(pd.Timestamp(START_DT), pd.Timestamp(END_DT))]["date"]
        .drop_duplicates()
        .tolist()
    )
    ret_wide = product_returns.pivot_table(
        index="date",
        columns="product_vt_symbol",
        values="product_return",
        aggfunc="last",
    ).fillna(0.0)
    feature_by_signal = {pd.Timestamp(date): group.copy() for date, group in features.groupby("signal_date", sort=True)}
    current_targets: dict[str, float] = {}
    previous_targets: dict[str, float] = {}
    rows: list[dict[str, Any]] = []
    for raw_date in all_dates:
        date = pd.Timestamp(raw_date)
        next_targets = current_targets
        is_rebalance = date in feature_by_signal
        if is_rebalance:
            next_targets = _rebalance_targets(feature_by_signal[date])
        ret_row = ret_wide.loc[date] if date in ret_wide.index else pd.Series(dtype=float)
        gross_return = float(
            sum(weight * _safe_float(ret_row.get(symbol, 0.0)) for symbol, weight in current_targets.items())
        )
        turnover = 0.0
        if is_rebalance:
            turnover_symbols = set(previous_targets) | set(next_targets)
            turnover = float(
                sum(abs(next_targets.get(symbol, 0.0) - previous_targets.get(symbol, 0.0)) for symbol in turnover_symbols)
            )
            current_targets = dict(next_targets)
            previous_targets = dict(next_targets)
        satellite_return = gross_return - turnover * COST_BPS / 10_000.0
        rows.append(
            {
                "date": date,
                "satellite_return": satellite_return,
                "gross_return_before_cost": gross_return,
                "turnover": turnover,
                "cost_bps": COST_BPS,
                "gross_exposure": float(sum(abs(value) for value in current_targets.values())),
                "active_products": int(sum(1 for value in current_targets.values() if abs(value) > 0.0)),
                "long_products": ",".join(sorted(symbol for symbol, weight in current_targets.items() if weight > 0.0)),
                "short_products": ",".join(sorted(symbol for symbol, weight in current_targets.items() if weight < 0.0)),
                "is_rebalance": int(is_rebalance),
            }
        )
    return pd.DataFrame(rows).sort_values("date").reset_index(drop=True)


def _load_c3_daily() -> pd.DataFrame:
    frame = pd.read_csv(C3_DAILY_PATH, encoding="utf-8-sig")
    frame = frame[frame["profile"].eq(C3_PROFILE) & frame["window_name"].eq("start_2020")].copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    frame["balance"] = pd.to_numeric(frame["balance"], errors="coerce").ffill().fillna(TOTAL_CAPITAL)
    previous_balance = frame["balance"].shift(1).fillna(TOTAL_CAPITAL).replace(0.0, np.nan)
    frame["c3_return"] = frame["balance"] / previous_balance - 1.0
    frame["c3_return"] = frame["c3_return"].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return frame[["date", "balance", "c3_return", "active_slippage", "trade_count"]].rename(
        columns={"balance": "c3_balance"}
    )


def _build_combo_daily(c3: pd.DataFrame, satellite: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[pd.DataFrame] = []
    summary_rows: list[dict[str, Any]] = []
    c3_metrics = _path_metrics(c3["c3_balance"], TOTAL_CAPITAL)
    base = c3.merge(satellite, on="date", how="left").fillna(0.0)
    satellite_balance = TOTAL_CAPITAL * (1.0 + base["satellite_return"]).cumprod()
    satellite_metrics = _path_metrics(satellite_balance, TOTAL_CAPITAL)
    summary_rows.append(
        {
            "variant": "B_seasonality_top3_bottom3_cost20bps",
            "arm": "B",
            "satellite_weight": 1.0,
            "total_return_pct": satellite_metrics["total_return_pct"],
            "return_retention_vs_c3_pct": math.nan,
            "max_dd_percent": satellite_metrics["max_dd_percent"],
            "sharpe_ratio": satellite_metrics["sharpe_ratio"],
            "c3_total_return_pct": c3_metrics["total_return_pct"],
            "c3_max_dd_percent": c3_metrics["max_dd_percent"],
        }
    )
    for satellite_weight in SATELLITE_WEIGHTS:
        c3_weight = 1.0 - satellite_weight
        combo_return = c3_weight * base["c3_return"] + satellite_weight * base["satellite_return"]
        combo_balance = TOTAL_CAPITAL * (1.0 + combo_return).cumprod()
        metrics = _path_metrics(combo_balance, TOTAL_CAPITAL)
        c3_label = _weight_label(c3_weight)
        satellite_label = _weight_label(satellite_weight)
        variant = f"C_c3_{c3_label}_seasonality_{satellite_label}_cost20bps"
        rows.append(
            pd.DataFrame(
                {
                    "date": base["date"],
                    "variant": variant,
                    "arm": "C",
                    "satellite_weight": satellite_weight,
                    "c3_return": base["c3_return"],
                    "satellite_return": base["satellite_return"],
                    "combo_return": combo_return,
                    "balance": combo_balance,
                }
            )
        )
        retention = (
            metrics["total_return_pct"] / c3_metrics["total_return_pct"] * 100.0
            if c3_metrics["total_return_pct"] > 0
            else math.nan
        )
        summary_rows.append(
            {
                "variant": variant,
                "arm": "C",
                "satellite_weight": satellite_weight,
                "total_return_pct": metrics["total_return_pct"],
                "return_retention_vs_c3_pct": retention,
                "max_dd_percent": metrics["max_dd_percent"],
                "sharpe_ratio": metrics["sharpe_ratio"],
                "c3_total_return_pct": c3_metrics["total_return_pct"],
                "c3_max_dd_percent": c3_metrics["max_dd_percent"],
            }
        )
    combo_daily = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    return combo_daily, pd.DataFrame(summary_rows)


def _gate(c3_return: float, candidate_return: float, candidate_dd: float) -> tuple[int, float]:
    if c3_return > 0:
        retention = candidate_return / c3_return * 100.0
        return int(candidate_dd >= TARGET_MAX_DD_PCT and retention >= RETURN_RETENTION_GATE_PCT), retention
    return int(candidate_dd >= TARGET_MAX_DD_PCT and candidate_return >= c3_return), math.nan


def _window_metrics(c3: pd.DataFrame, combo_daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for window in WINDOWS:
        c3_slice = c3[(c3["date"] >= window.start) & (c3["date"] <= window.end)].copy()
        if c3_slice.empty:
            continue
        c3_balance = TOTAL_CAPITAL * (1.0 + c3_slice["c3_return"]).cumprod()
        c3_metrics = _path_metrics(c3_balance, TOTAL_CAPITAL)
        for variant, group in combo_daily.groupby("variant", sort=False):
            sliced = group[(group["date"] >= window.start) & (group["date"] <= window.end)].copy()
            if sliced.empty:
                continue
            balance = TOTAL_CAPITAL * (1.0 + sliced["combo_return"]).cumprod()
            metrics = _path_metrics(balance, TOTAL_CAPITAL)
            gate_ok, retention = _gate(c3_metrics["total_return_pct"], metrics["total_return_pct"], metrics["max_dd_percent"])
            rows.append(
                {
                    "window_name": window.name,
                    "window_label": window.label,
                    "variant": variant,
                    "satellite_weight": float(sliced["satellite_weight"].iloc[0]),
                    "c3_total_return_pct": c3_metrics["total_return_pct"],
                    "c3_max_dd_percent": c3_metrics["max_dd_percent"],
                    "total_return_pct": metrics["total_return_pct"],
                    "return_retention_vs_c3_pct": retention,
                    "max_dd_percent": metrics["max_dd_percent"],
                    "sharpe_ratio": metrics["sharpe_ratio"],
                    "gate_ok": gate_ok,
                }
            )
    return pd.DataFrame(rows)


def _decide(summary: pd.DataFrame, windows: pd.DataFrame) -> dict[str, Any]:
    combo_summary = summary[summary["arm"].eq("C")].copy()
    if combo_summary.empty or windows.empty:
        return {"decision": "no_candidate", "reason": "empty_summary"}
    full_pass = combo_summary[
        (combo_summary["max_dd_percent"] >= TARGET_MAX_DD_PCT)
        & (combo_summary["return_retention_vs_c3_pct"] >= RETURN_RETENTION_GATE_PCT)
    ].copy()
    strict_variants: list[str] = []
    for variant, group in windows.groupby("variant", sort=True):
        if int(group["gate_ok"].min()) == 1:
            strict_variants.append(variant)
    best_retention = combo_summary.sort_values(
        ["return_retention_vs_c3_pct", "max_dd_percent"],
        ascending=[False, False],
    ).head(1)
    best_dd = combo_summary.sort_values(
        ["max_dd_percent", "return_retention_vs_c3_pct"],
        ascending=[False, False],
    ).head(1)
    return {
        "decision": "seasonality_netvalue_candidate_requires_true_engine" if strict_variants else "seasonality_satellite_screen_fail",
        "full_pass_variants": full_pass["variant"].tolist(),
        "strict_window_pass_variants": strict_variants,
        "best_retention_variant": best_retention.to_dict(orient="records")[0] if not best_retention.empty else {},
        "best_drawdown_variant": best_dd.to_dict(orient="records")[0] if not best_dd.empty else {},
    }


def _build_report(
    summary: pd.DataFrame,
    windows: pd.DataFrame,
    decision: dict[str, Any],
    feature_count: int,
    satellite: pd.DataFrame,
) -> str:
    combo_summary = summary[summary["arm"].eq("C")].sort_values("satellite_weight")
    standalone = summary[summary["arm"].eq("B")].copy()
    best_variant = decision.get("best_drawdown_variant", {}).get("variant", "")
    best_windows = windows[windows["variant"].eq(best_variant)].copy()
    active_days = int((satellite["active_products"] > 0).sum()) if not satellite.empty else 0
    avg_turnover = float(satellite["turnover"].mean()) if not satellite.empty else 0.0
    rebalance_count = int(satellite["is_rebalance"].sum()) if not satellite.empty else 0
    return "\n".join(
        [
            "# Stage064 商品季节性卫星净值层筛查",
            "",
            "## 定位",
            "",
            "- A：C3当前底座，不修改78-1核心alpha、AI池、入场和供需过滤。",
            "- B：商品季节性卫星，使用历史同月收益排序，做多前3、做空后3。",
            "- C：C3叠加季节性卫星，只测 `10%/20%/30%` 粗权重。",
            "- 本阶段是净值层方向筛查；即使通过，也必须再进入真实资金、保证金和整数手数验证。",
            "",
            "## 点时化约束",
            "",
            f"- 历史窗口：`{HISTORY_START_DT:%Y-%m-%d}` 至 `{END_DT:%Y-%m-%d}`。",
            f"- 每月信号只用当前年份之前最近 `{LOOKBACK_YEARS}` 个同月样本。",
            f"- 单品种至少需要 `{MIN_HISTORY_YEARS}` 个历史年份。",
            "- 月初第一天不吃新信号当日收益，避免时序乐观。",
            "",
            "## 数据与交易假设",
            "",
            f"- 季节性特征数：`{feature_count}`。",
            f"- 卫星活跃天数：`{active_days}`。",
            f"- 调仓次数：`{rebalance_count}`。",
            f"- 平均日换手：`{avg_turnover:.4f}`。",
            f"- 成本：`{COST_BPS:g}bp * 换手`。",
            "",
            "## B：卫星独立结果",
            "",
            _to_markdown_table(
                standalone,
                [
                    "variant",
                    "total_return_pct",
                    "max_dd_percent",
                    "sharpe_ratio",
                ],
                max_rows=20,
            ),
            "",
            "## C：C3组合全样本结果",
            "",
            _to_markdown_table(
                combo_summary,
                [
                    "variant",
                    "total_return_pct",
                    "return_retention_vs_c3_pct",
                    "max_dd_percent",
                    "sharpe_ratio",
                ],
                max_rows=30,
            ),
            "",
            "## 最低回撤组合多周期",
            "",
            _to_markdown_table(
                best_windows,
                [
                    "window_name",
                    "variant",
                    "c3_total_return_pct",
                    "total_return_pct",
                    "return_retention_vs_c3_pct",
                    "c3_max_dd_percent",
                    "max_dd_percent",
                    "gate_ok",
                ],
                max_rows=80,
            ),
            "",
            "## 决策",
            "",
            f"- 决策标签：`{decision.get('decision')}`。",
            f"- 全样本通过候选：`{decision.get('full_pass_variants')}`。",
            f"- 多周期严格通过候选：`{decision.get('strict_window_pass_variants')}`。",
            "- 若没有多周期严格通过候选，停止当前季节性卫星形状；不要事后挑月份、品种或继续调权重小数。",
        ]
    )


def main() -> None:
    products = sorted(VT_SYMBOLS)
    product_returns = _load_main_product_returns(products)
    features = _build_seasonality_features(product_returns)
    satellite = _build_satellite_returns(features, product_returns)
    c3 = _load_c3_daily()
    combo_daily, summary = _build_combo_daily(c3, satellite)
    windows = _window_metrics(c3, combo_daily)
    decision = _decide(summary, windows)

    PRODUCT_RETURN_PATH.parent.mkdir(parents=True, exist_ok=True)
    product_returns.to_csv(PRODUCT_RETURN_PATH, index=False, encoding="utf-8-sig")
    features.to_csv(FEATURE_PATH, index=False, encoding="utf-8-sig")
    satellite.to_csv(SATELLITE_DAILY_PATH, index=False, encoding="utf-8-sig")
    combo_daily.to_csv(COMBO_DAILY_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    windows.to_csv(WINDOW_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(
        _build_report(summary, windows, decision, len(features), satellite),
        encoding="utf-8",
    )

    print(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2))
    print(f"[stage364] report={REPORT_PATH}")


if __name__ == "__main__":
    main()
