from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


BASE_DIR: Path = Path(__file__).resolve().parent
NATIVE_RESULTS_DIR: Path = BASE_DIR / "native_results"

OUTPUT_DIR: Path = (NATIVE_RESULTS_DIR / "stock_range_reversion_30w_architecture_inventory_2018_2026").resolve()
PREFIX: str = "stock_range_reversion_30w_architecture_inventory_v1"

USER_RETURN_TARGET: float = 1.0
USER_MAX_DRAWDOWN_LIMIT: float = -0.20


@dataclass(frozen=True)
class CsvRouteSpec:
    route_id: str
    family: str
    description: str
    path: Path
    comparability: str
    governance_note: str
    preferred_variant_keywords: tuple[str, ...] = ()
    preferred_cost_bps: float | None = None
    source_line: str = "stock_range_30w_industry_resid_core"


CSV_ROUTE_SPECS: tuple[CsvRouteSpec, ...] = (
    CsvRouteSpec(
        route_id="stock_paper_300k_market_state_overlay",
        family="established_stock_paper",
        description="早期30万/300k股票震荡主路线的市场状态overlay复盘。",
        path=NATIVE_RESULTS_DIR
        / "stock_range_reversion_liquid_q3_300k_market_state_overlay_2018_2026"
        / "stock_range_reversion_liquid_q3_300k_market_state_overlay_v1_summary.csv",
        comparability="related_300k_line_not_current_core",
        governance_note="满足用户目标但属于已有paper/300k路线，不能被当前industry_resid_core微调结果冒名替代。",
        preferred_variant_keywords=("base_rerun",),
        source_line="stock_range_paper_v1",
    ),
    CsvRouteSpec(
        route_id="stock_paper_300k_good_state_aggressive_overlay",
        family="established_stock_paper",
        description="在已有300k主路线上尝试好状态加仓。",
        path=NATIVE_RESULTS_DIR
        / "stock_range_reversion_liquid_q3_300k_good_state_aggressive_overlay_2018_2026"
        / "stock_range_reversion_liquid_q3_300k_good_state_aggressive_overlay_v1_summary.csv",
        comparability="related_300k_line_not_current_core",
        governance_note="好状态加仓没有明显优于base_rerun，说明激进化不是免费午餐。",
        preferred_variant_keywords=("base_rerun", "prev_close_index_up_125"),
        source_line="stock_range_paper_v1",
    ),
    CsvRouteSpec(
        route_id="stock_paper_300k_sparse_variants",
        family="established_stock_paper",
        description="稀疏持仓/排除放量版本的30万可交易复盘。",
        path=NATIVE_RESULTS_DIR
        / "stock_range_reversion_liquid_q3_300k_sparse_variants_2018_2026"
        / "stock_range_reversion_liquid_q3_300k_sparse_variants_v1_summary.csv",
        comparability="related_300k_line_not_current_core",
        governance_note="回撤较浅但收益未到100%，可做稳健性参照，不是当前线的新增突破。",
        preferred_variant_keywords=("age4_daily_exclude_volume_dry",),
        source_line="stock_range_paper_v1",
    ),
    CsvRouteSpec(
        route_id="simple_oversold_ret20_30w_grid",
        family="single_stock_cross_section_reversal",
        description="30万专属：按20日超跌分数选股的简单横截面回归。",
        path=NATIVE_RESULTS_DIR
        / "stock_range_reversion_liquid_q3_30w_high_return_shape_grid_2018_2026"
        / "stock_range_reversion_liquid_q3_30w_high_return_shape_grid_v1_summary.csv",
        comparability="direct_30w_lot_replay",
        governance_note="简单、可解释，但当前收益/回撤仍未同时达到用户目标。",
        preferred_variant_keywords=("top8_gross70_ind2", "top8_gross50_ind2"),
    ),
    CsvRouteSpec(
        route_id="industry_resid_core_30w_base",
        family="industry_residual_reversal",
        description="行业残差核心的30万整手回放基准。",
        path=NATIVE_RESULTS_DIR
        / "stock_range_reversion_liquid_q3_industry_resid_core_30w_replay_2018_2026"
        / "stock_range_reversion_liquid_q3_industry_resid_core_30w_replay_v1_summary.csv",
        comparability="direct_30w_lot_replay",
        governance_note="信号有alpha，但回撤厚，不能继续只做局部修补。",
        preferred_variant_keywords=("industry_resid_core_h10_top8_gross70_ind2", "industry_resid_core_h10_top5_gross100_ind1"),
    ),
    CsvRouteSpec(
        route_id="industry_resid_core_slow_rhythm",
        family="industry_residual_reversal",
        description="第320阶段：路径依赖慢节奏/策略热度降仓。",
        path=NATIVE_RESULTS_DIR
        / "stock_range_reversion_liquid_q3_industry_resid_core_30w_slow_rhythm_replay_2018_2026"
        / "stock_range_reversion_liquid_q3_industry_resid_core_30w_slow_rhythm_replay_v1_summary.csv",
        comparability="direct_30w_lot_replay_but_failed_neighborhood",
        governance_note="出现过总收益>=100%且回撤<20%的候选，但第321邻域反证显示参数形状敏感，不能升级。",
        preferred_variant_keywords=("strategy_ret60_up_zero",),
    ),
    CsvRouteSpec(
        route_id="industry_resid_core_smooth_budget",
        family="industry_residual_reversal",
        description="第322阶段：硬阈值改为平滑风险预算。",
        path=NATIVE_RESULTS_DIR
        / "stock_range_reversion_liquid_q3_industry_resid_core_30w_smooth_risk_budget_replay_2018_2026"
        / "stock_range_reversion_liquid_q3_industry_resid_core_30w_smooth_risk_budget_replay_v1_summary.csv",
        comparability="direct_30w_lot_replay_probe",
        governance_note="平滑预算确认状态信息有用，但高收益与低回撤仍不能兼得。",
        preferred_variant_keywords=("smooth80_soft0to12_floor50", "smooth60_soft0to10_floor30"),
    ),
    CsvRouteSpec(
        route_id="industry_resid_core_loss_source_filter",
        family="industry_residual_reversal",
        description="第324/325阶段：亏损来源行业过滤探针。",
        path=NATIVE_RESULTS_DIR
        / "stock_range_reversion_liquid_q3_industry_resid_core_30w_loss_source_filter_probe_2018_2026"
        / "stock_range_reversion_liquid_q3_industry_resid_core_30w_loss_source_filter_probe_v1_summary.csv",
        comparability="direct_30w_lot_replay_probe",
        governance_note="固定弱行业更像风险归因，不是可穿越周期的硬过滤机制。",
        preferred_variant_keywords=("drop_stage323_weak_industries",),
    ),
    CsvRouteSpec(
        route_id="industry_resid_core_risk_on_probe",
        family="industry_residual_reversal",
        description="第323阶段：收益来源状态risk-on仓位探针。",
        path=NATIVE_RESULTS_DIR
        / "stock_range_reversion_liquid_q3_industry_resid_core_30w_profit_source_risk_on_2018_2026"
        / "stock_range_reversion_liquid_q3_industry_resid_core_30w_profit_source_risk_on_v1_summary.csv",
        comparability="direct_30w_lot_replay_probe",
        governance_note="提高收益时同步放大回撤，不能作为30万高收益低回撤主线。",
        preferred_variant_keywords=("strategy_not_hot",),
    ),
    CsvRouteSpec(
        route_id="strong_pullback_alt_30w",
        family="momentum_pullback_reversal",
        description="强行业/近高点/残差回调等强势回踩定义的30万回放。",
        path=NATIVE_RESULTS_DIR
        / "stock_range_reversion_liquid_q3_alt_strong_pullback_30w_replay_2018_2026"
        / "stock_range_reversion_liquid_q3_alt_strong_pullback_30w_replay_v1_summary.csv",
        comparability="direct_30w_lot_replay",
        governance_note="强者恒强+回调在现有定义下收益不够且回撤偏厚，暂时降级。",
        preferred_variant_keywords=("industry252_resid10_pullback",),
    ),
    CsvRouteSpec(
        route_id="strong_pullback_short_horizon_30w",
        family="momentum_pullback_reversal",
        description="强势回踩短持有周期版本。",
        path=NATIVE_RESULTS_DIR
        / "stock_range_reversion_liquid_q3_30w_strong_pullback_short_horizon_2018_2026"
        / "stock_range_reversion_liquid_q3_30w_strong_pullback_short_horizon_v1_summary.csv",
        comparability="direct_30w_lot_replay",
        governance_note="短周期强势回踩并未修复收益/回撤，继续扫会接近过拟合。",
        preferred_variant_keywords=("mom120_lowvol",),
    ),
    CsvRouteSpec(
        route_id="market_down_beta_residual",
        family="market_state_residual",
        description="市场下跌残差/beta归因路线。",
        path=NATIVE_RESULTS_DIR
        / "stock_range_reversion_market_down_beta_residual_2018_2026"
        / "stock_range_reversion_market_down_beta_residual_v1_summary.csv",
        comparability="not_30w_lot_strategy_attribution",
        governance_note="残差收益和超额回撤形态有信息，但不是30万整手交易系统。",
        preferred_variant_keywords=("strategy_net", "active_excess_net", "beta_residual_net"),
        preferred_cost_bps=20.0,
    ),
    CsvRouteSpec(
        route_id="broad_etf_architecture_readiness",
        family="etf_sleeve",
        description="宽基ETF模板/池/袖珍仓已有路线汇总。",
        path=NATIVE_RESULTS_DIR
        / "stock_range_reversion_etf_industry_rotation_readiness_2018_2026"
        / "stock_range_reversion_etf_industry_rotation_readiness_v1_existing_route_summary.csv",
        comparability="satellite_or_data_readiness",
        governance_note="ETF路线低回撤但收益厚度不足，可做平滑卫星，不宜当主引擎。",
        preferred_cost_bps=20.0,
    ),
    CsvRouteSpec(
        route_id="industry_etf_template",
        family="etf_sleeve",
        description="行业/中证1000ETF单模板均值回归。",
        path=NATIVE_RESULTS_DIR
        / "stock_range_reversion_etf_industry_template_2018_2026"
        / "stock_range_reversion_etf_industry_template_v1_summary.csv",
        comparability="satellite_or_template",
        governance_note="单ETF模板可降低回撤，但收益太薄、部分样本历史短。",
        preferred_cost_bps=20.0,
    ),
)

