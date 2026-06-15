from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage719_official_winner_trade_forensics as s719
import analyze_qmt_roll_stage825_stage819_intraday_rule_forensics as s825
import analyze_qmt_roll_stage827_stage819_intraday_c2_engine_ac as s827
import analyze_qmt_roll_stage830_stage827_c2_broker10_margin_cap as s830
import analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine as s847
import analyze_qmt_roll_stage861_stage860_full_visual_atlas as s861
import analyze_qmt_roll_stage863_stage847_c10_budget_lock_engine as s863
import qmt_roll_official_candidate_stage819_30w_config as stage819_cfg


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage868"
MODEL_TAG = "stage868_stage847_close_confirm_retry_engine_v1"
OUTPUT_PREFIX = "qmt_roll_stage868_stage847_close_confirm_retry_engine"

C4_ARM = s830.CAP_ARM
C9_ARM = s847.C9_ARM
C12_ARM = "stage868_stage819_c9_close_confirm_next_open_retry"

START = s847.START
END = s847.END

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
CURVE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curve_{MODEL_TAG}.csv"
TRADES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{MODEL_TAG}.csv"
ENTRY_RISK_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_{MODEL_TAG}.csv"
ENTRY_CANDIDATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidates_{MODEL_TAG}.csv"
TRADE_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_events_{MODEL_TAG}.csv"
INTRADAY_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_intraday_events_{MODEL_TAG}.csv"
STOP_RETRY_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stop_retry_events_{MODEL_TAG}.csv"
CLOSED_LOTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_closed_lots_{MODEL_TAG}.csv"
EVENT_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_summary_{MODEL_TAG}.csv"
PATH_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_path_chart_{MODEL_TAG}.png"
ATLAS_MANIFEST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if np.isfinite(number) else default


