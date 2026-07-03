from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage043"
MODEL_TAG = "stage043_cash_yield_overlay_feasibility_v1"
OUTPUT_PREFIX = "rebuilt_c9_stage043_cash_yield_overlay_feasibility"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage043_cash_yield_overlay_feasibility"
STAGES_DIR = LINE_DIR / "stages"

STAGE042_OUTPUT_DIR = LINE_DIR / "outputs" / "stage042_expanded_daily_cold_start_probe"
STAGE042_PREFIX = "rebuilt_c9_stage042_expanded_daily_cold_start_probe"
STAGE042_TAG = "stage042_expanded_daily_cold_start_probe_v1"
STAGE042_CURVES_PATH = STAGE042_OUTPUT_DIR / f"{STAGE042_PREFIX}_curves_{STAGE042_TAG}.csv"

CAPITAL = 150000.0
MIN_PERIOD_CALENDAR_DAYS = 366
CASH_YIELD_RATES = [0.0, 0.03, 0.05, 0.08, 0.12, 0.20, 0.40]

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
REQUIRED_WINDOWS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_required_windows_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if np.isnan(number) or np.isinf(number) else number
    if not isinstance(value, (str, bytes)) and pd.isna(value):
        return None
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_空_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    return data.to_markdown(index=False)


def _date_key(value: Any) -> str:
    return pd.Timestamp(value).date().isoformat()


def _required_simple_annual_yield(
    start_equity: float,
    end_equity: float,
    elapsed_days: int,
    yield_base_capital: float = CAPITAL,
) -> float:
    if elapsed_days <= 0 or yield_base_capital <= 0:
        return np.nan
    deficit = max(0.0, float(start_equity) - float(end_equity))
    return deficit / (float(yield_base_capital) * float(elapsed_days) / 365.0)


def _normalise_curves(curves: pd.DataFrame) -> pd.DataFrame:
    data = curves.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    data["equity"] = pd.to_numeric(data["equity"], errors="coerce")
    data["requested_start"] = data["requested_start"].astype(str)
    data = data.dropna(subset=["requested_start", "date", "equity"])
    return data.sort_values(["requested_start", "date"]).drop_duplicates(["requested_start", "date"])


def _window_rows_with_required_yield(
    curves: pd.DataFrame,
    min_period_days: int = MIN_PERIOD_CALENDAR_DAYS,
    yield_base_capital: float = CAPITAL,
) -> pd.DataFrame:
    data = _normalise_curves(curves)
    rows: list[dict[str, Any]] = []
    for requested_start, group in data.groupby("requested_start", sort=True):
        ordered = group.sort_values("date").reset_index(drop=True)
        if ordered.empty:
            continue
        start_date = pd.Timestamp(ordered["date"].iloc[0]).normalize()
        start_equity = float(ordered["equity"].iloc[0])
        min_end = start_date + pd.Timedelta(days=min_period_days)
        ends = ordered[ordered["date"].ge(min_end)].copy()
        for _, row in ends.iterrows():
            end_date = pd.Timestamp(row["date"]).normalize()
            end_equity = float(row["equity"])
            elapsed_days = int((end_date - start_date).days)
            return_pct = (end_equity / start_equity - 1.0) * 100.0 if abs(start_equity) > 1e-12 else np.nan
            required_yield = _required_simple_annual_yield(
                start_equity=start_equity,
                end_equity=end_equity,
                elapsed_days=elapsed_days,
                yield_base_capital=yield_base_capital,
            )
            rows.append(
                {
                    "requested_start": str(requested_start),
                    "end_date": _date_key(end_date),
                    "elapsed_days": elapsed_days,
                    "start_equity": start_equity,
                    "end_equity": end_equity,
                    "return_pct": return_pct,
                    "required_simple_annual_yield": required_yield,
                    "required_simple_annual_yield_pct": required_yield * 100.0,
                }
            )
    return pd.DataFrame(rows)


