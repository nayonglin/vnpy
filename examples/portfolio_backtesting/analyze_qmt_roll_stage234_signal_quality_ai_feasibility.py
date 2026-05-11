from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from main_contract_mapping import build_contract_metadata
from qmt_roll_official_stage78_config import OFFICIAL_STAGE78_CAPITAL, OFFICIAL_STAGE78_SHORT_ALIAS, OFFICIAL_STAGE78_VERSION, build_official_stage78_manifest, build_official_stage78_overrides
from run_qmt_alignment_backtest import OUTPUT_DIR
from run_qmt_roll_backtest import compute_round_trip_win_ratio
from run_qmt_roll_official_stage78_1 import OUTPUT_PREFIX as OFFICIAL_PREFIX
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


MODEL_TAG = "stage234_signal_quality_ai_feasibility_v1"
OUTPUT_PREFIX = "qmt_roll_stage234_signal_quality_ai_feasibility"

ENTRY_SNAPSHOTS_PATH = OUTPUT_DIR / f"{OFFICIAL_PREFIX}_entry_candidate_snapshots_2020_2026_04.csv"
TRADES_PATH = OUTPUT_DIR / f"{OFFICIAL_PREFIX}_trades_2020_2026_04.csv"
DAILY_PATH = OUTPUT_DIR / f"{OFFICIAL_PREFIX}_daily.csv"

SAMPLES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_samples_{MODEL_TAG}.csv"
WINDOW_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_summary_{MODEL_TAG}.csv"
BUCKET_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_summary_{MODEL_TAG}.csv"
WINDOW_BUCKET_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_bucket_summary_{MODEL_TAG}.csv"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
MANIFEST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_manifest_{MODEL_TAG}.json"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(v) or np.isinf(v):
        return default
    return v


def _to_markdown(df: pd.DataFrame, max_rows: int = 30) -> str:
    if df.empty:
        return "_empty_"
    return df.head(max_rows).to_markdown(index=False)


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, float]]:
    snapshots = pd.read_csv(ENTRY_SNAPSHOTS_PATH)
    snapshots["date"] = pd.to_datetime(snapshots["date"].astype(str).str.slice(0, 10)).dt.normalize()
    snapshots["entry_date"] = snapshots["date"]
    snapshots = snapshots[pd.to_numeric(snapshots["is_opened"], errors="coerce").fillna(0).astype(int).eq(1)].copy()
    snapshots["direction_key"] = snapshots["direction"].astype(str).str.lower()
    snapshots["vt_symbol"] = snapshots["contract_vt_symbol"]
    snapshots.sort_values(["date", "vt_symbol", "direction_key", "candidate_index"], inplace=True)
    snapshots = snapshots.drop_duplicates(subset=["date", "vt_symbol", "direction_key"], keep="last")

    trades = pd.read_csv(TRADES_PATH)
    trades["datetime"] = pd.to_datetime(trades["datetime"].astype(str).str.replace(r"\+08:00$", "", regex=True))
    trades["date"] = pd.to_datetime(trades["date"].astype(str).str.slice(0, 10)).dt.normalize()
    trades["direction"] = trades["direction"].astype(str)
    trades["offset"] = trades["offset"].astype(str)

    daily = pd.read_csv(DAILY_PATH)
    daily["date"] = pd.to_datetime(daily["date"].astype(str).str.slice(0, 10)).dt.normalize()
    daily.set_index("date", inplace=True)

    overrides = build_official_stage78_overrides()
    metadata = build_contract_metadata(supported_symbols=[str(v) for v in [*set(snapshots["product_vt_symbol"].dropna().tolist())]])
    size_map = {symbol: float(size) for symbol, size in metadata["sizes"].items()}
    return snapshots, trades, daily, size_map


def build_round_trips(trades: pd.DataFrame, size_map: dict[str, float]) -> pd.DataFrame:
    trades = trades.copy()
    trades["_row_order"] = np.arange(len(trades))
    trades = trades.sort_values(["datetime", "_row_order"]).copy()
    open_queues: dict[tuple[str, str], list[dict[str, Any]]] = {}
    rows: list[dict[str, Any]] = []
    for _, trade in trades.iterrows():
        vt_symbol = str(trade["vt_symbol"])
        price = float(trade["price"])
        volume = float(trade["volume"])
        contract_size = float(size_map.get(vt_symbol, 1.0))
        offset = str(trade["offset"]).lower()
        direction = str(trade["direction"]).lower()
        if offset == "open":
            position_direction = "long" if direction == "long" else "short"
            open_queues.setdefault((vt_symbol, position_direction), []).append(
                {
                    "entry_datetime": trade["datetime"],
                    "entry_date": trade["date"],
                    "entry_price": price,
                    "volume": volume,
                }
            )
            continue

        position_direction = "long" if direction == "short" else "short"
        queue = open_queues.setdefault((vt_symbol, position_direction), [])
        remaining = volume
        while remaining > 1e-9 and queue:
            lot = queue[0]
            matched = min(remaining, float(lot["volume"]))
            if position_direction == "long":
                gross = (price - float(lot["entry_price"])) * matched * contract_size
            else:
                gross = (float(lot["entry_price"]) - price) * matched * contract_size
            rows.append(
                {
                    "vt_symbol": vt_symbol,
                    "direction_key": position_direction,
                    "entry_datetime": lot["entry_datetime"],
                    "entry_date": lot["entry_date"],
                    "exit_datetime": trade["datetime"],
                    "exit_date": trade["date"],
                    "entry_price": float(lot["entry_price"]),
                    "exit_price": price,
                    "matched_volume": matched,
                    "gross_pnl": gross,
                }
            )
            remaining -= matched
            lot["volume"] = float(lot["volume"]) - matched
            if float(lot["volume"]) <= 1e-9:
                queue.pop(0)
    return pd.DataFrame(rows)


