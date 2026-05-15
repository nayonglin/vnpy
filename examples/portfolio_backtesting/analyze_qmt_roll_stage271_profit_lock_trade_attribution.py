from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any

import pandas as pd
from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.database import get_database


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"
MODEL_TAG: str = "stage271_profit_lock_trade_attribution_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage271_profit_lock_trade_attribution"

TRADES_PATH: Path = OUTPUT_DIR / "qmt_roll_official_stage78_1_trades_2020_2026_04.csv"
STATS_PATH: Path = OUTPUT_DIR / "qmt_roll_official_stage78_1_statistics.json"

CURRENT_TIERS: list[tuple[float, float]] = [
    (0.30, 0.20),
    (0.20, 0.15),
    (0.10, 0.08),
    (0.05, 0.03),
    (0.03, 0.01),
    (0.02, 0.001),
]

MFE_BUCKETS: list[tuple[str, float, float]] = [
    ("lt_2pct", -math.inf, 0.02),
    ("2_3pct", 0.02, 0.03),
    ("3_5pct", 0.03, 0.05),
    ("5_10pct", 0.05, 0.10),
    ("10_20pct", 0.10, 0.20),
    ("20_30pct", 0.20, 0.30),
    ("gte_30pct", 0.30, math.inf),
]


@dataclass
class OpenLot:
    trade_id: str
    vt_symbol: str
    direction: str
    datetime: pd.Timestamp
    price: float
    remaining_volume: float


def _normalize_datetime(series: pd.Series) -> pd.Series:
    values = pd.to_datetime(series, errors="coerce")
    try:
        return values.dt.tz_localize(None)
    except TypeError:
        return values.dt.tz_convert(None)


def _parse_vt_symbol(vt_symbol: str) -> tuple[str, Exchange]:
    symbol, exchange = vt_symbol.split(".", 1)
    return symbol, Exchange(exchange)


def _product_from_vt_symbol(vt_symbol: str) -> str:
    symbol, exchange = vt_symbol.split(".", 1)
    product = re.sub(r"\d+$", "", symbol)
    return f"{product}.{exchange}"


def _load_trades() -> pd.DataFrame:
    if not TRADES_PATH.exists():
        raise FileNotFoundError(f"Missing trade file: {TRADES_PATH}")

    trades = pd.read_csv(TRADES_PATH, encoding="utf-8-sig")
    trades["datetime"] = _normalize_datetime(trades["datetime"])
    trades["date"] = pd.to_datetime(trades["date"], errors="coerce").dt.normalize()
    trades["trade_id"] = trades["trade_id"].astype(str)
    trades["vt_symbol"] = trades["vt_symbol"].astype(str)
    trades["direction"] = trades["direction"].astype(str)
    trades["offset"] = trades["offset"].astype(str)
    trades["price"] = pd.to_numeric(trades["price"], errors="coerce")
    trades["volume"] = pd.to_numeric(trades["volume"], errors="coerce").fillna(0.0)
    trades["exit_reason"] = trades.get("exit_reason", "").fillna("").astype(str)
    trades.sort_values(["datetime", "vt_symbol", "trade_id"], inplace=True)
    return trades


def _load_bars_for_trades(trades: pd.DataFrame) -> dict[str, pd.DataFrame]:
    database = get_database()
    bars_by_symbol: dict[str, pd.DataFrame] = {}

    for vt_symbol, group in trades.groupby("vt_symbol"):
        symbol, exchange = _parse_vt_symbol(vt_symbol)
        start_dt = pd.Timestamp(group["datetime"].min()).to_pydatetime() - timedelta(days=180)
        end_dt = pd.Timestamp(group["datetime"].max()).to_pydatetime() + timedelta(days=180)
        bars = database.load_bar_data(symbol, exchange, Interval.DAILY, start_dt, end_dt)

        rows: list[dict[str, Any]] = []
        for bar in bars:
            rows.append(
                {
                    "date": pd.Timestamp(bar.datetime).tz_localize(None).normalize(),
                    "open": float(bar.open_price),
                    "high": float(bar.high_price),
                    "low": float(bar.low_price),
                    "close": float(bar.close_price),
                    "volume": float(bar.volume),
                }
            )

        if rows:
            bars_df = pd.DataFrame(rows).drop_duplicates(subset=["date"]).sort_values("date")
            bars_by_symbol[vt_symbol] = bars_df.reset_index(drop=True)

    return bars_by_symbol


