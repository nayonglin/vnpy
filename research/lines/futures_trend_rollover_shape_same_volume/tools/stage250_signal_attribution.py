"""Read-only attribution of a frozen mail cohort; never run a trading engine.

Execute only selected pure methods extracted from the frozen strategy AST.
The original method body is retained, with one trace assignment before its
final return. No strategy/runtime module, credential or account file is loaded.
"""
from __future__ import annotations

import ast
import hashlib
import json
import math
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd
import talib

LINE = Path(__file__).resolve().parents[1]
OUT = LINE / "outputs/stage250_20261015_no_signal_report"
EVIDENCE = OUT / "evidence"
TARGET = "2026-10-15"
METHODS = {
    "_generate_signal", "_passes_entry_filters", "_signal_result", "_calculate_macd",
    "_open_interest_risk_mode", "_volume_open_interest_risk_mode",
    "_is_latest_ma_extreme", "_get_ma_slope_direction", "_wick_chop_filter_ok",
    "_is_simple_ma_trend", "_evaluate_ma5_angle_reversal_filter",
}
NAMES = dict(zip(
    "AP CF FG MA OI SA SH SM au cu fu hc jm lc lh rb ru si sp".split(),
    "苹果 棉花 玻璃 甲醇 菜油 纯碱 烧碱 锰硅 黄金 铜 燃料油 热卷 焦煤 碳酸锂 生猪 螺纹钢 橡胶 工业硅 纸浆".split(),
))


def safe(value):
    if isinstance(value, dict):
        return {str(k): safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.floating, float)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, np.integer):
        return int(value)
    return value


def pure_strategy():
    src = EVIDENCE / "qmt_roll_portfolio_strategy.py"
    parsed = ast.parse(src.read_text())
    original = next(n for n in parsed.body if isinstance(n, ast.ClassDef) and n.name == "QmtRollPortfolioStrategy")
    nodes = []
    defaults = {}
    for node in original.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            try:
                defaults[node.target.id] = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                pass
        if isinstance(node, ast.FunctionDef) and node.name in METHODS:
            if node.name == "_generate_signal":
                node.body.insert(-1, ast.parse("self._trace = locals().copy()").body[0])
            nodes.append(node)
    assert {n.name for n in nodes} == METHODS
    cls = ast.ClassDef(name="PureSignal", bases=[], keywords=[], body=nodes, decorator_list=[])
    module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), cls], type_ignores=[])
    namespace = {"pd": pd, "np": np, "math": math, "Any": Any}
    exec(compile(ast.fix_missing_locations(module), str(src), "exec"), namespace)
    obj = namespace["PureSignal"]()
    for k, v in defaults.items():
        setattr(obj, k, v)
    base = ast.parse((EVIDENCE / "run_qmt_roll_backtest.py").read_text())
    fn = next(n for n in base.body if isinstance(n, ast.FunctionDef) and n.name == "build_roll_setting")
    setting = next(n.value for n in fn.body if isinstance(n, ast.AnnAssign) and getattr(n.target, "id", "") == "setting")
    for key, value in zip(setting.keys, setting.values):
        try:
            setattr(obj, ast.literal_eval(key), ast.literal_eval(value))
        except (ValueError, TypeError):
            pass
    # AM41 is declared in Stage777 config and applied by Stage772 ExactAm.
    return obj


def describe(row):
    checks = row["checks"]
    if row["raw_signal"] and not row["final_signal"]:
        failed = []
        if not row["ma5_filter_pass"]:
            failed.append("MA5连续两步逆向")
        if row["raw_signal"].startswith("short") and row["ma5_delta"] > 0:
            failed.append("空头MA5斜率大于0")
        if not row["wick_filter_pass"]:
            failed.append(f"近10根长影线{row['wick_count']}根，超过5根上限")
        return "产生" + row["raw_signal"] + "，但" + "；".join(failed) + "，初筛清空信号"
    trigger = [label for key, label in (
        ("golden_5_10", "MA5/10金叉"), ("death_5_10", "MA5/10死叉"),
        ("golden_10_20", "MA10/20金叉"), ("death_10_20", "MA10/20死叉"),
        ("golden_20_40", "MA20/40金叉"), ("death_20_40", "MA20/40死叉"),
        ("macd_golden", "MACD金叉"), ("macd_death", "MACD死叉"),
    ) if checks[key]]
    alignment = "多头排列" if checks["bullish_alignment"] else "空头排列" if checks["bearish_alignment"] else "均线混排"
    if not trigger:
        return alignment + "，今天无新的MA或MACD交叉触发"
    return "、".join(trigger) + "；" + alignment + "，不满足所需方向的完整排列/MACD条件"


