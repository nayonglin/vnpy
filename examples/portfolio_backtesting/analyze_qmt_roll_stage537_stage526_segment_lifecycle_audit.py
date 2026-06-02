from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
import re
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
LINE_ID = "futures_trend_drawdown30_preserve_return"
MODEL_TAG = "stage537_stage526_segment_lifecycle_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage537_stage526_segment_lifecycle_audit"

STAGE526_TAG = "stage526_productcap25_breadth_frontier_v1"
STAGE526_PREFIX = "qmt_roll_stage526_productcap25_breadth_frontier"
CANDIDATE = "r080_pc25_maxpos4"

DAILY_IN = OUTPUT_DIR / f"{STAGE526_PREFIX}_margin_daily_{STAGE526_TAG}.csv"
POSITIONS_IN = OUTPUT_DIR / f"{STAGE526_PREFIX}_positions_{STAGE526_TAG}.csv"
SUMMARY_IN = OUTPUT_DIR / f"{STAGE526_PREFIX}_summary_{STAGE526_TAG}.csv"

SEGMENT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_segments_{MODEL_TAG}.csv"
DURATION_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_duration_summary_{MODEL_TAG}.csv"
GUARD_PROBE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_guard_probe_{MODEL_TAG}.csv"
PRODUCT_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

BAD_START = pd.Timestamp("2022-03-09")
BAD_END = pd.Timestamp("2022-12-07")


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
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "无数据。"
    view = frame.copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda item: f"{item:.4f}" if pd.notna(item) else "")
    return view.to_markdown(index=False)


def _product_from_contract(vt_symbol: object) -> str:
    raw = str(vt_symbol)
    if "." not in raw:
        return raw
    symbol, exchange = raw.split(".", 1)
    match = re.match(r"[A-Za-z]+", symbol)
    product = match.group(0) if match else symbol
    return f"{product}.{exchange}"


def _load_daily_dates() -> pd.DataFrame:
    daily = pd.read_csv(DAILY_IN, encoding="utf-8-sig", usecols=["date", "variant"])
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
    daily = daily[daily["variant"].eq(CANDIDATE)].dropna(subset=["date"]).sort_values("date").drop_duplicates("date").copy()
    daily["day_index"] = np.arange(len(daily), dtype=int)
    return daily[["date", "day_index"]]


def _load_summary_metrics() -> dict[str, float]:
    summary = pd.read_csv(SUMMARY_IN, encoding="utf-8-sig")
    row = summary[summary["variant"].eq(CANDIDATE)]
    if row.empty:
        return {}
    record = row.iloc[0]
    return {
        "ending_equity": float(record.get("end_equity", 0.0)),
        "total_return_pct": float(record.get("total_return_pct", 0.0)),
        "max_dd_pct": float(record.get("max_dd_pct", 0.0)),
        "sharpe": float(record.get("sharpe", 0.0)),
        "ulcer_pct": float(record.get("ulcer_pct", 0.0)),
        "total_slippage": float(record.get("total_slippage", 0.0)),
        "total_trade_count": float(record.get("total_trade_count", 0.0)),
        "nonzero_daily_win_rate_pct": float(record.get("nonzero_daily_win_rate_pct", 0.0)),
    }


