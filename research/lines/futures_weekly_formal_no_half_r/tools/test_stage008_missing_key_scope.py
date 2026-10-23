"""Synthetic data-only scope tests; no financial replay or source files changed."""
import unittest
import pandas as pd
from pandas.testing import assert_frame_equal
try:
    from stage008_missing_key_scope import merge_missing_key_scope, audit_scope_consumption
except ImportError:
    merge_missing_key_scope = None
    audit_scope_consumption = None
from stage008_execution_audit import audit_actual_minute_volumes

VALUES=['open','high','low','close','volume','open_oi','close_oi']
STAMP=pd.Timestamp('2020-01-02 09:00:00')
def frame(volume=0.,stamp=STAMP,source='legacy',price=100.):
    return pd.DataFrame([dict(vt_symbol='CF005.CZCE',bar_datetime=stamp,bar_date=stamp.normalize(),
        open=price,high=price+1,low=price-1,close=price,volume=volume,open_oi=100.,close_oi=101.,source=source)])

class MissingKeyScopeTests(unittest.TestCase):
    def api(self):self.assertIsNotNone(merge_missing_key_scope,'missing-key scope API missing')
    def test_legacy_zero_volume_cannot_be_replaced_by_positive_patch(self):
        self.api();legacy=frame();new=frame(60.,source='completed')
        merged,scope=merge_missing_key_scope(legacy,[new],VALUES,set())
        self.assertEqual(merged.volume.tolist(),[0.]);self.assertEqual(merged.source.tolist(),['legacy'])
        self.assertEqual(scope['excluded_existing_count'],1);self.assertEqual(scope['conflicting_existing_count'],1)
        detail=scope['excluded_existing_keys'][0]
        self.assertEqual(detail['conflicting_fields'],{'volume':{'old':0.,'new':60.}})
        self.assertEqual(detail['old']['volume'],0.);self.assertEqual(detail['new']['volume'],60.)
    def test_legacy_positive_volume_and_price_cannot_be_replaced(self):
        self.api();merged,scope=merge_missing_key_scope(frame(40.),[frame(90.,price=102.)],VALUES,set())
        self.assertEqual(merged.volume.tolist(),[40.]);self.assertEqual(merged.open.tolist(),[100.])
        self.assertEqual(set(scope['conflicting_existing_keys'][0]['conflicting_fields']),{'open','high','low','close','volume'})
    def test_kept_zero_volume_still_fails_actual_fill_acceptance(self):
        self.api();merged,_=merge_missing_key_scope(frame(),[frame(60.)],VALUES,set())
        trade=dict(trade_id='T1',vt_symbol='CF005.CZCE',execution_datetime=str(STAMP),price=100.,volume=1.)
        audit=audit_actual_minute_volumes([trade],{'CF005.CZCE':merged})
        self.assertFalse(audit['accepted']);self.assertEqual(audit['verdict'],'REJECT_EXECUTION_ZERO_VOLUME')
        self.assertEqual(audit['zero_or_invalid_volume_count'],1)
    def test_equal_overlap_is_always_excluded_and_keeps_original_metadata(self):
        self.api();merged,scope=merge_missing_key_scope(frame(40.),[frame(40.,source='new')],VALUES,{('CF005.CZCE',STAMP)})
        self.assertEqual(merged.source.tolist(),['legacy']);self.assertEqual(scope['added_count'],0)
        self.assertEqual(scope['excluded_existing_count'],1);self.assertEqual(scope['conflicting_existing_count'],0)
        self.assertTrue(scope['excluded_existing_keys'][0]['requested_key'])
    def test_new_new_conflict_rejected_even_when_legacy_would_exclude_key(self):
        self.api()
        with self.assertRaisesRegex(ValueError,'completed_minute_source_overlap_conflict'):
            merge_missing_key_scope(frame(),[frame(10.),frame(20.)],VALUES,set())
    def test_new_new_conflict_on_new_key_also_rejected(self):
        self.api()
        with self.assertRaisesRegex(ValueError,'completed_minute_source_overlap_conflict'):
            merge_missing_key_scope(frame().iloc[:0],[frame(10.),frame(20.)],VALUES,set())
    def test_requested_conflict_raises_with_complete_report_and_no_mutation(self):
        self.api();legacy=frame();original=legacy.copy(deep=True)
        with self.assertRaisesRegex(ValueError,'requested_key_overlap_conflict') as caught:
            merge_missing_key_scope(legacy,[pd.concat([frame(60.),frame(80.,STAMP+pd.Timedelta(minutes=1))])],VALUES,{('CF005.CZCE',STAMP)})
        scope=caught.exception.scope_report
        self.assertEqual(scope['requested_conflicting_count'],1);self.assertEqual(scope['excluded_existing_count'],1)
        self.assertEqual(scope['added_count'],1);self.assertEqual(scope['status'],'REJECT_REQUESTED_KEY_CONFLICT')
        self.assertEqual(scope['conflicting_existing_keys'][0]['new']['volume'],60.)
        assert_frame_equal(legacy,original)
    def test_additions_preserve_original_values_and_nonvalue_metadata(self):
        self.api();legacy=frame();new=frame(123.5,STAMP+pd.Timedelta(minutes=1),'raw_completed',101.25)
        merged,scope=merge_missing_key_scope(legacy,[new],VALUES,{('CF005.CZCE',STAMP+pd.Timedelta(minutes=1))})
        self.assertEqual(merged.volume.tolist(),[0.,123.5]);self.assertEqual(merged.source.tolist(),['legacy','raw_completed'])
        self.assertEqual(merged.open.tolist(),[100.,101.25]);self.assertEqual(scope['added_count'],1)
        self.assertEqual(scope['added_keys'][0]['bar_datetime'],'2020-01-02T09:01:00')
        assert_frame_equal(new,frame(123.5,STAMP+pd.Timedelta(minutes=1),'raw_completed',101.25))
    def test_new_equal_duplicates_use_old_strict_rule_then_one_addition(self):
        self.api();new=frame(50.,STAMP+pd.Timedelta(minutes=1),'first')
        second=new.copy();second['source']='second'
        merged,scope=merge_missing_key_scope(frame(),[new,second],VALUES,set())
        self.assertEqual(len(merged),2);self.assertEqual(merged.source.tolist(),['legacy','first'])
        self.assertEqual(scope['new_input_rows'],2);self.assertEqual(scope['new_unique_count'],1)
    def test_duplicate_in_single_patch_rejected_not_silently_deduplicated(self):
        self.api()
        with self.assertRaisesRegex(ValueError,'patch_duplicate_minute'):
            merge_missing_key_scope(frame(),[pd.concat([frame(50.),frame(50.)])],VALUES,set())
    def test_empty_new_layers_preserve_legacy_without_mutation(self):
        self.api();legacy=frame();merged,scope=merge_missing_key_scope(legacy,[],VALUES,set())
        assert_frame_equal(merged,legacy);self.assertEqual(scope['added_count'],0)
        self.assertEqual(scope['excluded_existing_keys'],[])

