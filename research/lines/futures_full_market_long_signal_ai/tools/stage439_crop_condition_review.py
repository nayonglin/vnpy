#!/usr/bin/env python3
"""Independent one-pass bounded source-output review; no author imports or prices."""
import hashlib
import json
import re
import statistics
import time
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

BASE = Path('/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai')
ACTUAL = BASE / 'outputs/stage438_crop_condition_extract/actual_run1'
OUT = BASE / 'outputs/stage439_crop_condition_review/source_run1'
AUTHOR_SHA = '0734570ce5e0f29199a9e068419f2a400345a53714b5b1ba2a67d91d7381f870'
CASE_DATES = ['2017-04-03', '2018-07-23', '2018-09-10', '2018-09-11',
              '2020-08-24', '2024-08-26', '2024-09-03', '2025-09-02']
CROPS = ['Corn', 'Soybeans']
MONTHS = {v:i+1 for i,v in enumerate(['January','February','March','April','May','June',
    'July','August','September','October','November','December'])}
checks = 0
failures = []
raw_reads = []
input_bindings = {}
started = datetime.now(timezone.utc).isoformat()


def check(ok, label):
    global checks
    checks += 1
    if not ok:
        failures.append(label)


def digest(blob):
    return hashlib.sha256(blob).hexdigest()


def bind(path, blob):
    return {'path':str(path), 'bytes':len(blob), 'sha256':digest(blob)}


def read_input(path):
    blob = path.read_bytes()
    input_bindings[str(path)] = bind(path, blob)
    return blob


def dparse(text):
    match = re.search(r'\b('+'|'.join(MONTHS)+r')\s+(\d{1,2}),\s*(\d{4})\b',text)
    return date(int(match[3]), MONTHS[match[1]], int(match[2])).isoformat() if match else None


def five_from_evidence(field, tag):
    candidates = field['candidates']
    if len(candidates) != 1:
        check(field['five_categories'] is None and field['good_plus_excellent'] is None,
              tag+':missing/duplicate row does not invent numbers')
        return None
    item=candidates[0]
    check(item['line_number']==field['line_number'] and item['raw_line']==field['raw_line'],tag+':row evidence binding')
    tokens=item['raw_line'].split(':',1)[1].split()
    check(tokens==field['raw_tokens'], tag+':raw tokens')
    zero_defined=bool(field['zero_definition']) and all(re.fullmatch(r'\s*-\s+Represents zero\.\s*',x['raw_line']) for x in field['zero_definition'])
    nums=[]
    for token in tokens:
        if token.isdigit(): nums.append(int(token))
        elif token=='-' and zero_defined: nums.append(0)
        else: return None
    if len(nums)!=5 or min(nums)<0 or max(nums)>100 or sum(nums)!=100:
        return None
    check(nums==field['five_categories'],tag+':five numbers')
    if field['status']=='known':
        check(field['good_plus_excellent']==nums[3]+nums[4],tag+':GE')
    else:
        check(field['good_plus_excellent'] is None,tag+':unknown GE retained null')
    return nums


def stat(values):
    if not values:
        return {'n':0,'minimum':None,'maximum':None,'mean':None,'median':None,'frequency':{}}
    return {'n':len(values),'minimum':min(values),'maximum':max(values),'mean':statistics.mean(values),
            'median':statistics.median(values),'frequency':dict(sorted((str(k),v) for k,v in Counter(values).items()))}