def _position_direction(row: dict[str, Any]) -> str | None:
    direction = str(row["direction"])
    offset = str(row["offset"])
    if offset == "Open":
        return "long" if direction == "Long" else "short"
    if offset == "Close":
        return "long" if direction == "Short" else "short"
    return None


def _pair_round_trips(trades: pd.DataFrame) -> pd.DataFrame:
    open_queues: dict[tuple[str, str], list[OpenLot]] = {}
    pairs: list[dict[str, Any]] = []

    for row in trades.to_dict("records"):
        direction = _position_direction(row)
        if direction is None:
            continue

        vt_symbol = str(row["vt_symbol"])
        key = (vt_symbol, direction)
        volume = float(row["volume"])

        if str(row["offset"]) == "Open":
            open_queues.setdefault(key, []).append(
                OpenLot(
                    trade_id=str(row["trade_id"]),
                    vt_symbol=vt_symbol,
                    direction=direction,
                    datetime=pd.Timestamp(row["datetime"]),
                    price=float(row["price"]),
                    remaining_volume=volume,
                )
            )
            continue

        remaining = volume
        queue = open_queues.get(key, [])
        while remaining > 1e-8 and queue:
            lot = queue[0]
            used_volume = min(float(lot.remaining_volume), remaining)
            pairs.append(
                {
                    "entry_trade_id": lot.trade_id,
                    "exit_trade_id": str(row["trade_id"]),
                    "vt_symbol": vt_symbol,
                    "product_vt_symbol": _product_from_vt_symbol(vt_symbol),
                    "direction": direction,
                    "entry_datetime": lot.datetime,
                    "exit_datetime": pd.Timestamp(row["datetime"]),
                    "entry_date": lot.datetime.normalize(),
                    "exit_date": pd.Timestamp(row["datetime"]).normalize(),
                    "entry_price": float(lot.price),
                    "exit_price": float(row["price"]),
                    "volume": float(used_volume),
                    "exit_reason": str(row.get("exit_reason", "")),
                }
            )
            lot.remaining_volume -= used_volume
            remaining -= used_volume
            if lot.remaining_volume <= 1e-8:
                queue.pop(0)

    return pd.DataFrame(pairs)


def _current_lock_pct(max_profit_pct: float) -> float:
    for trigger_pct, lock_pct in CURRENT_TIERS:
        if max_profit_pct >= trigger_pct:
            return lock_pct
    return 0.0


def _current_trigger_label(max_profit_pct: float) -> str:
    for trigger_pct, lock_pct in CURRENT_TIERS:
        if max_profit_pct >= trigger_pct:
            return f"{trigger_pct:.1%}->{lock_pct:.1%}"
    return "no_lock"


def _profit_bucket(profit_pct: float) -> str:
    for label, low, high in MFE_BUCKETS:
        if low <= profit_pct < high:
            return label
    return "unknown"


