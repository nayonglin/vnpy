from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sqlite3
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PROJECT_DIR.parents[1]
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
DATABASE_PATH = PROJECT_ROOT / ".vntrader" / "database.db"
CONTRACT_ROOT = PROJECT_DIR / "downloaded_futures" / "tqsdk_daily_2010_2026_04"

SOURCE_PREFIX = "qmt_roll_stage719_official_winner_trade_forensics"
SOURCE_TAG = "stage719_official_winner_trade_forensics_v1"
SOURCE_CLOSED_LOTS_PATH = OUTPUT_DIR / f"{SOURCE_PREFIX}_closed_lots_{SOURCE_TAG}.csv"

MODEL_TAG = "stage733_shadowless_preentry_quality_v1"
OUTPUT_PREFIX = "qmt_roll_stage733_shadowless_preentry_quality"
LINE_ID = "futures_trend_winner_trade_forensics"

ENRICHED_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_enriched_closed_lots_{MODEL_TAG}.csv"
FEATURE_METRICS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_metrics_{MODEL_TAG}.csv"
YEAR_DETAIL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_detail_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

MIN_RELIABLE_ROWS = 30
MIN_RELIABLE_YEARS = 5
MIN_RELIABLE_PRODUCTS = 8
MAX_DOMINANT_PRODUCT_SHARE = 0.30
MIN_AVG_R_LIFT = 0.50
MIN_BIG_WINNER_RATE_LIFT_PP = 5.0
MIN_POSITIVE_R_YEARS = 5
MAX_BAD_RATE_PCT = 55.0

FEATURE_BUCKETS = [
    "pre1_total_wick_le20",
    "pre1_total_wick_le30",
    "pre1_both_wicks_le10",
    "pre1_adverse_wick_le10",
    "pre1_directional_close_strength_ge80",
    "pre1_marubozu_directional",
    "pre2_avg_total_wick_le30",
    "pre3_avg_total_wick_le30",
    "pre5_avg_total_wick_le30",
    "pre3_short_wick_count_ge2",
    "pre5_short_wick_count_ge3",
    "pre3_marubozu_count_ge1",
    "pre5_marubozu_count_ge2",
]


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if np.isnan(value) or np.isinf(value):
            return None
        return float(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if pd.isna(value):
        return None
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_无记录_"
    data = frame.copy()
    if max_rows is not None:
        data = data.head(max_rows)
    for column in data.columns:
        if pd.api.types.is_float_dtype(data[column]):
            data[column] = data[column].map(lambda value: "" if pd.isna(value) else f"{value:.4f}")
    data = data.fillna("")
    headers = [str(column) for column in data.columns]
    rows = [[str(value) for value in row] for row in data.to_numpy()]
    widths = [len(header) for header in headers]
    for row in rows:
        widths = [max(width, len(cell)) for width, cell in zip(widths, row)]
    line = "| " + " | ".join(header.ljust(width) for header, width in zip(headers, widths)) + " |"
    sep = "| " + " | ".join("-" * width for width in widths) + " |"
    body = ["| " + " | ".join(cell.ljust(width) for cell, width in zip(row, widths)) + " |" for row in rows]
    return "\n".join([line, sep, *body])


def _parse_vt(vt_symbol: str) -> tuple[str, str] | None:
    if not isinstance(vt_symbol, str) or "." not in vt_symbol:
        return None
    symbol, exchange = vt_symbol.split(".", 1)
    return symbol, exchange


def _load_closed_lots() -> pd.DataFrame:
    if not SOURCE_CLOSED_LOTS_PATH.exists():
        raise FileNotFoundError(SOURCE_CLOSED_LOTS_PATH)
    data = pd.read_csv(SOURCE_CLOSED_LOTS_PATH, encoding="utf-8-sig")
    for column in [
        "entry_date",
        "exit_date",
    ]:
        data[column] = pd.to_datetime(data[column], errors="coerce").dt.normalize()
    for column in [
        "realized_pnl",
        "risk_amount",
        "r_multiple",
        "mfe_r",
        "mae_r",
        "exit_efficiency",
        "winner",
        "big_winner",
        "quality_winner",
        "big_winner_threshold_r",
        "risk_multiplier",
        "loss_streak",
        "volume",
    ]:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    return data.sort_values(["entry_date", "lot_id"]).reset_index(drop=True)


def _load_bars_from_db(vt_symbol: str) -> pd.DataFrame:
    if not DATABASE_PATH.exists():
        return pd.DataFrame()
    parsed = _parse_vt(vt_symbol)
    if parsed is None:
        return pd.DataFrame()
    symbol, exchange = parsed
    query = """
        SELECT
            datetime AS date,
            open_price,
            high_price,
            low_price,
            close_price,
            volume,
            open_interest
        FROM dbbardata
        WHERE symbol = ? AND exchange = ? AND interval = 'd'
        ORDER BY datetime
    """
    with sqlite3.connect(DATABASE_PATH) as con:
        frame = pd.read_sql_query(query, con, params=(symbol, exchange))
    if frame.empty:
        return pd.DataFrame()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    return frame


def _load_bars_from_csv(vt_symbol: str) -> pd.DataFrame:
    parsed = _parse_vt(vt_symbol)
    if parsed is None:
        return pd.DataFrame()
    symbol, exchange = parsed
    path = CONTRACT_ROOT / exchange / f"{symbol}.csv"
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path, encoding="utf-8-sig")
    if frame.empty:
        return pd.DataFrame()
    if "trade_date" in frame.columns:
        frame["date"] = pd.to_datetime(frame["trade_date"], errors="coerce").dt.normalize()
    elif "datetime" in frame.columns:
        frame["date"] = pd.to_datetime(frame["datetime"], errors="coerce").dt.normalize()
    else:
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    rename_map = {
        "open": "open_price",
        "high": "high_price",
        "low": "low_price",
        "close": "close_price",
    }
    for old, new in rename_map.items():
        if old in frame.columns and new not in frame.columns:
            frame[new] = frame[old]
    return frame


