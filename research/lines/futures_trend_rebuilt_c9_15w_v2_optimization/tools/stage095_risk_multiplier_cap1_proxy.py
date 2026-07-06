from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage095"
MODEL_TAG = "stage095_risk_multiplier_cap1_proxy_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage095_risk_multiplier_cap1_proxy"

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage095_risk_multiplier_cap1_proxy"
STAGES_DIR = LINE_DIR / "stages"
BACKTEST_OUT = ROOT / "examples" / "portfolio_backtesting" / "backtest_outputs"

STAGE167_CURVES = (
    BACKTEST_OUT
    / "qmt_roll_stage167_c9_live_15w_multiperiod_ai_audit_curves_stage167_c9_live_15w_multiperiod_ai_audit_v1.csv"
)
STAGE094_DIR = LINE_DIR / "outputs" / "stage094_stage167_closed_lot_entry_state_audit"
STAGE094_CLOSED_LOTS = (
    STAGE094_DIR
    / "rebuilt_c9_v2_stage094_stage167_closed_lot_entry_state_audit_closed_lots_stage094_stage167_closed_lot_entry_state_audit_v1.csv.gz"
)

CURVES_PATH = OUT / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv.gz"
LOT_DELTAS_PATH = OUT / f"{OUTPUT_PREFIX}_lot_deltas_{MODEL_TAG}.csv.gz"
PER_START_PATH = OUT / f"{OUTPUT_PREFIX}_per_start_summary_{MODEL_TAG}.csv"
VARIANT_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_variant_summary_{MODEL_TAG}.csv"
RETENTION_PATH = OUT / f"{OUTPUT_PREFIX}_retention_vs_official_{MODEL_TAG}.csv"
LOT_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_lot_audit_{MODEL_TAG}.csv"
PERIOD_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_entry_year_audit_{MODEL_TAG}.csv"
COVERAGE_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_coverage_audit_{MODEL_TAG}.csv"
INPUT_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_input_audit_{MODEL_TAG}.csv"
CHART_RETURN_DD_PATH = OUT / f"{OUTPUT_PREFIX}_return_dd_by_start_{MODEL_TAG}.png"
CHART_UNDERWATER_PATH = OUT / f"{OUTPUT_PREFIX}_underwater_by_start_{MODEL_TAG}.png"
CHART_RETENTION_PATH = OUT / f"{OUTPUT_PREFIX}_retention_by_start_{MODEL_TAG}.png"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

BASE_CAPITAL = 150_000.0
START_MONTH_MIN = "2020-01"
START_MONTH_MAX = "2026-01"
REQUESTED_END = pd.Timestamp("2026-06-30")

VARIANT_SPECS: dict[str, dict[str, Any]] = {
    "official_c9_15w_reference": {
        "label": "Official C9 15w",
        "selector": "none",
        "risk_cap": None,
        "note": "Stage167 official curve, no proxy adjustment.",
    },
    "dd30_rm2_cap1_proxy": {
        "label": "DD>=30% and risk_multiplier>=2 cap to 1",
        "selector": "portfolio_drawdown_pct>=0.30 and risk_multiplier>=2",
        "risk_cap": 1.0,
        "note": "Entry-time state proxy: when portfolio DD is already >=30% and effective risk multiplier is >=2, cap the multiplier back to 1.",
    },
    "rm2_cap1_proxy": {
        "label": "risk_multiplier>=2 cap to 1",
        "selector": "risk_multiplier>=2",
        "risk_cap": 1.0,
        "note": "Upper-bound diagnostic for right-tail damage; not a preferred promotion candidate.",
    },
}