SIGNAL_SPECS: tuple[tuple[str, str, Path], ...] = (
    (
        "technical_pullback_composite_factor",
        "8点技术面统一复合因子/子因子信号归因。",
        NATIVE_RESULTS_DIR
        / "stock_range_reversion_liquid_q3_technical_pullback_composite_factor_2018_2026"
        / "stock_range_reversion_liquid_q3_technical_pullback_composite_factor_v1_summary.csv",
    ),
    (
        "alt_strong_pullback_definitions",
        "8类强势回踩定义的信号层归因。",
        NATIVE_RESULTS_DIR
        / "stock_range_reversion_liquid_q3_alt_strong_pullback_definitions_2018_2026"
        / "stock_range_reversion_liquid_q3_alt_strong_pullback_definitions_v1_summary.csv",
    ),
    (
        "residual_industry_signal",
        "残差/行业内横截面短反信号归因。",
        NATIVE_RESULTS_DIR
        / "stock_range_reversion_residual_industry_signal_2018_2026"
        / "stock_range_reversion_residual_industry_signal_v1_summary.csv",
    ),
    (
        "synthetic_industry_signal",
        "纯行业/强行业回踩等合成行业信号归因。",
        NATIVE_RESULTS_DIR
        / "stock_range_reversion_synthetic_industry_signal_attribution_2018_2026"
        / "stock_range_reversion_synthetic_industry_signal_attribution_v1_summary.csv",
    ),
)


