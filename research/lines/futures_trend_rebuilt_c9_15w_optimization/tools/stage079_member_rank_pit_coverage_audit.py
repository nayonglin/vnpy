from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
import re
from typing import Any

import numpy as np
import pandas as pd


LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage079"
MODEL_TAG = "stage079_member_rank_pit_coverage_audit_v1"
STAGE_SLUG = "stage079_member_rank_pit_coverage_audit"
OUTPUT_PREFIX = "rebuilt_c9_stage079_member_rank_pit_coverage_audit"

MAX_MEMBER_RANK_AGE_DAYS = 7
LEFT_TAIL_START = pd.Timestamp("2022-01-01")
LEFT_TAIL_END = pd.Timestamp("2023-12-31")
MIN_LEFT_TAIL_ENTRY_COVERAGE_PCT = 50.0
MIN_LEFT_TAIL_LOSS_COVERAGE_PCT = 50.0

TOOLS_DIR = Path(__file__).resolve().parent
LINE_DIR = TOOLS_DIR.parent
PROJECT_DIR = LINE_DIR.parents[2]
OUTPUT_DIR = LINE_DIR / "outputs" / STAGE_SLUG
STAGES_DIR = LINE_DIR / "stages"

BACKTEST_OUTPUTS_DIR = PROJECT_DIR / "examples" / "portfolio_backtesting" / "backtest_outputs"
MEMBER_RANK_PATH = BACKTEST_OUTPUTS_DIR / "external_domestic_member_rank_cache" / "member_rank_sum_daily_20230101_20260417.csv"

STAGE038_OUTPUT_DIR = LINE_DIR / "outputs" / "stage038_candidate_pit_feature_matrix_audit"
STAGE071_OUTPUT_DIR = LINE_DIR / "outputs" / "stage071_stage070_remaining_left_tail_attribution"
STAGE038_PREFIX = "rebuilt_c9_stage038_candidate_pit_feature_matrix_audit"
STAGE038_TAG = "stage038_candidate_pit_feature_matrix_audit_v1"
STAGE071_PREFIX = "rebuilt_c9_stage071_stage070_remaining_left_tail_attribution"
STAGE071_TAG = "stage071_stage070_remaining_left_tail_attribution_v1"

FEATURE_MATRIX_PATH = STAGE038_OUTPUT_DIR / f"{STAGE038_PREFIX}_feature_matrix_{STAGE038_TAG}.csv"
WINDOW_ENTRIES_PATH = STAGE071_OUTPUT_DIR / f"{STAGE071_PREFIX}_window_entries_{STAGE071_TAG}.csv"

MEMBER_FEATURES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_member_features_{MODEL_TAG}.csv"
JOINED_FEATURES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_joined_feature_matrix_{MODEL_TAG}.csv"
JOINED_WINDOWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_joined_window_entries_{MODEL_TAG}.csv"
YEAR_COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_coverage_{MODEL_TAG}.csv"
PRODUCT_COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_coverage_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if math.isnan(number) or math.isinf(number) else number
    if isinstance(value, (pd.Timestamp, datetime)):
        if pd.isna(value):
            return None
        return value.isoformat()
    if pd.isna(value):
        return None
    return value


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_无数据_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    for column in data.columns:
        if pd.api.types.is_float_dtype(data[column]):
            data[column] = data[column].map(lambda value: f"{value:.4f}" if pd.notna(value) else "")
    return data.to_markdown(index=False)


def _date_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, (int, np.integer)):
        return f"{int(value):08d}"
    if isinstance(value, (float, np.floating)) and np.isfinite(value) and float(value).is_integer():
        return f"{int(value):08d}"
    text = str(value).strip()
    if text.endswith(".0") and text[:-2].isdigit():
        return f"{int(float(text)):08d}"
    return text


def _parse_dates(series: pd.Series) -> pd.Series:
    text = series.map(_date_text)
    compact = text.str.fullmatch(r"\d{8}")
    parsed = pd.to_datetime(series, errors="coerce")
    if compact.any():
        parsed.loc[compact] = pd.to_datetime(text.loc[compact], format="%Y%m%d", errors="coerce")
    return parsed.dt.normalize()


