import json,tempfile,unittest
from pathlib import Path
import stage008_reviewed_visual as visual

class ReviewedVisualTests(unittest.TestCase):
 def test_requires_exact_locked_sha_and_passed_review(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'review.json';p.write_text(json.dumps(dict(status='PASS_WITH_LIMITATIONS',P0=0,P1=0,P2=0,failures=0)))
   self.assertEqual(visual.validate_review(p,visual.report.acct.sha(p))['status'],'PASS_WITH_LIMITATIONS')
   with self.assertRaisesRegex(ValueError,'locked_review_sha'):visual.validate_review(p,'0'*64)
 def test_failed_or_unlocked_review_cannot_make_reviewed_chart(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'review.json';p.write_text(json.dumps(dict(status='PASS_WITH_LIMITATIONS',P0=0,P1=1,P2=0)))
   with self.assertRaisesRegex(ValueError,'review_not_passed'):visual.validate_review(p,visual.report.acct.sha(p))
   with self.assertRaisesRegex(ValueError,'explicit_locked_sha'):visual.validate_review(p,None)
 def test_review_binds_exact_report_freeze_and_scope(self):
  doc=dict(freeze_sha256=visual.report.acct.FREEZE_SHA,arm_windows=46,independent_pairs=23)
  verdict=dict(report_comparison_sha256='a'*64,freeze_sha256=doc['freeze_sha256'],arm_windows=46,paired_windows=23)
  self.assertTrue(visual.validate_review_binding(verdict,doc,'a'*64))
  for key,value in [('report_comparison_sha256','b'*64),('freeze_sha256','b'*64),('arm_windows',44),('paired_windows',22)]:
   bad=dict(verdict);bad[key]=value
   with self.subTest(key=key),self.assertRaisesRegex(ValueError,'review_report_identity'):visual.validate_review_binding(bad,doc,'a'*64)
 def test_axis_signature_detects_bar_height_change(self):
  plt,_=visual.report._plot_setup();a,ax=plt.subplots();b,bx=plt.subplots();ax.bar([0],[1]);bx.bar([0],[2]);ax.set_ylim(0,3);bx.set_ylim(0,3)
  self.assertNotEqual(visual._artist_signature(a),visual._artist_signature(b));plt.close(a);plt.close(b)
 def test_exact_five_figure_receipt_contract(self):
  names=visual.report.FIGURE_NAMES
  self.assertEqual(len(names),5)
  self.assertEqual(visual.REVIEWED.name,'stage008_multistart_reviewed')
  self.assertEqual(visual.RECEIPT.name,'stage008_reviewed_visual_receipt.json')
  self.assertEqual(visual.figure_paths(visual.REVIEWED),[visual.REVIEWED/x for x in names])

if __name__=='__main__':unittest.main()
