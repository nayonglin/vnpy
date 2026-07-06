from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
PORTFOLIO_DIR = ROOT / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

import analyze_qmt_roll_stage719_official_winner_trade_forensics as s719  # noqa: E402
import analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow as s901  # noqa: E402


LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage094"
MODEL_TAG = "stage094_stage167_closed_lot_entry_state_audit_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage094_stage167_closed_lot_entry_state_audit"

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage094_stage167_closed_lot_entry_state_audit"
STAGES_DIR = LINE_DIR / "stages"

START_DATES = tuple(pd.Timestamp(f"{year}-{month:02d}-01") for year in range(2020, 2027) for month in (1, 7))
REQUESTED_END = pd.Timestamp("2026-06-30")
START_DATES = tuple(start for start in START_DATES if start <= REQUESTED_END and start.strftime("%Y-%m") <= "2026-01")

CLOSED_LOTS_PATH = OUT / f"{OUTPUT_PREFIX}_closed_lots_{MODEL_TAG}.csv.gz"
CONDITION_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_condition_summary_{MODEL_TAG}.csv"
CONDITION_BY_START_PATH = OUT / f"{OUTPUT_PREFIX}_condition_by_start_{MODEL_TAG}.csv"
RUN_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_run_summary_{MODEL_TAG}.csv"
INPUT_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_input_audit_{MODEL_TAG}.csv"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

SOURCE_FILES = [
    PORTFOLIO_DIR / "analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow.py",
    PORTFOLIO_DIR / "analyze_qmt_roll_stage719_official_winner_trade_forensics.py",
    PORTFOLIO_DIR / "qmt_roll_official_live_config.py",
]

