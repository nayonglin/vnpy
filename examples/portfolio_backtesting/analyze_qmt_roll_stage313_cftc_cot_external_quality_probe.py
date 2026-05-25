from __future__ import annotations

import io
import json
import math
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import analyze_qmt_roll_stage312_external_quality_signal_evaluator as stage312
from qmt_roll_official_stage78_config import OFFICIAL_STAGE78_VERSION
from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import to_markdown_table


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"
RAW_DIR: Path = OUTPUT_DIR / "external_cftc_cot_cache"

MODEL_TAG: str = "stage313_cftc_cot_external_quality_probe_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage313_cftc_cot_external_quality_probe"
LINE_ID: str = "futures_trend_drawdown30_preserve_return"

START_YEAR: int = 2020
END_YEAR: int = 2026
ROLLING_WEEKS: int = 156
MIN_ROLLING_WEEKS: int = 52

EXTERNAL_SIGNAL_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_external_signals_{MODEL_TAG}.csv"
JOINED_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_joined_candidates_{MODEL_TAG}.csv"
BUCKET_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_summary_{MODEL_TAG}.csv"
COVERAGE_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coverage_{MODEL_TAG}.csv"
SOURCE_SUMMARY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_summary_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


@dataclass(frozen=True)
class ProductCotMapping:
    product_vt_symbol: str
    cftc_market_name: str
    source_name: str
    mapping_type: str
    confidence: float


PRODUCT_COT_MAPPINGS: tuple[ProductCotMapping, ...] = (
    ProductCotMapping("CF.CZCE", "COTTON NO. 2 - ICE FUTURES U.S.", "CFTC COT Cotton No.2", "direct_global_proxy", 0.70),
    ProductCotMapping("OI.CZCE", "SOYBEAN OIL - CHICAGO BOARD OF TRADE", "CFTC COT Soybean Oil", "oilseed_proxy", 0.60),
    ProductCotMapping("lh.DCE", "LEAN HOGS - CHICAGO MERCANTILE EXCHANGE", "CFTC COT Lean Hogs", "direct_global_proxy", 0.70),
    ProductCotMapping("lc.GFEX", "LITHIUM HYDROXIDE  - COMMODITY EXCHANGE INC.", "CFTC COT Lithium Hydroxide", "new_market_proxy", 0.45),
    ProductCotMapping("au.SHFE", "GOLD - COMMODITY EXCHANGE INC.", "CFTC COT Gold", "direct_global_proxy", 0.75),
    ProductCotMapping("cu.SHFE", "COPPER- #1 - COMMODITY EXCHANGE INC.", "CFTC COT Copper", "direct_global_proxy", 0.75),
    ProductCotMapping("fu.SHFE", "FUEL OIL-3% USGC/3.5% FOB RDAM - ICE FUTURES ENERGY DIV", "CFTC COT Fuel Oil", "energy_proxy", 0.50),
    ProductCotMapping("hc.SHFE", "STEEL-HRC - COMMODITY EXCHANGE INC.", "CFTC COT HRC Steel", "steel_proxy", 0.55),
    ProductCotMapping("rb.SHFE", "STEEL-HRC - COMMODITY EXCHANGE INC.", "CFTC COT HRC Steel", "steel_proxy", 0.55),
)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or math.isinf(result):
        return default
    return result


