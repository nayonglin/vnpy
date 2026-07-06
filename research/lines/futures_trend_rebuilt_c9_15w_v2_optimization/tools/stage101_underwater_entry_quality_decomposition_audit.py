from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage101"
MODEL_TAG = "stage101_underwater_entry_quality_decomposition_audit_v2_panel_dd"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage101_underwater_entry_quality_decomposition_audit"

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage101_underwater_entry_quality_decomposition_audit"
STAGES_DIR = LINE_DIR / "stages"

STAGE094_OUT = LINE_DIR / "outputs" / "stage094_stage167_closed_lot_entry_state_audit"
STAGE094_PREFIX = "rebuilt_c9_v2_stage094_stage167_closed_lot_entry_state_audit"
STAGE094_TAG = "stage094_stage167_closed_lot_entry_state_audit_v1"
CLOSED_LOTS_PATH = STAGE094_OUT / f"{STAGE094_PREFIX}_closed_lots_{STAGE094_TAG}.csv.gz"

STAGE096_OUT = LINE_DIR / "outputs" / "stage096_position_concentration_predictive_audit"
STAGE096_PREFIX = "rebuilt_c9_v2_stage096_position_concentration_predictive_audit"
STAGE096_TAG = "stage096_position_concentration_predictive_audit_v1"
EXPOSURE_PANEL_PATH = STAGE096_OUT / f"{STAGE096_PREFIX}_exposure_panel_{STAGE096_TAG}.csv.gz"

STAGE095_OUT = LINE_DIR / "outputs" / "stage095_risk_multiplier_cap1_proxy"
STAGE095_PREFIX = "rebuilt_c9_v2_stage095_risk_multiplier_cap1_proxy"
STAGE095_TAG = "stage095_risk_multiplier_cap1_proxy_v1"
STAGE095_DECISION_PATH = STAGE095_OUT / f"{STAGE095_PREFIX}_decision_{STAGE095_TAG}.json"

LOT_CONTEXT_PATH = OUT / f"{OUTPUT_PREFIX}_lot_context_{MODEL_TAG}.csv.gz"
CONDITION_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_condition_summary_{MODEL_TAG}.csv"
CONDITION_BY_START_PATH = OUT / f"{OUTPUT_PREFIX}_condition_by_start_{MODEL_TAG}.csv"
PEER_COMPARISON_PATH = OUT / f"{OUTPUT_PREFIX}_peer_comparison_{MODEL_TAG}.csv"
TOP_LOSS_DETAIL_PATH = OUT / f"{OUTPUT_PREFIX}_top_loss_detail_{MODEL_TAG}.csv"
INPUT_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_input_audit_{MODEL_TAG}.csv"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

EXTERNAL_RESEARCH = [
    {
        "source": "pysystemtrade backtesting documentation",
        "url": "https://github.com/pst-group/pysystemtrade/blob/develop/docs/backtesting.md",
        "finding": "Trend research should separate signal, sizing, portfolio accounting and PnL attribution; closed-lot filters are only screening evidence.",
    },
    {
        "source": "Man Group Trend Following and Drawdowns",
        "url": "https://www.man.com/insights/is-this-time-different",
        "finding": "Trend-following drawdowns can persist through choppy regimes, so drawdown control must be tested against recovery and right-tail retention.",
    },
    {
        "source": "Research Affiliates stop-loss paper",
        "url": "https://www.researchaffiliates.com/content/dam/ra/publications/pdf/1099-stop-the-losses.pdf",
        "finding": "Stop-loss style protection can reduce some loss paths, but rule design must be broad and systematic rather than fitted to isolated episodes.",
    },
]

