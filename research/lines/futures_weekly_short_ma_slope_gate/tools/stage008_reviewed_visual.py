"""Display-only five-figure clone after explicit SHA-locked independent review.

Reads existing financial caches and pending tables; never calls financial loaders.
Pending report and every source byte are verified before and after derivation.
"""
from __future__ import annotations
import argparse,hashlib,json,os,tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import stage008_report as report
LINE=report.LINE;REVIEW=LINE/'stages/stage008_independent_final.json';REVIEWED=LINE/'artifacts/stage008_multistart_reviewed';RECEIPT=LINE/'stages/stage008_reviewed_visual_receipt.json'

def figure_paths(folder):return [Path(folder)/name for name in report.FIGURE_NAMES]

def validate_review(path,expected_sha):
 if not isinstance(expected_sha,str) or len(expected_sha)!=64:raise ValueError('explicit_locked_sha_required')
 if report.acct.sha(path)!=expected_sha:raise ValueError('locked_review_sha_mismatch')
 d=json.loads(Path(path).read_text())
 if d.get('status')!='PASS_WITH_LIMITATIONS' or any(d.get(k)!=0 for k in ['P0','P1','P2']) or d.get('failures',0)!=0:raise ValueError('independent_review_not_passed')
 return d

def validate_review_binding(verdict,doc,comparison_sha):
 if verdict.get('report_comparison_sha256')!=comparison_sha or verdict.get('freeze_sha256')!=doc.get('freeze_sha256') or verdict.get('arm_windows')!=46 or verdict.get('paired_windows')!=23 or doc.get('arm_windows')!=46 or doc.get('independent_pairs')!=23:raise ValueError('review_report_identity_mismatch')
 return True

def _bytes_sha(value):return hashlib.sha256(value).hexdigest()

def _artist_signature(fig):
 """Everything drawn in axes; figure suptitle deliberately excluded."""
 def array(x):
  a=np.ma.asarray(x)
  return dict(shape=list(a.shape),dtype=str(a.dtype),values=a.tolist(),mask=np.ma.getmaskarray(a).tolist())
 result=[]
 for ax in fig.axes:
  result.append(dict(xlim=ax.get_xlim(),ylim=ax.get_ylim(),position=ax.get_position().bounds,xscale=ax.get_xscale(),yscale=ax.get_yscale(),xlabel=ax.get_xlabel(),ylabel=ax.get_ylabel(),title=ax.get_title(),lines=[dict(x=array(x.get_xdata()),y=array(x.get_ydata()),color=x.get_color(),style=x.get_linestyle(),width=x.get_linewidth(),marker=x.get_marker(),label=x.get_label()) for x in ax.lines],images=[dict(data=array(x.get_array()),clim=x.get_clim(),cmap=x.get_cmap().name,extent=x.get_extent()) for x in ax.images],patches=[dict(type=type(x).__name__,vertices=array(x.get_path().vertices),transform=array(x.get_transform().get_matrix()),face=x.get_facecolor(),edge=x.get_edgecolor(),width=x.get_linewidth()) for x in ax.patches],texts=[dict(text=x.get_text(),position=x.get_position(),size=x.get_fontsize(),color=x.get_color()) for x in ax.texts],tables=[[(str(key),cell.get_text().get_text(),cell.get_xy(),cell.get_width(),cell.get_height()) for key,cell in table.get_celld().items()] for table in ax.tables]))
 return json.dumps(report.acct.safe(result),sort_keys=True,allow_nan=False)

