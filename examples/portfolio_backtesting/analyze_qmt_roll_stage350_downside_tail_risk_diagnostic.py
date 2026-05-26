from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from analyze_qmt_roll_stage324_true_combo_capital_margin import (
    _safe_float,
    _to_builtin,
    _to_markdown_table,
)
from analyze_qmt_roll_stage328_c3_single_path_loss_attribution import _load_bars_for_round_trips
from qmt_roll_official_stage78_config import OFFICIAL_STAGE78_ROLE, OFFICIAL_STAGE78_VERSION
from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage350_downside_tail_risk_diagnostic_v1"
OUTPUT_PREFIX = "qmt_roll_stage350_downside_tail_risk_diagnostic"
LINE_ID = "futures_trend_drawdown30_preserve_return"

STAGE328_TAG = "stage328_c3_single_path_loss_attribution_v1"
STAGE328_PREFIX = "qmt_roll_stage328_c3_single_path_loss_attribution"
STAGE328_ROUND_TRIPS = OUTPUT_DIR / f"{STAGE328_PREFIX}_round_trips_{STAGE328_TAG}.csv"
STAGE328_DECISION = OUTPUT_DIR / f"{STAGE328_PREFIX}_decision_{STAGE328_TAG}.json"


def _load_stage328_round_trips() -> tuple[pd.DataFrame, dict[str, Any]]:
    if not STAGE328_ROUND_TRIPS.exists():
        raise FileNotFoundError(f"missing Stage328 round trips: {STAGE328_ROUND_TRIPS}")
    if not STAGE328_DECISION.exists():
        raise FileNotFoundError(f"missing Stage328 decision: {STAGE328_DECISION}")
    frame = pd.read_csv(STAGE328_ROUND_TRIPS, encoding="utf-8-sig")
    for column in ["entry_date", "exit_date", "entry_datetime", "exit_datetime"]:
        if column in frame.columns:
            frame[column] = pd.to_datetime(frame[column]).dt.tz_localize(None)
    decision = json.loads(STAGE328_DECISION.read_text(encoding="utf-8"))
    return frame, decision


def _direction_sign(direction: object) -> float:
    return 1.0 if str(direction).lower() == "long" else -1.0


