from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage653_stage526_200k_forced_margin_deleverage as s653
import analyze_qmt_roll_stage659_stage653_2026_ytd_latest_ai_shadow as s659
import analyze_qmt_roll_stage660_stage653_multiperiod_live_audit as s660
import analyze_qmt_roll_stage661_stage653_min_one_throttle_multiperiod as s661
from qmt_roll_official_live_config import OFFICIAL_LIVE_PROFILE_NAME, OFFICIAL_LIVE_VERSION
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage662_stage653_recovery_sleeve_multiperiod_v1"
OUTPUT_PREFIX = "qmt_roll_stage662_stage653_recovery_sleeve_multiperiod"
LINE_ID = "futures_trend_drawdown30_preserve_return"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
ANNUAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_{MODEL_TAG}.csv"
MONTHLY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_monthly_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
ROLLING_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rolling_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
CHECKS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_checks_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

RECOVERY_BROKER_MARGIN_MULTIPLIER = 1.65
RECOVERY_MAX_SINGLE_CONTRACT_BROKER_MARGIN_TO_EQUITY = 0.20
RECOVERY_COOLDOWN_CALENDAR_DAYS = 20


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _install_recovery_sleeve_patch() -> None:
    original_calculate = QmtRollPortfolioStrategy._calculate_entry_sizing
    original_open = QmtRollPortfolioStrategy._open_position

    def patched_calculate_entry_sizing(
        self: QmtRollPortfolioStrategy,
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
            original_calculate(
                self,
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
        sizing.update(
            {
                "recovery_sleeve_enabled": 1,
                "recovery_sleeve_applied": 0,
                "recovery_sleeve_reason": "",
                "recovery_sleeve_selected_volume_before": int(sizing.get("selected_volume") or 0),
                "recovery_sleeve_selected_volume_after": int(sizing.get("selected_volume") or 0),
                "recovery_sleeve_broker_margin_multiplier": RECOVERY_BROKER_MARGIN_MULTIPLIER,
                "recovery_sleeve_single_contract_broker_margin_to_equity": 0.0,
                "recovery_sleeve_max_single_contract_broker_margin_to_equity": (
                    RECOVERY_MAX_SINGLE_CONTRACT_BROKER_MARGIN_TO_EQUITY
                ),
                "recovery_sleeve_cooldown_days": RECOVERY_COOLDOWN_CALENDAR_DAYS,
            }
        )

        if entry_context != "flat_entry":
            sizing["recovery_sleeve_reason"] = "not_flat_entry"
            return sizing

        if int(sizing.get("streak_entry_structure_risk_recovery_applied") or 0) != 1:
            sizing["recovery_sleeve_reason"] = str(
                sizing.get("streak_entry_structure_risk_recovery_reason") or "structure_recovery_not_applied"
            )
            return sizing

        base_multiplier = float(sizing.get("streak_entry_structure_risk_recovery_base_multiplier") or 0.0)
        if base_multiplier > 0.1000001:
            sizing["recovery_sleeve_reason"] = "not_throttle_floor"
            sizing["selected_volume"] = 0
            sizing["recovery_sleeve_selected_volume_after"] = 0
            return sizing

        candidate_date = pd.Timestamp(bar.datetime).tz_localize(None).normalize()
        last_open_date = getattr(self, "_stage662_recovery_sleeve_last_open_date", None)
        if last_open_date is not None:
            days_since = int((candidate_date - pd.Timestamp(last_open_date)).days)
            if days_since <= RECOVERY_COOLDOWN_CALENDAR_DAYS:
                sizing["recovery_sleeve_reason"] = "cooldown"
                sizing["selected_volume"] = 0
                sizing["recovery_sleeve_selected_volume_after"] = 0
                return sizing

        selected_before = int(sizing.get("selected_volume") or 0)
        if selected_before <= 0:
            sizing["recovery_sleeve_reason"] = "zero_after_structure_recovery"
            return sizing

        sizing_equity = float(
            sizing.get("sizing_equity")
            or sizing.get("effective_sizing_equity_cap")
            or self.estimated_equity
            or self.base_capital
            or 0.0
        )
        margin_per_contract = float(sizing.get("margin_per_contract") or 0.0)
        broker_single_ratio = (
            margin_per_contract * RECOVERY_BROKER_MARGIN_MULTIPLIER / sizing_equity
            if sizing_equity > 0 and margin_per_contract > 0
            else 999.0
        )
        sizing["recovery_sleeve_single_contract_broker_margin_to_equity"] = broker_single_ratio
        if broker_single_ratio > RECOVERY_MAX_SINGLE_CONTRACT_BROKER_MARGIN_TO_EQUITY:
            sizing["recovery_sleeve_reason"] = "single_contract_margin_too_high"
            sizing["selected_volume"] = 0
            sizing["recovery_sleeve_selected_volume_after"] = 0
            return sizing

        sizing["recovery_sleeve_applied"] = 1
        sizing["recovery_sleeve_reason"] = "structure_recovery_one_lot"
        sizing["recovery_sleeve_selected_volume_before"] = selected_before
        sizing["selected_volume"] = 1
        sizing["recovery_sleeve_selected_volume_after"] = 1
        return sizing

    def patched_open_position(
        self: QmtRollPortfolioStrategy,
        state: Any,
        contract_vt_symbol: str,
        direction: str,
        volume: int,
        bar: Any,
        signal: str,
        history: pd.DataFrame,
        signal_data: dict[str, Any],
        sizing_snapshot: dict[str, Any] | None = None,
    ) -> None:
        if sizing_snapshot and int(sizing_snapshot.get("recovery_sleeve_applied") or 0) == 1:
            self._stage662_recovery_sleeve_last_open_date = pd.Timestamp(bar.datetime).tz_localize(None).normalize()
        return original_open(
            self,
            state,
            contract_vt_symbol,
            direction,
            volume,
            bar,
            signal,
            history,
            signal_data,
            sizing_snapshot=sizing_snapshot,
        )

    QmtRollPortfolioStrategy._calculate_entry_sizing = patched_calculate_entry_sizing
    QmtRollPortfolioStrategy._open_position = patched_open_position


def _official_recovery_spec(metadata: dict[str, Any]) -> s653.ForcedVariant:
    spec = s660._official_spec(metadata)
    overrides = {
        **spec.overrides,
        "enable_streak_entry_structure_risk_recovery": True,
        "streak_entry_structure_recovery_signals": "long_case1a,short_case1a",
        "streak_entry_structure_recovery_min_multiplier": 1.0,
        "streak_entry_structure_recovery_require_flat_portfolio": True,
        "streak_entry_structure_recovery_max_same_direction_corr": 0.30,
        "streak_entry_structure_recovery_require_rsi_confirmation": False,
        "enable_recovery_sleeve": True,
        "recovery_sleeve_base_multiplier_max": 0.1000001,
        "recovery_sleeve_broker_margin_multiplier": RECOVERY_BROKER_MARGIN_MULTIPLIER,
        "recovery_sleeve_max_single_contract_broker_margin_to_equity": (
            RECOVERY_MAX_SINGLE_CONTRACT_BROKER_MARGIN_TO_EQUITY
        ),
        "recovery_sleeve_cooldown_days": RECOVERY_COOLDOWN_CALENDAR_DAYS,
        "recovery_sleeve_volume": 1,
    }
    return replace(spec, overrides=overrides, profile="forced_margin_95_to_80_recovery_sleeve")


def _run_latest_ytd_recovery(
    *,
    spec: s653.ForcedVariant,
    metadata: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    daily, positions, _usage, forced_events = s659._run_variant_dynamic(
        spec,
        metadata,
        datetime.strptime("2026-01-01", "%Y-%m-%d"),
        datetime.strptime("2026-06-04", "%Y-%m-%d"),
        s659.DEFAULT_AI_ELIGIBILITY_PATH.resolve(),
    )
    daily["account_capital"] = spec.capital.account_capital
    daily["c3_capital"] = spec.capital.c3_capital
    daily["profile"] = spec.profile
    positions["account_capital"] = spec.capital.account_capital
    positions["c3_capital"] = spec.capital.c3_capital
    c3_margin_daily, _product_margin = s513._position_margin(positions, metadata)
    combined = s650._combine_daily(daily, c3_margin_daily, spec.capital)
    combined["profile"] = spec.profile
    for column in [
        "forced_margin_deleverage_count",
        "forced_margin_deleverage_closed_volume",
        "forced_margin_deleverage_ratio",
        "forced_margin_deleverage_max_observed_ratio",
    ]:
        combined[column] = daily[column].iloc[0] if column in daily.columns and not daily.empty else 0
    return combined, forced_events


def _check_rows(summary: pd.DataFrame, cost: pd.DataFrame, comparison: pd.DataFrame, rolling: pd.DataFrame) -> pd.DataFrame:
    checks = s661._check_rows(summary, cost, comparison, rolling)
    rows = checks.to_dict("records")
    ytd_cmp = comparison[comparison["window_name"].eq("ytd_2026_latest_ai")]
    if not ytd_cmp.empty:
        row = ytd_cmp.iloc[0]
        delta_return = float(row["delta_return_pct"])
        delta_dd = float(row["delta_max_dd_pct"])
        rows.append(
            {
                "check_name": "latest_ytd_return_not_materially_worse",
                "status": "pass" if delta_return >= -2.0 else "fail",
                "value": delta_return,
                "threshold": ">= -2pp",
                "comment": "最新AI池YTD收益不应明显弱于原版。",
            }
        )
        rows.append(
            {
                "check_name": "latest_ytd_dd_not_materially_worse",
                "status": "pass" if delta_dd >= -2.0 else "fail",
                "value": delta_dd,
                "threshold": ">= -2pp",
                "comment": "最新AI池YTD回撤不应明显深于原版。",
            }
        )
    return pd.DataFrame(rows)


def _plot_report(summary: pd.DataFrame, curves: pd.DataFrame, comparison: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(16, 10), dpi=160)
    ax_nav, ax_dd, ax_cmp, ax_margin = axes.flatten()

    full = curves[curves["window_name"].eq("full_2020_20260430")].sort_values("date")
    ax_nav.plot(pd.to_datetime(full["date"]), full["rebased_nav"], color="#1f77b4", linewidth=1.3)
    ax_nav.set_title("Stage372 recovery sleeve NAV")
    ax_nav.grid(alpha=0.25)

    ax_dd.fill_between(
        pd.to_datetime(full["date"]),
        full["drawdown_pct"].astype(float),
        0.0,
        color="#d62728",
        alpha=0.35,
    )
    ax_dd.set_title("Stage372 recovery sleeve drawdown")
    ax_dd.grid(alpha=0.25)

    start_windows = summary[summary["window_group"].eq("start_year")].copy()
    ax_cmp.bar(start_windows["window_name"], start_windows["rebased_total_return_pct"].astype(float), color="#2ca02c")
    ax_cmp.axhline(0.0, color="#333333", linewidth=0.8)
    ax_cmp.set_title("Start-window total return")
    ax_cmp.tick_params(axis="x", rotation=35)
    ax_cmp.grid(axis="y", alpha=0.25)

    ax_margin.plot(
        pd.to_datetime(full["date"]),
        full["broker10_margin_to_rebased_equity_pct"],
        color="#ff7f0e",
        linewidth=1.1,
    )
    ax_margin.axhline(90.0, color="#d62728", linestyle="--", linewidth=0.8)
    ax_margin.axhline(100.0, color="#8c0000", linestyle="--", linewidth=0.8)
    ax_margin.set_title("Broker10 margin / equity")
    ax_margin.grid(alpha=0.25)

    fig.suptitle("Stage372 Stage653 Recovery Sleeve Multiperiod Candidate", fontsize=14)
    fig.tight_layout()
    fig.savefig(CHART_PATH)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    cost: pd.DataFrame,
    rolling: pd.DataFrame,
    comparison: pd.DataFrame,
    checks: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    lines = [
        "# Stage372 Stage653 受限恢复仓 sleeve 多周期审计",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 当前 official live：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_PROFILE_NAME}`",
        "- 候选假设：只在连续亏损把风险倍率压到0.1、且已有结构恢复信号确认时，允许一个受限1手恢复仓，避免小账户永久熄火。",
        "- 约束：flat_entry、组合空仓、`long_case1a/short_case1a`、同向相关不拥挤、单手 broker10 估算保证金不超过权益20%、恢复仓开仓后20个自然日冷却。",
        "- 本阶段不修改官方实盘配置、不连接 CTP、不调用下单。",
        "",
        "## 决策检查",
        "",
        _md_table(checks),
        "",
        "## 候选多周期结果",
        "",
        _md_table(
            summary[
                [
                    "window_name",
                    "window_label",
                    "analysis_start",
                    "analysis_end",
                    "rebased_end_equity",
                    "rebased_total_return_pct",
                    "rebased_cagr_pct",
                    "rebased_max_dd_pct",
                    "rebased_sharpe",
                    "max_broker10_margin_to_rebased_equity_pct",
                    "days_over_100pct",
                    "days_over_90pct",
                    "total_slippage",
                    "total_trade_count",
                    "nonzero_daily_win_rate_pct",
                    "deployable_pass",
                ]
            ],
            max_rows=80,
        ),
        "",
        "## A/C 对比",
        "",
        _md_table(comparison, max_rows=80),
        "",
        "## 成本压力",
        "",
        _md_table(cost, max_rows=120),
        "",
        "## 滚动窗口",
        "",
        _md_table(rolling),
        "",
        "## 决策",
        "",
        f"- 决策：`{decision['decision']}`。",
        f"- 硬失败项：`{', '.join(decision['hard_fail_checks']) or '无'}`。",
        f"- 观察项：`{', '.join(decision['watch_checks']) or '无'}`。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    metadata = s513._metadata()
    spec = _official_recovery_spec(metadata)

    summary_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    cost_rows: list[dict[str, Any]] = []
    annual_source_daily: pd.DataFrame | None = None

    for window_name, window_label, group, start, end in s660.WINDOWS:
        analysis_start = pd.Timestamp(start)
        analysis_end = pd.Timestamp(end) if end else pd.Timestamp("2026-04-30")
        print(f"[stage662] running {window_name}: {analysis_start.date()} -> {analysis_end.date()}", flush=True)
        frame, forced_events = s660._run_independent_window(
            spec=spec,
            metadata=metadata,
            analysis_start=analysis_start,
            analysis_end=analysis_end,
        )
        if window_name == "full_2020_20260430":
            annual_source_daily = frame.copy()
        row, curve, costs = s660._window_metrics(
            frame,
            window_name=window_name,
            window_label=window_label,
            group=group,
            source_name="stage653_recovery_sleeve_independent_window",
            caveat=(
                "历史窗口独立重跑，20万 fresh capital；风险倍率0.1时仅对结构恢复信号允许受限1手恢复仓。"
            ),
            forced_events=forced_events,
        )
        summary_rows.append(row)
        curve_frames.append(curve)
        cost_rows.extend(costs)

    ytd_frame, ytd_forced = _run_latest_ytd_recovery(spec=spec, metadata=metadata)
    ytd_row, ytd_curve, ytd_costs = s660._window_metrics(
        ytd_frame,
        window_name="ytd_2026_latest_ai",
        window_label="2026年初至2026-06-04最新AI池恢复仓候选",
        group="latest_ytd",
        source_name="stage653_recovery_sleeve_latest_ai_ytd",
        caveat="最新 AI 池独立年初至今影子盘；同样应用受限恢复仓。",
        forced_events=ytd_forced,
    )
    summary_rows.append(ytd_row)
    curve_frames.append(ytd_curve)
    cost_rows.extend(ytd_costs)

    summary = pd.DataFrame(summary_rows)
    curves = pd.concat(curve_frames, ignore_index=True, sort=False)
    cost = pd.DataFrame(cost_rows)
    if annual_source_daily is None:
        raise RuntimeError("full window daily not generated")
    annual, monthly = s660._annual_monthly(annual_source_daily, "stage653_recovery_sleeve_full_path")
    rolling = s661._rolling_metrics(curves[curves["window_name"].eq("full_2020_20260430")])
    comparison = s661._comparison(summary, cost)
    checks = _check_rows(summary, cost, comparison, rolling)
    hard_fail_checks = checks[checks["status"].eq("fail")]["check_name"].astype(str).tolist()
    watch_checks = checks[checks["status"].eq("watch")]["check_name"].astype(str).tolist()
    decision_label = (
        "stage653_recovery_sleeve_candidate_rejected"
        if hard_fail_checks
        else "stage653_recovery_sleeve_candidate_watch_pass"
    )
    decision = {
        "stage": "Stage372",
        "script_stage": "Stage662",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "baseline": "A=Stage653 official_live_stage653_20w_force95_to80",
        "candidate": "C=Stage653 + one-lot recovery sleeve only for structure recovery signals at risk floor",
        "recovery_constraints": {
            "signals": "long_case1a,short_case1a",
            "require_flat_portfolio": True,
            "max_same_direction_corr": 0.30,
            "broker_margin_multiplier": RECOVERY_BROKER_MARGIN_MULTIPLIER,
            "max_single_contract_broker_margin_to_equity": RECOVERY_MAX_SINGLE_CONTRACT_BROKER_MARGIN_TO_EQUITY,
            "cooldown_calendar_days": RECOVERY_COOLDOWN_CALENDAR_DAYS,
        },
        "decision": decision_label,
        "hard_fail_checks": hard_fail_checks,
        "watch_checks": watch_checks,
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "cost": str(COST_PATH),
            "annual": str(ANNUAL_PATH),
            "monthly": str(MONTHLY_PATH),
            "curves": str(CURVES_PATH),
            "rolling": str(ROLLING_PATH),
            "comparison": str(COMPARISON_PATH),
            "checks": str(CHECKS_PATH),
            "report": str(REPORT_PATH),
            "chart": str(CHART_PATH),
            "decision": str(DECISION_PATH),
        },
    }

    _plot_report(summary, curves, comparison)
    _write_report(summary, cost, rolling, comparison, checks, decision)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    annual.to_csv(ANNUAL_PATH, index=False, encoding="utf-8-sig")
    monthly.to_csv(MONTHLY_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    rolling.to_csv(ROLLING_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    checks.to_csv(CHECKS_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
