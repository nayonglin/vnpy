"""Bounded Stage206 contracts; synthetic books only, no historical I/O."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

TOOLS = Path(__file__).resolve().parent


def load():
    path = TOOLS/'stage206_local_curve_information_cash.py'
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location('fixture206', path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


class CashContracts(unittest.TestCase):
    def setUp(self):
        self.cash = load()
        self.assertIsNotNone(self.cash, 'Stage206 adapter missing')

    def test_four_candidate_specs_and_exact157_control_identity(self):
        c = self.cash
        specs = c.account_specs()
        self.assertEqual(len(specs), 4)
        self.assertEqual({s['arm'] for s in specs}, {'CURVE53'})
        accounts = [dict(s, arm='VOLUNTARY_RESELECT',
            account_id=f"NARROW_VOLUNTARY_RESELECT_{s['window']}_{s['cost']}",
            summary={'path': 'summary'}, ledgers={'daily': {'path': 'daily'}}) for s in specs]
        found = c.control_account_specs(dict(accounts=accounts))
        self.assertEqual(len(found), 4)
        self.assertTrue(all(s['source_only'] and not s['replayed'] for s in found))
        accounts[0]['account_id'] = 'NARROW_B_primary_2020_base'
        with self.assertRaisesRegex(ValueError, '157'):
            c.control_account_specs(dict(accounts=accounts))

    def test_all_four_CIs_and_strict_held_unknown_semantics(self):
        c = self.cash
        points = [dict(window=s['window'], cost=s['cost'], active_total_return_pct=10.,
            return_percentage_point_difference=1., drawdown_percentage_point_difference=1.,
            ci95_low=.001) for s in c.account_specs()]
        held = dict(groups={g: dict(known_u_equal_mean_increment_R=.01,
            nominal_pass=True, unknown_differential_selected_events=0, status='supported')
            for g in ('holdout_0','holdout_1')})
        gate = lambda: c.fixed_gate(points, held, False, wealth_positive=True,
                                    execution_unknown=False)
        self.assertTrue(gate()['nominal_pass'])
        points[-1]['ci95_low'] = 0.
        self.assertFalse(gate()['all_four_daily_log_CI_lower_positive'])
        points[-1]['ci95_low'] = .001
        held['groups']['holdout_1']['known_u_equal_mean_increment_R'] = -.0008020094736690167
        held['groups']['holdout_0']['unknown_differential_selected_events'] = 7
        self.assertFalse(gate()['nominal_pass'])
        self.assertFalse(gate()['held_known_strictly_positive_all_two'])
        self.assertTrue(gate()['held_signal_unknown'])
        held['groups']['holdout_1']['known_u_equal_mean_increment_R'] = 0.
        self.assertFalse(gate()['held_known_strictly_positive_all_two'])

    def fixture(self):
        c = self.cash; dates = [f'2020-01-{i:02d}' for i in range(1,31)]
        epoch = 'P.X.203001'; anchor = 'P.X.202912'
        store = c.cache_source.NativeBars(dates)
        for e in (epoch,anchor):
            store.series[e] = dict(days=np.arange(30), values=np.tile(
                [100.,102.,100.,101.,2000.],(30,1)), accepted=np.ones(30,bool),
                valid=np.ones(30,bool), N=np.repeat(4.,30),low20=np.repeat(98.,30),run=np.arange(1,31))
        mothers = pd.DataFrame([dict(sequence_index=j,event_id='p'+str(j),product_id='P.X',
            family_id='P.X',u_date=dates[20+j],u_index=20+j,reference_epoch=anchor) for j in range(10)])
        actions = pd.DataFrame([dict(action_id='a',event_id='a',action_sequence_index=42,
            mother_event_id='p0',mother_sequence_index=0,product_id='P.X',family_id='P.X',
            u_date=dates[20],u_index=20,reference_epoch=epoch,anchor_epoch=anchor,
            u_action_eligible=1,entry_capacity_qty=10,N_u=4.,low20_u=98.,u_close=101.)])
        choices = pd.DataFrame([dict(mothers.iloc[0],policy='NARROW',scope='main',cutoff='2020-01-01',
            chosen_action_id='a',chosen_action_sequence_index=42,chosen_epoch=epoch,
            anchor_epoch=anchor,score=.4,selected=1,arm='CURVE53')])
        econ = {e:dict(economics_status='exact_epoch_metadata_snapshot',contract_multiplier=10.,
            round_lot=1,tick_size=.1,vendor_margin_rate=.1) for e in store.series}
        boundaries = {e:dict(K_index=23,K_date=dates[23],K_target_date='2020-01-01',
            K_state='within_calendar') for e in store.series}
        market = c.CachedMarket(store)
        signals = c.make_signals(actions,mothers,choices,boundaries,market,dates,econ)
        self.assertEqual(choices.arm.tolist(), ['CURVE53'])
        self.assertEqual(signals.lifecycle_index.tolist(), [23])
        return signals,mothers,market,dates,econ

    def test_four_raw_books_before_metadata_and_no_replay(self):
        c = self.cash; signals,mothers,market,dates,econ = self.fixture()
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            books,accounts = c.run_account_checkpoints(out,signals,mothers,market,dates,econ,
                {w:[dates[21],dates[25]] for w in c.WINDOWS},fixture=True)
            terminal = json.loads((out/'financial_terminal.json').read_text())
            self.assertEqual((terminal['cash_accounts_started'],terminal['new_cash_accounts'],
                              terminal['raw_ledgers_checkpointed']), (4,4,4))
            self.assertEqual(len({id(b) for b in books.values()}),4)
            self.assertEqual(len(accounts),4)
            self.assertFalse((out/'account_summaries.csv.gz').exists())
            for spec in c.account_specs():
                self.assertTrue((out/spec['account_id']/'checkpoint.json').exists())
            with self.assertRaises(FileExistsError):
                c.run_account_checkpoints(out,signals,mothers,market,dates,econ,
                    {w:[dates[21],dates[25]] for w in c.WINDOWS},fixture=True)
            # Drive metadata from already-completed synthetic books only.
            control_accounts=[];control_reports={};control_fy=[]
            for spec in c.account_specs():
                w,cost=spec['window'],spec['cost'];book=books[(w,cost)]
                name=f'NARROW_VOLUNTARY_RESELECT_{w}_{cost}'
                summary,report,fy=c.helpers.cash_report(book,['P.X'],c.ref.INITIAL)
                capacity=dict(execution_unknown=book['execution_unknown'],unknown_capacity_fills=0,
                    capacity_unknown_roots=0,entry_execution_unknown=0)
                summary.update(capacity,account=name,arm='VOLUNTARY_RESELECT')
                report.update(capacity,account=name);control_reports[name]=report
                path=out/(name+'_summary.json');c.write_json(path,summary)
                control_accounts.append(dict(account_id=name,arm='VOLUNTARY_RESELECT',window=w,cost=cost,
                    summary=c.ref.file_binding(path),ledgers=dict(daily=next(a for a in accounts
                        if a['window']==w and a['cost']==cost)['ledgers']['daily'])))
                control_fy.append(c.report_helpers.add_family_costs(fy,book).assign(
                    arm='VOLUNTARY_RESELECT',window=w,cost=cost))
            dp=out/'control_diagnostics.json';c.write_json(dp,control_reports)
            fp=out/'control_family_year.csv.gz';c.ref.write_table(fp,pd.concat(control_fy),[])
            baseline=dict(accounts=control_accounts,diagnostics=c.ref.file_binding(dp),
                family_year_including_zero=c.ref.file_binding(fp))
            held=dict(groups={g:dict(known_u_equal_mean_increment_R=-.01,nominal_pass=False,
                unknown_differential_selected_events=7,status='unsupported') for g in ('holdout_0','holdout_1')})
            artifacts=c.summarize_checkpoints(out,books,accounts,mothers,
                {w:np.tile(np.arange(5),(2000,1)) for w in c.WINDOWS},held,baseline)
            self.assertIn('account_summaries',artifacts)
            self.assertFalse(json.loads((out/'continuation_gate.json').read_text())['nominal_pass'])
            rows=pd.read_csv(out/'account_summaries.csv.gz')
            self.assertEqual(len(rows),8)
            self.assertTrue({'closed_net_win_rate','closed_trades','total_fees','total_slippage'}.issubset(rows.columns))

    def test_saved_boolean_log_CI_and_native_json(self):
        c = self.cash
        a = pd.DataFrame(dict(date=['d1','d2'],equity=[1.1e6,1.21e6],ever_insolvent=['False','False']))
        b = pd.DataFrame(dict(date=['d1','d2'],equity=[1e6,1e6],ever_insolvent=['False','False']))
        stats,_ = c.paired_statistics(a,b,np.tile([1,0],(2000,1)))
        self.assertAlmostEqual(stats['ci95_low'],np.log(1.1))
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'native.json';c.write_json(p,dict(flag=np.bool_(False),count=np.int64(4)))
            self.assertEqual(json.loads(p.read_text()),dict(flag=False,count=4))


if __name__ == '__main__': unittest.main()
