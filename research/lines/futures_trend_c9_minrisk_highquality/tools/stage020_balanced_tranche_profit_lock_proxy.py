from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Any
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage020"
MODEL_TAG = "stage020_balanced_tranche_profit_lock_proxy_v1"
OUTPUT_PREFIX = "qmt_roll_stage020_c9_minrisk_balanced_tranche_profit_lock_proxy"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
if str(EXAMPLE_DIR) not in sys.path:
    sys.path.insert(0, str(EXAMPLE_DIR))

from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage020_balanced_tranche_profit_lock_proxy"
STAGE019_DIR = LINE_DIR / "outputs" / "stage019_no_follow_light_shave_true_engine"

CAPITAL = 150_000.0
TRADING_DAYS_PER_YEAR = 252

CURVE_IN = (
    STAGE019_DIR
    / "qmt_roll_stage019_c9_minrisk_no_follow_light_shave_true_engine_curve_"
    "stage019_no_follow_light_shave_true_engine_v1.csv"
)

LEDGER_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_ledger_{MODEL_TAG}.csv"
TRANSFERS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_transfers_{MODEL_TAG}.csv"
METRICS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_metrics_{MODEL_TAG}.csv"
YEAR_STATS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_stats_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_path_drawdown_chart_{MODEL_TAG}.png"
ACCOUNTS_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_account_layers_chart_{MODEL_TAG}.png"
TRANSFERS_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_transfer_ladder_chart_{MODEL_TAG}.png"
SCATTER_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_return_drawdown_scatter_{MODEL_TAG}.png"
YEAR_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_return_heatmap_{MODEL_TAG}.png"


@dataclass(frozen=True)
class TranchePolicy:
    name: str
    production_floor: float
    sweep_start: float
    sweep_ratio: float
    lock_ratio: float
    expansion_ratio: float


BALANCED_TRANCHE_V1 = TranchePolicy(
    name="balanced_tranche_v1_c9_15w_stage232_reuse",
    production_floor=CAPITAL,
    sweep_start=5_000_000.0,
    sweep_ratio=0.50,
    lock_ratio=0.60,
    expansion_ratio=0.40,
)