def _load_contract_bars(vt_symbol: str) -> pd.DataFrame:
    frame = _load_bars_from_db(vt_symbol)
    source = "db"
    if frame.empty:
        frame = _load_bars_from_csv(vt_symbol)
        source = "csv"
    if frame.empty:
        return pd.DataFrame()
    for column in ["open_price", "high_price", "low_price", "close_price", "volume", "open_interest"]:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = (
        frame.dropna(subset=["date", "open_price", "high_price", "low_price", "close_price"])
        .drop_duplicates("date")
        .sort_values("date")
        .reset_index(drop=True)
    )
    frame["bar_source"] = source
    return frame


def _add_candle_features(bars: pd.DataFrame, direction: str) -> pd.DataFrame:
    data = bars.copy()
    open_price = data["open_price"].astype("float64")
    high = data["high_price"].astype("float64")
    low = data["low_price"].astype("float64")
    close = data["close_price"].astype("float64")
    range_price = (high - low).replace(0.0, np.nan)
    upper = (high - pd.concat([open_price, close], axis=1).max(axis=1)).clip(lower=0.0)
    lower = (pd.concat([open_price, close], axis=1).min(axis=1) - low).clip(lower=0.0)
    body = (close - open_price).abs()
    data["range_pct"] = range_price / close.replace(0.0, np.nan)
    data["body_pct_of_range"] = body / range_price
    data["upper_wick_pct_of_range"] = upper / range_price
    data["lower_wick_pct_of_range"] = lower / range_price
    data["total_wick_pct_of_range"] = (upper + lower) / range_price
    close_position = (close - low) / range_price
    data["close_position"] = close_position
    if direction == "long":
        data["favorable_wick_pct_of_range"] = data["lower_wick_pct_of_range"]
        data["adverse_wick_pct_of_range"] = data["upper_wick_pct_of_range"]
        data["directional_close_strength"] = close_position
        data["directional_bar"] = (close > open_price).astype("int64")
    elif direction == "short":
        data["favorable_wick_pct_of_range"] = data["upper_wick_pct_of_range"]
        data["adverse_wick_pct_of_range"] = data["lower_wick_pct_of_range"]
        data["directional_close_strength"] = 1.0 - close_position
        data["directional_bar"] = (close < open_price).astype("int64")
    else:
        data["favorable_wick_pct_of_range"] = np.nan
        data["adverse_wick_pct_of_range"] = np.nan
        data["directional_close_strength"] = np.nan
        data["directional_bar"] = 0
    data["short_total_wick_bar"] = (data["total_wick_pct_of_range"] <= 0.20).astype("int64")
    data["both_wicks_short_bar"] = (
        (data["upper_wick_pct_of_range"] <= 0.10) & (data["lower_wick_pct_of_range"] <= 0.10)
    ).astype("int64")
    data["adverse_wick_short_bar"] = (data["adverse_wick_pct_of_range"] <= 0.10).astype("int64")
    data["marubozu_directional_bar"] = (
        (data["total_wick_pct_of_range"] <= 0.20)
        & (data["directional_close_strength"] >= 0.80)
        & (data["directional_bar"] == 1)
    ).astype("int64")
    return data


