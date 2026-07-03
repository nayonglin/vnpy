from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
UPSTREAM_LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage006"
MODEL_TAG = "stage006_stage013_base_holding_position_attribution_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage006_stage013_base_holding_position_attribution"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
UPSTREAM_LINE_DIR = PROJECT_DIR / "research" / "lines" / UPSTREAM_LINE_ID
UPSTREAM_TOOLS_DIR = UPSTREAM_LINE_DIR / "tools"
if str(UPSTREAM_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(UPSTREAM_TOOLS_DIR))


OUTPUT_DIR = LINE_DIR / "outputs" / "stage006_stage013_base_holding_position_attribution"

STAGE005_OUTPUT_DIR = LINE_DIR / "outputs" / "stage005_stage074_proxy_replay_attribution"
STAGE005_PREFIX = "rebuilt_c9_v2_stage005_stage074_proxy_replay_attribution"
STAGE005_TAG = "stage005_stage074_proxy_replay_attribution_v1"
STAGE005_WINDOW_ATTRIBUTION_PATH = (
    STAGE005_OUTPUT_DIR / f"{STAGE005_PREFIX}_window_attribution_{STAGE005_TAG}.csv"
)
STAGE005_DAILY_COMPONENTS_PATH = (
    STAGE005_OUTPUT_DIR / f"{STAGE005_PREFIX}_daily_components_{STAGE005_TAG}.csv.gz"
)

POSITIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_{MODEL_TAG}.csv.gz"
WINDOW_POSITION_DETAIL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_position_detail_{MODEL_TAG}.csv.gz"
PRODUCT_DIRECTION_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_direction_summary_{MODEL_TAG}.csv"
SOURCE_BUCKET_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_bucket_summary_{MODEL_TAG}.csv"
WINDOW_VALIDATION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_validation_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_position_holding_chart_{MODEL_TAG}.png"

RAMP_FLOOR = 0.35
RAMP_TRADING_DAYS = 252


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


def _month_start(month: Any) -> pd.Timestamp:
    return pd.Timestamp(f"{str(month)[:7]}-01").normalize()


def _product_from_vt_symbol(vt_symbol: Any) -> str:
    text = str(vt_symbol or "")
    if "." not in text:
        product = "".join(ch for ch in text if ch.isalpha()) or text
        return product
    symbol, exchange = text.split(".", 1)
    product = "".join(ch for ch in symbol if ch.isalpha()) or symbol
    return f"{product}.{exchange}"


def _direction_from_position(start_pos: float, end_pos: float, pos_change: float = 0.0) -> str:
    position = start_pos if abs(start_pos) > 1e-9 else end_pos
    if abs(position) <= 1e-9:
        position = -1.0 if pos_change < 0 else 1.0 if pos_change > 0 else 0.0
    if position > 0:
        return "long"
    if position < 0:
        return "short"
    return "flat"


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


def _ramp_by_date_from_dates(
    dates: pd.Series,
    *,
    ramp_floor: float = RAMP_FLOOR,
    ramp_trading_days: int = RAMP_TRADING_DAYS,
) -> dict[pd.Timestamp, float]:
    unique_dates = pd.Series(pd.to_datetime(dates, errors="coerce").dropna().unique()).sort_values().reset_index(drop=True)
    multiplier = compute_age_ramp_multiplier(
        len(unique_dates),
        floor=ramp_floor,
        ramp_trading_days=ramp_trading_days,
    )
    return {pd.Timestamp(date).normalize(): float(value) for date, value in zip(unique_dates, multiplier)}


def _prepare_positions(positions: pd.DataFrame) -> pd.DataFrame:
    data = positions.copy()
    data["requested_start_month"] = data["requested_start_month"].astype(str)
    data["source_start_month"] = data["requested_start_month"]
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    data = data.dropna(subset=["requested_start_month", "date"])
    for column in [
        "start_pos",
        "end_pos",
        "pos_change",
        "trade_count",
        "holding_pnl",
        "trading_pnl",
        "commission",
        "slippage",
        "net_pnl",
        "total_pnl",
    ]:
        data[column] = _numeric(data, column)
    data["product"] = data["vt_symbol"].map(_product_from_vt_symbol)
    position = data["start_pos"].where(data["start_pos"].abs().gt(1e-9), data["end_pos"])
    position = position.where(position.abs().gt(1e-9), np.sign(data["pos_change"]))
    data["direction"] = np.select(
        [position.gt(0), position.lt(0)],
        ["long", "short"],
        default="flat",
    )
    return data.sort_values(["requested_start_month", "date", "vt_symbol"]).reset_index(drop=True)


