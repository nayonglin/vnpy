from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
PORTFOLIO_DIR = ROOT / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513  # noqa: E402
import analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow as s901  # noqa: E402


LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage096"
MODEL_TAG = "stage096_position_concentration_predictive_audit_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage096_position_concentration_predictive_audit"

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage096_position_concentration_predictive_audit"
STAGES_DIR = LINE_DIR / "stages"

BACKTEST_OUT = ROOT / "examples" / "portfolio_backtesting" / "backtest_outputs"
STAGE167_CURVES = BACKTEST_OUT / "qmt_roll_stage167_c9_live_15w_multiperiod_ai_audit_curves_stage167_c9_live_15w_multiperiod_ai_audit_v1.csv"

START_DATES = tuple(pd.Timestamp(f"{year}-{month:02d}-01") for year in range(2020, 2027) for month in (1, 7))
REQUESTED_END = pd.Timestamp("2026-06-30")
START_DATES = tuple(start for start in START_DATES if start <= REQUESTED_END and start.strftime("%Y-%m") <= "2026-01")
BAD_WINDOW_START = pd.Timestamp("2022-07-15")
BAD_WINDOW_END = pd.Timestamp("2023-07-05")

POSITIONS_PATH = OUT / f"{OUTPUT_PREFIX}_positions_{MODEL_TAG}.csv.gz"
PRODUCT_MARGIN_PATH = OUT / f"{OUTPUT_PREFIX}_product_margin_{MODEL_TAG}.csv.gz"
EXPOSURE_PANEL_PATH = OUT / f"{OUTPUT_PREFIX}_exposure_panel_{MODEL_TAG}.csv.gz"
FACTOR_GATE_PATH = OUT / f"{OUTPUT_PREFIX}_factor_gate_summary_{MODEL_TAG}.csv"
JOINT_GATE_PATH = OUT / f"{OUTPUT_PREFIX}_joint_gate_summary_{MODEL_TAG}.csv"
BAD_WINDOW_PATH = OUT / f"{OUTPUT_PREFIX}_bad_window_summary_{MODEL_TAG}.csv"
RUN_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_run_summary_{MODEL_TAG}.csv"
INPUT_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_input_audit_{MODEL_TAG}.csv"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

SOURCE_FILES = [
    STAGE167_CURVES,
    PORTFOLIO_DIR / "analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow.py",
    PORTFOLIO_DIR / "analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine.py",
    PORTFOLIO_DIR / "analyze_qmt_roll_stage513_stage208_exact_position_margin_audit.py",
    PORTFOLIO_DIR / "run_qmt_alignment_backtest.py",
]

EXTERNAL_RESEARCH = [
    {
        "source": "pysystemtrade backtesting docs",
        "url": "https://github.com/pst-group/pysystemtrade/blob/develop/docs/backtesting.md",
        "finding": "Trend systems should separate rules, forecast scaling, position sizing, portfolio construction and PnL evaluation.",
    },
    {
        "source": "Man Group trend-following risk disclosure",
        "url": "https://www.man.com/trend-following",
        "finding": "Concentration risk is a first-order risk in trend-following because a limited number of investments can raise volatility.",
    },
    {
        "source": "Concretum Group position sizing in trend following",
        "url": "https://concretumgroup.com/position-sizing-in-trend-following-comparing-volatility-targeting-volatility-parity-and-pyramiding/",
        "finding": "Sizing overlays can change drawdown and right-tail behavior; they need direct path-level testing rather than isolated loss inspection.",
    },
]

FACTOR_DEFINITIONS = {
    "top1_product_margin_share": "Top1 product margin share",
    "top2_product_margin_share": "Top2 product margin share",
    "product_margin_hhi": "Product margin HHI",
    "top_product_direction_margin_share": "Top product-direction margin share",
    "direction_dominance_margin_share": "Dominant long/short margin share",
    "dominant_direction_product_count": "Dominant direction active product count",
    "active_product_count": "Active product count",
    "active_contract_count": "Active contract count",
    "broker10_margin_to_equity_pct": "Broker10 margin/equity",
    "drawdown_depth_pct": "Current drawdown depth",
}


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


