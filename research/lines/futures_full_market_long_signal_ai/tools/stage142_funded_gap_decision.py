"""Report accepted derived accounting only; zero new fits, SQL or cash."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse,json,hashlib
import pandas as pd
L=Path(__file__).resolve().parents[1]
def bind(p):
 p=Path(p).resolve();v=p.read_bytes();return dict(path=str(p),bytes=len(v),sha256=hashlib.sha256(v).hexdigest())
def dump(p,v):p.write_text(json.dumps(v,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n')
def fmt(v):return f'{float(v):,.2f}'
def md(rows):
 cols=list(rows[0]);return '\n'.join(['| '+' | '.join(cols)+' |','| '+' | '.join(['---']*len(cols))+' |']+['| '+' | '.join(str(r[k]) for k in cols)+' |' for r in rows])
def main(args):
 R=Path(args.review);r=json.loads(R.read_text());t=json.loads(Path(args.terminal).read_text());assert r['status']=='completed' and r['counts']==dict(Critical=0,Important=0,Minor=0) and t['exit_code']==0
 A=L/'outputs/stage140_funded_gap/actual_run2';m=json.loads((A/'manifest.json').read_text());assert r['exact_inputs']['attribution_manifest']==bind(A/'manifest.json');assert r['account_count']==88 and r['pair_count']==84
 O=L/'outputs/stage142_funded_gap_decision';O.mkdir(exist_ok=False);now=datetime.now(ZoneInfo('Asia/Shanghai'))
 agg=pd.read_csv(A/'aggregate_summaries.csv.gz');rows=[]
 for a in agg.to_dict('records'):rows.append({'起点':a['window'],'成本':a['cost'],'对照':a['contrast'],'净增长差':fmt(a['delta_CNY']),'风险份额项':fmt(a['risk_component']),'每风险单位贡献项':fmt(a['unit_component']),'参与项':fmt(a['participation_component']),'正向母信号差额和':fmt(a['positive_delta_CNY']),'负向母信号差额和':fmt(a['negative_delta_CNY'])})
 def mean_components(name,dim):
  d=pd.read_csv(A/(name+'.csv.gz'));d=d[(d.window=='primary_2020')&(d.cost=='stress')&d.control_id.str.startswith('RANDOM')];g=d.groupby(dim)[['delta_CNY','risk_component','unit_component','participation_component','parent_rows']].sum()/20.;return g
 cat=mean_components('category_components','category');path=mean_components('path_components','path_diagnostic');affected=mean_components('affected_components','affected');family=mean_components('family_components','family_id');cohort=mean_components('cohort_components','cohort_year')
 def compact(g,label):return [{label:str(k),'平均母信号数':fmt(v['parent_rows']),'净CNY差':fmt(v['delta_CNY']),'风险份额项':fmt(v['risk_component']),'单位贡献项':fmt(v['unit_component']),'参与项':fmt(v['participation_component'])} for k,v in g.iterrows()]
 top=pd.read_csv(A/'top_parent_contributions.csv.gz');top=top[(top.window=='primary_2020')&(top.cost=='stress')&top.contrast.eq('AI_minus_RANDOM_POS_mean20')];toprows=[{'方向':v['side'],'排名':int(v['rank']),'family':v['family_id'],'原信号u':v['u_date'],'平均CNY差':fmt(v['delta_CNY'])} for v in top.to_dict('records')]
 s=agg[agg.window.eq('primary_2020')&agg.cost.eq('stress')&agg.contrast.eq('AI_minus_RANDOM_POS_mean20')].iloc[0]
 assert abs(s['delta_CNY']-124770.909875)<1e-5
 report=f'''# Stage142：AI资金优势的会计来源与训练目标边界\n\n时间：{now:%Y-%m-%d %H:%M} CST。研究线 futures_full_market_long_signal_ai。非重要突破；上一goal轮为progress，本轮继续取得已核实的归因证据，完整目标尚未达成。\n\n2020起压力成本下，AI比20个随机账户的平均资金增长多 **124,770.91元**。按已接受账本的对称会计桥，这一差额为：初始冻结风险份额项 **+19,207.86**，每风险单位实际贡献项 **+168,461.56**，入场参与项 **−62,898.51**。在这个坐标下，正差额主要落在共同入场的每风险单位实际贡献项，不能简单解释成“AI多下注了”。这些项是已有资金路径的事后恒等式，不是纯AI因果效应或加注实验。\n\n更具体地说，共同入场且初开月份不同的母信号平均贡献差 **+185,115.23元**；同初开动作仅 **+2,554.18元**；单边参与净差抵消约6.29万元。一个EC母信号的正差达168,059.70元，超过全部净差，但附近和其他EC信号存在大量负向抵消，EC全family净差仅41,260.75元。不能将最大赢家称为全部净优势，也不能删掉它制造新回测。\n\n现有信息仍不足以证明稳定优势：Stage138八组日log配对CI全跨0、执行容量与估值未知保持。本轮没有新增fit、SQL、标签、现金账户、行情或资金重放；累计仍391fit/202现金。\n\n## 调研和判断\n\n[LEAN TradeBuilder](https://github.com/QuantConnect/Lean/blob/master/Common/Statistics/TradeBuilder.cs)区分交易盈亏与费用，且提示不同成交时间与数量使利润/回撤归因复杂；[官方持仓文档](https://www.quantconnect.com/docs/v2/writing-algorithms/portfolio/holdings)明确未实现与平仓利润的费用口径；[Backtrader作者维护的期货经济实现](https://github.com/mementum/backtrader/blob/master/backtrader/comminfo.py)将数量、价格、乘数和保证金/费用分开。采用的判断是：先闭合货币会计，风险投入必须有一致单位，开放持仓不能丢；这些资料不提供本研究的因果或alpha保证。\n\n## 改动、输入和方法\n\n新增/修改/删除策略参数：均无。新增工具140和独立141只做已有账本派生，原模型、stop、风险、选择、预算与退出不改。新增/修改/删除回测结果：均无，只有本次归因表。期末权益、收益、回撤、Sharpe、滑点、交易数与胜率沿[Stage138完整88账户]({L/'outputs/stage138_month_ranking_decision/完整88账户指标.csv'})：例如原AI主stress期末1,569,355.17、收益56.94%、DD−10.73%；它们不是这次重新回放得到的。\n\nsourceB main selected全4917个母信号进入每个book/pair，包括无BUY、拒绝、entry unknown及outsidewindow。原完整161014 B父本仍以exact引用保留；本表的4917是冻结准入后的条件域，不冒称全市场所有信号。88book-parent共432696行、84pair-parent共413028行；cold-start保留start−1源日预留，不按u_date>=start错误截掉。\n\n每个root：C=已实现gross−entry/exit fee+末端unrealized；closed另核net_pnl。所有root、fills和期末增长回加一致，滑点已在fill价格，未重复扣除。F=initial_qty×初开时冻结risk_per_lot，BUY独核；F是初始风险分配单位，非保证金、真实 deposited capital或最大损失上界。Y=C/F，含实际减仓、退出和末端mark，既不是独立动作标签net_R，也不是每笔最大亏损。\n\n双方已入场时：ΔC=(FA−FB)×(YA+YB)/2+(YA−YB)×(FA+FB)/2；单边入场的±C归参与项。无BUY仅账本记C=0，F/Y保留空，不能把现实执行未知当0。先逐随机配对分解，再对20个CNY分量均值；不能先均F/Y再乘、替换成中位账户，或拿这套CNY桥替换138每日log CI。\n\n## 全部八组会计桥（元）\n\n{md(rows)}\n\n正负差额和是先对每条配对内的母信号差额分正负求和、再跨20随机平均；它不同于先均母信号再分正负。本表不把正负抵消后的净额称为稳定alpha。\n\n## 主stress：参与与不同月份\n\n{md(compact(cat,'互斥类别'))}\n\n母信号数是20配对的均值，允许小数；不能称20组独立交易样本。共同入场是资金路径之后的条件集合，不能用该子集估计全策略因果效应。不同月份项同时混有月份、初始风险、实际退出与后续资金路径。\n\n## 同动作路径诊断\n\n{md(compact(path,'观测路径类别'))}\n\n相同动作在同分数化成交路径下，单位项约0，金额差记在冻结风险项；少数不同成交路径仍产生单位贡献差。因此“同action”不保证相同Y。签名只覆盖归一初始手数的fills和终态、精度round12，不覆盖完整日内/逐日状态；即使相同也不证明执行未知已抵消。\n\n## 覆盖标记层，不是扣除未知后的反事实\n\n{md(compact(affected,'任侧affected'))}\n\naffected包括任侧容量unknown、曾stale、terminal open或entry execution unknown。主stress标记层净差−12,192.87元，不表示现实执行问题使AI恰损失这笔，也不能删除该层后称136,963.78为可执行净优势；变更执行会改变其余资金和持仓路径。其余原始标记可以重叠，完整pair表保留，禁止将重叠金额相加。\n\n## 入场信号cohort年及集中度\n\n{md(compact(cohort,'原u信号cohort年'))}\n\n这是把root全部生命周期贡献归给原u年份，**不是实际年度账户利润**；2026为不完整信号cohort。2024/2025为正、2022/2026为负，只作描述，不据此筛年份。真正年度回测仍沿已接受daily年边界口径。\n\n主stress的family正向前五与负向前五如下，所有family完整保存：\n\n{md(compact(pd.concat([family.nlargest(5,'delta_CNY'),family.nsmallest(5,'delta_CNY')]),'family'))}\n\n{md(toprows)}\n\n相邻或同趋势的原信号会因占仓、退出与再入场在不同母信号之间转移贡献。EC最大正项不能当独立发现；需同时看全family及正负offset，不把去掉一个母信号后的差额当新资金曲线。\n\n## 与独立标签R的错位及下一判断\n\nStage138已知域AI−uniformS等u平均−0.087607R、103增量未知；整体均值仍不可识别。本轮正的Y分量来自实际共同入场、按初始风险资金及资金路径加权，样本/分母/权重均不同，所以没有算术矛盾，也不能反推全部独立动作标签为正或已学到通用规则。\n\n原130模型仅用cutoff前成熟闭合交易net_R_stress训练；score是带闭合条件的目标，和全动作政策价值/资金目标存在区分。当前结果提示后续必须把参与、实际风险权重和尾部一并评价，**本轮尚未识别闭合条件化是该差异的原因**。不能立即用本次事后资金贡献重新贴标签、加样本权重或挑品种训练，以免将已见曲线反馈进模型。\n\n独立判断：归因有价值，已定位点估计落在哪些资金层；没有形成新可晋级策略。停止对现有52槽/Ridge/0.25N包做种子、阈值、风险和止损救参。下一步应转可证伪的新信息或目标资格问题，先核PIT可得性/标签含义，再决定是否值得一个真正不同的固定实验；不因本次正分量直接重训或增加投注。\n\n## 验证与真实运行史\n\n140第一次纯派生在1.44秒、首本前因YYYYMMDD整数被误读为日期天数而停止；修正为接受132已有解析，新增fixture先复现错误年份再GREEN。原失败terminal/源码保持，第二次纯派生107.617秒完成，10新fixture通过，金额最大绝对残差1.164×10⁻⁹元；无金融重跑。\n\n141第一次独立重建完成后，opaque路径签名因CSV数值解析相差2×10⁻¹²产生hash差异；原始ledger金额和本次资金归因未改，只修审查器诊断签名读取，保留失败/修正证据。最终独立审查C/I/M=0/0/0，核完整父域、root与BUY、每对风险/单位/参与桥、20平均、分层和固定top5。它不重审旧native/模型或重放资金。审查器自己的元数据有一处非关键展示问题：checks各项columns_checked误记为行数，逐列检查实际完成；保留原证据并在此单列，未为修正展示重跑。该问题不改变140归因表或科学审查0/0/0结论。\n\n结束过拟合反思：新增按收益调参=否；同史择题/事后叙事风险=是。继续价值=有，但当前这一会计缺口已解释到可观察资金层，应结束本归因包，不以更多分桶追逐确定故事。完整高收益低回撤、极窄损和加注资格未实现，goal保持active。\n'''
 stage=L/'stages'/f'{now:%Y%m%d_%H%M}_stage142_funded_gap_decision.md';stage.write_text(report)
 decision=dict(schema='stage142_funded_gap_decision_v1',status='completed',verdict='funded_gap_accounting_explained_no_stable_alpha_or_causal_identification',source_attribution=bind(A/'manifest.json'),independent_review=bind(R),review_terminal=bind(args.terminal),report=bind(stage),main_stress_CNY_bridge={k:float(s[k]) for k in ['delta_CNY','risk_component','unit_component','participation_component']},new_fit=0,new_SQL=0,new_cash=0,cumulative_actual_fit=391,cumulative_cash=202,original138_verdict_unchanged=True,goal_complete=False,production_qualified=False,increased_betting_qualified=False,continued_value=True,review_metadata_display_minor_deferred=1,repeated_history_story_selection_risk=True,new_outcome_tuning=False)
 dump(O/'decision.json',decision)
 assets={}
 def add(b,role='decision_asset'):
  b={k:b[k] for k in ['path','bytes','sha256']};assets[b['path']]=dict(b,artifact_role=role,reproducibility_required=True,raw_ohlc=False,storage='local_exact_reference_no_payload_copy')
 add(bind(L/'outputs/stage139_funded_gap_protocol/protocol.json'),'feature_contract')
 for b in m['input_bindings'].values():add(b)
 for b in m['source_bundle']+r['exact_inputs']['sources']:add(b,'feature_contract')
 for value in m.values():
  if isinstance(value,dict) and 'path' in value:add(value)
 for folder in [L/'outputs/stage139_funded_gap_protocol',L/'outputs/stage140_funded_gap/actual_run1',R.parent,L/'outputs/stage141_funded_gap_review/actual_run1']:
  for f in folder.rglob('*'):
   if f.is_file():add(bind(f),'qualification_evidence')
 for path in O.iterdir():
  if path.is_file():add(bind(path))
 add(bind(stage));add(bind(__file__),'feature_contract');add(bind(L/'outputs/stage138_month_ranking_decision/asset_declarations.json'))
 dump(O/'asset_declarations.json',dict(schema='stage142_local_ai_asset_references_v1',portable_bundle=False,registration_mode='local_exact_references_no_Git_or_payload_copy',assets=sorted(assets.values(),key=lambda x:x['path'])))
 print(json.dumps(dict(status='completed',report=bind(stage),decision=bind(O/'decision.json'),asset_count=len(assets)),ensure_ascii=False))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--review',required=True);p.add_argument('--terminal',required=True);main(p.parse_args())