def _window_stats(bars: pd.DataFrame, entry_date: pd.Timestamp, direction: str, window: int) -> dict[str, Any]:
    prior = bars[bars["date"] < entry_date].tail(window).copy()
    if prior.empty:
        return {}
    featured = _add_candle_features(prior, direction)
    result: dict[str, Any] = {
        f"pre{window}_available_bars": int(len(featured)),
        f"pre{window}_last_bar_date": featured["date"].iloc[-1].strftime("%Y-%m-%d"),
        f"pre{window}_bar_source": str(featured["bar_source"].iloc[-1]),
        f"pre{window}_avg_total_wick_pct": float(featured["total_wick_pct_of_range"].mean()),
        f"pre{window}_avg_adverse_wick_pct": float(featured["adverse_wick_pct_of_range"].mean()),
        f"pre{window}_avg_favorable_wick_pct": float(featured["favorable_wick_pct_of_range"].mean()),
        f"pre{window}_avg_body_pct": float(featured["body_pct_of_range"].mean()),
        f"pre{window}_avg_directional_close_strength": float(featured["directional_close_strength"].mean()),
        f"pre{window}_short_wick_count": int(featured["short_total_wick_bar"].sum()),
        f"pre{window}_both_wicks_short_count": int(featured["both_wicks_short_bar"].sum()),
        f"pre{window}_adverse_wick_short_count": int(featured["adverse_wick_short_bar"].sum()),
        f"pre{window}_marubozu_directional_count": int(featured["marubozu_directional_bar"].sum()),
        f"pre{window}_directional_bar_count": int(featured["directional_bar"].sum()),
    }
    if window == 1:
        last = featured.iloc[-1]
        for column in [
            "open_price",
            "high_price",
            "low_price",
            "close_price",
            "range_pct",
            "body_pct_of_range",
            "upper_wick_pct_of_range",
            "lower_wick_pct_of_range",
            "total_wick_pct_of_range",
            "favorable_wick_pct_of_range",
            "adverse_wick_pct_of_range",
            "directional_close_strength",
            "directional_bar",
            "short_total_wick_bar",
            "both_wicks_short_bar",
            "adverse_wick_short_bar",
            "marubozu_directional_bar",
        ]:
            result[f"pre1_{column}"] = float(last[column])
    return result


def _enrich_lots(lots: pd.DataFrame) -> pd.DataFrame:
    bar_cache: dict[str, pd.DataFrame] = {}
    records: list[dict[str, Any]] = []
    for row in lots.itertuples(index=False):
        record = row._asdict()
        vt_symbol = str(row.vt_symbol)
        bars = bar_cache.get(vt_symbol)
        if bars is None:
            bars = _load_contract_bars(vt_symbol)
            bar_cache[vt_symbol] = bars
        if not bars.empty:
            entry_date = pd.Timestamp(row.entry_date).normalize()
            direction = str(row.direction)
            for window in [1, 2, 3, 5]:
                record.update(_window_stats(bars, entry_date, direction, window))
        records.append(record)
    enriched = pd.DataFrame(records)
    enriched["entry_year"] = pd.to_datetime(enriched["entry_date"]).dt.year

    enriched["pre1_total_wick_le20"] = enriched["pre1_total_wick_pct_of_range"] <= 0.20
    enriched["pre1_total_wick_le30"] = enriched["pre1_total_wick_pct_of_range"] <= 0.30
    enriched["pre1_both_wicks_le10"] = (
        (enriched["pre1_upper_wick_pct_of_range"] <= 0.10)
        & (enriched["pre1_lower_wick_pct_of_range"] <= 0.10)
    )
    enriched["pre1_adverse_wick_le10"] = enriched["pre1_adverse_wick_pct_of_range"] <= 0.10
    enriched["pre1_directional_close_strength_ge80"] = enriched["pre1_directional_close_strength"] >= 0.80
    enriched["pre1_marubozu_directional"] = (
        enriched["pre1_total_wick_le20"]
        & enriched["pre1_directional_close_strength_ge80"]
        & (enriched["pre1_directional_bar"] == 1)
    )
    enriched["pre2_avg_total_wick_le30"] = (
        (enriched["pre2_available_bars"] >= 2) & (enriched["pre2_avg_total_wick_pct"] <= 0.30)
    )
    enriched["pre3_avg_total_wick_le30"] = (
        (enriched["pre3_available_bars"] >= 3) & (enriched["pre3_avg_total_wick_pct"] <= 0.30)
    )
    enriched["pre5_avg_total_wick_le30"] = (
        (enriched["pre5_available_bars"] >= 5) & (enriched["pre5_avg_total_wick_pct"] <= 0.30)
    )
    enriched["pre3_short_wick_count_ge2"] = (
        (enriched["pre3_available_bars"] >= 3) & (enriched["pre3_short_wick_count"] >= 2)
    )
    enriched["pre5_short_wick_count_ge3"] = (
        (enriched["pre5_available_bars"] >= 5) & (enriched["pre5_short_wick_count"] >= 3)
    )
    enriched["pre3_marubozu_count_ge1"] = (
        (enriched["pre3_available_bars"] >= 3) & (enriched["pre3_marubozu_directional_count"] >= 1)
    )
    enriched["pre5_marubozu_count_ge2"] = (
        (enriched["pre5_available_bars"] >= 5) & (enriched["pre5_marubozu_directional_count"] >= 2)
    )
    return enriched


