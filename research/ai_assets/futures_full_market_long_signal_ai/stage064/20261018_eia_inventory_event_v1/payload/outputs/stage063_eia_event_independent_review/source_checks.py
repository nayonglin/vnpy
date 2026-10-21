"""Independent checks of saved EIA sources; no network and no author imports."""
import csv
from datetime import datetime,time,date,timezone,timedelta
from decimal import Decimal,InvalidOperation
import hashlib
from html import unescape
import io,json,math,re
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
from cash_adapter import bound,compare

LABELS=('Commercial (Excluding SPR)','Total Motor Gasoline','Distillate Fuel Oil')
MONTHS={m:i for i,m in enumerate(('January','February','March','April','May','June','July','August','September','October','November','December'),1)}


def metadata_integer(value):
    try:parsed=Decimal(str(value))
    except InvalidOperation as exc:raise ValueError('metadata is not numeric') from exc
    if not parsed.is_finite() or parsed!=parsed.to_integral_value():
        raise ValueError('metadata must be finite and exactly integral')
    return int(parsed)


def read_csv_binding(item,**kwargs):
    return pd.read_csv(io.BytesIO(bound(item)),compression='gzip' if item['path'].endswith('.gz') else None,**kwargs)


def check_release_cells(html,calendar):
    """Direct independent link/adjacent-cell checks plus complete weekly dates.

    The saved calendar year is cross-checked by its continuous data-week chain;
    no release date is computed from a URL folder's numeric date.
    """
    cells=list(re.finditer(r'<td\b[^>]*>(.*?)</td\s*>',html,re.I|re.S))
    current_month=None;links={}
    for i,match in enumerate(cells):
        body=match.group(1);plain=unescape(re.sub('<[^>]*>','',body)).strip()
        if plain in MONTHS:current_month=MONTHS[plain]
        for link in re.finditer(r'<a\b[^>]*href=["\']([^"\']*?/petroleum/supply/weekly/archive/[^"\']*?wpsr[^"\']*)["\'][^>]*>(.*?)</a>',body,re.I|re.S):
            url=unescape(link.group(1));rid='eia_wpsr_'+Path(urlparse(url).path).parent.name
            release_day=int(re.sub('<[^>]*>','',link.group(2)).strip())
            following=unescape(re.sub('<[^>]*>','',cells[i+1].group(1))).strip()
            assert rid not in links
            links[rid]=(current_month,release_day,following)
    assert set(links)==set(calendar.report_id)
    for row in calendar.itertuples(index=False):
        month,day,ending=links[row.report_id];release=date.fromisoformat(row.release_date)
        assert release.month==month and release.day==day
        pieces=ending.split('/');expected=date.fromisoformat(row.data_ending_expected)
        assert expected.day==int(pieces[-1])
        assert expected.month==(int(pieces[0]) if len(pieces)==2 else month)
        assert expected<release and (release-expected).days<=31
    weeks=sorted(date.fromisoformat(d) for d in calendar.data_ending_expected)
    assert len(set(weeks))==len(calendar)
    assert all(b-a==timedelta(days=7) for a,b in zip(weeks,weeks[1:]))
    return len(links)


def parse_saved_stock(raw,ending,precision_policy='printed_quantum_065'):
    assert precision_policy in ('exact_060','printed_quantum_065')
    lines=list(csv.reader(io.StringIO(raw.decode('utf-8-sig',errors='replace').replace('\x1a',''))))
    header=lines[0]
    assert header[0]=='STUB_1' and header[3]=='Difference'
    assert datetime.strptime(header[1].strip(),'%m/%d/%y').date().isoformat()==ending
    found={}
    for i,row in enumerate(lines[1:],2):
        if row and row[0]=='STUB_1':break
        if not row or row[0] not in LABELS:continue
        assert row[0] not in found
        v=[Decimal(s.replace(',','').strip()) for s in row[1:4]]
        assert all(a.is_finite() for a in v) and v[0]>0 and v[1]>0
        residual=v[0]-v[1]-v[2]
        # A displayed Decimal x represents a rounding interval of half its
        # own printed quantum. Keep trailing zeros; never derive a tolerance
        # from binary floats or reconstruct the provider's unrounded value.
        quantum=[Decimal(1).scaleb(x.as_tuple().exponent) for x in v]
        limit=sum(quantum,Decimal(0))/2
        assert residual==0 if precision_policy=='exact_060' else abs(residual)<=limit
        found[row[0]]=dict(current=float(v[0]*1000),prior_inline=float(v[1]*1000),delta=float(v[2]*1000),row=i,
            precision_residual_native=str(residual),precision_bound_native=str(limit),
            precision_compatible=abs(residual)<=limit)
    assert set(found)==set(LABELS)
    return found


