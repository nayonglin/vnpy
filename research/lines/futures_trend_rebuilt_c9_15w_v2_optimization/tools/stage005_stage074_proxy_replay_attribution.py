from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
UPSTREAM_LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage005"
MODEL_TAG = "stage005_stage074_proxy_replay_attribution_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage005_stage074_proxy_replay_attribution"

TARGET_VARIANT = "full_market_ai_top8_and_active_positions_lt3"
TOP_N_WINDOWS = 1000
RAMP_FLOOR = 0.35
RAMP_TRADING_DAYS = 252

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
UPSTREAM_LINE_DIR = PROJECT_DIR / "research" / "lines" / UPSTREAM_LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage005_stage074_proxy_replay_attribution"

STAGE004_OUTPUT_DIR = LINE_DIR / "outputs" / "stage004_oracle_residual_path_attribution"
STAGE004_PREFIX = "rebuilt_c9_v2_stage004_oracle_residual_path_attribution"
STAGE004_TAG = "stage004_oracle_residual_path_attribution_v1"
STAGE004_WINDOW_ATTRIBUTION_PATH = (
    STAGE004_OUTPUT_DIR / f"{STAGE004_PREFIX}_window_attribution_{STAGE004_TAG}.csv"
)

STAGE013_CURVES_PATH = (
    UPSTREAM_LINE_DIR
    / "outputs"
    / "stage013_account_state_pilot_gate_engine"
    / "rebuilt_c9_stage013_account_state_pilot_gate_engine_curves_stage013_account_state_pilot_gate_engine_v1.csv"
)
STAGE070_LOT_DELTAS_PATH = (
    UPSTREAM_LINE_DIR
    / "outputs"
    / "stage070_super_quality_sibling_panel"
    / "rebuilt_c9_stage070_super_quality_sibling_panel_lot_deltas_stage070_super_quality_sibling_panel_v1.csv"
)
STAGE074_PANEL_PATH = (
    UPSTREAM_LINE_DIR
    / "outputs"
    / "stage074_cold_start_capital_ramp_proxy"
    / "rebuilt_c9_stage074_cold_start_capital_ramp_proxy_panel_curves_stage074_cold_start_capital_ramp_proxy_v1.csv.gz"
)

DAILY_COMPONENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_components_{MODEL_TAG}.csv.gz"
WINDOW_ATTRIBUTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_attribution_{MODEL_TAG}.csv"
LOT_ATTRIBUTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_lot_attribution_{MODEL_TAG}.csv.gz"
PRODUCT_DIRECTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_direction_summary_{MODEL_TAG}.csv"
MONTH_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_month_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_loss_component_chart_{MODEL_TAG}.png"


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
        number = float(value)
        return None if not np.isfinite(number) else number
    if isinstance(value, (pd.Timestamp, datetime)):
        return None if pd.isna(value) else value.isoformat()
    if pd.isna(value):
        return None
    return value


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


