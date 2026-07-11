#!/usr/bin/env python3
"""Stage012: use reconciled account equity throughout portfolio sizing."""

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


TOOLS_DIR = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[4]
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage006_stage013_reconciled_equity_engine as s6  # noqa: E402
import stage007_stage006_reconciled_equity_halfyear as s7  # noqa: E402
import stage009_gate_opportunity_cost_attribution as s9  # noqa: E402
import stage010_drawdown_recovery_progress_ramp as s10  # noqa: E402
import stage011_2021_anchor_path_feedback_attribution as s11  # noqa: E402


STAGE_LABEL = "Stage012"
STAGE_ID = "stage012_global_authoritative_equity_sizing_engine"
MODEL_TAG = f"{STAGE_ID}_v1"
LINE_ID = "futures_trend_stage013_current_ai_revalidation"
OUTPUT_PREFIX = f"stage013_current_ai_{STAGE_ID}"
A_VERSION = s10.A_VERSION
C_VERSION = "c_current_ai_stage012_global_authoritative_equity_sizing"
VERSIONS = (A_VERSION, C_VERSION)
C_STRATEGY = "stage012_global_authoritative_equity_sizing"
ANCHOR_STARTS = s10.ANCHOR_STARTS
REQUESTED_END = s10.REQUESTED_END
IMMEDIATE_REASON = "stage012_immediate_trade_duplicate_equity_correction"

LINE_DIR = TOOLS_DIR.parent
OUT = LINE_DIR / "outputs" / STAGE_ID
OUT.mkdir(parents=True, exist_ok=True)
SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
PAIR_PATH = OUT / f"{OUTPUT_PREFIX}_anchor_gates_{MODEL_TAG}.csv"
WINDOW_PATH = OUT / f"{OUTPUT_PREFIX}_2022_drawdown_windows_{MODEL_TAG}.csv"
REPRODUCTION_PATH = OUT / f"{OUTPUT_PREFIX}_a_reproduction_{MODEL_TAG}.csv"
RECONCILIATION_PATH = OUT / f"{OUTPUT_PREFIX}_reconciliation_{MODEL_TAG}.csv"
IMMEDIATE_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_immediate_correction_audit_{MODEL_TAG}.csv"
SIZING_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_sizing_alignment_audit_{MODEL_TAG}.csv.gz"
SIZING_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_sizing_alignment_summary_{MODEL_TAG}.csv"
AI_PARITY_PATH = OUT / f"{OUTPUT_PREFIX}_ai_parity_{MODEL_TAG}.csv"
AI_USAGE_PATH = OUT / f"{OUTPUT_PREFIX}_ai_usage_{MODEL_TAG}.csv"
CURVES_PATH = OUT / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv.gz"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
LINEAGE_PATH = OUT / f"{OUTPUT_PREFIX}_lineage_{MODEL_TAG}.json"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUT / f"{OUTPUT_PREFIX}_anchor_equity_drawdown_{MODEL_TAG}.png"
MANIFEST_PATH = OUT / f"{OUTPUT_PREFIX}_manifest_{MODEL_TAG}.csv"
TEST_PATH = TOOLS_DIR / "test_stage012_global_authoritative_equity_sizing_engine.py"

SAVE_FRAME_NAMES = (
    "entry_candidates",
    "trades",
    "trade_events",
    "stage006_equity_daily",
    "stage006_trade_corrections",
    "stage012_immediate_corrections",
    "stop_retry_events",
)


def _immediate_trade_equity_correction(
    *,
    settled_balance: float,
    estimated_equity: float,
    cumulative_duplicate_before: float,
    cumulative_duplicate_after: float,
) -> dict[str, float]:
    current_duplicate = float(cumulative_duplicate_after) - float(
        cumulative_duplicate_before
    )
    return {
        "current_duplicate_pnl": current_duplicate,
        "corrected_settled_balance": float(settled_balance) - current_duplicate,
        "corrected_estimated_equity": float(estimated_equity) - current_duplicate,
    }


def _legacy_counterfactual_equity(
    *, corrected_equity: float, cumulative_duplicate_pnl: float
) -> float:
    return float(corrected_equity) + float(cumulative_duplicate_pnl)