def _download_year_zip(year: int) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = RAW_DIR / f"fut_disagg_txt_{year}.zip"
    if zip_path.exists() and zip_path.stat().st_size > 0:
        return zip_path

    url = f"https://www.cftc.gov/files/dea/history/fut_disagg_txt_{year}.zip"
    request = urllib.request.Request(url, headers={"User-Agent": "curl/8.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        zip_path.write_bytes(response.read())
    return zip_path


def _load_cftc_disaggregated_futures_only(years: range) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    use_columns = [
        "Market_and_Exchange_Names",
        "Report_Date_as_YYYY-MM-DD",
        "Open_Interest_All",
        "M_Money_Positions_Long_All",
        "M_Money_Positions_Short_All",
        "Change_in_M_Money_Long_All",
        "Change_in_M_Money_Short_All",
    ]

    for year in years:
        zip_path = _download_year_zip(year)
        with zipfile.ZipFile(zip_path) as archive:
            member = archive.namelist()[0]
            data = archive.read(member)
        frame = pd.read_csv(io.BytesIO(data), usecols=use_columns, low_memory=False)
        frame["source_year"] = year
        frames.append(frame)

    data = pd.concat(frames, ignore_index=True)
    data["Report_Date_as_YYYY-MM-DD"] = pd.to_datetime(data["Report_Date_as_YYYY-MM-DD"], errors="coerce")
    data = data[data["Report_Date_as_YYYY-MM-DD"].notna()].copy()
    for column in [
        "Open_Interest_All",
        "M_Money_Positions_Long_All",
        "M_Money_Positions_Short_All",
        "Change_in_M_Money_Long_All",
        "Change_in_M_Money_Short_All",
    ]:
        data[column] = pd.to_numeric(data[column], errors="coerce").fillna(0.0)
    data.sort_values(["Market_and_Exchange_Names", "Report_Date_as_YYYY-MM-DD"], inplace=True)
    data.reset_index(drop=True, inplace=True)
    return data


def _rolling_zscore(series: pd.Series) -> pd.Series:
    mean = series.rolling(ROLLING_WEEKS, min_periods=MIN_ROLLING_WEEKS).mean()
    std = series.rolling(ROLLING_WEEKS, min_periods=MIN_ROLLING_WEEKS).std().replace(0.0, np.nan)
    return ((series - mean) / std).replace([np.inf, -np.inf], np.nan)


def _build_cot_feature_table(raw: pd.DataFrame) -> pd.DataFrame:
    frame = raw.copy()
    open_interest = frame["Open_Interest_All"].replace(0.0, np.nan)
    frame["managed_money_net_oi"] = (
        frame["M_Money_Positions_Long_All"] - frame["M_Money_Positions_Short_All"]
    ) / open_interest
    frame["managed_money_flow_oi"] = (
        frame["Change_in_M_Money_Long_All"] - frame["Change_in_M_Money_Short_All"]
    ) / open_interest

    chunks: list[pd.DataFrame] = []
    for _, group in frame.groupby("Market_and_Exchange_Names", sort=False):
        group = group.sort_values("Report_Date_as_YYYY-MM-DD").copy()
        group["managed_money_net_z"] = _rolling_zscore(group["managed_money_net_oi"])
        group["managed_money_flow_z"] = _rolling_zscore(group["managed_money_flow_oi"])
        chunks.append(group)
    features = pd.concat(chunks, ignore_index=True)
    features["managed_money_net_component"] = (features["managed_money_net_z"].clip(-2.0, 2.0) / 2.0).fillna(0.0)
    features["managed_money_flow_component"] = (features["managed_money_flow_z"].clip(-2.0, 2.0) / 2.0).fillna(0.0)
    features["cot_directional_component"] = (
        0.35 * features["managed_money_net_component"]
        + 0.65 * features["managed_money_flow_component"]
    ).clip(-1.0, 1.0)
    # COT reports are dated Tuesday and generally released Friday. Use Saturday morning China time
    # as a conservative point-in-time availability assumption for daily Chinese futures signals.
    features["available_datetime"] = features["Report_Date_as_YYYY-MM-DD"] + pd.Timedelta(days=4, hours=8)
    return features


def _quality_row(
    *,
    mapping: ProductCotMapping,
    feature_row: dict[str, Any],
    direction: str,
) -> dict[str, Any]:
    direction_sign = 1.0 if direction == "long" else -1.0
    quality = float(direction_sign * _safe_float(feature_row.get("cot_directional_component")))
    quality = float(np.clip(quality, -1.0, 1.0))
    multiplier = float(np.clip(1.0 + 0.15 * quality, 0.85, 1.15))
    veto_flag = int(quality <= -0.75 and mapping.confidence >= 0.55)
    return {
        "available_datetime": pd.Timestamp(feature_row["available_datetime"]).isoformat(),
        "product_vt_symbol": mapping.product_vt_symbol,
        "direction": direction,
        "source_type": "official_positioning",
        "source_name": mapping.source_name,
        "external_quality_score": quality,
        "suggested_volume_multiplier": multiplier,
        "veto_flag": veto_flag,
        "confidence": mapping.confidence,
        "source_url": "https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalCompressed/index.htm",
        "text_hash": f"cftc:{mapping.cftc_market_name}:{pd.Timestamp(feature_row['Report_Date_as_YYYY-MM-DD']).date()}",
        "notes": (
            f"{mapping.mapping_type}; managed-money flow/level alignment, "
            f"report_date={pd.Timestamp(feature_row['Report_Date_as_YYYY-MM-DD']).date()}"
        ),
    }


def _build_external_signals(features: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    source_rows: list[dict[str, Any]] = []
    available_markets = set(features["Market_and_Exchange_Names"].astype(str).unique())

    for mapping in PRODUCT_COT_MAPPINGS:
        market_df = features[features["Market_and_Exchange_Names"].astype(str).eq(mapping.cftc_market_name)].copy()
        source_rows.append(
            {
                "product_vt_symbol": mapping.product_vt_symbol,
                "cftc_market_name": mapping.cftc_market_name,
                "source_name": mapping.source_name,
                "mapping_type": mapping.mapping_type,
                "confidence": mapping.confidence,
                "market_available": int(mapping.cftc_market_name in available_markets),
                "raw_rows": int(len(market_df)),
                "signal_start": str(market_df["available_datetime"].min()) if not market_df.empty else "",
                "signal_end": str(market_df["available_datetime"].max()) if not market_df.empty else "",
            }
        )
        if market_df.empty:
            continue
        for record in market_df.to_dict("records"):
            rows.append(_quality_row(mapping=mapping, feature_row=record, direction="long"))
            rows.append(_quality_row(mapping=mapping, feature_row=record, direction="short"))

    signals = pd.DataFrame(rows, columns=list(stage312.REQUIRED_EXTERNAL_COLUMNS))
    if not signals.empty:
        signals.sort_values(["available_datetime", "product_vt_symbol", "direction"], inplace=True)
        signals.reset_index(drop=True, inplace=True)
    return signals, pd.DataFrame(source_rows)


def _build_report(
    *,
    source_summary: pd.DataFrame,
    coverage_df: pd.DataFrame,
    bucket_summary: pd.DataFrame,
    decision: str,
) -> str:
    lines = [
        "# Stage313 CFTC COT 外生开仓质量探针",
        "",
        "## 本阶段定位",
        "",
        "- 这是 Stage013 外生开仓质量框架的第一份真实官方数据填充。",
        "- 数据源是 CFTC Disaggregated Futures Only 周度持仓，不是中国本土公告；因此只做开仓质量代理验证，不直接改第78-1交易。",
        "- 使用 managed money 净持仓水平和周度净流入构造方向一致性分数：趋势方向与资金流/净仓同向加分，反向扣分。",
        "",
        "## 点时化假设",
        "",
        "- COT 报告日期是周二持仓。",
        "- 为保守避免未来函数，本脚本把可用时间设为报告日后第4天早上8点中国时间。",
        "- 候选开仓只允许匹配此前45天内最近一条 COT 信号。",
        "",
        "## 数据源覆盖",
        "",
        to_markdown_table(source_summary),
        "",
        "## 候选匹配覆盖",
        "",
        to_markdown_table(coverage_df),
        "",
        "## 分桶质量",
        "",
        to_markdown_table(bucket_summary) if not bucket_summary.empty else "没有形成可评估分桶。",
        "",
        "## 判定",
        "",
        f"- `{decision}`",
        "",
        "## 解释",
        "",
        "- 如果 test 高分桶没有更高20日R、更低20日不利波动R，则 COT 方向一致性不应接入交易。",
        "- 如果覆盖率太低，即使局部有效，也只能作为后续外生因子候选之一，不能单独承担回撤30以内目标。",
    ]
    return "\n".join(lines)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stage312._require_inputs()

    raw = _load_cftc_disaggregated_futures_only(range(START_YEAR, END_YEAR + 1))
    features = _build_cot_feature_table(raw)
    signals, source_summary = _build_external_signals(features)
    signals.to_csv(EXTERNAL_SIGNAL_PATH, index=False, encoding="utf-8-sig")
    source_summary.to_csv(SOURCE_SUMMARY_PATH, index=False, encoding="utf-8-sig")

    samples, sample_coverage = stage312._build_stage78_candidate_samples()
    samples = stage312._assign_split(samples)
    loaded_signals = stage312._load_external_signals(EXTERNAL_SIGNAL_PATH)
    joined = stage312._join_external_signals(samples, loaded_signals)
    coverage_df = stage312._build_coverage(joined, loaded_signals, sample_coverage)
    bucket_summary = stage312._build_bucket_summary(joined)
    decision = stage312._decision(bucket_summary, coverage_df)

    joined.to_csv(JOINED_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    coverage_df.to_csv(COVERAGE_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    bucket_summary.to_csv(BUCKET_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    REPORT_PATH.write_text(
        _build_report(
            source_summary=source_summary,
            coverage_df=coverage_df,
            bucket_summary=bucket_summary,
            decision=decision,
        ),
        encoding="utf-8",
    )
    SUMMARY_JSON_PATH.write_text(
        json.dumps(
            {
                "model_tag": MODEL_TAG,
                "line_id": LINE_ID,
                "base_version": OFFICIAL_STAGE78_VERSION,
                "analysis_type": "real_external_cot_quality_probe_no_strategy_backtest",
                "decision": decision,
                "years": [START_YEAR, END_YEAR],
                "rolling_weeks": ROLLING_WEEKS,
                "min_rolling_weeks": MIN_ROLLING_WEEKS,
                "product_cot_mappings": [mapping.__dict__ for mapping in PRODUCT_COT_MAPPINGS],
                "source_summary": source_summary.to_dict(orient="records"),
                "coverage": coverage_df.to_dict(orient="records"),
                "bucket_summary": bucket_summary.to_dict(orient="records"),
                "outputs": {
                    "external_signals": str(EXTERNAL_SIGNAL_PATH),
                    "joined_candidates": str(JOINED_OUTPUT_PATH),
                    "coverage": str(COVERAGE_OUTPUT_PATH),
                    "bucket_summary": str(BUCKET_OUTPUT_PATH),
                    "source_summary": str(SOURCE_SUMMARY_PATH),
                    "report": str(REPORT_PATH),
                },
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    print(f"[stage313-cftc-cot] signals: {EXTERNAL_SIGNAL_PATH}")
    print(f"[stage313-cftc-cot] report: {REPORT_PATH}")
    print(f"[stage313-cftc-cot] decision: {decision}")
    print(source_summary.to_string(index=False))
    print(coverage_df.to_string(index=False))
    if not bucket_summary.empty:
        print(bucket_summary.to_string(index=False))


if __name__ == "__main__":
    main()
