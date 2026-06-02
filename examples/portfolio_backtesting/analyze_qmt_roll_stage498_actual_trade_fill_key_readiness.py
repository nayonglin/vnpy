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
RAW_BASE = PROJECT_DIR / "downloaded_futures"
sys.path.insert(0, str(PROJECT_DIR.resolve()))

os.environ.setdefault("STAGE459_RAW_SUBDIR", "tqsdk_stage498_actual_trade_fill_key_backfill")
os.environ.setdefault("STAGE459_DISABLE_TQSDK_PRINT", "1")

import analyze_qmt_roll_stage459_completed_preclose_full_bar_shard as s459  # noqa: E402


STAGE = "Stage198"
MODEL_TAG = "stage498_actual_trade_fill_key_readiness_v1"
OUTPUT_PREFIX = "qmt_roll_stage498_actual_trade_fill_key_readiness"
LINE_ID = "futures_trend_drawdown30_preserve_return"

STAGE197_TRADE_USAGE_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage497_consistent_preclose_full_bar_replay_trade_usage_stage497_consistent_preclose_full_bar_replay_v1.csv"
)

ENABLE_TQSDK_BACKFILL = os.getenv("STAGE498_ENABLE_TQSDK_BACKFILL", "0").strip() == "1"
MIN_PRECLOSE_BAR_COUNT = int(os.getenv("STAGE498_MIN_PRECLOSE_BAR_COUNT", "200"))
MIN_FILL_BAR_COUNT = int(os.getenv("STAGE498_MIN_FILL_BAR_COUNT", "4"))
RAW_ROOTS = [
    item.strip()
    for item in os.getenv("STAGE498_RAW_ROOTS", "").split(",")
    if item.strip()
]

TARGETS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_targets_{MODEL_TAG}.csv"
RAW_COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_raw_coverage_{MODEL_TAG}.csv"
STATUS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_extract_status_{MODEL_TAG}.csv"
BARS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_completed_minute_bars_{MODEL_TAG}.csv"
SYNTH_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_synthetic_preclose_bars_{MODEL_TAG}.csv"
GAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gap_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(item) for k, item in value.items()}
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


def _product_vt_symbol(vt_symbol: str) -> str:
    symbol, exchange = str(vt_symbol).split(".", 1)
    product = "".join(ch for ch in symbol if ch.isalpha())
    return f"{product}.{exchange}"