def _sizing_alignment_pass(
    frame: pd.DataFrame, *, expected_starts: set[str]
) -> bool:
    if frame.empty or set(frame["requested_start_month"].astype(str)) != set(
        expected_starts
    ):
        return False
    sizing_error = pd.to_numeric(
        frame["legacy_minus_official_same_day"], errors="coerce"
    )
    identity_error = pd.to_numeric(
        frame["official_daily_identity_error"], errors="coerce"
    )
    return bool(
        sizing_error.notna().all()
        and identity_error.notna().all()
        and sizing_error.abs().le(1e-8).all()
        and identity_error.abs().le(1e-8).all()
    )


class QmtRollPortfolioStrategyStage012GlobalAuthoritativeEquitySizing(
    s6.QmtRollPortfolioStrategyStage006ReconciledEquity
):
    enable_stage012_global_authoritative_equity_sizing: bool = False

    parameters = (
        s6.QmtRollPortfolioStrategyStage006ReconciledEquity.parameters
        + ["enable_stage012_global_authoritative_equity_sizing"]
    )
    variables = (
        s6.QmtRollPortfolioStrategyStage006ReconciledEquity.variables
        + ["stage012_immediate_correction_total"]
    )

    def __init__(
        self,
        strategy_engine: Any,
        strategy_name: str,
        vt_symbols: list[str],
        setting: dict[str, Any],
    ) -> None:
        self.stage012_immediate_correction_total = 0.0
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)

    def update_trade(self, trade: Any) -> None:
        cumulative_before = float(self.stage006_cumulative_duplicate_pnl)
        super().update_trade(trade)
        if not self.enable_stage012_global_authoritative_equity_sizing:
            return
        corrected = _immediate_trade_equity_correction(
            settled_balance=float(self.settled_balance),
            estimated_equity=float(self.estimated_equity),
            cumulative_duplicate_before=cumulative_before,
            cumulative_duplicate_after=float(self.stage006_cumulative_duplicate_pnl),
        )
        self.settled_balance = corrected["corrected_settled_balance"]
        self.estimated_equity = corrected["corrected_estimated_equity"]
        self.stage012_immediate_correction_total += corrected[
            "current_duplicate_pnl"
        ]
        self.trade_event_diagnostics.append(
            {
                "datetime": trade.datetime,
                "date": self._normalized_date(trade.datetime).date(),
                "vt_symbol": str(trade.vt_symbol),
                "product_vt_symbol": str(
                    self.source_symbol_by_contract.get(str(trade.vt_symbol), "")
                ),
                "direction": str(getattr(trade.direction, "value", trade.direction)),
                "offset": "Audit",
                "reason": IMMEDIATE_REASON,
                "volume": float(trade.volume),
                "price": float(trade.price),
                "stage012_trade_id": str(getattr(trade, "vt_tradeid", "")),
                "stage012_current_duplicate_pnl": corrected[
                    "current_duplicate_pnl"
                ],
                "stage012_cumulative_duplicate_pnl": float(
                    self.stage006_cumulative_duplicate_pnl
                ),
                "stage012_immediate_correction_total": float(
                    self.stage012_immediate_correction_total
                ),
                "stage012_corrected_settled_balance": float(
                    self.settled_balance
                ),
                "stage012_corrected_estimated_equity": float(
                    self.estimated_equity
                ),
            }
        )

    def _stage006_refresh_authoritative_equity(
        self, bars: dict[str, Any]
    ) -> None:
        if not bars:
            return
        first_bar = next(iter(bars.values()))
        current_date = self._normalized_date(first_bar.datetime)
        date_text = current_date.date().isoformat()
        if date_text in self.stage006_processed_dates:
            self.stage006_duplicate_date_count += 1
            raise RuntimeError(f"duplicate Stage012 equity date: {date_text}")
        self.stage006_processed_dates.add(date_text)

        engine_bars = dict(getattr(self.strategy_engine, "bars", {}) or bars)
        corrected_equity = float(self._estimate_equity(engine_bars))
        legacy_counterfactual = _legacy_counterfactual_equity(
            corrected_equity=corrected_equity,
            cumulative_duplicate_pnl=float(
                self.stage006_cumulative_duplicate_pnl
            ),
        )
        self.stage006_legacy_equity_at_close = legacy_counterfactual
        self.stage006_authoritative_equity = corrected_equity
        self.stage006_authoritative_high_water = max(
            float(self.base_capital),
            float(self.stage006_authoritative_high_water),
            corrected_equity,
        )
        if self.stage006_authoritative_high_water > 0.0:
            self.stage006_authoritative_drawdown_pct = max(
                0.0,
                (
                    self.stage006_authoritative_high_water - corrected_equity
                )
                / self.stage006_authoritative_high_water,
            )
        else:
            self.stage006_authoritative_drawdown_pct = 0.0
        self.trade_event_diagnostics.append(
            {
                "datetime": first_bar.datetime,
                "date": current_date.date(),
                "vt_symbol": "",
                "product_vt_symbol": "",
                "direction": "",
                "offset": "Audit",
                "reason": s6.DAILY_REASON,
                "volume": 0,
                "price": 0.0,
                "stage006_legacy_equity": legacy_counterfactual,
                "stage006_cumulative_duplicate_pnl": float(
                    self.stage006_cumulative_duplicate_pnl
                ),
                "stage006_authoritative_equity": corrected_equity,
                "stage006_authoritative_high_water": float(
                    self.stage006_authoritative_high_water
                ),
                "stage006_authoritative_drawdown_pct": float(
                    self.stage006_authoritative_drawdown_pct
                ),
                "stage006_future_trade_violation_count": int(
                    self.stage006_future_trade_violation_count
                ),
                "stage006_duplicate_date_count": int(
                    self.stage006_duplicate_date_count
                ),
                "stage012_global_authoritative_equity_sizing_enabled": int(
                    self.enable_stage012_global_authoritative_equity_sizing
                ),
                "stage012_immediate_correction_total": float(
                    self.stage012_immediate_correction_total
                ),
            }
        )


