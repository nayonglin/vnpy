from __future__ import annotations

import argparse
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, time as dt_time, timedelta
import hashlib
import html
from io import BytesIO
import json
import math
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
from typing import Any

import numpy as np
import pandas as pd
from plotly.offline import get_plotlyjs
from tqsdk import BacktestFinished, TqApi, TqAuth, TqBacktest, TqSim


REPO_ROOT = Path(__file__).resolve().parents[4]
EXAMPLES_DIR = REPO_ROOT / "examples" / "portfolio_backtesting"
if str(EXAMPLES_DIR) not in sys.path:
    sys.path.insert(0, str(EXAMPLES_DIR))

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513  # noqa: E402
import analyze_qmt_roll_stage719_official_winner_trade_forensics as s719  # noqa: E402
import analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow as s901  # noqa: E402
from qmt_roll_official_live_config import (  # noqa: E402
    OFFICIAL_LIVE_ALIAS,
    OFFICIAL_LIVE_CAPITAL,
    OFFICIAL_LIVE_VERSION,
)
from vnpy.trader.setting import SETTINGS  # noqa: E402
from vnpy.trader.utility import ZoneInfo  # noqa: E402


LINE_ID = "futures_trend_winner_trade_forensics"
STAGE = "Stage038"
MODEL_TAG = "stage038_c9_15w_big_winner_multiscale_html_v2"
OUTPUT_DIR = (
    REPO_ROOT
    / "research"
    / "lines"
    / LINE_ID
    / "outputs"
    / "stage038_c9_15w_big_winner_multiscale_html"
)
HTML_PATH = OUTPUT_DIR / "index.html"
CLOSED_LOTS_PATH = OUTPUT_DIR / "closed_lots.csv"
WINNERS_PATH = OUTPUT_DIR / "big_winners.csv"
SELECTED_EPISODES_PATH = OUTPUT_DIR / "selected_profit_loss_episodes.csv"
MINUTE_15M_PATH = OUTPUT_DIR / "winner_bars_15m.csv"
STRATEGY_DAILY_PATH = OUTPUT_DIR / "strategy_daily.csv"
MANIFEST_PATH = OUTPUT_DIR / "chart_manifest.csv"
SUMMARY_PATH = OUTPUT_DIR / "summary.json"
FULL_OUTPUT_DIR = (
    REPO_ROOT
    / "research"
    / "lines"
    / LINE_ID
    / "outputs"
    / "stage042_c9_15w_all_trade_multiscale_html"
)
FULL_HTML_PATH = FULL_OUTPUT_DIR / "index.html"
FULL_MANIFEST_PATH = FULL_OUTPUT_DIR / "chart_manifest.csv"
FULL_SUMMARY_PATH = FULL_OUTPUT_DIR / "summary.json"
STAGE037C_SOURCE_COMMIT = "ec4f1a39b48ed168662059aea7a98030a01a3ccf"
STAGE037C_SOURCE_ROOT = (
    "research/lines/futures_trend_rollover_shape_same_volume/artifacts/stage037"
)
STAGE037C_OUTPUT_DIR = (
    REPO_ROOT
    / "research"
    / "lines"
    / LINE_ID
    / "outputs"
    / "stage045_stage037c_all_trade_multiscale_html"
)
STAGE037C_HTML_PATH = STAGE037C_OUTPUT_DIR / "index.html"
STAGE037C_CLOSED_LOTS_PATH = STAGE037C_OUTPUT_DIR / "closed_lots.csv"
STAGE037C_SELECTED_EPISODES_PATH = STAGE037C_OUTPUT_DIR / "selected_profit_loss_episodes.csv"
STAGE037C_MINUTE_PATH = STAGE037C_OUTPUT_DIR / "bars_15m_not_used.csv"
STAGE037C_DAILY_PATH = STAGE037C_OUTPUT_DIR / "strategy_daily.csv"
STAGE037C_MANIFEST_PATH = STAGE037C_OUTPUT_DIR / "chart_manifest.csv"
STAGE037C_SUMMARY_PATH = STAGE037C_OUTPUT_DIR / "summary.json"
STAGE061_TOP10_SOURCE_COMMIT = "6750783fe7aab92e6dbdd6820fa212e2e53ea353"
STAGE061_TOP10_SOURCE_ROOT = (
    "research/lines/futures_trend_rollover_shape_same_volume/artifacts/"
    "stage061_ai_top10_to_top19_fullperiod"
)
STAGE061_TOP10_OUTPUT_DIR = (
    REPO_ROOT / "research" / "lines" / LINE_ID / "outputs"
    / "stage049_stage061_top10_fu_all_trade_multiscale_html"
)
STAGE061_TOP10_DATABASE_PATH = (
    REPO_ROOT / ".worktrees" / "stage051-deep-v-rebound-failure-long-filter"
    / ".vntrader" / "database.db"
)
STAGE061_TOP10_DATABASE_SHA256 = "ee83eae2159afec2b745a5827f73aaf9da1e71d65af2c0a624496555c08b6ebe"
DAILY_PATH = EXAMPLES_DIR / "backtest_outputs" / (
    "qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow_daily_"
    "stage901_stage847_c9_2026_ytd_live_shadow_v1.csv"
)
DATABASE_PATH = REPO_ROOT / ".vntrader" / "database.db"
STAGE037C_FROZEN_DATABASE_PATH = (
    REPO_ROOT
    / ".worktrees"
    / "stage037-short-mirror-block"
    / ".vntrader"
    / "database.db"
)
STAGE037C_FROZEN_DATABASE_SHA256 = "d7375edac99e182ba3524abfbed92abb035e101d05744cb801ec5c7b5dbd47f5"
ACTIVE_DATABASE_PATH = DATABASE_PATH
PREFER_DATABASE_DAILY = False
MAPPING_PATH = EXAMPLES_DIR / "backtest_outputs" / "tqsdk_all_futures_main_contract_mapping_2010_2026_04.csv"
LOCAL_MINUTE_ROOT = EXAMPLES_DIR / "downloaded_futures"

START = pd.Timestamp("2018-01-01")
DEFAULT_END = pd.Timestamp("2026-08-12")
DAILY_PRE = 300
DAILY_POST = 50
INTRADAY_PRE = 5
INTRADAY_POST = 5
MONTHLY_PRE = 10
MONTHLY_POST = 10
CHINA_TZ = ZoneInfo("Asia/Shanghai")
MA_PERIODS = (5, 10, 20, 40)
# Include a small whole-week cushion because the earliest available source
# week can be partial even when the product calendar contains that period.
WEEKLY_MA_WARMUP_WEEKS = max(MA_PERIODS) + 5
MONTHLY_MA_WARMUP_MONTHS = max(MA_PERIODS) + 5
# A 40-period MA on a 30-trading-day candle needs at least 1,200 prior
# trading days.  One additional bucket keeps the first computed bar immune to
# where the materialized context happens to begin inside the fixed calendar
# bucket.
TRADING_DAY_MA_WARMUP_DAYS = max(MA_PERIODS) * 30 + 30


@dataclass(frozen=True)
class FetchStatus:
    vt_symbol: str
    tq_symbol: str
    start: str
    end: str
    rows: int
    elapsed_seconds: float
    status: str
    message: str


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        result = float(value)
        return result if math.isfinite(result) else None
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if pd.isna(value):
        return None
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_git_csv(commit: str, path: str) -> tuple[pd.DataFrame, str]:
    result = subprocess.run(
        ["git", "show", f"{commit}:{path}"],
        cwd=REPO_ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    payload = result.stdout
    return pd.read_csv(BytesIO(payload), encoding="utf-8-sig"), hashlib.sha256(payload).hexdigest()


def _load_stage037c_frozen_source() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any], dict[str, Any]]:
    names = {
        "trades": "stage037_trades.csv",
        "curve": "stage037_abc_curve.csv",
        "summary": "stage037_abc_summary.csv",
    }
    frames: dict[str, pd.DataFrame] = {}
    hashes: dict[str, str] = {}
    paths: dict[str, str] = {}
    for key, name in names.items():
        path = f"{STAGE037C_SOURCE_ROOT}/{name}"
        frames[key], hashes[key] = _read_git_csv(STAGE037C_SOURCE_COMMIT, path)
        paths[key] = path

    trades = frames["trades"].loc[frames["trades"]["experiment_arm"].eq("C")].copy()
    curve = frames["curve"].loc[frames["curve"]["experiment_arm"].eq("C")].copy()
    summary_rows = frames["summary"].loc[frames["summary"]["experiment_arm"].eq("C")].copy()
    if len(trades) != 733 or curve.empty or len(summary_rows) != 1:
        raise RuntimeError(
            "Frozen Stage037 C evidence mismatch: "
            f"trades={len(trades)}, curve={len(curve)}, summary={len(summary_rows)}."
        )
    metrics = summary_rows.iloc[0].to_dict()
    if not math.isclose(float(metrics["end_equity"]), 17_051_717.30, rel_tol=0.0, abs_tol=0.01):
        raise RuntimeError(f"Frozen Stage037 C end equity mismatch: {metrics['end_equity']}")
    metrics["end_equity"] = round(float(metrics["end_equity"]), 2)
    trades = trades.sort_values(["datetime", "trade_id"]).reset_index(drop=True)
    curve = curve.sort_values("date").reset_index(drop=True)
    provenance = {
        "source_commit": STAGE037C_SOURCE_COMMIT,
        "source_paths": paths,
        "source_sha256": hashes,
        "source_arm": "C",
    }
    return curve, trades, metrics, provenance


def _load_stage061_top10_frozen_source() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any], dict[str, Any]]:
    """Read the immutable T10 arm, never rerun or substitute the current strategy."""
    frames, hashes, paths = {}, {}, {}
    for key, filename in {
        "trades": "stage061_trades.csv",
        "curve": "stage061_equity_curve.csv",
        "summary": "stage061_summary.csv",
    }.items():
        paths[key] = f"{STAGE061_TOP10_SOURCE_ROOT}/{filename}"
        frame, hashes[key] = _read_git_csv(STAGE061_TOP10_SOURCE_COMMIT, paths[key])
        frames[key] = frame.loc[frame["experiment_arm"].eq("T10")].copy()
    trades = frames["trades"].sort_values(["datetime", "trade_id"]).reset_index(drop=True)
    curve = frames["curve"].sort_values("date").reset_index(drop=True)
    curve["date"] = pd.to_datetime(curve["date"], errors="raise").dt.strftime("%Y-%m-%d")
    rows = frames["summary"]
    if len(trades) != 798 or len(curve) != 2101 or len(rows) != 1:
        raise RuntimeError(
            f"Frozen Top10 evidence mismatch: trades={len(trades)}, curve={len(curve)}, summary={len(rows)}"
        )
    metrics = rows.iloc[0].to_dict()
    if (
        trades["trade_id"].duplicated().any()
        or curve["date"].duplicated().any()
        or curve["date"].iloc[0] != "2018-01-02"
        or curve["date"].iloc[-1] != "2026-08-28"
        or any(set(frame["profile"]) != {"stage061_top10_plus_fu"} for frame in frames.values())
        or int(metrics["total_trade_count"]) != 798
        or not math.isclose(float(metrics["end_equity"]), 21_870_488.80, abs_tol=0.01, rel_tol=0)
        or not math.isclose(float(curve["account_equity"].iloc[-1]), 21_870_488.80, abs_tol=0.01, rel_tol=0)
    ):
        raise RuntimeError("Frozen Top10 evidence mismatch: identity, dates, or equity")
    metrics["end_equity"] = round(float(metrics["end_equity"]), 2)
    return curve, trades, metrics, {
        "source_commit": STAGE061_TOP10_SOURCE_COMMIT,
        "source_paths": paths, "source_sha256": hashes, "source_arm": "T10",
    }


def _closed_lots_from_trade_ledger(
    trades: pd.DataFrame,
    *,
    sizes: dict[str, float],
    allow_residual_open: bool = False,
    source_prefix: str = "stage037c",
) -> pd.DataFrame:
    """Reconstruct completed lots from a frozen trade ledger using strict FIFO."""
    normalized_sizes = {str(key).lower(): float(value) for key, value in sizes.items()}
    queues: dict[tuple[str, str], deque[dict[str, Any]]] = {}
    rows: list[dict[str, Any]] = []
    direction_map = {"多": "long", "long": "long", "空": "short", "short": "short"}
    offset_map = {"开": "open", "open": "open", "平": "close", "close": "close"}
    ordered = trades.copy()
    ordered["_datetime"] = pd.to_datetime(ordered["datetime"], errors="raise", utc=True)
    ordered = ordered.sort_values(["_datetime", "trade_id"]).reset_index(drop=True)

    for trade in ordered.to_dict("records"):
        vt_symbol = str(trade["vt_symbol"])
        direction = direction_map.get(str(trade["direction"]).strip().lower())
        offset = offset_map.get(str(trade["offset"]).strip().lower())
        if direction is None or offset is None:
            raise RuntimeError(
                f"Unsupported frozen trade side: {trade['direction']}/{trade['offset']} ({trade['trade_id']})."
            )
        volume = float(trade["volume"])
        if volume <= 0.0:
            raise RuntimeError(f"Non-positive frozen trade volume: {trade['trade_id']}={volume}")
        size = normalized_sizes.get(vt_symbol.lower())
        if size is None:
            raise RuntimeError(f"Missing contract size metadata for frozen trade {vt_symbol}.")
        if offset == "open":
            queues.setdefault((vt_symbol, direction), deque()).append(
                {**trade, "remaining": volume, "size": size}
            )
            continue

        position_direction = "long" if direction == "short" else "short"
        queue = queues.setdefault((vt_symbol, position_direction), deque())
        remaining = volume
        while remaining > 1e-12:
            if not queue:
                raise RuntimeError(
                    f"Unmatched frozen close {trade['trade_id']} for {vt_symbol} {position_direction}: "
                    f"remaining={remaining}."
                )
            opened = queue[0]
            matched = min(remaining, float(opened["remaining"]))
            entry_price = float(opened["price"])
            exit_price = float(trade["price"])
            sign = 1.0 if position_direction == "long" else -1.0
            realized_pnl = (exit_price - entry_price) * matched * size * sign
            entry_date = pd.Timestamp(opened["date"]).normalize()
            exit_date = pd.Timestamp(trade["date"]).normalize()
            exit_reason = trade.get("exit_reason", "")
            rows.append(
                {
                    "lot_id": f"{source_prefix}.{len(rows) + 1}",
                    "open_trade_id": str(opened["trade_id"]),
                    "close_trade_id": str(trade["trade_id"]),
                    "vt_symbol": vt_symbol,
                    "product": s719._infer_product(vt_symbol),
                    "direction": position_direction,
                    "entry_date": entry_date.date().isoformat(),
                    "exit_date": exit_date.date().isoformat(),
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "volume": matched,
                    "size": size,
                    "realized_pnl": realized_pnl,
                    "risk_amount": np.nan,
                    "r_multiple": np.nan,
                    "holding_calendar_days": int((exit_date - entry_date).days),
                    "exit_reason": "" if pd.isna(exit_reason) else str(exit_reason),
                    "signal": "",
                    "winner": int(realized_pnl > 0.0),
                }
            )
            remaining -= matched
            opened["remaining"] = float(opened["remaining"]) - matched
            if float(opened["remaining"]) <= 1e-12:
                queue.popleft()

    residual = [
        (vt_symbol, direction, sum(float(item["remaining"]) for item in queue))
        for (vt_symbol, direction), queue in queues.items()
        if queue
    ]
    if residual and not allow_residual_open:
        raise RuntimeError(f"Frozen {source_prefix} ledger has unclosed FIFO positions: {residual[:10]}")
    result = pd.DataFrame(rows)
    result.attrs["residual_open_positions"] = [
        {"vt_symbol": symbol, "direction": direction, "volume": volume}
        for symbol, direction, volume in residual
    ]
    return result


