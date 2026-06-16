from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
MODEL_TAG = "stage896_c9_vs_official_halfyear_rolling3y_v1"
PREFIX = "qmt_roll_stage896_c9_vs_official_halfyear_rolling3y"

CURVES_PATH = OUTPUT_DIR / f"{PREFIX}_curves_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{PREFIX}_comparison_{MODEL_TAG}.csv"

CHART_DIR = OUTPUT_DIR / f"{PREFIX}_charts_{MODEL_TAG}"
MANIFEST_PATH = CHART_DIR / f"{PREFIX}_curve_charts_manifest_{MODEL_TAG}.csv"
NAV_GRID_PATH = CHART_DIR / f"{PREFIX}_all_windows_nav_grid_{MODEL_TAG}.png"
EQUITY_GRID_PATH = CHART_DIR / f"{PREFIX}_all_windows_equity_grid_{MODEL_TAG}.png"

ARM_LABELS = {
    "official_live_stage372_20w": "A Stage372 official 20w",
    "c9_stage847_stage819_30w": "C9 Stage847 30w",
}
COLORS = {
    "official_live_stage372_20w": "#2563eb",
    "c9_stage847_stage819_30w": "#dc2626",
}


def _safe_float(value: object) -> float:
    return float(pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0])


def _format_window_title(row: pd.Series) -> str:
    suffix = " terminal partial" if int(row["terminal_partial"]) == 1 else " complete 3Y"
    return f"{row['window_start']} to {row['window_end']}{suffix}"


def _plot_single_window(curves: pd.DataFrame, comparison: pd.DataFrame, window_id: str) -> Path:
    data = curves[curves["window_id"].astype(str).eq(window_id)].copy()
    row = comparison[comparison["window_id"].astype(str).eq(window_id)].iloc[0]
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    chart_path = CHART_DIR / f"{PREFIX}_window_{window_id}_nav_and_equity_{MODEL_TAG}.png"

    fig, axes = plt.subplots(2, 1, figsize=(13.5, 8.0), sharex=True, constrained_layout=True)
    for arm_key, group in data.groupby("arm_key", sort=False):
        arm_key = str(arm_key)
        group = group.sort_values("date")
        label = ARM_LABELS.get(arm_key, arm_key)
        axes[0].plot(
            group["date"],
            pd.to_numeric(group["rebased_nav"], errors="coerce"),
            color=COLORS.get(arm_key, "#111827"),
            linewidth=1.8,
            label=label,
        )
        axes[1].plot(
            group["date"],
            pd.to_numeric(group["rebased_equity"], errors="coerce"),
            color=COLORS.get(arm_key, "#111827"),
            linewidth=1.8,
            label=label,
        )

    axes[0].axhline(1.0, color="#94a3b8", linewidth=0.9, linestyle="--")
    axes[0].set_title(
        "Normalized NAV, start = 1 | "
        f"A ret {row['return_official_pct']:.1f}%, DD {row['max_dd_official_pct']:.1f}% | "
        f"C9 ret {row['return_c9_pct']:.1f}%, DD {row['max_dd_c9_pct']:.1f}%"
    )
    axes[0].set_ylabel("NAV")
    axes[1].set_title("Absolute equity")
    axes[1].set_ylabel("Equity")
    axes[1].set_xlabel("Date")
    for ax in axes:
        ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.35)
        ax.legend(loc="upper left", frameon=False)
    fig.suptitle(_format_window_title(row), fontsize=15)
    fig.savefig(chart_path, dpi=170)
    plt.close(fig)
    return chart_path


