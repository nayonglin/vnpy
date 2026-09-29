"""Extended stock-only history, separate from the immutable v1 download.

Run with absolute Python -I from this package. No credentials or shared vn.py
configuration are consulted. Price limits remain derived, not exchange fields.
"""
from __future__ import annotations

import json
import hashlib
import fcntl
import math
import re
import signal
import shutil
import socket
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import pandas as pd

from .baostock_download import collect_response, snapshot_dates, validate_components, membership_flags, audit_limits

ROOT = Path(__file__).resolve().parent
DOWNLOADS_DIR = ROOT / "data" / "downloads"


def year_segments(start, end):
    first, last = pd.Timestamp(start), pd.Timestamp(end)
    if first > last or pd.isna(first) or pd.isna(last):
        raise ValueError("Invalid date interval")
    return [(max(first, pd.Timestamp(year, 1, 1)).strftime("%Y-%m-%d"),
             min(last, pd.Timestamp(year, 12, 31)).strftime("%Y-%m-%d"))
            for year in range(first.year, last.year + 1)]


def _safe(path):
    path = Path(path)
    root = DOWNLOADS_DIR.absolute()
    if not path.absolute().is_relative_to(root):
        raise ValueError("History output must remain in stock DOWNLOADS_DIR")
    current = path.absolute()
    while current != root.parent.parent:
        if current.is_symlink():
            raise ValueError("History paths must not be symlinks")
        current = current.parent
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("History output path escapes data directory")
    return path


def _write_json(path, value):
    path = _safe(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _begin_attempt(directory):
    """Keep past errors as evidence while distinguishing the current attempt."""
    attempt_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    errors = _safe(directory / "download_errors.json")
    if errors.exists():
        previous = json.loads(errors.read_text(encoding="utf-8"))
        if not isinstance(previous, list):
            raise ValueError("Invalid previous download error report")
        if previous:
            archive = _safe(directory / f"download_errors_{attempt_id}.json")
            if archive.exists():
                raise FileExistsError("Never replace an attempt error archive")
            shutil.copyfile(errors, archive)
    reports = sorted(_safe(path).name for path in directory.glob("download_errors_*.json"))
    _write_json(errors, [])
    return dict(attempt_id=attempt_id, current_failures=[], historical_failure_reports=reports)


@contextmanager
def _deadline(seconds):
    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.getitimer(signal.ITIMER_REAL)
    def expired(*_):
        raise TimeoutError("BaoStock request deadline exceeded")
    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, *previous_timer)
        signal.signal(signal.SIGALRM, previous_handler)


