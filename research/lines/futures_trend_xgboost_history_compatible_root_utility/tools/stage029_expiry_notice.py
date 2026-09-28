from __future__ import annotations

import importlib.util
import json
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("notice_coverage029", ROOT / "tools/stage028_chain_coverage.py")
coverage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(coverage)
base = coverage.base
SOURCES = ROOT / "artifacts/stage029_expiry_notice_sources"
OUTPUT = ROOT / "artifacts/stage029_corrected_chain_coverage"
CONTRACT = ROOT / "stages/20260906_0701_stage029_expiry_notice_contract.md"


def apply_notice(catalog, notice):
    corrected = catalog.copy(deep=True)
    coverage.dates([notice["published_on"], notice["available_on"]])
    if notice["available_on"] < notice["published_on"] or catalog.tq_symbol.duplicated().any():
        raise ValueError("notice_time_or_catalog_invalid")
    records = notice["contracts"]
    if len({r["tq_symbol"] for r in records}) != len(records):
        raise ValueError("duplicate_notice_contract")
    audit = []
    for row in records:
        coverage.dates([row["last_trade_date"]])
        if notice["available_on"] >= row["last_trade_date"]:
            raise ValueError("notice_not_available_before_last_day")
        selected = corrected.tq_symbol.eq(row["tq_symbol"])
        before = corrected.loc[selected, "expire_date"].iloc[0] if selected.any() else None
        if before is not None and notice["available_on"] >= before:
            raise ValueError("notice_after_old_expiry")
        corrected.loc[selected, "expire_date"] = row["last_trade_date"]
        audit.append({**row, "old_expire_date": before, "notice_id": notice["notice_id"],
            "published_on": notice["published_on"], "available_on": notice["available_on"],
            "status": "corrected" if before is not None else "outside_research_catalog"})
    return corrected, pd.DataFrame(audit)


def yearbook_row(text, symbol):
    lines = re.findall(r"^\s*" + re.escape(symbol) + r"\b.*$", text, re.M)
    if len(lines) != 2:
        raise ValueError("yearbook_contract_rows_ambiguous")
    values = []
    for line, expected_dates in zip(lines, [4, 3], strict=True):
        matches = list(re.finditer(r"\b\d{8}\b", line))
        if len(matches) != expected_dates:
            raise ValueError("yearbook_date_columns_ambiguous")
        date = datetime.strptime(matches[-1].group(), "%Y%m%d").date().isoformat()
        quantity = float(re.sub(r"[,\s]", "", line[matches[-2].end():matches[-1].start()]))
        values.append((date, quantity))
    return dict(symbol=symbol, close_date=values[0][0], close=values[0][1],
                oi_date=values[1][0], close_oi=values[1][1])


def parse_notice(html):
    text = re.sub(r"\s+", "", BeautifulSoup(html, "html.parser").get_text())
    if "上期发〔2020〕66号" not in text or "上海期货交易所2020年3月12日" not in text:
        raise ValueError("notice_identity_not_matched")
    result = dict(notice_id="SHFE[2020]66", published_on="2020-03-12", available_on="2020-03-13",
        source_kind="issuer_notice_republished_by_member", historical_web_vintage_proven=False, contracts=[])
    for number in ["一", "二"]:
        matches = re.findall(number + r"、(.+?)的最后交易日为(\d{4})年(\d{1,2})月(\d{1,2})日", text)
        if len(matches) != 1:
            raise ValueError("notice_clause_ambiguous")
        symbols, year, month, day = matches[0]
        date = datetime(int(year), int(month), int(day)).date().isoformat()
        for symbol in re.findall(r"[A-Z]{1,2}\d{4}", symbols):
            result["contracts"].append(dict(tq_symbol="SHFE." + symbol.lower(), last_trade_date=date))
    if len(result["contracts"]) != 14:
        raise ValueError("notice_contract_count_changed")
    return result


