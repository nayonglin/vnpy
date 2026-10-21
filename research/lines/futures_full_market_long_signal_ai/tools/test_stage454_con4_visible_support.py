"""Eight synthetic clock/identity risks; no actual research input is loaded."""
import importlib.util
import json
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('con4_454', HERE/'stage454_con4_visible_support.py')
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)
CLOCK = json.loads((HERE.parent/'outputs/stage453_Con4_fixed_protocol/protocol.json').read_text())['clock_contract451']


def row(day, value=.25, code='002602', channel='DCE.C'):
    return dict(asof=day, market_code=code, channel=channel, Con4Net_All=value,
                unknown_reasons=[], status='known_Con', observed_origins=[])


class ClockRisks(unittest.TestCase):
    def build(self, rows, clock=CLOCK):
        self.assertTrue(hasattr(MOD, 'compile_clock'), 'missing frozen clock implementation')
        return MOD.compile_clock(rows, clock)

    def value(self, compiled, day, product='DCE.C'):
        mothers=pd.DataFrame([dict(sequence_index=0,event_id='m0',product_id=product,
            family_id=product,u_date=day,u_index=123,reference_epoch='')])
        return MOD.project_mothers(mothers, *compiled).iloc[0]

    def test_ordinary_deferred_is_not_unknown_and_known_zero_survives(self):
        c=self.build([row('2020-01-07',0.),row('2020-01-14',.5)])
        self.assertTrue(np.isnan(self.value(c,'2020-01-17').q_raw))
        self.assertEqual(self.value(c,'2020-01-18').q_raw,0.)
        self.assertEqual(self.value(c,'2020-01-24').q_raw,0.)
        self.assertEqual(self.value(c,'2020-01-25').q_raw,.5)
        self.assertEqual(self.value(c,'2020-01-25','DCE.J').unknown_reason,'structurally_unmapped')
        self.assertEqual(self.value(c,'2020-01-25','DCE.J').source_episode_index,-1)

    def test_seven_ny_calendar_days_cross_dst_and_half_open_expiry(self):
        c=self.build([row('2023-02-28',.6)],clock={**CLOCK,'mask_decisions_10':[],
            'publication_event_decisions_54':[], 'correction_decisions_11':[]})
        ep=c[0][0]
        self.assertEqual(ep['research_available_at'],'2023-03-11T00:00:00-05:00')
        self.assertEqual(ep['research_expiry_at'],'2023-03-18T00:00:00-04:00')
        self.assertEqual(ep['expiry_utc_epoch']-ep['available_utc_epoch'],167*3600)
        self.assertEqual(self.value(c,'2023-03-17').q_raw,.6)
        self.assertTrue(np.isnan(self.value(c,'2023-03-18').q_raw))

    def test_interruption_cancels_pre_gap_pending_grant_and_source_tail(self):
        c=self.build([row('2025-09-16',.1),row('2025-09-23'),row('2025-09-30'),row('2025-12-30')])
        self.assertTrue(all(e['research_available_at'] is None for e in c[0][1:]))
        self.assertIn('ordinary_grant_crosses_interruption',c[0][1]['row_quarantine_reasons'])
        self.assertEqual(self.value(c,'2025-09-27').q_raw,.1)
        self.assertEqual(self.value(c,'2025-10-02').q_raw,.1)
        self.assertTrue(np.isnan(self.value(c,'2025-10-03').q_raw))
        self.assertTrue(np.isnan(self.value(c,'2026-01-01').q_raw))

    def test_revision_unknown_consumes_asof_before_same_instant_older_grant(self):
        c=self.build([row('2019-10-08',.1),row('2019-10-15',.9),row('2019-10-22',.4)])
        self.assertIsNone(c[0][1]['research_available_at'])
        self.assertIn('revision_quarantine',c[0][1]['row_quarantine_reasons'])
        self.assertTrue(np.isnan(self.value(c,'2019-10-19').q_raw))
        self.assertTrue(np.isnan(self.value(c,'2019-10-26').q_raw))
        self.assertEqual(self.value(c,'2019-11-02').q_raw,.4)

    def test_all_seven_ion_overrides_and_mar17_reset_tie(self):
        days=['2023-01-31','2023-02-07','2023-02-14','2023-02-21','2023-02-28','2023-03-07','2023-03-14']
        c=self.build([row(d,(i+1)/10) for i,d in enumerate(days)])
        self.assertEqual([e['research_available_at'][:10] for e in c[0]],
            ['2023-02-25','2023-03-04','2023-03-09','2023-03-11','2023-03-15','2023-03-17','2023-03-22'])
        self.assertEqual(self.value(c,'2023-03-17').q_raw,.6)
        self.assertEqual(c[0][5]['position_asof_alignment_status'],
            'unique_native_date_to_explicit_original_scheduled_slot_retrospective_assumption_not_source_confirmed_asof')
        self.assertEqual(self.value(c,'2023-03-22').q_raw,.7)

    def test_masks_guards_and_confirmed_monday_obey_priority(self):
        c=self.build([row('2013-09-24'),row('2013-11-05'),row('2013-11-12'),
            row('2018-12-18'),row('2019-03-26',code='085692',channel='SHFE.CU'),
            row('2015-06-30'),row('2020-12-21'),row('2012-12-24')])
        self.assertIsNone(c[0][0]['research_available_at'])
        self.assertIsNone(c[0][1]['research_available_at'])
        self.assertEqual(c[0][2]['clock_status'],'normal_after_expected_resumption_assumption')
        self.assertIsNone(c[0][3]['research_available_at'])
        self.assertEqual(c[0][4]['research_available_at'],'2019-03-30T00:00:00-04:00')
        self.assertIn('unaligned_event',c[0][5]['row_quarantine_reasons'])
        self.assertEqual(c[0][6]['research_available_at'],'2020-12-29T00:00:00-05:00')
        self.assertIsNone(c[0][7]['research_available_at'])

    def test_later_old_confirmed_report_cannot_replace_newer_consumed_asof(self):
        event=dict(event_id='synthetic_delayed',decision='date_confirmed_release_override_next_NY_midnight',
            proposed_native_asof_for_design='2020-01-07',proposed_research_available_at='2020-01-29T00:00:00-05:00',
            position_asof_alignment_status='explicit_source_position_asof',
            source_fields=dict(confirmed_release_date='2020-01-28',confirmed_release_at=None,
                original_scheduled_release_date='2020-01-10',position_asof='2020-01-07'))
        clock={**CLOCK,'publication_event_decisions_54':[event]}
        c=self.build([row('2020-01-07',.1),row('2020-01-14',.9)],clock)
        self.assertEqual(self.value(c,'2020-01-29').q_raw,.9)
        self.assertTrue(np.isnan(self.value(c,'2020-02-01').q_raw))
        self.assertIn('older_than_consumed_source_asof',c[0][0]['row_quarantine_reasons'])

    def test_support_uses_original_weights_and_identity_and_deduplicated_release(self):
        self.assertTrue(hasattr(MOD,'support_summary'),'missing source support implementation')
        frame=pd.DataFrame(dict(family_id=['a','a','b','b'],u_date=['2020-01-01']*4,
            q_raw=[0.,1.,np.nan,1.],availability_group_id=['g1','g2','','g2'],
            release_episode_id=['e1','e2','','e2'],source_asof=['2018-12-25','2019-01-01','','2019-01-01'],
            source_CFTC_code=['002602']*4,clock_status=['assumed_normal_week']*4,
            unknown_reason=['','','clock_quarantine','']))
        s=MOD.support_summary(frame,np.array([1.,3.,100.,1.]))
        self.assertAlmostEqual(s['q_statistics']['mean'],.8)
        self.assertAlmostEqual(s['q_statistics']['var'],.16)
        self.assertEqual(s['availability_groups'],2)
        self.assertEqual(s['mapped_families'],2)
        self.assertAlmostEqual(s['availability_weight_concentration']['max_share'],.8)
        mothers=pd.DataFrame(dict(sequence_index=[0],product_id=['DCE.C'],family_id=['corn'],u_date=['2018-01-01'],u_index=[1]))
        train=pd.DataFrame(dict(sequence_index=[4],mother_sequence_index=[0],product_id=['DCE.C'],family_id=['WRONG'],u_date=['2018-01-01'],u_index=[1],sample_weight=[1.]))
        with self.assertRaisesRegex(ValueError,'parent_identity_family_id'):
            MOD.validate_training_identity(train,mothers,dict(training_rows=1,scope='main',cutoff='2020-01-01'))


if __name__=='__main__': unittest.main()
