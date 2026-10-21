"""Only new Stage168 synthetic contracts; no accepted arrays or real cash run."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

TOOLS=Path(__file__).resolve().parent


def load():
    path=TOOLS/'stage168_member_concentration_cash.py'
    if not path.exists():return None
    spec=importlib.util.spec_from_file_location('fixture168',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


class ConcentrationCash(unittest.TestCase):
    def setUp(self):
        self.m=load()
        self.assertIsNotNone(self.m,'Stage168 implementation missing')

    def fixture(self):
        dates=[f'2020-01-{i:02d}' for i in range(1,31)]
        store=self.m.cache_source.NativeBars(dates)
        for epoch in ('P.X.203001','P.X.202912'):
            valid=np.ones(30,bool);valid[[23,24]]=False
            store.series[epoch]=dict(days=np.arange(30),values=np.tile([100.,102.,100.,101.,2000.],(30,1)),
                accepted=np.ones(30,bool),valid=valid,N=np.repeat(4.,30),low20=np.repeat(98.,30),run=np.arange(1,31))
        # Full canonical parents keep the original anchor present after entry;
        # a one-row mother table would legitimately request observation exit.
        mothers=pd.DataFrame([dict(sequence_index=7+j,event_id='parent' if j==0 else 'parent'+str(j),
            product_id='P.X',family_id='P.X',u_date=dates[20+j],u_index=20+j,
            reference_epoch='P.X.202912') for j in range(10)])
        actions=pd.DataFrame([dict(action_id='child'+str(j),event_id='child'+str(j),action_sequence_index=42+j,
            mother_event_id='parent',mother_sequence_index=7,product_id='P.X',family_id='P.X',u_date=dates[20],
            u_index=20,reference_epoch=e,anchor_epoch='P.X.202912',u_action_eligible=1,
            entry_capacity_qty=10,N_u=4.,low20_u=98.,u_close=101.) for j,e in enumerate(store.series)])
        choices=pd.DataFrame([dict(mothers.iloc[0],policy='NARROW',scope='main',cutoff='2020-01-01',
            chosen_action_id='child'+str(j),chosen_action_sequence_index=42+j,chosen_epoch=e,
            anchor_epoch='P.X.202912',score=.4,selected=1,arm=arm)
            for j,(arm,e) in enumerate(zip(self.m.ARMS,store.series))])
        econ={e:dict(economics_status='exact_epoch_metadata_snapshot',contract_multiplier=10.,round_lot=1,
            tick_size=.1,vendor_margin_rate=.1) for e in store.series}
        boundaries={e:dict(K_index=23,K_date=dates[23],K_target_date='2020-01-01',
            K_state='within_calendar',K_after_sample_end=False) for e in store.series}
        return actions,mothers,choices,boundaries,self.m.CachedMarket(store),dates,econ

    def points(self):
        return [dict(window=w,cost=c,active_total_return_pct=10.,return_percentage_point_difference=1.,
            drawdown_percentage_point_difference=1.,ci95_low=.001,identification='identified')
            for w in self.m.WINDOWS for c in self.m.COSTS]

    def held(self,unknown=0):
        return dict(groups={g:dict(known_u_equal_mean_increment_R=0.,unknown_differential_selected_events=unknown,
            status='unknown' if unknown else 'supported',nominal_pass=True) for g in ('holdout_0','holdout_1')})

    def test_both_arms_keep_independent_child_anchor_and_K_without_changing_global_arms(self):
        a,m,c,b,market,dates,e=self.fixture();before=c.copy(deep=True)
        out={arm:self.m.make_arm_signals(a,m,c,b,market,dates,e,arm) for arm in self.m.ARMS}
        self.assertEqual(out['CONTROL54'].reference_epoch.tolist(),['P.X.203001'])
        self.assertEqual(out['CONCENTRATION54'].reference_epoch.tolist(),['P.X.202912'])
        self.assertEqual(out['CONTROL54'].anchor_epoch.tolist(),['P.X.202912'])
        self.assertEqual(out['CONCENTRATION54'].lifecycle_index.tolist(),[23])
        pd.testing.assert_frame_equal(c,before)
        self.assertEqual(self.m.author.ARMS,('A','B'))
        b['P.X.203001']['K_index']=21
        with self.assertRaisesRegex(ValueError,'D<K'):
            self.m.make_arm_signals(a,m,c,b,market,dates,e,'CONTROL54')

    def test_empty_arm_is_preserved_instead_of_reusing_the_other_arms_signals(self):
        a,m,c,b,market,dates,e=self.fixture();c.loc[c.arm.eq('CONTROL54'),'selected']=0
        s=self.m.make_arm_signals(a,m,c,b,market,dates,e,'CONTROL54')
        self.assertTrue(s.empty)
        self.assertEqual(len(self.m.make_arm_signals(a,m,c,b,market,dates,e,'CONCENTRATION54')),1)

    def test_eight_real_synthetic_books_checkpoint_before_any_metadata_and_retain_deferred_K(self):
        a,m,c,b,market,dates,e=self.fixture()
        signals={arm:self.m.make_arm_signals(a,m,c,b,market,dates,e,arm) for arm in self.m.ARMS}
        windows={w:[dates[21],dates[25]] for w in self.m.WINDOWS}
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory)
            books,accounts=self.m.run_account_checkpoints(out,signals,m,market,dates,e,windows,fixture=True)
            terminal=json.loads((out/'financial_terminal.json').read_text())
            self.assertEqual((terminal['cash_accounts_started'],terminal['new_cash_accounts']),(8,8))
            self.assertEqual(terminal['raw_ledgers_checkpointed'],8)
            self.assertTrue(terminal['fixture'])
            self.assertEqual(len(accounts),8)
            for spec in self.m.account_specs():
                book=books[(spec['arm'],spec['window'],spec['cost'])]
                self.assertEqual([f['side'] for f in book['fills']],['BUY','SELL'])
                self.assertEqual(book['fills'][-1]['date'],dates[25])
                self.assertEqual(book['open_episodes'],[])
                self.assertTrue((out/spec['account_id']/'checkpoint.json').exists())
                self.assertFalse((out/spec['account_id']/'summary.json').exists())
            # A missing report field must not erase or regenerate completed cash.
            with self.assertRaises(KeyError):self.m.build_disclosure({}, {})
            self.assertEqual(json.loads((out/'financial_terminal.json').read_text())['new_cash_accounts'],8)
            with self.assertRaises(FileExistsError):
                self.m.run_account_checkpoints(out,signals,m,market,dates,e,windows,fixture=True)

    def test_disclosure_reads_top_level_anchor_and_does_not_rededuct_slippage(self):
        p={'cash':{},'statistics':{'indices':{}}}
        x=self.m.build_disclosure(p,{'anchor_and_execution':{'immutable':True},'cash':{'capacity':{'rate':.01}}})
        self.assertTrue(x['anchor']['immutable'])
        self.assertFalse(x['slippage_deducted_again'])

    def test_second_book_failure_retains_first_checkpoint_and_attempt_counts(self):
        a,m,c,b,market,dates,e=self.fixture()
        signals={arm:self.m.make_arm_signals(a,m,c,b,market,dates,e,arm) for arm in self.m.ARMS}
        original=self.m.kernel.run_cash_account;calls=[]
        def run(*args,**kwargs):
            calls.append(args[5])
            if len(calls)==2:raise RuntimeError('synthetic second account failure')
            return original(*args,**kwargs)
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory)
            with patch.object(self.m.kernel,'run_cash_account',side_effect=run):
                with self.assertRaisesRegex(RuntimeError,'synthetic second'):
                    self.m.run_account_checkpoints(out,signals,m,market,dates,e,
                        {w:[dates[21],dates[25]] for w in self.m.WINDOWS},fixture=True)
            terminal=json.loads((out/'financial_terminal.json').read_text())
            self.assertEqual((terminal['cash_accounts_started'],terminal['new_cash_accounts'],
                terminal['raw_ledgers_checkpointed']),(2,1,1))
            self.assertEqual(terminal['status'],'failed')
            self.assertTrue((out/self.m.account_specs()[0]['account_id']/'checkpoint.json').exists())

    def test_reports_consume_all_new_checkpoints_with_zero_family_year_and_both_arms(self):
        a,m,c,b,market,dates,e=self.fixture()
        signals={arm:self.m.make_arm_signals(a,m,c,b,market,dates,e,arm) for arm in self.m.ARMS}
        # A zero family must remain visible without a synthetic entry.
        m=pd.concat([m,pd.DataFrame([dict(m.iloc[0],event_id='zero',product_id='Z.X',family_id='Z.X')])],ignore_index=True)
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory)
            books,accounts=self.m.run_account_checkpoints(out,signals,m,market,dates,e,
                {w:[dates[21],dates[25]] for w in self.m.WINDOWS},fixture=True)
            bindings=self.m.summarize_checkpoints(out,books,accounts,m,
                {w:np.tile(np.arange(5),(2000,1)) for w in self.m.WINDOWS},self.held())
            self.assertEqual(len(accounts),8)
            self.assertEqual(len([a for a in accounts if 'summary' in a]),8)
            family=pd.read_csv(bindings['family_year_including_zero']['path'])
            self.assertEqual(set(family.arm),set(self.m.ARMS))
            self.assertEqual(len(family.loc[family.family_id.eq('Z.X')]),8)
            self.assertTrue(family.loc[family.family_id.eq('Z.X'),'net_equity_contribution'].eq(0).all())
            gate=json.loads((out/'continuation_gate.json').read_text())
            self.assertFalse(gate['nominal_pass'])
            self.assertFalse(gate['held_diagnostic_is_K_cash_target'])

    def test_strict_primary_null_reference_DD_and_held_unknown_cannot_pass(self):
        good=self.m.fixed_gate(self.points(),self.held(),False,wealth_positive=True,execution_unknown=False)
        self.assertTrue(good['nominal_pass'])
        for case in ('null','equal'):
            points=self.points();points[1]['drawdown_percentage_point_difference']=None if case=='null' else 0.
            gate=self.m.fixed_gate(points,self.held(),False,wealth_positive=True,execution_unknown=False)
            self.assertFalse(gate['nominal_pass'])
            if case=='null':self.assertIn('unknown',gate['status'])
        gate=self.m.fixed_gate(self.points(),self.held(2),False,wealth_positive=True,execution_unknown=False)
        self.assertTrue(gate['cash_nominal_pass']);self.assertFalse(gate['nominal_pass'])
        self.assertFalse(gate['held_diagnostic_is_K_cash_target'])
        self.assertFalse(gate['production_qualified'])

    def test_pairs_are_concentration_minus_new_control_on_exact_calendar(self):
        daily={};summaries={}
        for arm in self.m.ARMS:
            for w in self.m.WINDOWS:
                for c in self.m.COSTS:
                    key=(arm,w,c)
                    daily[key]=pd.DataFrame(dict(date=['u1','u2'],equity=[1.1e6,1.21e6] if arm=='CONCENTRATION54' else [1e6,1e6],ever_insolvent=[False,False]))
                    summaries[key]=dict(total_return_pct=21. if arm=='CONCENTRATION54' else 0.,
                        max_drawdown_pct=-1. if arm=='CONCENTRATION54' else -2.,fills=2)
        points,dist=self.m.compare_accounts(summaries,daily,{w:np.tile([1,0],(2000,1)) for w in self.m.WINDOWS})
        self.assertEqual(len(points),4)
        self.assertEqual({p['contrast'] for p in points},{'CONCENTRATION54_minus_CONTROL54'})
        self.assertAlmostEqual(points[0]['ci95_low'],np.log(1.1))
        self.assertEqual(points[0]['return_percentage_point_difference'],21.)
        summaries[('CONTROL54','primary_2020','stress')]['max_drawdown_pct']=None
        points,_=self.m.compare_accounts(summaries,daily,{w:np.tile([1,0],(2000,1)) for w in self.m.WINDOWS})
        self.assertIsNone(points[1]['drawdown_percentage_point_difference'])


if __name__=='__main__':unittest.main()
