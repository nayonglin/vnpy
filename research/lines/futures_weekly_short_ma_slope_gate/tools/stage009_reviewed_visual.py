"""Derive only five SHA-locked reviewed copies of the Stage009 pending figures.

No accounting cache, financial loader, engine or production module is imported.
The exact pending PNGs must first be reproduced from round-trip CSV input. Only
figure suptitle review-state text may then change; source files stay immutable.
"""
from __future__ import annotations
import argparse,hashlib,json,math,os,re,shutil,tempfile
from datetime import datetime,date
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import stage009_plots as plots

LINE=Path(__file__).resolve().parents[1]
STAGES=LINE/'stages'
FREEZE=STAGES/'stage009_freeze.json'
REVIEW=STAGES/'stage009_independent_final.json'
PENDING=LINE/'artifacts/stage009_multistart'
REVIEWED=LINE/'artifacts/stage009_multistart_reviewed'
RECEIPT=STAGES/'stage009_reviewed_visual_receipt.json'
VARIANT_SCOPE=('A_idle','A_R','C_idle','C_R')
SAVE_KWARGS=dict(dpi=160,bbox_inches='tight')

def require(value,label):
 if not value:raise ValueError('stage009_reviewed_visual:'+label)

def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for block in iter(lambda:f.read(4194304),b''):h.update(block)
 return h.hexdigest()

def load(path):return json.loads(Path(path).read_text())

class SourceBook:
 def __init__(self):self.files={}
 def add(self,path,expected=None):
  path=str(Path(path).resolve());require(Path(path).is_file(),'missing_source:'+path)
  if path not in self.files:self.files[path]=sha(path)
  require(expected is None or self.files[path]==expected,'source_sha_mismatch:'+path)
  return self.files[path]
 def add_map(self,mapping):
  require(isinstance(mapping,dict),'source_map_required')
  for path,digest in mapping.items():self.add(path,digest)
 def verify(self):
  for path,digest in self.files.items():require(Path(path).is_file() and sha(path)==digest,'source_changed:'+path)

def validate_review(path,expected_sha):
 require(isinstance(expected_sha,str) and re.fullmatch('[0-9a-f]{64}',expected_sha) is not None,'explicit_locked_sha_required')
 require(sha(path)==expected_sha,'locked_review_sha_mismatch')
 review=load(path)
 require(review.get('status') in {'PASS','PASS_WITH_LIMITATIONS'} and all(review.get(k)==0 for k in ['P0','P1','P2','failures']),'independent_review_not_passed')
 return review

def validate_review_binding(review,comparison,comparison_sha,freeze_sha,source_head):
 scope=dict(arm_windows=46,paired_windows=46,independent_starts=23,summary_rows=92,total_daily_points=141996)
 require(all(review.get(k)==v and comparison.get(k)==v for k,v in scope.items()),'review_report_scope_mismatch')
 require(review.get('freeze_sha256')==comparison.get('freeze_sha256')==freeze_sha,'review_report_freeze_mismatch')
 require(review.get('source_head')==comparison.get('source_head')==comparison.get('financial_source_head')==source_head,'review_report_source_head_mismatch')
 require(review.get('report_comparison_sha256')==comparison_sha,'review_report_comparison_sha_mismatch')
 expected=dict(complete_pairs_per_arm=22,observation_per_arm=1,expected_new_engines=46,total_initial_capital=300000,engine_initial_capital=150000,reserve_initial_capital=150000)
 require(all(comparison.get(k)==v for k,v in expected.items()),'report_complete_same_capital_scope')
 require(comparison.get('starts')==list(plots.STARTS) and comparison.get('cutoff')==plots.CUTOFF and comparison.get('variants')==list(VARIANT_SCOPE),'report_exact_starts_cutoff_variants')
 require(comparison.get('five_figures')==list(plots.FIGURE_NAMES) and comparison.get('promotion_decision')=='NO_PROMOTION','report_five_and_no_promotion')
 return True

def require_five_names(names):
 require(len(names)==5 and set(names)==set(plots.FIGURE_NAMES),'exact_five_figure_names')

def figure_paths(folder):return [Path(folder)/name for name in plots.FIGURE_NAMES]

