#!/usr/bin/env python3
"""Stage001: revalidate the frozen Stage013 pilot on the current AI file."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
PORTFOLIO_DIR = ROOT / "examples" / "portfolio_backtesting"
SOURCE_TOOLS_DIR = (
    ROOT
    / "research"
    / "lines"
    / "futures_trend_marginal_covariance_risk_budget"
    / "tools"
)
STAGE013_TOOLS_DIR = (
    ROOT
    / "research"
    / "lines"
    / "futures_trend_rebuilt_c9_15w_optimization"
    / "tools"
)
for item in (PORTFOLIO_DIR, SOURCE_TOOLS_DIR, STAGE013_TOOLS_DIR):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import stage001_dated_marginal_covariance_budget_engine as source  # noqa: E402
import stage013_account_state_pilot_gate_engine as stage013  # noqa: E402
from qmt_roll_official_live_config import OFFICIAL_LIVE_AI_ELIGIBILITY_PATH  # noqa: E402


LINE_ID = "futures_trend_stage013_current_ai_revalidation"
STAGE_ID = "stage001_stage013_current_ai_engine"
STAGE_LABEL = "Stage001"
MODEL_TAG = f"{STAGE_ID}_v1"
OUTPUT_PREFIX = f"stage013_current_ai_{STAGE_ID}"

A_VERSION = "a_current_ai_c9_control"
C_VERSION = "c_current_ai_stage013_pilot"
A_STRATEGY = f"{STAGE_ID}_a"
C_STRATEGY = f"{STAGE_ID}_c"
VERSIONS = (A_VERSION, C_VERSION)
CAPITAL = float(source.CAPITAL)
START_MONTH = "2020-01"

RETURN_RETENTION_MIN = 0.70
FULL_DD_IMPROVEMENT_MIN_PP = 3.0
YEAR_2022_DD_IMPROVEMENT_MIN_PP = 5.0
STRESS_DD_IMPROVEMENT_MIN_PP = 3.0

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / STAGE_ID
SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
STRESS_PATH = OUT / f"{OUTPUT_PREFIX}_stress_{MODEL_TAG}.csv"
CURVES_PATH = OUT / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv.gz"
PILOT_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_pilot_audit_{MODEL_TAG}.csv"
AI_PARITY_PATH = OUT / f"{OUTPUT_PREFIX}_ai_parity_{MODEL_TAG}.csv"
AI_USAGE_PATH = OUT / f"{OUTPUT_PREFIX}_ai_usage_{MODEL_TAG}.csv"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUT / f"{OUTPUT_PREFIX}_equity_drawdown_stress_{MODEL_TAG}.png"


def _sha16(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def _eligibility(strategy: str, score_type: str, version: str) -> tuple[pd.DataFrame, Path]:
    frame = source.s006._official_eligibility_for_strategy(strategy, score_type)
    path = OUT / f"{OUTPUT_PREFIX}_{version}_eligibility_{MODEL_TAG}.csv"
    frame.to_csv(path, index=False, encoding="utf-8-sig")
    return frame, path


def _a_profile(metadata: dict[str, Any], eligibility_path: Path) -> dict[str, Any]:
    return source._profile(
        metadata,
        version=A_VERSION,
        strategy_name=A_STRATEGY,
        eligibility_path=eligibility_path,
        label="A current AI C9 control",
        candidate=False,
    )


def _c_profile(metadata: dict[str, Any], eligibility_path: Path) -> dict[str, Any]:
    profile = stage013._stage013_profile(metadata)
    spec = profile["spec"]
    overrides = {
        **spec.overrides,
        "enable_ai_product_pool_filter": True,
        "ai_product_pool_eligibility_path": str(eligibility_path),
        "ai_product_pool_strategy": C_STRATEGY,
        "account_capital": CAPITAL,
        "c3_capital": CAPITAL,
        "enable_stage013_account_state_pilot_gate": True,
        "stage013_pilot_drawdown_trigger_pct": stage013.PILOT_DRAWDOWN_TRIGGER_PCT,
        "stage013_pilot_active_positions_max": stage013.PILOT_ACTIVE_POSITIONS_MAX,
        "stage013_pilot_min_volume": stage013.PILOT_MIN_VOLUME,
    }
    capital = replace(
        spec.capital,
        variant=C_VERSION,
        label="C current AI Stage013 pilot",
        account_capital=CAPITAL,
        c3_capital=CAPITAL,
    )
    result = dict(profile)
    result["profile"] = C_VERSION
    result["strategy_cls"] = stage013.QmtRollPortfolioStrategyStage013AccountStatePilotGate
    result["spec"] = replace(
        spec,
        capital=capital,
        overrides=overrides,
        profile=C_VERSION,
    )
    return result


def _run(
    metadata: dict[str, Any],
    profile: dict[str, Any],
    version: str,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    daily, frames, _ = source.s006._run_profile(metadata, profile, version)
    trade_events = frames.get("trade_events", pd.DataFrame()).copy()
    if version == C_VERSION and not trade_events.empty and "reason" in trade_events.columns:
        frames["pilot_gate_events"] = trade_events[
            trade_events["reason"].astype(str).eq("stage013_account_state_pilot_gate")
        ].copy()
    else:
        frames["pilot_gate_events"] = pd.DataFrame()
    daily = daily.copy()
    daily["stage"] = STAGE_LABEL
    daily["model_tag"] = MODEL_TAG
    daily["line_id"] = LINE_ID
    daily["requested_start_month"] = START_MONTH
    for name, frame in list(frames.items()):
        frame = frame.copy()
        if not frame.empty:
            frame["stage"] = STAGE_LABEL
            frame["model_tag"] = MODEL_TAG
            frame["line_id"] = LINE_ID
            frame["start_month"] = START_MONTH
        frames[name] = frame
    return daily, frames


def _save_arm(version: str, daily: pd.DataFrame, frames: dict[str, pd.DataFrame]) -> None:
    daily.to_csv(
        OUT / f"{OUTPUT_PREFIX}_{version}_daily_{MODEL_TAG}.csv.gz",
        index=False,
        encoding="utf-8-sig",
    )
    for name in (
        "entry_candidates",
        "entry_risk",
        "trades",
        "trade_events",
        "stop_retry_events",
        "pilot_gate_events",
    ):
        frame = frames.get(name, pd.DataFrame())
        if not frame.empty:
            frame.to_csv(
                OUT / f"{OUTPUT_PREFIX}_{version}_{name}_{MODEL_TAG}.csv.gz",
                index=False,
                encoding="utf-8-sig",
            )


def _summary_row(
    version: str,
    daily: pd.DataFrame,
    frames: dict[str, pd.DataFrame],
    metadata: dict[str, Any],
) -> tuple[dict[str, Any], pd.DataFrame]:
    closed = source._closed_lots(frames, metadata)
    if not closed.empty:
        closed.to_csv(
            OUT / f"{OUTPUT_PREFIX}_{version}_closed_lots_{MODEL_TAG}.csv.gz",
            index=False,
            encoding="utf-8-sig",
        )
    curve = source.s006.base._curve_for_metrics(daily, version)
    row = source.s006._summarize_curve(curve)
    realized = pd.to_numeric(
        closed.get("realized_pnl", pd.Series(dtype=float)), errors="coerce"
    ).dropna()
    row.update(
        {
            "stage": STAGE_LABEL,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "requested_start_month": START_MONTH,
            "closed_lot_count": int(len(realized)),
            "closed_lot_win_rate_pct": (
                float((realized > 0.0).mean() * 100.0) if len(realized) else 0.0
            ),
        }
    )
    curve["stage"] = STAGE_LABEL
    curve["model_tag"] = MODEL_TAG
    curve["line_id"] = LINE_ID
    return row, curve


def _stress(daily_by_version: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for version, daily in daily_by_version.items():
        rows.append(
            source._window_metrics(
                daily,
                version=version,
                window="year_2022",
                start=source.YEAR_2022_START,
                end=source.YEAR_2022_END,
            )
        )
        rows.append(
            source._window_metrics(
                daily,
                version=version,
                window="main_2022_2024_stress",
                start=source.STRESS_START,
                end=source.STRESS_END,
            )
        )
    return pd.DataFrame(rows)


def _pilot_audit(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    events = frames.get("pilot_gate_events", pd.DataFrame()).copy()
    if events.empty:
        return pd.DataFrame([{"sample": "all", "rows": 0}])
    numeric = (
        "stage013_pilot_gate_selected_volume_before",
        "stage013_pilot_gate_selected_volume_after",
        "stage013_pilot_gate_reduced_volume",
        "stage013_pilot_gate_drawdown_pct",
        "stage013_pilot_gate_drawdown_trigger_pct",
        "stage013_pilot_gate_active_positions_before",
        "stage013_pilot_gate_active_positions_max",
        "stage013_pilot_gate_pilot_min_volume",
    )
    for column in numeric:
        events[column] = pd.to_numeric(events[column], errors="coerce")
    events["date"] = pd.to_datetime(events["date"], errors="coerce")
    events["year"] = events["date"].dt.year
    rows: list[dict[str, Any]] = []
    masks = [("all", pd.Series(True, index=events.index))]
    masks.extend((str(year), events["year"].eq(year)) for year in sorted(events["year"].dropna().unique()))
    for sample, mask in masks:
        part = events[mask]
        rows.append(
            {
                "sample": sample,
                "rows": int(len(part)),
                "reduced_volume_sum": float(part["stage013_pilot_gate_reduced_volume"].sum()),
                "selected_before_sum": float(part["stage013_pilot_gate_selected_volume_before"].sum()),
                "selected_after_sum": float(part["stage013_pilot_gate_selected_volume_after"].sum()),
                "drawdown_min": float(part["stage013_pilot_gate_drawdown_pct"].min()),
                "drawdown_max": float(part["stage013_pilot_gate_drawdown_pct"].max()),
                "active_positions_max": int(part["stage013_pilot_gate_active_positions_before"].max()),
                "after_not_one_count": int(
                    part["stage013_pilot_gate_selected_volume_after"].ne(1).sum()
                ),
                "below_drawdown_trigger_count": int(
                    (
                        part["stage013_pilot_gate_drawdown_pct"]
                        < part["stage013_pilot_gate_drawdown_trigger_pct"] - 1e-12
                    ).sum()
                ),
                "above_active_limit_count": int(
                    (
                        part["stage013_pilot_gate_active_positions_before"]
                        > part["stage013_pilot_gate_active_positions_max"]
                    ).sum()
                ),
                "product_count": int(part["product_vt_symbol"].nunique()),
            }
        )
    return pd.DataFrame(rows)


def _ai_parity(eligibility: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for version, frame in eligibility.items():
        rows.append(
            {
                "version": version,
                "rows": int(len(frame)),
                "eval_date_count": int(frame["eval_date"].nunique()),
                "normalized_sha16": source._normalized_ai_hash(frame),
                "official_ai_path": str(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH),
                "official_ai_sha16": _sha16(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH),
            }
        )
    result = pd.DataFrame(rows)
    result["all_normalized_equal"] = int(result["normalized_sha16"].nunique() == 1)
    return result


def _metric(frame: pd.DataFrame, version: str) -> dict[str, Any]:
    return frame[frame["version"].eq(version)].iloc[0].to_dict()


def _window(frame: pd.DataFrame, version: str, window: str) -> dict[str, Any]:
    return frame[(frame["version"].eq(version)) & (frame["window"].eq(window))].iloc[0].to_dict()


def _decision(
    summary: pd.DataFrame,
    stress: pd.DataFrame,
    pilot: pd.DataFrame,
    ai_parity: pd.DataFrame,
) -> dict[str, Any]:
    a = _metric(summary, A_VERSION)
    c = _metric(summary, C_VERSION)
    a22 = _window(stress, A_VERSION, "year_2022")
    c22 = _window(stress, C_VERSION, "year_2022")
    ast = _window(stress, A_VERSION, "main_2022_2024_stress")
    cst = _window(stress, C_VERSION, "main_2022_2024_stress")
    all_pilot = pilot[pilot["sample"].eq("all")].iloc[0]
    retention = float(c["total_return_pct"] / a["total_return_pct"])
    full_dd_delta = float(c["max_drawdown_pct"] - a["max_drawdown_pct"])
    year_dd_delta = float(c22["window_max_drawdown_pct"] - a22["window_max_drawdown_pct"])
    stress_dd_delta = float(cst["window_max_drawdown_pct"] - ast["window_max_drawdown_pct"])
    broker_delta = float(
        c["max_broker10_margin_to_equity_pct"]
        - a["max_broker10_margin_to_equity_pct"]
    )
    semantics_ok = (
        bool(ai_parity["all_normalized_equal"].all())
        and int(all_pilot["rows"]) > 0
        and int(all_pilot["after_not_one_count"]) == 0
        and int(all_pilot["below_drawdown_trigger_count"]) == 0
        and int(all_pilot["above_active_limit_count"]) == 0
    )
    performance_ok = (
        float(c["total_return_pct"]) > 0.0
        and retention >= RETURN_RETENTION_MIN
        and full_dd_delta >= FULL_DD_IMPROVEMENT_MIN_PP
        and year_dd_delta >= YEAR_2022_DD_IMPROVEMENT_MIN_PP
        and stress_dd_delta >= STRESS_DD_IMPROVEMENT_MIN_PP
        and broker_delta <= 1e-9
    )
    return {
        "stage": STAGE_LABEL,
        "stage_id": STAGE_ID,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S CST"),
        "a_control": a,
        "c_candidate": c,
        "a_year_2022": a22,
        "c_year_2022": c22,
        "a_main_stress": ast,
        "c_main_stress": cst,
        "return_retention_ratio": retention,
        "full_drawdown_delta_pct": full_dd_delta,
        "year_2022_drawdown_delta_pct": year_dd_delta,
        "main_stress_drawdown_delta_pct": stress_dd_delta,
        "broker10_peak_delta_pct": broker_delta,
        "semantics_ok": bool(semantics_ok),
        "performance_ok": bool(performance_ok),
        "decision": (
            "stage001_continue_to_halfyear_if_review_passes"
            if semantics_ok and performance_ok
            else "stage001_close_no_parameter_rescue"
        ),
        "overfit_before": "low: frozen prior Stage013 rule revalidated on current AI",
        "overfit_after": "pending_independent_review",
        "continue_value_before": "yes: targeted deep-drawdown restart risk without broad right-tail cuts",
        "continue_value_after": "pending_independent_review",
    }


def _normalized_window(
    data: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp
) -> tuple[pd.Series, pd.Series]:
    frame = data.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame[(frame["date"] >= start) & (frame["date"] <= end)].copy()
    equity = pd.to_numeric(frame["account_equity_for_metrics"], errors="coerce").ffill()
    return frame["date"], equity / float(equity.iloc[0])


def _plot(curves: pd.DataFrame) -> None:
    labels = {A_VERSION: "A current C9", C_VERSION: "C Stage013 pilot"}
    colors = {A_VERSION: "#111827", C_VERSION: "#0f766e"}
    fig, axes = plt.subplots(2, 2, figsize=(16, 9))
    for version, group in curves.groupby("version", sort=False):
        group = group.sort_values("date").copy()
        group["date"] = pd.to_datetime(group["date"], errors="coerce")
        equity = pd.to_numeric(group["account_equity_for_metrics"], errors="coerce").ffill()
        axes[0, 0].plot(group["date"], equity, label=labels[version], color=colors[version], linewidth=1.1)
        axes[1, 0].plot(
            group["date"],
            source.s006.base._drawdown_pct(equity),
            label=labels[version],
            color=colors[version],
            linewidth=1.0,
        )
        d22, n22 = _normalized_window(group, source.YEAR_2022_START, source.YEAR_2022_END)
        axes[0, 1].plot(d22, n22, label=labels[version], color=colors[version], linewidth=1.1)
        dst, nst = _normalized_window(group, source.STRESS_START, source.STRESS_END)
        axes[1, 1].plot(dst, nst, label=labels[version], color=colors[version], linewidth=1.1)
    axes[0, 0].axhline(CAPITAL, color="#64748b", linestyle="--", linewidth=0.8)
    axes[0, 0].set_title("Absolute account equity")
    axes[1, 0].set_title("Full-period drawdown")
    axes[0, 1].set_title("2022 normalized equity")
    axes[1, 1].set_title("2022-07-15 to 2024-05-10 normalized equity")
    axes[1, 0].set_ylabel("drawdown %")
    for ax in axes.flat:
        ax.grid(True, alpha=0.22)
        ax.legend(fontsize=8)
    fig.suptitle("Stage001 current-AI Stage013 pilot A/C")
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=170, bbox_inches="tight")
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    stress: pd.DataFrame,
    pilot: pd.DataFrame,
    ai_parity: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    REPORT_PATH.write_text(
        f"""# Stage001 当前 AI Stage013 pilot A/C

