from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from io import BytesIO
import json
import math
import os
from pathlib import Path
import sys
import tempfile
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage059_stage056_vs_stage037_multicycle as runner  # noqa: E402


OUTPUT_DIR = runner.OUTPUT_DIR
EFFECT_TOLERANCE = 1e-9


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def add_effect_diagnostics(
    aggregate: pd.DataFrame, comparison: pd.DataFrame
) -> pd.DataFrame:
    """Keep the frozen C>=A gate and add a strict, ties-excluded diagnostic."""

    diagnostic_columns = {
        "return_nonunderperformance_rate_pct",
        "tie_window_count",
        "effect_window_count",
        "strict_return_win_count",
        "strict_return_loss_count",
        "strict_return_win_rate_effect_pct",
    }
    result = aggregate.drop(
        columns=[column for column in diagnostic_columns if column in aggregate.columns]
    ).copy()
    result["return_nonunderperformance_rate_pct"] = pd.to_numeric(
        result["return_win_rate_pct"], errors="raise"
    )
    diagnostics: list[dict[str, Any]] = []
    rolling = comparison[pd.to_numeric(comparison["duration_years"]).gt(0)].copy()
    rolling["delta_return_pct"] = pd.to_numeric(rolling["delta_return_pct"], errors="raise")
    for years in runner.DURATIONS_YEARS:
        duration = rolling[rolling["duration_years"].eq(years)]
        for cohort, month in runner.COHORTS:
            group = duration if month is None else duration[duration["start_month_num"].eq(month)]
            ties = group["delta_return_pct"].abs().le(EFFECT_TOLERANCE)
            effect = group[~ties]
            wins = int(effect["delta_return_pct"].gt(EFFECT_TOLERANCE).sum())
            losses = int(effect["delta_return_pct"].lt(-EFFECT_TOLERANCE).sum())
            diagnostics.append(
                {
                    "duration_years": years,
                    "start_cohort": cohort,
                    "tie_window_count": int(ties.sum()),
                    "effect_window_count": int(len(effect)),
                    "strict_return_win_count": wins,
                    "strict_return_loss_count": losses,
                    "strict_return_win_rate_effect_pct": (
                        float(wins / len(effect) * 100.0) if len(effect) else np.nan
                    ),
                }
            )
    additions = pd.DataFrame(diagnostics)
    return result.merge(
        additions, on=["duration_years", "start_cohort"], how="left", validate="one_to_one"
    )


def _png(fig: plt.Figure, *, dpi: int) -> bytes:
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=dpi)
    plt.close(fig)
    return buffer.getvalue()


def _plot_full(curves: pd.DataFrame) -> bytes:
    fig, ax = plt.subplots(figsize=(14, 6))
    for arm in runner.ARMS:
        item = curves[
            curves["window_group"].eq("full_period")
            & curves["promotion_arm"].eq(arm["arm"])
        ].sort_values("date")
        ax.plot(
            pd.to_datetime(item["date"]),
            pd.to_numeric(item["account_equity"]) / 10_000,
            color=arm["color"],
            lw=1.4,
            label=arm["plot_label"],
        )
    ax.set_title("Stage059 OFFLINE RESEARCH — Full Period: Stage037 vs Stage056")
    ax.set_ylabel("Equity (10k CNY)")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    return _png(fig, dpi=170)


def _plot_grid(curves: pd.DataFrame, comparison: pd.DataFrame, years: int) -> bytes:
    selected = comparison[comparison["duration_years"].eq(years)].sort_values("requested_start")
    rows = math.ceil(len(selected) / 4)
    fig, axes = plt.subplots(rows, 4, figsize=(18, 3.5 * rows), squeeze=False)
    for ax, (_, window) in zip(axes.ravel(), selected.iterrows(), strict=False):
        data = curves[curves["window_id"].eq(window["window_id"])]
        for arm in runner.ARMS:
            item = data[data["promotion_arm"].eq(arm["arm"])].sort_values("date")
            ax.plot(
                pd.to_datetime(item["date"]),
                pd.to_numeric(item["account_equity"]) / 10_000,
                color=arm["color"],
                lw=1,
                label=arm["plot_label"],
            )
        ax.set_title(f"{window['requested_start']} ({years}Y)", fontsize=10)
        ax.grid(alpha=0.22)
        ax.tick_params(axis="x", rotation=25, labelsize=8)
    for ax in axes.ravel()[len(selected) :]:
        ax.axis("off")
    handles, labels = axes.ravel()[0].get_legend_handles_labels()
    fig.suptitle(
        f"Stage059 OFFLINE RESEARCH — {years}-Year Independent Curves: January + June Starts",
        y=0.998,
        fontsize=15,
    )
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.975), ncol=2)
    fig.tight_layout(rect=[0, 0.01, 1, 0.94])
    return _png(fig, dpi=150)


