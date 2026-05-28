from __future__ import annotations

from collections import Counter
from datetime import datetime
import json
import math
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd
from vnpy.trader.object import BarData, TradeData
from vnpy_portfoliostrategy.backtesting import Status

PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
sys.path.insert(0, str(PROJECT_DIR.resolve()))

import run_qmt_roll_backtest as rb  # noqa: E402
from analyze_qmt_roll_stage324_true_combo_capital_margin import _c3_overrides  # noqa: E402
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import (  # noqa: E402
    BASE_RISK_RATIO,
)


MODEL_TAG = "stage457_volume_oi_materiality_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage457_volume_oi_materiality_audit"
LINE_ID = "futures_trend_drawdown30_preserve_return"

C3_CAPITAL = 500_000.0
STAGE079_CASH = 115_000.0
ACCOUNT_CAPITAL = C3_CAPITAL + STAGE079_CASH

VARIANTS: tuple[str, ...] = ("baseline", "volume_zero", "open_interest_zero", "volume_open_interest_zero")

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
RISK_MODE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_risk_mode_{MODEL_TAG}.csv"
TRADE_DIFF_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_diff_{MODEL_TAG}.csv"
DAILY_DIFF_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_diff_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _json_safe(value: Any) -> Any:
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
    if isinstance(value, (pd.Timestamp, datetime)):
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
            view[column] = view[column].map(lambda value: f"{value:.4f}" if pd.notna(value) else "")
    return view.to_markdown(index=False)


def _clone_bar(bar: BarData, field_mode: str) -> BarData:
    volume = float(bar.volume)
    open_interest = float(bar.open_interest)
    if field_mode in {"volume_zero", "volume_open_interest_zero"}:
        volume = 0.0
    if field_mode in {"open_interest_zero", "volume_open_interest_zero"}:
        open_interest = 0.0
    return BarData(
        symbol=bar.symbol,
        exchange=bar.exchange,
        datetime=bar.datetime,
        interval=bar.interval,
        volume=volume,
        turnover=bar.turnover,
        open_interest=open_interest,
        open_price=bar.open_price,
        high_price=bar.high_price,
        low_price=bar.low_price,
        close_price=bar.close_price,
        gateway_name=bar.gateway_name,
    )


def _build_field_override_engine(field_mode: str) -> type[rb.SameDayCloseBacktestingEngine]:
    class FieldOverrideSameDayCloseEngine(rb.SameDayCloseBacktestingEngine):
        def new_bars(self, dt) -> None:
            self.datetime = dt

            bars: dict[str, BarData] = {}
            for vt_symbol in self.vt_symbols:
                raw_bar: BarData | None = self.history_data.get((dt, vt_symbol), None)
                bar: BarData | None = None
                if raw_bar:
                    bar = _clone_bar(raw_bar, field_mode)
                    self.bars[vt_symbol] = bar
                    bars[vt_symbol] = bar
                elif vt_symbol in self.bars:
                    old_bar: BarData = self.bars[vt_symbol]
                    bar = BarData(
                        symbol=old_bar.symbol,
                        exchange=old_bar.exchange,
                        datetime=dt,
                        interval=old_bar.interval,
                        volume=0.0,
                        turnover=0.0,
                        open_interest=0.0 if field_mode in {"open_interest_zero", "volume_open_interest_zero"} else float(old_bar.open_interest),
                        open_price=old_bar.close_price,
                        high_price=old_bar.close_price,
                        low_price=old_bar.close_price,
                        close_price=old_bar.close_price,
                        gateway_name=old_bar.gateway_name,
                    )
                    if field_mode == "baseline":
                        bar.volume = float(old_bar.volume)
                    elif field_mode == "open_interest_zero":
                        bar.volume = float(old_bar.volume)
                    self.bars[vt_symbol] = bar

            self.strategy.on_bars(bars)
            self.cross_limit_order_on_close()

            if self.strategy.inited:
                self.update_daily_close(self.bars, dt)

    return FieldOverrideSameDayCloseEngine