class ScopeConsumptionTests(unittest.TestCase):
    def conflict(self):
        self.assertIsNotNone(merge_missing_key_scope,'missing-key scope API missing')
        _,scope=merge_missing_key_scope(frame(40.),[frame(90.)],VALUES,set())
        return scope
    def test_positive_old_volume_conflicted_actual_fill_is_rejected(self):
        scope=self.conflict()
        result=audit_scope_consumption([dict(trade_id='T1',vt_symbol='CF005.CZCE',execution_datetime='2020-01-02T01:00:00Z')],[],scope)
        self.assertFalse(result['accepted']);self.assertEqual(result['verdict'],'REJECT_EXECUTION_ANCHOR_MISMATCH')
        self.assertEqual(len(result['hits']),1);self.assertEqual(result['hits'][0]['origin'],'trade')
    def test_actual_anchor_request_without_trade_is_rejected(self):
        scope=self.conflict()
        result=audit_scope_consumption([],[dict(vt_symbol='CF005.CZCE',actual_time=str(STAMP),expected_start='2020-01-02 09:01:00')],scope)
        self.assertFalse(result['accepted']);self.assertEqual(result['hits'][0]['field'],'actual_time')
    def test_expected_anchor_request_checked_even_when_actual_is_different(self):
        scope=self.conflict()
        result=audit_scope_consumption([],[dict(vt_symbol='CF005.CZCE',actual_time='2020-01-02 09:01:00',expected_start='2020-01-02T09:00:00+08:00')],scope)
        self.assertFalse(result['accepted']);self.assertEqual(result['hits'][0]['field'],'expected_start')
    def test_other_keys_and_equal_excluded_keys_are_not_conflict_consumption(self):
        scope=self.conflict()
        result=audit_scope_consumption([dict(vt_symbol='CF005.CZCE',execution_datetime='2020-01-02 09:01:00')],[],scope)
        self.assertTrue(result['accepted']);self.assertEqual(result['verdict'],'PASS_NO_CONFLICTED_ANCHOR_CONSUMED');self.assertEqual(result['hits'],[])
        _,equal=merge_missing_key_scope(frame(40.),[frame(40.)],VALUES,set())
        result=audit_scope_consumption([dict(vt_symbol='CF005.CZCE',execution_datetime=str(STAMP))],[],equal)
        self.assertTrue(result['accepted'])

if __name__=='__main__':unittest.main()
