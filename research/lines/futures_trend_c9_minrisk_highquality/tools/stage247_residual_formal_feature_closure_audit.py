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

import stage245_realized_volatility_counterexample_audit as shared


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage247"
MODEL_TAG = "stage247_residual_formal_feature_closure_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage247_c9_minrisk_residual_formal_feature_closure_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage247_residual_formal_feature_closure_audit"

CURVE_IN = shared.CURVE_IN
STAGE239_DIR = shared.STAGE239_DIR
STAGE239_PREFIX = shared.STAGE239_PREFIX
STAGE239_TAG = shared.STAGE239_TAG
FEATURE_SUMMARY_IN = STAGE239_DIR / f"{STAGE239_PREFIX}_feature_rank_correlation_audit_{STAGE239_TAG}.csv"
QUINTILE_IN = STAGE239_DIR / f"{STAGE239_PREFIX}_feature_quintile_audit_{STAGE239_TAG}.csv"
STABILITY_IN = STAGE239_DIR / f"{STAGE239_PREFIX}_feature_stability_audit_{STAGE239_TAG}.csv"

RESIDUAL_FEATURES = [
    "low_range_ratio_1m",
    "directional_efficiency_30m",
    "volume_participation_30m",
]

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
RESIDUAL_FEATURE_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_residual_feature_summary_{MODEL_TAG}.csv"
RESIDUAL_QUINTILE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_residual_quintile_summary_{MODEL_TAG}.csv"
RESIDUAL_STABILITY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_residual_stability_summary_{MODEL_TAG}.csv"
GATE_STATUS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_status_{MODEL_TAG}.csv"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_status_{MODEL_TAG}.png"
LABEL_GRID_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_residual_feature_label_rate_grid_{MODEL_TAG}.png"
HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_residual_feature_risk_tail_heatmap_{MODEL_TAG}.png"
DELTA_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_residual_feature_top_bottom_delta_{MODEL_TAG}.png"
STABILITY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_residual_feature_stability_matrix_{MODEL_TAG}.png"


def _read_csv(path: Path, required: bool = True) -> pd.DataFrame:
    return shared._read_csv(path, required=required)


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    shared._write_csv(frame, path)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    shared._write_json(path, payload)


def _json_safe(value: Any) -> Any:
    return shared._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return shared._md_table(frame, max_rows=max_rows)


def _load_curve() -> pd.DataFrame:
    return shared._load_curve()


def _prepare_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    feature_summary = _read_csv(FEATURE_SUMMARY_IN)
    quintile = _read_csv(QUINTILE_IN)
    stability = _read_csv(STABILITY_IN)
    residual_feature = feature_summary[feature_summary["audit_feature_id"].isin(RESIDUAL_FEATURES)].copy()
    residual_quintile = quintile[quintile["audit_feature_id"].isin(RESIDUAL_FEATURES)].copy()
    residual_stability = stability[stability["audit_feature_id"].isin(RESIDUAL_FEATURES)].copy()
    return residual_feature, residual_quintile, residual_stability, _load_curve()


