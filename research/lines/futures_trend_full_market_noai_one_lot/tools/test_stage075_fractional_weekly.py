import importlib,unittest
from pathlib import Path
from types import SimpleNamespace
import pandas as pd
import test_stage059_contract_weekly_candidate as fixtures

try:module=importlib.import_module('stage075_fractional_weekly')
except ModuleNotFoundError as exc:
    if exc.name!='stage075_fractional_weekly':raise
    module=importlib.import_module('stage059_contract_weekly_candidate')

class NativePort:
    def _calculate_entry_sizing(self,*args,**kwargs):return {'selected_volume':3}
    def _open_position(self,state,contract,direction,volume,bar,signal,history,signal_data,sizing_snapshot=None):
        state.layers.append(SimpleNamespace(volume=volume,signal=signal,entry_price_synced=False))

class MultiWeeklyTests(unittest.TestCase):
    def fixture(self,bull=True,poison=False):
        cls=type('MultiWeekly',(module.WeeklyLongEntryMixin,NativePort),{})
        s=cls();s.strategy_engine=SimpleNamespace(weekly_contract=fixtures.Provider(bull,poison));s.source_symbol_by_contract={'rb202005.SHFE':'rb.SHFE'}
        state=SimpleNamespace(product_vt_symbol='rb.SHFE',layers=[])
        b=SimpleNamespace(datetime=pd.Timestamp('2019-12-31'));return s,state,b
    def test_three_contract_bullish_long_reaches_next_gate_and_retains_exact_receipt(self):
        s,state,b=self.fixture();s._open_position(state,'rb202005.SHFE','long',3,b,'long_case2',None,{},sizing_snapshot={})
        self.assertEqual(len(state.layers),1);self.assertEqual(state.layers[0].volume,3)
        self.assertEqual(state.layers[0].stage059_weekly_authorization.contract_vt_symbol,'rb202005.SHFE')
    def test_bearish_long_and_invalid_quantities_never_create_layer(self):
        for quantity,bull in [(3,False),(0,True),(-1,True),(True,True),(1.5,True)]:
            s,state,b=self.fixture(bull);s._open_position(state,'rb202005.SHFE','long',quantity,b,'long_case2',None,{})
            self.assertEqual(state.layers,[])
    def test_short_and_environment_probe_never_read_weekly(self):
        s,state,b=self.fixture(False,True);s._open_position(state,'rb202005.SHFE','short',3,b,'short_case2',None,{})
        self.assertEqual(state.layers[0].volume,3)
        sizing=s._calculate_entry_sizing('rb202005.SHFE','long',b,None,{},entry_context='env_probe')
        self.assertEqual(sizing['selected_volume'],3)

if __name__=='__main__':unittest.main()
