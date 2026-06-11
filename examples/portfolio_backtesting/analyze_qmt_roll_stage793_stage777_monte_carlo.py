from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage793_stage777_monte_carlo_v1"
OUTPUT_PREFIX = "qmt_roll_stage793_stage777_monte_carlo"

STAGE777_CURVES_PATH = OUTPUT_DIR / "qmt_roll_stage777_am41_oi08_monthly_curves_stage777_am41_oi08_monthly_v1.csv"
STAGE777_SUMMARY_PATH = OUTPUT_DIR / "qmt_roll_stage777_am41_oi08_monthly_summary_stage777_am41_oi08_monthly_v1.csv"
STAGE372_CURVES_PATH = OUTPUT_DIR / "qmt_roll_stage744_official_monthly_start_audit_curves_stage744_official_monthly_start_audit_v1.csv"
STAGE372_SUMMARY_PATH = OUTPUT_DIR / "qmt_roll_stage744_official_monthly_start_audit_summary_stage744_official_monthly_start_audit_v1.csv"

MC_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
STRESS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bad_block_stress_{MODEL_TAG}.csv"
SOURCE_PATH_STATS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_path_stats_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DD_PROB_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_dd_probability_{MODEL_TAG}.png"
FAN_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_fan_chart_{MODEL_TAG}.png"
STRESS_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bad_block_stress_{MODEL_TAG}.png"

N_SIMS = 10_000
PLOT_N_SIMS = 2_000
RANDOM_SEED = 79320260610
CHUNK_SIZE = 1_000
BLOCK_LENGTHS = (1, 20, 60, 120)
COMMON_END = pd.Timestamp("2026-04-30")


def _json_safe(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (pd.Timestamp,)):
        return value.strftime("%Y-%m-%d")
    if pd.isna(value):
        return None
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if max_rows is not None:
        frame = frame.head(max_rows)
    if frame.empty:
        return "(empty)"
    return frame.to_markdown(index=False)


