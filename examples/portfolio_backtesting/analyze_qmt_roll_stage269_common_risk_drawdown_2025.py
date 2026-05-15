from __future__ import annotations

import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage269_common_risk_drawdown_2025_v1"
OUTPUT_PREFIX = "qmt_roll_stage269_common_risk_drawdown_2025"

STAGE267_PREFIX = "qmt_roll_stage267_hot_product_official_add_one_validation"
BASE_NAME = "official_stage78_1_static18_plus_fu"
Y_NAME = "official_stage78_1_plus_y_DCE"
AG_NAME = "official_stage78_1_plus_ag_SHFE"

STRATEGIES: dict[str, dict[str, Path]] = {
    "A_static18_fu": {
        "daily": OUTPUT_DIR / f"{STAGE267_PREFIX}_{BASE_NAME}_daily.csv",
        "position_changes": OUTPUT_DIR / f"{STAGE267_PREFIX}_{BASE_NAME}_position_changes_2020_2026_04.csv",
        "entry_risk": OUTPUT_DIR / f"{STAGE267_PREFIX}_{BASE_NAME}_entry_risk_diagnostics_2020_2026_04.csv",
    },
    "C_plus_y_DCE": {
        "daily": OUTPUT_DIR / f"{STAGE267_PREFIX}_{Y_NAME}_daily.csv",
        "position_changes": OUTPUT_DIR / f"{STAGE267_PREFIX}_{Y_NAME}_position_changes_2020_2026_04.csv",
        "entry_risk": OUTPUT_DIR / f"{STAGE267_PREFIX}_{Y_NAME}_entry_risk_diagnostics_2020_2026_04.csv",
    },
    "C_plus_ag_SHFE": {
        "daily": OUTPUT_DIR / f"{STAGE267_PREFIX}_{AG_NAME}_daily.csv",
        "position_changes": OUTPUT_DIR / f"{STAGE267_PREFIX}_{AG_NAME}_position_changes_2020_2026_04.csv",
        "entry_risk": OUTPUT_DIR / f"{STAGE267_PREFIX}_{AG_NAME}_entry_risk_diagnostics_2020_2026_04.csv",
    },
}

WINDOWS: tuple[tuple[str, str, str], ...] = (
    ("full_aug_nov_2025", "2025-08-01", "2025-11-30"),
    ("ag_peak_to_trough", "2025-07-25", "2025-08-27"),
    ("y_worst_63d", "2025-08-14", "2025-11-18"),
    ("post_trough_recovery", "2025-08-28", "2025-11-17"),
)

TRADING_DAYS_PER_YEAR = 240
INITIAL_CAPITAL = 500_000.0

DAILY_METRICS_CSV = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_window_metrics_{MODEL_TAG}.csv"
PRODUCT_CONTRIB_CSV = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_contrib_{MODEL_TAG}.csv"
SECTOR_CONTRIB_CSV = OUTPUT_DIR / f"{OUTPUT_PREFIX}_sector_contrib_{MODEL_TAG}.csv"
DAILY_EXTREMES_CSV = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_common_risk_extremes_{MODEL_TAG}.csv"
ENTRY_RISK_CSV = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_window_{MODEL_TAG}.csv"
DELTA_CONTRIB_CSV = OUTPUT_DIR / f"{OUTPUT_PREFIX}_candidate_delta_contrib_{MODEL_TAG}.csv"
CORRELATION_CSV = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pnl_correlation_{MODEL_TAG}.csv"
PCA_CSV = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pca_common_mode_{MODEL_TAG}.csv"
SUMMARY_JSON = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_MD = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


