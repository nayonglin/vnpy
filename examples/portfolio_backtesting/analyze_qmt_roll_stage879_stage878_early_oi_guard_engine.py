from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
import math
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
STAGE = "Stage879"
MODEL_TAG = "stage879_stage878_early_oi_guard_engine_v1"
OUTPUT_PREFIX = "qmt_roll_stage879_stage878_early_oi_guard_engine"

C4_ARM = s830.CAP_ARM
C9_ARM = s847.C9_ARM
C15_ARM = "stage879_stage819_c9_early_oi_down_no_progress_guard"

START = s847.START
END = s847.END
EARLY_BARS = 60
MIN_EARLY_BARS = 60
EARLY_GUARD_R = 0.5
PER_PAGE = 4
MAX_ATLAS_ROWS = 16

STAGE863_PREFIX = "qmt_roll_stage863_stage847_c10_budget_lock_engine"
STAGE863_TAG = "stage863_stage847_c10_budget_lock_engine_v1"
STAGE863_SUMMARY_PATH = OUTPUT_DIR / f"{STAGE863_PREFIX}_summary_{STAGE863_TAG}.csv"
STAGE863_CURVE_PATH = OUTPUT_DIR / f"{STAGE863_PREFIX}_curve_{STAGE863_TAG}.csv"

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
        if pd.isna(value):
            return default
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if np.isfinite(number) else default


def _load_required_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


