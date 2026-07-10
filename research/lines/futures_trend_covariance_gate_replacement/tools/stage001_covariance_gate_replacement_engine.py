#!/usr/bin/env python3
"""Stage001: replace the legacy correlation gate with marginal covariance."""

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
import numpy as np
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
for item in (PORTFOLIO_DIR, SOURCE_TOOLS_DIR):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import stage001_dated_marginal_covariance_budget_engine as source  # noqa: E402
from qmt_roll_official_live_config import OFFICIAL_LIVE_AI_ELIGIBILITY_PATH  # noqa: E402


LINE_ID = "futures_trend_covariance_gate_replacement"
STAGE_ID = "stage001_covariance_gate_replacement_engine"
STAGE_LABEL = "Stage001"
MODEL_TAG = f"{STAGE_ID}_v1"
OUTPUT_PREFIX = f"cov_gate_replacement_{STAGE_ID}"

START_MONTH = "2020-01"
CAPITAL = float(source.CAPITAL)
LOOKBACK_RETURNS = int(source.LOOKBACK_RETURNS)

A_VERSION = "a_current_c9_legacy_corr_gate"
B_VERSION = "b_current_c9_no_corr_gate"
C_VERSION = "c_current_c9_marginal_cov_replacement"
VERSIONS = (A_VERSION, B_VERSION, C_VERSION)

RETURN_RETENTION_MIN = 0.70
FULL_DD_IMPROVEMENT_MIN_PP = 3.0
YEAR_2022_DD_IMPROVEMENT_MIN_PP = 5.0
STRESS_DD_IMPROVEMENT_MIN_PP = 3.0
MIN_POTENTIAL_COVERAGE = 0.80

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / STAGE_ID

SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
STRESS_PATH = OUT / f"{OUTPUT_PREFIX}_stress_{MODEL_TAG}.csv"
CURVES_PATH = OUT / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv.gz"
AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_marginal_audit_{MODEL_TAG}.csv"
GATE_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_gate_audit_{MODEL_TAG}.csv"
AI_PARITY_PATH = OUT / f"{OUTPUT_PREFIX}_ai_parity_{MODEL_TAG}.csv"
AI_USAGE_PATH = OUT / f"{OUTPUT_PREFIX}_ai_usage_{MODEL_TAG}.csv"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUT / f"{OUTPUT_PREFIX}_equity_drawdown_stress_{MODEL_TAG}.png"


