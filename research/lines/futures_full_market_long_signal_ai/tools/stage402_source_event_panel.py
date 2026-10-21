"""Build one frozen source-only weekly event panel from terminal Stage401 data."""
from __future__ import annotations

import collections
import copy
import csv
import argparse
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, localcontext
import hashlib
import json
import re
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "outputs/stage401_original_crop_archive/actual_run1"
BASE = ROOT / "outputs/stage402_source_event_panel"
OUT = BASE / "actual_run1"
PROTOCOL = ROOT / "outputs/stage403_weather_panel_root_protocol/protocol.json"
PROTOCOL_SHA = "a82d624d870e4e6f748644b6e61e6818d020f61255a3f0de7b14538a785a8f60"
STATES = ("Arkansas", "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana", "Michigan", "Minnesota",
          "Mississippi", "Missouri", "Nebraska", "North Carolina", "North Dakota", "Ohio", "South Dakota", "Tennessee", "Wisconsin")
PHASES = {"pods": "soybeans_setting_pods", "leaves": "soybeans_dropping_leaves"}
NY = ZoneInfo("America/New_York")
UTC = timezone.utc


def bind(path):
    path = Path(path)
    data = path.read_bytes()
    return {"path": str(path.resolve()), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+"\n")


def available(label):
    return datetime.combine(date.fromisoformat(label)+timedelta(days=1), time(0), NY).astimezone(UTC)


def number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
    except Exception:
        return None
    return result if result.is_finite() else None


def reference(record):
    if record is None:
        return None
    result = {key: record[key] for key in ("record_id", "publication", "release_date", "usable_at_UTC", "source_status", "body_bindings", "source_urls")}
    if record.get("local402_observed_row_adapter"):
        result["local402_observed_row_adapter"] = record["local402_observed_row_adapter"]
    return result


def adapt_observed_nc_rows(records):
    """Only four exact already-observed no-dot rows; never edit401 artifacts.

    NorthCarolina affects the unchanged18state domain. SouthCarolina is only
    the source-projection addendum explicitly authorized in the same pass.
    """
    evidence_paths = [BASE/"observed_no_dot_NC_original_evidence.json", BASE/"observed_no_dot_SC_original_addendum.json"]
    entries = [{**row, "evidence_binding": bind(path)} for path in evidence_paths for row in json.loads(path.read_text())["rows"]]
    expected = {("2018-01-12", "North Carolina"): (2017, 67600, "755aa0520291efec0bf8eebe8100391852ed305ff94e75694bd46819589213e3"),
                ("2019-02-08", "North Carolina"): (2018, 53380, "1ed719be80f2712dc990b15ceca7de26b3eb8d1a2b3389415b208b1f0b4914e1"),
                ("2018-01-12", "South Carolina"): (2017, 14820, "755aa0520291efec0bf8eebe8100391852ed305ff94e75694bd46819589213e3"),
                ("2019-02-08", "South Carolina"): (2018, 11063, "1ed719be80f2712dc990b15ceca7de26b3eb8d1a2b3389415b208b1f0b4914e1")}
    applied = []
    for entry in entries:
        label = entry["release_date"]
        raw = entry["original_row"]
        left, right = raw["raw_line"].split(":", 1)
        state = left.strip()
        if (label, state) not in expected:
            raise ValueError("Row adapter cannot extend to unobserved dates")
        year, value, sha = expected[(label, state)]
        matches = [x for x in records if x["publication"] == "crop-production-annual-summary" and x["release_date"] == label]
        if len(matches) != 1:
            raise ValueError("Observed annual report identity not unique")
        record = matches[0]
        if not record["report"] or [x["sha256"] for x in record["body_bindings"]] != [sha]:
            raise ValueError("Observed original annual SHA changed")
        local = copy.deepcopy(record["report"])
        table = local["tables"]["soybeans_production"]
        if (table["production_year"] != year or table["production_column_zero_based"] != 5
                or table["unit"] != "1000 bushels" or any(x["state"] == state for x in table["rows"])):
            raise ValueError("Observed mechanical missing-row condition changed")
        if raw not in table["raw_table_lines"]:
            raise ValueError("Exact original row evidence differs from retained401 table")
        tokens = right.split()
        if len(tokens) != 6 or not all(re.fullmatch(r"\d[\d,]*(?:\.\d+)?", x) for x in tokens):
            raise ValueError("Original six-token production schema differs")
        if int(tokens[5].replace(",", "")) != value:
            raise ValueError("Observed original production value differs")
        row = {"state": state, **raw, "tokens": tokens, "value": value, "token": tokens[5],
               "status": "reported_number_via402_observed_no_dot_state_row_adapter",
               "production_column_zero_based": 5, "production_year": year, "unit": "1000 bushels",
               "adapter_origin": "402local copied report only; original401 parsed rows/manifest untouched"}
        table["rows"].append(row)
        table["rows"].sort(key=lambda x: x["line_number"])
        record["report"] = local
        record.setdefault("local402_observed_row_adapter", []).append({"source_evidence_binding": entry["evidence_binding"], "row": row})
        applied.append({"release_date": label, "record_id": record["record_id"], "original_body_SHA256": sha, "row": row})
    if len(applied) != 4 or {(x["release_date"], x["row"]["state"]) for x in applied} != set(expected):
        raise ValueError("Only the four already-observed rows may be adapted")
    return {"schema": "stage402_one_local_observed_row_adapter_v1", "applied": applied,
            "first_original_result_manifest": bind(BASE/"actual_run1/event_table_manifest.json"),
            "first_original_result_summary": bind(BASE/"actual_run1/qualification_summary.json"),
            "original401_sources_or_manifest_changed": False,
            "scientific_thresholds_state_domain_dates_or_selection_changed": False}


