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


STAGE = "Stage006"
MODEL_TAG = "stage006_drawdown_deepening_quality_transfer_v1"
PROFILE_NAME = "stage006_drawdown_deepening_quality_transfer"
OUTPUT_PREFIX = "tight_stop_quality_stage006"
VARIANT = "C_stage006"
STARTS = s003.STARTS
END = s003.END
EXPECTED_CAPITAL = s003.EXPECTED_CAPITAL

OUT = LINE_DIR / "outputs" / "stage006_drawdown_deepening_quality_transfer"
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

STAGE006_AUDIT_FIELDS = (
    "stage006_enabled",
    "stage006_prior_drawdown_pct",
    "stage006_current_drawdown_pct",
    "stage006_drawdown_delta_pct",
    "stage006_gate_active",
    "stage006_gate_reason",
    "stage006_budget_weight",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def drawdown_deepening_gate(*, enabled: bool, entry_context: str, prior: float, current: float) -> tuple[bool, str]:
    if not enabled:
        return False, "disabled"
    if entry_context != "flat_entry":
        return False, "non_flat_entry"
    if float(current) <= float(prior) + 1e-12:
        return False, "drawdown_not_deepening"
    return True, "drawdown_deepening_quality_transfer"


def _payload(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {key: snapshot.get(key) for key in STAGE006_AUDIT_FIELDS}


class QmtRollPortfolioStrategyStage006DrawdownDeepening(s003.QmtRollPortfolioStrategyStage003RiskTransfer):
    enable_stage006_drawdown_deepening: bool = False
    parameters = s003.QmtRollPortfolioStrategyStage003RiskTransfer.parameters + [
        "enable_stage006_drawdown_deepening",
    ]

    def __init__(self, strategy_engine: Any, strategy_name: str, vt_symbols: list[str], setting: dict[str, Any]) -> None:
        self.stage006_prior_drawdown_pct = 0.0
        self.stage006_current_drawdown_pct = 0.0
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)

    def _refresh_risk_state(self, bars: dict[str, Any]) -> None:
        prior = max(0.0, float(getattr(self, "stage000_account_drawdown_pct", 0.0) or 0.0))
        super()._refresh_risk_state(bars)
        self.stage006_prior_drawdown_pct = prior
        self.stage006_current_drawdown_pct = max(
            0.0,
            float(getattr(self, "stage000_account_drawdown_pct", 0.0) or 0.0),
        )

    def _calculate_entry_sizing(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        positional_context = args[6] if len(args) > 6 else None
        entry_context = str(kwargs.get("entry_context", positional_context or "flat_entry"))
        prior = float(self.stage006_prior_drawdown_pct)
        current = float(self.stage006_current_drawdown_pct)
        gate_active, gate_reason = drawdown_deepening_gate(
            enabled=bool(self.enable_stage006_drawdown_deepening),
            entry_context=entry_context,
            prior=prior,
            current=current,
        )
        original_enabled = bool(self.enable_stage003_risk_transfer)
        self.enable_stage003_risk_transfer = bool(original_enabled and gate_active)
        try:
            result = super()._calculate_entry_sizing(*args, **kwargs)
        finally:
            self.enable_stage003_risk_transfer = original_enabled
        result.update(
            {
                "stage006_enabled": int(bool(self.enable_stage006_drawdown_deepening)),
                "stage006_prior_drawdown_pct": prior,
                "stage006_current_drawdown_pct": current,
                "stage006_drawdown_delta_pct": current - prior,
                "stage006_gate_active": int(gate_active),
                "stage006_gate_reason": gate_reason,
                "stage006_budget_weight": float(result.get("stage003_budget_weight", 1.0) or 1.0),
            }
        )
        return result

    def _record_entry_candidate_snapshot(self, *args: Any, **kwargs: Any) -> None:
        sizing_snapshot = kwargs.get("sizing_snapshot")
        super()._record_entry_candidate_snapshot(*args, **kwargs)
        if isinstance(sizing_snapshot, dict) and self.entry_candidate_snapshots:
            self.entry_candidate_snapshots[-1].update(_payload(sizing_snapshot))

    def _record_entry_risk_diagnostic(self, *args: Any, **kwargs: Any) -> None:
        sizing_snapshot = kwargs.get("sizing_snapshot")
        super()._record_entry_risk_diagnostic(*args, **kwargs)
        if isinstance(sizing_snapshot, dict) and self.entry_risk_diagnostics:
            self.entry_risk_diagnostics[-1].update(_payload(sizing_snapshot))


def _candidate_profile(metadata: dict[str, Any]) -> dict[str, Any]:
    base = s003._candidate_profile(metadata)
    spec = base["spec"]
    result = dict(base)
    result["profile"] = PROFILE_NAME
    result["strategy_cls"] = QmtRollPortfolioStrategyStage006DrawdownDeepening
    result["spec"] = replace(
        spec,
        overrides={**spec.overrides, "enable_stage006_drawdown_deepening": True},
        profile=PROFILE_NAME,
    )
    return result


def config_audit(metadata: dict[str, Any]) -> pd.DataFrame:
    base = s003._official_profile(metadata)
    candidate = _candidate_profile(metadata)
    a_overrides = dict(base["spec"].overrides)
    c_overrides = dict(candidate["spec"].overrides)
    allowed = {
        "enable_stage003_risk_transfer", "stage003_stop_atr_max", "stage003_body_min_exclusive",
        "stage003_body_max_inclusive", "stage003_quality_weight", "stage003_other_weight",
        "enable_stage006_drawdown_deepening",
    }
    rows = []
    for key in sorted(set(a_overrides) | set(c_overrides)):
        a = a_overrides.get(key, "<missing>")
        c = c_overrides.get(key, "<missing>")
        changed = a != c
        rows.append({"key": key, "A": a, "C": c, "changed": int(changed), "allowed": int(key in allowed)})
        if changed and key not in allowed:
            raise RuntimeError(f"unexpected Stage006 A/C override difference: {key}")
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
    required = set(s003.STAGE003_AUDIT_FIELDS) | set(STAGE006_AUDIT_FIELDS)
    missing = sorted(required - set(candidates.columns))
    if candidates.empty or missing:
        raise RuntimeError(f"Stage006 evidence missing: rows={len(candidates)}, columns={missing}")
    if not pd.to_numeric(candidates["stage006_enabled"], errors="coerce").eq(1).all():
        raise RuntimeError("Stage006 contains disabled rows")
    candidate_date = pd.to_datetime(candidates["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    feature_date = pd.to_datetime(candidates["stage003_feature_date"], errors="coerce", utc=True).dt.tz_convert(None).dt.normalize()
    if candidate_date.isna().any() or feature_date.isna().any() or not candidate_date.eq(feature_date).all():
        raise RuntimeError("Stage006 feature date is not signal date/T-1")
    prior = pd.to_numeric(candidates["stage006_prior_drawdown_pct"], errors="coerce")
    current = pd.to_numeric(candidates["stage006_current_drawdown_pct"], errors="coerce")
    delta = pd.to_numeric(candidates["stage006_drawdown_delta_pct"], errors="coerce")
    active = pd.to_numeric(candidates["stage006_gate_active"], errors="coerce").fillna(-1).astype(int)
    expected_active = current.gt(prior + 1e-12).astype(int)
    if prior.isna().any() or current.isna().any() or delta.isna().any():
        raise RuntimeError("Stage006 drawdown state contains NaN")
    if not np.allclose(delta, current - prior, rtol=0.0, atol=1e-12) or not active.eq(expected_active).all():
        raise RuntimeError("Stage006 gate does not match causal daily drawdown delta")
    weight = pd.to_numeric(candidates["stage006_budget_weight"], errors="coerce")
    if not np.allclose(weight[active.eq(0)], 1.0, rtol=0.0, atol=1e-12):
        raise RuntimeError("Stage006 changed risk when drawdown was not deepening")
    active_reason = candidates.loc[active.eq(1), "stage003_reason"].astype(str)
    if not set(active_reason.unique()).issubset({"quality_risk_increase", "other_risk_decrease", "recovery_sleeve_exempt", "feature_unavailable_fail_unchanged"}):
        raise RuntimeError("Stage006 active branch has unexpected Stage003 reason")
    before = pd.to_numeric(candidates["stage003_risk_amount_before"], errors="coerce")
    after = pd.to_numeric(candidates["stage003_risk_amount_after"], errors="coerce")
    comparable = before.notna() & after.notna() & weight.notna()
    if not comparable.any() or not np.allclose(after[comparable], before[comparable] * weight[comparable], rtol=0.0, atol=1e-8):
        raise RuntimeError("Stage006 risk amount does not reconcile")
    coverage = float(pd.to_numeric(candidates["stage003_feature_available"], errors="coerce").fillna(0).mean())
    if coverage < 0.99 or int(active.sum()) <= 0 or int(active.eq(0).sum()) <= 0:
        raise RuntimeError("Stage006 did not exercise both branches with sufficient coverage")
    return {
        "candidate_count": int(len(candidates)), "feature_coverage_ratio": coverage,
        "deepening_count": int(active.sum()), "not_deepening_count": int(active.eq(0).sum()),
        "deepening_quality_count": int(active_reason.eq("quality_risk_increase").sum()),
        "deepening_other_count": int(active_reason.eq("other_risk_decrease").sum()),
        "feature_date_mismatch_count": 0,
    }


def _feature_audit(candidates: pd.DataFrame) -> pd.DataFrame:
    return (
        candidates.groupby(["requested_start_month", "stage006_gate_reason", "stage003_reason"], dropna=False)
        .agg(
            candidate_count=("candidate_index", "size"),
            opened_count=("is_opened", lambda values: int(pd.to_numeric(values, errors="coerce").fillna(0).sum())),
            average_prior_drawdown=("stage006_prior_drawdown_pct", "mean"),
            average_current_drawdown=("stage006_current_drawdown_pct", "mean"),
            average_budget_weight=("stage006_budget_weight", "mean"),
        )
        .reset_index()
        .sort_values(["requested_start_month", "stage006_gate_reason", "stage003_reason"])
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
            ("Stage006 A/C absolute equity", "Normalized NAV by start", "Drawdown"),
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
        print(f"[stage006] {index}/{len(STARTS)} A start={start.date()}", flush=True)
        a_curve, a_frames = s003._run_official_repaired(metadata, start)
        summary_rows.append(s003.summarize_curve(a_curve, start, "A_official"))
        curve_frames.append(s003._tag_curve(a_curve, start, "A_official"))
        append_frames(a_frames, start, "A_official")
        print(f"[stage006] {index}/{len(STARTS)} C start={start.date()}", flush=True)
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
        raise RuntimeError("Stage006 AI month audit failed")
    if any(s003.is_ai_derived_field(column) for column in STAGE006_AUDIT_FIELDS):
        raise RuntimeError("Stage006 introduced an AI-derived feature")
    start_2022 = comparison[comparison["requested_start_month"].eq("2022-01")]
    gate = bool(
        len(comparison) == len(STARTS) and comparison["positive_return_pass"].eq(1).all()
        and comparison["retention_70_pass"].eq(1).all() and comparison["dd_not_worse_1pp_pass"].eq(1).all()
        and int(comparison["dd_improve_3pp_pass"].sum()) >= 3 and not start_2022.empty
        and int(start_2022["dd_improve_3pp_pass"].iloc[0]) == 1
    )
    decision = {
        "stage": STAGE, "model_tag": MODEL_TAG, "line_id": LINE_ID,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "official_live_version": s003.OFFICIAL_LIVE_VERSION, "minute_evidence": minute_audit,
        "candidate_new_ai_feature_count": 0, "feature_evidence_summary": feature_summary,
        "strict_account_equity_reconciliation": account_equity_summary,
        "strict_root_open_reconciliation_pass": True,
        "stop_retry_reconciliation_pass": True, "four_anchor_gate_pass": gate,
        "decision": "pending_independent_review" if gate else "failed_four_anchor_gate_pending_independent_review",
        "extend_half_year_allowed": False,
        "overfit_before": "高；状态逻辑由当前样本消融形成，但无数值阈值。",
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
            "# Stage006 回撤加深日质量风险转移 A/B", "", f"- 生成时间：`{decision['generated_at']}`",
            f"- 决策：`{decision['decision']}`", f"- 四锚点硬门：`{gate}`",
            "- 新增 AI 特征：`0`；仅在当日回撤较前一交易日加深时启用质量风险转移。",
            "", "## A/C 摘要", "", s003._md_table(summary), "", "## 硬门", "", s003._md_table(comparison),
            "", "## 状态与特征审计", "", s003._md_table(feature_audit),
            "", "## 成交与重试守恒", "", s003._md_table(retry_audit),
        ]) + "\n",
        encoding="utf-8",
    )
    input_paths = [
        Path(__file__), Path(s003.__file__), ROOT / ".vntrader" / "database.db",
        Path(s003.OFFICIAL_LIVE_AI_ELIGIBILITY_PATH), s003.REPAIRED_MINUTE_PATCH_PATH,
        s003.REPAIRED_MINUTE_AUDIT_PATH, Path(s003.s000.DECISION_PATH),
        PORTFOLIO_DIR / "qmt_roll_official_live_config.py", Path(s003.s847.__file__),
    ]
    missing = [str(path) for path in input_paths if not path.exists()]
    if missing:
        raise RuntimeError(f"Stage006 missing input files: {missing}")
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