SECTOR_MAP: dict[str, str] = {
    "AP.CZCE": "soft_agri",
    "CF.CZCE": "soft_agri",
    "SR.CZCE": "soft_agri",
    "CJ.CZCE": "soft_agri",
    "FG.CZCE": "chemicals_building",
    "MA.CZCE": "chemicals_building",
    "TA.CZCE": "chemicals_building",
    "PF.CZCE": "chemicals_building",
    "SA.CZCE": "chemicals_building",
    "SH.CZCE": "chemicals_building",
    "SM.CZCE": "black_ferrous",
    "SF.CZCE": "black_ferrous",
    "OI.CZCE": "agri_oils",
    "RM.CZCE": "agri_oils",
    "rb.SHFE": "black_ferrous",
    "hc.SHFE": "black_ferrous",
    "sp.SHFE": "chemicals_building",
    "ru.SHFE": "chemicals_building",
    "fu.SHFE": "energy_oil",
    "ag.SHFE": "precious_nonferrous",
    "au.SHFE": "precious_nonferrous",
    "cu.SHFE": "precious_nonferrous",
    "al.SHFE": "precious_nonferrous",
    "zn.SHFE": "precious_nonferrous",
    "pb.SHFE": "precious_nonferrous",
    "ni.SHFE": "precious_nonferrous",
    "sn.SHFE": "precious_nonferrous",
    "ao.SHFE": "precious_nonferrous",
    "sc.INE": "energy_oil",
    "lu.INE": "energy_oil",
    "lc.GFEX": "battery_metals",
    "i.DCE": "black_ferrous",
    "j.DCE": "black_ferrous",
    "jm.DCE": "black_ferrous",
    "lh.DCE": "livestock",
    "m.DCE": "agri_oils",
    "p.DCE": "agri_oils",
    "y.DCE": "agri_oils",
    "a.DCE": "agri_oils",
    "c.DCE": "grain",
    "cs.DCE": "grain",
    "v.DCE": "chemicals_building",
    "pp.DCE": "chemicals_building",
    "l.DCE": "chemicals_building",
    "eb.DCE": "chemicals_building",
    "pg.DCE": "energy_oil",
    "si.GFEX": "black_ferrous",
}


def _product_from_vt_symbol(vt_symbol: Any) -> str:
    text = str(vt_symbol)
    if "." not in text:
        return text
    symbol, exchange = text.split(".", 1)
    match = re.match(r"[A-Za-z]+", symbol)
    product = match.group(0) if match else symbol
    return f"{product}.{exchange}"


def _sector(product: str) -> str:
    return SECTOR_MAP.get(product, "unknown")


def _load_daily(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    for column in [
        "trade_count",
        "turnover",
        "commission",
        "slippage",
        "trading_pnl",
        "holding_pnl",
        "total_pnl",
        "net_pnl",
        "balance",
        "drawdown",
        "ddpercent",
    ]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0.0)
    return df.sort_values("date").reset_index(drop=True)


def _load_position_changes(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df["product_vt_symbol"] = df["vt_symbol"].map(_product_from_vt_symbol)
    df["sector"] = df["product_vt_symbol"].map(_sector)
    for column in [
        "start_pos",
        "end_pos",
        "pos_change",
        "close_price",
        "pre_close",
        "trade_count",
        "turnover",
        "commission",
        "slippage",
        "holding_pnl",
        "trading_pnl",
        "total_pnl",
        "net_pnl",
    ]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0.0)
    return df


def _load_entry_risk(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    for column in [
        "estimated_equity",
        "total_margin_in_use_before",
        "actual_margin_amount",
        "projected_total_margin_after",
        "portfolio_drawdown_pct",
        "same_direction_correlation_active_count",
        "same_direction_correlation_corr_count",
        "same_direction_correlation_max_corr",
        "same_direction_correlation_avg_corr",
        "target_risk_amount",
        "actual_risk_amount",
        "size",
    ]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0.0)
    if "product_vt_symbol" in df.columns:
        df["sector"] = df["product_vt_symbol"].map(_sector)
    else:
        df["sector"] = "unknown"
    return df


def _window_mask(df: pd.DataFrame, start: str, end: str) -> pd.Series:
    return (df["date"] >= pd.Timestamp(start)) & (df["date"] <= pd.Timestamp(end))