EXTERNAL_RESEARCH = [
    {
        "source": "Concretum Group position sizing in trend following",
        "url": "https://concretumgroup.com/position-sizing-in-trend-following-comparing-volatility-targeting-volatility-parity-and-pyramiding/",
        "finding": "Position sizing can reshape risk and return, but smoother risk often trades off with upside capture.",
    },
    {
        "source": "Diva thesis on CTA position sizing",
        "url": "https://www.diva-portal.org/smash/get/diva2%3A730028/fulltext01.pdf",
        "finding": "Trend-following position-sizing research should compare drawdown controls against baseline performance, not only isolated losses.",
    },
    {
        "source": "SSRN trade sizing for drawdown and tail risk control",
        "url": "https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID3231836_code1554519.pdf?abstractid=2063848&mirid=1",
        "finding": "Sizing methods can target drawdown or tail risk, but they need full-path validation.",
    },
]


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if not np.isfinite(number) else number
    if isinstance(value, float):
        return None if not np.isfinite(value) else value
    try:
        if pd.isna(value) and not isinstance(value, (str, bytes)):
            return None
    except Exception:
        pass
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_无记录_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    return data.to_markdown(index=False)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _input_audit(paths: list[Path]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for path in paths:
        if path.exists():
            stat = path.stat()
            rows.append(
                {
                    "path": str(path),
                    "exists": True,
                    "bytes": int(stat.st_size),
                    "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                    "sha256": _sha256(path),
                }
            )
        else:
            rows.append({"path": str(path), "exists": False, "bytes": 0, "mtime": "", "sha256": ""})
    return pd.DataFrame(rows)


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    values = pd.to_numeric(equity, errors="coerce").ffill()
    peak = values.cummax()
    return (values / peak.replace(0.0, np.nan) - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0) * 100.0


def _daily_sharpe(equity: pd.Series) -> float:
    returns = pd.to_numeric(equity, errors="coerce").pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    if returns.empty:
        return 0.0
    std = float(returns.std(ddof=1))
    if std <= 0.0 or not np.isfinite(std):
        return 0.0
    return float(returns.mean() / std * np.sqrt(252.0))


def _max_consecutive_true(mask: pd.Series) -> int:
    best = 0
    current = 0
    for value in mask.astype(bool).tolist():
        if value:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return int(best)


def _numeric(frame: pd.DataFrame, column: str, default: float = np.nan) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce")


def load_official_curves() -> pd.DataFrame:
    data = pd.read_csv(STAGE167_CURVES, encoding="utf-8-sig")
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    data = data.dropna(subset=["date"])
    data = data[data["date"].le(REQUESTED_END)].copy()
    data["requested_start_month"] = data["requested_start_month"].astype(str)
    data = data[data["requested_start_month"].between(START_MONTH_MIN, START_MONTH_MAX)].copy()
    for column in ["account_equity", "net_pnl", "slippage", "trade_count", "account_capital"]:
        data[column] = pd.to_numeric(data.get(column, 0.0), errors="coerce").fillna(0.0)
    return data.sort_values(["requested_start_month", "date"]).reset_index(drop=True)


def load_lots() -> pd.DataFrame:
    lots = pd.read_csv(STAGE094_CLOSED_LOTS, encoding="utf-8-sig", compression="gzip")
    for column in ["entry_date", "exit_date"]:
        lots[column] = pd.to_datetime(lots[column], errors="coerce").dt.normalize()
    lots["requested_start_month"] = lots["requested_start_month"].astype(str)
    lots = lots[lots["requested_start_month"].between(START_MONTH_MIN, START_MONTH_MAX)].copy()
    lots = lots[lots["exit_date"].notna() & lots["exit_date"].le(REQUESTED_END)].copy()
    for column in [
        "realized_pnl",
        "risk_multiplier",
        "portfolio_drawdown_pct",
        "big_winner",
        "selected_volume",
        "ai_product_pool_rank",
    ]:
        lots[column] = pd.to_numeric(lots.get(column, np.nan), errors="coerce")
    return lots.reset_index(drop=True)


def _selector_mask(lots: pd.DataFrame, selector: str) -> pd.Series:
    risk_multiplier = _numeric(lots, "risk_multiplier")
    if selector == "risk_multiplier>=2":
        return risk_multiplier.ge(2.0)
    if selector == "portfolio_drawdown_pct>=0.30 and risk_multiplier>=2":
        drawdown = _numeric(lots, "portfolio_drawdown_pct")
        return risk_multiplier.ge(2.0) & drawdown.ge(0.30)
    return pd.Series(False, index=lots.index)


def build_lot_deltas(lots: pd.DataFrame) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for version, spec in VARIANT_SPECS.items():
        if version == "official_c9_15w_reference":
            continue
        mask = _selector_mask(lots, str(spec["selector"]))
        selected = lots.loc[mask].copy()
        risk_multiplier = _numeric(selected, "risk_multiplier")
        cap = float(spec["risk_cap"])
        scale = np.minimum(1.0, cap / risk_multiplier.replace(0.0, np.nan))
        scale = pd.Series(scale, index=selected.index).replace([np.inf, -np.inf], np.nan).fillna(1.0)
        selected["version"] = version
        selected["variant_label"] = spec["label"]
        selected["selector"] = spec["selector"]
        selected["risk_cap"] = cap
        selected["proxy_scale"] = scale.astype(float)
        selected["proxy_adjustment_pnl"] = selected["realized_pnl"].fillna(0.0) * (selected["proxy_scale"] - 1.0)
        selected["proxy_adjusted_lot_pnl"] = selected["realized_pnl"].fillna(0.0) * selected["proxy_scale"]
        selected["proxy_note"] = (
            "closed-lot exit-date proxy: cap effective risk multiplier and book the PnL adjustment on exit date; "
            "not a path-consistent true engine."
        )
        frames.append(selected)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True, sort=False)


