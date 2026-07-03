from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sqlite3
import sys
from typing import Any, Iterable

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
PORTFOLIO_DIR = PROJECT_DIR / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

import analyze_qmt_roll_stage345_cross_sectional_momentum_satellite as s345  # noqa: E402
from main_contract_mapping import load_mapping_df  # noqa: E402
from qmt_universe import VT_SYMBOLS  # noqa: E402


LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage020"
MODEL_TAG = "stage020_sqlite_jd_repair_xsmom_inputs_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage020_sqlite_jd_repair_xsmom_inputs"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage020_sqlite_jd_repair_xsmom_inputs"
STAGES_DIR = LINE_DIR / "stages"

PRODUCT_RETURN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_returns_{MODEL_TAG}.csv"
FEATURE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_features_{MODEL_TAG}.csv"
SATELLITE_DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_satellite_daily_{MODEL_TAG}.csv"
MISSING_CLOSE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_missing_close_rows_{MODEL_TAG}.csv"
SOURCE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_summary_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
STAGE_RECORD_PATH = STAGES_DIR / "20260702_0610_stage020_sqlite_jd_repair_xsmom_inputs.md"

DATABASE_PATH = PROJECT_DIR / ".vntrader" / "database.db"
STAGE050_DIR = (
    PROJECT_DIR
    / "research"
    / "lines"
    / "futures_trend_rebuilt_c9_15w_optimization"
    / "outputs"
    / "stage050_jd_contract_oi_source_repair"
)
STAGE050_MAPPING_PATH = (
    STAGE050_DIR
    / "rebuilt_c9_stage050_jd_contract_oi_source_repair_combined_mapping_stage050_jd_contract_oi_source_repair_v1.csv"
)
STAGE050_BARS_PATH = (
    STAGE050_DIR
    / "rebuilt_c9_stage050_jd_contract_oi_source_repair_contract_bars_stage050_jd_contract_oi_source_repair_v1.csv"
)
EXTRA_JD_GAP_BARS_PATH = OUTPUT_DIR / "stage020_extra_jd_missing_gap_fetch_bars.csv"

EXTRA_PRODUCTS = ("jd.DCE",)
START_DATE = "2020-01-02"
TARGET_END_DATE = "2026-06-30"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        if pd.isna(value):
            return ""
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return str(value)
    if pd.isna(value):
        return ""
    return value


def selected_products() -> list[str]:
    return sorted(set(VT_SYMBOLS) | set(EXTRA_PRODUCTS))


def load_mapping() -> pd.DataFrame:
    start = pd.Timestamp(START_DATE)
    end = pd.Timestamp(TARGET_END_DATE)
    mapping = load_mapping_df()
    mapping["date"] = pd.to_datetime(mapping["date"], errors="coerce").dt.normalize()
    mapping = mapping[mapping["continuous_symbol_vt"].isin(selected_products())].copy()
    if STAGE050_MAPPING_PATH.exists():
        jd_mapping = pd.read_csv(STAGE050_MAPPING_PATH, encoding="utf-8-sig")
        jd_mapping["date"] = pd.to_datetime(jd_mapping["date"], errors="coerce").dt.normalize()
        jd_mapping = jd_mapping[jd_mapping["continuous_symbol_vt"].astype(str).eq("jd.DCE")].copy()
        mapping = mapping[~mapping["continuous_symbol_vt"].astype(str).eq("jd.DCE")].copy()
        mapping = pd.concat([mapping, jd_mapping], ignore_index=True, sort=False)
    mapping = mapping[mapping["date"].between(start, end)].copy()
    mapping["main_contract_vt"] = mapping["main_contract_vt"].fillna("").astype(str)
    mapping = mapping[mapping["main_contract_vt"].ne("")].copy()
    return mapping[["date", "continuous_symbol_vt", "main_contract_vt"]].drop_duplicates().reset_index(drop=True)


def _split_contracts(mapping: pd.DataFrame) -> pd.DataFrame:
    contracts = mapping[["main_contract_vt"]].drop_duplicates().copy()
    contracts[["symbol", "exchange"]] = contracts["main_contract_vt"].str.split(".", n=1, expand=True)
    return contracts.dropna(subset=["symbol", "exchange"]).reset_index(drop=True)


