from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
sys.path.insert(0, str(PROJECT_DIR.resolve()))

import analyze_qmt_roll_stage459_completed_preclose_full_bar_shard as s459  # noqa: E402


STAGE = os.getenv("STAGE490_STAGE_NAME", "Stage190")
MODEL_TAG = os.getenv("STAGE490_MODEL_TAG", "stage490_all_required_preclose_full_bar_readiness_v1")
OUTPUT_PREFIX = os.getenv("STAGE490_OUTPUT_PREFIX", "qmt_roll_stage490_all_required_preclose_full_bar_readiness")
LINE_ID = "futures_trend_drawdown30_preserve_return"

REQUIRED_KEYS_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage454_preclose_signal_bar_data_readiness_required_keys_stage454_preclose_signal_bar_data_readiness_v1.csv"
)

EXTRA_COMPLETED_RAW_ROOTS = [
    PROJECT_DIR / "downloaded_futures" / item.strip()
    for item in os.getenv("STAGE490_EXTRA_COMPLETED_RAW_ROOTS", "").split(",")
    if item.strip()
]
COMPLETED_RAW_ROOTS = EXTRA_COMPLETED_RAW_ROOTS + [
    PROJECT_DIR / "downloaded_futures" / "tqsdk_stage462_completed_preclose_full_dates_shard",
    PROJECT_DIR / "downloaded_futures" / "tqsdk_stage461_completed_preclose_full_dates_probe",
    PROJECT_DIR / "downloaded_futures" / "tqsdk_stage459_completed_preclose_full_bar_shard",
]

MIN_PRECLOSE_BAR_COUNT = 200
MIN_FILL_BAR_COUNT = 4

SYNTH_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_synthetic_{MODEL_TAG}.csv"
GAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gap_{MODEL_TAG}.csv"
SYMBOL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_symbol_summary_{MODEL_TAG}.csv"
COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stage154_coverage_summary_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
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
        value = float(value)
        return None if np.isnan(value) or np.isinf(value) else value
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


def _raw_path(root: Path, vt_symbol: str) -> Path:
    symbol, exchange = str(vt_symbol).split(".", 1)
    return root / exchange / f"{symbol}_completed_minute_backtest.csv"