def _json_safe(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if np.isnan(value) or np.isinf(value):
            return None
        return float(value)
    if isinstance(value, (pd.Timestamp,)):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _prepare_official_curve() -> pd.DataFrame:
    data = _read_csv(CURVE_IN)
    if "arm" in data.columns:
        data = data[data["arm"].eq("A_official_stage847_c9_15w")].copy()
    elif "variant" in data.columns:
        data = data[data["variant"].astype(str).str.contains("official_live_stage847_c9_15w")].copy()
    if data.empty:
        raise RuntimeError("Stage019 curve does not contain the official A arm")

    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data = data.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    for column in [
        "account_equity",
        "net_pnl",
        "broker10_total_margin_exact",
        "broker10_margin_to_equity_pct",
        "slippage",
        "trade_count",
    ]:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce").fillna(0.0)
        else:
            data[column] = 0.0
    data["official_daily_return"] = data["account_equity"].pct_change().replace([np.inf, -np.inf], np.nan).fillna(0.0)
    data["official_drawdown_pct"] = _drawdown_pct(data["account_equity"])
    return data[
        [
            "date",
            "account_equity",
            "net_pnl",
            "official_daily_return",
            "official_drawdown_pct",
            "broker10_total_margin_exact",
            "broker10_margin_to_equity_pct",
            "slippage",
            "trade_count",
        ]
    ].copy()


def _is_month_end(dates: pd.Series, idx: int) -> bool:
    if idx >= len(dates) - 1:
        return True
    current = dates.iloc[idx]
    nxt = dates.iloc[idx + 1]
    return current.month != nxt.month or current.year != nxt.year


def _drawdown_pct(equity: pd.Series | np.ndarray) -> pd.Series:
    values = pd.Series(equity, dtype="float64")
    hwm = values.cummax()
    return (values / hwm - 1.0) * 100.0


def _sharpe_from_equity(equity: pd.Series) -> float:
    returns = equity.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    if returns.empty or returns.std(ddof=0) <= 1e-12:
        return np.nan
    return float(returns.mean() / returns.std(ddof=0) * np.sqrt(TRADING_DAYS_PER_YEAR))


def _ulcer_pct(drawdown_pct: pd.Series) -> float:
    dd = pd.to_numeric(drawdown_pct, errors="coerce").fillna(0.0).clip(upper=0.0)
    return float(np.sqrt(np.mean(np.square(dd))))


def _simulate_official(official: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    records: list[dict[str, Any]] = []
    for _, row in official.iterrows():
        total_equity = float(row["account_equity"])
        records.append(
            {
                "date": row["date"],
                "arm": "A_official_full_reinvest",
                "policy": "official_full_reinvest",
                "daily_return_source": float(row["official_daily_return"]),
                "source_official_equity": float(row["account_equity"]),
                "production_before_transfer": total_equity,
                "production_equity": total_equity,
                "locked_equity": 0.0,
                "expansion_equity": 0.0,
                "total_equity": total_equity,
                "sweep_amount": 0.0,
                "refill_amount": 0.0,
                "event": "none",
                "risk_scale_to_official": 1.0,
                "broker10_margin_scaled": float(row["broker10_total_margin_exact"]),
                "broker10_margin_to_production_pct": float(row["broker10_margin_to_equity_pct"]),
                "broker10_margin_to_total_wealth_pct": float(row["broker10_margin_to_equity_pct"]),
                "official_broker10_margin_to_equity_pct": float(row["broker10_margin_to_equity_pct"]),
                "slippage_scaled": float(row["slippage"]),
                "trade_count_reference": float(row["trade_count"]),
                "threshold_gap_to_next_sweep": max(BALANCED_TRANCHE_V1.sweep_start - total_equity, 0.0),
            }
        )
    ledger = pd.DataFrame(records)
    ledger["total_drawdown_pct"] = _drawdown_pct(ledger["total_equity"]).to_numpy()
    ledger["production_drawdown_pct"] = _drawdown_pct(ledger["production_equity"]).to_numpy()
    transfers = pd.DataFrame(
        columns=[
            "date",
            "arm",
            "event_type",
            "sweep_amount",
            "locked_add",
            "expansion_add",
            "refill_amount",
            "production_after",
            "locked_after",
            "expansion_after",
            "total_after",
        ]
    )
    return ledger, transfers


def _simulate_balanced_tranche(official: pd.DataFrame, policy: TranchePolicy) -> tuple[pd.DataFrame, pd.DataFrame]:
    production = CAPITAL
    locked = 0.0
    expansion = 0.0
    records: list[dict[str, Any]] = []
    transfers: list[dict[str, Any]] = []
    dates = official["date"].reset_index(drop=True)

    for idx, row in official.reset_index(drop=True).iterrows():
        date = dates.iloc[idx]
        daily_return = float(row["official_daily_return"])
        source_official_equity = max(float(row["account_equity"]), 1e-9)
        production *= 1.0 + daily_return
        production = max(production, 0.0)
        production_before_transfer = production

        refill = 0.0
        sweep = 0.0
        event = "none"
        if _is_month_end(dates, idx):
            if production < policy.production_floor and expansion > 0.0:
                refill = min(policy.production_floor - production, expansion)
                production += refill
                expansion -= refill
                event = "refill"
                transfers.append(
                    {
                        "date": date,
                        "arm": policy.name,
                        "event_type": "refill",
                        "sweep_amount": 0.0,
                        "locked_add": 0.0,
                        "expansion_add": -refill,
                        "refill_amount": refill,
                        "production_after": production,
                        "locked_after": locked,
                        "expansion_after": expansion,
                        "total_after": production + locked + expansion,
                    }
                )
            if production > policy.sweep_start:
                sweep = (production - policy.sweep_start) * policy.sweep_ratio
                production -= sweep
                locked_add = sweep * policy.lock_ratio
                expansion_add = sweep * policy.expansion_ratio
                locked += locked_add
                expansion += expansion_add
                event = "sweep" if event == "none" else "refill_and_sweep"
                transfers.append(
                    {
                        "date": date,
                        "arm": policy.name,
                        "event_type": "sweep",
                        "sweep_amount": sweep,
                        "locked_add": locked_add,
                        "expansion_add": expansion_add,
                        "refill_amount": 0.0,
                        "production_after": production,
                        "locked_after": locked,
                        "expansion_after": expansion,
                        "total_after": production + locked + expansion,
                    }
                )

        total_equity = production + locked + expansion
        risk_scale = production_before_transfer / source_official_equity
        scaled_margin = float(row["broker10_total_margin_exact"]) * risk_scale
        records.append(
            {
                "date": date,
                "arm": policy.name,
                "policy": "monthly_profit_tranche",
                "daily_return_source": daily_return,
                "source_official_equity": float(row["account_equity"]),
                "production_before_transfer": production_before_transfer,
                "production_equity": production,
                "locked_equity": locked,
                "expansion_equity": expansion,
                "total_equity": total_equity,
                "sweep_amount": sweep,
                "refill_amount": refill,
                "event": event,
                "risk_scale_to_official": risk_scale,
                "broker10_margin_scaled": scaled_margin,
                "broker10_margin_to_production_pct": (
                    scaled_margin / production_before_transfer * 100.0 if production_before_transfer > 0 else np.nan
                ),
                "broker10_margin_to_total_wealth_pct": scaled_margin / total_equity * 100.0 if total_equity > 0 else np.nan,
                "official_broker10_margin_to_equity_pct": float(row["broker10_margin_to_equity_pct"]),
                "slippage_scaled": float(row["slippage"]) * risk_scale,
                "trade_count_reference": float(row["trade_count"]),
                "threshold_gap_to_next_sweep": max(policy.sweep_start - production, 0.0),
            }
        )

    ledger = pd.DataFrame(records)
    ledger["total_drawdown_pct"] = _drawdown_pct(ledger["total_equity"]).to_numpy()
    ledger["production_drawdown_pct"] = _drawdown_pct(ledger["production_equity"]).to_numpy()
    transfer_frame = pd.DataFrame(transfers)
    return ledger, transfer_frame


def _simulate_all(official: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    official_ledger, official_transfers = _simulate_official(official)
    tranche_ledger, tranche_transfers = _simulate_balanced_tranche(official, BALANCED_TRANCHE_V1)
    ledgers = pd.concat([official_ledger, tranche_ledger], ignore_index=True, sort=False)
    transfers = pd.concat([official_transfers, tranche_transfers], ignore_index=True, sort=False)
    return ledgers, transfers


def _build_metrics(ledger: pd.DataFrame, transfers: pd.DataFrame) -> pd.DataFrame:
    official_group = ledger[ledger["arm"].eq("A_official_full_reinvest")].sort_values("date")
    official_return = (float(official_group["total_equity"].iloc[-1]) / CAPITAL - 1.0) * 100.0
    official_max_dd = float(official_group["total_drawdown_pct"].min())
    official_broker_prod = float(official_group["broker10_margin_to_production_pct"].max())
    official_broker_total = float(official_group["broker10_margin_to_total_wealth_pct"].max())

    rows: list[dict[str, Any]] = []
    for arm, group in ledger.groupby("arm", sort=False):
        group = group.sort_values("date")
        total_equity = pd.to_numeric(group["total_equity"], errors="coerce")
        production_equity = pd.to_numeric(group["production_equity"], errors="coerce")
        total_return = (float(total_equity.iloc[-1]) / CAPITAL - 1.0) * 100.0
        arm_transfers = transfers[transfers["arm"].eq(arm)].copy() if not transfers.empty else pd.DataFrame()
        sweep_transfers = arm_transfers[arm_transfers["event_type"].eq("sweep")].copy() if not arm_transfers.empty else pd.DataFrame()
        first_sweep_date = ""
        if not sweep_transfers.empty:
            first_sweep_date = pd.to_datetime(sweep_transfers["date"].iloc[0]).strftime("%Y-%m-%d")

        max_dd = float(pd.to_numeric(group["total_drawdown_pct"], errors="coerce").min())
        row = {
            "arm": arm,
            "policy": str(group["policy"].iloc[0]),
            "end_total_equity": float(total_equity.iloc[-1]),
            "end_production_equity": float(production_equity.iloc[-1]),
            "end_locked_equity": float(pd.to_numeric(group["locked_equity"], errors="coerce").iloc[-1]),
            "end_expansion_equity": float(pd.to_numeric(group["expansion_equity"], errors="coerce").iloc[-1]),
            "total_return_pct": total_return,
            "return_retention_pct": total_return / official_return * 100.0 if abs(official_return) > 1e-9 else np.nan,
            "total_wealth_max_dd_pct": max_dd,
            "total_dd_improvement_pp": max_dd - official_max_dd,
            "production_max_dd_pct": float(pd.to_numeric(group["production_drawdown_pct"], errors="coerce").min()),
            "ulcer_pct": _ulcer_pct(pd.to_numeric(group["total_drawdown_pct"], errors="coerce")),
            "sharpe": _sharpe_from_equity(total_equity),
            "max_broker10_to_production_pct": float(
                pd.to_numeric(group["broker10_margin_to_production_pct"], errors="coerce").max()
            ),
            "max_broker10_to_total_wealth_pct": float(
                pd.to_numeric(group["broker10_margin_to_total_wealth_pct"], errors="coerce").max()
            ),
            "days_broker10_production_over_100pct": int(
                (pd.to_numeric(group["broker10_margin_to_production_pct"], errors="coerce") > 100).sum()
            ),
            "days_broker10_total_over_100pct": int(
                (pd.to_numeric(group["broker10_margin_to_total_wealth_pct"], errors="coerce") > 100).sum()
            ),
            "avg_risk_scale_to_official": float(pd.to_numeric(group["risk_scale_to_official"], errors="coerce").mean()),
            "min_risk_scale_to_official": float(pd.to_numeric(group["risk_scale_to_official"], errors="coerce").min()),
            "max_risk_scale_to_official": float(pd.to_numeric(group["risk_scale_to_official"], errors="coerce").max()),
            "total_scaled_slippage_proxy": float(pd.to_numeric(group["slippage_scaled"], errors="coerce").sum()),
            "official_trade_count_reference": float(pd.to_numeric(group["trade_count_reference"], errors="coerce").sum()),
            "total_swept": float(pd.to_numeric(group["sweep_amount"], errors="coerce").sum()),
            "total_refilled": float(pd.to_numeric(group["refill_amount"], errors="coerce").sum()),
            "sweep_event_count": int((pd.to_numeric(group["sweep_amount"], errors="coerce") > 0).sum()),
            "refill_event_count": int((pd.to_numeric(group["refill_amount"], errors="coerce") > 0).sum()),
            "first_sweep_date": first_sweep_date,
            "return_80_pass": int(total_return / official_return >= 0.80) if abs(official_return) > 1e-9 else 0,
            "dd_better_than_official": int(max_dd > official_max_dd),
            "meaningful_dd5_pass": int(max_dd - official_max_dd >= 5.0),
            "broker10_total_not_worse_pass": int(
                float(pd.to_numeric(group["broker10_margin_to_total_wealth_pct"], errors="coerce").max())
                <= official_broker_total + 1e-9
            ),
            "broker10_production_not_worse_pass": int(
                float(pd.to_numeric(group["broker10_margin_to_production_pct"], errors="coerce").max())
                <= official_broker_prod + 1e-9
            ),
            "candidate_ready": 0,
        }
        if row["policy"] == "official_full_reinvest":
            row["decision_note"] = "official baseline"
        elif row["return_80_pass"] == 0:
            row["decision_note"] = "fails return retention; no promotion"
        elif row["dd_better_than_official"] == 0:
            row["decision_note"] = "does not reduce total-wealth drawdown; no promotion"
        elif row["meaningful_dd5_pass"] == 0:
            row["decision_note"] = "proxy improves total-wealth drawdown, but improvement is too small"
        else:
            row["decision_note"] = "proxy promising only; needs multi-start/account-ledger validation before A/B"
        rows.append(row)
    return pd.DataFrame(rows)


def _year_stats(ledger: pd.DataFrame) -> pd.DataFrame:
    data = ledger.copy()
    data["year"] = pd.to_datetime(data["date"]).dt.year
    rows: list[dict[str, Any]] = []
    for (arm, year), group in data.groupby(["arm", "year"], sort=False):
        group = group.sort_values("date")
        first_total = float(group["total_equity"].iloc[0])
        first_return = float(group["daily_return_source"].iloc[0])
        start_total = first_total / (1.0 + first_return) if abs(1.0 + first_return) > 1e-12 else first_total
        end_total = float(group["total_equity"].iloc[-1])
        rows.append(
            {
                "arm": arm,
                "year": int(year),
                "start_total_equity": start_total,
                "end_total_equity": end_total,
                "year_return_pct": (end_total / start_total - 1.0) * 100.0 if start_total > 0 else np.nan,
                "year_total_wealth_max_dd_pct": float(pd.to_numeric(group["total_drawdown_pct"], errors="coerce").min()),
                "year_end_locked_equity": float(pd.to_numeric(group["locked_equity"], errors="coerce").iloc[-1]),
                "year_swept": float(pd.to_numeric(group["sweep_amount"], errors="coerce").sum()),
                "year_refilled": float(pd.to_numeric(group["refill_amount"], errors="coerce").sum()),
                "avg_risk_scale_to_official": float(pd.to_numeric(group["risk_scale_to_official"], errors="coerce").mean()),
            }
        )
    return pd.DataFrame(rows)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "(empty)"
    data = frame.copy()
    if max_rows is not None:
        data = data.head(max_rows).copy()
    for col in data.columns:
        if pd.api.types.is_float_dtype(data[col]):
            data[col] = data[col].map(lambda x: "" if pd.isna(x) else f"{float(x):,.4f}")
    return data.to_markdown(index=False)


def _plot_path_drawdown(ledger: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(18, 11), sharex=True, constrained_layout=True)
    official = ledger[ledger["arm"].eq("A_official_full_reinvest")].sort_values("date")
    tranche = ledger[ledger["arm"].eq(BALANCED_TRANCHE_V1.name)].sort_values("date")
    axes[0].plot(official["date"], official["total_equity"], label="A official full reinvest", color="#2563eb", linewidth=1.3)
    axes[0].plot(tranche["date"], tranche["total_equity"], label="C total wealth", color="#16a34a", linewidth=1.3)
    axes[0].plot(
        tranche["date"],
        tranche["production_equity"],
        label="C production account",
        color="#f97316",
        linewidth=1.0,
        alpha=0.85,
    )
    axes[0].set_yscale("log")
    axes[0].set_title("Stage020 C9/15w balanced tranche proxy: total wealth and production account")
    axes[0].grid(True, alpha=0.25)
    axes[0].legend(loc="upper left")

    axes[1].plot(official["date"], official["total_drawdown_pct"], label="A official DD", color="#2563eb", linewidth=1.2)
    axes[1].plot(tranche["date"], tranche["total_drawdown_pct"], label="C total wealth DD", color="#16a34a", linewidth=1.2)
    axes[1].plot(
        tranche["date"],
        tranche["production_drawdown_pct"],
        label="C production account DD",
        color="#f97316",
        linewidth=1.0,
        alpha=0.85,
    )
    axes[1].axhline(-40.0, color="#991b1b", linestyle="--", linewidth=0.9, alpha=0.6)
    axes[1].set_title("Drawdown: total wealth cushion vs production account risk")
    axes[1].grid(True, alpha=0.25)
    axes[1].legend(loc="lower left")
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_accounts(ledger: pd.DataFrame) -> None:
    tranche = ledger[ledger["arm"].eq(BALANCED_TRANCHE_V1.name)].sort_values("date")
    fig, axes = plt.subplots(2, 1, figsize=(18, 11), sharex=True, constrained_layout=True)
    axes[0].stackplot(
        tranche["date"],
        tranche["production_equity"],
        tranche["locked_equity"],
        tranche["expansion_equity"],
        labels=["production", "locked profit", "expansion reserve"],
        colors=["#fb923c", "#22c55e", "#38bdf8"],
        alpha=0.85,
    )
    axes[0].set_yscale("log")
    axes[0].set_title("Stage020 balanced tranche account layers")
    axes[0].grid(True, alpha=0.25)
    axes[0].legend(loc="upper left")

    axes[1].plot(tranche["date"], tranche["risk_scale_to_official"], color="#7c3aed", linewidth=1.2)
    axes[1].axhline(1.0, color="#334155", linestyle="--", linewidth=0.9)
    axes[1].set_title("Production risk scale relative to full official reinvest path")
    axes[1].grid(True, alpha=0.25)
    fig.savefig(ACCOUNTS_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_transfers(transfers: pd.DataFrame, ledger: pd.DataFrame) -> None:
    tranche = ledger[ledger["arm"].eq(BALANCED_TRANCHE_V1.name)].sort_values("date")
    sweep = transfers[transfers["event_type"].eq("sweep")].copy() if not transfers.empty else pd.DataFrame()
    fig, axes = plt.subplots(2, 1, figsize=(18, 10), sharex=True, constrained_layout=True)
    if not sweep.empty:
        axes[0].bar(pd.to_datetime(sweep["date"]), sweep["sweep_amount"], width=22, color="#0f766e", alpha=0.75)
    axes[0].set_title("Monthly sweep amounts")
    axes[0].grid(True, axis="y", alpha=0.25)
    axes[1].plot(tranche["date"], tranche["locked_equity"], label="locked profit", color="#16a34a", linewidth=1.3)
    axes[1].plot(tranche["date"], tranche["expansion_equity"], label="expansion reserve", color="#0284c7", linewidth=1.1)
    axes[1].set_title("Cumulative locked and reserve accounts")
    axes[1].grid(True, alpha=0.25)
    axes[1].legend(loc="upper left")
    fig.savefig(TRANSFERS_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_scatter(metrics: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(10, 7), constrained_layout=True)
    colors = {"A_official_full_reinvest": "#2563eb", BALANCED_TRANCHE_V1.name: "#16a34a"}
    for _, row in metrics.iterrows():
        ax.scatter(row["total_wealth_max_dd_pct"], row["total_return_pct"], s=120, color=colors.get(row["arm"], "#64748b"))
        ax.annotate(row["arm"], (row["total_wealth_max_dd_pct"], row["total_return_pct"]), xytext=(7, 5), textcoords="offset points")
    ax.axhline(float(metrics[metrics["arm"].eq("A_official_full_reinvest")]["total_return_pct"].iloc[0]) * 0.8, color="#334155", linestyle="--", linewidth=0.9)
    ax.axvline(float(metrics[metrics["arm"].eq("A_official_full_reinvest")]["total_wealth_max_dd_pct"].iloc[0]), color="#991b1b", linestyle="--", linewidth=0.9)
    ax.set_xlabel("Max drawdown pct")
    ax.set_ylabel("Total return pct")
    ax.set_title("Return retention vs total-wealth drawdown")
    ax.grid(True, alpha=0.25)
    fig.savefig(SCATTER_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_year_heatmap(year_stats: pd.DataFrame) -> None:
    pivot = year_stats.pivot(index="arm", columns="year", values="year_return_pct")
    fig, ax = plt.subplots(figsize=(15, 4.5), constrained_layout=True)
    data = pivot.to_numpy(dtype=float)
    max_abs = np.nanmax(np.abs(data)) if np.isfinite(data).any() else 1.0
    im = ax.imshow(data, aspect="auto", cmap="RdYlGn", vmin=-max_abs, vmax=max_abs)
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels([str(c) for c in pivot.columns], rotation=45, ha="right")
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            value = data[i, j]
            if np.isfinite(value):
                ax.text(j, i, f"{value:.0f}%", ha="center", va="center", fontsize=8, color="#0f172a")
    ax.set_title("Calendar-year total wealth returns")
    fig.colorbar(im, ax=ax, shrink=0.8)
    fig.savefig(YEAR_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _build_report(metrics: pd.DataFrame, transfers: pd.DataFrame, year_stats: pd.DataFrame, decision: dict[str, Any]) -> str:
    metric_cols = [
        "arm",
        "end_total_equity",
        "total_return_pct",
        "return_retention_pct",
        "total_wealth_max_dd_pct",
        "total_dd_improvement_pp",
        "production_max_dd_pct",
        "sharpe",
        "end_locked_equity",
        "end_expansion_equity",
        "sweep_event_count",
        "first_sweep_date",
        "max_broker10_to_production_pct",
        "max_broker10_to_total_wealth_pct",
        "days_broker10_total_over_100pct",
        "candidate_ready",
        "decision_note",
    ]
    year_cols = ["arm", "year", "year_return_pct", "year_total_wealth_max_dd_pct", "year_end_locked_equity", "year_swept"]
    sweep_preview = transfers[transfers["event_type"].eq("sweep")].tail(12).copy() if not transfers.empty else pd.DataFrame()
    if not sweep_preview.empty:
        sweep_preview["date"] = pd.to_datetime(sweep_preview["date"]).dt.strftime("%Y-%m-%d")
    lines = [
        "# Stage020 balanced_tranche_v1 C9/15w 出金锁盈代理审计",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：`day`",
        f"- 记录时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- 阶段性质：账户层资金分层/出金锁盈 proxy boundary，不是撮合级真引擎",
        "- 是否重要突破：否，先做 C9/15w 适配边界",
        "- 是否触发A/B：否，本阶段预声明 `candidate_ready=0`，只验证账户层代理是否值得后续多起点账本审计",
        "",
        "## 外部调研与判断",
        "",
        "- 参考资料：",
        "  - AQR《Demystifying Managed Futures》：趋势跟随收益主要由 time-series momentum 暴露解释，真实落地要重视成本、保证金和风控。",
        "  - Rob Carver / pysystemtrade capital correction：复利资本会放大仓位和执行容量问题，账户资本如何随盈亏变化是独立风险问题。",
        "  - CPPI/TIPP 文献与 AXA/CAIA 资料：保护机制本质是把风险资产和低风险资产分层，但会在下跌中去风险、在反转中受损。",
        "  - 本仓库 Stage232/237：`balanced_tranche_v1` 已有固定部署口径，非从 C9/15w 曲线反推。",
        "- 我的判断：",
        "  - Stage019 已反证入场后分钟 no-follow 降仓路线；继续调比例/窗口会过拟合。",
        "  - 出金锁盈不改变 C9 单笔路径，解决的是“高水位后是否把全部利润继续暴露”的账户治理问题。",
        "  - 本阶段只使用既有 `balanced_tranche_v1` 单点规则，不扫 `300万/500万/700万`、`30/50/70%` 或锁盈拆分。",
        "",
        "## 预声明规则",
        "",
        f"- A：当前官方 C9/15w 全复利路径 `{OFFICIAL_LIVE_VERSION}`。",
        "- C：同一日收益序列做账户层代理：生产账户按官方日收益变化；月末若生产账户超过 `5,000,000`，提取超额部分 `50%`；其中 `60%` 进锁盈账户，`40%` 进扩张/补仓储备；若月末生产账户低于初始 `150,000` 且扩张储备有余额，则补回生产账户。",
        "- 口径限制：这是按日收益缩放的账户账本代理，不是整数手重算；broker10 只给生产账户/总财富两个 proxy 口径。",
        "",
        "## 指标结果",
        "",
        _md_table(metrics[metric_cols]),
        "",
        "## 年度视觉辅助表",
        "",
        _md_table(year_stats[year_cols], max_rows=30),
        "",
        "## 最近提款事件",
        "",
        _md_table(
            sweep_preview[
                [
                    "date",
                    "sweep_amount",
                    "locked_add",
                    "expansion_add",
                    "production_after",
                    "locked_after",
                    "expansion_after",
                    "total_after",
                ]
            ]
            if not sweep_preview.empty
            else sweep_preview
        ),
        "",
        "## 视觉结论",
        "",
        f"- path chart：`{PATH_CHART_OUT}`",
        f"- account layers：`{ACCOUNTS_CHART_OUT}`",
        f"- transfer ladder：`{TRANSFERS_CHART_OUT}`",
        f"- return/drawdown scatter：`{SCATTER_CHART_OUT}`",
        f"- yearly heatmap：`{YEAR_HEATMAP_OUT}`",
        "- 观察：总财富曲线要和生产账户分开看。锁盈账户可以降低“总财富回撤”，但生产账户本身仍承担 C9 路径风险；如果生产账户回撤很深，只说明账户治理改善心理/资金保全，不等于策略本体降回撤。",
        "",
        "## 结论",
        "",
        f"- 本阶段结论：`{decision['decision']}`。",
        f"- 是否进入下一步：`{decision['next_step']}`",
        "- 不接正式版、不修改当前 official live config、不连接 CTP、不调用订单 API。",
        "",
        "## 过拟合反思",
        "",
        f"- 运行前判断：{decision['overfit_reflection_before']}",
        f"- 运行后判断：{decision['overfit_reflection_after']}",
        "",
        "## 继续价值反思",
        "",
        f"- 运行前判断：{decision['continue_value_before']}",
        f"- 运行后判断：{decision['continue_value_after']}",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    official = _prepare_official_curve()
    ledger, transfers = _simulate_all(official)
    metrics = _build_metrics(ledger, transfers)
    year_stats = _year_stats(ledger)

    _plot_path_drawdown(ledger)
    _plot_accounts(ledger)
    _plot_transfers(transfers, ledger)
    _plot_scatter(metrics)
    _plot_year_heatmap(year_stats)

    c_row = metrics[metrics["arm"].eq(BALANCED_TRANCHE_V1.name)].iloc[0].to_dict()
    if int(c_row["return_80_pass"]) == 0:
        decision_label = "stage020_balanced_tranche_proxy_failed_return_retention"
        next_step = "否，不能作为 C9/15w 低回撤候选；只保留为账户层边界证据"
    elif int(c_row["dd_better_than_official"]) == 0:
        decision_label = "stage020_balanced_tranche_proxy_no_drawdown_reduction"
        next_step = "否，未达降低回撤目标"
    elif int(c_row["meaningful_dd5_pass"]) == 0:
        decision_label = "stage020_balanced_tranche_proxy_small_total_wealth_dd_gain_no_candidate"
        next_step = "有限，只有做多起点账本/真实提款演练才有意义"
    else:
        decision_label = "stage020_balanced_tranche_proxy_promising_but_no_candidate"
        next_step = "是，但下一步必须做多起点账户账本和生产账户风险审计，不能直接接正式版"

    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "baseline_arm": "A_official_full_reinvest",
        "candidate_arm": BALANCED_TRANCHE_V1.name,
        "candidate_hypothesis": (
            "Reuse the pre-existing balanced_tranche_v1 account governance rule on the official C9/15w "
            "daily return path: keep the single-trade path unchanged, but move part of high-water profits "
            "out of the production account at month end."
        ),
        "predeclared_metrics": [
            "total wealth end equity, return, max drawdown, Sharpe",
            "return retention >= 80% versus official full reinvest",
            "total wealth drawdown improves versus official",
            "production account drawdown is shown separately and cannot be hidden",
            "broker10 proxy is reported versus production account and total wealth",
            "visual path chart, account-layer chart, transfer ladder, scatter and year heatmap",
        ],
        "policy": {
            "name": BALANCED_TRANCHE_V1.name,
            "production_floor": BALANCED_TRANCHE_V1.production_floor,
            "sweep_start": BALANCED_TRANCHE_V1.sweep_start,
            "sweep_ratio": BALANCED_TRANCHE_V1.sweep_ratio,
            "lock_ratio": BALANCED_TRANCHE_V1.lock_ratio,
            "expansion_ratio": BALANCED_TRANCHE_V1.expansion_ratio,
        },
        "classification": "proxy_boundary_not_ab_candidate",
        "decision": decision_label,
        "next_step": next_step,
        "comparison": metrics.to_dict(orient="records"),
        "transfer_summary": {
            "transfer_count": int(len(transfers)),
            "sweep_count": int((transfers["event_type"].eq("sweep")).sum()) if not transfers.empty else 0,
            "refill_count": int((transfers["event_type"].eq("refill")).sum()) if not transfers.empty else 0,
        },
        "order_api_called": False,
        "ctp_connected": False,
        "external_research_judgment": (
            "Trend-following and pysystemtrade references support treating capital scaling and profit lock as an "
            "account-level question; CPPI/TIPP literature warns that protection mechanisms can trade off return. "
            "Stage020 therefore tests a single pre-existing tranche rule, not a tuned risk overlay."
        ),
        "overfit_reflection_before": "否。规则来自既有 Stage232/237 的账户治理口径，不按 C9/15w 的坏窗口、品种、方向、月份或指标曲线反推。",
        "continue_value_before": "是。Stage019 后继续分钟内降仓会变成参数救援；不改变单笔路径的资金分层是更低自由度方向。",
        "overfit_reflection_after": "",
        "continue_value_after": "",
        "outputs": {
            "ledger": str(LEDGER_OUT.resolve()),
            "transfers": str(TRANSFERS_OUT.resolve()),
            "metrics": str(METRICS_OUT.resolve()),
            "year_stats": str(YEAR_STATS_OUT.resolve()),
            "summary": str(SUMMARY_OUT.resolve()),
            "decision": str(DECISION_OUT.resolve()),
            "report": str(REPORT_OUT.resolve()),
            "path_chart": str(PATH_CHART_OUT.resolve()),
            "account_layers_chart": str(ACCOUNTS_CHART_OUT.resolve()),
            "transfer_ladder_chart": str(TRANSFERS_CHART_OUT.resolve()),
            "scatter_chart": str(SCATTER_CHART_OUT.resolve()),
            "year_heatmap": str(YEAR_HEATMAP_OUT.resolve()),
        },
    }

    if "failed" in decision_label:
        decision["overfit_reflection_after"] = "否，本次没有调参；失败后若继续改提款阈值、比例、锁盈拆分或只看某个起点，就是过拟合。"
        decision["continue_value_after"] = "该固定账户层形状对 C9/15w 没有候选价值；整条目标仍有价值，但下一步要换真正外生风险源或多起点账户审计。"
    elif "small_total_wealth_dd_gain" in decision_label:
        decision["overfit_reflection_after"] = "否，本次只测一个继承规则；但用结果反推更低提款阈值或更高锁盈比例会过拟合。"
        decision["continue_value_after"] = "有限。只有在多起点账本也证明总财富回撤改善且生产账户风险可接受时，才值得继续。"
    else:
        decision["overfit_reflection_after"] = "否，本次只测固定继承规则；不得在当前结果上微调提款制度。"
        decision["continue_value_after"] = "有，但只能进入多起点账户账本验证和真实提款流程审计，不能直接 promotion。"

    ledger.to_csv(LEDGER_OUT, index=False, encoding="utf-8-sig")
    transfers.to_csv(TRANSFERS_OUT, index=False, encoding="utf-8-sig")
    metrics.to_csv(METRICS_OUT, index=False, encoding="utf-8-sig")
    year_stats.to_csv(YEAR_STATS_OUT, index=False, encoding="utf-8-sig")
    metrics.assign(stage=STAGE, model_tag=MODEL_TAG, line_id=LINE_ID).to_csv(SUMMARY_OUT, index=False, encoding="utf-8-sig")
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_OUT.write_text(_build_report(metrics, transfers, year_stats, decision), encoding="utf-8")

    print(json.dumps(_json_safe({"decision": decision_label, "metrics": metrics.to_dict(orient="records"), "outputs": decision["outputs"]}), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