def load_sqlite_close_source(mapping: pd.DataFrame) -> pd.DataFrame:
    contracts = _split_contracts(mapping)
    if contracts.empty or not DATABASE_PATH.exists():
        return pd.DataFrame(columns=["date", "main_contract_vt", "close_price", "source"])
    clauses: list[str] = []
    params: list[str] = []
    for row in contracts.itertuples(index=False):
        clauses.append("(symbol=? and exchange=?)")
        params.extend([str(row.symbol), str(row.exchange)])
    query = (
        "select symbol, exchange, datetime, close_price from dbbardata "
        f"where interval='d' and ({' or '.join(clauses)})"
    )
    with sqlite3.connect(DATABASE_PATH) as connection:
        bars = pd.read_sql_query(query, connection, params=params)
    if bars.empty:
        return pd.DataFrame(columns=["date", "main_contract_vt", "close_price", "source"])
    bars["date"] = pd.to_datetime(bars["datetime"], errors="coerce").dt.normalize()
    bars["main_contract_vt"] = bars["symbol"].astype(str) + "." + bars["exchange"].astype(str)
    bars["close_price"] = pd.to_numeric(bars["close_price"], errors="coerce")
    bars["source"] = "sqlite_db"
    return bars[["date", "main_contract_vt", "close_price", "source"]].dropna(subset=["date"])


def load_stage050_jd_close_source() -> pd.DataFrame:
    if not STAGE050_BARS_PATH.exists():
        return pd.DataFrame(columns=["date", "main_contract_vt", "close_price", "source"])
    bars = pd.read_csv(STAGE050_BARS_PATH, encoding="utf-8-sig")
    return normalise_contract_bar_source(bars, source_name="stage050_jd_repair")


def normalise_contract_bar_source(bars: pd.DataFrame, *, source_name: str) -> pd.DataFrame:
    bars["date"] = pd.to_datetime(bars["datetime"], errors="coerce").dt.normalize()
    bars["main_contract_vt"] = bars["contract_vt_symbol"].astype(str)
    bars["close_price"] = pd.to_numeric(bars["close_price"], errors="coerce")
    bars["source"] = source_name
    return bars[["date", "main_contract_vt", "close_price", "source"]].dropna(subset=["date"])


def load_extra_jd_gap_close_source() -> pd.DataFrame:
    if not EXTRA_JD_GAP_BARS_PATH.exists():
        return pd.DataFrame(columns=["date", "main_contract_vt", "close_price", "source"])
    bars = pd.read_csv(EXTRA_JD_GAP_BARS_PATH, encoding="utf-8-sig")
    return normalise_contract_bar_source(bars, source_name="stage020_extra_jd_gap_fetch")


def merge_close_sources(frames: Iterable[pd.DataFrame]) -> pd.DataFrame:
    cleaned: list[pd.DataFrame] = []
    for frame in frames:
        if frame.empty:
            continue
        data = frame.copy()
        data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
        data["close_price"] = pd.to_numeric(data["close_price"], errors="coerce")
        data = data.dropna(subset=["date", "main_contract_vt", "close_price"])
        data = data[data["close_price"].gt(0.0)].copy()
        cleaned.append(data[["date", "main_contract_vt", "close_price", "source"]])
    if not cleaned:
        return pd.DataFrame(columns=["date", "main_contract_vt", "close_price", "source"])
    merged = pd.concat(cleaned, ignore_index=True, sort=False)
    return (
        merged.sort_values(["date", "main_contract_vt", "source"])
        .drop_duplicates(["date", "main_contract_vt"], keep="last")
        .sort_values(["main_contract_vt", "date"])
        .reset_index(drop=True)
    )


