from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import json
import math
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
sys.path.insert(0, str(PROJECT_DIR.resolve()))

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513  # noqa: E402
import analyze_qmt_roll_stage517_portfolio_margin_deleverage_frontier as s517  # noqa: E402
import analyze_qmt_roll_stage519_product_margin_cap_frontier as s519  # noqa: E402
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650  # noqa: E402


MODEL_TAG = "stage651_stage526_200k_dynamic_margin_gate_v1"
OUTPUT_PREFIX = "qmt_roll_stage651_stage526_200k_dynamic_margin_gate"
LINE_ID = "futures_trend_drawdown30_preserve_return"

ACCOUNT_200K = 200_000.0
BROKER_MARGIN_MULTIPLIER = float(s517.BROKER_MARGIN_MULTIPLIER)
COST_MULTIPLIERS: tuple[float, ...] = (1.0, 2.0, 3.0)
BASELINE_VARIANT = "stage526_200k_allin_r080_pc25_maxpos4"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
POSITIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_{MODEL_TAG}.csv"
PRODUCT_MARGIN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_margin_{MODEL_TAG}.csv"
ROLLING_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rolling_holding_{MODEL_TAG}.csv"
EVENT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_days_{MODEL_TAG}.csv"
TRADE_USAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_usage_{MODEL_TAG}.csv"
CANDIDATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidates_{MODEL_TAG}.csv"
CANDIDATE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_candidate_summary_{MODEL_TAG}.csv"
ENTRY_RISK_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


@dataclass(frozen=True)
class DynamicVariant:
    capital: s650.CapitalVariant
    overrides: dict[str, Any]
    profile: str


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _entry_reduce_overrides(usage_ratio: float) -> dict[str, Any]:
    exchange_margin_usage_ratio = float(usage_ratio) / BROKER_MARGIN_MULTIPLIER
    return {
        "enable_incremental_margin_budget_gate": True,
        "incremental_margin_budget_gate_usage_ratio": exchange_margin_usage_ratio,
        "incremental_margin_budget_gate_min_openable_candidates": 1,
        "incremental_margin_budget_gate_protected_selection_rank": 0,
        "incremental_margin_budget_gate_reduce_volume": True,
        "incremental_margin_budget_gate_entry_contexts": (
            "flat_entry,reverse_entry,rollover_reopen,regular_add,donchian_add"
        ),
    }


def _portfolio_deleverage_overrides() -> dict[str, Any]:
    return s517._portfolio_margin_deleverage_overrides(
        start_ratio=0.80,
        full_ratio=1.00,
        layer_kinds="base,add,donchian",
        min_pressure=0.50,
    )


def _capital_variant(variant: str, label: str, note: str) -> s650.CapitalVariant:
    return s650.CapitalVariant(
        variant=variant,
        label=label,
        account_capital=ACCOUNT_200K,
        c3_capital=ACCOUNT_200K,
        risk_multiplier=0.80,
        product_cap_ratio=0.25,
        max_concurrent_positions=4,
        note=note,
    )


