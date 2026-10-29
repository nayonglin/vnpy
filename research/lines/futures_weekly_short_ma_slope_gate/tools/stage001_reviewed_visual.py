"""Publish a separately signed display image; preserve pending-review originals."""
from pathlib import Path
import os,json,hashlib
os.environ.setdefault('MPLCONFIGDIR','/private/tmp/weekly-short-ma-slope-mpl')
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
LINE=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 review=LINE/'stages/stage001_independent_final.json'
 result=json.loads(review.read_text())
 # Require a signed independent verdict, rather than author assertions.
 if result.get('status')!='PASS_WITH_LIMITATIONS' or not all(result.get('checks',{}).values()) or any(result.get(k)!=0 for k in ['P0','P1','P2']):raise ValueError('independent_review_not_passed')
 target=LINE/'artifacts/stage001_equity_drawdown_reviewed.png'
 if target.exists():raise ValueError('immutable_reviewed_figure_exists')
 fig,(top,bottom)=plt.subplots(2,1,figsize=(12,7.2),sharex=True,gridspec_kw={'height_ratios':[2,1]})
 sources={str(review):sha(review)};counts={}
 for arm,color,label in [('A','#2467a6','A: original19 weekly base, no addon'),('C','#c36f19','C: short MA5/10 slope gate, no addon')]:
  path=LINE/f'outputs/stage001_{arm}_attempt003/daily.csv';d=pd.read_csv(path);dates=pd.to_datetime(d.date);e=d.account_equity.to_numpy()
  if len(d)!=1652 or str(dates.iloc[-1])[:10]!='2026-10-29':raise ValueError('full_curve_required')
  peak=np.maximum.accumulate(np.r_[150000,e])[1:];top.plot(dates,e,lw=1.3,color=color,label=label);bottom.plot(dates,(e/peak-1)*100,lw=1.0,color=color)
  sources[str(path)]=sha(path);counts[arm]=len(d)
 top.axhline(150000,color='#888',lw=.7,ls='--');top.legend(frameon=False,fontsize=9);top.set_ylabel('Modeled equity (CNY)');top.yaxis.set_major_formatter(FuncFormatter(lambda v,_:f'{v:,.0f}'))
 bottom.set_ylabel('Drawdown (%)');bottom.set_xlabel('Exchange trading date')
 for ax in [top,bottom]:ax.grid(alpha=.2);ax.spines[['top','right']].set_visible(False)
 top.margins(x=.01)
 fig.suptitle('STAGE001 / INDEPENDENT REVIEW: PASS WITH LIMITATIONS / NO PROMOTION\n2020-01-02 to 2026-10-29; original19; CNY150,000 each; completed weekly MA5/10/20\nDaily next-open model; zero commission; configured static margin x1.65',fontsize=10.5,fontweight='bold')
 fig.tight_layout(rect=[0,0,1,.89]);fig.savefig(target,dpi=160);plt.close(fig)
 receipt=dict(schema='stage001_reviewed_visual_receipt_v1',independent_review='PASS_WITH_LIMITATIONS',production_qualified=False,source_sha256=sources,curve_points=counts,image_path=str(target),image_sha256=sha(target),financial_replays=0,unmodified_curve_values=True,pending_figure_preserved=True)
 (LINE/'stages/stage001_reviewed_visual_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
if __name__=='__main__':main()