def _eligibility(
    strategy_name: str, score_type: str, version: str
) -> tuple[pd.DataFrame, Path]:
    frame = s6.stage001.source.s006._official_eligibility_for_strategy(
        strategy_name, score_type
    )
    path = OUT / f"{OUTPUT_PREFIX}_{version}_eligibility_{MODEL_TAG}.csv"
    frame.to_csv(path, index=False, encoding="utf-8-sig")
    return frame, path


def _candidate_profile(
    metadata: dict[str, Any], eligibility_path: Path
) -> dict[str, Any]:
    profile = s6._candidate_profile(metadata, eligibility_path)
    spec = profile["spec"]
    capital = replace(
        spec.capital,
        variant=C_VERSION,
        label="C current AI Stage012 global authoritative equity sizing",
        note=(
            f"{spec.capital.note} | Stage012 isolated account-ledger correctness candidate. "
            "All sizing and risk state use immediately reconciled account equity; no Stage013/ramp."
        ),
    )
    overrides = {
        **spec.overrides,
        "ai_product_pool_strategy": C_STRATEGY,
        "enable_stage013_account_state_pilot_gate": False,
        "enable_stage012_global_authoritative_equity_sizing": True,
    }
    result = dict(profile)
    result["profile"] = C_VERSION
    result["strategy_cls"] = (
        QmtRollPortfolioStrategyStage012GlobalAuthoritativeEquitySizing
    )
    result["spec"] = replace(
        spec,
        capital=capital,
        overrides=overrides,
        profile=C_VERSION,
    )
    return result


def _tag(frame: pd.DataFrame, start: pd.Timestamp, version: str) -> pd.DataFrame:
    result = frame.copy()
    if result.empty:
        return result
    result["start_month"] = start.strftime("%Y-%m")
    result["requested_start_month"] = start.strftime("%Y-%m")
    result["requested_end"] = REQUESTED_END.date().isoformat()
    result["version"] = version
    result["stage"] = STAGE_LABEL
    result["model_tag"] = MODEL_TAG
    result["line_id"] = LINE_ID
    return result


def _source_a_path(start: pd.Timestamp, kind: str) -> Path:
    prefix = f"{s10.OUTPUT_PREFIX}_{start.strftime('%Y-%m')}_{A_VERSION}"
    return s10.OUT / f"{prefix}_{kind}_{s10.MODEL_TAG}.csv.gz"


