"""Explicit stock corporate actions; never infer dividends from price factors.

The accounting consumer still credits gross cash and new shares on ex-date.
Payment-date, withholding tax and separate share-listing delays are not modeled.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from io import StringIO
from pathlib import Path
import re
import tempfile
import time
from types import FunctionType, SimpleNamespace

import pandas as pd
import requests


SINA_COLUMNS = ["公告日期", "送股", "转增", "派息", "进度", "除权除息日", "股权登记日", "红股上市日"]
EXECUTION_SEMANTICS = {
    "cash_dividend": "gross before-tax cash per share credited on ex-date; payment-date and withholding-tax timing not modeled",
    "split_ratio": "bonus and capitalisation shares credited and saleable on ex-date; separate share-listing delay not modeled",
}
DATA_LIMITATIONS = ["cash_dividend_before_tax_on_ex_date", "bonus_shares_available_on_ex_date", "sina_display_precision", "rights_issues_not_modeled", "per_account_cash_cent_rounding_not_modeled"]


def _window(start: str, end: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    first, last = pd.Timestamp(start), pd.Timestamp(end)
    if pd.isna(first) or pd.isna(last) or first > last:
        raise ValueError("Invalid corporate-action date window")
    return first.normalize(), last.normalize()


def _number(value, *, allow_blank: bool = False) -> Decimal:
    if allow_blank and isinstance(value, str) and not value.strip():
        return Decimal(0)
    try:
        result = Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Invalid corporate-action amount: {value!r}") from exc
    if not result.is_finite() or result < 0:
        raise ValueError(f"Invalid corporate-action amount: {value!r}")
    return result


def _missing_cash(value) -> bool:
    return pd.isna(value) or (isinstance(value, str) and value.strip() in {"", "--"})


def _recover_bao_cash(frame: pd.DataFrame, row, date: pd.Timestamp, corroborating: dict) -> tuple[Decimal, dict]:
    peers = frame.loc[pd.to_datetime(frame["dividOperateDate"], errors="coerce").eq(date)]
    values = {_number(value) for value in peers["dividCashPsBeforeTax"] if not _missing_cash(value)}
    plan = str(row.get("dividCashStock", ""))
    plan_values = {Decimal(value) / 10 for value in re.findall(r"10(?:股)?派([0-9]+(?:\.[0-9]+)?)元", plan)}
    number = r"[0-9]+(?:\.[0-9]+)?"
    pure_shares = re.fullmatch(rf"10(?:股)?(?:送(?P<bonus>{number})(?:股)?(?:转(?P<capital>{number})(?:股)?)?|转(?P<capital_only>{number})(?:股)?)", re.sub(r"\s+", "", plan))
    reference = corroborating.get(date)
    if pure_shares:
        bonus = Decimal(pure_shares.group("bonus") or "0") / 10
        capital = Decimal(pure_shares.group("capital") or pure_shares.group("capital_only") or "0") / 10
        if (bonus != _number(row["dividStocksPs"], allow_blank=True)
                or capital != _number(row["dividReserveToStockPs"], allow_blank=True)
                or reference is None or reference["cash"] != 0 or reference["split"] != 1 + bonus + capital):
            raise ValueError(f"Conflicting pure-share cash recovery evidence on {date.date()}")
        plan_values = {Decimal(0)}
    if len(values) > 1 or len(plan_values) > 1 or (values and plan_values and values != plan_values):
        raise ValueError(f"Conflicting cash recovery evidence on {date.date()}")
    candidates = values or plan_values
    if len(candidates) != 1 or reference is None or next(iter(candidates)) != reference["cash"]:
        raise ValueError(f"Unresolved missing Baostock cash on {date.date()}")
    cash = next(iter(candidates))
    reason = "complete_peer_and_sina" if values else ("pure_share_plan_and_sina_zero" if pure_shares else "explicit_plan_and_sina")
    return cash, {"date": date.strftime("%Y-%m-%d"), "cash_per_share": str(cash), "reason": reason, "plan_text": plan,
                  "sina_cash_per_share": str(reference["cash"]), "sina_split_ratio": str(reference["split"])}


def _records(frame: pd.DataFrame, *, start: str, end: str, source: str, corroborating: dict | None = None) -> tuple[dict, dict]:
    first, last = _window(start, end)
    records: dict = {}
    counts = {"raw_count": len(frame), "duplicate_count": 0, "excluded_count": 0, "recovered_cash_count": 0, "cash_recoveries": []}
    if frame.empty:
        return records, counts
    columns = SINA_COLUMNS if source == "sina" else ["dividOperateDate", "dividCashPsBeforeTax", "dividStocksPs", "dividReserveToStockPs"]
    missing = set(columns) - set(frame.columns)
    if missing:
        raise ValueError(f"Missing {source} corporate-action columns: {sorted(missing)}")
    for _, row in frame.iterrows():
        date = pd.to_datetime(row["除权除息日" if source == "sina" else "dividOperateDate"], errors="coerce")
        if pd.isna(date) or not first <= date <= last or (source == "sina" and str(row["进度"]).strip() != "实施"):
            counts["excluded_count"] += 1
            continue
        date = pd.Timestamp(date).normalize()
        display_quantum = None
        if source == "sina":
            cash_text = row.get("_sina_cash_raw", row["派息"])
            raw_cash = _number(cash_text)
            if isinstance(cash_text, str):
                display_quantum = Decimal(1).scaleb(raw_cash.as_tuple().exponent)
            cash = raw_cash / 10
            split = 1 + (_number(row["送股"]) + _number(row["转增"])) / 10
        else:
            if _missing_cash(row["dividCashPsBeforeTax"]):
                raw_cash, evidence = _recover_bao_cash(frame, row, date, corroborating or {})
                counts["cash_recoveries"].append(evidence)
                counts["recovered_cash_count"] += 1
            else:
                raw_cash = _number(row["dividCashPsBeforeTax"])
                if isinstance(row["dividCashPsBeforeTax"], str):
                    display_quantum = Decimal(1).scaleb(raw_cash.as_tuple().exponent)
            cash = raw_cash
            split = 1 + _number(row["dividStocksPs"], allow_blank=True) + _number(row["dividReserveToStockPs"], allow_blank=True)
        event = {"cash": cash, "split": split, "raw_cash": raw_cash, "display_quantum": display_quantum}
        if date in records:
            previous = records[date]
            if (previous["cash"], previous["split"]) != (cash, split):
                raise ValueError(f"Conflicting {source} corporate actions on {date.date()}")
            if display_quantum is not None and (previous["display_quantum"] is None or display_quantum < previous["display_quantum"]):
                records[date] = event  # Keep the strictest displayed-precision evidence.
            counts["duplicate_count"] += 1
        else:
            records[date] = event
    return records, counts


def _frame(records: dict) -> pd.DataFrame:
    result = pd.DataFrame([
        {"date": date, "cash_dividend": float(event["cash"]), "split_ratio": float(event["split"])}
        for date, event in sorted(records.items())
    ], columns=["date", "cash_dividend", "split_ratio"])
    return result.astype({"date": "datetime64[ns]", "cash_dividend": "float64", "split_ratio": "float64"})


def normalize_sina_actions(frame: pd.DataFrame, *, start: str, end: str) -> pd.DataFrame:
    """Normalize implemented Sina per-ten-share events, deduplicating announcements."""
    records, _ = _records(frame, start=start, end=end, source="sina")
    return _frame(records)


_NOTICE_RULES = (
    dict(symbol="000333.SZSE", date="2021-06-02", bao=("1.600585",), sina="1.60058", total="1.6005847", notice_id="2021-049", notice_date="2021-05-26", record_date="2021-06-01",
         source_url="https://pdf.dfcfw.com/pdf/H2_AN202105261494005519_1.pdf", pdf_sha256="3ae86625494a29dbf4f5032d366698e9c428a93811083c57230420f76670ee1c",
         reason="company_notice_exact_cash_display_disambiguation", components=("1.6005847",), price_reference_note="notice gross cash is 16.005847 per ten shares; displayed sources suffer double rounding; price deduction 1.57 is not investor cash; raw preclose and factors are unchanged"),
    dict(symbol="000671.SZSE", date="2021-07-05", bao=("0.380642",), sina="0.380643", total="0.3806425", notice_id="2021-123", notice_date="2021-06-26", record_date="2021-07-02",
         source_url="https://pdf.dfcfw.com/pdf/H2_AN202106251499975801_1.pdf", pdf_sha256="047e666fde93d41623c63faf5213108d6885920e11b1e3c6286761b23f070576",
         reason="company_notice_exact_cash_display_disambiguation", components=("0.3806425",), price_reference_note="notice gross cash is 3.806425 per ten shares; Baostock rounding algorithm is unverified; price deduction 0.3784084 is not investor cash; raw preclose and factors are unchanged"),
    dict(symbol="002352.SZSE", date="2024-11-07", bao=("1.4",), sina="0.4", total="1.4", notice_id="2024-098", notice_date="2024-10-31", record_date="2024-11-06",
         source_url="https://pdf.dfcfw.com/pdf/H2_AN202410301640607006_1.pdf", pdf_sha256="338b6f3fe077d74966638cf0caf937e0d5e53aa86d06ed518b23e15c94cdc871",
         reason="company_notice_regular_plus_special_cash", components=("0.4", "1.0"), price_reference_note="interim 0.4 and special 1.0 are paid together; ex-price cash deduction 1.3939620 is not investor cash 1.4; raw preclose and factors are unchanged"),
    dict(symbol="002709.SZSE", date="2026-04-29", bao=("0.3",), sina="0.2", total="0.3", notice_id="2026-055", notice_date="2026-04-22", record_date="2026-04-28",
         source_url="https://disc.static.szse.cn/disc/disk03/finalpage/2026-04-22/918991c8-79bf-4509-8152-0ba427c1b429.PDF", pdf_sha256="cbdd94149088dc264f69f551711d00a3801936f9f1ddf3b421303b861723757e",
         reason="company_notice_regular_plus_special_cash", components=("0.2", "0.1"), price_reference_note="annual 0.2 and special 0.1 are paid together; ex-price cash deduction 0.2987497 is not investor cash 0.3; raw preclose and factors are unchanged"),
    dict(symbol="301308.SZSE", date="2026-06-02", bao=("0.34676", "0.643984"), sina="0.34676", total="0.9907442", notice_id="2026-065", notice_date="2026-05-26", record_date="2026-06-01",
         source_url="https://static.cninfo.com.cn/finalpage/2026-05-26/1225331662.PDF", pdf_sha256="25ec59eab647f69b51f34936fef2a23f937f5d86c081f4b9d25e983a4f8c8a40",
         reason="company_notice_combined_exact_cash", components=(), price_reference_note="notice publishes adjusted annual plus interim total 9.907442 per ten shares, not separate adjusted components; summing rounded vendor fields loses 0.0000002 per share; account-level cent truncation is not modeled; raw preclose and factors are unchanged"),
    dict(symbol="600025.SSE", date="2020-06-19", bao=("0.14913",), sina="0.18", total="0.18", notice_id="2020-028", notice_date="2020-06-12", record_date="2020-06-18",
         source_url="https://pdf.dfcfw.com/pdf/H2_AN202006111384194389_1.pdf", pdf_sha256="316b5b0cd8667807c3697319a66473571e9a0958a1058ea072ce8a7ef2abc2ca",
         reason="company_notice_public_share_cash", components=("0.18",), price_reference_note="notice ex-price cash deduction is 0.15; raw preclose and factors are unchanged"),
    dict(symbol="600803.SSE", date="2024-08-01", bao=("0.91",), sina="0.66", total="0.91", notice_id="2024-056", notice_date="2024-07-26", record_date="2024-07-31",
         source_url="https://static.cninfo.com.cn/finalpage/2024-07-26/1220731024.PDF", pdf_sha256="c610a0242cc13bbde06917cfaad3549365afc16e10a5bf278b4751f5be497917",
         reason="company_notice_regular_plus_special_cash", components=("0.66", "0.25"), price_reference_note="notice ex-price cash deduction is 0.9054, not investor cash 0.91; raw preclose and factors are unchanged"),
    dict(symbol="600803.SSE", date="2025-07-22", bao=("1.03",), sina="0.81", total="1.03", notice_id="2025-061", notice_date="2025-07-16", record_date="2025-07-21",
         source_url="https://file.finance.sina.com.cn/211.154.219.97%3A9494/MRGG/CNSESH_STOCK/2025/2025-7/2025-07-16/11240864.PDF", pdf_sha256="a47a387e531faaf13584f3b88a6d2af998427e034298e1503ada7146b6921f99",
         reason="company_notice_regular_plus_special_cash", components=("0.81", "0.22"), price_reference_note="cash total includes regular and special distribution; raw preclose and factors are unchanged"),
    dict(symbol="600989.SSE", date="2021-05-20", bao=("0.32091", "0.26472"), sina="0.32091", total="0.32091", notice_id="2021-026", notice_date="2021-05-12", record_date="2021-05-19",
         source_url="https://pdf.dfcfw.com/pdf/H2_AN202105111491094056_1.pdf", pdf_sha256="18570ede629e1cadef96c4ce83a8a44b8121a5b01f0c09b9679c10540718d40b",
         reason="company_notice_unrestricted_public_share_cash", components=("0.32091",), price_reference_note="restricted shares receive 0.26472; notice ex-price cash deduction is 0.28, not public cash 0.32091; raw preclose and factors are unchanged"),
    dict(symbol="600989.SSE", date="2020-06-04", bao=("0.27545",), sina="0.32091", total="0.32091", notice_id="2020-017", notice_date="2020-05-29", record_date="2020-06-03",
         source_url="https://pdf.dfcfw.com/pdf/H2_AN202005281380413497_1.pdf", pdf_sha256="c57baa032be861e871985022dd8b5f8a8dc48e8a83bd0b7981b1acd98b53de8b",
         reason="company_notice_unrestricted_public_share_cash", components=("0.32091",), price_reference_note="pre-IPO restricted shares receive 0.27545, not public cash 0.32091; raw preclose and factors are unchanged"),
    dict(symbol="600989.SSE", date="2022-05-12", bao=("0.2648",), sina="0.321", total="0.3210", notice_id="2022-018", notice_date="2022-05-05", record_date="2022-05-11",
         source_url="https://pdf.dfcfw.com/pdf/H2_AN202205041563491509_1.pdf", pdf_sha256="77c7945236346f652800a271f942a9610c3960538e011146aedd9860afb39bc8",
         reason="company_notice_unrestricted_public_share_cash", components=("0.3210",), price_reference_note="restricted shares receive 0.2648, not public cash 0.3210; raw preclose and factors are unchanged"),
    dict(symbol="600989.SSE", date="2022-12-27", bao=("0.1216",), sina="0.1841", total="0.1841", notice_id="2022-041", notice_date="2022-12-21", record_date="2022-12-26",
         source_url="https://pdf.dfcfw.com/pdf/H2_AN202212201581238778_1.pdf", pdf_sha256="d0ce17862db32ba2dde975b62dcc2286d16188ee59e287589f1969edaad909d0",
         reason="company_notice_unrestricted_public_share_cash", components=("0.1841",), price_reference_note="restricted shares receive 0.1216, not public cash 0.1841; raw preclose and factors are unchanged"),
    dict(symbol="600989.SSE", date="2026-04-28", bao=("0.42",), sina="0.4921", total="0.4921", notice_id="2026-029", notice_date="2026-04-22", record_date="2026-04-27",
         source_url="https://epaper.stcn.com/pic/202604/22/ccefab7c0770a5deda54386606e1a1be.pdf", pdf_sha256="68a8d9fb516c8d329afa75e44ff8a8281e52ba1e8d4143f0fd1b81305e2b127e",
         reason="company_notice_public_share_cash", components=("0.4921",), price_reference_note="large shareholders receive 0.3906; average and ex-price cash deduction is 0.42, not public cash 0.4921; raw preclose and factors are unchanged"),
    dict(symbol="600989.SSE", date="2024-07-24", bao=("0.28",), sina="0.3158", total="0.3158", notice_id="2024-040", notice_date="2024-07-18", record_date="2024-07-23",
         source_url="https://file.finance.sina.com.cn/211.154.219.97%3A9494/MRGG/CNSESH_STOCK/2024/2024-7/2024-07-18/10334213.PDF", pdf_sha256="d47db5c0b7d2c9bfc37dbc71cfdd2e34ed299948baaad08e7fadedb6fa2dde86",
         reason="company_notice_public_share_cash", components=("0.3158",), price_reference_note="large shareholders receive 0.2650; average and ex-price cash deduction is 0.28, not public cash 0.3158; raw preclose and factors are unchanged"),
    dict(symbol="600989.SSE", date="2025-05-13", bao=("0.409993",), sina="0.4598", total="0.4598", notice_id="2025-016", notice_date="2025-05-07", record_date="2025-05-12",
         source_url="https://stockn.xueqiu.com/SH600989/20250506679894.pdf", pdf_sha256="1a9e10e1bd1ba1e5ea3493a8c8dab9e1a70e2211de015c60c4ec97312a968f60",
         reason="company_notice_public_share_cash", components=("0.4598",), price_reference_note="large shareholders receive 0.3891; average and ex-price cash deduction is 0.41, not public cash 0.4598; raw preclose and factors are unchanged"),
    dict(symbol="601966.SSE", date="2024-06-14", bao=("0.286", "0.091"), sina="0.286", total="0.377", notice_id="2024-038", notice_date="2024-06-07", record_date="2024-06-13",
         source_url="https://epaper.stcn.com/pic/202406/07/39b5d9d80fd564560fbcddfe5394f4bf.pdf", pdf_sha256="45d621e95afe303b3ed6915ee0966cb5722c0651203e9062967e200592e50b24",
         reason="company_notice_separate_period_components", components=("0.286", "0.091"), price_reference_note="notice ex-price cash deduction is 0.37444, not investor cash 0.377; raw preclose and factors are unchanged"),
    dict(symbol="601966.SSE", date="2025-07-10", bao=("0.07",), sina="0.014", total="0.084", notice_id="2025-044", notice_date="2025-07-03", record_date="2025-07-09",
         source_url="https://static.cninfo.com.cn/finalpage/2025-07-03/1224067624.PDF", pdf_sha256="75ae0bb2d5a1a2715aaca1d26b15f0f296dc2ce9848e8cc074ed52ede183eab2",
         reason="company_notice_separate_period_components", components=("0.014", "0.07"), price_reference_note="2024 Q4 and 2025 Q1 distributions paid together; raw preclose and factors are unchanged"),
)


def _notice_events(frame: pd.DataFrame, sina: dict, *, symbol: str | None, start: str, end: str) -> tuple[pd.DataFrame, dict, list, int]:
    """Apply only independently verified source tuples, never generic same-day sums."""
    first, last = _window(start, end)
    remaining, events, audit, duplicates = frame, {}, [], 0
    for rule in _NOTICE_RULES:
        date = pd.Timestamp(rule["date"])
        if symbol != rule["symbol"] or not first <= date <= last:
            continue
        mask = pd.to_datetime(remaining.get("dividOperateDate", pd.Series(index=remaining.index, dtype="object")), errors="coerce").eq(date)
        rows, reference = remaining.loc[mask], sina.get(date)
        if rows.empty and reference is None:
            continue
        economics = {(_number(row["dividCashPsBeforeTax"]), 1 + _number(row["dividStocksPs"], allow_blank=True) + _number(row["dividReserveToStockPs"], allow_blank=True)) for _, row in rows.iterrows()}
        expected = {(Decimal(value), Decimal(1)) for value in rule["bao"]}
        if economics != expected or reference is None or reference["cash"] != Decimal(rule["sina"]) or reference["split"] != 1:
            raise ValueError(f"Conflicting company-notice source evidence: {symbol} {date.date()}")
        duplicates += len(rows) - len(economics)
        remaining = remaining.loc[~mask]
        value = Decimal(rule["total"])
        events[date] = {"cash": value, "split": Decimal(1), "raw_cash": value, "display_quantum": None}
        audit.append({
            **{key: rule[key] for key in ("symbol", "date", "reason", "notice_id", "notice_date", "record_date", "source_url", "pdf_sha256", "price_reference_note")},
            "original_cash_per_share": "+".join(sorted(rule["bao"])), "original_baostock_cash_components": sorted(rule["bao"]),
            "original_sina_cash_per_share": rule["sina"], "notice_components_per_share": list(rule["components"]),
            "resolved_cash_per_share": rule["total"], "applicable_shareholder": "public_A_shareholder", "payment_date": rule["date"],
        })
    return remaining, events, audit, duplicates


def merge_actions(baostock_actions: pd.DataFrame, sina_raw: pd.DataFrame, *, start: str, end: str, symbol: str | None = None) -> tuple[pd.DataFrame, dict]:
    """Keep finer evidenced precision; supplement dates, never sum duplicates.

    Both original numeric strings must exist. The finer value must round exactly
    to the coarser source's displayed value, within its half-step and 0.00005/share.
    Every such exception is audited. Share-ratio conflicts always fail closed.
    An explicit vt symbol enables only the audited source tuples in _NOTICE_RULES;
    absent identity never enables an announcement override.
    """
    sina, sina_counts = _records(sina_raw, start=start, end=end, source="sina")
    remaining, noticed, resolutions, notice_duplicates = _notice_events(baostock_actions, sina, symbol=symbol, start=start, end=end)
    bao, bao_counts = _records(remaining, start=start, end=end, source="baostock", corroborating=sina)
    bao_counts["raw_count"] = len(baostock_actions)
    bao_counts["duplicate_count"] += notice_duplicates
    bao.update(noticed)
    differences, sources = [], {}
    merged = dict(bao)
    for date, event in sina.items():
        if date not in bao:
            merged[date] = event
            sources[date.strftime("%Y-%m-%d")] = "sina_supplement"
            continue
        preferred = bao[date]
        if date in noticed:
            sources[date.strftime("%Y-%m-%d")] = "company_notice_resolution"
            continue
        if preferred["split"] != event["split"]:
            raise ValueError(f"Conflicting share ratios on {date.date()}")
        if preferred["cash"] != event["cash"]:
            bao_quantum, sina_raw_quantum = preferred["display_quantum"], event["display_quantum"]
            difference = preferred["cash"] - event["cash"]
            if bao_quantum is None or sina_raw_quantum is None:
                raise ValueError(f"Conflicting cash without original display evidence on {date.date()}")
            sina_quantum = sina_raw_quantum / 10
            select_sina = sina_quantum < bao_quantum
            coarse = bao_quantum if select_sina else sina_quantum
            high_cash, low_cash = (event["cash"], preferred["cash"]) if select_sina else (preferred["cash"], event["cash"])
            bound = min(coarse / 2, Decimal("0.00005"))
            if abs(difference) > bound or high_cash.quantize(coarse, rounding=ROUND_HALF_UP) != low_cash:
                raise ValueError(f"Conflicting cash dividends on {date.date()}: baostock={preferred['cash']} sina={event['cash']}")
            if select_sina:
                merged[date] = event
                sources[date.strftime("%Y-%m-%d")] = "sina_higher_precision"
            differences.append({"date": date.strftime("%Y-%m-%d"), "reason": "baostock_display_rounding" if select_sina else "sina_display_rounding", "selected_source": "sina" if select_sina else "baostock", "baostock_cash_per_share": str(preferred["cash"]), "sina_cash_per_ten": str(event["raw_cash"]), "baostock_display_quantum_per_share": str(bao_quantum), "sina_display_quantum_per_ten": str(sina_raw_quantum), "display_half_step_per_share": str(coarse / 2), "max_difference_per_share": str(bound), "cash_difference_per_share": str(difference)})
        sources.setdefault(date.strftime("%Y-%m-%d"), "baostock_sina_verified")
    for date in bao.keys() - sina.keys():
        sources[date.strftime("%Y-%m-%d")] = "baostock_only"
    audit = {
        **{f"baostock_{key}": value for key, value in bao_counts.items()},
        **{f"sina_{key}": value for key, value in sina_counts.items()},
        "baostock_only_count": len(bao.keys() - sina.keys()), "sina_only_count": len(sina.keys() - bao.keys()),
        "matched_count": len(bao.keys() & sina.keys()), "rounding_match_count": len(differences),
        "event_count": len(merged), "event_sources": dict(sorted(sources.items())), "differences": differences,
        "action_resolution_count": len(resolutions), "action_resolutions": resolutions,
        "provider": "baostock+sina", "data_limitations": list(DATA_LIMITATIONS), "execution_semantics": dict(EXECUTION_SEMANTICS),
    }
    result = _frame(merged)
    result.attrs.update({key: audit[key] for key in ("provider", "data_limitations", "execution_semantics")})
    return result, audit


def _validate_raw(frame: pd.DataFrame) -> None:
    if not isinstance(frame, pd.DataFrame) or set(SINA_COLUMNS) - set(frame.columns):
        raise ValueError("Missing Sina raw action schema; refusing empty-success cache")
    if frame.empty and frame.attrs.get("source_empty_confirmed") is not True:
        raise ValueError("Unverified empty Sina action response")


def _request_sina(symbol: str) -> pd.DataFrame:
    """Use the installed parser with private globals, never monkeypatch globals."""
    import akshare as ak
    from bs4 import BeautifulSoup

    original = ak.stock_history_dividend_detail
    session = requests.Session()
    bodies = []
    def get(url, **kwargs):
        response = session.get(url, timeout=(5, 20), **kwargs)
        response.raise_for_status()
        bodies.append(response.text)
        return response
    namespace = dict(original.__globals__)
    namespace["requests"] = SimpleNamespace(get=get)
    isolated = FunctionType(original.__code__, namespace, original.__name__, original.__defaults__, original.__closure__)
    try:
        result = isolated(symbol=symbol, indicator="分红")
    finally:
        session.close()
    if result.empty:
        if not bodies or "暂时没有数据！" not in bodies[-1]:
            raise ValueError("Sina returned empty actions without a no-data confirmation")
        result = pd.DataFrame(columns=SINA_COLUMNS)
        result.attrs["source_empty_confirmed"] = True
    else:
        # AkShare converts to float, losing trailing zeros. Keep the actual HTML
        # cash lexeme as separate evidence; never reconstruct display precision.
        html_tables = BeautifulSoup(bodies[-1], "lxml").find_all("table")
        raw_table = pd.read_html(StringIO(str(html_tables[12])), converters={3: str})[0]
        if len(raw_table) != len(result) or raw_table.shape[1] != 9:
            raise ValueError("Sina raw-display table does not align with installed parser")
        result["_sina_cash_raw"] = raw_table.iloc[:, 3].tolist()
    result.attrs["source_url"] = f"https://vip.stock.finance.sina.com.cn/corp/go.php/vISSUE_ShareBonus/stockid/{symbol}.phtml"
    _validate_raw(result)
    return result


def fetch_sina_actions(symbol: str, cache_dir: Path) -> pd.DataFrame:
    """Fetch/cache raw data in the caller's new run directory, with bounded retries.

    Corrupt caches and parser/schema failures are errors, not an empty event set.
    Only transient connection, timeout, HTTP 429/5xx errors retry (three attempts).
    """
    if not re.fullmatch(r"[0-9]{6}", symbol):
        raise ValueError("Sina symbol must be a six-digit bare stock code")
    directory = Path(cache_dir)
    path = directory / f"sina_actions_{symbol}.parquet"
    if path.exists():
        result = pd.read_parquet(path)
        _validate_raw(result)
        return result
    for attempt in range(3):
        try:
            result = _request_sina(symbol)
            _validate_raw(result)
            break
        except (requests.Timeout, requests.ConnectionError, requests.HTTPError) as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            retryable = not isinstance(exc, requests.HTTPError) or status == 429 or (status is not None and status >= 500)
            if not retryable or attempt == 2:
                raise
            time.sleep(0.1 * (2 ** attempt))
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix=f".{symbol}_", suffix=".parquet", dir=directory, delete=False) as temporary:
        temporary_path = Path(temporary.name)
    try:
        result.to_parquet(temporary_path, index=False)
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return result
