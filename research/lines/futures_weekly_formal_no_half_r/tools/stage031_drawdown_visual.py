"""Read-only same-date equity/percentage drawdown explanatory figure."""
from pathlib import Path
import hashlib,json,os
import numpy as np
import pandas as pd
os.environ.setdefault('MPLCONFIGDIR','/private/tmp/weekly-research-mpl')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
ROOT=Path(__file__).resolve().parents[4]
LINE=ROOT/'research/lines/futures_weekly_formal_no_half_r'

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()

def main():
 out=LINE/'artifacts/stage031_same_window_drawdown.png'
 receipt=LINE/'outputs/stage031_visual/receipt.json'
 if out.exists() or receipt.exists():raise ValueError('immutable_output_exists')
 frozen=json.loads((LINE/'stages/stage030_delivery_manifest.json').read_text())['files_sha256']
 inputs={};data={}
 for label,attempt in [('B','R_attempt003'),('W','stage030_weekly_attempt001')]:
  path=LINE/'outputs'/attempt/'daily.csv';inputs[str(path)]=sha(path)
  assert frozen[str(path)]==inputs[str(path)]
  frame=pd.read_csv(path,usecols=['date','account_equity']);frame.date=pd.to_datetime(frame.date)
  frame=frame.loc[frame.date.between('2018-02-27','2020-04-09')].copy()
  data[label]=frame
 assert data['B'].date.equals(data['W'].date)
 assert len(data['B'])==516
 assert np.isclose(data['B'].account_equity.iloc[0],355885) and np.isclose(data['W'].account_equity.iloc[0],290665)
 assert np.isclose(data['B'].account_equity.iloc[-1],160520) and np.isclose(data['W'].account_equity.iloc[-1],114515)
 fig,axes=plt.subplots(2,1,figsize=(12,7.6),sharex=True,gridspec_kw={'height_ratios':[1.25,1]})
 for label,color,name in [('B','#2467a6','B: no 5% half exit'),('W','#388663','W: weekly 5% half exit')]:
  d=data[label];start=float(d.account_equity.iloc[0]);end=float(d.account_equity.iloc[-1]);loss=start-end
  axes[0].plot(d.date,d.account_equity,lw=1.5,color=color,label=f'{name}: {start:,.0f} to {end:,.0f}; loss {loss:,.0f}')
  axes[0].scatter(d.date.iloc[[0,-1]],d.account_equity.iloc[[0,-1]],color=color,s=24)
  axes[1].plot(d.date,(d.account_equity/start-1)*100,lw=1.5,color=color,label=f'{label}: {(end/start-1)*100:.2f}% from the same start date')
  axes[1].scatter(d.date.iloc[-1],(end/start-1)*100,color=color,s=24)
 for ax in axes:
  ax.grid(alpha=.22);ax.legend(loc='lower left',fontsize=9,frameon=False)
 axes[0].set_ylabel('Account equity (CNY)');axes[0].yaxis.set_major_formatter(FuncFormatter(lambda x,_:f'{x:,.0f}'))
 axes[1].set_ylabel('Change from 2018-02-27 (%)');axes[1].set_xlabel('Trading date')
 fig.suptitle("Why W's percentage drawdown is larger\nSame dates: 2018-02-27 to 2020-04-09",fontweight='bold',fontsize=13)
 fig.text(.5,.015,'W loses CNY19,215 less, but starts with CNY65,220 less equity. Own maximum drawdowns start on different dates.\nRead-only frozen ledgers; zero commission / fixed slippage / daily-open model; no strategy replay or promotion.',ha='center',fontsize=9)
 fig.tight_layout(rect=(0,.07,1,.92));out.parent.mkdir(parents=True,exist_ok=True);fig.savefig(out,dpi=155);plt.close(fig)
 inputs[str(Path(__file__).resolve())]=sha(__file__)
 assert all(sha(p)==digest for p,digest in inputs.items())
 receipt.parent.mkdir(parents=True,exist_ok=True)
 receipt.write_text(json.dumps(dict(schema='stage031_same_window_visual_v1',source_files_sha256=inputs,output=str(out),output_sha256=sha(out),calendar_rows=516,financial_replays=0,new_downloads=0,production_qualified=False),ensure_ascii=False,indent=2)+'\n')
 print(out)
if __name__=='__main__':main()
