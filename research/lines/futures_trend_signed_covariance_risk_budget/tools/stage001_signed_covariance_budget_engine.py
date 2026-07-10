#!/usr/bin/env python3
"""Stage001: signed-covariance marginal portfolio risk budget A/C engine test.

The candidate keeps the current official AI pool and C9 execution logic.  It
adds one research-only sizing layer after the existing same-direction
correlation gate.  The new layer estimates a 63-day Ledoit-Wolf covariance
matrix over direction-adjusted returns for the candidate and active holdings,
then removes only the correlation-induced risk inflation.  It never increases
position size and preserves at least one contract for an already-openable
candidate.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf


ROOT = Path(__file__).resolve().parents[4]
PORTFOLIO_DIR = ROOT / "examples" / "portfolio_backtesting"
SOURCE_TOOLS_DIR = ROOT / "research" / "lines" / "futures_trend_full_market_ai_filter_002risk" / "tools"
for item in (PORTFOLIO_DIR, SOURCE_TOOLS_DIR):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import stage006_current_ai_paired_bottom_veto_engine as s006  # noqa: E402
from qmt_roll_official_live_config import OFFICIAL_LIVE_AI_ELIGIBILITY_PATH  # noqa: E402


LINE_ID = "futures_trend_signed_covariance_risk_budget"
STAGE_ID = "stage001_signed_covariance_budget_engine"
STAGE_LABEL = "Stage001"
MODEL_TAG = f"{STAGE_ID}_v1"
OUTPUT_PREFIX = f"signed_cov_budget_{STAGE_ID}"

REQUESTED_START = pd.Timestamp("2020-01-01")
REQUESTED_END = pd.Timestamp("2026-06-30")
START_MONTH = "2020-01"
CAPITAL = float(s006.base.CAPITAL)

LOOKBACK_DAYS = 63
MIN_OBSERVATIONS = 32
MIN_PRESERVED_VOLUME = 1

A_VERSION = "current_official_ai_c9_control"
C_VERSION = "current_official_ai_c9_signed_covariance_budget"
A_STRATEGY = "stage001_cov_budget_control_official_ai"
C_STRATEGY = "stage001_cov_budget_candidate_official_ai"
A_SCORE_TYPE = "current_official_ai_control"
C_SCORE_TYPE = "current_official_ai_signed_covariance_budget"

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / STAGE_ID
STAGES_DIR = LINE_DIR / "stages"
STAGE_RECORD_PATH = STAGES_DIR / "20260710_1718_stage001_signed_covariance_budget_engine.md"

A_ELIGIBILITY_PATH = OUT / f"{OUTPUT_PREFIX}_a_eligibility_{MODEL_TAG}.csv"
C_ELIGIBILITY_PATH = OUT / f"{OUTPUT_PREFIX}_c_eligibility_{MODEL_TAG}.csv"
A_DAILY_PATH = OUT / f"{OUTPUT_PREFIX}_a_daily_{MODEL_TAG}.csv.gz"
C_DAILY_PATH = OUT / f"{OUTPUT_PREFIX}_c_daily_{MODEL_TAG}.csv.gz"
A_ENTRY_PATH = OUT / f"{OUTPUT_PREFIX}_a_entry_candidates_{MODEL_TAG}.csv.gz"
C_ENTRY_PATH = OUT / f"{OUTPUT_PREFIX}_c_entry_candidates_{MODEL_TAG}.csv.gz"
A_RISK_PATH = OUT / f"{OUTPUT_PREFIX}_a_entry_risk_{MODEL_TAG}.csv.gz"
C_RISK_PATH = OUT / f"{OUTPUT_PREFIX}_c_entry_risk_{MODEL_TAG}.csv.gz"
A_TRADES_PATH = OUT / f"{OUTPUT_PREFIX}_a_trades_{MODEL_TAG}.csv.gz"
C_TRADES_PATH = OUT / f"{OUTPUT_PREFIX}_c_trades_{MODEL_TAG}.csv.gz"
A_CLOSED_PATH = OUT / f"{OUTPUT_PREFIX}_a_closed_lots_{MODEL_TAG}.csv.gz"
C_CLOSED_PATH = OUT / f"{OUTPUT_PREFIX}_c_closed_lots_{MODEL_TAG}.csv.gz"
CURVES_PATH = OUT / f"{OUTPUT_PREFIX}_ac_curves_{MODEL_TAG}.csv.gz"
SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_ac_summary_{MODEL_TAG}.csv"
COVARIANCE_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_covariance_audit_{MODEL_TAG}.csv"
AI_PARITY_PATH = OUT / f"{OUTPUT_PREFIX}_ai_parity_{MODEL_TAG}.csv"
AI_USAGE_PATH = OUT / f"{OUTPUT_PREFIX}_ai_usage_{MODEL_TAG}.csv"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUT / f"{OUTPUT_PREFIX}_equity_drawdown_{MODEL_TAG}.png"

CUSTOM_FIELDS = (
    "signed_covariance_budget_enabled",
    "signed_covariance_budget_available",
    "signed_covariance_lookback_days",
    "signed_covariance_observations",
    "signed_covariance_active_count",
    "signed_covariance_asset_count",
    "signed_covariance_active_symbols",
    "signed_covariance_diagonal_risk",
    "signed_covariance_portfolio_risk",
    "signed_covariance_inflation_ratio",
    "signed_covariance_budget_weight",
    "signed_covariance_selected_volume_before",
    "signed_covariance_selected_volume_after",
    "signed_covariance_volume_reduced",
)


class QmtRollPortfolioStrategySignedCovarianceBudget(
    s006.base.s847.QmtRollPortfolioStrategyStage847C9StopRetry
):
    enable_signed_covariance_budget: bool = True
    signed_covariance_lookback_days: int = LOOKBACK_DAYS
    signed_covariance_min_observations: int = MIN_OBSERVATIONS

    parameters = s006.base.s847.QmtRollPortfolioStrategyStage847C9StopRetry.parameters + [
        "enable_signed_covariance_budget",
        "signed_covariance_lookback_days",
        "signed_covariance_min_observations",
    ]

    @staticmethod
    def _direction_sign_text(direction: str) -> float:
        return 1.0 if str(direction).lower() == "long" else -1.0

    def _signed_covariance_snapshot(
        self,
        *,
        contract_vt_symbol: str,
        direction: str,
        history: pd.DataFrame,
        entry_context: str,
        selected_volume: int,
    ) -> dict[str, Any]:
        enabled = int(bool(self.enable_signed_covariance_budget) and entry_context == "flat_entry")
        result: dict[str, Any] = {
            "signed_covariance_budget_enabled": enabled,
            "signed_covariance_budget_available": 0,
            "signed_covariance_lookback_days": int(self.signed_covariance_lookback_days),
            "signed_covariance_observations": 0,
            "signed_covariance_active_count": 0,
            "signed_covariance_asset_count": 0,
            "signed_covariance_active_symbols": "",
            "signed_covariance_diagonal_risk": 0.0,
            "signed_covariance_portfolio_risk": 0.0,
            "signed_covariance_inflation_ratio": 1.0,
            "signed_covariance_budget_weight": 1.0,
            "signed_covariance_selected_volume_before": max(0, int(selected_volume)),
            "signed_covariance_selected_volume_after": max(0, int(selected_volume)),
            "signed_covariance_volume_reduced": 0,
        }
        if not enabled or selected_volume <= 0:
            return result

        lookback = max(20, int(self.signed_covariance_lookback_days or LOOKBACK_DAYS))
        candidate_returns = self._history_return_vector(history, lookback)
        if len(candidate_returns) < int(self.signed_covariance_min_observations):
            return result

        series: list[np.ndarray] = [candidate_returns * self._direction_sign_text(direction)]
        symbols: list[str] = [str(contract_vt_symbol)]
        positions: list[int] = [max(0, int(selected_volume))]
        sizes: list[float] = [float(self.get_size(contract_vt_symbol))]
        prices: list[float] = [float(pd.to_numeric(history["close"], errors="coerce").dropna().iloc[-1])]
        active_symbols: list[str] = []

        for state in self.states.values():
            active_contract = str(state.contract_vt_symbol or "")
            if not active_contract or active_contract == str(contract_vt_symbol):
                continue
            active_pos = abs(int(self.get_pos(active_contract)))
            if active_pos <= 0:
                continue
            active_am = self.ams.get(active_contract)
            if active_am is None or not active_am.inited:
                continue
            active_history = self._build_history_df(active_am)
            active_returns = self._history_return_vector(active_history, lookback)
            if len(active_returns) < int(self.signed_covariance_min_observations):
                continue
            active_close = pd.to_numeric(active_history["close"], errors="coerce").dropna()
            if active_close.empty:
                continue
            series.append(active_returns * self._direction_sign_text(str(state.direction)))
            symbols.append(active_contract)
            positions.append(active_pos)
            sizes.append(float(self.get_size(active_contract)))
            prices.append(float(active_close.iloc[-1]))
            active_symbols.append(active_contract)

        result["signed_covariance_active_count"] = len(active_symbols)
        result["signed_covariance_active_symbols"] = "/".join(active_symbols)
        result["signed_covariance_asset_count"] = len(series)
        if len(series) <= 1:
            return result

        observations = min(len(item) for item in series)
        observations = min(observations, lookback)
        if observations < int(self.signed_covariance_min_observations):
            return result
        matrix = np.column_stack([item[-observations:] for item in series]).astype("float64")
        matrix = matrix[np.isfinite(matrix).all(axis=1)]
        if len(matrix) < int(self.signed_covariance_min_observations):
            return result

        covariance = LedoitWolf().fit(matrix).covariance_
        vol = np.sqrt(np.clip(np.diag(covariance), 0.0, None))
        if len(vol) != len(series) or np.any(~np.isfinite(vol)) or np.any(vol <= 1e-12):
            return result
        correlation = covariance / np.outer(vol, vol)
        correlation = np.clip(np.nan_to_num(correlation, nan=0.0, posinf=1.0, neginf=-1.0), -1.0, 1.0)
        np.fill_diagonal(correlation, 1.0)

        exposure = np.asarray(positions, dtype="float64") * np.asarray(sizes) * np.asarray(prices) * vol
        diagonal_variance = float(np.dot(exposure, exposure))
        portfolio_variance = float(exposure @ correlation @ exposure)
        if diagonal_variance <= 1e-12 or portfolio_variance < 0.0 or not np.isfinite(portfolio_variance):
            return result

        diagonal_risk = math.sqrt(diagonal_variance)
        portfolio_risk = math.sqrt(max(0.0, portfolio_variance))
        inflation = portfolio_risk / max(diagonal_risk, 1e-12)
        weight = min(1.0, 1.0 / max(inflation, 1e-12))
        selected_before = max(0, int(selected_volume))
        selected_after = int(math.floor(selected_before * weight + 0.5))
        if selected_before > 0:
            selected_after = max(MIN_PRESERVED_VOLUME, selected_after)
        selected_after = min(selected_before, selected_after)

        result.update(
            {
                "signed_covariance_budget_available": 1,
                "signed_covariance_observations": int(len(matrix)),
                "signed_covariance_diagonal_risk": diagonal_risk,
                "signed_covariance_portfolio_risk": portfolio_risk,
                "signed_covariance_inflation_ratio": inflation,
                "signed_covariance_budget_weight": weight,
                "signed_covariance_selected_volume_before": selected_before,
                "signed_covariance_selected_volume_after": selected_after,
                "signed_covariance_volume_reduced": selected_before - selected_after,
            }
        )
        return result

    def _apply_same_direction_correlation_gate_to_sizing(
        self,
        sizing: dict[str, Any],
        *,
        contract_vt_symbol: str,
        direction: str,
        history: pd.DataFrame,
        entry_context: str,
        correlation_snapshot: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        adjusted = super()._apply_same_direction_correlation_gate_to_sizing(
            sizing,
            contract_vt_symbol=contract_vt_symbol,
            direction=direction,
            history=history,
            entry_context=entry_context,
            correlation_snapshot=correlation_snapshot,
        )
        snapshot = self._signed_covariance_snapshot(
            contract_vt_symbol=contract_vt_symbol,
            direction=direction,
            history=history,
            entry_context=entry_context,
            selected_volume=max(0, int(adjusted.get("selected_volume") or 0)),
        )
        adjusted.update(snapshot)
        adjusted["selected_volume"] = int(snapshot["signed_covariance_selected_volume_after"])
        return adjusted

    def _record_entry_candidate_snapshot(self, **kwargs: Any) -> None:
        sizing_snapshot = dict(kwargs.get("sizing_snapshot") or {})
        super()._record_entry_candidate_snapshot(**kwargs)
        if not self.entry_candidate_snapshots:
            return
        self.entry_candidate_snapshots[-1].update(
            {field: sizing_snapshot.get(field, "" if field.endswith("symbols") else 0) for field in CUSTOM_FIELDS}
        )


def _sha16(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def _normalized_ai_hash(frame: pd.DataFrame) -> str:
    columns = ["eval_date", "product_vt_symbol", "score", "score_rank", "top_n"]
    data = frame[columns].copy()
    data["eval_date"] = pd.to_datetime(data["eval_date"], errors="coerce").dt.date.astype(str)
    data = data.sort_values(["eval_date", "score_rank", "product_vt_symbol"]).reset_index(drop=True)
    payload = data.to_csv(index=False, lineterminator="\n").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def _metadata() -> dict[str, Any]:
    return s006._metadata()


def _profile(
    metadata: dict[str, Any],
    *,
    version: str,
    strategy_name: str,
    eligibility_path: Path,
    label: str,
    candidate: bool,
) -> dict[str, Any]:
    profile = s006._profile(
        metadata,
        version=version,
        strategy_name=strategy_name,
        eligibility_path=eligibility_path,
        label=label,
    )
    if not candidate:
        return profile
    spec = profile["spec"]
    overrides = {
        **spec.overrides,
        "enable_signed_covariance_budget": True,
        "signed_covariance_lookback_days": LOOKBACK_DAYS,
        "signed_covariance_min_observations": MIN_OBSERVATIONS,
    }
    profile = dict(profile)
    profile["strategy_cls"] = QmtRollPortfolioStrategySignedCovarianceBudget
    profile["spec"] = replace(spec, overrides=overrides, profile=version)
    profile["profile"] = version
    return profile


def _run(metadata: dict[str, Any], profile: dict[str, Any], version: str) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    daily, frames, _ = s006._run_profile(metadata, profile, version)
    daily = daily.copy()
    daily["stage"] = STAGE_LABEL
    daily["model_tag"] = MODEL_TAG
    daily["line_id"] = LINE_ID
    daily["requested_start_month"] = START_MONTH
    for frame in frames.values():
        if frame.empty:
            continue
        frame["stage"] = STAGE_LABEL
        frame["model_tag"] = MODEL_TAG
        frame["line_id"] = LINE_ID
        frame["start_month"] = START_MONTH
    return daily, frames


def _closed_lots(frames: dict[str, pd.DataFrame], metadata: dict[str, Any]) -> pd.DataFrame:
    trades = frames.get("trades", pd.DataFrame()).copy()
    entry_risk = frames.get("entry_risk", pd.DataFrame()).copy()
    candidates = frames.get("entry_candidates", pd.DataFrame()).copy()
    if trades.empty:
        return pd.DataFrame()
    return s006.base.s847.s719._build_closed_lots(trades, entry_risk, candidates, metadata)


def _save_frames(frames: dict[str, pd.DataFrame], paths: dict[str, Path]) -> None:
    for name, path in paths.items():
        data = frames.get(name, pd.DataFrame()).copy()
        if not data.empty:
            data.to_csv(path, index=False, encoding="utf-8-sig")


def _summary_row(curve: pd.DataFrame, closed: pd.DataFrame) -> dict[str, Any]:
    row = s006._summarize_curve(curve)
    row["stage"] = STAGE_LABEL
    row["model_tag"] = MODEL_TAG
    row["line_id"] = LINE_ID
    row["requested_start_month"] = START_MONTH
    realized = pd.to_numeric(closed.get("realized_pnl", pd.Series(dtype=float)), errors="coerce").dropna()
    row["closed_lot_count"] = int(len(realized))
    row["closed_lot_win_rate_pct"] = float((realized > 0.0).mean() * 100.0) if len(realized) else 0.0
    return row


def _covariance_audit(entries: pd.DataFrame) -> pd.DataFrame:
    if entries.empty:
        return pd.DataFrame([{"sample": "all", "rows": 0}])
    data = entries.copy()
    for column in CUSTOM_FIELDS:
        if column == "signed_covariance_active_symbols":
            continue
        data[column] = pd.to_numeric(data.get(column, 0), errors="coerce").fillna(0.0)
    before = data["signed_covariance_selected_volume_before"]
    after = data["signed_covariance_selected_volume_after"]
    data["selected_volume"] = pd.to_numeric(data.get("selected_volume", 0), errors="coerce").fillna(0.0)
    opened = pd.to_numeric(data.get("is_opened", 0), errors="coerce").fillna(0).astype(int).eq(1)
    available = data["signed_covariance_budget_available"].eq(1)
    reduced = data["signed_covariance_volume_reduced"].gt(0)
    rows: list[dict[str, Any]] = []
    for sample, mask in (
        ("all_candidates", pd.Series(True, index=data.index)),
        ("opened", opened),
        ("available", available),
        ("reduced", reduced),
    ):
        part = data[mask]
        rows.append(
            {
                "sample": sample,
                "rows": int(len(part)),
                "available_rows": int(part["signed_covariance_budget_available"].sum()),
                "reduced_rows": int(part["signed_covariance_volume_reduced"].gt(0).sum()),
                "volume_before_sum": float(part["signed_covariance_selected_volume_before"].sum()),
                "volume_after_sum": float(part["signed_covariance_selected_volume_after"].sum()),
                "volume_reduced_sum": float(part["signed_covariance_volume_reduced"].sum()),
                "weight_min": float(part["signed_covariance_budget_weight"].min()) if len(part) else 1.0,
                "weight_median": float(part["signed_covariance_budget_weight"].median()) if len(part) else 1.0,
                "inflation_max": float(part["signed_covariance_inflation_ratio"].max()) if len(part) else 1.0,
                "observation_min": int(part["signed_covariance_observations"].min()) if len(part) else 0,
                "observation_max": int(part["signed_covariance_observations"].max()) if len(part) else 0,
                "configured_lookback_match_count": int(
                    part["signed_covariance_observations"].eq(LOOKBACK_DAYS).sum()
                ),
                "after_gt_before_count": int(
                    (part["signed_covariance_selected_volume_after"] > part["signed_covariance_selected_volume_before"]).sum()
                ),
                "positive_before_zero_after_count": int(
                    (
                        part["signed_covariance_selected_volume_before"].gt(0)
                        & part["signed_covariance_selected_volume_after"].eq(0)
                    ).sum()
                ),
                "final_selected_gt_cov_before_count": int(
                    (part["selected_volume"] > part["signed_covariance_selected_volume_before"]).sum()
                ),
            }
        )
    return pd.DataFrame(rows)


def _decision(summary: pd.DataFrame, covariance_audit: pd.DataFrame, ai_parity: pd.DataFrame) -> dict[str, Any]:
    a = summary[summary["version"].eq(A_VERSION)].iloc[0].to_dict()
    c = summary[summary["version"].eq(C_VERSION)].iloc[0].to_dict()
    retention = float(c["total_return_pct"] / a["total_return_pct"]) if float(a["total_return_pct"]) else 0.0
    dd_delta = float(c["max_drawdown_pct"] - a["max_drawdown_pct"])
    sharpe_delta = float(c["sharpe"] - a["sharpe"])
    broker_delta = float(c["max_broker10_margin_to_equity_pct"] - a["max_broker10_margin_to_equity_pct"])
    all_row = covariance_audit[covariance_audit["sample"].eq("all_candidates")].iloc[0]
    available_row = covariance_audit[covariance_audit["sample"].eq("available")].iloc[0]
    local_transform_ok = (
        int(all_row["after_gt_before_count"]) == 0
        and int(all_row["positive_before_zero_after_count"]) == 0
        and bool(ai_parity["normalized_equal"].all())
    )
    configured_window_fulfilled = (
        int(available_row["rows"]) > 0
        and int(available_row["observation_min"]) >= LOOKBACK_DAYS
        and int(available_row["observation_max"]) >= LOOKBACK_DAYS
    )
    # Stage001 applies total portfolio inflation to the candidate.  That is not
    # the marginal contribution rule described by the research hypothesis.
    implemented_formula_is_marginal = False
    semantics_ok = local_transform_ok and configured_window_fulfilled and implemented_formula_is_marginal
    performance_ok = (
        float(c["total_return_pct"]) > 0.0
        and retention >= 0.80
        and broker_delta <= 1e-9
        and (dd_delta >= 3.0 or (sharpe_delta >= 0.05 and dd_delta >= 0.0))
    )
    decision = (
        "stage001_continue_to_halfyear_if_independent_review_passes"
        if semantics_ok and performance_ok
        else "stage001_stop_no_parameter_rescue"
    )
    return {
        "stage": STAGE_LABEL,
        "stage_id": STAGE_ID,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S CST"),
        "requested_start": REQUESTED_START.date().isoformat(),
        "requested_end": REQUESTED_END.date().isoformat(),
        "lookback_days": LOOKBACK_DAYS,
        "min_observations": MIN_OBSERVATIONS,
        "a_control": a,
        "c_candidate": c,
        "return_retention_ratio": retention,
        "return_delta_pct": float(c["total_return_pct"] - a["total_return_pct"]),
        "drawdown_delta_pct": dd_delta,
        "sharpe_delta": sharpe_delta,
        "broker10_peak_delta_pct": broker_delta,
        "local_transform_ok": bool(local_transform_ok),
        "configured_window_fulfilled": bool(configured_window_fulfilled),
        "actual_covariance_observation_min": int(available_row["observation_min"]),
        "actual_covariance_observation_max": int(available_row["observation_max"]),
        "implemented_formula_is_marginal": implemented_formula_is_marginal,
        "semantics_ok": bool(semantics_ok),
        "performance_ok": bool(performance_ok),
        "decision": decision,
        "overfit_before": "low_to_medium: one parameter-free structural scaler, with a fixed 63-day estimation window and no weak-window tuning.",
        "overfit_after": "current single test did not tune after results; any window, floor, threshold, or integer rescue would now be high-overfit.",
        "continue_value_before": "yes: it preserves AI opportunities and tests portfolio covariance risk rather than another product veto.",
        "continue_value_after": "no for this implementation: close without half-year expansion; a date-aligned marginal-contribution design would be a separate hypothesis.",
    }


def _plot(curves: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(13, 8), sharex=True)
    labels = {A_VERSION: "A current C9", C_VERSION: "C signed covariance budget"}
    colors = {A_VERSION: "#111827", C_VERSION: "#0f766e"}
    for version, group in curves.groupby("version", sort=False):
        data = group.sort_values("date")
        x = pd.to_datetime(data["date"])
        equity = pd.to_numeric(data["account_equity_for_metrics"], errors="coerce").ffill()
        axes[0].plot(x, equity, label=labels.get(version, version), color=colors.get(version), linewidth=1.15)
        axes[1].plot(x, s006.base._drawdown_pct(equity), label=labels.get(version, version), color=colors.get(version), linewidth=1.0)
    axes[0].axhline(CAPITAL, color="#64748b", linestyle="--", linewidth=0.9)
    axes[0].set_title("Stage001 signed covariance budget: absolute equity")
    axes[0].set_ylabel("account equity")
    axes[0].grid(alpha=0.25)
    axes[0].legend(loc="best")
    axes[1].set_title("Stage001 signed covariance budget: drawdown")
    axes[1].set_ylabel("drawdown %")
    axes[1].grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=170)
    plt.close(fig)


def _append_once(path: Path, marker: str, content: str) -> None:
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if marker not in existing:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(content)


def _write_records(
    summary: pd.DataFrame,
    covariance_audit: pd.DataFrame,
    ai_parity: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    a = summary[summary["version"].eq(A_VERSION)].iloc[0]
    c = summary[summary["version"].eq(C_VERSION)].iloc[0]
    summary_view = summary[
        [
            "version",
            "end_equity",
            "total_return_pct",
            "max_drawdown_pct",
            "sharpe",
            "total_slippage",
            "total_trade_count",
            "nonzero_daily_win_rate_pct",
            "closed_lot_count",
            "closed_lot_win_rate_pct",
            "max_broker10_margin_to_equity_pct",
        ]
    ]
    report = f"""# Stage001 方向协方差组合风险预算 A/C 真引擎

- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`
- line_id：`{LINE_ID}`
- 区间：`{REQUESTED_START.date()}` 到 `{REQUESTED_END.date()}`
- A：当前官方 AI + 当前 C9/15w。
- C：A + 配置 63 日、但受正式 AM41 限制实际仅 40 个收益观测的 Ledoit-Wolf 绝对组合风险膨胀缩放。
- 外部判断：风险预算适合处理组合相关暴露，但估计误差是主要风险；因此本阶段只跑一个冻结形状。

## 结果

{s006.base._md_table(summary_view)}

## 协方差语义审计

{s006.base._md_table(covariance_audit)}

## AI 同口径审计

{s006.base._md_table(ai_parity)}

## 决策

- 决策：`{decision['decision']}`
- 收益保留率：`{decision['return_retention_ratio']:.4f}`
- 回撤变化：`{decision['drawdown_delta_pct']:.4f}` 百分点
- Sharpe 变化：`{decision['sharpe_delta']:.4f}`
- broker10 峰值变化：`{decision['broker10_peak_delta_pct']:.4f}` 百分点
- 配置窗口是否兑现：`{decision['configured_window_fulfilled']}`；实际观测 `{decision['actual_covariance_observation_min']} -> {decision['actual_covariance_observation_max']}`。
- 边际风险语义是否兑现：`{decision['implemented_formula_is_marginal']}`；当前实现是总组合 inflation，不是候选边际贡献。
- 独立 review：`P0=0/P1=2/P2=3`；绩效统计闭合，但 63 日窗口与候选边际风险语义未兑现。
- 运行后过拟合判断：当前单次失败实验没有结果后调参；继续救窗口或权重会过拟合。
- 运行后继续价值判断：本实现无继续价值，关闭且不做逐半年。
"""
    REPORT_PATH.write_text(report, encoding="utf-8")

    stage_record = f"""# Stage001 方向协方差组合风险预算 A/C 真引擎

- line_id：`{LINE_ID}`
- 当前模式：`day`
- 记录时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`
- 工作区/分支：当前共享工作区；研究目录隔离
- 阶段性质：最小 A/C 真引擎验证
- 是否重要突破：否；独立 review 后关闭
- 是否触发A/B：是；A=当前 C9，C=A+方向协方差风险预算

