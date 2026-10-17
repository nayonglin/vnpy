"""Render four scientific figures from immutable Stage269 analysis caches.

No market computation, bootstrap, strategy engine, training or download occurs.
The alternate frozen site-packages path is used only by this plotting process.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

os.environ.setdefault('MPLCONFIGDIR','/tmp/stage269-mpl')
FROZEN_SITE=Path('/Users/mac/Documents/Codex/fian-research-20261014/.py311/lib/python3.11/site-packages')
if FROZEN_SITE.exists():
    sys.path.insert(0,str(FROZEN_SITE))

import matplotlib
matplotlib.use('Agg')
import matplotlib.dates as mdates
from matplotlib import font_manager
from matplotlib.ticker import PercentFormatter, FuncFormatter
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

COLORS={'low':'#376b9d','mid':'#b98524','high':'#b24b48'}
LABELS={'low':'低效率','mid':'中效率','high':'高效率'}
GROUPS=['low','mid','high']
INK='#243447'
MUTED='#6e7781'
BG='#ffffff'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def configure():
    choices=[Path('/System/Library/Fonts/PingFang.ttc'),Path('/System/Library/Fonts/STHeiti Medium.ttc')]
    font=next((p for p in choices if p.exists()),None)
    if font:
        font_manager.fontManager.addfont(str(font))
        name=font_manager.FontProperties(fname=str(font)).get_name()
    else:
        name='DejaVu Sans'
    plt.rcParams.update({'font.family':name,'font.size':11,'axes.titlesize':13,
        'axes.labelsize':11,'axes.labelcolor':INK,'text.color':INK,'xtick.color':INK,
        'ytick.color':INK,'axes.edgecolor':'#c8cdd2','axes.spines.top':False,
        'axes.spines.right':False,'axes.unicode_minus':False,'figure.facecolor':BG,
        'axes.facecolor':BG,'savefig.facecolor':BG,'grid.color':'#e2e7eb',
        'grid.alpha':.8,'grid.linewidth':.7,'legend.frameon':False})
    return str(font) if font else name


def polish(ax,grid=True):
    if grid:
        ax.grid(axis='y',zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(length=3)


def decorate(fig,title,subtitle,footer):
    fig.suptitle(title,x=.07,y=.978,ha='left',fontsize=19,fontweight='bold',color=INK)
    fig.text(.07,.941,subtitle,ha='left',va='top',fontsize=11,color=MUTED)
    fig.text(.07,.025,footer,ha='left',va='bottom',fontsize=10,color=MUTED,linespacing=1.5)


def save(fig,out,name):
    path=out/name
    fig.savefig(path,dpi=180,bbox_inches=None)
    plt.close(fig)
    return path


def figure1(daily,summary,out):
    fig,axs=plt.subplots(3,1,figsize=(16,11),sharex=True,
        gridspec_kw={'height_ratios':[1,1.2,1.2]})
    fig.subplots_adjust(left=.08,right=.97,top=.87,bottom=.11,hspace=.25)
    dates=daily.date
    coverage=daily.coverage_ratio
    axs[0].fill_between(dates,coverage,0,color='#c4d8e7',alpha=.8,lw=0,label='完整ER60 / 成熟活跃产品')
    axs[0].plot(dates,coverage,color=COLORS['low'],lw=1)
    axs[0].axhline(.9,color=COLORS['high'],ls='--',lw=1.3,label='总覆盖门90%')
    axs[0].scatter(dates[daily.gate_pass],coverage[daily.gate_pass],s=6,color='#1c746b',label='同时通过全部门')
    axs[0].set_ylim(.5,1.04)
    axs[0].yaxis.set_major_formatter(PercentFormatter(1))
    axs[0].set_ylabel('产品覆盖率')
    axs[0].set_title('a  2020年以来332/1,641日通过主门；还须满足每板块80%等条件',loc='left')
    axs[0].legend(loc='lower left',ncol=3,fontsize=9)
    axs[1].plot(dates,daily.raw_market_er60,color='#b7bdc4',lw=.9,label='raw ER60（有效集诊断，未认证全市场覆盖）')
    axs[1].plot(dates,daily.market_er60,color='#1c746b',lw=1.2,label='过门M（缺失保持空缺）',marker='.',ms=2)
    for group in GROUPS:
        mask=daily.regime.eq(group)
        axs[1].scatter(dates[mask],np.full(mask.sum(),-.012),s=12,color=COLORS[group],marker='|',label=f'{LABELS[group]}分桶日')
    axs[1].set_ylim(-.025,max(.36,float(daily.raw_market_er60.max())*1.06))
    axs[1].set_ylabel('ER60')
    axs[1].set_title('b  主指标有空缺；灰线只描述可得产品，不能替代缺失M',loc='left')
    axs[1].legend(loc='upper left',ncol=2,fontsize=9)
    axs[2].plot(dates,daily.account_equity/10000,color=INK,lw=1.4)
    axs[2].set_ylabel('原权益 / 万元')
    axs[2].set_title('c  固定Stage251 A_final3原权益；这里只对齐时间，不重跑引擎',loc='left')
    for ax in axs:
        polish(ax)
    axs[2].xaxis.set_major_locator(mdates.YearLocator())
    axs[2].xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    axs[2].set_xlim(dates.min(),dates.max())
    decorate(fig,'Stage269｜覆盖不足：122个成熟分桶日，未形成跨周期证据',
        '主样本2020-01-02—2026-10-14；142个分桶日集中在2025–2026，其中20日远期标签成熟122日。',
        '冻结门：ER60覆盖≥90%、商品≥15、板块≥5、每个当时存在板块覆盖≥80%；扩展分位须有252个此前有效M。\n历史样本已被观察；参数为C9/15万，回放含已接受的会计/撮合修复，非生产资格证明。')
    return save(fig,out,'01_coverage_efficiency_equity.png')


def figure2(primary,out):
    groups={g['regime']:g for g in primary['groups']}
    fig,axs=plt.subplots(1,2,figsize=(16,9))
    fig.subplots_adjust(left=.08,right=.97,top=.84,bottom=.27,wspace=.23)
    for ax,key,cikey,subtitle in [
        (axs[0],'mean','mean_ci','a  未来20个源交易日平均净权益收益'),
        (axs[1],'profit_probability','profit_probability_ci','b  同一20日标签的盈利概率')]:
        for i,group in enumerate(GROUPS):
            g=groups[group]
            value=g[key]
            lo,hi=g[cikey]
            ax.errorbar(i,value,yerr=np.array([[value-lo],[hi-value]]),fmt='o',ms=10,
                capsize=7,elinewidth=2,color=COLORS[group],zorder=3)
            ax.annotate(f'{value*100:+.2f}%' if key=='mean' else f'{value*100:.2f}%',
                (i,value),xytext=(13,0),textcoords='offset points',va='center',fontsize=12)
        ax.set_xticks(range(3),[f'{LABELS[g]}\n成熟 n={groups[g]["n"]}' for g in GROUPS])
        ax.set_xlim(-.55,2.8)
        ax.yaxis.set_major_formatter(PercentFormatter(1))
        ax.set_title(subtitle,loc='left',pad=18)
        polish(ax)
    axs[0].axhline(0,color=MUTED,lw=1,ls='--')
    axs[0].set_ylim(-.19,.22)
    axs[0].set_ylabel('净权益收益')
    axs[1].set_ylim(-.05,1.05)
    axs[1].set_ylabel('P(未来20日收益 > 0)')
    rlo,rhi=primary['return_ci'];plo,phi=primary['profit_probability_ci']
    fig.text(.08,.175,f'高 − 低：收益 {primary["return_difference"]*100:+.2f} 个百分点\n95% CI [{rlo*100:+.2f}, {rhi*100:+.2f}]',fontsize=13,linespacing=1.6)
    fig.text(.56,.175,f'高 − 低：盈利概率 {primary["profit_probability_difference"]*100:+.2f} 个百分点\n95% CI [{plo*100:+.2f}, {phi*100:+.2f}]',fontsize=13,linespacing=1.6)
    decorate(fig,'Stage269｜高组未更常盈利；高低收益差的区间跨0',
        '仅122个成熟分桶日：低33 / 中47 / 高42；中组表现最好，不能改写为“效率越高越好”。',
        '误差线直接来自固定60日平均长度的stationary block bootstrap：2000次、seed=42；未在作图时重估。\n标签重叠且样本稀疏；固定20日非重叠格点仅7个合格锚点。置信区间不创造独立市场周期。')
    return save(fig,out,'02_future20_groups_ci.png')


def effect_panel(ax,table,key,title,xlabel):
    xs=np.arange(len(table))
    finite=table.return_difference.notna() & table.profit_probability_difference.notna()
    ax.axhline(0,color=MUTED,lw=1,ls='--')
    ax.plot(xs[finite]-.08,table.loc[finite,'return_difference']*100,'o',color=COLORS['low'],ms=8,label='高−低：20日收益')
    ax.plot(xs[finite]+.08,table.loc[finite,'profit_probability_difference']*100,'s',color=COLORS['high'],ms=7,label='高−低：盈利概率')
    for i,row in table.iterrows():
        if not finite.iloc[i]:
            ax.text(i,1,'无成熟\n分桶样本',ha='center',va='bottom',fontsize=10,color=MUTED)
        else:
            upper=max(row.return_difference,row.profit_probability_difference)*100
            lower=min(row.return_difference,row.profit_probability_difference)*100
            ax.annotate(f'n={int(row.n_labeled)}\n低/中/高={int(row.n_low)}/{int(row.n_mid)}/{int(row.n_high)}',
                (i,upper),xytext=(0,13),textcoords='offset points',ha='center',fontsize=9)
            ax.annotate(f'{row.return_difference*100:+.2f} / {row.profit_probability_difference*100:+.2f}',
                (i,lower),xytext=(0,-20),textcoords='offset points',ha='center',fontsize=9,color=MUTED)
    ax.set_xticks(xs,table[key].astype(str))
    ax.set_ylabel('差值 / 百分点')
    ax.set_title(title,loc='left',pad=12)
    ax.set_xlabel(xlabel)
    ax.set_ylim(-26,26)
    ax.legend(loc='upper left',ncol=2,fontsize=9)
    polish(ax)


def figure3(summary,annual,leave,out):
    fig,axs=plt.subplots(3,1,figsize=(16,14),gridspec_kw={'height_ratios':[1.0,1.2,1.2]})
    fig.subplots_adjust(left=.08,right=.97,top=.88,bottom=.11,hspace=.60)
    coverage=pd.DataFrame(summary['coverage_by_year'])
    x=np.arange(len(coverage));width=.21
    for off,col,color,label in [(-1.5,'calendar_days','#d5dbe1','原样本交易日'),
                               (-.5,'gate_days','#9bbfcf','过市场门'),
                               (.5,'classified_days','#4f8eaa','可分桶'),
                               (1.5,'mature_classified_days','#245d76','20日标签成熟')]:
        values=coverage[col]
        axs[0].bar(x+off*width,values,width,color=color,label=label)
        if col=='mature_classified_days':
            for i,value in enumerate(values):
                axs[0].text(i+off*width,value+6,str(value),ha='center',fontsize=10)
    axs[0].set_xticks(x,coverage.year.astype(str))
    axs[0].set_ylim(0,285)
    axs[0].set_ylabel('源交易日数')
    axs[0].set_title('a  覆盖和标签成熟：2020–2024没有可分类主检验样本',loc='left')
    axs[0].legend(ncol=4,loc='upper left',fontsize=9)
    polish(axs[0])
    effect_panel(axs[1],annual,'year','b  年度高−低：2025与2026方向不同','所属年份（去掉20日标签跨年样本）')
    effect_panel(axs[2],leave,'excluded_year','c  逐年剔除：剔除无样本的2020–2024不会增加稳健性证据','剔除年份（去掉标签跨入被剔除年的行）')
    decorate(fig,'Stage269｜年度效应不稳，缺失年份不能画成0收益',
        '年度内标签：2025年47个、2026年67个；去掉跨年标签后少8个。主样本122日不等于122次独立试验。',
        '圆点为收益差，方点为同一20日盈利概率差；此图是年度/剔除一年点估计，不是独立检验或新OOS。\n原1,641日历行约27/14个60/120日长度量级，只表示原日历长度；不能当作合格样本的有效区块数。')
    return save(fig,out,'03_annual_and_leave_year_out.png')


def figure4(regression,episode_groups,episodes,out):
    fig,axs=plt.subplots(2,2,figsize=(17,12))
    fig.subplots_adjust(left=.14,right=.96,top=.86,bottom=.13,wspace=.34,hspace=.47)
    names=['年度效应','+ 市场波动','+ 相关/方向/自身ER','+ 事前策略暴露']
    beta=np.array([x['beta_per_sd'] for x in regression])*100
    ys=np.arange(len(beta))
    axs[0,0].axvline(0,color=MUTED,lw=1,ls='--')
    axs[0,0].plot(beta,ys,'o-',color=COLORS['low'],ms=8,lw=1)
    for x,y,model in zip(beta,ys,regression):
        axs[0,0].annotate(f'{x:+.2f} pp；n={model["n"]}',(x,y),xytext=(10,0),textcoords='offset points',va='center',fontsize=10)
    axs[0,0].set_yticks(ys,names)
    axs[0,0].invert_yaxis()
    axs[0,0].set_xlim(-.3,4.4)
    axs[0,0].set_xlabel('ER扩展分位提高1个样本标准差，对应20日收益 / 百分点')
    axs[0,0].set_title('a  固定OLS描述：加控制后不稳定；不绘IID置信区间',loc='left',pad=16)
    polish(axs[0,0])
    grouped=episode_groups.set_index('regime')
    rng=np.random.default_rng(42)
    for i,g in enumerate(GROUPS):
        values=episodes.loc[episodes.regime.eq(g)&episodes.is_closed,'net_R'].dropna()
        axs[0,1].scatter(i+rng.uniform(-.13,.13,len(values)),values,color=COLORS[g],s=40,alpha=.8,label='完整母信号' if i==0 else None)
        axs[0,1].hlines(grouped.loc[g,'meanR'],i-.28,i+.28,color=COLORS[g],lw=3,label='组内平均R' if i==0 else None)
        axs[0,1].hlines(grouped.loc[g,'medianR'],i-.28,i+.28,color=INK,lw=1.3,ls='--',label='组内中位R' if i==0 else None)
    axs[0,1].axhline(0,color=MUTED,lw=1)
    axs[0,1].set_xticks(range(3),[f'{LABELS[g]}\n已关 n={int(grouped.loc[g,"nclosed"])}' for g in GROUPS])
    axs[0,1].set_xlim(-.5,2.5)
    axs[0,1].set_ylim(-6,9)
    axs[0,1].set_ylabel('净R / 首次实成交初始风险')
    axs[0,1].set_title('b  完整母信号R：仅27个已关样本；高组均值−1.376R',loc='left',pad=16)
    axs[0,1].legend(loc='upper left',ncol=3,fontsize=9)
    polish(axs[0,1])
    xs=np.arange(3);w=.3
    for shift,col,label,color in [(-.5,'stoprate','0.5R止损触发率',COLORS['low']),(.5,'retryrate','重试率',COLORS['mid'])]:
        values=np.array([grouped.loc[g,col] for g in GROUPS])
        axs[1,0].bar(xs+shift*w,values,w,color=color,label=label,alpha=.85)
        for i,v in enumerate(values):
            axs[1,0].text(i+shift*w,v+.025,f'{v:.1%}',ha='center',fontsize=10)
    axs[1,0].set_xticks(xs,[f'{LABELS[g]}\n母信号 n={int(grouped.loc[g,"n"])}' for g in GROUPS])
    axs[1,0].set_ylim(0,.78)
    axs[1,0].yaxis.set_major_formatter(PercentFormatter(1))
    axs[1,0].set_title('c  触发率分母含未关母信号，不能当独立胜率',loc='left',pad=16)
    axs[1,0].legend(ncol=2,loc='upper left',fontsize=9)
    polish(axs[1,0])
    axs[1,1].axis('off')
    table_rows=[]
    for g in GROUPS:
        x=grouped.loc[g]
        table_rows.append([LABELS[g],f'{int(x.n)} / {int(x.nclosed)} / {int(x.nopen)}',
            f'{x.winprob:.1%}',f'{x.closednetpnl/10000:+.2f}',f'{x.retryClosedPNL/10000:+.2f}'])
    table=axs[1,1].table(cellText=table_rows,
        colLabels=['组别','总 / 已关 / 未关','已关胜率','已关净盈亏\n万元','重试已关盈亏\n万元'],
        loc='upper center',cellLoc='center',colWidths=[.14,.25,.18,.21,.23],bbox=[0,.36,1,.54])
    table.auto_set_font_size(False);table.set_fontsize(10)
    for (r,c),cell in table.get_celld().items():
        cell.set_edgecolor('#d8dfe5');cell.set_linewidth(.7)
        if r==0:
            cell.set_facecolor('#edf2f6');cell.set_text_props(weight='bold')
    axs[1,1].set_title('d  样本与金额口径：319母信号中仅28个可分类',loc='left',pad=16)
    axs[1,1].text(0,.24,'高组另有1个未关母信号：期末浮盈亏 −0.60万元（−0.30R），\n不计入已关胜率和完整净R。其重试未关浮盈亏 +0.48万元。',
        transform=axs[1,1].transAxes,fontsize=10,va='top',linespacing=1.7)
    decorate(fig,'Stage269｜控制项与母信号只作描述：样本不足以建立交易规则',
        '控制回归n=122；可分类母信号低/中/高=9/9/10，高组1个未关。观察期、策略和假说均有历史选择偏差。',
        'OLS为描述性固定低维模型，未计算IID标准误；完整净R分母固定母信号首次开仓实成交初始风险，包含一次重试。\n318个完整母信号中291个未分类；此图不补造被AI过滤信号的反事实收益，也不支持据此改仓位或规则。')
    return save(fig,out,'04_controls_episode_mechanism.png')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True,help='stage269_market_efficiency_validation output root')
    args=parser.parse_args(argv)
    root=Path(args.root).resolve();out=root/'figures';out.mkdir(parents=True,exist_ok=True)
    inputs={name:root/name for name in ['market/market_daily.csv','analysis/joined_daily.csv',
        'analysis/analysis_summary.json','analysis/primary_block60.json','analysis/annual_effects.csv',
        'analysis/leave_year_out.csv','analysis/regression_summary.json','analysis/episode_groups.csv','analysis/episodes.csv']}
    before={name:sha(path) for name,path in inputs.items()}
    font=configure()
    daily=pd.read_csv(inputs['analysis/joined_daily.csv'],parse_dates=['date'])
    summary=json.loads(inputs['analysis/analysis_summary.json'].read_text())
    primary=json.loads(inputs['analysis/primary_block60.json'].read_text())
    annual=pd.read_csv(inputs['analysis/annual_effects.csv'])
    leave=pd.read_csv(inputs['analysis/leave_year_out.csv'])
    regression=json.loads(inputs['analysis/regression_summary.json'].read_text())
    episode_groups=pd.read_csv(inputs['analysis/episode_groups.csv'])
    episodes=pd.read_csv(inputs['analysis/episodes.csv'])
    files=[figure1(daily,summary,out),figure2(primary,out),figure3(summary,annual,leave,out),
           figure4(regression,episode_groups,episodes,out)]
    after={name:sha(path) for name,path in inputs.items()}
    if before!=after:
        raise ValueError('input caches changed during plotting')
    metadata=dict(stage='stage269',font=font,source_cache_unchanged=True,
        market_recomputed=False,statistics_reestimated=False,financial_replays=0,
        script_sha256=sha(Path(__file__)),input_sha256=before,
        figure_sha256={p.name:sha(p) for p in files},
        note='All 95% intervals are read directly from primary_block60.json; missing annual effects are left missing. OLS has no invented confidence interval. Figures are historical descriptive evidence with sparse coverage.')
    (out/'figure_manifest.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(figures=[str(p) for p in files],font=font,input_unchanged=True),ensure_ascii=False))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