CONDITION_SPECS = [
    {
        "condition": "dd30_active_lt2",
        "label": "DD>=30% and active_positions_before<2",
        "peer_group": "dd30_active_split",
        "candidate_eligible": False,
        "note": "Stage095 shadow check only; do not promote directly.",
    },
    {
        "condition": "dd30_active_lt2_not_rm2",
        "label": "DD>=30% and active<2, excluding risk_multiplier>=2",
        "peer_group": "dd30_active_split_non_rm2",
        "candidate_eligible": True,
        "note": "Tests whether active<2 has signal after removing Stage095 failed selector.",
    },
    {
        "condition": "dd30_active_ge2",
        "label": "DD>=30% and active_positions_before>=2",
        "peer_group": "dd30_active_split",
        "candidate_eligible": False,
        "note": "Peer/complement; positive carry/recovery bucket.",
    },
    {
        "condition": "dd30_no_breakout_active_lt2",
        "label": "DD>=30%, active<2, non-breakout",
        "peer_group": "dd30_active_lt2_breakout_split",
        "candidate_eligible": True,
        "note": "Tests low-active deep-DD entries without breakout confirmation.",
    },
    {
        "condition": "dd30_no_breakout_active_lt2_not_rm2",
        "label": "DD>=30%, active<2, non-breakout, excluding risk_multiplier>=2",
        "peer_group": "dd30_active_lt2_breakout_split_non_rm2",
        "candidate_eligible": True,
        "note": "Core non-overlap candidate screen if stable across starts.",
    },
    {
        "condition": "dd30_breakout_active_lt2",
        "label": "DD>=30%, active<2, breakout",
        "peer_group": "dd30_active_lt2_breakout_split",
        "candidate_eligible": False,
        "note": "Peer/complement for non-breakout.",
    },
    {
        "condition": "dd30_ai_rank_1_8_active_lt2",
        "label": "DD>=30%, active<2, AI rank 1-8",
        "peer_group": "dd30_active_lt2_ai_split",
        "candidate_eligible": True,
        "note": "Tests whether AI quality alone protects deep-DD low-active entries.",
    },
    {
        "condition": "dd30_rank_gt8_or_missing_active_lt2",
        "label": "DD>=30%, active<2, AI rank >8 or missing",
        "peer_group": "dd30_active_lt2_ai_split",
        "candidate_eligible": True,
        "note": "Tests lower/missing AI pool in the same account state.",
    },
    {
        "condition": "dd30_selected_vol_gt1_active_lt2",
        "label": "DD>=30%, active<2, selected_volume>1",
        "peer_group": "dd30_active_lt2_volume_split",
        "candidate_eligible": True,
        "note": "Tests integer sizing exposure in low-active recovery attempts.",
    },
    {
        "condition": "dd30_loss_streak_ge3_active_lt2",
        "label": "DD>=30%, active<2, loss_streak>=3",
        "peer_group": "dd30_active_lt2_loss_streak_split",
        "candidate_eligible": True,
        "note": "Tests whether accumulated realized losses still matter in deep drawdown.",
    },
    {
        "condition": "dd30_corr0_active_lt2",
        "label": "DD>=30%, active<2, no same-direction active position",
        "peer_group": "dd30_active_lt2_corr_split",
        "candidate_eligible": True,
        "note": "Tests fresh/uncorrelated entries in deep-DD low-active state.",
    },
    {
        "condition": "below_initial_no_breakout_active_lt2_not_rm2",
        "label": "Below initial equity, active<2, non-breakout, excluding risk_multiplier>=2",
        "peer_group": "below_initial_breakout_split_non_rm2",
        "candidate_eligible": True,
        "note": "Same idea using below-initial water state instead of peak drawdown.",
    },
]


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if not np.isfinite(number) else number
    if isinstance(value, float):
        return None if not np.isfinite(value) else value
    try:
        if pd.isna(value) and not isinstance(value, (str, bytes)):
            return None
    except Exception:
        pass
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_无记录_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    return data.to_markdown(index=False)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _input_audit(paths: list[Path]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for path in paths:
        if path.exists():
            stat = path.stat()
            rows.append(
                {
                    "path": str(path),
                    "exists": True,
                    "bytes": int(stat.st_size),
                    "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                    "sha256": _sha256(path),
                }
            )
        else:
            rows.append({"path": str(path), "exists": False, "bytes": 0, "mtime": "", "sha256": ""})
    return pd.DataFrame(rows)


def _numeric(frame: pd.DataFrame, column: str, default: float = np.nan) -> pd.Series:
    if column in frame.columns:
        return pd.to_numeric(frame[column], errors="coerce")
    return pd.Series(default, index=frame.index, dtype=float)


def _safe_div(numerator: float, denominator: float) -> float:
    if not np.isfinite(numerator) or not np.isfinite(denominator) or abs(denominator) < 1e-12:
        return np.nan
    return float(numerator / denominator)


def load_stage095_decision() -> dict[str, Any]:
    decision = json.loads(STAGE095_DECISION_PATH.read_text(encoding="utf-8"))
    if decision.get("decision") != "stage095_no_proxy_candidate":
        raise ValueError(f"Unexpected Stage095 decision: {decision.get('decision')}")
    return decision


def load_lot_context() -> pd.DataFrame:
    lots = pd.read_csv(CLOSED_LOTS_PATH, encoding="utf-8-sig")
    panel = pd.read_csv(
        EXPOSURE_PANEL_PATH,
        usecols=[
            "requested_start_month",
            "date",
            "account_equity",
            "account_capital",
            "drawdown_depth_pct",
            "nav",
        ],
        encoding="utf-8-sig",
    )
    lots["entry_date"] = pd.to_datetime(lots["entry_date"], errors="coerce").dt.normalize()
    lots["exit_date"] = pd.to_datetime(lots["exit_date"], errors="coerce").dt.normalize()
    panel["date"] = pd.to_datetime(panel["date"], errors="coerce").dt.normalize()
    lots["requested_start_month"] = lots["requested_start_month"].astype(str)
    panel["requested_start_month"] = panel["requested_start_month"].astype(str)
    panel_keys = ["requested_start_month", "date"]
    duplicate_panel_keys = int(panel.duplicated(panel_keys).sum())
    if duplicate_panel_keys:
        raise ValueError(f"Stage096 exposure panel has duplicate entry-date keys: {duplicate_panel_keys}")
    numeric_cols = [
        "realized_pnl",
        "r_multiple",
        "risk_multiplier",
        "loss_streak",
        "active_positions_before",
        "ai_product_pool_rank",
        "ai_product_pool_score",
        "selected_volume",
        "breakout",
        "portfolio_drawdown_pct",
        "same_direction_correlation_active_count",
        "same_direction_correlation_max_corr",
        "entry_risk_distance_pct",
        "mfe_r",
        "mae_r",
        "winner",
        "big_winner",
    ]
    for column in numeric_cols:
        lots[column] = _numeric(lots, column)
    for column in ["account_equity", "account_capital", "drawdown_depth_pct", "nav"]:
        panel[column] = _numeric(panel, column)
    context = lots.merge(
        panel.rename(
            columns={
                "date": "entry_panel_date",
                "account_equity": "entry_account_equity",
                "account_capital": "entry_account_capital",
                "drawdown_depth_pct": "entry_panel_drawdown_depth_pct",
                "nav": "entry_nav",
            }
        ),
        left_on=["requested_start_month", "entry_date"],
        right_on=["requested_start_month", "entry_panel_date"],
        how="left",
        validate="many_to_one",
    )
    missing_panel_match = int(context["entry_account_equity"].isna().sum())
    if missing_panel_match:
        raise ValueError(f"Stage096 exposure panel exact-match missing lots: {missing_panel_match}")
    context["entry_below_initial"] = context["entry_account_equity"].lt(context["entry_account_capital"])
    context["entry_under_initial_pct"] = (
        context["entry_account_equity"].div(context["entry_account_capital"]).sub(1.0) * 100.0
    )
    context["stage094_portfolio_dd30"] = context["portfolio_drawdown_pct"].ge(0.30)
    context["panel_dd30"] = context["entry_panel_drawdown_depth_pct"].ge(30.0)
    context["dd30"] = context["panel_dd30"]
    context["stage095_risk_multiplier_ge2"] = context["risk_multiplier"].ge(2.0)
    context["active_lt2"] = context["active_positions_before"].notna() & context["active_positions_before"].lt(2.0)
    context["active_ge2"] = context["active_positions_before"].notna() & context["active_positions_before"].ge(2.0)
    context["breakout_available"] = context["breakout"].notna()
    context["breakout_bool"] = context["breakout_available"] & context["breakout"].gt(0.0)
    context["non_breakout_bool"] = context["breakout_available"] & ~context["breakout_bool"]
    context["ai_rank_1_8"] = context["ai_product_pool_rank"].between(1, 8, inclusive="both")
    context["ai_rank_gt8_or_missing"] = ~context["ai_rank_1_8"]
    context["same_direction_active0"] = context["same_direction_correlation_active_count"].fillna(0.0).eq(0.0)
    context["selected_volume_gt1"] = context["selected_volume"].gt(1.0)
    context["loss_streak_ge3"] = context["loss_streak"].ge(3.0)
    context["entry_year"] = _numeric(context, "entry_year").astype("Int64")
    add_conditions(context)
    return context


def add_conditions(context: pd.DataFrame) -> None:
    context["dd30_active_lt2"] = context["dd30"] & context["active_lt2"]
    context["dd30_active_lt2_not_rm2"] = context["dd30_active_lt2"] & ~context["stage095_risk_multiplier_ge2"]
    context["dd30_active_ge2"] = context["dd30"] & context["active_ge2"]
    context["dd30_no_breakout_active_lt2"] = context["dd30_active_lt2"] & context["non_breakout_bool"]
    context["dd30_no_breakout_active_lt2_not_rm2"] = (
        context["dd30_no_breakout_active_lt2"] & ~context["stage095_risk_multiplier_ge2"]
    )
    context["dd30_breakout_active_lt2"] = context["dd30_active_lt2"] & context["breakout_bool"]
    context["dd30_ai_rank_1_8_active_lt2"] = context["dd30_active_lt2"] & context["ai_rank_1_8"]
    context["dd30_rank_gt8_or_missing_active_lt2"] = context["dd30_active_lt2"] & context["ai_rank_gt8_or_missing"]
    context["dd30_selected_vol_gt1_active_lt2"] = context["dd30_active_lt2"] & context["selected_volume_gt1"]
    context["dd30_loss_streak_ge3_active_lt2"] = context["dd30_active_lt2"] & context["loss_streak_ge3"]
    context["dd30_corr0_active_lt2"] = context["dd30_active_lt2"] & context["same_direction_active0"]
    context["below_initial_no_breakout_active_lt2_not_rm2"] = (
        context["entry_below_initial"]
        & context["active_lt2"]
        & context["non_breakout_bool"]
        & ~context["stage095_risk_multiplier_ge2"]
    )


def _condition_mask(context: pd.DataFrame, condition: str) -> pd.Series:
    return context[condition].fillna(False).astype(bool)


def _top_product_stats(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty or "product" not in frame.columns:
        return {
            "top_product": "",
            "top_product_lot_share": np.nan,
            "top_product_loss_share": np.nan,
            "product_hhi_by_lot": np.nan,
        }
    by_product = frame.groupby("product", dropna=False).agg(lot_count=("lot_id", "count"), pnl=("realized_pnl", "sum"))
    top = by_product.sort_values("lot_count", ascending=False).iloc[0]
    lot_share = _safe_div(float(top["lot_count"]), float(len(frame)))
    negative_abs_total = float(-frame.loc[frame["realized_pnl"].lt(0), "realized_pnl"].sum())
    product_negative_abs = (
        frame.loc[frame["realized_pnl"].lt(0)]
        .groupby("product", dropna=False)["realized_pnl"]
        .sum()
        .mul(-1.0)
        .sort_values(ascending=False)
    )
    top_loss_share = _safe_div(float(product_negative_abs.iloc[0]), negative_abs_total) if not product_negative_abs.empty else np.nan
    product_lot_shares = by_product["lot_count"].astype(float).div(float(len(frame)))
    return {
        "top_product": str(top.name),
        "top_product_lot_share": lot_share,
        "top_product_loss_share": top_loss_share,
        "product_hhi_by_lot": float((product_lot_shares**2).sum()),
    }


def summarize_conditions(context: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    total_negative_abs = float(-context.loc[context["realized_pnl"].lt(0), "realized_pnl"].sum())
    total_positive = float(context.loc[context["realized_pnl"].gt(0), "realized_pnl"].sum())
    rows: list[dict[str, Any]] = []
    by_start_rows: list[dict[str, Any]] = []
    for spec in CONDITION_SPECS:
        condition = spec["condition"]
        selected = context[_condition_mask(context, condition)].copy()
        old_overlap = selected[selected["stage095_risk_multiplier_ge2"]].copy()
        non_old = selected[~selected["stage095_risk_multiplier_ge2"]].copy()
        if selected.empty:
            rows.append(
                {
                    **spec,
                    "lot_count": 0,
                    "start_count": 0,
                    "entry_year_count": 0,
                    "product_count": 0,
                    "realized_pnl_sum": 0.0,
                    "positive_pnl_sum": 0.0,
                    "negative_pnl_abs_sum": 0.0,
                    "winner_rate": np.nan,
                    "median_r_multiple": np.nan,
                    "negative_start_count": 0,
                    "negative_start_rate": np.nan,
                    "big_winner_count": 0,
                    "big_winner_pnl": 0.0,
                    "big_winner_pnl_share_of_positive": np.nan,
                    "loss_capture_share": 0.0,
                    "gain_share": 0.0,
                    "stage095_overlap_lot_count": 0,
                    "stage095_overlap_lot_share": 0.0,
                    "stage095_overlap_pnl_sum": 0.0,
                    "non_stage095_pnl_sum": 0.0,
                    "old_selector_explains_loss": False,
                    "candidate_for_next_proxy": False,
                }
            )
            continue
        start_pnl = selected.groupby("requested_start_month")["realized_pnl"].sum()
        positive_pnl = float(selected.loc[selected["realized_pnl"].gt(0), "realized_pnl"].sum())
        negative_abs = float(-selected.loc[selected["realized_pnl"].lt(0), "realized_pnl"].sum())
        big_winner_pnl = float(selected.loc[selected["big_winner"].eq(1), "realized_pnl"].clip(lower=0.0).sum())
        top_product = _top_product_stats(selected)
        old_overlap_pnl = float(old_overlap["realized_pnl"].sum()) if not old_overlap.empty else 0.0
        non_old_pnl = float(non_old["realized_pnl"].sum()) if not non_old.empty else 0.0
        old_selector_explains_loss = bool(float(selected["realized_pnl"].sum()) < 0.0 and non_old_pnl >= -100_000.0)
        candidate = bool(
            spec["candidate_eligible"]
            and len(selected) >= 80
            and len(old_overlap) == 0
            and selected["requested_start_month"].nunique() >= 8
            and selected["entry_year"].nunique() >= 4
            and selected["product"].nunique() >= 8
            and float(selected["realized_pnl"].sum()) < 0.0
            and non_old_pnl < -250_000.0
            and _safe_div(float(start_pnl.lt(0).sum()), float(len(start_pnl))) >= 0.55
            and _safe_div(big_winner_pnl, positive_pnl) <= 0.15
            and top_product["top_product_loss_share"] <= 0.50
            and not old_selector_explains_loss
        )
        rows.append(
            {
                **spec,
                "lot_count": int(len(selected)),
                "start_count": int(selected["requested_start_month"].nunique()),
                "entry_year_count": int(selected["entry_year"].nunique()),
                "product_count": int(selected["product"].nunique()),
                "realized_pnl_sum": float(selected["realized_pnl"].sum()),
                "positive_pnl_sum": positive_pnl,
                "negative_pnl_abs_sum": negative_abs,
                "winner_rate": float(selected["winner"].mean()),
                "median_r_multiple": float(selected["r_multiple"].median()),
                "negative_start_count": int(start_pnl.lt(0).sum()),
                "negative_start_rate": _safe_div(float(start_pnl.lt(0).sum()), float(len(start_pnl))),
                "start_pnl_min": float(start_pnl.min()),
                "start_pnl_median": float(start_pnl.median()),
                "start_pnl_max": float(start_pnl.max()),
                "big_winner_count": int(selected["big_winner"].eq(1).sum()),
                "big_winner_pnl": big_winner_pnl,
                "big_winner_pnl_share_of_positive": _safe_div(big_winner_pnl, positive_pnl),
                "loss_capture_share": _safe_div(negative_abs, total_negative_abs),
                "gain_share": _safe_div(positive_pnl, total_positive),
                "stage095_overlap_lot_count": int(len(old_overlap)),
                "stage095_overlap_lot_share": _safe_div(float(len(old_overlap)), float(len(selected))),
                "stage095_overlap_pnl_sum": old_overlap_pnl,
                "non_stage095_lot_count": int(len(non_old)),
                "non_stage095_pnl_sum": non_old_pnl,
                "old_selector_explains_loss": old_selector_explains_loss,
                "candidate_for_next_proxy": candidate,
                **top_product,
            }
        )
        for start_month, group in selected.groupby("requested_start_month", sort=True):
            by_start_rows.append(
                {
                    "condition": condition,
                    "label": spec["label"],
                    "requested_start_month": start_month,
                    "lot_count": int(len(group)),
                    "realized_pnl_sum": float(group["realized_pnl"].sum()),
                    "positive_pnl_sum": float(group.loc[group["realized_pnl"].gt(0), "realized_pnl"].sum()),
                    "negative_pnl_abs_sum": float(-group.loc[group["realized_pnl"].lt(0), "realized_pnl"].sum()),
                    "winner_rate": float(group["winner"].mean()),
                    "stage095_overlap_lot_count": int(group["stage095_risk_multiplier_ge2"].sum()),
                    "non_stage095_pnl_sum": float(group.loc[~group["stage095_risk_multiplier_ge2"], "realized_pnl"].sum()),
                }
            )
    summary = pd.DataFrame(rows).sort_values(
        ["candidate_for_next_proxy", "realized_pnl_sum", "lot_count"],
        ascending=[False, True, False],
    )
    by_start = pd.DataFrame(by_start_rows).sort_values(["condition", "requested_start_month"])
    return summary, by_start


def build_peer_comparison(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for peer_group, group in summary.groupby("peer_group", dropna=False):
        if len(group) < 2:
            continue
        sorted_group = group.sort_values("realized_pnl_sum")
        worst = sorted_group.iloc[0]
        best = sorted_group.iloc[-1]
        rows.append(
            {
                "peer_group": peer_group,
                "worst_condition": worst["condition"],
                "worst_label": worst["label"],
                "worst_lot_count": int(worst["lot_count"]),
                "worst_pnl": float(worst["realized_pnl_sum"]),
                "worst_non_stage095_pnl": float(worst["non_stage095_pnl_sum"]),
                "best_condition": best["condition"],
                "best_label": best["label"],
                "best_lot_count": int(best["lot_count"]),
                "best_pnl": float(best["realized_pnl_sum"]),
                "pnl_spread_worst_minus_best": float(worst["realized_pnl_sum"] - best["realized_pnl_sum"]),
            }
        )
    return pd.DataFrame(rows).sort_values("pnl_spread_worst_minus_best")


def build_top_loss_detail(context: pd.DataFrame) -> pd.DataFrame:
    focus = context[context["dd30_no_breakout_active_lt2_not_rm2"].fillna(False)].copy()
    if focus.empty:
        focus = context[context["dd30_no_breakout_active_lt2"].fillna(False)].copy()
    cols = [
        "requested_start_month",
        "lot_id",
        "vt_symbol",
        "product",
        "direction",
        "entry_date",
        "exit_date",
        "exit_reason",
        "realized_pnl",
        "r_multiple",
        "risk_multiplier",
        "active_positions_before",
        "ai_product_pool_rank",
        "selected_volume",
        "breakout",
        "portfolio_drawdown_pct",
        "entry_account_equity",
        "entry_under_initial_pct",
        "mfe_r",
        "mae_r",
    ]
    return focus.sort_values("realized_pnl").loc[:, [col for col in cols if col in focus.columns]].head(80)


def make_decision(
    summary: pd.DataFrame,
    peer: pd.DataFrame,
    context: pd.DataFrame,
    stage095_decision: dict[str, Any],
) -> dict[str, Any]:
    candidates = summary[summary["candidate_for_next_proxy"].astype(bool)].copy()
    best_condition = ""
    if not candidates.empty:
        best = candidates.sort_values(
            ["stage095_overlap_lot_count", "realized_pnl_sum", "negative_start_rate"],
            ascending=[True, True, False],
        ).iloc[0]
        best_condition = str(best["condition"])
        decision = "stage101_underwater_entry_quality_candidate_for_frozen_proxy"
        next_step = (
            f"只允许围绕 `{best_condition}` 做一次隔离 proxy/true-engine 验证；"
            "不得继续扫产品、方向、年份、DD 阈值、active 阈值或 breakout 阈值。"
        )
        continue_after = "有"
        continue_reason = (
            "closed-lot 审计出现非 Stage095 完全重叠的水下低持仓非突破形状，"
            "但它还没有账户曲线、复利、保证金释放和后续信号检验。"
        )
        overfit_after = (
            "否，但风险升高。候选来自预声明状态拆解，不按坏月份或产品挑选；"
            "下一步必须冻结一次验证，不能扩展成阈值搜索。"
        )
    else:
        decision = "stage101_no_nonoverlap_underwater_entry_candidate"
        next_step = (
            "不进入 true engine；当前水下入场质量负收益主要被 Stage095 已失败的 risk_multiplier 字段族解释，"
            "按 Stage096 exact panel DD30 修正后，其余非重叠条件不足以跨起点稳定。"
            "下一步应换到更底层的资金路径或外生信息源。"
        )
        continue_after = "有但需换层"
        continue_reason = "本阶段排除了把 active 低持仓/DD 深水下包装成新规则的风险；继续同字段救参会过拟合。"
        overfit_after = "否。只读拆解并显式扣除 Stage095 已失败字段；没有按品种、方向、月份或小数阈值救参。"
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": decision,
        "candidate_rule_count": int(len(candidates)),
        "best_condition": best_condition,
        "promote_to_true_engine": bool(not candidates.empty),
        "strategy_changed": False,
        "true_engine_run": False,
        "order_api_calls": 0,
        "ctp_connected": False,
        "closed_lot_count": int(len(context)),
        "panel_matched_lot_count": int(context["entry_account_equity"].notna().sum()),
        "stage094_dd30_lot_count": int(context["stage094_portfolio_dd30"].sum()),
        "stage096_panel_dd30_lot_count": int(context["panel_dd30"].sum()),
        "dd30_overlap_lot_count": int((context["stage094_portfolio_dd30"] & context["panel_dd30"]).sum()),
        "dd30_primary_source": "Stage096 exact-match exposure_panel.drawdown_depth_pct >= 30.0",
        "stage095_decision": str(stage095_decision.get("decision", "")),
        "stage095_failed_selector": "risk_multiplier>=2 / DD>=30% & risk_multiplier>=2 cap1 proxy failed in Stage095",
        "next_step": next_step,
        "overfit_after": overfit_after,
        "continue_after": continue_after,
        "continue_reason": continue_reason,
        "peer_groups": peer.to_dict(orient="records") if not peer.empty else [],
    }


def write_report(summary: pd.DataFrame, by_start: pd.DataFrame, peer: pd.DataFrame, detail: pd.DataFrame, decision: dict[str, Any]) -> None:
    research_rows = "\n".join(
        f"| {item['source']} | {item['url']} | {item['finding']} |" for item in EXTERNAL_RESEARCH
    )
    report = f"""# {STAGE} Underwater Entry Quality Decomposition Audit

## 外部调研与判断

| source | url | finding |
| --- | --- | --- |
{research_rows}

我的判断：趋势系统的水下治理不能只看减亏。Stage101 v2 只读拆解深回撤/低持仓/非突破/AI rank 的闭合 lot 表现，主水下口径改用 Stage096 exact-match panel DD，并显式扣除 Stage095 已失败的 `risk_multiplier>=2` 字段族，避免把旧失败规则换名重跑。

## Condition Summary

{_md_table(summary, 80)}

## Peer Comparison

{_md_table(peer, 80)}

## Condition By Start

{_md_table(by_start, 140)}

## Focus Top Loss Detail

{_md_table(detail, 80)}

## 决策

```json
{json.dumps(_json_safe(decision), ensure_ascii=False, indent=2)}
```

## 统计口径

- 输入：Stage094 closed lots + Stage096 exposure panel exact entry-date match。
- 水下定义：Stage096 exact-match `entry_panel_drawdown_depth_pct >= 30.0` 作为主口径；Stage094 `portfolio_drawdown_pct>=0.30` 只保留为审计字段；`entry_account_equity < entry_account_capital` 作为辅口径。
- Stage095 扣除：对每个条件统计 `stage095_overlap_*` 与 `non_stage095_pnl_sum`；如果负收益主要由 `risk_multiplier>=2` 解释，不视为新候选。
- 候选门槛：固定条件，且不得包含 Stage095 overlap；至少 `80` lots、`8` 起点、`4` 年、`8` 产品，非 Stage095 部分亏损小于 `-250,000`，负起点率不低于 `55%`，big winner PnL 占正收益不高于 `15%`，最大产品亏损占比不高于 `50%`。
- 限制：本阶段不是账户曲线，不重算复利、保证金释放、后续入场，也不连接 CTP/订单 API。

## 过拟合反思

- 运行前：否。条件来自水下状态和入场质量分解，不按产品/方向/月度坏窗口挑选。
- 运行后：{decision['overfit_after']}

## 继续价值反思

- 运行前：有。需要确认水下拖长是否来自可交易化的入场质量结构。
- 运行后：{decision['continue_after']}。{decision['continue_reason']}

## 输出

- lot_context：`{LOT_CONTEXT_PATH}`
- condition_summary：`{CONDITION_SUMMARY_PATH}`
- condition_by_start：`{CONDITION_BY_START_PATH}`
- peer_comparison：`{PEER_COMPARISON_PATH}`
- top_loss_detail：`{TOP_LOSS_DETAIL_PATH}`
- input_audit：`{INPUT_AUDIT_PATH}`
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def write_stage_record(summary: pd.DataFrame, by_start: pd.DataFrame, peer: pd.DataFrame, detail: pd.DataFrame, decision: dict[str, Any]) -> Path:
    now = datetime.now()
    path = STAGES_DIR / f"{now:%Y%m%d_%H%M}_stage101_underwater_entry_quality_decomposition_audit.md"
    text = f"""# Stage101 水下入场质量拆解审计 v2

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{now:%Y-%m-%d %H:%M} CST
- 工作区/分支：`{ROOT}`
- 阶段性质：只读 closed-lot / exposure-panel 归因；不重新跑策略；修正 v1 独立审查发现的 DD 口径问题
- 是否重要突破：{"是，发现候选下一步验证形状" if decision["candidate_rule_count"] else "否"}
- 是否触发A/B：否，本阶段不改策略也不与正式版做 A/B

## 外部调研与判断

- 参考资料：pysystemtrade backtesting、Man Group trend-following drawdown、Research Affiliates stop-loss framework。
- 我的判断：深回撤风控不能只压亏损，要核算是否把恢复期和右尾砍掉；本阶段只确认是否存在非 Stage095 字段族的新水下入场质量形状。

## 本次变更

- 新增脚本：无，本次沿用并修正 `research/lines/{LINE_ID}/tools/stage101_underwater_entry_quality_decomposition_audit.py`
- 修改脚本：主 DD30 从 Stage094 closed-lot `portfolio_drawdown_pct>=0.30` 改为 Stage096 exact-match panel `drawdown_depth_pct>=30.0`；新增 panel key 唯一性/merge 完整性断言；新增 Stage095 decision 断言；候选要求不得包含 Stage095 overlap。
- 删除脚本：无。
- 新增参数：无。
- 修改参数：`DD>=30%` 主口径改为 Stage096 exact panel DD；候选必须 `stage095_overlap_lot_count == 0`。
- 删除参数：无。

## 回测/归因参数

- 输入：Stage094 closed lots；Stage096 exposure panel。
- 账户规模：沿用 Stage167/Stage094 `150,000`；本阶段不重算账户曲线。
- 成本口径：沿用 closed-lot realized PnL。
- 样本过滤：2020-01 到 2026-01 逐半年起点，终点 2026-06-30 的 Stage094 闭合 lot。
- 策略/归因口径：只读条件拆解；`risk_multiplier>=2` 作为 Stage095 已失败字段族显式剔除/标记；Stage094 DD 只作审计对照。

## Condition Summary

{_md_table(summary, 80)}

## Peer Comparison

{_md_table(peer, 80)}

## Condition By Start

{_md_table(by_start, 140)}

## Focus Top Loss Detail

{_md_table(detail, 80)}

## 结论

- 本阶段结论：`{decision['decision']}`。
- 候选数：`{decision['candidate_rule_count']}`。
- 最优候选：`{decision['best_condition']}`。
- 是否进入 true engine：`{decision['promote_to_true_engine']}`。
- 下一步：{decision['next_step']}

## 回测记录字段

- 期末权益/总收益/最大回撤/Sharpe/总滑点/总交易次数/胜率：本阶段不是新策略曲线，不新增这些汇总。
- closed_lot_count：`{decision['closed_lot_count']}`
- panel_matched_lot_count：`{decision['panel_matched_lot_count']}`
- stage094_dd30_lot_count：`{decision['stage094_dd30_lot_count']}`
- stage096_panel_dd30_lot_count：`{decision['stage096_panel_dd30_lot_count']}`
- dd30_overlap_lot_count：`{decision['dd30_overlap_lot_count']}`

## 过拟合反思

- 运行前判断：否。
- 运行后判断：{decision['overfit_after']}

## 继续价值反思

- 运行前判断：有。
- 运行后判断：{decision['continue_after']}
- 原因：{decision['continue_reason']}

## 合入建议

- 是否更新本线 `LINE.md`：否，等独立 agent 审查。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段只是候选资格审计。
"""
    path.write_text(text, encoding="utf-8")
    return path


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    context = load_lot_context()
    stage095_decision = load_stage095_decision()
    summary, by_start = summarize_conditions(context)
    peer = build_peer_comparison(summary)
    detail = build_top_loss_detail(context)
    input_audit = _input_audit([CLOSED_LOTS_PATH, EXPOSURE_PANEL_PATH, STAGE095_DECISION_PATH])
    decision = make_decision(summary, peer, context, stage095_decision)

    context.to_csv(LOT_CONTEXT_PATH, index=False, encoding="utf-8-sig", compression="gzip")
    summary.to_csv(CONDITION_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    by_start.to_csv(CONDITION_BY_START_PATH, index=False, encoding="utf-8-sig")
    peer.to_csv(PEER_COMPARISON_PATH, index=False, encoding="utf-8-sig")
    detail.to_csv(TOP_LOSS_DETAIL_PATH, index=False, encoding="utf-8-sig")
    input_audit.to_csv(INPUT_AUDIT_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(summary, by_start, peer, detail, decision)
    stage_path = write_stage_record(summary, by_start, peer, detail, decision)
    print(
        json.dumps(
            _json_safe({"decision": decision, "stage_path": stage_path, "report_path": REPORT_PATH}),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
