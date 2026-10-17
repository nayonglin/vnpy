"""Independent raw H5/CZCE audit. Reads root inputs, never root inventory results.

No network, DB writes, imputation, or pickle globals. Zero-volume vendor prices
are counted separately and never asserted to be observed exchange trade prices.
"""
from collections import Counter,defaultdict
import csv
from datetime import datetime
import hashlib
import io
import json
from pathlib import Path
import pickle
import pickletools
import re
from zoneinfo import ZoneInfo

import h5py
import numpy as np

LINE=Path(__file__).resolve().parents[1]
BASE=LINE/'outputs/stage265_deep_daily'
OUT=BASE/'czce'
RQ=BASE/'rqalpha'
EXCHANGES={'SHFE','DCE','CZCE','CFFEX','INE','GFEX'}
FIELDS=('open','high','low','close','volume','open_interest')
LOW,HIGH=20100101,20261016

class NoGlobals(pickle.Unpickler):
    def find_class(self,module,name):
        raise pickle.UnpicklingError('all_globals_denied')
    def persistent_load(self,pid):
        raise pickle.UnpicklingError('persistent_ids_denied')


def metadata():
    body=(RQ/'instruments.pk').read_bytes()
    dangerous={'GLOBAL','STACK_GLOBAL','REDUCE','NEWOBJ','NEWOBJ_EX','OBJ','INST','EXT1','EXT2','EXT4','PERSID','BINPERSID'}
    opcounts=Counter()
    for op,arg,pos in pickletools.genops(body):
        opcounts[op.name]+=1
        if op.name in dangerous:
            raise RuntimeError('unsafe_pickle_opcode:'+op.name)
    value=NoGlobals(io.BytesIO(body)).load()
    if not isinstance(value,list) or any(not isinstance(x,dict) for x in value):
        raise RuntimeError('unexpected_metadata_shape')
    return [x for x in value if x.get('type')=='Future'],dict(opcounts)


def dayint(value):
    if not value or value=='0000-00-00':return None
    return int(value[:10].replace('-',''))


def classify(info):
    name=info['order_book_id']
    code=re.fullmatch(r'([A-Z]+)(\d{4})(F?)',name)
    if not code:return None,'not_four_digit_real_delivery_code'
    product,digits,monthly=code.groups()
    if monthly and (product not in {'L','PP','V'} or info.get('exchange')!='DCE'):
        return None,'unsupported_monthly_average_family'
    if not 1<=int(digits[-2:])<=12:return None,'non_delivery_month_code'
    if info.get('exchange') not in EXCHANGES:return None,'unknown_exchange'
    expected_underlying=product+'_F' if monthly else product
    if expected_underlying!=info.get('underlying_symbol'):return None,'product_metadata_code_mismatch'
    maturity=dayint(info.get('maturity_date'))
    if maturity is None:return None,'missing_real_maturity_metadata'
    year=maturity//10000
    possible=[y for y in range(year-1,year+2) if y%100==int(digits[:2])]
    if len(possible)!=1:return None,'delivery_year_not_unique'
    delivery=f'{possible[0]:04d}{digits[-2:]}'
    if info['exchange']=='CZCE' and str(maturity)[:6]!=delivery:
        return None,'czce_maturity_delivery_month_mismatch'
    return delivery,None


def writecsv(name,rows,fields=None):
    if fields is None:fields=list(rows[0]) if rows else []
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields,extrasaction='ignore')
        writer.writeheader();writer.writerows(rows)


def summarize_arr(arr):
    days=arr['datetime']//1000000
    mask=(days>=LOW)&(days<=HIGH)
    a=arr[mask]
    p=np.column_stack([a[f] for f in FIELDS[:4]])
    finite=np.isfinite(p).all(axis=1)&np.isfinite(a['volume'])&np.isfinite(a['open_interest'])
    positive=(p>0).all(axis=1)
    geometry=(a['low']<=np.minimum(a['open'],a['close']))&(np.maximum(a['open'],a['close'])<=a['high'])&(a['low']<=a['high'])
    zero=a['volume']==0;traded=a['volume']>0
    return {'rows_in_scope':int(len(a)),'first_date_in_scope':int(days[mask][0]) if len(a) else None,'last_date_in_scope':int(days[mask][-1]) if len(a) else None,
        'finite_six_fields':int(finite.sum()),'positive_ohlc':int(positive.sum()),'valid_positive_ohlc_geometry':int((positive&geometry).sum()),
        'volume_positive_rows':int(traded.sum()),'zero_volume_rows':int(zero.sum()),'zero_volume_positive_ohlc':int((zero&positive).sum()),
        'zero_volume_invalid_ohlc_geometry':int((zero&~geometry).sum()),'positive_volume_invalid_ohlc_geometry':int((traded&~geometry).sum()),
        'nonfinite_six_fields':int((~finite).sum()),'negative_volume_or_oi':int(((a['volume']<0)|(a['open_interest']<0)).sum()),
        'duplicate_dates':int(len(days)-len(set(days.tolist()))),'non_increasing_datetimes':int((np.diff(arr['datetime'])<=0).sum()),
        'raw_rows_after_user_cutoff':int((days>HIGH).sum())}


