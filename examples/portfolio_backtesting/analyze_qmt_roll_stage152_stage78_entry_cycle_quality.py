from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from main_contract_mapping import get_preferred_mapping_path
from qmt_roll_official_stage78_config import (
    OFFICIAL_STAGE78_CAPITAL,
    OFFICIAL_STAGE78_REFERENCE_METRICS,
    OFFICIAL_STAGE78_ROLE,
    OFFICIAL_STAGE78_VERSION,
)


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"
MODEL_TAG: str = "stage152_stage78_entry_cycle_quality_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage152_stage78_entry_cycle_quality"

TRADES_PATH: Path = OUTPUT_DIR / "qmt_roll_official_stage78_defensive_formal_trades_2020_2026_04.csv"
POSITION_CHANGES_PATH: Path = (
    OUTPUT_DIR / "qmt_roll_official_stage78_defensive_formal_position_changes_2020_2026_04.csv"
)
ENTRY_SNAPSHOTS_PATH: Path = (
    OUTPUT_DIR / "qmt_roll_official_stage78_defensive_formal_entry_candidate_snapshots_2020_2026_04.csv"
)

ENTRY_SAMPLES_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_samples_{MODEL_TAG}.csv"
GROUP_SUMMARY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_group_summary_{MODEL_TAG}.csv"
ROBUST_GROUPS_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_robust_groups_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

HORIZONS: tuple[int, ...] = (5, 10, 20, 40)
MIN_GROUP_SAMPLE_COUNT: int = 20


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or math.isinf(result):
        return default
    return result


def _to_markdown_table(df: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 20) -> str:
    if df.empty:
        return "_empty_"
    view = df[columns].copy() if columns else df.copy()
    view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda value: f"{value:.4f}")
    header = "| " + " | ".join(view.columns) + " |"
    separator = "| " + " | ".join(["---"] * len(view.columns)) + " |"
    rows = ["| " + " | ".join(map(str, row)) + " |" for row in view.to_numpy()]
    return "\n".join([header, separator, *rows])


def _product_from_contract(vt_symbol: str, exchange: str) -> str:
    match = re.match(r"^([A-Za-z]+)", str(vt_symbol))
    product = match.group(1) if match else str(vt_symbol)
    return f"{product}.{exchange}"


def _bucket_active_positions(value: Any) -> str:
    active = _safe_float(value, default=-1)
    if active < 0:
        return "unknown"
    if active <= 2:
        return "active_0_2"
    if active <= 5:
        return "active_3_5"
    if active <= 8:
        return "active_6_8"
    return "active_gt_8"


def _bucket_drawdown(value: Any) -> str:
    drawdown = _safe_float(value, default=np.nan)
    if pd.isna(drawdown):
        return "unknown"
    drawdown_pct = drawdown * 100.0 if abs(drawdown) <= 1.0 else drawdown
    if drawdown_pct <= 0.1:
        return "dd_0"
    if drawdown_pct <= 5:
        return "dd_0_5pct"
    if drawdown_pct <= 15:
        return "dd_5_15pct"
    if drawdown_pct <= 30:
        return "dd_15_30pct"
    return "dd_gt_30pct"


def _bucket_rsi(value: Any) -> str:
    rsi = _safe_float(value, default=np.nan)
    if pd.isna(rsi):
        return "unknown"
    if rsi <= 40:
        return "rsi_le_40"
    if rsi <= 60:
        return "rsi_40_60"
    if rsi <= 80:
        return "rsi_60_80"
    if rsi <= 95:
        return "rsi_80_95"
    return "rsi_gt_95"


def _bucket_ai_age(value: Any) -> str:
    age = _safe_float(value, default=np.nan)
    if pd.isna(age):
        return "unknown"
    if age <= 7:
        return "ai_age_0_7d"
    if age <= 20:
        return "ai_age_8_20d"
    if age <= 40:
        return "ai_age_21_40d"
    return "ai_age_gt_40d"


