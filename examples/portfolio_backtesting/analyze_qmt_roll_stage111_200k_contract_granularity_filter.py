from __future__ import annotations

import json
import math
import re
import sys
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.database import get_database

from analyze_qmt_roll_stage105_margin_constraint_surface import (
    MARGIN_EXTREME_BALANCE_PCT,
    MARGIN_REJECT_BALANCE_PCT,
    _calculate_daily_risk,
    _calculate_margin_path,
    _safe_float,
    _to_markdown_table,
)
from main_contract_mapping import build_contract_metadata, load_product_universe_symbols
from qmt_roll_stage111_400k_margin_safe_config import STAGE111_MARGIN_PROFILE, build_stage111_manifest, build_stage111_overrides
from qmt_universe import END_DT, START_DT
from run_qmt_alignment_backtest import build_positions_df
from run_qmt_roll_backtest import run_backtest
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage113_stage111_200k_contract_granularity_filter_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage111_200k_contract_granularity_filter"
CAPITAL: float = 200_000.0
THRESHOLD_PCTS: tuple[float, ...] = (20.0, 15.0)
SINGLE_CONTRACT_REJECT_PCT: float = 25.0
WORST_5D_REJECT_PCT: float = -50.0
WORST_20D_REJECT_PCT: float = -70.0

CONTRACT_MARGIN_AUDIT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_contract_margin_audit_{MODEL_TAG}.csv"
SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _parse_vt_symbol(vt_symbol: str) -> tuple[str, Exchange] | None:
    if "." not in vt_symbol:
        return None
    symbol, exchange = vt_symbol.split(".", 1)
    try:
        return symbol, Exchange(exchange)
    except ValueError:
        return None


def _product_from_contract(vt_symbol: object) -> str:
    raw = str(vt_symbol)
    if "." not in raw:
        return raw
    symbol, exchange = raw.split(".", 1)
    match = re.match(r"^([A-Za-z]+)", symbol)
    product = match.group(1) if match else symbol
    return f"{product}.{exchange}"


def _load_contract_margin_audit() -> pd.DataFrame:
    manifest = build_stage111_manifest()
    base_universe_path = Path(str(manifest["product_universe_csv_path"]))
    supported_symbols = load_product_universe_symbols(base_universe_path)
    metadata = build_contract_metadata(supported_symbols=supported_symbols)
    database = get_database()
    rows: list[dict[str, Any]] = []
    start_dt = START_DT
    end_dt = END_DT

    for vt_symbol in sorted(metadata["vt_symbols"]):
        parsed = _parse_vt_symbol(vt_symbol)
        if parsed is None:
            continue
        symbol, exchange = parsed
        size = float(metadata["sizes"].get(vt_symbol, 1) or 1)
        margin_ratio = float(metadata["margin_ratios"].get(vt_symbol, 0.15) or 0.15)
        bars = database.load_bar_data(symbol, exchange, Interval.DAILY, start_dt, end_dt)
        values: list[float] = []
        for bar in bars:
            close = float(getattr(bar, "close_price", 0.0) or 0.0)
            if close > 0:
                values.append(close * size * margin_ratio)
        if not values:
            continue
        series = pd.Series(values, dtype=float)
        rows.append(
            {
                "product_vt_symbol": _product_from_contract(vt_symbol),
                "vt_symbol": vt_symbol,
                "bar_count": int(len(values)),
                "max_single_contract_margin": float(series.max()),
                "p95_single_contract_margin": float(series.quantile(0.95)),
                "median_single_contract_margin": float(series.median()),
                "max_single_contract_margin_pct_capital": float(series.max() / CAPITAL * 100.0),
                "p95_single_contract_margin_pct_capital": float(series.quantile(0.95) / CAPITAL * 100.0),
                "median_single_contract_margin_pct_capital": float(series.median() / CAPITAL * 100.0),
            }
        )

    contract_df = pd.DataFrame(rows)
    if contract_df.empty:
        return pd.DataFrame()
    product_df = (
        contract_df.groupby("product_vt_symbol", as_index=False)
        .agg(
            contract_count=("vt_symbol", "nunique"),
            total_bar_count=("bar_count", "sum"),
            max_single_contract_margin=("max_single_contract_margin", "max"),
            p95_single_contract_margin=("p95_single_contract_margin", "max"),
            median_single_contract_margin=("median_single_contract_margin", "median"),
            max_single_contract_margin_pct_capital=("max_single_contract_margin_pct_capital", "max"),
            p95_single_contract_margin_pct_capital=("p95_single_contract_margin_pct_capital", "max"),
            median_single_contract_margin_pct_capital=("median_single_contract_margin_pct_capital", "median"),
        )
        .sort_values("max_single_contract_margin_pct_capital", ascending=False)
        .reset_index(drop=True)
    )
    return product_df