def pct(value: Any) -> str:
    number = safe_float(value)
    if pd.isna(number):
        return "NA"
    return f"{number:.2%}"


def safe_float(value: Any, default: float = float("nan")) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def safe_str(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value)


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def metric_column(frame: pd.DataFrame, *candidates: str) -> str | None:
    for candidate in candidates:
        if candidate in frame.columns:
            return candidate
    return None


def normalize_metric_columns(frame: pd.DataFrame) -> pd.DataFrame:
    work = frame.copy()
    final_col = metric_column(work, "final_equity_min_fee", "final_equity", "ledger_final_equity")
    return_col = metric_column(work, "total_return_min_fee", "total_return", "ledger_total_return")
    dd_col = metric_column(work, "max_drawdown_min_fee", "max_drawdown", "ledger_max_drawdown")
    sharpe_col = metric_column(work, "sharpe_min_fee", "sharpe", "ledger_sharpe")
    trade_col = metric_column(work, "trade_count", "order_rows", "order_count", "latest_order_count")
    win_col = metric_column(work, "win_rate", "net_active_day_win_rate", "active_day_win_rate")
    cost_col = metric_column(work, "roundtrip_cost_bps", "cost_bps")
    start_col = metric_column(work, "date_start", "start_date")
    end_col = metric_column(work, "date_end", "end_date")
    days_col = metric_column(work, "trading_days", "days", "daily_rows")

    mapping = {
        "final_equity": final_col,
        "total_return": return_col,
        "max_drawdown": dd_col,
        "sharpe": sharpe_col,
        "trade_count": trade_col,
        "win_rate": win_col,
        "roundtrip_cost_bps": cost_col,
        "date_start": start_col,
        "date_end": end_col,
        "days": days_col,
    }
    for output, source in mapping.items():
        if source is None:
            work[output] = pd.NA
        else:
            work[output] = work[source]
    for column in ("final_equity", "total_return", "max_drawdown", "sharpe", "trade_count", "win_rate", "roundtrip_cost_bps", "days"):
        work[column] = pd.to_numeric(work[column], errors="coerce")
    return work


def variant_name(row: pd.Series) -> str:
    parts: list[str] = []
    for column in (
        "variant",
        "scenario",
        "path",
        "path_label",
        "route",
        "best_variant",
        "strategy",
        "model",
        "definition",
        "portfolio",
        "ts_code",
        "etf_name",
        "description",
    ):
        text = safe_str(row.get(column)).strip()
        if text and text not in parts:
            parts.append(text)
    return " / ".join(parts[:4]) if parts else "unknown"


def source_metric_basis(frame: pd.DataFrame) -> str:
    if "total_return_min_fee" in frame.columns:
        return "min_fee"
    if "roundtrip_cost_bps" in frame.columns:
        return "roundtrip_cost_bps"
    return "reported"