def normalize_stock(raw, factors, events):
    if raw.empty:
        raise ValueError("No bars for a historical constituent")
    frame = raw.copy()
    for column in ("tradestatus", "isST"):
        if not frame[column].astype(str).isin(["0", "1"]).all():
            raise ValueError(f"Unknown historical {column}")
    suspended = frame.tradestatus.astype(str).eq("0")
    empty_volume = frame.volume.isna() | frame.volume.astype(str).str.strip().eq("")
    frame.loc[suspended & empty_volume, "volume"] = "0"
    frame["date"] = pd.to_datetime(frame["date"], errors="raise")
    if frame.date.isna().any() or frame.date.duplicated().any() or not frame.date.eq(frame.date.dt.normalize()).all():
        raise ValueError("Bars must have unique daily dates")
    if frame.code.nunique() != 1 or not frame.code.astype(str).str.fullmatch(r"(?:sh|sz)\.\d{6}").all():
        raise ValueError("Expected one SSE/SZSE stock")
    for column in ("open", "high", "low", "close", "preclose", "volume"):
        frame[column] = pd.to_numeric(frame[column], errors="raise").astype(float)
        if not frame[column].map(math.isfinite).all():
            raise ValueError(f"Nonfinite {column}")
    if (frame[["open", "high", "low", "close", "preclose"]] <= 0).any().any() or (frame.volume < 0).any():
        raise ValueError("Invalid price or volume")
    if (suspended & frame.volume.gt(0)).any():
        raise ValueError("Positive volume conflicts with suspended trading status")
    code = frame.code.iloc[0]
    frame["vt_symbol"] = code[3:] + (".SSE" if code.startswith("sh.") else ".SZSE")
    frame["is_st"] = frame.isST.astype(str).eq("1")
    frame["is_member"] = False
    ratio = pd.Series(.10, index=frame.index)
    ratio = ratio.mask(frame.is_st & (frame.date < pd.Timestamp("2026-07-06")), .05)
    if code.startswith("sz.3"):
        ratio = ratio.mask(frame.date >= pd.Timestamp("2020-08-24"), .20)
    elif code.startswith("sh.688"):
        ratio[:] = .20
    for column, sign in (("limit_up", 1), ("limit_down", -1)):
        frame[column] = [float((Decimal(str(ref)) * (Decimal(1) + sign * Decimal(str(rate)))).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)) for ref, rate in zip(frame.preclose, ratio)]
    frame = frame.sort_values("date")
    frame["adj_factor"] = 1.
    if not factors.empty:
        factor = factors[["dividOperateDate", "backAdjustFactor"]].copy()
        factor["date"] = pd.to_datetime(factor.pop("dividOperateDate"), errors="raise")
        factor["adj_factor"] = pd.to_numeric(factor.pop("backAdjustFactor"), errors="raise")
        if factor.date.isna().any() or factor.date.duplicated().any() or not factor.adj_factor.map(math.isfinite).all() or (factor.adj_factor <= 0).any():
            raise ValueError("Invalid or duplicate factor event")
        frame = pd.merge_asof(frame.drop(columns="adj_factor"), factor.sort_values("date"), on="date", direction="backward")
        frame["adj_factor"] = frame.adj_factor.fillna(1.)
    frame["cash_dividend"], frame["split_ratio"] = 0., 1.
    if not events.empty:
        event = events[["date", "cash_dividend", "split_ratio"]].copy()
        event["date"] = pd.to_datetime(event.date)
        if event.date.duplicated().any():
            raise ValueError("Duplicate merged corporate actions")
        frame = frame.drop(columns=["cash_dividend", "split_ratio"]).merge(event, on="date", how="left", validate="one_to_one")
        frame["cash_dividend"] = frame.cash_dividend.fillna(0.)
        frame["split_ratio"] = frame.split_ratio.fillna(1.)
    return frame[["date", "vt_symbol", "open", "high", "low", "close", "volume", "adj_factor", "limit_up", "limit_down", "is_st", "is_member", "cash_dividend", "split_ratio"]]


def fetch_cached(path, method, *, attempts=3, timeout=20, **kwargs):
    path = _safe(path)
    if path.exists():
        return pd.read_parquet(path)
    if attempts < 1:
        raise ValueError("At least one request attempt is required")
    result = None
    for attempt in range(attempts):
        try:
            with _deadline(timeout):
                result = collect_response(method(**kwargs))
            break
        except (OSError, RuntimeError) as exc:
            if attempt + 1 == attempts:
                raise RuntimeError(f"Request failed after {attempts} attempts: {exc}") from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    result.to_parquet(path, index=False)
    return result


def collect_membership(start, end, client):
    start_date, end_date = pd.Timestamp(start).strftime("%Y-%m-%d"), pd.Timestamp(end).strftime("%Y-%m-%d")
    dates = snapshot_dates(start_date, end_date)
    directory = _safe(DOWNLOADS_DIR / f"history_{start_date.replace('-', '')}_{end_date.replace('-', '')}")
    if _safe(directory / "source_panel.parquet").exists():
        raise FileExistsError("Complete or partially published history source already exists; never overwrite")
    parts = []
    for date in dates:
        part = fetch_cached(directory / "raw" / f"hs300_{date}.parquet", client.query_hs300_stocks, date=date)
        validate_components(part, date)
        parts.append(part.assign(snapshot_date=date))
    membership = pd.concat(parts, ignore_index=True)
    membership.to_parquet(_safe(directory / "historical_components.parquet"), index=False)
    symbols = sorted(code for code in membership.code.unique() if not code[3:].startswith(("300", "688")))
    status = dict(state="membership_ready", provider="baostock+sina", requested_start=start_date, requested_end=end_date, snapshots=len(parts), historical_union_stocks=len(symbols), symbols=symbols)
    _write_json(directory / "download_manifest.json", status)
    print(f"[history] membership_ready snapshots={len(parts)} stocks={len(symbols)} directory={directory}", flush=True)
    return directory, membership, symbols


