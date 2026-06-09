from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

SOURCE_PREFIX = "qmt_roll_stage719_official_winner_trade_forensics"
SOURCE_TAG = "stage719_official_winner_trade_forensics_v1"
SOURCE_CLOSED_LOTS_PATH = OUTPUT_DIR / f"{SOURCE_PREFIX}_closed_lots_{SOURCE_TAG}.csv"

MODEL_TAG = "stage732_risk_floor_trade_review_v1"
OUTPUT_PREFIX = "qmt_roll_stage732_risk_floor_trade_review"
LINE_ID = "futures_trend_winner_trade_forensics"

RISK_FLOOR_LOTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_risk_floor_lots_{MODEL_TAG}.csv"
BIG_WINNERS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_big_winners_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
YEAR_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _json_safe(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if np.isnan(value) or np.isinf(value):
            return None
        return float(value)
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if pd.isna(value):
        return None
    return value


def _fmt_float(value: Any, digits: int = 2, missing: str = "NA") -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return missing
    if np.isnan(number) or np.isinf(number):
        return missing
    return f"{number:.{digits}f}"


def _fmt_money(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "NA"
    if np.isnan(number) or np.isinf(number):
        return "NA"
    return f"{number:,.0f}"


def _fmt_bool(value: Any) -> str:
    try:
        return "是" if int(float(value)) == 1 else "否"
    except (TypeError, ValueError):
        return "NA"


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_无记录_"
    data = frame.copy()
    if max_rows is not None:
        data = data.head(max_rows)
    headers = [str(column) for column in data.columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for _, row in data.iterrows():
        values = []
        for value in row.tolist():
            if isinstance(value, float):
                values.append(_fmt_float(value, 4))
            else:
                values.append(str(value))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def _classify(row: pd.Series) -> str:
    r_multiple = float(row.get("r_multiple", np.nan))
    mfe_r = float(row.get("mfe_r", np.nan))
    big_threshold = float(row.get("big_winner_threshold_r", np.nan))
    if int(row.get("big_winner", 0)) == 1:
        return "realized_big_winner"
    if not np.isnan(mfe_r) and not np.isnan(big_threshold) and mfe_r >= big_threshold:
        return "big_mfe_gave_back"
    if r_multiple >= 1.0:
        return "ordinary_winner_ge_1r"
    if r_multiple > 0.0:
        return "small_winner"
    if not np.isnan(mfe_r) and mfe_r >= 1.0:
        return "failed_after_1r_mfe"
    return "loss_or_no_right_tail"


def _risk_floor_reason(row: pd.Series) -> str:
    reasons: list[str] = []
    loss_streak = row.get("loss_streak")
    try:
        if float(loss_streak) >= 3.0:
            reasons.append(f"连续亏损{int(float(loss_streak))}笔")
    except (TypeError, ValueError):
        pass
    if int(float(row.get("recovery_sleeve_applied", 0) or 0)) == 1:
        reasons.append("official recovery sleeve")
    if int(float(row.get("streak_entry_structure_risk_recovery_applied", 0) or 0)) == 1:
        reasons.append("streak structure recovery")
    return " + ".join(reasons) if reasons else "risk_multiplier=0.1"


def _review_text(row: pd.Series) -> str:
    group = row["review_group"]
    r_text = _fmt_float(row.get("r_multiple"), 2)
    mfe_text = _fmt_float(row.get("mfe_r"), 2)
    mae_text = _fmt_float(row.get("mae_r"), 2)
    exit_eff = _fmt_float(row.get("exit_efficiency"), 2)
    pnl_text = _fmt_money(row.get("realized_pnl"))
    linear_delta = _fmt_money(row.get("linear_delta_vs_actual"))
    mfe_part = f"{mfe_text}R" if mfe_text != "NA" else "NA"
    mae_part = f"{mae_text}R" if mae_text != "NA" else "NA"
    base = (
        f"{row['vt_symbol']} {row['direction']}，{row['entry_date']} 入场，"
        f"{row['exit_date']} 退出，{row['exit_reason']}，最终 {pnl_text} / {r_text}R；"
        f"MFE {mfe_part}，MAE {mae_part}，退出效率 {exit_eff}。"
    )
    if group == "realized_big_winner":
        verdict = (
            "这是唯一真正被 0.1 风险压小的已实现大赢家；若只按风险倍率线性放大到 1.0，"
            f"少赚约 {linear_delta}。"
        )
    elif group == "big_mfe_gave_back":
        verdict = (
            "盘中曾达到大赢家级别 MFE，但最终回吐成亏损；它说明入场有右尾潜力，"
            "但不能证明应该放开 0.1 风险，因为退出/路径质量没有锁住右尾。"
        )
    elif group == "ordinary_winner_ge_1r":
        verdict = "这是 1R 以上普通赢家，放大风险会增加收益，但不属于当前正式口径的大赢家。"
    elif group == "small_winner":
        verdict = "这是小赢家，证明 0.1 档并非完全无效，但右尾贡献有限。"
    elif group == "failed_after_1r_mfe":
        verdict = "曾经到过 1R 以上浮盈但最后失败，核心问题是趋势延续不足或退出回吐。"
    else:
        verdict = "没有形成可补偿连败环境的大右尾，是 0.1 防守档主要想压住的交易。"
    return f"{base}{verdict}"


def _load_risk_floor_lots() -> pd.DataFrame:
    if not SOURCE_CLOSED_LOTS_PATH.exists():
        raise FileNotFoundError(f"missing source file: {SOURCE_CLOSED_LOTS_PATH}")
    data = pd.read_csv(SOURCE_CLOSED_LOTS_PATH, encoding="utf-8-sig")
    for column in [
        "risk_multiplier",
        "loss_streak",
        "realized_pnl",
        "risk_amount",
        "r_multiple",
        "mfe_r",
        "mae_r",
        "exit_efficiency",
        "big_winner_threshold_r",
        "portfolio_drawdown_pct",
        "target_risk_amount",
        "selected_volume",
        "contracts_by_risk",
        "contracts_by_margin",
        "stop_distance",
        "entry_risk_distance_pct",
        "ai_product_pool_rank",
        "ai_product_pool_score",
        "rsi_value",
        "active_positions_before",
    ]:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    for column in ["entry_date", "exit_date"]:
        data[column] = pd.to_datetime(data[column], errors="coerce").dt.strftime("%Y-%m-%d")
    mask = (data["risk_multiplier"] <= 0.100001) | (data["risk_multiplier_bucket"].astype(str) == "risk_floor_01")
    result = data.loc[mask].copy().sort_values(["entry_date", "lot_id"]).reset_index(drop=True)
    result["review_group"] = result.apply(_classify, axis=1)
    result["risk_floor_reason"] = result.apply(_risk_floor_reason, axis=1)
    result["linear_full_risk_pnl_est"] = np.where(
        result["risk_multiplier"] > 0.0,
        result["realized_pnl"] / result["risk_multiplier"],
        np.nan,
    )
    result["linear_delta_vs_actual"] = result["linear_full_risk_pnl_est"] - result["realized_pnl"]
    result["linear_warning"] = "仅按风险倍率线性估算，未重跑保证金/整数手/组合排队"
    result["review_text"] = result.apply(_review_text, axis=1)
    return result


def _build_summary(lots: pd.DataFrame) -> pd.DataFrame:
    threshold = float(lots["big_winner_threshold_r"].dropna().iloc[0])
    winners = lots[lots["realized_pnl"] > 0]
    losers = lots[lots["realized_pnl"] <= 0]
    mfe_big = lots[lots["mfe_r"] >= threshold]
    rows = [
        {
            "metric": "risk_floor_closed_lots",
            "value": len(lots),
            "note": "正式版实际成交里 risk_multiplier=0.1 的 closed lots",
        },
        {
            "metric": "winner_lots",
            "value": len(winners),
            "note": "最终 realized_pnl > 0",
        },
        {
            "metric": "realized_big_winner_lots",
            "value": int(lots["big_winner"].sum()),
            "note": f"Stage719 预声明阈值 r_multiple >= {threshold:.4f}",
        },
        {
            "metric": "big_mfe_lots",
            "value": len(mfe_big),
            "note": f"持仓路径 MFE 达到大赢家阈值 {threshold:.4f}R",
        },
        {
            "metric": "actual_pnl_sum",
            "value": float(lots["realized_pnl"].sum()),
            "note": "0.1 档实际总盈亏",
        },
        {
            "metric": "linear_full_risk_pnl_est_sum",
            "value": float(lots["linear_full_risk_pnl_est"].sum()),
            "note": "仅按风险倍率线性放大到 1.0 的总盈亏估算",
        },
        {
            "metric": "missed_winner_upside_linear",
            "value": float(winners["linear_delta_vs_actual"].sum()),
            "note": "只看盈利交易，0.1 相比 1.0 少赚的线性估算",
        },
        {
            "metric": "avoided_loser_downside_linear",
            "value": float(-losers["linear_delta_vs_actual"].sum()),
            "note": "只看亏损交易，0.1 相比 1.0 少亏的线性估算",
        },
        {
            "metric": "net_protection_linear",
            "value": float(lots["realized_pnl"].sum() - lots["linear_full_risk_pnl_est"].sum()),
            "note": "实际 0.1 档相对线性 1.0 的净保护估算",
        },
        {
            "metric": "sum_r_multiple",
            "value": float(lots["r_multiple"].sum()),
            "note": "R 倍数总和，风险单位化后仍为负",
        },
    ]
    return pd.DataFrame(rows)


def _build_year_summary(lots: pd.DataFrame) -> pd.DataFrame:
    data = lots.copy()
    data["entry_year"] = pd.to_datetime(data["entry_date"]).dt.year
    return (
        data.groupby("entry_year", dropna=False)
        .agg(
            lots=("lot_id", "count"),
            winners=("winner", "sum"),
            big_winners=("big_winner", "sum"),
            big_mfe_lots=("review_group", lambda s: int((s == "big_mfe_gave_back").sum() + (s == "realized_big_winner").sum())),
            pnl=("realized_pnl", "sum"),
            r_sum=("r_multiple", "sum"),
            avg_r=("r_multiple", "mean"),
            min_r=("r_multiple", "min"),
            max_r=("r_multiple", "max"),
        )
        .reset_index()
    )


def _build_report(lots: pd.DataFrame, summary: pd.DataFrame, year_summary: pd.DataFrame) -> str:
    threshold = float(lots["big_winner_threshold_r"].dropna().iloc[0])
    key_cols = [
        "lot_id",
        "vt_symbol",
        "direction",
        "entry_date",
        "exit_date",
        "realized_pnl",
        "r_multiple",
        "mfe_r",
        "mae_r",
        "loss_streak",
        "exit_reason",
        "review_group",
    ]
    big_cols = [
        "lot_id",
        "vt_symbol",
        "direction",
        "entry_date",
        "exit_date",
        "realized_pnl",
        "r_multiple",
        "mfe_r",
        "mae_r",
        "exit_efficiency",
        "loss_streak",
        "linear_delta_vs_actual",
        "review_text",
    ]
    big_or_mfe = lots[lots["review_group"].isin(["realized_big_winner", "big_mfe_gave_back"])]

    lines = [
        "# Stage732 正式版 0.1 风险交易逐笔复盘",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} CST",
        f"- 研究线：`{LINE_ID}`",
        f"- 数据源：`{SOURCE_CLOSED_LOTS_PATH.name}`",
        "- 口径：只读正式版 Stage372/20万 Stage719 closed lots，筛选 `risk_multiplier<=0.100001` 或 `risk_multiplier_bucket=risk_floor_01`。",
        f"- 大赢家定义：沿用 Stage719 预声明 `r_multiple >= {threshold:.4f}`，不在本阶段重定义阈值。",
        "",
        "## 总览",
        "",
        _md_table(summary),
        "",
        "## 年度分布",
        "",
        _md_table(year_summary),
        "",
        "## 真大赢家与大 MFE 回吐",
        "",
        _md_table(big_or_mfe[big_cols]),
        "",
        "## 全部 0.1 风险交易明细",
        "",
        _md_table(lots[key_cols]),
        "",
        "## 每笔完整复盘",
        "",
    ]

    detail_cols = [
        "risk_floor_reason",
        "signal",
        "entry_context",
        "layer_kind",
        "active_positions_before",
        "ai_product_pool_allowed",
        "ai_product_pool_rank",
        "ai_product_pool_score",
        "rsi_value",
        "breakout",
        "bullish_alignment",
        "bearish_alignment",
        "portfolio_drawdown_pct",
        "same_direction_correlation_max_corr",
        "same_direction_correlation_active_count",
        "target_risk_amount",
        "selected_volume",
        "contracts_by_risk",
        "contracts_by_margin",
        "stop_distance",
        "entry_risk_distance_pct",
        "path_bar_count",
        "days_to_mfe",
        "days_to_mae",
        "linear_full_risk_pnl_est",
        "linear_delta_vs_actual",
    ]
    for row in lots.itertuples(index=False):
        record = row._asdict()
        lines.extend(
            [
                f"### lot_id {record['lot_id']} - {record['vt_symbol']} {record['direction']}",
                "",
                f"- 结论：{record['review_text']}",
                f"- 0.1 原因：{record['risk_floor_reason']}",
                f"- 是否最终大赢家：{_fmt_bool(record.get('big_winner'))}；是否最终盈利：{_fmt_bool(record.get('winner'))}；分类：`{record['review_group']}`",
            ]
        )
        for column in detail_cols:
            value = record.get(column)
            if column in {
                "target_risk_amount",
                "linear_full_risk_pnl_est",
                "linear_delta_vs_actual",
            }:
                text = _fmt_money(value)
            elif column in {
                "ai_product_pool_score",
                "rsi_value",
                "portfolio_drawdown_pct",
                "same_direction_correlation_max_corr",
                "stop_distance",
                "entry_risk_distance_pct",
            }:
                text = _fmt_float(value, 4)
            else:
                text = "NA" if pd.isna(value) else str(value)
            lines.append(f"- {column}：{text}")
        lines.append("")

    lines.extend(
        [
            "## 反过拟合判断",
            "",
            "- 本阶段只复盘既有成交，不新增策略条件，因此不是交易化过拟合。",
            "- 但不能把唯一一笔真大赢家或一笔大 MFE 回吐交易直接提炼成豁免条件；样本太少，且收益集中在单一年份/单一局部状态。",
            "- 更稳的结论是：0.1 风险档整体仍为有效防守，若要找豁免，需要外生、前置、可 walk-forward 的质量特征，而不是从这 51 笔里倒推规则。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    lots = _load_risk_floor_lots()
    summary = _build_summary(lots)
    year_summary = _build_year_summary(lots)
    big_winners = lots[lots["big_winner"] == 1].copy()

    RISK_FLOOR_LOTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    lots.to_csv(RISK_FLOOR_LOTS_PATH, index=False, encoding="utf-8-sig")
    big_winners.to_csv(BIG_WINNERS_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    year_summary.to_csv(YEAR_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    REPORT_PATH.write_text(_build_report(lots, summary, year_summary), encoding="utf-8")

    threshold = float(lots["big_winner_threshold_r"].dropna().iloc[0])
    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "source_closed_lots_path": str(SOURCE_CLOSED_LOTS_PATH),
        "risk_floor_lots": int(len(lots)),
        "winner_lots": int((lots["realized_pnl"] > 0).sum()),
        "realized_big_winner_lots": int(lots["big_winner"].sum()),
        "big_winner_threshold_r": threshold,
        "big_mfe_lots": int((lots["mfe_r"] >= threshold).sum()),
        "actual_pnl_sum": float(lots["realized_pnl"].sum()),
        "linear_full_risk_pnl_est_sum": float(lots["linear_full_risk_pnl_est"].sum()),
        "net_protection_linear": float(lots["realized_pnl"].sum() - lots["linear_full_risk_pnl_est"].sum()),
        "decision": "risk_floor_trade_review_supports_defensive_throttle_no_exemption_feature",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    DECISION_PATH.write_text(
        json.dumps({key: _json_safe(value) for key, value in decision.items()}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(decision, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
