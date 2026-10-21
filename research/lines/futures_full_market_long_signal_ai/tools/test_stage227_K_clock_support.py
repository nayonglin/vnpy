"""Four new tiny clock/gate/partition fixtures; zero accepted large inputs."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('fixture227', Path(__file__).with_name('stage227_K_clock_support.py'))
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)

CAL = ['2020-01-30', '2020-01-31', '2020-02-03', '2020-02-04', '2020-02-05', '2020-03-02']
END = '2020-02-05'
FIELDS = ['sequence_index','action_sequence_index','action_id','mother_sequence_index','mother_event_id',
          'product_id','family_id','u_date','u_index','reference_epoch','anchor_epoch','u_action_eligible',
          'D_index','label_history_ready20','participation_state','label_state','filled','trade_label_known',
          'entry_index','entry_date','exit_index','exit_date','unknown_index','unknown_date','label_known_date',
          'label_known_phase','participation_known_date','participation_known_phase','last_path_index','cancel_reason']


def row(seq=0, state='closed_complete_bar_model', **changes):
    result = dict.fromkeys(FIELDS, '')
    result.update(sequence_index=str(seq), action_sequence_index=str(seq), action_id='accepted-'+str(seq),
                  mother_sequence_index='0', mother_event_id='m0', product_id='DCE.a', family_id='DCE.a',
                  u_date=CAL[0], u_index='0', reference_epoch='DCE.a.202003', anchor_epoch='DCE.a.202003',
                  u_action_eligible='1', D_index='1', label_history_ready20='1', participation_state='filled',
                  label_state=state, filled='1', trade_label_known='0', entry_index='1', entry_date=CAL[1],
                  participation_known_date=CAL[1], participation_known_phase='after_close', last_path_index='1')
    if state == 'closed_complete_bar_model':
        result.update(trade_label_known='1', exit_index='1', exit_date=CAL[1],
                      label_known_date=CAL[1], label_known_phase='after_close')
    if state == 'known_nonparticipation':
        result.update(participation_state=state, filled='0', entry_index='', entry_date='',
                      last_path_index='', cancel_reason='stale_boundary_at_open')
    result.update(changes)
    return result


class ClockSupportFixtures(unittest.TestCase):
    def test_calendar_gate_strict_boundary_sentinel_and_unclipped_pending(self):
        cases = [(0,'DCE.a.202003','allowed_D_before_K',1),
                 (1,'DCE.a.202003','blocked_D_on_or_after_K',0),
                 (5,'DCE.a.202005','unknown_D_sentinel',None),
                 (5,'DCE.a.202001','blocked_beforecalendar',0),
                 (0,'DCE.a.202005','allowed_aftercalendar_D_before_target',1)]
        for u, epoch, state, allowed in cases:
            got = probe.action_gate(u, epoch, CAL, END)
            self.assertEqual((got['calendar_state'],got['calendar_allowed']), (state,allowed))
        got = probe.action_gate(0,'DCE.a.202005',CAL,END)
        self.assertEqual((got['K_index'],got['K_date'],got['K_target_date']), (None,None,'2020-04-01'))
        self.assertTrue(got['K_after_sample_end'])

    def test_exit_equality_unknown_absence_and_open_sample_clock(self):
        cases = [(row(), 'closed_before_K',0,0),
                 (row(exit_index='2',exit_date=CAL[2],last_path_index='2',label_known_date=CAL[2]),
                  'closed_on_K_priority_reprice',1,0),
                 (row(exit_index='3',exit_date=CAL[3],last_path_index='3',label_known_date=CAL[3]),
                  'closed_after_K',1,0),
                 (row(state='path_or_execution_unknown',unknown_index='3',unknown_date=CAL[3]),
                  'unknown_after_K',1,0),
                 (row(state='path_or_execution_unknown'), 'unknown_unclassified',0,1),
                 (row(state='entry_execution_unknown',filled='0',entry_index='',entry_date='',
                      participation_state='execution_unknown',unknown_index='1',unknown_date=CAL[1],last_path_index=''),
                  'unknown_before_K',0,1),
                 (row(state='open_right_censored'), 'open_K_reached',1,0),
                 (row(state='open_right_censored',reference_epoch='DCE.a.202005'), 'open_K_pending',0,1)]
        for raw, timing, support, unresolved in cases:
            got = probe.classify_action(raw,CAL,END)
            self.assertEqual((got['timing_state'],got['potential_clock_or_repricing_support'],
                              got['unresolved_clock_obscures_no_effect']), (timing,support,unresolved))
            self.assertEqual(got['path_state'],raw['label_state'])
        before = row(state='path_or_execution_unknown',reference_epoch='DCE.a.202001')
        self.assertEqual(probe.classify_action(before,CAL,END)['timing_state'],'K_before_calendar_unavailable')
        no_part = row(state='known_nonparticipation',reference_epoch='DCE.a.202001')
        self.assertEqual(probe.classify_action(no_part,CAL,END)['timing_state'],'known_nonparticipation')

    def test_complete_projection_parent_nochild_and_fixed_group_conservation(self):
        mothers = [dict(sequence_index='0',event_id='m0',product_id='DCE.a',family_id='DCE.a',
                        u_date=CAL[0],u_index='0',reference_epoch='DCE.a.202003'),
                   dict(sequence_index='1',event_id='m1',product_id='DCE.b',family_id='DCE.b',
                        u_date=CAL[2],u_index='2',reference_epoch='')]
        actions = [row(),row(1,exit_index='2',exit_date=CAL[2],last_path_index='2',label_known_date=CAL[2]),
                   row(2,state='path_or_execution_unknown'),row(3,state='known_nonparticipation'),
                   row(4,u_action_eligible='0'),row(5,state='open_right_censored')]
        projected=[];parents=[]
        got = probe.probe_metadata(mothers,iter(actions),CAL,END,6,projected.append,parents.append)
        all_counts = got['scopes']['all']
        self.assertEqual([all_counts[k] for k in ('action_count','primary_domain_count','potential_support_count',
                         'unresolved_primary_count','mother_count','nochild_mother_count')],[6,5,2,1,2,1])
        self.assertEqual(len(projected),6);self.assertEqual(len(parents),2)
        self.assertEqual((parents[0]['child_count'],parents[1]['child_count'],parents[1]['nochild']),(6,0,1))
        self.assertEqual([a['sequence_index'] for a in got['anchors']],['0','1','2','3','4','5'])
        self.assertEqual(got['fixed_partitions']['family'],['DCE.a','DCE.b'])
        for dim, entries in got['partitions'].items():
            for scope in ('all','2020onward'):
                selected = [r for r in entries if r['scope']==scope]
                for name in got['metric_columns']:
                    self.assertEqual(sum(r[name] for r in selected),got['scopes'][scope][name],(dim,scope,name))
        self.assertTrue(all(all(k in p for k in FIELDS) for p in projected))

    def test_malformed_clock_and_identity_stop_instead_of_imputing(self):
        corruptions = [('D_index','2'),('u_date',CAL[1]),('exit_date',CAL[2]),
                       ('unknown_index','2'),('u_action_eligible','2'),('label_state','invented_state')]
        for key,value in corruptions:
            with self.subTest(key=key),self.assertRaises(ValueError):
                probe.classify_action(row(**{key:value}),CAL,END)
        m = dict(sequence_index='0',event_id='m0',product_id='DCE.a',family_id='DCE.a',
                 u_date=CAL[0],u_index='0',reference_epoch='DCE.a.202003')
        with self.assertRaises(ValueError):
            probe.probe_metadata([m],iter([row(mother_event_id='wrong')]),CAL,END,1,lambda r:None,lambda r:None)


if __name__ == '__main__':
    unittest.main()
