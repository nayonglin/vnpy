from pathlib import Path
import hashlib,json,tempfile,unittest
import pandas as pd
try:
    from stage024_execution_quotes import load_quantity_execution_overlay
except ModuleNotFoundError:
    load_quantity_execution_overlay=None

class QuoteLoaderTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.csv=self.root/'quotes.csv';self.receipt=self.root/'receipt.json'
        self.contracts=pd.DataFrame([dict(vt_symbol='al202110.SHFE',contract_epoch_id='SHFE.AL.202110',maturity_date='2021-10-15')])
        self.market=pd.DataFrame([dict(vt_symbol='al202110.SHFE',date='2021-09-23',open=100,high=101,low=99,close=100,volume=100,execution_only=False)])
        self.row=dict(vt_symbol='al202110.SHFE',contract_epoch_id='SHFE.AL.202110',date='2021-09-24',open=101,high=103,low=100,close=102,volume=5,
                      execution_only=True,allow_new_open=False,quantity_certified=False,quote_class='quantity_conflict_price_consensus_execution_only',evidence_id='test:1')
    def freeze(self,**change):
        pd.DataFrame([dict(self.row,**change)]).to_csv(self.csv,index=False)
        digest=hashlib.sha256(self.csv.read_bytes()).hexdigest()
        self.receipt.write_text(json.dumps(dict(rows=1,output=dict(sha256=digest))))
    def load(self):
        self.assertIsNotNone(load_quantity_execution_overlay,'missing quote-only loader')
        return load_quantity_execution_overlay(self.market,self.contracts,self.csv,self.receipt)
    def test_consensus_exit_quote_appended_without_altering_signal_rows(self):
        self.freeze();combined,binding=self.load()
        self.assertEqual(len(combined),2);self.assertEqual(combined.iloc[0].close,100)
        self.assertFalse(combined.iloc[0].execution_only);self.assertTrue(combined.iloc[1].execution_only)
        self.assertEqual(binding['bound_rows'],1)
    def test_tampered_unbound_quote_is_rejected(self):
        self.freeze();self.csv.write_text(self.csv.read_text().replace(',102,',',999,'))
        with self.assertRaises(ValueError):self.load()
    def test_new_open_or_certified_quantity_claim_or_zero_volume_rejected(self):
        for change in [dict(allow_new_open=True),dict(execution_only=False),dict(quantity_certified=True),dict(volume=0)]:
            with self.subTest(change=change):
                self.freeze(**change)
                with self.assertRaises(ValueError):self.load()
    def test_duplicate_accepted_key_rejected(self):
        self.freeze(date='2021-09-23')
        with self.assertRaises(ValueError):self.load()
    def test_wrong_epoch_or_post_maturity_quote_rejected(self):
        for change in [dict(contract_epoch_id='SHFE.AL.202111'),dict(date='2021-10-16')]:
            with self.subTest(change=change):
                self.freeze(**change)
                with self.assertRaises(ValueError):self.load()
if __name__=='__main__':unittest.main()
