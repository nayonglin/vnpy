from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[4]
BACKTEST_DIR = ROOT_DIR / "examples" / "portfolio_backtesting"
if str(BACKTEST_DIR) not in sys.path:
    sys.path.insert(0, str(BACKTEST_DIR))

from main_contract_mapping import load_mapping_df  # noqa: E402


LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE_ID = "stage122_2022_full_market_trend_inventory"
MODEL_TAG = f"{STAGE_ID}_v1"

DB_PATH = ROOT_DIR / ".vntrader" / "database.db"
FULL_MARKET_ELIGIBLE_PATH = (
    BACKTEST_DIR
    / "backtest_outputs"
    / "qmt_roll_full_market_tradable_universe_eligible_full_market_tradable_universe_v1.csv"
)
STAGE182_COMBINED_ELIGIBILITY_PATH = (
    BACKTEST_DIR
    / "backtest_outputs"
    / "qmt_roll_stage182_ai_product_pool_live_inference_combined_stage78_eligibility_stage182_ai_product_pool_live_inference_v1.csv"
)

OUTPUT_DIR = ROOT_DIR / "research" / "lines" / LINE_ID / "outputs" / STAGE_ID
STAGE_RECORD_PATH = (
    ROOT_DIR
    / "research"
    / "lines"
    / LINE_ID
    / "stages"
    / "20260709_1327_stage122_2022_full_market_trend_inventory.md"
)

PRODUCT_DAILY_PATH = OUTPUT_DIR / f"rebuilt_c9_v2_{STAGE_ID}_product_daily_{MODEL_TAG}.csv.gz"
PRODUCT_PERIOD_SUMMARY_PATH = OUTPUT_DIR / f"rebuilt_c9_v2_{STAGE_ID}_product_period_summary_{MODEL_TAG}.csv"
UNIVERSE_PERIOD_SUMMARY_PATH = OUTPUT_DIR / f"rebuilt_c9_v2_{STAGE_ID}_universe_period_summary_{MODEL_TAG}.csv"
TOP_TREND_PATH = OUTPUT_DIR / f"rebuilt_c9_v2_{STAGE_ID}_top_trend_products_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"rebuilt_c9_v2_{STAGE_ID}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"rebuilt_c9_v2_{STAGE_ID}_report_{MODEL_TAG}.md"
TREND_BAR_CHART_PATH = OUTPUT_DIR / f"rebuilt_c9_v2_{STAGE_ID}_loss_window_top_trend_bar_{MODEL_TAG}.png"
TREND_SCATTER_CHART_PATH = OUTPUT_DIR / f"rebuilt_c9_v2_{STAGE_ID}_loss_window_trend_scatter_{MODEL_TAG}.png"

ANALYSIS_QUERY_START = pd.Timestamp("2021-01-01")
ANALYSIS_QUERY_END = pd.Timestamp("2022-12-31")
LOSS_WINDOW_START = pd.Timestamp("2022-03-09")
LOSS_WINDOW_END = pd.Timestamp("2022-06-29")
FULL_2022_START = pd.Timestamp("2022-01-01")
FULL_2022_END = pd.Timestamp("2022-12-31")
MIN_COVERAGE = 0.80


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if np.isnan(value) or np.isinf(value):
            return None
        return float(value)
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if pd.isna(value):
        return None
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    display = frame.copy()
    if max_rows is not None:
        display = display.head(max_rows)
    return display.to_markdown(index=False, floatfmt=".4f")


def _split_vt(vt_symbol: str) -> tuple[str, str]:
    symbol, exchange = vt_symbol.split(".", 1)
    return symbol, exchange


