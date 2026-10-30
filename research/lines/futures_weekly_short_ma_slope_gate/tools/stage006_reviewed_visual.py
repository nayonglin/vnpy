"""Display-only reviewed clone of Stage006 chart; source/pending artifacts stay frozen."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import json,tempfile
import numpy as np
import pandas as pd
from stage006_report import LINE,OUT,FIGURE,PATHS,plot,nav_drawdown,sha,verify_sources

def main():
 review=LINE/'stages/stage006_independent_final.json';out=LINE/'artifacts/stage006_nav_drawdown_reviewed.png';receipt=LINE/'stages/stage006_reviewed_visual_receipt.json'
 if out.exists() or receipt.exists():raise ValueError('immutable_reviewed_visual_exists')
 verdict=json.loads(review.read_text())
 if verdict.get('status')!='PASS_WITH_LIMITATIONS' or any(verdict.get(k)!=0 for k in ['P0','P1','P2']) or verdict.get('failures',0)!=0:raise ValueError('independent_final_not_passed')
 comparison=OUT/'comparison.json';doc=json.loads(comparison.read_text());verify_sources(doc['output_files_sha256'])
 inputs={str(p):sha(p) for p in [review,comparison,FIGURE,Path(__file__),Path(__file__).with_name('stage006_report.py'),OUT/'nav_drawdown.csv']}
 ledgers={};deviations={};curves=pd.read_csv(OUT/'nav_drawdown.csv')
 for role,run in PATHS.items():
  source=run/'daily.csv';csv=OUT/f'{role}_daily.csv';inputs[str(source)]=sha(source);inputs[str(csv)]=sha(csv)
  if doc['source_files_sha256'].get(str(source))!=inputs[str(source)]:raise ValueError('source daily not bound to frozen report')
  d=pd.read_csv(source,usecols=['date','account_equity'],low_memory=False);d['date']=pd.to_datetime(d.date.astype(str).str[:10]);ledgers[role]={'daily':d}
  nav,dd=nav_drawdown(d.account_equity);c=curves.loc[curves.role.eq(role)]
  if list(d.date.dt.strftime('%Y-%m-%d'))!=list(c.date):raise ValueError('curve calendar changed')
  deviations[role]=dict(points=len(d),max_nav_error=float(np.max(np.abs(nav-c.nav.to_numpy()))),max_drawdown_error=float(np.max(np.abs(dd-c.drawdown_pct.to_numpy()))))
  if max(deviations[role]['max_nav_error'],deviations[role]['max_drawdown_error'])>1e-12:raise ValueError('curve values changed')
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 captured=[];original=plt.subplots
 def capture(*a,**kw):
  result=original(*a,**kw);captured.append(result[0]);return result
 plt.subplots=capture
 try:
  with tempfile.TemporaryDirectory(prefix='stage006_reviewed_visual_') as tmp:
   regenerated=Path(tmp)/'pending.png';plot(ledgers,regenerated,reviewed=False);plot(ledgers,out,reviewed=True);pending_regenerated_matches=sha(regenerated)==sha(FIGURE)
 finally:plt.subplots=original
 a,b=captured;checks=[]
 for index,(ax,bx) in enumerate(zip(a.axes,b.axes)):
  checks.append(dict(axis=index,xlim_identical=ax.get_xlim()==bx.get_xlim(),ylim_identical=ax.get_ylim()==bx.get_ylim(),position_identical=ax.get_position().bounds==bx.get_position().bounds,line_count=len(ax.lines),line_values_identical=len(ax.lines)==len(bx.lines) and all(np.array_equal(x.get_xdata(),y.get_xdata()) and np.array_equal(x.get_ydata(),y.get_ydata()) and x.get_color()==y.get_color() and x.get_linestyle()==y.get_linestyle() and x.get_linewidth()==y.get_linewidth() for x,y in zip(ax.lines,bx.lines))))
 if not pending_regenerated_matches or any(not all(v for k,v in row.items() if k.endswith('_identical')) for row in checks):raise ValueError('pending_or_reviewed_chart_differs_beyond_title')
 verify_sources(inputs)
 result=dict(schema='stage006_reviewed_visual_receipt_v1',status='PASS_VISUAL_REVIEWED_COPY_ONLY',generated_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),independent_review=str(review),independent_review_sha256=sha(review),independent_review_verdict=verdict['status'],strategy_promotion_decision='NO_PROMOTION',source_inputs_sha256=inputs,reviewed_figure=str(out),reviewed_figure_sha256=sha(out),pending_figure_bytes_preserved=True,pending_regenerated_sha_matches_original=pending_regenerated_matches,axes_and_lines=checks,curve_comparison=deviations,only_change='title review status updated; all chart data, axes, lines and styles identical',financial_replays=0,market_downloads=0,production_accesses=0)
 receipt.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
