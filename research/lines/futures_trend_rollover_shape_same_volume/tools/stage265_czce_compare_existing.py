"""Read-only exact-epoch overlap diagnostics; never rescale or write bars."""
from collections import Counter,defaultdict
import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo

LINE=Path(__file__).resolve().parents[1]
ROOT=LINE.parents[2]
OUT=LINE/'outputs/stage265_deep_daily/czce'
DB=ROOT/'.vntrader/database.db'
FIELDS=('open','high','low','close','volume','open_interest')


def same(a,b):
    return abs(float(a)-float(b))<1e-8


def main():
    bars=[]
    input_sha={}
    for path in sorted(OUT.glob('work_*_fullmarket_bars.csv')):
        input_sha[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
        with path.open(encoding='utf-8-sig',newline='') as stream:
            bars.extend(csv.DictReader(stream))
    targets={(r['vt_symbol'].split('.')[0],r['date']):r for r in bars}
    if len(targets)!=len(bars):
        raise RuntimeError('duplicate_symbol_date_within_2010_2018_snapshot')
    existing={}
    by_symbol=defaultdict(list)
    con=sqlite3.connect(DB.resolve().as_uri()+'?mode=ro',uri=True)
    con.row_factory=sqlite3.Row
    con.execute('PRAGMA query_only=ON')
    for raw in con.execute("SELECT symbol,datetime,open_price,high_price,low_price,close_price,volume,open_interest FROM dbbardata WHERE exchange='CZCE' AND interval='d' AND datetime>='2010-01-01' AND datetime<'2018-04-27' ORDER BY symbol,datetime"):
        row={'symbol':raw['symbol'],'date':raw['datetime'][:10],**{f:raw[f+'_price'] if f in FIELDS[:4] else raw[f] for f in FIELDS}}
        key=row['symbol'],row['date']
        if key in existing:
            raise RuntimeError('duplicate_database_daily_symbol_date')
        existing[key]=row
        by_symbol[row['symbol']].append(row)
    con.close()
    next_bar={}
    for symbol,rows in by_symbol.items():
        for a,b in zip(rows,rows[1:]):
            # Only a bounded next observed daily bar is a clock diagnostic.
            da=datetime.fromisoformat(a['date']);db=datetime.fromisoformat(b['date'])
            if (db-da).days<=14:
                next_bar[symbol,a['date']]=b
    counters=defaultdict(Counter)
    diff=[]
    for key,source in targets.items():
        product=source['product']
        c=counters[product]
        c['source_rows']+=1
        if key not in existing:
            c['new_unique_days']+=1
            continue
        local=existing[key]
        c['overlap_rows']+=1
        different=[]
        for field in FIELDS:
            if same(source[field],local[field]):
                c['equal_'+field]+=1
            else:
                c['different_'+field]+=1
                different.append(field)
        if all(same(source[field],local[field]) for field in FIELDS[:4]):
            c['equal_ohlc']+=1
        if same(source['volume'],2*float(local['volume'])):
            c['source_volume_equals_2x_database']+=1
        if same(source['open_interest'],2*float(local['open_interest'])):
            c['source_oi_equals_2x_database_same_day']+=1
        if key in next_bar:
            c['next_database_day_available']+=1
            if same(source['open_interest'],2*next_bar[key]['open_interest']):
                c['source_oi_equals_2x_next_database_day_oi']+=1
            if same(source['open_interest'],next_bar[key]['open_interest']):
                c['source_oi_equals_next_database_day_oi']+=1
        if different:
            diff.append({'contract_epoch_id':source['contract_epoch_id'],'date':source['date'],'different_fields':','.join(different),
                **{'source_'+f:source[f] for f in FIELDS},**{'database_'+f:local[f] for f in FIELDS}})
    fields=['contract_epoch_id','date','different_fields',*['source_'+f for f in FIELDS],*['database_'+f for f in FIELDS]]
    with (OUT/'work_fullmarket_existing_differences.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        w=csv.DictWriter(stream,fieldnames=fields);w.writeheader();w.writerows(diff)
    totals=Counter()
    for c in counters.values(): totals.update(c)
    report={'generated_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),'status':'read_only_overlap_diagnostics_no_rescaling_or_acceptance',
        'source_input_sha256':input_sha,'database_path':str(DB),'database_size_bytes':DB.stat().st_size,
        'database_daily_rows_in_query':len(existing),'by_product':{p:dict(c) for p,c in sorted(counters.items())},'totals':dict(totals),
        'source_ohlc_equality_is_not_metadata_certification':True,
        'clock_interpretation':'Repository importer source indicates TQ open_oi. A source OI equal to 2x the next observed database daily OI supports close/open timing and double/single units; it does not authorize per-row replacement, use of next-day OI as a feature, or universal rescaling.',
        'database_writes':0,'training_runs':0,'backtest_runs':0}
    (OUT/'work_fullmarket_existing_overlap.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report['totals'],ensure_ascii=False,indent=2))


if __name__=='__main__':main()
