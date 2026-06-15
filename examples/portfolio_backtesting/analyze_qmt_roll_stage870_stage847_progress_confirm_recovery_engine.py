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
STAGE = "Stage870"
MODEL_TAG = "stage870_stage847_progress_confirm_recovery_engine_v1"
OUTPUT_PREFIX = "qmt_roll_stage870_stage847_progress_confirm_recovery_engine"

C4_ARM = s830.CAP_ARM
C9_ARM = s847.C9_ARM
C13_ARM = "stage870_stage819_c9_progress_confirm_recovery"

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
        if pd.isna(value):
            return default
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if np.isfinite(number) else default


class QmtRollPortfolioStrategyStage870ProgressConfirmRecovery(s847.QmtRollPortfolioStrategyStage847C9StopRetry):
    enable_stage870_progress_confirm_recovery: bool = False

    parameters = s847.QmtRollPortfolioStrategyStage847C9StopRetry.parameters + [
        "enable_stage870_progress_confirm_recovery",
    ]
    variables = s847.QmtRollPortfolioStrategyStage847C9StopRetry.variables + [
        "stage870_progress_reentry_count",
        "stage870_progress_reentry_failed_count",
    ]

    def __init__(self, strategy_engine, strategy_name: str, vt_symbols: list[str], setting: dict) -> None:
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)
        self.stage870_progress_reentry_count: int = 0
        self.stage870_progress_reentry_failed_count: int = 0

    def _stage847_stop_retry_event_after_open_trade(self, trade: s827.TradeData) -> dict[str, Any] | None:
        if not self.enable_stage870_progress_confirm_recovery:
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
        initial_stop_price = entry_price - sign * float(self.stage847_stop_retry_r) * risk_price
        progress_price = entry_price + sign * float(self.stage847_stop_retry_r) * risk_price
        recovery_stop_price = entry_price

        first_stop_idx = -1
        first_stop_time = ""
        first_note = ""
        for idx, item in enumerate(entry_day.itertuples(index=False)):
            if position_direction == "long":
                adverse_hit = float(item.low) <= initial_stop_price
                progress_hit = float(item.high) >= progress_price
            else:
                adverse_hit = float(item.high) >= initial_stop_price
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
        reclaim_idx = -1
        reclaim_time = ""
        progress_reentry_idx = -1
        progress_reentry_time = ""
        progress_reentry_price = np.nan

        if max_retries > 0:
            for idx in range(first_stop_idx + 1, len(entry_day)):
                item = entry_day.iloc[idx]
                if position_direction == "long":
                    reclaimed = float(item["high"]) >= entry_price
                    progress_confirmed = float(item["high"]) >= progress_price
                else:
                    reclaimed = float(item["low"]) <= entry_price
                    progress_confirmed = float(item["low"]) <= progress_price
                if reclaim_idx < 0 and reclaimed:
                    reclaim_idx = idx
                    reclaim_time = pd.Timestamp(item["bar_datetime"]).isoformat()
                if progress_confirmed:
                    progress_reentry_idx = idx
                    progress_reentry_time = pd.Timestamp(item["bar_datetime"]).isoformat()
                    progress_reentry_price = progress_price
                    break

        progress_failed_idx = -1
        progress_failed_time = ""
        if progress_reentry_idx >= 0:
            for idx in range(progress_reentry_idx, len(entry_day)):
                item = entry_day.iloc[idx]
                if position_direction == "long":
                    recovery_stop_hit = float(item["low"]) <= recovery_stop_price
                else:
                    recovery_stop_hit = float(item["high"]) >= recovery_stop_price
                if recovery_stop_hit:
                    progress_failed_idx = idx
                    progress_failed_time = pd.Timestamp(item["bar_datetime"]).isoformat()
                    break

        contract_vt_symbol = state.contract_vt_symbol
        product_vt_symbol = state.product_vt_symbol
        close_volume = sum(state.layers[index].volume for index in candidate_indexes)
        if close_volume <= 0:
            return None

        synthetic_trades: list[dict[str, Any]] = [
            {
                "action": "close",
                "source": "stage870_intraday_05r_initial_stop",
                "price": initial_stop_price,
                "volume": close_volume,
                "time": first_stop_time,
            }
        ]
        final_state = "flat_no_progress_reentry"
        exit_reason = "stage870_intraday_05r_stop_no_progress_reentry"
        final_exit_price = initial_stop_price

        if progress_reentry_idx >= 0 and np.isfinite(progress_reentry_price):
            synthetic_trades.append(
                {
                    "action": "open",
                    "source": "stage870_intraday_progress_confirm_reentry",
                    "price": progress_reentry_price,
                    "volume": close_volume,
                    "time": progress_reentry_time,
                }
            )
            final_state = "open_after_progress_reentry"
            exit_reason = "stage870_intraday_progress_reentry_open"
            final_exit_price = np.nan
            if progress_failed_idx >= 0:
                synthetic_trades.append(
                    {
                        "action": "close",
                        "source": "stage870_intraday_progress_reentry_failed_entry_stop",
                        "price": recovery_stop_price,
                        "volume": close_volume,
                        "time": progress_failed_time,
                    }
                )
                final_state = "flat_progress_reentry_failed"
                exit_reason = "stage870_intraday_progress_reentry_failed_entry_stop"
                final_exit_price = recovery_stop_price

        event_bar = getattr(self.strategy_engine, "bars", {}).get(contract_vt_symbol)
        if final_state != "open_after_progress_reentry":
            if len(candidate_indexes) == len(state.layers):
                self._close_all_layers_and_set_flat_target(
                    state,
                    final_exit_price,
                    execution_price_override=final_exit_price,
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
                    price=final_exit_price,
                )
                self._close_layers(state, candidate_indexes, final_exit_price, exit_reason=exit_reason)
                self._apply_state_target(state, execution_price_override=final_exit_price)

        if progress_reentry_idx >= 0:
            self.stage870_progress_reentry_count += 1
        if progress_failed_idx >= 0:
            self.stage870_progress_reentry_failed_count += 1
        self.stage847_stop_retry_event_count += 1
        event = {
            "datetime": trade.datetime,
            "trade_id": trade.vt_tradeid,
            "vt_symbol": trade.vt_symbol,
            "product_vt_symbol": product_vt_symbol,
            "direction": position_direction,
            "entry_price": entry_price,
            "stop_price": initial_stop_price,
            "progress_price": progress_price,
            "recovery_stop_price": recovery_stop_price,
            "risk_price": risk_price,
            "stop_r": float(self.stage847_stop_retry_r),
            "max_retries": max_retries,
            "volume": close_volume,
            "first_stop_time": first_stop_time,
            "first_stop_bar_index": first_stop_idx,
            "reclaim_time": reclaim_time,
            "reclaim_bar_index": reclaim_idx,
            "reentry_time": progress_reentry_time,
            "reentry_bar_index": progress_reentry_idx,
            "reentry_price": progress_reentry_price,
            "retry_failed_time": progress_failed_time,
            "retry_failed_bar_index": progress_failed_idx,
            "retry_reentered": int(progress_reentry_idx >= 0),
            "retry_failed": int(progress_failed_idx >= 0),
            "final_state": final_state,
            "final_exit_price": final_exit_price,
            "note": first_note,
            "exit_reason": exit_reason,
            "synthetic_trades": synthetic_trades,
        }
        self.stage847_stop_retry_events.append(event)
        return event