def _tail_features(prior: pd.DataFrame, direction: str, lookback: int) -> dict[str, float]:
    if prior is None or prior.empty or len(prior) < max(10, lookback // 2):
        return {
            f"downside_vol{lookback}_annual_pct": math.nan,
            f"upside_vol{lookback}_annual_pct": math.nan,
            f"down_up_vol_ratio{lookback}": math.nan,
            f"tail_q10_{lookback}_pct": math.nan,
            f"tail_q05_{lookback}_pct": math.nan,
            f"skew{lookback}": math.nan,
            f"loss_day_ratio{lookback}_pct": math.nan,
        }
    close = prior["close"].astype(float)
    returns = close.pct_change().dropna().tail(lookback)
    if len(returns) < max(10, lookback // 2):
        return {
            f"downside_vol{lookback}_annual_pct": math.nan,
            f"upside_vol{lookback}_annual_pct": math.nan,
            f"down_up_vol_ratio{lookback}": math.nan,
            f"tail_q10_{lookback}_pct": math.nan,
            f"tail_q05_{lookback}_pct": math.nan,
            f"skew{lookback}": math.nan,
            f"loss_day_ratio{lookback}_pct": math.nan,
        }
    directional = returns.astype(float) * _direction_sign(direction)
    downside = directional[directional < 0.0]
    upside = directional[directional > 0.0]
    downside_vol = math.sqrt(float(np.mean(np.square(downside)))) * math.sqrt(252.0) * 100.0 if len(downside) else 0.0
    upside_vol = math.sqrt(float(np.mean(np.square(upside)))) * math.sqrt(252.0) * 100.0 if len(upside) else 0.0
    return {
        f"downside_vol{lookback}_annual_pct": downside_vol,
        f"upside_vol{lookback}_annual_pct": upside_vol,
        f"down_up_vol_ratio{lookback}": downside_vol / upside_vol if upside_vol > 1e-9 else math.nan,
        f"tail_q10_{lookback}_pct": float(np.percentile(directional, 10) * 100.0),
        f"tail_q05_{lookback}_pct": float(np.percentile(directional, 5) * 100.0),
        f"skew{lookback}": float(pd.Series(directional).skew()),
        f"loss_day_ratio{lookback}_pct": float((directional < 0.0).mean() * 100.0),
    }


def _add_tail_features(round_trips: pd.DataFrame) -> pd.DataFrame:
    bars_by_symbol = _load_bars_for_round_trips(round_trips)
    rows: list[dict[str, Any]] = []
    for row in round_trips.to_dict("records"):
        vt_symbol = str(row["vt_symbol"])
        entry_date = pd.Timestamp(row["entry_date"]).normalize()
        bars = bars_by_symbol.get(vt_symbol)
        enriched = dict(row)
        if bars is None or bars.empty:
            rows.append(enriched)
            continue
        prior = bars[bars["date"] <= entry_date].copy()
        direction = str(row["direction"]).lower()
        enriched.update(_tail_features(prior, direction, 20))
        enriched.update(_tail_features(prior, direction, 60))
        rows.append(enriched)
    return pd.DataFrame(rows)


def _fixed_downside_bucket(value: object) -> str:
    value = _safe_float(value, math.nan)
    if not np.isfinite(value):
        return "unknown"
    if value <= 15:
        return "downside_vol_low_le15"
    if value <= 30:
        return "downside_vol_mid_15_30"
    return "downside_vol_high_gt30"


def _fixed_tail_bucket(value: object) -> str:
    value = _safe_float(value, math.nan)
    if not np.isfinite(value):
        return "unknown"
    if value >= -1.0:
        return "tail_mild_ge_minus1"
    if value >= -2.0:
        return "tail_mid_minus2_minus1"
    return "tail_deep_lt_minus2"


def _fixed_skew_bucket(value: object) -> str:
    value = _safe_float(value, math.nan)
    if not np.isfinite(value):
        return "unknown"
    if value <= -0.5:
        return "skew_negative_le_minus0_5"
    if value < 0.5:
        return "skew_neutral"
    return "skew_positive_ge0_5"


def _rank_bucket(series: pd.Series, high_label: str, mid_label: str, low_label: str) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    valid = numeric.dropna()
    result = pd.Series("unknown", index=series.index, dtype=object)
    if len(valid) < 20:
        return result
    q1, q2 = valid.quantile([1 / 3, 2 / 3]).tolist()
    result.loc[numeric <= q1] = low_label
    result.loc[(numeric > q1) & (numeric <= q2)] = mid_label
    result.loc[numeric > q2] = high_label
    return result


def _add_buckets(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["downside_vol60_fixed_bucket"] = result["downside_vol60_annual_pct"].map(_fixed_downside_bucket)
    result["downside_vol20_fixed_bucket"] = result["downside_vol20_annual_pct"].map(_fixed_downside_bucket)
    result["tail_q10_60_fixed_bucket"] = result["tail_q10_60_pct"].map(_fixed_tail_bucket)
    result["tail_q10_20_fixed_bucket"] = result["tail_q10_20_pct"].map(_fixed_tail_bucket)
    result["skew60_fixed_bucket"] = result["skew60"].map(_fixed_skew_bucket)
    result["downside_vol60_rank_bucket"] = _rank_bucket(
        result["downside_vol60_annual_pct"],
        "rank_high_downside_vol60",
        "rank_mid_downside_vol60",
        "rank_low_downside_vol60",
    )
    result["tail_q10_60_rank_bucket"] = _rank_bucket(
        -pd.to_numeric(result["tail_q10_60_pct"], errors="coerce"),
        "rank_deep_tail60",
        "rank_mid_tail60",
        "rank_mild_tail60",
    )
    return result


def _summarize(frame: pd.DataFrame, group_type: str, column: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for value, group in frame.groupby(column, dropna=False):
        pnl = pd.to_numeric(group["gross_pnl"], errors="coerce").fillna(0.0)
        mae = pd.to_numeric(group.get("mae_pct", np.nan), errors="coerce")
        mfe = pd.to_numeric(group.get("mfe_pct", np.nan), errors="coerce")
        overlap = pd.to_numeric(group.get("overlaps_max_dd_window", 0), errors="coerce").fillna(0).astype(int)
        rows.append(
            {
                "group_type": group_type,
                "group_value": "missing" if pd.isna(value) else str(value),
                "sample_count": int(len(group)),
                "total_pnl": float(pnl.sum()),
                "mean_pnl": float(pnl.mean()) if len(group) else math.nan,
                "median_pnl": float(pnl.median()) if len(group) else math.nan,
                "win_rate_pct": float((pnl > 0).mean() * 100.0) if len(group) else math.nan,
                "median_mae_pct": float(mae.median()) if mae.notna().any() else math.nan,
                "median_mfe_pct": float(mfe.median()) if mfe.notna().any() else math.nan,
                "dd_overlap_count": int(overlap.sum()),
                "dd_overlap_net_pnl": float(pnl[overlap.eq(1)].sum()),
                "dd_overlap_loss_abs": float((-pnl[overlap.eq(1)].clip(upper=0.0)).sum()),
            }
        )
    return pd.DataFrame(rows)


def _build_summary(frame: pd.DataFrame) -> pd.DataFrame:
    group_columns = [
        ("downside_vol60_fixed", "downside_vol60_fixed_bucket"),
        ("downside_vol20_fixed", "downside_vol20_fixed_bucket"),
        ("tail_q10_60_fixed", "tail_q10_60_fixed_bucket"),
        ("tail_q10_20_fixed", "tail_q10_20_fixed_bucket"),
        ("skew60_fixed", "skew60_fixed_bucket"),
        ("downside_vol60_rank", "downside_vol60_rank_bucket"),
        ("tail_q10_60_rank", "tail_q10_60_rank_bucket"),
    ]
    frames = [_summarize(frame, group_type, column) for group_type, column in group_columns]
    result = pd.concat(frames, ignore_index=True)
    result["loss_per_trade"] = result["total_pnl"] / result["sample_count"].replace(0, np.nan)
    return result.sort_values(["group_type", "group_value"]).reset_index(drop=True)


def _decision(summary: pd.DataFrame) -> dict[str, Any]:
    vol_rank = summary[
        summary["group_type"].eq("downside_vol60_rank")
        & summary["group_value"].isin(["rank_high_downside_vol60", "rank_low_downside_vol60"])
    ].copy()
    high = vol_rank[vol_rank["group_value"].eq("rank_high_downside_vol60")]
    low = vol_rank[vol_rank["group_value"].eq("rank_low_downside_vol60")]
    high_pnl = _safe_float(high["total_pnl"].iloc[0], math.nan) if not high.empty else math.nan
    low_pnl = _safe_float(low["total_pnl"].iloc[0], math.nan) if not low.empty else math.nan
    high_dd_loss = _safe_float(high["dd_overlap_loss_abs"].iloc[0], 0.0) if not high.empty else 0.0
    total_dd_loss = float(
        summary[summary["group_type"].eq("downside_vol60_rank")]
        .drop_duplicates(["group_value"])["dd_overlap_loss_abs"]
        .sum()
    )
    high_dd_loss_share = high_dd_loss / total_dd_loss * 100.0 if total_dd_loss > 0 else math.nan
    candidate_like = bool(
        np.isfinite(high_pnl)
        and np.isfinite(low_pnl)
        and high_pnl < low_pnl
        and high_pnl < 0
        and high_dd_loss_share >= 50.0
    )
    return {
        "decision": "downside_tail_candidate_requires_engine" if candidate_like else "downside_tail_diagnostic_no_promotion",
        "high_downside_vol60_total_pnl": high_pnl,
        "low_downside_vol60_total_pnl": low_pnl,
        "high_downside_vol60_dd_loss_share_pct": high_dd_loss_share,
        "candidate_like": candidate_like,
    }


def _build_report(enriched: pd.DataFrame, summary: pd.DataFrame, decision: dict[str, Any], paths: dict[str, Path]) -> str:
    top = summary.sort_values(["dd_overlap_loss_abs", "total_pnl"], ascending=[False, True]).head(20)
    worst = summary[summary["sample_count"].ge(10)].sort_values("total_pnl").head(20)
    lines = [
        "# Stage050 C3下行半波动与左尾风险诊断",
        "",
        "## 定位",
        "",
        "- 本阶段是只读诊断，不修改 C3，不新增交易规则。",
        "- 外部研究线索显示，商品趋势/动量策略的下行半波动、尾部风险和非对称性可能影响回撤；本阶段先验证它是否能解释 C3 剩余最大回撤。",
        "- 诊断使用入场日前已知的合约日线收益，不使用未来收益构造特征；分位桶只用于归因展示，不能直接当作交易阈值。",
        "",
        "## 样本",
        "",
        f"- 持仓回合数：`{len(enriched)}`",
        f"- 有60日下行风险特征样本：`{pd.to_numeric(enriched['downside_vol60_annual_pct'], errors='coerce').notna().sum()}`",
        f"- 决策标签：`{decision['decision']}`",
        f"- 高60日下行半波动桶全样本净损益：`{decision['high_downside_vol60_total_pnl']:,.2f}`",
        f"- 低60日下行半波动桶全样本净损益：`{decision['low_downside_vol60_total_pnl']:,.2f}`",
        f"- 高60日下行半波动桶在最大回撤窗口亏损占比：`{decision['high_downside_vol60_dd_loss_share_pct']:.4f}%`",
        "",
        "## 最大回撤窗口亏损贡献最高的风险桶",
        "",
        _to_markdown_table(
            top,
            [
                "group_type",
                "group_value",
                "sample_count",
                "total_pnl",
                "win_rate_pct",
                "median_mae_pct",
                "dd_overlap_count",
                "dd_overlap_net_pnl",
                "dd_overlap_loss_abs",
            ],
            max_rows=20,
        ),
        "",
        "## 全样本最差风险桶",
        "",
        _to_markdown_table(
            worst,
            [
                "group_type",
                "group_value",
                "sample_count",
                "total_pnl",
                "mean_pnl",
                "win_rate_pct",
                "median_mae_pct",
                "median_mfe_pct",
                "dd_overlap_count",
            ],
            max_rows=20,
        ),
        "",
        "## 判断",
        "",
    ]
    if decision["decision"] == "downside_tail_candidate_requires_engine":
        lines.extend(
            [
                "- 下行风险桶具备初步解释力，但仍不是正式规则。",
                "- 下一步只能预注册低自由度阈值后做真实引擎验证，不能使用本阶段分位边界调参。",
            ]
        )
    else:
        lines.extend(
            [
                "- 下行半波动/左尾风险没有形成足够强的单一解释变量。",
                "- 不建议把它直接做成开仓过滤、持仓门禁或降仓规则；继续调分位阈值会过拟合。",
            ]
        )
    lines.extend(
        [
            "",
            "## 输出",
            "",
            f"- enriched：`{paths['enriched'].name}`",
            f"- summary：`{paths['summary'].name}`",
            f"- decision：`{paths['decision'].name}`",
            "",
            "## 反思",
            "",
            "- 是否过拟合：否。本阶段只做已冻结 C3 的点时化风险特征归因，没有新增交易参数。",
            "- 是否还有价值继续：若本阶段不能给出稳定解释，则该具体方向继续价值低；总研究线仍有价值，但应换更独立的收益源或部署层候选。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    round_trips, stage328_decision = _load_stage328_round_trips()
    enriched = _add_tail_features(round_trips)
    enriched = _add_buckets(enriched)
    summary = _build_summary(enriched)
    decision_metrics = _decision(summary)
    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "official_version": OFFICIAL_STAGE78_VERSION,
        "official_role": OFFICIAL_STAGE78_ROLE,
        "source_stage": "stage328_c3_single_path_loss_attribution_v1",
        "source_drawdown": stage328_decision.get("drawdown", {}),
        **decision_metrics,
        "overfit_judgement": "否。只读归因，没有修改交易参数。",
        "continue_value_judgement": (
            "有条件。若下行尾部特征解释力不足，应停止该方向；若解释力强，也必须进入预注册真实引擎验证。"
        ),
    }
    paths = {
        "enriched": OUTPUT_DIR / f"{OUTPUT_PREFIX}_round_trips_enriched_{MODEL_TAG}.csv",
        "summary": OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv",
        "report": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md",
        "decision": OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json",
    }
    enriched.to_csv(paths["enriched"], index=False, encoding="utf-8-sig")
    summary.to_csv(paths["summary"], index=False, encoding="utf-8-sig")
    paths["decision"].write_text(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    paths["report"].write_text(_build_report(enriched, summary, decision, paths), encoding="utf-8")
    print(json.dumps(_to_builtin(decision_metrics), ensure_ascii=False, indent=2))
    print(f"[stage350] report: {paths['report']}")


if __name__ == "__main__":
    main()
