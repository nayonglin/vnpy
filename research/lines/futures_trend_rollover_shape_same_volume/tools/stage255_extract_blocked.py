"""Stage255只读提取已记录候选拒绝/计划未成交与换月延迟上下文。"""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import numpy as np
import pandas as pd

KEY=['date','contract_vt_symbol','direction','entry_context']
REASONS={
 'short_signal_rejected':'空头入口拒绝：只允许 short_case1a，本候选为其他空头信号族',
 'sizing_zero_volume':'最终定仓手数为零；具体已记录风控条件见附加诊断，不等同于余额不足',
 'ai_product_pool_blocked':'当期正式品种资格池不包含该品种（主拒绝原因）',
 'planned_open_unfilled_same_day_deleverage':'计划开仓后同日发生保证金强制减仓，最终无对应开仓成交；无独立订单取消回执',
}
ZH={
 'drop_strictly_above_threshold':'信号日不利下跌严格超过 ATR 冲击阈值',
 'rise_strictly_above_threshold':'信号日不利上涨严格超过 ATR 冲击阈值',
 'range_strictly_above_and_recent_gain_below_threshold':'区间扩张超过阈值且近期上涨停滞',
 'short_range_strictly_above_and_recent_decline_below_threshold':'空头区间扩张超过阈值且近期下跌停滞',
 'ordered_drawdown_strictly_above_threshold':'有序回撤超过阈值',
 'short_ordered_rebound_strictly_above_threshold':'空头有序反弹超过阈值',
}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def clean(x):
 if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,np.generic):x=x.item()
 return None if pd.isna(x) else x

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[4]);ap.add_argument('--source',type=Path);ap.add_argument('--output',type=Path);a=ap.parse_args()
 root=a.root.resolve();line=root/'research/lines/futures_trend_rollover_shape_same_volume';src=a.source or line/'outputs/stage254_formal_2025/run_diagnostic';out=a.output or line/'outputs/stage255_blocked_signals';out.mkdir(parents=True,exist_ok=True)
 names=['entry_candidates.csv','long_signal_atr_shock.csv','long_signal_range_atr.csv','rollover_shape_same_volume.csv','rollover_delay.csv','entry_risk.csv','trade_events.csv','execution_proxy_usage.csv','trades.csv','pending_orders.csv','actual_strategy_settings.json','effective_parameters.json','metrics.json','run_provenance.json']
 hashes={n:sha(src/n) for n in names};frames={n:pd.read_csv(src/n) for n in names if n.endswith('.csv')};cand=frames['entry_candidates.csv'];prov=read(src/'run_provenance.json');metrics=read(src/'metrics.json');settings=read(src/'actual_strategy_settings.json')[0]['actual']
 assert not cand[KEY].duplicated().any() and cand.candidate_index.is_unique
 assert set(cand.candidate_status)=={'opened','skipped'} and cand.date.between(metrics['start'],metrics['end']).all()
 assert settings['reverse_on_opposite_signal'] is False
 assert set(cand.loc[cand.candidate_status.eq('skipped'),'skip_reason'])<=set(REASONS)
 def evidence(name,index,role):return {'source_file':str(src/name),'source_row_index':int(index),'source_record_number_1based':int(index)+1,'source_sha256':hashes[name],'role':role,'raw_record':clean(frames[name].loc[index].to_dict())}
 bykey={tuple(r[k] for k in KEY):int(i) for i,r in cand.iterrows()};extra={i:[] for i in cand.index};aux=[]
 for name,flag in [('long_signal_atr_shock.csv','long_signal_atr_shock_blocked'),('long_signal_range_atr.csv','long_signal_range_atr_blocked')]:
  f=frames[name];assert not f[KEY].duplicated().any()
  for i,r in f[f[flag].eq(1)].iterrows():
   key=tuple(r[k] for k in KEY);assert key in bykey;ci=bykey[key];assert cand.loc[ci,'candidate_status']=='skipped';reason_col=flag.replace('_blocked','_reason');reason=str(r[reason_col]);code=f'{flag}:{reason}';ev=evidence(name,i,'additional_recorded_blocked_condition');ev.update(code=code,reason_zh=ZH.get(reason,reason),candidate_index=int(cand.loc[ci,'candidate_index']));extra[ci].append(ev);aux.append(ev)
 usage=frames['execution_proxy_usage.csv'].copy();usage['normalized_direction']=usage.direction.replace({'Long':'long','Short':'short','多':'long','空':'short'});usage_open=usage[usage.offset.isin(['Open','开'])];fillkeys=set(zip(usage_open.signal_date,usage_open.vt_symbol,usage_open.normalized_direction));tradeids=set(frames['trades.csv'].trade_id);assert set(usage.trade_id)==tradeids
 selected=[];unfilled=[]
 for i,r in cand.iterrows():
  key=(r.date,r.contract_vt_symbol,r.direction);filled=key in fillkeys
  if r.candidate_status=='skipped':assert not filled;selected.append((i,r,'candidate_rejected',str(r.skip_reason),[]))
  elif not filled:
   risk=frames['entry_risk.csv'];rr=risk[risk.date.eq(r.date)&risk.contract_vt_symbol.eq(r.contract_vt_symbol)&risk.direction.eq(r.direction)];te=frames['trade_events.csv'];ev=te[te.date.eq(r.date)&te.vt_symbol.eq(r.contract_vt_symbol)&te.position_direction.eq(r.direction)&te.reason.eq('forced_margin_deleverage')]
   assert len(rr)==len(ev)==1 and rr.actual_filled_volume.isna().all() and rr.filled_entry_price.isna().all()
   assert float(ev.volume.iloc[0])==float(r.selected_volume) and float(ev.price.iloc[0])==float(r.planned_entry_price)
   linked=[evidence('entry_risk.csv',rr.index[0],'planned_entry_without_fill'),evidence('trade_events.csv',ev.index[0],'same_day_forced_margin_target_reduction')]
   selected.append((i,r,'planned_open_unfilled','planned_open_unfilled_same_day_deleverage',linked));unfilled.append(int(r.candidate_index))
 rows=[]
 for i,r,kind,reason,linked in selected:
  assert np.isfinite(r.planned_entry_price) and r.planned_entry_price>0
  signal_key='|'.join([str(r.date),str(r.contract_vt_symbol),str(r.direction),str(r.entry_context)])
  ident='stage255_'+hashlib.sha256((str(src.resolve())+'|'+signal_key).encode()).hexdigest()[:20]
  ai_allowed=int(r.ai_product_pool_allowed);raw_rank=clean(r.ai_product_pool_rank);raw_score=clean(r.ai_product_pool_score)
  related=[evidence('entry_candidates.csv',i,'primary_candidate_record'),*extra[i],*linked]
  conditions=[x['code'] for x in extra[i]]
  if ai_allowed==0:conditions.append('ai_pool_disallowed_recorded')
  if int(r.selected_volume)==0 and reason!='sizing_zero_volume':conditions.append('selected_volume_zero_recorded')
  row={'signal_id':ident,'candidate_key':signal_key,'date':r.date,'signal_date':r.date,'signal_datetime':r.datetime,'contract_vt_symbol':r.contract_vt_symbol,'vt_symbol':r.contract_vt_symbol,'product_vt_symbol':r.product_vt_symbol,'direction':r.direction,'signal_family':r.signal,'signal':r.signal,'entry_context':r.entry_context,'candidate_index':int(r.candidate_index),'candidate_status':r.candidate_status,'record_kind':kind,'blocking_reason_code':reason,'blocking_reason_zh':REASONS[reason],'primary_reason_code':reason,'is_ai_primary_block':reason=='ai_product_pool_blocked','ai_pool_disallowed':ai_allowed==0,'ai_allowed':ai_allowed,'ai_eval_date':clean(r.ai_product_pool_signal_date),'ai_rank':raw_rank if ai_allowed else None,'ai_score':raw_score if ai_allowed else None,'ai_rank_raw':raw_rank,'ai_score_raw':raw_score,'ai_score_rank_semantics':'exported_allowed_product_rank_and_score' if ai_allowed else 'not_in_exported_pool; raw_zero_is_default_placeholder_not_rank_or_score','ai_reason_zh':'当期资格允许' if ai_allowed else '当期正式资格池不含此品种；原文件未提供落选全宇宙排名或模型原因','reference_price':float(r.planned_entry_price),'reference_price_date':r.date,'reference_price_source_field':'entry_candidates.csv.planned_entry_price','reference_price_semantics':'策略信号日bar.close_price的定仓参考价；不是实际委托价或成交价','reference_price_is_execution':False,'stop_price_reference':float(r.stop_price),'selected_volume_raw':int(r.selected_volume),'has_actual_open_fill':False,'additional_blocking_reason_codes':json.dumps(conditions,ensure_ascii=False),'additional_blocking_reasons_zh':json.dumps([x['reason_zh'] for x in extra[i]],ensure_ascii=False),'atr_shock_blocked':any(x['code'].startswith('long_signal_atr_shock') for x in extra[i]),'range_atr_blocked':any(x['code'].startswith('long_signal_range_atr') for x in extra[i]),'source_file':str(src/'entry_candidates.csv'),'source_row_index':int(i),'source_record_number_1based':int(i)+1,'source_sha256':hashes['entry_candidates.csv'],'related_evidence_json':json.dumps(clean(related),ensure_ascii=False,allow_nan=False),'source_run':str(src.resolve()),'source_run_provenance_sha256':hashes['run_provenance.json'],'data_completeness':'diagnostic_incomplete_minutes; 2 ordinary execution anchor gaps in underlying run','outcome_semantics':'未成交/拒绝记录，无真实交易PnL；不推断若入场后的盈亏'}
  for col in ['sizing_equity','limited_balance','free_capital','contracts_by_risk','contracts_by_margin','contracts_by_single_trade_cap','risk_cluster_max_volume','remaining_position_slots','risk_per_contract','margin_per_contract']:
   if col in r:row[col]=clean(r[col])
  rows.append(row)
 blocked=pd.DataFrame(rows).sort_values(['date','candidate_index']).reset_index(drop=True);assert blocked.signal_id.is_unique
 assert len(blocked)==len(cand[cand.candidate_status.eq('skipped')])+len(unfilled)
 blocked.to_csv(out/'blocked_signals.csv',index=False,encoding='utf-8-sig')
 auxrows=[{'candidate_index':x['candidate_index'],'code':x['code'],'reason_zh':x['reason_zh'],'source_file':x['source_file'],'source_row_index':x['source_row_index'],'source_sha256':x['source_sha256'],'raw_record_json':json.dumps(x['raw_record'],ensure_ascii=False,allow_nan=False)} for x in aux]
 pd.DataFrame(auxrows).to_csv(out/'blocking_evidence.csv',index=False,encoding='utf-8-sig')
 delay=frames['rollover_delay.csv'].copy();delay['is_deferred_context']=delay.status.isin(['scheduled','waiting']);delay['is_new_candidate_signal']=False;delay['source_row_index']=delay.index;delay['source_file']=str(src/'rollover_delay.csv');delay['source_sha256']=hashes['rollover_delay.csv'];delay['reference_price']=np.nan;delay['reference_price_semantics']='未记录；不从其他日期或合约拼造参考价';delay['rollover_episode_key']=delay.product_vt_symbol+'|'+delay.old_contract_vt_symbol+'|'+delay.target_contract_vt_symbol+'|'+delay.signal_date;delay.to_csv(out/'rollover_delay_context.csv',index=False,encoding='utf-8-sig')
 shape=frames['rollover_shape_same_volume.csv'];assert set(shape.status)=={'targeted'} and (shape.final_volume==shape.previous_volume).all()
 skipped=cand[cand.candidate_status.eq('skipped')];source_summary={'status':'read_only_extraction_complete','source_run':str(src.resolve()),'window':{'start':metrics['start'],'end':metrics['end']},'candidate_count':len(cand),'candidate_status_counts':cand.candidate_status.value_counts().to_dict(),'primary_skip_reason_counts':skipped.skip_reason.value_counts().to_dict(),'blocked_signals_rows':len(blocked),'record_kind_counts':blocked.record_kind.value_counts().to_dict(),'ai_primary_block_count':int(blocked.is_ai_primary_block.sum()),'ai_pool_disallowed_count':int(blocked.ai_pool_disallowed.sum()),'ai_disallowed_by_primary_reason':skipped[skipped.ai_product_pool_allowed.eq(0)].skip_reason.value_counts().to_dict(),'auxiliary_atr_shock_blocked_records':sum(x['code'].startswith('long_signal_atr_shock') for x in aux),'auxiliary_range_atr_blocked_records':sum(x['code'].startswith('long_signal_range_atr') for x in aux),'auxiliary_unique_candidates':len({x['candidate_index'] for x in aux}),'all_auxiliary_blocked_records_attached_to_existing_candidates':True,'planned_open_unfilled_candidate_indexes':unfilled,'unfilled_classification_evidence':'opened candidate + unfilled entry_risk + same-symbol/date/direction/volume forced_margin_deleverage event + no open fill for candidate key; no actual cancellation receipt claimed','rollover_delay_status_counts':delay.status.value_counts().to_dict(),'rollover_delay_deferred_rows':int(delay.is_deferred_context.sum()),'rollover_delay_distinct_episodes':int(delay.rollover_episode_key.nunique()),'rollover_delay_counted_as_candidate_signal':False,'shape_status_counts':shape.status.value_counts().to_dict(),'shape_blocked_count':0,'reverse_on_opposite_signal':settings['reverse_on_opposite_signal'],'reference_price_missing':int(blocked.reference_price.isna().sum()),'source_hashes':hashes,'script_sha256':sha(__file__),'blocked_signals_sha256':sha(out/'blocked_signals.csv'),'columns':list(blocked.columns),'no_new_backtest_download_or_strategy_change':True,'limitations':['Only recorded candidates/diagnostics; not all theoretical price-pattern signals.','MA5 extreme, short MA5 slope, wick chop and optional angle filters can clear signals before candidate logging. Missing mapping/bar, insufficient history/AM readiness, entry_allowed_today and no-plan branches can be absent.','Reverse-on-opposite disabled in this run; absence of reverse diagnostics is not proof that no opposite pattern existed.','Primary skip reason follows code precedence; AI eligibility can fail alongside short-type or sizing rejection.','Zero final volume does not by itself identify a unique risk subcause; retain recorded numeric caps and attached ATR flags.','No actual trade outcome or counterfactual PnL exists for blocked signals; planned price is not a fill price.','Underlying Stage254 diagnostic retained two incomplete ordinary execution anchors.']}
 for n,h in hashes.items():assert sha(src/n)==h,n
 (out/'source_summary.json').write_text(json.dumps(clean(source_summary),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
 notes=f'''# Stage255 已记录拦截候选提取与语义审查

- 范围：{metrics['start']}至{metrics['end']}，Stage254独立15万空仓起点的既有诊断输出；仅读取，不回测、不下载、不改策略。
- entry_candidates共{len(cand)}条：181 skipped、55 opened。主表{len(blocked)}条=181条直接拒绝+1条计划开仓但未成交；candidate的opened是策略计划状态，不自动等于成交。
- 主要拒绝原因：空头信号族拒绝102、最终手数为零43、AI资格拒绝36。空头仅允许short_case1a（策略源码8364行）；不把其他空头族称为AI拒绝。
- AI主因36条；所有AI资格不允许91条，另有37条空头主因、18条零手数主因。is_ai_primary_block和ai_pool_disallowed分别保留；原rank/score为0时只是默认占位，展示值留空，raw字段保留，不虚构落选名次或模型理由。
- ATR shock的3条blocked、range ATR的33条blocked均附回已拒绝候选；不再新增36条信号。附加原因和完整原始行见related_evidence_json及blocking_evidence.csv。condition_met不等于实际blocked，提取只认*_blocked==1。
- 换月形态仅1条targeted且同手数成功，无形态拒绝。换月延迟18条=6 scheduled+11 waiting+1 due，写入rollover_delay_context.csv；17条延迟上下文属于6次换月过程，不是17个新增入场信号，due不算阻断。
- 特殊记录：candidate153，2026-03-04 OI605.CZCE long_case2，计划4手、参考9486。同日forced_margin_deleverage记录4手，entry_risk填价/填量为空，usage/trades没有此候选的开仓成交；归类planned_open_unfilled。证据支持同日目标减仓后计划未成交，不宣称有独立订单取消回执，也不记实际亏损。
- 参考价来自entry_candidates.planned_entry_price；源码_record_entry_candidate_snapshot先取bar.close_price（6302行），作为信号日定仓参考。182条均非空，日期为signal_date；它不是次日实际可成交价，HTML只能画信号参考点。换月延迟无原始参考价，留空。
- 保留source_row_index（0起始CSV数据记录索引）、source_record_number_1based、candidate_index、稳定signal_id及各来源SHA；按date+contract+direction+entry_context唯一关联，不跨来源按行号猜测。

## 覆盖边界

这不是“所有理论信号”。_passes_entry_filters在候选之前可因MA5极值、短侧MA5坡度、影线震荡及可选角度过滤返回False，_generate_signal会清空signal；这些未入候选。映射/行情缺失、AM或历史未就绪、entry_allowed_today=False及no-plan等分支也没有完整候选拒绝流水。反向开仓开关本次为False，不能从缺少反向记录推断没有相反形态。43条零手数只记录最终结果及可用诊断，不反推唯一资金原因。

底层Stage254为诊断，保留2个普通成交首锚缺口；本页是已有拦截记录复盘，不是完整数据绩效验收。未成交不等于亏损，也不能把未来价格路径当作已实现交易收益。本次是只读解释已有规则，不进行调参；有解释价值，不能据个别事后赢家新增规则。
'''
 (out/'audit_notes.md').write_text(notes)
 print(json.dumps({k:source_summary[k] for k in ['blocked_signals_rows','record_kind_counts','primary_skip_reason_counts','ai_primary_block_count','ai_pool_disallowed_count','auxiliary_unique_candidates','blocked_signals_sha256','script_sha256']},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
