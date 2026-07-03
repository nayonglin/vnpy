from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
UPSTREAM_LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage003"
MODEL_TAG = "stage003_residual_complement_audit_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage003_residual_complement_audit"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
UPSTREAM_LINE_DIR = PROJECT_DIR / "research" / "lines" / UPSTREAM_LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage003_residual_complement_audit"

STAGE052_CURVES_PATH = (
    UPSTREAM_LINE_DIR
    / "outputs"
    / "stage052_contract_oi_share_add_risk_proxy"
    / "rebuilt_c9_stage052_contract_oi_share_add_risk_proxy_curves_stage052_contract_oi_share_add_risk_proxy_v1.csv"
)
STAGE074_PANEL_PATH = (
    UPSTREAM_LINE_DIR
    / "outputs"
    / "stage074_cold_start_capital_ramp_proxy"
    / "rebuilt_c9_stage074_cold_start_capital_ramp_proxy_panel_curves_stage074_cold_start_capital_ramp_proxy_v1.csv.gz"
)
STAGE074_TARGET_VARIANT = "full_market_ai_top8_and_active_positions_lt3"
STAGE074_AUDIT_VARIANT = f"{STAGE074_TARGET_VARIANT}_cold_start_ramp"
RAMP_FLOOR = 0.35
RAMP_TRADING_DAYS = 252

SOURCE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_summary_{MODEL_TAG}.csv"
MONTH_CLUSTER_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_month_cluster_summary_{MODEL_TAG}.csv"
ORACLE_WORST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_oracle_worst_windows_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_negative_overlap_chart_{MODEL_TAG}.png"

OBJECTIVE_START_MIN = pd.Timestamp("2020-01-01")
OBJECTIVE_START_MAX = pd.Timestamp("2025-06-30")
MIN_PERIOD_CALENDAR_DAYS = 366
WORST_LIMIT_PER_SOURCE = 120


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if pd.isna(value):
        return None
    return value


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, encoding="utf-8-sig")


def _ret_pct(start_equity: float, end_equity: np.ndarray) -> np.ndarray:
    if start_equity == 0:
        return np.full_like(end_equity, np.nan, dtype=float)
    return (end_equity / float(start_equity) - 1.0) * 100.0


def compute_age_ramp_multiplier(
    length: int,
    *,
    floor: float = RAMP_FLOOR,
    ramp_trading_days: int = RAMP_TRADING_DAYS,
) -> np.ndarray:
    if length <= 0:
        return np.array([], dtype=float)
    days = max(1, int(ramp_trading_days))
    floor_value = max(0.0, min(1.0, float(floor)))
    age_for_pnl = np.maximum(np.arange(length, dtype=float) - 1.0, 0.0)
    if days <= 1:
        values = np.ones(length, dtype=float)
        values[0] = floor_value
        return values
    ramp = floor_value + (1.0 - floor_value) * np.minimum(age_for_pnl, days - 1.0) / (days - 1.0)
    return np.clip(ramp, floor_value, 1.0)


def start_reset_ramp_returns(
    equity: np.ndarray,
    start_index: int,
    end_indices: np.ndarray,
    *,
    floor: float = RAMP_FLOOR,
    ramp_trading_days: int = RAMP_TRADING_DAYS,
) -> np.ndarray:
    start_equity = float(equity[start_index])
    segment = equity[start_index : int(end_indices[-1]) + 1]
    pnl = np.diff(segment, prepend=segment[0])
    multiplier = compute_age_ramp_multiplier(len(segment), floor=floor, ramp_trading_days=ramp_trading_days)
    adjusted = start_equity + np.cumsum(pnl * multiplier)
    local_end_indices = end_indices - start_index
    return _ret_pct(start_equity, adjusted[local_end_indices])