def attribute_window_positions(
    positions: pd.DataFrame,
    window: pd.Series,
    selected_rank: int,
    *,
    ramp_floor: float = RAMP_FLOOR,
    ramp_trading_days: int = RAMP_TRADING_DAYS,
    ramp_by_date: dict[pd.Timestamp, float] | None = None,
) -> pd.DataFrame:
    source_start_month = str(window["source_start_month"])
    start_date = pd.Timestamp(window["start_date"]).normalize()
    end_date = pd.Timestamp(window["end_date"]).normalize()
    if {"source_start_month", "product", "direction"}.issubset(positions.columns):
        data = positions.copy()
    else:
        data = _prepare_positions(positions)
    source = data[data["requested_start_month"].astype(str).eq(source_start_month)].copy()
    segment = source[source["date"].ge(start_date) & source["date"].le(end_date)].copy()
    if ramp_by_date is None:
        ramp_by_date = _ramp_by_date_from_dates(
            segment["date"],
            ramp_floor=ramp_floor,
            ramp_trading_days=ramp_trading_days,
        )
    existing_contracts = set(
        segment[
            segment["date"].eq(start_date)
            & (segment["start_pos"].abs() + segment["end_pos"].abs()).gt(1e-9)
        ]["vt_symbol"].astype(str)
    )
    window_positions = segment[segment["date"].gt(start_date) & segment["date"].le(end_date)].copy()
    if window_positions.empty:
        return pd.DataFrame()
    active = (
        window_positions["start_pos"].abs()
        + window_positions["end_pos"].abs()
        + window_positions["pos_change"].abs()
        + window_positions["trade_count"].abs()
    ).gt(1e-9)
    window_positions = window_positions[active].copy()
    if window_positions.empty:
        return pd.DataFrame()
    window_positions["source_bucket"] = np.where(
        window_positions["vt_symbol"].astype(str).isin(existing_contracts),
        "existing_at_window_start",
        "opened_or_traded_after_window_start",
    )
    window_positions["stage074_ramp_multiplier_from_window_start"] = window_positions["date"].map(
        lambda value: float(ramp_by_date.get(pd.Timestamp(value).normalize(), 0.0))
    )
    m = window_positions["stage074_ramp_multiplier_from_window_start"]
    window_positions["stage074_scaled_holding_pnl"] = window_positions["holding_pnl"] * m
    window_positions["stage074_scaled_trading_pnl"] = window_positions["trading_pnl"] * m
    window_positions["stage074_scaled_commission"] = window_positions["commission"] * m
    window_positions["stage074_scaled_slippage"] = window_positions["slippage"] * m
    window_positions["stage074_scaled_cost"] = window_positions["stage074_scaled_commission"] + window_positions["stage074_scaled_slippage"]
    window_positions["stage074_scaled_net_pnl"] = window_positions["net_pnl"] * m
    window_id = f"{int(selected_rank):03d}_{source_start_month}_{_date_text(start_date)}_{_date_text(end_date)}"
    window_positions["selected_rank"] = int(selected_rank)
    window_positions["window_id"] = window_id
    window_positions["window_start_date"] = _date_text(start_date)
    window_positions["window_end_date"] = _date_text(end_date)

    summary = (
        window_positions.groupby(
            [
                "selected_rank",
                "window_id",
                "source_start_month",
                "window_start_date",
                "window_end_date",
                "product",
                "direction",
                "source_bucket",
            ],
            dropna=False,
        )
        .agg(
            stage074_scaled_holding_pnl=("stage074_scaled_holding_pnl", "sum"),
            stage074_scaled_trading_pnl=("stage074_scaled_trading_pnl", "sum"),
            stage074_scaled_commission=("stage074_scaled_commission", "sum"),
            stage074_scaled_slippage=("stage074_scaled_slippage", "sum"),
            stage074_scaled_cost=("stage074_scaled_cost", "sum"),
            stage074_scaled_net_pnl=("stage074_scaled_net_pnl", "sum"),
            active_days=("date", "nunique"),
            contract_count=("vt_symbol", "nunique"),
            trade_count=("trade_count", "sum"),
            max_abs_end_pos=("end_pos", lambda s: float(pd.to_numeric(s, errors="coerce").abs().max())),
        )
        .reset_index()
    )
    return summary.sort_values("stage074_scaled_holding_pnl").reset_index(drop=True)


