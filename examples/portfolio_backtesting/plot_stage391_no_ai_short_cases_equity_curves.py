from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
PLOT_DIR = OUTPUT_DIR / "stage391_equity_plots"
WINDOW_FULL = "full_2020_20260430"


@dataclass(frozen=True)
class StageFiles:
    stage: str
    curves: Path
    summary: Path


STAGES = {
    "S387": StageFiles(
        stage="S387 fixed+4",
        curves=OUTPUT_DIR
        / "qmt_roll_stage675_stage372_500k_trade_risk002_ni_ag_sc_p_curves_stage675_stage372_500k_trade_risk002_ni_ag_sc_p_v1.csv",
        summary=OUTPUT_DIR
        / "qmt_roll_stage675_stage372_500k_trade_risk002_ni_ag_sc_p_summary_stage675_stage372_500k_trade_risk002_ni_ag_sc_p_v1.csv",
    ),
    "S388": StageFiles(
        stage="S388 AI plus23",
        curves=OUTPUT_DIR
        / "qmt_roll_stage676_stage372_500k_trade_risk002_ai_plus23_curves_stage676_stage372_500k_trade_risk002_ai_plus23_v1.csv",
        summary=OUTPUT_DIR
        / "qmt_roll_stage676_stage372_500k_trade_risk002_ai_plus23_summary_stage676_stage372_500k_trade_risk002_ai_plus23_v1.csv",
    ),
    "S389": StageFiles(
        stage="S389 AI plus24 jd",
        curves=OUTPUT_DIR
        / "qmt_roll_stage677_stage372_500k_trade_risk002_ai_plus24_jd_curves_stage677_stage372_500k_trade_risk002_ai_plus24_jd_v1.csv",
        summary=OUTPUT_DIR
        / "qmt_roll_stage677_stage372_500k_trade_risk002_ai_plus24_jd_summary_stage677_stage372_500k_trade_risk002_ai_plus24_jd_v1.csv",
    ),
    "S390": StageFiles(
        stage="S390 noAI plus24 jd",
        curves=OUTPUT_DIR
        / "qmt_roll_stage678_stage372_500k_trade_risk002_no_ai_plus24_jd_curves_stage678_stage372_500k_trade_risk002_no_ai_plus24_jd_v1.csv",
        summary=OUTPUT_DIR
        / "qmt_roll_stage678_stage372_500k_trade_risk002_no_ai_plus24_jd_summary_stage678_stage372_500k_trade_risk002_no_ai_plus24_jd_v1.csv",
    ),
    "S391": StageFiles(
        stage="S391 noAI plus24 jd short123",
        curves=OUTPUT_DIR
        / "qmt_roll_stage679_stage372_500k_trade_risk002_no_ai_plus24_jd_short_cases123_curves_stage679_stage372_500k_trade_risk002_no_ai_plus24_jd_short_cases123_v1.csv",
        summary=OUTPUT_DIR
        / "qmt_roll_stage679_stage372_500k_trade_risk002_no_ai_plus24_jd_short_cases123_summary_stage679_stage372_500k_trade_risk002_no_ai_plus24_jd_short_cases123_v1.csv",
    ),
}


LABELS = {
    "stage372_500k_trade_risk004_plus_ni_ag_sc_p_maxpos4": "S387 A risk4 fixed+4",
    "stage372_500k_trade_risk002_plus_ni_ag_sc_p_maxpos4": "S387 C risk2 fixed+4",
    "stage372_500k_trade_risk002_plus_ni_ag_sc_p_maxpos23": "S387 C2 risk2 fixed+4 maxpos23",
    "stage372_500k_trade_risk004_ai_plus23_maxpos4": "S388 A risk4 AI plus23",
    "stage372_500k_trade_risk002_ai_plus23_maxpos4": "S388 C risk2 AI plus23",
    "stage372_500k_trade_risk004_ai_plus24_jd_maxpos4": "S389 A risk4 AI plus24 jd",
    "stage372_500k_trade_risk002_ai_plus24_jd_maxpos4": "S389 C risk2 AI plus24 jd",
    "stage372_500k_trade_risk004_no_ai_plus24_jd_maxpos4": "S390 A risk4 noAI plus24 jd",
    "stage372_500k_trade_risk002_no_ai_plus24_jd_maxpos4": "S390 C risk2 noAI plus24 jd",
    "stage372_500k_trade_risk002_no_ai_plus24_jd_maxpos24": "S390 C2 risk2 noAI maxpos24",
    "stage372_500k_trade_risk004_no_ai_plus24_jd_short_cases123_maxpos4": "S391 A risk4 noAI short123",
    "stage372_500k_trade_risk002_no_ai_plus24_jd_short_cases123_maxpos4": "S391 C risk2 noAI short123",
    "stage372_500k_trade_risk002_no_ai_plus24_jd_short_cases123_maxpos24": "S391 C2 risk2 noAI short123 maxpos24",
}