def _latest_completed_date() -> pd.Timestamp:
    if DAILY_PATH.exists():
        daily = pd.read_csv(DAILY_PATH, usecols=["date"])
        values = pd.to_datetime(daily["date"], errors="coerce").dropna()
        if len(values):
            return pd.Timestamp(values.max()).normalize()
    return DEFAULT_END


def _run_current_c9(end: pd.Timestamp) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame], Any]:
    metadata = s513._metadata()
    combined, frames, spec = s901._run_live_c9(metadata, START, end)
    closed = s719._build_closed_lots(
        frames.get("trades", pd.DataFrame()),
        frames.get("entry_risk", pd.DataFrame()),
        frames.get("entry_candidates", pd.DataFrame()),
        metadata,
    )
    if closed.empty:
        raise RuntimeError("Current C9/15w replay produced no closed lots.")
    closed["official_live_version"] = OFFICIAL_LIVE_VERSION
    closed["account_capital"] = OFFICIAL_LIVE_CAPITAL
    selected = _selected_tail_episodes(closed)
    if selected.empty:
        raise RuntimeError("Current C9/15w replay produced no profit/loss tail episodes.")
    return combined, closed, frames, spec


def _strategy_inputs(
    end: pd.Timestamp,
    *,
    reuse_existing: bool,
    closed_path: Path = CLOSED_LOTS_PATH,
    selected_path: Path = SELECTED_EPISODES_PATH,
    daily_path: Path = STRATEGY_DAILY_PATH,
    summary_path: Path = SUMMARY_PATH,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, Any | None, dict[str, Any]]:
    if not reuse_existing:
        combined, closed, _frames, spec = _run_current_c9(end)
        return combined, closed, _selected_tail_episodes(closed), spec, {}

    required = (closed_path, selected_path, daily_path, summary_path)
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Cannot reuse missing atlas artifacts: {missing}")
    combined = pd.read_csv(daily_path, encoding="utf-8-sig")
    closed = pd.read_csv(closed_path, encoding="utf-8-sig")
    selected = pd.read_csv(selected_path, encoding="utf-8-sig")
    prior_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if combined.empty or closed.empty or selected.empty:
        raise RuntimeError("Existing atlas strategy artifacts are empty.")
    return combined, closed, selected, None, prior_summary


def _trade_episodes(closed: pd.DataFrame) -> pd.DataFrame:
    """Collapse every entry and its partial exits into one complete episode."""
    rows: list[dict[str, Any]] = []
    for open_trade_id, group in closed.groupby("open_trade_id", sort=False):
        group = group.sort_values(["exit_date", "lot_id"]).reset_index(drop=True)
        first, final = group.iloc[0], group.iloc[-1]
        risk_amount = pd.to_numeric(group["risk_amount"], errors="coerce").sum(min_count=1)
        realized_pnl = float(pd.to_numeric(group["realized_pnl"], errors="coerce").sum())
        close_volume = pd.to_numeric(group["volume"], errors="coerce").fillna(0.0)
        close_price = pd.to_numeric(group["exit_price"], errors="coerce")
        valid_close = close_volume.gt(0.0) & close_price.notna()
        total_close_volume = float(close_volume.loc[valid_close].sum())
        weighted_exit_price = (
            float((close_price.loc[valid_close] * close_volume.loc[valid_close]).sum())
            / total_close_volume
            if total_close_volume > 0.0
            else np.nan
        )
        entry_price = float(first["entry_price"])
        price_change_pct = (
            (weighted_exit_price - entry_price) / entry_price * 100.0
            if math.isfinite(weighted_exit_price) and entry_price != 0.0
            else np.nan
        )
        if pd.isna(price_change_pct):
            price_change_label = "价格涨跌 N/A"
        elif price_change_pct > 0.0:
            price_change_label = f"价格上涨 {price_change_pct:.2f}%"
        elif price_change_pct < 0.0:
            price_change_label = f"价格下跌 {abs(price_change_pct):.2f}%"
        else:
            price_change_label = "价格持平 0.00%"
        rows.append(
            {
                **first.to_dict(),
                "lot_id": ",".join(group["lot_id"].astype(str)),
                "close_trade_id": ",".join(group["close_trade_id"].astype(str)),
                "open_trade_id": str(open_trade_id),
                "exit_date": final["exit_date"],
                "exit_price": float(final["exit_price"]),
                "exit_reason": str(final["exit_reason"]),
                "volume": float(pd.to_numeric(group["volume"], errors="coerce").sum()),
                "realized_pnl": realized_pnl,
                "weighted_exit_price": weighted_exit_price,
                "price_change_pct": price_change_pct,
                "price_change_label": price_change_label,
                "risk_amount": risk_amount,
                "r_multiple": realized_pnl / risk_amount if pd.notna(risk_amount) and risk_amount else np.nan,
                "holding_calendar_days": int((pd.Timestamp(final["exit_date"]) - pd.Timestamp(first["entry_date"])).days),
                "lot_count": int(len(group)),
            }
        )
    return pd.DataFrame(rows)


def _selected_tail_episodes(closed: pd.DataFrame) -> pd.DataFrame:
    """Select symmetric profit/loss R tails from complete entry episodes."""
    episodes = _trade_episodes(closed)
    positive = episodes[episodes["realized_pnl"].gt(0.0)]
    negative = episodes[episodes["realized_pnl"].lt(0.0)]
    profit_r_threshold = float(positive.loc[positive["r_multiple"].gt(0.0), "r_multiple"].quantile(0.80))
    profit_pnl_threshold = float(positive["realized_pnl"].quantile(0.80))
    loss_r_threshold = float(negative.loc[negative["r_multiple"].lt(0.0), "r_multiple"].quantile(0.20))
    loss_pnl_threshold = float(negative["realized_pnl"].quantile(0.20))
    profit_selected = episodes["realized_pnl"].gt(0.0) & (
        episodes["r_multiple"].ge(profit_r_threshold)
        | (episodes["r_multiple"].isna() & episodes["realized_pnl"].ge(profit_pnl_threshold))
    )
    loss_selected = episodes["realized_pnl"].lt(0.0) & (
        episodes["r_multiple"].le(loss_r_threshold)
        | (episodes["r_multiple"].isna() & episodes["realized_pnl"].le(loss_pnl_threshold))
    )
    episodes["result_type"] = np.where(
        profit_selected,
        "profit",
        np.where(loss_selected, "loss", "not_selected"),
    )
    episodes["selection_basis"] = np.where(
        episodes["r_multiple"].ge(profit_r_threshold) & profit_selected,
        "episode R前20%",
        np.where(
            episodes["r_multiple"].isna() & profit_selected,
            "episode盈利额前20%（R缺失）",
            np.where(
                episodes["r_multiple"].le(loss_r_threshold) & loss_selected,
                "episode亏损R最差20%",
                np.where(
                    episodes["r_multiple"].isna() & loss_selected,
                    "episode亏损额最差20%（R缺失）",
                    "未入选",
                ),
            ),
        ),
    )
    episodes["profit_r_threshold"] = profit_r_threshold
    episodes["profit_pnl_threshold"] = profit_pnl_threshold
    episodes["loss_r_threshold"] = loss_r_threshold
    episodes["loss_pnl_threshold"] = loss_pnl_threshold
    result = episodes[episodes["result_type"].ne("not_selected")].copy()
    result["r_magnitude"] = result["r_multiple"].abs()
    result = result.sort_values(
        ["result_type", "r_magnitude", "realized_pnl"],
        ascending=[False, False, False],
        na_position="last",
    ).reset_index(drop=True)
    result["result_rank"] = result.groupby("result_type", sort=False).cumcount() + 1
    return result


def _all_trade_episodes(closed: pd.DataFrame) -> pd.DataFrame:
    episodes = _trade_episodes(closed)
    tails = _selected_tail_episodes(closed)
    tail_by_id = tails.set_index("open_trade_id")
    episodes["result_type"] = np.where(
        episodes["realized_pnl"].gt(0.0),
        "profit",
        np.where(episodes["realized_pnl"].lt(0.0), "loss", "flat"),
    )
    episodes["is_tail"] = episodes["open_trade_id"].isin(tail_by_id.index).astype(int)
    episodes["draw_intraday"] = episodes["is_tail"]
    episodes["selection_basis"] = "全量交易（非尾部）"
    for column in [
        "profit_r_threshold",
        "profit_pnl_threshold",
        "loss_r_threshold",
        "loss_pnl_threshold",
    ]:
        episodes[column] = float(tails[column].iloc[0])
    for index, open_trade_id in episodes["open_trade_id"].items():
        if open_trade_id in tail_by_id.index:
            episodes.at[index, "selection_basis"] = str(tail_by_id.at[open_trade_id, "selection_basis"])
    episodes["r_magnitude"] = episodes["r_multiple"].abs()
    episodes = episodes.sort_values(
        ["result_type", "r_magnitude", "realized_pnl"],
        ascending=[True, False, False],
        na_position="last",
    ).reset_index(drop=True)
    episodes["result_rank"] = episodes.groupby("result_type", sort=False).cumcount() + 1
    return episodes


def _contract_daily(vt_symbol: str) -> pd.DataFrame:
    bars = pd.DataFrame() if PREFER_DATABASE_DAILY else s719._read_contract_bars(vt_symbol).copy()
    if bars.empty:
        symbol, exchange = vt_symbol.split(".", 1)
        with sqlite3.connect(ACTIVE_DATABASE_PATH) as connection:
            bars = pd.read_sql_query(
                """
                SELECT datetime AS date,
                       open_price AS open,
                       high_price AS high,
                       low_price AS low,
                       close_price AS close,
                       volume,
                       open_interest AS close_oi
                  FROM dbbardata
                 WHERE symbol = ? AND exchange = ? AND interval = 'd'
                 ORDER BY datetime
                """,
                connection,
                params=(symbol, exchange),
            )
    if bars.empty:
        raise RuntimeError(f"Missing daily bars in CSV and vn.py database for {vt_symbol}.")
    bars["date"] = pd.to_datetime(bars["date"], errors="coerce").dt.normalize()
    bars = bars.dropna(subset=["date", "open", "high", "low", "close"]).copy()
    if "volume" not in bars.columns:
        bars["volume"] = 0.0
    bars["volume"] = pd.to_numeric(bars["volume"], errors="coerce").fillna(0.0)
    return bars.drop_duplicates("date").sort_values("date").reset_index(drop=True)


def _date_index(daily: pd.DataFrame, value: Any, *, exact: bool = False) -> int:
    date = pd.Timestamp(value).normalize()
    dates = daily["date"].to_numpy(dtype="datetime64[ns]")
    matches = np.flatnonzero(dates == np.datetime64(date))
    if len(matches):
        return int(matches[0])
    if exact:
        raise RuntimeError(f"Required trading day {date.date()} is absent from the chart calendar.")
    position = int(np.searchsorted(dates, np.datetime64(date)))
    return min(max(position, 0), len(daily) - 1)


def _window_dates(daily: pd.DataFrame, entry: Any, exit_: Any, pre: int, post: int) -> list[pd.Timestamp]:
    entry_index = _date_index(daily, entry, exact=True)
    exit_index = _date_index(daily, exit_, exact=True)
    start = max(0, entry_index - pre)
    end = min(len(daily), exit_index + post + 1)
    return [pd.Timestamp(value).normalize() for value in daily.iloc[start:end]["date"]]


def _main_mapping() -> pd.DataFrame:
    mapping = pd.read_csv(MAPPING_PATH, encoding="utf-8-sig")
    mapping["date"] = pd.to_datetime(mapping["date"], errors="coerce").dt.normalize()
    mapping = mapping.dropna(subset=["date", "main_contract_vt"]).copy()
    return mapping.sort_values(["product", "exchange", "date"]).reset_index(drop=True)


def _product_calendar(mapping: pd.DataFrame, vt_symbol: str) -> list[pd.Timestamp]:
    exchange = str(vt_symbol).split(".", 1)[1]
    product = s719._infer_product(vt_symbol)
    values = mapping[
        mapping["product"].astype(str).str.lower().eq(product.lower()) & mapping["exchange"].eq(exchange)
    ]["date"].drop_duplicates().sort_values()
    if values.empty:
        raise RuntimeError(f"Missing product trading calendar for {vt_symbol}.")
    return [pd.Timestamp(value).normalize() for value in values]


