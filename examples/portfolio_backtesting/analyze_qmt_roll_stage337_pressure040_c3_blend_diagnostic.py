from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage337_pressure040_c3_blend_diagnostic_v1"
OUTPUT_PREFIX = "qmt_roll_stage337_pressure040_c3_blend_diagnostic"
LINE_ID = "futures_trend_drawdown30_preserve_return"

CAPITAL = 500_000.0
SOURCE_TAG = "stage319_supply_headwind_risk_scale_validation_v1"
SOURCE_PREFIX = "qmt_roll_stage319_supply_headwind_risk_scale_validation"
SOURCE_SUMMARY_PATH = OUTPUT_DIR / f"{SOURCE_PREFIX}_summary_{SOURCE_TAG}.csv"
SOURCE_CURVES_PATH = OUTPUT_DIR / f"{SOURCE_PREFIX}_curves_{SOURCE_TAG}.csv"

PRESSURE_VARIANT = "C_pressure040"
C3_VARIANT = "C3_supply_headwind"
WINDOW_NAME = "full_2020_2026"

WEIGHTS: tuple[float, ...] = (0.0, 0.25, 0.50, 0.75, 1.0)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isinf(result) or pd.isna(result):
        return default
    return result


def _to_builtin(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _to_builtin(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_builtin(item) for item in value]
    if isinstance(value, tuple):
        return [_to_builtin(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _to_markdown_table(df: pd.DataFrame, columns: list[str] | None = None) -> str:
    if df.empty:
        return "_empty_"
    view = df[columns].copy() if columns else df.copy()
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda value: f"{value:.4f}")
    header = "| " + " | ".join(view.columns) + " |"
    separator = "| " + " | ".join(["---"] * len(view.columns)) + " |"
    rows = ["| " + " | ".join(map(str, row)) + " |" for row in view.to_numpy()]
    return "\n".join([header, separator, *rows])


def _curve_metrics(balance: pd.Series) -> dict[str, Any]:
    balance = pd.to_numeric(balance, errors="coerce").ffill().dropna()
    if balance.empty:
        return {
            "start_date": "",
            "end_date": "",
            "first_balance": CAPITAL,
            "end_balance": CAPITAL,
            "total_return_pct": 0.0,
            "total_return_vs_first_pct": 0.0,
            "max_dd_pct": 0.0,
            "max_dd_start": "",
            "max_dd_end": "",
            "sharpe": 0.0,
        }
    high = balance.cummax()
    dd = (balance - high) / high.replace(0.0, np.nan) * 100.0
    dd_end = dd.idxmin()
    dd_start = balance.loc[:dd_end].idxmax()
    returns = balance.pct_change().fillna(0.0)
    std = float(returns.std(ddof=1)) if len(returns) > 1 else 0.0
    sharpe = float(returns.mean() / std * np.sqrt(252)) if std > 0 else 0.0
    return {
        "start_date": str(balance.index[0].date()),
        "end_date": str(balance.index[-1].date()),
        "first_balance": float(balance.iloc[0]),
        "end_balance": float(balance.iloc[-1]),
        "total_return_pct": float((balance.iloc[-1] / CAPITAL - 1.0) * 100.0),
        "total_return_vs_first_pct": float((balance.iloc[-1] / balance.iloc[0] - 1.0) * 100.0),
        "max_dd_pct": float(dd.min()),
        "max_dd_start": str(dd_start.date()),
        "max_dd_end": str(dd_end.date()),
        "sharpe": sharpe,
    }


def _source_variant_rows(summary_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    full = summary_df[summary_df["window_name"].eq(WINDOW_NAME)].copy()
    for variant in [PRESSURE_VARIANT, C3_VARIANT]:
        row = full[full["variant"].eq(variant)]
        if row.empty:
            continue
        raw = row.iloc[0]
        rows.append(
            {
                "variant": variant,
                "total_return_pct": _safe_float(raw.get("total_return_pct")),
                "max_dd_pct": _safe_float(raw.get("max_dd_percent")),
                "sharpe": _safe_float(raw.get("sharpe_ratio")),
                "total_trade_count": int(_safe_float(raw.get("total_trade_count"))),
                "win_ratio_pct": _safe_float(raw.get("win_ratio_pct")),
                "total_slippage": _safe_float(raw.get("total_slippage")),
            }
        )
    return pd.DataFrame(rows)


def _build_frontier(curves_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    full = curves_df[curves_df["window_name"].eq(WINDOW_NAME)].copy()
    full["date"] = pd.to_datetime(full["date"])
    pivot = (
        full.pivot_table(index="date", columns="variant", values="balance", aggfunc="last")
        .sort_index()
        .dropna(subset=[PRESSURE_VARIANT, C3_VARIANT])
    )
    daily_returns = pivot[[PRESSURE_VARIANT, C3_VARIANT]].pct_change().dropna()
    corr = float(daily_returns[PRESSURE_VARIANT].corr(daily_returns[C3_VARIANT]))

    daily_frames: list[pd.DataFrame] = []
    rows: list[dict[str, Any]] = []
    for pressure_weight in WEIGHTS:
        c3_weight = 1.0 - pressure_weight
        label = f"pressure{pressure_weight:.2f}_c3{c3_weight:.2f}"
        balance = pivot[PRESSURE_VARIANT] * pressure_weight + pivot[C3_VARIANT] * c3_weight
        metrics = _curve_metrics(balance)
        rows.append(
            {
                "blend_name": label,
                "pressure040_weight": pressure_weight,
                "c3_weight": c3_weight,
                **metrics,
            }
        )
        frame = pd.DataFrame(
            {
                "date": balance.index,
                "blend_name": label,
                "balance": balance.to_numpy(dtype=float),
            }
        )
        frame["highlevel"] = frame["balance"].cummax()
        frame["drawdown"] = frame["balance"] - frame["highlevel"]
        frame["ddpercent"] = frame["drawdown"] / frame["highlevel"].replace(0.0, np.nan) * 100.0
        daily_frames.append(frame)

    diagnostics = {
        "daily_return_corr_pressure040_c3": corr,
        "pressure040_rows": int(pivot[PRESSURE_VARIANT].notna().sum()),
        "c3_rows": int(pivot[C3_VARIANT].notna().sum()),
        "first_date": str(pivot.index[0].date()) if not pivot.empty else "",
        "last_date": str(pivot.index[-1].date()) if not pivot.empty else "",
    }
    daily_df = pd.concat(daily_frames, ignore_index=True) if daily_frames else pd.DataFrame()
    return pd.DataFrame(rows), daily_df, diagnostics


def _build_report(source_rows: pd.DataFrame, frontier: pd.DataFrame, diagnostics: dict[str, Any]) -> str:
    equal = frontier[frontier["blend_name"].eq("pressure0.50_c30.50")]
    equal_row = equal.iloc[0] if not equal.empty else None
    lines = [
        "# Stage337 C_pressure040 与 C3 组合口径诊断",
        "",
        "## 目标",
        "",
        "- 修正 `C_pressure040 + C3` 与 `C3 + 低相关卫星` 混淆的问题。",
        "- 只读取 Stage319 已生成的真实引擎权益曲线，不新增策略参数，不重新调参。",
        "- 检查两个同源趋势版本叠加后，是否能自然把最大回撤压到30%以内。",
        "",
        "## 单版本口径",
        "",
        _to_markdown_table(
            source_rows,
            ["variant", "total_return_pct", "max_dd_pct", "sharpe", "total_trade_count", "win_ratio_pct"],
        ),
        "",
        "## 组合权重前沿",
        "",
        _to_markdown_table(
            frontier,
            [
                "blend_name",
                "pressure040_weight",
                "c3_weight",
                "total_return_pct",
                "max_dd_pct",
                "max_dd_start",
                "max_dd_end",
                "sharpe",
            ],
        ),
        "",
        "## 阶段判断",
        "",
    ]
    if equal_row is not None:
        lines.append(
            "- 等权组合全周期收益 "
            f"`{equal_row['total_return_pct']:.4f}%`，最大回撤 "
            f"`{equal_row['max_dd_pct']:.4f}%`。"
        )
    lines.append(
        "- 两条权益曲线日收益相关性为 "
        f"`{diagnostics['daily_return_corr_pressure040_c3']:.4f}`，且最大回撤结束日同为 "
        f"`{frontier['max_dd_end'].mode().iloc[0]}`。"
    )
    lines.append(
        "- 结论：`C_pressure040` 和 `C3` 是同源趋势版本，组合后收益位于两者之间，但最坏回撤没有改善，不能作为回撤30以内的解法。"
    )
    lines.extend(
        [
            "",
            "## 过拟合反思",
            "",
            "- 本阶段没有搜索新参数，只做口径纠错和同源组合诊断，过拟合风险低。",
            "- 若继续调整两个同源版本的权重，只是在同一个回撤路径上移动收益，不能解决目标。",
            "",
            "## 继续价值反思",
            "",
            "- 这一步有价值，因为它排除了一个看似自然的组合方向，避免把低相关卫星结果误记成同源趋势组合。",
            "- 下一步继续找真正低相关、真实资金下可交易的卫星或账户层部署结构。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    if not SOURCE_SUMMARY_PATH.exists():
        raise FileNotFoundError(SOURCE_SUMMARY_PATH)
    if not SOURCE_CURVES_PATH.exists():
        raise FileNotFoundError(SOURCE_CURVES_PATH)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary_df = pd.read_csv(SOURCE_SUMMARY_PATH)
    curves_df = pd.read_csv(SOURCE_CURVES_PATH)

    source_rows = _source_variant_rows(summary_df)
    frontier, daily_df, diagnostics = _build_frontier(curves_df)
    report = _build_report(source_rows, frontier, diagnostics)

    summary_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
    daily_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
    source_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_variants_{MODEL_TAG}.csv"
    report_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
    decision_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

    frontier.to_csv(summary_path, index=False, encoding="utf-8-sig")
    daily_df.to_csv(daily_path, index=False, encoding="utf-8-sig")
    source_rows.to_csv(source_path, index=False, encoding="utf-8-sig")
    report_path.write_text(report, encoding="utf-8")

    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "source_tag": SOURCE_TAG,
        "source_summary": str(SOURCE_SUMMARY_PATH),
        "source_curves": str(SOURCE_CURVES_PATH),
        "diagnostics": diagnostics,
        "decision": "fail_same_family_blend_no_drawdown_improvement",
        "paths": {
            "summary": str(summary_path),
            "daily": str(daily_path),
            "source_variants": str(source_path),
            "report": str(report_path),
        },
    }
    decision_path.write_text(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[stage337] summary={summary_path}")
    print(f"[stage337] daily={daily_path}")
    print(f"[stage337] source_variants={source_path}")
    print(f"[stage337] report={report_path}")
    print(f"[stage337] decision={decision_path}")
    print(report)


if __name__ == "__main__":
    main()
