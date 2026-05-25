from __future__ import annotations

import json
import math
import multiprocessing as mp
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
RAW_DIR: Path = OUTPUT_DIR / "external_supply_demand_cache"

MODEL_TAG: str = "stage316_supply_demand_quality_probe_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage316_supply_demand_quality_probe"
LINE_ID: str = "futures_trend_drawdown30_preserve_return"

FETCH_START_DAY: str = "20230101"
FETCH_END_DAY: str = "20260417"
ROLLING_DAYS: int = 120
MIN_ROLLING_DAYS: int = 40
BASIS_CHANGE_DAYS: int = 20
MAX_SIGNAL_AGE_DAYS: int = 7
SOURCE_TIMEOUT_SECONDS: int = 12
MAX_CONSECUTIVE_SOURCE_FAILURES: int = 8

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
    "JM": "jm.DCE",
    "LC": "lc.GFEX",
    "LH": "lh.DCE",
    "RB": "rb.SHFE",
    "RU": "ru.SHFE",
    "SI": "si.GFEX",
    "SP": "sp.SHFE",
}

SHFE_CODES: tuple[str, ...] = ("AU", "CU", "FU", "HC", "RB", "RU", "SP")
CZCE_CODES: tuple[str, ...] = ("AP", "CF", "FG", "MA", "OI", "SA", "SH", "SM")
GFEX_CODES: tuple[str, ...] = ("LC", "SI")

RAW_BASIS_PATH: Path = RAW_DIR / f"supply_demand_basis_{FETCH_START_DAY}_{FETCH_END_DAY}.csv"
RAW_WAREHOUSE_PATH: Path = RAW_DIR / f"supply_demand_warehouse_{FETCH_START_DAY}_{FETCH_END_DAY}.csv"
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
    raise TimeoutErrorForSource(f"source_timeout_after_{SOURCE_TIMEOUT_SECONDS}s")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or math.isinf(result):
        return default
    return result


def _numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0.0)


def _rolling_zscore(series: pd.Series) -> pd.Series:
    mean = series.rolling(ROLLING_DAYS, min_periods=MIN_ROLLING_DAYS).mean()
    std = series.rolling(ROLLING_DAYS, min_periods=MIN_ROLLING_DAYS).std().replace(0.0, np.nan)
    return ((series - mean) / std).replace([np.inf, -np.inf], np.nan)


def _calendar_days() -> list[str]:
    from akshare.futures import cons

    start = pd.Timestamp(FETCH_START_DAY)
    end = pd.Timestamp(FETCH_END_DAY)
    calendar = pd.Series(cons.get_calendar()).astype(str).str.replace("-", "", regex=False)
    days = calendar[(calendar >= start.strftime("%Y%m%d")) & (calendar <= end.strftime("%Y%m%d"))]
    return days.drop_duplicates().sort_values().tolist()


def _run_with_alarm(func: Any, *args: Any, **kwargs: Any) -> Any:
    signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(SOURCE_TIMEOUT_SECONDS)
    try:
        return func(*args, **kwargs)
    finally:
        signal.alarm(0)


def _akshare_worker(function_name: str, args: tuple[Any, ...], kwargs: dict[str, Any], queue: mp.Queue) -> None:
    try:
        import akshare as ak

        result = getattr(ak, function_name)(*args, **kwargs)
        queue.put({"status": "ok", "result": result})
    except Exception as exc:  # pragma: no cover - external source instability
        queue.put({"status": "error", "error_type": type(exc).__name__, "error_message": str(exc)})


def _run_akshare_source(function_name: str, *args: Any, **kwargs: Any) -> Any:
    ctx = mp.get_context("fork")
    queue: mp.Queue = ctx.Queue()
    process = ctx.Process(target=_akshare_worker, args=(function_name, args, kwargs, queue))
    process.start()
    process.join(SOURCE_TIMEOUT_SECONDS)
    if process.is_alive():
        process.terminate()
        process.join(2)
        raise TimeoutErrorForSource(f"{function_name}_timeout_after_{SOURCE_TIMEOUT_SECONDS}s")
    if queue.empty():
        raise RuntimeError(f"{function_name}_returned_no_result")
    message = queue.get()
    if message.get("status") != "ok":
        raise RuntimeError(f"{message.get('error_type')}: {message.get('error_message')}")
    return message.get("result")


