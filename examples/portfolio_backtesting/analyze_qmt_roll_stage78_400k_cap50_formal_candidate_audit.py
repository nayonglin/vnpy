from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage122_stage78_cap50_single25_formal_candidate_audit_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage78_cap50_single25_formal_candidate_audit"
PROFILE_NAME: str = "stage78_cap50_single25"
STAGE111_NAME: str = "stage111_400k_margin_safe_reference"
CAPITAL: float = 400_000.0
MARGIN_REDLINE_PCT: float = 80.0

STAGE119_FULL_COMPARISON_PATH: Path = (
    OUTPUT_DIR
    / "qmt_roll_stage78_400k_margin_profile_surface_full_comparison_"
    "stage119_stage78_400k_margin_profile_surface_v1.csv"
)
STAGE119_HORIZON_COMPARISON_PATH: Path = (
    OUTPUT_DIR
    / "qmt_roll_stage78_400k_margin_profile_surface_horizon_comparison_"
    "stage119_stage78_400k_margin_profile_surface_v1.csv"
)
STAGE119_HORIZON_SUMMARY_PATH: Path = (
    OUTPUT_DIR
    / "qmt_roll_stage78_400k_margin_profile_surface_horizon_summary_"
    "stage119_stage78_400k_margin_profile_surface_v1.csv"
)
STAGE120_FULL_COMPARISON_PATH: Path = (
    OUTPUT_DIR
    / "qmt_roll_stage78_400k_decoupled_margin_surface_full_comparison_"
    "stage120_stage78_400k_decoupled_margin_surface_v1.csv"
)

FULL_SELECTED_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_full_selected_{MODEL_TAG}.csv"
HORIZON_SELECTED_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_selected_{MODEL_TAG}.csv"
SAFETY_STRESS_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_safety_stress_{MODEL_TAG}.csv"
SLIPPAGE_STRESS_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_slippage_stress_{MODEL_TAG}.csv"
GATE_DECISION_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_decision_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _to_markdown_table(df: pd.DataFrame, columns: list[str], max_rows: int = 40) -> str:
    if df.empty:
        return "_No rows._"
    view = df.loc[:, [column for column in columns if column in df.columns]].head(max_rows).copy()
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda value: f"{value:.4f}")
    return "\n".join(
        [
            "| " + " | ".join(view.columns) + " |",
            "| " + " | ".join(["---"] * len(view.columns)) + " |",
            *["| " + " | ".join(map(str, row)) + " |" for row in view.to_numpy()],
        ]
    )


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(str(path))
    return pd.read_csv(path)


def _build_full_selected() -> pd.DataFrame:
    full119 = _load_csv(STAGE119_FULL_COMPARISON_PATH)
    full120 = _load_csv(STAGE120_FULL_COMPARISON_PATH)
    selected_names = [
        STAGE111_NAME,
        "stage78_cap45_single20",
        PROFILE_NAME,
        "stage78_cap55_single25",
    ]
    frames = []
    for frame in (full119, full120):
        frames.append(frame[frame["profile_name"].astype(str).isin(selected_names)].copy())
    selected = pd.concat(frames, ignore_index=True, sort=False)
    selected = selected.drop_duplicates(subset=["profile_name"], keep="last")
    order = {name: index for index, name in enumerate(selected_names)}
    selected["_order"] = selected["profile_name"].map(order).fillna(999)
    selected.sort_values("_order", inplace=True)
    selected.drop(columns=["_order"], inplace=True)
    return selected


def _build_horizon_selected() -> pd.DataFrame:
    comparison = _load_csv(STAGE119_HORIZON_COMPARISON_PATH)
    selected = comparison[comparison["profile_name"].astype(str).isin([STAGE111_NAME, PROFILE_NAME])].copy()
    selected.sort_values(["horizon", "profile_name"], inplace=True)
    return selected


def _build_safety_stress(horizon_selected: pd.DataFrame) -> pd.DataFrame:
    profile = horizon_selected[horizon_selected["profile_name"].astype(str).eq(PROFILE_NAME)].copy()
    rows: list[dict[str, Any]] = []
    for _, row in profile.iterrows():
        max_margin = float(row.get("max_margin_to_balance_pct", 0.0) or 0.0)
        for stress_type, values in {
            "margin_multiplier": (1.001, 1.005, 1.01, 1.03, 1.05, 1.10),
            "equity_haircut_pct": (0.1, 0.5, 1.0, 3.0, 5.0, 10.0),
        }.items():
            for value in values:
                if stress_type == "margin_multiplier":
                    stressed = max_margin * value
                    label_value = value
                else:
                    stressed = max_margin / max(1.0 - value / 100.0, 1e-9)
                    label_value = value
                rows.append(
                    {
                        "profile_name": PROFILE_NAME,
                        "horizon": row["horizon"],
                        "base_max_margin_to_balance_pct": max_margin,
                        "stress_type": stress_type,
                        "stress_value": label_value,
                        "stressed_max_margin_to_balance_pct": stressed,
                        "breaks_80pct": int(stressed > MARGIN_REDLINE_PCT),
                        "buffer_to_80pct_pp": MARGIN_REDLINE_PCT - max_margin,
                        "relative_buffer_to_80pct_pct": (MARGIN_REDLINE_PCT / max_margin - 1.0) * 100.0
                        if max_margin > 0
                        else np.nan,
                    }
                )
    return pd.DataFrame(rows)


