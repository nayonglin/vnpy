"""Three synthetic behaviors only: no real archive, HTTP, old suite or fits."""
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

p=Path(__file__).with_name('stage257_extract_raw_spot_archive.py')
s=importlib.util.spec_from_file_location('tiny257',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
FIELDS=['date','fdata_top_level_row','product_text','spot_price_text','numeric_text_state','page_content_state','unit_text_id','source_raw_sha256']


def bound(p):
    b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())


def put(p,value):
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value));return bound(p)


def page(day,rows):
    d=day.replace('-','年',1).replace('-','月',1)+'日'
    return ('<title>'+d+'商品现货与期货价格对比表</title><div class="title2">'+d+' 16:30 来源：fixture</div>\n'
        '<table id="fdata"><tr><td>商品</td><td>现货</td><td>最近合约</td><td>主力合约</td></tr>'
        '<tr><td>价格</td><td>代码</td><td>价格</td><td>现期差1</td><td>代码</td><td>价格</td><td>现期差2</td></tr>'+rows+'</table>\n'
        '<span>单位:元/吨</span>').encode()


def data(name,price):
    return '<tr>'+''.join('<td>'+v+'</td>' for v in [name,price,'2001','10','<table><tr><td>1</td></tr></table>','2003','11',''])+'</tr>'


