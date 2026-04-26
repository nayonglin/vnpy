from __future__ import annotations

import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from vnpy.trader.constant import Interval
from vnpy.trader.object import BarData, TradeData
from vnpy_portfoliostrategy.backtesting import Status

from main_contract_mapping import build_contract_metadata, load_product_universe_symbols
from qmt_roll_official_stage78_config import (
    OFFICIAL_STAGE78_CAPITAL,
    OFFICIAL_STAGE78_REFERENCE_METRICS,
    OFFICIAL_STAGE78_ROLE,
    OFFICIAL_STAGE78_VERSION,
    build_official_stage78_overrides,
    build_official_stage78_paths,
)
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy
from qmt_universe import END_DT, PRELOAD_START_DT, START_DT
from run_qmt_roll_backtest import (
    SameDayCloseBacktestingEngine,
    build_roll_setting,
    build_summary_row,
    compute_round_trip_win_ratio,
)
from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import (
    to_markdown_table,
)
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import (
    BASE_RISK_RATIO,
)


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"
GENERATED_DIR: Path = OUTPUT_DIR / "stage153_generated_inputs"

MODEL_TAG: str = "stage153_stage78_anti_fit_validation_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage153_stage78_anti_fit_validation"

PLACEBO_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_placebo_ai_pool_{MODEL_TAG}.csv"
SIZING_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_sizing_invariance_{MODEL_TAG}.csv"
EXECUTION_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_execution_delay_{MODEL_TAG}.csv"
BOOTSTRAP_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_monthly_block_bootstrap_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

FORMAL_DAILY_PATH: Path = OUTPUT_DIR / "qmt_roll_official_stage78_defensive_formal_daily.csv"

PLACEBO_RANDOM_SEEDS: tuple[int, ...] = (11, 29, 47)
BOOTSTRAP_SEED: int = 15378
BOOTSTRAP_ITERATIONS: int = 2000


class DelayedExecutionBacktestingEngine(SameDayCloseBacktestingEngine):
    """Execute orders generated on day T on day T+1 at a configurable bar price."""

    delayed_price_field: str = "open_price"

    def new_bars(self, dt) -> None:
        self.datetime = dt

        bars: dict[str, BarData] = {}
        for vt_symbol in self.vt_symbols:
            bar: BarData | None = self.history_data.get((dt, vt_symbol), None)

            if bar:
                self.bars[vt_symbol] = bar
                bars[vt_symbol] = bar
            elif vt_symbol in self.bars:
                old_bar: BarData = self.bars[vt_symbol]
                bar = BarData(
                    symbol=old_bar.symbol,
                    exchange=old_bar.exchange,
                    datetime=dt,
                    open_price=old_bar.close_price,
                    high_price=old_bar.close_price,
                    low_price=old_bar.close_price,
                    close_price=old_bar.close_price,
                    gateway_name=old_bar.gateway_name,
                )
                self.bars[vt_symbol] = bar

        self.cross_delayed_orders()
        self.strategy.on_bars(bars)

        if self.strategy.inited:
            self.update_daily_close(self.bars, dt)

    def cross_delayed_orders(self) -> None:
        for order in list(self.active_limit_orders.values()):
            bar: BarData | None = self.bars.get(order.vt_symbol)
            if bar is None:
                continue

            trade_price = float(getattr(bar, self.delayed_price_field, 0.0) or 0.0)
            if trade_price <= 0:
                trade_price = float(bar.close_price)
            if trade_price <= 0:
                continue

            if order.status == Status.SUBMITTING:
                order.status = Status.NOTTRADED
                self.strategy.update_order(order)

            order.traded = order.volume
            order.status = Status.ALLTRADED
            self.strategy.update_order(order)

            if order.vt_orderid in self.active_limit_orders:
                self.active_limit_orders.pop(order.vt_orderid)

            self.trade_count += 1
            trade = TradeData(
                symbol=order.symbol,
                exchange=order.exchange,
                orderid=order.orderid,
                tradeid=str(self.trade_count),
                direction=order.direction,
                offset=order.offset,
                price=trade_price,
                volume=order.volume,
                datetime=self.datetime,
                gateway_name=self.gateway_name,
            )

            self.strategy.update_trade(trade)
            self.trades[trade.vt_tradeid] = trade