def _product_code(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if not text:
        return ""
    if "." in text:
        text = text.split(".", 1)[0]
    match = re.match(r"([A-Za-z]+)", text)
    return match.group(1).upper() if match else ""


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(0.0, index=frame.index, dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce").fillna(0.0)


def _empty_member_features() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "member_date",
            "available_date",
            "product_code",
            "contract_rows_used",
            "has_product_aggregate_row",
            "long_open_interest_top20",
            "short_open_interest_top20",
            "long_open_interest_chg_top20",
            "short_open_interest_chg_top20",
            "vol_top20",
            "net_position_ratio_top20",
            "net_position_chg_ratio_top20",
            "turnover_pressure_ratio_top20",
        ]
    )


def normalize_member_rank_history(raw: pd.DataFrame) -> pd.DataFrame:
    if raw.empty or "date" not in raw.columns or "variety" not in raw.columns:
        return _empty_member_features()

    frame = raw.copy()
    frame["member_date"] = _parse_dates(frame["date"])
    frame["product_code"] = frame["variety"].map(_product_code)
    frame["symbol_text"] = frame.get("symbol", "").astype(str).str.strip().str.upper()
    frame = frame.dropna(subset=["member_date"])
    frame = frame[frame["product_code"].ne("")]
    if frame.empty:
        return _empty_member_features()

    rows: list[dict[str, Any]] = []
    for (member_date, product_code), group in frame.groupby(["member_date", "product_code"], sort=True):
        product_rows = group[group["symbol_text"].eq(product_code)]
        selected = product_rows if not product_rows.empty else group
        long_oi = float(_numeric(selected, "long_open_interest_top20").sum())
        short_oi = float(_numeric(selected, "short_open_interest_top20").sum())
        long_chg = float(_numeric(selected, "long_open_interest_chg_top20").sum())
        short_chg = float(_numeric(selected, "short_open_interest_chg_top20").sum())
        vol = float(_numeric(selected, "vol_top20").sum())
        denominator = max(long_oi + short_oi, 1.0)
        rows.append(
            {
                "member_date": pd.Timestamp(member_date),
                "available_date": pd.Timestamp(member_date) + pd.Timedelta(days=1),
                "product_code": product_code,
                "contract_rows_used": int(len(selected)),
                "has_product_aggregate_row": bool(not product_rows.empty),
                "long_open_interest_top20": long_oi,
                "short_open_interest_top20": short_oi,
                "long_open_interest_chg_top20": long_chg,
                "short_open_interest_chg_top20": short_chg,
                "vol_top20": vol,
                "net_position_ratio_top20": (long_oi - short_oi) / denominator,
                "net_position_chg_ratio_top20": (long_chg - short_chg) / denominator,
                "turnover_pressure_ratio_top20": vol / denominator,
            }
        )
    return pd.DataFrame(rows).sort_values(["product_code", "available_date"]).reset_index(drop=True)


def _entry_product_code(frame: pd.DataFrame) -> pd.Series:
    if "product" in frame.columns:
        product = frame["product"].map(_product_code)
    elif "vt_symbol" in frame.columns:
        product = frame["vt_symbol"].map(_product_code)
    elif "product_key" in frame.columns:
        product = frame["product_key"].map(_product_code)
    else:
        product = pd.Series("", index=frame.index)
    if "vt_symbol" in frame.columns:
        fallback = frame["vt_symbol"].map(_product_code)
        product = product.mask(product.eq(""), fallback)
    return product.fillna("")