def _date_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return pd.Timestamp(value).date().isoformat()


def _product_from_contract(vt_symbol: Any) -> str:
    text = str(vt_symbol)
    if "." not in text:
        return text
    symbol, exchange = text.split(".", 1)
    product = "".join(ch for ch in symbol if ch.isalpha())
    return f"{product}.{exchange}"


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    values = pd.to_numeric(equity, errors="coerce").ffill()
    peak = values.cummax().replace(0.0, np.nan)
    return (values / peak - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0) * 100.0


def _run_positions() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    metadata = s513._metadata()
    position_frames: list[pd.DataFrame] = []
    product_margin_frames: list[pd.DataFrame] = []
    run_rows: list[dict[str, Any]] = []
    for idx, start in enumerate(START_DATES, start=1):
        print(f"[stage096] run {idx}/{len(START_DATES)} start={_date_text(start)}", flush=True)
        combined, frames, _spec = s901._run_live_c9(metadata, start, REQUESTED_END)
        positions = frames.get("positions", pd.DataFrame()).copy()
        if not positions.empty:
            positions["requested_start"] = _date_text(start)
            positions["requested_start_month"] = start.strftime("%Y-%m")
            positions["requested_end"] = _date_text(REQUESTED_END)
            positions["stage"] = STAGE
            positions["model_tag"] = MODEL_TAG
            positions["line_id"] = LINE_ID
            positions["source_live_version"] = s901.OFFICIAL_LIVE_VERSION
            _daily_margin, product_margin = s513._position_margin(positions, metadata)
            product_margin["requested_start"] = _date_text(start)
            product_margin["requested_start_month"] = start.strftime("%Y-%m")
            product_margin["requested_end"] = _date_text(REQUESTED_END)
            product_margin["stage"] = STAGE
            product_margin["model_tag"] = MODEL_TAG
            product_margin["line_id"] = LINE_ID
            product_margin["source_live_version"] = s901.OFFICIAL_LIVE_VERSION
            position_frames.append(positions)
            product_margin_frames.append(product_margin)
        run_rows.append(
            {
                "requested_start_month": start.strftime("%Y-%m"),
                "daily_rows": int(len(combined)),
                "position_rows": int(len(positions)),
                "active_position_rows": int(
                    pd.to_numeric(positions.get("end_pos", pd.Series(dtype=float)), errors="coerce")
                    .fillna(0.0)
                    .abs()
                    .gt(0)
                    .sum()
                )
                if not positions.empty
                else 0,
                "product_margin_rows": int(len(product_margin)) if not positions.empty else 0,
                "order_api_calls": 0,
                "ctp_connected": False,
            }
        )
    positions_all = pd.concat(position_frames, ignore_index=True, sort=False) if position_frames else pd.DataFrame()
    product_margin_all = (
        pd.concat(product_margin_frames, ignore_index=True, sort=False) if product_margin_frames else pd.DataFrame()
    )
    return positions_all, product_margin_all, pd.DataFrame(run_rows)


def _active_positions_with_margin(positions: pd.DataFrame) -> pd.DataFrame:
    if positions.empty:
        return pd.DataFrame()
    metadata = s513._metadata()
    data = positions.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    for column in ["end_pos", "close_price", "holding_pnl", "trading_pnl", "net_pnl"]:
        data[column] = pd.to_numeric(data.get(column, 0.0), errors="coerce").fillna(0.0)
    data["abs_end_pos"] = data["end_pos"].abs()
    data = data[data["abs_end_pos"].gt(0.0)].copy()
    if data.empty:
        return data
    data["size"] = data["vt_symbol"].map(metadata["sizes"]).fillna(1.0).astype(float)
    data["margin_ratio"] = data["vt_symbol"].map(metadata["margin_ratios"]).fillna(0.15).astype(float)
    data["product_vt_symbol"] = data["vt_symbol"].map(_product_from_contract)
    data["position_direction"] = np.where(data["end_pos"].gt(0), "long", "short")
    data["position_margin_exact"] = (
        data["abs_end_pos"] * data["close_price"].clip(lower=0.0) * data["size"] * data["margin_ratio"]
    )
    return data


