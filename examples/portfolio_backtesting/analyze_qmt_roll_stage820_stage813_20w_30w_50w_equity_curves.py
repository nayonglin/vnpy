from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage820_stage813_20w_30w_50w_equity_curves_v1"
OUTPUT_PREFIX = "qmt_roll_stage820_stage813_20w_30w_50w_equity_curves"
LINE_ID = "futures_trend_2019_data_extension"

CURVES_20W_PATH = (
    OUTPUT_DIR / "qmt_roll_stage817_stage813_20w_yearly_curves_stage817_stage813_20w_yearly_v1.csv"
)
CURVES_30W_PATH = (
    OUTPUT_DIR / "qmt_roll_stage819_stage813_30w_yearly_curves_stage819_stage813_30w_yearly_v1.csv"
)
CURVES_50W_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage813_stage804_rsi_partial_exit_ablation_yearly_on_curves_"
    "stage813_stage804_rsi_partial_exit_ablation_yearly_v1.csv"
)

ABSOLUTE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_absolute_{MODEL_TAG}.png"
NORMALIZED_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_normalized_{MODEL_TAG}.png"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

SERIES = [
    ("Stage813 50w", CURVES_50W_PATH, "#1d4ed8", 1.25),
    ("Stage819 30w", CURVES_30W_PATH, "#16a34a", 1.35),
    ("Stage817 20w", CURVES_20W_PATH, "#dc2626", 1.25),
]


def _load_curves(path: Path, label: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    frame = pd.read_csv(path, parse_dates=["date"], encoding="utf-8-sig")
    required = {"date", "start_month", "account_equity", "nav"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{path} missing columns: {missing}")
    frame = frame.copy()
    frame["start_month"] = frame["start_month"].astype(str)
    frame["series_label"] = label
    return frame.sort_values(["start_month", "date"]).reset_index(drop=True)


def _shared_starts(curves_by_label: dict[str, pd.DataFrame]) -> list[str]:
    shared: set[str] | None = None
    for frame in curves_by_label.values():
        starts = set(frame["start_month"].astype(str).unique())
        shared = starts if shared is None else shared & starts
    if not shared:
        raise ValueError("no shared start_month values")
    return sorted(shared)


def _plot_grid(
    curves_by_label: dict[str, pd.DataFrame],
    starts: list[str],
    *,
    value_column: str,
    scale: float,
    ylabel: str,
    title: str,
    output_path: Path,
) -> None:
    fig, axes = plt.subplots(3, 3, figsize=(20, 12.5), sharex=False)
    axes = axes.ravel()
    color_map = {label: color for label, _path, color, _linewidth in SERIES}
    linewidth_map = {label: linewidth for label, _path, _color, linewidth in SERIES}

    for ax, start_month in zip(axes, starts, strict=False):
        for label, frame in curves_by_label.items():
            current = frame[frame["start_month"].eq(start_month)]
            values = pd.to_numeric(current[value_column], errors="coerce") / scale
            ax.plot(
                current["date"],
                values,
                color=color_map[label],
                linewidth=linewidth_map[label],
                label=label,
            )

        ax.set_title(start_month, fontsize=11)
        ax.grid(alpha=0.22)
        ax.tick_params(axis="x", labelrotation=25, labelsize=8)
        ax.tick_params(axis="y", labelsize=8)
        ax.set_ylabel(ylabel, fontsize=9)

    for ax in axes[len(starts) :]:
        ax.axis("off")

    handles, labels = axes[0].get_legend_handles_labels()
    fig.suptitle(title, y=0.992, fontsize=15)
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.963), ncol=3, frameon=False)
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def _write_report(starts: list[str]) -> None:
    lines = [
        "# Stage820 Stage813 20w/30w/50w Equity Curves",
        "",
        f"- line_id: `{LINE_ID}`",
        f"- model_tag: `{MODEL_TAG}`",
        "- Inputs:",
        f"  - 20w: `{CURVES_20W_PATH}`",
        f"  - 30w: `{CURVES_30W_PATH}`",
        f"  - 50w: `{CURVES_50W_PATH}`",
        f"- shared_start_months: `{', '.join(starts)}`",
        "- Outputs:",
        f"  - absolute: `{ABSOLUTE_PATH}`",
        f"  - normalized: `{NORMALIZED_PATH}`",
        "",
        "No backtest was rerun. This stage only plots existing Stage813 50w, Stage819 30w, and Stage817 20w yearly-start curves.",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curves_by_label = {label: _load_curves(path, label) for label, path, _color, _linewidth in SERIES}
    starts = _shared_starts(curves_by_label)

    _plot_grid(
        curves_by_label,
        starts,
        value_column="account_equity",
        scale=10_000.0,
        ylabel="Equity (10k CNY)",
        title="Stage813 Yearly Starts: 50w vs 30w vs 20w Absolute Equity",
        output_path=ABSOLUTE_PATH,
    )
    _plot_grid(
        curves_by_label,
        starts,
        value_column="nav",
        scale=1.0,
        ylabel="NAV (initial=1.0)",
        title="Stage813 Yearly Starts: 50w vs 30w vs 20w Normalized NAV",
        output_path=NORMALIZED_PATH,
    )
    _write_report(starts)
    print(f"absolute: {ABSOLUTE_PATH}")
    print(f"normalized: {NORMALIZED_PATH}")
    print(f"report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