def attach_member_rank_asof(entries: pd.DataFrame, member_features: pd.DataFrame, max_age_days: int = MAX_MEMBER_RANK_AGE_DAYS) -> pd.DataFrame:
    result = entries.copy()
    result["_stage079_rowid"] = np.arange(len(result))
    result["entry_date"] = pd.to_datetime(result.get("entry_date"), errors="coerce").dt.normalize()
    result["member_rank_product_code"] = _entry_product_code(result)

    metric_columns = [
        "member_date",
        "available_date",
        "product_code",
        "contract_rows_used",
        "has_product_aggregate_row",
        "long_open_interest_top20",
        "short_open_interest_top20",
        "long_open_interest_chg_top20",
        "short_open_interest_chg_top20",
        "vol_top20",
        "net_position_ratio_top20",
        "net_position_chg_ratio_top20",
        "turnover_pressure_ratio_top20",
    ]
    if result.empty or member_features.empty:
        for column in metric_columns:
            if column not in result.columns:
                result[f"member_rank_{column}"] = np.nan
        result["member_rank_age_days"] = np.nan
        result["member_rank_available"] = False
        return result.drop(columns=["_stage079_rowid"])

    member = member_features.copy()
    member["available_date"] = pd.to_datetime(member["available_date"], errors="coerce").dt.normalize()
    member["member_date"] = pd.to_datetime(member["member_date"], errors="coerce").dt.normalize()
    member = member.dropna(subset=["available_date"])
    for column in metric_columns:
        if column not in member.columns:
            member[column] = np.nan
    joined_parts: list[pd.DataFrame] = []

    for product_code, left_group in result.groupby("member_rank_product_code", dropna=False, sort=False):
        left = left_group.sort_values("entry_date").copy()
        right = member[member["product_code"].eq(product_code)].sort_values("available_date").copy()
        if right.empty:
            for column in metric_columns:
                left[f"member_rank_{column}"] = np.nan
            joined_parts.append(left)
            continue
        renamed = right[metric_columns].rename(columns={column: f"member_rank_{column}" for column in metric_columns})
        merged = pd.merge_asof(
            left,
            renamed,
            left_on="entry_date",
            right_on="member_rank_available_date",
            direction="backward",
        )
        joined_parts.append(merged)

    expected_member_columns = [f"member_rank_{column}" for column in metric_columns]
    concat_parts = []
    for part in joined_parts:
        drop_columns = [
            column
            for column in expected_member_columns
            if column in part.columns and part[column].isna().all()
        ]
        concat_parts.append(part.drop(columns=drop_columns))
    joined = pd.concat(concat_parts, ignore_index=True, sort=False)
    for column in expected_member_columns:
        if column not in joined.columns:
            joined[column] = np.nan
    joined["member_rank_age_days"] = (
        joined["entry_date"] - pd.to_datetime(joined["member_rank_available_date"], errors="coerce")
    ).dt.days
    joined["member_rank_available"] = (
        joined["member_rank_available_date"].notna()
        & joined["member_rank_age_days"].ge(0)
        & joined["member_rank_age_days"].le(max_age_days)
    )
    joined = joined.sort_values("_stage079_rowid").drop(columns=["_stage079_rowid"]).reset_index(drop=True)
    return joined


def _coverage_pct(available_count: int, total_count: int) -> float:
    return float(available_count / total_count * 100.0) if total_count else 0.0


