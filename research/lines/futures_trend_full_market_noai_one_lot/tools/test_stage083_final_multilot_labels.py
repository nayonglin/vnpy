"""Final multi-lot labels survive canonical review regeneration, data unchanged."""
import importlib.util,json,unittest
from pathlib import Path
HERE=Path(__file__).parent

class FinalLabelsTest(unittest.TestCase):
    def setUp(self):
        path=HERE/'stage083_final_multilot_labels.py';self.assertTrue(path.exists(),'final labels adapter missing');spec=importlib.util.spec_from_file_location('labels083',path);self.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.m)

    def test_only_whitelisted_text_and_safely_escaped_disclosure(self):
        page="<html><body><div class=\"note\">old</div><script>const records=[];let metric=[['净利润',pnlValue],['平仓lot',m.lot_count]];</script></body></html>"
        changed=self.m.patch_html(page);self.assertEqual(self.m.unpatch_html(changed),page);self.assertIn("['交易手数',m.volume]",changed);self.assertIn('加权平均退出价',changed);self.assertIn('最后一笔实际成交价',changed)
        with self.assertRaisesRegex(ValueError,'already_patched'):self.m.patch_html(changed)
        with self.assertRaisesRegex(ValueError,'label_contract'):self.m.patch_html(page.replace("['平仓lot',m.lot_count]",''))

    def test_canonical_marker_actual_final_exit_and_weighted_move_are_distinct(self):
        records=[dict(meta=dict(vt_symbol='x',exit_source='x',exit_price=120.,exit_marker_price=120.,entry_price=100.,weighted_exit_price=350/3,price_change_pct=(350/3/100-1)*100))]
        proof=self.m.verify_exit_semantics(records);self.assertEqual(proof['records_checked'],1);self.assertEqual(proof['marker_price_basis'],'last_actual_exit_fill')
        records[0]['meta']['exit_marker_price']=350/3
        with self.assertRaisesRegex(ValueError,'actual_final_exit_marker'):self.m.verify_exit_semantics(records)

    def test_full_frozen_copy_preserves_every_nonHTML_byte_and_refuses_tamper(self):
        spec=importlib.util.spec_from_file_location('fixture083',HERE/'test_stage071_fractional_recap.py');fmod=importlib.util.module_from_spec(spec);spec.loader.exec_module(fmod);f=fmod.FractionalRecapTest('runTest');f.setUp();self.addCleanup(f.doCleanups);source,raw,root=f.source_fixture();parent=root/'reviewed';f.mod.enrich(source,raw,parent)
        summary=json.loads((parent/'summary.json').read_text());records=json.loads((parent/'records.json').read_text());page=f.renderer._html(records,summary);(parent/'index.html').write_text(page);summary['artifact_sha256']['index.html']=self.m.sha(parent/'index.html');(parent/'summary.json').write_text(json.dumps(summary))
        before={name:self.m.sha(parent/name) for name in summary['artifact_sha256']};out=root/'labels';r=self.m.generate(parent,out)
        for name,digest in before.items():
            if name!='index.html':self.assertEqual(self.m.sha(out/name),digest)
        spec=importlib.util.spec_from_file_location('audit083',HERE/'stage081_validate_fractional_display.py');audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit);self.assertGreater(audit.scripts(out,audit.NODE),0)
        self.assertEqual(json.loads((out/'records.json').read_text()),records);self.assertEqual(r['backtest_metrics'],summary['backtest_metrics']);self.assertTrue(r['final_multilot_display']['all_non_html_artifacts_byte_identical'])
        with self.assertRaises(FileExistsError):self.m.generate(parent,out)
        (parent/'records.json').write_text('[]')
        with self.assertRaisesRegex(ValueError,'parent_hash'):self.m.generate(parent,root/'other')

if __name__=='__main__':unittest.main()
