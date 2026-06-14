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
import analyze_qmt_roll_stage752_theoretical_winner_kline_atlas as s752
import analyze_qmt_roll_stage815_stage813_top40_loss_kline_atlas as s815
import analyze_qmt_roll_stage825_stage819_intraday_rule_forensics as s825
import qmt_roll_official_candidate_stage819_30w_config as stage819_cfg


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage837"
MODEL_TAG = "stage837_stage832_holding_pressure_forensics_v1"
OUTPUT_PREFIX = "qmt_roll_stage837_stage832_holding_pressure_forensics"

STAGE832_PREFIX = "qmt_roll_stage832_stage831_c4_stress_forensics"
STAGE832_TAG = "stage832_stage831_c4_stress_forensics_v1"

BASE_ARM = "stage827_stage819_baseline"
C4_ARM = "stage830_stage819_c2_broker10_100_cap"
BROKER10_CURVE_MULTIPLIER = 1.10
BROKER100 = 100.0
DD50 = -50.0
HORIZONS = [1, 3, 5, 10, 20]
TOP_CONTRACTS_PER_ANCHOR = 3
MAX_ATLAS_ROWS = 12

STRESS_DAYS_PATH = OUTPUT_DIR / f"{STAGE832_PREFIX}_stress_days_{STAGE832_TAG}.csv"
ANCHORS_PATH = OUTPUT_DIR / f"{STAGE832_PREFIX}_stress_anchors_{STAGE832_TAG}.csv"
PRODUCT_MARGIN_PATH = OUTPUT_DIR / f"{STAGE832_PREFIX}_product_margin_{STAGE832_TAG}.csv"
CONTRACT_MARGIN_PATH = OUTPUT_DIR / f"{STAGE832_PREFIX}_contract_margin_{STAGE832_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{STAGE832_PREFIX}_curves_{STAGE832_TAG}.csv"

PRESSURE_DECOMP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pressure_decomposition_{MODEL_TAG}.csv"
PRE_ANCHOR_CLUSTER_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pre_anchor_cluster_{MODEL_TAG}.csv"
STRESS_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stress_summary_{MODEL_TAG}.csv"
MINUTE_FEATURES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_minute_pressure_features_{MODEL_TAG}.csv"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
DECOMP_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decomposition_chart_{MODEL_TAG}.png"
CLUSTER_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cluster_chart_{MODEL_TAG}.png"
DAILY_ATLAS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_pressure_atlas_{MODEL_TAG}.png"
MINUTE_ATLAS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_minute_pressure_atlas_{MODEL_TAG}.png"


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


def _prepare_inputs() -> dict[str, pd.DataFrame]:
    stress_days = _load_csv(STRESS_DAYS_PATH)
    anchors = _load_csv(ANCHORS_PATH)
    product_margin = _load_csv(PRODUCT_MARGIN_PATH)
    contract_margin = _load_csv(CONTRACT_MARGIN_PATH)
    curves = _load_csv(CURVES_PATH)
    for frame in [stress_days, anchors, product_margin, contract_margin, curves]:
        if "date" in frame.columns:
            frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    for frame in [product_margin, contract_margin]:
        for column in [
            "c3_margin_exact",
            "abs_end_pos",
            "holding_pnl",
            "trading_pnl",
            "net_pnl",
            "close_price",
            "pre_close",
            "end_pos",
        ]:
            if column in frame.columns:
                frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)
    for frame in [stress_days, anchors, curves]:
        for column in frame.columns:
            if column.endswith("_A") or column.endswith("_C4") or column.endswith("_delta_C4_minus_A"):
                frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return {
        "stress_days": stress_days,
        "anchors": anchors,
        "product_margin": product_margin,
        "contract_margin": contract_margin,
        "curves": curves,
    }


def _calendar(curves: pd.DataFrame) -> pd.DataFrame:
    dates = pd.to_datetime(curves["date"], errors="coerce").dt.normalize().dropna().drop_duplicates().sort_values()
    return pd.DataFrame({"date": dates.reset_index(drop=True), "td_index": np.arange(len(dates), dtype=int)})


def _anchor_margin_frame(product_margin: pd.DataFrame, start_month: str, date: pd.Timestamp, arm: str) -> pd.DataFrame:
    return product_margin[
        product_margin["start_month"].astype(str).eq(str(start_month))
        & product_margin["arm"].astype(str).eq(arm)
        & product_margin["date"].eq(date)
    ].copy()


