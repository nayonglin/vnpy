from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from main_contract_mapping import build_contract_metadata, load_product_universe_symbols
from qmt_roll_official_stage78_config import OFFICIAL_STAGE78_VERSION, build_official_stage78_manifest


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage124_stage78_concurrency_quality_attribution_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage78_concurrency_quality_attribution"
FORMAL_PREFIX: str = "qmt_roll_official_stage78_defensive_formal"
CAPITAL: float = 200_000.0
TRADING_DAYS_PER_YEAR: int = 240

DAILY_PATH: Path = OUTPUT_DIR / f"{FORMAL_PREFIX}_daily.csv"
POSITION_CHANGES_PATH: Path = OUTPUT_DIR / f"{FORMAL_PREFIX}_position_changes_2020_2026_04.csv"
CANDIDATE_PATH: Path = OUTPUT_DIR / f"{FORMAL_PREFIX}_entry_candidate_snapshots_2020_2026_04.csv"
ENTRY_RISK_PATH: Path = OUTPUT_DIR / f"{FORMAL_PREFIX}_entry_risk_diagnostics_2020_2026_04.csv"

DAILY_CONCURRENCY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_concurrency_{MODEL_TAG}.csv"
DAILY_BUCKET_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_bucket_summary_{MODEL_TAG}.csv"
ENTRY_QUALITY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_quality_{MODEL_TAG}.csv"
ENTRY_BUCKET_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_quality_by_active_before_{MODEL_TAG}.csv"
HYPOTHESIS_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_hypothesis_block_summary_{MODEL_TAG}.csv"
WORST_WINDOWS_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_worst_20d_windows_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _to_markdown_table(df: pd.DataFrame, columns: list[str], max_rows: int = 30) -> str:
    if df.empty:
        return "_No rows._"
    view = df.loc[:, [column for column in columns if column in df.columns]].head(max_rows).copy()
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda value: f"{value:.4f}")
    return "\n".join(
        [
            "| " + " | ".join(view.columns) + " |",
            "| " + " | ".join(["---"] * len(view.columns)) + " |",
            *["| " + " | ".join(map(str, row)) + " |" for row in view.to_numpy()],
        ]
    )


def _require(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"missing required Stage78 artifact: {path}")


def _product_from_contract(vt_symbol: object) -> str:
    raw = str(vt_symbol)
    if "." not in raw:
        return raw
    symbol, exchange = raw.split(".", 1)
    match = re.match(r"^([A-Za-z]+)", symbol)
    product = match.group(1) if match else symbol
    return f"{product}.{exchange}"


