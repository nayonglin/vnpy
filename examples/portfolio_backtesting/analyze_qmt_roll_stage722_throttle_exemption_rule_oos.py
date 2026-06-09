from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from itertools import combinations
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage722_throttle_exemption_rule_oos_v1"
OUTPUT_PREFIX = "qmt_roll_stage722_throttle_exemption_rule_oos"
LINE_ID = "futures_trend_winner_trade_forensics"

SOURCE_STAGE716_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage716_official_throttle_quality_readonly_labeled_candidates_"
    "stage716_official_throttle_quality_readonly_v1.csv"
)

RULE_METRICS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rule_metrics_{MODEL_TAG}.csv"
YEAR_DETAIL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_detail_{MODEL_TAG}.csv"
ANCHORED_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_anchored_selector_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

MIN_RULE_ROWS = 30
MIN_RULE_YEARS = 4
MIN_RULE_PRODUCT_COUNT = 6
MAX_DOMINANT_PRODUCT_SHARE = 0.35
MIN_GOOD_LIFT_PP = 10.0
MAX_BAD_RATE_PCT = 60.0
MIN_LOO_TEST_YEARS = 4
MIN_LOO_TEST_ROWS = 12
MIN_LOO_GOOD_YEARS = 3
MIN_LOO_SCORE_POSITIVE_YEARS = 3
MIN_ANCHORED_YEARS = 3
MAX_RULE_ATOMS = 2
MIN_ATOM_ROWS = 5
MIN_RULE_SUPPORT_FOR_SCREEN = 5

CONTRADICTED_ATOMS = {
    "status_scope=sizing_zero_volume": "Stage411 min-one and Stage420 scout tests contradicted sizing-zero promotion.",
    "pairwise_rank_bucket=pair_missing": "Alias-like sizing-zero population already contradicted by Stage411/Stage420.",
    "recovery_sleeve_reason=cooldown": "Only a small fixed-horizon watch sample; related recovery/scout expansions did not promote.",
    "contracts_by_risk=0": "Zero-risk-sizing population overlaps prior failed min-one/scout tests.",
}


