from __future__ import annotations

from datetime import datetime, timedelta
import json
import math
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from vnpy.trader.constant import Interval


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
sys.path.insert(0, str(PROJECT_DIR.resolve()))

import analyze_qmt_roll_stage402_stage079_xsmom_volmanaged_true_integer as s402  # noqa: E402
import analyze_qmt_roll_stage403_stage079_xsmom_execution_margin_audit as s403  # noqa: E402
import analyze_qmt_roll_stage506_next_real_forward_risk_signal_frontier as s506  # noqa: E402
from analyze_qmt_roll_stage324_true_combo_capital_margin import _c3_overrides  # noqa: E402
from main_contract_mapping import build_contract_metadata, load_product_universe_symbols  # noqa: E402
from qmt_backtest_runtime_guard import assert_stage196_database_sentinels  # noqa: E402
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy  # noqa: E402
from qmt_universe import END_DT, PRELOAD_START_DT, START_DT  # noqa: E402
from run_qmt_alignment_backtest import build_positions_df  # noqa: E402
from run_qmt_roll_backtest import build_roll_setting  # noqa: E402
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import (  # noqa: E402
    BASE_RISK_RATIO,
)


MODEL_TAG = "stage513_stage208_exact_position_margin_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage513_stage208_exact_position_margin_audit"
LINE_ID = "futures_trend_drawdown30_preserve_return"

ACCOUNT_CAPITAL = 615_000.0
C3_CAPITAL = 500_000.0
STAGE208_TAG = "stage508_xsmom_true_carry_replay_v1"
STAGE208_PREFIX = "qmt_roll_stage508_xsmom_true_carry_replay"
STAGE213_TAG = "stage512_stage208_deployment_constraint_audit_v1"
STAGE213_PREFIX = "qmt_roll_stage512_stage208_deployment_constraint_audit"

DAILY_IN = OUTPUT_DIR / f"{STAGE208_PREFIX}_daily_{STAGE208_TAG}.csv"
XSMOM_DAILY_IN = OUTPUT_DIR / f"{STAGE208_PREFIX}_xsmom_daily_{STAGE208_TAG}.csv"
PROXY_DETAIL_IN = OUTPUT_DIR / f"{STAGE213_PREFIX}_daily_detail_{STAGE213_TAG}.csv"

POSITIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_c3_positions_{MODEL_TAG}.csv"
MARGIN_DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_margin_daily_{MODEL_TAG}.csv"
MATRIX_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_deployment_matrix_{MODEL_TAG}.csv"
EVENT_DAYS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_days_{MODEL_TAG}.csv"
PRODUCT_DAYS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_top_margin_product_days_{MODEL_TAG}.csv"
VALIDATION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_validation_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

RISK060_CLEAN = "stage079_next_real_risk060_clean"
RISK070_CLEAN = "stage079_next_real_risk070_clean"
RISK060_COMBO = "stage079_next_real_risk060_clean_plus_stage103_xsmom_true"
RISK070_COMBO = "stage079_next_real_risk070_clean_plus_stage103_xsmom_true"
VARIANT_SPECS = {
    RISK060_CLEAN: {
        "combo_variant": RISK060_COMBO,
        "label": "risk060 clean C3",
        "risk_multiplier": 0.60,
    },
    RISK070_CLEAN: {
        "combo_variant": RISK070_COMBO,
        "label": "risk070 clean C3",
        "risk_multiplier": 0.70,
    },
}
COMBO_TO_CLEAN = {item["combo_variant"]: key for key, item in VARIANT_SPECS.items()}
COST_MULTIPLIERS = [1.0, 2.0, 3.0]
MARGIN_CAPS = [100.0, 95.0, 90.0]
DD_LIMIT_PCT = -40.0


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "无数据。"
    view = frame.copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda item: f"{item:.4f}" if pd.notna(item) else "")
    return view.to_markdown(index=False)


def _product_from_contract(vt_symbol: object) -> str:
    raw = str(vt_symbol)
    if "." not in raw:
        return raw
    symbol, exchange = raw.split(".", 1)
    letters = "".join(ch for ch in symbol if ch.isalpha())
    return f"{letters or symbol}.{exchange}"


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    values = equity.astype(float)
    return (values / values.cummax() - 1.0) * 100.0


def _max_drawdown_pct(equity: pd.Series) -> float:
    return float(_drawdown_pct(equity).min())


def _ulcer_pct(equity: pd.Series) -> float:
    dd = _drawdown_pct(equity)
    return float(np.sqrt(np.mean(np.square(np.minimum(dd.to_numpy(dtype=float), 0.0)))))


def _longest_underwater_days(equity: pd.Series) -> int:
    dd = _drawdown_pct(equity)
    longest = 0
    current = 0
    for value in dd.to_numpy(dtype=float):
        if value < -1e-12:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return int(longest)