## 外部调研与判断

- 参考资料：AQR managed futures、Active Risk Budgeting、pysystemtrade position sizing/portfolio correlation。
- 我的判断：不再修 AI 排名，改为保留机会并治理组合相关风险；当前 C9 已有相关性门控，新增层必须用真实结果证明增量价值。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/{Path(__file__).name}`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无。
- 新增参数：配置 `lookback=63`、`min_observations=32`、Ledoit-Wolf、只降不升、至少保留 1 手；独立审计确认正式 AM41 下实际只有 40 个收益观测。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：`{REQUESTED_START.date()}` 到 `{REQUESTED_END.date()}`。
- 账户规模：`{CAPITAL:,.0f}`。
- 成本口径：沿用当前 C9 真引擎滑点、手续费与 broker10 保证金口径。
- 样本过滤：当前官方 AI 月池；A/C 归一化 eligibility 完全一致。
- 策略/归因口径：只在 flat_entry 正式相关性门控后缩放候选手数；止损重试、退出、加仓、换月不变。

## 结果

- A 期末权益：`{a['end_equity']:,.2f}`；总收益 `{a['total_return_pct']:.4f}%`；最大回撤 `{a['max_drawdown_pct']:.4f}%`；Sharpe `{a['sharpe']:.4f}`；总滑点 `{a['total_slippage']:,.2f}`；总交易次数 `{a['total_trade_count']:,.0f}`；非零日胜率 `{a['nonzero_daily_win_rate_pct']:.4f}%`；逐笔胜率 `{a['closed_lot_win_rate_pct']:.4f}%`。
- C 期末权益：`{c['end_equity']:,.2f}`。
- C 总收益：`{c['total_return_pct']:.4f}%`。
- C 最大回撤：`{c['max_drawdown_pct']:.4f}%`。
- C Sharpe：`{c['sharpe']:.4f}`。
- C 总滑点：`{c['total_slippage']:,.2f}`。
- C 总交易次数：`{c['total_trade_count']:,.0f}`。
- C 非零日胜率：`{c['nonzero_daily_win_rate_pct']:.4f}%`；逐笔胜率 `{c['closed_lot_win_rate_pct']:.4f}%`。
- 其他关键指标：收益保留 `{decision['return_retention_ratio']:.4f}`；回撤变化 `{decision['drawdown_delta_pct']:.4f}`pp；Sharpe 变化 `{decision['sharpe_delta']:.4f}`；broker10 峰值变化 `{decision['broker10_peak_delta_pct']:.4f}`pp。
- 语义审计：局部 transform 只减不增且不归零为 `{decision['local_transform_ok']}`；63 日窗口兑现为 `{decision['configured_window_fulfilled']}`（实际 `{decision['actual_covariance_observation_min']} -> {decision['actual_covariance_observation_max']}`）；候选边际风险语义兑现为 `{decision['implemented_formula_is_marginal']}`。

## 输出文件

- report：`{REPORT_PATH}`
- summary：`{SUMMARY_PATH}`
- daily：`{A_DAILY_PATH}` / `{C_DAILY_PATH}`
- quality：`{COVARIANCE_AUDIT_PATH}` / `{AI_PARITY_PATH}`

## 结论

- 本阶段结论：`{decision['decision']}`。当前落地是 40 观测绝对 inflation 版本，不能表述为真正 63 日边际风险版本。
- 是否进入下一步：否；独立 review 为 `P0=0/P1=2/P2=3`，关闭本线且不做逐半年。
- 下一步：禁止扫描窗口、阈值、weight floor 或整数规则；日期对齐、同日批量感知的候选边际风险贡献若未来研究，必须另开新线并重新预声明。

## 过拟合反思

- 运行前判断：低到中等；单一结构、固定 63 日、无坏窗口或品种补丁，但协方差估计可能噪声化。
- 运行后判断：当前结果本身没有通过调参制造过拟合，但继续救参会转为高风险过拟合。
- 原因：四项绩效闸门失败，且实际观测/边际语义与研究表述不一致；不允许扫窗口、收缩强度、weight floor 或整数规则救参。

## 继续价值反思

- 运行前判断：有价值；它保留 AI 机会，只治理组合层相关风险。
- 运行后判断：本实现无继续价值。
- 原因：收益保留、回撤、Sharpe、broker10 和语义审计均未通过；只保留失败证据。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：待 review 后统一更新。
- 是否追加根目录 `memory.md/back_log.md`：按 A/B skill 追加 `back_log.md`；不更新 `memory.md`。
"""
    STAGE_RECORD_PATH.write_text(stage_record, encoding="utf-8")

    line_marker = "## Stage001 结果"
    line_append = f"""

{line_marker}

- 时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`
- 决策：`{decision['decision']}`
- A：`{a['end_equity']:,.2f}` / `{a['total_return_pct']:.4f}%` / `{a['max_drawdown_pct']:.4f}%` / Sharpe `{a['sharpe']:.4f}`。
- C：`{c['end_equity']:,.2f}` / `{c['total_return_pct']:.4f}%` / `{c['max_drawdown_pct']:.4f}%` / Sharpe `{c['sharpe']:.4f}`。
- 收益保留：`{decision['return_retention_ratio']:.4f}`；回撤变化：`{decision['drawdown_delta_pct']:.4f}`pp；等待独立 review。
"""
    _append_once(LINE_DIR / "LINE.md", line_marker, line_append)

    back_marker = f"`{LINE_ID}` Stage001 完成方向协方差组合风险预算"
    back_append = f"""