def _enrich_pairs_with_path_metrics(pairs: pd.DataFrame, bars_by_symbol: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for row in pairs.to_dict("records"):
        vt_symbol = str(row["vt_symbol"])
        bars = bars_by_symbol.get(vt_symbol)
        if bars is None or bars.empty:
            continue

        entry_date = pd.Timestamp(row["entry_date"]).normalize()
        exit_date = pd.Timestamp(row["exit_date"]).normalize()
        trade_bars = bars[(bars["date"] >= entry_date) & (bars["date"] <= exit_date)].copy()
        if trade_bars.empty:
            continue

        post_bars = bars[bars["date"] > exit_date].head(20).copy()
        entry_price = float(row["entry_price"])
        exit_price = float(row["exit_price"])
        direction = str(row["direction"])

        if direction == "long":
            pnl_pct = exit_price / entry_price - 1.0
            mfe_pct = float(trade_bars["high"].max()) / entry_price - 1.0
            max_close_profit_pct = float(trade_bars["close"].max()) / entry_price - 1.0
            mae_pct = float(trade_bars["low"].min()) / entry_price - 1.0
            post_best_profit_pct = (
                float(post_bars["high"].max()) / entry_price - 1.0 if not post_bars.empty else pnl_pct
            )
        else:
            pnl_pct = entry_price / exit_price - 1.0
            mfe_pct = entry_price / float(trade_bars["low"].min()) - 1.0
            max_close_profit_pct = entry_price / float(trade_bars["close"].min()) - 1.0
            mae_pct = entry_price / float(trade_bars["high"].max()) - 1.0
            post_best_profit_pct = (
                entry_price / float(post_bars["low"].min()) - 1.0 if not post_bars.empty else pnl_pct
            )

        current_lock = _current_lock_pct(max_close_profit_pct)
        capture_ratio = pnl_pct / mfe_pct if mfe_pct > 1e-12 else float("nan")
        giveback_pct = mfe_pct - pnl_pct
        missed_after_exit_pct = max(0.0, post_best_profit_pct - pnl_pct)
        locked_but_lost = bool(current_lock > 0 and pnl_pct < 0)
        lock_floor_breached = bool(current_lock > 0 and pnl_pct + 1e-10 < current_lock)

        enriched = dict(row)
        enriched.update(
            {
                "holding_days": int((exit_date - entry_date).days),
                "pnl_pct": float(pnl_pct),
                "mfe_pct": float(mfe_pct),
                "max_close_profit_pct": float(max_close_profit_pct),
                "mae_pct": float(mae_pct),
                "capture_ratio": float(capture_ratio) if math.isfinite(capture_ratio) else None,
                "giveback_from_mfe_pct": float(giveback_pct),
                "post20_best_profit_pct": float(post_best_profit_pct),
                "missed_after_exit_pct": float(missed_after_exit_pct),
                "current_lock_pct": float(current_lock),
                "current_trigger_label": _current_trigger_label(max_close_profit_pct),
                "mfe_bucket": _profit_bucket(mfe_pct),
                "max_close_profit_bucket": _profit_bucket(max_close_profit_pct),
                "lock_floor_breached": int(lock_floor_breached),
                "locked_but_lost": int(locked_but_lost),
            }
        )
        rows.append(enriched)

    return pd.DataFrame(rows)


def _safe_mean(series: pd.Series) -> float:
    values = pd.to_numeric(series, errors="coerce").dropna()
    return float(values.mean()) if not values.empty else 0.0


def _safe_median(series: pd.Series) -> float:
    values = pd.to_numeric(series, errors="coerce").dropna()
    return float(values.median()) if not values.empty else 0.0


def _summarize_by(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    grouped = df.groupby(group_cols, dropna=False)
    summary = grouped.agg(
        trade_legs=("exit_trade_id", "count"),
        win_rate=("pnl_pct", lambda s: float((pd.to_numeric(s, errors="coerce") > 0).mean())),
        avg_pnl_pct=("pnl_pct", _safe_mean),
        median_pnl_pct=("pnl_pct", _safe_median),
        avg_mfe_pct=("mfe_pct", _safe_mean),
        avg_max_close_profit_pct=("max_close_profit_pct", _safe_mean),
        avg_mae_pct=("mae_pct", _safe_mean),
        avg_capture_ratio=("capture_ratio", _safe_mean),
        avg_giveback_pct=("giveback_from_mfe_pct", _safe_mean),
        median_missed_after_exit_pct=("missed_after_exit_pct", _safe_median),
        locked_but_lost_count=("locked_but_lost", "sum"),
        lock_floor_breached_count=("lock_floor_breached", "sum"),
    ).reset_index()
    return summary


def _format_pct(value: Any) -> str:
    try:
        if pd.isna(value):
            return ""
        return f"{float(value) * 100:.2f}%"
    except Exception:
        return str(value)


def _format_table(df: pd.DataFrame, columns: list[str], *, max_rows: int = 20) -> str:
    if df.empty:
        return "- 无数据"

    view = df.loc[:, [column for column in columns if column in df.columns]].head(max_rows).copy()
    pct_columns = [
        col
        for col in view.columns
        if col.endswith("_pct") or col in {"win_rate", "avg_capture_ratio"}
    ]
    for column in pct_columns:
        view[column] = view[column].map(_format_pct)
    return view.to_markdown(index=False)


def _write_report(
    *,
    enriched: pd.DataFrame,
    bucket_summary: pd.DataFrame,
    trigger_summary: pd.DataFrame,
    exit_reason_summary: pd.DataFrame,
    year_summary: pd.DataFrame,
    paths: dict[str, Path],
) -> None:
    stats_payload: dict[str, Any] = {}
    if STATS_PATH.exists():
        stats_payload = json.loads(STATS_PATH.read_text(encoding="utf-8"))

    total_legs = int(len(enriched))
    lock_eligible = int((enriched["current_lock_pct"] > 0).sum()) if not enriched.empty else 0
    locked_but_lost = int(enriched["locked_but_lost"].sum()) if not enriched.empty else 0
    floor_breached = int(enriched["lock_floor_breached"].sum()) if not enriched.empty else 0
    avg_capture = _safe_mean(enriched.get("capture_ratio", pd.Series(dtype=float))) if not enriched.empty else 0.0
    avg_giveback = _safe_mean(enriched.get("giveback_from_mfe_pct", pd.Series(dtype=float))) if not enriched.empty else 0.0

    report = f"""# Stage271 盈利锁定分层交易级归因

## 定位

- 当前基准：Stage78-1 `official_stage78_1_defensive_50w_no_sizing_cap`。
- 本阶段只做交易级归因，不改正式参数，不做候选晋级。
- 数据源：`{TRADES_PATH.name}` 与 vn.py 本地日线数据库。
- 当前锁盈档位：`30->20, 20->15, 10->8, 5->3, 3->1, 2->0.1`。
- 注意：策略实际触发锁盈用的是收盘价更新后的 `max_profit_pct`，不是日内最高/最低的 MFE。本报告同时保留 MFE 作为路径归因。

## 外部调研与判断

- Walk-forward / out-of-sample 是交易参数研究的基本防线；purged CV 用于避免持仓窗口重叠造成的信息泄漏。
- Trailing stop 在趋势策略中有合理性，但常见失败是过早切断后续趋势，所以不能用全周期最优收益直接替换正式档位。
- 我的判断：先看 MFE/MAE/回吐/离场后继续趋势，再做低自由度 A/B/C；不做逐档任意搜索。

## 78-1 基准摘要

- 期末权益：`{stats_payload.get("end_balance", "")}`
- 总收益：`{stats_payload.get("total_return", "")}`
- 最大回撤：`{stats_payload.get("max_ddpercent", "")}`
- Sharpe：`{stats_payload.get("sharpe_ratio", "")}`
- 总交易次数：`{stats_payload.get("total_trade_count", "")}`

## 归因总览

- 已配对平仓腿数：`{total_legs}`
- 历史按收盘最大浮盈曾触发当前锁盈档位的腿数：`{lock_eligible}`
- 触发锁盈但最终亏损的腿数：`{locked_but_lost}`
- 按当前锁盈地板估算低于地板退出的腿数：`{floor_breached}`
- 平均利润捕获率：`{avg_capture:.4f}`
- 平均从最大浮盈回吐：`{avg_giveback:.4f}`

## 按收盘最大浮盈分桶

{_format_table(bucket_summary, ["max_close_profit_bucket", "trade_legs", "win_rate", "avg_pnl_pct", "avg_max_close_profit_pct", "avg_mfe_pct", "avg_mae_pct", "avg_capture_ratio", "avg_giveback_pct", "median_missed_after_exit_pct", "locked_but_lost_count", "lock_floor_breached_count"], max_rows=20)}

## 按当前触发档位

{_format_table(trigger_summary, ["current_trigger_label", "trade_legs", "win_rate", "avg_pnl_pct", "avg_max_close_profit_pct", "avg_mfe_pct", "avg_capture_ratio", "avg_giveback_pct", "median_missed_after_exit_pct", "locked_but_lost_count", "lock_floor_breached_count"], max_rows=20)}

## 按退出原因

{_format_table(exit_reason_summary, ["exit_reason", "trade_legs", "win_rate", "avg_pnl_pct", "avg_mfe_pct", "avg_capture_ratio", "avg_giveback_pct", "median_missed_after_exit_pct"], max_rows=30)}

## 按年份

{_format_table(year_summary, ["entry_year", "trade_legs", "win_rate", "avg_pnl_pct", "avg_mfe_pct", "avg_capture_ratio", "avg_giveback_pct", "median_missed_after_exit_pct"], max_rows=20)}

## 下一步候选空间

- 不做 6 个档位的任意网格搜索。
- Stage002 候选只允许低自由度：
  - `retain_ratio` 型：`lock=max(min_lock, MFE * retain_ratio)`，最多测试 3 个 retain 档。
  - `smooth_curve` 型：固定触发点，锁定曲线单调且平滑，不允许逐档乱跳。
  - `volatility_context` 仅作为归因标签，暂不作为交易条件。
- 晋级必须通过全周期、起始年份、季度冷启动、弱窗口、3x/5x滑点；否则不进入正式 78-1。

## 输出文件

- trade_attribution：`{paths["trade_attribution"].name}`
- bucket_summary：`{paths["bucket_summary"].name}`
- trigger_summary：`{paths["trigger_summary"].name}`
- exit_reason_summary：`{paths["exit_reason_summary"].name}`
- year_summary：`{paths["year_summary"].name}`
- summary_json：`{paths["summary_json"].name}`
"""
    paths["report"].write_text(report, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    trades = _load_trades()
    pairs = _pair_round_trips(trades)
    bars_by_symbol = _load_bars_for_trades(trades)
    enriched = _enrich_pairs_with_path_metrics(pairs, bars_by_symbol)
    if enriched.empty:
        raise RuntimeError("No paired trades with bar data.")

    enriched["entry_year"] = pd.to_datetime(enriched["entry_datetime"]).dt.year
    bucket_summary = _summarize_by(enriched, ["max_close_profit_bucket"])
    bucket_order = {label: index for index, (label, _, _) in enumerate(MFE_BUCKETS)}
    bucket_summary["bucket_order"] = bucket_summary["max_close_profit_bucket"].map(bucket_order).fillna(999)
    bucket_summary.sort_values("bucket_order", inplace=True)
    bucket_summary.drop(columns=["bucket_order"], inplace=True)

    trigger_summary = _summarize_by(enriched, ["current_trigger_label"])
    trigger_summary["trigger_order"] = trigger_summary["current_trigger_label"].map(
        {f"{trigger:.1%}->{lock:.1%}": index for index, (trigger, lock) in enumerate(CURRENT_TIERS)}
    ).fillna(999)
    trigger_summary.sort_values("trigger_order", inplace=True)
    trigger_summary.drop(columns=["trigger_order"], inplace=True)

    exit_reason_summary = _summarize_by(enriched, ["exit_reason"]).sort_values("trade_legs", ascending=False)
    year_summary = _summarize_by(enriched, ["entry_year"]).sort_values("entry_year")

    paths = {
        "trade_attribution": OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{MODEL_TAG}.csv",
        "bucket_summary": OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_summary_{MODEL_TAG}.csv",
        "trigger_summary": OUTPUT_DIR / f"{OUTPUT_PREFIX}_trigger_summary_{MODEL_TAG}.csv",
        "exit_reason_summary": OUTPUT_DIR / f"{OUTPUT_PREFIX}_exit_reason_summary_{MODEL_TAG}.csv",
        "year_summary": OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_summary_{MODEL_TAG}.csv",
        "summary_json": OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json",
        "report": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md",
    }

    enriched.to_csv(paths["trade_attribution"], index=False, encoding="utf-8-sig")
    bucket_summary.to_csv(paths["bucket_summary"], index=False, encoding="utf-8-sig")
    trigger_summary.to_csv(paths["trigger_summary"], index=False, encoding="utf-8-sig")
    exit_reason_summary.to_csv(paths["exit_reason_summary"], index=False, encoding="utf-8-sig")
    year_summary.to_csv(paths["year_summary"], index=False, encoding="utf-8-sig")

    summary_payload: dict[str, Any] = {
        "model_tag": MODEL_TAG,
        "baseline": "official_stage78_1_defensive_50w_no_sizing_cap",
        "current_tiers": CURRENT_TIERS,
        "paired_trade_legs": int(len(enriched)),
        "lock_eligible_legs": int((enriched["current_lock_pct"] > 0).sum()),
        "locked_but_lost_legs": int(enriched["locked_but_lost"].sum()),
        "lock_floor_breached_legs": int(enriched["lock_floor_breached"].sum()),
        "avg_capture_ratio": _safe_mean(enriched["capture_ratio"]),
        "avg_giveback_from_mfe_pct": _safe_mean(enriched["giveback_from_mfe_pct"]),
        "outputs": {key: str(value) for key, value in paths.items()},
    }
    paths["summary_json"].write_text(json.dumps(summary_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    _write_report(
        enriched=enriched,
        bucket_summary=bucket_summary,
        trigger_summary=trigger_summary,
        exit_reason_summary=exit_reason_summary,
        year_summary=year_summary,
        paths=paths,
    )

    print(json.dumps(summary_payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
