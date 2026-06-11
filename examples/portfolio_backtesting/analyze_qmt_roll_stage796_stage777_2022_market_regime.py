from __future__ import annotations

import json
import math
import sqlite3
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
from main_contract_mapping import load_mapping_df
import qmt_roll_official_candidate_stage777_config as stage777_cfg


PROJECT_DIR = Path(__file__).resolve().parent
ROOT_DIR = PROJECT_DIR.parent.parent
DB_PATH = ROOT_DIR / ".vntrader" / "database.db"
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage796_stage777_2022_market_regime_v1"
OUTPUT_PREFIX = "qmt_roll_stage796_stage777_2022_market_regime"
LINE_ID = "futures_trend_2019_data_extension"

DD_START = pd.Timestamp("2022-03-09")
DD_END = pd.Timestamp("2022-06-29")

MARKET_DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_market_daily_{MODEL_TAG}.csv"
PERIOD_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_period_summary_{MODEL_TAG}.csv"
PRODUCT_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_summary_{MODEL_TAG}.csv"
ROLLING_WINDOWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rolling_window_percentiles_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _split_vt(vt_symbol: str) -> tuple[str, str]:
    symbol, exchange = vt_symbol.split(".", 1)
    return symbol, exchange


def _load_official_candidate_universe() -> tuple[list[str], dict[str, float]]:
    universe_path, _eligibility_path = stage777_cfg.build_official_candidate_stage777_paths()
    universe = pd.read_csv(universe_path)
    if "eligible" in universe.columns:
        universe = universe[pd.to_numeric(universe["eligible"], errors="coerce").fillna(0).astype(int).eq(1)].copy()
    column = "product_vt_symbol" if "product_vt_symbol" in universe.columns else "vt_symbol"
    if column not in universe.columns:
        raise ValueError(f"official candidate universe missing product symbol column: {universe_path}")
    products = sorted(universe[column].dropna().astype(str).unique().tolist())
    if not products:
        raise RuntimeError(f"empty official candidate universe: {universe_path}")
    size_map: dict[str, float] = {}
    for row in universe.itertuples(index=False):
        vt_symbol = str(getattr(row, column))
        size = getattr(row, "volume_multiple", 0.0)
        try:
            size_value = float(size)
        except (TypeError, ValueError):
            size_value = 0.0
        size_map[vt_symbol] = size_value if size_value > 0 else 1.0
    return products, size_map


