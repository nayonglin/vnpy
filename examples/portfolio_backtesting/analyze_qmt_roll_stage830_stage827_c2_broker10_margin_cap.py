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
import qmt_roll_official_candidate_stage819_30w_config as stage819_cfg


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage830"
MODEL_TAG = "stage830_stage827_c2_broker10_margin_cap_v1"
OUTPUT_PREFIX = "qmt_roll_stage830_stage827_c2_broker10_margin_cap"

STAGE827_TAG = "stage827_stage819_intraday_c2_engine_ac_v1"
STAGE827_PREFIX = "qmt_roll_stage827_stage819_intraday_c2_engine_ac"
BASE_ARM = "stage827_stage819_baseline"
C2_ARM = "stage827_stage819_c2_engine"
CAP_ARM = "stage830_stage819_c2_broker10_100_cap"

BROKER_MARGIN_MULTIPLIER = 1.65
PROJECTED_BROKER10_MARGIN_TO_EQUITY_CAP = 1.00

STAGE827_SUMMARY_PATH = OUTPUT_DIR / f"{STAGE827_PREFIX}_summary_{STAGE827_TAG}.csv"
STAGE827_CURVE_PATH = OUTPUT_DIR / f"{STAGE827_PREFIX}_curve_{STAGE827_TAG}.csv"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
CURVE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curve_{MODEL_TAG}.csv"
TRADES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{MODEL_TAG}.csv"
ENTRY_RISK_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_{MODEL_TAG}.csv"
ENTRY_CANDIDATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidates_{MODEL_TAG}.csv"
TRADE_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_events_{MODEL_TAG}.csv"
INTRADAY_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_intraday_events_{MODEL_TAG}.csv"
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
        raise RuntimeError(f"missing required Stage827 output: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


class QmtRollPortfolioStrategyStage830C2Broker10MarginCap(s827.QmtRollPortfolioStrategyStage827C2):
    enable_stage830_broker10_margin_cap: bool = False
    stage830_broker_margin_multiplier: float = BROKER_MARGIN_MULTIPLIER
    stage830_projected_broker10_margin_to_equity_cap: float = PROJECTED_BROKER10_MARGIN_TO_EQUITY_CAP

    parameters = s827.QmtRollPortfolioStrategyStage827C2.parameters + [
        "enable_stage830_broker10_margin_cap",
        "stage830_broker_margin_multiplier",
        "stage830_projected_broker10_margin_to_equity_cap",
    ]
    variables = s827.QmtRollPortfolioStrategyStage827C2.variables + [
        "stage830_margin_cap_reduce_count",
        "stage830_margin_cap_block_count",
    ]

    def __init__(self, strategy_engine, strategy_name: str, vt_symbols: list[str], setting: dict) -> None:
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)
        self.stage830_margin_cap_events: list[dict[str, Any]] = []
        self.stage830_margin_cap_reduce_count: int = 0
        self.stage830_margin_cap_block_count: int = 0

    def _calculate_entry_sizing(
        self,
        vt_symbol: str,
        direction: str,
        bar: Any,
        history: pd.DataFrame,
        signal_data: dict[str, Any],
        risk_mode_override: str | None = None,
        entry_context: str = "flat_entry",
        apply_env_gate: bool = True,
        active_positions_before: int | None = None,
        correlation_snapshot: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        sizing = dict(
            super()._calculate_entry_sizing(
                vt_symbol,
                direction,
                bar,
                history,
                signal_data,
                risk_mode_override=risk_mode_override,
                entry_context=entry_context,
                apply_env_gate=apply_env_gate,
                active_positions_before=active_positions_before,
                correlation_snapshot=correlation_snapshot,
            )
        )
        before = max(0, int(sizing.get("selected_volume") or 0))
        equity = float(getattr(self, "estimated_equity", 0.0) or sizing.get("sizing_equity") or self.base_capital or 0.0)
        reserved_margin = float(sizing.get("reserved_margin_before") or 0.0)
        margin_per_contract = float(sizing.get("margin_per_contract") or 0.0)
        multiplier = float(self.stage830_broker_margin_multiplier)
        cap_ratio = float(self.stage830_projected_broker10_margin_to_equity_cap)
        projected_before = (
            (reserved_margin + margin_per_contract * before) * multiplier / equity if equity > 0 else np.inf
        )
        sizing.update(
            {
                "stage830_broker10_margin_cap_enabled": int(bool(self.enable_stage830_broker10_margin_cap)),
                "stage830_broker10_margin_cap_applied": 0,
                "stage830_broker10_margin_cap_reason": "disabled",
                "stage830_broker10_margin_cap_ratio": cap_ratio,
                "stage830_broker_margin_multiplier": multiplier,
                "stage830_margin_cap_selected_volume_before": before,
                "stage830_margin_cap_selected_volume_after": before,
                "stage830_projected_broker10_margin_to_equity_before": projected_before,
                "stage830_projected_broker10_margin_to_equity_after": projected_before,
                "stage830_margin_cap_max_affordable_volume": before,
            }
        )
        if not bool(self.enable_stage830_broker10_margin_cap):
            return sizing
        if entry_context != "flat_entry":
            sizing["stage830_broker10_margin_cap_reason"] = "not_flat_entry"
            return sizing
        if before <= 0:
            sizing["stage830_broker10_margin_cap_reason"] = "zero_selected_volume"
            return sizing
        if equity <= 0 or margin_per_contract <= 0 or multiplier <= 0 or cap_ratio <= 0:
            sizing["stage830_broker10_margin_cap_reason"] = "invalid_inputs"
            return sizing

        max_projected_margin = equity * cap_ratio / multiplier
        remaining_margin_budget = max_projected_margin - reserved_margin
        max_affordable = int(np.floor(remaining_margin_budget / margin_per_contract)) if remaining_margin_budget > 0 else 0
        after = min(before, max(0, max_affordable))
        if 0 < after < self.min_position_size:
            after = 0
        projected_after = (
            (reserved_margin + margin_per_contract * after) * multiplier / equity if equity > 0 else np.inf
        )
        reason = "within_broker10_margin_cap"
        if after < before:
            reason = "broker10_margin_cap_reduce" if after > 0 else "broker10_margin_cap_block"
            self.stage830_margin_cap_reduce_count += 1
            if after <= 0:
                self.stage830_margin_cap_block_count += 1
            product_vt_symbol = self.source_symbol_by_contract.get(vt_symbol, self._product_vt_symbol(vt_symbol))
            event = {
                "datetime": bar.datetime,
                "date": pd.Timestamp(bar.datetime).normalize().date().isoformat(),
                "vt_symbol": vt_symbol,
                "product_vt_symbol": product_vt_symbol,
                "contract_vt_symbol": vt_symbol,
                "position_direction": direction,
                "direction": direction,
                "offset": "RiskSizing",
                "price": float(getattr(bar, "close_price", 0.0) or 0.0),
                "volume": before - after,
                "signal": str(signal_data.get("signal", "")),
                "entry_context": entry_context,
                "selected_volume_before": before,
                "selected_volume_after": after,
                "reduced_volume": before - after,
                "estimated_equity": equity,
                "reserved_margin_before": reserved_margin,
                "margin_per_contract": margin_per_contract,
                "broker_margin_multiplier": multiplier,
                "cap_ratio": cap_ratio,
                "max_affordable_volume": max_affordable,
                "projected_broker10_margin_to_equity_before": projected_before,
                "projected_broker10_margin_to_equity_after": projected_after,
                "reason": reason,
            }
            self.stage830_margin_cap_events.append(event)
            diagnostics = getattr(self, "trade_event_diagnostics", None)
            if diagnostics is not None:
                diagnostics.append(event)

        sizing["selected_volume"] = after
        sizing["stage830_broker10_margin_cap_applied"] = int(after < before)
        sizing["stage830_broker10_margin_cap_reason"] = reason
        sizing["stage830_margin_cap_selected_volume_after"] = after
        sizing["stage830_projected_broker10_margin_to_equity_after"] = projected_after
        sizing["stage830_margin_cap_max_affordable_volume"] = max_affordable
        return sizing


def _cap_profile(metadata: dict[str, Any]) -> dict[str, Any]:
    profile = s827._profile(metadata, enabled=True)
    spec = profile["spec"]
    capital = replace(
        spec.capital,
        variant=f"{CAP_ARM}_2018",
        label="Stage830 Stage819 C2 broker10 100pct projected margin cap 2018 start",
        note=(
            f"{spec.capital.note} | Stage830 live-feasible account guard. C2 intraday stop remains enabled; "
            "flat-entry sizing is reduced only when projected broker10 margin/equity would exceed 100%."
        ),
    )
    overrides = {
        **spec.overrides,
        "enable_stage827_intraday_c2_stop": True,
        "enable_stage830_broker10_margin_cap": True,
        "stage830_broker_margin_multiplier": BROKER_MARGIN_MULTIPLIER,
        "stage830_projected_broker10_margin_to_equity_cap": PROJECTED_BROKER10_MARGIN_TO_EQUITY_CAP,
    }
    result = dict(profile)
    result["profile"] = CAP_ARM
    result["strategy_cls"] = QmtRollPortfolioStrategyStage830C2Broker10MarginCap
    result["spec"] = replace(spec, capital=capital, overrides=overrides, profile=result["profile"])
    return result


def _comparison(summary: pd.DataFrame) -> pd.DataFrame:
    base = summary[summary["arm"].eq(BASE_ARM)].iloc[0]
    c2 = summary[summary["arm"].eq(C2_ARM)].iloc[0]
    rows: list[dict[str, Any]] = []
    for _, row in summary.iterrows():
        rows.append(
            {
                "arm": row["arm"],
                "end_equity": row["end_equity"],
                "end_equity_delta_vs_A": row["end_equity"] - base["end_equity"],
                "end_equity_delta_vs_C2": row["end_equity"] - c2["end_equity"],
                "total_return_pct": row["total_return_pct"],
                "max_dd_pct": row["max_dd_pct"],
                "max_dd_delta_vs_A": row["max_dd_pct"] - base["max_dd_pct"],
                "max_dd_delta_vs_C2": row["max_dd_pct"] - c2["max_dd_pct"],
                "sharpe": row["sharpe"],
                "sharpe_delta_vs_A": row["sharpe"] - base["sharpe"],
                "total_slippage": row["total_slippage"],
                "total_trade_count": row["total_trade_count"],
                "win_rate_pct": row["nonzero_daily_win_rate_pct"],
                "max_broker10_margin_to_equity_pct": row.get("max_broker10_margin_to_equity_pct", np.nan),
                "p95_broker10_margin_to_equity_pct": row.get("p95_broker10_margin_to_equity_pct", np.nan),
            }
        )
    return pd.DataFrame(rows)


def _plot_path(curve: pd.DataFrame) -> None:
    data = curve[curve["arm"].isin([BASE_ARM, C2_ARM, CAP_ARM])].copy()
    if data.empty:
        return
    data["date"] = pd.to_datetime(data["date"], errors="coerce", format="mixed")
    fig, axes = plt.subplots(3, 1, figsize=(18, 11), sharex=True, constrained_layout=True)
    colors = {BASE_ARM: "#2563eb", C2_ARM: "#dc2626", CAP_ARM: "#16a34a"}
    labels = {BASE_ARM: "A baseline", C2_ARM: "C2 naked", CAP_ARM: "C2 + broker10 100% cap"}
    for arm, group in data.groupby("arm"):
        group = group.sort_values("date")
        color = colors.get(arm)
        label = labels.get(arm, arm)
        axes[0].plot(group["date"], group["account_equity"], label=label, color=color)
        axes[1].plot(group["date"], group["drawdown_pct"], label=label, color=color)
        axes[2].plot(group["date"], group["broker10_margin_to_equity_pct"], label=label, color=color)
    axes[0].set_title("Stage830 equity path")
    axes[1].set_title("Drawdown")
    axes[2].set_title("Broker10 margin to equity pct")
    for ax in axes:
        ax.grid(True, alpha=0.25)
        ax.legend(loc="best")
    fig.savefig(PATH_CHART_PATH, dpi=150)
    plt.close(fig)


def _path_diagnostics(curve: pd.DataFrame) -> pd.DataFrame:
    data = curve[curve["arm"].isin([BASE_ARM, C2_ARM, CAP_ARM])].copy()
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

    start = pd.Timestamp("2022-03-09")
    end = pd.Timestamp("2022-06-29")
    base = data[data["arm"].eq(BASE_ARM) & data["date"].between(start, end)][["date", "net_pnl", "account_equity"]]
    for arm in [C2_ARM, CAP_ARM]:
        group = data[data["arm"].eq(arm) & data["date"].between(start, end)][
            ["date", "net_pnl", "account_equity", "broker10_margin_to_equity_pct", "drawdown_pct"]
        ]
        merged = base.merge(group, on="date", suffixes=("_A", "_X"))
        rows.append(
            {
                "arm": f"{arm}_2022_peak_to_trough_window",
                "peak_date": start.date().isoformat(),
                "peak_equity": float(group.iloc[0]["account_equity"]) if not group.empty else np.nan,
                "trough_date": end.date().isoformat(),
                "trough_equity": float(group.iloc[-1]["account_equity"]) if not group.empty else np.nan,
                "trough_dd_pct": float(group["drawdown_pct"].min()) if not group.empty else np.nan,
                "max_broker10_margin_to_equity_pct": float(group["broker10_margin_to_equity_pct"].max()) if not group.empty else np.nan,
                "p95_broker10_margin_to_equity_pct": float(group["broker10_margin_to_equity_pct"].quantile(0.95)) if not group.empty else np.nan,
                "window_net_pnl_delta_vs_A": float((merged["net_pnl_X"] - merged["net_pnl_A"]).sum()) if not merged.empty else np.nan,
                "window_end_equity_gap_vs_A": float(merged.iloc[-1]["account_equity_X"] - merged.iloc[-1]["account_equity_A"])
                if not merged.empty
                else np.nan,
            }
        )
    return pd.DataFrame(rows)


def _write_report(
    comparison: pd.DataFrame,
    path_diag: pd.DataFrame,
    cap_events: pd.DataFrame,
    intraday_events: pd.DataFrame,
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
    intraday_by_year = pd.DataFrame()
    if not intraday_events.empty:
        temp = intraday_events.copy()
        temp["datetime"] = pd.to_datetime(temp["datetime"], errors="coerce")
        temp["year"] = temp["datetime"].dt.year
        intraday_by_year = (
            temp.groupby("year", dropna=False).agg(events=("vt_symbol", "size"), volume=("volume", "sum")).reset_index()
        )

    lines = [
        "# Stage830 Stage827 C2 broker10保证金上限",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 源候选：`{stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION}`",
        "- 阶段性质：live-feasible 账户层规则 A/C；不改正式策略、不连接 CTP、不调用下单。",
        "",
        "## 规则语义",
        "",
        "- A：Stage827 baseline，即 Stage819 原始候选复现。",
        "- C2：Stage827 裸 C2，即开仓后若入场日分钟K先触发 1R 逆向止损而非 1R 顺向确认，则同日止损。",
        "- C4：C2 保持不变；flat-entry 开仓前若 projected broker10 margin/equity 超过 100%，则把手数降到不超过 100%。",
        "- 100% 是账户生存闸门，不是按 2022、品种或收益反推的阈值。",
        "",
        "## Result",
        "",
        _md_table(comparison, max_rows=10),
        "",
        "## Path Diagnostics",
        "",
        _md_table(path_diag, max_rows=10),
        "",
        "## Cap Events By Year",
        "",
        _md_table(cap_by_year, max_rows=20),
        "",
        "## C2 Intraday Stop Events By Year",
        "",
        _md_table(intraday_by_year, max_rows=20),
        "",
        "## Largest Cap Events",
        "",
        _md_table(cap_events.sort_values("reduced_volume", ascending=False).head(20) if not cap_events.empty else pd.DataFrame(), max_rows=20),
        "",
        "## Capped Closed Lots Snapshot",
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
        "- 该阶段检验的是 live-feasible 账户层保证金生存闸门能否修复 C2 的二阶仓位风险。",
        "- 若最大回撤仍差于 A，则不能晋级；下一步应考虑更本质的释放资金再使用规则，而不是调保证金阈值。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stage827_summary = _load_required_csv(STAGE827_SUMMARY_PATH)
    stage827_curve = _load_required_csv(STAGE827_CURVE_PATH)

    metadata = s513._metadata()
    vt_symbols = set(str(item) for item in metadata["vt_symbols"])
    minute_bars = s825._load_minute_bars(vt_symbols)
    s827._GLOBAL_MINUTE_BY_SYMBOL = s825._minute_groups(minute_bars)

    profile = _cap_profile(metadata)
    combined, frames = s827._run_profile(profile, metadata)
    cap_summary, cap_curve = s827._metric(profile, combined)
    cap_summary["arm"] = CAP_ARM
    cap_curve["arm"] = CAP_ARM

    trades = frames.get("trades", pd.DataFrame()).copy()
    entry_risk = frames.get("entry_risk", pd.DataFrame()).copy()
    entry_candidates = frames.get("entry_candidates", pd.DataFrame()).copy()
    trade_events = frames.get("trade_events", pd.DataFrame()).copy()
    intraday_events = frames.get("intraday_events", pd.DataFrame()).copy()
    closed_lots = s719._build_closed_lots(trades, entry_risk, entry_candidates, metadata)
    if not closed_lots.empty:
        closed_lots["arm"] = CAP_ARM
        closed_lots["variant"] = profile["spec"].capital.variant

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
            stage827_summary[stage827_summary["arm"].isin([BASE_ARM, C2_ARM])],
            cap_summary,
        ],
        ignore_index=True,
        sort=False,
    )
    curve = pd.concat(
        [
            stage827_curve[stage827_curve["arm"].isin([BASE_ARM, C2_ARM])],
            cap_curve,
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
    closed_lots.to_csv(CLOSED_LOTS_PATH, index=False, encoding="utf-8-sig")
    cap_events.to_csv(CAP_EVENTS_PATH, index=False, encoding="utf-8-sig")
    _plot_path(curve)
    _write_report(comparison, path_diag, cap_events, intraday_events, closed_lots)

    cap_event_summary = {
        "events": int(len(cap_events)),
        "blocked": int(cap_events["reason"].astype(str).eq("broker10_margin_cap_block").sum()) if not cap_events.empty else 0,
        "reduced_volume": float(pd.to_numeric(cap_events.get("reduced_volume", 0), errors="coerce").fillna(0).sum())
        if not cap_events.empty
        else 0.0,
    }
    cap_row = comparison[comparison["arm"].eq(CAP_ARM)].iloc[0].to_dict()
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "source_candidate": stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION,
        "strategy_changed": False,
        "ctp_connected": False,
        "order_api_called": False,
        "formal_ab_triggered": False,
        "rule_type": "live_feasible_account_margin_guard",
        "broker_margin_multiplier": BROKER_MARGIN_MULTIPLIER,
        "projected_broker10_margin_to_equity_cap": PROJECTED_BROKER10_MARGIN_TO_EQUITY_CAP,
        "cap_event_summary": cap_event_summary,
        "comparison": comparison.to_dict("records"),
        "path_diagnostics": path_diag.to_dict("records"),
        "decision": "research_only_not_promoted_unless_dd_repaired_without_large_return_sacrifice",
        "candidate_result": cap_row,
        "overfit_reflection": (
            "The rule uses a fixed 100% broker10 projected margin/equity survival gate and does not inspect A path, "
            "future returns, years, products, directions, or R thresholds."
        ),
        "continue_value": (
            "If this improves C2 drawdown materially, continue with monthly-start/cost stress. If not, stop margin-threshold "
            "tuning and move to released-capital quarantine or same-risk-cluster reuse discipline."
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