def _load_active_positions(day_index: pd.DataFrame) -> pd.DataFrame:
    if not POSITIONS_IN.exists():
        raise FileNotFoundError(POSITIONS_IN)
    usecols = [
        "date",
        "vt_symbol",
        "start_pos",
        "end_pos",
        "trade_count",
        "slippage",
        "holding_pnl",
        "trading_pnl",
        "net_pnl",
        "variant",
    ]
    frames: list[pd.DataFrame] = []
    date_to_idx = dict(zip(day_index["date"], day_index["day_index"], strict=False))
    for chunk in pd.read_csv(POSITIONS_IN, usecols=usecols, chunksize=500_000, encoding="utf-8-sig"):
        chunk["date"] = pd.to_datetime(chunk["date"], errors="coerce").dt.normalize()
        mask = chunk["variant"].eq(CANDIDATE)
        if not mask.any():
            continue
        frame = chunk.loc[mask].copy()
        for column in ["start_pos", "end_pos", "trade_count", "slippage", "holding_pnl", "trading_pnl", "net_pnl"]:
            frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
        active = frame["start_pos"].ne(0.0) | frame["end_pos"].ne(0.0) | frame["trade_count"].gt(0.0)
        frame = frame[active].copy()
        if frame.empty:
            continue
        frame["day_index"] = frame["date"].map(date_to_idx)
        frame = frame.dropna(subset=["day_index"])
        frame["day_index"] = frame["day_index"].astype(int)
        frame["product_vt_symbol"] = frame["vt_symbol"].map(_product_from_contract)
        frames.append(frame)
    if not frames:
        raise RuntimeError("no active candidate positions")
    active_positions = pd.concat(frames, ignore_index=True, sort=False)
    return active_positions.sort_values(["vt_symbol", "day_index"]).reset_index(drop=True)