def _build_filtered_universe(
    contract_margin_audit: pd.DataFrame,
    threshold_pct: float,
) -> tuple[Path, pd.DataFrame]:
    manifest = build_stage111_manifest()
    base_universe_path = Path(str(manifest["product_universe_csv_path"]))
    universe = pd.read_csv(base_universe_path)
    audit = contract_margin_audit[["product_vt_symbol", "max_single_contract_margin_pct_capital"]].copy()
    filtered = universe.merge(audit, on="product_vt_symbol", how="left")
    filtered["base_eligible"] = pd.to_numeric(filtered.get("eligible", 1), errors="coerce").fillna(1).astype(int)
    filtered["max_single_contract_margin_pct_capital"] = pd.to_numeric(
        filtered["max_single_contract_margin_pct_capital"],
        errors="coerce",
    ).fillna(999.0)
    filtered["contract_granularity_threshold_pct"] = threshold_pct
    filtered["contract_granularity_reject_reason"] = np.where(
        filtered["max_single_contract_margin_pct_capital"] > threshold_pct,
        "single_contract_margin_above_threshold",
        "",
    )
    filtered["eligible"] = (
        (filtered["base_eligible"] == 1)
        & (filtered["max_single_contract_margin_pct_capital"] <= threshold_pct)
    ).astype(int)

    tag = str(threshold_pct).replace(".", "p")
    path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_universe_threshold_{tag}_{MODEL_TAG}.csv"
    filtered.to_csv(path, index=False, encoding="utf-8-sig")
    return path, filtered


def _run_filtered_backtest(universe_path: Path, threshold_pct: float) -> tuple[pd.DataFrame, dict[str, Any], pd.DataFrame]:
    overrides = build_stage111_overrides()
    overrides["product_universe_csv_path"] = str(universe_path)
    profile_name = f"single_margin_le_{threshold_pct:g}pct"
    print(f"[stage111-200k-granularity] run {profile_name}")
    log_buffer = StringIO()
    try:
        with redirect_stdout(log_buffer), redirect_stderr(log_buffer):
            engine, analysis_df, statistics = run_backtest(
                risk_ratio=BASE_RISK_RATIO,
                strategy_overrides=overrides,
                analysis_start=START_DT,
                analysis_end=END_DT,
                capital=CAPITAL,
                save_artifacts=False,
                include_start_year_sweep=False,
                file_prefix=f"{OUTPUT_PREFIX}_{profile_name}",
                chart_title=f"QMT Roll Stage111 200k Granularity {profile_name}",
            )
    except Exception:
        sys.stderr.write(log_buffer.getvalue())
        raise

    daily = analysis_df.copy() if analysis_df is not None else pd.DataFrame()
    if not daily.empty:
        daily.sort_index(inplace=True)
    positions = build_positions_df(engine)
    return daily, statistics, positions


def _product_exposure(product_daily: pd.DataFrame, daily_margin: pd.DataFrame) -> pd.DataFrame:
    if product_daily.empty:
        return pd.DataFrame()
    balance = daily_margin[["date", "balance"]].copy() if not daily_margin.empty else pd.DataFrame()
    frame = product_daily.merge(balance, on="date", how="left")
    frame["balance"] = pd.to_numeric(frame["balance"], errors="coerce").ffill().fillna(CAPITAL)
    frame["product_margin_to_balance_pct"] = (
        frame["product_margin"] / frame["balance"].replace(0.0, pd.NA) * 100.0
    ).fillna(0.0)
    return (
        frame.groupby("product_vt_symbol", as_index=False)
        .agg(
            total_net_pnl=("product_net_pnl", "sum"),
            total_trade_count=("product_trade_count", "sum"),
            active_days=("active_product", "sum"),
            max_margin_to_balance_pct=("product_margin_to_balance_pct", "max"),
            max_single_contract_margin=("max_single_contract_margin", "max"),
        )
        .sort_values(["max_margin_to_balance_pct", "total_net_pnl"], ascending=[False, False])
        .reset_index(drop=True)
    )