class NextOpenDelayedExecutionEngine(DelayedExecutionBacktestingEngine):
    delayed_price_field = "open_price"


class NextCloseDelayedExecutionEngine(DelayedExecutionBacktestingEngine):
    delayed_price_field = "close_price"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or math.isinf(result):
        return default
    return result


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


def _run_stage78_variant(
    *,
    profile_name: str,
    experiment_type: str,
    strategy_overrides: dict[str, Any] | None = None,
    engine_class: type[SameDayCloseBacktestingEngine] = SameDayCloseBacktestingEngine,
    slippage_multiplier: float = 1.0,
    analysis_start: datetime = START_DT,
    analysis_end: datetime = END_DT,
) -> dict[str, Any]:
    overrides = build_official_stage78_overrides()
    if strategy_overrides:
        overrides.update(strategy_overrides)

    preload_start = max(PRELOAD_START_DT, analysis_start - timedelta(days=365))
    supported_symbols = load_product_universe_symbols(str(overrides.get("product_universe_csv_path", "") or ""))
    metadata = build_contract_metadata(supported_symbols=supported_symbols)

    engine = engine_class()
    engine.output = lambda msg: None
    engine.set_parameters(
        vt_symbols=metadata["vt_symbols"],
        interval=Interval.DAILY,
        start=preload_start,
        end=analysis_end,
        rates=metadata["rates"],
        slippages=metadata["slippages"],
        sizes=metadata["sizes"],
        priceticks=metadata["priceticks"],
        capital=OFFICIAL_STAGE78_CAPITAL,
    )
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
        experiment_type=experiment_type,
        profile_name=profile_name,
        slippage_multiplier=slippage_multiplier,
        total_net_pnl=float(statistics.get("total_net_pnl", 0) or 0),
        total_slippage=float(statistics.get("total_slippage", 0) or 0),
        total_commission=float(statistics.get("total_commission", 0) or 0),
        profit_days=int(statistics.get("profit_days", 0) or 0),
        loss_days=int(statistics.get("loss_days", 0) or 0),
        win_count=int(statistics.get("win_count", 0) or 0),
        round_trip_count=int(statistics.get("round_trip_count", 0) or 0),
    )
    reference = OFFICIAL_STAGE78_REFERENCE_METRICS["full_2020_2026"]
    row["end_balance_diff_vs_stage78"] = _safe_float(row.get("end_balance")) - float(reference["end_balance"])
    row["sharpe_diff_vs_stage78"] = _safe_float(row.get("sharpe_ratio")) - float(reference["sharpe_ratio"])
    row["max_dd_diff_vs_stage78"] = _safe_float(row.get("max_dd_percent")) - float(reference["max_dd_percent"])
    row["trade_count_diff_vs_stage78"] = _safe_float(row.get("total_trade_count")) - float(reference["total_trade_count"])
    return row


def _write_random_ai_pool(seed: int) -> Path:
    universe_path, eligibility_path = build_official_stage78_paths()
    universe_df = pd.read_csv(universe_path)
    products = sorted(universe_df[universe_df["eligible"].astype(int).eq(1)]["product_vt_symbol"].astype(str).unique())
    source = pd.read_csv(eligibility_path)
    rng = np.random.default_rng(seed)

    rows: list[dict[str, Any]] = []
    for eval_date, group in source.groupby("eval_date", sort=True):
        score_type = str(group["score_type"].iloc[0])
        if score_type == "static18_pre_ai_boundary":
            rows.extend(group.to_dict(orient="records"))
            continue

        top_n = int(pd.to_numeric(group["top_n"], errors="coerce").max())
        sample_n = min(max(top_n, 1), len(products))
        selected = list(rng.choice(products, size=sample_n, replace=False))
        source_scores = sorted(pd.to_numeric(group["score"], errors="coerce").fillna(0.0).tolist(), reverse=True)
        while len(source_scores) < sample_n:
            source_scores.append(0.0)
        for rank, product in enumerate(selected, start=1):
            rows.append(
                {
                    "strategy": str(group["strategy"].iloc[0]),
                    "score_type": f"stage153_random_placebo_seed_{seed}",
                    "eval_date": eval_date,
                    "product_vt_symbol": product,
                    "score": float(source_scores[rank - 1]),
                    "score_rank": rank,
                    "top_n": sample_n,
                }
            )

    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    path = GENERATED_DIR / f"stage153_random_ai_pool_seed_{seed}.csv"
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")
    return path