def _build_slippage_stress() -> pd.DataFrame:
    horizon_summary = _load_csv(STAGE119_HORIZON_SUMMARY_PATH)
    profile = horizon_summary[
        horizon_summary["profile_name"].astype(str).eq(PROFILE_NAME)
        & horizon_summary["complete_horizon"].astype(bool)
    ].copy()
    rows: list[dict[str, Any]] = []
    for multiplier in (1.0, 1.5, 2.0, 3.0):
        stressed = profile.copy()
        extra_slippage = (multiplier - 1.0) * pd.to_numeric(stressed["total_slippage"], errors="coerce").fillna(0.0)
        stressed["stressed_total_return_pct"] = (
            pd.to_numeric(stressed["total_return_pct"], errors="coerce").fillna(0.0) - extra_slippage / CAPITAL * 100.0
        )
        aggregate = (
            stressed.groupby("horizon", as_index=False)
            .agg(
                window_count=("window_name", "count"),
                positive_return_count=("stressed_total_return_pct", lambda s: int((s > 0).sum())),
                median_return_pct=("stressed_total_return_pct", "median"),
                worst_return_pct=("stressed_total_return_pct", "min"),
                median_slippage=("total_slippage", "median"),
            )
            .sort_values("horizon")
        )
        aggregate["positive_return_rate_pct"] = aggregate["positive_return_count"] / aggregate["window_count"] * 100.0
        aggregate["slippage_multiplier"] = multiplier
        rows.extend(aggregate.to_dict(orient="records"))
    return pd.DataFrame(rows)


def _build_gate_decision(full_selected: pd.DataFrame, horizon_selected: pd.DataFrame, safety_stress: pd.DataFrame) -> pd.DataFrame:
    stage111_full = full_selected[full_selected["profile_name"].astype(str).eq(STAGE111_NAME)].iloc[0]
    cap50_full = full_selected[full_selected["profile_name"].astype(str).eq(PROFILE_NAME)].iloc[0]
    stage111_h = horizon_selected[horizon_selected["profile_name"].astype(str).eq(STAGE111_NAME)].copy()
    cap50_h = horizon_selected[horizon_selected["profile_name"].astype(str).eq(PROFILE_NAME)].copy()

    cap50_63 = cap50_h[cap50_h["horizon"].astype(str).eq("63d")].iloc[0]
    stage111_63 = stage111_h[stage111_h["horizon"].astype(str).eq("63d")].iloc[0]
    cap50_126 = cap50_h[cap50_h["horizon"].astype(str).eq("126d")].iloc[0]
    stage111_126 = stage111_h[stage111_h["horizon"].astype(str).eq("126d")].iloc[0]

    max_stressed_5pct_margin = safety_stress[
        (safety_stress["stress_type"].eq("margin_multiplier")) & (safety_stress["stress_value"].eq(1.05))
    ]["stressed_max_margin_to_balance_pct"].max()
    max_stressed_5pct_equity = safety_stress[
        (safety_stress["stress_type"].eq("equity_haircut_pct")) & (safety_stress["stress_value"].eq(5.0))
    ]["stressed_max_margin_to_balance_pct"].max()

    rows = [
        {
            "gate": "margin_safety_buffer",
            "pass": bool(max_stressed_5pct_margin <= MARGIN_REDLINE_PCT and max_stressed_5pct_equity <= MARGIN_REDLINE_PCT),
            "value": max(max_stressed_5pct_margin, max_stressed_5pct_equity),
            "threshold": MARGIN_REDLINE_PCT,
            "judgement": "5%保证金上浮和5%权益误差后仍不破80%",
        },
        {
            "gate": "full_return_premium_vs_stage111",
            "pass": bool(float(cap50_full["total_return_pct"]) - float(stage111_full["total_return_pct"]) >= 100.0),
            "value": float(cap50_full["total_return_pct"]) - float(stage111_full["total_return_pct"]),
            "threshold": 100.0,
            "judgement": "替换正式版本至少需要明显收益溢价",
        },
        {
            "gate": "sharpe_not_worse_than_stage111",
            "pass": bool(float(cap50_full["sharpe_ratio"]) >= float(stage111_full["sharpe_ratio"])),
            "value": float(cap50_full["sharpe_ratio"]) - float(stage111_full["sharpe_ratio"]),
            "threshold": 0.0,
            "judgement": "保守正式候选不应牺牲Sharpe",
        },
        {
            "gate": "short_window_not_worse_than_stage111",
            "pass": bool(
                float(cap50_63["positive_return_rate_pct"]) >= float(stage111_63["positive_return_rate_pct"])
                and float(cap50_63["worst_return_pct"]) >= float(stage111_63["worst_return_pct"])
                and float(cap50_126["worst_return_pct"]) >= float(stage111_126["worst_return_pct"])
            ),
            "value": float(cap50_63["worst_return_pct"]) - float(stage111_63["worst_return_pct"]),
            "threshold": 0.0,
            "judgement": "短窗口不能比Stage111更脆",
        },
    ]
    decision = pd.DataFrame(rows)
    formal = bool(decision["pass"].all())
    decision.loc[len(decision)] = {
        "gate": "formal_candidate",
        "pass": formal,
        "value": float(decision["pass"].sum()),
        "threshold": float(len(rows)),
        "judgement": "全部通过才允许固化为正式候选",
    }
    return decision


