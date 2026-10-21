"""Bounded official HTTP evidence only; stop on403/429, no alternate host."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo

LINE = Path(__file__).resolve().parents[1]
ROOT = LINE / "outputs/stage408_cftc_publication_evidence"
PROTOCOL = LINE / "outputs/stage407_cot_source_years/protocol.json"
SOURCES = [
    "https://www.cftc.gov/MarketReports/CommitmentsofTraders/ReleaseSchedule/index.htm",
    "https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalSpecialAnnouncements/index.htm",
]


def now(): return datetime.now(timezone.utc).isoformat()


def bind(path):
    data = path.read_bytes()
    return {"path": str(path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def save(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + "\n")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl): return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--related-discovery")
    parser.add_argument("--compile-local", action="store_true")
    args = parser.parse_args()
    if args.compile_local:
        return compile_local()
    out = ROOT / "actual_http1"
    protocol = json.loads(PROTOCOL.read_text())
    assert protocol["clock_stage408"]["official_sources"] == SOURCES
    if args.related_discovery:
        receipt = json.loads((out / "receipt.json").read_text())
        assert not receipt["status"].startswith("stopped"), "Raw HTTP worker already stopped"
        discovery = Path(args.related_discovery).resolve()
        candidates = [r["url"] for r in json.loads(discovery.read_text())["related"]]
        receipt["related_discovery"] = bind(discovery)
        receipt["tool_at_related_pass"] = bind(Path(__file__))
    else:
        out.mkdir(parents=True, exist_ok=False)
        candidates = SOURCES
        receipt = {"schema": "stage408_bounded_official_clock_http_v1", "started_at": now(),
               "protocol": bind(PROTOCOL), "tool": bind(Path(__file__)), "requests": [],
               "maximum_GET": 16, "maximum_total_body": 8388608, "maximum_each_body": 2097152,
               "worker_concurrency": 1, "automatic_retry": 0, "duplicate_URL_GET": 0,
               "year_index_or_ZIP_reads": 0, "fit": 0, "cash": 0, "SQL": 0, "market_API": 0,
                   "status": "started"}
    seen = {r["url"] for r in receipt["requests"]}
    for index, url in enumerate(candidates, len(receipt["requests"])+1):
        assert url not in seen and len(seen) < 16
        assert url.startswith("https://www.cftc.gov/"), "Only discovered official host allowed"
        seen.add(url)
        record = {"url": url, "started_at": now(), "retry": 0, "redirect": 0}
        body = b""
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "fian-publication-evidence/408", "Accept-Encoding": "identity"})
            try:
                response = urllib.request.build_opener(NoRedirect()).open(request, timeout=30)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                record["status"] = response.code
                record["headers"] = dict(response.headers)
                declared = response.headers.get("Content-Length")
                if declared is not None and int(declared) > 2097152:
                    raise RuntimeError("declared page exceeds2MiB; no body consumed")
                body = response.read(2097153)
                if len(body) > 2097152: raise RuntimeError("page exceeded2MiB")
                record["ok"] = response.code == 200
        except BaseException as error:
            record["ok"] = False
            record["error"] = repr(error)
        path = out / f"{index:02d}_official_response.body"
        path.write_bytes(body)
        record.update(ended_at=now(), body=bind(path))
        receipt["requests"].append(record)
        save(out / "receipt.json", receipt)
        if record.get("status") in (403, 429):
            receipt["status"] = "stopped_raw_http403or429_no_fallback_requests"
            break
        if not record.get("ok"):
            receipt["status"] = "stopped_raw_http_error_no_retry"
            break
    else:
        receipt["status"] = "official_entry_pages_received_not_yet_interpreted"
    receipt.update(ended_at=now(), actual_GET=len(receipt["requests"]), body_bytes=sum(r["body"]["bytes"] for r in receipt["requests"]))
    assert receipt["body_bytes"] <= 8388608
    receipt["unrequested_entry_urls"] = [u for u in SOURCES if u not in seen]
    save(out / "receipt.json", receipt)
    print(json.dumps({"status": receipt["status"], "requests": len(receipt["requests"]),
                      "HTTP_statuses": [r.get("status") for r in receipt["requests"]], "receipt": bind(out / "receipt.json")}))


def compile_local():
    """Normalize the nine already-received official pages; never opens a socket."""
    raw = ROOT / "actual_http1"
    out = ROOT / "compiled"
    out.mkdir(exist_ok=False)
    http = json.loads((raw / "receipt.json").read_text())
    assert http["actual_GET"] == 9 and http["body_bytes"] == 459252
    assert all(r.get("status") == 200 and r["retry"] == 0 for r in http["requests"])
    assert len({r["url"] for r in http["requests"]}) == 9
    names = ["current_release_rule", "historical_special_announcements", "2013_anticipated_schedule",
             "2013_nonpublication_notice", "2019_expected_backlog_schedule", "2025_revised_intended_schedule",
             "2025_initial_intended_schedule", "about_COT_historical_rule", "2023_postponement_notice"]
    sources = []
    text_by_id = {}
    for number, (request, name) in enumerate(zip(http["requests"], names), 1):
        body = Path(request["body"]["path"])
        assert bind(body) == request["body"]
        textpath = raw / f"{number:02d}_derived_text.txt"
        sid = f"S{number:02d}"
        text_by_id[sid] = textpath.read_text().splitlines()
        sources.append({"source_id": sid, "label": name, "url": request["url"],
                        "evidence_type": "actual_HTTP200_official_HTML", "raw": bind(body),
                        "derived_text": bind(textpath), "downloaded_at_2026_UTC": request["ended_at"],
                        "historical_publication_clock_inferred_from_download": False})

    def evidence(sid, needle, end=None):
        lines = text_by_id[sid]
        hits = [i for i, line in enumerate(lines) if needle in line]
        assert len(hits) == 1, (sid, needle, hits)
        start = hits[0]
        stop = start if end is None else next(i for i in range(start, len(lines)) if end in lines[i])
        return {"source_id": sid, "derived_line_start": start + 1, "derived_line_end": stop + 1,
                "original_text": "\n".join(lines[start:stop+1])}

    date_re = re.compile(r"^([A-Z][a-z]+),?\s+(\d{1,2}),\s+(20\d{2}):")
    lines = text_by_id["S02"]
    catalog = []
    current = None
    for i, line in enumerate(lines):
        m = date_re.match(line)
        if m:
            if current is not None:
                current["derived_line_end"] = i
                catalog.append(current)
            d = datetime.strptime(" ".join(m.groups()), "%B %d %Y").date().isoformat()
            current = {"announcement_id": f"C{len(catalog)+1:03d}", "announcement_date": d,
                       "source_id": "S02", "derived_line_start": i+1, "original_lines": [line]}
        elif current is not None:
            if re.fullmatch(r"20\d{2}", line):
                current["derived_line_end"] = i
                catalog.append(current)
                current = None
            else:
                current["original_lines"].append(line)
    if current is not None:
        current["derived_line_end"] = len(lines)
        catalog.append(current)
    catalog = [c for c in catalog if "2010-01-01" <= c["announcement_date"] <= "2025-12-31"]
    for c in catalog:
        c["literal_CFTC_codes_detected"] = sorted(set(re.findall(r"\b[0-9]{3}[0-9A-Z+]{3}(?!\w)", "\n".join(c["original_lines"]))))
        c["interpretation"] = "raw_dated_announcement_not_automatic_clock_or_revision_mask"
    save(out / "announcement_catalog.json", {"schema": "stage408_official_dated_announcements_v1",
         "source": sources[1], "entries": catalog, "count": len(catalog),
         "scope": "All dated 2010-2025 entries observed on the current official long page; absence is not proof of no revision."})

    mapped = {"088691": "SHFE.AU", "084691": "SHFE.AG", "085692": "SHFE.CU", "026603": "DCE.M",
              "007601": "DCE.Y", "002602": "DCE.C", "033661": "CZCE.CF", "080732": "CZCE.SR"}
    ny = ZoneInfo("America/New_York")

    def exact(d, clock="15:30"):
        return datetime.fromisoformat(f"{d}T{clock}:00").replace(tzinfo=ny).isoformat()

    def midnight_after(d):
        return datetime.combine(datetime.fromisoformat(d).date()+timedelta(days=1), datetime.min.time(), ny).isoformat()

    events = []

    def event(eid, kind, known, evid, asof=None, scheduled=None, confirmed=None, planned=None,
              confirmed_at=None, note="", scope="all_COT", correction_scope=None):
        r = {"event_id": eid, "kind": kind, "position_asof": asof,
             "original_scheduled_release_date": scheduled, "scheduled_release_at": None,
             "planned_release_date": planned, "confirmed_release_date": confirmed,
             "confirmed_release_at": confirmed_at, "announcement_date": known,
             "release_status": "confirmed_exact_clock" if confirmed_at else "confirmed_date_only" if confirmed else "planned_not_confirmed" if planned else "unknown_or_nonpublication",
             "correctionKnownscope": correction_scope, "report_scope": scope,
             "research_available_at": confirmed_at,
             "research_available_status": "explicit_exact_release_clock" if confirmed_at else "unknown_exact_clock",
             "candidate_research_boundary_next_NY_midnight": midnight_after(confirmed) if confirmed and not confirmed_at else None,
             "candidate_boundary_is_assumption": bool(confirmed and not confirmed_at),
             "candidate_boundary_basis": "dated retrospective official publication confirmation; not archived first-seen proof" if confirmed and not confirmed_at else None,
             "downloaded_at_2026_UTC": [s["downloaded_at_2026_UTC"] for s in sources if s["source_id"] == evid[0]["source_id"]][0],
             "evidence": evid, "note": note}
        events.append(r)
        return r

    # These official forward-looking announcements deliberately do not receive actual release timestamps.
    event("shutdown2013_first_expected", "anticipated_shutdown_catchup", "2013-10-23",
          [evidence("S03", "The CFTC will begin issuing")], scheduled="2013-10-04", planned="2013-10-25",
          note="Anticipated first release and intended return by Nov8; position-asof not stated. No actual completion evidence in this bounded collection.")
    event("shutdown2013_nonpublication", "explicit_nonpublication_week", "2013-10-17",
          [evidence("S04", "Washington, DC – The U.S.")], note="Original notice says no COT/Cotton reports that week; do not correct or infer report-to-date association from the two literal scheduled dates.")
    event("shutdown2018_last_confirmed", "last_pre_shutdown_publication", "2019-01-29",
          [evidence("S05", "COT: The last COT report")], confirmed="2018-12-21",
          note="Last actual publication date is stated retrospectively; asof and precise clock unknown.")
    event("shutdown2019_first_expected", "expected_shutdown_catchup", "2019-01-29",
          [evidence("S05", "COT: The last COT report")], asof="2018-12-24", scheduled="2018-12-28", planned="2019-02-01",
          note="Monday asof explicit. Subsequent Tuesday/Friday catchup sequence is expected, not individually confirmed; end date unknown.")
    event("shutdown2018_nonpublication", "explicit_shutdown_nonpublication", "2018-12-22",
          [evidence("S02", "December 22, 2018:")], note="No specific first resumed release is confirmed by this announcement.")
    event("holiday2018_monday_positions", "explicit_Monday_asof_rule", "2018-12-21",
          [evidence("S02", "December 21, 2018:")], note="Two next releases use Monday data because Dec25/Jan1 are Tuesdays; original Friday plan is superseded by shutdown interruption.")
    event("holiday2018_mourning", "office_closure_only", "2018-12-04",
          [evidence("S02", "December 4, 2018:")], note="Closure Dec5 stated, next COT publication not stated; do not invent a release override.")

    ion = [("2023-02-24", "2023-02-03", "2023-01-31", "February 24, 2023:"),
           ("2023-03-03", "2023-02-10", "2023-02-07", "March 3, 2023:"),
           ("2023-03-08", "2023-02-17", "2023-02-14", "March 8, 2023:"),
           ("2023-03-10", "2023-02-24", "2023-02-21", "March 10, 2023:"),
           ("2023-03-14", "2023-03-03", None, "March 14, 2023:"),
           ("2023-03-16", "2023-03-10", None, "March 16, 2023:"),
           ("2023-03-21", "2023-03-17", None, "March 21, 2023:")]
    for confirmed, scheduled, asof, needle in ion:
        event("ION_"+confirmed, "today_issuing_confirmation", confirmed, [evidence("S02", needle)],
              asof=asof, scheduled=scheduled, confirmed=confirmed,
              note="Exact hour and original first-seen vintage unknown. Later three rows must align by original scheduled date to native annual asof; not asof+4-day inference.")
    event("ION2023_feb3_delayed", "explicit_delayed_release", "2023-02-02", [evidence("S02", "February 2, 2023:")], scheduled="2023-02-03")
    event("ION2023_earliest_resume_plan", "earliest_intended_resumption", "2023-02-16", [evidence("S09", "“CFTC staff intends")], planned="2023-02-24",
          note="As early as is a conditional plan, not actual publication proof.")
    event("ION2023_mar17_nonpublication", "explicit_nonpublication", "2023-03-17", [evidence("S02", "March 17, 2023:", "The CFTC intends")], scheduled="2023-03-17")

    event("holiday2020_monday_confirmed", "actual_holiday_exception", "2020-12-28", [evidence("S02", "December 28, 2020:")], asof="2020-12-21", confirmed="2020-12-28",
          note="Both Monday position and Monday publication are explicit; actual hour unknown.")
    event("holiday2021_juneteenth_plan", "planned_holiday_exception", "2021-06-17", [evidence("S02", "June 17, 2021:")], asof="2021-06-15", scheduled="2021-06-18", planned="2021-06-21")
    event("holiday2025_mourning_plan", "planned_holiday_exception", "2025-01-07", [evidence("S02", "January 07, 2025:")], planned="2025-01-13",
          note="As-of and original publication date not explicit. Do not infer from current2026holidaycalendar.")
    event("holiday2014_december_plan", "planned_holiday_exception", "2014-12-19", [evidence("S02", "December 19, 2014:")], planned="2014-12-30")
    r = event("premature2014_unchanged", "actual_premature_identical_release", "2014-07-07", [evidence("S02", "July 7, 2014:")], scheduled="2014-07-07", confirmed="2014-07-04", confirmed_at=exact("2014-07-04"),
          note="EDT explicitly stated. Early and scheduled data identical. Position-asof not stated; no hardcoded guessed Tuesday.")
    r["scheduled_release_at"] = exact("2014-07-07")
    event("premature2015_incomplete", "actual_incomplete_release", "2015-07-06", [evidence("S02", "July 6, 2015:")], confirmed="2015-07-03", scope="premature_incomplete_COT_not_complete_target_data",
          note="Actual publication only establishes an incomplete report, not usable complete PMPU. Complete release will occur July6 at15:30 is a plan.")["research_available_at"] = None
    event("complete2015_plan", "planned_complete_replacement", "2015-07-06", [evidence("S02", "July 6, 2015:")], planned="2015-07-06",
          note="Planned15:30; no retrospective confirmation of complete publication in this bounded source set.")

    def planned_table(sid, start, ending):
        ls = text_by_id[sid]
        a = next(i for i, line in enumerate(ls) if start in line)
        b = next(i for i in range(a+1, len(ls)) if ending in ls[i])
        # Adjacent HTML cells become '09/30/202510/03/202511/19/2025'.
        # Slashes and fixed width delimit dates; word boundaries would silently drop all such rows.
        tokens = re.findall(r"\d{2}/\d{2}/\d{4}", "\n".join(ls[a:b]))
        assert len(tokens) % 3 == 0
        return [[datetime.strptime(t, "%m/%d/%Y").date().isoformat() for t in tokens[i:i+3]] for i in range(0, len(tokens), 3)], a+1, b

    schedules = []
    for sid, announced, expected_count, version in [("S07", "2025-11-18", 17, "initial"), ("S06", "2025-12-09", 13, "revised")]:
        rows, first, last = planned_table(sid, "COT Report Date", "+First catch-up publication")
        assert len(rows) == expected_count
        for asof, scheduled, planned in rows:
            r = event(f"shutdown2025_{version}_{asof}", "intended_catchup_schedule", announced,
                  [{"source_id": sid, "derived_line_start": first, "derived_line_end": last,
                    "table_row_literal_ISO": [asof, scheduled, planned]}],
                  asof=asof, scheduled=scheduled, planned=planned,
                  note="All entries are intended, including rows earlier than announcement date. Calendar plan not actual release confirmation.")
            r["plan_version"] = version
            r["superseded_as_plan_by"] = "2025-12-09" if version == "initial" and asof <= "2025-12-23" else None
            schedules.append(r)

    corrections = []
    def correction(cid, asof, known, needle, codes, kind="postpublication_data_revision", published=None,
                   clock=None, target=True, note="", end=None):
        c = {"correction_id": cid, "position_asof": asof, "original_published_date": published,
             "correction_known_date": known, "correction_known_at": exact(known, clock) if clock else None,
             "correction_clock_precision": "exact_explicit_Eastern" if clock else "date_only",
             "kind": kind, "affected_CFTC_codes": codes,
             "mapped_target_codes": sorted(set(mapped).intersection(codes)) if codes is not None else sorted(mapped) if target else [],
             "correctionKnownscope": "all_COT_trader_classifications" if codes is None and target else "listed_markets_only",
             "target_disaggregated_FuturesOnly_implicated": target,
             "research_available_at": exact(known, clock) if clock else None,
             "candidate_research_boundary_next_NY_midnight": None if clock else midnight_after(known),
             "candidate_boundary_is_assumption": not bool(clock), "original_firstseen_vintage": "not_obtained",
             "notice_is_current_retrospective_official_page": True, "evidence": [evidence("S02", needle, end)], "note": note}
        corrections.append(c)
        return c
    correction("classification2012_all", "2012-11-27", "2012-12-05", "December 5, 2012:", None, clock="15:30",
               note="Late account-transfer classification stated Dec4. Current annual row cannot be asserted first available at ordinary first release.")
    correction("reporting2017_transfer", "2017-03-28", "2017-04-04", "April 4, 2017:",
        ["001602","001626","002602","005602","00639W","00639Y","020601","042601","043602","044601","045601","080732","098662","132741","13874+","13874A"], end="CME E-Mini S&P Stock Index")
    correction("reporting2019_march", "2019-03-26", "2019-04-03", "April 3, 2019:",
        ["001602","001612","002602","005602","007601","026603","043602","1170E1","054642","095741","13874A","209742","025608","06665G","075651","076651","084691","088691","033661","073732","080732","083731"],
        published="2019-03-29", end="ICUS Coffee C")
    correction("reporting2019_october", "2019-10-15", "2019-10-24", "October 24, 2019:",
        ["002602","005602","007601","026603","135731"], published="2019-10-18", end="ICUS Canola")
    correction("OI2011_corn_adjusted_at_release", "2011-10-11", "2011-10-14", "October 14, 2011:",
        ["054642","057642","002602"], kind="adjustment_at_publication_not_later_revision", published="2011-10-14",
        note="Denominator OI adjusted at original publication. Do not incorrectly quarantine as a later overwrite.")
    correction("Legacy2018_concentration_not_target", "2018-09-18", "2018-09-26", "September 26, 2018:", None,
        target=False, note="Sep25 explicitly states Disaggregated/TFF concentration accurate. Legacy correction is not a FuturesOnly PMPU mask.")
    correction("options2018_not_target", "2017-12-26", "2018-01-03", "January 3, 2018:", ["02365U"], target=False,
        note="Futures-and-options combined only; not target FuturesOnly.")
    correction("options2014_not_target", "2014-03-11", "2014-03-18", "March 18, 2014:", ["005602"], target=False,
        note="Additional option positions in combined reports only; not target FuturesOnly.")
    correction("options2010_corn_not_automatic_target", "2010-08-17", "2010-09-02", "September 2, 2010:", ["002602"], published="2010-08-20", target=False,
        note="Notice specifies additional options positions; do not automatically mask target FuturesOnly corn merely because the code matches.")
    correction("format2015_reportdate", "2015-06-16", "2015-06-22", "June 22, 2015:", None,
        kind="format_revision_planned_not_numeric_confirmation", target=False,
        note="Revised release planned June23. Formatting issue relevant to automated readers, not confirmed numerical category revision.")
    correction("metadata2022_copper_name", None, "2022-02-11", "February 11, 2022:", ["085692"], kind="names_only_codes_and_values_unaffected", target=False,
        end="192651CMXUS MIDWEST", note="085692 unchanged; COPPERGRADE#1 -> COPPER#1 is not a new contract.")

    # Mark out-of-scope records explicitly even when their CFTC code coincides with a target code.
    for c in corrections:
        if not c["target_disaggregated_FuturesOnly_implicated"]:
            c["matching_codes_but_scope_excludes_target"] = c["mapped_target_codes"]
            c["mapped_target_codes"] = []

    masks = [
      {"mask_id":"M2013_shutdown_clock_unknown", "basis":"original_scheduled_release_date", "start":"2013-10-04", "end_inclusive":"2013-11-08",
       "meaning":"candidate quarantine through expected resumption; expected endpoint is not confirmed actual resumption", "evidence_events":["shutdown2013_first_expected","shutdown2013_nonpublication"], "root_decision_required":True},
      {"mask_id":"M2018_19_backlog_actual_clock_gap", "basis":"position_asof", "start":"2018-12-24", "end_inclusive":"2019-03-25",
       "meaning":"candidate bounded evidence-gap quarantine until explicit Mar26 report later confirmed published Mar29; NOT claim backlog persisted until March", "actual_backlog_end":"unknown",
       "evidence_events":["shutdown2019_first_expected"], "confirmed_later_anchor_correction":"reporting2019_march", "root_decision_required":True},
      {"mask_id":"M2023_ION_override", "basis":"original_scheduled_release_date", "start":"2023-02-03", "end_inclusive":"2023-03-17",
       "meaning":"replace ordinary rule with seven confirmed issuing date rows; exact clock unknown, candidate next NY midnight separately exposed", "evidence_events":[r["event_id"] for r in events if r["kind"]=="today_issuing_confirmation"], "root_decision_required":True},
      {"mask_id":"M2025_intended_not_confirmed", "basis":"position_asof", "start":"2025-09-30", "end_inclusive":"2025-12-23",
       "exact_position_asofs":[r["position_asof"] for r in schedules if r["plan_version"]=="revised"],
       "meaning":"13 intended revised release dates may be adopted only as explicit retrospective planned-clock assumption, or masked; actual confirmed fields remain unknown", "root_decision_required":True},
      {"mask_id":"M2015_incomplete_alignment_unknown", "basis":"original_scheduled_release_date", "start":"2015-07-06", "end_inclusive":"2015-07-06",
       "meaning":"incomplete early Jul3 release cannot qualify complete current annual row; complete Jul6 is only planned", "position_asof":"unknown", "root_decision_required":True},
      {"mask_id":"M2011_MFGlobal_quality_caution", "basis":"position_asof", "start":"2011-11-08", "end_inclusive":"2011-11-08",
       "meaning":"general classification/transfer caution; named unavailable markets do not match eight codes, so no assertion PMPU mapped values were erroneous", "root_decision_required":True}
    ]
    for c in corrections:
        if c["target_disaggregated_FuturesOnly_implicated"] and c["kind"]=="postpublication_data_revision":
            masks.append({"mask_id":"M_"+c["correction_id"], "basis":"position_asof_and_CFTC_code", "start":c["position_asof"], "end_inclusive":c["position_asof"],
                          "target_codes":c["mapped_target_codes"], "meaning":"current annual snapshot potentially revised; use correction boundary assumption or mask this row, not all markets/weeks", "correction_id":c["correction_id"], "root_decision_required":True})

    panel = {"schema":"stage408_official_publication_exception_panel_v1", "created_at":now(),
        "domain":{"source_years":[2010,2025], "warmup_year":2010,"main_years":[2011,2025],"target_report":"Disaggregated Futures Only",
                  "mapped_codes":mapped,"mother_universe_products":98,"mother_universe_families":95,"unmapped_products":90,"mother_scope_narrowed":False},
        "source_clock_rule":{
          "timezone":"America/New_York", "ordinary_publication_weekday":"Friday", "ordinary_publication_time_local":"15:30:00", "usual_position_weekday":"Tuesday",
          "status":"retrospective_normal_week_rule_assumption_not_weekly_actual_confirmation",
          "source_evidence":[evidence("S01","The Commitments of Traders reports are released"), evidence("S08","The COT report is published more often"), evidence("S08","The COT report is released more quickly")],
          "current_2026_tentative_calendar_applies_to_2010_2025":False,
          "ordinary_holiday_release_calendar_2010_2025":"not_comprehensively_collected; do not silently infer from2026table or fixed4days",
          "retrospective_use_permitted_only_as_explicit_assumption":True,
          "strict_original_firstseen_vintage_obtained":False,
          "missing_firstseen_vintage_automatically_vetoes_all_retrospective_research":False,
          "annual_snapshot_download_is_historical_release_clock":False},
        "sources":sources,"publication_events":events,"publication_event_count":len(events),
        "catchup2025_plan_versions":{"initial_announcement_date":"2025-11-18","revised_announcement_date":"2025-12-09","initial_rows":17,"revised_rows":13,"latest13_are_actual_confirmations":False},
        "corrections_and_scope":corrections,"affected_ranges_and_candidate_masks":masks,
        "remaining_unknowns":["Per-week original firstseen vintages unavailable; current annual ZIPs can contain revisions.",
          "Absence of a notice, including2016noannouncements, does not establish no revisions.",
          "2013actual first resumption and final backlog completion unconfirmed;2019expectedcatchup dates unconfirmed.",
          "2025latest13row schedule is intended, not individually confirmed even for dates preceding Dec9.",
          "Ordinary2010-2025holiday calendars not exhaustively archived; only explicit observed exceptions normalized.",
          "2023lastthree issuing announcements give originalscheduleddate, not explicit positionasof; alignment belongs to root409.",
          "Date-only confirmations have no exact clock; nextNYmidnight is a disclosed research boundary assumption, not source fact."],
        "downstream_contract":{"root409_builds_weekly_projection_and_visible_event_counts":True,"source_floor_400_or_held35_computed_here":False,
          "independent_event_identity":"actual/assumed release availability group, not8markets or nativeasof count",
          "no_Y_fit_cash_or_alpha_qualification":True,"no_source_rule_changed_to_pass_floor":True},
        "scope_receipt":{"actual_GET":9,"raw_body_bytes":459252,"HTTP_statuses":[200]*9,"automatic_retry":0,"duplicate_URL_GET":0,"worker_concurrency":1,
          "yearindex_GET_or_ZIP_reads":0,"new_network_after_source_terminal":0,"fit":0,"cash":0,"SQL":0,"market_API":0},
        "http_receipt":bind(raw/"receipt.json"),"protocol407":bind(PROTOCOL),"tool":bind(Path(__file__)),"announcement_catalog":bind(out/"announcement_catalog.json")}
    save(out/"exceptions_panel.json", panel)
    fields = ["event_id","kind","position_asof","original_scheduled_release_date","scheduled_release_at","planned_release_date","confirmed_release_date","confirmed_release_at","announcement_date","release_status","research_available_at","research_available_status","candidate_research_boundary_next_NY_midnight","candidate_boundary_is_assumption","report_scope","plan_version","superseded_as_plan_by","downloaded_at_2026_UTC","note"]
    with (out/"publication_events.csv").open("w",newline="") as f:
        writer=csv.DictWriter(f, fieldnames=fields,extrasaction="ignore")
        writer.writeheader();writer.writerows(events)
    save(out/"affected_ranges.json", masks)
    save(out/"corrections_scope.json", corrections)
    summary = {"status":"bounded_official_clock_sources_complete_with_explicit_unknowns", "completed_at":now(),
               "actual_GET":9,"raw_body_bytes":459252,"all_HTTP200":True,"no_retry_or_duplicate_URL":True,
               "dated_2010_2025_announcements":len(catalog),"publication_events":len(events),
               "confirmed_ION_issuing_dates":len(ion),"2025_revised_intended_rows":13,
               "2025_revised_confirmed_rows":0,"normalized_correction_scope_records":len(corrections),
               "financial_or_alpha_qualification":False,"retrospective_research_not_globally_vetoed":True,
               "output_files":[bind(out/n) for n in ["announcement_catalog.json","exceptions_panel.json","publication_events.csv","affected_ranges.json","corrections_scope.json"]],
               "local_compile_reads_only_saved_HTML_derived_text_and407_protocol":True,"new_network_during_compile":0}
    save(out/"source_panel_receipt.json", summary)
    print(json.dumps({"receipt":bind(out/"source_panel_receipt.json"),"status":summary["status"],"ION_confirmed":len(ion),"2025planned":13,"GET":9,"bytes":459252}))


if __name__ == "__main__": main()
