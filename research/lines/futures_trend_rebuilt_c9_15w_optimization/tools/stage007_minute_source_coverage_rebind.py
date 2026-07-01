from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
TOOLS_DIR = Path(__file__).resolve().parent
PORTFOLIO_DIR = PROJECT_DIR / "examples" / "portfolio_backtesting"
for path in (str(TOOLS_DIR), str(PORTFOLIO_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

import stage006_current_quality_feature_binder as s006


LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage007"
MODEL_TAG = "stage007_minute_source_coverage_rebind_v1"
OUTPUT_PREFIX = "rebuilt_c9_stage007_minute_source_coverage_rebind"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage007_minute_source_coverage_rebind"
BT_OUTPUT_DIR = PORTFOLIO_DIR / "backtest_outputs"
STAGE006_OUTPUT_DIR = LINE_DIR / "outputs" / "stage006_current_quality_feature_binder"

STAGE006_CLOSED_LOTS_PATH = (
    STAGE006_OUTPUT_DIR
    / "rebuilt_c9_stage006_current_quality_feature_binder_closed_lots_"
    "stage006_current_quality_feature_binder_v1.csv"
)

MINUTE_SOURCE_CANDIDATES = {
    "stage861_visual_atlas": (
        BT_OUTPUT_DIR
        / "qmt_roll_stage861_stage860_full_visual_atlas_full_minute_bars_"
        "stage861_stage860_full_visual_atlas_v1.csv"
    ),
    "stage449_session_rebuild": (
        BT_OUTPUT_DIR
        / "qmt_roll_stage449_minute_session_rebuild_full_minute_bars_"
        "stage449_minute_session_rebuild_full_v1.csv"
    ),
    "stage152_complete": (
        BT_OUTPUT_DIR
        / "qmt_roll_stage152_stage861_candidate_stage449_859_stage900complete_full_minute_bars_v1.csv"
    ),
    "stage152_local": (
        BT_OUTPUT_DIR
        / "qmt_roll_stage152_stage861_candidate_stage449_859_stage900local_full_minute_bars_v1.csv"
    ),
    "stage152_raw": (
        BT_OUTPUT_DIR
        / "qmt_roll_stage152_stage861_candidate_stage449_859_900raw_full_minute_bars_v1.csv"
    ),
    "stage900_gap_backfill": (
        BT_OUTPUT_DIR
        / "qmt_roll_stage900_stage898_c9_gap_backfill_minute_bars_stage900_stage898_c9_gap_backfill_v1.csv"
    ),
}
PRIMARY_SOURCE_ID = "stage152_complete"
PRIMARY_MINUTE_PATH = MINUTE_SOURCE_CANDIDATES[PRIMARY_SOURCE_ID]

COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coverage_compare_{MODEL_TAG}.csv"
QUALITY_FEATURES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_quality_features_{MODEL_TAG}.csv"
QUALITY_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_quality_summary_{MODEL_TAG}.csv"
ANNUAL_QUALITY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_quality_{MODEL_TAG}.csv"
MISSING_LOTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_missing_lots_{MODEL_TAG}.csv"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coverage_quality_chart_{MODEL_TAG}.png"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _json_safe(value: Any) -> Any:
    return s006._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s006._md_table(frame, max_rows=max_rows)


def _entry_pairs(lots: pd.DataFrame) -> pd.DataFrame:
    pairs = lots[["vt_symbol", "entry_date"]].copy()
    pairs["entry_date_key"] = pd.to_datetime(pairs["entry_date"], errors="coerce").dt.date.astype(str)
    return pairs[["vt_symbol", "entry_date_key"]]


def _minute_pairs(path: Path) -> tuple[pd.DataFrame, pd.Series]:
    header = pd.read_csv(path, encoding="utf-8-sig", nrows=0)
    columns = set(header.columns)
    if "bar_date" in columns:
        usecols = ["vt_symbol", "bar_date"]
        if "minute_source" in columns:
            usecols.append("minute_source")
        bars = pd.read_csv(path, encoding="utf-8-sig", usecols=usecols)
        bars["entry_date_key"] = bars["bar_date"].astype(str)
    elif "bar_datetime" in columns:
        usecols = ["vt_symbol", "bar_datetime"]
        if "minute_source" in columns:
            usecols.append("minute_source")
        bars = pd.read_csv(path, encoding="utf-8-sig", usecols=usecols)
        bars["entry_date_key"] = pd.to_datetime(bars["bar_datetime"], errors="coerce").dt.date.astype(str)
    elif "datetime" in columns:
        usecols = ["vt_symbol", "datetime"]
        if "minute_source" in columns:
            usecols.append("minute_source")
        bars = pd.read_csv(path, encoding="utf-8-sig", usecols=usecols)
        bars["entry_date_key"] = pd.to_datetime(bars["datetime"], errors="coerce").dt.date.astype(str)
    else:
        raise RuntimeError(f"Minute file has no usable date column: {path}")

    pairs = bars[["vt_symbol", "entry_date_key"]].dropna().drop_duplicates()
    source_counts = (
        bars["minute_source"].value_counts(dropna=False)
        if "minute_source" in bars.columns
        else pd.Series({"missing_minute_source_column": len(bars)})
    )
    return pairs, source_counts


def _coverage_compare(lots: pd.DataFrame) -> pd.DataFrame:
    lot_pairs = _entry_pairs(lots)
    rows: list[dict[str, Any]] = []
    for source_id, path in MINUTE_SOURCE_CANDIDATES.items():
        if not path.exists():
            rows.append(
                {
                    "source_id": source_id,
                    "path": str(path),
                    "exists": 0,
                    "minute_pairs": 0,
                    "covered_lots": 0,
                    "total_lots": int(len(lots)),
                    "coverage_pct": 0.0,
                    "minute_source_counts": "",
                }
            )
            continue
        pairs, source_counts = _minute_pairs(path)
        hit = (
            lot_pairs.merge(pairs.assign(hit=1), on=["vt_symbol", "entry_date_key"], how="left")["hit"]
            .fillna(0)
            .astype(bool)
        )
        rows.append(
            {
                "source_id": source_id,
                "path": str(path),
                "exists": 1,
                "minute_pairs": int(len(pairs)),
                "covered_lots": int(hit.sum()),
                "total_lots": int(len(lots)),
                "coverage_pct": float(hit.mean() * 100.0),
                "minute_source_counts": "; ".join(f"{k}={int(v)}" for k, v in source_counts.items()),
            }
        )
    return pd.DataFrame(rows).sort_values(["covered_lots", "minute_pairs"], ascending=[False, False]).reset_index(drop=True)


def _rebind_quality(lots: pd.DataFrame) -> pd.DataFrame:
    original_path = s006.MINUTE_BARS_PATH
    try:
        s006.MINUTE_BARS_PATH = PRIMARY_MINUTE_PATH
        features = s006._build_quality_features(lots)
    finally:
        s006.MINUTE_BARS_PATH = original_path
    if not features.empty:
        features["minute_binder_source_id"] = PRIMARY_SOURCE_ID
        features["minute_binder_path"] = str(PRIMARY_MINUTE_PATH)
    return features


def _missing_lots(features: pd.DataFrame) -> pd.DataFrame:
    if features.empty:
        return pd.DataFrame()
    missing = features[~features["entry_first_bar_available"].astype(bool)].copy()
    keep = [
        "requested_start_month",
        "lot_id",
        "vt_symbol",
        "product",
        "direction",
        "entry_date",
        "exit_date",
        "realized_pnl",
        "r_multiple",
        "ai_product_pool_rank",
    ]
    return missing[[column for column in keep if column in missing.columns]].reset_index(drop=True)


def _plot(coverage: pd.DataFrame, quality: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(18, 7), constrained_layout=True)
    ax = axes[0]
    x = np.arange(len(coverage))
    ax.bar(x, coverage["coverage_pct"], color="#2563eb")
    ax.set_xticks(x)
    ax.set_xticklabels(coverage["source_id"], rotation=35, ha="right")
    ax.set_title("Minute Source Coverage For Stage006 Closed Lots")
    ax.set_ylabel("coverage %")
    ax.set_ylim(0, max(105.0, float(coverage["coverage_pct"].max()) * 1.08))
    ax.grid(True, axis="y", alpha=0.25)

    ax = axes[1]
    plot = quality.copy()
    x = np.arange(len(plot))
    ax.bar(x, plot["pnl_sum"], color=np.where(plot["pnl_sum"].ge(0), "#16a34a", "#dc2626"))
    ax.set_xticks(x)
    ax.set_xticklabels(plot["bucket"], rotation=45, ha="right")
    ax.set_title("Rebound Quality Bucket PnL")
    ax.set_ylabel("realized pnl")
    ax.grid(True, axis="y", alpha=0.25)
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(decision: dict[str, Any], coverage: pd.DataFrame, quality: pd.DataFrame, missing: pd.DataFrame) -> None:
    lines = [
        f"# {STAGE} 分钟源覆盖修复与质量标签重绑",
        "",
        f"- 生成时间：`{decision['generated_at']}`",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        "- 阶段性质：只读覆盖审计；读取 Stage006 closed_lots，不重跑策略，不改实盘，不连接 CTP，不调用下单。",
        f"- 主绑定分钟源：`{PRIMARY_SOURCE_ID}`",
        "",
        "## 外部调研判断",
        "",
        "- TqSdk 官方文档显示历史 K 线通过 `get_kline_serial` 获取，且 TqSdk 与 vn.py 的 K 线生成/保存机制不同；研究场景应优先使用已下载 CSV。",
        "- PBO/DSR 资料继续约束本线：本阶段只修复数据绑定证据，不按质量桶结果调参。",
        "- Meta-labeling 只能在标签覆盖和时间稳定性足够后作为二级风险预算方法，不能用低覆盖标签直接加仓。",
        "",
        "## 分钟源覆盖对比",
        "",
        _md_table(coverage, max_rows=20),
        "",
        "## 重绑质量桶统计",
        "",
        _md_table(quality, max_rows=30),
        "",
        "## 仍缺首分钟的 lot",
        "",
        _md_table(missing, max_rows=30),
        "",
        "## 判断",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 过拟合反思：{decision['overfit_reflection_after']}",
        f"- 继续价值反思：{decision['continue_value_after']}",
        "",
        "## 输出文件",
        "",
    ]
    for key, path in decision["outputs"].items():
        lines.append(f"- {key}: `{path}`")
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    closed_lots = pd.read_csv(STAGE006_CLOSED_LOTS_PATH, encoding="utf-8-sig")
    coverage = _coverage_compare(closed_lots)
    features = _rebind_quality(closed_lots)
    quality = s006._quality_summary(features)
    annual = s006._annual_quality(features)
    missing = _missing_lots(features)
    _plot(coverage, quality)

    coverage.to_csv(COVERAGE_PATH, index=False, encoding="utf-8-sig")
    features.to_csv(QUALITY_FEATURES_PATH, index=False, encoding="utf-8-sig")
    quality.to_csv(QUALITY_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    annual.to_csv(ANNUAL_QUALITY_PATH, index=False, encoding="utf-8-sig")
    missing.to_csv(MISSING_LOTS_PATH, index=False, encoding="utf-8-sig")

    best = coverage.iloc[0].to_dict() if not coverage.empty else {}
    ai46 = (
        quality[quality["bucket"].astype(str).eq("ai4_6_entry_or_first_aligned")].iloc[0].to_dict()
        if not quality.empty and quality["bucket"].astype(str).eq("ai4_6_entry_or_first_aligned").any()
        else {}
    )
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "stage006_closed_lots": int(len(closed_lots)),
        "primary_source_id": PRIMARY_SOURCE_ID,
        "primary_minute_path": str(PRIMARY_MINUTE_PATH),
        "best_source_id": best.get("source_id", ""),
        "best_source_coverage_pct": best.get("coverage_pct", 0.0),
        "entry_first_bar_available": int(features["entry_first_bar_available"].sum()) if not features.empty else 0,
        "entry_first_bar_coverage_pct": (
            float(features["entry_first_bar_available"].mean() * 100.0) if len(features) else 0.0
        ),
        "missing_lots": int(len(missing)),
        "ai4_6_entry_or_first_aligned_lots": int(ai46.get("lot_count", 0)),
        "ai4_6_entry_or_first_aligned_years": int(ai46.get("year_count", 0)),
        "ai4_6_entry_or_first_aligned_pnl": float(ai46.get("pnl_sum", 0.0)),
        "decision": "stage007_minute_binding_repaired_but_quality_bucket_still_readonly_no_engine_change",
        "strategy_changed": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "external_research_judgment": (
            "TqSdk/vn.py minute construction differences justify comparing local CSV sources first. "
            "PBO/DSR guardrails prevent promoting the improved labels without frozen proxy and true-engine validation."
        ),
        "overfit_reflection_before": (
            "否。目标是定位 Stage006 分钟覆盖缺口，变量只有分钟源选择，不调交易规则。"
        ),
        "continue_value_before": (
            "是。若覆盖缺口来自源选择错误，修复后才有资格继续做高质量信号代理。"
        ),
        "overfit_reflection_after": (
            "否。本阶段只比较既有分钟 CSV 的覆盖并重绑固定 0R 方向标签，没有按结果调参或改 C9。"
        ),
        "continue_value_after": (
            "有，但仍需只读代理。覆盖已接近完整，旧 ai4_6∩aligned 标签样本扩大后才能评估；不能直接上线或加仓。"
        ),
        "outputs": {
            "coverage_compare": str(COVERAGE_PATH),
            "quality_features": str(QUALITY_FEATURES_PATH),
            "quality_summary": str(QUALITY_SUMMARY_PATH),
            "annual_quality": str(ANNUAL_QUALITY_PATH),
            "missing_lots": str(MISSING_LOTS_PATH),
            "chart": str(CHART_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(decision, coverage, quality, missing)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print("coverage")
    print(coverage.to_string(index=False))
    print("quality_summary")
    print(quality.to_string(index=False))


if __name__ == "__main__":
    main()