def _c13_profile(metadata: dict[str, Any]) -> dict[str, Any]:
    profile = s847._c9_profile(metadata)
    spec = profile["spec"]
    capital = replace(
        spec.capital,
        variant=f"{C13_ARM}_2018",
        label="Stage870 Stage819 progress-confirm recovery",
        note=(
            f"{spec.capital.note} | Stage870 C13. After the first 0.5R intraday stop, do not reopen at the "
            "original entry reclaim. Reopen once only if price reaches the original +0.5R progress level on the "
            "same entry day; after that recovery entry, stop immediately if price falls back to the original entry."
        ),
    )
    overrides = {
        **spec.overrides,
        "enable_stage870_progress_confirm_recovery": True,
    }
    result = dict(profile)
    result["profile"] = C13_ARM
    result["strategy_cls"] = QmtRollPortfolioStrategyStage870ProgressConfirmRecovery
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


def _event_summary(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    data = events.copy()
    data["datetime"] = pd.to_datetime(data["datetime"], errors="coerce")
    data["year"] = data["datetime"].dt.year
    for column in ["volume", "retry_reentered", "retry_failed", "entry_price"]:
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
            reentered=("retry_reentered", "sum"),
            retry_failed=("retry_failed", "sum"),
            median_reentry_price_minus_entry=("reentry_price_minus_entry", "median"),
        )
        .reset_index()
    )


