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
MODEL_TAG: str = "stage272_profit_lock_low_tier_ablation_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage272_profit_lock_low_tier_ablation"


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
        Window("since_2021", datetime(2021, 1, 1), END_DT),
        Window("since_2022", datetime(2022, 1, 1), END_DT),
        Window("since_2023", datetime(2023, 1, 1), END_DT),
        Window("since_2024", datetime(2024, 1, 1), END_DT),
        Window("since_2025", datetime(2025, 1, 1), END_DT),
        Window("since_2026", datetime(2026, 1, 1), END_DT),
        Window("stage269_aug_nov_2025", datetime(2025, 8, 1), datetime(2025, 11, 30)),
        Window("stage131_q2022_4_proxy_252d", datetime(2022, 10, 1), datetime(2023, 9, 30)),
    ]


def _variants() -> list[Variant]:
    official = build_official_stage78_overrides()
    no_low_tiers = dict(official)
    no_low_tiers["profit_lock_tiers"] = "0.30:0.20,0.20:0.15,0.10:0.08,0.05:0.03"
    return [
        Variant("A_stage78_1_current", "Current Stage78-1 profit lock tiers.", official),
        Variant(
            "C_no_2_3pct_early_lock",
            "Keep 5/10/20/30 profit-lock tiers unchanged, remove 2% and 3% early-lock tiers.",
            no_low_tiers,
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
        candidate = by_variant.get("C_no_2_3pct_early_lock")
        if not base or not candidate:
            continue
        rows.append(
            {
                "window_name": window_name,
                "c_end_minus_a": _safe_float(candidate["end_balance"]) - _safe_float(base["end_balance"]),
                "c_return_minus_a_pct": _safe_float(candidate["total_return_pct"]) - _safe_float(base["total_return_pct"]),
                "c_dd_minus_a_pct": _safe_float(candidate["max_dd_percent"]) - _safe_float(base["max_dd_percent"]),
                "c_sharpe_minus_a": _safe_float(candidate["sharpe_ratio"]) - _safe_float(base["sharpe_ratio"]),
                "c_trade_count_minus_a": int(candidate["total_trade_count"]) - int(base["total_trade_count"]),
                "a_end_balance": _safe_float(base["end_balance"]),
                "c_end_balance": _safe_float(candidate["end_balance"]),
                "a_max_dd_percent": _safe_float(base["max_dd_percent"]),
                "c_max_dd_percent": _safe_float(candidate["max_dd_percent"]),
                "a_sharpe": _safe_float(base["sharpe_ratio"]),
                "c_sharpe": _safe_float(candidate["sharpe_ratio"]),
            }
        )
    return pd.DataFrame(rows)


def _decision(comparison: pd.DataFrame) -> dict[str, Any]:
    if comparison.empty:
        return {"promotion_decision": "fail_no_comparison"}

    full = comparison[comparison["window_name"].eq("full_2020_2026")].iloc[0].to_dict()
    since_2026 = comparison[comparison["window_name"].eq("since_2026")].iloc[0].to_dict()
    weak = comparison[comparison["window_name"].isin(["stage269_aug_nov_2025", "stage131_q2022_4_proxy_252d"])]
    start_years = comparison[comparison["window_name"].str.startswith("since_")]

    full_return_ok = float(full["c_return_minus_a_pct"]) >= -250.0
    full_dd_ok = float(full["c_dd_minus_a_pct"]) >= -2.0
    latest_ok = float(since_2026["c_end_minus_a"]) >= -50_000.0 and float(since_2026["c_dd_minus_a_pct"]) >= -5.0
    weak_ok_count = int(((weak["c_end_minus_a"] >= -100_000.0) & (weak["c_dd_minus_a_pct"] >= -5.0)).sum())
    start_year_win_count = int((start_years["c_end_minus_a"] > 0).sum())

    pass_minimal = bool(
        full_return_ok
        and full_dd_ok
        and latest_ok
        and weak_ok_count >= 1
        and start_year_win_count >= 3
    )
    return {
        "promotion_decision": "candidate_for_stage273_robustness" if pass_minimal else "fail_or_hold_no_promotion",
        "pass_minimal_gate": pass_minimal,
        "full_return_ok": full_return_ok,
        "full_dd_ok": full_dd_ok,
        "latest_2026_ok": latest_ok,
        "weak_ok_count": weak_ok_count,
        "start_year_win_count": start_year_win_count,
        "next_step": (
            "run_stage273_full_robustness_and_slippage"
            if pass_minimal
            else "stop_no_low_tier_candidate_or_keep_as_attribution_only"
        ),
    }


def _format_table(df: pd.DataFrame, columns: list[str]) -> str:
    if df.empty:
        return "- 无数据"
    view = df[[column for column in columns if column in df.columns]].copy()
    return view.to_markdown(index=False)


def _write_report(
    *,
    summary: pd.DataFrame,
    comparison: pd.DataFrame,
    decision: dict[str, Any],
    paths: dict[str, Path],
) -> None:
    report = f"""# Stage272 去掉低档位早锁 A/C 最小验证

## 设计

- A：Stage78-1 当前正式盈利锁定档位。
- C：保留 `5/10/20/30%` 档位，去掉 `2%->0.1%` 与 `3%->1%` 早锁档位。
- 本阶段不是参数搜索，只验证 Stage271 交易级归因暴露出的低档位疑点。
- 若 C 不通过，不继续围绕低档位小数阈值调参。

## 判定

```json
{json.dumps(decision, ensure_ascii=False, indent=2)}
```

## A/C 对比

{_format_table(comparison, ["window_name", "c_end_minus_a", "c_return_minus_a_pct", "c_dd_minus_a_pct", "c_sharpe_minus_a", "c_trade_count_minus_a", "a_end_balance", "c_end_balance", "a_max_dd_percent", "c_max_dd_percent"])}

## 原始结果

{_format_table(summary, ["variant", "window_name", "end_balance", "total_return_pct", "max_dd_percent", "sharpe_ratio", "total_trade_count", "win_ratio_pct"])}

## 结论

- 本阶段只决定是否值得进入 Stage273 的更完整稳健性/滑点验证。
- 即使通过，也不能直接替换正式 78-1。
- 若不通过，保留 Stage271 归因，不继续微调 `2%/3%` 小数阈值。

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
    manifest = build_official_stage78_manifest()
    decision["baseline_version"] = OFFICIAL_STAGE78_VERSION
    decision["official_manifest_capital"] = manifest.get("capital")

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