class QmtRollPortfolioStrategyStage879EarlyOiGuard(s847.QmtRollPortfolioStrategyStage847C9StopRetry):
    enable_stage879_early_oi_down_no_progress_guard: bool = False
    stage879_early_bars: int = EARLY_BARS
    stage879_early_guard_r: float = EARLY_GUARD_R

    parameters = s847.QmtRollPortfolioStrategyStage847C9StopRetry.parameters + [
        "enable_stage879_early_oi_down_no_progress_guard",
        "stage879_early_bars",
        "stage879_early_guard_r",
    ]
    variables = s847.QmtRollPortfolioStrategyStage847C9StopRetry.variables + [
        "stage879_early_oi_guard_count",
    ]

    def __init__(self, strategy_engine, strategy_name: str, vt_symbols: list[str], setting: dict) -> None:
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)
        self.stage879_early_oi_guard_count: int = 0

    def _stage847_stop_retry_event_after_open_trade(self, trade: s827.TradeData) -> dict[str, Any] | None:
        c9_event = super()._stage847_stop_retry_event_after_open_trade(trade)
        if c9_event:
            c9_event["stage879_early_oi_guard_checked"] = 0
            return c9_event
        if not bool(self.enable_stage879_early_oi_down_no_progress_guard):
            return None
        return self._stage879_early_oi_guard_event_after_open_trade(trade)

    def _stage879_early_oi_guard_event_after_open_trade(self, trade: s827.TradeData) -> dict[str, Any] | None:
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
        entry_day = bars[bars["bar_date"].eq(trade_date)].copy().sort_values("bar_datetime").reset_index(drop=True)
        if len(entry_day) < int(self.stage879_early_bars):
            return None
        early = entry_day.head(int(self.stage879_early_bars)).reset_index(drop=True)

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
        progress_price = entry_price + sign * float(self.stage879_early_guard_r) * risk_price
        progress_hit = False
        for item in early.itertuples(index=False):
            if position_direction == "long":
                progress_hit = float(item.high) >= progress_price
            else:
                progress_hit = float(item.low) <= progress_price
            if progress_hit:
                break
        if progress_hit:
            return None

        first_open = _safe_float(early.iloc[0].get("open"))
        early_close = _safe_float(early.iloc[-1].get("close"))
        first_oi = _safe_float(early.iloc[0].get("open_oi"))
        last_oi = _safe_float(early.iloc[-1].get("close_oi"))
        if first_open <= 0 or early_close <= 0 or first_oi <= 0 or last_oi <= 0:
            return None
        price_dir_return = sign * (early_close / first_open - 1.0)
        oi_change = (last_oi - first_oi) / first_oi
        if not (price_dir_return < 0 and oi_change < 0):
            return None

        contract_vt_symbol = state.contract_vt_symbol
        product_vt_symbol = state.product_vt_symbol
        close_volume = sum(state.layers[index].volume for index in candidate_indexes)
        if close_volume <= 0:
            return None

        exit_time = pd.Timestamp(early.iloc[-1]["bar_datetime"]).isoformat()
        exit_reason = "stage879_early60_adverse_price_oi_down_no_progress_exit"
        if len(candidate_indexes) == len(state.layers):
            self._close_all_layers_and_set_flat_target(
                state,
                early_close,
                execution_price_override=early_close,
                exit_reason=exit_reason,
            )
        else:
            event_bar = getattr(self.strategy_engine, "bars", {}).get(contract_vt_symbol)
            self._record_trade_event(
                bar=event_bar,
                contract_vt_symbol=contract_vt_symbol,
                product_vt_symbol=product_vt_symbol,
                position_direction=position_direction,
                offset="Close",
                reason=exit_reason,
                volume=close_volume,
                price=early_close,
            )
            self._close_layers(state, candidate_indexes, early_close, exit_reason=exit_reason)
            self._apply_state_target(state, execution_price_override=early_close)

        self.stage847_stop_retry_event_count += 1
        self.stage879_early_oi_guard_count += 1
        event = {
            "datetime": trade.datetime,
            "trade_id": trade.vt_tradeid,
            "vt_symbol": trade.vt_symbol,
            "product_vt_symbol": product_vt_symbol,
            "direction": position_direction,
            "entry_price": entry_price,
            "stop_price": np.nan,
            "progress_price": progress_price,
            "risk_price": risk_price,
            "stop_r": float(self.stage879_early_guard_r),
            "max_retries": int(self.stage847_max_retries),
            "volume": close_volume,
            "first_stop_time": "",
            "first_stop_bar_index": -1,
            "reentry_time": "",
            "reentry_bar_index": -1,
            "retry_failed_time": "",
            "retry_failed_bar_index": -1,
            "retry_reentered": 0,
            "retry_failed": 0,
            "final_state": "flat_early_oi_down_no_progress",
            "final_exit_price": early_close,
            "note": "early60 adverse price direction plus OI down, no +0.5R progress",
            "exit_reason": exit_reason,
            "stage879_early_oi_guard_checked": 1,
            "stage879_early_state": "adverse_price_oi_down",
            "stage879_early_bars": int(len(early)),
            "stage879_early_exit_time": exit_time,
            "stage879_early_exit_bar_index": int(len(early) - 1),
            "stage879_early_price_dir_return_pct": float(price_dir_return * 100.0),
            "stage879_early_oi_change_pct": float(oi_change * 100.0),
            "stage879_progress_hit_early": 0,
            "synthetic_trades": [
                {
                    "action": "close",
                    "source": "stage879_early_oi_down_no_progress_exit",
                    "price": early_close,
                    "volume": close_volume,
                    "time": exit_time,
                }
            ],
        }
        self.stage847_stop_retry_events.append(event)
        return event


def _c15_profile(metadata: dict[str, Any]) -> dict[str, Any]:
    profile = s847._c9_profile(metadata)
    spec = profile["spec"]
    capital = replace(
        spec.capital,
        variant=f"{C15_ARM}_2018",
        label="Stage879 Stage819 C9 plus early OI-down no-progress guard",
        note=(
            f"{spec.capital.note} | Stage879 C15. Keep C9 stop/retry. If the first 60 entry-day minute bars "
            "do not touch +0.5R progress and end with price against signal plus OI down, close at the 60th "
            "bar close and do not retry that same entry attempt."
        ),
    )
    overrides = {
        **spec.overrides,
        "enable_stage879_early_oi_down_no_progress_guard": True,
        "stage879_early_bars": EARLY_BARS,
        "stage879_early_guard_r": EARLY_GUARD_R,
    }
    result = dict(profile)
    result["profile"] = C15_ARM
    result["strategy_cls"] = QmtRollPortfolioStrategyStage879EarlyOiGuard
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
    data = curve[curve["arm"].isin([C4_ARM, C9_ARM, C15_ARM])].copy()
    if data.empty:
        return
    data["date"] = pd.to_datetime(data["date"], errors="coerce", format="mixed")
    fig, axes = plt.subplots(3, 1, figsize=(18, 11), sharex=True, constrained_layout=True)
    colors = {C4_ARM: "#16a34a", C9_ARM: "#7c3aed", C15_ARM: "#0f766e"}
    labels = {
        C4_ARM: "C4 broker10 cap",
        C9_ARM: "C9 0.5R stop + retry",
        C15_ARM: "C15 early OI guard",
    }
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
    axes[0].set_title("Stage879 equity path")
    axes[1].set_title("Drawdown")
    axes[2].set_title("Broker10 margin to equity pct")
    for ax in axes:
        ax.grid(True, alpha=0.25)
        ax.legend(loc="best")
    fig.savefig(PATH_CHART_PATH, dpi=150)
    plt.close(fig)