def _fetch_basis_daily() -> tuple[pd.DataFrame, str]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    if RAW_BASIS_PATH.exists() and RAW_BASIS_PATH.stat().st_size > 0:
        return pd.read_csv(RAW_BASIS_PATH), "cache"

    import akshare as ak

    rows: list[pd.DataFrame] = []
    vars_list = sorted(PRODUCTS_BY_CODE)
    for index, day in enumerate(_calendar_days(), start=1):
        try:
            daily = _run_akshare_source("futures_spot_price", day, vars_list)
        except Exception as exc:  # pragma: no cover - external source instability
            print(f"basis_fetch_failed {day} {type(exc).__name__}: {exc}")
            continue
        if isinstance(daily, pd.DataFrame) and not daily.empty:
            rows.append(daily.copy())
        if index % 80 == 0:
            print(f"basis_fetch_progress {index}")
    result = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    result.to_csv(RAW_BASIS_PATH, index=False, encoding="utf-8-sig")
    return result, "akshare"


def _czce_total_row(frame: pd.DataFrame) -> pd.Series:
    if frame.empty:
        return pd.Series(dtype=object)
    first_col = frame.columns[0]
    mask = frame[first_col].astype(str).str.contains("总计", na=False)
    if mask.any():
        return frame.loc[mask].iloc[-1]
    return pd.Series(dtype=object)


