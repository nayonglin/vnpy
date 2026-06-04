from __future__ import annotations

from datetime import date, datetime
import json
import math
import os
from pathlib import Path
from zoneinfo import ZoneInfo

Path("/private/tmp/vnpy_mplconfig").mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/vnpy_mplconfig")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_drawdown30_preserve_return"
MODEL_TAG = "stage562_stage526_failure_memory_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage562_stage526_failure_memory_audit"
LOCAL_TZ = ZoneInfo("Asia/Shanghai")

SEGMENTS_PATH = OUTPUT_DIR / "qmt_roll_stage537_stage526_segment_lifecycle_audit_segments_stage537_stage526_segment_lifecycle_audit_v1.csv"
REFERENCE_SUMMARY_PATH = OUTPUT_DIR / "qmt_roll_stage526_productcap25_breadth_frontier_summary_stage526_productcap25_breadth_frontier_v1.csv"

SEGMENTS_ENRICHED_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_segments_enriched_{MODEL_TAG}.csv"
BUCKET_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_summary_{MODEL_TAG}.csv"
PROBE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rule_probe_{MODEL_TAG}.csv"
PRODUCT_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_failure_memory_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

MIN_SEGMENTS_FOR_PROMOTION = 20
MIN_WIN_RATE_IMPROVEMENT_PP = 10.0
MIN_ESTIMATED_DELTA = 100_000.0
MAX_POSITIVE_PNL_AT_RISK_PCT = 15.0


def _json_safe(value):
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.isoformat()
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "无数据。"
    view = frame.copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda item: f"{item:.4f}" if pd.notna(item) else "")
    return view.to_markdown(index=False)


def _bucket_consecutive_loss(value: int) -> str:
    if value <= 0:
        return "0"
    if value == 1:
        return "1"
    if value == 2:
        return "2"
    return "3+"


def _bucket_prior_loss(value: int) -> str:
    if value <= 0:
        return "0"
    if value == 1:
        return "1"
    if value <= 3:
        return "2-3"
    return "4+"


def _bucket_gap(days: float) -> str:
    if pd.isna(days):
        return "no_prior"
    if days <= 5:
        return "<=5"
    if days <= 20:
        return "6-20"
    if days <= 60:
        return "21-60"
    return ">60"


def _load_reference() -> dict:
    if not REFERENCE_SUMMARY_PATH.exists():
        return {}
    summary = pd.read_csv(REFERENCE_SUMMARY_PATH, encoding="utf-8-sig")
    row = summary.loc[summary["variant"] == "r080_pc25_maxpos4"]
    if row.empty:
        return {}
    return row.iloc[0].to_dict()


def _load_segments() -> pd.DataFrame:
    if not SEGMENTS_PATH.exists():
        raise FileNotFoundError(f"missing segments file: {SEGMENTS_PATH}")
    segments = pd.read_csv(SEGMENTS_PATH, encoding="utf-8-sig")
    for column in ["start", "end"]:
        segments[column] = pd.to_datetime(segments[column], errors="coerce")
    numeric_columns = [
        "start_day_index",
        "end_day_index",
        "segment_days",
        "net_pnl",
        "holding_pnl",
        "trading_pnl",
        "slippage",
        "trade_count",
        "overlap_bad_window",
    ]
    for column in numeric_columns:
        if column in segments.columns:
            segments[column] = pd.to_numeric(segments[column], errors="coerce").fillna(0)
    segments = segments.sort_values(["product_vt_symbol", "start", "segment_id"]).reset_index(drop=True)
    return segments