def _variants(identity_map: str) -> list[DynamicVariant]:
    base = {
        **s519._product_cap_overrides(0.25, identity_map),
        "max_concurrent_positions": 4,
    }
    return [
        DynamicVariant(
            capital=_capital_variant(
                BASELINE_VARIANT,
                "20w all-in Stage526 core r080 pc25 maxpos4",
                "Stage350 原版 20万 all-in 对照；不启用动态保证金执行层。",
            ),
            overrides=base,
            profile="baseline",
        ),
        DynamicVariant(
            capital=_capital_variant(
                "stage526_200k_entry_reduce95_r080_pc25_maxpos4",
                "20w Stage526 entry reduce95 r080 pc25 maxpos4",
                "开新仓前按 broker10 95% 预算逐手降低 selected_volume，降到0才跳过。",
            ),
            overrides={**base, **_entry_reduce_overrides(0.95)},
            profile="entry_reduce95",
        ),
        DynamicVariant(
            capital=_capital_variant(
                "stage526_200k_entry_reduce90_r080_pc25_maxpos4",
                "20w Stage526 entry reduce90 r080 pc25 maxpos4",
                "开新仓前按 broker10 90% 预算逐手降低 selected_volume，作为更保守粗档。",
            ),
            overrides={**base, **_entry_reduce_overrides(0.90)},
            profile="entry_reduce90",
        ),
        DynamicVariant(
            capital=_capital_variant(
                "stage526_200k_pm_all80_100_r080_pc25_maxpos4",
                "20w Stage526 portfolio margin all80-100 r080 pc25 maxpos4",
                "持仓后 broker10 保证金/权益进入 80%-100% 压力区，允许关闭 base/add/donchian 层。",
            ),
            overrides={**base, **_portfolio_deleverage_overrides()},
            profile="portfolio_deleverage80_100",
        ),
        DynamicVariant(
            capital=_capital_variant(
                "stage526_200k_entry95_pm80_100_r080_pc25_maxpos4",
                "20w Stage526 entry95 + pm80-100 r080 pc25 maxpos4",
                "开仓前95%预算逐手降手，同时持仓后80%-100%压力区主动降杠杆。",
            ),
            overrides={**base, **_entry_reduce_overrides(0.95), **_portfolio_deleverage_overrides()},
            profile="entry_reduce95_plus_portfolio_deleverage80_100",
        ),
    ]