def _build_report(
    full_selected: pd.DataFrame,
    horizon_selected: pd.DataFrame,
    safety_stress: pd.DataFrame,
    slippage_stress: pd.DataFrame,
    gate_decision: pd.DataFrame,
) -> str:
    tight_safety = safety_stress[
        (
            (safety_stress["stress_type"].eq("margin_multiplier") & safety_stress["stress_value"].isin([1.05, 1.10]))
            | (safety_stress["stress_type"].eq("equity_haircut_pct") & safety_stress["stress_value"].isin([5.0, 10.0]))
        )
    ].copy()
    return "\n".join(
        [
            "# Stage122 Stage78 Cap50 Single25 Formal Candidate Audit",
            "",
            "## Full Selected",
            "",
            _to_markdown_table(
                full_selected,
                [
                    "profile_name",
                    "total_return_pct",
                    "max_dd_percent",
                    "sharpe_ratio",
                    "total_slippage",
                    "total_trade_count",
                    "win_ratio_pct",
                    "max_margin_to_balance_pct",
                ],
            ),
            "",
            "## Horizon Selected",
            "",
            _to_markdown_table(
                horizon_selected,
                [
                    "profile_name",
                    "horizon",
                    "positive_return_rate_pct",
                    "median_return_pct",
                    "worst_return_pct",
                    "worst_max_dd_percent",
                    "max_margin_to_balance_pct",
                    "windows_margin_gt_80pct",
                    "windows_margin_gt_100pct",
                ],
            ),
            "",
            "## Safety Stress",
            "",
            _to_markdown_table(
                tight_safety,
                [
                    "horizon",
                    "stress_type",
                    "stress_value",
                    "base_max_margin_to_balance_pct",
                    "stressed_max_margin_to_balance_pct",
                    "breaks_80pct",
                    "buffer_to_80pct_pp",
                    "relative_buffer_to_80pct_pct",
                ],
            ),
            "",
            "## Slippage Stress",
            "",
            _to_markdown_table(
                slippage_stress,
                [
                    "slippage_multiplier",
                    "horizon",
                    "positive_return_rate_pct",
                    "median_return_pct",
                    "worst_return_pct",
                ],
            ),
            "",
            "## Gate Decision",
            "",
            _to_markdown_table(gate_decision, ["gate", "pass", "value", "threshold", "judgement"]),
            "",
            "## Judgement",
            "",
            "- Cap50/single25 has enough margin safety buffer.",
            "- It does not have enough performance edge to replace Stage111 as a formal version.",
            "- Keep it as a conservative research reference, not as a frozen formal strategy.",
        ]
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    full_selected = _build_full_selected()
    horizon_selected = _build_horizon_selected()
    safety_stress = _build_safety_stress(horizon_selected)
    slippage_stress = _build_slippage_stress()
    gate_decision = _build_gate_decision(full_selected, horizon_selected, safety_stress)

    full_selected.to_csv(FULL_SELECTED_PATH, index=False, encoding="utf-8-sig")
    horizon_selected.to_csv(HORIZON_SELECTED_PATH, index=False, encoding="utf-8-sig")
    safety_stress.to_csv(SAFETY_STRESS_PATH, index=False, encoding="utf-8-sig")
    slippage_stress.to_csv(SLIPPAGE_STRESS_PATH, index=False, encoding="utf-8-sig")
    gate_decision.to_csv(GATE_DECISION_PATH, index=False, encoding="utf-8-sig")

    summary = {
        "model_tag": MODEL_TAG,
        "profile_name": PROFILE_NAME,
        "formal_candidate": bool(
            gate_decision[gate_decision["gate"].astype(str).eq("formal_candidate")]["pass"].iloc[0]
        ),
        "passed_gates": int(gate_decision[gate_decision["gate"].astype(str).ne("formal_candidate")]["pass"].sum()),
        "total_gates": int(gate_decision[gate_decision["gate"].astype(str).ne("formal_candidate")].shape[0]),
        "output_paths": {
            "full_selected": str(FULL_SELECTED_PATH),
            "horizon_selected": str(HORIZON_SELECTED_PATH),
            "safety_stress": str(SAFETY_STRESS_PATH),
            "slippage_stress": str(SLIPPAGE_STRESS_PATH),
            "gate_decision": str(GATE_DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }
    SUMMARY_JSON_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(
        _build_report(full_selected, horizon_selected, safety_stress, slippage_stress, gate_decision),
        encoding="utf-8",
    )

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"[stage122-cap50-formal-audit] report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