TARGET_C_VARIANTS = {
    "S387": "stage372_500k_trade_risk002_plus_ni_ag_sc_p_maxpos4",
    "S388": "stage372_500k_trade_risk002_ai_plus23_maxpos4",
    "S389": "stage372_500k_trade_risk002_ai_plus24_jd_maxpos4",
    "S390": "stage372_500k_trade_risk002_no_ai_plus24_jd_maxpos4",
    "S391": "stage372_500k_trade_risk002_no_ai_plus24_jd_short_cases123_maxpos4",
}

STAGE391_VARIANTS = [
    "stage372_500k_trade_risk004_no_ai_plus24_jd_short_cases123_maxpos4",
    "stage372_500k_trade_risk002_no_ai_plus24_jd_short_cases123_maxpos4",
    "stage372_500k_trade_risk002_no_ai_plus24_jd_short_cases123_maxpos24",
]

NO_AI_VARIANTS = {
    "S390": [
        "stage372_500k_trade_risk004_no_ai_plus24_jd_maxpos4",
        "stage372_500k_trade_risk002_no_ai_plus24_jd_maxpos4",
        "stage372_500k_trade_risk002_no_ai_plus24_jd_maxpos24",
    ],
    "S391": STAGE391_VARIANTS,
}

STAGE_VARIANTS = {
    "S387": [
        "stage372_500k_trade_risk004_plus_ni_ag_sc_p_maxpos4",
        "stage372_500k_trade_risk002_plus_ni_ag_sc_p_maxpos4",
        "stage372_500k_trade_risk002_plus_ni_ag_sc_p_maxpos23",
    ],
    "S388": [
        "stage372_500k_trade_risk004_ai_plus23_maxpos4",
        "stage372_500k_trade_risk002_ai_plus23_maxpos4",
    ],
    "S389": [
        "stage372_500k_trade_risk004_ai_plus24_jd_maxpos4",
        "stage372_500k_trade_risk002_ai_plus24_jd_maxpos4",
    ],
    "S390": NO_AI_VARIANTS["S390"],
    "S391": STAGE391_VARIANTS,
}


def _assert_inputs() -> None:
    missing: list[Path] = []
    for files in STAGES.values():
        for path in (files.curves, files.summary):
            if not path.exists():
                missing.append(path)
    if missing:
        formatted = "\n".join(str(path) for path in missing)
        raise FileNotFoundError(f"Missing backtest output files:\n{formatted}")


def _read_curves(stage_key: str) -> pd.DataFrame:
    frame = pd.read_csv(STAGES[stage_key].curves)
    frame["date"] = pd.to_datetime(frame["date"])
    return frame


def _read_summary(stage_key: str) -> pd.DataFrame:
    return pd.read_csv(STAGES[stage_key].summary)


def _label(variant: str) -> str:
    return LABELS.get(variant, variant)


def _row_value(row: pd.Series | dict[str, object], *names: str) -> object:
    for name in names:
        if isinstance(row, dict) and name in row:
            return row[name]
        if isinstance(row, pd.Series) and name in row.index:
            return row[name]
    return None


def _full_variant_curve(stage_key: str, variant: str) -> pd.DataFrame:
    frame = _read_curves(stage_key)
    filtered = frame[(frame["window_name"] == WINDOW_FULL) & (frame["variant"] == variant)].copy()
    if filtered.empty:
        raise ValueError(f"No full-window curve for {stage_key} {variant}")
    return filtered.sort_values("date")