def _load_a_reference(
    start: pd.Timestamp,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], pd.DataFrame]:
    daily = pd.read_csv(_source_a_path(start, "daily"))
    frames = {}
    for name in ("entry_candidates", "trades", "trade_events", "stop_retry_events"):
        path = _source_a_path(start, name)
        frames[name] = pd.read_csv(path) if path.exists() else pd.DataFrame()
    closed_path = _source_a_path(start, "closed_lots")
    closed = pd.read_csv(closed_path)
    return _tag(daily, start, A_VERSION), {
        name: _tag(frame, start, A_VERSION) for name, frame in frames.items()
    }, _tag(closed, start, A_VERSION)


def _run_c(
    metadata: dict[str, Any], profile: dict[str, Any], start: pd.Timestamp
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], pd.DataFrame]:
    with s7._requested_window(start):
        daily, frames = s6.stage001._run(metadata, profile, C_VERSION)
    trade_events = frames.get("trade_events", pd.DataFrame()).copy()
    reason = trade_events.get("reason", pd.Series(dtype=str)).astype(str)
    frames["stage006_equity_daily"] = trade_events[reason.eq(s6.DAILY_REASON)].copy()
    frames["stage006_trade_corrections"] = trade_events[
        reason.eq(s6.CORRECTION_REASON)
    ].copy()
    frames["stage012_immediate_corrections"] = trade_events[
        reason.eq(IMMEDIATE_REASON)
    ].copy()
    closed = s6.stage001.source._closed_lots(frames, metadata)
    return _tag(daily, start, C_VERSION), {
        name: _tag(frame, start, C_VERSION) for name, frame in frames.items()
    }, _tag(closed, start, C_VERSION)


def _summary(
    daily: pd.DataFrame,
    closed: pd.DataFrame,
    version: str,
    start: pd.Timestamp,
) -> tuple[dict[str, Any], pd.DataFrame]:
    curve = s6.stage001.source.s006.base._curve_for_metrics(daily, version)
    row = s6.stage001.source.s006._summarize_curve(curve)
    realized = pd.to_numeric(
        closed.get("realized_pnl", pd.Series(dtype=float)), errors="coerce"
    ).dropna()
    row.update(
        {
            "stage": STAGE_LABEL,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "version": version,
            "requested_start_month": start.strftime("%Y-%m"),
            "requested_end": REQUESTED_END.date().isoformat(),
            "closed_lot_count": int(len(realized)),
            "closed_lot_win_rate_pct": (
                float((realized > 0.0).mean() * 100.0) if len(realized) else 0.0
            ),
        }
    )
    return row, _tag(curve, start, version)


def _save_arm(
    start: pd.Timestamp,
    version: str,
    daily: pd.DataFrame,
    frames: dict[str, pd.DataFrame],
    closed: pd.DataFrame,
) -> None:
    prefix = f"{OUTPUT_PREFIX}_{start.strftime('%Y-%m')}_{version}"
    daily.to_csv(
        OUT / f"{prefix}_daily_{MODEL_TAG}.csv.gz",
        index=False,
        encoding="utf-8-sig",
    )
    closed.to_csv(
        OUT / f"{prefix}_closed_lots_{MODEL_TAG}.csv.gz",
        index=False,
        encoding="utf-8-sig",
    )
    for name in SAVE_FRAME_NAMES:
        frame = frames.get(name, pd.DataFrame())
        if frame.empty:
            continue
        frame.to_csv(
            OUT / f"{prefix}_{name}_{MODEL_TAG}.csv.gz",
            index=False,
            encoding="utf-8-sig",
        )


