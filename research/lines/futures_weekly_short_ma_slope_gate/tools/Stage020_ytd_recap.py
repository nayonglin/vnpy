"""Identity-closed annual trade adapter for the unchanged canonical renderer.

All OHLC, aggregation, chart layout, period controls and zoom are provided by
the canonical Stage038 functions. Only local frozen inputs and semantic facts
are supplied here; no strategy, market client or production module is imported.
"""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse,ast,base64,copy,hashlib,html,importlib.util,json,math,re
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[4]
LINE=ROOT/'research/lines/futures_weekly_short_ma_slope_gate'
RUN=Path('/Users/mac/.codex/worktrees/weekly-short-ma-slope-20261029/fian/research/lines/futures_weekly_short_ma_slope_gate/outputs/stage014_C_20260101_attempt001')
DATA=RUN.parent/'data_stage014_20261030/data_approved'
YTD=LINE/'artifacts/stage019_2026_ytd'
OUTPUT=LINE/'artifacts/stage020_2026_ytd_recap'
LIB=ROOT/'research/lines/futures_weekly_formal_no_half_r/tools/stage031_canonical_recap.py'
RENDERER=ROOT/'research/lines/futures_trend_winner_trade_forensics/tools/stage038_c9_15w_big_winner_multiscale_html.py'
MINUTES=LINE/'stages/Stage020_review_qualified_15m_warmup.csv'
MINUTE_RECEIPT=LINE/'stages/Stage020_review_minute_qualification_v2.json'
MINUTE_QUALIFICATION_SHA='1974601517b2496dc6f5793ac9fd7347254c82f6933de3380e9e2ad891c54677'
SOURCE_PROFILE='stage019_C_R150_20260101'
CUTOFF='2026-10-30'

def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb')as stream:
  for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
 return h.hexdigest()

def require(value,reason):
 if not value:raise ValueError(reason)

def near(a,b,label):require(np.allclose(a,b,rtol=1e-10,atol=1e-6,equal_nan=False),label)

def library():
 spec=importlib.util.spec_from_file_location('canonical_recap_pure_loader',LIB)
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def require_output(path):
 path=Path(path).resolve()
 require(path==OUTPUT.resolve()or(path.parent==OUTPUT.parent.resolve()and re.fullmatch(OUTPUT.name+r'_attempt[0-9]{3}',path.name)),
  'Only a new Stage020 output in this research line is allowed')
 require(not path.exists(),'Preserve existing output; use a new explicit attempt')

def verify_delivery(path=YTD/'delivery_receipt.json'):
 path=Path(path);r=json.loads(path.read_text())
 require(r.get('schema')=='Stage019.annual-window-delivery.v1'and r.get('accepted')is True
  and r.get('method')=='verified_existing_fresh_engine_window'and r.get('source_window_requested_start')=='2026-01-01'
  and r.get('actual_dates')==['2026-01-05',CUTOFF]and r.get('trading_days')==198,'Wrong or incomplete annual delivery')
 pins=r.get('delivery_files_sha256');require(isinstance(pins,dict)and {'summary.json','daily.csv','trades.csv','source_manifest.json'}<=set(pins),'Annual source pins incomplete')
 for name,want in pins.items():
  require(Path(name).name==name and sha(path.parent/name)==want,'Annual delivery bytes changed:'+name)
 review=Path(r['independent_review_path']);require(sha(review)==r['independent_review_sha256'],'Annual review changed')
 accepted=json.loads(review.read_text());require(accepted.get('accepted')is True and not accepted.get('failures'),'Annual review not accepted')
 require(Path(accepted['source_run']).resolve()==RUN.resolve(),'Annual source run mismatch')
 return r,accepted

def verify_market_inputs(inputs,data):
 require(isinstance(inputs,dict),'Original market input pins missing')
 for name in ['daily.sqlite','physical_epoch_daily.csv','metadata.csv','mapping.csv','receipt.json']:
  path=Path(data)/name;require(str(path)in inputs and sha(path)==inputs[str(path)],'Original market input changed:'+name)

