from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from analyze_qmt_roll_ai_product_suitability_walkforward import (
    PRODUCT_DAILY_OUTPUT_PATH,
    PROBABILITY_COLUMN,
    SIMPLE_SCORE_COLUMN,
    SOURCE_PREFIX,
    product_from_contract,
)
from analyze_qmt_roll_ai_product_suitability_market_walkforward import PREDICTIONS_OUTPUT_PATH as MARKET_PREDICTIONS_PATH


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "ai_product_pool_shadow_v1"
OUTPUT_PREFIX: str = "qmt_roll_ai_product_pool_shadow_portfolio"

POSITION_CHANGES_PATH: Path = OUTPUT_DIR / f"{SOURCE_PREFIX}_position_changes_2020_2026_04.csv"
OFFICIAL_DAILY_PATH: Path = OUTPUT_DIR / f"{SOURCE_PREFIX}_daily.csv"

DAILY_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
SUMMARY_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
YEARLY_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_yearly_{MODEL_TAG}.csv"
PRODUCT_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_attribution_{MODEL_TAG}.csv"
PRODUCT_YEAR_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_year_attribution_{MODEL_TAG}.csv"
ELIGIBILITY_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_eligibility_{MODEL_TAG}.csv"
SUMMARY_JSON_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

INITIAL_CAPITAL: float = 200_000.0
TRADING_DAYS_PER_YEAR: int = 240


@dataclass(frozen=True)
class PoolSpec:
    strategy: str
    score_type: str
    score_column: str
    top_n: int | None
    description: str


POOL_SPECS: tuple[PoolSpec, ...] = (
    PoolSpec(
        strategy="baseline_all_products",
        score_type="baseline",
        score_column="",
        top_n=None,
        description="No product-pool filter, same frozen formal position path over the AI evaluation period.",
    ),
    PoolSpec(
        strategy="ai_top5_entry_filter",
        score_type="ai_probability",
        score_column=PROBABILITY_COLUMN,
        top_n=5,
        description="Use V2 AI probabilities, allow only top 5 products for new entries.",
    ),
    PoolSpec(
        strategy="ai_top8_entry_filter",
        score_type="ai_probability",
        score_column=PROBABILITY_COLUMN,
        top_n=8,
        description="Use V2 AI probabilities, allow only top 8 products for new entries.",
    ),
    PoolSpec(
        strategy="simple_top5_entry_filter",
        score_type="simple_score",
        score_column=SIMPLE_SCORE_COLUMN,
        top_n=5,
        description="Use transparent simple suitability score, allow only top 5 products for new entries.",
    ),
)


NUMERIC_COLUMNS: tuple[str, ...] = (
    "start_pos",
    "end_pos",
    "pos_change",
    "trade_count",
    "turnover",
    "commission",
    "slippage",
    "holding_pnl",
    "trading_pnl",
    "total_pnl",
    "net_pnl",
)


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or math.isinf(result):
        return default
    return result


def load_position_changes() -> pd.DataFrame:
    if not POSITION_CHANGES_PATH.exists():
        raise FileNotFoundError(f"missing position changes: {POSITION_CHANGES_PATH}")

    columns = ["date", "vt_symbol", *NUMERIC_COLUMNS]
    df = pd.read_csv(POSITION_CHANGES_PATH, usecols=lambda column: column in columns)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df["product_vt_symbol"] = df["vt_symbol"].map(product_from_contract)
    for column in NUMERIC_COLUMNS:
        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0.0)
    df.sort_values(["vt_symbol", "date"], inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def load_official_daily() -> pd.DataFrame:
    if not OFFICIAL_DAILY_PATH.exists():
        raise FileNotFoundError(f"missing official daily: {OFFICIAL_DAILY_PATH}")
    df = pd.read_csv(OFFICIAL_DAILY_PATH)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    for column in ["net_pnl", "balance", "trade_count", "slippage"]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0.0)
    df.sort_values("date", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def load_predictions() -> pd.DataFrame:
    if not MARKET_PREDICTIONS_PATH.exists():
        raise FileNotFoundError(f"missing market predictions: {MARKET_PREDICTIONS_PATH}")
    df = pd.read_csv(MARKET_PREDICTIONS_PATH)
    df["eval_date"] = pd.to_datetime(df["eval_date"]).dt.normalize()
    for column in [PROBABILITY_COLUMN, SIMPLE_SCORE_COLUMN]:
        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0.0)
    return df


