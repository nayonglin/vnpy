from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage696_stage407_soft_streak_risk as s696
import analyze_qmt_roll_stage707_recovery_all_cases_multiperiod as s707
from qmt_roll_official_live_config import OFFICIAL_LIVE_CAPITAL, OFFICIAL_LIVE_PROFILE_NAME, OFFICIAL_LIVE_VERSION


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage708_recovery_all_cases_attribution_v1"
OUTPUT_PREFIX = "qmt_roll_stage708_recovery_all_cases_attribution"
LINE_ID = "futures_trend_drawdown30_preserve_return"

BASE_VARIANT = OFFICIAL_LIVE_PROFILE_NAME
CANDIDATE_VARIANT = s707.CANDIDATE_VARIANT

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
POSITIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_{MODEL_TAG}.csv"
PRODUCT_DELTA_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_delta_{MODEL_TAG}.csv"
ENTRY_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_summary_{MODEL_TAG}.csv"
RECOVERY_DETAIL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_recovery_detail_{MODEL_TAG}.csv"
RECOVERY_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_recovery_summary_{MODEL_TAG}.csv"
FORCED_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_forced_events_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_delta_chart_{MODEL_TAG}.png"

WINDOWS: tuple[tuple[str, str, str, str], ...] = (
    ("phase_2022_2023", "2022-2023 独立启动改善窗口", "2022-01-01", "2023-12-31"),
    ("phase_2024_2025", "2024-2025 独立启动改善窗口", "2024-01-01", "2025-12-31"),
    ("phase_2026_latest", "2026 独立启动失败窗口", "2026-01-01", "2026-04-30"),
)


def _json_safe(value: Any) -> Any:
    return s707._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s707._md_table(frame, max_rows=max_rows)


def _product_from_vt_symbol(vt_symbol: Any) -> str:
    text = str(vt_symbol or "")
    symbol = text.split(".", 1)[0]
    product = ""
    for char in symbol:
        if char.isalpha():
            product += char
        else:
            break
    return product.lower()


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    values = pd.to_numeric(equity, errors="coerce").ffill().fillna(OFFICIAL_LIVE_CAPITAL)
    peak = values.cummax()
    return (values / peak.replace(0.0, np.nan) - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0) * 100.0


def _sharpe(equity: pd.Series) -> float:
    returns = pd.to_numeric(equity, errors="coerce").ffill().pct_change().replace([np.inf, -np.inf], np.nan).fillna(0.0)
    std = float(returns.std(ddof=1))
    if std <= 0:
        return 0.0
    return float(returns.mean() / std * np.sqrt(252.0))


