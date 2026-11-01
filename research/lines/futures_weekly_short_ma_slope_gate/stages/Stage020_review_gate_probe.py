"""Adversarial receipt gate probe; stop before loader/render/output, never finance."""
from pathlib import Path
import importlib.util,json,tempfile,unittest
ROOT=Path(__file__).resolve().parents[4];TOOL=ROOT/'research/lines/futures_weekly_short_ma_slope_gate/tools/Stage020_ytd_recap.py'
class ReachedUnqualifiedLoader(RuntimeError):pass
class MinuteGate(unittest.TestCase):
 def test_rejected_receipt_stops_before_render_loader(self):
  spec=importlib.util.spec_from_file_location('reviewed_stage020',TOOL);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  with tempfile.TemporaryDirectory(prefix='Stage020_review_')as temp:
   p=Path(temp)/'rejected_receipt.json';p.write_text(json.dumps({'accepted':False,'status':'REJECTED','failures':['unqualified_minutes'],'qualified_csv_sha256':'0'*64}));m.MINUTE_RECEIPT=p
   def sentinel():raise ReachedUnqualifiedLoader('unqualified receipt reached downstream pure renderer loader')
   m.library=sentinel
   with self.assertRaises(ValueError):m.build(m.OUTPUT.with_name(m.OUTPUT.name+'_attempt999'))
if __name__=='__main__':unittest.main()
