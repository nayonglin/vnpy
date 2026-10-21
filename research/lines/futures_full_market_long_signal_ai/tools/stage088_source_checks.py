"""One new OI-column SELECT and independent full085 reconstruction, no author code."""
import io,json,sqlite3,math
from pathlib import Path
from collections import Counter
import numpy as np
import pandas as pd
from stage088_cash_adapter import bound,compare,numeric

QUERIES=0
IDS=['sequence_index','event_id','product_id','family_id','exchange','u_date','u_index','reference_epoch']

def state(binding):
    p=Path(binding['path']).resolve();s=p.stat()
    x=dict(path=str(p),bytes=s.st_size,mtime_ns=s.st_mtime_ns,inode=s.st_ino,wal_present=Path(str(p)+'-wal').exists(),shm_present=Path(str(p)+'-shm').exists())
    assert all(x[k]==binding[k]for k in x),'accepted DB stat changed'
    return x

def valid(x):
    return x is not None and isinstance(x,(int,float,np.number)) and math.isfinite(float(x))

def unit(row,contract):
    epoch,day,exchange,oi,volume,source,family,vf,of,quality,nv,no,locator=row
    if not(valid(vf)and valid(of))or contract['canonical_quantity_unit']!='single_sided_contracts'or contract['cleaner_rule_approved']is not True:
        return 'unknown_or_inconsistent_unit','unit_contract_or_factor_unknown'
    expected=None;name='source_family_or_identity_unknown'
    if family=='rqalpha'and source=='rqalpha':
        matches=[r for r in contract['rqalpha']['rules']if exchange in r['exchanges']and r['start']<=day<=r['end']]
        if len(matches)==1:
            r=matches[0];expected=(r['volume_factor'],r['close_oi_factor']);name=f"rqalpha_{r['start']}_{r['end']}_{exchange}"
    elif family in ('old_tq','recent_tq')and str(source).startswith(family+':'):
        expected=(contract[family]['volume_factor'],contract[family]['close_oi_factor']);name=family+'_inherited_pinned_stage266'
    elif family=='official'and str(source).startswith('official:')and vf==of and vf in set(contract['official']['accepted_regime_factors'].values()):
        expected=(vf,of);name='official_inherited_stage266_accepted_factor'
    return ('accepted_canonical_inherited_stage266',name)if expected==(vf,of)else('unknown_or_inconsistent_unit',name)

