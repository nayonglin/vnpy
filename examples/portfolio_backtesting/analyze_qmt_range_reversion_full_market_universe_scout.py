from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from qmt_universe import VT_SYMBOLS


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"
DAILY_ROOT: Path = PROJECT_DIR / "downloaded_futures" / "tqsdk_daily_2010_2026_04"
MAPPING_PATH: Path = OUTPUT_DIR / "tqsdk_all_futures_main_contract_mapping_2010_2026_04.csv"
PRODUCTS_PATH: Path = OUTPUT_DIR / "tqsdk_all_futures_products_2010_2026_04.csv"

MODEL_TAG: str = "range_reversion_full_market_universe_scout_v1"
PRODUCT_DIRECTION_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_full_market_universe_scout_product_direction_{MODEL_TAG}.csv"
TOP_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_full_market_universe_scout_top_candidates_{MODEL_TAG}.csv"
YEAR_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_full_market_universe_scout_year_direction_{MODEL_TAG}.csv"
SUMMARY_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_full_market_universe_scout_summary_{MODEL_TAG}.json"
REPORT_OUTPUT_PATH: Path = OUTPUT_DIR / f"qmt_range_reversion_full_market_universe_scout_report_{MODEL_TAG}.md"

ANALYSIS_START: pd.Timestamp = pd.Timestamp("2020-01-01")
ANALYSIS_END: pd.Timestamp = pd.Timestamp("2026-04-30")
MIN_BARS: int = 500
MIN_DIRECTION_SIGNALS: int = 20
MIN_YEARS: int = 3

CHANNEL_WINDOW: int = 20
RSI_WINDOW: int = 14
ADX_WINDOW: int = 14
EFFICIENCY_WINDOW: int = 20
ATR_WINDOW: int = 20

RANGE_SOFT_ADX_MAX: float = 32.0
RANGE_EFFICIENCY_MAX: float = 0.40
SHORT_RANGE_POSITION_MIN: float = 0.65
LONG_RANGE_POSITION_MAX: float = 0.35
SHORT_RSI_MIN: float = 55.0
SHORT_RSI_MAX: float = 75.0
LONG_RSI_MIN: float = 25.0
LONG_RSI_MAX: float = 45.0


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or math.isinf(result):
        return default
    return result


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, **kwargs)


def _split_vt_symbol(vt_symbol: str) -> tuple[str, str]:
    symbol, exchange = str(vt_symbol).split(".", 1)
    return symbol, exchange


def _contract_csv_path(vt_symbol: str) -> Path:
    symbol, exchange = _split_vt_symbol(vt_symbol)
    return DAILY_ROOT / exchange / f"{symbol}.csv"


def _load_contract_bars(vt_symbol: str) -> pd.DataFrame:
    path = _contract_csv_path(vt_symbol)
    if not path.exists():
        return pd.DataFrame(columns=["date", "main_contract_vt", "open", "high", "low", "close", "volume"])

    df = _read_csv(path, encoding="utf-8-sig")
    if df.empty or "trade_date" not in df.columns:
        return pd.DataFrame(columns=["date", "main_contract_vt", "open", "high", "low", "close", "volume"])

    df = df.rename(columns={"trade_date": "date"}).copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    df = df[(df["date"] >= ANALYSIS_START) & (df["date"] <= ANALYSIS_END)].copy()
    if df.empty:
        return pd.DataFrame(columns=["date", "main_contract_vt", "open", "high", "low", "close", "volume"])

    for column in ("open", "high", "low", "close", "volume"):
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df["main_contract_vt"] = vt_symbol
    return df[["date", "main_contract_vt", "open", "high", "low", "close", "volume"]].dropna(subset=["date"])


