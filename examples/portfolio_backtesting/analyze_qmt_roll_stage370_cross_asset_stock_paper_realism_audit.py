from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
ALPHA_DIR = PROJECT_DIR.parent / "alpha_research"
if str(ALPHA_DIR) not in sys.path:
    sys.path.insert(0, str(ALPHA_DIR))

import analyze_stock_range_reversion_liquid_q3_300k_lot_feasibility as lot_replay  # noqa: E402


OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
MODEL_TAG = "stage370_cross_asset_stock_paper_realism_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage370_cross_asset_stock_paper_realism_audit"

C3_DAILY_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage336_c3_cash_reserve_multiperiod_daily_stage336_c3_cash_reserve_multiperiod_v1.csv"
)
STAGE369_DAILY_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage369_cross_asset_stock_paper_combo_probe_daily_stage369_cross_asset_stock_paper_combo_probe_v1.csv"
)
STOCK_LEDGER_DIR = (
    PROJECT_DIR.parent
    / "alpha_research"
    / "native_results"
    / "stock_range_reversion_liquid_q3_paper_ledger_2018_2026"
)
STOCK_LEDGER_PREFIX = "stock_range_reversion_liquid_q3_paper_ledger_v1"
V3_DIR = (
    PROJECT_DIR.parent
    / "alpha_research"
    / "native_results"
    / "stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality_2018_2026"
)
V3_PREFIX = "stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality"
FALLBACK_AUDIT_DIR = (
    PROJECT_DIR.parent
    / "alpha_research"
    / "native_results"
    / "stock_range_reversion_liquid_q3_v3_fallback_audit_2018_2026"
)
FALLBACK_AUDIT_PREFIX = "stock_range_reversion_liquid_q3_v3_fallback_audit_v1"

INITIAL_CAPITAL = 500_000.0
BASE_PROFILE = "c3_active100_cash0"
BASE_WINDOW = "start_2020"
TRUE_STOCK_LEG_CAPITAL = 25_000.0
REALISM_ACCOUNT_SIZES = (25_000.0, 50_000.0, 100_000.0, 250_000.0, 300_000.0, 1_000_000.0)
TRUE_SPLIT_C3_WEIGHT = 0.95
TRUE_SPLIT_STOCK_WEIGHT = 0.05
PASS_MAX_DD = -30.0
PASS_RETURN_RETENTION = 80.0


@dataclass(frozen=True)
class SeriesStats:
    variant: str
    label: str
    days: int
    start_date: str
    end_date: str
    end_nav: float
    total_return_pct: float
    max_dd_percent: float
    sharpe: float
    ulcer: float
    longest_underwater_days: int


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _max_drawdown(nav: pd.Series) -> float:
    if nav.empty:
        return 0.0
    return float((nav / nav.cummax() - 1.0).min())


def _ulcer(nav: pd.Series) -> float:
    if nav.empty:
        return 0.0
    dd_pct = (nav / nav.cummax() - 1.0) * 100.0
    return float(np.sqrt(np.mean(np.square(np.minimum(dd_pct, 0.0)))))


def _longest_underwater(nav: pd.Series) -> int:
    longest = 0
    current = 0
    for value in nav / nav.cummax() - 1.0:
        if value < -1e-12:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return int(longest)


def _annualized_sharpe(daily_ret: pd.Series) -> float:
    daily_ret = daily_ret.dropna().astype(float)
    if len(daily_ret) < 2:
        return 0.0
    std = float(daily_ret.std(ddof=1))
    if std <= 0:
        return 0.0
    return float(daily_ret.mean() / std * math.sqrt(252.0))


def _stats(variant: str, label: str, daily_ret: pd.Series) -> SeriesStats:
    daily_ret = daily_ret.fillna(0.0).astype(float)
    nav = (1.0 + daily_ret).cumprod()
    if nav.empty:
        return SeriesStats(variant, label, 0, "", "", 1.0, 0.0, 0.0, 0.0, 0.0, 0)
    return SeriesStats(
        variant=variant,
        label=label,
        days=int(len(daily_ret)),
        start_date=str(daily_ret.index.min().date()),
        end_date=str(daily_ret.index.max().date()),
        end_nav=float(nav.iloc[-1]),
        total_return_pct=float((nav.iloc[-1] - 1.0) * 100.0),
        max_dd_percent=_max_drawdown(nav) * 100.0,
        sharpe=_annualized_sharpe(daily_ret),
        ulcer=_ulcer(nav),
        longest_underwater_days=_longest_underwater(nav),
    )