def _metric_suffix(stage_key: str, variant: str) -> str:
    summary = _read_summary(stage_key)
    row = summary[(summary["window_name"] == WINDOW_FULL) & (summary["variant"] == variant)]
    if row.empty:
        return ""
    data = row.iloc[0]
    total_return = _row_value(data, "total_return_pct", "rebased_total_return_pct", "path_return_pct")
    max_dd = _row_value(data, "max_dd_percent", "rebased_max_dd_pct")
    sharpe = _row_value(data, "sharpe_ratio", "rebased_sharpe")
    if total_return is None or max_dd is None or sharpe is None:
        return ""
    return (
        f" | ret {float(total_return):.1f}%"
        f" DD {float(max_dd):.1f}%"
        f" Sh {float(sharpe):.2f}"
    )


def _plot_equity_and_drawdown(
    series: list[tuple[str, pd.DataFrame]],
    title: str,
    output_path: Path,
    use_nav: bool = False,
) -> None:
    fig, (ax_equity, ax_dd) = plt.subplots(
        2,
        1,
        figsize=(14, 9),
        sharex=True,
        gridspec_kw={"height_ratios": [2.3, 1.0]},
    )
    for label, frame in series:
        y_col = "rebased_nav" if use_nav else "rebased_equity"
        ax_equity.plot(frame["date"], frame[y_col], linewidth=1.4, label=label)
        ax_dd.plot(frame["date"], frame["drawdown_pct"], linewidth=1.0, label=label)

    ax_equity.set_title(title)
    ax_equity.set_ylabel("NAV" if use_nav else "Equity")
    ax_equity.grid(alpha=0.25)
    ax_equity.legend(fontsize=8, ncol=2)
    ax_dd.axhline(-30.0, color="#b00020", linestyle="--", linewidth=1.0, alpha=0.75, label="DD -30%")
    ax_dd.set_ylabel("Drawdown %")
    ax_dd.set_xlabel("Date")
    ax_dd.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def _plot_stage_facets() -> Path:
    output_path = PLOT_DIR / "stage387_to_391_all_cases_full_nav_facets.png"
    fig, axes = plt.subplots(3, 2, figsize=(15, 12), sharex=True)
    axes_flat = axes.flatten()
    for ax, stage_key in zip(axes_flat, STAGES.keys()):
        for variant in STAGE_VARIANTS[stage_key]:
            curve = _full_variant_curve(stage_key, variant)
            ax.plot(curve["date"], curve["rebased_nav"], linewidth=1.2, label=_label(variant))
        ax.set_title(STAGES[stage_key].stage)
        ax.set_ylabel("NAV")
        ax.grid(alpha=0.25)
        ax.legend(fontsize=7)
    axes_flat[-1].axis("off")
    for ax in axes_flat[-2:]:
        ax.set_xlabel("Date")
    fig.suptitle("Stage387-391 all available full-window cases", y=0.995)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
    return output_path


def _plot_stage391_windows() -> Path:
    output_path = PLOT_DIR / "stage391_c_all_windows_rebased_nav.png"
    variant = "stage372_500k_trade_risk002_no_ai_plus24_jd_short_cases123_maxpos4"
    frame = _read_curves("S391")
    frame = frame[frame["variant"] == variant].copy()
    order = [
        "full_2020_20260430",
        "since_2021",
        "since_2022",
        "since_2023",
        "since_2024",
        "since_2025",
        "since_2026_hist",
        "phase_2020_2021",
        "phase_2022_2023",
        "phase_2024_2025",
        "weak_2021_drawdown",
        "ytd_2026_latest_ai",
    ]
    available = [name for name in order if name in set(frame["window_name"])]
    cols = 3
    rows = (len(available) + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(16, 3.2 * rows))
    axes_flat = axes.flatten()
    for ax, window_name in zip(axes_flat, available):
        curve = frame[frame["window_name"] == window_name].sort_values("date")
        ax.plot(curve["date"], curve["rebased_nav"], linewidth=1.1, color="#2468a2")
        ax2 = ax.twinx()
        ax2.fill_between(curve["date"], curve["drawdown_pct"], 0, color="#b00020", alpha=0.12)
        ax.axhline(1.0, color="#333333", linewidth=0.6, alpha=0.5)
        ax.set_title(window_name)
        ax.set_ylabel("NAV")
        ax2.set_ylabel("DD %")
        ax.grid(alpha=0.2)
    for ax in axes_flat[len(available) :]:
        ax.axis("off")
    fig.suptitle("Stage391 C case: rebased equity curves by independent window", y=0.995)
    fig.tight_layout()
    fig.savefig(output_path, dpi=180)
    plt.close(fig)
    return output_path