def _load_curves(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    data = pd.read_csv(path, parse_dates=["date"])
    if "start_month" not in data.columns and "requested_start_month" in data.columns:
        data["start_month"] = data["requested_start_month"]
    data["start_month"] = data["start_month"].astype(str)
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    data = data.dropna(subset=["date"]).sort_values(["start_month", "date"]).reset_index(drop=True)
    if "rebased_nav" not in data.columns:
        data["rebased_nav"] = pd.to_numeric(data["rebased_equity"], errors="coerce") / float(
            pd.to_numeric(data["rebased_equity"], errors="coerce").dropna().iloc[0]
        )
    return data


def _path_frame(
    curves: pd.DataFrame,
    *,
    start_month: str,
    end_date: pd.Timestamp | None,
) -> pd.DataFrame:
    frame = curves[curves["start_month"].eq(start_month)].copy()
    if frame.empty:
        raise RuntimeError(f"missing start_month={start_month}")
    if end_date is not None:
        frame = frame[frame["date"].le(end_date)].copy()
    frame = frame.sort_values("date").reset_index(drop=True)
    frame["nav_for_mc"] = pd.to_numeric(frame["rebased_nav"], errors="coerce").ffill()
    frame = frame.dropna(subset=["nav_for_mc"]).reset_index(drop=True)
    if len(frame) < 100:
        raise RuntimeError(f"too few daily rows for {start_month}: {len(frame)}")
    return frame


def _returns_from_path(frame: pd.DataFrame) -> np.ndarray:
    returns = frame["nav_for_mc"].pct_change().replace([np.inf, -np.inf], np.nan).dropna().to_numpy(dtype=float)
    returns = returns[np.isfinite(returns)]
    if len(returns) < 50:
        raise RuntimeError("too few returns")
    return returns


def _path_stats(frame: pd.DataFrame, *, scenario: str, family: str) -> dict[str, Any]:
    nav = frame["nav_for_mc"].to_numpy(dtype=float)
    running_peak = np.maximum.accumulate(nav)
    dd = nav / np.where(running_peak == 0, np.nan, running_peak) - 1.0
    trough_idx = int(np.nanargmin(dd))
    peak_idx = int(np.nanargmax(nav[: trough_idx + 1]))
    returns = _returns_from_path(frame)
    sharpe = np.nan
    if np.nanstd(returns, ddof=1) > 0:
        sharpe = float(np.nanmean(returns) / np.nanstd(returns, ddof=1) * np.sqrt(252))
    return {
        "scenario": scenario,
        "family": family,
        "start_date": frame["date"].iloc[0].date().isoformat(),
        "end_date": frame["date"].iloc[-1].date().isoformat(),
        "days": int(len(frame)),
        "return_count": int(len(returns)),
        "historical_end_nav": float(nav[-1]),
        "historical_total_return_pct": float((nav[-1] - 1.0) * 100.0),
        "historical_max_dd_pct": float(np.nanmin(dd) * 100.0),
        "historical_min_nav": float(np.nanmin(nav)),
        "historical_sharpe": sharpe,
        "worst_peak_date": frame["date"].iloc[peak_idx].date().isoformat(),
        "worst_trough_date": frame["date"].iloc[trough_idx].date().isoformat(),
        "worst_block_days": int(trough_idx - peak_idx + 1),
    }


def _simulate_bootstrap(
    returns: np.ndarray,
    *,
    n_sims: int,
    block_len: int,
    rng: np.random.Generator,
    collect_paths: bool = False,
) -> tuple[pd.DataFrame, np.ndarray | None]:
    n = int(len(returns))
    chunks: list[pd.DataFrame] = []
    collected: list[np.ndarray] = []
    done = 0
    offsets = np.arange(block_len)
    while done < n_sims:
        chunk = min(CHUNK_SIZE, n_sims - done)
        if block_len <= 1:
            idx = rng.integers(0, n, size=(chunk, n), endpoint=False)
        else:
            n_blocks = int(np.ceil(n / block_len))
            starts = rng.integers(0, n, size=(chunk, n_blocks), endpoint=False)
            idx = (starts[:, :, None] + offsets[None, None, :]) % n
            idx = idx.reshape(chunk, n_blocks * block_len)[:, :n]
        sampled = returns[idx]
        nav = np.cumprod(1.0 + sampled, axis=1)
        running_peak = np.maximum.accumulate(nav, axis=1)
        dd = nav / np.where(running_peak == 0, np.nan, running_peak) - 1.0
        end_nav = nav[:, -1]
        max_dd = np.nanmin(dd, axis=1)
        min_nav = np.nanmin(nav, axis=1)
        days_below_initial = np.sum(nav < 1.0, axis=1)
        chunks.append(
            pd.DataFrame(
                {
                    "end_nav": end_nav,
                    "total_return_pct": (end_nav - 1.0) * 100.0,
                    "max_dd_pct": max_dd * 100.0,
                    "min_nav": min_nav,
                    "days_below_initial": days_below_initial,
                }
            )
        )
        if collect_paths:
            collected.append(nav.copy())
        done += chunk
    sims = pd.concat(chunks, ignore_index=True)
    paths = np.vstack(collected) if collected else None
    return sims, paths


def _summarize_sims(
    sims: pd.DataFrame,
    *,
    scenario: str,
    family: str,
    method: str,
    block_len: int,
    source_days: int,
    source_return_count: int,
) -> dict[str, Any]:
    end = sims["end_nav"].astype(float)
    ret = sims["total_return_pct"].astype(float)
    dd = sims["max_dd_pct"].astype(float)
    min_nav = sims["min_nav"].astype(float)
    days_below = sims["days_below_initial"].astype(float)
    return {
        "scenario": scenario,
        "family": family,
        "method": method,
        "block_len": int(block_len),
        "n_sims": int(len(sims)),
        "source_days": int(source_days),
        "source_return_count": int(source_return_count),
        "end_nav_p01": float(end.quantile(0.01)),
        "end_nav_p05": float(end.quantile(0.05)),
        "end_nav_p10": float(end.quantile(0.10)),
        "end_nav_p50": float(end.quantile(0.50)),
        "end_nav_p90": float(end.quantile(0.90)),
        "end_nav_p95": float(end.quantile(0.95)),
        "return_pct_p01": float(ret.quantile(0.01)),
        "return_pct_p05": float(ret.quantile(0.05)),
        "return_pct_p10": float(ret.quantile(0.10)),
        "return_pct_p50": float(ret.quantile(0.50)),
        "return_pct_p90": float(ret.quantile(0.90)),
        "return_pct_p95": float(ret.quantile(0.95)),
        "max_dd_pct_p01": float(dd.quantile(0.01)),
        "max_dd_pct_p05": float(dd.quantile(0.05)),
        "max_dd_pct_p10": float(dd.quantile(0.10)),
        "max_dd_pct_p50": float(dd.quantile(0.50)),
        "max_dd_pct_p90": float(dd.quantile(0.90)),
        "prob_end_below_initial_pct": float((end < 1.0).mean() * 100.0),
        "prob_maxdd_gt_40_pct": float((dd <= -40.0).mean() * 100.0),
        "prob_maxdd_gt_50_pct": float((dd <= -50.0).mean() * 100.0),
        "prob_maxdd_gt_60_pct": float((dd <= -60.0).mean() * 100.0),
        "prob_min_nav_lt_0_50_pct": float((min_nav < 0.50).mean() * 100.0),
        "prob_min_nav_lt_0_30_pct": float((min_nav < 0.30).mean() * 100.0),
        "days_below_initial_p50": float(days_below.quantile(0.50)),
        "days_below_initial_p90": float(days_below.quantile(0.90)),
        "days_below_initial_p95": float(days_below.quantile(0.95)),
    }


def _worst_block_returns(frame: pd.DataFrame) -> np.ndarray:
    nav = frame["nav_for_mc"].to_numpy(dtype=float)
    running_peak = np.maximum.accumulate(nav)
    dd = nav / np.where(running_peak == 0, np.nan, running_peak) - 1.0
    trough_idx = int(np.nanargmin(dd))
    peak_idx = int(np.nanargmax(nav[: trough_idx + 1]))
    returns = _returns_from_path(frame)
    start_ret_idx = max(0, peak_idx)
    end_ret_idx = min(len(returns), trough_idx)
    block = returns[start_ret_idx:end_ret_idx].copy()
    if len(block) < 5:
        block = returns.copy()
    return block


def _metrics_from_returns(returns: np.ndarray) -> dict[str, float]:
    nav = np.cumprod(1.0 + returns)
    running_peak = np.maximum.accumulate(nav)
    dd = nav / np.where(running_peak == 0, np.nan, running_peak) - 1.0
    first_recovery_idx = np.where(nav >= 1.0)[0]
    if len(first_recovery_idx):
        first_recovery_days = float(first_recovery_idx[0] + 1)
    else:
        first_recovery_days = np.nan
    return {
        "end_nav": float(nav[-1]),
        "total_return_pct": float((nav[-1] - 1.0) * 100.0),
        "max_dd_pct": float(np.nanmin(dd) * 100.0),
        "min_nav": float(np.nanmin(nav)),
        "days_below_initial": float(np.sum(nav < 1.0)),
        "first_recovery_days": first_recovery_days,
    }


def _same_length_frontload(base_returns: np.ndarray, block: np.ndarray, *, repeat: int = 1, scale: float = 1.0) -> np.ndarray:
    stress = np.tile(block, repeat).astype(float) * float(scale)
    stress = np.clip(stress, -0.95, 10.0)
    n = len(base_returns)
    if len(stress) >= n:
        return stress[:n]
    tail = base_returns[: n - len(stress)]
    return np.concatenate([stress, tail])


def _bad_block_stress(source_frames: dict[str, tuple[str, pd.DataFrame]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for scenario, (family, frame) in source_frames.items():
        base_returns = _returns_from_path(frame)
        worst_block = _worst_block_returns(frame)
        variants = {
            "historical_order": base_returns,
            "frontload_worst_block": _same_length_frontload(base_returns, worst_block, repeat=1, scale=1.0),
            "frontload_worst_block_x2": _same_length_frontload(base_returns, worst_block, repeat=2, scale=1.0),
            "frontload_worst_block_scaled_1_25": _same_length_frontload(base_returns, worst_block, repeat=1, scale=1.25),
            "frontload_worst_block_scaled_1_50": _same_length_frontload(base_returns, worst_block, repeat=1, scale=1.50),
        }
        for stress_name, stress_returns in variants.items():
            metrics = _metrics_from_returns(stress_returns)
            metrics.update(
                {
                    "scenario": scenario,
                    "family": family,
                    "stress_name": stress_name,
                    "source_return_count": int(len(base_returns)),
                    "worst_block_return_count": int(len(worst_block)),
                    "worst_block_return_pct": float((np.prod(1.0 + worst_block) - 1.0) * 100.0),
                }
            )
            rows.append(metrics)
    return pd.DataFrame(rows)


def _plot_dd_probability(summary: pd.DataFrame) -> None:
    view = summary[
        summary["method"].isin(["iid", "block_20", "block_60", "block_120"])
        & summary["scenario"].isin(["candidate_2020_01_common", "official_2020_01_common", "candidate_2018_01_full"])
    ].copy()
    view["label"] = view["scenario"] + " / " + view["method"]
    fig, ax = plt.subplots(figsize=(18, 8))
    x = np.arange(len(view))
    ax.bar(x, view["prob_maxdd_gt_50_pct"], color="#d95f02", alpha=0.78, label="P(maxDD > 50%)")
    ax.plot(x, view["prob_maxdd_gt_40_pct"], color="#1b9e77", marker="o", linewidth=2.0, label="P(maxDD > 40%)")
    ax.plot(x, view["prob_maxdd_gt_60_pct"], color="#7570b3", marker="o", linewidth=2.0, label="P(maxDD > 60%)")
    ax.set_xticks(x)
    ax.set_xticklabels(view["label"], rotation=35, ha="right", fontsize=9)
    ax.set_ylabel("Probability (%)")
    ax.set_title("Stage793 Monte Carlo drawdown breach probabilities")
    ax.grid(axis="y", alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(DD_PROB_CHART_PATH, dpi=170)
    plt.close(fig)


def _plot_fan(
    fan_paths: dict[str, np.ndarray],
    source_frames: dict[str, tuple[str, pd.DataFrame]],
) -> None:
    fig, axes = plt.subplots(1, len(fan_paths), figsize=(22, 7), sharey=False)
    if len(fan_paths) == 1:
        axes = [axes]
    for ax, (scenario_method, paths) in zip(axes, fan_paths.items(), strict=False):
        scenario, method = scenario_method.split("|", 1)
        frame = source_frames[scenario][1]
        dates = frame["date"].iloc[1 : paths.shape[1] + 1].reset_index(drop=True)
        pct = np.percentile(paths, [5, 25, 50, 75, 95], axis=0)
        ax.fill_between(dates, pct[0], pct[4], color="#9ecae1", alpha=0.35, label="p5-p95")
        ax.fill_between(dates, pct[1], pct[3], color="#3182bd", alpha=0.22, label="p25-p75")
        ax.plot(dates, pct[2], color="#08519c", linewidth=1.8, label="p50")
        ax.axhline(1.0, color="#6b7280", linestyle="--", linewidth=1.1)
        ax.set_title(f"{scenario}\n{method}, {PLOT_N_SIMS} paths")
        ax.set_ylabel("NAV")
        ax.grid(True, alpha=0.25)
        ax.legend(fontsize=9)
    fig.suptitle("Stage793 Monte Carlo NAV fan charts", fontsize=15)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(FAN_CHART_PATH, dpi=170)
    plt.close(fig)


def _plot_stress(stress: pd.DataFrame) -> None:
    view = stress[stress["stress_name"].ne("historical_order")].copy()
    view["label"] = view["scenario"] + " / " + view["stress_name"]
    fig, axes = plt.subplots(2, 1, figsize=(18, 10), sharex=True)
    x = np.arange(len(view))
    axes[0].bar(x, view["total_return_pct"], color="#2ca25f", alpha=0.78)
    axes[0].axhline(0.0, color="#6b7280", linestyle="--", linewidth=1.0)
    axes[0].set_ylabel("Total return (%)")
    axes[0].set_title("Bad-block front-load stress: ending return")
    axes[0].grid(axis="y", alpha=0.25)
    axes[1].bar(x, view["max_dd_pct"], color="#de2d26", alpha=0.78)
    axes[1].axhline(-50.0, color="#111827", linestyle="--", linewidth=1.0, label="-50%")
    axes[1].axhline(-60.0, color="#111827", linestyle=":", linewidth=1.0, label="-60%")
    axes[1].set_ylabel("Max DD (%)")
    axes[1].set_title("Bad-block front-load stress: max drawdown")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(view["label"], rotation=35, ha="right", fontsize=8)
    axes[1].grid(axis="y", alpha=0.25)
    axes[1].legend()
    fig.tight_layout()
    fig.savefig(STRESS_CHART_PATH, dpi=170)
    plt.close(fig)


def _write_report(source_stats: pd.DataFrame, mc: pd.DataFrame, stress: pd.DataFrame) -> None:
    key_cols = [
        "scenario",
        "method",
        "return_pct_p05",
        "return_pct_p50",
        "max_dd_pct_p05",
        "max_dd_pct_p50",
        "prob_end_below_initial_pct",
        "prob_maxdd_gt_40_pct",
        "prob_maxdd_gt_50_pct",
        "prob_maxdd_gt_60_pct",
        "prob_min_nav_lt_0_50_pct",
    ]
    key = mc[
        mc["scenario"].isin(["candidate_2018_01_full", "candidate_2020_01_common", "official_2020_01_common"])
        & mc["method"].isin(["block_60", "block_120"])
    ][key_cols].copy()
    for col in key.columns:
        if col not in {"scenario", "method"}:
            key[col] = key[col].map(lambda x: round(float(x), 4))

    stress_view = stress[
        stress["scenario"].isin(["candidate_2018_01_full", "candidate_2020_01_common", "official_2020_01_common"])
        & stress["stress_name"].isin(
            [
                "frontload_worst_block",
                "frontload_worst_block_x2",
                "frontload_worst_block_scaled_1_50",
            ]
        )
    ].copy()
    for col in ["total_return_pct", "max_dd_pct", "min_nav", "days_below_initial", "worst_block_return_pct"]:
        stress_view[col] = stress_view[col].map(lambda x: round(float(x), 4))

    text = "\n".join(
        [
            "# Stage793 Stage777 Official Candidate Monte Carlo",
            "",
            "本阶段不改策略、不调参数、不切换实盘默认，只对 Stage792 官方候选做路径风险压力测试。",
            "",
            "主口径：日收益 bootstrap。`iid` 打乱单日收益，`block_20/60/120` 使用 circular block bootstrap 保留趋势策略的连续盈亏结构。每个场景每个方法 `10,000` 条路径。",
            "",
            "候选：`official_candidate_stage777_50w_am41_oi08_old_ai_v1`。对照：当前官方 Stage372 20万逐月启动审计输出。",
            "",
            "## Source Path Stats",
            "",
            _md_table(source_stats),
            "",
            "## Key Monte Carlo Results",
            "",
            _md_table(key),
            "",
            "## Bad Block Stress",
            "",
            _md_table(
                stress_view[
                    [
                        "scenario",
                        "stress_name",
                        "total_return_pct",
                        "max_dd_pct",
                        "min_nav",
                        "days_below_initial",
                        "worst_block_return_pct",
                    ]
                ]
            ),
            "",
            "## Outputs",
            "",
            f"- MC summary: `{MC_SUMMARY_PATH}`",
            f"- Bad-block stress: `{STRESS_PATH}`",
            f"- DD probability chart: `{DD_PROB_CHART_PATH}`",
            f"- Fan chart: `{FAN_CHART_PATH}`",
            f"- Stress chart: `{STRESS_CHART_PATH}`",
            "",
            "## Decision",
            "",
            "Stage777 候选保留了明显右尾，但 Monte Carlo 明确显示它不是低回撤部署口径。若接受 `50%+` 回撤概率，它可以保留为高风险官方候选；若目标是接近 Stage372 的防守实盘体验，本阶段不支持直接切换 live default。",
        ]
    )
    REPORT_PATH.write_text(text, encoding="utf-8")


def main() -> None:
    stage777_curves = _load_curves(STAGE777_CURVES_PATH)
    stage372_curves = _load_curves(STAGE372_CURVES_PATH)
    source_frames: dict[str, tuple[str, pd.DataFrame]] = {
        "candidate_2018_01_full": ("stage777_candidate", _path_frame(stage777_curves, start_month="2018-01", end_date=None)),
        "candidate_2020_01_common": (
            "stage777_candidate",
            _path_frame(stage777_curves, start_month="2020-01", end_date=COMMON_END),
        ),
        "candidate_2022_01_common": (
            "stage777_candidate",
            _path_frame(stage777_curves, start_month="2022-01", end_date=COMMON_END),
        ),
        "official_2020_01_common": (
            "stage372_official",
            _path_frame(stage372_curves, start_month="2020-01", end_date=COMMON_END),
        ),
        "official_2022_01_common": (
            "stage372_official",
            _path_frame(stage372_curves, start_month="2022-01", end_date=COMMON_END),
        ),
    }

    source_stats = pd.DataFrame(
        [_path_stats(frame, scenario=scenario, family=family) for scenario, (family, frame) in source_frames.items()]
    )
    source_stats.to_csv(SOURCE_PATH_STATS_PATH, index=False, encoding="utf-8-sig")

    rng = np.random.default_rng(RANDOM_SEED)
    rows: list[dict[str, Any]] = []
    fan_paths: dict[str, np.ndarray] = {}
    fan_targets = {
        ("candidate_2018_01_full", "block_60"),
        ("candidate_2020_01_common", "block_60"),
        ("official_2020_01_common", "block_60"),
    }
    for scenario, (family, frame) in source_frames.items():
        returns = _returns_from_path(frame)
        for block_len in BLOCK_LENGTHS:
            method = "iid" if block_len <= 1 else f"block_{block_len}"
            print(f"[stage793] {scenario} {method} sims={N_SIMS}", flush=True)
            sims, _ = _simulate_bootstrap(
                returns,
                n_sims=N_SIMS,
                block_len=block_len,
                rng=rng,
                collect_paths=False,
            )
            rows.append(
                _summarize_sims(
                    sims,
                    scenario=scenario,
                    family=family,
                    method=method,
                    block_len=block_len,
                    source_days=len(frame),
                    source_return_count=len(returns),
                )
            )
            if (scenario, method) in fan_targets:
                plot_rng = np.random.default_rng(RANDOM_SEED + len(fan_paths) + 100)
                _, paths = _simulate_bootstrap(
                    returns,
                    n_sims=PLOT_N_SIMS,
                    block_len=block_len,
                    rng=plot_rng,
                    collect_paths=True,
                )
                if paths is not None:
                    fan_paths[f"{scenario}|{method}"] = paths
    mc = pd.DataFrame(rows)
    mc.to_csv(MC_SUMMARY_PATH, index=False, encoding="utf-8-sig")

    stress = _bad_block_stress(source_frames)
    stress.to_csv(STRESS_PATH, index=False, encoding="utf-8-sig")

    _plot_dd_probability(mc)
    _plot_fan(fan_paths, source_frames)
    _plot_stress(stress)
    _write_report(source_stats, mc, stress)

    decision = {
        "model_tag": MODEL_TAG,
        "candidate": "official_candidate_stage777_50w_am41_oi08_old_ai_v1",
        "n_sims": N_SIMS,
        "methods": ["iid", "block_20", "block_60", "block_120"],
        "outputs": {
            "source_path_stats": str(SOURCE_PATH_STATS_PATH),
            "mc_summary": str(MC_SUMMARY_PATH),
            "bad_block_stress": str(STRESS_PATH),
            "report": str(REPORT_PATH),
            "dd_probability_chart": str(DD_PROB_CHART_PATH),
            "fan_chart": str(FAN_CHART_PATH),
            "stress_chart": str(STRESS_CHART_PATH),
        },
        "judgment": (
            "Stage777 remains a high-return official candidate, but Monte Carlo should be read as a drawdown "
            "survivability test; direct live default promotion requires explicit acceptance of high path risk."
        ),
    }
    DECISION_PATH.write_text(json.dumps(decision, ensure_ascii=False, indent=2, default=_json_safe), encoding="utf-8")
    print(json.dumps(decision, ensure_ascii=False, indent=2, default=_json_safe), flush=True)


if __name__ == "__main__":
    main()
