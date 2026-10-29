"""Canonical display-only adapter for 35 unexecuted Stage002 signal events.

The canonical renderer owns all bars/MA aggregation, candles, axes and zoom.
This adapter supplies frozen data and changes only trade-specific semantics.
"""
from __future__ import annotations
import argparse,copy,hashlib,html,importlib.util,json,math,re,subprocess
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[4];LINE=ROOT/'research/lines/futures_weekly_short_ma_slope_gate'
RUN=LINE/'outputs/stage002_C_attempt001';DATA=LINE/'outputs/data_stage001_20261029/data_approved'
OUTPUT=LINE/'outputs/stage003_blocked_recap';SOURCE_HEAD='4be2e9389'
ADAPTER=ROOT/'research/lines/futures_weekly_formal_no_half_r/tools/stage031_canonical_recap.py'
spec=importlib.util.spec_from_file_location('frozen_canonical_adapter',ADAPTER);frozen=importlib.util.module_from_spec(spec);spec.loader.exec_module(frozen)
RENDERER=frozen.RENDERER
sha=frozen.sha256

def verify_hashes(expected):
 bad=[p for p,d in expected.items() if not Path(p).is_file() or sha(Path(p))!=d]
 if bad:raise ValueError('frozen source mismatch:'+repr(bad[:8]))
 return len(expected)

def require_output(output):
 if Path(output).resolve()!=OUTPUT.resolve():raise ValueError('adapter assigned output only')

def select_blocked(short,long):
 selected=[]
 for direction,rows in [('short',short),('long',long)]:
  for row in rows:
   if row.get('applied_block') is not True:continue
   if float(row['selected_volume_before'])<=0 or float(row['selected_volume_after'])!=0:raise ValueError('applied block requires positive plan changed to zero')
   selected.append({**row,'direction':direction})
 selected.sort(key=lambda x:(x['signal_date'],x['vt_symbol'],x['direction'],x['signal']))
 keys=[(x['signal_date'],x['vt_symbol'],x['direction'],x['signal']) for x in selected]
 if len(keys)!=len(set(keys)):raise ValueError('duplicate blocked signal event')
 return [{**x,'event_id':f'B{i:03d}'} for i,x in enumerate(selected,1)]

def _direction(v):return {'多':'long','空':'short','Direction.LONG':'long','Direction.SHORT':'short'}.get(str(v),str(v))
def _open(v):return str(v) in {'开','Open','open','Offset.OPEN'}
def baseline_match(g,candidates,anchors,trades,label):
 key=(g['signal_date'],g['vt_symbol'],g['direction'],g['signal'])
 c=candidates.loc[candidates.date.astype(str).str[:10].eq(key[0]) & candidates.contract_vt_symbol.eq(key[1]) & candidates.direction.map(_direction).eq(key[2]) & candidates.signal.eq(key[3]) & candidates.entry_context.eq('flat_entry')]
 info=dict(source=label,matching_key=dict(signal_date=key[0],vt_symbol=key[1],direction=key[2],signal=key[3]),candidate_count=len(c),actual_open_date=None,actual_open_volume=None,actual_open_trade_ids=[],actual_open_prices=[],pnl=None)
 if c.empty:return {**info,'status':'no_candidate'}
 info.update(candidate_statuses=c.candidate_status.astype(str).tolist(),candidate_selected_volumes=pd.to_numeric(c.selected_volume).tolist())
 if not c.candidate_status.eq('opened').any():return {**info,'status':'candidate_not_opened'}
 a=anchors.loc[anchors.signal_date.astype(str).str[:10].eq(key[0]) & anchors.vt_symbol.eq(key[1]) & anchors.offset.map(_open)]
 t=trades.loc[trades.order_id.astype(str).isin(a.order_id.astype(str)) & trades.vt_symbol.eq(key[1]) & trades.direction.map(_direction).eq(key[2]) & trades.offset.map(_open)]
 if t.empty:return {**info,'status':'candidate_opened_no_actual_fill'}
 dates=sorted(set(t.trading_date.astype(str).str[:10]));return {**info,'status':'actual_open_matched','actual_open_date':dates[0] if len(dates)==1 else dates,'actual_open_volume':float(t.volume.sum()),'actual_open_trade_ids':t.trade_id.astype(str).tolist(),'actual_open_prices':t.price.astype(float).tolist()}

