"""All-market as-of month-end frozen signal input matrix; no economic replay."""
import ast
from copy import deepcopy
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import sqlite3
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import talib

from training_source_profile import PROFILE_PATH, apply_training_overrides

LINE = Path(__file__).resolve().parents[1]
ROOT = LINE.parents[2]
PRIOR = ROOT / "research/lines/futures_trend_rollover_shape_same_volume/outputs"
OUT = LINE / "outputs/stage008_monthly_raw_matrix"
CONTRACT = LINE / "outputs/stage005_source_mapping/raw_matrix_contract.json"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def choose_representative(frame, asof):
    if frame.empty:
        return None
    selected = frame.loc[pd.to_datetime(frame.trade_date).eq(pd.Timestamp(asof))].copy()
    selected = selected.loc[np.isfinite(selected.volume) & selected.volume.gt(0)]
    if selected.empty:
        return None
    if selected.contract_epoch_id.duplicated().any():
        raise ValueError("duplicate representative candidate")
    selected = selected.sort_values(["volume", "close_oi", "contract_epoch_id"], ascending=[False, False, True], na_position="last")
    return selected.iloc[0].to_dict()


def strict_history(frame, calendar, asof):
    calendar = pd.DatetimeIndex(calendar)
    asof = pd.Timestamp(asof)
    if calendar.hasnans or calendar.has_duplicates or not calendar.is_monotonic_increasing or asof not in calendar:
        raise ValueError("invalid calendar")
    index = int(calendar.get_loc(asof))
    if index < 40:
        raise ValueError("insufficient_calendar_history")
    expected = calendar[index-40:index+1]
    bounded = frame.loc[pd.to_datetime(frame.trade_date).le(asof)].copy()
    bounded["trade_date"] = pd.to_datetime(bounded.trade_date)
    if bounded.trade_date.duplicated().any():
        raise ValueError("duplicate history date")
    bounded = bounded.loc[bounded.trade_date.ge(expected[0])].sort_values("trade_date")
    if not pd.DatetimeIndex(bounded.trade_date).equals(expected):
        raise ValueError("missing_exact_epoch_calendar_bar")
    prices = bounded[["open", "high", "low", "close"]].to_numpy(dtype=float)
    if not np.isfinite(prices).all() or (prices <= 0).any():
        raise ValueError("invalid_OHLC")
    if (bounded.high < bounded[["open", "close"]].max(axis=1)).any() or (bounded.low > bounded[["open", "close"]].min(axis=1)).any() or (bounded.low > bounded.high).any():
        raise ValueError("invalid_OHLC_geometry")
    if not np.isfinite(bounded[["volume", "close_oi"]].to_numpy(dtype=float)).all() or bounded.volume.le(0).any() or bounded.close_oi.lt(0).any():
        raise ValueError("unknown_or_invalid_volume_oi")
    return bounded.reset_index(drop=True)


def frozen_signal_host():
    current = json.loads((ROOT / "official_strategy_materials/CURRENT.json").read_text())
    release = ROOT / "official_strategy_materials" / current["strategy_version"] / "releases" / current["release_id"]
    manifest = json.loads((release / "manifest.json").read_text())
    logical = "examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py"
    source = release / "payload" / logical
    expected = next(x["sha256"] for x in manifest["files"] if x["logical_path"] == logical)
    if digest(source) != expected:
        raise ValueError("frozen_signal_source_mismatch")
    config = json.loads(CONTRACT.read_text())
    methods = config["required_methods"] + ["_evaluate_ma5_angle_reversal_filter"]
    tree = ast.parse(source.read_text())
    original = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "QmtRollPortfolioStrategy")
    functions = {n.name:n for n in original.body if isinstance(n, ast.FunctionDef)}
    hashes = {name:hashlib.sha256(ast.dump(functions[name], include_attributes=False).encode()).hexdigest() for name in methods}
    klass = ast.ClassDef(name="FrozenMonthlySignal", bases=[], keywords=[], body=[deepcopy(functions[n]) for n in methods], decorator_list=[])
    module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), klass], type_ignores=[])
    namespace = dict(pd=pd, np=np, math=math, Any=Any)
    exec(compile(ast.fix_missing_locations(module), str(source), "exec"), namespace)
    host = namespace["FrozenMonthlySignal"]()
    settings = apply_training_overrides(config["settings"])
    for key, value in settings.items():
        setattr(host, key, value)
    return host, dict(release_id=current["release_id"], frozen_source_sha256=expected,
                      method_ast_sha256=hashes, settings=settings,
                      contract_sha256=digest(CONTRACT), training_profile_sha256=digest(PROFILE_PATH))


