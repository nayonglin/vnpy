"""Stage246 开仓自然日分钟完整性独立审计（不读取账户、不下载行情、不回测）。

用法：
  .py311/bin/python research/lines/futures_trend_rollover_shape_same_volume/tools/\
stage246_validate_minute_sessions.py --repo-root /path/to/replay/fian \
    --minute-dir /path/to/entry_minute_download \
    --coverage /path/to/entry_minute_coverage.csv --output /private/tmp/night_audit

每个 coverage (vt_symbol, entry_date) 审计自然日 225 根日盘及应有的夜盘分钟。
夜盘属于下一交易日，但下载器按上海自然日保存；因此周五晚间属于下周一
交易日，却仍须在周五 parquet 中出现；周五延续至周六凌晨的 au/cu 数据
不属于周五自然日，也不应凭周一开仓 key 期待周一凌晨。

规则资料（交易所/监管机构原始资料；历史通知另列原文转发）：
  SHFE 交易时间和夜盘归属：
  https://www.shfe.com.cn/services/calenderandholidays/tradinghours/
  CSRC 2020-02-03 当晚暂停夜盘：
  https://www.csrc.gov.cn/csrc/c100028/c1000838/content.shtml
  CZCE 烧碱 2023-09-15 上市当晚启用 21:00-23:00 夜盘：
  https://www.czce.com.cn/cn/rootfiles/2023/10/18/1697226838884489-1697226838904727.pdf
  CZCE 纯碱 2023 规则 21:00-23:00：
  https://www.czce.com.cn/cn/uploadfile/2023/05/15/20230515110954123.pdf
  CZCE 苹果、锰硅日盘规则（夜盘须另行公告）：
  https://www.czce.com.cn/cn/uploadfile/2022/08/31/20220831180835227.pdf
  https://www.czce.com.cn/cn/uploadfile/2022/08/31/20220831175840500.pdf
  CZCE 2019-12-11 全部夜盘品种由 23:30 调至 23:00，原郑商函〔2019〕473号；
  本审计从 2020 开始。交易所原文转发：
  https://www.xzfutures.com/article/10115096/index.html
  GFEX SI/LC 合约交易时间：
  https://www.gfex.com.cn/gfex/sspzb/sspz.shtml
  SHFE 假日前夜盘停、假后当晚恢复的原始实例：
  https://www.shfe.com.cn/publicnotice/notice/202409/t20240910_802477.html
  2020-05-06 夜盘恢复：上期发〔2020〕157号、郑商函〔2020〕153号原文转发：
  https://www.ghlsqh.com.cn/news/show-15628.html
  https://www.ghlsqh.com.cn/news/show-15634.html

交易日历从 repo-root/.vntrader/database.db 的日线日期只读取得。相邻自然日
交易或普通周五至下周一均期待夜盘；较长/非常规间隔按节前停盘处理。
日历尾日不猜下一交易日，报告 unknown。2020-02-03 至 2020-05-05
为证监会停盘区间，2020-05-06 晚恢复（郑商函〔2020〕153号等）。
"""

from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, time, timedelta
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from typing import Any

from stage246_download_entry_minutes import expected_day_grid, read_coverage


NIGHT_TO_23 = {"rb", "hc", "fu", "ru", "sp", "jm", "MA", "OI", "CF", "FG", "SA", "SH"}
NIGHT_TO_01 = {"cu"}
NIGHT_TO_0230 = {"au"}
DAY_ONLY = {"AP", "SM", "si", "lc", "lh"}
ALL_PRODUCTS = NIGHT_TO_23 | NIGHT_TO_01 | NIGHT_TO_0230 | DAY_ONLY
PAUSE_START = date(2020, 2, 3)
RESUME_NIGHT = date(2020, 5, 6)


def product_of(symbol: str) -> str:
    match = re.fullmatch(r"([A-Za-z]+)[0-9]+\.(SHFE|CZCE|DCE|GFEX)", symbol)
    if not match or match.group(1) not in ALL_PRODUCTS:
        raise ValueError(f"unsupported_product:{symbol}")
    return match.group(1)