def verify_minute_source(path,receipt,*,expected_receipt_sha256=MINUTE_QUALIFICATION_SHA):
 require(sha(receipt)==expected_receipt_sha256,'Minute qualification receipt changed')
 r=json.loads(Path(receipt).read_text())
 require(r.get('accepted')is True and not r.get('failures')and Path(r.get('qualified_csv','')).resolve()==Path(path).resolve(),'Minute source not admitted')
 require(sha(path)==r.get('qualified_csv_sha256'),'Admitted minute CSV changed')
 pins=r.get('input_files_sha256');require(isinstance(pins,dict),'Minute source pins missing')
 for file,want in pins.items():require(sha(file)==want,'Minute source input changed:'+file)
 return pins

def normalize_rounds(rounds,fills,sizes,slippages,rates):
 """Normalize the independently exported flat-to-flat groups, retaining NET PnL."""
 require(not fills.trade_id.duplicated().any(),'Duplicate fill ID')
 def number(value):return int(str(value).rsplit('.',1)[-1])
 used=set();rows=[]
 for item in rounds.itertuples(index=False):
  ids=ast.literal_eval(item.trade_ids)if isinstance(item.trade_ids,str)else list(item.trade_ids)
  require(isinstance(ids,list)and len(ids)==len(set(ids))and not used.intersection(ids),'Round fill IDs overlap')
  part=fills.loc[fills.trade_id.isin(ids)].copy();require(len(part)==len(ids)and len(part)>=2,'Incomplete closed round')
  part=part.assign(_order=part.trade_id.map(number)).sort_values('_order')
  require(part.vt_symbol.eq(item.vt_symbol).all(),'Mixed contracts in round')
  opens=part.loc[part.offset.eq('开')];closes=part.loc[part.offset.eq('平')]
  require(len(opens)+len(closes)==len(part)and len(opens)>0 and len(closes)>0,'Open round lacks final close')
  require(part.iloc[0].offset=='开'and part.iloc[-1].offset=='平','Round endpoints invalid')
  require(opens.direction.nunique()==closes.direction.nunique()==1 and opens.direction.iloc[0]!=closes.direction.iloc[0],'Fill direction invalid')
  volume=float(opens.volume.sum());require(volume>0,'Nonpositive volume');near(volume,closes.volume.sum(),'Residual position cannot be dropped')
  symbol=str(item.vt_symbol);size=float(sizes[symbol]);slip=float(slippages[symbol]);rate=float(rates[symbol])
  direction='long'if opens.direction.iloc[0]=='多'else'short';entry=float(np.average(opens.price,weights=opens.volume));exit_=float(np.average(closes.price,weights=closes.volume))
  gross=(exit_-entry)*volume*size*(1 if direction=='long'else-1)
  cost=float((part.volume*size*(slip+part.price*rate)).sum());net=gross-cost;near(net,item.net_pnl,'Frozen net PnL differs from fills/costs')
  require(str(opens.trading_date.iloc[0])[:10]==str(item.opened_on)[:10]and str(closes.trading_date.iloc[-1])[:10]==str(item.closed_on)[:10],'Round trading dates mismatch')
  rows.append(dict(role='C_R150',vt_symbol=symbol,direction=direction,entry_trade_id=part.trade_id.iloc[0],exit_trade_id=part.trade_id.iloc[-1],
   entry_trading_date=str(opens.trading_date.iloc[0])[:10],exit_trading_date=str(closes.trading_date.iloc[-1])[:10],
   entry_execution_datetime=str(opens.datetime.iloc[0]),exit_execution_datetime=str(closes.datetime.iloc[-1]),
   opened_volume=volume,fill_count=len(part),net_pnl=net,gross_pnl=gross,cost=cost,price_move_pct=(exit_/entry-1)*100))
  used.update(ids)
 require(used==set(fills.trade_id),'Residual or unpaired source fills cannot be dropped')
 return pd.DataFrame(rows)

