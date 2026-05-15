from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from qmt_roll_official_stage78_config import (
    OFFICIAL_STAGE78_CAPITAL,
    OFFICIAL_STAGE78_VERSION,
    build_official_stage78_manifest,
    build_official_stage78_overrides,
)
from qmt_universe import END_DT, START_DT
from run_qmt_roll_backtest import run_backtest
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"
MODEL_TAG: str = "stage274_profit_lock_engine_falsification_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage274_profit_lock_engine_falsification"


@dataclass(frozen=True)
class Variant:
    name: str
    description: str
    overrides: dict[str, Any]


@dataclass(frozen=True)
class Window:
    name: str
    start: datetime
    end: datetime


def _windows() -> list[Window]:
    return [
        Window("full_2020_2026", START_DT, END_DT),
        Window("since_2022", datetime(2022, 1, 1), END_DT),
        Window("since_2025", datetime(2025, 1, 1), END_DT),
        Window("since_2026", datetime(2026, 1, 1), END_DT),
        Window("stage269_aug_nov_2025", datetime(2025, 8, 1), datetime(2025, 11, 30)),
        Window("stage131_q2022_4_proxy_252d", datetime(2022, 10, 1), datetime(2023, 9, 30)),
    ]


def _variants() -> list[Variant]:
    official = build_official_stage78_overrides()

    scale_165 = dict(official)
    scale_165["profit_lock_tiers"] = "0.30:0.294,0.20:0.196,0.10:0.098,0.05:0.049,0.03:0.0165,0.02:0.0016"

    two_segment = dict(official)
    two_segment["profit_lock_tiers"] = "0.30:0.270,0.20:0.180,0.10:0.090,0.05:0.015,0.03:0.009,0.02:0.006"

    return [
        Variant("A_stage78_1_current", "Current Stage78-1 profit lock tiers.", official),
        Variant(
            "C_scale_current_1_65",
            "Stage273 event-level robust-best: scale current locks by 1.65 with lock <= 98% trigger cap.",
            scale_165,
        ),
        Variant(
            "D_two_segment_30_90",
            "Stage273 conservative no-negative-year event candidate: low tiers retain 30%, high tiers retain 90%.",
            two_segment,
        ),
    ]


def _safe_float(value: Any) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except Exception:
        return 0.0


def _run_one(variant: Variant, window: Window) -> dict[str, Any]:
    _, _, stats = run_backtest(
        risk_ratio=BASE_RISK_RATIO,
        strategy_overrides=variant.overrides,
        analysis_start=window.start,
        analysis_end=window.end,
        capital=OFFICIAL_STAGE78_CAPITAL,
        save_artifacts=False,
        include_start_year_sweep=False,
        file_prefix=f"{OUTPUT_PREFIX}_{variant.name}_{window.name}",
        chart_title=f"{variant.name} {window.name}",
    )
    return {
        "variant": variant.name,
        "variant_description": variant.description,
        "window_name": window.name,
        "analysis_start": window.start.date().isoformat(),
        "analysis_end": window.end.date().isoformat(),
        "end_balance": _safe_float(stats.get("end_balance")),
        "total_return_pct": _safe_float(stats.get("total_return")),
        "max_dd_percent": _safe_float(stats.get("max_ddpercent")),
        "sharpe_ratio": _safe_float(stats.get("sharpe_ratio")),
        "total_slippage": _safe_float(stats.get("total_slippage")),
        "total_commission": _safe_float(stats.get("total_commission")),
        "total_trade_count": int(stats.get("total_trade_count", 0) or 0),
        "win_ratio_pct": _safe_float(stats.get("win_ratio")),
    }