def _concentration_metrics(active_positions: pd.DataFrame) -> pd.DataFrame:
    if active_positions.empty:
        return pd.DataFrame(
            columns=[
                "requested_start_month",
                "date",
                "total_position_margin_exact",
                "active_contract_count",
                "active_product_count",
                "top1_product_margin_share",
                "top2_product_margin_share",
                "product_margin_hhi",
                "top_product_direction_margin_share",
                "direction_dominance_margin_share",
                "dominant_direction_product_count",
            ]
        )
    rows: list[dict[str, Any]] = []
    group_keys = ["requested_start_month", "date"]
    for (start_month, date), group in active_positions.groupby(group_keys, sort=True):
        total_margin = float(group["position_margin_exact"].sum())
        product_margin = (
            group.groupby("product_vt_symbol", as_index=False)["position_margin_exact"].sum().sort_values(
                "position_margin_exact", ascending=False
            )
        )
        product_dir_margin = (
            group.groupby(["product_vt_symbol", "position_direction"], as_index=False)["position_margin_exact"]
            .sum()
            .sort_values("position_margin_exact", ascending=False)
        )
        direction_margin = (
            group.groupby("position_direction", as_index=False)
            .agg(position_margin_exact=("position_margin_exact", "sum"), active_products=("product_vt_symbol", "nunique"))
            .sort_values("position_margin_exact", ascending=False)
        )
        if total_margin > 0:
            shares = product_margin["position_margin_exact"] / total_margin
            top1 = float(shares.iloc[0]) if len(shares) else 0.0
            top2 = float(shares.head(2).sum()) if len(shares) else 0.0
            hhi = float(np.square(shares.to_numpy(dtype=float)).sum())
            top_pd = float(product_dir_margin["position_margin_exact"].iloc[0] / total_margin) if len(product_dir_margin) else 0.0
            dom_share = float(direction_margin["position_margin_exact"].iloc[0] / total_margin) if len(direction_margin) else 0.0
        else:
            top1 = top2 = hhi = top_pd = dom_share = 0.0
        rows.append(
            {
                "requested_start_month": str(start_month),
                "date": pd.Timestamp(date).normalize(),
                "total_position_margin_exact": total_margin,
                "active_contract_count": int(group["vt_symbol"].nunique()),
                "active_product_count": int(product_margin["product_vt_symbol"].nunique()),
                "top1_product_margin_share": top1,
                "top2_product_margin_share": top2,
                "product_margin_hhi": hhi,
                "top_product_direction_margin_share": top_pd,
                "direction_dominance_margin_share": dom_share,
                "dominant_direction": str(direction_margin["position_direction"].iloc[0]) if len(direction_margin) else "",
                "dominant_direction_product_count": int(direction_margin["active_products"].iloc[0]) if len(direction_margin) else 0,
                "top_product": str(product_margin["product_vt_symbol"].iloc[0]) if len(product_margin) else "",
                "top_product_direction": (
                    f"{product_dir_margin['product_vt_symbol'].iloc[0]} {product_dir_margin['position_direction'].iloc[0]}"
                    if len(product_dir_margin)
                    else ""
                ),
            }
        )
    return pd.DataFrame(rows)


def load_stage167_curves() -> pd.DataFrame:
    data = pd.read_csv(STAGE167_CURVES, encoding="utf-8-sig")
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    data = data.dropna(subset=["date"]).copy()
    data = data[data["requested_start_month"].astype(str).isin([start.strftime("%Y-%m") for start in START_DATES])].copy()
    data = data[data["date"].le(REQUESTED_END)].copy()
    data["requested_start_month"] = data["requested_start_month"].astype(str)
    for column in [
        "account_equity",
        "account_capital",
        "net_pnl",
        "broker10_margin_to_equity_pct",
        "c3_active_contracts",
        "c3_active_products",
        "total_margin_exact",
        "slippage",
        "trade_count",
    ]:
        data[column] = pd.to_numeric(data.get(column, 0.0), errors="coerce").fillna(0.0)
    return data.sort_values(["requested_start_month", "date"]).reset_index(drop=True)


