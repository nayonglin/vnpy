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
STAGE = "Stage004"
MODEL_TAG = "stage004_oracle_residual_path_attribution_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage004_oracle_residual_path_attribution"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
UPSTREAM_LINE_DIR = PROJECT_DIR / "research" / "lines" / UPSTREAM_LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage004_oracle_residual_path_attribution"

STAGE003_OUTPUT_DIR = LINE_DIR / "outputs" / "stage003_residual_complement_audit"
STAGE003_PREFIX = "rebuilt_c9_v2_stage003_residual_complement_audit"
STAGE003_TAG = "stage003_residual_complement_audit_v1"
STAGE003_ORACLE_WORST_PATH = (
    STAGE003_OUTPUT_DIR / f"{STAGE003_PREFIX}_oracle_worst_windows_{STAGE003_TAG}.csv"
)

STAGE052_CURVES_PATH = (
    UPSTREAM_LINE_DIR
    / "outputs"
    / "stage052_contract_oi_share_add_risk_proxy"
    / "rebuilt_c9_stage052_contract_oi_share_add_risk_proxy_curves_stage052_contract_oi_share_add_risk_proxy_v1.csv"
)
STAGE074_PANEL_PATH = (
    UPSTREAM_LINE_DIR
    / "outputs"
    / "stage074_cold_start_capital_ramp_proxy"
    / "rebuilt_c9_stage074_cold_start_capital_ramp_proxy_panel_curves_stage074_cold_start_capital_ramp_proxy_v1.csv.gz"
)

WINDOW_ATTRIBUTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_attribution_{MODEL_TAG}.csv"
SOURCE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_summary_{MODEL_TAG}.csv"
MONTH_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_month_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_loss_driver_chart_{MODEL_TAG}.png"

TOP_N_WINDOWS = 1000
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


def _prepare_curve(frame: pd.DataFrame) -> pd.DataFrame:
    data = frame.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    data = data.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    return data


def _state_at_or_before(curve: pd.DataFrame, date: pd.Timestamp, column: str) -> float:
    source = curve[curve["date"].le(date)]
    if source.empty:
        source = curve[curve["date"].ge(date)]
    if source.empty or column not in source.columns:
        return np.nan
    return float(pd.to_numeric(source[column], errors="coerce").ffill().iloc[-1])


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


def _dominant_from_shares(
    *,
    holding_loss_share_pct: float,
    trading_loss_share_pct: float,
    cost_loss_share_pct: float,
    proxy_delta_loss_share_pct: float,
    unsplit_loss_share_pct: float,
) -> str:
    shares = {
        "holding_pnl_dominant": holding_loss_share_pct,
        "trading_pnl_dominant": trading_loss_share_pct,
        "cost_pressure_dominant": cost_loss_share_pct,
        "proxy_delta_dominant": proxy_delta_loss_share_pct,
        "unsplit_equity_delta_dominant": unsplit_loss_share_pct,
    }
    label, value = max(shares.items(), key=lambda item: item[1])
    if value >= 60.0:
        return label
    if unsplit_loss_share_pct >= 40.0:
        return "unsplit_equity_delta_dominant"
    return "mixed_path"


