"""Small source-audit counterexamples; no actual source reads/network/financial work."""
import importlib.util
from pathlib import Path
import unittest
import json

SOURCE=Path(__file__).with_name('stage181_warehouse_archive_review.py')


class SourceReviewTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SOURCE.exists(),'independent181 reviewer missing')
        spec=importlib.util.spec_from_file_location('independent181_fixture',SOURCE)
        self.r=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.r)

    def test_empty_list_is_an_empty_source_report_not_zero_inventory(self):
        r=self.r.inspect_source(b'{"o_cursor":[],"report_date":"20140519"}','json','20140519')
        self.assertTrue(r['envelope']['expected_envelope'])
        self.assertEqual(r['envelope']['date_state'],'matched')
        self.assertEqual(r['structure']['cursor_rows'],0)
        self.assertTrue(r['structure']['empty_cursor'])
        self.assertFalse(r['structure']['inventory_zero_inferred'])
        other=self.r.inspect_source(b'{"wrong_cursor":[]}', 'json','20140519')
        self.assertFalse(other['envelope']['expected_envelope'])
        self.assertIsNone(other['structure']['cursor_rows'])

    def test_all_row_keysets_and_nonobjects_survive_without_numeric_parsing(self):
        body=json.dumps(dict(o_cursor=[dict(VARID='cu',WRTWGHTS='not a number'),dict(VARID='ag',WGHTUNIT='1'),'nonobject'],o_tradingday='20140520',update_date='later archive clock')).encode()
        r=self.r.inspect_source(body,'json','20140519')
        self.assertEqual(r['envelope']['date_state'],'conflict')
        self.assertEqual(r['structure']['cursor_rows'],3)
        self.assertEqual(r['structure']['nonobject_row_types'],{'str':1})
        self.assertEqual(sum(v['count'] for v in r['structure']['row_keysets']),2)
        self.assertEqual(r['structure']['archive_update_date'],'later archive clock')
        self.assertNotIn('warehouse_quantity',r['structure'])

    def test_html_uses_visible_intro_and_report_headers_not_dates_in_data_or_script(self):
        b='''<table class="content_intro"><tr><td>2025-11-18<script>2020-01-01</script></td></tr></table>
        <table><tr><th>地区</th><th>交割仓库</th><th>本日数量</th><th>增减</th></tr>
        <tr><td>改名于2019-01-01</td><td>库</td><td>not numeric</td><td>—</td></tr></table>'''.encode()
        r=self.r.inspect_source(b,'html','20251118')
        self.assertTrue(r['envelope']['expected_envelope']);self.assertEqual(r['envelope']['report_dates'],{'intro':['20251118']})
        self.assertEqual(r['structure']['table_count'],2)
        self.assertEqual(r['structure']['report_header_table_count'],1)
        error=self.r.inspect_source(b'<table><tr><td>HTTP200 error</td></tr></table>','html','20251118')
        self.assertFalse(error['envelope']['expected_envelope'])

    def test_explicit_bad_date_is_not_treated_as_absent(self):
        r=self.r.inspect_source(b'{"o_cursor":[],"report_date":"2014-99-99"}','json','20140519')
        self.assertEqual(r['envelope']['date_state'],'unparseable')
        absent=self.r.inspect_source(b'{"o_cursor":[],"report_date":null}','json','20140519')
        self.assertEqual(absent['envelope']['date_state'],'absent')

    def test_new_success_after_first_failure_cannot_be_hidden(self):
        rows=[dict(sequence_index=0,date='20140519',action='new_get',attempt=1,state='failed_http_or_network'),dict(sequence_index=1,date='20140520',action='new_get',attempt=0,state='not_attempted_after_stop'),dict(sequence_index=2,date='20200102',action='reuse',attempt=0,state='reused_binding_verified')]
        self.r.validate_stop_order(rows,'stopped')
        rows[1].update(attempt=1,state='http200_expected_envelope')
        with self.assertRaises(AssertionError):self.r.validate_stop_order(rows,'stopped')

    def test_partial_or_failed_body_is_not_a_certified_empty_report(self):
        structure=self.r.inspect_source(b'{"o_cursor":[]}', 'json','20140519')['structure']
        observations=[dict(date='20140519',format='json',body=dict(complete=True),archive_state='http200_expected_envelope',structure=structure),dict(date='20140520',format='json',body=dict(complete=False),archive_state='failed_bound_or_budget',structure=structure)]
        groups=self.r.group_structures(observations)
        self.assertEqual(groups['empty_cursor_dates'],['20140519'])
        self.assertEqual(groups['partial_or_failed_dates'],['20140520'])


if __name__=='__main__':unittest.main()