def summarize_member_rank_coverage(
    joined_features: pd.DataFrame,
    joined_windows: pd.DataFrame,
    *,
    min_left_tail_entry_coverage_pct: float = MIN_LEFT_TAIL_ENTRY_COVERAGE_PCT,
    min_left_tail_loss_coverage_pct: float = MIN_LEFT_TAIL_LOSS_COVERAGE_PCT,
) -> dict[str, Any]:
    features = joined_features.copy()
    windows = joined_windows.copy()
    features["entry_date"] = pd.to_datetime(features.get("entry_date"), errors="coerce").dt.normalize()
    windows["entry_date"] = pd.to_datetime(windows.get("entry_date"), errors="coerce").dt.normalize()
    features_available = features.get("member_rank_available", pd.Series(False, index=features.index)).fillna(False).astype(bool)
    windows_available = windows.get("member_rank_available", pd.Series(False, index=windows.index)).fillna(False).astype(bool)
    feature_left_tail = features["entry_date"].between(LEFT_TAIL_START, LEFT_TAIL_END, inclusive="both")
    window_left_tail = windows["entry_date"].between(LEFT_TAIL_START, LEFT_TAIL_END, inclusive="both")
    loss_abs = pd.to_numeric(windows.get("stage071_base_loss_abs"), errors="coerce").fillna(0.0)

    all_feature_count = int(len(features))
    all_feature_available = int(features_available.sum())
    left_tail_entry_count = int(feature_left_tail.sum())
    left_tail_entry_available = int((feature_left_tail & features_available).sum())
    window_entry_count = int(window_left_tail.sum())
    window_entry_available = int((window_left_tail & windows_available).sum())
    total_left_tail_loss = float(loss_abs.loc[window_left_tail].sum())
    covered_left_tail_loss = float(loss_abs.loc[window_left_tail & windows_available].sum())
    left_tail_entry_coverage_pct = _coverage_pct(window_entry_available, window_entry_count)
    left_tail_loss_coverage_pct = (
        float(covered_left_tail_loss / total_left_tail_loss * 100.0) if total_left_tail_loss else 0.0
    )
    history_selector_ready = (
        left_tail_entry_coverage_pct >= min_left_tail_entry_coverage_pct
        and left_tail_loss_coverage_pct >= min_left_tail_loss_coverage_pct
    )

    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "decision": (
            "stage079_member_rank_history_selector_ready_needs_signal_audit"
            if history_selector_ready
            else "stage079_member_rank_not_history_selector_missing_left_tail"
        ),
        "history_selector_ready": bool(history_selector_ready),
        "all_feature_count": all_feature_count,
        "all_feature_available_count": all_feature_available,
        "all_feature_coverage_pct": _coverage_pct(all_feature_available, all_feature_count),
        "stage038_left_tail_entry_count": left_tail_entry_count,
        "stage038_left_tail_available_count": left_tail_entry_available,
        "stage038_left_tail_entry_coverage_pct": _coverage_pct(left_tail_entry_available, left_tail_entry_count),
        "left_tail_window_entry_count": window_entry_count,
        "left_tail_window_available_count": window_entry_available,
        "left_tail_entry_coverage_pct": left_tail_entry_coverage_pct,
        "left_tail_total_loss_abs": total_left_tail_loss,
        "left_tail_covered_loss_abs": covered_left_tail_loss,
        "left_tail_loss_coverage_pct": left_tail_loss_coverage_pct,
        "thresholds": {
            "max_member_rank_age_days": MAX_MEMBER_RANK_AGE_DAYS,
            "left_tail_start": LEFT_TAIL_START.date().isoformat(),
            "left_tail_end": LEFT_TAIL_END.date().isoformat(),
            "min_left_tail_entry_coverage_pct": min_left_tail_entry_coverage_pct,
            "min_left_tail_loss_coverage_pct": min_left_tail_loss_coverage_pct,
        },
    }


def _year_coverage(joined: pd.DataFrame, label: str) -> pd.DataFrame:
    if joined.empty:
        return pd.DataFrame()
    data = joined.copy()
    data["entry_year"] = pd.to_datetime(data["entry_date"], errors="coerce").dt.year
    data["member_rank_available"] = data["member_rank_available"].fillna(False).astype(bool)
    rows = []
    for year, group in data.groupby("entry_year", dropna=True):
        rows.append(
            {
                "sample": label,
                "entry_year": int(year),
                "entry_count": int(len(group)),
                "available_count": int(group["member_rank_available"].sum()),
                "coverage_pct": _coverage_pct(int(group["member_rank_available"].sum()), int(len(group))),
                "realized_pnl": float(pd.to_numeric(group.get("realized_pnl"), errors="coerce").fillna(0.0).sum()),
                "covered_realized_pnl": float(
                    pd.to_numeric(group.loc[group["member_rank_available"], "realized_pnl"], errors="coerce").fillna(0.0).sum()
                )
                if "realized_pnl" in group.columns
                else 0.0,
            }
        )
    return pd.DataFrame(rows).sort_values(["sample", "entry_year"]).reset_index(drop=True)


