"""Expiry-only executable-price evidence, separate from accepted training bars.

No financial replay, source mutation, data download, or synthesized candle.
"""
from __future__ import annotations
from collections import Counter,defaultdict
import csv
import gzip
import io
import json
import math
from pathlib import Path
import sqlite3
import sys
import zipfile

import pandas as pd
from stage002_market_source import SOURCE_LINE,LINE,identity,research_symbol

FIELDS=('open','high','low','close','volume')
START,END='2014-01-01','2026-10-16'
OUTPUT=LINE/'outputs/expiry_execution_overlay.csv'


def qualify_pair(contract,day,official,rq):
    if not contract.get('maturity_date') or contract['maturity_date']!=day:
        return False,'not_exact_known_maturity_day'
    for row in [official,rq]:
        try:
            values={k:float(row[k]) for k in [*FIELDS,'close_oi']}
        except (TypeError,ValueError,KeyError):
            return False,'missing_or_invalid_quote'
        if not all(math.isfinite(v) for v in values.values()):
            return False,'nonfinite_quote'
        if any(values[k]<=0 for k in FIELDS) or values['close_oi']<0:
            return False,'nonpositive_price_or_volume_or_negative_oi'
        if not values['low']<=min(values['open'],values['close'])<=max(values['open'],values['close'])<=values['high']:
            return False,'invalid_ohlc_geometry'
    if any(float(official[k])!=float(rq[k]) for k in FIELDS):
        return False,'price_or_volume_disagreement'
    if float(official['close_oi'])!=0 or float(rq['close_oi'])<=0:
        return False,'not_official_zero_oi_vs_positive_rq_oi'
    return True,'eligible_expiry_oi_timing_conflict'


def _date(value):
    text=str(int(value));return f'{text[:4]}-{text[4:6]}-{text[6:8]}'


def _rq_factor(exchange,day,unit_contract):
    rules=[r for r in unit_contract['rqalpha']['rules'] if exchange in r['exchanges'] and r['start']<=day<=r['end']]
    if len(rules)!=1:raise ValueError('rq_unit_contract_not_unique')
    return float(rules[0]['volume_factor']),float(rules[0]['close_oi_factor'])


def _raw_cffex_proof(source,normalized):
    """Decode the actual archive member, never infer a raw quote from normalization."""
    if normalized['exchange']!='CFFEX' or not source['raw_path']:
        raise ValueError('unsupported_raw_archive_proof')
    raw=Path(source['raw_path'])
    with zipfile.ZipFile(raw) as archive:
        member=normalized['source_member'];body=archive.read(member)
    try:text=body.decode('utf-8-sig')
    except UnicodeDecodeError:text=body.decode('gb18030')
    row_number=int(normalized['source_row'])
    rows=list(csv.DictReader(io.StringIO(text)))
    # source_row counts the header as row 1.
    row=rows[row_number-2]
    if row['合约代码'].strip()!=normalized['source_symbol']:
        raise ValueError('raw_contract_identity_disagreement')
    columns={'open':'今开盘','high':'最高价','low':'最低价','close':'今收盘','volume':'成交量','close_oi':'持仓量'}
    actual={key:float(row[column]) for key,column in columns.items()}
    target={key:float(normalized['open_interest' if key=='close_oi' else key]) for key in columns}
    if actual!=target:raise ValueError('raw_normalized_quote_disagreement')
    return dict(raw_archive=identity(raw),member=member,member_sha256=__import__('hashlib').sha256(body).hexdigest(),
                row_number=row_number,raw_values=row,decoded_quote=actual,
                settlement=float(row['今结算']))


