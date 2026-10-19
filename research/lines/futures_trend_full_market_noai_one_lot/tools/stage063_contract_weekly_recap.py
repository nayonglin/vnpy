"""Replace only weekly OHLCV/MA with exact traded-contract accepted-clean weeks.

Read a completed canonical raw/R recap. Keep every other payload, coordinate,
selection and trade marker, and render through the unchanged canonical _html.
"""
import argparse,csv,hashlib,json,math,shutil
from pathlib import Path
import numpy as np
import pandas as pd
from stage001_frozen_recap import CANONICAL,load_display_functions,sha256
from stage058_weekly_contract import WeeklyContractTrend
from stage062_contract_weekly_overview import WEEKLY_POLICY
from stage042_account_overview import verify_hashes,safe_member

FIELDS=('open','high','low','close','volume','ma5','ma10','ma20','ma40')
META_FIELD='weekly_contract_display'
NOTE=('周K及周MA使用每笔交易合约自身accepted-clean未复权OHLC，禁止主力连续/其他合约/执行报价补周历史；'
    '完整独立交易周格保留缺周，周末会话本合约close无效则整根周OHLCV/MA缺失，40周预热仅用本合约历史。'
    '有效周末但周中缺clean日时仅聚合本合约实际可用日，不补价。partial_sessions表示自然周交易会话未覆盖数（含首次上市边界），不都代表数据缺口。'
    '周线坐标和显示窗沿用父页，所有非周线周期、排序、成交标记及R保持原样。'
    '其他周期仍可能含背景主力拼接或退出报价，不是合约周线门槛证据；真实授权看stage059两JSON与weekly_signal_audit/weekly_execution_audit。')


def require(condition,message):
    if not condition:raise ValueError(message)


def payload_hash(values):
    h=hashlib.sha256();h.update(b'[')
    for i,value in enumerate(values):
        if i:h.update(b',')
        h.update(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode())
    h.update(b']');return h.hexdigest()


def non_weekly_payload_hash(records):
    return payload_hash({**{k:v for k,v in r.items() if k not in ('weekly','meta')},'meta':{k:v for k,v in r['meta'].items() if k!=META_FIELD}} for r in records)


def coordinate_hash(records):return payload_hash({k:r['weekly'][k] for k in ('label','x','width')} for r in records)


def explicit_false(value):return isinstance(value,(bool,np.bool_)) and not bool(value)


def build_weekly_tables(market,contracts,calendar,symbols):
    """Full local calendar weeks before display cropping; EOW gates match 058."""
    require({'date','vt_symbol','open','high','low','close','volume','execution_only','quote_class'}.issubset(market.columns),'missing_exact_weekly_market_columns')
    renderer=load_display_functions({});market=market.copy();market['date']=pd.to_datetime(market.date).dt.normalize().dt.tz_localize(None)
    require(not market.duplicated(['date','vt_symbol']).any(),'duplicate_contract_daily_price')
    gate=WeeklyContractTrend(market,contracts,calendar);positions=market.groupby('vt_symbol',sort=False).indices
    metadata=contracts.set_index('vt_symbol');tables={}
    clean=market.execution_only.map(explicit_false)&market.quote_class.eq('accepted_clean')
    if 'allow_new_open' in market:clean&=~market.allow_new_open.map(explicit_false)
    values=market[['open','high','low','close','volume']].apply(pd.to_numeric,errors='coerce')
    clean&=np.isfinite(values).all(axis=1)&values.gt(0).all(axis=1)
    clean&=values.high.ge(values[['open','close','low']].max(axis=1))&values.low.le(values[['open','close','high']].min(axis=1))
    cal=pd.DatetimeIndex(pd.to_datetime(calendar['date'] if isinstance(calendar,pd.DataFrame) else calendar)).normalize().tz_localize(None)
    require(not cal.has_duplicates,'duplicate_calendar_session')
    calendar_counts=pd.Series(cal).groupby(cal.to_period('W-FRI').astype(str)).size()
    for vt in sorted(symbols):
        require(vt in metadata.index,'unknown_chart_contract:'+vt)
        gate.lookup(vt,market.date.max(),phase='signal_close')
        features=pd.DataFrame(gate._cache[vt])
        if features.empty:
            tables[vt]=pd.DataFrame(columns=['week',*FIELDS,'partial_sessions','valid']);continue
        features['week']=pd.to_datetime(features.week_last_session).dt.to_period('W-FRI').astype(str)
        require(not features.week.duplicated().any(),'calendar_week_alignment_ambiguous')
        local=market.iloc[positions.get(vt,[])];local=local.loc[clean.loc[local.index]]
        listed=pd.to_datetime(metadata.loc[vt].get('listed_date'),errors='coerce')
        if pd.notna(listed):local=local[local.date.ge(listed)]
        agg=renderer._weekly_from_daily(local.sort_values('date')).set_index('week').reindex(features.week).reset_index()
        valid=features.valid.to_numpy(dtype=bool)
        for field in ('open','high','low','close','volume'):agg.loc[~valid,field]=np.nan
        observed=local.groupby(local.date.dt.to_period('W-FRI').astype(str)).size()
        agg['partial_sessions']=(agg.week.map(calendar_counts).fillna(0)-agg.week.map(observed).fillna(0)).clip(lower=0).astype(int)
        agg['valid']=valid
        agg=renderer._add_moving_averages(agg)
        for field in ('close','ma5','ma10','ma20','ma40'):
            wanted=pd.to_numeric(features[field],errors='coerce').to_numpy(dtype=float)
            require(np.allclose(agg[field],wanted,equal_nan=True,atol=1e-8,rtol=1e-12),'canonical_vs_058_weekly_mismatch:'+vt+':'+field)
        tables[vt]=agg
    return tables


