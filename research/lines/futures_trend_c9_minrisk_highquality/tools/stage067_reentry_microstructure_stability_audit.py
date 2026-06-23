from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
import re
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage067"
MODEL_TAG = "stage067_reentry_microstructure_stability_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage067_c9_minrisk_reentry_microstructure_stability_audit"

OFFICIAL_ARM = "A_official_stage847_c9_15w"
INITIAL_CAPITAL = 150_000.0

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
if str(EXAMPLE_DIR) not in sys.path:
    sys.path.insert(0, str(EXAMPLE_DIR))

from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage067_reentry_microstructure_stability_audit"
STAGE066_DIR = LINE_DIR / "outputs" / "stage066_tick_microstructure_expansion_attempt"
STAGE046_DIR = LINE_DIR / "outputs" / "stage046_entry_day_confirmed_breakeven_true_engine"

FEATURES_IN = (
    STAGE066_DIR
    / "qmt_roll_stage066_c9_minrisk_tick_microstructure_expansion_attempt_event_microstructure_features_"
    "stage066_tick_microstructure_expansion_attempt_v1.csv"
)
OFFICIAL_CURVE_IN = (
    STAGE046_DIR
    / "qmt_roll_stage046_c9_minrisk_entry_day_confirmed_breakeven_true_engine_curve_"
    "stage046_entry_day_confirmed_breakeven_true_engine_v1.csv"
)

EVENTS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_events_{MODEL_TAG}.csv"
FEATURE_STABILITY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_stability_{MODEL_TAG}.csv"
LEAVE_ONE_YEAR_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_leave_one_year_{MODEL_TAG}.csv"
FAMILY_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_family_summary_{MODEL_TAG}.csv"
YEAR_FAMILY_MATRIX_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_family_matrix_{MODEL_TAG}.csv"
SCORE_BUCKET_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_score_bucket_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_score_chart_{MODEL_TAG}.png"
STABILITY_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_stability_chart_{MODEL_TAG}.png"
TAIL_SCATTER_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_tail_protection_scatter_{MODEL_TAG}.png"
FAMILY_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_family_heatmap_{MODEL_TAG}.png"
ATLAS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_tail_microstructure_atlas_{MODEL_TAG}.png"


PRODUCT_FAMILY: dict[str, tuple[str, str]] = {
    "CY.CZCE": ("soft_agri", "棉纺软商品"),
    "SR.CZCE": ("soft_agri", "糖棉软商品"),
    "PK.CZCE": ("grains_oilseeds", "油脂油料/农产品"),
    "a.DCE": ("grains_oilseeds", "油脂油料/农产品"),
    "c.DCE": ("grains_oilseeds", "谷物/农产品"),
    "cs.DCE": ("grains_oilseeds", "谷物/农产品"),
    "m.DCE": ("grains_oilseeds", "油脂油料/农产品"),
    "p.DCE": ("grains_oilseeds", "油脂油料/农产品"),
    "y.DCE": ("grains_oilseeds", "油脂油料/农产品"),
    "rr.DCE": ("grains_oilseeds", "谷物/农产品"),
    "jd.DCE": ("livestock", "畜禽农产品"),
    "sc.INE": ("energy_oil", "原油能源"),
    "lu.INE": ("energy_oil", "燃油能源"),
    "bu.SHFE": ("energy_oil", "沥青能源"),
    "pg.DCE": ("energy_oil", "LPG能源"),
    "TA.CZCE": ("petrochem", "聚酯化工"),
    "PF.CZCE": ("petrochem", "聚酯化工"),
    "PX.CZCE": ("petrochem", "芳烃化工"),
    "UR.CZCE": ("petrochem", "尿素化工"),
    "eb.DCE": ("petrochem", "苯乙烯化工"),
    "v.DCE": ("petrochem", "PVC化工"),
    "br.SHFE": ("rubber", "橡胶"),
    "nr.INE": ("rubber", "橡胶"),
    "i.DCE": ("black_ferrous", "黑色矿石焦煤"),
    "j.DCE": ("black_ferrous", "黑色焦煤焦炭"),
    "SF.CZCE": ("black_ferrous", "铁合金"),
    "ag.SHFE": ("precious_metals", "贵金属"),
    "al.SHFE": ("base_metals", "有色金属"),
    "ao.SHFE": ("base_metals", "有色金属"),
    "bc.INE": ("base_metals", "有色金属"),
    "ni.SHFE": ("base_metals", "有色金属"),
    "pb.SHFE": ("base_metals", "有色金属"),
    "sn.SHFE": ("base_metals", "有色金属"),
    "ss.SHFE": ("base_metals", "不锈钢金属"),
    "zn.SHFE": ("base_metals", "有色金属"),
    "IH.CFFEX": ("financial_index", "股指"),
    "PR.CZCE": ("other", "其他新品种"),
    "fb.DCE": ("other", "板材其他"),
    "AP.CZCE": ("soft_agri", "apple soft/agri"),
    "CF.CZCE": ("soft_agri", "cotton soft/agri"),
    "FG.CZCE": ("black_ferrous", "glass construction chain"),
    "MA.CZCE": ("petrochem", "methanol petrochem"),
    "OI.CZCE": ("grains_oilseeds", "rapeseed oil"),
    "SA.CZCE": ("petrochem", "soda ash chemical"),
    "SH.CZCE": ("petrochem", "caustic soda chemical"),
    "SM.CZCE": ("black_ferrous", "silicomanganese"),
    "au.SHFE": ("precious_metals", "gold"),
    "cu.SHFE": ("base_metals", "copper"),
    "fu.SHFE": ("energy_oil", "fuel oil"),
    "hc.SHFE": ("black_ferrous", "hot rolled coil"),
    "rb.SHFE": ("black_ferrous", "rebar"),
    "ru.SHFE": ("rubber", "rubber"),
    "sp.SHFE": ("other", "pulp"),
    "jm.DCE": ("black_ferrous", "coking coal"),
    "lh.DCE": ("livestock", "live hog"),
    "lc.GFEX": ("base_metals", "battery metal"),
    "si.GFEX": ("base_metals", "industrial silicon"),
}


