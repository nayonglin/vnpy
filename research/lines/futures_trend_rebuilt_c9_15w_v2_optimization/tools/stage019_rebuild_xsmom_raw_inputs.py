from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
PORTFOLIO_DIR = PROJECT_DIR / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

import analyze_qmt_roll_stage345_cross_sectional_momentum_satellite as s345  # noqa: E402
from qmt_universe import VT_SYMBOLS  # noqa: E402


LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage019"
MODEL_TAG = "stage019_rebuild_xsmom_raw_inputs_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage019_rebuild_xsmom_raw_inputs"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage019_rebuild_xsmom_raw_inputs"
STAGES_DIR = LINE_DIR / "stages"

PRODUCT_RETURN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_returns_{MODEL_TAG}.csv"
FEATURE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_features_{MODEL_TAG}.csv"
SATELLITE_DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_satellite_daily_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
STAGE_RECORD_PATH = STAGES_DIR / "20260702_0548_stage019_rebuild_xsmom_raw_inputs.md"

EXTRA_PRODUCTS = ("jd.DCE",)
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
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return str(value)
    return value


def selected_products() -> list[str]:
    return sorted(set(VT_SYMBOLS) | set(EXTRA_PRODUCTS))


def _csv_list_count(value: Any) -> int:
    if pd.isna(value):
        return 0
    text = str(value).strip()
    if not text:
        return 0
    return len([item for item in text.split(",") if item.strip()])


def summarize_product_returns(frame: pd.DataFrame, *, min_valid_products: int = s345.MIN_VALID_PRODUCTS) -> dict[str, Any]:
    if frame.empty:
        return {
            "rows": 0,
            "products": 0,
            "start_date": "",
            "end_date": "",
            "last_date_with_min_valid_products": "",
            "all_missing_close_dates": 0,
            "missing_main_close_rows": 0,
            "nonzero_return_rows": 0,
        }
    data = frame.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    data["main_close"] = pd.to_numeric(data["main_close"], errors="coerce")
    data["product_return"] = pd.to_numeric(data["product_return"], errors="coerce").fillna(0.0)
    valid_close_counts = data.groupby("date")["main_close"].apply(lambda series: int(series.notna().sum()))
    valid_dates = valid_close_counts[valid_close_counts >= int(min_valid_products)]
    last_valid_date = pd.Timestamp(valid_dates.index.max()).date().isoformat() if not valid_dates.empty else ""
    return {
        "rows": int(len(data)),
        "products": int(data["product_vt_symbol"].nunique()),
        "start_date": pd.Timestamp(data["date"].min()).date().isoformat(),
        "end_date": pd.Timestamp(data["date"].max()).date().isoformat(),
        "last_date_with_min_valid_products": last_valid_date,
        "all_missing_close_dates": int((valid_close_counts == 0).sum()),
        "missing_main_close_rows": int(data["main_close"].isna().sum()),
        "nonzero_return_rows": int((data["product_return"].abs() > 0).sum()),
    }


def summarize_satellite_signals(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {
            "rows": 0,
            "specs": 0,
            "start_date": "",
            "end_date": "",
            "active_signal_rows": 0,
            "max_long_count": 0,
            "max_short_count": 0,
        }
    data = frame.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    long_count = data["long_products"].map(_csv_list_count)
    short_count = data["short_products"].map(_csv_list_count)
    return {
        "rows": int(len(data)),
        "specs": int(data["spec"].nunique()),
        "start_date": pd.Timestamp(data["date"].min()).date().isoformat(),
        "end_date": pd.Timestamp(data["date"].max()).date().isoformat(),
        "active_signal_rows": int(((long_count + short_count) > 0).sum()),
        "max_long_count": int(long_count.max()) if len(long_count) else 0,
        "max_short_count": int(short_count.max()) if len(short_count) else 0,
    }


def assess_rebuild(
    *,
    product_summary: dict[str, Any],
    feature_rows: int,
    signal_summary: dict[str, Any],
    target_end_date: str = TARGET_END_DATE,
) -> dict[str, Any]:
    raw_ready = (
        int(product_summary.get("rows", 0)) > 0
        and int(product_summary.get("products", 0)) >= s345.MIN_VALID_PRODUCTS
        and int(feature_rows) > 0
        and int(signal_summary.get("rows", 0)) > 0
        and int(signal_summary.get("active_signal_rows", 0)) > 0
        and int(signal_summary.get("specs", 0)) > 0
    )
    last_valid_text = str(product_summary.get("last_date_with_min_valid_products", "") or "")
    target = pd.Timestamp(target_end_date).normalize()
    coverage_ready = bool(last_valid_text) and pd.Timestamp(last_valid_text).normalize() >= target
    ready = raw_ready and coverage_ready
    if ready:
        decision = "stage019_xsmom_raw_inputs_rebuilt_ready_for_proxy"
    elif raw_ready and not coverage_ready:
        decision = "stage019_xsmom_raw_inputs_need_daily_backfill_keep_readonly"
    else:
        decision = "stage019_xsmom_raw_inputs_incomplete_keep_readonly"
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "decision": decision,
        "ready_for_stage020_proxy": bool(ready),
        "raw_shape_rebuilt": bool(raw_ready),
        "coverage_ready_for_target_end": bool(coverage_ready),
        "target_end_date": target.date().isoformat(),
        "product_summary": product_summary,
        "feature_rows": int(feature_rows),
        "signal_summary": signal_summary,
    }


