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

import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage719_official_winner_trade_forensics as s719
import analyze_qmt_roll_stage825_stage819_intraday_rule_forensics as s825
import analyze_qmt_roll_stage827_stage819_intraday_c2_engine_ac as s827
import analyze_qmt_roll_stage830_stage827_c2_broker10_margin_cap as s830
import analyze_qmt_roll_stage840_stage830_c4_120m_failfast_engine as s840
import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import qmt_roll_official_candidate_stage819_30w_config as stage819_cfg


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage843"
MODEL_TAG = "stage843_stage830_c4_s3_structural_break_engine_v1"
OUTPUT_PREFIX = "qmt_roll_stage843_stage830_c4_s3_structural_break_engine"

STAGE830_TAG = s840.STAGE830_TAG
STAGE830_PREFIX = s840.STAGE830_PREFIX

BASE_ARM = s830.BASE_ARM
C2_ARM = s830.C2_ARM
C4_ARM = s830.CAP_ARM
C8_ARM = "stage843_stage819_c4_s3_two_stop_side_closes"

START = s827.START
END = s827.END
CAPITAL = stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_CAPITAL

STRUCTURAL_STOP_R = 0.5
REQUIRED_STOP_SIDE_CLOSES = 2

STAGE830_SUMMARY_PATH = OUTPUT_DIR / f"{STAGE830_PREFIX}_summary_{STAGE830_TAG}.csv"
STAGE830_CURVE_PATH = OUTPUT_DIR / f"{STAGE830_PREFIX}_curve_{STAGE830_TAG}.csv"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
CURVE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curve_{MODEL_TAG}.csv"
TRADES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{MODEL_TAG}.csv"
ENTRY_RISK_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_{MODEL_TAG}.csv"
ENTRY_CANDIDATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidates_{MODEL_TAG}.csv"
TRADE_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_events_{MODEL_TAG}.csv"
INTRADAY_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_intraday_events_{MODEL_TAG}.csv"
C2_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_c2_events_{MODEL_TAG}.csv"
STRUCTURAL_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_structural_stop_events_{MODEL_TAG}.csv"
CLOSED_LOTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_closed_lots_{MODEL_TAG}.csv"
CAP_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cap_events_{MODEL_TAG}.csv"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
PATH_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_path_chart_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _load_required_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required Stage830 output: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