def _run_window_with_diagnostics(
    *,
    spec: s696.s692.s653.ForcedVariant,
    metadata: dict[str, Any],
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    original_start = s696.s692.s653.s517.START_DT
    original_end = s696.s692.s653.s517.END_DT
    try:
        s696.s692.s653.s517.START_DT = start.to_pydatetime()
        s696.s692.s653.s517.END_DT = end.to_pydatetime()
        daily, positions, _product_margin, _usage, _candidates, entry_risk, forced_events = (
            s696._run_variant_with_diagnostics(replace(spec), metadata)
        )
    finally:
        s696.s692.s653.s517.START_DT = original_start
        s696.s692.s653.s517.END_DT = original_end

    daily = daily.copy()
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
    daily = daily[daily["date"].between(start, end)].copy()

    positions = positions.copy()
    if not positions.empty:
        positions["date"] = pd.to_datetime(positions["date"], errors="coerce").dt.normalize()
        positions = positions[positions["date"].between(start, end)].copy()
        positions["product"] = positions["vt_symbol"].map(_product_from_vt_symbol)

    entry_risk = entry_risk.copy()
    if not entry_risk.empty:
        entry_risk["date"] = pd.to_datetime(entry_risk["date"], errors="coerce").dt.normalize()
        entry_risk = entry_risk[entry_risk["date"].between(start, end)].copy()
        entry_risk["product"] = entry_risk["product_vt_symbol"].map(_product_from_vt_symbol)

    forced_events = forced_events.copy()
    if not forced_events.empty and "date" in forced_events.columns:
        forced_events["date"] = pd.to_datetime(forced_events["date"], errors="coerce").dt.normalize()
        forced_events = forced_events[forced_events["date"].between(start, end)].copy()

    return daily, positions, entry_risk, forced_events, pd.DataFrame()


def _metric_row(daily: pd.DataFrame, *, window_name: str, window_label: str, variant: str, label: str) -> dict[str, Any]:
    ordered = daily.sort_values("date").reset_index(drop=True)
    equity = pd.to_numeric(ordered["account_equity"], errors="coerce").ffill().fillna(OFFICIAL_LIVE_CAPITAL)
    dd = _drawdown_pct(equity)
    slippage_col = "total_slippage" if "total_slippage" in ordered.columns else "slippage"
    return {
        "window_name": window_name,
        "window_label": window_label,
        "variant": variant,
        "label": label,
        "start_date": pd.Timestamp(ordered["date"].iloc[0]).date().isoformat(),
        "end_date": pd.Timestamp(ordered["date"].iloc[-1]).date().isoformat(),
        "end_equity": float(equity.iloc[-1]),
        "total_return_pct": float((equity.iloc[-1] / OFFICIAL_LIVE_CAPITAL - 1.0) * 100.0),
        "max_dd_pct": float(dd.min()),
        "sharpe": _sharpe(equity),
        "total_slippage": float(pd.to_numeric(ordered.get(slippage_col, 0.0), errors="coerce").fillna(0.0).sum()),
        "total_trade_count": float(pd.to_numeric(ordered.get("trade_count", 0.0), errors="coerce").fillna(0.0).sum()),
        "win_rate_pct": float(
            pd.to_numeric(ordered.get("net_pnl", 0.0), errors="coerce").fillna(0.0).loc[
                lambda series: series.abs().gt(1e-12)
            ].gt(0.0).mean()
            * 100.0
        )
        if pd.to_numeric(ordered.get("net_pnl", 0.0), errors="coerce").fillna(0.0).abs().gt(1e-12).any()
        else 0.0,
        "max_broker10_margin_to_equity_pct": float(
            pd.to_numeric(ordered.get("broker10_margin_to_equity_pct", 0.0), errors="coerce").fillna(0.0).max()
        ),
    }


def _product_delta(positions: pd.DataFrame, entry_risk: pd.DataFrame) -> pd.DataFrame:
    if positions.empty:
        return pd.DataFrame()
    data = positions.copy()
    for column in ["net_pnl", "slippage", "trade_count"]:
        data[column] = pd.to_numeric(data.get(column, 0.0), errors="coerce").fillna(0.0)
    product = (
        data.groupby(["window_name", "variant", "product"], dropna=False)
        .agg(net_pnl=("net_pnl", "sum"), trade_count=("trade_count", "sum"), slippage=("slippage", "sum"))
        .reset_index()
    )
    entry_volume = pd.DataFrame()
    if not entry_risk.empty:
        risk = entry_risk.copy()
        risk["selected_volume"] = pd.to_numeric(risk.get("selected_volume", 0.0), errors="coerce").fillna(0.0)
        entry_volume = (
            risk.groupby(["window_name", "variant", "product"], dropna=False)
            .agg(opened_entries=("selected_volume", "size"), selected_volume=("selected_volume", "sum"))
            .reset_index()
        )
    if not entry_volume.empty:
        product = product.merge(entry_volume, on=["window_name", "variant", "product"], how="outer")
    for column in ["net_pnl", "trade_count", "slippage", "opened_entries", "selected_volume"]:
        product[column] = pd.to_numeric(product.get(column, 0.0), errors="coerce").fillna(0.0)

    rows: list[dict[str, Any]] = []
    for (window_name, product_name), group in product.groupby(["window_name", "product"], sort=True):
        base = group[group["variant"].eq(BASE_VARIANT)]
        candidate = group[group["variant"].eq(CANDIDATE_VARIANT)]
        b = base.iloc[0].to_dict() if not base.empty else {}
        c = candidate.iloc[0].to_dict() if not candidate.empty else {}
        row = {"window_name": window_name, "product": product_name}
        for metric in ["net_pnl", "trade_count", "slippage", "opened_entries", "selected_volume"]:
            base_value = float(b.get(metric, 0.0) or 0.0)
            candidate_value = float(c.get(metric, 0.0) or 0.0)
            row[f"base_{metric}"] = base_value
            row[f"candidate_{metric}"] = candidate_value
            row[f"delta_{metric}"] = candidate_value - base_value
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["window_name", "delta_net_pnl"], ascending=[True, True])