def write_report(summary: dict[str, Any]) -> None:
    product_summary = summary["product_summary"]
    signal_summary = summary["signal_summary"]
    lines = [
        "# Stage019 xsmom 原始输入重建",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 阶段性质：只重建低相关收益腿原始输入，不跑旧 C3 组合，不产生正式候选，不改实盘。",
        f"- 决策：`{summary['decision']}`",
        "",
        "## 调研判断",
        "",
        "- 外部趋势跟随资料支持使用跨规则/横截面动量作为低相关收益源，但必须先保证本地输入可复验。",
        "- 旧 Stage345 绑定 C3 组合日报；当前二期线只复用其产品收益与横截面动量构造，不复用旧 C3 组合评估。",
        "- 本阶段显式把 `jd.DCE` 加入研究输入池；这不代表线上 AI 池或实盘池已经改变。",
        "",
        "## 输入池",
        "",
        f"- 请求产品数：`{len(selected_products())}`。",
        f"- 额外加入：`{', '.join(EXTRA_PRODUCTS)}`。",
        "",
        "## 输出摘要",
        "",
        f"- product_returns rows：`{product_summary['rows']}`，products：`{product_summary['products']}`，名义区间：`{product_summary['start_date']} -> {product_summary['end_date']}`。",
        f"- 有效结束日（每天至少 `{s345.MIN_VALID_PRODUCTS}` 个产品有 close）：`{product_summary['last_date_with_min_valid_products']}`；目标终点：`{summary['target_end_date']}`。",
        f"- product_returns missing_main_close_rows：`{product_summary['missing_main_close_rows']}`，all_missing_close_dates：`{product_summary['all_missing_close_dates']}`，nonzero_return_rows：`{product_summary['nonzero_return_rows']}`。",
        f"- features rows：`{summary['feature_rows']}`。",
        f"- satellite rows：`{signal_summary['rows']}`，specs：`{signal_summary['specs']}`，active_signal_rows：`{signal_summary['active_signal_rows']}`。",
        f"- max long/short count：`{signal_summary['max_long_count']}` / `{signal_summary['max_short_count']}`。",
        "",
        "## 输出文件",
        "",
        f"- product_returns：`{PRODUCT_RETURN_PATH.relative_to(PROJECT_DIR)}`",
        f"- features：`{FEATURE_PATH.relative_to(PROJECT_DIR)}`",
        f"- satellite_daily：`{SATELLITE_DAILY_PATH.relative_to(PROJECT_DIR)}`",
        f"- summary：`{SUMMARY_PATH.relative_to(PROJECT_DIR)}`",
        "",
        "## 过拟合反思",
        "",
        "- 运行前判断：否。原因：本阶段只恢复预声明输入链，不看回测结果调参数。",
        "- 运行后判断：否。原因：没有根据收益筛品种、日期、方向或权重；`jd.DCE` 是用户目标中的基础池扩展要求。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前判断：是。原因：Stage018 已确认低相关腿方向有历史线索但输入缺失。",
        "- 运行后判断：是，但若有效结束日早于目标终点，必须先补日线覆盖，不能把缺 close 的 0 收益尾部拿去做 proxy。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    STAGE_RECORD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    products = selected_products()
    product_returns = s345._load_main_product_returns(products)
    features = s345._build_momentum_features(product_returns)
    satellite = s345._build_satellite_returns(features, product_returns)

    product_returns.to_csv(PRODUCT_RETURN_PATH, index=False, encoding="utf-8-sig")
    features.to_csv(FEATURE_PATH, index=False, encoding="utf-8-sig")
    satellite.to_csv(SATELLITE_DAILY_PATH, index=False, encoding="utf-8-sig")

    summary = assess_rebuild(
        product_summary=summarize_product_returns(product_returns),
        feature_rows=len(features),
        signal_summary=summarize_satellite_signals(satellite),
        target_end_date=TARGET_END_DATE,
    )
    SUMMARY_PATH.write_text(json.dumps(_json_safe(summary), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_report(summary)
    print(json.dumps(_json_safe(summary), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
