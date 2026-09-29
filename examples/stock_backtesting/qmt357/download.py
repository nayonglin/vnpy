"""Isolated, resumable Tushare downloader; never imports broker/futures code.

Run with the isolated interpreter to bypass repository sitecustomize.py:
    .py311/bin/python -I examples/stock_backtesting/qmt357/download.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
FIELDS = {
    "daily": "ts_code,trade_date,open,high,low,close,vol",
    "index_daily": "ts_code,trade_date,open,high,low,close,vol",
    "index_weight": "index_code,con_code,trade_date,weight",
    "adj_factor": "ts_code,trade_date,adj_factor",
    "stk_limit": "ts_code,trade_date,up_limit,down_limit",
    "namechange": "ts_code,name,start_date,end_date,ann_date,change_reason",
    "dividend": "ts_code,end_date,ann_date,div_proc,stk_div,stk_bo_rate,stk_co_rate,cash_div,cash_div_tax,record_date,ex_date,pay_date,div_listdate,imp_ann_date",
}
LIMITATIONS = [
    "沪深300使用Tushare月度权重快照，只有快照日期之后生效；月内调整可能延迟，不将月末成分回填月初。",
    "现金分红使用cash_div_tax税前金额，在ex_date计入现金；未建pay_date应收账款，不计个人持有期红利税。",
    "送转比例使用stk_bo_rate+stk_co_rate，在ex_date增股；未推迟至div_listdate才可卖，须按工程迁移验证解读。",
    "历史名称和公司行为为供应商当前历史记录，无法保证其后续修订的逐版本PIT可得性。",
]
EXECUTION_SEMANTICS = {
    "price_basis": "unadjusted_prices_with_separate_adj_factor",
    "volume_unit": "shares",
    "membership": "historical_monthly_snapshot_effective_strictly_after_snapshot_date",
    "price_limits": "tushare_stk_limit_reported_daily_limits",
    "cash_dividend": "pretax_cash_div_tax_credited_on_ex_date_not_pay_date",
    "stock_distribution": "bonus_plus_capitalisation_on_ex_date_sellable_without_listing_delay",
}


class DataSourceError(RuntimeError):
    """A classified source failure safe to show without credentials."""


class CachedTushareClient:
    def __init__(self, pro, cache_dir: Path, min_interval: float = .65, token: str = ""):
        self.pro = pro
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.min_interval = min_interval
        self.token = token
        self.last_request = 0.0

    def fetch(self, endpoint: str, params: dict, fields: str) -> pd.DataFrame:
        request = {"endpoint": endpoint, "params": params, "fields": fields}
        key = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()[:24]
        target = self.cache_dir / f"{endpoint}_{key}.parquet"
        meta = self.cache_dir / f"{endpoint}_{key}.json"
        if target.exists() and meta.exists():
            receipt = json.loads(meta.read_text())
            if hashlib.sha256(target.read_bytes()).hexdigest() != receipt["sha256"]:
                raise DataSourceError("cached payload checksum mismatch")
            return pd.read_parquet(target)
        for attempt in range(3):
            delay = self.min_interval - (time.monotonic() - self.last_request)
            if delay > 0:
                time.sleep(delay)
            self.last_request = time.monotonic()
            try:
                result = self.pro.query(endpoint, fields=fields, **params)
                missing = set(fields.split(",")) - set(result.columns)
                if missing:
                    raise DataSourceError(f"schema missing fields: {sorted(missing)}")
                payload = result.to_parquet(index=False)
                temporary = target.with_suffix(".part")
                temporary.write_bytes(payload)
                temporary.replace(target)
                receipt = {**request, "rows": len(result), "columns": list(result.columns), "fetched_at_utc": datetime.now(timezone.utc).isoformat(), "sha256": hashlib.sha256(payload).hexdigest()}
                meta.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
                return result
            except Exception as exc:
                message = str(exc)
                if self.token:
                    message = message.replace(self.token, "[REDACTED]")
                lower = message.lower()
                if "token" in lower or "认证" in message:
                    kind = "authentication"
                elif any(word in message for word in ("权限", "积分", "没有访问")):
                    kind = "permission"
                elif any(word in lower for word in ("timeout", "timed out", "connection", "429", "502", "503", "504")) or any(word in message for word in ("频次", "每分钟", "限流")):
                    kind = "transient"
                else:
                    kind = "request_or_schema"
                if kind == "transient" and attempt < 2:
                    time.sleep(min(10, 2 ** (attempt + 1)))
                    continue
                failure = {**request, "status": "failed", "kind": kind, "error": message[:500], "attempts": attempt + 1, "at_utc": datetime.now(timezone.utc).isoformat()}
                self.cache_dir.joinpath(f"{endpoint}_{key}_failure.json").write_text(json.dumps(failure, ensure_ascii=False, indent=2), encoding="utf-8")
                raise DataSourceError(f"{endpoint}: {kind}: {message[:240]}") from None
        raise AssertionError("unreachable")


def membership_flags(dates, symbol: str, weights: pd.DataFrame) -> np.ndarray:
    """Use the most recent *whole snapshot* strictly before each date."""
    snapshots = {}
    for date, part in weights.groupby("trade_date"):
        snapshots[pd.Timestamp(str(date))] = set(part["con_code"])
    ordered = sorted(snapshots)
    positions = np.searchsorted(pd.DatetimeIndex(ordered).asi8, pd.DatetimeIndex(dates).asi8, side="left") - 1
    return np.asarray([position >= 0 and symbol in snapshots[ordered[position]] for position in positions], dtype=bool)


def _st_flags(dates: pd.Series, names: pd.DataFrame) -> np.ndarray:
    status = np.zeros(len(dates), dtype=bool)
    covered = np.zeros(len(dates), dtype=bool)
    for row in names.sort_values("start_date").itertuples():
        if pd.isna(row.start_date) or pd.isna(row.name):
            continue
        start = pd.Timestamp(str(row.start_date))
        end = pd.Timestamp(str(row.end_date)) if pd.notna(row.end_date) else pd.Timestamp.max.normalize()
        mask = dates.ge(start).to_numpy() & dates.le(end).to_numpy()
        status[mask] = "ST" in str(row.name).upper()
        covered |= mask
    if not covered.all():
        raise ValueError(f"historical names uncovered on {int((~covered).sum())} rows")
    return status


def _actions(dividends: pd.DataFrame) -> pd.DataFrame:
    columns = ["date", "cash_dividend", "split_ratio"]
    if dividends.empty:
        return pd.DataFrame(columns=columns)
    actions = dividends.loc[dividends["div_proc"].eq("实施") & dividends["ex_date"].notna()].copy()
    if actions.empty:
        return pd.DataFrame(columns=columns)
    values = ["cash_div_tax", "stk_bo_rate", "stk_co_rate"]
    for column in values:
        actions[column] = pd.to_numeric(actions[column], errors="raise").fillna(0.)
    if (actions[values] < 0).any().any():
        raise ValueError("negative corporate action")
    if "stk_div" in actions and not np.allclose(pd.to_numeric(actions["stk_div"]).fillna(0), actions["stk_bo_rate"] + actions["stk_co_rate"]):
        raise ValueError("Conflicting total and component stock distributions")
    actions = actions.drop_duplicates(["ts_code", "end_date", "ex_date", *values])
    if actions.duplicated(["ts_code", "end_date", "ex_date"]).any():
        raise ValueError("Conflicting corporate actions for the same period/date")
    actions["date"] = pd.to_datetime(actions["ex_date"], format="%Y%m%d")
    grouped = actions.groupby("date", as_index=False)[values].sum()
    grouped["cash_dividend"] = grouped["cash_div_tax"]
    grouped["split_ratio"] = 1 + grouped["stk_bo_rate"] + grouped["stk_co_rate"]
    return grouped[columns]


def normalize_symbol(daily, factors, limits, names, dividends, weights, *, is_index=False) -> pd.DataFrame:
    """Join actual daily facts; missing tradability metadata is a hard failure."""
    if daily.empty or daily["ts_code"].nunique() != 1:
        raise ValueError("daily data must contain one nonempty symbol")
    panel = daily.copy().drop_duplicates().sort_values("trade_date")
    if panel.duplicated(["ts_code", "trade_date"]).any():
        raise ValueError("conflicting daily duplicates")
    symbol = str(panel["ts_code"].iloc[0])
    panel["date"] = pd.to_datetime(panel["trade_date"], format="%Y%m%d")
    panel["vt_symbol"] = symbol.replace(".SH", ".SSE").replace(".SZ", ".SZSE")
    panel["volume"] = pd.to_numeric(panel["vol"], errors="raise") * 100
    if is_index:
        panel["adj_factor"] = 1.
        panel["limit_up"] = np.nan
        panel["limit_down"] = np.nan
        panel["is_st"] = False
        panel["is_member"] = False
        panel["cash_dividend"] = 0.
        panel["split_ratio"] = 1.
    else:
        for extra, required in ((factors, ["adj_factor"]), (limits, ["up_limit", "down_limit"])):
            relevant = extra.loc[extra["ts_code"].eq(symbol), ["ts_code", "trade_date", *required]].drop_duplicates()
            panel = panel.merge(relevant, on=["ts_code", "trade_date"], how="left", validate="one_to_one")
            if panel[required].isna().any().any():
                raise ValueError(f"missing historical metadata: {required}")
        panel = panel.rename(columns={"up_limit": "limit_up", "down_limit": "limit_down"})
        panel["is_st"] = _st_flags(panel["date"], names.loc[names["ts_code"].eq(symbol)])
        panel["is_member"] = membership_flags(panel["date"], symbol, weights)
        events = _actions(dividends.loc[dividends["ts_code"].eq(symbol)] if not dividends.empty else dividends)
        if not events.empty:
            relevant = events.loc[events["date"].between(panel["date"].min(), panel["date"].max())]
            if not relevant["date"].isin(panel["date"]).all():
                raise ValueError("corporate action date has no tradable daily row; explicit suspension accounting required")
            panel = panel.merge(relevant, on="date", how="left", validate="one_to_one")
            panel["cash_dividend"] = panel["cash_dividend"].fillna(0.)
            panel["split_ratio"] = panel["split_ratio"].fillna(1.)
        else:
            panel["cash_dividend"] = 0.
            panel["split_ratio"] = 1.
    return panel[["date", "vt_symbol", "open", "high", "low", "close", "volume", "adj_factor", "limit_up", "limit_down", "is_st", "is_member", "cash_dividend", "split_ratio"]].reset_index(drop=True)


def _year_chunks(start: str, end: str):
    for year in range(int(start[:4]), int(end[:4]) + 1):
        yield max(start, f"{year}0101"), min(end, f"{year}1231")


def download_panel(start="20231001", end="20251231", *, client=None) -> Path:
    start_dt = pd.to_datetime(start, format="%Y%m%d", errors="raise")
    end_dt = pd.to_datetime(end, format="%Y%m%d", errors="raise")
    if start_dt > end_dt or end_dt > pd.Timestamp.today().normalize():
        raise ValueError("date range must be ordered and entirely historical")
    output = ROOT / "data" / "downloads" / f"tushare_{start}_{end}"
    if any(path.is_symlink() for path in (ROOT / "data", ROOT / "data" / "downloads", output)):
        raise ValueError("download output may not be redirected by a symlink")
    output.mkdir(parents=True, exist_ok=True)
    if client is None:
        token = os.environ.get("TUSHARE_TOKEN", "").strip()
        if not token:
            raise DataSourceError("authentication: TUSHARE_TOKEN is not configured")
        import tushare as ts
        client = CachedTushareClient(ts.pro_api(token, timeout=20), output / "cache", token=token)
    receipt = {"provider": "tushare", "start_date": start, "end_date": end, "created_at_utc": datetime.now(timezone.utc).isoformat(), "data_limitations": LIMITATIONS, "execution_semantics": EXECUTION_SEMANTICS, "status": "running"}
    manifest = output / "download_manifest.json"
    try:
        parts = []
        first_month = start_dt.to_period("M") - 1
        for month in pd.period_range(first_month, end_dt.to_period("M"), freq="M"):
            frame = client.fetch("index_weight", {"index_code": "399300.SZ", "start_date": month.start_time.strftime("%Y%m%d"), "end_date": month.end_time.strftime("%Y%m%d")}, FIELDS["index_weight"])
            if frame.empty or len(frame) >= 4000:
                raise ValueError(f"empty or potentially truncated membership month {month}")
            if not frame.groupby("trade_date")["con_code"].nunique().eq(300).all():
                raise ValueError(f"incomplete 300-member snapshots in {month}")
            parts.append(frame)
        weights = pd.concat(parts, ignore_index=True).drop_duplicates()
        weights.to_parquet(output / "membership_snapshots.parquet", index=False)
        symbols = sorted(code for code in weights["con_code"].unique() if not code.startswith(("300", "688")))
        chunks = list(_year_chunks(start, end))

        def history(endpoint, code):
            frames = [client.fetch(endpoint, {"ts_code": code, "start_date": left, "end_date": right}, FIELDS[endpoint]) for left, right in chunks]
            if any(len(frame) >= 2000 for frame in frames):
                raise ValueError(f"potentially truncated annual {endpoint} segment")
            return pd.concat(frames, ignore_index=True).drop_duplicates()

        index_daily = history("index_daily", "000300.SH")
        panels = [normalize_symbol(index_daily, None, None, None, None, None, is_index=True)]
        for ordinal, symbol in enumerate(symbols, 1):
            daily = history("daily", symbol)
            if daily.empty:
                raise ValueError(f"missing history for historical member {symbol}")
            factors = history("adj_factor", symbol)
            limits = history("stk_limit", symbol)
            names = client.fetch("namechange", {"ts_code": symbol}, FIELDS["namechange"])
            dividends = client.fetch("dividend", {"ts_code": symbol}, FIELDS["dividend"])
            if len(dividends) >= 2000 or len(names) >= 1000:
                raise ValueError(f"potentially truncated metadata for {symbol}")
            panels.append(normalize_symbol(daily, factors, limits, names, dividends, weights))
            if ordinal % 20 == 0 or ordinal == len(symbols):
                print(json.dumps({"downloaded_symbols": ordinal, "total_symbols": len(symbols)}), flush=True)
        panel = pd.concat(panels, ignore_index=True).sort_values(["date", "vt_symbol"]).reset_index(drop=True)
        panel.attrs = {"provider": "tushare", "historical_membership_verified": True, "membership_source": "Tushare index_weight 399300.SZ historical monthly snapshots; strictly later dates only", "data_limitations": LIMITATIONS, "execution_semantics": EXECUTION_SEMANTICS}
        target = output / "source_panel.parquet"
        panel.to_parquet(target, index=False)
        receipt.update(status="complete", rows=len(panel), stock_symbols=len(symbols), membership_snapshot_dates=int(weights["trade_date"].nunique()), index_trading_days=len(index_daily), source_panel=str(target), source_panel_sha256=hashlib.sha256(target.read_bytes()).hexdigest())
        manifest.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
        return target
    except Exception as exc:
        receipt.update(status="failed", error=str(exc)[:500])
        manifest.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="20231001")
    parser.add_argument("--end", default="20251231")
    args = parser.parse_args()
    try:
        print(download_panel(args.start, args.end))
    except (DataSourceError, ValueError) as exc:
        parser.exit(2, f"download failed: {exc}\n")


if __name__ == "__main__":
    main()
