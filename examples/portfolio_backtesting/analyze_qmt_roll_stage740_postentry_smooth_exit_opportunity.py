from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage733_shadowless_preentry_quality as s733
import analyze_qmt_roll_stage735_postentry_smooth_kline_hold_quality as s735


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage740_postentry_smooth_exit_opportunity_v1"
OUTPUT_PREFIX = "qmt_roll_stage740_postentry_smooth_exit_opportunity"
LINE_ID = "futures_trend_winner_trade_forensics"

SOURCE_ENRICHED_PATH = s735.ENRICHED_PATH
SOURCE_METRICS_PATH = s735.FEATURE_METRICS_PATH

ENRICHED_EXIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_enriched_exit_lots_{MODEL_TAG}.csv"
GROUP_METRICS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_group_metrics_{MODEL_TAG}.csv"
YEAR_DETAIL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_detail_{MODEL_TAG}.csv"
TOP_CONTINUATION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_top_continuation_lots_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

FORWARD_WINDOWS = [3, 5, 10, 20]
MAIN_WINDOW = 20

MIN_WATCH_ROWS = 30
MIN_WATCH_YEARS = 5
MIN_WATCH_PRODUCTS = 8
MAX_DOMINANT_PRODUCT_SHARE = 0.30
MIN_FAVORABLE_2R_LIFT_PP = 8.0
MIN_CLEAN_1R_LIFT_PP = 5.0
MAX_DANGER_1R_LIFT_PP = 8.0

FAST_FEATURES = [
    "post1_smooth_directional_combo",
    "post1_body60_ratio_ge50",
    "post1_avg_directional_close_strength_ge60",
    "post2_clean_shadow_combo",
    "post2_short30_ratio_ge50",
]

POST5_FEATURES = [
    "post5_smooth_directional_combo",
    "post5_long60_ratio_le20",
    "post5_avg_directional_close_strength_ge60",
    "post5_avg_adverse_wick_le25",
]


def _bool_series(data: pd.DataFrame, column: str) -> pd.Series:
    if column not in data.columns:
        return pd.Series(False, index=data.index)
    series = data[column]
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)
    return series.astype(str).str.lower().isin(["true", "1", "yes", "y"])


def _load_sources() -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    if not SOURCE_ENRICHED_PATH.exists() or not SOURCE_METRICS_PATH.exists():
        s735.main()
    lots = pd.read_csv(SOURCE_ENRICHED_PATH, encoding="utf-8-sig")
    metrics = pd.read_csv(SOURCE_METRICS_PATH, encoding="utf-8-sig")

    for column in ["entry_date", "exit_date"]:
        lots[column] = pd.to_datetime(lots[column], errors="coerce").dt.normalize()
    for column in [
        "entry_price",
        "exit_price",
        "volume",
        "size",
        "realized_pnl",
        "risk_amount",
        "r_multiple",
        "big_winner",
        "quality_winner",
    ]:
        if column in lots.columns:
            lots[column] = pd.to_numeric(lots[column], errors="coerce")

    passed = metrics.loc[_bool_series(metrics, "passes_reliable_gate"), "feature"].dropna().astype(str).tolist()
    return lots, metrics, passed


def _first_hit_day(values: pd.Series, threshold: float) -> float:
    hits = np.flatnonzero(values.to_numpy(dtype="float64") >= threshold)
    if len(hits) == 0:
        return np.nan
    return float(hits[0] + 1)