class QmtRollPortfolioStrategyStage868CloseConfirmRetry(s847.QmtRollPortfolioStrategyStage847C9StopRetry):
    enable_stage868_close_confirm_retry: bool = False

    parameters = s847.QmtRollPortfolioStrategyStage847C9StopRetry.parameters + [
        "enable_stage868_close_confirm_retry",
    ]
    variables = s847.QmtRollPortfolioStrategyStage847C9StopRetry.variables + [
        "stage868_close_confirm_retry_count",
        "stage868_close_confirm_no_retry_count",
    ]

    def __init__(self, strategy_engine, strategy_name: str, vt_symbols: list[str], setting: dict) -> None:
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)
        self.stage868_close_confirm_retry_count: int = 0
        self.stage868_close_confirm_no_retry_count: int = 0

    def _stage847_stop_retry_event_after_open_trade(self, trade: s827.TradeData) -> dict[str, Any] | None:
        if not self.enable_stage868_close_confirm_retry:
            return super()._stage847_stop_retry_event_after_open_trade(trade)

        state = self._find_state_by_contract(trade.vt_symbol)
        if state is None or not state.layers:
            return None

        position_direction = "long" if trade.direction == s827.Direction.LONG else "short"
        if state.direction != position_direction:
            return None

        trade_date = s827._normalize_date(trade.datetime)
        bars = self.stage827_minute_by_symbol.get(str(trade.vt_symbol), pd.DataFrame())
        if bars.empty:
            return None
        entry_day = bars[bars["bar_date"].eq(trade_date)].copy().reset_index(drop=True)
        if entry_day.empty:
            return None

        entry_price = float(trade.price)
        if entry_price <= 0:
            return None

        candidate_indexes: list[int] = []
        risk_prices: list[float] = []
        for index, layer in enumerate(state.layers):
            if layer.direction != position_direction:
                continue
            candidate_indexes.append(index)
            risk_prices.append(abs(entry_price - float(layer.stop_price)))
        if not candidate_indexes:
            return None

        risk_price = max(risk_prices) if risk_prices else 0.0
        min_risk = max(float(self.get_pricetick(trade.vt_symbol)), 1e-9)
        if not np.isfinite(risk_price) or risk_price < min_risk:
            return None

        sign = s827._direction_sign(position_direction)
        stop_price = entry_price - sign * float(self.stage847_stop_retry_r) * risk_price
        progress_price = entry_price + sign * float(self.stage847_stop_retry_r) * risk_price
        first_stop_idx = -1
        first_stop_time = ""
        first_note = ""
        for idx, item in enumerate(entry_day.itertuples(index=False)):
            if position_direction == "long":
                adverse_hit = float(item.low) <= stop_price
                progress_hit = float(item.high) >= progress_price
            else:
                adverse_hit = float(item.high) >= stop_price
                progress_hit = float(item.low) <= progress_price
            if adverse_hit:
                first_stop_idx = idx
                first_stop_time = pd.Timestamp(item.bar_datetime).isoformat()
                first_note = "same_bar_conservative_05r_stop_first" if progress_hit else "0.5R adverse before 0.5R progress"
                break
            if progress_hit:
                return None
        if first_stop_idx < 0:
            return None

        max_retries = max(0, int(self.stage847_max_retries))
        touch_reclaim_idx = -1
        touch_reclaim_time = ""
        close_confirm_idx = -1
        close_confirm_time = ""
        reentry_idx = -1
        reentry_time = ""
        reentry_price = np.nan

        if max_retries > 0:
            for idx in range(first_stop_idx + 1, len(entry_day)):
                item = entry_day.iloc[idx]
                if position_direction == "long":
                    reclaimed = float(item["high"]) >= entry_price
                else:
                    reclaimed = float(item["low"]) <= entry_price
                if reclaimed:
                    touch_reclaim_idx = idx
                    touch_reclaim_time = pd.Timestamp(item["bar_datetime"]).isoformat()
                    break

            for idx in range(first_stop_idx + 1, len(entry_day) - 1):
                item = entry_day.iloc[idx]
                if position_direction == "long":
                    close_confirmed = float(item["close"]) >= entry_price
                else:
                    close_confirmed = float(item["close"]) <= entry_price
                if not close_confirmed:
                    continue
                next_item = entry_day.iloc[idx + 1]
                close_confirm_idx = idx
                close_confirm_time = pd.Timestamp(item["bar_datetime"]).isoformat()
                reentry_idx = idx + 1
                reentry_time = pd.Timestamp(next_item["bar_datetime"]).isoformat()
                reentry_price = float(next_item["open"])
                break

        retry_failed_idx = -1
        retry_failed_time = ""
        if reentry_idx >= 0:
            for idx in range(reentry_idx, len(entry_day)):
                item = entry_day.iloc[idx]
                if position_direction == "long":
                    retry_stop_hit = float(item["low"]) <= stop_price
                else:
                    retry_stop_hit = float(item["high"]) >= stop_price
                if retry_stop_hit:
                    retry_failed_idx = idx
                    retry_failed_time = pd.Timestamp(item["bar_datetime"]).isoformat()
                    break

        contract_vt_symbol = state.contract_vt_symbol
        product_vt_symbol = state.product_vt_symbol
        close_volume = sum(state.layers[index].volume for index in candidate_indexes)
        if close_volume <= 0:
            return None

        synthetic_trades: list[dict[str, Any]] = [
            {
                "action": "close",
                "source": "stage868_intraday_05r_initial_stop",
                "price": stop_price,
                "volume": close_volume,
                "time": first_stop_time,
            }
        ]
        final_state = "flat_no_close_confirm_reentry"
        exit_reason = "stage868_intraday_05r_stop_no_close_confirm_reentry"
        final_exit_price = stop_price

        if reentry_idx >= 0 and np.isfinite(reentry_price) and reentry_price > 0:
            synthetic_trades.append(
                {
                    "action": "open",
                    "source": "stage868_intraday_reentry_next_open_after_close_confirm",
                    "price": reentry_price,
                    "volume": close_volume,
                    "time": reentry_time,
                }
            )
            final_state = "open_after_close_confirm_reentry"
            exit_reason = "stage868_intraday_05r_stop_close_confirm_reentry_open"
            final_exit_price = np.nan
            if retry_failed_idx >= 0:
                synthetic_trades.append(
                    {
                        "action": "close",
                        "source": "stage868_intraday_close_confirm_retry_failed_05r_stop",
                        "price": stop_price,
                        "volume": close_volume,
                        "time": retry_failed_time,
                    }
                )
                final_state = "flat_close_confirm_retry_failed"
                exit_reason = "stage868_intraday_close_confirm_retry_failed_05r_stop"
                final_exit_price = stop_price

        event_bar = getattr(self.strategy_engine, "bars", {}).get(contract_vt_symbol)
        if final_state != "open_after_close_confirm_reentry":
            if len(candidate_indexes) == len(state.layers):
                self._close_all_layers_and_set_flat_target(
                    state,
                    stop_price,
                    execution_price_override=stop_price,
                    exit_reason=exit_reason,
                )
            else:
                self._record_trade_event(
                    bar=event_bar,
                    contract_vt_symbol=contract_vt_symbol,
                    product_vt_symbol=product_vt_symbol,
                    position_direction=position_direction,
                    offset="Close",
                    reason=exit_reason,
                    volume=close_volume,
                    price=stop_price,
                )
                self._close_layers(state, candidate_indexes, stop_price, exit_reason=exit_reason)
                self._apply_state_target(state, execution_price_override=stop_price)

        if reentry_idx >= 0:
            self.stage868_close_confirm_retry_count += 1
        else:
            self.stage868_close_confirm_no_retry_count += 1
        self.stage847_stop_retry_event_count += 1
        event = {
            "datetime": trade.datetime,
            "trade_id": trade.vt_tradeid,
            "vt_symbol": trade.vt_symbol,
            "product_vt_symbol": product_vt_symbol,
            "direction": position_direction,
            "entry_price": entry_price,
            "stop_price": stop_price,
            "progress_price": progress_price,
            "risk_price": risk_price,
            "stop_r": float(self.stage847_stop_retry_r),
            "max_retries": max_retries,
            "volume": close_volume,
            "first_stop_time": first_stop_time,
            "first_stop_bar_index": first_stop_idx,
            "touch_reclaim_time": touch_reclaim_time,
            "touch_reclaim_bar_index": touch_reclaim_idx,
            "close_confirm_time": close_confirm_time,
            "close_confirm_bar_index": close_confirm_idx,
            "reentry_time": reentry_time,
            "reentry_bar_index": reentry_idx,
            "reentry_price": reentry_price,
            "retry_failed_time": retry_failed_time,
            "retry_failed_bar_index": retry_failed_idx,
            "retry_reentered": int(reentry_idx >= 0),
            "retry_touch_reclaim_observed": int(touch_reclaim_idx >= 0),
            "retry_close_confirmed": int(close_confirm_idx >= 0),
            "retry_failed": int(retry_failed_idx >= 0),
            "final_state": final_state,
            "final_exit_price": final_exit_price,
            "note": first_note,
            "exit_reason": exit_reason,
            "synthetic_trades": synthetic_trades,
        }
        self.stage847_stop_retry_events.append(event)
        return event


