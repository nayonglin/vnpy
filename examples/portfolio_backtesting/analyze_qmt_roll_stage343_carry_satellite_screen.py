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
from qmt_roll_official_stage78_config import OFFICIAL_STAGE78_ROLE, OFFICIAL_STAGE78_VERSION
from qmt_universe import END_DT, START_DT, VT_SYMBOLS
from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage343_carry_satellite_screen_v1"
OUTPUT_PREFIX = "qmt_roll_stage343_carry_satellite_screen"
LINE_ID = "futures_trend_drawdown30_preserve_return"

RAW_CONTRACT_DIR = Path(__file__).resolve().parent / "downloaded_futures" / "tqsdk_daily_2010_2026_04"
C3_DAILY_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage336_c3_cash_reserve_multiperiod_daily_"
    "stage336_c3_cash_reserve_multiperiod_v1.csv"
)
C3_PROFILE = "c3_active100_cash0"
TOTAL_CAPITAL = 500_000.0

TOP_N = 3
BOTTOM_N = 3
MIN_VALID_PRODUCTS = 8
MIN_DAYS_TO_EXPIRY = 15
MAX_LIQUID_CONTRACTS = 4
COST_BPS_LIST = (0.0, 5.0, 10.0, 20.0)
SATELLITE_WEIGHTS = (0.10, 0.20, 0.30)
TARGET_MAX_DD_PCT = -30.0
RETURN_RETENTION_GATE_PCT = 80.0

FEATURE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_term_structure_features_{MODEL_TAG}.csv"
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
    sharpe = float(np.mean(returns) / std * np.sqrt(252)) if std > 0 else 0.0
    return {
        "end_balance": float(values[-1]),
        "total_return_pct": float((values[-1] / start_capital - 1.0) * 100.0),
        "max_dd_percent": float(dd_pct.min()),
        "sharpe_ratio": sharpe,
    }


def _parse_contract_month(symbol: str, exchange: str) -> pd.Timestamp | None:
    match = re.match(r"([A-Za-z]+)(\d+)$", symbol)
    if not match:
        return None
    digits = match.group(2)
    year: int
    month: int
    if len(digits) == 4:
        yy = int(digits[:2])
        year = 2000 + yy if yy < 70 else 1900 + yy
        month = int(digits[2:])
    elif len(digits) == 3 and exchange == "CZCE":
        year = 2020 + int(digits[:1])
        month = int(digits[1:])
    else:
        return None
    if month < 1 or month > 12:
        return None
    return pd.Timestamp(year=year, month=month, day=1)


def _split_product(product_vt_symbol: str) -> tuple[str, str]:
    product, exchange = product_vt_symbol.split(".", 1)
    return product, exchange


def _contract_path(vt_symbol: str) -> Path:
    symbol, exchange = vt_symbol.split(".", 1)
    return RAW_CONTRACT_DIR / exchange / f"{symbol}.csv"


