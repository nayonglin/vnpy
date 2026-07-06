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
STAGE = "Stage103"
MODEL_TAG = "stage103_dd30_close_post_exit_continuation_audit_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage103_dd30_close_post_exit_continuation_audit"

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage103_dd30_close_post_exit_continuation_audit"
STAGES_DIR = LINE_DIR / "stages"

STAGE102_OUT = LINE_DIR / "outputs" / "stage102_exit_close_event_accounting_audit"
STAGE102_PREFIX = "rebuilt_c9_v2_stage102_exit_close_event_accounting_audit"
STAGE102_TAG = "stage102_exit_close_event_accounting_audit_v2_reviewed_all"
CLOSE_EVENTS_PATH = STAGE102_OUT / f"{STAGE102_PREFIX}_close_events_{STAGE102_TAG}.csv.gz"
STAGE102_DECISION_PATH = STAGE102_OUT / f"{STAGE102_PREFIX}_decision_{STAGE102_TAG}.json"

STAGE096_OUT = LINE_DIR / "outputs" / "stage096_position_concentration_predictive_audit"
STAGE096_PREFIX = "rebuilt_c9_v2_stage096_position_concentration_predictive_audit"
STAGE096_TAG = "stage096_position_concentration_predictive_audit_v1"
POSITIONS_PATH = STAGE096_OUT / f"{STAGE096_PREFIX}_positions_{STAGE096_TAG}.csv.gz"

STAGE094_OUT = LINE_DIR / "outputs" / "stage094_stage167_closed_lot_entry_state_audit"
STAGE094_PREFIX = "rebuilt_c9_v2_stage094_stage167_closed_lot_entry_state_audit"
STAGE094_TAG = "stage094_stage167_closed_lot_entry_state_audit_v1"
CLOSED_LOTS_PATH = STAGE094_OUT / f"{STAGE094_PREFIX}_closed_lots_{STAGE094_TAG}.csv.gz"

EVENT_PANEL_PATH = OUT / f"{OUTPUT_PREFIX}_event_panel_{MODEL_TAG}.csv.gz"
HORIZON_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_horizon_summary_{MODEL_TAG}.csv"
BY_START_PATH = OUT / f"{OUTPUT_PREFIX}_by_start_horizon_{MODEL_TAG}.csv"
BY_EXIT_REASON_PATH = OUT / f"{OUTPUT_PREFIX}_by_exit_reason_horizon_{MODEL_TAG}.csv"
TOP_EVENTS_PATH = OUT / f"{OUTPUT_PREFIX}_top_post_exit_events_{MODEL_TAG}.csv"
INPUT_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_input_audit_{MODEL_TAG}.csv"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

HORIZONS = [1, 2, 3, 5]
MAIN_HORIZON = 3
EPS = 1e-9

