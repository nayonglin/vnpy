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


LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage100"
MODEL_TAG = "stage100_early_no_progress_lot_proxy_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage100_early_no_progress_lot_proxy"

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage100_early_no_progress_lot_proxy"
STAGES_DIR = LINE_DIR / "stages"

STAGE094_OUT = LINE_DIR / "outputs" / "stage094_stage167_closed_lot_entry_state_audit"
STAGE094_PREFIX = "rebuilt_c9_v2_stage094_stage167_closed_lot_entry_state_audit"
STAGE094_TAG = "stage094_stage167_closed_lot_entry_state_audit_v1"
CLOSED_LOTS_PATH = STAGE094_OUT / f"{STAGE094_PREFIX}_closed_lots_{STAGE094_TAG}.csv.gz"

LOT_PROXY_PATH = OUT / f"{OUTPUT_PREFIX}_lot_proxy_{MODEL_TAG}.csv.gz"
VARIANT_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_variant_summary_{MODEL_TAG}.csv"
VARIANT_BY_START_PATH = OUT / f"{OUTPUT_PREFIX}_variant_by_start_{MODEL_TAG}.csv"
CLASSIFICATION_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_classification_summary_{MODEL_TAG}.csv"
INPUT_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_input_audit_{MODEL_TAG}.csv"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

EXTERNAL_RESEARCH = [
    {
        "source": "pysystemtrade backtesting documentation",
        "url": "https://github.com/pst-group/pysystemtrade/blob/develop/docs/backtesting.md",
        "finding": "Position buffering and cost separation matter; a lot-level proxy is only a screen before full engine validation.",
    },
    {
        "source": "Rob Carver, Dynamic trend following",
        "url": "https://qoppac.blogspot.com/2020/12/dynamic-trend-following.html",
        "finding": "Tight early stops or changing exits can protect some paths but risk killing right tails; no-progress exits need right-tail damage checks.",
    },
    {
        "source": "Hudson & Thames meta-labeling / triple barrier",
        "url": "https://hudsonthames.org/does-meta-labeling-add-to-signal-efficacy-triple-barrier-method/",
        "finding": "Secondary filters should be available at decision time and then validated OOS; path labels alone are not a trading rule.",
    },
]