def _load_contract_panel(products: list[str]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for product_vt in products:
        product, exchange = _split_product(product_vt)
        directory = RAW_CONTRACT_DIR / exchange
        if not directory.exists():
            continue
        for path in sorted(directory.glob(f"{product}*.csv")):
            symbol = path.stem
            expiry_month = _parse_contract_month(symbol, exchange)
            if expiry_month is None:
                continue
            try:
                frame = pd.read_csv(
                    path,
                    usecols=["trade_date", "close", "volume", "close_oi"],
                    encoding="utf-8-sig",
                )
            except ValueError:
                continue
            if frame.empty:
                continue
            frame["date"] = pd.to_datetime(frame["trade_date"]).dt.normalize()
            frame["product_vt_symbol"] = product_vt
            frame["contract_vt_symbol"] = f"{symbol}.{exchange}"
            frame["expiry_month"] = expiry_month
            frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
            frame["volume"] = pd.to_numeric(frame["volume"], errors="coerce").fillna(0.0)
            frame["close_oi"] = pd.to_numeric(frame["close_oi"], errors="coerce").fillna(0.0)
            frame = frame[(frame["date"] >= START_DT) & (frame["date"] <= END_DT)].copy()
            frame = frame[frame["close"] > 0].copy()
            if not frame.empty:
                frames.append(
                    frame[
                        [
                            "date",
                            "product_vt_symbol",
                            "contract_vt_symbol",
                            "expiry_month",
                            "close",
                            "volume",
                            "close_oi",
                        ]
                    ]
                )
    if not frames:
        return pd.DataFrame()
    panel = pd.concat(frames, ignore_index=True)
    panel["days_to_expiry"] = (panel["expiry_month"] - panel["date"]).dt.days
    panel = panel[panel["days_to_expiry"] >= MIN_DAYS_TO_EXPIRY].copy()
    panel["liquidity"] = panel["close_oi"].where(panel["close_oi"] > 0.0, panel["volume"])
    panel = panel[panel["liquidity"] > 0.0].copy()
    return panel.sort_values(["product_vt_symbol", "date", "expiry_month"]).reset_index(drop=True)


def _build_term_structure_features(panel: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if panel.empty:
        return pd.DataFrame()
    for (date, product), group in panel.groupby(["date", "product_vt_symbol"], sort=True):
        liquid = group.sort_values("liquidity", ascending=False).head(MAX_LIQUID_CONTRACTS)
        if len(liquid) < 2:
            continue
        liquid = liquid.sort_values("expiry_month")
        near = liquid.iloc[0]
        far = liquid.iloc[-1]
        if near["contract_vt_symbol"] == far["contract_vt_symbol"]:
            continue
        months_between = max(
            1.0,
            (pd.Timestamp(far["expiry_month"]) - pd.Timestamp(near["expiry_month"])).days / 30.4375,
        )
        near_close = _safe_float(near["close"])
        far_close = _safe_float(far["close"])
        if near_close <= 0.0 or far_close <= 0.0:
            continue
        slope_per_month = math.log(far_close / near_close) / months_between
        rows.append(
            {
                "date": pd.Timestamp(date),
                "product_vt_symbol": product,
                "near_contract": near["contract_vt_symbol"],
                "far_contract": far["contract_vt_symbol"],
                "near_close": near_close,
                "far_close": far_close,
                "near_oi": _safe_float(near["close_oi"]),
                "far_oi": _safe_float(far["close_oi"]),
                "months_between": months_between,
                "slope_per_month": slope_per_month,
                "carry_score": -slope_per_month,
            }
        )
    return pd.DataFrame(rows).sort_values(["date", "product_vt_symbol"]).reset_index(drop=True)


def _load_main_returns(products: list[str], panel: pd.DataFrame) -> pd.DataFrame:
    mapping = load_mapping_df()
    mapping = mapping[mapping["continuous_symbol_vt"].isin(products)].copy()
    mapping["date"] = pd.to_datetime(mapping["date"]).dt.normalize()
    mapping = mapping[(mapping["date"] >= START_DT) & (mapping["date"] <= END_DT)].copy()
    close_lookup = panel[["date", "contract_vt_symbol", "close"]].drop_duplicates(
        ["date", "contract_vt_symbol"],
        keep="last",
    )
    merged = mapping.merge(
        close_lookup,
        left_on=["date", "main_contract_vt"],
        right_on=["date", "contract_vt_symbol"],
        how="left",
    )
    merged = merged[["date", "continuous_symbol_vt", "main_contract_vt", "close"]].rename(
        columns={"continuous_symbol_vt": "product_vt_symbol", "close": "main_close"}
    )
    merged = merged.sort_values(["product_vt_symbol", "date"]).reset_index(drop=True)
    merged["prev_main_close"] = merged.groupby("product_vt_symbol")["main_close"].shift(1)
    merged["prev_main_contract"] = merged.groupby("product_vt_symbol")["main_contract_vt"].shift(1)
    same_contract = merged["main_contract_vt"].eq(merged["prev_main_contract"])
    merged["product_return"] = np.where(
        same_contract & (merged["prev_main_close"] > 0.0),
        merged["main_close"] / merged["prev_main_close"] - 1.0,
        0.0,
    )
    merged["product_return"] = pd.to_numeric(merged["product_return"], errors="coerce").fillna(0.0)
    return merged[["date", "product_vt_symbol", "main_contract_vt", "main_close", "product_return"]]


def _rebalance_targets(feature_slice: pd.DataFrame) -> dict[str, float]:
    clean = feature_slice.dropna(subset=["carry_score"]).copy()
    clean = clean.sort_values("carry_score", ascending=False)
    if len(clean) < MIN_VALID_PRODUCTS:
        return {}
    longs = clean.head(TOP_N)["product_vt_symbol"].tolist()
    shorts = clean.tail(BOTTOM_N)["product_vt_symbol"].tolist()
    symbols = [*longs, *shorts]
    gross_count = len(symbols)
    if gross_count == 0:
        return {}
    unit = 1.0 / gross_count
    targets = {symbol: unit for symbol in longs}
    targets.update({symbol: -unit for symbol in shorts})
    return targets


def _build_satellite_returns(features: pd.DataFrame, product_returns: pd.DataFrame) -> pd.DataFrame:
    if features.empty or product_returns.empty:
        return pd.DataFrame()
    all_dates = sorted(product_returns["date"].drop_duplicates().tolist())
    monthly_targets: dict[pd.Timestamp, dict[str, float]] = {}
    current_month: tuple[int, int] | None = None
    last_targets: dict[str, float] = {}
    for index, raw_date in enumerate(all_dates):
        date = pd.Timestamp(raw_date)
        month_key = (date.year, date.month)
        if month_key != current_month:
            current_month = month_key
            if index == 0:
                last_targets = {}
            else:
                signal_date = pd.Timestamp(all_dates[index - 1])
                signal_slice = features[features["date"].eq(signal_date)]
                targets = _rebalance_targets(signal_slice)
                last_targets = targets if targets else {}
        monthly_targets[date] = dict(last_targets)

    ret_wide = product_returns.pivot_table(
        index="date",
        columns="product_vt_symbol",
        values="product_return",
        aggfunc="last",
    ).fillna(0.0)
    rows: list[dict[str, Any]] = []
    prev_targets: dict[str, float] = {}
    for date in ret_wide.index:
        targets = monthly_targets.get(pd.Timestamp(date), {})
        ret_row = ret_wide.loc[date]
        gross_exposure = float(sum(abs(value) for value in targets.values()))
        gross_return = float(sum(weight * _safe_float(ret_row.get(symbol, 0.0)) for symbol, weight in targets.items()))
        turnover_symbols = set(prev_targets) | set(targets)
        turnover = float(sum(abs(targets.get(symbol, 0.0) - prev_targets.get(symbol, 0.0)) for symbol in turnover_symbols))
        base_row: dict[str, Any] = {
            "date": pd.Timestamp(date),
            "gross_return_before_cost": gross_return,
            "gross_exposure": gross_exposure,
            "turnover": turnover,
            "active_products": int(sum(1 for value in targets.values() if abs(value) > 0.0)),
            "long_products": ",".join(sorted(symbol for symbol, weight in targets.items() if weight > 0.0)),
            "short_products": ",".join(sorted(symbol for symbol, weight in targets.items() if weight < 0.0)),
        }
        for cost_bps in COST_BPS_LIST:
            base_row[f"satellite_return_cost{cost_bps:g}bps"] = gross_return - turnover * cost_bps / 10_000.0
        rows.append(base_row)
        prev_targets = targets
    return pd.DataFrame(rows).sort_values("date").reset_index(drop=True)


def _load_c3_daily() -> pd.DataFrame:
    frame = pd.read_csv(C3_DAILY_PATH, encoding="utf-8-sig")
    frame = frame[frame["profile"].eq(C3_PROFILE) & frame["window_name"].eq("start_2020")].copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    frame["balance"] = pd.to_numeric(frame["balance"], errors="coerce").ffill().fillna(TOTAL_CAPITAL)
    previous_balance = frame["balance"].shift(1).fillna(TOTAL_CAPITAL)
    frame["c3_return"] = frame["balance"] / previous_balance.replace(0.0, np.nan) - 1.0
    frame["c3_return"] = frame["c3_return"].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return frame[["date", "balance", "c3_return", "active_slippage", "trade_count"]].rename(
        columns={"balance": "c3_balance"}
    )


def _build_combo_daily(c3: pd.DataFrame, satellite: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    base = c3.merge(satellite, on="date", how="left").fillna(0.0)
    rows: list[pd.DataFrame] = []
    summary_rows: list[dict[str, Any]] = []
    c3_metrics = _path_metrics(base["c3_balance"], TOTAL_CAPITAL)
    for cost_bps in COST_BPS_LIST:
        sat_col = f"satellite_return_cost{cost_bps:g}bps"
        satellite_balance = TOTAL_CAPITAL * (1.0 + base[sat_col]).cumprod()
        satellite_metrics = _path_metrics(satellite_balance, TOTAL_CAPITAL)
        summary_rows.append(
            {
                "variant": f"carry_satellite_cost{cost_bps:g}bps",
                "satellite_weight": 1.0,
                "cost_bps": cost_bps,
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
            combo_return = c3_weight * base["c3_return"] + satellite_weight * base[sat_col]
            combo_balance = TOTAL_CAPITAL * (1.0 + combo_return).cumprod()
            metrics = _path_metrics(combo_balance, TOTAL_CAPITAL)
            variant = f"c3_{int(c3_weight * 100)}_carry_{int(satellite_weight * 100)}_cost{cost_bps:g}bps"
            daily = pd.DataFrame(
                {
                    "date": base["date"],
                    "variant": variant,
                    "satellite_weight": satellite_weight,
                    "cost_bps": cost_bps,
                    "c3_return": base["c3_return"],
                    "satellite_return": base[sat_col],
                    "combo_return": combo_return,
                    "balance": combo_balance,
                }
            )
            rows.append(daily)
            retention = (
                metrics["total_return_pct"] / c3_metrics["total_return_pct"] * 100.0
                if c3_metrics["total_return_pct"] > 0
                else math.nan
            )
            summary_rows.append(
                {
                    "variant": variant,
                    "satellite_weight": satellite_weight,
                    "cost_bps": cost_bps,
                    "total_return_pct": metrics["total_return_pct"],
                    "return_retention_vs_c3_pct": retention,
                    "max_dd_percent": metrics["max_dd_percent"],
                    "sharpe_ratio": metrics["sharpe_ratio"],
                    "c3_total_return_pct": c3_metrics["total_return_pct"],
                    "c3_max_dd_percent": c3_metrics["max_dd_percent"],
                }
            )
    combo_daily = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    summary = pd.DataFrame(summary_rows)
    return combo_daily, summary


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
            retention = (
                metrics["total_return_pct"] / c3_metrics["total_return_pct"] * 100.0
                if c3_metrics["total_return_pct"] > 0
                else math.nan
            )
            rows.append(
                {
                    "window_name": window.name,
                    "window_label": window.label,
                    "variant": variant,
                    "cost_bps": float(sliced["cost_bps"].iloc[0]),
                    "satellite_weight": float(sliced["satellite_weight"].iloc[0]),
                    "c3_total_return_pct": c3_metrics["total_return_pct"],
                    "c3_max_dd_percent": c3_metrics["max_dd_percent"],
                    "total_return_pct": metrics["total_return_pct"],
                    "return_retention_vs_c3_pct": retention,
                    "max_dd_percent": metrics["max_dd_percent"],
                    "sharpe_ratio": metrics["sharpe_ratio"],
                    "gate_ok": int(
                        metrics["max_dd_percent"] >= TARGET_MAX_DD_PCT
                        and (math.isnan(retention) or retention >= RETURN_RETENTION_GATE_PCT)
                    ),
                }
            )
    return pd.DataFrame(rows)


def _decide(summary: pd.DataFrame, windows: pd.DataFrame) -> dict[str, Any]:
    combo_summary = summary[summary["satellite_weight"] < 1.0].copy()
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
        "decision": "carry_satellite_screen_pass_requires_true_engine" if strict_variants else "carry_satellite_screen_fail",
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
    combo_summary = summary[summary["satellite_weight"] < 1.0].sort_values(
        ["cost_bps", "satellite_weight"],
    )
    best_windows = windows[windows["variant"].isin(decision.get("strict_window_pass_variants", []))]
    if best_windows.empty:
        best_variant = decision.get("best_drawdown_variant", {}).get("variant", "")
        best_windows = windows[windows["variant"].eq(best_variant)].copy()
    active_days = int((satellite["active_products"] > 0).sum()) if not satellite.empty else 0
    avg_turnover = float(satellite["turnover"].mean()) if not satellite.empty else 0.0
    return "\n".join(
        [
            "# Stage043 期限结构Carry低相关卫星净值层筛查",
            "",
            "## 定位",
            "",
            "- 本阶段不修改78-1/C3信号，只做低相关卫星的最小可行筛查。",
            "- 卫星信号：每月用上一交易日逐合约期限结构排序，做多近强远弱的前3个品种，做空近弱远强的后3个品种。",
            "- 这是净值层筛查，不是真实引擎；只有通过后才值得进入真实资金、保证金和整数手数验证。",
            "",
            "## 数据与交易假设",
            "",
            f"- 逐合约期限结构特征数：`{feature_count}`。",
            f"- 卫星活跃交易日：`{active_days}`。",
            f"- 平均日换手：`{avg_turnover:.4f}`。",
            f"- 成本档位：`{', '.join(f'{value:g}bp' for value in COST_BPS_LIST)}`。",
            f"- 组合权重：`{', '.join(f'C3 {int((1.0 - w) * 100)}% + Carry {int(w * 100)}%' for w in SATELLITE_WEIGHTS)}`。",
            "",
            "## 全样本组合结果",
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
                max_rows=80,
            ),
            "",
            "## 关键多周期结果",
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
            "- 若没有多周期严格通过候选，停止该Carry卫星形状；不要调top/bottom数量、月份、成本小数来救结果。",
            "",
            "## 反过拟合与继续价值",
            "",
            "- 运行前：不是过拟合。Carry/期限结构是独立于趋势入场的经济因子，使用月度低换手、固定top/bottom和固定成本档位。",
            "- 运行后：若失败，继续微调横截面数量或月份会过拟合；若通过，也仍只是净值层线索，必须落真实引擎。",
            "- 继续价值：本阶段有价值，因为它检验的是新低相关收益源，而不是继续修补C3内部小阈值。",
        ]
    )


def main() -> None:
    products = sorted(VT_SYMBOLS)
    panel = _load_contract_panel(products)
    features = _build_term_structure_features(panel)
    product_returns = _load_main_returns(products, panel)
    satellite = _build_satellite_returns(features, product_returns)
    c3 = _load_c3_daily()
    combo_daily, summary = _build_combo_daily(c3, satellite)
    windows = _window_metrics(c3, combo_daily)
    decision = _decide(summary, windows)

    FEATURE_PATH.parent.mkdir(parents=True, exist_ok=True)
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
    print(f"[stage343] report={REPORT_PATH}")


if __name__ == "__main__":
    main()
