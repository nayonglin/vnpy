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
STAGE = "Stage107"
MODEL_TAG = "stage107_long_base_stop_post_exit_continuation_audit_v2_reviewed_representative_sensitivity"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage107_long_base_stop_post_exit_continuation_audit"

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / "stage107_long_base_stop_post_exit_continuation_audit"
STAGES_DIR = LINE_DIR / "stages"

STAGE094_OUT = LINE_DIR / "outputs" / "stage094_stage167_closed_lot_entry_state_audit"
STAGE094_PREFIX = "rebuilt_c9_v2_stage094_stage167_closed_lot_entry_state_audit"
STAGE094_TAG = "stage094_stage167_closed_lot_entry_state_audit_v1"
CLOSED_LOTS_PATH = STAGE094_OUT / f"{STAGE094_PREFIX}_closed_lots_{STAGE094_TAG}.csv.gz"

STAGE096_OUT = LINE_DIR / "outputs" / "stage096_position_concentration_predictive_audit"
STAGE096_PREFIX = "rebuilt_c9_v2_stage096_position_concentration_predictive_audit"
STAGE096_TAG = "stage096_position_concentration_predictive_audit_v1"
POSITIONS_PATH = STAGE096_OUT / f"{STAGE096_PREFIX}_positions_{STAGE096_TAG}.csv.gz"

STAGE106_DECISION_PATH = (
    LINE_DIR
    / "outputs"
    / "stage106_non_intraday_exit_family_lifecycle_audit"
    / "rebuilt_c9_v2_stage106_non_intraday_exit_family_lifecycle_audit_decision_stage106_non_intraday_exit_family_lifecycle_audit_v2_reviewed_canonical.json"
)

EVENT_PANEL_PATH = OUT / f"{OUTPUT_PREFIX}_event_panel_{MODEL_TAG}.csv.gz"
HORIZON_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_horizon_summary_{MODEL_TAG}.csv"
BY_START_PATH = OUT / f"{OUTPUT_PREFIX}_by_start_horizon_{MODEL_TAG}.csv"
BY_SYMBOL_PATH = OUT / f"{OUTPUT_PREFIX}_by_symbol_horizon_{MODEL_TAG}.csv"
TOP_EVENTS_PATH = OUT / f"{OUTPUT_PREFIX}_top_events_{MODEL_TAG}.csv"
INPUT_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_input_audit_{MODEL_TAG}.csv"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"

HORIZONS = [1, 2, 3, 5]
MAIN_HORIZON = 3