def make_context(renderer,row,mapping,exact):
 env=renderer._context_daily.__globals__
 env['_contract_daily']=lambda symbol:exact.copy()if symbol==row.vt_symbol else(_ for _ in()).throw(ValueError('Proxy context forbidden'))
 env['_daily_from_existing_minute_files']=lambda *a,**k:pd.DataFrame()
 local=mapping.copy();local['main_contract_vt']=row.vt_symbol
 daily,minute_days=renderer._context_daily(row,local,{},allow_daily_download=False,allow_noncritical_daily_gaps=True,data_end=pd.Timestamp(CUTOFF))
 held=set(mapping.loc[mapping['product'].astype(str).str.lower().eq(row.product.split('.')[0].lower())&mapping.exchange.eq(row.vt_symbol.split('.')[1])&mapping.date.between(pd.Timestamp(row.entry_date),pd.Timestamp(row.exit_date)),'date'])
 require(not(held-set(daily.date)),'Exact held-period daily bars missing')
 require(not daily.context_fallback.any(),'Unexpected proxy data')
 return daily,minute_days

def minute_moving_averages(renderer,bars,mapping):
 """Use canonical MA math on hidden real bars, resetting after missing days."""
 pieces=[]
 for symbol,group in bars.groupby('vt_symbol',sort=False):
  product,exchange=re.match(r'([A-Za-z]+)[0-9]+\.([A-Z]+)$',symbol).groups()
  cal=sorted(set(mapping.loc[mapping['product'].str.lower().eq(product.lower())&mapping.exchange.eq(exchange),'date']))
  index={pd.Timestamp(d).normalize():i for i,d in enumerate(cal)}
  group=group.sort_values(['trading_day','bar_datetime']).copy();segment=[];prior=None;current=0
  for day in group.trading_day:
   day=pd.Timestamp(day).normalize();require(day in index,'Minute day outside frozen product calendar')
   if prior is not None and day!=prior and index[day]!=index[prior]+1:current+=1
   segment.append(current);prior=day
  group['_segment']=segment
  for _,part in group.groupby('_segment',sort=False):pieces.append(renderer._add_moving_averages(part))
 return pd.concat(pieces,ignore_index=True)if pieces else bars.copy()

FACTS_HOOK=r'''<script>
(function(){const original=Plotly.react;Plotly.react=function(target,traces,layout,config){
if(target==='chart'&&typeof filtered!=='undefined'&&filtered[active]){
 const m=filtered[active].meta,f=v=>Number(v).toLocaleString('zh-CN',{maximumFractionDigits:4});
 const field=document.getElementById('tradeFacts');
 if(field)field.innerHTML=`<b>${m.direction==='long'?'多头':'空头'} · ${f(m.volume)}手</b>　开仓 ${m.entry_execution_datetime} @ ${f(m.entry_price)}　→　平仓 ${m.exit_execution_datetime} @ ${f(m.exit_price)}<br>信号：${m.signal}；退出：${m.exit_reason}；本轮滑点及手续费 ${f(m.round_cost)}元。<br>精确交割epoch：${m.physical_epoch_id}；日K前史 ${m.exact_pre_bars}/300、后史 ${m.exact_post_bars}/50（按真实上市历史与10月30日截断）。<br>${m.minute_disclosure}；缺交易日后分钟MA重新预热；可见MA40空值 ${m.intraday_ma40_warmup_missing_bars} 根。`;
}return original.call(this,target,traces,layout,config);};})();
</script>'''

