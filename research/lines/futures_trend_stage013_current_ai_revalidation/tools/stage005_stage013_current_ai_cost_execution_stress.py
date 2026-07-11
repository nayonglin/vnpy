#!/usr/bin/env python3
"""Stage005: true-engine cost and execution stress for frozen Stage013."""

from __future__ import annotations

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
TOOLS_DIR = Path(__file__).resolve().parent
PORTFOLIO_DIR = ROOT / "examples" / "portfolio_backtesting"
for item in (TOOLS_DIR, PORTFOLIO_DIR):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

import stage001_stage013_current_ai_engine as stage001  # noqa: E402
from qmt_roll_official_live_config import OFFICIAL_LIVE_AI_ELIGIBILITY_PATH  # noqa: E402


LINE_ID = "futures_trend_stage013_current_ai_revalidation"
STAGE_ID = "stage005_stage013_current_ai_cost_execution_stress"
STAGE_LABEL = "Stage005"
MODEL_TAG = f"{STAGE_ID}_v1"
OUTPUT_PREFIX = f"stage013_current_ai_{STAGE_ID}"

A_VERSION = stage001.A_VERSION
C_VERSION = stage001.C_VERSION
VERSIONS = (A_VERSION, C_VERSION)
COST_MULTIPLIERS = (1.0, 2.0, 3.0)
RUN_ORDER = (
    (1.0, A_VERSION),
    (1.0, C_VERSION),
    (2.0, C_VERSION),
    (2.0, A_VERSION),
    (3.0, A_VERSION),
    (3.0, C_VERSION),
)
CORE_TOLERANCE = 1e-8

RETURN_RETENTION_MIN = stage001.RETURN_RETENTION_MIN
FULL_DD_IMPROVEMENT_MIN_PP = stage001.FULL_DD_IMPROVEMENT_MIN_PP
YEAR_2022_DD_IMPROVEMENT_MIN_PP = stage001.YEAR_2022_DD_IMPROVEMENT_MIN_PP
STRESS_DD_IMPROVEMENT_MIN_PP = stage001.STRESS_DD_IMPROVEMENT_MIN_PP

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / STAGE_ID
SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
STRESS_PATH = OUT / f"{OUTPUT_PREFIX}_stress_{MODEL_TAG}.csv"
PAIR_PATH = OUT / f"{OUTPUT_PREFIX}_paired_gates_{MODEL_TAG}.csv"
COST_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_cost_metadata_audit_{MODEL_TAG}.csv"
REPRO_PATH = OUT / f"{OUTPUT_PREFIX}_stage001_reproduction_{MODEL_TAG}.csv"
PILOT_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_pilot_audit_{MODEL_TAG}.csv"
AI_PARITY_PATH = OUT / f"{OUTPUT_PREFIX}_ai_parity_{MODEL_TAG}.csv"
AI_USAGE_PATH = OUT / f"{OUTPUT_PREFIX}_ai_usage_{MODEL_TAG}.csv"
CURVES_PATH = OUT / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv.gz"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
LINEAGE_PATH = OUT / f"{OUTPUT_PREFIX}_lineage_{MODEL_TAG}.json"
MANIFEST_PATH = OUT / f"{OUTPUT_PREFIX}_manifest_{MODEL_TAG}.csv"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUT / f"{OUTPUT_PREFIX}_equity_drawdown_by_cost_{MODEL_TAG}.png"

