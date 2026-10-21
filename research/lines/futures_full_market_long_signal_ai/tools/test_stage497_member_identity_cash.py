"""Synthetic Stage497 boundaries; no original data, native cache or cash kernel."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import pandas as pd

TOOLS=Path(__file__).resolve().parent


def load():
    path=TOOLS/'stage497_member_identity_cash.py'
    if not path.exists():return None
    spec=importlib.util.spec_from_file_location('fixture497',path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod


class Cash497Boundaries(unittest.TestCase):
    def setUp(self):
        self.m=load();self.assertIsNotNone(self.m,'Stage497 implementation is missing')

    def mothers(self):
        return pd.DataFrame([dict(sequence_index=i,event_id='m'+str(i),product_id='P.X',family_id='P.X',
            u_date=d,u_index=i,reference_epoch='P.X.old') for i,d in enumerate(['2020-01-02','2023-01-03'])])

    def choices(self,arm):
        f=self.mothers();f['scope']='main';f['policy']='NARROW';f['arm']='VOLUNTARY_RESELECT';f['candidate']=arm
        f['cutoff']=['2020-01-01','2023-01-01'];f['selected']=[1,0];f['chosen_action_id']=['child-new','']
        f['chosen_action_sequence_index']=[9,-1];f['score']=[.3,0.];f['chosen_epoch']=['P.X.new',''];f['anchor_epoch']='P.X.old'
        return f

    def test_complete_forward_universe_retained_and_identity_arm_explicit(self):
        arm=self.m.ARMS[0]
        picked,ids=self.m.prepare_choices(self.mothers(),self.choices(arm),arm,expected_parents=2)
        self.assertEqual(ids,{'child-new'});self.assertEqual(len(picked),2)
        self.assertEqual(picked.candidate.unique().tolist(),[arm]);self.assertEqual(picked.selected.tolist(),[1,0])
        with self.assertRaisesRegex(ValueError,'complete'):
            self.m.prepare_choices(self.mothers(),self.choices(arm).iloc[:1],arm,expected_parents=2)
        bad=self.choices(arm);bad.loc[1,'reference_epoch']='changed'
        with self.assertRaisesRegex(ValueError,'identity'):
            self.m.prepare_choices(self.mothers(),bad,arm,expected_parents=2)
        bad=self.choices(arm);bad['candidate']='C_PRE_LIQUIDITY_FOMC'
        with self.assertRaisesRegex(ValueError,'candidate'):
            self.m.prepare_choices(self.mothers(),bad,arm,expected_parents=2)

    def test_future_outcome_fields_rejected_and_selected_union_exact(self):
        rows=[]
        for i,name in enumerate(['child-new','child-C','ineligible']):
            x={c:'' for c in self.m.ACTION_FIELDS};x.update(action_id=name,event_id=name,
                action_sequence_index=i,mother_sequence_index=i,mother_event_id='m'+str(i),product_id='P.X',
                family_id='P.X',u_date='2020-01-02',u_index=0,reference_epoch='P.X.new',anchor_epoch='P.X.old',
                u_action_eligible=0 if name=='ineligible' else 1,entry_capacity_qty=3,N_u=1.,low20_u=99.,u_close=100.)
            rows.append(x)
        full=pd.DataFrame(rows,columns=self.m.ACTION_FIELDS)
        selected,receipt=self.m.collect_action_union(full,{'child-new','child-C'},expected_rows=3)
        self.assertEqual(set(selected.action_id),{'child-new','child-C'})
        self.assertEqual(receipt['ineligible_rows_retained_in_source'],1)
        self.assertEqual(receipt['original129_reads'],0)
        with self.assertRaisesRegex(ValueError,'exact16'):
            self.m.collect_action_union(full.assign(net_R_stress=1),{'child-new'},expected_rows=3)

    def points(self):
        return [dict(window=w,cost=c,active_total_return_pct=1.,return_percentage_point_difference=.1,
            drawdown_percentage_point_difference=.1,ci95_low=.001) for w in self.m.WINDOWS for c in self.m.COSTS]

    def held(self):
        return dict(groups={g:dict(known_u_equal_mean_increment_R=.1,unknown_differential_selected_events=0)
            for g in ('holdout_0','holdout_1')})

    def test_dual_identity_increment_gate_unknown_preserved_and_no_betting_claim(self):
        p={k:self.points() for k in self.m.CONTRASTS};h={k:self.held() for k in self.m.CONTRASTS}
        g=self.m.dual_gate(p,h,wealth_positive=True)
        self.assertTrue(g['nominal_pass']);self.assertEqual(g['required_contrasts'],['C_minus_B','C_minus_A'])
        self.assertFalse(g['member_is_end_investor_proved']);self.assertFalse(g['increased_betting_qualified'])
        p['C_minus_B'][1]['drawdown_percentage_point_difference']=0.
        self.assertFalse(self.m.dual_gate(p,h,wealth_positive=True)['nominal_pass'])
        p['C_minus_B']=self.points();h['C_minus_A']['groups']['holdout_1']['unknown_differential_selected_events']=1
        g=self.m.dual_gate(p,h,wealth_positive=True)
        self.assertFalse(g['nominal_pass']);self.assertTrue(g['contrasts']['C_minus_A']['held_signal_unknown'])
        view=self.m.same_book_through_2025(pd.DataFrame([
            dict(date='2020-01-02',equity=1050000.),dict(date='2025-12-31',equity=1200000.),
            dict(date='2026-01-02',equity=900000.)]),initial=1000000.)
        self.assertEqual(view['ending_equity'],1200000.);self.assertFalse(view['capital_reset'])

    def test_exact_eight_checkpoint_before_reports_and_failure_never_retries(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'fresh';calls=[]
            def run(spec):calls.append(spec['account_id']);return {'id':spec['account_id'],'synthetic':True}
            def export(spec,book):raise RuntimeError('synthetic report failure')
            with self.assertRaisesRegex(RuntimeError,'report failure'):self.m.run_eight(folder,run,export)
            self.assertEqual(len(calls),8)
            cp=json.loads((folder/'book_checkpoints.json').read_text())
            self.assertEqual((cp['cash_accounts_started'],cp['cash_accounts_completed'],len(cp['books'])),(8,8,8))
            self.assertTrue(all(Path(x['book']['path']).is_file() for x in cp['books']))
            self.assertEqual(json.loads((folder/'actual_started.json').read_text())['stage'],497)
            with self.assertRaises(FileExistsError):self.m.run_eight(folder,run,export)
            self.assertEqual(len(calls),8)
            terminal=json.loads((folder/'actual_terminal.json').read_text())
            self.assertEqual(terminal['cash_accounts_completed'],8);self.assertFalse(terminal['auto_retry'])
            folder2=Path(tmp)/'cash-fail';calls2=[]
            def failing(spec):
                calls2.append(spec['account_id'])
                if len(calls2)==3:raise ValueError('synthetic kernel failure')
                return {'id':spec['account_id']}
            with self.assertRaisesRegex(ValueError,'kernel failure'):self.m.run_eight(folder2,failing,lambda s,b:{})
            terminal=json.loads((folder2/'actual_terminal.json').read_text())
            self.assertEqual((terminal['cash_accounts_started'],terminal['cash_accounts_completed']),(3,2))


if __name__=='__main__':unittest.main()