FEATURE_SPECS: dict[str, dict[str, Any]] = {
    # expected_sign is a first-principles diagnostic orientation, not a fitted trading rule.
    "open_interest_delta_target": {
        "label": "OI delta, lower less crowded",
        "expected_sign": -1,
        "score_feature": True,
    },
    "median_spread_r": {
        "label": "median spread / risk, lower cheaper",
        "expected_sign": -1,
        "score_feature": True,
    },
    "p90_spread_r": {
        "label": "p90 spread / risk, lower cheaper",
        "expected_sign": -1,
        "score_feature": True,
    },
    "median_depth1_log": {
        "label": "top-book depth, higher more liquid",
        "expected_sign": 1,
        "score_feature": True,
    },
    "median_directional_book_imbalance": {
        "label": "directional book imbalance, higher supportive",
        "expected_sign": 1,
        "score_feature": True,
    },
    "directional_mid_move_r": {
        "label": "target-minute directional mid move, higher supportive",
        "expected_sign": 1,
        "score_feature": True,
    },
    "directional_last_move_r": {
        "label": "target-minute directional last move, higher supportive",
        "expected_sign": 1,
        "score_feature": True,
    },
    "volume_delta_target": {
        "label": "target-minute volume delta, diagnostic only",
        "expected_sign": 0,
        "score_feature": False,
    },
    "amount_delta_target": {
        "label": "target-minute amount delta, diagnostic only",
        "expected_sign": 0,
        "score_feature": False,
    },
    "median_book_imbalance": {
        "label": "raw book imbalance, diagnostic only",
        "expected_sign": 0,
        "score_feature": False,
    },
}

RIGHT_TAIL_WATCH_EVENTS = {"BACKTESTING.424", "BACKTESTING.570", "BACKTESTING.749"}
BAD_TAIL_WATCH_EVENTS = {"BACKTESTING.529", "BACKTESTING.708"}


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    return value


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _safe_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    display = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    for column in display.columns:
        if pd.api.types.is_float_dtype(display[column]):
            display[column] = display[column].map(lambda value: "" if pd.isna(value) else f"{value:.4f}")
    lines = [
        "| " + " | ".join(str(column) for column in display.columns) + " |",
        "| " + " | ".join(["---"] * len(display.columns)) + " |",
    ]
    for _, row in display.iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in display.columns) + " |")
    return "\n".join(lines)


def _normalize_product(vt_symbol: Any) -> str:
    symbol = "" if pd.isna(vt_symbol) else str(vt_symbol)
    if "." not in symbol:
        return symbol or "UNKNOWN"
    code, exchange = symbol.split(".", 1)
    match = re.match(r"^([A-Za-z]+)", code)
    if not match:
        return symbol
    return f"{match.group(1)}.{exchange}"


def _product_family(product: str) -> tuple[str, str]:
    if product in PRODUCT_FAMILY:
        return PRODUCT_FAMILY[product]
    return ("unknown", "未分类")


def _load_features() -> pd.DataFrame:
    features = _read_csv(FEATURES_IN)
    required = {
        "event_key",
        "vt_symbol",
        "normalized_product",
        "direction",
        "direction_sign",
        "reentry_year",
        "reentry_time",
        "reentry_lot_pnl",
        "risk_price",
        "microstructure_ready",
        "tick_file_path",
    } | set(FEATURE_SPECS)
    missing = required - set(features.columns)
    if missing:
        raise RuntimeError(f"Stage066 features missing columns: {sorted(missing)}")
    features["event_key"] = features["event_key"].astype(str)
    features["vt_symbol"] = features["vt_symbol"].astype(str)
    features["normalized_product"] = features["vt_symbol"].map(_normalize_product)
    features["reentry_time"] = pd.to_datetime(features["reentry_time"], errors="coerce")
    features["reentry_year"] = pd.to_numeric(features["reentry_year"], errors="coerce").astype("Int64")
    features["reentry_lot_pnl"] = _safe_num(features["reentry_lot_pnl"]).fillna(0.0)
    features["risk_price"] = _safe_num(features["risk_price"])
    features["microstructure_ready"] = features["microstructure_ready"].astype(bool)
    for col in FEATURE_SPECS:
        features[col] = _safe_num(features[col])
    family_rows = [_product_family(product) for product in features["normalized_product"].astype(str)]
    features["product_family"] = [item[0] for item in family_rows]
    features["product_family_note"] = [item[1] for item in family_rows]
    features["is_right_tail_watch"] = features["event_key"].isin(RIGHT_TAIL_WATCH_EVENTS)
    features["is_bad_tail_watch"] = features["event_key"].isin(BAD_TAIL_WATCH_EVENTS)
    features["tail_watch_role"] = np.select(
        [features["is_right_tail_watch"], features["is_bad_tail_watch"]],
        ["right_tail_watch", "bad_tail_watch"],
        default="other",
    )
    return features.sort_values(["reentry_time", "event_key"]).reset_index(drop=True)


def _load_official_curve() -> pd.DataFrame:
    curve = _read_csv(OFFICIAL_CURVE_IN)
    if "arm" not in curve.columns:
        raise RuntimeError("official curve missing arm column")
    curve = curve[curve["arm"].eq(OFFICIAL_ARM)].copy()
    if curve.empty:
        raise RuntimeError(f"official curve arm is empty: {OFFICIAL_ARM}")
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce")
    return curve.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)


def _equity_metrics(curve: pd.DataFrame) -> dict[str, float | str]:
    equity = curve["account_equity"].astype(float).reset_index(drop=True)
    drawdown = (equity / equity.cummax() - 1.0) * 100.0
    returns = equity.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    ret_std = returns.std(ddof=0)
    sharpe = float(returns.mean() / ret_std * np.sqrt(252.0)) if ret_std and ret_std > 0 else np.nan
    trough_idx = int(drawdown.idxmin())
    nonzero = curve[curve["net_pnl"].ne(0)]
    return {
        "end_equity": float(equity.iloc[-1]),
        "total_return_pct": float((equity.iloc[-1] / INITIAL_CAPITAL - 1.0) * 100.0),
        "max_dd_pct": float(drawdown.min()),
        "max_dd_date": curve["date"].iloc[trough_idx].strftime("%Y-%m-%d"),
        "sharpe": sharpe,
        "total_slippage": float(curve["slippage"].sum()),
        "total_trade_count": float(curve["trade_count"].sum()),
        "win_rate_pct": float((nonzero["net_pnl"] > 0).mean() * 100.0) if len(nonzero) else np.nan,
        "max_broker10_margin_to_equity_pct": float(curve["broker10_margin_to_equity_pct"].max()),
        "days_over_100pct": float((curve["broker10_margin_to_equity_pct"] > 100.0).sum()),
    }


def _feature_corr(sample: pd.DataFrame, feature: str) -> float:
    data = sample[[feature, "reentry_lot_pnl"]].dropna()
    if len(data) < 3 or data[feature].nunique() <= 1:
        return np.nan
    return float(data[feature].corr(data["reentry_lot_pnl"], method="spearman"))


