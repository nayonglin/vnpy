"""New importer behaviors only: independent literal calendars and stock arithmetic."""
from datetime import date, timedelta
import importlib.util
from pathlib import Path
import unittest

import pandas as pd

SOURCE = Path(__file__).with_name('stage060_eia_report_import.py')
spec = importlib.util.spec_from_file_location('stage060_subject', SOURCE) if SOURCE.exists() else None
m = importlib.util.module_from_spec(spec) if spec else None
if m is not None:
    spec.loader.exec_module(m)
LABELS = ['Commercial (Excluding SPR)', 'Total Motor Gasoline', 'Distillate Fuel Oil']


def archive(rows, year=2020):
    return '<table><tr><td></td><td colspan="2"><strong>' + str(year) + '</strong></td></tr>' + ''.join(
        '<tr><td>' + month + '</td><td><a href="' + url + '">' + release + '</a></td><td>' + ending + '</td></tr>'
        for month, url, release, ending in rows) + '</table>'


def report(rid, release, ending):
    return dict(report_id=rid, issue_url='https://www.eia.gov/petroleum/supply/weekly/archive/fixture/' + rid + '/wpsr.php',
                release_date=release, data_ending_expected=ending)


class ImportBehaviors(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(m, 'Stage060 importer behavior is not implemented')

    def test_archive_cross_year_release_and_data_ending_are_distinct(self):
        # A regression using data-ending year or URL date would fail this.
        h = archive([('January', '/petroleum/supply/weekly/archive/2020/2020_01_03/wpsr.php', '3', '12/27')])
        got = m.parse_archive_html(h)
        self.assertEqual([(x['release_date'], x['data_ending_expected']) for x in got], [('2020-01-03', '2019-12-27')])
        self.assertTrue(got[0]['issue_url'].startswith('https://www.eia.gov/'))

    def test_delayed_same_day_issues_use_release_cell_not_directory_day(self):
        h = archive([('June', '/petroleum/supply/weekly/archive/2022/2022_06_17_data/wpsr.php', '29', '17'),
                     ('', '/petroleum/supply/weekly/archive/2022/2022_06_29/wpsr.php', '29', '24')], 2022)
        got = m.parse_archive_html(h)
        self.assertEqual([x['release_date'] for x in got], ['2022-06-29', '2022-06-29'])
        self.assertEqual([x['data_ending_expected'] for x in got], ['2022-06-17', '2022-06-24'])
        self.assertEqual(len({x['report_id'] for x in got}), 2)

    def test_archive_orphan_td_group_is_retained_as_official_report(self):
        # Actual archive lacks opening tr for 2016/2017 November final rows.
        h = ('<table><tr><td></td><td colspan="2">2016</td><td colspan="2">2017</td></tr>'
             '<tr><td>November</td><td><a href="/petroleum/supply/weekly/archive/2016/2016_11_23/wpsr.php">23</a></td><td>18</td><td></td><td></td></tr>'
             '<td></td><td><a href="/petroleum/supply/weekly/archive/2016/2016_11_30/wpsr.php">30</a></td><td>25</td>'
             '<td><a href="/petroleum/supply/weekly/archive/2017/2017_11_29/wpsr.php">29</a></td><td>24</td></tr></table>')
        got = m.parse_archive_html(h)
        self.assertEqual([x['release_date'] for x in got], ['2016-11-23', '2016-11-30', '2017-11-29'])

    def test_upper_stock_exact_labels_convert_and_reject_bad_differences(self):
        # Treating lower table flows or SPR as stock would corrupt these literal answers.
        text = ('"STUB_1","12/27/19","12/20/19","Difference","Percent Change"\n'
                '"Crude Oil","999","998","1","0"\n'
                '"Commercial (Excluding SPR)","429.896","441.359","-11.463","0"\n'
                '"Strategic Petroleum Reserve (SPR)","634.967","634.967","0","0"\n'
                '"Total Motor Gasoline","242.472","239.260","3.212","0"\n'
                '"Distillate Fuel Oil","133.720","124.944","8.776","0"\n'
                '"STUB_1","STUB_2","12/27/19","12/20/19","Difference"\n'
                '"Distillate Fuel Oil","nonsense flow","9","8","1"\n')
        r = report('2020_01_03', '2020-01-03', '2019-12-27')
        got = m.parse_table1(text.encode(), r)
        self.assertEqual([x['series_label'] for x in got], LABELS)
        self.assertEqual([x['current'] for x in got], [429896., 242472., 133720.])
        self.assertEqual([x['delta'] for x in got], [-11463., 3212., 8776.])
        self.assertTrue(all(x['native_unit'] == 'million_barrels' and x['normalized_unit'] == 'thousand_barrels' for x in got))
        self.assertEqual(got[0]['data_ending'], '2019-12-27')
        with self.assertRaises(ValueError):
            m.parse_table1(text.replace('"-11.463"', '"-10.463"').encode(), r)

    def test_calendar_missing_ordinal_and_sham_never_use_future_or_inline_prior(self):
        reports = []; stocks = []
        for i in range(55):
            d = date(2018, 1, 3) + timedelta(weeks=i)
            reports.append(report(f'r{i:03}', str(d), str(d - timedelta(days=5))))
            if i != 1:
                stocks.extend(dict(report_id=f'r{i:03}', series_label=k, current=1000.+i,
                                   prior_inline=999999., delta=float(i+1)) for k in LABELS)
        got = m.make_report_signals(reports, stocks, pd.bdate_range('2018-01-01', '2019-02-01'), source_end='2019-02-01')
        self.assertEqual(len(got), 55)
        self.assertEqual(got.ordinal.tolist(), list(range(55)))
        self.assertTrue(pd.isna(got.iloc[53].s))  # lag1 was missing; no compression.
        self.assertAlmostEqual(got.iloc[54].s, -52./1053.)  # previous archived current, not inline prior.
        self.assertEqual(got.iloc[54].past_sham_report_id, 'r052')
        self.assertAlmostEqual(got.iloc[54].past_sham_s, -52./1051.)
        self.assertEqual(got.iloc[52].external_missing, 1)  # valid s, no past scalar.
        self.assertEqual((got.iloc[52].inventory_s, got.iloc[52].past_sham_s), (0., 0.))
        poisoned = stocks + [dict(report_id='future', series_label=k, current=1., delta=1e99) for k in LABELS]
        again = m.make_report_signals(reports, poisoned, pd.bdate_range('2018-01-01', '2019-02-01'), source_end='2019-02-01')
        pd.testing.assert_frame_equal(got, again)

    def test_explicit_unknown_stock_rows_remain_calendar_events_with_neutral_inputs(self):
        reports = [report('unknown', '2021-01-06', '2021-01-01')]
        stocks = [dict(report_id='unknown', series_label=k, current=None, delta=None) for k in LABELS]
        try:
            got = m.make_report_signals(reports, stocks, ['2021-01-07','2021-01-08'], source_end='2021-01-08')
        except TypeError as exc:
            self.fail('explicit null stock coverage must not crash or disappear: ' + str(exc))
        events = m.make_event_map(got)
        self.assertEqual(len(events), 1)
        self.assertEqual(events.iloc[0].stock_missing, 1)
        self.assertEqual(events.iloc[0].external_missing, 1)
        self.assertEqual((events.iloc[0].inventory_s, events.iloc[0].past_sham_s), (0., 0.))

    def test_conservative_dst_u_next_native_D_and_superseded_unique_event_interface(self):
        # NY date-end changes UTC with DST; Chinese named Thursday night open already happened.
        reports = [report('winter_old', '2021-01-06', '2020-12-25'),
                   report('winter_new', '2021-01-07', '2021-01-01'),
                   report('summer', '2021-07-07', '2021-07-02'),
                   report('tail', '2021-07-08', '2021-07-03')]
        dates = ['2021-01-08', '2021-01-11', '2021-07-08', '2021-07-09', '2021-07-12']
        got = m.make_report_signals(reports, [], dates, source_end='2021-07-09')
        self.assertEqual(got.iloc[0].available_at_utc, '2021-01-07T04:59:59+00:00')
        self.assertEqual(got.iloc[2].available_at_utc, '2021-07-08T03:59:59+00:00')
        self.assertEqual(got.iloc[2].u_date, '2021-07-08')
        self.assertEqual(got.iloc[2].native_D_date, '2021-07-09')
        self.assertTrue(got.iloc[0].superseded_before_first_decision)
        events = m.make_event_map(got)
        self.assertEqual(events.u_date.tolist(), ['2021-01-08', '2021-07-08', '2021-07-09'])
        self.assertEqual(events.report_id.tolist(), ['winter_new', 'summer', 'tail'])
        self.assertTrue({'u_date','report_id','s','past_sham_s','external_missing'}.issubset(events.columns))
        self.assertEqual(events.external_missing.tolist(), [1, 1, 1])
        self.assertEqual(events.iloc[-1].execution_state, 'pending_after_source_end')
        self.assertTrue(pd.isna(events.iloc[-1].native_D_date))


if __name__ == '__main__':
    unittest.main(verbosity=2)