def number(value):return float(value) if value is not None and pd.notna(value) and math.isfinite(float(value)) else None


def replace_weekly_records(records,tables):
    for r in records:
        vt=str(r['meta']['vt_symbol']);require(vt in tables,'missing_exact_weekly_table:'+vt)
        frame=tables[vt].set_index('week');w=r['weekly'];require(len(set(w['label']))==len(w['label']),'duplicate_parent_week_label')
        aligned=frame.reindex(w['label']);updated={**w,**{field:[number(v) for v in aligned[field]] for field in FIELDS}}
        r['weekly']=updated
        r['meta'][META_FIELD]=dict(source=WEEKLY_POLICY['source'],contract_vt_symbol=vt,full_history_weeks=len(frame),
            visible_weeks=len(w['label']),visible_missing_weeks=sum(v is None for v in updated['close']),
            visible_partial_sessions=int(aligned.partial_sessions.fillna(0).sum()),calendar_gaps_preserved=True)
    return records



def validate_weekly_records(records,tables):
    """Check every exported value against the full exact-contract table."""
    slots=missing=0
    for record in records:
        vt=str(record['meta']['vt_symbol']);weekly=record['weekly'];labels=weekly['label']
        expected=tables[vt].set_index('week').reindex(labels)
        require(len(weekly['x'])==len(weekly['width'])==len(labels),'weekly_coordinate_length_mismatch')
        for field in FIELDS:
            wanted=[number(value) for value in expected[field]]
            require(weekly[field]==wanted,'weekly_value_mismatch:'+vt+':'+field)
        slots+=len(labels);missing+=sum(value is None for value in weekly['close'])
    return dict(records_checked=len(records),contracts_checked=len(tables),weekly_slots=slots,
        ohlcv_values_checked=slots*5,ma_values_checked=slots*4,missing_weekly_slots=missing,
        exact_table_values_match=True,calendar_gaps_preserved=True)


def validate_frozen_features(tables,features):
    require({'contract_vt_symbol','week_last_session','close','ma5','ma10','ma20','ma40'}.issubset(features.columns),'frozen_weekly_feature_columns_missing')
    count=0
    for vt,rows in features.groupby('contract_vt_symbol',sort=False):
        if vt not in tables:continue
        labels=pd.to_datetime(rows.week_last_session).dt.to_period('W-FRI').astype(str)
        frame=tables[vt].set_index('week')
        require(set(labels).issubset(frame.index),'frozen_weekly_history_missing:'+vt)
        expected=frame.reindex(labels)
        for field in ('close','ma5','ma10','ma20','ma40'):
            require(np.allclose(pd.to_numeric(rows[field],errors='coerce'),expected[field],equal_nan=True,atol=1e-8,rtol=1e-12),'frozen_weekly_feature_mismatch:'+vt+':'+field)
        count+=len(rows)
    return count