def calculate(obj, frame):
    history = frame.tail(41).reset_index(drop=True)
    assert len(history) == 41
    close = history["close"].to_numpy(dtype=float)
    am = SimpleNamespace(close_array=close, rsi=lambda length: talib.RSI(close, timeperiod=length)[-1])
    # Observe which pre-filter candidate the unmodified method checks.
    captured = []
    original_filter = obj._passes_entry_filters

    def capture(signal, hist):
        captured.append(signal)
        return original_filter(signal, hist)

    obj._passes_entry_filters = capture
    try:
        result = obj._generate_signal(am, history)
    finally:
        obj._passes_entry_filters = original_filter
    trace = obj._trace
    checks = {k: bool(trace[k]) for k in [
        "golden_5_10", "death_5_10", "golden_10_20", "death_10_20",
        "golden_20_40", "death_20_40", "macd_golden", "macd_death",
        "bullish_alignment", "bearish_alignment", "allow_long", "allow_short",
        "breakout_up", "breakout_down",
    ]}
    raw = captured[0] if captured else ""
    wick_pass, wick_count, _ = obj._wick_chop_filter_ok(history, 10, 5)
    row = {
        "product": str(frame["product"].iloc[-1]), "contract": str(frame["contract"].iloc[-1]),
        "date": str(frame["datetime"].iloc[-1])[:10], "close": float(close[-1]),
        "window_start": str(history["datetime"].iloc[0])[:10], "window_bars": 41,
        "ma5_prev": trace["short_y"], "ma5": trace["short_t"],
        "ma10_prev": trace["mid_y"], "ma10": trace["mid_t"],
        "ma20_prev": trace["long_y"], "ma20": trace["long_t"],
        "ma40_prev": trace["extra_y"], "ma40": trace["extra_t"],
        "dif_prev": trace["dif"].iloc[-2], "dif": trace["dif"].iloc[-1],
        "dea_prev": trace["dea"].iloc[-2], "dea": trace["dea"].iloc[-1],
        "macd_hist": trace["macd_hist_t"], "rsi6": result["rsi_value"],
        "ma5_recent3": history["close"].rolling(5).mean().tail(3).tolist(),
        "ma5_delta": trace["short_t"] - trace["short_y"],
        "ma5_filter_pass": obj._is_latest_ma_extreme(history,5,3,"min" if raw.startswith("short") else "max")[0],
        "wick_count": wick_count, "wick_filter_pass": wick_pass,
        "simple_trend_history_required": 45, "checks": checks,
        "raw_signal": raw, "final_signal": result["signal"],
        "donchian_upper": history["high"].iloc[:-1].tail(20).max(),
        "donchian_lower": history["low"].iloc[:-1].tail(20).min(),
    }
    row["reason"] = describe(row)
    return safe(row)


def main():
    obj = pure_strategy()
    bars = pd.read_csv(EVIDENCE / "bars_65.csv")
    decision = json.loads(next(EVIDENCE.glob("*_decision_*.json")).read_text())
    pool = decision["ai_pool_audit"]["latest_products"]
    rows = []
    for product, frame in bars.groupby("product", sort=False):
        row = calculate(obj, frame)
        row["name"] = NAMES[product.split(".")[0]]
        row["in_ai_pool"] = product in pool
        row["pool_rank"] = pool.index(product) + 1 if product in pool else None
        row["primary_reason"] = row["reason"]
        row["eligibility_note"] = "10月池内" if product in pool else "10月池外；即使以后有基础信号也不具备本月新开仓资格，今天未实际走到AI过滤"
        rows.append(row)
    rows.sort(key=lambda r: (not r["in_ai_pool"], r["pool_rank"] or 99, r["product"]))
    candidates = pd.read_csv(EVIDENCE / "entry_candidates.csv")
    # Cross-check historical frozen candidate indicator values using the same
    # rolling AM41 calculation; do not rerun portfolio sizing or any engine.
    crosschecks = []
    for _, candidate in candidates[candidates["date"] >= "2026-10-01"].iterrows():
        frame = bars[(bars["contract"] == candidate["contract_vt_symbol"]) & (bars["datetime"].str[:10] <= candidate["date"])]
        if len(frame) < 41:
            continue
        rebuilt = calculate(obj, frame)
        pairs = [("ma10", "ma_mid_value"), ("ma20", "ma_long_value"), ("rsi6", "rsi_value")]
        differences = {a: abs(rebuilt[a] - float(candidate[b])) for a,b in pairs}
        match = rebuilt["final_signal"] == candidate["signal"] and max(differences.values()) < 1e-8
        crosschecks.append({"date": candidate["date"], "product": candidate["product_vt_symbol"], "signal": candidate["signal"], "matched": match, "absolute_differences": differences})
    assert crosschecks and all(c["matched"] for c in crosschecks), crosschecks
    assert len(rows) == 19 and sum(r["in_ai_pool"] for r in rows) == 11
    assert not candidates["date"].eq(TARGET).any()
    assert not any(r["final_signal"] for r in rows), rows
    settings = {key: getattr(obj,key) for key in ["ma_short","ma_mid","ma_long","ma_extra_long","rsi_length","enable_rsi_filter","ma5_extreme_filter_enabled","ma5_extreme_compare_days","ma5_angle_reversal_filter_enabled","short_ma5_slope_filter_enabled","wick_chop_filter_enabled","wick_chop_filter_lookback","wick_chop_filter_max_days","donchian_entry_period"]}
    payload = {"target_date":TARGET,"source_cohort_id":decision["cohort_id"],"method":"frozen_strategy_pure_method_ast_with_readonly_sqlite_snapshot","settings":settings,"historical_candidate_crosschecks":crosschecks,"rows":rows}
    (OUT / "diagnostics.json").write_text(json.dumps(safe(payload),ensure_ascii=False,indent=2,allow_nan=False))
    pd.json_normalize(rows).to_csv(OUT / "per_product.csv",index=False,encoding="utf-8-sig")
    print(json.dumps({"crosschecks":crosschecks,"rows":[{k:r[k] for k in ["name","product","in_ai_pool","raw_signal","final_signal","primary_reason"]} for r in rows]},ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()
