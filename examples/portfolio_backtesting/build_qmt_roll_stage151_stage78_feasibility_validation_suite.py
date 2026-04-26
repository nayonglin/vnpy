from __future__ import annotations

import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from main_contract_mapping import get_preferred_mapping_path
from qmt_roll_official_stage78_config import (
    OFFICIAL_STAGE78_CAPITAL,
    OFFICIAL_STAGE78_REFERENCE_METRICS,
    OFFICIAL_STAGE78_ROLE,
    OFFICIAL_STAGE78_VERSION,
    build_official_stage78_overrides,
    build_official_stage78_paths,
)
from qmt_universe import END_DT, PRELOAD_START_DT, START_DT
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy
from run_qmt_roll_backtest import (
    build_backtest_engine,
    build_roll_setting,
    build_summary_row,
    compute_round_trip_win_ratio,
    run_backtest,
)
from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import (
    to_markdown_table,
)
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import (
    BASE_RISK_RATIO,
)


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"
MODEL_TAG: str = "stage151_stage78_feasibility_validation_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage151_stage78_feasibility_validation"

COST_STRESS_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
PRODUCT_ABLATION_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_ablation_{MODEL_TAG}.csv"
ROLL_SHIFT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_roll_shift_{MODEL_TAG}.csv"
SHADOW_PROTOCOL_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_shadow_protocol_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

GENERATED_DIR: Path = OUTPUT_DIR / "stage151_generated_inputs"

STAGE147_SUMMARY_PATH: Path = (
    OUTPUT_DIR / "qmt_roll_stage147_stage78_live_weekly_report_summary_stage147_stage78_live_weekly_report_v1.json"
)
STAGE148_SUMMARY_PATH: Path = (
    OUTPUT_DIR / "qmt_roll_stage148_stage78_live_go_no_go_audit_summary_stage148_stage78_live_go_no_go_audit_v1.json"
)

SLIPPAGE_MULTIPLIERS: tuple[float, ...] = (1.0, 2.0, 3.0, 5.0)
ROLL_SHIFT_DAYS: tuple[int, ...] = (-3, -1, 1, 3)


def to_markdown_table(df: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 20) -> str:
    if df.empty:
        return "_empty_"
    view = df[columns].copy() if columns else df.copy()
    view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda value: f"{value:.4f}")
    header = "| " + " | ".join(view.columns) + " |"
    separator = "| " + " | ".join(["---"] * len(view.columns)) + " |"
    rows = ["| " + " | ".join(map(str, row)) + " |" for row in view.to_numpy()]
    return "\n".join([header, separator, *rows])


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or math.isinf(result):
        return default
    return result


def _run_stage78_variant(
    *,
    analysis_start: datetime = START_DT,
    analysis_end: datetime = END_DT,
    strategy_overrides: dict[str, Any] | None = None,
    slippage_multiplier: float = 1.0,
) -> dict[str, Any]:
    overrides = build_official_stage78_overrides()
    if strategy_overrides:
        overrides.update(strategy_overrides)

    preload_start = max(PRELOAD_START_DT, analysis_start - timedelta(days=365))
    engine, metadata = build_backtest_engine(
        preload_start=preload_start,
        backtest_end=analysis_end,
        capital=OFFICIAL_STAGE78_CAPITAL,
        product_universe_csv_path=str(overrides.get("product_universe_csv_path", "") or ""),
    )
    engine.output = lambda msg: None
    if abs(slippage_multiplier - 1.0) > 1e-9:
        engine.slippages = {key: float(value) * slippage_multiplier for key, value in engine.slippages.items()}

    setting = build_roll_setting(
        metadata["margin_ratios"],
        risk_ratio=BASE_RISK_RATIO,
        strategy_overrides=overrides,
    )
    setting["capital_base"] = OFFICIAL_STAGE78_CAPITAL
    engine.add_strategy(QmtRollPortfolioStrategy, setting)
    engine.load_data()
    engine.run_backtesting()
    daily_df = engine.calculate_result()
    if daily_df is not None:
        analysis_df = daily_df.copy()
        analysis_df = analysis_df.loc[
            (analysis_df.index >= analysis_start.date())
            & (analysis_df.index <= analysis_end.date())
        ]
    else:
        analysis_df = None

    statistics: dict[str, Any] = engine.calculate_statistics(analysis_df)
    win_ratio_pct, win_count, round_trip_count = compute_round_trip_win_ratio(engine)
    statistics["win_ratio"] = win_ratio_pct
    statistics["win_count"] = win_count
    statistics["round_trip_count"] = round_trip_count
    row = build_summary_row(
        statistics,
        analysis_start=analysis_start,
        analysis_end=analysis_end,
        total_net_pnl=float(statistics.get("total_net_pnl", 0) or 0),
        total_slippage=float(statistics.get("total_slippage", 0) or 0),
        total_commission=float(statistics.get("total_commission", 0) or 0),
        profit_days=int(statistics.get("profit_days", 0) or 0),
        loss_days=int(statistics.get("loss_days", 0) or 0),
        round_trip_count=int(statistics.get("round_trip_count", 0) or 0),
    )
    return row