def _forward_stats_for_window(bars: pd.DataFrame, row: pd.Series, window: int) -> dict[str, Any]:
    exit_date = pd.Timestamp(row["exit_date"]).normalize()
    forward = bars[bars["date"] > exit_date].head(window).copy()
    prefix = f"fwd{window}"
    if forward.empty:
        return {f"{prefix}_available_bars": 0}

    exit_price = float(row["exit_price"])
    risk_amount = float(row["risk_amount"])
    volume = float(row["volume"])
    size = float(row["size"])
    if not np.isfinite(exit_price) or not np.isfinite(risk_amount) or risk_amount <= 0:
        return {f"{prefix}_available_bars": int(len(forward))}

    high = forward["high_price"].astype("float64")
    low = forward["low_price"].astype("float64")
    close = forward["close_price"].astype("float64")
    multiplier = volume * size
    direction = str(row["direction"])

    if direction == "long":
        favorable_cash = (high - exit_price) * multiplier
        adverse_cash = (exit_price - low) * multiplier
        close_cash = (close - exit_price) * multiplier
    elif direction == "short":
        favorable_cash = (exit_price - low) * multiplier
        adverse_cash = (high - exit_price) * multiplier
        close_cash = (exit_price - close) * multiplier
    else:
        return {f"{prefix}_available_bars": int(len(forward))}

    favorable_r = favorable_cash / risk_amount
    adverse_r = adverse_cash / risk_amount
    close_r = close_cash / risk_amount
    first_fav1 = _first_hit_day(favorable_r, 1.0)
    first_adv1 = _first_hit_day(adverse_r, 1.0)
    first_fav2 = _first_hit_day(favorable_r, 2.0)
    first_adv2 = _first_hit_day(adverse_r, 2.0)
    fav1_before_adv1 = np.isfinite(first_fav1) and (not np.isfinite(first_adv1) or first_fav1 <= first_adv1)
    adv1_before_fav1 = np.isfinite(first_adv1) and (not np.isfinite(first_fav1) or first_adv1 < first_fav1)

    return {
        f"{prefix}_available_bars": int(len(forward)),
        f"{prefix}_end_date": forward.iloc[-1]["date"].strftime("%Y-%m-%d"),
        f"{prefix}_favorable_max_r": float(favorable_r.max()),
        f"{prefix}_adverse_max_r": float(adverse_r.max()),
        f"{prefix}_close_r": float(close_r.iloc[-1]),
        f"{prefix}_first_favorable_1r_day": first_fav1,
        f"{prefix}_first_adverse_1r_day": first_adv1,
        f"{prefix}_first_favorable_2r_day": first_fav2,
        f"{prefix}_first_adverse_2r_day": first_adv2,
        f"{prefix}_favor1_before_adverse1": bool(fav1_before_adv1),
        f"{prefix}_adverse1_before_favor1": bool(adv1_before_fav1),
        f"{prefix}_clean_continuation_1r": bool(favorable_r.max() >= 1.0 and adverse_r.max() < 1.0),
        f"{prefix}_clean_continuation_2r": bool(favorable_r.max() >= 2.0 and adverse_r.max() < 1.5),
        f"{prefix}_danger_adverse_1r": bool(adverse_r.max() >= 1.0),
        f"{prefix}_danger_adverse_2r": bool(adverse_r.max() >= 2.0),
    }


def _enrich_forward_exit_opportunity(lots: pd.DataFrame, passed_features: list[str]) -> pd.DataFrame:
    bar_cache: dict[str, pd.DataFrame] = {}
    records: list[dict[str, Any]] = []
    for _, row in lots.iterrows():
        record = row.to_dict()
        vt_symbol = str(row["vt_symbol"])
        bars = bar_cache.get(vt_symbol)
        if bars is None:
            bars = s733._load_contract_bars(vt_symbol)
            bar_cache[vt_symbol] = bars
        if not bars.empty:
            for window in FORWARD_WINDOWS:
                record.update(_forward_stats_for_window(bars, row, window))
        records.append(record)

    enriched = pd.DataFrame(records)
    enriched["entry_year"] = pd.to_datetime(enriched["entry_date"], errors="coerce").dt.year
    enriched["exit_year"] = pd.to_datetime(enriched["exit_date"], errors="coerce").dt.year

    enriched["hq_any_stage735_pass"] = False
    for feature in passed_features:
        enriched["hq_any_stage735_pass"] = enriched["hq_any_stage735_pass"] | _bool_series(enriched, feature)
    enriched["hq_fast_day1_2"] = False
    for feature in FAST_FEATURES:
        enriched["hq_fast_day1_2"] = enriched["hq_fast_day1_2"] | _bool_series(enriched, feature)
    enriched["hq_post5_family"] = False
    for feature in POST5_FEATURES:
        enriched["hq_post5_family"] = enriched["hq_post5_family"] | _bool_series(enriched, feature)
    return enriched


def _selected_mask(data: pd.DataFrame, group: str) -> pd.Series:
    if group == "baseline_all":
        return pd.Series(True, index=data.index)
    return _bool_series(data, group)