def compare_source(h5,rows,label):
    groups=defaultdict(list)
    for r in rows:
        delivery=r.get('contract_yyyymm') or r['contract_epoch_id'].split('@')[1]
        product=r['product'].split('.')[0].upper()
        groups[product+delivery[2:]].append(r)
    counts=Counter();byproduct=defaultdict(Counter);diff=[]
    for name,source_rows in sorted(groups.items()):
        if name not in h5:
            counts['missing_h5_dataset_source_rows']+=len(source_rows);continue
        arr=h5[name][:];idx={int(x['datetime']//1000000):x for x in arr}
        for r in source_rows:
            c=byproduct[r['product']];c['source_rows']+=1;counts['source_rows']+=1
            d=int(r['date'].replace('-',''))
            if d not in idx:c['missing_h5_date']+=1;counts['missing_h5_date']+=1;continue
            a=idx[d];c['overlap_rows']+=1;counts['overlap_rows']+=1
            different_fields=[]
            for field in FIELDS:
                equal=bool(np.isclose(float(r[field]),float(a[field]),rtol=0,atol=1e-7))
                key=('equal_' if equal else 'different_')+field;c[key]+=1;counts[key]+=1
                if not equal:different_fields.append(field)
            p_equal=all(np.isclose(float(r[f]),float(a[f]),rtol=0,atol=1e-7) for f in FIELDS[:4])
            c['equal_ohlc']+=int(p_equal);counts['equal_ohlc']+=int(p_equal)
            c['volume_source_equals_2x_rq']+=int(np.isclose(float(r['volume']),2*float(a['volume']),rtol=0,atol=1e-7))
            c['oi_source_equals_2x_rq']+=int(np.isclose(float(r['open_interest']),2*float(a['open_interest']),rtol=0,atol=1e-7))
            if different_fields:
                diff.append({'different_fields':','.join(different_fields),'source':label,'rq_key':name,'product':r['product'],'date':r['date'],'source_volume':r['volume'],'rq_volume':float(a['volume']),
                    **{'source_'+f:r[f] for f in FIELDS},**{'rq_'+f:float(a[f]) for f in FIELDS}})
    writecsv('rqalpha_'+label+'_field_differences.csv',diff,['different_fields','source','rq_key','product','date',*['source_'+f for f in FIELDS],*['rq_'+f for f in FIELDS]])
    return {'totals':dict(counts),'by_product':{p:dict(c) for p,c in sorted(byproduct.items())},'ohlc_difference_rows':counts['overlap_rows']-counts['equal_ohlc'],'any_field_difference_rows':len(diff)}


def sm77(h5):
    source=LINE/'outputs/stage264_pre_main_daily/manifest_main_dates.csv'
    gaps=[r for r in csv.DictReader(source.open(encoding='utf-8-sig',newline='')) if r['product']=='SM.CZCE' and r['coverage_ok'].lower()!='true']
    wanted={r['date'] for r in gaps};wide={}
    suffix={'open':'open','high':'high','low':'low','close':'cl','volume':'vol','open_interest':'oi'}
    for field,end in suffix.items():
        wide[field]={r['']:r for r in csv.DictReader((BASE/f'opensource/work_SM_data_{end}.raw').open(encoding='utf-8-sig',newline='')) if r[''] in wanted}
    result=[];counts=Counter()
    for r in gaps:
        name='SM'+r['contract_yyyymm'][2:];day=int(r['date'].replace('-',''))
        arr=h5[name][:];exact=arr[arr['datetime']//1000000==day]
        counts['original_gap_days']+=1
        if len(exact)!=1:counts['not_exactly_one_rq_row']+=1;continue
        a=exact[0];item={**r,'rq_key':name,**{'rq_'+f:float(a[f]) for f in (*FIELDS,'settlement','prev_settlement')}}
        aliases=[name+'.CZC','SM'+r['contract_yyyymm'][3:]+'.CZC']
        for field in FIELDS:
            raw=wide[field].get(r['date'],{})
            observed=[float(raw[c]) for c in aliases if raw.get(c) is not None and raw.get(c)!='']
            if len(set(observed))>1:raise RuntimeError('sm_alias_conflict')
            item['work_'+field]=observed[0] if observed else None
        item['work_four_prices_blank']=all(item['work_'+f] is None for f in FIELDS[:4])
        item['rq_zero_volume_flat_positive_prices']=bool(a['volume']==0 and a['open']==a['high']==a['low']==a['close'] and a['open']>0)
        counts['rq_rows_present']+=1
        counts['work_four_prices_blank']+=int(item['work_four_prices_blank'])
        counts['work_volume_zero']+=int(item['work_volume']==0)
        counts['rq_zero_volume_flat_positive_prices']+=int(item['rq_zero_volume_flat_positive_prices'])
        result.append(item)
    writecsv('rqalpha_SM77_raw_rows.csv',result)
    return dict(counts)


def main():
    future,opcounts=metadata()
    ids=[x['order_book_id'] for x in future]
    if len(ids)!=len(set(ids)):raise RuntimeError('duplicate_metadata_id')
    meta={x['order_book_id']:x for x in future}
    receipt=json.loads((RQ/'bundle_download_status.json').read_text())
    source_hash={}
    for name in ['futures.h5','instruments.pk','trading_dates.npy','future_info.json']:
        path=RQ/name
        sha=hashlib.sha256(path.read_bytes()).hexdigest();source_hash[name]=sha
        expected=next(x['sha256'] for x in receipt['saved'] if x['file']==name)
        if sha!=expected:raise RuntimeError('raw_hash_not_receipt:'+name)
    calendar=np.load(RQ/'trading_dates.npy',allow_pickle=False)
    if calendar.dtype.kind not in 'iu':raise RuntimeError('noninteger_calendar')
    inventory=[];excluded=[];quality_rows=[];exchange_counts=defaultdict(Counter);product_rows=defaultdict(list)
    manifests=json.loads((LINE/'outputs/stage264_pre_main_daily/manifest_contracts.json').read_text())
    target_reports=[]
    with h5py.File(RQ/'futures.h5','r') as h:
        no_meta=[]
        for name in h:
            if name not in meta:no_meta.append(name);continue
            info=meta[name];delivery,reason=classify(info)
            if reason:excluded.append({'rq_key':name,'reason':reason});continue
            arr=h[name][:];counts=summarize_arr(arr);days=arr['datetime']//1000000
            listed=dayint(info.get('listed_date'));delisted=dayint(info.get('de_listed_date'))
            counts.update(rows_before_candidate_listing=int((days<listed).sum()) if listed else None,
                rows_after_candidate_delisting=int((days>delisted).sum()) if delisted else None)
            record={'rq_key':name,'product':info['underlying_symbol'],'exchange':info['exchange'],'delivery_yyyymm':delivery,'contract_family':'monthly_average_futures' if name.endswith('F') else 'standard_futures',
                'candidate_listed_date':info.get('listed_date'),'candidate_delisted_date':info.get('de_listed_date'),**counts}
            positive_geometry_bad=(arr['volume']>0)&((arr['low']>np.minimum(arr['open'],arr['close']))|(np.maximum(arr['open'],arr['close'])>arr['high']))
            before_listing=(days<listed) if listed else np.zeros(len(arr),dtype=bool)
            for raw in arr[((days>=LOW)&(days<=HIGH))&(positive_geometry_bad|before_listing)]:
                d=int(raw['datetime']//1000000)
                reasons=[]
                if listed and d<listed:reasons.append('before_candidate_listing')
                if raw['volume']>0 and not raw['low']<=min(raw['open'],raw['close'])<=max(raw['open'],raw['close'])<=raw['high']:reasons.append('positive_volume_invalid_ohlc_geometry')
                quality_rows.append({'rq_key':name,'exchange':info['exchange'],'date':d,'reason':','.join(reasons),'candidate_listed_date':info.get('listed_date'),**{f:float(raw[f]) for f in FIELDS}})
            inventory.append(record);product_rows[info['exchange']+'.'+info['underlying_symbol']].append(record)
            c=exchange_counts[info['exchange']];c['real_contract_datasets']+=1
            for k,v in counts.items():
                if v is not None and k not in ('first_date_in_scope','last_date_in_scope'):c[k]+=v
        for target in manifests:
            name=target['product'].split('.')[0].upper()+target['contract_yyyymm'][2:]
            info=meta.get(name);present=name in h
            record={'contract_epoch_id':target['contract_epoch_id'],'rq_key':name,'product':target['product'],'dataset_present':present,
                'metadata_present':bool(info),'metadata_exchange_matches':bool(info and info.get('exchange')==target['exchange']),
                'raw_rows':0,'positive_volume_valid_ohlc_rows':0,'rows_through_original_first_main':0,'positive_volume_valid_rows_through_original_first_main':0,
                'first_main_date':target['first_main_date']}
            if present:
                arr=h[name][:];days=arr['datetime']//1000000
                cut=int(target['first_main_date'].replace('-',''));bounded=(days>=LOW)&(days<=HIGH)
                valid=(arr['volume']>0)&(arr['open']>0)&(arr['close']>0)&(arr['low']>0)&(arr['high']>0)&(arr['low']<=np.minimum(arr['open'],arr['close']))&(np.maximum(arr['open'],arr['close'])<=arr['high'])
                record.update(raw_rows=int(bounded.sum()),positive_volume_valid_ohlc_rows=int((bounded&valid).sum()),
                    rows_through_original_first_main=int((bounded&(days<=cut)).sum()),
                    positive_volume_valid_rows_through_original_first_main=int((bounded&valid&(days<=cut)).sum()),
                    first_raw_day=int(days.min()) if len(days) else None,last_raw_day=int(days.max()) if len(days) else None,
                    candidate_listed_date=info.get('listed_date') if info else None,candidate_delisted_date=info.get('de_listed_date') if info else None)
            target_reports.append(record)
        work=[]
        for path in sorted(OUT.glob('work_*_fullmarket_bars.csv')):
            work.extend(csv.DictReader(path.open(encoding='utf-8-sig',newline='')))
        workcmp=compare_source(h,work,'work')
        official=list(csv.DictReader((LINE/'outputs/stage264_pre_main_daily/shfe_official/normalized_bars.csv').open(encoding='utf-8-sig',newline='')))
        officialcmp=compare_source(h,official,'shfe_official')
        sm77_report=sm77(h)
        h5_count=len(h)
    writecsv('rqalpha_independent_contract_inventory.csv',inventory)
    writecsv('rqalpha_independent_row_issues.csv',quality_rows)
    writecsv('rqalpha_independent_old231_coverage.csv',target_reports)
    writecsv('rqalpha_independent_excluded_h5_keys.csv',excluded)
    products={}
    for p,rows in sorted(product_rows.items()):
        in_scope=[r for r in rows if r['rows_in_scope']]
        products[p]={'datasets':len(rows),'datasets_with_rows_in_scope':len(in_scope),'rows_in_scope':sum(r['rows_in_scope'] for r in rows),
            'first_date_in_scope':min((r['first_date_in_scope'] for r in in_scope),default=None),'last_date_in_scope':max((r['last_date_in_scope'] for r in in_scope),default=None)}
    summary={'generated_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),'status':'independent_raw_vendor_audit_no_database_or_training_acceptance',
        'inputs_sha256':source_hash,'pickle_opcode_counts':opcounts,'pickle_globals_or_reducers':0,'unpickler_find_class':'all_globals_denied',
        'quality_issue_rows':len(quality_rows),'quality_issue_reasons':dict(Counter(r['reason'] for r in quality_rows)),
        'monthly_average_datasets':sum(r['contract_family']=='monthly_average_futures' for r in inventory),
        'future_metadata_rows':len(future),'h5_datasets':h5_count,'real_delivery_datasets':len(inventory),'excluded_continuous_or_non_delivery_datasets':len(excluded),
        'h5_keys_without_future_metadata':no_meta,'exchange_counts':{p:dict(c) for p,c in sorted(exchange_counts.items())},'by_product':products,
        'old231_targets':{'targets':len(target_reports),'datasets_present':sum(r['dataset_present'] for r in target_reports),
            'metadata_exchange_matches':sum(r['metadata_exchange_matches'] for r in target_reports),
            'AM120_nominal_raw_rows_through_original_first_main':sum(r['rows_through_original_first_main']>=120 for r in target_reports),
            'AM120_positive_volume_valid_rows_through_original_first_main':sum(r['positive_volume_valid_rows_through_original_first_main']>=120 for r in target_reports)},
        'work_comparison':workcmp,'shfe_official_comparison':officialcmp,'SM77_raw_comparison':sm77_report,
        'calendar_np_load_allow_pickle':False,'calendar_first':int(calendar[0]),'calendar_last':int(calendar[-1]),
        'limits':['Positive flat OHLC on V=0 can encode a vendor fill for exchange blank no-trade prices. All SM77 existing gaps have V0 and flat positive OHLC in RQ, and cannot be declared repaired observed trading days.',
            'A raw calendar row or metadata listing date is not exchange lifecycle certification or a qualified training sample. No change to AM120 or source acceptance contract is made.',
            'Monthly bundle ends before the user date cutoff; recent daily tails require separate frozen/source-clock validation. Trading calendar through 2027 is not future price coverage.',
            'Cross-source matches support only the compared products/dates. V/OI are not divided or overwritten, and current metadata margin is not historical daily margin.'],
        'database_writes':0,'training_runs':0,'backtest_runs':0,'network_requests':0}
    (OUT/'rqalpha_independent_audit.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('by_product','pickle_opcode_counts','work_comparison','shfe_official_comparison','limits')},ensure_ascii=False,indent=2))
    print('work',json.dumps(workcmp['totals'],ensure_ascii=False));print('official',json.dumps(officialcmp['totals'],ensure_ascii=False))


if __name__=='__main__':main()