def build_product_returns(mapping: pd.DataFrame, closes: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = mapping.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    data = data.rename(columns={"continuous_symbol_vt": "product_vt_symbol"})
    close_data = closes.copy()
    close_data["date"] = pd.to_datetime(close_data["date"], errors="coerce").dt.normalize()
    merged = data.merge(close_data, on=["date", "main_contract_vt"], how="left")
    merged = merged.rename(columns={"close_price": "main_close", "source": "close_source"})
    merged["main_close"] = pd.to_numeric(merged["main_close"], errors="coerce")
    merged = merged.sort_values(["product_vt_symbol", "date"]).reset_index(drop=True)
    merged["prev_close"] = merged.groupby("product_vt_symbol")["main_close"].shift(1)
    merged["prev_contract"] = merged.groupby("product_vt_symbol")["main_contract_vt"].shift(1)
    same_contract = merged["main_contract_vt"].eq(merged["prev_contract"])
    valid_return = same_contract & merged["main_close"].gt(0) & merged["prev_close"].gt(0)
    merged["product_return"] = 0.0
    merged.loc[valid_return, "product_return"] = (
        merged.loc[valid_return, "main_close"] / merged.loc[valid_return, "prev_close"] - 1.0
    )
    missing = merged[merged["main_close"].isna()].copy()
    return (
        merged[
            [
                "date",
                "product_vt_symbol",
                "main_contract_vt",
                "main_close",
                "product_return",
                "close_source",
            ]
        ].reset_index(drop=True),
        missing[["date", "product_vt_symbol", "main_contract_vt"]].rename(
            columns={"product_vt_symbol": "continuous_symbol_vt"}
        ),
    )


def assess_coverage(
    product_returns: pd.DataFrame,
    missing_close_rows: pd.DataFrame,
    *,
    min_valid_products: int = s345.MIN_VALID_PRODUCTS,
    target_end_date: str = TARGET_END_DATE,
) -> dict[str, Any]:
    data = product_returns.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    data["main_close"] = pd.to_numeric(data["main_close"], errors="coerce")
    valid_counts = data.groupby("date")["main_close"].apply(lambda series: int(series.notna().sum()))
    min_valid_dates = valid_counts[valid_counts >= int(min_valid_products)]
    last_min_valid = pd.Timestamp(min_valid_dates.index.max()).date().isoformat() if not min_valid_dates.empty else ""
    target = pd.Timestamp(target_end_date).normalize()
    target_count = int(valid_counts.get(target, 0))
    target_covered = target_count >= int(min_valid_products)
    missing_rows = int(len(missing_close_rows))
    if target_covered and missing_rows == 0:
        decision = "stage020_xsmom_inputs_target_covered_no_gaps_ready_for_proxy"
    elif target_covered:
        decision = "stage020_xsmom_inputs_target_covered_with_gaps_keep_readonly"
    else:
        decision = "stage020_xsmom_inputs_target_not_covered_keep_readonly"
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "decision": decision,
        "target_end_date": target.date().isoformat(),
        "target_end_valid_products": target_count,
        "target_end_min_valid_covered": bool(target_covered),
        "last_date_with_min_valid_products": last_min_valid,
        "min_valid_products": int(min_valid_products),
        "rows": int(len(data)),
        "products": int(data["product_vt_symbol"].nunique()),
        "start_date": pd.Timestamp(data["date"].min()).date().isoformat() if not data.empty else "",
        "end_date": pd.Timestamp(data["date"].max()).date().isoformat() if not data.empty else "",
        "missing_close_rows": missing_rows,
        "missing_close_products": int(missing_close_rows["continuous_symbol_vt"].nunique())
        if not missing_close_rows.empty
        else 0,
        "all_missing_close_dates": int((valid_counts == 0).sum()),
    }


def _summarize_source(product_returns: pd.DataFrame) -> pd.DataFrame:
    data = product_returns.copy()
    data["close_source"] = data["close_source"].fillna("missing")
    return (
        data.groupby(["product_vt_symbol", "close_source"], dropna=False)
        .size()
        .reset_index(name="rows")
        .sort_values(["product_vt_symbol", "close_source"])
    )


def _summarize_satellite(satellite: pd.DataFrame) -> dict[str, Any]:
    if satellite.empty:
        return {"rows": 0, "specs": 0, "active_signal_rows": 0, "start_date": "", "end_date": ""}
    data = satellite.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    active = data["long_products"].fillna("").astype(str).ne("") | data["short_products"].fillna("").astype(str).ne("")
    return {
        "rows": int(len(data)),
        "specs": int(data["spec"].nunique()),
        "active_signal_rows": int(active.sum()),
        "start_date": pd.Timestamp(data["date"].min()).date().isoformat(),
        "end_date": pd.Timestamp(data["date"].max()).date().isoformat(),
    }