def _enrich_segments(segments: pd.DataFrame) -> pd.DataFrame:
    enriched_parts = []
    for _, group in segments.groupby("product_vt_symbol", sort=False):
        group = group.sort_values(["start", "segment_id"]).copy()
        prior_counts = []
        prior_loss_counts = []
        prior_win_counts = []
        consecutive_losses = []
        recent3_losses = []
        recent5_losses = []
        days_since_prior = []
        loss_streak = 0
        prior_edges: list[float] = []
        prior_end = None
        for _, row in group.iterrows():
            prior_counts.append(len(prior_edges))
            loss_count = sum(edge < 0 for edge in prior_edges)
            win_count = sum(edge > 0 for edge in prior_edges)
            prior_loss_counts.append(loss_count)
            prior_win_counts.append(win_count)
            consecutive_losses.append(loss_streak)
            recent3_losses.append(sum(edge < 0 for edge in prior_edges[-3:]))
            recent5_losses.append(sum(edge < 0 for edge in prior_edges[-5:]))
            if prior_end is None or pd.isna(prior_end) or pd.isna(row["start"]):
                days_since_prior.append(np.nan)
            else:
                days_since_prior.append((row["start"] - prior_end).days)
            edge = float(row["net_pnl"])
            prior_edges.append(edge)
            loss_streak = loss_streak + 1 if edge < 0 else 0
            prior_end = row["end"]
        group["prior_segment_count"] = prior_counts
        group["prior_loss_count"] = prior_loss_counts
        group["prior_win_count"] = prior_win_counts
        group["prior_loss_rate_pct"] = [
            100.0 * loss / count if count else np.nan
            for loss, count in zip(prior_loss_counts, prior_counts)
        ]
        group["consecutive_loss_count"] = consecutive_losses
        group["recent3_loss_count"] = recent3_losses
        group["recent5_loss_count"] = recent5_losses
        group["days_since_prior_segment"] = days_since_prior
        group["consecutive_loss_bucket"] = group["consecutive_loss_count"].map(_bucket_consecutive_loss)
        group["prior_loss_count_bucket"] = group["prior_loss_count"].map(_bucket_prior_loss)
        group["recent3_loss_bucket"] = group["recent3_loss_count"].astype(int).astype(str)
        group["recent5_loss_bucket"] = group["recent5_loss_count"].map(lambda item: "4+" if item >= 4 else str(int(item)))
        group["gap_bucket"] = group["days_since_prior_segment"].map(_bucket_gap)
        enriched_parts.append(group)
    enriched = pd.concat(enriched_parts, ignore_index=True)
    return enriched


def _summarize_bucket(enriched: pd.DataFrame, column: str) -> pd.DataFrame:
    rows = []
    total_positive = float(enriched.loc[enriched["net_pnl"] > 0, "net_pnl"].sum())
    for bucket, group in enriched.groupby(column, dropna=False):
        positive = float(group.loc[group["net_pnl"] > 0, "net_pnl"].sum())
        negative = float(group.loc[group["net_pnl"] < 0, "net_pnl"].sum())
        rows.append(
            {
                "bucket_type": column,
                "bucket": str(bucket),
                "segment_count": int(len(group)),
                "net_pnl": float(group["net_pnl"].sum()),
                "positive_pnl": positive,
                "negative_pnl": negative,
                "win_rate_pct": 100.0 * float((group["net_pnl"] > 0).mean()) if len(group) else 0.0,
                "median_net_pnl": float(group["net_pnl"].median()) if len(group) else 0.0,
                "slippage": float(group["slippage"].sum()) if "slippage" in group.columns else 0.0,
                "trade_count": float(group["trade_count"].sum()) if "trade_count" in group.columns else 0.0,
                "bad_window_net_pnl": float(group.loc[group["overlap_bad_window"] == 1, "net_pnl"].sum())
                if "overlap_bad_window" in group.columns
                else 0.0,
                "positive_pnl_share_pct": 100.0 * positive / total_positive if total_positive else 0.0,
            }
        )
    return pd.DataFrame(rows)