def _sha16(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def _eligibility(version: str) -> tuple[pd.DataFrame, Path]:
    strategy_name = f"{STAGE_ID}_{version}"
    frame = source.s006._official_eligibility_for_strategy(strategy_name, version)
    path = OUT / f"{OUTPUT_PREFIX}_{version}_eligibility_{MODEL_TAG}.csv"
    frame.to_csv(path, index=False, encoding="utf-8-sig")
    return frame, path


def _profile(
    metadata: dict[str, Any],
    *,
    version: str,
    eligibility_path: Path,
    marginal: bool,
) -> dict[str, Any]:
    profile = source._profile(
        metadata,
        version=version,
        strategy_name=f"{STAGE_ID}_{version}",
        eligibility_path=eligibility_path,
        label=version,
        candidate=marginal,
    )
    if version == A_VERSION:
        return profile
    spec = profile["spec"]
    overrides = {
        **spec.overrides,
        "enable_same_direction_correlation_gate": False,
    }
    result = dict(profile)
    result["spec"] = replace(spec, overrides=overrides, profile=version)
    result["profile"] = version
    return result


def _tag_frames(
    daily: pd.DataFrame,
    frames: dict[str, pd.DataFrame],
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
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


def _run(
    metadata: dict[str, Any],
    profile: dict[str, Any],
    version: str,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    daily, frames, _ = source.s006._run_profile(metadata, profile, version)
    return _tag_frames(daily, frames)


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


def _gate_audit(frames_by_version: dict[str, dict[str, pd.DataFrame]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for version, frames in frames_by_version.items():
        data = frames.get("entry_candidates", pd.DataFrame()).copy()
        if data.empty:
            rows.append({"version": version, "candidate_rows": 0})
            continue
        def numeric(column: str, default: float = 0.0) -> pd.Series:
            values = data[column] if column in data.columns else pd.Series(default, index=data.index)
            return pd.to_numeric(values, errors="coerce").fillna(default)

        opened = numeric("is_opened").eq(1)
        corr_weight = numeric("same_direction_correlation_gate_weight", 1.0)
        marginal_reduced = numeric("marginal_covariance_volume_reduced").gt(0)
        selected = numeric("selected_volume")
        ungated = numeric("selected_volume_ungated") if "selected_volume_ungated" in data.columns else selected
        rows.append(
            {
                "version": version,
                "candidate_rows": int(len(data)),
                "opened_rows": int(opened.sum()),
                "legacy_corr_enabled_rows": int(
                    numeric("same_direction_correlation_gate_enabled").gt(0).sum()
                ),
                "legacy_corr_reduced_rows": int(corr_weight.lt(1.0 - 1e-12).sum()),
                "legacy_corr_reduced_opened_rows": int(
                    (opened & corr_weight.lt(1.0 - 1e-12)).sum()
                ),
                "marginal_reduced_rows": int(marginal_reduced.sum()),
                "marginal_reduced_opened_rows": int((opened & marginal_reduced).sum()),
                "selected_volume_sum": float(selected.sum()),
                "selected_volume_ungated_sum": float(ungated.sum()),
            }
        )
    return pd.DataFrame(rows)


def _ai_parity(eligibility_by_version: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for version, frame in eligibility_by_version.items():
        rows.append(
            {
                "version": version,
                "rows": int(len(frame)),
                "normalized_sha16": source._normalized_ai_hash(frame),
                "official_ai_path": str(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH),
                "official_ai_sha16": _sha16(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH),
            }
        )
    result = pd.DataFrame(rows)
    result["all_normalized_equal"] = int(result["normalized_sha16"].nunique() == 1)
    return result


def _row(frame: pd.DataFrame, version: str) -> dict[str, Any]:
    return frame[frame["version"].eq(version)].iloc[0].to_dict()


def _stress_row(stress: pd.DataFrame, version: str, window: str) -> dict[str, Any]:
    return stress[(stress["version"].eq(version)) & (stress["window"].eq(window))].iloc[0].to_dict()


def _decision(
    summary: pd.DataFrame,
    stress: pd.DataFrame,
    audit: pd.DataFrame,
    ai_parity: pd.DataFrame,
) -> dict[str, Any]:
    a = _row(summary, A_VERSION)
    b = _row(summary, B_VERSION)
    c = _row(summary, C_VERSION)
    a22 = _stress_row(stress, A_VERSION, "year_2022")
    b22 = _stress_row(stress, B_VERSION, "year_2022")
    c22 = _stress_row(stress, C_VERSION, "year_2022")
    ast = _stress_row(stress, A_VERSION, "main_2022_2024_stress")
    bst = _stress_row(stress, B_VERSION, "main_2022_2024_stress")
    cst = _stress_row(stress, C_VERSION, "main_2022_2024_stress")
    all_audit = audit[audit["sample"].eq("all_candidates")].iloc[0]
    available = audit[audit["sample"].eq("available")].iloc[0]
    potential = audit[audit["sample"].eq("potential_opened")].iloc[0]

    retention = float(c["total_return_pct"] / a["total_return_pct"])
    full_dd_delta = float(c["max_drawdown_pct"] - a["max_drawdown_pct"])
    year_dd_delta = float(c22["window_max_drawdown_pct"] - a22["window_max_drawdown_pct"])
    stress_dd_delta = float(cst["window_max_drawdown_pct"] - ast["window_max_drawdown_pct"])
    broker_delta = float(
        c["max_broker10_margin_to_equity_pct"]
        - a["max_broker10_margin_to_equity_pct"]
    )
    same_day_final_target_semantics_ok = False
    semantics_ok = (
        bool(ai_parity["all_normalized_equal"].all())
        and int(available["observation_min"]) == LOOKBACK_RETURNS
        and int(available["observation_max"]) == LOOKBACK_RETURNS
        and int(all_audit["future_date_violation_count"]) == 0
        and int(available["last_date_lag_max"]) == 0
        and int(all_audit["final_gt_before_count"]) == 0
        and int(all_audit["positive_before_zero_after_count"]) == 0
        and int(all_audit["diversifying_reduced_count"]) == 0
        and float(potential["potential_coverage_ratio"]) >= MIN_POTENTIAL_COVERAGE
        and same_day_final_target_semantics_ok
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
        "b_no_legacy_gate": b,
        "c_replacement": c,
        "a_year_2022": a22,
        "b_year_2022": b22,
        "c_year_2022": c22,
        "a_main_stress": ast,
        "b_main_stress": bst,
        "c_main_stress": cst,
        "return_retention_ratio": retention,
        "full_drawdown_delta_pct": full_dd_delta,
        "year_2022_drawdown_delta_pct": year_dd_delta,
        "main_stress_drawdown_delta_pct": stress_dd_delta,
        "broker10_peak_delta_pct": broker_delta,
        "c_vs_b_full_drawdown_delta_pct": float(
            c["max_drawdown_pct"] - b["max_drawdown_pct"]
        ),
        "c_vs_b_year_2022_drawdown_delta_pct": float(
            c22["window_max_drawdown_pct"] - b22["window_max_drawdown_pct"]
        ),
        "c_vs_b_main_stress_drawdown_delta_pct": float(
            cst["window_max_drawdown_pct"] - bst["window_max_drawdown_pct"]
        ),
        "same_day_final_target_semantics_ok": same_day_final_target_semantics_ok,
        "semantics_ok": bool(semantics_ok),
        "performance_ok": bool(performance_ok),
        "decision": "invalid_semantics_and_close_no_rescue",
        "overfit_before": "low: one structural replacement, no threshold/window/product/date scan",
        "overfit_after": "low: frozen structural test; invalid result closed without rescue",
        "continue_value_before": "yes: isolates legacy correlation gate from marginal covariance",
        "continue_value_after": "no: final-target semantics has P1 and all performance gates fail",
    }


def _window_normalized(
    data: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> tuple[pd.Series, pd.Series]:
    frame = data.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame[(frame["date"] >= start) & (frame["date"] <= end)].copy()
    equity = pd.to_numeric(frame["account_equity_for_metrics"], errors="coerce").ffill()
    normalized = equity / float(equity.iloc[0]) if len(equity) else equity
    return frame["date"], normalized


def _plot(curves: pd.DataFrame) -> None:
    labels = {
        A_VERSION: "A current C9 legacy gate",
        B_VERSION: "B no correlation gate",
        C_VERSION: "C marginal covariance replacement",
    }
    colors = {A_VERSION: "#111827", B_VERSION: "#b45309", C_VERSION: "#0f766e"}
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
        dates22, norm22 = _window_normalized(group, source.YEAR_2022_START, source.YEAR_2022_END)
        axes[0, 1].plot(dates22, norm22, label=labels[version], color=colors[version], linewidth=1.1)
        dates_st, norm_st = _window_normalized(group, source.STRESS_START, source.STRESS_END)
        axes[1, 1].plot(dates_st, norm_st, label=labels[version], color=colors[version], linewidth=1.1)
    axes[0, 0].axhline(CAPITAL, color="#64748b", linestyle="--", linewidth=0.8)
    axes[0, 0].set_title("Absolute account equity")
    axes[1, 0].set_title("Full-period drawdown")
    axes[0, 1].set_title("2022 normalized equity")
    axes[1, 1].set_title("2022-07-15 to 2024-05-10 normalized equity")
    axes[1, 0].set_ylabel("drawdown %")
    for ax in axes.flat:
        ax.grid(True, alpha=0.22)
        ax.legend(fontsize=8)
    fig.suptitle("Stage001 correlation-gate replacement A/B/C")
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=170, bbox_inches="tight")
    plt.close(fig)


def _md(frame: pd.DataFrame) -> str:
    return frame.to_markdown(index=False)


def _write_report(
    summary: pd.DataFrame,
    stress: pd.DataFrame,
    audit: pd.DataFrame,
    gate_audit: pd.DataFrame,
    ai_parity: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    report = f"""# Stage001 相关门替换 A/B/C 真引擎

- 生成时间：`{decision['generated_at']}`
- 决策：`{decision['decision']}`
- 语义通过：`{decision['semantics_ok']}`
- 绩效通过：`{decision['performance_ok']}`
- 收益保留：`{decision['return_retention_ratio']:.6f}`
- C-A 全周期/2022/主压力窗回撤变化：`{decision['full_drawdown_delta_pct']:.4f}` / `{decision['year_2022_drawdown_delta_pct']:.4f}` / `{decision['main_stress_drawdown_delta_pct']:.4f}` pp
- C-A broker10 峰值变化：`{decision['broker10_peak_delta_pct']:.4f}` pp

## 全周期

{_md(summary)}

## 压力窗口

{_md(stress)}

## 相关门触发

{_md(gate_audit)}

## 边际协方差语义

{_md(audit)}

## AI 一致性

{_md(ai_parity)}
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def build() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    metadata = source._metadata()
    eligibility_by_version: dict[str, pd.DataFrame] = {}
    eligibility_paths: dict[str, Path] = {}
    for version in VERSIONS:
        eligibility_by_version[version], eligibility_paths[version] = _eligibility(version)

    profiles = {
        A_VERSION: _profile(
            metadata,
            version=A_VERSION,
            eligibility_path=eligibility_paths[A_VERSION],
            marginal=False,
        ),
        B_VERSION: _profile(
            metadata,
            version=B_VERSION,
            eligibility_path=eligibility_paths[B_VERSION],
            marginal=False,
        ),
        C_VERSION: _profile(
            metadata,
            version=C_VERSION,
            eligibility_path=eligibility_paths[C_VERSION],
            marginal=True,
        ),
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
    audit = source._marginal_audit(frames_by_version[C_VERSION]["entry_candidates"])
    gate_audit = _gate_audit(frames_by_version)
    ai_parity = _ai_parity(eligibility_by_version)
    ai_usage = source.s006._ai_usage_audit(frames_by_version)
    decision = _decision(summary, stress, audit, ai_parity)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    stress.to_csv(STRESS_PATH, index=False, encoding="utf-8-sig")
    curve_frame.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    audit.to_csv(AUDIT_PATH, index=False, encoding="utf-8-sig")
    gate_audit.to_csv(GATE_AUDIT_PATH, index=False, encoding="utf-8-sig")
    ai_parity.to_csv(AI_PARITY_PATH, index=False, encoding="utf-8-sig")
    ai_usage.to_csv(AI_USAGE_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(
        json.dumps(source.s006.base._json_safe(decision), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _plot(curve_frame)
    _write_report(summary, stress, audit, gate_audit, ai_parity, decision)
    return {
        "summary": summary,
        "stress": stress,
        "audit": audit,
        "gate_audit": gate_audit,
        "ai_parity": ai_parity,
        "decision": decision,
    }


if __name__ == "__main__":
    result = build()
    print(result["summary"].to_string(index=False))
    print(json.dumps(source.s006.base._json_safe(result["decision"]), ensure_ascii=False, indent=2))