def _baseline_metrics(data: pd.DataFrame) -> dict[str, float]:
    valid = data.dropna(subset=["r_multiple"]).copy()
    return {
        "rows": float(len(valid)),
        "avg_r": float(valid["r_multiple"].mean()),
        "median_r": float(valid["r_multiple"].median()),
        "winner_rate_pct": float((valid["realized_pnl"] > 0).mean() * 100.0),
        "big_winner_rate_pct": float(valid["big_winner"].fillna(0).mean() * 100.0),
        "quality_winner_rate_pct": float(valid["quality_winner"].fillna(0).mean() * 100.0),
        "bad_rate_pct": float((valid["r_multiple"] <= -1.0).mean() * 100.0),
        "sum_r": float(valid["r_multiple"].sum()),
    }


def _feature_year_detail(data: pd.DataFrame, feature: str) -> pd.DataFrame:
    selected = data[data[feature].fillna(False)].copy()
    if selected.empty:
        return pd.DataFrame()
    return (
        selected.groupby("entry_year")
        .agg(
            rows=("lot_id", "count"),
            products=("product", "nunique"),
            directions=("direction", "nunique"),
            avg_r=("r_multiple", "mean"),
            sum_r=("r_multiple", "sum"),
            winners=("winner", "sum"),
            big_winners=("big_winner", "sum"),
            pnl=("realized_pnl", "sum"),
        )
        .reset_index()
        .assign(feature=feature)
    )