EXTERNAL_RESEARCH = [
    {
        "source": "Expert Systems with Applications trend-following signal filtering abstract",
        "url": "https://www.sciencedirect.com/science/article/abs/pii/S0957417425024030",
        "finding": "Signal filtering can be a valid trend-following research direction, but it must be evaluated out of sample rather than inferred from isolated losing windows.",
    },
    {
        "source": "QuantInsti robust trend following overview",
        "url": "https://quantra.quantinsti.com/glossary/How-to-Create-a-Robust-Trend-Following-Strategy",
        "finding": "Robustness is usually improved through diversification and position sizing, not by stacking many fragile entry filters.",
    },
    {
        "source": "Investopedia futures trend filters",
        "url": "https://www.investopedia.com/articles/optioninvestor/10/trend-following-indicators.asp",
        "finding": "Trend filters are better viewed as constraints on what not to do; they still require explicit buy/sell, sizing, and stop rules.",
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


def _date_text(value: pd.Timestamp) -> str:
    return pd.Timestamp(value).date().isoformat()


def run_closed_lots() -> tuple[pd.DataFrame, pd.DataFrame]:
    metadata = s901.s513._metadata()
    closed_frames: list[pd.DataFrame] = []
    run_rows: list[dict[str, Any]] = []
    for idx, start in enumerate(START_DATES, start=1):
        print(f"[stage094] run {idx}/{len(START_DATES)} start={_date_text(start)}", flush=True)
        combined, frames, _spec = s901._run_live_c9(metadata, start, REQUESTED_END)
        trades = frames.get("trades", pd.DataFrame()).copy()
        entry_risk = frames.get("entry_risk", pd.DataFrame()).copy()
        candidates = frames.get("entry_candidates", pd.DataFrame()).copy()
        closed = s719._build_closed_lots(trades, entry_risk, candidates, metadata)
        if not closed.empty:
            closed["stage"] = STAGE
            closed["model_tag"] = MODEL_TAG
            closed["line_id"] = LINE_ID
            closed["source_live_version"] = s901.OFFICIAL_LIVE_VERSION
            closed["requested_start"] = _date_text(start)
            closed["requested_start_month"] = start.strftime("%Y-%m")
            closed["requested_end"] = _date_text(REQUESTED_END)
            closed_frames.append(closed)
        run_rows.append(
            {
                "requested_start_month": start.strftime("%Y-%m"),
                "daily_rows": int(len(combined)),
                "trade_rows": int(len(trades)),
                "entry_risk_rows": int(len(entry_risk)),
                "entry_candidate_rows": int(len(candidates)),
                "closed_lot_rows": int(len(closed)),
                "closed_lot_realized_pnl": float(pd.to_numeric(closed.get("realized_pnl", 0.0), errors="coerce").sum())
                if not closed.empty
                else 0.0,
                "order_api_calls": 0,
                "ctp_connected": False,
            }
        )
    closed_all = pd.concat(closed_frames, ignore_index=True, sort=False) if closed_frames else pd.DataFrame()
    return closed_all, pd.DataFrame(run_rows)


def add_condition_columns(lots: pd.DataFrame) -> pd.DataFrame:
    data = lots.copy()
    numeric_cols = [
        "realized_pnl",
        "r_multiple",
        "risk_multiplier",
        "loss_streak",
        "active_positions_before",
        "ai_product_pool_rank",
        "ai_product_pool_score",
        "rsi_value",
        "portfolio_drawdown_pct",
        "same_direction_correlation_max_corr",
        "same_direction_correlation_active_count",
        "selected_volume",
        "entry_risk_distance_pct",
        "breakout",
        "recovery_sleeve_applied",
        "streak_entry_structure_risk_recovery_applied",
    ]
    for column in numeric_cols:
        data[column] = pd.to_numeric(data.get(column, np.nan), errors="coerce")
    direction = data.get("direction", pd.Series("", index=data.index)).astype(str).str.lower()
    rank = data["ai_product_pool_rank"]
    data["cond_ai_rank_1_8"] = rank.between(1, 8, inclusive="both")
    data["cond_ai_rank_5_8"] = rank.between(5, 8, inclusive="both")
    data["cond_selected_volume_gt1"] = data["selected_volume"].gt(1)
    data["cond_ai_rank_1_8_and_selected_volume_gt1"] = data["cond_ai_rank_1_8"] & data["cond_selected_volume_gt1"]
    data["cond_risk_multiplier_ge2"] = data["risk_multiplier"].ge(2)
    data["cond_rsi_exhaustion_zone"] = (
        (direction.eq("long") & data["rsi_value"].ge(75))
        | (direction.eq("short") & data["rsi_value"].le(25))
    )
    data["cond_portfolio_dd_ge30pct"] = data["portfolio_drawdown_pct"].ge(0.30)
    data["cond_loss_streak_ge3"] = data["loss_streak"].ge(3)
    data["cond_active_positions_ge2"] = data["active_positions_before"].ge(2)
    data["cond_same_direction_active_ge1"] = data["same_direction_correlation_active_count"].ge(1)
    data["cond_same_direction_corr_abs_ge05"] = data["same_direction_correlation_max_corr"].abs().ge(0.5)
    data["cond_stop_distance_ge2pct"] = data["entry_risk_distance_pct"].ge(0.02)
    data["cond_breakout"] = data["breakout"].fillna(0).gt(0)
    data["cond_recovery_sleeve"] = data["recovery_sleeve_applied"].fillna(0).gt(0)
    data["cond_streak_recovery"] = data["streak_entry_structure_risk_recovery_applied"].fillna(0).gt(0)
    data["cond_dd30_and_risk_multiplier_ge2"] = data["cond_portfolio_dd_ge30pct"] & data["cond_risk_multiplier_ge2"]
    data["cond_dd30_and_selected_volume_gt1"] = data["cond_portfolio_dd_ge30pct"] & data["cond_selected_volume_gt1"]
    data["cond_rsi_exhaustion_and_selected_volume_gt1"] = data["cond_rsi_exhaustion_zone"] & data["cond_selected_volume_gt1"]
    return data


CONDITION_LABELS = {
    "cond_ai_rank_1_8": "AI rank 1-8",
    "cond_ai_rank_5_8": "AI rank 5-8",
    "cond_selected_volume_gt1": "selected_volume > 1",
    "cond_ai_rank_1_8_and_selected_volume_gt1": "AI rank 1-8 and selected_volume > 1",
    "cond_risk_multiplier_ge2": "risk_multiplier >= 2",
    "cond_rsi_exhaustion_zone": "RSI exhaustion: long>=75 or short<=25",
    "cond_portfolio_dd_ge30pct": "portfolio drawdown >= 30%",
    "cond_loss_streak_ge3": "loss_streak >= 3",
    "cond_active_positions_ge2": "active_positions_before >= 2",
    "cond_same_direction_active_ge1": "same-direction active count >= 1",
    "cond_same_direction_corr_abs_ge05": "abs same-direction corr >= 0.5",
    "cond_stop_distance_ge2pct": "entry stop distance >= 2%",
    "cond_breakout": "breakout",
    "cond_recovery_sleeve": "recovery sleeve applied",
    "cond_streak_recovery": "streak recovery applied",
    "cond_dd30_and_risk_multiplier_ge2": "DD>=30% and risk_multiplier>=2",
    "cond_dd30_and_selected_volume_gt1": "DD>=30% and selected_volume>1",
    "cond_rsi_exhaustion_and_selected_volume_gt1": "RSI exhaustion and selected_volume>1",
}


def summarize_conditions(lots: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if lots.empty:
        return pd.DataFrame(), pd.DataFrame()
    total_lots = len(lots)
    total_positive = float(lots.loc[lots["realized_pnl"].gt(0), "realized_pnl"].sum())
    total_negative_abs = float(-lots.loc[lots["realized_pnl"].lt(0), "realized_pnl"].sum())
    total_big_winner_pnl = float(lots.loc[lots.get("big_winner", 0).eq(1), "realized_pnl"].clip(lower=0).sum())
    rows: list[dict[str, Any]] = []
    by_start_rows: list[dict[str, Any]] = []
    all_starts = sorted(lots["requested_start_month"].astype(str).unique().tolist())
    for condition, label in CONDITION_LABELS.items():
        selected = lots[lots[condition].fillna(False).astype(bool)].copy()
        if selected.empty:
            rows.append(
                {
                    "condition": condition,
                    "label": label,
                    "lot_count": 0,
                    "lot_share": 0.0,
                    "start_count": 0,
                    "negative_start_count": 0,
                    "negative_start_rate": np.nan,
                    "realized_pnl_sum": 0.0,
                    "positive_pnl_sum": 0.0,
                    "negative_pnl_abs_sum": 0.0,
                    "loss_capture_share": 0.0,
                    "gain_sacrifice_share": 0.0,
                    "loss_minus_gain_share": 0.0,
                    "winner_rate": np.nan,
                    "median_r_multiple": np.nan,
                    "big_winner_count": 0,
                    "big_winner_pnl": 0.0,
                    "candidate_rule_viable": False,
                }
            )
            continue
        positive = float(selected.loc[selected["realized_pnl"].gt(0), "realized_pnl"].sum())
        negative_abs = float(-selected.loc[selected["realized_pnl"].lt(0), "realized_pnl"].sum())
        realized = float(selected["realized_pnl"].sum())
        by_start = (
            selected.groupby("requested_start_month", as_index=False)
            .agg(
                lot_count=("realized_pnl", "size"),
                realized_pnl_sum=("realized_pnl", "sum"),
                positive_pnl_sum=("realized_pnl", lambda s: float(s[s > 0].sum())),
                negative_pnl_abs_sum=("realized_pnl", lambda s: float(-s[s < 0].sum())),
                winner_rate=("realized_pnl", lambda s: float((s > 0).mean())),
            )
            .copy()
        )
        for start in all_starts:
            if start not in set(by_start["requested_start_month"].astype(str)):
                by_start_rows.append(
                    {
                        "condition": condition,
                        "label": label,
                        "requested_start_month": start,
                        "lot_count": 0,
                        "realized_pnl_sum": 0.0,
                        "positive_pnl_sum": 0.0,
                        "negative_pnl_abs_sum": 0.0,
                        "winner_rate": np.nan,
                    }
                )
        for row in by_start.to_dict("records"):
            by_start_rows.append({"condition": condition, "label": label, **row})
        start_count = int(selected["requested_start_month"].nunique())
        negative_start_count = int(by_start["realized_pnl_sum"].lt(0).sum())
        loss_share = negative_abs / total_negative_abs if total_negative_abs > 0 else np.nan
        gain_share = positive / total_positive if total_positive > 0 else np.nan
        big_winner_pnl = float(selected.loc[selected.get("big_winner", 0).eq(1), "realized_pnl"].clip(lower=0).sum())
        big_winner_pnl_share = big_winner_pnl / total_big_winner_pnl if total_big_winner_pnl > 0 else np.nan
        candidate = bool(
            len(selected) >= 30
            and start_count >= max(6, int(len(all_starts) * 0.5))
            and realized < 0
            and loss_share > gain_share * 1.5
            and (negative_start_count / start_count if start_count else 0.0) >= 0.65
        )
        rows.append(
            {
                "condition": condition,
                "label": label,
                "lot_count": int(len(selected)),
                "lot_share": float(len(selected) / total_lots),
                "start_count": start_count,
                "negative_start_count": negative_start_count,
                "negative_start_rate": float(negative_start_count / start_count) if start_count else np.nan,
                "realized_pnl_sum": realized,
                "realized_pnl_mean": float(selected["realized_pnl"].mean()),
                "positive_pnl_sum": positive,
                "negative_pnl_abs_sum": negative_abs,
                "loss_capture_share": float(loss_share),
                "gain_sacrifice_share": float(gain_share),
                "loss_minus_gain_share": float(loss_share - gain_share),
                "winner_rate": float(selected["realized_pnl"].gt(0).mean()),
                "median_r_multiple": float(pd.to_numeric(selected["r_multiple"], errors="coerce").median()),
                "big_winner_count": int(pd.to_numeric(selected.get("big_winner", 0), errors="coerce").fillna(0).sum()),
                "big_winner_pnl": big_winner_pnl,
                "big_winner_pnl_share": float(big_winner_pnl_share),
                "candidate_rule_viable": candidate,
            }
        )
    summary = pd.DataFrame(rows).sort_values(
        ["candidate_rule_viable", "loss_minus_gain_share", "realized_pnl_sum"],
        ascending=[False, False, True],
    )
    return summary, pd.DataFrame(by_start_rows)


def make_decision(condition_summary: pd.DataFrame, lots: pd.DataFrame, run_summary: pd.DataFrame) -> dict[str, Any]:
    viable = condition_summary[condition_summary["candidate_rule_viable"].astype(bool)].copy()
    best_candidate = ""
    if not viable.empty:
        best = viable.sort_values(["loss_minus_gain_share", "negative_start_rate"], ascending=[False, False]).iloc[0]
        best_candidate = str(best["condition"])
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": "stage094_entry_state_guard_candidate_for_proxy" if best_candidate else "stage094_no_entry_state_guard_candidate",
        "candidate_rule_count": int(len(viable)),
        "best_candidate": best_candidate,
        "closed_lot_rows": int(len(lots)),
        "run_start_count": int(len(run_summary)),
        "closed_lot_realized_pnl": float(pd.to_numeric(lots.get("realized_pnl", 0.0), errors="coerce").sum())
        if not lots.empty
        else 0.0,
        "promote_to_true_engine": False,
        "next_step": (
            f"先对 `{best_candidate}` 做曲线/交易级 no-lookahead proxy，只有 proxy 保留右尾才允许 true engine。"
            if best_candidate
            else "不进入入场状态 hard guard；继续只能转新 PIT 信息源、逐合约持仓贡献下钻或独立低相关收益腿。"
        ),
        "strategy_changed": False,
        "true_engine_run": True,
        "order_api_calls": 0,
        "ctp_connected": False,
        "overfit_after": (
            "否。只用预声明入场前字段做全样本 outcome 审计；没有按产品/方向/坏窗口黑名单或小数阈值救参。"
        ),
        "continue_after": "有" if best_candidate else "有但需换层",
        "continue_reason": (
            "有候选但仍只是 ex-post lot outcome，需要先做 proxy 反事实。"
            if best_candidate
            else "全样本入场状态没有形成稳健 guard；继续调当前字段会变成过拟合。"
        ),
    }


def write_report(
    condition_summary: pd.DataFrame,
    condition_by_start: pd.DataFrame,
    run_summary: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    research_rows = "\n".join(
        f"| {item['source']} | {item['url']} | {item['finding']} |" for item in EXTERNAL_RESEARCH
    )
    report = f"""# {STAGE} Stage167 Closed-Lot Entry State Audit

## 外部调研与判断

| source | url | finding |
| --- | --- | --- |
{research_rows}

我的判断：入场过滤必须先证明它在全路径上捕获亏损且少牺牲右尾，不能只从坏窗口亏损仓反推。Stage094 只做 outcome 审计，不直接改变策略。

## Run Summary

{_md_table(run_summary)}

## Condition Summary

{_md_table(condition_summary)}

## Condition By Start

{_md_table(condition_by_start.sort_values(["condition", "requested_start_month"]), 120)}

## 决策

```json
{json.dumps(_json_safe(decision), ensure_ascii=False, indent=2)}
```

## 过拟合反思

- 运行前：否。条件来自既有入场前字段和 Stage025 已暴露出的候选族，但本阶段改为全样本检验。
- 运行后：{decision['overfit_after']}

## 继续价值反思

- 运行前：有。Stage025/026 说明只看坏窗口会误导，需要全路径 closed-lot outcome。
- 运行后：{decision['continue_after']}。{decision['continue_reason']}

## 输出

- closed_lots：`{CLOSED_LOTS_PATH}`
- condition_summary：`{CONDITION_SUMMARY_PATH}`
- condition_by_start：`{CONDITION_BY_START_PATH}`
- run_summary：`{RUN_SUMMARY_PATH}`
- input_audit：`{INPUT_AUDIT_PATH}`
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def write_stage_record(
    condition_summary: pd.DataFrame,
    condition_by_start: pd.DataFrame,
    run_summary: pd.DataFrame,
    decision: dict[str, Any],
) -> Path:
    now = datetime.now()
    stage_path = STAGES_DIR / f"{now:%Y%m%d_%H%M}_stage094_stage167_closed_lot_entry_state_audit.md"
    text = f"""# Stage094 Stage167 全路径入场状态 closed-lot 审计

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{now:%Y-%m-%d %H:%M} CST
- 工作区/分支：`{ROOT}`
- 阶段性质：只读真实引擎复跑 + closed-lot outcome 审计
- 是否重要突破：否
- 是否触发A/B：否，本阶段不提出可合入候选

## 外部调研与判断

- 参考资料：trend-following signal filtering、robust trend following、trend filters。
- 我的判断：入场状态过滤只有在全路径 closed lots 上负期望稳定、且右尾牺牲少于亏损捕获时，才值得进入 proxy；不能从坏窗口亏损仓直接反推。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage094_stage167_closed_lot_entry_state_audit.py`
- 修改脚本：无正式交易入口修改。
- 删除脚本：无。
- 新增参数：预声明入场状态条件族；不新增正式交易参数。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：`2020-01` 至 `2026-01` 逐半年起点，统一终点 `2026-06-30`。
- 账户规模：`150,000`
- 引擎口径：复用 Stage901/Stage167 official live C9 wrapper；额外用 Stage719 `_build_closed_lots` 生成每笔 closed-lot outcome。
- 成本口径：沿用 live wrapper trades 和 closed-lot 实现。
- 审计口径：只用入场前可见字段分组；不做产品/方向/日期黑名单；不生成订单。

## Run Summary

{_md_table(run_summary)}

## Condition Summary

{_md_table(condition_summary)}

## Condition By Start

{_md_table(condition_by_start.sort_values(["condition", "requested_start_month"]), 120)}

## 结论

- 本阶段结论：`{decision['decision']}`。
- 候选数：`{decision['candidate_rule_count']}`。
- 最优候选：`{decision['best_candidate']}`。
- 是否进入下一步：`{decision['promote_to_true_engine']}`。
- 下一步：{decision['next_step']}

## 回测记录字段

- closed-lot realized pnl：`{decision['closed_lot_realized_pnl']:.4f}`
- 总滑点/交易次数：本阶段未新增策略版本汇总曲线；详见 run summary 和 Stage167 baseline。
- 期末权益/总收益/最大回撤/Sharpe/胜率：本阶段不是新策略回测，保留 Stage167 baseline。

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
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段无重要突破。
"""
    stage_path.write_text(text, encoding="utf-8")
    return stage_path


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    lots_raw, run_summary = run_closed_lots()
    lots = add_condition_columns(lots_raw) if not lots_raw.empty else lots_raw
    condition_summary, condition_by_start = summarize_conditions(lots)
    input_audit = _input_audit(SOURCE_FILES)
    decision = make_decision(condition_summary, lots, run_summary)

    lots.to_csv(CLOSED_LOTS_PATH, index=False, encoding="utf-8-sig", compression="gzip")
    condition_summary.to_csv(CONDITION_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    condition_by_start.to_csv(CONDITION_BY_START_PATH, index=False, encoding="utf-8-sig")
    run_summary.to_csv(RUN_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    input_audit.to_csv(INPUT_AUDIT_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(condition_summary, condition_by_start, run_summary, decision)
    stage_path = write_stage_record(condition_summary, condition_by_start, run_summary, decision)
    print(json.dumps(_json_safe({"decision": decision, "stage_path": stage_path, "report_path": REPORT_PATH}), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
