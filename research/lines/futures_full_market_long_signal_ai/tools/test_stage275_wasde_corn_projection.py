"""Three synthetic World Corn/date/unknown tests; zero real raw or finance."""
import importlib.util
from pathlib import Path
import unittest

p=Path(__file__).with_name('stage275_wasde_corn_projection.py')
s=importlib.util.spec_from_file_location('tiny275',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)


def row(attribute,value,**updates):
    r=dict(WasdeNumber='999',ReportDate='June 2024',ReportTitle='World Corn Supply and Use',Attribute=attribute,
        ReliabilityProjection='',Commodity='Corn',Region='World',MarketYear='2024/25',ProjEstFlag='Proj.',
        AnnualQuarterFlag='Annual',Value=value,Unit='Million Metric Tons',ReleaseDate='2024-06-12',
        ReleaseTime='0.5000000',ForecastYear='2024',ForecastMonth='6',source_filename='fixture.csv',
        source_member='',source_row='1',source_line_end='2',source_sha256='synthetic',visible_version_suffix='',row_parse_state='parsed')
    r.update(updates);return r


def pair(**updates):return [row('Ending Stocks','200',**updates),row('Domestic Total','1000',source_row='2',**updates)]


class TestStage275(unittest.TestCase):
    def function(self,name):
        self.assertTrue(callable(getattr(m,name,None)),'frozen274 quantity behavior missing')
        return getattr(m,name)

    def test_current_vintage_highest_year_must_remain_proj_no_old_proj_fallback(self):
        project=self.function('project_report')
        rows=pair()+pair(MarketYear='2025/26',ForecastMonth='5')
        got=project(rows)
        self.assertTrue(got['feature_eligible']);self.assertEqual(got['marketing_year'],'2024/25')
        self.assertEqual((got['S_text'],got['U_text'],got['q_raw']),('200','1000','0.2'))
        got=project(rows+pair(MarketYear='2025/26',ProjEstFlag='Est.'))
        self.assertFalse(got['feature_eligible']);self.assertEqual(got['marketing_year'],'2025/26')
        self.assertEqual(got['unknown_reason'],'latest_marketing_year_not_unique_Proj')

    def test_explicit_dates_and_two_calendar_day_new_york_delay_across_dst(self):
        parse=self.function('release_date');boundary=self.function('candidate_boundary');project=self.function('project_report')
        self.assertEqual(parse('03/09/2024').isoformat(),'2024-03-09')
        self.assertEqual(parse('2024-03-09').isoformat(),'2024-03-09')
        self.assertEqual(boundary(parse('2024-03-09')),'2024-03-11T04:00:00+00:00')
        self.assertEqual(boundary(parse('2024-11-02')),'2024-11-04T05:00:00+00:00')
        got=project(pair(ReleaseDate='06/12/2024'))
        self.assertTrue(got['feature_eligible']);self.assertEqual(got['release_date'],'2024-06-12')
        self.assertEqual(got['ReleaseTime_literals'],['0.5000000'])
        with self.assertRaises(ValueError):parse('June 2024')

    def test_duplicates_unit_missing_conflict_and_visible_v2_stay_unknown(self):
        project=self.function('project_report')
        cases=[(pair()+[row('Ending Stocks','200')],'duplicate_or_missing_quantity_pair'),
            ([row('Ending Stocks','200')],'duplicate_or_missing_quantity_pair'),
            ([row('Ending Stocks','200',Unit='Bushels'),row('Domestic Total','1000')],'quantity_unit_mismatch'),
            ([row('Ending Stocks','200'),row('Domestic Total','1000',ReportDate='May 2024')],'report_release_month_conflict')]
        for rows,reason in cases:
            with self.subTest(reason=reason):
                got=project(rows);self.assertFalse(got['feature_eligible']);self.assertEqual(got['unknown_reason'],reason)
                self.assertEqual(got['q_raw'],'')
        got=project(pair(visible_version_suffix='V2',source_filename='fixture-V2.csv'))
        self.assertFalse(got['feature_eligible']);self.assertEqual(got['q_raw'],'0.2')
        self.assertEqual((got['unknown_reason'],got['correction_known_at']),('visible_V2_correction_time_unknown','unknown'))


if __name__=='__main__':unittest.main()
