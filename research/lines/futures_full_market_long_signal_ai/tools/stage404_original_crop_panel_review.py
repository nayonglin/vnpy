"""One independent source/table/event review. No author parser is imported."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, localcontext
import hashlib
import html
import io
import json
from pathlib import Path
import re
import time as timing
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

LINE = Path(__file__).resolve().parents[1]
ROOT = LINE / "outputs/stage404_original_crop_panel_review"
SOURCE = LINE / "outputs/stage401_original_crop_archive/actual_run1"
PROTOCOL = LINE / "outputs/stage403_weather_panel_root_protocol/protocol.json"
STATES = ("Arkansas", "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana", "Michigan", "Minnesota",
          "Mississippi", "Missouri", "Nebraska", "North Carolina", "North Dakota", "Ohio", "South Dakota", "Tennessee", "Wisconsin")
ALL_STATES = set(("Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|Florida|Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|Mississippi|Missouri|Montana|Nebraska|Nevada|New Hampshire|New Jersey|New Mexico|New York|North Carolina|North Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|Rhode Island|South Carolina|South Dakota|Tennessee|Texas|Utah|Vermont|Virginia|Washington|West Virginia|Wisconsin|Wyoming|United States").split("|"))
PHASES = {"pods": ("Soybeans Setting Pods - Selected States", "soybeans_setting_pods"),
          "leaves": ("Soybeans Dropping Leaves - Selected States", "soybeans_dropping_leaves")}
NY, UTC = ZoneInfo("America/New_York"), timezone.utc


class Files:
    def __init__(self): self.data = {}
    def read(self, path):
        key = str(Path(path).resolve())
        if key not in self.data: self.data[key] = Path(key).read_bytes()
        return self.data[key]
    def bind(self, path):
        body = self.read(path)
        return {"path": str(Path(path).resolve()), "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
    def check(self, binding): assert self.bind(binding["path"]) == binding, binding["path"]
    def load(self, path): return json.loads(self.read(path))


def now(): return datetime.now(UTC).isoformat()


def usable(label):
    day = date.fromisoformat(label) + timedelta(days=1)
    return datetime.combine(day, time(), NY).astimezone(UTC)


def token_value(token, dash_zero):
    if token == "-": return Decimal(0) if dash_zero else None
    if not re.fullmatch(r"\d[\d,]*(?:\.\d+)?", token): return None
    return Decimal(token.replace(",", ""))


def row_values(lines, begin, columns, dash_zero):
    result = {}
    for index in range(begin, min(len(lines), begin+125)):
        if ":" not in lines[index]: continue
        label, values = lines[index].split(":", 1)
        label = re.sub(r"\s+\d+/$", "", label.rstrip(". ")).strip()
        # Deliberately do not require dot leaders: full-width state names have no dots.
        if label not in ALL_STATES and not re.fullmatch(r"\d+ States", label): continue
        cells = values.split()
        assert len(cells) == columns, (label, lines[index])
        assert label not in result
        result[label] = {"tokens": cells, "line": index+1, "raw": lines[index],
                         "values": [token_value(x, dash_zero) for x in cells]}
        if label == "United States" or re.fullmatch(r"\d+ States", label): break
    return result


def independent_tables(raw, publication, release):
    try: text = raw.decode("utf-8-sig")
    except UnicodeDecodeError: text = raw.decode("cp1252", errors="surrogateescape")
    lines = text.splitlines()
    dash = bool(re.search(r"(?im)^\s*-\s+Represents zero\.\s*$", text))
    if publication == "crop-progress":
        match = re.search(r"\bReleased\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})", " ".join(lines[:60]))
        if match:
            assert datetime.strptime(match.group(1), "%B %d, %Y").date().isoformat() == release
        else:
            # One archived original is a genuine delay notice, not a crop-data report.
            issued = re.search(r"\bIssued\s+([A-Za-z.]+\s+\d{1,2},\s+\d{4})", " ".join(lines[:30]))
            assert issued and "Crop Progress Report Delayed" in text
            stamp = issued.group(1).replace("Sept.", "September")
            assert datetime.strptime(stamp, "%B %d, %Y").date().isoformat() == release
        tables = {}
        for phase, (title, _) in PHASES.items():
            hits = [i for i, s in enumerate(lines) if " ".join(s.split()).casefold() == title.casefold()]
            if not hits:
                tables[phase] = {"present": False, "rows": {}, "reference_date": None}
                continue
            assert len(hits) == 1
            start = hits[0]
            schema = []
            for i in range(start+1, start+15):
                a, b = lines[i].split(":"), lines[i+1].split(":")
                if len(a) == len(b) == 5 and a[0].strip() == "State" and b[3].strip() == release[:4]:
                    day = datetime.strptime(a[3].strip()+" "+b[3].strip(), "%B %d, %Y").date()
                    assert day.weekday() == 6 and day <= date.fromisoformat(release)
                    schema.append((i, day))
            assert len(schema) == 1
            i, ref = schema[0]
            rows = row_values(lines, i+2, 4, dash)
            assert rows and re.fullmatch(r"\d+ States", list(rows)[-1])
            tables[phase] = {"present": True, "reference_date": ref.isoformat(), "rows": rows}
        return tables
    hits = [i for i, s in enumerate(lines) if s.startswith("Soybeans for Beans Area Planted and Harvested, Yield, and Production")
            and any("Yield per acre" in h and "Production" in h for h in lines[i:i+14])]
    if not hits: return {"annual": {"present": False, "rows": {}, "year": None}}
    assert len(hits) == 1
    start = hits[0]
    header = next(i for i in range(start, start+14) if "Yield per acre" in lines[i] and "Production" in lines[i])
    yl = next(i for i in range(header+1, header+7) if len(re.findall(r"\b20\d{2}\b", lines[i])) == 6)
    years = [int(y) for y in re.findall(r"\b20\d{2}\b", lines[yl])]
    assert years[:3] == years[3:] and int(release[:4])-1 in years[3:]
    assert "1,000 bushels" in " ".join(lines[yl+1:yl+5])
    column = 3 + years[3:].index(int(release[:4])-1)
    rows = row_values(lines, yl+2, 6, dash)
    assert list(rows)[-1] == "United States"
    return {"annual": {"present": True, "rows": rows, "year": int(release[:4])-1, "column": column}}


def reused391_tables(f, publication):
    # Reuse the accepted derived evidence; do not parse the two old original reports again.
    p = LINE / "outputs/stage391_original_soy_exposure_sample/actual_run1/exposure_rows.json"
    old = f.load(p)
    if publication != "crop-progress":
        rows = {state: {"tokens": r["original_all_six_tokens"], "line": r["line_number"], "raw": r["raw_line"],
                        "values": [token_value(x, False) for x in r["original_all_six_tokens"]]}
                for state, r in old["all_annual_states_and_us"].items()}
        return {"annual": {"present": True, "rows": rows, "year": 2019, "column": 5}}
    result = {}
    for phase in PHASES:
        rows = {}
        for state in old["rows"]:
            r = state[phase+"_raw"]
            rows[state["state"]] = {"tokens": r["original_all_four_tokens"], "line": r["line_number"], "raw": r["raw_line"],
                                     "values": [token_value(x, True) for x in r["original_all_four_tokens"]]}
        result[phase] = {"present": True, "reference_date": "2020-08-30", "rows": rows}
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--panel-dir", required=True)
    args = parser.parse_args()
    output = ROOT / "actual_review_receipt.json"
    if output.exists(): raise RuntimeError("Single source/event review already completed")
    started, tick, f = now(), timing.monotonic(), Files()
    protocol = f.load(PROTOCOL)
    harvest = f.load(SOURCE / "harvest_manifest.json")
    inventory = f.load(SOURCE / "reports_index.json")
    parsed = f.load(SOURCE / "parsed_original_tables.json")
    assert harvest["status"] == "bounded_harvest_complete_with_explicit_unknowns"
    requests = harvest["all_request_records"]
    assert len(requests) == harvest["GET_total"] == len({r["url"] for r in requests}) == 391
    assert sum(r["body"]["bytes"] for r in requests) == harvest["source_body_bytes"] == 26306297
    assert Counter(r["role"] for r in requests) == {"locator": 74, "txt": 317}
    for r in requests:
        assert r["status"] == 200 and r["retry"] == r["redirect"] == 0
        assert urlsplit(r["url"]).hostname == "esmis.nal.usda.gov"
        f.check(r["body"])
    by_url = {r["source"]["url"]: r for r in parsed["reports"]}
    assert len(inventory["reports"]) == len(parsed["reports"]) == 319
    originals, omissions, numeric_cells, parsed_new, reused = [], [], 0, 0, 0
    accepted_old_shas = {"232aadcb45eafd4638d1b87977065cf0d99aa9352c775f1d810213018328319b",
                         "d62776648672a0da1656b4bcc67419745be826809ad964fc5ef5fd1eb3c81918"}
    for record in inventory["reports"]:
        assert len(record["original_sources"]) == 1
        original = record["original_sources"][0]
        assert original["ok"]
        if original.get("mode") == "reused_exact391_original_no_GET":
            assert original["body"]["sha256"] in accepted_old_shas
        else:
            assert original["status"] == 200
        f.check(original["body"])
        locator = html.unescape(f.read(record["locator_body"]["path"]).decode("utf-8"))
        assert (original["url"] in locator or urlsplit(original["url"]).path in locator)
        assert any(urlsplit(x).path in locator for x in record["release_pages"])
        pub, label, sha = record["publication"], record["release_date"], original["body"]["sha256"]
        authored = by_url[original["url"]]
        assert authored["raw"]["sha256"] == sha and authored["source"]["release_date"] == label
        if sha in accepted_old_shas:
            tables = reused391_tables(f, pub); reused += 1
        else:
            tables = independent_tables(f.read(original["body"]["path"]), pub, label); parsed_new += 1
        for phase, table in tables.items():
            key = "soybeans_production" if phase == "annual" else PHASES[phase][1]
            actual = authored["tables"][key]
            assert actual["present"] == table["present"], (pub, label, phase, "false table absence")
            if not table["present"]: continue
            assert actual["status"] == "parsed_original_schema", (pub, label, phase, "false unknown schema")
            column = table["column"] if phase == "annual" else 2
            actual_rows = {r["state"]: r for r in actual["rows"]}
            for state, row in table["rows"].items():
                if re.fullmatch(r"\d+ States", state) and state not in actual_rows: continue
                if state not in actual_rows:
                    omissions.append({"publication": pub, "release_date": label, "state": state, "line": row["line"],
                                      "raw": row["raw"], "value": str(row["values"][column]), "affects_fixed18": state in STATES})
                    continue
                a = actual_rows[state]
                expected = row["values"][column]
                assert (Decimal(str(a["value"])) if a["value"] is not None else None) == expected, (pub,label,state)
                assert a["raw_line"] == row["raw"] and a["line_number"] == row["line"]
                numeric_cells += 1
        canonical = {"publication": pub, "release": label, "usable": usable(label), "body": original["body"], "tables": tables}
        key = f"{pub}:{label}:"+sha
        canonical["id"] = hashlib.sha256(key.encode()).hexdigest()
        originals.append(canonical)
    assert parsed_new == 317 and reused == 2
    assert {(r["release_date"],r["state"]) for r in omissions} == {
        ("2017-01-12","North Carolina"),("2017-01-12","South Carolina"),
        ("2018-01-12","North Carolina"),("2018-01-12","South Carolina"),
        ("2019-02-08","North Carolina"),("2019-02-08","South Carolina")}
    panel = Path(args.panel_dir).resolve()
    manifest = f.load(panel / "event_table_manifest.json")
    for b in manifest["outputs"]: f.check(b)
    assert manifest["frozen403_protocol"] == f.bind(PROTOCOL)
    events = f.load(panel / "all_candidate_events.json")["events"]
    summary = f.load(panel / "qualification_summary.json")
    adapter = f.load(panel / "local_observed_row_adapter.json")
    assert adapter["original401_sources_or_manifest_changed"] is False
    assert adapter["scientific_thresholds_state_domain_dates_or_selection_changed"] is False
    assert len(adapter["applied"]) == 4
    for entry in adapter["applied"]:
        raw = next(x for x in originals if x["publication"] != "crop-progress" and x["release"] == entry["release_date"])
        row = raw["tables"]["annual"]["rows"][entry["row"]["state"]]
        assert entry["original_body_SHA256"] == raw["body"]["sha256"] and entry["record_id"] == raw["id"]
        assert entry["row"]["raw_line"] == row["raw"] and entry["row"]["line_number"] == row["line"]
        assert entry["row"]["tokens"] == row["tokens"] and entry["row"]["value"] == row["values"][5]
        assert entry["row"]["production_year"] == int(entry["release_date"][:4])-1 and entry["row"]["unit"] == "1000 bushels"
    f.check(adapter["first_original_result_manifest"]); f.check(adapter["first_original_result_summary"])
    independent = []
    max_error, inherited_total = Decimal(0), 0
    with localcontext() as ctx:
        ctx.prec = 60
        for year in protocol["event_population"]["years"]:
            new_day = date(year,7,1)
            new_day += timedelta(days=(-new_day.weekday())%7)
            while new_day <= date(year,10,31):
                new = datetime.combine(new_day,time(),UTC)
                clock = new+timedelta(hours=37)
                available = [r for r in originals if r["publication"] == "crop-progress" and r["release"][:4] == str(year) and r["usable"] <= clock]
                latest = max(available,key=lambda r:r["release"]) if available else None
                annual = [r for r in originals if r["publication"] != "crop-progress" and r["release"][:4] == str(year) and r["usable"] <= clock and r["tables"]["annual"]["present"]]
                chosen = min(annual,key=lambda r:r["release"]) if annual else None
                assert chosen is not None and latest is not None
                at = chosen["tables"]["annual"];col = at["column"];us = at["rows"]["United States"]["values"][col]
                assert at["year"] == year-1 and us > 0
                gsum, qsum, unknown, inherited = Decimal(0), Decimal(0), [], 0
                states = {}
                for state in STATES:
                    q = at["rows"][state]["values"][col]
                    phase_values = {}
                    phase_sources = {}
                    for phase in PHASES:
                        table = latest["tables"][phase]
                        source = latest
                        val = table["rows"].get(state,{}).get("values",[None]*4)[2] if table["present"] else None
                        status = "current_original" if table["present"] and val is not None else None
                        if not table["present"]:
                            explicit = [(r, r["tables"][phase]["rows"].get(state,{}).get("values",[None]*4)[2])
                                        for r in available if r["release"] < latest["release"] and r["tables"][phase]["present"]]
                            explicit = [(r,v) for r,v in explicit if v is not None]
                            previous = max(explicit,key=lambda x:x[0]["release"]) if explicit else None
                            if previous and previous[1] == 100:
                                source,val = previous;status = "inherited_explicit100_completion";inherited += 1
                        phase_values[phase] = val
                        phase_sources[phase] = (source,status)
                    p,l = phase_values["pods"],phase_values["leaves"]
                    g = (p-l)/100 if p is not None and l is not None and p >= l else None
                    if q is None or (q > 0 and g is None):unknown.append(state)
                    w = q/us if q is not None else None
                    wg = w*g if w is not None and g is not None else Decimal(0) if w == 0 else None
                    if wg is not None:gsum += wg
                    if q is not None:qsum += q
                    states[state] = {"q":q,"w":w,"g":g,"wg":wg,"p":p,"l":l,"phase_sources":phase_sources}
                independent.append({"new":new,"A":clock,"year":year,"report":latest,"annual":chosen,"US":us,
                                    "qualified":not unknown,"unknown":unknown,"inherited":inherited,"gsum":gsum,"qsum":qsum,"states":states})
                new_day += timedelta(days=7)
        assert len(independent) == len(events) == 141
        selected = []
        for i,(truth,e) in enumerate(zip(independent,events)):
            assert e["new_init_UTC"] == truth["new"].isoformat() and e["A_UTC"] == truth["A"].isoformat()
            assert e["old_init_UTC"] == (truth["new"]-timedelta(days=1)).isoformat()
            assert e["V_start_UTC"] == (truth["new"]+timedelta(hours=48)).isoformat() and e["V_end_UTC"] == (truth["new"]+timedelta(hours=216)).isoformat()
            assert e["progress_release_date"] == truth["report"]["release"] and e["progress_record_id"] == truth["report"]["id"]
            assert e["annual_release_date"] == truth["annual"]["release"] and e["annual_record_id"] == truth["annual"]["id"]
            assert e["US_Q_prior_cropyear_1000bushels"] == truth["US"]
            assert e["source_qualified"] == truth["qualified"] and e["unknown_positive_production_states"] == truth["unknown"]
            assert e["inherited_completion_cells"] == truth["inherited"]
            inherited_total += truth["inherited"]
            for actual,state in zip(e["states"],STATES):
                t = truth["states"][state];assert actual["state"] == state
                for key, expected in [("Q_prior_cropyear_1000bushels",t["q"]),("w",t["w"]),("pods_pct",t["p"]),("leaves_pct",t["l"]),("g",t["g"]),("weighted_g",t["wg"])]:
                    a = Decimal(str(actual[key])) if actual[key] is not None else None
                    if a is None or expected is None:assert a == expected,(i,state,key,a,expected)
                    else:
                        error = abs(a-expected);max_error = max(max_error,error);assert error < Decimal('1e-35')
                for phase in PHASES:
                    source,status = t["phase_sources"][phase]
                    if status:
                        assert actual[phase+"_source_status"] == status
                        evidence = actual[phase+"_evidence"]
                        assert evidence["record"]["record_id"] == source["id"] and Decimal(evidence["value"]) == t["p" if phase == "pods" else "l"]
                        assert source["usable"] <= truth["A"]
            expected_weighted = truth["gsum"] if truth["qualified"] else None
            actual_weighted = Decimal(e["weighted_g_sum"]) if e["weighted_g_sum"] is not None else None
            if expected_weighted is None:assert actual_weighted is None
            else:assert abs(actual_weighted-expected_weighted) < Decimal('1e-35')
        counts = {}
        for year in protocol["event_population"]["years"]:
            qualified = [i for i,t in enumerate(independent) if t["year"] == year and t["qualified"]]
            first8 = qualified[:8];selected += [events[i]["event_id"] for i in first8]
            counts[str(year)] = {"all_candidates":sum(t["year"] == year for t in independent),"all_source_qualified":len(qualified),"selected":len(first8)}
            for i,t in enumerate(independent):
                if t["year"] == year:assert events[i]["selected_first8"] == (i in first8)
            sy = summary["year_counts"][str(year)]
            assert sy["all_candidates"] == counts[str(year)]["all_candidates"] and sy["all_source_qualified"] == len(qualified) and sy["selected_first8_source_qualified"] == len(first8)
            assert sy["selected_event_ids"] == [events[i]["event_id"] for i in first8]
        assert f.load(panel/"selected_event_ids.json")["events"] == selected
        for filename, expected_ids in [("all_candidate_events.csv",[e["event_id"] for e in events]),
                                       ("selected_events.csv",selected),
                                       ("unknown_events.csv",[e["event_id"] for e in events if not e["source_qualified"]])]:
            rows = list(csv.DictReader(io.StringIO(f.read(panel/filename).decode())))
            assert [r["event_id"] for r in rows] == expected_ids
        train = sum(counts[str(y)]["selected"] for y in range(2018,2023));held = sum(counts[str(y)]["selected"] for y in range(2023,2026))
        assert summary["train_selected_events"] == train and summary["held_selected_events"] == held
        assert train < 30 and held < 15 and summary["source_count_gate_passed"] is False and manifest["source_gate_passed"] is False
        report_reuse = Counter(e["progress_record_id"] for e in events if e["selected_first8"])
        assert len(report_reuse) == summary["distinct_selected_release_reports"] == 13
        assert dict(report_reuse) == summary["selected_original_report_reuse_counts"]
    result = {"schema":"stage404_independent_original_crop_panel_review_v1","status":"passed_corrected_source_NO_GO_confirmed",
              "started_at":started,"ended_at":now(),"elapsed_seconds":timing.monotonic()-tick,"tool":f.bind(__file__),
              "source401_manifest":f.bind(SOURCE/"harvest_manifest.json"),"panel402_manifest":f.bind(panel/"event_table_manifest.json"),"protocol403":f.bind(PROTOCOL),
              "source_reports":319,"new_raw_reports_independently_parsed":parsed_new,"old391_derived_only_reused":reused,
              "new_source_numeric_cells_checked":numeric_cells,"original_projection_omissions":omissions,
              "reviewer_initial_metadata_failures":{"count":3,"reasons":["accepted391 reuse record intentionally has no new HTTP status; first review incorrectly required one after five annual reports", "2018-09-10 is a genuine ASB delay notice with an Issued label, not a Released crop report; second review required the wrong header before full completion", "the same no-dot projection omission also occurs in unused2017 annual; initial expectation of four instead of six omitted rows stopped after a completed source pass but before event review"],"source_or_author_changed":False,"prior_new_report_parse_counts":[5,68,317]},
              "fixed18_NC_recovered_correctly":True,"outside_domain_SC_projection_limitation_retained":True,
              "source_requests":391,"source_body_bytes":26306297,"source_network_retry":0,
              "candidate_events_checked":141,"state_event_rows_checked":141*18,"year_counts":counts,
              "train":train,"held":held,"source_floor_passed":False,"completion100_cells_checked":inherited_total,
              "max_Decimal_absolute_error":str(max_error),"latest_report_ids_and_visibility_verified":True,
              "first8_selection_verified":True,"failed_report_fallback_in_code":False,
              "distinct_selected_release_reports":13,"selected_release_report_reuse":dict(report_reuse),
              "P0_remaining":0,"P1_remaining":0,"P2_remaining":0,
              "reviewer_network":0,"reviewer_SQL":0,"reviewer_fit":0,"reviewer_cash":0,"new_weather":0,
              "old390_GRIB_decodes":0,"old391_original_report_parses":0,"alpha_qualified":False,"whole_goal":False,
              "limitations":["Original401 no-dot omissions in2017/2018/2019 preserved;2018/19 NC needed by the fixed event domain corrected in402;2017 annual and SC do not enter current events.",
                             "Following-midnight NY is a disclosed historical availability assumption, not first-seen proof.",
                             "2025October has no native archive option; no unseen report was fabricated. Source NO-GO is not a weather-alpha rejection.",
                             "Source floors are feasibility gates, not statistical power or independent trading observations."]}
    ROOT.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
    print(json.dumps({"status":result["status"],"receipt":Files().bind(output),"year_counts":counts,"train":train,"held":held,"source_cells":numeric_cells,"elapsed_seconds":result["elapsed_seconds"]}))


if __name__ == "__main__": main()