def build_curves(official: pd.DataFrame, lot_deltas: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for version, spec in VARIANT_SPECS.items():
        if version == "official_c9_15w_reference":
            base = official.copy()
            base["version"] = version
            base["variant_label"] = spec["label"]
            base["proxy_daily_adjustment_pnl"] = 0.0
            base["proxy_cumulative_adjustment_pnl"] = 0.0
            base["proxy_selected_lot_count"] = 0
            base["proxy_active"] = 0
            base["proxy_note"] = spec["note"]
            rows.append(base)
            continue
        delta = (
            lot_deltas[lot_deltas["version"].eq(version)]
            .groupby(["requested_start_month", "exit_date"], as_index=False)
            .agg(
                proxy_daily_adjustment_pnl=("proxy_adjustment_pnl", "sum"),
                proxy_selected_lot_count=("proxy_adjustment_pnl", "size"),
            )
            .rename(columns={"exit_date": "date"})
        )
        merged = official.merge(delta, on=["requested_start_month", "date"], how="left")
        merged["proxy_daily_adjustment_pnl"] = pd.to_numeric(
            merged["proxy_daily_adjustment_pnl"], errors="coerce"
        ).fillna(0.0)
        merged["proxy_selected_lot_count"] = pd.to_numeric(
            merged["proxy_selected_lot_count"], errors="coerce"
        ).fillna(0).astype(int)
        merged["version"] = version
        merged["variant_label"] = spec["label"]
        frames: list[pd.DataFrame] = []
        for _, group in merged.groupby("requested_start_month", sort=True):
            g = group.sort_values("date").copy()
            g["proxy_cumulative_adjustment_pnl"] = g["proxy_daily_adjustment_pnl"].cumsum()
            g["account_equity"] = g["account_equity"] + g["proxy_cumulative_adjustment_pnl"]
            g["proxy_active"] = g["proxy_selected_lot_count"].gt(0).astype(int)
            g["proxy_note"] = spec["note"]
            frames.append(g)
        rows.append(pd.concat(frames, ignore_index=True, sort=False))
    curves = pd.concat(rows, ignore_index=True, sort=False)
    curves["nav"] = pd.to_numeric(curves["account_equity"], errors="coerce") / BASE_CAPITAL
    curves["drawdown_pct"] = (
        curves.groupby(["version", "requested_start_month"], group_keys=False)["account_equity"].apply(_drawdown_pct)
    )
    return curves.sort_values(["version", "requested_start_month", "date"]).reset_index(drop=True)


def summarize_curve(frame: pd.DataFrame) -> dict[str, Any]:
    frame = frame.sort_values("date").reset_index(drop=True)
    equity = pd.to_numeric(frame["account_equity"], errors="coerce").ffill()
    drawdown = _drawdown_pct(equity)
    below = equity < BASE_CAPITAL - 1e-9
    nonzero_net = pd.to_numeric(frame.get("net_pnl", 0.0), errors="coerce").fillna(0.0).ne(0.0)
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "version": frame["version"].iloc[0],
        "variant_label": frame["variant_label"].iloc[0],
        "requested_start_month": frame["requested_start_month"].iloc[0],
        "actual_start": frame["date"].iloc[0].date().isoformat(),
        "actual_end": frame["date"].iloc[-1].date().isoformat(),
        "trading_days": int(len(frame)),
        "account_capital": BASE_CAPITAL,
        "end_equity": float(equity.iloc[-1]),
        "total_return_pct": float((equity.iloc[-1] / BASE_CAPITAL - 1.0) * 100.0),
        "max_drawdown_pct": float(drawdown.min()),
        "sharpe": _daily_sharpe(equity),
        "min_equity": float(equity.min()),
        "days_below_initial": int(below.sum()),
        "max_consecutive_below_initial_days": _max_consecutive_true(below),
        "total_slippage": float(pd.to_numeric(frame.get("slippage", 0.0), errors="coerce").fillna(0.0).sum()),
        "total_trade_count": float(pd.to_numeric(frame.get("trade_count", 0.0), errors="coerce").fillna(0.0).sum()),
        "nonzero_net_win_rate": float(
            pd.to_numeric(frame.loc[nonzero_net, "net_pnl"], errors="coerce").gt(0.0).mean()
        )
        if bool(nonzero_net.any())
        else np.nan,
        "cost_trade_winrate_scope": "official_original_curve_not_proxy_recomputed",
        "proxy_adjustment_pnl_sum": float(
            pd.to_numeric(frame["proxy_daily_adjustment_pnl"], errors="coerce").fillna(0.0).sum()
        ),
        "proxy_active_days": int(pd.to_numeric(frame["proxy_active"], errors="coerce").fillna(0).sum()),
        "proxy_selected_lot_count": int(pd.to_numeric(frame["proxy_selected_lot_count"], errors="coerce").fillna(0).sum()),
    }