def attribute_window(
    curve: pd.DataFrame,
    window: pd.Series,
    selected_rank: int,
    *,
    equity_column: str = "account_equity",
    delta_column: str | None = None,
    attribution_kind: str = "daily_pnl_exact",
    oracle_winner: str | None = None,
    use_start_reset_ramp: bool = False,
    ramp_floor: float = RAMP_FLOOR,
    ramp_trading_days: int = RAMP_TRADING_DAYS,
) -> dict[str, Any]:
    source_start_month = str(window.get("source_start_month", window.get("requested_start_month", "")))
    start_date = pd.Timestamp(window["start_date"]).normalize()
    end_date = pd.Timestamp(window["end_date"]).normalize()
    source_curve = _prepare_curve(curve)
    if "requested_start_month" in source_curve.columns and source_start_month:
        source_curve = source_curve[source_curve["requested_start_month"].astype(str).eq(source_start_month)].copy()

    start_equity = _state_at_or_before(source_curve, start_date, equity_column)
    end_equity = _state_at_or_before(source_curve, end_date, equity_column)
    window_curve = source_curve[source_curve["date"].gt(start_date) & source_curve["date"].le(end_date)].copy()

    if use_start_reset_ramp:
        raw_equity = pd.to_numeric(
            source_curve[source_curve["date"].ge(start_date) & source_curve["date"].le(end_date)][equity_column],
            errors="coerce",
        ).ffill()
        raw_delta = raw_equity.diff().fillna(0.0).to_numpy(dtype=float)
        multiplier = compute_age_ramp_multiplier(
            len(raw_delta),
            floor=ramp_floor,
            ramp_trading_days=ramp_trading_days,
        )
        adjusted_delta = raw_delta * multiplier
        net_pnl = float(adjusted_delta[1:].sum()) if len(adjusted_delta) > 1 else 0.0
        end_equity = start_equity + float(adjusted_delta[1:].sum()) if pd.notna(start_equity) else np.nan
        holding_pnl = 0.0
        trading_pnl = 0.0
        commission = 0.0
        slippage = 0.0
        proxy_delta_pnl = 0.0
        unsplit_equity_delta_pnl = net_pnl
        split_precision = "equity_delta_only"
    else:
        base_net_pnl = float(_numeric(window_curve, "net_pnl", 0.0).sum())
        proxy_delta_pnl = float(_numeric(window_curve, delta_column, 0.0).sum()) if delta_column else 0.0
        net_pnl = base_net_pnl + proxy_delta_pnl
        holding_pnl = float(_numeric(window_curve, "holding_pnl", 0.0).sum())
        trading_pnl = float(_numeric(window_curve, "trading_pnl", 0.0).sum())
        commission = float(_numeric(window_curve, "commission", 0.0).sum())
        slippage = float(_numeric(window_curve, "slippage", 0.0).sum())
        unsplit_equity_delta_pnl = 0.0
        split_precision = "exact_base_plus_proxy_delta" if delta_column else "exact_base_daily_pnl"

    equity_change = end_equity - start_equity if pd.notna(start_equity) and pd.notna(end_equity) else np.nan
    loss_denominator = abs(net_pnl) if net_pnl < 0 else abs(equity_change) if pd.notna(equity_change) else 0.0
    if loss_denominator <= 0:
        loss_denominator = 1.0

    holding_loss_abs = abs(min(holding_pnl, 0.0))
    trading_loss_abs = abs(min(trading_pnl, 0.0))
    cost_loss_abs = abs(commission) + abs(slippage)
    proxy_delta_loss_abs = abs(min(proxy_delta_pnl, 0.0))
    unsplit_loss_abs = abs(min(unsplit_equity_delta_pnl, 0.0))

    holding_loss_share_pct = holding_loss_abs / loss_denominator * 100.0
    trading_loss_share_pct = trading_loss_abs / loss_denominator * 100.0
    cost_loss_share_pct = cost_loss_abs / loss_denominator * 100.0
    proxy_delta_loss_share_pct = proxy_delta_loss_abs / loss_denominator * 100.0
    unsplit_loss_share_pct = unsplit_loss_abs / loss_denominator * 100.0

    broker10_max = float(_numeric(window_curve, "broker10_margin_to_equity_pct", 0.0).max()) if not window_curve.empty else 0.0
    active_products_max = float(_numeric(window_curve, "c3_active_products", 0.0).max()) if not window_curve.empty else 0.0
    drawdown_min = float(_numeric(window_curve, "drawdown_pct", 0.0).min()) if not window_curve.empty else 0.0
    trade_count = float(_numeric(window_curve, "trade_count", 0.0).sum()) if not window_curve.empty else 0.0

    dominant = _dominant_from_shares(
        holding_loss_share_pct=holding_loss_share_pct,
        trading_loss_share_pct=trading_loss_share_pct,
        cost_loss_share_pct=cost_loss_share_pct,
        proxy_delta_loss_share_pct=proxy_delta_loss_share_pct,
        unsplit_loss_share_pct=unsplit_loss_share_pct,
    )

    return {
        "selected_rank": int(selected_rank),
        "window_id": f"{int(selected_rank):03d}_{source_start_month}_{_date_text(start_date)}_{_date_text(end_date)}",
        "source_start_month": source_start_month,
        "start_date": _date_text(start_date),
        "end_date": _date_text(end_date),
        "period_calendar_days": int((end_date - start_date).days),
        "period_trading_days": int(len(window_curve)),
        "oracle_winner": oracle_winner or attribution_kind,
        "attribution_kind": attribution_kind,
        "split_precision": split_precision,
        "start_equity": start_equity,
        "end_equity": end_equity,
        "equity_change": equity_change,
        "net_pnl": net_pnl,
        "holding_pnl": holding_pnl,
        "trading_pnl": trading_pnl,
        "commission": commission,
        "slippage": slippage,
        "proxy_delta_pnl": proxy_delta_pnl,
        "unsplit_equity_delta_pnl": unsplit_equity_delta_pnl,
        "equity_change_vs_net_pnl_abs_diff": abs(equity_change - net_pnl) if pd.notna(equity_change) else np.nan,
        "holding_loss_share_pct": holding_loss_share_pct,
        "trading_loss_share_pct": trading_loss_share_pct,
        "cost_loss_share_pct": cost_loss_share_pct,
        "proxy_delta_loss_share_pct": proxy_delta_loss_share_pct,
        "unsplit_loss_share_pct": unsplit_loss_share_pct,
        "dominant_loss_driver": dominant,
        "broker10_margin_to_equity_max_pct": broker10_max,
        "broker10_pressure_flag": int(broker10_max >= 80.0),
        "active_products_max": active_products_max,
        "active4_pressure_flag": int(active_products_max >= 4.0),
        "window_min_drawdown_pct": drawdown_min,
        "trade_count": trade_count,
        "base_return_pct": float(window.get("base_return_pct", np.nan)),
        "stage052_return_pct": float(window.get("stage052_return_pct", np.nan)),
        "stage074_return_pct": float(window.get("stage074_return_pct", np.nan)),
        "oracle_return_pct": float(window.get("oracle_return_pct", np.nan)),
    }