def _load_mapping() -> pd.DataFrame:
    mapping = _read_csv(MAPPING_PATH, encoding="utf-8-sig")
    mapping["date"] = pd.to_datetime(mapping["date"], errors="coerce").dt.normalize()
    mapping["continuous_symbol_vt"] = mapping["continuous_symbol_vt"].fillna("").astype(str)
    mapping["main_contract_vt"] = mapping["main_contract_vt"].fillna("").astype(str)
    mapping = mapping[(mapping["date"] >= ANALYSIS_START) & (mapping["date"] <= ANALYSIS_END)].copy()
    mapping = mapping[mapping["main_contract_vt"] != ""].copy()
    return mapping


def _load_products() -> pd.DataFrame:
    products = _read_csv(PRODUCTS_PATH, encoding="utf-8-sig")
    products["product_vt"] = products["product_vt"].astype(str)
    return products


def _build_product_series(
    product_vt: str,
    mapping: pd.DataFrame,
    contract_cache: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    product_mapping = mapping[mapping["continuous_symbol_vt"] == product_vt].copy()
    if product_mapping.empty:
        return pd.DataFrame()

    contracts = sorted(product_mapping["main_contract_vt"].dropna().astype(str).unique())
    frames: list[pd.DataFrame] = []
    for vt_symbol in contracts:
        if vt_symbol not in contract_cache:
            contract_cache[vt_symbol] = _load_contract_bars(vt_symbol)
        bars = contract_cache[vt_symbol]
        if not bars.empty:
            frames.append(bars)
    if not frames:
        return pd.DataFrame()

    bar_df = pd.concat(frames, ignore_index=True)
    merged = product_mapping[["date", "continuous_symbol_vt", "main_contract_vt"]].merge(
        bar_df,
        on=["date", "main_contract_vt"],
        how="left",
    )
    merged = merged.dropna(subset=["open", "high", "low", "close"]).copy()
    merged = merged[(merged["close"] > 0) & (merged["volume"] > 0)].copy()
    if merged.empty:
        return merged

    merged = merged.sort_values("date").drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)
    merged["product_vt"] = product_vt
    merged["contract_changed"] = merged["main_contract_vt"] != merged["main_contract_vt"].shift(1)
    return merged


def _rsi(close: pd.Series, window: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean()
    avg_loss = loss.ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    return 100.0 - (100.0 / (1.0 + rs))


def _true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    previous_close = close.shift(1)
    return pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)


def _adx(high: pd.Series, low: pd.Series, close: pd.Series, window: int) -> pd.Series:
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=high.index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=high.index)
    tr = _true_range(high, low, close)
    atr = tr.ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean()
    plus_di = 100.0 * plus_dm.ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean() / atr
    minus_di = 100.0 * minus_dm.ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean() / atr
    dx = ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, np.nan)) * 100.0
    return dx.ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean()