def verify_pending_manifest(folder,book):
 folder=Path(folder);manifest_path=folder/'delivery_manifest.json';manifest=load(manifest_path);mapping=manifest.get('files_sha256',{})
 require(manifest.get('self_hash_excluded') is True and isinstance(mapping,dict) and mapping,'pending_manifest_required')
 require(all(isinstance(name,str) and Path(name).name==name and name!='delivery_manifest.json' for name in mapping),'pending_manifest_safe_names')
 require(all(p.is_file() for p in folder.iterdir()),'pending_flat_files_only')
 require({p.name for p in folder.iterdir()}==set(mapping)|{'delivery_manifest.json'},'pending_manifest_exact_file_set')
 for name,digest in mapping.items():book.add(folder/name,digest)
 book.add(manifest_path)
 return {str(p.resolve()):book.files[str(p.resolve())] for p in folder.iterdir()}

def _safe(value):
 if isinstance(value,np.generic):return _safe(value.item())
 if isinstance(value,(datetime,date,pd.Timestamp)):return value.isoformat()
 if isinstance(value,float) and not math.isfinite(value):return {'nonfinite_artist':str(value)}
 if isinstance(value,dict):return {str(k):_safe(v) for k,v in value.items()}
 if isinstance(value,(tuple,list)):return [_safe(x) for x in value]
 if isinstance(value,np.ndarray):return _array(value)
 return value

def _array(value):
 a=np.ma.asarray(value)
 return dict(shape=list(a.shape),dtype=str(a.dtype),values=_safe(a.tolist()),mask=np.ma.getmaskarray(a).tolist())

def _text(value,include_text=True):
 result=dict(position=value.get_position(),size=value.get_fontsize(),color=value.get_color(),weight=value.get_fontweight(),style=value.get_fontstyle(),family=value.get_fontfamily(),rotation=value.get_rotation(),ha=value.get_ha(),va=value.get_va(),visible=value.get_visible(),alpha=value.get_alpha())
 if include_text:result['text']=value.get_text()
 return result

def _legend(value):
 if value is None:return None
 return dict(texts=[_text(t) for t in value.get_texts()],title=_text(value.get_title()),position=value.get_window_extent().bounds,visible=value.get_visible())

def artist_signature(fig):
 """Every chart artist and figure annotation except the suptitle's text."""
 fig.canvas.draw();axes=[]
 for ax in fig.axes:
  tables=[]
  for table in ax.tables:
   tables.append([(str(key),_text(cell.get_text()),cell.get_xy(),cell.get_width(),cell.get_height(),cell.get_facecolor(),cell.get_edgecolor(),cell.get_linewidth()) for key,cell in sorted(table.get_celld().items())])
  collections=[]
  for item in ax.collections:
   collections.append(dict(type=type(item).__name__,offsets=_array(item.get_offsets()),array=None if item.get_array() is None else _array(item.get_array()),paths=[dict(vertices=_array(p.vertices),codes=None if p.codes is None else _array(p.codes)) for p in item.get_paths()],face=_array(item.get_facecolors()),edge=_array(item.get_edgecolors()),widths=_array(item.get_linewidths()),sizes=None if not hasattr(item,'get_sizes') else _array(item.get_sizes()),transform=_array(item.get_transform().get_matrix()),offset_transform=_array(item.get_offset_transform().get_matrix()),alpha=item.get_alpha(),clim=item.get_clim()))
  axes.append(dict(xlim=ax.get_xlim(),ylim=ax.get_ylim(),position=ax.get_position().bounds,xscale=ax.get_xscale(),yscale=ax.get_yscale(),visible=ax.get_visible(),xlabel=ax.get_xlabel(),ylabel=ax.get_ylabel(),title=ax.get_title(),xticks=_array(ax.get_xticks()),yticks=_array(ax.get_yticks()),xticklabels=[_text(t) for t in ax.get_xticklabels()],yticklabels=[_text(t) for t in ax.get_yticklabels()],legend=_legend(ax.get_legend()),lines=[dict(x=_array(item.get_xdata()),y=_array(item.get_ydata()),color=item.get_color(),style=item.get_linestyle(),width=item.get_linewidth(),marker=item.get_marker(),label=item.get_label(),alpha=item.get_alpha(),visible=item.get_visible()) for item in ax.lines],images=[dict(data=_array(item.get_array()),clim=item.get_clim(),cmap=item.get_cmap().name,extent=item.get_extent(),alpha=item.get_alpha()) for item in ax.images],patches=[dict(type=type(item).__name__,vertices=_array(item.get_path().vertices),codes=None if item.get_path().codes is None else _array(item.get_path().codes),transform=_array(item.get_transform().get_matrix()),face=item.get_facecolor(),edge=item.get_edgecolor(),width=item.get_linewidth(),alpha=item.get_alpha(),visible=item.get_visible()) for item in ax.patches],collections=collections,texts=[_text(t) for t in ax.texts],tables=tables))
 result=dict(size=fig.get_size_inches().tolist(),dpi=fig.dpi,face=fig.get_facecolor(),axes=axes,texts=[_text(t) for t in fig.texts if t is not fig._suptitle],legends=[_legend(v) for v in fig.legends],suptitle_style=_text(fig._suptitle,include_text=False))
 return json.dumps(_safe(result),sort_keys=True,allow_nan=False,separators=(',',':'))