class QmtRollPortfolioStrategyStage843C8S3StructuralBreak(s830.QmtRollPortfolioStrategyStage830C2Broker10MarginCap):
    enable_stage843_s3_structural_break_stop: bool = False
    stage843_structural_stop_r: float = STRUCTURAL_STOP_R
    stage843_required_stop_side_closes: int = REQUIRED_STOP_SIDE_CLOSES

    parameters = s830.QmtRollPortfolioStrategyStage830C2Broker10MarginCap.parameters + [
        "enable_stage843_s3_structural_break_stop",
        "stage843_structural_stop_r",
        "stage843_required_stop_side_closes",
    ]
    variables = s830.QmtRollPortfolioStrategyStage830C2Broker10MarginCap.variables + [
        "stage843_structural_stop_count",
    ]

    def __init__(self, strategy_engine, strategy_name: str, vt_symbols: list[str], setting: dict) -> None:
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)
        self.stage843_structural_stop_events: list[dict[str, Any]] = []
        # Stage840 runner reads this attribute; keep it populated for frame compatibility.
        self.stage840_failfast_events: list[dict[str, Any]] = self.stage843_structural_stop_events
        self.stage843_structural_stop_count: int = 0

    def stage827_intraday_exit_after_open_trade(self, trade: s827.TradeData) -> dict[str, Any] | None:
        c2_event = super().stage827_intraday_exit_after_open_trade(trade)
        if c2_event:
            return c2_event
        if not self.enable_stage843_s3_structural_break_stop:
            return None

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
        stop05_price = entry_price - sign * float(self.stage843_structural_stop_r) * risk_price
        stop_hits = []
        for idx, item in enumerate(entry_day.itertuples(index=False)):
            if position_direction == "long":
                hit = float(item.low) <= stop05_price
            else:
                hit = float(item.high) >= stop05_price
            if hit:
                stop_hits.append(idx)
                break
        if not stop_hits:
            return None

        first_stop_idx = int(stop_hits[0])
        consecutive = 0
        hit_time = ""
        exit_price = np.nan
        trigger_index = -1
        required = max(1, int(self.stage843_required_stop_side_closes))
        for idx in range(first_stop_idx + 1, len(entry_day)):
            item = entry_day.iloc[idx]
            if position_direction == "long":
                reclaim_entry = float(item["high"]) >= entry_price
                on_stop_side_close = float(item["close"]) <= stop05_price
            else:
                reclaim_entry = float(item["low"]) <= entry_price
                on_stop_side_close = float(item["close"]) >= stop05_price
            if reclaim_entry:
                return None
            if on_stop_side_close:
                consecutive += 1
                if consecutive >= required:
                    trigger_index = idx
                    hit_time = pd.Timestamp(item["bar_datetime"]).isoformat()
                    exit_price = float(item["close"])
                    break
            else:
                consecutive = 0
        if not hit_time or not np.isfinite(exit_price) or exit_price <= 0:
            return None

        contract_vt_symbol = state.contract_vt_symbol
        product_vt_symbol = state.product_vt_symbol
        close_volume = sum(state.layers[index].volume for index in candidate_indexes)
        if close_volume <= 0:
            return None

        exit_reason = "stage843_intraday_s3_two_stop_side_closes"
        engine_bars: dict[str, s827.BarData] = getattr(self.strategy_engine, "bars", {})
        event_bar = engine_bars.get(contract_vt_symbol)
        if len(candidate_indexes) == len(state.layers):
            self._close_all_layers_and_set_flat_target(
                state,
                exit_price,
                execution_price_override=exit_price,
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
                price=exit_price,
            )
            self._close_layers(state, candidate_indexes, exit_price, exit_reason=exit_reason)
            self._apply_state_target(state, execution_price_override=exit_price)

        self.stage843_structural_stop_count += 1
        event = {
            "datetime": trade.datetime,
            "trade_id": trade.vt_tradeid,
            "vt_symbol": trade.vt_symbol,
            "product_vt_symbol": product_vt_symbol,
            "direction": position_direction,
            "entry_price": entry_price,
            "stop_price": exit_price,
            "exit_price": exit_price,
            "structural_stop_price_05r": stop05_price,
            "risk_price": risk_price,
            "structural_stop_r": float(self.stage843_structural_stop_r),
            "required_stop_side_closes": required,
            "volume": close_volume,
            "first_stop05_time": pd.Timestamp(entry_day.loc[first_stop_idx, "bar_datetime"]).isoformat(),
            "hit_time": hit_time,
            "trigger_bar_index": trigger_index,
            "note": "two_stop_side_closes_before_reclaim_entry",
            "exit_reason": exit_reason,
        }
        self.stage843_structural_stop_events.append(event)
        return event


def _c8_profile(metadata: dict[str, Any]) -> dict[str, Any]:
    profile = s830._cap_profile(metadata)
    spec = profile["spec"]
    capital = replace(
        spec.capital,
        variant=f"{C8_ARM}_2018",
        label="Stage843 Stage819 C4 plus S3 two stop-side closes 2018 start",
        note=(
            f"{spec.capital.note} | Stage843 frozen C8. After C2/C4, if entry-day price first hits "
            "0.5R adverse and then has two consecutive 1-minute closes on the 0.5R stop side before reclaiming entry, "
            "close at the second close. No retry rule is added."
        ),
    )
    overrides = {
        **spec.overrides,
        "enable_stage827_intraday_c2_stop": True,
        "enable_stage830_broker10_margin_cap": True,
        "enable_stage843_s3_structural_break_stop": True,
        "stage843_structural_stop_r": STRUCTURAL_STOP_R,
        "stage843_required_stop_side_closes": REQUIRED_STOP_SIDE_CLOSES,
    }
    result = dict(profile)
    result["profile"] = C8_ARM
    result["strategy_cls"] = QmtRollPortfolioStrategyStage843C8S3StructuralBreak
    result["spec"] = replace(spec, capital=capital, overrides=overrides, profile=result["profile"])
    return result