def _entry_summary(entry_risk: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if entry_risk.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    data = entry_risk.copy()
    numeric_columns = [
        "selected_volume",
        "target_risk_amount",
        "actual_risk_amount",
        "risk_multiplier",
        "loss_streak",
        "streak_entry_structure_risk_recovery_applied",
        "streak_entry_structure_risk_recovery_base_multiplier",
        "streak_entry_structure_risk_recovery_effective_multiplier",
    ]
    for column in numeric_columns:
        data[column] = pd.to_numeric(data.get(column, 0.0), errors="coerce").fillna(0.0)
    data["severe_streak"] = data["loss_streak"].ge(3).astype(int)
    data["recovery_applied"] = data["streak_entry_structure_risk_recovery_applied"].gt(0).astype(int)

    summary = (
        data.groupby(["window_name", "variant"], sort=True)
        .agg(
            opened_entries=("entry_index", "size"),
            selected_volume=("selected_volume", "sum"),
            target_risk_amount=("target_risk_amount", "sum"),
            actual_risk_amount=("actual_risk_amount", "sum"),
            avg_risk_multiplier=("risk_multiplier", "mean"),
            severe_streak_entries=("severe_streak", "sum"),
            severe_streak_volume=("selected_volume", lambda series: float(series[data.loc[series.index, "severe_streak"].eq(1)].sum())),
            recovery_applied_entries=("recovery_applied", "sum"),
            recovery_applied_volume=("selected_volume", lambda series: float(series[data.loc[series.index, "recovery_applied"].eq(1)].sum())),
        )
        .reset_index()
    )

    recovery_detail = data[data["recovery_applied"].eq(1)].copy()
    detail_columns = [
        "window_name",
        "variant",
        "date",
        "product",
        "product_vt_symbol",
        "contract_vt_symbol",
        "direction",
        "signal",
        "loss_streak",
        "streak_entry_structure_risk_recovery_reason",
        "streak_entry_structure_risk_recovery_base_multiplier",
        "streak_entry_structure_risk_recovery_effective_multiplier",
        "selected_volume",
        "target_risk_amount",
        "actual_risk_amount",
        "portfolio_drawdown_pct",
        "same_direction_correlation_max_corr",
    ]
    recovery_detail = recovery_detail[[column for column in detail_columns if column in recovery_detail.columns]].copy()
    recovery_summary = pd.DataFrame()
    if not recovery_detail.empty:
        recovery_summary = (
            recovery_detail.groupby(["window_name", "variant", "product", "signal"], sort=True)
            .agg(
                recovery_entries=("selected_volume", "size"),
                recovery_volume=("selected_volume", "sum"),
                target_risk_amount=("target_risk_amount", "sum"),
                actual_risk_amount=("actual_risk_amount", "sum"),
            )
            .reset_index()
            .sort_values(["window_name", "variant", "recovery_volume"], ascending=[True, True, False])
        )
    return summary, recovery_detail, recovery_summary


def _summary_delta(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for window_name, group in summary.groupby("window_name", sort=True):
        base = group[group["variant"].eq(BASE_VARIANT)]
        candidate = group[group["variant"].eq(CANDIDATE_VARIANT)]
        if base.empty or candidate.empty:
            continue
        b = base.iloc[0]
        c = candidate.iloc[0]
        rows.append(
            {
                "window_name": window_name,
                "base_return_pct": float(b["total_return_pct"]),
                "candidate_return_pct": float(c["total_return_pct"]),
                "delta_return_pct": float(c["total_return_pct"] - b["total_return_pct"]),
                "base_max_dd_pct": float(b["max_dd_pct"]),
                "candidate_max_dd_pct": float(c["max_dd_pct"]),
                "delta_max_dd_pct": float(c["max_dd_pct"] - b["max_dd_pct"]),
                "base_sharpe": float(b["sharpe"]),
                "candidate_sharpe": float(c["sharpe"]),
                "delta_sharpe": float(c["sharpe"] - b["sharpe"]),
                "delta_end_equity": float(c["end_equity"] - b["end_equity"]),
                "delta_trade_count": float(c["total_trade_count"] - b["total_trade_count"]),
                "delta_slippage": float(c["total_slippage"] - b["total_slippage"]),
            }
        )
    return pd.DataFrame(rows)


def _plot_product_delta(product_delta: pd.DataFrame) -> None:
    if product_delta.empty:
        return
    fig, axes = plt.subplots(len(WINDOWS), 1, figsize=(14, 10), sharex=False)
    if len(WINDOWS) == 1:
        axes = [axes]
    for ax, (window_name, _label, _start, _end) in zip(axes, WINDOWS):
        frame = product_delta[product_delta["window_name"].eq(window_name)].copy()
        if frame.empty:
            continue
        frame = frame.reindex(frame["delta_net_pnl"].abs().sort_values(ascending=False).index).head(12)
        colors = np.where(frame["delta_net_pnl"].ge(0), "#16a34a", "#dc2626")
        ax.bar(frame["product"], frame["delta_net_pnl"], color=colors)
        ax.axhline(0.0, color="#64748b", linewidth=0.8)
        ax.set_title(f"{window_name}: candidate product PnL delta vs official")
        ax.set_ylabel("delta net pnl")
        ax.grid(True, axis="y", linestyle="--", linewidth=0.5, alpha=0.35)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=170)
    plt.close(fig)


def _decision(summary_delta: pd.DataFrame, product_delta: pd.DataFrame, recovery_summary: pd.DataFrame) -> dict[str, Any]:
    phase_2026 = summary_delta[summary_delta["window_name"].eq("phase_2026_latest")]
    phase_2024 = summary_delta[summary_delta["window_name"].eq("phase_2024_2025")]
    phase_2022 = summary_delta[summary_delta["window_name"].eq("phase_2022_2023")]
    hard_finding = ""
    if not phase_2026.empty and float(phase_2026["delta_end_equity"].iloc[0]) < 0:
        hard_finding = "2026 independent-start attribution remains negative"
    return {
        "stage": "Stage422",
        "script_stage": "Stage708",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "baseline": BASE_VARIANT,
        "candidate": CANDIDATE_VARIANT,
        "decision": "read_only_attribution_no_promotion",
        "hard_finding": hard_finding,
        "change": {
            "official_config_changed": False,
            "ctp_connected": False,
            "order_api_called": False,
            "new_trading_rule": False,
            "attribution_windows": [item[0] for item in WINDOWS],
        },
        "summary_delta": summary_delta.to_dict("records"),
        "top_negative_product_delta": (
            product_delta.sort_values("delta_net_pnl").head(20).to_dict("records") if not product_delta.empty else []
        ),
        "recovery_summary": recovery_summary.to_dict("records") if not recovery_summary.empty else [],
        "stage421_context": {
            "candidate_was_not_promoted": True,
            "reason": "multi-start failure in since_2026 / phase_2026_latest",
        },
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "daily": str(DAILY_PATH),
            "positions": str(POSITIONS_PATH),
            "product_delta": str(PRODUCT_DELTA_PATH),
            "entry_summary": str(ENTRY_SUMMARY_PATH),
            "recovery_detail": str(RECOVERY_DETAIL_PATH),
            "recovery_summary": str(RECOVERY_SUMMARY_PATH),
            "forced_events": str(FORCED_EVENTS_PATH),
            "chart": str(CHART_PATH),
            "report": str(REPORT_PATH),
            "decision": str(DECISION_PATH),
        },
    }