def assert_title_only_change(pending,reviewed):
 before=pending._suptitle.get_text();after=reviewed._suptitle.get_text()
 require(before.count('INDEPENDENT REVIEW PENDING')==1 and after==before.replace('INDEPENDENT REVIEW PENDING','REVIEWED WITH LIMITATIONS',1),'only_review_state_suptitle_change')
 a,b=artist_signature(pending),artist_signature(reviewed)
 require(a==b,'axes_lines_images_bars_scatter_tables_or_annotations_changed')
 return hashlib.sha256(a.encode()).hexdigest()

def atomic_publish(prepared_figures,destination,prepared_receipt,receipt_path,guard):
 """Exclusive final receipt is the commit marker; never overwrite old delivery."""
 prepared_figures=Path(prepared_figures);destination=Path(destination);prepared_receipt=Path(prepared_receipt);receipt_path=Path(receipt_path)
 require(not destination.exists() and not receipt_path.exists(),'immutable_reviewed_delivery_exists')
 require(all(p.is_file() for p in prepared_figures.iterdir()),'prepared_five_flat_files_only')
 require_five_names([p.name for p in prepared_figures.iterdir() if p.is_file()]);published=[]
 try:
  guard();require(not destination.exists() and not receipt_path.exists(),'delivery_appeared_during_preparation')
  os.rename(prepared_figures,destination);published.append(destination)
  guard();os.link(prepared_receipt,receipt_path);published.append(receipt_path)
  guard()
 except BaseException:
  for path in reversed(published):
   if path.is_dir():shutil.rmtree(path)
   elif path.exists():path.unlink()
  raise


