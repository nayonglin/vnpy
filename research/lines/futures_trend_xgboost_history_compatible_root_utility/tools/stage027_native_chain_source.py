from __future__ import annotations

import importlib.util
import json
import signal
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("chain_base027", ROOT / "tools/stage024_contract_catalog.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
OUTPUT = ROOT / "artifacts/stage027_native_chain_source"
CATALOG = ROOT / "artifacts/stage026_sdk_cache_catalog"
CONTRACT = ROOT / "stages/20260906_0633_stage027_native_chain_source_contract.md"
FIELDS = ["id", "datetime", "open", "high", "low", "close", "volume", "open_oi", "close_oi"]


def normalise(raw, symbol, expiry):
    frame = raw[FIELDS].copy().apply(pd.to_numeric, errors="raise")
    ids = frame.id.to_numpy(float)
    if not np.isfinite(ids).all() or not (ids == np.floor(ids)).all():
        raise ValueError("invalid_serial_id")
    stats = dict(raw_rows=len(frame), padding_rows=int(frame.id.lt(0).sum()))
    frame = frame[frame.id.ge(0)].copy()
    if not np.isfinite(frame.datetime).all() or frame.datetime.le(0).any():
        raise ValueError("invalid_real_timestamp")
    days = pd.to_datetime(frame.datetime, unit="ns", utc=True, errors="raise").dt.tz_convert(
        "Asia/Shanghai").dt.tz_localize(None).dt.normalize()
    end = min(base.CUTOFF, pd.Timestamp(expiry).normalize())
    if days.gt(end).any():
        raise ValueError("bar_after_expiry_or_cutoff")
    stats["before_start_rows"] = int(days.lt(base.START).sum())
    frame["trade_date"] = days.dt.strftime("%Y-%m-%d")
    frame = frame[days.ge(base.START)].copy()
    if frame.trade_date.duplicated().any():
        raise ValueError("duplicate_trade_date")
    values = frame[FIELDS[2:]].to_numpy(float)
    if not np.isfinite(values).all():
        raise ValueError("nonfinite_real_bar")
    if frame[["open", "high", "low", "close"]].le(0).any().any():
        raise ValueError("nonpositive_price")
    if frame[["volume", "open_oi", "close_oi"]].lt(0).any().any():
        raise ValueError("negative_volume_or_oi")
    if (frame.high.lt(frame[["open", "close", "low"]].max(axis=1)).any()
            or frame.low.gt(frame[["open", "close", "high"]].min(axis=1)).any()):
        raise ValueError("inconsistent_ohlc")
    frame["tq_symbol"] = symbol
    frame = frame[["tq_symbol", "trade_date"] + FIELDS].sort_values("trade_date").reset_index(drop=True)
    stats.update(status="daily_rows_returned_not_chain_qualified" if len(frame) else "empty_unqualified",
        rows=len(frame), first_date=frame.trade_date.iloc[0] if len(frame) else None,
        last_date=frame.trade_date.iloc[-1] if len(frame) else None)
    return frame, stats


def plan_batches(symbols, probe):
    if (not probe or len(set(symbols)) != len(symbols) or len(set(probe)) != len(probe)
            or not set(probe).issubset(symbols)):
        raise ValueError("invalid_probe_inventory")
    rest = sorted(set(symbols) - set(probe))
    return [sorted(probe)] + [rest[i:i + 40] for i in range(0, len(rest), 40)]


def fetch_batch(symbols, path, expiry, credentials):
    from tqsdk import BacktestFinished, TqApi, TqAuth, TqBacktest, TqSim

    receipt = dict(status="running", symbols=symbols, started_at=datetime.now().astimezone().isoformat(),
                   step="connect", contracts=[])
    api = None
    try:
        signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError("batch_timeout")))
        signal.alarm(300)
        api = TqApi(TqSim(), backtest=TqBacktest(start_dt=base.CUTOFF.date(), end_dt=base.CUTOFF.date()),
                    auth=TqAuth(*credentials), debug=False, disable_print=True)
        receipt["step"] = "subscribe"
        serials = {s: api.get_kline_serial(s, duration_seconds=86400, data_length=10000) for s in symbols}
        receipt["step"] = "finish_history_day"
        try:
            while True:
                api.wait_update()
        except BacktestFinished:
            pass
        frames = {s: serials[s][FIELDS].copy(deep=True) for s in symbols}
        receipt["step"] = "save_raw"
        for symbol, frame in frames.items():
            frame.to_csv(path / f"{symbol}.raw.csv.gz", index=False)
        receipt["step"] = "normalise"
        for symbol, frame in frames.items():
            data, stats = normalise(frame, symbol, expiry[symbol])
            data.to_csv(path / f"{symbol}.daily.csv.gz", index=False)
            receipt["contracts"].append(dict(tq_symbol=symbol, **stats))
        receipt.update(status="batch_complete", step="complete")
    except Exception as exc:
        message = str(exc)
        for secret in credentials:
            if secret:
                message = message.replace(secret, "[REDACTED]")
        receipt.update(status="batch_failed_stop", error_type=type(exc).__name__, error=message[:2000])
    finally:
        signal.alarm(0)
        if api is not None:
            try:
                api.close()
            except Exception as exc:
                receipt.update(status="batch_failed_stop", close_error_type=type(exc).__name__)
        receipt["finished_at"] = datetime.now().astimezone().isoformat()
        receipt["outputs"] = {p.name: base.identity(p) for p in sorted(path.iterdir())}
        base.save(path / "receipt.json", receipt)
    return receipt