def _plot_grid(curves: pd.DataFrame, comparison: pd.DataFrame, value_column: str, path: Path, title: str, ylabel: str) -> None:
    windows = comparison["window_id"].astype(str).tolist()
    fig, axes = plt.subplots(4, 2, figsize=(18, 18), sharex=False, constrained_layout=True)
    for ax, window_id in zip(axes.flatten(), windows, strict=True):
        row = comparison[comparison["window_id"].astype(str).eq(window_id)].iloc[0]
        data = curves[curves["window_id"].astype(str).eq(window_id)].copy()
        data["date"] = pd.to_datetime(data["date"], errors="coerce")
        for arm_key, group in data.groupby("arm_key", sort=False):
            arm_key = str(arm_key)
            group = group.sort_values("date")
            ax.plot(
                group["date"],
                pd.to_numeric(group[value_column], errors="coerce"),
                color=COLORS.get(arm_key, "#111827"),
                linewidth=1.25,
                label=ARM_LABELS.get(arm_key, arm_key),
            )
        if value_column == "rebased_nav":
            ax.axhline(1.0, color="#94a3b8", linewidth=0.7, linestyle="--")
        suffix = "T" if int(row["terminal_partial"]) == 1 else "3Y"
        ax.set_title(f"{row['start_month']} {suffix}: A {row['return_official_pct']:.0f}% / C9 {row['return_c9_pct']:.0f}%")
        ax.grid(True, linestyle="--", linewidth=0.4, alpha=0.32)
        ax.set_ylabel(ylabel)
    handles, labels = axes.flatten()[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2, frameon=False, bbox_to_anchor=(0.5, 1.01))
    fig.suptitle(title, fontsize=16)
    fig.savefig(path, dpi=170, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    curves = pd.read_csv(CURVES_PATH, encoding="utf-8-sig")
    comparison = pd.read_csv(COMPARISON_PATH, encoding="utf-8-sig").sort_values("window_start").reset_index(drop=True)

    chart_rows: list[dict[str, object]] = []
    for _, row in comparison.iterrows():
        window_id = str(row["window_id"])
        path = _plot_single_window(curves, comparison, window_id)
        chart_rows.append(
            {
                "window_id": window_id,
                "window_start": row["window_start"],
                "window_end": row["window_end"],
                "complete_3y": int(row["complete_3y"]),
                "terminal_partial": int(row["terminal_partial"]),
                "return_official_pct": _safe_float(row["return_official_pct"]),
                "return_c9_pct": _safe_float(row["return_c9_pct"]),
                "max_dd_official_pct": _safe_float(row["max_dd_official_pct"]),
                "max_dd_c9_pct": _safe_float(row["max_dd_c9_pct"]),
                "chart": str(path),
            }
        )

    _plot_grid(curves, comparison, "rebased_nav", NAV_GRID_PATH, "Stage896 all windows normalized NAV, start = 1", "NAV")
    _plot_grid(curves, comparison, "rebased_equity", EQUITY_GRID_PATH, "Stage896 all windows absolute equity", "Equity")

    chart_rows.append(
        {
            "window_id": "all_windows_nav_grid",
            "window_start": "",
            "window_end": "",
            "complete_3y": "",
            "terminal_partial": "",
            "return_official_pct": "",
            "return_c9_pct": "",
            "max_dd_official_pct": "",
            "max_dd_c9_pct": "",
            "chart": str(NAV_GRID_PATH),
        }
    )
    chart_rows.append(
        {
            "window_id": "all_windows_equity_grid",
            "window_start": "",
            "window_end": "",
            "complete_3y": "",
            "terminal_partial": "",
            "return_official_pct": "",
            "return_c9_pct": "",
            "max_dd_official_pct": "",
            "max_dd_c9_pct": "",
            "chart": str(EQUITY_GRID_PATH),
        }
    )
    pd.DataFrame(chart_rows).to_csv(MANIFEST_PATH, index=False, encoding="utf-8-sig")
    print(f"manifest={MANIFEST_PATH}")
    print(f"nav_grid={NAV_GRID_PATH}")
    print(f"equity_grid={EQUITY_GRID_PATH}")
    for item in chart_rows[: len(comparison)]:
        print(f"{item['window_id']} {item['chart']}")


if __name__ == "__main__":
    main()