def _oracle_winner(row: pd.Series) -> str:
    stage052 = float(row.get("stage052_return_pct", np.nan))
    stage074 = float(row.get("stage074_return_pct", np.nan))
    if np.isfinite(stage052) and np.isfinite(stage074) and stage052 >= stage074:
        return "stage052_proxy"
    return "stage074_ramp"


def run_attribution(
    worst_windows: pd.DataFrame,
    stage052_curves: pd.DataFrame,
    stage074_panel: pd.DataFrame,
    *,
    top_n: int = TOP_N_WINDOWS,
) -> pd.DataFrame:
    worst = worst_windows.copy()
    worst["start_date"] = pd.to_datetime(worst["start_date"], errors="coerce").dt.normalize()
    worst["end_date"] = pd.to_datetime(worst["end_date"], errors="coerce").dt.normalize()
    worst["oracle_return_pct"] = pd.to_numeric(worst["oracle_return_pct"], errors="coerce")
    worst = worst.dropna(subset=["source_start_month", "start_date", "end_date", "oracle_return_pct"])
    selected = worst.sort_values("oracle_return_pct").head(int(top_n)).reset_index(drop=True)

    curves052 = _prepare_curve(stage052_curves)
    panel074 = _prepare_curve(stage074_panel)
    rows: list[dict[str, Any]] = []
    for index, window in selected.iterrows():
        rank = index + 1
        winner = _oracle_winner(window)
        source = str(window["source_start_month"])
        if winner == "stage052_proxy":
            source_curve = curves052[curves052["requested_start_month"].astype(str).eq(source)].copy()
            rows.append(
                attribute_window(
                    source_curve,
                    window,
                    rank,
                    equity_column="stage052_account_equity",
                    delta_column="stage052_daily_delta",
                    attribution_kind="stage052_base_pnl_plus_contract_oi_delta",
                    oracle_winner=winner,
                )
            )
        else:
            source_curve = panel074[
                panel074["requested_start_month"].astype(str).eq(source)
                & panel074["variant"].astype(str).eq("full_market_ai_top8_and_active_positions_lt3")
            ].copy()
            rows.append(
                attribute_window(
                    source_curve,
                    window,
                    rank,
                    equity_column="equity",
                    attribution_kind="stage074_start_reset_ramp_equity_only",
                    oracle_winner=winner,
                    use_start_reset_ramp=True,
                )
            )
    return pd.DataFrame(rows)