- 生成时间：`{decision['generated_at']}`
- 决策：`{decision['decision']}`
- 语义通过：`{decision['semantics_ok']}`
- 绩效通过：`{decision['performance_ok']}`
- 收益保留：`{decision['return_retention_ratio']:.6f}`
- C-A 全周期/2022/主压力窗回撤变化：`{decision['full_drawdown_delta_pct']:.4f}` / `{decision['year_2022_drawdown_delta_pct']:.4f}` / `{decision['main_stress_drawdown_delta_pct']:.4f}` pp
- C-A broker10 峰值变化：`{decision['broker10_peak_delta_pct']:.4f}` pp

## 全周期

{summary.to_markdown(index=False)}

## 压力窗口

{stress.to_markdown(index=False)}

## Pilot 事件

{pilot.to_markdown(index=False)}

## AI 一致性

{ai_parity.to_markdown(index=False)}
""",
        encoding="utf-8",
    )


def build() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    metadata = source._metadata()
    a_eligibility, a_path = _eligibility(A_STRATEGY, A_VERSION, A_VERSION)
    c_eligibility, c_path = _eligibility(C_STRATEGY, C_VERSION, C_VERSION)
    eligibility = {A_VERSION: a_eligibility, C_VERSION: c_eligibility}
    profiles = {
        A_VERSION: _a_profile(metadata, a_path),
        C_VERSION: _c_profile(metadata, c_path),
    }
    daily_by_version: dict[str, pd.DataFrame] = {}
    frames_by_version: dict[str, dict[str, pd.DataFrame]] = {}
    summary_rows: list[dict[str, Any]] = []
    curves: list[pd.DataFrame] = []
    for version in VERSIONS:
        daily, frames = _run(metadata, profiles[version], version)
        daily_by_version[version] = daily
        frames_by_version[version] = frames
        _save_arm(version, daily, frames)
        row, curve = _summary_row(version, daily, frames, metadata)
        summary_rows.append(row)
        curves.append(curve)
    summary = pd.DataFrame(summary_rows)
    curve_frame = pd.concat(curves, ignore_index=True, sort=False)
    stress = _stress(daily_by_version)
    pilot = _pilot_audit(frames_by_version[C_VERSION])
    ai_parity = _ai_parity(eligibility)
    ai_usage = source.s006._ai_usage_audit(frames_by_version)
    decision = _decision(summary, stress, pilot, ai_parity)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    stress.to_csv(STRESS_PATH, index=False, encoding="utf-8-sig")
    curve_frame.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    pilot.to_csv(PILOT_AUDIT_PATH, index=False, encoding="utf-8-sig")
    ai_parity.to_csv(AI_PARITY_PATH, index=False, encoding="utf-8-sig")
    ai_usage.to_csv(AI_USAGE_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(
        json.dumps(source.s006.base._json_safe(decision), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _plot(curve_frame)
    _write_report(summary, stress, pilot, ai_parity, decision)
    return {
        "summary": summary,
        "stress": stress,
        "pilot": pilot,
        "ai_parity": ai_parity,
        "decision": decision,
    }


if __name__ == "__main__":
    result = build()
    print(result["summary"].to_string(index=False))
    print(json.dumps(source.s006.base._json_safe(result["decision"]), ensure_ascii=False, indent=2))
