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
STAGE = "Stage829"
MODEL_TAG = "stage829_stage827_c2_baseline_volume_cap_v1"
OUTPUT_PREFIX = "qmt_roll_stage829_stage827_c2_baseline_volume_cap"

STAGE827_TAG = "stage827_stage819_intraday_c2_engine_ac_v1"
STAGE827_PREFIX = "qmt_roll_stage827_stage819_intraday_c2_engine_ac"
BASE_ARM = "stage827_stage819_baseline"
C2_ARM = "stage827_stage819_c2_engine"
CAPPED_ARM = "stage829_stage819_c2_a_open_volume_cap"

STAGE827_SUMMARY_PATH = OUTPUT_DIR / f"{STAGE827_PREFIX}_summary_{STAGE827_TAG}.csv"
STAGE827_CURVE_PATH = OUTPUT_DIR / f"{STAGE827_PREFIX}_curve_{STAGE827_TAG}.csv"
STAGE827_ENTRY_CANDIDATES_PATH = OUTPUT_DIR / f"{STAGE827_PREFIX}_entry_candidates_{STAGE827_TAG}.csv"

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

_BASELINE_OPEN_VOLUME_CAP: dict[tuple[str, str, str, str, str], int] = {}


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _safe_float(value: Any, default: float = np.nan) -> float:
    return s825._safe_float(value, default=default)


def _load_required_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required Stage827 output: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _cap_key(
    date_value: Any,
    product_vt_symbol: Any,
    direction: Any,
    signal: Any,
    entry_context: Any,
) -> tuple[str, str, str, str, str]:
    date_text = pd.Timestamp(date_value).normalize().strftime("%Y-%m-%d")
    return (
        date_text,
        str(product_vt_symbol),
        str(direction),
        str(signal),
        str(entry_context),
    )


def _build_baseline_open_volume_cap(candidates: pd.DataFrame) -> dict[tuple[str, str, str, str, str], int]:
    data = candidates[candidates["profile"].astype(str).eq(BASE_ARM)].copy()
    if data.empty:
        raise RuntimeError("Stage827 baseline candidate snapshots are empty; cannot build cap map.")
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    data["selected_volume"] = pd.to_numeric(data.get("selected_volume", 0), errors="coerce").fillna(0).astype(int)
    opened = data[
        data["candidate_status"].astype(str).eq("opened")
        & data["date"].notna()
        & data["product_vt_symbol"].notna()
        & data["direction"].astype(str).isin(["long", "short"])
        & data["signal"].astype(str).ne("")
    ].copy()
    cap: dict[tuple[str, str, str, str, str], int] = {}
    for row in opened.to_dict("records"):
        key = _cap_key(row["date"], row["product_vt_symbol"], row["direction"], row["signal"], row["entry_context"])
        cap[key] = cap.get(key, 0) + max(0, int(row.get("selected_volume") or 0))
    if not cap:
        raise RuntimeError("Stage827 baseline opened candidate cap map is empty.")
    return cap


class QmtRollPortfolioStrategyStage829C2BaselineVolumeCap(s827.QmtRollPortfolioStrategyStage827C2):
    enable_stage829_baseline_open_volume_cap: bool = False

    parameters = s827.QmtRollPortfolioStrategyStage827C2.parameters + [
        "enable_stage829_baseline_open_volume_cap",
    ]
    variables = s827.QmtRollPortfolioStrategyStage827C2.variables + [
        "stage829_baseline_cap_reduce_count",
        "stage829_baseline_cap_block_count",
    ]

    def __init__(self, strategy_engine, strategy_name: str, vt_symbols: list[str], setting: dict) -> None:
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)
        self.stage829_baseline_cap_events: list[dict[str, Any]] = []
        self.stage829_baseline_cap_reduce_count: int = 0
        self.stage829_baseline_cap_block_count: int = 0

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
        sizing.update(
            {
                "stage829_baseline_open_volume_cap_enabled": int(bool(self.enable_stage829_baseline_open_volume_cap)),
                "stage829_baseline_open_volume_cap_applied": 0,
                "stage829_baseline_open_volume_cap_reason": "disabled",
                "stage829_baseline_open_volume_cap": before,
                "stage829_baseline_open_volume_before": before,
                "stage829_baseline_open_volume_after": before,
            }
        )
        if not bool(self.enable_stage829_baseline_open_volume_cap):
            return sizing
        if entry_context != "flat_entry":
            sizing["stage829_baseline_open_volume_cap_reason"] = "not_flat_entry"
            return sizing

        product_vt_symbol = self.source_symbol_by_contract.get(vt_symbol, self._product_vt_symbol(vt_symbol))
        signal = str(signal_data.get("signal", ""))
        key = _cap_key(bar.datetime, product_vt_symbol, direction, signal, entry_context)
        cap_volume = max(0, int(_BASELINE_OPEN_VOLUME_CAP.get(key, 0)))
        after = min(before, cap_volume)
        if 0 < after < self.min_position_size:
            after = 0
        reason = "within_baseline_open_volume"
        if after < before:
            reason = "baseline_open_volume_cap_reduce" if after > 0 else "baseline_open_volume_cap_block"
            self.stage829_baseline_cap_reduce_count += 1
            if after <= 0:
                self.stage829_baseline_cap_block_count += 1
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
                "signal": signal,
                "entry_context": entry_context,
                "selected_volume_before": before,
                "baseline_open_volume_cap": cap_volume,
                "selected_volume_after": after,
                "reduced_volume": before - after,
                "reason": reason,
            }
            self.stage829_baseline_cap_events.append(event)
            diagnostics = getattr(self, "trade_event_diagnostics", None)
            if diagnostics is not None:
                diagnostics.append(event)
        sizing["selected_volume"] = after
        sizing["stage829_baseline_open_volume_cap_applied"] = int(after < before)
        sizing["stage829_baseline_open_volume_cap_reason"] = reason
        sizing["stage829_baseline_open_volume_cap"] = cap_volume
        sizing["stage829_baseline_open_volume_after"] = after
        return sizing