def _read_date_frame(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    if "date" in frame.columns:
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    return frame


def _bucket_active(value: float) -> str:
    if pd.isna(value) or value <= 0:
        return "0"
    if value <= 2:
        return "1-2"
    if value <= 4:
        return "3-4"
    if value <= 6:
        return "5-6"
    return "7+"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or math.isinf(result):
        return default
    return result


def _load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    for path in (DAILY_PATH, POSITION_CHANGES_PATH, CANDIDATE_PATH, ENTRY_RISK_PATH):
        _require(path)
    return (
        _read_date_frame(DAILY_PATH),
        _read_date_frame(POSITION_CHANGES_PATH),
        _read_date_frame(CANDIDATE_PATH),
        _read_date_frame(ENTRY_RISK_PATH),
    )


def _build_daily_exposure(positions: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    manifest = build_official_stage78_manifest()
    supported_symbols = load_product_universe_symbols(manifest["product_universe_csv_path"])
    metadata = build_contract_metadata(supported_symbols=supported_symbols)

    frame = positions.copy()
    frame["product_vt_symbol"] = frame["vt_symbol"].map(_product_from_contract)
    for column in ["start_pos", "end_pos", "close_price"]:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    frame["size"] = frame["vt_symbol"].map(metadata["sizes"]).fillna(1).astype(float)
    frame["margin_ratio"] = frame["vt_symbol"].map(metadata["margin_ratios"]).fillna(0.15).astype(float)
    frame["start_abs_pos"] = frame["start_pos"].abs()
    frame["end_abs_pos"] = frame["end_pos"].abs()
    frame["start_margin"] = frame["start_abs_pos"] * frame["close_price"].clip(lower=0.0) * frame["size"] * frame["margin_ratio"]
    frame["end_margin"] = frame["end_abs_pos"] * frame["close_price"].clip(lower=0.0) * frame["size"] * frame["margin_ratio"]

    product_daily = (
        frame.groupby(["date", "product_vt_symbol"], as_index=False)
        .agg(
            start_product_pos=("start_abs_pos", "sum"),
            end_product_pos=("end_abs_pos", "sum"),
            start_product_margin=("start_margin", "sum"),
            end_product_margin=("end_margin", "sum"),
            product_net_pnl=("net_pnl", "sum"),
            product_trade_count=("trade_count", "sum"),
        )
        .sort_values(["date", "product_vt_symbol"])
    )
    product_daily["start_active_product"] = (product_daily["start_product_pos"] > 0).astype(int)
    product_daily["end_active_product"] = (product_daily["end_product_pos"] > 0).astype(int)

    daily_exposure = (
        frame.groupby("date", as_index=False)
        .agg(
            start_active_contract_count=("start_abs_pos", lambda s: int((s > 0).sum())),
            end_active_contract_count=("end_abs_pos", lambda s: int((s > 0).sum())),
            start_total_margin=("start_margin", "sum"),
            end_total_margin=("end_margin", "sum"),
            max_start_contract_margin=("start_margin", "max"),
            max_end_contract_margin=("end_margin", "max"),
        )
        .sort_values("date")
    )
    product_counts = (
        product_daily.groupby("date", as_index=False)
        .agg(
            start_active_product_count=("start_active_product", "sum"),
            end_active_product_count=("end_active_product", "sum"),
            max_start_product_margin=("start_product_margin", "max"),
            max_end_product_margin=("end_product_margin", "max"),
        )
        .sort_values("date")
    )
    daily_exposure = daily_exposure.merge(product_counts, on="date", how="left")
    return daily_exposure, product_daily


def _build_daily_concurrency(daily: pd.DataFrame, daily_exposure: pd.DataFrame) -> pd.DataFrame:
    frame = daily.merge(daily_exposure, on="date", how="left").sort_values("date").reset_index(drop=True)
    for column in [
        "start_active_contract_count",
        "end_active_contract_count",
        "start_active_product_count",
        "end_active_product_count",
        "start_total_margin",
        "end_total_margin",
    ]:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    frame["previous_balance"] = pd.to_numeric(frame["balance"], errors="coerce").shift(1).fillna(CAPITAL)
    frame["daily_return_pct"] = (
        pd.to_numeric(frame["net_pnl"], errors="coerce").fillna(0.0)
        / frame["previous_balance"].replace(0.0, np.nan)
        * 100.0
    ).fillna(0.0)
    frame["start_margin_to_balance_pct"] = frame["start_total_margin"] / frame["previous_balance"].replace(0.0, np.nan) * 100.0
    frame["end_margin_to_balance_pct"] = frame["end_total_margin"] / pd.to_numeric(frame["balance"], errors="coerce").replace(0.0, np.nan) * 100.0
    frame["start_margin_to_balance_pct"] = frame["start_margin_to_balance_pct"].fillna(0.0)
    frame["end_margin_to_balance_pct"] = frame["end_margin_to_balance_pct"].fillna(0.0)
    frame["start_active_product_bucket"] = frame["start_active_product_count"].map(_bucket_active)
    frame["end_active_product_bucket"] = frame["end_active_product_count"].map(_bucket_active)
    frame["loss_day"] = (pd.to_numeric(frame["net_pnl"], errors="coerce").fillna(0.0) < 0).astype(int)
    frame["rolling_20d_net_pnl"] = pd.to_numeric(frame["net_pnl"], errors="coerce").fillna(0.0).rolling(20, min_periods=5).sum()
    frame["rolling_20d_avg_start_active_product"] = frame["start_active_product_count"].rolling(20, min_periods=5).mean()
    frame["rolling_20d_max_start_margin_pct"] = frame["start_margin_to_balance_pct"].rolling(20, min_periods=5).max()
    return frame


def _summarize_daily_buckets(daily_concurrency: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        daily_concurrency.groupby("start_active_product_bucket", as_index=False)
        .agg(
            day_count=("date", "count"),
            total_net_pnl=("net_pnl", "sum"),
            median_daily_return_pct=("daily_return_pct", "median"),
            mean_daily_return_pct=("daily_return_pct", "mean"),
            loss_day_rate_pct=("loss_day", "mean"),
            worst_daily_net_pnl=("net_pnl", "min"),
            median_start_active_product_count=("start_active_product_count", "median"),
            median_start_margin_to_balance_pct=("start_margin_to_balance_pct", "median"),
            max_start_margin_to_balance_pct=("start_margin_to_balance_pct", "max"),
            min_ddpercent=("ddpercent", "min"),
        )
        .sort_values("start_active_product_bucket")
    )
    grouped["loss_day_rate_pct"] = grouped["loss_day_rate_pct"] * 100.0
    return grouped


def _forward_product_pnl(product_daily: pd.DataFrame, product: str, date: pd.Timestamp, horizon_rows: int) -> float:
    product_frame = product_daily[
        (product_daily["product_vt_symbol"].astype(str) == str(product))
        & (product_daily["date"] >= date)
    ].sort_values("date")
    if product_frame.empty:
        return 0.0
    return float(pd.to_numeric(product_frame.head(horizon_rows)["product_net_pnl"], errors="coerce").fillna(0.0).sum())


def _build_entry_quality(candidates: pd.DataFrame, product_daily: pd.DataFrame) -> pd.DataFrame:
    opened = candidates[candidates["candidate_status"].astype(str).eq("opened")].copy()
    if opened.empty:
        return opened
    opened["datetime"] = pd.to_datetime(opened["datetime"], errors="coerce").dt.tz_localize(None)
    opened["date"] = pd.to_datetime(opened["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    numeric_columns = [
        "active_positions_before",
        "selection_pairwise_rank",
        "selection_pairwise_score",
        "ai_product_pool_rank",
        "same_direction_correlation_active_count",
        "same_direction_correlation_max_corr",
        "same_direction_correlation_avg_corr",
        "selected_volume",
        "target_risk_amount",
        "margin_per_contract",
        "projected_total_margin_after",
        "estimated_equity",
        "portfolio_drawdown_pct",
    ]
    for column in numeric_columns:
        if column in opened.columns:
            opened[column] = pd.to_numeric(opened[column], errors="coerce")
        else:
            opened[column] = np.nan
    opened["active_before_bucket"] = opened["active_positions_before"].map(_bucket_active)
    opened["forward_20d_product_net_pnl"] = [
        _forward_product_pnl(product_daily, row.product_vt_symbol, row.date, 20)
        for row in opened[["product_vt_symbol", "date"]].itertuples(index=False)
    ]
    opened["forward_63d_product_net_pnl"] = [
        _forward_product_pnl(product_daily, row.product_vt_symbol, row.date, 63)
        for row in opened[["product_vt_symbol", "date"]].itertuples(index=False)
    ]
    opened["forward_20d_positive"] = (opened["forward_20d_product_net_pnl"] > 0).astype(int)
    opened["forward_63d_positive"] = (opened["forward_63d_product_net_pnl"] > 0).astype(int)
    return opened


def _summarize_entry_quality(entry_quality: pd.DataFrame) -> pd.DataFrame:
    if entry_quality.empty:
        return pd.DataFrame()
    summary = (
        entry_quality.groupby("active_before_bucket", as_index=False)
        .agg(
            entry_count=("date", "count"),
            median_selection_rank=("selection_pairwise_rank", "median"),
            median_selection_score=("selection_pairwise_score", "median"),
            median_ai_rank=("ai_product_pool_rank", "median"),
            median_selected_volume=("selected_volume", "median"),
            median_same_direction_max_corr=("same_direction_correlation_max_corr", "median"),
            median_forward_20d_product_net_pnl=("forward_20d_product_net_pnl", "median"),
            total_forward_20d_product_net_pnl=("forward_20d_product_net_pnl", "sum"),
            forward_20d_positive_rate_pct=("forward_20d_positive", "mean"),
            median_forward_63d_product_net_pnl=("forward_63d_product_net_pnl", "median"),
            total_forward_63d_product_net_pnl=("forward_63d_product_net_pnl", "sum"),
            forward_63d_positive_rate_pct=("forward_63d_positive", "mean"),
        )
        .sort_values("active_before_bucket")
    )
    summary["forward_20d_positive_rate_pct"] = summary["forward_20d_positive_rate_pct"] * 100.0
    summary["forward_63d_positive_rate_pct"] = summary["forward_63d_positive_rate_pct"] * 100.0
    return summary


def _build_hypothesis_summary(entry_quality: pd.DataFrame) -> pd.DataFrame:
    if entry_quality.empty:
        return pd.DataFrame()
    hypotheses = {
        "active>=6_rank>8": (entry_quality["active_positions_before"] >= 6)
        & (entry_quality["selection_pairwise_rank"] > 8),
        "active>=6_rank>10": (entry_quality["active_positions_before"] >= 6)
        & (entry_quality["selection_pairwise_rank"] > 10),
        "active>=6_ai_rank>8": (entry_quality["active_positions_before"] >= 6)
        & (entry_quality["ai_product_pool_rank"] > 8),
        "active>=6_corr>0.6": (entry_quality["active_positions_before"] >= 6)
        & (entry_quality["same_direction_correlation_max_corr"] > 0.6),
        "active>=5_rank>8_corr>0.5": (entry_quality["active_positions_before"] >= 5)
        & (entry_quality["selection_pairwise_rank"] > 8)
        & (entry_quality["same_direction_correlation_max_corr"] > 0.5),
    }
    rows: list[dict[str, Any]] = []
    for name, mask in hypotheses.items():
        subset = entry_quality[mask.fillna(False)].copy()
        rows.append(
            {
                "hypothesis": name,
                "blocked_entry_count": int(len(subset)),
                "blocked_entry_rate_pct": len(subset) / len(entry_quality) * 100.0 if len(entry_quality) else 0.0,
                "median_selection_rank": _safe_float(subset["selection_pairwise_rank"].median()) if not subset.empty else 0.0,
                "median_ai_rank": _safe_float(subset["ai_product_pool_rank"].median()) if not subset.empty else 0.0,
                "median_forward_20d_product_net_pnl": _safe_float(subset["forward_20d_product_net_pnl"].median()) if not subset.empty else 0.0,
                "total_forward_20d_product_net_pnl": _safe_float(subset["forward_20d_product_net_pnl"].sum()) if not subset.empty else 0.0,
                "forward_20d_positive_rate_pct": _safe_float(subset["forward_20d_positive"].mean() * 100.0) if not subset.empty else 0.0,
                "median_forward_63d_product_net_pnl": _safe_float(subset["forward_63d_product_net_pnl"].median()) if not subset.empty else 0.0,
                "total_forward_63d_product_net_pnl": _safe_float(subset["forward_63d_product_net_pnl"].sum()) if not subset.empty else 0.0,
                "forward_63d_positive_rate_pct": _safe_float(subset["forward_63d_positive"].mean() * 100.0) if not subset.empty else 0.0,
            }
        )
    return pd.DataFrame(rows).sort_values("total_forward_20d_product_net_pnl")


def _build_worst_windows(daily_concurrency: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "date",
        "rolling_20d_net_pnl",
        "rolling_20d_avg_start_active_product",
        "rolling_20d_max_start_margin_pct",
        "balance",
        "ddpercent",
    ]
    return (
        daily_concurrency.dropna(subset=["rolling_20d_net_pnl"])
        .nsmallest(20, "rolling_20d_net_pnl")[columns]
        .copy()
    )


def _build_report(
    daily_bucket: pd.DataFrame,
    entry_bucket: pd.DataFrame,
    hypothesis: pd.DataFrame,
    worst_windows: pd.DataFrame,
) -> str:
    return "\n".join(
        [
            "# Stage124 Stage78 Concurrency Quality Attribution",
            "",
            "## Boundary",
            "",
            f"- Base version: `{OFFICIAL_STAGE78_VERSION}`",
            "- This is attribution only. No trading rule is changed.",
            "- Forward product PnL is a proxy for entry quality, not a formal realized-trade PnL.",
            "",
            "## Daily Concurrency Buckets",
            "",
            _to_markdown_table(
                daily_bucket,
                [
                    "start_active_product_bucket",
                    "day_count",
                    "total_net_pnl",
                    "median_daily_return_pct",
                    "loss_day_rate_pct",
                    "worst_daily_net_pnl",
                    "median_start_margin_to_balance_pct",
                    "max_start_margin_to_balance_pct",
                    "min_ddpercent",
                ],
            ),
            "",
            "## Opened Entry Quality By Active Positions Before Entry",
            "",
            _to_markdown_table(
                entry_bucket,
                [
                    "active_before_bucket",
                    "entry_count",
                    "median_selection_rank",
                    "median_ai_rank",
                    "median_forward_20d_product_net_pnl",
                    "total_forward_20d_product_net_pnl",
                    "forward_20d_positive_rate_pct",
                    "median_forward_63d_product_net_pnl",
                    "total_forward_63d_product_net_pnl",
                    "forward_63d_positive_rate_pct",
                ],
            ),
            "",
            "## Candidate Block Hypotheses",
            "",
            _to_markdown_table(
                hypothesis,
                [
                    "hypothesis",
                    "blocked_entry_count",
                    "blocked_entry_rate_pct",
                    "median_selection_rank",
                    "median_ai_rank",
                    "total_forward_20d_product_net_pnl",
                    "forward_20d_positive_rate_pct",
                    "total_forward_63d_product_net_pnl",
                    "forward_63d_positive_rate_pct",
                ],
            ),
            "",
            "## Worst Rolling 20D Windows",
            "",
            _to_markdown_table(
                worst_windows,
                [
                    "date",
                    "rolling_20d_net_pnl",
                    "rolling_20d_avg_start_active_product",
                    "rolling_20d_max_start_margin_pct",
                    "balance",
                    "ddpercent",
                ],
            ),
            "",
            "## Judgement",
            "",
            "- If high concurrency has positive forward entry quality, simple max-position cuts are likely to destroy edge.",
            "- A viable next rule must block low-quality incremental entries only when the portfolio is already crowded.",
        ]
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    daily, positions, candidates, _entry_risk = _load_inputs()
    daily_exposure, product_daily = _build_daily_exposure(positions)
    daily_concurrency = _build_daily_concurrency(daily, daily_exposure)
    daily_bucket = _summarize_daily_buckets(daily_concurrency)
    entry_quality = _build_entry_quality(candidates, product_daily)
    entry_bucket = _summarize_entry_quality(entry_quality)
    hypothesis = _build_hypothesis_summary(entry_quality)
    worst_windows = _build_worst_windows(daily_concurrency)

    daily_concurrency.to_csv(DAILY_CONCURRENCY_PATH, index=False, encoding="utf-8-sig")
    daily_bucket.to_csv(DAILY_BUCKET_PATH, index=False, encoding="utf-8-sig")
    entry_quality.to_csv(ENTRY_QUALITY_PATH, index=False, encoding="utf-8-sig")
    entry_bucket.to_csv(ENTRY_BUCKET_PATH, index=False, encoding="utf-8-sig")
    hypothesis.to_csv(HYPOTHESIS_PATH, index=False, encoding="utf-8-sig")
    worst_windows.to_csv(WORST_WINDOWS_PATH, index=False, encoding="utf-8-sig")

    payload = {
        "model_tag": MODEL_TAG,
        "base_version": OFFICIAL_STAGE78_VERSION,
        "daily_bucket": daily_bucket.to_dict(orient="records"),
        "entry_bucket": entry_bucket.to_dict(orient="records"),
        "hypothesis": hypothesis.to_dict(orient="records"),
        "output_paths": {
            "daily_concurrency": str(DAILY_CONCURRENCY_PATH),
            "daily_bucket": str(DAILY_BUCKET_PATH),
            "entry_quality": str(ENTRY_QUALITY_PATH),
            "entry_bucket": str(ENTRY_BUCKET_PATH),
            "hypothesis": str(HYPOTHESIS_PATH),
            "worst_windows": str(WORST_WINDOWS_PATH),
            "report": str(REPORT_PATH),
        },
    }
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    REPORT_PATH.write_text(_build_report(daily_bucket, entry_bucket, hypothesis, worst_windows), encoding="utf-8")

    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    print(f"[stage124-concurrency-quality] report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
