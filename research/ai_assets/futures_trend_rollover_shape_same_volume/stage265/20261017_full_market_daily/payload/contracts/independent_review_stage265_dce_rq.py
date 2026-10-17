"""Independent read-only DCE official-vs-RQ review; no downloads or pickle globals."""
from __future__ import annotations

from collections import Counter, defaultdict
import csv
from datetime import date, datetime
import hashlib
import io
import json
import math
from pathlib import Path
import pickle
import pickletools
import re
from zoneinfo import ZoneInfo

import h5py
import numpy as np

LINE = Path(__file__).resolve().parents[1]
BASE = LINE/'outputs/stage265_deep_daily'
DCE = BASE/'dce'
RQ = BASE/'rqalpha'
PREFIX = 'independent_review_stage265_dce_rq'
FIELDS = ('open','high','low','close')
END = '2026-09-30'
DANGEROUS = {'GLOBAL','STACK_GLOBAL','REDUCE','INST','OBJ','NEWOBJ','NEWOBJ_EX','EXT1','EXT2','EXT4','PERSID','BINPERSID'}


def stamp():
    return datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()


def sha(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for part in iter(lambda:stream.read(1024*1024),b''):digest.update(part)
    return digest.hexdigest()


def save(name,obj):
    path=DCE/(PREFIX+name+'.json')
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')


class PrimitiveOnly(pickle.Unpickler):
    def find_class(self,module,name):
        raise pickle.UnpicklingError('all_global_resolution_forbidden')

    def persistent_load(self,pid):
        raise pickle.UnpicklingError('all_persistent_references_forbidden')


def safe_metadata(path):
    data=path.read_bytes()
    if len(data)>32*1024*1024:raise ValueError('metadata_size_cap')
    bad=[{'opcode':op.name,'position':position} for op,arg,position in pickletools.genops(data) if op.name in DANGEROUS]
    if bad:raise ValueError('nonprimitive_pickle_opcode:'+repr(bad[:5]))
    result=PrimitiveOnly(io.BytesIO(data)).load()
    def validate(item,depth=0):
        if depth>100:raise ValueError('primitive_nesting_cap')
        if type(item) in (str,int,float,bool,type(None),bytes):return
        if type(item) in (list,tuple,set,frozenset):
            for value in item:validate(value,depth+1)
            return
        if type(item) is dict:
            for key,value in item.items():validate(key,depth+1);validate(value,depth+1)
            return
        raise ValueError('nonprimitive_metadata:'+type(item).__name__)
    validate(result)
    if type(result) is not list or any(type(x) is not dict for x in result):raise ValueError('metadata_schema')
    return result,{'pickletools_dangerous_opcodes':bad,'all_find_class_calls_rejected':True,
                   'persistent_load_rejected':True,'recursive_primitive_validation':True}


def identity(item):
    symbol=item['order_book_id']
    match=re.fullmatch(r'([A-Z]+)(\d{2})(\d{2})',symbol)
    if not match or not 1<=int(match[3])<=12:return None
    maturity=item.get('maturity_date','')
    date.fromisoformat(maturity)
    yyyymm=maturity[:4]+maturity[5:7]
    if yyyymm[2:]!=match[2]+match[3]:raise ValueError('maturity_symbol_disagreement:'+symbol)
    return {'rq_symbol':symbol,'product':match[1].lower()+'.DCE','yyyymm':yyyymm,
            'epoch':symbol.lower()+'.DCE@'+yyyymm,'listed':item['listed_date'],
            'delisted':item['de_listed_date']}


def day_of(value):
    raw=str(int(value))
    if len(raw)!=14 or raw[-6:]!='000000':raise ValueError('unexpected_datetime:'+raw)
    day=raw[:4]+'-'+raw[4:6]+'-'+raw[6:8]
    date.fromisoformat(day)
    return day


def valid_price(row):
    op,hi,lo,cl=[float(row[f]) for f in FIELDS]
    return all(math.isfinite(x) and x>0 for x in (op,hi,lo,cl)) and lo<=min(op,cl)<=max(op,cl)<=hi


def equal(a,b):
    return math.isclose(float(a),float(b),abs_tol=1e-7,rel_tol=0)


def ratio(a,b):
    if float(b)==0:return 'both_zero' if float(a)==0 else 'rq_zero_official_positive'
    return str(round(float(a)/float(b),8))


def main():
    official=DCE/'official_fullmarket_daily.csv'
    source_stats={str(path.relative_to(LINE)):{'bytes':path.stat().st_size,'sha256':sha(path)}
                  for path in (official,RQ/'futures.h5',RQ/'instruments.pk',RQ/'trading_dates.npy')}
    before={str(path):path.stat().st_mtime_ns for path in (official,RQ/'futures.h5',RQ/'instruments.pk')}
    metadata,safety=safe_metadata(RQ/'instruments.pk')
    future=[x for x in metadata if x.get('type')=='Future']
    dce=[x for x in future if x.get('exchange')=='DCE']
    real={};duplicate_metadata=[]
    for item in dce:
        ident=identity(item)
        if ident is None:continue
        if ident['rq_symbol'] in real:duplicate_metadata.append(ident['rq_symbol'])
        real[ident['rq_symbol']]=ident
    epoch_to_rq={ident['epoch']:key for key,ident in real.items()}
    calendar=np.load(RQ/'trading_dates.npy',allow_pickle=False)
    if calendar.dtype.kind not in 'iu' or calendar.ndim!=1:raise ValueError('calendar_not_primitive_1d_int')
    caldays=[f'{int(x):08d}' for x in calendar]
    caldays=[x[:4]+'-'+x[4:6]+'-'+x[6:8] for x in caldays]
    calendarset=set(caldays)
    counters=defaultdict(Counter);volume_ratios=defaultdict(Counter);oi_ratios=defaultdict(Counter)
    differences=[];official_missing=[];rq_zero_official_trade=[]
    observed_rq_ohlc_bad=[];coverage=[];dataset_missing=[];yearly_rq=defaultdict(Counter)
    malformed_dates=[];duplicate_dates=[];outside_life=[]
    h5_max='';h5_min='9999-99-99';real_datasets=0
    with h5py.File(RQ/'futures.h5','r') as handle:
        cache_key=None;cache={}
        with official.open() as stream:
            for off in csv.DictReader(stream):
                year=off['date'][:4];counts=counters[year];counts['official_valid_traded_rows']+=1
                rq_key=epoch_to_rq.get(off['contract_epoch_id'])
                if rq_key is None or rq_key not in handle:
                    counts['rq_contract_absent']+=1
                    official_missing.append({'epoch':off['contract_epoch_id'],'date':off['date'],'reason':'rq_contract_absent'})
                    continue
                if rq_key!=cache_key:
                    array=handle[rq_key][:]
                    cache={day_of(r['datetime']):r for r in array};cache_key=rq_key
                row=cache.get(off['date'])
                if row is None:
                    counts['rq_day_absent']+=1
                    official_missing.append({'epoch':off['contract_epoch_id'],'date':off['date'],'reason':'rq_day_absent'})
                    continue
                counts['matched_raw_key']+=1
                if float(row['volume'])<=0:
                    counts['official_traded_rq_zero_volume']+=1
                    rq_zero_official_trade.append({'epoch':off['contract_epoch_id'],'date':off['date'],
                        'official_volume':float(off['volume']),'rq_volume':float(row['volume']),
                        'official_ohlc':{f:float(off[f]) for f in FIELDS},'rq_ohlc':{f:float(row[f]) for f in FIELDS}})
                    continue
                counts['both_traded_rows']+=1
                ohlc_equal=all(equal(off[f],row[f]) for f in FIELDS)
                counts['ohlc_equal' if ohlc_equal else 'ohlc_mismatch']+=1
                if not valid_price(row):counts['rq_invalid_ohlc_on_official_valid_day']+=1
                vr=ratio(off['volume'],row['volume']);oir=ratio(off['close_open_interest'],row['open_interest'])
                volume_ratios[year][vr]+=1;oi_ratios[year][oir]+=1
                counts['volume_native_equal']+=equal(off['volume'],row['volume'])
                counts['volume_official_half_equal']+=equal(float(off['volume'])/2,row['volume'])
                counts['close_oi_native_equal']+=equal(off['close_open_interest'],row['open_interest'])
                counts['close_oi_official_half_equal']+=equal(float(off['close_open_interest'])/2,row['open_interest'])
                differences.append({'epoch':off['contract_epoch_id'],'date':off['date'],'ohlc_equal':ohlc_equal,
                    'volume_ratio_official_over_rq':vr,'close_oi_ratio_official_over_rq':oir,
                    'official':{**{f:float(off[f]) for f in FIELDS},'volume':float(off['volume']),
                                'close_oi':float(off['close_open_interest'])},
                    'rq':{**{f:float(row[f]) for f in FIELDS},'volume':float(row['volume']),
                          'close_oi':float(row['open_interest'])}})
        for rq_key,ident in sorted(real.items()):
            active_start=max('2023-01-01',ident['listed']);active_end=min(END,ident['delisted'])
            intersects=active_start<=active_end
            if rq_key not in handle:
                dataset_missing.append({**ident,'overlaps_2023_2026_scope':intersects})
                if intersects:coverage.append({**ident,'status':'missing_dataset','expected_days':sum(active_start<=d<=active_end for d in caldays),'missing_days':[]})
                continue
            real_datasets+=1;array=handle[rq_key][:]
            required={'datetime',*FIELDS,'volume','open_interest','settlement'}
            if not required.issubset(set(array.dtype.names or ())):raise ValueError('dataset_schema:'+rq_key)
            seen=set();traded=0;valid_traded=0;zero=0;all_latest=None;traded_latest=None
            for raw in array:
                try:day=day_of(raw['datetime'])
                except ValueError as err:malformed_dates.append({'rq_symbol':rq_key,'error':str(err)});continue
                if day in seen:duplicate_dates.append({'rq_symbol':rq_key,'date':day})
                seen.add(day);h5_max=max(h5_max,day);h5_min=min(h5_min,day)
                if not ident['listed']<=day<=ident['delisted']:outside_life.append({'rq_symbol':rq_key,'date':day,'listed':ident['listed'],'delisted':ident['delisted']})
                if not '2023-01-01'<=day<=END:continue
                year=day[:4];out=yearly_rq[year];out['raw_rows']+=1
                all_latest=day if all_latest is None else max(day,all_latest)
                if float(raw['volume'])<=0:
                    zero+=1;out['zero_volume_rows_excluded']+=1
                    if all(equal(raw[f],raw['open']) for f in FIELDS) and float(raw['open'])>0:out['zero_volume_positive_flat_rows']+=1
                    if not valid_price(raw):out['zero_volume_invalid_ohlc_rows']+=1
                    continue
                traded+=1;out['traded_rows']+=1;traded_latest=day if traded_latest is None else max(day,traded_latest)
                finite=all(math.isfinite(float(raw[f])) for f in (*FIELDS,'volume','open_interest','settlement'))
                valid=finite and valid_price(raw) and float(raw['open_interest'])>=0
                if valid:valid_traded+=1;out['valid_traded_rows']+=1
                else:
                    out['invalid_traded_rows']+=1
                    observed_rq_ohlc_bad.append({'rq_symbol':rq_key,'epoch':ident['epoch'],'date':day,
                        **{f:float(raw[f]) for f in (*FIELDS,'volume','open_interest','settlement')},'all_numeric_finite':finite})
            if intersects:
                expected={d for d in caldays if active_start<=d<=active_end}
                missing=sorted(expected-seen);extra=sorted(d for d in seen if active_start<=d<=active_end and d not in calendarset)
                coverage.append({**ident,'status':'present','expected_days':len(expected),'present_expected_days':len(expected&seen),
                    'missing_days':missing,'noncalendar_days':extra,'scope_raw_rows':sum(active_start<=d<=active_end for d in seen),
                    'scope_traded_rows':traded,'scope_valid_traded_rows':valid_traded,'scope_zero_volume_rows_excluded':zero,
                    'last_raw_day_in_scope':all_latest,'last_traded_day_in_scope':traded_latest})
    after={str(path):path.stat().st_mtime_ns for path in (official,RQ/'futures.h5',RQ/'instruments.pk')}
    overlap_totals=Counter()
    for c in counters.values():overlap_totals.update(c)
    modes={year:{'volume':v.most_common(1)[0][0],
                'close_oi':Counter({k:n for k,n in oi_ratios[year].items() if k!='both_zero'}).most_common(1)[0][0]}
           for year,v in volume_ratios.items()}
    differences=[r for r in differences if not r['ohlc_equal'] or
        r['volume_ratio_official_over_rq']!=modes[r['date'][:4]]['volume'] or
        r['close_oi_ratio_official_over_rq'] not in (modes[r['date'][:4]]['close_oi'],'both_zero')]
    nonmodal={year:{'volume':sum(n for k,n in volume_ratios[year].items() if k!=modes[year]['volume']),
                    'close_oi':sum(n for k,n in oi_ratios[year].items() if k not in (modes[year]['close_oi'],'both_zero'))}
              for year in volume_ratios}
    coverage_by_year={}
    for year in ('2023','2024','2025','2026'):
        yr_end=min(year+'-12-31',END);yr_start=year+'-01-01'
        expected_contracts=[r for r in real.values() if max(yr_start,r['listed'])<=min(yr_end,r['delisted'])]
        missing_contracts=[r['rq_symbol'] for r in expected_contracts if any(d['rq_symbol']==r['rq_symbol'] for d in dataset_missing)]
        missing_days=[{'rq_symbol':r['rq_symbol'],'days':[d for d in r.get('missing_days',[]) if yr_start<=d<=yr_end]} for r in coverage]
        missing_days=[r for r in missing_days if r['days']]
        coverage_by_year[year]={'expected_real_contracts_from_bundled_metadata':len(expected_contracts),'missing_datasets':missing_contracts,
                              'missing_calendar_day_count':sum(len(r['days']) for r in missing_days),'missing_day_contracts':len(missing_days),
                              'observed':dict(yearly_rq[year])}
    summary={'generated_at':stamp(),'source_files':source_stats,'metadata_safety':safety,'source_mtimes_unchanged':before==after,
        'future_metadata_count':len(future),'dce_metadata_count':len(dce),'dce_real_metadata_count':len(real),
        'dce_excluded_continuous_or_synthetic_count':len(dce)-len(real),'dce_real_datasets':real_datasets,
        'dce_missing_metadata_datasets_count':len(dataset_missing),'dce_duplicate_metadata_ids':duplicate_metadata,
        'dce_h5_real_min_date':h5_min,'dce_h5_real_max_date':h5_max,
        'comparison_contract':'trading day + full YYYYMM from maturity metadata; both sources volume>0; closing OI compared at same day; tolerance abs1e-7',
        'overlap_totals':dict(overlap_totals),'overlap_by_year':{y:dict(v) for y,v in sorted(counters.items())},
        'volume_ratio_official_over_rq_by_year':{y:dict(v) for y,v in sorted(volume_ratios.items())},
        'close_oi_ratio_official_over_rq_by_year':{y:dict(v) for y,v in sorted(oi_ratios.items())},
        'empirical_ratio_modes_by_year':dict(sorted(modes.items())),
        'nonmodal_ratio_row_counts_by_year':dict(sorted(nonmodal.items())),
        'price_or_nonmodal_unit_difference_rows':len(differences),
        'post_2023_coverage_by_year':coverage_by_year,
        'post_2023_missing_dataset_count':sum(x['overlaps_2023_2026_scope'] for x in dataset_missing),
        'post_2023_missing_day_count':sum(len(r.get('missing_days',[])) for r in coverage),
        'post_2023_invalid_traded_rows':len(observed_rq_ohlc_bad),
        'post_2023_invalid_traded_on_delisting_day':sum(r['date']==real[r['rq_symbol']]['delisted'] for r in observed_rq_ohlc_bad),
        'post_2023_invalid_traded_open_high_low_equal':sum(equal(r['open'],r['high']) and equal(r['open'],r['low']) for r in observed_rq_ohlc_bad),
        'post_2023_invalid_traded_by_product':dict(Counter(r['rq_symbol'].rstrip('0123456789') for r in observed_rq_ohlc_bad)),
        'malformed_datetime_count':len(malformed_dates),'duplicate_date_count':len(duplicate_dates),'outside_metadata_life_count':len(outside_life),
        'network_calls':0,'database_write_calls':0,'backtest_calls':0,'training_calls':0,
        'limitations':['Coverage is relative to supplied metadata and calendar, not independent proof the metadata enumerates every listed DCE contract.',
            'All vendor zero-volume rows are excluded from genuine traded bars, even when OHLC is positive and flat.',
            'Archive fields remain native; this review does not mutate either source or approve silent unit conversion.',
            'RQ monthly bundle ends 2026-09-30 and cannot satisfy the 2026-10-16 target alone.']}
    save('',summary)
    save('_differences',{'both_traded_price_or_empirically_nonmodal_unit_rows':differences,'official_missing_in_rq':official_missing,
         'official_traded_rq_zero_volume':rq_zero_official_trade,'post_2023_invalid_traded_rows':observed_rq_ohlc_bad})
    save('_coverage',{'dataset_missing':dataset_missing,'coverage_by_contract':coverage,'malformed_dates':malformed_dates,
         'duplicate_dates':duplicate_dates,'outside_metadata_life':outside_life})
    verdict={'generated_at':stamp(),'scope':'Independent DCE official-vs-RQ data review only',
        'P0':0,'P1':3,'unqualified_merge_approved':False,
        'findings':[
            {'priority':'P1','title':'Rows requiring quarantine before genuine-bar use',
             'evidence':{'cross_source_price_or_nonmodal_unit_rows':len(differences),
                 'cross_source_price_mismatch':overlap_totals['ohlc_mismatch'],
                 'official_traded_rq_zero_volume':overlap_totals['official_traded_rq_zero_volume'],
                 'post_2023_invalid_traded_ohlc':len(observed_rq_ohlc_bad),
                 'post_2023_vendor_zero_volume_rows':sum(c['zero_volume_rows_excluded'] for c in yearly_rq.values())},
             'required':'Keep zero-volume rows out of genuine bars; quarantine incompatible OHLC and source conflicts with provenance. Do not expand high/low or forward-fill prices to fabricate valid bars.'},
            {'priority':'P1','title':'Volume and closing OI have a source/time unit seam',
             'evidence':'Official/RQ yearly modal ratio is 1 through 2019 and 2 in 2020-2022, with explicit nonmodal rows.',
             'required':'Declare source and period unit policy, preserve raw units, and quarantine nonmodal differences; never apply a single full-history divisor or mix closing OI with TQ opening OI.'},
            {'priority':'P1','title':'Monthly RQ bundle does not reach the requested 2026-10-16 cutoff',
             'evidence':{'max_actual_dce_real_date':h5_max,'requested_target':'2026-10-16'},
             'required':'Verify a separate actual latest-date source through 2026-10-16; metadata and raw row counts alone do not close this gap.'}],
        'positive_evidence':{'all_official_valid_traded_keys_found_in_rq':overlap_totals['matched_raw_key']==overlap_totals['official_valid_traded_rows'],
            'post_2023_missing_datasets':summary['post_2023_missing_dataset_count'],
            'post_2023_missing_expected_calendar_days':summary['post_2023_missing_day_count'],
            'source_files_unchanged':before==after,'metadata_primitive_safe_read':True},
        'not_a_backtest':True,'overfitting':'No new fit or selection was performed; continue only data validation and declared source reconciliation.'}
    save('_verdict',verdict)
    print(json.dumps({k:v for k,v in summary.items() if k not in ('source_files','overlap_by_year','volume_ratio_official_over_rq_by_year','close_oi_ratio_official_over_rq_by_year')},ensure_ascii=False))


if __name__=='__main__':main()
