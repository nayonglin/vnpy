"""从已验收结果生成静态对比图，不运行或调整策略。"""
import argparse
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--baseline',type=Path,required=True);ap.add_argument('--stats',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
for name in ['/System/Library/Fonts/PingFang.ttc','/System/Library/Fonts/Supplemental/Arial Unicode.ttf']:
    if Path(name).exists():
        font_manager.fontManager.addfont(name);plt.rcParams['font.family']=font_manager.FontProperties(fname=name).get_name();break
plt.rcParams['axes.unicode_minus']=False
new=pd.read_csv(a.source/'daily.csv');old=pd.read_csv(a.baseline/'daily.csv');m=pd.read_csv(a.stats/'year_month_results.csv');m=m[(m.frequency=='month')&(m.period>='2025-09')]
fig,ax=plt.subplots(3,1,figsize=(12,10),gridspec_kw={'height_ratios':[1.3,1,1]})
ax[0].plot(pd.to_datetime(old.date),old.account_equity/10000,label='旧回放（含已确认缺陷）',color='#a4acb3',lw=1.2)
ax[0].plot(pd.to_datetime(new.date),new.account_equity/10000,label='正确性修复后',color='#1d6677',lw=1.5)
ax[0].axvline(pd.Timestamp('2025-09-01'),ls='--',color='#b27e49',lw=1)
ax[0].set_title('C9 15万：固定策略参数下的正确性修复重跑',loc='left',fontsize=16,fontweight='bold');ax[0].set_ylabel('权益（万元）');ax[0].legend(frameon=False)
x=np.arange(len(m));ax[1].bar(x,m.net_mtm_pnl/10000,color=['#b85443' if v<0 else '#287b70' for v in m.net_mtm_pnl]);ax[1].axhline(0,c='#777',lw=.6);ax[1].set_ylabel('月度净盯市盈亏（万元）');ax[1].set_xticks(x,m.period,rotation=40,ha='right')
values=m.exit_win_rate_pct.fillna(0);ax[2].bar(x,values,color='#467aa4');ax[2].set_ylim(0,105);ax[2].set_ylabel('当月平仓周期胜率（%）');ax[2].set_xticks(x,m.period,rotation=40,ha='right')
for i,r in enumerate(m.itertuples()):ax[2].text(i,(r.exit_win_rate_pct if pd.notna(r.exit_win_rate_pct) else 0)+2,f'{int(r.exit_wins)}/{int(r.exit_closed_cycles)}',ha='center',fontsize=9)
for item in ax:item.spines[['top','right']].set_visible(False);item.grid(axis='y',alpha=.18)
fig.text(.08,.012,'截止2026-10-14交易日；胜率不含未平仓。手续费沿正式设为0、滑点固定；分钟OHLC采用预先固定的保守顺序。',fontsize=9)
fig.tight_layout(rect=(0,.035,1,1));a.output.parent.mkdir(parents=True,exist_ok=True);fig.savefig(a.output,dpi=170);fig.savefig(a.output.with_suffix('.svg'));plt.close(fig)