def _path_metrics(equity: pd.Series) -> dict[str, float]:
    clean = pd.to_numeric(equity, errors="coerce").ffill().dropna()
    if clean.empty:
        return {
            "stage079_end_equity": ACCOUNT_CAPITAL,
            "stage079_total_return_pct": 0.0,
            "stage079_max_dd_pct": 0.0,
            "stage079_sharpe": 0.0,
            "stage079_ulcer": 0.0,
        }
    arr = clean.to_numpy(dtype=float)
    high = np.maximum.accumulate(arr)
    dd = np.divide(arr - high, high, out=np.zeros_like(arr), where=high != 0) * 100.0
    ret = pd.Series(arr).pct_change().fillna(0.0).to_numpy(dtype=float)
    std = float(np.std(ret, ddof=1)) if len(ret) > 1 else 0.0
    sharpe = float(np.mean(ret) / std * math.sqrt(252.0)) if std > 0 else 0.0
    return {
        "stage079_end_equity": float(arr[-1]),
        "stage079_total_return_pct": float((arr[-1] / ACCOUNT_CAPITAL - 1.0) * 100.0),
        "stage079_max_dd_pct": float(dd.min()),
        "stage079_sharpe": sharpe,
        "stage079_ulcer": float(math.sqrt(np.mean(np.square(np.minimum(dd, 0.0))))),
    }


