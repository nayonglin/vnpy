"""Small warehouse schema/Decimal/span fixtures, never reads real seven raw."""
import importlib.util
from pathlib import Path
import unittest

SOURCE=Path(__file__).with_name('stage173_warehouse_normalize.py')
if SOURCE.exists():
    spec=importlib.util.spec_from_file_location('warehouse173',SOURCE)
    w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
else:
    w=None


class WarehouseTest(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(w,'warehouse normalization implementation missing')

    def test_decimal_missing_zero_placeholder_and_parse_failure_do_not_collapse(self):
        expected=[('', 'blank',None),('0','numeric_zero','0'),('--','placeholder',None),
                  ('12,345.50','numeric','12345.50'),('12,34','parse_failure',None),
                  ('1e3','parse_failure',None),('-2','numeric','-2'),(None,'null',None)]
        for raw,state,value in expected:
            with self.subTest(raw=raw):
                got=w.decimal_cell(raw)
                self.assertEqual((got['state'],got['value']),(state,value))
                self.assertEqual(got['raw'],raw)

    def test_html_header_reverse_and_rowspan_quantity_origin_are_preserved(self):
        html='''<table class="content_intro"><tr><td>2025-11-18 第212期</td></tr></table>
        <table><tr><th>厂库</th><th>地区</th><th>期货</th><th>增减</th></tr>
        <tr><td colspan="3">胶版印刷纸厂库</td><td>单位：吨</td></tr>
        <tr><td rowspan="2">工厂A</td><td>甲地</td><td rowspan="2">10</td><td rowspan="2">0</td></tr>
        <tr><td>乙地</td></tr><tr><td colspan="2">总计</td><td>10</td><td>0</td></tr></table>'''
        rows,meta=w.normalize_html(html,'20251118')
        self.assertEqual(len(rows),6)
        leaf=[r for r in rows if r['row_level']=='leaf']
        self.assertEqual(len(leaf),2)
        self.assertEqual([r['warehouse_raw'] for r in leaf],['工厂A','工厂A'])
        self.assertEqual([r['region_raw'] for r in leaf],['甲地','乙地'])
        self.assertEqual(leaf[0]['quantity_origin'],leaf[1]['quantity_origin'])
        self.assertTrue(leaf[1]['quantity_inherited'])
        checks=w.intra_checks(rows)
        check=next(c for c in checks if c['aggregate_label']=='总计' and c['field']=='quantity')
        self.assertEqual((check['status'],check['computed_sum']),('match','10'))

    def test_json_codes_unknown_units_and_report_dates_preserve_every_row(self):
        obj={'report_date':'20251114','o_tradingday':'20251114','update_date':'20251114 15:00:00','o_cursor':[
            {'VARNAME':'铜$$COPPER','VARID':'cu','WHTYPE':'1','WGHTUNIT':'2','REGNAME':'上海$$Shanghai','WHABBRNAME':'仓库A','ROWSTATUS':'0','WRTWGHTS':0,'WRTCHANGE':'--'},
            {'VARNAME':'铜$$COPPER','VARID':'cu','WHTYPE':'1','WGHTUNIT':'2','REGNAME':'','WHABBRNAME':'总计','ROWSTATUS':'2','WRTWGHTS':0,'WRTCHANGE':0}]}
        rows,meta=w.normalize_json(obj,'20251113')
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]['raw_fields'],obj['o_cursor'][0])
        self.assertEqual((rows[0]['unit_state'],rows[0]['unit_raw']),('code_unmapped','2'))
        self.assertEqual(rows[0]['type_code_state'],'code_unmapped')
        self.assertEqual(rows[0]['quantity']['state'],'numeric_zero')
        self.assertEqual(rows[0]['official_delta']['state'],'placeholder')
        self.assertEqual(meta['date_state'],'mismatch')
        self.assertEqual(w.intra_checks(rows)[0]['basis'],'raw_code_only_not_physical_unit_certification')

    def test_subtotals_and_partition_totals_are_not_added_as_leaves(self):
        html='''<table><tr><th>地区</th><th>仓库</th><th>期货</th><th>增减</th></tr>
        <tr><td colspan="3">铜</td><td>单位：吨</td></tr>
        <tr><td rowspan="3">上海</td><td>A(保税)</td><td>10</td><td>1</td></tr>
        <tr><td>B</td><td>20</td><td>2</td></tr>
        <tr><td>合计</td><td>30</td><td>3</td></tr>
        <tr><td colspan="2">保税商品总计</td><td>10</td><td>1</td></tr>
        <tr><td colspan="2">完税商品总计</td><td>20</td><td>2</td></tr>
        <tr><td colspan="2">总计</td><td>30</td><td>3</td></tr></table>'''
        rows,_=w.normalize_html(html,'20251118')
        got=[c for c in w.intra_checks(rows) if c['aggregate_label']=='总计' and c['field']=='quantity'][0]
        self.assertEqual(got['computed_sum'],'30')
        self.assertEqual(got['measurement_count'],2)
        self.assertEqual(len(rows),8)

    def test_adjacent_unknown_unit_or_coverage_never_claims_physical_delta(self):
        def html(names,values,delta):
            body=''.join(f'<tr><td>上海</td><td>{n}</td><td>{v}</td><td>0</td></tr>' for n,v in zip(names,values))
            return f'<table><tr><th>地区</th><th>仓库</th><th>期货</th><th>增减</th></tr><tr><td colspan="3">铜</td><td>单位：吨</td></tr>{body}<tr><td colspan="2">总计</td><td>{sum(values)}</td><td>{delta}</td></tr></table>'
        prev,_=w.normalize_html(html(['A'],[10],0),'20251118')
        curr,_=w.normalize_html(html(['A'],[12],2),'20251119')
        checks=w.adjacent_checks(prev,curr)
        good=next(c for c in checks if c['aggregate_label']=='总计')
        self.assertEqual((good['status'],good['computed_difference'],good['official_delta']),('match','2','2'))
        changed,_=w.normalize_html(html(['A','B'],[12,0],2),'20251120')
        self.assertTrue(all(c['status']=='unknown_coverage' for c in w.adjacent_checks(curr,changed)))
        for row in curr:
            row['unit_state']='unknown';row['unit_value']=None
        self.assertTrue(all(c['status'].startswith('unknown') for c in w.adjacent_checks(prev,curr)))

    def test_duplicate_leaf_is_unknown_and_missing_total_is_not_failure(self):
        html='''<table><tr><th>地区</th><th>仓库</th><th>期货</th><th>增减</th></tr><tr><td colspan="3">铜</td><td>单位：吨</td></tr>
        <tr><td>上海</td><td>A</td><td>10</td><td>0</td></tr><tr><td>上海</td><td>A</td><td>10</td><td>0</td></tr>
        <tr><td colspan="2">总计</td><td>20</td><td>0</td></tr></table>'''
        rows,_=w.normalize_html(html,'20251118')
        self.assertTrue(all(c['status']=='unknown_duplicate_leaf' for c in w.intra_checks(rows)))
        no_total=[r for r in rows if r['row_level']!='grand_total']
        self.assertEqual(w.intra_checks(no_total),[])

    def test_sc_explicit_current_quantity_and_delivery_warehouse_aliases(self):
        html='''<table><tr><th>交割仓库</th><th>上日数量</th><th>本日数量</th></tr>
        <tr><td colspan="2">原油</td><td>单位：桶</td></tr>
        <tr><td>库A</td><td>8</td><td>10</td></tr>
        <tr><td>总计</td><td>8</td><td>10</td></tr></table>'''
        rows,_=w.normalize_html(html,'20251118')
        leaves=[r for r in rows if r['row_level']=='leaf']
        self.assertEqual(len(leaves),1)
        self.assertEqual(leaves[0]['quantity']['value'],'10')
        self.assertEqual(leaves[0]['quantity_field_name'],'本日数量')
        self.assertEqual(leaves[0]['location_field_name'],'交割仓库')
        self.assertEqual(leaves[0]['official_delta']['state'],'missing_field')
        self.assertEqual(leaves[0]['unit_value'],'桶')


if __name__=='__main__':
    unittest.main()
