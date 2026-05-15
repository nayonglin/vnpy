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
MODEL_TAG: str = "stage279_profit_lock_trend_relaxed_prev2day_engine_screen_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage279_profit_lock_trend_relaxed_prev2day_engine_screen"


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

    relaxed = dict(official)
    relaxed.update(
        {
            "enable_profit_lock_trend_relaxed_prev2day_stop": True,
            "profit_lock_trend_relax_trigger_pct": 0.05,
            "profit_lock_trend_relax_ma_fast": 20,
            "profit_lock_trend_relax_ma_slow": 40,
            "profit_lock_trend_relax_slope_days": 3,
        }
    )

    return [
        Variant("A_stage78_1_current", "Current official Stage78-1 exits.", official),
        Variant(
            "C_locked_trend_relaxed_prev2day",
            "Skip prev2day_stop only when profit lock >=5% and MA20/MA40 trend remains aligned.",
            relaxed,
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
    engine, _, stats = run_backtest(
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
    strategy = getattr(engine, "strategy", None)
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
        "relaxed_prev2day_skip_count": int(
            getattr(strategy, "profit_lock_trend_relaxed_prev2day_skip_count", 0) if strategy else 0
        ),
    }


def _build_comparison(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for window_name, group in summary.groupby("window_name"):
        base_rows = group[group["variant"].eq("A_stage78_1_current")]
        candidate_rows = group[group["variant"].eq("C_locked_trend_relaxed_prev2day")]
        if base_rows.empty or candidate_rows.empty:
            continue
        base = base_rows.iloc[0]
        candidate = candidate_rows.iloc[0]
        rows.append(
            {
                "candidate": "C_locked_trend_relaxed_prev2day",
                "window_name": window_name,
                "end_minus_a": _safe_float(candidate["end_balance"]) - _safe_float(base["end_balance"]),
                "return_minus_a_pct": _safe_float(candidate["total_return_pct"]) - _safe_float(base["total_return_pct"]),
                "dd_minus_a_pct": _safe_float(candidate["max_dd_percent"]) - _safe_float(base["max_dd_percent"]),
                "sharpe_minus_a": _safe_float(candidate["sharpe_ratio"]) - _safe_float(base["sharpe_ratio"]),
                "trade_count_minus_a": int(candidate["total_trade_count"]) - int(base["total_trade_count"]),
                "relaxed_prev2day_skip_count": int(candidate["relaxed_prev2day_skip_count"]),
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
    if comparison.empty:
        return {"pass_engine_screen": False, "next_step": "reject_missing_comparison"}

    full = comparison[comparison["window_name"].eq("full_2020_2026")].iloc[0].to_dict()
    since_2026 = comparison[comparison["window_name"].eq("since_2026")].iloc[0].to_dict()
    win_count = int((comparison["end_minus_a"] > 0).sum())
    dd_ok_count = int((comparison["dd_minus_a_pct"] >= -2.0).sum())
    weak = comparison[comparison["window_name"].isin(["stage269_aug_nov_2025", "stage131_q2022_4_proxy_252d"])]
    weak_ok_count = int(((weak["end_minus_a"] >= -100_000.0) & (weak["dd_minus_a_pct"] >= -5.0)).sum())
    total_skip_count = int(comparison["relaxed_prev2day_skip_count"].sum())
    pass_gate = bool(
        total_skip_count > 0
        and float(full["end_minus_a"]) >= 0.0
        and float(full["dd_minus_a_pct"]) >= -2.0
        and float(since_2026["end_minus_a"]) >= -50_000.0
        and win_count >= 4
        and dd_ok_count >= 5
        and weak_ok_count >= 2
    )
    return {
        "baseline_version": OFFICIAL_STAGE78_VERSION,
        "official_manifest_capital": build_official_stage78_manifest().get("capital"),
        "candidate": "C_locked_trend_relaxed_prev2day",
        "total_relaxed_prev2day_skip_count": total_skip_count,
        "window_win_count": win_count,
        "dd_ok_count": dd_ok_count,
        "weak_ok_count": weak_ok_count,
        "full_end_minus_a": float(full["end_minus_a"]),
        "full_dd_minus_a_pct": float(full["dd_minus_a_pct"]),
        "full_sharpe_minus_a": float(full["sharpe_minus_a"]),
        "since_2026_end_minus_a": float(since_2026["end_minus_a"]),
        "pass_engine_screen": pass_gate,
        "next_step": "stage280_full_robustness" if pass_gate else "reject_do_not_promote",
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
    report = f"""# Stage279 锁盈趋势态放宽 prev2day_stop 引擎小屏

## 假设

Stage278 显示，固定盈利锁本身不是主要退出源；真正可能过早截断趋势的是 `prev2day_stop + 已锁盈状态` 的组合。本阶段不调盈利锁百分比，只验证一个结构化开关：

- 当任一持仓层最大收盘浮盈 `>=5%`；
- 且 MA20/MA40 保持同向趋势；
- 且 MA20 过去3日仍向趋势方向推进；
- 当天跳过 `prev2day_stop`，但固定盈利锁、base stop、MA stop、换月等其它退出不关闭。

## A/C

- A：当前正式 Stage78-1。
- C：A + `enable_profit_lock_trend_relaxed_prev2day_stop=True`。
- B：该模块不能独立成完整策略，不单独评估。

## 预声明闸门

- full window C 期末权益不低于 A。
- full window 最大回撤恶化不超过 `2pp`。
- 2026 独立启动不低于 A `50,000`。
- 6个窗口至少4个窗口期末权益胜出。
- 6个窗口至少5个窗口最大回撤恶化不超过 `2pp`。
- 2个弱窗口都不能明显恶化：`end_minus_a >= -100,000` 且 DD 恶化不超过 `5pp`。

## 判定

```json
{json.dumps(decision, ensure_ascii=False, indent=2)}
```

## 原始结果

{_format_table(summary, ["variant", "window_name", "end_balance", "total_return_pct", "max_dd_percent", "sharpe_ratio", "total_slippage", "total_trade_count", "win_ratio_pct", "relaxed_prev2day_skip_count"])}

## C 相对 A

{_format_table(comparison, ["window_name", "end_minus_a", "return_minus_a_pct", "dd_minus_a_pct", "sharpe_minus_a", "trade_count_minus_a", "relaxed_prev2day_skip_count", "a_end_balance", "candidate_end_balance", "a_max_dd_percent", "candidate_max_dd_percent"])}

## 结论边界

- 本阶段是完整组合引擎小屏，但不是最终稳健性验证。
- 若 `pass_engine_screen=false`，不进入正式参数，不进影子盘。
- 若 `pass_engine_screen=true`，下一步仍需起始年份、季度冷启动、短窗口、滑点压力和逐笔集中度审查。

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