def main(expected_sha):
 require(not REVIEWED.exists() and not RECEIPT.exists(),'immutable_reviewed_delivery_exists')
 review=validate_review(REVIEW,expected_sha);book=SourceBook();book.add(REVIEW,expected_sha);freeze=load(FREEZE);freeze_sha=book.add(FREEZE)
 require(freeze.get('starts')==list(plots.STARTS) and freeze.get('cutoff')==plots.CUTOFF and freeze.get('planned_arm_windows')==freeze.get('planned_financial_replays')==46,'actual_frozen46_23_scope')
 comparison=load(PENDING/'comparison.json');comparison_sha=sha(PENDING/'comparison.json')
 validate_review_binding(review,comparison,comparison_sha,freeze_sha,freeze['source_head'])
 pending_hashes=verify_pending_manifest(PENDING,book)
 require(review.get('report_directory')==str(PENDING) and review.get('report_files_sha256')==pending_hashes,'review_exact_pending_file_snapshot')
 source_map=comparison.get('source_files_sha256',{});review_sources=review.get('source_files_sha256',{})
 require(load(PENDING/'source_hashes.json')==source_map and all(review_sources.get(p)==digest for p,digest in source_map.items()),'review_report_source_bindings')
 book.add_map(source_map);book.add_map(review_sources);book.add_map(freeze.get('source_files_sha256',{}))
 # The final independent review must bind this exact transformation and tests.
 for path in [Path(__file__),Path(__file__).with_name('test_stage009_reviewed_visual.py')]:
  require(review_sources.get(str(path.resolve()))==sha(path),'reviewed_visual_source_not_independently_bound:'+path.name)
  book.add(path)
 for path in [Path(plots.__file__),Path(plots.__file__).with_name('test_stage009_plots.py'),Path(plots.__file__).with_name('stage009_report.py'),Path(plots.__file__).with_name('test_stage009_report.py')]:
  require(source_map.get(str(path.resolve()))==sha(path),'pending_renderer_source_not_current:'+path.name)
  book.add(path)
 # Explicit round-trip parser retains the floats used before CSV publication.
 summary=pd.read_csv(PENDING/'summary.csv',float_precision='round_trip')
 paired=pd.read_csv(PENDING/'paired.csv',float_precision='round_trip')
 daily=pd.read_csv(PENDING/'all_daily.csv',float_precision='round_trip')
 book.verify();pending_figures=plots.render_five(summary,paired,daily,reviewed=False);reviewed_figures={}
 try:
  require_five_names(list(pending_figures));book.verify();validate_review(REVIEW,expected_sha)
  with tempfile.TemporaryDirectory(prefix='.stage009_reviewed_',dir=REVIEWED.parent) as temporary:
   root=Path(temporary);rebuilt=root/'pending';prepared=root/'reviewed';rebuilt.mkdir();prepared.mkdir()
   for name,fig in pending_figures.items():fig.savefig(rebuilt/name,**SAVE_KWARGS)
   pending_checks={name:sha(rebuilt/name)==pending_hashes[str((PENDING/name).resolve())] for name in plots.FIGURE_NAMES}
   require(all(pending_checks.values()),'regenerated_pending_png_not_byte_identical')
   reviewed_figures=plots.render_five(summary,paired,daily,reviewed=True);require_five_names(list(reviewed_figures))
   signature_hashes={name:assert_title_only_change(pending_figures[name],reviewed_figures[name]) for name in plots.FIGURE_NAMES}
   for name,fig in reviewed_figures.items():fig.savefig(prepared/name,**SAVE_KWARGS)
   # Saving must not introduce a layout/data change either.
   require(all(signature_hashes[name]==assert_title_only_change(pending_figures[name],reviewed_figures[name]) for name in plots.FIGURE_NAMES),'post_save_artist_drift')
   reviewed_hashes={str((REVIEWED/name).resolve()):sha(prepared/name) for name in plots.FIGURE_NAMES}
   result=dict(schema='stage009_five_reviewed_visual_receipt_v1',status='PASS_FIVE_REVIEWED_COPIES_ONLY',generated_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),independent_review=str(REVIEW),independent_review_sha256=expected_sha,independent_review_verdict=review['status'],freeze_sha256=freeze_sha,report_comparison_sha256=comparison_sha,reviewed_figures_sha256=reviewed_hashes,source_inputs_sha256=dict(book.files),pending_files_preserved=True,pending_figures_regenerated_byte_identical=pending_checks,axes_lines_images_bars_tables_identical={name:True for name in plots.FIGURE_NAMES},artist_signature_sha256=signature_hashes,arm_windows=46,paired_windows=46,independent_starts=23,summary_rows=92,total_daily_points=141996,complete_pairs_per_arm=22,observation_per_arm=1,only_change='Five suptitle review-state texts. All axes, lines, heatmaps, bars, scatter, tables, legends and other annotations identical.',promotion_decision='NO_PROMOTION',financial_replays=0,market_downloads=0,production_accesses=0)
   staged_receipt=root/'receipt.json';staged_receipt.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
   def guard():
    validate_review(REVIEW,expected_sha)
    require(all(p.is_file() for p in PENDING.iterdir()) and {str(p.resolve()) for p in PENDING.iterdir()}==set(pending_hashes),'pending_file_set_changed')
    book.verify()
   atomic_publish(prepared,REVIEWED,staged_receipt,RECEIPT,guard)
 finally:
  for fig in [*pending_figures.values(),*reviewed_figures.values()]:fig.clear()
 print(json.dumps(dict(status=result['status'],receipt=str(RECEIPT),receipt_sha256=sha(RECEIPT),reviewed_figures_sha256=reviewed_hashes,financial_replays=0),ensure_ascii=False))
 return result

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--locked-review-sha',required=True);args=parser.parse_args();main(args.locked_review_sha)
