from __future__ import annotations

import json
import math
import signal
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import analyze_qmt_roll_stage312_external_quality_signal_evaluator as stage312
from qmt_roll_official_stage78_config import OFFICIAL_STAGE78_VERSION
from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import to_markdown_table


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"
RAW_DIR: Path = OUTPUT_DIR / "external_domestic_member_rank_cache"

MODEL_TAG: str = "stage315_member_rank_quality_probe_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage315_member_rank_quality_probe"
LINE_ID: str = "futures_trend_drawdown30_preserve_return"

FETCH_START_DAY: str = "20230101"
FETCH_END_DAY: str = "20260417"
ROLLING_DAYS: int = 120
MIN_ROLLING_DAYS: int = 40
MAX_SIGNAL_AGE_DAYS: int = 7
AKSHARE_TIMEOUT_SECONDS: int = 240

PRODUCTS_BY_CODE: dict[str, str] = {
    "AP": "AP.CZCE",
    "CF": "CF.CZCE",
    "FG": "FG.CZCE",
    "MA": "MA.CZCE",
    "OI": "OI.CZCE",
    "SA": "SA.CZCE",
    "SH": "SH.CZCE",
    "SM": "SM.CZCE",
    "AU": "au.SHFE",
    "CU": "cu.SHFE",
    "FU": "fu.SHFE",
    "HC": "hc.SHFE",
    "RB": "rb.SHFE",
    "RU": "ru.SHFE",
    "SP": "sp.SHFE",
}

RAW_MEMBER_RANK_PATH: Path = RAW_DIR / f"member_rank_sum_daily_{FETCH_START_DAY}_{FETCH_END_DAY}.csv"
FEATURE_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_features_{MODEL_TAG}.csv"
EXTERNAL_SIGNAL_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_external_signals_{MODEL_TAG}.csv"
JOINED_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_joined_candidates_{MODEL_TAG}.csv"
BUCKET_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_summary_{MODEL_TAG}.csv"
COVERAGE_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coverage_{MODEL_TAG}.csv"
SOURCE_SUMMARY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_summary_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


class TimeoutErrorForSource(RuntimeError):
    pass


def _timeout_handler(signum: int, frame: Any) -> None:
    raise TimeoutErrorForSource(f"akshare_timeout_after_{AKSHARE_TIMEOUT_SECONDS}s")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or math.isinf(result):
        return default
    return result


def _rolling_zscore(series: pd.Series) -> pd.Series:
    mean = series.rolling(ROLLING_DAYS, min_periods=MIN_ROLLING_DAYS).mean()
    std = series.rolling(ROLLING_DAYS, min_periods=MIN_ROLLING_DAYS).std().replace(0.0, np.nan)
    return ((series - mean) / std).replace([np.inf, -np.inf], np.nan)


def _fetch_member_rank_sum_daily() -> tuple[pd.DataFrame, str]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    if RAW_MEMBER_RANK_PATH.exists() and RAW_MEMBER_RANK_PATH.stat().st_size > 0:
        return pd.read_csv(RAW_MEMBER_RANK_PATH), "cache"

    import akshare as ak

    signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(AKSHARE_TIMEOUT_SECONDS)
    try:
        raw = ak.get_rank_sum_daily(
            start_day=FETCH_START_DAY,
            end_day=FETCH_END_DAY,
            vars_list=sorted(PRODUCTS_BY_CODE.keys()),
        )
    finally:
        signal.alarm(0)
    raw.to_csv(RAW_MEMBER_RANK_PATH, index=False, encoding="utf-8-sig")
    return raw, "akshare"


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(frame[column], errors="coerce").fillna(0.0)


def _select_product_rows(group: pd.DataFrame) -> pd.DataFrame:
    variety = str(group["variety"].iloc[0]).upper()
    symbol = group["symbol"].astype(str).str.upper()
    product_rows = group[symbol.eq(variety)].copy()
    if not product_rows.empty:
        return product_rows
    return group.copy()