def _metrics_from_daily(daily: pd.DataFrame, strategy_label: str, window_name: str, start: str, end: str) -> dict[str, Any]:
    part = daily[_window_mask(daily, start, end)].copy()
    if part.empty:
        return {
            "strategy_label": strategy_label,
            "window_name": window_name,
            "start_date": start,
            "end_date": end,
            "days": 0,
        }
    net_pnl = part["net_pnl"].to_numpy(dtype=float)
    previous = np.concatenate([[float(part["balance"].iloc[0] - net_pnl[0])], part["balance"].iloc[:-1].to_numpy(dtype=float)])
    returns = np.divide(net_pnl, previous, out=np.zeros_like(net_pnl), where=previous != 0.0)
    high = part["balance"].cummax()
    local_dd = part["balance"] - high
    local_dd_pct = np.divide(local_dd, high, out=np.zeros(len(part), dtype=float), where=high.to_numpy(dtype=float) != 0.0) * 100.0
    trough_idx = int(local_dd.idxmin())
    peak_balance = float(high.loc[trough_idx])
    peak_idx = int(part.loc[:trough_idx][part.loc[:trough_idx, "balance"].eq(peak_balance)].index[-1])
    std = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.0
    sharpe = float(np.mean(returns) / std * math.sqrt(TRADING_DAYS_PER_YEAR)) if std > 0 else 0.0
    return {
        "strategy_label": strategy_label,
        "window_name": window_name,
        "start_date": start,
        "end_date": end,
        "days": int(len(part)),
        "window_start_balance": float(part["balance"].iloc[0] - net_pnl[0]),
        "window_end_balance": float(part["balance"].iloc[-1]),
        "window_net_pnl": float(part["net_pnl"].sum()),
        "window_return_pct_on_start_balance": float(part["net_pnl"].sum() / (part["balance"].iloc[0] - net_pnl[0]) * 100.0),
        "window_trade_count": int(part["trade_count"].sum()),
        "window_slippage": float(part["slippage"].sum()),
        "loss_day_count": int((part["net_pnl"] < 0).sum()),
        "profit_day_count": int((part["net_pnl"] > 0).sum()),
        "worst_day": part.loc[part["net_pnl"].idxmin(), "date"].date().isoformat(),
        "worst_day_net_pnl": float(part["net_pnl"].min()),
        "best_day": part.loc[part["net_pnl"].idxmax(), "date"].date().isoformat(),
        "best_day_net_pnl": float(part["net_pnl"].max()),
        "local_peak_date": part.loc[peak_idx, "date"].date().isoformat(),
        "local_trough_date": part.loc[trough_idx, "date"].date().isoformat(),
        "local_drawdown": float(local_dd.min()),
        "local_drawdown_pct": float(local_dd_pct.min()),
        "local_sharpe": sharpe,
    }


def _product_contrib(pc: pd.DataFrame, strategy_label: str, window_name: str, start: str, end: str) -> pd.DataFrame:
    part = pc[_window_mask(pc, start, end)].copy()
    if part.empty:
        return pd.DataFrame()
    group = part.groupby(["product_vt_symbol", "sector"], as_index=False).agg(
        net_pnl=("net_pnl", "sum"),
        holding_pnl=("holding_pnl", "sum"),
        trading_pnl=("trading_pnl", "sum"),
        slippage=("slippage", "sum"),
        trade_count=("trade_count", "sum"),
        turnover=("turnover", "sum"),
        active_days=("end_pos", lambda x: int((x != 0).sum())),
        avg_abs_end_pos=("end_pos", lambda x: float(np.abs(x).mean())),
        max_abs_end_pos=("end_pos", lambda x: float(np.abs(x).max())),
    )
    group.insert(0, "window_name", window_name)
    group.insert(0, "strategy_label", strategy_label)
    return group.sort_values(["window_name", "strategy_label", "net_pnl"])


def _sector_contrib(product_contrib: pd.DataFrame) -> pd.DataFrame:
    if product_contrib.empty:
        return pd.DataFrame()
    return (
        product_contrib.groupby(["strategy_label", "window_name", "sector"], as_index=False)
        .agg(
            net_pnl=("net_pnl", "sum"),
            holding_pnl=("holding_pnl", "sum"),
            trading_pnl=("trading_pnl", "sum"),
            slippage=("slippage", "sum"),
            trade_count=("trade_count", "sum"),
            active_days=("active_days", "sum"),
            product_count=("product_vt_symbol", "nunique"),
        )
        .sort_values(["window_name", "strategy_label", "net_pnl"])
    )


