from __future__ import annotations

from datetime import datetime
import json
import math
import os
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
sys.path.insert(0, str(PROJECT_DIR.resolve()))

os.environ.setdefault("STAGE459_RAW_SUBDIR", "tqsdk_stage491_covered_key_full_session_backfill")
os.environ.setdefault("STAGE459_DISABLE_TQSDK_PRINT", "1")

import analyze_qmt_roll_stage459_completed_preclose_full_bar_shard as s459  # noqa: E402


STAGE_NAME = os.getenv("STAGE491_STAGE_NAME", "Stage191")
MODEL_TAG = os.getenv("STAGE491_MODEL_TAG", "stage491_covered_key_full_session_backfill_001_010_v1")
OUTPUT_PREFIX = os.getenv("STAGE491_OUTPUT_PREFIX", "qmt_roll_stage491_covered_key_full_session_backfill_shard")
LINE_ID = "futures_trend_drawdown30_preserve_return"

STAGE190_GAP_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage490_all_required_preclose_full_bar_readiness_gap_stage490_all_required_preclose_full_bar_readiness_v1.csv"
)

START_SPAN = int(os.getenv("STAGE491_START_SPAN", "1"))
MAX_SPANS = int(os.getenv("STAGE491_MAX_SPANS", "10"))
MAX_DATES_PER_SYMBOL = int(os.getenv("STAGE491_MAX_DATES_PER_SYMBOL", "0"))
MIN_PRECLOSE_BAR_COUNT = int(os.getenv("STAGE491_MIN_PRECLOSE_BAR_COUNT", "200"))
MIN_FILL_BAR_COUNT = int(os.getenv("STAGE491_MIN_FILL_BAR_COUNT", "4"))

PLAN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_download_plan_{MODEL_TAG}.csv"
TARGETS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_selected_targets_{MODEL_TAG}.csv"
STATUS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_extract_status_{MODEL_TAG}.csv"
BARS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_completed_minute_bars_{MODEL_TAG}.csv"
SYNTH_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_synthetic_preclose_bars_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
GAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gap_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "无数据。"
    view = frame.copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda value: f"{value:.4f}" if pd.notna(value) else "")
    return view.to_markdown(index=False)


