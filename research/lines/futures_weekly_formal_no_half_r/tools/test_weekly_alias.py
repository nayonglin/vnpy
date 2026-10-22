from datetime import datetime,timedelta
import unittest
from test_weekly_adapter import AM,bar
from weekly_adapter import WeeklyArrayManager,completed_weeks
class AliasTests(unittest.TestCase):
    def test_decade_reused_contract_name_cannot_combine_20_plus_21_weeks(self):
        old=[(datetime(2010,1,8)+timedelta(weeks=i)).strftime('%Y-%m-%d') for i in range(20)]
        new=[(datetime(2020,1,3)+timedelta(weeks=i)).strftime('%Y-%m-%d') for i in range(21)]
        m=WeeklyArrayManager(AM(),completed_weeks(old+new))
        for d in old+new:m.update_bar(bar(d))
        self.assertEqual(m.count,21);self.assertFalse(m.inited);self.assertEqual(m.max_count,21)
if __name__=='__main__':unittest.main()
