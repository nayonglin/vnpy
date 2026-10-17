"""Read-only unit calibration of the pinned Stage265 daily files; no network/orders."""
from __future__ import annotations
from collections import Counter, defaultdict
from datetime import datetime
from functools import lru_cache
import csv, gzip, hashlib, json, math, re
from pathlib import Path
from zoneinfo import ZoneInfo
import h5py
import numpy as np
from independent_review_stage265_dce_rq import safe_metadata, sha

LINE=Path(__file__).resolve().parents[1]
BASE=LINE/'outputs/stage265_deep_daily'
OUT=LINE/'outputs/stage266_clean_daily'
OLD=LINE.parents[2]/'examples/portfolio_backtesting/downloaded_futures/tqsdk_daily_2010_2026_04'
COMMODITY={'SHFE','INE','DCE','CZCE','GFEX'}
FIELDS=('volume','close_oi')

def close(a,b): return math.isclose(float(a),float(b),rel_tol=0,abs_tol=1e-7)
def ratio(a,b):
    if not b:return 'both_zero' if not a else 'reference_zero'
    return str(round(a/b,8))
def iso(v):
    s=str(int(v)); return f'{s[:4]}-{s[4:6]}-{s[6:8]}'
def rq_factor(exchange,day): return 0.5 if exchange in COMMODITY and day<'2020-01-01' else 1.0

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    meta,safety=safe_metadata(BASE/'rqalpha/instruments.pk')
    real={}; bycode=defaultdict(list); byepoch={}
    for m in meta:
        s=m.get('order_book_id',''); match=re.fullmatch(r'([A-Z]+)(\d{2})(\d{2})(F?)',s)
        if m.get('type')!='Future' or not match or not 1<=int(match[3])<=12:continue
        # Symbol carries nominal delivery month; INE and F maturity can precede it.
        info={**m,'product':match[1].lower(),'yyyymm':'20'+match[2]+match[3],'is_f':bool(match[4])}
        real[s]=info;bycode[(m['exchange'],str(m['trading_code']).lower())].append(s)
        byepoch[(m['exchange'],info['product'],info['yyyymm'],info['is_f'])]=s
    parity=defaultdict(Counter);official=defaultdict(Counter);tq=defaultdict(Counter)
    offratios=defaultdict(lambda:defaultdict(Counter));tqratios=defaultdict(lambda:defaultdict(Counter))
    exceptions=[];tq_exceptions=[];unresolved=Counter();source_hashes=[];tq_files=[]
    cross_boundary=[];dataset_parity=[]
    with h5py.File(BASE/'rqalpha/futures.h5','r') as h:
        @lru_cache(maxsize=256)
        def bars(s):
            if s not in h:return {}
            return {iso(r['datetime']):r for r in h[s][:]}
        for s,m in sorted(real.items()):
            if s not in h:continue
            a=h[s][:];days=a['datetime']//10000000000
            ds={};
            for year in range(2010,2027):
                z=a[(days==year)&(a['volume']>0)]
                if not len(z):continue
                count=parity[(m['exchange'],str(year))]; count['positive_volume_rows']+=len(z)
                d=Counter(positive_volume_rows=len(z))
                for field in ('volume','open_interest'):
                    x=z[field].astype(float);finite=np.isfinite(x);integer=finite&(x==np.floor(x))
                    vals={'nonfinite':int((~finite).sum()),'noninteger':int((finite&~integer).sum()),'odd':int((integer&(x%2!=0)).sum())}
                    for name,value in vals.items():count[field+'_'+name]+=value;d[field+'_'+name]=value
                ds[str(year)]=dict(d)
            pre=[r for r in a if 20100101000000<=int(r['datetime'])<20200101000000 and float(r['volume'])>0]
            post=[r for r in a if 20200101000000<=int(r['datetime'])<=20261016000000 and float(r['volume'])>0]
            if pre and post and m['exchange'] in COMMODITY:
                cross_boundary.append({'rq_symbol':s,'exchange':m['exchange'],'last_pre2020_date':iso(pre[-1]['datetime']),
                    'last_pre2020_volume':float(pre[-1]['volume']),'last_pre2020_close_oi':float(pre[-1]['open_interest']),
                    'first_post2020_date':iso(post[0]['datetime']),'first_post2020_volume':float(post[0]['volume']),
                    'first_post2020_close_oi':float(post[0]['open_interest'])})
            dataset_parity.append({'rq_symbol':s,'exchange':m['exchange'],'years':ds})
        print('parity_done',len(dataset_parity),flush=True)

        def compare(ref,s,source,factor,unit_kind):
            day=ref['date'];exchange=ref['exchange']
            if not '2010-01-01'<=day<='2026-10-16':return
            group=(exchange,day[:4],unit_kind);out=official[group];out['reference_rows']+=1
            if s is None:out['contract_unresolved']+=1;return
            r=bars(s).get(day)
            if r is None:out['rq_row_missing']+=1;return
            if float(r['volume'])<=0:out['rq_v0_excluded']+=1;return
            out['both_positive_volume']+=1
            out['ohlc_equal']+=all(close(ref[f],r[f]) for f in ('open','high','low','close'))
            details={};any_mismatch=False
            for field,rqfield in [('volume','volume'),('close_oi','open_interest')]:
                rv=float(r[rqfield]);ov=float(ref[field]);ra=ratio(ov,rv);offratios[group][field][ra]+=1
                if factor is None:continue
                expected=ov*factor;actual=rv*rq_factor(exchange,day)
                ok=close(expected,actual);out[field+'_canonical_equal' if ok else field+'_canonical_mismatch']+=1
                if not ok:any_mismatch=True;details[field]={'reference_native':ov,'rq_native':rv,'reference_to_single_factor':factor,'rq_to_single_factor':rq_factor(exchange,day),'reference_over_rq':ra}
            if factor is None:
                out['unknown_reference_unit_rows']+=1
            elif any_mismatch:
                exceptions.append({'exchange':exchange,'rq_symbol':s,'date':day,'reference_source':source,'reference_unit':unit_kind,'field_mismatches':details,'action':'quarantine_unit_conflict_preserve_both_native_values'})

        dcepath=BASE/'dce/official_fullmarket_daily.csv'
        source_hashes.append({'path':str(dcepath.relative_to(LINE)),'sha256':sha(dcepath)})
        with dcepath.open() as f:
            for row in csv.DictReader(f):
                s=byepoch.get(('DCE',row['product'].split('.')[0],row['contract_yyyymm'],False))
                ref={**row,'exchange':'DCE','close_oi':row['close_open_interest']}
                compare(ref,s,row['source_key'],0.5,'dce_annual_archive_empirical_double')
        print('dce_done',len(exceptions),flush=True)
        manifestpath=BASE/'other_exchanges/normalized/official_normalization_manifest.json'
        manifest=json.loads(manifestpath.read_text());source_hashes.append({'path':str(manifestpath.relative_to(LINE)),'sha256':sha(manifestpath)})
        for source in manifest['sources']:
            path=Path(source['normalized_path'])
            source_hashes.append({'path':str(path.relative_to(LINE)),'sha256':source['normalized_sha256']})
            with gzip.open(path,'rt') as f:
                for row in csv.DictReader(f):
                    kind=row['unit_regime'];factor=0.5 if kind=='official_two_sided_volume_and_close_oi' else 1.0 if 'single_sided' in kind else None
                    s=byepoch.get((row['exchange'],row['product'].lower().split('.')[0],row['contract_yyyymm'],False))
                    ref={**row,'close_oi':row['open_interest']}
                    compare(ref,s,row['source_id'],factor,kind)
        print('official_done',len(exceptions),flush=True)
        for exchange in sorted(COMMODITY|{'CFFEX'}):
            for path in sorted((OLD/exchange).glob('*.csv')):
                file_rows=0
                with path.open(encoding='utf-8-sig') as f:
                    for row in csv.DictReader(f):
                        day=row.get('trade_date','')[:10]
                        if not '2010-01-01'<=day<='2026-10-16':continue
                        v=float(row['volume']);
                        if v<=0:continue
                        file_rows+=1;group=(exchange,day[:4]);out=tq[group];out['tq_positive_rows']+=1
                        candidates=bycode.get((exchange,path.stem.lower()),[])
                        active=[s for s in candidates if real[s]['listed_date']<=day<=real[s]['de_listed_date']]
                        if len(active)!=1:
                            if len(candidates)==1:active=candidates
                            else:out['contract_unresolved']+=1;unresolved[(exchange,path.stem)]+=1;continue
                        s=active[0];r=bars(s).get(day)
                        if r is None:out['rq_row_missing']+=1;continue
                        if float(r['volume'])<=0:out['rq_v0_excluded']+=1;continue
                        out['both_positive_volume']+=1
                        out['ohlc_equal']+=all(close(row[f],r[f]) for f in ('open','high','low','close'))
                        for field,rqfield,tqfield in [('volume','volume','volume'),('close_oi','open_interest','close_oi')]:
                            ra=ratio(float(r[rqfield]),float(row[tqfield]));tqratios[group][field][ra]+=1
                        mismatch={}
                        for field,rqfield,tqfield in [('volume','volume','volume'),('close_oi','open_interest','close_oi')]:
                            rv=float(r[rqfield]);tv=float(row[tqfield]);factor=rq_factor(exchange,day)
                            if not close(rv*factor,tv):
                                mismatch[field]={'rq_native':rv,'tq_native':tv,'rq_to_single_factor':factor,'tq_to_single_factor':1.0}
                        if mismatch:
                            tq_exceptions.append({'exchange':exchange,'rq_symbol':s,'date':day,'reference_source':str(path.relative_to(LINE.parents[2])),
                                'field_mismatches':mismatch,'action':'quarantine_cross_source_conflict_preserve_native'})
                        out['rq_close_oi_equal_tq_open_oi']+=close(r['open_interest'],row['open_oi'])
                        out['rq_close_oi_equal_tq_close_oi']+=close(r['open_interest'],row['close_oi'])
                tq_files.append({'path':str(path.relative_to(LINE.parents[2])),'sha256':sha(path),'positive_rows_in_scope':file_rows})
        print('tq_done',len(tq_files),flush=True)
    def serial_counts(d):return {'|'.join(key):dict(value) for key,value in sorted(d.items())}
    def serial_ratios(d):return {'|'.join(key):{field:dict(count.most_common()) for field,count in value.items()} for key,value in sorted(d.items())}
    evidence={'generated_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),'scope':'2010-01-01..2026-10-16 observed files only; RQ ends2026-09-30',
        'script_sha256':sha(Path(__file__)),'metadata_safety':safety,'rq_h5_sha256':sha(BASE/'rqalpha/futures.h5'),'rq_metadata_sha256':sha(BASE/'rqalpha/instruments.pk'),
        'h5_parity_by_exchange_year':serial_counts(parity),'official_overlap':serial_counts(official),'official_native_over_rq_ratios':serial_ratios(offratios),
        'old_tq_overlap':serial_counts(tq),'rq_native_over_old_tq_ratios':serial_ratios(tqratios),
        'old_tq_files':tq_files,'official_source_bindings':source_hashes,'cross_2020_dataset_boundary_samples':cross_boundary,
        'main_database_written':False,'new_downloads':0,'new_tq_subscriptions':0,'backtests':0,'training_runs':0}
    (OUT/'stage266_units_evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
    deny=sorted({(r['exchange'],r['rq_symbol'],r['date']) for r in exceptions+tq_exceptions})
    (OUT/'stage266_units_exceptions.json').write_text(json.dumps({'generated_at':evidence['generated_at'],'scope':'2010+ only','conflict_reference_rows':len(exceptions),
        'unit_conflicts':exceptions,'old_tq_conflict_reference_rows':len(tq_exceptions),'old_tq_unit_conflicts':tq_exceptions,
        'unique_conflict_keys':len(deny),'quarantine_keys':[{'exchange':e,'rq_symbol':s,'date':d} for e,s,d in deny],
        'policy':'No ratio-based row repair. Quarantine conflicts, retain raw values; canonical source precedence is cleaner responsibility.'},ensure_ascii=False,indent=2)+'\n')
    # Dataset parity is a disproof screen for mixing, not sufficient proof of units by itself.
    (OUT/'stage266_units_dataset_parity.json').write_text(json.dumps(dataset_parity,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'evidence':str(OUT/'stage266_units_evidence.json'),'conflict_reference_rows':len(exceptions),'official_rows':sum(v['reference_rows'] for v in official.values()),'old_tq_files':len(tq_files)},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
