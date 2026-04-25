from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage127_stage78_profit_drawdown_attribution_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage127_stage78_profit_drawdown_attribution"
FORMAL_PREFIX: str = "qmt_roll_official_stage78_defensive_formal"
CAPITAL: float = 200_000.0

DAILY_PATH: Path = OUTPUT_DIR / f"{FORMAL_PREFIX}_daily.csv"
POSITIONS_PATH: Path = OUTPUT_DIR / f"{FORMAL_PREFIX}_position_changes_2020_2026_04.csv"
CANDIDATES_PATH: Path = OUTPUT_DIR / f"{FORMAL_PREFIX}_entry_candidate_snapshots_2020_2026_04.csv"

EPISODE_SUMMARY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_drawdown_episode_summary_{MODEL_TAG}.csv"
PROFIT_WINDOW_SUMMARY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_profit_window_summary_{MODEL_TAG}.csv"
SEGMENT_PRODUCT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_segment_product_attribution_{MODEL_TAG}.csv"
SEGMENT_DIRECTION_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_segment_direction_attribution_{MODEL_TAG}.csv"
SEGMENT_ENTRY_SIGNAL_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_segment_entry_signal_attribution_{MODEL_TAG}.csv"
FULL_PRODUCT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_full_product_attribution_{MODEL_TAG}.csv"
FULL_DIRECTION_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_full_direction_attribution_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


@dataclass(frozen=True)
class Segment:
    segment_id: str
    segment_type: str
    start_date: pd.Timestamp
    end_date: pd.Timestamp
    trough_date: pd.Timestamp | None = None
    rolling_window_days: int = 0


def _require(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"missing required Stage78 artifact: {path}")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or math.isinf(result):
        return default
    return result


def _product_from_contract(vt_symbol: object) -> str:
    raw = str(vt_symbol)
    if "." not in raw:
        return raw
    symbol, exchange = raw.split(".", 1)
    match = re.match(r"^([A-Za-z]+)", symbol)
    product = match.group(1) if match else symbol
    return f"{product}.{exchange}"


def _to_markdown_table(df: pd.DataFrame, columns: list[str], max_rows: int = 20) -> str:
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