def _load_product_bars() -> pd.DataFrame:
    vt_symbols, size_map = _load_official_candidate_universe()
    start = pd.Timestamp("2020-01-01")
    end = pd.Timestamp("2026-05-31")
    mapping = load_mapping_df()
    mapping["date"] = pd.to_datetime(mapping["date"], errors="coerce").dt.normalize()
    mapping = mapping[
        mapping["continuous_symbol_vt"].isin(vt_symbols)
        & mapping["date"].ge(start)
        & mapping["date"].le(end)
        & mapping["main_contract_vt"].fillna("").astype(str).ne("")
    ].copy()
    mapping.rename(columns={"continuous_symbol_vt": "product_vt_symbol"}, inplace=True)
    main_contracts = sorted(mapping["main_contract_vt"].dropna().astype(str).unique().tolist())

    rows: list[pd.DataFrame] = []
    with sqlite3.connect(DB_PATH) as conn:
        for vt_symbol in main_contracts:
            symbol, exchange = _split_vt(vt_symbol)
            frame = pd.read_sql_query(
                """
                select
                    datetime as date,
                    symbol,
                    exchange,
                    open_price as open,
                    high_price as high,
                    low_price as low,
                    close_price as close,
                    volume,
                    open_interest
                from dbbardata
                where interval = 'd'
                  and symbol = ?
                  and exchange = ?
                  and datetime between '2020-01-01' and '2026-05-31'
                order by datetime
                """,
                conn,
                params=(symbol, exchange),
            )
            if frame.empty:
                continue
            frame["main_contract_vt"] = vt_symbol
            frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
            rows.append(frame)
    if not rows:
        raise RuntimeError("no product bars loaded")
    contract_bars = pd.concat(rows, ignore_index=True)
    bars = mapping[["date", "product_vt_symbol", "main_contract_vt"]].merge(
        contract_bars,
        on=["date", "main_contract_vt"],
        how="left",
    )
    for column in ["open", "high", "low", "close", "volume", "open_interest"]:
        bars[column] = pd.to_numeric(bars[column], errors="coerce")
    bars["contract_size"] = bars["product_vt_symbol"].map(size_map).fillna(1.0).astype(float)
    bars["notional_proxy"] = bars["close"] * bars["contract_size"] * bars["volume"]
    bars["oi_notional_proxy"] = bars["close"] * bars["contract_size"] * bars["open_interest"]
    bars["range_pct"] = ((bars["high"] - bars["low"]) / bars["close"].replace(0.0, np.nan)).replace(
        [np.inf, -np.inf],
        np.nan,
    )
    bars.sort_values(["product_vt_symbol", "date"], inplace=True)
    bars["ret"] = bars.groupby("product_vt_symbol")["close"].pct_change(fill_method=None)
    bars["abs_ret"] = bars["ret"].abs()
    for window in (20, 40, 60):
        bars[f"ret_{window}d"] = bars.groupby("product_vt_symbol")["close"].pct_change(window, fill_method=None)
        net = bars.groupby("product_vt_symbol")["close"].diff(window).abs()
        diff_abs = bars.groupby("product_vt_symbol")["close"].diff().abs()
        path = (
            diff_abs.groupby(bars["product_vt_symbol"])
            .rolling(window, min_periods=10)
            .sum()
            .reset_index(level=0, drop=True)
        )
        bars[f"trend_eff_{window}d"] = (net / path.replace(0.0, np.nan)).replace([np.inf, -np.inf], np.nan)
        volume_ma = (
            bars.groupby("product_vt_symbol")["volume"]
            .rolling(window, min_periods=10)
            .mean()
            .reset_index(level=0, drop=True)
        )
        bars[f"vol_ratio_{window}d"] = bars["volume"] / volume_ma.replace(0.0, np.nan)
        bars[f"oi_chg_{window}d"] = bars.groupby("product_vt_symbol")["open_interest"].pct_change(window, fill_method=None)
    return bars


def _avg_pairwise_corr(daily_returns: pd.DataFrame) -> float:
    if daily_returns.shape[1] < 2:
        return 0.0
    corr = daily_returns.corr(min_periods=10)
    values = corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool)).stack()
    if values.empty:
        return 0.0
    return float(values.mean())