def _product_coverage(joined: pd.DataFrame, label: str) -> pd.DataFrame:
    if joined.empty:
        return pd.DataFrame()
    data = joined.copy()
    data["member_rank_available"] = data["member_rank_available"].fillna(False).astype(bool)
    if "product" not in data.columns:
        data["product"] = data["member_rank_product_code"]
    rows = []
    for product, group in data.groupby("product", dropna=False):
        rows.append(
            {
                "sample": label,
                "product": product,
                "entry_count": int(len(group)),
                "available_count": int(group["member_rank_available"].sum()),
                "coverage_pct": _coverage_pct(int(group["member_rank_available"].sum()), int(len(group))),
                "first_entry_date": pd.to_datetime(group["entry_date"], errors="coerce").min(),
                "last_entry_date": pd.to_datetime(group["entry_date"], errors="coerce").max(),
            }
        )
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    result["first_entry_date"] = pd.to_datetime(result["first_entry_date"], errors="coerce").dt.date.astype(str)
    result["last_entry_date"] = pd.to_datetime(result["last_entry_date"], errors="coerce").dt.date.astype(str)
    return result.sort_values(["sample", "coverage_pct", "entry_count"], ascending=[True, True, False]).reset_index(drop=True)


def _source_summary(member_features: pd.DataFrame, raw_member_rows: int) -> dict[str, Any]:
    return {
        "raw_member_rank_rows": int(raw_member_rows),
        "member_feature_rows": int(len(member_features)),
        "member_date_min": member_features["member_date"].min() if not member_features.empty else None,
        "member_date_max": member_features["member_date"].max() if not member_features.empty else None,
        "available_date_min": member_features["available_date"].min() if not member_features.empty else None,
        "available_date_max": member_features["available_date"].max() if not member_features.empty else None,
        "unique_member_dates": int(member_features["member_date"].nunique()) if not member_features.empty else 0,
        "product_count": int(member_features["product_code"].nunique()) if not member_features.empty else 0,
        "products": sorted(member_features["product_code"].dropna().unique().tolist()) if not member_features.empty else [],
        "source_path": str(MEMBER_RANK_PATH),
    }