def _pressure_decomposition(anchors: pd.DataFrame, product_margin: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for anchor in anchors.to_dict("records"):
        start_month = str(anchor["start_month"])
        date = pd.Timestamp(anchor["date"]).normalize()
        c4 = _anchor_margin_frame(product_margin, start_month, date, C4_ARM)
        a = _anchor_margin_frame(product_margin, start_month, date, BASE_ARM)
        c4_margin = float(pd.to_numeric(c4["c3_margin_exact"], errors="coerce").sum()) if not c4.empty else 0.0
        a_margin = float(pd.to_numeric(a["c3_margin_exact"], errors="coerce").sum()) if not a.empty else 0.0
        c4_equity = _safe_float(anchor.get("account_equity_C4"))
        a_equity = _safe_float(anchor.get("account_equity_A"))
        c4_exact_ratio = BROKER10_CURVE_MULTIPLIER * c4_margin / c4_equity * 100.0 if c4_equity > 0 else np.nan
        a_exact_ratio = BROKER10_CURVE_MULTIPLIER * a_margin / a_equity * 100.0 if a_equity > 0 else np.nan
        numerator_effect_pp = BROKER10_CURVE_MULTIPLIER * (c4_margin - a_margin) / a_equity * 100.0 if a_equity > 0 else np.nan
        denominator_effect_pp = (
            BROKER10_CURVE_MULTIPLIER * c4_margin * (1.0 / c4_equity - 1.0 / a_equity) * 100.0
            if c4_equity > 0 and a_equity > 0
            else np.nan
        )
        total = c4["c3_margin_exact"].sum() if not c4.empty else 0.0
        by_product = c4.groupby(["product_vt_symbol", "position_direction"], as_index=False)["c3_margin_exact"].sum()
        by_product.sort_values("c3_margin_exact", ascending=False, inplace=True)
        by_direction = c4.groupby("position_direction", as_index=False)["c3_margin_exact"].sum()
        long_margin = float(by_direction[by_direction["position_direction"].eq("long")]["c3_margin_exact"].sum())
        short_margin = float(by_direction[by_direction["position_direction"].eq("short")]["c3_margin_exact"].sum())
        top1_share = float(by_product["c3_margin_exact"].head(1).sum() / total * 100.0) if total > 0 else 0.0
        top3_share = float(by_product["c3_margin_exact"].head(3).sum() / total * 100.0) if total > 0 else 0.0
        top_product = ""
        if not by_product.empty:
            first = by_product.iloc[0]
            top_product = f"{first['product_vt_symbol']} {first['position_direction']}"
        rows.append(
            {
                "start_month": start_month,
                "date": date,
                "anchor_type": anchor["anchor_type"],
                "account_equity_A": a_equity,
                "account_equity_C4": c4_equity,
                "equity_delta_C4_minus_A": c4_equity - a_equity,
                "drawdown_pct_A": _safe_float(anchor.get("drawdown_pct_A")),
                "drawdown_pct_C4": _safe_float(anchor.get("drawdown_pct_C4")),
                "actual_broker10_pct_A": _safe_float(anchor.get("broker10_margin_to_equity_pct_A")),
                "actual_broker10_pct_C4": _safe_float(anchor.get("broker10_margin_to_equity_pct_C4")),
                "exact_broker10_pct_A": a_exact_ratio,
                "exact_broker10_pct_C4": c4_exact_ratio,
                "exact_broker10_delta_pp": c4_exact_ratio - a_exact_ratio,
                "numerator_margin_effect_pp": numerator_effect_pp,
                "denominator_equity_effect_pp": denominator_effect_pp,
                "c4_margin": c4_margin,
                "a_margin": a_margin,
                "margin_delta_C4_minus_A": c4_margin - a_margin,
                "top_product_direction": top_product,
                "product_direction_count": int(len(by_product)),
                "top1_margin_share_pct": top1_share,
                "top3_margin_share_pct": top3_share,
                "short_margin_share_pct": short_margin / total * 100.0 if total > 0 else 0.0,
                "long_margin_share_pct": long_margin / total * 100.0 if total > 0 else 0.0,
                "net_pnl_delta_C4_minus_A": _safe_float(anchor.get("net_pnl_delta_C4_minus_A")),
            }
        )
    return pd.DataFrame(rows).sort_values(["start_month", "date", "anchor_type"]).reset_index(drop=True)


def _stress_summary(stress_days: pd.DataFrame, pressure: pd.DataFrame) -> pd.DataFrame:
    stress = (
        stress_days.groupby(["start_month", "stress_reason"], as_index=False)
        .agg(
            stress_days=("date", "count"),
            first_stress_date=("date", "min"),
            last_stress_date=("date", "max"),
            max_broker10_C4=("broker10_margin_to_equity_pct_C4", "max"),
            min_drawdown_C4=("drawdown_pct_C4", "min"),
            min_equity_delta_C4_minus_A=("account_equity_delta_C4_minus_A", "min"),
        )
        .sort_values(["start_month", "stress_reason"])
        if not stress_days.empty
        else pd.DataFrame()
    )
    anchor = (
        pressure.groupby("start_month", as_index=False)
        .agg(
            max_top3_margin_share_pct=("top3_margin_share_pct", "max"),
            max_short_margin_share_pct=("short_margin_share_pct", "max"),
            max_denominator_effect_pp=("denominator_equity_effect_pp", "max"),
            max_numerator_effect_pp=("numerator_margin_effect_pp", "max"),
        )
        if not pressure.empty
        else pd.DataFrame()
    )
    return stress.merge(anchor, on="start_month", how="left") if not stress.empty else stress


def _pre_anchor_cluster(
    anchors: pd.DataFrame,
    product_margin: pd.DataFrame,
    calendar: pd.DataFrame,
) -> pd.DataFrame:
    mapping = calendar.set_index("date")["td_index"]
    product = product_margin.copy()
    product["td_index"] = product["date"].map(mapping)
    rows: list[dict[str, Any]] = []
    for anchor in anchors.to_dict("records"):
        start_month = str(anchor["start_month"])
        date = pd.Timestamp(anchor["date"]).normalize()
        anchor_idx = mapping.get(date, np.nan)
        if pd.isna(anchor_idx):
            continue
        anchor_idx = int(anchor_idx)
        anchor_c4 = _anchor_margin_frame(product, start_month, date, C4_ARM)
        if anchor_c4.empty:
            continue
        total_anchor_margin = float(anchor_c4["c3_margin_exact"].sum())
        anchor_keys = [
            "start_month",
            "product_vt_symbol",
            "position_direction",
        ]
        anchor_margin = (
            anchor_c4.groupby(anchor_keys, as_index=False)
            .agg(
                anchor_margin=("c3_margin_exact", "sum"),
                anchor_abs_pos=("abs_end_pos", "sum"),
                anchor_contract_count=("contract_count", "sum"),
            )
        )
        a_anchor = _anchor_margin_frame(product, start_month, date, BASE_ARM)
        a_margin = (
            a_anchor.groupby(anchor_keys, as_index=False)
            .agg(A_anchor_margin=("c3_margin_exact", "sum"), A_anchor_abs_pos=("abs_end_pos", "sum"))
        )
        anchor_margin = anchor_margin.merge(a_margin, on=anchor_keys, how="left")
        anchor_margin["A_anchor_margin"] = pd.to_numeric(anchor_margin["A_anchor_margin"], errors="coerce").fillna(0.0)
        anchor_margin["A_anchor_abs_pos"] = pd.to_numeric(anchor_margin["A_anchor_abs_pos"], errors="coerce").fillna(0.0)
        anchor_margin["anchor_margin_share_pct"] = np.where(
            total_anchor_margin > 0,
            anchor_margin["anchor_margin"] / total_anchor_margin * 100.0,
            0.0,
        )
        for horizon in HORIZONS:
            start_idx = max(0, anchor_idx - horizon + 1)
            window = product[
                product["start_month"].astype(str).eq(start_month)
                & product["arm"].astype(str).eq(C4_ARM)
                & pd.to_numeric(product["td_index"], errors="coerce").between(start_idx, anchor_idx)
            ].copy()
            if window.empty:
                continue
            grouped = (
                window.groupby(anchor_keys, as_index=False)
                .agg(
                    days=("date", "nunique"),
                    window_margin_sum=("c3_margin_exact", "sum"),
                    window_margin_max=("c3_margin_exact", "max"),
                    window_holding_pnl=("holding_pnl", "sum"),
                    window_trading_pnl=("trading_pnl", "sum"),
                    window_net_pnl=("net_pnl", "sum"),
                    adverse_days=("net_pnl", lambda x: int(pd.to_numeric(x, errors="coerce").lt(0).sum())),
                )
                .merge(anchor_margin, on=anchor_keys, how="left")
            )
            grouped = grouped[pd.to_numeric(grouped["anchor_margin"], errors="coerce").notna()].copy()
            grouped["horizon_trading_days"] = horizon
            grouped["anchor_type"] = anchor["anchor_type"]
            grouped["anchor_date"] = date
            grouped["anchor_broker10_pct"] = _safe_float(anchor.get("broker10_margin_to_equity_pct_C4"))
            grouped["anchor_drawdown_pct"] = _safe_float(anchor.get("drawdown_pct_C4"))
            grouped["margin_delta_C4_minus_A"] = grouped["anchor_margin"] - grouped["A_anchor_margin"]
            grouped["window_loss_per_anchor_margin"] = np.where(
                grouped["anchor_margin"].abs() > 0,
                grouped["window_net_pnl"] / grouped["anchor_margin"],
                np.nan,
            )
            rows.extend(grouped.to_dict("records"))
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    result.sort_values(
        ["start_month", "anchor_date", "anchor_type", "horizon_trading_days", "anchor_margin_share_pct"],
        ascending=[True, True, True, True, False],
        inplace=True,
    )
    return result.reset_index(drop=True)


def _selected_pressure_contracts(anchors: pd.DataFrame, contract_margin: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    focus_anchors = anchors[anchors["anchor_type"].isin(["max_broker10", "first_broker100", "first_dd50"])].copy()
    for anchor in focus_anchors.to_dict("records"):
        start_month = str(anchor["start_month"])
        date = pd.Timestamp(anchor["date"]).normalize()
        part = contract_margin[
            contract_margin["start_month"].astype(str).eq(start_month)
            & contract_margin["arm"].astype(str).eq(C4_ARM)
            & contract_margin["date"].eq(date)
            & pd.to_numeric(contract_margin["c3_margin_exact"], errors="coerce").gt(0)
        ].copy()
        if part.empty:
            continue
        part["anchor_type"] = anchor["anchor_type"]
        part["anchor_broker10_pct"] = _safe_float(anchor.get("broker10_margin_to_equity_pct_C4"))
        part["anchor_drawdown_pct"] = _safe_float(anchor.get("drawdown_pct_C4"))
        part["anchor_equity_C4"] = _safe_float(anchor.get("account_equity_C4"))
        rows.append(part.sort_values("c3_margin_exact", ascending=False).head(TOP_CONTRACTS_PER_ANCHOR))
    if not rows:
        return pd.DataFrame()
    result = pd.concat(rows, ignore_index=True, sort=False)
    result.drop_duplicates(["start_month", "date", "anchor_type", "vt_symbol"], inplace=True)
    result.sort_values(["date", "c3_margin_exact"], ascending=[True, False], inplace=True)
    return result.head(MAX_ATLAS_ROWS).reset_index(drop=True)


def _minute_features(selected: pd.DataFrame) -> pd.DataFrame:
    if selected.empty:
        return pd.DataFrame()
    vt_symbols = set(selected["vt_symbol"].astype(str).dropna().unique())
    minute_bars = s825._load_minute_bars(vt_symbols)
    minute_by_symbol = s825._minute_groups(minute_bars)
    rows: list[dict[str, Any]] = []
    for row in selected.to_dict("records"):
        vt_symbol = str(row["vt_symbol"])
        date = pd.Timestamp(row["date"]).normalize()
        direction = str(row["position_direction"])
        bars = minute_by_symbol.get(vt_symbol, pd.DataFrame())
        day = bars[bars["bar_date"].eq(date)].copy().sort_values("bar_datetime") if not bars.empty else pd.DataFrame()
        item = {
            "start_month": row["start_month"],
            "date": date,
            "anchor_type": row["anchor_type"],
            "vt_symbol": vt_symbol,
            "product_vt_symbol": row.get("product_vt_symbol", ""),
            "position_direction": direction,
            "end_pos": _safe_float(row.get("end_pos")),
            "c3_margin_exact": _safe_float(row.get("c3_margin_exact")),
            "anchor_broker10_pct": _safe_float(row.get("anchor_broker10_pct")),
            "anchor_drawdown_pct": _safe_float(row.get("anchor_drawdown_pct")),
            "day_net_pnl": _safe_float(row.get("net_pnl")),
            "minute_bars": int(len(day)),
            "minute_source_state": "covered" if not day.empty else "missing",
            "intraday_open": np.nan,
            "intraday_close": np.nan,
            "intraday_adverse_pct": np.nan,
            "intraday_favorable_pct": np.nan,
            "intraday_signed_close_move_pct": np.nan,
        }
        if not day.empty:
            open_price = float(day["open"].iloc[0])
            close_price = float(day["close"].iloc[-1])
            high_price = float(day["high"].max())
            low_price = float(day["low"].min())
            if open_price > 0:
                if direction == "long":
                    adverse = (open_price - low_price) / open_price * 100.0
                    favorable = (high_price - open_price) / open_price * 100.0
                    signed_close = (close_price - open_price) / open_price * 100.0
                else:
                    adverse = (high_price - open_price) / open_price * 100.0
                    favorable = (open_price - low_price) / open_price * 100.0
                    signed_close = (open_price - close_price) / open_price * 100.0
                item.update(
                    {
                        "intraday_open": open_price,
                        "intraday_close": close_price,
                        "intraday_adverse_pct": adverse,
                        "intraday_favorable_pct": favorable,
                        "intraday_signed_close_move_pct": signed_close,
                    }
                )
        rows.append(item)
    return pd.DataFrame(rows)


def _plot_decomposition(pressure: pd.DataFrame) -> None:
    if pressure.empty:
        return
    data = pressure[pressure["anchor_type"].isin(["first_broker100", "max_broker10", "first_dd50", "max_drawdown"])].copy()
    data["label"] = data["start_month"].astype(str) + " " + data["anchor_type"].astype(str)
    data = data.sort_values(["date", "start_month", "anchor_type"])
    fig, axes = plt.subplots(2, 1, figsize=(18, 9), constrained_layout=True)
    x = np.arange(len(data))
    axes[0].bar(x - 0.2, data["actual_broker10_pct_A"], width=0.4, color="#2563eb", label="A actual broker10")
    axes[0].bar(x + 0.2, data["actual_broker10_pct_C4"], width=0.4, color="#16a34a", label="C4 actual broker10")
    axes[0].axhline(BROKER100, color="#dc2626", linestyle="--", linewidth=0.9)
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(data["label"], rotation=30, ha="right", fontsize=8)
    axes[0].set_title("Anchor broker10 margin/equity")
    axes[0].grid(True, axis="y", alpha=0.2)
    axes[0].legend()
    axes[1].bar(x - 0.2, data["numerator_margin_effect_pp"], width=0.4, color="#7c3aed", label="margin numerator effect")
    axes[1].bar(x + 0.2, data["denominator_equity_effect_pp"], width=0.4, color="#f59e0b", label="equity denominator effect")
    axes[1].axhline(0, color="#111827", linewidth=0.8)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(data["label"], rotation=30, ha="right", fontsize=8)
    axes[1].set_title("C4-A exact broker10 delta decomposition")
    axes[1].grid(True, axis="y", alpha=0.2)
    axes[1].legend()
    fig.suptitle("Stage837 holding pressure decomposition", fontsize=13)
    fig.savefig(DECOMP_CHART_PATH, dpi=150)
    plt.close(fig)


def _plot_cluster(pre_anchor: pd.DataFrame) -> None:
    if pre_anchor.empty:
        return
    data = pre_anchor[
        pre_anchor["anchor_type"].isin(["first_broker100", "max_broker10"])
        & pre_anchor["horizon_trading_days"].eq(10)
    ].copy()
    if data.empty:
        data = pre_anchor[pre_anchor["horizon_trading_days"].eq(10)].copy()
    data["cluster"] = data["product_vt_symbol"].astype(str) + " " + data["position_direction"].astype(str)
    data = data.sort_values("anchor_margin_share_pct", ascending=False).head(20)
    fig, axes = plt.subplots(1, 2, figsize=(18, 6), constrained_layout=True)
    labels = data["start_month"].astype(str) + "\n" + data["cluster"]
    y = np.arange(len(data))
    axes[0].barh(y, data["anchor_margin_share_pct"], color="#16a34a")
    axes[0].set_yticks(y)
    axes[0].set_yticklabels(labels, fontsize=8)
    axes[0].invert_yaxis()
    axes[0].set_title("Top 10-day anchor margin share")
    axes[0].grid(True, axis="x", alpha=0.2)
    axes[1].barh(y, data["window_net_pnl"], color=np.where(data["window_net_pnl"].lt(0), "#dc2626", "#2563eb"))
    axes[1].set_yticks(y)
    axes[1].set_yticklabels(labels, fontsize=8)
    axes[1].invert_yaxis()
    axes[1].axvline(0, color="#111827", linewidth=0.8)
    axes[1].set_title("10-day pre-anchor net pnl")
    axes[1].grid(True, axis="x", alpha=0.2)
    fig.suptitle("Stage837 pre-anchor product-direction clusters", fontsize=13)
    fig.savefig(CLUSTER_CHART_PATH, dpi=150)
    plt.close(fig)


def _plot_daily_atlas(selected: pd.DataFrame) -> None:
    if selected.empty:
        return
    fig, axes = plt.subplots(len(selected), 1, figsize=(18, max(4, 3.1 * len(selected))), constrained_layout=True)
    axes_list = list(np.atleast_1d(axes))
    for ax, row in zip(axes_list, selected.to_dict("records"), strict=False):
        vt_symbol = row["vt_symbol"]
        anchor_date = pd.Timestamp(row["date"]).normalize()
        bars, source = s815._read_plot_bars(vt_symbol)
        if bars.empty:
            ax.axis("off")
            ax.text(0.5, 0.5, f"missing daily bars {vt_symbol}", ha="center", va="center")
            continue
        idx = s752._event_index(bars, anchor_date)
        start = max(0, idx - 45)
        end = min(len(bars), idx + 31)
        window = bars.iloc[start:end].copy().reset_index(drop=True)
        local_idx = idx - start
        s752._plot_candles(ax, window)
        for ma, color in [(5, "#f59e0b"), (10, "#2563eb"), (20, "#7c3aed"), (40, "#111827")]:
            ax.plot(window["close"].rolling(ma).mean().to_numpy(), color=color, linewidth=0.75, alpha=0.82)
        ax.axvline(local_idx, color="#dc2626", linestyle="--", linewidth=1.0)
        ticks = np.linspace(0, len(window) - 1, num=min(8, len(window)), dtype=int)
        ax.set_xticks(ticks)
        ax.set_xticklabels([pd.Timestamp(window.loc[pos, "date"]).strftime("%Y-%m-%d") for pos in ticks], rotation=28, ha="right", fontsize=7)
        ax.grid(True, alpha=0.18)
        ax.set_title(
            (
                f"{row['start_month']} {row['anchor_type']} {vt_symbol} {row['position_direction']} "
                f"{anchor_date:%Y-%m-%d} pos={_safe_float(row.get('end_pos')):.0f} "
                f"margin={_safe_float(row.get('c3_margin_exact')):,.0f} "
                f"broker10={_safe_float(row.get('anchor_broker10_pct')):.2f}% source={source}"
            ),
            fontsize=8.5,
            loc="left",
        )
    fig.suptitle("Stage837 top pressure contracts daily K atlas", fontsize=13)
    fig.savefig(DAILY_ATLAS_PATH, dpi=150)
    plt.close(fig)


def _plot_minute_atlas(selected: pd.DataFrame) -> None:
    if selected.empty:
        return
    vt_symbols = set(selected["vt_symbol"].astype(str).dropna().unique())
    minute_bars = s825._load_minute_bars(vt_symbols)
    minute_by_symbol = s825._minute_groups(minute_bars)
    fig, axes = plt.subplots(len(selected), 1, figsize=(18, max(4, 3.0 * len(selected))), constrained_layout=True)
    axes_list = list(np.atleast_1d(axes))
    for ax, row in zip(axes_list, selected.to_dict("records"), strict=False):
        vt_symbol = str(row["vt_symbol"])
        anchor_date = pd.Timestamp(row["date"]).normalize()
        bars = minute_by_symbol.get(vt_symbol, pd.DataFrame())
        day = bars[bars["bar_date"].eq(anchor_date)].copy().sort_values("bar_datetime").head(280).reset_index(drop=True) if not bars.empty else pd.DataFrame()
        if day.empty:
            ax.axis("off")
            ax.text(0.5, 0.5, f"missing minute bars {vt_symbol} {anchor_date:%Y-%m-%d}", ha="center", va="center")
            continue
        s825._plot_candles(ax, day)
        ax.plot(np.arange(len(day)), day["close"].rolling(5).mean(), color="#f59e0b", linewidth=0.75)
        ax.plot(np.arange(len(day)), day["close"].rolling(20).mean(), color="#2563eb", linewidth=0.75)
        ticks = np.linspace(0, len(day) - 1, num=min(8, len(day)), dtype=int)
        ax.set_xticks(ticks)
        ax.set_xticklabels([pd.Timestamp(day.loc[pos, "bar_datetime"]).strftime("%H:%M") for pos in ticks], fontsize=7)
        ax.grid(True, alpha=0.18)
        open_price = float(day["open"].iloc[0])
        close_price = float(day["close"].iloc[-1])
        direction = str(row["position_direction"])
        if open_price > 0:
            signed = (close_price - open_price) / open_price * 100.0 if direction == "long" else (open_price - close_price) / open_price * 100.0
        else:
            signed = np.nan
        ax.set_title(
            (
                f"{row['start_month']} {row['anchor_type']} {vt_symbol} {direction} "
                f"{anchor_date:%Y-%m-%d} signed_close={signed:.2f}% "
                f"net_pnl={_safe_float(row.get('net_pnl')):,.0f}"
            ),
            fontsize=8.5,
            loc="left",
        )
    fig.suptitle("Stage837 top pressure contracts stress-day minute K atlas", fontsize=13)
    fig.savefig(MINUTE_ATLAS_PATH, dpi=150)
    plt.close(fig)


def _write_report(
    stress_summary: pd.DataFrame,
    pressure: pd.DataFrame,
    pre_anchor: pd.DataFrame,
    minute_features: pd.DataFrame,
) -> None:
    pressure_display = pressure[
        [
            "start_month",
            "date",
            "anchor_type",
            "actual_broker10_pct_A",
            "actual_broker10_pct_C4",
            "drawdown_pct_A",
            "drawdown_pct_C4",
            "equity_delta_C4_minus_A",
            "margin_delta_C4_minus_A",
            "numerator_margin_effect_pp",
            "denominator_equity_effect_pp",
            "top_product_direction",
            "top1_margin_share_pct",
            "top3_margin_share_pct",
            "short_margin_share_pct",
        ]
    ].copy()
    cluster_display = pre_anchor[
        pre_anchor["horizon_trading_days"].eq(10)
        & pre_anchor["anchor_type"].isin(["first_broker100", "max_broker10", "first_dd50"])
    ].copy()
    if not cluster_display.empty:
        cluster_display = cluster_display.sort_values(["anchor_margin_share_pct", "window_net_pnl"], ascending=[False, True]).head(60)
        cluster_display = cluster_display[
            [
                "start_month",
                "anchor_date",
                "anchor_type",
                "product_vt_symbol",
                "position_direction",
                "horizon_trading_days",
                "anchor_margin",
                "anchor_margin_share_pct",
                "margin_delta_C4_minus_A",
                "window_net_pnl",
                "adverse_days",
                "window_loss_per_anchor_margin",
            ]
        ]
    minute_display = minute_features.sort_values(["minute_source_state", "c3_margin_exact"], ascending=[True, False]).head(40)
    lines = [
        "# Stage837 C4持仓后全路径压力法证",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 源候选：`{stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION}`",
        "- 阶段性质：只读归因；不改正式策略、不改候选配置、不连接 CTP、不调用下单。",
        "",
        "## 外部调研判断",
        "",
        "- CME 风险管理资料强调 futures 风险由合约、手数和止损共同决定，不能只看是否有止损。",
        "- Euronext Clearing 说明 margin 是覆盖 open position 理论成本的核心工具，并明确有 liquidity/concentration 等 add-on。",
        "- FINRA portfolio margin 监管材料强调需要 intraday 和 end-of-day 监控组合持仓风险。",
        "- 因此本阶段优先拆持仓簇、产品集中、权益分母和分钟级不利运动，而不是继续改 C2 止损或 cooldown。",
        "",
        "## Stress Summary",
        "",
        _md_table(stress_summary, max_rows=40),
        "",
        "## Pressure Decomposition",
        "",
        _md_table(pressure_display, max_rows=80),
        "",
        "## Pre-Anchor 10D Clusters",
        "",
        _md_table(cluster_display, max_rows=60),
        "",
        "## Minute Pressure Features",
        "",
        _md_table(minute_display, max_rows=40),
        "",
        "## Charts",
        "",
        f"- decomposition chart：`{DECOMP_CHART_PATH}`",
        f"- cluster chart：`{CLUSTER_CHART_PATH}`",
        f"- daily pressure atlas：`{DAILY_ATLAS_PATH}`",
        f"- minute pressure atlas：`{MINUTE_ATLAS_PATH}`",
        "",
        "## Judgment",
        "",
        "- broker100 是持仓簇集中 + 权益分母共同作用，不是入口 cap 失效。",
        "- DD50 与 broker100 仍不是同一件事：DD50 锚点常常保证金为 0，主要是历史高水位后的权益路径问题。",
        "- 若继续设计规则，应围绕持仓中压力状态做低自由度减风险，而不是按产品或年份过滤。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    frames = _prepare_inputs()
    calendar = _calendar(frames["curves"])
    pressure = _pressure_decomposition(frames["anchors"], frames["product_margin"])
    stress_summary = _stress_summary(frames["stress_days"], pressure)
    pre_anchor = _pre_anchor_cluster(frames["anchors"], frames["product_margin"], calendar)
    selected = _selected_pressure_contracts(frames["anchors"], frames["contract_margin"])
    minute_features = _minute_features(selected)

    _plot_decomposition(pressure)
    _plot_cluster(pre_anchor)
    _plot_daily_atlas(selected)
    _plot_minute_atlas(selected)
    _write_report(stress_summary, pressure, pre_anchor, minute_features)

    pressure.to_csv(PRESSURE_DECOMP_PATH, index=False, encoding="utf-8-sig")
    pre_anchor.to_csv(PRE_ANCHOR_CLUSTER_PATH, index=False, encoding="utf-8-sig")
    stress_summary.to_csv(STRESS_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    minute_features.to_csv(MINUTE_FEATURES_PATH, index=False, encoding="utf-8-sig")

    broker = pressure[pressure["anchor_type"].isin(["first_broker100", "max_broker10"])].copy()
    broker["top3_high"] = pd.to_numeric(broker["top3_margin_share_pct"], errors="coerce").ge(75.0)
    broker["short_cluster"] = pd.to_numeric(broker["short_margin_share_pct"], errors="coerce").ge(75.0)
    broker["denominator_positive"] = pd.to_numeric(broker["denominator_equity_effect_pp"], errors="coerce").gt(0)
    broker_rule_shape_supported = bool(
        not broker.empty
        and broker["top3_high"].mean() >= 0.75
        and broker["short_cluster"].mean() >= 0.75
    )
    decision_label = (
        "stage837_holding_pressure_cluster_rule_shape_supported"
        if broker_rule_shape_supported
        else "stage837_holding_pressure_mixed_no_rule_yet"
    )
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "source_candidate": stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION,
        "strategy_changed": False,
        "ctp_connected": False,
        "order_api_called": False,
        "decision": decision_label,
        "broker_anchor_count": int(len(broker)),
        "broker_top3_high_rate": float(broker["top3_high"].mean()) if not broker.empty else np.nan,
        "broker_short_cluster_rate": float(broker["short_cluster"].mean()) if not broker.empty else np.nan,
        "broker_denominator_positive_rate": float(broker["denominator_positive"].mean()) if not broker.empty else np.nan,
        "overfit_reflection": (
            "Stage837 is read-only and uses all Stage832 stress anchors. It tests broad cluster conditions instead of "
            "filtering individual products or years. Product-specific rules from these anchors would overfit."
        ),
        "continue_value": (
            "Continue only if a broad holding-state rule emerges across broker100 anchors. If mixed, keep forensics and "
            "do not build a live rule."
        ),
        "outputs": {
            "pressure_decomposition": str(PRESSURE_DECOMP_PATH),
            "pre_anchor_cluster": str(PRE_ANCHOR_CLUSTER_PATH),
            "stress_summary": str(STRESS_SUMMARY_PATH),
            "minute_features": str(MINUTE_FEATURES_PATH),
            "report": str(REPORT_PATH),
            "decomposition_chart": str(DECOMP_CHART_PATH),
            "cluster_chart": str(CLUSTER_CHART_PATH),
            "daily_atlas": str(DAILY_ATLAS_PATH),
            "minute_atlas": str(MINUTE_ATLAS_PATH),
        },
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print("stress_summary")
    print(stress_summary.to_string(index=False))
    print("pressure")
    print(pressure.to_string(index=False))
    print("pre_anchor_top")
    show = pre_anchor[
        pre_anchor["horizon_trading_days"].eq(10)
        & pre_anchor["anchor_type"].isin(["first_broker100", "max_broker10", "first_dd50"])
    ].copy()
    if not show.empty:
        print(
            show.sort_values(["anchor_margin_share_pct", "window_net_pnl"], ascending=[False, True])
            .head(40)
            .to_string(index=False)
        )
    print("minute_features")
    print(minute_features.to_string(index=False))


if __name__ == "__main__":
    main()