def build_exposure_panel(curves: pd.DataFrame, concentration: pd.DataFrame) -> pd.DataFrame:
    panel = curves.merge(concentration, on=["requested_start_month", "date"], how="left")
    fill_zero_cols = [
        "total_position_margin_exact",
        "active_contract_count",
        "active_product_count",
        "top1_product_margin_share",
        "top2_product_margin_share",
        "product_margin_hhi",
        "top_product_direction_margin_share",
        "direction_dominance_margin_share",
        "dominant_direction_product_count",
    ]
    for column in fill_zero_cols:
        panel[column] = pd.to_numeric(panel.get(column, 0.0), errors="coerce").fillna(0.0)
    for column in ["top_product", "top_product_direction", "dominant_direction"]:
        panel[column] = panel.get(column, "").fillna("").astype(str)
    rows: list[pd.DataFrame] = []
    for _, group in panel.groupby("requested_start_month", sort=True):
        frame = group.sort_values("date").reset_index(drop=True).copy()
        equity = frame["account_equity"].astype(float)
        capital = frame["account_capital"].replace(0.0, np.nan)
        frame["drawdown_pct"] = _drawdown_pct(equity)
        frame["drawdown_depth_pct"] = -frame["drawdown_pct"].clip(upper=0.0)
        frame["daily_return_on_capital_pct"] = frame["net_pnl"] / capital * 100.0
        frame["next_date"] = frame["date"].shift(-1)
        frame["next_net_pnl"] = frame["net_pnl"].shift(-1)
        frame["next_return_on_capital_pct"] = frame["daily_return_on_capital_pct"].shift(-1)
        frame["next_loss"] = frame["next_net_pnl"] < -1e-9
        frame["next_drawdown_pct"] = frame["drawdown_pct"].shift(-1)
        frame["next_drawdown_delta_pp"] = frame["next_drawdown_pct"] - frame["drawdown_pct"]
        frame["next_drawdown_deepens"] = frame["next_drawdown_delta_pp"] < -1e-9
        frame["in_bad_window"] = frame["date"].between(BAD_WINDOW_START, BAD_WINDOW_END)
        rows.append(frame)
    return pd.concat(rows, ignore_index=True).dropna(subset=["next_date"]).reset_index(drop=True)