def _metric_for_group(data: pd.DataFrame, group: str, window: int, baseline: dict[str, float] | None) -> dict[str, Any]:
    prefix = f"fwd{window}"
    selected = data[_selected_mask(data, group)].dropna(
        subset=[f"{prefix}_favorable_max_r", f"{prefix}_adverse_max_r", f"{prefix}_close_r"]
    )
    if selected.empty:
        return {
            "group": group,
            "window": window,
            "rows": 0,
            "passes_exit_watch_gate": False,
        }

    product_share = float(selected["product"].value_counts(normalize=True).iloc[0])
    favorable_1r_rate = float((selected[f"{prefix}_favorable_max_r"] >= 1.0).mean() * 100.0)
    favorable_2r_rate = float((selected[f"{prefix}_favorable_max_r"] >= 2.0).mean() * 100.0)
    clean_1r_rate = float(_bool_series(selected, f"{prefix}_clean_continuation_1r").mean() * 100.0)
    clean_2r_rate = float(_bool_series(selected, f"{prefix}_clean_continuation_2r").mean() * 100.0)
    danger_1r_rate = float(_bool_series(selected, f"{prefix}_danger_adverse_1r").mean() * 100.0)
    favor1_before_adv1_rate = float(_bool_series(selected, f"{prefix}_favor1_before_adverse1").mean() * 100.0)
    adverse1_before_favor1_rate = float(_bool_series(selected, f"{prefix}_adverse1_before_favor1").mean() * 100.0)

    baseline = baseline or {}
    favorable_2r_lift = favorable_2r_rate - float(baseline.get("favorable_2r_rate_pct", favorable_2r_rate))
    clean_1r_lift = clean_1r_rate - float(baseline.get("clean_1r_rate_pct", clean_1r_rate))
    danger_1r_lift = danger_1r_rate - float(baseline.get("danger_1r_rate_pct", danger_1r_rate))

    years = int(selected["exit_year"].nunique())
    products = int(selected["product"].nunique())
    directions = int(selected["direction"].nunique())
    passes = bool(
        group != "baseline_all"
        and len(selected) >= MIN_WATCH_ROWS
        and years >= MIN_WATCH_YEARS
        and products >= MIN_WATCH_PRODUCTS
        and product_share <= MAX_DOMINANT_PRODUCT_SHARE
        and directions >= 2
        and favorable_2r_lift >= MIN_FAVORABLE_2R_LIFT_PP
        and clean_1r_lift >= MIN_CLEAN_1R_LIFT_PP
        and danger_1r_lift <= MAX_DANGER_1R_LIFT_PP
    )

    return {
        "group": group,
        "window": window,
        "rows": int(len(selected)),
        "coverage_pct": float(len(selected) / len(data.dropna(subset=[f"{prefix}_favorable_max_r"])) * 100.0),
        "years": years,
        "products": products,
        "directions": directions,
        "dominant_product_share_pct": product_share * 100.0,
        "avg_final_r": float(selected["r_multiple"].mean()),
        "sum_realized_pnl": float(selected["realized_pnl"].sum()),
        "post_exit_favorable_avg_r": float(selected[f"{prefix}_favorable_max_r"].mean()),
        "post_exit_favorable_median_r": float(selected[f"{prefix}_favorable_max_r"].median()),
        "favorable_1r_rate_pct": favorable_1r_rate,
        "favorable_2r_rate_pct": favorable_2r_rate,
        "favorable_2r_lift_pp": favorable_2r_lift,
        "post_exit_adverse_avg_r": float(selected[f"{prefix}_adverse_max_r"].mean()),
        "danger_1r_rate_pct": danger_1r_rate,
        "danger_1r_lift_pp": danger_1r_lift,
        "danger_2r_rate_pct": float(_bool_series(selected, f"{prefix}_danger_adverse_2r").mean() * 100.0),
        "close_after_avg_r": float(selected[f"{prefix}_close_r"].mean()),
        "close_after_positive_rate_pct": float((selected[f"{prefix}_close_r"] > 0.0).mean() * 100.0),
        "clean_1r_rate_pct": clean_1r_rate,
        "clean_1r_lift_pp": clean_1r_lift,
        "clean_2r_rate_pct": clean_2r_rate,
        "favor1_before_adv1_rate_pct": favor1_before_adv1_rate,
        "adverse1_before_favor1_rate_pct": adverse1_before_favor1_rate,
        "passes_exit_watch_gate": passes,
    }


def _build_group_metrics(data: pd.DataFrame, passed_features: list[str]) -> pd.DataFrame:
    groups = [
        "baseline_all",
        "hq_any_stage735_pass",
        "hq_fast_day1_2",
        "hq_post5_family",
        *passed_features,
    ]
    rows: list[dict[str, Any]] = []
    for window in FORWARD_WINDOWS:
        baseline = _metric_for_group(data, "baseline_all", window, None)
        rows.append(baseline)
        for group in groups[1:]:
            rows.append(_metric_for_group(data, group, window, baseline))
    return pd.DataFrame(rows).sort_values(
        ["window", "passes_exit_watch_gate", "favorable_2r_lift_pp", "clean_1r_lift_pp"],
        ascending=[True, False, False, False],
    )


