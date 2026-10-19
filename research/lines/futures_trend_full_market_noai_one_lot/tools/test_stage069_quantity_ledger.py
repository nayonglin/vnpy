"""Real financial matching: quantities, proportional costs and full entry episodes."""
import importlib.util,sys,unittest
from pathlib import Path
import pandas as pd
HERE=Path(__file__).parent
sys.path.insert(0,str(HERE))
ENTRY=HERE/'stage069_quantity_ledger.py'
if ENTRY.exists():
    spec=importlib.util.spec_from_file_location('quantity_ledger',ENTRY);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
else:
    import ast,types
    from collections import deque
    tree=ast.parse((HERE/'stage060_run_contract_weekly_long.py').read_text())
    function=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='closed_ledger')
    namespace={'pd':pd,'deque':deque}
    exec(compile(ast.Module(body=[function],type_ignores=[]),'old_actual_closed_ledger','exec'),namespace)
    mod=types.SimpleNamespace(closed_ledger=namespace['closed_ledger'])

def row(key,offset,volume,price,fee=0,slip=0,direction=None):
    return dict(trade_id=key,vt_symbol='x.DCE',offset=offset,direction=direction or ('long' if offset=='open' else 'short'),
        date='2020-01-02' if offset=='open' else '2020-01-03',price=price,volume=volume,commission=fee,slippage=slip,signal='long_case2')

class QuantityLedgerTests(unittest.TestCase):
    def ledger(self,rows):return mod.closed_ledger(pd.DataFrame(rows),{'x.DCE':{'size':10}})
    def test_whole_multi_contract_profit_and_fees_are_cash_totals(self):
        closed,residual=self.ledger([row('1','open',3,100,6,3),row('2','close',3,110,9,3)])
        self.assertEqual(len(closed),1);self.assertFalse(residual)
        self.assertEqual(closed.iloc[0].gross_pnl,300)
        self.assertEqual(closed.iloc[0].cost,21)
        self.assertEqual(closed.iloc[0].net_pnl,279)
        self.assertEqual(closed.iloc[0].volume,3)
    def test_partial_exit_is_one_completed_entry_episode_with_weighted_exit(self):
        closed,residual=self.ledger([row('1','open',3,100,6,3),row('2','close',1,110,2,1),row('3','close',2,120,4,2)])
        self.assertEqual(len(closed),1);self.assertFalse(residual)
        r=closed.iloc[0];self.assertEqual(r.gross_pnl,500);self.assertEqual(r.cost,18);self.assertEqual(r.net_pnl,482)
        self.assertAlmostEqual(r.exit_price,350/3);self.assertEqual(r.entry_trade_id,'1');self.assertEqual(r.volume,3)
    def test_unfinished_entry_excludes_partial_profit_from_complete_episode_win_rate(self):
        closed,residual=self.ledger([row('1','open',3,100,6,3),row('2','close',1,110,2,1)])
        self.assertEqual(len(closed),0);self.assertEqual(len(residual),1)
        r=residual[0];self.assertEqual(r['volume'],2);self.assertEqual(r['original_open_volume'],3)
        self.assertEqual(r['commission'],4);self.assertEqual(r['slippage'],2)
        self.assertEqual(len(r['realized_segments']),1);self.assertEqual(r['realized_segments'][0]['net_pnl'],94)
    def test_short_multi_contract_price_change_has_correct_sign(self):
        closed,_=self.ledger([row('1','open',4,100,direction='short'),row('2','close',4,90,direction='long')])
        self.assertEqual(closed.iloc[0].gross_pnl,400)
    def test_reject_overclose_duplicate_trade_fractional_or_nonpositive_volume(self):
        for rows in [[row('1','open',2,100),row('2','close',3,110)],
                     [row('1','open',2,100),row('1','close',2,110)],
                     [row('1','open',1.5,100)], [row('1','open',0,100)]]:
            with self.subTest(rows=rows):
                with self.assertRaises((ValueError,RuntimeError)):self.ledger(rows)
    def test_reject_adds_and_unmatched_closes(self):
        for rows in [[row('1','open',1,100),row('2','open',2,110)],[row('1','close',1,100)]]:
            with self.assertRaises((ValueError,RuntimeError)):self.ledger(rows)

if __name__=='__main__':unittest.main()