def _summarize(
    *,
    threshold_pct: float,
    universe: pd.DataFrame,
    statistics: dict[str, Any],
    daily_risk: pd.DataFrame,
    daily_margin: pd.DataFrame,
    product_exposure: pd.DataFrame,
) -> dict[str, Any]:
    worst_daily = daily_risk.loc[daily_risk["net_pnl"].idxmin()].to_dict() if not daily_risk.empty else {}
    worst_5d = daily_risk.loc[daily_risk["rolling_5d_net_pnl"].idxmin()].to_dict() if not daily_risk.empty else {}
    worst_20d = daily_risk.loc[daily_risk["rolling_20d_net_pnl"].idxmin()].to_dict() if not daily_risk.empty else {}
    max_margin = (
        daily_margin.loc[daily_margin["total_margin_to_balance_pct"].idxmax()].to_dict()
        if not daily_margin.empty
        else {}
    )
    max_single_contract = (
        daily_margin.loc[daily_margin["max_single_contract_margin_pct_capital"].idxmax()].to_dict()
        if not daily_margin.empty
        else {}
    )

    max_margin_to_balance = _safe_float(max_margin.get("total_margin_to_balance_pct"))
    max_single_contract_pct = _safe_float(max_single_contract.get("max_single_contract_margin_pct_capital"))
    worst_5d_pct = _safe_float(worst_5d.get("rolling_5d_pct_capital"))
    worst_20d_pct = _safe_float(worst_20d.get("rolling_20d_pct_capital"))
    extreme_days = int((daily_margin["total_margin_to_balance_pct"] > MARGIN_EXTREME_BALANCE_PCT).sum()) if not daily_margin.empty else 0
    reject_days = int((daily_margin["total_margin_to_balance_pct"] > MARGIN_REJECT_BALANCE_PCT).sum()) if not daily_margin.empty else 0

    hard_reasons: list[str] = []
    if reject_days > 0 or max_margin_to_balance > MARGIN_REJECT_BALANCE_PCT:
        hard_reasons.append("margin_to_balance_gt_100pct")
    elif extreme_days > 0 or max_margin_to_balance > MARGIN_EXTREME_BALANCE_PCT:
        hard_reasons.append("margin_to_balance_gt_80pct")
    if max_single_contract_pct > SINGLE_CONTRACT_REJECT_PCT:
        hard_reasons.append("single_contract_margin_too_coarse")
    if worst_5d_pct < WORST_5D_REJECT_PCT:
        hard_reasons.append("worst_5d_loss_too_large")
    if worst_20d_pct < WORST_20D_REJECT_PCT:
        hard_reasons.append("worst_20d_loss_too_large")

    label = "PASS_FULL_WINDOW_NEEDS_QUARTERLY" if not hard_reasons else "REJECT_FULL_WINDOW"
    return {
        "model_tag": MODEL_TAG,
        "capital": CAPITAL,
        "threshold_pct": threshold_pct,
        "base_margin_profile": STAGE111_MARGIN_PROFILE,
        "eligible_product_count": int(pd.to_numeric(universe["eligible"], errors="coerce").fillna(0).sum()),
        "rejected_product_count": int((pd.to_numeric(universe["eligible"], errors="coerce").fillna(0) == 0).sum()),
        "rejected_products": sorted(
            universe.loc[pd.to_numeric(universe["eligible"], errors="coerce").fillna(0) == 0, "product_vt_symbol"]
            .dropna()
            .astype(str)
            .tolist()
        ),
        "end_balance": _safe_float(statistics.get("end_balance")),
        "total_return_pct": _safe_float(statistics.get("total_return")),
        "annual_return_pct": _safe_float(statistics.get("annual_return")),
        "max_dd_percent": _safe_float(statistics.get("max_ddpercent")),
        "sharpe_ratio": _safe_float(statistics.get("sharpe_ratio")),
        "total_slippage": _safe_float(statistics.get("total_slippage")),
        "total_trade_count": _safe_float(statistics.get("total_trade_count")),
        "win_ratio_pct": _safe_float(statistics.get("win_ratio")),
        "worst_daily_pct_prev_balance": _safe_float(worst_daily.get("daily_net_pnl_pct_prev_balance")),
        "worst_daily_date": str(worst_daily.get("date", ""))[:10],
        "worst_5d_pct_capital": worst_5d_pct,
        "worst_5d_end_date": str(worst_5d.get("date", ""))[:10],
        "worst_20d_pct_capital": worst_20d_pct,
        "worst_20d_end_date": str(worst_20d.get("date", ""))[:10],
        "max_margin_to_balance_pct": max_margin_to_balance,
        "max_margin_to_initial_capital_pct": _safe_float(max_margin.get("total_margin_to_initial_capital_pct")),
        "margin_days_gt_80pct": extreme_days,
        "margin_days_gt_100pct": reject_days,
        "max_single_contract_margin_pct_capital": max_single_contract_pct,
        "decision_label": label,
        "hard_reasons": hard_reasons,
        "top_product_exposure": product_exposure.head(10).to_dict(orient="records"),
    }