def _segments(active_positions: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for vt_symbol, group in active_positions.groupby("vt_symbol"):
        group = group.sort_values("day_index").reset_index(drop=True)
        new_segment = group["day_index"].diff().fillna(9999).gt(1)
        segment_id = new_segment.cumsum()
        group["segment_id"] = segment_id
        for seg_id, segment in group.groupby("segment_id"):
            segment = segment.sort_values("day_index").copy()
            net_values = segment["net_pnl"].astype(float).to_numpy()
            cumsum = np.cumsum(net_values)
            direction = float(segment["end_pos"].replace(0.0, np.nan).dropna().median()) if segment["end_pos"].ne(0.0).any() else 0.0
            row = {
                "vt_symbol": vt_symbol,
                "product_vt_symbol": segment["product_vt_symbol"].iloc[0],
                "segment_id": int(seg_id),
                "start": segment["date"].iloc[0],
                "end": segment["date"].iloc[-1],
                "start_day_index": int(segment["day_index"].iloc[0]),
                "end_day_index": int(segment["day_index"].iloc[-1]),
                "segment_days": int(len(segment)),
                "direction": "long" if direction > 0 else ("short" if direction < 0 else "flat"),
                "max_abs_pos": float(segment[["start_pos", "end_pos"]].abs().max().max()),
                "net_pnl": float(segment["net_pnl"].sum()),
                "holding_pnl": float(segment["holding_pnl"].sum()),
                "trading_pnl": float(segment["trading_pnl"].sum()),
                "slippage": float(segment["slippage"].sum()),
                "trade_count": float(segment["trade_count"].sum()),
                "trade_days": int(segment["trade_count"].gt(0.0).sum()),
                "overlap_bad_window": int(segment["date"].between(BAD_START, BAD_END).any()),
            }
            for day in [1, 2, 3, 5, 10]:
                if len(cumsum) >= day:
                    row[f"cum_net_day{day}"] = float(cumsum[day - 1])
                    row[f"active_at_day{day}"] = 1
                else:
                    row[f"cum_net_day{day}"] = np.nan
                    row[f"active_at_day{day}"] = 0
            rows.append(row)
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    bins = [0, 3, 5, 10, 20, 60, np.inf]
    labels = ["1-3", "4-5", "6-10", "11-20", "21-60", "60+"]
    frame["duration_bucket"] = pd.cut(frame["segment_days"], bins=bins, labels=labels, right=True).astype(str)
    frame["edge_sign"] = np.select([frame["net_pnl"].gt(0), frame["net_pnl"].lt(0)], ["positive", "negative"], default="flat")
    return frame.sort_values("start").reset_index(drop=True)


def _duration_summary(segments: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for scope, frame in [("all", segments), ("bad_window_overlap", segments[segments["overlap_bad_window"].eq(1)])]:
        grouped = (
            frame.groupby("duration_bucket", as_index=False)
            .agg(
                segment_count=("vt_symbol", "count"),
                net_pnl=("net_pnl", "sum"),
                positive_pnl=("net_pnl", lambda item: float(item[item > 0].sum())),
                negative_pnl=("net_pnl", lambda item: float(item[item < 0].sum())),
                positive_count=("net_pnl", lambda item: int((item > 0).sum())),
                negative_count=("net_pnl", lambda item: int((item < 0).sum())),
                slippage=("slippage", "sum"),
                trade_count=("trade_count", "sum"),
                median_net_pnl=("net_pnl", "median"),
            )
            .sort_values("duration_bucket")
        )
        grouped.insert(0, "scope", scope)
        rows.append(grouped)
    return pd.concat(rows, ignore_index=True, sort=False)


def _guard_probes(segments: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for scope, frame in [("all", segments), ("bad_window_overlap", segments[segments["overlap_bad_window"].eq(1)])]:
        for day in [1, 2, 3, 5, 10]:
            col = f"cum_net_day{day}"
            active_col = f"active_at_day{day}"
            trigger = frame[frame[active_col].eq(1) & frame[col].lt(0.0)].copy()
            if trigger.empty:
                rows.append(
                    {
                        "scope": scope,
                        "probe": f"exit_after_day{day}_if_cum_negative",
                        "trigger_count": 0,
                        "trigger_final_net_pnl": 0.0,
                        "trigger_cum_net_at_check": 0.0,
                        "estimated_exit_delta": 0.0,
                        "estimated_half_delta": 0.0,
                        "negative_final_count": 0,
                        "positive_final_count": 0,
                        "positive_final_pnl_at_risk": 0.0,
                        "missed_recovery_after_check": 0.0,
                        "loss_saved_after_check": 0.0,
                    }
                )
                continue
            estimated_exit_delta = trigger[col] - trigger["net_pnl"]
            positive_final = trigger[trigger["net_pnl"].gt(0.0)]
            negative_final = trigger[trigger["net_pnl"].lt(0.0)]
            rows.append(
                {
                    "scope": scope,
                    "probe": f"exit_after_day{day}_if_cum_negative",
                    "trigger_count": int(len(trigger)),
                    "trigger_final_net_pnl": float(trigger["net_pnl"].sum()),
                    "trigger_cum_net_at_check": float(trigger[col].sum()),
                    "estimated_exit_delta": float(estimated_exit_delta.sum()),
                    "estimated_half_delta": float(0.5 * estimated_exit_delta.sum()),
                    "negative_final_count": int(len(negative_final)),
                    "positive_final_count": int(len(positive_final)),
                    "positive_final_pnl_at_risk": float(positive_final["net_pnl"].sum()) if len(positive_final) else 0.0,
                    "missed_recovery_after_check": float((positive_final["net_pnl"] - positive_final[col]).sum()) if len(positive_final) else 0.0,
                    "loss_saved_after_check": float((negative_final[col] - negative_final["net_pnl"]).sum()) if len(negative_final) else 0.0,
                }
            )
    result = pd.DataFrame(rows)
    return result.sort_values(["scope", "estimated_exit_delta"], ascending=[True, False])


def _product_summary(segments: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        segments.groupby("product_vt_symbol", as_index=False)
        .agg(
            segment_count=("vt_symbol", "count"),
            net_pnl=("net_pnl", "sum"),
            positive_pnl=("net_pnl", lambda item: float(item[item > 0].sum())),
            negative_pnl=("net_pnl", lambda item: float(item[item < 0].sum())),
            short_loss_count=("net_pnl", lambda item: int((item < 0).sum())),
            slippage=("slippage", "sum"),
            trade_count=("trade_count", "sum"),
            bad_window_net_pnl=("net_pnl", lambda item: float(item[segments.loc[item.index, "overlap_bad_window"].eq(1)].sum())),
        )
        .sort_values("net_pnl")
    )
    return grouped


def _decision(
    segments: pd.DataFrame,
    duration_summary: pd.DataFrame,
    guard_probe: pd.DataFrame,
    product_summary: pd.DataFrame,
    summary_metrics: dict[str, float],
) -> dict[str, Any]:
    all_probes = guard_probe[guard_probe["scope"].eq("all")].copy()
    best = all_probes.sort_values("estimated_exit_delta", ascending=False).head(1)
    best_row = best.iloc[0].to_dict() if not best.empty else {}
    label = "early_adverse_lifecycle_probe_only"
    if best_row and float(best_row.get("estimated_exit_delta", 0.0)) <= 0.0:
        label = "early_adverse_exit_rejected"
    elif best_row and float(best_row.get("positive_final_pnl_at_risk", 0.0)) > float(best_row.get("loss_saved_after_check", 0.0)) * 0.50:
        label = "early_adverse_exit_positive_tail_risk"

    return {
        "stage": "Stage237",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": label,
        "candidate": CANDIDATE,
        "full_period_reference": _json_safe(summary_metrics),
        "segment_count": int(len(segments)),
        "segment_net_pnl_sum": float(segments["net_pnl"].sum()),
        "segment_positive_pnl_sum": float(segments.loc[segments["net_pnl"].gt(0.0), "net_pnl"].sum()),
        "segment_negative_pnl_sum": float(segments.loc[segments["net_pnl"].lt(0.0), "net_pnl"].sum()),
        "bad_window_segment_net_pnl_sum": float(segments.loc[segments["overlap_bad_window"].eq(1), "net_pnl"].sum()),
        "best_lifecycle_probe": _json_safe(best_row),
        "duration_summary": _json_safe(duration_summary.to_dict(orient="records")),
        "top_loss_products": _json_safe(product_summary.sort_values("net_pnl").head(8).to_dict(orient="records")),
        "top_gain_products": _json_safe(product_summary.sort_values("net_pnl", ascending=False).head(8).to_dict(orient="records")),
        "interpretation": "这是持仓段账本近似，不等同真实引擎退出；若有价值，必须进入真实撮合回测验证。",
    }


def _plot(segments: pd.DataFrame, duration_summary: pd.DataFrame, guard_probe: pd.DataFrame, product_summary: pd.DataFrame) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(2, 2, figsize=(17, 11))
    ax_duration, ax_guard, ax_scatter, ax_product = axes.flatten()

    all_duration = duration_summary[duration_summary["scope"].eq("all")].copy()
    ax_duration.bar(all_duration["duration_bucket"], all_duration["negative_pnl"], color="#dc2626", label="negative pnl")
    ax_duration.bar(all_duration["duration_bucket"], all_duration["positive_pnl"], bottom=all_duration["negative_pnl"], color="#16a34a", label="positive pnl")
    ax_duration.axhline(0, color="#111827", linewidth=1)
    ax_duration.set_title("Full-period segment PnL by duration")
    ax_duration.set_xlabel("segment days bucket")
    ax_duration.grid(axis="y", alpha=0.25)
    ax_duration.legend(fontsize=8)

    all_probe = guard_probe[guard_probe["scope"].eq("all")].copy()
    ax_guard.barh(all_probe["probe"], all_probe["estimated_exit_delta"], color=np.where(all_probe["estimated_exit_delta"].ge(0), "#16a34a", "#dc2626"))
    ax_guard.axvline(0, color="#111827", linewidth=1)
    ax_guard.set_title("Approx early-exit delta full-period")
    ax_guard.grid(axis="x", alpha=0.25)

    colors = np.where(segments["net_pnl"].lt(0), "#dc2626", "#2563eb")
    sizes = np.clip(segments["trade_count"] * 10 + 18, 20, 260)
    ax_scatter.scatter(segments["cum_net_day3"], segments["net_pnl"], c=colors, s=sizes, alpha=0.72, edgecolors="#111827", linewidths=0.35)
    ax_scatter.axhline(0, color="#111827", linewidth=1)
    ax_scatter.axvline(0, color="#111827", linewidth=1)
    ax_scatter.set_title("Day3 cumulative PnL vs final segment PnL")
    ax_scatter.set_xlabel("cum net pnl day3")
    ax_scatter.set_ylabel("final segment pnl")
    ax_scatter.grid(alpha=0.25)

    product = pd.concat([product_summary.sort_values("net_pnl").head(6), product_summary.sort_values("net_pnl", ascending=False).head(6)])
    product = product.drop_duplicates("product_vt_symbol").sort_values("net_pnl")
    ax_product.barh(product["product_vt_symbol"], product["net_pnl"], color=np.where(product["net_pnl"].ge(0), "#16a34a", "#dc2626"))
    ax_product.axvline(0, color="#111827", linewidth=1)
    ax_product.set_title("Segment net PnL by product")
    ax_product.grid(axis="x", alpha=0.25)

    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _write_report(
    segments: pd.DataFrame,
    duration_summary: pd.DataFrame,
    guard_probe: pd.DataFrame,
    product_summary: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    worst_segments = segments.sort_values("net_pnl").head(24)
    best_segments = segments.sort_values("net_pnl", ascending=False).head(16)
    lines = [
        "# Stage237 Stage526持仓段生命周期审计",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        "- 阶段性质：Stage236 后续只读诊断；全周期验证短命亏损段和早期不利退出近似。",
        "- 运行前过拟合判断：否。只读取 Stage526 固定持仓账本，不改策略、不扫小数；早退只是账本近似。",
        "- 运行前继续价值判断：是。Stage236 只说明坏窗口短命亏损明显，本阶段验证全周期误伤右尾。",
        "",
        "## 外部调研判断",
        "",
        "- 趋势跟随可使用 time stop / adverse excursion 规则，但公开资料也反复提示趋势右尾需要时间，过早退出会损害主收益来源。",
        "- 本阶段只做持仓段账本审计，不把近似结果当作真实可部署规则。",
        "",
        "## 决策",
        "",
        "```json",
        json.dumps(_json_safe(decision), ensure_ascii=False, indent=2),
        "```",
        "",
        "## 持仓时长归因",
        "",
        _md_table(duration_summary),
        "",
        "## 早期不利退出近似探针",
        "",
        _md_table(guard_probe),
        "",
        "## 产品持仓段汇总",
        "",
        _md_table(product_summary, max_rows=40),
        "",
        "## 最差持仓段",
        "",
        _md_table(
            worst_segments[
                [
                    "product_vt_symbol",
                    "vt_symbol",
                    "direction",
                    "start",
                    "end",
                    "segment_days",
                    "net_pnl",
                    "cum_net_day2",
                    "cum_net_day3",
                    "cum_net_day5",
                    "slippage",
                    "trade_count",
                    "overlap_bad_window",
                ]
            ],
            max_rows=24,
        ),
        "",
        "## 最好持仓段",
        "",
        _md_table(
            best_segments[
                [
                    "product_vt_symbol",
                    "vt_symbol",
                    "direction",
                    "start",
                    "end",
                    "segment_days",
                    "net_pnl",
                    "cum_net_day2",
                    "cum_net_day3",
                    "cum_net_day5",
                    "slippage",
                    "trade_count",
                    "overlap_bad_window",
                ]
            ],
            max_rows=16,
        ),
        "",
        "## 图表视觉复盘",
        "",
        f"- 图表：`{CHART_PATH}`",
        "- 左上：看短持有桶到底是净亏还是同时有大正收益。",
        "- 右上：看早期不利退出近似是正贡献还是误伤右尾。",
        "- 左下：若第3天亏损但最终盈利的点很多，早退规则危险。",
        "- 右下：看产品贡献是否仍然不能简化为黑名单。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    day_index = _load_daily_dates()
    summary_metrics = _load_summary_metrics()
    active_positions = _load_active_positions(day_index)
    segments = _segments(active_positions)
    duration_summary = _duration_summary(segments)
    guard_probe = _guard_probes(segments)
    product_summary = _product_summary(segments)
    decision = _decision(segments, duration_summary, guard_probe, product_summary, summary_metrics)
    _plot(segments, duration_summary, guard_probe, product_summary)
    _write_report(segments, duration_summary, guard_probe, product_summary, decision)

    segments.to_csv(SEGMENT_PATH, index=False, encoding="utf-8-sig")
    duration_summary.to_csv(DURATION_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    guard_probe.to_csv(GUARD_PROBE_PATH, index=False, encoding="utf-8-sig")
    product_summary.to_csv(PRODUCT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
