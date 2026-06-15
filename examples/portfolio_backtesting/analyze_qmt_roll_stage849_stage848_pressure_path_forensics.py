from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage825_stage819_intraday_rule_forensics as s825
import qmt_roll_official_candidate_stage819_30w_config as stage819_cfg


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage849"
MODEL_TAG = "stage849_stage848_pressure_path_forensics_v1"
OUTPUT_PREFIX = "qmt_roll_stage849_stage848_pressure_path_forensics"

STAGE830_PREFIX = "qmt_roll_stage830_stage827_c2_broker10_margin_cap"
STAGE830_TAG = "stage830_stage827_c2_broker10_margin_cap_v1"
STAGE847_PREFIX = "qmt_roll_stage847_stage830_c4_stop_retry_engine"
STAGE847_TAG = "stage847_stage830_c4_stop_retry_engine_v1"
STAGE848_PREFIX = "qmt_roll_stage848_stage847_c9_peak_trough_forensics"
STAGE848_TAG = "stage848_stage847_c9_peak_trough_forensics_v1"

C4_ARM = "stage830_stage819_c2_broker10_100_cap"
C9_ARM = "stage847_stage819_c4_05r_stop_retry_once"

C4_TRADES_PATH = OUTPUT_DIR / f"{STAGE830_PREFIX}_trades_{STAGE830_TAG}.csv"
C4_CLOSED_PATH = OUTPUT_DIR / f"{STAGE830_PREFIX}_closed_lots_{STAGE830_TAG}.csv"
C9_TRADES_PATH = OUTPUT_DIR / f"{STAGE847_PREFIX}_trades_{STAGE847_TAG}.csv"
C9_CLOSED_PATH = OUTPUT_DIR / f"{STAGE847_PREFIX}_closed_lots_{STAGE847_TAG}.csv"
STAGE848_DAILY_DELTA_PATH = OUTPUT_DIR / f"{STAGE848_PREFIX}_daily_delta_{STAGE848_TAG}.csv"

EPISODE_DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_episode_daily_{MODEL_TAG}.csv"
EPISODE_LOTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_episode_lots_{MODEL_TAG}.csv"
EPISODE_LOT_PAIRS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_episode_lot_pairs_{MODEL_TAG}.csv"
EPISODE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_episode_summary_{MODEL_TAG}.csv"
MINUTE_FEATURES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_minute_features_{MODEL_TAG}.csv"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
PATH_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_episode_path_chart_{MODEL_TAG}.png"
ATLAS_MANIFEST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_episode_atlas_manifest_{MODEL_TAG}.csv"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_episode_atlas_{{episode_id}}_{MODEL_TAG}.png"

# Episodes are derived from Stage848's named pressure product-directions.
# They are not optimized thresholds and are used only for read-only path attribution.
EPISODES = [
    {
        "episode_id": "fu_long_20220325_0401",
        "product": "fu.SHFE",
        "direction": "long",
        "start": "2022-03-25",
        "anchor": "2022-03-29",
        "end": "2022-04-01",
        "reason": "first fu long pressure/recovery pair inside the Stage848 peak-trough window",
    },
    {
        "episode_id": "fu_long_20220418_0419",
        "product": "fu.SHFE",
        "direction": "long",
        "start": "2022-04-18",
        "anchor": "2022-04-19",
        "end": "2022-04-19",
        "reason": "fu long heat deleverage pair inside the Stage848 peak-trough window",
    },
    {
        "episode_id": "ap_long_20220428_0510",
        "product": "AP.CZCE",
        "direction": "long",
        "start": "2022-04-28",
        "anchor": "2022-05-09",
        "end": "2022-05-10",
        "reason": "AP long pressure day noted by Stage848",
    },
    {
        "episode_id": "fu_long_20220506_0509",
        "product": "fu.SHFE",
        "direction": "long",
        "start": "2022-05-06",
        "anchor": "2022-05-06",
        "end": "2022-05-09",
        "reason": "fu long broker/exposure pressure day noted by Stage848",
    },
    {
        "episode_id": "fg_short_20220524_0602",
        "product": "FG.CZCE",
        "direction": "short",
        "start": "2022-05-24",
        "anchor": "2022-05-27",
        "end": "2022-06-02",
        "reason": "FG short max broker10 pressure segment noted by Stage848",
    },
    {
        "episode_id": "fu_long_20220527_0531",
        "product": "fu.SHFE",
        "direction": "long",
        "start": "2022-05-27",
        "anchor": "2022-05-27",
        "end": "2022-05-31",
        "reason": "second fu long pressure pair inside the Stage848 peak-trough window",
    },
    {
        "episode_id": "fu_short_20220622_0629",
        "product": "fu.SHFE",
        "direction": "short",
        "start": "2022-06-22",
        "anchor": "2022-06-28",
        "end": "2022-06-29",
        "reason": "fu short terminal pressure segment noted by Stage848",
    },
]


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if np.isfinite(number) else default


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"Missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _normal_date(value: Any) -> pd.Timestamp:
    if pd.isna(value):
        return pd.NaT
    text = str(value)
    if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
        ts = pd.to_datetime(text[:10], errors="coerce")
    else:
        ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return pd.NaT
    if getattr(ts, "tzinfo", None) is not None:
        ts = pd.Timestamp(ts).tz_convert("Asia/Shanghai").tz_localize(None)
    return pd.Timestamp(ts).normalize()