def _sign(value: float) -> int:
    if pd.isna(value) or value == 0:
        return 0
    return 1 if value > 0 else -1


def _add_predeclared_score(features: pd.DataFrame) -> pd.DataFrame:
    data = features.copy()
    ready = data[data["microstructure_ready"]].copy()
    for feature, spec in FEATURE_SPECS.items():
        if not spec["score_feature"]:
            continue
        expected_sign = int(spec["expected_sign"])
        threshold = ready[feature].median()
        if pd.isna(threshold):
            threshold = np.nan
        score_col = f"{feature}_supportive_stage067"
        if expected_sign > 0:
            data[score_col] = data[feature].ge(threshold)
        elif expected_sign < 0:
            data[score_col] = data[feature].le(threshold)
        else:
            data[score_col] = False
        data.loc[data[feature].isna(), score_col] = False
        data[score_col] = data[score_col].astype(int)
    score_cols = [f"{feature}_supportive_stage067" for feature, spec in FEATURE_SPECS.items() if spec["score_feature"]]
    data["predeclared_microstructure_score"] = data[score_cols].sum(axis=1)
    data["predeclared_microstructure_score_max"] = len(score_cols)
    data["predeclared_microstructure_bucket"] = pd.cut(
        data["predeclared_microstructure_score"],
        bins=[-0.1, 2.0, 4.0, len(score_cols) + 0.1],
        labels=["headwind_low_score", "mixed_mid_score", "supportive_high_score"],
    ).astype(str)
    return data


def _build_feature_stability(features: pd.DataFrame) -> pd.DataFrame:
    ready = features[features["microstructure_ready"]].copy()
    rows: list[dict[str, Any]] = []
    for feature, spec in FEATURE_SPECS.items():
        expected_sign = int(spec["expected_sign"])
        sample = ready[[feature, "reentry_lot_pnl"]].dropna()
        global_spearman = _feature_corr(ready, feature)
        global_sign = _sign(global_spearman)

        yearly_signs: list[int] = []
        yearly_corrs: list[float] = []
        for _, group in ready.groupby("reentry_year", dropna=True):
            corr = _feature_corr(group, feature)
            if pd.notna(corr):
                yearly_corrs.append(float(corr))
                yearly_signs.append(_sign(corr))

        family_signs: list[int] = []
        family_corrs: list[float] = []
        for _, group in ready.groupby("product_family", dropna=True):
            corr = _feature_corr(group, feature)
            if pd.notna(corr):
                family_corrs.append(float(corr))
                family_signs.append(_sign(corr))

        rows.append(
            {
                "feature": feature,
                "label": spec["label"],
                "score_feature": bool(spec["score_feature"]),
                "n": int(len(sample)),
                "unique_count": int(sample[feature].nunique()) if not sample.empty else 0,
                "expected_sign": expected_sign,
                "global_spearman_to_pnl": global_spearman,
                "global_sign": global_sign,
                "global_matches_expected": int(expected_sign != 0 and global_sign == expected_sign),
                "year_corr_count": int(len(yearly_corrs)),
                "year_sign_agree_global_count": int(sum(1 for sign in yearly_signs if sign != 0 and sign == global_sign)),
                "year_sign_agree_global_pct": float(sum(1 for sign in yearly_signs if sign != 0 and sign == global_sign) / len(yearly_signs) * 100.0)
                if yearly_signs
                else np.nan,
                "year_sign_agree_expected_count": int(sum(1 for sign in yearly_signs if expected_sign != 0 and sign == expected_sign)),
                "year_sign_agree_expected_pct": float(sum(1 for sign in yearly_signs if expected_sign != 0 and sign == expected_sign) / len(yearly_signs) * 100.0)
                if yearly_signs
                else np.nan,
                "family_corr_count": int(len(family_corrs)),
                "family_sign_agree_global_count": int(sum(1 for sign in family_signs if sign != 0 and sign == global_sign)),
                "family_sign_agree_global_pct": float(sum(1 for sign in family_signs if sign != 0 and sign == global_sign) / len(family_signs) * 100.0)
                if family_signs
                else np.nan,
                "family_sign_agree_expected_count": int(sum(1 for sign in family_signs if expected_sign != 0 and sign == expected_sign)),
                "family_sign_agree_expected_pct": float(sum(1 for sign in family_signs if expected_sign != 0 and sign == expected_sign) / len(family_signs) * 100.0)
                if family_signs
                else np.nan,
                "year_corr_min": float(np.nanmin(yearly_corrs)) if yearly_corrs else np.nan,
                "year_corr_max": float(np.nanmax(yearly_corrs)) if yearly_corrs else np.nan,
                "family_corr_min": float(np.nanmin(family_corrs)) if family_corrs else np.nan,
                "family_corr_max": float(np.nanmax(family_corrs)) if family_corrs else np.nan,
            }
        )
    stability = pd.DataFrame(rows)
    return stability.sort_values(["score_feature", "global_matches_expected", "feature"], ascending=[False, False, True])


