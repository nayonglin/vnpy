from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage146_portfolio_tail_risk_monitor_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage146_portfolio_tail_risk_monitor"
FORMAL_PREFIX: str = "qmt_roll_official_stage78_defensive_formal"
STAGE145_TAG: str = "stage145_extreme_loss_event_ledger_v1"
STAGE145_PREFIX: str = "qmt_roll_stage145_extreme_loss_event_ledger"

DAILY_PATH: Path = OUTPUT_DIR / f"{FORMAL_PREFIX}_daily.csv"
SUMMARY_PATH: Path = OUTPUT_DIR / "qmt_roll_official_stage78_defensive_summary.json"
LEDGER_PATH: Path = OUTPUT_DIR / f"{STAGE145_PREFIX}_ledger_{STAGE145_TAG}.csv"

WINDOW_STATE_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_state_{MODEL_TAG}.csv"
CURRENT_STATUS_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_current_status_{MODEL_TAG}.csv"
RECENT_TAIL_EVENTS_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_recent_tail_events_{MODEL_TAG}.csv"
WORST_WINDOWS_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_worst_windows_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


PRODUCT_FAMILY: dict[str, str] = {
    "AP": "agri_soft",
    "CF": "agri_soft",
    "OI": "agri_soft",
    "au": "metals",
    "cu": "metals",
    "rb": "black_chain",
    "hc": "black_chain",
    "SM": "black_chain",
    "jm": "black_chain",
    "fu": "energy_oil",
    "MA": "chemical",
    "SA": "chemical",
    "FG": "chemical",
    "SH": "chemical",
    "sp": "chemical",
    "ru": "rubber_chemical",
    "lh": "livestock",
    "lc": "new_energy",
    "si": "new_energy",
}


def _require(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"missing required artifact: {path}")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or math.isinf(result):
        return default
    return result


def _fmt(value: Any, digits: int = 4) -> str:
    if isinstance(value, (int, np.integer)):
        return f"{int(value):,}"
    numeric = _safe_float(value, default=float("nan"))
    if math.isnan(numeric):
        return str(value)
    if abs(numeric) >= 1000:
        return f"{numeric:,.0f}"
    return f"{numeric:.{digits}f}"


def _to_markdown_table(df: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 20) -> str:
    if df.empty:
        return "_No rows._"
    view = df.copy()
    if columns is not None:
        view = view.loc[:, [column for column in columns if column in view.columns]]
    view = view.head(max_rows).copy()
    for column in view.columns:
        if column in {"date", "close_date", "open_date"}:
            view[column] = pd.to_datetime(view[column], errors="coerce").dt.strftime("%Y-%m-%d")
        elif pd.api.types.is_numeric_dtype(view[column]):
            view[column] = view[column].map(_fmt)
    return "\n".join(
        [
            "| " + " | ".join(view.columns) + " |",
            "| " + " | ".join(["---"] * len(view.columns)) + " |",
            *["| " + " | ".join(map(str, row)) + " |" for row in view.to_numpy()],
        ]
    )