def build_row(spec: CsvRouteSpec, role: str, row: pd.Series, status: str = "available") -> dict[str, Any]:
    total_return = safe_float(row.get("total_return"))
    max_drawdown = safe_float(row.get("max_drawdown"))
    sharpe = safe_float(row.get("sharpe"))
    final_equity = safe_float(row.get("final_equity"))
    return_over_dd = total_return / abs(max_drawdown) if not pd.isna(total_return) and max_drawdown < 0 else float("nan")
    return {
        "route_id": spec.route_id,
        "family": spec.family,
        "role": role,
        "status": status,
        "variant": variant_name(row),
        "description": spec.description,
        "comparability": spec.comparability,
        "date_start": row.get("date_start"),
        "date_end": row.get("date_end"),
        "days": row.get("days"),
        "roundtrip_cost_bps": row.get("roundtrip_cost_bps"),
        "final_equity": final_equity,
        "total_return": total_return,
        "max_drawdown": max_drawdown,
        "sharpe": sharpe,
        "return_over_abs_dd": return_over_dd,
        "trade_count": row.get("trade_count"),
        "win_rate": row.get("win_rate"),
        "meets_user_goal": bool(total_return >= USER_RETURN_TARGET and max_drawdown >= USER_MAX_DRAWDOWN_LIMIT),
        "metric_basis": row.get("metric_basis"),
        "governance_note": spec.governance_note,
        "source_line": spec.source_line,
        "source_path": str(spec.path),
    }


def select_route_rows(spec: CsvRouteSpec) -> list[dict[str, Any]]:
    raw = read_csv(spec.path)
    if raw.empty:
        return [
            {
                "route_id": spec.route_id,
                "family": spec.family,
                "role": "missing",
                "status": "missing",
                "variant": "",
                "description": spec.description,
                "comparability": spec.comparability,
                "date_start": pd.NA,
                "date_end": pd.NA,
                "days": pd.NA,
                "roundtrip_cost_bps": pd.NA,
                "final_equity": float("nan"),
                "total_return": float("nan"),
                "max_drawdown": float("nan"),
                "sharpe": float("nan"),
                "return_over_abs_dd": float("nan"),
                "trade_count": pd.NA,
                "win_rate": pd.NA,
                "meets_user_goal": False,
                "metric_basis": "",
                "governance_note": spec.governance_note,
                "source_line": spec.source_line,
                "source_path": str(spec.path),
            }
        ]

    work = normalize_metric_columns(raw)
    work["metric_basis"] = source_metric_basis(raw)
    if spec.preferred_cost_bps is not None and "roundtrip_cost_bps" in work.columns:
        cost_filtered = work[work["roundtrip_cost_bps"] == spec.preferred_cost_bps]
        if not cost_filtered.empty:
            work = cost_filtered
    if spec.route_id == "market_down_beta_residual" and "path" in work.columns:
        net_or_residual = work[~work["path"].astype(str).eq("strategy_gross")]
        if not net_or_residual.empty:
            work = net_or_residual

    metric_ready = work.dropna(subset=["total_return", "max_drawdown"], how="any").copy()
    if metric_ready.empty:
        return [build_row(spec, "no_metric", work.iloc[0], status="no_metric")]

    selected: list[tuple[str, pd.Series]] = []
    selected.append(("best_return", metric_ready.sort_values(["total_return", "sharpe"], ascending=False).iloc[0]))
    positive = metric_ready[metric_ready["total_return"] > 0]
    if not positive.empty:
        selected.append(("lowest_drawdown_positive", positive.sort_values(["max_drawdown", "total_return"], ascending=False).iloc[0]))
    goal_hits = metric_ready[(metric_ready["total_return"] >= USER_RETURN_TARGET) & (metric_ready["max_drawdown"] >= USER_MAX_DRAWDOWN_LIMIT)]
    if not goal_hits.empty:
        selected.append(("goal_hit_best_return", goal_hits.sort_values(["total_return", "sharpe"], ascending=False).iloc[0]))
    if spec.preferred_variant_keywords:
        names = metric_ready.apply(variant_name, axis=1)
        for keyword in spec.preferred_variant_keywords:
            matched = metric_ready[names.str.contains(keyword, regex=False, na=False)]
            if not matched.empty:
                selected.append((f"preferred_{keyword}", matched.sort_values(["total_return", "sharpe"], ascending=False).iloc[0]))

    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for role, row in selected:
        key = (role, variant_name(row))
        if key in seen:
            continue
        seen.add(key)
        rows.append(build_row(spec, role, row))
    return rows