def _build_leave_one_year(features: pd.DataFrame) -> pd.DataFrame:
    ready = features[features["microstructure_ready"]].copy()
    years = sorted(int(year) for year in ready["reentry_year"].dropna().unique())
    rows: list[dict[str, Any]] = []
    for feature, spec in FEATURE_SPECS.items():
        for year in years:
            train = ready[ready["reentry_year"].ne(year)].copy()
            holdout = ready[ready["reentry_year"].eq(year)].copy()
            train_sample = train[[feature, "reentry_lot_pnl"]].dropna()
            hold_sample = holdout[[feature, "reentry_lot_pnl"]].dropna()
            train_spearman = _feature_corr(train_sample, feature)
            train_sign = _sign(train_spearman)
            if train_sign == 0 and int(spec["expected_sign"]) != 0:
                train_sign = int(spec["expected_sign"])
            train_median = train_sample[feature].median() if not train_sample.empty else np.nan
            if len(hold_sample) == 0 or pd.isna(train_median) or train_sign == 0:
                rows.append(
                    {
                        "feature": feature,
                        "holdout_year": year,
                        "train_n": int(len(train_sample)),
                        "holdout_n": int(len(hold_sample)),
                        "train_spearman": train_spearman,
                        "train_sign": train_sign,
                        "train_median": train_median,
                        "favorable_count": 0,
                        "unfavorable_count": 0,
                        "favorable_pnl": 0.0,
                        "unfavorable_pnl": 0.0,
                        "favorable_mean_pnl": np.nan,
                        "unfavorable_mean_pnl": np.nan,
                        "holdout_mean_edge": np.nan,
                        "holdout_edge_positive": np.nan,
                    }
                )
                continue
            score = hold_sample[feature] * train_sign
            favorable = hold_sample[score >= train_median * train_sign]
            unfavorable = hold_sample[score < train_median * train_sign]
            fav_mean = favorable["reentry_lot_pnl"].mean() if len(favorable) else np.nan
            unfav_mean = unfavorable["reentry_lot_pnl"].mean() if len(unfavorable) else np.nan
            edge = fav_mean - unfav_mean if pd.notna(fav_mean) and pd.notna(unfav_mean) else np.nan
            rows.append(
                {
                    "feature": feature,
                    "holdout_year": year,
                    "train_n": int(len(train_sample)),
                    "holdout_n": int(len(hold_sample)),
                    "train_spearman": train_spearman,
                    "train_sign": train_sign,
                    "train_median": train_median,
                    "favorable_count": int(len(favorable)),
                    "unfavorable_count": int(len(unfavorable)),
                    "favorable_pnl": float(favorable["reentry_lot_pnl"].sum()) if len(favorable) else 0.0,
                    "unfavorable_pnl": float(unfavorable["reentry_lot_pnl"].sum()) if len(unfavorable) else 0.0,
                    "favorable_mean_pnl": float(fav_mean) if pd.notna(fav_mean) else np.nan,
                    "unfavorable_mean_pnl": float(unfav_mean) if pd.notna(unfav_mean) else np.nan,
                    "holdout_mean_edge": float(edge) if pd.notna(edge) else np.nan,
                    "holdout_edge_positive": int(edge > 0) if pd.notna(edge) else np.nan,
                }
            )
    return pd.DataFrame(rows)


