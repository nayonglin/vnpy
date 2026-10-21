"""New wrapper boundaries only; never import accepted financial kernel/data."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import pandas as pd

SOURCE=Path(__file__).with_name('stage286_wasde_offset_cash.py')


def module(case):
    case.assertTrue(SOURCE.exists(),'Stage286 implementation is missing')
    spec=importlib.util.spec_from_file_location('fixture286',SOURCE)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result


class NewSelectionBoundary(unittest.TestCase):
    def test_new_selected_actions_are_not_limited_to_the_old_4365(self):
        m=module(self)
        mothers=pd.DataFrame([
            dict(sequence_index=0,event_id='past',product_id='DCE.C',family_id='corn',u_date='2019-01-02',u_index=2,reference_epoch='DCE.C.201905'),
            dict(sequence_index=1,event_id='p1',product_id='DCE.C',family_id='corn',u_date='2020-01-02',u_index=5,reference_epoch='DCE.C.202005'),
            dict(sequence_index=2,event_id='p2',product_id='DCE.M',family_id='meal',u_date='2020-01-02',u_index=5,reference_epoch='DCE.M.202005')])
        choices=mothers.iloc[1:].copy().reset_index(drop=True)
        choices['chosen_action_id']=['never_in_old_signals',''];choices['selected']=[1,0]
        choices['scope']='main';choices['policy']='NARROW';choices['arm']=m.CANDIDATE
        original=choices.copy(deep=True)
        aliased,ids=m.prepare_choices(mothers,choices,expected_parents=2)
        self.assertEqual(ids,{'never_in_old_signals'})
        self.assertEqual(aliased.arm.tolist(),['VOLUNTARY_RESELECT','VOLUNTARY_RESELECT'])
        pd.testing.assert_frame_equal(choices,original)
        rows=[]
        for identity in ['old_only','never_in_old_signals']:
            row={name:'' for name in m.ACTION_FIELDS};row['action_id']=identity;row['mother_event_id']='p1';rows.append(row)
        consumed=[]
        def chunks():
            for row in rows:consumed.append(row['action_id']);yield pd.DataFrame([row])
        actions=m.collect_selected_actions(chunks(),ids)
        self.assertEqual(actions.action_id.tolist(),['never_in_old_signals'])
        self.assertEqual(consumed,['old_only','never_in_old_signals'])
        with self.assertRaises(ValueError):m.collect_selected_actions([pd.DataFrame(rows)],{'missing'})
        with self.assertRaises(ValueError):m.collect_selected_actions([pd.DataFrame([rows[1],rows[1]])],ids)
        with self.assertRaises(ValueError):m.prepare_choices(mothers,choices.iloc[:1],expected_parents=2)
        bad=choices.copy();bad.loc[0,'reference_epoch']='new_fake_canonical'
        with self.assertRaises(ValueError):m.prepare_choices(mothers,bad,expected_parents=2)

    def test_fixed_four_cash_counts_and_stress_only_four_predicate_gate(self):
        m=module(self)
        points=[dict(window=w,cost=c,ending_equity_difference=(1 if c=='stress' else -99),drawdown_percentage_point_difference=(1 if c=='stress' else -99)) for w in m.WINDOWS for c in m.COSTS]
        self.assertTrue(m.nominal_gate(points)['nominal_economic_pass'])
        points[-1]['drawdown_percentage_point_difference']=0
        self.assertFalse(m.nominal_gate(points)['nominal_economic_pass'])
        paired=m.pair_years([dict(year='2026',partial=True,return_pct=4.,cash_growth=40.,max_drawdown_pct=-3.)],
            [dict(year='2026',partial=True,return_pct=2.,cash_growth=20.,max_drawdown_pct=-5.)])
        self.assertEqual(paired[0]['growth_amount_difference'],20.)
        self.assertEqual(paired[0]['return_percentage_point_difference'],2.)
        self.assertEqual(paired[0]['drawdown_percentage_point_difference'],2.)
        self.assertTrue(paired[0]['partial'])
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'good';attempts=[]
            def run(spec):
                attempts.append(spec['account_id'])
                x=json.loads((out/'cash_progress.json').read_text())
                self.assertEqual((x['cash_accounts_started'],x['cash_accounts_completed']),(len(attempts),len(attempts)-1))
                return {}
            m.run_four(out,run,lambda spec,book:dict(spec))
            self.assertEqual(len(attempts),4)
            x=json.loads((out/'actual_terminal.json').read_text())
            self.assertEqual((x['cash_accounts_started'],x['cash_accounts_completed']),(4,4))
            with self.assertRaises(FileExistsError):m.run_four(out,run,lambda spec,book:dict(spec))
            bad=Path(tmp)/'bad';attempts=[]
            def failure(spec):
                attempts.append(spec['account_id'])
                if len(attempts)==2:raise RuntimeError('synthetic stop')
                return {}
            with self.assertRaises(RuntimeError):m.run_four(bad,failure,lambda spec,book:dict(spec))
            x=json.loads((bad/'actual_terminal.json').read_text())
            self.assertEqual((x['cash_accounts_started'],x['cash_accounts_completed']),(2,1))
            self.assertEqual(x['status'],'failed')


if __name__=='__main__':unittest.main()