def _bucket_roll_phase(days_since_roll: Any, days_to_roll: Any) -> str:
    since = _safe_float(days_since_roll, default=np.nan)
    to_next = _safe_float(days_to_roll, default=np.nan)
    if pd.isna(since) or pd.isna(to_next):
        return "unknown"
    if since <= 3:
        return "roll_first_3d"
    if since <= 10:
        return "roll_first_4_10d"
    if to_next <= 3:
        return "roll_last_3d"
    if to_next <= 10:
        return "roll_last_4_10d"
    return "roll_middle"


def load_entry_trades() -> pd.DataFrame:
    trades = pd.read_csv(TRADES_PATH)
    trades["date"] = pd.to_datetime(trades["date"]).dt.normalize()
    entries = trades[trades["offset"].astype(str).str.lower().eq("open")].copy()
    entries["entry_id"] = np.arange(1, len(entries) + 1)
    entries["direction_key"] = entries["direction"].astype(str).str.lower()
    entries["product_vt_symbol"] = [
        _product_from_contract(vt_symbol, exchange)
        for vt_symbol, exchange in zip(entries["vt_symbol"], entries["exchange"], strict=False)
    ]
    entries.rename(columns={"date": "entry_date", "price": "entry_price"}, inplace=True)
    return entries


def load_opened_snapshots() -> pd.DataFrame:
    snapshots = pd.read_csv(ENTRY_SNAPSHOTS_PATH)
    snapshots["date"] = pd.to_datetime(snapshots["date"]).dt.normalize()
    snapshots = snapshots[pd.to_numeric(snapshots["is_opened"], errors="coerce").fillna(0).astype(int).eq(1)].copy()
    snapshots["direction_key"] = snapshots["direction"].astype(str).str.lower()
    snapshot_columns = [
        "date",
        "contract_vt_symbol",
        "direction_key",
        "candidate_index",
        "product_vt_symbol",
        "entry_context",
        "signal",
        "portfolio_drawdown_pct",
        "active_positions_before",
        "remaining_position_slots",
        "risk_mode",
        "risk_ratio",
        "risk_multiplier",
        "selection_pairwise_score",
        "selection_pairwise_rank",
        "ai_product_pool_signal_date",
        "ai_product_pool_score",
        "ai_product_pool_rank",
        "ai_product_pool_top_n",
        "rsi_value",
        "breakout",
        "loss_streak",
        "profit_recovery_streak",
    ]
    snapshots = snapshots[[column for column in snapshot_columns if column in snapshots.columns]].copy()
    snapshots.sort_values(["date", "contract_vt_symbol", "direction_key", "candidate_index"], inplace=True)
    return snapshots.drop_duplicates(subset=["date", "contract_vt_symbol", "direction_key"], keep="last")


def enrich_entries(entries: pd.DataFrame, snapshots: pd.DataFrame) -> pd.DataFrame:
    merged = entries.merge(
        snapshots,
        left_on=["entry_date", "vt_symbol", "direction_key"],
        right_on=["date", "contract_vt_symbol", "direction_key"],
        how="left",
        suffixes=("", "_snapshot"),
    )
    if "product_vt_symbol_snapshot" in merged.columns:
        merged["product_vt_symbol"] = merged["product_vt_symbol_snapshot"].fillna(merged["product_vt_symbol"])
    if "ai_product_pool_signal_date" in merged.columns:
        merged["ai_product_pool_signal_date"] = pd.to_datetime(
            merged["ai_product_pool_signal_date"], errors="coerce"
        ).dt.normalize()
        merged["ai_pool_age_days"] = (
            merged["entry_date"] - merged["ai_product_pool_signal_date"]
        ).dt.days
    else:
        merged["ai_pool_age_days"] = np.nan
    merged["entry_month"] = merged["entry_date"].dt.month
    merged["entry_quarter"] = "Q" + merged["entry_date"].dt.quarter.astype(str)
    merged["entry_year"] = merged["entry_date"].dt.year
    merged["entry_weekday"] = merged["entry_date"].dt.day_name()
    merged["active_positions_bucket"] = merged.get("active_positions_before", pd.Series(index=merged.index)).map(
        _bucket_active_positions
    )
    merged["portfolio_drawdown_bucket"] = merged.get("portfolio_drawdown_pct", pd.Series(index=merged.index)).map(
        _bucket_drawdown
    )
    merged["rsi_bucket"] = merged.get("rsi_value", pd.Series(index=merged.index)).map(_bucket_rsi)
    merged["ai_pool_age_bucket"] = merged["ai_pool_age_days"].map(_bucket_ai_age)
    merged["signal"] = merged.get("signal", pd.Series("unknown", index=merged.index)).fillna("unknown")
    merged["entry_context"] = merged.get("entry_context", pd.Series("unknown", index=merged.index)).fillna("unknown")
    return merged


