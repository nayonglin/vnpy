from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime
import json
import math
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
sys.path.insert(0, str(PROJECT_DIR.resolve()))

import analyze_qmt_roll_stage402_stage079_xsmom_volmanaged_true_integer as s402  # noqa: E402


MODEL_TAG = "stage511_stage208_bad_window_postmortem_v1"
OUTPUT_PREFIX = "qmt_roll_stage511_stage208_bad_window_postmortem"
LINE_ID = "futures_trend_drawdown30_preserve_return"

STAGE208_TAG = "stage508_xsmom_true_carry_replay_v1"
STAGE208_PREFIX = "qmt_roll_stage508_xsmom_true_carry_replay"
STAGE211_TAG = "stage510_stage208_robustness_audit_v1"
STAGE211_PREFIX = "qmt_roll_stage510_stage208_robustness_audit"
STAGE506_TAG = "stage506_next_real_forward_risk_signal_frontier_v1"
STAGE506_PREFIX = "qmt_roll_stage506_next_real_forward_risk_signal_frontier"

DAILY_IN = OUTPUT_DIR / f"{STAGE208_PREFIX}_daily_{STAGE208_TAG}.csv"
XSMOM_DAILY_IN = OUTPUT_DIR / f"{STAGE208_PREFIX}_xsmom_daily_{STAGE208_TAG}.csv"
BAD_WINDOWS_IN = OUTPUT_DIR / f"{STAGE211_PREFIX}_bad_windows_{STAGE211_TAG}.csv"
TRADE_USAGE_IN = OUTPUT_DIR / f"{STAGE506_PREFIX}_trade_usage_{STAGE506_TAG}.csv"

PEAK_TROUGH_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_peak_trough_{MODEL_TAG}.csv"
TOP_LOSS_DAYS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_top_loss_days_{MODEL_TAG}.csv"
TRADE_REALIZED_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_realized_detail_{MODEL_TAG}.csv"
TRADE_PRODUCT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_product_summary_{MODEL_TAG}.csv"
XSMOM_ACTIVITY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_xsmom_activity_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

PRIMARY = "stage079_next_real_risk070_clean_plus_stage103_xsmom_true"
PRIMARY_CLEAN = "stage079_next_real_risk070_clean"
CONSERVATIVE = "stage079_next_real_risk060_clean_plus_stage103_xsmom_true"
BASELINE = "stage079"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


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


def _contract_product(vt_symbol: str) -> str:
    raw = str(vt_symbol)
    if "." not in raw:
        return raw
    symbol, exchange = raw.split(".", 1)
    letters = "".join(char for char in symbol if char.isalpha())
    return f"{letters or symbol}.{exchange}"