def _build_feature_metrics(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, float]]:
    valid = data.dropna(subset=["r_multiple", "pre1_total_wick_pct_of_range"]).copy()
    baseline = _baseline_metrics(valid)
    metric_rows: list[dict[str, Any]] = []
    year_frames: list[pd.DataFrame] = []
    for feature in FEATURE_BUCKETS:
        selected = valid[valid[feature].fillna(False)].copy()
        if selected.empty:
            continue
        unselected = valid[~valid[feature].fillna(False)].copy()
        product_share = selected["product"].value_counts(normalize=True).iloc[0]
        years = int(selected["entry_year"].nunique())
        products = int(selected["product"].nunique())
        directions = int(selected["direction"].nunique())
        year_detail = _feature_year_detail(valid, feature)
        if not year_detail.empty:
            year_frames.append(year_detail)
        positive_r_years = int((year_detail["sum_r"] > 0).sum()) if not year_detail.empty else 0
        avg_r = float(selected["r_multiple"].mean())
        median_r = float(selected["r_multiple"].median())
        big_rate = float(selected["big_winner"].fillna(0).mean() * 100.0)
        bad_rate = float((selected["r_multiple"] <= -1.0).mean() * 100.0)
        metric_rows.append(
            {
                "feature": feature,
                "rows": int(len(selected)),
                "coverage_pct": len(selected) / len(valid) * 100.0,
                "years": years,
                "products": products,
                "directions": directions,
                "dominant_product_share_pct": product_share * 100.0,
                "winner_rate_pct": float((selected["realized_pnl"] > 0).mean() * 100.0),
                "big_winner_rate_pct": big_rate,
                "quality_winner_rate_pct": float(selected["quality_winner"].fillna(0).mean() * 100.0),
                "bad_rate_pct": bad_rate,
                "avg_r": avg_r,
                "median_r": median_r,
                "sum_r": float(selected["r_multiple"].sum()),
                "avg_r_lift": avg_r - baseline["avg_r"],
                "median_r_lift": median_r - baseline["median_r"],
                "big_winner_rate_lift_pp": big_rate - baseline["big_winner_rate_pct"],
                "bad_rate_lift_pp": bad_rate - baseline["bad_rate_pct"],
                "unselected_rows": int(len(unselected)),
                "unselected_avg_r": float(unselected["r_multiple"].mean()) if not unselected.empty else np.nan,
                "unselected_big_winner_rate_pct": (
                    float(unselected["big_winner"].fillna(0).mean() * 100.0) if not unselected.empty else np.nan
                ),
                "positive_r_years": positive_r_years,
                "passes_reliable_gate": bool(
                    len(selected) >= MIN_RELIABLE_ROWS
                    and years >= MIN_RELIABLE_YEARS
                    and products >= MIN_RELIABLE_PRODUCTS
                    and product_share <= MAX_DOMINANT_PRODUCT_SHARE
                    and directions >= 2
                    and (avg_r - baseline["avg_r"]) >= MIN_AVG_R_LIFT
                    and (big_rate - baseline["big_winner_rate_pct"]) >= MIN_BIG_WINNER_RATE_LIFT_PP
                    and positive_r_years >= MIN_POSITIVE_R_YEARS
                    and bad_rate <= MAX_BAD_RATE_PCT
                ),
            }
        )
    metrics = pd.DataFrame(metric_rows).sort_values(
        ["passes_reliable_gate", "avg_r_lift", "big_winner_rate_lift_pp"], ascending=[False, False, False]
    )
    year_detail = pd.concat(year_frames, ignore_index=True) if year_frames else pd.DataFrame()
    return metrics, year_detail, baseline


def _plot_feature_metrics(metrics: pd.DataFrame, baseline: dict[str, float]) -> None:
    if metrics.empty:
        return
    top = metrics.sort_values("avg_r_lift", ascending=False).head(10).copy()
    plt.figure(figsize=(13, 7))
    colors = ["#2ca02c" if value else "#1f77b4" for value in top["passes_reliable_gate"]]
    plt.barh(top["feature"], top["avg_r_lift"], color=colors)
    plt.axvline(0.0, color="#666666", linewidth=1)
    plt.axvline(MIN_AVG_R_LIFT, color="#cc3333", linewidth=1, linestyle="--", label="avg R lift gate")
    plt.title("Stage733 pre-entry short-wick feature avg R lift")
    plt.xlabel(f"Avg R lift vs baseline avg R {baseline['avg_r']:.3f}")
    plt.gca().invert_yaxis()
    plt.grid(axis="x", alpha=0.25)
    plt.legend(loc="lower right")
    plt.tight_layout()
    plt.savefig(CHART_PATH, dpi=160)
    plt.close()