def summarize_position_detail(detail: pd.DataFrame) -> dict[str, Any]:
    if detail.empty:
        return {
            "row_count": 0,
            "dominant_loss_driver": "missing_position_detail",
        }
    data = detail.copy()
    for column in [
        "stage074_scaled_holding_pnl",
        "stage074_scaled_trading_pnl",
        "stage074_scaled_cost",
        "stage074_scaled_net_pnl",
    ]:
        data[column] = _numeric(data, column)
    total_loss = float(data["stage074_scaled_net_pnl"].clip(upper=0.0).abs().sum())
    if total_loss <= 0:
        total_loss = abs(float(data["stage074_scaled_net_pnl"].sum())) or 1.0
    holding_loss = float(data["stage074_scaled_holding_pnl"].clip(upper=0.0).abs().sum())
    trading_loss = float(data["stage074_scaled_trading_pnl"].clip(upper=0.0).abs().sum())
    cost_loss = float(data["stage074_scaled_cost"].abs().sum())
    holding_share = holding_loss / total_loss * 100.0
    trading_share = trading_loss / total_loss * 100.0
    cost_share = cost_loss / total_loss * 100.0
    shares = {
        "position_holding_pnl_dominant": holding_share,
        "position_trading_pnl_dominant": trading_share,
        "position_cost_dominant": cost_share,
    }
    dominant = max(shares.items(), key=lambda item: item[1])[0]
    if shares[dominant] < 60.0:
        dominant = "mixed_position_path"

    bucket_loss = (
        data.assign(holding_loss_abs=data["stage074_scaled_holding_pnl"].clip(upper=0.0).abs())
        .groupby("source_bucket", dropna=False)["holding_loss_abs"]
        .sum()
    )
    holding_denominator = float(bucket_loss.sum()) or 1.0
    existing_share = float(bucket_loss.get("existing_at_window_start", 0.0)) / holding_denominator * 100.0
    opened_share = float(bucket_loss.get("opened_or_traded_after_window_start", 0.0)) / holding_denominator * 100.0

    return {
        "row_count": int(len(data)),
        "window_count": int(data.get("window_id", pd.Series(dtype=str)).nunique()),
        "source_count": int(data.get("source_start_month", pd.Series(dtype=str)).nunique()),
        "stage074_scaled_net_pnl": float(data["stage074_scaled_net_pnl"].sum()),
        "stage074_scaled_holding_pnl": float(data["stage074_scaled_holding_pnl"].sum()),
        "stage074_scaled_trading_pnl": float(data["stage074_scaled_trading_pnl"].sum()),
        "stage074_scaled_cost": float(data["stage074_scaled_cost"].sum()),
        "holding_loss_share_pct": holding_share,
        "trading_loss_share_pct": trading_share,
        "cost_loss_share_pct": cost_share,
        "existing_at_window_start_holding_loss_share_pct": existing_share,
        "opened_after_window_start_holding_loss_share_pct": opened_share,
        "dominant_loss_driver": dominant,
    }


def _run_stage013_positions(sources: list[str], requested_end: pd.Timestamp) -> pd.DataFrame:
    import stage013_account_state_pilot_gate_engine as s013

    metadata = s013.s901.s513._metadata()
    frames: list[pd.DataFrame] = []
    for index, source in enumerate(sources, start=1):
        start = _month_start(source)
        print(f"[stage006] running stage013 positions {index}/{len(sources)} source={source} end={_date_text(requested_end)}", flush=True)
        _combined, run_frames, _spec = s013._run_live_stage013(metadata, start, requested_end)
        positions = run_frames.get("positions", pd.DataFrame()).copy()
        if positions.empty:
            continue
        positions["requested_start_month"] = source
        positions["requested_start"] = _date_text(start)
        positions["requested_end"] = _date_text(requested_end)
        positions["stage"] = STAGE
        positions["model_tag"] = MODEL_TAG
        positions["line_id"] = LINE_ID
        frames.append(positions)
    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()