def enrich(source,parent,output):
    source,parent,output=(Path(p).resolve() for p in (source,parent,output))
    for original in (source,parent):require(not(output.is_relative_to(original) or original.is_relative_to(output)),'output_must_be_isolated')
    if output.exists():raise FileExistsError(output)
    dependencies={name:sha256(Path(__file__).with_name(name)) for name in ('stage001_frozen_recap.py','stage042_account_overview.py','stage055_weekly_account_overview.py','stage058_weekly_contract.py','stage062_contract_weekly_overview.py')}
    generator_hash=sha256(Path(__file__));source_hash=sha256(source/'manifest.json');identity=json.loads((source/'manifest.json').read_text());bound=verify_hashes(source,identity)
    for name in ('trading_calendar.csv','contract_metadata.csv','market_daily.csv','weekly_contract_features.csv'):require(name in bound,'weekly_source_binding_missing:'+name)
    metrics=json.loads((source/'summary.json').read_text())
    for item in (identity,metrics):require(item.get('long_weekly_filter') is True and item.get('weekly_policy')==WEEKLY_POLICY,'exact_weekly_policy_mismatch')
    summary=json.loads((parent/'summary.json').read_text());parent_hash=sha256(parent/'summary.json')
    require(summary['source_manifest_sha256']==source_hash and Path(summary['source_directory']).resolve()==source,'parent_source_identity_mismatch')
    require(summary['backtest_metrics']==metrics,'parent_metrics_mismatch')
    require(summary['canonical_renderer_sha256']==sha256(CANONICAL),'canonical_hash_mismatch')
    for name in ('records.json','index.html','chart_manifest.csv','closed_lots.csv','all_trade_episodes.csv'):require(name in summary['artifact_sha256'],'parent_binding_missing:'+name)
    for name,digest in summary['artifact_sha256'].items():require(sha256(safe_member(parent,name))==digest,'parent_hash_mismatch:'+name)
    for name in ('stage058_weekly_contract.py',):
        if name in identity.get('code_snapshot_hashes',{}):require(sha256(Path(__file__).with_name(name))==identity['code_snapshot_hashes'][name],'weekly_feature_code_mismatch')
    records=json.loads((parent/'records.json').read_text());page=(parent/'index.html').read_text();marker='const records='
    embedded,_=json.JSONDecoder().raw_decode(page[page.index(marker)+len(marker):]);require(embedded==records,'parent_embedded_records_mismatch');del embedded,page
    before=non_weekly_payload_hash(records);coords=coordinate_hash(records)
    market=pd.read_csv(source/'market_daily.csv',float_precision='round_trip');metadata=pd.read_csv(source/'contract_metadata.csv',float_precision='round_trip');calendar=pd.read_csv(source/'trading_calendar.csv')
    tables=build_weekly_tables(market,metadata,calendar,{str(r['meta']['vt_symbol']) for r in records});replace_weekly_records(records,tables)
    validation=validate_weekly_records(records,tables)
    validation['frozen_signal_feature_weeks_checked']=validate_frozen_features(tables,pd.read_csv(source/'weekly_contract_features.csv',float_precision='round_trip'))
    require(non_weekly_payload_hash(records)==before,'non_weekly_payload_changed');require(coordinate_hash(records)==coords,'weekly_coordinates_changed')
    provenance=dict(source_manifest_sha256=source_hash,parent_directory=str(parent),parent_summary_sha256=parent_hash,parent_artifact_sha256=dict(summary['artifact_sha256']),
        generator_sha256=generator_hash,dependency_sha256=dependencies,canonical_renderer_sha256=sha256(CANONICAL),weekly_feature_code_sha256=sha256(Path(__file__).with_name('stage058_weekly_contract.py')),
        weekly_policy=WEEKLY_POLICY,validation=validation,records=len(records),contracts=len(tables),weekly_slots=sum(len(r['weekly']['label']) for r in records),
        missing_weekly_slots=sum(r['meta'][META_FIELD]['visible_missing_weeks'] for r in records),
        non_weekly_payload_sha256_before=before,non_weekly_payload_sha256_after=non_weekly_payload_hash(records),
        weekly_coordinate_sha256_before=coords,weekly_coordinate_sha256_after=coordinate_hash(records),financial_replays=0,market_downloads=0,source_mutations=0)
    summary['weekly_contract_enrichment']=provenance;summary['source_warning']+=' '+NOTE
    summary['page_title']='交易合约自身周K · '+summary.get('page_title','逐笔复盘');summary['source_label']='交易合约自身周K · '+summary.get('source_label','')
    renderer=load_display_functions({});page=renderer._html(records,summary)
    def unchanged():
        require(sha256(Path(__file__))==generator_hash and sha256(CANONICAL)==provenance['canonical_renderer_sha256'],'display_code_changed')
        for name,digest in dependencies.items():require(sha256(Path(__file__).with_name(name))==digest,'display_dependency_changed:'+name)
        require(sha256(source/'manifest.json')==source_hash and verify_hashes(source,identity)==bound,'source_changed_during_render')
        require(sha256(parent/'summary.json')==parent_hash,'parent_changed_during_render')
        for name,digest in provenance['parent_artifact_sha256'].items():require(sha256(safe_member(parent,name))==digest,'parent_changed_during_render:'+name)
    unchanged();output.mkdir(parents=True)
    for name in summary['artifact_sha256']:
        if name not in ('index.html','records.json','chart_manifest.csv','summary.json'):shutil.copy2(parent/name,output/name)
    with (parent/'chart_manifest.csv').open(newline='',encoding='utf-8-sig') as handle:
        reader=csv.DictReader(handle);fields=list(reader.fieldnames);rows=list(reader)
    by_id={str(r['meta']['open_trade_id']):r['meta'][META_FIELD] for r in records};new_fields=('weekly_price_source','weekly_contract_vt_symbol','weekly_missing_weeks','weekly_partial_sessions')
    require(len(rows)==len(records),'chart_manifest_episode_count_mismatch')
    for row in rows:
        detail=by_id[row['open_trade_id']];row.update(dict(zip(new_fields,(WEEKLY_POLICY['source'],detail['contract_vt_symbol'],detail['visible_missing_weeks'],detail['visible_partial_sessions']))))
    with (output/'chart_manifest.csv').open('w',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=fields+[k for k in new_fields if k not in fields]);writer.writeheader();writer.writerows(rows)
    pd.concat([frame.assign(contract_vt_symbol=vt) for vt,frame in tables.items()],ignore_index=True).to_csv(output/'weekly_contract_chart_features.csv',index=False)
    (output/'records.json').write_text(json.dumps(renderer._json_safe(records),ensure_ascii=False,separators=(',',':'))+'\n');(output/'index.html').write_text(page)
    saved=json.loads((output/'records.json').read_text());require(non_weekly_payload_hash(saved)==before and coordinate_hash(saved)==coords,'persisted_nonweekly_or_coordinates_changed');validate_weekly_records(saved,tables);del saved
    embedded,_=json.JSONDecoder().raw_decode(page[page.index(marker)+len(marker):]);require(non_weekly_payload_hash(embedded)==before and coordinate_hash(embedded)==coords,'embedded_nonweekly_or_coordinates_changed');validate_weekly_records(embedded,tables);del embedded
    validation['persisted_records_json_verified']=True;validation['embedded_html_records_json_verified']=True
    (output/'weekly_contract_display_manifest.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2)+'\n');unchanged()
    summary['artifact_sha256']={p.name:sha256(p) for p in output.iterdir() if p.name!='summary.json'}
    (output/'summary.json').write_text(json.dumps(renderer._json_safe(summary),ensure_ascii=False,indent=2)+'\n');return summary


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('source','parent','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();result=enrich(a.source,a.parent,a.output);print(json.dumps(result['weekly_contract_enrichment'],ensure_ascii=False,indent=2))

if __name__=='__main__':main()