def _write_report(
    summary: pd.DataFrame,
    summary_delta: pd.DataFrame,
    product_delta: pd.DataFrame,
    entry_summary: pd.DataFrame,
    recovery_detail: pd.DataFrame,
    recovery_summary: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    lines = [
        "# Stage422 / Script708 Recovery All Cases Attribution",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        "- 阶段性质：只读归因，解释 Stage421 all-cases recovery 为什么改善 2022-2025、但 2026 独立启动失败。",
        "- 不新增交易规则、不修改正式配置、不连接 CTP、不调用下单。",
        "",
        "## Summary Delta",
        "",
        _md_table(summary_delta, max_rows=40),
        "",
        "## Product Delta: Worst Contributors",
        "",
        _md_table(product_delta.sort_values(["window_name", "delta_net_pnl"]).groupby("window_name").head(10), max_rows=80),
        "",
        "## Product Delta: Best Contributors",
        "",
        _md_table(
            product_delta.sort_values(["window_name", "delta_net_pnl"], ascending=[True, False])
            .groupby("window_name")
            .head(10),
            max_rows=80,
        ),
        "",
        "## Entry Summary",
        "",
        _md_table(entry_summary, max_rows=80),
        "",
        "## Recovery Summary",
        "",
        _md_table(recovery_summary, max_rows=100),
        "",
        "## Recovery Detail",
        "",
        _md_table(recovery_detail, max_rows=120),
        "",
        "## Raw Summary",
        "",
        _md_table(summary, max_rows=80),
        "",
        "## Decision",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- hard_finding：`{decision.get('hard_finding') or '无'}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    metadata = s707.s513._metadata()
    specs = [s707.s660._official_spec(metadata), s707._candidate_spec(metadata)]

    summary_rows: list[dict[str, Any]] = []
    daily_frames: list[pd.DataFrame] = []
    position_frames: list[pd.DataFrame] = []
    entry_frames: list[pd.DataFrame] = []
    forced_frames: list[pd.DataFrame] = []

    for window_name, window_label, start_text, end_text in WINDOWS:
        start = pd.Timestamp(start_text)
        end = pd.Timestamp(end_text)
        for spec in specs:
            print(f"[stage708] running {window_name} {spec.capital.variant}", flush=True)
            daily, positions, entry_risk, forced_events, _unused = _run_window_with_diagnostics(
                spec=spec,
                metadata=metadata,
                start=start,
                end=end,
            )
            daily["window_name"] = window_name
            daily["window_label"] = window_label
            positions["window_name"] = window_name
            positions["window_label"] = window_label
            entry_risk["window_name"] = window_name
            entry_risk["window_label"] = window_label
            if not forced_events.empty:
                forced_events["window_name"] = window_name
                forced_events["window_label"] = window_label
                forced_frames.append(forced_events)
            summary_rows.append(
                _metric_row(
                    daily,
                    window_name=window_name,
                    window_label=window_label,
                    variant=spec.capital.variant,
                    label=spec.capital.label,
                )
            )
            daily_frames.append(daily)
            position_frames.append(positions)
            entry_frames.append(entry_risk)

    summary = pd.DataFrame(summary_rows)
    daily_all = pd.concat(daily_frames, ignore_index=True, sort=False) if daily_frames else pd.DataFrame()
    positions_all = pd.concat(position_frames, ignore_index=True, sort=False) if position_frames else pd.DataFrame()
    entry_all = pd.concat(entry_frames, ignore_index=True, sort=False) if entry_frames else pd.DataFrame()
    forced_all = pd.concat(forced_frames, ignore_index=True, sort=False) if forced_frames else pd.DataFrame()
    summary_delta = _summary_delta(summary)
    product_delta = _product_delta(positions_all, entry_all)
    entry_summary, recovery_detail, recovery_summary = _entry_summary(entry_all)
    decision = _decision(summary_delta, product_delta, recovery_summary)

    _plot_product_delta(product_delta)
    _write_report(summary, summary_delta, product_delta, entry_summary, recovery_detail, recovery_summary, decision)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    daily_all.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    positions_all.to_csv(POSITIONS_PATH, index=False, encoding="utf-8-sig")
    product_delta.to_csv(PRODUCT_DELTA_PATH, index=False, encoding="utf-8-sig")
    entry_summary.to_csv(ENTRY_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    recovery_detail.to_csv(RECOVERY_DETAIL_PATH, index=False, encoding="utf-8-sig")
    recovery_summary.to_csv(RECOVERY_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    forced_all.to_csv(FORCED_EVENTS_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