def source_records(inventory, parsed):
    by_url = collections.defaultdict(list)
    for report in parsed["reports"]:
        source = report.get("source")
        url = source.get("url") if isinstance(source, dict) else source
        if url:
            by_url[url].append(report)
    grouped = collections.defaultdict(list)
    for row in inventory["reports"]:
        grouped[(row["publication"], row["release_date"])].append(row)
    records = []
    checked = {}
    for (publication, label), rows in sorted(grouped.items()):
        bodies, urls, tables = {}, set(), []
        errors = []
        originals = {x["url"]: x for row in rows for x in row.get("original_sources", [])}
        if not originals:
            errors.append("no_original_TXT_in_inventory")
        for url, original in sorted(originals.items()):
            urls.add(url)
            if not original.get("ok") or not original.get("body"):
                errors.append("original_TXT_unreceived:"+url)
                continue
            binding = original["body"]
            if binding["path"] not in checked:
                checked[binding["path"]] = bind(binding["path"])
            if checked[binding["path"]] != binding:
                raise ValueError("Stage401 original body changed")
            bodies[binding["sha256"]] = binding
            candidates = [x for x in by_url.get(url, []) if x.get("raw", {}).get("sha256") == binding["sha256"]]
            if len(candidates) != 1:
                errors.append("one_original_parser_result_not_confirmed:"+url)
                continue
            parsed_report = candidates[0]
            if parsed_report.get("release", {}).get("body_metadata_date_match") is False:
                errors.append("body_release_label_conflict:"+url)
            tables.append(parsed_report)
        if len(bodies) != 1:
            errors.append("original_release_body_count_not_one")
        if tables and len({x.get("raw", {}).get("sha256") for x in tables}) != 1:
            errors.append("ambiguous_distinct_original_bodies_same_release")
        report = tables[0] if tables and not errors else None
        key = f"{publication}:{label}:"+",".join(sorted(bodies))
        records.append({"record_id": hashlib.sha256(key.encode()).hexdigest(), "publication": publication,
                        "release_date": label, "usable_at_UTC": available(label).isoformat(),
                        "source_status": "one_original_received_and_parsed" if report else "unknown_original",
                        "source_errors": errors, "body_bindings": list(bodies.values()), "source_urls": sorted(urls),
                        "report": report, "locator_bindings": [row["locator_body"] for row in rows]})
    return records