EXTERNAL_RESEARCH = [
    {
        "source": "pysystemtrade backtesting documentation",
        "url": "https://github.com/pst-group/pysystemtrade/blob/develop/docs/backtesting.md",
        "finding": "Exit and position accounting should be audited separately from the trading engine before changing rules.",
    },
    {
        "source": "Rob Carver, Dynamic trend following",
        "url": "https://qoppac.blogspot.com/2020/12/dynamic-trend-following.html",
        "finding": "Dynamic stop changes can reduce some losses but easily alter trend right-tail behavior.",
    },
    {
        "source": "Research Affiliates stop-loss paper",
        "url": "https://www.researchaffiliates.com/content/dam/ra/publications/pdf/1099-stop-the-losses.pdf",
        "finding": "Stop-loss overlays require a drawdown and return trade-off audit, not only a loss-event audit.",
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


def load_stage102_decision() -> dict[str, Any]:
    decision = json.loads(STAGE102_DECISION_PATH.read_text(encoding="utf-8"))
    if decision.get("decision") != "stage102_close_accounting_candidate_for_post_exit_audit":
        raise ValueError(f"Unexpected Stage102 decision: {decision.get('decision')}")
    if decision.get("best_candidate") != "dd30_close_events":
        raise ValueError(f"Unexpected Stage102 best candidate: {decision.get('best_candidate')}")
    return decision


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    close_events = pd.read_csv(CLOSE_EVENTS_PATH, encoding="utf-8-sig")
    lots = pd.read_csv(
        CLOSED_LOTS_PATH,
        usecols=["requested_start_month", "vt_symbol", "exit_date", "volume", "size", "realized_pnl"],
        encoding="utf-8-sig",
    )
    prices = pd.read_csv(
        POSITIONS_PATH,
        usecols=["requested_start_month", "date", "vt_symbol", "close_price"],
        encoding="utf-8-sig",
    )
    stage102_decision = load_stage102_decision()
    close_events["date"] = pd.to_datetime(close_events["date"], errors="coerce").dt.normalize()
    close_events["next_date"] = pd.to_datetime(close_events["next_date"], errors="coerce").dt.normalize()
    lots["exit_date"] = pd.to_datetime(lots["exit_date"], errors="coerce").dt.normalize()
    prices["date"] = pd.to_datetime(prices["date"], errors="coerce").dt.normalize()
    close_events["requested_start_month"] = close_events["requested_start_month"].astype(str)
    lots["requested_start_month"] = lots["requested_start_month"].astype(str)
    prices["requested_start_month"] = prices["requested_start_month"].astype(str)
    for column in ["end_pos", "close_day_net_pnl", "drawdown_depth_pct"]:
        close_events[column] = _numeric(close_events, column)
    for column in ["volume", "size", "realized_pnl"]:
        lots[column] = _numeric(lots, column)
    prices["close_price"] = _numeric(prices, "close_price")
    prices = prices.dropna(subset=["date", "close_price"]).copy()
    if prices.duplicated(["requested_start_month", "vt_symbol", "date"]).any():
        raise ValueError("Stage096 positions price table has duplicate start/symbol/date keys")
    return close_events, lots, prices, stage102_decision


def build_size_map(lots: pd.DataFrame) -> pd.DataFrame:
    group = (
        lots.groupby(["requested_start_month", "vt_symbol", "exit_date"], dropna=False)
        .agg(
            size_nunique=("size", "nunique"),
            size=("size", "first"),
            size_map_volume_sum=("volume", "sum"),
            size_map_lot_count=("volume", "size"),
            size_map_lot_pnl_sum=("realized_pnl", "sum"),
        )
        .reset_index()
        .rename(columns={"exit_date": "next_date"})
    )
    bad_size = int(group["size_nunique"].gt(1).sum())
    if bad_size:
        raise ValueError(f"Exit groups with multiple contract sizes: {bad_size}")
    return group.drop(columns=["size_nunique"])


def build_price_ladder(prices: pd.DataFrame) -> pd.DataFrame:
    ladder = prices.sort_values(["requested_start_month", "vt_symbol", "date"]).copy()
    ladder["seq"] = ladder.groupby(["requested_start_month", "vt_symbol"], sort=False).cumcount()
    return ladder


def build_event_panel(close_events: pd.DataFrame, lots: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    target = close_events[close_events["dd30_before_next_date"].astype(bool)].copy()
    target = target[target["end_pos"].abs().gt(EPS)].copy()
    size_map = build_size_map(lots)
    target = target.merge(
        size_map,
        on=["requested_start_month", "vt_symbol", "next_date"],
        how="left",
        validate="many_to_one",
    )
    missing_size = int(target["size"].isna().sum())
    if missing_size:
        raise ValueError(f"DD30 close events missing contract size: {missing_size}")
    volume_diff = target["end_pos"].abs().sub(target["size_map_volume_sum"]).abs()
    bad_volume = int(volume_diff.gt(EPS).sum())
    if bad_volume:
        raise ValueError(f"DD30 close events volume mismatch vs matched lots: {bad_volume}")
    ladder = build_price_ladder(prices)
    exit_prices = ladder.rename(
        columns={"date": "next_date", "close_price": "exit_close_price", "seq": "exit_seq"}
    )[["requested_start_month", "vt_symbol", "next_date", "exit_close_price", "exit_seq"]]
    target = target.merge(
        exit_prices,
        on=["requested_start_month", "vt_symbol", "next_date"],
        how="left",
        validate="many_to_one",
    )
    missing_exit_price = int(target["exit_close_price"].isna().sum())
    if missing_exit_price:
        raise ValueError(f"DD30 close events missing exit-day close price: {missing_exit_price}")
    frames: list[pd.DataFrame] = []
    for horizon in HORIZONS:
        view = target.copy()
        view["horizon_days"] = horizon
        view["future_seq"] = view["exit_seq"] + horizon
        future = ladder.rename(
            columns={"date": "future_date", "close_price": "future_close_price", "seq": "future_seq"}
        )[["requested_start_month", "vt_symbol", "future_seq", "future_date", "future_close_price"]]
        view = view.merge(
            future,
            on=["requested_start_month", "vt_symbol", "future_seq"],
            how="left",
            validate="many_to_one",
        )
        view["has_future_price"] = view["future_close_price"].notna()
        price_diff = view["future_close_price"].sub(view["exit_close_price"])
        view["post_exit_continuation_pnl"] = view["end_pos"] * view["size"] * price_diff
        view["post_exit_continuation_return_on_abs_exit_notional"] = (
            view["post_exit_continuation_pnl"].div(view["end_pos"].abs() * view["size"] * view["exit_close_price"])
        )
        view["would_help_actual_close"] = view["post_exit_continuation_pnl"].gt(0.0)
        frames.append(view)
    panel = pd.concat(frames, ignore_index=True, sort=False)
    return panel


def _summary_for(frame: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    grouped = frame.groupby(group_cols, dropna=False, sort=True)
    for key, group in grouped:
        key_tuple = key if isinstance(key, tuple) else (key,)
        valid = group[group["has_future_price"]].copy()
        pnl = valid["post_exit_continuation_pnl"]
        by_start = valid.groupby("requested_start_month")["post_exit_continuation_pnl"].sum()
        by_date = valid.groupby("next_date")["post_exit_continuation_pnl"].sum()
        row = {col: key_tuple[idx] for idx, col in enumerate(group_cols)}
        positive_sum = float(pnl[pnl.gt(0)].sum()) if not pnl.empty else 0.0
        negative_abs = float(-pnl[pnl.lt(0)].sum()) if not pnl.empty else 0.0
        top_positive = float(pnl.max()) if not pnl.empty else np.nan
        row.update(
            {
                "events": int(len(group)),
                "covered_events": int(len(valid)),
                "coverage_rate": _safe_div(float(len(valid)), float(len(group))),
                "start_count": int(valid["requested_start_month"].nunique()) if not valid.empty else 0,
                "date_count": int(valid["next_date"].nunique()) if not valid.empty else 0,
                "symbol_count": int(valid["vt_symbol"].nunique()) if not valid.empty else 0,
                "post_exit_continuation_pnl_sum": float(pnl.sum()) if not pnl.empty else 0.0,
                "post_exit_continuation_pnl_positive_sum": positive_sum,
                "post_exit_continuation_pnl_negative_abs_sum": negative_abs,
                "event_help_rate": float(valid["would_help_actual_close"].mean()) if not valid.empty else np.nan,
                "positive_start_count": int(by_start.gt(0).sum()) if len(by_start) else 0,
                "positive_start_rate": _safe_div(float(by_start.gt(0).sum()), float(len(by_start))),
                "positive_date_count": int(by_date.gt(0).sum()) if len(by_date) else 0,
                "positive_date_rate": _safe_div(float(by_date.gt(0).sum()), float(len(by_date))),
                "start_pnl_min": float(by_start.min()) if len(by_start) else np.nan,
                "start_pnl_median": float(by_start.median()) if len(by_start) else np.nan,
                "start_pnl_max": float(by_start.max()) if len(by_start) else np.nan,
                "top_event_positive_share": _safe_div(top_positive, positive_sum) if positive_sum > 0 else np.nan,
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def build_summaries(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    horizon_summary = _summary_for(panel, ["horizon_days"]).sort_values("horizon_days")
    by_start = _summary_for(panel, ["horizon_days", "requested_start_month"]).sort_values(
        ["horizon_days", "requested_start_month"]
    )
    by_exit_reason = _summary_for(panel, ["horizon_days", "primary_exit_reason"]).sort_values(
        ["horizon_days", "post_exit_continuation_pnl_sum"]
    )
    return horizon_summary, by_start, by_exit_reason


def build_top_events(panel: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "horizon_days",
        "requested_start_month",
        "date",
        "next_date",
        "future_date",
        "vt_symbol",
        "end_pos",
        "size",
        "drawdown_depth_pct",
        "primary_exit_reason",
        "close_day_net_pnl",
        "matched_lot_pnl_sum",
        "exit_close_price",
        "future_close_price",
        "post_exit_continuation_pnl",
        "would_help_actual_close",
    ]
    valid = panel[panel["has_future_price"]].copy()
    head_loss = valid.sort_values("post_exit_continuation_pnl").head(50)
    head_gain = valid.sort_values("post_exit_continuation_pnl", ascending=False).head(50)
    out = pd.concat([head_loss.assign(tail="most_negative"), head_gain.assign(tail="most_positive")], ignore_index=True)
    return out.loc[:, ["tail", *[col for col in cols if col in out.columns]]]


def make_decision(
    panel: pd.DataFrame,
    horizon_summary: pd.DataFrame,
    by_start: pd.DataFrame,
    stage102_decision: dict[str, Any],
) -> dict[str, Any]:
    main = horizon_summary[horizon_summary["horizon_days"].eq(MAIN_HORIZON)]
    main_row = main.iloc[0].to_dict() if not main.empty else {}
    all_horizons_covered = bool(horizon_summary["coverage_rate"].ge(0.95).all()) if not horizon_summary.empty else False
    all_horizons_nonnegative = bool(horizon_summary["post_exit_continuation_pnl_sum"].ge(0.0).all()) if not horizon_summary.empty else False
    main_positive = float(main_row.get("post_exit_continuation_pnl_sum", 0.0) or 0.0) > 500_000.0
    main_broad = bool(
        int(main_row.get("covered_events", 0) or 0) >= 300
        and int(main_row.get("start_count", 0) or 0) >= 6
        and int(main_row.get("symbol_count", 0) or 0) >= 40
        and float(main_row.get("positive_start_rate", 0.0) or 0.0) >= 0.65
        and float(main_row.get("positive_date_rate", 0.0) or 0.0) >= 0.55
        and (
            pd.isna(main_row.get("top_event_positive_share"))
            or float(main_row.get("top_event_positive_share", 1.0) or 1.0) <= 0.25
        )
    )
    candidate = bool(all_horizons_covered and all_horizons_nonnegative and main_positive and main_broad)
    if candidate:
        decision = "stage103_dd30_close_post_exit_positive_continuation_candidate_for_proxy_design"
        next_step = (
            "只允许冻结 `DD30 close + 3-day post-exit continuation` 形状做一次保守 proxy 设计；"
            "不得扫 DD 阈值、horizon、品种、方向、exit_reason 或日期。"
        )
        continue_after = "有"
        continue_reason = "DD30 close 后存在跨起点、跨日期的正向延续，可能说明部分水下平仓切断恢复。"
        overfit_after = "否但风险升高。horizon 已冻结为 1/2/3/5，候选必须所有 horizon 不为负且主 horizon 宽样本正贡献。"
    else:
        decision = "stage103_dd30_close_post_exit_no_delay_candidate"
        next_step = (
            "不进入退出延迟 proxy；如果继续，应转向分钟路径止损穿价/滑点审计，"
            "或重新回到底层持仓路径而不是延迟退出。"
        )
        continue_after = "有但需换问题"
        continue_reason = "DD30 close 后的固定 horizon 未来路径不足以证明延迟退出能稳健减少水下期。"
        overfit_after = "否。只读审计固定 horizon，不按最优 horizon 或局部品种方向选择。"
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": decision,
        "candidate_rule_count": int(candidate),
        "best_candidate": "dd30_close_events_post_exit_3d" if candidate else "",
        "stage102_decision": str(stage102_decision.get("decision", "")),
        "stage102_best_candidate": str(stage102_decision.get("best_candidate", "")),
        "horizons": HORIZONS,
        "main_horizon": MAIN_HORIZON,
        "dd30_close_events": int(panel[panel["horizon_days"].eq(MAIN_HORIZON)].shape[0]),
        "main_covered_events": int(main_row.get("covered_events", 0) or 0),
        "main_coverage_rate": float(main_row.get("coverage_rate", np.nan)),
        "main_post_exit_continuation_pnl_sum": float(main_row.get("post_exit_continuation_pnl_sum", 0.0) or 0.0),
        "main_event_help_rate": float(main_row.get("event_help_rate", np.nan)),
        "main_positive_start_rate": float(main_row.get("positive_start_rate", np.nan)),
        "main_positive_date_rate": float(main_row.get("positive_date_rate", np.nan)),
        "all_horizons_covered": all_horizons_covered,
        "all_horizons_nonnegative": all_horizons_nonnegative,
        "main_positive": main_positive,
        "main_broad": main_broad,
        "promote_to_proxy": False,
        "promote_to_true_engine": False,
        "strategy_changed": False,
        "true_engine_run": False,
        "order_api_calls": 0,
        "ctp_connected": False,
        "next_step": next_step,
        "overfit_after": overfit_after,
        "continue_after": continue_after,
        "continue_reason": continue_reason,
    }


def write_report(
    horizon_summary: pd.DataFrame,
    by_start: pd.DataFrame,
    by_exit_reason: pd.DataFrame,
    top_events: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    research_rows = "\n".join(
        f"| {item['source']} | {item['url']} | {item['finding']} |" for item in EXTERNAL_RESEARCH
    )
    report = f"""# {STAGE} DD30 Close Post-Exit Continuation Audit

## 外部调研与判断

| source | url | finding |
| --- | --- | --- |
{research_rows}

我的判断：本阶段只回答 DD30 下 close 后是否有稳定反弹/延续，不把未来价格当作可交易特征；只有固定 horizon 同向证据足够强，才允许进入下一次保守 proxy 设计。

## Horizon Summary

{_md_table(horizon_summary)}

## By Start

{_md_table(by_start, 120)}

## By Exit Reason

{_md_table(by_exit_reason, 120)}

## Top Events

{_md_table(top_events, 100)}

## 决策

```json
{json.dumps(_json_safe(decision), ensure_ascii=False, indent=2)}
```

## 统计口径

- 样本：Stage102 v2 的 `dd30_close_events`，即 close 前账户 drawdown depth `>=30%` 的同合约平仓事件。
- horizon：冻结为 `{HORIZONS}` 个后续交易日，主观察 horizon 为 `{MAIN_HORIZON}`，不按结果选择最优天数。
- 价格：使用 Stage096 positions 的同起点、同合约日线 close；若后续价格缺失则计入 coverage。
- PnL：`end_pos * contract_size * (future_close - exit_day_close)`，表示如果平仓日收盘后继续持有到 horizon 的增量机会成本；不含新增手续费/滑点，也不代表真实成交价。
- 候选闸门：所有 horizon coverage `>=95%` 且总 continuation 不为负；主 horizon 总额 `>500,000`、样本宽、正贡献起点/日期占比达标、单事件不主导。

## 过拟合反思

- 运行前：风险中等。Stage102 给出 DD30 close 聚合形状，本阶段必须冻结 horizon，不能扫最优。
- 运行后：{decision['overfit_after']}

## 继续价值反思

- 运行前：有。它直接回答水下平仓是否错过恢复，或是否避免进一步亏损。
- 运行后：{decision['continue_after']}。{decision['continue_reason']}

## 输出

- event_panel：`{EVENT_PANEL_PATH}`
- horizon_summary：`{HORIZON_SUMMARY_PATH}`
- by_start：`{BY_START_PATH}`
- by_exit_reason：`{BY_EXIT_REASON_PATH}`
- top_events：`{TOP_EVENTS_PATH}`
- input_audit：`{INPUT_AUDIT_PATH}`
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def write_stage_record(
    horizon_summary: pd.DataFrame,
    by_start: pd.DataFrame,
    by_exit_reason: pd.DataFrame,
    top_events: pd.DataFrame,
    decision: dict[str, Any],
) -> Path:
    now = datetime.now()
    path = STAGES_DIR / f"{now:%Y%m%d_%H%M}_stage103_dd30_close_post_exit_continuation_audit.md"
    text = f"""# Stage103 DD30 平仓后延续路径审计

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{now:%Y-%m-%d %H:%M} CST
- 工作区/分支：`{ROOT}`
- 阶段性质：只读 post-exit continuation 归因；不重新跑策略
- 是否重要突破：否
- 是否触发A/B：否，本阶段不产生可合入候选

## 外部调研与判断

- 参考资料：pysystemtrade backtesting、Rob Carver dynamic trend following、Research Affiliates stop-loss paper。
- 我的判断：退出/止损优化必须证明不是在切断趋势右尾。本阶段只看固定 horizon 的退出后路径，不扫最优 horizon。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage103_dd30_close_post_exit_continuation_audit.py`
- 修改脚本：无正式交易入口修改。
- 删除脚本：无。
- 新增参数：无正式交易参数；审计 horizon 固定为 `{HORIZONS}`，主 horizon `{MAIN_HORIZON}`。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 输入：Stage102 v2 close events、Stage096 positions price table、Stage094 closed lots size map。
- 数据区间：Stage096/102 的 `2020-01` 至 `2026-01` 逐半年起点，统一终点 `2026-06-30`。
- 账户规模：沿用 Stage167/Stage102 `150,000`；本阶段不重算账户曲线。
- 成本口径：post-exit continuation 只算退出后价格增量，不含新增手续费/滑点。
- 样本过滤：`dd30_before_next_date=True` 且 close event matched lot volume 与 `abs(end_pos)` 一致。
- 策略/归因口径：只读“如果退出日收盘后继续持有 N 个交易日”的机会成本；不代表真实成交价和策略回放。

## Horizon Summary

{_md_table(horizon_summary)}

## By Start

{_md_table(by_start, 120)}

## By Exit Reason

{_md_table(by_exit_reason, 120)}

## Top Events

{_md_table(top_events, 100)}

## 结论

- 本阶段结论：`{decision['decision']}`。
- 候选数：`{decision['candidate_rule_count']}`。
- 最优候选：`{decision['best_candidate']}`。
- main horizon：`{decision['main_horizon']}`。
- main covered events：`{decision['main_covered_events']}`。
- main coverage：`{decision['main_coverage_rate']}`。
- main post-exit continuation PnL：`{decision['main_post_exit_continuation_pnl_sum']:.4f}`。
- main event help rate：`{decision['main_event_help_rate']}`。
- main positive start rate：`{decision['main_positive_start_rate']}`。
- main positive date rate：`{decision['main_positive_date_rate']}`。
- 是否进入 proxy：`{decision['promote_to_proxy']}`。
- 是否进入 true engine：`{decision['promote_to_true_engine']}`。
- 下一步：{decision['next_step']}

## 回测记录字段

- 期末权益/总收益/最大回撤/Sharpe/总滑点/总交易次数/胜率：本阶段不是新策略曲线，不新增这些汇总。

## 过拟合反思

- 运行前判断：风险中等但可控。
- 运行后判断：{decision['overfit_after']}
- 原因：固定 horizon 和宽样本闸门，不按结果挑选日期/品种/方向。

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
    close_events, lots, prices, stage102_decision = load_inputs()
    input_audit = _input_audit([CLOSE_EVENTS_PATH, CLOSED_LOTS_PATH, POSITIONS_PATH, STAGE102_DECISION_PATH])
    input_audit.to_csv(INPUT_AUDIT_PATH, index=False, encoding="utf-8-sig")
    panel = build_event_panel(close_events, lots, prices)
    horizon_summary, by_start, by_exit_reason = build_summaries(panel)
    top_events = build_top_events(panel)
    decision = make_decision(panel, horizon_summary, by_start, stage102_decision)
    panel.to_csv(EVENT_PANEL_PATH, index=False, encoding="utf-8-sig")
    horizon_summary.to_csv(HORIZON_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    by_start.to_csv(BY_START_PATH, index=False, encoding="utf-8-sig")
    by_exit_reason.to_csv(BY_EXIT_REASON_PATH, index=False, encoding="utf-8-sig")
    top_events.to_csv(TOP_EVENTS_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(horizon_summary, by_start, by_exit_reason, top_events, decision)
    stage_path = write_stage_record(horizon_summary, by_start, by_exit_reason, top_events, decision)
    print(json.dumps(_json_safe({"decision": decision, "stage_path": stage_path}), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