def same_stat(a,b,label):
    for k in ['n','minimum','maximum','median','frequency']:
        check(a[k]==b[k],label+':'+k)
    check((a['mean'] is None and b['mean'] is None) or
          (a['mean'] is not None and b['mean'] is not None and abs(a['mean']-b['mean'])<1e-12),label+':mean')


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    t0=time.monotonic()
    try:
        rows=[json.loads(line) for line in read_input(ACTUAL/'crop_rows.jsonl').decode().splitlines()]
        reports_doc=json.loads(read_input(ACTUAL/'reports.json'))
        reports=reports_doc['reports']
        summary=json.loads(read_input(ACTUAL/'summary.json'))
        startup=json.loads(read_input(ACTUAL/'startup.json'))
        terminal=json.loads(read_input(ACTUAL/'terminal.json'))
        preflight=json.loads(read_input(ACTUAL/'preflight.json'))
        auth=json.loads(read_input(BASE/'outputs/stage438_crop_condition_extract/root_authorization.json'))
        author_code=read_input(BASE/'tools/stage438_crop_condition_extract.py')
        fixture_code=read_input(BASE/'tools/stage438_crop_condition_fixture.py')
        scope_blob=read_input(BASE/'outputs/stage437_crop_condition_scope/scope.json')
        scope=json.loads(scope_blob)
        check(digest(author_code)==AUTHOR_SHA,'author frozen SHA')
        check(startup['script']['sha256']==terminal['script']['sha256']==auth['script_sha256']==AUTHOR_SHA,'startup/terminal/authorization code binding')
        check(startup['scope_sha256']==terminal['scope_sha256']==reports_doc['scope_sha256']==auth['scope_sha256']==digest(scope_blob),'scope binding')
        check(startup['authorization']==terminal['authorization']==input_bindings[str(BASE/'outputs/stage438_crop_condition_extract/root_authorization.json')],'authorization file binding')
        check(terminal['status']=='complete' and terminal['error'] is None,'complete terminal')
        check(len(rows)==618 and len(reports)==309,'source population 309x2')
        flat=[r for report in reports for r in report['rows']]
        check(flat==rows,'reports and jsonl exact row equality')
        bydate={r['metadata_release_date']:r for r in reports}
        check(len(bydate)==309 and len({r['source']['path'] for r in reports})==309,'unique dates and source paths')
        check(set(bydate)==set(sorted(bydate)),'unique metadata dates')
        observed={}
        evidence_five={}
        for report in reports:
            day=report['metadata_release_date']
            check(len(report['rows'])==2 and {x['crop'] for x in report['rows']}==set(CROPS),day+':both slots')
            release=report['body_release']
            release_lines=release['candidates']
            rdate=dparse(release_lines[0]['raw_line']) if len(release_lines)==1 else None
            expected_release_known=len(release_lines)==1 and rdate==day
            check((release['status']=='known')==expected_release_known,day+':release qualification')
            check(release['body_release_date']==rdate,day+':release parse')
            check(release['historical_first_seen']=='unknown',day+':firstseen unknown')
            for row in report['rows']:
                tag=day+':'+row['crop']
                check(row['source']==report['source'] and row['body_release']==release,tag+':parent identity')
                n=five_from_evidence(row['current'],tag+':current')
                five_from_evidence(row['printed_previous_week'],tag+':previous printed')
                five_from_evidence(row['printed_previous_year'],tag+':previous year')
                tables=row['table_candidates']
                valid_table=False
                if len(tables)==1:
                    table=tables[0]
                    ref=dparse(' '.join(x['raw_line'] for x in table['reference_date_evidence']))
                    check(row['reference_week_date']==ref==table['reference_week_date'],tag+':reference date')
                    headers=[x for x in table['header_candidates'] if [re.sub(r'\s+',' ',x.strip()).lower() for x in x['raw_line'].split(':')]==['state','very poor','poor','fair','good','excellent']]
                    check(table['current']['raw_line']==row['current']['raw_line'],tag+':national row table binding')
                    valid_table=(ref is not None and len(headers)==1 and n is not None and rdate is not None and ref<=rdate)
                known=bool(expected_release_known and valid_table and not row['unknown_reasons'])
                check((row['current']['status']=='known')==known,tag+':current qualification')
                check(row['historical_first_seen']=='unknown',tag+':firstseen unknown')
                if not known:
                    check(row['current']['good_plus_excellent'] is None and row['unknown_reasons'],tag+':unknown not imputed')
                observed[(day,row['crop'])]=row
                evidence_five[(day,row['crop'])]=n
        ordered=sorted(bydate)
        reconstructed_changes={}
        reconstructed_revision={}
        for index,day in enumerate(ordered):
            prevday=ordered[index-1] if index else None
            for crop in CROPS:
                row=observed[day,crop]
                adj=row['adjacent_change']
                prev=observed[prevday,crop] if prevday else None
                ref=row['reference_week_date']; pref=prev['reference_week_date'] if prev else None
                gap=(date.fromisoformat(ref)-date.fromisoformat(pref)).days if ref and pref else None
                known=(prev is not None and gap==7 and ref[:4]==pref[:4] and
                       row['current']['status']=='known' and prev['current']['status']=='known')
                value=(evidence_five[day,crop][3]+evidence_five[day,crop][4]-evidence_five[prevday,crop][3]-evidence_five[prevday,crop][4]) if known else None
                tag=day+':'+crop
                check(adj['previous_metadata_release_date']==prevday,tag+':immediate predecessor')
                check(adj['previous_source']==(prev['source'] if prev else None),tag+':previous source')
                check(adj['previous_release_source_candidates']==([prev['source']] if prev else []),tag+':previous source candidates')
                check(adj['previous_reference_week_date']==pref and adj['reference_gap_days']==gap,tag+':reference adjacency')
                check((adj['status']=='known')==known and adj['value_pp']==value,tag+':original release GE delta')
                check(adj['same_report_previous_week_used_as_original'] is False,tag+':no previous-week substitution')
                if not known: check(adj['unknown_reasons'] and adj['value_pp'] is None,tag+':unknown delta')
                printed=row['printed_previous_week']
                pdate=printed['explicit_reference_date']
                revision_known=bool(known and printed['status']=='known' and (pdate is None or pdate==pref))
                diag=row['revision_diagnostic']
                check((diag['status']=='known')==revision_known,tag+':revision qualification')
                if revision_known:
                    delta=printed['five_categories'][3]+printed['five_categories'][4]-sum(evidence_five[prevday,crop][3:])
                    differs=printed['five_categories']!=evidence_five[prevday,crop]
                    check(diag['five_categories_differ']==differs and diag['printed_previous_minus_original_GE_pp']==delta,tag+':five-field revision semantic')
                else:
                    check(diag['five_categories_differ'] is None and diag['printed_previous_minus_original_GE_pp'] is None,tag+':unknown revision')
                reconstructed_changes[day,crop]=value
                reconstructed_revision[day,crop]=diag
        years=sorted({int(x[:4]) for x in ordered})
        yearly=[]
        for year in years:
            for crop in CROPS:
                group=[r for r in rows if int(r['metadata_release_date'][:4])==year and r['crop']==crop]
                k=sum(r['current']['status']=='known' for r in group)
                a=sum(reconstructed_changes[r['metadata_release_date'],crop] is not None for r in group)
                yearly.append({'metadata_release_year':year,'crop':crop,'total':len(group),'known_current':k,'known_adjacent_change':a,'unknown_current':len(group)-k})
        check(yearly==summary['year_crop'],'all year/crop counts')
        known_count=sum(r['current']['status']=='known' for r in rows)
        adj_count=sum(x is not None for x in reconstructed_changes.values())
        check(known_count==summary['known_current'] and adj_count==summary['known_adjacent_change'],'all known totals')
        shared={'metadata_distinct_release_count':len(ordered),'body_release_agrees_with_metadata':sum(r['body_release']['status']=='known' for r in reports),
                'any_crop_known':sum(any(x['current']['status']=='known' for x in r['rows']) for r in reports),
                'both_crops_known':sum(all(x['current']['status']=='known' for x in r['rows']) for r in reports),
                'two_crops_are_not_independent_release_events':True}
        check(shared==summary['shared_releases'],'shared release counts')
        check(dict(Counter(reason for r in rows for reason in r['unknown_reasons']))==summary['missing_or_conflicting_reasons'],'missing/conflict histogram')
        check(dict(Counter(reason for r in rows for reason in r['adjacent_change']['unknown_reasons']))==summary['adjacent_unknown_reasons'],'adjacent unknown histogram')
        check(dict(Counter(r['coverage']['status'] for r in rows))==summary['coverage_status_counts'],'coverage histogram')
        rc=Counter()
        for diag in reconstructed_revision.values():
            rc[diag['status']]+=1
            if diag['status']=='known':
                rc['five_categories_differ' if diag['five_categories_differ'] else 'five_categories_same']+=1
                if diag['printed_previous_minus_original_GE_pp']!=0: rc['GE_differs']+=1
        check(dict(rc)==summary['revision_diagnostic_counts'],'revision summary')
        check(not summary['revision_examples_earliest_max12'] and not rc['five_categories_differ'],'no observed revision examples')
        check(dict(Counter(date.fromisoformat(x).strftime('%A') for x in ordered))==summary['metadata_release_weekdays'],'weekday histogram')
        for crop in CROPS:
            values=[sum(evidence_five[r['metadata_release_date'],crop][3:]) for r in rows if r['crop']==crop and r['current']['status']=='known']
            deltas=[v for (d,c),v in reconstructed_changes.items() if c==crop and v is not None]
            same_stat(stat(values),summary['crop_distributions'][crop]['GE'],crop+':GE distribution')
            same_stat(stat(deltas),summary['crop_distributions'][crop]['adjacent_original_GE_change_pp'],crop+':change distribution')
            check(dict(Counter(str(r['adjacent_change']['reference_gap_days']) for r in rows if r['crop']==crop))==summary['reference_gap_counts_by_crop'][crop],crop+':reference gap histogram')
        check(summary['original_first_seen']['status']=='unknown' and summary['original_first_seen']['reports']==309,'all firstseen unknown')
        check(summary['operations']==terminal['operations'],'terminal summary operation agreement')
        op=terminal['operations']
        check(op['original_body_reads']==op['original_body_unique_reads']==op['same_read_SHA_size_validations']==309,'author logged single-read counts')
        check(all(op[k]==0 for k in ['HTTP','market_API','SQL','price_Y_score_reads','fit','cash','future_D','original_body_writes']),'prohibited logged operations zero')
        # The only original TXT reads in this reviewer: fixed eight distinct cases, one read each.
        case_evidence=[]
        case_cache={}
        for day in CASE_DATES:
            report=bydate[day]; src=report['source']; path=Path(src['path'])
            check(str(path) not in raw_reads,'unique raw read:'+day)
            raw_reads.append(str(path))
            blob=path.read_bytes()
            check(len(blob)==src['bytes'] and digest(blob)==src['sha256'],'sample SHA/bytes:'+day)
            lines=blob.decode('utf-8-sig').splitlines()
            case_cache[day]=lines
            snippets={}
            def line_check(item,label):
                n=item['line_number']
                check(1<=n<=len(lines) and lines[n-1]==item['raw_line'],day+':raw evidence:'+label)
                snippets[n]=lines[n-1]
            for item in report['body_release']['candidates']: line_check(item,'release')
            literal_releases=[x for x in lines if re.match(r'^\s*Released\b',x)]
            check(len(literal_releases)==len(report['body_release']['candidates']),day+':raw release candidates exhaustive')
            for row in report['rows']:
                crop=row['crop']
                titlepattern=re.compile(r'^\s*'+('Corn' if crop=='Corn' else 'Soybeans?')+r' Condition\b',re.I)
                titles=[(i,x) for i,x in enumerate(lines,1) if titlepattern.match(x)]
                check(len(titles)==len(row['table_candidates']),day+':raw title candidates:'+crop)
                for table in row['table_candidates']:
                    line_check(table['title'],crop+' title')
                    for field in ['current','printed_previous_week','printed_previous_year']:
                        for item in table[field]['candidates']: line_check(item,crop+' '+field)
                        for item in table[field]['zero_definition']: line_check(item,crop+' zero definition')
                    for item in table['reference_date_evidence']: line_check(item,crop+' reference')
                    for item in table['header_candidates']: line_check(item,crop+' header')
                    for cov in table['coverage']['candidates']:
                        line_check(cov,crop+' coverage')
                        raw_text='\n'.join(lines[cov['line_number']-1:cov['line_end']])
                        check(raw_text==cov['raw_text'],day+':raw multiline coverage:'+crop)
            for policy in report['literal_policy_passages']:
                text='\n'.join(lines[policy['line_start']-1:policy['line_end']])
                check(text==policy['raw_text'],day+':raw policy passage')
            case_evidence.append({'metadata_release_date':day,'source':src,'raw_body_read_count':1,
                                  'line_count':len(lines),'body_release_status':report['body_release']['status'],
                                  'crops':[{'crop':r['crop'],'current_status':r['current']['status'],
                                            'five_categories':r['current']['five_categories'],
                                            'GE':r['current']['good_plus_excellent'],
                                            'adjacent_change':r['adjacent_change']['value_pp'],
                                            'reasons':r['unknown_reasons']} for r in report['rows']],
                                  'checked_line_evidence':[{'line_number':k,'raw_line':v} for k,v in sorted(snippets.items())]})
        expected_431={('2018-07-23','Corn'):[3,6,19,50,22],('2018-07-23','Soybeans'):[2,6,22,52,18],
                      ('2020-08-24','Corn'):[4,8,24,49,15],('2020-08-24','Soybeans'):[2,6,23,55,14],
                      ('2024-09-03','Corn'):[4,8,23,50,15],('2024-09-03','Soybeans'):[3,7,25,52,13]}
        for key,val in expected_431.items(): check(evidence_five[key]==val,'431 literal 3 reports/6 crop cases:'+str(key))
        for crop in CROPS:
            check(reconstructed_changes['2018-09-11',crop] is None,'notice breaks immediately adjacent chain:'+crop)
            check(reconstructed_changes['2024-09-03',crop]==(0 if crop=='Corn' else -2),'raw adjacent pair 2024:'+crop)
        check(any('Represents zero.' in x for x in case_cache['2020-08-24']),'real table zero definition present')
        check(not any('-' in (r['current']['raw_tokens'] or []) for r in rows),'no real national dash-zero token in 618 slots')
        soy_dev=sum(x['known_adjacent_change'] for x in yearly if x['crop']=='Soybeans' and 2017<=x['metadata_release_year']<=2022)
        soy_held=sum(x['known_adjacent_change'] for x in yearly if x['crop']=='Soybeans' and 2023<=x['metadata_release_year']<=2025)
        held_counts={str(x['metadata_release_year']):x['known_adjacent_change'] for x in yearly if x['crop']=='Soybeans' and 2023<=x['metadata_release_year']<=2025}
        source_gate=soy_dev>=50 and soy_held>=30 and all(x>=10 for x in held_counts.values())
        receipt={'schema':'stage439_crop_condition_independent_source_review_v1','started_at':started,
                 'ended_at':datetime.now(timezone.utc).isoformat(),'status':'accepted' if not failures else 'rejected',
                 'remaining_core_problems':len(failures),'core_problems':failures,'checks':checks,
                 'reviewer_script':bind(Path(__file__).resolve(),Path(__file__).read_bytes()),
                 'author_code_sha256':digest(author_code),'input_bindings':list(input_bindings.values()),
                 'scope':{'new_report_outputs':309,'new_crop_rows':618,'original_body_reads_actual':len(raw_reads),
                          'original_body_distinct_reads_actual':len(set(raw_reads)),'max_original_body_reads':8,
                          'no_author_extractor_rerun':True,'no_author_code_import':True,
                          'all_NEW_output_field_semantics_rebuilt':True,'all_309_raw_bodies_reparsed':False,
                          'author_309_reads_verified_by':'logged startup/terminal plus code inspection; not independent instrumentation'},
                 'reconstructed':{'known_current':known_count,'known_adjacent_change':adj_count,
                                  'year_crop':yearly,'shared_releases':shared,'revision_diagnostic_counts':dict(rc),
                                  'soy_development_adjacent':soy_dev,'soy_later_adjacent':soy_held,'soy_held_years':held_counts},
                 'cases':case_evidence,'source_440_count_gate':source_gate,
                 'eligible_for_root_to_consider_440_fixed_timing_diagnostic':source_gate and not failures,
                 'price_actual_authorized':False,'financial_actual_authorized':False,
                 'limitations':['Historical first-seen and first-release bytes remain unverified for all reports.',
                                '342 known five-category revision diagnostics show no differences; this does not prove no revisions outside comparable archive pairs.',
                                '8 raw cases verify evidence fidelity; remaining 301 bodies were not independently reparsed.',
                                'A maximum of nine source years and three later years does not establish independent weekly observations or calibrated confidence.',
                                'Source acceptance is not a tradable alpha, costed return, fit, cash or production qualification.'],
                 'operations':{'review_script_actual_runs':1,'original_body_reads':len(raw_reads),'API':0,'HTTP':0,'SQL':0,
                               'price_Y_score_reads':0,'fit':0,'cash':0,'future_D':0,'author_extractor_runs':0},
                 'elapsed_seconds':time.monotonic()-t0}
        (OUT/'review_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
        print(json.dumps({'status':receipt['status'],'checks':checks,'remaining_core_problems':len(failures),
                          'raw_reads':len(raw_reads),'source_gate':source_gate,'receipt_sha256':digest((OUT/'review_receipt.json').read_bytes()),
                          'soy_dev':soy_dev,'soy_held':soy_held,'held_years':held_counts},ensure_ascii=False))
    except Exception as exc:
        failure={'schema':'stage439_crop_condition_review_failure_v1','started_at':started,'error_type':type(exc).__name__,
                 'error':str(exc),'raw_reads_before_error':raw_reads,'checks':checks,'failures':failures,
                 'input_bindings':list(input_bindings.values())}
        (OUT/'failure.json').write_text(json.dumps(failure,ensure_ascii=False,indent=2)+'\n')
        raise


if __name__=='__main__':
    main()
