from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import build_qmt_roll_ai_candidate_training_samples as candidate_samples
from qmt_roll_official_stage78_config import OFFICIAL_STAGE78_VERSION
from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import to_markdown_table


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage312_external_quality_signal_evaluator_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage312_external_quality_signal_evaluator"
LINE_ID: str = "futures_trend_drawdown30_preserve_return"

STAGE78_CANDIDATE_PATH: Path = (
    OUTPUT_DIR / "qmt_roll_official_stage78_defensive_formal_entry_candidate_snapshots_2020_2026_04.csv"
)
STAGE78_ENTRY_RISK_PATH: Path = (
    OUTPUT_DIR / "qmt_roll_official_stage78_defensive_formal_entry_risk_diagnostics_2020_2026_04.csv"
)
STAGE78_TRADES_PATH: Path = OUTPUT_DIR / "qmt_roll_official_stage78_defensive_formal_trades_2020_2026_04.csv"

EXTERNAL_SIGNAL_TEMPLATE_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_external_signal_template_{MODEL_TAG}.csv"
EXTERNAL_SIGNAL_SCHEMA_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_external_signal_schema_{MODEL_TAG}.json"
JOINED_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_joined_candidates_{MODEL_TAG}.csv"
BUCKET_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_summary_{MODEL_TAG}.csv"
COVERAGE_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coverage_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

MAX_SIGNAL_AGE_DAYS: int = 45
MIN_OOS_MATCHED_ROWS: int = 30

REQUIRED_EXTERNAL_COLUMNS: tuple[str, ...] = (
    "available_datetime",
    "product_vt_symbol",
    "direction",
    "source_type",
    "source_name",
    "external_quality_score",
    "suggested_volume_multiplier",
    "veto_flag",
    "confidence",
    "source_url",
    "text_hash",
    "notes",
)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or math.isinf(result):
        return default
    return result


def _require_inputs() -> None:
    for path in (STAGE78_CANDIDATE_PATH, STAGE78_ENTRY_RISK_PATH, STAGE78_TRADES_PATH):
        if not path.exists():
            raise FileNotFoundError(path)


def _build_stage78_candidate_samples() -> tuple[pd.DataFrame, dict[str, Any]]:
    original_paths = (
        candidate_samples.CANDIDATE_PATH,
        candidate_samples.ENTRY_RISK_PATH,
        candidate_samples.TRADES_PATH,
    )
    candidate_samples.CANDIDATE_PATH = STAGE78_CANDIDATE_PATH
    candidate_samples.ENTRY_RISK_PATH = STAGE78_ENTRY_RISK_PATH
    candidate_samples.TRADES_PATH = STAGE78_TRADES_PATH
    try:
        samples_df, coverage = candidate_samples.build_training_samples()
    finally:
        (
            candidate_samples.CANDIDATE_PATH,
            candidate_samples.ENTRY_RISK_PATH,
            candidate_samples.TRADES_PATH,
        ) = original_paths
    return samples_df, coverage


def _create_external_signal_template(path: Path) -> None:
    if path.exists():
        return
    pd.DataFrame(columns=list(REQUIRED_EXTERNAL_COLUMNS)).to_csv(path, index=False, encoding="utf-8-sig")


