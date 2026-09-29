"""Dedicated historical HS300 stock download; never reads vn.py resources.

Run with the repository's absolute Python path and ``-I``. All caches live under
this package's data/downloads. This is an explicitly imperfect daily replay
source: limits are derived; dividend cash and bonus shares are credited ex-date.
"""
from __future__ import annotations

import hashlib
import json
import math
import socket
from bisect import bisect_left
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parent
DOWNLOADS_DIR = ROOT / "data" / "downloads"
FIELDS = "date,code,open,high,low,close,preclose,volume,tradestatus,isST"


def collect_response(response: Any) -> pd.DataFrame:
    """Do not silently transform provider failures into successful empty data."""
    if response.error_code != "0":
        raise RuntimeError(f"BaoStock {response.error_code}: {response.error_msg}")
    rows = []
    while response.next():
        rows.append(response.get_row_data())
    if response.error_code != "0":
        raise RuntimeError(f"BaoStock {response.error_code}: {response.error_msg}")
    return pd.DataFrame(rows, columns=response.fields)


def snapshot_dates(start: str, end: str) -> list[str]:
    first, last = pd.Timestamp(start), pd.Timestamp(end)
    if first > last:
        raise ValueError("start must not be later than end")
    prior_end = first.replace(day=1) - pd.Timedelta(days=1)
    values = list(pd.date_range(prior_end, last, freq="ME"))
    # A partial final month is queried only to bound the declared data coverage.
    if values[-1] != last:
        values.append(last)
    return [value.strftime("%Y-%m-%d") for value in values]


def membership_flags(dates, code: str, snapshots: pd.DataFrame) -> list[bool]:
    """A month-end snapshot may affect only the next day and later."""
    snapshots = snapshots.copy()
    snapshots["snapshot_date"] = pd.to_datetime(snapshots["snapshot_date"])
    grouped = {date: set(part["code"]) for date, part in snapshots.groupby("snapshot_date")}
    known = sorted(grouped)
    flags = []
    for date in pd.to_datetime(dates):
        index = bisect_left(known, date) - 1
        flags.append(index >= 0 and code in grouped[known[index]])
    return flags


def validate_components(frame: pd.DataFrame, query_date: str) -> None:
    """Fail closed on incomplete, duplicate or lookahead HS300 snapshots."""
    if len(frame) != 300 or frame["code"].nunique() != 300:
        raise ValueError(f"HS300 snapshot must contain 300 unique securities: {query_date}")
    if not frame["code"].astype(str).str.fullmatch(r"(?:sh|sz)\.\d{6}").all():
        raise ValueError(f"Invalid HS300 security code: {query_date}")
    updated = pd.to_datetime(frame["updateDate"], errors="raise")
    if updated.isna().any() or (updated > pd.Timestamp(query_date)).any():
        raise ValueError(f"HS300 snapshot has missing/future updateDate: {query_date}")


