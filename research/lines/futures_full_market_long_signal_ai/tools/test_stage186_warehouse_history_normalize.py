"""Nine source-only synthetic cases. No historical batch, network or finance."""
import copy
import json
import unittest

try:
    import stage186_warehouse_history_normalize as norm
except ModuleNotFoundError:
    norm = None


def overlay():
    return dict(research_product_ids=['SHFE.CU', 'INE.SC', 'DCE.L_F'],
                entries=[dict(entry_id='jcu', source_format='json', source_label='铜$$COPPER',
                              valid_from='20140519', valid_to='20251117', mapped_research_product_id='SHFE.CU',
                              expected_disclosed_VARID='cu'),
                         dict(entry_id='hcu', source_format='html', source_label='铜',
                              valid_from='20251118', valid_to='20261016', mapped_research_product_id='SHFE.CU',
                              expected_disclosed_VARID='cu'),
                         dict(entry_id='hsc', source_format='html', source_label='中质含硫原油',
                              valid_from='20251118', valid_to='20261016', mapped_research_product_id='INE.SC',
                              expected_disclosed_VARID='sc')],
                disclosed_code_blocking_identities={'cu': {'product_id': 'SHFE.CU'}})


def raw(warehouse, quantity, status='0', region='上海$$Shanghai'):
    return dict(REGNAME=region, REGSORT=0, ROWORDER=1, ROWSTATUS=status,
                VARNAME='铜$$COPPER', VARSORT=0, WGHTUNIT='2', WHABBRNAME=warehouse,
                WHROWS=1, WRTCHANGE=0, WRTWGHTS=quantity)


def report(rows):
    return {'o_cursor': rows}


class NormalizeTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(norm, 'stage186 implementation is missing')

    def process(self, rows, date='20200102'):
        return norm.process_report(report(rows), 'json', date, overlay())

    def test_presence_and_three_schema_boundaries_are_not_backfilled(self):
        # Catches replacing absent/null/blank or joining different keyset regimes.
        values = [norm.field_state({}, 'x'), norm.field_state({'x': None}, 'x'),
                  norm.field_state({'x': ''}, 'x'), norm.field_state({'x': ' '}, 'x'),
                  norm.field_state({'x': '2'}, 'x')]
        self.assertEqual([v['state'] for v in values], ['absent', 'null', 'empty', 'blank', 'literal'])
        early = [raw('甲库', 3), raw('总计$$Total', 3, '2', '')]
        a = self.process(early)
        disclosed = [{**r, 'VARID': 'cu', 'WHTYPE': '1'} for r in early]
        b = self.process(disclosed, '20231117')
        compact = [{k: v for k, v in r.items() if k not in ('REGSORT', 'ROWORDER', 'VARSORT')} for r in disclosed]
        c = self.process(compact, '20240321')
        self.assertEqual(len({x['scopes'][0]['representation_version'] for x in [a,b,c]}), 3)
        self.assertEqual(len({x['scopes'][0]['scope_id'] for x in [a,b,c]}), 3)
        self.assertEqual(a['rows'][0]['field_states']['VARID']['state'], 'absent')
        self.assertNotIn('VARID', a['rows'][0]['raw_fields'])
        self.assertIsNone(a['rows'][0]['physical_type'])

    def test_unique_plain_total_uses_all_leaves_not_tax_or_subtotal(self):
        # Catches tax/parent double counting and inferring code meaning from arithmetic.
        rows = [raw('甲库', '3'), raw('乙库', '7'), raw('合计$$Subtotal', 10, '1'),
                raw('保税商品总计$$Total (Bonded)', 2, '2', ''),
                raw('完税商品总计$$Total (Tax included)', 8, '2', ''), raw('总计$$Total', 10, '2', '')]
        x = self.process(rows);s = x['scopes'][0]
        self.assertEqual(len(x['rows']), 6)
        self.assertEqual(s['quantity_value'], '10')
        self.assertEqual(s['leaf_sum_quantity'], '10')
        self.assertEqual(s['leaf_measurement_count'], 2)
        self.assertEqual(s['status'], 'conditional_source_qualified')
        self.assertFalse(s['physical_unit_certified'])
        self.assertEqual(s['quantity_arithmetic_status'], 'match')

    def test_multiple_totals_are_unknown_not_first_last_or_split(self):
        # Catches choosing one total or splitting an ambiguous original group.
        x = self.process([raw('甲库', 3), raw('总计$$Total', 3, '2', ''), raw('总计$$Total', 3, '2', '')])
        self.assertEqual(len(x['scopes']), 1)
        self.assertEqual(x['scopes'][0]['ordinary_total_count'], 2)
        self.assertEqual(x['scopes'][0]['status'], 'unknown')
        self.assertIn('nonunique_plain_total', x['scopes'][0]['reasons'])

    def test_duplicate_leaf_unknown_role_and_mixed_units_remain_required(self):
        # Catches dropping bad source rows/groups to manufacture valid coverage.
        for rows, reason in [([raw('甲库', 2), raw('甲库', 2), raw('总计$$Total', 4, '2', '')], 'duplicate_leaf_identity'),
                             ([raw('甲库', 2, '9'), raw('总计$$Total', 2, '2', '')], 'unknown_source_role')]:
            with self.subTest(reason=reason):
                x = self.process(rows)
                self.assertEqual(x['scopes'][0]['status'], 'unknown')
                self.assertIn(reason, x['scopes'][0]['reasons'])
                self.assertEqual(next(p for p in x['products'] if p['mapped_research_product_id']=='SHFE.CU')['status'], 'unknown')
        good = [raw('甲库', 2), raw('总计$$Total', 2, '2', '')]
        bad = raw('乙库', 1);bad['WGHTUNIT'] = '1'
        x = self.process(good + [bad]);p = next(p for p in x['products'] if p['mapped_research_product_id']=='SHFE.CU')
        self.assertEqual(len(p['required_scope_ids']), 2)
        self.assertEqual(len(p['bad_scope_ids']), 1)
        self.assertEqual(p['status'], 'unknown')

    def test_decimal_and_quantity_missing_never_become_zero(self):
        # Catches fill-zero, non-finite parsing and negative source quantities.
        for value, state in [(None,'null'),('', 'blank'),('--','placeholder'),('oops','parse_failure'),(0,'numeric_zero')]:
            with self.subTest(value=value):
                x = self.process([raw('甲库', value), raw('总计$$Total', 0, '2', '')])
                self.assertEqual(x['rows'][0]['quantity']['state'], state)
                self.assertEqual(x['scopes'][0]['status'], 'conditional_source_qualified' if value==0 else 'unknown')
        x = self.process([raw('甲库', -1), raw('总计$$Total', -1, '2', '')])
        self.assertEqual(x['scopes'][0]['status'], 'unknown')
        self.assertIn('negative_quantity', x['scopes'][0]['reasons'])
        self.assertTrue(hasattr(norm,'decode_json'), 'raw JSON decimal decoding is missing')
        source=json.dumps(report([raw('甲库','EXACT_NUMBER'),raw('总计$$Total','EXACT_NUMBER','2','')]),ensure_ascii=False)
        source=source.replace('"EXACT_NUMBER"','0.100000000000000005')
        x=norm.process_report(norm.decode_json(source),'json','20200102',overlay())
        self.assertEqual(x['rows'][0]['quantity']['value'],'0.100000000000000005')
        saved=json.loads(norm.canon(x['rows'][0]))
        self.assertEqual(saved['raw_field_types']['WRTWGHTS'],'json_decimal_number')
        self.assertEqual(saved['raw_fields']['WRTWGHTS'],'0.100000000000000005')

    def test_html_repeated_headers_keep_one_original_table_and_ambiguous_total(self):
        # Catches using only the last header or making each header a convenient scope.
        h = '''<table><tr><th>地区</th><th>仓库</th><th>期货</th><th>增减</th></tr>
        <tr><td colspan="3">铜</td><td>单位：吨</td></tr><tr><td>沪</td><td>甲库</td><td>2</td><td>0</td></tr>
        <tr><td colspan="2">总计</td><td>2</td><td>0</td></tr>
        <tr><th>仓库</th><th>地区</th><th>期货</th><th>增减</th></tr>
        <tr><td>乙库</td><td>沪</td><td>3</td><td>0</td></tr><tr><td colspan="2">总计</td><td>3</td><td>0</td></tr></table>'''
        x = norm.process_report(h, 'html', '20251118', overlay())
        self.assertEqual(len(x['rows']), 7)
        self.assertEqual(len(x['scopes']), 1)
        self.assertEqual(x['scopes'][0]['ordinary_total_count'], 2)
        self.assertEqual(x['scopes'][0]['status'], 'unknown')
        self.assertEqual(x['rows'][5]['warehouse_raw'], '乙库')
        self.assertNotEqual(x['rows'][2]['header_occurrence'], x['rows'][5]['header_occurrence'])
        self.assertEqual({r['table_index'] for r in x['rows']}, {0})

    def test_html_rowspan_quantities_are_counted_once_with_full_context(self):
        # Catches duplicating factory quantities across delivery places or losing their coverage.
        h = '''<table><tr><th>仓库</th><th>地区</th><th>提货地</th><th>期货</th><th>增减</th></tr>
        <tr><td colspan="4">铜</td><td>单位：吨</td></tr>
        <tr><td rowspan="2">甲库</td><td rowspan="2">沪</td><td>A</td><td rowspan="2">5</td><td rowspan="2">1</td></tr>
        <tr><td>B</td></tr><tr><td colspan="3">总计</td><td>5</td><td>1</td></tr></table>'''
        x = norm.process_report(h, 'html', '20251118', overlay());s=x['scopes'][0]
        self.assertEqual(s['source_leaf_row_count'], 2)
        self.assertEqual(s['leaf_measurement_count'], 1)
        self.assertEqual(s['leaf_sum_quantity'], '5')
        self.assertEqual(s['status'], 'conditional_source_qualified')
        self.assertTrue(x['rows'][3]['quantity_inherited'])
        changed = norm.process_report(h.replace('<td>B</td>', '<td>C</td>'), 'html', '20251118', overlay())
        self.assertNotEqual(s['leaf_coverage_fingerprint'], changed['scopes'][0]['leaf_coverage_fingerprint'])
        amount = norm.process_report(h.replace('>5<','>7<'), 'html', '20251118', overlay())
        self.assertEqual(s['leaf_coverage_fingerprint'], amount['scopes'][0]['leaf_coverage_fingerprint'])

    def test_exact_overlay_and_unresolved_membership_do_not_alias_or_drop(self):
        # Catches near-name/F aliasing, period leakage or silently omitting an unmapped required scope.
        x = self.process([raw('甲库', 2), raw('总计$$Total', 2, '2', '')])
        self.assertEqual(len(x['products']), 3)
        no_source=next(p for p in x['products'] if p['mapped_research_product_id']=='DCE.L_F')
        self.assertEqual(no_source['status'], 'unknown_no_source_scope')
        bad=raw('甲库', 2);bad['VARNAME']='铜 $$COPPER'
        y = self.process([raw('甲库', 2),raw('总计$$Total',2,'2',''),bad])
        p=next(p for p in y['products'] if p['mapped_research_product_id']=='SHFE.CU')
        self.assertFalse(p['scope_membership_complete'])
        self.assertTrue(p['unresolved_report_scope_ids'])
        self.assertEqual(p['status'], 'unknown')
        r=[{**z,'VARID':'cu_F','WHTYPE':'1'} for z in [raw('甲库',2),raw('总计$$Total',2,'2','')]]
        self.assertEqual(self.process(r,'20231117')['scopes'][0]['mapping_state'], 'unknown_code_conflict')
        expired=self.process([raw('甲库',2),raw('总计$$Total',2,'2','')],'20251118')
        self.assertEqual(expired['scopes'][0]['mapping_state'], 'unknown_no_exact_entry')

    def test_sc_special_header_preserves_missing_delta_and_all_raw_rows(self):
        # Catches missing-column zero fill and losing intro/header rows or SC aliases.
        h='''<table class="content_intro"><tr><td>报告日期2025-11-18</td></tr></table>
        <table><tr><th>地区</th><th>交割仓库</th><th>本日数量</th></tr>
        <tr><td colspan="2">中质含硫原油</td><td>单位：桶</td></tr>
        <tr><td>甲地</td><td>甲库</td><td>2</td></tr><tr><td colspan="2">总计</td><td>2</td></tr></table>'''
        x=norm.process_report(h,'html','20251118',overlay())
        self.assertEqual(len(x['rows']),5)
        self.assertEqual(x['rows'][3]['quantity_field_name'],'本日数量')
        self.assertEqual(x['rows'][3]['official_delta']['state'],'missing_field')
        self.assertEqual(x['scopes'][0]['quantity_value'],'2')
        self.assertEqual(x['scopes'][0]['status'],'conditional_source_qualified')
        self.assertEqual(x['rows'][0]['row_level'],'intro')


if __name__=='__main__':
    unittest.main()