def _c12_profile(metadata: dict[str, Any]) -> dict[str, Any]:
    profile = s847._c9_profile(metadata)
    spec = profile["spec"]
    capital = replace(
        spec.capital,
        variant=f"{C12_ARM}_2018",
        label="Stage868 Stage819 C9 close-confirm next-open retry",
        note=(
            f"{spec.capital.note} | Stage868 C12. Keep C9 first 0.5R stop, but do not reopen on an intrabar "
            "touch of the original entry. Reopen at the next minute open only after a minute closes back beyond "
            "the original entry level. Retry still uses the original 0.5R stop and is allowed once."
        ),
    )
    overrides = {
        **spec.overrides,
        "enable_stage868_close_confirm_retry": True,
    }
    result = dict(profile)
    result["profile"] = C12_ARM
    result["strategy_cls"] = QmtRollPortfolioStrategyStage868CloseConfirmRetry
    result["spec"] = replace(spec, capital=capital, overrides=overrides, profile=result["profile"])
    return result


def _comparison(summary: pd.DataFrame) -> pd.DataFrame:
    c4 = summary[summary["arm"].eq(C4_ARM)].iloc[0]
    c9 = summary[summary["arm"].eq(C9_ARM)].iloc[0]
    rows: list[dict[str, Any]] = []
    for _, row in summary.iterrows():
        rows.append(
            {
                "arm": row["arm"],
                "end_equity": row["end_equity"],
                "end_equity_delta_vs_C4": row["end_equity"] - c4["end_equity"],
                "end_equity_delta_vs_C9": row["end_equity"] - c9["end_equity"],
                "total_return_pct": row["total_return_pct"],
                "max_dd_pct": row["max_dd_pct"],
                "max_dd_delta_vs_C4": row["max_dd_pct"] - c4["max_dd_pct"],
                "max_dd_delta_vs_C9": row["max_dd_pct"] - c9["max_dd_pct"],
                "sharpe": row["sharpe"],
                "sharpe_delta_vs_C4": row["sharpe"] - c4["sharpe"],
                "sharpe_delta_vs_C9": row["sharpe"] - c9["sharpe"],
                "total_slippage": row["total_slippage"],
                "total_trade_count": row["total_trade_count"],
                "win_rate_pct": row["nonzero_daily_win_rate_pct"],
                "max_broker10_margin_to_equity_pct": row.get("max_broker10_margin_to_equity_pct", np.nan),
                "p95_broker10_margin_to_equity_pct": row.get("p95_broker10_margin_to_equity_pct", np.nan),
            }
        )
    return pd.DataFrame(rows)


