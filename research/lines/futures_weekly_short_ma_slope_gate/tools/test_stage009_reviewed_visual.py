"""Pure gates and synthetic artist checks; never builds the real reviewed report."""
import os
os.environ.setdefault('MPLCONFIGDIR','/private/tmp/stage009-plots-mpl')
import json,tempfile,unittest
from pathlib import Path
from datetime import datetime
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
try:
 import stage009_reviewed_visual as visual
except ImportError:visual=None


def fixture(reviewed=False):
 f=Figure(figsize=(8,3));FigureCanvasAgg(f);a,b,c=f.subplots(1,3)
 a.plot([datetime(2026,1,x) for x in [1,2,3]],[1,2,3],label='curve');a.scatter([20454,20455],[2,3],s=[10,20]);a.legend();b.bar([0,1],[1,2]);b.table(cellText=[['source','42']],loc='bottom');c.imshow([[0,1],[2,3]])
 f.text(.02,.01,'Fixed footer');f.suptitle('STAGE009 | '+('REVIEWED WITH LIMITATIONS' if reviewed else 'INDEPENDENT REVIEW PENDING')+' | NO PROMOTION');return f

class ReviewedVisualTests(unittest.TestCase):
 def setUp(self):self.assertIsNotNone(visual,'Stage009 reviewed visual tool missing')
 def test_review_must_be_explicit_hash_locked_pass_with_zero_findings(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'review.json';good=dict(status='PASS_WITH_LIMITATIONS',P0=0,P1=0,P2=0,failures=0);p.write_text(json.dumps(good));visual.validate_review(p,visual.sha(p))
   with self.assertRaises(ValueError):visual.validate_review(p,'0'*64)
   for field,value in [('status','PENDING'),('P2',1),('failures',1)]:
    p.write_text(json.dumps(dict(good,**{field:value})))
    with self.assertRaises(ValueError):visual.validate_review(p,visual.sha(p))
 def test_exact_stage009_46pairs23starts_freeze_and_report_binding(self):
  doc=dict(freeze_sha256='a'*64,source_head='source',financial_source_head='source',arm_windows=46,paired_windows=46,independent_starts=23,summary_rows=92,total_daily_points=141996,complete_pairs_per_arm=22,observation_per_arm=1,expected_new_engines=46,total_initial_capital=300000,engine_initial_capital=150000,reserve_initial_capital=150000,cutoff='2026-10-29',starts=list(visual.plots.STARTS),variants=['A_idle','A_R','C_idle','C_R'],five_figures=list(visual.plots.FIGURE_NAMES),promotion_decision='NO_PROMOTION')
  verdict=dict(freeze_sha256='a'*64,source_head='source',report_comparison_sha256='b'*64,arm_windows=46,paired_windows=46,independent_starts=23,summary_rows=92,total_daily_points=141996)
  visual.validate_review_binding(verdict,doc,'b'*64,'a'*64,'source')
  for field,value in [('paired_windows',23),('independent_starts',22),('freeze_sha256','f'*64),('report_comparison_sha256','e'*64)]:
   with self.assertRaises(ValueError):visual.validate_review_binding(dict(verdict,**{field:value}),doc,'b'*64,'a'*64,'source')
 def test_only_suptitle_state_may_change_including_bars_scatter_images_tables(self):
  a,b=fixture(),fixture(True);self.assertEqual(len(visual.assert_title_only_change(a,b)),64);a.clear();b.clear()
  for mutate in [lambda f:f.axes[0].lines[0].set_ydata([1,2,4]),lambda f:f.axes[1].patches[0].set_height(4),lambda f:f.axes[2].images[0].set_data([[0,1],[2,4]]),lambda f:f.axes[0].collections[0].set_offsets([[20454,1],[20455,4]]),lambda f:f.axes[1].tables[0][(0,1)].get_text().set_text('43')]:
   a,b=fixture(),fixture(True);mutate(b)
   with self.assertRaises(ValueError):visual.assert_title_only_change(a,b)
   a.clear();b.clear()
 def test_exact_five_names_and_pending_manifest_no_hidden_file_drift(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);names=list(visual.plots.FIGURE_NAMES);visual.require_five_names(names)
   with self.assertRaises(ValueError):visual.require_five_names(names[:-1])
   (p/'x.csv').write_text('original');(p/'delivery_manifest.json').write_text(json.dumps(dict(files_sha256={'x.csv':visual.sha(p/'x.csv')},self_hash_excluded=True)));visual.verify_pending_manifest(p,visual.SourceBook())
   (p/'x.csv').write_text('changed')
   with self.assertRaises(ValueError):visual.verify_pending_manifest(p,visual.SourceBook())
 def test_atomic_publish_rollback_preserves_sources_and_rejects_existing(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);stage=root/'prepared';stage.mkdir()
   for name in visual.plots.FIGURE_NAMES:(stage/name).write_bytes(b'synthetic')
   receipt=root/'prepared.json';receipt.write_text('{}');source=root/'source';source.write_text('immutable');calls=[]
   def fail_after_rename():
    calls.append(1)
    if len(calls)==2:raise ValueError('source_changed')
   with self.assertRaises(ValueError):visual.atomic_publish(stage,root/'reviewed',receipt,root/'receipt.json',fail_after_rename)
   self.assertFalse((root/'reviewed').exists());self.assertFalse((root/'receipt.json').exists());self.assertEqual(source.read_text(),'immutable')
   target=root/'existing';target.mkdir()
   with self.assertRaises(ValueError):visual.atomic_publish(stage,target,receipt,root/'receipt.json',lambda:None)
if __name__=='__main__':unittest.main()
