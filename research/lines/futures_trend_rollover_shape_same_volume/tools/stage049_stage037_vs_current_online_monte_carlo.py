from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
LINE_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

import stage047_stage037_vs_current_online_fullperiod as s47  # noqa: E402


SOURCE_DIR = LINE_DIR / "artifacts" / "stage047_stage037_vs_live"
STAGE048_DIR = LINE_DIR / "artifacts" / "stage048_stage037_vs_live_multicycle"
OUTPUT_DIR = LINE_DIR / "artifacts" / "stage049_stage037_vs_live_monte_carlo"
SOURCE_CURVE = SOURCE_DIR / s47.CURVE_NAME
SOURCE_SUMMARY = SOURCE_DIR / s47.SUMMARY_NAME
SOURCE_DECISION = SOURCE_DIR / s47.DECISION_NAME
STAGE048_DECISION = STAGE048_DIR / "stage048_decision.json"

N_SIMULATIONS = 10_000
PLOT_SIMULATIONS = 2_000
CHUNK_SIZE = 500
BLOCK_LENGTHS = (1, 20, 60, 120)
MAIN_BLOCK_LENGTHS = (60, 120)
RANDOM_SEED = 49_037_20260829
INITIAL_CAPITAL = 150_000.0
STAGE047_RESULT_COMMIT = "a50d83f6d6e45577696cc0181ce70aff50747be1"
STAGE048_RESULT_COMMIT = "f57678fe7671affe15d3a9fdd67266080e8b5957"
STAGE048_DECISION_SHA256 = "801237f46a16f759c5a1bf242eec8406479e29bf0f4aeb9cc7a142c7c4945aaa"
RUNNER_CONTRACT_VERSION = 1

SIMULATION_NAME = "stage049_simulations.csv"
PAIR_NAME = "stage049_paired_simulations.csv"
SUMMARY_NAME = "stage049_monte_carlo_summary.csv"
PAIR_SUMMARY_NAME = "stage049_paired_summary.csv"
SOURCE_STATS_NAME = "stage049_source_path_stats.csv"
DECISION_NAME = "stage049_decision.json"
REPORT_NAME = "stage049_monte_carlo_report.md"
FAN_CHART_NAME = "stage049_nav_fan_ac.png"
DD_CHART_NAME = "stage049_drawdown_probability_ac.png"
PAIR_CHART_NAME = "stage049_paired_advantage_ac.png"

ARM_LABELS = {
    "A": "A Current Online",
    "C": "C Stage037",
}
ARM_COLORS = {
    "A": "#2563eb",
    "C": "#16a34a",
}


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=PROJECT_DIR,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _json_safe(value: Any) -> Any:
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if pd.isna(value):
        return None
    return value


def _md_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "(empty)"
    return frame.to_markdown(index=False)