def run_placebo_ai_pool() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for seed in PLACEBO_RANDOM_SEEDS:
        print(f"[stage153] placebo random AI pool seed={seed}", flush=True)
        path = _write_random_ai_pool(seed)
        row = _run_stage78_variant(
            profile_name=f"random_ai_pool_seed_{seed}",
            experiment_type="placebo_ai_pool",
            strategy_overrides={"ai_product_pool_eligibility_path": str(path)},
        )
        row["placebo_seed"] = seed
        row["ai_product_pool_eligibility_path"] = str(path)
        rows.append(row)
    return pd.DataFrame(rows)


def run_sizing_invariance() -> pd.DataFrame:
    experiments: tuple[tuple[str, dict[str, Any]], ...] = (
        ("initial_cap_no_upward_compounding", {"sizing_equity_cap": OFFICIAL_STAGE78_CAPITAL}),
        ("fixed_size_1_contract", {"fixed_size": 1, "min_position_size": 1, "max_position_size": 1}),
    )
    rows: list[dict[str, Any]] = []
    for profile_name, overrides in experiments:
        print(f"[stage153] sizing invariance {profile_name}", flush=True)
        rows.append(
            _run_stage78_variant(
                profile_name=profile_name,
                experiment_type="sizing_invariance",
                strategy_overrides=overrides,
            )
        )
    return pd.DataFrame(rows)


def run_execution_delay() -> pd.DataFrame:
    experiments: tuple[tuple[str, type[SameDayCloseBacktestingEngine], float], ...] = (
        ("next_open_delay", NextOpenDelayedExecutionEngine, 1.0),
        ("next_close_delay", NextCloseDelayedExecutionEngine, 1.0),
        ("next_open_delay_slippage_x3", NextOpenDelayedExecutionEngine, 3.0),
    )
    rows: list[dict[str, Any]] = []
    for profile_name, engine_class, slippage_multiplier in experiments:
        print(f"[stage153] execution delay {profile_name}", flush=True)
        rows.append(
            _run_stage78_variant(
                profile_name=profile_name,
                experiment_type="execution_delay",
                engine_class=engine_class,
                slippage_multiplier=slippage_multiplier,
            )
        )
    return pd.DataFrame(rows)


def run_monthly_block_bootstrap() -> pd.DataFrame:
    if not FORMAL_DAILY_PATH.exists():
        return pd.DataFrame()

    daily = pd.read_csv(FORMAL_DAILY_PATH)
    if "date" in daily.columns:
        daily["date"] = pd.to_datetime(daily["date"])
    else:
        daily.rename(columns={daily.columns[0]: "date"}, inplace=True)
        daily["date"] = pd.to_datetime(daily["date"])
    if "net_pnl" not in daily.columns:
        return pd.DataFrame()

    daily = daily.sort_values("date").copy()
    daily["month"] = daily["date"].dt.to_period("M").astype(str)
    blocks = [group["net_pnl"].astype(float).to_numpy() for _, group in daily.groupby("month", sort=True)]
    if not blocks:
        return pd.DataFrame()

    rng = np.random.default_rng(BOOTSTRAP_SEED)
    rows: list[dict[str, Any]] = []
    for iteration in range(BOOTSTRAP_ITERATIONS):
        sampled = rng.choice(len(blocks), size=len(blocks), replace=True)
        pnl_path = np.concatenate([blocks[int(index)] for index in sampled])
        balance = OFFICIAL_STAGE78_CAPITAL + np.cumsum(pnl_path)
        high_water = np.maximum.accumulate(np.insert(balance, 0, OFFICIAL_STAGE78_CAPITAL))[1:]
        drawdown_pct = np.where(high_water > 0, (balance - high_water) / high_water * 100.0, 0.0)
        rows.append(
            {
                "iteration": iteration + 1,
                "end_balance": float(balance[-1]) if len(balance) else OFFICIAL_STAGE78_CAPITAL,
                "total_return_pct": float((balance[-1] / OFFICIAL_STAGE78_CAPITAL - 1.0) * 100.0)
                if len(balance)
                else 0.0,
                "max_dd_percent": float(drawdown_pct.min()) if len(drawdown_pct) else 0.0,
                "sampled_months": ",".join(str(int(index)) for index in sampled),
            }
        )
    return pd.DataFrame(rows)