def _immediate_audit(
    frames: dict[str, pd.DataFrame], start: pd.Timestamp
) -> dict[str, Any]:
    trades = frames.get("trades", pd.DataFrame())
    stage006_events = frames.get("stage006_trade_corrections", pd.DataFrame())
    immediate = frames.get("stage012_immediate_corrections", pd.DataFrame())
    current = pd.to_numeric(
        immediate.get("stage012_current_duplicate_pnl", pd.Series(dtype=float)),
        errors="coerce",
    )
    cumulative = pd.to_numeric(
        immediate.get(
            "stage012_cumulative_duplicate_pnl", pd.Series(dtype=float)
        ),
        errors="coerce",
    )
    total = pd.to_numeric(
        immediate.get(
            "stage012_immediate_correction_total", pd.Series(dtype=float)
        ),
        errors="coerce",
    )
    max_running_error = (
        float((total - cumulative).abs().max()) if len(immediate) else np.nan
    )
    return {
        "requested_start_month": start.strftime("%Y-%m"),
        "trade_count": int(len(trades)),
        "stage006_correction_count": int(len(stage006_events)),
        "stage012_immediate_correction_count": int(len(immediate)),
        "current_duplicate_sum": float(current.sum()),
        "final_cumulative_duplicate": float(cumulative.iloc[-1]) if len(cumulative) else 0.0,
        "final_immediate_correction_total": float(total.iloc[-1]) if len(total) else 0.0,
        "max_running_total_abs_error": max_running_error,
        "immediate_correction_pass": bool(
            len(trades) > 0
            and len(trades) == len(stage006_events) == len(immediate)
            and current.notna().all()
            and abs(float(current.sum()) - float(cumulative.iloc[-1])) <= 1e-8
            and max_running_error <= 1e-8
        ),
    }