def _load_required() -> pd.DataFrame:
    required = pd.read_csv(REQUIRED_KEYS_PATH, encoding="utf-8-sig")
    required["date"] = pd.to_datetime(required["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    required["has_preclose_1455_1500"] = pd.to_numeric(
        required.get("has_preclose_1455_1500", 0), errors="coerce"
    ).fillna(0).astype(int)
    required = required.dropna(subset=["date", "vt_symbol", "product_vt_symbol"]).copy()
    required["exchange"] = required["vt_symbol"].astype(str).str.split(".").str[-1]
    required["plan_rank"] = np.arange(1, len(required) + 1)
    return required.sort_values(["vt_symbol", "date", "product_vt_symbol"]).reset_index(drop=True)


def _key_frame(frame: pd.DataFrame) -> pd.DataFrame:
    key = frame[["date", "product_vt_symbol", "vt_symbol"]].copy()
    key["date"] = pd.to_datetime(key["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    key["product_vt_symbol"] = key["product_vt_symbol"].astype(str)
    key["vt_symbol"] = key["vt_symbol"].astype(str)
    return key


def _key_tuples(frame: pd.DataFrame) -> set[tuple[pd.Timestamp, str, str]]:
    key = _key_frame(frame).dropna(subset=["date", "product_vt_symbol", "vt_symbol"])
    return {
        (pd.Timestamp(row.date).normalize(), str(row.product_vt_symbol), str(row.vt_symbol))
        for row in key.itertuples(index=False)
    }


def _discover_stage489_synthetic_files() -> list[Path]:
    files = []
    for path in OUTPUT_DIR.glob("*completed_preclose_full_dates*_synthetic_preclose_bars_stage*completed_preclose_full_dates*.csv"):
        if path.name.startswith("qmt_roll_stage489_"):
            continue
        files.append(path)
    if not files:
        raise FileNotFoundError("No Stage461-488 synthetic_preclose_bars files found.")
    return sorted(files)


def _load_stage489_missing_synthetic(required: pd.DataFrame) -> pd.DataFrame:
    missing_required = required[required["has_preclose_1455_1500"].eq(0)].copy()
    missing_keys = _key_tuples(missing_required)
    frames: list[pd.DataFrame] = []
    for path in _discover_stage489_synthetic_files():
        frame = pd.read_csv(path, encoding="utf-8-sig")
        if frame.empty:
            continue
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
        frames.append(frame.dropna(subset=["date", "product_vt_symbol", "vt_symbol"]))
    if not frames:
        raise RuntimeError("Stage489 synthetic source files were empty.")
    synthetic = pd.concat(frames, ignore_index=True)
    synthetic = synthetic.drop_duplicates(["date", "product_vt_symbol", "vt_symbol"], keep="last")
    synthetic_keys = _key_tuples(synthetic)
    if missing_keys - synthetic_keys:
        raise RuntimeError(f"Stage489 synthetic missing keys: {len(missing_keys - synthetic_keys)}")
    synthetic = synthetic[
        synthetic.apply(
            lambda row: (pd.Timestamp(row["date"]).normalize(), str(row["product_vt_symbol"]), str(row["vt_symbol"]))
            in missing_keys,
            axis=1,
        )
    ].copy()
    metadata = missing_required[
        ["date", "product_vt_symbol", "vt_symbol", "has_preclose_1455_1500", "exchange"]
    ].drop_duplicates(["date", "product_vt_symbol", "vt_symbol"])
    synthetic = synthetic.merge(
        metadata,
        on=["date", "product_vt_symbol", "vt_symbol"],
        how="left",
        suffixes=("", "_required"),
    )
    if "exchange_required" in synthetic.columns:
        synthetic["exchange"] = synthetic["exchange_required"].fillna(synthetic.get("exchange", ""))
        synthetic.drop(columns=["exchange_required"], inplace=True)
    synthetic["raw_source_roots"] = "stage489_synthetic_preclose_bars"
    synthetic["raw_bar_rows"] = 1
    return synthetic


def _load_extra_precomputed_synthetic(required: pd.DataFrame) -> pd.DataFrame:
    patterns = [item.strip() for item in os.getenv("STAGE490_EXTRA_SYNTHETIC_GLOBS", "").split(",") if item.strip()]
    if not patterns:
        return pd.DataFrame()
    required_keys = _key_tuples(required)
    frames: list[pd.DataFrame] = []
    for pattern in patterns:
        pattern_path = Path(pattern)
        paths = list(pattern_path.parent.glob(pattern_path.name)) if pattern_path.parent != Path(".") else list(OUTPUT_DIR.glob(pattern))
        for path in sorted(paths):
            frame = pd.read_csv(path, encoding="utf-8-sig")
            if frame.empty:
                continue
            frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
            frame = frame.dropna(subset=["date", "product_vt_symbol", "vt_symbol"]).copy()
            frame = frame[
                frame.apply(
                    lambda row: (
                        pd.Timestamp(row["date"]).normalize(),
                        str(row["product_vt_symbol"]),
                        str(row["vt_symbol"]),
                    )
                    in required_keys,
                    axis=1,
                )
            ].copy()
            if frame.empty:
                continue
            frame["raw_source_roots"] = f"extra_synthetic:{path.name}"
            frame["raw_bar_rows"] = 1
            frames.append(frame)
    if not frames:
        return pd.DataFrame()
    synthetic = pd.concat(frames, ignore_index=True)
    synthetic = synthetic.drop_duplicates(["date", "product_vt_symbol", "vt_symbol"], keep="last")
    metadata = required[
        ["date", "product_vt_symbol", "vt_symbol", "has_preclose_1455_1500", "exchange"]
    ].drop_duplicates(["date", "product_vt_symbol", "vt_symbol"])
    synthetic = synthetic.merge(
        metadata,
        on=["date", "product_vt_symbol", "vt_symbol"],
        how="left",
        suffixes=("", "_required"),
    )
    if "exchange_required" in synthetic.columns:
        synthetic["exchange"] = synthetic["exchange_required"].fillna(synthetic.get("exchange", ""))
        synthetic.drop(columns=["exchange_required"], inplace=True)
    return synthetic


def _load_completed_raw(vt_symbol: str) -> tuple[pd.DataFrame, list[str]]:
    frames: list[pd.DataFrame] = []
    source_roots: list[str] = []
    for root in COMPLETED_RAW_ROOTS:
        path = _raw_path(root, vt_symbol)
        if not path.exists():
            continue
        frame = pd.read_csv(path, encoding="utf-8-sig")
        if frame.empty:
            continue
        frame["bar_datetime"] = pd.to_datetime(frame["bar_datetime"], errors="coerce").dt.tz_localize(None)
        frame["vt_symbol"] = vt_symbol
        frames.append(frame.dropna(subset=["bar_datetime"]))
        source_roots.append(root.name)
    if not frames:
        return pd.DataFrame(), source_roots
    bars = pd.concat(frames, ignore_index=True)
    bars = bars.drop_duplicates(["vt_symbol", "bar_datetime"], keep="last")
    bars = bars.sort_values(["vt_symbol", "bar_datetime"]).reset_index(drop=True)
    return bars, sorted(set(source_roots))


def _empty_synth_rows(targets: pd.DataFrame, source_roots: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in targets.itertuples(index=False):
        item = row._asdict()
        item.update(
            {
                "session_start": pd.NaT,
                "freeze_dt": pd.NaT,
                "fill_end_dt": pd.NaT,
                "boundary_uncertain": 1,
                "preclose_bar_count": 0,
                "fill_bar_count": 0,
                "valid_ohlc": 0,
                "volume_ok": 0,
                "open_interest_ok": 0,
                "fill_ok": 0,
                "full_bar_ready": 0,
                "synthetic_open": np.nan,
                "synthetic_high": np.nan,
                "synthetic_low": np.nan,
                "synthetic_close": np.nan,
                "synthetic_volume": np.nan,
                "synthetic_open_interest": np.nan,
                "fill_first_open": np.nan,
                "fill_last_close": np.nan,
                "fill_volume": np.nan,
                "raw_source_roots": ",".join(source_roots),
                "raw_bar_rows": 0,
            }
        )
        rows.append(item)
    return pd.DataFrame(rows)


def _strict_gap_reason(row: pd.Series) -> str:
    if int(row.get("raw_bar_rows", 0)) <= 0:
        return "no_completed_raw_file"
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


def _coverage_summary(synth: pd.DataFrame) -> pd.DataFrame:
    grouped = synth.groupby("has_preclose_1455_1500", dropna=False)
    rows: list[dict[str, Any]] = []
    for value, frame in grouped:
        rows.append(
            {
                "stage154_has_preclose_1455_1500": int(value),
                "required_keys": int(len(frame)),
                "strict_ready_count": int(frame["strict_full_preclose_ready"].sum()),
                "strict_ready_rate": float(frame["strict_full_preclose_ready"].mean()) if len(frame) else 0.0,
                "full_bar_ready_count": int(frame["full_bar_ready"].sum()),
                "preclose_bar_count_min": int(frame["preclose_bar_count"].min()) if len(frame) else 0,
                "fill_bar_count_min": int(frame["fill_bar_count"].min()) if len(frame) else 0,
                "raw_symbol_count": int(frame[frame["raw_bar_rows"].gt(0)]["vt_symbol"].nunique()),
                "total_symbol_count": int(frame["vt_symbol"].nunique()),
            }
        )
    return pd.DataFrame(rows).sort_values("stage154_has_preclose_1455_1500")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    required = _load_required()
    stage489_missing_synth = _load_stage489_missing_synthetic(required)
    extra_synth = _load_extra_precomputed_synthetic(required)
    precomputed_frames = [stage489_missing_synth]
    if not extra_synth.empty:
        precomputed_frames.append(extra_synth)
    precomputed_synth = pd.concat(precomputed_frames, ignore_index=True)
    precomputed_synth = precomputed_synth.drop_duplicates(["date", "product_vt_symbol", "vt_symbol"], keep="last")
    stage489_keys = _key_tuples(precomputed_synth)
    remaining = required[
        required.apply(
            lambda row: (pd.Timestamp(row["date"]).normalize(), str(row["product_vt_symbol"]), str(row["vt_symbol"]))
            not in stage489_keys,
            axis=1,
        )
    ].copy()
    synth_frames: list[pd.DataFrame] = [precomputed_synth]

    for vt_symbol, targets in remaining.groupby("vt_symbol", sort=False):
        bars, roots = _load_completed_raw(str(vt_symbol))
        if bars.empty:
            synth = _empty_synth_rows(targets, roots)
        else:
            synth = s459._synthesize_for_targets(targets.copy(), bars)
            synth["raw_source_roots"] = ",".join(roots)
            synth["raw_bar_rows"] = int(len(bars))
        synth_frames.append(synth)

    synth_all = pd.concat(synth_frames, ignore_index=True) if synth_frames else pd.DataFrame()
    if synth_all.empty:
        raise RuntimeError("No synthetic rows were produced.")

    numeric_flags = ["full_bar_ready", "valid_ohlc", "volume_ok", "open_interest_ok", "fill_ok"]
    for column in numeric_flags + ["preclose_bar_count", "fill_bar_count", "raw_bar_rows", "has_preclose_1455_1500"]:
        synth_all[column] = pd.to_numeric(synth_all.get(column, 0), errors="coerce").fillna(0).astype(int)

    synth_all["strict_gap_reason"] = synth_all.apply(_strict_gap_reason, axis=1)
    synth_all["strict_full_preclose_ready"] = synth_all["strict_gap_reason"].eq("").astype(int)
    synth_all = synth_all.sort_values(["date", "product_vt_symbol", "vt_symbol"]).reset_index(drop=True)

    gap = synth_all[synth_all["strict_full_preclose_ready"].eq(0)].copy()
    symbol_summary = (
        synth_all.groupby(["vt_symbol", "product_vt_symbol", "exchange"], dropna=False)
        .agg(
            required_keys=("strict_full_preclose_ready", "size"),
            strict_ready_count=("strict_full_preclose_ready", "sum"),
            full_bar_ready_count=("full_bar_ready", "sum"),
            preclose_bar_count_min=("preclose_bar_count", "min"),
            fill_bar_count_min=("fill_bar_count", "min"),
            raw_bar_rows=("raw_bar_rows", "max"),
            raw_source_roots=("raw_source_roots", "first"),
        )
        .reset_index()
    )
    symbol_summary["strict_ready_rate"] = symbol_summary["strict_ready_count"] / symbol_summary["required_keys"]
    symbol_summary = symbol_summary.sort_values(["strict_ready_rate", "required_keys"], ascending=[True, False])

    coverage = _coverage_summary(synth_all)
    gap_reason_counts = (
        gap["strict_gap_reason"].value_counts().rename_axis("strict_gap_reason").reset_index(name="count")
    )

    required_key_count = int(len(required))
    strict_ready_count = int(synth_all["strict_full_preclose_ready"].sum())
    full_bar_ready_count = int(synth_all["full_bar_ready"].sum())
    raw_symbol_count = int(synth_all[synth_all["raw_bar_rows"].gt(0)]["vt_symbol"].nunique())
    summary = pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "required_key_count": required_key_count,
                "synthetic_row_count": int(len(synth_all)),
                "required_symbol_count": int(required["vt_symbol"].nunique()),
                "raw_symbol_count": raw_symbol_count,
                "full_bar_ready_count": full_bar_ready_count,
                "strict_full_preclose_ready_count": strict_ready_count,
                "strict_full_preclose_ready_rate": strict_ready_count / required_key_count if required_key_count else 0.0,
                "gap_count": int(len(gap)),
                "min_preclose_bar_count": int(synth_all["preclose_bar_count"].min()),
                "min_fill_bar_count": int(synth_all["fill_bar_count"].min()),
                "stage154_missing_key_count": int((required["has_preclose_1455_1500"] == 0).sum()),
                "stage154_precovered_key_count": int((required["has_preclose_1455_1500"] == 1).sum()),
                "min_preclose_bar_gate": MIN_PRECLOSE_BAR_COUNT,
                "min_fill_bar_gate": MIN_FILL_BAR_COUNT,
            }
        ]
    )

    synth_all.to_csv(SYNTH_PATH, index=False, encoding="utf-8-sig")
    gap.to_csv(GAP_PATH, index=False, encoding="utf-8-sig")
    symbol_summary.to_csv(SYMBOL_PATH, index=False, encoding="utf-8-sig")
    coverage.to_csv(COVERAGE_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")

    all_ready = required_key_count > 0 and strict_ready_count == required_key_count
    decision_label = (
        "all_required_preclose_full_bar_ready_proceed_to_consistent_replay"
        if all_ready
        else "all_required_preclose_full_bar_not_ready_need_covered_key_backfill"
    )
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": generated_at,
        "decision": decision_label,
        "promotion_candidate": "none",
        "summary": summary.iloc[0].to_dict(),
        "gap_reason_counts": gap_reason_counts.to_dict(orient="records"),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "synthetic": str(SYNTH_PATH),
            "gap": str(GAP_PATH),
            "symbol_summary": str(SYMBOL_PATH),
            "coverage_summary": str(COVERAGE_PATH),
            "report": str(REPORT_PATH),
        },
        "next_step": (
            "全部required key严格可用后再做一致预收盘真实回放；若仍有gap，先补齐Stage154已覆盖但未具备完整preclose-session的键。"
        ),
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")

    report = "\n".join(
        [
            "# Stage190 全required-key预收盘完整bar准备度审计",
            "",
            f"- 生成时间：{generated_at}",
            "- 阶段性质：执行数据链路审计；不新增策略，不修改 Stage079/C3 交易规则。",
            "- 审计对象：Stage154 全部 required key，而不只是缺口 key。",
            f"- 严格口径：`full_bar_ready=1`、`preclose_bar_count>={MIN_PRECLOSE_BAR_COUNT}`、`fill_bar_count>={MIN_FILL_BAR_COUNT}`。",
            "",
            "## 外部调研与判断",
            "",
            "- TqSdk 文档说明回测 K 线会随时间推进更新，不能把最终日K直接当作决策时可见数据。",
            "- 回测防未来函数的通用原则是区分决策时点与成交时点；本阶段因此要求策略输入bar和成交窗口都来自冻结前可见数据。",
            "- 判断：Stage189 已证明缺口 key 可以补齐，但不能自动证明原本 Stage154 已覆盖的 `14:55-15:00` key 也具备完整冻结前 OHLCVOI。",
            "",
            "## 汇总",
            "",
            _md_table(summary),
            "",
            "## Stage154覆盖分组",
            "",
            _md_table(coverage),
            "",
            "## Gap原因",
            "",
            _md_table(gap_reason_counts),
            "",
            "## Gap最多合约",
            "",
            _md_table(symbol_summary[symbol_summary["strict_ready_rate"].lt(1.0)].head(40)),
            "",
            "## 决策",
            "",
            f"- 决策标签：`{decision_label}`。",
            "- 本阶段不产生策略晋级候选。",
            "",
            "## 过拟合与继续价值反思",
            "",
            "- 运行前过拟合反思：否。只检查数据可得性与执行语义，不看收益曲线。",
            "- 运行后过拟合反思：否。本阶段没有新增参数搜索，严格阈值只用于排除14:55局部窗口伪装成完整日K的情况。",
            "- 运行前继续价值反思：是。若这里不严，后续3个月/6个月体验优化会建立在混合数据语义上。",
            "- 运行后继续价值反思：见决策；若存在gap，先补数据比直接回放更有价值。",
        ]
    )
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"wrote: {REPORT_PATH}")


if __name__ == "__main__":
    main()