def _round_price(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _event_number(row: pd.Series, field: str) -> float:
    value = row.get(field, "")
    if value is None or pd.isna(value) or str(value).strip() == "":
        return 0.0
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError(f"Invalid corporate action {field}: {value}")
    return result


def normalize_stock(raw: pd.DataFrame, factors: pd.DataFrame, dividends: pd.DataFrame) -> pd.DataFrame:
    """Map raw bars and explicitly sourced actions, without selecting stocks."""
    if raw.empty:
        raise ValueError("BaoStock returned no raw bars for a historical constituent")
    raw = raw.copy()
    if not raw["tradestatus"].astype(str).isin(["0", "1"]).all():
        raise ValueError("Unknown historical trading status")
    if not raw["isST"].astype(str).isin(["0", "1"]).all():
        raise ValueError("Unknown historical ST status")
    raw = raw.loc[raw["tradestatus"].astype(str) == "1"].copy()
    raw["date"] = pd.to_datetime(raw["date"])
    raw = raw.sort_values("date")
    for column in ["open", "high", "low", "close", "preclose", "volume"]:
        raw[column] = pd.to_numeric(raw[column], errors="raise").astype(float)
    if not raw["preclose"].map(math.isfinite).all() or (raw["preclose"] <= 0).any():
        raise ValueError("A positive finite ex-rights reference preclose is required")
    if raw["code"].nunique() > 1:
        raise ValueError("normalize_stock expects one security at a time")
    code = str(raw["code"].iloc[0]) if len(raw) else str(raw["code"].name)
    raw["vt_symbol"] = code[3:] + (".SSE" if code.startswith("sh.") else ".SZSE")
    raw["is_st"] = raw["isST"].astype(str).eq("1")
    raw["is_member"] = False
    ratios = raw["is_st"].map({True: 0.05, False: 0.10})
    # Source alpha excludes 300/688 only; retained 301/302 remain ChiNext.
    if code.startswith("sz.3"):
        ratios = ratios.mask(raw["date"] >= pd.Timestamp("2020-08-24"), 0.20)
    elif code.startswith("sh.688"):
        ratios[:] = 0.20
    raw["limit_up"] = [_round_price(Decimal(str(ref)) * (Decimal(1) + Decimal(str(ratio)))) for ref, ratio in zip(raw["preclose"], ratios)]
    raw["limit_down"] = [_round_price(Decimal(str(ref)) * (Decimal(1) - Decimal(str(ratio)))) for ref, ratio in zip(raw["preclose"], ratios)]
    raw["adj_factor"] = 1.0
    if not factors.empty:
        factor = factors[["dividOperateDate", "backAdjustFactor"]].copy()
        factor["date"] = pd.to_datetime(factor.pop("dividOperateDate"))
        factor["adj_factor"] = pd.to_numeric(factor.pop("backAdjustFactor"), errors="raise")
        if factor["date"].duplicated().any():
            raise ValueError("Duplicate effective adjustment-factor dates")
        raw = pd.merge_asof(raw.drop(columns=["adj_factor"]), factor.sort_values("date"), on="date", direction="backward")
        raw["adj_factor"] = raw["adj_factor"].fillna(1.0)
    raw["cash_dividend"] = 0.0
    raw["split_ratio"] = 1.0
    seen_events: dict[str, tuple[float, float, float]] = {}
    for _, event in dividends.iterrows():
        ex_date = event.get("dividOperateDate", "")
        if not ex_date:
            continue
        cash = _event_number(event, "dividCashPsBeforeTax")
        bonus = _event_number(event, "dividStocksPs")
        capitalisation = _event_number(event, "dividReserveToStockPs")
        economic_action = (cash, bonus, capitalisation)
        if ex_date in seen_events:
            if seen_events[ex_date] != economic_action:
                raise ValueError(f"Conflicting dividend effective date: {code} {ex_date}")
            continue  # One action can have multiple identical-economic announcement versions.
        seen_events[ex_date] = economic_action
        mask = raw["date"].eq(pd.Timestamp(ex_date))
        raw.loc[mask, "cash_dividend"] = cash
        raw.loc[mask, "split_ratio"] = 1.0 + bonus + capitalisation
    return raw[["date", "vt_symbol", "open", "high", "low", "close", "volume", "adj_factor", "limit_up", "limit_down", "is_st", "is_member", "cash_dividend", "split_ratio"]]


def audit_limits(panel: pd.DataFrame) -> pd.DataFrame:
    """Expose IPO/relisting/vendor exceptions; never remove securities or rows."""
    stock = panel.loc[panel["vt_symbol"] != "000300.SSE"]
    outside = (stock["high"] > stock["limit_up"] + 0.005) | (stock["low"] < stock["limit_down"] - 0.005)
    return stock.loc[outside].copy()


def _fetch_cached(path: Path, method, **kwargs) -> pd.DataFrame:
    if path.is_symlink():
        raise ValueError("Downloader cache must not be a symlink")
    if path.exists():
        return pd.read_parquet(path)
    result = collect_response(method(**kwargs))
    result.to_parquet(path, index=False)
    return result


def download_panel(start: str = "20231001", end: str = "20251231", *, client=None) -> Path:
    """Download the entire historical main-board HS300 union, resume local cache.

    ``client`` is an optional Baostock-compatible transport for isolated tests.
    The default SDK is imported only on explicit download. No credentials needed.
    """
    start_date = pd.Timestamp(start).strftime("%Y-%m-%d")
    end_date = pd.Timestamp(end).strftime("%Y-%m-%d")
    if pd.Timestamp(end_date) >= pd.Timestamp("2026-07-06"):
        raise ValueError("Derived mainboard ST limits are supported only before 2026-07-06; newer rule periods require a separate data contract")
    dates = snapshot_dates(start_date, end_date)
    if DOWNLOADS_DIR.is_symlink() or DOWNLOADS_DIR.parent.is_symlink():
        raise ValueError("Downloads must remain in the isolated stock data directory")
    directory = DOWNLOADS_DIR / f"baostock_{start_date.replace('-', '')}_{end_date.replace('-', '')}"
    if directory.is_symlink():
        raise ValueError("Download directory must not be a symlink")
    for filename in ("download_manifest.json", "historical_components.parquet", "source_panel.parquet", "derived_limit_violations.parquet"):
        if (directory / filename).is_symlink():
            raise ValueError("Download output files must not be symlinks")
    raw_dir = directory / "raw"
    if raw_dir.is_symlink():
        raise ValueError("Raw cache must not be a symlink")
    raw_dir.mkdir(parents=True, exist_ok=True)
    if client is None:
        import baostock as client
    previous_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(20)
    manifest_path = directory / "download_manifest.json"
    status = {"provider": "baostock", "start_date": start_date, "end_date": end_date, "state": "downloading", "complete_stocks": 0}
    logged_in = False
    try:
        login = client.login()
        if login.error_code != "0":
            raise RuntimeError(f"BaoStock login: {login.error_msg}")
        logged_in = True
        snapshots = []
        for query_date in dates:
            part = _fetch_cached(raw_dir / f"hs300_{query_date}.parquet", client.query_hs300_stocks, date=query_date)
            validate_components(part, query_date)
            part = part.assign(snapshot_date=query_date)
            snapshots.append(part)
        membership = pd.concat(snapshots, ignore_index=True)
        membership.to_parquet(directory / "historical_components.parquet", index=False)
        # Original strategy excludes 300/688; no result-driven sub-universe is used.
        symbols = sorted(code for code in membership["code"].unique() if not code[3:].startswith(("300", "688")))
        status["historical_union_stocks"] = len(symbols)
        status["snapshots"] = len(snapshots)
        index = _fetch_cached(raw_dir / "index_000300.parquet", client.query_history_k_data_plus,
                              code="sh.000300", fields="date,code,open,high,low,close,preclose,volume",
                              start_date=start_date, end_date=end_date, frequency="d", adjustflag="3")
        if index.empty:
            raise ValueError("Missing historical 000300 index")
        index["date"] = pd.to_datetime(index["date"])
        index = index.assign(vt_symbol="000300.SSE", adj_factor=1.0, limit_up=float("nan"), limit_down=float("nan"), is_st=False, is_member=False, cash_dividend=0.0, split_ratio=1.0)
        for col in ["open", "high", "low", "close", "volume"]:
            index[col] = pd.to_numeric(index[col], errors="raise")
        frames = []
        for number, code in enumerate(symbols, 1):
            raw = _fetch_cached(raw_dir / f"bars_{code}.parquet", client.query_history_k_data_plus, code=code, fields=FIELDS,
                                start_date=start_date, end_date=end_date, frequency="d", adjustflag="3")
            factor = _fetch_cached(raw_dir / f"factors_{code}.parquet", client.query_adjust_factor, code=code, start_date="1990-01-01", end_date=end_date)
            actions = []
            for year in range(pd.Timestamp(start_date).year, pd.Timestamp(end_date).year + 1):
                actions.append(_fetch_cached(raw_dir / f"dividend_{code}_{year}.parquet", client.query_dividend_data, code=code, year=str(year), yearType="operate"))
            action_frame = pd.concat(actions, ignore_index=True).drop_duplicates() if actions else pd.DataFrame()
            frame = normalize_stock(raw, factor, action_frame)
            frame["is_member"] = membership_flags(frame["date"], code, membership)
            frames.append(frame)
            status["complete_stocks"] = number
            manifest_path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"[baostock] {number}/{len(symbols)} {code} rows={len(frame)}", flush=True)
        panel = pd.concat(frames + [index[frames[0].columns]], ignore_index=True).sort_values(["date", "vt_symbol"])
        panel.attrs = {
            "provider": "baostock",
            "source": "query_hs300_stocks + raw query_history_k_data_plus + query_adjust_factor + query_dividend_data",
            "historical_membership_verified": True,
            "membership_source": "Baostock date-addressed historical monthly snapshots, used only strictly after query date; source declaration only",
            "derived_limit_rule_valid_before": "2026-07-06",
            "derived_limit_rule_boundary_source": "https://investor.szse.cn/lawrules/rule/trade/t20260424_620190.html",
            "data_limitations": ["derived_limits", "ipo_relisting_limit_exceptions_not_modeled", "monthly_membership_lags_actual_reconstitution", "cash_dividend_before_tax_on_ex_date", "bonus_shares_available_on_ex_date", "rights_issues_not_modeled", "suspended_rows_omitted"],
            "execution_semantics": {"limit_reference": "Baostock raw preclose (ex-rights reference), Decimal ROUND_HALF_UP to 0.01; 2023-2025 mainboard 10%, ST 5%; retained ChiNext 301/302 20% including ST (effective 2020-08-24); NOT exchange-published limits", "limit_rule_source": "https://investor.szse.cn/institute/rules/t20200807_580310.html", "cash_dividend": "gross before-tax cash per share credited on ex-date, payment-date and withholding-tax timing not modeled", "split_ratio": "1 + dividStocksPs + dividReserveToStockPs on ex-date; separate share-listing date not modeled", "adjustment_factor": "backAdjustFactor carried forward from 1990-query history; no future factor backward fill", "membership": "month-end query snapshots effective on the following calendar day"},
        }
        limit_audit = audit_limits(panel)
        limit_audit.to_parquet(directory / "derived_limit_violations.parquet", index=False)
        panel.attrs["derived_limit_violation_rows"] = len(limit_audit)
        panel.attrs["derived_limit_violation_member_rows"] = int(limit_audit["is_member"].sum())
        output = directory / "source_panel.parquet"
        if output.is_symlink() or manifest_path.is_symlink():
            raise ValueError("Download output files must not be symlinks")
        panel.to_parquet(output, index=False)
        status.update(state="complete", rows=len(panel), output=str(output), output_sha256=hashlib.sha256(output.read_bytes()).hexdigest(), data_limitations=panel.attrs["data_limitations"], derived_limit_violation_rows=len(limit_audit), derived_limit_violation_member_rows=int(limit_audit["is_member"].sum()), completed_at_utc=datetime.now(timezone.utc).isoformat())
        manifest_path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return output
    except Exception as exc:
        status.update(state="failed", error=f"{type(exc).__name__}: {exc}")
        if not manifest_path.is_symlink():
            manifest_path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        raise
    finally:
        if logged_in:
            client.logout()
        socket.setdefaulttimeout(previous_timeout)


if __name__ == "__main__":
    print(download_panel(), flush=True)