def _bootstrap_summary(bootstrap_df: pd.DataFrame) -> dict[str, Any]:
    if bootstrap_df.empty:
        return {}
    end_balance = pd.to_numeric(bootstrap_df["end_balance"], errors="coerce")
    max_dd = pd.to_numeric(bootstrap_df["max_dd_percent"], errors="coerce")
    return {
        "iterations": int(len(bootstrap_df)),
        "positive_end_balance_rate_pct": float((end_balance > OFFICIAL_STAGE78_CAPITAL).mean() * 100.0),
        "end_balance_p05": float(end_balance.quantile(0.05)),
        "end_balance_median": float(end_balance.median()),
        "end_balance_p95": float(end_balance.quantile(0.95)),
        "max_dd_p05": float(max_dd.quantile(0.05)),
        "max_dd_median": float(max_dd.median()),
        "max_dd_p95": float(max_dd.quantile(0.95)),
    }


def _build_judgement(
    placebo_df: pd.DataFrame,
    sizing_df: pd.DataFrame,
    execution_df: pd.DataFrame,
    bootstrap_df: pd.DataFrame,
) -> dict[str, Any]:
    reference = OFFICIAL_STAGE78_REFERENCE_METRICS["full_2020_2026"]
    placebo = placebo_df.copy()
    sizing = sizing_df.copy()
    execution = execution_df.copy()

    placebo_best = float(pd.to_numeric(placebo["end_balance"], errors="coerce").max()) if not placebo.empty else 0.0
    placebo_median = float(pd.to_numeric(placebo["end_balance"], errors="coerce").median()) if not placebo.empty else 0.0
    sizing_positive_rate = float((pd.to_numeric(sizing["total_return_pct"], errors="coerce") > 0).mean() * 100.0) if not sizing.empty else 0.0
    execution_positive_rate = (
        float((pd.to_numeric(execution["total_return_pct"], errors="coerce") > 0).mean() * 100.0)
        if not execution.empty
        else 0.0
    )
    bootstrap = _bootstrap_summary(bootstrap_df)

    return {
        "reference_end_balance": float(reference["end_balance"]),
        "placebo_best_end_balance": placebo_best,
        "placebo_median_end_balance": placebo_median,
        "placebo_all_below_stage78": bool(placebo_best < float(reference["end_balance"])) if not placebo.empty else False,
        "sizing_positive_rate_pct": sizing_positive_rate,
        "execution_delay_positive_rate_pct": execution_positive_rate,
        "bootstrap": bootstrap,
        "overfit_judgement_before": "否。Stage153固定official_stage78_defensive_v1，只改变随机AI池、资金缩放口径、成交延迟和路径重排，不根据收益调参。",
        "continue_value_before": "是。若Stage78在负控、去复利和成交延迟下仍有优势或正收益，能更直接反证历史拟合。",
        "overfit_judgement_after": "否，但需要防止误用。placebo和固定风险结果只能用于证伪Stage78，不应用来反向选择产品或微调AI池。",
        "continue_value_after": "有条件。若负控明显弱于Stage78且执行延迟仍为正，下一步转向真实影子盘；若延迟成交崩坏，优先审计执行假设。",
    }


