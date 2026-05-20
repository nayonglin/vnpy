from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

from run_qmt_no_lower_shadow_swing_backtest import (
    DEFAULT_MAPPING_PATH,
    DEFAULT_OUTPUT_PREFIX,
    DEFAULT_UNIVERSE_PATH,
    OUTPUT_DIR,
    _load_bar_cache,
)


MODEL_TAG = "no_lower_shadow_swing_failure_attribution_v1"
OUTPUT_PREFIX = "qmt_no_lower_shadow_swing_failure_attribution"

SOURCE_PREFIX = DEFAULT_OUTPUT_PREFIX
CANDIDATES_PATH = OUTPUT_DIR / f"{SOURCE_PREFIX}_candidates.csv"
ROUNDTRIPS_PATH = OUTPUT_DIR / f"{SOURCE_PREFIX}_roundtrips.csv"
TRADES_PATH = OUTPUT_DIR / f"{SOURCE_PREFIX}_trades.csv"

EVENTS_CSV = OUTPUT_DIR / f"{OUTPUT_PREFIX}_events_{MODEL_TAG}.csv"
FEATURE_CONTRAST_CSV = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_contrast_{MODEL_TAG}.csv"
BUCKET_SUMMARY_CSV = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_summary_{MODEL_TAG}.csv"
PRODUCT_SUMMARY_CSV = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_summary_{MODEL_TAG}.csv"
SECTOR_SUMMARY_CSV = OUTPUT_DIR / f"{OUTPUT_PREFIX}_sector_summary_{MODEL_TAG}.csv"
YEAR_SUMMARY_CSV = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_summary_{MODEL_TAG}.csv"
SKIP_SUMMARY_CSV = OUTPUT_DIR / f"{OUTPUT_PREFIX}_skip_summary_{MODEL_TAG}.csv"
SUMMARY_JSON = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_MD = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


SECTOR_MAP: dict[str, str] = {
    "AP.CZCE": "soft_agri",
    "CF.CZCE": "soft_agri",
    "CY.CZCE": "chemicals_building",
    "FG.CZCE": "chemicals_building",
    "IH.CFFEX": "equity_index",
    "MA.CZCE": "chemicals_building",
    "OI.CZCE": "agri_oils",
    "PF.CZCE": "chemicals_building",
    "PK.CZCE": "soft_agri",
    "PR.CZCE": "grain",
    "PX.CZCE": "chemicals_building",
    "SA.CZCE": "chemicals_building",
    "SF.CZCE": "black_ferrous",
    "SH.CZCE": "chemicals_building",
    "SM.CZCE": "black_ferrous",
    "SR.CZCE": "soft_agri",
    "TA.CZCE": "chemicals_building",
    "UR.CZCE": "chemicals_building",
    "a.DCE": "agri_oils",
    "ag.SHFE": "precious_nonferrous",
    "al.SHFE": "precious_nonferrous",
    "ao.SHFE": "precious_nonferrous",
    "au.SHFE": "precious_nonferrous",
    "bc.INE": "precious_nonferrous",
    "br.SHFE": "chemicals_building",
    "bu.SHFE": "energy_oil",
    "c.DCE": "grain",
    "cs.DCE": "grain",
    "cu.SHFE": "precious_nonferrous",
    "eb.DCE": "chemicals_building",
    "fb.DCE": "chemicals_building",
    "fu.SHFE": "energy_oil",
    "hc.SHFE": "black_ferrous",
    "i.DCE": "black_ferrous",
    "j.DCE": "black_ferrous",
    "jd.DCE": "livestock",
    "jm.DCE": "black_ferrous",
    "lc.GFEX": "battery_metals",
    "lh.DCE": "livestock",
    "lu.INE": "energy_oil",
    "m.DCE": "agri_oils",
    "ni.SHFE": "precious_nonferrous",
    "nr.INE": "chemicals_building",
    "p.DCE": "agri_oils",
    "pb.SHFE": "precious_nonferrous",
    "pg.DCE": "energy_oil",
    "rb.SHFE": "black_ferrous",
    "rr.DCE": "grain",
    "ru.SHFE": "chemicals_building",
    "sc.INE": "energy_oil",
    "si.GFEX": "black_ferrous",
    "sn.SHFE": "precious_nonferrous",
    "sp.SHFE": "chemicals_building",
    "ss.SHFE": "black_ferrous",
    "v.DCE": "chemicals_building",
    "y.DCE": "agri_oils",
    "zn.SHFE": "precious_nonferrous",
}