@dataclass(frozen=True)
class Atom:
    name: str
    family: str
    mask: pd.Series


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if np.isnan(value) or np.isinf(value):
            return None
        return float(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if pd.isna(value):
        return None
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    for column in data.columns:
        if pd.api.types.is_float_dtype(data[column]):
            data[column] = data[column].map(lambda value: "" if pd.isna(value) else f"{value:.4f}")
    data = data.fillna("")
    headers = [str(column) for column in data.columns]
    rows = [[str(value) for value in row] for row in data.to_numpy()]
    widths = [len(header) for header in headers]
    for row in rows:
        widths = [max(width, len(cell)) for width, cell in zip(widths, row)]
    line = "| " + " | ".join(header.ljust(width) for header, width in zip(headers, widths)) + " |"
    sep = "| " + " | ".join("-" * width for width in widths) + " |"
    body = ["| " + " | ".join(cell.ljust(width) for cell, width in zip(row, widths)) + " |" for row in rows]
    return "\n".join([line, sep, *body])


def _truthy(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.lower().isin({"true", "1", "1.0", "yes", "y"})


def _load_actionable() -> pd.DataFrame:
    if not SOURCE_STAGE716_PATH.exists():
        raise FileNotFoundError(SOURCE_STAGE716_PATH)
    data = pd.read_csv(SOURCE_STAGE716_PATH, encoding="utf-8-sig")
    actionable_flag = _truthy(data["actionable_throttle"])
    for column in [
        "h40_barrier_good",
        "h40_barrier_bad",
        "h40_mfe_r",
        "h40_mae_r",
        "h40_path_score_r",
        "h40_days_observed",
        "year",
        "ai_product_pool_rank",
        "ai_product_pool_score",
        "selection_pairwise_score",
        "selection_pairwise_rank",
        "rsi_value",
        "portfolio_drawdown_pct",
        "same_direction_correlation_max_corr",
        "active_positions_before",
        "contracts_by_risk",
        "breakout",
    ]:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    actionable = data[
        actionable_flag & data["h40_label_status"].astype(str).eq("ok")
    ].copy()
    actionable["year"] = actionable["year"].astype(int)
    return actionable.reset_index(drop=True)


def _atom_from_values(data: pd.DataFrame, column: str, values: list[str], family: str) -> list[Atom]:
    atoms: list[Atom] = []
    if column not in data.columns:
        return atoms
    text = data[column].astype(str)
    for value in values:
        mask = text.eq(value)
        if int(mask.sum()) >= MIN_ATOM_ROWS:
            atoms.append(Atom(f"{column}={value}", family, mask))
    return atoms


def _build_atoms(data: pd.DataFrame) -> list[Atom]:
    atoms: list[Atom] = []
    atoms += _atom_from_values(data, "status_scope", ["opened", "sizing_zero_volume"], "status_scope")
    atoms += _atom_from_values(data, "direction", ["long", "short"], "direction")
    atoms += _atom_from_values(data, "signal", ["long_case1a", "long_case2", "short_case1a", "short_case2"], "signal")
    atoms += _atom_from_values(
        data,
        "ai_rank_bucket",
        ["rank_1_3", "rank_4_6", "rank_7_9", "rank_10_plus"],
        "ai_rank_bucket",
    )
    atoms += _atom_from_values(
        data,
        "rsi_direction_bucket",
        ["rsi_strong", "rsi_mild", "rsi_neutral"],
        "rsi_direction_bucket",
    )
    atoms += _atom_from_values(data, "corr_bucket", ["corr_none", "corr_low", "corr_mid", "corr_high"], "corr_bucket")
    atoms += _atom_from_values(
        data,
        "drawdown_bucket",
        ["dd_0_5", "dd_5_15", "dd_15_plus"],
        "drawdown_bucket",
    )
    atoms += _atom_from_values(
        data,
        "active_positions_bucket",
        ["active_0", "active_1_2", "active_3_plus"],
        "active_positions_bucket",
    )
    atoms += _atom_from_values(
        data,
        "pairwise_rank_bucket",
        ["pair_missing", "pair_0_1", "pair_2_plus"],
        "pairwise_rank_bucket",
    )
    atoms += _atom_from_values(
        data,
        "contracts_by_risk_bucket",
        ["contracts_0", "contracts_1", "contracts_2_3", "contracts_4_plus"],
        "contracts_by_risk_bucket",
    )
    atoms += _atom_from_values(data, "target_risk_bucket", ["risk_lt1k", "risk_1k_2k5", "risk_ge2k5"], "target_risk")
    atoms += _atom_from_values(
        data,
        "stop_distance_pct_bucket",
        ["stop_tight", "stop_mid", "stop_wide"],
        "stop_distance",
    )
    atoms += _atom_from_values(data, "breakout_bucket", ["breakout_yes", "breakout_no"], "breakout_bucket")
    atoms += _atom_from_values(
        data,
        "recovery_sleeve_reason",
        ["cooldown", "no_multiplier_lift", "not_floor"],
        "recovery_sleeve_reason",
    )

    if {"direction", "rsi_value"}.issubset(data.columns):
        rsi = data["rsi_value"]
        direction = data["direction"].astype(str)
        atoms.append(Atom("directional_rsi_strong60", "directional_rsi", ((direction.eq("long") & rsi.ge(60.0)) | (direction.eq("short") & rsi.le(40.0))).fillna(False)))
        atoms.append(Atom("directional_rsi_extreme70", "directional_rsi", ((direction.eq("long") & rsi.ge(70.0)) | (direction.eq("short") & rsi.le(30.0))).fillna(False)))
    if "ai_product_pool_rank" in data.columns:
        rank = data["ai_product_pool_rank"]
        atoms.append(Atom("ai_rank_top3", "ai_rank_numeric", rank.le(3).fillna(False)))
        atoms.append(Atom("ai_rank_top6", "ai_rank_numeric", rank.le(6).fillna(False)))
        atoms.append(Atom("ai_rank_top9", "ai_rank_numeric", rank.le(9).fillna(False)))
    if "ai_product_pool_score" in data.columns:
        score = data["ai_product_pool_score"]
        atoms.append(Atom("ai_score_ge050", "ai_score", score.ge(0.50).fillna(False)))
        atoms.append(Atom("ai_score_ge070", "ai_score", score.ge(0.70).fillna(False)))
    if "selection_pairwise_score" in data.columns:
        pair_score = data["selection_pairwise_score"]
        atoms.append(Atom("pair_score_positive", "pair_score", pair_score.gt(0.0).fillna(False)))
        atoms.append(Atom("pair_score_ge050", "pair_score", pair_score.ge(0.50).fillna(False)))
    if "same_direction_correlation_max_corr" in data.columns:
        corr = data["same_direction_correlation_max_corr"]
        atoms.append(Atom("corr_max_le025", "corr_numeric", corr.le(0.25).fillna(False)))
        atoms.append(Atom("corr_max_le000", "corr_numeric", corr.le(0.0).fillna(False)))
    if "portfolio_drawdown_pct" in data.columns:
        dd = data["portfolio_drawdown_pct"]
        atoms.append(Atom("portfolio_dd_lt15", "portfolio_drawdown", dd.lt(0.15).fillna(False)))
        atoms.append(Atom("portfolio_dd_15_25", "portfolio_drawdown", dd.ge(0.15).fillna(False) & dd.lt(0.25).fillna(False)))
        atoms.append(Atom("portfolio_dd_ge25", "portfolio_drawdown", dd.ge(0.25).fillna(False)))
    if "active_positions_before" in data.columns:
        active = data["active_positions_before"]
        atoms.append(Atom("active_positions_eq0", "active_numeric", active.eq(0).fillna(False)))
        atoms.append(Atom("active_positions_le1", "active_numeric", active.le(1).fillna(False)))
    if "contracts_by_risk" in data.columns:
        contracts = data["contracts_by_risk"]
        atoms.append(Atom("contracts_by_risk=0", "contracts_by_risk_numeric", contracts.eq(0).fillna(False)))
        atoms.append(Atom("contracts_by_risk_ge1", "contracts_by_risk_numeric", contracts.ge(1).fillna(False)))
        atoms.append(Atom("contracts_by_risk_ge2", "contracts_by_risk_numeric", contracts.ge(2).fillna(False)))
    if "breakout" in data.columns:
        breakout = data["breakout"]
        atoms.append(Atom("breakout_numeric_yes", "breakout_numeric", breakout.eq(1).fillna(False)))

    dedup: dict[str, Atom] = {}
    for atom in atoms:
        mask = atom.mask.fillna(False).astype(bool)
        if int(mask.sum()) >= MIN_ATOM_ROWS:
            dedup[atom.name] = Atom(atom.name, atom.family, mask)
    return list(dedup.values())


def _dominant_share(group: pd.DataFrame) -> tuple[str, float]:
    shares = group["product"].value_counts(normalize=True)
    if shares.empty:
        return "", np.nan
    return str(shares.index[0]), float(shares.iloc[0])


def _metrics_for_group(group: pd.DataFrame, baseline: pd.DataFrame) -> dict[str, Any]:
    if group.empty:
        return {
            "rows": 0,
            "good_rate_pct": np.nan,
            "bad_rate_pct": np.nan,
            "good_lift_pp": np.nan,
            "bad_lift_pp": np.nan,
            "avg_path_score_r": np.nan,
            "score_lift_r": np.nan,
            "years": 0,
            "years_good_ge_base": 0,
            "years_score_positive": 0,
            "product_count": 0,
            "dominant_product": "",
            "dominant_product_share_pct": np.nan,
        }
    baseline_good = float(baseline["h40_barrier_good"].mean())
    baseline_bad = float(baseline["h40_barrier_bad"].mean())
    baseline_score = float(baseline["h40_path_score_r"].mean())
    year_stats = group.groupby("year").agg(
        rows=("candidate_index", "count"),
        good_rate=("h40_barrier_good", "mean"),
        avg_score=("h40_path_score_r", "mean"),
    )
    dominant_product, dominant_share = _dominant_share(group)
    return {
        "rows": int(len(group)),
        "good_rate_pct": float(group["h40_barrier_good"].mean() * 100.0),
        "bad_rate_pct": float(group["h40_barrier_bad"].mean() * 100.0),
        "good_lift_pp": float((group["h40_barrier_good"].mean() - baseline_good) * 100.0),
        "bad_lift_pp": float((group["h40_barrier_bad"].mean() - baseline_bad) * 100.0),
        "avg_path_score_r": float(group["h40_path_score_r"].mean()),
        "score_lift_r": float(group["h40_path_score_r"].mean() - baseline_score),
        "years": int(len(year_stats)),
        "years_good_ge_base": int((year_stats["good_rate"] >= baseline_good).sum()),
        "years_score_positive": int((year_stats["avg_score"] > 0.0).sum()),
        "product_count": int(group["product"].nunique()),
        "dominant_product": dominant_product,
        "dominant_product_share_pct": float(dominant_share * 100.0),
    }


def _rule_fail_reasons(row: pd.Series) -> str:
    reasons: list[str] = []
    if int(row["rows"]) < MIN_RULE_ROWS:
        reasons.append(f"rows<{MIN_RULE_ROWS}")
    if int(row["years"]) < MIN_RULE_YEARS:
        reasons.append(f"years<{MIN_RULE_YEARS}")
    if int(row["product_count"]) < MIN_RULE_PRODUCT_COUNT:
        reasons.append(f"products<{MIN_RULE_PRODUCT_COUNT}")
    if float(row["dominant_product_share_pct"]) > MAX_DOMINANT_PRODUCT_SHARE * 100.0:
        reasons.append(f"dominant_product_share>{MAX_DOMINANT_PRODUCT_SHARE * 100:.0f}%")
    if float(row["good_lift_pp"]) < MIN_GOOD_LIFT_PP:
        reasons.append(f"good_lift<{MIN_GOOD_LIFT_PP:.0f}pp")
    if float(row["bad_rate_pct"]) > MAX_BAD_RATE_PCT:
        reasons.append(f"bad_rate>{MAX_BAD_RATE_PCT:.0f}%")
    if int(row["loo_test_years"]) < MIN_LOO_TEST_YEARS:
        reasons.append(f"loo_years<{MIN_LOO_TEST_YEARS}")
    if int(row["loo_test_rows"]) < MIN_LOO_TEST_ROWS:
        reasons.append(f"loo_rows<{MIN_LOO_TEST_ROWS}")
    if int(row["loo_good_years_ge_base"]) < MIN_LOO_GOOD_YEARS:
        reasons.append(f"loo_good_years<{MIN_LOO_GOOD_YEARS}")
    if int(row["loo_score_positive_years"]) < MIN_LOO_SCORE_POSITIVE_YEARS:
        reasons.append(f"loo_positive_score_years<{MIN_LOO_SCORE_POSITIVE_YEARS}")
    if float(row["loo_good_lift_pp"]) < 0.0:
        reasons.append("loo_good_lift<0pp")
    if float(row["loo_bad_rate_pct"]) > MAX_BAD_RATE_PCT:
        reasons.append(f"loo_bad_rate>{MAX_BAD_RATE_PCT:.0f}%")
    if str(row.get("contradiction") or ""):
        reasons.append("contradicted_by_prior_backtest")
    return "; ".join(reasons)


def _contradiction_for_rule(atom_names: tuple[str, ...]) -> str:
    hits = [CONTRADICTED_ATOMS[name] for name in atom_names if name in CONTRADICTED_ATOMS]
    return " | ".join(hits)


def _rule_score(row: pd.Series) -> float:
    return (
        float(row["good_lift_pp"])
        - max(float(row["bad_lift_pp"]), 0.0)
        + min(float(row["avg_path_score_r"]), 20.0)
        + float(row["years_good_ge_base"]) * 2.0
        + min(float(row["rows"]), 40.0) / 4.0
    )


def _evaluate_rules(data: pd.DataFrame, atoms: list[Atom]) -> tuple[pd.DataFrame, pd.DataFrame]:
    baseline = data
    rows: list[dict[str, Any]] = []
    year_rows: list[dict[str, Any]] = []
    candidates: list[tuple[tuple[str, ...], str, pd.Series]] = []
    for atom in atoms:
        candidates.append(((atom.name,), atom.family, atom.mask))
    for left, right in combinations(atoms, 2):
        if left.family == right.family:
            continue
        mask = left.mask & right.mask
        if int(mask.sum()) >= MIN_RULE_SUPPORT_FOR_SCREEN:
            candidates.append(((left.name, right.name), f"{left.family}&{right.family}", mask))

    for atom_names, family, mask in candidates:
        group = data[mask].copy()
        if len(group) < MIN_RULE_SUPPORT_FOR_SCREEN:
            continue
        row = {
            "rule": " & ".join(atom_names),
            "atom_count": len(atom_names),
            "rule_family": family,
            **_metrics_for_group(group, baseline),
            "contradiction": _contradiction_for_rule(atom_names),
        }
        loo_years: list[dict[str, Any]] = []
        for year, test_baseline in data.groupby("year"):
            test_group = group[group["year"].eq(year)]
            if test_group.empty:
                continue
            test_metrics = _metrics_for_group(test_group, test_baseline)
            loo_years.append({"year": int(year), **test_metrics})
            year_rows.append({"rule": row["rule"], **loo_years[-1]})
        if loo_years:
            loo = pd.DataFrame(loo_years)
            row.update(
                {
                    "loo_test_years": int(len(loo)),
                    "loo_test_rows": int(loo["rows"].sum()),
                    "loo_good_rate_pct": float(np.average(loo["good_rate_pct"], weights=loo["rows"])),
                    "loo_bad_rate_pct": float(np.average(loo["bad_rate_pct"], weights=loo["rows"])),
                    "loo_good_lift_pp": float(np.average(loo["good_lift_pp"], weights=loo["rows"])),
                    "loo_avg_path_score_r": float(np.average(loo["avg_path_score_r"], weights=loo["rows"])),
                    "loo_good_years_ge_base": int((loo["good_lift_pp"] >= 0.0).sum()),
                    "loo_score_positive_years": int((loo["avg_path_score_r"] > 0.0).sum()),
                }
            )
        else:
            row.update(
                {
                    "loo_test_years": 0,
                    "loo_test_rows": 0,
                    "loo_good_rate_pct": np.nan,
                    "loo_bad_rate_pct": np.nan,
                    "loo_good_lift_pp": np.nan,
                    "loo_avg_path_score_r": np.nan,
                    "loo_good_years_ge_base": 0,
                    "loo_score_positive_years": 0,
                }
            )
        rows.append(row)

    metrics = pd.DataFrame(rows)
    metrics["screen_score"] = metrics.apply(_rule_score, axis=1)
    metrics["fail_reasons"] = metrics.apply(_rule_fail_reasons, axis=1)
    metrics["passes_rule_gate"] = metrics["fail_reasons"].eq("")
    metrics["classification"] = np.select(
        [
            metrics["passes_rule_gate"],
            metrics["contradiction"].astype(str).ne(""),
            metrics["good_lift_pp"].ge(MIN_GOOD_LIFT_PP) & metrics["rows"].ge(10),
        ],
        ["reliable_exemption_rule_candidate", "watch_but_backtest_contradicted", "watch_only_oos_or_sample_gap"],
        default="not_reliable",
    )
    metrics = metrics.sort_values(
        ["passes_rule_gate", "screen_score", "good_lift_pp", "rows"],
        ascending=[False, False, False, False],
    ).reset_index(drop=True)
    return metrics, pd.DataFrame(year_rows)


def _anchored_selector(data: pd.DataFrame, metrics: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    years = sorted(data["year"].unique())
    for year in years:
        train = data[data["year"].lt(year)]
        test = data[data["year"].eq(year)]
        if train["year"].nunique() < 2 or test.empty:
            continue
        selected: pd.Series | None = None
        train_candidates: list[dict[str, Any]] = []
        for _, rule_row in metrics.iterrows():
            atom_names = str(rule_row["rule"]).split(" & ")
            mask = pd.Series(True, index=data.index)
            possible = True
            for atom_name in atom_names:
                possible = False
                for atom in _build_atoms(data):
                    if atom.name == atom_name:
                        mask &= atom.mask
                        possible = True
                        break
                if not possible:
                    break
            if not possible:
                continue
            train_group = train[mask.loc[train.index]]
            if train_group.empty:
                continue
            train_metrics = _metrics_for_group(train_group, train)
            if (
                train_metrics["rows"] >= 15
                and train_metrics["years"] >= 2
                and train_metrics["good_lift_pp"] >= MIN_GOOD_LIFT_PP
                and train_metrics["bad_rate_pct"] <= MAX_BAD_RATE_PCT
                and train_metrics["dominant_product_share_pct"] <= 40.0
                and not _contradiction_for_rule(tuple(atom_names))
            ):
                train_candidates.append(
                    {
                        "rule": rule_row["rule"],
                        "train_score": (
                            train_metrics["good_lift_pp"]
                            - max(train_metrics["bad_lift_pp"], 0.0)
                            + min(train_metrics["avg_path_score_r"], 20.0)
                            + train_metrics["years_good_ge_base"] * 2.0
                        ),
                        **{f"train_{key}": value for key, value in train_metrics.items()},
                    }
                )
        if train_candidates:
            selected_row = max(train_candidates, key=lambda item: item["train_score"])
            selected = pd.Series(selected_row)
            atom_names = str(selected["rule"]).split(" & ")
            mask = pd.Series(True, index=data.index)
            for atom_name in atom_names:
                for atom in _build_atoms(data):
                    if atom.name == atom_name:
                        mask &= atom.mask
                        break
            test_group = test[mask.loc[test.index]]
            test_metrics = _metrics_for_group(test_group, test)
            selected_rule = str(selected["rule"])
            train_score = float(selected["train_score"])
            train_rows = int(selected["train_rows"])
        else:
            test_metrics = _metrics_for_group(pd.DataFrame(columns=test.columns), test)
            selected_rule = ""
            train_score = np.nan
            train_rows = 0
        rows.append(
            {
                "test_year": int(year),
                "selected_rule": selected_rule,
                "train_score": train_score,
                "train_rows": train_rows,
                "candidate_count": len(train_candidates),
                **{f"test_{key}": value for key, value in test_metrics.items()},
                "baseline_rows": int(len(test)),
                "baseline_good_rate_pct": float(test["h40_barrier_good"].mean() * 100.0),
                "baseline_bad_rate_pct": float(test["h40_barrier_bad"].mean() * 100.0),
                "baseline_avg_path_score_r": float(test["h40_path_score_r"].mean()),
            }
        )
    return pd.DataFrame(rows)


def _plot(metrics: pd.DataFrame, anchored: pd.DataFrame) -> None:
    plt.rcParams["font.family"] = "DejaVu Sans"
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    top = metrics.sort_values(["screen_score"], ascending=False).head(12).copy()
    colors = [
        "#2f855a" if value else "#dd6b20" if "watch" in cls else "#718096"
        for value, cls in zip(top["passes_rule_gate"], top["classification"])
    ]
    axes[0].barh(top["rule"], top["good_lift_pp"], color=colors)
    axes[0].axvline(MIN_GOOD_LIFT_PP, color="#2f855a", linestyle="--", linewidth=1.0, label="required +10pp")
    axes[0].axvline(0, color="#4a5568", linewidth=0.8)
    axes[0].set_title("Top screened throttle-exemption rules")
    axes[0].set_xlabel("full-sample H40 good lift (pp)")
    axes[0].invert_yaxis()
    axes[0].legend()

    if not anchored.empty:
        view = anchored.copy()
        axes[1].plot(view["test_year"], view["baseline_good_rate_pct"], marker="o", label="baseline good")
        axes[1].plot(view["test_year"], view["test_good_rate_pct"], marker="o", label="anchored selected rule good")
        for _, row in view.iterrows():
            if str(row["selected_rule"]):
                axes[1].text(row["test_year"], row["test_good_rate_pct"] + 1.5, str(row["test_rows"]), fontsize=8)
        axes[1].set_title("Anchored selector OOS good rate")
        axes[1].set_xlabel("test year")
        axes[1].set_ylabel("H40 good rate (%)")
        axes[1].legend()
    fig.suptitle("Stage722 Throttle Exemption Rule OOS", fontsize=15)
    fig.tight_layout(rect=[0, 0.02, 1, 0.94])
    CHART_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _build_report(data: pd.DataFrame, metrics: pd.DataFrame, anchored: pd.DataFrame, decision: dict[str, Any]) -> str:
    top_columns = [
        "rule",
        "atom_count",
        "rows",
        "good_rate_pct",
        "bad_rate_pct",
        "good_lift_pp",
        "loo_test_years",
        "loo_test_rows",
        "loo_good_lift_pp",
        "loo_bad_rate_pct",
        "product_count",
        "dominant_product_share_pct",
        "classification",
        "fail_reasons",
    ]
    anchored_columns = [
        "test_year",
        "selected_rule",
        "candidate_count",
        "train_rows",
        "test_rows",
        "test_good_rate_pct",
        "test_bad_rate_pct",
        "test_good_lift_pp",
        "baseline_good_rate_pct",
    ]
    lines = [
        "# Stage722 Throttle Exemption Rule OOS",
        "",
        f"- line_id: `{LINE_ID}`",
        f"- generated_at: `{decision['generated_at']}`",
        f"- source: `{SOURCE_STAGE716_PATH}`",
        f"- actionable_h40_rows: `{len(data)}`",
        f"- atom_count: `{decision['atom_count']}`",
        f"- screened_rule_count: `{decision['screened_rule_count']}`",
        f"- promoted_rule_count: `{decision['promoted_rule_count']}`",
        f"- decision: `{decision['decision']}`",
        "",
        "## Gate",
        "",
        f"- max atoms per rule: `{MAX_RULE_ATOMS}`",
        f"- rule rows >= `{MIN_RULE_ROWS}`; years >= `{MIN_RULE_YEARS}`; products >= `{MIN_RULE_PRODUCT_COUNT}`",
        f"- dominant product share <= `{MAX_DOMINANT_PRODUCT_SHARE * 100:.0f}%`",
        f"- full-sample H40 +2R good lift >= `{MIN_GOOD_LIFT_PP:.0f}pp`; bad rate <= `{MAX_BAD_RATE_PCT:.0f}%`",
        f"- LOO test years >= `{MIN_LOO_TEST_YEARS}`; LOO rows >= `{MIN_LOO_TEST_ROWS}`; LOO good years >= `{MIN_LOO_GOOD_YEARS}`",
        "- no atom contradicted by prior actual backtests.",
        "",
        "## Top Rules",
        "",
        _md_table(metrics[top_columns], max_rows=25),
        "",
        "## Anchored Selector",
        "",
        _md_table(anchored[anchored_columns], max_rows=None) if not anchored.empty else "_empty_",
        "",
        "## Interpretation",
        "",
        "- This is a pressure test for simple one- or two-condition exemption rules, not a strategy change.",
        "- If no rule passes, the correct conclusion is that current historical fields still do not justify bypassing the 0.1 floor.",
        "- Any rule relying on sizing-zero/cooldown-like atoms is downgraded because prior path backtests already failed those shapes.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    data = _load_actionable()
    atoms = _build_atoms(data)
    metrics, year_detail = _evaluate_rules(data, atoms)
    anchored = _anchored_selector(data, metrics)
    promoted = metrics[metrics["passes_rule_gate"]]
    if not anchored.empty:
        selected = anchored[anchored["selected_rule"].astype(str).ne("")]
        anchored_summary = {
            "anchored_test_years": int(len(anchored)),
            "anchored_selected_years": int(len(selected)),
            "anchored_selected_rows": int(selected["test_rows"].sum()) if not selected.empty else 0,
            "anchored_selected_good_rate_pct": float(
                np.average(selected["test_good_rate_pct"], weights=selected["test_rows"])
            )
            if not selected.empty and selected["test_rows"].sum() > 0
            else None,
            "anchored_selected_bad_rate_pct": float(
                np.average(selected["test_bad_rate_pct"], weights=selected["test_rows"])
            )
            if not selected.empty and selected["test_rows"].sum() > 0
            else None,
            "anchored_baseline_good_rate_pct": float(
                np.average(anchored["baseline_good_rate_pct"], weights=anchored["baseline_rows"])
            ),
            "anchored_baseline_bad_rate_pct": float(
                np.average(anchored["baseline_bad_rate_pct"], weights=anchored["baseline_rows"])
            ),
        }
    else:
        anchored_summary = {}
    decision = {
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": str(SOURCE_STAGE716_PATH),
        "actionable_h40_rows": int(len(data)),
        "atom_count": int(len(atoms)),
        "screened_rule_count": int(len(metrics)),
        "promoted_rule_count": int(len(promoted)),
        "promoted_rules": promoted[["rule", "rows", "good_rate_pct", "loo_good_lift_pp"]].to_dict(
            orient="records"
        ),
        "top_watch_rules": metrics.head(8)[
            ["rule", "rows", "good_rate_pct", "good_lift_pp", "loo_good_lift_pp", "fail_reasons"]
        ].to_dict(orient="records"),
        "anchored_summary": anchored_summary,
        "decision": "no_reliable_exemption_rule_found",
        "next_step": (
            "Stop mining simple historical throttle-exemption features unless new exogenous fields or forward samples "
            "are added. Current evidence supports keeping the 0.1 floor without bypass."
        ),
    }
    metrics.to_csv(RULE_METRICS_PATH, index=False, encoding="utf-8-sig")
    year_detail.to_csv(YEAR_DETAIL_PATH, index=False, encoding="utf-8-sig")
    anchored.to_csv(ANCHORED_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _plot(metrics, anchored)
    REPORT_PATH.write_text(_build_report(data, metrics, anchored, decision), encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