def _build_year_detail(data: pd.DataFrame, groups: list[str], window: int) -> pd.DataFrame:
    prefix = f"fwd{window}"
    frames: list[pd.DataFrame] = []
    for group in groups:
        selected = data[_selected_mask(data, group)].dropna(subset=[f"{prefix}_favorable_max_r"]).copy()
        if selected.empty:
            continue
        year = (
            selected.groupby("exit_year")
            .agg(
                rows=("lot_id", "count"),
                products=("product", "nunique"),
                directions=("direction", "nunique"),
                avg_final_r=("r_multiple", "mean"),
                realized_pnl=("realized_pnl", "sum"),
                post_exit_favorable_avg_r=(f"{prefix}_favorable_max_r", "mean"),
                favorable_2r_count=(f"{prefix}_favorable_max_r", lambda s: int((s >= 2.0).sum())),
                clean_1r_count=(f"{prefix}_clean_continuation_1r", "sum"),
                danger_1r_count=(f"{prefix}_danger_adverse_1r", "sum"),
                close_after_avg_r=(f"{prefix}_close_r", "mean"),
            )
            .reset_index()
        )
        year["group"] = group
        year["favorable_2r_rate_pct"] = year["favorable_2r_count"] / year["rows"] * 100.0
        year["clean_1r_rate_pct"] = year["clean_1r_count"] / year["rows"] * 100.0
        year["danger_1r_rate_pct"] = year["danger_1r_count"] / year["rows"] * 100.0
        frames.append(year)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _plot_metrics(metrics: pd.DataFrame) -> None:
    focus = metrics[metrics["window"] == MAIN_WINDOW].copy()
    focus = focus[focus["group"].isin(["baseline_all", "hq_any_stage735_pass", "hq_fast_day1_2", "hq_post5_family"])]
    if focus.empty:
        return
    focus = focus.sort_values("favorable_2r_rate_pct", ascending=True)
    labels = focus["group"].tolist()
    y = np.arange(len(focus))
    plt.figure(figsize=(12, 6))
    plt.barh(y - 0.18, focus["favorable_2r_rate_pct"], height=0.34, label="post-exit favorable >= 2R")
    plt.barh(y + 0.18, focus["danger_1r_rate_pct"], height=0.34, label="post-exit adverse >= 1R")
    plt.yticks(y, labels)
    plt.xlabel("Rate (%)")
    plt.title("Stage740 exit-after opportunity: continuation vs danger (20 bars)")
    plt.grid(axis="x", alpha=0.25)
    plt.legend(loc="lower right")
    plt.tight_layout()
    plt.savefig(CHART_PATH, dpi=160)
    plt.close()


def _top_continuation_lots(data: pd.DataFrame, passed_features: list[str]) -> pd.DataFrame:
    prefix = f"fwd{MAIN_WINDOW}"
    columns = [
        "lot_id",
        "vt_symbol",
        "product",
        "direction",
        "entry_date",
        "exit_date",
        "exit_reason",
        "r_multiple",
        "realized_pnl",
        "hq_any_stage735_pass",
        "hq_fast_day1_2",
        "hq_post5_family",
        f"{prefix}_favorable_max_r",
        f"{prefix}_adverse_max_r",
        f"{prefix}_close_r",
        f"{prefix}_first_favorable_1r_day",
        f"{prefix}_first_adverse_1r_day",
        f"{prefix}_favor1_before_adverse1",
        *passed_features,
    ]
    available = [column for column in columns if column in data.columns]
    return data.sort_values(f"{prefix}_favorable_max_r", ascending=False)[available].head(80)