def _build_report(summary_df: pd.DataFrame, contract_margin_audit: pd.DataFrame) -> str:
    columns = [
        "threshold_pct",
        "eligible_product_count",
        "rejected_product_count",
        "end_balance",
        "total_return_pct",
        "max_dd_percent",
        "sharpe_ratio",
        "total_trade_count",
        "win_ratio_pct",
        "worst_5d_pct_capital",
        "worst_20d_pct_capital",
        "max_margin_to_balance_pct",
        "max_single_contract_margin_pct_capital",
        "decision_label",
        "hard_reasons",
    ]
    audit_columns = [
        "product_vt_symbol",
        "max_single_contract_margin",
        "max_single_contract_margin_pct_capital",
        "p95_single_contract_margin_pct_capital",
        "contract_count",
    ]
    return "\n".join(
        [
            "# Stage111 200k Contract Granularity Filter",
            "",
            "## Boundary",
            "",
            "- This is a structural small-capital feasibility filter, not an alpha optimization.",
            "- Products are removed only by historical max single-contract margin / 200k capital.",
            "- Stage111 trading rules and capital ratios are otherwise unchanged.",
            "",
            "## Summary",
            "",
            _to_markdown_table(summary_df, columns, max_rows=20),
            "",
            "## Coarsest Products",
            "",
            _to_markdown_table(contract_margin_audit, audit_columns, max_rows=12),
            "",
            "## Judgement",
            "",
            "- If a threshold still fails on worst 5d loss, the next step is not more threshold fitting; it needs dynamic risk or product-level path-risk filtering.",
            "- A full-window pass is not promotion; it must still pass quarterly cold-start validation.",
        ]
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    contract_margin_audit = _load_contract_margin_audit()
    contract_margin_audit.to_csv(CONTRACT_MARGIN_AUDIT_PATH, index=False, encoding="utf-8-sig")

    summaries: list[dict[str, Any]] = []
    output_files: dict[str, Any] = {
        "contract_margin_audit": str(CONTRACT_MARGIN_AUDIT_PATH),
        "summary_csv": str(SUMMARY_CSV_PATH),
        "summary_json": str(SUMMARY_JSON_PATH),
        "report": str(REPORT_PATH),
        "universes": {},
    }

    for threshold_pct in THRESHOLD_PCTS:
        universe_path, universe = _build_filtered_universe(contract_margin_audit, threshold_pct)
        daily, statistics, positions = _run_filtered_backtest(universe_path, threshold_pct)
        daily_risk = _calculate_daily_risk(daily, CAPITAL)
        daily_margin, product_daily = _calculate_margin_path(positions, daily_risk, capital=CAPITAL)
        product_exposure = _product_exposure(product_daily, daily_margin)
        summary = _summarize(
            threshold_pct=threshold_pct,
            universe=universe,
            statistics=statistics,
            daily_risk=daily_risk,
            daily_margin=daily_margin,
            product_exposure=product_exposure,
        )
        summaries.append(summary)

        tag = str(threshold_pct).replace(".", "p")
        daily_margin_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_margin_threshold_{tag}_{MODEL_TAG}.csv"
        product_daily_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_daily_threshold_{tag}_{MODEL_TAG}.csv"
        positions_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_threshold_{tag}_{MODEL_TAG}.csv"
        daily_margin.to_csv(daily_margin_path, index=False, encoding="utf-8-sig")
        product_daily.to_csv(product_daily_path, index=False, encoding="utf-8-sig")
        positions.to_csv(positions_path, index=False, encoding="utf-8-sig")
        output_files["universes"][f"threshold_{tag}"] = {
            "universe": str(universe_path),
            "daily_margin": str(daily_margin_path),
            "product_daily": str(product_daily_path),
            "positions": str(positions_path),
        }
        print(
            f"[stage111-200k-granularity] threshold={threshold_pct:g}% "
            f"return={summary['total_return_pct']:.4f}% "
            f"dd={summary['max_dd_percent']:.4f}% "
            f"worst5d={summary['worst_5d_pct_capital']:.4f}% "
            f"decision={summary['decision_label']}"
        )

    summary_df = pd.DataFrame(summaries).sort_values("threshold_pct", ascending=False).reset_index(drop=True)
    summary_df.to_csv(SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_JSON_PATH.write_text(
        json.dumps(
            {
                "model_tag": MODEL_TAG,
                "capital": CAPITAL,
                "thresholds": THRESHOLD_PCTS,
                "summaries": summaries,
                "outputs": output_files,
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    REPORT_PATH.write_text(_build_report(summary_df, contract_margin_audit), encoding="utf-8")
    print(json.dumps(summaries, ensure_ascii=False, indent=2, default=str))
    print(f"[stage111-200k-granularity] report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