def _write_report(
    decision: dict[str, Any],
    year_coverage: pd.DataFrame,
    product_coverage: pd.DataFrame,
) -> None:
    REPORT_PATH.write_text(
        "\n".join(
            [
                "# Stage079 member rank PIT coverage audit",
                "",
                f"- 决策：`{decision['decision']}`。",
                "- 类型：国内会员持仓/成交排名源的点时化覆盖审计；不写交易规则、不改线上、不改 AI 池。",
                f"- 点时约束：会员排名按 `T+1` 可见，最大允许旧值 `{MAX_MEMBER_RANK_AGE_DAYS}` 天；同日和未来数据不参与匹配。",
                "- 外部调研：CFTC COT 与 CME OI 资料说明持仓结构、集中度和 OI 有市场动态含义，但都有发布滞后/覆盖门槛；pysystemtrade 的思路也强调可复验的系统化输入，不支持在覆盖不足时硬写规则。",
                "",
                "## 源覆盖",
                "",
                f"- 原始行数：`{decision['source_summary']['raw_member_rank_rows']}`。",
                f"- 聚合后品种-日期行：`{decision['source_summary']['member_feature_rows']}`。",
                f"- 会员日期：`{decision['source_summary']['member_date_min']}` 到 `{decision['source_summary']['member_date_max']}`。",
                f"- 可见日期：`{decision['source_summary']['available_date_min']}` 到 `{decision['source_summary']['available_date_max']}`。",
                f"- 品种数：`{decision['source_summary']['product_count']}`。",
                "",
                "## 关键覆盖结论",
                "",
                f"- Stage038 全样本覆盖：`{decision['all_feature_available_count']}/{decision['all_feature_count']}` = `{decision['all_feature_coverage_pct']:.4f}%`。",
                f"- Stage071 左尾窗口覆盖：`{decision['left_tail_window_available_count']}/{decision['left_tail_window_entry_count']}` = `{decision['left_tail_entry_coverage_pct']:.4f}%`。",
                f"- Stage071 左尾亏损金额覆盖：`{decision['left_tail_covered_loss_abs']:.2f}/{decision['left_tail_total_loss_abs']:.2f}` = `{decision['left_tail_loss_coverage_pct']:.4f}%`。",
                "",
                "## 年度覆盖",
                "",
                _md_table(year_coverage, max_rows=20),
                "",
                "## 覆盖最低品种",
                "",
                _md_table(product_coverage.head(20)),
                "",
                "## 反思",
                "",
                "- 运行前过拟合反思：否；本阶段只审数据是否能作为历史选择器，不根据坏窗口调阈值。",
                "- 运行后过拟合反思：若源无法覆盖 2022 左尾，继续从这份历史源上挖规则就是过拟合。",
                "- 运行前继续价值反思：有；Stage078 已把现有内部字段族基本耗尽，需要验证新 PIT 源。",
                "- 运行后继续价值反思：若缺左尾覆盖，它仍可做 forward monitor，但不能解决当前历史目标。",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_stage_record(decision: dict[str, Any], year_coverage: pd.DataFrame, product_coverage: pd.DataFrame) -> Path:
    stage_path = STAGES_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M')}_stage079_member_rank_pit_coverage_audit.md"
    stage_path.write_text(
        "\n".join(
            [
                "# Stage079 国内会员持仓排名 PIT 覆盖审计",
                "",
                f"- line_id：`{LINE_ID}`",
                "- 当前模式：day",
                f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} CST",
                "- 阶段性质：只读外生源覆盖审计，不改线上、不改 AI 池、不接 CTP/SimNow。",
                "- 是否重要突破：否。",
                "- 是否触发A/B：否。",
                "",
                "## 外部调研与判断",
                "",
                "- 参考资料：CFTC COT 报告说明持仓报告按周发布并存在报告门槛和分类限制；CME OI 教程说明 OI/持仓变化可以反映资金进入或退出；pysystemtrade 作为开源系统化交易框架强调可复验输入和成本/风险纪律。",
                "- 我的判断：会员持仓/排名在经济含义上可能有价值，但必须先证明点时可用和关键左尾覆盖；当前阶段只审覆盖，不写规则。",
                "",
                "## 本次变更",
                "",
                f"- 新增脚本：`research/lines/{LINE_ID}/tools/stage079_member_rank_pit_coverage_audit.py`。",
                f"- 新增测试：`tests/test_rebuilt_c9_stage079_member_rank_pit_coverage_audit.py`。",
                "- 修改脚本：无。",
                "- 删除脚本：无。",
                f"- 新增参数：`MAX_MEMBER_RANK_AGE_DAYS={MAX_MEMBER_RANK_AGE_DAYS}`、`MIN_LEFT_TAIL_ENTRY_COVERAGE_PCT={MIN_LEFT_TAIL_ENTRY_COVERAGE_PCT}`、`MIN_LEFT_TAIL_LOSS_COVERAGE_PCT={MIN_LEFT_TAIL_LOSS_COVERAGE_PCT}`。",
                "- 修改参数：无正式交易参数修改。",
                "- 删除参数：无。",
                "",
                "## 回测/归因参数",
                "",
                "- 数据区间：Stage038 候选 `2020-01-02` 到 `2026-06-24`；Stage071 剩余左尾窗口 `2021-11-01` 到 `2023-10-18`；会员排名源 `2023-01-03` 到 `2026-04-17`。",
                "- 账户规模：不适用，本阶段无资金曲线回测。",
                "- 成本口径：不适用，本阶段无交易回放。",
                "- 样本过滤：会员排名 `T+1` 可见，最大旧值 7 天；同日/未来数据禁止匹配。",
                "- 策略/归因口径：Stage038 全候选 + Stage071 剩余左尾 entries 的 PIT 覆盖审计。",
                "",
                "## 结果",
                "",
                "- 期末权益：不适用。",
                "- 总收益：不适用。",
                "- 最大回撤：不适用。",
                "- Sharpe：不适用。",
                "- 总滑点：不适用。",
                "- 总交易次数：不适用。",
                "- 胜率：不适用。",
                f"- 决策：`{decision['decision']}`。",
                f"- Stage038 全样本覆盖：`{decision['all_feature_available_count']}/{decision['all_feature_count']}` = `{decision['all_feature_coverage_pct']:.4f}%`。",
                f"- Stage071 左尾窗口覆盖：`{decision['left_tail_window_available_count']}/{decision['left_tail_window_entry_count']}` = `{decision['left_tail_entry_coverage_pct']:.4f}%`。",
                f"- Stage071 左尾亏损金额覆盖：`{decision['left_tail_covered_loss_abs']:.2f}/{decision['left_tail_total_loss_abs']:.2f}` = `{decision['left_tail_loss_coverage_pct']:.4f}%`。",
                "",
                "## 输出文件",
                "",
                f"- report：`{REPORT_PATH}`",
                f"- summary：`{DECISION_PATH}`",
                f"- daily/features：`{MEMBER_FEATURES_PATH}`",
                f"- joined：`{JOINED_FEATURES_PATH}`、`{JOINED_WINDOWS_PATH}`",
                f"- coverage：`{YEAR_COVERAGE_PATH}`、`{PRODUCT_COVERAGE_PATH}`",
                "",
                "## 年度覆盖",
                "",
                _md_table(year_coverage, max_rows=20),
                "",
                "## 覆盖最低品种",
                "",
                _md_table(product_coverage.head(20)),
                "",
                "## 结论",
                "",
                f"- 本阶段结论：`{decision['decision']}`；国内会员排名源缺 2022 左尾，不能作为当前历史目标的选择器，只能保留 forward monitor 或后续补历史后再审。",
                "- 是否进入下一步：不进入规则/proxy/真引擎。",
                "- 下一步：寻找覆盖 2022-2023 左尾的新 PIT 信息源，或者把会员排名只作为 2023 以后 forward 观察，不用它修当前目标。",
                "",
                "## 过拟合反思",
                "",
                "- 运行前判断：否；只做覆盖审计，不用坏窗口回推阈值。",
                "- 运行后判断：若基于覆盖不足的会员排名继续挖历史规则，就是过拟合。",
                "- 原因：关键亏损期缺数据，任何后验阈值都无法证明当时可用。",
                "",
                "## 继续价值反思",
                "",
                "- 运行前判断：有；Stage078 后需要验证新 PIT 源。",
                "- 运行后判断：会员排名对当前目标继续价值低，但可保留 forward monitor。",
                "- 原因：它的源从 2023-01-03 才开始，关键 2022 左尾覆盖不足。",
                "",
                "## 合入建议",
                "",
                "- 是否更新本线 `LINE.md`：是，记录 Stage079 关闭该历史选择器方向。",
                "- 是否更新 `research/registry.md`：是，最新关键阶段推进到 Stage079。",
                "- 是否追加根目录 `memory.md/back_log.md`：仅追加 `back_log.md` 重要摘要，不改 `memory.md`。",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return stage_path


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)

    raw_member = _read_csv(MEMBER_RANK_PATH)
    features = _read_csv(FEATURE_MATRIX_PATH)
    windows = _read_csv(WINDOW_ENTRIES_PATH)

    member_features = normalize_member_rank_history(raw_member)
    joined_features = attach_member_rank_asof(features, member_features)
    joined_windows = attach_member_rank_asof(windows, member_features)
    decision = summarize_member_rank_coverage(joined_features, joined_windows)
    decision["source_summary"] = _source_summary(member_features, len(raw_member))

    year_coverage = pd.concat(
        [_year_coverage(joined_features, "stage038_all"), _year_coverage(joined_windows, "stage071_left_tail")],
        ignore_index=True,
        sort=False,
    )
    product_coverage = pd.concat(
        [_product_coverage(joined_features, "stage038_all"), _product_coverage(joined_windows, "stage071_left_tail")],
        ignore_index=True,
        sort=False,
    )

    member_features.to_csv(MEMBER_FEATURES_PATH, index=False, encoding="utf-8-sig")
    joined_features.to_csv(JOINED_FEATURES_PATH, index=False, encoding="utf-8-sig")
    joined_windows.to_csv(JOINED_WINDOWS_PATH, index=False, encoding="utf-8-sig")
    year_coverage.to_csv(YEAR_COVERAGE_PATH, index=False, encoding="utf-8-sig")
    product_coverage.to_csv(PRODUCT_COVERAGE_PATH, index=False, encoding="utf-8-sig")
    _write_report(decision, year_coverage, product_coverage)
    stage_path = _write_stage_record(decision, year_coverage, product_coverage)
    decision["stage_record_path"] = str(stage_path)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    return decision


if __name__ == "__main__":
    print(json.dumps(_json_safe(run()), ensure_ascii=False, indent=2))