def _build_report(
    metrics: pd.DataFrame,
    year_detail: pd.DataFrame,
    top_lots: pd.DataFrame,
    passed_features: list[str],
) -> str:
    main = metrics[metrics["window"] == MAIN_WINDOW].copy()
    pass_watch = main[main["passes_exit_watch_gate"].fillna(False)].copy()
    cols = [
        "group",
        "window",
        "rows",
        "coverage_pct",
        "years",
        "products",
        "directions",
        "dominant_product_share_pct",
        "avg_final_r",
        "post_exit_favorable_avg_r",
        "favorable_2r_rate_pct",
        "favorable_2r_lift_pp",
        "danger_1r_rate_pct",
        "danger_1r_lift_pp",
        "close_after_avg_r",
        "clean_1r_rate_pct",
        "clean_1r_lift_pp",
        "favor1_before_adv1_rate_pct",
        "adverse1_before_favor1_rate_pct",
        "passes_exit_watch_gate",
    ]
    lines = [
        "# Stage740 入场后顺畅K线与正式退出后机会损失审计",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} CST",
        f"- 研究线：`{LINE_ID}`",
        f"- 数据源：`{SOURCE_ENRICHED_PATH.name}` + `{SOURCE_METRICS_PATH.name}`",
        "- 目标：只读验证 Stage735 已通过的顺畅 K 线标签，是否能解释正式退出后仍有顺势空间的交易。",
        "- 方法：以正式退出价为锚，观察退出后 `3/5/10/20` 根合约日线的顺势最大机会 R、反向最大风险 R、收盘后净变化 R。",
        "- 重要限制：退出后机会不是可交易收益，只用于判断现有退出是否可能过早；真实规则需要重新进入 A/C 回测。",
        "",
        "## 20根主窗口分组",
        "",
        s733._md_table(main[cols], max_rows=40),
        "",
        "## 通过观察闸门分组",
        "",
        s733._md_table(pass_watch[cols] if not pass_watch.empty else pass_watch),
        "",
        "## 所有窗口 Top",
        "",
        s733._md_table(metrics[cols], max_rows=80),
        "",
        "## 年度明细（20根）",
        "",
        s733._md_table(year_detail.sort_values(["group", "exit_year"]).head(120) if not year_detail.empty else year_detail),
        "",
        "## 退出后最大顺势空间样本",
        "",
        s733._md_table(top_lots, max_rows=50),
        "",
        "## 结论",
        "",
    ]
    if pass_watch.empty:
        lines.extend(
            [
                "- Stage735 顺畅 K 线标签没有通过退出后机会观察闸门；暂不值得接真实退出规则。",
            ]
        )
    else:
        lines.extend(
            [
                f"- 有 {len(pass_watch)} 个分组通过退出后机会观察闸门，可以进入下一步真实 A/C 设计。",
                "- 但本阶段仍不能证明应扩大初始风险；它只说明这些标签可能用于持仓/退出管理。",
            ]
        )
    lines.extend(
        [
            "",
            "## 已固定特征",
            "",
            s733._md_table(pd.DataFrame({"passed_stage735_feature": passed_features})),
            "",
            "## 过拟合反思",
            "",
            "- 本阶段没有新增阈值，也没有按 2025 红框窗口反推参数。",
            "- 退出后 20 根是解释窗口，不是交易规则；若下一步要转规则，必须预声明 A/C 并对 2020-2024、2025、2026 分段验收。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    lots, _, passed_features = _load_sources()
    enriched = _enrich_forward_exit_opportunity(lots, passed_features)
    metrics = _build_group_metrics(enriched, passed_features)
    focus_groups = ["baseline_all", "hq_any_stage735_pass", "hq_fast_day1_2", "hq_post5_family"]
    year_detail = _build_year_detail(enriched, focus_groups, MAIN_WINDOW)
    top_lots = _top_continuation_lots(enriched, passed_features)
    _plot_metrics(metrics)

    enriched.to_csv(ENRICHED_EXIT_PATH, index=False, encoding="utf-8-sig")
    metrics.to_csv(GROUP_METRICS_PATH, index=False, encoding="utf-8-sig")
    year_detail.to_csv(YEAR_DETAIL_PATH, index=False, encoding="utf-8-sig")
    top_lots.to_csv(TOP_CONTINUATION_PATH, index=False, encoding="utf-8-sig")
    REPORT_PATH.write_text(_build_report(metrics, year_detail, top_lots, passed_features), encoding="utf-8")

    main_window = metrics[metrics["window"] == MAIN_WINDOW].copy()
    pass_watch = main_window[main_window["passes_exit_watch_gate"].fillna(False)].copy()
    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "source_enriched": SOURCE_ENRICHED_PATH.name,
        "source_metrics": SOURCE_METRICS_PATH.name,
        "closed_lots": int(len(lots)),
        "passed_stage735_features": passed_features,
        "main_window": MAIN_WINDOW,
        "watch_gate_pass_count": int(len(pass_watch)),
        "watch_gate_pass_groups": pass_watch["group"].tolist(),
        "decision": (
            "postentry_smooth_kline_can_enter_exit_management_ac"
            if not pass_watch.empty
            else "postentry_smooth_kline_exit_opportunity_not_reliable_enough"
        ),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    DECISION_PATH.write_text(json.dumps(s733._json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(s733._json_safe(decision), ensure_ascii=False, indent=2))
    print(main_window.to_string(index=False))


if __name__ == "__main__":
    main()
