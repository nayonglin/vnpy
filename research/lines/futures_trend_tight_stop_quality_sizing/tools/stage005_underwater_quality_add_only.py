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
LINE_ID = "futures_trend_tight_stop_quality_sizing"
LINE_DIR = ROOT / "research" / "lines" / LINE_ID
TOOLS_DIR = LINE_DIR / "tools"
PORTFOLIO_DIR = ROOT / "examples" / "portfolio_backtesting"
for path in (str(TOOLS_DIR), str(PORTFOLIO_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

import stage003_lower_half_stop_moderate_body_risk_transfer as s003  # noqa: E402
import stage004_underwater_only_quality_transfer as s004  # noqa: E402


STAGE = "Stage005"
MODEL_TAG = "stage005_underwater_quality_add_only_v1"
PROFILE_NAME = "stage005_underwater_quality_add_only"
OUTPUT_PREFIX = "tight_stop_quality_stage005"
VARIANT = "C_stage005"
STARTS = s003.STARTS
END = s003.END
EXPECTED_CAPITAL = s003.EXPECTED_CAPITAL

OUT = LINE_DIR / "outputs" / "stage005_underwater_quality_add_only"
SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COMPARISON_PATH = OUT / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
CURVES_PATH = OUT / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv.gz"
TRADES_PATH = OUT / f"{OUTPUT_PREFIX}_ab_trades_{MODEL_TAG}.csv.gz"
ENTRY_CANDIDATES_PATH = OUT / f"{OUTPUT_PREFIX}_ab_entry_candidates_{MODEL_TAG}.csv.gz"
ENTRY_RISK_PATH = OUT / f"{OUTPUT_PREFIX}_ab_entry_risk_{MODEL_TAG}.csv.gz"
TRADE_EVENTS_PATH = OUT / f"{OUTPUT_PREFIX}_ab_trade_events_{MODEL_TAG}.csv.gz"
STOP_RETRY_EVENTS_PATH = OUT / f"{OUTPUT_PREFIX}_ab_stop_retry_events_{MODEL_TAG}.csv.gz"
STOP_RETRY_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_stop_retry_audit_{MODEL_TAG}.csv"
AI_MONTH_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_ai_month_audit_{MODEL_TAG}.csv"
CONFIG_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_config_audit_{MODEL_TAG}.csv"
FEATURE_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_feature_audit_{MODEL_TAG}.csv"
CHART_PATH = OUT / f"{OUTPUT_PREFIX}_four_anchor_equity_drawdown_{MODEL_TAG}.png"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
INPUT_MANIFEST_PATH = OUT / f"{OUTPUT_PREFIX}_input_manifest_{MODEL_TAG}.csv"
MANIFEST_PATH = OUT / f"{OUTPUT_PREFIX}_manifest_{MODEL_TAG}.csv"

STAGE005_AUDIT_FIELDS = (
    "stage005_quality_add_only",
    "stage005_budget_weight",
    "stage005_reason",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stage005_reason(snapshot: dict[str, Any]) -> str:
    if not int(snapshot.get("stage004_underwater_gate_active") or 0):
        return "high_water_unchanged"
    stage003_reason = str(snapshot.get("stage003_reason") or "")
    if stage003_reason == "quality_risk_increase":
        return "underwater_quality_risk_increase"
    if stage003_reason == "other_risk_decrease":
        return "underwater_other_unchanged"
    return stage003_reason or "unknown"


def _stage005_payload(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage005_quality_add_only": 1,
        "stage005_budget_weight": float(snapshot.get("stage003_budget_weight", 1.0) or 1.0),
        "stage005_reason": _stage005_reason(snapshot),
    }


class QmtRollPortfolioStrategyStage005UnderwaterQualityAddOnly(s004.QmtRollPortfolioStrategyStage004UnderwaterOnly):
    def _calculate_entry_sizing(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        result = super()._calculate_entry_sizing(*args, **kwargs)
        result.update(_stage005_payload(result))
        return result

    def _record_entry_candidate_snapshot(self, *args: Any, **kwargs: Any) -> None:
        sizing_snapshot = kwargs.get("sizing_snapshot")
        super()._record_entry_candidate_snapshot(*args, **kwargs)
        if isinstance(sizing_snapshot, dict) and self.entry_candidate_snapshots:
            self.entry_candidate_snapshots[-1].update(
                {key: sizing_snapshot.get(key) for key in STAGE005_AUDIT_FIELDS}
            )

    def _record_entry_risk_diagnostic(self, *args: Any, **kwargs: Any) -> None:
        sizing_snapshot = kwargs.get("sizing_snapshot")
        super()._record_entry_risk_diagnostic(*args, **kwargs)
        if isinstance(sizing_snapshot, dict) and self.entry_risk_diagnostics:
            self.entry_risk_diagnostics[-1].update(
                {key: sizing_snapshot.get(key) for key in STAGE005_AUDIT_FIELDS}
            )


def _candidate_profile(metadata: dict[str, Any]) -> dict[str, Any]:
    base = s004._candidate_profile(metadata)
    spec = base["spec"]
    result = dict(base)
    result["profile"] = PROFILE_NAME
    result["strategy_cls"] = QmtRollPortfolioStrategyStage005UnderwaterQualityAddOnly
    result["spec"] = replace(
        spec,
        overrides={**spec.overrides, "stage003_other_weight": 1.0},
        profile=PROFILE_NAME,
    )
    return result


def config_audit(metadata: dict[str, Any]) -> pd.DataFrame:
    base = s003._official_profile(metadata)
    candidate = _candidate_profile(metadata)
    a_overrides = dict(base["spec"].overrides)
    c_overrides = dict(candidate["spec"].overrides)
    allowed = {
        "enable_stage003_risk_transfer",
        "stage003_stop_atr_max",
        "stage003_body_min_exclusive",
        "stage003_body_max_inclusive",
        "stage003_quality_weight",
        "stage003_other_weight",
        "enable_stage004_underwater_only",
    }
    rows = []
    for key in sorted(set(a_overrides) | set(c_overrides)):
        a = a_overrides.get(key, "<missing>")
        c = c_overrides.get(key, "<missing>")
        changed = a != c
        rows.append({"key": key, "A": a, "C": c, "changed": int(changed), "allowed": int(key in allowed)})
        if changed and key not in allowed:
            raise RuntimeError(f"unexpected Stage005 A/C override difference: {key}")
    return pd.DataFrame(rows)


def _run_candidate(metadata: dict[str, Any], start: pd.Timestamp) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    original_start = s003.s847.START
    original_end = s003.s847.END
    original_minute = s003.s847.s827._GLOBAL_MINUTE_BY_SYMBOL
    s003.install_repaired_minute_sessions(metadata)
    try:
        s003._begin_repaired_minute_run()
        s003.s847.START = start.normalize()
        s003.s847.END = END.normalize()
        profile = _candidate_profile(metadata)
        combined, frames = s003._run_profile_with_repaired_engine(profile, metadata)
        s003._assert_repaired_minute_run_complete()
        strict_open_audit = s003._annotate_and_validate_strict_open_trades(frames.get("trades", pd.DataFrame()))
        spec = profile["spec"]
    finally:
        s003.s847.START = original_start
        s003.s847.END = original_end
        s003.s847.s827._GLOBAL_MINUTE_BY_SYMBOL = original_minute
    combined["account_capital"] = spec.capital.account_capital
    combined["profile"] = spec.profile
    combined["strict_root_open_count"] = strict_open_audit["root_open_count"]
    combined["strict_open_match_count"] = strict_open_audit["strict_open_match_count"]
    for frame in frames.values():
        if not frame.empty:
            frame["account_capital"] = spec.capital.account_capital
            frame["profile"] = spec.profile
            frame["minute_source"] = str(s003.REPAIRED_MINUTE_PATCH_PATH)
    return combined, frames


def _comparison(summary: pd.DataFrame) -> pd.DataFrame:
    compatible = summary.copy()
    compatible["variant"] = compatible["variant"].replace({VARIANT: "C_stage003"})
    return s003._comparison(compatible)


def validate_feature_evidence(candidates: pd.DataFrame) -> dict[str, Any]:
    required = set(STAGE005_AUDIT_FIELDS)
    missing = sorted(required - set(candidates.columns))
    if candidates.empty or missing:
        raise RuntimeError(f"Stage005 evidence missing: rows={len(candidates)}, columns={missing}")
    base = s004.validate_feature_evidence(candidates)
    if not pd.to_numeric(candidates["stage005_quality_add_only"], errors="coerce").eq(1).all():
        raise RuntimeError("Stage005 contains disabled evidence")
    active = pd.to_numeric(candidates["stage004_underwater_gate_active"], errors="coerce").eq(1)
    quality = pd.to_numeric(candidates["stage003_quality_hit"], errors="coerce").eq(1)
    weight = pd.to_numeric(candidates["stage005_budget_weight"], errors="coerce")
    if not np.allclose(weight[active & quality], s003.QUALITY_WEIGHT, rtol=0.0, atol=1e-12):
        raise RuntimeError("Stage005 underwater quality weight drift")
    if not np.allclose(weight[~(active & quality)], 1.0, rtol=0.0, atol=1e-12):
        raise RuntimeError("Stage005 changed high-water or non-quality risk")
    expected_reason = candidates.apply(lambda row: _stage005_reason(row.to_dict()), axis=1)
    if not candidates["stage005_reason"].astype(str).eq(expected_reason.astype(str)).all():
        raise RuntimeError("Stage005 reason audit mismatch")
    base.update(
        {
            "underwater_quality_add_count": int((active & quality).sum()),
            "unchanged_count": int((~(active & quality)).sum()),
        }
    )
    return base


def _feature_audit(candidates: pd.DataFrame) -> pd.DataFrame:
    return (
        candidates.groupby(["requested_start_month", "stage005_reason"], dropna=False)
        .agg(
            candidate_count=("candidate_index", "size"),
            opened_count=("is_opened", lambda values: int(pd.to_numeric(values, errors="coerce").fillna(0).sum())),
            average_drawdown=("stage004_portfolio_drawdown_pct", "mean"),
            average_budget_weight=("stage005_budget_weight", "mean"),
        )
        .reset_index()
        .sort_values(["requested_start_month", "stage005_reason"])
    )


def _plot(curves: pd.DataFrame) -> None:
    with plt.style.context("default"):
        fig, axes = plt.subplots(3, 1, figsize=(18, 14), sharex=True, constrained_layout=True)
        starts = sorted(curves["requested_start_month"].unique())
        colors = {start: color for start, color in zip(starts, plt.cm.tab10.colors)}
        for (start, variant), group in curves.groupby(["requested_start_month", "variant"]):
            group = group.sort_values("date")
            style = "-" if variant == "A_official" else "--"
            label = f"{start} {variant}"
            axes[0].plot(group["date"], group["account_equity"], color=colors[start], linestyle=style, linewidth=1.15, label=label)
            axes[1].plot(group["date"], group["nav"], color=colors[start], linestyle=style, linewidth=1.05)
            axes[2].plot(group["date"], group["drawdown_pct"], color=colors[start], linestyle=style, linewidth=1.0)
        axes[0].axhline(EXPECTED_CAPITAL, color="#111827", linestyle=":", linewidth=0.8)
        for axis, title, label in zip(
            axes,
            ("Stage005 A/C absolute equity", "Normalized NAV by start", "Drawdown"),
            ("equity", "NAV", "drawdown %"),
        ):
            axis.set_title(title)
            axis.set_ylabel(label)
            axis.grid(alpha=0.2)
        axes[2].set_xlabel("date")
        axes[0].legend(ncol=4, fontsize=8)
        fig.savefig(CHART_PATH, dpi=160, facecolor="white")
        plt.close(fig)


def main() -> None:
    if s003.OFFICIAL_LIVE_VERSION != s003.EXPECTED_VERSION or abs(float(s003.OFFICIAL_LIVE_CAPITAL) - EXPECTED_CAPITAL) > 1e-9:
        raise RuntimeError("official version/capital drift")
    OUT.mkdir(parents=True, exist_ok=True)
    metadata = s003.s901.s513._metadata()
    minute_audit = s003.install_repaired_minute_sessions(metadata)
    config = config_audit(metadata)
    summary_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    evidence: dict[str, list[pd.DataFrame]] = {
        "trades": [], "entry_candidates": [], "entry_risk": [], "trade_events": [], "stop_retry_events": []
    }

    def append_frames(frames: dict[str, pd.DataFrame], start: pd.Timestamp, variant: str) -> None:
        for name in evidence:
            frame = frames.get(name, pd.DataFrame())
            if not frame.empty:
                evidence[name].append(s003._tag_evidence(frame, start, variant))

    for index, start in enumerate(STARTS, start=1):
        print(f"[stage005] {index}/{len(STARTS)} A start={start.date()}", flush=True)
        a_curve, a_frames = s003._run_official_repaired(metadata, start)
        summary_rows.append(s003.summarize_curve(a_curve, start, "A_official"))
        curve_frames.append(s003._tag_curve(a_curve, start, "A_official"))
        append_frames(a_frames, start, "A_official")
        print(f"[stage005] {index}/{len(STARTS)} C start={start.date()}", flush=True)
        c_curve, c_frames = _run_candidate(metadata, start)
        summary_rows.append(s003.summarize_curve(c_curve, start, VARIANT))
        curve_frames.append(s003._tag_curve(c_curve, start, VARIANT))
        append_frames(c_frames, start, VARIANT)

    summary = pd.DataFrame(summary_rows).sort_values(["requested_start_month", "variant"]).reset_index(drop=True)
    curves = pd.concat(curve_frames, ignore_index=True, sort=False)
    frames = {name: pd.concat(items, ignore_index=True, sort=False) if items else pd.DataFrame() for name, items in evidence.items()}
    candidates = frames["entry_candidates"]
    candidate_evidence = candidates[candidates["variant"].astype(str).eq(VARIANT)].copy()
    comparison = _comparison(summary)
    feature_summary = validate_feature_evidence(candidate_evidence)
    account_equity_summary = s003.validate_account_equity_evidence(candidates, curves)
    feature_audit = _feature_audit(candidate_evidence)
    ai_audit = s003._ai_audit(candidate_evidence, summary[summary["variant"].astype(str).eq(VARIANT)].copy())
    ai_audit["variant"] = VARIANT
    retry_audit = s003.stop_retry_audit(frames["trades"], frames["stop_retry_events"], summary)
    if int(ai_audit["status"].eq("FAIL").sum()) != 0:
        raise RuntimeError("Stage005 AI month audit failed")
    if any(s003.is_ai_derived_field(column) for column in STAGE005_AUDIT_FIELDS):
        raise RuntimeError("Stage005 introduced an AI-derived feature")

    start_2022 = comparison[comparison["requested_start_month"].eq("2022-01")]
    gate = bool(
        len(comparison) == len(STARTS)
        and comparison["positive_return_pass"].eq(1).all()
        and comparison["retention_70_pass"].eq(1).all()
        and comparison["dd_not_worse_1pp_pass"].eq(1).all()
        and int(comparison["dd_improve_3pp_pass"].sum()) >= 3
        and not start_2022.empty
        and int(start_2022["dd_improve_3pp_pass"].iloc[0]) == 1
    )
    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "official_live_version": s003.OFFICIAL_LIVE_VERSION,
        "minute_evidence": minute_audit,
        "candidate_new_ai_feature_count": 0,
        "feature_evidence_summary": feature_summary,
        "strict_account_equity_reconciliation": account_equity_summary,
        "strict_root_open_reconciliation_pass": True,
        "stop_retry_reconciliation_pass": True,
        "four_anchor_gate_pass": gate,
        "decision": "pending_independent_review" if gate else "failed_four_anchor_gate_pending_independent_review",
        "extend_half_year_allowed": False,
        "overfit_before": "高；质量定义来自当前样本，本轮只做单边增仓消融。",
        "overfit_after": "待独立 review；未扫描任何参数。",
        "continue_after": "待独立 review 与四锚点硬门判断。",
    }

    summary.to_csv(SUMMARY_PATH, index=False)
    comparison.to_csv(COMPARISON_PATH, index=False)
    curves.to_csv(CURVES_PATH, index=False, compression="gzip")
    frames["trades"].to_csv(TRADES_PATH, index=False, compression="gzip")
    candidates.to_csv(ENTRY_CANDIDATES_PATH, index=False, compression="gzip")
    frames["entry_risk"].to_csv(ENTRY_RISK_PATH, index=False, compression="gzip")
    frames["trade_events"].to_csv(TRADE_EVENTS_PATH, index=False, compression="gzip")
    frames["stop_retry_events"].to_csv(STOP_RETRY_EVENTS_PATH, index=False, compression="gzip")
    retry_audit.to_csv(STOP_RETRY_AUDIT_PATH, index=False)
    ai_audit.to_csv(AI_MONTH_AUDIT_PATH, index=False)
    config.to_csv(CONFIG_AUDIT_PATH, index=False)
    feature_audit.to_csv(FEATURE_AUDIT_PATH, index=False)
    _plot(curves)
    DECISION_PATH.write_text(json.dumps(s003._json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT_PATH.write_text(
        "\n".join([
            "# Stage005 水下高质量机会单边增仓 A/B", "",
            f"- 生成时间：`{decision['generated_at']}`", f"- 决策：`{decision['decision']}`",
            f"- 四锚点硬门：`{gate}`", "- 新增 AI 特征：`0`；水下只增加质量机会预算，普通机会不降风险。",
            "", "## A/C 摘要", "", s003._md_table(summary), "", "## 硬门", "", s003._md_table(comparison),
            "", "## 状态与特征审计", "", s003._md_table(feature_audit),
            "", "## 成交与重试守恒", "", s003._md_table(retry_audit),
        ]) + "\n",
        encoding="utf-8",
    )
    input_paths = [
        Path(__file__), Path(s004.__file__), Path(s003.__file__), ROOT / ".vntrader" / "database.db",
        Path(s003.OFFICIAL_LIVE_AI_ELIGIBILITY_PATH), s003.REPAIRED_MINUTE_PATCH_PATH,
        s003.REPAIRED_MINUTE_AUDIT_PATH, Path(s003.s000.DECISION_PATH),
        PORTFOLIO_DIR / "qmt_roll_official_live_config.py", Path(s003.s847.__file__),
    ]
    missing = [str(path) for path in input_paths if not path.exists()]
    if missing:
        raise RuntimeError(f"Stage005 missing input files: {missing}")
    pd.DataFrame([{"path": str(path), "bytes": path.stat().st_size, "sha256": _sha256(path)} for path in input_paths]).to_csv(INPUT_MANIFEST_PATH, index=False)
    outputs = [
        SUMMARY_PATH, COMPARISON_PATH, CURVES_PATH, TRADES_PATH, ENTRY_CANDIDATES_PATH, ENTRY_RISK_PATH,
        TRADE_EVENTS_PATH, STOP_RETRY_EVENTS_PATH, STOP_RETRY_AUDIT_PATH, AI_MONTH_AUDIT_PATH,
        CONFIG_AUDIT_PATH, FEATURE_AUDIT_PATH, CHART_PATH, DECISION_PATH, REPORT_PATH, INPUT_MANIFEST_PATH,
    ]
    pd.DataFrame([{"path": str(path), "bytes": path.stat().st_size, "sha256": _sha256(path)} for path in outputs]).to_csv(MANIFEST_PATH, index=False)
    print(json.dumps(s003._json_safe(decision), ensure_ascii=False, indent=2), flush=True)
    print(comparison.to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