def _context_daily(
    row: Any,
    mapping: pd.DataFrame,
    bar_cache: dict[str, pd.DataFrame],
    *,
    allow_daily_download: bool = True,
    allow_noncritical_daily_gaps: bool = False,
    data_end: pd.Timestamp | None = None,
) -> tuple[pd.DataFrame, list[pd.Timestamp]]:
    product_value = str(row.product)
    if "." in product_value:
        product, exchange = product_value.split(".", 1)
    else:
        product = product_value
        exchange = str(row.vt_symbol).split(".", 1)[1]
    calendar = mapping[
        mapping["product"].astype(str).str.lower().eq(product.lower()) & mapping["exchange"].eq(exchange)
    ].drop_duplicates("date").sort_values("date").reset_index(drop=True)
    if data_end is not None:
        calendar = calendar[calendar["date"].le(pd.Timestamp(data_end).normalize())].reset_index(drop=True)
    calendar["trading_day_index"] = np.arange(len(calendar), dtype=int)
    entry_date = pd.Timestamp(row.entry_date).normalize()
    exit_date = pd.Timestamp(row.exit_date).normalize()
    entry_index = _date_index(calendar, entry_date, exact=True)
    exit_index = _date_index(calendar, exit_date, exact=True)
    daily_display_start = max(0, entry_index - DAILY_PRE)
    daily_display_end = min(len(calendar), exit_index + DAILY_POST + 1)
    daily_display_dates = set(calendar.iloc[daily_display_start:daily_display_end]["date"])

    # Daily candles honor the exact trading-day window requested by the user.
    # Weekly candles retain their established whole-week boundaries through a
    # separate visibility mask, so tightening the daily panel does not create
    # partial or missing boundary weeks.
    weekly_display_start = daily_display_start
    weekly_display_end = daily_display_end
    first_period = calendar.loc[weekly_display_start, "date"].to_period("W-FRI")
    last_period = calendar.loc[weekly_display_end - 1, "date"].to_period("W-FRI")
    while (
        weekly_display_start > 0
        and calendar.loc[weekly_display_start - 1, "date"].to_period("W-FRI") == first_period
    ):
        weekly_display_start -= 1
    while (
        weekly_display_end < len(calendar)
        and calendar.loc[weekly_display_end, "date"].to_period("W-FRI") == last_period
    ):
        weekly_display_end += 1
    weekly_display_dates = set(calendar.iloc[weekly_display_start:weekly_display_end]["date"])

    monthly_start_period = entry_date.to_period("M") - MONTHLY_PRE
    monthly_end_period = exit_date.to_period("M") + MONTHLY_POST
    calendar_months = calendar["date"].dt.to_period("M")
    monthly_visible_indices = calendar.index[
        (calendar_months >= monthly_start_period) & (calendar_months <= monthly_end_period)
    ]
    if len(monthly_visible_indices):
        monthly_display_start = int(monthly_visible_indices[0])
        monthly_display_end = int(monthly_visible_indices[-1]) + 1
    else:
        monthly_display_start = daily_display_start
        monthly_display_end = daily_display_end

    # Keep the requested chart window unchanged, but load enough earlier daily
    # bars to seed genuine 40-week and 40-month moving averages.  The monthly
    # panel has its own wider visible window, while the original three panels
    # retain their existing display dates.
    warmup_start = weekly_display_start
    if weekly_display_start > 0:
        prior_periods = (
            calendar.iloc[:weekly_display_start]["date"]
            .dt.to_period("W-FRI")
            .drop_duplicates()
            .tail(WEEKLY_MA_WARMUP_WEEKS)
        )
        if len(prior_periods):
            first_warmup_period = prior_periods.iloc[0]
            warmup_start = int(
                calendar.index[
                    calendar["date"].dt.to_period("W-FRI").eq(first_warmup_period)
                ][0]
            )
    monthly_warmup_start = monthly_display_start
    if monthly_display_start > 0:
        prior_months = (
            calendar.iloc[:monthly_display_start]["date"]
            .dt.to_period("M")
            .drop_duplicates()
            .tail(MONTHLY_MA_WARMUP_MONTHS)
        )
        if len(prior_months):
            first_warmup_month = prior_months.iloc[0]
            monthly_warmup_start = int(calendar.index[calendar_months.eq(first_warmup_month)][0])
    trading_day_warmup_start = max(0, monthly_display_start - TRADING_DAY_MA_WARMUP_DAYS)
    warmup_start = min(warmup_start, monthly_warmup_start, trading_day_warmup_start)
    context_end = max(daily_display_end, weekly_display_end, monthly_display_end)
    wanted = calendar.iloc[warmup_start:context_end].copy()
    def bars(source: str) -> pd.DataFrame:
        if source not in bar_cache:
            bar_cache[source] = _contract_daily(source)
        return bar_cache[source]

    exact_bars = bars(str(row.vt_symbol))
    exact_by_date = exact_bars.set_index("date")
    output: list[dict[str, Any]] = []
    missing_context_dates: list[str] = []
    local_minute_checked: set[str] = set()
    for item in wanted.itertuples(index=False):
        item_month = pd.Timestamp(item.date).to_period("M")
        monthly_display = monthly_start_period <= item_month <= monthly_end_period
        required_visible = (
            item.date in daily_display_dates
            or item.date in weekly_display_dates
            or monthly_display
        )
        source = str(row.vt_symbol) if item.date in exact_by_date.index else str(item.main_contract_vt)
        try:
            source_bars = bars(source)
        except RuntimeError:
            if allow_daily_download:
                raise
            source_bars = pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
            bar_cache[source] = source_bars
        matched = source_bars[source_bars["date"].eq(item.date)]
        if matched.empty and not allow_daily_download and source not in local_minute_checked:
            local_minute_checked.add(source)
            recovered = _daily_from_existing_minute_files(
                source,
                [pd.Timestamp(value).normalize() for value in calendar["date"]],
            )
            if not recovered.empty:
                combined_bars = (
                    recovered.copy()
                    if source_bars.empty
                    else pd.concat([source_bars, recovered], ignore_index=True, sort=False)
                )
                source_bars = (
                    combined_bars.drop_duplicates("date", keep="last")
                    .sort_values("date")
                    .reset_index(drop=True)
                )
                bar_cache[source] = source_bars
                matched = source_bars[source_bars["date"].eq(item.date)]
        if matched.empty and allow_daily_download:
            downloaded = _fetch_daily_tq(source, wanted["date"].min(), wanted["date"].max())
            source_bars = (
                pd.concat([source_bars, downloaded], ignore_index=True, sort=False)
                .drop_duplicates("date", keep="last")
                .sort_values("date")
                .reset_index(drop=True)
            )
            bar_cache[source] = source_bars
            matched = source_bars[source_bars["date"].eq(item.date)]
        if matched.empty:
            if not required_visible:
                continue
            if allow_noncritical_daily_gaps and item.date not in {entry_date, exit_date}:
                missing_context_dates.append(pd.Timestamp(item.date).date().isoformat())
                continue
            raise RuntimeError(f"Missing daily context bar for {row.open_trade_id}: {source} {item.date.date()}.")
        bar = matched.iloc[0].to_dict()
        bar["source_vt_symbol"] = source
        bar["context_fallback"] = int(source != str(row.vt_symbol))
        bar["display"] = int(item.date in daily_display_dates)
        bar["weekly_display"] = int(item.date in weekly_display_dates)
        bar["monthly_display"] = int(monthly_display)
        bar["trading_day_index"] = int(item.trading_day_index)
        output.append(bar)
    daily = pd.DataFrame(output).sort_values("date").reset_index(drop=True)
    daily.attrs["missing_context_dates"] = missing_context_dates
    _date_index(daily, entry_date, exact=True)
    _date_index(daily, exit_date, exact=True)
    intraday_dates = _window_dates(calendar, entry_date, exit_date, INTRADAY_PRE, INTRADAY_POST)
    return daily, intraday_dates


def _to_tq_symbol(vt_symbol: str) -> str:
    symbol, exchange = str(vt_symbol).split(".", 1)
    return f"{exchange}.{symbol}"


def _normalize_tq_datetime(value: Any) -> pd.Timestamp:
    timestamp = pd.to_datetime(value, unit="ns", errors="coerce", utc=True)
    if pd.isna(timestamp):
        return pd.NaT
    return timestamp.tz_convert(CHINA_TZ).tz_localize(None)


def _fetch_15m(vt_symbol: str, start: pd.Timestamp, end: pd.Timestamp) -> tuple[pd.DataFrame, FetchStatus]:
    username = str(SETTINGS.get("datafeed.username", ""))
    password = str(SETTINGS.get("datafeed.password", ""))
    if not username or not password:
        raise RuntimeError("TqSdk credentials are missing in vn.py SETTINGS.")
    tq_symbol = _to_tq_symbol(vt_symbol)
    replay_start = (start - pd.Timedelta(days=3)).to_pydatetime()
    # Keep enough future time for the final requested bar to become the
    # completed previous row even across Golden Week / Spring Festival.
    replay_end = (end + pd.Timedelta(days=14, hours=23, minutes=59)).to_pydatetime()
    api: TqApi | None = None
    rows: list[dict[str, Any]] = []
    seen: set[int] = set()
    status = "unknown"
    message = ""
    started = time.time()
    try:
        api = TqApi(
            TqSim(),
            backtest=TqBacktest(start_dt=replay_start, end_dt=replay_end),
            auth=TqAuth(username, password),
        )
        serial = api.get_kline_serial(tq_symbol, duration_seconds=15 * 60, data_length=500)
        while True:
            api.wait_update()
            if not api.is_changing(serial.iloc[-1], "datetime"):
                continue
            # The last row is the newly forming bar.  Only the previous row is
            # complete and carries authoritative OHLC/volume.
            raw = serial.iloc[-2].to_dict()
            bar_id = int(raw.get("id", -1))
            if bar_id in seen:
                continue
            seen.add(bar_id)
            bar_datetime = _normalize_tq_datetime(raw.get("datetime"))
            if pd.isna(bar_datetime):
                continue
            rows.append(
                {
                    "vt_symbol": vt_symbol,
                    "tq_symbol": tq_symbol,
                    "bar_datetime": bar_datetime,
                    "bar_id": bar_id,
                    "open": float(raw.get("open", np.nan)),
                    "high": float(raw.get("high", np.nan)),
                    "low": float(raw.get("low", np.nan)),
                    "close": float(raw.get("close", np.nan)),
                    "volume": float(raw.get("volume", np.nan)),
                    "open_oi": float(raw.get("open_oi", np.nan)),
                    "close_oi": float(raw.get("close_oi", np.nan)),
                }
            )
    except BacktestFinished:
        status = "extracted"
    except Exception as exc:
        status = "failed"
        message = repr(exc)
    finally:
        if api is not None:
            api.close()
    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame = frame.dropna(subset=["bar_datetime", "open", "high", "low", "close"])
        frame = frame.drop_duplicates(["vt_symbol", "bar_datetime"]).sort_values("bar_datetime").reset_index(drop=True)
    if status == "unknown":
        status = "extracted" if len(frame) else "failed"
    fetch_status = FetchStatus(
        vt_symbol=vt_symbol,
        tq_symbol=tq_symbol,
        start=start.date().isoformat(),
        end=end.date().isoformat(),
        rows=int(len(frame)),
        elapsed_seconds=round(time.time() - started, 3),
        status=status,
        message=message,
    )
    if status != "extracted" or frame.empty:
        raise RuntimeError(f"15m fetch failed for {vt_symbol}: {asdict(fetch_status)}")
    return frame, fetch_status


