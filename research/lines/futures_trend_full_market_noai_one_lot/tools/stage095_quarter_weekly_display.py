"""Exact-contract weekly charts for both quarter-risk strategy modes.

A pure market/calendar display calculation. Never instantiate or query strategy
weekly providers; disabled financial evidence stays empty and explicitly N/A.
Canonical aggregation/MA/payload/HTML functions are reused without copying.
"""
import argparse,csv,json,shutil
from pathlib import Path
import numpy as np
import pandas as pd
import stage063_contract_weekly_recap as old
import stage094_quarter_risk_recap as quarter
from stage001_frozen_recap import CANONICAL,load_display_functions,sha256
from stage042_account_overview import verify_hashes,safe_member

replace_weekly_records=old.replace_weekly_records
non_weekly_payload_hash=old.non_weekly_payload_hash
coordinate_hash=old.coordinate_hash
validate_weekly_records=old.validate_weekly_records

def disclosure(enabled):
 base=old.NOTE[:old.NOTE.index('其他周期仍可能')]
 return base+'其他周期仍可能含背景主力拼接或退出报价。'+quarter.mode_note(enabled)+('周图为复盘显示，不构成额外策略授权。' if enabled else '关闭版周图仅从冻结市场纯展示重建，不构成策略周过滤证据，不声称关闭版满足周门。')

def build_display_tables(market,contracts,calendar,symbols):
 renderer=load_display_functions({});market=market.copy();market['date']=pd.to_datetime(market.date).dt.normalize();quarter.check(not market.duplicated(['vt_symbol','date']).any(),'duplicate_market_daily')
 cal=pd.DatetimeIndex(pd.to_datetime(calendar.date)).normalize();quarter.check(not cal.has_duplicates,'duplicate_calendar');ends=pd.Series(cal).groupby(cal.to_period('W-SUN')).max();counts=pd.Series(cal).groupby(cal.to_period('W-FRI').astype(str)).size();meta=contracts.set_index('vt_symbol');groups={k:v.sort_values('date') for k,v in market.groupby('vt_symbol',sort=False)};tables={}
 clean=market.execution_only.map(old.explicit_false)&market.quote_class.eq('accepted_clean')
 if 'allow_new_open' in market:clean&=~market.allow_new_open.map(old.explicit_false)
 vals=market[list(old.FIELDS[:5])].apply(pd.to_numeric,errors='coerce');clean&=np.isfinite(vals).all(axis=1)&vals.gt(0).all(axis=1)&vals.high.ge(vals[['open','low','close']].max(axis=1))&vals.low.le(vals[['open','high','close']].min(axis=1))
 for vt in sorted(symbols):
  quarter.check(vt in groups and vt in meta.index,'missing_contract_history:'+vt);g=groups[vt];listed=pd.to_datetime(meta.loc[vt].get('listed_date'),errors='coerce');start=listed if pd.notna(listed) else g.date.min();local_ends=ends[(ends.index>=start.to_period('W-SUN'))&(ends.index<=g.date.max().to_period('W-SUN'))];local_ends=local_ends[local_ends.ge(start)]
  selected=g[clean.loc[g.index]&g.date.ge(start)];labels=[str(v.to_period('W-FRI')) for v in local_ends];frame=renderer._weekly_from_daily(selected).set_index('week').reindex(labels).reset_index(names='week');available=set(selected.date);valid=np.array([v in available for v in local_ends],dtype=bool)
  for f in old.FIELDS[:5]:frame.loc[~valid,f]=np.nan
  observed=selected.groupby(selected.date.dt.to_period('W-FRI').astype(str)).size();frame['partial_sessions']=(frame.week.map(counts).fillna(0)-frame.week.map(observed).fillna(0)).clip(lower=0).astype(int);frame['valid']=valid;tables[vt]=renderer._add_moving_averages(frame)
 return tables

