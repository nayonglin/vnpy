"""Small synthetic guard cases only; no historical books or native-source read."""
import importlib.util, inspect, unittest
from pathlib import Path
import test_stage131_contract_choice_cash as fixtures
TOOLS=Path(__file__).resolve().parent

def load_kernel():
    path=TOOLS/'stage575_open_cap_kernel.py'
    if not path.exists(): return None
    spec=importlib.util.spec_from_file_location('test575_local_kernel',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

class CapGuard(unittest.TestCase):
    def setUp(self):
        self.k=load_kernel();self.assertIsNotNone(self.k,'new isolated kernel missing')
        self.fixture=fixtures.ContractChoiceCash();self.fixture.setUp()
    def book(self,cap,*,missing=(),huge_open=False):
        market,dates=self.fixture.market(missing=missing)
        if huge_open:
            records=[]
            for epoch in ('P.X.203001','P.X.202912'):
                for j,day in enumerate(dates):
                    b=market.bar(epoch,j);b=dict(b)
                    if j==21:b.update(open=1e8,high=1e8+1,low=1e8-1,close=1e8)
                    records.append(dict(contract_epoch_id=epoch,trade_date=day,quality_status='accepted',**b))
            market=self.k.ref.Market.from_records(records,dates)
        signals=self.fixture.signal(market,dates);signals['u_close']=cap
        refs={j:{'P.X':'P.X.202912'} for j in range(len(dates))}
        return self.k.run_cash_account(signals,market,dates,self.fixture.econ(),'base','fixture',21,22,prepared=({20:signals.to_dict('records')},refs))
    def test_equal_cap_passes(self):
        self.assertTrue(self.k.cap_accepts(100.1,100.1))
        book=self.book(100.1);self.assertEqual(book['fills'][0]['side'],'BUY')
    def test_above_cap_known_cancel(self):
        book=self.book(100.0);r=book['budgets'][0]
        self.assertEqual((r['D_state'],r['D_qty']),('execution_price_above_u_close',0));self.assertEqual(book['fills'],[])
    def test_slip_tick_quote_instead_of_raw_open(self):
        e=self.fixture.econ()['P.X.203001'];q=self.k.adverse_quote(100.,'BUY',e,'base')
        self.assertGreater(q['fill_price'],100.);self.assertFalse(self.k.cap_accepts(q['fill_price'],100.))
    def test_qty_zero_reason_precedes_guard(self):
        book=self.book(100.,huge_open=True);r=book['budgets'][0]
        self.assertEqual(r['D_state'],'own_open_allocation_insufficient');self.assertNotIn('cap_candidate_fill_price',r)
    def test_unknown_keeps_original_state(self):
        book=self.book(100.,missing=(21,));self.assertTrue(book['execution_unknown'])
        self.assertEqual(book['entry_execution_unknown'][0]['state'],'entry_execution_unknown');self.assertEqual(book['fills'],[])
    def test_source_is_original_except_guard(self):
        text=inspect.getsource(self.k.run_cash_account);before,rest=text.split('            # BEGIN575_ENTRY_CAP\n',1);_,after=rest.split('            # END575_ENTRY_CAP\n',1)
        self.assertEqual(before+after,inspect.getsource(self.k.accepted.run_cash_account))
    def test_same_D_other_budget_not_refilled(self):
        market,dates=self.fixture.market();records=[]
        for epoch in ('P.X.203001','Q.X.203001'):
            for j,day in enumerate(dates):records.append(dict(contract_epoch_id=epoch,trade_date=day,quality_status='accepted',**market.bar('P.X.203001',j)))
        market=self.k.ref.Market.from_records(records,dates);e=self.fixture.econ()['P.X.203001'];economics={x:dict(e) for x in ('P.X.203001','Q.X.203001')}
        p=self.fixture.signal(market,dates,anchor='P.X.203001').iloc[0].to_dict();p.update(event_id='p',u_close=100.)
        q=dict(p,event_id='q',family_id='Q.X',product_id='Q.X',reference_epoch='Q.X.203001',anchor_epoch='Q.X.203001',u_close=101.)
        import pandas as pd
        refs={j:{'P.X':'P.X.203001','Q.X':'Q.X.203001'} for j in range(len(dates))}
        book=self.k.run_cash_account(pd.DataFrame([p,q]),market,dates,economics,'base','fixture',21,22,prepared=({20:[p,q]},refs))
        r=next(x for x in book['budgets'] if x['event_id']=='q');expected,_=self.k.execution_quantity(r,100.,e,'base','NARROW')
        self.assertEqual(next(x for x in book['budgets'] if x['event_id']=='p')['D_qty'],0)
        self.assertEqual(next(x for x in book['fills'] if x['event_id']=='q')['qty'],expected)

if __name__=='__main__':unittest.main()
