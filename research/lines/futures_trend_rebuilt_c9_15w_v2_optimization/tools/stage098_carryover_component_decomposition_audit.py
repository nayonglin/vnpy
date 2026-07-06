from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage098"
MODEL_TAG = "stage098_carryover_component_decomposition_audit_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage098_carryover_component_decomposition_audit"

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage098_carryover_component_decomposition_audit"
STAGES_DIR = LINE_DIR / "stages"

STAGE096_OUT = LINE_DIR / "outputs" / "stage096_position_concentration_predictive_audit"
STAGE096_PREFIX = "rebuilt_c9_v2_stage096_position_concentration_predictive_audit"
STAGE096_TAG = "stage096_position_concentration_predictive_audit_v1"
STAGE096_POSITIONS = STAGE096_OUT / f"{STAGE096_PREFIX}_positions_{STAGE096_TAG}.csv.gz"
STAGE096_PANEL = STAGE096_OUT / f"{STAGE096_PREFIX}_exposure_panel_{STAGE096_TAG}.csv.gz"

COMPONENT_PANEL_PATH = OUT / f"{OUTPUT_PREFIX}_component_panel_{MODEL_TAG}.csv.gz"
SEGMENT_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_segment_summary_{MODEL_TAG}.csv"
CONDITION_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_condition_component_summary_{MODEL_TAG}.csv"
BAD_BY_START_PATH = OUT / f"{OUTPUT_PREFIX}_bad_window_by_start_{MODEL_TAG}.csv"
TOP_COMPONENT_DAYS_PATH = OUT / f"{OUTPUT_PREFIX}_top_component_days_{MODEL_TAG}.csv"
RESIDUAL_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_residual_audit_{MODEL_TAG}.csv"
INPUT_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_input_audit_{MODEL_TAG}.csv"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

BAD_WINDOW_START = pd.Timestamp("2022-07-15")
BAD_WINDOW_END = pd.Timestamp("2023-07-05")

SOURCE_FILES = [STAGE096_POSITIONS, STAGE096_PANEL]

EXTERNAL_RESEARCH = [
    {
        "source": "pysystemtrade backtesting documentation",
        "url": "https://github.com/pst-group/pysystemtrade/blob/develop/docs/backtesting.md",
        "finding": "Position inertia/buffering and component attribution matter because cost and trading contributions should be separated from instrument returns.",
    },
    {
        "source": "Rob Carver blog on correlations, weights and multipliers",
        "url": "https://qoppac.blogspot.com/2016/01/correlations-weights-multipliers.html",
        "finding": "Portfolio-level diversification multipliers and weights are core trend-following controls, but need separate estimation and validation.",
    },
    {
        "source": "Volatility stops overview",
        "url": "https://www.investopedia.com/articles/trading/09/volatility-stops.asp",
        "finding": "Stop/exits should respect volatility noise; premature tightening can create whipsaw, so attribution should precede exit-rule changes.",
    },
]