def _load_gap() -> pd.DataFrame:
    gap = pd.read_csv(STAGE190_GAP_PATH, encoding="utf-8-sig")
    gap["date"] = pd.to_datetime(gap["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    gap["has_preclose_1455_1500"] = pd.to_numeric(
        gap.get("has_preclose_1455_1500", 0), errors="coerce"
    ).fillna(0).astype(int)
    gap = gap[
        gap["date"].notna()
        & gap["vt_symbol"].notna()
        & gap["product_vt_symbol"].notna()
        & gap["has_preclose_1455_1500"].eq(1)
    ].copy()
    return gap.sort_values(["vt_symbol", "date", "product_vt_symbol"]).reset_index(drop=True)


def _build_plan(gap: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (vt_symbol, product_vt_symbol), frame in gap.groupby(["vt_symbol", "product_vt_symbol"], sort=False):
        dates = sorted(pd.Timestamp(date).normalize() for date in frame["date"].unique())
        if not dates:
            continue
        span_start = dates[0]
        previous = dates[0]
        span_dates = [dates[0]]
        for date in dates[1:]:
            if (date - previous).days > 14:
                rows.append(
                    {
                        "vt_symbol": str(vt_symbol),
                        "product_vt_symbol": str(product_vt_symbol),
                        "exchange": s459._exchange(str(vt_symbol)),
                        "span_start": span_start,
                        "span_end": previous,
                        "target_dates": len(span_dates),
                        "span_calendar_days": int((previous - span_start).days) + 1,
                    }
                )
                span_start = date
                span_dates = []
            span_dates.append(date)
            previous = date
        rows.append(
            {
                "vt_symbol": str(vt_symbol),
                "product_vt_symbol": str(product_vt_symbol),
                "exchange": s459._exchange(str(vt_symbol)),
                "span_start": span_start,
                "span_end": previous,
                "target_dates": len(span_dates),
                "span_calendar_days": int((previous - span_start).days) + 1,
            }
        )
    plan = pd.DataFrame(rows)
    if plan.empty:
        return plan
    plan = plan.sort_values(["target_dates", "span_calendar_days"], ascending=[False, False]).reset_index(drop=True)
    plan.insert(0, "plan_rank", np.arange(1, len(plan) + 1))
    return plan


def _select_targets(gap: pd.DataFrame, plan: pd.DataFrame) -> pd.DataFrame:
    selected_plan = plan[plan["plan_rank"].ge(START_SPAN)].copy()
    if MAX_SPANS > 0:
        selected_plan = selected_plan.head(MAX_SPANS)
    rows: list[dict[str, Any]] = []
    for plan_row in selected_plan.itertuples(index=False):
        dates = gap[
            gap["vt_symbol"].astype(str).eq(str(plan_row.vt_symbol))
            & gap["product_vt_symbol"].astype(str).eq(str(plan_row.product_vt_symbol))
            & (gap["date"] >= pd.Timestamp(plan_row.span_start))
            & (gap["date"] <= pd.Timestamp(plan_row.span_end))
        ].sort_values("date")
        if MAX_DATES_PER_SYMBOL > 0:
            dates = dates.head(MAX_DATES_PER_SYMBOL)
        for date_row in dates.itertuples(index=False):
            rows.append(
                {
                    "plan_rank": int(plan_row.plan_rank),
                    "vt_symbol": str(plan_row.vt_symbol),
                    "exchange": str(plan_row.exchange),
                    "product_vt_symbol": str(plan_row.product_vt_symbol),
                    "date": pd.Timestamp(date_row.date).normalize(),
                    "span_start": pd.Timestamp(plan_row.span_start).normalize(),
                    "span_end": pd.Timestamp(plan_row.span_end).normalize(),
                    "missing_dates_in_span": int(plan_row.target_dates),
                    "span_calendar_days": int(plan_row.span_calendar_days),
                }
            )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(["plan_rank", "vt_symbol", "date"]).reset_index(drop=True)


def _strict_gap_reason(row: pd.Series) -> str:
    if int(row.get("valid_ohlc", 0)) != 1:
        return "invalid_or_missing_ohlc"
    if int(row.get("preclose_bar_count", 0)) < MIN_PRECLOSE_BAR_COUNT:
        return "short_preclose_session"
    if int(row.get("volume_ok", 0)) != 1:
        return "preclose_volume_not_positive"
    if int(row.get("open_interest_ok", 0)) != 1:
        return "open_interest_missing"
    if int(row.get("fill_bar_count", 0)) < MIN_FILL_BAR_COUNT or int(row.get("fill_ok", 0)) != 1:
        return "fill_window_missing"
    if int(row.get("full_bar_ready", 0)) != 1:
        return "full_bar_ready_false"
    return ""


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    gap = _load_gap()
    plan = _build_plan(gap)
    plan.to_csv(PLAN_PATH, index=False, encoding="utf-8-sig")
    targets = _select_targets(gap, plan)
    targets.to_csv(TARGETS_PATH, index=False, encoding="utf-8-sig")
    if targets.empty:
        raise RuntimeError("No Stage491 targets selected.")

    username, password = s459._require_credentials()
    status_rows: list[dict[str, Any]] = []
    bar_frames: list[pd.DataFrame] = []
    for vt_symbol, frame in targets.groupby("vt_symbol", sort=False):
        status, bars = s459._extract_symbol(str(vt_symbol), list(pd.to_datetime(frame["date"])), username, password)
        status_rows.append(status)
        if not bars.empty:
            bar_frames.append(bars)

    status_df = pd.DataFrame(status_rows)
    status_df.to_csv(STATUS_PATH, index=False, encoding="utf-8-sig")
    bars_df = pd.concat(bar_frames, ignore_index=True) if bar_frames else pd.DataFrame()
    if not bars_df.empty:
        bars_df = bars_df.drop_duplicates(["vt_symbol", "bar_datetime"]).sort_values(["vt_symbol", "bar_datetime"])
    bars_df.to_csv(BARS_PATH, index=False, encoding="utf-8-sig")

    synth = s459._synthesize_for_targets(targets, bars_df)
    if not synth.empty:
        for column in ["full_bar_ready", "valid_ohlc", "volume_ok", "open_interest_ok", "fill_ok", "preclose_bar_count", "fill_bar_count"]:
            synth[column] = pd.to_numeric(synth.get(column, 0), errors="coerce").fillna(0).astype(int)
        synth["strict_gap_reason"] = synth.apply(_strict_gap_reason, axis=1)
        synth["strict_full_preclose_ready"] = synth["strict_gap_reason"].eq("").astype(int)
    synth.to_csv(SYNTH_PATH, index=False, encoding="utf-8-sig")
    synth_gap = synth[synth["strict_full_preclose_ready"].eq(0)].copy() if not synth.empty else pd.DataFrame()
    synth_gap.to_csv(GAP_PATH, index=False, encoding="utf-8-sig")

    target_count = int(len(targets))
    ready_count = int(synth["strict_full_preclose_ready"].sum()) if not synth.empty else 0
    failed_symbol_count = int(status_df["status"].astype(str).eq("failed").sum()) if not status_df.empty else 0
    timeout_count = int(status_df["status"].astype(str).eq("timeout").sum()) if not status_df.empty else 0
    status_values = ",".join(sorted(status_df["status"].astype(str).unique())) if not status_df.empty else ""
    summary = pd.DataFrame(
        [
            {
                "stage": STAGE_NAME,
                "model_tag": MODEL_TAG,
                "start_span": START_SPAN,
                "max_spans": MAX_SPANS,
                "max_dates_per_symbol": MAX_DATES_PER_SYMBOL,
                "total_gap_keys": int(len(gap)),
                "download_plan_spans": int(len(plan)),
                "selected_span_count": int(targets["plan_rank"].nunique()),
                "selected_symbol_count": int(targets["vt_symbol"].nunique()),
                "selected_target_dates": target_count,
                "minute_bar_count": int(len(bars_df)),
                "strict_full_preclose_ready_count": ready_count,
                "strict_full_preclose_ready_rate": ready_count / target_count if target_count else 0.0,
                "remaining_gap_count": int(len(synth_gap)),
                "failed_symbol_count": failed_symbol_count,
                "timeout_count": timeout_count,
                "status_values": status_values,
                "min_preclose_bar_count": int(synth["preclose_bar_count"].min()) if not synth.empty else 0,
                "min_fill_bar_count": int(synth["fill_bar_count"].min()) if not synth.empty else 0,
                "min_preclose_bar_gate": MIN_PRECLOSE_BAR_COUNT,
                "min_fill_bar_gate": MIN_FILL_BAR_COUNT,
            }
        ]
    )
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")

    all_ready = target_count > 0 and ready_count == target_count and failed_symbol_count == 0 and timeout_count == 0
    decision_label = (
        "covered_key_full_session_shard_ready_continue"
        if all_ready
        else "covered_key_full_session_shard_gap_need_attribution"
    )
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    decision = {
        "stage": STAGE_NAME,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": generated_at,
        "decision": decision_label,
        "promotion_candidate": "none",
        "summary": summary.iloc[0].to_dict(),
        "outputs": {
            "download_plan": str(PLAN_PATH),
            "targets": str(TARGETS_PATH),
            "status": str(STATUS_PATH),
            "completed_minute_bars": str(BARS_PATH),
            "synthetic": str(SYNTH_PATH),
            "gap": str(GAP_PATH),
            "summary": str(SUMMARY_PATH),
            "report": str(REPORT_PATH),
        },
        "next_step": "若本分片strict ready为100%，继续后续covered-key full-session分片；全量通过后再重跑Stage190和一致预收盘真实回放。",
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")

    gap_reason_counts = (
        synth_gap["strict_gap_reason"].value_counts().rename_axis("strict_gap_reason").reset_index(name="count")
        if not synth_gap.empty and "strict_gap_reason" in synth_gap.columns
        else pd.DataFrame(columns=["strict_gap_reason", "count"])
    )
    report = "\n".join(
        [
            "# Stage191 covered-key full-session分片回补",
            "",
            f"- 生成时间：{generated_at}",
            "- 阶段性质：执行数据链路回补；不新增策略，不修改 Stage079/C3 交易规则。",
            "- 回补对象：Stage190 中 Stage154 原已覆盖 `14:55-15:00` 但不具备完整冻结前 OHLCVOI 的 key。",
            f"- 决策标签：`{decision_label}`。",
            "",
            "## 参数",
            "",
            f"- `STAGE491_START_SPAN={START_SPAN}`",
            f"- `STAGE491_MAX_SPANS={MAX_SPANS}`",
            f"- `STAGE491_MAX_DATES_PER_SYMBOL={MAX_DATES_PER_SYMBOL}`",
            f"- `STAGE459_RAW_SUBDIR={os.environ.get('STAGE459_RAW_SUBDIR')}`",
            f"- `MIN_PRECLOSE_BAR_COUNT={MIN_PRECLOSE_BAR_COUNT}`",
            f"- `MIN_FILL_BAR_COUNT={MIN_FILL_BAR_COUNT}`",
            "",
            "## 汇总",
            "",
            _md_table(summary),
            "",
            "## 抽取状态",
            "",
            _md_table(status_df, max_rows=30),
            "",
            "## Gap原因",
            "",
            _md_table(gap_reason_counts),
            "",
            "## 样本",
            "",
            _md_table(synth, max_rows=20),
            "",
            "## 过拟合与继续价值反思",
            "",
            "- 过拟合：否。本阶段只补数据链路，不看收益，不调策略参数。",
            "- 继续价值：是。Stage190 已证明直接回放会混合数据语义，covered-key full-session 是一致回放的必要前置。",
        ]
    )
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"wrote: {REPORT_PATH}")


if __name__ == "__main__":
    main()
