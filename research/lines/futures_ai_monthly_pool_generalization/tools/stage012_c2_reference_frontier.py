"""Conditional entry-day C2 identifiability, not a trade replay or 60d label.

Daily classification assumes entry at the day's true first open. Actual session
and fill qualification are separate. Missingness is never turned into no stop.
"""
import ast
from collections import Counter
from copy import deepcopy
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from training_source_profile import apply_training_overrides

LINE = Path(__file__).resolve().parents[1]
ROOT = LINE.parents[2]
PRIOR = ROOT / "research/lines/futures_trend_rollover_shape_same_volume/outputs"
OUT = LINE / "outputs/stage012_c2_reference_frontier"


def parse_boolean(series):
    values = series.astype(str).str.lower().str.strip()
    if not values.isin(["true", "false", "1", "0"]).all():
        raise ValueError("explicit boolean required")
    return values.isin(["true", "1"])


def initial_risk(direction, entry, signal_stop, configured_tick):
    if direction not in {"long", "short"}:
        raise ValueError("invalid direction")
    values = [entry, signal_stop, configured_tick]
    if not all(np.isfinite(x) and x > 0 for x in values):
        return dict(risk_status="unknown_or_invalid_economic_input", risk_price=None)
    risk = (entry-signal_stop) if direction == "long" else (signal_stop-entry)
    if risk <= 0:
        return dict(risk_status="gap_wrong_side_or_zero", risk_price=risk)
    if risk < max(configured_tick, 1e-9):
        return dict(risk_status="below_configured_tick", risk_price=risk)
    return dict(risk_status="valid", risk_price=risk)


def classify_daily(direction, opening, high, low, close, risk):
    if direction not in {"long", "short"}:
        raise ValueError("invalid direction")
    if not all(np.isfinite(x) and x > 0 for x in [opening,high,low,close,risk]) or low > min(opening,close) or high < max(opening,close) or low > high:
        raise ValueError("invalid OHLC or risk")
    sign = 1 if direction == "long" else -1
    stop, confirm = opening-sign*risk, opening+sign*risk
    if stop <= 0 or confirm <= 0:
        raise ValueError("nonpositive OHLC-derived barrier")
    adverse = low <= stop if direction == "long" else high >= stop
    advanced = high >= confirm if direction == "long" else low <= confirm
    case = "both_unidentified" if adverse and advanced else "stop_only" if adverse else "confirm_only" if advanced else "neither"
    actions = {"both_unidentified":["c2_stop","confirmation_disarms_c2"],
               "stop_only":["c2_stop"], "confirm_only":["confirmation_disarms_c2"],
               "neither":["no_c2_trigger"]}[case]
    return dict(daily_case=case, stop_threshold=stop, confirm_threshold=confirm,
                daily_action_identified=case!="both_unidentified", possible_actions=actions,
                exact_fill_identified=False,
                assumption="entry equals true full-session first open; complete correct-session daily OHLC")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def frozen_initial_stop_host():
    current=json.loads((ROOT/"official_strategy_materials/CURRENT.json").read_text())
    release=ROOT/"official_strategy_materials"/current["strategy_version"]/"releases"/current["release_id"]
    manifest=json.loads((release/"manifest.json").read_text())
    def method(logical, class_name):
        path=release/"payload"/logical
        expected=next(r["sha256"] for r in manifest["files"] if r["logical_path"]==logical)
        if sha(path)!=expected:raise ValueError("frozen stop source hash mismatch")
        tree=ast.parse(path.read_text())
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==class_name)
        return deepcopy(next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=="_entry_stop_price")),dict(path=str(path),sha256=expected)
    base,base_receipt=method("examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py","QmtRollPortfolioStrategy")
    override,override_receipt=method("examples/portfolio_backtesting/analyze_qmt_roll_stage804_stage777_long_tighter_initial_stop_yearly.py","QmtRollPortfolioStrategyLongTighterInitialStop")
    base_class=ast.ClassDef(name="StopBase",bases=[],keywords=[],body=[base],decorator_list=[])
    sub_class=ast.ClassDef(name="StopHost",bases=[ast.Name(id="StopBase",ctx=ast.Load())],keywords=[],body=[override],decorator_list=[])
    module=ast.Module(body=[ast.ImportFrom(module="__future__",names=[ast.alias(name="annotations")],level=0),base_class,sub_class],type_ignores=[])
    namespace=dict(pd=pd,np=np,Any=Any)
    exec(compile(ast.fix_missing_locations(module),"frozen_initial_stop_probe","exec"),namespace)
    host=namespace["StopHost"]();host.stop_loss_pct=.02;host.long_tighter_initial_stop=True
    return host,[base_receipt,override_receipt]