def audit_factor_gaps(panel):
    stocks = panel.loc[panel.vt_symbol != "000300.SSE"].sort_values(["vt_symbol", "date"]).copy()
    stocks["previous_factor"] = stocks.groupby("vt_symbol").adj_factor.shift()
    changed = stocks.previous_factor.notna() & ~stocks.adj_factor.combine(stocks.previous_factor, lambda a, b: math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-12))
    return stocks.loc[changed & stocks.cash_dividend.eq(0) & stocks.split_ratio.eq(1)].copy()


@contextmanager
def stock_lock(directory, code, timeout=90):
    if not re.fullmatch(r"(?:sh|sz)\.\d{6}", code) or timeout <= 0:
        raise ValueError("Invalid stock lock request")
    path = _safe(Path(directory) / ".locks" / f"{code}.lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    with path.open("a") as handle:
        while True:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() - start >= timeout:
                    raise TimeoutError(f"Stock lock timeout: {code}")
                time.sleep(min(.05, timeout))
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def fetch_stock_raw(directory, code, start, end, client):
    """Both primary and prefetch workers must hold this same process lock."""
    from .corporate_actions import fetch_sina_actions
    with stock_lock(directory, code):
        raw_dir = _safe(Path(directory) / "raw")
        parts = [fetch_cached(raw_dir / f"bars_{code}_{lo}_{hi}.parquet", client.query_history_k_data_plus,
                              code=code, fields="date,code,open,high,low,close,preclose,volume,tradestatus,isST",
                              start_date=lo, end_date=hi, frequency="d", adjustflag="3")
                 for lo, hi in year_segments(start, end)]
        raw = pd.concat(parts, ignore_index=True)
        factors = fetch_cached(raw_dir / f"factors_{code}_{end}.parquet", client.query_adjust_factor,
                               code=code, start_date="1990-01-01", end_date=end)
        dividends = [fetch_cached(raw_dir / f"dividend_{code}_{year}.parquet", client.query_dividend_data,
                                  code=code, year=str(year), yearType="operate")
                     for year in range(pd.Timestamp(start).year, pd.Timestamp(end).year + 1)]
        sina_dir = _safe(raw_dir / "sina")
        sina_dir.mkdir(parents=True, exist_ok=True)
        sina = fetch_sina_actions(code[3:], sina_dir)
        return raw, factors, pd.concat(dividends, ignore_index=True), sina


def prefetch_raw(start="20191001", end="20260924", *, offset=210, client=None):
    """Second independent API process: raw caches and private progress only."""
    intervals = year_segments(start, end)
    first, last = intervals[0][0], intervals[-1][1]
    directory = _safe(DOWNLOADS_DIR / f"history_{first.replace('-', '')}_{last.replace('-', '')}")
    if _safe(directory / "source_panel.parquet").exists():
        raise FileExistsError("Refusing prefetch into an already published source")
    # Read immutable per-query caches, not the primary's changing manifest/file.
    parts = []
    for date in snapshot_dates(first, last):
        part = pd.read_parquet(_safe(directory / "raw" / f"hs300_{date}.parquet"))
        validate_components(part, date)
        parts.append(part)
    symbols = sorted(code for code in pd.concat(parts).code.unique() if not code[3:].startswith(("300", "688")))
    if not isinstance(offset, int) or not 0 <= offset <= len(symbols):
        raise ValueError("Invalid prefetch stock offset")
    progress = _safe(directory / f"prefetch_progress_{offset}.json")
    status = dict(state="starting", offset=offset, stocks=len(symbols) - offset, complete_stocks=0, failures=[])
    if client is None:
        import baostock as client
    previous_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(20)
    logged_in = False
    try:
        with _deadline(20):
            login = client.login()
        if login.error_code != "0":
            raise RuntimeError(f"BaoStock prefetch login: {login.error_msg}")
        logged_in = True
        for number, code in enumerate(symbols[offset:], 1):
            try:
                fetch_stock_raw(directory, code, first, last, client)
                status["complete_stocks"] += 1
                print(f"[prefetch] {number}/{len(symbols)-offset} {code}", flush=True)
            except Exception as exc:
                status["failures"].append(dict(code=code, error=f"{type(exc).__name__}: {exc}"))
                print(f"[prefetch] FAILED {code}: {exc}", flush=True)
            status.update(state="prefetching", attempted_stocks=number)
            _write_json(progress, status)
        status["state"] = "failed" if status["failures"] else "complete"
        _write_json(progress, status)
        if status["failures"]:
            raise RuntimeError("Raw prefetch incomplete; see private prefetch progress")
        return progress
    finally:
        try:
            if logged_in:
                with _deadline(10):
                    client.logout()
        finally:
            socket.setdefaulttimeout(previous_timeout)


def download_panel(start="20191001", end="20260924", *, client=None):
    """Freeze the entire date-addressed constituent union; resume only raw caches."""
    from .corporate_actions import merge_actions, DATA_LIMITATIONS, EXECUTION_SEMANTICS
    from .data import _normalise

    intervals = year_segments(start, end)
    first, requested_end = intervals[0][0], intervals[-1][1]
    directory = _safe(DOWNLOADS_DIR / f"history_{first.replace('-', '')}_{requested_end.replace('-', '')}")
    output = _safe(directory / "source_panel.parquet")
    if output.exists():
        raise FileExistsError(f"History source already frozen: {output}")
    attempt = _begin_attempt(directory)
    if client is None:
        import baostock as client
    previous_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(20)
    status = dict(state="starting", requested_start=first, requested_end=requested_end, **attempt)
    logged_in = False
    try:
        with _deadline(20):
            login = client.login()
        if login.error_code != "0":
            raise RuntimeError(f"BaoStock login: {login.error_msg}")
        logged_in = True
        directory, membership, symbols = collect_membership(first, requested_end, client)
        status = json.loads((directory / "download_manifest.json").read_text())
        status.update(attempt)
        raw_dir = directory / "raw"
        fields = "date,code,open,high,low,close,preclose,volume"
        index_parts = [fetch_cached(raw_dir / f"index_000300_{lo}_{hi}.parquet", client.query_history_k_data_plus,
                                   code="sh.000300", fields=fields, start_date=lo, end_date=hi, frequency="d", adjustflag="3")
                       for lo, hi in intervals]
        index = pd.concat(index_parts, ignore_index=True)
        if index.empty:
            raise ValueError("No complete 000300 index bars in requested interval")
        index["date"] = pd.to_datetime(index.date)
        if index.date.duplicated().any() or not index.date.between(pd.Timestamp(first), pd.Timestamp(requested_end)).all():
            raise ValueError("Index dates duplicate or outside requested interval")
        effective_end = index.date.max().strftime("%Y-%m-%d")
        status.update(state="downloading", effective_end=effective_end, complete_stocks=0, failed_stocks=0)
        index = index.assign(vt_symbol="000300.SSE", adj_factor=1., limit_up=float("nan"), limit_down=float("nan"), is_st=False, is_member=False, cash_dividend=0., split_ratio=1.)
        intervals = year_segments(first, effective_end)
        frames, failures, action_audits = [], [], {}
        suspended_rows = 0
        for number, code in enumerate(symbols, 1):
            try:
                raw, factors, bao_actions, sina = fetch_stock_raw(directory, code, first, effective_end, client)
                events, audit = merge_actions(bao_actions, sina, start=first, end=effective_end,
                                              symbol=code[3:] + (".SSE" if code.startswith("sh.") else ".SZSE"))
                frame = normalize_stock(raw, factors, events)
                frame["is_member"] = membership_flags(frame.date, code, membership)
                audit["unmapped_event_dates"] = events.loc[~events.date.isin(frame.date), "date"].dt.strftime("%Y-%m-%d").tolist()
                audit["suspended_bar_rows"] = int(raw.tradestatus.astype(str).eq("0").sum())
                suspended_rows += audit["suspended_bar_rows"]
                action_audits[code] = audit
                _write_json(directory / "action_audits" / f"{code}.json", audit)
                event_path = _safe(directory / "events" / f"{code}.parquet")
                event_path.parent.mkdir(parents=True, exist_ok=True)
                events.to_parquet(event_path, index=False)
                frames.append(frame)
                status["complete_stocks"] += 1
                print(f"[history] {number}/{len(symbols)} {code} rows={len(frame)} sina_added={audit['sina_only_count']}", flush=True)
            except Exception as exc:
                failures.append(dict(code=code, error=f"{type(exc).__name__}: {exc}"))
                status["failed_stocks"] = len(failures)
                status["current_failures"] = failures
                _write_json(directory / "download_errors.json", failures)
                print(f"[history] FAILED {number}/{len(symbols)} {code}: {exc}", flush=True)
            status["attempted_stocks"] = number
            _write_json(directory / "download_manifest.json", status)
        if failures:
            raise RuntimeError(f"{len(failures)} historical stocks failed; no partial panel published; see download_errors.json")
        if not frames:
            raise ValueError("No eligible historical stocks")
        panel = _normalise(pd.concat(frames + [index[frames[0].columns]], ignore_index=True))
        gaps = audit_factor_gaps(panel)
        limits = audit_limits(panel)
        gaps.to_parquet(_safe(directory / "factor_gaps.parquet"), index=False)
        limits.to_parquet(_safe(directory / "derived_limit_violations.parquet"), index=False)
        source_url = "https://www.sse.com.cn/aboutus/mediacenter/hotandd/c/c_20260424_10816474.shtml"
        panel.attrs = dict(provider="baostock+sina", source="date-addressed HS300 + raw bars + cumulative factors + reconciled BaoStock/Sina actions",
                           requested_start=first, requested_end=requested_end, effective_end=effective_end,
                           historical_membership_verified=True, membership_source="BaoStock monthly query snapshots strictly effective after query date; source declaration only",
                           data_limitations=["derived_limits", "ipo_relisting_limit_exceptions_not_modeled", "monthly_membership_lags_actual_reconstitution", "unexplained_factor_discontinuities_not_repaired", "historical_security_identity_changes_not_reconstructed"] + list(DATA_LIMITATIONS),
                           execution_semantics={**EXECUTION_SEMANTICS, "limits": "raw preclose Decimal HALF_UP cents; mainboard normal10%; ST5% before2026-07-06 then10%; ChiNext20% from2020-08-24; not exchange limits", "suspension": "retain real OHLC and events; only missing volume on tradestatus=0 converted to zero", "adjustment_factor": "cumulative backAdjustFactor asof effective date; never infer investor shares/cash from factor"},
                           limit_rule_sources=[source_url, "https://docs.static.szse.cn/www/lawrules/rule/allrules/bussiness/W020260424690713155663.pdf", "https://investor.szse.cn/institute/rules/t20200807_580310.html"],
                           factor_gap_rows=len(gaps), derived_limit_violation_rows=len(limits), derived_limit_violation_member_rows=int(limits.is_member.sum()), suspended_bar_rows=suspended_rows,
                           sina_supplement_events=sum(a["sina_only_count"] for a in action_audits.values()),
                           action_resolution_count=sum(a.get("action_resolution_count", 0) for a in action_audits.values()),
                           unmapped_action_events=sum(len(a["unmapped_event_dates"]) for a in action_audits.values()))
        if output.exists():
            raise FileExistsError(f"Never replace existing source: {output}")
        panel.to_parquet(output, index=False)
        status.update(state="complete", rows=len(panel), output=str(output), output_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                      metadata=panel.attrs, completed_at_utc=datetime.now(timezone.utc).isoformat(),
                      code_sha256={name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in ("history_download.py", "corporate_actions.py", "baostock_download.py", "data.py")})
        _write_json(directory / "download_manifest.json", status)
        return output
    except Exception as exc:
        status.update(state="failed", error=f"{type(exc).__name__}: {exc}")
        _write_json(directory / "download_manifest.json", status)
        raise
    finally:
        try:
            if logged_in:
                with _deadline(10):
                    client.logout()
        finally:
            socket.setdefaulttimeout(previous_timeout)