def _load_daily() -> pd.DataFrame:
    frame = pd.read_csv(DAILY_IN, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    for column in ["account_equity", "net_pnl", "slippage", "trade_count"]:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    return frame.dropna(subset=["date", "variant"]).sort_values(["variant", "date"]).reset_index(drop=True)


def _load_xsmom() -> pd.DataFrame:
    frame = pd.read_csv(XSMOM_DAILY_IN, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    for column in [
        "xsmom_true_daily_pnl",
        "xsmom_frozen_daily_pnl",
        "xsmom_true_turnover_contracts",
        "xsmom_true_held_contract_count",
    ]:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    return frame.dropna(subset=["date"]).sort_values("date")


def _size_map() -> dict[str, float]:
    price = s402._build_price_frame()
    price["size"] = pd.to_numeric(price.get("size", 1.0), errors="coerce").fillna(1.0)
    size_by_contract = (
        price.dropna(subset=["main_contract_vt"])
        .sort_values("date")
        .drop_duplicates("main_contract_vt", keep="last")
        .set_index("main_contract_vt")["size"]
        .astype(float)
        .to_dict()
    )
    return {str(key): float(value) for key, value in size_by_contract.items()}


def _canonical_bad_windows() -> pd.DataFrame:
    bad = pd.read_csv(BAD_WINDOWS_IN, encoding="utf-8-sig")
    bad["start_date"] = pd.to_datetime(bad["start_date"], errors="coerce").dt.normalize()
    bad["end_date"] = pd.to_datetime(bad["end_date"], errors="coerce").dt.normalize()
    for column in ["return_pct", "max_dd_pct", "ulcer_pct", "xsmom_true_pnl", "clean_c3_net_pnl", "combo_net_pnl"]:
        bad[column] = pd.to_numeric(bad.get(column, 0.0), errors="coerce").fillna(0.0)
    focus = bad[bad["variant"].eq(PRIMARY) & bad["horizon_days"].isin([90, 180, 252, 504])].copy()
    rows = []
    for horizon, group in focus.groupby("horizon_days"):
        chosen = group.sort_values(["max_dd_pct", "return_pct"], ascending=[True, True]).iloc[0].copy()
        chosen["window_name"] = f"primary_worst_{int(horizon)}d"
        rows.append(chosen)
    return pd.DataFrame(rows).sort_values("horizon_days").reset_index(drop=True)


def _find_peak_trough(daily: pd.DataFrame, windows: pd.DataFrame) -> pd.DataFrame:
    primary = daily[daily["variant"].eq(PRIMARY)].sort_values("date").set_index("date")
    clean = daily[daily["variant"].eq(PRIMARY_CLEAN)].sort_values("date").set_index("date")
    xsmom = _load_xsmom().set_index("date")
    rows: list[dict[str, Any]] = []
    for row in windows.itertuples(index=False):
        start = pd.Timestamp(row.start_date).normalize()
        end = pd.Timestamp(row.end_date).normalize()
        segment = primary.loc[(primary.index >= start) & (primary.index <= end)].copy()
        peak_equity = -np.inf
        peak_date = None
        peak_date_at_trough = None
        peak_equity_at_trough = np.nan
        trough_date = None
        max_dd = 0.0
        for date, item in segment.iterrows():
            equity = _safe_float(item.account_equity)
            if equity > peak_equity:
                peak_equity = equity
                peak_date = date
            dd = equity / peak_equity - 1.0 if peak_equity > 0 else 0.0
            if dd < max_dd:
                max_dd = dd
                peak_date_at_trough = peak_date
                peak_equity_at_trough = peak_equity
                trough_date = date
        if peak_date_at_trough is None or trough_date is None:
            continue
        pt_segment = primary.loc[(primary.index >= peak_date_at_trough) & (primary.index <= trough_date)].copy()
        clean_segment = clean.loc[(clean.index >= peak_date_at_trough) & (clean.index <= trough_date)].copy()
        x_segment = xsmom.loc[(xsmom.index >= peak_date_at_trough) & (xsmom.index <= trough_date)].copy()
        rows.append(
            {
                "window_name": row.window_name,
                "horizon_days": int(row.horizon_days),
                "window_start": start,
                "window_end": end,
                "peak_date": peak_date_at_trough,
                "trough_date": trough_date,
                "peak_equity": float(peak_equity_at_trough),
                "trough_equity": float(pt_segment["account_equity"].iloc[-1]),
                "peak_to_trough_dd_pct": float(max_dd * 100.0),
                "combo_net_pnl_peak_to_trough": float(pt_segment["net_pnl"].sum()),
                "clean_c3_net_pnl_peak_to_trough": float(clean_segment["net_pnl"].sum()) if not clean_segment.empty else np.nan,
                "xsmom_true_pnl_peak_to_trough": float(x_segment["xsmom_true_daily_pnl"].sum()) if not x_segment.empty else 0.0,
                "xsmom_turnover_peak_to_trough": float(x_segment["xsmom_true_turnover_contracts"].sum()) if not x_segment.empty else 0.0,
                "xsmom_active_days_peak_to_trough": int((x_segment["xsmom_true_held_contract_count"] != 0).sum()) if not x_segment.empty else 0,
            }
        )
    return pd.DataFrame(rows)


def _top_loss_days(daily: pd.DataFrame, peak_trough: pd.DataFrame) -> pd.DataFrame:
    primary = daily[daily["variant"].eq(PRIMARY)].sort_values("date").set_index("date")
    clean = daily[daily["variant"].eq(PRIMARY_CLEAN)].sort_values("date").set_index("date")
    xsmom = _load_xsmom().set_index("date")
    rows: list[dict[str, Any]] = []
    for row in peak_trough.itertuples(index=False):
        segment = primary.loc[(primary.index >= row.peak_date) & (primary.index <= row.trough_date)].copy()
        worst = segment.sort_values("net_pnl", ascending=True).head(12)
        for date, item in worst.iterrows():
            rows.append(
                {
                    "window_name": row.window_name,
                    "date": date,
                    "combo_net_pnl": float(item.net_pnl),
                    "combo_equity": float(item.account_equity),
                    "clean_c3_net_pnl": float(clean.loc[date, "net_pnl"]) if date in clean.index else np.nan,
                    "xsmom_true_pnl": float(xsmom.loc[date, "xsmom_true_daily_pnl"]) if date in xsmom.index else 0.0,
                    "xsmom_held_contract_count": float(xsmom.loc[date, "xsmom_true_held_contract_count"]) if date in xsmom.index else 0.0,
                }
            )
    return pd.DataFrame(rows)


def _signed_open_key(direction: str, offset: str) -> tuple[str, int]:
    direction = str(direction)
    offset = str(offset)
    if offset == "Open":
        return ("long", 1) if direction == "Long" else ("short", -1)
    if direction == "Short":
        return ("long", -1)
    return ("short", 1)


def _reconstruct_realized_trades() -> pd.DataFrame:
    usage = pd.read_csv(TRADE_USAGE_IN, encoding="utf-8-sig")
    usage = usage[usage["variant"].eq(PRIMARY_CLEAN)].copy()
    usage["fill_date"] = pd.to_datetime(usage["fill_date"], errors="coerce").dt.normalize()
    usage["order_volume"] = pd.to_numeric(usage["order_volume"], errors="coerce").fillna(0.0)
    usage["trade_price"] = pd.to_numeric(usage["trade_price"], errors="coerce").fillna(0.0)
    usage = usage.dropna(subset=["fill_date", "vt_symbol"]).sort_values(["fill_date", "orderid", "trade_id"]).reset_index(drop=True)
    sizes = _size_map()
    lots: dict[str, dict[str, deque[dict[str, float]]]] = defaultdict(lambda: {"long": deque(), "short": deque()})
    realized: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    for row in usage.itertuples(index=False):
        vt_symbol = str(row.vt_symbol)
        product = _contract_product(vt_symbol)
        side, sign = _signed_open_key(str(row.direction), str(row.offset))
        volume = float(row.order_volume)
        price = float(row.trade_price)
        size = sizes.get(vt_symbol, 1.0)
        if volume <= 0 or price <= 0:
            continue
        if str(row.offset) == "Open":
            lots[vt_symbol][side].append({"volume": volume, "price": price, "date": row.fill_date})
            continue
        # Close long uses a Short close order; close short uses a Long close order.
        close_side = side
        remaining = volume
        pnl = 0.0
        matched = 0.0
        while remaining > 1e-9 and lots[vt_symbol][close_side]:
            open_lot = lots[vt_symbol][close_side][0]
            matched_volume = min(remaining, float(open_lot["volume"]))
            if close_side == "long":
                pnl += (price - float(open_lot["price"])) * matched_volume * size
            else:
                pnl += (float(open_lot["price"]) - price) * matched_volume * size
            open_lot["volume"] = float(open_lot["volume"]) - matched_volume
            remaining -= matched_volume
            matched += matched_volume
            if open_lot["volume"] <= 1e-9:
                lots[vt_symbol][close_side].popleft()
        realized.append(
            {
                "close_date": row.fill_date,
                "vt_symbol": vt_symbol,
                "product": product,
                "close_direction": str(row.direction),
                "close_offset": str(row.offset),
                "closed_side": close_side,
                "requested_volume": volume,
                "matched_volume": matched,
                "unmatched_volume": remaining,
                "close_price": price,
                "size": size,
                "realized_gross_pnl": pnl,
                "price_source": str(row.price_source),
            }
        )
        if remaining > 1e-9:
            unmatched.append(realized[-1])
    return pd.DataFrame(realized)


def _trade_product_summary(realized: pd.DataFrame, peak_trough: pd.DataFrame) -> pd.DataFrame:
    usage = pd.read_csv(TRADE_USAGE_IN, encoding="utf-8-sig")
    usage = usage[usage["variant"].eq(PRIMARY_CLEAN)].copy()
    usage["fill_date"] = pd.to_datetime(usage["fill_date"], errors="coerce").dt.normalize()
    usage["order_volume"] = pd.to_numeric(usage["order_volume"], errors="coerce").fillna(0.0)
    usage["product"] = usage["vt_symbol"].map(_contract_product)
    rows: list[dict[str, Any]] = []
    for row in peak_trough.itertuples(index=False):
        start = pd.Timestamp(row.peak_date).normalize()
        end = pd.Timestamp(row.trough_date).normalize()
        trade_slice = usage[(usage["fill_date"] >= start) & (usage["fill_date"] <= end)].copy()
        realized_slice = realized[(realized["close_date"] >= start) & (realized["close_date"] <= end)].copy()
        product_set = sorted(set(trade_slice["product"].dropna().astype(str)) | set(realized_slice["product"].dropna().astype(str)))
        for product in product_set:
            t = trade_slice[trade_slice["product"].eq(product)]
            r = realized_slice[realized_slice["product"].eq(product)]
            rows.append(
                {
                    "window_name": row.window_name,
                    "peak_date": start,
                    "trough_date": end,
                    "product": product,
                    "order_count": int(len(t)),
                    "open_volume": float(t[t["offset"].eq("Open")]["order_volume"].sum()),
                    "close_volume": float(t[t["offset"].eq("Close")]["order_volume"].sum()),
                    "matched_close_volume": float(r["matched_volume"].sum()) if not r.empty else 0.0,
                    "realized_gross_pnl": float(r["realized_gross_pnl"].sum()) if not r.empty else 0.0,
                    "loss_close_count": int((r["realized_gross_pnl"] < 0.0).sum()) if not r.empty else 0,
                    "profit_close_count": int((r["realized_gross_pnl"] > 0.0).sum()) if not r.empty else 0,
                }
            )
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    return result.sort_values(["window_name", "realized_gross_pnl", "open_volume"], ascending=[True, True, False])


def _xsmom_activity(peak_trough: pd.DataFrame) -> pd.DataFrame:
    xsmom = _load_xsmom().set_index("date")
    rows: list[dict[str, Any]] = []
    for row in peak_trough.itertuples(index=False):
        for start_name, start, end in [
            ("full_bad_window", row.window_start, row.window_end),
            ("peak_to_trough", row.peak_date, row.trough_date),
        ]:
            segment = xsmom.loc[(xsmom.index >= pd.Timestamp(start)) & (xsmom.index <= pd.Timestamp(end))]
            rows.append(
                {
                    "window_name": row.window_name,
                    "segment": start_name,
                    "start_date": pd.Timestamp(start),
                    "end_date": pd.Timestamp(end),
                    "xsmom_true_pnl": float(segment["xsmom_true_daily_pnl"].sum()) if not segment.empty else 0.0,
                    "xsmom_frozen_pnl": float(segment["xsmom_frozen_daily_pnl"].sum()) if not segment.empty else 0.0,
                    "xsmom_turnover": float(segment["xsmom_true_turnover_contracts"].sum()) if not segment.empty else 0.0,
                    "active_days": int((segment["xsmom_true_held_contract_count"] != 0).sum()) if not segment.empty else 0,
                    "total_days": int(len(segment)),
                }
            )
    return pd.DataFrame(rows)


def _plot(daily: pd.DataFrame, peak_trough: pd.DataFrame, top_loss_days: pd.DataFrame) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(13, 10), sharex=False)
    focus_start = pd.Timestamp("2021-05-01")
    focus_end = pd.Timestamp("2022-03-31")
    for variant in [BASELINE, PRIMARY_CLEAN, PRIMARY, CONSERVATIVE]:
        frame = daily[(daily["variant"].eq(variant)) & (daily["date"].between(focus_start, focus_end))].copy()
        if frame.empty:
            continue
        equity = pd.Series(frame["account_equity"].to_numpy(dtype=float), index=pd.to_datetime(frame["date"]))
        nav = equity / float(equity.iloc[0])
        axes[0].plot(nav.index, nav, label=variant, linewidth=1.0)
        dd = nav / nav.cummax() - 1.0
        axes[1].plot(dd.index, dd * 100.0, label=variant, linewidth=1.0)
    for row in peak_trough.itertuples(index=False):
        if int(row.horizon_days) in (90, 180):
            axes[0].axvspan(pd.Timestamp(row.peak_date), pd.Timestamp(row.trough_date), color="#b3261e", alpha=0.08)
            axes[1].axvspan(pd.Timestamp(row.peak_date), pd.Timestamp(row.trough_date), color="#b3261e", alpha=0.08)
    axes[0].set_title("Stage208 bad-window zoom NAV: 2021-05 to 2022-03")
    axes[0].legend(fontsize=7)
    axes[0].grid(True, alpha=0.22)
    axes[1].set_title("Drawdown in zoom window")
    axes[1].axhline(-40.0, color="#222222", linestyle="--", linewidth=1.0)
    axes[1].axhline(-30.0, color="#777777", linestyle=":", linewidth=0.9)
    axes[1].set_ylabel("DD %")
    axes[1].grid(True, alpha=0.22)
    loss = top_loss_days[top_loss_days["window_name"].eq("primary_worst_90d")].sort_values("date").copy()
    if not loss.empty:
        axes[2].bar(pd.to_datetime(loss["date"]), loss["clean_c3_net_pnl"], label="clean C3 daily PnL", alpha=0.7)
        axes[2].bar(pd.to_datetime(loss["date"]), loss["xsmom_true_pnl"], label="xsmom true daily PnL", alpha=0.7)
    axes[2].set_title("Worst 90d peak-trough: top loss days attribution")
    axes[2].set_ylabel("PnL")
    axes[2].legend(fontsize=8)
    axes[2].grid(True, alpha=0.22)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _decision(peak_trough: pd.DataFrame, xsmom_activity: pd.DataFrame, product_summary: pd.DataFrame) -> dict[str, Any]:
    worst_90 = peak_trough[peak_trough["window_name"].eq("primary_worst_90d")].iloc[0]
    worst_180 = peak_trough[peak_trough["window_name"].eq("primary_worst_180d")].iloc[0]
    activity_90 = xsmom_activity[
        xsmom_activity["window_name"].eq("primary_worst_90d") & xsmom_activity["segment"].eq("peak_to_trough")
    ].iloc[0]
    top_losses = (
        product_summary[product_summary["window_name"].eq("primary_worst_180d")]
        .sort_values("realized_gross_pnl")
        .head(5)
    )
    return {
        "stage": "Stage212",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": "bad_windows_are_c3_path_and_xsmom_activation_gap_no_direct_rule_change",
        "worst_90_peak_to_trough_dd_pct": _safe_float(worst_90["peak_to_trough_dd_pct"]),
        "worst_90_peak_date": worst_90["peak_date"],
        "worst_90_trough_date": worst_90["trough_date"],
        "worst_90_xsmom_active_days": int(activity_90["active_days"]),
        "worst_90_xsmom_true_pnl": _safe_float(activity_90["xsmom_true_pnl"]),
        "worst_180_peak_to_trough_dd_pct": _safe_float(worst_180["peak_to_trough_dd_pct"]),
        "worst_180_xsmom_true_pnl_peak_to_trough": _safe_float(worst_180["xsmom_true_pnl_peak_to_trough"]),
        "top_realized_loss_products_worst180": top_losses[["product", "realized_gross_pnl", "order_count"]].to_dict("records"),
        "next_step": "Do not add ATR/K-line patch yet; inspect exact C3 position path or compare conservative risk060 as deployment fallback.",
    }


def _write_report(
    peak_trough: pd.DataFrame,
    top_loss_days: pd.DataFrame,
    realized: pd.DataFrame,
    product_summary: pd.DataFrame,
    xsmom_activity: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    top_product = product_summary.sort_values(["window_name", "realized_gross_pnl"]).groupby("window_name").head(12)
    report = [
        "# Stage212 Stage208坏窗口逐笔/账本复盘",
        "",
        f"- 生成时间：{decision['generated_at']}",
        "- 阶段性质：只读坏窗口复盘；不新增规则、不调参数、不做收益筛选。",
        "- 运行前过拟合判断：否。目标是解释 Stage211 中 Stage208 主候选的脆弱来源，不根据结果修补策略。",
        "- 运行前继续价值判断：是。只有先确定坏窗口失效结构，才知道是否值得做 ATR/K线/持仓释放等策略本体实验。",
        "",
        "## 决策",
        "",
        f"- 决策标签：`{decision['decision']}`。",
        f"- 最差90日峰谷：`{decision['worst_90_peak_date']}` 到 `{decision['worst_90_trough_date']}`，回撤 `{decision['worst_90_peak_to_trough_dd_pct']:.4f}%`。",
        f"- 最差90日峰谷 xsmom 活跃天数：`{decision['worst_90_xsmom_active_days']}`，xsmom PnL `{decision['worst_90_xsmom_true_pnl']:.0f}`。",
        f"- 最差180日峰谷回撤：`{decision['worst_180_peak_to_trough_dd_pct']:.4f}%`，xsmom PnL `{decision['worst_180_xsmom_true_pnl_peak_to_trough']:.0f}`。",
        "- 初步判断：Stage208 的最短坏窗口不是 xsmom 亏损造成，而是 xsmom 空档时 C3 本体路径承压；180/252/504天坏窗口中 xsmom 有正贡献，但只能把 DD 从破40拉回贴线，不能提供厚安全垫。",
        "",
        "## 峰谷摘要",
        "",
        _md_table(peak_trough),
        "",
        "## xsmom活动",
        "",
        _md_table(xsmom_activity),
        "",
        "## 峰谷最差日",
        "",
        _md_table(top_loss_days.sort_values(["window_name", "combo_net_pnl"]), max_rows=80),
        "",
        "## C3近似已实现盈亏产品归因",
        "",
        "- 注意：这是根据 Stage506 C3 成交 usage 还原的已实现 gross PnL，不含未平仓持仓的逐日盯市损益，因此只能作为产品暴露线索，不能替代完整产品日度 PnL。",
        "",
        _md_table(top_product, max_rows=80),
        "",
        "## 视觉复盘",
        "",
        f"- 图表：`{CHART_PATH}`。",
        "- 红色阴影段显示 2021-2022 的主候选峰谷区间；最差90日峰谷中 xsmom 日PnL为0，说明短窗口左尾主要由 C3 本体承担。",
        "",
        "## 结论",
        "",
        "- 不直接新增 ATR/K线规则。原因是坏窗口证据目前指向 C3 持仓路径与 xsmom 激活空档，而不是某个单一可泛化的K线形态或止损倍数。",
        "- 下一步若继续优化，有两个低过拟合方向：一是补更完整的 C3 持仓日度产品归因；二是把 `risk060 + true xsmom` 作为保守部署候选，与 `risk070 + true xsmom` 做真实保证金对照。",
        "",
        "## 过拟合与继续价值反思",
        "",
        "- 运行后过拟合判断：否。本阶段只解释固定坏窗口，不新增策略。",
        "- 运行后继续价值判断：继续有价值，但必须沿着完整持仓路径归因或部署口径选择走；直接调 ATR/K线阈值价值低。",
    ]
    REPORT_PATH.write_text("\n".join(report) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    daily = _load_daily()
    windows = _canonical_bad_windows()
    peak_trough = _find_peak_trough(daily, windows)
    top_loss_days = _top_loss_days(daily, peak_trough)
    realized = _reconstruct_realized_trades()
    product_summary = _trade_product_summary(realized, peak_trough)
    xsmom_activity = _xsmom_activity(peak_trough)
    decision = _decision(peak_trough, xsmom_activity, product_summary)
    _plot(daily, peak_trough, top_loss_days)

    peak_trough.to_csv(PEAK_TROUGH_PATH, index=False, encoding="utf-8-sig")
    top_loss_days.to_csv(TOP_LOSS_DAYS_PATH, index=False, encoding="utf-8-sig")
    realized.to_csv(TRADE_REALIZED_PATH, index=False, encoding="utf-8-sig")
    product_summary.to_csv(TRADE_PRODUCT_PATH, index=False, encoding="utf-8-sig")
    xsmom_activity.to_csv(XSMOM_ACTIVITY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(peak_trough, top_loss_days, realized, product_summary, xsmom_activity, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"wrote: {REPORT_PATH}")


if __name__ == "__main__":
    main()
