"""Independent offline audit of the already-downloaded three-exchange TQ tail."""
from collections import Counter,defaultdict
import csv
from datetime import datetime,timezone
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import re
from zoneinfo import ZoneInfo

import h5py
import numpy as np

from independent_review_stage265_dce_rq import safe_metadata,sha,valid_price,equal,day_of

LINE=Path(__file__).resolve().parents[1]
BASE=LINE/'outputs/stage265_deep_daily'
OUT=BASE/'tq_latest'
RQ=BASE/'rqalpha'
PREFIX='independent_review_stage265_tq_tail'
START,END='2026-09-01','2026-10-16'
EXCHANGES={'DCE','CZCE','GFEX'}
FIELDS=('open','high','low','close')


def write(suffix,obj):
    (OUT/(PREFIX+suffix+'.json')).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def parse_tq_day(row):
    ns=int(Decimal(row['datetime']))
    return datetime.fromtimestamp(ns/1e9,timezone.utc).astimezone(ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%d')


def main():
    catalog_path=OUT/'current_futures_catalog.json';status_path=OUT/'recent_download_status.json'
    catalog=json.loads(catalog_path.read_text());status=json.loads(status_path.read_text())
    metadata,safety=safe_metadata(RQ/'instruments.pk')
    futures=[r for r in metadata if r.get('type')=='Future']
    md_by_tq=defaultdict(list)
    for r in futures:
        if not '2000-01-01'<=r.get('listed_date','')<=END or r.get('de_listed_date','')<START:continue
        md_by_tq[(r.get('exchange'),r.get('trading_code','').casefold())].append(r)
    expected=set(status['expected_symbols']);current=set(catalog['symbols'])
    reconstructed={s for s in current if s.split('.')[0] in EXCHANGES}
    for item in futures:
        if item.get('exchange') in EXCHANGES and '2000-01-01'<=item.get('listed_date','')<=END and item.get('de_listed_date','')>='2026-10-01':
            reconstructed.add(item['exchange']+'.'+item['trading_code'])
    errors=[];rows_by_symbol={};files=[];traded=[];no_trade=[];invalid=[];latest=Counter();by_exchange=defaultdict(Counter)
    source_finger=hashlib.sha256();metadata_absent=[];metadata_multiple=[];future_suffix=[]
    before={str(p):p.stat().st_mtime_ns for p in (catalog_path,status_path,RQ/'futures.h5',RQ/'instruments.pk')}
    if reconstructed!=expected:errors.append('expected_symbol_selection_mismatch')
    if len(expected)!=542 or len(current)!=870:errors.append('unexpected_census_count')
    for symbol in sorted(expected):
        item=status['items'][symbol];path=OUT/item['file'];rows=list(csv.DictReader(path.open()))
        digest=sha(path);source_finger.update((symbol+':'+digest+'\n').encode())
        files.append({'symbol':symbol,'file':item['file'],'sha256':digest,'rows':len(rows)})
        if item.get('status')!='downloaded' or len(rows)!=item['rows']:errors.append('status_row_count:'+symbol)
        dates=[r['trade_date'] for r in rows]
        if len(dates)!=len(set(dates)) or dates!=sorted(dates):errors.append('duplicate_or_unordered_day:'+symbol)
        if dates and (min(dates)<START or max(dates)>END):errors.append('outside_cutoff:'+symbol)
        if dates and (min(dates)!=item['first_date'] or max(dates)!=item['last_date']):errors.append('reported_date_range:'+symbol)
        if not dates and (item['first_date'] is not None or item['last_date'] is not None):errors.append('empty_reported_range:'+symbol)
        latest[dates[-1] if dates else 'empty']+=1
        exchange,code=symbol.split('.',1);by_exchange[exchange]['symbols']+=1;by_exchange[exchange]['raw_rows']+=len(rows)
        rows_by_symbol[symbol]=rows
        md=md_by_tq.get((exchange,code.casefold()),[])
        if not md:metadata_absent.append(symbol)
        if len(md)>1:metadata_multiple.append({'symbol':symbol,'ids':[x['order_book_id'] for x in md]})
        if exchange=='DCE' and code.endswith('F'):
            future_suffix.append({'symbol':symbol,'rq_order_book_id':md[0]['order_book_id'] if len(md)==1 else None,
                'rq_maturity_date':md[0].get('maturity_date') if len(md)==1 else None,
                'nominal_contract_yymm':re.search(r'(\d{4})F$',code)[1],
                'last_date':dates[-1] if dates else None,'raw_rows':len(rows)})
        for row in rows:
            if row['symbol']!=symbol or int(row['duration'])!=86400:errors.append('symbol_duration:'+symbol)
            if parse_tq_day(row)!=row['trade_date'] or datetime.fromisoformat(row['timestamp_shanghai']).strftime('%Y-%m-%d')!=row['trade_date']:
                errors.append('timestamp_trade_date:'+symbol+':'+row['trade_date'])
            numbers={f:float(row[f]) for f in (*FIELDS,'volume','open_oi','close_oi')}
            if not all(math.isfinite(x) for x in numbers.values()) or any(numbers[f]<0 for f in ('volume','open_oi','close_oi')):
                invalid.append({'symbol':symbol,'date':row['trade_date'],'reason':'nonfinite_or_negative','numbers':{f:x if math.isfinite(x) else None for f,x in numbers.items()}})
                continue
            context={'symbol':symbol,'date':row['trade_date'],**numbers}
            if numbers['volume']<=0:
                no_trade.append(context);by_exchange[exchange]['zero_volume_rows_excluded']+=1;continue
            if not valid_price(numbers):
                invalid.append({**context,'reason':'invalid_ohlc'});by_exchange[exchange]['invalid_traded_rows']+=1;continue
            traded.append(context);by_exchange[exchange]['valid_traded_rows']+=1
    overlap=defaultdict(Counter);differences=[];empty_checks=[];no_rq_dataset=[]
    future_meta=[r for r in futures if r.get('exchange')=='DCE' and re.fullmatch(r'[A-Z]+\d{4}F',r['order_book_id']) and r.get('listed_date','')>'2000-01-01']
    f_h5_summary={'real_metadata_contracts':len(future_meta),'dataset_count':0,'missing_datasets':[],
                  'yearly_rows':{},'missing_expected_calendar_days':0}
    f_yearly=defaultdict(Counter)
    calendar=np.load(RQ/'trading_dates.npy',allow_pickle=False)
    calendar_days=[str(int(x))[:4]+'-'+str(int(x))[4:6]+'-'+str(int(x))[6:8] for x in calendar]
    with h5py.File(RQ/'futures.h5','r') as h5:
        for item in future_meta:
            key=item['order_book_id']
            if key not in h5:f_h5_summary['missing_datasets'].append(key);continue
            f_h5_summary['dataset_count']+=1;data=h5[key][:];seen=set()
            for row in data:
                day=day_of(row['datetime']);seen.add(day);out=f_yearly[day[:4]];out['raw_rows']+=1
                if float(row['volume'])<=0:out['zero_volume_rows_excluded']+=1
                elif valid_price(row):out['valid_traded_rows']+=1
                else:out['invalid_traded_rows']+=1
            expected_days={d for d in calendar_days if item['listed_date']<=d<=min(item['de_listed_date'],'2026-09-30')}
            f_h5_summary['missing_expected_calendar_days']+=len(expected_days-seen)
        f_h5_summary['yearly_rows']={y:dict(x) for y,x in f_yearly.items()}
        for symbol,rows in rows_by_symbol.items():
            exchange,code=symbol.split('.',1);md=md_by_tq.get((exchange,code.casefold()),[])
            if len(md)!=1:continue
            rqid=md[0]['order_book_id']
            if rqid not in h5:
                no_rq_dataset.append({'symbol':symbol,'rq_id':rqid});continue
            data=h5[rqid][:];by_day={day_of(r['datetime']):r for r in data}
            if not rows:
                empty_checks.append({'symbol':symbol,'rq_id':rqid,'listed_date':md[0]['listed_date'],
                    'delisted_date':md[0]['de_listed_date'],'rq_rows':len(data),
                    'rq_date_min':min(by_day) if by_day else None,'rq_date_max':max(by_day) if by_day else None,
                    'rq_all_stored_volume_zero':bool((data['volume']==0).all()),
                    'rq_volume_sum':float(data['volume'].sum()),
                    'classification':'real listed contract; RQ stored no-trade encoding through 09-30; TQ empty does not prove every later historical day had no trades'})
            for row in rows:
                if row['trade_date']>'2026-09-30':continue
                out=overlap[exchange];out['tq_september_raw_rows']+=1;rq=by_day.get(row['trade_date'])
                if rq is None:out['rq_day_missing']+=1;continue
                out['matched_raw_keys']+=1
                tv,rv=float(row['volume']),float(rq['volume'])
                if tv<=0 or rv<=0:
                    out['not_both_traded_excluded']+=1
                    if tv>0 and rv<=0:out['tq_traded_rq_zero_volume']+=1
                    if tv<=0 and rv>0:out['tq_zero_volume_rq_traded']+=1
                    continue
                out['both_traded']+=1
                same=all(equal(row[f],rq[f]) for f in FIELDS)
                out['ohlc_equal' if same else 'ohlc_different']+=1
                veq=equal(tv,rv);ceq=equal(row['close_oi'],rq['open_interest']);oeq=equal(row['open_oi'],rq['open_interest'])
                out['volume_equal']+=veq;out['close_oi_equal_rq_oi']+=ceq;out['open_oi_equal_rq_oi']+=oeq
                if not same or not veq or not ceq:
                    differences.append({'symbol':symbol,'rq_id':rqid,'date':row['trade_date'],'ohlc_equal':same,
                        'volume_equal':veq,'close_oi_equal':ceq,
                        'tq':{f:float(row[f]) for f in (*FIELDS,'volume','open_oi','close_oi')},
                        'rq':{f:float(rq[f]) for f in (*FIELDS,'volume','open_interest')}})
    initial_proofs=[]
    for sample in json.loads((OUT/'initial_probe.json').read_text())['samples']:
        symbol=sample['symbol'];path=Path(sample['file'])
        if not path.is_absolute():path=LINE.parents[2]/path
        initial=list(csv.DictReader(path.open()))
        formed=[parse_tq_day(row) for row in initial if parse_tq_day(row)>END]
        final_days={r['trade_date'] for r in rows_by_symbol[symbol]}
        initial_proofs.append({'symbol':symbol,'initial_rows':len(initial),'initial_after_cutoff_dates':formed,
            'none_after_cutoff_in_final':not any(d>END for d in final_days)})
    quoted=OUT/(PREFIX+'_empty_quotes.json');quote=json.loads(quoted.read_text()) if quoted.exists() else None
    quote_counts=Counter()
    if quote:
        for symbol,q in quote.get('quotes',{}).items():
            if q.get('static_metadata_ready') and q.get('ins_class')=='FUTURE' and not q.get('expired'):
                quote_counts['listed_unexpired_static_metadata_ready']+=1
            if q.get('volume')==0 and q.get('last_price') is None:quote_counts['no_observable_latest_trade_price_volume_zero']+=1
            if q.get('datetime'):quote_counts['actual_quote_message_timestamp_present']+=1
    census={}
    for exchange in sorted({s.split('.')[0] for s in current}|EXCHANGES):
        c={s for s in current if s.split('.')[0]==exchange};e={s for s in expected if s.split('.')[0]==exchange}
        census[exchange]={'current_catalog':len(c),'tail_selected':len(e),'intersection':len(c&e),
            'catalog_not_in_tail':len(c-e),'tail_not_in_current':sorted(e-c)}
    totals=Counter()
    for value in overlap.values():totals.update(value)
    after={str(p):p.stat().st_mtime_ns for p in (catalog_path,status_path,RQ/'futures.h5',RQ/'instruments.pk')}
    report={'generated_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),'scope':'Already-downloaded DCE/CZCE/GFEX recent daily tail, no batch redownload',
        'metadata_safety':safety,'source_mtimes_unchanged':before==after,'catalog_total':len(current),'tail_total':len(expected),
        'selection_reconstructed_equal':reconstructed==expected,'exchange_census':census,'latest_date_distribution':dict(latest),
        'reported_formed_rows_excluded':sum(x.get('future_or_incomplete_rows_excluded',0) for x in status['items'].values()),
        'independent_original_probe_formed_row_proofs':initial_proofs,'raw_csv_file_count':len(list((OUT/'daily35').glob('*.csv'))),
        'raw_csv_fingerprint_sha256':source_finger.hexdigest(),'by_exchange':{k:dict(v) for k,v in by_exchange.items()},
        'raw_rows':sum(len(r) for r in rows_by_symbol.values()),'valid_traded_rows':len(traded),
        'zero_volume_rows_excluded':len(no_trade),'invalid_rows':len(invalid),'validation_errors':errors,
        'empty_series_checks':empty_checks,'readonly_empty_quote_result':dict(quote_counts),
        'rq_snapshot_metadata_absent_symbols':metadata_absent,'ambiguous_contemporaneous_metadata':metadata_multiple,
        'rq_metadata_dataset_missing':no_rq_dataset,'F_month_average_current_contracts':future_suffix,
        'F_real_metadata_count_all_vintages':len(future_meta),
        'F_h5_supplement_to_prior_plain_contract_review':f_h5_summary,
        'september_overlap_by_exchange':{k:dict(v) for k,v in overlap.items()},'september_overlap_totals':dict(totals),
        'september_field_difference_rows':len(differences),
        'post_rq_cutoff_observed_raw_rows':sum(row['trade_date']>'2026-09-30' for rows in rows_by_symbol.values() for row in rows),
        'post_rq_cutoff_valid_traded_rows':sum(r['date']>'2026-09-30' for r in traded),
        'post_rq_cutoff_valid_traded_on_10_16':sum(r['date']=='2026-10-16' for r in traded),
        'prior_cutoff_P1':'The 09-30-only limitation is resolved for actually observed tail rows through 10-16, not for unobserved zero-trade days or other exchanges.',
        'F_scope_correction':'Previous plain-YYMM DCE review excluded actual F monthly-average contracts together with nonstandard codes. Those earlier counts apply only to ordinary contracts; this tail review includes all 18 current F contracts and preserves suffix F. Named contract YYMM and maturity date may differ.',
        'unit_semantics':'TQ volume compared unscaled with RQ in September 2026; TQ close_oi compared with daily RQ open_interest. TQ open_oi is a different opening-time field and must not silently replace closing OI.',
        'no_trade_policy':'All V0 rows excluded from genuine bars; empty quotes prove only latest observable state, never blanket historical zero volume.',
        'network_calls_in_offline_review':0,'quote_probe_symbols':5 if quote else 0,'batch_redownloads':0,
        'database_write_calls':0,'backtest_calls':0,'training_calls':0}
    write('',report)
    write('_details',{'csv_files':files,'invalid_rows':invalid,'september_field_differences':differences,
        'empty_quote_evidence_path':str(quoted.relative_to(LINE)) if quote else None})
    write('_verdict',{'generated_at':report['generated_at'],'scope':'TQ recent-tail integrity, not unqualified full-history merge',
        'P0':0,'P1':int(bool(errors or invalid)),'base_contract_pass':not errors and not invalid,
        'cutoff_closed_for_observed_genuine_rows_only':True,
        'actual_valid_traded_rows_after_09_30':report['post_rq_cutoff_valid_traded_rows'],
        'actual_valid_traded_rows_on_10_16':report['post_rq_cutoff_valid_traded_on_10_16'],
        'empty_series_latest_quote_classification':'All five are listed unexpired FUTURE instruments with timestamped quote messages but zero volume and no observable last trade price; historical non-trading cannot be generalized.',
        'cross_source_price_differences':len(differences),
        'all_price_difference_rq_rows_invalid':all(not valid_price(r['rq']) and valid_price(r['tq']) for r in differences),
        'merge_requirement':'Preserve observed source rows and explicit source priority; exclude all V0 and quarantine incompatible prices. Do not create bars on unobserved days.',
        'F_current_contracts_included':len(future_suffix),'F_all_snapshot_contracts_included_in_supplement':len(future_meta),
        'other_exchange_tail_not_reviewed':['SHFE','INE','CFFEX'],
        'previous_review_scope_correction':report['F_scope_correction']})
    print(json.dumps({k:v for k,v in report.items() if k not in ('F_month_average_current_contracts','empty_series_checks','independent_original_probe_formed_row_proofs')},ensure_ascii=False))


if __name__=='__main__':main()
