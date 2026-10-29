import unittest,json
from copy import deepcopy
from pathlib import Path
from run_stage001 import normalize_settings,LINE,FROZEN
class EmptySignals(unittest.TestCase):
 def test_real_failed_settings_only_isolated_empty_signals_are_allowed(self):
  r=json.loads((FROZEN/'R_attempt003/actual_strategy_settings.json').read_text())[0]
  current=json.loads((LINE/'outputs/stage001_A_attempt002/actual_strategy_settings.json').read_text())[0]
  data=LINE/'outputs/data_stage001_20261029/data_approved';approved=json.loads((data/'receipt.json').read_text()).get('approved_new_metadata',{})
  for section in ['setting','actual']:
   self.assertEqual(normalize_settings(current[section],r[section],str(data/'mapping.csv'),approved),r[section])
if __name__=='__main__':unittest.main()