def _matrix(aggregate: pd.DataFrame, column: str) -> np.ndarray:
    return np.array(
        [
            [
                float(
                    aggregate[
                        aggregate["start_cohort"].eq(cohort)
                        & aggregate["duration_years"].eq(years)
                    ].iloc[0][column]
                )
                for years in runner.DURATIONS_YEARS
            ]
            for cohort, _ in runner.COHORTS
        ]
    )


def _plot_aggregate(aggregate: pd.DataFrame) -> bytes:
    metrics = (
        ("return_nonunderperformance_rate_pct", "C>=A Non-Underperformance (%)\nTies Included", "YlGn", 0, 100),
        ("strict_return_win_rate_effect_pct", "Strict Win Rate on Effect Windows (%)\nTies Excluded", "Greens", 0, 100),
        ("median_return_delta_pct", "Median Return Delta (pp)", "coolwarm", None, None),
        ("dd_noninferior_2pp_rate_pct", "DD Non-Inferior <=2pp (%)", "YlOrBr", 0, 100),
        ("sharpe_noninferior_005_rate_pct", "Sharpe Non-Inferior (%)", "PuBuGn", 0, 100),
        ("slippage_ratio", "Aggregate Slippage Ratio", "Reds", 1.0, None),
    )
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    for ax, (column, title, cmap, vmin, vmax) in zip(axes.ravel(), metrics, strict=True):
        values = _matrix(aggregate, column)
        if column == "median_return_delta_pct":
            bound = max(float(np.abs(values).max()), 1.0)
            vmin, vmax = -bound, bound
        elif column == "slippage_ratio":
            vmax = max(float(values.max()), 1.05)
        image = ax.imshow(values, aspect="auto", cmap=cmap, vmin=vmin, vmax=vmax)
        for i in range(values.shape[0]):
            for j in range(values.shape[1]):
                fmt = ".3f" if column == "slippage_ratio" else ".1f"
                ax.text(j, i, format(values[i, j], fmt), ha="center", va="center")
        ax.set_title(title)
        ax.set_xticks(range(3), ["1Y", "2Y", "3Y"])
        ax.set_yticks(range(3), [item[0].title() for item in runner.COHORTS])
        fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    fig.suptitle(
        "Stage059 OFFLINE RESEARCH — Stage037 vs Stage056: Combined / January / June",
        fontsize=15,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    return _png(fig, dpi=170)


def _annotate_report(report: str, aggregate: pd.DataFrame) -> str:
    if "**OFFLINE RESEARCH**" not in report:
        report = report.replace(
            "# Stage059 Stage056 与 Stage037 多周期对比\n",
            "# Stage059 Stage056 与 Stage037 多周期对比\n\n"
            "> **OFFLINE RESEARCH**：本报告不是当前生产策略A/C，也不可直接用于晋升。\n",
            1,
        )
    old_header = "| 周期 | 起点 | 窗口 | C收益胜率 | 收益差中位 | DD非劣率 | Sharpe非劣率 | 滑点比 |"
    if old_header in report:
        report = report.replace(
            old_header,
            "| 周期 | 起点 | 窗口 | C非劣率(C>=A,含并列) | 差异窗 | 严格胜率(不含并列) | 收益差中位 | DD非劣率 | Sharpe非劣率 | 滑点比 |",
        ).replace(
            "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
            "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            1,
        )
    old_rows = []
    new_rows = []
    for row in aggregate.itertuples(index=False):
        old_rows.append(
            f"| {row.duration_years}年 | {row.start_cohort} | {row.window_count} | "
            f"{row.return_win_rate_pct:.2f}% | {row.median_return_delta_pct:+.4f}pp | "
            f"{row.dd_noninferior_2pp_rate_pct:.2f}% | {row.sharpe_noninferior_005_rate_pct:.2f}% | "
            f"{row.slippage_ratio:.4f} |"
        )
        new_rows.append(
            f"| {row.duration_years}年 | {row.start_cohort} | {row.window_count} | "
            f"{row.return_nonunderperformance_rate_pct:.2f}% | {int(row.effect_window_count)} | "
            f"{row.strict_return_win_rate_effect_pct:.2f}% | {row.median_return_delta_pct:+.4f}pp | "
            f"{row.dd_noninferior_2pp_rate_pct:.2f}% | {row.sharpe_noninferior_005_rate_pct:.2f}% | "
            f"{row.slippage_ratio:.4f} |"
        )
    for old, new in zip(old_rows, new_rows, strict=True):
        report = report.replace(old, new)
    explanation = (
        "## 独立review后的收益口径澄清\n\n"
        "- 冻结gate保持原定义：`C>=A`，因此零差窗口计为非劣；原字段不删除、不改判定。\n"
        "- AI池实际产生差异的窗口每个周期均为9个；严格排除并列后，"
        "1年为`3/9=33.33%`、2年为`6/9=66.67%`、3年为`4/9=44.44%`。\n"
        "- 因此名义非劣率不能解释为严格胜率，Stage056的研究结论仍为硬失败。\n\n"
    )
    if "## 独立review后的收益口径澄清" not in report:
        report = report.replace("## 最弱窗口\n", explanation + "## 最弱窗口\n")
    if "stage059_run_and_publish.py" not in report:
        report += (
            "\n## 二步发布的单一复现入口\n\n"
            "- 运行：`PYTHONPATH=$PWD .py311/bin/python "
            "research/lines/futures_trend_rollover_shape_same_volume/tools/stage059_run_and_publish.py`。\n"
            "- wrapper固定先运行真引擎与检查点，再运行独立review注释器；后者不会改变策略结果或冻结gate。\n"
        )
    return report


def _write_atomic(path: Path, payload: bytes) -> None:
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        temporary.write_bytes(payload)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def main() -> None:
    comparison = pd.read_csv(OUTPUT_DIR / runner.COMPARISON_NAME)
    aggregate_path = OUTPUT_DIR / runner.AGGREGATE_NAME
    aggregate = add_effect_diagnostics(pd.read_csv(aggregate_path), comparison)
    combined = aggregate[aggregate["start_cohort"].eq("combined")].set_index("duration_years")
    if combined["effect_window_count"].to_dict() != {1: 9, 2: 9, 3: 9}:
        raise RuntimeError("stage059_effect_window_contract_drift")
    if combined["strict_return_win_count"].to_dict() != {1: 3, 2: 6, 3: 4}:
        raise RuntimeError("stage059_strict_win_contract_drift")

    decision_path = OUTPUT_DIR / runner.DECISION_NAME
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    frozen = {
        "decision": decision["decision"],
        "all_multicycle_gates_pass": decision["all_multicycle_gates_pass"],
        "full_period_gates": decision["full_period_gates"],
        "cycle_gates": decision["cycle_gates"],
    }
    decision["post_review_annotation"] = {
        "annotated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "strategy_results_changed": False,
        "frozen_gates_changed": False,
        "annotation_script_sha256": _sha256(Path(__file__)),
        "label_contract": "OFFLINE RESEARCH",
        "return_nonunderperformance_definition": "C>=A; ties included; frozen gate unchanged",
        "strict_effect_window_definition": "abs(C-A)>1e-9; win requires C-A>1e-9",
        "combined_effect_diagnostics": {
            str(int(years)): {
                "effect_window_count": int(row.effect_window_count),
                "tie_window_count": int(row.tie_window_count),
                "strict_return_win_count": int(row.strict_return_win_count),
                "strict_return_loss_count": int(row.strict_return_loss_count),
                "strict_return_win_rate_effect_pct": float(row.strict_return_win_rate_effect_pct),
            }
            for years, row in combined.iterrows()
        },
    }
    assert frozen == {
        "decision": decision["decision"],
        "all_multicycle_gates_pass": decision["all_multicycle_gates_pass"],
        "full_period_gates": decision["full_period_gates"],
        "cycle_gates": decision["cycle_gates"],
    }

    curves = pd.read_csv(OUTPUT_DIR / runner.CURVE_NAME)
    report_path = OUTPUT_DIR / runner.REPORT_NAME
    report = _annotate_report(report_path.read_text(encoding="utf-8"), aggregate)
    charts = {
        runner.CHART_FILES["full_period"]: _plot_full(curves),
        runner.CHART_FILES["1y"]: _plot_grid(curves, comparison, 1),
        runner.CHART_FILES["2y"]: _plot_grid(curves, comparison, 2),
        runner.CHART_FILES["3y"]: _plot_grid(curves, comparison, 3),
        runner.CHART_FILES["aggregate"]: _plot_aggregate(aggregate),
    }

    _write_atomic(aggregate_path, aggregate.to_csv(index=False).encode("utf-8-sig"))
    _write_atomic(
        decision_path,
        (json.dumps(decision, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
    )
    _write_atomic(report_path, report.encode("utf-8"))
    for filename, payload in charts.items():
        _write_atomic(OUTPUT_DIR / filename, payload)
    print(json.dumps(decision["post_review_annotation"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