def event_metadata(record,g,baseline,signal_close):
 r=copy.deepcopy(record);m=r['meta'];signal_x=m['entry_x']
 for k in list(m):
  if k.startswith(('entry_','exit_','weighted_exit','profit_','loss_')) or k in {'open_trade_id','close_trade_id','lot_id','holding_calendar_days'}:m.pop(k)
 m.update(event_id=g['event_id'],signal_date=g['signal_date'],signal_close=float(signal_close),signal_x=signal_x,status='被拦候选，未成交',result_type='blocked_'+g['direction'],direction=g['direction'],signal=g['signal'],volume=None,realized_pnl=None,r_multiple=None,lot_count=None,price_change_pct=None,price_change_label='N/A：未成交，非交易收益',selected_volume_before=int(g['selected_volume_before']),selected_volume_after=0,gate_evidence=g,baseline_actual=baseline,selection_basis='真实路径正计划手数被斜率门归零；不是已成交交易',physical_epoch_id=g.get('physical_epoch_id'),actual_fill=False,actual_pnl_available=False)
 return r

def canonical_context(renderer,row,mapping,exact):
 env=renderer._context_daily.__globals__;env['_contract_daily']=lambda symbol:exact.copy() if symbol==row.vt_symbol else (_ for _ in ()).throw(ValueError('proxy prohibited'));env['_daily_from_existing_minute_files']=lambda *a,**kw:pd.DataFrame()
 local=mapping.copy();local['main_contract_vt']=row.vt_symbol
 return renderer._context_daily(row,local,{},allow_daily_download=False,allow_noncritical_daily_gaps=True,data_end=pd.Timestamp('2026-10-29'))

# Semantic overlay only: no candle construction, aggregation, axes or zoom code.
SEMANTIC_HOOK=r'''<script>
(function(){const original=Plotly.react;Plotly.react=function(target,traces,layout,config){
if(target==='chart'&&typeof filtered!=='undefined'&&filtered[active]){
const r=filtered[active],m=r.meta,g=m.gate_evidence,b=m.baseline_actual,sourceMarker=traces.find(t=>t.name==='同源成交价格');
traces=traces.filter(t=>t.name!=='同源成交价格');
if(sourceMarker){traces.push({type:'scatter',mode:'markers',name:'被拦候选，未成交',x:[m.signal_x],y:[m.signal_close],xaxis:sourceMarker.xaxis,yaxis:sourceMarker.yaxis,marker:{symbol:'x',size:14,color:'#dc2626'},hovertemplate:m.signal_date+'<br>当日真实close=%{y}<br>未成交，不是成交价格<extra>被拦候选</extra>'});
[5,10].forEach(p=>traces.push({type:'scatter',mode:'lines+markers',name:'策略观察周 MA'+p,x:m.strategy_ma.x,y:m.strategy_ma['ma'+p],xaxis:sourceMarker.xaxis,yaxis:sourceMarker.yaxis,line:{color:p===5?'#b45309':'#0369a1',width:3,dash:'dot'},marker:{size:8},customdata:m.strategy_ma.dates,hovertemplate:'策略接受周 %{customdata}<br>MA'+p+'=%{y}<extra>门控实际值</extra>'}));}
layout.shapes=(layout.shapes||[]).filter(s=>s.type!=='rect'&&!(s.type==='line'&&s.x0===m.signal_x));layout.shapes.push({type:'line',xref:'x',yref:'paper',x0:m.signal_x,x1:m.signal_x,y0:0,y1:1,line:{color:'#dc2626',width:1.5,dash:'dot'}});layout.annotations=[{xref:'x',yref:'paper',x:m.signal_x,y:1,text:'被拦信号，未成交',showarrow:false,font:{color:'#dc2626'}}];layout.title.text=`被拦候选 #${active+1} ${m.vt_symbol} ${m.direction==='long'?'多头':'空头'}｜${m.signal_date}｜未成交，PnL/R不适用`;
const f=v=>v===null||v===undefined?'N/A':Number(v).toLocaleString('zh-CN',{maximumFractionDigits:5}),status={actual_open_matched:'旧路径实际开仓',no_candidate:'旧路径无同键候选',candidate_not_opened:'旧路径候选本就未开',candidate_opened_no_actual_fill:'旧路径计划开仓，未找到实际成交'};
const metrics=[['事件',m.event_id+' · 未成交'],['方向/信号',(m.direction==='long'?'多头':'空头')+' / '+m.signal],['MA5：前→本 / Δ',`${f(g.ma5_previous)} → ${f(g.ma5_current)} / ${f(g.ma5_delta)}`],['MA10：前→本 / Δ',`${f(g.ma10_previous)} → ${f(g.ma10_current)} / ${f(g.ma10_delta)}`],['实际接受周',g.previous_week_end+' → '+g.week_end],['过滤前计划→后',m.selected_volume_before+' → 0手（非成交）'],['新C盈亏 / R','N/A / N/A'],['上一版本核对',(status[b.status]||b.status)+(b.actual_open_date?'<br>'+b.actual_open_date+'，'+f(b.actual_open_volume)+'手':'')]];
document.getElementById('metrics').innerHTML=metrics.map(([k,v])=>`<div class="metric"><div class="k">${k}</div><div class="v">${v}</div></div>`).join('');
const details=document.getElementById('gateEvidence');if(details)details.innerHTML='<summary>查看策略实际接受的11个周收盘、MA门控与上一版本证据</summary><pre>'+JSON.stringify({gate:g,baseline:b,coverage:m.coverage,ma_warmup_null_counts:m.ma_warmup_null_counts},null,2)+'</pre>';
}return original.call(this,target,traces,layout,config);};})();
</script>'''

