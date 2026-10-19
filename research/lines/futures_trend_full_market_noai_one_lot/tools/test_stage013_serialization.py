from datetime import date
import json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from stage004_run import safe
class Serialization(unittest.TestCase):
    def test_native_statistics_dates_are_json_safe(self):
        self.assertEqual(json.loads(json.dumps(safe({'start_date':date(2015,1,5)}))),{'start_date':'2015-01-05'})
