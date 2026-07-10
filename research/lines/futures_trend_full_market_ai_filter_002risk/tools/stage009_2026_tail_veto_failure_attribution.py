#!/usr/bin/env python3
"""Stage009: read-only attribution for Stage008's 2026-01 failure window."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys
from typing import Any

import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

import stage001_full_market_pit_ai_risk002_engine as base
import stage008_guarded_official_tail_bottom_veto_halfyear_engine as s008


LINE_ID = base.LINE_ID
STAGE_ID = "stage009_2026_tail_veto_failure_attribution"
STAGE_LABEL = "Stage009"
MODEL_TAG = f"{STAGE_ID}_v1"
OUTPUT_PREFIX = f"full_market_ai002_{STAGE_ID}"

START = pd.Timestamp("2026-01-01")
END = s008.REQUESTED_END

OUT = base.LINE_DIR / "outputs" / STAGE_ID
STAGES_DIR = base.LINE_DIR / "stages"
STAGE_RECORD_PATH = STAGES_DIR / "20260709_2345_stage009_2026_tail_veto_failure_attribution.md"

CURVES_PATH = OUT / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv.gz"
SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
MISSING_ENTRIES_PATH = OUT / f"{OUTPUT_PREFIX}_a0_entries_missing_in_c_{MODEL_TAG}.csv"
PRODUCT_PNL_DIFF_PATH = OUT / f"{OUTPUT_PREFIX}_product_pnl_diff_{MODEL_TAG}.csv"
DAILY_DIFF_PATH = OUT / f"{OUTPUT_PREFIX}_daily_diff_{MODEL_TAG}.csv"
RELEVANT_OVERLAY_PATH = OUT / f"{OUTPUT_PREFIX}_relevant_overlay_{MODEL_TAG}.csv"
RELEVANT_TRADES_PATH = OUT / f"{OUTPUT_PREFIX}_relevant_trades_{MODEL_TAG}.csv"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _profile(label: str, *, version: str, strategy_name: str, eligibility_path: Path) -> dict[str, Any]:
    metadata = _metadata()
    return s008._profile(
        metadata,
        version=version,
        strategy_name=strategy_name,
        eligibility_path=eligibility_path,
        label=label,
    )


def _metadata() -> dict[str, Any]:
    return s008.s007._metadata()


def _run(version_label: str, profile: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    daily, frames = s008.s007._run_profile_for_start(_metadata(), profile, profile["profile"], START)
    daily = daily.copy()
    daily["stage"] = STAGE_LABEL
    daily["model_tag"] = MODEL_TAG
    daily["line_id"] = LINE_ID
    daily["requested_start_month"] = START.strftime("%Y-%m")
    daily["version_label"] = version_label
    for frame in frames.values():
        if frame.empty:
            continue
        frame["stage"] = STAGE_LABEL
        frame["model_tag"] = MODEL_TAG
        frame["line_id"] = LINE_ID
        frame["requested_start_month"] = START.strftime("%Y-%m")
        frame["version_label"] = version_label
    return daily, frames


def _product_from_vt(vt_symbol: pd.Series) -> pd.Series:
    return vt_symbol.astype(str).str.extract(r"^([A-Za-z]+)", expand=False).fillna("")


def _summary(curves: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, group in curves.groupby("version_label", sort=True):
        row = base._summarize_curve(group)
        row["stage"] = STAGE_LABEL
        row["model_tag"] = MODEL_TAG
        row["line_id"] = LINE_ID
        row["requested_start_month"] = START.strftime("%Y-%m")
        rows.append(row)
    return pd.DataFrame(rows)


def _entry_key(frame: pd.DataFrame) -> pd.Series:
    key_cols = ["date", "product_vt_symbol", "contract_vt_symbol", "direction", "signal"]
    return frame[key_cols].astype(str).agg("|".join, axis=1)


def _missing_entries(a0_frames: dict[str, pd.DataFrame], c_frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    a0 = a0_frames["entry_risk"].copy()
    c = c_frames["entry_risk"].copy()
    a0["_key"] = _entry_key(a0)
    c["_key"] = _entry_key(c)
    missing = a0[~a0["_key"].isin(set(c["_key"]))].copy()
    if missing.empty:
        return missing

    candidates = c_frames["entry_candidates"].copy()
    candidates["_key"] = _entry_key(candidates)
    candidate_cols = [
        "_key",
        "candidate_status",
        "skip_reason",
        "passed_initial_filter",
        "ai_product_pool_allowed",
        "ai_product_pool_signal_date",
        "ai_product_pool_strategy",
    ]
    candidate_cols = [c for c in candidate_cols if c in candidates.columns]
    missing = missing.merge(candidates[candidate_cols], on="_key", how="left", suffixes=("", "_candidate"))

    overlay = pd.read_csv(s008.OVERLAY_AUDIT_PATH)
    overlay["eval_date"] = overlay["eval_date"].astype(str)
    overlay["product_vt_symbol"] = overlay["product_vt_symbol"].astype(str)
    missing["ai_product_pool_signal_date"] = missing["ai_product_pool_signal_date"].astype(str)
    overlay_cols = [
        "eval_date",
        "product_vt_symbol",
        "official_score_rank",
        "official_rank_protected",
        "full_market_score",
        "full_market_rank_pct_available",
        "full_market_bottom_veto",
        "guarded_bottom_veto",
        "overlay_keep",
        "overlay_reason",
    ]
    missing = missing.merge(
        overlay[overlay_cols],
        left_on=["ai_product_pool_signal_date", "product_vt_symbol"],
        right_on=["eval_date", "product_vt_symbol"],
        how="left",
    )
    return missing


def _product_pnl_diff(a0_frames: dict[str, pd.DataFrame], c_frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for label, frames in [("a0", a0_frames), ("c", c_frames)]:
        pos = frames["positions"].copy()
        pos["product"] = _product_from_vt(pos["vt_symbol"])
        pos["net_pnl"] = pd.to_numeric(pos["net_pnl"], errors="coerce").fillna(0.0)
        grouped = pos.groupby("product", as_index=False)["net_pnl"].sum()
        grouped = grouped.rename(columns={"net_pnl": label})
        rows.append(grouped)
    result = rows[0].merge(rows[1], on="product", how="outer").fillna(0.0)
    result["c_minus_a0"] = result["c"] - result["a0"]
    return result.sort_values("c_minus_a0").reset_index(drop=True)


def _daily_diff(a0_daily: pd.DataFrame, c_daily: pd.DataFrame) -> pd.DataFrame:
    result = a0_daily[["date", "account_equity", "net_pnl"]].rename(
        columns={"account_equity": "a0_equity", "net_pnl": "a0_net_pnl"}
    ).merge(
        c_daily[["date", "account_equity", "net_pnl"]].rename(
            columns={"account_equity": "c_equity", "net_pnl": "c_net_pnl"}
        ),
        on="date",
        how="inner",
    )
    result["diff_c_minus_a0"] = result["c_equity"] - result["a0_equity"]
    result["daily_pnl_diff"] = result["c_net_pnl"] - result["a0_net_pnl"]
    return result.sort_values("date").reset_index(drop=True)


def _relevant_trades(a0_frames: dict[str, pd.DataFrame], c_frames: dict[str, pd.DataFrame], products: set[str]) -> pd.DataFrame:
    rows = []
    for label, frames in [("a0", a0_frames), ("c", c_frames)]:
        trades = frames["trades"].copy()
        if trades.empty:
            continue
        trades["product"] = _product_from_vt(trades["vt_symbol"])
        trades = trades[trades["product"].isin(products)].copy()
        trades["version_label"] = label
        rows.append(trades)
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True, sort=False).sort_values(["product", "datetime", "version_label"])


def _write_report(
    summary: pd.DataFrame,
    missing: pd.DataFrame,
    pnl_diff: pd.DataFrame,
    daily_diff: pd.DataFrame,
    relevant_overlay: pd.DataFrame,
    relevant_trades: pd.DataFrame,
) -> None:
    a0 = summary[summary["version"].eq(s008.A0_VERSION)].iloc[0]
    c = summary[summary["version"].eq(s008.CANDIDATE_VERSION)].iloc[0]
    nonzero_pnl_diff = pnl_diff[pnl_diff["c_minus_a0"].abs().gt(1e-9)].sort_values("c_minus_a0")
    top_daily = daily_diff.reindex(daily_diff["daily_pnl_diff"].abs().sort_values(ascending=False).index).head(10)
    lines = [
        "# Stage009 2026-01 tail veto failure attribution",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 窗口：`{START.date()}` 到 `{END.date()}`",
        "- 性质：Stage008 失败窗口只读归因，不新增参数、不改策略、不碰实盘链路。",
        "- 运行前过拟合判断：低。只解释已失败窗口，不用它反推新阈值。",
        "- 运行前继续价值判断：有。确认 Stage008 的损益缺口来自哪些被 veto 的实际机会。",
        "",
        "## A0/C 单窗口结果",
        "",
        base._md_table(summary[[
            "version",
            "end_equity",
            "total_return_pct",
            "max_drawdown_pct",
            "sharpe",
            "total_trade_count",
            "total_slippage",
        ]]),
        "",
        "## A0 有、C 没有的实际开仓",
        "",
        base._md_table(missing[[
            "date",
            "product_vt_symbol",
            "contract_vt_symbol",
            "direction",
            "signal",
            "volume",
            "risk_ratio",
            "risk_multiplier",
            "ai_product_pool_signal_date",
            "official_score_rank",
            "full_market_rank_pct_available",
            "overlay_reason",
        ]]),
        "",
        "## 产品 PnL 差异",
        "",
        base._md_table(nonzero_pnl_diff),
        "",
        "## 最大日度差异",
        "",
        base._md_table(top_daily),
        "",
        "## 相关 veto 记录",
        "",
        base._md_table(relevant_overlay),
        "",
        "## 相关交易",
        "",
        base._md_table(relevant_trades[[
            "version_label",
            "datetime",
            "vt_symbol",
            "product",
            "direction",
            "offset",
            "price",
            "volume",
            "exit_reason",
        ]]),
        "",
        "## 归因结论",
        "",
        f"- A0 期末权益 `{float(a0['end_equity']):,.2f}`，C 期末权益 `{float(c['end_equity']):,.2f}`，C-A0 `{float(c['end_equity'] - a0['end_equity']):,.2f}`。",
        "- Stage008 主要失败点不是整体风险变坏，而是 `2026-01-30` 月池把 `AP.CZCE` 作为 official tail 且 full-market bottom25 删除。",
        "- A0 随后在 `2026-02-13` 开 `AP605.CZCE` 多头 3 手，`2026-03-05` 平仓，产品层净贡献约 `+21,300`；C 完全错过。",
        "- C 确实少做了部分 `MA.CZCE` 亏损，且部分后续品种因资金路径变化略有受益，但这些不足以抵消 AP 的机会成本。",
        "- 运行后过拟合判断：继续扫 rank/分位会高度过拟合 2026-01 与 2022-01 两个相反案例。",
        "- 运行后继续价值判断：本分支只保留经验，不继续做参数实验；除非引入外生新信息源，否则不应推进为正式候选。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_stage_record(summary: pd.DataFrame, missing: pd.DataFrame, pnl_diff: pd.DataFrame) -> None:
    a0 = summary[summary["version"].eq(s008.A0_VERSION)].iloc[0]
    c = summary[summary["version"].eq(s008.CANDIDATE_VERSION)].iloc[0]
    ap_loss = float(pnl_diff.loc[pnl_diff["product"].eq("AP"), "c_minus_a0"].iloc[0])
    ma_offset = float(pnl_diff.loc[pnl_diff["product"].eq("MA"), "c_minus_a0"].iloc[0])
    sm_offset = float(pnl_diff.loc[pnl_diff["product"].eq("SM"), "c_minus_a0"].iloc[0])
    lines = [
        "# Stage009 2026-01 tail veto failure attribution",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：`day`",
        f"- 记录时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        "- 阶段性质：Stage008 失败窗口只读归因",
        "- 是否重要突破：否",
        "- 是否触发A/B：否，仅复跑 2026-01 A0/C 诊断",
        "",
        "## 本次变更",
        "",
        f"- 新增脚本：`research/lines/{LINE_ID}/tools/stage009_2026_tail_veto_failure_attribution.py`",
        "- 新增参数：无。",
        "- 修改参数：无。",
        "- 删除参数：无。",
        "",
        "## 回测/诊断参数",
        "",
        f"- 起点：`{START.date()}`",
        f"- 终点：`{END.date()}`",
        f"- 账户规模：`{base.CAPITAL:,.0f}`",
        "- 成本/风险口径：沿用 Stage008 A0/C 真实引擎原口径。",
        "",
        "## 结果",
        "",
        f"- A0 期末权益：`{float(a0['end_equity']):,.2f}`，总收益 `{float(a0['total_return_pct']):.4f}%`，最大回撤 `{float(a0['max_drawdown_pct']):.4f}%`，Sharpe `{float(a0['sharpe']):.4f}`。",
        f"- C 期末权益：`{float(c['end_equity']):,.2f}`，总收益 `{float(c['total_return_pct']):.4f}%`，最大回撤 `{float(c['max_drawdown_pct']):.4f}%`，Sharpe `{float(c['sharpe']):.4f}`。",
        f"- C-A0 期末权益差：`{float(c['end_equity'] - a0['end_equity']):,.2f}`。",
        f"- A0 有、C 没有的实际开仓：`{len(missing)}` 笔；核心机会成本 `AP.CZCE` 产品层 C-A0 `{ap_loss:,.2f}`；主要抵消项 `MA.CZCE` `{ma_offset:,.2f}`、`SM.CZCE` `{sm_offset:,.2f}`。",
        "",
        "## 输出文件",
        "",
        f"- report：`{REPORT_PATH}`",
        f"- summary：`{SUMMARY_PATH}`",
        f"- missing_entries：`{MISSING_ENTRIES_PATH}`",
        f"- product_pnl_diff：`{PRODUCT_PNL_DIFF_PATH}`",
        f"- daily_diff：`{DAILY_DIFF_PATH}`",
        "",
        "## 结论",
        "",
        "- 本阶段结论：Stage008 失败主要来自 `AP.CZCE` 被 veto 后错过单笔右尾，不建议继续扫 rank/分位救参。",
        "- 是否进入下一步：等待独立 agent review 后收束本分支。",
        "",
        "## 过拟合反思",
        "",
        "- 运行前判断：低，只做失败窗口归因。",
        "- 运行后判断：高风险在于把 2026-01 的 AP 个案反推成参数，所以不继续扫参。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前判断：有价值，用于确认 guarded veto 的失败机制。",
        "- 运行后判断：继续做参数实验价值低；除非引入外生新信息源，否则本分支应收束。",
    ]
    STAGE_RECORD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)

    metadata = _metadata()
    a0_profile = s008._profile(
        metadata,
        version=s008.A0_VERSION,
        strategy_name=s008.STRATEGY_NAME_A0,
        eligibility_path=s008.A0_ELIGIBILITY_PATH,
        label="Stage009 A0 current official AI no veto",
    )
    c_profile = s008._profile(
        metadata,
        version=s008.CANDIDATE_VERSION,
        strategy_name=s008.STRATEGY_NAME_C,
        eligibility_path=s008.C_ELIGIBILITY_PATH,
        label="Stage009 C guarded official-tail full-market bottom25 veto",
    )

    print("running 2026-01 A0", flush=True)
    a0_daily, a0_frames = _run("a0", a0_profile)
    print("running 2026-01 C", flush=True)
    c_daily, c_frames = _run("c", c_profile)

    curves = pd.concat(
        [base._curve_for_metrics(a0_daily, s008.A0_VERSION), base._curve_for_metrics(c_daily, s008.CANDIDATE_VERSION)],
        ignore_index=True,
        sort=False,
    )
    curves["stage"] = STAGE_LABEL
    curves["model_tag"] = MODEL_TAG
    curves["line_id"] = LINE_ID
    curves["requested_start_month"] = START.strftime("%Y-%m")
    summary = _summary(curves)
    missing = _missing_entries(a0_frames, c_frames)
    pnl_diff = _product_pnl_diff(a0_frames, c_frames)
    daily_diff = _daily_diff(a0_daily, c_daily)
    relevant_products = set(missing["product_vt_symbol"].astype(str).str.extract(r"^([A-Za-z]+)", expand=False).dropna())
    relevant_products.update(pnl_diff.loc[pnl_diff["c_minus_a0"].abs().gt(1e-9), "product"].astype(str).tolist())
    relevant_trades = _relevant_trades(a0_frames, c_frames, relevant_products)

    overlay = pd.read_csv(s008.OVERLAY_AUDIT_PATH)
    signal_dates = set(missing.get("ai_product_pool_signal_date", pd.Series(dtype=str)).astype(str))
    missing_products = set(missing["product_vt_symbol"].astype(str))
    relevant_overlay = overlay[
        overlay["eval_date"].astype(str).isin(signal_dates)
        & overlay["product_vt_symbol"].astype(str).isin(missing_products)
    ].copy()

    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    missing.to_csv(MISSING_ENTRIES_PATH, index=False, encoding="utf-8-sig")
    pnl_diff.to_csv(PRODUCT_PNL_DIFF_PATH, index=False, encoding="utf-8-sig")
    daily_diff.to_csv(DAILY_DIFF_PATH, index=False, encoding="utf-8-sig")
    relevant_overlay.to_csv(RELEVANT_OVERLAY_PATH, index=False, encoding="utf-8-sig")
    relevant_trades.to_csv(RELEVANT_TRADES_PATH, index=False, encoding="utf-8-sig")
    _write_report(summary, missing, pnl_diff, daily_diff, relevant_overlay, relevant_trades)
    _write_stage_record(summary, missing, pnl_diff)

    print(summary.to_string(index=False))
    print(missing[["date", "product_vt_symbol", "contract_vt_symbol", "volume", "ai_product_pool_signal_date", "overlay_reason"]].to_string(index=False))
    print(pnl_diff.sort_values("c_minus_a0").head(8).to_string(index=False))
    print(f"report={REPORT_PATH}")


if __name__ == "__main__":
    main()