def _build_market_daily(bars: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    returns_pivot = bars.pivot_table(index="date", columns="product_vt_symbol", values="ret", aggfunc="first")
    for date, group in bars.groupby("date", sort=True):
        active = group[group["close"].notna()].copy()
        if active.empty:
            continue
        ret_row = returns_pivot.loc[:date].tail(20)
        trend_ret_20 = pd.to_numeric(active["ret_20d"], errors="coerce")
        rows.append(
            {
                "date": date,
                "active_products": int(active["product_vt_symbol"].nunique()),
                "total_volume": float(active["volume"].fillna(0.0).sum()),
                "total_notional_proxy": float(active["notional_proxy"].fillna(0.0).sum()),
                "total_open_interest": float(active["open_interest"].fillna(0.0).sum()),
                "total_oi_notional_proxy": float(active["oi_notional_proxy"].fillna(0.0).sum()),
                "avg_volume_per_product": float(active["volume"].fillna(0.0).mean()),
                "avg_notional_per_product": float(active["notional_proxy"].fillna(0.0).mean()),
                "avg_oi_per_product": float(active["open_interest"].fillna(0.0).mean()),
                "avg_range_pct": float(active["range_pct"].mean() * 100.0),
                "avg_abs_ret_pct": float(active["abs_ret"].mean() * 100.0),
                "avg_trend_eff_20d": float(active["trend_eff_20d"].mean()),
                "avg_trend_eff_40d": float(active["trend_eff_40d"].mean()),
                "avg_trend_eff_60d": float(active["trend_eff_60d"].mean()),
                "positive_ret_breadth_pct": float((pd.to_numeric(active["ret"], errors="coerce") > 0.0).mean() * 100.0),
                "positive_20d_breadth_pct": float((trend_ret_20 > 0.0).mean() * 100.0),
                "abs_20d_breadth_away_50": float(abs((trend_ret_20 > 0.0).mean() * 100.0 - 50.0)),
                "avg_pairwise_corr_20d": _avg_pairwise_corr(ret_row),
            }
        )
    out = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    for column in [
        "total_volume",
        "total_notional_proxy",
        "total_open_interest",
        "total_oi_notional_proxy",
        "avg_range_pct",
        "avg_abs_ret_pct",
        "avg_trend_eff_20d",
        "avg_pairwise_corr_20d",
    ]:
        out[f"{column}_z252"] = (
            (out[column] - out[column].rolling(252, min_periods=126).mean())
            / out[column].rolling(252, min_periods=126).std().replace(0.0, np.nan)
        )
    return out


def _period_slices(market: pd.DataFrame) -> dict[str, pd.DataFrame]:
    ordered_dates = pd.DatetimeIndex(market["date"].sort_values().unique())
    dd_dates = ordered_dates[(ordered_dates >= DD_START) & (ordered_dates <= DD_END)]
    dd_len = len(dd_dates)
    pre_dates = ordered_dates[ordered_dates < DD_START][-dd_len:]
    post_dates = ordered_dates[ordered_dates > DD_END][:dd_len]
    return {
        "pre_same_length": market[market["date"].isin(pre_dates)].copy(),
        "dd_20220309_20220629": market[market["date"].isin(dd_dates)].copy(),
        "post_same_length": market[market["date"].isin(post_dates)].copy(),
        "same_calendar_2021": market[(market["date"] >= pd.Timestamp("2021-03-09")) & (market["date"] <= pd.Timestamp("2021-06-29"))].copy(),
        "same_calendar_2023": market[(market["date"] >= pd.Timestamp("2023-03-09")) & (market["date"] <= pd.Timestamp("2023-06-29"))].copy(),
        "same_calendar_2024": market[(market["date"] >= pd.Timestamp("2024-03-09")) & (market["date"] <= pd.Timestamp("2024-06-29"))].copy(),
        "full_2020_2026": market.copy(),
    }


def _period_summary(market: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for name, frame in _period_slices(market).items():
        if frame.empty:
            continue
        rows.append(
            {
                "period": name,
                "start": frame["date"].min().date().isoformat(),
                "end": frame["date"].max().date().isoformat(),
                "trading_days": int(len(frame)),
                "active_products_avg": float(frame["active_products"].mean()),
                "total_volume_avg": float(frame["total_volume"].mean()),
                "total_notional_proxy_avg": float(frame["total_notional_proxy"].mean()),
                "total_open_interest_avg": float(frame["total_open_interest"].mean()),
                "total_oi_notional_proxy_avg": float(frame["total_oi_notional_proxy"].mean()),
                "avg_volume_per_product": float(frame["avg_volume_per_product"].mean()),
                "avg_notional_per_product": float(frame["avg_notional_per_product"].mean()),
                "avg_oi_per_product": float(frame["avg_oi_per_product"].mean()),
                "avg_range_pct": float(frame["avg_range_pct"].mean()),
                "avg_abs_ret_pct": float(frame["avg_abs_ret_pct"].mean()),
                "avg_trend_eff_20d": float(frame["avg_trend_eff_20d"].mean()),
                "avg_trend_eff_40d": float(frame["avg_trend_eff_40d"].mean()),
                "avg_trend_eff_60d": float(frame["avg_trend_eff_60d"].mean()),
                "positive_ret_breadth_pct": float(frame["positive_ret_breadth_pct"].mean()),
                "positive_20d_breadth_pct": float(frame["positive_20d_breadth_pct"].mean()),
                "abs_20d_breadth_away_50": float(frame["abs_20d_breadth_away_50"].mean()),
                "avg_pairwise_corr_20d": float(frame["avg_pairwise_corr_20d"].mean()),
                "total_volume_z252_avg": float(frame["total_volume_z252"].mean()),
                "total_notional_z252_avg": float(frame["total_notional_proxy_z252"].mean()),
                "open_interest_z252_avg": float(frame["total_open_interest_z252"].mean()),
                "range_z252_avg": float(frame["avg_range_pct_z252"].mean()),
                "abs_ret_z252_avg": float(frame["avg_abs_ret_pct_z252"].mean()),
                "trend_eff20_z252_avg": float(frame["avg_trend_eff_20d_z252"].mean()),
                "corr20_z252_avg": float(frame["avg_pairwise_corr_20d_z252"].mean()),
            }
        )
    summary = pd.DataFrame(rows)
    base = summary[summary["period"].eq("dd_20220309_20220629")].iloc[0]
    for column in [
        "total_volume_avg",
        "total_notional_proxy_avg",
        "total_open_interest_avg",
        "total_oi_notional_proxy_avg",
        "avg_volume_per_product",
        "avg_notional_per_product",
        "avg_oi_per_product",
        "avg_range_pct",
        "avg_abs_ret_pct",
        "avg_trend_eff_20d",
        "avg_pairwise_corr_20d",
    ]:
        summary[f"dd_ratio_{column}"] = base[column] / summary[column].replace(0.0, np.nan)
    return summary


def _product_summary(bars: pd.DataFrame) -> pd.DataFrame:
    dd = bars[(bars["date"] >= DD_START) & (bars["date"] <= DD_END)].copy()
    pre_dates = pd.DatetimeIndex(sorted(bars["date"].unique()))
    dd_len = pd.DatetimeIndex(sorted(dd["date"].unique())).size
    pre_index = pre_dates[pre_dates < DD_START][-dd_len:]
    pre = bars[bars["date"].isin(pre_index)].copy()
    rows: list[dict[str, Any]] = []
    for product in sorted(set(dd["product_vt_symbol"])):
        d = dd[dd["product_vt_symbol"].eq(product)]
        p = pre[pre["product_vt_symbol"].eq(product)]
        if d.empty:
            continue
        start_close = float(d.sort_values("date")["close"].iloc[0])
        end_close = float(d.sort_values("date")["close"].iloc[-1])
        rows.append(
            {
                "product_vt_symbol": product,
                "dd_days": int(len(d)),
                "dd_return_pct": (end_close / start_close - 1.0) * 100.0 if start_close else np.nan,
                "dd_volume_avg": float(d["volume"].mean()),
                "pre_volume_avg": float(p["volume"].mean()) if len(p) else np.nan,
                "volume_ratio_vs_pre": float(d["volume"].mean() / p["volume"].mean()) if len(p) and float(p["volume"].mean()) else np.nan,
                "dd_oi_avg": float(d["open_interest"].mean()),
                "pre_oi_avg": float(p["open_interest"].mean()) if len(p) else np.nan,
                "oi_ratio_vs_pre": float(d["open_interest"].mean() / p["open_interest"].mean()) if len(p) and float(p["open_interest"].mean()) else np.nan,
                "dd_range_pct": float(d["range_pct"].mean() * 100.0),
                "dd_abs_ret_pct": float(d["abs_ret"].mean() * 100.0),
                "dd_trend_eff_20d": float(d["trend_eff_20d"].mean()),
            }
        )
    return pd.DataFrame(rows).sort_values("dd_return_pct").reset_index(drop=True)


def _rolling_window_percentiles(market: pd.DataFrame) -> pd.DataFrame:
    metrics = [
        "total_volume",
        "total_notional_proxy",
        "total_open_interest",
        "avg_range_pct",
        "avg_abs_ret_pct",
        "avg_trend_eff_20d",
        "avg_pairwise_corr_20d",
    ]
    dates = pd.DatetimeIndex(market["date"].sort_values().unique())
    dd_dates = dates[(dates >= DD_START) & (dates <= DD_END)]
    window = len(dd_dates)
    rows: list[dict[str, Any]] = []
    ordered = market.set_index("date").sort_index()
    dd_mean = ordered.loc[dd_dates, metrics].mean()
    for metric in metrics:
        roll = ordered[metric].rolling(window, min_periods=window).mean().dropna()
        percentile = float((roll <= dd_mean[metric]).mean() * 100.0) if len(roll) else np.nan
        rows.append(
            {
                "metric": metric,
                "dd_mean": float(dd_mean[metric]),
                "rolling_window_days": int(window),
                "percentile_low_to_high": percentile,
                "interpretation": "higher_than_most" if percentile >= 70 else ("lower_than_most" if percentile <= 30 else "middle"),
            }
        )
    return pd.DataFrame(rows)


def _plot(market: pd.DataFrame) -> None:
    frame = market[(market["date"] >= pd.Timestamp("2021-01-01")) & (market["date"] <= pd.Timestamp("2023-12-31"))].copy()
    fig, axes = plt.subplots(4, 1, figsize=(17, 11), sharex=True)
    specs = [
        ("total_volume", "Total volume"),
        ("total_open_interest", "Total open interest"),
        ("avg_range_pct", "Average intraday range %"),
        ("avg_trend_eff_20d", "Average 20d trend efficiency"),
    ]
    for ax, (column, title) in zip(axes, specs, strict=True):
        ax.plot(frame["date"], frame[column], color="#1f77b4", linewidth=1.2)
        ax.axvspan(DD_START, DD_END, color="#ef4444", alpha=0.16, label="Stage777 max DD")
        ax.set_ylabel(title)
        ax.grid(alpha=0.24)
    axes[0].legend(loc="upper left")
    axes[-1].set_xlabel("Date")
    fig.suptitle("Stage777 2022 drawdown window: market liquidity and regime", fontsize=15)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _write_report(period: pd.DataFrame, product: pd.DataFrame, rolling: pd.DataFrame, decision: dict[str, Any]) -> None:
    display_cols = [
        "period",
        "trading_days",
        "total_volume_avg",
        "total_notional_proxy_avg",
        "total_open_interest_avg",
        "avg_range_pct",
        "avg_abs_ret_pct",
        "avg_trend_eff_20d",
        "avg_pairwise_corr_20d",
        "total_volume_z252_avg",
        "open_interest_z252_avg",
    ]
    product_cols = [
        "product_vt_symbol",
        "dd_return_pct",
        "volume_ratio_vs_pre",
        "oi_ratio_vs_pre",
        "dd_range_pct",
        "dd_trend_eff_20d",
    ]
    lines = [
        "# Stage796 Stage777 2022最大回撤市场状态归因",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 回撤窗口：`{DD_START.date()}` 到 `{DD_END.date()}`。",
        "- 口径：官方候选冻结品种池 19 个商品连续品种；成交额/持仓额使用 `close * contract_size * volume/open_interest` 代理。",
        "",
        "## Period Summary",
        "",
        _md_table(period[display_cols], max_rows=20),
        "",
        "## Rolling Window Percentiles",
        "",
        _md_table(rolling, max_rows=20),
        "",
        "## Product Summary",
        "",
        _md_table(product[product_cols], max_rows=25),
        "",
        "## Decision",
        "",
        f"- 结论：{decision['conclusion']}",
        f"- 判断：{decision['judgment']}",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    bars = _load_product_bars()
    market = _build_market_daily(bars)
    period = _period_summary(market)
    product = _product_summary(bars)
    rolling = _rolling_window_percentiles(market)
    _plot(market)

    dd_row = period[period["period"].eq("dd_20220309_20220629")].iloc[0]
    pre_row = period[period["period"].eq("pre_same_length")].iloc[0]
    decision = {
        "stage": "Stage796",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "window": {"start": DD_START.date().isoformat(), "end": DD_END.date().isoformat()},
        "conclusion": "volume_not_collapsed_but_trend_quality_collapsed_with_high_participation",
        "judgment": (
            "The drawdown window is not best described as a simple liquidity drought. "
            "Aggregate volume was lower than the immediately preceding surge, but open interest stayed elevated; "
            "the more damaging features were high realized range, synchronized macro reversal, and lower trend efficiency."
        ),
        "key_ratios_vs_pre": {
            "total_volume": float(dd_row["total_volume_avg"] / pre_row["total_volume_avg"]),
            "total_notional_proxy": float(dd_row["total_notional_proxy_avg"] / pre_row["total_notional_proxy_avg"]),
            "total_open_interest": float(dd_row["total_open_interest_avg"] / pre_row["total_open_interest_avg"]),
            "avg_range_pct": float(dd_row["avg_range_pct"] / pre_row["avg_range_pct"]),
            "avg_trend_eff_20d": float(dd_row["avg_trend_eff_20d"] / pre_row["avg_trend_eff_20d"]),
        },
        "outputs": {
            "market_daily": str(MARKET_DAILY_PATH),
            "period_summary": str(PERIOD_SUMMARY_PATH),
            "product_summary": str(PRODUCT_SUMMARY_PATH),
            "rolling_percentiles": str(ROLLING_WINDOWS_PATH),
            "chart": str(CHART_PATH),
            "report": str(REPORT_PATH),
        },
    }

    market.to_csv(MARKET_DAILY_PATH, index=False, encoding="utf-8-sig")
    period.to_csv(PERIOD_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    product.to_csv(PRODUCT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    rolling.to_csv(ROLLING_WINDOWS_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(period, product, rolling, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