def _daily_active_summary(pc: pd.DataFrame, strategy_label: str, window_name: str, start: str, end: str) -> pd.DataFrame:
    part = pc[_window_mask(pc, start, end)].copy()
    if part.empty:
        return pd.DataFrame()
    product_day = part.groupby(["date", "product_vt_symbol", "sector"], as_index=False).agg(
        net_pnl=("net_pnl", "sum"),
        holding_pnl=("holding_pnl", "sum"),
        trading_pnl=("trading_pnl", "sum"),
        slippage=("slippage", "sum"),
        trade_count=("trade_count", "sum"),
        end_pos=("end_pos", "sum"),
    )
    rows: list[dict[str, Any]] = []
    for date, group in product_day.groupby("date", sort=True):
        active = group[group["end_pos"].ne(0)].copy()
        losers = group[group["net_pnl"].lt(0)].sort_values("net_pnl")
        negative_loss = float(-losers["net_pnl"].sum()) if not losers.empty else 0.0
        top_loss = float(losers["net_pnl"].iloc[0]) if not losers.empty else 0.0
        top_product = str(losers["product_vt_symbol"].iloc[0]) if not losers.empty else ""
        top_sector = str(losers["sector"].iloc[0]) if not losers.empty else ""
        rows.append(
            {
                "strategy_label": strategy_label,
                "window_name": window_name,
                "date": pd.Timestamp(date).date().isoformat(),
                "net_pnl": float(group["net_pnl"].sum()),
                "holding_pnl": float(group["holding_pnl"].sum()),
                "trading_pnl": float(group["trading_pnl"].sum()),
                "slippage": float(group["slippage"].sum()),
                "trade_count": int(group["trade_count"].sum()),
                "active_product_count": int(active["product_vt_symbol"].nunique()),
                "long_product_count": int(active[active["end_pos"].gt(0)]["product_vt_symbol"].nunique()),
                "short_product_count": int(active[active["end_pos"].lt(0)]["product_vt_symbol"].nunique()),
                "negative_product_count": int(losers["product_vt_symbol"].nunique()),
                "negative_loss_abs": negative_loss,
                "top_loss_product": top_product,
                "top_loss_sector": top_sector,
                "top_loss_net_pnl": top_loss,
                "top_loss_share_of_negative_loss": float((-top_loss / negative_loss) if negative_loss else 0.0),
                "loss_concentration_hhi": float(
                    np.square((-losers["net_pnl"] / negative_loss).to_numpy(dtype=float)).sum()
                )
                if negative_loss
                else 0.0,
                "long_bias_ratio": float(
                    active[active["end_pos"].gt(0)]["product_vt_symbol"].nunique() / len(active)
                )
                if len(active)
                else 0.0,
            }
        )
    return pd.DataFrame(rows)