def _plot_path(curve: pd.DataFrame) -> None:
    data = curve[curve["arm"].isin([C4_ARM, C9_ARM, C13_ARM])].copy()
    if data.empty:
        return
    data["date"] = pd.to_datetime(data["date"], errors="coerce", format="mixed")
    colors = {C4_ARM: "#16a34a", C9_ARM: "#7c3aed", C13_ARM: "#0f766e"}
    labels = {
        C4_ARM: "C4 broker10 cap",
        C9_ARM: "C9 reclaim retry",
        C13_ARM: "C13 progress-confirm recovery",
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
    axes[0].set_title("Stage870 equity path")
    axes[1].set_title("Drawdown")
    axes[2].set_title("Broker10 margin/equity pct")
    for ax in axes:
        ax.grid(True, alpha=0.25)
        ax.legend(loc="best")
    fig.savefig(PATH_CHART_PATH, dpi=150)
    plt.close(fig)


def _plot_event_atlas(events: pd.DataFrame, minute_bars: pd.DataFrame) -> tuple[list[Path], pd.DataFrame]:
    if events.empty:
        return [], pd.DataFrame()
    selected = events[events["profile"].astype(str).eq(C13_ARM)].copy()
    if selected.empty:
        return [], pd.DataFrame()
    selected["datetime"] = pd.to_datetime(selected["datetime"], errors="coerce")
    selected = (
        pd.concat(
            [
                selected[selected["final_state"].astype(str).eq("flat_progress_reentry_failed")].head(4),
                selected[selected["final_state"].astype(str).eq("open_after_progress_reentry")].head(4),
                selected[selected["final_state"].astype(str).eq("flat_no_progress_reentry")].head(4),
            ],
            ignore_index=True,
            sort=False,
        )
        .drop_duplicates(["vt_symbol", "datetime", "final_state"])
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
        for ax, (_, row) in zip(axes, page_rows.iterrows(), strict=False):
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
                day = day.sort_values("bar_datetime").reset_index(drop=True)
                s825._plot_candles(ax, day)
                for label, price, color, linestyle in [
                    ("entry/recovery stop", row.get("entry_price"), "#2563eb", "-"),
                    ("initial 0.5R stop", row.get("stop_price"), "#dc2626", "--"),
                    ("progress reentry", row.get("progress_price"), "#16a34a", "--"),
                ]:
                    value = _safe_float(price)
                    if np.isfinite(value):
                        ax.axhline(value, color=color, linestyle=linestyle, linewidth=0.9, label=label)
                for key, color, label in [
                    ("first_stop_time", "#dc2626", "first stop"),
                    ("reclaim_time", "#7c3aed", "reclaim"),
                    ("reentry_time", "#16a34a", "progress reentry"),
                    ("retry_failed_time", "#7c2d12", "recovery fail"),
                ]:
                    value = row.get(key)
                    ts = pd.to_datetime(value, errors="coerce")
                    if pd.isna(ts):
                        continue
                    matches = day.index[pd.to_datetime(day["bar_datetime"], errors="coerce").eq(ts)]
                    if len(matches):
                        ax.axvline(int(matches[0]), color=color, alpha=0.75, linewidth=0.85, label=label)
                ticks = np.linspace(0, len(day) - 1, num=min(8, len(day)), dtype=int)
                ax.set_xticks(ticks)
                ax.set_xticklabels([pd.Timestamp(day.loc[pos, "bar_datetime"]).strftime("%H:%M") for pos in ticks], fontsize=7)
                handles, labels = ax.get_legend_handles_labels()
                if handles:
                    dedup = dict(zip(labels, handles, strict=False))
                    ax.legend(dedup.values(), dedup.keys(), loc="best", fontsize=7)
                ax.grid(True, alpha=0.18)
            ax.set_title(f"{vt_symbol} {row.get('direction')} {entry_dt:%Y-%m-%d} {row.get('final_state')}", fontsize=9)
            manifest.append(
                {
                    "page": page,
                    "vt_symbol": vt_symbol,
                    "direction": row.get("direction"),
                    "entry_date": entry_dt.date().isoformat(),
                    "final_state": row.get("final_state"),
                    "first_stop_time": row.get("first_stop_time", ""),
                    "reclaim_time": row.get("reclaim_time", ""),
                    "reentry_time": row.get("reentry_time", ""),
                    "retry_failed_time": row.get("retry_failed_time", ""),
                    "entry_price": _safe_float(row.get("entry_price")),
                    "progress_price": _safe_float(row.get("progress_price")),
                    "bars": int(len(day)) if not day.empty else 0,
                }
            )
        for ax in axes[len(page_rows) :]:
            ax.set_axis_off()
        path = Path(str(ATLAS_TEMPLATE).format(page=page))
        fig.suptitle("Stage870 progress-confirm recovery minute-K atlas", fontsize=13)
        fig.savefig(path, dpi=150)
        plt.close(fig)
        paths.append(path)
    return paths, pd.DataFrame(manifest)


def _write_report(comparison: pd.DataFrame, event_summary: pd.DataFrame, atlas_paths: list[Path], decision: str) -> None:
    lines = [
        "# Stage870 progress-confirm recovery 真实引擎",
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
        "- Backtrader stop/bracket examples：https://www.backtrader.com/blog/posts/2018-02-01-stop-trading/stop-trading/",
        "- 我的判断：趋势重入不能只靠 reclaim，必须要求价格重新证明趋势进展；本阶段把证明定义为打到原入场后的 +0.5R progress，并用原入场价作为重入后的实时硬止损。",
        "",
        "## 预声明臂",
        "",
        "- A：C4，即 Stage830 C2 + broker10 projected `100%` entry cap。",
        "- B：C9，即 Stage847 C4 + `0.5R` stop-first + 原入场价触碰 reclaim 后允许一次重试。",
        "- C：C13，即首次 `0.5R` 止损不变；之后只有达到原入场方向 `+0.5R progress` 才重开，重开后若回到原入场价立即止损。",
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
        f"- 决策：`{decision}`。",
        "- 若 C13 不能同时改善 C9 的收益、回撤和 broker10，说明 progress-confirm recovery 不是当前可用结构，应停止该分支。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _decision(comparison: pd.DataFrame) -> str:
    c13 = comparison[comparison["arm"].eq(C13_ARM)]
    if c13.empty:
        return "stage870_progress_confirm_recovery_failed_no_c13"
    row = c13.iloc[0]
    if (
        row["end_equity_delta_vs_C9"] > 0
        and row["max_dd_delta_vs_C9"] >= 0
        and row["sharpe_delta_vs_C9"] > 0
        and row["max_broker10_margin_to_equity_pct"]
        <= comparison.loc[comparison["arm"].eq(C9_ARM), "max_broker10_margin_to_equity_pct"].iloc[0]
    ):
        return "stage870_progress_confirm_recovery_promising_needs_robustness"
    return "stage870_progress_confirm_recovery_not_promoted"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    metadata = s513._metadata()
    vt_symbols = set(str(item) for item in metadata["vt_symbols"])
    minute_bars = s863._load_stage861_full_minute_bars(vt_symbols)
    s827._GLOBAL_MINUTE_BY_SYMBOL = s825._minute_groups(minute_bars)

    profiles = [s830._cap_profile(metadata), s847._c9_profile(metadata), _c13_profile(metadata)]
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
    _plot_path(curve)
    atlas_paths, atlas_manifest = _plot_event_atlas(output_frames["stop_retry_events"], minute_bars)
    decision = _decision(comparison)

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
    atlas_manifest.to_csv(ATLAS_MANIFEST_PATH, index=False, encoding="utf-8-sig")
    _write_report(comparison, event_summary, atlas_paths, decision)

    c13_events = output_frames["stop_retry_events"][
        output_frames["stop_retry_events"]["profile"].astype(str).eq(C13_ARM)
    ].copy()
    payload = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "source_candidate": stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION,
        "strategy_changed": True,
        "ctp_connected": False,
        "order_api_called": False,
        "formal_ab_triggered": False,
        "minute_source": {
            "stage861_full_minute_bars": str(s861.FULL_MINUTE_BARS_PATH),
            "loaded_minute_bars": int(len(minute_bars)),
            "loaded_symbols": int(minute_bars["vt_symbol"].astype(str).nunique()) if not minute_bars.empty else 0,
        },
        "rule": {
            "initial_stop": "first 0.5R adverse before 0.5R progress closes initial entry",
            "reentry": "same-day +0.5R progress touch after initial stop",
            "reentry_execution": "synthetic open at original progress_price",
            "recovery_stop": "original entry price after progress-confirm reentry",
            "max_retries": 1,
        },
        "comparison": comparison.to_dict("records"),
        "event_summary": event_summary.to_dict("records"),
        "c13_event_counts": c13_events["final_state"].value_counts(dropna=False).to_dict() if not c13_events.empty else {},
        "decision": decision,
        "overfit_reflection": (
            "本阶段不是扫参：只把 C9 的 reclaim 重入替换为一个固定的趋势恢复证明，即先到 +0.5R progress，"
            "并把原入场价作为重入后的硬止损；没有扫描 R、窗口、品种、方向或年份。"
        ),
        "continue_value": (
            "若 C13 同时改善 C9 收益、回撤、Sharpe 与 broker10，则有继续做滚动起点/成本压力的价值；"
            "否则停止 progress-confirm recovery 分支。"
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
            "decision": str(DECISION_PATH),
        },
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