def cell(record, phase, state):
    """Original current-week cell only; this does not carry observations forward."""
    if not record or not record["report"]:
        return None, "unknown_original", None
    table = record["report"]["tables"].get(PHASES[phase], {})
    if table.get("present") is False and table.get("status") == "missing_table":
        return None, "missing_table", None
    if table.get("status") != "parsed_original_schema":
        return None, "unknown_table_schema", None
    rows = [x for x in table.get("rows", []) if x.get("state") == state]
    if len(rows) != 1:
        return None, "missing_or_duplicate_state", None
    row = rows[0]
    val = number(row.get("value"))
    evidence = {"record": reference(record), "phase": phase, "state": state,
                "reference_week_end": table.get("current_reference_date"),
                "current_column_zero_based": table.get("current_column_zero_based"),
                "value": str(val) if val is not None else None,
                "token": row.get("token"), "token_status": row.get("status"),
                "line_number": row.get("line_number"), "raw_line": row.get("raw_line"),
                "raw_current_row_tokens": row.get("tokens")}
    if row.get("token") == "-" and (row.get("status") != "explicit_reported_zero" or not record["report"].get("explicit_dash_zero_footnotes")):
        return None, "dash_meaning_unknown", evidence
    if val is None or val < 0 or val > 100:
        return None, "unknown_or_out_of_range_current_cell", evidence
    return val, "current_original", evidence


def resolve_phase(record, phase, state, year, history):
    val, status, evidence = cell(record, phase, state)
    if status != "missing_table":
        return val, status, evidence
    # Completion inheritance is the sole exception: last explicit original
    # value must be100. Later explicit<100 retracts an older completion claim.
    previous = []
    for earlier in history:
        if earlier["release_date"][:4] != str(year) or earlier["release_date"] >= record["release_date"]:
            continue
        old, old_status, old_evidence = cell(earlier, phase, state)
        if old_status == "current_original":
            previous.append((earlier["release_date"], old, old_evidence))
    if not previous:
        return None, "missing_table_no_earlier_explicit_completion100", None
    _, last, last_evidence = max(previous, key=lambda x: x[0])
    if last == 100:
        last_evidence = {**last_evidence, "inherited_into_missing_table_of_record_id": record["record_id"],
                         "inheritance_rule": "earlier_same_cropyear_state_phase_explicit100_completion_only"}
        return last, "inherited_explicit100_completion", last_evidence
    status = "missing_table_completion100_retracted_by_later_explicit_value" if any(x[1] == 100 for x in previous) else "missing_table_no_earlier_explicit_completion100"
    return None, status, last_evidence


def annual_exposure(year, clock, annual):
    original = [x for x in annual if int(x["release_date"][:4]) == year and datetime.fromisoformat(x["usable_at_UTC"]) <= clock]
    table_candidates = [x for x in original if x["report"] and x["report"]["tables"].get("soybeans_production", {}).get("present")]
    notices = [reference(x) for x in original if x["report"] and not x["report"]["tables"].get("soybeans_production", {}).get("present")]
    chosen = min(table_candidates, key=lambda x: x["release_date"]) if table_candidates else None
    if chosen is None:
        return None, {}, None, ["annual_original_production_unavailable"], notices
    table = chosen["report"]["tables"]["soybeans_production"]
    if table.get("status") != "parsed_original_schema" or table.get("production_year") != year-1 or table.get("unit") != "1000 bushels":
        return chosen, {}, None, ["annual_original_year_unit_schema_unknown"], notices
    rows = collections.defaultdict(list)
    for row in table["rows"]:
        rows[row["state"]].append(row)
    us = number(rows["United States"][0].get("value")) if len(rows["United States"]) == 1 else None
    reasons = []
    if us is None or us <= 0 or us != us.to_integral_value():
        reasons.append("annual_US_denominator_unknown_or_nonpositive")
    output = {}
    for state in STATES:
        row = rows[state][0] if len(rows[state]) == 1 else None
        q = number(row.get("value")) if row else None
        if q is None or q < 0 or q != q.to_integral_value():
            reasons.append("annual_state_production_unknown:"+state)
            q = None
        output[state] = {"Q_prior_cropyear_1000bushels": int(q) if q is not None else None,
                         "raw_row": row, "unit": "1000 bushels", "production_year": year-1}
    return chosen, output, us, reasons, notices