def _build_score_bucket_summary(features: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    total_positive = float(features.loc[features["reentry_lot_pnl"] > 0, "reentry_lot_pnl"].sum())
    total_negative_abs = float(-features.loc[features["reentry_lot_pnl"] < 0, "reentry_lot_pnl"].sum())
    for bucket, group in features.groupby("predeclared_microstructure_bucket", dropna=False):
        positive = float(group.loc[group["reentry_lot_pnl"] > 0, "reentry_lot_pnl"].sum())
        negative_abs = float(-group.loc[group["reentry_lot_pnl"] < 0, "reentry_lot_pnl"].sum())
        rows.append(
            {
                "score_bucket": bucket,
                "event_count": int(len(group)),
                "product_count": int(group["normalized_product"].nunique()),
                "family_count": int(group["product_family"].nunique()),
                "year_count": int(group["reentry_year"].nunique()),
                "net_reentry_lot_pnl": float(group["reentry_lot_pnl"].sum()),
                "positive_pnl": positive,
                "negative_pnl_abs": negative_abs,
                "positive_coverage_pct": positive / total_positive * 100.0 if total_positive else np.nan,
                "negative_abs_coverage_pct": negative_abs / total_negative_abs * 100.0 if total_negative_abs else np.nan,
                "right_tail_watch_count": int(group["is_right_tail_watch"].sum()),
                "bad_tail_watch_count": int(group["is_bad_tail_watch"].sum()),
                "median_score": float(group["predeclared_microstructure_score"].median()),
            }
        )
    return pd.DataFrame(rows).sort_values("score_bucket")


def _build_family_summary(features: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for family, group in features.groupby("product_family", dropna=False):
        rows.append(
            {
                "product_family": family,
                "family_note": str(group["product_family_note"].iloc[0]) if len(group) else "",
                "event_count": int(len(group)),
                "product_count": int(group["normalized_product"].nunique()),
                "year_count": int(group["reentry_year"].nunique()),
                "net_reentry_lot_pnl": float(group["reentry_lot_pnl"].sum()),
                "positive_pnl": float(group.loc[group["reentry_lot_pnl"] > 0, "reentry_lot_pnl"].sum()),
                "negative_pnl_abs": float(-group.loc[group["reentry_lot_pnl"] < 0, "reentry_lot_pnl"].sum()),
                "median_predeclared_score": float(group["predeclared_microstructure_score"].median()),
                "headwind_event_count": int(group["predeclared_microstructure_bucket"].eq("headwind_low_score").sum()),
                "supportive_event_count": int(group["predeclared_microstructure_bucket"].eq("supportive_high_score").sum()),
            }
        )
    return pd.DataFrame(rows).sort_values("net_reentry_lot_pnl", ascending=False)


def _build_year_family_matrix(features: pd.DataFrame) -> pd.DataFrame:
    matrix = (
        features.groupby(["reentry_year", "product_family"], dropna=False)
        .agg(
            event_count=("event_key", "size"),
            net_reentry_lot_pnl=("reentry_lot_pnl", "sum"),
            median_predeclared_score=("predeclared_microstructure_score", "median"),
        )
        .reset_index()
    )
    return matrix.sort_values(["reentry_year", "product_family"])


def _build_decision(
    features: pd.DataFrame,
    stability: pd.DataFrame,
    leave_year: pd.DataFrame,
    bucket_summary: pd.DataFrame,
    official_metrics: dict[str, Any],
) -> dict[str, Any]:
    score_features = stability[stability["score_feature"]].copy()
    loyo_summary = (
        leave_year.groupby("feature", as_index=False)
        .agg(
            loyo_years=("holdout_edge_positive", lambda s: int(s.notna().sum())),
            loyo_positive_years=("holdout_edge_positive", lambda s: int(pd.to_numeric(s, errors="coerce").fillna(0).sum())),
            median_holdout_mean_edge=("holdout_mean_edge", "median"),
        )
    )
    score_features = score_features.merge(loyo_summary, on="feature", how="left")
    score_features["loyo_positive_year_pct"] = np.where(
        score_features["loyo_years"] > 0,
        score_features["loyo_positive_years"] / score_features["loyo_years"] * 100.0,
        np.nan,
    )

    stable_feature_count = int(
        (
            score_features["global_matches_expected"].eq(1)
            & score_features["loyo_positive_year_pct"].ge(60.0)
            & score_features["family_sign_agree_expected_pct"].ge(60.0)
        ).sum()
    )

    right_tail = features[features["is_right_tail_watch"]].copy()
    bad_tail = features[features["is_bad_tail_watch"]].copy()
    right_tail_protected = right_tail["predeclared_microstructure_bucket"].eq("supportive_high_score")
    bad_tail_identified = bad_tail["predeclared_microstructure_bucket"].eq("headwind_low_score")

    high_bucket = bucket_summary[bucket_summary["score_bucket"].eq("supportive_high_score")]
    low_bucket = bucket_summary[bucket_summary["score_bucket"].eq("headwind_low_score")]
    high_net = float(high_bucket["net_reentry_lot_pnl"].iloc[0]) if not high_bucket.empty else 0.0
    low_net = float(low_bucket["net_reentry_lot_pnl"].iloc[0]) if not low_bucket.empty else 0.0

    pass_gates = {
        "stable_score_feature_count_ge3": stable_feature_count >= 3,
        "all_named_right_tail_watch_supportive": bool(len(right_tail) == len(RIGHT_TAIL_WATCH_EVENTS) and right_tail_protected.all()),
        "all_named_bad_tail_watch_headwind": bool(len(bad_tail) == len(BAD_TAIL_WATCH_EVENTS) and bad_tail_identified.all()),
        "supportive_bucket_net_positive": high_net > 0,
        "headwind_bucket_net_negative": low_net < 0,
    }
    pass_count = int(sum(bool(value) for value in pass_gates.values()))
    passed = all(pass_gates.values())
    decision = "stage067_reentry_microstructure_stability_failed_stop_rule_path" if not passed else "stage067_reentry_microstructure_stability_watch_only_no_engine_yet"
    next_step = (
        "stop_reentry_microstructure_rule_path_and_move_to_stage045_initial_entry_tick_coverage_audit"
        if not passed
        else "prepare_predeclared_stage068_watch_protocol_before_any_true_engine"
    )

    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "decision": decision,
        "next_step": next_step,
        "strategy_rule_created": False,
        "true_engine_run": False,
        "ab_triggered": False,
        "official_metrics": official_metrics,
        "event_count": int(len(features)),
        "microstructure_ready_count": int(features["microstructure_ready"].sum()),
        "product_count": int(features["normalized_product"].nunique()),
        "family_count": int(features["product_family"].nunique()),
        "year_count": int(features["reentry_year"].nunique()),
        "stable_score_feature_count": stable_feature_count,
        "pass_gates": pass_gates,
        "pass_count": pass_count,
        "pass_total": len(pass_gates),
        "right_tail_watch": right_tail[
            [
                "event_key",
                "vt_symbol",
                "reentry_lot_pnl",
                "predeclared_microstructure_score",
                "predeclared_microstructure_bucket",
            ]
        ].to_dict("records"),
        "bad_tail_watch": bad_tail[
            [
                "event_key",
                "vt_symbol",
                "reentry_lot_pnl",
                "predeclared_microstructure_score",
                "predeclared_microstructure_bucket",
            ]
        ].to_dict("records"),
        "score_bucket_summary": bucket_summary.to_dict("records"),
        "feature_summary": score_features[
            [
                "feature",
                "global_spearman_to_pnl",
                "global_matches_expected",
                "loyo_positive_year_pct",
                "family_sign_agree_expected_pct",
                "median_holdout_mean_edge",
            ]
        ].to_dict("records"),
    }


def _interp_equity_at_events(curve: pd.DataFrame, event_time: pd.Series) -> np.ndarray:
    curve_x = curve["date"].astype("int64").to_numpy(dtype=float)
    curve_y = (curve["account_equity"] / 1_000_000.0).to_numpy(dtype=float)
    event_x = pd.to_datetime(event_time).astype("int64").to_numpy(dtype=float)
    return np.interp(event_x, curve_x, curve_y)


def _plot_path(features: pd.DataFrame, curve: pd.DataFrame) -> None:
    events = features.dropna(subset=["reentry_time"]).sort_values("reentry_time").copy()
    bucket_colors = {
        "supportive_high_score": "#009e73",
        "mixed_mid_score": "#0072b2",
        "headwind_low_score": "#d55e00",
    }
    fig, axes = plt.subplots(3, 1, figsize=(14, 12), sharex=False)

    axes[0].plot(curve["date"], curve["account_equity"] / 1_000_000.0, color="#1f77b4", linewidth=2.0)
    for bucket, group in events.groupby("predeclared_microstructure_bucket"):
        axes[0].scatter(
            group["reentry_time"],
            _interp_equity_at_events(curve, group["reentry_time"]),
            s=34 + group["predeclared_microstructure_score"] * 8,
            color=bucket_colors.get(bucket, "#999999"),
            alpha=0.82,
            label=bucket,
            edgecolor="white",
            linewidth=0.5,
        )
    axes[0].set_title("Official C9/15w equity path with Stage067 predeclared microstructure buckets")
    axes[0].set_ylabel("Equity (million CNY)")
    axes[0].grid(alpha=0.25)
    axes[0].legend(loc="upper left", fontsize=8)

    for bucket, group in events.groupby("predeclared_microstructure_bucket"):
        group = group.sort_values("reentry_time").copy()
        group["cum_pnl"] = group["reentry_lot_pnl"].cumsum()
        axes[1].plot(
            group["reentry_time"],
            group["cum_pnl"] / 10_000.0,
            marker="o",
            linewidth=1.7,
            color=bucket_colors.get(bucket, "#999999"),
            label=bucket,
        )
    axes[1].axhline(0, color="black", linewidth=0.8)
    axes[1].set_title("Cumulative reentry-lot PnL by fixed score bucket (diagnostic, not a strategy curve)")
    axes[1].set_ylabel("Cumulative PnL (10k CNY)")
    axes[1].grid(alpha=0.25)
    axes[1].legend(loc="upper left", fontsize=8)

    axes[2].plot(curve["date"], curve["drawdown_pct"], color="#6a3d9a", linewidth=1.8, label="official drawdown")
    tail = events[events["tail_watch_role"].ne("other")]
    if not tail.empty:
        tail_y = np.interp(
            pd.to_datetime(tail["reentry_time"]).astype("int64").to_numpy(dtype=float),
            curve["date"].astype("int64").to_numpy(dtype=float),
            curve["drawdown_pct"].to_numpy(dtype=float),
        )
        for role, marker, color in [
            ("right_tail_watch", "^", "#009e73"),
            ("bad_tail_watch", "v", "#d55e00"),
        ]:
            sub = tail[tail["tail_watch_role"].eq(role)]
            if sub.empty:
                continue
            sub_y = np.interp(
                pd.to_datetime(sub["reentry_time"]).astype("int64").to_numpy(dtype=float),
                curve["date"].astype("int64").to_numpy(dtype=float),
                curve["drawdown_pct"].to_numpy(dtype=float),
            )
            axes[2].scatter(sub["reentry_time"], sub_y, marker=marker, s=90, color=color, label=role, edgecolor="black")
            for x, y, label in zip(sub["reentry_time"], sub_y, sub["vt_symbol"]):
                axes[2].annotate(label, (x, y), xytext=(4, 4), textcoords="offset points", fontsize=7)
    axes[2].set_title("Official drawdown path with named right-tail and bad-tail checks")
    axes[2].set_ylabel("Drawdown (%)")
    axes[2].grid(alpha=0.25)
    axes[2].legend(loc="lower left", fontsize=8)

    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=180)
    plt.close(fig)