class TestStage257(unittest.TestCase):
    def function(self,name):
        self.assertTrue(callable(getattr(m,name,None)),'frozen257 extraction behavior missing')
        return getattr(m,name)

    def test_literals_duplicate_ambiguity_and_unsupported_format_stay_unknown(self):
        parse=self.function('parse_body');day='2020-01-02';raw=page(day,data('原名 A','12.30')+data('原名 A','--')+'<tr><td>新行</td><td>3</td></tr>')
        ref=dict(path='synthetic.response',bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
        groups={'literal_unit_text_9':['单位:元/吨']};inv,rows=parse(day,raw,ref,groups)
        self.assertEqual([r['product_text'] for r in rows],['原名 A','原名 A'])
        self.assertEqual([r['spot_price_text'] for r in rows],['12.30','--'])
        self.assertEqual([r['numeric_text_state'] for r in rows],['positive','non_numeric'])
        self.assertEqual({r['unit_text_id'] for r in rows},{'literal_unit_text_9'})
        self.assertEqual(inv['duplicate_product_groups'],[dict(product_text='原名 A',top_level_rows=[3,4])])
        self.assertEqual(inv['unsupported_rows'],[dict(top_level_row=5,cells=['新行','3'],state='unknown_unsupported_row')])
        self.assertEqual(inv['source_data_state'],'unknown_unsupported_rows')
        bad,badrows=parse(day,b'<html>unexpected</html>',dict(path='bad',bytes=23,sha256='bad'),groups)
        self.assertTrue(bad['source_data_state'].startswith('unknown'));self.assertEqual(badrows,[])

    def test_accepted_csv_and_empty_bodies_never_opened_full_inventory_and_once_new_reads(self):
        run=self.function('run_extraction')
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);archive=root/'archive';rowsdir=archive/'rows';rowsdir.mkdir(parents=True)
            oldpositive=[f'2020-02-{i:02d}' for i in range(1,8)];empty=['2020-01-01','2020-01-02']
            accepted='2020-01-03';new='2020-03-01';error='2020-03-02';unattempted='2020-03-03';alias='2020-03-04'
            dates=empty+[accepted]+oldpositive+[new,error,unattempted,alias];reuse={}
            for day in empty:
                reuse[day]=dict(body=dict(path='/must/not/open/'+day,bytes=3,sha256='empty'),source_receipt='accepted',http_status=200)
            for day in oldpositive:
                b=page(day,data('旧原名','2'));f=root/(day+'.response');f.write_bytes(b)
                reuse[day]=dict(body=bound(f),source_receipt='accepted',http_status=200)
            b=page(new,data('新原名','4'));f=root/(new+'.response');f.write_bytes(b)
            put(rowsdir/(new+'.json'),dict(date=new,state='http_complete',http_success=True,http_status=200,body=bound(f)))
            put(rowsdir/(error+'.json'),dict(date=error,state='http_failed',http_success=False,http_status=None,body=None,transport_error={'type':'fixture'}))
            put(rowsdir/(alias+'.json'),dict(date=alias,state='http_complete',http_success=True,body=dict(path='/must/not/open/accepted',bytes=3,sha256='acceptedsha')))
            original=put(root/'original.json',dict(date_count=len(dates),dates=dates,reused=reuse,output_contract=dict(path=str(archive),metadata_subdir='rows',body_subdir='raw')))
            csvp=root/'accepted.csv';text=io.StringIO();w=csv.DictWriter(text,fieldnames=FIELDS);w.writeheader();w.writerow(dict(zip(FIELDS,[accepted,'3','原CSV名','8.00','positive','positive_spot_rows_observed','literal_unit_text_1','acceptedsha'])));csvp.write_text(text.getvalue())
            csvref=bound(csvp);csvref['data_rows']=1
            inherited=[dict(date=d,body_sha256='empty',fdata_top_level_rows=3,positive_numeric_spot_rows=0,no_data=True,source_data_state='explicit_empty') for d in empty]
            prior=put(root/'accepted_receipt.json',dict(literal_unit_text_groups={'literal_unit_text_1':['单位:元/吨']},new_rows=[dict(date=accepted,source_body=dict(path='/must/not/open/accepted',bytes=3,sha256='acceptedsha'),source_data_state='positive_spot_rows_observed',positive_numeric_spot_rows=1,spot_csv_rows=1)],inherited_nine_rows=inherited))
            terminal=root/'255terminal.json';put(terminal,dict(schema='fixture255',status='completed',exit_code=0))
            protocol=dict(original249=original,accepted253_receipt=prior,accepted253_CSV=csvref,acquisition255_terminal_required=str(terminal),same_CSV_fields=FIELDS,output_folder=str(root/'out'))
            result=run(protocol)
            self.assertEqual(result['counts']['date_inventory_rows'],14)
            self.assertEqual(result['counts']['accepted253_csv_reads'],1)
            self.assertEqual(result['counts']['accepted253_body_reads'],0)
            self.assertEqual(result['counts']['old9_empty_body_reads'],0)
            self.assertEqual(result['counts']['old9_positive_body_reads'],7)
            self.assertEqual(result['counts']['remaining_body_reads'],1)
            self.assertEqual(result['counts']['output_spot_rows'],9)
            inventory=[json.loads(s) for s in (root/'out/date_inventory.jsonl').read_text().splitlines()]
            self.assertEqual(next(r for r in inventory if r['date']==error)['source_data_state'],'unknown_no_body')
            self.assertEqual(next(r for r in inventory if r['date']==unattempted)['source_data_state'],'unattempted')
            self.assertEqual(next(r for r in inventory if r['date']==alias)['source_data_state'],'unknown_ref_to_inherited_body_no_read')
            with (root/'out/raw_spot_text.csv').open() as f:out=list(csv.DictReader(f))
            self.assertEqual(out[0]['spot_price_text'],'8.00')
            self.assertEqual((root/'out/literal_unit_groups.json').read_text().count('literal_unit_text_1'),1)

    def test_live_or_missing_255_terminal_blocks_before_inputs_or_output(self):
        run=self.function('run_extraction')
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);terminal=root/'terminal.json';protocol=dict(acquisition255_terminal_required=str(terminal),output_folder=str(root/'out'))
            with self.assertRaises(RuntimeError):run(protocol)
            self.assertFalse((root/'out').exists())
            put(terminal,dict(status='running'))
            with self.assertRaises(RuntimeError):run(protocol)
            self.assertFalse((root/'out').exists())


if __name__=='__main__':unittest.main()