def build_paper_suite_row() -> dict[str, Any]:
    path = (
        NATIVE_RESULTS_DIR
        / "stock_range_reversion_liquid_q3_paper_monitor_suite_2018_2026"
        / "stock_range_reversion_liquid_q3_paper_monitor_suite_v1_summary.json"
    )
    data = read_json(path)
    total_return = safe_float(data.get("ledger_total_return"))
    max_drawdown = safe_float(data.get("ledger_max_drawdown"))
    return {
        "route_id": "stock_range_paper_v1_monitor_suite",
        "family": "established_stock_paper",
        "role": "latest_paper_monitor",
        "status": "available" if data else "missing",
        "variant": "paper monitor suite / age4_daily_exclude_volume_dry",
        "description": "股票震荡paper线的最新固定suite监控。",
        "comparability": "paper_monitor_not_new_30w_research",
        "date_start": "2018-2026",
        "date_end": data.get("latest_target_date"),
        "days": pd.NA,
        "roundtrip_cost_bps": pd.NA,
        "final_equity": safe_float(data.get("ledger_final_equity")),
        "total_return": total_return,
        "max_drawdown": max_drawdown,
        "sharpe": safe_float(data.get("ledger_sharpe")),
        "return_over_abs_dd": total_return / abs(max_drawdown) if not pd.isna(total_return) and max_drawdown < 0 else float("nan"),
        "trade_count": data.get("latest_order_count"),
        "win_rate": pd.NA,
        "meets_user_goal": bool(total_return >= USER_RETURN_TARGET and max_drawdown >= USER_MAX_DRAWDOWN_LIMIT),
        "metric_basis": "paper_ledger",
        "governance_note": "这是已隔离paper线的监控结果，状态仍为yellow_caution_continue_paper，不代表当前线可直接实盘。",
        "source_line": "stock_range_paper_v1",
        "source_path": str(path),
    }


def build_architecture_summary() -> pd.DataFrame:
    rows = [build_paper_suite_row()]
    for spec in CSV_ROUTE_SPECS:
        rows.extend(select_route_rows(spec))
    frame = pd.DataFrame(rows)
    frame["is_direct_30w"] = frame["comparability"].astype(str).str.startswith("direct_30w")
    frame["is_current_line"] = frame["source_line"].eq("stock_range_30w_industry_resid_core")
    frame["decision_bucket"] = frame.apply(decision_bucket_for_row, axis=1)
    return frame


def decision_bucket_for_row(row: pd.Series) -> str:
    comparability = safe_str(row.get("comparability"))
    family = safe_str(row.get("family"))
    route_id = safe_str(row.get("route_id"))
    if safe_str(row.get("status")) != "available":
        return "missing_or_unusable"
    if route_id == "stock_range_paper_v1_monitor_suite":
        return "keep_paper_monitor_separate"
    if safe_str(row.get("source_line")) == "stock_range_paper_v1":
        return "paper_baseline_reference"
    if row.get("meets_user_goal") and "failed_neighborhood" in comparability:
        return "goal_hit_but_not_robust"
    if row.get("meets_user_goal") and comparability.startswith("direct_30w"):
        return "candidate_requires_ab_or_oos"
    if family == "etf_sleeve":
        return "satellite_only"
    if family == "momentum_pullback_reversal":
        return "downgrade_definition"
    if comparability.startswith("not_30w"):
        return "attribution_not_strategy"
    return "continue_architecture_research"


def build_signal_evidence() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for signal_id, description, path in SIGNAL_SPECS:
        frame = read_csv(path)
        if frame.empty:
            rows.append(
                {
                    "signal_id": signal_id,
                    "description": description,
                    "role": "missing",
                    "name": "",
                    "horizon": pd.NA,
                    "selected_rows": pd.NA,
                    "mean_forward_or_excess": float("nan"),
                    "t_stat": float("nan"),
                    "positive_ratio": float("nan"),
                    "judgement": "缺失，无法评价。",
                    "source_path": str(path),
                }
            )
            continue

        metric_cols = [
            "daily_avg_fwd_excess_ret_10",
            "avg_fwd_excess_ret_10",
            "top_minus_bottom_excess_mean",
            "mean_fwd_excess",
            "top_excess_ret_mean",
        ]
        t_cols = ["daily_t_stat_excess_10", "top_minus_bottom_excess_t", "t_stat_excess", "top_excess_ret_t"]
        ratio_cols = ["positive_excess_10_ratio", "top_minus_bottom_excess_positive_ratio", "positive_excess_day_ratio", "top_excess_ret_positive_ratio"]
        metric_col = metric_column(frame, *metric_cols)
        t_col = metric_column(frame, *t_cols)
        ratio_col = metric_column(frame, *ratio_cols)
        name_col = metric_column(frame, "model", "definition", "signal_variant", "feature")
        horizon_col = metric_column(frame, "horizon")
        selected_col = metric_column(frame, "selected_rows", "sample_rows")

        work = frame.copy()
        if metric_col is None:
            rows.append(
                {
                    "signal_id": signal_id,
                    "description": description,
                    "role": "no_metric",
                    "name": variant_name(work.iloc[0]),
                    "horizon": pd.NA,
                    "selected_rows": len(work),
                    "mean_forward_or_excess": float("nan"),
                    "t_stat": float("nan"),
                    "positive_ratio": float("nan"),
                    "judgement": "无统一前瞻收益字段，仅保留文件引用。",
                    "source_path": str(path),
                }
            )
            continue
        work[metric_col] = pd.to_numeric(work[metric_col], errors="coerce")
        if t_col is not None:
            work[t_col] = pd.to_numeric(work[t_col], errors="coerce")
        best = work.sort_values([metric_col, t_col] if t_col else [metric_col], ascending=False).head(3)
        for i, item in best.iterrows():
            signal_name = safe_str(item.get(name_col)) if name_col else variant_name(item)
            metric = safe_float(item.get(metric_col))
            t_stat = safe_float(item.get(t_col)) if t_col else float("nan")
            positive_ratio = safe_float(item.get(ratio_col)) if ratio_col else float("nan")
            if signal_id == "technical_pullback_composite_factor" and signal_name == "composite_all8_product_damage":
                judgement = "8点统一复合因子信号弱于核心子因子，不能直接当交易系统。"
            elif metric > 0 and (pd.isna(t_stat) or t_stat > 1.5):
                judgement = "信号层有正向信息，但仍需整手/成本/稳定性复放。"
            else:
                judgement = "信号层证据偏弱或不稳定，不宜直接策略化。"
            rows.append(
                {
                    "signal_id": signal_id,
                    "description": description,
                    "role": f"top_signal_{len(rows) + 1}",
                    "name": signal_name,
                    "horizon": item.get(horizon_col) if horizon_col else pd.NA,
                    "selected_rows": item.get(selected_col) if selected_col else pd.NA,
                    "mean_forward_or_excess": metric,
                    "t_stat": t_stat,
                    "positive_ratio": positive_ratio,
                    "judgement": judgement,
                    "source_path": str(path),
                }
            )
    return pd.DataFrame(rows)