def canonical_html(renderer,records,summary):
 page=renderer._html(records,summary)
 # Rename chart-anchor fields to signal semantics in canonical JS references.
 for old,new in [('entry_date','signal_date'),('exit_date','signal_date'),('entry_x','signal_x'),('exit_x','signal_x'),('entry_marker_price','signal_close'),('exit_marker_price','signal_close'),('open_trade_id','event_id')]:page=page.replace('.'+old,'.'+new)
 page,count=re.subn(r'</div><script>(\s*const records=)',lambda m:'</div><details id="gateEvidence" class="note"></details>'+SEMANTIC_HOOK+'<script>'+m.group(1),page,count=1)
 if count!=1:raise ValueError('canonical script boundary changed')
 page,n=re.subn(r'<select id="result">.*?</select>','<select id="result"><option value="all">全部35个被拦候选</option><option value="blocked_long">多头被拦20个</option><option value="blocked_short">空头被拦15个</option></select>',page,count=1)
 if n!=1:raise ValueError('canonical result selector changed')
 page,n=re.subn(r'<select id="sort">.*?</select>','<select id="sort"><option value="date_asc">信号日期从早到晚</option><option value="date_desc">信号日期从晚到早</option></select>',page,count=1)
 if n!=1:raise ValueError('canonical sort selector changed')
 old="filtered.sort((a,b)=>{if(sortMode==='price_desc'"
 new="filtered.sort((a,b)=>{if(sortMode==='date_asc'||sortMode==='date_desc'){const c=a.meta.signal_date.localeCompare(b.meta.signal_date);return sortMode==='date_desc'?-c:c}if(sortMode==='price_desc'"
 if old not in page:raise ValueError('canonical sort implementation changed')
 page=page.replace(old,new,1)
 page,n=re.subn(r'function refreshSelect\(\)\{.*?\}\nfunction colors',"function refreshSelect(){tradeEl.innerHTML=filtered.map((r,i)=>`<option value=\"${i}\">${r.meta.event_id} ${r.meta.vt_symbol} ${r.meta.direction==='long'?'多':'空'} ${r.meta.signal_date} · 被拦未成交</option>`).join('');tradeEl.value=String(active)}\nfunction colors",page,count=1)
 if n!=1:raise ValueError('canonical event selector changed')
 page=page.replace('日K严格展示开仓前300个交易日至最终平仓后50个交易日的可用历史','日K展示信号前300个交易日至信号后50个交易日的可用历史').replace('月K独立展示开仓前10个月至最终平仓后10个月','月K独立展示信号前后各10个月').replace('蓝线=开仓日，紫线=最终平仓日，淡黄色=持仓区间；灰虚线表示精确合约缺历史数据后切到当日主力上下文。','红线/叉=被拦信号日真实收盘，未成交；无持仓区间。缺精确合约历史保持缺口，不使用主力代理。').replace('当前交易无15分钟数据','本页15分钟无缓存、未下载').replace('；切到已补数交易时恢复。','。').replace('当前勾选的周期在这笔交易上没有可绘制数据','当前勾选的周期在此候选上没有可绘制数据').replace('没有符合筛选条件的交易','没有符合筛选条件的候选').replace('上一笔','上一个').replace('下一笔','下一个')
 return page