def _comparison(summary: pd.DataFrame) -> pd.DataFrame:
    base = summary[summary["arm"].eq(BASE_ARM)].iloc[0]
    c2 = summary[summary["arm"].eq(C2_ARM)].iloc[0]
    c4 = summary[summary["arm"].eq(C4_ARM)].iloc[0]
    rows: list[dict[str, Any]] = []
    for _, row in summary.iterrows():
        rows.append(
            {
                "arm": row["arm"],
                "end_equity": row["end_equity"],
                "end_equity_delta_vs_A": row["end_equity"] - base["end_equity"],
                "end_equity_delta_vs_C2": row["end_equity"] - c2["end_equity"],
                "end_equity_delta_vs_C4": row["end_equity"] - c4["end_equity"],
                "total_return_pct": row["total_return_pct"],
                "max_dd_pct": row["max_dd_pct"],
                "max_dd_delta_vs_A": row["max_dd_pct"] - base["max_dd_pct"],
                "max_dd_delta_vs_C2": row["max_dd_pct"] - c2["max_dd_pct"],
                "max_dd_delta_vs_C4": row["max_dd_pct"] - c4["max_dd_pct"],
                "sharpe": row["sharpe"],
                "sharpe_delta_vs_A": row["sharpe"] - base["sharpe"],
                "sharpe_delta_vs_C4": row["sharpe"] - c4["sharpe"],
                "total_slippage": row["total_slippage"],
                "total_trade_count": row["total_trade_count"],
                "win_rate_pct": row["nonzero_daily_win_rate_pct"],
                "max_broker10_margin_to_equity_pct": row.get("max_broker10_margin_to_equity_pct", np.nan),
                "p95_broker10_margin_to_equity_pct": row.get("p95_broker10_margin_to_equity_pct", np.nan),
            }
        )
    return pd.DataFrame(rows)


