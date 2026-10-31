"""Independent manual-ledger semantic corruption probes; fixture only."""
from pathlib import Path
import copy,json,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[4];sys.path[:0]=[str(ROOT),str(ROOT/'tests'),str(ROOT/'examples/portfolio_backtesting')]
import tests.test_weekly19_manual_cash as fixtures
import qmt_roll_weekly19_funding as funds
from qmt_roll_weekly19_funding_store import FundingStore
class ManualLedgerIndependent(unittest.TestCase):
 def forged_crossday(self):
  state,rid=fixtures.initial();at=fixtures.NOW.replace(month=11,day=2,hour=9,minute=1)
  current=fixtures.account(balance='150000.00',deposit='0.00',day='2026-11-02',at=at)
  record=fixtures.review(state,current,closed=[fixtures.close(dep=3000000)],topups=[fixtures.topup(rid)])
  updated=funds.apply_operator_cash_review(state,record,current,at,trading_calendar=fixtures.CALENDAR)
  bad=copy.deepcopy(updated);item=bad['manual_cash_reviews']['review-1'];raw=json.loads(item['raw_payload'])
  raw['closed_days'][0]['final_deposit_fen']=0
  item.update(fixtures.envelope(raw))
  bad['day_rolls'][0]['closing']=funds._operator_closing(raw['closed_days'][0]);bad['day_rolls'][0]['continuity_sha256']=item['raw_sha256']
  bad['receipts']['manual-bank-reference-1']['raw_sha256']=item['raw_sha256']
  return state,updated,bad
 def test_validate_rejects_claimed_topup_without_declared_gross_deposit(self):
  state,good,bad=self.forged_crossday();funds.validate_state(good)
  with self.assertRaises(ValueError,msg='Closed Friday Deposit0 cannot support Friday manual T30000 even with self-consistent hashes'):
   funds.validate_state(bad)
 def test_store_rejects_same_parent_corrupt_manual_review_before_commit(self):
  state,good,bad=self.forged_crossday()
  with tempfile.TemporaryDirectory(dir='/private/tmp')as temp:
   root=Path(temp).resolve();root.chmod(0o700);store=FundingStore(root/'cash.json')
   start=funds.initial_state(fixtures.ACCOUNT,fixtures.RELEASE,'2026-10-30');store.create(start);store.commit(0,state)
   with self.assertRaises(ValueError,msg='Crossday CAS cannot accept T increase unsupported by manual gross Deposit'):
    store.commit(state['revision'],bad)
   self.assertEqual(store.load(),state)
if __name__=='__main__':unittest.main(defaultTest='ManualLedgerIndependent')