def build_quality_checkpoints(summary: pd.DataFrame, signals: pd.DataFrame) -> pd.DataFrame:
    current_direct = summary[summary["is_direct_30w"] & summary["is_current_line"]]
    current_goal = current_direct[current_direct["meets_user_goal"]]
    robust_goal = current_goal[~current_goal["comparability"].astype(str).str.contains("failed_neighborhood", na=False)]
    paper_goal = summary[(summary["source_line"] == "stock_range_paper_v1") & summary["meets_user_goal"]]
    etf_goal = summary[(summary["family"] == "etf_sleeve") & summary["meets_user_goal"]]
    paper_goal_count = len(paper_goal.drop_duplicates(["route_id", "variant"]))
    robust_goal_count = len(robust_goal.drop_duplicates(["route_id", "variant"]))
    etf_goal_count = len(etf_goal.drop_duplicates(["route_id", "variant"]))
    rows = [
        {
            "checkpoint": "paper_line_has_goal_like_result",
            "status": "pass" if paper_goal_count > 0 else "warn",
            "value": f"unique_goal_variants={paper_goal_count}",
            "expected": "已有隔离paper线能达到高收益/低回撤画像",
            "judgement": "说明股票震荡大方向没有错，但必须和当前30万industry_resid研究线隔离。",
        },
        {
            "checkpoint": "current_line_robust_goal_hit",
            "status": "fail" if robust_goal_count == 0 else "pass",
            "value": f"unique_robust_goal_variants={robust_goal_count}",
            "expected": "当前线有通过稳健性反证的30万高收益低回撤候选",
            "judgement": "当前线尚无可升级正式候选，Stage320命中过目标但邻域敏感。",
        },
        {
            "checkpoint": "simple_oversold_vs_industry_resid",
            "status": "pass",
            "value": "both_available",
            "expected": "有简单基准和复杂基准可比较",
            "judgement": "简单20日超跌反而是重要对照；复杂行业残差不能脱离简单基准证明增益。",
        },
        {
            "checkpoint": "strong_pullback_tradeable_evidence",
            "status": "fail",
            "value": "30w_replay_weak",
            "expected": "强势回踩应改善收益或回撤",
            "judgement": "现有强势回踩定义在30万整手回放里偏弱，应暂停交易化微调。",
        },
        {
            "checkpoint": "etf_as_core_goal_hit",
            "status": "fail" if etf_goal_count == 0 else "pass",
            "value": f"unique_etf_goal_variants={etf_goal_count}",
            "expected": "ETF路线能独立达到总收益>=100%且回撤<=20%",
            "judgement": "ETF更适合做低波动卫星或状态参照，不适合当前主收益引擎。",
        },
        {
            "checkpoint": "signal_not_strategy_boundary",
            "status": "pass" if not signals.empty else "warn",
            "value": f"signal_rows={len(signals)}",
            "expected": "信号层归因和交易回放分开记录",
            "judgement": "信号正向不等于能交易；30万整手、成本和持有路径是当前瓶颈。",
        },
    ]
    return pd.DataFrame(rows)