def enrich(source,parent,output):
 source,parent,output=map(lambda p:Path(p).resolve(),(source,parent,output))
 for original in (source,parent):quarter.check(not(output.is_relative_to(original) or original.is_relative_to(output)),'output_overlaps_input')
 if output.exists():raise FileExistsError(output)
 code=sha256(Path(__file__));dependencies={n:sha256(Path(__file__).with_name(n)) for n in ('stage094_quarter_risk_recap.py','stage063_contract_weekly_recap.py','stage001_frozen_recap.py')};identity=json.loads((source/'manifest.json').read_text());metrics=json.loads((source/'summary.json').read_text());quarter.validate_policy(identity,metrics);bound=verify_hashes(source,identity);source_hash=sha256(source/'manifest.json');enabled=identity['long_weekly_filter']
 for name in ('trading_calendar.csv','contract_metadata.csv','market_daily.csv','weekly_contract_features.csv'):quarter.check(name in bound,'weekly_binding_missing:'+name)
 features=pd.read_csv(source/'weekly_contract_features.csv',float_precision='round_trip')
 if not enabled:quarter.check(features.empty,'disabled_financial_features_not_empty')
 summary=json.loads((parent/'summary.json').read_text());parent_hash=sha256(parent/'summary.json');artifacts=dict(summary['artifact_sha256']);quarter.check(summary['source_manifest_sha256']==source_hash and summary['backtest_metrics']==metrics,'parent_source_mismatch');quarter.check(summary['canonical_renderer_sha256']==sha256(CANONICAL),'canonical_changed')
 for name,digest in artifacts.items():quarter.check(sha256(safe_member(parent,name))==digest,'parent_hash:'+name)
 records=json.loads((parent/'records.json').read_text());page=(parent/'index.html').read_text();marker='const records=';embedded,_=json.JSONDecoder().raw_decode(page[page.index(marker)+len(marker):]);quarter.check(embedded==records,'parent_embedded_records');del embedded,page
 before=non_weekly_payload_hash(records);coords=coordinate_hash(records);tables=build_display_tables(pd.read_csv(source/'market_daily.csv',float_precision='round_trip'),pd.read_csv(source/'contract_metadata.csv',float_precision='round_trip'),pd.read_csv(source/'trading_calendar.csv'),{r['meta']['vt_symbol'] for r in records});replace_weekly_records(records,tables);validation=validate_weekly_records(records,tables)
 validation['frozen_strategy_feature_weeks_checked']=old.validate_frozen_features(tables,features) if enabled else None;validation['strategy_weekly_filter']=enabled;validation['financial_provider_queries_by_display']=0
 quarter.check(non_weekly_payload_hash(records)==before and coordinate_hash(records)==coords,'protected_payload_changed')
 proof=dict(generator_sha256=code,dependency_sha256=dependencies,source_manifest_sha256=source_hash,parent_directory=str(parent),parent_summary_sha256=parent_hash,parent_artifact_sha256=artifacts,canonical_renderer_sha256=sha256(CANONICAL),validation=validation,weekly_filter=enabled,display_only_weekly_data=True,financial_provider_instantiated=False,financial_provider_queries=0,non_weekly_payload_sha256_before=before,non_weekly_payload_sha256_after=non_weekly_payload_hash(records),weekly_coordinate_sha256_before=coords,weekly_coordinate_sha256_after=coordinate_hash(records),financial_replays=0,market_downloads=0)
 summary['quarter_weekly_display']=proof;summary['source_warning']+=' '+disclosure(enabled);summary['page_title']=('【周过滤启用】' if enabled else '【周过滤关闭，周图仅复盘】')+summary['page_title'];renderer=load_display_functions({});page=renderer._html(records,summary)
 output.mkdir(parents=True)
 for name in artifacts:
  if name not in ('summary.json','index.html','records.json','chart_manifest.csv'):shutil.copy2(parent/name,output/name)
 with (parent/'chart_manifest.csv').open(newline='',encoding='utf-8-sig') as h:reader=csv.DictReader(h);fields=list(reader.fieldnames);rows=list(reader)
 by_id={str(r['meta']['open_trade_id']):r['meta'][old.META_FIELD] for r in records};extra=('weekly_price_source','weekly_contract_vt_symbol','weekly_missing_weeks','weekly_partial_sessions','strategy_weekly_filter')
 for row in rows:
  d=by_id[row['open_trade_id']];row.update(dict(zip(extra,(quarter.WEEKLY_POLICY['source'],d['contract_vt_symbol'],d['visible_missing_weeks'],d['visible_partial_sessions'],enabled))))
 with (output/'chart_manifest.csv').open('w',newline='') as h:w=csv.DictWriter(h,fieldnames=fields+[n for n in extra if n not in fields]);w.writeheader();w.writerows(rows)
 pd.concat([f.assign(contract_vt_symbol=vt) for vt,f in tables.items()],ignore_index=True).to_csv(output/'weekly_contract_chart_features.csv',index=False)
 (output/'records.json').write_text(json.dumps(renderer._json_safe(records),ensure_ascii=False,separators=(',',':'))+'\n');(output/'index.html').write_text(page);saved=json.loads((output/'records.json').read_text());quarter.check(non_weekly_payload_hash(saved)==before and coordinate_hash(saved)==coords,'persisted_protected_payload');validate_weekly_records(saved,tables);del saved
 (output/'quarter_weekly_display_manifest.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n')
 quarter.check(sha256(Path(__file__))==code and sha256(source/'manifest.json')==source_hash and verify_hashes(source,identity)==bound and sha256(parent/'summary.json')==parent_hash,'inputs_changed')
 for name,digest in artifacts.items():quarter.check(sha256(safe_member(parent,name))==digest,'parent_changed')
 for name,digest in dependencies.items():quarter.check(sha256(Path(__file__).with_name(name))==digest,'dependency_changed')
 summary['artifact_sha256']={p.name:sha256(p) for p in output.iterdir() if p.name!='summary.json'};(output/'summary.json').write_text(json.dumps(renderer._json_safe(summary),ensure_ascii=False,indent=2)+'\n');return summary

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('source','parent','output'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();r=enrich(a.source,a.parent,a.output);print(json.dumps(r['quarter_weekly_display'],ensure_ascii=False,indent=2))

if __name__=='__main__':main()