def page(renderer,records,summary):
 result=renderer._html(records,summary)
 for option in ['<option value="profit_tail">盈利尾部</option>','<option value="loss_tail">亏损尾部</option>']:
  require(result.count(option)==1,'Canonical result selector changed');result=result.replace(option,'')
 result=result.replace('当前交易无15分钟数据，已跳过15分钟K；切到已补数交易时恢复。','当前交易没有已核准的15分钟数据，已跳过；本页不下载或补造。')
 image=base64.b64encode((YTD/'2026_ytd_nav.png').read_bytes()).decode()
 extra='<details class="note"><summary>年度净值与回撤｜15万元交易资金起点</summary><img style="width:100%;height:auto" alt="2026年度交易净值与回撤" src="data:image/png;base64,'+image+'"></details><div id="tradeFacts" class="note"></div>'
 require(result.count('<div class="toolbar">')==1,'Canonical toolbar changed');result=result.replace('<div class="toolbar">',extra+'<div class="toolbar">',1)
 result,count=re.subn(r'</div><script>(\s*const records=)',lambda m:'</div>'+FACTS_HOOK+'<script>'+m[1],result,count=1)
 require(count==1,'Canonical script boundary changed');return result

def build(output=OUTPUT):
 output=Path(output);require_output(output);delivery,review=verify_delivery()
 financial_review=LINE/'stages/stage014_independent_receipts/2026-01-01_C.json';old=json.loads(financial_review.read_text())
 source_pins=old['source_files_sha256']
 for p,want in source_pins.items():require(sha(p)==want,'Frozen source changed:'+p)
 require(MINUTES.is_file()and MINUTE_RECEIPT.is_file(),'Admitted local minute receipt required')
 verify_market_inputs(json.loads((RUN/'input_manifest.json').read_text()),DATA)
 minute_pins=verify_minute_source(MINUTES,MINUTE_RECEIPT)
 lib=library();renderer=lib.load_canonical_renderer(RENDERER)
 fills=pd.read_csv(RUN/'trades.csv');rounds_path=LINE/'stages/Stage019_review_closed_rounds.csv'
 require(sha(rounds_path)==review['audit_evidence_sha256'][str(rounds_path)],'Frozen closed-round export changed')
 eff=json.loads((RUN/'effective_parameters.json').read_text());rounds=normalize_rounds(pd.read_csv(rounds_path),fills,eff['sizes'],eff['slippages'],eff['rates'])
 episodes,_=lib.episodes_from_frozen(rounds,pd.DataFrame(columns=['role']),fills,'C_R150')
 require(len(episodes)==18 and len(fills)==36,'Wrong annual round count');near(episodes.realized_pnl.sum(),22380,'Annual net PnL')
 episodes=episodes.sort_values(['entry_date','open_trade_id']).reset_index(drop=True);episodes['result_rank']=np.arange(1,len(episodes)+1)
 mapping=pd.read_csv(DATA/'mapping.csv');mapping['date']=pd.to_datetime(mapping.date).dt.normalize()
 physical=pd.read_csv(DATA/'physical_epoch_daily.csv');daily={};intraday={};coverage={}
 minute=pd.read_csv(MINUTES);minute['bar_datetime']=pd.to_datetime(minute.bar_datetime);minute['trading_day']=pd.to_datetime(minute.trading_day).dt.normalize()
 require(not minute.duplicated(['vt_symbol','bar_datetime']).any(),'Duplicate admitted minutes')
 minute_ma=minute_moving_averages(renderer,minute,mapping)
 for i,row in enumerate(episodes.itertuples(index=False)):
  exact,epoch=lib.exact_epoch_bars(DATA/'daily.sqlite',physical,row.vt_symbol,row.entry_date,row.exit_date)
  exact=exact.loc[exact.date.le(pd.Timestamp(CUTOFF))].copy()
  daily[row.open_trade_id],intraday[row.open_trade_id]=make_context(renderer,row,mapping,exact)
  has_minute=bool(((minute.vt_symbol==row.vt_symbol)&minute.trading_day.isin(intraday[row.open_trade_id])).any())
  episodes.loc[i,'draw_intraday']=int(has_minute);episodes.loc[i,'physical_epoch_id']=epoch
  coverage[row.open_trade_id]=dict(pre=int(exact.date.lt(pd.Timestamp(row.entry_date)).sum()),post=int(exact.date.gt(pd.Timestamp(row.exit_date)).sum()),first=str(exact.date.min().date()),last=str(exact.date.max().date()))
 records,manifest=lib.make_records(renderer,episodes,daily,intraday)if minute.empty else renderer._records(episodes,daily,intraday,minute)
 # Reuse canonical candle/period construction, but retain the true hidden minute
 # history and reset at rejected days instead of rolling across a cache hole.
 anchors=pd.read_csv(RUN/'execution_anchor_requests.csv');risk=pd.read_csv(RUN/'entry_risk.csv')
 for record in records:
  m=record['meta'];row=rounds.loc[rounds.entry_trade_id.eq(m['open_trade_id'])].iloc[0]
  c=coverage[m['open_trade_id']];m.update(physical_epoch_id=episodes.loc[episodes.open_trade_id.eq(m['open_trade_id']),'physical_epoch_id'].iloc[0],
   entry_execution_datetime=row.entry_execution_datetime,exit_execution_datetime=row.exit_execution_datetime,round_cost=float(row.cost),gross_pnl=float(row.gross_pnl),
   exact_pre_bars=c['pre'],exact_post_bars=c['post'],exact_history_start=c['first'],exact_history_end=c['last'],r_multiple=None)
  entry=fills.loc[fills.trade_id.eq(m['open_trade_id'])].iloc[0];signals=risk.loc[risk.signal_order_id.astype(str).eq(str(entry.order_id)),'signal'].drop_duplicates()
  m['signal']=str(signals.iloc[0])if len(signals)==1 else'冻结源未封存唯一入场信号'
  selected=minute_ma.loc[minute_ma.vt_symbol.eq(m['vt_symbol'])].set_index('bar_datetime')
  for period in (5,10,20,40):record['intraday']['ma'+str(period)]=[None if pd.isna(selected.loc[pd.Timestamp(t),'ma'+str(period)])else float(selected.loc[pd.Timestamp(t),'ma'+str(period)])for t in record['intraday']['datetime']]
  m['intraday_ma40_warmup_missing_bars']=sum(v is None for v in record['intraday']['ma40'])
  m['minute_disclosure']=('仅显示已核准完整日的本地15分钟；部分交易日缺失'if m['missing_15m_dates']else'可见窗口本地15分钟已核齐')if m['draw_intraday']else'本交易窗口无已核准可绘制的15分钟；已有其他缓存不作替代'
  m['intraday_selection']=m['minute_disclosure']
  m['ma_warmup_null_counts']={period:{'ma'+str(n):sum(v is None or(not pd.notna(v))for v in record[period]['ma'+str(n)])for n in (5,10,20,40)}for period in ('daily','weekly','monthly','day10','day30','intraday')}
  # Complete-day admission means passing 15m to the canonical builder must not
  # change even a single approved daily OHLCV value.
  exact=daily[m['open_trade_id']].set_index('date')
  for col in ('open','high','low','close','volume'):
   near(record['daily'][col],[exact.loc[pd.Timestamp(d),col]for d in record['daily']['date']],'Minute data changed approved daily '+col)
 manifest['physical_epoch_id']=[r['meta']['physical_epoch_id']for r in records]
 manifest['exact_pre_bars']=[r['meta']['exact_pre_bars']for r in records];manifest['exact_post_bars']=[r['meta']['exact_post_bars']for r in records]
 manifest['missing_15m_dates']=[json.dumps(r['meta']['missing_15m_dates'])for r in records]
 frozen=json.loads((YTD/'summary.json').read_text())
 summary=dict(source_profile=SOURCE_PROFILE,episode_scope='all',rank_basis='realized_pnl',
  page_title='2026年19品种周线 C_R150｜18轮逐笔复盘（离线文件）',source_label='Stage019已核年度独立窗口',source_version='Stage014 C_R150 · 2026-01-01—2026-10-30',
  coverage_note='全部18轮可选30日、10日、月、周、日K；15分钟只使用本地逐日/逐桶核准的缓存，缺日不补造。未满300日前史、50日后史与MA40预热的真实上市/截止边界见逐笔说明。',
  source_warning='研究模拟：15万交易资金＋15万场外备用金；期末交易权益173100，交易净利22380，补资720；手续费0、滑点2930。非已部署实盘；不模拟人工转账延迟。',
  footer_scope='18轮完整交易、36笔成交，8盈10亏；净PnL已扣全部成本；R未有封存口径保持N/A；本页没有补齐或代理K线。',
  closed_rounds=18,source_fills=36,profits=8,losses=10,flat=0,net_pnl=22380.,gross_pnl=float(rounds.gross_pnl.sum()),cost=float(rounds.cost.sum()),
  residual_positions=0,minute_episodes=sum(int(r['meta']['draw_intraday'])for r in records),minute_available_complete_for_all=False,
  frozen_backtest_metrics=frozen,financial_replays=0,market_downloads=0,production_accesses=0,ctp_connected=False,http_service_started=False)
 html_text=page(renderer,records,summary)
 require(not re.search(r'<script[^>]+src\s*=',html_text,re.I),'External script dependency forbidden')
 output.mkdir(parents=True)
 safe=renderer._json_safe
 for name,obj in [('records.json',records),('summary.json',summary)]:
  (output/name).write_text(json.dumps(safe(obj),ensure_ascii=False,indent=2,allow_nan=False))
 manifest.to_csv(output/'chart_manifest.csv',index=False);rounds.to_csv(output/'closed_rounds.csv',index=False)
 (output/'index.html').write_text(html_text)
 scripts=re.findall(r'<script[^>]*>([\s\S]*?)</script>',html_text)
 for i,script in enumerate(scripts):(output/f'embedded_script_{i}.js').write_text(script)
 source_map={**source_pins,**minute_pins,str(YTD/'delivery_receipt.json'):sha(YTD/'delivery_receipt.json'),str(YTD/'summary.json'):sha(YTD/'summary.json'),
  str(YTD/'2026_ytd_nav.png'):sha(YTD/'2026_ytd_nav.png'),str(rounds_path):sha(rounds_path),str(MINUTES):sha(MINUTES),str(MINUTE_RECEIPT):sha(MINUTE_RECEIPT),
  str(RENDERER):sha(RENDERER),str(LIB):sha(LIB),str(Path(__file__)):sha(__file__)}
 for name in ['daily.sqlite','physical_epoch_daily.csv','metadata.csv','mapping.csv','receipt.json']:source_map[str(DATA/name)]=sha(DATA/name)
 receipt=dict(schema='Stage020.canonical-annual-recap-generation.v1',generated_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),source_files_sha256=source_map,
  output_files_sha256={p.name:sha(p)for p in output.iterdir()if p.is_file()},source_profile=SOURCE_PROFILE,completed_rounds=18,source_fills=36,
  full_canonical_source_unchanged=True,canonical_functions_copied=False,market_downloads=0,financial_replays=0,production_accesses=0,status='PENDING_BROWSER_AND_INDEPENDENT_ACCEPTANCE')
 (output/'generation_manifest.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
 return dict(output=str(output),completed_rounds=18,net_pnl=22380,minute_episodes=summary['minute_episodes'],html_bytes=(output/'index.html').stat().st_size)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source-profile',choices=[SOURCE_PROFILE],default=SOURCE_PROFILE);p.add_argument('--output',type=Path,default=OUTPUT);args=p.parse_args()
 print(json.dumps(build(args.output),ensure_ascii=False))