def _numeric(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for column in columns:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    return frame


def _read_csv(path: Path) -> pd.DataFrame:
    _require(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def _normalize_date(frame: pd.DataFrame, column: str = "date") -> pd.DataFrame:
    frame[column] = pd.to_datetime(frame[column], errors="coerce").dt.tz_localize(None).dt.normalize()
    return frame.dropna(subset=[column]).reset_index(drop=True)


def _product_prefix(product_vt_symbol: Any) -> str:
    symbol = str(product_vt_symbol).split(".", 1)[0]
    return "".join(ch for ch in symbol if ch.isalpha())


def _load_inputs() -> dict[str, Any]:
    for path in (DAILY_PATH, SUMMARY_PATH, LEDGER_PATH):
        _require(path)
    daily = _normalize_date(_read_csv(DAILY_PATH)).sort_values("date").reset_index(drop=True)
    _numeric(daily, ["net_pnl", "balance", "ddpercent", "trade_count", "slippage"])

    ledger = _read_csv(LEDGER_PATH)
    ledger["open_date"] = pd.to_datetime(ledger["open_date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    ledger["close_date"] = pd.to_datetime(ledger["close_date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    ledger = ledger.dropna(subset=["close_date"]).reset_index(drop=True)
    _numeric(ledger, ["lifecycle_net_pnl", "loss_percentile_low", "pnl_to_entry_risk"])
    ledger["product_prefix"] = ledger["product_vt_symbol"].map(_product_prefix)
    ledger["product_family"] = ledger["product_prefix"].map(PRODUCT_FAMILY).fillna("other")
    ledger["is_tail_5pct"] = ledger["tail_bucket"].isin(["catastrophic_bottom_1pct", "severe_bottom_5pct"])
    ledger["is_bottom_1pct"] = ledger["tail_bucket"].eq("catastrophic_bottom_1pct")

    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    return {"daily": daily, "ledger": ledger, "summary": summary}


def _dominant_share(frame: pd.DataFrame, column: str) -> tuple[str, float, int]:
    if frame.empty or column not in frame.columns:
        return "", 0.0, 0
    counts = frame[column].fillna("").astype(str).value_counts()
    if counts.empty:
        return "", 0.0, 0
    top_name = str(counts.index[0])
    top_count = int(counts.iloc[0])
    return top_name, float(top_count / len(frame)), top_count


def _window_events(ledger: pd.DataFrame, dates: list[pd.Timestamp]) -> pd.DataFrame:
    if not dates:
        return ledger.iloc[0:0].copy()
    date_set = set(dates)
    return ledger[ledger["close_date"].isin(date_set) & ledger["is_tail_5pct"]].copy()


def _build_window_state(daily: pd.DataFrame, ledger: pd.DataFrame) -> pd.DataFrame:
    dates = list(daily["date"])
    rows: list[dict[str, Any]] = []
    for idx, date in enumerate(dates):
        dates20 = dates[max(0, idx - 19) : idx + 1]
        dates63 = dates[max(0, idx - 62) : idx + 1]
        tail20 = _window_events(ledger, dates20)
        tail63 = _window_events(ledger, dates63)
        dir20, dir20_share, dir20_count = _dominant_share(tail20, "direction")
        family20, family20_share, family20_count = _dominant_share(tail20, "product_family")
        exit20, exit20_share, exit20_count = _dominant_share(tail20, "exit_reason")
        dir63, dir63_share, dir63_count = _dominant_share(tail63, "direction")
        family63, family63_share, family63_count = _dominant_share(tail63, "product_family")
        exit63, exit63_share, exit63_count = _dominant_share(tail63, "exit_reason")
        rows.append(
            {
                "date": date,
                "tail20_count": int(len(tail20)),
                "tail20_bottom1_count": int(tail20["is_bottom_1pct"].sum()) if not tail20.empty else 0,
                "tail20_loss_abs_sum": float(-tail20["lifecycle_net_pnl"].sum()) if not tail20.empty else 0.0,
                "tail20_dominant_direction": dir20,
                "tail20_dominant_direction_share": dir20_share,
                "tail20_dominant_direction_count": dir20_count,
                "tail20_dominant_family": family20,
                "tail20_dominant_family_share": family20_share,
                "tail20_dominant_family_count": family20_count,
                "tail20_dominant_exit_reason": exit20,
                "tail20_dominant_exit_reason_share": exit20_share,
                "tail20_dominant_exit_reason_count": exit20_count,
                "tail63_count": int(len(tail63)),
                "tail63_bottom1_count": int(tail63["is_bottom_1pct"].sum()) if not tail63.empty else 0,
                "tail63_loss_abs_sum": float(-tail63["lifecycle_net_pnl"].sum()) if not tail63.empty else 0.0,
                "tail63_dominant_direction": dir63,
                "tail63_dominant_direction_share": dir63_share,
                "tail63_dominant_direction_count": dir63_count,
                "tail63_dominant_family": family63,
                "tail63_dominant_family_share": family63_share,
                "tail63_dominant_family_count": family63_count,
                "tail63_dominant_exit_reason": exit63,
                "tail63_dominant_exit_reason_share": exit63_share,
                "tail63_dominant_exit_reason_count": exit63_count,
            }
        )
    state = pd.DataFrame(rows)
    state["tail20_direction_cluster"] = (state["tail20_count"] >= 2) & (state["tail20_dominant_direction_share"] >= 2 / 3)
    state["tail20_family_cluster"] = (state["tail20_count"] >= 2) & (state["tail20_dominant_family_share"] >= 2 / 3)
    state["tail20_exit_cluster"] = (state["tail20_count"] >= 2) & (state["tail20_dominant_exit_reason_share"] >= 2 / 3)
    state["tail63_direction_cluster"] = (state["tail63_count"] >= 2) & (state["tail63_dominant_direction_share"] >= 2 / 3)
    state["tail63_family_cluster"] = (state["tail63_count"] >= 2) & (state["tail63_dominant_family_share"] >= 2 / 3)
    state["tail63_exit_cluster"] = (state["tail63_count"] >= 2) & (state["tail63_dominant_exit_reason_share"] >= 2 / 3)
    return state


def _status_high_is_bad(latest: float, watch: float, alert: float, severe: float) -> str:
    if latest > severe:
        return "severe"
    if latest > alert:
        return "alert"
    if latest > watch:
        return "watch"
    return "normal"


def _build_current_status(state: pd.DataFrame) -> pd.DataFrame:
    metrics = [
        "tail20_count",
        "tail20_bottom1_count",
        "tail20_loss_abs_sum",
        "tail63_count",
        "tail63_bottom1_count",
        "tail63_loss_abs_sum",
        "tail20_dominant_direction_share",
        "tail20_dominant_family_share",
        "tail20_dominant_exit_reason_share",
        "tail63_dominant_direction_share",
        "tail63_dominant_family_share",
        "tail63_dominant_exit_reason_share",
    ]
    latest = state.iloc[-1]
    rows: list[dict[str, Any]] = []
    for metric in metrics:
        series = pd.to_numeric(state[metric], errors="coerce").fillna(0.0)
        watch = float(np.percentile(series, 90))
        alert = float(np.percentile(series, 95))
        severe = float(np.percentile(series, 99))
        latest_value = float(latest[metric])
        rows.append(
            {
                "metric": metric,
                "latest_value": latest_value,
                "watch_threshold": watch,
                "alert_threshold": alert,
                "severe_threshold": severe,
                "status": _status_high_is_bad(latest_value, watch, alert, severe),
            }
        )
    cluster_items = [
        "tail20_direction_cluster",
        "tail20_family_cluster",
        "tail20_exit_cluster",
        "tail63_direction_cluster",
        "tail63_family_cluster",
        "tail63_exit_cluster",
    ]
    for metric in cluster_items:
        rows.append(
            {
                "metric": metric,
                "latest_value": int(bool(latest[metric])),
                "watch_threshold": 1,
                "alert_threshold": 1,
                "severe_threshold": 1,
                "status": "watch" if bool(latest[metric]) else "normal",
            }
        )
    return pd.DataFrame(rows)


def _build_recent_tail_events(daily: pd.DataFrame, ledger: pd.DataFrame) -> pd.DataFrame:
    dates63 = set(daily["date"].tail(63))
    return (
        ledger[ledger["close_date"].isin(dates63) & ledger["is_tail_5pct"]]
        .sort_values("close_date", ascending=False)
        .reset_index(drop=True)
    )


def _build_worst_windows(state: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "date",
        "tail20_count",
        "tail20_loss_abs_sum",
        "tail20_dominant_family",
        "tail20_dominant_family_share",
        "tail63_count",
        "tail63_loss_abs_sum",
        "tail63_dominant_family",
        "tail63_dominant_family_share",
    ]
    return (
        state.sort_values(["tail20_count", "tail20_loss_abs_sum", "tail63_count"], ascending=[False, False, False])
        .loc[:, cols]
        .head(30)
        .reset_index(drop=True)
    )


def _build_summary_payload(
    inputs: dict[str, Any],
    state: pd.DataFrame,
    current_status: pd.DataFrame,
    recent_tail_events: pd.DataFrame,
) -> dict[str, Any]:
    summary = inputs["summary"]
    stage78_full = summary["reference_metrics"]["full_2020_2026"]
    latest = state.iloc[-1]
    status_counts = current_status["status"].value_counts().to_dict()
    severe_count = int(status_counts.get("severe", 0))
    alert_count = int(status_counts.get("alert", 0))
    decision = "monitor_only_keep_stage78"
    if severe_count:
        decision = "pause_new_research_tail_risk_review"
    elif alert_count:
        decision = "review_tail_risk_keep_stage78"
    return {
        "model_tag": MODEL_TAG,
        "is_strategy_change": False,
        "version_ab_skill_triggered": False,
        "stage78_reference": stage78_full,
        "latest_date": latest["date"].date().isoformat(),
        "tail20_count": int(latest["tail20_count"]),
        "tail20_loss_abs_sum": float(latest["tail20_loss_abs_sum"]),
        "tail63_count": int(latest["tail63_count"]),
        "tail63_loss_abs_sum": float(latest["tail63_loss_abs_sum"]),
        "tail63_dominant_family": latest["tail63_dominant_family"],
        "tail63_dominant_family_share": float(latest["tail63_dominant_family_share"]),
        "tail63_dominant_exit_reason": latest["tail63_dominant_exit_reason"],
        "tail63_dominant_exit_reason_share": float(latest["tail63_dominant_exit_reason_share"]),
        "recent_63d_tail_products": recent_tail_events["product_vt_symbol"].tolist(),
        "status_counts": status_counts,
        "decision": decision,
        "anti_overfit_boundary": (
            "This monitor only turns full lifecycle tail events into alerts. It must not directly change "
            "position sizing, product pool, stop rules, or profit-giveback exits."
        ),
    }


def _write_report(
    payload: dict[str, Any],
    state: pd.DataFrame,
    current_status: pd.DataFrame,
    recent_tail_events: pd.DataFrame,
    worst_windows: pd.DataFrame,
) -> None:
    stage78 = payload["stage78_reference"]
    status_cols = ["metric", "latest_value", "watch_threshold", "alert_threshold", "severe_threshold", "status"]
    event_cols = [
        "product_vt_symbol",
        "product_family",
        "contract_vt_symbol",
        "direction",
        "open_date",
        "close_date",
        "exit_reason",
        "lifecycle_net_pnl",
        "tail_bucket",
        "entry_signal",
    ]
    latest_cols = [
        "date",
        "tail20_count",
        "tail20_loss_abs_sum",
        "tail20_dominant_family",
        "tail20_dominant_family_share",
        "tail20_dominant_exit_reason",
        "tail63_count",
        "tail63_loss_abs_sum",
        "tail63_dominant_family",
        "tail63_dominant_family_share",
        "tail63_dominant_exit_reason",
        "tail63_dominant_exit_reason_share",
    ]
    report = f"""# Stage146 Stage78组合层尾部风险监控

## 结论
- 本阶段不是策略版本，不改Stage78，不触发A/B技能。
- 当前决策：`{payload["decision"]}`。
- 过拟合判断：否。监控阈值来自全历史生命周期尾部事件分布，只做告警，不改交易参数、不筛品种。
- 是否有价值继续：是。Stage145说明尾部风险是跨品种组合问题，本阶段把它转成可跟踪的20/63日组合层状态。

## Stage78 正式基准
- 期末权益：{_fmt(stage78.get("end_balance"))}
- 总收益：{_fmt(stage78.get("total_return_pct"))}%
- 最大回撤：{_fmt(stage78.get("max_dd_percent"))}%
- Sharpe：{_fmt(stage78.get("sharpe_ratio"))}
- 总滑点：{_fmt(stage78.get("total_slippage"))}
- 总交易次数：{_fmt(stage78.get("total_trade_count"))}

## 当前尾部状态
- 最新日期：{payload["latest_date"]}
- 近20日Bottom 5%尾部事件数：{payload["tail20_count"]}
- 近20日尾部亏损绝对值合计：{_fmt(payload["tail20_loss_abs_sum"])}
- 近63日Bottom 5%尾部事件数：{payload["tail63_count"]}
- 近63日尾部亏损绝对值合计：{_fmt(payload["tail63_loss_abs_sum"])}
- 近63日主导板块：`{payload["tail63_dominant_family"]}`，占比`{_fmt(payload["tail63_dominant_family_share"])}`
- 近63日主导退出原因：`{payload["tail63_dominant_exit_reason"]}`，占比`{_fmt(payload["tail63_dominant_exit_reason_share"])}`
- 状态计数：{json.dumps(payload["status_counts"], ensure_ascii=False)}

## 当前监控项
{_to_markdown_table(current_status, status_cols, max_rows=30)}

## 最新窗口状态
{_to_markdown_table(state.tail(10), latest_cols, max_rows=10)}

## 近63日尾部事件
{_to_markdown_table(recent_tail_events, event_cols, max_rows=20)}

## 历史最拥挤尾部窗口
{_to_markdown_table(worst_windows, max_rows=20)}

## 使用边界
- 本监控只回答“尾部事件是否聚集”，不直接下调仓位、不改变品种池、不改止损。
- 如果进入`alert/severe`，优先进入人工复盘和暂停新研究；只有跨周期反复验证后，才讨论组合层风控。
- 禁止把当前监控项转成单品种黑名单或短窗口参数补丁。
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def main() -> None:
    inputs = _load_inputs()
    state = _build_window_state(inputs["daily"], inputs["ledger"])
    current_status = _build_current_status(state)
    recent_tail_events = _build_recent_tail_events(inputs["daily"], inputs["ledger"])
    worst_windows = _build_worst_windows(state)
    payload = _build_summary_payload(inputs, state, current_status, recent_tail_events)

    state.to_csv(WINDOW_STATE_PATH, index=False, encoding="utf-8-sig")
    current_status.to_csv(CURRENT_STATUS_PATH, index=False, encoding="utf-8-sig")
    recent_tail_events.to_csv(RECENT_TAIL_EVENTS_PATH, index=False, encoding="utf-8-sig")
    worst_windows.to_csv(WORST_WINDOWS_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    _write_report(payload, state, current_status, recent_tail_events, worst_windows)

    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    print(f"wrote: {REPORT_PATH}")


if __name__ == "__main__":
    main()
