"""Exclude the bounded legacy-reference price disputes without rebuilding sources."""
import csv
from datetime import datetime
import json
from pathlib import Path
import shutil
import sqlite3

from stage266_clean_daily import OUT, digest, load_json


def main():
    summary=load_json(OUT/'cleaning_summary.json')
    if summary.get('legacy_reference_finalization'):
        raise RuntimeError('already_finalized_legacy_reference')
    evidence=OUT/'stage266_legacy_db_price_overlap_differences.csv'
    with evidence.open(encoding='utf-8-sig') as f:
        keys=sorted({(r['contract_epoch_id'],r['trade_date']) for r in csv.DictReader(f)})
    if len(keys)>100:
        raise RuntimeError('unexpected_broad_legacy_disagreement_requires_review')
    dbpath=OUT/'clean_daily.sqlite';before_hash=digest(dbpath)
    temp=OUT/'clean_daily.legacy_finalizing.sqlite'
    if temp.exists():raise RuntimeError('prior_incomplete_legacy_finalization')
    shutil.copy2(dbpath,temp)
    inventory=load_json(OUT/'csv_inventory.json');index={r['contract_epoch_id']:r for r in inventory}
    fields=['trade_date','open','high','low','close','volume','open_oi','close_oi','open_oi_status','legacy108_row_usable','source_id','volume_factor','oi_factor']
    header=['trade_date','datetime','open','high','low','close','volume','open_oi','close_oi','contract_epoch_id','open_oi_status','legacy108_row_usable','source_id','volume_factor','oi_factor']
    with sqlite3.connect(temp) as db:
        before=db.execute('SELECT COUNT(*) FROM daily_bars').fetchone()[0]
        training_removed=0
        for key in keys:
            flag=db.execute('SELECT legacy108_row_usable FROM daily_bars WHERE contract_epoch_id=? AND trade_date=?',key).fetchone()
            if flag is None:raise RuntimeError('legacy_conflict_key_missing')
            training_removed+=flag[0]
        db.executemany('DELETE FROM daily_bars WHERE contract_epoch_id=? AND trade_date=?',keys)
        for identity in sorted({k[0] for k in keys}):
            item=index[identity];target=OUT/item['path'];count=complete=0
            with target.open('w',encoding='utf-8-sig',newline='') as f:
                w=csv.DictWriter(f,fieldnames=header,lineterminator='\n');w.writeheader()
                for r in db.execute('SELECT '+','.join(fields)+' FROM daily_bars WHERE contract_epoch_id=? ORDER BY trade_date',(identity,)):
                    row=dict(zip(fields,r));row.update(datetime=row['trade_date']+' 00:00:00+08:00',contract_epoch_id=identity)
                    w.writerow(row);count+=1;complete+=row['legacy108_row_usable']
            item.update(rows=count,legacy108_rows=complete,sha256=digest(target))
        groups=db.execute('SELECT exchange,COUNT(*),COUNT(DISTINCT contract_epoch_id),SUM(legacy108_row_usable),MIN(trade_date),MAX(trade_date) FROM daily_bars GROUP BY exchange').fetchall()
        sources=db.execute('SELECT s.family,COUNT(*),SUM(d.legacy108_row_usable) FROM daily_bars d JOIN sources s USING(source_id) GROUP BY s.family').fetchall()
    temp.replace(dbpath)
    # One combined price quarantine contains all source-to-source and baseline disputes.
    quarantine=OUT/'price_conflict_quarantine.csv'
    with quarantine.open() as f: all_rows=list(csv.DictReader(f))
    all_rows += [dict(contract_epoch_id=k[0],trade_date=k[1],reason='unresolved_legacy_reference_ohlc',action='exclude_whole_contract_day_all_sources') for k in keys]
    with quarantine.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['contract_epoch_id','trade_date','reason','action'],lineterminator='\n');w.writeheader();w.writerows(all_rows)
    final_hash=digest(dbpath)
    delta=dict(evidence_path=str(evidence),evidence_sha256=digest(evidence),excluded_keys=len(keys),
        legacy108_rows_removed=training_removed,initial_database_sha256=before_hash,final_database_sha256=final_hash,
        source_files_reread=0,script_sha256=digest(Path(__file__)),rule='same whole-day quarantine for unresolved baseline OHLC; never correct prices')
    summary.update(generated_at=datetime.now().astimezone().isoformat(),db_sha256=final_hash,
        selected_rows=before-len(keys),legacy108_row_usable=sum(r[3] for r in groups),legacy_reference_finalization=delta,
        by_exchange=[dict(zip(['exchange','selected_rows','contracts','legacy108_rows','first_date','last_date'],r)) for r in groups],
        by_selected_source=[dict(zip(['family','selected_rows','legacy108_rows'],r)) for r in sources])
    (OUT/'cleaning_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    (OUT/'csv_inventory.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2)+'\n')
    contract=load_json(OUT/'contract.json');contract.update(final_database_sha256=final_hash,
        price_conflict_sha256=digest(quarantine),price_conflict_count=len(all_rows),legacy_reference_finalization=delta,
        legacy_reference_finalization_source=str(Path(__file__)))
    (OUT/'contract.json').write_text(json.dumps(contract,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(selected_rows=summary['selected_rows'],legacy108_rows=summary['legacy108_row_usable'],
        price_quarantine_keys=len(all_rows),db_sha256=final_hash,contract_sha256=digest(OUT/'contract.json')),ensure_ascii=False))


if __name__=='__main__':main()