def _sizing_summary(audit: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for start, part in audit.groupby("requested_start_month"):
        error = pd.to_numeric(
            part["legacy_minus_official_same_day"], errors="coerce"
        )
        identity = pd.to_numeric(
            part["official_daily_identity_error"], errors="coerce"
        )
        rows.append(
            {
                "requested_start_month": str(start),
                "candidate_day_count": int(len(part)),
                "max_sizing_equity_abs_error": float(error.abs().max()),
                "max_official_daily_identity_abs_error": float(
                    identity.abs().max()
                ),
                "all_candidate_days_aligned": bool(
                    error.notna().all()
                    and identity.notna().all()
                    and error.abs().le(1e-8).all()
                    and identity.abs().le(1e-8).all()
                ),
            }
        )
    return pd.DataFrame(rows)


def _windows(
    daily_by_key: dict[tuple[str, str], pd.DataFrame]
) -> pd.DataFrame:
    rows = []
    for start in ANCHOR_STARTS:
        start_month = start.strftime("%Y-%m")
        for version in VERSIONS:
            rows.append(
                {
                    "requested_start_month": start_month,
                    "version": version,
                    **s9._window_drawdown_metrics(
                        daily_by_key[(start_month, version)],
                        start=s9.YEAR_2022_START,
                        end=s9.YEAR_2022_END,
                    ),
                }
            )
    return pd.DataFrame(rows)


def _pairs(summary: pd.DataFrame, windows: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for start in ANCHOR_STARTS:
        start_month = start.strftime("%Y-%m")
        group = summary[summary["requested_start_month"].eq(start_month)]
        a = group[group["version"].eq(A_VERSION)].iloc[0].to_dict()
        c = group[group["version"].eq(C_VERSION)].iloc[0].to_dict()
        window = windows[windows["requested_start_month"].eq(start_month)]
        aw = window[window["version"].eq(A_VERSION)].iloc[0]
        cw = window[window["version"].eq(C_VERSION)].iloc[0]
        row = s10._anchor_gate_row(
            requested_start_month=start_month,
            a=a,
            c=c,
            a_2022_account_history_drawdown=float(
                aw["account_history_max_drawdown_pct"]
            ),
            c_2022_account_history_drawdown=float(
                cw["account_history_max_drawdown_pct"]
            ),
        )
        row.update(
            {
                "a_local_reset_2022_drawdown_pct": float(
                    aw["local_window_reset_max_drawdown_pct"]
                ),
                "c_local_reset_2022_drawdown_pct": float(
                    cw["local_window_reset_max_drawdown_pct"]
                ),
                "local_reset_2022_dd_improvement_pp": float(
                    cw["local_window_reset_max_drawdown_pct"]
                    - aw["local_window_reset_max_drawdown_pct"]
                ),
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def _ai_parity(
    eligibility: dict[str, pd.DataFrame], paths: dict[str, Path]
) -> pd.DataFrame:
    rows = []
    for version in VERSIONS:
        frame = eligibility[version]
        rows.append(
            {
                "version": version,
                "rows": int(len(frame)),
                "eval_date_count": int(frame["eval_date"].nunique()),
                "normalized_sha256": s6.stage001.source._normalized_ai_hash(frame),
                "eligibility_sha256": s9._sha256(paths[version]),
            }
        )
    result = pd.DataFrame(rows)
    result["all_normalized_equal"] = int(
        result["normalized_sha256"].nunique() == 1
    )
    return result


def _plot(curves: pd.DataFrame, pairs: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, len(ANCHOR_STARTS), figsize=(18, 9))
    colors = {A_VERSION: "#111827", C_VERSION: "#0f766e"}
    for index, start in enumerate(ANCHOR_STARTS):
        start_month = start.strftime("%Y-%m")
        for version in VERSIONS:
            part = curves[
                curves["requested_start_month"].eq(start_month)
                & curves["version"].eq(version)
            ].copy()
            part["date"] = pd.to_datetime(part["date"])
            equity = pd.to_numeric(part["account_equity"], errors="coerce")
            axes[0, index].plot(
                part["date"], equity, color=colors[version], label=version, linewidth=1.1
            )
            axes[1, index].plot(
                part["date"], (equity / equity.cummax() - 1.0) * 100.0,
                color=colors[version], linewidth=1.1,
            )
        pair = pairs[pairs["requested_start_month"].eq(start_month)].iloc[0]
        axes[0, index].set_title(
            f"{start_month} retention={pair['return_retention_ratio']:.1%}"
        )
        axes[0, index].grid(alpha=0.25)
        axes[1, index].grid(alpha=0.25)
        axes[1, index].set_title(
            f"DD improve={pair['full_drawdown_improvement_pp']:.2f}pp"
        )
    axes[0, 0].legend(fontsize=7)
    axes[0, 0].set_ylabel("account equity")
    axes[1, 0].set_ylabel("drawdown %")
    fig.suptitle("Stage012 global authoritative-equity sizing anchors")
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _manifest() -> pd.DataFrame:
    rows = []
    for path in sorted(OUT.iterdir()):
        if not path.is_file() or path == MANIFEST_PATH:
            continue
        rows.append(
            {
                "file": path.name,
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    return pd.DataFrame(rows)


def _write_report(
    summary: pd.DataFrame,
    pairs: pd.DataFrame,
    reconciliation: pd.DataFrame,
    immediate: pd.DataFrame,
    sizing_summary: pd.DataFrame,
    ai_parity: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    REPORT_PATH.write_text(
        f"""# Stage012 全局权威权益 sizing 三锚点 A/C

- 生成时间：`{decision['generated_at']}`。
- 决策：`{decision['decision']}`。
- A：Stage010 manifest 冻结的当前 C9 对照；C：每笔成交立即消除重复权益项，全局 sizing 使用正确账。
- C 明确关闭 Stage013 固定1手和 Stage010 ramp；AI、风险参数、退出、heat、成本和日期均未改。

## 锚点硬门

{pairs.to_markdown(index=False)}

## 分臂汇总

{summary.to_markdown(index=False)}

## 权威权益 reconciliation

{reconciliation.to_markdown(index=False)}

## 即时成交修正

{immediate.to_markdown(index=False)}

## 候选日 sizing 对齐

{sizing_summary.to_markdown(index=False)}

## AI parity

{ai_parity.to_markdown(index=False)}
""",
        encoding="utf-8",
    )


def build() -> dict[str, Any]:
    source_stage010 = s9._verify_manifest(s10.OUT, s10.MANIFEST_PATH)
    source_stage011 = s9._verify_manifest(s11.OUT, s11.MANIFEST_PATH)
    if not source_stage010["pass"] or not source_stage011["pass"]:
        raise RuntimeError(
            f"source manifest failed: stage010={source_stage010}, stage011={source_stage011}"
        )

    metadata = s6.stage001.source._metadata()
    a_eligibility, a_path = _eligibility(s10.A_STRATEGY, A_VERSION, A_VERSION)
    c_eligibility, c_path = _eligibility(C_STRATEGY, C_VERSION, C_VERSION)
    c_profile = _candidate_profile(metadata, c_path)
    eligibility = {A_VERSION: a_eligibility, C_VERSION: c_eligibility}
    eligibility_paths = {A_VERSION: a_path, C_VERSION: c_path}

    daily_by_key: dict[tuple[str, str], pd.DataFrame] = {}
    summary_rows = []
    curves = []
    reproduction_rows = []
    reconciliation_parts = []
    immediate_rows = []
    sizing_parts = []
    ai_usage_rows = []
    forbidden_event_count = 0

    for index, start in enumerate(ANCHOR_STARTS, 1):
        start_month = start.strftime("%Y-%m")
        print(f"[stage012] anchor {index}/{len(ANCHOR_STARTS)} start={start_month}", flush=True)

        a_daily, a_frames, a_closed = _load_a_reference(start)
        a_row, a_curve = _summary(a_daily, a_closed, A_VERSION, start)
        _save_arm(start, A_VERSION, a_daily, a_frames, a_closed)
        daily_by_key[(start_month, A_VERSION)] = a_daily
        summary_rows.append(a_row)
        curves.append(a_curve)
        reproduction_rows.append(s10._a_reproduction(start, a_daily))
        ai_usage_rows.append(s7._ai_usage_row(a_frames, A_VERSION, start))

        c_daily, c_frames, c_closed = _run_c(metadata, c_profile, start)
        c_row, c_curve = _summary(c_daily, c_closed, C_VERSION, start)
        _save_arm(start, C_VERSION, c_daily, c_frames, c_closed)
        daily_by_key[(start_month, C_VERSION)] = c_daily
        summary_rows.append(c_row)
        curves.append(c_curve)
        ai_usage_rows.append(s7._ai_usage_row(c_frames, C_VERSION, start))

        reconciliation = s6._equity_reconciliation(c_daily, c_frames)
        reconciliation["requested_start_month"] = start_month
        reconciliation_parts.append(reconciliation)
        immediate_rows.append(_immediate_audit(c_frames, start))
        sizing = s11._pretrade_equity_audit(
            c_frames["entry_candidates"], c_daily
        )
        sizing["requested_start_month"] = start_month
        sizing_parts.append(sizing)
        reason = c_frames.get("trade_events", pd.DataFrame()).get(
            "reason", pd.Series(dtype=str)
        ).astype(str)
        forbidden_event_count += int(
            reason.isin(
                [
                    "stage013_account_state_pilot_gate",
                    s10.RAMP_REASON,
                ]
            ).sum()
        )

    summary = pd.DataFrame(summary_rows).sort_values(
        ["requested_start_month", "version"]
    ).reset_index(drop=True)
    curve_frame = pd.concat(curves, ignore_index=True, sort=False)
    reproduction = pd.DataFrame(reproduction_rows).sort_values(
        "requested_start_month"
    )
    reconciliation = pd.concat(
        reconciliation_parts, ignore_index=True, sort=False
    )
    immediate = pd.DataFrame(immediate_rows).sort_values(
        "requested_start_month"
    )
    sizing_audit = pd.concat(sizing_parts, ignore_index=True, sort=False)
    sizing_summary = _sizing_summary(sizing_audit)
    ai_usage = pd.DataFrame(ai_usage_rows).sort_values(
        ["requested_start_month", "version"]
    )
    ai_parity = _ai_parity(eligibility, eligibility_paths)
    windows = _windows(daily_by_key)
    pairs = _pairs(summary, windows)

    expected_starts = {start.strftime("%Y-%m") for start in ANCHOR_STARTS}
    reproduction_ok = bool(
        len(reproduction) == len(ANCHOR_STARTS)
        and reproduction["reproduction_pass"].astype(bool).all()
    )
    reconciliation_ok = bool(
        len(reconciliation) >= len(ANCHOR_STARTS)
        and reconciliation["reconciliation_pass"].astype(bool).all()
    )
    immediate_ok = bool(
        len(immediate) == len(ANCHOR_STARTS)
        and immediate["immediate_correction_pass"].astype(bool).all()
    )
    sizing_ok = _sizing_alignment_pass(
        sizing_audit, expected_starts=expected_starts
    )
    ai_parity_ok = bool(ai_parity["all_normalized_equal"].eq(1).all())
    ai_usage_ok = s10._ai_usage_pass(ai_usage)
    semantics_ok = bool(
        source_stage010["pass"]
        and source_stage011["pass"]
        and reproduction_ok
        and reconciliation_ok
        and immediate_ok
        and sizing_ok
        and ai_parity_ok
        and ai_usage_ok
        and forbidden_event_count == 0
    )
    performance_ok = s10._anchor_performance_pass(pairs)
    decision = {
        "stage": STAGE_LABEL,
        "stage_id": STAGE_ID,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S CST"),
        "anchor_starts": [start.strftime("%Y-%m") for start in ANCHOR_STARTS],
        "requested_end": REQUESTED_END.date().isoformat(),
        "a_reference_reused_from_stage010": True,
        "c_true_engine_run_count": len(ANCHOR_STARTS),
        "source_stage010_manifest_pass": bool(source_stage010["pass"]),
        "source_stage011_manifest_pass": bool(source_stage011["pass"]),
        "a_reproduction_ok": reproduction_ok,
        "all_reconciliations_ok": reconciliation_ok,
        "all_immediate_corrections_ok": immediate_ok,
        "all_candidate_day_sizing_aligned": sizing_ok,
        "ai_parity_ok": ai_parity_ok,
        "ai_usage_ok": ai_usage_ok,
        "forbidden_stage013_or_ramp_event_count": int(forbidden_event_count),
        "semantics_ok": semantics_ok,
        "performance_ok": performance_ok,
        "anchor_gates": pairs.to_dict("records"),
        "final_goal_complete": False,
        "decision": (
            "stage012_anchor_pass_allow_halfyear"
            if semantics_ok and performance_ok
            else "stage012_anchor_fail_close_no_parameter_rescue"
        ),
        "overfit_before": "low: parameter-free account ledger correctness repair",
        "overfit_after": "pending_independent_review",
        "continue_value_before": "yes: current C9 sizing consumes a proven incorrect equity ledger",
        "continue_value_after": "pending_independent_review",
    }

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    pairs.to_csv(PAIR_PATH, index=False, encoding="utf-8-sig")
    windows.to_csv(WINDOW_PATH, index=False, encoding="utf-8-sig")
    reproduction.to_csv(REPRODUCTION_PATH, index=False, encoding="utf-8-sig")
    reconciliation.to_csv(RECONCILIATION_PATH, index=False, encoding="utf-8-sig")
    immediate.to_csv(IMMEDIATE_AUDIT_PATH, index=False, encoding="utf-8-sig")
    sizing_audit.to_csv(SIZING_AUDIT_PATH, index=False, compression="gzip")
    sizing_summary.to_csv(SIZING_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    ai_parity.to_csv(AI_PARITY_PATH, index=False, encoding="utf-8-sig")
    ai_usage.to_csv(AI_USAGE_PATH, index=False, encoding="utf-8-sig")
    curve_frame.to_csv(CURVES_PATH, index=False, compression="gzip")
    DECISION_PATH.write_text(
        json.dumps(s9._json_safe(decision), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    lineage = {
        "stage": STAGE_LABEL,
        "source_stage010_manifest": str(s10.MANIFEST_PATH),
        "source_stage010_manifest_audit": source_stage010,
        "source_stage011_manifest": str(s11.MANIFEST_PATH),
        "source_stage011_manifest_audit": source_stage011,
        "stage012_tool": {
            "path": str(Path(__file__).resolve()),
            "sha256": s9._sha256(Path(__file__).resolve()),
        },
        "stage012_test": {
            "path": str(TEST_PATH),
            "sha256": s9._sha256(TEST_PATH),
        },
        "a_reference_files": {
            f"{start.strftime('%Y-%m')}_{kind}": str(_source_a_path(start, kind))
            for start in ANCHOR_STARTS
            for kind in ("daily", "entry_candidates", "trades", "trade_events", "closed_lots")
        },
        "history_database_snapshot_complete": False,
    }
    LINEAGE_PATH.write_text(
        json.dumps(s9._json_safe(lineage), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _plot(curve_frame, pairs)
    _write_report(
        summary,
        pairs,
        reconciliation,
        immediate,
        sizing_summary,
        ai_parity,
        decision,
    )
    _manifest().to_csv(MANIFEST_PATH, index=False, encoding="utf-8-sig")
    return {
        "summary": summary,
        "pairs": pairs,
        "reconciliation": reconciliation,
        "immediate": immediate,
        "sizing_summary": sizing_summary,
        "decision": decision,
    }


if __name__ == "__main__":
    result = build()
    print(result["summary"].to_string(index=False))
    print(result["pairs"].to_string(index=False))
    print(result["immediate"].to_string(index=False))
    print(result["sizing_summary"].to_string(index=False))