def _write_external_signal_schema(path: Path) -> None:
    schema = {
        "model_tag": MODEL_TAG,
        "purpose": "外生数据开仓质量/开仓数量评估输入，不是公告日避险表",
        "point_in_time_rule": "available_datetime 必须早于或等于 candidate_datetime；不能使用事后新闻、事后修订或人工复盘标签。",
        "join_rule": {
            "product_vt_symbol": "可填具体产品如 SC.INE / FU.SHFE，也可填 ALL 表示全市场慢变量。",
            "direction": "long / short / both；方向不匹配则不用于该候选。",
            "max_signal_age_days": MAX_SIGNAL_AGE_DAYS,
            "selection": "同一候选命中多条外生信号时，取 available_datetime 最新的一条；同时间取 confidence 高者。",
        },
        "columns": {
            "available_datetime": "信号在交易前实际可用的时间，ISO格式，例如 2026-05-08 20:30:00。",
            "product_vt_symbol": "产品级映射，如 rb.SHFE、SC.INE、FU.SHFE；全局信号填 ALL。",
            "direction": "long、short 或 both。",
            "source_type": "official_announcement / government_policy / inventory_report / industry_news / news_sentiment / manual_research。",
            "source_name": "来源名称，例如 EIA、国家发改委、交易所公告、USDA WASDE。",
            "external_quality_score": "外生开仓质量分，建议范围[-1,1]；正数提高开仓质量预期，负数降低。",
            "suggested_volume_multiplier": "建议手数倍率，研究期只评估，不直接执行；例如 0.80、1.00、1.15。",
            "veto_flag": "1表示建议禁止新增开仓，0表示不禁止；研究初期默认不接执行。",
            "confidence": "0到1，来源可信度和解析置信度。",
            "source_url": "来源链接，可留空；后续用于审计。",
            "text_hash": "原文或摘要hash，用于避免事后改写；可留空。",
            "notes": "中文说明。",
        },
    }
    path.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_external_signals(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=list(REQUIRED_EXTERNAL_COLUMNS))
    signals = pd.read_csv(path)
    missing = [column for column in REQUIRED_EXTERNAL_COLUMNS if column not in signals.columns]
    if missing:
        raise ValueError(f"external signal missing columns: {missing}")
    if signals.empty:
        return signals

    frame = signals.copy()
    frame["available_datetime"] = pd.to_datetime(frame["available_datetime"], errors="coerce")
    frame = frame[frame["available_datetime"].notna()].copy()
    frame["product_vt_symbol"] = frame["product_vt_symbol"].astype(str).str.strip()
    frame["direction"] = frame["direction"].astype(str).str.lower().str.strip()
    frame["source_type"] = frame["source_type"].astype(str)
    frame["source_name"] = frame["source_name"].astype(str)
    frame["external_quality_score"] = pd.to_numeric(frame["external_quality_score"], errors="coerce").fillna(0.0)
    frame["external_quality_score"] = frame["external_quality_score"].clip(-1.0, 1.0)
    frame["suggested_volume_multiplier"] = (
        pd.to_numeric(frame["suggested_volume_multiplier"], errors="coerce").fillna(1.0).clip(0.0, 2.0)
    )
    frame["veto_flag"] = pd.to_numeric(frame["veto_flag"], errors="coerce").fillna(0).astype("int64").clip(0, 1)
    frame["confidence"] = pd.to_numeric(frame["confidence"], errors="coerce").fillna(0.0).clip(0.0, 1.0)
    frame.sort_values(["available_datetime", "confidence"], inplace=True)
    frame.reset_index(drop=True, inplace=True)
    return frame


def _assign_split(samples_df: pd.DataFrame) -> pd.DataFrame:
    frame = samples_df.copy()
    frame["candidate_date"] = pd.to_datetime(frame["candidate_date"])
    frame["dataset_split"] = "train"
    frame.loc[frame["candidate_date"] >= pd.Timestamp("2023-01-01"), "dataset_split"] = "valid"
    frame.loc[frame["candidate_date"] >= pd.Timestamp("2024-01-01"), "dataset_split"] = "test"
    return frame