def _audit_cash_yield_variants(
    curves: pd.DataFrame,
    yield_rates: list[float] | tuple[float, ...] = tuple(CASH_YIELD_RATES),
    min_period_days: int = MIN_PERIOD_CALENDAR_DAYS,
    yield_base_capital: float = CAPITAL,
    source_variant: str = "curve",
) -> pd.DataFrame:
    data = _normalise_curves(curves)
    rows: list[dict[str, Any]] = []
    for rate in yield_rates:
        window_count = 0
        negative_count = 0
        negative_probe_starts = 0
        min_return = np.inf
        worst_start = ""
        worst_end = ""
        to_final_returns: list[float] = []
        required_to_clear = 0.0
        for requested_start, group in data.groupby("requested_start", sort=True):
            ordered = group.sort_values("date").reset_index(drop=True)
            if ordered.empty:
                continue
            start_date = pd.Timestamp(ordered["date"].iloc[0]).normalize()
            start_equity = float(ordered["equity"].iloc[0])
            elapsed_all = (ordered["date"] - start_date).dt.days.astype(float)
            overlay_equity = ordered["equity"].astype(float) + yield_base_capital * float(rate) * elapsed_all / 365.0
            start_total = float(overlay_equity.iloc[0])
            final_return = (float(overlay_equity.iloc[-1]) / start_total - 1.0) * 100.0
            to_final_returns.append(final_return)
            min_end = start_date + pd.Timedelta(days=min_period_days)
            ends = ordered[ordered["date"].ge(min_end)].copy()
            if ends.empty or abs(start_total) <= 1e-12:
                continue
            end_elapsed = (ends["date"] - start_date).dt.days.astype(float)
            end_equity = ends["equity"].astype(float) + yield_base_capital * float(rate) * end_elapsed / 365.0
            returns = (end_equity / start_total - 1.0) * 100.0
            window_count += int(len(returns))
            neg = returns.lt(0.0)
            negative_count += int(neg.sum())
            negative_probe_starts += int(neg.any())
            if len(returns) > 0:
                idx = returns.idxmin()
                candidate_min = float(returns.loc[idx])
                if candidate_min < min_return:
                    min_return = candidate_min
                    worst_start = str(requested_start)
                    worst_end = _date_key(ends.loc[idx, "date"])
            for _, row in ends.iterrows():
                required_to_clear = max(
                    required_to_clear,
                    _required_simple_annual_yield(
                        start_equity=start_equity,
                        end_equity=float(row["equity"]),
                        elapsed_days=int((pd.Timestamp(row["date"]) - start_date).days),
                        yield_base_capital=yield_base_capital,
                    ),
                )
        rows.append(
            {
                "source_variant": source_variant,
                "cash_yield_rate": float(rate),
                "cash_yield_rate_pct": float(rate) * 100.0,
                "requested_start_count": int(data["requested_start"].nunique()),
                "negative_probe_start_count": int(negative_probe_starts),
                "window_count": int(window_count),
                "negative_count": int(negative_count),
                "negative_rate_pct": float(negative_count / window_count * 100.0) if window_count else np.nan,
                "min_return_pct": float(min_return) if np.isfinite(min_return) else np.nan,
                "worst_requested_start": worst_start,
                "worst_end_date": worst_end,
                "to_final_min_return_pct": float(min(to_final_returns)) if to_final_returns else np.nan,
                "required_yield_to_clear_pct": float(required_to_clear * 100.0),
            }
        )
    return pd.DataFrame(rows)


def _load_stage042_curves() -> pd.DataFrame:
    data = pd.read_csv(STAGE042_CURVES_PATH, encoding="utf-8-sig")
    frames: list[pd.DataFrame] = []
    for source_variant, column in [
        ("stage013_daily_cold_start_engine", "account_equity"),
        ("stage042_daily_cold_start_stage039_ai_top8_proxy", "stage039_account_equity"),
    ]:
        frame = data[["requested_start", "date", column, "probe_bucket"]].copy()
        frame.rename(columns={column: "equity"}, inplace=True)
        frame["source_variant"] = source_variant
        frames.append(frame)
    return pd.concat(frames, ignore_index=True, sort=False)


