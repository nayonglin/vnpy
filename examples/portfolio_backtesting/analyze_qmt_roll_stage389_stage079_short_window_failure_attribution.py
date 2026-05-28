from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
MODEL_TAG = "stage389_stage079_short_window_failure_attribution_v1"
OUTPUT_PREFIX = "qmt_roll_stage389_stage079_short_window_failure_attribution"

STAGE383_DAILY_PATH = OUTPUT_DIR / "qmt_roll_stage383_three_version_deep_audit_daily_stage383_three_version_deep_audit_v1.csv"
PRODUCT_DAILY_PATH = OUTPUT_DIR / "qmt_roll_stage360_c3_product_group_ledger_ablation_product_daily_stage360_c3_product_group_ledger_ablation_v1.csv"

ACCOUNT_CAPITAL = 615_000.0
TARGET_VARIANT = "stage079"
HORIZONS = (90, 180)

WINDOW_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_worst_windows_{MODEL_TAG}.csv"
PRODUCT_ATTR_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_attribution_{MODEL_TAG}.csv"
LOSS_DAY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_loss_days_{MODEL_TAG}.csv"
STATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_state_context_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def _md_table(frame: pd.DataFrame, max_rows: int = 20) -> str:
    if frame.empty:
        return "无数据。"
    view = frame.head(max_rows).copy()
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: f"{x:.4f}" if pd.notna(x) else "")
    return view.to_markdown(index=False)