def summarize_attributions(attrs: pd.DataFrame) -> dict[str, Any]:
    if attrs.empty:
        return {
            "window_count": 0,
            "net_pnl": 0.0,
            "dominant_loss_driver": "missing_attribution",
        }

    data = attrs.copy()
    for column in [
        "net_pnl",
        "holding_pnl",
        "trading_pnl",
        "commission",
        "slippage",
        "proxy_delta_pnl",
        "unsplit_equity_delta_pnl",
    ]:
        data[column] = _numeric(data, column, 0.0)

    net_pnl = float(data["net_pnl"].sum())
    loss_denominator = float(data["net_pnl"].clip(upper=0.0).abs().sum())
    if loss_denominator <= 0:
        loss_denominator = abs(net_pnl) if net_pnl else 1.0

    holding_loss_abs = float(data["holding_pnl"].clip(upper=0.0).abs().sum())
    trading_loss_abs = float(data["trading_pnl"].clip(upper=0.0).abs().sum())
    cost_loss_abs = float(data["commission"].abs().sum() + data["slippage"].abs().sum())
    proxy_delta_loss_abs = float(data["proxy_delta_pnl"].clip(upper=0.0).abs().sum())
    unsplit_loss_abs = float(data["unsplit_equity_delta_pnl"].clip(upper=0.0).abs().sum())

    holding_loss_share_pct = holding_loss_abs / loss_denominator * 100.0
    trading_loss_share_pct = trading_loss_abs / loss_denominator * 100.0
    cost_loss_share_pct = cost_loss_abs / loss_denominator * 100.0
    proxy_delta_loss_share_pct = proxy_delta_loss_abs / loss_denominator * 100.0
    unsplit_loss_share_pct = unsplit_loss_abs / loss_denominator * 100.0

    dominant = _dominant_from_shares(
        holding_loss_share_pct=holding_loss_share_pct,
        trading_loss_share_pct=trading_loss_share_pct,
        cost_loss_share_pct=cost_loss_share_pct,
        proxy_delta_loss_share_pct=proxy_delta_loss_share_pct,
        unsplit_loss_share_pct=unsplit_loss_share_pct,
    )
    window_count = int(len(data))
    stage074_ramp_window_count = int(data.get("oracle_winner", pd.Series("", index=data.index)).astype(str).eq("stage074_ramp").sum())
    stage052_proxy_window_count = int(data.get("oracle_winner", pd.Series("", index=data.index)).astype(str).eq("stage052_proxy").sum())
    broker10_count = int(_numeric(data, "broker10_pressure_flag", 0.0).sum())
    active4_count = int(_numeric(data, "active4_pressure_flag", 0.0).sum())

    return {
        "window_count": window_count,
        "net_pnl": net_pnl,
        "holding_pnl": float(data["holding_pnl"].sum()),
        "trading_pnl": float(data["trading_pnl"].sum()),
        "commission": float(data["commission"].sum()),
        "slippage": float(data["slippage"].sum()),
        "proxy_delta_pnl": float(data["proxy_delta_pnl"].sum()),
        "unsplit_equity_delta_pnl": float(data["unsplit_equity_delta_pnl"].sum()),
        "holding_loss_share_pct": holding_loss_share_pct,
        "trading_loss_share_pct": trading_loss_share_pct,
        "cost_loss_share_pct": cost_loss_share_pct,
        "proxy_delta_loss_share_pct": proxy_delta_loss_share_pct,
        "unsplit_loss_share_pct": unsplit_loss_share_pct,
        "dominant_loss_driver": dominant,
        "stage074_ramp_window_count": stage074_ramp_window_count,
        "stage052_proxy_window_count": stage052_proxy_window_count,
        "stage074_ramp_window_rate_pct": stage074_ramp_window_count / window_count * 100.0 if window_count else np.nan,
        "stage052_proxy_window_rate_pct": stage052_proxy_window_count / window_count * 100.0 if window_count else np.nan,
        "broker10_pressure_window_count": broker10_count,
        "active4_pressure_window_count": active4_count,
        "oracle_min_return_pct": float(_numeric(data, "oracle_return_pct", np.nan).min()),
        "source_count": int(data.get("source_start_month", pd.Series(dtype=str)).astype(str).nunique()),
    }