def _plot_stability(stability: pd.DataFrame, leave_year: pd.DataFrame) -> None:
    score_features = stability[stability["score_feature"]].copy()
    loyo = (
        leave_year.groupby("feature", as_index=False)
        .agg(
            loyo_positive_years=("holdout_edge_positive", lambda s: int(pd.to_numeric(s, errors="coerce").fillna(0).sum())),
            loyo_years=("holdout_edge_positive", lambda s: int(s.notna().sum())),
            median_holdout_mean_edge=("holdout_mean_edge", "median"),
        )
    )
    loyo["loyo_positive_year_pct"] = np.where(loyo["loyo_years"] > 0, loyo["loyo_positive_years"] / loyo["loyo_years"] * 100.0, np.nan)
    data = score_features.merge(loyo, on="feature", how="left")
    data = data.sort_values("global_spearman_to_pnl")
    y = np.arange(len(data))

    fig, axes = plt.subplots(1, 3, figsize=(16, 6), sharey=True)
    colors = np.where(data["global_matches_expected"].eq(1), "#009e73", "#d55e00")
    axes[0].barh(y, data["global_spearman_to_pnl"], color=colors)
    axes[0].axvline(0, color="black", linewidth=0.8)
    axes[0].set_yticks(y)
    axes[0].set_yticklabels(data["feature"], fontsize=8)
    axes[0].set_title("Global Spearman vs reentry PnL")
    axes[0].grid(axis="x", alpha=0.25)

    axes[1].barh(y, data["loyo_positive_year_pct"], color="#56b4e9")
    axes[1].axvline(60, color="#d55e00", linestyle="--", linewidth=1.0)
    axes[1].set_title("Leave-one-year positive edge rate")
    axes[1].set_xlabel("% years")
    axes[1].grid(axis="x", alpha=0.25)

    axes[2].barh(y, data["family_sign_agree_expected_pct"], color="#cc79a7")
    axes[2].axvline(60, color="#d55e00", linestyle="--", linewidth=1.0)
    axes[2].set_title("Family sign agrees expected direction")
    axes[2].set_xlabel("% families")
    axes[2].grid(axis="x", alpha=0.25)

    fig.tight_layout()
    fig.savefig(STABILITY_CHART_OUT, dpi=180)
    plt.close(fig)