def _load_stage208_daily() -> pd.DataFrame:
    frame = pd.read_csv(DAILY_IN, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    for column in ["account_equity", "slippage", "trade_count", "net_pnl"]:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    keep = [RISK060_COMBO, RISK070_COMBO]
    return frame[frame["variant"].isin(keep)].dropna(subset=["date"]).sort_values(["variant", "date"]).copy()


def _load_xsmom_daily() -> pd.DataFrame:
    frame = pd.read_csv(XSMOM_DAILY_IN, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    for column in ["xsmom_true_margin", "xsmom_true_daily_pnl", "xsmom_true_held_contract_count"]:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    return frame.dropna(subset=["date"]).sort_values("date").copy()


def _metadata() -> dict[str, Any]:
    overrides = _c3_overrides(START_DT)
    supported_symbols = load_product_universe_symbols(str(overrides.get("product_universe_csv_path", "") or ""))
    return build_contract_metadata(supported_symbols=supported_symbols)


def _run_c3_positions(clean_variant: str, metadata: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    spec = VARIANT_SPECS[clean_variant]
    assert_stage196_database_sentinels()
    s506._patch_stage506_raw_roots()
    overrides = _c3_overrides(START_DT)
    preload_start = max(PRELOAD_START_DT, START_DT - timedelta(days=365))
    _, open_map = s506.s501._seed_proxy_maps()
    engine = s506.s502.ConfirmedDailyNextRealOpenEngine(open_map)
    engine.output = lambda msg: None
    engine.set_parameters(
        vt_symbols=metadata["vt_symbols"],
        interval=Interval.DAILY,
        start=preload_start,
        end=END_DT,
        rates=metadata["rates"],
        slippages=metadata["slippages"],
        sizes=metadata["sizes"],
        priceticks=metadata["priceticks"],
        capital=C3_CAPITAL,
    )
    setting = build_roll_setting(
        metadata["margin_ratios"],
        risk_ratio=BASE_RISK_RATIO * float(spec["risk_multiplier"]),
        strategy_overrides=overrides,
    )
    setting["capital_base"] = C3_CAPITAL
    engine.add_strategy(QmtRollPortfolioStrategy, setting)
    engine.load_data()
    engine.run_backtesting()
    daily_df = engine.calculate_result()
    if daily_df is None or daily_df.empty:
        raise RuntimeError(f"empty daily result: {clean_variant}")
    daily = daily_df.copy()
    daily = daily.loc[(daily.index >= START_DT.date()) & (daily.index <= END_DT.date())].reset_index()
    daily.rename(columns={"index": "date"}, inplace=True)
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
    for column in ["net_pnl", "trade_count", "slippage", "commission", "turnover"]:
        daily[column] = pd.to_numeric(daily.get(column, 0.0), errors="coerce").fillna(0.0)
    daily["account_equity"] = ACCOUNT_CAPITAL + daily["net_pnl"].cumsum()
    daily["variant"] = clean_variant
    daily["combo_variant"] = spec["combo_variant"]
    positions = build_positions_df(engine)
    if positions.empty:
        raise RuntimeError(f"empty positions: {clean_variant}")
    positions["variant"] = clean_variant
    positions["combo_variant"] = spec["combo_variant"]
    positions["risk_multiplier"] = float(spec["risk_multiplier"])
    return daily, positions


def _position_margin(positions: pd.DataFrame, metadata: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    frame = positions.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    for column in ["end_pos", "close_price", "pre_close", "holding_pnl", "trading_pnl", "net_pnl"]:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    frame["size"] = frame["vt_symbol"].map(metadata["sizes"]).fillna(1.0).astype(float)
    frame["margin_ratio"] = frame["vt_symbol"].map(metadata["margin_ratios"]).fillna(0.15).astype(float)
    frame["product_vt_symbol"] = frame["vt_symbol"].map(_product_from_contract)
    frame["abs_end_pos"] = frame["end_pos"].abs()
    frame["c3_margin_exact"] = frame["abs_end_pos"] * frame["close_price"].clip(lower=0.0) * frame["size"] * frame["margin_ratio"]
    frame["active_contract"] = (frame["abs_end_pos"] > 0).astype(int)
    product = (
        frame.groupby(["variant", "combo_variant", "date", "product_vt_symbol"], as_index=False)
        .agg(
            c3_margin_exact=("c3_margin_exact", "sum"),
            active_contracts=("active_contract", "sum"),
            holding_pnl=("holding_pnl", "sum"),
            trading_pnl=("trading_pnl", "sum"),
            net_pnl=("net_pnl", "sum"),
        )
        .sort_values(["variant", "date", "c3_margin_exact"], ascending=[True, True, False])
    )
    product["active_product"] = (product["c3_margin_exact"] > 0.0).astype(int)
    daily = (
        product.groupby(["variant", "combo_variant", "date"], as_index=False)
        .agg(
            c3_margin_exact=("c3_margin_exact", "sum"),
            c3_active_contracts=("active_contracts", "sum"),
            c3_active_products=("active_product", "sum"),
        )
        .sort_values(["variant", "date"])
    )
    return daily, product


def _proxy_margin_reference() -> pd.DataFrame:
    if not PROXY_DETAIL_IN.exists():
        return pd.DataFrame()
    frame = pd.read_csv(PROXY_DETAIL_IN, encoding="utf-8-sig")
    frame = frame[frame["cost_multiplier"].eq(1.0)].copy()
    return frame[["variant", "max_broker10_margin_to_equity_pct", "days_over_100pct", "days_over_90pct"]].rename(
        columns={
            "variant": "combo_variant",
            "max_broker10_margin_to_equity_pct": "stage213_proxy_max_broker10_margin_pct",
            "days_over_100pct": "stage213_proxy_days_over_100pct",
            "days_over_90pct": "stage213_proxy_days_over_90pct",
        }
    )


def _combine_margin(
    stage208_daily: pd.DataFrame,
    c3_margin_daily: pd.DataFrame,
    xsmom_daily: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    x = xsmom_daily[["date", "xsmom_true_margin", "xsmom_true_held_contract_count"]].copy()
    for combo_variant, frame in stage208_daily.groupby("variant"):
        clean_variant = COMBO_TO_CLEAN[combo_variant]
        merged = frame.merge(
            c3_margin_daily[c3_margin_daily["variant"].eq(clean_variant)][
                ["date", "c3_margin_exact", "c3_active_contracts", "c3_active_products"]
            ],
            on="date",
            how="left",
        ).merge(x, on="date", how="left")
        merged["clean_variant"] = clean_variant
        merged["xsmom_true_margin"] = pd.to_numeric(merged.get("xsmom_true_margin", 0.0), errors="coerce").fillna(0.0)
        merged["c3_margin_exact"] = pd.to_numeric(merged.get("c3_margin_exact", 0.0), errors="coerce").fillna(0.0)
        merged["total_margin_exact"] = merged["c3_margin_exact"] + merged["xsmom_true_margin"]
        merged["broker10_total_margin_exact"] = merged["total_margin_exact"] * float(s403.BROKER10_MULTIPLIER)
        merged["broker10_margin_to_equity_pct"] = (
            merged["broker10_total_margin_exact"] / merged["account_equity"].replace(0.0, np.nan) * 100.0
        ).fillna(0.0)
        rows.append(merged)
    return pd.concat(rows, ignore_index=True)


def _stressed_equity(frame: pd.DataFrame, cost_multiplier: float, extra_cash: float = 0.0) -> pd.Series:
    ordered = frame.sort_values("date").copy()
    additional_slippage = ordered["slippage"].astype(float).cumsum() * max(cost_multiplier - 1.0, 0.0)
    values = ordered["account_equity"].astype(float).to_numpy() - additional_slippage.to_numpy() + float(extra_cash)
    return pd.Series(values, index=pd.to_datetime(ordered["date"]))


def _needed_cash_for_dd(equity: pd.Series, dd_limit_pct: float) -> float:
    if _max_drawdown_pct(equity) >= dd_limit_pct:
        return 0.0
    low = 0.0
    high = max(float(equity.max() - equity.min()), ACCOUNT_CAPITAL)
    while _max_drawdown_pct(equity + high) < dd_limit_pct:
        high *= 2.0
        if high > 100_000_000.0:
            break
    for _ in range(80):
        mid = (low + high) / 2.0
        if _max_drawdown_pct(equity + mid) >= dd_limit_pct:
            high = mid
        else:
            low = mid
    return float(high)


def _needed_cash_for_margin(equity: pd.Series, broker_margin: pd.Series, cap_pct: float) -> float:
    aligned = broker_margin.reindex(equity.index).ffill().fillna(0.0).astype(float)
    cap_fraction = float(cap_pct) / 100.0
    required = aligned / cap_fraction - equity.astype(float)
    return float(max(0.0, required.max()))


def _metrics(
    combo_variant: str,
    cost_multiplier: float,
    margin_cap_pct: float,
    equity_no_cash: pd.Series,
    broker_margin: pd.Series,
    extra_cash: float,
) -> dict[str, Any]:
    equity = equity_no_cash + float(extra_cash)
    margin_ratio = broker_margin.reindex(equity.index).ffill().fillna(0.0).astype(float) / equity.astype(float) * 100.0
    profit = float(equity_no_cash.iloc[-1] - ACCOUNT_CAPITAL)
    deployed = ACCOUNT_CAPITAL + float(extra_cash)
    return {
        "combo_variant": combo_variant,
        "clean_variant": COMBO_TO_CLEAN[combo_variant],
        "cost_multiplier": cost_multiplier,
        "margin_cap_pct": margin_cap_pct,
        "extra_cash": float(extra_cash),
        "deployed_capital": deployed,
        "end_equity": float(equity.iloc[-1]),
        "profit": profit,
        "pnl_on_base_capital_pct": profit / ACCOUNT_CAPITAL * 100.0,
        "return_on_deployed_capital_pct": profit / deployed * 100.0,
        "max_dd_pct": _max_drawdown_pct(equity),
        "ulcer_pct": _ulcer_pct(equity),
        "longest_underwater_days": _longest_underwater_days(equity),
        "max_broker10_margin_to_equity_pct": float(margin_ratio.max()),
        "p95_broker10_margin_to_equity_pct": float(margin_ratio.quantile(0.95)),
        "days_over_100pct": int((margin_ratio > 100.0 + 1e-9).sum()),
        "days_over_95pct": int((margin_ratio > 95.0 + 1e-9).sum()),
        "days_over_90pct": int((margin_ratio > 90.0 + 1e-9).sum()),
        "days_over_cap": int((margin_ratio > float(margin_cap_pct) + 1e-9).sum()),
        "dd40_pass": int(_max_drawdown_pct(equity) >= DD_LIMIT_PCT),
        "margin_cap_pass": int((margin_ratio <= float(margin_cap_pct) + 1e-9).all()),
    }


def _deployment_matrix(margin_daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    baseline_return = 4947.260162601626
    for combo_variant, frame in margin_daily.groupby("variant"):
        frame = frame.sort_values("date")
        broker_margin = pd.Series(frame["broker10_total_margin_exact"].to_numpy(dtype=float), index=pd.to_datetime(frame["date"]))
        for cost_multiplier in COST_MULTIPLIERS:
            equity_no_cash = _stressed_equity(frame, cost_multiplier)
            dd_cash = _needed_cash_for_dd(equity_no_cash, DD_LIMIT_PCT)
            no_cash = _metrics(combo_variant, cost_multiplier, 100.0, equity_no_cash, broker_margin, 0.0)
            no_cash["scenario"] = "no_extra_cash"
            no_cash["cash_needed_for_dd40"] = dd_cash
            no_cash["cash_needed_for_margin_cap"] = 0.0
            no_cash["cash_binding_reason"] = "none"
            no_cash["return_retention_vs_stage079_base_pct"] = no_cash["pnl_on_base_capital_pct"] / baseline_return * 100.0
            no_cash["return_retention_vs_stage079_deployed_pct"] = no_cash["return_on_deployed_capital_pct"] / baseline_return * 100.0
            no_cash["deploy_pass"] = int(no_cash["dd40_pass"] == 1 and no_cash["days_over_100pct"] == 0)
            rows.append(no_cash)
            for cap in MARGIN_CAPS:
                margin_cash = _needed_cash_for_margin(equity_no_cash, broker_margin, cap)
                extra_cash = max(dd_cash, margin_cash)
                row = _metrics(combo_variant, cost_multiplier, cap, equity_no_cash, broker_margin, extra_cash)
                row["scenario"] = f"dd40_and_exact_broker10_cap_{int(cap)}"
                row["cash_needed_for_dd40"] = dd_cash
                row["cash_needed_for_margin_cap"] = margin_cash
                row["cash_binding_reason"] = "dd40" if dd_cash > margin_cash + 1e-6 else "margin" if margin_cash > dd_cash + 1e-6 else "tie_or_zero"
                row["return_retention_vs_stage079_base_pct"] = row["pnl_on_base_capital_pct"] / baseline_return * 100.0
                row["return_retention_vs_stage079_deployed_pct"] = row["return_on_deployed_capital_pct"] / baseline_return * 100.0
                row["deploy_pass"] = int(row["dd40_pass"] == 1 and row["margin_cap_pass"] == 1)
                rows.append(row)
    return pd.DataFrame(rows)


def _event_days(margin_daily: pd.DataFrame, product_margin: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    event_rows: list[dict[str, Any]] = []
    product_rows: list[pd.DataFrame] = []
    for combo_variant, frame in margin_daily.groupby("variant"):
        frame = frame.sort_values("date")
        equity = pd.Series(frame["account_equity"].to_numpy(dtype=float), index=pd.to_datetime(frame["date"]))
        margin = pd.Series(frame["broker10_total_margin_exact"].to_numpy(dtype=float), index=pd.to_datetime(frame["date"]))
        ratio = margin / equity * 100.0
        dd = _drawdown_pct(equity)
        top_margin_dates = list(ratio.sort_values(ascending=False).head(12).index)
        deep_dd_dates = list(dd.sort_values(ascending=True).head(12).index)
        for event_type, dates in [("top_exact_margin_ratio", top_margin_dates), ("deepest_drawdown", deep_dd_dates)]:
            for date in dates:
                row = frame[frame["date"].eq(date)].iloc[0]
                event_rows.append(
                    {
                        "combo_variant": combo_variant,
                        "clean_variant": COMBO_TO_CLEAN[combo_variant],
                        "event_type": event_type,
                        "date": date,
                        "account_equity": float(row["account_equity"]),
                        "c3_margin_exact": float(row["c3_margin_exact"]),
                        "xsmom_true_margin": float(row["xsmom_true_margin"]),
                        "broker10_total_margin_exact": float(row["broker10_total_margin_exact"]),
                        "broker10_margin_to_equity_pct": float(ratio.loc[date]),
                        "drawdown_pct": float(dd.loc[date]),
                    }
                )
                clean = COMBO_TO_CLEAN[combo_variant]
                p = product_margin[
                    product_margin["variant"].eq(clean)
                    & product_margin["date"].eq(pd.Timestamp(date).normalize())
                    & product_margin["c3_margin_exact"].gt(0.0)
                ].copy()
                if not p.empty:
                    p["combo_variant"] = combo_variant
                    p["event_type"] = event_type
                    p["event_date"] = date
                    product_rows.append(p.sort_values("c3_margin_exact", ascending=False).head(8))
    return pd.DataFrame(event_rows), pd.concat(product_rows, ignore_index=True) if product_rows else pd.DataFrame()


def _validation(c3_daily: pd.DataFrame, positions_daily: pd.DataFrame, margin_daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    proxy_ref = _proxy_margin_reference()
    for clean_variant, frame in c3_daily.groupby("variant"):
        combo_variant = str(frame["combo_variant"].iloc[0])
        stage208 = _load_stage208_daily()
        combo = stage208[stage208["variant"].eq(combo_variant)].sort_values("date")
        clean = frame.sort_values("date")
        clean_return = float(clean["account_equity"].iloc[-1] / ACCOUNT_CAPITAL - 1.0) * 100.0
        combo_return = float(combo["account_equity"].iloc[-1] / ACCOUNT_CAPITAL - 1.0) * 100.0
        exact = margin_daily[margin_daily["variant"].eq(combo_variant)].copy()
        row = {
            "clean_variant": clean_variant,
            "combo_variant": combo_variant,
            "rerun_clean_total_return_pct": clean_return,
            "stage208_combo_total_return_pct": combo_return,
            "rerun_clean_max_dd_pct": _max_drawdown_pct(pd.Series(clean["account_equity"].to_numpy(dtype=float), index=pd.to_datetime(clean["date"]))),
            "stage208_combo_max_dd_pct": _max_drawdown_pct(pd.Series(combo["account_equity"].to_numpy(dtype=float), index=pd.to_datetime(combo["date"]))),
            "exact_max_broker10_margin_to_equity_pct": float(exact["broker10_margin_to_equity_pct"].max()),
            "exact_days_over_100pct": int((exact["broker10_margin_to_equity_pct"] > 100.0).sum()),
            "exact_days_over_90pct": int((exact["broker10_margin_to_equity_pct"] > 90.0).sum()),
            "exact_max_c3_margin": float(exact["c3_margin_exact"].max()),
            "exact_max_xsmom_margin": float(exact["xsmom_true_margin"].max()),
        }
        if not proxy_ref.empty:
            p = proxy_ref[proxy_ref["combo_variant"].eq(combo_variant)]
            if not p.empty:
                row.update(p.iloc[0].to_dict())
                row["exact_minus_proxy_max_margin_pct"] = (
                    row["exact_max_broker10_margin_to_equity_pct"]
                    - row["stage213_proxy_max_broker10_margin_pct"]
                )
                row["exact_minus_proxy_days_over_100pct"] = (
                    row["exact_days_over_100pct"] - row["stage213_proxy_days_over_100pct"]
                )
        rows.append(row)
    return pd.DataFrame(rows)


def _decision(matrix: pd.DataFrame, validation: pd.DataFrame) -> dict[str, Any]:
    r060 = matrix[
        matrix["combo_variant"].eq(RISK060_COMBO)
        & matrix["cost_multiplier"].eq(1.0)
        & matrix["scenario"].eq("no_extra_cash")
    ].iloc[0]
    r060_2x = matrix[
        matrix["combo_variant"].eq(RISK060_COMBO)
        & matrix["cost_multiplier"].eq(2.0)
        & matrix["scenario"].eq("no_extra_cash")
    ].iloc[0]
    r060_90 = matrix[
        matrix["combo_variant"].eq(RISK060_COMBO)
        & matrix["cost_multiplier"].eq(1.0)
        & matrix["margin_cap_pct"].eq(90.0)
        & matrix["scenario"].str.contains("cap_90")
    ].iloc[0]
    r070 = matrix[
        matrix["combo_variant"].eq(RISK070_COMBO)
        & matrix["cost_multiplier"].eq(1.0)
        & matrix["scenario"].eq("no_extra_cash")
    ].iloc[0]
    if int(r060["dd40_pass"]) == 1 and int(r060["days_over_100pct"]) == 0 and int(r060_2x["dd40_pass"]) == 1:
        label = "risk060_exact_position_margin_deployment_candidate_needs_broker_rate_table"
    else:
        label = "risk060_exact_position_margin_not_ready"
    return {
        "stage": "Stage214",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": label,
        "risk060_1x_exact_max_dd_pct": _safe_float(r060["max_dd_pct"]),
        "risk060_1x_exact_max_broker10_margin_pct": _safe_float(r060["max_broker10_margin_to_equity_pct"]),
        "risk060_1x_exact_days_over_100pct": int(r060["days_over_100pct"]),
        "risk060_2x_exact_max_dd_pct": _safe_float(r060_2x["max_dd_pct"]),
        "risk060_1x_exact_cap90_extra_cash": _safe_float(r060_90["extra_cash"]),
        "risk060_1x_exact_cap90_deployed_return_pct": _safe_float(r060_90["return_on_deployed_capital_pct"]),
        "risk070_1x_exact_max_dd_pct": _safe_float(r070["max_dd_pct"]),
        "risk070_1x_exact_max_broker10_margin_pct": _safe_float(r070["max_broker10_margin_to_equity_pct"]),
        "risk070_1x_exact_days_over_100pct": int(r070["days_over_100pct"]),
        "validation_rows": validation.to_dict(orient="records"),
        "next_step": (
            "Do not promote risk060 yet. First audit the exact-vs-proxy margin gap, "
            "then either confirm historical broker-rate-table replay or redesign the "
            "capital/margin structure before any deployment-candidate upgrade."
        ),
    }


def _plot(margin_daily: pd.DataFrame, matrix: pd.DataFrame, product_days: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    ax_margin, ax_components, ax_dd, ax_cash = axes.ravel()
    colors = {RISK060_COMBO: "#1b7f5a", RISK070_COMBO: "#b55a2a"}
    labels = {
        RISK060_COMBO: "risk060 + true xsmom",
        RISK070_COMBO: "risk070 + true xsmom",
    }
    for combo_variant, frame in margin_daily.groupby("variant"):
        frame = frame.sort_values("date")
        x = pd.to_datetime(frame["date"])
        ratio = frame["broker10_margin_to_equity_pct"].astype(float)
        ax_margin.plot(x, ratio, label=labels.get(combo_variant, combo_variant), color=colors[combo_variant], linewidth=1.0)
        equity = pd.Series(frame["account_equity"].to_numpy(dtype=float), index=x)
        dd = _drawdown_pct(equity)
        ax_dd.plot(x, dd, label=labels.get(combo_variant, combo_variant), color=colors[combo_variant], linewidth=1.0)
    ax_margin.axhline(100.0, color="#222222", linestyle="--", linewidth=1.0)
    ax_margin.axhline(90.0, color="#777777", linestyle=":", linewidth=0.9)
    ax_margin.set_title("Exact position broker10 margin / equity")
    ax_margin.set_ylabel("Margin / equity %")
    ax_margin.grid(True, alpha=0.22)
    ax_margin.legend(fontsize=8)
    ax_dd.axhline(-40.0, color="#222222", linestyle="--", linewidth=1.0)
    ax_dd.axhline(-30.0, color="#777777", linestyle=":", linewidth=0.9)
    ax_dd.set_title("Drawdown under Stage208 combo equity")
    ax_dd.set_ylabel("Drawdown %")
    ax_dd.grid(True, alpha=0.22)
    focus = margin_daily[margin_daily["variant"].eq(RISK060_COMBO)].sort_values("date")
    x = pd.to_datetime(focus["date"])
    ax_components.stackplot(
        x,
        focus["c3_margin_exact"].astype(float) / 10_000.0,
        focus["xsmom_true_margin"].astype(float) / 10_000.0,
        labels=["C3 exact margin", "xsmom true margin"],
        colors=["#4d9078", "#d8a23a"],
        alpha=0.82,
    )
    ax_components.set_title("risk060 margin components")
    ax_components.set_ylabel("Margin, 10k CNY")
    ax_components.grid(True, alpha=0.22)
    ax_components.legend(fontsize=8)
    cap90 = matrix[
        matrix["scenario"].str.contains("cap_90")
        & matrix["cost_multiplier"].isin(COST_MULTIPLIERS)
    ].copy()
    xloc = np.arange(len(COST_MULTIPLIERS))
    width = 0.34
    for offset, combo_variant in [(-width / 2, RISK060_COMBO), (width / 2, RISK070_COMBO)]:
        sub = cap90[cap90["combo_variant"].eq(combo_variant)].sort_values("cost_multiplier")
        ax_cash.bar(xloc + offset, sub["extra_cash"].to_numpy(dtype=float) / 10_000.0, width, label=labels[combo_variant], color=colors[combo_variant], alpha=0.85)
    ax_cash.set_title("Exact extra cash: DD40 + broker10 <= 90%")
    ax_cash.set_xticks(xloc, [f"{int(item)}x cost" for item in COST_MULTIPLIERS])
    ax_cash.set_ylabel("Extra cash, 10k CNY")
    ax_cash.grid(True, axis="y", alpha=0.22)
    ax_cash.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _write_report(
    validation: pd.DataFrame,
    matrix: pd.DataFrame,
    events: pd.DataFrame,
    product_days: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    no_cash = matrix[matrix["scenario"].eq("no_extra_cash")].sort_values(["cost_multiplier", "combo_variant"])
    cap90 = matrix[matrix["scenario"].str.contains("cap_90")].sort_values(["cost_multiplier", "combo_variant"])
    report = [
        "# Stage214 Stage208精确持仓保证金审计",
        "",
        f"- 生成时间：{decision['generated_at']}",
        f"- line_id：`{LINE_ID}`",
        "- 阶段性质：只读精确持仓保证金审计；重跑固定 `risk060/risk070` C3 配置只为抽取每日持仓，不改策略逻辑、不新增信号、不扫参数。",
        "- 运行前过拟合判断：否。当前只是替代 Stage213 的保证金代理，验证固定候选能否更接近实盘。",
        "- 运行前继续价值判断：是。Stage213 已显示保证金是部署成败关键，需要更强证据。",
        "",
        "## 外部调研判断",
        "",
        "- 交易所规则显示保证金、结算准备金、强行平仓和风险警示都是真实交易约束，且交易所可按风险状态调整保证金；因此必须从持仓和合约保证金出发复核候选，而不是只看权益曲线。",
        "- 我的判断：本阶段仍不是最终券商保证金，因为历史逐日交易所/期货公司保证金率可能变化；但它已经比 `c3_margin * risk_multiplier` 更接近真实持仓口径。",
        "",
        "## 决策",
        "",
        f"- 决策标签：`{decision['decision']}`。",
        f"- `risk060` 1x 精确持仓最大回撤/最大 broker10 保证金：`{decision['risk060_1x_exact_max_dd_pct']:.4f}% / {decision['risk060_1x_exact_max_broker10_margin_pct']:.4f}%`。",
        f"- `risk060` 2x 成本最大回撤：`{decision['risk060_2x_exact_max_dd_pct']:.4f}%`。",
        f"- `risk060` 1x 若要求 broker10<=90% 所需现金：`{decision['risk060_1x_exact_cap90_extra_cash']:.0f}`。",
        f"- `risk070` 1x 精确持仓最大回撤/最大 broker10 保证金：`{decision['risk070_1x_exact_max_dd_pct']:.4f}% / {decision['risk070_1x_exact_max_broker10_margin_pct']:.4f}%`。",
        "",
        "## 代理口径校验",
        "",
        _md_table(validation),
        "",
        "## 无额外现金压力",
        "",
        _md_table(
            no_cash[
                [
                    "combo_variant",
                    "cost_multiplier",
                    "pnl_on_base_capital_pct",
                    "max_dd_pct",
                    "ulcer_pct",
                    "max_broker10_margin_to_equity_pct",
                    "days_over_100pct",
                    "days_over_90pct",
                    "dd40_pass",
                    "deploy_pass",
                ]
            ]
        ),
        "",
        "## broker10<=90% 且 DD40",
        "",
        _md_table(
            cap90[
                [
                    "combo_variant",
                    "cost_multiplier",
                    "extra_cash",
                    "cash_binding_reason",
                    "return_on_deployed_capital_pct",
                    "return_retention_vs_stage079_deployed_pct",
                    "max_dd_pct",
                    "max_broker10_margin_to_equity_pct",
                    "deploy_pass",
                ]
            ]
        ),
        "",
        "## 关键事件日",
        "",
        _md_table(
            events.sort_values(["combo_variant", "event_type", "broker10_margin_to_equity_pct"], ascending=[True, True, False])[
                [
                    "combo_variant",
                    "event_type",
                    "date",
                    "account_equity",
                    "c3_margin_exact",
                    "xsmom_true_margin",
                    "broker10_total_margin_exact",
                    "broker10_margin_to_equity_pct",
                    "drawdown_pct",
                ]
            ],
            max_rows=48,
        ),
        "",
        "## 关键事件日C3产品保证金",
        "",
        _md_table(
            product_days[
                [
                    "combo_variant",
                    "event_type",
                    "event_date",
                    "product_vt_symbol",
                    "c3_margin_exact",
                    "active_contracts",
                    "holding_pnl",
                    "trading_pnl",
                    "net_pnl",
                ]
            ].sort_values(["combo_variant", "event_date", "c3_margin_exact"], ascending=[True, True, False]),
            max_rows=96,
        ),
        "",
        "## 图表视觉复盘",
        "",
        "- 精确持仓保证金曲线显示 `risk060/risk070` 都多次穿越 100% 线，Stage213 代理口径低估了真实持仓保证金压力。",
        "- `risk060` 的保证金峰值主要集中在 2024-2025 的权益非低谷阶段；2022 深水下窗口也出现一次 100% 以上占用，说明风险来自“高名义持仓拥挤”和“弱窗口权益收缩”两类不同机制。",
        "- risk060 组件图显示大部分保证金来自 C3 主体，xsmom 只是边际叠加；下一步核心不是调 xsmom，而是核实 C3 持仓保证金率、合约乘数、券商加收和资金结构。",
        "- 90%现金缓冲图显示两者都需要数百万额外现金才能压到 broker10<=90%；此时 deployed return 被严重摊薄，已经不满足“保留大部分收益”的初衷。",
        "",
        "## 结论",
        "",
        "- 本阶段确认 `risk060 + true xsmom` 不能晋级部署候选：1x 最大 broker10 保证金/权益为 138.93%，穿 100% 共 17 天；虽然 1x/2x 成本下回撤仍守 DD40，但真实资金约束不通过。",
        "- 若强行用额外现金把 `risk060` 压到 broker10<=90%，需要约 377.07 万额外现金，部署收益降到约 457.57%，收益保留只剩 Stage079 部署收益的 9.25%，不符合当前目标。",
        "- `risk070 + true xsmom` 同样不进入实盘候选：收益略高，但精确持仓保证金最大 140.32%、穿 100% 共 25 天，且 2x 成本回撤跌破 DD40。",
        "- 本阶段仍不能标记总目标完成；下一步必须先复盘 exact-vs-proxy 保证金差异来源，再决定是修正保证金数据、降持仓名义风险，还是放弃当前组合形状。",
        "",
        "## 过拟合与继续价值反思",
        "",
        "- 运行后过拟合判断：否。没有改交易规则，只是重跑固定配置抽持仓并计算保证金。",
        "- 运行后继续价值判断：是。但继续方向不是把 `risk060` 当候选精修，而是查明保证金差异和寻找更低名义风险结构。",
    ]
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    metadata = _metadata()
    daily_frames: list[pd.DataFrame] = []
    position_frames: list[pd.DataFrame] = []
    for clean_variant in [RISK060_CLEAN, RISK070_CLEAN]:
        daily, positions = _run_c3_positions(clean_variant, metadata)
        daily_frames.append(daily)
        position_frames.append(positions)
    c3_daily = pd.concat(daily_frames, ignore_index=True)
    positions = pd.concat(position_frames, ignore_index=True)
    c3_margin_daily, product_margin = _position_margin(positions, metadata)
    stage208_daily = _load_stage208_daily()
    xsmom_daily = _load_xsmom_daily()
    margin_daily = _combine_margin(stage208_daily, c3_margin_daily, xsmom_daily)
    matrix = _deployment_matrix(margin_daily)
    events, product_days = _event_days(margin_daily, product_margin)
    validation = _validation(c3_daily, c3_margin_daily, margin_daily)
    decision = _decision(matrix, validation)
    _plot(margin_daily, matrix, product_days)
    _write_report(validation, matrix, events, product_days, decision)
    positions.to_csv(POSITIONS_PATH, index=False, encoding="utf-8-sig")
    margin_daily.to_csv(MARGIN_DAILY_PATH, index=False, encoding="utf-8-sig")
    matrix.to_csv(MATRIX_PATH, index=False, encoding="utf-8-sig")
    events.to_csv(EVENT_DAYS_PATH, index=False, encoding="utf-8-sig")
    product_days.to_csv(PRODUCT_DAYS_PATH, index=False, encoding="utf-8-sig")
    validation.to_csv(VALIDATION_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