def _condition_stats(panel: pd.DataFrame, mask: pd.Series, condition: str, label: str) -> dict[str, Any]:
    selected = panel[mask.fillna(False)].copy()
    total_positive = float(panel.loc[panel["next_net_pnl"].gt(0), "next_net_pnl"].sum())
    total_negative_abs = float(-panel.loc[panel["next_net_pnl"].lt(0), "next_net_pnl"].sum())
    if selected.empty:
        return {
            "condition": condition,
            "label": label,
            "rows": 0,
            "row_share": 0.0,
            "start_count": 0,
            "negative_start_count": 0,
            "negative_start_rate": np.nan,
            "next_net_pnl_sum": 0.0,
            "positive_next_pnl_sum": 0.0,
            "negative_next_pnl_abs_sum": 0.0,
            "loss_capture_share": 0.0,
            "gain_sacrifice_share": 0.0,
            "loss_minus_gain_share": 0.0,
            "loss_rate": np.nan,
            "drawdown_deepen_rate": np.nan,
            "bad_window_row_ratio": np.nan,
            "candidate_for_proxy": False,
        }
    positive = float(selected.loc[selected["next_net_pnl"].gt(0), "next_net_pnl"].sum())
    negative_abs = float(-selected.loc[selected["next_net_pnl"].lt(0), "next_net_pnl"].sum())
    by_start = selected.groupby("requested_start_month")["next_net_pnl"].sum()
    start_count = int(by_start.size)
    negative_start_count = int(by_start.lt(0.0).sum())
    loss_share = negative_abs / total_negative_abs if total_negative_abs > 0 else np.nan
    gain_share = positive / total_positive if total_positive > 0 else np.nan
    negative_start_rate = negative_start_count / start_count if start_count else np.nan
    candidate = bool(
        len(selected) >= 60
        and start_count >= 8
        and float(selected["next_net_pnl"].sum()) < 0.0
        and np.isfinite(loss_share)
        and np.isfinite(gain_share)
        and loss_share > gain_share * 1.5
        and negative_start_rate >= 0.60
    )
    return {
        "condition": condition,
        "label": label,
        "rows": int(len(selected)),
        "row_share": float(len(selected) / len(panel)),
        "start_count": start_count,
        "negative_start_count": negative_start_count,
        "negative_start_rate": float(negative_start_rate),
        "next_net_pnl_sum": float(selected["next_net_pnl"].sum()),
        "positive_next_pnl_sum": positive,
        "negative_next_pnl_abs_sum": negative_abs,
        "loss_capture_share": float(loss_share),
        "gain_sacrifice_share": float(gain_share),
        "loss_minus_gain_share": float(loss_share - gain_share),
        "loss_rate": float(selected["next_loss"].mean()),
        "loss_rate_lift": float(selected["next_loss"].mean() - panel["next_loss"].mean()),
        "drawdown_deepen_rate": float(selected["next_drawdown_deepens"].mean()),
        "drawdown_deepen_rate_lift": float(selected["next_drawdown_deepens"].mean() - panel["next_drawdown_deepens"].mean()),
        "bad_window_row_ratio": float(selected["in_bad_window"].mean()),
        "candidate_for_proxy": candidate,
    }


