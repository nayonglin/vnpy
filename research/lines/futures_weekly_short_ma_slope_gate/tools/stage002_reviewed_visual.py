from pathlib import Path
import hashlib,json,os
os.environ.setdefault('MPLCONFIGDIR','/private/tmp/weekly-short-ma-slope-mpl')
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
L=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 review=L/'stages/stage002_independent_final.json';r=json.loads(review.read_text())
 if r.get('status')!='PASS_WITH_LIMITATIONS' or any(r.get(k)!=0 for k in ['P0','P1','P2']):raise ValueError('independent_review_not_passed')
 target=L/'artifacts/stage002_equity_drawdown_reviewed.png'
 if target.exists():raise ValueError('immutable_image_exists')
 fig,(top,bottom)=plt.subplots(2,1,figsize=(12,7.2),sharex=True,gridspec_kw={'height_ratios':[2,1]});sources={str(review):sha(review)}
 for name,color,label in [('original','#7d8995','Original: no slope gates'),('short_only','#2467a6','Stage001: short gate only'),('symmetric','#c36f19','Stage002: long + short gates')]:
  p=L/f'artifacts/stage002_comparison/{name}_daily.csv';d=pd.read_csv(p);e=d.account_equity.to_numpy();dates=pd.to_datetime(d.date)
  if len(d)!=1652 or str(dates.iloc[-1])[:10]!='2026-10-29':raise ValueError('full_window_required')
  peak=np.maximum.accumulate(np.r_[150000,e])[1:];top.plot(dates,e,color=color,lw=1.2,label=label);bottom.plot(dates,(e/peak-1)*100,color=color,lw=1);sources[str(p)]=sha(p)
 top.legend(frameon=False,fontsize=9);top.set_ylabel('Modeled equity (CNY)');top.yaxis.set_major_formatter(FuncFormatter(lambda v,_:f'{v:,.0f}'));bottom.set_ylabel('Drawdown (%)');bottom.set_xlabel('Exchange trading date')
 for ax in [top,bottom]:ax.grid(alpha=.2);ax.spines[['top','right']].set_visible(False)
 fig.suptitle('STAGE002 / INDEPENDENT REVIEW: PASS WITH LIMITATIONS / NO PROMOTION\n2020-01-02 to 2026-10-29; original19; CNY150,000 each; no addon\nCompleted weekly MA5/10; daily next-open; zero commission; configured static margin x1.65',fontsize=10.5,fontweight='bold');fig.tight_layout(rect=[0,0,1,.89]);fig.savefig(target,dpi=160);plt.close(fig)
 (L/'stages/stage002_reviewed_visual_receipt.json').write_text(json.dumps(dict(independent_review=r['status'],sources_sha256=sources,image_sha256=sha(target),points_per_curve=1652,financial_replays=0),indent=2)+'\n');print(target)
if __name__=='__main__':main()