def build_aligned_panel(stage052_curves: pd.DataFrame, stage074_panel: pd.DataFrame) -> pd.DataFrame:
    stage052 = stage052_curves[
        ["requested_start_month", "date", "account_equity", "stage052_account_equity"]
    ].copy()
    stage052.rename(columns={"account_equity": "base", "stage052_account_equity": "stage052"}, inplace=True)
    stage052["date"] = pd.to_datetime(stage052["date"], errors="coerce").dt.normalize()

    stage074 = stage074_panel[stage074_panel["variant"].eq(STAGE074_TARGET_VARIANT)].copy()
    stage074 = stage074[["requested_start_month", "date", "equity"]].copy()
    stage074.rename(columns={"equity": "stage074"}, inplace=True)
    stage074["date"] = pd.to_datetime(stage074["date"], errors="coerce").dt.normalize()

    panel = stage052.merge(stage074, on=["requested_start_month", "date"], how="inner")
    for column in ("base", "stage052", "stage074"):
        panel[column] = pd.to_numeric(panel[column], errors="coerce")
    panel = panel.dropna(subset=["requested_start_month", "date", "base", "stage052", "stage074"])
    return panel[["requested_start_month", "date", "base", "stage052", "stage074"]].sort_values(
        ["requested_start_month", "date"]
    ).reset_index(drop=True)


def _corr_from_sums(n: int, sum_x: float, sum_y: float, sum_x2: float, sum_y2: float, sum_xy: float) -> float:
    if n <= 1:
        return np.nan
    numerator = sum_xy - (sum_x * sum_y / n)
    denom_x = sum_x2 - (sum_x * sum_x / n)
    denom_y = sum_y2 - (sum_y * sum_y / n)
    denominator = np.sqrt(max(denom_x, 0.0) * max(denom_y, 0.0))
    if denominator == 0:
        return np.nan
    return float(numerator / denominator)


def _update_cluster(
    clusters: dict[tuple[str, str], dict[str, Any]],
    start_month: str,
    end_months: pd.Series,
    base_negative: np.ndarray,
    oracle_negative: np.ndarray,
    oracle_returns: np.ndarray,
) -> None:
    if len(end_months) == 0:
        return
    cluster_frame = pd.DataFrame(
        {
            "end_month": end_months.to_numpy(),
            "base_negative": base_negative.astype(int),
            "oracle_negative": oracle_negative.astype(int),
            "oracle_return_pct": oracle_returns,
        }
    )
    for end_month, group in cluster_frame.groupby("end_month"):
        key = (start_month, str(end_month))
        row = clusters.setdefault(
            key,
            {
                "start_year_month": start_month,
                "end_year_month": str(end_month),
                "base_negative_count": 0,
                "oracle_negative_count": 0,
                "oracle_min_return_pct": np.inf,
            },
        )
        row["base_negative_count"] += int(group["base_negative"].sum())
        row["oracle_negative_count"] += int(group["oracle_negative"].sum())
        row["oracle_min_return_pct"] = min(row["oracle_min_return_pct"], float(group["oracle_return_pct"].min()))


