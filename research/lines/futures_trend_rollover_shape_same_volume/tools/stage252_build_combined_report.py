"""Stage252 已完成引擎结果的 AI 选品+0.5R 组合 A/C 对比，不修改策略或输入。"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def fmt(v, digits=2):
    return f'{v:,.{digits}f}'


def table(columns, rows):
    return '\n'.join(['|'+'|'.join(columns)+'|','|'+'|'.join(['---']*len(columns))+'|',*['|'+'|'.join(map(str,row))+'|' for row in rows]])


def traded_products(trades, universe):
    """仅从实际成交合约归属统计品种，不以候选或 AI 快照冒充交易。"""
    products = set()
    for symbol in trades['vt_symbol'].dropna().astype(str):
        match = re.fullmatch(r'([A-Za-z]+)\d+\.([A-Za-z]+)', symbol)
        if match is None:
            raise ValueError(f'cannot_identify_trade_product:{symbol}')
        product = f'{match.group(1)}.{match.group(2)}'
        if product not in universe:
            raise ValueError(f'trade_product_outside_base_universe:{product}')
        products.add(product)
    return sorted(products)


def pre_ai_candidate_counts(candidates):
    """候选资格按各组自身路径计数；不能将不同路径逐行配对归因。"""
    before = candidates.loc[candidates['date'].astype(str).str[:10].lt('2022-02-01')].copy()
    if before.empty:
        raise ValueError('pre_202202_candidates_missing')
    rows = []
    for product, group in before.groupby('product_vt_symbol', sort=True):
        allowed = pd.to_numeric(group['ai_product_pool_allowed'], errors='raise').astype(int)
        enabled = pd.to_numeric(group['ai_product_pool_enabled'], errors='raise').astype(int)
        opened = pd.to_numeric(group['is_opened'], errors='raise').astype(int)
        rows.append({'product_vt_symbol': str(product), 'candidate_count': len(group),
                     'ai_enabled_count': int(enabled.sum()), 'ai_allowed_count': int(allowed.sum()),
                     'ai_blocked_count': int((allowed == 0).sum()), 'opened_candidate_count': int(opened.sum())})
    return pd.DataFrame(rows)


def minute_request_quality(root):
    """从引擎实际请求计数；只作报告状态，不把诊断结果升级成验收。"""
    scans=pd.read_csv(root/'minute_scan_requests.csv')
    anchors=pd.read_csv(root/'execution_anchor_requests.csv')
    missing_bars=pd.to_numeric(scans['missing_bar_count'],errors='raise').fillna(0)
    scan_bad=missing_bars.gt(0) | scans['coverage_status'].astype(str).ne('complete')
    anchor_present=anchors['anchor_present'].astype(str).str.casefold().isin({'true','1'})
    anchor_bad=~anchor_present | anchors['coverage_status'].astype(str).ne('complete')
    return {'scan_requests':int(len(scans)),'scan_requests_incomplete':int(scan_bad.sum()),
            'scan_missing_bars':int(missing_bars.sum()),'anchor_requests':int(len(anchors)),
            'anchor_requests_incomplete':int(anchor_bad.sum())}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--a',type=Path,required=True);ap.add_argument('--c',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    x=ap.parse_args();out=x.output.resolve();out.mkdir(parents=True,exist_ok=True)
    runs={'A':x.a.resolve(),'C':x.c.resolve()};data={};sources={}
    for arm,root in runs.items():
        m=json.loads((root/'metrics.json').read_text());p=json.loads((root/'run_provenance.json').read_text());s=json.loads((root/'statistics_audit/summary.json').read_text())
        if bool(p['diagnostic_incomplete_minutes']) != bool(s['diagnostic_incomplete_minutes']):
            raise ValueError(f'{arm}:diagnostic_status_mismatch')
        assert p['arm']==arm and p['all_other_parameters_match_baseline']
        d=pd.read_csv(root/'daily.csv');y=pd.read_csv(root/'statistics_audit/year_month_results.csv');cycles=pd.read_csv(root/'statistics_audit/complete_cycles.csv')
        trades=pd.read_csv(root/'trades.csv');candidates=pd.read_csv(root/'entry_candidates.csv')
        settings=json.loads((root/'actual_strategy_settings.json').read_text())
        parameters=json.loads((root/'effective_parameters.json').read_text())
        if len(settings)!=1 or settings[0]['actual']['enable_ai_product_pool_filter'] is not (arm=='A'):
            raise ValueError(f'{arm}:actual_ai_pool_flag_mismatch')
        actual=settings[0]['actual']
        if actual['enable_stage847_half_r_stop_retry'] is not (arm=='A') or actual['enable_selection_pairwise_v2'] is not True or actual['enable_selection_pairwise_v2_volume_tilt'] is not True:
            raise ValueError(f'{arm}:retained_modules_mismatch')
        if arm=='C' and (settings[0]['ai_product_pool_load_status']!='disabled' or settings[0]['ai_product_pool_snapshot_count']!=0):
            raise ValueError('C:ai_pool_still_loaded')
        if parameters['spec']['overrides']['enable_ai_product_pool_filter'] is not (arm=='A'):
            raise ValueError(f'{arm}:effective_ai_pool_flag_mismatch')
        if parameters['spec']['overrides']['enable_stage847_half_r_stop_retry'] is not (arm=='A'):
            raise ValueError(f'{arm}:effective_half_r_flag_mismatch')
        universe_path=Path(parameters['spec']['overrides']['product_universe_csv_path'])
        universe_frame=pd.read_csv(universe_path)
        universe=set(universe_frame.loc[pd.to_numeric(universe_frame['eligible'],errors='raise').eq(1),'product_vt_symbol'].astype(str))
        if len(universe)!=19 or len(universe_frame)!=19:
            raise ValueError(f'{arm}:base_universe_not_19')
        data[arm]={'metrics':m,'provenance':p,'stats':s,'daily':d,'year_month':y,'cycles':cycles,
                   'trades':trades,'candidates':candidates,'settings':settings,'parameters':parameters,
                   'universe':universe,'universe_sha256':hashlib.sha256(universe_path.read_bytes()).hexdigest(),
                   'traded_products':traded_products(trades,universe),'pre_ai_counts':pre_ai_candidate_counts(candidates),
                   'minute_quality':minute_request_quality(root)}
        for name in ['metrics.json','run_provenance.json','daily.csv','statistics_audit/summary.json','statistics_audit/year_month_results.csv','statistics_audit/complete_cycles.csv','trades.csv','entry_candidates.csv','actual_strategy_settings.json','effective_parameters.json','minute_scan_requests.csv','execution_anchor_requests.csv']:
            sources[str(root/name)]=hashlib.sha256((root/name).read_bytes()).hexdigest()
    a,c=data['A'],data['C']
    delta_net=c['metrics']['end_equity']-a['metrics']['end_equity']
    cost_saved=float(a['daily'].slippage.sum()+a['daily'].commission.sum()-c['daily'].slippage.sum()-c['daily'].commission.sum())
    delta_gross=delta_net-cost_saved
    assert a['provenance']['minute_input_sha256']==c['provenance']['minute_input_sha256']
    assert a['provenance']['input_manifest_sha256']==c['provenance']['input_manifest_sha256']
    assert a['daily'].date.tolist()==c['daily'].date.tolist()
    if a['universe']!=c['universe'] or a['universe_sha256']!=c['universe_sha256']:
        raise ValueError('base_universe_differs_between_arms')
    if a['parameters']['spec']['overrides'].keys()!=c['parameters']['spec']['overrides'].keys():
        raise ValueError('override_keys_differ_between_arms')
    for key in a['parameters']['spec']['overrides']:
        if key not in {'enable_ai_product_pool_filter','enable_stage847_half_r_stop_retry'} and a['parameters']['spec']['overrides'][key]!=c['parameters']['spec']['overrides'][key]:
            raise ValueError(f'non_ai_pool_override_differs:{key}')
    c_quality=c['minute_quality']
    diagnostic=bool(c['provenance']['diagnostic_incomplete_minutes'])
    missing_requests=c_quality['scan_requests_incomplete']+c_quality['anchor_requests_incomplete']
    quality_label=('现有分钟数据估算，未通过完整性验收'
                   if diagnostic or missing_requests else '严格引擎完成，待独立来源及执行验收')
    accepted_performance=False
    pre_ai_rows=[]
    for arm,z in data.items():
        for row in z['pre_ai_counts'].to_dict('records'):
            pre_ai_rows.append({'arm':arm,**row})
    pd.DataFrame(pre_ai_rows).to_csv(out/'pre_202202_candidate_eligibility.csv',index=False,encoding='utf-8-sig')
    pre_fu_rows=[]
    for arm,z in data.items():
        found=z['pre_ai_counts'].loc[z['pre_ai_counts'].product_vt_symbol.eq('fu.SHFE')]
        row=found.iloc[0] if len(found)==1 else None
        pre_fu_rows.append([arm,int(row.candidate_count) if row is not None else 0,
                            int(row.ai_blocked_count) if row is not None else 0,
                            int(row.opened_candidate_count) if row is not None else 0])
    product_rows=[{'arm':arm,'traded_product_count':len(z['traded_products']),
                   'traded_products':','.join(z['traded_products']),
                   'base_product_count':len(z['universe'])} for arm,z in data.items()]
    pd.DataFrame(product_rows).to_csv(out/'actual_traded_products.csv',index=False,encoding='utf-8-sig')
    full=[]
    for label,key,digits,suffix in [('期末权益','end_equity',0,''),('总收益','total_return_pct',2,'%'),('最大回撤','max_dd_pct',2,'%'),('Sharpe','sharpe',3,''),('总滑点','total_slippage',0,''),('成交笔数','total_trade_count',0,''),('保证金峰值/权益','max_broker10_margin_to_equity_pct',2,'%'),('保证金超过100%的交易日','days_over_100pct',0,'')]:
        av,cv=a['metrics'][key],c['metrics'][key];full.append([label,fmt(av,digits)+suffix,fmt(cv,digits)+suffix,fmt(cv-av,digits)+suffix])
    for label,field in [('完整持仓周期','entry_cohort_complete_cycles'),('独立交易段（合并重试）','entry_cohort_complete_episodes')]:
        av=a['stats']['periods']['all'][field];cv=c['stats']['periods']['all'][field]
        full.append([label+'数量',av['closed_cycles'],cv['closed_cycles'],cv['closed_cycles']-av['closed_cycles']])
        full.append([label+'胜率',fmt(av['win_rate_pct'])+'%',fmt(cv['win_rate_pct'])+'%',fmt(cv['win_rate_pct']-av['win_rate_pct'])+'个百分点'])
        full.append([label+'盈亏因子',fmt(av['profit_factor'],3),fmt(cv['profit_factor'],3),fmt(cv['profit_factor']-av['profit_factor'],3)])
    recent=[]
    ar=a['stats']['periods']['since_202509'];cr=c['stats']['periods']['since_202509']
    for label,key,digits,suffix in [('期初权益','start_equity',0,''),('净盈亏','net_mtm_pnl',0,''),('区间收益','return_pct',2,'%'),('区间最大回撤','max_dd_pct',2,'%'),('成交笔数','fill_count',0,'')]:
        recent.append([label,fmt(ar[key],digits)+suffix,fmt(cr[key],digits)+suffix])
    for label,field in [('完整周期胜率','entry_cohort_complete_cycles'),('独立交易段胜率','entry_cohort_complete_episodes')]:
        recent.append([label,f"{ar[field]['wins']}/{ar[field]['closed_cycles']} = {fmt(ar[field]['win_rate_pct'])}%",f"{cr[field]['wins']}/{cr[field]['closed_cycles']} = {fmt(cr[field]['win_rate_pct'])}%"])
    yearly=a['year_month'].merge(c['year_month'],on=['frequency','period'],suffixes=('_A','_C'),validate='one_to_one')
    yearly.to_csv(out/'year_month_comparison.csv',index=False,encoding='utf-8-sig')
    year_rows=[[r.period,fmt(r.return_pct_A)+'%',fmt(r.return_pct_C)+'%',fmt(r.max_dd_pct_A)+'%',fmt(r.max_dd_pct_C)+'%',fmt(r.net_mtm_pnl_C-r.net_mtm_pnl_A,0)] for r in yearly[yearly.frequency.eq('year')].itertuples()]
    stress=[]
    for mult in [1,2,3]:
        for arm,z in data.items():
            d=z['daily'];capital=z['metrics']['account_capital'];eq=d.account_equity.to_numpy()-(mult-1)*d.total_slippage.cumsum().to_numpy();path=np.r_[capital,eq]
            stress.append({'arm':arm,'slippage_multiplier':mult,'end_equity':float(eq[-1]),'total_return_pct':float((eq[-1]/capital-1)*100),'max_dd_pct':float((path/np.maximum.accumulate(path)-1).min()*100),'feedback_replayed':False})
    pd.DataFrame(stress).to_csv(out/'fixed_path_cost_stress.csv',index=False)
    gates={'full_equity_not_lower':c['metrics']['end_equity']>=a['metrics']['end_equity'],'full_sharpe_not_lower':c['metrics']['sharpe']>=a['metrics']['sharpe'],'full_drawdown_not_deeper':c['metrics']['max_dd_pct']>=a['metrics']['max_dd_pct'],'weak_return_not_lower':cr['return_pct']>=ar['return_pct'],'weak_drawdown_not_deeper':cr['max_dd_pct']>=ar['max_dd_pct'],'broker_margin_within_100':c['metrics']['days_over_100pct']==0}
    passed=all(gates.values())
    verdict=('组合方案数值达到预注册最小门槛，但完整性及独立验收前不能据此晋升。'
             if passed else '组合方案数值未达到预注册最小门槛；不追加阈值或品种规则挽救。')
    if not c['metrics']['dd40_pass']:
        verdict+=' C的全期回撤仍超过40%的正式风险门槛。'
    fig,axes=plt.subplots(3,1,figsize=(13,11),constrained_layout=True)
    for arm,z,color,label in [('A',a,'#2878B5','A: official baseline'),('C',c,'#DC6C36','C: AI pool and half-R disabled')]:
        d=z['daily'];date=pd.to_datetime(d.date);eq=d.account_equity
        axes[0].plot(date,eq/10000,label=label,color=color,lw=1.5)
        axes[1].plot(date,(eq/eq.cummax()-1)*100,label=arm,color=color,lw=1.3)
        mask=d.date.ge('2025-09-01');base=z['stats']['periods']['since_202509']['start_equity']
        axes[2].plot(date[mask],(eq[mask]/base-1)*100,color=color,label=arm,lw=1.5)
    axes[0].set_title('Stage252 combined | 2020-01-01 to 2026-10-14 | CNY 150,000',loc='left');axes[0].set_ylabel('Equity (CNY 10,000)');axes[0].legend(loc='upper left')
    quality_plot_label=('EXISTING DATA ESTIMATE - INCOMPLETE MINUTE COVERAGE'
                        if diagnostic or missing_requests else 'STRICT ENGINE / ACCEPTANCE PENDING')
    axes[0].text(.98,.97,quality_plot_label,transform=axes[0].transAxes,ha='right',va='top',
                 fontsize=10,color='#a33128',fontweight='bold',
                 bbox={'facecolor':'#fff0ed','edgecolor':'#a33128','pad':5})
    axes[1].set_ylabel('Drawdown (%)');axes[2].set_ylabel('Return since Sep 2025 (%)');axes[2].set_title('Each arm normalized to its own 2025-08-29 closing equity',loc='left',fontsize=10)
    for ax in axes:ax.grid(alpha=.2);ax.spines[['top','right']].set_visible(False)
    fig.savefig(out/'comparison.png',dpi=160);plt.close(fig)
    decomposition=f'净权益差额 {fmt(delta_net,0)} 元 = 毛盈亏差额 {fmt(delta_gross,0)} 元 + 成本减少 {fmt(cost_saved,0)} 元。这是账面恒等式，仓位、信号竞争与资金路径已经联动，不能将成本差额直接当作独立因果贡献。'
    report='''# Stage252：同时关闭月度 AI 选品与 0.5R 的组合对比

'''+f'**{quality_label}。** C 的分钟扫描缺失请求 {c_quality["scan_requests_incomplete"]}/{c_quality["scan_requests"]}（缺 {c_quality["scan_missing_bars"]} 根），普通成交首锚不完整请求 {c_quality["anchor_requests_incomplete"]}/{c_quality["anchor_requests"]}。诊断模式：{diagnostic}。下列收益、胜率和图表只描述当前输入下的引擎输出，不是已验收绩效；本轮不作为正式晋升依据。\n\n'+'''
A 复用 Stage251/A_final3 的 m0008 / Stage037 / C9 15万正式参数及已验收共同正确性修复；C 同时关闭 `enable_ai_product_pool_filter` 和 `enable_stage847_half_r_stop_retry`。基础池是静态18品种加 fu，共19品种；C 解除前期静态18边界及随后月度 Top10 非 fu 加固定 fu 资格限制，并取消0.5R初止及依赖重试。C2入场日条件1R止损、日线退出、仓位和保证金规则不变。独立 pairwise 候选排序及多头量倾斜仍保留。**这是双开关组合效果，不能拆为 AI 与 0.5R 各自的因果贡献，也不是无 AI 策略。**

'''+verdict+'\n\n## 全期比较\n\n'+table(['指标','A：正式参数基准','C：关闭AI选品及0.5R','C−A'],full)+'\n\n'+decomposition+'''\n
成交笔数是买卖成交数量；胜率采用扣成本后完整平仓周期。A可能有0.5R重试，故同时给出合并重试的独立交易段，避免将同一信号的多段成交当成独立机会。期末未平仓按每日收盘估值计入权益，不计入完整周期胜率。

## 基础池与实际交易品种

'''+table(['组别','基础池品种数','实际成交品种数','实际成交品种'],[[r['arm'],r['base_product_count'],r['traded_product_count'],r['traded_products']] for r in product_rows])+'''

上表从实际 `trades.csv` 的成交合约归属提取，不用候选或 AI 快照替代成交。基础19只表示可进入后续信号和风控流程；上市时间、主力映射、行情、仓位与风控仍会阻止部分品种交易。[逐品种候选资格审计](pre_202202_candidate_eligibility.csv)记录2022年2月以前各组实际候选次数、月度 AI 允许/阻断次数与已开仓候选次数。A 在此段采用2019-12-31的静态18边界且不含 fu，C 采用含 fu 的基础19。该段燃油候选的实际计数如下：

'''+table(['组别','fu候选数','AI阻断数','已开仓候选数'],pre_fu_rows)+'''

全期差异同时包含2020—2021年燃油放行及0.5R退出变化，不能归因于2022年以后的 AI 预测能力，也不能分别量化两个开关的贡献。候选与成交差异以实际计数为准；两组历史仓位路径可能分化，候选行不可机械地一对一配对。

## 2025年9月之后

'''+table(['指标','A','C'],recent)+'''\n
两组进入弱段时资金规模不同，绝对亏损不可直接当作风险优劣；以各自期初权益计算收益和回撤。此弱段是事前指定的观察段，不因结果另选月份。

## 年度路径

'''+table(['年份','A收益','C收益','A区间回撤','C区间回撤','C−A净盈亏'],year_rows)+'''\n
年度、月度结果来自连续复利路径，不是各年独立15万起跑。2026年仅截至10月14日。[完整月度表](year_month_comparison.csv)。

## 固定成交路径的滑点压力

'''+table(['滑点倍数','组别','期末权益','总收益','最大回撤'],[[r['slippage_multiplier'],r['arm'],fmt(r['end_equity'],0),fmt(r['total_return_pct'])+'%',fmt(r['max_dd_pct'])+'%'] for r in stress])+'''\n
这里只在已实现路径上增加滑点扣减，未重算仓位反馈、信号竞争和保证金约束，属于条件敏感性分析。正式费率为零，保留历史口径，不代表真实交易免手续费。

## 数据、执行与证据边界

两组使用相同数据和模型文件SHA、分钟缓存、日期、成本与共同修复源码。本轮 C 使用现有分钟数据，不因出具这份报告而补齐扫描或普通成交首锚；上述不完整请求已逐项计数。即使缺口恰为0，若引擎以诊断模式运行，也不能自行提升为严格回测。报告的算术校验不代替来源、执行路径和独立review验收。

供需过滤开关保持正式True，但历史供需信号文件缺失、实际加载0行，策略按no_signal/weight1运行。两组共用相同缺失输入状态；这一边界与上一轮Stage249一致，不能宣称已覆盖完整生产外部信号。

月度 AI 政策只在 A 生效：2022年2月以前为2019-12-31静态18边界，之后为历史月度Top10非fu加固定fu；C 在全窗口仅受基础19资格约束，同时关闭0.5R。两组继续保留独立 pairwise 模型排序及多头仓位倾斜。月度模型训练含2020—2022年，不能把整个窗口称为严格样本外；本轮也不能称无 AI 策略。

本机可核实冻结物料和远端master，不能核实生产主机实时状态。没有修改正式配置、冻结物料或生产任务，没有委托或报撤调用。

## 调研、过拟合与后续判断

[VeighNa官方回测源码](https://github.com/vnpy/vnpy_portfoliostrategy/blob/main/vnpy_portfoliostrategy/backtesting.py)支持完整订单路径重放；候选池变化会联动仓位和资金，不能从旧账本直接推算。资料不证明任何一组更优。

这次预先指定的双开关组合没有参数寻优，但选题受已观察弱段影响，仍有选择偏差；现有分钟数据的单次历史估算不足以晋升。下一步不按亏损品种、月份、R小数或 AI 分数追加条件。

'''
    report+='预注册门槛：\n\n'+table(['门槛','结果'],[[k,'通过' if v else '未通过'] for k,v in gates.items()])+'\n'
    report+='\n## 曲线与逐笔证据\n\n'+f'![两组权益、回撤及近期收益对比]({out / "comparison.png"})\n\n'
    for arm,root in runs.items():
        report+=f'- {arm}：[逐日权益]({root / "daily.csv"})、[逐笔成交]({root / "trades.csv"})、[完整持仓周期]({root / "statistics_audit/complete_cycles.csv"})、[合并重试交易段]({root / "statistics_audit/complete_episodes.csv"})、[运行身份与输入]({root / "run_provenance.json"})。\n'
    report+='\n置信度：算术、执行及来源的可复现性按独立验收判断；策略未来泛化证据仍有限，完整历史窗口和已观察弱段不替代独立起点验证。\n'
    (out/'report.md').write_text(report)
    summary={'A':a['metrics'],'C':c['metrics'],'weak_period':{'A':ar,'C':cr},'gates':gates,'minimum_gate_pass_numeric_only':passed,'verdict':verdict,'promotion':False,'quality_status':quality_label,'performance_accepted':accepted_performance,'C_diagnostic_incomplete_minutes':diagnostic,'C_minute_request_quality':c_quality,'ablation_flags':{'enable_ai_product_pool_filter':{'A':True,'C':False},'enable_stage847_half_r_stop_retry':{'A':True,'C':False}},'effect_scope':'combined_only_not_separable','source_hashes':sources,'same_minute_input_sha256':a['provenance']['minute_input_sha256'],'same_input_manifest_sha256':a['provenance']['input_manifest_sha256'],'base_universe':sorted(a['universe']),'base_universe_sha256':a['universe_sha256'],'actual_traded_products':{arm:z['traded_products'] for arm,z in data.items()},'pre_202202_candidate_counts':{arm:z['pre_ai_counts'].to_dict('records') for arm,z in data.items()},'fixed_path_cost_stress':stress,'accounting_decomposition':{'delta_net':delta_net,'delta_gross':delta_gross,'cost_saved':cost_saved,'causal_attribution':False}}
    (out/'comparison_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'gates':gates,'verdict':verdict},ensure_ascii=False))

if __name__=='__main__':main()