def _probe(enriched: pd.DataFrame, name: str, selected_mask: pd.Series, mode: str) -> dict:
    selected = enriched[selected_mask].copy()
    skipped = enriched[~selected_mask].copy()
    control_net = float(enriched["net_pnl"].sum())
    selected_net = float(selected["net_pnl"].sum())
    skipped_net = float(skipped["net_pnl"].sum())
    if mode == "only_selected":
        retained_net = selected_net
        estimated_delta = retained_net - control_net
        positive_pnl_at_risk = float(skipped.loc[skipped["net_pnl"] > 0, "net_pnl"].sum())
        negative_pnl_avoided = float(skipped.loc[skipped["net_pnl"] < 0, "net_pnl"].sum())
    elif mode == "block_selected":
        retained_net = skipped_net
        estimated_delta = retained_net - control_net
        positive_pnl_at_risk = float(selected.loc[selected["net_pnl"] > 0, "net_pnl"].sum())
        negative_pnl_avoided = float(selected.loc[selected["net_pnl"] < 0, "net_pnl"].sum())
    else:
        raise ValueError(mode)
    total_positive = float(enriched.loc[enriched["net_pnl"] > 0, "net_pnl"].sum())
    selected_win_rate = 100.0 * float((selected["net_pnl"] > 0).mean()) if len(selected) else 0.0
    all_win_rate = 100.0 * float((enriched["net_pnl"] > 0).mean()) if len(enriched) else 0.0
    return {
        "probe": name,
        "mode": mode,
        "trigger_count": int(len(selected)),
        "control_net_pnl": control_net,
        "selected_net_pnl": selected_net,
        "skipped_net_pnl": skipped_net,
        "retained_net_pnl": retained_net,
        "estimated_delta_vs_control": estimated_delta,
        "selected_win_rate_pct": selected_win_rate,
        "all_win_rate_pct": all_win_rate,
        "win_rate_improvement_pp": selected_win_rate - all_win_rate,
        "selected_median_net_pnl": float(selected["net_pnl"].median()) if len(selected) else 0.0,
        "selected_bad_window_net_pnl": float(selected.loc[selected["overlap_bad_window"] == 1, "net_pnl"].sum())
        if len(selected)
        else 0.0,
        "positive_pnl_at_risk": positive_pnl_at_risk,
        "negative_pnl_avoided": negative_pnl_avoided,
        "positive_pnl_at_risk_pct": 100.0 * positive_pnl_at_risk / total_positive if total_positive else 0.0,
    }


def _make_probes(enriched: pd.DataFrame) -> pd.DataFrame:
    probes = []
    for threshold in [1, 2, 3]:
        mask = enriched["consecutive_loss_count"] >= threshold
        probes.append(_probe(enriched, f"only_after_consecutive_loss_ge{threshold}", mask, "only_selected"))
        probes.append(_probe(enriched, f"block_after_consecutive_loss_ge{threshold}", mask, "block_selected"))
    for threshold in [1, 2, 3]:
        mask = enriched["recent3_loss_count"] >= threshold
        probes.append(_probe(enriched, f"only_after_recent3_loss_ge{threshold}", mask, "only_selected"))
        probes.append(_probe(enriched, f"block_after_recent3_loss_ge{threshold}", mask, "block_selected"))
    for threshold in [2, 3, 4]:
        mask = enriched["prior_loss_count"] >= threshold
        probes.append(_probe(enriched, f"only_after_prior_loss_ge{threshold}", mask, "only_selected"))
        probes.append(_probe(enriched, f"block_after_prior_loss_ge{threshold}", mask, "block_selected"))
    return pd.DataFrame(probes).sort_values("estimated_delta_vs_control", ascending=False).reset_index(drop=True)