VARIANTS = [
    {
        "variant": "no_progress_3bars_mfe_lt05r",
        "label": "3 completed daily bars, MFE < 0.5R",
        "kind": "no_progress",
        "bar_count": 3,
        "mfe_r_threshold": 0.5,
        "require_underwater": False,
        "giveback_mfe_r": np.nan,
    },
    {
        "variant": "no_progress_5bars_mfe_lt1r",
        "label": "5 completed daily bars, MFE < 1.0R",
        "kind": "no_progress",
        "bar_count": 5,
        "mfe_r_threshold": 1.0,
        "require_underwater": False,
        "giveback_mfe_r": np.nan,
    },
    {
        "variant": "underwater_5bars_mfe_lt1r",
        "label": "5 completed daily bars, MFE < 1.0R and current PnL < 0",
        "kind": "no_progress",
        "bar_count": 5,
        "mfe_r_threshold": 1.0,
        "require_underwater": True,
        "giveback_mfe_r": np.nan,
    },
    {
        "variant": "giveback_2r_to_underwater",
        "label": "After MFE >= 2R, exit if EOD PnL turns negative",
        "kind": "giveback",
        "bar_count": 0,
        "mfe_r_threshold": np.nan,
        "require_underwater": True,
        "giveback_mfe_r": 2.0,
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


def load_lots() -> pd.DataFrame:
    lots = pd.read_csv(CLOSED_LOTS_PATH, encoding="utf-8-sig")
    lots["entry_date"] = pd.to_datetime(lots["entry_date"], errors="coerce").dt.normalize()
    lots["exit_date"] = pd.to_datetime(lots["exit_date"], errors="coerce").dt.normalize()
    for column in [
        "entry_price",
        "exit_price",
        "volume",
        "size",
        "realized_pnl",
        "risk_amount",
        "r_multiple",
        "holding_calendar_days",
        "mfe_r",
        "mae_r",
    ]:
        lots[column] = pd.to_numeric(lots.get(column, np.nan), errors="coerce")
    lots["requested_start_month"] = lots["requested_start_month"].astype(str)
    return lots.dropna(subset=["entry_date", "exit_date", "vt_symbol", "entry_price", "realized_pnl"]).copy()


def _path_for_lot(lot: pd.Series) -> pd.DataFrame:
    bars = s719._read_contract_bars(lot["vt_symbol"])
    if bars.empty:
        return pd.DataFrame()
    window = bars[(bars["date"] >= lot["entry_date"]) & (bars["date"] <= lot["exit_date"])].copy()
    if window.empty:
        return pd.DataFrame()
    direction = str(lot["direction"])
    entry_price = float(lot["entry_price"])
    size = float(lot["size"])
    volume = float(lot["volume"])
    risk_amount = float(lot["risk_amount"]) if np.isfinite(float(lot.get("risk_amount", np.nan))) else np.nan
    if entry_price <= 0 or size <= 0 or volume <= 0:
        return pd.DataFrame()
    if direction == "long":
        window["close_pnl"] = (window["close"] - entry_price) * size * volume
        window["high_pnl"] = (window["high"] - entry_price) * size * volume
        window["low_pnl"] = (window["low"] - entry_price) * size * volume
        window["favorable_pnl"] = window["high_pnl"]
        window["adverse_pnl"] = -window["low_pnl"]
    else:
        window["close_pnl"] = (entry_price - window["close"]) * size * volume
        window["high_pnl"] = (entry_price - window["low"]) * size * volume
        window["low_pnl"] = (entry_price - window["high"]) * size * volume
        window["favorable_pnl"] = window["high_pnl"]
        window["adverse_pnl"] = -window["low_pnl"]
    window["bar_number"] = np.arange(1, len(window) + 1)
    window["cum_mfe_cash"] = window["favorable_pnl"].cummax().clip(lower=0.0)
    window["cum_mae_cash"] = window["adverse_pnl"].cummax().clip(lower=0.0)
    if np.isfinite(risk_amount) and risk_amount > 0:
        window["close_r"] = window["close_pnl"] / risk_amount
        window["cum_mfe_r"] = window["cum_mfe_cash"] / risk_amount
        window["cum_mae_r"] = window["cum_mae_cash"] / risk_amount
    else:
        window["close_r"] = np.nan
        window["cum_mfe_r"] = np.nan
        window["cum_mae_r"] = np.nan
    return window


def _proxy_lot(lot: pd.Series, variant_spec: dict[str, Any]) -> dict[str, Any]:
    path = _path_for_lot(lot)
    original = float(lot["realized_pnl"])
    base = {
        "variant": variant_spec["variant"],
        "variant_label": variant_spec["label"],
        "requested_start_month": lot["requested_start_month"],
        "lot_id": int(lot["lot_id"]),
        "vt_symbol": lot["vt_symbol"],
        "direction": lot["direction"],
        "entry_date": lot["entry_date"],
        "exit_date": lot["exit_date"],
        "exit_reason": lot.get("exit_reason", ""),
        "holding_calendar_days": float(lot["holding_calendar_days"]),
        "risk_amount": float(lot["risk_amount"]) if pd.notna(lot.get("risk_amount")) else np.nan,
        "original_pnl": original,
        "original_r": float(lot["r_multiple"]) if pd.notna(lot.get("r_multiple")) else np.nan,
        "triggered": False,
        "trigger_date": pd.NaT,
        "trigger_bar_number": 0,
        "trigger_close_r": np.nan,
        "trigger_mfe_r": np.nan,
        "proxy_pnl": original,
        "proxy_delta": 0.0,
        "loss_reduced": 0.0,
        "gain_sacrificed": 0.0,
    }
    if path.empty:
        base["path_missing"] = True
        return base
    base["path_missing"] = False
    trigger_row: pd.Series | None = None
    if variant_spec["kind"] == "no_progress":
        bar_count = int(variant_spec["bar_count"])
        if len(path) > bar_count:
            row = path.iloc[bar_count - 1]
            mfe_r = float(row["cum_mfe_r"]) if pd.notna(row["cum_mfe_r"]) else np.nan
            close_r = float(row["close_r"]) if pd.notna(row["close_r"]) else np.nan
            if np.isfinite(mfe_r) and mfe_r < float(variant_spec["mfe_r_threshold"]):
                if not bool(variant_spec["require_underwater"]) or (np.isfinite(close_r) and close_r < 0.0):
                    trigger_row = row
    elif variant_spec["kind"] == "giveback":
        threshold = float(variant_spec["giveback_mfe_r"])
        candidates = path[path["cum_mfe_r"].ge(threshold) & path["close_r"].lt(0.0)].copy()
        if not candidates.empty:
            trigger_row = candidates.iloc[0]
    if trigger_row is None:
        return base
    proxy_pnl = float(trigger_row["close_pnl"])
    delta = proxy_pnl - original
    base.update(
        {
            "triggered": True,
            "trigger_date": trigger_row["date"],
            "trigger_bar_number": int(trigger_row["bar_number"]),
            "trigger_close_r": float(trigger_row["close_r"]) if pd.notna(trigger_row["close_r"]) else np.nan,
            "trigger_mfe_r": float(trigger_row["cum_mfe_r"]) if pd.notna(trigger_row["cum_mfe_r"]) else np.nan,
            "proxy_pnl": proxy_pnl,
            "proxy_delta": delta,
            "loss_reduced": max(delta, 0.0) if original < 0 else 0.0,
            "gain_sacrificed": max(-delta, 0.0) if original > 0 else max(-delta, 0.0),
        }
    )
    return base


def build_lot_proxy(lots: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, lot in lots.iterrows():
        for spec in VARIANTS:
            rows.append(_proxy_lot(lot, spec))
    return pd.DataFrame(rows)


def build_variant_summary(proxy: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    # Compute from unique lots to avoid counting variants repeatedly.
    unique_lots = proxy.drop_duplicates(["requested_start_month", "lot_id"])
    original_total = float(unique_lots["original_pnl"].sum())
    original_positive = float(unique_lots.loc[unique_lots["original_pnl"].gt(0), "original_pnl"].sum())
    original_negative_abs = float(-unique_lots.loc[unique_lots["original_pnl"].lt(0), "original_pnl"].sum())
    all_starts = sorted(proxy["requested_start_month"].unique().tolist())
    for variant, frame in proxy.groupby("variant", sort=True):
        by_start = (
            frame.groupby("requested_start_month", as_index=False)
            .agg(
                original_pnl=("original_pnl", "sum"),
                proxy_pnl=("proxy_pnl", "sum"),
                proxy_delta=("proxy_delta", "sum"),
                triggered_lots=("triggered", "sum"),
                path_missing_lots=("path_missing", "sum"),
            )
            .copy()
        )
        positive_delta_starts = int(by_start["proxy_delta"].gt(0).sum())
        negative_delta_starts = int(by_start["proxy_delta"].lt(0).sum())
        proxy_total = float(frame["proxy_pnl"].sum())
        delta_total = float(frame["proxy_delta"].sum())
        loss_reduced = float(frame["loss_reduced"].sum())
        gain_sacrificed = float(frame["gain_sacrificed"].sum())
        rows.append(
            {
                "variant": variant,
                "label": str(frame["variant_label"].iloc[0]),
                "lot_count": int(len(frame)),
                "triggered_lot_count": int(frame["triggered"].sum()),
                "triggered_lot_share": float(frame["triggered"].mean()),
                "path_missing_lot_count": int(frame["path_missing"].sum()),
                "start_count": int(len(all_starts)),
                "positive_delta_start_count": positive_delta_starts,
                "negative_delta_start_count": negative_delta_starts,
                "positive_delta_start_rate": float(positive_delta_starts / len(all_starts)) if all_starts else np.nan,
                "original_pnl_sum": original_total,
                "proxy_pnl_sum": proxy_total,
                "proxy_delta_sum": delta_total,
                "loss_reduced_sum": loss_reduced,
                "gain_sacrificed_sum": gain_sacrificed,
                "loss_reduced_to_gain_sacrificed": loss_reduced / gain_sacrificed if gain_sacrificed > 0 else np.inf,
                "original_positive_pnl_sum": original_positive,
                "original_negative_abs_sum": original_negative_abs,
                "candidate_for_true_engine": bool(
                    delta_total > 0
                    and positive_delta_starts >= 8
                    and loss_reduced > gain_sacrificed * 1.5
                    and int(frame["triggered"].sum()) >= 30
                ),
            }
        )
    return pd.DataFrame(rows).sort_values(["candidate_for_true_engine", "proxy_delta_sum"], ascending=[False, False])


def build_variant_by_start(proxy: pd.DataFrame) -> pd.DataFrame:
    return (
        proxy.groupby(["variant", "variant_label", "requested_start_month"], as_index=False)
        .agg(
            lot_count=("lot_id", "size"),
            triggered_lot_count=("triggered", "sum"),
            original_pnl=("original_pnl", "sum"),
            proxy_pnl=("proxy_pnl", "sum"),
            proxy_delta=("proxy_delta", "sum"),
            loss_reduced=("loss_reduced", "sum"),
            gain_sacrificed=("gain_sacrificed", "sum"),
            path_missing_lot_count=("path_missing", "sum"),
        )
        .sort_values(["variant", "requested_start_month"])
    )


def build_classification_summary(lots: pd.DataFrame) -> pd.DataFrame:
    data = lots.copy()
    data["loss"] = data["realized_pnl"].lt(0)
    data["hold_bucket"] = pd.cut(
        data["holding_calendar_days"],
        bins=[-1, 0, 2, 5, 10, 20, 40, 10000],
        labels=["0d", "1-2d", "3-5d", "6-10d", "11-20d", "21-40d", "40d+"],
    )
    data["mfe_loss_bucket"] = pd.cut(
        data["mfe_r"],
        bins=[-999, -0.01, 0.0, 0.5, 1.0, 2.0, 5.0, 999],
        labels=["mfe<0", "0", "0-0.5R", "0.5-1R", "1-2R", "2-5R", "5R+"],
    )
    rows: list[dict[str, Any]] = []
    for name, frame in data.groupby("hold_bucket", observed=False):
        rows.append(
            {
                "group_type": "holding_bucket",
                "group": str(name),
                "lot_count": int(len(frame)),
                "loss_lot_count": int(frame["loss"].sum()),
                "pnl_sum": float(frame["realized_pnl"].sum()),
                "median_r": float(frame["r_multiple"].median()),
            }
        )
    for name, frame in data[data["loss"]].groupby("mfe_loss_bucket", observed=False):
        rows.append(
            {
                "group_type": "loser_mfe_bucket",
                "group": str(name),
                "lot_count": int(len(frame)),
                "loss_lot_count": int(len(frame)),
                "pnl_sum": float(frame["realized_pnl"].sum()),
                "median_r": float(frame["r_multiple"].median()),
            }
        )
    for name, frame in data.groupby("exit_reason", dropna=False):
        rows.append(
            {
                "group_type": "exit_reason",
                "group": str(name),
                "lot_count": int(len(frame)),
                "loss_lot_count": int(frame["loss"].sum()),
                "pnl_sum": float(frame["realized_pnl"].sum()),
                "median_r": float(frame["r_multiple"].median()),
            }
        )
    return pd.DataFrame(rows).sort_values(["group_type", "pnl_sum"])


def make_decision(summary: pd.DataFrame) -> dict[str, Any]:
    candidates = summary[summary["candidate_for_true_engine"].astype(bool)].copy()
    if candidates.empty:
        decision = "stage100_no_lot_proxy_candidate"
        best_variant = ""
        next_step = (
            "不进入 true engine；早期无进展/回吐 proxy 没有达到跨起点收益改善与右尾保留门槛。"
            "下一步优先做更底层的交易事件/退出原因分解，或回到独立收益腿数据补齐。"
        )
        continue_after = "有但需换层"
        continue_reason = "lot-level 代理未证明早期退出能稳健改善，继续扫 bar_count/MFE 阈值会过拟合。"
    else:
        best = candidates.sort_values(["proxy_delta_sum", "positive_delta_start_rate"], ascending=[False, False]).iloc[0]
        decision = "stage100_lot_proxy_candidate_for_true_engine"
        best_variant = str(best["variant"])
        next_step = f"只允许对 `{best_variant}` 做一次冻结 true-engine 验证；不得继续扫 bar_count、MFE、产品、方向或年份。"
        continue_after = "有"
        continue_reason = "lot-level 代理跨起点改善且损失捕获明显高于右尾牺牲，但仍需 true engine 检验资金路径。"
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": decision,
        "candidate_rule_count": int(len(candidates)),
        "best_variant": best_variant,
        "promote_to_true_engine": bool(not candidates.empty),
        "strategy_changed": False,
        "true_engine_run": False,
        "order_api_calls": 0,
        "ctp_connected": False,
        "next_step": next_step,
        "overfit_after": (
            "否。只测试预声明 4 个生命周期 proxy，不按品种、方向、月份、坏窗口或小数阈值救参；"
            "但若继续扫 bar_count/MFE 阈值就会过拟合。"
        ),
        "continue_after": continue_after,
        "continue_reason": continue_reason,
    }


def write_report(
    classification_summary: pd.DataFrame,
    variant_summary: pd.DataFrame,
    variant_by_start: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    research_rows = "\n".join(
        f"| {item['source']} | {item['url']} | {item['finding']} |" for item in EXTERNAL_RESEARCH
    )
    report = f"""# {STAGE} Early No-Progress Lot Proxy

## 外部调研与判断

| source | url | finding |
| --- | --- | --- |
{research_rows}

我的判断：Stage098/099 已显示坏窗口主要是 carryover，但固定 EOD 趋势衰减条件太窄；本阶段只做 lot-level 生命周期 proxy，筛查早期无进展或回吐是否值得进入 true engine。

## Classification Summary

{_md_table(classification_summary, 80)}

## Variant Summary

{_md_table(variant_summary)}

## Variant By Start

{_md_table(variant_by_start, 120)}

## 决策

```json
{json.dumps(_json_safe(decision), ensure_ascii=False, indent=2)}
```

## 统计口径

- 输入：Stage094 closed lots，不重新跑策略，不连接 CTP，不调用订单 API。
- 代理规则：固定 3/5 根日线无进展和 2R 后回水下，不扫产品、方向、年份或小数阈值。
- 代理价格：触发日 EOD close；仅重算该 lot 的 PnL，不重算账户资金、保证金释放、后续信号或复利路径。
- 因此本阶段最多只能决定是否进入一次冻结 true-engine 验证，不能作为上线结论。

## 过拟合反思

- 运行前：否。规则来自生命周期假设，数量少且预声明。
- 运行后：{decision['overfit_after']}

## 继续价值反思

- 运行前：有。早期亏损桶明显负，需要确认是否有可交易化 proxy。
- 运行后：{decision['continue_after']}。{decision['continue_reason']}

## 输出

- lot_proxy：`{LOT_PROXY_PATH}`
- variant_summary：`{VARIANT_SUMMARY_PATH}`
- variant_by_start：`{VARIANT_BY_START_PATH}`
- classification_summary：`{CLASSIFICATION_SUMMARY_PATH}`
- input_audit：`{INPUT_AUDIT_PATH}`
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def write_stage_record(
    classification_summary: pd.DataFrame,
    variant_summary: pd.DataFrame,
    variant_by_start: pd.DataFrame,
    decision: dict[str, Any],
) -> Path:
    now = datetime.now()
    path = STAGES_DIR / f"{now:%Y%m%d_%H%M}_stage100_early_no_progress_lot_proxy.md"
    text = f"""# Stage100 早期无进展/回吐 lot-level proxy

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{now:%Y-%m-%d %H:%M} CST
- 工作区/分支：`{ROOT}`
- 阶段性质：只读 lot-level 生命周期 proxy；不重新跑策略
- 是否重要突破：否
- 是否触发A/B：否，本阶段不提出可合入候选

## 外部调研与判断

- 参考资料：pysystemtrade position buffering、Rob Carver dynamic trend following、Hudson & Thames meta-labeling。
- 我的判断：早期退出最容易误杀趋势右尾，必须先用 lot-level proxy 看损失捕获与右尾牺牲；不能直接改 true engine。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage100_early_no_progress_lot_proxy.py`
- 修改脚本：无正式交易入口修改。
- 删除脚本：无。
- 新增参数：4 个固定生命周期 proxy：`3bars MFE<0.5R`、`5bars MFE<1R`、`5bars MFE<1R 且水下`、`2R 后回到水下`。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 输入：Stage094 closed lots。
- 账户规模：沿用 Stage094/Stage167 `150,000`，但本阶段不重算账户曲线。
- 成本口径：沿用 Stage094 closed-lot realized PnL；代理退出价使用触发日 EOD close，未加额外滑点压力。
- 引擎口径：不重新跑 true engine。
- 审计口径：lot-level PnL delta；不做产品/方向/日期黑名单。

## Classification Summary

{_md_table(classification_summary, 80)}

## Variant Summary

{_md_table(variant_summary)}

## Variant By Start

{_md_table(variant_by_start, 120)}

## 结论

- 本阶段结论：`{decision['decision']}`。
- 候选数：`{decision['candidate_rule_count']}`。
- 最优候选：`{decision['best_variant']}`。
- 是否进入 true engine：`{decision['promote_to_true_engine']}`。
- 下一步：{decision['next_step']}

## 回测记录字段

- 期末权益/总收益/最大回撤/Sharpe/总滑点/总交易次数/胜率：本阶段不是新策略曲线，不新增这些汇总。

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
    path.write_text(text, encoding="utf-8")
    return path


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    lots = load_lots()
    proxy = build_lot_proxy(lots)
    variant_summary = build_variant_summary(proxy)
    variant_by_start = build_variant_by_start(proxy)
    classification_summary = build_classification_summary(lots)
    input_audit = _input_audit([CLOSED_LOTS_PATH])
    decision = make_decision(variant_summary)

    proxy.to_csv(LOT_PROXY_PATH, index=False, encoding="utf-8-sig", compression="gzip")
    variant_summary.to_csv(VARIANT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    variant_by_start.to_csv(VARIANT_BY_START_PATH, index=False, encoding="utf-8-sig")
    classification_summary.to_csv(CLASSIFICATION_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    input_audit.to_csv(INPUT_AUDIT_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(classification_summary, variant_summary, variant_by_start, decision)
    stage_path = write_stage_record(classification_summary, variant_summary, variant_by_start, decision)
    print(json.dumps(_json_safe({"decision": decision, "stage_path": stage_path, "report_path": REPORT_PATH}), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