def _load_c3_ret() -> pd.Series:
    df = pd.read_csv(C3_DAILY_PATH)
    df = df[(df["profile"] == BASE_PROFILE) & (df["window_name"] == BASE_WINDOW)].copy()
    if df.empty:
        raise ValueError(f"missing {BASE_PROFILE}/{BASE_WINDOW} in {C3_DAILY_PATH}")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df[df["date"].notna()].sort_values("date")
    balance = pd.to_numeric(df["balance"], errors="coerce").ffill()
    ret = balance.pct_change()
    ret.iloc[0] = balance.iloc[0] / INITIAL_CAPITAL - 1.0
    ret.index = pd.DatetimeIndex(df["date"])
    return ret.astype(float)


def _load_stage369_ret(variant: str) -> pd.Series:
    df = pd.read_csv(STAGE369_DAILY_PATH)
    df = df[df["variant"] == variant].copy()
    if df.empty:
        raise ValueError(f"missing {variant} in {STAGE369_DAILY_PATH}")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df[df["date"].notna()].sort_values("date")
    ret = pd.to_numeric(df["daily_ret"], errors="coerce").fillna(0.0)
    ret.index = pd.DatetimeIndex(df["date"])
    return ret.astype(float)


def _align_pair(left: pd.Series, right: pd.Series) -> pd.DataFrame:
    start = max(left.index.min(), right.index.min(), pd.Timestamp("2020-01-01"))
    end = min(left.index.max(), right.index.max())
    index = pd.date_range(start=start, end=end, freq="D")
    frame = pd.DataFrame(index=index)
    frame["left"] = left.groupby(level=0).sum().reindex(index).fillna(0.0)
    frame["right"] = right.groupby(level=0).sum().reindex(index).fillna(0.0)
    return frame


def _build_stock_lot_replays() -> tuple[pd.DataFrame, pd.DataFrame]:
    selected_all = lot_replay.pl.read_parquet(
        lot_replay.FILTER_OUTPUT_DIR / f"{lot_replay.FILTER_PREFIX}_selected_all.parquet"
    )
    stock_df, benchmark_df = lot_replay.load_panels()
    target_weights = lot_replay.build_target_weights(selected_all)
    target_maps = lot_replay.build_target_maps(target_weights)
    dates = lot_replay.build_tracking_dates(target_weights, benchmark_df)
    exec_info = lot_replay.build_exec_info(stock_df)

    summary_rows: list[dict[str, Any]] = []
    daily_frames: list[pd.DataFrame] = []
    original_account_size = lot_replay.ACCOUNT_SIZE_CNY
    try:
        for account_size in REALISM_ACCOUNT_SIZES:
            lot_replay.ACCOUNT_SIZE_CNY = account_size
            orders, daily, _ = lot_replay.replay_lot_account(target_maps, dates, exec_info)
            summary = lot_replay.summarize_orders(orders, daily)
            summary_rows.append(summary)
            daily_pd = daily.to_pandas()
            daily_pd["date"] = pd.to_datetime(daily_pd["date"], errors="coerce")
            daily_pd = daily_pd[daily_pd["date"].notna()].copy()
            daily_pd["account_size_cny"] = account_size
            daily_frames.append(
                daily_pd[
                    [
                        "date",
                        "account_size_cny",
                        "strategy_daily_ret_bps_only",
                        "strategy_daily_ret_min_fee",
                        "equity_min_fee",
                        "drawdown_min_fee",
                        "target_symbol_count",
                        "zero_lot_target_count",
                        "actual_symbol_count",
                        "actual_gross_weight",
                        "target_amount_sum_cny",
                        "rounded_target_amount_sum_cny",
                        "filled_amount_sum_cny",
                        "blocked_order_count",
                    ]
                ]
            )
    finally:
        lot_replay.ACCOUNT_SIZE_CNY = original_account_size
    return pd.DataFrame(summary_rows), pd.concat(daily_frames, ignore_index=True)


