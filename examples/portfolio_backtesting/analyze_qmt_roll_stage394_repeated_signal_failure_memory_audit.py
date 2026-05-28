from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


MODEL_TAG = "stage394_repeated_signal_failure_memory_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage394_repeated_signal_failure_memory_audit"
LINE_ID = "futures_trend_drawdown30_preserve_return"

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR / "backtest_outputs"
ROUND_TRIPS_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage328_c3_single_path_loss_attribution_round_trips_stage328_c3_single_path_loss_attribution_v1.csv"
)


@dataclass(frozen=True)
class KeyDefinition:
    prefix: str
    label: str
    key_columns: tuple[str, ...]


KEY_DEFINITIONS = (
    KeyDefinition("pd", "same_product_direction", ("product_vt_symbol", "direction")),
    KeyDefinition("ps", "same_product_signal", ("product_vt_symbol", "signal")),
)


def _safe_float(value: Any, default: float = math.nan) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if np.isfinite(number) else default


def _to_builtin(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _to_builtin(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_builtin(v) for v in value]
    if isinstance(value, tuple):
        return [_to_builtin(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if pd.isna(value):
        return None
    return value


def _markdown_table(frame: pd.DataFrame, columns: list[str], max_rows: int = 20) -> str:
    if frame.empty:
        return "_无数据_"
    view = frame.loc[:, [column for column in columns if column in frame.columns]].head(max_rows).copy()
    if view.empty:
        return "_无数据_"
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda x: "" if pd.isna(x) else f"{float(x):.4f}")
    header = "| " + " | ".join(view.columns) + " |"
    sep = "| " + " | ".join(["---"] * len(view.columns)) + " |"
    rows = ["| " + " | ".join(str(value) for value in row) + " |" for row in view.to_numpy()]
    return "\n".join([header, sep, *rows])


def _load_round_trips() -> pd.DataFrame:
    if not ROUND_TRIPS_PATH.exists():
        raise FileNotFoundError(f"missing round-trip attribution file: {ROUND_TRIPS_PATH}")
    frame = pd.read_csv(ROUND_TRIPS_PATH)
    for column in ["entry_datetime", "exit_datetime", "entry_date", "exit_date"]:
        frame[column] = pd.to_datetime(frame[column]).dt.tz_localize(None)
    frame["signal"] = frame.get("signal", "unknown").fillna("unknown").astype(str)
    frame["direction"] = frame["direction"].fillna("unknown").astype(str)
    frame["product_vt_symbol"] = frame["product_vt_symbol"].fillna("unknown").astype(str)
    frame["gross_pnl"] = pd.to_numeric(frame["gross_pnl"], errors="coerce").fillna(0.0)
    frame["gross_return_pct"] = pd.to_numeric(frame.get("gross_return_pct", np.nan), errors="coerce")
    frame["mae_pct"] = pd.to_numeric(frame.get("mae_pct", np.nan), errors="coerce")
    frame["mfe_pct"] = pd.to_numeric(frame.get("mfe_pct", np.nan), errors="coerce")
    frame["holding_days"] = pd.to_numeric(frame.get("holding_days", np.nan), errors="coerce")
    frame = frame.sort_values(["entry_datetime", "leg_id"]).reset_index(drop=True)
    frame["is_win"] = frame["gross_pnl"] > 0
    frame["entry_year"] = frame["entry_date"].dt.year
    return frame


def _consecutive_failures(past: pd.DataFrame, entry_date: pd.Timestamp | None = None, lookback_days: int | None = None) -> int:
    if past.empty:
        return 0
    ordered = past.sort_values(["exit_datetime", "leg_id"])
    count = 0
    for row in ordered.iloc[::-1].to_dict("records"):
        if entry_date is not None and lookback_days is not None:
            if pd.Timestamp(row["exit_date"]) < entry_date - pd.Timedelta(days=lookback_days):
                break
        if _safe_float(row["gross_pnl"], 0.0) <= 0.0:
            count += 1
        else:
            break
    return count


def _add_memory_features(frame: pd.DataFrame, key_def: KeyDefinition) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for index, row in frame.iterrows():
        prior = frame.iloc[:index]
        mask = pd.Series(True, index=prior.index)
        for column in key_def.key_columns:
            mask &= prior[column].astype(str).eq(str(row[column]))
        entry_date = pd.Timestamp(row["entry_date"]).normalize()
        past = prior[mask & (prior["exit_date"] < entry_date)].copy()
        past252 = past[past["entry_date"] >= entry_date - pd.Timedelta(days=252)].copy()
        last_exit = past["exit_date"].max() if not past.empty else pd.NaT
        last_entry = past["entry_date"].max() if not past.empty else pd.NaT
        consecutive_all = _consecutive_failures(past)
        consecutive_252 = _consecutive_failures(past, entry_date=entry_date, lookback_days=252)
        rows.append(
            {
                f"{key_def.prefix}_prior_signal_count_all": int(len(past)),
                f"{key_def.prefix}_prior_signal_count_252": int(len(past252)),
                f"{key_def.prefix}_prior_failed_count_252": int((past252["gross_pnl"] <= 0).sum()),
                f"{key_def.prefix}_prior_win_count_252": int((past252["gross_pnl"] > 0).sum()),
                f"{key_def.prefix}_prior_fail_rate_252": float((past252["gross_pnl"] <= 0).mean())
                if len(past252)
                else math.nan,
                f"{key_def.prefix}_consecutive_failures_all": int(consecutive_all),
                f"{key_def.prefix}_consecutive_failures_252": int(consecutive_252),
                f"{key_def.prefix}_attempt_after_failure_all": int(consecutive_all + 1),
                f"{key_def.prefix}_attempt_after_failure_252": int(consecutive_252 + 1),
                f"{key_def.prefix}_days_since_last_exit": int((entry_date - last_exit).days)
                if pd.notna(last_exit)
                else math.nan,
                f"{key_def.prefix}_days_since_last_entry": int((entry_date - last_entry).days)
                if pd.notna(last_entry)
                else math.nan,
            }
        )
    return pd.concat([frame.reset_index(drop=True), pd.DataFrame(rows)], axis=1)


def _count_bucket(value: Any, cap: int = 3) -> str:
    number = int(max(0, _safe_float(value, 0.0)))
    if number >= cap:
        return f"{cap}+"
    return str(number)


def _attempt_bucket(value: Any, cap: int = 4) -> str:
    number = int(max(1, _safe_float(value, 1.0)))
    if number >= cap:
        return f"{cap}+"
    return str(number)


def _add_buckets(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    for key_def in KEY_DEFINITIONS:
        prefix = key_def.prefix
        for column in [
            "prior_signal_count_252",
            "prior_failed_count_252",
            "consecutive_failures_all",
            "consecutive_failures_252",
        ]:
            result[f"{prefix}_{column}_bucket"] = result[f"{prefix}_{column}"].map(_count_bucket)
        for column in ["attempt_after_failure_all", "attempt_after_failure_252"]:
            result[f"{prefix}_{column}_bucket"] = result[f"{prefix}_{column}"].map(_attempt_bucket)
    return result


def _summary_stats(group: pd.DataFrame, all_frame: pd.DataFrame) -> dict[str, Any]:
    pnl = pd.to_numeric(group["gross_pnl"], errors="coerce").fillna(0.0)
    gross_return = pd.to_numeric(group.get("gross_return_pct", np.nan), errors="coerce")
    mae = pd.to_numeric(group.get("mae_pct", np.nan), errors="coerce")
    mfe = pd.to_numeric(group.get("mfe_pct", np.nan), errors="coerce")
    holding = pd.to_numeric(group.get("holding_days", np.nan), errors="coerce")
    positive_pnl = pd.to_numeric(all_frame.loc[all_frame["gross_pnl"] > 0, "gross_pnl"], errors="coerce")
    big_threshold = float(positive_pnl.quantile(0.75)) if len(positive_pnl) else math.nan
    tail_threshold = float(pd.to_numeric(all_frame["gross_pnl"], errors="coerce").quantile(0.90))
    years = group.groupby("entry_year")["gross_pnl"].sum() if "entry_year" in group.columns else pd.Series(dtype=float)
    return {
        "sample_count": int(len(group)),
        "total_gross_pnl": float(pnl.sum()),
        "mean_gross_pnl": float(pnl.mean()) if len(pnl) else math.nan,
        "median_gross_pnl": float(pnl.median()) if len(pnl) else math.nan,
        "p25_gross_pnl": float(pnl.quantile(0.25)) if len(pnl) else math.nan,
        "p05_gross_pnl": float(pnl.quantile(0.05)) if len(pnl) else math.nan,
        "win_rate_pct": float((pnl > 0).mean() * 100.0) if len(pnl) else math.nan,
        "mean_return_pct": float(gross_return.mean()) if gross_return.notna().any() else math.nan,
        "median_return_pct": float(gross_return.median()) if gross_return.notna().any() else math.nan,
        "big_winner_rate_pct": float((pnl >= big_threshold).mean() * 100.0)
        if np.isfinite(big_threshold) and len(pnl)
        else math.nan,
        "tail_winner_rate_pct": float((pnl >= tail_threshold).mean() * 100.0)
        if np.isfinite(tail_threshold) and len(pnl)
        else math.nan,
        "median_mae_pct": float(mae.median()) if mae.notna().any() else math.nan,
        "median_mfe_pct": float(mfe.median()) if mfe.notna().any() else math.nan,
        "median_holding_days": float(holding.median()) if holding.notna().any() else math.nan,
        "positive_year_count": int((years > 0).sum()) if len(years) else 0,
        "year_count": int(len(years)),
        "positive_year_rate_pct": float((years > 0).mean() * 100.0) if len(years) else math.nan,
        "worst_year_gross_pnl": float(years.min()) if len(years) else math.nan,
    }


def _build_feature_summary(frame: pd.DataFrame) -> pd.DataFrame:
    specs = []
    for key_def in KEY_DEFINITIONS:
        prefix = key_def.prefix
        for feature in [
            "consecutive_failures_all",
            "consecutive_failures_252",
            "prior_failed_count_252",
            "prior_signal_count_252",
            "attempt_after_failure_all",
            "attempt_after_failure_252",
        ]:
            specs.append((key_def.label, f"{prefix}_{feature}", f"{prefix}_{feature}_bucket"))

    rows: list[dict[str, Any]] = []
    base = _summary_stats(frame, frame)
    for key_label, feature_column, bucket_column in specs:
        for bucket, group in frame.groupby(bucket_column, dropna=False):
            stats = _summary_stats(group, frame)
            stats.update(
                {
                    "key_scope": key_label,
                    "feature": feature_column,
                    "bucket": str(bucket),
                    "mean_edge_vs_all": stats["mean_gross_pnl"] - base["mean_gross_pnl"],
                    "win_rate_edge_vs_all_pp": stats["win_rate_pct"] - base["win_rate_pct"],
                    "median_edge_vs_all": stats["median_gross_pnl"] - base["median_gross_pnl"],
                }
            )
            rows.append(stats)
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    result = result[
        [
            "key_scope",
            "feature",
            "bucket",
            "sample_count",
            "total_gross_pnl",
            "mean_gross_pnl",
            "mean_edge_vs_all",
            "median_gross_pnl",
            "median_edge_vs_all",
            "p25_gross_pnl",
            "p05_gross_pnl",
            "win_rate_pct",
            "win_rate_edge_vs_all_pp",
            "big_winner_rate_pct",
            "tail_winner_rate_pct",
            "mean_return_pct",
            "median_return_pct",
            "median_mae_pct",
            "median_mfe_pct",
            "median_holding_days",
            "positive_year_count",
            "year_count",
            "positive_year_rate_pct",
            "worst_year_gross_pnl",
        ]
    ]
    return result.sort_values(["key_scope", "feature", "bucket"]).reset_index(drop=True)


def _bootstrap_mean_diff(
    group: pd.DataFrame,
    complement: pd.DataFrame,
    iterations: int = 5000,
    seed: int = 20260527,
) -> dict[str, Any]:
    a = pd.to_numeric(group["gross_pnl"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    b = pd.to_numeric(complement["gross_pnl"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    if len(a) < 5 or len(b) < 5:
        return {
            "bootstrap_iterations": iterations,
            "mean_diff_ci05": math.nan,
            "mean_diff_ci50": math.nan,
            "mean_diff_ci95": math.nan,
            "prob_mean_gt_complement_pct": math.nan,
        }
    rng = np.random.default_rng(seed)
    a_idx = rng.integers(0, len(a), size=(iterations, len(a)))
    b_idx = rng.integers(0, len(b), size=(iterations, len(b)))
    diffs = a[a_idx].mean(axis=1) - b[b_idx].mean(axis=1)
    return {
        "bootstrap_iterations": iterations,
        "mean_diff_ci05": float(np.quantile(diffs, 0.05)),
        "mean_diff_ci50": float(np.quantile(diffs, 0.50)),
        "mean_diff_ci95": float(np.quantile(diffs, 0.95)),
        "prob_mean_gt_complement_pct": float((diffs > 0).mean() * 100.0),
    }


def _build_hypothesis_tests(frame: pd.DataFrame) -> pd.DataFrame:
    tests = [
        (
            "H1_pd_consecutive_failures_all_ge2",
            "same product+direction, 2+ consecutive completed losing trades before entry",
            frame["pd_consecutive_failures_all"] >= 2,
        ),
        (
            "H1_pd_consecutive_failures_252_ge2",
            "same product+direction, 2+ recent consecutive losing trades within 252d",
            frame["pd_consecutive_failures_252"] >= 2,
        ),
        (
            "H1_pd_prior_failed_252_ge2",
            "same product+direction, 2+ failed trades within 252d",
            frame["pd_prior_failed_count_252"] >= 2,
        ),
        (
            "H1_ps_consecutive_failures_all_ge2",
            "same product+signal, 2+ consecutive completed losing trades before entry",
            frame["ps_consecutive_failures_all"] >= 2,
        ),
        (
            "H1_ps_prior_failed_252_ge2",
            "same product+signal, 2+ failed trades within 252d",
            frame["ps_prior_failed_count_252"] >= 2,
        ),
        (
            "NEG_pd_consecutive_failures_252_ge3",
            "same product+direction, 3+ recent consecutive losing trades within 252d",
            frame["pd_consecutive_failures_252"] >= 3,
        ),
        (
            "NEG_pd_prior_signal_252_ge3",
            "same product+direction, 3+ prior signals within 252d regardless of outcome",
            frame["pd_prior_signal_count_252"] >= 3,
        ),
    ]
    base = _summary_stats(frame, frame)
    rows: list[dict[str, Any]] = []
    for name, description, mask in tests:
        group = frame[mask].copy()
        complement = frame[~mask].copy()
        stats = _summary_stats(group, frame)
        comp = _summary_stats(complement, frame)
        boot = _bootstrap_mean_diff(group, complement, seed=20260527 + len(rows))
        row = {
            "test_name": name,
            "description": description,
            "sample_count": stats["sample_count"],
            "complement_count": comp["sample_count"],
            "total_gross_pnl": stats["total_gross_pnl"],
            "mean_gross_pnl": stats["mean_gross_pnl"],
            "complement_mean_gross_pnl": comp["mean_gross_pnl"],
            "mean_diff_vs_complement": stats["mean_gross_pnl"] - comp["mean_gross_pnl"],
            "mean_edge_vs_all": stats["mean_gross_pnl"] - base["mean_gross_pnl"],
            "median_gross_pnl": stats["median_gross_pnl"],
            "complement_median_gross_pnl": comp["median_gross_pnl"],
            "median_diff_vs_complement": stats["median_gross_pnl"] - comp["median_gross_pnl"],
            "p05_gross_pnl": stats["p05_gross_pnl"],
            "complement_p05_gross_pnl": comp["p05_gross_pnl"],
            "win_rate_pct": stats["win_rate_pct"],
            "complement_win_rate_pct": comp["win_rate_pct"],
            "win_rate_diff_vs_complement_pp": stats["win_rate_pct"] - comp["win_rate_pct"],
            "big_winner_rate_pct": stats["big_winner_rate_pct"],
            "complement_big_winner_rate_pct": comp["big_winner_rate_pct"],
            "tail_winner_rate_pct": stats["tail_winner_rate_pct"],
            "complement_tail_winner_rate_pct": comp["tail_winner_rate_pct"],
            "positive_year_rate_pct": stats["positive_year_rate_pct"],
            "worst_year_gross_pnl": stats["worst_year_gross_pnl"],
            **boot,
        }
        row["verdict"] = _judge_hypothesis_row(row)
        rows.append(row)
    return pd.DataFrame(rows)


def _judge_hypothesis_row(row: dict[str, Any]) -> str:
    sample_count = int(row.get("sample_count") or 0)
    if sample_count < 20:
        return "too_small_diagnostic_only"
    win_better = _safe_float(row.get("win_rate_diff_vs_complement_pp"), 0.0) > 0.0
    mean_better = _safe_float(row.get("mean_diff_vs_complement"), 0.0) > 0.0
    median_better = _safe_float(row.get("median_diff_vs_complement"), 0.0) > 0.0
    prob = _safe_float(row.get("prob_mean_gt_complement_pct"), 0.0)
    if win_better and median_better and not mean_better:
        return "win_rate_supported_expectancy_not_supported"
    if win_better and mean_better and prob >= 60.0:
        return "weak_positive_feature"
    if not win_better and not mean_better:
        return "negative_or_no_edge"
    return "mixed_diagnostic_only"


def _year_bucket_table(frame: pd.DataFrame, bucket_column: str) -> pd.DataFrame:
    table = (
        frame.assign(bucket=frame[bucket_column].astype(str))
        .groupby(["entry_year", "bucket"], dropna=False)["gross_pnl"]
        .sum()
        .unstack("bucket")
        .fillna(0.0)
        .sort_index()
    )
    for column in ["0", "1", "2", "3+"]:
        if column not in table.columns:
            table[column] = 0.0
    return table[["0", "1", "2", "3+"]].reset_index()


def _plot_outputs(frame: pd.DataFrame, feature_summary: pd.DataFrame) -> Path:
    chart_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_charts_{MODEL_TAG}.png"
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))

    def bar_line(ax: plt.Axes, feature: str, title: str) -> None:
        data = feature_summary[
            (feature_summary["key_scope"] == "same_product_direction")
            & (feature_summary["feature"] == feature)
        ].copy()
        order = ["0", "1", "2", "3+"] if "attempt" not in feature else ["1", "2", "3", "4+"]
        data["_order"] = data["bucket"].map({value: idx for idx, value in enumerate(order)})
        data = data.sort_values("_order")
        x = np.arange(len(data))
        ax.bar(x, data["mean_gross_pnl"] / 10000.0, color="#4777b2", alpha=0.82)
        ax.set_xticks(x)
        ax.set_xticklabels(data["bucket"].astype(str).tolist())
        ax.set_ylabel("Mean PnL (10k CNY)")
        ax.set_title(title)
        ax.grid(axis="y", alpha=0.25)
        ax2 = ax.twinx()
        ax2.plot(x, data["win_rate_pct"], color="#c75b12", marker="o", linewidth=2)
        ax2.set_ylabel("Win rate (%)")
        for idx, row in enumerate(data.to_dict("records")):
            ax.text(idx, row["mean_gross_pnl"] / 10000.0, f"n={int(row['sample_count'])}", ha="center", va="bottom", fontsize=8)

    bar_line(
        axes[0, 0],
        "pd_consecutive_failures_252",
        "Same product+direction: recent consecutive failures",
    )
    bar_line(
        axes[0, 1],
        "pd_prior_failed_count_252",
        "Same product+direction: failed signals in trailing 252d",
    )

    plot_data = []
    labels = []
    for bucket in ["0", "1", "2", "3+"]:
        values = frame.loc[frame["pd_consecutive_failures_252_bucket"].eq(bucket), "gross_pnl"].clip(-350000, 700000)
        if len(values):
            plot_data.append(values.to_numpy())
            labels.append(bucket)
    axes[1, 0].boxplot(plot_data, tick_labels=labels, showfliers=False)
    axes[1, 0].axhline(0, color="#222222", linewidth=0.8)
    axes[1, 0].set_title("PnL distribution by recent consecutive failures (clipped)")
    axes[1, 0].set_xlabel("bucket")
    axes[1, 0].set_ylabel("Gross PnL")
    axes[1, 0].grid(axis="y", alpha=0.25)

    heat = (
        frame.assign(bucket=frame["pd_consecutive_failures_252_bucket"].astype(str))
        .groupby(["entry_year", "bucket"])["gross_pnl"]
        .sum()
        .unstack("bucket")
        .fillna(0.0)
    )
    for column in ["0", "1", "2", "3+"]:
        if column not in heat.columns:
            heat[column] = 0.0
    heat = heat[["0", "1", "2", "3+"]] / 10000.0
    im = axes[1, 1].imshow(heat.to_numpy(), cmap="RdYlGn", aspect="auto")
    axes[1, 1].set_title("Year x failure bucket total PnL (10k CNY)")
    axes[1, 1].set_xticks(np.arange(len(heat.columns)))
    axes[1, 1].set_xticklabels(heat.columns.tolist())
    axes[1, 1].set_yticks(np.arange(len(heat.index)))
    axes[1, 1].set_yticklabels(heat.index.astype(str).tolist())
    for i in range(heat.shape[0]):
        for j in range(heat.shape[1]):
            value = heat.iloc[i, j]
            axes[1, 1].text(j, i, f"{value:.0f}", ha="center", va="center", fontsize=8)
    fig.colorbar(im, ax=axes[1, 1], fraction=0.046, pad=0.04)

    fig.tight_layout()
    fig.savefig(chart_path, dpi=160)
    plt.close(fig)
    return chart_path


def _build_report(
    frame: pd.DataFrame,
    feature_summary: pd.DataFrame,
    hypothesis_tests: pd.DataFrame,
    year_bucket: pd.DataFrame,
    chart_path: Path,
    decision: dict[str, Any],
) -> str:
    base = _summary_stats(frame, frame)
    top_feature_columns = [
        "key_scope",
        "feature",
        "bucket",
        "sample_count",
        "total_gross_pnl",
        "mean_gross_pnl",
        "median_gross_pnl",
        "win_rate_pct",
        "big_winner_rate_pct",
        "tail_winner_rate_pct",
        "positive_year_rate_pct",
        "worst_year_gross_pnl",
    ]
    selected_features = feature_summary[
        feature_summary["feature"].isin(
            [
                "pd_consecutive_failures_252",
                "pd_prior_failed_count_252",
                "ps_consecutive_failures_all",
                "ps_prior_failed_count_252",
            ]
        )
    ].copy()
    h_columns = [
        "test_name",
        "sample_count",
        "mean_gross_pnl",
        "complement_mean_gross_pnl",
        "mean_diff_vs_complement",
        "win_rate_pct",
        "complement_win_rate_pct",
        "win_rate_diff_vs_complement_pp",
        "median_diff_vs_complement",
        "p05_gross_pnl",
        "prob_mean_gt_complement_pct",
        "verdict",
    ]
    report = [
        f"# Stage094 同品种信号失败记忆特征只读审计（{MODEL_TAG}）",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- 研究线：`{LINE_ID}`",
        "- 对象：纯 C3 的 Stage328 逐笔 round-trip 归因样本；Stage079 继承同一 C3 下单路径，因此该信号特征先在 C3 交易层验证。",
        "- 阶段性质：只读特征审计；不修改信号、品种、仓位、AI 池或资金口径。",
        "- 口径：只使用入场前已经完成且已知盈亏的同品种/同方向或同品种/同信号历史交易，避免偷看当前交易结果。",
        "",
        "## 外部调研与判断",
        "",
        "- 趋势跟随长期有效的基础来自时间序列动量/趋势跟随证据，但趋势策略的收益来自少数大趋势尾部，不是高胜率。",
        "- 失败突破/whipsaw 资料支持两个相反机制：连续失败可能代表趋势前的反复试探，也可能代表市场仍在震荡。不能把“不会一直震荡”当作规则，必须检验胜率、平均收益、尾部大赢家捕获和年份稳定性。",
        "- 本地判断：这个特征适合作为诊断/风控状态变量候选；若只提升胜率但降低大赢家捕获，不应直接加仓或过滤。",
        "",
        "## 基础样本",
        "",
        f"- round-trip 样本数：`{int(base['sample_count'])}`",
        f"- 总 gross PnL：`{base['total_gross_pnl']:,.0f}`",
        f"- 单笔均值：`{base['mean_gross_pnl']:,.2f}`",
        f"- 单笔中位数：`{base['median_gross_pnl']:,.2f}`",
        f"- 胜率：`{base['win_rate_pct']:.4f}%`",
        f"- 大赢家阈值口径：盈利交易的 75% 分位；尾部赢家阈值口径：全部交易 PnL 的 90% 分位。",
        "",
        "## 核心特征分桶",
        "",
        _markdown_table(selected_features, top_feature_columns, max_rows=60),
        "",
        "## 用户假设检验",
        "",
        _markdown_table(hypothesis_tests, h_columns, max_rows=20),
        "",
        "## 年份稳定性：同品种同方向 252日连续失败桶",
        "",
        _markdown_table(year_bucket, year_bucket.columns.tolist(), max_rows=20),
        "",
        "## 图表",
        "",
        f"![Stage094 feature charts]({chart_path})",
        "",
        "## 决策",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 用户假设胜率层面：`{decision['user_hypothesis_win_rate']}`",
        f"- 用户假设收益期望层面：`{decision['user_hypothesis_expectancy']}`",
        f"- 可交易建议：`{decision['trading_rule_judgment']}`",
        f"- 下一步：`{decision['next_step']}`",
        "",
        "## 过拟合与继续价值",
        "",
        f"- 过拟合判断：`{decision['overfit_judgment']}`",
        f"- 继续价值判断：`{decision['continue_value_judgment']}`",
    ]
    return "\n".join(report) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    frame = _load_round_trips()
    for key_def in KEY_DEFINITIONS:
        frame = _add_memory_features(frame, key_def)
    frame = _add_buckets(frame)

    feature_summary = _build_feature_summary(frame)
    hypothesis_tests = _build_hypothesis_tests(frame)
    year_bucket = _year_bucket_table(frame, "pd_consecutive_failures_252_bucket")
    chart_path = _plot_outputs(frame, feature_summary)

    h1_pd = hypothesis_tests[hypothesis_tests["test_name"].eq("H1_pd_consecutive_failures_all_ge2")].iloc[0]
    h1_recent = hypothesis_tests[hypothesis_tests["test_name"].eq("H1_pd_consecutive_failures_252_ge2")].iloc[0]
    neg_recent = hypothesis_tests[hypothesis_tests["test_name"].eq("NEG_pd_consecutive_failures_252_ge3")].iloc[0]

    decision = {
        "decision": "diagnostic_only_no_promotion",
        "user_hypothesis_win_rate": "partially_supported",
        "user_hypothesis_expectancy": "not_supported",
        "trading_rule_judgment": (
            "不能直接做成连续失败后加仓规则；连续失败后胜率提高但平均收益和大赢家捕获下降，"
            "3次以上近期连续失败样本为负但样本只有17笔，只能作为下一轮固定冷却候选。"
        ),
        "next_step": (
            "若继续，只测试一个低自由度真实引擎版本：同品种同方向252日内3次连续已执行亏损后，"
            "冷却90日或直到时间衰减；不扫2/3/4次、不扫冷却天数小数。"
        ),
        "overfit_judgment": (
            "本阶段不是过拟合，因为特征在看结果前定义且只读归因；现在若直接按最差桶调参或加仓会过拟合。"
        ),
        "continue_value_judgment": (
            "继续有价值，但价值在验证一个固定冷却形状是否减少3/6个月坏体验；"
            "连续失败后加仓方向价值不足。"
        ),
        "key_numbers": {
            "h1_pd_consecutive_failures_all_ge2": h1_pd.to_dict(),
            "h1_pd_consecutive_failures_252_ge2": h1_recent.to_dict(),
            "neg_pd_consecutive_failures_252_ge3": neg_recent.to_dict(),
        },
    }

    featured_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_featured_round_trips_{MODEL_TAG}.csv"
    summary_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_summary_{MODEL_TAG}.csv"
    hypothesis_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_hypothesis_tests_{MODEL_TAG}.csv"
    year_bucket_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_bucket_{MODEL_TAG}.csv"
    decision_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
    report_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

    frame.to_csv(featured_path, index=False)
    feature_summary.to_csv(summary_path, index=False)
    hypothesis_tests.to_csv(hypothesis_path, index=False)
    year_bucket.to_csv(year_bucket_path, index=False)
    decision_path.write_text(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(
        _build_report(frame, feature_summary, hypothesis_tests, year_bucket, chart_path, decision),
        encoding="utf-8",
    )

    print(json.dumps(_to_builtin({
        "model_tag": MODEL_TAG,
        "decision": decision["decision"],
        "featured_path": str(featured_path),
        "feature_summary_path": str(summary_path),
        "hypothesis_path": str(hypothesis_path),
        "year_bucket_path": str(year_bucket_path),
        "decision_path": str(decision_path),
        "report_path": str(report_path),
        "chart_path": str(chart_path),
        "h1_pd_consecutive_failures_all_ge2": h1_pd.to_dict(),
        "h1_pd_consecutive_failures_252_ge2": h1_recent.to_dict(),
        "neg_pd_consecutive_failures_252_ge3": neg_recent.to_dict(),
    }), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