def _runtime_contract_sha256() -> str:
    digest = sha256(str(RUNNER_CONTRACT_VERSION).encode())
    for path in (
        Path(__file__),
        Path(s47.__file__),
        SOURCE_CURVE,
        SOURCE_SUMMARY,
        SOURCE_DECISION,
        STAGE048_DECISION,
    ):
        digest.update(str(path.resolve()).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _preflight() -> dict[str, Any]:
    for path in (SOURCE_CURVE, SOURCE_SUMMARY, SOURCE_DECISION, STAGE048_DECISION):
        if not path.exists():
            raise FileNotFoundError(path)
    for commit in (STAGE047_RESULT_COMMIT, STAGE048_RESULT_COMMIT):
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit, "HEAD"],
            cwd=PROJECT_DIR,
            check=True,
        )

    live_identity = s47._preflight()
    source_decision = json.loads(SOURCE_DECISION.read_text(encoding="utf-8"))
    stage048_decision = json.loads(STAGE048_DECISION.read_text(encoding="utf-8"))
    if source_decision.get("stage") != "Stage047":
        raise RuntimeError("stage049_source_decision_stage_mismatch")
    if not bool(source_decision.get("full_period_comparison_pass")):
        raise RuntimeError("stage049_source_full_period_gate_not_passed")
    if _file_sha256(STAGE048_DECISION) != STAGE048_DECISION_SHA256:
        raise RuntimeError("stage049_stage048_decision_sha_drift")
    expected_stage048_fields = {
        "stage": "Stage048",
        "all_multicycle_gates_pass": False,
        "promote_to_official": False,
        "decision": "stage037_multicycle_has_hard_fail_keep_research",
    }
    for field, expected in expected_stage048_fields.items():
        if stage048_decision.get(field) != expected:
            raise RuntimeError(f"stage049_stage048_decision_field_mismatch:{field}")
    source_identity = source_decision.get("identity", {})
    for field in ("production_head", "remote_master", "origin_master_tracking"):
        if source_identity.get(field) != live_identity.get(field):
            raise RuntimeError(f"stage049_live_identity_drift:{field}")
    if source_identity.get("ai_pool", {}).get("sha256") != live_identity.get("ai_pool", {}).get("sha256"):
        raise RuntimeError("stage049_ai_pool_identity_drift")
    if source_identity.get("runtime_binding", {}).get("database_sha256") != live_identity.get(
        "runtime_binding", {}
    ).get("database_sha256"):
        raise RuntimeError("stage049_database_identity_drift")
    if s47.override_diff() != s47._expected_override_diff():
        raise RuntimeError("stage049_candidate_scope_drift")

    return {
        **live_identity,
        "stage047_result_commit": STAGE047_RESULT_COMMIT,
        "stage048_result_commit": STAGE048_RESULT_COMMIT,
        "stage049_parent_head": _git("rev-parse", "HEAD"),
        "source_curve_sha256": _file_sha256(SOURCE_CURVE),
        "source_summary_sha256": _file_sha256(SOURCE_SUMMARY),
        "source_decision_sha256": _file_sha256(SOURCE_DECISION),
        "stage048_decision_sha256": _file_sha256(STAGE048_DECISION),
        "runtime_contract_sha256": _runtime_contract_sha256(),
    }


def _load_aligned_returns() -> tuple[pd.DataFrame, pd.DataFrame]:
    curve = pd.read_csv(SOURCE_CURVE, parse_dates=["date"])
    source_summary = pd.read_csv(SOURCE_SUMMARY)
    if set(curve["experiment_arm"].astype(str)) != {"A", "C"}:
        raise RuntimeError("stage049_source_curve_arm_mismatch")
    if set(source_summary["experiment_arm"].astype(str)) != {"A", "C"} or len(source_summary) != 2:
        raise RuntimeError("stage049_source_summary_arm_mismatch")
    if curve.duplicated(["experiment_arm", "date"]).any():
        raise RuntimeError("stage049_source_curve_duplicate_date")

    aligned: pd.DataFrame | None = None
    stats: list[dict[str, Any]] = []
    for arm in ("A", "C"):
        frame = curve[curve["experiment_arm"].astype(str).eq(arm)].copy()
        source_row = source_summary[source_summary["experiment_arm"].astype(str).eq(arm)].iloc[0]
        frame = frame.sort_values("date").reset_index(drop=True)
        nav = pd.to_numeric(frame["rebased_nav"], errors="raise")
        if not np.isfinite(nav).all() or (nav <= 0).any():
            raise RuntimeError(f"stage049_invalid_nav:{arm}")
        daily_return = nav.pct_change()
        arm_frame = pd.DataFrame({"date": frame["date"], arm: daily_return})
        aligned = arm_frame if aligned is None else aligned.merge(arm_frame, on="date", how="inner", validate="one_to_one")

        running_peak = np.maximum.accumulate(nav.to_numpy(dtype=float))
        max_dd_pct = float(np.min(nav.to_numpy(dtype=float) / running_peak - 1.0) * 100.0)
        returns = daily_return.dropna().to_numpy(dtype=float)
        if not np.isclose(float(nav.iloc[-1]), float(source_row["nav_end"]), rtol=0.0, atol=1e-9):
            raise RuntimeError(f"stage049_source_end_nav_mismatch:{arm}")
        if not np.isclose(max_dd_pct, float(source_row["rebased_max_dd_pct"]), rtol=0.0, atol=1e-9):
            raise RuntimeError(f"stage049_source_max_dd_mismatch:{arm}")
        stats.append(
            {
                "arm": arm,
                "label": ARM_LABELS[arm],
                "start_date": str(frame["date"].min().date()),
                "end_date": str(frame["date"].max().date()),
                "source_days": int(len(frame)),
                "return_count": int(len(returns)),
                "historical_end_nav": float(source_row["nav_end"]),
                "historical_end_equity": float(source_row["rebased_end_equity"]),
                "historical_total_return_pct": float(source_row["rebased_total_return_pct"]),
                "historical_max_dd_pct": float(source_row["rebased_max_dd_pct"]),
                "historical_sharpe": float(source_row["rebased_sharpe"]),
                "historical_total_slippage": float(source_row["total_slippage"]),
                "historical_total_trade_count": int(source_row["total_trade_count"]),
                "historical_nonzero_daily_win_rate_pct": float(source_row["nonzero_daily_win_rate_pct"]),
            }
        )

    assert aligned is not None
    aligned = aligned.dropna().sort_values("date").reset_index(drop=True)
    if len(aligned) < 1_000:
        raise RuntimeError(f"stage049_too_few_aligned_returns:{len(aligned)}")
    if not np.isfinite(aligned[["A", "C"]].to_numpy(dtype=float)).all():
        raise RuntimeError("stage049_nonfinite_aligned_returns")
    if aligned[["A", "C"]].le(-1.0).any().any():
        raise RuntimeError("stage049_return_le_minus_one")
    return aligned, pd.DataFrame(stats)


