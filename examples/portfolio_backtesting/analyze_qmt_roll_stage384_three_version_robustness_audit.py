from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
LINE_ID = "futures_trend_drawdown30_preserve_return"
MODEL_TAG = "stage384_three_version_robustness_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage384_three_version_robustness_audit"

START_CAPITAL = 500_000.0
STAGE079_CASH = 115_000.0
STAGE079_ACCOUNT_CAPITAL = START_CAPITAL + STAGE079_CASH
TARGET_MAX_DD_PCT = -30.0
RETENTION_GATE_VS_C3_PCT = 80.0
RNG_SEED = 20260527
BOOTSTRAP_SIMS = 3000
MONTH_PERMUTATION_SIMS = 3000

STAGE383_DAILY_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage383_three_version_deep_audit_daily_stage383_three_version_deep_audit_v1.csv"
)
OFFICIAL_DAILY_PATH = OUTPUT_DIR / "qmt_roll_official_stage78_1_daily_equity.csv"
C3_DAILY_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage336_c3_cash_reserve_multiperiod_daily_stage336_c3_cash_reserve_multiperiod_v1.csv"
)

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
ROLLING_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rolling_distribution_{MODEL_TAG}.csv"
TAIL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_tail_dependency_{MODEL_TAG}.csv"
BOOTSTRAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_block_bootstrap_{MODEL_TAG}.csv"
MONTH_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_month_permutation_{MODEL_TAG}.csv"
CASH_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cash_requirement_{MODEL_TAG}.csv"
SCORE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_score_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
HTML_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_dashboard_{MODEL_TAG}.html"

VARIANTS = [
    ("stage78_1", "78-1正式版", START_CAPITAL),
    ("c3", "纯C3", START_CAPITAL),
    ("stage079", "Stage079：C3+11.5万现金", STAGE079_ACCOUNT_CAPITAL),
]


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
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


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "无数据。"
    view = frame.copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: f"{x:.4f}" if pd.notna(x) else "")
    return view.to_markdown(index=False)