def _ramp_by_date_for_window(daily_components: pd.DataFrame, window: pd.Series) -> dict[pd.Timestamp, float]:
    source = str(window["source_start_month"])
    start_date = pd.Timestamp(window["start_date"]).normalize()
    end_date = pd.Timestamp(window["end_date"]).normalize()
    data = daily_components
    if not pd.api.types.is_datetime64_any_dtype(data["date"]):
        data = data.copy()
        data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    segment = data[
        data["requested_start_month"].astype(str).eq(source)
        & data["date"].ge(start_date)
        & data["date"].le(end_date)
    ].sort_values("date")
    multiplier = compute_age_ramp_multiplier(len(segment))
    return {pd.Timestamp(date).normalize(): float(value) for date, value in zip(segment["date"].tolist(), multiplier)}


def run_position_attribution(
    positions: pd.DataFrame,
    windows: pd.DataFrame,
    daily_components: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    prepared_positions = _prepare_positions(positions)
    positions_by_source = {
        str(source): group.reset_index(drop=True)
        for source, group in prepared_positions.groupby("source_start_month", sort=False)
    }
    prepared_daily = daily_components.copy()
    prepared_daily["date"] = pd.to_datetime(prepared_daily["date"], errors="coerce").dt.normalize()
    daily_by_source = {
        str(source): group.reset_index(drop=True)
        for source, group in prepared_daily.groupby("requested_start_month", sort=False)
    }
    detail_frames: list[pd.DataFrame] = []
    validation_rows: list[dict[str, Any]] = []
    ordered = windows.copy()
    ordered["oracle_return_pct"] = pd.to_numeric(ordered["oracle_return_pct"], errors="coerce")
    ordered = ordered.sort_values("oracle_return_pct").reset_index(drop=True)
    for index, window in ordered.iterrows():
        rank = index + 1
        source = str(window["source_start_month"])
        source_daily = daily_by_source.get(source, prepared_daily.iloc[0:0])
        ramp_by_date = _ramp_by_date_for_window(source_daily, window)
        source_positions = positions_by_source.get(source, prepared_positions.iloc[0:0])
        detail = attribute_window_positions(source_positions, window, rank, ramp_by_date=ramp_by_date)
        if not detail.empty:
            detail_frames.append(detail)
        holding_sum = float(_numeric(detail, "stage074_scaled_holding_pnl").sum()) if not detail.empty else 0.0
        trading_sum = float(_numeric(detail, "stage074_scaled_trading_pnl").sum()) if not detail.empty else 0.0
        cost_sum = float(_numeric(detail, "stage074_scaled_cost").sum()) if not detail.empty else 0.0
        validation_rows.append(
            {
                "selected_rank": rank,
                "window_id": f"{rank:03d}_{window['source_start_month']}_{window['start_date']}_{window['end_date']}",
                "source_start_month": str(window["source_start_month"]),
                "start_date": window["start_date"],
                "end_date": window["end_date"],
                "stage005_base_holding_pnl": float(window.get("stage074_base_holding_pnl", np.nan)),
                "position_scaled_holding_pnl": holding_sum,
                "holding_abs_diff": abs(float(window.get("stage074_base_holding_pnl", 0.0)) - holding_sum),
                "stage005_base_trading_pnl": float(window.get("stage074_base_trading_pnl", np.nan)),
                "position_scaled_trading_pnl": trading_sum,
                "trading_abs_diff": abs(float(window.get("stage074_base_trading_pnl", 0.0)) - trading_sum),
                "stage005_base_cost": float(window.get("stage074_base_slippage", 0.0)) + float(window.get("stage074_base_commission", 0.0)),
                "position_scaled_cost": cost_sum,
                "cost_abs_diff": abs(
                    float(window.get("stage074_base_slippage", 0.0)) + float(window.get("stage074_base_commission", 0.0)) - cost_sum
                ),
            }
        )
    detail_all = pd.concat(detail_frames, ignore_index=True, sort=False) if detail_frames else pd.DataFrame()
    validation = pd.DataFrame(validation_rows)
    return detail_all, validation


def _group_summary(detail: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    if detail.empty:
        return pd.DataFrame()
    data = detail.copy()
    for column in [
        "stage074_scaled_holding_pnl",
        "stage074_scaled_trading_pnl",
        "stage074_scaled_cost",
        "stage074_scaled_net_pnl",
    ]:
        data[column] = _numeric(data, column)
    return (
        data.groupby(keys, dropna=False)
        .agg(
            stage074_scaled_holding_pnl=("stage074_scaled_holding_pnl", "sum"),
            stage074_scaled_trading_pnl=("stage074_scaled_trading_pnl", "sum"),
            stage074_scaled_cost=("stage074_scaled_cost", "sum"),
            stage074_scaled_net_pnl=("stage074_scaled_net_pnl", "sum"),
            window_count=("window_id", "nunique"),
            source_count=("source_start_month", "nunique"),
            active_days=("active_days", "sum"),
            contract_count=("contract_count", "sum"),
        )
        .reset_index()
        .sort_values("stage074_scaled_holding_pnl")
    )


def make_decision(summary: dict[str, Any], validation: pd.DataFrame, product_direction: pd.DataFrame) -> dict[str, Any]:
    max_diff = (
        float(
            validation[["holding_abs_diff", "trading_abs_diff", "cost_abs_diff"]]
            .apply(pd.to_numeric, errors="coerce")
            .max()
            .max()
        )
        if not validation.empty
        else np.nan
    )
    if np.isfinite(max_diff) and max_diff > 1e-6:
        decision = "stage006_position_validation_warning_do_not_use_for_strategy"
    elif float(summary.get("existing_at_window_start_holding_loss_share_pct", 0.0)) >= 60.0:
        decision = "stage006_base_holding_existing_positions_dominant_need_holding_risk_structure"
    elif float(summary.get("opened_after_window_start_holding_loss_share_pct", 0.0)) >= 60.0:
        decision = "stage006_base_holding_new_positions_dominant_need_entry_signal_audit"
    else:
        decision = "stage006_base_holding_mixed_position_path_need_deeper_replay"
    worst = product_direction.iloc[0].to_dict() if not product_direction.empty else {}
    return {
        "decision": decision,
        "max_validation_abs_diff": max_diff,
        **summary,
        "worst_product_direction": _json_safe(worst),
    }


def _plot(product_direction: pd.DataFrame, source_bucket: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(16, 6), constrained_layout=True)
    ax = axes[0]
    if not product_direction.empty:
        shown = product_direction.head(12).copy()
        shown["label"] = shown["product"].astype(str) + " " + shown["direction"].astype(str) + "\n" + shown["source_bucket"].astype(str)
        ax.barh(shown["label"], shown["stage074_scaled_holding_pnl"], color="#d1495b")
    ax.set_title("Worst Product/Direction Holding PnL")
    ax.set_xlabel("stage074 scaled holding pnl")
    ax.grid(True, axis="x", alpha=0.25)

    ax = axes[1]
    if not source_bucket.empty:
        ax.barh(source_bucket["source_bucket"], source_bucket["stage074_scaled_holding_pnl"], color="#4f6d7a")
    ax.set_title("Holding PnL By Position Source Bucket")
    ax.set_xlabel("stage074 scaled holding pnl")
    ax.grid(True, axis="x", alpha=0.25)
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
    decision: dict[str, Any],
    product_direction: pd.DataFrame,
    source_bucket: pd.DataFrame,
    validation: pd.DataFrame,
) -> None:
    lines = [
        "# Stage006 Stage013 base holding position 归因",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：day",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 阶段性质：只读 Stage013 positions 重放；不新增交易规则，不修改官方实盘/CTP/邮件/launchd",
        "- 是否重要突破：否",
        "- 是否触发A/B：否",
        "",
        "## 外部调研与判断",
        "",
        "- 系统化期货回测资料强调，PnL 归因要把仓位、成本、合约方向和账户层分开，否则容易把 mark-to-market 损失误判成信号筛选问题。",
        "- 趋势跟随资料提示 whipsaw 和 timing luck 往往表现为持仓期浮亏，而非某个单一入场标签错误。",
        "- 我的判断：Stage005 已排除 AI proxy 主导，本阶段只验证母本 base holding 的产品/方向/仓位来源。",
        "",
        "## 关键结果",
        "",
        f"- 决策：`{decision['decision']}`。",
        f"- 归因行数：`{decision.get('row_count', 0)}`；窗口数：`{decision.get('window_count', 0)}`。",
        f"- scaled holding pnl：`{decision.get('stage074_scaled_holding_pnl', np.nan):,.4f}`。",
        f"- holding loss share：`{decision.get('holding_loss_share_pct', np.nan):.4f}%`。",
        f"- 起点已有仓 holding loss share：`{decision.get('existing_at_window_start_holding_loss_share_pct', np.nan):.4f}%`。",
        f"- 窗口后新增/交易仓 holding loss share：`{decision.get('opened_after_window_start_holding_loss_share_pct', np.nan):.4f}%`。",
        f"- validation max abs diff：`{decision.get('max_validation_abs_diff', np.nan):.8f}`。",
        "",
        "## 产品方向归因",
        "",
        _md_table(product_direction, max_rows=30),
        "",
        "## 仓位来源分桶",
        "",
        _md_table(source_bucket, max_rows=20),
        "",
        "## 校验",
        "",
        _md_table(validation.sort_values("holding_abs_diff", ascending=False), max_rows=30),
        "",
        "## 结论",
        "",
        "- 本阶段不产生新规则；只确认 Stage013 base holding 的实际产品/方向/仓位来源。",
        "- 若亏损集中在窗口起点已有仓，下一步应研究持仓风险结构或账户层，而不是开仓筛选。",
        "- 若亏损集中在窗口后新开仓，下一步才回到入场质量或 AI 选品。",
        "",
        "## 过拟合反思",
        "",
        "- 运行前判断：不过拟合，本阶段只重放 positions 并做路径归因。",
        "- 运行后判断：不过拟合。",
        "- 原因：没有按产品/方向/日期生成黑名单，也没有调参。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前判断：有价值。",
        "- 运行后判断：有价值。",
        "- 原因：它决定下一步是做持仓风险结构，还是回到入场质量。",
        "",
        "## 输出文件",
        "",
        f"- positions：`{POSITIONS_PATH}`",
        f"- window_position_detail：`{WINDOW_POSITION_DETAIL_PATH}`",
        f"- product_direction：`{PRODUCT_DIRECTION_SUMMARY_PATH}`",
        f"- source_bucket：`{SOURCE_BUCKET_SUMMARY_PATH}`",
        f"- validation：`{WINDOW_VALIDATION_PATH}`",
        f"- chart：`{CHART_PATH}`",
        f"- decision：`{DECISION_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    windows = _read_csv(STAGE005_WINDOW_ATTRIBUTION_PATH)
    daily_components = _read_csv(STAGE005_DAILY_COMPONENTS_PATH)
    windows["end_date"] = pd.to_datetime(windows["end_date"], errors="coerce").dt.normalize()
    requested_end = pd.Timestamp(windows["end_date"].max()).normalize()
    sources = sorted(windows["source_start_month"].dropna().astype(str).unique().tolist())

    if POSITIONS_PATH.exists():
        positions = _read_csv(POSITIONS_PATH)
    else:
        positions = _run_stage013_positions(sources, requested_end)
        positions.to_csv(POSITIONS_PATH, index=False, encoding="utf-8-sig", compression="gzip")
    detail, validation = run_position_attribution(positions, windows, daily_components)
    product_direction = _group_summary(detail, ["product", "direction", "source_bucket"])
    source_bucket = _group_summary(detail, ["source_bucket"])
    summary = summarize_position_detail(detail)
    decision = make_decision(summary, validation, product_direction)

    detail.to_csv(WINDOW_POSITION_DETAIL_PATH, index=False, encoding="utf-8-sig", compression="gzip")
    product_direction.to_csv(PRODUCT_DIRECTION_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    source_bucket.to_csv(SOURCE_BUCKET_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    validation.to_csv(WINDOW_VALIDATION_PATH, index=False, encoding="utf-8-sig")
    _plot(product_direction, source_bucket)
    _write_report(decision, product_direction, source_bucket, validation)
    payload = {
        "decision": decision,
        "sources": sources,
        "requested_end": _date_text(requested_end),
        "outputs": {
            "positions": str(POSITIONS_PATH),
            "window_position_detail": str(WINDOW_POSITION_DETAIL_PATH),
            "product_direction": str(PRODUCT_DIRECTION_SUMMARY_PATH),
            "source_bucket": str(SOURCE_BUCKET_SUMMARY_PATH),
            "validation": str(WINDOW_VALIDATION_PATH),
            "chart": str(CHART_PATH),
            "report": str(REPORT_PATH),
            "decision": str(DECISION_PATH),
        },
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    return payload


if __name__ == "__main__":
    main()