def build_samples(snapshots: pd.DataFrame, round_trips: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    trade_stats = (
        round_trips.groupby(["entry_date", "vt_symbol", "direction_key"], as_index=False)
        .agg(
            round_trip_count=("gross_pnl", "size"),
            realized_pnl=("gross_pnl", "sum"),
            win_round_trip_count=("gross_pnl", lambda s: int((s > 0).sum())),
            first_exit_date=("exit_date", "min"),
            last_exit_date=("exit_date", "max"),
        )
    )
    samples = snapshots.merge(
        trade_stats,
        on=["entry_date", "vt_symbol", "direction_key"],
        how="left",
    )
    samples["round_trip_count"] = pd.to_numeric(samples["round_trip_count"], errors="coerce").fillna(0).astype(int)
    samples["realized_pnl"] = pd.to_numeric(samples["realized_pnl"], errors="coerce").fillna(0.0)
    samples["meta_success"] = (samples["realized_pnl"] > 0).astype(int)
    samples["entry_year"] = samples["entry_date"].dt.year
    samples["selection_pairwise_rank"] = pd.to_numeric(samples.get("selection_pairwise_rank"), errors="coerce")
    samples["ai_product_pool_rank"] = pd.to_numeric(samples.get("ai_product_pool_rank"), errors="coerce")
    samples["rsi_value"] = pd.to_numeric(samples.get("rsi_value"), errors="coerce")
    samples["portfolio_drawdown_pct"] = pd.to_numeric(samples.get("portfolio_drawdown_pct"), errors="coerce")
    samples["stop_distance"] = pd.to_numeric(samples.get("stop_distance"), errors="coerce")
    samples["target_risk_amount"] = pd.to_numeric(samples.get("target_risk_amount"), errors="coerce")
    samples["risk_reward_proxy"] = np.divide(
        samples["realized_pnl"],
        samples["target_risk_amount"].replace(0, np.nan),
    )
    samples["pairwise_rank_bucket"] = pd.cut(
        samples["selection_pairwise_rank"],
        bins=[-np.inf, 3, 8, np.inf],
        labels=["rank_1_3", "rank_4_8", "rank_gt_8"],
    ).astype(str)
    samples["ai_rank_bucket"] = pd.cut(
        samples["ai_product_pool_rank"],
        bins=[-np.inf, 3, 8, np.inf],
        labels=["ai_1_3", "ai_4_8", "ai_gt_8"],
    ).astype(str)
    samples["rsi_bucket"] = pd.cut(
        samples["rsi_value"],
        bins=[-np.inf, 40, 60, 80, np.inf],
        labels=["rsi_le_40", "rsi_40_60", "rsi_60_80", "rsi_gt_80"],
    ).astype(str)
    return samples


def summarize_windows(samples: pd.DataFrame) -> pd.DataFrame:
    windows = [
        ("train_2020_2023", 2020, 2023),
        ("test_2024_2025", 2024, 2025),
        ("test_2026", 2026, 2026),
    ]
    rows: list[dict[str, Any]] = []
    for window_name, start_year, end_year in windows:
        subset = samples[(samples["entry_year"] >= start_year) & (samples["entry_year"] <= end_year)].copy()
        if subset.empty:
            continue
        rows.append(
            {
                "window_name": window_name,
                "start_year": start_year,
                "end_year": end_year,
                "sample_count": int(len(subset)),
                "opened_roundtrip_count": int((subset["round_trip_count"] > 0).sum()),
                "meta_success_rate_pct": float(subset["meta_success"].mean() * 100.0),
                "avg_realized_pnl": float(subset["realized_pnl"].mean()),
                "median_realized_pnl": float(subset["realized_pnl"].median()),
                "positive_pnl_sum": float(subset.loc[subset["realized_pnl"] > 0, "realized_pnl"].sum()),
                "negative_pnl_sum": float(subset.loc[subset["realized_pnl"] <= 0, "realized_pnl"].sum()),
            }
        )
    return pd.DataFrame(rows)


def summarize_buckets(samples: pd.DataFrame) -> pd.DataFrame:
    bucket_cols = ["direction_key", "signal", "pairwise_rank_bucket", "ai_rank_bucket", "rsi_bucket"]
    rows: list[dict[str, Any]] = []
    for col in bucket_cols:
        grouped = (
            samples.groupby(col, dropna=False)
            .agg(
                sample_count=("meta_success", "size"),
                success_rate_pct=("meta_success", lambda s: float(s.mean() * 100.0)),
                avg_realized_pnl=("realized_pnl", "mean"),
                median_realized_pnl=("realized_pnl", "median"),
                avg_risk_reward_proxy=("risk_reward_proxy", "mean"),
            )
            .reset_index()
            .rename(columns={col: "bucket_value"})
        )
        grouped["bucket_type"] = col
        rows.append(grouped)
    summary = pd.concat(rows, ignore_index=True)
    return summary.sort_values(["bucket_type", "success_rate_pct", "avg_realized_pnl"], ascending=[True, False, False])


def summarize_window_buckets(samples: pd.DataFrame) -> pd.DataFrame:
    samples = samples.copy()
    samples["time_window"] = pd.cut(
        samples["entry_year"],
        bins=[2019, 2023, 2025, 2026],
        labels=["train_2020_2023", "test_2024_2025", "test_2026"],
    ).astype(str)
    bucket_cols = ["signal", "direction_key", "rsi_bucket", "ai_rank_bucket"]
    rows: list[pd.DataFrame] = []
    for col in bucket_cols:
        grouped = (
            samples.groupby(["time_window", col], dropna=False)
            .agg(
                sample_count=("meta_success", "size"),
                success_rate_pct=("meta_success", lambda s: float(s.mean() * 100.0)),
                avg_realized_pnl=("realized_pnl", "mean"),
                median_realized_pnl=("realized_pnl", "median"),
            )
            .reset_index()
            .rename(columns={col: "bucket_value"})
        )
        grouped["bucket_type"] = col
        rows.append(grouped)
    return pd.concat(rows, ignore_index=True).sort_values(["bucket_type", "time_window", "bucket_value"])


def build_report(samples: pd.DataFrame, windows: pd.DataFrame, buckets: pd.DataFrame, window_buckets: pd.DataFrame) -> str:
    lines = [
        "# Stage234 AI 信号质量模型离线可行性验证",
        "",
        "## 口径",
        "",
        f"- 基准：`{OFFICIAL_STAGE78_SHORT_ALIAS}` / `{OFFICIAL_STAGE78_VERSION}`",
        "- 方法：不预测市场涨跌，只对 `78-1` 已打开的真实信号做 `meta-label` 可行性审计。",
        "- 标签：按 FIFO 配对后的已实现 `gross_pnl>0` 记为成功，否则记为失败。",
        "- 注意：本阶段只做离线分桶与时间样本外验证，不改正式策略。",
        "",
        "## 窗口结果",
        "",
        _to_markdown(windows),
        "",
        "## 分桶结果",
        "",
        _to_markdown(buckets, max_rows=50),
        "",
        "## 时间样本外分桶",
        "",
        _to_markdown(window_buckets, max_rows=80),
        "",
        "## 初步判断",
        "",
        f"- 样本数：`{len(samples)}`，有闭合轮次标签的样本：`{int((samples['round_trip_count'] > 0).sum())}`。",
        f"- 总体 meta success rate：`{samples['meta_success'].mean() * 100.0:.2f}%`。",
        "- 若高 rank/低 drawdown/特定 signal 桶在样本外仍明显优于低质量桶，则二级模型方向成立。",
        "- 若样本外分桶差异消失，则停止，不接入仓位倍率。",
        "",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    snapshots, trades, daily, size_map = load_inputs()
    round_trips = build_round_trips(trades, size_map)
    samples = build_samples(snapshots, round_trips, daily)
    windows = summarize_windows(samples)
    buckets = summarize_buckets(samples)
    window_buckets = summarize_window_buckets(samples)
    samples.to_csv(SAMPLES_PATH, index=False, encoding="utf-8-sig")
    windows.to_csv(WINDOW_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    buckets.to_csv(BUCKET_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    window_buckets.to_csv(WINDOW_BUCKET_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    REPORT_PATH.write_text(build_report(samples, windows, buckets, window_buckets), encoding="utf-8")
    MANIFEST_PATH.write_text(
        json.dumps(
            {
                "model_tag": MODEL_TAG,
                "official_manifest": build_official_stage78_manifest(),
                "base_risk_ratio": BASE_RISK_RATIO,
                "capital": OFFICIAL_STAGE78_CAPITAL,
                "paths": {
                    "entry_snapshots": str(ENTRY_SNAPSHOTS_PATH.resolve()),
                    "trades": str(TRADES_PATH.resolve()),
                    "daily": str(DAILY_PATH.resolve()),
                    "samples": str(SAMPLES_PATH.resolve()),
                    "window_summary": str(WINDOW_SUMMARY_PATH.resolve()),
                    "bucket_summary": str(BUCKET_SUMMARY_PATH.resolve()),
                    "window_bucket_summary": str(WINDOW_BUCKET_SUMMARY_PATH.resolve()),
                    "report": str(REPORT_PATH.resolve()),
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(REPORT_PATH.resolve())
    print(windows.to_string(index=False))
    print(buckets.head(30).to_string(index=False))
    print(window_buckets.head(60).to_string(index=False))


if __name__ == "__main__":
    main()
