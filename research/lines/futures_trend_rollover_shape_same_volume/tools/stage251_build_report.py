"""Stage251 已完成引擎结果的 A/C 对比，不修改策略或输入。"""
from __future__ import annotations
import argparse
import hashlib
import json
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


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--a',type=Path,required=True);ap.add_argument('--c',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    x=ap.parse_args();out=x.output.resolve();out.mkdir(parents=True,exist_ok=True)
    runs={'A':x.a.resolve(),'C':x.c.resolve()};data={};sources={}
    for arm,root in runs.items():
        m=json.loads((root/'metrics.json').read_text());p=json.loads((root/'run_provenance.json').read_text());s=json.loads((root/'statistics_audit/summary.json').read_text())
        assert not p['diagnostic_incomplete_minutes'] and not s['diagnostic_incomplete_minutes']
        assert p['arm']==arm and p['all_other_parameters_match_baseline']
        d=pd.read_csv(root/'daily.csv');y=pd.read_csv(root/'statistics_audit/year_month_results.csv');cycles=pd.read_csv(root/'statistics_audit/complete_cycles.csv')
        data[arm]={'metrics':m,'provenance':p,'stats':s,'daily':d,'year_month':y,'cycles':cycles}
        for name in ['metrics.json','run_provenance.json','daily.csv','statistics_audit/summary.json','statistics_audit/year_month_results.csv','statistics_audit/complete_cycles.csv']:
            sources[str(root/name)]=hashlib.sha256((root/name).read_bytes()).hexdigest()
    a,c=data['A'],data['C']
    delta_net=c['metrics']['end_equity']-a['metrics']['end_equity']
    cost_saved=float(a['daily'].slippage.sum()+a['daily'].commission.sum()-c['daily'].slippage.sum()-c['daily'].commission.sum())
    delta_gross=delta_net-cost_saved
    assert a['provenance']['minute_input_sha256']==c['provenance']['minute_input_sha256']
    assert a['provenance']['input_manifest_sha256']==c['provenance']['input_manifest_sha256']
    assert a['daily'].date.tolist()==c['daily'].date.tolist()
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
    verdict='通过本轮最小门槛，可另行考虑固定多周期验证；本轮不能晋升。' if passed else '未通过预注册最小门槛，本轮不进入正式候选；不追加阈值或品种规则挽救。'
    if not c['metrics']['dd40_pass']:
        verdict+=' C的全期回撤仍超过40%的正式风险门槛。'
    fig,axes=plt.subplots(3,1,figsize=(13,11),constrained_layout=True)
    for arm,z,color,label in [('A',a,'#2878B5','A: official + accepted execution fixes'),('C',c,'#DC6C36','C: half-R module disabled')]:
        d=z['daily'];date=pd.to_datetime(d.date);eq=d.account_equity
        axes[0].plot(date,eq/10000,label=label,color=color,lw=1.5)
        axes[1].plot(date,(eq/eq.cummax()-1)*100,label=arm,color=color,lw=1.3)
        mask=d.date.ge('2025-09-01');base=z['stats']['periods']['since_202509']['start_equity']
        axes[2].plot(date[mask],(eq[mask]/base-1)*100,color=color,label=arm,lw=1.5)
    axes[0].set_title('Stage251 | 2020-01-01 to 2026-10-14 | Initial capital CNY 150,000',loc='left');axes[0].set_ylabel('Equity (CNY 10,000)');axes[0].legend(loc='upper left')
    axes[1].set_ylabel('Drawdown (%)');axes[2].set_ylabel('Return since Sep 2025 (%)');axes[2].set_title('Each arm normalized to its own 2025-08-29 closing equity',loc='left',fontsize=10)
    for ax in axes:ax.grid(alpha=.2);ax.spines[['top','right']].set_visible(False)
    fig.savefig(out/'comparison.png',dpi=160);plt.close(fig)
    decomposition=f'净权益差额 {fmt(delta_net,0)} 元 = 毛盈亏差额 {fmt(delta_gross,0)} 元 + 成本减少 {fmt(cost_saved,0)} 元。这是账面恒等式，仓位、信号竞争与资金路径已经联动，不能将成本差额直接当作独立因果贡献。'
    report='''# Stage251：关闭0.5R模块的回测对比

本轮在 `codex/stage251-disable-half-r-stop` 分支直接完成，未创建工作树。

A 是 m0008 / Stage037 / C9 15万正式参数，加上一轮已验收的权益与撮合正确性修复；C 仅关闭 `enable_stage847_half_r_stop_retry`，因此同时取消初次0.5R止损和其依赖重试。C2入场日条件1R止损、日线退出、月度AI、仓位和保证金规则保持一致。

'''+verdict+'\n\n## 全期比较\n\n'+table(['指标','A：正式参数基准','C：关闭0.5R模块','C−A'],full)+'\n\n'+decomposition+'''\n
成交笔数是买卖成交数量；胜率采用扣成本后完整平仓周期。A重试会产生额外周期，因此同时给出合并依赖重试的独立交易段，避免机械地把减少重试当成胜率改善。期末未平仓按每日收盘估值计入权益，不计入完整周期胜率。

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

两组使用相同数据和模型文件SHA、分钟缓存、日期、成本与共同修复源码。严格模式要求实际入场扫描和普通成交首分钟完整；实际消费范围还需独立原始来源验证。报告的算术校验不代替来源、执行路径和独立review验收，最终状态以 `final_acceptance.json` 为准。

供需过滤开关保持正式True，但历史供需信号文件缺失、实际加载0行，策略按no_signal/weight1运行。两组共用相同缺失输入状态；这一边界与上一轮Stage249一致，不能宣称已覆盖完整生产外部信号。

历史AI按同一正式政策：2022年1月以前使用静态18品种边界，其后使用历史月度Top10非fu加固定fu。模型训练含2020—2022年，不能把整个窗口称为严格样本外；两组的相对实验保持同一AI口径。

本机可核实冻结物料和远端master，不能核实生产主机实时状态。没有修改正式配置、冻结物料或生产任务，没有委托或报撤调用。

## 调研、过拟合与后续判断

[VeighNa官方回测源码](https://github.com/vnpy/vnpy_portfoliostrategy/blob/main/vnpy_portfoliostrategy/backtesting.py)与[Backtrader执行文档](https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/)支持完整订单路径重放；不能简单删除旧止损单重算收益。资料不证明任何一组更优。

这次固定开/关消融本身没有参数寻优，但选题受已观察弱段影响，仍有选择偏差；单次历史优势不足以晋升。下一步仅依据预注册门槛，不按亏损品种、月份或R小数追加条件。

'''
    report+='预注册门槛：\n\n'+table(['门槛','结果'],[[k,'通过' if v else '未通过'] for k,v in gates.items()])+'\n'
    report+='\n## 曲线与逐笔证据\n\n'+f'![两组权益、回撤及近期收益对比]({out / "comparison.png"})\n\n'
    for arm,root in runs.items():
        report+=f'- {arm}：[逐日权益]({root / "daily.csv"})、[逐笔成交]({root / "trades.csv"})、[完整持仓周期]({root / "statistics_audit/complete_cycles.csv"})、[合并重试交易段]({root / "statistics_audit/complete_episodes.csv"})、[运行身份与输入]({root / "run_provenance.json"})。\n'
    report+='\n置信度：算术、执行及来源的可复现性按独立验收判断；策略未来泛化证据仍有限，完整历史窗口和已观察弱段不替代独立起点验证。\n'
    (out/'report.md').write_text(report)
    summary={'A':a['metrics'],'C':c['metrics'],'weak_period':{'A':ar,'C':cr},'gates':gates,'minimum_gate_pass':passed,'verdict':verdict,'promotion':False,'source_hashes':sources,'same_minute_input_sha256':a['provenance']['minute_input_sha256'],'same_input_manifest_sha256':a['provenance']['input_manifest_sha256'],'fixed_path_cost_stress':stress,'accounting_decomposition':{'delta_net':delta_net,'delta_gross':delta_gross,'cost_saved':cost_saved,'causal_attribution':False}}
    (out/'comparison_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'gates':gates,'verdict':verdict},ensure_ascii=False))

if __name__=='__main__':main()