def _load_stage079() -> pd.DataFrame:
    frame = pd.read_csv(STAGE383_DAILY_PATH, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["equity"] = pd.to_numeric(frame["equity"], errors="coerce")
    curves = frame.dropna(subset=["date", "variant", "equity"]).pivot(index="date", columns="variant", values="equity").sort_index()
    calendar = pd.date_range(curves.index.min(), curves.index.max(), freq="D")
    curves = curves.reindex(calendar).ffill().dropna(subset=["c3", TARGET_VARIANT])
    curves["stage079_ret"] = curves[TARGET_VARIANT].pct_change().fillna(0.0)
    curves["c3_ret20"] = curves["c3"].pct_change(20)
    curves["c3_ret60"] = curves["c3"].pct_change(60)
    curves["c3_dd_pct"] = (curves["c3"] / curves["c3"].cummax() - 1.0) * 100.0
    return curves


def _load_product_daily() -> pd.DataFrame:
    frame = pd.read_csv(PRODUCT_DAILY_PATH, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["net_pnl"] = pd.to_numeric(frame["net_pnl"], errors="coerce").fillna(0.0)
    frame["trade_count"] = pd.to_numeric(frame["trade_count"], errors="coerce").fillna(0).astype(int)
    frame["slippage"] = pd.to_numeric(frame["slippage"], errors="coerce").fillna(0.0)
    return frame.dropna(subset=["date", "product_vt_symbol"])


def _window_metrics(curves: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    dates = curves.index
    date_index = pd.Index(dates)
    equity = curves[TARGET_VARIANT].to_numpy(dtype=float)
    for horizon in HORIZONS:
        last_start = dates.max() - pd.Timedelta(days=horizon)
        for start_idx, start_date in enumerate(dates):
            if start_date > last_start:
                break
            end_date = start_date + pd.Timedelta(days=horizon)
            if end_date not in date_index:
                continue
            end_idx = int(date_index.get_loc(end_date))
            seg = equity[start_idx : end_idx + 1]
            nav = seg / seg[0]
            dd = nav / np.maximum.accumulate(nav) - 1.0
            start_state = curves.iloc[start_idx]
            rows.append(
                {
                    "horizon_days": horizon,
                    "start_date": start_date,
                    "end_date": end_date,
                    "return_pct": float((nav[-1] - 1.0) * 100.0),
                    "max_dd_pct": float(dd.min() * 100.0),
                    "start_c3_dd_pct": float(start_state["c3_dd_pct"]),
                    "start_c3_ret20_pct": float(start_state["c3_ret20"] * 100.0) if pd.notna(start_state["c3_ret20"]) else np.nan,
                    "start_c3_ret60_pct": float(start_state["c3_ret60"] * 100.0) if pd.notna(start_state["c3_ret60"]) else np.nan,
                    "start_equity": float(seg[0]),
                    "end_equity": float(seg[-1]),
                }
            )
    metrics = pd.DataFrame(rows)
    metrics["return_rank_in_horizon"] = metrics.groupby("horizon_days")["return_pct"].rank(method="first", ascending=True).astype(int)
    metrics["dd_rank_in_horizon"] = metrics.groupby("horizon_days")["max_dd_pct"].rank(method="first", ascending=True).astype(int)
    return metrics


def _attribute_products(worst_windows: pd.DataFrame, product_daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, window in worst_windows.iterrows():
        start = pd.Timestamp(window["start_date"])
        end = pd.Timestamp(window["end_date"])
        segment = product_daily[(product_daily["date"] >= start) & (product_daily["date"] <= end)]
        grouped = (
            segment.groupby("product_vt_symbol", as_index=False)
            .agg(net_pnl=("net_pnl", "sum"), trade_count=("trade_count", "sum"), slippage=("slippage", "sum"), active_days=("net_pnl", lambda x: int((x != 0).sum())))
            .sort_values("net_pnl")
        )
        total_loss = float(grouped[grouped["net_pnl"] < 0.0]["net_pnl"].sum())
        for rank, row in enumerate(grouped.head(10).itertuples(index=False), start=1):
            loss_share = float(row.net_pnl / total_loss) if total_loss < 0.0 and row.net_pnl < 0.0 else 0.0
            rows.append(
                {
                    "horizon_days": int(window["horizon_days"]),
                    "window_rank": int(window["return_rank_in_horizon"]),
                    "start_date": start.date().isoformat(),
                    "end_date": end.date().isoformat(),
                    "window_return_pct": float(window["return_pct"]),
                    "window_max_dd_pct": float(window["max_dd_pct"]),
                    "product_rank": rank,
                    "product_vt_symbol": row.product_vt_symbol,
                    "net_pnl": float(row.net_pnl),
                    "loss_share_in_negative_products": loss_share,
                    "trade_count": int(row.trade_count),
                    "slippage": float(row.slippage),
                    "active_days": int(row.active_days),
                }
            )
    return pd.DataFrame(rows)


def _loss_days(worst_windows: pd.DataFrame, curves: pd.DataFrame, product_daily: pd.DataFrame) -> pd.DataFrame:
    daily_product = product_daily.groupby("date", as_index=False)["net_pnl"].sum().rename(columns={"net_pnl": "product_net_pnl"})
    daily = curves[[TARGET_VARIANT, "stage079_ret", "c3_dd_pct", "c3_ret20", "c3_ret60"]].reset_index().rename(columns={"index": "date"})
    daily["stage079_net_pnl"] = daily[TARGET_VARIANT].diff().fillna(0.0)
    daily = daily.merge(daily_product, on="date", how="left").fillna({"product_net_pnl": 0.0})
    rows: list[pd.DataFrame] = []
    for _, window in worst_windows.iterrows():
        start = pd.Timestamp(window["start_date"])
        end = pd.Timestamp(window["end_date"])
        segment = daily[(daily["date"] >= start) & (daily["date"] <= end)].copy()
        segment = segment.sort_values("stage079_net_pnl").head(10)
        segment["horizon_days"] = int(window["horizon_days"])
        segment["window_rank"] = int(window["return_rank_in_horizon"])
        segment["window_start_date"] = start.date().isoformat()
        segment["window_end_date"] = end.date().isoformat()
        rows.append(segment)
    result = pd.concat(rows, ignore_index=True)
    result["c3_ret20_pct"] = result["c3_ret20"] * 100.0
    result["c3_ret60_pct"] = result["c3_ret60"] * 100.0
    return result[
        [
            "horizon_days",
            "window_rank",
            "window_start_date",
            "window_end_date",
            "date",
            "stage079_net_pnl",
            "product_net_pnl",
            "stage079_ret",
            "c3_dd_pct",
            "c3_ret20_pct",
            "c3_ret60_pct",
        ]
    ]


def _state_context(metrics: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for horizon in HORIZONS:
        all_windows = metrics[metrics["horizon_days"].eq(horizon)]
        worst = all_windows.nsmallest(max(1, int(len(all_windows) * 0.05)), "return_pct")
        median = all_windows
        rows.append(
            {
                "horizon_days": horizon,
                "window_group": "worst_return_5pct",
                "count": int(len(worst)),
                "return_median_pct": float(worst["return_pct"].median()),
                "return_mean_pct": float(worst["return_pct"].mean()),
                "max_dd_median_pct": float(worst["max_dd_pct"].median()),
                "start_c3_dd_median_pct": float(worst["start_c3_dd_pct"].median()),
                "start_c3_ret20_median_pct": float(worst["start_c3_ret20_pct"].median()),
                "start_c3_ret60_median_pct": float(worst["start_c3_ret60_pct"].median()),
            }
        )
        rows.append(
            {
                "horizon_days": horizon,
                "window_group": "all_windows",
                "count": int(len(median)),
                "return_median_pct": float(median["return_pct"].median()),
                "return_mean_pct": float(median["return_pct"].mean()),
                "max_dd_median_pct": float(median["max_dd_pct"].median()),
                "start_c3_dd_median_pct": float(median["start_c3_dd_pct"].median()),
                "start_c3_ret20_median_pct": float(median["start_c3_ret20_pct"].median()),
                "start_c3_ret60_median_pct": float(median["start_c3_ret60_pct"].median()),
            }
        )
    return pd.DataFrame(rows)


def _write_report(worst_windows: pd.DataFrame, product_attr: pd.DataFrame, loss_days: pd.DataFrame, state_context: pd.DataFrame, decision: dict[str, Any]) -> None:
    report = [
        "# Stage089 Stage079短窗口失败归因",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：只读归因；不修改策略、不构造候选。",
        "",
        "## 结论摘要",
        "",
        "- 3个月和6个月最差体验主要表现为趋势策略在水下或刚脱离高位时遭遇集中日亏损，而不是现金缓冲不足本身。",
        "- 单靠下跌刹车会改善左尾，但 Stage088 已显示会损伤长期收益和 Sharpe；因此下一步更适合找能在这些窗口独立盈利的承载，或找能提前识别坏窗口的外生状态变量。",
        "",
        "## 最差窗口",
        "",
        _md_table(worst_windows[["horizon_days", "return_rank_in_horizon", "start_date", "end_date", "return_pct", "max_dd_pct", "start_c3_dd_pct", "start_c3_ret20_pct", "start_c3_ret60_pct"]], 20),
        "",
        "## 最差窗口品种亏损归因",
        "",
        _md_table(product_attr[["horizon_days", "window_rank", "start_date", "end_date", "product_rank", "product_vt_symbol", "net_pnl", "loss_share_in_negative_products", "trade_count", "active_days"]], 40),
        "",
        "## 最差窗口内最大亏损日",
        "",
        _md_table(loss_days[["horizon_days", "window_rank", "date", "stage079_net_pnl", "product_net_pnl", "c3_dd_pct", "c3_ret20_pct", "c3_ret60_pct"]], 40),
        "",
        "## 状态上下文",
        "",
        _md_table(state_context, 20),
        "",
        "## 决策",
        "",
        f"- 结论：`{decision['decision']}`。",
        "- 不从本阶段直接生成交易规则；禁止把最差窗口中的单品种名单升级成黑名单。",
        "",
    ]
    REPORT_PATH.write_text("\n".join(report), encoding="utf-8")


def main() -> None:
    curves = _load_stage079()
    product_daily = _load_product_daily()
    metrics = _window_metrics(curves)
    worst_windows = (
        metrics.sort_values(["horizon_days", "return_rank_in_horizon"])
        .groupby("horizon_days", group_keys=False)
        .head(10)
        .reset_index(drop=True)
    )
    product_attr = _attribute_products(worst_windows.groupby("horizon_days", group_keys=False).head(5), product_daily)
    loss_day = _loss_days(worst_windows.groupby("horizon_days", group_keys=False).head(5), curves, product_daily)
    state_context = _state_context(metrics)
    decision = {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "decision": "diagnostic_only_no_candidate_generated",
        "outputs": {
            "worst_windows": str(WINDOW_PATH),
            "product_attribution": str(PRODUCT_ATTR_PATH),
            "loss_days": str(LOSS_DAY_PATH),
            "state_context": str(STATE_PATH),
            "report": str(REPORT_PATH),
        },
    }
    worst_windows.to_csv(WINDOW_PATH, index=False, encoding="utf-8-sig")
    product_attr.to_csv(PRODUCT_ATTR_PATH, index=False, encoding="utf-8-sig")
    loss_day.to_csv(LOSS_DAY_PATH, index=False, encoding="utf-8-sig")
    state_context.to_csv(STATE_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(worst_windows, product_attr, loss_day, state_context, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