def _trades_frame(trades: list[TradeData], variant: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for i, trade in enumerate(sorted(trades, key=lambda item: (pd.Timestamp(item.datetime), item.vt_tradeid)), start=1):
        rows.append(
            {
                "variant": variant,
                "trade_ordinal": i,
                "datetime": trade.datetime,
                "date": pd.Timestamp(trade.datetime).normalize(),
                "vt_symbol": trade.vt_symbol,
                "direction": getattr(trade.direction, "value", str(trade.direction)),
                "offset": getattr(trade.offset, "value", str(trade.offset)),
                "price": float(trade.price),
                "volume": float(trade.volume),
            }
        )
    return pd.DataFrame(rows)


def _risk_mode_rows(snapshots: list[dict[str, Any]], variant: str) -> list[dict[str, Any]]:
    if not snapshots:
        return []
    frame = pd.DataFrame(snapshots)
    if frame.empty or "risk_mode" not in frame.columns:
        return []
    frame["risk_mode"] = frame["risk_mode"].fillna("").astype(str)
    selected_volume = frame["selected_volume"] if "selected_volume" in frame.columns else pd.Series(0.0, index=frame.index)
    native_openable = frame["native_openable"] if "native_openable" in frame.columns else pd.Series(0, index=frame.index)
    frame["selected_volume"] = pd.to_numeric(selected_volume, errors="coerce").fillna(0.0)
    frame["native_openable"] = pd.to_numeric(native_openable, errors="coerce").fillna(0).astype(int)
    rows: list[dict[str, Any]] = []
    for risk_mode, group in frame.groupby("risk_mode", dropna=False):
        rows.append(
            {
                "variant": variant,
                "risk_mode": risk_mode or "(blank)",
                "candidate_count": int(len(group)),
                "native_openable_count": int(group["native_openable"].sum()),
                "selected_volume_sum": float(group["selected_volume"].sum()),
            }
        )
    return rows


def _run_variant(variant: str) -> dict[str, Any]:
    original_engine_class = rb.SameDayCloseBacktestingEngine
    if variant != "baseline":
        rb.SameDayCloseBacktestingEngine = _build_field_override_engine(variant)
    try:
        engine, analysis_df, statistics = rb.run_backtest(
            risk_ratio=BASE_RISK_RATIO,
            strategy_overrides=_c3_overrides(rb.START_DT),
            analysis_start=rb.START_DT,
            analysis_end=rb.END_DT,
            preload_start=rb.PRELOAD_START_DT,
            capital=C3_CAPITAL,
            save_artifacts=False,
            include_start_year_sweep=False,
            file_prefix=f"{OUTPUT_PREFIX}_{variant}",
            chart_title=f"Stage457 {variant}",
        )
    finally:
        rb.SameDayCloseBacktestingEngine = original_engine_class

    if analysis_df is None or analysis_df.empty:
        daily = pd.DataFrame(columns=["date", "c3_balance", "stage079_equity"])
    else:
        daily = analysis_df.copy().reset_index().rename(columns={"index": "date"})
        daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
        daily["c3_balance"] = pd.to_numeric(daily.get("balance", C3_CAPITAL), errors="coerce").ffill().fillna(C3_CAPITAL)
        daily["stage079_equity"] = daily["c3_balance"] + STAGE079_CASH
        daily["variant"] = variant

    snapshots = list(getattr(engine.strategy, "entry_candidate_snapshots", []) or [])
    trades = _trades_frame(list(engine.get_all_trades()), variant)
    metrics = _path_metrics(daily.set_index("date")["stage079_equity"] if not daily.empty else pd.Series(dtype=float))
    metrics.update(
        {
            "variant": variant,
            "c3_end_balance": float(statistics.get("end_balance", 0.0) or 0.0),
            "c3_total_return_pct": float(statistics.get("total_return", 0.0) or 0.0),
            "c3_max_dd_pct": float(statistics.get("max_ddpercent", 0.0) or 0.0),
            "c3_sharpe": float(statistics.get("sharpe_ratio", 0.0) or 0.0),
            "total_trade_count": int(statistics.get("total_trade_count", len(trades)) or len(trades)),
            "entry_candidate_count": int(len(snapshots)),
        }
    )
    return {
        "variant": variant,
        "metrics": metrics,
        "daily": daily[["variant", "date", "c3_balance", "stage079_equity"]],
        "trades": trades,
        "risk_mode_rows": _risk_mode_rows(snapshots, variant),
    }


def _diff_against_baseline(baseline: dict[str, Any], variant_result: dict[str, Any]) -> tuple[dict[str, Any], pd.DataFrame]:
    variant = str(variant_result["variant"])
    baseline_daily = baseline["daily"].set_index("date")["stage079_equity"].astype(float)
    variant_daily = variant_result["daily"].set_index("date")["stage079_equity"].astype(float)
    aligned = pd.concat([baseline_daily.rename("baseline"), variant_daily.rename(variant)], axis=1).ffill().dropna()
    aligned["equity_diff"] = aligned[variant] - aligned["baseline"]
    daily_diff = aligned.reset_index()
    daily_diff.insert(0, "variant", variant)

    base_trades = baseline["trades"].set_index("trade_ordinal")
    variant_trades = variant_result["trades"].set_index("trade_ordinal")
    max_ordinal = max(len(base_trades), len(variant_trades))
    mismatch = 0
    first_mismatch = ""
    for ordinal in range(1, max_ordinal + 1):
        base_row = base_trades.loc[ordinal].to_dict() if ordinal in base_trades.index else {}
        variant_row = variant_trades.loc[ordinal].to_dict() if ordinal in variant_trades.index else {}
        keys = ["date", "vt_symbol", "direction", "offset", "price", "volume"]
        if any(str(base_row.get(key, "")) != str(variant_row.get(key, "")) for key in keys):
            mismatch += 1
            if not first_mismatch:
                first_mismatch = str(ordinal)

    summary = {
        "variant": variant,
        "max_abs_equity_diff": float(daily_diff["equity_diff"].abs().max()) if not daily_diff.empty else 0.0,
        "end_equity_diff": float(daily_diff["equity_diff"].iloc[-1]) if not daily_diff.empty else 0.0,
        "trade_count_diff": int(len(variant_trades) - len(base_trades)),
        "trade_ordinal_mismatch_count": int(mismatch),
        "first_trade_ordinal_mismatch": first_mismatch,
    }
    return summary, daily_diff


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    for variant in VARIANTS:
        print(f"[stage457] running {variant}", flush=True)
        results.append(_run_variant(variant))

    summary_rows = [result["metrics"] for result in results]
    baseline = results[0]
    diff_rows: list[dict[str, Any]] = []
    daily_diff_frames: list[pd.DataFrame] = []
    for result in results[1:]:
        diff, daily_diff = _diff_against_baseline(baseline, result)
        diff_rows.append(diff)
        daily_diff_frames.append(daily_diff)
        for row in summary_rows:
            if row["variant"] == result["variant"]:
                row.update(diff)
                break
    summary_rows[0].update(
        {
            "max_abs_equity_diff": 0.0,
            "end_equity_diff": 0.0,
            "trade_count_diff": 0,
            "trade_ordinal_mismatch_count": 0,
            "first_trade_ordinal_mismatch": "",
        }
    )
    summary = pd.DataFrame(summary_rows)
    risk_mode = pd.DataFrame([row for result in results for row in result["risk_mode_rows"]])
    trade_diff = pd.DataFrame(diff_rows)
    daily_diff = pd.concat(daily_diff_frames, ignore_index=True) if daily_diff_frames else pd.DataFrame()

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    risk_mode.to_csv(RISK_MODE_PATH, index=False, encoding="utf-8-sig")
    trade_diff.to_csv(TRADE_DIFF_PATH, index=False, encoding="utf-8-sig")
    daily_diff.to_csv(DAILY_DIFF_PATH, index=False, encoding="utf-8-sig")

    diff_by_variant = {row["variant"]: row for row in diff_rows}
    volume_diff = diff_by_variant.get("volume_zero", {})
    oi_diff = diff_by_variant.get("open_interest_zero", {})
    volume_material = float(volume_diff.get("max_abs_equity_diff", 0.0) or 0.0) > 1e-9 or int(
        volume_diff.get("trade_ordinal_mismatch_count", 0) or 0
    ) > 0
    oi_material = float(oi_diff.get("max_abs_equity_diff", 0.0) or 0.0) > 1e-9 or int(
        oi_diff.get("trade_ordinal_mismatch_count", 0) or 0
    ) > 0
    decision_label = (
        "volume_not_material_but_open_interest_material_allow_ohlc_oi_spec"
        if (not volume_material and oi_material)
        else "volume_or_open_interest_material_keep_strict_ohlcvoi_requirement"
        if (volume_material or oi_material)
        else "volume_open_interest_not_material_allow_ohlc_only_spec"
    )
    decision = {
        "stage": "Stage157",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": decision_label,
        "promotion_candidate": "none",
        "volume_material": bool(volume_material),
        "open_interest_material": bool(oi_material),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "risk_mode": str(RISK_MODE_PATH),
            "trade_diff": str(TRADE_DIFF_PATH),
            "daily_diff": str(DAILY_DIFF_PATH),
            "report": str(REPORT_PATH),
        },
        "next_step": "若volume物料性为真，继续寻找冻结时点前真实分钟volume数据源；若仅open_interest物料性为真，可把Stage155规格降级为OHLC+OI并先做小批次一致预收盘回放。",
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")

    report = "\n".join(
        [
            "# Stage157 volume/open_interest 物料性审计",
            "",
            f"- 生成时间：{decision['generated_at']}",
            "- 阶段性质：字段物料性反事实；不新增策略、不修改 Stage079/C3 交易规则。",
            f"- 决策标签：`{decision_label}`。",
            "",
            "## 外部调研与判断",
            "",
            "- 期货成交量与持仓量含义不同：volume 描述期间成交活动，open interest 描述未平仓合约存量；二者都可能改变趋势确认或风险承载，但不能互相替代。",
            "- 本阶段用动态反事实判断字段是否影响 Stage079 路径，不靠静态引用下结论。",
            "",
            "## 汇总",
            "",
            _md_table(summary),
            "",
            "## 风险模式分布",
            "",
            _md_table(risk_mode),
            "",
            "## 相对基准差异",
            "",
            _md_table(trade_diff),
            "",
            "## 结论",
            "",
            f"- volume_material：`{bool(volume_material)}`。",
            f"- open_interest_material：`{bool(oi_material)}`。",
            "- 如果字段物料性为真，不能因为 Stage156 小样本 volume 全0就降级规格；必须找真实冻结时点前字段源。",
            "- 如果字段物料性为假，才允许把预收盘一致回放规格降级并推进小批次真实重放。",
            "",
            "## 过拟合与继续价值反思",
            "",
            "- 过拟合：否。本阶段只做字段置零反事实，没有按收益筛参数。",
            "- 继续价值：取决于结果。若 volume 不物料，预收盘一致回放可继续；若 volume 物料，则下一步必须先换数据源。",
        ]
    )
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