def _capped_profile(metadata: dict[str, Any]) -> dict[str, Any]:
    profile = s827._profile(metadata, enabled=True)
    spec = profile["spec"]
    capital = replace(
        spec.capital,
        variant=f"{CAPPED_ARM}_2018",
        label="Stage829 Stage819 C2 with A-opened-volume cap 2018 start",
        note=(
            f"{spec.capital.note} | Stage829 counterfactual: C2 intraday stop remains enabled, "
            "but flat-entry selected volume is capped to the Stage827 A baseline opened volume for the same "
            "date/product/direction/signal/context."
        ),
    )
    overrides = {
        **spec.overrides,
        "enable_stage827_intraday_c2_stop": True,
        "enable_stage829_baseline_open_volume_cap": True,
    }
    result = dict(profile)
    result["profile"] = CAPPED_ARM
    result["strategy_cls"] = QmtRollPortfolioStrategyStage829C2BaselineVolumeCap
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
    data = curve[curve["arm"].isin([BASE_ARM, C2_ARM, CAPPED_ARM])].copy()
    if data.empty:
        return
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    fig, axes = plt.subplots(3, 1, figsize=(18, 11), sharex=True, constrained_layout=True)
    colors = {BASE_ARM: "#2563eb", C2_ARM: "#dc2626", CAPPED_ARM: "#16a34a"}
    labels = {BASE_ARM: "A baseline", C2_ARM: "C2 naked", CAPPED_ARM: "C2 + A volume cap"}
    for arm, group in data.groupby("arm"):
        group = group.sort_values("date")
        color = colors.get(arm)
        label = labels.get(arm, arm)
        axes[0].plot(group["date"], group["account_equity"], label=label, color=color)
        axes[1].plot(group["date"], group["drawdown_pct"], label=label, color=color)
        axes[2].plot(group["date"], group["broker10_margin_to_equity_pct"], label=label, color=color)
    axes[0].set_title("Stage829 equity path")
    axes[1].set_title("Drawdown")
    axes[2].set_title("Broker10 margin to equity pct")
    for ax in axes:
        ax.grid(True, alpha=0.25)
        ax.legend(loc="best")
    fig.savefig(PATH_CHART_PATH, dpi=150)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    comparison: pd.DataFrame,
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
                blocked=("reason", lambda s: int(s.astype(str).eq("baseline_open_volume_cap_block").sum())),
                reduced_volume=("reduced_volume", "sum"),
            )
            .reset_index()
        )
    intraday_by_year = pd.DataFrame()
    if not intraday_events.empty:
        temp = intraday_events.copy()
        temp["datetime"] = pd.to_datetime(temp["datetime"], errors="coerce")
        temp["year"] = temp["datetime"].dt.year
        intraday_by_year = temp.groupby("year", dropna=False).agg(events=("vt_symbol", "size"), volume=("volume", "sum")).reset_index()

    lines = [
        "# Stage829 Stage827 C2基线开仓手数上限反事实",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 源候选：`{stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION}`",
        "- 阶段性质：账户层 counterfactual attribution；不改正式策略、不连接 CTP、不调用下单。",
        "",
        "## 规则语义",
        "",
        "- A：Stage827 baseline，即 Stage819 原始候选复现。",
        "- C2：Stage827 裸 C2，即开仓后若入场日分钟K先触发 1R 逆向止损而非 1R 顺向确认，则同日止损。",
        "- C3：C2 保持不变，但每个 flat-entry 的手数不得超过 A 在同一 `date/product/direction/signal/entry_context` 实际开仓手数；若 A 没开，C3 也不开。这是归因工具，不是可直接实盘规则。",
        "",
        "## Result",
        "",
        _md_table(comparison, max_rows=10),
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
        "- 如果 C3 明显降低 C2 回撤但也大幅吃掉收益，说明 C2 裸规则的优势依赖释放资金后的仓位放大，裸接入仍不能晋级。",
        "- 如果 C3 同时保留大部分收益并修复回撤，下一步才值得设计 live-feasible 的账户层预算规则；不能把这个 A 基线 cap 本身当作实盘规则。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    global _BASELINE_OPEN_VOLUME_CAP
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    stage827_summary = _load_required_csv(STAGE827_SUMMARY_PATH)
    stage827_curve = _load_required_csv(STAGE827_CURVE_PATH)
    stage827_candidates = _load_required_csv(STAGE827_ENTRY_CANDIDATES_PATH)
    _BASELINE_OPEN_VOLUME_CAP = _build_baseline_open_volume_cap(stage827_candidates)

    metadata = s513._metadata()
    vt_symbols = set(str(item) for item in metadata["vt_symbols"])
    minute_bars = s825._load_minute_bars(vt_symbols)
    s827._GLOBAL_MINUTE_BY_SYMBOL = s825._minute_groups(minute_bars)

    profile = _capped_profile(metadata)
    combined, frames = s827._run_profile(profile, metadata)
    capped_summary, capped_curve = s827._metric(profile, combined)
    capped_summary["arm"] = CAPPED_ARM
    capped_curve["arm"] = CAPPED_ARM

    trades = frames.get("trades", pd.DataFrame()).copy()
    entry_risk = frames.get("entry_risk", pd.DataFrame()).copy()
    entry_candidates = frames.get("entry_candidates", pd.DataFrame()).copy()
    closed_lots = s719._build_closed_lots(trades, entry_risk, entry_candidates, metadata)
    if not closed_lots.empty:
        closed_lots["arm"] = CAPPED_ARM
        closed_lots["variant"] = profile["spec"].capital.variant

    trade_events = frames.get("trade_events", pd.DataFrame()).copy()
    cap_events = pd.DataFrame()
    if not trade_events.empty and "reason" in trade_events.columns:
        cap_events = trade_events[trade_events["reason"].astype(str).str.startswith("baseline_open_volume_cap")].copy()
        for column in ["selected_volume_before", "baseline_open_volume_cap", "selected_volume_after", "reduced_volume"]:
            cap_events[column] = pd.to_numeric(cap_events.get(column, 0), errors="coerce").fillna(0)

    summary = pd.concat(
        [
            stage827_summary[stage827_summary["arm"].isin([BASE_ARM, C2_ARM])],
            capped_summary,
        ],
        ignore_index=True,
        sort=False,
    )
    curve = pd.concat(
        [
            stage827_curve[stage827_curve["arm"].isin([BASE_ARM, C2_ARM])],
            capped_curve,
        ],
        ignore_index=True,
        sort=False,
    )
    comparison = _comparison(summary)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    curve.to_csv(CURVE_PATH, index=False, encoding="utf-8-sig")
    trades.to_csv(TRADES_PATH, index=False, encoding="utf-8-sig")
    entry_risk.to_csv(ENTRY_RISK_PATH, index=False, encoding="utf-8-sig")
    entry_candidates.to_csv(ENTRY_CANDIDATES_PATH, index=False, encoding="utf-8-sig")
    trade_events.to_csv(TRADE_EVENTS_PATH, index=False, encoding="utf-8-sig")
    frames.get("intraday_events", pd.DataFrame()).to_csv(INTRADAY_EVENTS_PATH, index=False, encoding="utf-8-sig")
    closed_lots.to_csv(CLOSED_LOTS_PATH, index=False, encoding="utf-8-sig")
    cap_events.to_csv(CAP_EVENTS_PATH, index=False, encoding="utf-8-sig")
    _plot_path(curve)
    _write_report(summary, comparison, cap_events, frames.get("intraday_events", pd.DataFrame()), closed_lots)

    capped_row = comparison[comparison["arm"].eq(CAPPED_ARM)].iloc[0].to_dict()
    cap_event_summary = {
        "events": int(len(cap_events)),
        "blocked": int(cap_events["reason"].astype(str).eq("baseline_open_volume_cap_block").sum()) if not cap_events.empty else 0,
        "reduced_volume": float(pd.to_numeric(cap_events.get("reduced_volume", 0), errors="coerce").fillna(0).sum())
        if not cap_events.empty
        else 0.0,
    }
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "source_candidate": stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION,
        "strategy_changed": False,
        "ctp_connected": False,
        "order_api_called": False,
        "formal_ab_triggered": False,
        "rule_type": "counterfactual_attribution_not_live_rule",
        "cap_key": "date/product_vt_symbol/direction/signal/entry_context",
        "baseline_cap_rows": int(len(_BASELINE_OPEN_VOLUME_CAP)),
        "cap_event_summary": cap_event_summary,
        "comparison": comparison.to_dict("records"),
        "decision": "research_only_not_promoted_until_live_feasible_risk_budget_is_tested",
        "candidate_result": capped_row,
        "overfit_reflection": (
            "No parameter search was added. The cap uses the frozen Stage827 A path as an attribution ceiling, "
            "so it is explicitly not a live rule and must not be promoted directly."
        ),
        "continue_value": (
            "Continue only if this attribution shows that account-level risk-budget discipline can repair C2 path risk. "
            "Next step must translate it into a live-feasible rule without referencing the A path."
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