def make_decision(summary: dict[str, Any]) -> dict[str, Any]:
    window_count = int(summary.get("window_count", 0) or 0)
    if window_count == 0:
        return {
            "decision": "stage004_missing_attribution",
            "window_count": 0,
            "position_replay_recommended": 0,
        }

    unsplit_share = float(summary.get("unsplit_loss_share_pct", 0.0) or 0.0)
    stage074_rate = float(summary.get("stage074_ramp_window_rate_pct", 0.0) or 0.0)
    holding_share = float(summary.get("holding_loss_share_pct", 0.0) or 0.0)
    trading_share = float(summary.get("trading_loss_share_pct", 0.0) or 0.0)

    if unsplit_share >= 50.0 or stage074_rate >= 50.0:
        decision = "stage004_stage074_ramp_residual_dominant_need_true_position_replay"
        position_replay_recommended = 1
    elif holding_share >= 70.0:
        decision = "stage004_holding_path_dominant_need_position_replay"
        position_replay_recommended = 1
    elif trading_share >= 70.0:
        decision = "stage004_trading_realized_loss_dominant_need_entry_signal_audit"
        position_replay_recommended = 0
    else:
        decision = "stage004_mixed_path_need_deeper_attribution"
        position_replay_recommended = 1

    return {
        "decision": decision,
        "position_replay_recommended": position_replay_recommended,
        "window_count": window_count,
        "net_pnl": summary.get("net_pnl"),
        "holding_loss_share_pct": holding_share,
        "trading_loss_share_pct": trading_share,
        "cost_loss_share_pct": summary.get("cost_loss_share_pct"),
        "proxy_delta_loss_share_pct": summary.get("proxy_delta_loss_share_pct"),
        "unsplit_loss_share_pct": unsplit_share,
        "stage074_ramp_window_count": summary.get("stage074_ramp_window_count", 0),
        "stage052_proxy_window_count": summary.get("stage052_proxy_window_count", 0),
        "stage074_ramp_window_rate_pct": stage074_rate,
        "broker10_pressure_window_count": summary.get("broker10_pressure_window_count", 0),
        "active4_pressure_window_count": summary.get("active4_pressure_window_count", 0),
        "oracle_min_return_pct": summary.get("oracle_min_return_pct"),
    }