def build_report(
    placebo_df: pd.DataFrame,
    sizing_df: pd.DataFrame,
    execution_df: pd.DataFrame,
    bootstrap_df: pd.DataFrame,
    summary: dict[str, Any],
) -> str:
    reference = OFFICIAL_STAGE78_REFERENCE_METRICS["full_2020_2026"]
    bootstrap_summary = summary["judgement"].get("bootstrap", {})
    lines = [
        "# Stage153 Stage78反拟合验证",
        "",
        "## 定位",
        "",
        "- 本阶段不是新策略版本，不修改Stage78正式策略参数。",
        "- 目标是验证Stage78是否依赖AI池偶然命中、复利路径、同日理想成交或单一路径顺序。",
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
            f"交易 `{reference['total_trade_count']:,.0f}`。"
        ),
        "",
        "## Placebo AI池",
        "",
        to_markdown_table(
            placebo_df,
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
        "## 资金口径不变性",
        "",
        to_markdown_table(
            sizing_df,
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
        "## 延迟执行压力",
        "",
        to_markdown_table(
            execution_df,
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
        "## 月度区块Bootstrap",
        "",
        f"- 迭代次数：`{int(bootstrap_summary.get('iterations', 0))}`",
        f"- 期末权益高于初始本金概率：`{_safe_float(bootstrap_summary.get('positive_end_balance_rate_pct')):.4f}%`",
        f"- 期末权益P05/中位/P95：`{_safe_float(bootstrap_summary.get('end_balance_p05')):,.0f}` / `{_safe_float(bootstrap_summary.get('end_balance_median')):,.0f}` / `{_safe_float(bootstrap_summary.get('end_balance_p95')):,.0f}`",
        f"- 最大回撤P05/中位/P95：`{_safe_float(bootstrap_summary.get('max_dd_p05')):.4f}%` / `{_safe_float(bootstrap_summary.get('max_dd_median')):.4f}%` / `{_safe_float(bootstrap_summary.get('max_dd_p95')):.4f}%`",
        "",
        "## 汇总结论",
        "",
        f"- 随机AI池最优期末权益：`{summary['judgement']['placebo_best_end_balance']:,.0f}`",
        f"- 随机AI池中位期末权益：`{summary['judgement']['placebo_median_end_balance']:,.0f}`",
        f"- 随机AI池是否全部低于Stage78：`{summary['judgement']['placebo_all_below_stage78']}`",
        f"- 去复利/固定手数正收益率：`{summary['judgement']['sizing_positive_rate_pct']:.4f}%`",
        f"- 延迟执行正收益率：`{summary['judgement']['execution_delay_positive_rate_pct']:.4f}%`",
        "",
        "## 反思",
        "",
        f"- 运行前过拟合反思：{summary['judgement']['overfit_judgement_before']}",
        f"- 运行前继续价值反思：{summary['judgement']['continue_value_before']}",
        f"- 运行后过拟合反思：{summary['judgement']['overfit_judgement_after']}",
        f"- 运行后继续价值反思：{summary['judgement']['continue_value_after']}",
        "",
        "## 后续TODO",
        "",
        "- 不根据随机AI池胜负反向删品种或调TopN。",
        "- 若延迟执行压力明显坍塌，下一步专门做可成交价和限价失败审计。",
        "- 若本阶段通过，优先进入真实影子盘逐日ledger，而不是继续历史参数优化。",
    ]
    return "\n".join(lines)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    print("[stage153] start anti-fit validation", flush=True)
    placebo_df = run_placebo_ai_pool()
    sizing_df = run_sizing_invariance()
    execution_df = run_execution_delay()
    bootstrap_df = run_monthly_block_bootstrap()

    placebo_df.to_csv(PLACEBO_PATH, index=False, encoding="utf-8-sig")
    sizing_df.to_csv(SIZING_PATH, index=False, encoding="utf-8-sig")
    execution_df.to_csv(EXECUTION_PATH, index=False, encoding="utf-8-sig")
    if not bootstrap_df.empty:
        bootstrap_df.to_csv(BOOTSTRAP_PATH, index=False, encoding="utf-8-sig")

    summary = {
        "model_tag": MODEL_TAG,
        "official_version": OFFICIAL_STAGE78_VERSION,
        "official_role": OFFICIAL_STAGE78_ROLE,
        "capital": OFFICIAL_STAGE78_CAPITAL,
        "reference_metrics": OFFICIAL_STAGE78_REFERENCE_METRICS,
        "judgement": _build_judgement(placebo_df, sizing_df, execution_df, bootstrap_df),
        "outputs": {
            "placebo_ai_pool": str(PLACEBO_PATH),
            "sizing_invariance": str(SIZING_PATH),
            "execution_delay": str(EXECUTION_PATH),
            "monthly_block_bootstrap": str(BOOTSTRAP_PATH) if not bootstrap_df.empty else "",
            "report": str(REPORT_PATH),
        },
    }
    SUMMARY_JSON_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(build_report(placebo_df, sizing_df, execution_df, bootstrap_df, summary), encoding="utf-8")

    print(json.dumps(summary["judgement"], ensure_ascii=False, indent=2), flush=True)
    print(f"[stage153] report: {REPORT_PATH}", flush=True)


if __name__ == "__main__":
    main()