def _add_features(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    close = result["close"].astype("float64")
    high = result["high"].astype("float64")
    low = result["low"].astype("float64")

    channel_high = high.rolling(CHANNEL_WINDOW, min_periods=CHANNEL_WINDOW).max()
    channel_low = low.rolling(CHANNEL_WINDOW, min_periods=CHANNEL_WINDOW).min()
    width = (channel_high - channel_low).replace(0.0, np.nan)
    result["range_position"] = (close - channel_low) / width
    result["rsi"] = _rsi(close, RSI_WINDOW)
    result["adx"] = _adx(high, low, close, ADX_WINDOW)
    path_length = close.diff().abs().rolling(EFFICIENCY_WINDOW, min_periods=EFFICIENCY_WINDOW).sum()
    result["efficiency"] = (close - close.shift(EFFICIENCY_WINDOW)).abs() / path_length.replace(0.0, np.nan)
    tr = _true_range(high, low, close)
    result["atr_pct"] = tr.rolling(ATR_WINDOW, min_periods=ATR_WINDOW).mean() / close.replace(0.0, np.nan)
    result["prev_close"] = close.shift(1)

    for horizon in (1, 3, 5):
        future_close = close.shift(-horizon)
        same_contract = result["main_contract_vt"] == result["main_contract_vt"].shift(-horizon)
        raw_return = future_close / close - 1.0
        result[f"fwd_{horizon}d_return"] = raw_return.where(same_contract)
        result[f"fwd_{horizon}d_atr"] = (raw_return / result["atr_pct"]).where(same_contract)

    low_trend = (result["adx"] <= RANGE_SOFT_ADX_MAX) & (result["efficiency"] <= RANGE_EFFICIENCY_MAX)
    result["short_reversion_signal"] = (
        low_trend
        & (result["range_position"] >= SHORT_RANGE_POSITION_MIN)
        & (result["rsi"] >= SHORT_RSI_MIN)
        & (result["rsi"] <= SHORT_RSI_MAX)
        & (close < result["prev_close"])
    )
    result["long_reversion_signal"] = (
        low_trend
        & (result["range_position"] <= LONG_RANGE_POSITION_MAX)
        & (result["rsi"] >= LONG_RSI_MIN)
        & (result["rsi"] <= LONG_RSI_MAX)
        & (close > result["prev_close"])
    )
    return result


def _summarize_direction(df: pd.DataFrame, direction: str) -> dict[str, Any]:
    signal_col = f"{direction}_reversion_signal"
    signal_df = df[df[signal_col]].copy()
    if signal_df.empty:
        return {
            "signals": 0,
            "years": 0,
            "positive_years": 0,
            "avg_fwd_5d_atr": 0.0,
            "positive_5d_rate": 0.0,
            "bad_tail_5d_rate": 0.0,
            "score": -999.0,
        }

    sign = 1.0 if direction == "long" else -1.0
    for horizon in (1, 3, 5):
        signal_df[f"direction_fwd_{horizon}d_atr"] = sign * signal_df[f"fwd_{horizon}d_atr"]

    signal_df = signal_df.dropna(subset=["direction_fwd_5d_atr"]).copy()
    if signal_df.empty:
        return {
            "signals": 0,
            "years": 0,
            "positive_years": 0,
            "avg_fwd_5d_atr": 0.0,
            "positive_5d_rate": 0.0,
            "bad_tail_5d_rate": 0.0,
            "score": -999.0,
        }

    signal_df["year"] = signal_df["date"].dt.year.astype(int)
    yearly = signal_df.groupby("year", as_index=False).agg(
        signals=("direction_fwd_5d_atr", "size"),
        avg_fwd_5d_atr=("direction_fwd_5d_atr", "mean"),
        positive_5d_rate=("direction_fwd_5d_atr", lambda s: float((s > 0).mean())),
        bad_tail_5d_rate=("direction_fwd_5d_atr", lambda s: float((s <= -1.0).mean())),
    )
    years = int(yearly["year"].nunique())
    positive_years = int((yearly["avg_fwd_5d_atr"] > 0).sum())
    positive_year_rate = positive_years / max(years, 1)
    signals = int(len(signal_df))
    avg_fwd_1d_atr = _safe_float(signal_df["direction_fwd_1d_atr"].mean())
    avg_fwd_3d_atr = _safe_float(signal_df["direction_fwd_3d_atr"].mean())
    avg_fwd_5d_atr = _safe_float(signal_df["direction_fwd_5d_atr"].mean())
    median_fwd_5d_atr = _safe_float(signal_df["direction_fwd_5d_atr"].median())
    positive_5d_rate = _safe_float((signal_df["direction_fwd_5d_atr"] > 0).mean())
    bad_tail_5d_rate = _safe_float((signal_df["direction_fwd_5d_atr"] <= -1.0).mean())
    score = (
        1.50 * avg_fwd_5d_atr
        + 1.00 * (positive_5d_rate - 0.50)
        + 0.75 * (positive_year_rate - 0.50)
        - 0.50 * bad_tail_5d_rate
        + min(signals, 80) / 800.0
    )
    return {
        "signals": signals,
        "years": years,
        "positive_years": positive_years,
        "positive_year_rate": positive_year_rate,
        "avg_fwd_1d_atr": avg_fwd_1d_atr,
        "avg_fwd_3d_atr": avg_fwd_3d_atr,
        "avg_fwd_5d_atr": avg_fwd_5d_atr,
        "median_fwd_5d_atr": median_fwd_5d_atr,
        "positive_5d_rate": positive_5d_rate,
        "bad_tail_5d_rate": bad_tail_5d_rate,
        "score": _safe_float(score, -999.0),
    }


def _year_direction_rows(df: pd.DataFrame, product_vt: str, direction: str) -> list[dict[str, Any]]:
    signal_col = f"{direction}_reversion_signal"
    signal_df = df[df[signal_col]].copy()
    if signal_df.empty:
        return []
    sign = 1.0 if direction == "long" else -1.0
    signal_df["direction_fwd_5d_atr"] = sign * signal_df["fwd_5d_atr"]
    signal_df = signal_df.dropna(subset=["direction_fwd_5d_atr"]).copy()
    if signal_df.empty:
        return []
    signal_df["year"] = signal_df["date"].dt.year.astype(int)
    rows = []
    for row in signal_df.groupby("year").agg(
        signals=("direction_fwd_5d_atr", "size"),
        avg_fwd_5d_atr=("direction_fwd_5d_atr", "mean"),
        positive_5d_rate=("direction_fwd_5d_atr", lambda s: float((s > 0).mean())),
        bad_tail_5d_rate=("direction_fwd_5d_atr", lambda s: float((s <= -1.0).mean())),
    ).reset_index().itertuples(index=False):
        rows.append(
            {
                "product_vt": product_vt,
                "direction": direction,
                "year": int(row.year),
                "signals": int(row.signals),
                "avg_fwd_5d_atr": _safe_float(row.avg_fwd_5d_atr),
                "positive_5d_rate": _safe_float(row.positive_5d_rate),
                "bad_tail_5d_rate": _safe_float(row.bad_tail_5d_rate),
            }
        )
    return rows


def _eligible(row: pd.Series) -> bool:
    return (
        int(row["bars"]) >= MIN_BARS
        and int(row["signals"]) >= MIN_DIRECTION_SIGNALS
        and int(row["years"]) >= MIN_YEARS
        and float(row["avg_fwd_5d_atr"]) > 0.05
        and float(row["positive_year_rate"]) >= 0.60
        and float(row["positive_5d_rate"]) >= 0.52
        and float(row["bad_tail_5d_rate"]) <= 0.42
    )


def _write_report(product_direction: pd.DataFrame, top_candidates: pd.DataFrame, summary: dict[str, Any]) -> None:
    lines: list[str] = [
        "# QMT Range Reversion Full Market Universe Scout",
        "",
        "## 结论",
        f"- 全市场产品数：`{summary['total_products']}`。",
        f"- 可计算产品数：`{summary['computed_products']}`。",
        f"- 方向样本行数：`{summary['direction_rows']}`。",
        f"- 候选方向数：`{summary['eligible_direction_rows']}`。",
        f"- 非18品种候选方向数：`{summary['eligible_non_static18_direction_rows']}`。",
        "- 本阶段不是交易回测，只是从全市场寻找更适合震荡均值回归的品种/方向。",
        "",
        "## Top候选方向",
    ]
    if top_candidates.empty:
        lines.append("- 无候选方向通过基础稳定性门槛。")
    else:
        cols = [
            "product_vt",
            "direction",
            "is_static18",
            "signals",
            "years",
            "positive_year_rate",
            "avg_fwd_5d_atr",
            "positive_5d_rate",
            "bad_tail_5d_rate",
            "score",
        ]
        lines.append(top_candidates[cols].head(30).to_markdown(index=False))

    lines.extend(
        [
            "",
            "## 方法",
            "- 使用全市场主力合约映射和本地TqSdk日线CSV，构造按产品的主力连续样本。",
            "- 为避免换月跳价污染，1/3/5日前瞻收益要求信号日和未来日仍为同一主力合约。",
            "- 震荡候选不是按收益优化出来的参数，而是固定的低趋势、低效率、通道边缘、RSI温和极值、单日反转确认。",
            "- 评分只用于排序，不代表可交易版本。",
            "",
            "## 输出文件",
            f"- product_direction: `{PRODUCT_DIRECTION_OUTPUT_PATH}`",
            f"- top_candidates: `{TOP_OUTPUT_PATH}`",
            f"- year_direction: `{YEAR_OUTPUT_PATH}`",
            f"- summary: `{SUMMARY_OUTPUT_PATH}`",
        ]
    )
    REPORT_OUTPUT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    mapping = _load_mapping()
    products = _load_products()
    static18 = set(VT_SYMBOLS)
    contract_cache: dict[str, pd.DataFrame] = {}

    product_rows: list[dict[str, Any]] = []
    year_rows: list[dict[str, Any]] = []
    total_products = 0
    computed_products = 0

    for product_row in products.itertuples(index=False):
        product_vt = str(product_row.product_vt)
        total_products += 1
        series = _build_product_series(product_vt, mapping, contract_cache)
        if len(series) < MIN_BARS:
            continue
        featured = _add_features(series)
        computed_products += 1
        bars = int(len(featured))
        recent_bars = int((featured["date"] >= ANALYSIS_END - pd.Timedelta(days=365)).sum())
        for direction in ("short", "long"):
            summary = _summarize_direction(featured, direction)
            row = {
                "product_vt": product_vt,
                "exchange": str(getattr(product_row, "exchange", "")),
                "direction": direction,
                "is_static18": product_vt in static18,
                "bars": bars,
                "recent_bars": recent_bars,
                **summary,
            }
            product_rows.append(row)
            year_rows.extend(_year_direction_rows(featured, product_vt, direction))

    product_direction = pd.DataFrame(product_rows)
    if product_direction.empty:
        raise RuntimeError("no product direction rows generated")

    product_direction["eligible"] = product_direction.apply(_eligible, axis=1).astype(int)
    product_direction = product_direction.sort_values(
        ["eligible", "score", "avg_fwd_5d_atr", "signals"],
        ascending=[False, False, False, False],
    ).reset_index(drop=True)
    top_candidates = product_direction[product_direction["eligible"] == 1].copy()
    year_direction = pd.DataFrame(year_rows)

    product_direction.to_csv(PRODUCT_DIRECTION_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    top_candidates.to_csv(TOP_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    year_direction.to_csv(YEAR_OUTPUT_PATH, index=False, encoding="utf-8-sig")

    summary = {
        "model_tag": MODEL_TAG,
        "analysis_start": str(ANALYSIS_START.date()),
        "analysis_end": str(ANALYSIS_END.date()),
        "total_products": total_products,
        "computed_products": computed_products,
        "direction_rows": int(len(product_direction)),
        "eligible_direction_rows": int(len(top_candidates)),
        "eligible_non_static18_direction_rows": int((top_candidates["is_static18"] == False).sum()) if not top_candidates.empty else 0,
        "parameters": {
            "channel_window": CHANNEL_WINDOW,
            "rsi_window": RSI_WINDOW,
            "adx_window": ADX_WINDOW,
            "efficiency_window": EFFICIENCY_WINDOW,
            "range_soft_adx_max": RANGE_SOFT_ADX_MAX,
            "range_efficiency_max": RANGE_EFFICIENCY_MAX,
            "short_range_position_min": SHORT_RANGE_POSITION_MIN,
            "long_range_position_max": LONG_RANGE_POSITION_MAX,
            "short_rsi_min": SHORT_RSI_MIN,
            "short_rsi_max": SHORT_RSI_MAX,
            "long_rsi_min": LONG_RSI_MIN,
            "long_rsi_max": LONG_RSI_MAX,
        },
    }
    SUMMARY_OUTPUT_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(product_direction, top_candidates, summary)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"product_direction: {PRODUCT_DIRECTION_OUTPUT_PATH}")
    print(f"top_candidates: {TOP_OUTPUT_PATH}")
    print(f"year_direction: {YEAR_OUTPUT_PATH}")
    print(f"report: {REPORT_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
