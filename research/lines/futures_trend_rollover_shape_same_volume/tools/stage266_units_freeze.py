"""Create source-locked Stage266 unit contract from independently read-only audit."""
from collections import Counter,defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import csv,json,re,sys
from independent_review_stage265_dce_rq import sha
LINE=Path(__file__).resolve().parents[1]
OUT=LINE/'outputs/stage266_clean_daily'
def main():
    e=json.loads((OUT/'stage266_units_evidence.json').read_text());x=json.loads((OUT/'stage266_units_exceptions.json').read_text())
    path=OUT/'stage266_units_quarantine.csv'
    rows=[]
    for r in x['quarantine_keys']:
        match=re.fullmatch(r'([A-Z]+)(\d{2})(\d{2})(F?)',r['rq_symbol'])
        if not match:raise ValueError(r)
        product=match[1]+('_F' if match[4] else '');month='20'+match[2]+match[3]
        rows.append({'contract_epoch_id':r['exchange']+'.'+product+'.'+month,'trade_date':r['date'],
            'exchange':r['exchange'],'product':product,'contract_yyyymm':month,'rq_symbol':r['rq_symbol'],
            'reason':'unresolved_cross_source_quantity_conflict','action':'exclude_entire_contract_day_all_sources'})
    rows.sort(key=lambda r:(r['contract_epoch_id'],r['trade_date']))
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
    evidence_paths=[OUT/f for f in ['stage266_units_evidence.json','stage266_units_exceptions.json','stage266_units_dataset_parity.json','stage266_units_quarantine.csv']]
    contract={
        'schema_version':'stage266.units.v1','generated_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
        'cleaner_rule_approved':True,'approval_scope':'Only pinned RQ H5 and observed Stage265/old-TQ files, 2010-01-01..2026-10-16; no universal future-vendor guarantee',
        'canonical_quantity_unit':'single_sided_contracts','preserve_native_fields':True,
        'source_lock':{'rq_h5_sha256':e['rq_h5_sha256'],'rq_metadata_sha256':e['rq_metadata_sha256'],'rq_last_observed_day':'2026-09-30'},
        'rqalpha':{'real_contracts_only':True,'include_dce_month_average_F':True,'nominal_contract_month_from_symbol':True,
            'rules':[{'exchanges':['SHFE','INE','DCE','CZCE'],'start':'2010-01-01','end':'2019-12-31','native_side':'double','volume_factor':0.5,'close_oi_factor':0.5},
                {'exchanges':['SHFE','INE','DCE','CZCE'],'start':'2020-01-01','end':'2026-09-30','native_side':'single','volume_factor':1.0,'close_oi_factor':1.0},
                {'exchanges':['CFFEX'],'start':'2010-01-01','end':'2026-09-30','native_side':'single','volume_factor':1.0,'close_oi_factor':1.0},
                {'exchanges':['GFEX'],'start':'2022-12-22','end':'2026-09-30','native_side':'single','volume_factor':1.0,'close_oi_factor':1.0}],
            'pre2010_action':'unknown_outside_calibrated_scope_preserve_raw_do_not_apply_rule',
            'open_interest_timing':'close_end_of_trading_day','open_oi':None,'missing_open_oi_action':'keep_null_never_shift_previous_close_oi',
            'pre2020_integer_even_guard_fields':['volume','open_interest'],'guard_failure_action':'quarantine_do_not_round_or_infer'},
        'old_tq':{'native_side':'single','volume_factor':1.0,'close_oi_factor':1.0,'open_oi_factor':1.0,
            'scope':'Only 4041 existing pinned CSV files enumerated with SHA in stage266_units_evidence.json; observed dates 2016..2026. No assumption about absent earlier files.',
            'open_oi_timing':'start_of_day_bar','close_oi_timing':'end_of_day_bar','pre2020_calibration_overlap_rows':4211},
        'recent_tq':{'native_side':'single','volume_factor':1.0,'close_oi_factor':1.0,'open_oi_factor':1.0,
            'scope':'Frozen Stage265 tq_latest daily35 observed rows only, final dates <=2026-10-16',
            'open_oi_timing':'start_of_day_bar','close_oi_timing':'end_of_day_bar','forming_2026_10_19_action':'exclude'},
        'official':{'accepted_regime_factors':{'official_two_sided_volume_and_close_oi':0.5,
            'official_single_sided_volume_and_close_oi':1.0,'cffex_official_single_sided_volume_and_close_oi':1.0,
            'official_2026_single_sided_volume_and_close_oi':1.0},
            'factor_applies_to':['volume','close_oi'],'unknown_regime_action':'exclude_from_clean_daily_preserve_reference',
            'infer_from_year_alone':False,'dce_annual_archive_priority_eligible':False,
            'dce_annual_archive_policy':'Cross-check evidence only. Empirically mostly double through2022, but no reliable per-pack footnote; do not promote via year or modal ratio.'},
        'zero_volume_action':'preserve_raw_exclude_from_real_traded_bar_history_even_if_positive_flat_ohlc',
        'quarantine':{'path':str(path),'sha256':sha(path),'format':'csv','key_fields':['contract_epoch_id','trade_date'],
            'contract_epoch_id_format':'EXCHANGE.PRODUCT.YYYYMM; uppercase PRODUCT; month-average product suffix _F',
            'row_count':len(rows),'scope':'all candidate sources, including official, old_tq, recent_tq and rqalpha',
            'action':'exclude_entire_contract_day_all_sources','override_allowed':False,
            'reason':'Quantity conflict has no proved ground truth. Do not rescue a row by priority or inferred ratio.'},
        'prohibited_inferences':['Do not divide CFFEX by2','Do not divide already single TQ by2',
            'Do not default prev_closeOI to true openOI','Do not infer any official archive unit from trade year alone',
            'Do not label all source mismatches as unit-side switching','Do not extend pinned-file rule outside calibrated dates or hashes'],
        'evidence_bindings':[{'path':str(p),'sha256':sha(p)} for p in evidence_paths],
        'audit_tool':{'path':str(LINE/'tools/stage266_units_audit.py'),'sha256':sha(LINE/'tools/stage266_units_audit.py')},
        'backtests':0,'training_runs':0,'new_market_downloads':0,'new_tq_subscriptions':0,'main_database_written':False,
    }
    cpath=OUT/'unit_contract.json';cpath.write_text(json.dumps(contract,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'contract':str(cpath),'sha256':sha(cpath),'quarantine':contract['quarantine'],'sample':rows[:2]},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