def minute_range(day: date, start: time, end_exclusive: time) -> set[datetime]:
    first = datetime.combine(day, start)
    last = datetime.combine(day, end_exclusive)
    return {first + timedelta(minutes=i) for i in range(int((last - first).total_seconds() // 60))}


def trading_dates(db_path: Path, first: date, last: date) -> set[date]:
    if not db_path.is_file():
        raise FileNotFoundError(f"daily_calendar_db_missing:{db_path}")
    uri = f"file:{db_path.resolve()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        rows = connection.execute(
            "SELECT DISTINCT substr(datetime, 1, 10) FROM dbbardata "
            "WHERE interval='d' AND datetime>=? AND datetime<? ORDER BY 1",
            ((first - timedelta(days=8)).isoformat(), (last + timedelta(days=8)).isoformat()),
        ).fetchall()
    finally:
        connection.close()
    result = {date.fromisoformat(row[0]) for row in rows}
    if not result:
        raise ValueError("daily_calendar_empty")
    return result


def evening_state(day: date, calendar: set[date]) -> tuple[str, str]:
    """active / closed / unknown；普通周五至下周一是 active。"""
    if PAUSE_START <= day < RESUME_NIGHT:
        return "closed", "csrc_2020_night_pause"
    if day not in calendar:
        return "closed", "not_daily_trading_date"
    later = sorted(d for d in calendar if d > day)
    if not later:
        return "unknown", "next_trading_date_unavailable"
    next_day = later[0]
    gap = (next_day - day).days
    if gap == 1 or (day.weekday() == 4 and gap == 3 and next_day.weekday() == 0):
        return "active", "adjacent_trading_day_or_ordinary_friday"
    return "closed", "holiday_eve_or_nonstandard_gap"


def expected_sessions(symbol: str, day: date, calendar: set[date]) -> dict[str, Any]:
    product = product_of(symbol)
    day_grid = expected_day_grid(day.isoformat())
    if product in DAY_ONLY:
        return {"day": day_grid, "early": set(), "evening": set(),
                "early_state": "closed", "evening_state": "closed",
                "early_reason": "day_only_product", "evening_reason": "day_only_product"}
    evening_state_now, evening_reason = evening_state(day, calendar)
    previous_day = day - timedelta(days=1)
    early_state_prev, early_reason = evening_state(previous_day, calendar)
    if product in NIGHT_TO_23:
        early_state_prev, early_reason = "closed", "night_ends_before_midnight"
    evening_end = time(23, 0) if product in NIGHT_TO_23 else time(0, 0)
    # 00:00 是次日，不能用同日 datetime.combine(00:00) 表达夜盘晚段终点。
    evening = (
        {datetime.combine(day, time(21, 0)) + timedelta(minutes=i) for i in range(180)}
        if product not in NIGHT_TO_23 and evening_state_now == "active"
        else minute_range(day, time(21, 0), evening_end)
        if evening_state_now == "active" else set()
    )
    early_end = time(1, 0) if product in NIGHT_TO_01 else time(2, 30)
    early = minute_range(day, time(0, 0), early_end) if early_state_prev == "active" else set()
    return {"day": day_grid, "early": early, "evening": evening,
            "early_state": early_state_prev, "evening_state": evening_state_now,
            "early_reason": early_reason, "evening_reason": evening_reason}


def observed_moments(parquet_path: Path, proof_path: Path, symbol: str) -> tuple[set[datetime], str]:
    import pandas as pd

    if not parquet_path.is_file() or not proof_path.is_file():
        return set(), "parquet_or_proof_missing"
    try:
        proof = json.loads(proof_path.read_text(encoding="utf-8"))
        digest = hashlib.sha256(parquet_path.read_bytes()).hexdigest()
        if proof.get("sha256") != digest:
            return set(), "proof_sha256_mismatch"
        if symbol not in proof.get("all_cached_symbols", []):
            return set(), "symbol_missing_from_proof"
        frame = pd.read_parquet(parquet_path, columns=["vt_symbol", "bar_datetime"])
        frame = frame.loc[frame["vt_symbol"].astype(str).eq(symbol)]
        moments = pd.to_datetime(frame["bar_datetime"], errors="coerce")
        if moments.isna().any() or moments.dt.tz is not None:
            return set(), "minute_timestamp_invalid"
        if moments.duplicated().any():
            return set(), "duplicate_minute"
        if not moments.dt.second.eq(0).all() or not moments.dt.microsecond.eq(0).all():
            return set(), "minute_not_aligned"
        return {moment.to_pydatetime() for moment in moments}, "ok"
    except (OSError, ValueError, KeyError, TypeError):
        return set(), "parquet_or_proof_unreadable"


def compact_ranges(moments: set[datetime]) -> list[str]:
    ordered = sorted(moments)
    if not ordered:
        return []
    groups: list[tuple[datetime, datetime]] = []
    first = previous = ordered[0]
    for moment in ordered[1:]:
        if moment - previous != timedelta(minutes=1):
            groups.append((first, previous))
            first = moment
        previous = moment
    groups.append((first, previous))
    return [f"{first:%Y-%m-%d %H:%M}..{last:%H:%M}" for first, last in groups]


def audit_key(symbol: str, day_string: str, calendar: set[date], minute_dir: Path) -> dict[str, Any]:
    day = date.fromisoformat(day_string)
    expected = expected_sessions(symbol, day, calendar)
    stem = day.strftime("%Y%m%d")
    observed, source_status = observed_moments(
        minute_dir / f"{stem}.parquet", minute_dir / f"{stem}_proof.json", symbol
    )
    missing_day = expected["day"] - observed
    missing_early = expected["early"] - observed
    missing_evening = expected["evening"] - observed
    unexpected = observed - (expected['day'] | expected['early'] | expected['evening'])
    unknown = expected["evening_state"] == "unknown" or expected["early_state"] == "unknown"
    status = "missing" if missing_day or missing_early or missing_evening or source_status != "ok" else "unknown" if unknown else "unexpected" if unexpected else "complete"
    return {
        "vt_symbol": symbol, "entry_date": day_string, "product": product_of(symbol),
        "status": status, "source_status": source_status,
        "day_expected": len(expected["day"]), "day_observed": len(expected["day"] & observed),
        "day_missing": len(missing_day),
        "early_state": expected["early_state"], "early_reason": expected["early_reason"],
        "early_expected": len(expected["early"]), "early_observed": len(expected["early"] & observed),
        "early_missing": len(missing_early),
        "evening_state": expected["evening_state"], "evening_reason": expected["evening_reason"],
        "evening_expected": len(expected["evening"]), "evening_observed": len(expected["evening"] & observed),
        "evening_missing": len(missing_evening),
        "missing_ranges": compact_ranges(missing_day | missing_early | missing_evening),
        "unexpected_count": len(unexpected), "unexpected_ranges": compact_ranges(unexpected),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--minute-dir", type=Path, required=True)
    parser.add_argument("--coverage", type=Path, action="append", required=True)
    parser.add_argument("--calendar-extra-date", action="append", default=[],
                        help="补充日线库尾端尚未结算的已证实交易日；需同时给出来源")
    parser.add_argument("--calendar-extra-source", help="额外交易日的交易所原始公告或行情 URL")
    parser.add_argument("--output", type=Path, required=True, help="JSON/CSV 共同输出前缀")
    args = parser.parse_args()
    keys = read_coverage(args.coverage)
    dates = [date.fromisoformat(day) for _, day in keys]
    db_path = args.repo_root / ".vntrader" / "database.db"
    calendar = trading_dates(db_path, min(dates), max(dates))
    if args.calendar_extra_date and not args.calendar_extra_source:
        parser.error("--calendar-extra-date requires --calendar-extra-source")
    if args.calendar_extra_source and not args.calendar_extra_date:
        parser.error("--calendar-extra-source requires --calendar-extra-date")
    if args.calendar_extra_source and not args.calendar_extra_source.startswith("https://"):
        parser.error("calendar extra source must be an https URL")
    extra_dates = {date.fromisoformat(value) for value in args.calendar_extra_date}
    calendar.update(extra_dates)
    rows = [audit_key(symbol, day, calendar, args.minute_dir) for symbol, day in sorted(keys)]
    counts = {status: sum(row["status"] == status for row in rows) for status in ("complete", "missing", "unknown", "unexpected")}
    summary = {
        "status": "complete" if counts["complete"] == len(rows) else "incomplete",
        "coverage_files": [str(path.resolve()) for path in args.coverage],
        "minute_dir": str(args.minute_dir.resolve()), "calendar_db": str(db_path.resolve()),
        "calendar_extra_dates": sorted(value.isoformat() for value in extra_dates),
        "calendar_extra_source": args.calendar_extra_source,
        "keys": len(rows), "counts": counts,
        "night_missing_minutes": sum(row["early_missing"] + row["evening_missing"] for row in rows),
        "day_missing_minutes": sum(row["day_missing"] for row in rows),
        "calendar_first": min(calendar).isoformat(), "calendar_last": max(calendar).isoformat(),
        "rows": rows,
    }
    output_json = args.output.with_suffix(".json")
    output_csv = args.output.with_suffix(".csv")
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    with output_csv.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, list) else value
                             for key, value in row.items()})
    print(json.dumps({key: summary[key] for key in ("status", "keys", "counts", "night_missing_minutes", "day_missing_minutes")}, ensure_ascii=False))
    print(f"audit_json={output_json}\naudit_csv={output_csv}")
    return 0 if summary["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