def audit_group(
    source_start_month: str,
    group: pd.DataFrame,
    *,
    objective_start_min: pd.Timestamp = OBJECTIVE_START_MIN,
    objective_start_max: pd.Timestamp = OBJECTIVE_START_MAX,
    min_period_calendar_days: int = MIN_PERIOD_CALENDAR_DAYS,
    worst_limit: int = WORST_LIMIT_PER_SOURCE,
    apply_stage074_start_reset_ramp: bool = False,
    ramp_floor: float = RAMP_FLOOR,
    ramp_trading_days: int = RAMP_TRADING_DAYS,
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    data = group.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    dates = data["date"].to_numpy(dtype="datetime64[ns]")
    date_series = pd.to_datetime(data["date"], errors="coerce")
    base = data["base"].to_numpy(dtype=float)
    stage052 = data["stage052"].to_numpy(dtype=float)
    stage074 = data["stage074"].to_numpy(dtype=float)
    objective_mask = (date_series >= objective_start_min) & (date_series <= objective_start_max)
    start_indices = np.flatnonzero(objective_mask.to_numpy())

    counters = {
        "window_count": 0,
        "base_negative_count": 0,
        "stage052_negative_count": 0,
        "stage074_negative_count": 0,
        "oracle_negative_count": 0,
        "base_negative_stage052_fixed_count": 0,
        "base_negative_stage074_fixed_count": 0,
        "base_negative_both_fixed_count": 0,
        "base_negative_either_fixed_count": 0,
        "base_negative_neither_fixed_count": 0,
    }
    min_returns = {
        "base_min_return_pct": np.inf,
        "stage052_min_return_pct": np.inf,
        "stage074_min_return_pct": np.inf,
        "oracle_min_return_pct": np.inf,
    }
    sums = {
        "sum_delta052": 0.0,
        "sum_delta074": 0.0,
        "sum_delta052_sq": 0.0,
        "sum_delta074_sq": 0.0,
        "sum_delta052_delta074": 0.0,
    }
    worst_rows: list[dict[str, Any]] = []
    clusters: dict[tuple[str, str], dict[str, Any]] = {}

    for idx in start_indices:
        start_date = pd.Timestamp(dates[idx])
        min_end_date = start_date + pd.Timedelta(days=min_period_calendar_days)
        min_end_idx = int(np.searchsorted(dates, np.datetime64(min_end_date), side="left"))
        if min_end_idx >= len(dates):
            continue

        end_indices = np.arange(min_end_idx, len(dates), dtype=int)
        base_ret = _ret_pct(float(base[idx]), base[end_indices])
        stage052_ret = _ret_pct(float(stage052[idx]), stage052[end_indices])
        if apply_stage074_start_reset_ramp:
            stage074_ret = start_reset_ramp_returns(
                stage074,
                idx,
                end_indices,
                floor=ramp_floor,
                ramp_trading_days=ramp_trading_days,
            )
        else:
            stage074_ret = _ret_pct(float(stage074[idx]), stage074[end_indices])
        valid = np.isfinite(base_ret) & np.isfinite(stage052_ret) & np.isfinite(stage074_ret)
        if not bool(valid.any()):
            continue
        end_indices = end_indices[valid]
        base_ret = base_ret[valid]
        stage052_ret = stage052_ret[valid]
        stage074_ret = stage074_ret[valid]
        oracle_ret = np.maximum(stage052_ret, stage074_ret)

        base_negative = base_ret < 0.0
        stage052_negative = stage052_ret < 0.0
        stage074_negative = stage074_ret < 0.0
        oracle_negative = oracle_ret < 0.0

        counters["window_count"] += int(len(base_ret))
        counters["base_negative_count"] += int(base_negative.sum())
        counters["stage052_negative_count"] += int(stage052_negative.sum())
        counters["stage074_negative_count"] += int(stage074_negative.sum())
        counters["oracle_negative_count"] += int(oracle_negative.sum())
        counters["base_negative_stage052_fixed_count"] += int((base_negative & ~stage052_negative).sum())
        counters["base_negative_stage074_fixed_count"] += int((base_negative & ~stage074_negative).sum())
        counters["base_negative_both_fixed_count"] += int((base_negative & ~stage052_negative & ~stage074_negative).sum())
        counters["base_negative_either_fixed_count"] += int((base_negative & (~stage052_negative | ~stage074_negative)).sum())
        counters["base_negative_neither_fixed_count"] += int((base_negative & stage052_negative & stage074_negative).sum())

        min_returns["base_min_return_pct"] = min(min_returns["base_min_return_pct"], float(base_ret.min()))
        min_returns["stage052_min_return_pct"] = min(min_returns["stage052_min_return_pct"], float(stage052_ret.min()))
        min_returns["stage074_min_return_pct"] = min(min_returns["stage074_min_return_pct"], float(stage074_ret.min()))
        min_returns["oracle_min_return_pct"] = min(min_returns["oracle_min_return_pct"], float(oracle_ret.min()))

        delta052 = stage052_ret - base_ret
        delta074 = stage074_ret - base_ret
        sums["sum_delta052"] += float(delta052.sum())
        sums["sum_delta074"] += float(delta074.sum())
        sums["sum_delta052_sq"] += float(np.square(delta052).sum())
        sums["sum_delta074_sq"] += float(np.square(delta074).sum())
        sums["sum_delta052_delta074"] += float((delta052 * delta074).sum())

        cluster_mask = base_negative | oracle_negative
        if bool(cluster_mask.any()):
            cluster_end_indices = end_indices[cluster_mask]
            cluster_end_months = pd.Series(pd.to_datetime(dates[cluster_end_indices]).strftime("%Y-%m"))
            _update_cluster(
                clusters,
                start_date.strftime("%Y-%m"),
                cluster_end_months,
                base_negative[cluster_mask],
                oracle_negative[cluster_mask],
                oracle_ret[cluster_mask],
            )

        if bool(oracle_negative.any()):
            neg_end_indices = end_indices[oracle_negative]
            neg_oracle = oracle_ret[oracle_negative]
            neg_base = base_ret[oracle_negative]
            neg_052 = stage052_ret[oracle_negative]
            neg_074 = stage074_ret[oracle_negative]

            k = min(worst_limit, len(neg_oracle))
            local = np.argpartition(neg_oracle, k - 1)[:k]
            for local_pos in local:
                end_idx = int(neg_end_indices[local_pos])
                worst_rows.append(
                    {
                        "source_start_month": source_start_month,
                        "start_date": start_date.date().isoformat(),
                        "end_date": pd.Timestamp(dates[end_idx]).date().isoformat(),
                        "period_calendar_days": int((pd.Timestamp(dates[end_idx]) - start_date).days),
                        "base_return_pct": float(neg_base[local_pos]),
                        "stage052_return_pct": float(neg_052[local_pos]),
                        "stage074_return_pct": float(neg_074[local_pos]),
                        "oracle_return_pct": float(neg_oracle[local_pos]),
                    }
                )

    window_count = counters["window_count"]
    summary = {
        "source_start_month": source_start_month,
        **counters,
        "base_negative_rate_pct": counters["base_negative_count"] / window_count * 100.0 if window_count else np.nan,
        "stage052_negative_rate_pct": counters["stage052_negative_count"] / window_count * 100.0 if window_count else np.nan,
        "stage074_negative_rate_pct": counters["stage074_negative_count"] / window_count * 100.0 if window_count else np.nan,
        "oracle_negative_rate_pct": counters["oracle_negative_count"] / window_count * 100.0 if window_count else np.nan,
        "base_negative_either_fixed_rate_pct": (
            counters["base_negative_either_fixed_count"] / counters["base_negative_count"] * 100.0
            if counters["base_negative_count"]
            else np.nan
        ),
        "delta_improvement_corr": _corr_from_sums(
            window_count,
            sums["sum_delta052"],
            sums["sum_delta074"],
            sums["sum_delta052_sq"],
            sums["sum_delta074_sq"],
            sums["sum_delta052_delta074"],
        ),
        **{key: (value if np.isfinite(value) else np.nan) for key, value in min_returns.items()},
    }

    worst = pd.DataFrame(worst_rows)
    if not worst.empty:
        worst = worst.sort_values("oracle_return_pct").head(worst_limit).reset_index(drop=True)

    cluster_rows = list(clusters.values())
    clusters_frame = pd.DataFrame(cluster_rows)
    if not clusters_frame.empty:
        clusters_frame["source_start_month"] = source_start_month
        clusters_frame = clusters_frame[
            [
                "source_start_month",
                "start_year_month",
                "end_year_month",
                "base_negative_count",
                "oracle_negative_count",
                "oracle_min_return_pct",
            ]
        ].sort_values(["oracle_min_return_pct", "oracle_negative_count"], ascending=[True, False]).reset_index(drop=True)

    return summary, worst, clusters_frame


def audit_panel(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    summary_rows: list[dict[str, Any]] = []
    worst_frames: list[pd.DataFrame] = []
    cluster_frames: list[pd.DataFrame] = []
    for source_start_month, group in panel.groupby("requested_start_month", sort=True):
        summary, worst, clusters = audit_group(
            str(source_start_month),
            group,
            apply_stage074_start_reset_ramp=True,
        )
        summary_rows.append(summary)
        if not worst.empty:
            worst_frames.append(worst)
        if not clusters.empty:
            cluster_frames.append(clusters)

    source_summary = pd.DataFrame(summary_rows)
    worst_windows = pd.concat(worst_frames, ignore_index=True, sort=False) if worst_frames else pd.DataFrame()
    month_clusters = pd.concat(cluster_frames, ignore_index=True, sort=False) if cluster_frames else pd.DataFrame()
    if not worst_windows.empty:
        worst_windows = worst_windows.sort_values("oracle_return_pct").head(1000).reset_index(drop=True)
    if not month_clusters.empty:
        month_clusters = month_clusters.sort_values(
            ["oracle_min_return_pct", "oracle_negative_count"], ascending=[True, False]
        ).reset_index(drop=True)
    return source_summary, worst_windows, month_clusters


def make_decision(source_summary: pd.DataFrame) -> dict[str, Any]:
    if source_summary.empty:
        return {"decision": "stage003_missing_source_summary", "window_count": 0, "best_case_strict_goal_pass": 0}
    numeric_cols = [
        "window_count",
        "base_negative_count",
        "stage052_negative_count",
        "stage074_negative_count",
        "oracle_negative_count",
        "base_negative_either_fixed_count",
        "base_negative_neither_fixed_count",
    ]
    data = source_summary.copy()
    for column in numeric_cols:
        if column not in data.columns:
            data[column] = 0
    for column in ("oracle_min_return_pct", "stage052_min_return_pct", "stage074_min_return_pct"):
        if column not in data.columns:
            data[column] = np.nan
    totals = {column: int(pd.to_numeric(data[column], errors="coerce").fillna(0).sum()) for column in numeric_cols}
    oracle_min = float(pd.to_numeric(data["oracle_min_return_pct"], errors="coerce").min())
    stage052_min = float(pd.to_numeric(data["stage052_min_return_pct"], errors="coerce").min())
    stage074_min = float(pd.to_numeric(data["stage074_min_return_pct"], errors="coerce").min())
    best_case_pass = int(totals["oracle_negative_count"] == 0 and oracle_min > 0.0)
    if best_case_pass:
        decision = "stage003_oracle_upper_bound_clears_path_needs_true_combo_engine"
    else:
        decision = "stage003_oracle_upper_bound_still_fails_not_enough"
    return {
        "decision": decision,
        "window_count": totals["window_count"],
        "base_negative_count": totals["base_negative_count"],
        "stage052_negative_count": totals["stage052_negative_count"],
        "stage074_negative_count": totals["stage074_negative_count"],
        "oracle_negative_count": totals["oracle_negative_count"],
        "oracle_negative_rate_pct": (
            totals["oracle_negative_count"] / totals["window_count"] * 100.0 if totals["window_count"] else None
        ),
        "base_negative_either_fixed_count": totals["base_negative_either_fixed_count"],
        "base_negative_neither_fixed_count": totals["base_negative_neither_fixed_count"],
        "oracle_min_return_pct": oracle_min,
        "stage052_min_return_pct": stage052_min,
        "stage074_min_return_pct": stage074_min,
        "best_case_strict_goal_pass": best_case_pass,
    }


def _plot_negative_overlap(decision: dict[str, Any]) -> None:
    labels = ["base", "stage052", "stage074", "oracle max"]
    values = [
        decision.get("base_negative_count", 0),
        decision.get("stage052_negative_count", 0),
        decision.get("stage074_negative_count", 0),
        decision.get("oracle_negative_count", 0),
    ]
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.bar(labels, values, color=["#4f6d7a", "#59a14f", "#f28e2b", "#d1495b"])
    ax.set_ylabel("Strict >1y negative windows")
    ax.set_title("Stage003 Stage052/Stage074 same-window complement upper bound")
    for index, value in enumerate(values):
        ax.text(index, value, f"{int(value):,}", ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def _md_table(frame: pd.DataFrame, max_rows: int = 20) -> str:
    if frame.empty:
        return "_无数据_"
    return frame.head(max_rows).to_markdown(index=False)


def _write_report(source_summary: pd.DataFrame, worst_windows: pd.DataFrame, month_clusters: pd.DataFrame, decision: dict[str, Any]) -> None:
    key_cols = [
        "source_start_month",
        "window_count",
        "base_negative_count",
        "stage052_negative_count",
        "stage074_negative_count",
        "oracle_negative_count",
        "oracle_min_return_pct",
        "delta_improvement_corr",
    ]
    lines = [
        "# Stage003 Stage052 vs Stage074 残差互补审计",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：day",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 阶段性质：同窗互补上界审计，不产生新交易规则",
        "- 是否重要突破：否",
        "- 是否触发A/B：否",
        "",
        "## 外部调研与判断",
        "",
        "- managed futures 与趋势跟随组合资料提示，互补收益流有机会降低组合回撤。",
        "- 多信号组合过拟合资料提示，直接把两个历史有效形状叠加很危险。",
        "- 我的判断：先看同一窗口内 Stage052 与 Stage074 的 oracle 上界；若上界仍失败，说明这两条旧路线本身互补不够。",
        "",
        "## 关键结果",
        "",
        f"- 决策：`{decision['decision']}`。",
        f"- 总窗口数：`{decision['window_count']}`。",
        f"- Stage013 base 负窗口：`{decision['base_negative_count']}`。",
        f"- Stage052 负窗口：`{decision['stage052_negative_count']}`，最差 `{decision['stage052_min_return_pct']:.4f}%`。",
        f"- Stage074 负窗口：`{decision['stage074_negative_count']}`，最差 `{decision['stage074_min_return_pct']:.4f}%`。",
        f"- oracle max(Stage052, Stage074) 负窗口：`{decision['oracle_negative_count']}`，最差 `{decision['oracle_min_return_pct']:.4f}%`。",
        f"- base 负窗口中至少一条路线修复：`{decision['base_negative_either_fixed_count']}`；两条都没修复：`{decision['base_negative_neither_fixed_count']}`。",
        "",
        "## Source 摘要",
        "",
        _md_table(source_summary[key_cols].sort_values("oracle_min_return_pct"), max_rows=20),
        "",
        "## oracle 剩余最差窗口",
        "",
        _md_table(worst_windows, max_rows=20),
        "",
        "## oracle 剩余负窗口月份聚类",
        "",
        _md_table(month_clusters, max_rows=20),
        "",
        "## 结论",
        "",
        "- 本阶段只做上界审计，不能当作真实组合引擎结论。",
        "- 若 oracle 上界仍有负窗口，说明单靠 Stage052/Stage074 两条旧路线的互补不足以达成用户目标。",
        "- 下一步应从 oracle 剩余窗口继续找真正新信息源或交易路径机制，而不是直接叠加两个代理。",
        "",
        "## 过拟合反思",
        "",
        "- 运行前判断：不过拟合，本阶段是同窗上界审计，不调参数。",
        "- 运行后判断：不过拟合。",
        "- 原因：没有新增交易规则，只验证两条已冻结路线的互补上限。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前判断：有价值。",
        "- 运行后判断：有价值。",
        "- 原因：能决定是否值得为 Stage052/074 写真实组合引擎，避免无效叠加。",
        "",
        "## 输出文件",
        "",
        f"- source_summary：`{SOURCE_SUMMARY_PATH}`",
        f"- month_cluster：`{MONTH_CLUSTER_PATH}`",
        f"- oracle_worst：`{ORACLE_WORST_PATH}`",
        f"- chart：`{CHART_PATH}`",
        f"- decision：`{DECISION_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stage052 = _read_csv(STAGE052_CURVES_PATH)
    stage074 = _read_csv(STAGE074_PANEL_PATH)
    panel = build_aligned_panel(stage052, stage074)
    source_summary, worst_windows, month_clusters = audit_panel(panel)
    decision = make_decision(source_summary)

    source_summary.to_csv(SOURCE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    worst_windows.to_csv(ORACLE_WORST_PATH, index=False, encoding="utf-8-sig")
    month_clusters.to_csv(MONTH_CLUSTER_PATH, index=False, encoding="utf-8-sig")
    _plot_negative_overlap(decision)
    _write_report(source_summary, worst_windows, month_clusters, decision)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    return decision


if __name__ == "__main__":
    main()