def _feature_closure_summary(residual_feature: pd.DataFrame, residual_quintile: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for feature in RESIDUAL_FEATURES:
        fs = residual_feature[residual_feature["audit_feature_id"].eq(feature)]
        qs = residual_quintile[residual_quintile["audit_feature_id"].eq(feature)].copy()
        nonempty = qs[qs["row_count"].fillna(0).gt(0)]
        best_risk = nonempty.sort_values(["risk_bad_rate", "quality_quintile"], ascending=[True, True]).head(1)
        best_tail = nonempty.sort_values(["right_tail_rate", "quality_quintile"], ascending=[False, True]).head(1)
        q1 = qs[qs["quality_quintile"].eq(1)]
        q5 = qs[qs["quality_quintile"].eq(5)]
        row = {
            "audit_feature_id": feature,
            "feature_id": fs["feature_id"].iloc[0] if not fs.empty else "",
            "quality_unique_value_count": int(fs["quality_unique_value_count"].iloc[0]) if not fs.empty else 0,
            "nonempty_quality_quintile_count": int(fs["nonempty_quality_quintile_count"].iloc[0]) if not fs.empty else 0,
            "quality_rank_corr_vs_risk_bad": float(fs["quality_rank_corr_vs_risk_bad"].iloc[0]) if not fs.empty else np.nan,
            "quality_rank_corr_vs_right_tail": float(fs["quality_rank_corr_vs_right_tail"].iloc[0]) if not fs.empty else np.nan,
            "q5_minus_q1_risk_bad_rate": float(fs["q5_minus_q1_risk_bad_rate"].iloc[0]) if not fs.empty and pd.notna(fs["q5_minus_q1_risk_bad_rate"].iloc[0]) else np.nan,
            "q5_minus_q1_right_tail_rate": float(fs["q5_minus_q1_right_tail_rate"].iloc[0]) if not fs.empty and pd.notna(fs["q5_minus_q1_right_tail_rate"].iloc[0]) else np.nan,
            "year_risk_good_split_share": float(fs["year_risk_good_split_share"].iloc[0]) if not fs.empty else np.nan,
            "exchange_risk_good_split_share": float(fs["exchange_risk_good_split_share"].iloc[0]) if not fs.empty else np.nan,
            "universal_structure_watch_only": int(fs["universal_structure_watch_only"].iloc[0]) if not fs.empty else 0,
            "best_risk_quintile": int(best_risk["quality_quintile"].iloc[0]) if not best_risk.empty else 0,
            "best_risk_bad_rate": float(best_risk["risk_bad_rate"].iloc[0]) if not best_risk.empty else np.nan,
            "best_risk_row_count": int(best_risk["row_count"].iloc[0]) if not best_risk.empty else 0,
            "best_tail_quintile": int(best_tail["quality_quintile"].iloc[0]) if not best_tail.empty else 0,
            "best_tail_rate": float(best_tail["right_tail_rate"].iloc[0]) if not best_tail.empty else np.nan,
            "best_tail_row_count": int(best_tail["row_count"].iloc[0]) if not best_tail.empty else 0,
            "q1_row_count": int(q1["row_count"].iloc[0]) if not q1.empty else 0,
            "q5_row_count": int(q5["row_count"].iloc[0]) if not q5.empty else 0,
            "closure_decision": "close_no_true_engine",
            "stage247_strategy_rule_allowed": 0,
        }
        if feature == "low_range_ratio_1m":
            row["closure_reason"] = "ties_make_quintiles_unstable_and_q5_does_not_reduce_risk"
        elif feature == "directional_efficiency_30m":
            row["closure_reason"] = "highest_efficiency_q5_has_risk_rebound_and_no_tail_edge"
        else:
            row["closure_reason"] = "only_two_nonempty_quintiles_and_no_ranking_power"
        rows.append(row)
    return pd.DataFrame(rows)


def _build_gate_status(summary: dict[str, Any]) -> pd.DataFrame:
    gates = [
        ("feature_summary_exists", FEATURE_SUMMARY_IN.exists(), "Stage239 feature summary exists"),
        ("quintile_exists", QUINTILE_IN.exists(), "Stage239 quintile audit exists"),
        ("stability_exists", STABILITY_IN.exists(), "Stage239 stability audit exists"),
        ("curve_exists", CURVE_IN.exists(), "official curve exists"),
        ("residual_feature_count_3", summary["residual_feature_count"] == 3, "three residual formal features reviewed"),
        ("all_residual_watch_only_zero", summary["residual_watch_only_count"] == 0, "no residual feature passed Stage239 watch-only"),
        ("volume_participation_sparse", summary["volume_participation_nonempty_quintile_count"] == 2, "volume participation has only two nonempty quintiles"),
        ("directional_efficiency_q5_risk_rebound", summary["directional_efficiency_q5_risk_bad_rate"] > summary["directional_efficiency_q4_risk_bad_rate"], "directional efficiency Q5 risk rebounds"),
        ("range_ratio_tie_unstable", summary["range_ratio_q5_row_count"] > 60 and summary["range_ratio_q4_row_count"] < 20, "range ratio quintiles are tie-skewed"),
        ("strategy_rule_created", False, "no strategy rule created"),
        ("true_engine_run", False, "no true engine run"),
        ("ab_triggered", False, "no A/B triggered"),
        ("official_config_changed", False, "official config untouched"),
        ("order_api_called", False, "no order API call"),
    ]
    return pd.DataFrame([{"gate_id": gate_id, "pass": int(bool(passed)), "description": description} for gate_id, passed, description in gates])


def _plot_official_path(curve: pd.DataFrame, summary: dict[str, Any]) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(13, 7), sharex=True)
    axes[0].plot(curve["date"], curve["account_equity"], color="#1f77b4", linewidth=1.5)
    axes[0].set_title("Official path unchanged; Stage247 closes residual formal features")
    axes[0].set_ylabel("equity")
    axes[0].grid(alpha=0.25)
    axes[1].plot(curve["date"], curve["drawdown_pct"], color="#d62728", linewidth=1.1)
    axes[1].fill_between(curve["date"], curve["drawdown_pct"], 0, color="#d62728", alpha=0.12)
    axes[1].set_ylabel("drawdown pct")
    axes[1].grid(alpha=0.25)
    text = (
        f"residual_features=3 watch_only=0 | "
        f"range Q5 n={summary['range_ratio_q5_row_count']} | "
        f"eff Q5 risk={summary['directional_efficiency_q5_risk_bad_rate']:.3f} | true_engine=0"
    )
    axes[0].text(0.01, 0.93, text, transform=axes[0].transAxes, fontsize=10, va="top")
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_label_grid(quintile: pd.DataFrame) -> None:
    fig, axes = plt.subplots(len(RESIDUAL_FEATURES), 1, figsize=(12, 10), sharex=True)
    for ax, feature in zip(axes, RESIDUAL_FEATURES):
        data = quintile[quintile["audit_feature_id"].eq(feature)].sort_values("quality_quintile")
        x = np.arange(len(data))
        width = 0.24
        ax.bar(x - width, data["risk_bad_rate"], width, label="risk_bad", color="#d62728")
        ax.bar(x, data["right_tail_rate"], width, label="right_tail", color="#2ca02c")
        ax.bar(x + width, data["low_resolution_rate"], width, label="low_resolution", color="#ff7f0e")
        ax.set_title(feature)
        ax.set_ylabel("rate")
        ax.grid(axis="y", alpha=0.25)
        for idx, row in data.reset_index(drop=True).iterrows():
            values = [row["risk_bad_rate"], row["right_tail_rate"], row["low_resolution_rate"]]
            ymax = np.nanmax(values) if np.isfinite(values).any() else 0
            ax.text(idx, ymax + 0.025, f"n={int(row['row_count'])}", ha="center", fontsize=8)
    axes[-1].set_xticks(np.arange(5))
    axes[-1].set_xticklabels(["Q1", "Q2", "Q3", "Q4", "Q5"])
    axes[0].legend(loc="best")
    fig.suptitle("Residual formal features: label rates by fixed quality quintile", fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(LABEL_GRID_OUT, dpi=160)
    plt.close(fig)


def _plot_heatmap(quintile: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8))
    for ax, value_col, title, cmap in [
        (axes[0], "risk_bad_rate", "risk_bad_rate", "Reds"),
        (axes[1], "right_tail_rate", "right_tail_rate", "Greens"),
    ]:
        pivot = quintile.pivot(index="audit_feature_id", columns="quality_quintile", values=value_col).reindex(RESIDUAL_FEATURES)
        count = quintile.pivot(index="audit_feature_id", columns="quality_quintile", values="row_count").reindex(RESIDUAL_FEATURES)
        data = pivot.to_numpy(dtype=float)
        vmax = max(0.35, np.nanmax(data) if np.isfinite(data).any() else 0.35)
        image = ax.imshow(np.ma.masked_invalid(data), aspect="auto", cmap=cmap, vmin=0, vmax=vmax)
        ax.set_xticks(np.arange(5))
        ax.set_xticklabels(["Q1", "Q2", "Q3", "Q4", "Q5"])
        ax.set_yticks(np.arange(len(RESIDUAL_FEATURES)))
        ax.set_yticklabels(RESIDUAL_FEATURES, fontsize=8)
        ax.set_title(title)
        for y in range(data.shape[0]):
            for x in range(data.shape[1]):
                value = data[y, x]
                n = int(count.to_numpy()[y, x]) if np.isfinite(count.to_numpy()[y, x]) else 0
                if np.isfinite(value):
                    ax.text(x, y, f"{value:.2f}\nn={n}", ha="center", va="center", fontsize=7)
        fig.colorbar(image, ax=ax, fraction=0.035, pad=0.03)
    fig.tight_layout()
    fig.savefig(HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _plot_delta(feature_summary: pd.DataFrame) -> None:
    data = feature_summary.set_index("audit_feature_id").reindex(RESIDUAL_FEATURES)
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8))
    x = np.arange(len(data))
    width = 0.34
    axes[0].bar(x - width / 2, data["q5_minus_q1_risk_bad_rate"], width, color="#d62728", label="risk Q5-Q1")
    axes[0].bar(x + width / 2, data["q5_minus_q1_right_tail_rate"], width, color="#2ca02c", label="tail Q5-Q1")
    axes[0].axhline(0, color="#111111", linewidth=0.8)
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(RESIDUAL_FEATURES, rotation=20, ha="right", fontsize=8)
    axes[0].set_title("Top-bottom label deltas")
    axes[0].grid(axis="y", alpha=0.25)
    axes[0].legend(loc="best")
    axes[1].bar(x - width / 2, data["quality_unique_value_count"], width, color="#1f77b4", label="unique values")
    axes[1].bar(x + width / 2, data["nonempty_quality_quintile_count"], width, color="#ff7f0e", label="nonempty quintiles")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(RESIDUAL_FEATURES, rotation=20, ha="right", fontsize=8)
    axes[1].set_title("Ranking capacity")
    axes[1].grid(axis="y", alpha=0.25)
    axes[1].legend(loc="best")
    fig.tight_layout()
    fig.savefig(DELTA_OUT, dpi=160)
    plt.close(fig)


