from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage818_stage813_20w_50w_equity_curves_v1"
OUTPUT_PREFIX = "qmt_roll_stage818_stage813_20w_50w_equity_curves"
LINE_ID = "futures_trend_2019_data_extension"

CURVES_20W_PATH = (
    OUTPUT_DIR / "qmt_roll_stage817_stage813_20w_yearly_curves_stage817_stage813_20w_yearly_v1.csv"
)
CURVES_50W_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage813_stage804_rsi_partial_exit_ablation_yearly_on_curves_"
    "stage813_stage804_rsi_partial_exit_ablation_yearly_v1.csv"
)

ABSOLUTE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_absolute_{MODEL_TAG}.png"
NORMALIZED_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_normalized_{MODEL_TAG}.png"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


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


def _plot_grid(
    curves_20w: pd.DataFrame,
    curves_50w: pd.DataFrame,
    *,
    value_column: str,
    scale: float,
    ylabel: str,
    title: str,
    output_path: Path,
) -> None:
    starts = sorted(set(curves_20w["start_month"].unique()) & set(curves_50w["start_month"].unique()))
    if not starts:
        raise ValueError("no shared start_month values")

    fig, axes = plt.subplots(3, 3, figsize=(19, 12), sharex=False)
    axes = axes.ravel()
    colors = {"Stage813 50w": "#1d4ed8", "Stage813 20w": "#dc2626"}

    for ax, start_month in zip(axes, starts, strict=False):
        left = curves_50w[curves_50w["start_month"].eq(start_month)]
        right = curves_20w[curves_20w["start_month"].eq(start_month)]
        for frame, label in [(left, "Stage813 50w"), (right, "Stage813 20w")]:
            values = pd.to_numeric(frame[value_column], errors="coerce") / scale
            ax.plot(frame["date"], values, color=colors[label], linewidth=1.25, label=label)

        ax.set_title(start_month, fontsize=11)
        ax.grid(alpha=0.22)
        ax.tick_params(axis="x", labelrotation=25, labelsize=8)
        ax.tick_params(axis="y", labelsize=8)
        ax.set_ylabel(ylabel, fontsize=9)

    for ax in axes[len(starts) :]:
        ax.axis("off")

    handles, labels = axes[0].get_legend_handles_labels()
    fig.suptitle(title, y=0.992, fontsize=15)
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.963), ncol=2, frameon=False)
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def _write_report() -> None:
    lines = [
        "# Stage818 Stage813 20w vs 50w Equity Curves",
        "",
        f"- line_id: `{LINE_ID}`",
        f"- model_tag: `{MODEL_TAG}`",
        "- Inputs:",
        f"  - 20w: `{CURVES_20W_PATH}`",
        f"  - 50w: `{CURVES_50W_PATH}`",
        "- Outputs:",
        f"  - absolute: `{ABSOLUTE_PATH}`",
        f"  - normalized: `{NORMALIZED_PATH}`",
        "",
        "No backtest was rerun. This stage only plots existing Stage813 50w and Stage817 20w yearly-start curves.",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curves_20w = _load_curves(CURVES_20W_PATH, "Stage813 20w")
    curves_50w = _load_curves(CURVES_50W_PATH, "Stage813 50w")

    _plot_grid(
        curves_20w,
        curves_50w,
        value_column="account_equity",
        scale=10_000.0,
        ylabel="Equity (10k CNY)",
        title="Stage813 Yearly Starts: 20w vs 50w Absolute Equity",
        output_path=ABSOLUTE_PATH,
    )
    _plot_grid(
        curves_20w,
        curves_50w,
        value_column="nav",
        scale=1.0,
        ylabel="NAV (initial=1.0)",
        title="Stage813 Yearly Starts: 20w vs 50w Normalized NAV",
        output_path=NORMALIZED_PATH,
    )
    _write_report()
    print(f"absolute: {ABSOLUTE_PATH}")
    print(f"normalized: {NORMALIZED_PATH}")
    print(f"report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