def _numeric(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").fillna(default)


def _date_text(value: Any) -> str:
    return pd.Timestamp(value).date().isoformat()


def compute_age_ramp_multiplier(
    length: int,
    *,
    floor: float = RAMP_FLOOR,
    ramp_trading_days: int = RAMP_TRADING_DAYS,
) -> np.ndarray:
    if length <= 0:
        return np.array([], dtype=float)
    days = max(1, int(ramp_trading_days))
    floor_value = max(0.0, min(1.0, float(floor)))
    age_for_pnl = np.maximum(np.arange(length, dtype=float) - 1.0, 0.0)
    if days <= 1:
        values = np.ones(length, dtype=float)
        values[0] = floor_value
        return values
    ramp = floor_value + (1.0 - floor_value) * np.minimum(age_for_pnl, days - 1.0) / (days - 1.0)
    return np.clip(ramp, floor_value, 1.0)


def build_stage070_daily_components(
    base_curves: pd.DataFrame,
    lot_deltas: pd.DataFrame,
    *,
    target_variant: str = TARGET_VARIANT,
) -> pd.DataFrame:
    base = base_curves.copy()
    base["requested_start_month"] = base["requested_start_month"].astype(str)
    base["date"] = pd.to_datetime(base["date"], errors="coerce").dt.normalize()
    base = base.dropna(subset=["requested_start_month", "date"]).sort_values(["requested_start_month", "date"])
    base_keep = pd.DataFrame(
        {
            "requested_start_month": base["requested_start_month"],
            "date": base["date"],
            "base_account_equity": _numeric(base, "account_equity"),
            "base_net_pnl": _numeric(base, "net_pnl"),
            "base_holding_pnl": _numeric(base, "holding_pnl"),
            "base_trading_pnl": _numeric(base, "trading_pnl"),
            "base_commission": _numeric(base, "commission"),
            "base_slippage": _numeric(base, "slippage"),
            "base_trade_count": _numeric(base, "trade_count"),
            "broker10_margin_to_equity_pct": _numeric(base, "broker10_margin_to_equity_pct"),
            "c3_active_products": _numeric(base, "c3_active_products"),
            "drawdown_pct": _numeric(base, "drawdown_pct"),
        }
    )

    lots = lot_deltas.copy()
    if lots.empty:
        daily_delta = pd.DataFrame(columns=["requested_start_month", "date", "proxy_delta_pnl"])
    else:
        lots = lots[lots["candidate_variant"].astype(str).eq(target_variant)].copy()
        lots["requested_start_month"] = lots["requested_start_month"].astype(str)
        lots["exit_date"] = pd.to_datetime(lots["exit_date"], errors="coerce").dt.normalize()
        lots["stage070_proxy_delta_pnl"] = _numeric(lots, "stage070_proxy_delta_pnl")
        daily_delta = (
            lots.dropna(subset=["requested_start_month", "exit_date"])
            .groupby(["requested_start_month", "exit_date"], as_index=False)["stage070_proxy_delta_pnl"]
            .sum()
            .rename(columns={"exit_date": "date", "stage070_proxy_delta_pnl": "proxy_delta_pnl"})
        )
    merged = base_keep.merge(daily_delta, on=["requested_start_month", "date"], how="left")
    merged["proxy_delta_pnl"] = _numeric(merged, "proxy_delta_pnl")
    merged["stage070_daily_delta"] = merged["base_net_pnl"] + merged["proxy_delta_pnl"]

    frames: list[pd.DataFrame] = []
    for _, group in merged.groupby("requested_start_month", sort=True):
        g = group.sort_values("date").copy()
        g["stage070_proxy_cum_delta"] = g["proxy_delta_pnl"].cumsum()
        g["stage070_equity"] = g["base_account_equity"] + g["stage070_proxy_cum_delta"]
        frames.append(g)
    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()


def _source_window_components(
    components: pd.DataFrame,
    source_start_month: str,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> tuple[pd.DataFrame, pd.DataFrame, np.ndarray]:
    source = components[components["requested_start_month"].astype(str).eq(str(source_start_month))].copy()
    source["date"] = pd.to_datetime(source["date"], errors="coerce").dt.normalize()
    segment = source[source["date"].ge(start_date) & source["date"].le(end_date)].sort_values("date").copy()
    multiplier = compute_age_ramp_multiplier(len(segment))
    if len(segment):
        segment["stage074_ramp_multiplier_from_window_start"] = multiplier
    window = segment[segment["date"].gt(start_date)].copy()
    return source, window, multiplier


def attribute_stage074_window(
    components: pd.DataFrame,
    window: pd.Series,
    selected_rank: int,
    *,
    ramp_floor: float = RAMP_FLOOR,
    ramp_trading_days: int = RAMP_TRADING_DAYS,
) -> dict[str, Any]:
    source_start_month = str(window["source_start_month"])
    start_date = pd.Timestamp(window["start_date"]).normalize()
    end_date = pd.Timestamp(window["end_date"]).normalize()
    source = components[components["requested_start_month"].astype(str).eq(source_start_month)].copy()
    source["date"] = pd.to_datetime(source["date"], errors="coerce").dt.normalize()
    segment = source[source["date"].ge(start_date) & source["date"].le(end_date)].sort_values("date").copy()
    multiplier = compute_age_ramp_multiplier(
        len(segment),
        floor=ramp_floor,
        ramp_trading_days=ramp_trading_days,
    )
    if len(segment):
        segment["ramp_multiplier"] = multiplier
    window_part = segment[segment["date"].gt(start_date)].copy()
    for column in [
        "stage070_daily_delta",
        "base_net_pnl",
        "base_holding_pnl",
        "base_trading_pnl",
        "base_commission",
        "base_slippage",
        "proxy_delta_pnl",
    ]:
        window_part[column] = _numeric(window_part, column)
    if "ramp_multiplier" not in window_part.columns:
        window_part["ramp_multiplier"] = pd.Series(dtype=float)
    scaled = window_part["ramp_multiplier"]
    adjusted_net = float((window_part["stage070_daily_delta"] * scaled).sum())
    base_net = float((window_part["base_net_pnl"] * scaled).sum())
    holding = float((window_part["base_holding_pnl"] * scaled).sum())
    trading = float((window_part["base_trading_pnl"] * scaled).sum())
    commission = float((window_part["base_commission"] * scaled).sum())
    slippage = float((window_part["base_slippage"] * scaled).sum())
    proxy_delta = float((window_part["proxy_delta_pnl"] * scaled).sum())
    loss_denominator = abs(adjusted_net) if adjusted_net < 0 else 1.0
    holding_loss_share = abs(min(holding, 0.0)) / loss_denominator * 100.0
    trading_loss_share = abs(min(trading, 0.0)) / loss_denominator * 100.0
    cost_loss_share = (abs(commission) + abs(slippage)) / loss_denominator * 100.0
    proxy_loss_share = abs(min(proxy_delta, 0.0)) / loss_denominator * 100.0
    start_equity_row = segment[segment["date"].eq(start_date)]
    start_equity = float(start_equity_row["stage070_equity"].iloc[0]) if not start_equity_row.empty else np.nan
    end_equity = start_equity + adjusted_net if pd.notna(start_equity) else np.nan
    return {
        "selected_rank": int(selected_rank),
        "window_id": f"{int(selected_rank):03d}_{source_start_month}_{_date_text(start_date)}_{_date_text(end_date)}",
        "source_start_month": source_start_month,
        "start_date": _date_text(start_date),
        "end_date": _date_text(end_date),
        "period_calendar_days": int((end_date - start_date).days),
        "period_trading_days": int(len(window_part)),
        "stage074_start_equity": start_equity,
        "stage074_end_equity": end_equity,
        "stage074_adjusted_net_pnl": adjusted_net,
        "stage074_base_net_pnl": base_net,
        "stage074_base_holding_pnl": holding,
        "stage074_base_trading_pnl": trading,
        "stage074_base_commission": commission,
        "stage074_base_slippage": slippage,
        "stage074_proxy_delta_pnl": proxy_delta,
        "component_sum_validation_abs_diff": abs(adjusted_net - (base_net + proxy_delta)),
        "base_holding_loss_share_pct": holding_loss_share,
        "base_trading_loss_share_pct": trading_loss_share,
        "cost_loss_share_pct": cost_loss_share,
        "proxy_delta_loss_share_pct": proxy_loss_share,
        "broker10_margin_to_equity_max_pct": float(_numeric(window_part, "broker10_margin_to_equity_pct").max())
        if not window_part.empty
        else 0.0,
        "active_products_max": float(_numeric(window_part, "c3_active_products").max()) if not window_part.empty else 0.0,
        "window_min_drawdown_pct": float(_numeric(window_part, "drawdown_pct").min()) if not window_part.empty else 0.0,
        "oracle_return_pct": float(window.get("oracle_return_pct", np.nan)),
        "stage074_return_pct": float(window.get("stage074_return_pct", np.nan)),
    }


def summarize_lot_attribution(
    lot_deltas: pd.DataFrame,
    window: pd.Series,
    selected_rank: int,
    ramp_by_date: dict[pd.Timestamp, float],
    *,
    target_variant: str = TARGET_VARIANT,
) -> pd.DataFrame:
    if lot_deltas.empty:
        return pd.DataFrame()
    source_start_month = str(window["source_start_month"])
    start_date = pd.Timestamp(window["start_date"]).normalize()
    end_date = pd.Timestamp(window["end_date"]).normalize()
    lots = lot_deltas.copy()
    lots = lots[
        lots["candidate_variant"].astype(str).eq(target_variant)
        & lots["requested_start_month"].astype(str).eq(source_start_month)
    ].copy()
    lots["exit_date"] = pd.to_datetime(lots["exit_date"], errors="coerce").dt.normalize()
    lots = lots[lots["exit_date"].gt(start_date) & lots["exit_date"].le(end_date)].copy()
    if lots.empty:
        return lots
    lots["stage070_proxy_delta_pnl"] = _numeric(lots, "stage070_proxy_delta_pnl")
    lots["stage074_ramp_multiplier_from_window_start"] = lots["exit_date"].map(
        lambda value: float(ramp_by_date.get(pd.Timestamp(value), 0.0))
    )
    lots["stage074_scaled_proxy_delta_pnl"] = (
        lots["stage070_proxy_delta_pnl"] * lots["stage074_ramp_multiplier_from_window_start"]
    )
    lots["selected_rank"] = int(selected_rank)
    lots["window_id"] = f"{int(selected_rank):03d}_{source_start_month}_{_date_text(start_date)}_{_date_text(end_date)}"
    return lots


def run_window_attribution(
    components: pd.DataFrame,
    lot_deltas: pd.DataFrame,
    stage004_windows: pd.DataFrame,
    *,
    top_n: int = TOP_N_WINDOWS,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    windows = stage004_windows.copy()
    windows = windows[windows["oracle_winner"].astype(str).eq("stage074_ramp")].copy()
    windows["oracle_return_pct"] = pd.to_numeric(windows["oracle_return_pct"], errors="coerce")
    windows = windows.dropna(subset=["source_start_month", "start_date", "end_date", "oracle_return_pct"])
    selected = windows.sort_values("oracle_return_pct").head(int(top_n)).reset_index(drop=True)
    rows: list[dict[str, Any]] = []
    lot_frames: list[pd.DataFrame] = []
    for index, window in selected.iterrows():
        rank = index + 1
        row = attribute_stage074_window(components, window, selected_rank=rank)
        rows.append(row)
        source = components[components["requested_start_month"].astype(str).eq(str(window["source_start_month"]))].copy()
        source["date"] = pd.to_datetime(source["date"], errors="coerce").dt.normalize()
        segment = source[
            source["date"].ge(pd.Timestamp(window["start_date"]).normalize())
            & source["date"].le(pd.Timestamp(window["end_date"]).normalize())
        ].sort_values("date")
        multiplier = compute_age_ramp_multiplier(len(segment))
        ramp_by_date = {
            pd.Timestamp(date): float(value)
            for date, value in zip(segment["date"].tolist(), multiplier)
        }
        lot_attr = summarize_lot_attribution(lot_deltas, window, rank, ramp_by_date)
        if not lot_attr.empty:
            lot_frames.append(lot_attr)
    window_attr = pd.DataFrame(rows)
    lot_attr_all = pd.concat(lot_frames, ignore_index=True, sort=False) if lot_frames else pd.DataFrame()
    return window_attr, lot_attr_all


def summarize_window_attribution(window_attr: pd.DataFrame) -> dict[str, Any]:
    if window_attr.empty:
        return {"window_count": 0, "decision": "stage005_missing_stage074_windows"}
    data = window_attr.copy()
    for column in [
        "stage074_adjusted_net_pnl",
        "stage074_base_holding_pnl",
        "stage074_base_trading_pnl",
        "stage074_base_commission",
        "stage074_base_slippage",
        "stage074_proxy_delta_pnl",
    ]:
        data[column] = _numeric(data, column)
    total_loss = float(data["stage074_adjusted_net_pnl"].clip(upper=0.0).abs().sum())
    if total_loss <= 0:
        total_loss = abs(float(data["stage074_adjusted_net_pnl"].sum())) or 1.0
    holding_loss = float(data["stage074_base_holding_pnl"].clip(upper=0.0).abs().sum())
    trading_loss = float(data["stage074_base_trading_pnl"].clip(upper=0.0).abs().sum())
    cost_loss = float(data["stage074_base_commission"].abs().sum() + data["stage074_base_slippage"].abs().sum())
    proxy_loss = float(data["stage074_proxy_delta_pnl"].clip(upper=0.0).abs().sum())
    holding_share = holding_loss / total_loss * 100.0
    trading_share = trading_loss / total_loss * 100.0
    cost_share = cost_loss / total_loss * 100.0
    proxy_share = proxy_loss / total_loss * 100.0
    shares = {
        "stage013_base_holding_dominant": holding_share,
        "stage013_base_trading_dominant": trading_share,
        "cost_pressure_dominant": cost_share,
        "stage070_proxy_lot_delta_dominant": proxy_share,
    }
    dominant = max(shares.items(), key=lambda item: item[1])[0]
    if shares[dominant] < 60.0:
        dominant = "mixed_base_and_proxy_path"
    decision = (
        "stage005_stage074_residual_base_holding_dominant_stop_ai_proxy_tuning"
        if dominant == "stage013_base_holding_dominant"
        else "stage005_stage074_residual_needs_deeper_true_engine_or_signal_audit"
    )
    return {
        "window_count": int(len(data)),
        "stage074_adjusted_net_pnl": float(data["stage074_adjusted_net_pnl"].sum()),
        "stage074_base_holding_pnl": float(data["stage074_base_holding_pnl"].sum()),
        "stage074_base_trading_pnl": float(data["stage074_base_trading_pnl"].sum()),
        "stage074_base_commission": float(data["stage074_base_commission"].sum()),
        "stage074_base_slippage": float(data["stage074_base_slippage"].sum()),
        "stage074_proxy_delta_pnl": float(data["stage074_proxy_delta_pnl"].sum()),
        "base_holding_loss_share_pct": holding_share,
        "base_trading_loss_share_pct": trading_share,
        "cost_loss_share_pct": cost_share,
        "proxy_delta_loss_share_pct": proxy_share,
        "dominant_loss_driver": dominant,
        "decision": decision,
        "oracle_min_return_pct": float(pd.to_numeric(data["oracle_return_pct"], errors="coerce").min()),
        "component_validation_max_abs_diff": float(
            pd.to_numeric(data["component_sum_validation_abs_diff"], errors="coerce").max()
        ),
    }


def _group_lot_summary(lot_attr: pd.DataFrame) -> pd.DataFrame:
    if lot_attr.empty:
        return pd.DataFrame()
    data = lot_attr.copy()
    data["stage074_scaled_proxy_delta_pnl"] = _numeric(data, "stage074_scaled_proxy_delta_pnl")
    keys = ["product", "direction"]
    summary = (
        data.groupby(keys, dropna=False)
        .agg(
            scaled_proxy_delta_pnl=("stage074_scaled_proxy_delta_pnl", "sum"),
            raw_proxy_delta_pnl=("stage070_proxy_delta_pnl", "sum"),
            lot_rows=("stage074_scaled_proxy_delta_pnl", "size"),
            window_count=("window_id", "nunique"),
            source_count=("requested_start_month", "nunique"),
        )
        .reset_index()
        .sort_values("scaled_proxy_delta_pnl")
    )
    return summary


def _month_summary(window_attr: pd.DataFrame) -> pd.DataFrame:
    if window_attr.empty:
        return pd.DataFrame()
    data = window_attr.copy()
    data["start_year_month"] = pd.to_datetime(data["start_date"], errors="coerce").dt.strftime("%Y-%m")
    data["end_year_month"] = pd.to_datetime(data["end_date"], errors="coerce").dt.strftime("%Y-%m")
    rows: list[dict[str, Any]] = []
    for key, group in data.groupby(["start_year_month", "end_year_month"], sort=True):
        summary = summarize_window_attribution(group)
        rows.append({"start_year_month": key[0], "end_year_month": key[1], **summary})
    return pd.DataFrame(rows).sort_values("oracle_min_return_pct").reset_index(drop=True)


def _plot(summary: dict[str, Any]) -> None:
    labels = ["base holding", "base trading", "cost", "proxy delta"]
    values = [
        float(summary.get("base_holding_loss_share_pct", 0.0) or 0.0),
        float(summary.get("base_trading_loss_share_pct", 0.0) or 0.0),
        float(summary.get("cost_loss_share_pct", 0.0) or 0.0),
        float(summary.get("proxy_delta_loss_share_pct", 0.0) or 0.0),
    ]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(labels, values, color=["#4f6d7a", "#59a14f", "#f28e2b", "#d1495b"])
    ax.set_title("Stage005 Stage074 proxy replay loss attribution")
    ax.set_ylabel("Share of negative adjusted PnL (%)")
    for index, value in enumerate(values):
        ax.text(index, value, f"{value:.1f}%", ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _md_table(frame: pd.DataFrame, max_rows: int = 20) -> str:
    if frame.empty:
        return "_无数据_"
    data = frame.head(max_rows).copy()
    for column in data.columns:
        if pd.api.types.is_float_dtype(data[column]):
            data[column] = data[column].map(lambda value: f"{value:.4f}" if pd.notna(value) else "")
    return data.to_markdown(index=False)


def _write_report(
    summary: dict[str, Any],
    window_attr: pd.DataFrame,
    product_direction: pd.DataFrame,
    month_summary: pd.DataFrame,
) -> None:
    lines = [
        "# Stage005 Stage074 proxy replay 路径归因",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：day",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 阶段性质：只读代理重放；不新增交易规则，不修改官方实盘/CTP/邮件/launchd",
        "- 是否重要突破：否",
        "- 是否触发A/B：否",
        "",
        "## 外部调研与判断",
        "",
        "- 系统化期货回测资料强调 futures PnL 必须保留合约乘数、仓位和成本口径；代理曲线不能直接替代真实持仓账。",
        "- 趋势跟随 whipsaw/drawdown 资料提示，要先区分 base 持仓路径亏损和新增信号加风险亏损。",
        "- 我的判断：Stage074 仍是代理重放，但能把 Stage004 的 `unsplit equity delta` 拆回 Stage013 base PnL 与 Stage070 lot delta；若 base holding 主导，就不要继续调 AI proxy。",
        "",
        "## 关键结果",
        "",
        f"- 决策：`{summary['decision']}`。",
        f"- Stage074 ramp 窗口数：`{summary['window_count']}`。",
        f"- oracle 最差收益：`{summary.get('oracle_min_return_pct'):.4f}%`。",
        f"- adjusted net pnl：`{summary.get('stage074_adjusted_net_pnl'):,.4f}`。",
        f"- base holding loss share：`{summary.get('base_holding_loss_share_pct'):.4f}%`。",
        f"- base trading loss share：`{summary.get('base_trading_loss_share_pct'):.4f}%`。",
        f"- cost loss share：`{summary.get('cost_loss_share_pct'):.4f}%`。",
        f"- Stage070 proxy delta loss share：`{summary.get('proxy_delta_loss_share_pct'):.4f}%`。",
        f"- component validation max abs diff：`{summary.get('component_validation_max_abs_diff'):.8f}`。",
        "",
        "## 最差窗口样例",
        "",
        _md_table(
            window_attr[
                [
                    "selected_rank",
                    "source_start_month",
                    "start_date",
                    "end_date",
                    "oracle_return_pct",
                    "stage074_adjusted_net_pnl",
                    "stage074_base_holding_pnl",
                    "stage074_base_trading_pnl",
                    "stage074_proxy_delta_pnl",
                    "base_holding_loss_share_pct",
                    "proxy_delta_loss_share_pct",
                ]
            ],
            max_rows=20,
        ),
        "",
        "## Stage070 proxy lot 产品方向归因",
        "",
        _md_table(product_direction, max_rows=30),
        "",
        "## 月份聚类",
        "",
        _md_table(month_summary, max_rows=20),
        "",
        "## 结论",
        "",
        "- Stage005 不是新策略候选；它只是把 Stage074 equity-only residual 拆回可审计的 base PnL 与 proxy lot delta。",
        "- 若 base holding loss share 明显占主导，说明当前左尾不是 AI 加风险 lot 本身造成，而是母本持仓路径/行情 whipsaw 主导。",
        "- 下一步应避免继续调 Stage070/074 代理参数；若要真正优化，应做真实 engine 或账户层结构，而不是按历史窗口调 AI 选品阈值。",
        "",
        "## 过拟合反思",
        "",
        "- 运行前判断：不过拟合，本阶段只重放代理分量，不设计新参数。",
        "- 运行后判断：不过拟合。",
        "- 原因：没有把窗口归因转换成品种/方向/日期黑名单，也没有新增交易阈值。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前判断：有价值。",
        "- 运行后判断：有价值。",
        "- 原因：能判断 Stage074 residual 是否值得继续沿 AI proxy 优化，还是应转向母本持仓路径或真实 engine。",
        "",
        "## 输出文件",
        "",
        f"- daily_components：`{DAILY_COMPONENTS_PATH}`",
        f"- window_attribution：`{WINDOW_ATTRIBUTION_PATH}`",
        f"- lot_attribution：`{LOT_ATTRIBUTION_PATH}`",
        f"- product_direction：`{PRODUCT_DIRECTION_PATH}`",
        f"- month_summary：`{MONTH_SUMMARY_PATH}`",
        f"- chart：`{CHART_PATH}`",
        f"- decision：`{DECISION_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    base_curves = _read_csv(STAGE013_CURVES_PATH)
    lot_deltas = _read_csv(STAGE070_LOT_DELTAS_PATH)
    stage004_windows = _read_csv(STAGE004_WINDOW_ATTRIBUTION_PATH)
    components = build_stage070_daily_components(base_curves, lot_deltas)
    window_attr, lot_attr = run_window_attribution(components, lot_deltas, stage004_windows)
    summary = summarize_window_attribution(window_attr)
    product_direction = _group_lot_summary(lot_attr)
    month = _month_summary(window_attr)
    decision_payload = {
        "summary": summary,
        "outputs": {
            "daily_components": str(DAILY_COMPONENTS_PATH),
            "window_attribution": str(WINDOW_ATTRIBUTION_PATH),
            "lot_attribution": str(LOT_ATTRIBUTION_PATH),
            "product_direction": str(PRODUCT_DIRECTION_PATH),
            "month_summary": str(MONTH_SUMMARY_PATH),
            "chart": str(CHART_PATH),
            "report": str(REPORT_PATH),
            "decision": str(DECISION_PATH),
        },
    }
    components.to_csv(DAILY_COMPONENTS_PATH, index=False, encoding="utf-8-sig", compression="gzip")
    window_attr.to_csv(WINDOW_ATTRIBUTION_PATH, index=False, encoding="utf-8-sig")
    lot_attr.to_csv(LOT_ATTRIBUTION_PATH, index=False, encoding="utf-8-sig", compression="gzip")
    product_direction.to_csv(PRODUCT_DIRECTION_PATH, index=False, encoding="utf-8-sig")
    month.to_csv(MONTH_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    _plot(summary)
    _write_report(summary, window_attr, product_direction, month)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision_payload), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(summary), ensure_ascii=False, indent=2))
    return decision_payload


if __name__ == "__main__":
    main()