def load_price_frames() -> dict[str, pd.DataFrame]:
    prices = pd.read_csv(POSITION_CHANGES_PATH, usecols=["date", "vt_symbol", "close_price"])
    prices["date"] = pd.to_datetime(prices["date"]).dt.normalize()
    prices["close_price"] = pd.to_numeric(prices["close_price"], errors="coerce")
    prices = prices[prices["close_price"].fillna(0.0) > 0].copy()
    frames: dict[str, pd.DataFrame] = {}
    for vt_symbol, group in prices.groupby("vt_symbol"):
        frames[str(vt_symbol)] = group.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    return frames


def add_forward_path_metrics(entries: pd.DataFrame, price_frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for row in entries.to_dict(orient="records"):
        result = dict(row)
        frame = price_frames.get(str(row["vt_symbol"]))
        entry_price = _safe_float(row.get("entry_price"), default=0.0)
        direction = str(row.get("direction_key", "")).lower()
        sign = 1.0 if direction == "long" else -1.0
        if frame is None or frame.empty or entry_price <= 0:
            for horizon in HORIZONS:
                result[f"complete_{horizon}d"] = 0
                result[f"return_{horizon}d_pct"] = np.nan
                result[f"mfe_{horizon}d_pct"] = np.nan
                result[f"mae_{horizon}d_pct"] = np.nan
            rows.append(result)
            continue

        dates = frame["date"].to_numpy(dtype="datetime64[ns]")
        closes = frame["close_price"].to_numpy(dtype=float)
        entry_date = np.datetime64(pd.Timestamp(row["entry_date"]).to_datetime64())
        start_idx = int(np.searchsorted(dates, entry_date, side="left"))
        if start_idx >= len(frame) or dates[start_idx] != entry_date:
            start_idx = int(np.searchsorted(dates, entry_date, side="right")) - 1
        for horizon in HORIZONS:
            target_idx = start_idx + horizon
            if start_idx < 0 or target_idx >= len(frame):
                result[f"complete_{horizon}d"] = 0
                result[f"return_{horizon}d_pct"] = np.nan
                result[f"mfe_{horizon}d_pct"] = np.nan
                result[f"mae_{horizon}d_pct"] = np.nan
                continue
            path = closes[start_idx + 1 : target_idx + 1]
            if len(path) < horizon:
                result[f"complete_{horizon}d"] = 0
                result[f"return_{horizon}d_pct"] = np.nan
                result[f"mfe_{horizon}d_pct"] = np.nan
                result[f"mae_{horizon}d_pct"] = np.nan
                continue
            directional_path = (path / entry_price - 1.0) * sign * 100.0
            result[f"complete_{horizon}d"] = 1
            result[f"return_{horizon}d_pct"] = float(directional_path[-1])
            result[f"mfe_{horizon}d_pct"] = float(np.nanmax(directional_path))
            result[f"mae_{horizon}d_pct"] = float(np.nanmin(directional_path))
        rows.append(result)
    return pd.DataFrame(rows)


def build_roll_phase_table() -> pd.DataFrame:
    mapping = pd.read_csv(get_preferred_mapping_path())
    mapping["date"] = pd.to_datetime(mapping["date"]).dt.normalize()
    mapping = mapping[mapping["main_contract_vt"].astype(str) != ""].copy()
    mapping.sort_values(["continuous_symbol_vt", "date"], inplace=True)
    frames: list[pd.DataFrame] = []
    for product, group in mapping.groupby("continuous_symbol_vt"):
        group = group.copy().reset_index(drop=True)
        segment_id = group["main_contract_vt"].ne(group["main_contract_vt"].shift()).cumsum()
        group["roll_segment_id"] = segment_id
        group["segment_index"] = group.groupby("roll_segment_id").cumcount()
        group["segment_length"] = group.groupby("roll_segment_id")["date"].transform("count")
        group["days_since_roll"] = group["segment_index"]
        group["days_to_roll"] = group["segment_length"] - group["segment_index"] - 1
        frames.append(group[["date", "continuous_symbol_vt", "main_contract_vt", "days_since_roll", "days_to_roll"]])
    if not frames:
        return pd.DataFrame(columns=["date", "product_vt_symbol", "main_contract_vt", "days_since_roll", "days_to_roll"])
    phase = pd.concat(frames, ignore_index=True)
    phase.rename(columns={"continuous_symbol_vt": "product_vt_symbol"}, inplace=True)
    return phase


def add_roll_phase(entries: pd.DataFrame) -> pd.DataFrame:
    phase = build_roll_phase_table()
    merged = entries.merge(
        phase,
        left_on=["entry_date", "product_vt_symbol", "vt_symbol"],
        right_on=["date", "product_vt_symbol", "main_contract_vt"],
        how="left",
        suffixes=("", "_roll"),
    )
    merged["roll_phase_bucket"] = [
        _bucket_roll_phase(since, to_next)
        for since, to_next in zip(merged["days_since_roll"], merged["days_to_roll"], strict=False)
    ]
    return merged


def summarize_group(entries: pd.DataFrame, group_type: str, column: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if column not in entries.columns:
        return pd.DataFrame()
    for group_value, group in entries.groupby(column, dropna=False):
        group_value_text = "missing" if pd.isna(group_value) else str(group_value)
        for horizon in HORIZONS:
            complete = group[pd.to_numeric(group[f"complete_{horizon}d"], errors="coerce").fillna(0).astype(int).eq(1)]
            returns = pd.to_numeric(complete[f"return_{horizon}d_pct"], errors="coerce").dropna()
            mfe = pd.to_numeric(complete[f"mfe_{horizon}d_pct"], errors="coerce").dropna()
            mae = pd.to_numeric(complete[f"mae_{horizon}d_pct"], errors="coerce").dropna()
            sample_count = int(len(returns))
            rows.append(
                {
                    "group_type": group_type,
                    "group_value": group_value_text,
                    "horizon": f"{horizon}d",
                    "horizon_days": horizon,
                    "sample_count": sample_count,
                    "positive_rate_pct": float((returns > 0).mean() * 100.0) if sample_count else 0.0,
                    "median_return_pct": float(returns.median()) if sample_count else 0.0,
                    "mean_return_pct": float(returns.mean()) if sample_count else 0.0,
                    "median_mfe_pct": float(mfe.median()) if not mfe.empty else 0.0,
                    "median_mae_pct": float(mae.median()) if not mae.empty else 0.0,
                    "complete_rate_pct": sample_count / max(1, len(group)) * 100.0,
                }
            )
    return pd.DataFrame(rows)


def build_group_summary(entries: pd.DataFrame) -> pd.DataFrame:
    group_specs = [
        ("calendar_month", "entry_month"),
        ("calendar_quarter", "entry_quarter"),
        ("entry_year", "entry_year"),
        ("weekday", "entry_weekday"),
        ("direction", "direction_key"),
        ("product", "product_vt_symbol"),
        ("entry_context", "entry_context"),
        ("signal", "signal"),
        ("portfolio_drawdown", "portfolio_drawdown_bucket"),
        ("active_positions", "active_positions_bucket"),
        ("rsi", "rsi_bucket"),
        ("ai_pool_age", "ai_pool_age_bucket"),
        ("roll_phase", "roll_phase_bucket"),
    ]
    frames = [summarize_group(entries, group_type, column) for group_type, column in group_specs]
    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def build_robust_groups(group_summary: pd.DataFrame) -> pd.DataFrame:
    if group_summary.empty:
        return pd.DataFrame()
    focus = group_summary[
        group_summary["sample_count"].astype(int).ge(MIN_GROUP_SAMPLE_COUNT)
        & group_summary["horizon"].isin(["20d", "40d"])
    ].copy()
    focus = focus[~focus["group_value"].astype(str).isin({"unknown", "missing"})].copy()
    if focus.empty:
        return pd.DataFrame()
    focus["robust_label"] = np.select(
        [
            focus["positive_rate_pct"].ge(55.0) & focus["median_return_pct"].gt(0.0),
            focus["positive_rate_pct"].le(45.0) & focus["median_return_pct"].lt(0.0),
        ],
        ["strong_entry_environment", "weak_entry_environment"],
        default="neutral",
    )
    focus["quality_score"] = focus["positive_rate_pct"] + focus["median_return_pct"] * 10.0
    focus.sort_values(["robust_label", "quality_score"], ascending=[True, False], inplace=True)
    return focus.reset_index(drop=True)


def build_summary(entries: pd.DataFrame, group_summary: pd.DataFrame, robust_groups: pd.DataFrame) -> dict[str, Any]:
    complete_counts = {
        f"{horizon}d": int(pd.to_numeric(entries[f"complete_{horizon}d"], errors="coerce").fillna(0).sum())
        for horizon in HORIZONS
    }
    strong = robust_groups[robust_groups["robust_label"].eq("strong_entry_environment")].copy()
    weak = robust_groups[robust_groups["robust_label"].eq("weak_entry_environment")].copy()
    return {
        "model_tag": MODEL_TAG,
        "official_version": OFFICIAL_STAGE78_VERSION,
        "official_role": OFFICIAL_STAGE78_ROLE,
        "capital": OFFICIAL_STAGE78_CAPITAL,
        "reference_metrics": OFFICIAL_STAGE78_REFERENCE_METRICS,
        "entry_count": int(len(entries)),
        "complete_counts": complete_counts,
        "group_summary_count": int(len(group_summary)),
        "robust_group_count": int(len(robust_groups)),
        "strong_group_count": int(len(strong)),
        "weak_group_count": int(len(weak)),
        "top_strong_groups": strong.sort_values("quality_score", ascending=False).head(10).to_dict(orient="records"),
        "top_weak_groups": weak.sort_values("quality_score", ascending=True).head(10).to_dict(orient="records"),
        "overfit_judgement": "否。仅做Stage78进场环境归因统计，不修改进场规则。",
        "continue_value_judgement": "有。该审计能决定影子盘应重点观察哪些进场环境，但不能直接转成过滤器。",
        "outputs": {
            "entry_samples": str(ENTRY_SAMPLES_PATH),
            "group_summary": str(GROUP_SUMMARY_PATH),
            "robust_groups": str(ROBUST_GROUPS_PATH),
            "summary_json": str(SUMMARY_JSON_PATH),
            "report": str(REPORT_PATH),
        },
    }


def build_report(summary: dict[str, Any], group_summary: pd.DataFrame, robust_groups: pd.DataFrame) -> str:
    reference = OFFICIAL_STAGE78_REFERENCE_METRICS["full_2020_2026"]
    strong = robust_groups[robust_groups["robust_label"].eq("strong_entry_environment")].copy()
    weak = robust_groups[robust_groups["robust_label"].eq("weak_entry_environment")].copy()
    month_20 = group_summary[
        group_summary["group_type"].eq("calendar_month")
        & group_summary["horizon"].eq("20d")
        & group_summary["sample_count"].ge(MIN_GROUP_SAMPLE_COUNT)
    ].sort_values("quality_score" if "quality_score" in group_summary.columns else "positive_rate_pct", ascending=False)
    lines = [
        "# Stage152 Stage78进场周期质量审计",
        "",
        "## 定位",
        "",
        "- 本阶段不是新策略版本，不改Stage78，不触发A/B技能。",
        "- 目标是统计进场环境质量，而不是找到历史最赚钱日期后反向限制交易。",
        "- 每笔开仓作为一个样本，观察进场后5/10/20/40个交易日的方向收益、MFE和MAE。",
        "",
        "## Stage78冻结基准",
        "",
        f"- 期末权益：`{reference['end_balance']:,.0f}`",
        f"- 总收益：`{reference['total_return_pct']:.4f}%`",
        f"- 最大回撤：`{reference['max_dd_percent']:.4f}%`",
        f"- Sharpe：`{reference['sharpe_ratio']:.4f}`",
        f"- 总滑点：`{reference['total_slippage']:,.0f}`",
        f"- 总交易次数：`{reference['total_trade_count']:,.0f}`",
        "",
        "## 样本覆盖",
        "",
        f"- 开仓样本数：`{summary['entry_count']}`",
        f"- 完整5/10/20/40日样本：`{summary['complete_counts']}`",
        "",
        "## 强进场环境",
        "",
        _to_markdown_table(
            strong.sort_values("quality_score", ascending=False),
            [
                "group_type",
                "group_value",
                "horizon",
                "sample_count",
                "positive_rate_pct",
                "median_return_pct",
                "median_mfe_pct",
                "median_mae_pct",
            ],
            max_rows=15,
        ),
        "",
        "## 弱进场环境",
        "",
        _to_markdown_table(
            weak.sort_values("quality_score", ascending=True),
            [
                "group_type",
                "group_value",
                "horizon",
                "sample_count",
                "positive_rate_pct",
                "median_return_pct",
                "median_mfe_pct",
                "median_mae_pct",
            ],
            max_rows=15,
        ),
        "",
        "## 20日历月观察",
        "",
        _to_markdown_table(
            month_20,
            [
                "group_value",
                "sample_count",
                "positive_rate_pct",
                "median_return_pct",
                "median_mfe_pct",
                "median_mae_pct",
            ],
            max_rows=12,
        ),
        "",
        "## 反思",
        "",
        f"- 是否过拟合：{summary['overfit_judgement']}",
        f"- 是否还有价值继续：{summary['continue_value_judgement']}",
        "",
        "## 使用边界",
        "",
        "- 强环境只能作为影子盘重点观察对象，不能直接加开仓过滤。",
        "- 弱环境不能直接禁入，必须先看是否跨年份、跨品种、跨方向稳定。",
        "- 真要接入正式版，必须另做预注册A/B和未来样本外验证。",
    ]
    return "\n".join(lines)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    entries = enrich_entries(load_entry_trades(), load_opened_snapshots())
    entries = add_forward_path_metrics(entries, load_price_frames())
    entries = add_roll_phase(entries)
    group_summary = build_group_summary(entries)
    robust_groups = build_robust_groups(group_summary)
    if not robust_groups.empty:
        score_map = robust_groups.set_index(["group_type", "group_value", "horizon"])["quality_score"]
        group_summary["quality_score"] = [
            score_map.get((row.group_type, row.group_value, row.horizon), np.nan)
            for row in group_summary.itertuples(index=False)
        ]

    summary = build_summary(entries, group_summary, robust_groups)

    entries.to_csv(ENTRY_SAMPLES_PATH, index=False, encoding="utf-8-sig")
    group_summary.to_csv(GROUP_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    robust_groups.to_csv(ROBUST_GROUPS_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_JSON_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(build_report(summary, group_summary, robust_groups), encoding="utf-8")

    print(json.dumps({k: summary[k] for k in ("entry_count", "complete_counts", "strong_group_count", "weak_group_count")}, ensure_ascii=False, indent=2))
    print(f"[stage152] report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