def _circular_block_indices(
    rng: np.random.Generator,
    *,
    n_paths: int,
    n_observations: int,
    block_length: int,
) -> np.ndarray:
    if n_paths <= 0 or n_observations <= 0 or block_length <= 0:
        raise ValueError("stage049_invalid_bootstrap_dimensions")
    if block_length == 1:
        return rng.integers(0, n_observations, size=(n_paths, n_observations), endpoint=False)
    n_blocks = int(np.ceil(n_observations / block_length))
    starts = rng.integers(0, n_observations, size=(n_paths, n_blocks), endpoint=False)
    offsets = np.arange(block_length, dtype=np.int64)
    indices = (starts[:, :, None] + offsets[None, None, :]) % n_observations
    return indices.reshape(n_paths, n_blocks * block_length)[:, :n_observations]


def _path_metrics(sampled_returns: np.ndarray) -> dict[str, np.ndarray]:
    nav = np.cumprod(1.0 + sampled_returns, axis=1)
    running_peak = np.maximum(1.0, np.maximum.accumulate(nav, axis=1))
    drawdown = nav / running_peak - 1.0
    std = np.std(sampled_returns, axis=1, ddof=1)
    sharpe = np.divide(
        np.mean(sampled_returns, axis=1) * np.sqrt(252.0),
        std,
        out=np.full_like(std, np.nan, dtype=float),
        where=std > 0,
    )
    return {
        "end_nav": nav[:, -1],
        "total_return_pct": (nav[:, -1] - 1.0) * 100.0,
        "max_dd_pct": np.min(drawdown, axis=1) * 100.0,
        "min_nav": np.minimum(1.0, np.min(nav, axis=1)),
        "sharpe": sharpe,
        "days_below_initial": np.sum(nav < 1.0, axis=1),
        "nav_paths": nav,
    }