def _normal_dt(value: Any) -> pd.Timestamp:
    if pd.isna(value):
        return pd.NaT
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return pd.NaT
    if getattr(ts, "tzinfo", None) is not None:
        ts = pd.Timestamp(ts).tz_convert("Asia/Shanghai").tz_localize(None)
    return pd.Timestamp(ts)


def _numeric(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for column in columns:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def _product_from_vt(vt_symbol: Any) -> str:
    text = str(vt_symbol)
    if "." not in text:
        return text
    contract, exchange = text.split(".", 1)
    letters = "".join(ch for ch in contract if ch.isalpha())
    return f"{letters}.{exchange}" if letters else text


def _prepare_closed(path: Path, arm_label: str) -> pd.DataFrame:
    data = _load_csv(path).copy()
    if "arm" in data.columns:
        data = data[data["arm"].astype(str).isin([arm_label])].copy()
    for column in ("entry_date", "exit_date"):
        data[column] = data[column].map(_normal_date)
    data["product"] = data["vt_symbol"].map(_product_from_vt)
    data["arm_label"] = "C4" if arm_label == C4_ARM else "C9"
    return _numeric(
        data,
        [
            "entry_price",
            "exit_price",
            "volume",
            "size",
            "realized_pnl",
            "risk_amount",
            "r_multiple",
            "target_risk_amount",
            "selected_volume",
            "stop_distance",
        ],
    )


def _prepare_trades(path: Path, arm_label: str) -> pd.DataFrame:
    data = _load_csv(path).copy()
    data["date"] = data["date"].map(_normal_date)
    data["datetime_norm"] = data["datetime"].map(_normal_dt)
    data["product"] = data["vt_symbol"].map(_product_from_vt)
    data["arm_label"] = "C4" if arm_label == C4_ARM else "C9"
    return _numeric(data, ["price", "volume", "signed_volume"])


def _prepare_stage848_daily() -> pd.DataFrame:
    data = _load_csv(STAGE848_DAILY_DELTA_PATH).copy()
    data["date"] = data["date"].map(_normal_date)
    return _numeric(
        data,
        [
            "account_equity_C4",
            "account_equity_C9",
            "account_equity_delta_C9_minus_C4",
            "drawdown_pct_C4",
            "drawdown_pct_C9",
            "drawdown_pct_delta_C9_minus_C4",
            "broker10_margin_to_equity_pct_C4",
            "broker10_margin_to_equity_pct_C9",
            "broker10_margin_to_equity_pct_delta_C9_minus_C4",
            "net_pnl_C4",
            "net_pnl_C9",
            "net_pnl_delta_C9_minus_C4",
            "trade_count_C4",
            "trade_count_C9",
            "total_slippage_C4",
            "total_slippage_C9",
        ],
    )


def _size_map(*closed_frames: pd.DataFrame) -> dict[str, float]:
    rows = []
    for frame in closed_frames:
        if not frame.empty:
            rows.append(frame[["vt_symbol", "size"]].dropna())
    if not rows:
        return {}
    data = pd.concat(rows, ignore_index=True, sort=False)
    data["size"] = pd.to_numeric(data["size"], errors="coerce")
    data = data.dropna(subset=["size"]).drop_duplicates("vt_symbol", keep="last")
    return {str(row.vt_symbol): float(row.size) for row in data.itertuples(index=False)}


def _snapshot(
    trades: pd.DataFrame,
    target_date: pd.Timestamp,
    product: str,
    direction: str,
    sizes: dict[str, float],
) -> dict[str, Any]:
    upto = trades[trades["date"].le(target_date)].copy()
    if upto.empty:
        return _empty_snapshot()
    grouped = (
        upto.groupby("vt_symbol", dropna=False)
        .agg(position=("signed_volume", "sum"), last_price=("price", "last"), product=("product", "last"))
        .reset_index()
    )
    grouped = grouped[grouped["product"].astype(str).eq(product)].copy()
    if direction == "long":
        grouped = grouped[pd.to_numeric(grouped["position"], errors="coerce").fillna(0.0).gt(0)]
    else:
        grouped = grouped[pd.to_numeric(grouped["position"], errors="coerce").fillna(0.0).lt(0)]
    grouped["abs_contracts"] = pd.to_numeric(grouped["position"], errors="coerce").abs().fillna(0.0)
    grouped = grouped[grouped["abs_contracts"].gt(0)].copy()
    if grouped.empty:
        return _empty_snapshot()
    grouped["size"] = grouped["vt_symbol"].astype(str).map(sizes).fillna(1.0)
    grouped["abs_exposure_proxy"] = grouped["abs_contracts"] * pd.to_numeric(grouped["last_price"], errors="coerce").abs().fillna(0.0) * grouped["size"]
    grouped = grouped.sort_values("abs_exposure_proxy", ascending=False)
    dominant = grouped.iloc[0]
    return {
        "vt_symbols": "|".join(str(v) for v in grouped["vt_symbol"]),
        "dominant_vt_symbol": str(dominant["vt_symbol"]),
        "contracts": float(grouped["abs_contracts"].sum()),
        "exposure_proxy": float(grouped["abs_exposure_proxy"].sum()),
        "dominant_contracts": float(dominant["abs_contracts"]),
        "dominant_exposure_proxy": float(dominant["abs_exposure_proxy"]),
        "dominant_last_price": float(dominant["last_price"]),
    }


def _empty_snapshot() -> dict[str, Any]:
    return {
        "vt_symbols": "",
        "dominant_vt_symbol": "",
        "contracts": 0.0,
        "exposure_proxy": 0.0,
        "dominant_contracts": 0.0,
        "dominant_exposure_proxy": 0.0,
        "dominant_last_price": np.nan,
    }


def _episode_lots(c4_closed: pd.DataFrame, c9_closed: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    all_closed = pd.concat([c4_closed, c9_closed], ignore_index=True, sort=False)
    for episode in EPISODES:
        start = pd.Timestamp(episode["start"])
        end = pd.Timestamp(episode["end"])
        mask = (
            all_closed["product"].astype(str).eq(episode["product"])
            & all_closed["direction"].astype(str).eq(episode["direction"])
            & all_closed["entry_date"].le(end)
            & all_closed["exit_date"].ge(start)
        )
        part = all_closed[mask].copy()
        if part.empty:
            continue
        part["episode_id"] = episode["episode_id"]
        part["episode_product"] = episode["product"]
        part["episode_direction"] = episode["direction"]
        part["episode_start"] = start
        part["episode_anchor"] = pd.Timestamp(episode["anchor"])
        part["episode_end"] = end
        rows.append(part)
    if not rows:
        return pd.DataFrame()
    data = pd.concat(rows, ignore_index=True, sort=False)
    keep = [
        "episode_id",
        "arm_label",
        "lot_id",
        "open_trade_id",
        "close_trade_id",
        "vt_symbol",
        "product",
        "direction",
        "entry_date",
        "exit_date",
        "holding_calendar_days",
        "entry_price",
        "exit_price",
        "volume",
        "size",
        "realized_pnl",
        "risk_amount",
        "r_multiple",
        "exit_reason",
        "signal",
        "risk_mode",
        "target_risk_amount",
        "selected_volume",
        "stop_distance",
        "episode_start",
        "episode_anchor",
        "episode_end",
    ]
    return data[[column for column in keep if column in data.columns]].sort_values(
        ["episode_id", "arm_label", "entry_date", "vt_symbol", "lot_id"]
    ).reset_index(drop=True)


def _episode_lot_pairs(lots: pd.DataFrame) -> pd.DataFrame:
    if lots.empty:
        return pd.DataFrame()
    data = lots.copy()
    data["pair_key"] = (
        data["episode_id"].astype(str)
        + "|"
        + data["vt_symbol"].astype(str)
        + "|"
        + data["direction"].astype(str)
        + "|"
        + data["entry_date"].dt.strftime("%Y-%m-%d")
        + "|"
        + data["exit_date"].dt.strftime("%Y-%m-%d")
        + "|"
        + pd.to_numeric(data["entry_price"], errors="coerce").round(6).astype(str)
        + "|"
        + pd.to_numeric(data["exit_price"], errors="coerce").round(6).astype(str)
        + "|"
        + data["exit_reason"].astype(str)
    )
    rows: list[dict[str, Any]] = []
    for pair_key, group in data.groupby("pair_key", dropna=False):
        c4 = group[group["arm_label"].eq("C4")]
        c9 = group[group["arm_label"].eq("C9")]
        sample = group.iloc[0]
        row = {
            "pair_key": pair_key,
            "episode_id": sample["episode_id"],
            "vt_symbol": sample["vt_symbol"],
            "product": sample["product"],
            "direction": sample["direction"],
            "entry_date": sample["entry_date"],
            "exit_date": sample["exit_date"],
            "entry_price": sample["entry_price"],
            "exit_price": sample["exit_price"],
            "exit_reason": sample.get("exit_reason", ""),
            "c4_lots": int(len(c4)),
            "c9_lots": int(len(c9)),
            "volume_C4": float(pd.to_numeric(c4["volume"], errors="coerce").sum()),
            "volume_C9": float(pd.to_numeric(c9["volume"], errors="coerce").sum()),
            "risk_amount_C4": float(pd.to_numeric(c4["risk_amount"], errors="coerce").sum()),
            "risk_amount_C9": float(pd.to_numeric(c9["risk_amount"], errors="coerce").sum()),
            "realized_pnl_C4": float(pd.to_numeric(c4["realized_pnl"], errors="coerce").sum()),
            "realized_pnl_C9": float(pd.to_numeric(c9["realized_pnl"], errors="coerce").sum()),
        }
        row["volume_delta_C9_minus_C4"] = row["volume_C9"] - row["volume_C4"]
        row["risk_amount_delta_C9_minus_C4"] = row["risk_amount_C9"] - row["risk_amount_C4"]
        row["realized_pnl_delta_C9_minus_C4"] = row["realized_pnl_C9"] - row["realized_pnl_C4"]
        row["c9_to_c4_volume_ratio"] = row["volume_C9"] / row["volume_C4"] if row["volume_C4"] > 0 else np.nan
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["episode_id", "entry_date", "vt_symbol"]).reset_index(drop=True)


def _episode_daily(c4_trades: pd.DataFrame, c9_trades: pd.DataFrame, daily: pd.DataFrame, sizes: dict[str, float]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for episode in EPISODES:
        start = pd.Timestamp(episode["start"])
        end = pd.Timestamp(episode["end"])
        dates = daily[daily["date"].between(start, end, inclusive="both")]["date"].drop_duplicates().sort_values()
        for current_date in dates:
            c4_snap = _snapshot(c4_trades, current_date, episode["product"], episode["direction"], sizes)
            c9_snap = _snapshot(c9_trades, current_date, episode["product"], episode["direction"], sizes)
            curve_row = daily[daily["date"].eq(current_date)].iloc[0].to_dict()
            row = {
                "episode_id": episode["episode_id"],
                "product": episode["product"],
                "direction": episode["direction"],
                "date": current_date,
                "episode_start": start,
                "episode_anchor": pd.Timestamp(episode["anchor"]),
                "episode_end": end,
                "reason": episode["reason"],
            }
            for key, value in c4_snap.items():
                row[f"{key}_C4"] = value
            for key, value in c9_snap.items():
                row[f"{key}_C9"] = value
            row["contracts_delta_C9_minus_C4"] = row["contracts_C9"] - row["contracts_C4"]
            row["exposure_proxy_delta_C9_minus_C4"] = row["exposure_proxy_C9"] - row["exposure_proxy_C4"]
            for key, value in curve_row.items():
                if key != "date":
                    row[key] = value
            rows.append(row)
    return pd.DataFrame(rows)


def _episode_summary(daily: pd.DataFrame, lots: pd.DataFrame, pairs: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for episode in EPISODES:
        episode_id = episode["episode_id"]
        daily_part = daily[daily["episode_id"].astype(str).eq(episode_id)].copy()
        lot_part = lots[lots["episode_id"].astype(str).eq(episode_id)].copy() if not lots.empty else pd.DataFrame()
        pair_part = pairs[pairs["episode_id"].astype(str).eq(episode_id)].copy() if not pairs.empty else pd.DataFrame()
        if daily_part.empty:
            continue
        first = daily_part.sort_values("date").iloc[0]
        last = daily_part.sort_values("date").iloc[-1]
        c4_lots = lot_part[lot_part["arm_label"].eq("C4")]
        c9_lots = lot_part[lot_part["arm_label"].eq("C9")]
        rows.append(
            {
                "episode_id": episode_id,
                "product": episode["product"],
                "direction": episode["direction"],
                "start": episode["start"],
                "anchor": episode["anchor"],
                "end": episode["end"],
                "days": int(len(daily_part)),
                "equity_change_C4": float(last["account_equity_C4"] - first["account_equity_C4"]),
                "equity_change_C9": float(last["account_equity_C9"] - first["account_equity_C9"]),
                "equity_change_delta_C9_minus_C4": float(
                    (last["account_equity_C9"] - first["account_equity_C9"])
                    - (last["account_equity_C4"] - first["account_equity_C4"])
                ),
                "min_drawdown_C4": float(daily_part["drawdown_pct_C4"].min()),
                "min_drawdown_C9": float(daily_part["drawdown_pct_C9"].min()),
                "min_drawdown_delta_C9_minus_C4": float(daily_part["drawdown_pct_delta_C9_minus_C4"].min()),
                "max_broker10_C4": float(daily_part["broker10_margin_to_equity_pct_C4"].max()),
                "max_broker10_C9": float(daily_part["broker10_margin_to_equity_pct_C9"].max()),
                "max_broker10_delta_C9_minus_C4": float(daily_part["broker10_margin_to_equity_pct_delta_C9_minus_C4"].max()),
                "max_exposure_proxy_C4": float(daily_part["exposure_proxy_C4"].max()),
                "max_exposure_proxy_C9": float(daily_part["exposure_proxy_C9"].max()),
                "max_exposure_proxy_delta_C9_minus_C4": float(daily_part["exposure_proxy_delta_C9_minus_C4"].max()),
                "lots_C4": int(len(c4_lots)),
                "lots_C9": int(len(c9_lots)),
                "volume_C4": float(pd.to_numeric(c4_lots["volume"], errors="coerce").sum()) if not c4_lots.empty else 0.0,
                "volume_C9": float(pd.to_numeric(c9_lots["volume"], errors="coerce").sum()) if not c9_lots.empty else 0.0,
                "risk_amount_C4": float(pd.to_numeric(c4_lots["risk_amount"], errors="coerce").sum()) if not c4_lots.empty else 0.0,
                "risk_amount_C9": float(pd.to_numeric(c9_lots["risk_amount"], errors="coerce").sum()) if not c9_lots.empty else 0.0,
                "realized_pnl_C4": float(pd.to_numeric(c4_lots["realized_pnl"], errors="coerce").sum()) if not c4_lots.empty else 0.0,
                "realized_pnl_C9": float(pd.to_numeric(c9_lots["realized_pnl"], errors="coerce").sum()) if not c9_lots.empty else 0.0,
                "paired_lots": int(len(pair_part)),
                "paired_volume_delta_C9_minus_C4": float(pd.to_numeric(pair_part["volume_delta_C9_minus_C4"], errors="coerce").sum()) if not pair_part.empty else 0.0,
                "paired_risk_delta_C9_minus_C4": float(pd.to_numeric(pair_part["risk_amount_delta_C9_minus_C4"], errors="coerce").sum()) if not pair_part.empty else 0.0,
                "paired_pnl_delta_C9_minus_C4": float(pd.to_numeric(pair_part["realized_pnl_delta_C9_minus_C4"], errors="coerce").sum()) if not pair_part.empty else 0.0,
            }
        )
    return pd.DataFrame(rows)


def _weighted_avg(group: pd.DataFrame, value_col: str, weight_col: str = "volume") -> float:
    if group.empty:
        return np.nan
    values = pd.to_numeric(group[value_col], errors="coerce")
    weights = pd.to_numeric(group[weight_col], errors="coerce")
    mask = values.notna() & weights.gt(0)
    if not mask.any():
        return np.nan
    return float(np.average(values[mask], weights=weights[mask]))


def _minute_features(lots: pd.DataFrame, episode_daily: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if lots.empty:
        return pd.DataFrame(), pd.DataFrame()
    vt_symbols = set(lots["vt_symbol"].astype(str).dropna().unique())
    minute_bars = s825._load_minute_bars(vt_symbols)
    minute_by_symbol = s825._minute_groups(minute_bars)
    rows: list[dict[str, Any]] = []
    selected: list[dict[str, Any]] = []
    for episode in EPISODES:
        episode_id = episode["episode_id"]
        ep_lots = lots[lots["episode_id"].astype(str).eq(episode_id)].copy()
        if ep_lots.empty:
            continue
        daily_part = episode_daily[episode_daily["episode_id"].astype(str).eq(episode_id)].copy()
        dominant = ""
        if not daily_part.empty:
            row = daily_part.sort_values("exposure_proxy_C9", ascending=False).iloc[0]
            dominant = str(row.get("dominant_vt_symbol_C9") or row.get("dominant_vt_symbol_C4") or "")
        if not dominant:
            dominant = str(ep_lots["vt_symbol"].mode().iloc[0])
        dates = set(pd.to_datetime(ep_lots["entry_date"]).dropna().map(_normal_date))
        dates.update(pd.to_datetime(ep_lots["exit_date"]).dropna().map(_normal_date))
        dates.add(pd.Timestamp(episode["anchor"]))
        for day in sorted(d for d in dates if pd.notna(d)):
            day_bars = minute_by_symbol.get(dominant, pd.DataFrame())
            day_bars = (
                day_bars[day_bars["bar_date"].eq(day)].copy().sort_values("bar_datetime").reset_index(drop=True)
                if not day_bars.empty
                else pd.DataFrame()
            )
            same_symbol_lots = ep_lots[ep_lots["vt_symbol"].astype(str).eq(dominant)].copy()
            direction = episode["direction"]
            entry_avg_c4 = _weighted_avg(same_symbol_lots[same_symbol_lots["arm_label"].eq("C4")], "entry_price")
            entry_avg_c9 = _weighted_avg(same_symbol_lots[same_symbol_lots["arm_label"].eq("C9")], "entry_price")
            exit_avg_c4 = _weighted_avg(same_symbol_lots[same_symbol_lots["arm_label"].eq("C4")], "exit_price")
            exit_avg_c9 = _weighted_avg(same_symbol_lots[same_symbol_lots["arm_label"].eq("C9")], "exit_price")
            record = {
                "episode_id": episode_id,
                "vt_symbol": dominant,
                "date": day,
                "direction": direction,
                "minute_bars": int(len(day_bars)),
                "entry_avg_C4": entry_avg_c4,
                "entry_avg_C9": entry_avg_c9,
                "exit_avg_C4": exit_avg_c4,
                "exit_avg_C9": exit_avg_c9,
            }
            if not day_bars.empty:
                open_price = float(day_bars.iloc[0]["open"])
                high_price = float(pd.to_numeric(day_bars["high"], errors="coerce").max())
                low_price = float(pd.to_numeric(day_bars["low"], errors="coerce").min())
                close_price = float(day_bars.iloc[-1]["close"])
                sign = 1.0 if direction == "long" else -1.0
                if direction == "long":
                    favorable = (high_price / open_price - 1.0) * 100.0 if open_price > 0 else np.nan
                    adverse = (low_price / open_price - 1.0) * 100.0 if open_price > 0 else np.nan
                else:
                    favorable = (open_price / low_price - 1.0) * 100.0 if low_price > 0 else np.nan
                    adverse = (open_price / high_price - 1.0) * 100.0 if high_price > 0 else np.nan
                record.update(
                    {
                        "open": open_price,
                        "high": high_price,
                        "low": low_price,
                        "close": close_price,
                        "directional_close_return_pct": (close_price / open_price - 1.0) * 100.0 * sign
                        if open_price > 0
                        else np.nan,
                        "intraday_favorable_from_open_pct": favorable,
                        "intraday_adverse_from_open_pct": adverse,
                        "range_pct": (high_price / low_price - 1.0) * 100.0 if low_price > 0 else np.nan,
                    }
                )
            rows.append(record)
            selected.append(record)
    return pd.DataFrame(rows), pd.DataFrame(selected)


def _plot_path_chart(episode_daily: pd.DataFrame) -> None:
    if episode_daily.empty:
        return
    episodes = [episode["episode_id"] for episode in EPISODES if episode["episode_id"] in set(episode_daily["episode_id"])]
    fig, axes = plt.subplots(len(episodes), 3, figsize=(20, max(3.2, len(episodes) * 2.6)), constrained_layout=True)
    axes_arr = np.atleast_2d(axes)
    for row_index, episode_id in enumerate(episodes):
        data = episode_daily[episode_daily["episode_id"].astype(str).eq(episode_id)].sort_values("date")
        ax0, ax1, ax2 = axes_arr[row_index]
        ax0.plot(data["date"], data["account_equity_C4"], color="#16a34a", label="C4 equity")
        ax0.plot(data["date"], data["account_equity_C9"], color="#7c3aed", label="C9 equity")
        ax1.plot(data["date"], data["broker10_margin_to_equity_pct_C4"], color="#16a34a", label="C4 broker10")
        ax1.plot(data["date"], data["broker10_margin_to_equity_pct_C9"], color="#7c3aed", label="C9 broker10")
        ax2.plot(data["date"], data["exposure_proxy_C4"], color="#16a34a", label="C4 exposure")
        ax2.plot(data["date"], data["exposure_proxy_C9"], color="#7c3aed", label="C9 exposure")
        ax0.set_title(f"{episode_id} equity")
        ax1.set_title("broker10")
        ax2.set_title("product-direction exposure proxy")
        for ax in (ax0, ax1, ax2):
            ax.grid(True, alpha=0.25)
            ax.legend(loc="best", fontsize=7)
            ax.tick_params(axis="x", labelrotation=25)
    fig.savefig(PATH_CHART_PATH, dpi=150)
    plt.close(fig)


def _plot_episode_atlas(lots: pd.DataFrame, minute_features: pd.DataFrame) -> tuple[list[Path], pd.DataFrame]:
    if lots.empty or minute_features.empty:
        return [], pd.DataFrame()
    vt_symbols = set(minute_features["vt_symbol"].astype(str).dropna().unique())
    minute_bars = s825._load_minute_bars(vt_symbols)
    minute_by_symbol = s825._minute_groups(minute_bars)
    paths: list[Path] = []
    manifest: list[dict[str, Any]] = []
    for episode in EPISODES:
        episode_id = episode["episode_id"]
        features = minute_features[minute_features["episode_id"].astype(str).eq(episode_id)].copy()
        if features.empty:
            continue
        features = features.sort_values("date").drop_duplicates(["vt_symbol", "date"]).head(4)
        fig, axes = plt.subplots(len(features), 1, figsize=(18, max(4.0, len(features) * 3.2)), constrained_layout=True)
        axes_list = list(np.atleast_1d(axes))
        for ax, (_, row) in zip(axes_list, features.iterrows(), strict=False):
            vt_symbol = str(row["vt_symbol"])
            day = _normal_date(row["date"])
            bars = minute_by_symbol.get(vt_symbol, pd.DataFrame())
            bars = (
                bars[bars["bar_date"].eq(day)].copy().sort_values("bar_datetime").head(320).reset_index(drop=True)
                if not bars.empty
                else pd.DataFrame()
            )
            if bars.empty:
                ax.axis("off")
                ax.text(0.5, 0.5, f"missing minute bars {vt_symbol} {day:%Y-%m-%d}", ha="center", va="center")
            else:
                s825._plot_candles(ax, bars)
                for value, color, style, label in [
                    (_safe_float(row.get("entry_avg_C4")), "#16a34a", "-", "C4 entry avg"),
                    (_safe_float(row.get("entry_avg_C9")), "#7c3aed", "-", "C9 entry avg"),
                    (_safe_float(row.get("exit_avg_C4")), "#16a34a", "--", "C4 exit avg"),
                    (_safe_float(row.get("exit_avg_C9")), "#7c3aed", "--", "C9 exit avg"),
                ]:
                    if np.isfinite(value):
                        ax.axhline(value, color=color, linestyle=style, linewidth=0.9, label=label)
                ticks = np.linspace(0, len(bars) - 1, num=min(8, len(bars)), dtype=int)
                ax.set_xticks(ticks)
                ax.set_xticklabels([pd.Timestamp(bars.loc[pos, "bar_datetime"]).strftime("%H:%M") for pos in ticks], fontsize=7)
                handles, labels = ax.get_legend_handles_labels()
                if handles:
                    dedup = dict(zip(labels, handles))
                    ax.legend(dedup.values(), dedup.keys(), loc="best", fontsize=7)
                ax.grid(True, alpha=0.18)
            title = (
                f"{episode_id} | {vt_symbol} {episode['direction']} {day:%Y-%m-%d} "
                f"dir_close={_safe_float(row.get('directional_close_return_pct')):.2f}% "
                f"adv={_safe_float(row.get('intraday_adverse_from_open_pct')):.2f}% "
                f"fav={_safe_float(row.get('intraday_favorable_from_open_pct')):.2f}%"
            )
            ax.set_title(title, loc="left", fontsize=8.3)
            manifest.append(
                {
                    "episode_id": episode_id,
                    "vt_symbol": vt_symbol,
                    "date": day.strftime("%Y-%m-%d"),
                    "minute_bars": int(row.get("minute_bars", 0)),
                    "directional_close_return_pct": _safe_float(row.get("directional_close_return_pct")),
                    "intraday_adverse_from_open_pct": _safe_float(row.get("intraday_adverse_from_open_pct")),
                    "intraday_favorable_from_open_pct": _safe_float(row.get("intraday_favorable_from_open_pct")),
                }
            )
        fig.suptitle(f"Stage849 pressure episode minute atlas: {episode_id}", fontsize=13)
        path = Path(str(ATLAS_TEMPLATE).format(episode_id=episode_id))
        fig.savefig(path, dpi=150)
        plt.close(fig)
        paths.append(path)
    return paths, pd.DataFrame(manifest)


def _write_report(
    episode_summary: pd.DataFrame,
    lot_pairs: pd.DataFrame,
    minute_features: pd.DataFrame,
    atlas_paths: list[Path],
) -> None:
    top_pairs = lot_pairs.sort_values("realized_pnl_delta_C9_minus_C4").head(20) if not lot_pairs.empty else pd.DataFrame()
    minute_display = minute_features.sort_values(
        ["episode_id", "date"], ascending=[True, True]
    ).head(40) if not minute_features.empty else pd.DataFrame()
    lines = [
        "# Stage849 Pressure Path Forensics",
        "",
        f"- line_id: `{LINE_ID}`",
        f"- model_tag: `{MODEL_TAG}`",
        f"- source candidate: `{stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION}`",
        "- Scope: read-only pressure-segment path attribution. No strategy rule, no parameter search, no CTP/order path.",
        "",
        "## External Reference Judgment",
        "",
        "- CME risk management and CFTC stop-loss education support treating stops as one part of risk control, not as a substitute for position sizing and margin discipline.",
        "- vn.py is used only as a deterministic backtesting/output reference; no external alpha rule is copied.",
        "- Judgment: Stage849 should inspect whether the Stage848 weak path is same-timing-larger-size risk, not invent another entry-day R multiple.",
        "",
        "## Episode Summary",
        "",
        _md_table(episode_summary, max_rows=20),
        "",
        "## Paired Lot Delta",
        "",
        _md_table(top_pairs, max_rows=20),
        "",
        "## Minute Features",
        "",
        _md_table(minute_display, max_rows=40),
        "",
        "## Charts",
        "",
        f"- episode path chart: `{PATH_CHART_PATH}`",
        *[f"- episode atlas: `{path}`" for path in atlas_paths],
        "",
        "## Judgment",
        "",
        "- This is diagnostic only. It is not a C10/C11 proposal.",
        "- If C9 and C4 mostly share the same contracts, dates, entry prices, exit prices, and exit reasons, the weak path is primarily sizing/exposure pressure.",
        "- A next rule shape, if any, must be account/holding-state based and low-degree; product-name or 2022-only filters would be overfit.",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    c4_closed = _prepare_closed(C4_CLOSED_PATH, C4_ARM)
    c9_closed = _prepare_closed(C9_CLOSED_PATH, C9_ARM)
    c4_trades = _prepare_trades(C4_TRADES_PATH, C4_ARM)
    c9_trades = _prepare_trades(C9_TRADES_PATH, C9_ARM)
    daily = _prepare_stage848_daily()
    sizes = _size_map(c4_closed, c9_closed)

    lots = _episode_lots(c4_closed, c9_closed)
    lot_pairs = _episode_lot_pairs(lots)
    episode_daily = _episode_daily(c4_trades, c9_trades, daily, sizes)
    episode_summary = _episode_summary(episode_daily, lots, lot_pairs)
    minute_features, _ = _minute_features(lots, episode_daily)
    _plot_path_chart(episode_daily)
    atlas_paths, atlas_manifest = _plot_episode_atlas(lots, minute_features)
    _write_report(episode_summary, lot_pairs, minute_features, atlas_paths)

    episode_daily.to_csv(EPISODE_DAILY_PATH, index=False, encoding="utf-8-sig")
    lots.to_csv(EPISODE_LOTS_PATH, index=False, encoding="utf-8-sig")
    lot_pairs.to_csv(EPISODE_LOT_PAIRS_PATH, index=False, encoding="utf-8-sig")
    episode_summary.to_csv(EPISODE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    minute_features.to_csv(MINUTE_FEATURES_PATH, index=False, encoding="utf-8-sig")
    atlas_manifest.to_csv(ATLAS_MANIFEST_PATH, index=False, encoding="utf-8-sig")

    total_pair_pnl_delta = float(pd.to_numeric(lot_pairs.get("realized_pnl_delta_C9_minus_C4"), errors="coerce").sum()) if not lot_pairs.empty else 0.0
    total_pair_risk_delta = float(pd.to_numeric(lot_pairs.get("risk_amount_delta_C9_minus_C4"), errors="coerce").sum()) if not lot_pairs.empty else 0.0
    total_pair_volume_delta = float(pd.to_numeric(lot_pairs.get("volume_delta_C9_minus_C4"), errors="coerce").sum()) if not lot_pairs.empty else 0.0
    same_timing_pairs = int(
        len(
            lot_pairs[
                lot_pairs["c4_lots"].gt(0)
                & lot_pairs["c9_lots"].gt(0)
                & pd.to_numeric(lot_pairs["volume_delta_C9_minus_C4"], errors="coerce").gt(0)
            ]
        )
    ) if not lot_pairs.empty else 0
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "source_candidate": stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION,
        "strategy_changed": False,
        "ctp_connected": False,
        "order_api_called": False,
        "formal_ab_triggered": False,
        "decision": "stage849_pressure_path_forensics_no_rule_yet",
        "episodes": EPISODES,
        "episode_count": int(len(EPISODES)),
        "paired_lot_count": int(len(lot_pairs)),
        "same_timing_larger_c9_pairs": same_timing_pairs,
        "total_pair_pnl_delta_C9_minus_C4": total_pair_pnl_delta,
        "total_pair_risk_delta_C9_minus_C4": total_pair_risk_delta,
        "total_pair_volume_delta_C9_minus_C4": total_pair_volume_delta,
        "outputs": {
            "episode_daily": str(EPISODE_DAILY_PATH),
            "episode_lots": str(EPISODE_LOTS_PATH),
            "episode_lot_pairs": str(EPISODE_LOT_PAIRS_PATH),
            "episode_summary": str(EPISODE_SUMMARY_PATH),
            "minute_features": str(MINUTE_FEATURES_PATH),
            "report": str(REPORT_PATH),
            "path_chart": str(PATH_CHART_PATH),
            "atlas_manifest": str(ATLAS_MANIFEST_PATH),
            "atlas_paths": [str(path) for path in atlas_paths],
        },
        "overfit_reflection": (
            "No. Stage849 replays pressure episodes predeclared by Stage848/LINE.md and does not select new thresholds, "
            "product filters, or strategy parameters."
        ),
        "continue_value_reflection": (
            "Yes. The evidence can distinguish same-timing-larger-size risk from entry-day stop/retry failure and guide whether "
            "a low-degree holding-state rule is worth testing later."
        ),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    DECISION_PATH.write_text(json.dumps(decision, ensure_ascii=False, indent=2, default=_json_safe) + "\n", encoding="utf-8")
    print(json.dumps(decision, ensure_ascii=False, indent=2, default=_json_safe))


if __name__ == "__main__":
    main()