def signal_fields(host, history):
    close = history.close.to_numpy(dtype=float)
    history = history.copy()
    history["open_interest"] = history.close_oi
    rsi = float(talib.RSI(close, timeperiod=int(host.rsi_length))[-1])
    if not np.isfinite(rsi):
        raise ValueError("nonfinite_RSI")
    am = SimpleNamespace(close_array=close, rsi=lambda length: float(talib.RSI(close, timeperiod=length)[-1]))
    raw = host._generate_signal(am, history)
    dif, dea, hist = host._calculate_macd(pd.Series(close))
    fields = {"raw_signal":raw["signal"], "bullish_alignment":raw["bullish_alignment"],
              "bearish_alignment":raw["bearish_alignment"], "rsi6":rsi,
              "breakout":raw["breakout"], "risk_mode":raw["risk_mode"],
              "dif_over_close":float(dif.iloc[-1]/close[-1]),
              "dea_over_close":float(dea.iloc[-1]/close[-1]),
              "macd_hist_over_close":float(hist.iloc[-1]/close[-1])}
    signal = str(raw["signal"])
    for direction in ["long", "short"]:
        shock = host._long_signal_atr_shock_snapshot(direction, history, "flat_entry")
        spread = host._long_signal_range_atr_snapshot(direction, history, "flat_entry")
        fields[direction+"_shock_reason"] = shock["long_signal_atr_shock_reason"]
        fields[direction+"_range_reason"] = spread["long_signal_range_atr_reason"]
        known = all(np.isfinite(snap[key]) and snap[key] > 0 for snap,key in [
            (shock,"long_signal_atr_shock_atr"), (spread,"long_signal_range_prior_atr")])
        fields[direction+"_hardblock_known"] = bool(known)
        fields[direction+"_hardblock"] = bool(shock["long_signal_atr_shock_blocked"] or spread["long_signal_range_atr_condition_met"]) if known else None
    allowed_direction = bool(signal.startswith("long") or (signal.startswith("short") and host._can_open_short_signal(signal)))
    direction = "long" if signal.startswith("long") else "short" if signal.startswith("short") else ""
    fields["fresh_direction_allowed"] = allowed_direction
    fields["fresh_after_hardblocks"] = bool(allowed_direction and fields[direction+"_hardblock_known"] and not fields[direction+"_hardblock"]) if direction else False
    fields["fresh_qualification_complete"] = bool(not direction or fields[direction+"_hardblock_known"])
    fields["input_ready"] = True
    return fields