def _run_variant(
    spec: DynamicVariant,
    metadata: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    s517.assert_stage196_database_sentinels()
    s517.s506._patch_stage506_raw_roots()
    c3_overrides = s513._c3_overrides(s517.START_DT)
    preload_start = max(s517.PRELOAD_START_DT, s517.START_DT - timedelta(days=365))
    _, open_map = s517.s506.s501._seed_proxy_maps()
    engine = s517.s506.s502.ConfirmedDailyNextRealOpenEngine(open_map)
    engine.output = lambda msg: None
    engine.set_parameters(
        vt_symbols=metadata["vt_symbols"],
        interval=s517.Interval.DAILY,
        start=preload_start,
        end=s517.END_DT,
        rates=metadata["rates"],
        slippages=metadata["slippages"],
        sizes=metadata["sizes"],
        priceticks=metadata["priceticks"],
        capital=spec.capital.c3_capital,
    )
    setting = s517.build_roll_setting(
        metadata["margin_ratios"],
        risk_ratio=s517.BASE_RISK_RATIO * float(spec.capital.risk_multiplier),
        strategy_overrides=c3_overrides,
    )
    setting["capital_base"] = spec.capital.c3_capital
    setting.update(spec.overrides)
    engine.add_strategy(s517.QmtRollPortfolioStrategy, setting)
    engine.load_data()
    engine.run_backtesting()
    daily_df = engine.calculate_result()
    if daily_df is None or daily_df.empty:
        raise RuntimeError(f"empty daily result: {spec.capital.variant}")

    daily = daily_df.copy()
    daily = daily.loc[
        (daily.index >= s517.START_DT.date()) & (daily.index <= s517.END_DT.date())
    ].reset_index()
    daily.rename(columns={"index": "date"}, inplace=True)
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
    for column in ["net_pnl", "trade_count", "slippage", "commission", "turnover"]:
        daily[column] = pd.to_numeric(daily.get(column, 0.0), errors="coerce").fillna(0.0)
    daily["c3_equity"] = spec.capital.c3_capital + daily["net_pnl"].cumsum()
    daily["variant"] = spec.capital.variant
    daily["combo_variant"] = spec.capital.variant
    daily["label"] = spec.capital.label
    daily["risk_multiplier"] = spec.capital.risk_multiplier
    daily["note"] = spec.capital.note

    strategy = getattr(engine, "strategy", None)
    daily["portfolio_margin_deleverage_count"] = int(
        getattr(strategy, "portfolio_margin_deleverage_count", 0) or 0
    )
    daily["risk_cluster_heat_deleverage_count"] = int(
        getattr(strategy, "risk_cluster_heat_deleverage_count", 0) or 0
    )
    daily["portfolio_drawdown_deleverage_count"] = int(
        getattr(strategy, "portfolio_drawdown_deleverage_count", 0) or 0
    )

    positions = s517.build_positions_df(engine)
    if positions.empty:
        raise RuntimeError(f"empty positions: {spec.capital.variant}")
    positions["variant"] = spec.capital.variant
    positions["combo_variant"] = spec.capital.variant
    positions["label"] = spec.capital.label
    positions["risk_multiplier"] = spec.capital.risk_multiplier

    usage = pd.DataFrame(getattr(engine, "trade_usage_rows", []))
    if not usage.empty:
        usage["variant"] = spec.capital.variant
        usage["label"] = spec.capital.label
        usage["risk_multiplier"] = spec.capital.risk_multiplier

    candidates = pd.DataFrame(getattr(strategy, "entry_candidate_snapshots", []) if strategy else [])
    if not candidates.empty:
        candidates["variant"] = spec.capital.variant
        candidates["label"] = spec.capital.label
        candidates["risk_multiplier"] = spec.capital.risk_multiplier
    entry_risk = pd.DataFrame(getattr(strategy, "entry_risk_diagnostics", []) if strategy else [])
    if not entry_risk.empty:
        entry_risk["variant"] = spec.capital.variant
        entry_risk["label"] = spec.capital.label
        entry_risk["risk_multiplier"] = spec.capital.risk_multiplier
    return daily, positions, usage, candidates, entry_risk


def _candidate_summary(spec: DynamicVariant, candidates: pd.DataFrame, entry_risk: pd.DataFrame) -> dict[str, Any]:
    row: dict[str, Any] = {
        "variant": spec.capital.variant,
        "label": spec.capital.label,
        "profile": spec.profile,
        "flat_candidate_count": 0,
        "opened_flat_entry_count": 0,
        "blocked_by_incremental_gate_count": 0,
        "entry_gate_volume_reduced_count": 0,
        "opened_entry_gate_volume_reduced_count": 0,
        "entry_gate_volume_zeroed_count": 0,
        "entry_gate_total_volume_reduced": 0,
        "entry_gate_median_volume_before": 0.0,
        "entry_gate_median_volume_after": 0.0,
        "executed_entry_gate_volume_reduced_count": 0,
        "executed_entry_gate_total_volume_reduced": 0,
        "executed_entry_gate_reduced_contexts": "",
    }
    if not entry_risk.empty:
        risk = entry_risk.copy()
        for column in [
            "incremental_margin_budget_gate_volume_reduced",
            "incremental_margin_budget_gate_selected_volume_before",
            "incremental_margin_budget_gate_selected_volume_after",
        ]:
            if column not in risk.columns:
                risk[column] = 0.0
            risk[column] = pd.to_numeric(risk[column], errors="coerce").fillna(0.0)
        executed_reduced = risk[risk["incremental_margin_budget_gate_volume_reduced"].gt(0)]
        executed_delta = (
            executed_reduced["incremental_margin_budget_gate_selected_volume_before"]
            - executed_reduced["incremental_margin_budget_gate_selected_volume_after"]
        )
        context_column = "entry_context" if "entry_context" in executed_reduced.columns else "env_gate_entry_context"
        context_counts = (
            executed_reduced[context_column].astype(str).value_counts().to_dict()
            if context_column in executed_reduced.columns and not executed_reduced.empty
            else {}
        )
        row.update(
            {
                "executed_entry_gate_volume_reduced_count": int(len(executed_reduced)),
                "executed_entry_gate_total_volume_reduced": int(executed_delta.clip(lower=0).sum())
                if not executed_reduced.empty
                else 0,
                "executed_entry_gate_reduced_contexts": ",".join(
                    f"{key}:{value}" for key, value in sorted(context_counts.items())
                ),
            }
        )

    if candidates.empty or "entry_context" not in candidates.columns:
        return row

    flat = candidates[candidates["entry_context"].astype(str).eq("flat_entry")].copy()
    if flat.empty:
        return row

    numeric_columns = [
        "incremental_margin_budget_gate_volume_reduced",
        "incremental_margin_budget_gate_selected_volume_before",
        "incremental_margin_budget_gate_selected_volume_after",
    ]
    for column in numeric_columns:
        if column not in flat.columns:
            flat[column] = 0.0
        flat[column] = pd.to_numeric(flat[column], errors="coerce").fillna(0.0)

    opened = flat[flat["candidate_status"].astype(str).eq("opened")]
    blocked = flat[flat["skip_reason"].astype(str).eq("incremental_margin_budget_gate")]
    reduced = flat[flat["incremental_margin_budget_gate_volume_reduced"].gt(0)]
    opened_reduced = reduced[reduced["candidate_status"].astype(str).eq("opened")]
    zeroed = reduced[reduced["incremental_margin_budget_gate_selected_volume_after"].le(0)]
    volume_delta = (
        reduced["incremental_margin_budget_gate_selected_volume_before"]
        - reduced["incremental_margin_budget_gate_selected_volume_after"]
    )

    row.update(
        {
            "flat_candidate_count": int(len(flat)),
            "opened_flat_entry_count": int(len(opened)),
            "blocked_by_incremental_gate_count": int(len(blocked)),
            "entry_gate_volume_reduced_count": int(len(reduced)),
            "opened_entry_gate_volume_reduced_count": int(len(opened_reduced)),
            "entry_gate_volume_zeroed_count": int(len(zeroed)),
            "entry_gate_total_volume_reduced": int(volume_delta.clip(lower=0).sum()) if not reduced.empty else 0,
            "entry_gate_median_volume_before": float(
                reduced["incremental_margin_budget_gate_selected_volume_before"].median()
            )
            if not reduced.empty
            else 0.0,
            "entry_gate_median_volume_after": float(
                reduced["incremental_margin_budget_gate_selected_volume_after"].median()
            )
            if not reduced.empty
            else 0.0,
        }
    )
    return row


def _metrics_with_diagnostics(
    frame: pd.DataFrame,
    spec: DynamicVariant,
    cost_multiplier: float,
    candidate_row: dict[str, Any],
) -> dict[str, Any]:
    row = s650._metrics(frame, spec.capital, cost_multiplier)
    row.update(
        {
            "profile": spec.profile,
            "portfolio_margin_deleverage_count": int(frame["portfolio_margin_deleverage_count"].max())
            if "portfolio_margin_deleverage_count" in frame.columns
            else 0,
            "entry_gate_volume_reduced_count": int(candidate_row.get("entry_gate_volume_reduced_count", 0) or 0),
            "opened_entry_gate_volume_reduced_count": int(
                candidate_row.get("opened_entry_gate_volume_reduced_count", 0) or 0
            ),
            "entry_gate_volume_zeroed_count": int(candidate_row.get("entry_gate_volume_zeroed_count", 0) or 0),
            "entry_gate_total_volume_reduced": int(candidate_row.get("entry_gate_total_volume_reduced", 0) or 0),
            "executed_entry_gate_volume_reduced_count": int(
                candidate_row.get("executed_entry_gate_volume_reduced_count", 0) or 0
            ),
            "executed_entry_gate_total_volume_reduced": int(
                candidate_row.get("executed_entry_gate_total_volume_reduced", 0) or 0
            ),
        }
    )
    return row


def _add_retention(summary: pd.DataFrame, cost: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    baseline = summary[summary["variant"].eq(BASELINE_VARIANT)]
    baseline_return = float(baseline["total_return_pct"].iloc[0]) if not baseline.empty else math.nan
    for frame in [summary, cost]:
        if baseline_return and not math.isnan(baseline_return):
            frame["return_retention_vs_20w_baseline_pct"] = (
                frame["total_return_pct"].astype(float) / baseline_return * 100.0
            )
        else:
            frame["return_retention_vs_20w_baseline_pct"] = 0.0
    return summary, cost


def _decision(summary: pd.DataFrame, cost: pd.DataFrame) -> dict[str, Any]:
    cost2 = cost[cost["cost_multiplier"].eq(2.0)].set_index("variant")
    rows: list[dict[str, Any]] = []
    for item in summary.to_dict(orient="records"):
        variant = str(item["variant"])
        cost2_row = cost2.loc[variant].to_dict() if variant in cost2.index else {}
        cost2_dd40_pass = int(float(cost2_row.get("max_dd_pct", -999.0)) >= -40.0)
        cost2_survival_pass = int(int(cost2_row.get("account_survival_pass", 0) or 0) == 1)
        hard_pass = int(
            int(item.get("deployable_pass", 0) or 0) == 1
            and cost2_dd40_pass == 1
            and cost2_survival_pass == 1
        )
        ranked_item = dict(item)
        ranked_item.update(
            {
                "cost2_dd40_pass": cost2_dd40_pass,
                "cost2_survival_pass": cost2_survival_pass,
                "hard_pass": hard_pass,
            }
        )
        rows.append(ranked_item)
    ranked = sorted(
        rows,
        key=lambda row: (
            int(row["variant"] != BASELINE_VARIANT),
            int(row["hard_pass"]),
            float(row["total_return_pct"]),
        ),
        reverse=True,
    )
    non_baseline_hard = [row for row in ranked if row["variant"] != BASELINE_VARIANT and int(row["hard_pass"]) == 1]
    best = non_baseline_hard[0] if non_baseline_hard else (ranked[0] if ranked else {})
    label = (
        "stage526_200k_dynamic_margin_gate_hard_pass"
        if non_baseline_hard
        else "stage526_200k_dynamic_margin_gate_not_ready"
    )
    return {
        "stage": "Stage351",
        "script_stage": "Stage651",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": label,
        "best_variant": best,
        "ranked_variants": ranked,
        "pass_definition": (
            "1x: account equity > 0, max drawdown >= -40%, broker10 margin/equity <= 100%; "
            "2x cost: max drawdown >= -40% and account equity > 0."
        ),
    }


def _write_report(
    summary: pd.DataFrame,
    cost: pd.DataFrame,
    rolling: pd.DataFrame,
    events: pd.DataFrame,
    candidate_summary: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    result_view = summary.sort_values(["hard_pass", "total_return_pct"], ascending=[False, False])
    cost_view = cost.sort_values(["variant", "cost_multiplier"])
    lines = [
        "# Stage651 Stage526 20万动态保证金执行层",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        "- 阶段性质：部署资金层 A/C；不改 Stage526 alpha，不连接 CTP，不调用下单。",
        "- A：`stage526_200k_allin_r080_pc25_maxpos4`。",
        "- C：同一信号叠加动态保证金执行层，包括开仓前逐手降手和持仓后组合保证金降杠杆。",
        "- 运行前过拟合判断：否。只用当时可见权益、已有持仓保证金和拟开仓保证金，不按坏日期或坏品种修补。",
        "- 运行前继续价值判断：是。Stage350 的原版20万只在少数保证金高压日失败，正适合检验执行层资金闸门。",
        f"- 决策：`{decision['decision']}`。",
        "",
        "## 外部调研判断",
        "",
        "- vn.py PortfolioStrategy 是多合约组合策略模块，执行层目标是把组合持仓调到目标状态；这类问题适合放在策略/风控执行层，而不是改 alpha。",
        "- vn.py GitHub 同时提供 portfolio_strategy 与 risk_manager 模块；仓库说明里 risk_manager 覆盖下单数量、活动委托、撤单等前端风控。",
        "- 期货保证金本质上约束开仓所需资金，且杠杆会放大账户路径风险；小资金账户必须按合约整数手、保证金和风险预算共同决定开仓手数。",
        "",
        "## 预声明通过标准",
        "",
        "- 正常成本：账户权益始终大于0，最大回撤 `>= -40%`。",
        "- 正常成本：broker10 保证金/权益全程 `<= 100%`。",
        "- 2x 成本：账户权益始终大于0，最大回撤 `>= -40%`。",
        "",
        "## 核心结果",
        "",
        _md_table(
            result_view[
                [
                    "variant",
                    "profile",
                    "end_equity",
                    "total_return_pct",
                    "return_retention_vs_20w_baseline_pct",
                    "cagr_pct",
                    "max_dd_pct",
                    "sharpe",
                    "max_broker10_margin_to_equity_pct",
                    "days_over_100pct",
                    "total_slippage",
                    "total_trade_count",
                    "nonzero_daily_win_rate_pct",
                    "portfolio_margin_deleverage_count",
                    "entry_gate_volume_reduced_count",
                    "entry_gate_total_volume_reduced",
                    "executed_entry_gate_volume_reduced_count",
                    "executed_entry_gate_total_volume_reduced",
                    "hard_pass",
                ]
            ]
        ),
        "",
        "## 开仓候选诊断",
        "",
        _md_table(candidate_summary),
        "",
        "## 成本压力",
        "",
        _md_table(
            cost_view[
                [
                    "variant",
                    "cost_multiplier",
                    "end_equity",
                    "total_return_pct",
                    "max_dd_pct",
                    "sharpe",
                    "max_broker10_margin_to_equity_pct",
                    "days_over_100pct",
                    "deployable_pass",
                ]
            ],
            max_rows=40,
        ),
        "",
        "## 63/126/252日任意启动体验",
        "",
        _md_table(
            rolling[
                [
                    "variant",
                    "holding_days",
                    "p05_return_pct",
                    "median_return_pct",
                    "positive_rate_pct",
                    "min_window_dd_pct",
                    "worst_return_start",
                    "worst_return_end",
                ]
            ],
            max_rows=80,
        ),
        "",
        "## 关键风险日",
        "",
        _md_table(events, max_rows=50),
        "",
        "## 结论",
        "",
        f"- 决策标签：`{decision['decision']}`。",
        f"- 最优候选：`{decision.get('best_variant', {}).get('variant', '')}`。",
        "- 如果只有持仓降杠杆或组合闸门通过，还不能直接等价为“少开一点就行”；需要看开仓降手诊断是否实际减少了手数，以及是否仍出现持仓后保证金穿线。",
        "- 本阶段仍不关闭 Stage526 live TCA 缺口；即使保证金层通过，也需要后续真实委托/成交/TCA 验收。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    metadata = s513._metadata()
    identity_map = s519._product_identity_cluster_map(metadata)
    specs = _variants(identity_map)

    daily_frames: list[pd.DataFrame] = []
    position_frames: list[pd.DataFrame] = []
    usage_frames: list[pd.DataFrame] = []
    candidate_frames: list[pd.DataFrame] = []
    entry_risk_frames: list[pd.DataFrame] = []
    product_frames: list[pd.DataFrame] = []
    candidate_summary_rows: list[dict[str, Any]] = []

    for spec in specs:
        print(f"[stage651] running {spec.capital.variant}", flush=True)
        daily, positions, usage, candidates, entry_risk = _run_variant(spec, metadata)
        daily["account_capital"] = spec.capital.account_capital
        daily["c3_capital"] = spec.capital.c3_capital
        positions["account_capital"] = spec.capital.account_capital
        positions["c3_capital"] = spec.capital.c3_capital
        c3_margin_daily, product_margin = s513._position_margin(positions, metadata)
        combined = s650._combine_daily(daily, c3_margin_daily, spec.capital)
        combined["profile"] = spec.profile

        daily_frames.append(combined)
        position_frames.append(positions)
        product_frames.append(product_margin)
        candidate_summary_rows.append(_candidate_summary(spec, candidates, entry_risk))
        if not usage.empty:
            usage["account_capital"] = spec.capital.account_capital
            usage["c3_capital"] = spec.capital.c3_capital
            usage_frames.append(usage)
        if not candidates.empty:
            candidates["profile"] = spec.profile
            candidate_frames.append(candidates)
        if not entry_risk.empty:
            entry_risk["profile"] = spec.profile
            entry_risk_frames.append(entry_risk)

    combo_daily = pd.concat(daily_frames, ignore_index=True, sort=False)
    positions_all = pd.concat(position_frames, ignore_index=True, sort=False)
    product_margin_all = pd.concat(product_frames, ignore_index=True, sort=False)
    usage_all = pd.concat(usage_frames, ignore_index=True, sort=False) if usage_frames else pd.DataFrame()
    candidates_all = (
        pd.concat(candidate_frames, ignore_index=True, sort=False) if candidate_frames else pd.DataFrame()
    )
    entry_risk_all = (
        pd.concat(entry_risk_frames, ignore_index=True, sort=False) if entry_risk_frames else pd.DataFrame()
    )
    candidate_summary = pd.DataFrame(candidate_summary_rows)

    spec_map = {spec.capital.variant: spec for spec in specs}
    candidate_map = candidate_summary.set_index("variant").to_dict(orient="index")
    summary_rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    for variant, frame in combo_daily.groupby("variant", sort=False):
        spec = spec_map[variant]
        candidate_row = candidate_map.get(variant, {})
        for cost_multiplier in COST_MULTIPLIERS:
            row = _metrics_with_diagnostics(frame, spec, cost_multiplier, candidate_row)
            cost_rows.append(row)
            if cost_multiplier == 1.0:
                summary_rows.append(row)
    summary = pd.DataFrame(summary_rows)
    cost = pd.DataFrame(cost_rows)
    summary, cost = _add_retention(summary, cost)
    decision = _decision(summary, cost)

    hard_map = {row["variant"]: row for row in decision["ranked_variants"]}
    summary["hard_pass"] = summary["variant"].map(lambda variant: int(hard_map.get(variant, {}).get("hard_pass", 0)))
    cost["hard_pass"] = cost["variant"].map(lambda variant: int(hard_map.get(variant, {}).get("hard_pass", 0)))

    rolling = s650._rolling_holding(combo_daily)
    events = s650._event_days(combo_daily, product_margin_all)
    original_chart_path = s650.CHART_PATH
    try:
        s650.CHART_PATH = CHART_PATH
        s650._plot(combo_daily, summary)
    finally:
        s650.CHART_PATH = original_chart_path
    _write_report(summary, cost, rolling, events, candidate_summary, decision)

    combo_daily.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    positions_all.to_csv(POSITIONS_PATH, index=False, encoding="utf-8-sig")
    product_margin_all.to_csv(PRODUCT_MARGIN_PATH, index=False, encoding="utf-8-sig")
    if not usage_all.empty:
        usage_all.to_csv(TRADE_USAGE_PATH, index=False, encoding="utf-8-sig")
    if not candidates_all.empty:
        candidates_all.to_csv(CANDIDATES_PATH, index=False, encoding="utf-8-sig")
    if not entry_risk_all.empty:
        entry_risk_all.to_csv(ENTRY_RISK_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    rolling.to_csv(ROLLING_PATH, index=False, encoding="utf-8-sig")
    events.to_csv(EVENT_PATH, index=False, encoding="utf-8-sig")
    candidate_summary.to_csv(CANDIDATE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