def _build_member_rank_features(raw: pd.DataFrame) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame()

    frame = raw.copy()
    frame["date"] = frame["date"].astype(str).str.replace("-", "", regex=False)
    frame["variety"] = frame["variety"].astype(str).str.upper()
    frame = frame[frame["variety"].isin(PRODUCTS_BY_CODE)].copy()
    if frame.empty:
        return pd.DataFrame()

    rows: list[dict[str, Any]] = []
    needed_columns = [
        "long_open_interest_top20",
        "long_open_interest_chg_top20",
        "short_open_interest_top20",
        "short_open_interest_chg_top20",
        "vol_top20",
        "vol_chg_top20",
    ]
    for column in needed_columns:
        frame[column] = _numeric(frame, column)

    for (date, variety), group in frame.groupby(["date", "variety"], sort=True):
        selected = _select_product_rows(group)
        long_oi = float(selected["long_open_interest_top20"].sum())
        short_oi = float(selected["short_open_interest_top20"].sum())
        long_chg = float(selected["long_open_interest_chg_top20"].sum())
        short_chg = float(selected["short_open_interest_chg_top20"].sum())
        vol = float(selected["vol_top20"].sum())
        vol_chg = float(selected["vol_chg_top20"].sum())
        denominator = max(long_oi + short_oi, 1.0)
        rows.append(
            {
                "date": date,
                "product_code": variety,
                "product_vt_symbol": PRODUCTS_BY_CODE[variety],
                "contract_rows_used": int(len(selected)),
                "long_open_interest_top20": long_oi,
                "short_open_interest_top20": short_oi,
                "long_open_interest_chg_top20": long_chg,
                "short_open_interest_chg_top20": short_chg,
                "vol_top20": vol,
                "vol_chg_top20": vol_chg,
                "net_position_ratio_top20": (long_oi - short_oi) / denominator,
                "net_position_chg_ratio_top20": (long_chg - short_chg) / denominator,
                "turnover_pressure_ratio_top20": vol / denominator,
            }
        )

    features = pd.DataFrame(rows)
    features["date_dt"] = pd.to_datetime(features["date"], format="%Y%m%d", errors="coerce")
    features = features[features["date_dt"].notna()].copy()
    feature_chunks: list[pd.DataFrame] = []
    for _, group in features.groupby("product_vt_symbol", sort=False):
        group = group.sort_values("date_dt").copy()
        group["net_position_ratio_z"] = _rolling_zscore(group["net_position_ratio_top20"])
        group["net_position_chg_ratio_z"] = _rolling_zscore(group["net_position_chg_ratio_top20"])
        group["member_rank_level_component"] = (group["net_position_ratio_z"].clip(-2.0, 2.0) / 2.0).fillna(0.0)
        group["member_rank_flow_component"] = (group["net_position_chg_ratio_z"].clip(-2.0, 2.0) / 2.0).fillna(0.0)
        group["member_rank_directional_component"] = (
            0.25 * group["member_rank_level_component"] + 0.75 * group["member_rank_flow_component"]
        ).clip(-1.0, 1.0)
        feature_chunks.append(group)

    result = pd.concat(feature_chunks, ignore_index=True)
    # Exchange ranking data is generated after settlement. Treat 20:00 China time as a conservative
    # same-date availability point, so it can only affect the next daily candidate timestamp.
    result["available_datetime"] = result["date_dt"] + pd.Timedelta(hours=20)
    return result


def _signal_row(feature_row: dict[str, Any], direction: str) -> dict[str, Any]:
    sign = 1.0 if direction == "long" else -1.0
    quality = float(np.clip(sign * _safe_float(feature_row.get("member_rank_directional_component")), -1.0, 1.0))
    return {
        "available_datetime": pd.Timestamp(feature_row["available_datetime"]).isoformat(),
        "product_vt_symbol": str(feature_row["product_vt_symbol"]),
        "direction": direction,
        "source_type": "exchange_member_position",
        "source_name": "国内交易所前20会员净持仓变化",
        "external_quality_score": quality,
        "suggested_volume_multiplier": float(np.clip(1.0 + 0.12 * quality, 0.88, 1.12)),
        "veto_flag": int(quality <= -0.80),
        "confidence": 0.70,
        "source_url": "akshare:get_rank_sum_daily; exchange official ranking pages",
        "text_hash": f"member_rank:{feature_row['product_vt_symbol']}:{feature_row['date']}",
        "notes": (
            f"net_chg_ratio={_safe_float(feature_row.get('net_position_chg_ratio_top20')):.6f}; "
            f"net_level_ratio={_safe_float(feature_row.get('net_position_ratio_top20')):.6f}; "
            f"rows={int(_safe_float(feature_row.get('contract_rows_used')))}"
        ),
    }


def _build_external_signals(features: pd.DataFrame) -> pd.DataFrame:
    usable = features.copy()
    usable = usable[usable["date_dt"] >= pd.Timestamp(FETCH_START_DAY)].copy()
    usable = usable[usable["date_dt"] <= pd.Timestamp(FETCH_END_DAY)].copy()
    rows: list[dict[str, Any]] = []
    for record in usable.to_dict("records"):
        rows.append(_signal_row(record, "long"))
        rows.append(_signal_row(record, "short"))
    signals = pd.DataFrame(rows, columns=list(stage312.REQUIRED_EXTERNAL_COLUMNS))
    if not signals.empty:
        signals.sort_values(["available_datetime", "product_vt_symbol", "direction"], inplace=True)
        signals.reset_index(drop=True, inplace=True)
    return signals