def _build_comparison(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for window_name, group in summary.groupby("window_name"):
        by_variant = {str(row["variant"]): row for row in group.to_dict("records")}
        base = by_variant.get("A_stage78_1_current")
        if not base:
            continue
        for candidate_name in ["C_scale_current_1_65", "D_two_segment_30_90"]:
            candidate = by_variant.get(candidate_name)
            if not candidate:
                continue
            rows.append(
                {
                    "candidate": candidate_name,
                    "window_name": window_name,
                    "end_minus_a": _safe_float(candidate["end_balance"]) - _safe_float(base["end_balance"]),
                    "return_minus_a_pct": _safe_float(candidate["total_return_pct"]) - _safe_float(base["total_return_pct"]),
                    "dd_minus_a_pct": _safe_float(candidate["max_dd_percent"]) - _safe_float(base["max_dd_percent"]),
                    "sharpe_minus_a": _safe_float(candidate["sharpe_ratio"]) - _safe_float(base["sharpe_ratio"]),
                    "trade_count_minus_a": int(candidate["total_trade_count"]) - int(base["total_trade_count"]),
                    "a_end_balance": _safe_float(base["end_balance"]),
                    "candidate_end_balance": _safe_float(candidate["end_balance"]),
                    "a_max_dd_percent": _safe_float(base["max_dd_percent"]),
                    "candidate_max_dd_percent": _safe_float(candidate["max_dd_percent"]),
                    "a_sharpe": _safe_float(base["sharpe_ratio"]),
                    "candidate_sharpe": _safe_float(candidate["sharpe_ratio"]),
                }
            )
    return pd.DataFrame(rows)


def _decision(comparison: pd.DataFrame) -> dict[str, Any]:
    decisions: dict[str, Any] = {}
    for candidate, group in comparison.groupby("candidate"):
        full = group[group["window_name"].eq("full_2020_2026")].iloc[0].to_dict()
        since_2026 = group[group["window_name"].eq("since_2026")].iloc[0].to_dict()
        win_count = int((group["end_minus_a"] > 0).sum())
        dd_ok_count = int((group["dd_minus_a_pct"] >= -2.0).sum())
        weak = group[group["window_name"].isin(["stage269_aug_nov_2025", "stage131_q2022_4_proxy_252d"])]
        weak_ok_count = int(((weak["end_minus_a"] >= -100_000.0) & (weak["dd_minus_a_pct"] >= -5.0)).sum())
        pass_gate = bool(
            float(full["end_minus_a"]) >= 0.0
            and float(full["dd_minus_a_pct"]) >= -2.0
            and float(since_2026["end_minus_a"]) >= -50_000.0
            and win_count >= 4
            and dd_ok_count >= 5
            and weak_ok_count >= 1
        )
        decisions[candidate] = {
            "pass_engine_gate": pass_gate,
            "window_win_count": win_count,
            "dd_ok_count": dd_ok_count,
            "weak_ok_count": weak_ok_count,
            "full_end_minus_a": float(full["end_minus_a"]),
            "full_dd_minus_a_pct": float(full["dd_minus_a_pct"]),
            "since_2026_end_minus_a": float(since_2026["end_minus_a"]),
            "next_step": "stage275_full_robustness" if pass_gate else "reject_do_not_promote",
        }
    return {
        "baseline_version": OFFICIAL_STAGE78_VERSION,
        "official_manifest_capital": build_official_stage78_manifest().get("capital"),
        "candidate_decisions": decisions,
        "any_pass_engine_gate": any(bool(item["pass_engine_gate"]) for item in decisions.values()),
    }


def _format_table(df: pd.DataFrame, columns: list[str]) -> str:
    if df.empty:
        return "- 无数据"
    return df[[column for column in columns if column in df.columns]].to_markdown(index=False)


def _write_report(
    *,
    summary: pd.DataFrame,
    comparison: pd.DataFrame,
    decision: dict[str, Any],
    paths: dict[str, Path],
) -> None:
    report = f"""# Stage274 盈利锁定候选组合引擎反证

## 设计

- A：Stage78-1 当前正式盈利锁定档位。
- C：Stage273 事件级 robust-best，当前档位整体放大约 1.65 倍。
- D：Stage273 更保守的 two-segment 候选，低档位保留30%，高档位保留90%。
- 本阶段不是正式晋级验证，而是反证事件级候选是否在组合引擎里仍然有效。

## 判定

```json
{json.dumps(decision, ensure_ascii=False, indent=2)}
```

## A/C/D 原始结果

{_format_table(summary, ["variant", "window_name", "end_balance", "total_return_pct", "max_dd_percent", "sharpe_ratio", "total_slippage", "total_trade_count", "win_ratio_pct"])}

## 候选相对A

{_format_table(comparison, ["candidate", "window_name", "end_minus_a", "return_minus_a_pct", "dd_minus_a_pct", "sharpe_minus_a", "trade_count_minus_a", "a_end_balance", "candidate_end_balance", "a_max_dd_percent", "candidate_max_dd_percent"])}

## 结论

- 只有通过 engine gate 的候选，才有资格进入 Stage275 全稳健性/滑点压力。
- 若失败，则 Stage273 的事件级最优只能视为样本内路径现象，不替换正式 78-1。

## 输出文件

- summary：`{paths["summary"].name}`
- comparison：`{paths["comparison"].name}`
- decision：`{paths["decision"].name}`
"""
    paths["report"].write_text(report, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for variant in _variants():
        for window in _windows():
            rows.append(_run_one(variant, window))

    summary = pd.DataFrame(rows)
    comparison = _build_comparison(summary)
    decision = _decision(comparison)

    paths = {
        "summary": OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv",
        "comparison": OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv",
        "decision": OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json",
        "report": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md",
    }
    summary.to_csv(paths["summary"], index=False, encoding="utf-8-sig")
    comparison.to_csv(paths["comparison"], index=False, encoding="utf-8-sig")
    paths["decision"].write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(summary=summary, comparison=comparison, decision=decision, paths=paths)

    print(json.dumps(decision, ensure_ascii=False, indent=2))
    print(f"report: {paths['report']}")


if __name__ == "__main__":
    main()