def main(expected_sha):
 if REVIEWED.exists() or RECEIPT.exists():raise ValueError('immutable_reviewed_delivery_exists')
 verdict=validate_review(REVIEW,expected_sha);pending=report.OUT;comparison=pending/'comparison.json';doc=json.loads(comparison.read_text());manifest=json.loads((pending/'delivery_manifest.json').read_text())
 if doc.get('arm_windows')!=46 or doc.get('complete_vote_pairs')!=22 or doc.get('observation_pairs')!=1 or doc.get('five_figures')!=report.FIGURE_NAMES or doc.get('freeze_sha256')!=report.acct.FREEZE_SHA:raise ValueError('complete_pending_report_required')
 validate_review_binding(verdict,doc,report.acct.sha(comparison))
 pending_hashes={str(p.resolve()):report.acct.sha(p) for p in pending.iterdir() if p.is_file()}
 report.acct.verify_sources({str(pending/name):value for name,value in manifest['files_sha256'].items()});report.acct.verify_sources(doc['output_files_sha256']);report.acct.verify_sources(doc['source_files_sha256'])
 for p in [Path(report.__file__),Path(report.__file__).with_name('test_stage008_report.py')]:
  if doc['source_files_sha256'].get(str(p.resolve()))!=report.acct.sha(p):raise ValueError('pending_renderer_source_not_current')
 caches={}
 for start in report.acct.STARTS:
  for arm in ['A','C']:
   path=report.acct.cache_path(start,arm);ledger=path/'ledger.json';daily=path/'daily.csv'
   for source in [ledger,daily]:
    if doc['source_files_sha256'].get(str(source.resolve()))!=report.acct.sha(source):raise ValueError('cache_source_not_bound_to_pending_report')
   d=json.loads(ledger.read_text());d['_daily']=pd.read_csv(daily);d['_daily']['date']=pd.to_datetime(d['_daily'].date);d['_cache_path']=path;caches[(start,arm)]=d
 summary=pd.DataFrame([report.flatten_cache(caches[(s,a)]) for s in report.acct.STARTS for a in ['A','C']]);paired=report.make_pairs(summary);cohorts=report.aggregate(summary,paired);weakest=report.weakest_windows(summary);tables={'summary.csv':summary,'paired.csv':paired,'cohort_summary.csv':cohorts,'weakest_windows.csv':weakest,'all_daily.csv':pd.concat([d['_daily'].assign(start=s,arm=a) for (s,a),d in caches.items()],ignore_index=True)}
 table_checks={name:_bytes_sha(df.to_csv(index=False).encode())==report.acct.sha(pending/name) for name,df in tables.items()}
 if not all(table_checks.values()):raise ValueError('reconstructed_pending_table_changed')
 plt,_=report._plot_setup();captured=[];original=plt.subplots
 def capture(*a,**kw):
  result=original(*a,**kw);captured.append(result[0]);return result
 plt.subplots=capture
 try:
  with tempfile.TemporaryDirectory(prefix='.stage008_reviewed_',dir=REVIEWED.parent) as td:
   root=Path(td);regenerated=root/'pending';reviewed=root/'reviewed';regenerated.mkdir();reviewed.mkdir();report.render_figures(caches,summary,paired,cohorts,weakest,regenerated,reviewed=False);report.render_figures(caches,summary,paired,cohorts,weakest,reviewed,reviewed=True)
   pending_checks={name:report.acct.sha(regenerated/name)==report.acct.sha(pending/name) for name in report.FIGURE_NAMES}
   if len(captured)!=10:raise ValueError('exact_five_plus_five_figures_required')
   axes_checks={name:_artist_signature(captured[i])==_artist_signature(captured[i+5]) for i,name in enumerate(report.FIGURE_NAMES)}
   if not all(pending_checks.values()) or not all(axes_checks.values()):raise ValueError('pending_or_reviewed_chart_changed_beyond_review_title')
   validate_review(REVIEW,expected_sha);report.acct.verify_sources(pending_hashes);report.acct.verify_sources(doc['source_files_sha256']);os.rename(reviewed,REVIEWED)
 finally:plt.subplots=original
 validate_review(REVIEW,expected_sha);reviewed_hashes={str(p.resolve()):report.acct.sha(p) for p in figure_paths(REVIEWED)}
 inputs={**pending_hashes,str(REVIEW.resolve()):expected_sha,str(Path(__file__).resolve()):report.acct.sha(__file__),str(Path(__file__).with_name('test_stage008_reviewed_visual.py').resolve()):report.acct.sha(Path(__file__).with_name('test_stage008_reviewed_visual.py'))}
 result=dict(schema='stage008_five_reviewed_visual_receipt_v1',status='PASS_FIVE_VISUAL_REVIEWED_COPIES_ONLY',generated_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),independent_review=str(REVIEW),independent_review_sha256=expected_sha,independent_review_verdict=verdict['status'],reviewed_figures_sha256=reviewed_hashes,source_inputs_sha256=inputs,pending_files_preserved=True,pending_figures_regenerated_byte_identical=pending_checks,axes_lines_images_bars_tables_identical=axes_checks,reconstructed_pending_tables_identical=table_checks,total_daily_points=doc['total_daily_points'],arm_windows=46,complete_vote_pairs=22,observation_pairs=1,only_change='Five figure suptitles updated from pending to reviewed; all financial data, axes, lines, images, bars and tables identical.',promotion_decision='NO_PROMOTION',financial_replays=0,market_downloads=0,production_accesses=0)
 report.acct.verify_sources(inputs);report.acct.write_json(RECEIPT,result);validate_review(REVIEW,expected_sha);print(json.dumps(dict(status=result['status'],reviewed_figures_sha256=reviewed_hashes,receipt=str(RECEIPT)),ensure_ascii=False));return result

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--locked-review-sha',required=True);args=ap.parse_args();main(args.locked_review_sha)
