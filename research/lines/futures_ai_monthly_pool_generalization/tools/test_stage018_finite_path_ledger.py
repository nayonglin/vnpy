import unittest

from stage018_finite_path_ledger import Bar, Session, Position, enumerate_paths


def b(o,h,l,c):
    return Bar(o,h,l,c)


def s(day,*paths):
    return Session(day, tuple(tuple(p) for p in paths))


def position(**kw):
    return Position(**dict(direction='long',entry=100,stop=90,guard_tick=1,fill_tick=1,**kw))


class FiniteLedgerTests(unittest.TestCase):
    def test_identical_day_ohlc_keeps_stop_and_confirm_branches(self):
        day=s('2020-01-02',[b(100,101,89,95),b(95,111,94,100)],
              [b(100,111,99,105),b(105,106,89,100)])
        rows=enumerate_paths(position(),[day,s('2020-01-03',[b(100,121,99,120)])])
        self.assertEqual(len(rows),2)
        self.assertEqual([r['total_r'] for r in rows],[-1,2])
        self.assertEqual([r['position_open'] for r in rows],[False,True])
        self.assertEqual(rows[0]['path_choices'],[0,0])

    def test_short_mirror(self):
        longbars=[b(100,101,89,95),b(95,111,94,100)]
        mirror=[b(200-x.open,200-x.low,200-x.high,200-x.close) for x in longbars]
        r=enumerate_paths(Position('short',100,110,1,1),[s('2020-01-02',mirror)])[0]
        self.assertEqual(r['total_r'],-1)

    def test_confirmation_at_open_precedes_intrabar_adverse(self):
        r=enumerate_paths(position(),[s('2020-01-02',[b(100,109,99,105),b(111,111,89,100)])])[0]
        self.assertEqual(r['c2_state'],'confirmed')
        self.assertTrue(r['position_open'])

    def test_same_minute_both_uses_reference_policy(self):
        r=enumerate_paths(position(),[s('2020-01-02',[b(100,111,89,100)])])[0]
        self.assertEqual(r['total_r'],-1)
        self.assertEqual(r['c2_state'],'stopped')

    def test_neither_expires_at_end_of_entry_session(self):
        r=enumerate_paths(position(),[s('2020-01-02',[b(100,109,91,100)]),
                                     s('2020-01-03',[b(89,101,80,100)])])[0]
        self.assertEqual(r['c2_state'],'entry_session_expired')
        self.assertTrue(r['position_open'])
        self.assertEqual(r['total_r'],0)

    def test_gap_loss_is_not_clipped_and_no_retry(self):
        r=enumerate_paths(position(),[s('2020-01-02',[b(100,101,95,96),b(85,89,84,88)]),
                                     s('2020-01-03',[b(100,151,99,150)])])[0]
        self.assertEqual(r['total_r'],-1.5)
        self.assertFalse(r['position_open'])
        self.assertEqual(r['trace'][-1]['unrealized_r'],0)

    def test_unreachable_fill_is_unknown_not_zero(self):
        p=Position('long',100,90.3,.1,1)
        r=enumerate_paths(p,[s('2020-01-02',[b(100,101,95,96),b(91,91,90.2,90.5)])])[0]
        self.assertEqual(r['status'],'execution_unknown')
        self.assertIsNone(r['total_r'])

    def test_guard_tick_distinct_from_fill_tick(self):
        p=Position('long',100,99.5,.1,1)
        r=enumerate_paths(p,[s('2020-01-02',[b(100,100.1,99,99.2)])])[0]
        self.assertEqual(r['total_r'],-2)

    def test_subtick_guard_is_inactive_without_flooring_r(self):
        p=Position('long',100,99.5,1,1)
        r=enumerate_paths(p,[s('2020-01-02',[b(100,101,99,99)])])[0]
        self.assertEqual(r['c2_state'],'guard_inactive')
        self.assertTrue(r['position_open'])
        self.assertEqual(r['risk'],.5)
        self.assertEqual(r['total_r'],-2)

    def test_source_effective_guard_has_one_nanounit_floor(self):
        p=Position('long',1e-8,9.5e-9,1e-12,1e-12)
        r=enumerate_paths(p,[s('2020-01-02',[b(1e-8,1.01e-8,9.4e-9,9.6e-9)])])[0]
        self.assertEqual(r['c2_state'],'guard_inactive')
        self.assertTrue(r['position_open'])
        self.assertAlmostEqual(r['total_r'],-.8)

    def test_missing_after_stop_does_not_erase_known_realized(self):
        r=enumerate_paths(position(),[s('2020-01-02',[b(100,101,89,95)]),
                                     Session('2020-01-03',None)])[0]
        self.assertEqual(r['status'],'known')
        self.assertEqual(r['total_r'],-1)
        self.assertTrue(r['trace'][1]['path_missing'])

    def test_missing_day_preserved_unknown_and_absorbing(self):
        r=enumerate_paths(position(),[s('2020-01-02',[b(100,109,91,105)]),
                                     Session('2020-01-03',None),s('2020-01-06',[b(100,121,99,120)])])[0]
        self.assertEqual(r['status'],'path_unknown')
        self.assertIsNone(r['total_r'])
        self.assertEqual(len(r['trace']),3)

    def test_fixed_initial_r_and_mark_is_not_final_exit(self):
        r=enumerate_paths(position(),[s('2020-01-02',[b(100,111,99,110)]),
                                     s('2020-01-03',[b(110,121,109,120)])])[0]
        self.assertEqual(r['risk'],10)
        self.assertEqual(r['trace'][0]['total_r'],1)
        self.assertEqual(r['total_r'],2)
        self.assertEqual(r['realized_r'],0)

    def test_five_days_all_explicit_paths_and_no_merge(self):
        a=[b(100,101,99,100),b(100,101,99,100)]
        z=[b(100,100,99,100),b(100,101,99,100)]
        days=[s(f'2020-01-0{n}',a,z) for n in range(2,7)]
        rows=enumerate_paths(position(),days)
        self.assertEqual(len(rows),32)
        self.assertEqual(len({tuple(r['path_choices']) for r in rows}),32)
        self.assertTrue(all(len(r['trace'])==5 for r in rows))

    def test_reject_invalid_contracts(self):
        day=s('2020-01-02',[b(100,109,91,100)])
        for p in [Position('long',90,95,1,1),Position('other',100,90,1,1),
                  Position('long',100,90,1,0)]:
            with self.assertRaises(ValueError):enumerate_paths(p,[day])
        with self.assertRaises(ValueError):enumerate_paths(position(),[day]*2)
        with self.assertRaises(ValueError):enumerate_paths(position(),[])
        with self.assertRaises(ValueError):enumerate_paths(position(),[s('2020-01-02',[b(101,109,91,100)])])
        with self.assertRaises(ValueError):enumerate_paths(position(),[s('2020-01-02',[b(100,99,101,100)])])
        with self.assertRaises(ValueError):enumerate_paths(position(),[s('2020-01-02',[b(100,109,91,100)],[b(100,110,91,100)])])
        with self.assertRaises(ValueError):enumerate_paths(position(),[s('2020-01-02',[b(100,109,91,100)],[b(100,109,91,100),b(100,109,91,100)])])

    def test_budget_rejects_instead_of_truncating(self):
        path=[b(100,101,99,100)]
        days=[s(f'2020-01-0{n}',path,path,path,path) for n in range(2,7)]
        with self.assertRaisesRegex(ValueError,'budget'):enumerate_paths(position(),days)
        with self.assertRaises(ValueError):enumerate_paths(position(),days+[s('2020-01-07',path)])


if __name__=='__main__':unittest.main()