NUMERIC_FEATURES: tuple[str, ...] = (
    "entry_gap_vs_signal2_close_pct",
    "entry_open_vs_signal2_high_pct",
    "entry_risk_distance_pct",
    "entry_open_position_in_signal2_range",
    "two_signal_day_return_pct",
    "signal1_body_pct",
    "signal2_body_pct",
    "signal2_close_to_high_pct",
    "entry_day_open_to_low_r",
    "entry_day_range_pct",
    "entry_day_close_return_pct",
    "pre20_return_pct",
    "signal2_volume_ratio_20d",
    "entry_volume_ratio_20d",
    "recent_median_volume",
    "estimated_margin_per_contract",
)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or math.isinf(result):
        return default
    return result


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path)


def _normalize_dates(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    result = df.copy()
    for column in columns:
        if column in result.columns:
            result[column] = pd.to_datetime(result[column]).dt.tz_localize(None).dt.normalize()
    return result


def _sector(product: str) -> str:
    return SECTOR_MAP.get(str(product), "unknown")


def _load_universe_metadata() -> pd.DataFrame:
    df = pd.read_csv(DEFAULT_UNIVERSE_PATH)
    if "eligible" in df.columns:
        df = df[pd.to_numeric(df["eligible"], errors="coerce").fillna(0).astype(int) == 1].copy()
    keep = [
        column
        for column in [
            "product_vt_symbol",
            "recent_median_volume",
            "recent_bar_coverage_ratio",
            "recent_nonzero_volume_ratio",
            "estimated_margin_per_contract",
        ]
        if column in df.columns
    ]
    return df[keep].copy()


def _bar_series(cache: dict[str, dict[pd.Timestamp, Any]], contract: str) -> list[Any]:
    return [cache[contract][date] for date in sorted(cache.get(contract, {}))]


def _bar_lookup(cache: dict[str, dict[pd.Timestamp, Any]], contract: str, date: pd.Timestamp) -> Any | None:
    return cache.get(contract, {}).get(pd.Timestamp(date).normalize())


def _lookback_bars(series: list[Any], date: pd.Timestamp, count: int) -> list[Any]:
    normalized = pd.Timestamp(date).normalize()
    before = [bar for bar in series if bar.date < normalized]
    return before[-count:]


def _pct(numerator: float, denominator: float) -> float:
    if denominator == 0 or pd.isna(denominator):
        return float("nan")
    return numerator / denominator * 100.0


def _volume_ratio(series: list[Any], date: pd.Timestamp, current_volume: float, count: int = 20) -> float:
    lookback = _lookback_bars(series, date, count)
    volumes = [float(bar.volume) for bar in lookback if float(bar.volume) > 0]
    if not volumes:
        return float("nan")
    mean_volume = sum(volumes) / len(volumes)
    return current_volume / mean_volume if mean_volume > 0 else float("nan")


def _pre20_return(series: list[Any], date: pd.Timestamp, current_open: float) -> float:
    lookback = _lookback_bars(series, date, 20)
    if not lookback:
        return float("nan")
    start_close = float(lookback[0].close)
    return _pct(current_open - start_close, start_close)


def _build_events() -> tuple[pd.DataFrame, pd.DataFrame]:
    candidates = _normalize_dates(
        _read_csv(CANDIDATES_PATH),
        ["date", "signal_date_1", "signal_date_2"],
    )
    roundtrips = _normalize_dates(_read_csv(ROUNDTRIPS_PATH), ["entry_date", "exit_date"])
    opened = candidates[candidates["candidate_status"].astype(str).eq("opened")].copy()
    if opened.empty:
        return pd.DataFrame(), candidates

    contracts = sorted(set(opened["entry_contract_vt_symbol"].dropna().astype(str)))
    start = pd.Timestamp(opened["signal_date_1"].min()) - pd.Timedelta(days=80)
    end = pd.Timestamp(roundtrips["exit_date"].max()) + pd.Timedelta(days=5)
    cache = _load_bar_cache(contracts, start=start.to_pydatetime(), end=end.to_pydatetime())

    universe_meta = _load_universe_metadata()
    opened = opened.merge(universe_meta, on="product_vt_symbol", how="left")
    opened = opened.merge(
        roundtrips,
        left_on=["product_vt_symbol", "entry_contract_vt_symbol", "date"],
        right_on=["product_vt_symbol", "contract_vt_symbol", "entry_date"],
        how="left",
        suffixes=("", "_roundtrip"),
    )

    rows: list[dict[str, Any]] = []
    for row in opened.itertuples(index=False):
        contract = str(row.entry_contract_vt_symbol)
        series = _bar_series(cache, contract)
        signal_date_1 = pd.Timestamp(row.signal_date_1)
        signal_date_2 = pd.Timestamp(row.signal_date_2)
        entry_date = pd.Timestamp(row.date)
        signal1 = _bar_lookup(cache, contract, signal_date_1)
        signal2 = _bar_lookup(cache, contract, signal_date_2)
        entry = _bar_lookup(cache, contract, entry_date)
        if signal1 is None or signal2 is None or entry is None:
            continue

        entry_price = _safe_float(row.entry_price)
        stop_price = _safe_float(row.stop_price)
        stop_distance = max(entry_price - stop_price, 1e-12)
        signal2_range = max(float(signal2.high) - float(signal2.low), 1e-12)
        signal2_close_to_high = _pct(float(signal2.high) - float(signal2.close), float(signal2.open))
        entry_day_open_to_low = max(0.0, entry_price - float(entry.low))
        exit_reason = str(getattr(row, "exit_reason", "") or "")

        rows.append(
            {
                "candidate_index": int(row.candidate_index),
                "entry_date": entry_date.date().isoformat(),
                "entry_year": int(entry_date.year),
                "product_vt_symbol": str(row.product_vt_symbol),
                "sector": _sector(str(row.product_vt_symbol)),
                "contract_vt_symbol": contract,
                "exit_date": pd.Timestamp(getattr(row, "exit_date")).date().isoformat()
                if pd.notna(getattr(row, "exit_date"))
                else "",
                "exit_reason": exit_reason,
                "is_long_initial_stop": int(exit_reason == "long_initial_stop"),
                "net_pnl": _safe_float(getattr(row, "net_pnl", 0.0)),
                "slippage": _safe_float(getattr(row, "slippage", 0.0)),
                "holding_days": _safe_float(getattr(row, "holding_days", 0.0)),
                "selected_volume": int(_safe_float(row.selected_volume)),
                "planned_half_exit_volume": int(_safe_float(getattr(row, "planned_half_exit_volume", 0.0))),
                "entry_price": entry_price,
                "stop_price": stop_price,
                "stop_distance": stop_distance,
                "entry_gap_vs_signal2_close_pct": _pct(entry_price - float(signal2.close), float(signal2.close)),
                "entry_open_vs_signal2_high_pct": _pct(entry_price - float(signal2.high), float(signal2.high)),
                "entry_risk_distance_pct": _pct(stop_distance, entry_price),
                "entry_open_position_in_signal2_range": (entry_price - float(signal2.low)) / signal2_range,
                "two_signal_day_return_pct": _pct(float(signal2.close) - float(signal1.open), float(signal1.open)),
                "signal1_body_pct": _pct(float(signal1.close) - float(signal1.open), float(signal1.open)),
                "signal2_body_pct": _pct(float(signal2.close) - float(signal2.open), float(signal2.open)),
                "signal2_close_to_high_pct": signal2_close_to_high,
                "entry_day_open_to_low_r": entry_day_open_to_low / stop_distance,
                "entry_day_range_pct": _pct(float(entry.high) - float(entry.low), entry_price),
                "entry_day_close_return_pct": _pct(float(entry.close) - entry_price, entry_price),
                "entry_day_low_breached_stop": int(float(entry.low) <= stop_price),
                "entry_day_gap_stop": int(float(entry.open) <= stop_price),
                "pre20_return_pct": _pre20_return(series, signal_date_1, float(signal1.open)),
                "signal2_volume_ratio_20d": _volume_ratio(series, signal_date_2, float(signal2.volume)),
                "entry_volume_ratio_20d": _volume_ratio(series, entry_date, float(entry.volume)),
                "recent_median_volume": _safe_float(getattr(row, "recent_median_volume", 0.0)),
                "recent_bar_coverage_ratio": _safe_float(getattr(row, "recent_bar_coverage_ratio", 0.0)),
                "recent_nonzero_volume_ratio": _safe_float(getattr(row, "recent_nonzero_volume_ratio", 0.0)),
                "estimated_margin_per_contract": _safe_float(getattr(row, "estimated_margin_per_contract", 0.0)),
            }
        )

    return pd.DataFrame(rows), candidates


def _build_feature_contrast(events: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for feature in NUMERIC_FEATURES:
        values = pd.to_numeric(events[feature], errors="coerce")
        initial = values[events["is_long_initial_stop"].astype(int).eq(1)].dropna()
        others = values[events["is_long_initial_stop"].astype(int).eq(0)].dropna()
        rows.append(
            {
                "feature": feature,
                "initial_stop_count": int(len(initial)),
                "other_count": int(len(others)),
                "initial_stop_mean": float(initial.mean()) if not initial.empty else float("nan"),
                "other_mean": float(others.mean()) if not others.empty else float("nan"),
                "mean_diff_initial_minus_other": float(initial.mean() - others.mean())
                if not initial.empty and not others.empty
                else float("nan"),
                "initial_stop_median": float(initial.median()) if not initial.empty else float("nan"),
                "other_median": float(others.median()) if not others.empty else float("nan"),
                "median_diff_initial_minus_other": float(initial.median() - others.median())
                if not initial.empty and not others.empty
                else float("nan"),
            }
        )
    return pd.DataFrame(rows)


def _bucket_series(series: pd.Series, bins: list[float], labels: list[str]) -> pd.Series:
    return pd.cut(pd.to_numeric(series, errors="coerce"), bins=bins, labels=labels, include_lowest=True).astype(str)


def _build_bucket_summary(events: pd.DataFrame) -> pd.DataFrame:
    bucket_defs = {
        "entry_gap_vs_signal2_close_pct": (
            [-math.inf, 0.0, 0.5, 1.0, 2.0, math.inf],
            ["<=0", "0~0.5", "0.5~1", "1~2", ">2"],
        ),
        "entry_risk_distance_pct": (
            [-math.inf, 1.0, 2.0, 3.0, 5.0, math.inf],
            ["<=1", "1~2", "2~3", "3~5", ">5"],
        ),
        "entry_open_position_in_signal2_range": (
            [-math.inf, 1.0, 1.5, 2.0, 3.0, math.inf],
            ["<=1x", "1~1.5x", "1.5~2x", "2~3x", ">3x"],
        ),
        "entry_day_range_pct": (
            [-math.inf, 1.0, 2.0, 3.0, 5.0, math.inf],
            ["<=1", "1~2", "2~3", "3~5", ">5"],
        ),
        "pre20_return_pct": (
            [-math.inf, -5.0, 0.0, 5.0, 10.0, math.inf],
            ["<=-5", "-5~0", "0~5", "5~10", ">10"],
        ),
        "signal2_volume_ratio_20d": (
            [-math.inf, 0.8, 1.2, 2.0, 3.0, math.inf],
            ["<=0.8x", "0.8~1.2x", "1.2~2x", "2~3x", ">3x"],
        ),
    }
    rows: list[pd.DataFrame] = []
    for feature, (bins, labels) in bucket_defs.items():
        frame = events.copy()
        frame["bucket"] = _bucket_series(frame[feature], bins, labels)
        summary = _group_summary(frame, "bucket")
        if summary.empty:
            continue
        summary.insert(0, "feature", feature)
        rows.append(summary)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def _group_summary(events: pd.DataFrame, group_column: str) -> pd.DataFrame:
    if events.empty or group_column not in events.columns:
        return pd.DataFrame()
    grouped = events.groupby(group_column, dropna=False)
    result = grouped.agg(
        event_count=("net_pnl", "size"),
        net_pnl=("net_pnl", "sum"),
        avg_net_pnl=("net_pnl", "mean"),
        initial_stop_count=("is_long_initial_stop", "sum"),
        win_ratio_pct=("net_pnl", lambda values: float((values > 0).mean() * 100.0)),
        avg_entry_gap_pct=("entry_gap_vs_signal2_close_pct", "mean"),
        avg_entry_risk_distance_pct=("entry_risk_distance_pct", "mean"),
        avg_entry_day_open_to_low_r=("entry_day_open_to_low_r", "mean"),
    ).reset_index()
    result["initial_stop_rate_pct"] = result["initial_stop_count"] / result["event_count"] * 100.0
    return result.sort_values("net_pnl").reset_index(drop=True)


def _skip_summary(candidates: pd.DataFrame) -> pd.DataFrame:
    frame = candidates.copy()
    frame["skip_reason"] = frame["skip_reason"].fillna("")
    return (
        frame.groupby(["candidate_status", "skip_reason"], dropna=False)
        .size()
        .reset_index(name="count")
        .sort_values(["candidate_status", "count"], ascending=[True, False])
    )


def _to_markdown_table(df: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 12) -> str:
    if df.empty:
        return "_empty_"
    view = df[columns].copy() if columns else df.copy()
    view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda value: f"{value:.4f}")
    header = "| " + " | ".join(view.columns) + " |"
    separator = "| " + " | ".join(["---"] * len(view.columns)) + " |"
    rows = ["| " + " | ".join(map(str, row)) + " |" for row in view.to_numpy()]
    return "\n".join([header, separator, *rows])


def _build_report(
    summary: dict[str, Any],
    feature_contrast: pd.DataFrame,
    bucket_summary: pd.DataFrame,
    sector_summary: pd.DataFrame,
    year_summary: pd.DataFrame,
    product_summary: pd.DataFrame,
    skip_summary: pd.DataFrame,
) -> str:
    selected_features = feature_contrast[
        feature_contrast["feature"].isin(
            [
                "entry_day_open_to_low_r",
                "entry_day_range_pct",
                "entry_gap_vs_signal2_close_pct",
                "entry_risk_distance_pct",
                "pre20_return_pct",
                "signal2_volume_ratio_20d",
            ]
        )
    ].copy()
    selected_buckets = bucket_summary[
        bucket_summary["feature"].isin(
            [
                "entry_gap_vs_signal2_close_pct",
                "entry_risk_distance_pct",
                "entry_day_range_pct",
                "pre20_return_pct",
                "signal2_volume_ratio_20d",
            ]
        )
    ].copy()
    return "\n".join(
        [
            "# 期货无下影线波段 Stage002 失败归因",
            "",
            "## 总览",
            "",
            f"- 开仓事件：`{summary['event_count']}`",
            f"- 首日止损事件：`{summary['initial_stop_count']}`，占比 `{summary['initial_stop_rate_pct']:.2f}%`",
            f"- 首日止损净亏：`{summary['initial_stop_net_pnl']:,.0f}`",
            f"- 非首日止损净赚/亏：`{summary['other_net_pnl']:,.0f}`",
            f"- 首日止损平均 entry_day_open_to_low_r：`{summary['initial_stop_avg_open_to_low_r']:.4f}`",
            f"- 其他事件平均 entry_day_open_to_low_r：`{summary['other_avg_open_to_low_r']:.4f}`",
            "",
            "## 关键特征对比",
            "",
            _to_markdown_table(
                selected_features,
                [
                    "feature",
                    "initial_stop_mean",
                    "other_mean",
                    "mean_diff_initial_minus_other",
                    "initial_stop_median",
                    "other_median",
                ],
                20,
            ),
            "",
            "## 分桶摘要",
            "",
            _to_markdown_table(
                selected_buckets,
                [
                    "feature",
                    "bucket",
                    "event_count",
                    "net_pnl",
                    "initial_stop_rate_pct",
                    "avg_entry_day_open_to_low_r",
                ],
                40,
            ),
            "",
            "## 板块摘要",
            "",
            _to_markdown_table(
                sector_summary,
                ["sector", "event_count", "net_pnl", "initial_stop_rate_pct", "avg_entry_day_open_to_low_r"],
                20,
            ),
            "",
            "## 年度摘要",
            "",
            _to_markdown_table(
                year_summary,
                ["entry_year", "event_count", "net_pnl", "initial_stop_rate_pct", "avg_entry_day_open_to_low_r"],
                20,
            ),
            "",
            "## 品种摘要",
            "",
            _to_markdown_table(
                product_summary,
                [
                    "product_vt_symbol",
                    "event_count",
                    "net_pnl",
                    "initial_stop_rate_pct",
                    "avg_entry_gap_pct",
                    "avg_entry_day_open_to_low_r",
                ],
                20,
            ),
            "",
            "## 候选跳过摘要",
            "",
            _to_markdown_table(skip_summary, max_rows=20),
            "",
            "## 结论",
            "",
            "- 主要损害来自入场日向下回撤直接吃满风险预算，而不是持仓后移动止损拖累。",
            "- 形态在部分事件里有后续波段收益，但原始入口对第三天开盘后的反身性太敏感。",
            "- 下一步只建议做首日失败机制的反事实归因，不建议直接扫宽松下影线或任意加过滤器。",
            "",
        ]
    )


def main() -> None:
    events, candidates = _build_events()
    if events.empty:
        raise RuntimeError("No opened events available for attribution.")

    feature_contrast = _build_feature_contrast(events)
    bucket_summary = _build_bucket_summary(events)
    product_summary = _group_summary(events, "product_vt_symbol")
    sector_summary = _group_summary(events, "sector")
    year_summary = _group_summary(events, "entry_year")
    skipped = _skip_summary(candidates)

    initial = events[events["is_long_initial_stop"].astype(int).eq(1)].copy()
    other = events[events["is_long_initial_stop"].astype(int).eq(0)].copy()
    summary = {
        "model_tag": MODEL_TAG,
        "source_prefix": SOURCE_PREFIX,
        "mapping_path": str(DEFAULT_MAPPING_PATH),
        "universe_path": str(DEFAULT_UNIVERSE_PATH),
        "event_count": int(len(events)),
        "initial_stop_count": int(len(initial)),
        "initial_stop_rate_pct": float(len(initial) / len(events) * 100.0),
        "initial_stop_net_pnl": float(initial["net_pnl"].sum()),
        "other_net_pnl": float(other["net_pnl"].sum()),
        "initial_stop_avg_open_to_low_r": float(initial["entry_day_open_to_low_r"].mean()),
        "other_avg_open_to_low_r": float(other["entry_day_open_to_low_r"].mean()),
        "initial_stop_avg_entry_gap_pct": float(initial["entry_gap_vs_signal2_close_pct"].mean()),
        "other_avg_entry_gap_pct": float(other["entry_gap_vs_signal2_close_pct"].mean()),
    }

    EVENTS_CSV.parent.mkdir(parents=True, exist_ok=True)
    events.to_csv(EVENTS_CSV, index=False, encoding="utf-8-sig")
    feature_contrast.to_csv(FEATURE_CONTRAST_CSV, index=False, encoding="utf-8-sig")
    bucket_summary.to_csv(BUCKET_SUMMARY_CSV, index=False, encoding="utf-8-sig")
    product_summary.to_csv(PRODUCT_SUMMARY_CSV, index=False, encoding="utf-8-sig")
    sector_summary.to_csv(SECTOR_SUMMARY_CSV, index=False, encoding="utf-8-sig")
    year_summary.to_csv(YEAR_SUMMARY_CSV, index=False, encoding="utf-8-sig")
    skipped.to_csv(SKIP_SUMMARY_CSV, index=False, encoding="utf-8-sig")
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_MD.write_text(
        _build_report(summary, feature_contrast, bucket_summary, sector_summary, year_summary, product_summary, skipped),
        encoding="utf-8",
    )

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(
        json.dumps(
            {
                "events": str(EVENTS_CSV),
                "feature_contrast": str(FEATURE_CONTRAST_CSV),
                "bucket_summary": str(BUCKET_SUMMARY_CSV),
                "product_summary": str(PRODUCT_SUMMARY_CSV),
                "sector_summary": str(SECTOR_SUMMARY_CSV),
                "year_summary": str(YEAR_SUMMARY_CSV),
                "skip_summary": str(SKIP_SUMMARY_CSV),
                "summary": str(SUMMARY_JSON),
                "report": str(REPORT_MD),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