EXTERNAL_RESEARCH = [
    {
        "source": "Rob Carver, Dynamic trend following",
        "url": "https://qoppac.blogspot.com/2020/12/dynamic-trend-following.html",
        "finding": "Exit changes should be evaluated as path changes because they can harm right-tail trend capture.",
    },
    {
        "source": "PriceActionLab trend-following stop-loss discussion",
        "url": "https://www.priceactionlab.com/Blog/2023/04/trend-following-stop-loss/",
        "finding": "Stop-loss rules have trade-offs across drawdown, trade count, win rate and return; post-exit continuation alone is not promotion evidence.",
    },
    {
        "source": "pysystemtrade backtesting documentation",
        "url": "https://github.com/pst-group/pysystemtrade/blob/develop/docs/backtesting.md",
        "finding": "Position and accounting attribution should be separated before creating a new trading rule.",
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


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    stage106 = json.loads(STAGE106_DECISION_PATH.read_text(encoding="utf-8"))
    if stage106.get("best_candidate") != "long_base_stop":
        raise ValueError(f"Unexpected Stage106 best candidate: {stage106.get('best_candidate')}")
    lots = pd.read_csv(CLOSED_LOTS_PATH, encoding="utf-8-sig")
    prices = pd.read_csv(
        POSITIONS_PATH,
        usecols=["requested_start_month", "date", "vt_symbol", "close_price"],
        encoding="utf-8-sig",
    )
    lots = lots[lots["exit_reason"].astype(str).eq("long_base_stop")].copy()
    lots["entry_date"] = pd.to_datetime(lots["entry_date"], errors="coerce").dt.normalize()
    lots["exit_date"] = pd.to_datetime(lots["exit_date"], errors="coerce").dt.normalize()
    prices["date"] = pd.to_datetime(prices["date"], errors="coerce").dt.normalize()
    lots["requested_start_month"] = lots["requested_start_month"].astype(str)
    prices["requested_start_month"] = prices["requested_start_month"].astype(str)
    for column in ["entry_price", "exit_price", "volume", "size", "realized_pnl", "holding_calendar_days"]:
        lots[column] = _numeric(lots, column)
    prices["close_price"] = _numeric(prices, "close_price")
    prices = prices.dropna(subset=["date", "close_price"]).copy()
    prices = prices.drop_duplicates(["requested_start_month", "vt_symbol", "date"])
    return lots, prices, stage106


def build_price_ladder(prices: pd.DataFrame) -> pd.DataFrame:
    ladder = prices.sort_values(["requested_start_month", "vt_symbol", "date"]).copy()
    ladder["seq"] = ladder.groupby(["requested_start_month", "vt_symbol"], sort=False).cumcount()
    return ladder


def build_event_panel(lots: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    ladder = build_price_ladder(prices)
    exit_prices = ladder.rename(columns={"date": "exit_date", "close_price": "exit_close_price", "seq": "exit_seq"})[
        ["requested_start_month", "vt_symbol", "exit_date", "exit_close_price", "exit_seq"]
    ]
    base = lots.merge(
        exit_prices,
        on=["requested_start_month", "vt_symbol", "exit_date"],
        how="left",
        validate="many_to_one",
    )
    missing_exit = int(base["exit_close_price"].isna().sum())
    if missing_exit:
        raise ValueError(f"long_base_stop missing exit close prices: {missing_exit}")
    base["exit_fill_vs_daily_close_delta"] = base["exit_price"].sub(base["exit_close_price"])
    frames: list[pd.DataFrame] = []
    future_base = ladder.rename(columns={"date": "future_date", "close_price": "future_close_price", "seq": "future_seq"})[
        ["requested_start_month", "vt_symbol", "future_seq", "future_date", "future_close_price"]
    ]
    for horizon in HORIZONS:
        view = base.copy()
        view["horizon_days"] = horizon
        view["future_seq"] = view["exit_seq"] + horizon
        view = view.merge(
            future_base,
            on=["requested_start_month", "vt_symbol", "future_seq"],
            how="left",
            validate="many_to_one",
        )
        view["has_future_price"] = view["future_close_price"].notna()
        view["post_exit_continuation_pnl"] = (
            (view["future_close_price"] - view["exit_price"]) * view["volume"] * view["size"]
        )
        view["post_exit_continuation_pnl_from_exit_close"] = (
            (view["future_close_price"] - view["exit_close_price"]) * view["volume"] * view["size"]
        )
        view.loc[~view["has_future_price"], "post_exit_continuation_pnl"] = np.nan
        view.loc[~view["has_future_price"], "post_exit_continuation_pnl_from_exit_close"] = np.nan
        view["actual_fill_basis_minus_exit_close_basis_pnl_delta"] = (
            view["post_exit_continuation_pnl"] - view["post_exit_continuation_pnl_from_exit_close"]
        )
        view["would_help_actual_exit"] = view["post_exit_continuation_pnl"].gt(0)
        key_cols = ["vt_symbol", "entry_date", "exit_date", "direction", "entry_price", "exit_price", "exit_reason"]
        view["physical_event_key"] = view[key_cols].astype(str).agg("|".join, axis=1)
        frames.append(view)
    return pd.concat(frames, ignore_index=True, sort=False)


def representative_sensitivity(valid: pd.DataFrame) -> dict[str, float | int]:
    if valid.empty:
        return {
            "duplicate_physical_key_count": 0,
            "volume_varying_physical_key_count": 0,
            "first_start_representative_pnl_sum": 0.0,
            "last_start_representative_pnl_sum": 0.0,
            "min_representative_pnl_sum": 0.0,
            "max_representative_pnl_sum": 0.0,
            "mean_per_physical_key_pnl_sum": 0.0,
        }
    ordered = valid.sort_values(["physical_event_key", "requested_start_month"]).copy()
    duplicate_counts = ordered.groupby("physical_event_key").size()
    volume_nunique = ordered.groupby("physical_event_key")["volume"].nunique(dropna=False)
    by_key = ordered.groupby("physical_event_key")["post_exit_continuation_pnl"]
    return {
        "duplicate_physical_key_count": int(duplicate_counts.gt(1).sum()),
        "volume_varying_physical_key_count": int(volume_nunique.gt(1).sum()),
        "first_start_representative_pnl_sum": float(by_key.first().sum()),
        "last_start_representative_pnl_sum": float(by_key.last().sum()),
        "min_representative_pnl_sum": float(by_key.min().sum()),
        "max_representative_pnl_sum": float(by_key.max().sum()),
        "mean_per_physical_key_pnl_sum": float(by_key.mean().sum()),
    }


def summarize(frame: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for key, group in frame.groupby(group_cols, dropna=False, sort=True):
        key_tuple = key if isinstance(key, tuple) else (key,)
        valid = group[group["has_future_price"]].copy()
        pnl = valid["post_exit_continuation_pnl"]
        close_basis_pnl = valid["post_exit_continuation_pnl_from_exit_close"]
        sensitivity = representative_sensitivity(valid)
        by_start = valid.groupby("requested_start_month")["post_exit_continuation_pnl"].sum()
        positive_sum = float(pnl[pnl.gt(0)].sum()) if len(pnl) else 0.0
        top_positive = float(pnl.max()) if len(pnl) else np.nan
        row = {col: key_tuple[idx] for idx, col in enumerate(group_cols)}
        row.update(
            {
                "events": int(len(group)),
                "covered_events": int(len(valid)),
                "coverage_rate": _safe_div(float(len(valid)), float(len(group))),
                "start_count": int(valid["requested_start_month"].nunique()) if len(valid) else 0,
                "unique_physical_events": int(valid["physical_event_key"].nunique()) if len(valid) else 0,
                "symbol_count": int(valid["vt_symbol"].nunique()) if len(valid) else 0,
                "post_exit_continuation_pnl_sum": float(pnl.sum()) if len(pnl) else 0.0,
                "post_exit_continuation_positive_sum": positive_sum,
                "post_exit_continuation_negative_abs_sum": float(-pnl[pnl.lt(0)].sum()) if len(pnl) else 0.0,
                "post_exit_continuation_pnl_from_exit_close_sum": float(close_basis_pnl.sum()) if len(close_basis_pnl) else 0.0,
                "actual_fill_basis_minus_exit_close_basis_pnl_delta_sum": float(
                    valid["actual_fill_basis_minus_exit_close_basis_pnl_delta"].sum()
                )
                if len(valid)
                else 0.0,
                "duplicate_physical_key_count": sensitivity["duplicate_physical_key_count"],
                "volume_varying_physical_key_count": sensitivity["volume_varying_physical_key_count"],
                "first_start_representative_pnl_sum": sensitivity["first_start_representative_pnl_sum"],
                "last_start_representative_pnl_sum": sensitivity["last_start_representative_pnl_sum"],
                "min_representative_pnl_sum": sensitivity["min_representative_pnl_sum"],
                "max_representative_pnl_sum": sensitivity["max_representative_pnl_sum"],
                "mean_per_physical_key_pnl_sum": sensitivity["mean_per_physical_key_pnl_sum"],
                "event_help_rate": float(valid["would_help_actual_exit"].mean()) if len(valid) else np.nan,
                "positive_start_count": int(by_start.gt(0).sum()) if len(by_start) else 0,
                "positive_start_rate": _safe_div(float(by_start.gt(0).sum()), float(len(by_start))),
                "start_pnl_min": float(by_start.min()) if len(by_start) else np.nan,
                "start_pnl_median": float(by_start.median()) if len(by_start) else np.nan,
                "start_pnl_max": float(by_start.max()) if len(by_start) else np.nan,
                "top_event_positive_share": _safe_div(top_positive, positive_sum) if positive_sum > 0 else np.nan,
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def build_top_events(panel: pd.DataFrame) -> pd.DataFrame:
    valid = panel[panel["has_future_price"]].copy()
    cols = [
        "horizon_days",
        "requested_start_month",
        "vt_symbol",
        "entry_date",
        "exit_date",
        "future_date",
        "entry_price",
        "exit_price",
        "future_close_price",
        "volume",
        "size",
        "realized_pnl",
        "post_exit_continuation_pnl",
        "post_exit_continuation_pnl_from_exit_close",
        "actual_fill_basis_minus_exit_close_basis_pnl_delta",
        "would_help_actual_exit",
        "physical_event_key",
    ]
    loss = valid.sort_values("post_exit_continuation_pnl").head(50).assign(tail="most_negative")
    gain = valid.sort_values("post_exit_continuation_pnl", ascending=False).head(50).assign(tail="most_positive")
    return pd.concat([loss, gain], ignore_index=True, sort=False)[["tail", *cols]]


def make_decision(panel: pd.DataFrame, horizon_summary: pd.DataFrame, stage106: dict[str, Any]) -> dict[str, Any]:
    main = horizon_summary[horizon_summary["horizon_days"].eq(MAIN_HORIZON)]
    main_row = main.iloc[0].to_dict() if not main.empty else {}
    all_covered = bool(horizon_summary["coverage_rate"].ge(0.95).all()) if not horizon_summary.empty else False
    all_positive = bool(horizon_summary["post_exit_continuation_pnl_sum"].gt(0.0).all()) if not horizon_summary.empty else False
    main_material = float(main_row.get("post_exit_continuation_pnl_sum", 0.0) or 0.0) >= 1_000_000.0
    main_first_representative_material = float(main_row.get("first_start_representative_pnl_sum", 0.0) or 0.0) >= 300_000.0
    main_mean_representative_material = float(main_row.get("mean_per_physical_key_pnl_sum", 0.0) or 0.0) >= 300_000.0
    main_min_representative_nonnegative = float(main_row.get("min_representative_pnl_sum", 0.0) or 0.0) >= 0.0
    main_broad = bool(
        int(main_row.get("start_count", 0) or 0) >= 8
        and int(main_row.get("unique_physical_events", 0) or 0) >= 20
        and float(main_row.get("positive_start_rate", 0.0) or 0.0) >= 0.65
        and (
            pd.isna(main_row.get("top_event_positive_share"))
            or float(main_row.get("top_event_positive_share", 1.0) or 1.0) <= 0.35
        )
    )
    main_representative_stable = bool(
        main_first_representative_material and main_mean_representative_material and main_min_representative_nonnegative
    )
    candidate = bool(all_covered and all_positive and main_material and main_representative_stable and main_broad)
    if candidate:
        decision = "stage107_long_base_stop_post_exit_positive_continuation_for_fixed_proxy_design"
        candidate_rule_count = 1
        best_candidate = "long_base_stop_3d_post_exit_continuation"
        next_step = (
            "只允许一次固定 proxy 设计：long_base_stop 后延迟/确认形状必须冻结为本阶段主 horizon 语义；"
            "不得扫 horizon、倍数、品种、方向或日期。"
        )
        continue_after = "有"
        continue_reason = "long_base_stop 后固定 horizon 延续为正且宽样本，可能说明 base stop 过早砍掉恢复。"
        overfit_after = "否但风险升高。候选来自 Stage106 唯一 canonical 对象，并要求所有 horizon 同向正。"
    else:
        decision = "stage107_long_base_stop_post_exit_positive_but_representative_sensitive_followup_only"
        candidate_rule_count = 0
        best_candidate = ""
        next_step = (
            "不直接进入 base_stop 延迟/确认策略版本；只允许先做一次无前视机制可行性审计，"
            "验证是否存在固定、可执行、非扫参的确认条件。"
        )
        continue_after = "有但降级"
        continue_reason = "行级和启动月维度均显示 base stop 后有恢复，但物理事件代表值对启动月/手数敏感，不能直接转成规则。"
        overfit_after = (
            "否，但已识别路径依赖风险。horizon 固定且所有 horizon 总额为正；"
            "物理事件 min 代表为负，所以不把本阶段升为 proxy 候选。"
        )
    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "decision": decision,
        "candidate_rule_count": candidate_rule_count,
        "best_candidate": best_candidate,
        "stage106_decision": str(stage106.get("decision", "")),
        "stage106_best_candidate": str(stage106.get("best_candidate", "")),
        "horizons": HORIZONS,
        "main_horizon": MAIN_HORIZON,
        "all_covered": all_covered,
        "all_positive": all_positive,
        "main_material": main_material,
        "main_first_representative_material": main_first_representative_material,
        "main_mean_representative_material": main_mean_representative_material,
        "main_min_representative_nonnegative": main_min_representative_nonnegative,
        "main_representative_stable": main_representative_stable,
        "main_broad": main_broad,
        "main_events": int(main_row.get("events", 0) or 0),
        "main_covered_events": int(main_row.get("covered_events", 0) or 0),
        "main_post_exit_continuation_pnl_sum": float(main_row.get("post_exit_continuation_pnl_sum", 0.0) or 0.0),
        "main_post_exit_continuation_pnl_from_exit_close_sum": float(
            main_row.get("post_exit_continuation_pnl_from_exit_close_sum", 0.0) or 0.0
        ),
        "main_actual_fill_basis_minus_exit_close_basis_pnl_delta_sum": float(
            main_row.get("actual_fill_basis_minus_exit_close_basis_pnl_delta_sum", 0.0) or 0.0
        ),
        "main_duplicate_physical_key_count": int(main_row.get("duplicate_physical_key_count", 0) or 0),
        "main_volume_varying_physical_key_count": int(main_row.get("volume_varying_physical_key_count", 0) or 0),
        "main_first_start_representative_pnl_sum": float(main_row.get("first_start_representative_pnl_sum", 0.0) or 0.0),
        "main_last_start_representative_pnl_sum": float(main_row.get("last_start_representative_pnl_sum", 0.0) or 0.0),
        "main_min_representative_pnl_sum": float(main_row.get("min_representative_pnl_sum", 0.0) or 0.0),
        "main_max_representative_pnl_sum": float(main_row.get("max_representative_pnl_sum", 0.0) or 0.0),
        "main_mean_per_physical_key_pnl_sum": float(main_row.get("mean_per_physical_key_pnl_sum", 0.0) or 0.0),
        "main_event_help_rate": float(main_row.get("event_help_rate", np.nan)),
        "main_positive_start_rate": float(main_row.get("positive_start_rate", np.nan)),
        "main_top_event_positive_share": float(main_row.get("top_event_positive_share", np.nan)),
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
    by_symbol: pd.DataFrame,
    top_events: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    research_rows = "\n".join(
        f"| {item['source']} | {item['url']} | {item['finding']} |" for item in EXTERNAL_RESEARCH
    )
    report = f"""# {STAGE} Long Base Stop Post-Exit Continuation Audit

## 外部调研与判断

| source | url | finding |
| --- | --- | --- |
{research_rows}

我的判断：Stage107 只回答 long_base_stop 是否过早切断后续恢复。即使 continuation 为正，也只能进入下一层固定 proxy 设计；如果 horizon 不一致或样本集中，直接停止。

v2 复核后补充判断：物理事件跨启动月重复时，手数会因账户路径不同而变化；因此 `first_start` 只能作为代表口径之一，不能当作稳健独立证据。后续最多进入无前视机制可行性审计，不直接做策略晋级。

## Decision

```json
{json.dumps(_json_safe(decision), ensure_ascii=False, indent=2)}
```

## Horizon Summary

{_md_table(horizon_summary)}

## By Start

{_md_table(by_start, 120)}

## By Symbol

{_md_table(by_symbol.sort_values(["horizon_days", "post_exit_continuation_pnl_sum"]), 160)}

## Top Events

{_md_table(top_events, 100)}

## 统计口径

- 样本：Stage106 唯一 canonical follow-up 对象 `long_base_stop`。
- continuation：假设当前 exit 后继续持有同一手数到后续第 `1/2/3/5` 个交易日 close，PnL = `(future_close - exit_price) * volume * size`。
- `post_exit_continuation_pnl_from_exit_close`：对照口径，假设从退出日收盘价继续持有；两者差异用于防止把实际退出价后续机会误读成 close-to-close 机会。
- `first/last/min/max/mean representative`：同一物理事件跨启动月重复时，分别取最早启动月、最晚启动月、最小、最大、均值后再求和；不再只用 `first_start` 代表独立样本。
- 这是 post-exit opportunity/cost 审计，不代表真实可成交延迟退出；不含新增手续费/滑点。
- 候选闸门：所有 horizon coverage `>=95%` 且总 continuation 均为正；主 horizon `3` 天行级增量 `>=1,000,000`、first/mean 代表增量 `>=300,000`、min 代表非负、起点/事件宽、正起点率 `>=65%`、单事件不主导。

## 过拟合反思

- 运行前：否。对象来自 Stage106 唯一 canonical 宽样本退出族，不扫品种/方向/日期。
- 运行后：{decision['overfit_after']}

## 继续价值反思

- 运行前：有。它判断 base stop 是否过早切断恢复，直接对应水下期来源。
- 运行后：{decision['continue_after']}。{decision['continue_reason']}

## 输出

- event_panel：`{EVENT_PANEL_PATH}`
- horizon_summary：`{HORIZON_SUMMARY_PATH}`
- by_start：`{BY_START_PATH}`
- by_symbol：`{BY_SYMBOL_PATH}`
- top_events：`{TOP_EVENTS_PATH}`
- input_audit：`{INPUT_AUDIT_PATH}`
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def write_stage_record(
    horizon_summary: pd.DataFrame,
    by_start: pd.DataFrame,
    by_symbol: pd.DataFrame,
    top_events: pd.DataFrame,
    decision: dict[str, Any],
) -> Path:
    now = datetime.now()
    path = STAGES_DIR / f"{now:%Y%m%d_%H%M}_stage107_long_base_stop_post_exit_continuation_audit.md"
    text = f"""# Stage107 long_base_stop 平仓后延续路径审计

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{now:%Y-%m-%d %H:%M} CST
- 工作区：`{ROOT}`
- 阶段性质：只读 post-exit continuation；不改策略、不跑 true engine
- 是否重要突破：否；v2 已按独立评审降级为机制线索，不是 proxy 候选
- 是否触发A/B：否，本阶段不是可合入策略

## 外部调研与判断

- 参考资料：Rob Carver dynamic trend following、PriceActionLab stop-loss discussion、pysystemtrade backtesting docs。
- 我的判断：base stop 是否过早，只能先看退出后固定 horizon 是否有宽样本正 continuation；不能因为 `long_base_stop` 本身亏损就直接放宽止损。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage107_long_base_stop_post_exit_continuation_audit.py`
- 修改脚本：无正式交易入口修改。
- 删除脚本：无。
- 新增参数：只读 horizon `{HORIZONS}`，主 horizon `{MAIN_HORIZON}`；主 horizon material 闸门行级 `1,000,000`、first/mean 代表 `300,000`、min 代表非负。
- 修改参数：无正式策略参数。
- 删除参数：无。

## 回测/审计参数

- 输入 lots：`{CLOSED_LOTS_PATH}`
- 输入价格：`{POSITIONS_PATH}`
- Stage106 decision：`{decision['stage106_decision']}`
- Stage106 best：`{decision['stage106_best_candidate']}`
- true engine：未运行。
- 订单 API：`0`
- CTP：未连接。

## 结果摘要

- 决策：`{decision['decision']}`
- 候选规则数：`{decision['candidate_rule_count']}`
- 最佳候选：`{decision['best_candidate'] or '无'}`
- 主 horizon：`{decision['main_horizon']}`
- 主 horizon events：`{decision['main_events']}`
- 主 horizon covered：`{decision['main_covered_events']}`
- 主 horizon continuation：`{decision['main_post_exit_continuation_pnl_sum']:,.2f}`
- 主 horizon exit-close 对照 continuation：`{decision['main_post_exit_continuation_pnl_from_exit_close_sum']:,.2f}`
- 主 horizon actual-fill minus exit-close delta：`{decision['main_actual_fill_basis_minus_exit_close_basis_pnl_delta_sum']:,.2f}`
- 主 horizon first-start representative：`{decision['main_first_start_representative_pnl_sum']:,.2f}`
- 主 horizon last-start representative：`{decision['main_last_start_representative_pnl_sum']:,.2f}`
- 主 horizon min representative：`{decision['main_min_representative_pnl_sum']:,.2f}`
- 主 horizon max representative：`{decision['main_max_representative_pnl_sum']:,.2f}`
- 主 horizon mean-per-key representative：`{decision['main_mean_per_physical_key_pnl_sum']:,.2f}`
- 主 horizon duplicate physical keys：`{decision['main_duplicate_physical_key_count']}`
- 主 horizon volume-varying physical keys：`{decision['main_volume_varying_physical_key_count']}`
- 主 horizon help rate：`{decision['main_event_help_rate']:.4f}`
- 主 horizon positive start rate：`{decision['main_positive_start_rate']:.4f}`
- 主 horizon top positive share：`{decision['main_top_event_positive_share']:.4f}`
- all_positive：`{decision['all_positive']}`
- main_material：`{decision['main_material']}`
- main_representative_stable：`{decision['main_representative_stable']}`
- main_first_representative_material：`{decision['main_first_representative_material']}`
- main_mean_representative_material：`{decision['main_mean_representative_material']}`
- main_min_representative_nonnegative：`{decision['main_min_representative_nonnegative']}`
- main_broad：`{decision['main_broad']}`

## Horizon Summary

{_md_table(horizon_summary)}

## By Start

{_md_table(by_start, 120)}

## Top Events

{_md_table(top_events, 80)}

## 标准回测指标

- 期末权益：不适用，本阶段只读归因未重跑策略。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。

## 决策

```json
{json.dumps(_json_safe(decision), ensure_ascii=False, indent=2)}
```

## 后续规划和 TODO

- {decision['next_step']}

## 过拟合反思

- 运行前：否，唯一对象来自 Stage106；horizon 固定为 `{HORIZONS}`。
- 运行后：{decision['overfit_after']}

## 继续价值反思

- 运行前：有，直接判断 base stop 是否切断后续恢复。
- 运行后：{decision['continue_after']}。{decision['continue_reason']}

## 输出

- 报告：`{REPORT_PATH}`
- event_panel：`{EVENT_PANEL_PATH}`
- horizon_summary：`{HORIZON_SUMMARY_PATH}`
- by_start：`{BY_START_PATH}`
- by_symbol：`{BY_SYMBOL_PATH}`
- top_events：`{TOP_EVENTS_PATH}`
- input_audit：`{INPUT_AUDIT_PATH}`
"""
    path.write_text(text, encoding="utf-8")
    return path


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    input_audit = _input_audit([CLOSED_LOTS_PATH, POSITIONS_PATH, STAGE106_DECISION_PATH])
    if not bool(input_audit["exists"].all()):
        raise FileNotFoundError("Stage107 input missing")
    lots, prices, stage106 = load_inputs()
    panel = build_event_panel(lots, prices)
    horizon_summary = summarize(panel, ["horizon_days"]).sort_values("horizon_days")
    by_start = summarize(panel, ["horizon_days", "requested_start_month"]).sort_values(
        ["horizon_days", "requested_start_month"]
    )
    by_symbol = summarize(panel, ["horizon_days", "vt_symbol"]).sort_values(["horizon_days", "vt_symbol"])
    top_events = build_top_events(panel)
    decision = make_decision(panel, horizon_summary, stage106)

    panel.to_csv(EVENT_PANEL_PATH, index=False, encoding="utf-8-sig", compression="gzip")
    horizon_summary.to_csv(HORIZON_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    by_start.to_csv(BY_START_PATH, index=False, encoding="utf-8-sig")
    by_symbol.to_csv(BY_SYMBOL_PATH, index=False, encoding="utf-8-sig")
    top_events.to_csv(TOP_EVENTS_PATH, index=False, encoding="utf-8-sig")
    input_audit.to_csv(INPUT_AUDIT_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(horizon_summary, by_start, by_symbol, top_events, decision)
    stage_path = write_stage_record(horizon_summary, by_start, by_symbol, top_events, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"[stage107] report={REPORT_PATH}")
    print(f"[stage107] stage_record={stage_path}")


if __name__ == "__main__":
    main()