def _event_summary(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    data = events.copy()
    for column in ["stage879_early_oi_guard_checked", "retry_reentered", "retry_failed", "volume"]:
        if column not in data.columns:
            data[column] = 0
        data[column] = pd.to_numeric(data[column], errors="coerce").fillna(0)
    rows: list[dict[str, Any]] = []
    for state, group in data.groupby("final_state", dropna=False):
        rows.append(
            {
                "final_state": str(state),
                "events": int(len(group)),
                "early_oi_guard_events": int(group["stage879_early_oi_guard_checked"].sum()),
                "volume": float(group["volume"].sum()),
                "reentered": int(group["retry_reentered"].sum()),
                "retry_failed": int(group["retry_failed"].sum()),
                "median_early_price_dir_return_pct": float(
                    pd.to_numeric(group.get("stage879_early_price_dir_return_pct"), errors="coerce").median()
                ),
                "median_early_oi_change_pct": float(
                    pd.to_numeric(group.get("stage879_early_oi_change_pct"), errors="coerce").median()
                ),
            }
        )
    return pd.DataFrame(rows).sort_values("events", ascending=False).reset_index(drop=True)


def _select_atlas_events(events: pd.DataFrame, closed_lots: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    data = events[events["profile"].astype(str).eq(C15_ARM)].copy()
    data = data[data["final_state"].astype(str).eq("flat_early_oi_down_no_progress")]
    if data.empty:
        return pd.DataFrame()
    data["entry_date"] = pd.to_datetime(data["datetime"], errors="coerce").map(
        lambda value: s827._normalize_date(value) if pd.notna(value) else pd.NaT
    )
    lots = closed_lots.copy()
    if not lots.empty:
        lots = lots[lots["arm"].astype(str).eq(C15_ARM)].copy()
        lots["entry_date_norm"] = pd.to_datetime(lots["entry_date"], errors="coerce").map(
            lambda value: s827._normalize_date(value) if pd.notna(value) else pd.NaT
        )
        lots["event_key"] = (
            lots["vt_symbol"].astype(str)
            + "|"
            + lots["direction"].astype(str)
            + "|"
            + lots["entry_date_norm"].dt.strftime("%Y-%m-%d")
        )
        data["event_key"] = (
            data["vt_symbol"].astype(str)
            + "|"
            + data["direction"].astype(str)
            + "|"
            + data["entry_date"].dt.strftime("%Y-%m-%d")
        )
        data = data.merge(
            lots[["event_key", "realized_pnl", "r_multiple", "exit_reason"]].drop_duplicates("event_key"),
            on="event_key",
            how="left",
        )
    data["sort_pnl"] = pd.to_numeric(data.get("realized_pnl"), errors="coerce").fillna(0.0)
    losses = data.sort_values("sort_pnl").head(8)
    winners = data.sort_values("sort_pnl", ascending=False).head(8)
    return pd.concat([losses, winners], ignore_index=True, sort=False).drop_duplicates(
        ["vt_symbol", "entry_date", "direction"]
    ).head(MAX_ATLAS_ROWS)


def _plot_event_atlas(events: pd.DataFrame, closed_lots: pd.DataFrame, minute_bars: pd.DataFrame) -> tuple[list[Path], pd.DataFrame]:
    selected = _select_atlas_events(events, closed_lots)
    if selected.empty:
        return [], pd.DataFrame()
    minute_by_symbol = s825._minute_groups(minute_bars)
    pages = int(math.ceil(len(selected) / PER_PAGE))
    paths: list[Path] = []
    manifest: list[dict[str, Any]] = []
    for page in range(1, pages + 1):
        part = selected.iloc[(page - 1) * PER_PAGE : page * PER_PAGE].copy()
        fig, axes = plt.subplots(len(part), 1, figsize=(18, max(4.0, 3.5 * len(part))), constrained_layout=True)
        for ax, (_, row) in zip(list(np.atleast_1d(axes)), part.iterrows(), strict=False):
            vt_symbol = str(row["vt_symbol"])
            entry_date = s827._normalize_date(row["entry_date"])
            direction = str(row["direction"])
            day = minute_by_symbol.get(vt_symbol, pd.DataFrame())
            day = (
                day[day["bar_date"].eq(entry_date)].copy().sort_values("bar_datetime").head(280).reset_index(drop=True)
                if not day.empty
                else pd.DataFrame()
            )
            if day.empty:
                ax.axis("off")
                ax.text(0.5, 0.5, f"missing minute bars {vt_symbol} {entry_date:%Y-%m-%d}", ha="center", va="center")
            else:
                s825._plot_candles(ax, day)
                for price_col, color, label in [
                    ("entry_price", "#2563eb", "entry"),
                    ("progress_price", "#16a34a", "+0.5R progress"),
                    ("final_exit_price", "#dc2626", "early OI exit"),
                ]:
                    price = _safe_float(row.get(price_col))
                    if np.isfinite(price):
                        ax.axhline(price, color=color, linestyle="--" if price_col != "entry_price" else "-", linewidth=0.9, label=label)
                exit_time = pd.to_datetime(row.get("stage879_early_exit_time"), errors="coerce")
                if pd.notna(exit_time):
                    matches = day.index[pd.to_datetime(day["bar_datetime"], errors="coerce").eq(exit_time)]
                    if len(matches):
                        ax.axvline(int(matches[0]), color="#dc2626", linewidth=0.95, alpha=0.85, label="60th bar exit")
                ax.axvspan(0, min(EARLY_BARS - 1, len(day) - 1), color="#fef3c7", alpha=0.18)
                ticks = np.linspace(0, len(day) - 1, num=min(8, len(day)), dtype=int)
                ax.set_xticks(ticks)
                ax.set_xticklabels([pd.Timestamp(day.loc[pos, "bar_datetime"]).strftime("%H:%M") for pos in ticks], fontsize=7)
                handles, labels = ax.get_legend_handles_labels()
                if handles:
                    dedup = dict(zip(labels, handles))
                    ax.legend(dedup.values(), dedup.keys(), loc="best", fontsize=7)
                ax.grid(True, alpha=0.18)
            ax.set_title(
                f"{vt_symbol} {direction} {entry_date:%Y-%m-%d} pnl={_safe_float(row.get('realized_pnl')):,.0f} "
                f"R={_safe_float(row.get('r_multiple')):.2f} "
                f"price60={_safe_float(row.get('stage879_early_price_dir_return_pct')):.2f}% "
                f"oi60={_safe_float(row.get('stage879_early_oi_change_pct')):.2f}%",
                fontsize=8.1,
                loc="left",
            )
            manifest.append(
                {
                    "page": page,
                    "vt_symbol": vt_symbol,
                    "entry_date": entry_date.strftime("%Y-%m-%d"),
                    "direction": direction,
                    "final_state": row.get("final_state", ""),
                    "realized_pnl": _safe_float(row.get("realized_pnl")),
                    "r_multiple": _safe_float(row.get("r_multiple")),
                    "early_price_dir_return_pct": _safe_float(row.get("stage879_early_price_dir_return_pct")),
                    "early_oi_change_pct": _safe_float(row.get("stage879_early_oi_change_pct")),
                    "early_exit_time": row.get("stage879_early_exit_time", ""),
                }
            )
        fig.suptitle("Stage879 early OI guard minute-K atlas", fontsize=13)
        path = Path(str(ATLAS_TEMPLATE).format(page=page))
        fig.savefig(path, dpi=150)
        plt.close(fig)
        paths.append(path)
    return paths, pd.DataFrame(manifest)


def _write_report(
    comparison: pd.DataFrame,
    event_summary: pd.DataFrame,
    atlas_paths: list[Path],
    decision_label: str,
) -> None:
    lines = [
        "# Stage879 Stage878 早段 OI 参与度真实引擎审计",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 源候选：`{stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION}`",
        "- 阶段性质：冻结真实引擎审计；不改官方正式版、不改官方候选配置、不连接 CTP、不调用下单。",
        "",
        "## 外部调研判断",
        "",
        "- CME open interest education：OI 反映未平仓合约数量，是价格之外的一阶参与度信息。",
        "- Turtle/趋势跟随资料：右尾来自持续持有，止损纪律不能频繁按失败样本救参。",
        "- vn.py GitHub：策略候选必须落到可复现组合回测引擎，而不是只看 lot-level 代理。",
        "- 我的判断：Stage878 证明 `favorable_price_oi_up` 是右尾核心；因此本阶段只测试最窄的 `adverse_price_oi_down + no progress`，并显式保护早段顺向、OI上升和已到 `+0.5R` 的路径。",
        "",
        "## 冻结规则",
        "",
        "- A：C4，即 Stage830 broker10 入口 cap。",
        "- B：C9，即 Stage847 C4 + `0.5R` stop/retry once。",
        "- C：C15，即 C9 保持不变；若入场日最早 `60` 根1分钟K没有触达 `+0.5R` progress，且第 `60` 根时信号方向价格收益为负、OI变化为负，则按第 `60` 根收盘价退出，当天不重试。",
        "- 不扫描分钟窗口、OI阈值、成交量阈值、品种、方向或年份。",
        "",
        "## Result",
        "",
        _md_table(comparison, max_rows=10),
        "",
        "## Event Summary",
        "",
        _md_table(event_summary, max_rows=30),
        "",
        "## Charts",
        "",
        f"- path chart：`{PATH_CHART_PATH}`",
        *[f"- atlas：`{path}`" for path in atlas_paths],
        "",
        "## Judgment",
        "",
        f"- 决策：`{decision_label}`",
        "- 若 C15 不能同时改善 C9 的收益、回撤、Sharpe 和 broker10，说明早段 OI-down no-progress 仍会误伤或无效，应停止该真实引擎分支。",
        "- 若 C15 通过，才允许进入滚动起点、成本压力和 broker10 深审计；本阶段不直接进入官方候选或 A/B。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stage863_summary = _load_required_csv(STAGE863_SUMMARY_PATH)
    stage863_curve = _load_required_csv(STAGE863_CURVE_PATH)

    metadata = s513._metadata()
    vt_symbols = set(str(item) for item in metadata["vt_symbols"])
    minute_bars = s863._load_stage861_full_minute_bars(vt_symbols)
    s827._GLOBAL_MINUTE_BY_SYMBOL = s825._minute_groups(minute_bars)

    profile = _c15_profile(metadata)
    combined, frames = s863._run_profile(profile, metadata)
    c15_summary, c15_curve = s827._metric(profile, combined)
    c15_summary["arm"] = C15_ARM
    c15_curve["arm"] = C15_ARM

    trades = frames.get("trades", pd.DataFrame()).copy()
    entry_risk = frames.get("entry_risk", pd.DataFrame()).copy()
    entry_candidates = frames.get("entry_candidates", pd.DataFrame()).copy()
    trade_events = frames.get("trade_events", pd.DataFrame()).copy()
    intraday_events = frames.get("intraday_events", pd.DataFrame()).copy()
    stop_retry_events = frames.get("stop_retry_events", pd.DataFrame()).copy()
    closed_lots = s719._build_closed_lots(trades, entry_risk, entry_candidates, metadata)
    if not closed_lots.empty:
        closed_lots["arm"] = C15_ARM
        closed_lots["variant"] = profile["spec"].capital.variant

    summary = pd.concat(
        [
            stage863_summary[stage863_summary["arm"].isin([C4_ARM, C9_ARM])],
            c15_summary,
        ],
        ignore_index=True,
        sort=False,
    )
    curve = pd.concat(
        [
            stage863_curve[stage863_curve["arm"].isin([C4_ARM, C9_ARM])],
            c15_curve,
        ],
        ignore_index=True,
        sort=False,
    )
    comparison = _comparison(summary)
    event_summary = _event_summary(stop_retry_events)
    atlas_paths, atlas_manifest = _plot_event_atlas(stop_retry_events, closed_lots, minute_bars)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    curve.to_csv(CURVE_PATH, index=False, encoding="utf-8-sig")
    trades.to_csv(TRADES_PATH, index=False, encoding="utf-8-sig")
    entry_risk.to_csv(ENTRY_RISK_PATH, index=False, encoding="utf-8-sig")
    entry_candidates.to_csv(ENTRY_CANDIDATES_PATH, index=False, encoding="utf-8-sig")
    trade_events.to_csv(TRADE_EVENTS_PATH, index=False, encoding="utf-8-sig")
    intraday_events.to_csv(INTRADAY_EVENTS_PATH, index=False, encoding="utf-8-sig")
    stop_retry_events.to_csv(STOP_RETRY_EVENTS_PATH, index=False, encoding="utf-8-sig")
    closed_lots.to_csv(CLOSED_LOTS_PATH, index=False, encoding="utf-8-sig")
    event_summary.to_csv(EVENT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    atlas_manifest.to_csv(ATLAS_MANIFEST_PATH, index=False, encoding="utf-8-sig")
    _plot_path(curve)

    c15_row = comparison[comparison["arm"].eq(C15_ARM)].iloc[0].to_dict()
    c9_row = comparison[comparison["arm"].eq(C9_ARM)].iloc[0].to_dict()
    early_guard_events = int(
        pd.to_numeric(stop_retry_events.get("stage879_early_oi_guard_checked", 0), errors="coerce").fillna(0).sum()
    )
    c15_changed_c9 = any(
        abs(float(c15_row[column])) > 1e-9
        for column in ["end_equity_delta_vs_C9", "max_dd_delta_vs_C9", "sharpe_delta_vs_C9"]
    )
    c15_passes = (
        float(c15_row["end_equity_delta_vs_C9"]) > 0
        and float(c15_row["max_dd_delta_vs_C9"]) >= 0
        and float(c15_row["sharpe_delta_vs_C9"]) > 0
        and float(c15_row["max_broker10_margin_to_equity_pct"])
        <= float(c9_row["max_broker10_margin_to_equity_pct"])
    )
    if early_guard_events == 0 and not c15_changed_c9:
        decision_label = "stage879_early_oi_guard_no_effect_not_promoted"
    elif c15_passes:
        decision_label = "stage879_early_oi_guard_promising_needs_rolling_and_cost_stress"
    else:
        decision_label = "stage879_early_oi_guard_not_promoted"

    _write_report(comparison, event_summary, atlas_paths, decision_label)
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
        "rule_type": "c9_plus_early_oi_down_no_progress_guard",
        "rule": {
            "base_arm": C9_ARM,
            "early_bars": EARLY_BARS,
            "min_early_bars": MIN_EARLY_BARS,
            "progress_r_guard": EARLY_GUARD_R,
            "trigger": "no +0.5R progress in first 60 bars and price directional return < 0 and OI change < 0",
            "exit_price": "60th minute close",
            "same_day_retry": False,
            "no_parameter_scan": True,
        },
        "event_summary": {
            "c15_stop_retry_or_guard_events": int(len(stop_retry_events)),
            "early_guard_events": early_guard_events,
            "c15_changed_vs_c9": bool(c15_changed_c9),
        },
        "event_summary_table": event_summary.to_dict("records"),
        "comparison": comparison.to_dict("records"),
        "decision": decision_label,
        "candidate_result": c15_row,
        "overfit_reflection": (
            "不是过拟合式扫参。本阶段只把 Stage878 的四象限参与度线索落成一个固定且更窄的真实引擎规则，"
            "窗口固定为 60 根、阈值只用 0 轴和 C9 既有 +0.5R progress，不扫品种、方向、年份或 OI 小数。"
        ),
        "continue_value": (
            "若 C15 失败，应停止把早段 OI 状态直接写成退出规则；若通过，也只能进入滚动起点和成本压力，"
            "不能直接推广到官方候选。"
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
            "atlas_manifest": str(ATLAS_MANIFEST_PATH),
            "report": str(REPORT_PATH),
            "path_chart": str(PATH_CHART_PATH),
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
