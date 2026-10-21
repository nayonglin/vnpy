"""Finite independent source-review counterexamples; no real source or actual."""
import importlib.util
from pathlib import Path
import unittest

SOURCE=Path(__file__).with_name('stage163_member_distribution_review.py')


class DistributionReviewFixtures(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SOURCE.is_file(),'Stage163 independent source reviewer missing')
        spec=importlib.util.spec_from_file_location('review163_fixture',SOURCE)
        self.r=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.r)

    def test_two_side_shapes_are_independent_and_999_is_not_a_member(self):
        vectors=[dict(rank=1,id='A',name='a',qty_state='finite_integer',qty=3,source_row=0),dict(rank=2,id='B',name='b',qty_state='finite_integer',qty=1,source_row=1)]
        got=self.r.vector_math(vectors,4)
        self.assertEqual((got['sum'],got['sumsq'],got['named_count']),(4,10,2))
        self.assertAlmostEqual(got['H'],.625)
        with self.assertRaises(AssertionError):self.r.vector_math(vectors+[dict(vectors[0],rank=999)],8)

    def test_unequal_side_lengths_and_empty_slots_do_not_mean_zero_members(self):
        long=[dict(rank=1,id='A',name='a',qty_state='finite_integer',qty=6,source_row=0),dict(rank=2,id='B',name='b',qty_state='finite_integer',qty=2,source_row=1)]
        short=[dict(rank=1,id='Z',name='z',qty_state='finite_integer',qty=8,source_row=0),dict(rank=2,id='',name='',qty_state='empty_string',qty=None,source_row=1)]
        a,b=self.r.vector_math(long,8),self.r.vector_math(short,8)
        self.assertEqual((a['named_count'],b['named_count'],b['empty_slots']),(2,1,1))
        self.assertAlmostEqual(a['H']-b['H'],-.375)
        self.assertTrue(a['available'] and b['available'])

    def test_missing_999_keeps_diagnostic_H_but_primary_unknown(self):
        rows=[dict(rank=1,id='A',name='a',qty_state='true_zero',qty=0,source_row=0),dict(rank=2,id='B',name='b',qty_state='finite_integer',qty=4,source_row=1)]
        got=self.r.vector_math(rows,None)
        self.assertEqual((got['sum'],got['true_zero']), (4,1))
        self.assertEqual(got['H'],1.)
        self.assertFalse(got['available'])
        self.assertFalse(self.r.vector_math([rows[0]],0)['available'])

    def test_duplicate_identity_or_rank_and_999_mismatch_block_primary(self):
        a=dict(rank=1,id='A',name='a',qty_state='finite_integer',qty=2,source_row=0)
        for other in (dict(a,rank=2,source_row=1),dict(a,id='B',name='b',source_row=1)):
            self.assertFalse(self.r.vector_math([a,other],4)['available'])
        self.assertFalse(self.r.vector_math([a],99)['available'])

    def test_exact_epoch_mapping_uses_directory_owner_not_SHFE_prefix(self):
        directory=['INE.SC.202611','SHFE.RB.202611','SHFE.RB.201611']
        self.assertEqual(self.r.epoch_candidates('sc2611',directory),['INE.SC.202611'])
        self.assertEqual(self.r.epoch_candidates('rb1611',directory),['SHFE.RB.201611'])
        self.assertEqual(self.r.epoch_candidates('rball',directory),[])
        self.assertEqual(self.r.epoch_candidates('sc2611',['INE.SC.202611','INE.SC.212611']),['INE.SC.202611','INE.SC.212611'])
        self.assertEqual(self.r.epoch_candidates('l2301F',['DCE.L.202301','DCE.L_F.202301']),['DCE.L_F.202301'])

    def test_previous_source_session_is_exact_no_ffill_and_no_mother_drop(self):
        calendar=['2020-01-02','2020-01-03','2020-01-06']
        self.assertEqual(self.r.previous_day('2020-01-06',calendar),'20200103')
        self.assertIsNone(self.r.previous_day('2020-01-02',calendar))
        with self.assertRaises(AssertionError):self.r.previous_day('2020-01-05',calendar)
        self.assertEqual(self.r.lookup_projection('2020-01-06','INE.SC.202611',calendar,{('20200102','INE.SC.202611'):{'scope_id':'older','available':True,'q':.2}})['observed'],0)
        self.assertEqual(self.r.lookup_projection('2020-01-06','',calendar,{})['reason'],'no_reference_epoch')

    def test_ID_only_is_identity_and_unidentified_true_zero_is_not_a_seat(self):
        a=dict(rank=1,id='A',name='',qty_state='finite_integer',qty=4,source_row=0)
        b=dict(rank=2,id='B',name='',qty_state='finite_integer',qty=4,source_row=1)
        zero=dict(rank=3,id='',name='',qty_state='true_zero',qty=0,source_row=2)
        got=self.r.vector_math([a,b,zero],8)
        self.assertTrue(got['available'])
        self.assertEqual((got['named_count'],got['true_zero'],got['H']),(2,0,.5))

    def test_quantity_representation_is_strict_without_value_repair(self):
        self.assertEqual(self.r.quantity('12.00'),('finite_integer',12))
        self.assertEqual(self.r.quantity(12.0),('finite_integer',12))
        self.assertIsNone(self.r.quantity('1e3')[1])
        self.assertIsNone(self.r.quantity('1,000')[1])
        self.assertIsNone(self.r.quantity(True)[1])

    def test_large_integer_quantities_are_checked_exactly(self):
        with self.assertRaises(AssertionError):self.r.fields({'sumsq':str(2**60+1)},{'sumsq':2**60},'exact quantity')

    def test_new_HTTP_and_reused_bytes_have_different_denominators(self):
        records=[dict(status='http_200',raw_body_bytes=10),dict(status='reused_stage104_106',raw_body_bytes=3),dict(status='network_error')]
        self.assertEqual(self.r.source_byte_accounting(records,10,13),dict(new_original_bytes=10,reused_original_bytes=3,all_consumed_bytes=13))
        with self.assertRaises(AssertionError):self.r.source_byte_accounting(records,10,10)


if __name__=='__main__':unittest.main()