def _plot_path(curve: pd.DataFrame) -> None:
    data = curve[curve["arm"].isin([BASE_ARM, C2_ARM, C4_ARM, C8_ARM])].copy()
    if data.empty:
        return
    data["date"] = pd.to_datetime(data["date"], errors="coerce", format="mixed")
    fig, axes = plt.subplots(3, 1, figsize=(18, 11), sharex=True, constrained_layout=True)
    colors = {BASE_ARM: "#2563eb", C2_ARM: "#dc2626", C4_ARM: "#16a34a", C8_ARM: "#7c3aed"}
    labels = {
        BASE_ARM: "A baseline",
        C2_ARM: "C2 naked",
        C4_ARM: "C4 broker10 cap",
        C8_ARM: "C8 C4 + S3 structural stop",
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
    axes[0].set_title("Stage843 equity path")
    axes[1].set_title("Drawdown")
    axes[2].set_title("Broker10 margin to equity pct")
    for ax in axes:
        ax.grid(True, alpha=0.25)
        ax.legend(loc="best")
    fig.savefig(PATH_CHART_PATH, dpi=150)
    plt.close(fig)


def _path_diagnostics(curve: pd.DataFrame) -> pd.DataFrame:
    data = curve[curve["arm"].isin([BASE_ARM, C2_ARM, C4_ARM, C8_ARM])].copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce", format="mixed").dt.normalize()
    rows: list[dict[str, Any]] = []
    for arm, group in data.groupby("arm"):
        group = group.sort_values("date")
        trough = group.loc[group["drawdown_pct"].idxmin()]
        before = group[group["date"].le(trough["date"])]
        peak = before.loc[before["account_equity"].idxmax()]
        rows.append(
            {
                "arm": arm,
                "peak_date": pd.Timestamp(peak["date"]).date().isoformat(),
                "peak_equity": float(peak["account_equity"]),
                "trough_date": pd.Timestamp(trough["date"]).date().isoformat(),
                "trough_equity": float(trough["account_equity"]),
                "trough_dd_pct": float(trough["drawdown_pct"]),
                "max_broker10_margin_to_equity_pct": float(group["broker10_margin_to_equity_pct"].max()),
                "p95_broker10_margin_to_equity_pct": float(group["broker10_margin_to_equity_pct"].quantile(0.95)),
            }
        )
    return pd.DataFrame(rows)


def _events_by_year(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    temp = events.copy()
    temp["datetime"] = pd.to_datetime(temp["datetime"], errors="coerce")
    temp["year"] = temp["datetime"].dt.year
    return (
        temp.groupby("year", dropna=False)
        .agg(
            events=("vt_symbol", "size"),
            products=("product_vt_symbol", "nunique"),
            volume=("volume", "sum"),
            avg_risk_price=("risk_price", "mean"),
        )
        .reset_index()
    )


def _write_report(
    comparison: pd.DataFrame,
    path_diag: pd.DataFrame,
    cap_events: pd.DataFrame,
    c2_events: pd.DataFrame,
    structural_events: pd.DataFrame,
    closed_lots: pd.DataFrame,
) -> None:
    cap_by_year = pd.DataFrame()
    if not cap_events.empty:
        temp = cap_events.copy()
        temp["datetime"] = pd.to_datetime(temp["datetime"], errors="coerce")
        temp["year"] = temp["datetime"].dt.year
        cap_by_year = (
            temp.groupby("year", dropna=False)
            .agg(
                events=("reason", "size"),
                blocked=("reason", lambda s: int(s.astype(str).eq("broker10_margin_cap_block").sum())),
                reduced_volume=("reduced_volume", "sum"),
                avg_projected_before=("projected_broker10_margin_to_equity_before", "mean"),
                avg_projected_after=("projected_broker10_margin_to_equity_after", "mean"),
            )
            .reset_index()
        )

    lines = [
        "# Stage843 C4 + S3结构破坏止损真实引擎",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 源候选：`{stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION}`",
        "- 阶段性质：Stage819 候选独立研究线的冻结真实引擎 A/C；不改正式版、不改候选配置、不连接 CTP、不调用下单。",
        "",
        "## 规则语义",
        "",
        "- A：Stage827 baseline，即 Stage819 原始候选复现。",
        "- C2：开仓后若入场日分钟K先触发 `1R` 逆向止损而非 `1R` 顺向确认，则同日止损。",
        "- C4：C2 保持不变；flat-entry 开仓前若 projected broker10 margin/equity 超过 `100%`，则降手数到不超过 `100%`。",
        "- C8：C4 保持不变；若 C2 未触发，入场日先触发 `0.5R` 逆向后，在重新站回入场价之前连续两根1分钟K收在 `0.5R` 止损侧，则按第二根收盘价合成实时平仓；不增加重试规则。",
        "- 本阶段固定 S3，不扫描连续根数、OR长度、R倍数、品种、方向或年份。",
        "",
        "## Result",
        "",
        _md_table(comparison, max_rows=10),
        "",
        "## Path Diagnostics",
        "",
        _md_table(path_diag, max_rows=12),
        "",
        "## Cap Events By Year",
        "",
        _md_table(cap_by_year, max_rows=20),
        "",
        "## C2 Events By Year",
        "",
        _md_table(_events_by_year(c2_events), max_rows=20),
        "",
        "## C8 Structural Events By Year",
        "",
        _md_table(_events_by_year(structural_events), max_rows=20),
        "",
        "## Largest C8 Structural Events",
        "",
        _md_table(structural_events.sort_values("volume", ascending=False).head(20) if not structural_events.empty else pd.DataFrame(), max_rows=20),
        "",
        "## C8 Closed Lots Snapshot",
        "",
        _md_table(
            closed_lots[["lot_id", "vt_symbol", "direction", "entry_date", "exit_date", "volume", "realized_pnl", "exit_reason", "signal"]].head(20)
            if not closed_lots.empty
            else pd.DataFrame(),
            max_rows=20,
        ),
        "",
        "## Chart",
        "",
        f"- path chart：`{PATH_CHART_PATH}`",
        "",
        "## Judgment",
        "",
        "- 本阶段只验证 Stage842 的 S3 线索能否穿过真实组合资金联动；不允许因为单次结果继续扫连续根数或阈值。",
        "- 若 C8 未同时改善 C4 的收益、回撤和 broker10 路径，则停止 S3 结构破坏退出路线。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stage830_summary = _load_required_csv(STAGE830_SUMMARY_PATH)
    stage830_curve = _load_required_csv(STAGE830_CURVE_PATH)

    metadata = s513._metadata()
    vt_symbols = set(str(item) for item in metadata["vt_symbols"])
    minute_bars = s825._load_minute_bars(vt_symbols)
    s827._GLOBAL_MINUTE_BY_SYMBOL = s825._minute_groups(minute_bars)

    profile = _c8_profile(metadata)
    combined, frames = s840._run_profile(profile, metadata)
    c8_summary, c8_curve = s827._metric(profile, combined)
    c8_summary["arm"] = C8_ARM
    c8_curve["arm"] = C8_ARM

    trades = frames.get("trades", pd.DataFrame()).copy()
    entry_risk = frames.get("entry_risk", pd.DataFrame()).copy()
    entry_candidates = frames.get("entry_candidates", pd.DataFrame()).copy()
    trade_events = frames.get("trade_events", pd.DataFrame()).copy()
    intraday_events = frames.get("intraday_events", pd.DataFrame()).copy()
    c2_events = frames.get("c2_events", pd.DataFrame()).copy()
    structural_events = frames.get("failfast_events", pd.DataFrame()).copy()
    closed_lots = s719._build_closed_lots(trades, entry_risk, entry_candidates, metadata)
    if not closed_lots.empty:
        closed_lots["arm"] = C8_ARM
        closed_lots["variant"] = profile["spec"].capital.variant
        if not structural_events.empty:
            structural_keys = (
                structural_events["vt_symbol"].astype(str)
                + "|"
                + structural_events["direction"].astype(str)
                + "|"
                + structural_events["datetime"].astype(str).str.slice(0, 10)
            )
            lot_keys = (
                closed_lots["vt_symbol"].astype(str)
                + "|"
                + closed_lots["direction"].astype(str)
                + "|"
                + closed_lots["entry_date"].astype(str).str.slice(0, 10)
            )
            closed_lots.loc[lot_keys.isin(set(structural_keys)), "exit_reason"] = (
                "stage843_intraday_s3_two_stop_side_closes"
            )

    cap_events = pd.DataFrame()
    if not trade_events.empty and "reason" in trade_events.columns:
        cap_events = trade_events[trade_events["reason"].astype(str).str.startswith("broker10_margin_cap")].copy()
        for column in [
            "selected_volume_before",
            "selected_volume_after",
            "reduced_volume",
            "estimated_equity",
            "reserved_margin_before",
            "margin_per_contract",
            "broker_margin_multiplier",
            "cap_ratio",
            "max_affordable_volume",
            "projected_broker10_margin_to_equity_before",
            "projected_broker10_margin_to_equity_after",
        ]:
            cap_events[column] = pd.to_numeric(cap_events.get(column, 0), errors="coerce").fillna(0.0)

    summary = pd.concat(
        [
            stage830_summary[stage830_summary["arm"].isin([BASE_ARM, C2_ARM, C4_ARM])],
            c8_summary,
        ],
        ignore_index=True,
        sort=False,
    )
    curve = pd.concat(
        [
            stage830_curve[stage830_curve["arm"].isin([BASE_ARM, C2_ARM, C4_ARM])],
            c8_curve,
        ],
        ignore_index=True,
        sort=False,
    )
    comparison = _comparison(summary)
    path_diag = _path_diagnostics(curve)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    curve.to_csv(CURVE_PATH, index=False, encoding="utf-8-sig")
    trades.to_csv(TRADES_PATH, index=False, encoding="utf-8-sig")
    entry_risk.to_csv(ENTRY_RISK_PATH, index=False, encoding="utf-8-sig")
    entry_candidates.to_csv(ENTRY_CANDIDATES_PATH, index=False, encoding="utf-8-sig")
    trade_events.to_csv(TRADE_EVENTS_PATH, index=False, encoding="utf-8-sig")
    intraday_events.to_csv(INTRADAY_EVENTS_PATH, index=False, encoding="utf-8-sig")
    c2_events.to_csv(C2_EVENTS_PATH, index=False, encoding="utf-8-sig")
    structural_events.to_csv(STRUCTURAL_EVENTS_PATH, index=False, encoding="utf-8-sig")
    closed_lots.to_csv(CLOSED_LOTS_PATH, index=False, encoding="utf-8-sig")
    cap_events.to_csv(CAP_EVENTS_PATH, index=False, encoding="utf-8-sig")
    _plot_path(curve)
    _write_report(comparison, path_diag, cap_events, c2_events, structural_events, closed_lots)

    c8_row = comparison[comparison["arm"].eq(C8_ARM)].iloc[0].to_dict()
    c4_row = comparison[comparison["arm"].eq(C4_ARM)].iloc[0].to_dict()
    c8_beats_c4_return = float(c8_row["end_equity_delta_vs_C4"]) > 0
    c8_beats_c4_dd = float(c8_row["max_dd_delta_vs_C4"]) >= 0
    c8_beats_c4_broker = float(c8_row["max_broker10_margin_to_equity_pct"]) <= float(
        c4_row["max_broker10_margin_to_equity_pct"]
    )
    decision_label = (
        "stage843_c8_promising_requires_yearly_and_cost_stress"
        if c8_beats_c4_return and c8_beats_c4_dd and c8_beats_c4_broker
        else "stage843_c8_not_promoted_s3_structural_break_fullpath_failed"
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
        "rule_type": "frozen_intraday_structural_break_exit",
        "rule": {
            "base_arm": C4_ARM,
            "c2_preserved": True,
            "broker10_entry_cap_preserved": True,
            "structural_stop_r": STRUCTURAL_STOP_R,
            "required_stop_side_closes": REQUIRED_STOP_SIDE_CLOSES,
            "retry_added": False,
            "exit_price": "second_stop_side_close_price",
        },
        "event_summary": {
            "c2_events": int(len(c2_events)),
            "structural_stop_events": int(len(structural_events)),
            "cap_events": int(len(cap_events)),
            "cap_blocked": int(cap_events["reason"].astype(str).eq("broker10_margin_cap_block").sum()) if not cap_events.empty else 0,
            "cap_reduced_volume": float(pd.to_numeric(cap_events.get("reduced_volume", 0), errors="coerce").fillna(0).sum())
            if not cap_events.empty
            else 0.0,
        },
        "comparison": comparison.to_dict("records"),
        "path_diagnostics": path_diag.to_dict("records"),
        "decision": decision_label,
        "candidate_result": c8_row,
        "overfit_reflection": (
            "C8 uses exactly the Stage842 S3 shape fixed before this engine run: 0.5R first adverse hit plus two "
            "consecutive stop-side closes before entry reclaim. No year, product, direction, stop multiple, OR length, "
            "or consecutive-bar scan is performed."
        ),
        "continue_value": (
            "Continue to yearly/cost stress only if C8 improves C4 after full portfolio capital linkage; otherwise stop "
            "the S3 structural-break exit branch."
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
            "c2_events": str(C2_EVENTS_PATH),
            "structural_stop_events": str(STRUCTURAL_EVENTS_PATH),
            "closed_lots": str(CLOSED_LOTS_PATH),
            "cap_events": str(CAP_EVENTS_PATH),
            "report": str(REPORT_PATH),
            "path_chart": str(PATH_CHART_PATH),
        },
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print("comparison")
    print(comparison.to_string(index=False))


if __name__ == "__main__":
    main()