def run():
    if OUTPUT.exists():
        raise RuntimeError("notice_correction_output_exists")
    if base.identity(SOURCES / "notice.html")["sha256"] != "e7ce1c52ca3f3f59444424d159671e68ab7fa78ae3eef088ac2e10936164488b":
        raise RuntimeError("notice_body_changed")
    if base.identity(SOURCES / "shfe_2021.pdf")["sha256"] != "6e5ffed87c1f0865ca05bc6bab25d39f8c4d701a30dcf185420faf56b803ce83":
        raise RuntimeError("yearbook_pdf_changed")
    original = json.loads((coverage.OUTPUT / "summary.json").read_text())
    if original["status"] != "chain_event_coverage_fail_no_features":
        raise RuntimeError("original_coverage_identity_invalid")
    sources = json.loads((coverage.OUTPUT / "input_manifest.json").read_text())
    sources.update({v["path"]: v for v in original["outputs"].values()})
    for path, value in sources.items():
        if base.identity(path) != value:
            raise RuntimeError("original_coverage_inputs_changed")
    paths = list(SOURCES.iterdir()) + [Path(__file__), CONTRACT, coverage.OUTPUT / "summary.json",
        ROOT / "tests/test_stage029_expiry_notice.py"]
    sources.update({str(p): base.identity(p) for p in paths if p.is_file()})
    OUTPUT.mkdir(parents=True)
    base.save(OUTPUT / "input_manifest.json", sources)
    report = dict(status="running", started_at=datetime.now().astimezone().isoformat(),
        reviewer_count=0, label_read_count=0, model_fit_predict_count=0, strategy_backtest_count=0,
        production_write_count=0, historical_listing_universe_proven=False, historical_vintage_proven=False)
    try:
        notice = parse_notice((SOURCES / "notice.html").read_text())
        catalog = pd.read_csv(coverage.CATALOG)
        corrected, audit = apply_notice(catalog, notice)
        applied = audit[audit.status.eq("corrected")]
        if len(applied) != 5 or not applied.old_expire_date.eq("2021-02-18").all():
            raise RuntimeError("notice_catalog_intersection_changed")
        pages = json.loads((SOURCES / "table_page_index.json").read_text())
        table_rows = []
        for row in applied.itertuples():
            symbol = row.tq_symbol.split(".")[1]
            page = pages[symbol]
            if len(page) != 1:
                raise RuntimeError("yearbook_page_ambiguous")
            official = yearbook_row((SOURCES / f"page_{page[0]:03d}.txt").read_text(), symbol)
            if official["close_date"] != row.last_trade_date or official["oi_date"] != row.last_trade_date:
                raise RuntimeError("yearbook_notice_date_mismatch")
            raw_paths = list(coverage.SOURCE.glob(f"batch_*/{row.tq_symbol}.daily.csv.gz"))
            if len(raw_paths) != 1:
                raise RuntimeError("source_contract_path_ambiguous")
            data = pd.read_csv(raw_paths[0], usecols=["trade_date", "close", "close_oi"])
            last = data.loc[data.trade_date.eq(row.last_trade_date)]
            if len(last) != 1 or any(float(last[k].iloc[0]) != official[k] for k in ["close", "close_oi"]):
                raise RuntimeError("yearbook_native_last_values_mismatch")
            table_rows.append({**official, "pdf_page": page[0], "native_close_oi_exact": True, "native_close_exact": True})
        bars = pd.read_csv(coverage.OUTPUT / "source_bars.csv.gz", float_precision="round_trip")
        calendar = pd.read_csv(coverage.OUTPUT / "calendar.csv").date.tolist()
        events = pd.read_csv(base.EVENTS, usecols=coverage.EVENT_COLUMNS)
        chain, gaps, lifetime = coverage.audit_chain(bars, corrected, calendar)
        covered = coverage.event_coverage(events, bars, corrected, chain, calendar)
        a_days = pd.read_csv(coverage.CALENDAR, usecols=["date"]).date.tolist()
        pairs = [(day, product) for day in a_days for product in sorted(catalog.product_vt_symbol.unique())]
        full = coverage.windows([x[0] for x in pairs], [x[1] for x in pairs], chain, calendar)
        for name, value in {"corrected_catalog.csv.gz": corrected, "notice_applicability.csv": audit,
            "official_yearbook_comparison.csv": pd.DataFrame(table_rows), "chain_daily.csv.gz": chain,
            "missing_contract_days.csv.gz": gaps, "observed_lifetimes.csv": lifetime,
            "event_coverage.csv": covered, "a_calendar_coverage.csv.gz": full}.items():
            value.to_csv(OUTPUT / name, index=False)
        base.save(OUTPUT / "notice.json", notice)
        ready = bool(gaps.empty and covered.coverage_status.eq("available").all())
        report.update(status="corrected_event_source_qualified_not_model" if ready else "corrected_source_fail_no_features",
            corrected_contracts=len(applied), notice_contracts=len(notice["contracts"]),
            event_count=len(covered), event_status_counts=covered.coverage_status.value_counts().to_dict(),
            missing_contract_days=len(gaps), chain_status_counts=chain.coverage_status.value_counts().to_dict(),
            calendar_status_counts=full.coverage_status.value_counts().to_dict(),
            official_yearbook_verified_contracts=len(table_rows))
        if any(base.identity(path) != value for path, value in sources.items()):
            raise RuntimeError("notice_inputs_changed")
        report["inputs_unchanged"] = True
    except Exception as exc:
        report.update(status="correction_technical_failure", error_type=type(exc).__name__, error=str(exc))
        raise
    finally:
        report["finished_at"] = datetime.now().astimezone().isoformat()
        report["outputs"] = {p.name: base.identity(p) for p in sorted(OUTPUT.iterdir()) if p.name != "summary.json"}
        base.save(OUTPUT / "summary.json", report)
    print(json.dumps({k: v for k, v in report.items() if k != "outputs"}), flush=True)


if __name__ == "__main__":
    run()