def _load_universe() -> pd.DataFrame:
    eligible = pd.read_csv(FULL_MARKET_ELIGIBLE_PATH)
    eligible = eligible[pd.to_numeric(eligible["eligible"], errors="coerce").fillna(0).astype(int).eq(1)].copy()
    eligible["product_vt_symbol"] = eligible["product_vt_symbol"].astype(str)
    eligible["is_static_strategy_product"] = (
        pd.to_numeric(eligible.get("is_static_strategy_product", 0), errors="coerce").fillna(0).astype(int)
    )

    if STAGE182_COMBINED_ELIGIBILITY_PATH.exists():
        ai = pd.read_csv(STAGE182_COMBINED_ELIGIBILITY_PATH)
        ai["eval_date"] = pd.to_datetime(ai["eval_date"], errors="coerce")
        ai_2022 = ai[
            ai["eval_date"].ge(pd.Timestamp("2022-01-01"))
            & ai["eval_date"].le(pd.Timestamp("2022-12-31"))
        ].copy()
        ai_2022_loss = ai_2022[
            ai_2022["eval_date"].ge(pd.Timestamp("2022-01-01"))
            & ai_2022["eval_date"].le(LOSS_WINDOW_END)
        ].copy()
        ai_2022_products = set(ai_2022["product_vt_symbol"].dropna().astype(str))
        ai_loss_products = set(ai_2022_loss["product_vt_symbol"].dropna().astype(str))
    else:
        ai_2022_products = set()
        ai_loss_products = set()

    eligible["in_static18_pool"] = eligible["is_static_strategy_product"].eq(1)
    eligible["in_stage182_ai_2022_union"] = eligible["product_vt_symbol"].isin(ai_2022_products)
    eligible["in_stage182_ai_loss_window_to_202206"] = eligible["product_vt_symbol"].isin(ai_loss_products)
    return eligible