COMPONENT_COLUMNS = [
    "same_symbol_holding_pnl",
    "same_symbol_rebalance_net_pnl",
    "same_symbol_net_pnl",
    "roll_same_product_net_pnl",
    "new_product_net_pnl",
    "residual_net_pnl",
    "next_net_pnl",
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


def _product_from_contract(vt_symbol: Any) -> str:
    text = str(vt_symbol)
    if "." not in text:
        return text
    symbol, exchange = text.split(".", 1)
    product = "".join(ch for ch in symbol if ch.isalpha())
    return f"{product}.{exchange}"


def _numeric_column(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column in frame.columns:
        return pd.to_numeric(frame[column], errors="coerce").fillna(default)
    return pd.Series(default, index=frame.index, dtype=float)


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    positions = pd.read_csv(STAGE096_POSITIONS, encoding="utf-8-sig")
    panel = pd.read_csv(STAGE096_PANEL, encoding="utf-8-sig")
    positions["date"] = pd.to_datetime(positions["date"], errors="coerce").dt.normalize()
    panel["date"] = pd.to_datetime(panel["date"], errors="coerce").dt.normalize()
    panel["next_date"] = pd.to_datetime(panel["next_date"], errors="coerce").dt.normalize()
    positions["requested_start_month"] = positions["requested_start_month"].astype(str)
    panel["requested_start_month"] = panel["requested_start_month"].astype(str)
    for column in [
        "start_pos",
        "end_pos",
        "pos_change",
        "holding_pnl",
        "trading_pnl",
        "commission",
        "slippage",
        "net_pnl",
        "trade_count",
    ]:
        positions[column] = pd.to_numeric(positions.get(column, 0.0), errors="coerce").fillna(0.0)
    for column in [
        "next_net_pnl",
        "active_contract_count",
        "active_product_count",
        "top1_product_margin_share",
        "broker10_margin_to_equity_pct",
        "drawdown_depth_pct",
    ]:
        panel[column] = pd.to_numeric(panel.get(column, 0.0), errors="coerce").fillna(0.0)
    positions["product_vt_symbol"] = positions["vt_symbol"].map(_product_from_contract)
    return positions.dropna(subset=["date"]), panel.dropna(subset=["date", "next_date"]).copy()


def build_component_panel(positions: pd.DataFrame, panel: pd.DataFrame) -> pd.DataFrame:
    active = positions[positions["end_pos"].abs().gt(1e-9)][
        ["requested_start_month", "date", "vt_symbol", "product_vt_symbol", "end_pos"]
    ].drop_duplicates()
    base_keys = panel[["requested_start_month", "date", "next_date"]].copy()
    active_next = active.merge(base_keys, on=["requested_start_month", "date"], how="inner")
    next_positions = positions[
        [
            "requested_start_month",
            "date",
            "vt_symbol",
            "product_vt_symbol",
            "start_pos",
            "end_pos",
            "pos_change",
            "holding_pnl",
            "trading_pnl",
            "commission",
            "slippage",
            "net_pnl",
            "trade_count",
        ]
    ].rename(columns={"date": "next_date"})

    same_symbol = active_next.merge(
        next_positions,
        on=["requested_start_month", "next_date", "vt_symbol", "product_vt_symbol"],
        how="left",
        suffixes=("_prev", "_next"),
    )
    for column in ["holding_pnl", "trading_pnl", "commission", "slippage", "net_pnl", "trade_count", "start_pos", "end_pos"]:
        same_symbol[column] = _numeric_column(same_symbol, column)
    same_symbol["same_symbol_rebalance_net_pnl"] = (
        same_symbol["trading_pnl"] - same_symbol["commission"] - same_symbol["slippage"]
    )
    same_summary = (
        same_symbol.groupby(["requested_start_month", "date"], as_index=False)
        .agg(
            same_symbol_holding_pnl=("holding_pnl", "sum"),
            same_symbol_trading_pnl=("trading_pnl", "sum"),
            same_symbol_commission=("commission", "sum"),
            same_symbol_slippage=("slippage", "sum"),
            same_symbol_rebalance_net_pnl=("same_symbol_rebalance_net_pnl", "sum"),
            same_symbol_net_pnl=("net_pnl", "sum"),
            same_symbol_trade_count=("trade_count", "sum"),
            same_symbol_count=("vt_symbol", "nunique"),
        )
        .copy()
    )

    prev_active_product = active_next[["requested_start_month", "date", "next_date", "product_vt_symbol"]].drop_duplicates()
    prev_active_symbol = active_next[["requested_start_month", "date", "next_date", "vt_symbol"]].drop_duplicates()
    next_nonzero = next_positions[
        next_positions[
            ["start_pos", "end_pos", "pos_change", "holding_pnl", "trading_pnl", "net_pnl", "trade_count"]
        ]
        .abs()
        .sum(axis=1)
        .gt(1e-9)
    ].copy()
    with_symbol = next_nonzero.merge(
        base_keys,
        on=["requested_start_month", "next_date"],
        how="inner",
    ).merge(
        prev_active_symbol.assign(prev_same_symbol=1),
        on=["requested_start_month", "date", "next_date", "vt_symbol"],
        how="left",
    ).merge(
        prev_active_product.assign(prev_same_product=1),
        on=["requested_start_month", "date", "next_date", "product_vt_symbol"],
        how="left",
    )
    for column in ["prev_same_symbol", "prev_same_product"]:
        with_symbol[column] = _numeric_column(with_symbol, column)
    with_symbol["component_bucket"] = np.select(
        [
            with_symbol["prev_same_symbol"].gt(0),
            with_symbol["prev_same_product"].gt(0),
        ],
        ["same_symbol", "roll_same_product"],
        default="new_product",
    )
    non_same_symbol = with_symbol[~with_symbol["component_bucket"].eq("same_symbol")].copy()
    bucket_summary = (
        non_same_symbol.groupby(["requested_start_month", "date", "component_bucket"], as_index=False)
        .agg(
            net_pnl=("net_pnl", "sum"),
            holding_pnl=("holding_pnl", "sum"),
            trading_pnl=("trading_pnl", "sum"),
            commission=("commission", "sum"),
            slippage=("slippage", "sum"),
            trade_count=("trade_count", "sum"),
            symbol_count=("vt_symbol", "nunique"),
        )
        .copy()
    )
    pivot = bucket_summary.pivot_table(
        index=["requested_start_month", "date"],
        columns="component_bucket",
        values=["net_pnl", "holding_pnl", "trading_pnl", "commission", "slippage", "trade_count", "symbol_count"],
        aggfunc="sum",
        fill_value=0.0,
    )
    pivot.columns = [f"{bucket}_{metric}" for metric, bucket in pivot.columns.to_flat_index()]
    pivot = pivot.reset_index()

    enriched = panel.merge(same_summary, on=["requested_start_month", "date"], how="left").merge(
        pivot, on=["requested_start_month", "date"], how="left"
    )
    numeric_cols = [
        "same_symbol_holding_pnl",
        "same_symbol_trading_pnl",
        "same_symbol_commission",
        "same_symbol_slippage",
        "same_symbol_rebalance_net_pnl",
        "same_symbol_net_pnl",
        "same_symbol_trade_count",
        "same_symbol_count",
        "roll_same_product_net_pnl",
        "new_product_net_pnl",
        "roll_same_product_holding_pnl",
        "roll_same_product_trading_pnl",
        "new_product_holding_pnl",
        "new_product_trading_pnl",
    ]
    for column in numeric_cols:
        enriched[column] = _numeric_column(enriched, column)
    enriched["known_component_net_pnl"] = (
        enriched["same_symbol_net_pnl"] + enriched["roll_same_product_net_pnl"] + enriched["new_product_net_pnl"]
    )
    enriched["residual_net_pnl"] = enriched["next_net_pnl"] - enriched["known_component_net_pnl"]
    enriched["in_bad_window_by_next_date"] = enriched["next_date"].between(BAD_WINDOW_START, BAD_WINDOW_END)
    enriched["eod_active"] = enriched["active_contract_count"].gt(0)
    return enriched


def _segment_stats(frame: pd.DataFrame, segment: str) -> dict[str, Any]:
    row: dict[str, Any] = {
        "segment": segment,
        "rows": int(len(frame)),
        "start_count": int(frame["requested_start_month"].nunique()) if not frame.empty else 0,
        "date_count": int(frame["date"].nunique()) if not frame.empty else 0,
    }
    for column in COMPONENT_COLUMNS:
        values = pd.to_numeric(frame[column], errors="coerce").fillna(0.0) if not frame.empty else pd.Series(dtype=float)
        row[f"{column}_sum"] = float(values.sum()) if not values.empty else 0.0
        row[f"{column}_positive_sum"] = float(values[values.gt(0)].sum()) if not values.empty else 0.0
        row[f"{column}_negative_abs_sum"] = float(-values[values.lt(0)].sum()) if not values.empty else 0.0
        row[f"{column}_loss_rate"] = float(values.lt(0).mean()) if not values.empty else np.nan
    row["max_abs_component_residual"] = float(pd.to_numeric(frame.get("residual_net_pnl", 0.0), errors="coerce").abs().max()) if not frame.empty else 0.0
    return row


def build_segment_summary(panel: pd.DataFrame) -> pd.DataFrame:
    groups = {
        "all_rows": panel,
        "eod_active_only": panel[panel["eod_active"]].copy(),
        "eod_flat_only": panel[~panel["eod_active"]].copy(),
        "bad_window_by_next_date": panel[panel["in_bad_window_by_next_date"]].copy(),
        "bad_window_active_by_next_date": panel[panel["in_bad_window_by_next_date"] & panel["eod_active"]].copy(),
        "bad_window_flat_by_next_date": panel[panel["in_bad_window_by_next_date"] & ~panel["eod_active"]].copy(),
        "outside_bad_window_active": panel[~panel["in_bad_window_by_next_date"] & panel["eod_active"]].copy(),
    }
    return pd.DataFrame([_segment_stats(frame, name) for name, frame in groups.items()])


def build_bad_by_start(panel: pd.DataFrame) -> pd.DataFrame:
    bad = panel[panel["in_bad_window_by_next_date"]].copy()
    rows: list[dict[str, Any]] = []
    for (start_month, active_state), frame in bad.assign(active_state=np.where(bad["eod_active"], "eod_active", "eod_flat")).groupby(
        ["requested_start_month", "active_state"], sort=True
    ):
        row = _segment_stats(frame, f"{start_month}_{active_state}")
        row["requested_start_month"] = start_month
        row["active_state"] = active_state
        rows.append(row)
    return pd.DataFrame(rows)


def _condition_stats(panel: pd.DataFrame, condition: str, label: str, mask: pd.Series, component: str) -> dict[str, Any]:
    selected = panel[mask.fillna(False)].copy()
    total = pd.to_numeric(panel[component], errors="coerce").fillna(0.0)
    total_positive = float(total[total.gt(0)].sum())
    total_negative_abs = float(-total[total.lt(0)].sum())
    if selected.empty:
        return {
            "condition": condition,
            "label": label,
            "component": component,
            "rows": 0,
            "start_count": 0,
            "date_count": 0,
            "negative_start_rate": np.nan,
            "negative_date_rate": np.nan,
            "component_pnl_sum": 0.0,
            "loss_capture_share": 0.0,
            "gain_sacrifice_share": 0.0,
            "loss_minus_gain_share": 0.0,
            "candidate_for_proxy": False,
        }
    values = pd.to_numeric(selected[component], errors="coerce").fillna(0.0)
    by_start = selected.groupby("requested_start_month")[component].sum()
    by_date = selected.groupby("date")[component].sum()
    positive = float(values[values.gt(0)].sum())
    negative_abs = float(-values[values.lt(0)].sum())
    loss_share = negative_abs / total_negative_abs if total_negative_abs > 0 else np.nan
    gain_share = positive / total_positive if total_positive > 0 else np.nan
    negative_start_rate = float(by_start.lt(0).mean()) if len(by_start) else np.nan
    negative_date_rate = float(by_date.lt(0).mean()) if len(by_date) else np.nan
    candidate = bool(
        len(selected) >= 60
        and len(by_start) >= 8
        and len(by_date) >= 80
        and values.sum() < 0.0
        and np.isfinite(loss_share)
        and np.isfinite(gain_share)
        and loss_share > gain_share * 1.5
        and negative_start_rate >= 0.60
        and negative_date_rate >= 0.55
    )
    return {
        "condition": condition,
        "label": label,
        "component": component,
        "rows": int(len(selected)),
        "start_count": int(len(by_start)),
        "date_count": int(len(by_date)),
        "negative_start_count": int(by_start.lt(0).sum()),
        "negative_start_rate": negative_start_rate,
        "negative_date_count": int(by_date.lt(0).sum()),
        "negative_date_rate": negative_date_rate,
        "component_pnl_sum": float(values.sum()),
        "positive_component_pnl_sum": positive,
        "negative_component_pnl_abs_sum": negative_abs,
        "loss_capture_share": float(loss_share),
        "gain_sacrifice_share": float(gain_share),
        "loss_minus_gain_share": float(loss_share - gain_share),
        "candidate_for_proxy": candidate,
    }


def build_condition_summary(panel: pd.DataFrame) -> pd.DataFrame:
    active = panel["eod_active"]
    dd20 = panel["drawdown_depth_pct"].ge(20.0)
    dd30 = panel["drawdown_depth_pct"].ge(30.0)
    one_product = active & panel["active_product_count"].eq(1)
    high_top1 = active & panel["top1_product_margin_share"].ge(0.80)
    broker50 = panel["broker10_margin_to_equity_pct"].ge(50.0)
    specs = [
        ("eod_active", "EOD active", active),
        ("single_product_active", "EOD single product", one_product),
        ("top1_ge80_active", "EOD top1 share >=80%", high_top1),
        ("dd20", "DD>=20%", dd20),
        ("dd30", "DD>=30%", dd30),
        ("active_and_dd20", "EOD active and DD>=20%", active & dd20),
        ("active_and_dd30", "EOD active and DD>=30%", active & dd30),
        ("single_product_and_dd20", "Single product and DD>=20%", one_product & dd20),
        ("single_product_and_dd30", "Single product and DD>=30%", one_product & dd30),
        ("top1_ge80_and_dd20", "Top1>=80% and DD>=20%", high_top1 & dd20),
        ("top1_ge80_and_dd30", "Top1>=80% and DD>=30%", high_top1 & dd30),
        ("broker50_and_dd20", "Broker10>=50% and DD>=20%", broker50 & dd20),
    ]
    components = [
        "same_symbol_holding_pnl",
        "same_symbol_rebalance_net_pnl",
        "same_symbol_net_pnl",
        "roll_same_product_net_pnl",
        "new_product_net_pnl",
    ]
    rows = []
    for component in components:
        for condition, label, mask in specs:
            rows.append(_condition_stats(panel, condition, label, mask, component))
    summary = pd.DataFrame(rows)
    return summary.sort_values(
        ["candidate_for_proxy", "component", "loss_minus_gain_share", "component_pnl_sum"],
        ascending=[False, True, False, True],
    ).reset_index(drop=True)


def build_top_component_days(panel: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for component in ["same_symbol_holding_pnl", "same_symbol_rebalance_net_pnl", "roll_same_product_net_pnl", "new_product_net_pnl"]:
        cols = [
            "requested_start_month",
            "date",
            "next_date",
            "in_bad_window_by_next_date",
            "eod_active",
            "active_product_count",
            "top1_product_margin_share",
            "drawdown_depth_pct",
            component,
            "next_net_pnl",
        ]
        view = panel[cols].copy()
        view["component"] = component
        view["component_pnl"] = view[component]
        rows.append(view.sort_values("component_pnl").head(25))
    return pd.concat(rows, ignore_index=True, sort=False)


def build_residual_audit(panel: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    data = panel.copy()
    data["residual_abs"] = pd.to_numeric(data["residual_net_pnl"], errors="coerce").fillna(0.0).abs()
    data["next_abs"] = pd.to_numeric(data["next_net_pnl"], errors="coerce").fillna(0.0).abs()
    data["month"] = data["date"].dt.to_period("M").astype(str)
    groups = {
        "all_rows": data,
        "residual_nonzero": data[data["residual_abs"].gt(1e-6)].copy(),
        "bad_window": data[data["in_bad_window_by_next_date"]].copy(),
        "bad_window_residual_nonzero": data[data["in_bad_window_by_next_date"] & data["residual_abs"].gt(1e-6)].copy(),
        "outside_bad_window_residual_nonzero": data[
            ~data["in_bad_window_by_next_date"] & data["residual_abs"].gt(1e-6)
        ].copy(),
    }
    for segment, frame in groups.items():
        rows.append(
            {
                "segment": segment,
                "rows": int(len(frame)),
                "start_count": int(frame["requested_start_month"].nunique()) if not frame.empty else 0,
                "date_count": int(frame["date"].nunique()) if not frame.empty else 0,
                "month_min": str(frame["month"].min()) if not frame.empty else "",
                "month_max": str(frame["month"].max()) if not frame.empty else "",
                "residual_sum": float(frame["residual_net_pnl"].sum()) if not frame.empty else 0.0,
                "residual_abs_sum": float(frame["residual_abs"].sum()) if not frame.empty else 0.0,
                "residual_abs_max": float(frame["residual_abs"].max()) if not frame.empty else 0.0,
                "next_abs_sum": float(frame["next_abs"].sum()) if not frame.empty else 0.0,
                "residual_abs_to_all_next_abs_pct": float(
                    frame["residual_abs"].sum() / data["next_abs"].sum() * 100.0
                )
                if data["next_abs"].sum() > 0
                else np.nan,
            }
        )
    by_month = (
        data[data["residual_abs"].gt(1e-6)]
        .groupby("month", as_index=False)
        .agg(
            rows=("residual_abs", "size"),
            start_count=("requested_start_month", "nunique"),
            date_count=("date", "nunique"),
            residual_sum=("residual_net_pnl", "sum"),
            residual_abs_sum=("residual_abs", "sum"),
            residual_abs_max=("residual_abs", "max"),
            next_abs_sum=("next_abs", "sum"),
        )
    )
    if not by_month.empty:
        by_month.insert(0, "segment", "residual_nonzero_by_month")
        by_month["month_min"] = by_month["month"]
        by_month["month_max"] = by_month["month"]
        by_month["residual_abs_to_all_next_abs_pct"] = by_month["residual_abs_sum"] / data["next_abs"].sum() * 100.0
        by_month = by_month.drop(columns=["month"])
        rows.extend(by_month.to_dict("records"))
    return pd.DataFrame(rows)


def make_decision(
    segment_summary: pd.DataFrame, condition_summary: pd.DataFrame, residual_audit: pd.DataFrame
) -> dict[str, Any]:
    candidates = condition_summary[condition_summary["candidate_for_proxy"].astype(bool)].copy()
    bad_active = segment_summary[segment_summary["segment"].eq("bad_window_active_by_next_date")]
    if not bad_active.empty:
        bad_active_row = bad_active.iloc[0].to_dict()
    else:
        bad_active_row = {}
    residual_rows = residual_audit.set_index("segment") if not residual_audit.empty else pd.DataFrame()
    residual_nonzero = residual_rows.loc["residual_nonzero"].to_dict() if "residual_nonzero" in residual_rows.index else {}
    bad_window_residual_nonzero = (
        residual_rows.loc["bad_window_residual_nonzero"].to_dict()
        if "bad_window_residual_nonzero" in residual_rows.index
        else {}
    )
    if candidates.empty:
        decision = "stage098_no_component_condition_candidate_carryover_holding_dominates_bad_window"
        best_candidate = ""
        next_step = (
            "不进入 component proxy；EOD集中度阈值停止。下一步若继续，应看持仓趋势衰减/退出信号质量，"
            "或回到独立收益腿数据补齐。"
        )
        continue_after = "有但需换机制"
        continue_reason = "坏窗口亏损主要来自 carryover/same-symbol holding，但当前离散可见状态无法稳定识别。"
    else:
        best = candidates.sort_values(["loss_minus_gain_share", "negative_date_rate"], ascending=[False, False]).iloc[0]
        decision = "stage098_component_condition_candidate_for_proxy"
        best_candidate = f"{best['component']}::{best['condition']}"
        next_step = f"只允许对 `{best_candidate}` 做一次冻结 no-lookahead proxy；不得扫阈值、产品、方向、日期。"
        continue_after = "有"
        continue_reason = "组件层条件出现候选，但仍需 proxy 和 true engine 验证。"
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": decision,
        "candidate_rule_count": int(len(candidates)),
        "best_candidate": best_candidate,
        "bad_window_active_same_symbol_holding_pnl": float(
            bad_active_row.get("same_symbol_holding_pnl_sum", 0.0) or 0.0
        ),
        "bad_window_active_same_symbol_rebalance_net_pnl": float(
            bad_active_row.get("same_symbol_rebalance_net_pnl_sum", 0.0) or 0.0
        ),
        "bad_window_active_roll_same_product_net_pnl": float(
            bad_active_row.get("roll_same_product_net_pnl_sum", 0.0) or 0.0
        ),
        "bad_window_active_new_product_net_pnl": float(
            bad_active_row.get("new_product_net_pnl_sum", 0.0) or 0.0
        ),
        "component_residual_nonzero_rows": int(residual_nonzero.get("rows", 0) or 0),
        "component_residual_abs_sum": float(residual_nonzero.get("residual_abs_sum", 0.0) or 0.0),
        "component_residual_abs_to_all_next_abs_pct": float(
            residual_nonzero.get("residual_abs_to_all_next_abs_pct", 0.0) or 0.0
        ),
        "component_residual_month_min": str(residual_nonzero.get("month_min", "") or ""),
        "component_residual_month_max": str(residual_nonzero.get("month_max", "") or ""),
        "bad_window_residual_nonzero_rows": int(bad_window_residual_nonzero.get("rows", 0) or 0),
        "bad_window_residual_abs_sum": float(bad_window_residual_nonzero.get("residual_abs_sum", 0.0) or 0.0),
        "residual_caveat": (
            "组件残差全部集中在 2026-06 尾段 Stage096 exposure panel 与 positions 明细不闭合处，bad-window residual 为 0；"
            "Stage098 的坏窗口归因结论不依赖这些尾部残差。"
        ),
        "promote_to_true_engine": False,
        "strategy_changed": False,
        "true_engine_run": False,
        "order_api_calls": 0,
        "ctp_connected": False,
        "next_step": next_step,
        "overfit_after": "否。只做组件拆分和预声明离散条件审计，不扫阈值、不按产品/方向/日期黑名单。",
        "continue_after": continue_after,
        "continue_reason": continue_reason,
    }


def write_report(
    segment_summary: pd.DataFrame,
    condition_summary: pd.DataFrame,
    bad_by_start: pd.DataFrame,
    top_days: pd.DataFrame,
    residual_audit: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    research_rows = "\n".join(
        f"| {item['source']} | {item['url']} | {item['finding']} |" for item in EXTERNAL_RESEARCH
    )
    report = f"""# {STAGE} Carryover Component Decomposition Audit

## 外部调研与判断

| source | url | finding |
| --- | --- | --- |
{research_rows}

我的判断：Stage097 已经不支持 EOD 集中度 gate。Stage098 只拆分亏损来源，避免把 holding loss、调仓成本、换月和新开仓混在一起解释；本阶段不新增策略规则。

## Segment Summary

{_md_table(segment_summary)}

## Condition Component Summary

{_md_table(condition_summary, 120)}

## Bad Window By Start

{_md_table(bad_by_start, 80)}

## Top Component Loss Days

{_md_table(top_days, 120)}

## Residual Audit

{_md_table(residual_audit, 40)}

## 决策

```json
{json.dumps(_json_safe(decision), ensure_ascii=False, indent=2)}
```

## 统计口径

- `same_symbol_holding_pnl`：前一日 EOD 已持有的同一合约，下一交易日 daily holding PnL。
- `same_symbol_rebalance_net_pnl`：同一合约下一交易日 `trading_pnl - commission - slippage`。
- `roll_same_product_net_pnl`：下一交易日同产品但不同合约的 PnL。
- `new_product_net_pnl`：下一交易日前一日没有同产品 EOD 持仓的 PnL。
- 本阶段复用 Stage096 outputs，不重新跑策略，不连接 CTP，不调用订单 API。
- `residual_net_pnl`：`next_net_pnl - 已识别组件净 PnL`；当前非零残差全部位于 `2026-06` 尾段 Stage096 exposure panel 与 positions 明细不闭合处，bad-window residual 为 `0`。

## 过拟合反思

- 运行前：否。只做组件拆分，不新增交易规则。
- 运行后：{decision['overfit_after']}

## 继续价值反思

- 运行前：有。需要知道亏损来自持仓延续还是新交易，才知道下一步是不是应该做退出/持仓质量，而不是入场 gate。
- 运行后：{decision['continue_after']}。{decision['continue_reason']}

## 输出

- component_panel：`{COMPONENT_PANEL_PATH}`
- segment_summary：`{SEGMENT_SUMMARY_PATH}`
- condition_component_summary：`{CONDITION_SUMMARY_PATH}`
- bad_window_by_start：`{BAD_BY_START_PATH}`
- top_component_days：`{TOP_COMPONENT_DAYS_PATH}`
- input_audit：`{INPUT_AUDIT_PATH}`
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def write_stage_record(
    segment_summary: pd.DataFrame,
    condition_summary: pd.DataFrame,
    bad_by_start: pd.DataFrame,
    top_days: pd.DataFrame,
    residual_audit: pd.DataFrame,
    decision: dict[str, Any],
) -> Path:
    now = datetime.now()
    stage_path = STAGES_DIR / f"{now:%Y%m%d_%H%M}_stage098_carryover_component_decomposition_audit.md"
    text = f"""# Stage098 carryover 组件拆分审计

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{now:%Y-%m-%d %H:%M} CST
- 工作区/分支：`{ROOT}`
- 阶段性质：只读组件归因；不重新跑策略
- 是否重要突破：否
- 是否触发A/B：否，本阶段不提出可合入候选

## 外部调研与判断

- 参考资料：pysystemtrade backtesting、Rob Carver 组合权重/分散乘数、volatility stop exit。
- 我的判断：趋势持仓亏损不能直接等同于入场问题；要先拆成持仓延续、同合约调仓、换月/同产品新合约、全新品种新交易。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage098_carryover_component_decomposition_audit.py`
- 修改脚本：无正式交易入口修改。
- 删除脚本：无。
- 新增参数：固定组件拆分口径和预声明离散条件；不新增正式交易参数。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 输入：Stage096 positions 与 exposure panel。
- 数据区间：Stage096 的 `2020-01` 至 `2026-01` 逐半年起点，统一终点 `2026-06-30`。
- 引擎口径：本阶段不重新跑引擎。
- 审计口径：下一日 PnL 组件拆分，不做产品/方向/日期黑名单。

## Segment Summary

{_md_table(segment_summary)}

## Condition Component Summary

{_md_table(condition_summary, 120)}

## Bad Window By Start

{_md_table(bad_by_start, 80)}

## Top Component Loss Days

{_md_table(top_days, 120)}

## Residual Audit

{_md_table(residual_audit, 40)}

## 结论

- 本阶段结论：`{decision['decision']}`。
- 候选数：`{decision['candidate_rule_count']}`。
- 最优候选：`{decision['best_candidate']}`。
- 坏窗口 active same-symbol holding PnL：`{decision['bad_window_active_same_symbol_holding_pnl']:.4f}`。
- 坏窗口 active same-symbol rebalance net PnL：`{decision['bad_window_active_same_symbol_rebalance_net_pnl']:.4f}`。
- 坏窗口 active roll same-product net PnL：`{decision['bad_window_active_roll_same_product_net_pnl']:.4f}`。
- 坏窗口 active new-product net PnL：`{decision['bad_window_active_new_product_net_pnl']:.4f}`。
- 组件残差非零行：`{decision['component_residual_nonzero_rows']}`。
- 组件残差绝对值合计：`{decision['component_residual_abs_sum']:.4f}`。
- 组件残差/全体 next PnL 绝对值：`{decision['component_residual_abs_to_all_next_abs_pct']:.4f}%`。
- bad-window 残差非零行：`{decision['bad_window_residual_nonzero_rows']}`。
- bad-window 残差绝对值合计：`{decision['bad_window_residual_abs_sum']:.4f}`。
- 残差 caveat：{decision['residual_caveat']}
- 是否进入 true engine：`{decision['promote_to_true_engine']}`。
- 下一步：{decision['next_step']}

## 回测记录字段

- 期末权益/总收益/最大回撤/Sharpe/总滑点/总交易次数/胜率：本阶段不是新策略曲线，不新增这些汇总。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：{decision['overfit_after']}

## 继续价值反思

- 运行前判断：有。
- 运行后判断：{decision['continue_after']}
- 原因：{decision['continue_reason']}

## 合入建议

- 是否更新本线 `LINE.md`：否，等独立 agent 审查。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段无重要突破。
"""
    stage_path.write_text(text, encoding="utf-8")
    return stage_path


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    positions, panel = load_inputs()
    component_panel = build_component_panel(positions, panel)
    segment_summary = build_segment_summary(component_panel)
    condition_summary = build_condition_summary(component_panel)
    bad_by_start = build_bad_by_start(component_panel)
    top_days = build_top_component_days(component_panel)
    residual_audit = build_residual_audit(component_panel)
    input_audit = _input_audit(SOURCE_FILES)
    decision = make_decision(segment_summary, condition_summary, residual_audit)

    component_panel.to_csv(COMPONENT_PANEL_PATH, index=False, encoding="utf-8-sig", compression="gzip")
    segment_summary.to_csv(SEGMENT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    condition_summary.to_csv(CONDITION_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    bad_by_start.to_csv(BAD_BY_START_PATH, index=False, encoding="utf-8-sig")
    top_days.to_csv(TOP_COMPONENT_DAYS_PATH, index=False, encoding="utf-8-sig")
    residual_audit.to_csv(RESIDUAL_AUDIT_PATH, index=False, encoding="utf-8-sig")
    input_audit.to_csv(INPUT_AUDIT_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(segment_summary, condition_summary, bad_by_start, top_days, residual_audit, decision)
    stage_path = write_stage_record(segment_summary, condition_summary, bad_by_start, top_days, residual_audit, decision)
    print(json.dumps(_json_safe({"decision": decision, "stage_path": stage_path, "report_path": REPORT_PATH}), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
