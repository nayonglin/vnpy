"""One fixed actual-format MY regression; no historical/source payload or fitting."""
from pathlib import Path
import importlib.util
import unittest
import pandas as pd

HERE=Path(__file__).resolve().parent

class ActualMarketingYearLiteral(unittest.TestCase):
    def test_month_year_range_preserves_economic_phase_and_rejects_wrong_ranges(self):
        spec=importlib.util.spec_from_file_location('esr670_schema_fixture',HERE/'stage670_esr_schema_kernel.py')
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        def row(cid,my):
            return dict(source_row='1',period_end_date='1990-01-04',commodityId=str(cid),myDefinition=my,mycoTypeName='Standard',weekNumber='1',netSales='-5')
        frames={10:pd.DataFrame([row(10,'Sep 1989/Aug 1990')]),15:pd.DataFrame([row(15,'Oct 1989/Sep 1990')]),27:pd.DataFrame([row(27,'Aug 1989/Jul 1990')])}
        specs=[dict(commodity_id=10,MY_start_month=9),dict(commodity_id=15,MY_start_month=10),dict(commodity_id=27,MY_start_month=8)]
        actual=m.prepare_sources(frames,specs,dict(blackout_period_end_ranges=[]))
        self.assertEqual(actual.period_valid.tolist(),[True,True,True])
        self.assertEqual(actual.myDefinition.tolist(),['Sep 1989/Aug 1990','Oct 1989/Sep 1990','Aug 1989/Jul 1990'])
        for phase,days in zip(actual.phase,[125,95,156]):self.assertAlmostEqual(float(phase),days/365)
        spaced=m.prepare_sources({10:pd.DataFrame([row(10,' Sep  1989 / Aug  1990 ')])},[specs[0]],dict(blackout_period_end_ranges=[]))
        self.assertTrue(bool(spaced.iloc[0].period_valid))
        self.assertAlmostEqual(float(spaced.iloc[0].phase),125/365)
        for wrong in ['1989/1990','Sep 1989/Sep 1990','Sep 1989/Aug 1989','Oct 1989/Sep 1990','Sep 1989/Aug 1991']:
            invalid=m.prepare_sources({10:pd.DataFrame([row(10,wrong)])},[specs[0]],dict(blackout_period_end_ranges=[]))
            self.assertFalse(bool(invalid.iloc[0].period_valid),wrong)

if __name__=='__main__':unittest.main(verbosity=2)