def _parse_czce_warehouse(date: str, data: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for code in CZCE_CODES:
        frame = data.get(code)
        if frame is None or frame.empty:
            continue
        total = _czce_total_row(frame)
        if total.empty:
            continue
        receipt_columns = [column for column in frame.columns if str(column).startswith("仓单数量")]
        quantity = sum(_safe_float(total.get(column)) for column in receipt_columns)
        change = _safe_float(total.get("当日增减"))
        rows.append(
            {
                "date": date,
                "product_code": code,
                "product_vt_symbol": PRODUCTS_BY_CODE[code],
                "warehouse_receipt_quantity": quantity,
                "warehouse_receipt_change": change,
                "warehouse_source": "czce_warehouse_receipt",
            }
        )
    return rows


def _parse_shfe_warehouse(date: str, data: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    frames = [frame for frame in data.values() if isinstance(frame, pd.DataFrame) and not frame.empty]
    if not frames:
        return []
    frame = pd.concat(frames, ignore_index=True)
    if "VARID" not in frame.columns:
        return []
    frame["product_code"] = frame["VARID"].astype(str).str.upper()
    rows: list[dict[str, Any]] = []
    for code, group in frame[frame["product_code"].isin(SHFE_CODES)].groupby("product_code", sort=True):
        rows.append(
            {
                "date": date,
                "product_code": code,
                "product_vt_symbol": PRODUCTS_BY_CODE[code],
                "warehouse_receipt_quantity": float(_numeric(group["WRTWGHTS"]).sum())
                if "WRTWGHTS" in group.columns
                else 0.0,
                "warehouse_receipt_change": float(_numeric(group["WRTCHANGE"]).sum())
                if "WRTCHANGE" in group.columns
                else 0.0,
                "warehouse_source": "shfe_warehouse_receipt",
            }
        )
    return rows


def _parse_gfex_warehouse(date: str, data: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for code in GFEX_CODES:
        frame = data.get(code)
        if frame is None or frame.empty:
            continue
        rows.append(
            {
                "date": date,
                "product_code": code,
                "product_vt_symbol": PRODUCTS_BY_CODE[code],
                "warehouse_receipt_quantity": float(_numeric(frame["今日仓单量"]).sum())
                if "今日仓单量" in frame.columns
                else 0.0,
                "warehouse_receipt_change": float(_numeric(frame["增减"]).sum()) if "增减" in frame.columns else 0.0,
                "warehouse_source": "gfex_warehouse_receipt",
            }
        )
    return rows


def _fetch_warehouse_daily() -> tuple[pd.DataFrame, str]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    if RAW_WAREHOUSE_PATH.exists() and RAW_WAREHOUSE_PATH.stat().st_size > 0:
        return pd.read_csv(RAW_WAREHOUSE_PATH), "cache"

    rows: list[dict[str, Any]] = []
    disabled_exchanges: set[str] = set()
    consecutive_failures: dict[str, int] = {"shfe": 0, "czce": 0, "gfex": 0}
    for index, day in enumerate(_calendar_days(), start=1):
        for exchange, function_name, parser in (
            ("shfe", "futures_shfe_warehouse_receipt", _parse_shfe_warehouse),
            ("czce", "futures_warehouse_receipt_czce", _parse_czce_warehouse),
            ("gfex", "futures_gfex_warehouse_receipt", _parse_gfex_warehouse),
        ):
            if exchange in disabled_exchanges:
                continue
            try:
                data = _run_akshare_source(function_name, day)
            except Exception as exc:  # pragma: no cover - external source instability
                consecutive_failures[exchange] += 1
                print(f"warehouse_fetch_failed {exchange} {day} {type(exc).__name__}: {exc}")
                if consecutive_failures[exchange] >= MAX_CONSECUTIVE_SOURCE_FAILURES:
                    disabled_exchanges.add(exchange)
                    print(
                        "warehouse_source_disabled "
                        f"{exchange} {day} consecutive_failures={consecutive_failures[exchange]}"
                    )
                continue
            consecutive_failures[exchange] = 0
            rows.extend(parser(day, data))
        if index % 80 == 0:
            print(f"warehouse_fetch_progress {index}")
            if rows:
                pd.DataFrame(rows).to_csv(RAW_WAREHOUSE_PATH, index=False, encoding="utf-8-sig")
    result = pd.DataFrame(rows)
    result.to_csv(RAW_WAREHOUSE_PATH, index=False, encoding="utf-8-sig")
    return result, "akshare"


def _build_basis_features(raw: pd.DataFrame) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame()
    frame = raw.copy()
    frame["date"] = frame["date"].astype(str).str.replace("-", "", regex=False)
    frame["product_code"] = frame["symbol"].astype(str).str.upper()
    frame = frame[frame["product_code"].isin(PRODUCTS_BY_CODE)].copy()
    if frame.empty:
        return pd.DataFrame()
    frame["product_vt_symbol"] = frame["product_code"].map(PRODUCTS_BY_CODE)
    for column in ["spot_price", "dominant_contract_price", "dom_basis", "dom_basis_rate"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["basis_date_dt"] = pd.to_datetime(frame["date"], format="%Y%m%d", errors="coerce")
    frame = frame[frame["basis_date_dt"].notna()].copy()

    chunks: list[pd.DataFrame] = []
    for _, group in frame.groupby("product_vt_symbol", sort=False):
        group = group.sort_values("basis_date_dt").copy()
        group["dom_basis_rate_change_20d"] = group["dom_basis_rate"].diff(BASIS_CHANGE_DAYS)
        group["basis_level_z"] = _rolling_zscore(group["dom_basis_rate"])
        group["basis_change_z"] = _rolling_zscore(group["dom_basis_rate_change_20d"])
        # AKShare defines dom_basis_rate as futures / spot - 1. Lower values mean spot strength.
        group["basis_level_long_component"] = (-group["basis_level_z"].clip(-2.0, 2.0) / 2.0).fillna(0.0)
        group["basis_change_long_component"] = (-group["basis_change_z"].clip(-2.0, 2.0) / 2.0).fillna(0.0)
        chunks.append(group)
    return pd.concat(chunks, ignore_index=True)


def _build_warehouse_features(raw: pd.DataFrame) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame()
    frame = raw.copy()
    frame["date"] = frame["date"].astype(str).str.replace("-", "", regex=False)
    frame["product_code"] = frame["product_code"].astype(str).str.upper()
    frame = frame[frame["product_code"].isin(PRODUCTS_BY_CODE)].copy()
    if frame.empty:
        return pd.DataFrame()
    frame["product_vt_symbol"] = frame["product_code"].map(PRODUCTS_BY_CODE)
    frame["warehouse_receipt_quantity"] = pd.to_numeric(frame["warehouse_receipt_quantity"], errors="coerce").fillna(0.0)
    frame["warehouse_receipt_change"] = pd.to_numeric(frame["warehouse_receipt_change"], errors="coerce").fillna(0.0)
    frame["warehouse_date_dt"] = pd.to_datetime(frame["date"], format="%Y%m%d", errors="coerce")
    frame = frame[frame["warehouse_date_dt"].notna()].copy()

    chunks: list[pd.DataFrame] = []
    for _, group in frame.groupby("product_vt_symbol", sort=False):
        group = group.sort_values("warehouse_date_dt").copy()
        denominator = (
            group["warehouse_receipt_quantity"].abs().rolling(60, min_periods=20).median().replace(0.0, np.nan)
        )
        group["warehouse_change_ratio"] = (group["warehouse_receipt_change"] / denominator).replace(
            [np.inf, -np.inf], np.nan
        )
        group["warehouse_change_z"] = _rolling_zscore(group["warehouse_change_ratio"])
        group["warehouse_change_long_component"] = (-group["warehouse_change_z"].clip(-2.0, 2.0) / 2.0).fillna(0.0)
        chunks.append(group)
    return pd.concat(chunks, ignore_index=True)


def _combine_features(basis_features: pd.DataFrame, warehouse_features: pd.DataFrame) -> pd.DataFrame:
    basis_cols = [
        "date",
        "product_code",
        "product_vt_symbol",
        "basis_date_dt",
        "spot_price",
        "dominant_contract",
        "dominant_contract_price",
        "dom_basis",
        "dom_basis_rate",
        "dom_basis_rate_change_20d",
        "basis_level_long_component",
        "basis_change_long_component",
    ]
    warehouse_cols = [
        "date",
        "product_vt_symbol",
        "warehouse_date_dt",
        "warehouse_receipt_quantity",
        "warehouse_receipt_change",
        "warehouse_change_ratio",
        "warehouse_change_long_component",
        "warehouse_source",
    ]
    left = basis_features[basis_cols].copy() if not basis_features.empty else pd.DataFrame(columns=basis_cols)
    right = (
        warehouse_features[warehouse_cols].copy()
        if not warehouse_features.empty
        else pd.DataFrame(columns=warehouse_cols)
    )
    combined = pd.merge(left, right, on=["date", "product_vt_symbol"], how="outer")
    combined["product_code"] = combined["product_code"].fillna(
        combined["product_vt_symbol"].astype(str).str.split(".", n=1).str[0].str.upper()
    )
    combined["date_dt"] = pd.to_datetime(combined["date"], format="%Y%m%d", errors="coerce")
    combined = combined[combined["date_dt"].notna()].copy()

    for component in [
        "basis_level_long_component",
        "basis_change_long_component",
        "warehouse_change_long_component",
    ]:
        combined[component] = pd.to_numeric(combined[component], errors="coerce")

    def weighted_component(row: pd.Series) -> tuple[float, int]:
        pieces = [
            (0.40, row.get("basis_level_long_component")),
            (0.30, row.get("basis_change_long_component")),
            (0.30, row.get("warehouse_change_long_component")),
        ]
        available = [(weight, _safe_float(value)) for weight, value in pieces if not pd.isna(value)]
        if not available:
            return 0.0, 0
        weight_sum = sum(weight for weight, _ in available)
        score = sum(weight * value for weight, value in available) / max(weight_sum, 1e-12)
        return float(np.clip(score, -1.0, 1.0)), len(available)

    scored = combined.apply(weighted_component, axis=1, result_type="expand")
    combined["supply_demand_long_component"] = scored[0].astype(float)
    combined["supply_demand_component_count"] = scored[1].astype(int)
    combined = combined[combined["supply_demand_component_count"] > 0].copy()
    combined["available_datetime"] = combined["date_dt"] + pd.Timedelta(hours=20)
    return combined.sort_values(["date_dt", "product_vt_symbol"]).reset_index(drop=True)


def _signal_row(feature_row: dict[str, Any], direction: str) -> dict[str, Any]:
    sign = 1.0 if direction == "long" else -1.0
    quality = float(np.clip(sign * _safe_float(feature_row.get("supply_demand_long_component")), -1.0, 1.0))
    component_count = int(_safe_float(feature_row.get("supply_demand_component_count")))
    confidence = {1: 0.55, 2: 0.65, 3: 0.75}.get(component_count, 0.50)
    return {
        "available_datetime": pd.Timestamp(feature_row["available_datetime"]).isoformat(),
        "product_vt_symbol": str(feature_row["product_vt_symbol"]),
        "direction": direction,
        "source_type": "supply_demand_basis_warehouse",
        "source_name": "仓单库存与基差供需压力",
        "external_quality_score": quality,
        "suggested_volume_multiplier": float(np.clip(1.0 + 0.10 * quality, 0.90, 1.10)),
        "veto_flag": int(quality <= -0.85),
        "confidence": confidence,
        "source_url": "akshare:futures_spot_price,futures_*_warehouse_receipt",
        "text_hash": f"supply_demand:{feature_row['product_vt_symbol']}:{feature_row['date']}",
        "notes": (
            f"basis_rate={_safe_float(feature_row.get('dom_basis_rate')):.6f}; "
            f"basis_chg20={_safe_float(feature_row.get('dom_basis_rate_change_20d')):.6f}; "
            f"warehouse_chg={_safe_float(feature_row.get('warehouse_receipt_change')):.2f}; "
            f"components={component_count}"
        ),
    }


def _build_external_signals(features: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for record in features.to_dict("records"):
        rows.append(_signal_row(record, "long"))
        rows.append(_signal_row(record, "short"))
    signals = pd.DataFrame(rows, columns=list(stage312.REQUIRED_EXTERNAL_COLUMNS))
    if not signals.empty:
        signals.sort_values(["available_datetime", "product_vt_symbol", "direction"], inplace=True)
        signals.reset_index(drop=True, inplace=True)
    return signals


def _source_summary(features: pd.DataFrame, basis_mode: str, warehouse_mode: str) -> pd.DataFrame:
    if features.empty:
        return pd.DataFrame()
    grouped = (
        features.groupby("product_vt_symbol")
        .agg(
            数据天数=("date", "nunique"),
            起始日期=("date", "min"),
            结束日期=("date", "max"),
            平均基差率=("dom_basis_rate", "mean"),
            平均仓单增减=("warehouse_receipt_change", "mean"),
            平均供需方向分量=("supply_demand_long_component", "mean"),
            平均可用组件数=("supply_demand_component_count", "mean"),
        )
        .reset_index()
    )
    grouped.insert(0, "warehouse_source_mode", warehouse_mode)
    grouped.insert(0, "basis_source_mode", basis_mode)
    return grouped


def _build_report(
    *,
    source_summary: pd.DataFrame,
    coverage_df: pd.DataFrame,
    bucket_summary: pd.DataFrame,
    decision: str,
    basis_mode: str,
    warehouse_mode: str,
) -> str:
    lines = [
        "# Stage316 仓单库存与基差开仓质量探针",
        "",
        "## 本阶段定位",
        "",
        "- 这是 Stage016 后的供需侧外生开仓质量因子。",
        "- 本阶段不修改第78-1交易逻辑，不运行收益回测；只验证供需压力能否区分好开仓和差开仓。",
        "- 固定低自由度公式：现货强、基差改善、仓单下降支持做多；反向支持做空。",
        "",
        "## 数据和点时化",
        "",
        f"- 基差数据来源模式：`{basis_mode}`。",
        f"- 仓单数据来源模式：`{warehouse_mode}`。",
        f"- 数据区间：`{FETCH_START_DAY}` 到 `{FETCH_END_DAY}`。",
        f"- 最大信号年龄：`{MAX_SIGNAL_AGE_DAYS}` 个自然日。",
        "- 仓单和基差均按收市后可见处理，本脚本将可用时间设为交易日20:00，只允许影响下一交易日及之后候选。",
        "",
        "## 因子公式",
        "",
        "- AKShare `dom_basis_rate = 主力期货价 / 现货价 - 1`，所以数值越低通常代表现货更强。",
        "- 做多方向：`-基差率zscore`、`-20日基差率变化zscore`、`-仓单变化率zscore`。",
        "- 固定权重：基差水平 `40%`、基差变化 `30%`、仓单变化 `30%`；缺失组件按可用组件重归一。",
        "- 做空方向取做多供需分量的反号。",
        "",
        "## 数据覆盖",
        "",
        to_markdown_table(source_summary) if not source_summary.empty else "没有可用供需数据。",
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
        "- 本阶段不根据结果调整权重；若失败，优先换数据形态或放弃该因子。",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    basis_raw, basis_mode = _fetch_basis_daily()
    warehouse_raw, warehouse_mode = _fetch_warehouse_daily()

    basis_features = _build_basis_features(basis_raw)
    warehouse_features = _build_warehouse_features(warehouse_raw)
    features = _combine_features(basis_features, warehouse_features)
    signals = _build_external_signals(features)
    source_summary = _source_summary(features, basis_mode, warehouse_mode)

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
            basis_mode=basis_mode,
            warehouse_mode=warehouse_mode,
        ),
        encoding="utf-8",
    )
    summary = {
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "base_version": OFFICIAL_STAGE78_VERSION,
        "analysis_type": "supply_demand_quality_probe_no_strategy_backtest",
        "decision": decision,
        "fetch_start_day": FETCH_START_DAY,
        "fetch_end_day": FETCH_END_DAY,
        "rolling_days": ROLLING_DAYS,
        "min_rolling_days": MIN_ROLLING_DAYS,
        "basis_change_days": BASIS_CHANGE_DAYS,
        "max_signal_age_days": MAX_SIGNAL_AGE_DAYS,
        "basis_source_mode": basis_mode,
        "warehouse_source_mode": warehouse_mode,
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
