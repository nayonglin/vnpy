"""Seven bounded semantic fixtures; never opens accepted research inputs."""
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SOURCE = Path(__file__).with_name('stage162_member_distribution.py')
if SOURCE.exists():
    spec = importlib.util.spec_from_file_location('stage162', SOURCE)
    impl = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(impl)
else:
    impl = None


def row(rank, lq='', sq='', ln='', sn='', lid='', sid='', instrument='cu2001'):
    return dict(INSTRUMENTID=instrument, RANK=rank, CJ2=lq, CJ3=sq,
                PARTICIPANTABBR2=ln, PARTICIPANTABBR3=sn,
                PARTICIPANTID2=lid, PARTICIPANTID3=sid)


class MemberDistributionTest(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(impl, 'Stage162 implementation is missing')
        self.index = impl.build_epoch_index([
            dict(epoch='SHFE.CU.202001', product_id='SHFE.CU'),
            dict(epoch='INE.BC.202301', product_id='INE.BC'),
            dict(epoch='DCE.L.202301', product_id='DCE.L'),
            dict(epoch='DCE.L_F.202301', product_id='DCE.L_F'),
        ])

    def norm(self, rows, instrument='cu2001'):
        return impl.normalize_scope(rows, '2020-01-02', instrument, self.index)

    def test_independent_sides_exclude_category_and_999_from_hhi(self):
        # Catches treating 999/category as a participant or pairing side names.
        got = self.norm([row(1, 80, 50, '甲', '乙'), row(2, 20, 50, '乙', '丙'),
                         row(999, 100, 100, '合计', '合计'), row(-1, 9999, 9999)])
        self.assertEqual(got['scope_status'], 'verified')
        self.assertAlmostEqual(got['long_H'], .68)
        self.assertAlmostEqual(got['short_H'], .5)
        self.assertAlmostEqual(got['scalar_primary'], .18)
        self.assertEqual((got['long_named_count'], got['short_named_count']), (2, 2))

    def test_empty_slots_and_named_true_zero_are_distinct_and_totals_can_differ(self):
        # Catches filling empty slots with zero or enforcing long=short totals.
        got = self.norm([row(1, '5', 3.0, '', '乙', 'A'), row(2, '0.0', '', '丙', ''),
                         row(3), row(4, 0, 0), row(999, 5, 3, '合计', '合计')])
        self.assertEqual(got['scope_status'], 'verified')
        self.assertEqual((got['long_sum'], got['short_sum']), (5, 3))
        self.assertEqual((got['long_named_count'], got['long_true_zero']), (2, 1))
        self.assertEqual((got['long_empty_slots'], got['short_empty_slots']), (1, 2))
        self.assertEqual(got['long_absent_rank_count'], 16)
        self.assertEqual((got['long_unidentified_true_zero'], got['short_unidentified_true_zero']), (1, 1))
        self.assertEqual(got['scalar_primary'], 0)

    def test_invalid_quantities_duplicate_rank_and_side_identity_stay_unknown(self):
        # Catches silent quantity repair or deduplication of ambiguous members.
        cases = [
            ([row(1, '', 1, '甲', '乙')], 'missing_quantity'),
            ([row(1, -1, 1, '甲', '乙')], 'negative_quantity'),
            ([row(1, '2 lots', 1, '甲', '乙')], 'invalid_quantity'),
            ([row(1, '1e3', 1, '甲', '乙')], 'invalid_quantity'),
            ([row(1, '1,000', 1, '甲', '乙')], 'invalid_quantity'),
            ([row(1, True, 1, '甲', '乙')], 'invalid_quantity'),
            ([row(1, 1.5, 1, '甲', '乙')], 'invalid_quantity'),
            ([row(1, 2, 1, '', '乙')], 'missing_identity'),
            ([row(1, 1, 1, '甲', '乙'), row(1, 1, 1, '丙', '丁')], 'duplicate_rank'),
            ([row(1, 1, 1, '甲', '乙', 'A', 'B'),
              row(2, 1, 1, '丙', '丁', 'A', 'C')], 'duplicate_side_identity'),
        ]
        for rows, reason in cases:
            with self.subTest(reason=reason):
                got = self.norm(rows + [row(999, 2, 2, '合计', '合计')])
                self.assertEqual(got['scope_status'], 'unknown')
                self.assertIsNone(got['scalar_primary'])
                self.assertIn(reason, got['long_reasons'])

    def test_absent_or_mismatched_999_never_certifies_primary(self):
        # Catches admitting an unchecked sum or replacing 999 by computed sum.
        got = self.norm([row(1, 2, 4, '甲', '乙')])
        self.assertEqual(got['scope_status'], 'total_unverified')
        self.assertEqual(got['long_H'], 1)
        self.assertIsNone(got['scalar_primary'])
        bad = self.norm([row(1, 2, 4, '甲', '乙'), row(999, 3, 4, '合计', '合计')])
        self.assertEqual(bad['scope_status'], 'unknown')
        self.assertIn('total_mismatch', bad['long_reasons'])

    def test_exact_epoch_mapping_keeps_ine_f_and_ambiguous_century_separate(self):
        # Catches blanket SHFE mapping, F stripping, all fallback and year guessing.
        self.assertEqual(impl.resolve_instrument(' bc2301 ', self.index)['epoch'], 'INE.BC.202301')
        self.assertEqual(impl.resolve_instrument('l2301F', self.index)['epoch'], 'DCE.L_F.202301')
        self.assertEqual(impl.resolve_instrument('l2301', self.index)['epoch'], 'DCE.L.202301')
        self.assertEqual(impl.resolve_instrument('cuall', self.index)['mapping_state'], 'aggregate_all_excluded')
        ambiguous = impl.build_epoch_index([
            dict(epoch='SHFE.CU.192001', product_id='SHFE.CU'),
            dict(epoch='SHFE.CU.202001', product_id='SHFE.CU')])
        self.assertEqual(impl.resolve_instrument('cu2001', ambiguous)['mapping_state'], 'ambiguous_epoch')
        self.assertEqual(impl.resolve_instrument('cu2002', self.index)['mapping_state'], 'unmapped_instrument')

    def test_full_calendar_predecessor_never_ffills_or_uses_u_and_retains_all_identity(self):
        # Catches previous-success fallback, u-day lookahead and no-reference drops.
        cal = ['2020-01-02', '2020-01-03', '2020-01-06']
        scopes = {('2020-01-02', 'SHFE.CU.202001'): {'scope_id': 'old', 'scope_status': 'verified', 'scalar_primary': .5},
                  ('2020-01-06', 'SHFE.CU.202001'): {'scope_id': 'future', 'scope_status': 'verified', 'scalar_primary': .8}}
        days = {'2020-01-02': 'http_200', '2020-01-03': 'network_error', '2020-01-06': 'http_200'}
        inputs = [dict(sequence_index='0', event_id='a', product_id='SHFE.CU', family_id='CU', u_date='2020-01-06', u_index='2', reference_epoch='SHFE.CU.202001'),
                  dict(sequence_index='1', event_id='b', product_id='INE.BC', family_id='BC', u_date='2020-01-06', u_index='2', reference_epoch='')]
        got = [impl.project_identity(r, 'reference_epoch', cal, days, scopes) for r in inputs]
        self.assertEqual(len(got), 2)
        self.assertEqual(got[0]['v_date'], '2020-01-03')
        self.assertEqual(got[0]['projection_status'], 'source_day_unavailable')
        self.assertIsNone(got[0]['scalar_primary'])
        self.assertEqual(got[1]['projection_status'], 'no_reference_epoch')
        self.assertEqual(got[1]['sequence_index'], '1')

    def test_verified_archive_body_and_fresh_output_preserve_failure_evidence(self):
        # Catches parsing before original hashes or overwriting a previous attempt.
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            body = json.dumps({'o_cursor': [row(1, 1, 1, '甲', '乙')]}).encode()
            archive = gzip.compress(body)
            raw = p / 'source.gz'
            raw.write_bytes(archive)
            entry = dict(status='http_200', archive_path=str(raw), archive_bytes=len(archive),
                         archive_sha256=hashlib.sha256(archive).hexdigest(), raw_body_bytes=len(body),
                         raw_body_sha256=hashlib.sha256(body).hexdigest())
            parsed, audit = impl.read_verified_source(entry)
            self.assertEqual(parsed['o_cursor'][0]['CJ2'], 1)
            self.assertTrue(audit['body_hash_verified'])
            entry['raw_body_sha256'] = '0' * 64
            with self.assertRaisesRegex(ValueError, 'body_identity'):
                impl.read_verified_source(entry)
            out = p / 'fresh'
            impl.prepare_output(out)
            (out / 'started.json').write_text('{}')
            with self.assertRaises(FileExistsError):
                impl.prepare_output(out)
            self.assertTrue((out / 'started.json').exists())

    def test_action_aliases_preserve_distinct_mother_identity(self):
        # Catches mistaking mother IDs for aliases of the independent child ID.
        action = dict(sequence_index='7', action_sequence_index='7',
                      event_id='stage129_action:child', action_id='stage129_action:child',
                      actual_epoch='SHFE.CU.202001', reference_epoch='SHFE.CU.202001',
                      mother_sequence_index='2', mother_event_id='stage004_product_day:parent')
        try:
            impl.validate_action_identity(action)
        except ValueError as exc:
            self.fail('valid distinct mother/action identities were rejected: ' + str(exc))
        for key, value in [('reference_epoch', 'SHFE.CU.202002'),
                           ('action_sequence_index', '8'), ('action_id', 'wrong-child')]:
            with self.subTest(key=key):
                invalid = dict(action, **{key: value})
                with self.assertRaisesRegex(ValueError, 'action_identity_alias'):
                    impl.validate_action_identity(invalid)


if __name__ == '__main__':
    unittest.main()
