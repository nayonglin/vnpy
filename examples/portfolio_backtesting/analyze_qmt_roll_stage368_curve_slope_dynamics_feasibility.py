from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from qmt_universe import END_DT, START_DT
from run_qmt_alignment_backtest import OUTPUT_DIR
from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import (
    to_markdown_table,
)


PROJECT_DIR = Path(__file__).resolve().parent
MODEL_TAG = "stage368_curve_slope_dynamics_feasibility_v1"
OUTPUT_PREFIX = "qmt_roll_stage368_curve_slope_dynamics_feasibility"
LINE_ID = "futures_trend_drawdown30_preserve_return"

CONTRACT_ROOT = PROJECT_DIR / "downloaded_futures" / "tqsdk_daily_2010_2026_04"
UNIVERSE_PATH = (
    OUTPUT_DIR
    / "qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_static18_plus_fu_universe.csv"
)
C3_DAILY_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage336_c3_cash_reserve_multiperiod_daily_"
    "stage336_c3_cash_reserve_multiperiod_v1.csv"
)
C3_PROFILE = "c3_active100_cash0"
START_CAPITAL = 500_000.0

FEATURE_START_DT = datetime(2019, 10, 1)
MIN_MONTHS_TO_MATURITY = 1
MAX_MONTHS_TO_MATURITY = 24
MAX_NEAR_FAR_GAP_MONTHS = 18
LIQUID_TOP_N = 4
SLOPE_CHANGE_DAYS = 20
COST_BPS = 2.0
SATELLITE_WEIGHTS = (0.10, 0.20)
TARGET_MAX_DD_PCT = -30.0
RETURN_RETENTION_GATE_PCT = 80.0

CURVE_FEATURE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curve_features_{MODEL_TAG}.csv"
SATELLITE_DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_satellite_daily_{MODEL_TAG}.csv"
COMBO_DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_combo_daily_{MODEL_TAG}.csv"
COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coverage_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
WINDOW_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_summary_{MODEL_TAG}.csv"
ANNUAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_returns_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


@dataclass(frozen=True)
class ContractInfo:
    exchange: str
    product: str
    symbol: str
    contract_vt_symbol: str
    maturity_month: int
    maturity_year: int | None
    czce_year_digit: int | None


@dataclass(frozen=True)
class Window:
    name: str
    label: str
    start: datetime
    end: datetime


WINDOWS: tuple[Window, ...] = (
    Window("full_2020_2026", "2020起点至今", START_DT, END_DT),
    Window("since_2021", "2021起点至今", datetime(2021, 1, 1), END_DT),
    Window("since_2022", "2022起点至今", datetime(2022, 1, 1), END_DT),
    Window("since_2023", "2023起点至今", datetime(2023, 1, 1), END_DT),
    Window("since_2024", "2024起点至今", datetime(2024, 1, 1), END_DT),
    Window("weak_2021_dd", "2021已知回撤窗口", datetime(2021, 5, 12), datetime(2021, 7, 2)),
    Window("weak_2022_path", "2022弱路径窗口", datetime(2022, 3, 9), datetime(2022, 12, 7)),
    Window("ytd_2026", "2026年初至今", datetime(2026, 1, 1), END_DT),
)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or math.isinf(result):
        return default
    return result


def _fmt_pct(value: float | int | str | None, digits: int = 4) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.{digits}f}%"
    except (TypeError, ValueError):
        return str(value)


def _fmt_num(value: float | int | str | None, digits: int = 4) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