def run():
    OUT.mkdir(parents=True,exist_ok=False)
    started=datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
    source=LINE/"outputs/stage008_monthly_raw_matrix/monthly_raw_signal_matrix.csv"
    source_summary=json.loads((source.parent/"summary.json").read_text())
    if sha(source)!=source_summary["matrix_sha256"]:raise ValueError("raw matrix changed")
    frame=pd.read_csv(source,dtype=str,keep_default_na=False)
    # A blank is unknown, not False; the known-complete gate is explicit.
    selected=frame.loc[frame.fresh_after_hardblocks.eq("True")].copy()
    if not parse_boolean(selected.input_ready).all():raise ValueError("unready reference signal")
    if not parse_boolean(selected.fresh_qualification_complete).all():raise ValueError("unknown hardblock state")
    if len(selected)!=source_summary["fresh_after_hardblocks"]:raise ValueError("reference event count mismatch")
    dates=np.load(PRIOR/"stage265_deep_daily/rqalpha/trading_dates.npy",allow_pickle=False)
    calendar=pd.DatetimeIndex(pd.to_datetime(dates.astype(str),format="%Y%m%d"))
    calendar=calendar[(calendar>="2010-01-01") & (calendar<="2026-10-16")]
    requests=[];wanted=set()
    for row in selected.to_dict("records"):
        signal=pd.Timestamp(row["eval_date"]);index=int(calendar.get_loc(signal));following=calendar[index+1] if index+1<len(calendar) else pd.NaT
        row["reference_execution_date"]="" if pd.isna(following) else str(following.date())
        row["direction"]="long" if row["raw_signal"].startswith("long") else "short"
        row["signal_prior_dates"]=[str(x.date()) for x in calendar[max(0,index-2):index+1]]
        requests.append(row)
        for date in [*row["signal_prior_dates"],row["reference_execution_date"]]:
            if date:wanted.add((row["reference_epoch"],date))
    db=PRIOR/"stage266_clean_daily/clean_daily.sqlite";before=db.stat()
    with sqlite3.connect(db.resolve().as_uri()+"?mode=ro",uri=True) as con:
        con.execute("PRAGMA query_only=ON")
        values=",".join("(?,?)" for _ in wanted)
        parameters=[v for pair in sorted(wanted) for v in pair]
        bars=pd.read_sql_query(f"WITH requested(epoch,day) AS (VALUES {values}) SELECT b.contract_epoch_id,b.trade_date,b.open,b.high,b.low,b.close,b.source_id FROM daily_bars b JOIN requested r ON b.contract_epoch_id=r.epoch AND b.trade_date=r.day",con,params=parameters)
    if (before.st_size,before.st_mtime_ns)!=(db.stat().st_size,db.stat().st_mtime_ns):raise ValueError("clean DB changed")
    lookup={(r["contract_epoch_id"],r["trade_date"]):r for r in bars.to_dict("records")}
    economic_path=LINE/"outputs/stage006_economic_coverage/epoch_economic_inventory.csv"
    economics=pd.read_csv(economic_path,keep_default_na=False).set_index("contract_epoch_id").to_dict("index")
    host,bindings=frozen_initial_stop_host()
    rows=[]
    for item in requests:
        row={k:v for k,v in item.items() if k not in {"signal_prior_dates"}}
        row.update(probe_status="unknown",daily_case="unknown",daily_action_identified=False,
                   exact_fill_identified=False,canonical_session_first_open_verified=False,
                   reference_only=True,not_a_60d_label=True)
        try:
            epoch=item["reference_epoch"]
            signal_bars=[lookup[(epoch,date)] for date in item["signal_prior_dates"]]
            signal_bar=signal_bars[-1]
            future=lookup[(epoch,item["reference_execution_date"])]
            meta=economics.get(epoch,{})
            tick=float(meta.get("tick_size") or "nan")
            bar=SimpleNamespace(close_price=signal_bar["close"],low_price=signal_bar["low"],high_price=signal_bar["high"])
            stop=host._entry_stop_price(item["direction"],bar,pd.DataFrame(signal_bars),True)
            risk=initial_risk(item["direction"],future["open"],stop,tick)
            row.update(risk,signal_stop_price=stop,reference_entry_price=future["open"],configured_tick=tick,
                       daily_open=future["open"],daily_high=future["high"],daily_low=future["low"],daily_close=future["close"],
                       signal_source_id=signal_bar["source_id"],entry_source_id=future["source_id"])
            if risk["risk_status"]=="valid":
                result=classify_daily(item["direction"],future["open"],future["high"],future["low"],future["close"],risk["risk_price"])
                result["possible_actions"]=json.dumps(result["possible_actions"])
                row.update(result,probe_status="conditional_daily_reference")
            else:row["probe_status"]=risk["risk_status"]
        except KeyError:
            row["probe_status"]="missing_required_signal_or_next_source_day_bar"
        rows.append(row)
    result=pd.DataFrame(rows)
    result.to_csv(OUT/"entry_day_c2_frontier.csv",index=False)
    profile=apply_training_overrides({"enable_stage847_half_r_stop_retry":True,"enable_stage827_intraday_c2_stop":True})
    summary=dict(status="CONDITIONAL_ENTRY_DAY_IDENTIFICATION_NOT_60D_LABELS",started_at=started,
        completed_at=datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),reference_events=len(result),
        products=int(result.product_vt_symbol.nunique()),daily_rows_read=len(bars),
        probe_status_counts=dict(Counter(result.probe_status)),daily_case_counts=dict(Counter(result.daily_case)),
        conditional_action_identified=int(result.daily_action_identified.sum()),
        canonical_session_first_open_verified=0,exact_fills_identified=0,
        source_matrix_sha256=sha(source),economic_inventory_sha256=sha(economic_path),frozen_initial_stop_sources=bindings,
        reference_execution_kernel=dict(path=str(ROOT/"examples/portfolio_backtesting/qmt_roll_intraday_execution.py"),sha256=sha(ROOT/"examples/portfolio_backtesting/qmt_roll_intraday_execution.py"),version="repaired_open_first_adverse_minute_ties; not frozen_m0008_C2"),
        training_overrides=profile,model_fits=0,financial_backtests=0,economic_60d_labels=0,orders=0,
        scope="185 hypothetical monthly first-open probes; no positions/rollover/continuous source account or PIT certification",
        script_sha256=sha(__file__),frontier_sha256=sha(OUT/"entry_day_c2_frontier.csv"))
    (OUT/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:v for k,v in summary.items() if k not in {"frozen_initial_stop_sources","reference_execution_kernel"}},ensure_ascii=False,indent=2))


if __name__=="__main__":run()
