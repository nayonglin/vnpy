"""Zero-account enumeration using the accepted original C9 signal functions.

No engine, strategy initialization, planner, orders, positions, PnL, model fit or
network access. Existing Stage004 coverage is a cached timestamp-key audit,
not proof that every possible account path is executable.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
LINE = ROOT / "research/lines/futures_trend_triple_screen"
PROJECT = ROOT / "examples/portfolio_backtesting"
FROZEN_SITE = Path("/Users/mac/Documents/Codex/fian-research-20261014/.py311/lib/python3.11/site-packages")
VENDOR = Path("/Users/mac/Documents/Codex/fian-handoff-20261014/vnpy_handoff_20261014/vendor")
OUTPUT = LINE / "outputs/stage005_potential_signal_demand"
PROTOCOL = LINE / "stages/20261017_2326_stage005_potential_signal_demand_protocol.md"
A0 = LINE / "outputs/stage001_first_screen/A0_attempt2"
OLD = ROOT / "research/lines/futures_trend_rollover_shape_same_volume/outputs/stage251_half_r_ab/A_final3"
COVERAGE = LINE / "outputs/stage004_minute_coverage"
REVIEW = LINE / "outputs/stage004_independent_review/review_receipt.json"
WEEKLY = LINE / "outputs/stage001_weekly_features/weekly_daily.csv"
DATABASE = ROOT / ".vntrader/database.db"
FORMAL19 = {"AP.CZCE", "CF.CZCE", "FG.CZCE", "MA.CZCE", "OI.CZCE", "SA.CZCE", "SH.CZCE", "SM.CZCE",
    "jm.DCE", "lh.DCE", "lc.GFEX", "si.GFEX", "au.SHFE", "cu.SHFE", "fu.SHFE", "hc.SHFE", "rb.SHFE", "ru.SHFE", "sp.SHFE"}
EXPECTED = {
    str(PROTOCOL): "c03bb81752babd24b5adf28784530c3679b1260e1a52cea50db108aea50587d5",
    str(COVERAGE / "summary.json"): "d4edaf2926d9cd227afaba623201d2df3bd01c2b50eda33b3025d76702ba24f9",
    str(REVIEW): "2e0edc2d64b77e2821f7427646ed457cded0d0a1da90be73de5f2d928ec25984",
    str(WEEKLY): "d8bae99069a24195975aac62fd47a1cfbdf5f024f15861a6772e424faf6c5f8e",
    str(PROJECT / "qmt_roll_portfolio_strategy.py"): "6d6aa534715200c40a5743697114f73080111d609b29980d924dcb1d362792e9",
}
_RUNTIME = None


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024*1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path, payload):
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False)+"\n")


def load_runtime():
    global _RUNTIME
    if _RUNTIME is not None:
        return _RUNTIME
    for name in ("numpy", "pandas", "scipy", "sklearn", "joblib"):
        item = sys.modules.get(name)
        if item is not None and not Path(item.__file__).resolve().is_relative_to(FROZEN_SITE):
            raise RuntimeError(f"wrong_preimported_runtime:{name}")
    sys.path[:0] = [str(ROOT), str(VENDOR), str(PROJECT), str(FROZEN_SITE)]
    os.environ["TZ"] = "Asia/Shanghai"
    if hasattr(time, "tzset"):
        time.tzset()
    import numpy as np
    import pandas as pd
    from vnpy.trader.utility import ArrayManager
    from vnpy.trader.object import BarData
    from vnpy.trader.constant import Exchange, Interval
    from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy
    from qmt_roll_intraday_execution import session_minutes
    _RUNTIME = dict(np=np, pd=pd, ArrayManager=ArrayManager, BarData=BarData,
        Exchange=Exchange, Interval=Interval, Strategy=QmtRollPortfolioStrategy, session_minutes=session_minutes)
    return _RUNTIME


def make_indicator_object(actual_settings):
    """Allocate a method container only. Never invoke any strategy __init__."""
    strategy = load_runtime()["Strategy"].__new__(load_runtime()["Strategy"])
    for key, value in actual_settings.items():
        setattr(strategy, key, value)
    if hasattr(strategy, "strategy_engine") or hasattr(strategy, "states"):
        raise ValueError("unexpected_account_initialized")
    return strategy


def weekly_allows(signal, ready, direction):
    if not ready:
        return True
    return int(direction) == (1 if str(signal).startswith("long") else -1)


def enumerate_signals(daily, mapping, metadata, strategy, *, start, end, weekly=None, progress=None):
    """Consume each real bar once, return all pure initial alpha events.

    The global engine calendar is the union of metadata-contract real bar
    datetimes. Mapping-calendar dates are deliberately not inserted here.
    """
    runtime = load_runtime()
    pd, np = runtime["pd"], runtime["np"]
    frame = daily.copy()
    frame["datetime"] = pd.to_datetime(frame.datetime, errors="raise")
    if frame.datetime.dt.tz is not None:
        frame["datetime"] = frame.datetime.dt.tz_convert("Asia/Shanghai").dt.tz_localize(None)
    if frame.duplicated(["vt_symbol", "datetime"]).any():
        raise ValueError("duplicate real daily contract key")
    symbols = set(metadata)
    if not frame.vt_symbol.isin(symbols).all():
        raise ValueError("daily contains contracts outside fixed metadata")
    size = int(strategy.research_exact_array_manager_size)
    if size != 41:
        raise ValueError("not_frozen_am41")
    managers = {symbol: runtime["ArrayManager"](size) for symbol in sorted(symbols)}
    dates = pd.DatetimeIndex(sorted(frame.datetime.unique()))
    next_dates = {day: dates[i+1] if i+1 < len(dates) else None for i, day in enumerate(dates)}
    reasons = Counter()
    output = []
    start_date, end_date = pd.Timestamp(start), pd.Timestamp(end)
    for batch_index, (day, bars) in enumerate(frame.sort_values(["datetime", "vt_symbol"]).groupby("datetime", sort=True)):
        actual_symbols = set(bars.vt_symbol)
        for row in bars.itertuples(index=False):
            symbol, exchange = row.vt_symbol.rsplit(".", 1)
            bar = runtime["BarData"](symbol=symbol, exchange=runtime["Exchange"](exchange),
                datetime=day.to_pydatetime(), interval=runtime["Interval"].DAILY, gateway_name="DB",
                open_price=float(row.open_price), high_price=float(row.high_price), low_price=float(row.low_price),
                close_price=float(row.close_price), volume=float(row.volume), turnover=float(row.turnover),
                open_interest=float(row.open_interest))
            managers[row.vt_symbol].update_bar(bar)
        if day < start_date or day > end_date:
            continue
        day_text = day.strftime("%Y-%m-%d")
        for product, target in sorted(mapping.get(day_text, {}).items()):
            if not target:
                reasons["target_mapping_missing"] += 1
                continue
            if target not in managers:
                raise ValueError(f"mapping_target_outside_metadata:{target}")
            if target not in actual_symbols:
                reasons["target_real_bar_missing"] += 1
                continue
            manager = managers[target]
            if not manager.inited:
                reasons["target_am_warmup"] += 1
                continue
            history = strategy._build_history_df(manager)
            signal_data = strategy._generate_signal(manager, history)
            signal = str(signal_data["signal"])
            if not signal.startswith(("long", "short")):
                reasons["no_alpha_signal"] += 1
                continue
            next_day = next_dates[day]
            code, exchange = product.rsplit(".", 1)
            feature = weekly.get(day_text, f"{exchange}.{code}".upper()) if weekly is not None else dict(
                ready=False, direction=0, weekly_asof="", reason="not_supplied_test_only")
            output.append(dict(signal_date=day_text, product_vt_symbol=product, vt_symbol=target, signal=signal,
                risk_mode=str(signal_data.get("risk_mode", "")), am_count=int(manager.count),
                history_first_close=float(history.close.iloc[0]), history_last_close=float(history.close.iloc[-1]),
                execution_trade_date=next_day.strftime("%Y-%m-%d") if next_day is not None else "",
                event_status="potential_initial_signal" if next_day is not None else "terminal_pending",
                weekly_ready=bool(feature["ready"]), weekly_direction=int(feature["direction"]),
                weekly_asof=str(feature["weekly_asof"]), weekly_reason=str(feature["reason"]),
                c0_allowed=weekly_allows(signal, feature["ready"], feature["direction"])))
            reasons["raw_alpha_event"] += 1
        if progress is not None and batch_index % 250 == 0:
            progress(batch_index+1, len(dates), day_text, len(output))
    columns = ["signal_date", "product_vt_symbol", "vt_symbol", "signal", "risk_mode", "am_count",
        "history_first_close", "history_last_close", "execution_trade_date", "event_status", "weekly_ready",
        "weekly_direction", "weekly_asof", "weekly_reason", "c0_allowed"]
    return pd.DataFrame(output, columns=columns), dict(global_engine_batches=len(dates),
        first_global_batch=str(dates.min()), last_global_batch=str(dates.max()),
        global_calendar_sha256=hashlib.sha256(np.array(dates.astype("int64")).tobytes()).hexdigest(),
        real_daily_rows=len(frame), reasons=dict(reasons), am_final_counts={k: int(v.count) for k, v in managers.items()})


def join_session_coverage(events, coverage, calendar):
    """Reuse accepted Stage004 exact timestamp counts; never reindex raw minute prices."""
    runtime = load_runtime()
    pd = runtime["pd"]
    demand = events.loc[events.execution_trade_date.ne("")].copy()
    keys = ["vt_symbol", "execution_trade_date"]
    demand = demand.groupby(keys, as_index=False).agg(product_vt_symbol=("product_vt_symbol", "first"),
        raw_events=("c0_allowed", "size"), c0_events=("c0_allowed", "sum"))
    cached = coverage.copy().rename(columns={"date": "execution_trade_date"})
    cached["execution_trade_date"] = pd.to_datetime(cached.execution_trade_date).dt.strftime("%Y-%m-%d")
    if cached.duplicated(keys).any():
        raise ValueError("duplicate coverage cache session key")
    joined = demand.merge(cached, on=keys, how="left", validate="one_to_one", indicator=True,
        suffixes=("", "_coverage"))
    if not joined._merge.eq("both").all():
        raise ValueError("coverage_join_missing")
    starts, finishes = [], []
    for row in joined.itertuples(index=False):
        grid = runtime["session_minutes"](row.vt_symbol, row.execution_trade_date, calendar)
        if len(grid) != int(row.expected_minutes):
            raise ValueError(f"cached_session_count_disagrees:{row.vt_symbol}:{row.execution_trade_date}")
        starts.append(grid[0].isoformat())
        finishes.append((grid[-1]+pd.Timedelta(minutes=1)).isoformat())
    joined["session_start"] = starts
    joined["session_end_exclusive"] = finishes
    return joined.drop(columns="_merge")


def known_subset_check(events, known):
    required = ["date", "product_vt_symbol", "contract_vt_symbol", "signal"]
    candidate = known[required].rename(columns={"date": "signal_date", "contract_vt_symbol": "vt_symbol"})
    columns = ["signal_date", "product_vt_symbol", "vt_symbol", "signal"]
    keys = set(events[columns].itertuples(index=False, name=None))
    missing = [dict(zip(columns, row)) for row in candidate[columns].itertuples(index=False, name=None) if row not in keys]
    if missing:
        raise ValueError(f"known_A0_initial_signals_missing:{missing[:5]}")
    return dict(known_rows=len(candidate), matched_rows=len(candidate), missing_rows=0,
        fields_read=required, outcome_fields_read=0, meaning="necessary subset sentinel only, not complete-path proof")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enumerate", action="store_true", required=True)
    parser.parse_args()
    if OUTPUT.exists():
        raise FileExistsError("existing_enumeration_attempt_refusing_repeat")
    # Pin current provenance before importing the original strategy functions.
    checked = {}
    for path, expected in EXPECTED.items():
        checked[path] = sha256(path)
        if checked[path] != expected:
            raise ValueError(f"frozen_input_changed:{path}")
    cache_summary = json.loads((COVERAGE/"summary.json").read_text())
    cache_inputs = json.loads((COVERAGE/"input_manifest.json").read_text())
    review = json.loads(REVIEW.read_text())
    if not cache_summary["all_inputs_unchanged"] or review.get("p0_findings") != 0 or review.get("p1_findings") != 0:
        raise ValueError("coverage_prior_qualification_failed")
    for filename in ("input_manifest.json", "session_coverage.csv.gz", "local_source_candidates.csv"):
        path = COVERAGE/filename
        checked[str(path)] = sha256(path)
        if checked[str(path)] != cache_summary["artifact_sha256"][filename]:
            raise ValueError(f"coverage_artifact_changed:{filename}")
    actual = json.loads((A0/"actual_strategy_settings.json").read_text())[0]["actual"]
    mapping_path = Path(actual["mapping_csv_path"])
    for path in (DATABASE, mapping_path, A0/"actual_strategy_settings.json", A0/"effective_parameters.json"):
        checked[str(path)] = sha256(path)
        if checked[str(path)] != cache_inputs[str(path)]:
            raise ValueError(f"source_changed_since_stage004:{path}")
    # Large minute files are not reopened: bind inherited counts to the frozen input manifest.
    for path, expected in cache_inputs.items():
        if path.endswith("qmt_roll_intraday_execution.py"):
            checked[path] = sha256(path)
            if checked[path] != expected:
                raise ValueError("session_helper_changed_since_coverage")
    if actual["research_exact_array_manager_size"] != 41 or actual["warmup_days"] != 90 or actual["trade_start_date"] != "2020-01-01":
        raise ValueError("frozen_indicator_settings_changed")
    OUTPUT.mkdir(parents=True, exist_ok=False)
    started = datetime.now().astimezone().isoformat(timespec="seconds")
    write_json(OUTPUT/"attempt_started.json", dict(started_at=started, financial_attempts=0, downloads=0, model_fits=0))
    try:
        runtime = load_runtime()
        pd, np = runtime["pd"], runtime["np"]
        import inspect
        from main_contract_mapping import build_daily_mapping, load_product_universe_symbols
        from stage001_run_first_screen import WeeklyLookup
        import vnpy.trader.utility as utility
        metadata = sorted(json.loads((A0/"effective_parameters.json").read_text())["contract_sizes"])
        supported = load_product_universe_symbols(actual["product_universe_csv_path"])
        if set(supported) != FORMAL19:
            raise ValueError("formal19_universe_changed")
        mapping = build_daily_mapping(mapping_path, supported_symbols=supported)
        mapping_calendar = pd.DatetimeIndex(sorted(pd.Timestamp(day) for day in mapping))
        with sqlite3.connect(DATABASE.resolve().as_uri()+"?mode=ro", uri=True) as db:
            db.execute("PRAGMA query_only=ON")
            daily = pd.read_sql_query("SELECT symbol||'.'||exchange AS vt_symbol,datetime,open_price,high_price,low_price,close_price,volume,turnover,open_interest FROM dbbardata WHERE interval='d' AND datetime >= '2019-06-01 00:00:00' AND datetime <= '2026-10-14 00:00:00'", db)
        daily = daily.loc[daily.vt_symbol.isin(metadata)].copy()
        for path in (Path(__file__), Path(__file__).with_name("test_stage005_potential_signal_demand.py"),
                     Path(inspect.getfile(runtime["Strategy"])), Path(utility.__file__),
                     Path(actual["product_universe_csv_path"]), A0/"entry_candidates.csv"):
            checked[str(path)] = sha256(path)
        strategy = make_indicator_object(actual)
        weekly = WeeklyLookup.read(WEEKLY)
        events, diagnostics = enumerate_signals(daily, mapping, metadata, strategy,
            start="2020-01-01", end="2026-10-14", weekly=weekly,
            progress=lambda done,total,day,count: print(f"indicator batches {done}/{total}, date={day}, raw events={count}", flush=True))
        events.to_csv(OUTPUT/"potential_initial_events.csv", index=False)
        events.loc[events.c0_allowed].to_csv(OUTPUT/"c0_potential_initial_events.csv", index=False)
        known = pd.read_csv(A0/"entry_candidates.csv", usecols=["date", "product_vt_symbol", "contract_vt_symbol", "signal"])
        subset = known_subset_check(events, known)
        write_json(OUTPUT/"known_A0_subset_check.json", subset)
        coverage_columns = ["vt_symbol", "date", "expected_minutes", "available_minutes", "missing_minutes", "anchor_present", "complete", "local_candidate_paths"]
        coverage = pd.read_csv(COVERAGE/"session_coverage.csv.gz", usecols=coverage_columns)
        sessions = join_session_coverage(events, coverage, mapping_calendar)
        sessions.to_csv(OUTPUT/"initial_session_demand.csv", index=False)
        sessions.loc[sessions.missing_minutes.gt(0)].to_csv(OUTPUT/"initial_session_gaps.csv", index=False)
        inventory = pd.read_csv(COVERAGE/"local_source_candidates.csv")
        gap_symbols = set(sessions.loc[sessions.missing_minutes.gt(0), "vt_symbol"])
        inventory.loc[inventory.vt_symbol.isin(gap_symbols)].to_csv(OUTPUT/"gap_local_candidate_paths.csv", index=False)
        sessions["year"] = pd.to_datetime(sessions.execution_trade_date).dt.year
        reports = []
        for name, subset_sessions in (("raw_initial_upper", sessions), ("c0_initial_upper", sessions.loc[sessions.c0_events.gt(0)])):
            for keys, file in ((["year"], "year"), (["product_vt_symbol", "year"], "product_year")):
                report = subset_sessions.groupby(keys, as_index=False).agg(sessions=("vt_symbol", "size"),
                    complete_sessions=("complete", "sum"), missing_minutes=("missing_minutes", "sum"),
                    anchor_present=("anchor_present", "sum"), potential_events=("raw_events" if name.startswith("raw") else "c0_events", "sum"))
                report["scope"] = name
                reports.append((file, report))
        for file in ("year", "product_year"):
            pd.concat([f for name,f in reports if name == file], ignore_index=True).to_csv(OUTPUT/f"{file}_coverage.csv", index=False)
        (OUTPUT/"global_engine_calendar.csv").write_text("date\n"+"\n".join(pd.to_datetime(sorted(daily.datetime.unique())).strftime("%Y-%m-%d"))+"\n")
        unchanged = all(sha256(path) == digest for path, digest in checked.items())
        if not unchanged:
            raise ValueError("consumed_inputs_changed_during_enumeration")
        write_json(OUTPUT/"input_manifest.json", checked)
        summary = dict(status="completed_zero_account_initial_signal_demand_pending_independent_review", started_at=started,
            completed_at=datetime.now().astimezone().isoformat(timespec="seconds"), protocol_sha256=checked[str(PROTOCOL)],
            financial_attempts=0, downloads=0, model_fits=0, strategy_initializations=0, account_engines=0,
            order_api_calls=0, cancel_api_calls=0, outcome_fields_read=0, source_writes=0,
            preload_start="2019-06-01", trade_start="2020-01-01", end="2026-10-14", warmup_days=90, am_size=41,
            warmup_semantics="metadata real-bar batches continuously update AMs; warmup/trading split never resets AMs; pretrade signals discarded",
            raw_events=len(events), c0_allowed_events=int(events.c0_allowed.sum()), weekly_unknown_events=int((~events.weekly_ready).sum()),
            terminal_pending_events=int(events.event_status.eq("terminal_pending").sum()),
            raw_required_sessions=len(sessions), raw_complete_sessions=int(sessions.complete.sum()),
            raw_missing_sessions=int(sessions.missing_minutes.gt(0).sum()), raw_missing_minutes=int(sessions.missing_minutes.sum()),
            c0_required_sessions=int(sessions.c0_events.gt(0).sum()),
            c0_missing_sessions=int((sessions.c0_events.gt(0)&sessions.missing_minutes.gt(0)).sum()),
            c0_missing_minutes=int(sessions.loc[sessions.c0_events.gt(0),"missing_minutes"].sum()),
            known_A0_subset=subset, diagnostics=diagnostics, all_inputs_unchanged=unchanged,
            coverage_scope="exact pure-alpha initial-event upper bound; not actual fills or exit/add/rollover coverage",
            coverage_inheritance="Stage004 frozen timestamp counts plus limited semantic and 8-session independent sample review; not full independent recertification",
            inherited_base_overlay_binding=cache_inputs,
            production_qualified=False, financial_metrics="N/A", candidate_file_contents_read=0,
            runtime=dict(python=sys.executable, numpy=np.__version__, pandas=pd.__version__,
                numpy_path=np.__file__, pandas_path=pd.__file__, strategy_path=inspect.getfile(runtime["Strategy"]),
                array_manager_path=utility.__file__),
            artifacts={p.name:sha256(p) for p in OUTPUT.iterdir() if p.is_file()})
        write_json(OUTPUT/"summary.json", summary)
        print(json.dumps({k:summary[k] for k in ("status","raw_events","c0_allowed_events","raw_required_sessions","raw_complete_sessions","raw_missing_sessions","c0_required_sessions","c0_missing_sessions")},ensure_ascii=False),flush=True)
    except Exception as error:
        write_json(OUTPUT/"failure_receipt.json", dict(status="failed_no_automatic_repeat", error=repr(error),
            failed_at=datetime.now().astimezone().isoformat(timespec="seconds"), financial_attempts=0, downloads=0,
            partial_outputs_not_completed_demand=True))
        raise


if __name__ == "__main__":
    main()
