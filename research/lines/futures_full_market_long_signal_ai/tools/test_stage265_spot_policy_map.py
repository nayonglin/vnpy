"""Three synthetic tests; no real spot, prices, cash, network or old suite."""
from datetime import date,timedelta
import importlib.util
from pathlib import Path
import unittest

p=Path(__file__).with_name('stage265_spot_policy_map.py')
s=importlib.util.spec_from_file_location('tiny265',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)


def fixture():
    dates=[(date(2020,1,1)+timedelta(days=i)).isoformat() for i in range(23)]
    inventory={d:dict(date=d,source_data_state='positive_spot_rows_observed') for d in dates}
    rows=[dict(date=d,product_text='原名',spot_price_text='10000000000000000.01',numeric_text_state='positive',
        page_content_state='positive_spot_rows_observed',unit_text_id='unit_a') for d in dates]
    rows[20]['spot_price_text']='10000000000000000.02'
    rows[21]['spot_price_text']='1'  # u itself must never enter the window.
    return dates,inventory,rows


class TestStage265(unittest.TestCase):
    def function(self,name):
        self.assertTrue(callable(getattr(m,name,None)),'fixed264 policy behavior not implemented')
        return getattr(m,name)

    def test_interleaved_calendar_prior_endpoints_and_missing_middle_not_compressed(self):
        build=self.function('prepare_source');evaluate=self.function('evaluate')
        dates,inventory,rows=fixture();mapping={'EX.P':'原名'};groups={'unit_a':['原单位']}
        source=build(dates[::2]+dates[1::2],mapping,inventory,rows,groups)
        got=evaluate(dates[21],'EX.P',source)
        self.assertEqual((got['available'],got['keep_entry'],got['action']),(1,1,'retain'))
        self.assertEqual((got['window_start'],got['window_end']),(dates[0],dates[20]))
        self.assertEqual((got['spot_start_text'],got['spot_end_text']),('10000000000000000.01','10000000000000000.02'))
        missing=build(dates,mapping,inventory,[r for r in rows if r['date']!=dates[10]],groups)
        got=evaluate(dates[22],'EX.P',missing)
        self.assertEqual((got['available'],got['keep_entry'],got['reason']),(0,1,'missing_quote'))
        inv=dict(inventory);inv[dates[10]]=dict(date=dates[10],source_data_state='explicit_empty')
        self.assertEqual(evaluate(dates[21],'EX.P',build(dates,mapping,inv,rows,groups))['reason'],'page_unavailable')

    def test_duplicate_unit_switch_and_nonpositive_are_unavailable(self):
        build=self.function('prepare_source');evaluate=self.function('evaluate')
        dates,inv,rows=fixture();mapping={'EX.P':'原名'};groups={'unit_a':['原单位'],'unit_b':['不同原单位']}
        cases=[('duplicate_literal',rows+[dict(rows[8])]),
            ('unit_switch',[dict(r,unit_text_id='unit_b') if i==8 else dict(r) for i,r in enumerate(rows)]),
            ('nonpositive_or_non_numeric',[dict(r,spot_price_text='0',numeric_text_state='zero') if i==8 else dict(r) for i,r in enumerate(rows)])]
        for reason,data in cases:
            with self.subTest(reason=reason):
                got=evaluate(dates[21],'EX.P',build(dates,mapping,inv,data,groups))
                self.assertEqual((got['available'],got['keep_entry'],got['action'],got['reason']),(0,1,'retain',reason))

    def test_unmapped_inherits_and_complete_signal_identity_not_changed(self):
        build=self.function('prepare_source');make=self.function('make_sidecars');gate=self.function('require_source_review')
        dates,inv,rows=fixture()
        # Equal endpoints fail the only fixed condition; no future u value helps.
        rows[20]['spot_price_text']=rows[0]['spot_price_text']
        source=build(dates,{'EX.P':'原名'},inv,rows,{'unit_a':['原单位']})
        choices=[];signals=[]
        for i,product in enumerate(['EX.P','EX.UNKNOWN','EX.P']):
            c=dict(sequence_index=str(i),event_id='mother'+str(i),product_id=product,family_id=product,
                u_date=dates[21],u_index='123',reference_epoch=product+'.202002',anchor_epoch=product+'.202002',
                chosen_action_id='action'+str(i) if i<2 else '',chosen_epoch=product+'.202003' if i<2 else '',
                selected='1' if i<2 else '0',selection_state='selected' if i<2 else 'no_original_entry')
            choices.append(c)
            if i<2:signals.append(dict(event_id=c['chosen_action_id'],mother_event_id=c['event_id'],product_id=product,
                family_id=product,u_date=dates[21],u_index='123',reference_epoch=c['chosen_epoch'],anchor_epoch=c['anchor_epoch']))
        cm,sm=make(choices,signals,source)
        self.assertEqual([r['event_id'] for r in cm],['mother0','mother1','mother2'])
        self.assertEqual([r['event_id'] for r in sm],['action0','action1'])
        self.assertEqual([r['signal_row'] for r in sm],[0,1])
        self.assertEqual([(r['available'],r['keep_entry'],r['action']) for r in sm],[(1,0,'cancel'),(0,1,'retain')])
        self.assertEqual(sm[1]['reason'],'unmapped_product');self.assertEqual(cm[2]['action'],'retain')
        broken=[dict(signals[0],mother_event_id='wrong')]+signals[1:]
        with self.assertRaises(ValueError):make(choices,broken,source)
        with self.assertRaises(ValueError):gate(dict(status='completed',core_blockers=1))
        gate(dict(status='completed',core_blockers=0))


if __name__=='__main__':unittest.main()