def _build_report(enriched: pd.DataFrame, metrics: pd.DataFrame, year_detail: pd.DataFrame, baseline: dict[str, float]) -> str:
    pass_df = metrics[metrics["passes_reliable_gate"]].copy()
    top_cols = [
        "feature",
        "rows",
        "coverage_pct",
        "years",
        "products",
        "directions",
        "dominant_product_share_pct",
        "avg_r",
        "avg_r_lift",
        "median_r",
        "big_winner_rate_pct",
        "big_winner_rate_lift_pp",
        "bad_rate_pct",
        "positive_r_years",
        "passes_reliable_gate",
    ]
    sample_cols = [
        "lot_id",
        "vt_symbol",
        "direction",
        "entry_date",
        "exit_date",
        "r_multiple",
        "mfe_r",
        "mae_r",
        "realized_pnl",
        "pre1_last_bar_date",
        "pre1_total_wick_pct_of_range",
        "pre1_adverse_wick_pct_of_range",
        "pre1_directional_close_strength",
        "pre1_marubozu_directional",
    ]
    strong_sample = enriched[enriched["pre1_marubozu_directional"].fillna(False)].copy()
    strong_sample = strong_sample.sort_values("r_multiple", ascending=False).head(20)
    lines = [
        "# Stage733 入场前短影线质量特征审计",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} CST",
        f"- 研究线：`{LINE_ID}`",
        f"- 数据源：`{SOURCE_CLOSED_LOTS_PATH.name}`",
        "- 口径：只读正式版 Stage719 closed lots；对每笔实际入场只使用 `entry_date` 之前已完成的合约日线，不使用入场日之后信息。",
        "- 特征：预声明短影线/Marubozu-like 桶，不做小数阈值扫描。",
        "",
        "## Baseline",
        "",
        _md_table(pd.DataFrame([baseline])),
        "",
        "## 可靠性闸门",
        "",
        f"- rows >= {MIN_RELIABLE_ROWS}",
        f"- years >= {MIN_RELIABLE_YEARS}",
        f"- products >= {MIN_RELIABLE_PRODUCTS}",
        f"- dominant product share <= {MAX_DOMINANT_PRODUCT_SHARE:.0%}",
        "- directions >= 2",
        f"- avg R lift >= {MIN_AVG_R_LIFT:.2f}",
        f"- big winner rate lift >= {MIN_BIG_WINNER_RATE_LIFT_PP:.1f}pp",
        f"- positive R years >= {MIN_POSITIVE_R_YEARS}",
        f"- bad rate <= {MAX_BAD_RATE_PCT:.1f}%",
        "",
        "## 通过特征",
        "",
        _md_table(pass_df[top_cols] if not pass_df.empty else pass_df),
        "",
        "## Top 特征指标",
        "",
        _md_table(metrics[top_cols], max_rows=20),
        "",
        "## pre1_marubozu_directional 高 R 样本",
        "",
        _md_table(strong_sample[sample_cols], max_rows=20),
        "",
        "## 年度明细 Top",
        "",
        _md_table(year_detail.sort_values(["feature", "entry_year"]).head(80) if not year_detail.empty else year_detail),
        "",
        "## 结论",
        "",
    ]
    if pass_df.empty:
        lines.extend(
            [
                "- 没有短影线特征通过完整可靠性闸门。",
                "- 当前可以把短影线视作解释性/观察性特征，但不能直接用于所有交易扩大风险资金。",
            ]
        )
    else:
        lines.extend(
            [
                f"- 有 {len(pass_df)} 个特征通过完整可靠性闸门，可以进入下一步 A/C 风险放大压力测试。",
                "- 下一步仍不能直接合入正式版，必须先验证全周期、多起点、成本压力和弱窗口。",
            ]
        )
    lines.extend(
        [
            "",
            "## 过拟合反思",
            "",
            "- 本阶段只读审计，不改仓位，不构成交易化过拟合。",
            "- 若为了让短影线通过而继续扫 `0.15/0.18/0.25` 或叠加品种、年份、方向条件，会变成高风险过拟合。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    lots = _load_closed_lots()
    enriched = _enrich_lots(lots)
    metrics, year_detail, baseline = _build_feature_metrics(enriched)
    _plot_feature_metrics(metrics, baseline)

    enriched.to_csv(ENRICHED_PATH, index=False, encoding="utf-8-sig")
    metrics.to_csv(FEATURE_METRICS_PATH, index=False, encoding="utf-8-sig")
    year_detail.to_csv(YEAR_DETAIL_PATH, index=False, encoding="utf-8-sig")
    REPORT_PATH.write_text(_build_report(enriched, metrics, year_detail, baseline), encoding="utf-8")

    pass_df = metrics[metrics["passes_reliable_gate"]].copy()
    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "source_closed_lots_path": str(SOURCE_CLOSED_LOTS_PATH),
        "closed_lots": int(len(lots)),
        "feature_valid_lots": int(enriched["pre1_total_wick_pct_of_range"].notna().sum()),
        "baseline": baseline,
        "passed_feature_count": int(len(pass_df)),
        "passed_features": pass_df["feature"].tolist(),
        "decision": (
            "shadowless_feature_can_enter_ac_backtest"
            if not pass_df.empty
            else "no_reliable_shadowless_risk_expansion_feature_found"
        ),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(metrics.head(20).to_string(index=False))


if __name__ == "__main__":
    main()