def _plot_tail_scatter(features: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    bucket_colors = {
        "supportive_high_score": "#009e73",
        "mixed_mid_score": "#0072b2",
        "headwind_low_score": "#d55e00",
    }
    for bucket, group in features.groupby("predeclared_microstructure_bucket"):
        axes[0].scatter(
            group["predeclared_microstructure_score"],
            group["reentry_lot_pnl"] / 10_000.0,
            s=50,
            color=bucket_colors.get(bucket, "#999999"),
            label=bucket,
            alpha=0.82,
            edgecolor="white",
            linewidth=0.5,
        )
    for _, row in features[features["tail_watch_role"].ne("other")].iterrows():
        axes[0].annotate(
            f"{row['vt_symbol']}\n{row['event_key'].split('.')[-1]}",
            (row["predeclared_microstructure_score"], row["reentry_lot_pnl"] / 10_000.0),
            xytext=(5, 5),
            textcoords="offset points",
            fontsize=8,
            color="#111111",
        )
    axes[0].axhline(0, color="black", linewidth=0.8)
    axes[0].set_title("Tail protection check: fixed score vs reentry PnL")
    axes[0].set_xlabel("Predeclared microstructure score (0-7)")
    axes[0].set_ylabel("Reentry lot PnL (10k CNY)")
    axes[0].grid(alpha=0.25)
    axes[0].legend(loc="upper left", fontsize=8)

    x = features["open_interest_delta_target"]
    y = features["median_directional_book_imbalance"]
    sizes = 40 + features["reentry_lot_pnl"].abs().clip(upper=950_000) / 950_000 * 180
    colors = features["reentry_lot_pnl"].map(lambda value: "#009e73" if value > 0 else "#d55e00")
    axes[1].scatter(x, y, s=sizes, color=colors, alpha=0.72, edgecolor="white", linewidth=0.5)
    for _, row in features[features["tail_watch_role"].ne("other")].iterrows():
        axes[1].annotate(
            row["vt_symbol"],
            (row["open_interest_delta_target"], row["median_directional_book_imbalance"]),
            xytext=(5, 5),
            textcoords="offset points",
            fontsize=8,
        )
    axes[1].axhline(0, color="black", linewidth=0.8)
    axes[1].axvline(0, color="black", linewidth=0.8)
    axes[1].set_title("OI delta vs directional book imbalance")
    axes[1].set_xlabel("Open interest delta in target minute")
    axes[1].set_ylabel("Directional book imbalance")
    axes[1].grid(alpha=0.25)

    fig.tight_layout()
    fig.savefig(TAIL_SCATTER_OUT, dpi=180)
    plt.close(fig)


def _plot_family_heatmap(matrix: pd.DataFrame) -> None:
    if matrix.empty:
        return
    heat = matrix.pivot_table(
        index="product_family",
        columns="reentry_year",
        values="net_reentry_lot_pnl",
        aggfunc="sum",
        fill_value=0.0,
    )
    score = matrix.pivot_table(
        index="product_family",
        columns="reentry_year",
        values="median_predeclared_score",
        aggfunc="median",
        fill_value=np.nan,
    ).reindex(index=heat.index, columns=heat.columns)
    fig, axes = plt.subplots(1, 2, figsize=(16, max(5.5, 0.45 * len(heat))))
    vmax = float(np.nanmax(np.abs(heat.to_numpy()))) if heat.size else 1.0
    image = axes[0].imshow(heat.to_numpy() / 10_000.0, aspect="auto", cmap="RdYlGn", vmin=-vmax / 10_000.0, vmax=vmax / 10_000.0)
    axes[0].set_xticks(np.arange(len(heat.columns)))
    axes[0].set_xticklabels([str(int(col)) for col in heat.columns], rotation=45, ha="right")
    axes[0].set_yticks(np.arange(len(heat.index)))
    axes[0].set_yticklabels(heat.index)
    axes[0].set_title("Net reentry-lot PnL by family/year (10k CNY)")
    fig.colorbar(image, ax=axes[0], fraction=0.046, pad=0.04)

    im2 = axes[1].imshow(score.to_numpy(), aspect="auto", cmap="viridis", vmin=0, vmax=7)
    axes[1].set_xticks(np.arange(len(score.columns)))
    axes[1].set_xticklabels([str(int(col)) for col in score.columns], rotation=45, ha="right")
    axes[1].set_yticks(np.arange(len(score.index)))
    axes[1].set_yticklabels(score.index)
    axes[1].set_title("Median fixed microstructure score by family/year")
    fig.colorbar(im2, ax=axes[1], fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(FAMILY_HEATMAP_OUT, dpi=180)
    plt.close(fig)


def _target_minute(reentry_time: pd.Timestamp) -> tuple[pd.Timestamp, pd.Timestamp]:
    start = reentry_time.floor("min")
    return start, start + pd.Timedelta(minutes=1)


def _plot_tail_atlas(features: pd.DataFrame) -> None:
    watch = features[features["tail_watch_role"].ne("other")].copy()
    if watch.empty:
        return
    watch = pd.concat(
        [
            watch[watch["is_right_tail_watch"]].sort_values("reentry_lot_pnl", ascending=False),
            watch[watch["is_bad_tail_watch"]].sort_values("reentry_lot_pnl"),
        ],
        ignore_index=True,
    )
    n = len(watch)
    fig, axes = plt.subplots(n, 3, figsize=(15, max(2.2 * n, 8)), squeeze=False)
    for row_idx, (_, event) in enumerate(watch.iterrows()):
        path = Path(str(event["tick_file_path"]))
        title = (
            f"{event['tail_watch_role']} {event['vt_symbol']} {event['direction']} "
            f"PnL={event['reentry_lot_pnl'] / 10000:.1f}w score={event['predeclared_microstructure_score']}/7"
        )
        for col_idx in range(3):
            axes[row_idx, col_idx].set_title(title if col_idx == 0 else "")
            axes[row_idx, col_idx].grid(alpha=0.25)
        if not path.exists():
            axes[row_idx, 0].text(0.5, 0.5, "tick file missing", ha="center", va="center")
            continue
        try:
            ticks = pd.read_csv(path, encoding="utf-8-sig")
        except Exception as exc:
            axes[row_idx, 0].text(0.5, 0.5, f"read failed: {type(exc).__name__}", ha="center", va="center")
            continue
        if ticks.empty or "tick_datetime" not in ticks.columns:
            axes[row_idx, 0].text(0.5, 0.5, "empty tick frame", ha="center", va="center")
            continue
        ticks["tick_datetime"] = pd.to_datetime(ticks["tick_datetime"], errors="coerce")
        ticks = ticks.dropna(subset=["tick_datetime"]).sort_values("tick_datetime")
        start, end = _target_minute(pd.Timestamp(event["reentry_time"]))
        target = ticks[(ticks["tick_datetime"] >= start) & (ticks["tick_datetime"] < end)].copy()
        if target.empty:
            target = ticks.copy()
        for col in ["last_price", "ask_price1", "bid_price1", "ask_volume1", "bid_volume1", "volume", "open_interest"]:
            if col in target.columns:
                target[col] = _safe_num(target[col])
            else:
                target[col] = np.nan
        valid = target[(target["ask_price1"] > 0) & (target["bid_price1"] > 0) & (target["ask_price1"] >= target["bid_price1"])].copy()
        if valid.empty:
            axes[row_idx, 0].text(0.5, 0.5, "no valid top book rows", ha="center", va="center")
            continue
        valid["mid_price"] = (valid["ask_price1"] + valid["bid_price1"]) / 2.0
        valid["spread_r"] = (valid["ask_price1"] - valid["bid_price1"]) / float(event["risk_price"])
        valid["depth1"] = valid["ask_volume1"].fillna(0) + valid["bid_volume1"].fillna(0)
        denom = valid["depth1"].replace(0, np.nan)
        valid["directional_book_imbalance"] = float(event["direction_sign"]) * (
            valid["bid_volume1"].fillna(0) - valid["ask_volume1"].fillna(0)
        ) / denom
        valid["sec"] = (valid["tick_datetime"] - valid["tick_datetime"].iloc[0]).dt.total_seconds()
        valid["directional_mid_move_r"] = float(event["direction_sign"]) * (
            valid["mid_price"] - valid["mid_price"].iloc[0]
        ) / float(event["risk_price"])
        axes[row_idx, 0].plot(valid["sec"], valid["directional_mid_move_r"], color="#0072b2", linewidth=1.5)
        axes[row_idx, 0].axhline(0, color="black", linewidth=0.8)
        axes[row_idx, 0].set_ylabel("mid move / R")

        axes[row_idx, 1].plot(valid["sec"], valid["spread_r"], color="#d55e00", linewidth=1.3, label="spread/R")
        ax2 = axes[row_idx, 1].twinx()
        ax2.plot(valid["sec"], valid["depth1"], color="#009e73", linewidth=1.0, alpha=0.75, label="depth1")
        axes[row_idx, 1].set_ylabel("spread/R")
        ax2.set_ylabel("depth1")

        axes[row_idx, 2].plot(valid["sec"], valid["directional_book_imbalance"], color="#cc79a7", linewidth=1.3)
        axes[row_idx, 2].axhline(0, color="black", linewidth=0.8)
        axes[row_idx, 2].set_ylabel("dir book imbalance")
        axes[row_idx, 2].set_xlabel("seconds from target-minute first tick")
    fig.tight_layout()
    fig.savefig(ATLAS_OUT, dpi=180)
    plt.close(fig)


def _write_report(
    features: pd.DataFrame,
    stability: pd.DataFrame,
    leave_year: pd.DataFrame,
    family_summary: pd.DataFrame,
    bucket_summary: pd.DataFrame,
    decision: dict[str, Any],
    official_metrics: dict[str, Any],
) -> None:
    loyo_summary = (
        leave_year.groupby("feature", as_index=False)
        .agg(
            loyo_years=("holdout_edge_positive", lambda s: int(s.notna().sum())),
            loyo_positive_years=("holdout_edge_positive", lambda s: int(pd.to_numeric(s, errors="coerce").fillna(0).sum())),
            median_holdout_mean_edge=("holdout_mean_edge", "median"),
        )
    )
    loyo_summary["loyo_positive_year_pct"] = np.where(
        loyo_summary["loyo_years"] > 0,
        loyo_summary["loyo_positive_years"] / loyo_summary["loyo_years"] * 100.0,
        np.nan,
    )
    score_stability = stability[stability["score_feature"]].merge(loyo_summary, on="feature", how="left")
    right_tail = features[features["is_right_tail_watch"]][
        [
            "event_key",
            "vt_symbol",
            "reentry_lot_pnl",
            "predeclared_microstructure_score",
            "predeclared_microstructure_bucket",
            "open_interest_delta_target",
            "median_spread_r",
            "median_depth1_log",
            "median_directional_book_imbalance",
            "directional_mid_move_r",
        ]
    ].sort_values("reentry_lot_pnl", ascending=False)
    bad_tail = features[features["is_bad_tail_watch"]][
        [
            "event_key",
            "vt_symbol",
            "reentry_lot_pnl",
            "predeclared_microstructure_score",
            "predeclared_microstructure_bucket",
            "open_interest_delta_target",
            "median_spread_r",
            "median_depth1_log",
            "median_directional_book_imbalance",
            "directional_mid_move_r",
        ]
    ].sort_values("reentry_lot_pnl")

    REPORT_OUT.write_text(
        f"""# Stage067 Reentry 微观盘口稳定性审计

- line_id：`{LINE_ID}`
- official：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`
- 阶段性质：固定 Stage066 特征的稳定性/视觉审计，不是真实组合引擎，不生成交易规则
- 运行时间：`{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`
- 决策：`{decision['decision']}`
- 下一步：`{decision['next_step']}`

## 口径

- 输入：Stage066 全覆盖 reentry tick 微观结构特征，事件数 `{len(features)}`，microstructure ready `{int(features['microstructure_ready'].sum())}`。
- 固定 score 特征：`open_interest_delta_target`、`median_spread_r`、`p90_spread_r`、`median_depth1_log`、`median_directional_book_imbalance`、`directional_mid_move_r`、`directional_last_move_r`。
- 固定解释方向：低 OI 扩张、低 spread、高 depth、方向侧 book 支持、方向侧 mid/last move 为更优；这是执行微观结构诊断，不是交易阈值。
- 审计门槛：至少 `3` 个 score 特征跨 leave-one-year 与产品族稳定，且必须同时保护 `OI201/lh2301/FG601` 右尾并识别 `jm2209/OI505` 坏尾。

## 官方基准指标

- 期末权益：`{official_metrics['end_equity']:.2f}`
- 总收益：`{official_metrics['total_return_pct']:.4f}%`
- 最大回撤：`{official_metrics['max_dd_pct']:.4f}%`
- Sharpe：`{official_metrics['sharpe']:.4f}`
- 总滑点：`{official_metrics['total_slippage']:.0f}`
- 总交易次数：`{official_metrics['total_trade_count']:.0f}`
- 胜率：`{official_metrics['win_rate_pct']:.4f}%`

## 固定 score bucket

{_md_table(bucket_summary)}

## Score 特征稳定性

{_md_table(score_stability[['feature','global_spearman_to_pnl','global_matches_expected','loyo_positive_year_pct','family_sign_agree_expected_pct','median_holdout_mean_edge']], max_rows=20)}

## 右尾保护检查

{_md_table(right_tail)}

## 坏尾识别检查

{_md_table(bad_tail)}

## 产品族摘要

{_md_table(family_summary[['product_family','event_count','product_count','year_count','net_reentry_lot_pnl','median_predeclared_score','headwind_event_count','supportive_event_count']], max_rows=20)}

## 视觉观察

- 官方路径图显示 Stage067 固定 score bucket 并没有形成“高分承接右尾、低分集中坏尾”的清晰分层；命名右尾和坏尾分布在 mixed/headwind/supportive 之间。
- tail scatter 显示 `open_interest_delta_target` 与方向盘口不平衡仍高度重叠，赢家和亏损样本没有形成可普世切开的边界。
- 产品族/年份热力图显示大额贡献集中在少数 family-year cell，样本稀疏；这类结构不足以支撑跨周期规则。
- tail atlas 中 `OI201/lh2301/FG601` 与 `jm2209/OI505` 的盘口形态并未呈现同一种稳定可分离模式；部分大赢家反而在低分或混合状态。

## 结论

- 本阶段不通过。数据覆盖已足够，但固定 Stage066 微观盘口特征没有通过稳定性和右尾/坏尾双门槛。
- 不进入 true engine、不触发 A/B、不接正式候选。
- 下一步应停止 reentry 微观盘口规则化，转向 Stage045 `timestamp_ready=1` initial entry 的同口径 tick/盘口覆盖审计；如果没有新外生信息，不再围绕 reentry 盘口字段做阈值或小样本救参。
""",
        encoding="utf-8",
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    features = _load_features()
    curve = _load_official_curve()
    official_metrics = _equity_metrics(curve)

    features = _add_predeclared_score(features)
    stability = _build_feature_stability(features)
    leave_year = _build_leave_one_year(features)
    family_summary = _build_family_summary(features)
    year_family = _build_year_family_matrix(features)
    bucket_summary = _build_score_bucket_summary(features)
    decision = _build_decision(features, stability, leave_year, bucket_summary, official_metrics)

    features.to_csv(EVENTS_OUT, index=False, encoding="utf-8-sig")
    stability.to_csv(FEATURE_STABILITY_OUT, index=False, encoding="utf-8-sig")
    leave_year.to_csv(LEAVE_ONE_YEAR_OUT, index=False, encoding="utf-8-sig")
    family_summary.to_csv(FAMILY_SUMMARY_OUT, index=False, encoding="utf-8-sig")
    year_family.to_csv(YEAR_FAMILY_MATRIX_OUT, index=False, encoding="utf-8-sig")
    bucket_summary.to_csv(SCORE_BUCKET_OUT, index=False, encoding="utf-8-sig")
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")

    _plot_path(features, curve)
    _plot_stability(stability, leave_year)
    _plot_tail_scatter(features)
    _plot_family_heatmap(year_family)
    _plot_tail_atlas(features)
    _write_report(features, stability, leave_year, family_summary, bucket_summary, decision, official_metrics)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