def _simulate_paired(
    returns: np.ndarray,
    *,
    block_length: int,
    n_simulations: int,
    seed: int,
    collect_paths: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, np.ndarray] | None]:
    if returns.ndim != 2 or returns.shape[1] != 2:
        raise ValueError("stage049_returns_must_be_n_by_two")
    method = "iid" if block_length == 1 else f"block_{block_length}"
    rng = np.random.default_rng(seed)
    arm_rows: list[pd.DataFrame] = []
    pair_rows: list[pd.DataFrame] = []
    collected: dict[str, list[np.ndarray]] = {"A": [], "C": []}
    done = 0
    while done < n_simulations:
        chunk = min(CHUNK_SIZE, n_simulations - done)
        indices = _circular_block_indices(
            rng,
            n_paths=chunk,
            n_observations=len(returns),
            block_length=block_length,
        )
        metrics: dict[str, dict[str, np.ndarray]] = {}
        simulation_ids = np.arange(done + 1, done + chunk + 1)
        for column, arm in enumerate(("A", "C")):
            arm_metrics = _path_metrics(returns[indices, column])
            metrics[arm] = arm_metrics
            arm_rows.append(
                pd.DataFrame(
                    {
                        "simulation": simulation_ids,
                        "method": method,
                        "block_length": block_length,
                        "arm": arm,
                        "end_nav": arm_metrics["end_nav"],
                        "total_return_pct": arm_metrics["total_return_pct"],
                        "max_dd_pct": arm_metrics["max_dd_pct"],
                        "min_nav": arm_metrics["min_nav"],
                        "sharpe": arm_metrics["sharpe"],
                        "days_below_initial": arm_metrics["days_below_initial"],
                    }
                )
            )
            if collect_paths:
                collected[arm].append(arm_metrics["nav_paths"])

        pair_rows.append(
            pd.DataFrame(
                {
                    "simulation": simulation_ids,
                    "method": method,
                    "block_length": block_length,
                    "C_minus_A_end_nav": metrics["C"]["end_nav"] - metrics["A"]["end_nav"],
                    "C_minus_A_return_pct": metrics["C"]["total_return_pct"]
                    - metrics["A"]["total_return_pct"],
                    "C_minus_A_max_dd_pct": metrics["C"]["max_dd_pct"] - metrics["A"]["max_dd_pct"],
                    "C_minus_A_sharpe": metrics["C"]["sharpe"] - metrics["A"]["sharpe"],
                    "C_end_nav_above_A": metrics["C"]["end_nav"] > metrics["A"]["end_nav"],
                    "C_dd_noninferior_2pp": metrics["C"]["max_dd_pct"]
                    >= metrics["A"]["max_dd_pct"] - 2.0,
                    "C_sharpe_noninferior_005": metrics["C"]["sharpe"] >= metrics["A"]["sharpe"] - 0.05,
                }
            )
        )
        done += chunk

    path_payload = None
    if collect_paths:
        path_payload = {arm: np.vstack(paths) for arm, paths in collected.items()}
    return pd.concat(arm_rows, ignore_index=True), pd.concat(pair_rows, ignore_index=True), path_payload


