"""Plot cached full-period accounts; no financial replay or parameter search."""
import os
import json
from pathlib import Path
import sys

LINE=Path(__file__).resolve().parents[1]
OUT=LINE/'outputs/stage001_first_screen'
os.environ.setdefault('MPLCONFIGDIR',str(OUT/'runtime/matplotlib_plot'))
sys.path.insert(0,'/Users/mac/Documents/Codex/fian-research-20261014/.py311/lib/python3.11/site-packages')
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
from matplotlib import pyplot as plt
from matplotlib.font_manager import FontProperties


def main():
    font=FontProperties(fname='/System/Library/Fonts/STHeiti Medium.ttc')
    matplotlib.rcParams.update({'font.family':font.get_name(),'axes.unicode_minus':False,'font.size':11})
    fig,axes=plt.subplots(2,2,figsize=(16,10),constrained_layout=True)
    colors={'A0':'#326d9f','C0':'#bb5147'}
    data={}
    paths=json.loads((OUT/'completed_arm_paths.json').read_text()) if (OUT/'completed_arm_paths.json').exists() else {'A0':'A0','C0':'C0'}
    for arm in ['A0','C0']:
        f=pd.read_csv(OUT/paths[arm]/'daily.csv',parse_dates=['date'])
        data[arm]=f
        eq=f.account_equity.to_numpy()
        draw=(eq/np.maximum.accumulate(np.r_[150000.,eq])[1:]-1)*100
        axes[0,0].plot(f.date,eq/10000,label=arm,color=colors[arm],lw=1.5)
        axes[0,1].plot(f.date,draw,label=arm,color=colors[arm],lw=1.3)
    annual=[]
    for arm,f in data.items():
        previous=150000.
        for year,g in f.groupby(f.date.dt.year):
            end=float(g.account_equity.iloc[-1])
            annual.append(dict(arm=arm,year=year,ret=(end/previous-1)*100))
            previous=end
    annual=pd.DataFrame(annual)
    years=sorted(annual.year.unique());x=np.arange(len(years))
    for arm,shift in [('A0',-.18),('C0',.18)]:
        vals=annual.loc[annual.arm.eq(arm)].set_index('year').ret.reindex(years)
        axes[1,0].bar(x+shift,vals,width=.36,color=colors[arm],label=arm)
    axes[1,0].set_xticks(x,years)
    a=pd.read_csv(OUT/paths['C0']/'weekly_gate_audit.csv',parse_dates=['date'])
    a['year']=a.date.dt.year
    a=a.loc[a.native_openable_before]
    counts=a.groupby('year').agg(total=('date','size'),ready=('weekly_ready','sum'),blocked=('gate_blocked','sum'))
    counts['unknown']=counts.total-counts.ready
    xx=np.arange(len(counts))
    axes[1,1].bar(xx,counts.blocked,color='#bb5147',label='新门拦截')
    allowed=counts.ready-counts.blocked
    axes[1,1].bar(xx,allowed,bottom=counts.blocked,color='#51966a',label='已知且顺向')
    axes[1,1].bar(xx,counts.unknown,bottom=counts.ready,color='#b8b8b8',label='未知保留基线')
    axes[1,1].set_xticks(xx,counts.index)
    titles=['原账户净权益（万元）','相对历史峰值回撤（%）','连续账户各年收益（%，不代表独立冷启动）','C0原规则可开初始计划的周状态（次数）']
    for ax,title in zip(axes.flat,titles):
        ax.set_title(title,loc='left',pad=12)
        ax.grid(axis='y',alpha=.2)
        ax.spines[['top','right']].set_visible(False)
        ax.legend(frameon=False,fontsize=9)
    fig.suptitle('三重滤网第一层：已完成周方向许可的离线A0/C0比较',fontsize=20)
    target=OUT/'comparison.png'
    fig.savefig(target,dpi=150)
    plt.close(fig)
    print(target)


if __name__=='__main__':main()