def _plot_path(curve: pd.DataFrame) -> None:
    data = curve[curve["arm"].isin([C4_ARM, C9_ARM, C12_ARM])].copy()
    if data.empty:
        return
    data["date"] = pd.to_datetime(data["date"], errors="coerce", format="mixed")
    colors = {C4_ARM: "#16a34a", C9_ARM: "#7c3aed", C12_ARM: "#0f766e"}
    labels = {
        C4_ARM: "C4 broker10 cap",
        C9_ARM: "C9 touch retry",
        C12_ARM: "C12 close-confirm retry",
    }
    fig, axes = plt.subplots(3, 1, figsize=(18, 11), sharex=True, constrained_layout=True)
    for arm, group in data.groupby("arm"):
        group = group.sort_values("date")
        axes[0].plot(group["date"], group["account_equity"], label=labels.get(arm, arm), color=colors.get(arm))
        axes[1].plot(group["date"], group["drawdown_pct"], label=labels.get(arm, arm), color=colors.get(arm))
        axes[2].plot(
            group["date"],
            group["broker10_margin_to_equity_pct"],
            label=labels.get(arm, arm),
            color=colors.get(arm),
        )
    axes[0].set_title("Stage868 equity path")
    axes[1].set_title("Drawdown")
    axes[2].set_title("Broker10 margin/equity pct")
    for ax in axes:
        ax.grid(True, alpha=0.25)
        ax.legend(loc="best")
    fig.savefig(PATH_CHART_PATH, dpi=150)
    plt.close(fig)


