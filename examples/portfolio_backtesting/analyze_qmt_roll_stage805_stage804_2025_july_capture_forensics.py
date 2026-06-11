from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from pathlib import Path
from typing import Any
import json
import os
import re

import pandas as pd

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage772_am40_80_120_oi_monthly as s772
import analyze_qmt_roll_stage778_stage777_2022_drawdown_forensics as s778
import analyze_qmt_roll_stage804_stage777_long_tighter_initial_stop_yearly as s804


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage805_stage804_2025_july_capture_forensics_v1"
OUTPUT_PREFIX = "qmt_roll_stage805_stage804_2025_july_capture_forensics"
LINE_ID = "futures_trend_2019_data_extension"

STARTS = tuple(pd.date_range("2018-01-01", "2025-01-01", freq="YS"))
WINDOW_START = pd.Timestamp("2025-06-16")
WINDOW_END = pd.Timestamp("2025-07-25")
ENTRY_LOOKBACK_START = pd.Timestamp("2025-05-01")
SNAPSHOT_DATES = (pd.Timestamp("2025-07-01"), pd.Timestamp("2025-07-25"))
# AI eligibility files are shared by the profile builders; keep this forensic
# replay serial by default to avoid parallel read/write races.
MAX_WORKERS = max(1, min(4, int(os.environ.get("STAGE805_MAX_WORKERS", "1"))))

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
PRODUCT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_contribution_{MODEL_TAG}.csv"
SNAPSHOT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_active_positions_{MODEL_TAG}.csv"
ENTRY_RISK_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_window_{MODEL_TAG}.csv"
TRADES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_window_{MODEL_TAG}.csv"
SKIP_REASON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_candidate_skip_reasons_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _product_from_vt_symbol(vt_symbol: Any) -> str:
    text = str(vt_symbol or "")
    if "." not in text:
        return text
    symbol, exchange = text.split(".", 1)
    product = re.sub(r"\d+$", "", symbol)
    return f"{product}.{exchange}"


def _year_start_text(start: pd.Timestamp) -> str:
    return pd.Timestamp(start).strftime("%Y-%m")


def _base_profile(metadata: dict[str, Any], start: pd.Timestamp) -> dict[str, Any]:
    base = next(profile for profile in s772._profile_specs(metadata) if profile["profile"] == "oi_restore_am40")
    spec = base["spec"]
    start_text = _year_start_text(start)
    capital = replace(
        spec.capital,
        variant=f"stage805_a777_{start_text.replace('-', '_')}",
        label=f"Stage805 A777 baseline {start_text}",
        note=f"{spec.capital.note} | Stage805 July 2025 capture forensics baseline.",
    )
    profile = dict(base)
    profile["profile"] = "stage805_a777_baseline"
    profile["spec"] = replace(spec, capital=capital, profile=profile["profile"])
    profile["note"] = "Stage777 baseline rerun for July 2025 capture forensics."
    return profile


def _arm_profile(arm: str, metadata: dict[str, Any], start: pd.Timestamp) -> dict[str, Any]:
    if arm == "A777":
        return _base_profile(metadata, start)
    if arm == "C804":
        profile = s804._profile(metadata, start)
        spec = profile["spec"]
        profile = dict(profile)
        profile["profile"] = "stage805_c804_long_tighter_stop"
        profile["spec"] = replace(spec, profile=profile["profile"])
        profile["note"] = "Stage804 long-only tighter initial stop rerun for July 2025 capture forensics."
        return profile
    raise ValueError(f"unknown arm: {arm}")


def _window_summary(combined: pd.DataFrame, start: pd.Timestamp, arm: str) -> dict[str, Any]:
    daily = combined.copy()
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
    win = daily[(daily["date"] >= WINDOW_START) & (daily["date"] <= WINDOW_END)].copy()
    if win.empty:
        return {
            "start_month": _year_start_text(start),
            "arm": arm,
            "window_pnl": 0.0,
            "window_trade_count": 0,
            "window_start_equity": None,
            "window_end_equity": None,
            "window_return_on_start_equity_pct": None,
            "window_max_broker10_margin_pct": None,
        }
    start_equity = float(win["account_equity"].iloc[0] - win["net_pnl"].iloc[0])
    pnl = float(pd.to_numeric(win["net_pnl"], errors="coerce").fillna(0.0).sum())
    return {
        "start_month": _year_start_text(start),
        "arm": arm,
        "window_pnl": pnl,
        "window_trade_count": int(pd.to_numeric(win.get("trade_count", 0), errors="coerce").fillna(0).sum()),
        "window_start_equity": start_equity,
        "window_end_equity": float(win["account_equity"].iloc[-1]),
        "window_return_on_start_equity_pct": pnl / start_equity * 100 if start_equity else None,
        "window_max_broker10_margin_pct": float(
            pd.to_numeric(win.get("broker10_margin_to_equity_pct", 0), errors="coerce").fillna(0).max()
        ),
    }