def _match_one_signal(candidate_row: dict[str, Any], signals: pd.DataFrame) -> dict[str, Any]:
    if signals.empty:
        return {}

    candidate_dt = pd.Timestamp(candidate_row["candidate_datetime"]).tz_localize(None)
    min_dt = candidate_dt - pd.Timedelta(days=MAX_SIGNAL_AGE_DAYS)
    product = str(candidate_row["product_vt_symbol"])
    direction = str(candidate_row["direction"]).lower()
    mask = (
        (signals["available_datetime"] <= candidate_dt)
        & (signals["available_datetime"] >= min_dt)
        & (signals["product_vt_symbol"].isin([product, "ALL", "all"]))
        & (signals["direction"].isin([direction, "both", "all", ""]))
    )
    candidates = signals.loc[mask].copy()
    if candidates.empty:
        return {}
    candidates.sort_values(["available_datetime", "confidence"], ascending=[False, False], inplace=True)
    row = candidates.iloc[0].to_dict()
    signal_age_days = (candidate_dt - pd.Timestamp(row["available_datetime"])).total_seconds() / 86400.0
    return {
        "external_signal_matched": 1,
        "external_signal_available_datetime": pd.Timestamp(row["available_datetime"]).isoformat(),
        "external_signal_age_days": signal_age_days,
        "external_product_vt_symbol": str(row.get("product_vt_symbol", "")),
        "external_direction": str(row.get("direction", "")),
        "external_source_type": str(row.get("source_type", "")),
        "external_source_name": str(row.get("source_name", "")),
        "external_quality_score": _safe_float(row.get("external_quality_score")),
        "external_suggested_volume_multiplier": _safe_float(row.get("suggested_volume_multiplier"), 1.0),
        "external_veto_flag": int(_safe_float(row.get("veto_flag"))),
        "external_confidence": _safe_float(row.get("confidence")),
        "external_source_url": str(row.get("source_url", "")),
        "external_text_hash": str(row.get("text_hash", "")),
        "external_notes": str(row.get("notes", "")),
    }


def _join_external_signals(samples_df: pd.DataFrame, signals: pd.DataFrame) -> pd.DataFrame:
    base = samples_df.copy()
    base["external_signal_matched"] = 0
    base["external_signal_available_datetime"] = ""
    base["external_signal_age_days"] = np.nan
    base["external_product_vt_symbol"] = ""
    base["external_direction"] = ""
    base["external_source_type"] = ""
    base["external_source_name"] = ""
    base["external_quality_score"] = 0.0
    base["external_suggested_volume_multiplier"] = 1.0
    base["external_veto_flag"] = 0
    base["external_confidence"] = 0.0
    base["external_source_url"] = ""
    base["external_text_hash"] = ""
    base["external_notes"] = ""

    if signals.empty:
        return base

    updates: list[dict[str, Any]] = []
    for row in base.to_dict("records"):
        updates.append(_match_one_signal(row, signals))
    for index, update in enumerate(updates):
        if not update:
            continue
        for key, value in update.items():
            base.at[index, key] = value
    return base


def _build_coverage(joined: pd.DataFrame, signals: pd.DataFrame, sample_coverage: dict[str, Any]) -> pd.DataFrame:
    selected = joined[joined["label_is_selected"].astype(int).eq(1)].copy()
    rows = [
        {
            "指标": "候选样本数",
            "数值": int(len(joined)),
        },
        {
            "指标": "实际开仓候选数",
            "数值": int(len(selected)),
        },
        {
            "指标": "外生信号行数",
            "数值": int(len(signals)),
        },
        {
            "指标": "候选命中外生信号数",
            "数值": int(joined["external_signal_matched"].sum()),
        },
        {
            "指标": "实际开仓命中外生信号数",
            "数值": int(selected["external_signal_matched"].sum()) if not selected.empty else 0,
        },
        {
            "指标": "候选命中率",
            "数值": float(joined["external_signal_matched"].mean()) if not joined.empty else 0.0,
        },
        {
            "指标": "实际开仓命中率",
            "数值": float(selected["external_signal_matched"].mean()) if not selected.empty else 0.0,
        },
        {
            "指标": "原始候选覆盖",
            "数值": json.dumps(sample_coverage, ensure_ascii=False, default=str),
        },
    ]
    return pd.DataFrame(rows)


