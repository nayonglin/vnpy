"""One incremental exclusion of unresolved cross-source prices, before acceptance.

Does not reread input archives. Raw disagreement evidence is retained. The
initial builder and this finalizer form one deterministic preparation workflow.
"""
from collections import Counter
import csv
from datetime import datetime
import gzip
import json
import shutil
import sqlite3
from pathlib import Path

from stage266_clean_daily import OUT, digest, load_json


def main():
    dbpath=OUT/'clean_daily.sqlite'
    summary=load_json(OUT/'cleaning_summary.json')
    if summary.get('price_conflict_finalization'):
        raise RuntimeError('already_finalized_no_silent_second_pass')
    rows={}
    with gzip.open(OUT/'source_disagreements.csv.gz','rt',encoding='utf-8') as f:
        for r in csv.DictReader(f):
            if set(r['different_fields'].split('|')) & {'open','high','low','close'}:
                rows[(r['contract_epoch_id'],r['trade_date'])]=dict(contract_epoch_id=r['contract_epoch_id'],
                    trade_date=r['trade_date'],reason='unresolved_cross_source_ohlc',action='exclude_whole_contract_day_all_sources')
    quarantine=OUT/'price_conflict_quarantine.csv'
    with quarantine.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['contract_epoch_id','trade_date','reason','action'],lineterminator='\n')
        w.writeheader();w.writerows(rows[k] for k in sorted(rows))
    temp=OUT/'clean_daily.finalizing.sqlite'
    if temp.exists():
        raise RuntimeError('prior_incomplete_finalization_needs_explicit_review')
    shutil.copy2(dbpath,temp)
    affected={key[0] for key in rows}
    csv_inventory=load_json(OUT/'csv_inventory.json')
    inventory_by_id={x['contract_epoch_id']:x for x in csv_inventory}
    header=['trade_date','datetime','open','high','low','close','volume','open_oi','close_oi',
        'contract_epoch_id','open_oi_status','legacy108_row_usable','source_id','volume_factor','oi_factor']
    with sqlite3.connect(temp) as db:
        before=db.execute('SELECT COUNT(*) FROM daily_bars').fetchone()[0]
        db.executemany('DELETE FROM daily_bars WHERE contract_epoch_id=? AND trade_date=?',sorted(rows))
        after=db.execute('SELECT COUNT(*) FROM daily_bars').fetchone()[0]
        if before-after!=len(rows):
            raise RuntimeError('price_quarantine_key_count_not_exact')
        for identity in sorted(affected):
            item=inventory_by_id[identity];target=OUT/item['path']
            fields=['trade_date','open','high','low','close','volume','open_oi','close_oi','open_oi_status',
                'legacy108_row_usable','source_id','volume_factor','oi_factor']
            count=complete=0
            with target.open('w',encoding='utf-8-sig',newline='') as f:
                w=csv.DictWriter(f,fieldnames=header,lineterminator='\n');w.writeheader()
                for r in db.execute('SELECT '+','.join(fields)+' FROM daily_bars WHERE contract_epoch_id=? ORDER BY trade_date',(identity,)):
                    record=dict(zip(fields,r));record.update(datetime=record['trade_date']+' 00:00:00+08:00',contract_epoch_id=identity)
                    w.writerow(record);count+=1;complete+=record['legacy108_row_usable']
            item.update(rows=count,legacy108_rows=complete,sha256=digest(target))
        groups=db.execute('SELECT exchange,COUNT(*),COUNT(DISTINCT contract_epoch_id),SUM(legacy108_row_usable),MIN(trade_date),MAX(trade_date) FROM daily_bars GROUP BY exchange').fetchall()
        sources=db.execute('SELECT s.family,COUNT(*),SUM(d.legacy108_row_usable) FROM daily_bars d JOIN sources s USING(source_id) GROUP BY s.family').fetchall()
    temp.replace(dbpath)
    summary.update(generated_at=datetime.now().astimezone().isoformat(),db_sha256=digest(dbpath),
        selected_rows=after,legacy108_row_usable=sum(r[3] for r in groups),
        by_exchange=[dict(zip(['exchange','selected_rows','contracts','legacy108_rows','first_date','last_date'],r)) for r in groups],
        by_selected_source=[dict(zip(['family','selected_rows','legacy108_rows'],r)) for r in sources],
        price_conflict_finalization=dict(initial_selected_rows=before,excluded_contract_days=len(rows),
            final_selected_rows=after,affected_csv_files=len(affected),raw_archives_reread=0,
            script_sha256=digest(Path(__file__)),quarantine_path=str(quarantine),quarantine_sha256=digest(quarantine),
            rule='Unresolved cross-source OHLC differences are quarantined independent of performance; no source priority can rescue these keys'))
    (OUT/'cleaning_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    (OUT/'csv_inventory.json').write_text(json.dumps(csv_inventory,ensure_ascii=False,indent=2)+'\n')
    contract=load_json(OUT/'contract.json')
    contract.update(price_conflict_path=str(quarantine),price_conflict_sha256=digest(quarantine),
        price_conflict_count=len(rows),price_conflict_action='exclude_entire_contract_day_all_sources',
        finalization_source_path=str(Path(__file__)),finalization_source_sha256=digest(Path(__file__)),
        finalized=True,final_database_sha256=summary['db_sha256'])
    (OUT/'contract.json').write_text(json.dumps(contract,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'selected_rows':after,'legacy108_rows':summary['legacy108_row_usable'],
        'excluded_price_conflict_keys':len(rows),'affected_csv_files':len(affected),
        'db_sha256':summary['db_sha256'],'contract_sha256':digest(OUT/'contract.json')},ensure_ascii=False))


if __name__=='__main__':
    main()