def _write_json(path,value,renderer):path.write_text(json.dumps(renderer._json_safe(value),ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def build(output=OUTPUT,resume_incomplete=False):
 require_output(output)
 if output.exists() and (not resume_incomplete or (output/'delivery_manifest.json').exists()):raise ValueError('immutable output exists')
 delivery=LINE/'stages/stage002_delivery_manifest.json';d=json.loads(delivery.read_text());verified=verify_hashes(d['files_sha256'])
 if verified!=3141 or d['review']!='PASS_WITH_LIMITATIONS':raise ValueError('unexpected frozen source delivery')
 renderer=frozen.load_canonical_renderer(RENDERER)
 short=json.loads((RUN/'short_ma_slope_decisions.json').read_text());long=json.loads((RUN/'long_ma_slope_decisions.json').read_text());gates=select_blocked(short,long)
 if len(gates)!=35 or sum(x['direction']=='long' for x in gates)!=20:raise ValueError('expected20long15short')
 sources=[delivery,ADAPTER,RENDERER,Path(__file__),Path(__file__).with_name('test_stage003_blocked_recap.py'),LINE/'stages/20261029_2059_stage002_symmetric_result.md',*[(RUN/n) for n in ['short_ma_slope_decisions.json','long_ma_slope_decisions.json','trades.csv','daily.csv','metrics.json','preflight.json','effective_parameters.json','terminal.json']],DATA/'daily.sqlite',DATA/'physical_epoch_daily.csv',DATA/'mapping.csv',DATA/'receipt.json',LINE/'artifacts/stage002_comparison/summary.csv']
 baseline={}
 for direction,role in [('short','stage001_A_attempt003'),('long','stage001_C_attempt003')]:
  p=LINE/'outputs'/role;files=[p/n for n in ['entry_candidates.csv','execution_anchor_requests.csv','trades.csv']];sources.extend(files);baseline[direction]=(role,*[pd.read_csv(f,keep_default_na=False) for f in files])
 hashes={str(p):sha(p) for p in sources};symbols={g['vt_symbol'] for g in gates};parts=[]
 for chunk in pd.read_csv(DATA/'physical_epoch_daily.csv',chunksize=100000):parts.append(chunk.loc[chunk.vt_symbol.isin(symbols)])
 physical=pd.concat(parts,ignore_index=True);mapping=pd.read_csv(DATA/'mapping.csv');mapping['date']=pd.to_datetime(mapping.date).dt.normalize();mapping=mapping.drop_duplicates(['date','product','exchange'])
 episodes=[];contexts={};dates={};coverage=[];event_rows=[]
 for i,g in enumerate(gates,1):
  close=g['source_week_closes'];ends=g['source_week_ends']
  if len(close)!=11 or len(ends)!=11 or ends[-1]!=g['week_end'] or ends[-2]!=g['previous_week_end']:raise ValueError('gate 11 accepted observation source inconsistent')
  for period in [5,10]:
   for k,v in [('current',sum(close[-period:])/period),('previous',sum(close[-period-1:-1])/period)]:
    if not math.isclose(g[f'ma{period}_{k}'],v,abs_tol=1e-7,rel_tol=1e-10):raise ValueError('gate MA source mismatch')
  want=(g['ma5_delta']<0 or g['ma10_delta']<0) if g['direction']=='long' else (g['ma5_delta']>0 or g['ma10_delta']>0)
  if not want:raise ValueError('selected event does not meet direction gate')
  exact,epoch=frozen.exact_epoch_bars(DATA/'daily.sqlite',physical,g['vt_symbol'],g['signal_date'],g['signal_date']);g['physical_epoch_id']=epoch
  price=float(exact.loc[exact.date.eq(pd.Timestamp(g['signal_date'])),'close'].iloc[0]);prod=re.sub(r'\d+(?=\.)','',g['vt_symbol'])
  row=dict(open_trade_id=g['event_id'],close_trade_id='internal_render_anchor_only',lot_id='none',lot_count=0,vt_symbol=g['vt_symbol'],product=prod,direction=g['direction'],entry_date=g['signal_date'],exit_date=g['signal_date'],entry_price=price,exit_price=price,weighted_exit_price=price,price_change_pct=np.nan,price_change_label='N/A',volume=np.nan,realized_pnl=np.nan,r_multiple=np.nan,selection_basis='blocked signal event; not a trade',holding_calendar_days=0,exit_reason='not_executed',signal=g['signal'],profit_r_threshold=np.nan,loss_r_threshold=np.nan,result_rank=i,result_type='blocked_'+g['direction'],is_tail=0,draw_intraday=0)
  context,intraday=canonical_context(renderer,SimpleNamespace(**row),mapping,exact);contexts[g['event_id']]=context;dates[g['event_id']]=intraday
  c=dict(event_id=g['event_id'],real_history_start=str(exact.date.min().date()),real_history_end=str(exact.date.max().date()),real_history_rows=len(exact),signal_pre_real_bars=int(exact.date.lt(pd.Timestamp(g['signal_date'])).sum()),signal_post_real_bars=int(exact.date.gt(pd.Timestamp(g['signal_date'])).sum()),daily_pre_requested=300,daily_post_requested=50,listing_truncated_pre=bool(exact.date.lt(pd.Timestamp(g['signal_date'])).sum()<300),post_history_truncated=bool(exact.date.gt(pd.Timestamp(g['signal_date'])).sum()<50),proxy_days=0,physical_epoch_id=epoch)
  coverage.append(c);label,cands,anchors,trades=baseline[g['direction']];b=baseline_match(g,cands,anchors,trades,label);event_rows.append(dict(gate=g,baseline=b,price=price,coverage=c));episodes.append(row)
 records,manifest=renderer._records(pd.DataFrame(episodes),contexts,dates,pd.DataFrame(columns=['vt_symbol','bar_datetime','trading_day','open','high','low','close','volume']))
 cleaned=[]
 for record,event in zip(records,event_rows):
  g=event['gate'];record=event_metadata(record,g,event['baseline'],event['price']);m=record['meta'];xs=dict(zip(record['daily']['date'],record['daily']['x']));ma_dates=[g['previous_week_end'],g['week_end']]
  if any(d not in xs for d in ma_dates):raise ValueError('actual accepted week outside displayed exact day dates')
  m['strategy_ma']=dict(dates=ma_dates,x=[xs[d] for d in ma_dates],ma5=[g['ma5_previous'],g['ma5_current']],ma10=[g['ma10_previous'],g['ma10_current']]);m['coverage']=event['coverage'];m['ma_warmup_null_counts']={period:{f'ma{n}':sum(v is None or (isinstance(v,float) and not math.isfinite(v)) for v in record[period][f'ma{n}']) for n in [5,10,20,40]} for period in ['daily','weekly','monthly','day10','day30']};cleaned.append(record)
 records=renderer._json_safe(cleaned)
 summary=dict(schema='stage003_blocked_signal_canonical_recap_v1',episode_scope='all',rank_basis='signal_date',page_title='Stage002 双向MA斜率门：35个被拦候选复盘（未成交）',coverage_note='20个多头、15个空头；只含门控前计划手数>0而被实际归零的候选。没有真实开平仓、持仓区间、PnL或R。',footer_scope='35个信号事件，非35笔成交。上一版本匹配只作独立事实对照，不能当作新C盈亏。',source_label='冻结离线研究，非生产资格',source_version='weekly_symmetric_ma_slope_gate_v1 / Stage002 C / 19品种 / 2020—2026-10-29',source_warning='点线MA5/MA10是策略实际接受观察周的前/本周门控值；自然周图MA仅参考，可能因缺周/观察规则不同而不同。MA40未参与策略。精确同物理epoch历史不足和MA预热空值保留；15分钟无缓存，未下载。',source_head=SOURCE_HEAD,run_source_head=json.loads((RUN/'preflight.json').read_text())['head'],blocked_event_count=35,long_blocked_count=20,short_blocked_count=15,closed_trade_count=0,unexecuted_event_count=35,raw_gate_rows=dict(short=len(short),long=len(long)),zero_or_unapplied_excluded=dict(short=len(short)-15,long=len(long)-20),baseline_matches={k:sum(x['meta']['baseline_actual']['status']==k for x in records) for k in ['actual_open_matched','no_candidate','candidate_not_opened','candidate_opened_no_actual_fill']},frozen_source_metrics=json.loads((RUN/'metrics.json').read_text()),frozen_summary=pd.read_csv(LINE/'artifacts/stage002_comparison/summary.csv').to_dict('records'),source_delivery_verified_files=verified,financial_replays=0,market_downloads=0,production_accesses=0,strategy_changes=0,default_periods=['day30','daily'],periods=['day30','day10','monthly','weekly','daily','intraday'],intraday_status='unavailable_no_download',chart_week_basis='natural W-FRI reference vs separately marked accepted strategy observations',context_proxy_days=0,canonical_renderer=str(RENDERER),canonical_renderer_sha256=hashes[str(RENDERER)])
 output.mkdir(parents=True,exist_ok=resume_incomplete)
 _write_json(output/'records.json',records,renderer);_write_json(output/'summary.json',summary,renderer)
 manifest=pd.DataFrame([{**r['meta'],**{f'{p}_bars':len(r[p]['x']) for p in ['daily','weekly','monthly','day10','day30','intraday']}} for r in records]);manifest.to_csv(output/'chart_manifest.csv',index=False)
 pd.DataFrame(coverage).to_csv(output/'exact_epoch_coverage.csv',index=False);pd.DataFrame([dict(event_id=x['gate']['event_id'],**x['baseline']) for x in event_rows]).to_csv(output/'previous_version_actual_open_matches.csv',index=False)
 _write_json(output/'source_hashes.json',hashes,renderer);(output/'index.html').write_text(canonical_html(renderer,records,summary))
 # Isolated script parse verifies syntax without opening account/network runtimes.
 scripts=re.findall(r'<script[^>]*>(.*?)</script>',(output/'index.html').read_text(),flags=re.S)
 for i,script in enumerate(scripts):
  p=output/f'embedded_script_{i}.js';p.write_text(script);subprocess.run(['/Users/mac/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node','--check',str(p)],check=True,capture_output=True)
 verify_hashes(hashes);verify_hashes(d['files_sha256'])
 artifacts={str(p.relative_to(output)):sha(p) for p in sorted(output.rglob('*')) if p.is_file()};_write_json(output/'delivery_manifest.json',dict(schema='stage003_display_delivery_v1',files_sha256=artifacts,self_hash_excluded=True,source_files_unchanged=True,source3141_unchanged=True,javascript_parse='PASS',financial_replays=0,market_downloads=0,production_accesses=0),renderer)
 return summary

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=OUTPUT);ap.add_argument('--resume-incomplete',action='store_true');a=ap.parse_args();r=build(a.output,a.resume_incomplete);print(json.dumps({k:r[k] for k in ['blocked_event_count','long_blocked_count','short_blocked_count','baseline_matches','source_delivery_verified_files']},ensure_ascii=False));print(str(a.output/'index.html'))
if __name__=='__main__':main()
