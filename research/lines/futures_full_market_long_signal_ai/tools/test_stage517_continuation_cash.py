"""New synthetic continuation policy boundaries; no historical source reads."""
import importlib.util
from pathlib import Path
import unittest
import gzip
from datetime import date,timedelta
import pandas as pd

TOOLS=Path(__file__).resolve().parent

def load(name,identity):
    spec=importlib.util.spec_from_file_location(identity,TOOLS/name)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

class ContinuationCash(unittest.TestCase):
    def setUp(self):
        self.k=load('stage517_continuation_kernel.py','test517kernel')
        self.v=load('stage157_voluntary_cash.py','test517voluntary')

    def fixture(self,missing=(),force_day=None,huge_mark=False,start_date=None,stop_entry=False):
        dates=[f'2020-01-{j:02d}' for j in range(1,31)]
        if start_date is not None:dates=[(start_date+timedelta(days=j)).isoformat() for j in range(30)]
        epoch='P.X.202002';records=[]
        for j,day in enumerate(dates):
            if j in missing:continue
            close=20000. if huge_mark and j==21 else 101.
            records.append(dict(contract_epoch_id=epoch,trade_date=day,open=100.,
                high=max(102.,close),low=98. if j<=20 else 99. if stop_entry and j==21 else 100.,close=close,
                volume=2000.,quality_status='accepted'))
        market=self.v.ref.Market.from_records(records,dates)
        ind=market.indicator(epoch,20)
        signal=pd.DataFrame([dict(event_id='child',mother_event_id='mother',
            product_id='P.X',family_id='P.X',reference_epoch=epoch,anchor_epoch=epoch,
            lifecycle_index=29,u_index=20,u_date=dates[20],D_index=21,N_u=ind['N'],
            low20_u=ind['low20'],u_close=101.,history_run=21,entry_capacity_qty=10,
            potential=1,source_lifecycle_target_date='2020-02-01',K_target_date='2020-01-30')])
        econ={epoch:dict(economics_status='exact_epoch_metadata_snapshot',contract_multiplier=10.,
            round_lot=1,tick_size=.1,vendor_margin_rate=.8 if huge_mark else .1)}
        refs={j:{'P.X':('OTHER.X.202002' if force_day is not None and j>=force_day else epoch)} for j in range(30)}
        prep=({20:signal.to_dict('records')},refs)
        return signal,market,dates,econ,prep

    def runbook(self,hook=None,**options):
        sig,market,dates,econ,prep=self.fixture(**options)
        book=self.k.run_cash_account(sig,market,dates,econ,'base','same',21,25,prepared=prep,continuation=hook)
        return book,dates

    def test_disabled_hook_has_exact_old_cash_parity(self):
        sig,m,dates,econ,prep=self.fixture(missing=(23,))
        a=self.k.old.run_cash_account(sig,m,dates,econ,'base','same',21,25,prepared=prep)
        b=self.k.run_cash_account(sig,m,dates,econ,'base','same',21,25,prepared=prep)
        self.assertEqual(a,b)

    def test_negative_close_executes_only_next_open_and_zero_holds(self):
        calls=[]
        def negative(day,state):calls.append((day,state));return dict(prediction=-.1,cutoff='2020-01-01',status='observed')
        b,dates=self.runbook(negative)
        self.assertEqual(b['fills'][-1]['date'],dates[22])
        self.assertEqual(b['fills'][-1]['reason'],'ai_continuation_next_open_exit')
        self.assertEqual(calls[0][1]['age_source_days'],1)
        self.assertEqual(calls[0][1]['previous_close'],101.)
        self.assertEqual(calls[0][1]['SL0'],100.-.25*4.)
        z,_=self.runbook(lambda d,s:dict(prediction=0.,cutoff='2020-01-01',status='observed'))
        self.assertEqual([f['side'] for f in z['fills']],['BUY'])

    def test_forced_exit_and_scheduled_reduction_take_precedence(self):
        calls=[]
        def neg(day,state):calls.append(day);return dict(prediction=-1.,cutoff='2020-01-01')
        b,dates=self.runbook(neg,force_day=21)
        self.assertEqual(calls,[])
        self.assertEqual(b['fills'][-1]['reason'],'liquidity_reference_changed')
        r,dates=self.runbook(neg,huge_mark=True)
        self.assertEqual(r['continuation_audit'][0]['discretionary'],0)
        self.assertEqual(r['continuation_audit'][0]['status'],'not_discretionary')
        self.assertTrue(any(f['reason']=='risk_margin_joint_reduction' for f in r['fills']))

    def test_missing_next_open_preserves_request_and_defers_under_original_priority(self):
        b,dates=self.runbook(lambda d,s:dict(prediction=-.1,cutoff='2020-01-01'),missing=(22,23))
        self.assertEqual([f['side'] for f in b['fills']],['BUY','SELL'])
        self.assertEqual(b['fills'][-1]['date'],dates[24])
        self.assertEqual(b['fills'][-1]['reason'],'research_deferred_liquidation')
        rows={r['date']:r for r in b['position_days']}
        self.assertEqual(rows[dates[23]]['mark_state'],'stale')
        self.assertEqual(rows[dates[23]]['voluntary_requested_next'],1)
        self.assertEqual(rows[dates[23]]['SL0'],rows[dates[21]]['SL0'])

    def test_zero_reduction_record_does_not_block_and_invalid_prediction_holds(self):
        p=dict(stale=False,force_reason=None,reduce_to=4,qty=4)
        self.assertTrue(self.k.discretionary_close(p))
        self.assertFalse(self.k.latch_decision(p,dict(prediction=float('nan')),'2023-01-01'))
        p['reduce_to']=3
        self.assertFalse(self.k.discretionary_close(p))


    def test_cash_hook_receives_current_close_date_across_head_cutoff(self):
        calls=[]
        def heads(day,state):
            cutoff='2020-01-01' if day<'2023-01-01' else '2023-01-01'
            calls.append((day,cutoff,state['age_source_days']))
            return dict(prediction=1. if cutoff=='2020-01-01' else -1.,cutoff=cutoff)
        book,dates=self.runbook(heads,start_date=date(2022,12,10))
        self.assertEqual(calls[:2],[('2022-12-31','2020-01-01',1),('2023-01-01','2023-01-01',2)])
        self.assertEqual(book['fills'][-1]['date'],'2023-01-02')
        self.assertEqual(book['closed_episodes'][0]['voluntary_model_cutoff'],'2023-01-01')

    def test_entry_same_bar_stop_never_reaches_close_model(self):
        calls=[]
        def hook(day,state):calls.append(day);return dict(prediction=-1.)
        book,dates=self.runbook(hook,stop_entry=True)
        self.assertEqual(calls,[])
        self.assertEqual([f['date'] for f in book['fills']],[dates[21],dates[21]])

    def test_signal_projection_never_materializes_future_terminal_fields(self):
        cash=load('stage517_continuation_cash.py','test517driver')
        row={k:'' for k in cash.ACTION_FIELDS}
        row.update(sequence_index='0',action_id='a',mother_sequence_index='1',mother_event_id='m',
            product_id='P.X',family_id='P.X',u_date='2020-01-01',u_index='2',reference_epoch='P.X.202002',
            anchor_epoch='P.X.202002',u_action_eligible='1',entry_capacity_qty='10',N_u='4',low20_u='98',u_close='101',
            source_lifecycle_target_date='2020-02-01',K_target_date='2020-01-01',
            terminal_state='FAKE_FUTURE',exit_date='9999-01-01',exit_reference='99999999')
        other=dict(row,sequence_index='1',action_id='b',u_action_eligible='0')
        raw=gzip.compress(pd.DataFrame([row,other]).to_csv(index=False).encode())
        frame,receipt=cash.selected_action_projection(raw,{'a'},expected_rows=2)
        self.assertEqual(frame.action_id.tolist(),['a'])
        self.assertEqual(frame.action_sequence_index.tolist(),[0])
        self.assertEqual(frame.event_id.tolist(),['a'])
        self.assertEqual(receipt['source_action_rows'],2)
        self.assertNotIn('exit_date',frame.columns)
        self.assertNotIn('terminal_state',frame.columns)
        self.assertEqual(receipt['outcome_field_reads'],0)

if __name__=='__main__':unittest.main()