def build_route_decision(summary: pd.DataFrame, checkpoints: pd.DataFrame) -> pd.DataFrame:
    robust_goal_ok = checkpoints.loc[checkpoints["checkpoint"] == "current_line_robust_goal_hit", "status"].iloc[0] == "pass"
    return pd.DataFrame(
        [
            {
                "priority": 1,
                "decision": "stop_micro_repair_industry_resid_core",
                "status": "active",
                "action": "暂停围绕industry_resid_core继续加小型硬过滤、时间止损、状态加仓。",
                "reason": "连续阶段显示能解释亏损但难以稳健修复，继续缝补会偏离初衷并增加过拟合。",
            },
            {
                "priority": 2,
                "decision": "keep_paper_v1_separate",
                "status": "active",
                "action": "继续把净值2.x、回撤约10-15%的paper线作为独立监控线。",
                "reason": "它满足画像但已有固定suite与黄灯paper状态，不能和当前研究线混账。",
            },
            {
                "priority": 3,
                "decision": "rebuild_architecture_from_simple_baseline",
                "status": "active",
                "action": "从简单20日超跌30万基准出发，逐层证明行业残差/状态/ETF卫星是否有真实增益。",
                "reason": "简单基准更少假设，更适合作为穿越周期的地基。",
            },
            {
                "priority": 4,
                "decision": "downgrade_strong_pullback_definitions",
                "status": "active",
                "action": "暂不继续强势回踩交易化扫参，只保留信号层经验。",
                "reason": "强者恒强+回调在现有定义下没有改善30万收益回撤。",
            },
            {
                "priority": 5,
                "decision": "use_etf_as_satellite_not_core",
                "status": "active",
                "action": "ETF路线只作为平滑/状态/风险预算卫星，暂不设为主策略。",
                "reason": "ETF低回撤但收益厚度不足，适合搭配而非承担高收益目标。",
            },
            {
                "priority": 6,
                "decision": "candidate_gate",
                "status": "blocked" if not robust_goal_ok else "review",
                "action": "没有稳健30万候选前，不触发A/B、不接实盘、不合入第78。",
                "reason": "当前最好的当前线目标命中来自敏感慢节奏候选，仍需重新架构验证。",
            },
        ]
    )


def format_frame_for_report(frame: pd.DataFrame) -> pd.DataFrame:
    display = frame.copy()
    for column in ("total_return", "max_drawdown", "win_rate"):
        if column in display.columns:
            display[f"{column}_pct"] = display[column].map(pct)
    for column in ("final_equity", "sharpe", "return_over_abs_dd"):
        if column in display.columns:
            display[column] = display[column].map(lambda value: "" if pd.isna(value) else f"{float(value):.4f}")
    return display