def _positions_window(positions: pd.DataFrame, start: pd.Timestamp, arm: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    if positions.empty:
        return pd.DataFrame(), pd.DataFrame()
    pos = positions.copy()
    pos["date"] = pd.to_datetime(pos["date"], errors="coerce").dt.normalize()
    pos["product_vt_symbol"] = pos["vt_symbol"].map(_product_from_vt_symbol)
    win = pos[(pos["date"] >= WINDOW_START) & (pos["date"] <= WINDOW_END)].copy()
    if win.empty:
        return pd.DataFrame(), pd.DataFrame()

    for column in ["net_pnl", "trade_count", "slippage", "end_pos", "start_pos"]:
        win[column] = pd.to_numeric(win.get(column, 0), errors="coerce").fillna(0.0)
    product = (
        win.groupby(["product_vt_symbol"], as_index=False)
        .agg(
            net_pnl=("net_pnl", "sum"),
            trade_count=("trade_count", "sum"),
            slippage=("slippage", "sum"),
            max_abs_pos=("end_pos", lambda series: float(series.abs().max())),
            active_days=("end_pos", lambda series: int(series.ne(0).sum())),
        )
        .sort_values("net_pnl", ascending=False)
    )
    product.insert(0, "arm", arm)
    product.insert(0, "start_month", _year_start_text(start))

    active = win[win["end_pos"].ne(0)].copy()
    snapshots = active[active["date"].isin(SNAPSHOT_DATES)].copy()
    keep_cols = [
        "date",
        "product_vt_symbol",
        "vt_symbol",
        "start_pos",
        "end_pos",
        "close_price",
        "net_pnl",
        "holding_pnl",
        "trading_pnl",
    ]
    for col in keep_cols:
        if col not in snapshots.columns:
            snapshots[col] = None
    snapshots = snapshots[keep_cols].sort_values(["date", "product_vt_symbol", "vt_symbol"])
    snapshots.insert(0, "arm", arm)
    snapshots.insert(0, "start_month", _year_start_text(start))
    return product, snapshots


def _entry_risk_window(entry_risk: pd.DataFrame, start: pd.Timestamp, arm: str) -> pd.DataFrame:
    if entry_risk.empty:
        return pd.DataFrame()
    frame = entry_risk.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame[(frame["date"] >= ENTRY_LOOKBACK_START) & (frame["date"] <= WINDOW_END)].copy()
    if frame.empty:
        return pd.DataFrame()
    keep_cols = [
        "date",
        "product_vt_symbol",
        "contract_vt_symbol",
        "direction",
        "signal",
        "layer_kind",
        "risk_mode",
        "risk_ratio",
        "risk_multiplier",
        "oi_price_confirm_risk_restore_applied",
        "oi_price_confirm_passed",
        "entry_price",
        "stop_price",
        "stop_distance",
        "risk_per_contract",
        "target_risk_amount",
        "contracts_by_risk",
        "contracts_by_margin",
        "contracts_by_single_trade_cap",
        "selected_volume",
        "selected_volume_ungated",
        "same_direction_correlation_gate_weight",
        "same_direction_correlation_active_count",
        "same_direction_correlation_max_corr",
        "portfolio_drawdown_pct",
        "loss_streak",
    ]
    for col in keep_cols:
        if col not in frame.columns:
            frame[col] = None
    frame = frame[keep_cols].sort_values(["date", "product_vt_symbol", "contract_vt_symbol"])
    frame.insert(0, "arm", arm)
    frame.insert(0, "start_month", _year_start_text(start))
    return frame


def _trades_window(trades: pd.DataFrame, start: pd.Timestamp, arm: str) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    frame = trades.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame[(frame["date"] >= ENTRY_LOOKBACK_START) & (frame["date"] <= WINDOW_END)].copy()
    if frame.empty:
        return pd.DataFrame()
    frame["product_vt_symbol"] = frame["vt_symbol"].map(_product_from_vt_symbol)
    keep_cols = [
        "date",
        "product_vt_symbol",
        "vt_symbol",
        "direction",
        "offset",
        "price",
        "volume",
        "signed_volume",
        "exit_reason",
    ]
    for col in keep_cols:
        if col not in frame.columns:
            frame[col] = None
    frame = frame[keep_cols].sort_values(["date", "product_vt_symbol", "vt_symbol", "offset"])
    frame.insert(0, "arm", arm)
    frame.insert(0, "start_month", _year_start_text(start))
    return frame


def _candidate_skip_reasons(candidates: pd.DataFrame, start: pd.Timestamp, arm: str) -> pd.DataFrame:
    if candidates.empty:
        return pd.DataFrame()
    frame = candidates.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame[(frame["date"] >= ENTRY_LOOKBACK_START) & (frame["date"] <= WINDOW_END)].copy()
    if frame.empty:
        return pd.DataFrame()
    reason_col = "skip_reason" if "skip_reason" in frame.columns else "reason"
    if reason_col not in frame.columns:
        frame[reason_col] = "unknown"
    product_col = "product_vt_symbol" if "product_vt_symbol" in frame.columns else "contract_vt_symbol"
    if product_col not in frame.columns:
        frame[product_col] = ""
    out = (
        frame.groupby([reason_col, product_col], dropna=False)
        .size()
        .reset_index(name="count")
        .rename(columns={reason_col: "skip_reason", product_col: "product_vt_symbol"})
        .sort_values("count", ascending=False)
    )
    out.insert(0, "arm", arm)
    out.insert(0, "start_month", _year_start_text(start))
    return out


def _run_one(start_text: str, arm: str) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    start = pd.Timestamp(start_text).normalize()
    metadata = s513._metadata()
    profile = _arm_profile(arm, metadata, start)
    combined, frames = s778._run_profile(
        profile=profile,
        start=start,
        metadata=metadata,
        base_c3_overrides=dict(s513._c3_overrides(pd.Timestamp("2018-01-01").to_pydatetime())),
    )
    summary = _window_summary(combined, start, arm)
    product, snapshots = _positions_window(frames.get("positions", pd.DataFrame()), start, arm)
    entry_risk = _entry_risk_window(frames.get("entry_risk", pd.DataFrame()), start, arm)
    trades = _trades_window(frames.get("trades", pd.DataFrame()), start, arm)
    skips = _candidate_skip_reasons(frames.get("entry_candidates", pd.DataFrame()), start, arm)
    return summary, product, snapshots, entry_risk, trades, skips


def _write_report(summary: pd.DataFrame, product: pd.DataFrame, entry_risk: pd.DataFrame) -> dict[str, Any]:
    pivot = summary.pivot(index="start_month", columns="arm", values="window_pnl").reset_index()
    if {"A777", "C804"}.issubset(pivot.columns):
        pivot["c804_minus_a777"] = pivot["C804"] - pivot["A777"]
    else:
        pivot["c804_minus_a777"] = None

    top_products = product.sort_values(["start_month", "arm", "net_pnl"], ascending=[True, True, False])
    top_products = top_products.groupby(["start_month", "arm"]).head(6).reset_index(drop=True)

    entry_count = (
        entry_risk.groupby(["start_month", "arm", "product_vt_symbol", "direction"], dropna=False)
        .agg(
            entries=("selected_volume", "count"),
            selected_volume=("selected_volume", "sum"),
            median_stop_distance=("stop_distance", "median"),
            median_contracts_by_risk=("contracts_by_risk", "median"),
            oi_applied_count=("oi_price_confirm_risk_restore_applied", "sum"),
        )
        .reset_index()
        .sort_values(["start_month", "arm", "selected_volume"], ascending=[True, True, False])
    )
    entry_count = entry_count.groupby(["start_month", "arm"]).head(8).reset_index(drop=True)

    decision = {
        "stage": "Stage805",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "window": f"{WINDOW_START.date()}->{WINDOW_END.date()}",
        "summary": {
            "best_c804_minus_a777": float(pd.to_numeric(pivot["c804_minus_a777"], errors="coerce").max()),
            "worst_c804_minus_a777": float(pd.to_numeric(pivot["c804_minus_a777"], errors="coerce").min()),
            "c804_window_pnl_win_count": int(pd.to_numeric(pivot["c804_minus_a777"], errors="coerce").gt(0).sum()),
            "sample_count": int(len(pivot)),
        },
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "product_contribution": str(PRODUCT_PATH),
            "active_positions": str(SNAPSHOT_PATH),
            "entry_risk_window": str(ENTRY_RISK_PATH),
            "trades_window": str(TRADES_PATH),
            "skip_reasons": str(SKIP_REASON_PATH),
            "report": str(REPORT_PATH),
        },
    }
    lines = [
        "# Stage805 Stage804 2025-07 行情捕获归因",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 窗口：`{WINDOW_START.date()} -> {WINDOW_END.date()}`",
        "- A：Stage777 baseline 复跑；C：Stage804 多头更紧初始止损复跑。",
        "",
        "## Window PnL",
        "",
        _md_table(pivot, max_rows=20),
        "",
        "## Top Product Contributions",
        "",
        _md_table(top_products, max_rows=80),
        "",
        "## Entry Risk Summary",
        "",
        _md_table(entry_count, max_rows=80),
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return decision


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    tasks = [(start.strftime("%Y-%m-%d"), arm) for start in STARTS for arm in ("A777", "C804")]
    summaries: list[dict[str, Any]] = []
    products: list[pd.DataFrame] = []
    snapshots: list[pd.DataFrame] = []
    entry_risks: list[pd.DataFrame] = []
    trades: list[pd.DataFrame] = []
    skips: list[pd.DataFrame] = []

    print(f"[stage805] launching {len(tasks)} runs workers={MAX_WORKERS}", flush=True)
    if MAX_WORKERS == 1:
        iterator = []
        for task in tasks:
            print(f"[stage805] running {task}", flush=True)
            iterator.append((task, _run_one(*task)))
    else:
        iterator = []
        with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_map = {executor.submit(_run_one, *task): task for task in tasks}
            for idx, future in enumerate(as_completed(future_map), start=1):
                task = future_map[future]
                iterator.append((task, future.result()))
                print(f"[stage805] completed {idx}/{len(tasks)} {task}", flush=True)

    for _task, result in iterator:
        summary, product, snapshot, entry_risk, trade, skip = result
        summaries.append(summary)
        if not product.empty:
            products.append(product)
        if not snapshot.empty:
            snapshots.append(snapshot)
        if not entry_risk.empty:
            entry_risks.append(entry_risk)
        if not trade.empty:
            trades.append(trade)
        if not skip.empty:
            skips.append(skip)

    summary_df = pd.DataFrame(summaries).sort_values(["start_month", "arm"]).reset_index(drop=True)
    product_df = pd.concat(products, ignore_index=True, sort=False) if products else pd.DataFrame()
    snapshot_df = pd.concat(snapshots, ignore_index=True, sort=False) if snapshots else pd.DataFrame()
    entry_risk_df = pd.concat(entry_risks, ignore_index=True, sort=False) if entry_risks else pd.DataFrame()
    trades_df = pd.concat(trades, ignore_index=True, sort=False) if trades else pd.DataFrame()
    skip_df = pd.concat(skips, ignore_index=True, sort=False) if skips else pd.DataFrame()

    summary_df.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    product_df.to_csv(PRODUCT_PATH, index=False, encoding="utf-8-sig")
    snapshot_df.to_csv(SNAPSHOT_PATH, index=False, encoding="utf-8-sig")
    entry_risk_df.to_csv(ENTRY_RISK_PATH, index=False, encoding="utf-8-sig")
    trades_df.to_csv(TRADES_PATH, index=False, encoding="utf-8-sig")
    skip_df.to_csv(SKIP_REASON_PATH, index=False, encoding="utf-8-sig")
    decision = _write_report(summary_df, product_df, entry_risk_df)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(summary_df.to_string(index=False))


if __name__ == "__main__":
    main()