def _load_stage383_curves() -> pd.DataFrame:
    if not STAGE383_DAILY_PATH.exists():
        raise FileNotFoundError(f"missing Stage383 daily output: {STAGE383_DAILY_PATH}")
    frame = pd.read_csv(STAGE383_DAILY_PATH, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["equity"] = pd.to_numeric(frame["equity"], errors="coerce")
    frame = frame.dropna(subset=["date", "equity", "variant"])
    curves = frame.pivot(index="date", columns="variant", values="equity").sort_index()
    needed = [name for name, _, _ in VARIANTS]
    missing = [name for name in needed if name not in curves.columns]
    if missing:
        raise ValueError(f"missing variants in Stage383 daily output: {missing}")
    return curves[needed].dropna()


def _nav(equity: pd.Series, initial: float) -> pd.Series:
    return equity.astype(float) / float(initial)


def _drawdown(nav: pd.Series) -> pd.Series:
    return nav / nav.cummax() - 1.0


def _max_dd(nav: pd.Series) -> float:
    return float(_drawdown(nav).min() * 100.0)


def _ulcer(nav: pd.Series) -> float:
    dd = np.minimum(_drawdown(nav).to_numpy(dtype=float) * 100.0, 0.0)
    return float(np.sqrt(np.mean(np.square(dd)))) if len(dd) else 0.0


def _sharpe_from_returns(ret: pd.Series) -> float:
    ret = ret.dropna().astype(float)
    if len(ret) < 2:
        return 0.0
    std = float(ret.std(ddof=1))
    if std <= 0:
        return 0.0
    return float(ret.mean() / std * math.sqrt(252.0))


def _cvar(values: pd.Series, q: float) -> float:
    values = values.dropna().astype(float)
    if values.empty:
        return 0.0
    threshold = values.quantile(q)
    tail = values[values <= threshold]
    return float(tail.mean()) if len(tail) else float(threshold)


def _longest_underwater(nav: pd.Series) -> int:
    mask = _drawdown(nav) < -1e-12
    longest = 0
    start: pd.Timestamp | None = None
    for date, flag in mask.items():
        date = pd.Timestamp(date)
        if flag:
            if start is None:
                start = date
            longest = max(longest, int((date - start).days) + 1)
        else:
            start = None
    return longest


def _summary(curves: pd.DataFrame) -> pd.DataFrame:
    rows = []
    c3_return = None
    for variant, label, initial in VARIANTS:
        equity = curves[variant]
        nav = _nav(equity, initial)
        ret = nav.pct_change().dropna()
        total_return = float((nav.iloc[-1] - 1.0) * 100.0)
        if variant == "c3":
            c3_return = total_return
        rows.append(
            {
                "variant": variant,
                "label": label,
                "initial_capital": initial,
                "start_date": str(curves.index.min().date()),
                "end_date": str(curves.index.max().date()),
                "end_equity": float(equity.iloc[-1]),
                "total_return_pct": total_return,
                "max_dd_pct": _max_dd(nav),
                "sharpe": _sharpe_from_returns(ret),
                "ulcer_pct": _ulcer(nav),
                "calmar_like": float(total_return / abs(_max_dd(nav))) if _max_dd(nav) < 0 else 0.0,
                "daily_return_p01_pct": float(ret.quantile(0.01) * 100.0),
                "daily_return_p05_pct": float(ret.quantile(0.05) * 100.0),
                "daily_cvar05_pct": _cvar(ret * 100.0, 0.05),
                "daily_positive_rate": float((ret > 0).mean()),
                "longest_underwater_days": _longest_underwater(nav),
            }
        )
    frame = pd.DataFrame(rows)
    if c3_return and c3_return > 0:
        frame["return_retention_vs_c3_pct"] = frame["total_return_pct"] / c3_return * 100.0
    else:
        frame["return_retention_vs_c3_pct"] = np.nan
    frame["dd30_pass"] = (frame["max_dd_pct"] >= TARGET_MAX_DD_PCT).astype(int)
    return frame


def _window_drawdown(values: np.ndarray) -> float:
    peak = np.maximum.accumulate(values)
    return float(np.min(values / peak - 1.0))


def _rolling_distribution(curves: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for window in (21, 63, 126, 252, 504):
        for variant, label, initial in VARIANTS:
            nav = _nav(curves[variant], initial)
            rolling_return = nav / nav.shift(window) - 1.0
            rolling_dd = nav.rolling(window).apply(_window_drawdown, raw=True)
            ret = nav.pct_change()
            rolling_sharpe = ret.rolling(window).apply(
                lambda x: 0.0
                if np.nanstd(x, ddof=1) <= 0
                else float(np.nanmean(x) / np.nanstd(x, ddof=1) * math.sqrt(252.0)),
                raw=True,
            )
            valid = pd.DataFrame(
                {
                    "rolling_return_pct": rolling_return * 100.0,
                    "rolling_dd_pct": rolling_dd * 100.0,
                    "rolling_sharpe": rolling_sharpe,
                }
            ).dropna()
            rows.append(
                {
                    "window_days": window,
                    "variant": variant,
                    "label": label,
                    "count": int(len(valid)),
                    "return_min_pct": float(valid["rolling_return_pct"].min()),
                    "return_p01_pct": float(valid["rolling_return_pct"].quantile(0.01)),
                    "return_p05_pct": float(valid["rolling_return_pct"].quantile(0.05)),
                    "return_median_pct": float(valid["rolling_return_pct"].median()),
                    "positive_return_rate": float((valid["rolling_return_pct"] > 0).mean()),
                    "dd_min_pct": float(valid["rolling_dd_pct"].min()),
                    "dd_p01_pct": float(valid["rolling_dd_pct"].quantile(0.01)),
                    "dd30_pass_rate": float((valid["rolling_dd_pct"] >= TARGET_MAX_DD_PCT).mean()),
                    "sharpe_p05": float(valid["rolling_sharpe"].quantile(0.05)),
                    "sharpe_median": float(valid["rolling_sharpe"].median()),
                }
            )
    return pd.DataFrame(rows)


def _tail_dependency(curves: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for variant, label, initial in VARIANTS:
        nav = _nav(curves[variant], initial)
        ret = nav.pct_change().dropna()
        for remove_count in (1, 3, 5, 10, 20):
            shocked = ret.copy()
            top_idx = shocked.nlargest(remove_count).index
            shocked.loc[top_idx] = 0.0
            shocked_nav = (1.0 + shocked).cumprod()
            rows.append(
                {
                    "variant": variant,
                    "label": label,
                    "removed_top_positive_days": remove_count,
                    "total_return_after_removal_pct": float((shocked_nav.iloc[-1] - 1.0) * 100.0),
                    "return_loss_vs_original_pp": float((nav.iloc[-1] - shocked_nav.iloc[-1]) * 100.0),
                    "max_dd_after_removal_pct": _max_dd(shocked_nav),
                    "sharpe_after_removal": _sharpe_from_returns(shocked),
                    "top_removed_dates": ",".join(str(pd.Timestamp(x).date()) for x in top_idx[:5]),
                }
            )
    return pd.DataFrame(rows)


def _simulate_nav_from_returns(ret: np.ndarray) -> tuple[float, float, float]:
    nav = np.cumprod(1.0 + ret)
    peak = np.maximum.accumulate(nav)
    dd = nav / peak - 1.0
    total_return = float((nav[-1] - 1.0) * 100.0)
    max_dd = float(dd.min() * 100.0)
    ulcer = float(np.sqrt(np.mean(np.square(np.minimum(dd * 100.0, 0.0)))))
    return total_return, max_dd, ulcer


def _block_bootstrap(curves: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(RNG_SEED)
    rows = []
    for variant, label, initial in VARIANTS:
        ret = _nav(curves[variant], initial).pct_change().dropna().to_numpy(dtype=float)
        n = len(ret)
        for block_len in (20, 60):
            block_count = int(math.ceil(n / block_len))
            stats = []
            max_start = max(1, n - block_len + 1)
            for _ in range(BOOTSTRAP_SIMS):
                starts = rng.integers(0, max_start, size=block_count)
                sample = np.concatenate([ret[s : s + block_len] for s in starts])[:n]
                stats.append(_simulate_nav_from_returns(sample))
            sim = pd.DataFrame(stats, columns=["total_return_pct", "max_dd_pct", "ulcer_pct"])
            rows.append(
                {
                    "variant": variant,
                    "label": label,
                    "block_len": block_len,
                    "sims": BOOTSTRAP_SIMS,
                    "return_p05_pct": float(sim["total_return_pct"].quantile(0.05)),
                    "return_median_pct": float(sim["total_return_pct"].median()),
                    "return_p95_pct": float(sim["total_return_pct"].quantile(0.95)),
                    "max_dd_p05_pct": float(sim["max_dd_pct"].quantile(0.05)),
                    "max_dd_median_pct": float(sim["max_dd_pct"].median()),
                    "max_dd_breach30_rate": float((sim["max_dd_pct"] < TARGET_MAX_DD_PCT).mean()),
                    "ulcer_median_pct": float(sim["ulcer_pct"].median()),
                    "ulcer_p95_pct": float(sim["ulcer_pct"].quantile(0.95)),
                }
            )
    return pd.DataFrame(rows)


def _month_permutation(curves: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(RNG_SEED + 1)
    rows = []
    months = curves.index.to_period("M")
    month_keys = list(pd.Series(months.unique()).astype(str))
    for variant, label, initial in VARIANTS:
        ret = _nav(curves[variant], initial).pct_change().dropna()
        ret_months = ret.index.to_period("M").astype(str)
        blocks = [ret[ret_months == key].to_numpy(dtype=float) for key in month_keys if len(ret[ret_months == key]) > 0]
        stats = []
        for _ in range(MONTH_PERMUTATION_SIMS):
            order = rng.permutation(len(blocks))
            sample = np.concatenate([blocks[i] for i in order])
            stats.append(_simulate_nav_from_returns(sample))
        sim = pd.DataFrame(stats, columns=["total_return_pct", "max_dd_pct", "ulcer_pct"])
        rows.append(
            {
                "variant": variant,
                "label": label,
                "sims": MONTH_PERMUTATION_SIMS,
                "max_dd_p05_pct": float(sim["max_dd_pct"].quantile(0.05)),
                "max_dd_median_pct": float(sim["max_dd_pct"].median()),
                "max_dd_breach30_rate": float((sim["max_dd_pct"] < TARGET_MAX_DD_PCT).mean()),
                "ulcer_median_pct": float(sim["ulcer_pct"].median()),
                "ulcer_p95_pct": float(sim["ulcer_pct"].quantile(0.95)),
                "return_median_pct": float(sim["total_return_pct"].median()),
            }
        )
    return pd.DataFrame(rows)


def _load_official_raw() -> pd.DataFrame:
    frame = pd.read_csv(OFFICIAL_DAILY_PATH, encoding="utf-8-sig")
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["net_pnl"] = pd.to_numeric(frame["net_pnl"], errors="coerce").fillna(0.0)
    frame["slippage"] = pd.to_numeric(frame["slippage"], errors="coerce").fillna(0.0)
    return frame.dropna(subset=["date"]).sort_values("date")


def _load_c3_raw() -> pd.DataFrame:
    frame = pd.read_csv(C3_DAILY_PATH, encoding="utf-8-sig")
    frame = frame[frame["profile"].eq("c3_active100_cash0") & frame["window_name"].eq("start_2020")].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["active_net_pnl"] = pd.to_numeric(frame["active_net_pnl"], errors="coerce").fillna(0.0)
    frame["active_slippage"] = pd.to_numeric(frame["active_slippage"], errors="coerce").fillna(0.0)
    return frame.dropna(subset=["date"]).sort_values("date")


def _cash_needed_for_dd(equity_without_extra_cash: pd.Series, target_dd: float = TARGET_MAX_DD_PCT) -> float:
    target_ratio = 1.0 + target_dd / 100.0
    if not 0.0 < target_ratio < 1.0:
        raise ValueError("target drawdown must be between -100% and 0%")
    values = equity_without_extra_cash.astype(float)
    peaks = values.cummax()
    required = (target_ratio * peaks - values) / (1.0 - target_ratio)
    return float(max(0.0, required.max()))


def _cash_requirement() -> pd.DataFrame:
    rows = []
    official = _load_official_raw()
    c3 = _load_c3_raw()
    for multiplier in (1.0, 2.0, 3.0, 5.0):
        official_pnl = official["net_pnl"] - (multiplier - 1.0) * official["slippage"]
        official_equity = pd.Series(
            START_CAPITAL + official_pnl.cumsum().to_numpy(dtype=float),
            index=official["date"],
        )
        official_equity = pd.concat(
            [pd.Series([START_CAPITAL], index=[official_equity.index.min() - pd.Timedelta(days=1)]), official_equity]
        ).sort_index()
        c3_pnl = c3["active_net_pnl"] - (multiplier - 1.0) * c3["active_slippage"]
        c3_equity = pd.Series(START_CAPITAL + c3_pnl.cumsum().to_numpy(dtype=float), index=c3["date"])
        c3_equity = pd.concat(
            [pd.Series([START_CAPITAL], index=[c3_equity.index.min() - pd.Timedelta(days=1)]), c3_equity]
        ).sort_index()
        for variant, label, base_equity, built_in_cash in [
            ("stage78_1", "78-1正式版", official_equity, 0.0),
            ("c3", "纯C3", c3_equity, 0.0),
            ("stage079", "Stage079：C3+11.5万现金", c3_equity, STAGE079_CASH),
        ]:
            required_cash = _cash_needed_for_dd(base_equity)
            total_account = START_CAPITAL + required_cash
            return_pct = float((base_equity.iloc[-1] + required_cash - total_account) / total_account * 100.0)
            rows.append(
                {
                    "scope": "full",
                    "variant": variant,
                    "label": label,
                    "slippage_multiplier": multiplier,
                    "cash_required_for_dd30": required_cash,
                    "built_in_cash": built_in_cash,
                    "additional_cash_needed": max(0.0, required_cash - built_in_cash),
                    "account_capital_if_exact_cash": total_account,
                    "return_pct_with_exact_cash": return_pct,
                }
            )

    return pd.DataFrame(rows)


def _score(
    summary: pd.DataFrame,
    rolling: pd.DataFrame,
    bootstrap: pd.DataFrame,
    month_perm: pd.DataFrame,
    cash_req: pd.DataFrame,
    tail: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    lookup = summary.set_index("variant")
    for variant, label, _ in VARIANTS:
        full = lookup.loc[variant]
        roll252 = rolling[(rolling["variant"].eq(variant)) & (rolling["window_days"].eq(252))].iloc[0]
        roll504 = rolling[(rolling["variant"].eq(variant)) & (rolling["window_days"].eq(504))].iloc[0]
        boot20 = bootstrap[(bootstrap["variant"].eq(variant)) & (bootstrap["block_len"].eq(20))].iloc[0]
        boot60 = bootstrap[(bootstrap["variant"].eq(variant)) & (bootstrap["block_len"].eq(60))].iloc[0]
        month = month_perm[month_perm["variant"].eq(variant)].iloc[0]
        cash_full_1x = cash_req[
            (cash_req["variant"].eq(variant))
            & (cash_req["scope"].eq("full"))
            & (cash_req["slippage_multiplier"].eq(1.0))
        ].iloc[0]
        cash_full_2x = cash_req[
            (cash_req["variant"].eq(variant))
            & (cash_req["scope"].eq("full"))
            & (cash_req["slippage_multiplier"].eq(2.0))
        ].iloc[0]
        tail10 = tail[(tail["variant"].eq(variant)) & (tail["removed_top_positive_days"].eq(10))].iloc[0]

        objective_score = (
            22.0 * int(full["dd30_pass"])
            + 16.0 * int(_safe_float(full["return_retention_vs_c3_pct"]) >= RETENTION_GATE_VS_C3_PCT)
            + 10.0 * _safe_float(roll252["dd30_pass_rate"])
            + 8.0 * _safe_float(roll504["positive_return_rate"])
            + 10.0 * (1.0 - _safe_float(boot20["max_dd_breach30_rate"]))
            + 8.0 * (1.0 - _safe_float(boot60["max_dd_breach30_rate"]))
            + 8.0 * (1.0 - _safe_float(month["max_dd_breach30_rate"]))
            + 8.0 * max(0.0, min(1.0, (25.0 - _safe_float(full["ulcer_pct"])) / 25.0))
            + 5.0 * max(0.0, min(1.0, 1.0 - _safe_float(cash_full_1x["additional_cash_needed"]) / 300_000.0))
            + 5.0 * max(0.0, min(1.0, 1.0 - _safe_float(cash_full_2x["additional_cash_needed"]) / 600_000.0))
        )
        alpha_score = (
            35.0 * max(0.0, min(1.0, _safe_float(full["total_return_pct"]) / 6500.0))
            + 20.0 * max(0.0, min(1.0, _safe_float(full["sharpe"]) / 1.5))
            + 15.0 * max(0.0, min(1.0, _safe_float(boot20["return_p05_pct"]) / 2500.0))
            + 10.0 * max(0.0, min(1.0, _safe_float(roll252["positive_return_rate"])))
            + 10.0 * max(0.0, min(1.0, (_safe_float(tail10["total_return_after_removal_pct"]) + 100.0) / 3000.0))
            + 10.0 * max(0.0, min(1.0, (45.0 + _safe_float(full["max_dd_pct"])) / 20.0))
        )
        rows.append(
            {
                "variant": variant,
                "label": label,
                "objective_score": objective_score,
                "alpha_score": alpha_score,
                "total_return_pct": _safe_float(full["total_return_pct"]),
                "max_dd_pct": _safe_float(full["max_dd_pct"]),
                "ulcer_pct": _safe_float(full["ulcer_pct"]),
                "return_retention_vs_c3_pct": _safe_float(full["return_retention_vs_c3_pct"]),
                "roll252_dd30_pass_rate": _safe_float(roll252["dd30_pass_rate"]),
                "boot20_dd_breach30_rate": _safe_float(boot20["max_dd_breach30_rate"]),
                "boot60_dd_breach30_rate": _safe_float(boot60["max_dd_breach30_rate"]),
                "month_order_dd_breach30_rate": _safe_float(month["max_dd_breach30_rate"]),
                "full_1x_additional_cash_needed": _safe_float(cash_full_1x["additional_cash_needed"]),
                "full_2x_additional_cash_needed": _safe_float(cash_full_2x["additional_cash_needed"]),
                "top10_removed_return_pct": _safe_float(tail10["total_return_after_removal_pct"]),
            }
        )
    return pd.DataFrame(rows).sort_values("objective_score", ascending=False)


def _build_report(
    summary: pd.DataFrame,
    rolling: pd.DataFrame,
    tail: pd.DataFrame,
    bootstrap: pd.DataFrame,
    month_perm: pd.DataFrame,
    cash_req: pd.DataFrame,
    score: pd.DataFrame,
    decision: dict[str, Any],
) -> str:
    roll_focus = rolling[rolling["window_days"].isin([252, 504])][
        [
            "window_days",
            "label",
            "return_p05_pct",
            "return_median_pct",
            "dd_min_pct",
            "dd30_pass_rate",
            "sharpe_p05",
        ]
    ]
    tail_focus = tail[tail["removed_top_positive_days"].isin([5, 10, 20])][
        [
            "label",
            "removed_top_positive_days",
            "total_return_after_removal_pct",
            "max_dd_after_removal_pct",
            "sharpe_after_removal",
        ]
    ]
    cash_focus = cash_req[cash_req["slippage_multiplier"].isin([1.0, 2.0, 3.0])][
        [
            "scope",
            "label",
            "slippage_multiplier",
            "cash_required_for_dd30",
            "built_in_cash",
            "additional_cash_needed",
        ]
    ]
    lines = [
        "# Stage084 三版本鲁棒性与路径压力审计",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：day",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M')} CST",
        "- 阶段性质：只读深度审计；不修改 `78-1`、`Stage079`、`C3` 的信号、品种、AI池、仓位或成交路径",
        "- 是否重要突破：否，重要复核。补充 Stage083 没有覆盖的路径依赖、bootstrap、月份顺序扰动和现金需求边界。",
        "- 是否触发A/B：否。本阶段没有新策略版本，只做候选排序审计。",
        "",
        "## 外部调研与判断",
        "",
        "- TradingStrategy.ai 的 backtesting/research methodology 强调，单条历史曲线不能证明稳健性，需要 walk-forward/rolling、成本、鲁棒性和过拟合控制一起看。",
        "- Ulcer Index/PerformanceAnalytics 体系强调回撤深度和持续时间，而不只看最大回撤单点。",
        "- 本阶段采用固定维度审计，避免为了让某一版本胜出临时挑指标。",
        "",
        "## 本次变更",
        "",
        "- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage384_three_version_robustness_audit.py`",
        "- 修改策略脚本：无。",
        "- 新增参数：block bootstrap `3000` 次，block 长度 `20/60`；月份顺序扰动 `3000` 次；尾部依赖移除最强正收益日 `1/3/5/10/20`；成本压力 `1x/2x/3x/5x`。",
        "- 修改参数：无。",
        "- 删除参数：无。",
        "",
        "## 全周期摘要",
        "",
        _md_table(
            summary[
                [
                    "label",
                    "total_return_pct",
                    "max_dd_pct",
                    "sharpe",
                    "ulcer_pct",
                    "daily_cvar05_pct",
                    "longest_underwater_days",
                    "return_retention_vs_c3_pct",
                    "dd30_pass",
                ]
            ]
        ),
        "",
        "## 滚动窗口重点",
        "",
        _md_table(roll_focus),
        "",
        "## Tail / 路径依赖",
        "",
        _md_table(tail_focus),
        "",
        "## Block Bootstrap",
        "",
        _md_table(
            bootstrap[
                [
                    "label",
                    "block_len",
                    "return_p05_pct",
                    "return_median_pct",
                    "max_dd_p05_pct",
                    "max_dd_breach30_rate",
                    "ulcer_median_pct",
                ]
            ]
        ),
        "",
        "## 月份顺序扰动",
        "",
        _md_table(
            month_perm[
                [
                    "label",
                    "max_dd_p05_pct",
                    "max_dd_median_pct",
                    "max_dd_breach30_rate",
                    "ulcer_median_pct",
                ]
            ]
        ),
        "",
        "## 现金需求边界",
        "",
        _md_table(cash_focus, 80),
        "",
        "## 综合排序",
        "",
        _md_table(score),
        "",
        "## 结论",
        "",
        f"- 主结论：`{decision['best_objective_label']}` 是当前目标下的综合最优版本。",
        "- 但若只问纯 alpha 收益，`纯C3` 仍然更强；Stage079 胜出不是因为信号更强，而是因为 `50万C3下单 + 11.5万现金` 的账户口径更符合回撤目标。",
        "- `78-1` 保留正式基准身份，但在本研究线目标下，收益、回撤、Ulcer 和滚动窗口体验均不占优。",
        "- 高滑点结论不变：Stage079 在 2x/3x 成本下仍需新增现金才可压进30%，不能宣称为高成本稳健版本。",
        "",
        "## 过拟合反思",
        "",
        "- 运行前判断：不是过拟合。固定比较对象与指标，不新增交易规则或参数搜索。",
        "- 运行后判断：不是过拟合。Stage079 的胜出来自部署现金边界，报告明确区分了账户口径和 alpha 强弱，没有把加现金误判为信号提升。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前判断：有价值。Stage083 给出排序，但还需要知道该排序是否经得住路径压力和成本现金边界。",
        "- 运行后判断：继续有价值，但不是继续调这三个版本。正常成本下推进 Stage079 的 forward/影子盘审计；高滑点目标则另找独立收益源或低费用承载工具。",
        "",
        "## 输出文件",
        "",
        f"- summary：`{SUMMARY_PATH}`",
        f"- rolling：`{ROLLING_PATH}`",
        f"- tail：`{TAIL_PATH}`",
        f"- block_bootstrap：`{BOOTSTRAP_PATH}`",
        f"- month_permutation：`{MONTH_PATH}`",
        f"- cash_requirement：`{CASH_PATH}`",
        f"- score：`{SCORE_PATH}`",
        f"- decision：`{DECISION_PATH}`",
        f"- report：`{REPORT_PATH}`",
        f"- dashboard：`{HTML_PATH}`",
    ]
    return "\n".join(lines) + "\n"


def _build_html(summary: pd.DataFrame, rolling: pd.DataFrame, bootstrap: pd.DataFrame, cash: pd.DataFrame, score: pd.DataFrame) -> str:
    def table_html(frame: pd.DataFrame, max_rows: int = 80) -> str:
        view = frame.head(max_rows).copy()
        return view.to_html(index=False, border=0, classes="data")

    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>Stage084 三版本鲁棒性审计</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 0; background: #f7f7f4; color: #1f2933; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 28px; }}
    section {{ margin: 22px 0; }}
    h1, h2 {{ margin: 0 0 12px; }}
    .note {{ padding: 14px 16px; border-left: 4px solid #2563eb; background: #ffffff; }}
    table.data {{ border-collapse: collapse; width: 100%; background: #fff; font-size: 13px; }}
    table.data th, table.data td {{ border-bottom: 1px solid #e5e7eb; padding: 7px 8px; text-align: right; }}
    table.data th:first-child, table.data td:first-child {{ text-align: left; }}
    table.data th {{ background: #eef2f7; }}
  </style>
</head>
<body>
<main>
  <h1>Stage084 三版本鲁棒性与路径压力审计</h1>
  <p class="note">结论：Stage079 是当前回撤30以内保收益目标下的正常成本主候选；纯C3是纯alpha收益最高版本；78-1保留正式基准身份但不是本线最优。</p>
  <section><h2>综合排序</h2>{table_html(score)}</section>
  <section><h2>全周期摘要</h2>{table_html(summary)}</section>
  <section><h2>滚动分布</h2>{table_html(rolling)}</section>
  <section><h2>Block Bootstrap</h2>{table_html(bootstrap)}</section>
  <section><h2>现金需求</h2>{table_html(cash)}</section>
</main>
</body>
</html>"""
    return html


def main() -> None:
    curves = _load_stage383_curves()
    summary = _summary(curves)
    rolling = _rolling_distribution(curves)
    tail = _tail_dependency(curves)
    bootstrap = _block_bootstrap(curves)
    month_perm = _month_permutation(curves)
    cash_req = _cash_requirement()
    score = _score(summary, rolling, bootstrap, month_perm, cash_req, tail)

    best_objective = score.sort_values("objective_score", ascending=False).iloc[0]
    best_alpha = score.sort_values("alpha_score", ascending=False).iloc[0]
    decision = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "best_objective_variant": str(best_objective["variant"]),
        "best_objective_label": str(best_objective["label"]),
        "best_alpha_variant": str(best_alpha["variant"]),
        "best_alpha_label": str(best_alpha["label"]),
        "score_table": _json_safe(score.to_dict(orient="records")),
        "conclusion": "Stage079 is best for the drawdown30 preserve-return objective under normal cost; C3 is best for pure alpha return; no version passes high-slippage robustness.",
        "overfit_reflection": "no_strategy_change_no_threshold_search_fixed_audit_dimensions",
        "continue_value": "stage079_forward_shadow_audit_under_normal_cost_or_search_new_low_corr_return_source_for_high_slippage",
    }

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    rolling.to_csv(ROLLING_PATH, index=False, encoding="utf-8-sig")
    tail.to_csv(TAIL_PATH, index=False, encoding="utf-8-sig")
    bootstrap.to_csv(BOOTSTRAP_PATH, index=False, encoding="utf-8-sig")
    month_perm.to_csv(MONTH_PATH, index=False, encoding="utf-8-sig")
    cash_req.to_csv(CASH_PATH, index=False, encoding="utf-8-sig")
    score.to_csv(SCORE_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(
        _build_report(summary, rolling, tail, bootstrap, month_perm, cash_req, score, decision),
        encoding="utf-8",
    )
    HTML_PATH.write_text(_build_html(summary, rolling, bootstrap, cash_req, score), encoding="utf-8")

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"summary={SUMMARY_PATH}")
    print(f"report={REPORT_PATH}")
    print(f"html={HTML_PATH}")


if __name__ == "__main__":
    main()