def check_source(source_binding,calendar_dates):
    source=json.loads(bound(source_binding));assert source['schema']=='stage060_eia_import_manifest_v1' and source['status']=='completed'
    producer=source.get('producer','stage060_eia_report_import')
    recovered_layer=producer=='stage065_eia_precision_recovery'
    assert producer in ('stage060_eia_report_import','stage065_eia_precision_recovery')
    assert source.get('fit_or_cash_authorized',False) is False and source['all_families_same_event_eligibility'] is True
    artifacts=source['artifacts']
    for item in artifacts.values():bound(item)
    for item in source['input_bindings'].values():bound(item)
    terminal=json.loads(bound(artifacts['actual_terminal']))
    assert terminal['status']=='completed'
    assert terminal['model_fits']==terminal['cash_accounts']==terminal['sql_queries']==0
    original=None;original_stocks=None;original_reports=None
    if recovered_layer:
        assert source['normalization_stage']=='stage065' and source['new_http_requests']==0
        assert terminal['source_actual_startups']==0 and terminal['offline_normalization_actual_startups']==1
        assert terminal['normalization_actual_startups']==1 and terminal['original060_source_actual_startups']==1
        assert terminal['new_http_requests']==0 and terminal['original_stage060_unchanged'] is True
        assert source['input_bindings']['precision_input_amendment']['sha256']=='46946878f76d2b0a134bf274898868e622c4bded4d021a1add62116f8af3e729'
        original=json.loads(bound(source['input_bindings']['original_stage060_manifest']))
        assert original['schema']=='stage060_eia_import_manifest_v1' and original.get('producer','stage060_eia_report_import')=='stage060_eia_report_import'
        assert original['status']=='completed'
        for item in original['artifacts'].values():bound(item)
        assert source['input_bindings']['original_stage060_actual']==original['artifacts']['actual_terminal']
        assert source['input_bindings']['original_stage060_source_bindings']==original['artifacts']['source_bindings']
        assert source['input_bindings']['original_stage060_implementation']==original['input_bindings']['implementation']
        assert source['input_bindings']['original_stage060_tests']==original['input_bindings']['tests']
        old_terminal=json.loads(bound(original['artifacts']['actual_terminal']))
        assert old_terminal['status']=='completed' and old_terminal['source_actual_startups']==1
        assert old_terminal['model_fits']==old_terminal['cash_accounts']==old_terminal['sql_queries']==0
        assert source['artifacts']['calendar']['sha256']==original['artifacts']['calendar']['sha256']
        for key in ('protocol','archive_acquisition','accepted_china_calendar'):
            assert source['input_bindings'][key]==original['input_bindings'][key]
        original_stocks=read_csv_binding(original['artifacts']['normalized_stocks'],dtype=str,keep_default_na=False)
        original_stocks=original_stocks.set_index(['report_id','series_label'])
        original_reports={r['report_id']:r for r in json.loads(bound(original['artifacts']['source_bindings']))['reports']}
    else:
        assert terminal['source_actual_startups']==1 and terminal['downloads_retried']==0
    assert source['input_bindings']['protocol']['sha256']=='ff1ecad21420681e8e1e8645be3da51172d35d4e24ef506ee3f88d2ed5e20158'
    archive=json.loads(bound(source['input_bindings']['archive_acquisition']))
    raw_html=Path(archive['raw_path']).read_bytes();assert hashlib.sha256(raw_html).hexdigest()==archive['sha256'] and len(raw_html)==archive['bytes'] and archive['status']==200
    calendar=read_csv_binding(artifacts['calendar'],dtype=str,keep_default_na=False)
    assert not calendar.report_id.duplicated().any()
    ordered=calendar.sort_values(['release_date','data_ending_expected','report_id']).reset_index(drop=True)
    assert ordered.report_id.tolist()==calendar.report_id.tolist()
    assert calendar.ordinal.astype(int).tolist()==list(range(len(calendar)))
    archive_checked=check_release_cells(raw_html.decode('utf-8'),calendar)
    values=read_csv_binding(artifacts['normalized_stocks'],dtype=str,keep_default_na=False)
    assert len(values)==3*len(calendar) and not values.duplicated(['report_id','series_label']).any()
    assert set(values.series_label)==set(LABELS)
    for name in ['current','prior_inline','delta']:
        values[name]=pd.to_numeric(values[name].replace('',np.nan),errors='raise')
    all_stocks=values.set_index(['report_id','series_label']);bindings=json.loads(bound(artifacts['source_bindings']))
    reports={r['report_id']:r for r in bindings['reports']};assert set(reports)==set(calendar.report_id)
    if recovered_layer:
        assert bindings['original_stage060_manifest']==source['input_bindings']['original_stage060_manifest']
        assert set(original_reports)==set(reports)
        recovery_audit=read_csv_binding(artifacts['recovery_audit'],dtype=str,keep_default_na=False)
    known=unknown=precision_recovered=original_known_unchanged=0
    for row in calendar.itertuples(index=False):
        record=reports[row.report_id];stocks=all_stocks.loc[row.report_id]
        assert set(stocks.index)==set(LABELS)
        assert stocks.native_unit.eq('million_barrels').all() and stocks.normalized_unit.eq('thousand_barrels').all()
        assert stocks.data_ending.eq(row.data_ending_expected).all()
        eligible=False
        if recovered_layer:
            old=original_reports[row.report_id]
            assert record['original_source_status']==old['source_status'] and record['original_parse_status']==old.get('parse_status')
            for key in ('raw_path','sha256','parse_error','status'):
                assert record.get(key)==old.get(key)
            eligible=old.get('status')==200 and old.get('source_status')=='unknown_parse_failed' and old.get('parse_error','').startswith('current-prior does not equal reported Difference:')
            if old['source_status']=='known':
                assert record['source_status']=='known'
                original_known_unchanged+=1
                for label in LABELS:
                    oldrow=original_stocks.loc[(row.report_id,label)]
                    for key in ('current','prior_inline','delta'):
                        compare(stocks.loc[label,key],float(oldrow[key]),'known060_unchanged_'+key,atol=0.,rtol=0.)
            elif record['source_status']=='known_precision_recovered':
                assert eligible
                precision_recovered+=1
            else:
                assert record['source_status']==old['source_status']
        if record['source_status'] in ('known','known_precision_recovered'):
            known+=1;raw=Path(record['raw_path']).read_bytes()
            assert hashlib.sha256(raw).hexdigest()==record['sha256'] and len(raw)==record['bytes'] and record['status']==200
            parsed=parse_saved_stock(raw,row.data_ending_expected,precision_policy='printed_quantum_065' if recovered_layer else 'exact_060')
            for label in LABELS:
                original=parsed[label];saved=stocks.loc[label]
                for field in ['current','prior_inline','delta']:compare(saved[field],original[field],'source_stock_'+field,atol=0.,rtol=0.)
                assert saved.value_status==record['source_status'] and saved.source_sha256==record['sha256']
                assert metadata_integer(saved.source_row_number)==original['row'] and float(saved.unit_conversion_factor)==1000
                if record['source_status']=='known_precision_recovered':
                    assert saved.normalization_stage=='stage065' and str(saved.precision_rounding_compatible) in ('True','1')
                    compare(float(saved.arithmetic_residual_thousand_barrels),float(Decimal(original['precision_residual_native'])*1000),'precision_residual',atol=0.,rtol=0.)
                    compare(float(saved.precision_rounding_bound_thousand_barrels),float(Decimal(original['precision_bound_native'])*1000),'precision_bound',atol=0.,rtol=0.)
        else:
            unknown+=1
            assert stocks.value_status.eq('unknown').all() and stocks[['current','prior_inline','delta']].isna().all().all()
            if recovered_layer and eligible:
                # A still-unknown arithmetic-only candidate must genuinely
                # fail the printed contract, not simply be skipped.
                raw=Path(record['raw_path']).read_bytes();assert hashlib.sha256(raw).hexdigest()==record['sha256']
                rejected=False
                try:parse_saved_stock(raw,row.data_ending_expected,precision_policy='printed_quantum_065')
                except (AssertionError,ValueError,IndexError,ArithmeticError):rejected=True
                assert rejected
        if recovered_layer and record['original_source_status']!='known':
            ra=recovery_audit.loc[recovery_audit.report_id.eq(row.report_id)]
            report_audit=ra.loc[ra.scope.eq('report')]
            assert len(report_audit)==1 and report_audit.iloc[0].original_source_status==record['original_source_status']
            assert report_audit.iloc[0].original_parse_error==str(record.get('parse_error') or '')
            if record['source_status']=='known_precision_recovered':
                assert report_audit.iloc[0].recovery_status=='recovered'
                assert len(ra.loc[ra.scope.eq('cell')])==3
            for a in ra.loc[ra.scope.eq('cell')].itertuples(index=False):
                nums=[Decimal(a.raw_current),Decimal(a.raw_prior_inline),Decimal(a.raw_difference)]
                quanta=[Decimal(1).scaleb(v.as_tuple().exponent) for v in nums]
                residual=nums[0]-nums[1]-nums[2];limit=sum(quanta,Decimal(0))/2
                assert Decimal(a.residual_native)==residual and Decimal(a.rounding_bound_native)==limit
                assert Decimal(a.current_quantum_native)==quanta[0] and Decimal(a.prior_quantum_native)==quanta[1] and Decimal(a.difference_quantum_native)==quanta[2]
                assert a.rounding_compatible==str(abs(residual)<=limit)
                assert a.original_parse_error==str(record['parse_error'])
        assert record.get('automatic_retries',0)==0
    features=read_csv_binding(artifacts['report_features'],keep_default_na=False,na_values=[''])
    events=read_csv_binding(artifacts['event_map'],keep_default_na=False,na_values=[''])
    assert features.report_id.tolist()==calendar.report_id.tolist() and features.ordinal.tolist()==list(range(len(calendar)))
    dates=[d for d in calendar_dates if d<='2026-10-16']
    closes=[datetime.combine(date.fromisoformat(d),time(16),ZoneInfo('Asia/Shanghai')) for d in dates]
    scalar=[];expected_u=[];available=[];shams=[]
    for i,r in enumerate(calendar.itertuples(index=False)):
        s=np.nan
        if i>=52:
            now=calendar.iloc[i].report_id;lag=calendar.iloc[i-52].report_id;prior=calendar.iloc[i-1].report_id
            component=[]
            for label in LABELS:
                x=all_stocks.loc[(now,label),'delta'];z=all_stocks.loc[(lag,label),'delta'];den=all_stocks.loc[(prior,label),'current']
                cur=all_stocks.loc[(now,label),'current']
                if not np.isfinite([x,z,den,cur]).all() or den<=0:component=[];break
                component.append(-(x-z)/den)
            if len(component)==3:s=math.fsum(component)/3
        compare(features.iloc[i].s,s,'source_seasonal_scalar',atol=1e-14,rtol=1e-12)
        candidates=[j for j in range(max(0,i-52),i) if np.isfinite(scalar[j])]
        missing=not np.isfinite(s) or not candidates
        assert int(features.iloc[i].external_missing)==int(missing)
        chosen=None
        if not missing:
            number=int(hashlib.sha256(('stage057_past_sham_v1|'+r.report_id).encode()).hexdigest(),16)
            chosen=candidates[number%len(candidates)]
            assert features.iloc[i].past_sham_report_id==calendar.iloc[chosen].report_id
            assert int(features.iloc[i].past_sham_ordinal)==chosen
            compare(features.iloc[i].inventory_s,s,'source_inventory_s',atol=1e-14,rtol=1e-12)
            compare(features.iloc[i].past_sham_s,scalar[chosen],'source_past_sham_s',atol=1e-14,rtol=1e-12)
        else:
            assert float(features.iloc[i].inventory_s)==float(features.iloc[i].past_sham_s)==0
        assert int(features.iloc[i].past_sham_candidates)==len(candidates)
        scalar.append(s);shams.append(chosen)
        at=datetime.combine(date.fromisoformat(r.release_date),time(23,59,59),ZoneInfo('America/New_York'))
        available.append(at)
        assert features.iloc[i].available_at_utc==at.astimezone(timezone.utc).isoformat()
        assert features.iloc[i].available_at_china==at.astimezone(ZoneInfo('Asia/Shanghai')).isoformat()
        ui=next((j for j,c in enumerate(closes) if c>at),None)
        u=dates[ui] if ui is not None else None;D=dates[ui+1] if ui is not None and ui+1<len(dates) else None
        actual=features.iloc[i]
        assert (pd.isna(actual.u_date) and u is None) or actual.u_date==u
        assert (pd.isna(actual.native_D_date) and D is None) or actual.native_D_date==D
        assert actual.availability_precision=='date_only_conservative_end_of_day'
        expected_u.append(u)
        if chosen is not None:assert available[chosen]<=at and i-52<=chosen<i
    expected_events={}
    for i,u in enumerate(expected_u):
        if u is None:continue
        previous=expected_events.get(u)
        if previous is None or (calendar.iloc[i].data_ending_expected,calendar.iloc[i].report_id)>(calendar.iloc[previous].data_ending_expected,calendar.iloc[previous].report_id):expected_events[u]=i
    kept=set(expected_events.values())
    for i,r in features.iterrows():
        expected=expected_u[i] is not None and i not in kept
        assert bool(r.superseded_before_first_decision)==expected
    assert events.u_date.tolist()==sorted(expected_events)
    assert events.report_id.tolist()==[calendar.iloc[expected_events[u]].report_id for u in sorted(expected_events)]
    for row in events.itertuples(index=False):
        old=features.loc[features.report_id.eq(row.report_id)].iloc[0]
        for field in ['inventory_s','past_sham_s','external_missing']:compare(getattr(row,field),old[field],'event_map_'+field,atol=0.,rtol=0.)
    coverage=json.loads(bound(artifacts['coverage']))
    assert coverage['calendar_reports']==len(calendar) and coverage['known_reports']==known and coverage['unknown_reports']==unknown
    if recovered_layer:
        assert coverage['precision_recovered_reports']==precision_recovered and coverage['original_known_reports']==original_known_unchanged
        assert coverage['new_http_requests']==0
    assert coverage['scalar_known']==int(np.isfinite(scalar).sum()) and coverage['decision_events']==len(events)
    assert coverage['shared_information_known']==int(features.external_missing.eq(0).sum())
    return source,events,dict(producer=producer,normalization_stage='stage065' if recovered_layer else 'stage060',
        original_known_reports_unchanged=original_known_unchanged,precision_recovered_reports=precision_recovered,
        calendar_reports=len(calendar),release_cells_checked=archive_checked,known_raw_reports_checked=known,
        unknown_reports_retained=unknown,normalized_stock_rows=len(values),scalar_known=int(np.isfinite(scalar).sum()),
        decision_events=len(events),superseded=int(features.superseded_before_first_decision.sum()),
        raw_sources_copied=False,network_downloads=0,first_vintage_proved=False)