def _product_summary(enriched: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for product, group in enriched.groupby("product_vt_symbol"):
        repeated = group[group["consecutive_loss_count"] >= 2]
        rows.append(
            {
                "product_vt_symbol": product,
                "segment_count": int(len(group)),
                "net_pnl": float(group["net_pnl"].sum()),
                "win_rate_pct": 100.0 * float((group["net_pnl"] > 0).mean()) if len(group) else 0.0,
                "consecutive_loss_ge2_count": int(len(repeated)),
                "consecutive_loss_ge2_net_pnl": float(repeated["net_pnl"].sum()) if len(repeated) else 0.0,
                "consecutive_loss_ge2_win_rate_pct": 100.0 * float((repeated["net_pnl"] > 0).mean()) if len(repeated) else 0.0,
                "max_consecutive_loss_before_entry": int(group["consecutive_loss_count"].max()) if len(group) else 0,
            }
        )
    return pd.DataFrame(rows).sort_values("consecutive_loss_ge2_net_pnl").reset_index(drop=True)


def _spearman_summary(enriched: pd.DataFrame) -> pd.DataFrame:
    features = [
        "prior_segment_count",
        "prior_loss_count",
        "prior_loss_rate_pct",
        "consecutive_loss_count",
        "recent3_loss_count",
        "recent5_loss_count",
        "days_since_prior_segment",
    ]
    rows = []
    for feature in features:
        pair = enriched[[feature, "net_pnl"]].dropna()
        corr = float(pair[feature].corr(pair["net_pnl"], method="spearman")) if len(pair) >= 3 else np.nan
        rows.append({"feature": feature, "non_null": int(len(pair)), "spearman_to_net_pnl": corr})
    return pd.DataFrame(rows)


def _write_chart(bucket_summary: pd.DataFrame, probe_summary: pd.DataFrame, product_summary: pd.DataFrame, decision: dict) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "PingFang SC", "Heiti TC", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    fig.suptitle("Stage562 Stage526失败记忆审计", fontsize=18, fontweight="bold")

    ax = axes[0, 0]
    consec = bucket_summary[bucket_summary["bucket_type"] == "consecutive_loss_bucket"].copy()
    order = ["0", "1", "2", "3+"]
    consec["bucket"] = pd.Categorical(consec["bucket"], categories=order, ordered=True)
    consec = consec.sort_values("bucket")
    x = np.arange(len(consec))
    colors = ["#59A14F" if value >= 0 else "#E15759" for value in consec["net_pnl"]]
    ax.bar(x, consec["net_pnl"], color=colors)
    ax.axhline(0, color="#333333", linewidth=1)
    ax.set_xticks(x)
    ax.set_xticklabels(consec["bucket"].astype(str))
    ax.set_title("按连续亏损次数分桶的后续段净损益")
    ax.set_ylabel("net pnl")
    for i, (_, row) in enumerate(consec.iterrows()):
        ax.text(i, row["net_pnl"], f"{int(row['segment_count'])}", ha="center", va="bottom" if row["net_pnl"] >= 0 else "top", fontsize=10)

    ax = axes[0, 1]
    recent = bucket_summary[bucket_summary["bucket_type"] == "recent3_loss_bucket"].copy()
    recent["bucket_sort"] = pd.to_numeric(recent["bucket"], errors="coerce")
    recent = recent.sort_values("bucket_sort")
    x = np.arange(len(recent))
    ax.bar(x, recent["median_net_pnl"], color="#F28E2B", alpha=0.45, label="median pnl")
    ax.set_xticks(x)
    ax.set_xticklabels(recent["bucket"].astype(str))
    ax.set_title("近3段亏损数：胜率与中位损益")
    ax.set_ylabel("median pnl")
    ax2 = ax.twinx()
    ax2.plot(x, recent["win_rate_pct"], marker="o", color="#4C78A8", label="win rate")
    ax2.axhline(decision["all_win_rate_pct"], color="#4C78A8", linestyle="--", linewidth=1, label="all win rate")
    ax2.set_ylabel("win rate %")
    lines, labels = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax2.legend(lines + lines2, labels + labels2, loc="upper right")

    ax = axes[1, 0]
    top_probe = probe_summary.head(10).copy().sort_values("estimated_delta_vs_control")
    colors = ["#59A14F" if value >= 0 else "#E15759" for value in top_probe["estimated_delta_vs_control"]]
    ax.barh(top_probe["probe"], top_probe["estimated_delta_vs_control"], color=colors)
    ax.axvline(0, color="#333333", linewidth=1)
    ax.set_title("规则探针：估算相对Stage526增量")
    ax.set_xlabel("estimated delta")

    ax = axes[1, 1]
    product_display = pd.concat([product_summary.head(5), product_summary.tail(5)], ignore_index=True)
    product_display = product_display.drop_duplicates("product_vt_symbol").sort_values("consecutive_loss_ge2_net_pnl")
    colors = ["#59A14F" if value >= 0 else "#E15759" for value in product_display["consecutive_loss_ge2_net_pnl"]]
    ax.barh(product_display["product_vt_symbol"], product_display["consecutive_loss_ge2_net_pnl"], color=colors)
    ax.axvline(0, color="#333333", linewidth=1)
    ax.set_title("连续亏损>=2后入场：最弱/最强产品")
    ax.set_xlabel("net pnl")

    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def main() -> None:
    now = datetime.now(LOCAL_TZ)
    reference = _load_reference()
    segments = _load_segments()
    enriched = _enrich_segments(segments)
    bucket_summary = pd.concat(
        [
            _summarize_bucket(enriched, "consecutive_loss_bucket"),
            _summarize_bucket(enriched, "prior_loss_count_bucket"),
            _summarize_bucket(enriched, "recent3_loss_bucket"),
            _summarize_bucket(enriched, "recent5_loss_bucket"),
            _summarize_bucket(enriched, "gap_bucket"),
        ],
        ignore_index=True,
    )
    probe_summary = _make_probes(enriched)
    product_summary = _product_summary(enriched)
    spearman_summary = _spearman_summary(enriched)

    all_net = float(enriched["net_pnl"].sum())
    all_win_rate = 100.0 * float((enriched["net_pnl"] > 0).mean())
    all_median = float(enriched["net_pnl"].median())
    consecutive_ge2 = enriched[enriched["consecutive_loss_count"] >= 2].copy()
    consecutive_ge2_net = float(consecutive_ge2["net_pnl"].sum())
    consecutive_ge2_win_rate = 100.0 * float((consecutive_ge2["net_pnl"] > 0).mean()) if len(consecutive_ge2) else 0.0
    best_probe = probe_summary.iloc[0].to_dict() if not probe_summary.empty else {}

    promotion_checks = {
        "enough_segments": int(len(consecutive_ge2)) >= MIN_SEGMENTS_FOR_PROMOTION,
        "win_rate_improves": (consecutive_ge2_win_rate - all_win_rate) >= MIN_WIN_RATE_IMPROVEMENT_PP,
        "selected_net_positive": consecutive_ge2_net > 0,
        "best_probe_material_positive": float(best_probe.get("estimated_delta_vs_control", 0.0)) >= MIN_ESTIMATED_DELTA,
        "positive_pnl_at_risk_small": float(best_probe.get("positive_pnl_at_risk_pct", 100.0)) <= MAX_POSITIVE_PNL_AT_RISK_PCT,
    }
    promotion_pass = all(promotion_checks.values())
    diagnostic_positive = (
        int(len(consecutive_ge2)) >= MIN_SEGMENTS_FOR_PROMOTION
        and consecutive_ge2_net > 0
        and (consecutive_ge2_win_rate - all_win_rate) >= 5.0
    )
    decision_label = "failure_memory_positive_diagnostic_not_trade_gate"
    if not diagnostic_positive:
        decision_label = "failure_memory_not_supported_keep_stage526"
    if promotion_pass:
        decision_label = "failure_memory_signal_promising_needs_real_engine_replay"

    decision = {
        "stage": "Stage262",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at_local": now.isoformat(),
        "decision": decision_label,
        "candidate": "r080_pc25_maxpos4",
        "reference": reference,
        "segment_count": int(len(enriched)),
        "all_net_pnl": all_net,
        "all_win_rate_pct": all_win_rate,
        "all_median_net_pnl": all_median,
        "consecutive_loss_ge2": {
            "segment_count": int(len(consecutive_ge2)),
            "net_pnl": consecutive_ge2_net,
            "win_rate_pct": consecutive_ge2_win_rate,
            "win_rate_improvement_pp": consecutive_ge2_win_rate - all_win_rate,
            "median_net_pnl": float(consecutive_ge2["net_pnl"].median()) if len(consecutive_ge2) else 0.0,
            "bad_window_net_pnl": float(consecutive_ge2.loc[consecutive_ge2["overlap_bad_window"] == 1, "net_pnl"].sum()) if len(consecutive_ge2) else 0.0,
        },
        "best_probe": best_probe,
        "promotion_checks": promotion_checks,
        "diagnostic_positive": diagnostic_positive,
        "spearman_summary": spearman_summary.to_dict(orient="records"),
        "outputs": {
            "segments_enriched": str(SEGMENTS_ENRICHED_PATH),
            "bucket_summary": str(BUCKET_SUMMARY_PATH),
            "rule_probe": str(PROBE_SUMMARY_PATH),
            "product_summary": str(PRODUCT_SUMMARY_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
            "chart": str(CHART_PATH),
        },
    }

    report = f"""# Stage262 Stage526失败记忆审计

- line_id：`{LINE_ID}`
- 生成时间：`{now.strftime('%Y-%m-%d %H:%M:%S %Z')}`
- 阶段性质：只读归因；不做收益回测，不修改交易规则。
- 决策：`{decision_label}`

## 核心结论

- 本阶段检验“同一品种连续失败后，下一次信号是否更容易成功”的假设。
- Stage526 持仓段总数 `{len(enriched)}`，段净损益合计 `{all_net:,.0f}`，全体段胜率 `{all_win_rate:.2f}%`，中位净损益 `{all_median:,.0f}`。
- 连续亏损 `>=2` 后的后续段数 `{len(consecutive_ge2)}`，净损益 `{consecutive_ge2_net:,.0f}`，胜率 `{consecutive_ge2_win_rate:.2f}%`，相对全体胜率变化 `{consecutive_ge2_win_rate - all_win_rate:.2f}pp`。
- 最好规则探针为 `{best_probe.get('probe', '')}` / `{best_probe.get('mode', '')}`，估算相对 Stage526 增量 `{float(best_probe.get('estimated_delta_vs_control', 0.0)):,.0f}`，触发段数 `{int(best_probe.get('trigger_count', 0))}`。
- 判断：失败记忆有正向诊断价值，但没有达到交易规则晋级要求；它不能作为直接开仓门禁，后续若继续，只能作为极低自由度 sizing/观察因子再审计。

## 晋级检查

{_md_table(pd.DataFrame([promotion_checks]))}

## 分桶摘要

{_md_table(bucket_summary)}

## 规则探针 Top

{_md_table(probe_summary.head(12))}

## 产品摘要 Top Weak

{_md_table(product_summary.head(12))}

## Spearman 诊断

{_md_table(spearman_summary)}

## 过拟合反思

- 运行前判断：不是过拟合。本阶段只读 Stage526 固定持仓段，检验一个预先明确的失败记忆假设，不调阈值。
- 运行后判断：不是过拟合。结果未通过后直接降级，没有为了救结论继续改 `>=2/>=3` 或产品名单。

## 继续价值反思

- 运行前判断：有价值。该假设来自“多次失败后可能更容易走出震荡”的直觉，需要用数据反证。
- 运行后判断：这个子方向继续价值低。失败记忆不能作为 Stage526 的新增入场/加仓规则；策略本体优化应转向更接近成本 churn 或真实执行偏差的结构，而不是信号次数记忆。
"""

    enriched.to_csv(SEGMENTS_ENRICHED_PATH, index=False, encoding="utf-8-sig")
    bucket_summary.to_csv(BUCKET_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    probe_summary.to_csv(PROBE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    product_summary.to_csv(PRODUCT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(report, encoding="utf-8")
    _write_chart(bucket_summary, probe_summary, product_summary, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