def _bucketize(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    result = frame.copy()
    if result["external_quality_score"].nunique() >= 3:
        result["external_quality_bucket"] = pd.qcut(
            result["external_quality_score"].rank(method="first"),
            q=3,
            labels=["低分", "中分", "高分"],
        )
    else:
        result["external_quality_bucket"] = np.where(
            result["external_quality_score"] > 0,
            "高分",
            np.where(result["external_quality_score"] < 0, "低分", "中分"),
        )
    return result


def _build_bucket_summary(joined: pd.DataFrame) -> pd.DataFrame:
    matched = joined[joined["external_signal_matched"].astype(int).eq(1)].copy()
    if matched.empty:
        return pd.DataFrame()

    for column in [
        "label_candidate_quality_score_v2",
        "label_candidate_forward_10d_r_multiple",
        "label_candidate_forward_20d_r_multiple",
        "label_candidate_20d_mfe_r",
        "label_candidate_20d_mae_r",
        "external_quality_score",
        "external_suggested_volume_multiplier",
    ]:
        matched[column] = pd.to_numeric(matched[column], errors="coerce").fillna(0.0)

    rows: list[dict[str, Any]] = []
    for split in ["train", "valid", "test"]:
        split_df = _bucketize(matched[matched["dataset_split"].astype(str).eq(split)].copy())
        if split_df.empty:
            continue
        grouped = (
            split_df.groupby("external_quality_bucket", observed=False)
            .agg(
                样本数=("sample_id", "count"),
                产品数=("product_vt_symbol", "nunique"),
                平均外生分=("external_quality_score", "mean"),
                平均建议手数倍率=("external_suggested_volume_multiplier", "mean"),
                建议禁止开仓率=("external_veto_flag", "mean"),
                实际开仓率=("label_is_selected", "mean"),
                平均候选质量分=("label_candidate_quality_score_v2", "mean"),
                平均10日R=("label_candidate_forward_10d_r_multiple", "mean"),
                平均20日R=("label_candidate_forward_20d_r_multiple", "mean"),
                平均20日有利波动R=("label_candidate_20d_mfe_r", "mean"),
                平均20日不利波动R=("label_candidate_20d_mae_r", "mean"),
            )
            .reset_index()
        )
        grouped.insert(0, "样本切分", split)
        rows.extend(grouped.to_dict(orient="records"))
    return pd.DataFrame(rows)


def _decision(bucket_summary: pd.DataFrame, coverage_df: pd.DataFrame) -> str:
    signal_count = int(coverage_df.loc[coverage_df["指标"].eq("外生信号行数"), "数值"].iloc[0])
    if signal_count <= 0:
        return "data_not_ready_create_point_in_time_external_signal_file"
    test_rows = bucket_summary[bucket_summary["样本切分"].astype(str).eq("test")].copy()
    if test_rows.empty or int(test_rows["样本数"].sum()) < MIN_OOS_MATCHED_ROWS:
        return "fail_insufficient_oos_coverage"
    ordered = test_rows.sort_values("external_quality_bucket")
    low = ordered.iloc[0]
    high = ordered.iloc[-1]
    if _safe_float(high["平均20日R"]) <= _safe_float(low["平均20日R"]):
        return "fail_quality_score_not_monotonic_on_oos_forward_r"
    if _safe_float(high["平均20日不利波动R"]) >= _safe_float(low["平均20日不利波动R"]):
        return "fail_quality_score_not_reducing_oos_mae"
    return "monitor_candidate_ready_for_frozen_C_backtest"


def _build_report(
    *,
    coverage_df: pd.DataFrame,
    bucket_summary: pd.DataFrame,
    decision: str,
    external_signal_path: Path,
) -> str:
    lines = [
        "# Stage312 外生开仓质量因子评估器",
        "",
        "## 本阶段定位",
        "",
        "- 目标不是证明“公告附近导致亏损”，而是检验外生信息能否提高开仓质量和控制开仓数量。",
        "- 本阶段不修改第78-1交易逻辑，不新增实盘开关，不运行收益回测。",
        "- 外生信号必须在开仓候选生成前可得，先通过只读评估，再决定是否进入 C 方案。",
        "",
        "## 外生信号输入契约",
        "",
        f"- 输入模板：`{external_signal_path.name}`",
        f"- 最大可用期：`{MAX_SIGNAL_AGE_DAYS}` 个自然日。",
        "- 关键字段：`available_datetime`、`product_vt_symbol`、`direction`、`external_quality_score`、`suggested_volume_multiplier`、`veto_flag`、`confidence`。",
        "- 预期用法：高分可以提高开仓优先级或手数，低分可以降低手数或禁止新增开仓；研究期只评估，不执行。",
        "",
        "## 覆盖情况",
        "",
        to_markdown_table(coverage_df),
        "",
        "## 外生分桶质量",
        "",
        to_markdown_table(bucket_summary) if not bucket_summary.empty else "当前没有真实外生信号命中候选，暂不能做分桶质量判断。",
        "",
        "## 判定",
        "",
        f"- `{decision}`",
        "",
        "## 下一步",
        "",
        "- 优先接入低自由度、可点时化的数据：交易所公告、监管/政府公告、EIA/USDA等固定发布时间报告、产业库存/开工率。",
        "- 每条外生记录只输出一个分数和一个建议手数倍率；不要让LLM按历史收益反推标签。",
        "- 只有当 valid/test 切分里高分桶稳定表现为更高20日R、更低20日不利波动R，才进入冻结规则的 A/C 回测。",
    ]
    return "\n".join(lines)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _require_inputs()
    _create_external_signal_template(EXTERNAL_SIGNAL_TEMPLATE_PATH)
    _write_external_signal_schema(EXTERNAL_SIGNAL_SCHEMA_PATH)

    samples, sample_coverage = _build_stage78_candidate_samples()
    samples = _assign_split(samples)
    signals = _load_external_signals(EXTERNAL_SIGNAL_TEMPLATE_PATH)
    joined = _join_external_signals(samples, signals)
    coverage_df = _build_coverage(joined, signals, sample_coverage)
    bucket_summary = _build_bucket_summary(joined)
    decision = _decision(bucket_summary, coverage_df)

    joined.to_csv(JOINED_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    coverage_df.to_csv(COVERAGE_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    bucket_summary.to_csv(BUCKET_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    REPORT_PATH.write_text(
        _build_report(
            coverage_df=coverage_df,
            bucket_summary=bucket_summary,
            decision=decision,
            external_signal_path=EXTERNAL_SIGNAL_TEMPLATE_PATH,
        ),
        encoding="utf-8",
    )
    SUMMARY_JSON_PATH.write_text(
        json.dumps(
            {
                "model_tag": MODEL_TAG,
                "line_id": LINE_ID,
                "base_version": OFFICIAL_STAGE78_VERSION,
                "analysis_type": "external_quality_monitor_evaluator_no_strategy_backtest",
                "decision": decision,
                "max_signal_age_days": MAX_SIGNAL_AGE_DAYS,
                "coverage": coverage_df.to_dict(orient="records"),
                "bucket_summary": bucket_summary.to_dict(orient="records"),
                "outputs": {
                    "external_signal_template": str(EXTERNAL_SIGNAL_TEMPLATE_PATH),
                    "external_signal_schema": str(EXTERNAL_SIGNAL_SCHEMA_PATH),
                    "joined_candidates": str(JOINED_OUTPUT_PATH),
                    "coverage": str(COVERAGE_OUTPUT_PATH),
                    "bucket_summary": str(BUCKET_OUTPUT_PATH),
                    "report": str(REPORT_PATH),
                },
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    print(f"[stage312-external-quality] template: {EXTERNAL_SIGNAL_TEMPLATE_PATH}")
    print(f"[stage312-external-quality] schema: {EXTERNAL_SIGNAL_SCHEMA_PATH}")
    print(f"[stage312-external-quality] joined: {JOINED_OUTPUT_PATH}")
    print(f"[stage312-external-quality] report: {REPORT_PATH}")
    print(f"[stage312-external-quality] decision: {decision}")
    print(coverage_df.to_string(index=False))
    if not bucket_summary.empty:
        print(bucket_summary.to_string(index=False))


if __name__ == "__main__":
    main()