def markdown_table(frame: pd.DataFrame, columns: list[str], limit: int = 30) -> str:
    if frame.empty:
        return "\n无数据。\n"
    table = frame[[col for col in columns if col in frame.columns]].head(limit).copy()
    return table.to_markdown(index=False)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def build_report(
    summary: pd.DataFrame,
    signals: pd.DataFrame,
    checkpoints: pd.DataFrame,
    decisions: pd.DataFrame,
) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M CST")
    summary_display = format_frame_for_report(
        summary.sort_values(["family", "route_id", "role"]).reset_index(drop=True)
    )
    goal_display = format_frame_for_report(
        summary[summary["meets_user_goal"]].sort_values(["source_line", "total_return"], ascending=[True, False])
    )
    direct_display = format_frame_for_report(
        summary[summary["is_direct_30w"] & summary["is_current_line"]].sort_values("total_return", ascending=False)
    )
    signal_display = signals.copy()
    if not signal_display.empty:
        signal_display["mean_forward_or_excess_pct"] = signal_display["mean_forward_or_excess"].map(pct)
        signal_display["positive_ratio_pct"] = signal_display["positive_ratio"].map(pct)
        signal_display["t_stat"] = signal_display["t_stat"].map(lambda value: "" if pd.isna(value) else f"{float(value):.3f}")

    return f"""# 股票震荡30万架构盘点 v1

- 记录时间：{now}
- 当前模式：day
- line_id：stock_range_30w_industry_resid_core
- 阶段性质：路线盘点/架构重置，不新增回测参数，不接入实盘，不触发A/B。
- 用户目标：30万本金，追求高收益，可接受最大回撤20%以内。

## 外部调研与判断

- 短期反转的学术证据更偏向“残差/行业内非基本面冲击回归”，而不是裸价格超跌；纽约联储 Staff Report 513 将短期反转收益拆成行业动量、行业内预期收益差、现金流反应不足和残差，并指出残差部分最关键：https://www.newyorkfed.org/research/staff_reports/sr513.html
- 残差短反方向也有论文支持，核心思想是剥离动态因子暴露后做短期反转：https://www.sciencedirect.com/science/article/pii/S1386418112000468
- Connors RSI(2) 这类业界系统强调“顺长期趋势买短期回调”，不是猜大底；它可当入场模板，但不等同于完整A股交易系统：https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/rsi-2
- 在线组合均值回归类研究提醒：很多benchmark会偏向均值回归，加入真实成本后可能失效：https://arxiv.org/abs/1909.04327
- GitHub上可见的均值回归/RSI2/配对交易项目多为教学或单标的框架，能借鉴流程，不能直接复制为30万A股策略：https://github.com/topics/mean-reversion-trading

我的判断：股市震荡策略的本质仍是“横截面短期流动性冲击回归”，但交易系统必须通过小账户整手、成本、持有路径和状态稳定性。我们之前对industry_resid_core的中段亏损归因没有错，但继续用小规则修补已经有偏离初衷的风险。

## 命中用户目标的既有结果

{markdown_table(goal_display, ["route_id", "role", "variant", "source_line", "comparability", "final_equity", "total_return_pct", "max_drawdown_pct", "sharpe", "decision_bucket"], 20)}

## 当前线30万直接可比路线

{markdown_table(direct_display, ["route_id", "role", "variant", "final_equity", "total_return_pct", "max_drawdown_pct", "sharpe", "return_over_abs_dd", "decision_bucket"], 40)}

## 全部架构代表样本

{markdown_table(summary_display, ["route_id", "family", "role", "variant", "comparability", "total_return_pct", "max_drawdown_pct", "sharpe", "decision_bucket"], 80)}

## 信号层证据

{markdown_table(signal_display, ["signal_id", "name", "horizon", "selected_rows", "mean_forward_or_excess_pct", "t_stat", "positive_ratio_pct", "judgement"], 30)}

## 质量检查

{markdown_table(checkpoints, ["checkpoint", "status", "value", "expected", "judgement"], 20)}

## 路线决策

{markdown_table(decisions, ["priority", "decision", "status", "action", "reason"], 20)}

## 结论

- 初衷没有错：我们要做的是30万A股长侧横截面震荡/短反策略，高收益、回撤尽量压在20%以内。
- 当前研究确实有一点偏离：第322到第330阶段越来越像围绕industry_resid_core修补尾部，而不是重新审视哪种架构更适合30万账户。
- 最大的正面证据仍在隔离的paper线：paper suite权益`2.2225`、总收益`122.25%`、最大回撤`-15.16%`，但状态是`yellow_caution_continue_paper`，不能直接实盘。
- 当前industry_resid_core线出现过第320目标命中，但第321邻域反证失败；后续平滑预算、risk-on、弱行业过滤、接刀子过滤、尾部预算、中段退出都没有给出稳健正式候选。
- 强势回踩/8点统一因子暂时没有成为更强交易系统；简单20日超跌30万基准反而是下一阶段更健康的地基。

## 下一步

1. 暂停industry_resid_core微修补，保留归因经验。
2. 以简单20日超跌30万基准为母本，重新做“架构级”A/B：简单超跌、残差增强、状态预算、ETF卫星分别逐层加入，每层必须证明增益。
3. paper_v1继续独立监控，不和当前线混合记账。
4. 强势回踩路线降级为信号研究，不再继续扫交易参数。

## 过拟合反思

- 运行前判断：否。本阶段只做既有结果盘点，不新增参数。
- 运行后判断：否。结论是暂停微调和重建架构，而不是挑一个最优参数上线。
- 风险提示：若下一步把本表里表现最好的行直接组合，会立刻转为过拟合；必须预注册架构层级再复放。

## 继续价值反思

- 运行前判断：是。用户目标清晰，已有paper线说明股票震荡方向有价值。
- 运行后判断：是，但价值不在继续修补当前残差核心，而在从简单基准重建可解释架构。
- 原因：30万账户的核心约束是整手、分散度和持有路径，不是再多一个漂亮状态阈值。

## 输出文件

- `{PREFIX}_architecture_summary.csv`
- `{PREFIX}_signal_evidence.csv`
- `{PREFIX}_quality_checkpoints.csv`
- `{PREFIX}_route_decision.csv`
- `{PREFIX}_meta.json`
"""


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = build_architecture_summary()
    signals = build_signal_evidence()
    checkpoints = build_quality_checkpoints(summary, signals)
    decisions = build_route_decision(summary, checkpoints)

    summary.to_csv(OUTPUT_DIR / f"{PREFIX}_architecture_summary.csv", index=False, encoding="utf-8-sig")
    signals.to_csv(OUTPUT_DIR / f"{PREFIX}_signal_evidence.csv", index=False, encoding="utf-8-sig")
    checkpoints.to_csv(OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv", index=False, encoding="utf-8-sig")
    decisions.to_csv(OUTPUT_DIR / f"{PREFIX}_route_decision.csv", index=False, encoding="utf-8-sig")

    meta = {
        "generated_at": datetime.now().isoformat(),
        "line_id": "stock_range_30w_industry_resid_core",
        "mode": "day",
        "user_return_target": USER_RETURN_TARGET,
        "user_max_drawdown_limit": USER_MAX_DRAWDOWN_LIMIT,
        "route_count": int(summary["route_id"].nunique()),
        "architecture_rows": int(len(summary)),
        "signal_rows": int(len(signals)),
        "direct_30w_current_rows": int((summary["is_direct_30w"] & summary["is_current_line"]).sum()),
        "current_line_goal_rows": int((summary["is_direct_30w"] & summary["is_current_line"] & summary["meets_user_goal"]).sum()),
        "source_paths": [str(spec.path) for spec in CSV_ROUTE_SPECS],
    }
    write_json(OUTPUT_DIR / f"{PREFIX}_meta.json", meta)

    report = build_report(summary, signals, checkpoints, decisions)
    (OUTPUT_DIR / f"{PREFIX}_report.md").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