def write_csv(name, rows):
    fields = ["event_id", "crop_year", "new_init_UTC", "old_init_UTC", "A_UTC", "V_start_UTC", "V_end_UTC",
              "progress_release_date", "progress_record_id", "report_age_hours", "annual_release_date", "annual_record_id",
              "source_qualified", "selected_first8", "unknown_reason_codes", "unknown_positive_production_states",
              "inherited_completion_cells", "weighted_g_sum", "covered_production_fraction_of_US"]
    with (OUT/name).open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(row[key], ensure_ascii=False) if isinstance(row.get(key), (list, dict)) else row.get(key) for key in fields})


def main(apply_observed_row_adapter=False):
    global OUT
    if apply_observed_row_adapter:
        OUT = BASE/"actual_run2_observed_row_adapter"
    if bind(PROTOCOL)["sha256"] != PROTOCOL_SHA:
        raise ValueError("Frozen403 protocol changed")
    if OUT.exists():
        raise FileExistsError("One frozen event build only; no replacement")
    harvest_path = SOURCE/"harvest_manifest.json"
    harvest = json.loads(harvest_path.read_text())
    if not harvest.get("ended_at") or harvest.get("status") != "bounded_harvest_complete_with_explicit_unknowns":
        raise ValueError("Wait for actual401 terminal source before the one build")
    index_path, parsed_path = SOURCE/"reports_index.json", SOURCE/"parsed_original_tables.json"
    inventory, parsed = json.loads(index_path.read_text()), json.loads(parsed_path.read_text())
    records = source_records(inventory, parsed)
    local_adapter = adapt_observed_nc_rows(records) if apply_observed_row_adapter else None
    progress = [x for x in records if x["publication"] == "crop-progress"]
    annual = [x for x in records if x["publication"] == "crop-production-annual-summary"]
    protocol = json.loads(PROTOCOL.read_text())
    requirement = protocol["event_population"]
    events = []
    annual_evidence = {}
    for year in requirement["years"]:
        current = date(year, 7, 1)
        current += timedelta(days=(-current.weekday()) % 7)
        while current <= date(year, 10, 31):
            new = datetime.combine(current, time(0), UTC)
            clock = new+timedelta(hours=37)
            seen = [x for x in progress if x["release_date"][:4] == str(year) and datetime.fromisoformat(x["usable_at_UTC"]) <= clock]
            report = max(seen, key=lambda x: x["release_date"]) if seen else None
            chosen, production, us, reasons, notices = annual_exposure(year, clock, annual)
            if not report:
                reasons.append("no_original_progress_release_available_by_A")
            elif not report["report"]:
                reasons.append("latest_original_progress_source_unknown")
            domain = []
            weighted = Decimal(0)
            qsum = Decimal(0)
            inherited = 0
            unknown_states = []
            with localcontext() as ctx:
                ctx.prec = 40
                for state in STATES:
                    production_row = production.get(state, {})
                    q = number(production_row.get("Q_prior_cropyear_1000bushels"))
                    w = q/us if q is not None and us is not None and us > 0 else None
                    p, ps, pe = resolve_phase(report, "pods", state, year, seen) if report else (None, "no_original_progress", None)
                    l, ls, le = resolve_phase(report, "leaves", state, year, seen) if report else (None, "no_original_progress", None)
                    state_errors = []
                    if p is None:
                        state_errors.append("pods:"+ps)
                    if l is None:
                        state_errors.append("leaves:"+ls)
                    if p is not None and l is not None and p < l:
                        state_errors.append("pods_below_leaves_unknown_no_repair")
                    g = (p-l)/100 if p is not None and l is not None and p >= l else None
                    if w is None:
                        state_errors.append("annual_weight_unknown")
                    required = q is None or q > 0
                    if state_errors and required:
                        unknown_states.append(state)
                    weighted_g = w*g if w is not None and g is not None else Decimal(0) if w == 0 else None
                    if weighted_g is not None:
                        weighted += weighted_g
                    if q is not None:
                        qsum += q
                    inherited += (ps == "inherited_explicit100_completion")+(ls == "inherited_explicit100_completion")
                    domain.append({"state": state, "production_required_positive_or_unknown": required,
                                   "Q_prior_cropyear_1000bushels": int(q) if q is not None else None,
                                   "w": str(w) if w is not None else None,
                                   "pods_pct": str(p) if p is not None else None, "leaves_pct": str(l) if l is not None else None,
                                   "g": str(g) if g is not None else None, "weighted_g": str(weighted_g) if weighted_g is not None else None,
                                   "pods_source_status": ps, "leaves_source_status": ls,
                                   "pods_evidence": pe, "leaves_evidence": le, "unknown_reasons": state_errors})
            if unknown_states:
                reasons.append("required_positive_production_state_phase_or_weight_unknown")
            qualified = not reasons
            event = {"event_id": f"soy-weather-source-{current.isoformat()}", "crop_year": year,
                     "new_init_UTC": new.isoformat(), "old_init_UTC": (new-timedelta(days=1)).isoformat(),
                     "A_UTC": clock.isoformat(), "A_CST": clock.astimezone(ZoneInfo("Asia/Shanghai")).isoformat(),
                     "V_start_UTC": (new+timedelta(hours=48)).isoformat(), "V_end_UTC": (new+timedelta(hours=216)).isoformat(),
                     "progress_release_date": report["release_date"] if report else None,
                     "progress_record_id": report["record_id"] if report else None,
                     "progress_reference": reference(report),
                     "report_age_hours": (clock-datetime.fromisoformat(report["usable_at_UTC"])).total_seconds()/3600 if report else None,
                     "annual_release_date": chosen["release_date"] if chosen else None,
                     "annual_record_id": chosen["record_id"] if chosen else None,
                     "annual_reference": reference(chosen), "US_Q_prior_cropyear_1000bushels": int(us) if us else None,
                     "source_qualified": qualified, "selected_first8": False,
                     "unknown_reason_codes": sorted(set(reasons)), "unknown_positive_production_states": unknown_states,
                     "inherited_completion_cells": inherited,
                     "weighted_g_sum": str(weighted) if qualified else None,
                     "known_component_weighted_g_not_full_feature": str(weighted),
                     "covered_production_fraction_of_US": str(qsum/us) if us and not any(x.startswith("annual_") for x in reasons) else None,
                     "states": domain}
            events.append(event)
            if chosen:
                annual_evidence[str(year)] = {"record": reference(chosen), "US_Q_prior_cropyear_1000bushels": int(us) if us else None,
                                              "states": production, "nonproduction_notices_not_substituted": notices}
            current += timedelta(days=7)
    selected = []
    year_counts = {}
    for year in requirement["years"]:
        this_year = [x for x in events if x["crop_year"] == year]
        qualified = [x for x in this_year if x["source_qualified"]]
        chosen = qualified[:8]
        for event in chosen:
            event["selected_first8"] = True
        selected.extend(chosen)
        year_counts[str(year)] = {"all_candidates": len(this_year), "all_source_qualified": len(qualified),
                                  "selected_first8_source_qualified": len(chosen), "unknown_candidates": len(this_year)-len(qualified),
                                  "qualified_after_first8_not_substitutes": max(0, len(qualified)-8),
                                  "selected_event_ids": [x["event_id"] for x in chosen],
                                  "unknown_reasons": dict(collections.Counter(reason for x in this_year if not x["source_qualified"] for reason in x["unknown_reason_codes"]))}
    train = sum(year_counts[str(y)]["selected_first8_source_qualified"] for y in requirement["train_years_required"])
    held = sum(year_counts[str(y)]["selected_first8_source_qualified"] for y in requirement["held_years"])
    gates = {"train_at_least30": train >= requirement["min_source_qualified_train"],
             "train_all_five_years_present": all(year_counts[str(y)]["selected_first8_source_qualified"] > 0 for y in requirement["train_years_required"]),
             "held_at_least15": held >= requirement["min_source_qualified_held_total"],
             "held_each_year_at_least4": all(year_counts[str(y)]["selected_first8_source_qualified"] >= requirement["held_year_min"] for y in requirement["held_years"])}
    passed = all(gates.values())
    selected_report_reuse = collections.Counter(x["progress_record_id"] for x in selected)
    all_qualified_report_reuse = collections.Counter(x["progress_record_id"] for x in events if x["source_qualified"])
    summary = {"schema": "stage402_original_source_eligibility_summary_v1",
               "status": "source_floor_passed_weather_or_finance_not_authorized" if passed else "NO_GO_frozen400_403_source_event_floor_insufficient_stop_specification",
               "source_count_gate_passed": passed, "gates": gates, "year_counts": year_counts,
               "all_candidate_events": len(events), "selected_independent_weather_week_events": len(selected),
               "train_selected_events": train, "held_selected_events": held,
               "distinct_selected_release_reports": len(selected_report_reuse),
               "selected_original_report_reuse_counts": dict(selected_report_reuse),
               "all_source_qualified_original_report_reuse_counts": dict(all_qualified_report_reuse),
               "independent_unit": "crop_year,newMonday00UTC; not states/counties/grid/product rows; repeated reportg disclosed",
               "financial_labels_read": False, "financial_label_overlap_known": False,
               "historical_received_at_known": False,
               "clock_assumption": "Original label following midnight America/New_York, not actual first-seen; actual holiday dates followed",
               "action": "Do not download new weather, read financial labels or fit. Stop this frozen specification if source gate failed; no month/year/phase/threshold rescue.",
               "universe": {"products": 98, "families": 95, "source_explanatory_channel_only": "m.DCE", "full_market_strategy_success": False},
               "local_mechanical_row_adapter": bool(local_adapter),
               "execution_counts": {"event_builds_cumulative": 2 if local_adapter else 1,
                                    "script_invocations_cumulative": 3 if local_adapter else 1,
                                    "pre_event_local_adapter_NameError": 1 if local_adapter else 0,
                                    "one_source_specification_not_new_financial_attempt": True,
                                    "HTTP": 0, "weather_requests": 0, "financial_label_reads": 0, "fit": 0, "cash": 0, "marketAPI": 0}}
    OUT.mkdir(parents=True)
    save("all_candidate_events.json", {"schema": "stage402_complete_candidate_events_v1", "events": events})
    write_csv("all_candidate_events.csv", events)
    write_csv("selected_events.csv", selected)
    write_csv("unknown_events.csv", [x for x in events if not x["source_qualified"]])
    save("selected_event_ids.json", {"selection": "first8qualified chronologically peryear before new weather/Y", "events": [x["event_id"] for x in selected]})
    save("annual_original_exposure_evidence.json", annual_evidence)
    save("source_report_registry.json", [{key: val for key, val in x.items() if key != "report"} for x in records])
    save("qualification_summary.json", summary)
    outputs = [OUT/name for name in ["all_candidate_events.json", "all_candidate_events.csv", "selected_events.csv", "unknown_events.csv", "selected_event_ids.json", "annual_original_exposure_evidence.json", "source_report_registry.json", "qualification_summary.json"]]
    if local_adapter:
        save("local_observed_row_adapter.json", local_adapter)
        outputs.append(OUT/"local_observed_row_adapter.json")
        save("original_annual_tables_with_observed_no_dot_rows.json", {"status": "402local source projection;401originals and manifests unchanged",
             "reports": [{"source": reference(x), "table": x["report"]["tables"]["soybeans_production"]}
                         for x in annual if x.get("local402_observed_row_adapter")],
             "SouthCarolina_not_added_to_fixed18_event_domain": True})
        outputs.append(OUT/"original_annual_tables_with_observed_no_dot_rows.json")
    save("event_table_manifest.json", {"schema": "stage402_frozen_source_event_table_manifest_v1", "created_at": datetime.now(UTC).isoformat(),
                                      "source_401_terminal": bind(harvest_path), "source_401_index": bind(index_path), "source_401_parsed": bind(parsed_path),
                                      "source_401_parser": parsed.get("parser"), "frozen403_protocol": bind(PROTOCOL), "script": bind(__file__),
                                      "outputs": [bind(x) for x in outputs], "source_gate_passed": passed,
                                      "source_freeze_before_new_weather_or_financial_labels": True,
                                      "previous_397_single_physical_sample_exists_not_used_for_selection": True,
                                      "whole_goal_achieved": False, "fit": 0, "cash": 0})
    print(json.dumps({key: summary[key] for key in ["status", "year_counts", "all_candidate_events", "train_selected_events", "held_selected_events", "distinct_selected_release_reports"]}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--observed-nc-row-adapter", action="store_true")
    main(apply_observed_row_adapter=parser.parse_args().observed_nc_row_adapter)