def build_summaries(curves: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    per_start = pd.DataFrame(
        [
            summarize_curve(group)
            for _, group in curves.groupby(["version", "requested_start_month"], sort=True)
        ]
    )
    official = per_start[per_start["version"].eq("official_c9_15w_reference")][
        [
            "requested_start_month",
            "total_return_pct",
            "max_drawdown_pct",
            "days_below_initial",
            "max_consecutive_below_initial_days",
            "end_equity",
        ]
    ].rename(
        columns={
            "total_return_pct": "official_return_pct",
            "max_drawdown_pct": "official_max_drawdown_pct",
            "days_below_initial": "official_days_below_initial",
            "max_consecutive_below_initial_days": "official_max_consecutive_below_initial_days",
            "end_equity": "official_end_equity",
        }
    )
    retention = per_start.merge(official, on="requested_start_month", how="left")
    retention = retention[~retention["version"].eq("official_c9_15w_reference")].copy()
    retention["return_retention_ratio"] = np.where(
        retention["official_return_pct"].abs() > 1e-12,
        retention["total_return_pct"] / retention["official_return_pct"],
        np.nan,
    )
    retention["end_equity_ratio"] = np.where(
        retention["official_end_equity"].abs() > 1e-12,
        retention["end_equity"] / retention["official_end_equity"],
        np.nan,
    )
    retention["return_delta_pp"] = retention["total_return_pct"] - retention["official_return_pct"]
    retention["drawdown_improvement_pp"] = retention["max_drawdown_pct"] - retention["official_max_drawdown_pct"]
    retention["days_below_delta"] = retention["days_below_initial"] - retention["official_days_below_initial"]
    retention["max_consecutive_below_delta"] = (
        retention["max_consecutive_below_initial_days"] - retention["official_max_consecutive_below_initial_days"]
    )

    official_row = {
        "worst_drawdown_pct": float(
            per_start.loc[per_start["version"].eq("official_c9_15w_reference"), "max_drawdown_pct"].min()
        ),
        "max_days_below_initial": int(
            per_start.loc[per_start["version"].eq("official_c9_15w_reference"), "days_below_initial"].max()
        ),
        "max_consecutive_below_initial_days": int(
            per_start.loc[
                per_start["version"].eq("official_c9_15w_reference"), "max_consecutive_below_initial_days"
            ].max()
        ),
    }
    rows: list[dict[str, Any]] = []
    for version, group in per_start.groupby("version", sort=False):
        ret_group = retention[retention["version"].eq(version)]
        early_ret = ret_group[ret_group["requested_start_month"].isin(["2020-01", "2020-07", "2021-01"])]
        rows.append(
            {
                "sample": "starts_2020_2026",
                "version": version,
                "variant_label": group["variant_label"].iloc[0],
                "start_count": int(len(group)),
                "positive_count": int(group["total_return_pct"].gt(0.0).sum()),
                "min_return_pct": float(group["total_return_pct"].min()),
                "median_return_pct": float(group["total_return_pct"].median()),
                "max_return_pct": float(group["total_return_pct"].max()),
                "min_return_retention_ratio": float(ret_group["return_retention_ratio"].min())
                if not ret_group.empty
                else 1.0,
                "median_return_retention_ratio": float(ret_group["return_retention_ratio"].median())
                if not ret_group.empty
                else 1.0,
                "early_2020_2021_min_retention_ratio": float(early_ret["return_retention_ratio"].min())
                if not early_ret.empty
                else np.nan,
                "early_2020_2021_median_return_delta_pp": float(early_ret["return_delta_pp"].median())
                if not early_ret.empty
                else np.nan,
                "worst_drawdown_pct": float(group["max_drawdown_pct"].min()),
                "median_drawdown_pct": float(group["max_drawdown_pct"].median()),
                "max_days_below_initial": int(group["days_below_initial"].max()),
                "median_days_below_initial": float(group["days_below_initial"].median()),
                "max_consecutive_below_initial_days": int(group["max_consecutive_below_initial_days"].max()),
                "median_consecutive_below_initial_days": float(group["max_consecutive_below_initial_days"].median()),
                "total_proxy_adjustment_pnl": float(group["proxy_adjustment_pnl_sum"].sum()),
                "total_proxy_selected_lots": int(group["proxy_selected_lot_count"].sum()),
                "total_slippage_sum": float(group["total_slippage"].sum()),
                "total_trade_count_sum": float(group["total_trade_count"].sum()),
                "nonzero_net_win_rate_mean": float(group["nonzero_net_win_rate"].mean()),
            }
        )
    summary = pd.DataFrame(rows)
    for idx, row in summary.iterrows():
        if row["version"] == "official_c9_15w_reference":
            summary.loc[idx, "passes_new_goal_vs_official"] = False
            continue
        summary.loc[idx, "passes_new_goal_vs_official"] = bool(
            row["min_return_retention_ratio"] >= 0.50
            and row["worst_drawdown_pct"] > official_row["worst_drawdown_pct"]
            and row["max_days_below_initial"] <= official_row["max_days_below_initial"]
            and row["max_consecutive_below_initial_days"]
            <= official_row["max_consecutive_below_initial_days"]
        )
    return per_start, summary, retention


def build_lot_audits(lots: pd.DataFrame, lot_deltas: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    missing_risk = lots["risk_multiplier"].isna()
    missing_dd = lots["portfolio_drawdown_pct"].isna()
    duplicate_keys = [
        "vt_symbol",
        "product",
        "direction",
        "entry_date",
        "exit_date",
        "entry_price",
        "exit_price",
        "volume",
        "realized_pnl",
    ]
    key_frame = lots[[column for column in duplicate_keys if column in lots.columns]].copy()
    unique_events = int(len(key_frame.drop_duplicates())) if not key_frame.empty else 0
    coverage = pd.DataFrame(
        [
            {
                "closed_lot_rows": int(len(lots)),
                "unique_event_approx_count": unique_events,
                "approx_duplicate_rate": float(1.0 - unique_events / len(lots)) if len(lots) else np.nan,
                "risk_multiplier_missing_count": int(missing_risk.sum()),
                "risk_multiplier_missing_pnl": float(lots.loc[missing_risk, "realized_pnl"].sum()),
                "portfolio_dd_missing_count": int(missing_dd.sum()),
                "portfolio_dd_missing_pnl": float(lots.loc[missing_dd, "realized_pnl"].sum()),
                "order_api_calls": 0,
                "ctp_connected": False,
            }
        ]
    )
    lot_rows: list[dict[str, Any]] = []
    period_rows: list[dict[str, Any]] = []
    for version, selected in lot_deltas.groupby("version", sort=True):
        positive = selected.loc[selected["realized_pnl"].gt(0), "realized_pnl"].sum()
        negative_abs = -selected.loc[selected["realized_pnl"].lt(0), "realized_pnl"].sum()
        big_winner_pnl = selected.loc[selected["big_winner"].fillna(0).gt(0), "realized_pnl"].clip(lower=0.0).sum()
        lot_rows.append(
            {
                "version": version,
                "variant_label": selected["variant_label"].iloc[0],
                "selector": selected["selector"].iloc[0],
                "lot_count": int(len(selected)),
                "start_count": int(selected["requested_start_month"].nunique()),
                "selected_realized_pnl": float(selected["realized_pnl"].sum()),
                "selected_positive_pnl": float(positive),
                "selected_negative_abs_pnl": float(negative_abs),
                "proxy_adjustment_pnl": float(selected["proxy_adjustment_pnl"].sum()),
                "mean_proxy_scale": float(selected["proxy_scale"].mean()),
                "big_winner_count": int(selected["big_winner"].fillna(0).gt(0).sum()),
                "big_winner_pnl": float(big_winner_pnl),
                "entry_year_2021_realized_pnl": float(
                    selected.loc[pd.to_datetime(selected["entry_date"]).dt.year.eq(2021), "realized_pnl"].sum()
                ),
                "entry_year_2021_adjustment_pnl": float(
                    selected.loc[pd.to_datetime(selected["entry_date"]).dt.year.eq(2021), "proxy_adjustment_pnl"].sum()
                ),
            }
        )
        with_year = selected.copy()
        with_year["entry_year"] = pd.to_datetime(with_year["entry_date"], errors="coerce").dt.year
        period = (
            with_year.groupby(["version", "variant_label", "entry_year"], as_index=False)
            .agg(
                lot_count=("realized_pnl", "size"),
                realized_pnl=("realized_pnl", "sum"),
                proxy_adjustment_pnl=("proxy_adjustment_pnl", "sum"),
                positive_pnl=("realized_pnl", lambda s: float(s[s > 0].sum())),
                negative_abs_pnl=("realized_pnl", lambda s: float(-s[s < 0].sum())),
            )
            .copy()
        )
        period_rows.extend(period.to_dict("records"))
    return pd.DataFrame(lot_rows), pd.DataFrame(period_rows), coverage


def write_charts(per_start: pd.DataFrame, retention: pd.DataFrame) -> None:
    versions = list(VARIANT_SPECS.keys())
    fig, axes = plt.subplots(2, 1, figsize=(14, 9), sharex=True)
    for version in versions:
        data = per_start[per_start["version"].eq(version)].sort_values("requested_start_month")
        axes[0].plot(data["requested_start_month"], data["total_return_pct"], marker="o", label=VARIANT_SPECS[version]["label"])
        axes[1].plot(data["requested_start_month"], data["max_drawdown_pct"], marker="o", label=VARIANT_SPECS[version]["label"])
    axes[0].set_title("Stage095 return by half-year start")
    axes[0].set_ylabel("total return %")
    axes[0].grid(alpha=0.25)
    axes[1].set_title("Stage095 max drawdown by half-year start")
    axes[1].set_ylabel("max drawdown %")
    axes[1].tick_params(axis="x", rotation=45)
    axes[1].grid(alpha=0.25)
    axes[0].legend(ncol=2, fontsize=8)
    fig.tight_layout()
    fig.savefig(CHART_RETURN_DD_PATH, dpi=160)
    plt.close(fig)

    fig, axes = plt.subplots(2, 1, figsize=(14, 9), sharex=True)
    for version in versions:
        data = per_start[per_start["version"].eq(version)].sort_values("requested_start_month")
        axes[0].plot(data["requested_start_month"], data["days_below_initial"], marker="o", label=VARIANT_SPECS[version]["label"])
        axes[1].plot(
            data["requested_start_month"],
            data["max_consecutive_below_initial_days"],
            marker="o",
            label=VARIANT_SPECS[version]["label"],
        )
    axes[0].set_title("Stage095 days below initial capital")
    axes[0].set_ylabel("days")
    axes[0].grid(alpha=0.25)
    axes[1].set_title("Stage095 max consecutive days below initial capital")
    axes[1].set_ylabel("days")
    axes[1].tick_params(axis="x", rotation=45)
    axes[1].grid(alpha=0.25)
    axes[0].legend(ncol=2, fontsize=8)
    fig.tight_layout()
    fig.savefig(CHART_UNDERWATER_PATH, dpi=160)
    plt.close(fig)

    fig, axes = plt.subplots(3, 1, figsize=(14, 11), sharex=True)
    for version in [value for value in versions if value != "official_c9_15w_reference"]:
        data = retention[retention["version"].eq(version)].sort_values("requested_start_month")
        axes[0].plot(data["requested_start_month"], data["return_retention_ratio"], marker="o", label=VARIANT_SPECS[version]["label"])
        axes[1].plot(data["requested_start_month"], data["drawdown_improvement_pp"], marker="o", label=VARIANT_SPECS[version]["label"])
        axes[2].plot(data["requested_start_month"], data["max_consecutive_below_delta"], marker="o", label=VARIANT_SPECS[version]["label"])
    axes[0].axhline(0.5, color="black", linewidth=1, linestyle="--")
    axes[0].set_title("Stage095 return retention vs official")
    axes[0].set_ylabel("retention")
    axes[1].axhline(0.0, color="black", linewidth=1, linestyle="--")
    axes[1].set_title("Drawdown improvement vs official")
    axes[1].set_ylabel("pp")
    axes[2].axhline(0.0, color="black", linewidth=1, linestyle="--")
    axes[2].set_title("Max consecutive underwater days delta vs official")
    axes[2].set_ylabel("days")
    axes[2].tick_params(axis="x", rotation=45)
    for axis in axes:
        axis.grid(alpha=0.25)
        axis.legend(ncol=2, fontsize=8)
    fig.tight_layout()
    fig.savefig(CHART_RETENTION_PATH, dpi=160)
    plt.close(fig)


def make_decision(variant_summary: pd.DataFrame) -> dict[str, Any]:
    candidates = variant_summary[
        variant_summary["version"].ne("official_c9_15w_reference")
        & variant_summary["passes_new_goal_vs_official"].astype(bool)
    ].copy()
    best_candidate = ""
    if not candidates.empty:
        best_candidate = str(
            candidates.sort_values(
                ["max_consecutive_below_initial_days", "worst_drawdown_pct", "min_return_retention_ratio"],
                ascending=[True, False, False],
            ).iloc[0]["version"]
        )
    if best_candidate:
        overfit_after = (
            "否，但仍需谨慎。本阶段没有根据结果改阈值；候选只能进入独立审查，不能直接 true engine 或上线。"
        )
        continue_after = "有条件。只有独立审查确认统计口径后，才允许进入 true engine A/C。"
    else:
        overfit_after = (
            "否。本阶段没有根据失败结果改 DD 阈值、risk cap、品种或方向；继续救该形状会转为过拟合。"
        )
        continue_after = "低。两个固定 proxy 都未同时改善收益保留、最大回撤和水下期，不应继续在该字段族上救参。"
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": "stage095_proxy_candidate_needs_review_before_true_engine" if best_candidate else "stage095_no_proxy_candidate",
        "candidate_rule_count": int(len(candidates)),
        "best_candidate": best_candidate,
        "promote_to_true_engine": False,
        "next_step": (
            "先由独立 agent 审查 Stage095；审查通过后再考虑 true engine A/C，不能直接上线。"
            if best_candidate
            else "不进入 true engine；该 risk_multiplier cap 形状停止，继续只能转更强 PIT 信息源或不同账户外层。"
        ),
        "strategy_changed": False,
        "true_engine_run": False,
        "order_api_calls": 0,
        "ctp_connected": False,
        "overfit_before": (
            "中等。候选来自 Stage094 全样本 closed-lot outcome，但本阶段冻结两个低自由度形状，不扫阈值、品种、方向或日期。"
        ),
        "overfit_after": overfit_after,
        "continue_before": "有。独立审查指出 DD>=30% and risk_multiplier>=2 值得做无前视 proxy。",
        "continue_after": continue_after,
    }


def write_report(
    per_start: pd.DataFrame,
    variant_summary: pd.DataFrame,
    retention: pd.DataFrame,
    lot_audit: pd.DataFrame,
    period_audit: pd.DataFrame,
    coverage_audit: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    research_rows = "\n".join(
        f"| {item['source']} | {item['url']} | {item['finding']} |" for item in EXTERNAL_RESEARCH
    )
    text = f"""# {STAGE} Risk Multiplier Cap1 Closed-Lot Exit-Date Proxy

## 外部调研与判断

| source | url | finding |
| --- | --- | --- |
{research_rows}

我的判断：趋势策略的风险预算可以做动态约束，但核心风险是错杀右尾。本阶段只验证 `risk_multiplier>=2` 加风险状态的低自由度降风险 proxy，不能当 true engine 或上线证据。

## Proxy Arms

| version | label | selector | note |
| --- | --- | --- | --- |
| official_c9_15w_reference | Official C9 15w | none | Stage167 baseline |
| dd30_rm2_cap1_proxy | DD>=30% and risk_multiplier>=2 cap to 1 | portfolio_drawdown_pct>=0.30 and risk_multiplier>=2 | preferred conservative proxy |
| rm2_cap1_proxy | risk_multiplier>=2 cap to 1 | risk_multiplier>=2 | upper-bound diagnostic |

## Variant Summary

{_md_table(variant_summary)}

## Per Start Summary

{_md_table(per_start.sort_values(["version", "requested_start_month"]), 80)}

## Retention vs Official

{_md_table(retention.sort_values(["version", "requested_start_month"]), 80)}

## Lot Audit

{_md_table(lot_audit)}

## Entry Year Audit

{_md_table(period_audit.sort_values(["version", "entry_year"]), 80)}

## Coverage Audit

{_md_table(coverage_audit)}

## Decision

```json
{json.dumps(_json_safe(decision), ensure_ascii=False, indent=2)}
```

## 口径限制

- 本阶段是 closed-lot exit-date proxy：命中 lot 的盈亏按 `min(1, 1/risk_multiplier)` 缩放，调整额记在退出日，再重建日线权益。
- 条件字段来自入场时可见状态；但候选来自 Stage094 事后 outcome 审计，所以不能视为 OOS 证明。
- 未重算真实保证金、后续 sizing、换月、开仓重试、手续费/滑点节省和后续 DD 内生变化；所有这些必须在 true engine 中验证。
- `total_slippage`、`total_trade_count`、`nonzero_net_win_rate` 是官方原始曲线字段，不是 proxy 后真实重算成本或胜率。
- 不连接 CTP，不调用订单 API，不修改官方实盘配置。

## 输出

- curves：`{CURVES_PATH}`
- lot_deltas：`{LOT_DELTAS_PATH}`
- per_start：`{PER_START_PATH}`
- variant_summary：`{VARIANT_SUMMARY_PATH}`
- retention：`{RETENTION_PATH}`
- lot_audit：`{LOT_AUDIT_PATH}`
- entry_year_audit：`{PERIOD_AUDIT_PATH}`
- coverage_audit：`{COVERAGE_AUDIT_PATH}`
- charts：`{CHART_RETURN_DD_PATH}`、`{CHART_UNDERWATER_PATH}`、`{CHART_RETENTION_PATH}`
"""
    REPORT_PATH.write_text(text, encoding="utf-8")


def write_stage_record(
    per_start: pd.DataFrame,
    variant_summary: pd.DataFrame,
    retention: pd.DataFrame,
    lot_audit: pd.DataFrame,
    period_audit: pd.DataFrame,
    coverage_audit: pd.DataFrame,
    decision: dict[str, Any],
) -> Path:
    now = datetime.now()
    path = STAGES_DIR / f"{now:%Y%m%d_%H%M}_stage095_risk_multiplier_cap1_proxy.md"
    text = f"""# Stage095 risk_multiplier cap1 closed-lot exit-date proxy

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{now:%Y-%m-%d %H:%M} CST
- 阶段性质：A/C 前置 proxy，不是真实引擎
- 是否重要突破：{'是，proxy 出现候选但需独立审查' if decision['candidate_rule_count'] else '否'}
- 是否触发A/B：否；本阶段只是 true engine 前置筛查

## 外部调研与判断

- 动态仓位和 drawdown/risk sizing 在趋势策略里有研究基础，但会天然压低右尾。
- 我的判断：只允许冻结 `DD>=30% and risk_multiplier>=2 cap to 1` 与全量 `risk_multiplier>=2 cap to 1` 两个低自由度 proxy；不扫 DD 阈值、risk cap、品种、方向或日期。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage095_risk_multiplier_cap1_proxy.py`
- 修改脚本：无正式交易入口修改。
- 删除脚本：无。
- 新增参数：`risk_cap=1.0`；两个固定 selector。
- 修改参数：无正式参数修改。
- 删除参数：无。

## 回测/归因参数

- 基准：Stage167 official C9/15w 日线曲线。
- proxy 输入：Stage094 closed lots。
- 起点：`2020-01` 到 `2026-01` 逐半年，终点 `2026-06-30`。
- 成本：底层 C9 成本保持不变；proxy 未计入降手数带来的手续费/滑点节省。
- `total_slippage`、`total_trade_count`、`nonzero_net_win_rate` 是官方原始曲线字段，不是 proxy 后真实重算成本或胜率。
- 订单/API：`0`；CTP connected：`False`。

## Variant Summary

{_md_table(variant_summary)}

## Per Start Summary

{_md_table(per_start.sort_values(["version", "requested_start_month"]), 80)}

## Retention vs Official

{_md_table(retention.sort_values(["version", "requested_start_month"]), 80)}

## Lot Audit

{_md_table(lot_audit)}

## Entry Year Audit

{_md_table(period_audit.sort_values(["version", "entry_year"]), 80)}

## Coverage Audit

{_md_table(coverage_audit)}

## 结论

- 决策：`{decision['decision']}`
- 候选数：`{decision['candidate_rule_count']}`
- 最优候选：`{decision['best_candidate']}`
- 是否直接进入 true engine：`{decision['promote_to_true_engine']}`
- 下一步：{decision['next_step']}

## 过拟合反思

- 运行前：{decision['overfit_before']}
- 运行后：{decision['overfit_after']}

## 继续价值反思

- 运行前：{decision['continue_before']}
- 运行后：{decision['continue_after']}

## TODO

- 拉独立 agent 审查代码、统计口径、右尾误伤和是否真的满足 50% 收益保留 + 降低水下/回撤。
- 若审查不通过，不进 true engine；若通过，再做真实引擎 A/C。
"""
    path.write_text(text, encoding="utf-8")
    return path


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    official = load_official_curves()
    lots = load_lots()
    lot_deltas = build_lot_deltas(lots)
    curves = build_curves(official, lot_deltas)
    per_start, variant_summary, retention = build_summaries(curves)
    lot_audit, period_audit, coverage_audit = build_lot_audits(lots, lot_deltas)
    input_audit = _input_audit([STAGE167_CURVES, STAGE094_CLOSED_LOTS])
    decision = make_decision(variant_summary)

    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig", compression="gzip")
    lot_deltas.to_csv(LOT_DELTAS_PATH, index=False, encoding="utf-8-sig", compression="gzip")
    per_start.to_csv(PER_START_PATH, index=False, encoding="utf-8-sig")
    variant_summary.to_csv(VARIANT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    retention.to_csv(RETENTION_PATH, index=False, encoding="utf-8-sig")
    lot_audit.to_csv(LOT_AUDIT_PATH, index=False, encoding="utf-8-sig")
    period_audit.to_csv(PERIOD_AUDIT_PATH, index=False, encoding="utf-8-sig")
    coverage_audit.to_csv(COVERAGE_AUDIT_PATH, index=False, encoding="utf-8-sig")
    input_audit.to_csv(INPUT_AUDIT_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    write_charts(per_start, retention)
    write_report(per_start, variant_summary, retention, lot_audit, period_audit, coverage_audit, decision)
    stage_path = write_stage_record(per_start, variant_summary, retention, lot_audit, period_audit, coverage_audit, decision)
    print(
        json.dumps(
            _json_safe(
                {
                    "decision": decision,
                    "stage_path": stage_path,
                    "report_path": REPORT_PATH,
                    "variant_summary_path": VARIANT_SUMMARY_PATH,
                }
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