def _load_fallback_targets() -> pd.DataFrame:
    trade_usage = pd.read_csv(STAGE197_TRADE_USAGE_PATH, encoding="utf-8-sig")
    trade_usage["date"] = pd.to_datetime(trade_usage["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    fallback = trade_usage[
        trade_usage["date"].notna()
        & trade_usage["vt_symbol"].notna()
        & trade_usage["fill_source"].astype(str).ne("stage196_fill_first_open")
    ].copy()
    if fallback.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for idx, row in enumerate(fallback.sort_values(["date", "vt_symbol", "orderid"]).itertuples(index=False), start=1):
        vt_symbol = str(row.vt_symbol)
        date = pd.Timestamp(row.date).normalize()
        rows.append(
            {
                "plan_rank": idx,
                "vt_symbol": vt_symbol,
                "exchange": vt_symbol.split(".", 1)[1],
                "product_vt_symbol": _product_vt_symbol(vt_symbol),
                "date": date,
                "span_start": date,
                "span_end": date,
                "missing_dates_in_span": 1,
                "span_calendar_days": 1,
                "stage197_orderid": str(row.orderid),
                "stage197_direction": str(row.direction),
                "stage197_offset": str(row.offset),
                "stage197_order_price": float(row.order_price),
                "stage197_bar_close_price": float(row.bar_close_price),
            }
        )
    targets = pd.DataFrame(rows)
    return targets.drop_duplicates(["date", "vt_symbol"], keep="first").reset_index(drop=True)


def _raw_path(root: Path, vt_symbol: str) -> Path:
    symbol, exchange = str(vt_symbol).split(".", 1)
    return root / exchange / f"{symbol}_completed_minute_backtest.csv"


def _candidate_roots() -> list[Path]:
    if RAW_ROOTS:
        roots = [Path(item) if Path(item).is_absolute() else RAW_BASE / item for item in RAW_ROOTS]
    else:
        roots = sorted(path for path in RAW_BASE.iterdir() if path.is_dir() and path.name.startswith("tqsdk_stage"))
    stage498_root = RAW_BASE / "tqsdk_stage498_actual_trade_fill_key_backfill"
    if stage498_root not in roots:
        roots.append(stage498_root)
    return roots


def _load_existing_bars(targets: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    frames: list[pd.DataFrame] = []
    coverage_rows: list[dict[str, Any]] = []
    for vt_symbol in sorted(targets["vt_symbol"].astype(str).unique()):
        for root in _candidate_roots():
            path = _raw_path(root, vt_symbol)
            exists = path.exists()
            rows = 0
            min_dt = pd.NaT
            max_dt = pd.NaT
            if exists:
                frame = pd.read_csv(path, encoding="utf-8-sig")
                if not frame.empty:
                    frame["bar_datetime"] = pd.to_datetime(frame["bar_datetime"], errors="coerce").dt.tz_localize(None)
                    frame = frame.dropna(subset=["bar_datetime"]).copy()
                    if not frame.empty:
                        frame["vt_symbol"] = vt_symbol
                        frame["raw_source_root"] = root.name
                        frames.append(frame)
                        rows = int(len(frame))
                        min_dt = frame["bar_datetime"].min()
                        max_dt = frame["bar_datetime"].max()
            coverage_rows.append(
                {
                    "vt_symbol": vt_symbol,
                    "raw_root": root.name,
                    "path": str(path),
                    "exists": int(exists),
                    "rows": rows,
                    "min_bar_datetime": min_dt,
                    "max_bar_datetime": max_dt,
                }
            )
    bars = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if not bars.empty:
        bars = bars.drop_duplicates(["vt_symbol", "bar_datetime"]).sort_values(["vt_symbol", "bar_datetime"])
    return bars, pd.DataFrame(coverage_rows)


def _time_on_date(date_value: Any, hhmm: str) -> pd.Timestamp:
    hour_text, minute_text = hhmm.split(":", 1)
    return pd.Timestamp(date_value).normalize() + pd.Timedelta(hours=int(hour_text), minutes=int(minute_text))


def _synthesize_targets(targets: pd.DataFrame, bars: pd.DataFrame) -> pd.DataFrame:
    if targets.empty:
        return pd.DataFrame()
    bars = bars.copy()
    if bars.empty:
        grouped: dict[str, pd.DataFrame] = {}
    else:
        bars["bar_datetime"] = pd.to_datetime(bars["bar_datetime"], errors="coerce").dt.tz_localize(None)
        bars = bars.dropna(subset=["bar_datetime"]).sort_values(["vt_symbol", "bar_datetime"])
        grouped = {symbol: frame.copy() for symbol, frame in bars.groupby("vt_symbol", sort=False)}
    rows: list[dict[str, Any]] = []
    for row in targets.sort_values(["vt_symbol", "date"]).itertuples(index=False):
        vt_symbol = str(row.vt_symbol)
        date = pd.Timestamp(row.date).normalize()
        frame = grouped.get(vt_symbol, pd.DataFrame())
        session_start = date - pd.Timedelta(days=s459.SESSION_LOOKBACK_CALENDAR_DAYS) + pd.Timedelta(
            hours=20, minutes=55
        )
        freeze_dt = _time_on_date(date, s459.FREEZE_TIME)
        fill_end_dt = _time_on_date(date, s459.FILL_END_TIME)
        preclose = frame[(frame["bar_datetime"] >= session_start) & (frame["bar_datetime"] < freeze_dt)]
        fill = frame[(frame["bar_datetime"] >= freeze_dt) & (frame["bar_datetime"] < fill_end_dt)]
        numeric_ohlc = preclose[["open", "high", "low", "close"]].replace([np.inf, -np.inf], np.nan) if not preclose.empty else pd.DataFrame()
        valid_ohlc = not preclose.empty and numeric_ohlc.notna().all().all()
        preclose_volume = pd.to_numeric(preclose.get("volume", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
        fill_volume = pd.to_numeric(fill.get("volume", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
        preclose_close_oi = pd.to_numeric(preclose.get("close_oi", pd.Series(dtype=float)), errors="coerce")
        fill_ohlc_ok = not fill.empty and fill[["open", "close"]].replace([np.inf, -np.inf], np.nan).notna().all().all()
        volume_sum = float(preclose_volume.sum()) if not preclose.empty else 0.0
        fill_volume_sum = float(fill_volume.sum()) if not fill.empty else 0.0
        oi_ok = not preclose.empty and preclose_close_oi.notna().any()
        fill_count = int(len(fill))
        preclose_count = int(len(preclose))
        strict_ready = bool(
            valid_ohlc
            and volume_sum > 0.0
            and oi_ok
            and fill_ohlc_ok
            and preclose_count >= MIN_PRECLOSE_BAR_COUNT
            and fill_count >= MIN_FILL_BAR_COUNT
        )
        if not valid_ohlc:
            reason = "invalid_or_missing_ohlc"
        elif preclose_count < MIN_PRECLOSE_BAR_COUNT:
            reason = "short_preclose_session"
        elif volume_sum <= 0.0:
            reason = "preclose_volume_not_positive"
        elif not oi_ok:
            reason = "open_interest_missing"
        elif not fill_ohlc_ok or fill_count < MIN_FILL_BAR_COUNT:
            reason = "fill_window_missing"
        else:
            reason = ""
        rows.append(
            {
                **row._asdict(),
                "session_start": session_start,
                "freeze_dt": freeze_dt,
                "fill_end_dt": fill_end_dt,
                "preclose_bar_count": preclose_count,
                "fill_bar_count": fill_count,
                "valid_ohlc": int(valid_ohlc),
                "volume_ok": int(volume_sum > 0.0),
                "open_interest_ok": int(oi_ok),
                "fill_ok": int(fill_ohlc_ok),
                "full_bar_ready": int(strict_ready),
                "strict_full_preclose_ready": int(strict_ready),
                "strict_gap_reason": reason,
                "synthetic_open": float(preclose["open"].iloc[0]) if valid_ohlc else np.nan,
                "synthetic_high": float(preclose["high"].max()) if valid_ohlc else np.nan,
                "synthetic_low": float(preclose["low"].min()) if valid_ohlc else np.nan,
                "synthetic_close": float(preclose["close"].iloc[-1]) if valid_ohlc else np.nan,
                "synthetic_volume": volume_sum if volume_sum > 0.0 else np.nan,
                "synthetic_open_interest": float(preclose_close_oi.dropna().iloc[-1]) if oi_ok else np.nan,
                "fill_first_open": float(fill["open"].iloc[0]) if fill_ohlc_ok else np.nan,
                "fill_last_close": float(fill["close"].iloc[-1]) if fill_ohlc_ok else np.nan,
                "fill_volume": fill_volume_sum if fill_volume_sum > 0.0 else np.nan,
            }
        )
    return pd.DataFrame(rows).sort_values(["date", "vt_symbol"]).reset_index(drop=True)


def _maybe_backfill(gap: pd.DataFrame) -> pd.DataFrame:
    if gap.empty or not ENABLE_TQSDK_BACKFILL:
        return pd.DataFrame()
    username, password = s459._require_credentials()
    status_rows: list[dict[str, Any]] = []
    bar_frames: list[pd.DataFrame] = []
    for vt_symbol, frame in gap.groupby("vt_symbol", sort=False):
        status, bars = s459._extract_symbol(str(vt_symbol), list(pd.to_datetime(frame["date"])), username, password)
        status_rows.append(status)
        if not bars.empty:
            bar_frames.append(bars)
    status_df = pd.DataFrame(status_rows)
    status_df.to_csv(STATUS_PATH, index=False, encoding="utf-8-sig")
    return pd.concat(bar_frames, ignore_index=True) if bar_frames else pd.DataFrame()


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    targets = _load_fallback_targets()
    targets.to_csv(TARGETS_PATH, index=False, encoding="utf-8-sig")
    if targets.empty:
        raise RuntimeError("Stage197 fallback targets are empty.")

    bars, coverage = _load_existing_bars(targets)
    initial_synth = _synthesize_targets(targets, bars)
    initial_gap = initial_synth[initial_synth["strict_full_preclose_ready"].ne(1)].copy()

    extracted_bars = _maybe_backfill(initial_gap)
    if not extracted_bars.empty:
        bars = pd.concat([bars, extracted_bars], ignore_index=True)
        bars = bars.drop_duplicates(["vt_symbol", "bar_datetime"]).sort_values(["vt_symbol", "bar_datetime"])
        synth = _synthesize_targets(targets, bars)
    else:
        if not STATUS_PATH.exists():
            pd.DataFrame().to_csv(STATUS_PATH, index=False, encoding="utf-8-sig")
        synth = initial_synth

    gap = synth[synth["strict_full_preclose_ready"].ne(1)].copy()
    bars.to_csv(BARS_PATH, index=False, encoding="utf-8-sig")
    coverage.to_csv(RAW_COVERAGE_PATH, index=False, encoding="utf-8-sig")
    synth.to_csv(SYNTH_PATH, index=False, encoding="utf-8-sig")
    gap.to_csv(GAP_PATH, index=False, encoding="utf-8-sig")

    ready_count = int(synth["strict_full_preclose_ready"].sum()) if not synth.empty else 0
    target_count = int(len(targets))
    decision_label = (
        "actual_trade_fill_keys_ready_for_no_fallback_replay"
        if ready_count == target_count
        else "actual_trade_fill_keys_need_tqsdk_backfill"
        if not ENABLE_TQSDK_BACKFILL
        else "actual_trade_fill_keys_backfill_still_incomplete"
    )
    summary = pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "target_count": target_count,
                "ready_count": ready_count,
                "ready_rate": ready_count / target_count if target_count else 0.0,
                "gap_count": int(len(gap)),
                "unique_symbol_count": int(targets["vt_symbol"].nunique()),
                "completed_minute_bar_rows": int(len(bars)),
                "raw_root_count": int(len(_candidate_roots())),
                "enable_tqsdk_backfill": int(ENABLE_TQSDK_BACKFILL),
                "min_preclose_bar_count": int(synth["preclose_bar_count"].min()) if not synth.empty else 0,
                "min_fill_bar_count": int(synth["fill_bar_count"].min()) if not synth.empty else 0,
                "decision": decision_label,
            }
        ]
    )
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")

    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": decision_label,
        "promotion_candidate": "none",
        "target_count": target_count,
        "ready_count": ready_count,
        "gap_count": int(len(gap)),
        "enable_tqsdk_backfill": ENABLE_TQSDK_BACKFILL,
        "outputs": {
            "targets": str(TARGETS_PATH),
            "raw_coverage": str(RAW_COVERAGE_PATH),
            "status": str(STATUS_PATH),
            "completed_minute_bars": str(BARS_PATH),
            "synthetic_preclose_bars": str(SYNTH_PATH),
            "gap": str(GAP_PATH),
            "summary": str(SUMMARY_PATH),
            "report": str(REPORT_PATH),
        },
        "next_step": (
            "ready=100%后，将Stage198 supplemental synthetic并入Stage196 preclose map，重跑Stage197 no-fallback replay；"
            "否则先用TqSdk补齐实际成交键。"
        ),
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")

    report = "\n".join(
        [
            "# Stage198 实际成交键预收盘完整bar准备度审计",
            "",
            f"- 生成时间：{decision['generated_at']}",
            "- 阶段性质：执行数据完整性审计；不新增策略、不修改 Stage079/C3 交易规则。",
            "- 目标：补 Stage197 的成交 fallback，检查实际成交键是否具备同口径 preclose OHLCVOI 与填充窗口。",
            "",
            "## 外部调研与判断",
            "",
            "- TqSdk 历史分钟K可用于冻结时点重建，但必须用同一时间窗口同时约束信号bar与成交bar。",
            "- 本阶段只审计实际成交键，不用收益结果反推数据选择。",
            "",
            "## 决策",
            "",
            f"- 决策标签：`{decision_label}`。",
            f"- ready：`{ready_count}/{target_count}`。",
            f"- 是否启用TqSdk补齐：`{int(ENABLE_TQSDK_BACKFILL)}`。",
            "",
            "## 总览",
            "",
            _md_table(summary),
            "",
            "## 未ready键",
            "",
            _md_table(gap, max_rows=80),
            "",
            "## 合成样本",
            "",
            _md_table(synth, max_rows=80),
            "",
            "## 结论",
            "",
            "- 本阶段没有策略候选晋级。",
            "- 若全部ready，下一步只做no-fallback一致回放；若不ready，先补数据，不做参数救援。",
            "",
            "## 过拟合与继续价值反思",
            "",
            "- 过拟合：否。只补执行数据键，不看收益调规则。",
            "- 继续价值：有。它决定 Stage197 反证是否还存在成交fallback口径瑕疵。",
        ]
    )
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"wrote: {REPORT_PATH}")


if __name__ == "__main__":
    main()