def build_eligibility(predictions: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for spec in POOL_SPECS:
        if spec.top_n is None:
            continue
        ranked = predictions.sort_values(["eval_date", spec.score_column], ascending=[True, False]).copy()
        ranked["score_rank"] = ranked.groupby("eval_date")[spec.score_column].rank(method="first", ascending=False)
        selected = ranked[ranked["score_rank"] <= spec.top_n].copy()
        for _, row in selected.iterrows():
            rows.append(
                {
                    "strategy": spec.strategy,
                    "score_type": spec.score_type,
                    "eval_date": row["eval_date"],
                    "product_vt_symbol": row["product_vt_symbol"],
                    "score": _safe_float(row[spec.score_column]),
                    "score_rank": int(row["score_rank"]),
                    "top_n": int(spec.top_n),
                }
            )
    return pd.DataFrame(rows).sort_values(["strategy", "eval_date", "score_rank"]).reset_index(drop=True)


def build_signal_lookup(eligibility: pd.DataFrame) -> dict[str, dict[pd.Timestamp, set[str]]]:
    lookup: dict[str, dict[pd.Timestamp, set[str]]] = {}
    for strategy, strategy_df in eligibility.groupby("strategy"):
        lookup[strategy] = {
            pd.Timestamp(eval_date): set(group["product_vt_symbol"].astype(str))
            for eval_date, group in strategy_df.groupby("eval_date")
        }
    return lookup


def latest_signal_dates(dates: pd.Series, eval_dates: list[pd.Timestamp]) -> pd.Series:
    eval_index = pd.DatetimeIndex(sorted(eval_dates))
    indices = eval_index.searchsorted(pd.DatetimeIndex(dates), side="left") - 1
    result = pd.Series(pd.NaT, index=dates.index, dtype="datetime64[ns]")
    mask = indices >= 0
    if mask.any():
        result.loc[mask] = eval_index[indices[mask]]
    return result


def product_is_eligible(
    *,
    strategy: str,
    date: pd.Timestamp,
    product: str,
    signal_date_by_date: dict[pd.Timestamp, pd.Timestamp],
    signal_lookup: dict[str, dict[pd.Timestamp, set[str]]],
) -> bool:
    if strategy == "baseline_all_products":
        return True
    signal_date = signal_date_by_date.get(date)
    if pd.isna(signal_date):
        return False
    return product in signal_lookup.get(strategy, {}).get(pd.Timestamp(signal_date), set())


def build_shadow_rows(
    position_changes: pd.DataFrame,
    strategy: str,
    evaluation_start: pd.Timestamp,
    signal_date_by_date: dict[pd.Timestamp, pd.Timestamp],
    signal_lookup: dict[str, dict[pd.Timestamp, set[str]]],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for _, contract_df in position_changes.groupby("vt_symbol", sort=False):
        active = False
        contract_df = contract_df[contract_df["date"] >= evaluation_start].sort_values("date")
        if contract_df.empty:
            continue

        for record in contract_df.itertuples(index=False):
            date = pd.Timestamp(record.date)
            start_pos = _safe_float(record.start_pos)
            end_pos = _safe_float(record.end_pos)
            product = str(record.product_vt_symbol)
            legacy_position = date == evaluation_start and abs(start_pos) > 0
            new_entry = abs(start_pos) == 0 and abs(end_pos) > 0

            if strategy == "baseline_all_products":
                keep = True
            elif active:
                keep = True
            elif legacy_position:
                # Keep inherited positions until their original exits; this is an entry filter, not a forced liquidation.
                active = True
                keep = True
            elif new_entry and product_is_eligible(
                strategy=strategy,
                date=date,
                product=product,
                signal_date_by_date=signal_date_by_date,
                signal_lookup=signal_lookup,
            ):
                active = True
                keep = True
            else:
                keep = False

            payload: dict[str, Any] = {
                "strategy": strategy,
                "date": date,
                "vt_symbol": record.vt_symbol,
                "product_vt_symbol": product,
                "kept": bool(keep),
                "new_entry": bool(new_entry),
                "legacy_position": bool(legacy_position),
            }
            for column in NUMERIC_COLUMNS:
                payload[column] = _safe_float(getattr(record, column)) if keep else 0.0
                payload[f"original_{column}"] = _safe_float(getattr(record, column))
            rows.append(payload)

            if active and abs(end_pos) == 0:
                active = False

    return pd.DataFrame(rows)


def calculate_daily(strategy_rows: pd.DataFrame, initial_balance: float) -> pd.DataFrame:
    aggregated = (
        strategy_rows.groupby(["strategy", "date"], as_index=False)
        .agg(
            net_pnl=("net_pnl", "sum"),
            total_pnl=("total_pnl", "sum"),
            holding_pnl=("holding_pnl", "sum"),
            trading_pnl=("trading_pnl", "sum"),
            turnover=("turnover", "sum"),
            commission=("commission", "sum"),
            slippage=("slippage", "sum"),
            trade_count=("trade_count", "sum"),
            original_net_pnl=("original_net_pnl", "sum"),
            original_trade_count=("original_trade_count", "sum"),
            original_slippage=("original_slippage", "sum"),
        )
        .sort_values(["strategy", "date"])
    )

    frames: list[pd.DataFrame] = []
    for _, group in aggregated.groupby("strategy", sort=False):
        group = group.copy()
        group["balance"] = initial_balance + group["net_pnl"].cumsum()
        previous_balance = group["balance"].shift(1).fillna(initial_balance)
        group["return"] = np.where(previous_balance != 0.0, group["net_pnl"] / previous_balance, 0.0)
        group["highlevel"] = group["balance"].cummax()
        group["drawdown"] = group["balance"] - group["highlevel"]
        group["ddpercent"] = np.where(group["highlevel"] != 0.0, group["drawdown"] / group["highlevel"] * 100.0, 0.0)
        frames.append(group)
    return pd.concat(frames, ignore_index=True)


def calculate_summary(daily: pd.DataFrame, initial_balance: float, spec_by_strategy: dict[str, PoolSpec]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    baseline = daily[daily["strategy"] == "baseline_all_products"].copy()
    baseline_end = float(baseline["balance"].iloc[-1]) if not baseline.empty else 0.0
    baseline_sharpe = _summary_sharpe(baseline)
    baseline_max_dd = float(baseline["ddpercent"].min()) if not baseline.empty else 0.0

    for strategy, group in daily.groupby("strategy", sort=False):
        spec = spec_by_strategy[strategy]
        end_balance = float(group["balance"].iloc[-1])
        returns = group["return"].to_numpy(dtype=float)
        return_std = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.0
        sharpe = float(np.mean(returns) / return_std * math.sqrt(TRADING_DAYS_PER_YEAR)) if return_std > 0 else 0.0
        total_net_pnl = float(group["net_pnl"].sum())
        original_net_pnl = float(group["original_net_pnl"].sum())
        total_trade_count = float(group["trade_count"].sum())
        original_trade_count = float(group["original_trade_count"].sum())
        total_slippage = float(group["slippage"].sum())
        original_slippage = float(group["original_slippage"].sum())
        rows.append(
            {
                "strategy": strategy,
                "score_type": spec.score_type,
                "top_n": spec.top_n if spec.top_n is not None else 0,
                "description": spec.description,
                "start_date": group["date"].min().date().isoformat(),
                "end_date": group["date"].max().date().isoformat(),
                "trading_days": int(group["date"].nunique()),
                "initial_balance": initial_balance,
                "end_balance": end_balance,
                "end_balance_diff_vs_baseline": end_balance - baseline_end,
                "total_return_pct": (end_balance / initial_balance - 1.0) * 100.0 if initial_balance else 0.0,
                "max_drawdown": float(group["drawdown"].min()),
                "max_dd_percent": float(group["ddpercent"].min()),
                "max_dd_percent_diff_vs_baseline": float(group["ddpercent"].min()) - baseline_max_dd,
                "sharpe_ratio": sharpe,
                "sharpe_ratio_diff_vs_baseline": sharpe - baseline_sharpe,
                "total_net_pnl": total_net_pnl,
                "blocked_net_pnl": original_net_pnl - total_net_pnl,
                "kept_net_pnl_ratio": total_net_pnl / original_net_pnl if original_net_pnl else 0.0,
                "total_trade_count": int(round(total_trade_count)),
                "blocked_trade_count": int(round(original_trade_count - total_trade_count)),
                "kept_trade_count_ratio": total_trade_count / original_trade_count if original_trade_count else 0.0,
                "total_slippage": total_slippage,
                "blocked_slippage": original_slippage - total_slippage,
                "kept_slippage_ratio": total_slippage / original_slippage if original_slippage else 0.0,
            }
        )
    return pd.DataFrame(rows).sort_values(["end_balance", "sharpe_ratio"], ascending=False).reset_index(drop=True)


def _summary_sharpe(daily: pd.DataFrame) -> float:
    returns = daily["return"].to_numpy(dtype=float)
    return_std = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.0
    return float(np.mean(returns) / return_std * math.sqrt(TRADING_DAYS_PER_YEAR)) if return_std > 0 else 0.0


def calculate_yearly(daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (strategy, year), group in daily.assign(year=daily["date"].dt.year).groupby(["strategy", "year"]):
        rows.append(
            {
                "strategy": strategy,
                "year": int(year),
                "days": int(group["date"].nunique()),
                "net_pnl": float(group["net_pnl"].sum()),
                "trade_count": int(round(float(group["trade_count"].sum()))),
                "slippage": float(group["slippage"].sum()),
                "max_dd_percent": float(group["ddpercent"].min()),
                "end_balance": float(group["balance"].iloc[-1]),
            }
        )
    return pd.DataFrame(rows).sort_values(["strategy", "year"]).reset_index(drop=True)


def calculate_product_attribution(strategy_rows: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        strategy_rows.groupby(["strategy", "product_vt_symbol"], as_index=False)
        .agg(
            net_pnl=("net_pnl", "sum"),
            original_net_pnl=("original_net_pnl", "sum"),
            trade_count=("trade_count", "sum"),
            original_trade_count=("original_trade_count", "sum"),
            slippage=("slippage", "sum"),
            original_slippage=("original_slippage", "sum"),
            kept_rows=("kept", "sum"),
            rows=("kept", "size"),
            new_entry_rows=("new_entry", "sum"),
        )
    )
    grouped["blocked_net_pnl"] = grouped["original_net_pnl"] - grouped["net_pnl"]
    grouped["kept_trade_count_ratio"] = np.where(
        grouped["original_trade_count"] != 0.0,
        grouped["trade_count"] / grouped["original_trade_count"],
        0.0,
    )
    return grouped.sort_values(["strategy", "net_pnl"], ascending=[True, False]).reset_index(drop=True)


def calculate_product_year_attribution(strategy_rows: pd.DataFrame) -> pd.DataFrame:
    source = strategy_rows.copy()
    source["year"] = source["date"].dt.year
    grouped = (
        source.groupby(["strategy", "year", "product_vt_symbol"], as_index=False)
        .agg(
            net_pnl=("net_pnl", "sum"),
            original_net_pnl=("original_net_pnl", "sum"),
            trade_count=("trade_count", "sum"),
            original_trade_count=("original_trade_count", "sum"),
            slippage=("slippage", "sum"),
            original_slippage=("original_slippage", "sum"),
            kept_rows=("kept", "sum"),
            rows=("kept", "size"),
            new_entry_rows=("new_entry", "sum"),
        )
    )
    grouped["blocked_net_pnl"] = grouped["original_net_pnl"] - grouped["net_pnl"]
    grouped["kept_trade_count_ratio"] = np.where(
        grouped["original_trade_count"] != 0.0,
        grouped["trade_count"] / grouped["original_trade_count"],
        0.0,
    )
    return grouped.sort_values(["strategy", "year", "blocked_net_pnl"], ascending=[True, True, False]).reset_index(drop=True)


def to_markdown_table(df: pd.DataFrame, columns: list[str]) -> str:
    if df.empty:
        return "_empty_"
    view = df[columns].copy()
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda value: f"{value:.4f}")
    header = "| " + " | ".join(view.columns) + " |"
    separator = "| " + " | ".join(["---"] * len(view.columns)) + " |"
    rows = ["| " + " | ".join(map(str, row)) + " |" for row in view.to_numpy()]
    return "\n".join([header, separator, *rows])


def build_report(summary: pd.DataFrame, yearly: pd.DataFrame) -> str:
    summary_columns = [
        "strategy",
        "end_balance",
        "end_balance_diff_vs_baseline",
        "total_return_pct",
        "max_dd_percent",
        "sharpe_ratio",
        "total_trade_count",
        "total_slippage",
    ]
    yearly_columns = ["strategy", "year", "net_pnl", "trade_count", "slippage", "max_dd_percent", "end_balance"]
    lines = [
        "# AI Product Pool Shadow Portfolio",
        "",
        "## Design Boundary",
        "",
        "- This is an entry-filter shadow portfolio built from frozen position-change PnL attribution.",
        "- Monthly AI signals are only effective after the signal date, so same-day lookahead is avoided.",
        "- It is not an executable vn.py backtest because position sizing is not recomputed after filtered trades.",
        "",
        "## Summary",
        "",
        to_markdown_table(summary, summary_columns),
        "",
        "## Yearly",
        "",
        to_markdown_table(yearly, yearly_columns),
    ]
    return "\n".join(lines)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    position_changes = load_position_changes()
    official_daily = load_official_daily()
    predictions = load_predictions()
    eligibility = build_eligibility(predictions)
    signal_lookup = build_signal_lookup(eligibility)

    eval_dates = sorted(pd.Timestamp(date) for date in predictions["eval_date"].unique())
    if not eval_dates:
        raise RuntimeError("no prediction eval dates")
    first_eval_date = min(eval_dates)
    all_dates = pd.Series(sorted(position_changes["date"].unique()))
    valid_dates = all_dates[all_dates > first_eval_date]
    if valid_dates.empty:
        raise RuntimeError("no dates after first prediction eval date")
    evaluation_start = pd.Timestamp(valid_dates.iloc[0])

    date_signal = pd.DataFrame({"date": valid_dates})
    date_signal["signal_date"] = latest_signal_dates(date_signal["date"], eval_dates)
    signal_date_by_date = {
        pd.Timestamp(row.date): pd.Timestamp(row.signal_date)
        for row in date_signal.itertuples(index=False)
        if not pd.isna(row.signal_date)
    }

    official_eval = official_daily[official_daily["date"] >= evaluation_start].copy()
    if official_eval.empty:
        raise RuntimeError("official daily has no evaluation rows")
    initial_balance = float(official_eval.iloc[0]["balance"] - official_eval.iloc[0]["net_pnl"])

    spec_by_strategy = {spec.strategy: spec for spec in POOL_SPECS}
    strategy_frames: list[pd.DataFrame] = []
    for spec in POOL_SPECS:
        strategy_frames.append(
            build_shadow_rows(
                position_changes=position_changes,
                strategy=spec.strategy,
                evaluation_start=evaluation_start,
                signal_date_by_date=signal_date_by_date,
                signal_lookup=signal_lookup,
            )
        )
    strategy_rows = pd.concat(strategy_frames, ignore_index=True)
    daily = calculate_daily(strategy_rows, initial_balance)
    summary = calculate_summary(daily, initial_balance, spec_by_strategy)
    yearly = calculate_yearly(daily)
    product = calculate_product_attribution(strategy_rows)
    product_year = calculate_product_year_attribution(strategy_rows)

    daily.to_csv(DAILY_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    yearly.to_csv(YEARLY_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    product.to_csv(PRODUCT_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    product_year.to_csv(PRODUCT_YEAR_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    eligibility.to_csv(ELIGIBILITY_OUTPUT_PATH, index=False, encoding="utf-8-sig")

    payload: dict[str, Any] = {
        "model_tag": MODEL_TAG,
        "source_prefix": SOURCE_PREFIX,
        "design_boundary": (
            "Entry-filter shadow portfolio from frozen position-change attribution; not an executable "
            "vn.py backtest because sizing and replacement trades are not recomputed."
        ),
        "source_paths": {
            "position_changes": str(POSITION_CHANGES_PATH),
            "official_daily": str(OFFICIAL_DAILY_PATH),
            "market_predictions": str(MARKET_PREDICTIONS_PATH),
            "product_daily": str(PRODUCT_DAILY_OUTPUT_PATH),
        },
        "parameters": {
            "first_prediction_eval_date": first_eval_date.date().isoformat(),
            "evaluation_start": evaluation_start.date().isoformat(),
            "signal_effective_rule": "latest eval_date strictly earlier than trade date",
            "legacy_position_rule": "positions already open at evaluation_start are kept until original exit",
            "trading_days_per_year": TRADING_DAYS_PER_YEAR,
            "initial_balance": initial_balance,
            "pool_specs": [spec.__dict__ for spec in POOL_SPECS],
        },
        "summary": summary.to_dict(orient="records"),
        "artifacts": {
            "daily_csv": str(DAILY_OUTPUT_PATH),
            "summary_csv": str(SUMMARY_OUTPUT_PATH),
            "yearly_csv": str(YEARLY_OUTPUT_PATH),
            "product_attribution_csv": str(PRODUCT_OUTPUT_PATH),
            "product_year_attribution_csv": str(PRODUCT_YEAR_OUTPUT_PATH),
            "eligibility_csv": str(ELIGIBILITY_OUTPUT_PATH),
            "summary_json": str(SUMMARY_JSON_OUTPUT_PATH),
            "report_md": str(REPORT_OUTPUT_PATH),
        },
        "judgement": (
            "If AI entry filters fail to improve the frozen attribution portfolio robustly, the model should stay "
            "shadow-only and not be connected to formal strategy logic."
        ),
    }
    SUMMARY_JSON_OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_OUTPUT_PATH.write_text(build_report(summary, yearly), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