STAGE001_OUT = LINE_DIR / "outputs" / stage001.STAGE_ID
STAGE001_SUMMARY_PATH = stage001.SUMMARY_PATH
CORE_DAILY_COLUMNS = (
    "trade_count",
    "turnover",
    "commission",
    "slippage",
    "trading_pnl",
    "holding_pnl",
    "total_pnl",
    "net_pnl",
    "c3_margin_exact",
    "total_net_pnl",
    "total_slippage",
    "account_equity",
    "total_margin_exact",
    "broker10_total_margin_exact",
    "broker10_margin_to_equity_pct",
)
CORE_SUMMARY_COLUMNS = (
    "end_equity",
    "total_return_pct",
    "max_drawdown_pct",
    "sharpe",
    "total_slippage",
    "total_trade_count",
    "nonzero_daily_win_rate_pct",
    "max_broker10_margin_to_equity_pct",
    "closed_lot_count",
    "closed_lot_win_rate_pct",
)
SAVE_FRAME_NAMES = (
    "entry_candidates",
    "entry_risk",
    "trades",
    "positions",
    "trade_events",
    "intraday_events",
    "c2_events",
    "stop_retry_events",
    "pending_orders",
    "pilot_gate_events",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _mapping_sha256(values: dict[str, Any]) -> str:
    payload = json.dumps(
        {str(key): float(value) for key, value in sorted(values.items())},
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def _scaled_metadata(
    metadata: dict[str, Any], multiplier: float
) -> tuple[dict[str, Any], dict[str, Any]]:
    if float(multiplier) <= 0.0:
        raise ValueError("slippage multiplier must be positive")
    original = {
        str(symbol): float(value)
        for symbol, value in dict(metadata.get("slippages", {})).items()
    }
    scaled_slippages = {
        symbol: value * float(multiplier) for symbol, value in original.items()
    }
    scaled = dict(metadata)
    scaled["slippages"] = scaled_slippages
    symbols = sorted(set(original) | set(scaled_slippages))
    ratio_errors = sum(
        abs(scaled_slippages.get(symbol, float("nan")) - original.get(symbol, float("nan")) * float(multiplier))
        > 1e-12
        for symbol in symbols
        if symbol in original and symbol in scaled_slippages
    )
    missing = len(set(original).symmetric_difference(scaled_slippages))
    audit = {
        "slippage_multiplier": float(multiplier),
        "symbol_count": int(len(original)),
        "base_min_slippage": float(min(original.values())) if original else 0.0,
        "base_max_slippage": float(max(original.values())) if original else 0.0,
        "scaled_min_slippage": float(min(scaled_slippages.values())) if scaled_slippages else 0.0,
        "scaled_max_slippage": float(max(scaled_slippages.values())) if scaled_slippages else 0.0,
        "base_slippage_sha256": _mapping_sha256(original),
        "scaled_slippage_sha256": _mapping_sha256(scaled_slippages),
        "ratio_error_count": int(ratio_errors),
        "missing_symbol_count": int(missing),
    }
    return scaled, audit


def _paired_gate_row(
    multiplier: float,
    a: dict[str, Any],
    c: dict[str, Any],
    a_windows: dict[str, float],
    c_windows: dict[str, float],
) -> dict[str, Any]:
    a_return = float(a["total_return_pct"])
    c_return = float(c["total_return_pct"])
    retention = c_return / a_return if a_return > 0.0 else float("nan")
    full_dd = float(c["max_drawdown_pct"]) - float(a["max_drawdown_pct"])
    year_2022_dd = float(c_windows["year_2022"]) - float(a_windows["year_2022"])
    main_stress_dd = (
        float(c_windows["main_2022_2024_stress"])
        - float(a_windows["main_2022_2024_stress"])
    )
    broker_delta = (
        float(c["max_broker10_margin_to_equity_pct"])
        - float(a["max_broker10_margin_to_equity_pct"])
    )
    positive_return_pass = c_return > 0.0
    retention_pass = retention >= RETURN_RETENTION_MIN
    full_dd_pass = full_dd >= FULL_DD_IMPROVEMENT_MIN_PP
    year_2022_dd_pass = year_2022_dd >= YEAR_2022_DD_IMPROVEMENT_MIN_PP
    main_stress_dd_pass = main_stress_dd >= STRESS_DD_IMPROVEMENT_MIN_PP
    broker_pass = broker_delta <= 1e-9
    return {
        "slippage_multiplier": float(multiplier),
        "a_total_return_pct": a_return,
        "c_total_return_pct": c_return,
        "same_cost_return_retention_ratio": float(retention),
        "full_drawdown_improvement_pct": full_dd,
        "year_2022_drawdown_improvement_pct": year_2022_dd,
        "main_stress_drawdown_improvement_pct": main_stress_dd,
        "broker10_peak_delta_pct": broker_delta,
        "positive_return_pass": bool(positive_return_pass),
        "return_retention_pass": bool(retention_pass),
        "full_drawdown_pass": bool(full_dd_pass),
        "year_2022_drawdown_pass": bool(year_2022_dd_pass),
        "main_stress_drawdown_pass": bool(main_stress_dd_pass),
        "broker10_pass": bool(broker_pass),
        "performance_gate_pass": bool(
            positive_return_pass
            and retention_pass
            and full_dd_pass
            and year_2022_dd_pass
            and main_stress_dd_pass
            and broker_pass
        ),
    }


def _eligibility(
    strategy_name: str, score_type: str, version: str
) -> tuple[pd.DataFrame, Path]:
    frame = stage001.source.s006._official_eligibility_for_strategy(
        strategy_name, score_type
    )
    path = OUT / f"{OUTPUT_PREFIX}_{version}_eligibility_{MODEL_TAG}.csv"
    frame.to_csv(path, index=False, encoding="utf-8-sig")
    return frame, path


def _run_arm(
    metadata: dict[str, Any],
    profile: dict[str, Any],
    version: str,
    multiplier: float,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    daily, frames = stage001._run(metadata, profile, version)
    daily = daily.copy()
    daily["stage"] = STAGE_LABEL
    daily["model_tag"] = MODEL_TAG
    daily["line_id"] = LINE_ID
    daily["slippage_multiplier"] = float(multiplier)
    daily["run_order_index"] = int(RUN_ORDER.index((multiplier, version)))
    for name, frame in list(frames.items()):
        frame = frame.copy()
        if not frame.empty:
            frame["stage"] = STAGE_LABEL
            frame["model_tag"] = MODEL_TAG
            frame["line_id"] = LINE_ID
            frame["slippage_multiplier"] = float(multiplier)
            frame["run_order_index"] = int(RUN_ORDER.index((multiplier, version)))
        frames[name] = frame
    return daily, frames


def _token(multiplier: float) -> str:
    return f"{multiplier:g}x".replace(".", "p")


def _save_arm(
    multiplier: float,
    version: str,
    daily: pd.DataFrame,
    frames: dict[str, pd.DataFrame],
    closed: pd.DataFrame,
) -> None:
    prefix = f"{OUTPUT_PREFIX}_{_token(multiplier)}_{version}"
    daily.to_csv(
        OUT / f"{prefix}_daily_{MODEL_TAG}.csv.gz",
        index=False,
        encoding="utf-8-sig",
    )
    if not closed.empty:
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


def _summary_row(
    multiplier: float,
    version: str,
    daily: pd.DataFrame,
    frames: dict[str, pd.DataFrame],
    metadata: dict[str, Any],
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    closed = stage001.source._closed_lots(frames, metadata)
    curve = stage001.source.s006.base._curve_for_metrics(daily, version)
    row = stage001.source.s006._summarize_curve(curve)
    realized = pd.to_numeric(
        closed.get("realized_pnl", pd.Series(dtype=float)), errors="coerce"
    ).dropna()
    row.update(
        {
            "stage": STAGE_LABEL,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "requested_start_month": stage001.START_MONTH,
            "slippage_multiplier": float(multiplier),
            "run_order_index": int(RUN_ORDER.index((multiplier, version))),
            "closed_lot_count": int(len(realized)),
            "closed_lot_win_rate_pct": (
                float((realized > 0.0).mean() * 100.0) if len(realized) else 0.0
            ),
        }
    )
    curve["stage"] = STAGE_LABEL
    curve["model_tag"] = MODEL_TAG
    curve["line_id"] = LINE_ID
    curve["slippage_multiplier"] = float(multiplier)
    return row, curve, closed


def _stress_rows(
    multiplier: float, daily_by_version: dict[str, pd.DataFrame]
) -> pd.DataFrame:
    result = stage001._stress(daily_by_version)
    result["stage"] = STAGE_LABEL
    result["model_tag"] = MODEL_TAG
    result["line_id"] = LINE_ID
    result["slippage_multiplier"] = float(multiplier)
    return result


def _metric(summary: pd.DataFrame, multiplier: float, version: str) -> dict[str, Any]:
    return summary[
        summary["slippage_multiplier"].eq(multiplier)
        & summary["version"].eq(version)
    ].iloc[0].to_dict()


def _window_map(stress: pd.DataFrame, multiplier: float, version: str) -> dict[str, float]:
    data = stress[
        stress["slippage_multiplier"].eq(multiplier)
        & stress["version"].eq(version)
    ]
    return {
        str(row["window"]): float(row["window_max_drawdown_pct"])
        for _, row in data.iterrows()
    }


def _paired_gates(summary: pd.DataFrame, stress: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for multiplier in COST_MULTIPLIERS:
        rows.append(
            _paired_gate_row(
                multiplier,
                _metric(summary, multiplier, A_VERSION),
                _metric(summary, multiplier, C_VERSION),
                _window_map(stress, multiplier, A_VERSION),
                _window_map(stress, multiplier, C_VERSION),
            )
        )
    return pd.DataFrame(rows)


def _canonical_daily_hash(frame: pd.DataFrame) -> str:
    data = frame.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    for column in CORE_DAILY_COLUMNS:
        data[column] = pd.to_numeric(data.get(column), errors="coerce").round(10)
    payload = data[["date", *CORE_DAILY_COLUMNS]].to_csv(
        index=False, float_format="%.10f", lineterminator="\n"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _compare_persisted_daily(reference_path: Path, fresh_path: Path) -> dict[str, Any]:
    reference_daily = pd.read_csv(reference_path, encoding="utf-8-sig")
    fresh_daily = pd.read_csv(fresh_path, encoding="utf-8-sig")
    reference_daily["date"] = pd.to_datetime(
        reference_daily["date"], errors="coerce"
    ).dt.normalize()
    fresh_daily["date"] = pd.to_datetime(
        fresh_daily["date"], errors="coerce"
    ).dt.normalize()
    merged = reference_daily[["date", *CORE_DAILY_COLUMNS]].merge(
        fresh_daily[["date", *CORE_DAILY_COLUMNS]],
        on="date",
        how="outer",
        suffixes=("_reference", "_fresh"),
        indicator=True,
    )
    missing_date_count = int(merged["_merge"].ne("both").sum())
    daily_max_abs = 0.0
    mismatch_cells = 0
    for column in CORE_DAILY_COLUMNS:
        left = pd.to_numeric(merged[f"{column}_reference"], errors="coerce")
        right = pd.to_numeric(merged[f"{column}_fresh"], errors="coerce")
        diff = (left - right).abs()
        daily_max_abs = max(
            daily_max_abs, float(diff.max()) if diff.notna().any() else 0.0
        )
        both_nan = left.isna() & right.isna()
        mismatch_cells += int((~both_nan & (diff.isna() | diff.gt(CORE_TOLERANCE))).sum())
    reference_hash = _canonical_daily_hash(reference_daily)
    fresh_hash = _canonical_daily_hash(fresh_daily)
    return {
        "reference_rows": int(len(reference_daily)),
        "fresh_rows": int(len(fresh_daily)),
        "missing_date_count": missing_date_count,
        "daily_mismatch_cell_count": int(mismatch_cells),
        "daily_max_abs_difference": float(daily_max_abs),
        "reference_core_daily_sha256": reference_hash,
        "fresh_core_daily_sha256": fresh_hash,
        "core_daily_hash_equal": bool(reference_hash == fresh_hash),
    }


def _reproduction_audit(summary: pd.DataFrame) -> pd.DataFrame:
    reference_summary = pd.read_csv(STAGE001_SUMMARY_PATH, encoding="utf-8-sig")
    rows: list[dict[str, Any]] = []
    for version in VERSIONS:
        reference_daily_path = (
            STAGE001_OUT
            / f"{stage001.OUTPUT_PREFIX}_{version}_daily_{stage001.MODEL_TAG}.csv.gz"
        )
        fresh_daily_path = (
            OUT
            / f"{OUTPUT_PREFIX}_{_token(1.0)}_{version}_daily_{MODEL_TAG}.csv.gz"
        )
        daily_comparison = _compare_persisted_daily(
            reference_daily_path, fresh_daily_path
        )
        reference_row = reference_summary[reference_summary["version"].eq(version)].iloc[0]
        current_row = summary[
            summary["version"].eq(version)
            & summary["slippage_multiplier"].eq(1.0)
        ].iloc[0]
        summary_diffs = []
        for column in CORE_SUMMARY_COLUMNS:
            summary_diffs.append(
                abs(float(reference_row[column]) - float(current_row[column]))
            )
        summary_max_abs = max(summary_diffs) if summary_diffs else 0.0
        rows.append(
            {
                "version": version,
                "reference_daily_path": str(reference_daily_path),
                "fresh_daily_path": str(fresh_daily_path),
                **daily_comparison,
                "summary_max_abs_difference": float(summary_max_abs),
                "reproduction_pass": bool(
                    daily_comparison["missing_date_count"] == 0
                    and daily_comparison["daily_mismatch_cell_count"] == 0
                    and daily_comparison["daily_max_abs_difference"] <= CORE_TOLERANCE
                    and summary_max_abs <= CORE_TOLERANCE
                    and daily_comparison["core_daily_hash_equal"]
                ),
            }
        )
    return pd.DataFrame(rows)


def _pilot_semantics_pass(pilot: pd.DataFrame) -> bool:
    all_rows = pilot[pilot["sample"].astype(str).eq("all")]
    if len(all_rows) != len(COST_MULTIPLIERS):
        return False
    return bool(
        (pd.to_numeric(all_rows["rows"], errors="coerce") > 0).all()
        and pd.to_numeric(all_rows["after_not_one_count"], errors="coerce").eq(0).all()
        and pd.to_numeric(all_rows["below_drawdown_trigger_count"], errors="coerce").eq(0).all()
        and pd.to_numeric(all_rows["above_active_limit_count"], errors="coerce").eq(0).all()
    )


def _plot(curves: pd.DataFrame) -> None:
    labels = {A_VERSION: "A current C9", C_VERSION: "C Stage013"}
    colors = {A_VERSION: "#111827", C_VERSION: "#0f766e"}
    fig, axes = plt.subplots(2, len(COST_MULTIPLIERS), figsize=(18, 9), sharex="col")
    for column, multiplier in enumerate(COST_MULTIPLIERS):
        subset = curves[curves["slippage_multiplier"].eq(multiplier)]
        for version, group in subset.groupby("version", sort=False):
            group = group.sort_values("date").copy()
            dates = pd.to_datetime(group["date"], errors="coerce")
            equity = pd.to_numeric(group["account_equity_for_metrics"], errors="coerce").ffill()
            axes[0, column].plot(
                dates,
                equity,
                label=labels.get(version, version),
                color=colors.get(version),
                linewidth=1.0,
            )
            axes[1, column].plot(
                dates,
                stage001.source.s006.base._drawdown_pct(equity),
                label=labels.get(version, version),
                color=colors.get(version),
                linewidth=0.9,
            )
        axes[0, column].axhline(stage001.CAPITAL, color="#64748b", linestyle="--", linewidth=0.7)
        axes[0, column].set_title(f"{multiplier:g}x slippage: equity")
        axes[1, column].set_title(f"{multiplier:g}x slippage: drawdown")
        axes[0, column].grid(True, alpha=0.22)
        axes[1, column].grid(True, alpha=0.22)
        axes[0, column].legend(fontsize=8)
        axes[1, column].legend(fontsize=8)
    axes[0, 0].set_ylabel("account equity")
    axes[1, 0].set_ylabel("drawdown %")
    fig.suptitle("Stage005 frozen Stage013 true-engine slippage stress")
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=170, bbox_inches="tight")
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    stress: pd.DataFrame,
    pairs: pd.DataFrame,
    cost_audit: pd.DataFrame,
    reproduction: pd.DataFrame,
    pilot: pd.DataFrame,
    ai_parity: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    REPORT_PATH.write_text(
        f"""# Stage005 Stage013 真实引擎成本与执行压力

- 生成时间：`{decision['generated_at']}`
- 决策：`{decision['decision']}`
- 成本实现：引擎初始化前逐合约缩放单位滑点，逐笔进入每日净损益并反馈后续权益/手数/账户状态。
- 1x Stage001 复现：`{decision['stage001_reproduction_ok']}`
- 成本元数据语义：`{decision['cost_metadata_semantics_ok']}`
- AI/Stage013 执行语义：`{decision['strategy_semantics_ok']}`
- 三档绩效硬门：`{decision['all_cost_performance_gates_pass']}`
- 独立 review：待完成。

## 同成本 A/C 硬门

{pairs.to_markdown(index=False)}

## 全周期

{summary.to_markdown(index=False)}

## 压力窗口

{stress.to_markdown(index=False)}

## 滑点元数据

{cost_audit.to_markdown(index=False)}

## Stage001 复现

{reproduction.to_markdown(index=False)}

## Stage013 事件

{pilot.to_markdown(index=False)}

## AI 一致性

{ai_parity.to_markdown(index=False)}
""",
        encoding="utf-8",
    )


def _lineage() -> dict[str, Any]:
    paths = {
        "stage005_tool": Path(__file__).resolve(),
        "stage001_tool": Path(stage001.__file__).resolve(),
        "stage001_summary": STAGE001_SUMMARY_PATH,
        "official_ai": OFFICIAL_LIVE_AI_ELIGIBILITY_PATH,
        "vnpy_portfolio_backtesting": ROOT
        / ".py311"
        / "lib"
        / "python3.11"
        / "site-packages"
        / "vnpy_portfoliostrategy"
        / "backtesting.py",
    }
    result: dict[str, Any] = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S CST"),
        "run_order": [
            {"slippage_multiplier": multiplier, "version": version}
            for multiplier, version in RUN_ORDER
        ],
        "inputs": {},
    }
    for name, path in paths.items():
        result["inputs"][name] = {
            "path": str(path),
            "sha256": _sha256(path),
            "bytes": int(path.stat().st_size),
        }
    return result


def _manifest() -> pd.DataFrame:
    rows = []
    for path in sorted(OUT.iterdir()):
        if not path.is_file() or path == MANIFEST_PATH:
            continue
        rows.append(
            {
                "file": path.name,
                "bytes": int(path.stat().st_size),
                "sha256": _sha256(path),
            }
        )
    return pd.DataFrame(rows)


def build() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    base_metadata = stage001.source._metadata()
    base_slippage_hash_before = _mapping_sha256(base_metadata["slippages"])
    a_eligibility, a_path = _eligibility(stage001.A_STRATEGY, A_VERSION, A_VERSION)
    c_eligibility, c_path = _eligibility(stage001.C_STRATEGY, C_VERSION, C_VERSION)
    eligibility = {A_VERSION: a_eligibility, C_VERSION: c_eligibility}

    scaled_by_multiplier: dict[float, dict[str, Any]] = {}
    profile_by_key: dict[tuple[float, str], dict[str, Any]] = {}
    cost_audits: list[dict[str, Any]] = []
    for multiplier in COST_MULTIPLIERS:
        scaled, audit = _scaled_metadata(base_metadata, multiplier)
        scaled_by_multiplier[multiplier] = scaled
        profile_by_key[(multiplier, A_VERSION)] = stage001._a_profile(scaled, a_path)
        profile_by_key[(multiplier, C_VERSION)] = stage001._c_profile(scaled, c_path)
        cost_audits.append(audit)

    daily_by_key: dict[tuple[float, str], pd.DataFrame] = {}
    frames_by_key: dict[tuple[float, str], dict[str, pd.DataFrame]] = {}
    summary_rows: list[dict[str, Any]] = []
    curves: list[pd.DataFrame] = []
    for multiplier, version in RUN_ORDER:
        metadata = scaled_by_multiplier[multiplier]
        daily, frames = _run_arm(
            metadata, profile_by_key[(multiplier, version)], version, multiplier
        )
        row, curve, closed = _summary_row(
            multiplier, version, daily, frames, metadata
        )
        _save_arm(multiplier, version, daily, frames, closed)
        daily_by_key[(multiplier, version)] = daily
        frames_by_key[(multiplier, version)] = frames
        summary_rows.append(row)
        curves.append(curve)

    summary = pd.DataFrame(summary_rows).sort_values(
        ["slippage_multiplier", "version"]
    ).reset_index(drop=True)
    curve_frame = pd.concat(curves, ignore_index=True, sort=False)
    stress = pd.concat(
        [
            _stress_rows(
                multiplier,
                {
                    version: daily_by_key[(multiplier, version)]
                    for version in VERSIONS
                },
            )
            for multiplier in COST_MULTIPLIERS
        ],
        ignore_index=True,
        sort=False,
    )
    pairs = _paired_gates(summary, stress)

    pilot_parts = []
    ai_usage_parts = []
    for multiplier in COST_MULTIPLIERS:
        pilot = stage001._pilot_audit(frames_by_key[(multiplier, C_VERSION)])
        pilot["slippage_multiplier"] = float(multiplier)
        pilot_parts.append(pilot)
        usage = stage001.source.s006._ai_usage_audit(
            {
                version: frames_by_key[(multiplier, version)]
                for version in VERSIONS
            }
        )
        usage["slippage_multiplier"] = float(multiplier)
        ai_usage_parts.append(usage)
    pilot = pd.concat(pilot_parts, ignore_index=True, sort=False)
    ai_usage = pd.concat(ai_usage_parts, ignore_index=True, sort=False)

    ai_parity = stage001._ai_parity(eligibility)
    ai_parity["all_cost_multipliers"] = "/".join(
        f"{item:g}x" for item in COST_MULTIPLIERS
    )
    reproduction = _reproduction_audit(summary)
    base_slippage_hash_after = _mapping_sha256(base_metadata["slippages"])
    for audit in cost_audits:
        audit["base_metadata_hash_before"] = base_slippage_hash_before
        audit["base_metadata_hash_after"] = base_slippage_hash_after
        audit["base_metadata_unmodified"] = bool(
            base_slippage_hash_before == base_slippage_hash_after
        )
    cost_audit = pd.DataFrame(cost_audits)

    cost_metadata_ok = bool(
        cost_audit["ratio_error_count"].eq(0).all()
        and cost_audit["missing_symbol_count"].eq(0).all()
        and cost_audit["base_metadata_unmodified"].all()
    )
    ai_ok = bool(ai_parity["all_normalized_equal"].all())
    pilot_ok = _pilot_semantics_pass(pilot)
    reproduction_ok = bool(reproduction["reproduction_pass"].all())
    performance_ok = bool(pairs["performance_gate_pass"].all())
    strategy_semantics_ok = bool(ai_ok and pilot_ok)
    decision = {
        "stage": STAGE_LABEL,
        "stage_id": STAGE_ID,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S CST"),
        "cost_multipliers": list(COST_MULTIPLIERS),
        "stage001_reproduction_ok": reproduction_ok,
        "cost_metadata_semantics_ok": cost_metadata_ok,
        "ai_parity_ok": ai_ok,
        "pilot_semantics_ok": pilot_ok,
        "strategy_semantics_ok": strategy_semantics_ok,
        "all_cost_performance_gates_pass": performance_ok,
        "paired_gates": pairs.to_dict("records"),
        "decision": (
            "stage005_cost_execution_pass_pending_independent_review"
            if reproduction_ok
            and cost_metadata_ok
            and strategy_semantics_ok
            and performance_ok
            else "stage005_fail_close_no_parameter_rescue"
        ),
        "overfit_before": "no: frozen strategy under predeclared monotonic cost stress",
        "overfit_after": "pending_independent_review",
        "continue_value_before": "yes: true-engine costs feed equity, sizing, and Stage013 state",
        "continue_value_after": "pending_independent_review",
    }

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    stress.to_csv(STRESS_PATH, index=False, encoding="utf-8-sig")
    pairs.to_csv(PAIR_PATH, index=False, encoding="utf-8-sig")
    cost_audit.to_csv(COST_AUDIT_PATH, index=False, encoding="utf-8-sig")
    reproduction.to_csv(REPRO_PATH, index=False, encoding="utf-8-sig")
    pilot.to_csv(PILOT_AUDIT_PATH, index=False, encoding="utf-8-sig")
    ai_parity.to_csv(AI_PARITY_PATH, index=False, encoding="utf-8-sig")
    ai_usage.to_csv(AI_USAGE_PATH, index=False, encoding="utf-8-sig")
    curve_frame.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(
        json.dumps(
            stage001.source.s006.base._json_safe(decision),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    LINEAGE_PATH.write_text(
        json.dumps(_lineage(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _plot(curve_frame)
    _write_report(
        summary,
        stress,
        pairs,
        cost_audit,
        reproduction,
        pilot,
        ai_parity,
        decision,
    )
    _manifest().to_csv(MANIFEST_PATH, index=False, encoding="utf-8-sig")
    return {
        "summary": summary,
        "stress": stress,
        "pairs": pairs,
        "cost_audit": cost_audit,
        "reproduction": reproduction,
        "pilot": pilot,
        "decision": decision,
    }


if __name__ == "__main__":
    result = build()
    print(result["summary"].to_string(index=False))
    print(result["pairs"].to_string(index=False))
    print(
        json.dumps(
            stage001.source.s006.base._json_safe(result["decision"]),
            ensure_ascii=False,
            indent=2,
        )
    )