def build_factor_gate_summary(panel: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for factor, label in FACTOR_DEFINITIONS.items():
        values = pd.to_numeric(panel[factor], errors="coerce")
        valid = panel[values.notna()].copy()
        if valid.empty:
            continue
        for tail_name, quantile in [("top10", 0.90), ("top20", 0.80)]:
            threshold = float(valid[factor].quantile(quantile))
            condition = f"{factor}_{tail_name}"
            row = _condition_stats(valid, valid[factor].ge(threshold), condition, f"{label} {tail_name}")
            row["factor"] = factor
            row["threshold"] = threshold
            row["tail"] = tail_name
            rows.append(row)
    summary = pd.DataFrame(rows)
    if summary.empty:
        return summary
    return summary.sort_values(
        ["candidate_for_proxy", "loss_minus_gain_share", "next_net_pnl_sum"],
        ascending=[False, False, True],
    ).reset_index(drop=True)


def build_joint_gate_summary(panel: pd.DataFrame) -> pd.DataFrame:
    thresholds = {
        factor: float(pd.to_numeric(panel[factor], errors="coerce").quantile(0.80))
        for factor in [
            "top1_product_margin_share",
            "top2_product_margin_share",
            "product_margin_hhi",
            "top_product_direction_margin_share",
            "direction_dominance_margin_share",
            "broker10_margin_to_equity_pct",
        ]
    }
    dd20 = panel["drawdown_depth_pct"].ge(20.0)
    dd30 = panel["drawdown_depth_pct"].ge(30.0)
    specs = [
        (
            "dd20_and_top1_product_share_top20",
            "DD>=20% and top1 product margin share top20",
            dd20 & panel["top1_product_margin_share"].ge(thresholds["top1_product_margin_share"]),
        ),
        (
            "dd30_and_top1_product_share_top20",
            "DD>=30% and top1 product margin share top20",
            dd30 & panel["top1_product_margin_share"].ge(thresholds["top1_product_margin_share"]),
        ),
        (
            "dd20_and_product_hhi_top20",
            "DD>=20% and product margin HHI top20",
            dd20 & panel["product_margin_hhi"].ge(thresholds["product_margin_hhi"]),
        ),
        (
            "dd30_and_product_hhi_top20",
            "DD>=30% and product margin HHI top20",
            dd30 & panel["product_margin_hhi"].ge(thresholds["product_margin_hhi"]),
        ),
        (
            "dd20_and_top_product_direction_share_top20",
            "DD>=20% and top product-direction share top20",
            dd20 & panel["top_product_direction_margin_share"].ge(thresholds["top_product_direction_margin_share"]),
        ),
        (
            "dd30_and_top_product_direction_share_top20",
            "DD>=30% and top product-direction share top20",
            dd30 & panel["top_product_direction_margin_share"].ge(thresholds["top_product_direction_margin_share"]),
        ),
        (
            "dd20_and_broker10_top20",
            "DD>=20% and broker10 pressure top20",
            dd20 & panel["broker10_margin_to_equity_pct"].ge(thresholds["broker10_margin_to_equity_pct"]),
        ),
        (
            "dd30_and_broker10_top20",
            "DD>=30% and broker10 pressure top20",
            dd30 & panel["broker10_margin_to_equity_pct"].ge(thresholds["broker10_margin_to_equity_pct"]),
        ),
    ]
    rows = [_condition_stats(panel, mask, condition, label) for condition, label, mask in specs]
    for row in rows:
        row["thresholds_json"] = json.dumps(thresholds, ensure_ascii=False, sort_keys=True)
    summary = pd.DataFrame(rows)
    return summary.sort_values(
        ["candidate_for_proxy", "loss_minus_gain_share", "next_net_pnl_sum"],
        ascending=[False, False, True],
    ).reset_index(drop=True)


def build_bad_window_summary(panel: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    factor_cols = list(FACTOR_DEFINITIONS)
    for start_month, group in panel.groupby("requested_start_month", sort=True):
        bad = group[group["in_bad_window"]].copy()
        outside = group[~group["in_bad_window"]].copy()
        row: dict[str, Any] = {
            "requested_start_month": start_month,
            "bad_rows": int(len(bad)),
            "outside_rows": int(len(outside)),
            "bad_next_net_pnl_sum": float(bad["next_net_pnl"].sum()),
            "outside_next_net_pnl_sum": float(outside["next_net_pnl"].sum()),
            "bad_loss_rate": float(bad["next_loss"].mean()) if not bad.empty else np.nan,
            "outside_loss_rate": float(outside["next_loss"].mean()) if not outside.empty else np.nan,
        }
        for factor in factor_cols:
            row[f"bad_{factor}_median"] = float(pd.to_numeric(bad[factor], errors="coerce").median()) if not bad.empty else np.nan
            row[f"outside_{factor}_median"] = (
                float(pd.to_numeric(outside[factor], errors="coerce").median()) if not outside.empty else np.nan
            )
        rows.append(row)
    return pd.DataFrame(rows)


def make_decision(factor_summary: pd.DataFrame, joint_summary: pd.DataFrame, run_summary: pd.DataFrame) -> dict[str, Any]:
    candidates = pd.concat(
        [
            factor_summary[factor_summary.get("candidate_for_proxy", False).astype(bool)].assign(summary_type="factor")
            if not factor_summary.empty
            else pd.DataFrame(),
            joint_summary[joint_summary.get("candidate_for_proxy", False).astype(bool)].assign(summary_type="joint")
            if not joint_summary.empty
            else pd.DataFrame(),
        ],
        ignore_index=True,
        sort=False,
    )
    if candidates.empty:
        decision = "stage096_no_concentration_gate_candidate"
        best_candidate = ""
        next_step = "不进入 concentration proxy；继续只能转更强独立收益腿数据补齐或更细的执行/持仓因果归因。"
        continue_after = "有但需换层"
        continue_reason = "单纯暴露集中度没有形成稳定可交易 gate，继续救参会过拟合。"
    else:
        best = candidates.sort_values(["loss_minus_gain_share", "negative_start_rate"], ascending=[False, False]).iloc[0]
        decision = "stage096_concentration_gate_candidate_for_proxy"
        best_candidate = str(best["condition"])
        next_step = f"只允许对 `{best_candidate}` 做一个冻结参数的 no-lookahead curve/position proxy；不得扫产品、方向、月份或小数阈值。"
        continue_after = "有"
        continue_reason = "有低自由度候选，但仍只是下一日归因统计，必须先 proxy 再谈 true engine。"
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": decision,
        "candidate_rule_count": int(len(candidates)),
        "best_candidate": best_candidate,
        "run_start_count": int(len(run_summary)),
        "position_rows": int(run_summary["position_rows"].sum()) if "position_rows" in run_summary else 0,
        "active_position_rows": int(run_summary["active_position_rows"].sum()) if "active_position_rows" in run_summary else 0,
        "promote_to_true_engine": False,
        "strategy_changed": False,
        "true_engine_run": True,
        "order_api_calls": 0,
        "ctp_connected": False,
        "next_step": next_step,
        "overfit_after": "否。只做预声明组合暴露指标的全路径下一日归因，不用产品/方向/日期黑名单，不扫连续阈值。",
        "continue_after": continue_after,
        "continue_reason": continue_reason,
    }


def write_report(
    run_summary: pd.DataFrame,
    factor_summary: pd.DataFrame,
    joint_summary: pd.DataFrame,
    bad_window_summary: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    research_rows = "\n".join(
        f"| {item['source']} | {item['url']} | {item['finding']} |" for item in EXTERNAL_RESEARCH
    )
    report = f"""# {STAGE} Position Concentration Predictive Audit

## 外部调研与判断

| source | url | finding |
| --- | --- | --- |
{research_rows}

我的判断：趋势跟随的组合集中度确实可能放大回撤，但它和趋势右尾是同源的。Stage096 只做全路径、下一日、无产品黑名单的归因审计，不把坏窗口的单品种亏损直接做成规则。

## Run Summary

{_md_table(run_summary)}

## Factor Gate Summary

{_md_table(factor_summary, 80)}

## Joint Gate Summary

{_md_table(joint_summary, 80)}

## Bad Window Summary

{_md_table(bad_window_summary, 40)}

## 决策

```json
{json.dumps(_json_safe(decision), ensure_ascii=False, indent=2)}
```

## 统计口径

- `factor_gate_summary`：用当日收盘可见暴露状态预测下一交易日 `next_net_pnl`。
- `joint_gate_summary`：只使用预声明的 `DD>=20/30%` 与 top20 分位集中度组合，不扫小数阈值。
- 本阶段复跑 Stage901/Stage167 official live C9 wrapper 只为拿 positions；不改策略、不连接 CTP、不调用订单 API。
- `candidate_for_proxy=True` 只是允许下一阶段 proxy，不是上线或 true-engine 晋级证据。

## 过拟合反思

- 运行前：否。目标是检验组合结构变量，而不是按坏窗口调品种/月份。
- 运行后：{decision['overfit_after']}

## 继续价值反思

- 运行前：有。Stage086/093/095 已排除简单 stop/retry、margin cap、risk_multiplier cap，仍需要确认真实持仓集中度是否有因果线索。
- 运行后：{decision['continue_after']}。{decision['continue_reason']}

## 输出

- positions：`{POSITIONS_PATH}`
- product_margin：`{PRODUCT_MARGIN_PATH}`
- exposure_panel：`{EXPOSURE_PANEL_PATH}`
- factor_gate_summary：`{FACTOR_GATE_PATH}`
- joint_gate_summary：`{JOINT_GATE_PATH}`
- bad_window_summary：`{BAD_WINDOW_PATH}`
- run_summary：`{RUN_SUMMARY_PATH}`
- input_audit：`{INPUT_AUDIT_PATH}`
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def write_stage_record(
    run_summary: pd.DataFrame,
    factor_summary: pd.DataFrame,
    joint_summary: pd.DataFrame,
    bad_window_summary: pd.DataFrame,
    decision: dict[str, Any],
) -> Path:
    now = datetime.now()
    stage_path = STAGES_DIR / f"{now:%Y%m%d_%H%M}_stage096_position_concentration_predictive_audit.md"
    text = f"""# Stage096 真实持仓集中度下一日归因审计

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{now:%Y-%m-%d %H:%M} CST
- 工作区/分支：`{ROOT}`
- 阶段性质：只读真实引擎复跑 + positions 暴露集中度归因
- 是否重要突破：否
- 是否触发A/B：否，本阶段不提出可合入候选

## 外部调研与判断

- 参考资料：pysystemtrade backtesting、Man Group trend-following concentration risk、Concretum position sizing。
- 我的判断：组合集中度是合理研究方向，但必须防止把趋势右尾一并砍掉。本阶段只验证“当日可见集中度状态是否稳定预示下一日亏损”，不做品种/方向/日期黑名单。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage096_position_concentration_predictive_audit.py`
- 修改脚本：无正式交易入口修改。
- 删除脚本：无。
- 新增参数：预声明集中度指标和 `DD>=20/30% + top20` 联合条件；不新增正式交易参数。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：`2020-01` 至 `2026-01` 逐半年起点，统一终点 `2026-06-30`。
- 账户规模：`150,000`
- 引擎口径：复用 Stage901/Stage167 official live C9 wrapper；额外保存 positions 并按保证金集中度归因。
- 成本口径：沿用 official wrapper；本阶段不生成新策略曲线。
- 审计口径：当日收盘可见暴露指标预测下一交易日 `next_net_pnl`；不使用未来收益构造特征。

## Run Summary

{_md_table(run_summary)}

## Factor Gate Summary

{_md_table(factor_summary, 80)}

## Joint Gate Summary

{_md_table(joint_summary, 80)}

## Bad Window Summary

{_md_table(bad_window_summary, 40)}

## 结论

- 本阶段结论：`{decision['decision']}`。
- 候选数：`{decision['candidate_rule_count']}`。
- 最优候选：`{decision['best_candidate']}`。
- 是否进入 true engine：`{decision['promote_to_true_engine']}`。
- 下一步：{decision['next_step']}

## 回测记录字段

- 期末权益/总收益/最大回撤/Sharpe/总滑点/总交易次数/胜率：本阶段不是新策略曲线，沿用 Stage167 baseline，不新增这些汇总。
- positions rows：`{decision['position_rows']}`。
- active position rows：`{decision['active_position_rows']}`。

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

    positions, product_margin, run_summary = _run_positions()
    curves = load_stage167_curves()
    active_positions = _active_positions_with_margin(positions)
    concentration = _concentration_metrics(active_positions)
    panel = build_exposure_panel(curves, concentration)
    factor_summary = build_factor_gate_summary(panel)
    joint_summary = build_joint_gate_summary(panel)
    bad_window_summary = build_bad_window_summary(panel)
    input_audit = _input_audit(SOURCE_FILES)
    decision = make_decision(factor_summary, joint_summary, run_summary)

    positions.to_csv(POSITIONS_PATH, index=False, encoding="utf-8-sig", compression="gzip")
    product_margin.to_csv(PRODUCT_MARGIN_PATH, index=False, encoding="utf-8-sig", compression="gzip")
    panel.to_csv(EXPOSURE_PANEL_PATH, index=False, encoding="utf-8-sig", compression="gzip")
    factor_summary.to_csv(FACTOR_GATE_PATH, index=False, encoding="utf-8-sig")
    joint_summary.to_csv(JOINT_GATE_PATH, index=False, encoding="utf-8-sig")
    bad_window_summary.to_csv(BAD_WINDOW_PATH, index=False, encoding="utf-8-sig")
    run_summary.to_csv(RUN_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    input_audit.to_csv(INPUT_AUDIT_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(run_summary, factor_summary, joint_summary, bad_window_summary, decision)
    stage_path = write_stage_record(run_summary, factor_summary, joint_summary, bad_window_summary, decision)
    print(json.dumps(_json_safe({"decision": decision, "stage_path": stage_path, "report_path": REPORT_PATH}), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