def run():
    from vnpy.trader.setting import SETTINGS

    expected = "71ac2c4ce8ea527fd51f60b940d789c78ec5ca7afca286428e95dc32a55918db"
    if base.identity(CATALOG / "summary.json")["sha256"] != expected:
        raise RuntimeError("catalog_summary_changed")
    catalog_report = json.loads((CATALOG / "summary.json").read_text())
    for value in catalog_report["outputs"].values():
        if base.identity(value["path"]) != value:
            raise RuntimeError("catalog_output_changed")
    catalog = pd.read_csv(CATALOG / "catalog.csv.gz")
    symbols = catalog.tq_symbol.tolist()
    missing = json.loads((base.OUTPUT / "summary.json").read_text())["missing_event_contracts"]
    probe = [f'{s.split(".")[1]}.{s.split(".")[0]}' for s in missing]
    if (len(symbols), len(probe)) != (1325, 13):
        raise RuntimeError("source_inventory_changed")
    batches = plan_batches(symbols, probe)
    files = [CATALOG / "summary.json", CATALOG / "catalog.csv.gz", base.OUTPUT / "summary.json",
        CONTRACT, Path(__file__), ROOT / "tests/test_stage027_native_chain_source.py",
        ROOT / "tools/stage024_contract_catalog.py",
        base.WORKSPACE / ".py311/lib/python3.11/site-packages/tqsdk/api.py",
        base.WORKSPACE / ".py311/lib/python3.11/site-packages/tqsdk/expired_quotes.json.lzma"]
    inputs = {str(p): base.identity(p) for p in files}
    if OUTPUT.exists():
        if json.loads((OUTPUT / "input_manifest.json").read_text()) != inputs:
            raise RuntimeError("resume_inputs_changed")
    else:
        OUTPUT.mkdir(parents=True)
        base.save(OUTPUT / "input_manifest.json", inputs)
        base.save(OUTPUT / "acquisition_plan.json", batches)
    if json.loads((OUTPUT / "acquisition_plan.json").read_text()) != batches:
        raise RuntimeError("resume_plan_changed")
    credentials = tuple(str(SETTINGS.get(k) or "") for k in ("datafeed.username", "datafeed.password"))
    if not all(credentials):
        raise RuntimeError("source_credentials_missing")
    expiry = dict(zip(catalog.tq_symbol, catalog.expire_date, strict=True))
    report = dict(status="running", started_at=datetime.now().astimezone().isoformat(),
        source_start=str(base.START.date()), cutoff=str(base.CUTOFF.date()),
        planned_contracts=len(symbols), planned_batches=len(batches), completed_batches=0,
        strategy_backtest_count=0, model_fit_predict_count=0, label_read_count=0,
        reviewer_count=0, production_write_count=0, full_chain_qualified=False, historical_vintage_proven=False)
    records = []
    try:
        for index, batch in enumerate(batches):
            path = OUTPUT / f"batch_{index:03d}"
            if path.exists():
                receipt = json.loads((path / "receipt.json").read_text())
                for value in receipt["outputs"].values():
                    if base.identity(value["path"]) != value:
                        raise RuntimeError("resume_batch_output_changed")
                if receipt["symbols"] != batch:
                    raise RuntimeError("resume_batch_symbols_changed")
            else:
                path.mkdir()
                receipt = fetch_batch(batch, path, expiry, credentials)
            if receipt["status"] != "batch_complete":
                report.update(failed_batch=index, failed_step=receipt["step"], error_type=receipt.get("error_type"))
                raise RuntimeError("source_batch_failed_no_retry")
            records.extend(receipt["contracts"])
            report["completed_batches"] += 1
            if index == 0 and any(not r["rows"] for r in records):
                raise RuntimeError("early_probe_empty_stop_no_expansion")
            print(f"native chain {len(records)}/{len(symbols)}, batch {index + 1}/{len(batches)}", flush=True)
            base.save(OUTPUT / "summary.json", report)
        report["status"] = "acquired_pending_chain_qualification"
        if inputs != {str(p): base.identity(p) for p in files}:
            raise RuntimeError("source_inputs_changed")
        report["inputs_unchanged"] = True
    except Exception as exc:
        report.update(status="acquisition_stopped", run_error=str(exc))
        raise
    finally:
        pd.DataFrame(records).to_csv(OUTPUT / "contract_status.csv", index=False)
        report.update(finished_at=datetime.now().astimezone().isoformat(), acquired_contracts=len(records),
            total_rows=sum(r["rows"] for r in records),
            empty_contracts=[r["tq_symbol"] for r in records if not r["rows"]])
        report["outputs"] = {str(p.relative_to(OUTPUT)): base.identity(p)
            for p in sorted(OUTPUT.rglob("*")) if p.is_file() and p != OUTPUT / "summary.json"}
        base.save(OUTPUT / "summary.json", report)
    print(json.dumps({k: v for k, v in report.items() if k != "outputs"}), flush=True)


if __name__ == "__main__":
    run()