def _summarize_simulations(simulations: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (method, block_length, arm), group in simulations.groupby(["method", "block_length", "arm"], sort=False):
        row: dict[str, Any] = {
            "method": method,
            "block_length": int(block_length),
            "arm": arm,
            "label": ARM_LABELS[str(arm)],
            "n_simulations": int(len(group)),
            "prob_end_below_initial_pct": float((group["end_nav"] < 1.0).mean() * 100.0),
            "prob_maxdd_gt_40_pct": float((group["max_dd_pct"] <= -40.0).mean() * 100.0),
            "prob_maxdd_gt_50_pct": float((group["max_dd_pct"] <= -50.0).mean() * 100.0),
            "prob_maxdd_gt_60_pct": float((group["max_dd_pct"] <= -60.0).mean() * 100.0),
            "prob_min_nav_lt_050_pct": float((group["min_nav"] < 0.50).mean() * 100.0),
        }
        for metric in ("end_nav", "total_return_pct", "max_dd_pct", "sharpe", "days_below_initial"):
            for quantile in (0.01, 0.05, 0.10, 0.50, 0.90, 0.95, 0.99):
                row[f"{metric}_p{int(quantile * 100):02d}"] = float(group[metric].quantile(quantile))
        rows.append(row)
    return pd.DataFrame(rows)


def _summarize_pairs(pairs: pd.DataFrame, summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (method, block_length), group in pairs.groupby(["method", "block_length"], sort=False):
        arm_summary = summary[summary["method"].eq(method)].set_index("arm")
        row = {
            "method": method,
            "block_length": int(block_length),
            "n_simulations": int(len(group)),
            "C_return_win_rate_pct": float(group["C_end_nav_above_A"].mean() * 100.0),
            "C_return_delta_p05_pct": float(group["C_minus_A_return_pct"].quantile(0.05)),
            "C_return_delta_p50_pct": float(group["C_minus_A_return_pct"].quantile(0.50)),
            "C_return_delta_p95_pct": float(group["C_minus_A_return_pct"].quantile(0.95)),
            "C_dd_noninferior_2pp_rate_pct": float(group["C_dd_noninferior_2pp"].mean() * 100.0),
            "C_dd_delta_p05_pct": float(group["C_minus_A_max_dd_pct"].quantile(0.05)),
            "C_dd_delta_p50_pct": float(group["C_minus_A_max_dd_pct"].quantile(0.50)),
            "C_sharpe_noninferior_005_rate_pct": float(
                group["C_sharpe_noninferior_005"].mean() * 100.0
            ),
            "C_sharpe_delta_p05": float(group["C_minus_A_sharpe"].quantile(0.05)),
            "C_sharpe_delta_p50": float(group["C_minus_A_sharpe"].quantile(0.50)),
            "C_p05_end_nav": float(arm_summary.loc["C", "end_nav_p05"]),
            "A_p05_end_nav": float(arm_summary.loc["A", "end_nav_p05"]),
            "C_prob_dd50_pct": float(arm_summary.loc["C", "prob_maxdd_gt_50_pct"]),
            "A_prob_dd50_pct": float(arm_summary.loc["A", "prob_maxdd_gt_50_pct"]),
        }
        row["gate_return_win_rate"] = bool(row["C_return_win_rate_pct"] >= 55.0)
        row["gate_return_delta_median"] = bool(row["C_return_delta_p50_pct"] >= 0.0)
        row["gate_dd_noninferior"] = bool(row["C_dd_noninferior_2pp_rate_pct"] >= 80.0)
        row["gate_sharpe_noninferior"] = bool(row["C_sharpe_noninferior_005_rate_pct"] >= 80.0)
        row["gate_p05_end_nav"] = bool(row["C_p05_end_nav"] >= row["A_p05_end_nav"])
        row["gate_dd50_probability"] = bool(row["C_prob_dd50_pct"] <= row["A_prob_dd50_pct"])
        row["all_gates_pass"] = bool(
            row["gate_return_win_rate"]
            and row["gate_return_delta_median"]
            and row["gate_dd_noninferior"]
            and row["gate_sharpe_noninferior"]
            and row["gate_p05_end_nav"]
            and row["gate_dd50_probability"]
        )
        rows.append(row)
    return pd.DataFrame(rows)


def _plot_fan(paths_by_method: dict[str, dict[str, np.ndarray]], dates: pd.Series) -> None:
    fig, axes = plt.subplots(1, len(MAIN_BLOCK_LENGTHS), figsize=(20, 7), sharey=False)
    for ax, block_length in zip(np.atleast_1d(axes), MAIN_BLOCK_LENGTHS, strict=True):
        method = f"block_{block_length}"
        for arm in ("A", "C"):
            paths = paths_by_method[method][arm]
            p05, p50, p95 = np.percentile(paths, [5, 50, 95], axis=0)
            color = ARM_COLORS[arm]
            ax.fill_between(dates, p05, p95, color=color, alpha=0.10)
            ax.plot(dates, p50, color=color, linewidth=2.0, label=f"{ARM_LABELS[arm]} median")
        ax.axhline(1.0, color="#64748b", linestyle="--", linewidth=1.0)
        ax.set_title(f"Circular block bootstrap: {block_length} trading days")
        ax.set_ylabel("Rebased NAV")
        ax.grid(True, alpha=0.22)
        ax.legend()
    fig.suptitle("Stage049 Monte Carlo NAV fan: p05-p95 bands, 2,000 paths", fontsize=15)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(OUTPUT_DIR / FAN_CHART_NAME, dpi=170)
    plt.close(fig)


def _plot_drawdown_probability(summary: pd.DataFrame) -> None:
    metrics = (
        ("prob_maxdd_gt_40_pct", "P(maxDD > 40%)"),
        ("prob_maxdd_gt_50_pct", "P(maxDD > 50%)"),
        ("prob_maxdd_gt_60_pct", "P(maxDD > 60%)"),
    )
    fig, axes = plt.subplots(1, 3, figsize=(20, 6), sharey=True)
    methods = ["iid", "block_20", "block_60", "block_120"]
    x = np.arange(len(methods))
    width = 0.36
    for ax, (metric, title) in zip(axes, metrics, strict=True):
        for offset, arm in ((-width / 2, "A"), (width / 2, "C")):
            view = summary[summary["arm"].eq(arm)].set_index("method").loc[methods]
            ax.bar(x + offset, view[metric], width, color=ARM_COLORS[arm], alpha=0.82, label=ARM_LABELS[arm])
        ax.set_xticks(x)
        ax.set_xticklabels(methods, rotation=20)
        ax.set_title(title)
        ax.grid(axis="y", alpha=0.22)
    axes[0].set_ylabel("Probability (%)")
    axes[0].legend()
    fig.suptitle("Stage049 Monte Carlo drawdown breach probability", fontsize=15)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(OUTPUT_DIR / DD_CHART_NAME, dpi=170)
    plt.close(fig)


def _plot_paired_advantage(pair_summary: pd.DataFrame) -> None:
    methods = ["iid", "block_20", "block_60", "block_120"]
    view = pair_summary.set_index("method").loc[methods]
    fig, ax = plt.subplots(figsize=(14, 7))
    x = np.arange(len(methods))
    width = 0.24
    ax.bar(x - width, view["C_return_win_rate_pct"], width, color="#16a34a", label="C return beats A")
    ax.bar(x, view["C_dd_noninferior_2pp_rate_pct"], width, color="#f59e0b", label="C DD noninferior (2pp)")
    ax.bar(x + width, view["C_sharpe_noninferior_005_rate_pct"], width, color="#7c3aed", label="C Sharpe noninferior (0.05)")
    ax.axhline(80.0, color="#475569", linestyle="--", linewidth=1.1, label="80% path-quality gate")
    ax.axhline(55.0, color="#94a3b8", linestyle=":", linewidth=1.1, label="55% return gate")
    ax.set_xticks(x)
    ax.set_xticklabels(methods)
    ax.set_ylim(0, 105)
    ax.set_ylabel("Paired-path rate (%)")
    ax.set_title("Stage037 paired Monte Carlo advantage versus current online")
    ax.grid(axis="y", alpha=0.22)
    ax.legend(ncol=2)
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / PAIR_CHART_NAME, dpi=170)
    plt.close(fig)


def _write_report(
    source_stats: pd.DataFrame,
    summary: pd.DataFrame,
    pair_summary: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    key_summary = summary[summary["method"].isin(["block_60", "block_120"])][
        [
            "method",
            "arm",
            "end_nav_p05",
            "end_nav_p50",
            "total_return_pct_p05",
            "total_return_pct_p50",
            "max_dd_pct_p05",
            "max_dd_pct_p50",
            "prob_maxdd_gt_40_pct",
            "prob_maxdd_gt_50_pct",
            "prob_maxdd_gt_60_pct",
        ]
    ].copy()
    pair_view = pair_summary[
        [
            "method",
            "C_return_win_rate_pct",
            "C_return_delta_p05_pct",
            "C_return_delta_p50_pct",
            "C_dd_noninferior_2pp_rate_pct",
            "C_dd_delta_p50_pct",
            "C_sharpe_noninferior_005_rate_pct",
            "C_sharpe_delta_p50",
            "all_gates_pass",
        ]
    ].copy()
    for frame in (key_summary, pair_view):
        for column in frame.select_dtypes(include=["number"]).columns:
            frame[column] = frame[column].map(lambda value: round(float(value), 4))

    report = "\n".join(
        [
            "# Stage049 Stage037 与当前线上版蒙特卡洛路径复核",
            "",
            "本阶段不改策略、不调参数、不连接CTP，只对Stage047冻结的全周期日收益路径做成对circular block bootstrap。",
            "",
            "## 方法",
            "",
            f"- 每种方法 `{N_SIMULATIONS:,}` 条路径，固定随机种子 `{RANDOM_SEED}`。",
            "- `iid`、`block_20`、`block_60`、`block_120`；主结论只认60/120日块。",
            "- A/C共用同一组重采样索引，保留同一历史时点下两策略的横向关系；每个块内保持原始日收益顺序并允许年末循环衔接。",
            "- 这是路径重采样，不重新运行交易引擎，不代表未来收益预测，也不能替代Stage048的独立冷启动失败结论。",
            "",
            "## 历史源路径",
            "",
            _md_table(source_stats),
            "",
            "## 主口径结果",
            "",
            _md_table(key_summary),
            "",
            "## 成对比较",
            "",
            _md_table(pair_view),
            "",
            "## 预声明门",
            "",
            "60/120日块分别要求：C收益胜率>=55%、收益差中位>=0、DD不劣2pp率>=80%、Sharpe不劣0.05率>=80%、C的p05期末NAV不低于A、C的DD50概率不高于A。两种主块必须全部通过才可称蒙特卡洛支持稳定路径优势。",
            "",
            "## 结论",
            "",
            f"- 决策：`{decision['decision']}`。",
            f"- 主块全部通过：`{decision['main_methods_all_pass']}`。",
            "- 无论本阶段是否通过，Stage048多周期硬失败仍有效，因此不晋升正式版、不改线上。",
            "",
            "## 输出",
            "",
            f"- `{SUMMARY_NAME}` / `{PAIR_SUMMARY_NAME}`",
            f"- `{SIMULATION_NAME}` / `{PAIR_NAME}`",
            f"- `{FAN_CHART_NAME}` / `{DD_CHART_NAME}` / `{PAIR_CHART_NAME}`",
            f"- `{DECISION_NAME}`",
        ]
    )
    (OUTPUT_DIR / REPORT_NAME).write_text(report, encoding="utf-8")


def main() -> None:
    identity = _preflight()
    aligned, source_stats = _load_aligned_returns()
    returns = aligned[["A", "C"]].to_numpy(dtype=float)

    all_simulations: list[pd.DataFrame] = []
    all_pairs: list[pd.DataFrame] = []
    paths_by_method: dict[str, dict[str, np.ndarray]] = {}
    for block_length in BLOCK_LENGTHS:
        method = "iid" if block_length == 1 else f"block_{block_length}"
        print(f"[stage049] {method}: simulations={N_SIMULATIONS}", flush=True)
        simulations, pairs, _ = _simulate_paired(
            returns,
            block_length=block_length,
            n_simulations=N_SIMULATIONS,
            seed=RANDOM_SEED + block_length,
            collect_paths=False,
        )
        all_simulations.append(simulations)
        all_pairs.append(pairs)
        if block_length in MAIN_BLOCK_LENGTHS:
            _, _, paths = _simulate_paired(
                returns,
                block_length=block_length,
                n_simulations=PLOT_SIMULATIONS,
                seed=RANDOM_SEED + 10_000 + block_length,
                collect_paths=True,
            )
            assert paths is not None
            paths_by_method[method] = paths

    simulations = pd.concat(all_simulations, ignore_index=True)
    pairs = pd.concat(all_pairs, ignore_index=True)
    summary = _summarize_simulations(simulations)
    pair_summary = _summarize_pairs(pairs, summary)
    main_view = pair_summary[pair_summary["block_length"].isin(MAIN_BLOCK_LENGTHS)]
    main_methods_all_pass = bool(len(main_view) == len(MAIN_BLOCK_LENGTHS) and main_view["all_gates_pass"].all())
    decision_code = (
        "stage049_mc_supports_stage037_path_advantage_but_stage048_hard_fail_keep_research"
        if main_methods_all_pass
        else "stage049_mc_does_not_support_stable_stage037_path_advantage_keep_research"
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    source_stats.to_csv(OUTPUT_DIR / SOURCE_STATS_NAME, index=False, encoding="utf-8-sig")
    simulations.to_csv(OUTPUT_DIR / SIMULATION_NAME, index=False, encoding="utf-8-sig")
    pairs.to_csv(OUTPUT_DIR / PAIR_NAME, index=False, encoding="utf-8-sig")
    summary.to_csv(OUTPUT_DIR / SUMMARY_NAME, index=False, encoding="utf-8-sig")
    pair_summary.to_csv(OUTPUT_DIR / PAIR_SUMMARY_NAME, index=False, encoding="utf-8-sig")

    plot_dates = aligned["date"].reset_index(drop=True)
    _plot_fan(paths_by_method, plot_dates)
    _plot_drawdown_probability(summary)
    _plot_paired_advantage(pair_summary)

    decision = {
        "line_id": "futures_trend_rollover_shape_same_volume",
        "stage": "Stage049",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "identity": identity,
        "source": {
            "curve": str(SOURCE_CURVE.resolve()),
            "summary": str(SOURCE_SUMMARY.resolve()),
            "decision": str(SOURCE_DECISION.resolve()),
            "aligned_return_count": int(len(aligned)),
            "start_date": str(aligned["date"].min().date()),
            "end_date": str(aligned["date"].max().date()),
        },
        "method": {
            "type": "paired_circular_block_bootstrap_on_daily_returns",
            "n_simulations_per_method": N_SIMULATIONS,
            "plot_simulations_per_main_method": PLOT_SIMULATIONS,
            "block_lengths": list(BLOCK_LENGTHS),
            "main_block_lengths": list(MAIN_BLOCK_LENGTHS),
            "random_seed": RANDOM_SEED,
            "common_indices_for_A_and_C": True,
        },
        "predeclared_gates": {
            "C_return_win_rate_pct_min": 55.0,
            "C_return_delta_p50_pct_min": 0.0,
            "C_dd_noninferior_2pp_rate_pct_min": 80.0,
            "C_sharpe_noninferior_005_rate_pct_min": 80.0,
            "C_p05_end_nav_not_below_A": True,
            "C_prob_dd50_not_above_A": True,
            "all_main_methods_required": True,
        },
        "main_methods_all_pass": main_methods_all_pass,
        "decision": decision_code,
        "promote_to_official": False,
        "stage048_multicycle_hard_fail_remains_binding": True,
        "order_api_called_count": 0,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "outputs": {
            "source_stats": SOURCE_STATS_NAME,
            "simulations": SIMULATION_NAME,
            "paired_simulations": PAIR_NAME,
            "summary": SUMMARY_NAME,
            "paired_summary": PAIR_SUMMARY_NAME,
            "report": REPORT_NAME,
            "fan_chart": FAN_CHART_NAME,
            "drawdown_chart": DD_CHART_NAME,
            "paired_chart": PAIR_CHART_NAME,
        },
    }
    (OUTPUT_DIR / DECISION_NAME).write_text(
        json.dumps(decision, ensure_ascii=False, indent=2, default=_json_safe),
        encoding="utf-8",
    )
    _write_report(source_stats, summary, pair_summary, decision)
    print(json.dumps(decision, ensure_ascii=False, indent=2, default=_json_safe), flush=True)


if __name__ == "__main__":
    main()