def _source_summary(features: pd.DataFrame, source_mode: str) -> pd.DataFrame:
    if features.empty:
        return pd.DataFrame()
    grouped = (
        features.groupby("product_vt_symbol")
        .agg(
            数据天数=("date", "nunique"),
            起始日期=("date", "min"),
            结束日期=("date", "max"),
            平均净多变化率=("net_position_chg_ratio_top20", "mean"),
            平均方向分量=("member_rank_directional_component", "mean"),
            平均合约行数=("contract_rows_used", "mean"),
        )
        .reset_index()
    )
    grouped.insert(0, "source_mode", source_mode)
    return grouped


def _build_report(
    *,
    source_summary: pd.DataFrame,
    coverage_df: pd.DataFrame,
    bucket_summary: pd.DataFrame,
    decision: str,
    source_mode: str,
) -> str:
    lines = [
        "# Stage315 国内会员持仓净变化开仓质量探针",
        "",
        "## 本阶段定位",
        "",
        "- 这是 Stage015 后的第一条国内外生开仓质量因子。",
        "- 本阶段不修改第78-1交易逻辑，不运行收益回测；只验证会员净多变化能否区分好开仓和差开仓。",
        "- 固定低自由度公式：前20会员净多变化率为主，净持仓水平为辅；不扫TopN、不扫阈值、不按收益调权重。",
        "",
        "## 数据和点时化",
        "",
        f"- 数据来源模式：`{source_mode}`。",
        f"- 数据区间：`{FETCH_START_DAY}` 到 `{FETCH_END_DAY}`。",
        f"- 最大信号年龄：`{MAX_SIGNAL_AGE_DAYS}` 个自然日。",
        "- 交易所会员排名按收市结算后才可见处理，本脚本将可用时间设为交易日20:00，只允许影响下一交易日及之后候选。",
        "",
        "## 因子公式",
        "",
        "- `net_position_ratio_top20 = (前20多头持仓 - 前20空头持仓) / (前20多头持仓 + 前20空头持仓)`",
        "- `net_position_chg_ratio_top20 = (前20多头增减 - 前20空头增减) / (前20多头持仓 + 前20空头持仓)`",
        f"- 两者分别做 `{ROLLING_DAYS}` 日滚动 zscore，最低 `{MIN_ROLLING_DAYS}` 日启用。",
        "- 方向分量：`0.25 * 净持仓水平分量 + 0.75 * 净多变化分量`。",
        "- 做多候选取同向分数，做空候选取反向分数。",
        "",
        "## 数据覆盖",
        "",
        to_markdown_table(source_summary) if not source_summary.empty else "没有可用会员持仓数据。",
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
        "- 若 test 高分桶不能同时表现为更高20日R、更低20日不利波动R，则该因子不能进入A/C回测。",
        "- 若只在少数品种或短窗口好看，也不能接入正式78-1。",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    raw, source_mode = _fetch_member_rank_sum_daily()
    features = _build_member_rank_features(raw)
    signals = _build_external_signals(features)
    source_summary = _source_summary(features, source_mode)

    features.to_csv(FEATURE_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    signals.to_csv(EXTERNAL_SIGNAL_PATH, index=False, encoding="utf-8-sig")
    source_summary.to_csv(SOURCE_SUMMARY_PATH, index=False, encoding="utf-8-sig")

    samples, sample_coverage = stage312._build_stage78_candidate_samples()
    samples = stage312._assign_split(samples)
    stage312.MAX_SIGNAL_AGE_DAYS = MAX_SIGNAL_AGE_DAYS
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
            source_mode=source_mode,
        ),
        encoding="utf-8",
    )
    summary = {
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "base_version": OFFICIAL_STAGE78_VERSION,
        "analysis_type": "domestic_member_rank_quality_probe_no_strategy_backtest",
        "decision": decision,
        "fetch_start_day": FETCH_START_DAY,
        "fetch_end_day": FETCH_END_DAY,
        "rolling_days": ROLLING_DAYS,
        "min_rolling_days": MIN_ROLLING_DAYS,
        "max_signal_age_days": MAX_SIGNAL_AGE_DAYS,
        "source_mode": source_mode,
        "external_signal_rows": int(len(signals)),
        "feature_rows": int(len(features)),
        "source_summary": source_summary.to_dict("records"),
        "coverage": coverage_df.to_dict("records"),
        "bucket_summary": bucket_summary.to_dict("records"),
        "outputs": {
            "features": str(FEATURE_OUTPUT_PATH),
            "external_signals": str(EXTERNAL_SIGNAL_PATH),
            "joined_candidates": str(JOINED_OUTPUT_PATH),
            "coverage": str(COVERAGE_OUTPUT_PATH),
            "bucket_summary": str(BUCKET_OUTPUT_PATH),
            "source_summary": str(SOURCE_SUMMARY_PATH),
            "report": str(REPORT_PATH),
        },
    }
    SUMMARY_JSON_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