def _account_combo_summary(c3_ret: pd.Series, lot_daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    base_stock_group = lot_daily[lot_daily["account_size_cny"].eq(TRUE_STOCK_LEG_CAPITAL)].copy()
    base_stock_ret = pd.to_numeric(base_stock_group["strategy_daily_ret_min_fee"], errors="coerce").fillna(0.0)
    base_stock_ret.index = pd.DatetimeIndex(base_stock_group["date"])
    base_aligned = _align_pair(c3_ret, base_stock_ret)
    c3_common_ret = base_aligned["left"]
    c3_stats = _stats("A_c3_100", "C3 100%", c3_common_ret)
    cash_control = _stats(
        "cash_control_c3_95_cash_05",
        "C3 95% + 现金 5%",
        TRUE_SPLIT_C3_WEIGHT * c3_common_ret,
    )
    rows.append(c3_stats.__dict__)
    rows.append(cash_control.__dict__)

    for account_size, group in lot_daily.groupby("account_size_cny"):
        stock_ret = pd.to_numeric(group["strategy_daily_ret_min_fee"], errors="coerce").fillna(0.0)
        stock_ret.index = pd.DatetimeIndex(group["date"])
        aligned = _align_pair(c3_ret, stock_ret)
        combo_ret = TRUE_SPLIT_C3_WEIGHT * aligned["left"] + TRUE_SPLIT_STOCK_WEIGHT * aligned["right"]
        stock_stats = _stats(
            f"stock_lot_{int(account_size)}",
            f"股票整手账户 {account_size:,.0f} 元",
            aligned["right"],
        )
        combo_stats = _stats(
            f"combo_c3_95_stock_lot_{int(account_size)}_05",
            f"C3 95% + 股票整手账户{account_size:,.0f}元收益 5%",
            combo_ret,
        )
        stock_row = stock_stats.__dict__
        stock_row["return_retention_vs_c3_pct"] = (
            stock_stats.total_return_pct / c3_stats.total_return_pct * 100.0
            if c3_stats.total_return_pct
            else 0.0
        )
        rows.append(stock_row)
        combo_row = combo_stats.__dict__
        combo_row["return_retention_vs_c3_pct"] = (
            combo_stats.total_return_pct / c3_stats.total_return_pct * 100.0
            if c3_stats.total_return_pct
            else 0.0
        )
        combo_row["beats_same_weight_cash_return"] = combo_stats.total_return_pct > cash_control.total_return_pct
        combo_row["beats_same_weight_cash_dd"] = combo_stats.max_dd_percent > cash_control.max_dd_percent
        combo_row["passes_drawdown30"] = combo_stats.max_dd_percent >= PASS_MAX_DD
        combo_row["passes_return_retention80"] = combo_row["return_retention_vs_c3_pct"] >= PASS_RETURN_RETENTION
        rows.append(combo_row)
    return pd.DataFrame(rows)


def _audit_summary(
    stock_ledger_summary: dict[str, Any],
    v3_summary: dict[str, Any],
    fallback_summary: dict[str, Any],
    account_summary: pd.DataFrame,
    combo_summary: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    true_account = account_summary[
        account_summary["account_size_cny"].astype(float).round(6) == TRUE_STOCK_LEG_CAPITAL
    ].iloc[0]
    true_combo = combo_summary[
        combo_summary["variant"].eq(f"combo_c3_95_stock_lot_{int(TRUE_STOCK_LEG_CAPITAL)}_05")
    ].iloc[0]
    cash_combo = combo_summary[combo_summary["variant"].eq("cash_control_c3_95_cash_05")].iloc[0]
    paper_combo = _stats("stage369_paper_combo", "Stage369 paper combo", _load_stage369_ret("C_c3_95_stock_05"))

    checkpoints = [
        {
            "checkpoint": "paper_ledger_quality_fail_zero",
            "status": "pass" if int(stock_ledger_summary.get("quality_fail_count", -1)) == 0 else "fail",
            "value": stock_ledger_summary.get("quality_fail_count"),
            "expected": 0,
            "note": "股票paper账本质量检查不应有失败项。",
        },
        {
            "checkpoint": "v3_exante_fill_ratio_above_99pct",
            "status": "pass" if _safe_float(v3_summary.get("overall_fill_ratio")) >= 0.99 else "fail",
            "value": v3_summary.get("overall_fill_ratio"),
            "expected": ">=0.99",
            "note": "v3使用交易前可知ADV口径后，成交填充率仍需足够高。",
        },
        {
            "checkpoint": "fallback_audit_pass",
            "status": "pass" if _safe_float(fallback_summary.get("audit_pass_ratio")) == 1.0 else "fail",
            "value": fallback_summary.get("audit_pass_ratio"),
            "expected": 1.0,
            "note": "fallback ADV订单复算需100%通过，避免同日成交额偷看。",
        },
        {
            "checkpoint": "fallback_not_current_turnover",
            "status": "pass" if int(fallback_summary.get("current_turnover_exact_match_orders", -1)) == 0 else "fail",
            "value": fallback_summary.get("current_turnover_exact_match_orders"),
            "expected": 0,
            "note": "fallback不应等同当日成交额。",
        },
        {
            "checkpoint": "true_25k_lot_rounding_tolerable",
            "status": "pass" if _safe_float(true_account.get("zero_lot_target_ratio")) < 0.10 else "fail",
            "value": f"{_safe_float(true_account.get('zero_lot_target_ratio')):.2%}",
            "expected": "<10%",
            "note": "50万账户5%股票腿只有2.5万；若大量目标买不到一手，原paper曲线不可直接承载。",
        },
        {
            "checkpoint": "true_25k_latest_diversification_tolerable",
            "status": "pass" if int(true_account.get("latest_actual_symbol_count", 0)) >= 15 else "fail",
            "value": true_account.get("latest_actual_symbol_count"),
            "expected": ">=15",
            "note": "最新目标日需要保留足够分散，否则股票腿变成少数票暴露。",
        },
        {
            "checkpoint": "true_25k_combo_drawdown30",
            "status": "pass" if bool(true_combo.get("passes_drawdown30")) else "fail",
            "value": f"{_safe_float(true_combo.get('max_dd_percent')):.4f}%",
            "expected": ">=-30%",
            "note": "真实2.5万整手股票腿组合路径仍需满足回撤闸门。",
        },
        {
            "checkpoint": "true_25k_combo_return_retention80",
            "status": "pass" if bool(true_combo.get("passes_return_retention80")) else "fail",
            "value": f"{_safe_float(true_combo.get('return_retention_vs_c3_pct')):.4f}%",
            "expected": ">=80%",
            "note": "真实2.5万整手股票腿不能显著牺牲C3收益。",
        },
        {
            "checkpoint": "true_25k_combo_beats_cash",
            "status": "pass"
            if bool(true_combo.get("beats_same_weight_cash_return"))
            and bool(true_combo.get("beats_same_weight_cash_dd"))
            else "fail",
            "value": (
                f"ret {true_combo['total_return_pct']:.4f}% vs cash {cash_combo['total_return_pct']:.4f}%; "
                f"dd {true_combo['max_dd_percent']:.4f}% vs cash {cash_combo['max_dd_percent']:.4f}%"
            ),
            "expected": "return and drawdown both better than cash",
            "note": "否则说明改善主要来自现金稀释，不来自可承载股票腿。",
        },
        {
            "checkpoint": "paper_to_true_25k_gap_small",
            "status": "pass"
            if abs(paper_combo.max_dd_percent - _safe_float(true_combo.get("max_dd_percent"))) <= 1.0
            else "warn",
            "value": (
                f"paper dd {paper_combo.max_dd_percent:.4f}%; "
                f"25k dd {true_combo['max_dd_percent']:.4f}%"
            ),
            "expected": "dd gap <=1pp preferred",
            "note": "该项是偏差提示；不是硬否决，但偏差大时不能直接沿用Stage369结论。",
        },
    ]
    decision = {
        "model_tag": MODEL_TAG,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "paper_combo_total_return_pct": paper_combo.total_return_pct,
        "paper_combo_max_dd_percent": paper_combo.max_dd_percent,
        "true_25k_combo_total_return_pct": _safe_float(true_combo.get("total_return_pct")),
        "true_25k_combo_max_dd_percent": _safe_float(true_combo.get("max_dd_percent")),
        "true_25k_combo_return_retention_vs_c3_pct": _safe_float(
            true_combo.get("return_retention_vs_c3_pct")
        ),
        "true_25k_zero_lot_target_ratio": _safe_float(true_account.get("zero_lot_target_ratio")),
        "true_25k_latest_actual_symbol_count": int(true_account.get("latest_actual_symbol_count", 0)),
        "cash_control_total_return_pct": _safe_float(cash_combo.get("total_return_pct")),
        "cash_control_max_dd_percent": _safe_float(cash_combo.get("max_dd_percent")),
    }
    fail_count = sum(1 for item in checkpoints if item["status"] == "fail")
    warn_count = sum(1 for item in checkpoints if item["status"] == "warn")
    if fail_count:
        decision["decision"] = "fail_true_50w_split_stock_leg_not_realistically_portable"
    elif warn_count:
        decision["decision"] = "conditional_candidate_needs_forward_paper_and_capital_review"
    else:
        decision["decision"] = "candidate_passes_initial_realism_audit"
    return pd.DataFrame(checkpoints), decision


def _format_table(df: pd.DataFrame, columns: list[str], max_rows: int = 30) -> str:
    if df.empty:
        return "无数据"
    return df.loc[:, [col for col in columns if col in df.columns]].head(max_rows).to_markdown(index=False)


def _write_report(
    account_summary: pd.DataFrame,
    combo_summary: pd.DataFrame,
    checkpoints: pd.DataFrame,
    decision: dict[str, Any],
    paths: dict[str, Path],
) -> None:
    true_combo = combo_summary[
        combo_summary["variant"].eq(f"combo_c3_95_stock_lot_{int(TRUE_STOCK_LEG_CAPITAL)}_05")
    ].iloc[0]
    cash_combo = combo_summary[combo_summary["variant"].eq("cash_control_c3_95_cash_05")].iloc[0]
    lines = [
        "# Stage370 跨资产股票paper真实性复核",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        f"- 模型标签：`{MODEL_TAG}`",
        "- 阶段性质：Stage069候选真实性复核；不新增交易信号、不调权重、不修改C3或股票paper参数。",
        "- 核心问题：Stage069的`95%C3+5%股票paper`是否能在50万账户里以`47.5万C3 + 2.5万股票腿`真实承载。",
        "",
        "## 外部调研与判断",
        "",
        "- 多资产分散有明确先验，但金融回测容易受到多重测试和纸面成交假设污染；因此本阶段只做真实性审计，不做参数救援。",
        "- 股票市场买入至少一手的制度约束会让小资金股票腿显著偏离权重账本。若2.5万无法买出足够分散度，Stage069只能保留为净值层研究线索。",
        "- 参考：AQR managed futures资料强调跨资产低相关分散；Novy-Marx/NBER和Harvey-Liu等研究提醒多信号回测存在过拟合与多重检验风险。",
        "",
        "## 审计结论",
        "",
        f"- 决策：`{decision['decision']}`。",
        f"- 账面paper组合：总收益`{decision['paper_combo_total_return_pct']:.4f}%`，最大回撤`{decision['paper_combo_max_dd_percent']:.4f}%`。",
        f"- 真实2.5万股票腿整手组合：总收益`{decision['true_25k_combo_total_return_pct']:.4f}%`，最大回撤`{decision['true_25k_combo_max_dd_percent']:.4f}%`，C3收益保留`{decision['true_25k_combo_return_retention_vs_c3_pct']:.4f}%`。",
        f"- 同权重现金对照：总收益`{cash_combo['total_return_pct']:.4f}%`，最大回撤`{cash_combo['max_dd_percent']:.4f}%`。",
        f"- 2.5万股票腿目标买不到一手比例：`{decision['true_25k_zero_lot_target_ratio']:.2%}`；最新实际持仓数：`{decision['true_25k_latest_actual_symbol_count']}`。",
        "",
        "## 检查点",
        "",
        _format_table(checkpoints, ["checkpoint", "status", "value", "expected", "note"], 50),
        "",
        "## 股票整手账户压力",
        "",
        _format_table(
            account_summary,
            [
                "account_size_cny",
                "total_return_min_fee",
                "max_drawdown_min_fee",
                "sharpe_min_fee",
                "zero_lot_target_ratio",
                "latest_target_symbol_count",
                "latest_actual_symbol_count",
                "latest_zero_lot_target_count",
                "latest_actual_gross_weight",
            ],
            20,
        ),
        "",
        "## 组合路径对比",
        "",
        _format_table(
            combo_summary[
                combo_summary["variant"].isin(
                    [
                        "A_c3_100",
                        "cash_control_c3_95_cash_05",
                        f"combo_c3_95_stock_lot_{int(TRUE_STOCK_LEG_CAPITAL)}_05",
                        "combo_c3_95_stock_lot_300000_05",
                    ]
                )
            ],
            [
                "variant",
                "label",
                "total_return_pct",
                "max_dd_percent",
                "return_retention_vs_c3_pct",
                "sharpe",
                "ulcer",
                "beats_same_weight_cash_return",
                "beats_same_weight_cash_dd",
            ],
            20,
        ),
        "",
        "## 运行前过拟合反思",
        "",
        "- 判断：否。",
        "- 原因：本阶段只做真实性审计和资金颗粒度复盘，不新增参数、不改变权重、不选择更好窗口。",
        "",
        "## 运行后过拟合反思",
        "",
        "- 判断：否。",
        "- 原因：结果反而暴露了Stage069的真实资金承载问题，没有因为结果不理想继续调权重或救股票腿参数。",
        "",
        "## 运行前继续价值反思",
        "",
        "- 判断：是。",
        "- 原因：Stage069是当前最接近目标的候选，必须先确认是否真实可执行。",
        "",
        "## 运行后继续价值反思",
        "",
        "- 判断：有价值但路线需要降级。",
        "- 原因：跨资产低相关思路仍成立；但2.5万股票腿不能直接复刻1000万paper账本，后续应转向真实可承载工具或更大独立股票资金，而不是继续用50万内5%股票腿替代现金。",
        "",
        "## 下一步",
        "",
        "- 不把Stage069直接升级为50万正式候选。",
        "- 若继续股票腿，只能做两个方向：一是独立股票账户资金不低于30万的组合层方案；二是寻找可小资金承载的ETF/指数/期权/期货化低相关工具。",
        "- 不扫`4%/6%/7%`股票权重，也不调股票paper内部参数。",
        "",
        "## 输出文件",
        "",
    ]
    for name, path in paths.items():
        lines.append(f"- `{name}`：`{path}`")
    paths["report"].write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stock_ledger_summary = _load_json(STOCK_LEDGER_DIR / f"{STOCK_LEDGER_PREFIX}_summary.json")
    v3_summary = _load_json(V3_DIR / f"{V3_PREFIX}_summary.json")
    fallback_summary = _load_json(FALLBACK_AUDIT_DIR / f"{FALLBACK_AUDIT_PREFIX}_summary.json")

    c3_ret = _load_c3_ret()
    account_summary, account_daily = _build_stock_lot_replays()
    combo_summary = _account_combo_summary(c3_ret, account_daily)
    checkpoints, decision = _audit_summary(
        stock_ledger_summary,
        v3_summary,
        fallback_summary,
        account_summary,
        combo_summary,
    )

    paths = {
        "report": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md",
        "account_summary": OUTPUT_DIR / f"{OUTPUT_PREFIX}_account_summary_{MODEL_TAG}.csv",
        "combo_summary": OUTPUT_DIR / f"{OUTPUT_PREFIX}_combo_summary_{MODEL_TAG}.csv",
        "account_daily": OUTPUT_DIR / f"{OUTPUT_PREFIX}_account_daily_{MODEL_TAG}.csv",
        "checkpoints": OUTPUT_DIR / f"{OUTPUT_PREFIX}_checkpoints_{MODEL_TAG}.csv",
        "decision": OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json",
    }
    account_summary.to_csv(paths["account_summary"], index=False, encoding="utf-8-sig")
    combo_summary.to_csv(paths["combo_summary"], index=False, encoding="utf-8-sig")
    account_daily.to_csv(paths["account_daily"], index=False, encoding="utf-8-sig")
    checkpoints.to_csv(paths["checkpoints"], index=False, encoding="utf-8-sig")
    paths["decision"].write_text(json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(account_summary, combo_summary, checkpoints, decision, paths)
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    print(f"report={paths['report']}")


if __name__ == "__main__":
    main()