def _build_summary_and_windows() -> tuple[pd.DataFrame, pd.DataFrame]:
    curves = _load_stage042_curves()
    summaries: list[pd.DataFrame] = []
    required_windows: list[pd.DataFrame] = []
    for source_variant, group in curves.groupby("source_variant", sort=True):
        audit = _audit_cash_yield_variants(group, source_variant=source_variant)
        summaries.append(audit)
        windows = _window_rows_with_required_yield(group)
        windows["source_variant"] = source_variant
        bucket_map = group[["requested_start", "probe_bucket"]].drop_duplicates("requested_start")
        windows = windows.merge(bucket_map, on="requested_start", how="left")
        required_windows.append(windows)
    summary = pd.concat(summaries, ignore_index=True, sort=False)
    windows = pd.concat(required_windows, ignore_index=True, sort=False)
    windows = windows.sort_values("required_simple_annual_yield", ascending=False).reset_index(drop=True)
    return summary, windows


def _write_report(summary: pd.DataFrame, windows: pd.DataFrame, decision: dict[str, Any], stage_record_path: Path) -> None:
    worst_windows = windows.head(20)
    report = f"""# Stage043 - 现金收益账户外层可行性审计

- 记录时间：`{datetime.now().strftime('%Y-%m-%dT%H:%M')}`
- line_id：`{LINE_ID}`
- model_tag：`{MODEL_TAG}`
- 决策：`{decision['decision']}`

## 口径

- 只读复用 Stage042 的 `32` 个日级冷启动曲线。
- 不改变交易信号、不改变持仓路径、不连接 CTP、不调用订单 API。
- 现金收益 overlay 公式：`overlay_equity = strategy_equity + 150000 * annual_yield * elapsed_days / 365`。
- 这是账户外层可行性下界审计，不是策略 alpha。

## 现金收益敏感性

{_md_table(summary)}

## 所需收益率最高的窗口

{_md_table(worst_windows)}

## 判断

- Stage042 proxy 要把全部 `>365` 天窗口打到非负，所需简单年化现金收益率为 `{decision['stage042_required_yield_to_clear_pct']:.4f}%`。
- 固定 `8%` 年化现金收益仍有 `{decision['stage042_negative_count_at_8pct']}` 个负结束日。
- 固定 `20%` 年化现金收益仍有 `{decision['stage042_negative_count_at_20pct']}` 个负结束日。
- 因此普通现金管理/备用金利息不是足够强的左尾解法。

## 输出

- summary：`{SUMMARY_PATH}`
- required_windows：`{REQUIRED_WINDOWS_PATH}`
- decision：`{DECISION_PATH}`
- report：`{REPORT_PATH}`
- stage_record：`{stage_record_path}`

## 反思

- 运行前过拟合反思：否。本阶段不新增交易规则，只验证账户外层的数学下界。
- 运行后过拟合反思：否。结论不依赖选择某个阈值入场；若用不现实收益率或按窗口注入资金救曲线才是过拟合/口径漂移。
- 运行前继续价值反思：有。Stage042 后必须判断账户外层是否值得继续。
- 运行后继续价值反思：账户外层普通现金收益路线继续价值低；更有价值的是新外生信息源或真正能改变坏窗口持仓路径的因果特征。
"""
    REPORT_PATH.write_text(report, encoding="utf-8")
    stage_record_path.write_text(report, encoding="utf-8")


def main() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    summary, windows = _build_summary_and_windows()
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    windows.to_csv(REQUIRED_WINDOWS_PATH, index=False, encoding="utf-8-sig")
    stage042 = summary[summary["source_variant"].eq("stage042_daily_cold_start_stage039_ai_top8_proxy")]
    required_yield = float(stage042["required_yield_to_clear_pct"].max())
    at_8 = stage042[stage042["cash_yield_rate"].eq(0.08)].iloc[0]
    at_20 = stage042[stage042["cash_yield_rate"].eq(0.20)].iloc[0]
    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "decision": "stage043_cash_yield_overlay_not_enough_requires_new_exogenous_source",
        "stage042_required_yield_to_clear_pct": required_yield,
        "stage042_negative_count_at_8pct": int(at_8["negative_count"]),
        "stage042_negative_count_at_20pct": int(at_20["negative_count"]),
        "strategy_changed": False,
        "true_engine": False,
        "cash_overlay_only": True,
        "ctp_connected": False,
        "order_api_called": False,
    }
    stage_record_path = STAGES_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M')}_stage043_cash_yield_overlay_feasibility.md"
    decision["stage_record_path"] = str(stage_record_path)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(summary, windows, decision, stage_record_path)
    return decision


if __name__ == "__main__":
    print(json.dumps(_json_safe(main()), ensure_ascii=False, indent=2))