def _entry_risk_summary(entries: pd.DataFrame, strategy_label: str, window_name: str, start: str, end: str) -> pd.DataFrame:
    if entries.empty:
        return pd.DataFrame()
    part = entries[_window_mask(entries, start, end)].copy()
    if part.empty:
        return pd.DataFrame(
            [
                {
                    "strategy_label": strategy_label,
                    "window_name": window_name,
                    "entry_count": 0,
                }
            ]
        )
    rows: list[dict[str, Any]] = []
    scopes = [("all_entries", part)]
    if "direction" in part.columns:
        scopes.extend(
            [
                ("long_entries", part[part["direction"].astype(str).str.lower().eq("long")]),
                ("short_entries", part[part["direction"].astype(str).str.lower().eq("short")]),
            ]
        )
    for scope, frame in scopes:
        rows.append(
            {
                "strategy_label": strategy_label,
                "window_name": window_name,
                "scope": scope,
                "entry_count": int(len(frame)),
                "product_count": int(frame["product_vt_symbol"].nunique()) if "product_vt_symbol" in frame.columns else 0,
                "avg_portfolio_drawdown_pct": float(frame["portfolio_drawdown_pct"].mean()) if "portfolio_drawdown_pct" in frame else 0.0,
                "max_portfolio_drawdown_pct": float(frame["portfolio_drawdown_pct"].max()) if "portfolio_drawdown_pct" in frame else 0.0,
                "avg_projected_total_margin_after": float(frame["projected_total_margin_after"].mean())
                if "projected_total_margin_after" in frame
                else 0.0,
                "max_projected_total_margin_after": float(frame["projected_total_margin_after"].max())
                if "projected_total_margin_after" in frame
                else 0.0,
                "avg_actual_margin_amount": float(frame["actual_margin_amount"].mean()) if "actual_margin_amount" in frame else 0.0,
                "max_actual_margin_amount": float(frame["actual_margin_amount"].max()) if "actual_margin_amount" in frame else 0.0,
                "avg_same_direction_active_count": float(frame["same_direction_correlation_active_count"].mean())
                if "same_direction_correlation_active_count" in frame
                else 0.0,
                "max_same_direction_active_count": float(frame["same_direction_correlation_active_count"].max())
                if "same_direction_correlation_active_count" in frame
                else 0.0,
                "avg_same_direction_max_corr": float(frame["same_direction_correlation_max_corr"].mean())
                if "same_direction_correlation_max_corr" in frame
                else 0.0,
                "max_same_direction_max_corr": float(frame["same_direction_correlation_max_corr"].max())
                if "same_direction_correlation_max_corr" in frame
                else 0.0,
            }
        )
    return pd.DataFrame(rows)