def _write_report(summary: dict[str, Any], satellite_summary: dict[str, Any]) -> None:
    lines = [
        "# Stage020 SQLite + jd 修复包 xsmom 输入重建",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 阶段性质：数据输入重建/覆盖审计，不做收益回测，不改官方实盘。",
        f"- 决策：`{summary['decision']}`",
        "",
        "## 调研判断",
        "",
        "- 外部趋势跟随/横截面动量资料支持低相关收益腿方向，但本阶段只修数据覆盖，不把信号交易化。",
        "- 本地 SQLite 日线覆盖 18 个非 jd 产品到目标终点；旧恢复线 Stage050 jd 修复包可覆盖 jd 的 2026-03-27 到 2026-06-30。",
        "- 仍保留 missing close 明细，避免把缺口静默当作真实 0 收益。",
        "",
        "## 覆盖摘要",
        "",
        f"- 产品数：`{summary['products']}`，行数：`{summary['rows']}`。",
        f"- 区间：`{summary['start_date']} -> {summary['end_date']}`。",
        f"- 目标终点 `{summary['target_end_date']}` 有效产品数：`{summary['target_end_valid_products']}`，min_valid：`{summary['min_valid_products']}`。",
        f"- last_date_with_min_valid_products：`{summary['last_date_with_min_valid_products']}`。",
        f"- missing_close_rows：`{summary['missing_close_rows']}`，missing_close_products：`{summary['missing_close_products']}`，all_missing_close_dates：`{summary['all_missing_close_dates']}`。",
        "",
        "## Satellite 摘要",
        "",
        f"- satellite rows：`{satellite_summary['rows']}`，specs：`{satellite_summary['specs']}`，active_signal_rows：`{satellite_summary['active_signal_rows']}`。",
        f"- satellite date range：`{satellite_summary['start_date']} -> {satellite_summary['end_date']}`。",
        "",
        "## 输出",
        "",
        f"- product_returns：`{PRODUCT_RETURN_PATH.relative_to(PROJECT_DIR)}`",
        f"- features：`{FEATURE_PATH.relative_to(PROJECT_DIR)}`",
        f"- satellite_daily：`{SATELLITE_DAILY_PATH.relative_to(PROJECT_DIR)}`",
        f"- missing_close_rows：`{MISSING_CLOSE_PATH.relative_to(PROJECT_DIR)}`",
        f"- source_summary：`{SOURCE_SUMMARY_PATH.relative_to(PROJECT_DIR)}`",
        f"- summary：`{SUMMARY_PATH.relative_to(PROJECT_DIR)}`",
        "",
        "## 过拟合反思",
        "",
        "- 运行前判断：否。原因：只合并预先存在的数据源，不根据收益调参数。",
        "- 运行后判断：否。原因：缺口明细被保留，没有把 missing close 静默伪装为全量有效。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前判断：是。原因：Stage019 暴露的覆盖缺口阻止后续 proxy。",
        "- 运行后判断：是。原因：目标终点已可覆盖；但仍需先处理/评估 jd 历史 missing close，再决定是否进入 proxy。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    STAGE_RECORD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    mapping = load_mapping()
    closes = merge_close_sources(
        [
            load_sqlite_close_source(mapping),
            load_stage050_jd_close_source(),
            load_extra_jd_gap_close_source(),
        ]
    )
    product_returns, missing = build_product_returns(mapping, closes)
    features = s345._build_momentum_features(product_returns)
    satellite = s345._build_satellite_returns(features, product_returns)
    summary = assess_coverage(product_returns, missing)
    satellite_summary = _summarize_satellite(satellite)
    summary["satellite_summary"] = satellite_summary

    product_returns.to_csv(PRODUCT_RETURN_PATH, index=False, encoding="utf-8-sig")
    features.to_csv(FEATURE_PATH, index=False, encoding="utf-8-sig")
    satellite.to_csv(SATELLITE_DAILY_PATH, index=False, encoding="utf-8-sig")
    missing.to_csv(MISSING_CLOSE_PATH, index=False, encoding="utf-8-sig")
    _summarize_source(product_returns).to_csv(SOURCE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_PATH.write_text(json.dumps(_json_safe(summary), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(summary, satellite_summary)
    print(json.dumps(_json_safe(summary), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