def _fetch_daily_tq(vt_symbol: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    username = str(SETTINGS.get("datafeed.username", ""))
    password = str(SETTINGS.get("datafeed.password", ""))
    if not username or not password:
        raise RuntimeError("TqSdk credentials are missing in vn.py SETTINGS.")
    api: TqApi | None = None
    rows: list[dict[str, Any]] = []
    seen: set[int] = set()
    try:
        api = TqApi(
            TqSim(),
            backtest=TqBacktest(
                start_dt=(start - pd.Timedelta(days=20)).to_pydatetime(),
                end_dt=(end + pd.Timedelta(days=20)).to_pydatetime(),
            ),
            auth=TqAuth(username, password),
        )
        serial = api.get_kline_serial(_to_tq_symbol(vt_symbol), duration_seconds=24 * 60 * 60, data_length=200)
        while True:
            api.wait_update()
            if not api.is_changing(serial.iloc[-1], "datetime"):
                continue
            raw = serial.iloc[-2].to_dict()
            bar_id = int(raw.get("id", -1))
            if bar_id in seen:
                continue
            seen.add(bar_id)
            value = _normalize_tq_datetime(raw.get("datetime"))
            if pd.isna(value):
                continue
            rows.append(
                {
                    "date": value.normalize(),
                    "open": float(raw.get("open", np.nan)),
                    "high": float(raw.get("high", np.nan)),
                    "low": float(raw.get("low", np.nan)),
                    "close": float(raw.get("close", np.nan)),
                    "volume": float(raw.get("volume", np.nan)),
                    "close_oi": float(raw.get("close_oi", np.nan)),
                }
            )
    except BacktestFinished:
        pass
    finally:
        if api is not None:
            api.close()
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    return frame.dropna(subset=["date", "open", "high", "low", "close"]).drop_duplicates("date").reset_index(drop=True)


def _assign_trading_day(frame: pd.DataFrame, daily_dates: list[pd.Timestamp]) -> pd.DataFrame:
    result = frame.copy()
    dates = np.array(daily_dates, dtype="datetime64[ns]")

    def resolve(value: Any) -> pd.Timestamp | pd.NaT:
        timestamp = pd.Timestamp(value)
        calendar_date = timestamp.normalize()
        clock = timestamp.time()
        side = "right" if clock >= dt_time(20, 0) else "left"
        position = int(np.searchsorted(dates, np.datetime64(calendar_date), side=side))
        if position >= len(dates):
            return pd.NaT
        candidate = pd.Timestamp(dates[position]).normalize()
        if dt_time(3, 0) <= clock < dt_time(20, 0) and candidate != calendar_date:
            return pd.NaT
        return candidate

    result["trading_day"] = result["bar_datetime"].map(resolve)
    return result.dropna(subset=["trading_day"]).reset_index(drop=True)


def _daily_from_minute_frame(
    frame: pd.DataFrame,
    daily_dates: list[pd.Timestamp],
) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
    minute = frame.copy()
    minute["bar_datetime"] = pd.to_datetime(minute["bar_datetime"], errors="coerce")
    minute = minute.dropna(subset=["bar_datetime", "open", "high", "low", "close"])
    minute = minute.sort_values("bar_datetime").drop_duplicates("bar_datetime", keep="last")
    minute = _assign_trading_day(minute, daily_dates)
    if minute.empty:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
    minute["volume"] = pd.to_numeric(minute.get("volume", 0.0), errors="coerce").fillna(0.0)
    aggregations: dict[str, tuple[str, str]] = {
        "open": ("open", "first"),
        "high": ("high", "max"),
        "low": ("low", "min"),
        "close": ("close", "last"),
        "volume": ("volume", "sum"),
    }
    if "close_oi" in minute.columns:
        aggregations["close_oi"] = ("close_oi", "last")
    return (
        minute.groupby("trading_day", sort=True)
        .agg(**aggregations)
        .reset_index()
        .rename(columns={"trading_day": "date"})
    )


def _daily_from_existing_minute_files(
    vt_symbol: str,
    daily_dates: list[pd.Timestamp],
) -> pd.DataFrame:
    symbol, exchange = str(vt_symbol).split(".", 1)
    candidates = sorted(
        LOCAL_MINUTE_ROOT.glob(f"*/{exchange}/{symbol}_completed_minute_backtest.csv")
    )
    frames: list[pd.DataFrame] = []
    for path in candidates:
        try:
            frames.append(
                pd.read_csv(
                    path,
                    encoding="utf-8-sig",
                    usecols=["bar_datetime", "open", "high", "low", "close", "volume", "close_oi"],
                )
            )
        except (OSError, ValueError):
            continue
    if not frames:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
    return _daily_from_minute_frame(pd.concat(frames, ignore_index=True, sort=False), daily_dates)


def _weekly_from_daily(daily: pd.DataFrame) -> pd.DataFrame:
    data = daily.copy()
    data["week"] = data["date"].dt.to_period("W-FRI").astype(str)
    return (
        data.groupby("week", sort=False)
        .agg(
            date_start=("date", "min"),
            date_end=("date", "max"),
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            volume=("volume", "sum"),
        )
        .reset_index()
    )


def _monthly_from_daily(daily: pd.DataFrame) -> pd.DataFrame:
    data = daily.copy().sort_values("date").reset_index(drop=True)
    data["month"] = pd.to_datetime(data["date"], errors="coerce").dt.to_period("M").astype(str)
    return (
        data.groupby("month", sort=False)
        .agg(
            date_start=("date", "min"),
            date_end=("date", "max"),
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            volume=("volume", "sum"),
        )
        .reset_index()
    )


def _trading_day_bars_from_daily(
    daily: pd.DataFrame,
    *,
    period_days: int,
) -> pd.DataFrame:
    """Aggregate non-overlapping bars anchored to the product trading calendar."""
    if period_days <= 0:
        raise ValueError("period_days must be positive")
    data = daily.copy().sort_values("date").reset_index(drop=True)
    if "trading_day_index" not in data.columns:
        raise ValueError("daily bars require trading_day_index for fixed calendar buckets")
    data["bucket"] = pd.to_numeric(data["trading_day_index"], errors="raise").astype(int) // period_days
    result = (
        data.groupby("bucket", sort=True)
        .agg(
            date_start=("date", "min"),
            date_end=("date", "max"),
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            volume=("volume", "sum"),
            day_count=("date", "size"),
        )
        .reset_index(drop=True)
    )
    result["period_days"] = int(period_days)
    result["label"] = [
        (
            f"{pd.Timestamp(row.date_start).date().isoformat()}~"
            f"{pd.Timestamp(row.date_end).date().isoformat()} "
            f"{int(row.day_count)}/{period_days}日"
        )
        for row in result.itertuples(index=False)
    ]
    return result


def _monthly_window(
    monthly: pd.DataFrame,
    *,
    entry_date: pd.Timestamp,
    exit_date: pd.Timestamp,
) -> pd.DataFrame:
    start = pd.Timestamp(entry_date).to_period("M") - MONTHLY_PRE
    end = pd.Timestamp(exit_date).to_period("M") + MONTHLY_POST
    periods = pd.PeriodIndex(monthly["month"], freq="M")
    return monthly.loc[(periods >= start) & (periods <= end)].copy().reset_index(drop=True)


def _add_moving_averages(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    close = pd.to_numeric(result["close"], errors="coerce")
    for period in MA_PERIODS:
        result[f"ma{period}"] = close.rolling(period, min_periods=period).mean()
    return result


def _period_coordinates(
    context_dates: pd.Series | pd.DatetimeIndex,
    periods: pd.DataFrame,
) -> tuple[list[float], list[float]]:
    dates = pd.Series(pd.to_datetime(context_dates, errors="coerce")).dropna().reset_index(drop=True)
    positions = {pd.Timestamp(value).normalize(): index + 0.5 for index, value in enumerate(dates)}
    x_values: list[float] = []
    widths: list[float] = []
    for row in periods.itertuples(index=False):
        members = [
            positions[pd.Timestamp(value).normalize()]
            for value in dates[dates.between(pd.Timestamp(row.date_start), pd.Timestamp(row.date_end))]
        ]
        if not members:
            raise RuntimeError(f"Period {row.date_start}..{row.date_end} has no shared-axis trading days.")
        x_values.append(float(np.mean(members)))
        widths.append(float(len(members) * 0.78))
    return x_values, widths


def _records(
    winners: pd.DataFrame,
    daily_by_episode: dict[str, pd.DataFrame],
    intraday_dates_by_episode: dict[str, list[pd.Timestamp]],
    bars_15m: pd.DataFrame,
) -> tuple[list[dict[str, Any]], pd.DataFrame]:
    minute_by_symbol = {key: group.copy() for key, group in bars_15m.groupby("vt_symbol", sort=False)}
    records: list[dict[str, Any]] = []
    manifest_rows: list[dict[str, Any]] = []
    for row in winners.itertuples(index=False):
        vt_symbol = str(row.vt_symbol)
        episode_id = str(row.open_trade_id)
        draw_intraday = int(getattr(row, "draw_intraday", 1))
        is_tail = int(getattr(row, "is_tail", 1))
        missing_context_dates = list(
            daily_by_episode[episode_id].attrs.get("missing_context_dates", [])
        )
        daily_full = daily_by_episode[episode_id].copy().reset_index(drop=True)
        daily = daily_full[daily_full["display"].eq(1)].copy().reset_index(drop=True)
        entry_date = pd.Timestamp(row.entry_date).normalize()
        exit_date = pd.Timestamp(row.exit_date).normalize()
        entry_index = _date_index(daily, entry_date, exact=True)
        exit_index = _date_index(daily, exit_date, exact=True)
        day_positions = {date: index for index, date in enumerate(daily["date"])}
        daily["x"] = np.arange(len(daily), dtype=float) + 0.5
        intraday_dates = intraday_dates_by_episode[episode_id]
        minute_parts: list[pd.DataFrame] = []
        if draw_intraday:
            for trading_day in intraday_dates:
                daily_row = daily[daily["date"].eq(trading_day)]
                if daily_row.empty:
                    continue
                source = str(daily_row.iloc[0]["source_vt_symbol"])
                source_minute = minute_by_symbol.get(source, pd.DataFrame())
                if not source_minute.empty:
                    minute_parts.append(source_minute[source_minute["trading_day"].eq(trading_day)].copy())
        minute = (
            pd.concat(minute_parts, ignore_index=True, sort=False)
            if minute_parts
            else pd.DataFrame(
                columns=[
                    "vt_symbol",
                    "bar_datetime",
                    "trading_day",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                ]
            )
        )
        minute = minute.sort_values(["trading_day", "bar_datetime"]).reset_index(drop=True)
        # Within the shared 15m window, derive the daily candle from the very
        # same intraday source.  This avoids provider-specific volume scaling
        # and rollover-day OHLC disagreements between unrelated feeds.
        aggregated_days: list[str] = []
        for trading_day, group in minute.groupby("trading_day", sort=False):
            target = daily_full.index[daily_full["date"].eq(trading_day)]
            if len(target) != 1:
                continue
            index = int(target[0])
            daily_full.loc[index, ["open", "high", "low", "close", "volume"]] = [
                group["open"].iloc[0],
                group["high"].max(),
                group["low"].min(),
                group["close"].iloc[-1],
                group["volume"].sum(),
            ]
            aggregated_days.append(pd.Timestamp(trading_day).date().isoformat())
        daily_full = _add_moving_averages(daily_full)
        weekly_full = _add_moving_averages(_weekly_from_daily(daily_full))
        monthly_full = _add_moving_averages(_monthly_from_daily(daily_full))
        day10 = _add_moving_averages(
            _trading_day_bars_from_daily(daily_full, period_days=10)
        )
        day30 = _add_moving_averages(
            _trading_day_bars_from_daily(daily_full, period_days=30)
        )
        monthly = _monthly_window(
            monthly_full,
            entry_date=entry_date,
            exit_date=exit_date,
        )
        context_day_positions = {
            pd.Timestamp(value).normalize(): index + 0.5
            for index, value in enumerate(daily_full["date"])
        }
        monthly["x"], monthly["width"] = _period_coordinates(daily_full["date"], monthly)
        day10["x"], day10["width"] = _period_coordinates(daily_full["date"], day10)
        day30["x"], day30["width"] = _period_coordinates(daily_full["date"], day30)
        monthly_context = daily_full[
            daily_full["date"].between(monthly["date_start"].iloc[0], monthly["date_end"].iloc[-1])
        ]
        chart_x_start = float(context_day_positions[monthly_context["date"].iloc[0]] - 0.5)
        chart_x_end = float(context_day_positions[monthly_context["date"].iloc[-1]] + 0.5)
        weekly_display_daily = daily_full[daily_full["weekly_display"].eq(1)]
        weekly_display_start_date = weekly_display_daily.iloc[0]["date"]
        weekly_display_end_date = weekly_display_daily.iloc[-1]["date"]
        daily = daily_full[daily_full["display"].eq(1)].copy().reset_index(drop=True)
        weekly = weekly_full[
            weekly_full["date_start"].ge(weekly_display_start_date)
            & weekly_full["date_end"].le(weekly_display_end_date)
        ].copy().reset_index(drop=True)
        daily["x"] = [context_day_positions[pd.Timestamp(value).normalize()] for value in daily["date"]]
        weekly["x"], weekly["width"] = _period_coordinates(daily_full["date"], weekly)
        # The 300-day daily window can start before the ten-month monthly window.
        # Keep one shared axis, but include every visible daily/weekly boundary.
        chart_x_start = min(
            chart_x_start, float(daily["x"].iloc[0] - 0.5),
            float(context_day_positions[weekly_display_start_date] - 0.5),
        )
        chart_x_end = max(
            chart_x_end, float(daily["x"].iloc[-1] + 0.5),
            float(context_day_positions[weekly_display_end_date] + 0.5),
        )
        minute["x"] = np.nan
        for trading_day, indices in minute.groupby("trading_day", sort=False).groups.items():
            normalized_day = pd.Timestamp(trading_day).normalize()
            if normalized_day not in context_day_positions:
                continue
            index_list = list(indices)
            count = len(index_list)
            minute.loc[index_list, "x"] = (
                context_day_positions[normalized_day] - 0.5 + (np.arange(count) + 0.5) / count
            )
        minute = minute.dropna(subset=["x"]).reset_index(drop=True)
        minute = _add_moving_averages(minute)
        covered_dates = set(pd.to_datetime(minute["trading_day"]).dt.normalize())
        missing_dates = (
            [value.date().isoformat() for value in intraday_dates if value not in covered_dates]
            if draw_intraday
            else []
        )
        entry_x = float(context_day_positions[entry_date])
        exit_x = float(context_day_positions[exit_date])
        fallback_days = [
            value.date().isoformat() for value in daily.loc[daily["context_fallback"].eq(1), "date"]
        ]
        entry_source = str(daily.loc[daily["date"].eq(entry_date), "source_vt_symbol"].iloc[0])
        exit_source = str(daily.loc[daily["date"].eq(exit_date), "source_vt_symbol"].iloc[0])
        source_switch_x = [
            float(daily.loc[index, "x"])
            for index in range(1, len(daily))
            if daily.loc[index, "source_vt_symbol"] != daily.loc[index - 1, "source_vt_symbol"]
        ]

        def series(frame: pd.DataFrame, column: str) -> list[Any]:
            return [_json_safe(item) for item in frame[column].tolist()]

        def period_payload(frame: pd.DataFrame, label_column: str = "label") -> dict[str, Any]:
            return {
                "x": series(frame, "x"),
                "label": frame[label_column].tolist(),
                "open": series(frame, "open"),
                "high": series(frame, "high"),
                "low": series(frame, "low"),
                "close": series(frame, "close"),
                "volume": series(frame, "volume"),
                "width": series(frame, "width"),
                **{f"ma{period}": series(frame, f"ma{period}") for period in MA_PERIODS},
            }

        record = {
            "meta": {
                "result_rank": int(row.result_rank),
                "result_type": str(row.result_type),
                "is_tail": is_tail,
                "draw_intraday": draw_intraday,
                "lot_id": str(row.lot_id),
                "lot_count": int(row.lot_count),
                "open_trade_id": str(row.open_trade_id),
                "close_trade_id": str(row.close_trade_id),
                "vt_symbol": vt_symbol,
                "product": str(row.product),
                "direction": str(row.direction),
                "entry_date": entry_date.date().isoformat(),
                "exit_date": exit_date.date().isoformat(),
                "entry_price": float(row.entry_price),
                "exit_price": float(row.exit_price),
                "weighted_exit_price": float(row.weighted_exit_price),
                "price_change_pct": float(row.price_change_pct),
                "price_change_label": str(row.price_change_label),
                "volume": float(row.volume),
                "realized_pnl": float(row.realized_pnl),
                "r_multiple": float(row.r_multiple),
                "selection_basis": str(row.selection_basis),
                "holding_calendar_days": int(row.holding_calendar_days),
                "exit_reason": str(row.exit_reason),
                "signal": str(row.signal),
                "profit_r_threshold": float(row.profit_r_threshold),
                "loss_r_threshold": float(row.loss_r_threshold),
                "entry_x": entry_x,
                "exit_x": exit_x,
                "chart_x_start": chart_x_start,
                "chart_x_end": chart_x_end,
                "daily_start": daily["date"].iloc[0].date().isoformat(),
                "daily_end": daily["date"].iloc[-1].date().isoformat(),
                "monthly_start": str(monthly["month"].iloc[0]),
                "monthly_end": str(monthly["month"].iloc[-1]),
                "intraday_start": intraday_dates[0].date().isoformat(),
                "intraday_end": intraday_dates[-1].date().isoformat(),
                "missing_15m_dates": missing_dates,
                "missing_context_dates": missing_context_dates,
                "context_fallback_dates": fallback_days,
                "source_switch_x": source_switch_x,
                "entry_source": entry_source,
                "exit_source": exit_source,
                "entry_marker_price": float(row.entry_price) if entry_source == vt_symbol else None,
                "exit_marker_price": float(row.exit_price) if exit_source == vt_symbol else None,
                "daily_from_15m_dates": aggregated_days,
            },
            "monthly": {
                **period_payload(monthly, "month"),
            },
            "day30": period_payload(day30),
            "day10": period_payload(day10),
            "daily": {
                "x": series(daily, "x"),
                "date": [value.date().isoformat() for value in daily["date"]],
                "open": series(daily, "open"),
                "high": series(daily, "high"),
                "low": series(daily, "low"),
                "close": series(daily, "close"),
                "volume": series(daily, "volume"),
                "source": daily["source_vt_symbol"].tolist(),
                **{f"ma{period}": series(daily, f"ma{period}") for period in MA_PERIODS},
            },
            "weekly": {
                "x": series(weekly, "x"),
                "label": weekly["week"].tolist(),
                "open": series(weekly, "open"),
                "high": series(weekly, "high"),
                "low": series(weekly, "low"),
                "close": series(weekly, "close"),
                "volume": series(weekly, "volume"),
                "width": series(weekly, "width"),
                **{f"ma{period}": series(weekly, f"ma{period}") for period in MA_PERIODS},
            },
            "intraday": {
                "x": series(minute, "x"),
                "datetime": [pd.Timestamp(value).strftime("%Y-%m-%d %H:%M") for value in minute["bar_datetime"]],
                "trading_day": [pd.Timestamp(value).date().isoformat() for value in minute["trading_day"]],
                "open": series(minute, "open"),
                "high": series(minute, "high"),
                "low": series(minute, "low"),
                "close": series(minute, "close"),
                "volume": series(minute, "volume"),
                "source": minute["vt_symbol"].tolist(),
                **{f"ma{period}": series(minute, f"ma{period}") for period in MA_PERIODS},
            },
        }
        records.append(record)
        manifest_rows.append(
            {
                **record["meta"],
                "day30_bars": len(day30),
                "day10_bars": len(day10),
                "monthly_bars": len(monthly),
                "daily_bars": len(daily),
                "weekly_bars": len(weekly),
                "bars_15m": len(minute),
                "intraday_expected_days": len(intraday_dates),
                "intraday_covered_days": len(covered_dates.intersection(intraday_dates)),
                "intraday_missing_days": len(missing_dates),
                "context_fallback_days": len(fallback_days),
            }
        )
    return records, pd.DataFrame(manifest_rows)


def _legacy_html(records: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    records_json = json.dumps(_json_safe(records), ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    summary_json = json.dumps(_json_safe(summary), ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    plotly_js = get_plotlyjs()
    is_all_scope = str(summary.get("episode_scope", "tail")) == "all"
    title = (
        "C9/15万全量交易：月K × 周K × 日K × 15分钟K（尾部）逐笔复盘"
        if is_all_scope
        else "C9/15万盈利/亏损尾部：月K × 周K × 日K × 15分钟K逐笔复盘"
    )
    coverage_note = (
        "全部交易均展示月K、周K和日K；原盈利/亏损尾部73笔继续展示15分钟K，其余交易不读取也不绘制分钟线。"
        if is_all_scope
        else "当前仅展示原盈利/亏损尾部交易，每笔均展示月K、周K、日K和15分钟K。"
    )
    footer_scope = (
        "共402笔完整开平仓episode，部分平仓按一次开仓聚合到最终平仓；"
        if is_all_scope
        else "盈利侧=正R前20%，亏损侧=负R最差20%，部分平仓按一次开仓聚合到最终平仓；"
    )
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><script>{plotly_js}</script>
<style>
:root{{--bg:#f4f6f8;--panel:#fff;--line:#d9dee7;--text:#17202a;--muted:#667085;--blue:#2563eb;--purple:#9333ea}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
.page{{max-width:1760px;margin:0 auto;padding:16px}} h1{{font-size:24px;margin:0 0 10px}}
.note{{font-size:13px;color:var(--muted);margin-bottom:12px}} .toolbar{{display:grid;grid-template-columns:160px 180px 150px 170px minmax(300px,1fr) auto auto;gap:8px;margin-bottom:10px}}
select,button{{height:38px;border:1px solid var(--line);border-radius:7px;background:#fff;padding:0 10px;font-size:13px}} button{{cursor:pointer}}
.metrics{{display:grid;grid-template-columns:repeat(8,minmax(120px,1fr));gap:8px;margin-bottom:10px}} .metric{{background:#fff;border:1px solid var(--line);border-radius:7px;padding:8px 10px}}
.metric .k{{font-size:11px;color:var(--muted)}} .metric .v{{font-size:16px;font-weight:700;margin-top:3px}}
.panel{{background:#fff;border:1px solid var(--line);border-radius:8px}} #chart{{height:1540px;width:100%}}
.footer{{font-size:12px;color:var(--muted);padding:10px 2px}} .warn{{color:#b42318;font-weight:600}}
@media(max-width:1000px){{.toolbar{{grid-template-columns:1fr}}.metrics{{grid-template-columns:repeat(2,1fr)}}#chart{{height:1350px}}}}
</style></head><body><div class="page"><h1>{html.escape(title)}</h1>
<div class="note">{coverage_note}日K严格展示开仓前300个交易日至最终平仓后50个交易日的可用历史；月K展示开仓前10个月至最终平仓后10个月的可用历史；各可见周期共享同一条完整上下文交易日坐标，框选、缩放和平移会同步且同一日期垂直对齐。各周期叠加 MA5/10/20/40，并使用图窗外历史预热，历史不足完整周期时均线留空，不用短样本冒充。蓝线=开仓日，紫线=最终平仓日，淡黄色=持仓区间；灰虚线表示精确合约缺历史数据后切到当日主力上下文。</div>
<div class="toolbar"><select id="result"><option value="all">全部交易</option><option value="profit">全部盈利</option><option value="loss">全部亏损</option><option value="flat">持平交易</option><option value="profit_tail">盈利尾部</option><option value="loss_tail">亏损尾部</option></select><select id="sort"><option value="extreme">R绝对值从大到小</option><option value="near">R绝对值从小到大</option></select><select id="year"></select><select id="product"></select><select id="trade"></select><button id="prev">上一笔</button><button id="next">下一笔</button></div>
<div id="metrics" class="metrics"></div><div class="panel"><div id="chart"></div></div>
<div class="footer">数据：当前正式 {html.escape(OFFICIAL_LIVE_ALIAS)}（{html.escape(OFFICIAL_LIVE_VERSION)}）；{footer_scope}本图用于对照复盘，不是交易规则。</div>
</div><script>
const records={records_json}; const summary={summary_json}; let filtered=[]; let active=0;
const resultEl=document.getElementById('result'), sortEl=document.getElementById('sort'), yearEl=document.getElementById('year'), productEl=document.getElementById('product'), tradeEl=document.getElementById('trade');
const fmt=(v,d=2)=>Number(v).toLocaleString('zh-CN',{{minimumFractionDigits:d,maximumFractionDigits:d}});
const uniq=a=>[...new Set(a)].sort();
function options(el,values,label){{el.innerHTML=`<option value="">全部${{label}}</option>`+values.map(v=>`<option value="${{v}}">${{v}}</option>`).join('')}}
options(yearEl,uniq(records.map(r=>r.meta.entry_date.slice(0,4))),'年份'); options(productEl,uniq(records.map(r=>r.meta.product)),'品种');
function apply(){{const result=resultEl.value,y=yearEl.value,p=productEl.value,extreme=sortEl.value==='extreme';const resultOk=r=>result==='all'||r.meta.result_type===result||(result==='profit_tail'&&r.meta.result_type==='profit'&&r.meta.is_tail===1)||(result==='loss_tail'&&r.meta.result_type==='loss'&&r.meta.is_tail===1);filtered=records.filter(r=>resultOk(r)&&(!y||r.meta.entry_date.startsWith(y))&&(!p||r.meta.product===p));filtered.sort((a,b)=>{{const ar=a.meta.r_multiple===null?null:Math.abs(Number(a.meta.r_multiple)),br=b.meta.r_multiple===null?null:Math.abs(Number(b.meta.r_multiple));if(ar===null&&br===null)return Math.abs(b.meta.realized_pnl)-Math.abs(a.meta.realized_pnl);if(ar===null)return 1;if(br===null)return -1;return extreme?br-ar:ar-br}});active=0;refreshSelect();render()}}
function rfmt(v){{return v===null?'N/A':fmt(v)}}
function refreshSelect(){{tradeEl.innerHTML=filtered.map((r,i)=>`<option value="${{i}}">#${{i+1}} ${{r.meta.vt_symbol}} ${{r.meta.direction}} R=${{rfmt(r.meta.r_multiple)}} ${{r.meta.entry_date}}→${{r.meta.exit_date}}</option>`).join('');tradeEl.value=String(active)}}
function colors(o,c){{return o.map((v,i)=>c[i]>=v?'#d92d20':'#039855')}}
function render(){{if(!filtered.length){{Plotly.purge('chart');document.getElementById('metrics').innerHTML='<div class="warn">没有符合筛选条件的交易</div>';return}}
 const r=filtered[active],m=r.meta,mo=r.monthly,d=r.daily,w=r.weekly,q=r.intraday; tradeEl.value=String(active);
 const hasIntraday=m.draw_intraday===1;
 document.getElementById('chart').style.height=hasIntraday?'1540px':'1120px';
 const missing=hasIntraday?(m.missing_15m_dates.length?`<span class="warn">${{m.missing_15m_dates.length}}日缺15m</span>`:'完整'):'尾部外不绘制';
 const contextGap=m.missing_context_dates.length?`<span class="warn">${{m.missing_context_dates.length}}日背景缺口</span>`:'日背景完整';
 const sourceParts=[];if(m.context_fallback_dates.length)sourceParts.push(`${{m.context_fallback_dates.length}}日主力代理`);if(m.missing_context_dates.length)sourceParts.push(`${{m.missing_context_dates.length}}日背景缺口`);const source=sourceParts.length?sourceParts.join('；'):'全程精确合约';
 const resultLabel=m.result_type==='profit'?'盈利':(m.result_type==='loss'?'亏损':'持平');
 const metric=[['R排序',`#${{active+1}}`],['结果',resultLabel],['合约',m.vt_symbol],['方向',m.direction],['净利润',fmt(m.realized_pnl,0)],['R倍数',rfmt(m.r_multiple)],['平仓lot',m.lot_count],['分钟/背景',`${{missing}}<br>${{contextGap}}`]];
 document.getElementById('metrics').innerHTML=metric.map(([k,v])=>`<div class="metric"><div class="k">${{k}}</div><div class="v">${{v}}</div></div>`).join('');
 const traces=[
  {{type:'candlestick',x:mo.x,open:mo.open,high:mo.high,low:mo.low,close:mo.close,name:'月K',xaxis:'x2',yaxis:'y',showlegend:false,increasing:{{line:{{color:'#d92d20'}}}},decreasing:{{line:{{color:'#039855'}}}}}},
  {{type:'scatter',mode:'lines',x:mo.x,y:mo.ma5,xaxis:'x2',yaxis:'y',name:'月MA5',showlegend:false,line:{{color:'#f59e0b',width:1.4}}}},
  {{type:'scatter',mode:'lines',x:mo.x,y:mo.ma10,xaxis:'x2',yaxis:'y',name:'月MA10',showlegend:false,line:{{color:'#2563eb',width:1.4}}}},
  {{type:'scatter',mode:'lines',x:mo.x,y:mo.ma20,xaxis:'x2',yaxis:'y',name:'月MA20',showlegend:false,line:{{color:'#9333ea',width:1.4}}}},
  {{type:'scatter',mode:'lines',x:mo.x,y:mo.ma40,xaxis:'x2',yaxis:'y',name:'月MA40',showlegend:false,line:{{color:'#111827',width:1.5}}}},
  {{type:'bar',x:mo.x,y:mo.volume,width:mo.width,xaxis:'x2',yaxis:'y2',marker:{{color:colors(mo.open,mo.close),opacity:.55}},name:'月成交量',showlegend:false,hovertext:mo.label,hovertemplate:'%{{hovertext}}<br>Vol=%{{y:,.0f}}<extra></extra>'}},
  {{type:'candlestick',x:w.x,open:w.open,high:w.high,low:w.low,close:w.close,name:'周K',yaxis:'y3',showlegend:false,increasing:{{line:{{color:'#d92d20'}}}},decreasing:{{line:{{color:'#039855'}}}}}},
  {{type:'scatter',mode:'lines',x:w.x,y:w.ma5,yaxis:'y3',name:'周MA5',showlegend:false,line:{{color:'#f59e0b',width:1.4}}}},
  {{type:'scatter',mode:'lines',x:w.x,y:w.ma10,yaxis:'y3',name:'周MA10',showlegend:false,line:{{color:'#2563eb',width:1.4}}}},
  {{type:'scatter',mode:'lines',x:w.x,y:w.ma20,yaxis:'y3',name:'周MA20',showlegend:false,line:{{color:'#9333ea',width:1.4}}}},
  {{type:'scatter',mode:'lines',x:w.x,y:w.ma40,yaxis:'y3',name:'周MA40',showlegend:false,line:{{color:'#111827',width:1.5}}}},
  {{type:'bar',x:w.x,y:w.volume,width:w.width,marker:{{color:colors(w.open,w.close),opacity:.55}},name:'周成交量',yaxis:'y4',showlegend:false,hovertext:w.label,hovertemplate:'%{{hovertext}}<br>Vol=%{{y:,.0f}}<extra></extra>'}},
  {{type:'candlestick',x:d.x,open:d.open,high:d.high,low:d.low,close:d.close,name:'日K',yaxis:'y5',showlegend:false,customdata:d.source,hovertemplate:'%{{customdata}}<br>O=%{{open}} H=%{{high}}<br>L=%{{low}} C=%{{close}}<extra></extra>',increasing:{{line:{{color:'#d92d20'}}}},decreasing:{{line:{{color:'#039855'}}}}}},
  {{type:'scatter',mode:'lines',x:d.x,y:d.ma5,yaxis:'y5',name:'MA5',legendgroup:'ma',line:{{color:'#f59e0b',width:1.4}}}},
  {{type:'scatter',mode:'lines',x:d.x,y:d.ma10,yaxis:'y5',name:'MA10',legendgroup:'ma',line:{{color:'#2563eb',width:1.4}}}},
  {{type:'scatter',mode:'lines',x:d.x,y:d.ma20,yaxis:'y5',name:'MA20',legendgroup:'ma',line:{{color:'#9333ea',width:1.4}}}},
  {{type:'scatter',mode:'lines',x:d.x,y:d.ma40,yaxis:'y5',name:'MA40',legendgroup:'ma',line:{{color:'#111827',width:1.5}}}},
  {{type:'bar',x:d.x,y:d.volume,width:.72,marker:{{color:colors(d.open,d.close),opacity:.55}},name:'日成交量',yaxis:'y6',showlegend:false,customdata:d.date,hovertemplate:'%{{customdata}}<br>Vol=%{{y:,.0f}}<extra></extra>'}},
  {{type:'candlestick',x:q.x,open:q.open,high:q.high,low:q.low,close:q.close,name:'15分钟K',yaxis:'y7',showlegend:false,customdata:q.datetime.map((v,i)=>[v,q.source[i]]),hovertemplate:'%{{customdata[0]}} %{{customdata[1]}}<br>O=%{{open}} H=%{{high}}<br>L=%{{low}} C=%{{close}}<extra></extra>',increasing:{{line:{{color:'#d92d20'}}}},decreasing:{{line:{{color:'#039855'}}}}}},
  {{type:'scatter',mode:'lines',x:q.x,y:q.ma5,yaxis:'y7',name:'15m MA5',showlegend:false,line:{{color:'#f59e0b',width:1.2}}}},
  {{type:'scatter',mode:'lines',x:q.x,y:q.ma10,yaxis:'y7',name:'15m MA10',showlegend:false,line:{{color:'#2563eb',width:1.2}}}},
  {{type:'scatter',mode:'lines',x:q.x,y:q.ma20,yaxis:'y7',name:'15m MA20',showlegend:false,line:{{color:'#9333ea',width:1.2}}}},
  {{type:'scatter',mode:'lines',x:q.x,y:q.ma40,yaxis:'y7',name:'15m MA40',showlegend:false,line:{{color:'#111827',width:1.3}}}},
  {{type:'bar',x:q.x,y:q.volume,marker:{{color:colors(q.open,q.close),opacity:.6}},name:'15分钟成交量',yaxis:'y8',showlegend:false,customdata:q.datetime,hovertemplate:'%{{customdata}}<br>Vol=%{{y:,.0f}}<extra></extra>'}},
  {{type:'scatter',mode:'markers',x:[m.entry_x,m.exit_x],y:[m.entry_marker_price,m.exit_marker_price],yaxis:'y5',name:'同源成交价格（日）',marker:{{symbol:['triangle-up','triangle-down'],size:12,color:['#2563eb','#9333ea']}}}}
 ].filter(trace=>hasIntraday||!['y7','y8'].includes(trace.yaxis));
 const tickStep=Math.max(1,Math.ceil(d.date.length/18)),tickvals=d.x.filter((_,i)=>i%tickStep===0),ticktext=d.date.filter((_,i)=>i%tickStep===0);
 const monthTickStep=Math.max(1,Math.ceil(mo.label.length/16)),monthTickvals=mo.x.filter((_,i)=>i%monthTickStep===0),monthTicktext=mo.label.filter((_,i)=>i%monthTickStep===0);
 const lowerPanelTop=hasIntraday?.78:.73;
 const switches=m.source_switch_x.map(x=>({{type:'line',xref:'x',yref:'paper',x0:x,x1:x,y0:0,y1:lowerPanelTop,line:{{color:'#98a2b3',width:1,dash:'dash'}}}}));
 const layout={{title:{{text:`${{resultLabel}} #${{active+1}} ${{m.vt_symbol}} ${{m.direction}}｜${{m.entry_date}} → ${{m.exit_date}}｜R=${{rfmt(m.r_multiple)}}｜PnL=${{fmt(m.realized_pnl,0)}}｜${{m.selection_basis}}｜${{source}}`,x:.01}},
  margin:{{l:72,r:28,t:74,b:76}},paper_bgcolor:'#fff',plot_bgcolor:'#fff',hovermode:'x unified',showlegend:true,legend:{{orientation:'h',y:1.065,x:1,xanchor:'right'}},
  xaxis:{{range:[m.chart_x_start,m.chart_x_end],tickvals,ticktext,tickangle:-35,showgrid:false,rangeslider:{{visible:false}},title:hasIntraday?'共享交易日坐标（四周期同步缩放）':'共享交易日坐标（月/周/日同步缩放；尾部外不绘制15分钟）'}},
  xaxis2:{{matches:'x',tickvals:monthTickvals,ticktext:monthTicktext,tickangle:-35,showgrid:false,rangeslider:{{visible:false}},side:'top',anchor:'y'}},
  yaxis:{{domain:hasIntraday?[.86,1]:[.82,1],title:'月K',showgrid:true,gridcolor:'#eef1f4',anchor:'x2'}},yaxis2:{{domain:hasIntraday?[.80,.84]:[.75,.80],title:'月量',showgrid:true,gridcolor:'#f2f4f7',anchor:'x2'}},
  yaxis3:{{domain:hasIntraday?[.64,.78]:[.52,.73],title:'周K',showgrid:true,gridcolor:'#eef1f4'}},yaxis4:{{domain:hasIntraday?[.58,.62]:[.45,.50],title:'周量',showgrid:true,gridcolor:'#f2f4f7'}},
  yaxis5:{{domain:hasIntraday?[.34,.56]:[.08,.43],title:'日K',showgrid:true,gridcolor:'#eef1f4'}},yaxis6:{{domain:hasIntraday?[.28,.32]:[0,.06],title:'日量',showgrid:true,gridcolor:'#f2f4f7'}},
  yaxis7:{{domain:[.07,.26],visible:hasIntraday,title:'15分钟K',showgrid:true,gridcolor:'#eef1f4'}},yaxis8:{{domain:[0,.05],visible:hasIntraday,title:'15m量',showgrid:true,gridcolor:'#f2f4f7'}},
  shapes:[{{type:'rect',xref:'x',yref:'paper',x0:m.entry_x,x1:m.exit_x,y0:0,y1:lowerPanelTop,fillcolor:'#fef3c7',opacity:.17,line:{{width:0}}}},{{type:'line',xref:'x',yref:'paper',x0:m.entry_x,x1:m.entry_x,y0:0,y1:lowerPanelTop,line:{{color:'#2563eb',width:1.5,dash:'dot'}}}},{{type:'line',xref:'x',yref:'paper',x0:m.exit_x,x1:m.exit_x,y0:0,y1:lowerPanelTop,line:{{color:'#9333ea',width:1.5,dash:'dot'}}}},...switches],
  annotations:[{{xref:'x',yref:'paper',x:m.entry_x,y:lowerPanelTop,text:'开仓',showarrow:false,font:{{color:'#2563eb'}}}},{{xref:'x',yref:'paper',x:m.exit_x,y:lowerPanelTop,text:'平仓',showarrow:false,font:{{color:'#9333ea'}}}}]}};
 Plotly.react('chart',traces,layout,{{responsive:true,displaylogo:false,scrollZoom:true}})
}}
resultEl.onchange=apply;sortEl.onchange=apply;yearEl.onchange=apply;productEl.onchange=apply;tradeEl.onchange=()=>{{active=Number(tradeEl.value);render()}};
document.getElementById('prev').onclick=()=>{{if(filtered.length){{active=(active-1+filtered.length)%filtered.length;render()}}}};
document.getElementById('next').onclick=()=>{{if(filtered.length){{active=(active+1)%filtered.length;render()}}}};
apply();
</script></body></html>"""


def _html(records: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    records_json = json.dumps(_json_safe(records), ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    summary_json = json.dumps(_json_safe(summary), ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    is_all_scope = str(summary.get("episode_scope", "tail")) == "all"
    title = str(summary.get("page_title") or (
        "C9/15万全量交易：30日K / 10日K / 月K × 周K × 日K × 15分钟K（尾部）逐笔复盘"
        if is_all_scope
        else "C9/15万盈利/亏损尾部：30日K / 10日K / 月K × 周K × 日K × 15分钟K逐笔复盘"
    ))
    coverage_note = str(summary.get("coverage_note") or (
        "全部交易均可选择30日K、10日K、月K、周K和日K；原盈利/亏损尾部73笔另可选择15分钟K，其余交易不读取也不绘制分钟线。"
        if is_all_scope
        else "当前仅展示原盈利/亏损尾部交易，每笔均可选择六种周期。"
    ))
    footer_scope = str(summary.get("footer_scope") or (
        "共402笔完整开平仓episode，部分平仓按一次开仓聚合到最终平仓；"
        if is_all_scope
        else "盈利侧=正R前20%，亏损侧=负R最差20%，部分平仓按一次开仓聚合到最终平仓；"
    ))
    source_label = str(summary.get("source_label") or f"当前正式 {OFFICIAL_LIVE_ALIAS}")
    source_version = str(summary.get("source_version") or OFFICIAL_LIVE_VERSION)
    source_warning = str(summary.get("source_warning") or "")
    rank_basis = str(summary.get("rank_basis") or "r_multiple")
    sort_extreme_label = "净利润绝对值从大到小" if rank_basis == "realized_pnl" else "R绝对值从大到小"
    sort_near_label = "净利润绝对值从小到大" if rank_basis == "realized_pnl" else "R绝对值从小到大"
    styles = """
:root{--bg:#f4f6f8;--panel:#fff;--line:#d9dee7;--text:#17202a;--muted:#667085;--blue:#2563eb;--purple:#9333ea}
*{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
.page{max-width:1760px;margin:0 auto;padding:16px} h1{font-size:24px;margin:0 0 10px}
.note{font-size:13px;color:var(--muted);margin-bottom:12px}.toolbar{display:grid;grid-template-columns:160px 180px 150px 170px minmax(300px,1fr) auto auto;gap:8px;margin-bottom:10px}
select,button{height:38px;border:1px solid var(--line);border-radius:7px;background:#fff;padding:0 10px;font-size:13px}button{cursor:pointer}
.period-picker{display:flex;align-items:center;flex-wrap:wrap;gap:8px;margin:0 0 8px}.period-title{font-size:13px;color:var(--muted);margin-right:2px}
.period-chip{display:inline-flex;align-items:center;gap:6px;min-height:34px;padding:5px 10px;border:1px solid var(--line);border-radius:999px;background:#fff;cursor:pointer;font-size:13px;user-select:none}
.period-chip:has(input:checked){border-color:#84adff;background:#eff4ff;color:#1849a9}.period-chip.unavailable{border-style:dashed;color:#98a2b3}.period-chip input{margin:0;accent-color:#2563eb}
.period-note{min-height:20px;font-size:12px;color:var(--muted);margin-bottom:8px}.metrics{display:grid;grid-template-columns:repeat(8,minmax(120px,1fr));gap:8px;margin-bottom:10px}.metric{background:#fff;border:1px solid var(--line);border-radius:7px;padding:8px 10px}
.metric .k{font-size:11px;color:var(--muted)}.metric .v{font-size:16px;font-weight:700;margin-top:3px}.submetric{display:block;font-size:12px;font-weight:600;margin-top:4px}.submetric.rise{color:#d92d20}.submetric.fall{color:#039855}.submetric.flat{color:var(--muted)}.panel{background:#fff;border:1px solid var(--line);border-radius:8px}#chart{height:820px;width:100%}
.footer{font-size:12px;color:var(--muted);padding:10px 2px}.warn{color:#b42318;font-weight:600}.empty-chart{display:grid;place-items:center;height:100%;color:var(--muted)}
@media(max-width:1000px){.toolbar{grid-template-columns:1fr}.metrics{grid-template-columns:repeat(2,1fr)}}
"""
    script = r"""
const records=__RECORDS_JSON__; const summary=__SUMMARY_JSON__; const rankBasis=summary.rank_basis||'r_multiple'; let filtered=[]; let active=0;
const resultEl=document.getElementById('result'),sortEl=document.getElementById('sort'),yearEl=document.getElementById('year'),productEl=document.getElementById('product'),tradeEl=document.getElementById('trade');
if(summary.intraday_top_selection){resultEl.insertAdjacentHTML('beforeend','<option value="long_top30">盈利多头涨幅Top30（15分钟）</option><option value="short_top30">盈利空头跌幅Top30（15分钟）</option>')}
const periodInputs=[...document.querySelectorAll('input[data-period]')];
const selectedPeriods=new Set(periodInputs.filter(el=>el.checked).map(el=>el.dataset.period));
const periodOptions=[
 {id:'day30',field:'day30',name:'30日K',volumeName:'30日成交量',kind:'period'},
 {id:'day10',field:'day10',name:'10日K',volumeName:'10日成交量',kind:'period'},
 {id:'monthly',field:'monthly',name:'月K',volumeName:'月成交量',kind:'period'},
 {id:'weekly',field:'weekly',name:'周K',volumeName:'周成交量',kind:'period'},
 {id:'daily',field:'daily',name:'日K',volumeName:'日成交量',kind:'daily'},
 {id:'intraday',field:'intraday',name:'15分钟K',volumeName:'15分钟成交量',kind:'intraday'}
];
const fmt=(v,d=2)=>Number(v).toLocaleString('zh-CN',{minimumFractionDigits:d,maximumFractionDigits:d});
const uniq=a=>[...new Set(a)].sort();
function options(el,values,label){el.innerHTML=`<option value="">全部${label}</option>`+values.map(v=>`<option value="${v}">${v}</option>`).join('')}
options(yearEl,uniq(records.map(r=>r.meta.entry_date.slice(0,4))),'年份');options(productEl,uniq(records.map(r=>r.meta.product)),'品种');
function apply(){const result=resultEl.value,y=yearEl.value,p=productEl.value,sortMode=sortEl.value,extreme=sortMode==='extreme';const resultOk=r=>result==='all'||r.meta.result_type===result||(result==='profit_tail'&&r.meta.result_type==='profit'&&r.meta.is_tail===1)||(result==='loss_tail'&&r.meta.result_type==='loss'&&r.meta.is_tail===1)||(result==='long_top30'&&r.meta.direction==='long'&&r.meta.intraday_top_rank>0)||(result==='short_top30'&&r.meta.direction==='short'&&r.meta.intraday_top_rank>0);filtered=records.filter(r=>resultOk(r)&&(!y||r.meta.entry_date.startsWith(y))&&(!p||r.meta.product===p));filtered.sort((a,b)=>{if(sortMode==='price_desc'||sortMode==='price_asc'){const av=Number(a.meta.price_change_pct),bv=Number(b.meta.price_change_pct),aValid=Number.isFinite(av),bValid=Number.isFinite(bv);if(!aValid&&!bValid)return 0;if(!aValid)return 1;if(!bValid)return -1;return sortMode==='price_desc'?bv-av:av-bv}if(rankBasis==='realized_pnl'){const av=Math.abs(Number(a.meta.realized_pnl)),bv=Math.abs(Number(b.meta.realized_pnl));return extreme?bv-av:av-bv}const ar=a.meta.r_multiple===null?null:Math.abs(Number(a.meta.r_multiple)),br=b.meta.r_multiple===null?null:Math.abs(Number(b.meta.r_multiple));if(ar===null&&br===null)return Math.abs(b.meta.realized_pnl)-Math.abs(a.meta.realized_pnl);if(ar===null)return 1;if(br===null)return -1;return extreme?br-ar:ar-br});active=0;refreshSelect();render()}
function rfmt(v){return v===null?'N/A':fmt(v)}
function refreshSelect(){const priceSort=sortEl.value.startsWith('price_');tradeEl.innerHTML=filtered.map((r,i)=>`<option value="${i}">#${i+1} ${r.meta.vt_symbol} ${r.meta.direction} ${priceSort?`涨跌=${fmt(r.meta.price_change_pct)}%`:(rankBasis==='realized_pnl'?`PnL=${fmt(r.meta.realized_pnl,0)}`:`R=${rfmt(r.meta.r_multiple)}`)} ${r.meta.entry_date}→${r.meta.exit_date}</option>`).join('');tradeEl.value=String(active)}
function colors(o,c){return o.map((v,i)=>c[i]>=v?'#d92d20':'#039855')}
function axisRef(prefix,index){return index===0?prefix:`${prefix}${index+1}`}
function layoutAxis(prefix,index){return index===0?`${prefix}axis`:`${prefix}axis${index+1}`}
function panelDomains(count,index){const gap=count===1?0:0.024;const height=(1-gap*(count-1))/count;const top=1-index*(height+gap);const bottom=top-height;const volumeHeight=height*.19;const innerGap=height*.035;return {price:[bottom+volumeHeight+innerGap,top],volume:[bottom,bottom+volumeHeight]}}
function visiblePeriodOptions(meta){return periodOptions.filter(option=>selectedPeriods.has(option.id)&&(option.id!=='intraday'||meta.draw_intraday===1))}
function updatePeriodNote(meta){const noMinute=meta.draw_intraday!==1;const chip=document.querySelector('[data-chip="intraday"]');chip.classList.toggle('unavailable',noMinute);const skipped=noMinute&&selectedPeriods.has('intraday');let text;if(meta.intraday_selection){const missing=meta.missing_15m_dates.length;const warm=meta.intraday_ma40_warmup_missing_bars||0;text=`${meta.intraday_selection}；${missing?`<span class="warn">${missing}个交易日缺少或不完整15分钟数据</span>`:'15分钟窗口已覆盖'}${warm?`；${warm}根MA40预热不足，保持空值`:''}。`}else{text=skipped?'<span class="warn">当前交易无15分钟数据，已跳过15分钟K；切到已补数交易时恢复。</span>':(noMinute?'当前交易无15分钟数据。':'六个周期均有可用数据。')}document.getElementById('periodNote').innerHTML=text}
function panelTraces(record,option,panelIndex){const data=record[option.field],xaxis=axisRef('x',panelIndex),priceAxis=axisRef('y',panelIndex*2),volumeAxis=axisRef('y',panelIndex*2+1);let customdata,hovertemplate;if(option.kind==='daily'){customdata=data.date.map((v,i)=>[v,data.source[i]]);hovertemplate='%{customdata[0]} %{customdata[1]}<br>O=%{open} H=%{high}<br>L=%{low} C=%{close}<extra></extra>'}else if(option.kind==='intraday'){customdata=data.datetime.map((v,i)=>[v,data.source[i]]);hovertemplate='%{customdata[0]} %{customdata[1]}<br>O=%{open} H=%{high}<br>L=%{low} C=%{close}<extra></extra>'}else{customdata=data.label;hovertemplate='%{customdata}<br>O=%{open} H=%{high}<br>L=%{low} C=%{close}<extra></extra>'}const width=option.kind==='daily'?.72:(option.kind==='intraday'?undefined:data.width);const candle={type:'candlestick',x:data.x,open:data.open,high:data.high,low:data.low,close:data.close,name:option.name,xaxis,yaxis:priceAxis,showlegend:false,customdata,hovertemplate,increasing:{line:{color:'#d92d20'}},decreasing:{line:{color:'#039855'}}};const traces=[candle];const maColors={5:'#f59e0b',10:'#2563eb',20:'#9333ea',40:'#111827'};[5,10,20,40].forEach(period=>traces.push({type:'scatter',mode:'lines',x:data.x,y:data[`ma${period}`],name:`${option.name} MA${period}`,xaxis,yaxis:priceAxis,showlegend:option.id==='daily',legendgroup:`ma${period}`,line:{color:maColors[period],width:option.kind==='intraday'?1.2:1.4}}));const volumeCustom=option.kind==='daily'?data.date:(option.kind==='intraday'?data.datetime:data.label);traces.push({type:'bar',x:data.x,y:data.volume,width,xaxis,yaxis:volumeAxis,marker:{color:colors(data.open,data.close),opacity:.56},name:option.volumeName,showlegend:false,customdata:volumeCustom,hovertemplate:'%{customdata}<br>Vol=%{y:,.0f}<extra></extra>'});return traces}
function render(){if(!filtered.length){Plotly.purge('chart');document.getElementById('metrics').innerHTML='<div class="warn">没有符合筛选条件的交易</div>';return}const r=filtered[active],m=r.meta,d=r.daily;tradeEl.value=String(active);updatePeriodNote(m);const visible=visiblePeriodOptions(m);const hasIntraday=m.draw_intraday===1;const missing=hasIntraday?(m.missing_15m_dates.length?`<span class="warn">${m.missing_15m_dates.length}日缺15m</span>`:'完整'):'不绘制';const contextGap=m.missing_context_dates.length?`<span class="warn">${m.missing_context_dates.length}日背景缺口</span>`:'日背景完整';const sourceParts=[];if(m.context_fallback_dates.length)sourceParts.push(`${m.context_fallback_dates.length}日主力代理`);if(m.missing_context_dates.length)sourceParts.push(`${m.missing_context_dates.length}日背景缺口`);const source=sourceParts.length?sourceParts.join('；'):'全程精确合约';const resultLabel=m.result_type==='profit'?'盈利':(m.result_type==='loss'?'亏损':'持平');const priceClass=m.price_change_pct>0?'rise':(m.price_change_pct<0?'fall':'flat');const pnlValue=`${fmt(m.realized_pnl,0)}<span class="submetric ${priceClass}">${m.price_change_label}</span>`;const rankLabel=sortEl.value.startsWith('price_')?'涨跌幅排序':(rankBasis==='realized_pnl'?'盈亏排序':'R排序');const metric=[[rankLabel,`#${active+1}`],['结果',resultLabel],['合约',m.vt_symbol],['方向',m.direction],['净利润',pnlValue],['R倍数',rfmt(m.r_multiple)],['平仓lot',m.lot_count],['分钟/背景',`${missing}<br>${contextGap}`]];document.getElementById('metrics').innerHTML=metric.map(([k,v])=>`<div class="metric"><div class="k">${k}</div><div class="v">${v}</div></div>`).join('');const chart=document.getElementById('chart');chart.style.height=`${Math.max(720,visible.length*350+100)}px`;if(!visible.length){Plotly.purge('chart');chart.innerHTML='<div class="empty-chart">当前勾选的周期在这笔交易上没有可绘制数据，请再选择一个非分钟周期。</div>';return}let traces=[];visible.forEach((option,index)=>{traces=traces.concat(panelTraces(r,option,index))});const markerPanelIndex=visible.findIndex(option=>option.id==='daily')>=0?visible.findIndex(option=>option.id==='daily'):visible.length-1;traces.push({type:'scatter',mode:'markers',x:[m.entry_x,m.exit_x],y:[m.entry_marker_price,m.exit_marker_price],xaxis:axisRef('x',markerPanelIndex),yaxis:axisRef('y',markerPanelIndex*2),name:'同源成交价格',marker:{symbol:['triangle-up','triangle-down'],size:12,color:['#2563eb','#9333ea']}});const tickStep=Math.max(1,Math.ceil(d.date.length/18)),tickvals=d.x.filter((_,i)=>i%tickStep===0),ticktext=d.date.filter((_,i)=>i%tickStep===0);const switches=m.source_switch_x.map(x=>({type:'line',xref:'x',yref:'paper',x0:x,x1:x,y0:0,y1:1,line:{color:'#98a2b3',width:1,dash:'dash'}}));const layout={title:{text:`${resultLabel} #${active+1} ${m.vt_symbol} ${m.direction}｜${m.entry_date} → ${m.exit_date}｜R=${rfmt(m.r_multiple)}｜PnL=${fmt(m.realized_pnl,0)}｜${m.selection_basis}｜${source}`,x:.01},margin:{l:72,r:28,t:74,b:76},paper_bgcolor:'#fff',plot_bgcolor:'#fff',hovermode:'x unified',showlegend:true,legend:{orientation:'h',y:1.055,x:1,xanchor:'right'},uirevision:m.open_trade_id,shapes:[{type:'rect',xref:'x',yref:'paper',x0:m.entry_x,x1:m.exit_x,y0:0,y1:1,fillcolor:'#fef3c7',opacity:.17,line:{width:0}},{type:'line',xref:'x',yref:'paper',x0:m.entry_x,x1:m.entry_x,y0:0,y1:1,line:{color:'#2563eb',width:1.5,dash:'dot'}},{type:'line',xref:'x',yref:'paper',x0:m.exit_x,x1:m.exit_x,y0:0,y1:1,line:{color:'#9333ea',width:1.5,dash:'dot'}},...switches],annotations:[{xref:'x',yref:'paper',x:m.entry_x,y:1,text:'开仓',showarrow:false,font:{color:'#2563eb'}},{xref:'x',yref:'paper',x:m.exit_x,y:1,text:'平仓',showarrow:false,font:{color:'#9333ea'}}]};visible.forEach((option,index)=>{const domains=panelDomains(visible.length,index),xRef=axisRef('x',index),xKey=layoutAxis('x',index),priceIndex=index*2,volumeIndex=priceIndex+1,priceKey=layoutAxis('y',priceIndex),volumeKey=layoutAxis('y',volumeIndex);layout[xKey]={range:[m.chart_x_start,m.chart_x_end],tickvals,ticktext,tickangle:-35,showticklabels:index===visible.length-1,showgrid:false,rangeslider:{visible:false},anchor:axisRef('y',priceIndex),title:index===visible.length-1?`共享交易日坐标（${visible.length}个周期同步缩放）`:undefined};if(index>0)layout[xKey].matches='x';layout[priceKey]={domain:domains.price,title:option.name,showgrid:true,gridcolor:'#eef1f4',anchor:xRef};layout[volumeKey]={domain:domains.volume,title:option.volumeName.replace('成交',''),showgrid:true,gridcolor:'#f2f4f7',anchor:xRef}});Plotly.react('chart',traces,layout,{responsive:true,displaylogo:false,scrollZoom:true})}
periodInputs.forEach(input=>input.addEventListener('change',()=>{if(input.checked){selectedPeriods.add(input.dataset.period)}else if(selectedPeriods.size===1){input.checked=true;return}else{selectedPeriods.delete(input.dataset.period)}render()}));
resultEl.onchange=apply;sortEl.onchange=apply;yearEl.onchange=apply;productEl.onchange=apply;tradeEl.onchange=()=>{active=Number(tradeEl.value);render()};
document.getElementById('prev').onclick=()=>{if(filtered.length){active=(active-1+filtered.length)%filtered.length;render()}};document.getElementById('next').onclick=()=>{if(filtered.length){active=(active+1)%filtered.length;render()}};apply();
"""
    script = script.replace("__RECORDS_JSON__", records_json).replace("__SUMMARY_JSON__", summary_json)
    plotly_js = get_plotlyjs()
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title><script>{plotly_js}</script><style>{styles}</style></head><body><div class="page"><h1>{html.escape(title)}</h1>
<div class="note">{html.escape(source_warning)}{' ' if source_warning else ''}{coverage_note}日K严格展示开仓前300个交易日至最终平仓后50个交易日的可用历史；30日K与10日K按产品交易日历固定、不重叠分桶；最新不足完整周期的K线仍显示，并在悬浮标签注明实际日数。月K独立展示开仓前10个月至最终平仓后10个月；所有周期的 MA5/10/20/40 均用图窗外历史预热。蓝线=开仓日，紫线=最终平仓日，淡黄色=持仓区间；灰虚线表示精确合约缺历史数据后切到当日主力上下文。</div>
<div class="toolbar"><select id="result"><option value="all">全部交易</option><option value="profit">全部盈利</option><option value="loss">全部亏损</option><option value="flat">持平交易</option><option value="profit_tail">盈利尾部</option><option value="loss_tail">亏损尾部</option></select><select id="sort"><option value="extreme">{html.escape(sort_extreme_label)}</option><option value="near">{html.escape(sort_near_label)}</option><option value="price_desc">价格涨跌百分比从大到小</option><option value="price_asc">价格涨跌百分比从小到大</option></select><select id="year"></select><select id="product"></select><select id="trade"></select><button id="prev">上一笔</button><button id="next">下一笔</button></div>
<div class="period-picker" id="periodPicker"><span class="period-title">绘制周期（可多选）</span>
<label class="period-chip" data-chip="day30"><input type="checkbox" data-period="day30" checked><span>30日K</span></label>
<label class="period-chip" data-chip="day10"><input type="checkbox" data-period="day10"><span>10日K</span></label>
<label class="period-chip" data-chip="monthly"><input type="checkbox" data-period="monthly"><span>月K</span></label>
<label class="period-chip" data-chip="weekly"><input type="checkbox" data-period="weekly"><span>周K</span></label>
<label class="period-chip" data-chip="daily"><input type="checkbox" data-period="daily" checked><span>日K</span></label>
<label class="period-chip" data-chip="intraday"><input type="checkbox" data-period="intraday"><span>15分钟K</span></label></div>
<div id="periodNote" class="period-note"></div><div id="metrics" class="metrics"></div><div class="panel"><div id="chart"></div></div>
<div class="footer">数据：{html.escape(source_label)}（{html.escape(source_version)}）；{footer_scope}{html.escape(source_warning)}{' ' if source_warning else ''}本图用于对照复盘，不是交易规则。</div>
</div><script>{script}</script></body></html>"""


def main() -> None:
    global ACTIVE_DATABASE_PATH, PREFER_DATABASE_DAILY
    parser = argparse.ArgumentParser(description="Build C9/15w historical profit/loss-tail monthly/weekly/daily/15m HTML atlas.")
    parser.add_argument(
        "--source-profile",
        choices=["official_c9", "stage037c", "stage061_top10"],
        default="official_c9",
        help="Use current C9 artifacts, frozen Stage037 C, or frozen Stage061 Top10+fu.",
    )
    parser.add_argument("--end", default=_latest_completed_date().date().isoformat())
    parser.add_argument(
        "--episode-scope",
        choices=["tail", "all"],
        default="tail",
        help="Render the original profit/loss tails or every completed trade episode.",
    )
    parser.add_argument("--reuse-market", action="store_true", help="Reuse the already materialized 15m market file.")
    parser.add_argument(
        "--reuse-strategy",
        action="store_true",
        help="Reuse the frozen closed lots, selected episodes, and strategy daily artifacts without rerunning C9.",
    )
    parser.add_argument(
        "--no-market-download",
        action="store_true",
        help="Use only existing daily/15m market files; fail if a visible chart window is incomplete.",
    )
    args = parser.parse_args()
    end = pd.Timestamp(args.end).normalize()
    is_stage037c = args.source_profile == "stage037c"
    is_stage061 = args.source_profile == "stage061_top10"
    is_frozen = is_stage037c or is_stage061
    if is_frozen and args.episode_scope != "all":
        raise RuntimeError("Frozen-source atlas is intentionally available only in full-cycle scope.")
    if is_frozen:
        args.no_market_download = True
    output_dir = (
        STAGE037C_OUTPUT_DIR
        if is_stage037c
        else (FULL_OUTPUT_DIR if args.episode_scope == "all" else OUTPUT_DIR)
    )
    html_path = (
        STAGE037C_HTML_PATH
        if is_stage037c
        else (FULL_HTML_PATH if args.episode_scope == "all" else HTML_PATH)
    )
    manifest_path = (
        STAGE037C_MANIFEST_PATH
        if is_stage037c
        else (FULL_MANIFEST_PATH if args.episode_scope == "all" else MANIFEST_PATH)
    )
    summary_path = (
        STAGE037C_SUMMARY_PATH
        if is_stage037c
        else (FULL_SUMMARY_PATH if args.episode_scope == "all" else SUMMARY_PATH)
    )
    closed_path = STAGE037C_CLOSED_LOTS_PATH if is_stage037c else CLOSED_LOTS_PATH
    selected_path = STAGE037C_SELECTED_EPISODES_PATH if is_stage037c else SELECTED_EPISODES_PATH
    daily_path = STAGE037C_DAILY_PATH if is_stage037c else STRATEGY_DAILY_PATH
    minute_path = STAGE037C_MINUTE_PATH if is_stage037c else MINUTE_15M_PATH
    if is_stage061:
        output_dir = STAGE061_TOP10_OUTPUT_DIR
        html_path = output_dir / "index.html"
        manifest_path = output_dir / "chart_manifest.csv"
        summary_path = output_dir / "summary.json"
        closed_path = output_dir / "closed_lots.csv"
        selected_path = output_dir / "selected_profit_loss_episodes.csv"
        daily_path = output_dir / "strategy_daily.csv"
        minute_path = output_dir / "bars_15m_not_used.csv"
    output_dir.mkdir(parents=True, exist_ok=True)

    started = time.time()
    if is_frozen:
        database_path = STAGE061_TOP10_DATABASE_PATH if is_stage061 else STAGE037C_FROZEN_DATABASE_PATH
        expected_database_hash = STAGE061_TOP10_DATABASE_SHA256 if is_stage061 else STAGE037C_FROZEN_DATABASE_SHA256
        if not database_path.exists():
            raise FileNotFoundError(f"Missing frozen database: {database_path}")
        database_sha256 = _sha256(database_path)
        if database_sha256 != expected_database_hash:
            raise RuntimeError(
                "Frozen database hash mismatch: "
                f"expected={expected_database_hash}, actual={database_sha256}."
            )
        ACTIVE_DATABASE_PATH = database_path
        PREFER_DATABASE_DAILY = True
        loader = _load_stage061_top10_frozen_source if is_stage061 else _load_stage037c_frozen_source
        combined, frozen_trades, frozen_metrics, provenance = loader()
        closed = _closed_lots_from_trade_ledger(
            frozen_trades,
            sizes=s513._metadata()["sizes"],
            allow_residual_open=True,
            source_prefix="stage061_top10" if is_stage061 else "stage037c",
        )
        residual_open_positions = list(closed.attrs.get("residual_open_positions", []))
        selected = _selected_tail_episodes(closed)
        spec = None
        prior_summary = {
            "backtest_metrics": frozen_metrics,
            "strategy_profile": str(frozen_metrics["profile"]),
            "provenance": {**provenance, "database_sha256": database_sha256},
        }
        closed.to_csv(closed_path, index=False, encoding="utf-8-sig")
        selected.to_csv(selected_path, index=False, encoding="utf-8-sig")
        combined.to_csv(daily_path, index=False, encoding="utf-8-sig")
    else:
        combined, closed, selected, spec, prior_summary = _strategy_inputs(
            end,
            reuse_existing=bool(args.reuse_strategy),
        )
        if not args.reuse_strategy:
            closed.to_csv(closed_path, index=False, encoding="utf-8-sig")
            selected[selected["result_type"].eq("profit")].to_csv(WINNERS_PATH, index=False, encoding="utf-8-sig")
            selected.to_csv(selected_path, index=False, encoding="utf-8-sig")
            combined.to_csv(daily_path, index=False, encoding="utf-8-sig")

    chart_episodes = _all_trade_episodes(closed) if args.episode_scope == "all" else selected.copy()
    if is_frozen:
        chart_episodes["draw_intraday"] = 0
    if args.episode_scope == "tail":
        chart_episodes["is_tail"] = 1
        chart_episodes["draw_intraday"] = 1

    effective_data_end = pd.to_datetime(combined["date"], errors="coerce").dropna().max().normalize()

    mapping = _main_mapping()
    bar_cache: dict[str, pd.DataFrame] = {}
    daily_by_episode: dict[str, pd.DataFrame] = {}
    intraday_dates_by_episode: dict[str, list[pd.Timestamp]] = {}
    for row in chart_episodes.itertuples(index=False):
        daily, intraday_dates = _context_daily(
            row,
            mapping,
            bar_cache,
            allow_daily_download=not args.no_market_download,
            allow_noncritical_daily_gaps=(
                args.episode_scope == "all" and int(getattr(row, "draw_intraday", 1)) == 0
            ),
            data_end=effective_data_end,
        )
        daily_by_episode[str(row.open_trade_id)] = daily
        intraday_dates_by_episode[str(row.open_trade_id)] = intraday_dates
        if len(daily_by_episode) % 50 == 0:
            print(f"Daily context {len(daily_by_episode)}/{len(chart_episodes)}", flush=True)
    source_ranges: dict[str, list[pd.Timestamp]] = {}
    for row in chart_episodes.itertuples(index=False):
        if int(getattr(row, "draw_intraday", 1)) == 0:
            continue
        daily = daily_by_episode[str(row.open_trade_id)].set_index("date")
        for trading_day in intraday_dates_by_episode[str(row.open_trade_id)]:
            source = str(daily.loc[trading_day, "source_vt_symbol"])
            source_ranges.setdefault(source, []).append(trading_day)
    fetch_rows: list[FetchStatus] = []
    if not source_ranges:
        bars_15m = pd.DataFrame(
            columns=[
                "vt_symbol",
                "bar_datetime",
                "trading_day",
                "open",
                "high",
                "low",
                "close",
                "volume",
            ]
        )
        bars_15m.to_csv(minute_path, index=False, encoding="utf-8-sig")
    elif args.reuse_market and minute_path.exists():
        bars_15m = pd.read_csv(minute_path, encoding="utf-8-sig")
        bars_15m["bar_datetime"] = pd.to_datetime(bars_15m["bar_datetime"], errors="coerce")
        bars_15m = pd.concat(
            [
                _assign_trading_day(group.drop(columns=["trading_day"], errors="ignore"), _product_calendar(mapping, symbol))
                for symbol, group in bars_15m.groupby("vt_symbol", sort=False)
            ],
            ignore_index=True,
            sort=False,
        )
        supplemental_frames: list[pd.DataFrame] = []
        for vt_symbol, all_dates in sorted(source_ranges.items()):
            required = {pd.Timestamp(value).normalize() for value in all_dates}
            available = set(
                pd.to_datetime(
                    bars_15m.loc[bars_15m["vt_symbol"].eq(vt_symbol), "trading_day"],
                    errors="coerce",
                ).dropna().dt.normalize()
            )
            missing = sorted(required.difference(available))
            if not missing:
                continue
            if args.no_market_download:
                raise RuntimeError(
                    f"Reused 15m market data is incomplete for {vt_symbol}: "
                    f"{[value.date().isoformat() for value in missing]}"
                )
            frame, fetch_status = _fetch_15m(vt_symbol, min(missing), max(missing))
            frame = _assign_trading_day(frame, _product_calendar(mapping, vt_symbol))
            supplemental_frames.append(frame)
            fetch_rows.append(fetch_status)
            print(
                f"15m supplement {vt_symbol}: {len(frame)} rows for {len(missing)} missing days "
                f"in {fetch_status.elapsed_seconds:.3f}s",
                flush=True,
            )
        if supplemental_frames:
            bars_15m = (
                pd.concat([bars_15m, *supplemental_frames], ignore_index=True, sort=False)
                .drop_duplicates(["vt_symbol", "bar_datetime"], keep="last")
                .sort_values(["vt_symbol", "bar_datetime"])
                .reset_index(drop=True)
            )
            bars_15m.to_csv(minute_path, index=False, encoding="utf-8-sig")
    else:
        minute_frames: list[pd.DataFrame] = []
        for vt_symbol, all_dates in sorted(source_ranges.items()):
            daily = bar_cache[vt_symbol]
            start = min(all_dates)
            finish = max(all_dates)
            frame, fetch_status = _fetch_15m(vt_symbol, start, finish)
            frame = _assign_trading_day(frame, _product_calendar(mapping, vt_symbol))
            minute_frames.append(frame)
            fetch_rows.append(fetch_status)
            print(f"15m {vt_symbol}: {len(frame)} rows in {fetch_status.elapsed_seconds:.3f}s", flush=True)
        bars_15m = pd.concat(minute_frames, ignore_index=True, sort=False)
        bars_15m.to_csv(minute_path, index=False, encoding="utf-8-sig")
    records, manifest = _records(chart_episodes, daily_by_episode, intraday_dates_by_episode, bars_15m)
    missing_intraday_days = int(manifest["intraday_missing_days"].sum())
    if missing_intraday_days:
        missing_rows = manifest.loc[
            manifest["intraday_missing_days"].gt(0),
            ["result_type", "result_rank", "open_trade_id", "vt_symbol", "intraday_missing_days"],
        ].to_dict("records")
        raise RuntimeError(f"Selected profit/loss episodes have incomplete 15m coverage: {missing_rows}")
    manifest.to_csv(manifest_path, index=False, encoding="utf-8-sig")

    equity_column = "account_equity" if "account_equity" in combined.columns else "equity"
    metrics = (
        prior_summary.get("backtest_metrics", {})
        if args.reuse_strategy or is_frozen
        else s901.s650._metrics(combined, spec.capital, 1.0)
    )
    summary = {
        "line_id": LINE_ID,
        "stage": "Stage045" if is_stage037c else ("Stage042" if args.episode_scope == "all" else STAGE),
        "model_tag": (
            "stage045_stage037c_all_trade_multiscale_html_v1"
            if is_stage037c
            else ("stage042_c9_15w_all_trade_multiscale_html_v2" if args.episode_scope == "all" else MODEL_TAG)
        ),
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "account_capital": OFFICIAL_LIVE_CAPITAL,
        "analysis_start": str(metrics.get("analysis_start", START.date().isoformat())),
        "requested_end": end.date().isoformat(),
        "effective_data_end": effective_data_end.date().isoformat(),
        "episode_scope": str(args.episode_scope),
        "chart_episodes": int(len(chart_episodes)),
        "chart_profit_episodes": int(chart_episodes["result_type"].eq("profit").sum()),
        "chart_loss_episodes": int(chart_episodes["result_type"].eq("loss").sum()),
        "chart_flat_episodes": int(chart_episodes["result_type"].eq("flat").sum()),
        "intraday_draw_episodes": int(pd.to_numeric(chart_episodes["draw_intraday"]).sum()),
        "closed_lots": int(len(closed)),
        "winner_lots": int(closed["winner"].sum()),
        "big_winner_lots": int(selected["result_type"].eq("profit").sum()),
        "big_winner_episodes": int(selected["result_type"].eq("profit").sum()),
        "big_loser_episodes": int(selected["result_type"].eq("loss").sum()),
        "selected_episode_closed_lots": int(pd.to_numeric(selected["lot_count"], errors="coerce").sum()),
        "episode_closed_lots": int(pd.to_numeric(selected.loc[selected["result_type"].eq("profit"), "lot_count"], errors="coerce").sum()),
        "big_winner_threshold_r": float(selected["profit_r_threshold"].iloc[0]),
        "big_loser_threshold_r": float(selected["loss_r_threshold"].iloc[0]),
        "unique_contracts": int(chart_episodes["vt_symbol"].nunique()),
        "bars_15m": int(len(bars_15m)),
        "chart_bars_15m": int(manifest["bars_15m"].sum()),
        "intraday_missing_days": int(manifest["intraday_missing_days"].sum()),
        "context_fallback_days": int(manifest["context_fallback_days"].sum()),
        "day30_bars": int(manifest["day30_bars"].sum()),
        "day10_bars": int(manifest["day10_bars"].sum()),
        "monthly_bars": int(manifest["monthly_bars"].sum()),
        "period_picker": {
            "options": ["day30", "day10", "monthly", "weekly", "daily", "intraday"],
            "default_selected": ["day30", "daily"],
            "fixed_trading_day_buckets": [30, 10],
            "ma_periods": list(MA_PERIODS),
            "trading_day_ma_warmup_days": TRADING_DAY_MA_WARMUP_DAYS,
        },
        "daily_window": {
            "trading_days_before_entry": DAILY_PRE,
            "trading_days_after_exit": DAILY_POST,
            "strict_visible_window": True,
        },
        "monthly_window": {
            "months_before_entry": MONTHLY_PRE,
            "months_after_exit": MONTHLY_POST,
            "ma_warmup_months": MONTHLY_MA_WARMUP_MONTHS,
        },
        "winner_selection": "Profit episodes selected by top-20% R, plus top-20% realized profit when R is unavailable.",
        "loser_selection": "Loss episodes selected by bottom-20% R, plus bottom-20% realized loss when R is unavailable.",
        "end_equity": float(pd.to_numeric(combined[equity_column], errors="coerce").dropna().iloc[-1])
        if equity_column in combined.columns and combined[equity_column].notna().any()
        else None,
        "backtest_metrics": _json_safe(metrics),
        "strategy_profile": (
            str(prior_summary.get("strategy_profile", ""))
            if args.reuse_strategy or is_frozen
            else str(spec.profile)
        ),
        "strategy_reused": bool(args.reuse_strategy or is_frozen),
        "market_download_disabled": bool(args.no_market_download or is_frozen),
        "fetch_status": [asdict(item) for item in fetch_rows],
        "elapsed_seconds": round(time.time() - started, 3),
        "artifacts": {
            "html": str(html_path),
            "closed_lots": str(closed_path),
            "big_winners": None if is_frozen else str(WINNERS_PATH),
            "selected_episodes": str(selected_path),
            "bars_15m": str(minute_path),
            "strategy_daily": str(daily_path),
            "manifest": str(manifest_path),
        },
        "anti_overfit_note": (
            "Visualization only. Full-cycle inspection is descriptive evidence, not a trading rule or alpha validation."
            if args.episode_scope == "all"
            else "Visualization only. Tail inspection is hypothesis generation, not rule validation."
        ),
    }
    if is_stage037c:
        summary.update(
            {
                "page_title": "Stage037 C研究版全周期逐笔复盘：30日K / 10日K / 月K / 周K / 日K",
                "source_label": "Stage037 C研究版",
                "source_version": str(metrics["variant"]),
                "source_warning": "研究版未晋级，不是当前正式策略。",
                "rank_basis": "realized_pnl",
                "coverage_note": (
                    "全部完整交易均可选择30日K、10日K、月K、周K和日K；"
                    f"冻结账本另有{len(residual_open_positions)}笔截至回测终点仍未平仓，因此不纳入需要明确平仓点的逐笔图；"
                    "冻结证据包不能保证同源15分钟数据完整，因此所有交易均不读取、不绘制分钟线。"
                ),
                "footer_scope": (
                    f"共{len(chart_episodes)}笔完整开平仓episode，部分平仓按一次开仓聚合到最终平仓；"
                    "冻结产物没有逐笔entry_risk，R统一显示N/A并按净利润绝对值排序；"
                ),
                "source_provenance": prior_summary["provenance"],
                "source_commit": STAGE037C_SOURCE_COMMIT,
                "source_database_sha256": prior_summary["provenance"]["database_sha256"],
                "residual_open_positions_not_charted": residual_open_positions,
            }
        )
    if is_stage061:
        summary.update({
            "stage": "Stage049",
            "model_tag": "stage049_stage061_top10_fu_all_trade_multiscale_html_v1",
            "page_title": "Stage037 + Top10＋fu 全周期逐笔复盘：30日K / 10日K / 月K / 周K / 日K",
            "source_label": "Stage037 + Top10＋fu 对应历史回测（Stage061 T10）",
            "source_version": str(metrics["variant"]),
            "source_warning": (
                "线上版本对应的历史回测，不是券商实盘成交。"
                "冻结区间2018-01-02～2026-08-28，798条成交记录；"
                "历史成本与多周期门禁失败记录仍保留，正式采用属于用户授权覆盖，不代表所有稳健性门禁通过。"
            ),
            "rank_basis": "realized_pnl",
            "coverage_note": (
                "全部完整交易均可选择30日K、10日K、月K、周K和日K，不绘制15分钟线；"
                f"回测终点另有{len(residual_open_positions)}笔未平仓持仓，不纳入需要明确平仓点的逐笔图。"
                "日线和交易日历均截于回测终点，窗口历史不足时按实际可用数据展示，不虚构未来K线。"
            ),
            "footer_scope": (
                f"798条原始成交配对为{len(closed)}条平仓记录、{len(chart_episodes)}笔完整开平仓交易；"
                "部分平仓按开仓聚合，价格涨跌幅采用成交量加权平仓价；"
                "冻结产物没有逐笔entry_risk，R显示N/A；单笔盈亏按成交价差与乘数计算，未另行摊分成本。"
            ),
            "source_provenance": prior_summary["provenance"],
            "source_commit": STAGE061_TOP10_SOURCE_COMMIT,
            "source_database_sha256": database_sha256,
            "source_mapping_sha256": _sha256(MAPPING_PATH),
            "source_mapping_path": str(MAPPING_PATH),
            "residual_open_positions_not_charted": residual_open_positions,
            "ruleset_version": "stage037_stage034_long_short_mirror_hard_block_v1",
            "ai_pool_policy_version": "ai_top10_plus_fu_official_live_v1",
            "production_reference_at_request": {
                "checked_date": "2026-08-31",
                "source_commit": "1961d98ccb2b9129e35fe982b7330ae4217dcde6",
                "material_release_id": "m0004_20260831T112631+0800_2485073e9594",
                "manifest_sha256": "50fa73a5627fb657958827c6dda66b39c46f0e49343d2217ad720a97ed46d778",
            },
            "order_api_called_count": 0,
            "ctp_connected": False,
        })
    html_path.write_text(_html(records, summary), encoding="utf-8")
    artifact_paths = {
        "html": html_path,
        "closed_lots": closed_path,
        "selected_episodes": selected_path,
        "bars_15m": minute_path,
        "strategy_daily": daily_path,
        "manifest": manifest_path,
    }
    if not is_frozen:
        artifact_paths["big_winners"] = WINNERS_PATH
    summary["artifact_sha256"] = {key: _sha256(path) for key, path in artifact_paths.items()}
    summary_path.write_text(json.dumps(_json_safe(summary), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: summary[key] for key in ["closed_lots", "winner_lots", "big_winner_episodes", "big_loser_episodes", "big_winner_threshold_r", "big_loser_threshold_r", "bars_15m", "intraday_missing_days", "elapsed_seconds"]}, ensure_ascii=False, indent=2))
    print(html_path)


if __name__ == "__main__":
    main()