def _event_summary(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    data = events.copy()
    data["datetime"] = pd.to_datetime(data["datetime"], errors="coerce")
    data["year"] = data["datetime"].dt.year
    for column in [
        "volume",
        "retry_reentered",
        "retry_touch_reclaim_observed",
        "retry_close_confirmed",
        "retry_failed",
        "entry_price",
    ]:
        data[column] = pd.to_numeric(data.get(column, 0), errors="coerce").fillna(0.0)
    data["reentry_price"] = pd.to_numeric(data.get("reentry_price"), errors="coerce")
    data["reentry_price_minus_entry"] = np.where(
        data["reentry_price"].gt(0),
        data["reentry_price"] - data["entry_price"],
        np.nan,
    )
    return (
        data.groupby(["profile", "final_state"], dropna=False)
        .agg(
            events=("vt_symbol", "size"),
            volume=("volume", "sum"),
            touch_reclaim_observed=("retry_touch_reclaim_observed", "sum"),
            close_confirmed=("retry_close_confirmed", "sum"),
            reentered=("retry_reentered", "sum"),
            retry_failed=("retry_failed", "sum"),
            median_reentry_price_minus_entry=("reentry_price_minus_entry", "median"),
        )
        .reset_index()
    )


def _plot_event_atlas(events: pd.DataFrame, minute_bars: pd.DataFrame) -> tuple[list[Path], pd.DataFrame]:
    if events.empty:
        return [], pd.DataFrame()
    selected = events[
        events["final_state"]
        .astype(str)
        .isin(["flat_no_close_confirm_reentry", "flat_close_confirm_retry_failed", "open_after_close_confirm_reentry"])
    ].copy()
    if selected.empty:
        return [], pd.DataFrame()
    selected["datetime"] = pd.to_datetime(selected["datetime"], errors="coerce")
    selected["reentry_price"] = pd.to_numeric(selected.get("reentry_price"), errors="coerce")
    selected = (
        selected.sort_values(["final_state", "first_stop_bar_index"], ascending=[True, True])
        .head(12)
        .reset_index(drop=True)
    )
    minute_by_symbol = s825._minute_groups(minute_bars)
    paths: list[Path] = []
    manifest: list[dict[str, Any]] = []
    per_page = 3
    for page_start in range(0, len(selected), per_page):
        page_rows = selected.iloc[page_start : page_start + per_page]
        page = page_start // per_page + 1
        fig, axes = plt.subplots(per_page, 1, figsize=(16, 4.2 * per_page), constrained_layout=True)
        if per_page == 1:
            axes = [axes]
        for ax, (_, row) in zip(axes, page_rows.iterrows()):
            vt_symbol = str(row["vt_symbol"])
            entry_dt = pd.Timestamp(row["datetime"]).tz_localize(None).normalize()
            bars = minute_by_symbol.get(vt_symbol, pd.DataFrame())
            day = pd.DataFrame()
            if not bars.empty:
                day = bars[pd.to_datetime(bars["bar_date"], errors="coerce").dt.normalize().eq(entry_dt)].copy()
            if day.empty:
                ax.text(0.5, 0.5, f"missing minute bars {vt_symbol} {entry_dt:%Y-%m-%d}", ha="center", va="center")
                ax.set_axis_off()
            else:
                day = day.sort_values("bar_datetime")
                ax.plot(day["bar_datetime"], day["close"], color="#ef4444", linewidth=0.8, alpha=0.65)
                entry_price = _safe_float(row.get("entry_price"))
                reentry_price = _safe_float(row.get("reentry_price"))
                stop_price = _safe_float(row.get("stop_price"))
                progress_price = _safe_float(row.get("progress_price"))
                if np.isfinite(entry_price):
                    ax.axhline(entry_price, color="#2563eb", linewidth=0.9, label="entry")
                if np.isfinite(reentry_price):
                    ax.axhline(reentry_price, color="#0f766e", linewidth=0.85, label="next-open reentry")
                if np.isfinite(stop_price):
                    ax.axhline(stop_price, color="#dc2626", linestyle="--", linewidth=0.9, label="0.5R stop")
                if np.isfinite(progress_price):
                    ax.axhline(progress_price, color="#16a34a", linestyle="--", linewidth=0.85, label="0.5R progress")
                for key, color, label in [
                    ("first_stop_time", "#dc2626", "first stop"),
                    ("touch_reclaim_time", "#7c3aed", "touch reclaim"),
                    ("close_confirm_time", "#f59e0b", "close confirm"),
                    ("reentry_time", "#0f766e", "next open reentry"),
                    ("retry_failed_time", "#7c2d12", "retry fail"),
                ]:
                    value = row.get(key)
                    if pd.notna(value) and str(value):
                        ax.axvline(pd.Timestamp(value), color=color, alpha=0.55, linewidth=0.8, label=label)
                ax.grid(True, alpha=0.18)
                ax.legend(loc="best", fontsize=8)
            ax.set_title(
                f"{vt_symbol} {row.get('direction')} {entry_dt:%Y-%m-%d} {row.get('final_state')} "
                f"reentry={_safe_float(row.get('reentry_price')):.2f}"
            )
            manifest.append(
                {
                    "page": page,
                    "vt_symbol": vt_symbol,
                    "direction": row.get("direction"),
                    "entry_date": entry_dt.date().isoformat(),
                    "final_state": row.get("final_state"),
                    "touch_reclaim_time": row.get("touch_reclaim_time", ""),
                    "close_confirm_time": row.get("close_confirm_time", ""),
                    "reentry_time": row.get("reentry_time", ""),
                    "retry_failed_time": row.get("retry_failed_time", ""),
                    "entry_price": _safe_float(row.get("entry_price")),
                    "reentry_price": _safe_float(row.get("reentry_price")),
                }
            )
        for ax in axes[len(page_rows) :]:
            ax.set_axis_off()
        path = Path(str(ATLAS_TEMPLATE).format(page=page))
        fig.suptitle("Stage868 close-confirm retry minute-K atlas", fontsize=13)
        fig.savefig(path, dpi=150)
        plt.close(fig)
        paths.append(path)
    manifest_df = pd.DataFrame(manifest)
    manifest_df.to_csv(ATLAS_MANIFEST_PATH, index=False, encoding="utf-8-sig")
    return paths, manifest_df


def _write_report(comparison: pd.DataFrame, event_summary: pd.DataFrame, atlas_paths: list[Path]) -> None:
    lines = [
        "# Stage868 close-confirm next-open retry 真实引擎",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 源候选：`{stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION}`",
        "- 阶段性质：研究线内冻结 A/C；不改正式版、不改候选配置、不连接 CTP、不调用下单。",
        "",
        "## 外部调研判断",
        "",
        "- vn.py GitHub：https://github.com/vnpy/vnpy",
        "- Backtrader order execution docs：https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/",
        "- Klement, Assessing Stop-Loss and Re-Entry Strategies：https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2466252",
        "- 我的判断：止损策略不能只评估离场，还必须同时定义可执行再入场；Stage868 不使用未来二次失败标签，只把 C9 的触碰重试改成更保守的收盘确认后下一分钟开盘重试。",
        "",
        "## 预声明臂",
        "",
        "- A：C4，即 Stage830 C2 + broker10 projected `100%` entry cap。",
        "- B：C9，即 Stage847 C4 + `0.5R` stop-first + 原入场价触碰 reclaim 后允许一次重试。",
        "- C：C12，即 C9 的首次 `0.5R` 止损不变，但只有后续一分钟收盘重新站回原入场价，才在下一分钟开盘重试一次。",
        "",
        "## Result",
        "",
        _md_table(comparison, max_rows=10),
        "",
        "## Event Summary",
        "",
        _md_table(event_summary, max_rows=30),
        "",
        "## Visuals",
        "",
        f"- path chart：`{PATH_CHART_PATH}`",
        *[f"- atlas page：`{path}`" for path in atlas_paths],
        "",
        "## Judgment",
        "",
        "- 若 C12 不能在 C9 基础上改善收益、回撤和 broker10，说明“更慢的 reclaim 确认”不是当前矛盾，应停止该分支。",
        "- 若 C12 改善 C9，再做滚动起点和成本压力；本阶段不直接进入正式候选或正式 A/B。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    metadata = s513._metadata()
    vt_symbols = set(str(item) for item in metadata["vt_symbols"])
    minute_bars = s863._load_stage861_full_minute_bars(vt_symbols)
    s827._GLOBAL_MINUTE_BY_SYMBOL = s825._minute_groups(minute_bars)

    profiles = [s830._cap_profile(metadata), s847._c9_profile(metadata), _c12_profile(metadata)]
    summaries: list[pd.DataFrame] = []
    curves: list[pd.DataFrame] = []
    merged_frames: dict[str, list[pd.DataFrame]] = {
        "trades": [],
        "entry_risk": [],
        "entry_candidates": [],
        "trade_events": [],
        "intraday_events": [],
        "stop_retry_events": [],
    }
    closed_frames: list[pd.DataFrame] = []

    for profile in profiles:
        combined, frames = s863._run_profile(profile, metadata)
        summary, curve = s827._metric(profile, combined)
        summary["arm"] = profile["profile"]
        curve["arm"] = profile["profile"]
        summaries.append(summary)
        curves.append(curve)
        for key in merged_frames:
            frame = frames.get(key, pd.DataFrame())
            if not frame.empty:
                merged_frames[key].append(frame)
        trades = frames.get("trades", pd.DataFrame()).copy()
        entry_risk = frames.get("entry_risk", pd.DataFrame()).copy()
        entry_candidates = frames.get("entry_candidates", pd.DataFrame()).copy()
        closed = s719._build_closed_lots(trades, entry_risk, entry_candidates, metadata)
        if not closed.empty:
            closed["arm"] = profile["profile"]
            closed["variant"] = profile["spec"].capital.variant
            closed_frames.append(closed)

    summary = pd.concat(summaries, ignore_index=True, sort=False)
    curve = pd.concat(curves, ignore_index=True, sort=False)
    comparison = _comparison(summary)
    output_frames = {
        key: pd.concat(value, ignore_index=True, sort=False) if value else pd.DataFrame()
        for key, value in merged_frames.items()
    }
    output_frames["closed_lots"] = pd.concat(closed_frames, ignore_index=True, sort=False) if closed_frames else pd.DataFrame()
    event_summary = _event_summary(output_frames["stop_retry_events"])
    atlas_paths, atlas_manifest = _plot_event_atlas(output_frames["stop_retry_events"], minute_bars)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    curve.to_csv(CURVE_PATH, index=False, encoding="utf-8-sig")
    output_frames["trades"].to_csv(TRADES_PATH, index=False, encoding="utf-8-sig")
    output_frames["entry_risk"].to_csv(ENTRY_RISK_PATH, index=False, encoding="utf-8-sig")
    output_frames["entry_candidates"].to_csv(ENTRY_CANDIDATES_PATH, index=False, encoding="utf-8-sig")
    output_frames["trade_events"].to_csv(TRADE_EVENTS_PATH, index=False, encoding="utf-8-sig")
    output_frames["intraday_events"].to_csv(INTRADAY_EVENTS_PATH, index=False, encoding="utf-8-sig")
    output_frames["stop_retry_events"].to_csv(STOP_RETRY_EVENTS_PATH, index=False, encoding="utf-8-sig")
    output_frames["closed_lots"].to_csv(CLOSED_LOTS_PATH, index=False, encoding="utf-8-sig")
    event_summary.to_csv(EVENT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    _plot_path(curve)
    _write_report(comparison, event_summary, atlas_paths)

    c12_row = comparison[comparison["arm"].eq(C12_ARM)].iloc[0].to_dict()
    c9_row = comparison[comparison["arm"].eq(C9_ARM)].iloc[0].to_dict()
    c12_events = output_frames["stop_retry_events"][output_frames["stop_retry_events"]["profile"].astype(str).eq(C12_ARM)].copy()
    changed_vs_c9 = any(
        abs(float(c12_row[column])) > 1e-9 for column in ["end_equity_delta_vs_C9", "max_dd_delta_vs_C9", "sharpe_delta_vs_C9"]
    )
    c12_beats_c9_return = float(c12_row["end_equity_delta_vs_C9"]) >= 0
    c12_repairs_c9_dd = float(c12_row["max_dd_delta_vs_C9"]) >= 0
    c12_repairs_c9_broker = float(c12_row["max_broker10_margin_to_equity_pct"]) <= float(
        c9_row["max_broker10_margin_to_equity_pct"]
    )
    decision_label = (
        "stage868_close_confirm_retry_promising_needs_stress"
        if changed_vs_c9 and c12_beats_c9_return and c12_repairs_c9_dd and c12_repairs_c9_broker
        else "stage868_close_confirm_retry_not_promoted"
    )
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "source_candidate": stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION,
        "strategy_changed": False,
        "ctp_connected": False,
        "order_api_called": False,
        "formal_ab_triggered": False,
        "minute_source": {
            "stage861_full_minute_bars": str(s861.FULL_MINUTE_BARS_PATH),
            "loaded_minute_bars": int(len(minute_bars)),
            "loaded_symbols": int(minute_bars["vt_symbol"].astype(str).nunique()) if not minute_bars.empty else 0,
        },
        "rule_type": "live_feasible_close_confirm_next_open_retry",
        "rule": {
            "base_arm": C9_ARM,
            "first_stop_r": s847.STOP_RETRY_R,
            "max_retries": s847.MAX_RETRIES,
            "reclaim_confirmation": "minute_close_beyond_original_entry",
            "reentry_execution": "next_minute_open_after_close_confirm",
            "retry_stop": "original_0.5R_stop",
            "no_parameter_scan": True,
            "future_retry_failure_label_rejected": True,
        },
        "event_summary": {
            "c12_stop_retry_events": int(len(c12_events)),
            "c12_touch_reclaim_observed": int(pd.to_numeric(c12_events.get("retry_touch_reclaim_observed", 0), errors="coerce").fillna(0).sum())
            if not c12_events.empty
            else 0,
            "c12_close_confirm_reentries": int(pd.to_numeric(c12_events.get("retry_reentered", 0), errors="coerce").fillna(0).sum())
            if not c12_events.empty
            else 0,
            "c12_retry_failed": int(pd.to_numeric(c12_events.get("retry_failed", 0), errors="coerce").fillna(0).sum())
            if not c12_events.empty
            else 0,
        },
        "comparison": comparison.to_dict("records"),
        "event_summary_table": event_summary.to_dict("records"),
        "decision": decision_label,
        "candidate_result": c12_row,
        "overfit_reflection": (
            "不是参数过拟合。本阶段只把 C9 的触碰 reclaim 重试改为收盘确认后下一分钟开盘重试；"
            "没有扫确认窗口、R、阈值、品种、方向或年份。"
        ),
        "continue_value": (
            "若 C12 不能改善 C9，说明重试质量不能靠更慢的 close confirm 解决，应停止该分支并换新结构。"
        ),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "comparison": str(COMPARISON_PATH),
            "curve": str(CURVE_PATH),
            "trades": str(TRADES_PATH),
            "entry_risk": str(ENTRY_RISK_PATH),
            "entry_candidates": str(ENTRY_CANDIDATES_PATH),
            "trade_events": str(TRADE_EVENTS_PATH),
            "intraday_events": str(INTRADAY_EVENTS_PATH),
            "stop_retry_events": str(STOP_RETRY_EVENTS_PATH),
            "closed_lots": str(CLOSED_LOTS_PATH),
            "event_summary": str(EVENT_SUMMARY_PATH),
            "path_chart": str(PATH_CHART_PATH),
            "atlas_manifest": str(ATLAS_MANIFEST_PATH),
            "atlas_pages": [str(path) for path in atlas_paths],
            "report": str(REPORT_PATH),
        },
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print("comparison")
    print(comparison.to_string(index=False))
    print("event_summary")
    print(event_summary.to_string(index=False) if not event_summary.empty else "empty")


if __name__ == "__main__":
    main()
