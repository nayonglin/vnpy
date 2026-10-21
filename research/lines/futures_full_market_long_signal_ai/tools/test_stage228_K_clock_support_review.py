"""Three independent, literal clock/partition fixtures; no old data or fit."""
import importlib.util
from pathlib import Path
import unittest

SOURCE = Path(__file__).with_name('stage228_K_clock_support_review.py')


def row(i=0, mother=0, state='closed_complete_bar_model', **updates):
    value = dict(sequence_index=str(i), action_sequence_index=str(i), action_id=f'a{i}',
                 mother_sequence_index=str(mother), mother_event_id=f'm{mother}',
                 product_id='DCE.L', family_id='DCE.L', u_date='2024-11-28', u_index='0',
                 reference_epoch='DCE.L.202501', anchor_epoch='DCE.L.202502',
                 u_action_eligible='1', D_index='1', label_history_ready20='1',
                 participation_state='filled', label_state=state, filled='1', trade_label_known='1',
                 entry_index='1', entry_date='2024-11-29', exit_index='2', exit_date='2024-12-02',
                 unknown_index='', unknown_date='', label_known_date='2024-12-02',
                 label_known_phase='AFTER_CLOSE', participation_known_date='2024-11-29',
                 participation_known_phase='AFTER_CLOSE', last_path_index='2', cancel_reason='')
    value.update({key: str(v) for key, v in updates.items()})
    return value


def mother(i=0):
    return dict(sequence_index=str(i), event_id=f'm{i}', product_id='DCE.L', family_id='DCE.L',
                u_date='2024-11-28', u_index='0', reference_epoch='DCE.L.202502')


class ClockReviewFixtures(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SOURCE.is_file(), 'independent clock classifier is not implemented')
        spec = importlib.util.spec_from_file_location('stage228_fixture', SOURCE)
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)
        self.cal = ['2024-11-28', '2024-11-29', '2024-12-02', '2024-12-03']

    def test_calendar_priority_strict_boundary_and_pending_not_clipped(self):
        # Mutations caught: <= admission, January underflow, clipping, sentinel-first.
        closed = row()
        d = self.m.derive_metadata(closed, self.cal, self.cal[-1])
        self.assertEqual((d['K_target_date'], d['K_index'], d['K_date']), ('2024-12-01', 2, '2024-12-02'))
        self.assertEqual((d['calendar_allowed'], d['calendar_state']), (True, 'allowed_D_before_K'))
        on = row(u_index=1, u_date='2024-11-29', D_index=2, entry_index=2, entry_date='2024-12-02')
        self.assertEqual(self.m.derive_metadata(on, self.cal, self.cal[-1])['calendar_allowed'], False)
        before = row(reference_epoch='DCE.L.202401', u_index=3, u_date='2024-12-03', D_index=4)
        self.assertEqual(self.m.derive_metadata(before, self.cal, self.cal[-1])['calendar_state'], 'blocked_beforecalendar')
        pending = row(reference_epoch='DCE.L.202503')
        p = self.m.derive_metadata(pending, self.cal, self.cal[-1])
        self.assertEqual((p['K_index'], p['K_date'], p['K_state']), (None, None, 'after_calendar_pending'))
        self.assertEqual(p['calendar_state'], 'allowed_aftercalendar_D_before_target')
        sentinel = row(reference_epoch='DCE.L.202503', u_index=3, u_date='2024-12-03', D_index=4)
        self.assertEqual(self.m.derive_metadata(sentinel, self.cal, self.cal[-1])['calendar_state'], 'unknown_D_sentinel')

    def test_same_day_reprice_missing_unknown_and_pending_open_stay_distinct(self):
        # Mutations caught: treating exit==K as unchanged, missing unknown as Y=0,
        # or treating a future/unknown K as the observed terminal session.
        on = self.m.derive_metadata(row(), self.cal, self.cal[-1])
        self.assertEqual(on['timing_state'], 'closed_on_K_priority_reprice')
        self.assertEqual(on['potential_clock_or_repricing_support'], True)
        before = row(exit_index=1, exit_date='2024-11-29', label_known_date='2024-11-29', last_path_index=1)
        self.assertEqual(self.m.derive_metadata(before, self.cal, self.cal[-1])['timing_state'], 'closed_before_K')
        after = row(exit_index=3, exit_date='2024-12-03', label_known_date='2024-12-03', last_path_index=3)
        self.assertEqual(self.m.derive_metadata(after, self.cal, self.cal[-1])['timing_state'], 'closed_after_K')
        unknown = row(state='entry_execution_unknown', participation_state='execution_unknown', filled=0,
                      trade_label_known=0, entry_index='', entry_date='', exit_index='', exit_date='',
                      label_known_date='', last_path_index='')
        self.assertEqual(self.m.derive_metadata(unknown, self.cal, self.cal[-1])['timing_state'], 'unknown_unclassified')
        unknown.update(unknown_index='3', unknown_date='2024-12-03')
        self.assertEqual(self.m.derive_metadata(unknown, self.cal, self.cal[-1])['timing_state'], 'unknown_after_K')
        opened = row(state='open_right_censored', trade_label_known=0, exit_index='', exit_date='', label_known_date='')
        self.assertEqual(self.m.derive_metadata(opened, self.cal, self.cal[-1])['timing_state'], 'open_K_reached')
        opened['reference_epoch'] = 'DCE.L.202503'
        self.assertEqual(self.m.derive_metadata(opened, self.cal, self.cal[-1])['timing_state'], 'open_K_pending')
        nonpart = row(state='known_nonparticipation', participation_state='known_nonparticipation', filled=0,
                      trade_label_known=0, entry_index='', entry_date='', exit_index='', exit_date='',
                      label_known_date='', last_path_index='', reference_epoch='DCE.L.202401')
        self.assertEqual(self.m.derive_metadata(nonpart, self.cal, self.cal[-1])['timing_state'], 'known_nonparticipation')
        with self.assertRaisesRegex(ValueError, 'date/index'):
            self.m.derive_metadata(row(exit_date='2024-12-03'), self.cal, self.cal[-1])

    def test_complete_partition_nochild_and_parent_identity_guard(self):
        # Mutations caught: dropping nochild/ineligible rows or grouping by child
        # anchor instead of preserving the original parent identity.
        values = [row(), row(1, u_action_eligible=0, exit_index=1, exit_date='2024-11-29',
                             label_known_date='2024-11-29', last_path_index=1)]
        empty = mother(1)
        empty['reference_epoch'] = ''  # accepted no-observation mothers have no anchor
        result = self.m.audit_rows([mother(), empty], values, self.cal, self.cal[-1], compare=False)
        self.assertEqual(result['counts']['action_rows'], 2)
        self.assertEqual(result['counts']['primary_domain_rows'], 1)
        self.assertEqual(result['counts']['mother_rows'], 2)
        self.assertEqual(result['counts']['nochild_mothers'], 1)
        self.assertEqual(result['groups']['global']['ALL']['action_rows'], 2)
        self.assertEqual(result['groups']['year']['2024']['primary_domain_rows'], 1)
        broken = row(anchor_epoch='DCE.L.202503')
        with self.assertRaisesRegex(ValueError, 'parent'):
            self.m.audit_rows([mother()], [broken], self.cal, self.cal[-1], compare=False)


if __name__ == '__main__':
    unittest.main()