def _to_builtin(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _to_builtin(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_builtin(v) for v in value]
    if isinstance(value, tuple):
        return [_to_builtin(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if pd.isna(value) if not isinstance(value, (list, tuple, dict, str)) else False:
        return None
    return value


def _path_metrics_from_returns(returns: pd.Series, start_capital: float = START_CAPITAL) -> dict[str, float]:
    clean = pd.to_numeric(returns, errors="coerce").fillna(0.0).astype(float)
    if clean.empty:
        return {
            "end_balance": start_capital,
            "total_return_pct": 0.0,
            "max_dd_percent": 0.0,
            "sharpe_ratio": 0.0,
            "ulcer_index_pct": 0.0,
            "longest_underwater_days": 0,
        }

    nav = (1.0 + clean).cumprod()
    balance = nav * start_capital
    high = np.maximum.accumulate(balance.to_numpy(dtype=float))
    drawdown_pct = np.divide(
        balance.to_numpy(dtype=float) - high,
        high,
        out=np.zeros(len(balance), dtype=float),
        where=high != 0.0,
    ) * 100.0
    std = float(clean.std(ddof=1)) if len(clean) > 1 else 0.0
    sharpe = float(clean.mean() / std * np.sqrt(252.0)) if std > 0.0 else 0.0
    underwater = balance.to_numpy(dtype=float) < high
    longest = 0
    current = 0
    for flag in underwater:
        if flag:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return {
        "end_balance": float(balance.iloc[-1]),
        "total_return_pct": float((nav.iloc[-1] - 1.0) * 100.0),
        "max_dd_percent": float(drawdown_pct.min()) if len(drawdown_pct) else 0.0,
        "sharpe_ratio": sharpe,
        "ulcer_index_pct": float(np.sqrt(np.mean(np.square(drawdown_pct)))) if len(drawdown_pct) else 0.0,
        "longest_underwater_days": int(longest),
    }


def _parse_contract_path(path: Path) -> ContractInfo | None:
    exchange = path.parent.name
    symbol = path.stem
    match = re.fullmatch(r"([A-Za-z]+)(\d{3,4})", symbol)
    if not match:
        return None
    product, suffix = match.groups()
    if len(suffix) == 4:
        year = 2000 + int(suffix[:2])
        month = int(suffix[2:])
        year_digit = None
    else:
        year = None
        year_digit = int(suffix[0])
        month = int(suffix[1:])
    if month < 1 or month > 12:
        return None
    return ContractInfo(
        exchange=exchange,
        product=product,
        symbol=symbol,
        contract_vt_symbol=f"{symbol}.{exchange}",
        maturity_month=month,
        maturity_year=year,
        czce_year_digit=year_digit,
    )


def _infer_months_to_maturity(
    dates: pd.Series,
    maturity_month: int,
    maturity_year: int | None,
    czce_year_digit: int | None,
) -> np.ndarray:
    years = dates.dt.year.to_numpy(dtype=int)
    months = dates.dt.month.to_numpy(dtype=int)
    if maturity_year is not None:
        return (maturity_year - years) * 12 + (maturity_month - months)

    if czce_year_digit is None:
        return np.full(len(dates), np.nan)

    out = np.full(len(dates), np.nan)
    for idx, (trade_year, trade_month) in enumerate(zip(years, months, strict=False)):
        decade_base = (int(trade_year) // 10) * 10 + int(czce_year_digit)
        candidates = [decade_base - 10, decade_base, decade_base + 10]
        diffs = [
            (candidate_year - int(trade_year)) * 12 + (int(maturity_month) - int(trade_month))
            for candidate_year in candidates
        ]
        valid = [diff for diff in diffs if diff >= 0]
        out[idx] = float(min(valid)) if valid else np.nan
    return out


def _read_products() -> list[dict[str, str]]:
    universe = pd.read_csv(UNIVERSE_PATH, encoding="utf-8-sig")
    universe = universe[universe["eligible"].eq(1)].copy()
    universe = universe[universe["structural_prefilter_kept"].eq(1)].copy()
    products = (
        universe[["product_vt_symbol", "exchange", "product"]]
        .drop_duplicates()
        .sort_values("product_vt_symbol")
        .to_dict("records")
    )
    return [{str(k): str(v) for k, v in row.items()} for row in products]


def _load_contract_curve_rows(products: list[dict[str, str]]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for row in products:
        exchange = row["exchange"]
        product = row["product"]
        product_vt_symbol = row["product_vt_symbol"]
        exchange_dir = CONTRACT_ROOT / exchange
        if not exchange_dir.exists():
            continue
        for path in sorted(exchange_dir.glob(f"{product}*.csv")):
            info = _parse_contract_path(path)
            if info is None or info.product != product:
                continue
            try:
                frame = pd.read_csv(
                    path,
                    usecols=["trade_date", "close", "volume", "close_oi"],
                    encoding="utf-8-sig",
                )
            except (ValueError, FileNotFoundError):
                continue
            if frame.empty:
                continue
            frame["date"] = pd.to_datetime(frame["trade_date"], errors="coerce").dt.normalize()
            frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
            frame["volume"] = pd.to_numeric(frame["volume"], errors="coerce")
            frame["close_oi"] = pd.to_numeric(frame["close_oi"], errors="coerce")
            frame = frame[
                (frame["date"] >= pd.Timestamp(FEATURE_START_DT))
                & (frame["date"] <= pd.Timestamp(END_DT))
                & (frame["close"] > 0.0)
                & (frame["volume"] > 0.0)
                & (frame["close_oi"] > 0.0)
            ].copy()
            if frame.empty:
                continue
            frame["months_to_maturity"] = _infer_months_to_maturity(
                frame["date"],
                info.maturity_month,
                info.maturity_year,
                info.czce_year_digit,
            )
            frame = frame[
                (frame["months_to_maturity"] >= MIN_MONTHS_TO_MATURITY)
                & (frame["months_to_maturity"] <= MAX_MONTHS_TO_MATURITY)
            ].copy()
            if frame.empty:
                continue
            frame["exchange"] = exchange
            frame["product"] = product
            frame["product_vt_symbol"] = product_vt_symbol
            frame["contract_vt_symbol"] = info.contract_vt_symbol
            frames.append(
                frame[
                    [
                        "date",
                        "exchange",
                        "product",
                        "product_vt_symbol",
                        "contract_vt_symbol",
                        "close",
                        "volume",
                        "close_oi",
                        "months_to_maturity",
                    ]
                ]
            )

    if not frames:
        return pd.DataFrame()

    all_rows = pd.concat(frames, ignore_index=True)
    all_rows = all_rows.sort_values(["contract_vt_symbol", "date"]).reset_index(drop=True)
    grouped = all_rows.groupby("contract_vt_symbol", sort=False)
    all_rows["next_date"] = grouped["date"].shift(-1)
    all_rows["next_close"] = grouped["close"].shift(-1)
    all_rows["contract_return_1d"] = all_rows["next_close"] / all_rows["close"] - 1.0
    next_gap_days = (all_rows["next_date"] - all_rows["date"]).dt.days
    all_rows.loc[next_gap_days.gt(7) | next_gap_days.isna(), "contract_return_1d"] = np.nan
    return all_rows


def _select_daily_curves(contract_rows: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if contract_rows.empty:
        return pd.DataFrame()

    for (date, product), group in contract_rows.groupby(["date", "product_vt_symbol"], sort=True):
        liquid = group.sort_values(["close_oi", "volume"], ascending=False).head(LIQUID_TOP_N).copy()
        liquid = liquid.sort_values(["months_to_maturity", "close_oi"], ascending=[True, False])
        if len(liquid) < 2:
            continue
        near = liquid.iloc[0]
        farther = liquid[liquid["months_to_maturity"] > near["months_to_maturity"]].copy()
        if farther.empty:
            continue
        far = farther.iloc[0]
        gap = float(far["months_to_maturity"] - near["months_to_maturity"])
        if gap <= 0.0 or gap > MAX_NEAR_FAR_GAP_MONTHS:
            continue
        near_close = _safe_float(near["close"], np.nan)
        far_close = _safe_float(far["close"], np.nan)
        if not np.isfinite(near_close) or not np.isfinite(far_close) or near_close <= 0.0 or far_close <= 0.0:
            continue
        rows.append(
            {
                "date": pd.Timestamp(date),
                "product_vt_symbol": product,
                "near_contract": str(near["contract_vt_symbol"]),
                "far_contract": str(far["contract_vt_symbol"]),
                "near_months": float(near["months_to_maturity"]),
                "far_months": float(far["months_to_maturity"]),
                "month_gap": gap,
                "near_close": near_close,
                "far_close": far_close,
                "near_oi": float(near["close_oi"]),
                "far_oi": float(far["close_oi"]),
                "near_return_1d": _safe_float(near["contract_return_1d"], np.nan),
                "candidate_count": int(len(group)),
                "liquid_count": int(len(liquid)),
                "curve_slope": float(np.log(far_close / near_close) / gap),
            }
        )

    if not rows:
        return pd.DataFrame()
    features = pd.DataFrame(rows).sort_values(["product_vt_symbol", "date"]).reset_index(drop=True)
    features["slope_change_20d"] = features.groupby("product_vt_symbol")["curve_slope"].diff(SLOPE_CHANGE_DAYS)
    features["signal"] = -np.sign(features["slope_change_20d"]).fillna(0.0)
    features.loc[~np.isfinite(features["near_return_1d"]), "near_return_1d"] = np.nan
    return features


def _build_coverage(features: pd.DataFrame, products: list[dict[str, str]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for product in sorted({row["product_vt_symbol"] for row in products}):
        sub = features[features["product_vt_symbol"].eq(product)]
        rows.append(
            {
                "product_vt_symbol": product,
                "valid_curve_days": int(len(sub)),
                "first_date": str(sub["date"].min().date()) if not sub.empty else "",
                "last_date": str(sub["date"].max().date()) if not sub.empty else "",
                "median_candidate_count": float(sub["candidate_count"].median()) if not sub.empty else 0.0,
                "median_month_gap": float(sub["month_gap"].median()) if not sub.empty else 0.0,
                "signal_days": int(sub["signal"].ne(0.0).sum()) if not sub.empty else 0,
                "signal_coverage_pct": float(sub["signal"].ne(0.0).mean() * 100.0) if not sub.empty else 0.0,
            }
        )
    return pd.DataFrame(rows)


def _build_satellite_daily(features: pd.DataFrame, c3_dates: pd.Series) -> pd.DataFrame:
    valid = features[
        (features["date"] >= pd.Timestamp(START_DT))
        & (features["date"] <= pd.Timestamp(END_DT))
        & np.isfinite(features["near_return_1d"])
    ].copy()
    dates = pd.Index(pd.to_datetime(c3_dates).dt.normalize().drop_duplicates().sort_values(), name="date")
    if valid.empty:
        return pd.DataFrame({"date": dates, "satellite_return": 0.0})

    signal = valid.pivot_table(index="date", columns="product_vt_symbol", values="signal", aggfunc="last")
    forward_return = valid.pivot_table(
        index="date",
        columns="product_vt_symbol",
        values="near_return_1d",
        aggfunc="last",
    )
    signal = signal.reindex(dates).fillna(0.0)
    forward_return = forward_return.reindex(dates).fillna(0.0)
    active_count = signal.ne(0.0).sum(axis=1).replace(0, np.nan)
    weights = signal.div(active_count, axis=0).fillna(0.0)
    turnover = weights.diff().abs().sum(axis=1)
    if not turnover.empty:
        turnover.iloc[0] = weights.iloc[0].abs().sum()
    gross_return = (weights * forward_return).sum(axis=1)
    cost_return = turnover * (COST_BPS / 10_000.0)
    satellite_return = gross_return - cost_return
    out = pd.DataFrame(
        {
            "date": dates,
            "satellite_return": satellite_return.to_numpy(dtype=float),
            "gross_return": gross_return.to_numpy(dtype=float),
            "cost_return": cost_return.to_numpy(dtype=float),
            "turnover": turnover.to_numpy(dtype=float),
            "active_product_count": signal.ne(0.0).sum(axis=1).to_numpy(dtype=int),
            "long_count": signal.gt(0.0).sum(axis=1).to_numpy(dtype=int),
            "short_count": signal.lt(0.0).sum(axis=1).to_numpy(dtype=int),
        }
    )
    out["nav"] = (1.0 + out["satellite_return"]).cumprod()
    return out


def _load_c3_daily() -> pd.DataFrame:
    daily = pd.read_csv(C3_DAILY_PATH, encoding="utf-8-sig")
    daily = daily[(daily["profile"].eq(C3_PROFILE)) & (daily["window_name"].eq("start_2020"))].copy()
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
    daily["balance"] = pd.to_numeric(daily["balance"], errors="coerce")
    daily = daily.dropna(subset=["date", "balance"]).sort_values("date").reset_index(drop=True)
    previous = daily["balance"].shift(1)
    previous.iloc[0] = START_CAPITAL
    daily["c3_return"] = daily["balance"] / previous - 1.0
    daily["c3_nav"] = (1.0 + daily["c3_return"]).cumprod()
    return daily[["date", "balance", "c3_return", "c3_nav"]]


def _build_combo_daily(c3_daily: pd.DataFrame, satellite_daily: pd.DataFrame) -> pd.DataFrame:
    base = c3_daily.merge(
        satellite_daily[["date", "satellite_return", "active_product_count", "turnover"]],
        on="date",
        how="left",
    )
    base["satellite_return"] = pd.to_numeric(base["satellite_return"], errors="coerce").fillna(0.0)
    base["active_product_count"] = pd.to_numeric(base["active_product_count"], errors="coerce").fillna(0).astype(int)
    base["turnover"] = pd.to_numeric(base["turnover"], errors="coerce").fillna(0.0)

    rows: list[pd.DataFrame] = []
    variant_returns = {
        "C3_current_100": base["c3_return"],
        "slope_dynamic_standalone": base["satellite_return"],
    }
    for weight in SATELLITE_WEIGHTS:
        cash_label = f"C3_cash_{int((1.0 - weight) * 100)}_{int(weight * 100)}"
        slope_label = f"C3_slope_{int((1.0 - weight) * 100)}_{int(weight * 100)}"
        variant_returns[cash_label] = base["c3_return"] * (1.0 - weight)
        variant_returns[slope_label] = base["c3_return"] * (1.0 - weight) + base["satellite_return"] * weight

    for variant, returns in variant_returns.items():
        frame = pd.DataFrame(
            {
                "date": base["date"],
                "variant": variant,
                "daily_return": pd.to_numeric(returns, errors="coerce").fillna(0.0),
                "c3_return": base["c3_return"],
                "satellite_return": base["satellite_return"],
                "active_product_count": base["active_product_count"],
                "turnover": base["turnover"],
            }
        )
        frame["nav"] = (1.0 + frame["daily_return"]).cumprod()
        frame["balance"] = frame["nav"] * START_CAPITAL
        rows.append(frame)
    return pd.concat(rows, ignore_index=True)


def _summarize_variants(combo_daily: pd.DataFrame) -> pd.DataFrame:
    c3_metrics = _path_metrics_from_returns(
        combo_daily[combo_daily["variant"].eq("C3_current_100")].set_index("date")["daily_return"]
    )
    c3_return = c3_metrics["total_return_pct"]
    rows: list[dict[str, Any]] = []
    for variant, group in combo_daily.groupby("variant", sort=True):
        group = group.sort_values("date")
        metrics = _path_metrics_from_returns(group.set_index("date")["daily_return"])
        metrics.update(
            {
                "variant": variant,
                "return_retention_vs_c3_pct": (
                    metrics["total_return_pct"] / c3_return * 100.0 if c3_return != 0.0 else 0.0
                ),
                "avg_active_product_count": float(group["active_product_count"].mean()),
                "avg_turnover": float(group["turnover"].mean()),
            }
        )
        rows.append(metrics)
    out = pd.DataFrame(rows)
    order = {
        "C3_current_100": 0,
        "C3_cash_90_10": 1,
        "C3_slope_90_10": 2,
        "C3_cash_80_20": 3,
        "C3_slope_80_20": 4,
        "slope_dynamic_standalone": 5,
    }
    out["sort_key"] = out["variant"].map(order).fillna(99)
    return out.sort_values("sort_key").drop(columns=["sort_key"]).reset_index(drop=True)


def _window_summary(combo_daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for window in WINDOWS:
        for variant, group in combo_daily.groupby("variant", sort=True):
            sub = group[
                (group["date"] >= pd.Timestamp(window.start))
                & (group["date"] <= pd.Timestamp(window.end))
            ].copy()
            metrics = _path_metrics_from_returns(sub.set_index("date")["daily_return"]) if not sub.empty else {}
            rows.append(
                {
                    "window_name": window.name,
                    "window_label": window.label,
                    "variant": variant,
                    "trading_days": int(len(sub)),
                    "total_return_pct": float(metrics.get("total_return_pct", 0.0)),
                    "max_dd_percent": float(metrics.get("max_dd_percent", 0.0)),
                    "sharpe_ratio": float(metrics.get("sharpe_ratio", 0.0)),
                    "ulcer_index_pct": float(metrics.get("ulcer_index_pct", 0.0)),
                }
            )
    return pd.DataFrame(rows)


def _annual_returns(combo_daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (variant, year), group in combo_daily.groupby(["variant", combo_daily["date"].dt.year], sort=True):
        returns = pd.to_numeric(group["daily_return"], errors="coerce").fillna(0.0)
        rows.append(
            {
                "variant": variant,
                "year": int(year),
                "annual_return_pct": float(((1.0 + returns).prod() - 1.0) * 100.0),
                "trading_days": int(len(group)),
            }
        )
    return pd.DataFrame(rows)


def _build_decision(summary: pd.DataFrame, window_summary: pd.DataFrame) -> dict[str, Any]:
    slope_rows = summary[summary["variant"].str.startswith("C3_slope_")].copy()
    decisions: list[dict[str, Any]] = []
    for row in slope_rows.itertuples(index=False):
        variant = str(row.variant)
        cash_variant = variant.replace("slope", "cash")
        cash_row = summary[summary["variant"].eq(cash_variant)]
        cash_return = float(cash_row["total_return_pct"].iloc[0]) if not cash_row.empty else 0.0
        weak = window_summary[
            (window_summary["variant"].eq(variant))
            & (window_summary["window_name"].isin(["weak_2021_dd", "weak_2022_path"]))
        ]
        worst_weak_dd = float(weak["max_dd_percent"].min()) if not weak.empty else 0.0
        decisions.append(
            {
                "variant": variant,
                "max_dd_pass": bool(float(row.max_dd_percent) >= TARGET_MAX_DD_PCT),
                "retention_pass": bool(float(row.return_retention_vs_c3_pct) >= RETURN_RETENTION_GATE_PCT),
                "beats_cash_same_weight": bool(float(row.total_return_pct) > cash_return),
                "worst_weak_dd_percent": worst_weak_dd,
                "promote": bool(
                    float(row.max_dd_percent) >= TARGET_MAX_DD_PCT
                    and float(row.return_retention_vs_c3_pct) >= RETURN_RETENTION_GATE_PCT
                    and float(row.total_return_pct) > cash_return
                ),
            }
        )

    standalone = summary[summary["variant"].eq("slope_dynamic_standalone")]
    standalone_return = float(standalone["total_return_pct"].iloc[0]) if not standalone.empty else 0.0
    standalone_sharpe = float(standalone["sharpe_ratio"].iloc[0]) if not standalone.empty else 0.0
    promote_variants = [item["variant"] for item in decisions if item["promote"]]
    decision = "pass_next_validation" if promote_variants else "fail_curve_slope_dynamic_satellite_not_promoted"
    return {
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": decision,
        "promote_variants": promote_variants,
        "standalone_total_return_pct": standalone_return,
        "standalone_sharpe": standalone_sharpe,
        "candidate_checks": decisions,
        "pass_gates": {
            "target_max_dd_pct": TARGET_MAX_DD_PCT,
            "return_retention_gate_pct": RETURN_RETENTION_GATE_PCT,
            "must_beat_same_weight_cash_dilution": True,
        },
        "overfit_guard": (
            "固定20日斜率变化、固定10%/20%权重、固定2bps成本；不按结果搜索阈值、月份或品种黑名单。"
        ),
    }


def _write_report(
    products: list[dict[str, str]],
    coverage: pd.DataFrame,
    summary: pd.DataFrame,
    window_summary: pd.DataFrame,
    annual: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    summary_view = summary.copy()
    for col in ["total_return_pct", "max_dd_percent", "ulcer_index_pct", "return_retention_vs_c3_pct"]:
        summary_view[col] = summary_view[col].map(_fmt_pct)
    summary_view["end_balance"] = summary_view["end_balance"].map(lambda x: f"{float(x):,.2f}")
    summary_view["sharpe_ratio"] = summary_view["sharpe_ratio"].map(lambda x: _fmt_num(x, 4))
    summary_view = summary_view[
        [
            "variant",
            "end_balance",
            "total_return_pct",
            "max_dd_percent",
            "ulcer_index_pct",
            "sharpe_ratio",
            "return_retention_vs_c3_pct",
            "longest_underwater_days",
        ]
    ]

    coverage_view = coverage.copy()
    coverage_view["signal_coverage_pct"] = coverage_view["signal_coverage_pct"].map(_fmt_pct)

    window_focus = window_summary[
        window_summary["variant"].isin(["C3_current_100", "C3_slope_90_10", "C3_slope_80_20"])
    ].copy()
    for col in ["total_return_pct", "max_dd_percent", "ulcer_index_pct"]:
        window_focus[col] = window_focus[col].map(_fmt_pct)
    window_focus["sharpe_ratio"] = window_focus["sharpe_ratio"].map(lambda x: _fmt_num(x, 4))

    annual_focus = annual[
        annual["variant"].isin(["C3_current_100", "C3_slope_90_10", "C3_slope_80_20"])
    ].copy()
    annual_focus["annual_return_pct"] = annual_focus["annual_return_pct"].map(_fmt_pct)

    lines = [
        "# Stage068 期限结构斜率变化卫星探针",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：day",
        "- 记录时间：2026-05-26 22:40 CST",
        "- 阶段性质：低自由度独立收益源可行性探针；不修改第78-1或C3正式策略逻辑。",
        "- 是否触发A/B：是，作为潜在 C3 组合卫星进行 A/B/C 前置筛查。",
        "- 当前基准：`C3_current_100`，即当前回撤30以内保收益线的最强单策略研究基准。",
        "",
        "## 外部调研与判断",
        "",
        "- 文献线索显示，商品期货期限结构动态斜率不同于静态 carry；曲线向更强 backwardation 或更强 contango 变化本身可能包含独立信息。",
        "- 我的判断：这个方向有第一性原理价值，因为它使用同一品种不同到期合约的相对价格变化，信息来源不同于单一主力趋势。",
        "- 风险：本阶段只是净值层探针，不是完整整数手数真实引擎；若不能明显打败等权现金稀释，就不能晋级。",
        "",
        "## 预声明实验口径",
        "",
        f"- 品种池：官方 78-1 静态池加 `fu` 候选，共 `{len(products)}` 个品种。",
        f"- 曲线选择：每日每品种取持仓量前 `{LIQUID_TOP_N}` 的合约，选择最近液态合约与下一远月合约。",
        f"- 信号：`{SLOPE_CHANGE_DAYS}` 日曲线斜率变化；斜率下降视为动态 backwardation 做多，斜率上升视为动态 contango 做空。",
        f"- 成本：卫星腿固定 `{COST_BPS}` bps 换手成本。",
        "- 组合：只测 `C3 90% + 卫星10%`、`C3 80% + 卫星20%`，并和同权重现金稀释对照。",
        "- 晋级门槛：最大回撤进入30以内、收益保留不低于80%、并且总收益高于同权重现金稀释。",
        "",
        "## 汇总结果",
        "",
        to_markdown_table(summary_view),
        "",
        "## 分窗口结果",
        "",
        to_markdown_table(
            window_focus[
                [
                    "window_label",
                    "variant",
                    "trading_days",
                    "total_return_pct",
                    "max_dd_percent",
                    "ulcer_index_pct",
                    "sharpe_ratio",
                ]
            ]
        ),
        "",
        "## 年度收益",
        "",
        to_markdown_table(annual_focus[["variant", "year", "annual_return_pct", "trading_days"]]),
        "",
        "## 曲线覆盖",
        "",
        to_markdown_table(
            coverage_view[
                [
                    "product_vt_symbol",
                    "valid_curve_days",
                    "first_date",
                    "last_date",
                    "median_candidate_count",
                    "median_month_gap",
                    "signal_days",
                    "signal_coverage_pct",
                ]
            ]
        ),
        "",
        "## 结论",
        "",
        f"- 决策：`{decision['decision']}`。",
        f"- 晋级变体：`{decision['promote_variants']}`。",
        f"- 卫星独立腿总收益：`{_fmt_pct(decision['standalone_total_return_pct'])}`，Sharpe `{_fmt_num(decision['standalone_sharpe'], 4)}`。",
        "- 如果组合没有打败同权重现金稀释，说明改善主要来自降低 C3 暴露，不是独立收益源贡献。",
        "",
        "## 过拟合反思",
        "",
        "- 运行前判断：不是过拟合。原因是规则来自外部期限结构动态文献和第一性原理，且只做固定窗口、固定权重、固定成本。",
        "- 运行后判断：见决策；若失败，不再通过阈值、月份、品种小数微调救援。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前判断：有价值。原因是它尝试寻找真正独立收益源，而不是继续稀释或修补同源趋势逻辑。",
        "- 运行后判断：若无法打败现金稀释，本形状停止；若通过，再进入真实期货整数手数承载验证。",
        "",
        "## 输出文件",
        "",
        f"- features：`{CURVE_FEATURE_PATH.relative_to(PROJECT_DIR)}`",
        f"- satellite_daily：`{SATELLITE_DAILY_PATH.relative_to(PROJECT_DIR)}`",
        f"- combo_daily：`{COMBO_DAILY_PATH.relative_to(PROJECT_DIR)}`",
        f"- summary：`{SUMMARY_PATH.relative_to(PROJECT_DIR)}`",
        f"- decision：`{DECISION_PATH.relative_to(PROJECT_DIR)}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    products = _read_products()
    contract_rows = _load_contract_curve_rows(products)
    features = _select_daily_curves(contract_rows)
    coverage = _build_coverage(features, products)
    c3_daily = _load_c3_daily()
    satellite_daily = _build_satellite_daily(features, c3_daily["date"])
    combo_daily = _build_combo_daily(c3_daily, satellite_daily)
    summary = _summarize_variants(combo_daily)
    window = _window_summary(combo_daily)
    annual = _annual_returns(combo_daily)
    decision = _build_decision(summary, window)

    features.to_csv(CURVE_FEATURE_PATH, index=False, encoding="utf-8-sig")
    satellite_daily.to_csv(SATELLITE_DAILY_PATH, index=False, encoding="utf-8-sig")
    combo_daily.to_csv(COMBO_DAILY_PATH, index=False, encoding="utf-8-sig")
    coverage.to_csv(COVERAGE_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    window.to_csv(WINDOW_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    annual.to_csv(ANNUAL_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(
        json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _write_report(products, coverage, summary, window, annual, decision)

    print(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2))
    print(f"report={REPORT_PATH}")


if __name__ == "__main__":
    main()