def review_source(manifest,mother,calendar,protocol):
    global QUERIES
    assert QUERIES==0,'one independent new-OI SELECT only'
    contract=json.loads(bound(protocol['unit_contract']));db=protocol['database'];before=state(db)
    needed={(r.reference_epoch,calendar[k])for r in mother.itertuples()if r.reference_epoch for k in (int(r.u_index)-1,int(r.u_index)-2)if k>=0}
    query='''SELECT d.contract_epoch_id,d.trade_date,d.exchange,d.close_oi,d.volume,d.source_id,s.family,d.volume_factor,d.oi_factor,d.quality_status,d.native_volume,d.native_close_oi,d.source_locator FROM daily_bars AS d LEFT JOIN sources AS s ON s.source_id=d.source_id WHERE d.trade_date BETWEEN ? AND ? ORDER BY d.contract_epoch_id,d.trade_date'''
    lookup={};scanned=0;QUERIES+=1
    uri=Path(db['path']).resolve().as_uri()+'?mode=ro&immutable=1'
    with sqlite3.connect(uri,uri=True)as con:
        for row in con.execute(query,(calendar[0],calendar[-1])):
            scanned+=1;key=(row[0],row[1])
            if key in needed:
                assert key not in lookup,'duplicate new OI epoch/day';lookup[key]=row
    after=state(db);units={key:unit(row,contract)for key,row in lookup.items()}
    p=pd.read_csv(io.BytesIO(bound(manifest['projection'])),compression='gzip',dtype=str,keep_default_na=False)
    assert len(p)==len(mother)==399252
    for c in IDS:
        if c in ('sequence_index','u_index'):compare(pd.to_numeric(p[c]),mother[c],'OI_identity_'+c,atol=0,rtol=0)
        else:assert p[c].tolist()==mother[c].tolist(),('OI_identity',c)
    nums=['v_index','w_index','v_close_oi','w_close_oi','v_volume','w_volume','v_volume_factor','w_volume_factor','v_oi_factor','w_oi_factor','v_native_volume','w_native_volume','v_native_close_oi','w_native_close_oi','oi_scalar_raw','oi_observed','oi_missing']
    numeric(p,nums);raw=np.full(len(p),np.nan);reasons_all=[];observed=0;zero=0;transitions=0
    fields={}
    for i,r in enumerate(mother.itertuples(index=False)):
        u=int(r.u_index);reasons=[];lags={};epoch=r.reference_epoch
        if not epoch:reasons.append('no_reference_epoch')
        if u<2:reasons.append('missing_lag_source_day')
        for name,k in [('v',u-1),('w',u-2)]:
            assert p.at[i,name+'_index']==k
            if k<0:assert p.at[i,name+'_date']=='';continue
            day=calendar[k];assert p.at[i,name+'_date']==day
            row=lookup.get((epoch,day))if epoch else None
            if row is None:
                reasons.append('missing_'+name+'_bar')
                assert all(np.isnan(p.at[i,name+'_'+x])for x in ('close_oi','volume','volume_factor','oi_factor','native_volume','native_close_oi'))
                assert all(p.at[i,name+'_'+x]==''for x in ('source_id','source_family','quality_status','source_locator','unit_state','unit_rule_id'))
                continue
            lags[name]=row;st,rule=units[(epoch,day)]
            mapping={'close_oi':row[3],'volume':row[4],'volume_factor':row[7],'oi_factor':row[8],'native_volume':row[10],'native_close_oi':row[11]}
            for key,value in mapping.items():
                fields.setdefault(name+'_'+key,[[],[]]);fields[name+'_'+key][0].append(p.at[i,name+'_'+key]);fields[name+'_'+key][1].append(float(value)if valid(value)else np.nan)
            for key,value in dict(source_id=row[5],source_family=row[6],quality_status=row[9],source_locator=row[12],unit_state=st,unit_rule_id=rule).items():assert p.at[i,name+'_'+key]==(value or ''),(i,name,key)
            if row[9]!='accepted':reasons.append('unaccepted_'+name+'_bar')
            if st!='accepted_canonical_inherited_stage266':reasons.append('unaccepted_'+name+'_unit')
            if not valid(row[3])or row[3]<0:reasons.append('invalid_'+name+'_close_oi')
            if name=='v'and(not valid(row[4])or row[4]<=0):reasons.append('invalid_v_volume')
        if len(lags)==2 and lags['v'][5]!=lags['w'][5]:reasons.append('different_source_id')
        if not reasons:
            value=(lags['v'][3]-lags['w'][3])/lags['v'][4]
            if valid(value):raw[i]=value
            else:reasons.append('nonfinite_ratio')
        known=not reasons;why='|'.join(dict.fromkeys(reasons));reasons_all.append(why)
        assert p.at[i,'oi_observed']==int(known)and p.at[i,'oi_missing']==int(not known)
        assert p.at[i,'missing_reason']==why and p.at[i,'projection_state']==('observed_same_epoch_same_source_canonical'if known else'missing')
        observed+=int(known);zero+=int(known and raw[i]==0);transitions+=int(known and lags['v'][8]!=lags['w'][8])
    for key,(saved,expected)in fields.items():compare(saved,expected,'OI_raw_'+key,atol=1e-10,rtol=2e-12)
    compare(p.oi_scalar_raw,raw,'all399252_OI_formula',atol=1e-12,rtol=2e-12)
    root=Path(manifest['projection']['path']).parent;summary=json.loads((root/'projection_summary.json').read_text())
    for key,value in dict(mother_rows=len(p),observed=observed,missing=len(p)-observed,valid_zero=zero).items():assert summary[key]==value,key
    assert summary['missing_reasons']==dict(Counter(v for v in reasons_all if v))
    coverage=pd.read_csv(root/'coverage.csv.gz',dtype=str,keep_default_na=False)
    expected=p.assign(year=p.u_date.str[:4]).groupby(['exchange','year','projection_state','missing_reason'],dropna=False).size().rename('rows').reset_index()
    assert coverage[['exchange','year','projection_state','missing_reason']].equals(expected[['exchange','year','projection_state','missing_reason']])
    assert np.array_equal(pd.to_numeric(coverage.rows),expected.rows)
    finite=json.loads((root/'finite_source_cases.json').read_text());assert finite['additional_native_queries']==0
    selectors=[('observed',p.oi_observed.eq(1)),('valid_zero',p.oi_observed.eq(1)&p.oi_scalar_raw.eq(0)),('canonical_factor_transition',p.oi_observed.eq(1)&p.v_oi_factor.ne(p.w_oi_factor))]
    selectors +=[(why,p.missing_reason.str.contains(why,regex=False))for why in('no_reference_epoch','missing_v_bar','missing_w_bar','different_source_id','unaccepted_v_unit','unaccepted_w_unit','invalid_v_volume')]
    cases={x['kind']:x for x in finite['cases']};assert set(cases)=={kind for kind,mask in selectors if mask.any()}
    for kind,mask in selectors:
        if mask.any():assert cases[kind]['projection']['event_id']==p.loc[mask].iloc[0].event_id
    return p,dict(mother_rows=len(p),observed=observed,missing=len(p)-observed,valid_zero=zero,canonical_factor_transitions=transitions,independent_new_OI_queries=QUERIES,query=query,query_parameters=[calendar[0],calendar[-1]],native_rows_scanned=scanned,lag_keys_needed=len(needed),lag_rows_retained=len(lookup),database_before=before,database_after=after,database_rehashed=False,old_cleaner_or_PIT_reaudit=False,coverage_rows=len(coverage),finite_first_source_cases=len(cases))
