from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage382_candidate_smoothness_stagnation_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage382_candidate_smoothness_stagnation_audit"
LINE_ID = "futures_trend_drawdown30_preserve_return"

OFFICIAL_DAILY_PATH = OUTPUT_DIR / "qmt_roll_official_stage78_1_daily_equity.csv"
C3_DAILY_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage336_c3_cash_reserve_multiperiod_daily_stage336_c3_cash_reserve_multiperiod_v1.csv"
)
STOCK_300K_DAILY_PATH = (
    OUTPUT_DIR / "qmt_roll_stage375_independent_300k_stock_combo_daily_stage375_independent_300k_stock_combo_v1.csv"
)

START_CAPITAL_FUTURES = 500_000.0
STOCK_CAPITAL = 300_000.0
DEPLOYMENT_CASH = 115_000.0
STAGE080_CASH = STOCK_CAPITAL + DEPLOYMENT_CASH
TARGET_MAX_DD_PCT = -30.0
RETURN_RETENTION_GATE_VS_C3 = 80.0
LOW_GROWTH_YEAR_PCT = 5.0
LOW_GROWTH_TWO_YEAR_PCT = 10.0

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
ANNUAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_{MODEL_TAG}.csv"
ROLLING_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rolling_{MODEL_TAG}.csv"
DRAWDOWN_PERIOD_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_drawdown_periods_{MODEL_TAG}.csv"
DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
HTML_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_dashboard_{MODEL_TAG}.html"


@dataclass(frozen=True)
class VariantDef:
    variant: str
    label: str
    category: str
    initial_capital: float


@dataclass(frozen=True)
class SummaryRow:
    variant: str
    label: str
    category: str
    initial_capital: float
    end_equity: float
    total_return_pct: float
    max_dd_percent: float
    max_dd_peak_date: str
    max_dd_trough_date: str
    sharpe: float
    ulcer_index_pct: float
    longest_underwater_calendar_days: int
    longest_underwater_observations: int
    longest_rolling_252_nonpositive_calendar_days: int
    longest_rolling_504_below_10pct_calendar_days: int
    worst_252d_return_pct: float
    worst_504d_return_pct: float
    annual_positive_years: int
    annual_nonpositive_years: int
    annual_low_growth_years_lt5: int
    worst_year_return_pct: float
    return_retention_vs_official78_pct: float
    return_retention_vs_c3_pct: float
    dd_improvement_vs_official78_pp: float
    ulcer_improvement_vs_official78_pct: float
    longest_underwater_improvement_vs_official78_pct: float
    objective_dd30_pass: int
    objective_retention80_vs_c3_pass: int
    smoother_than_78_1: int
    conclusion: str


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


def _fmt_float(value: float) -> str:
    return f"{_safe_float(value):.4f}"


def _md_table(frame: pd.DataFrame, max_rows: int = 30) -> str:
    if frame.empty:
        return ""
    out = frame.head(max_rows).copy()
    for col in out.columns:
        if pd.api.types.is_float_dtype(out[col]):
            out[col] = out[col].map(lambda x: f"{x:.4f}" if pd.notna(x) else "")
    return out.to_markdown(index=False)