def _plot_stability(feature_summary: pd.DataFrame) -> None:
    cols = [
        "year_risk_good_split_share",
        "year_tail_good_split_share",
        "exchange_risk_good_split_share",
        "exchange_tail_good_split_share",
        "direction_risk_good_split_share",
        "direction_tail_good_split_share",
    ]
    pivot = feature_summary.set_index("audit_feature_id").reindex(RESIDUAL_FEATURES)[cols]
    fig, ax = plt.subplots(figsize=(10.5, 4.6))
    data = pivot.to_numpy(dtype=float)
    image = ax.imshow(np.ma.masked_invalid(data), aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_xticks(np.arange(len(cols)))
    ax.set_xticklabels([c.replace("_good_split_share", "") for c in cols], rotation=25, ha="right", fontsize=8)
    ax.set_yticks(np.arange(len(RESIDUAL_FEATURES)))
    ax.set_yticklabels(RESIDUAL_FEATURES, fontsize=8)
    ax.set_title("Residual feature split-good share from Stage239")
    for y in range(data.shape[0]):
        for x in range(data.shape[1]):
            value = data[y, x]
            if np.isfinite(value):
                ax.text(x, y, f"{value:.2f}", ha="center", va="center", fontsize=8)
    fig.colorbar(image, ax=ax, fraction=0.035, pad=0.03)
    fig.tight_layout()
    fig.savefig(STABILITY_OUT, dpi=160)
    plt.close(fig)


def _write_report(
    summary: dict[str, Any],
    residual_feature_summary: pd.DataFrame,
    residual_quintile: pd.DataFrame,
    residual_stability: pd.DataFrame,
    gate_status: pd.DataFrame,
) -> None:
    lines = [
        "# Stage247 Residual Formal Feature Closure Audit",
        "",
        "## Decision",
        "",
        f"- decision: `{summary['decision']}`",
        f"- residual_feature_count: `{summary['residual_feature_count']}`",
        f"- residual_watch_only_count: `{summary['residual_watch_only_count']}`",
        f"- closed_feature_count: `{summary['closed_feature_count']}`",
        "- strategy_rule_created: `0`",
        "- true_engine_run: `0`",
        "- ab_triggered: `0`",
        "",
        "## Method",
        "",
        "- Use Stage239 feature summary, quintile audit, and stability audit.",
        "- Review only residual non-watch formal features: `low_range_ratio_1m`, `directional_efficiency_30m`, `volume_participation_30m`.",
        "- No new thresholds, no true engine, no A/B, no official config changes.",
        "",
        "## Residual Feature Summary",
        "",
        _md_table(residual_feature_summary),
        "",
        "## Residual Quintile Summary",
        "",
        _md_table(residual_quintile),
        "",
        "## Residual Stability Sample",
        "",
        _md_table(residual_stability, max_rows=18),
        "",
        "## Gate Status",
        "",
        _md_table(gate_status),
        "",
        "## Visuals",
        "",
        f"- `{PATH_CHART_OUT.relative_to(REPO_DIR)}`",
        f"- `{LABEL_GRID_OUT.relative_to(REPO_DIR)}`",
        f"- `{HEATMAP_OUT.relative_to(REPO_DIR)}`",
        f"- `{DELTA_OUT.relative_to(REPO_DIR)}`",
        f"- `{STABILITY_OUT.relative_to(REPO_DIR)}`",
        "",
    ]
    REPORT_OUT.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    residual_feature, residual_quintile, residual_stability, curve = _prepare_inputs()
    residual_feature_summary = _feature_closure_summary(residual_feature, residual_quintile)

    range_q4 = residual_quintile.query("audit_feature_id == 'low_range_ratio_1m' and quality_quintile == 4")
    range_q5 = residual_quintile.query("audit_feature_id == 'low_range_ratio_1m' and quality_quintile == 5")
    eff_q4 = residual_quintile.query("audit_feature_id == 'directional_efficiency_30m' and quality_quintile == 4")
    eff_q5 = residual_quintile.query("audit_feature_id == 'directional_efficiency_30m' and quality_quintile == 5")
    vol_part_row = residual_feature_summary[residual_feature_summary["audit_feature_id"].eq("volume_participation_30m")]

    decision = "stage247_residual_formal_features_closed_no_true_engine_no_rule"
    summary: dict[str, Any] = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "run_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": decision,
        "residual_feature_count": int(len(residual_feature_summary)),
        "residual_watch_only_count": int(residual_feature_summary["universal_structure_watch_only"].sum()),
        "closed_feature_count": int(residual_feature_summary["closure_decision"].eq("close_no_true_engine").sum()),
        "range_ratio_q4_row_count": int(range_q4["row_count"].iloc[0]),
        "range_ratio_q5_row_count": int(range_q5["row_count"].iloc[0]),
        "range_ratio_q5_risk_bad_rate": float(range_q5["risk_bad_rate"].iloc[0]),
        "range_ratio_q5_right_tail_rate": float(range_q5["right_tail_rate"].iloc[0]),
        "directional_efficiency_q4_risk_bad_rate": float(eff_q4["risk_bad_rate"].iloc[0]),
        "directional_efficiency_q5_risk_bad_rate": float(eff_q5["risk_bad_rate"].iloc[0]),
        "directional_efficiency_q5_right_tail_rate": float(eff_q5["right_tail_rate"].iloc[0]),
        "volume_participation_nonempty_quintile_count": int(vol_part_row["nonempty_quality_quintile_count"].iloc[0]),
        "strategy_feature_usable": 0,
        "strategy_rule_created": 0,
        "true_engine_run": 0,
        "ab_triggered": 0,
        "official_config_changed": 0,
        "ctp_or_simnow_connected": 0,
        "order_api_called": 0,
        "official_curve_initial_equity": float(curve["account_equity"].iloc[0]),
        "official_curve_final_equity": float(curve["account_equity"].iloc[-1]),
        "official_curve_total_return_pct": float((curve["account_equity"].iloc[-1] / curve["account_equity"].iloc[0] - 1) * 100),
        "official_curve_max_drawdown_pct": float(curve["drawdown_pct"].min()),
        "official_curve_broker10_peak_pct": float(curve["broker10_margin_to_equity_pct"].max()),
        "visual_file_count": 5,
    }

    gate_status = _build_gate_status(summary)
    _plot_official_path(curve, summary)
    _plot_label_grid(residual_quintile)
    _plot_heatmap(residual_quintile)
    _plot_delta(residual_feature)
    _plot_stability(residual_feature)

    _write_csv(pd.DataFrame([summary]), SUMMARY_OUT)
    _write_json(DECISION_OUT, summary)
    _write_csv(residual_feature_summary, RESIDUAL_FEATURE_SUMMARY_OUT)
    _write_csv(residual_quintile, RESIDUAL_QUINTILE_OUT)
    _write_csv(residual_stability, RESIDUAL_STABILITY_OUT)
    _write_csv(gate_status, GATE_STATUS_OUT)
    _write_report(summary, residual_feature_summary, residual_quintile, residual_stability, gate_status)
    print(json.dumps(_json_safe(summary), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