def build_overlay():
    import h5py
    clean=SOURCE_LINE/'stage266_clean_daily'
    db_path=clean/'clean_daily.sqlite'
    unit_contract=json.loads((clean/'unit_contract.json').read_text())
    fingerprint_before=identity(db_path)
    with sqlite3.connect(db_path.resolve().as_uri()+'?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row;db.execute('PRAGMA query_only=ON')
        contracts={r['contract_epoch_id']:dict(r) for r in db.execute('SELECT * FROM contracts')}
        sources={r['source_id']:dict(r) for r in db.execute('SELECT * FROM sources')}
    quarantined=pd.read_csv(clean/'stage266_units_quarantine.csv')
    keys={(r.contract_epoch_id,r.trade_date) for r in quarantined.itertuples()
          if START<=r.trade_date<=END and contracts.get(r.contract_epoch_id,{}).get('maturity_date')==r.trade_date}
    observations=defaultdict(list)
    with gzip.open(clean/'excluded_observations.csv.gz','rt',encoding='utf-8-sig') as stream:
        for row in csv.DictReader(stream):
            key=(row['contract_epoch_id'],row['trade_date'])
            if key in keys and row['reason']=='cross_source_quantity_conflict':
                observations[key].append(row)
    normalized_cache={};verified={};evidence=[];output=[];rejected=Counter()
    rq_path=Path(sources['rqalpha']['path'])
    rq_identity=identity(rq_path)
    if rq_identity['sha256']!=sources['rqalpha']['sha256']:
        raise ValueError('rq_source_fingerprint_changed')
    with h5py.File(rq_path,'r') as rq_store:
        for (epoch,day),observed in sorted(observations.items()):
            rq_rows=[r for r in observed if r['source_id']=='rqalpha']
            official_rows=[r for r in observed if r['source_id'].startswith('official:')]
            if len(rq_rows)!=1 or not official_rows:
                rejected['missing_unique_dual_source']+=1;continue
            rr=rq_rows[0];locator=json.loads(rr['source_locator']);rq_symbol=locator['key']
            raw_rq=rq_store[rq_symbol][int(locator['row'])]
            if _date(raw_rq['datetime'])!=day:
                raise ValueError('rq_row_date_disagreement')
            exchange,product,month=epoch.split('.')
            vf,of=_rq_factor(exchange,day,unit_contract)
            rq_quote={**{k:float(raw_rq[k]) for k in FIELDS},'close_oi':float(raw_rq['open_interest'])*of}
            rq_quote['volume']*=vf
            eligible=[]
            for oo in official_rows:
                src=sources[oo['source_id']];path=Path(src['path'])
                if oo['source_id'] not in verified:
                    measured=identity(path)
                    if measured['sha256']!=src['sha256']:raise ValueError('official_source_fingerprint_changed')
                    verified[oo['source_id']]=measured
                if oo['source_id'] not in normalized_cache:
                    with gzip.open(path,'rt',encoding='utf-8-sig') as stream:
                        normalized_cache[oo['source_id']]=list(csv.DictReader(stream))
                matches=[r for r in normalized_cache[oo['source_id']] if r['date']==day and r['product']==product and r['exchange']==exchange and str(r['contract_yyyymm'])==month]
                if len(matches)!=1:
                    rejected['official_normalized_identity_not_unique']+=1;continue
                normal=matches[0]
                factor=unit_contract['official']['accepted_regime_factors'].get(normal['unit_regime'])
                if factor is None:
                    rejected['unknown_official_unit_regime']+=1;continue
                oq={**{k:float(normal[k]) for k in FIELDS},'close_oi':float(normal['open_interest'])*float(factor)}
                oq['volume']*=float(factor)
                okay,reason=qualify_pair(contracts[epoch],day,oq,rq_quote)
                if not okay:rejected[reason]+=1;continue
                try:raw_proof=_raw_cffex_proof(src,normal)
                except ValueError as exc:
                    rejected[str(exc)]+=1;continue
                eligible.append((oo,oq,normal,raw_proof))
            if not eligible:continue
            # No source selection by return: all acceptable official quotes must be identical.
            if any(quote!=eligible[0][1] for _,quote,_,_ in eligible):
                raise ValueError('eligible_official_quote_disagreement')
            oo,oq,normal,raw_proof=sorted(eligible,key=lambda x:x[0]['source_id'])[0]
            evidence_id=f'expiry_execution:{epoch}:{day}'
            vt=research_symbol(exchange,product,month)
            output.append(dict(contract_epoch_id=epoch,exchange=exchange,product=product,contract_yyyymm=month,
                               date=day,**oq,open_oi=None,source_id=oo['source_id'],vt_symbol=vt,
                               execution_only=True,allow_new_open=False,evidence_id=evidence_id,
                               settlement=raw_proof['settlement'],settlement_is_executable_close=False))
            evidence.append(dict(evidence_id=evidence_id,contract=contracts[epoch],quarantine_key=[epoch,day],
                                 source_status='separate_execution_overlay_not_accepted_training_data',
                                 official_normalized=normal,official_normalized_file=verified[oo['source_id']],
                                 official_raw_proof=raw_proof,official_exclusion_record=oo,
                                 rq_source=rq_identity,rq_locator=locator,rq_quote=rq_quote,
                                 rq_native_row={k:float(raw_rq[k]) for k in raw_rq.dtype.names},rq_exclusion_record=rr,
                                 quantity_unit='single_sided_contracts',new_open_allowed=False))
    if fingerprint_before!=identity(db_path):raise ValueError('clean_database_changed')
    frame=pd.DataFrame(output)
    if frame.empty:raise ValueError('no_proven_expiry_overlay_records')
    if frame.duplicated(['vt_symbol','date']).any():raise ValueError('duplicate_overlay_key')
    if OUTPUT.exists():raise ValueError('overlay_exists_refusing_overwrite')
    frame.to_csv(OUTPUT,index=False)
    manifest=dict(status='execution_only_expiry_price_overlay_not_training_acceptance',financial_backtests=0,
                  predicate='known_exact_maturity_day_and_whole_key_quantity_quarantine_and_positive_real_volume_and_exact_official_RQ_OHLCV_agreement_and_official_OI_0_vs_RQ_positive',
                  scope=[START,END],rows=len(frame),products=sorted(set(frame.exchange+'.'+frame['product'])),
                  maturity_quarantine_keys_in_scope=len(keys),observed_maturity_conflict_keys=len(observations),
                  rejected=dict(rejected),source_inputs={n:identity(clean/n) for n in ['clean_daily.sqlite','unit_contract.json','stage266_units_quarantine.csv','excluded_observations.csv.gz']},
                  output=identity(OUTPUT),code=identity(__file__),evidence=evidence,
                  constraints=['No open/new signal/warmup/training eligibility from overlay bars.',
                               'Only existing-position close/valuation may use real OHLC quote.',
                               'Expiry cash settlement is distinct from market-close price and requires its own accounting/fees.',
                               'No zero-volume flat-candle recovery; FB201801 remains unresolved after 2018-01-02.',
                               'Unsupported official raw archive formats are rejected rather than inferred.'])
    (OUTPUT.parent/'expiry_execution_overlay_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in manifest.items() if k not in ['evidence','source_inputs']},ensure_ascii=False,indent=2))

if __name__=='__main__':build_overlay()