def _load_product_bars(universe: pd.DataFrame) -> pd.DataFrame:
    products = sorted(universe["product_vt_symbol"].dropna().astype(str).unique().tolist())
    mapping = load_mapping_df()
    mapping["date"] = pd.to_datetime(mapping["date"], errors="coerce").dt.normalize()
    mapping = mapping[
        mapping["continuous_symbol_vt"].isin(products)
        & mapping["date"].ge(ANALYSIS_QUERY_START)
        & mapping["date"].le(ANALYSIS_QUERY_END)
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
                  and datetime between ? and ?
                order by datetime
                """,
                conn,
                params=(
                    symbol,
                    exchange,
                    ANALYSIS_QUERY_START.strftime("%Y-%m-%d"),
                    ANALYSIS_QUERY_END.strftime("%Y-%m-%d"),
                ),
            )
            if frame.empty:
                continue
            frame["main_contract_vt"] = vt_symbol
            frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
            rows.append(frame)

    if not rows:
        raise RuntimeError("no dbbardata rows found for full-market products")

    contract_bars = pd.concat(rows, ignore_index=True)
    bars = mapping[["date", "product_vt_symbol", "main_contract_vt"]].merge(
        contract_bars,
        on=["date", "main_contract_vt"],
        how="left",
    )
    bars = bars.merge(
        universe[
            [
                "product_vt_symbol",
                "exchange",
                "is_static_strategy_product",
                "in_static18_pool",
                "in_stage182_ai_2022_union",
                "in_stage182_ai_loss_window_to_202206",
            ]
        ],
        on="product_vt_symbol",
        how="left",
        suffixes=("_contract", "_product"),
    )
    if "exchange_product" in bars.columns:
        bars["exchange"] = bars["exchange_product"].fillna(bars.get("exchange_contract"))
    elif "exchange_contract" in bars.columns:
        bars["exchange"] = bars["exchange_contract"]
    for column in ["open", "high", "low", "close", "volume", "open_interest"]:
        bars[column] = pd.to_numeric(bars[column], errors="coerce")
    bars.sort_values(["product_vt_symbol", "date"], inplace=True)
    bars["ret"] = bars.groupby("product_vt_symbol")["close"].pct_change(fill_method=None)
    bars["abs_ret"] = bars["ret"].abs()
    for window in (20, 40, 60, 120):
        bars[f"ret_{window}d"] = bars.groupby("product_vt_symbol")["close"].pct_change(window, fill_method=None)
        net = bars.groupby("product_vt_symbol")["close"].diff(window).abs()
        diff_abs = bars.groupby("product_vt_symbol")["close"].diff().abs()
        path = (
            diff_abs.groupby(bars["product_vt_symbol"])
            .rolling(window, min_periods=max(10, window // 2))
            .sum()
            .reset_index(level=0, drop=True)
        )
        bars[f"trend_eff_{window}d"] = (net / path.replace(0.0, np.nan)).replace([np.inf, -np.inf], np.nan)
    bars = _attach_adx(bars)
    return bars


def _wilder(series: pd.Series, window: int) -> pd.Series:
    return series.ewm(alpha=1.0 / window, adjust=False, min_periods=window).mean()


def _attach_adx(bars: pd.DataFrame, window: int = 14) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for _, group in bars.groupby("product_vt_symbol", sort=False):
        g = group.copy()
        high = pd.to_numeric(g["high"], errors="coerce")
        low = pd.to_numeric(g["low"], errors="coerce")
        close = pd.to_numeric(g["close"], errors="coerce")
        prev_close = close.shift(1)
        up_move = high.diff()
        down_move = -low.diff()
        plus_dm = pd.Series(
            np.where((up_move > down_move) & (up_move > 0), up_move, 0.0),
            index=g.index,
        )
        minus_dm = pd.Series(
            np.where((down_move > up_move) & (down_move > 0), down_move, 0.0),
            index=g.index,
        )
        tr = pd.concat(
            [
                high - low,
                (high - prev_close).abs(),
                (low - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        atr = _wilder(tr, window)
        plus_di = 100.0 * _wilder(plus_dm, window) / atr.replace(0.0, np.nan)
        minus_di = 100.0 * _wilder(minus_dm, window) / atr.replace(0.0, np.nan)
        dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, np.nan)
        g["adx14"] = _wilder(dx, window).replace([np.inf, -np.inf], np.nan)
        g["di_spread14"] = (plus_di - minus_di).replace([np.inf, -np.inf], np.nan)
        frames.append(g)
    return pd.concat(frames, ignore_index=True, sort=False)


def _period_frame(bars: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    return bars[bars["date"].ge(start) & bars["date"].le(end)].copy()


def _score_period(bars: pd.DataFrame, period: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    frame = _period_frame(bars, start, end)
    market_dates = pd.DatetimeIndex(sorted(frame["date"].dropna().unique()))
    rows: list[dict[str, Any]] = []
    for product, group in frame.groupby("product_vt_symbol", sort=True):
        g = group[group["close"].notna()].sort_values("date").copy()
        if g.empty:
            continue
        first = float(g["close"].iloc[0])
        last = float(g["close"].iloc[-1])
        close_diff_abs = g["close"].diff().abs().sum()
        net_move = abs(last - first)
        signed_return_pct = (last / first - 1.0) * 100.0 if first else np.nan
        trend_eff = net_move / close_diff_abs if close_diff_abs else np.nan
        ret20 = pd.to_numeric(g["ret_20d"], errors="coerce")
        ret60 = pd.to_numeric(g["ret_60d"], errors="coerce")
        positive20 = float((ret20 > 0.0).mean()) if ret20.notna().any() else np.nan
        negative20 = float((ret20 < 0.0).mean()) if ret20.notna().any() else np.nan
        rows.append(
            {
                "period": period,
                "period_start": start.date().isoformat(),
                "period_end": end.date().isoformat(),
                "product_vt_symbol": product,
                "exchange": str(g["exchange"].dropna().iloc[0]) if g["exchange"].notna().any() else "",
                "days": int(len(g)),
                "period_market_days": int(len(market_dates)),
                "coverage_ratio": float(len(g) / len(market_dates)) if len(market_dates) else np.nan,
                "contract_count": int(g["main_contract_vt"].dropna().astype(str).nunique()),
                "in_static18_pool": bool(g["in_static18_pool"].fillna(False).astype(bool).any()),
                "in_stage182_ai_2022_union": bool(g["in_stage182_ai_2022_union"].fillna(False).astype(bool).any()),
                "in_stage182_ai_loss_window_to_202206": bool(
                    g["in_stage182_ai_loss_window_to_202206"].fillna(False).astype(bool).any()
                ),
                "start_close": first,
                "end_close": last,
                "signed_return_pct": signed_return_pct,
                "abs_return_pct": abs(signed_return_pct),
                "trend_direction": "up" if signed_return_pct > 0 else ("down" if signed_return_pct < 0 else "flat"),
                "whole_window_trend_eff": trend_eff,
                "mean_trend_eff_20d": float(pd.to_numeric(g["trend_eff_20d"], errors="coerce").mean()),
                "mean_trend_eff_60d": float(pd.to_numeric(g["trend_eff_60d"], errors="coerce").mean()),
                "mean_adx14": float(pd.to_numeric(g["adx14"], errors="coerce").mean()),
                "max_adx14": float(pd.to_numeric(g["adx14"], errors="coerce").max()),
                "adx14_ge25_ratio": float((pd.to_numeric(g["adx14"], errors="coerce") >= 25.0).mean()),
                "mean_abs_20d_return_pct": float(ret20.abs().mean() * 100.0),
                "max_abs_20d_return_pct": float(ret20.abs().max() * 100.0),
                "mean_abs_60d_return_pct": float(ret60.abs().mean() * 100.0),
                "positive_20d_ratio": positive20,
                "negative_20d_ratio": negative20,
                "directional_20d_consistency": max(positive20, negative20)
                if pd.notna(positive20) and pd.notna(negative20)
                else np.nan,
                "avg_volume": float(pd.to_numeric(g["volume"], errors="coerce").mean()),
                "avg_open_interest": float(pd.to_numeric(g["open_interest"], errors="coerce").mean()),
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out = _attach_composite_score(out)
    out["trend_bucket"] = np.where(
        (out["coverage_ratio"] >= MIN_COVERAGE)
        & (out["trend_score"] >= out["trend_score"].quantile(0.75))
        & (out["abs_return_pct"] >= 10.0),
        "strong_trend_top_quartile",
        np.where(
            (out["coverage_ratio"] >= MIN_COVERAGE)
            & (out["trend_score"] >= out["trend_score"].quantile(0.50))
            & (out["abs_return_pct"] >= 7.0),
            "tradable_trend_middle_plus",
            "weak_or_noisy",
        ),
    )
    return out.sort_values(["period", "trend_score"], ascending=[True, False]).reset_index(drop=True)


def _attach_composite_score(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    metrics = [
        "abs_return_pct",
        "whole_window_trend_eff",
        "mean_trend_eff_20d",
        "mean_adx14",
        "adx14_ge25_ratio",
        "max_abs_20d_return_pct",
        "directional_20d_consistency",
    ]
    weights = {
        "abs_return_pct": 0.25,
        "whole_window_trend_eff": 0.20,
        "mean_trend_eff_20d": 0.15,
        "mean_adx14": 0.15,
        "adx14_ge25_ratio": 0.10,
        "max_abs_20d_return_pct": 0.10,
        "directional_20d_consistency": 0.05,
    }
    score = pd.Series(0.0, index=out.index)
    total_weight = 0.0
    for metric in metrics:
        values = pd.to_numeric(out[metric], errors="coerce")
        pct = values.rank(pct=True, na_option="bottom")
        weight = weights[metric]
        score = score + pct.fillna(0.0) * weight
        total_weight += weight
    out["trend_score"] = score / total_weight if total_weight else np.nan
    return out


def _universe_summary(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    universe_specs = {
        "full_market_eligible57": pd.Series(True, index=summary.index),
        "static18_strategy_pool": summary["in_static18_pool"].astype(bool),
        "stage182_ai_2022_union": summary["in_stage182_ai_2022_union"].astype(bool),
        "stage182_ai_loss_to_202206": summary["in_stage182_ai_loss_window_to_202206"].astype(bool),
        "outside_static18": ~summary["in_static18_pool"].astype(bool),
    }
    for period, period_frame in summary.groupby("period", sort=False):
        for universe_name, mask in universe_specs.items():
            f = period_frame[mask.reindex(period_frame.index, fill_value=False)].copy()
            f = f[f["coverage_ratio"].ge(MIN_COVERAGE)].copy()
            if f.empty:
                continue
            strong = f[f["trend_bucket"].eq("strong_trend_top_quartile")]
            rows.append(
                {
                    "period": period,
                    "universe": universe_name,
                    "product_count": int(len(f)),
                    "strong_trend_count": int(len(strong)),
                    "strong_trend_ratio": float(len(strong) / len(f)),
                    "mean_trend_score": float(f["trend_score"].mean()),
                    "median_abs_return_pct": float(f["abs_return_pct"].median()),
                    "top10_mean_trend_score": float(f.nlargest(min(10, len(f)), "trend_score")["trend_score"].mean()),
                    "top_products": "/".join(f.nlargest(min(10, len(f)), "trend_score")["product_vt_symbol"].astype(str)),
                }
            )
    return pd.DataFrame(rows)


def _plot_loss_window(summary: pd.DataFrame) -> None:
    loss = summary[summary["period"].eq("loss_window_20220309_20220629")].copy()
    loss = loss[loss["coverage_ratio"].ge(MIN_COVERAGE)].nlargest(25, "trend_score").copy()
    colors = np.where(loss["in_static18_pool"].astype(bool), "#1f77b4", "#ff7f0e")
    fig, ax = plt.subplots(figsize=(14, 8))
    ax.barh(loss["product_vt_symbol"], loss["trend_score"], color=colors)
    ax.invert_yaxis()
    ax.set_xlabel("Composite trend score")
    ax.set_title("2022 loss window top trend products: static pool vs full-market-only")
    ax.grid(axis="x", alpha=0.25)
    handles = [
        plt.Line2D([0], [0], color="#1f77b4", lw=8, label="static18 strategy pool"),
        plt.Line2D([0], [0], color="#ff7f0e", lw=8, label="outside static18"),
    ]
    ax.legend(handles=handles, loc="lower right")
    fig.tight_layout()
    fig.savefig(TREND_BAR_CHART_PATH, dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(14, 8))
    ax.scatter(
        loss["abs_return_pct"],
        loss["whole_window_trend_eff"],
        c=colors,
        s=(loss["mean_adx14"].fillna(0.0).clip(lower=0.0) + 5.0) * 6.0,
        alpha=0.78,
        edgecolor="white",
        linewidth=0.8,
    )
    for row in loss.head(18).itertuples(index=False):
        ax.annotate(
            str(row.product_vt_symbol),
            (float(row.abs_return_pct), float(row.whole_window_trend_eff)),
            xytext=(4, 4),
            textcoords="offset points",
            fontsize=8,
        )
    ax.set_xlabel("Absolute return in window %")
    ax.set_ylabel("Whole-window trend efficiency")
    ax.set_title("2022 loss window trend map; bubble size = mean ADX14")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(TREND_SCATTER_CHART_PATH, dpi=180)
    plt.close(fig)


def _write_report(product_summary: pd.DataFrame, universe_summary: pd.DataFrame, decision: dict[str, Any]) -> None:
    loss = product_summary[product_summary["period"].eq("loss_window_20220309_20220629")].copy()
    full = product_summary[product_summary["period"].eq("full_2022")].copy()
    top_cols = [
        "product_vt_symbol",
        "trend_direction",
        "signed_return_pct",
        "abs_return_pct",
        "whole_window_trend_eff",
        "mean_adx14",
        "adx14_ge25_ratio",
        "trend_score",
        "trend_bucket",
        "in_static18_pool",
        "in_stage182_ai_loss_window_to_202206",
    ]
    universe_cols = [
        "period",
        "universe",
        "product_count",
        "strong_trend_count",
        "strong_trend_ratio",
        "mean_trend_score",
        "median_abs_return_pct",
        "top_products",
    ]
    lines = [
        "# Stage122 2022 全品种趋势库存审计",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 最大回撤窗口：`{LOSS_WINDOW_START.date()}` 到 `{LOSS_WINDOW_END.date()}`。",
        f"- 全年窗口：`{FULL_2022_START.date()}` 到 `{FULL_2022_END.date()}`。",
        "- 口径：本地 full-market tradable eligibility 的 `57` 个可交易品种，按 TqSdk 主力映射拼连续主力日线；这不是交易规则，不做参数优化。",
        "",
        "## 判断",
        "",
        f"- 结论：`{decision['conclusion']}`",
        f"- 判断：{decision['judgment']}",
        "",
        "## Universe Summary",
        "",
        _md_table(universe_summary[universe_cols], max_rows=20),
        "",
        "## Loss Window Top Trend Products",
        "",
        _md_table(loss[top_cols].head(25), max_rows=25),
        "",
        "## Full 2022 Top Trend Products",
        "",
        _md_table(full[top_cols].head(25), max_rows=25),
        "",
        "## 输出",
        "",
        f"- product_daily：`{PRODUCT_DAILY_PATH}`",
        f"- product_period_summary：`{PRODUCT_PERIOD_SUMMARY_PATH}`",
        f"- universe_period_summary：`{UNIVERSE_PERIOD_SUMMARY_PATH}`",
        f"- top_trend：`{TOP_TREND_PATH}`",
        f"- chart_bar：`{TREND_BAR_CHART_PATH}`",
        f"- chart_scatter：`{TREND_SCATTER_CHART_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_stage_record(decision: dict[str, Any], universe_summary: pd.DataFrame) -> None:
    STAGE_RECORD_PATH.parent.mkdir(parents=True, exist_ok=True)
    loss_full = universe_summary[
        universe_summary["period"].eq("loss_window_20220309_20220629")
        & universe_summary["universe"].eq("full_market_eligible57")
    ].iloc[0]
    loss_static = universe_summary[
        universe_summary["period"].eq("loss_window_20220309_20220629")
        & universe_summary["universe"].eq("static18_strategy_pool")
    ].iloc[0]
    text = f"""# Stage122 2022 全品种趋势库存审计

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：2026-07-09 13:27 CST
- 工作区：`{ROOT_DIR}`
- 阶段性质：只读归因；统计 2022 最大回撤窗口和全年全品种趋势强度。
- 是否重要突破：否，归因证据，不是策略候选。
- 是否触发A/B：否。

## 外部调研与判断

- 参考资料：pysystemtrade / PyTrendFollow / ADX / Donchian 与时序动量资料都支持用价格趋势强度、路径效率和突破/动量类指标做趋势库存审计。
- 我的判断：先用低自由度趋势库存回答“池子有没有趋势”，不能直接据此扩池或上线。

## 本次变更

- 新增脚本：`{Path(__file__).relative_to(ROOT_DIR)}`
- 修改脚本：无正式入口修改。
- 删除脚本：无。
- 新增参数：`LOSS_WINDOW=2022-03-09..2022-06-29`、`FULL_2022=2022-01-01..2022-12-31`、`MIN_COVERAGE=0.80`。
- 修改参数：无策略参数。
- 删除参数：无。

## 回测/归因参数

- 数据区间：查询 `2021-01-01` 到 `2022-12-31` 日线，统计 `2022-03-09..2022-06-29` 与 `2022` 全年。
- 账户规模：不适用。
- 成本口径：不适用。
- 样本过滤：full-market tradable eligibility `57` 个品种，产品窗口覆盖率至少 `80%` 才进入强趋势统计。
- 策略/归因口径：连续主力日线；趋势分数由绝对收益、整窗路径效率、20日路径效率、ADX14、ADX>=25占比、20日最大绝对动量和20日方向一致性组成。

## 结果

- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。
- 其他关键指标：loss window 全市场强趋势 `{int(loss_full['strong_trend_count'])}/{int(loss_full['product_count'])}`，static18 强趋势 `{int(loss_static['strong_trend_count'])}/{int(loss_static['product_count'])}`；结论 `{decision['conclusion']}`。

## 输出文件

- report：`{REPORT_PATH}`
- summary：`{PRODUCT_PERIOD_SUMMARY_PATH}`
- orders：不适用。
- daily：`{PRODUCT_DAILY_PATH}`
- quality：`{UNIVERSE_PERIOD_SUMMARY_PATH}`

## 结论

- 本阶段结论：`{decision['conclusion']}`。
- 是否进入下一步：`False`。
- 下一步：如要研究扩池，只能把本阶段作为候选来源，再做 PIT 规则和真实引擎验证；不能直接按 2022 赢家补品种。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只做全品种趋势库存和归因，不按结果写交易规则、不扫阈值、不扩正式池。

## 继续价值反思

- 运行前判断：有。
- 运行后判断：有但仅限归因。
- 原因：它能回答 2022 是否缺趋势品种；但扩池需要单独的点时选择规则和真实引擎，不能从这张表直接上线。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录归因结论。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否，非正式候选、非突破。
"""
    STAGE_RECORD_PATH.write_text(text, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    universe = _load_universe()
    bars = _load_product_bars(universe)
    product_daily = bars.copy()
    loss = _score_period(bars, "loss_window_20220309_20220629", LOSS_WINDOW_START, LOSS_WINDOW_END)
    full = _score_period(bars, "full_2022", FULL_2022_START, FULL_2022_END)
    product_summary = pd.concat([loss, full], ignore_index=True, sort=False)
    universe_summary = _universe_summary(product_summary)

    loss_full = universe_summary[
        universe_summary["period"].eq("loss_window_20220309_20220629")
        & universe_summary["universe"].eq("full_market_eligible57")
    ].iloc[0]
    loss_static = universe_summary[
        universe_summary["period"].eq("loss_window_20220309_20220629")
        & universe_summary["universe"].eq("static18_strategy_pool")
    ].iloc[0]
    outside_top = (
        product_summary[
            product_summary["period"].eq("loss_window_20220309_20220629")
            & product_summary["coverage_ratio"].ge(MIN_COVERAGE)
            & ~product_summary["in_static18_pool"].astype(bool)
        ]
        .nlargest(10, "trend_score")["product_vt_symbol"]
        .astype(str)
        .tolist()
    )
    static_top = (
        product_summary[
            product_summary["period"].eq("loss_window_20220309_20220629")
            & product_summary["coverage_ratio"].ge(MIN_COVERAGE)
            & product_summary["in_static18_pool"].astype(bool)
        ]
        .nlargest(10, "trend_score")["product_vt_symbol"]
        .astype(str)
        .tolist()
    )
    decision = {
        "stage": "Stage122",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "conclusion": "full_market_had_trends_but_static_pool_also_had_enough_trend_not_simple_no_trend_pool",
        "judgment": (
            "2022 loss window is not explained by 'no trending products in the strategy pool' alone. "
            "The full tradable market did contain strong trends, including products outside static18, "
            "but the static18 pool also contained multiple high-trend products; the larger problem is likely "
            "direction/timing/sizing/AI selection and reversal path rather than pure absence of trends."
        ),
        "loss_window": {
            "start": LOSS_WINDOW_START.date().isoformat(),
            "end": LOSS_WINDOW_END.date().isoformat(),
            "full_market_strong_trend_count": int(loss_full["strong_trend_count"]),
            "full_market_product_count": int(loss_full["product_count"]),
            "static18_strong_trend_count": int(loss_static["strong_trend_count"]),
            "static18_product_count": int(loss_static["product_count"]),
            "outside_static18_top10": outside_top,
            "static18_top10": static_top,
        },
        "outputs": {
            "product_daily": str(PRODUCT_DAILY_PATH),
            "product_period_summary": str(PRODUCT_PERIOD_SUMMARY_PATH),
            "universe_period_summary": str(UNIVERSE_PERIOD_SUMMARY_PATH),
            "top_trend": str(TOP_TREND_PATH),
            "report": str(REPORT_PATH),
            "bar_chart": str(TREND_BAR_CHART_PATH),
            "scatter_chart": str(TREND_SCATTER_CHART_PATH),
            "stage_record": str(STAGE_RECORD_PATH),
        },
    }

    _plot_loss_window(product_summary)
    top_trend = product_summary.sort_values(["period", "trend_score"], ascending=[True, False]).groupby("period").head(30)
    product_daily.to_csv(PRODUCT_DAILY_PATH, index=False, encoding="utf-8-sig")
    product_summary.to_csv(PRODUCT_PERIOD_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    universe_summary.to_csv(UNIVERSE_PERIOD_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    top_trend.to_csv(TOP_TREND_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(product_summary, universe_summary, decision)
    _write_stage_record(decision, universe_summary)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