{datetime.now().strftime('%Y-%m-%d %H:%M CST')}：{back_marker} A/C 真引擎，决策 `{decision['decision']}`。新增脚本 `research/lines/{LINE_ID}/tools/{Path(__file__).name}`；新增参数 `lookback=63/min_observations=32/Ledoit-Wolf/只降不升/至少1手`，修改参数无，删除参数无。A 期末权益 `{a['end_equity']:,.2f}`、总收益 `{a['total_return_pct']:.4f}%`、最大回撤 `{a['max_drawdown_pct']:.4f}%`、Sharpe `{a['sharpe']:.4f}`、总滑点 `{a['total_slippage']:,.2f}`、总交易次数 `{a['total_trade_count']:,.0f}`、非零日胜率 `{a['nonzero_daily_win_rate_pct']:.4f}%`、逐笔胜率 `{a['closed_lot_win_rate_pct']:.4f}%`；C 期末权益 `{c['end_equity']:,.2f}`、总收益 `{c['total_return_pct']:.4f}%`、最大回撤 `{c['max_drawdown_pct']:.4f}%`、Sharpe `{c['sharpe']:.4f}`、总滑点 `{c['total_slippage']:,.2f}`、总交易次数 `{c['total_trade_count']:,.0f}`、非零日胜率 `{c['nonzero_daily_win_rate_pct']:.4f}%`、逐笔胜率 `{c['closed_lot_win_rate_pct']:.4f}%`。新增结果：收益保留 `{decision['return_retention_ratio']:.4f}`、回撤变化 `{decision['drawdown_delta_pct']:.4f}`pp、Sharpe 变化 `{decision['sharpe_delta']:.4f}`、broker10 峰值变化 `{decision['broker10_peak_delta_pct']:.4f}`pp；修改/删除回测结果无。运行前过拟合判断：低到中等，单一固定结构且不按坏窗口调参；运行后过拟合判断：待独立 agent review。运行前继续价值判断：有；运行后继续价值判断：待独立 review。report `{REPORT_PATH}`，summary `{SUMMARY_PATH}`。
"""
    _append_once(ROOT / "back_log.md", back_marker, back_append)


def build() -> dict[str, pd.DataFrame]:
    OUT.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)

    a_eligibility = s006._official_eligibility_for_strategy(A_STRATEGY, A_SCORE_TYPE)
    c_eligibility = s006._official_eligibility_for_strategy(C_STRATEGY, C_SCORE_TYPE)
    a_eligibility.to_csv(A_ELIGIBILITY_PATH, index=False, encoding="utf-8-sig")
    c_eligibility.to_csv(C_ELIGIBILITY_PATH, index=False, encoding="utf-8-sig")
    ai_parity = pd.DataFrame(
        [
            {
                "official_ai_path": str(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH),
                "official_ai_sha16": _sha16(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH),
                "a_file_sha16": _sha16(A_ELIGIBILITY_PATH),
                "c_file_sha16": _sha16(C_ELIGIBILITY_PATH),
                "a_normalized_sha16": _normalized_ai_hash(a_eligibility),
                "c_normalized_sha16": _normalized_ai_hash(c_eligibility),
                "normalized_equal": int(_normalized_ai_hash(a_eligibility) == _normalized_ai_hash(c_eligibility)),
                "a_rows": int(len(a_eligibility)),
                "c_rows": int(len(c_eligibility)),
            }
        ]
    )

    metadata = _metadata()
    a_profile = _profile(
        metadata,
        version=A_VERSION,
        strategy_name=A_STRATEGY,
        eligibility_path=A_ELIGIBILITY_PATH,
        label="A current official AI C9 control",
        candidate=False,
    )
    c_profile = _profile(
        metadata,
        version=C_VERSION,
        strategy_name=C_STRATEGY,
        eligibility_path=C_ELIGIBILITY_PATH,
        label="C current official AI C9 plus signed covariance budget",
        candidate=True,
    )

    a_daily, a_frames = _run(metadata, a_profile, A_VERSION)
    c_daily, c_frames = _run(metadata, c_profile, C_VERSION)
    a_closed = _closed_lots(a_frames, metadata)
    c_closed = _closed_lots(c_frames, metadata)

    a_daily.to_csv(A_DAILY_PATH, index=False, encoding="utf-8-sig")
    c_daily.to_csv(C_DAILY_PATH, index=False, encoding="utf-8-sig")
    _save_frames(a_frames, {"entry_candidates": A_ENTRY_PATH, "entry_risk": A_RISK_PATH, "trades": A_TRADES_PATH})
    _save_frames(c_frames, {"entry_candidates": C_ENTRY_PATH, "entry_risk": C_RISK_PATH, "trades": C_TRADES_PATH})
    if not a_closed.empty:
        a_closed.to_csv(A_CLOSED_PATH, index=False, encoding="utf-8-sig")
    if not c_closed.empty:
        c_closed.to_csv(C_CLOSED_PATH, index=False, encoding="utf-8-sig")

    a_curve = s006.base._curve_for_metrics(a_daily, A_VERSION)
    c_curve = s006.base._curve_for_metrics(c_daily, C_VERSION)
    curves = pd.concat([a_curve, c_curve], ignore_index=True, sort=False)
    curves["stage"] = STAGE_LABEL
    curves["model_tag"] = MODEL_TAG
    curves["line_id"] = LINE_ID
    summary = pd.DataFrame([_summary_row(a_curve, a_closed), _summary_row(c_curve, c_closed)])
    c_entries = c_frames.get("entry_candidates", pd.DataFrame()).copy()
    covariance_audit = _covariance_audit(c_entries)
    ai_usage = s006._ai_usage_audit({A_VERSION: a_frames, C_VERSION: c_frames})
    decision = _decision(summary, covariance_audit, ai_parity)

    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    covariance_audit.to_csv(COVARIANCE_AUDIT_PATH, index=False, encoding="utf-8-sig")
    ai_parity.to_csv(AI_PARITY_PATH, index=False, encoding="utf-8-sig")
    ai_usage.to_csv(AI_USAGE_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(s006.base._json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _plot(curves)
    _write_records(summary, covariance_audit, ai_parity, decision)
    return {
        "summary": summary,
        "covariance_audit": covariance_audit,
        "ai_parity": ai_parity,
        "ai_usage": ai_usage,
        "curves": curves,
    }


def main() -> None:
    outputs = build()
    print(outputs["summary"].to_string(index=False))
    print(outputs["covariance_audit"].to_string(index=False))
    print(outputs["ai_parity"].to_string(index=False))
    print(f"report={REPORT_PATH}")
    print(f"chart={CHART_PATH}")


if __name__ == "__main__":
    main()