def _load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    for path in (DAILY_PATH, POSITIONS_PATH, CANDIDATES_PATH):
        _require(path)
    daily = pd.read_csv(DAILY_PATH)
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    daily = daily.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    for column in ["net_pnl", "balance", "highlevel", "drawdown", "ddpercent", "trade_count", "slippage"]:
        daily[column] = pd.to_numeric(daily.get(column, 0.0), errors="coerce").fillna(0.0)

    positions = pd.read_csv(POSITIONS_PATH)
    positions["date"] = pd.to_datetime(positions["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    positions = positions.dropna(subset=["date"]).copy()
    for column in ["start_pos", "end_pos", "pos_change", "net_pnl", "trade_count", "slippage"]:
        positions[column] = pd.to_numeric(positions.get(column, 0.0), errors="coerce").fillna(0.0)
    positions["product_vt_symbol"] = positions["vt_symbol"].map(_product_from_contract)
    signed_exposure = positions["start_pos"].where(positions["start_pos"].abs() > 0, positions["end_pos"])
    signed_exposure = signed_exposure.where(signed_exposure.abs() > 0, positions["pos_change"])
    positions["position_direction"] = np.where(signed_exposure > 0, "long", np.where(signed_exposure < 0, "short", "flat"))

    candidates = pd.read_csv(CANDIDATES_PATH)
    candidates["date"] = pd.to_datetime(candidates["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    candidates = candidates.dropna(subset=["date"]).copy()
    for column in [
        "selected_volume",
        "selection_pairwise_rank",
        "ai_product_pool_rank",
        "active_positions_before",
        "same_direction_correlation_max_corr",
        "portfolio_drawdown_pct",
    ]:
        candidates[column] = pd.to_numeric(candidates.get(column, 0.0), errors="coerce").fillna(0.0)
    return daily, positions, candidates


def _build_drawdown_episodes(daily: pd.DataFrame) -> pd.DataFrame:
    episodes: list[dict[str, Any]] = []
    in_drawdown = False
    start_index = 0
    trough_index = 0
    for index, row in daily.iterrows():
        dd = float(row["ddpercent"])
        if dd < 0 and not in_drawdown:
            in_drawdown = True
            start_index = max(0, index - 1)
            trough_index = index
        if in_drawdown:
            if dd < float(daily.loc[trough_index, "ddpercent"]):
                trough_index = index
            is_recovered = dd >= 0 and index > start_index
            is_last = index == len(daily) - 1
            if is_recovered or is_last:
                end_index = index
                segment = daily.iloc[start_index : end_index + 1].copy()
                start_balance = float(daily.loc[start_index, "balance"])
                end_balance = float(daily.loc[end_index, "balance"])
                trough_balance = float(daily.loc[trough_index, "balance"])
                episodes.append(
                    {
                        "segment_id": f"dd_{len(episodes) + 1:02d}",
                        "segment_type": "drawdown_episode",
                        "start_date": daily.loc[start_index, "date"].date().isoformat(),
                        "trough_date": daily.loc[trough_index, "date"].date().isoformat(),
                        "end_date": daily.loc[end_index, "date"].date().isoformat(),
                        "calendar_days": int((daily.loc[end_index, "date"] - daily.loc[start_index, "date"]).days),
                        "trading_days": int(len(segment)),
                        "start_balance": start_balance,
                        "trough_balance": trough_balance,
                        "end_balance": end_balance,
                        "segment_net_pnl": float(segment["net_pnl"].sum()),
                        "trough_loss_amount": trough_balance - start_balance,
                        "max_dd_percent": float(daily.loc[trough_index, "ddpercent"]),
                        "total_trade_count": int(segment["trade_count"].sum()),
                        "total_slippage": float(segment["slippage"].sum()),
                    }
                )
                in_drawdown = False
    return pd.DataFrame(episodes).sort_values("max_dd_percent").reset_index(drop=True)


def _build_profit_windows(daily: pd.DataFrame, *, window_days: int = 20, top_n: int = 10) -> pd.DataFrame:
    frame = daily[["date", "net_pnl", "balance", "ddpercent", "trade_count", "slippage"]].copy()
    frame["rolling_net_pnl"] = frame["net_pnl"].rolling(window_days, min_periods=window_days).sum()
    frame["rolling_trade_count"] = frame["trade_count"].rolling(window_days, min_periods=window_days).sum()
    candidates = frame.dropna(subset=["rolling_net_pnl"]).sort_values("rolling_net_pnl", ascending=False)
    selected: list[dict[str, Any]] = []
    used_ranges: list[tuple[int, int]] = []
    for end_index in candidates.index:
        end_pos = int(end_index)
        start_pos = end_pos - window_days + 1
        if start_pos < 0:
            continue
        overlaps = any(not (end_pos < used_start or start_pos > used_end) for used_start, used_end in used_ranges)
        if overlaps:
            continue
        segment = daily.iloc[start_pos : end_pos + 1].copy()
        selected.append(
            {
                "segment_id": f"profit20_{len(selected) + 1:02d}",
                "segment_type": "profit_window",
                "start_date": daily.loc[start_pos, "date"].date().isoformat(),
                "end_date": daily.loc[end_pos, "date"].date().isoformat(),
                "rolling_window_days": window_days,
                "trading_days": int(len(segment)),
                "segment_net_pnl": float(segment["net_pnl"].sum()),
                "segment_return_on_start_balance_pct": float(
                    segment["net_pnl"].sum() / max(float(daily.loc[start_pos, "balance"]), 1e-9) * 100.0
                ),
                "min_ddpercent": float(segment["ddpercent"].min()),
                "total_trade_count": int(segment["trade_count"].sum()),
                "total_slippage": float(segment["slippage"].sum()),
            }
        )
        used_ranges.append((start_pos, end_pos))
        if len(selected) >= top_n:
            break
    return pd.DataFrame(selected)


def _segment_rows_from_summary(drawdowns: pd.DataFrame, profits: pd.DataFrame, top_drawdowns: int = 8) -> list[Segment]:
    segments: list[Segment] = []
    for row in drawdowns.head(top_drawdowns).itertuples(index=False):
        segments.append(
            Segment(
                segment_id=str(row.segment_id),
                segment_type="drawdown_episode",
                start_date=pd.Timestamp(row.start_date),
                end_date=pd.Timestamp(row.end_date),
                trough_date=pd.Timestamp(row.trough_date),
            )
        )
        segments.append(
            Segment(
                segment_id=f"{row.segment_id}_to_trough",
                segment_type="drawdown_to_trough",
                start_date=pd.Timestamp(row.start_date),
                end_date=pd.Timestamp(row.trough_date),
                trough_date=pd.Timestamp(row.trough_date),
            )
        )
    for row in profits.itertuples(index=False):
        segments.append(
            Segment(
                segment_id=str(row.segment_id),
                segment_type="profit_window",
                start_date=pd.Timestamp(row.start_date),
                end_date=pd.Timestamp(row.end_date),
                rolling_window_days=int(row.rolling_window_days),
            )
        )
    return segments


def _slice_by_segment(frame: pd.DataFrame, segment: Segment) -> pd.DataFrame:
    return frame[(frame["date"] >= segment.start_date) & (frame["date"] <= segment.end_date)].copy()


def _build_segment_product_attribution(positions: pd.DataFrame, segments: list[Segment]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for segment in segments:
        subset = _slice_by_segment(positions, segment)
        if subset.empty:
            continue
        grouped = (
            subset.groupby("product_vt_symbol", as_index=False)
            .agg(
                segment_net_pnl=("net_pnl", "sum"),
                trade_count=("trade_count", "sum"),
                slippage=("slippage", "sum"),
                active_days=("end_pos", lambda s: int((pd.to_numeric(s, errors="coerce").abs() > 0).sum())),
            )
            .sort_values("segment_net_pnl", ascending=segment.segment_type == "drawdown_episode")
        )
        grouped["segment_id"] = segment.segment_id
        grouped["segment_type"] = segment.segment_type
        grouped["start_date"] = segment.start_date.date().isoformat()
        grouped["end_date"] = segment.end_date.date().isoformat()
        rows.extend(grouped.head(12).to_dict(orient="records"))
    return pd.DataFrame(rows)


def _build_segment_direction_attribution(positions: pd.DataFrame, segments: list[Segment]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for segment in segments:
        subset = _slice_by_segment(positions, segment)
        if subset.empty:
            continue
        grouped = (
            subset.groupby(["position_direction"], as_index=False)
            .agg(
                segment_net_pnl=("net_pnl", "sum"),
                trade_count=("trade_count", "sum"),
                slippage=("slippage", "sum"),
            )
            .sort_values("segment_net_pnl")
        )
        grouped["segment_id"] = segment.segment_id
        grouped["segment_type"] = segment.segment_type
        grouped["start_date"] = segment.start_date.date().isoformat()
        grouped["end_date"] = segment.end_date.date().isoformat()
        rows.extend(grouped.to_dict(orient="records"))
    return pd.DataFrame(rows)


def _build_segment_entry_signal_attribution(candidates: pd.DataFrame, segments: list[Segment]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    opened = candidates[candidates["candidate_status"].astype(str).eq("opened")].copy()
    for segment in segments:
        subset = _slice_by_segment(opened, segment)
        if subset.empty:
            continue
        grouped = (
            subset.groupby(["direction", "signal"], as_index=False)
            .agg(
                entry_count=("candidate_index", "count"),
                median_selection_rank=("selection_pairwise_rank", "median"),
                median_ai_rank=("ai_product_pool_rank", "median"),
                median_selected_volume=("selected_volume", "median"),
                median_active_before=("active_positions_before", "median"),
                median_same_direction_corr=("same_direction_correlation_max_corr", "median"),
                median_portfolio_drawdown_pct=("portfolio_drawdown_pct", "median"),
            )
            .sort_values("entry_count", ascending=False)
        )
        grouped["segment_id"] = segment.segment_id
        grouped["segment_type"] = segment.segment_type
        grouped["start_date"] = segment.start_date.date().isoformat()
        grouped["end_date"] = segment.end_date.date().isoformat()
        rows.extend(grouped.to_dict(orient="records"))
    return pd.DataFrame(rows)


def _build_full_product_attribution(positions: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        positions.groupby("product_vt_symbol", as_index=False)
        .agg(
            full_net_pnl=("net_pnl", "sum"),
            trade_count=("trade_count", "sum"),
            slippage=("slippage", "sum"),
            active_days=("end_pos", lambda s: int((pd.to_numeric(s, errors="coerce").abs() > 0).sum())),
        )
        .sort_values("full_net_pnl", ascending=False)
        .reset_index(drop=True)
    )
    grouped["pnl_rank"] = grouped.index + 1
    return grouped


def _build_full_direction_attribution(positions: pd.DataFrame) -> pd.DataFrame:
    return (
        positions.groupby("position_direction", as_index=False)
        .agg(
            full_net_pnl=("net_pnl", "sum"),
            trade_count=("trade_count", "sum"),
            slippage=("slippage", "sum"),
        )
        .sort_values("full_net_pnl", ascending=False)
        .reset_index(drop=True)
    )


def _build_report(
    drawdowns: pd.DataFrame,
    profits: pd.DataFrame,
    segment_product: pd.DataFrame,
    full_product: pd.DataFrame,
    full_direction: pd.DataFrame,
) -> str:
    worst_dd = drawdowns.head(5).copy()
    top_profit = profits.head(5).copy()
    top_full = full_product.head(12).copy()
    bottom_full = full_product.tail(12).sort_values("full_net_pnl").copy()
    worst_products = segment_product[segment_product["segment_type"].astype(str).eq("drawdown_to_trough")].copy()
    if not worst_products.empty:
        worst_products = worst_products.sort_values(["segment_id", "segment_net_pnl"]).head(20)
    profit_products = segment_product[segment_product["segment_type"].astype(str).eq("profit_window")].copy()
    if not profit_products.empty:
        profit_products = profit_products.sort_values(["segment_id", "segment_net_pnl"], ascending=[True, False]).head(20)

    return "\n".join(
        [
            "# Stage127 Stage78 Profit Drawdown Attribution",
            "",
            "## Boundary",
            "",
            "- Base version: `official_stage78_defensive_v1`.",
            "- Attribution only. No trading rule is changed.",
            "- Objective: identify where Stage78 earns money and where drawdowns come from before designing new rules.",
            "",
            "## Worst Drawdown Episodes",
            "",
            _to_markdown_table(
                worst_dd,
                [
                    "segment_id",
                    "start_date",
                    "trough_date",
                    "end_date",
                    "trading_days",
                    "segment_net_pnl",
                    "trough_loss_amount",
                    "max_dd_percent",
                    "total_trade_count",
                ],
            ),
            "",
            "## Top Non-overlapping 20D Profit Windows",
            "",
            _to_markdown_table(
                top_profit,
                [
                    "segment_id",
                    "start_date",
                    "end_date",
                    "segment_net_pnl",
                    "segment_return_on_start_balance_pct",
                    "min_ddpercent",
                    "total_trade_count",
                ],
            ),
            "",
            "## Full-cycle Product Winners",
            "",
            _to_markdown_table(
                top_full,
                ["product_vt_symbol", "full_net_pnl", "trade_count", "slippage", "active_days", "pnl_rank"],
            ),
            "",
            "## Full-cycle Product Losers",
            "",
            _to_markdown_table(
                bottom_full,
                ["product_vt_symbol", "full_net_pnl", "trade_count", "slippage", "active_days", "pnl_rank"],
            ),
            "",
            "## Full-cycle Direction Attribution",
            "",
            _to_markdown_table(
                full_direction,
                ["position_direction", "full_net_pnl", "trade_count", "slippage"],
            ),
            "",
            "## Worst Trough-phase Product Drivers",
            "",
            _to_markdown_table(
                worst_products,
                ["segment_id", "product_vt_symbol", "segment_net_pnl", "trade_count", "slippage", "active_days"],
            ),
            "",
            "## Top Profit Window Product Drivers",
            "",
            _to_markdown_table(
                profit_products,
                ["segment_id", "product_vt_symbol", "segment_net_pnl", "trade_count", "slippage", "active_days"],
            ),
            "",
            "## Judgement",
            "",
            "- This stage should not be used to blacklist a single product directly.",
            "- A valid next rule must be structural, for example cutting risk after position-level adverse behavior rather than product-name filtering.",
        ]
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    daily, positions, candidates = _load_inputs()
    drawdowns = _build_drawdown_episodes(daily)
    profits = _build_profit_windows(daily, window_days=20, top_n=10)
    segments = _segment_rows_from_summary(drawdowns, profits)
    segment_product = _build_segment_product_attribution(positions, segments)
    segment_direction = _build_segment_direction_attribution(positions, segments)
    segment_entry_signal = _build_segment_entry_signal_attribution(candidates, segments)
    full_product = _build_full_product_attribution(positions)
    full_direction = _build_full_direction_attribution(positions)

    drawdowns.to_csv(EPISODE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    profits.to_csv(PROFIT_WINDOW_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    segment_product.to_csv(SEGMENT_PRODUCT_PATH, index=False, encoding="utf-8-sig")
    segment_direction.to_csv(SEGMENT_DIRECTION_PATH, index=False, encoding="utf-8-sig")
    segment_entry_signal.to_csv(SEGMENT_ENTRY_SIGNAL_PATH, index=False, encoding="utf-8-sig")
    full_product.to_csv(FULL_PRODUCT_PATH, index=False, encoding="utf-8-sig")
    full_direction.to_csv(FULL_DIRECTION_PATH, index=False, encoding="utf-8-sig")

    summary = {
        "model_tag": MODEL_TAG,
        "base_version": "official_stage78_defensive_v1",
        "capital": CAPITAL,
        "drawdown_episode_count": int(len(drawdowns)),
        "profit_window_count": int(len(profits)),
        "worst_drawdown": drawdowns.head(1).to_dict(orient="records"),
        "top_profit_window": profits.head(1).to_dict(orient="records"),
        "top_product_winners": full_product.head(8).to_dict(orient="records"),
        "top_product_losers": full_product.tail(8).sort_values("full_net_pnl").to_dict(orient="records"),
        "direction_attribution": full_direction.to_dict(orient="records"),
        "output_paths": {
            "drawdown_episode_summary": str(EPISODE_SUMMARY_PATH),
            "profit_window_summary": str(PROFIT_WINDOW_SUMMARY_PATH),
            "segment_product_attribution": str(SEGMENT_PRODUCT_PATH),
            "segment_direction_attribution": str(SEGMENT_DIRECTION_PATH),
            "segment_entry_signal_attribution": str(SEGMENT_ENTRY_SIGNAL_PATH),
            "full_product_attribution": str(FULL_PRODUCT_PATH),
            "full_direction_attribution": str(FULL_DIRECTION_PATH),
            "report": str(REPORT_PATH),
        },
    }
    SUMMARY_JSON_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(
        _build_report(drawdowns, profits, segment_product, full_product, full_direction),
        encoding="utf-8",
    )

    print(f"[stage127-stage78-attribution] drawdown episodes: {EPISODE_SUMMARY_PATH}")
    print(f"[stage127-stage78-attribution] profit windows: {PROFIT_WINDOW_SUMMARY_PATH}")
    print(f"[stage127-stage78-attribution] segment product: {SEGMENT_PRODUCT_PATH}")
    print(f"[stage127-stage78-attribution] report: {REPORT_PATH}")
    print(drawdowns.head(8).to_string(index=False))
    print(profits.head(8).to_string(index=False))
    print(full_product.head(12).to_string(index=False))
    print(full_product.tail(12).sort_values("full_net_pnl").to_string(index=False))
    print(full_direction.to_string(index=False))


if __name__ == "__main__":
    main()