def _add_reference_diffs(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    reference = OFFICIAL_STAGE78_REFERENCE_METRICS["full_2020_2026"]
    result = df.copy()
    result["end_balance_diff_vs_stage78"] = pd.to_numeric(result["end_balance"], errors="coerce").fillna(0.0) - float(
        reference["end_balance"]
    )
    result["return_diff_vs_stage78"] = pd.to_numeric(result["total_return_pct"], errors="coerce").fillna(0.0) - float(
        reference["total_return_pct"]
    )
    result["max_dd_diff_vs_stage78"] = pd.to_numeric(result["max_dd_percent"], errors="coerce").fillna(0.0) - float(
        reference["max_dd_percent"]
    )
    result["sharpe_diff_vs_stage78"] = pd.to_numeric(result["sharpe_ratio"], errors="coerce").fillna(0.0) - float(
        reference["sharpe_ratio"]
    )
    return result


def run_cost_stress() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for multiplier in SLIPPAGE_MULTIPLIERS:
        print(f"[stage151] cost stress slippage x{multiplier:g}", flush=True)
        row = _run_stage78_variant(slippage_multiplier=multiplier)
        row.update(
            {
                "experiment_type": "cost_stress",
                "profile_name": f"slippage_x{multiplier:g}",
                "slippage_multiplier": multiplier,
            }
        )
        rows.append(row)
    return _add_reference_diffs(pd.DataFrame(rows))


def _write_product_ablation_universe(removed_product: str) -> Path:
    universe_path, _ = build_official_stage78_paths()
    df = pd.read_csv(universe_path)
    df["eligible"] = pd.to_numeric(df["eligible"], errors="coerce").fillna(0).astype(int)
    df.loc[df["product_vt_symbol"].astype(str) == removed_product, "eligible"] = 0
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = removed_product.replace(".", "_")
    path = GENERATED_DIR / f"stage151_without_{safe_name}.csv"
    df.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def run_product_ablation() -> pd.DataFrame:
    universe_path, _ = build_official_stage78_paths()
    universe_df = pd.read_csv(universe_path)
    products = sorted(universe_df[universe_df["eligible"].astype(int).eq(1)]["product_vt_symbol"].astype(str).unique())

    rows: list[dict[str, Any]] = []
    for product in products:
        print(f"[stage151] product ablation without {product}", flush=True)
        ablation_universe_path = _write_product_ablation_universe(product)
        row = _run_stage78_variant(strategy_overrides={"product_universe_csv_path": str(ablation_universe_path)})
        row.update(
            {
                "experiment_type": "product_ablation",
                "profile_name": f"without_{product}",
                "removed_product": product,
                "product_universe_csv_path": str(ablation_universe_path),
            }
        )
        rows.append(row)
    result = _add_reference_diffs(pd.DataFrame(rows))
    if not result.empty:
        result["dependency_risk_rank"] = (
            pd.to_numeric(result["end_balance_diff_vs_stage78"], errors="coerce").rank(method="first")
        )
    return result.sort_values("end_balance_diff_vs_stage78").reset_index(drop=True)


def _write_shifted_mapping(shift_days: int) -> Path:
    mapping_path = get_preferred_mapping_path()
    df = pd.read_csv(mapping_path)
    df["date"] = pd.to_datetime(df["date"])
    df.sort_values(["continuous_symbol_vt", "date"], inplace=True)
    shifted = df.copy()
    grouped = shifted.groupby("continuous_symbol_vt", group_keys=False)["main_contract_vt"]
    shifted_values = grouped.shift(shift_days)
    shifted["main_contract_vt"] = shifted_values.fillna(shifted["main_contract_vt"]).fillna("")
    shifted["date"] = shifted["date"].dt.strftime("%Y-%m-%d")
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    direction = "lag" if shift_days > 0 else "lead"
    path = GENERATED_DIR / f"stage151_mapping_{direction}_{abs(shift_days)}d.csv"
    shifted.to_csv(path, index=False, encoding="utf-8-sig")
    return path


def run_roll_shift() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for shift_days in ROLL_SHIFT_DAYS:
        mapping_path = _write_shifted_mapping(shift_days)
        direction = "lag" if shift_days > 0 else "lead"
        print(f"[stage151] roll shift {direction} {abs(shift_days)}d", flush=True)
        row = _run_stage78_variant(strategy_overrides={"mapping_csv_path": str(mapping_path)})
        row.update(
            {
                "experiment_type": "roll_shift",
                "profile_name": f"roll_{direction}_{abs(shift_days)}d",
                "shift_days": shift_days,
                "mapping_csv_path": str(mapping_path),
            }
        )
        rows.append(row)
    return _add_reference_diffs(pd.DataFrame(rows))


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_shadow_protocol() -> pd.DataFrame:
    stage147 = _load_json(STAGE147_SUMMARY_PATH)
    stage148 = _load_json(STAGE148_SUMMARY_PATH)
    rows = [
        {
            "gate": "version_freeze",
            "status": "pass",
            "evidence": OFFICIAL_STAGE78_VERSION,
            "action": "不允许因影子盘短期表现修改Stage78参数。",
        },
        {
            "gate": "true_oos_available_now",
            "status": "not_yet",
            "evidence": "当前只能建立影子盘记录，未来交易日才是真正样本外。",
            "action": "从下一交易日开始逐日记录信号、理论成交、真实可成交、偏差。",
        },
        {
            "gate": "weekly_monitoring_pack",
            "status": "available" if stage147 else "missing",
            "evidence": str(STAGE147_SUMMARY_PATH),
            "action": "每周生成Stage78准实盘周报，severe时停止加新研究。",
        },
        {
            "gate": "go_no_go_audit",
            "status": str(stage148.get("decision", "available" if stage148 else "missing")),
            "evidence": str(STAGE148_SUMMARY_PATH),
            "action": "没有通过GO之前只做模拟盘/影子盘，不直接实盘。",
        },
        {
            "gate": "minimum_forward_sample",
            "status": "pending",
            "evidence": "建议至少3个月或80笔成交级别影子样本。",
            "action": "只比较分布是否落入历史压力区间，不追求复制历史收益。",
        },
    ]
    return pd.DataFrame(rows)


def _stress_judgement(cost_df: pd.DataFrame, ablation_df: pd.DataFrame, roll_df: pd.DataFrame) -> dict[str, Any]:
    cost = cost_df.copy()
    cost["total_return_pct"] = pd.to_numeric(cost["total_return_pct"], errors="coerce")
    x3 = cost[cost["slippage_multiplier"].astype(float).eq(3.0)]
    x5 = cost[cost["slippage_multiplier"].astype(float).eq(5.0)]
    x3_positive = bool(not x3.empty and float(x3["total_return_pct"].iloc[0]) > 0)
    x5_positive = bool(not x5.empty and float(x5["total_return_pct"].iloc[0]) > 0)

    ablation = ablation_df.copy()
    ablation["total_return_pct"] = pd.to_numeric(ablation["total_return_pct"], errors="coerce")
    ablation_positive_rate = float((ablation["total_return_pct"] > 0).mean() * 100.0) if not ablation.empty else 0.0
    worst_ablation = ablation.sort_values("end_balance_diff_vs_stage78").head(1).to_dict(orient="records")

    roll = roll_df.copy()
    roll["total_return_pct"] = pd.to_numeric(roll["total_return_pct"], errors="coerce")
    roll_positive_rate = float((roll["total_return_pct"] > 0).mean() * 100.0) if not roll.empty else 0.0
    worst_roll = roll.sort_values("end_balance_diff_vs_stage78").head(1).to_dict(orient="records")

    return {
        "cost_x3_positive": x3_positive,
        "cost_x5_positive": x5_positive,
        "ablation_positive_rate_pct": ablation_positive_rate,
        "roll_shift_positive_rate_pct": roll_positive_rate,
        "worst_ablation": worst_ablation[0] if worst_ablation else {},
        "worst_roll_shift": worst_roll[0] if worst_roll else {},
        "overfit_judgement": "否。实验固定Stage78，只改变成本、品种剥离和换月扰动来证伪。",
        "continue_value_judgement": "有。若在这些压力下仍有正期望，Stage78更接近准实盘；若失败，则暴露不可实盘的风险点。",
    }


def build_report(
    cost_df: pd.DataFrame,
    ablation_df: pd.DataFrame,
    roll_df: pd.DataFrame,
    shadow_df: pd.DataFrame,
    summary: dict[str, Any],
) -> str:
    reference = OFFICIAL_STAGE78_REFERENCE_METRICS["full_2020_2026"]
    worst_ablation = summary["judgement"].get("worst_ablation", {})
    worst_roll = summary["judgement"].get("worst_roll_shift", {})
    lines = [
        "# Stage151 Stage78可行性验证套件",
        "",
        "## 定位",
        "",
        "- 本阶段不是新策略版本，不修改Stage78正式策略，不触发A/B技能。",
        "- 目的不是提高回测收益，而是用固定版本做证伪：影子盘协议、成本压力、品种剥离、主力换月扰动。",
        "",
        "## Stage78冻结基准",
        "",
        f"- 版本：`{OFFICIAL_STAGE78_VERSION}`",
        f"- 角色：`{OFFICIAL_STAGE78_ROLE}`",
        f"- 本金：`{OFFICIAL_STAGE78_CAPITAL:,.0f}`",
        (
            f"- 全周期基准：期末权益 `{reference['end_balance']:,.0f}`，"
            f"总收益 `{reference['total_return_pct']:.4f}%`，"
            f"最大回撤 `{reference['max_dd_percent']:.4f}%`，"
            f"Sharpe `{reference['sharpe_ratio']:.4f}`，"
            f"总滑点 `{reference['total_slippage']:,.0f}`，"
            f"总交易 `{reference['total_trade_count']:,.0f}`。"
        ),
        "",
        "## 影子盘协议",
        "",
        to_markdown_table(shadow_df, ["gate", "status", "action"], max_rows=20),
        "",
        "## 成本压力测试",
        "",
        to_markdown_table(
            cost_df,
            [
                "profile_name",
                "end_balance",
                "total_return_pct",
                "max_dd_percent",
                "sharpe_ratio",
                "total_slippage",
                "total_trade_count",
                "win_ratio_pct",
                "end_balance_diff_vs_stage78",
            ],
            max_rows=20,
        ),
        "",
        "## 品种剥离最脆弱项",
        "",
        to_markdown_table(
            ablation_df.head(10),
            [
                "removed_product",
                "end_balance",
                "total_return_pct",
                "max_dd_percent",
                "sharpe_ratio",
                "total_trade_count",
                "win_ratio_pct",
                "end_balance_diff_vs_stage78",
            ],
            max_rows=10,
        ),
        "",
        "## 主力换月扰动",
        "",
        to_markdown_table(
            roll_df,
            [
                "profile_name",
                "end_balance",
                "total_return_pct",
                "max_dd_percent",
                "sharpe_ratio",
                "total_trade_count",
                "win_ratio_pct",
                "end_balance_diff_vs_stage78",
            ],
            max_rows=20,
        ),
        "",
        "## 汇总结论",
        "",
        f"- 3倍滑点仍为正收益：`{summary['judgement']['cost_x3_positive']}`",
        f"- 5倍滑点仍为正收益：`{summary['judgement']['cost_x5_positive']}`",
        f"- 品种剥离正收益率：`{summary['judgement']['ablation_positive_rate_pct']:.4f}%`",
        f"- 换月扰动正收益率：`{summary['judgement']['roll_shift_positive_rate_pct']:.4f}%`",
        (
            f"- 最敏感剥离品种：`{worst_ablation.get('removed_product', '')}`，"
            f"期末权益差 `{_safe_float(worst_ablation.get('end_balance_diff_vs_stage78')):,.0f}`。"
        ),
        (
            f"- 最敏感换月扰动：`{worst_roll.get('profile_name', '')}`，"
            f"期末权益差 `{_safe_float(worst_roll.get('end_balance_diff_vs_stage78')):,.0f}`。"
        ),
        "",
        "## 反思",
        "",
        f"- 是否过拟合：{summary['judgement']['overfit_judgement']}",
        f"- 是否还有价值继续：{summary['judgement']['continue_value_judgement']}",
        "",
        "## 后续TODO",
        "",
        "- 若压力测试通过，下一步不继续调参数，转向真实影子盘逐日落表。",
        "- 若某一品种剥离导致系统崩塌，不立刻黑名单或补丁，先判断是否为结构依赖还是单样本偶然。",
        "- 若主力换月扰动导致结果大幅坍塌，优先审计换月数据与执行规则，不修改策略信号。",
    ]
    return "\n".join(lines)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    print("[stage151] start validation suite", flush=True)

    shadow_df = build_shadow_protocol()
    cost_df = run_cost_stress()
    ablation_df = run_product_ablation()
    roll_df = run_roll_shift()

    shadow_df.to_csv(SHADOW_PROTOCOL_PATH, index=False, encoding="utf-8-sig")
    cost_df.to_csv(COST_STRESS_PATH, index=False, encoding="utf-8-sig")
    ablation_df.to_csv(PRODUCT_ABLATION_PATH, index=False, encoding="utf-8-sig")
    roll_df.to_csv(ROLL_SHIFT_PATH, index=False, encoding="utf-8-sig")

    summary = {
        "model_tag": MODEL_TAG,
        "official_version": OFFICIAL_STAGE78_VERSION,
        "official_role": OFFICIAL_STAGE78_ROLE,
        "capital": OFFICIAL_STAGE78_CAPITAL,
        "reference_metrics": OFFICIAL_STAGE78_REFERENCE_METRICS,
        "judgement": _stress_judgement(cost_df, ablation_df, roll_df),
        "outputs": {
            "shadow_protocol": str(SHADOW_PROTOCOL_PATH),
            "cost_stress": str(COST_STRESS_PATH),
            "product_ablation": str(PRODUCT_ABLATION_PATH),
            "roll_shift": str(ROLL_SHIFT_PATH),
            "report": str(REPORT_PATH),
        },
    }
    SUMMARY_JSON_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(build_report(cost_df, ablation_df, roll_df, shadow_df, summary), encoding="utf-8")

    print(json.dumps(summary["judgement"], ensure_ascii=False, indent=2), flush=True)
    print(f"[stage151] report: {REPORT_PATH}", flush=True)


if __name__ == "__main__":
    main()
