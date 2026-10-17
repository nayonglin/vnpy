import unittest
try:
    import stage256_freeze_pools as subject
except ModuleNotFoundError:
    subject = None


class FrozenPoolTests(unittest.TestCase):
    def test_all_months_have_ten_distinct_non_fu_and_fixed_fu(self):
        self.assertIsNotNone(subject, 'freeze implementation is required')
        dates = ['2024-12-31', '2025-01-27', '2025-02-28']
        rows = subject.random_memberships(subject.UNIVERSE, dates, 1)
        self.assertEqual(set(rows), set(dates))
        for members in rows.values():
            self.assertEqual(len(members), 11)
            self.assertEqual(len(set(members)), 11)
            self.assertEqual(members[-1], 'fu.SHFE')
            self.assertTrue(set(members[:-1]) <= set(subject.UNIVERSE))

    def test_random_path_is_reproducible_and_independent_of_job_order(self):
        self.assertIsNotNone(subject, 'freeze implementation is required')
        dates = ['2024-12-31', '2025-01-27', '2025-02-28']
        one = subject.random_memberships(subject.UNIVERSE, dates, 1)
        two = subject.random_memberships(subject.UNIVERSE, dates, 2)
        self.assertNotEqual(one, two)
        self.assertEqual(one, subject.random_memberships(subject.UNIVERSE, dates, 1))

    def test_invalid_universe_does_not_silently_change_draw(self):
        self.assertIsNotNone(subject, 'freeze implementation is required')
        with self.assertRaises(ValueError):
            subject.random_memberships(['fu.SHFE'] * 18, ['2024-12-31'], 1)
        with self.assertRaises(ValueError):
            subject.random_memberships(subject.UNIVERSE, ['2024-12-31'], 0)


if __name__ == '__main__':
    unittest.main()