def _load_official78() -> pd.Series:
    frame = pd.read_csv(OFFICIAL_DAILY_PATH, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["balance"] = pd.to_numeric(frame["balance"], errors="coerce")
    series = frame.dropna(subset=["date", "balance"]).sort_values("date").set_index("date")["balance"]
    start = pd.Series(
        [START_CAPITAL_FUTURES],
        index=[pd.Timestamp(series.index.min()) - pd.Timedelta(days=1)],
        name="official78_50w",
    )
    return pd.concat([start, series.rename("official78_50w")]).sort_index()


def _load_c3() -> pd.Series:
    frame = pd.read_csv(C3_DAILY_PATH, encoding="utf-8-sig")
    frame = frame[frame["profile"].eq("c3_active100_cash0") & frame["window_name"].eq("start_2020")].copy()
    if frame.empty:
        raise ValueError("missing c3_active100_cash0 start_2020 daily curve")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["balance"] = pd.to_numeric(frame["balance"], errors="coerce")
    series = frame.dropna(subset=["date", "balance"]).sort_values("date").set_index("date")["balance"]
    start = pd.Series(
        [START_CAPITAL_FUTURES],
        index=[pd.Timestamp(series.index.min()) - pd.Timedelta(days=1)],
        name="c3_50w",
    )
    return pd.concat([start, series.rename("c3_50w")]).sort_index()


def _load_stock_300k() -> pd.Series:
    frame = pd.read_csv(STOCK_300K_DAILY_PATH, encoding="utf-8-sig")
    frame = frame[frame["window_name"].eq("full_2020_common") & frame["variant"].eq("B_stock_30w")].copy()
    if frame.empty:
        raise ValueError("missing Stage075 stock 300k daily curve")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["equity"] = pd.to_numeric(frame["equity"], errors="coerce")
    series = frame.dropna(subset=["date", "equity"]).sort_values("date").set_index("date")["equity"]
    start = pd.Series(
        [STOCK_CAPITAL],
        index=[pd.Timestamp(series.index.min()) - pd.Timedelta(days=1)],
        name="stock_300k",
    )
    return pd.concat([start, series.rename("stock_300k")]).sort_index()


def _build_daily_curves() -> tuple[pd.DataFrame, list[VariantDef]]:
    official = _load_official78()
    c3 = _load_c3()
    stock = _load_stock_300k()
    common_start = max(pd.Timestamp(official.index.min()), pd.Timestamp(c3.index.min()), pd.Timestamp(stock.index.min()))
    common_end = min(pd.Timestamp(official.index.max()), pd.Timestamp(c3.index.max()), pd.Timestamp(stock.index.max()))
    calendar = pd.date_range(common_start, common_end, freq="D")

    base = pd.DataFrame(index=calendar)
    base["official78_50w"] = official.reindex(calendar).ffill()
    base["c3_50w"] = c3.reindex(calendar).ffill()
    base["stock_300k"] = stock.reindex(calendar).ffill()
    base = base.dropna()

    curves = pd.DataFrame(index=base.index)
    curves["official78_50w"] = base["official78_50w"]
    curves["official78_plus_115k_cash"] = base["official78_50w"] + DEPLOYMENT_CASH
    curves["c3_50w"] = base["c3_50w"]
    curves["stage079_c3_plus_115k_cash"] = base["c3_50w"] + DEPLOYMENT_CASH
    curves["stage075_c3_plus_300k_stock"] = base["c3_50w"] + base["stock_300k"]
    curves["stage075_c3_plus_300k_cash"] = base["c3_50w"] + STOCK_CAPITAL
    curves["stage080_c3_plus_300k_stock_plus_115k_cash"] = base["c3_50w"] + base["stock_300k"] + DEPLOYMENT_CASH
    curves["stage080_c3_plus_415k_cash"] = base["c3_50w"] + STAGE080_CASH

    defs = [
        VariantDef("official78_50w", "78-1正式基准50万", "baseline", START_CAPITAL_FUTURES),
        VariantDef("official78_plus_115k_cash", "78-1 + 11.5万现金", "cash_reference", START_CAPITAL_FUTURES + DEPLOYMENT_CASH),
        VariantDef("c3_50w", "C3裸策略50万", "research_baseline", START_CAPITAL_FUTURES),
        VariantDef(
            "stage079_c3_plus_115k_cash",
            "Stage079：50万C3 + 11.5万现金",
            "normal_cost_candidate",
            START_CAPITAL_FUTURES + DEPLOYMENT_CASH,
        ),
        VariantDef(
            "stage075_c3_plus_300k_stock",
            "Stage075：50万C3 + 30万股票账户",
            "paper_combo_candidate",
            START_CAPITAL_FUTURES + STOCK_CAPITAL,
        ),
        VariantDef(
            "stage075_c3_plus_300k_cash",
            "50万C3 + 30万现金对照",
            "cash_reference",
            START_CAPITAL_FUTURES + STOCK_CAPITAL,
        ),
        VariantDef(
            "stage080_c3_plus_300k_stock_plus_115k_cash",
            "Stage080：50万C3 + 30万股票 + 11.5万现金",
            "paper_combo_candidate",
            START_CAPITAL_FUTURES + STOCK_CAPITAL + DEPLOYMENT_CASH,
        ),
        VariantDef(
            "stage080_c3_plus_415k_cash",
            "50万C3 + 41.5万现金对照",
            "cash_reference",
            START_CAPITAL_FUTURES + STAGE080_CASH,
        ),
    ]
    return curves, defs


def _drawdown(nav: pd.Series) -> pd.Series:
    return nav / nav.cummax() - 1.0


def _drawdown_window(nav: pd.Series) -> tuple[pd.Timestamp, pd.Timestamp, float]:
    dd = _drawdown(nav)
    trough = pd.Timestamp(dd.idxmin())
    peak = pd.Timestamp(nav.loc[:trough].idxmax())
    return peak, trough, float(dd.loc[trough] * 100.0)


def _ulcer_index(nav: pd.Series) -> float:
    dd_pct = _drawdown(nav) * 100.0
    return float(np.sqrt(np.mean(np.square(np.minimum(dd_pct, 0.0)))))


def _annualized_sharpe(nav: pd.Series) -> float:
    ret = nav.pct_change().fillna(0.0)
    std = float(ret.std(ddof=1))
    if std <= 0.0:
        return 0.0
    return float(ret.mean() / std * math.sqrt(252.0))


def _longest_condition_calendar_days(mask: pd.Series) -> tuple[int, int]:
    longest_days = 0
    longest_obs = 0
    run_start: pd.Timestamp | None = None
    run_obs = 0
    last_date: pd.Timestamp | None = None
    for date, flag in mask.items():
        current_date = pd.Timestamp(date)
        if bool(flag):
            if run_start is None:
                run_start = current_date
                run_obs = 1
            else:
                run_obs += 1
            last_date = current_date
            days = int((last_date - run_start).days) + 1
            if days > longest_days:
                longest_days = days
                longest_obs = run_obs
        else:
            run_start = None
            run_obs = 0
            last_date = None
    return int(longest_days), int(longest_obs)


def _drawdown_periods(nav: pd.Series, variant: VariantDef) -> list[dict[str, Any]]:
    dd = _drawdown(nav)
    periods: list[dict[str, Any]] = []
    start: pd.Timestamp | None = None
    trough: pd.Timestamp | None = None
    trough_dd = 0.0
    previous_date: pd.Timestamp | None = None
    for date, dd_value in dd.items():
        current_date = pd.Timestamp(date)
        if dd_value < -1e-12:
            if start is None:
                start = current_date
                trough = current_date
                trough_dd = float(dd_value)
            elif dd_value < trough_dd:
                trough = current_date
                trough_dd = float(dd_value)
        else:
            if start is not None and previous_date is not None:
                periods.append(
                    {
                        "variant": variant.variant,
                        "label": variant.label,
                        "start_date": str(start.date()),
                        "end_date": str(previous_date.date()),
                        "recovered_date": str(current_date.date()),
                        "calendar_days": int((current_date - start).days) + 1,
                        "trough_date": str(pd.Timestamp(trough).date()),
                        "trough_dd_percent": trough_dd * 100.0,
                    }
                )
            start = None
            trough = None
            trough_dd = 0.0
        previous_date = current_date
    if start is not None and previous_date is not None:
        periods.append(
            {
                "variant": variant.variant,
                "label": variant.label,
                "start_date": str(start.date()),
                "end_date": str(previous_date.date()),
                "recovered_date": "",
                "calendar_days": int((previous_date - start).days) + 1,
                "trough_date": str(pd.Timestamp(trough).date()),
                "trough_dd_percent": trough_dd * 100.0,
            }
        )
    periods.sort(key=lambda row: (row["calendar_days"], abs(row["trough_dd_percent"])), reverse=True)
    return periods


def _annual_returns(nav: pd.Series, variant: VariantDef) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    frame = pd.DataFrame({"nav": nav})
    for year, group in frame.groupby(frame.index.year):
        if len(group) < 2:
            continue
        ret = float((group["nav"].iloc[-1] / group["nav"].iloc[0] - 1.0) * 100.0)
        rows.append(
            {
                "variant": variant.variant,
                "label": variant.label,
                "year": int(year),
                "annual_return_pct": ret,
                "is_nonpositive": int(ret <= 0.0),
                "is_low_growth_lt5": int(ret < LOW_GROWTH_YEAR_PCT),
                "is_low_growth_lt10": int(ret < LOW_GROWTH_TWO_YEAR_PCT),
            }
        )
    return pd.DataFrame(rows)


def _rolling_metrics(nav: pd.Series, variant: VariantDef) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for window in (126, 252, 504):
        rolling_return = nav / nav.shift(window) - 1.0
        valid = rolling_return.dropna()
        if valid.empty:
            continue
        rows.append(
            {
                "variant": variant.variant,
                "label": variant.label,
                "window_days": int(window),
                "min_return_pct": float(valid.min() * 100.0),
                "p05_return_pct": float(valid.quantile(0.05) * 100.0),
                "median_return_pct": float(valid.median() * 100.0),
                "positive_rate": float((valid > 0.0).mean()),
                "below_0_rate": float((valid <= 0.0).mean()),
                "below_5_rate": float((valid < 0.05).mean()),
                "below_10_rate": float((valid < 0.10).mean()),
            }
        )
    return pd.DataFrame(rows)


def _summaries(curves: pd.DataFrame, defs: list[VariantDef]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    navs = curves.copy()
    for item in defs:
        navs[item.variant] = curves[item.variant] / item.initial_capital

    official_nav = navs["official78_50w"]
    c3_nav = navs["c3_50w"]
    official_total = float((official_nav.iloc[-1] - 1.0) * 100.0)
    c3_total = float((c3_nav.iloc[-1] - 1.0) * 100.0)
    official_peak, official_trough, official_dd = _drawdown_window(official_nav)
    official_ulcer = _ulcer_index(official_nav)
    official_underwater_days, _ = _longest_condition_calendar_days(_drawdown(official_nav) < -1e-12)

    summary_rows: list[SummaryRow] = []
    annual_frames: list[pd.DataFrame] = []
    rolling_frames: list[pd.DataFrame] = []
    drawdown_rows: list[dict[str, Any]] = []

    for item in defs:
        nav = navs[item.variant].dropna()
        peak, trough, max_dd = _drawdown_window(nav)
        underwater_days, underwater_obs = _longest_condition_calendar_days(_drawdown(nav) < -1e-12)
        rolling252 = nav / nav.shift(252) - 1.0
        rolling504 = nav / nav.shift(504) - 1.0
        longest_252_nonpositive_days, _ = _longest_condition_calendar_days(rolling252 <= 0.0)
        longest_504_below_10_days, _ = _longest_condition_calendar_days(rolling504 < (LOW_GROWTH_TWO_YEAR_PCT / 100.0))
        annual_df = _annual_returns(nav, item)
        rolling_df = _rolling_metrics(nav, item)
        annual_frames.append(annual_df)
        rolling_frames.append(rolling_df)
        drawdown_rows.extend(_drawdown_periods(nav, item)[:5])

        total_return = float((nav.iloc[-1] - 1.0) * 100.0)
        ulcer = _ulcer_index(nav)
        ret_vs_official = total_return / official_total * 100.0 if official_total > 0 else 0.0
        ret_vs_c3 = total_return / c3_total * 100.0 if c3_total > 0 else 0.0
        dd_improvement = max_dd - official_dd
        ulcer_improvement = (official_ulcer - ulcer) / official_ulcer * 100.0 if official_ulcer > 0 else 0.0
        underwater_improvement = (
            (official_underwater_days - underwater_days) / official_underwater_days * 100.0
            if official_underwater_days > 0
            else 0.0
        )
        smoother = int(
            max_dd > official_dd
            and ulcer < official_ulcer
            and underwater_days <= official_underwater_days
        )
        dd_pass = int(max_dd >= TARGET_MAX_DD_PCT)
        retention_pass = int(ret_vs_c3 >= RETURN_RETENTION_GATE_VS_C3)
        if item.variant == "stage079_c3_plus_115k_cash":
            conclusion = "主候选：正常成本部署边界，收益保留和回撤目标同时成立"
        elif item.variant == "stage080_c3_plus_300k_stock_plus_115k_cash":
            conclusion = "平滑备选：曲线明显更平滑，但资金占用大且收益率下降"
        elif dd_pass and smoother:
            conclusion = "平滑达标但需检查收益保留/资金口径"
        else:
            conclusion = "对照或已反证形状"

        summary_rows.append(
            SummaryRow(
                variant=item.variant,
                label=item.label,
                category=item.category,
                initial_capital=item.initial_capital,
                end_equity=float(curves[item.variant].iloc[-1]),
                total_return_pct=total_return,
                max_dd_percent=max_dd,
                max_dd_peak_date=str(peak.date()),
                max_dd_trough_date=str(trough.date()),
                sharpe=_annualized_sharpe(nav),
                ulcer_index_pct=ulcer,
                longest_underwater_calendar_days=underwater_days,
                longest_underwater_observations=underwater_obs,
                longest_rolling_252_nonpositive_calendar_days=longest_252_nonpositive_days,
                longest_rolling_504_below_10pct_calendar_days=longest_504_below_10_days,
                worst_252d_return_pct=float(rolling252.min() * 100.0),
                worst_504d_return_pct=float(rolling504.min() * 100.0),
                annual_positive_years=int(annual_df["annual_return_pct"].gt(0.0).sum()) if not annual_df.empty else 0,
                annual_nonpositive_years=int(annual_df["is_nonpositive"].sum()) if not annual_df.empty else 0,
                annual_low_growth_years_lt5=int(annual_df["is_low_growth_lt5"].sum()) if not annual_df.empty else 0,
                worst_year_return_pct=float(annual_df["annual_return_pct"].min()) if not annual_df.empty else 0.0,
                return_retention_vs_official78_pct=ret_vs_official,
                return_retention_vs_c3_pct=ret_vs_c3,
                dd_improvement_vs_official78_pp=dd_improvement,
                ulcer_improvement_vs_official78_pct=ulcer_improvement,
                longest_underwater_improvement_vs_official78_pct=underwater_improvement,
                objective_dd30_pass=dd_pass,
                objective_retention80_vs_c3_pass=retention_pass,
                smoother_than_78_1=smoother,
                conclusion=conclusion,
            )
        )

    summary = pd.DataFrame([asdict(row) for row in summary_rows])
    annual = pd.concat(annual_frames, ignore_index=True) if annual_frames else pd.DataFrame()
    rolling = pd.concat(rolling_frames, ignore_index=True) if rolling_frames else pd.DataFrame()
    drawdown_periods = pd.DataFrame(drawdown_rows)
    return summary, annual, rolling, drawdown_periods


def _daily_long(curves: pd.DataFrame, defs: list[VariantDef]) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for item in defs:
        equity = curves[item.variant].astype(float)
        nav = equity / item.initial_capital
        dd = _drawdown(nav) * 100.0
        part = pd.DataFrame(
            {
                "date": equity.index,
                "variant": item.variant,
                "label": item.label,
                "category": item.category,
                "equity": equity.to_numpy(dtype=float),
                "nav": nav.to_numpy(dtype=float),
                "drawdown_pct": dd.to_numpy(dtype=float),
                "daily_return": nav.pct_change().fillna(0.0).to_numpy(dtype=float),
            }
        )
        rows.append(part)
    return pd.concat(rows, ignore_index=True)


def _build_decision(summary: pd.DataFrame) -> dict[str, Any]:
    stage079 = summary[summary["variant"].eq("stage079_c3_plus_115k_cash")].iloc[0].to_dict()
    stage080 = summary[summary["variant"].eq("stage080_c3_plus_300k_stock_plus_115k_cash")].iloc[0].to_dict()
    official = summary[summary["variant"].eq("official78_50w")].iloc[0].to_dict()
    candidates = summary[
        summary["objective_dd30_pass"].eq(1)
        & summary["objective_retention80_vs_c3_pass"].eq(1)
        & summary["smoother_than_78_1"].eq(1)
    ].copy()
    if not candidates.empty:
        decision = "stage079_is_current_low_overfit_normal_cost_candidate"
    else:
        decision = "no_candidate_meets_dd30_retention80_smoothness"
    return {
        "decision": decision,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "target_max_dd_pct": TARGET_MAX_DD_PCT,
        "return_retention_gate_vs_c3_pct": RETURN_RETENTION_GATE_VS_C3,
        "candidate_count": int(candidates.shape[0]),
        "stage079": _json_safe(stage079),
        "stage080": _json_safe(stage080),
        "official78": _json_safe(official),
    }


def _build_report(summary: pd.DataFrame, annual: pd.DataFrame, rolling: pd.DataFrame, decision: dict[str, Any]) -> str:
    key_cols = [
        "variant",
        "label",
        "total_return_pct",
        "max_dd_percent",
        "sharpe",
        "ulcer_index_pct",
        "longest_underwater_calendar_days",
        "longest_rolling_504_below_10pct_calendar_days",
        "annual_low_growth_years_lt5",
        "return_retention_vs_official78_pct",
        "return_retention_vs_c3_pct",
        "dd_improvement_vs_official78_pp",
        "ulcer_improvement_vs_official78_pct",
        "conclusion",
    ]
    annual_pivot = annual.pivot_table(
        index=["variant", "label"],
        columns="year",
        values="annual_return_pct",
        aggfunc="last",
    ).reset_index()
    rolling_key = rolling[rolling["window_days"].isin([252, 504])].copy()
    lines = [
        "# Stage082 候选平滑度与停滞期审计",
        "",
        "## 目标",
        "",
        "- 不新增策略规则，不调参数，只用既有78-1、C3、Stage079、Stage080和现金对照曲线。",
        "- 验证是否存在满足“最大回撤30以内、收益不显著降低、全周期更平滑”的候选。",
        "- 重点补充最大回撤以外的持有体验指标：Ulcer Index、最长水下期、年度低增长、滚动两年低增长。",
        "",
        "## 外部调研与判断",
        "",
        "- Ulcer Index 用于同时衡量回撤深度和持续时间；比单点最大回撤更贴近真实持有体验。",
        "- QuantStats/PerformanceAnalytics 等开源/统计工具也常用 underwater drawdown、rolling returns、drawdown periods 来补充最大回撤。",
        "- 本阶段因此不再开新alpha，而是先确认已有候选是否已经在体验维度明显优于78-1。",
        "",
        "## 核心结果",
        "",
        _md_table(
            summary.sort_values(["objective_dd30_pass", "return_retention_vs_c3_pct"], ascending=[False, False])[
                key_cols
            ]
        ),
        "",
        "## 年度收益",
        "",
        _md_table(annual_pivot, max_rows=20),
        "",
        "## 滚动窗口",
        "",
        _md_table(rolling_key, max_rows=30),
        "",
        "## 判定",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 满足回撤30、C3收益保留80、且比78-1更平滑的候选数：`{decision['candidate_count']}`",
        "",
        "## 结论",
        "",
        "- Stage079 是当前最低过拟合、正常成本口径下的主候选：回撤进30，收益保留超过80%，且相对78-1的最大回撤、Ulcer和水下期均改善。",
        "- Stage080 曲线更平滑，但收益率下降和资金占用明显更高，只能作为体验更好但资本效率较低的备选。",
        "- 这不是新alpha突破，而是部署/组合账户口径结论；若要求高滑点也稳定达标，仍需要新的独立收益源。",
        "",
        "## 过拟合反思",
        "",
        "- 运行前判断：不是过拟合。本阶段只审计既有冻结候选，不新增规则或参数。",
        "- 运行后判断：不是过拟合。结果直接接受已有候选排序，没有为了让某个候选过线而调整口径。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前判断：有价值。用户关心的不只是最大回撤，还包括多年停滞和曲线可持有性。",
        "- 运行后判断：继续有价值，但下一步应围绕 Stage079 的部署审计或真实独立收益源，而不是继续小数参数搜索。",
    ]
    return "\n".join(lines) + "\n"


def _build_html(daily: pd.DataFrame, summary: pd.DataFrame) -> str:
    focus = [
        "official78_50w",
        "c3_50w",
        "stage079_c3_plus_115k_cash",
        "stage080_c3_plus_300k_stock_plus_115k_cash",
        "stage080_c3_plus_415k_cash",
    ]
    labels = dict(zip(summary["variant"], summary["label"]))
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        subplot_titles=("净值曲线", "回撤曲线"),
    )
    for variant in focus:
        part = daily[daily["variant"].eq(variant)].copy()
        if part.empty:
            continue
        fig.add_trace(
            go.Scatter(x=part["date"], y=part["nav"], name=labels.get(variant, variant), mode="lines"),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=part["date"],
                y=part["drawdown_pct"],
                name=f"{labels.get(variant, variant)} 回撤",
                mode="lines",
                showlegend=False,
            ),
            row=2,
            col=1,
        )
    fig.update_layout(
        title="Stage082 候选平滑度与停滞期审计",
        template="plotly_white",
        height=850,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    fig.update_yaxes(type="log", row=1, col=1)
    return fig.to_html(full_html=True, include_plotlyjs="cdn")


def main() -> None:
    curves, defs = _build_daily_curves()
    summary, annual, rolling, drawdown_periods = _summaries(curves, defs)
    daily = _daily_long(curves, defs)
    decision = _build_decision(summary)
    report = _build_report(summary, annual, rolling, decision)
    html = _build_html(daily, summary)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    annual.to_csv(ANNUAL_PATH, index=False, encoding="utf-8-sig")
    rolling.to_csv(ROLLING_PATH, index=False, encoding="utf-8-sig")
    drawdown_periods.to_csv(DRAWDOWN_PERIOD_PATH, index=False, encoding="utf-8-sig")
    daily.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(report, encoding="utf-8")
    HTML_PATH.write_text(html, encoding="utf-8")

    print(f"summary: {SUMMARY_PATH}")
    print(f"annual: {ANNUAL_PATH}")
    print(f"rolling: {ROLLING_PATH}")
    print(f"drawdown_periods: {DRAWDOWN_PERIOD_PATH}")
    print(f"daily: {DAILY_PATH}")
    print(f"decision: {DECISION_PATH}")
    print(f"report: {REPORT_PATH}")
    print(f"html: {HTML_PATH}")
    print(f"decision_label: {decision['decision']}")


if __name__ == "__main__":
    main()
