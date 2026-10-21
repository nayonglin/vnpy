"""Derived Chinese decision report; no model, source query or cash replay."""
from pathlib import Path
import argparse,json,hashlib
from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
L=Path(__file__).resolve().parents[1]
def bind(p):
 p=Path(p).resolve();raw=p.read_bytes();return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def dump(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def md(rows,cols):
 return '\n'.join(['| '+' | '.join(cols)+' |','| '+' | '.join(['---']*len(cols))+' |']+['| '+' | '.join(str(r.get(k,'')) for k in cols)+' |' for r in rows])
def f(x,n=2):return '未知' if x is None or not np.isfinite(float(x)) else f'{float(x):,.{n}f}'
def main(args):
 review=json.loads(Path(args.review).read_text());terminal=json.loads(Path(args.terminal).read_text())
 assert review['status']=='completed' and review['counts']==dict(Critical=0,Important=0,Minor=0)
 assert terminal['status']=='completed' and terminal['exit_code']==0
 assert review['books']['accounts_checked']==84
 root=L/'outputs/stage136_month_ranking_cash/actual_run1';c=json.loads((root/'manifest.json').read_text());a=json.loads((L/'outputs/stage135_month_ranking_choices/actual_run1/manifest.json').read_text());p=json.loads((L/'outputs/stage134_month_ranking_protocol/protocol.json').read_text())
 assert c['new_cash_accounts']==84 and c['native_source_queries']==c['actual_model_fit_calls']==c['new_labels']==c['old_AI_books_replayed']==0
 assert review['exact_inputs']['cash']==bind(root/'manifest.json')
 assert review['exact_inputs']['attribution']==bind(L/'outputs/stage135_month_ranking_choices/actual_run1/manifest.json')
 assert review['exact_inputs']['protocol']==bind(L/'outputs/stage134_month_ranking_protocol/protocol.json')
 out=L/'outputs/stage138_month_ranking_decision';out.mkdir(exist_ok=False)
 now=datetime.now(ZoneInfo('Asia/Shanghai'));summ=pd.read_csv(root/'account_summaries.csv.gz');points=pd.read_csv(root/'comparisons.csv.gz');ranks=json.loads((root/'descriptive_seed_ranks.json').read_text());labels=json.loads(Path(a['diagnostic_summary']['path']).read_text());reports=json.loads((root/'diagnostics.json').read_text())
 ai=[]
 for key,book in c['baseline_books'].items():
  s=json.loads(Path(book['summary']['path']).read_text());s.update(control_id='AI',window=book['window'],cost=book['cost']);ai.append(s)
 combined=pd.concat([pd.DataFrame(ai),summ],ignore_index=True)
 cols=['control_id','window','cost','ending_equity','total_return_pct','max_drawdown_pct','sharpe','total_slippage','total_fees','closed_trades','closed_net_win_rate','fills','open_positions','stale_positions','execution_unknown','capacity_unknown_roots','entry_execution_unknown']
 combined[cols].rename(columns=dict(control_id='选月规则',window='起点',cost='成本',ending_equity='期末权益',total_return_pct='总收益百分比',max_drawdown_pct='最大回撤百分比',sharpe='Sharpe',total_slippage='总滑点金额',total_fees='总手续费',closed_trades='闭合交易次数',closed_net_win_rate='净胜率比例',fills='成交记录数',open_positions='期末持仓数',stale_positions='期末缺价持仓数',execution_unknown='执行未知',capacity_unknown_roots='容量未知交易数',entry_execution_unknown='入场未知数')).to_csv(out/'完整88账户指标.csv',index=False)
 overview=[];distributions=[]
 for (w,cost),g in summ.groupby(['window','cost'],sort=False):
  seeds=g[g.control_id.str.startswith('RANDOM')];vol=g[g.control_id.eq('MAX_VOLUME_POS')].iloc[0];original=combined[(combined.control_id=='AI')&(combined.window==w)&(combined.cost==cost)].iloc[0];rank=next(r for r in ranks if r['window']==w and r['cost']==cost)
  for name,column in [('收益','total_return_pct'),('最大回撤','max_drawdown_pct'),('Sharpe','sharpe'),('闭合交易数','closed_trades'),('净胜率','closed_net_win_rate')]:
   distributions.append(dict(window=w,cost=cost,metric=name,min=float(seeds[column].min()),median=float(seeds[column].median()),mean=float(seeds[column].mean()),max=float(seeds[column].max()),sample=20))
  overview.append({'窗口':w,'成本':cost,'AI收益/回撤':f(original.total_return_pct)+'% / '+f(original.max_drawdown_pct)+'%','成交量收益/回撤':f(vol.total_return_pct)+'% / '+f(vol.max_drawdown_pct)+'%','随机收益中位数':f(seeds.total_return_pct.median())+'%','随机回撤中位数':f(seeds.max_drawdown_pct.median())+'%','AI收益胜过随机':str(rank['random_returns_below_AI'])+'/20','随机收益范围':f(seeds.total_return_pct.min())+'%～'+f(seeds.total_return_pct.max())+'%'})
 dump(out/'random_distributions.json',distributions)
 comparison_rows=[]
 for r in points.to_dict('records'):
  comparison_rows.append({'窗口':r['window'],'成本':r['cost'],'对照':r['contrast'],'日均对数差':f(r['mean_daily_log_difference'],9),'95%区间':'['+f(r['ci95_low'],9)+', '+f(r['ci95_high'],9)+']','执行或估值未知':bool(r['financial_unknown'])})
 label_rows=[]
 for r in labels['aggregates']:
  if r['population'] in ['admitted','multiple'] and r['period']=='all' and r['contrast'] in ['AI_minus_UNIFORM_S','UNIFORM_S_minus_UNIFORM_E','AI_minus_MAX_VOLUME_POS','AI_minus_K']:
   label_rows.append({'范围':r['scope'],'样本':r['population'],'归因':r['contrast'],'已知域等日均R':f(r['mean_equal_u_known_only'],6),'未知条数':r['unknown_increment_rows'],'全部总体均值':f(r['all_identified_mean_equal_u'],6)})
 label_main=next(r for r in labels['aggregates'] if r['scope']=='main' and r['population']=='admitted' and r['period']=='all' and r['contrast']=='AI_minus_UNIFORM_S')
 primary=points[(points.window=='primary_2020')&(points.cost=='stress')&(points.contrast=='AI_minus_RANDOM_POS_mean20')].iloc[0]
 assert primary.ci95_low<0<primary.ci95_high
 # All predeclared random paths, including poorer paths; no best-seed plot.
 import importlib.util
 plot_available=importlib.util.find_spec('matplotlib') is not None
 if plot_available:
  import matplotlib
  matplotlib.use('Agg')
  import matplotlib.pyplot as plt
  fig,axes=plt.subplots(2,1,figsize=(11,7),sharex=True,gridspec_kw={'height_ratios':[2,1]})
  for account in c['accounts']:
   if account['window']!='primary_2020' or account['cost']!='stress':continue
   d=pd.read_csv(account['ledgers']['daily']['path']);x=pd.to_datetime(d.date);v=d.equity.to_numpy();random=account['control_id'].startswith('RANDOM')
   for ax,y in [(axes[0],v/1e6),(axes[1],100*(v/np.maximum.accumulate(np.r_[1e6,v])[1:]-1))]:ax.plot(x,y,color='#9ca3af' if random else '#0f766e',alpha=.32 if random else .95,lw=.8 if random else 1.8,label=None if random else 'Max volume (positive pool)')
  b=c['baseline_books']['primary_2020_stress'];d=pd.read_csv(b['daily']['path']);v=d.equity.to_numpy();x=pd.to_datetime(d.date)
  axes[0].plot(x,v/1e6,color='#111827',lw=2.2,label='Frozen AI');axes[1].plot(x,100*(v/np.maximum.accumulate(np.r_[1e6,v])[1:]-1),color='#111827',lw=2.2)
  axes[0].plot([],[],color='#9ca3af',label='20 predeclared random policies');axes[0].legend(loc='upper left',frameon=False);axes[0].set_ylabel('Equity / initial capital');axes[1].set_ylabel('Drawdown (%)');axes[0].set_title('2020 start, stress costs: same AI-admitted positive month pool')
  for ax in axes:ax.grid(alpha=.2)
  fig.tight_layout();fig.savefig(out/'primary2020_stress_equity_drawdown.png',dpi=160);plt.close(fig)
 all_rows=[]
 for r in combined[cols].to_dict('records'):
  all_rows.append({'规则':r['control_id'],'窗口/成本':r['window']+'/'+r['cost'],'期末权益':f(r['ending_equity'],0),'收益%':f(r['total_return_pct']),'回撤%':f(r['max_drawdown_pct']),'Sharpe':f(r['sharpe'],3),'总滑点':f(r['total_slippage'],0),'闭合交易数':int(r['closed_trades']),'净胜率%':f(100*r['closed_net_win_rate'])})
 refs='[约束相同的随机对照](https://arxiv.org/abs/0810.1922)、[QuantConnect 期货Universe官方文档](https://www.quantconnect.com/docs/v2/writing-algorithms/universes/futures)、[Lean期货过滤代码](https://github.com/QuantConnect/Lean/blob/master/Common/Securities/Future/FutureFilterUniverse.cs)'
 report=f'''# Stage138 固定AI正分月池内排序归因\n\n记录时间：{now:%Y-%m-%d %H:%M} CST。研究线 futures_full_market_long_signal_ai。非重要突破版本；不改变原 Stage133 unsupported 结论。\n\n冻结 AI 在四组账户中的收益均高于成交量规则，并高于 16～19 个随机账户；但全部八个日级配对区间均跨 0。主检验 2020 起点压力成本中，AI 收益 56.94%，随机收益中位数 42.43%，AI 胜过 16/20 个随机账户；这些是固定 20 样本的描述，尚未证明稳定排序优势。更值得警惕的是动作独立标签的已知域中 AI 减正分池精确均值为 {label_main['mean_equal_u_known_only']:.6f}R，且有 {label_main['unknown_increment_rows']} 条增量未知；单动作平均R与账户资金结果存在错位，不能宣称模型已能稳定挑出最高质量信号。\n\n本轮只做固定 B 准入条件下的选月机制归因。它不证明全市场准入门、全负分不参与或原 B 减旧 A 的全部收益来源。所有 20 随机政策保留，禁止把最佳随机种子转为 alpha。全市场 long-only 研究保持独立，当前没有加注或生产资格。\n\n外部调研与判断：{refs}支持按相同历史候选集与约束设置基准，并把品种准入与具体合约选择分开。采用其方法原则，不复制参数；上述资料不能证明国内期货本研究具有收益优势。\n\n## 冻结改动、参数与运行\n\n新增策略参数：无；修改策略参数：无；删除策略参数：无。实验控制hash/20种子已在134冻结。新增对照标签：MAX_VOLUME_POS 与预声明 RANDOM_POS_00～19；只用于归因，不作为新候选。删除/修改旧回测结果：无。\n\n复用原 1552456 个真实月份动作、原六个52槽 Ridge 模型预测和原 B 四条账本，零重训、零新标签、零SQL、零旧AI资金重放。固定 B 事前选中的 parent/family-u 及 exact product，再在 u 时合格且分数>0 的 S 内选月。随机键只包含 version/seed/product/u/actual_epoch，成本、起点、未来标签和资金状态均不进入键。最大成交量使用原始 u_volume，epoch/action_id 按升序打破并列。\n\n135：322028 行 B 完整父本引用，11249 个事前选中父本，236229 覆盖行，312170 个完整 family-u。未入选 family-u 各策略无意图为已知0；开放/未解标签保留未知，先做精确系数抵消。完整父本状态未丢弃。\n\n136：21规则×2独立起点×2成本=84 个新账户，每个有独立资金、占用、整数手和退出路径。初始100万，0.25N初损，单family风险0.0025，总风险0.02，保证金上限0.25、buffer1.1；u联合预算、D只减量、不再分配余量、冻结canonical anchor及自身20low/lifecycle不改。1%原生日成交量池与入场预留双向半cap不改；退出理想成交与实际未知分开披露。两窗口分别2020-01-01/2023-01-01至2026-10-16。\n\n一次135约127.2秒；一次136实际启动/完成84账户，SQL/fit/newlabel/旧AI重放均0。累计实际训练391次，累计资金账户由118增至202，20随机是固定实验样本，并非反复寻找有利结果。\n\n## 账户对照\n\n{md(overview,list(overview[0]))}\n\n随机中位收益与随机中位回撤是各自的分布统计，不代表某一条“中位账户”，也不是可交易组合。\n\n{('[2020压力成本全部固定对照]('+str(out/'primary2020_stress_equity_drawdown.png')+')') if plot_available else '当前既有解释器未配置绘图库，本轮未安装依赖；完整资金曲线保留在各账户daily.csv.gz，未因此重跑任何账户。'}\n\n## 配对不确定性\n\n{md(comparison_rows,list(comparison_rows[0]))}\n\n主比较是 AI 每日对数收益减20个随机账户每日对数收益的算术平均，不是均值权益的对数。复用原252源交易日块、2000组已绑定索引，未再抽样或补充种子。CI只条件于本次固定20条路径，不覆盖全部随机策略不确定性或历史择题/调参风险。8/8区间跨0，不能将点估计或16/20名次写成p值或未见样本证明。两个起点及两成本设置大量共享市场年份、信号与模型；独立账户不等于四个统计独立市场实验。\n\n## 单动作诊断\n\n{md(label_rows,list(label_rows[0]))}\n\n这些数值是自身策略压力成本 net_R，不是实际资金贡献或账户复利。原130的训练目标是u时合格、在cutoff前成熟闭合交易的net_R_stress；已知不参与与未成熟样本没有被冒充闭合训练收益。因此现有分数具有闭合样本条件，不能直接解释为全体u动作的无条件资金价值，当前归因也没有识别这种条件化是否造成观察到的错位。等权先在每个u内按family-u平均、再跨u平均；已知域均值会在不同对比中有不同支持域，不可把其均值直接相加为总体分解。逐family-u的符号线性恒等式始终成立，相关项的数值分解需共同可识别。任一非零未知系数保留总体未知，禁止补零、截尾或编造有限上下界。S只有一个动作时，两边相同行动的增量可精确抵消为0，即使共同标签未知，仍单列common_unresolved_count。\n\nK只在同一个 B 胜出品种的canonical属于S时参与，否则无动作；K不是旧A，不进行F替补。UNIFORM_E也保留B的准入门，因此本实验不识别所有负分不做的总体价值。pre_family只记录原parent的E非空/S为空数量，不能用事后标签扩大选样。\n\n## 准确性与决策边界\n\n137独立审查新覆盖、完整父本、全部312170 family-u、摘要、21信号表、84账本、预算、价格、整数手、anchor/latched request、原生容量、缺价、gap及8比较。复用接受后的132/独立102纯函数及原缓存，不重审旧模型或旧AI四账本。结果 Critical/Important/Minor=0/0/0；审查没有资金重放、SQL或fit。展示警告另列保留，不能把算术通过等同于执行保证。\n\n所有比较均含执行容量或估值未知。无冲突只代表固定日成交量假设内未检出冲突；不证明盘口可成交。0.25N不构成跳空亏损上限。原133主对比CI跨0、2023独立起点回撤恶化的否决事实不变。本次AI在2023 base回撤也差于随机中位数，不能只保留2020漂亮曲线。\n\n过拟合反思：本轮未做结果驱动选参，新增过拟合调参=否；反复使用历史后的择题风险仍然存在=是。正向点估计与负的已知域平均R同时存在，应降低“AI已识别高质量信号”的确信，不能凭默会判断替代可观察证据。\n\n继续价值：有，但不再扩大本轮种子、扫月份/分数/风险/止损。下一步应优先解释分数的单动作目标与资金贡献错位、容量和资金占用如何影响右尾；先复用现有账本做机制检查，再决定是否需要全新训练目标或新的外生PIT数据。当前更高收益且更低回撤、可用极小止损加注的完整目标尚未实现。\n\n## 全部预声明账户指标\n\n胜率为闭合交易净盈利比例；总滑点为已经计入成交价的货币成本，不能再从权益重复扣除。未闭合不冒充亏损/盈利或算进闭合胜率。完整手续费、成交数、未知等见[完整88账户指标]({out/'完整88账户指标.csv'})，4条AI为旧账本只读参照、84条为本轮新增。\n\n{md(all_rows,list(all_rows[0]))}\n\n资产均为本机精确引用：原输入、源码、协议、选择、84账户、独审证据与决策均登记保存，没有复制原始行情、推送Git、部署或连接交易系统。\n'''
 stage=L/'stages'/f'{now:%Y%m%d_%H%M}_stage138_month_ranking_decision.md';stage.write_text(report)
 decision=dict(schema='stage138_month_ranking_decision_v1',status='completed',verdict='conditional_positive_cash_lead_ranking_not_established',original133_verdict='unsupported',fixed_gate_unchanged=True,goal_complete=False,production_qualified=False,increased_betting_qualified=False,new_fits=0,new_SQL=0,new_labels=0,new_cash=84,old_AI_replays=0,cumulative_actual_fits=391,cumulative_cash_accounts=202,source_135=bind(L/'outputs/stage135_month_ranking_choices/actual_run1/manifest.json'),source_136=bind(root/'manifest.json'),independent_review=bind(args.review),review_terminal=bind(args.terminal),report=bind(stage),comparison_intervals_all_cross_zero=True,main_known_only_label_rank_difference=label_main['mean_equal_u_known_only'],main_label_unknown_rows=label_main['unknown_increment_rows'],random_ranks_descriptive_only=ranks,reflections=dict(new_outcome_tuning=False,repeated_history_selection_risk=True,continued_value=True),next='Existing-ledger attribution of label/score versus funded right tail and capacity; no more random seeds or rescue tuning')
 dump(out/'decision.json',decision)
 # Explicit roles, references only; no payload copying or Git action.
 assets={}
 def add(item,role,required=True,raw=False):
  b={k:item[k] for k in ['path','bytes','sha256']};assets[b['path']]=dict(b,artifact_role=role,reproducibility_required=required,raw_ohlc=raw,storage='local_exact_reference_no_payload_copy')
 for role,b in p['inputs'].items():
  add(b,'cache_or_visualization' if role=='native_cache' else 'decision_asset',role!='native_cache',role=='native_cache')
 for b in [bind(L/'outputs/stage134_month_ranking_protocol/protocol.json'),*a['source_bundle'],*c['source_bundle']]:add(b,'feature_contract')
 for b in a['full_base_references'].values():add(b,'decision_asset')
 for b in [a['authorization'],c['authorization'],bind(L/'outputs/stage134_month_ranking_protocol/authorize137.json')]:add(b,'qualification_evidence')
 for b in p['bootstrap_indices'].values():add(b,'qualification_evidence')
 for path in [L/'outputs/stage135_month_ranking_choices/actual_run1/manifest.json',root/'manifest.json',L/'outputs/stage133_contract_choice_decision/asset_declarations.json']:add(bind(path),'decision_asset')
 for k in ['overrides','diagnostic_family_u','diagnostic_summary','terminal']:add(a[k],'decision_asset')
 for b in c['artifacts']:add(b,'decision_asset')
 for path in Path(args.review).parent.iterdir():
  if path.is_file():add(bind(path),'qualification_evidence')
 for b in review['exact_inputs']['sources']:add(b,'qualification_evidence')
 for path in out.iterdir():
  if path.is_file():add(bind(path),'cache_or_visualization' if path.suffix=='.png' else 'decision_asset',path.suffix!='.png')
 add(bind(stage),'decision_asset');add(bind(__file__),'feature_contract')
 dump(out/'asset_declarations.json',dict(schema='stage138_local_ai_asset_references_v1',artifact_role='decision_asset',reproducibility_required=True,registration_mode='local_reference_only_no_Git_no_copy',assets=sorted(assets.values(),key=lambda a:a['path']),portable_bundle=False,production_qualified=False))
 print(json.dumps(dict(status='completed',report=bind(stage),decision=bind(out/'decision.json'),assets=len(assets)),ensure_ascii=False))
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--review',required=True);a.add_argument('--terminal',required=True);main(a.parse_args())