def run():
    OUT.mkdir(parents=True, exist_ok=False)
    host, frozen = frozen_signal_host()
    started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
    raw_calendar = np.load(PRIOR / "stage265_deep_daily/rqalpha/trading_dates.npy", allow_pickle=False)
    calendar = pd.DatetimeIndex(pd.to_datetime(raw_calendar.astype(str), format="%Y%m%d"))
    calendar = calendar[(calendar >= "2010-01-01") & (calendar <= "2026-10-16")]
    month_ends = pd.Series(calendar, index=calendar).groupby(calendar.to_period("M")).max()
    month_ends = month_ends.loc[month_ends.index < pd.Period("2026-10", freq="M")]
    database = PRIOR / "stage266_clean_daily/clean_daily.sqlite"
    before = database.stat()
    conn = sqlite3.connect(database.resolve().as_uri()+"?mode=ro", uri=True)
    try:
        conn.execute("PRAGMA query_only=ON")
        catalog = pd.read_sql_query("SELECT DISTINCT exchange,product FROM contracts ORDER BY exchange,product", conn)
        marks = ",".join("?" for _ in month_ends)
        candidates = pd.read_sql_query(f"SELECT exchange,product,contract_epoch_id,trade_date,volume,close_oi FROM daily_bars WHERE trade_date IN ({marks})", conn, params=[str(x.date()) for x in month_ends])
        selected = []
        for (_, _, day), group in candidates.groupby(["exchange", "product", "trade_date"], sort=True):
            row = choose_representative(group, pd.Timestamp(day))
            if row is not None:
                selected.append(row)
        selected = pd.DataFrame(selected)
        epochs = sorted(selected.contract_epoch_id.unique())
        marks = ",".join("?" for _ in epochs)
        history = pd.read_sql_query(f"SELECT contract_epoch_id,trade_date,open,high,low,close,volume,close_oi FROM daily_bars WHERE contract_epoch_id IN ({marks}) AND trade_date<=?", conn, params=[*epochs,"2026-09-30"])
    finally:
        conn.close()
    history["trade_date"] = pd.to_datetime(history.trade_date)
    frames = {epoch:group for epoch,group in history.groupby("contract_epoch_id", sort=False)}
    lookup = {(r["exchange"],r["product"],r["trade_date"]):r for r in selected.to_dict("records")}
    rows=[]
    for item in catalog.itertuples(index=False):
        for day in month_ends:
            row=dict(exchange=item.exchange, product=item.product, product_vt_symbol=item.product+"."+item.exchange,
                     eval_date=str(day.date()), monthly_average_F=item.product.endswith("_F"),
                     input_ready=False, input_status="no_asof_observation", reference_epoch="",
                     raw_signal=None, fresh_direction_allowed=None, fresh_after_hardblocks=None,
                     calendar_qualification="inherited_common_calendar_not_exchange_PIT")
            representative = lookup.get((item.exchange,item.product,str(day.date())))
            if representative is not None:
                epoch=representative["contract_epoch_id"]
                row.update(reference_epoch=epoch, asof_volume=representative["volume"], asof_close_oi=representative["close_oi"])
                try:
                    bounded=strict_history(frames[epoch],calendar,day)
                    row.update(signal_fields(host,bounded),input_status="frozen_AM41_input_ready",feature_start=str(bounded.trade_date.min().date()))
                except ValueError as exc:
                    row["input_status"]=str(exc)
            rows.append(row)
    after = database.stat()
    if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
        raise ValueError("database_changed_during_audit")
    result=pd.DataFrame(rows)
    result.to_csv(OUT/"monthly_raw_signal_matrix.csv",index=False)
    result.assign(year=result.eval_date.str[:4]).groupby("year").agg(
        total=("eval_date","size"), ready=("input_ready","sum"),
        nonempty_raw=("raw_signal",lambda x:int(x.fillna("").ne("").sum()))).to_csv(OUT/"annual_counts.csv")
    ready=result.loc[result.input_ready]
    ordinary=ready.loc[~ready.monthly_average_F]
    summary=dict(started_at=started,completed_at=datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        status="MONTHLY_RAW_INPUT_MATRIX_ONLY_NO_LABELS",rows=len(result),products=len(catalog),months=len(month_ends),
        representative_rows=len(selected),history_rows_read=len(history),input_ready_rows=len(ready),
        input_ready_products=int(ready.product_vt_symbol.nunique()),ordinary_input_ready_rows=len(ordinary),
        input_status_counts={str(k):int(v) for k,v in result.input_status.value_counts().items()},
        raw_signal_counts={str(k):int(v) for k,v in ready.raw_signal.value_counts().items()},
        fresh_after_hardblocks=int(ready.fresh_after_hardblocks.sum()),frozen=frozen,
        database_bytes=before.st_size,database_mtime_ns=before.st_mtime_ns,database_unchanged=True,
        model_fits=0,financial_backtests=0,economic_labels_generated=0,orders=0,
        training_half_r_enabled=bool(host.enable_stage847_half_r_stop_retry),production_modified=False,
        script_sha256=digest(__file__),matrix_sha256=digest(OUT/"monthly_raw_signal_matrix.csv"))
    (OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:v for k,v in summary.items() if k!="frozen"},ensure_ascii=False,indent=2))


if __name__ == "__main__":
    run()
