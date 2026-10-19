"""Read-only calendar MTM attribution of one hash-closed run; no strategy replay."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,html,json
import numpy as np
import pandas as pd

LINE=Path(__file__).resolve().parents[1]
SOURCE=LINE/'outputs/run_20261018_lifecycle_unlimited_v2'
OUT=LINE/'outputs/attribution_2024_20261019_v1'
YEAR='2024'

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()

def main():
 if OUT.exists():raise FileExistsError(OUT)
 manifest=json.loads((SOURCE/'manifest.json').read_text())
 required=['daily.csv','trades.csv','closed_episodes.csv','contract_metadata.csv','market_daily.csv','account_snapshots.csv','summary.json']
 for name in required:assert sha(SOURCE/name)==manifest['hashes'][name],name
 d=pd.read_csv(SOURCE/'daily.csv');year=d[d.date.str.startswith(YEAR)].copy();baseline=d[d.date.lt('2024-01-01')].iloc[-1]
 t=pd.read_csv(SOURCE/'trades.csv').fillna('');t['_sequence']=t.trade_id.str.rsplit('.',n=1).str[-1].astype(int);t=t.sort_values(['date','_sequence'])
 meta=pd.read_csv(SOURCE/'contract_metadata.csv').set_index('vt_symbol');episodes=pd.read_csv(SOURCE/'closed_episodes.csv');life=episodes.set_index('entry_trade_id').to_dict('index')
 opens=t[t.offset.eq('open')].set_index('trade_id').to_dict('index');lots={};active={}
 def new_lot(trade):
  info=opens[trade['trade_id']];vt=trade['vt_symbol'];sgn=1 if trade['direction']=='long' else -1
  assert trade['trade_id'] not in lots and trade['volume']==1
  lot={'id':trade['trade_id'],'vt':vt,'sign':sgn,'size':float(meta.loc[vt,'size']),'entry':info,'last_mark':None}
  lots[lot['id']]=lot;return lot
 for trade in t[t.date.lt('2024-01-01')].to_dict('records'):
  vt=trade['vt_symbol']
  if trade['offset']=='open':assert vt not in active;active[vt]=new_lot(trade)
  else:
   old=active.pop(vt);assert old['sign']==(-1 if trade['direction']=='long' else 1)
 start_ids={lot['id'] for lot in active.values()}
 market=pd.read_csv(SOURCE/'market_daily.csv',usecols=['date','vt_symbol','open','high','low','close','volume','quote_class','execution_only'])
 initial_bars=market[market.vt_symbol.isin(active)&market.date.le(baseline.date)].sort_values('date').groupby('vt_symbol').tail(1)
 for bar in initial_bars.to_dict('records'):active[bar['vt_symbol']]['last_mark']=float(bar['close'])
 assert all(lot['last_mark'] is not None for lot in active.values())
 def net_unrealized(lot):
  e=lot['entry'];return (lot['last_mark']-float(e['price']))*lot['sign']*lot['size']-float(e['commission'])-float(e['slippage'])
 start_unrealized=sum(net_unrealized(v) for v in active.values())
 bars={(b.date,b.vt_symbol):b for b in market[market.date.str.startswith(YEAR)].itertuples(index=False)}
 fills={date:g.to_dict('records') for date,g in t[t.date.str.startswith(YEAR)].groupby('date',sort=False)}
 snapshots=pd.read_csv(SOURCE/'account_snapshots.csv').set_index('date');assert {vt:int(l['sign']) for vt,l in active.items()}==json.loads(snapshots.loc[baseline.date,'positions'])
 rows=[];daily_proof=[]
 for day in year.itertuples(index=False):
  book={}
  def row_for(lot,start_qty=0):
   key=lot['id']
   if key not in book:
    b=bars.get((day.date,lot['vt']));close=float(b.close) if b is not None else lot['last_mark'];assert close is not None
    book[key]={'date':day.date,'entry_trade_id':key,'vt_symbol':lot['vt'],'direction':'long' if lot['sign']>0 else 'short','size':lot['size'],'start_qty':start_qty,'end_qty':start_qty,'previous_mark':lot['last_mark'],'close_mark':close,'holding_pnl':0.,'trading_pnl':0.,'commission':0.,'slippage':0.,'missing_held_bar':int(b is None and start_qty>0),'fills':[]}
   return book[key]
  for lot in active.values():
   row=row_for(lot,1);row['holding_pnl']=(row['close_mark']-lot['last_mark'])*lot['sign']*lot['size']
  for trade in fills.get(day.date,[]):
   vt=trade['vt_symbol'];bar=bars.get((day.date,vt));assert bar is not None and float(bar.volume)>=1 and abs(float(bar.open)-float(trade['price']))<1e-8
   if trade['offset']=='open':
    assert vt not in active;lot=new_lot(trade);active[vt]=lot;row=row_for(lot);row['end_qty']=1
    row['trading_pnl']+=(row['close_mark']-float(trade['price']))*lot['sign']*lot['size']
   else:
    lot=active.pop(vt);assert lot['sign']==(-1 if trade['direction']=='long' else 1);row=row_for(lot);row['end_qty']=0
    row['trading_pnl']+=(float(trade['price'])-row['close_mark'])*lot['sign']*lot['size']
   row['commission']+=float(trade['commission']);row['slippage']+=float(trade['slippage']);row['fills'].append(trade['trade_id'])
  for lot in active.values():lot['last_mark']=row_for(lot)['close_mark']
  assert {vt:int(l['sign']) for vt,l in active.items()}==json.loads(snapshots.loc[day.date,'positions']),day.date
  sums={key:sum(r[key] for r in book.values()) for key in ['holding_pnl','trading_pnl','commission','slippage']}
  sums['net_pnl']=sums['holding_pnl']+sums['trading_pnl']-sums['commission']-sums['slippage']
  for key,value in sums.items():assert abs(value-float(getattr(day,key)))<1e-5,(day.date,key,value,getattr(day,key))
  for row in book.values():
   row['gross_pnl']=row['holding_pnl']+row['trading_pnl'];row['net_pnl']=row['gross_pnl']-row['commission']-row['slippage'];row['fills']='|'.join(row['fills']);rows.append(row)
  daily_proof.append({'date':day.date,**sums,'source_net_pnl':day.net_pnl,'source_equity':day.equity})
 end_unrealized=sum(net_unrealized(v) for v in active.values());end_ids={lot['id'] for lot in active.values()}
 detail=pd.DataFrame(rows);group=detail.groupby('entry_trade_id',sort=False)
 yearly=group[['holding_pnl','trading_pnl','gross_pnl','commission','slippage','net_pnl','missing_held_bar']].sum().rename(columns={'net_pnl':'pnl_2024_net'})
 records=[]
 for entry_id,row in yearly.iterrows():
  lot=lots[entry_id];e=lot['entry'];closed=life.get(entry_id,{});vt=lot['vt'];end_trade=t[t.trade_id.eq(closed.get('exit_trade_id',''))]
  records.append({'entry_trade_id':entry_id,'vt_symbol':vt,'product':meta.loc[vt,'product_vt_symbol'],'product_class':meta.loc[vt,'product_class'],'direction':'long' if lot['sign']>0 else 'short','signal':e['signal'],'signal_date':str(e['signal_datetime'])[:10],'entry_date':e['date'],'exit_date':closed.get('exit_date',''),'entry_price':float(e['price']),'exit_price':closed.get('exit_price',None),'size':lot['size'],'pnl_2024_net':row['pnl_2024_net'],'gross_2024':row['gross_pnl'],'commission_2024':row['commission'],'slippage_2024':row['slippage'],'lifetime_net_pnl':closed.get('net_pnl',None),'carry_in':entry_id in start_ids,'carry_out':entry_id in end_ids,'missing_held_bar_days':int(row['missing_held_bar']),'exit_reason':str(end_trade.iloc[0]['exit_reason']) if len(end_trade) else ''})
 attributed=pd.DataFrame(records).sort_values('pnl_2024_net').reset_index(drop=True)
 total=float(year.net_pnl.sum());assert abs(attributed.pnl_2024_net.sum()-total)<1e-5
 closed_2024=episodes[episodes.exit_date.str.startswith(YEAR)].copy();closed_total=float(closed_2024.net_pnl.sum())
 assert abs(closed_total+end_unrealized-start_unrealized-total)<1e-5
 assert abs(float(year.equity.iloc[-1])-float(baseline.equity)-total)<1e-5
 def aggregate(keys):return attributed.groupby(keys,dropna=False).agg(episodes=('entry_trade_id','count'),net_pnl_2024=('pnl_2024_net','sum'),gross_pnl_2024=('gross_2024','sum'),commission=('commission_2024','sum'),slippage=('slippage_2024','sum')).sort_values('net_pnl_2024').reset_index()
 products=aggregate(['product','product_class']);signals=aggregate(['direction','signal']);families=aggregate(['product_class'])
 monthly=year.assign(month=year.date.str[:7]).groupby('month')[['net_pnl','commission','slippage','trade_count']].sum().reset_index()
 top_ids=['BACKTESTING.5022','BACKTESTING.5023','BACKTESTING.5024'];top3=attributed[attributed.entry_trade_id.isin(top_ids)]
 top3_loss=float(top3.pnl_2024_net.sum());assert len(top3)==3
 summary={'status':'PASS_daily_MTM_reconciled','year':2024,'analysis_mode':'frozen_read_only_attribution','start_equity':float(baseline.equity),'end_equity':float(year.equity.iloc[-1]),'year_net_pnl':total,'year_return_pct':100*total/float(baseline.equity),'year_fills':int(year.trade_count.sum()),'episodes_with_2024_exposure':len(attributed),'closed_exit_2024_count':len(closed_2024),'closed_exit_2024_lifetime_net_pnl':closed_total,'start_open_net_unrealized':start_unrealized,'end_open_net_unrealized':end_unrealized,'net_unrealized_change':end_unrealized-start_unrealized,'top3_october_net_pnl':top3_loss,'top3_share_of_annual_net_loss_pct':100*top3_loss/total,'other_episodes_arithmetic_net':total-top3_loss,'commission':float(year.commission.sum()),'slippage':float(year.slippage.sum()),'gross_pnl':float(year.total_pnl.sum()),'source_run_id':manifest['run_id'],'source_manifest_sha256':sha(SOURCE/'manifest.json'),'source_files_sha256':{n:sha(SOURCE/n) for n in required},'generator_sha256':sha(Path(__file__)),'all_daily_components_reconciled':True,'all_daily_positions_reconciled':True,'strategy_rerun':False,'market_download':False,'production_access':False,'created_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),'warning':'Calendar MTM is not lifetime PnL of exits in 2024. Arithmetic exclusion is not a counterfactual strategy rerun. Daily approximation/intraday stop and supply filter disabled; static fees and metadata remain.'}
 OUT.mkdir(parents=True)
 for name,frame in [('daily_episode_mtm_2024.csv',detail),('episodes_2024_mtm.csv',attributed),('daily_2024_reconciliation.csv',pd.DataFrame(daily_proof)),('products_2024.csv',products),('signals_2024.csv',signals),('asset_classes_2024.csv',families),('monthly_2024.csv',monthly),('closed_exit_2024_lifetime.csv',closed_2024)]:frame.to_csv(OUT/name,index=False)
 def table(frame):return frame.to_html(index=False,float_format=lambda v:f'{v:,.2f}',escape=True,border=0)
 top3cols=['vt_symbol','direction','signal_date','entry_date','exit_date','entry_price','exit_price','pnl_2024_net','exit_reason']
 detailcols=['entry_trade_id','vt_symbol','direction','signal','signal_date','entry_date','exit_date','entry_price','exit_price','pnl_2024_net','lifetime_net_pnl','carry_in','carry_out','exit_reason']
 page='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>2024逐笔回撤归因</title><style>body{font:14px -apple-system,BlinkMacSystemFont,Arial,sans-serif;color:#26394a;max-width:1500px;margin:25px auto;padding:0 20px}h1{font-size:27px}h2{font-size:20px;margin-top:32px}p{line-height:1.8}.table{overflow:auto}table{border-collapse:collapse;white-space:nowrap;width:100%}th,td{padding:8px 10px;border-bottom:1px solid #e2e8ed;text-align:right}th{background:#eef4f7}td:first-child,th:first-child{text-align:left}.note{background:#fff5e7;padding:14px;border-radius:7px}a{color:#147d92}</style><h1>2024年逐笔回撤归因</h1>'+f'<p>冻结来源：{manifest["run_id"]}。2023年末权益{baseline.equity:,.2f}元 → 2024年末{year.equity.iloc[-1]:,.2f}元；全年净亏{total:,.2f}元（{summary["year_return_pct"]:.2f}%）。所有{len(year)}个日账户边界、持仓与损益分项逐日对账通过。</p><p class="note">这是已有日线近似回测的归因，不是新回测。下列“2024净贡献”按日MTM归属到该年，含当年手续费与滑点；“整笔净盈亏”跨完整持有期。跨年交易两项可能不同。关闭的日内止损/重试及供需过滤限制仍在；不能把算术删去亏损交易当作可交易反事实。</p><h2>主要集中亏损：节后同日三笔股指多头</h2><p>三笔合计净亏'+f'{top3_loss:,.2f}元，占全年净亏{summary["top3_share_of_annual_net_loss_pct"]:.2f}%。这只是损益贡献比例，其它交易贡献与账户路径会相互影响。</p><div class="table">'+table(top3[top3cols])+'</div><h2>按品种</h2><div class="table">'+table(products)+'</div><h2>按信号与方向</h2><div class="table">'+table(signals)+'</div><h2>按月份</h2><div class="table">'+table(monthly)+'</div><h2>全部逐笔（按2024净贡献从差到好）</h2><p>包括跨年带入和年末仍未平仓的交易，未省略盈利交易；可用浏览器查找合约或trade_id。金额单位均为元。<a href="episodes_2024_mtm.csv">下载完整逐笔CSV</a> · <a href="daily_episode_mtm_2024.csv">下载逐笔逐日MTM CSV</a></p><div class="table">'+table(attributed[detailcols])+'</div><h2>日历账本与平仓账本桥接</h2><p>'+f'2024退出的整笔净盈亏{closed_total:,.6f}元 + 年末未平仓净浮盈亏{end_unrealized:,.6f}元 − 年初未平仓净浮盈亏{start_unrealized:,.6f}元 = 2024日历净损益{total:,.6f}元。浮盈亏这里含该未平仓的入场成本，以与完整episode净口径衔接。</p><p>source manifest SHA256：'+summary['source_manifest_sha256']+'</p></html>'
 (OUT/'index.html').write_text(page,encoding='utf-8')
 summary['artifact_sha256']={p.name:sha(p) for p in OUT.iterdir()}
 (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(summary,ensure_ascii=False,indent=2));print('PRODUCTS',products.head(16).to_json(orient='records',force_ascii=False));print('FAMILIES',families.to_json(orient='records',force_ascii=False));print('MONTHLY',monthly.to_json(orient='records',force_ascii=False))
if __name__=='__main__':main()