def _candidate_delta(product_contrib: pd.DataFrame, sector_contrib: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for level, frame, key_col in [
        ("product", product_contrib, "product_vt_symbol"),
        ("sector", sector_contrib, "sector"),
    ]:
        if frame.empty:
            continue
        for candidate in ["C_plus_y_DCE", "C_plus_ag_SHFE"]:
            base = frame[frame["strategy_label"].eq("A_static18_fu")].copy()
            cand = frame[frame["strategy_label"].eq(candidate)].copy()
            keep_cols = ["window_name", key_col, "net_pnl", "holding_pnl", "trading_pnl", "slippage", "trade_count"]
            if level == "product":
                keep_cols.insert(2, "sector")
            merged = cand[keep_cols].merge(
                base[keep_cols],
                on=["window_name", key_col] + (["sector"] if level == "product" else []),
                how="outer",
                suffixes=("_candidate", "_A"),
            ).fillna(0.0)
            merged.insert(0, "level", level)
            merged.insert(1, "candidate_label", candidate)
            for metric in ["net_pnl", "holding_pnl", "trading_pnl", "slippage", "trade_count"]:
                merged[f"{metric}_diff_vs_A"] = merged[f"{metric}_candidate"] - merged[f"{metric}_A"]
            rows.append(merged)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def _pnl_correlation_and_pca(pc: pd.DataFrame, strategy_label: str, window_name: str, start: str, end: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    part = pc[_window_mask(pc, start, end)].copy()
    if part.empty:
        return pd.DataFrame(), pd.DataFrame()
    product_day = (
        part.groupby(["date", "product_vt_symbol"], as_index=False)["net_pnl"]
        .sum()
        .pivot(index="date", columns="product_vt_symbol", values="net_pnl")
        .fillna(0.0)
    )
    active_sum = product_day.abs().sum(axis=0)
    product_day = product_day.loc[:, active_sum.gt(0.0)]
    if product_day.shape[1] < 2:
        return pd.DataFrame(), pd.DataFrame()
    active_sum = product_day.abs().sum(axis=0)
    top_cols = active_sum.sort_values(ascending=False).head(12).index.tolist()
    matrix = product_day[top_cols].copy()
    corr = matrix.corr().fillna(0.0)
    corr_rows = []
    for i, col_a in enumerate(top_cols):
        for col_b in top_cols[i + 1 :]:
            corr_rows.append(
                {
                    "strategy_label": strategy_label,
                    "window_name": window_name,
                    "product_a": col_a,
                    "sector_a": _sector(col_a),
                    "product_b": col_b,
                    "sector_b": _sector(col_b),
                    "corr": float(corr.loc[col_a, col_b]),
                }
            )
    standardized = matrix.copy()
    standardized = (standardized - standardized.mean()) / standardized.std(ddof=0).replace(0.0, np.nan)
    standardized = standardized.fillna(0.0)
    corr_matrix = np.corrcoef(standardized.to_numpy(dtype=float), rowvar=False)
    eigvals, eigvecs = np.linalg.eigh(corr_matrix)
    order = np.argsort(eigvals)[::-1]
    eigvals = eigvals[order]
    eigvecs = eigvecs[:, order]
    total = float(eigvals.sum()) if eigvals.size else 0.0
    pc1_share = float(eigvals[0] / total) if total else 0.0
    pca_rows = [
        {
            "strategy_label": strategy_label,
            "window_name": window_name,
            "component": "pc1_summary",
            "pc1_variance_share": pc1_share,
            "product_vt_symbol": "",
            "sector": "",
            "loading": 0.0,
        }
    ]
    for product, loading in sorted(zip(top_cols, eigvecs[:, 0], strict=True), key=lambda item: abs(item[1]), reverse=True):
        pca_rows.append(
            {
                "strategy_label": strategy_label,
                "window_name": window_name,
                "component": "pc1_loading",
                "pc1_variance_share": pc1_share,
                "product_vt_symbol": product,
                "sector": _sector(product),
                "loading": float(loading),
            }
        )
    return pd.DataFrame(corr_rows), pd.DataFrame(pca_rows)


def _format_markdown_table(df: pd.DataFrame, columns: list[str], max_rows: int = 12) -> str:
    if df.empty:
        return "_无数据_\n"
    view = df.loc[:, columns].head(max_rows).copy()
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda x: f"{x:.4f}")
    return view.to_markdown(index=False, disable_numparse=True)


def main() -> None:
    daily_by_strategy = {label: _load_daily(paths["daily"]) for label, paths in STRATEGIES.items()}
    pc_by_strategy = {label: _load_position_changes(paths["position_changes"]) for label, paths in STRATEGIES.items()}
    entries_by_strategy = {label: _load_entry_risk(paths["entry_risk"]) for label, paths in STRATEGIES.items()}

    metric_rows: list[dict[str, Any]] = []
    product_frames: list[pd.DataFrame] = []
    daily_extreme_frames: list[pd.DataFrame] = []
    entry_frames: list[pd.DataFrame] = []
    corr_frames: list[pd.DataFrame] = []
    pca_frames: list[pd.DataFrame] = []

    for window_name, start, end in WINDOWS:
        for label in STRATEGIES:
            metric_rows.append(_metrics_from_daily(daily_by_strategy[label], label, window_name, start, end))
            product_frames.append(_product_contrib(pc_by_strategy[label], label, window_name, start, end))
            daily_active = _daily_active_summary(pc_by_strategy[label], label, window_name, start, end)
            if not daily_active.empty:
                daily_extreme_frames.append(daily_active.sort_values("net_pnl").head(12))
            entry_frames.append(_entry_risk_summary(entries_by_strategy[label], label, window_name, start, end))
            corr, pca = _pnl_correlation_and_pca(pc_by_strategy[label], label, window_name, start, end)
            corr_frames.append(corr)
            pca_frames.append(pca)

    daily_metrics = pd.DataFrame(metric_rows)
    product_contrib = pd.concat(product_frames, ignore_index=True) if product_frames else pd.DataFrame()
    sector_contrib = _sector_contrib(product_contrib)
    daily_extremes = pd.concat(daily_extreme_frames, ignore_index=True) if daily_extreme_frames else pd.DataFrame()
    entry_risk = pd.concat(entry_frames, ignore_index=True) if entry_frames else pd.DataFrame()
    delta_contrib = _candidate_delta(product_contrib, sector_contrib)
    corr_df = pd.concat(corr_frames, ignore_index=True) if corr_frames else pd.DataFrame()
    pca_df = pd.concat(pca_frames, ignore_index=True) if pca_frames else pd.DataFrame()

    daily_metrics.to_csv(DAILY_METRICS_CSV, index=False)
    product_contrib.to_csv(PRODUCT_CONTRIB_CSV, index=False)
    sector_contrib.to_csv(SECTOR_CONTRIB_CSV, index=False)
    daily_extremes.to_csv(DAILY_EXTREMES_CSV, index=False)
    entry_risk.to_csv(ENTRY_RISK_CSV, index=False)
    delta_contrib.to_csv(DELTA_CONTRIB_CSV, index=False)
    corr_df.to_csv(CORRELATION_CSV, index=False)
    pca_df.to_csv(PCA_CSV, index=False)

    full_metrics = daily_metrics[daily_metrics["window_name"].eq("full_aug_nov_2025")].copy()
    base_full = full_metrics[full_metrics["strategy_label"].eq("A_static18_fu")].iloc[0].to_dict()
    y_full = full_metrics[full_metrics["strategy_label"].eq("C_plus_y_DCE")].iloc[0].to_dict()
    ag_full = full_metrics[full_metrics["strategy_label"].eq("C_plus_ag_SHFE")].iloc[0].to_dict()
    full_sector = sector_contrib[sector_contrib["window_name"].eq("full_aug_nov_2025")].copy()
    base_sector = full_sector[full_sector["strategy_label"].eq("A_static18_fu")].sort_values("net_pnl")
    base_product = product_contrib[
        (product_contrib["window_name"].eq("full_aug_nov_2025"))
        & (product_contrib["strategy_label"].eq("A_static18_fu"))
    ].sort_values("net_pnl")
    base_pca = pca_df[
        (pca_df["window_name"].eq("full_aug_nov_2025"))
        & (pca_df["strategy_label"].eq("A_static18_fu"))
        & (pca_df["component"].eq("pc1_summary"))
    ]
    pc1_share = float(base_pca["pc1_variance_share"].iloc[0]) if not base_pca.empty else 0.0
    y_delta = delta_contrib[
        (delta_contrib["window_name"].eq("full_aug_nov_2025"))
        & (delta_contrib["candidate_label"].eq("C_plus_y_DCE"))
        & (delta_contrib["level"].eq("product"))
    ].sort_values("net_pnl_diff_vs_A")
    ag_delta = delta_contrib[
        (delta_contrib["window_name"].eq("full_aug_nov_2025"))
        & (delta_contrib["candidate_label"].eq("C_plus_ag_SHFE"))
        & (delta_contrib["level"].eq("product"))
    ].sort_values("net_pnl_diff_vs_A")

    summary = {
        "model_tag": MODEL_TAG,
        "window": "2025-08-01 to 2025-11-30",
        "judgement": {
            "common_risk_main_source": "asynchronous_multi_product_giveback_with_lc_tail_day",
            "high_correlation_common_factor_supported": False,
            "single_product_blame_supported": False,
            "promote_y_now": False,
            "promote_ag_now": False,
            "next_step": "test_a_portfolio_level_profit_giveback_or_heat_reduction_gate_without_changing_alpha",
        },
        "base_full_aug_nov": base_full,
        "y_full_aug_nov": y_full,
        "ag_full_aug_nov": ag_full,
        "base_pc1_variance_share_full_aug_nov": pc1_share,
        "base_worst_products_full_aug_nov": base_product.head(8).to_dict(orient="records"),
        "base_worst_sectors_full_aug_nov": base_sector.head(6).to_dict(orient="records"),
        "y_worst_delta_products_full_aug_nov": y_delta.head(6).to_dict(orient="records"),
        "ag_worst_delta_products_full_aug_nov": ag_delta.head(6).to_dict(orient="records"),
    }
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    report = f"""# Stage269 2025-08 至 2025-11 共同风险暴露拆解

## 设计

- 只读取 Stage267 已保存产物，不重跑策略，不改 Stage78-1 正式池。
- 对比三条路径：A=`static18+fu`，C_y=A+`y.DCE`，C_ag=A+`ag.SHFE`。
- 主窗口：`2025-08-01` 至 `2025-11-30`；辅助窗口包括 `ag` 峰谷、`y` 最弱63日、谷底后恢复段。
- 归因层级：日级亏损、品种贡献、板块粗分类、候选增量、开仓时风险状态、PnL相关性/PCA共同因子。

## 结论

```json
{json.dumps(summary["judgement"], ensure_ascii=False, indent=2)}
```

## 主窗口指标

{_format_markdown_table(daily_metrics[daily_metrics["window_name"].eq("full_aug_nov_2025")], ["strategy_label", "window_net_pnl", "window_return_pct_on_start_balance", "local_drawdown", "local_drawdown_pct", "window_trade_count", "window_slippage", "worst_day", "worst_day_net_pnl"])}

## 辅助窗口指标

{_format_markdown_table(daily_metrics[~daily_metrics["window_name"].eq("full_aug_nov_2025")], ["window_name", "strategy_label", "window_net_pnl", "window_return_pct_on_start_balance", "local_drawdown", "local_drawdown_pct", "window_trade_count", "worst_day", "worst_day_net_pnl"], 12)}

## A基准主窗口最亏品种

{_format_markdown_table(base_product, ["product_vt_symbol", "sector", "net_pnl", "holding_pnl", "trading_pnl", "slippage", "trade_count", "active_days"], 12)}

## A基准主窗口最亏板块

{_format_markdown_table(base_sector, ["sector", "net_pnl", "holding_pnl", "trading_pnl", "slippage", "trade_count", "product_count"], 8)}

## Y.DCE 相对 A 的主窗口增量

{_format_markdown_table(y_delta, ["product_vt_symbol", "sector", "net_pnl_diff_vs_A", "holding_pnl_diff_vs_A", "trading_pnl_diff_vs_A", "slippage_diff_vs_A", "trade_count_diff_vs_A"], 10)}

## Ag.SHFE 相对 A 的主窗口增量

{_format_markdown_table(ag_delta, ["product_vt_symbol", "sector", "net_pnl_diff_vs_A", "holding_pnl_diff_vs_A", "trading_pnl_diff_vs_A", "slippage_diff_vs_A", "trade_count_diff_vs_A"], 10)}

## A基准最差日共振

{_format_markdown_table(daily_extremes[(daily_extremes["window_name"].eq("full_aug_nov_2025")) & (daily_extremes["strategy_label"].eq("A_static18_fu"))].sort_values("net_pnl"), ["date", "net_pnl", "active_product_count", "long_product_count", "short_product_count", "negative_product_count", "top_loss_product", "top_loss_sector", "top_loss_net_pnl", "top_loss_share_of_negative_loss", "loss_concentration_hhi"], 10)}

## A基准开仓风险状态

{_format_markdown_table(entry_risk[(entry_risk["window_name"].eq("full_aug_nov_2025")) & (entry_risk["strategy_label"].eq("A_static18_fu"))], ["scope", "entry_count", "product_count", "avg_portfolio_drawdown_pct", "max_portfolio_drawdown_pct", "avg_projected_total_margin_after", "max_projected_total_margin_after", "avg_same_direction_active_count", "max_same_direction_max_corr"], 8)}

## A基准 PCA 共同因子

主窗口 A 基准前12个PnL活跃品种的第一主成分解释比例：`{pc1_share:.4f}`。

{_format_markdown_table(pca_df[(pca_df["window_name"].eq("full_aug_nov_2025")) & (pca_df["strategy_label"].eq("A_static18_fu")) & (pca_df["component"].eq("pc1_loading"))].sort_values("loading", key=lambda s: s.abs(), ascending=False), ["product_vt_symbol", "sector", "loading", "pc1_variance_share"], 12)}

## 输出文件

- `{DAILY_METRICS_CSV.name}`
- `{PRODUCT_CONTRIB_CSV.name}`
- `{SECTOR_CONTRIB_CSV.name}`
- `{DAILY_EXTREMES_CSV.name}`
- `{ENTRY_RISK_CSV.name}`
- `{DELTA_CONTRIB_CSV.name}`
- `{CORRELATION_CSV.name}`
- `{PCA_CSV.name}`
- `{SUMMARY_JSON.name}`
"""
    REPORT_MD.write_text(report, encoding="utf-8")
    print(json.dumps(summary["judgement"], ensure_ascii=False, indent=2))
    print(f"report={REPORT_MD}")


if __name__ == "__main__":
    main()