def _group_summary(attrs: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    if attrs.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for group_key, group in attrs.groupby(keys, dropna=False, sort=True):
        summary = summarize_attributions(group)
        if not isinstance(group_key, tuple):
            group_key = (group_key,)
        row = {key: value for key, value in zip(keys, group_key)}
        row.update(summary)
        rows.append(row)
    return pd.DataFrame(rows)


def _plot_loss_drivers(summary: dict[str, Any]) -> None:
    labels = ["holding", "trading", "cost", "proxy_delta", "unsplit"]
    values = [
        float(summary.get("holding_loss_share_pct", 0.0) or 0.0),
        float(summary.get("trading_loss_share_pct", 0.0) or 0.0),
        float(summary.get("cost_loss_share_pct", 0.0) or 0.0),
        float(summary.get("proxy_delta_loss_share_pct", 0.0) or 0.0),
        float(summary.get("unsplit_loss_share_pct", 0.0) or 0.0),
    ]
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.bar(labels, values, color=["#4f6d7a", "#59a14f", "#f28e2b", "#8e6c8a", "#d1495b"])
    ax.set_ylabel("Share of selected residual-window loss (%)")
    ax.set_title("Stage004 oracle residual path attribution")
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


def _write_report(attrs: pd.DataFrame, source_summary: pd.DataFrame, month_summary: pd.DataFrame, summary: dict[str, Any], decision: dict[str, Any]) -> None:
    top_cols = [
        "selected_rank",
        "source_start_month",
        "start_date",
        "end_date",
        "oracle_winner",
        "oracle_return_pct",
        "net_pnl",
        "holding_loss_share_pct",
        "trading_loss_share_pct",
        "unsplit_loss_share_pct",
        "dominant_loss_driver",
        "split_precision",
    ]
    source_cols = [
        "source_start_month",
        "window_count",
        "stage074_ramp_window_count",
        "stage052_proxy_window_count",
        "oracle_min_return_pct",
        "holding_loss_share_pct",
        "trading_loss_share_pct",
        "unsplit_loss_share_pct",
        "dominant_loss_driver",
    ]
    month_cols = [
        "start_year_month",
        "end_year_month",
        "window_count",
        "stage074_ramp_window_count",
        "oracle_min_return_pct",
        "holding_loss_share_pct",
        "trading_loss_share_pct",
        "unsplit_loss_share_pct",
        "dominant_loss_driver",
    ]
    lines = [
        "# Stage004 oracle 剩余亏损窗口路径归因",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：day",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 阶段性质：只读归因，不新增交易规则，不修改官方实盘/CTP/邮件/launchd",
        "- 是否重要突破：否",
        "- 是否触发A/B：否",
        "",
        "## 外部调研与判断",
        "",
        "- Trend-following drawdown 资料把 whipsaw / 反复反转视为趋势系统常见亏损来源。",
        "- PnL explain 资料强调先把组合损益拆到路径、市场因子、成本或模型残差，再决定修哪一层。",
        "- GitHub 上 pysystemtrade 等期货趋势框架也体现了先隔离数据、规则、仓位和执行口径再优化的工程方式。",
        "- 我的判断：本阶段不该继续扫 OI/ramp 参数，应先确认剩余窗口是持仓路径亏损、开平仓实现亏损、成本压力，还是 Stage074 只有资金曲线导致需要重放持仓明细。",
        "",
        "## 关键结果",
        "",
        f"- 决策：`{decision['decision']}`。",
        f"- 归因窗口数：`{summary['window_count']}`。",
        f"- oracle 最差收益：`{summary.get('oracle_min_return_pct'):.4f}%`。",
        f"- Stage074 ramp 胜出窗口：`{summary.get('stage074_ramp_window_count', 0)}`，占比 `{summary.get('stage074_ramp_window_rate_pct', 0.0):.4f}%`。",
        f"- Stage052 proxy 胜出窗口：`{summary.get('stage052_proxy_window_count', 0)}`。",
        f"- holding loss share：`{summary.get('holding_loss_share_pct', 0.0):.4f}%`。",
        f"- trading loss share：`{summary.get('trading_loss_share_pct', 0.0):.4f}%`。",
        f"- cost loss share：`{summary.get('cost_loss_share_pct', 0.0):.4f}%`。",
        f"- proxy delta loss share：`{summary.get('proxy_delta_loss_share_pct', 0.0):.4f}%`。",
        f"- unsplit equity-delta loss share：`{summary.get('unsplit_loss_share_pct', 0.0):.4f}%`。",
        f"- broker10 压力窗口：`{summary.get('broker10_pressure_window_count', 0)}`；active>=4 压力窗口：`{summary.get('active4_pressure_window_count', 0)}`。",
        "",
        "## 最差窗口样例",
        "",
        _md_table(attrs[[column for column in top_cols if column in attrs.columns]], max_rows=25),
        "",
        "## Source 汇总",
        "",
        _md_table(source_summary[[column for column in source_cols if column in source_summary.columns]].sort_values("oracle_min_return_pct"), max_rows=20),
        "",
        "## 月份汇总",
        "",
        _md_table(month_summary[[column for column in month_cols if column in month_summary.columns]].sort_values("oracle_min_return_pct"), max_rows=20),
        "",
        "## 结论",
        "",
        "- Stage074 residual 占比高时，当前只有资金曲线，不能精确拆成 holding/trading；必须做真实 position replay 或重跑带 positions 的 Stage074 engine。",
        "- 如果未来 replay 证明确实是 holding PnL 主导，再研究持仓路径/退出结构；如果 trading PnL 主导，再回到入场信号质量。",
        "- 这一步的价值是避免把缺失明细误当作 AI/选品或 OI 参数问题。",
        "",
        "## 过拟合反思",
        "",
        "- 运行前判断：不过拟合，本阶段只做剩余亏损窗口归因，不产生可交易参数。",
        "- 运行后判断：不过拟合。",
        "- 原因：没有优化阈值，也没有用结果反推新规则，只决定下一层归因口径。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前判断：有价值。",
        "- 运行后判断：有价值。",
        "- 原因：Stage003 已证明简单组合上界仍失败，Stage004 能指出下一步应补真实持仓重放，而不是继续浅层扫参。",
        "",
        "## 输出文件",
        "",
        f"- window_attribution：`{WINDOW_ATTRIBUTION_PATH}`",
        f"- source_summary：`{SOURCE_SUMMARY_PATH}`",
        f"- month_summary：`{MONTH_SUMMARY_PATH}`",
        f"- chart：`{CHART_PATH}`",
        f"- decision：`{DECISION_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    worst = _read_csv(STAGE003_ORACLE_WORST_PATH)
    curves052 = _read_csv(STAGE052_CURVES_PATH)
    panel074 = _read_csv(STAGE074_PANEL_PATH)
    attrs = run_attribution(worst, curves052, panel074, top_n=TOP_N_WINDOWS)
    if not attrs.empty:
        attrs["start_year_month"] = pd.to_datetime(attrs["start_date"], errors="coerce").dt.strftime("%Y-%m")
        attrs["end_year_month"] = pd.to_datetime(attrs["end_date"], errors="coerce").dt.strftime("%Y-%m")
    summary = summarize_attributions(attrs)
    decision = make_decision(summary)
    source_summary = _group_summary(attrs, ["source_start_month"])
    month_summary = _group_summary(attrs, ["start_year_month", "end_year_month"])

    attrs.to_csv(WINDOW_ATTRIBUTION_PATH, index=False, encoding="utf-8-sig")
    source_summary.to_csv(SOURCE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    month_summary.to_csv(MONTH_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    _plot_loss_drivers(summary)
    _write_report(attrs, source_summary, month_summary, summary, decision)
    DECISION_PATH.write_text(
        json.dumps(_json_safe({"summary": summary, "decision": decision}), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    return decision


if __name__ == "__main__":
    main()