def _write_metrics_snapshot() -> Path:
    rows: list[dict[str, object]] = []
    for stage_key, files in STAGES.items():
        summary = _read_summary(stage_key)
        for variant in STAGE_VARIANTS[stage_key]:
            row = summary[(summary["window_name"] == WINDOW_FULL) & (summary["variant"] == variant)]
            if row.empty:
                continue
            data = row.iloc[0].to_dict()
            rows.append(
                {
                    "stage": stage_key,
                    "label": _label(variant),
                    "variant": variant,
                    "end_balance": _row_value(data, "end_balance", "rebased_end_equity", "end_equity_path"),
                    "total_return_pct": _row_value(
                        data, "total_return_pct", "rebased_total_return_pct", "path_return_pct"
                    ),
                    "max_dd_percent": _row_value(data, "max_dd_percent", "rebased_max_dd_pct"),
                    "sharpe_ratio": _row_value(data, "sharpe_ratio", "rebased_sharpe"),
                    "total_slippage": data.get("total_slippage"),
                    "total_trade_count": data.get("total_trade_count"),
                    "win_rate_pct": _row_value(data, "win_rate_pct", "nonzero_daily_win_rate_pct"),
                    "source_summary": files.summary.name,
                }
            )
    path = PLOT_DIR / "stage387_to_391_full_window_metrics_snapshot.csv"
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")
    return path


def main() -> None:
    _assert_inputs()
    PLOT_DIR.mkdir(parents=True, exist_ok=True)

    outputs: list[dict[str, str]] = []

    series = []
    for variant in STAGE391_VARIANTS:
        series.append((_label(variant) + _metric_suffix("S391", variant), _full_variant_curve("S391", variant)))
    path = PLOT_DIR / "stage391_no_ai_short123_all_cases_full_equity_dd.png"
    _plot_equity_and_drawdown(series, "Stage391 no-AI short123: all cases, full window", path)
    outputs.append({"file": str(path), "description": "Stage391 A/C/C2 full-window equity and drawdown"})

    series = []
    for stage_key, variants in NO_AI_VARIANTS.items():
        for variant in variants:
            series.append((_label(variant) + _metric_suffix(stage_key, variant), _full_variant_curve(stage_key, variant)))
    path = PLOT_DIR / "stage390_vs_stage391_no_ai_all_cases_full_nav_dd.png"
    _plot_equity_and_drawdown(series, "No-AI plus24 jd: Stage390 vs Stage391 all cases", path, use_nav=True)
    outputs.append({"file": str(path), "description": "Stage390 vs Stage391 no-AI all full-window cases"})

    series = []
    for stage_key, variant in TARGET_C_VARIANTS.items():
        series.append((_label(variant) + _metric_suffix(stage_key, variant), _full_variant_curve(stage_key, variant)))
    path = PLOT_DIR / "stage387_to_391_target_c_full_nav_dd.png"
    _plot_equity_and_drawdown(series, "Stage387-391 target C variants, full window", path, use_nav=True)
    outputs.append({"file": str(path), "description": "Stage387-391 target risk2/maxpos4 C comparison"})

    path = _plot_stage_facets()
    outputs.append({"file": str(path), "description": "Facet view of all available full-window cases by stage"})

    path = _plot_stage391_windows()
    outputs.append({"file": str(path), "description": "Stage391 C rebased equity curves by independent window"})

    metrics_path = _write_metrics_snapshot()
    outputs.append({"file": str(metrics_path), "description": "Full-window metrics for plotted variants"})

    manifest_path = PLOT_DIR / "stage391_equity_plot_manifest.csv"
    pd.DataFrame(outputs).to_csv(manifest_path, index=False, encoding="utf-8-sig")
    print(f"Wrote {len(outputs)} plot/metadata files to {PLOT_DIR}")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
