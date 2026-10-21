"""One independent projection-clock counterexample; no actual source reads."""
import unittest
try:
    import stage187_registration_projection_review as review
except ModuleNotFoundError:
    review = None


class ProjectionReviewTests(unittest.TestCase):
    def test_scalar_uses_two_reports_before_original_decision_not_entry(self):
        self.assertIsNotNone(review, 'projection reviewer is missing')
        calendar=['2020-01-01','2020-01-02','2020-01-03','2020-01-06','2020-01-07']
        scopes=[];statuses=[]
        for d,q in [('20200102','1'),('20200103','3')]:
            scopes.append(dict(request_date=d,scope_id='s',mapped_research_product_id='SHFE.CU',status='conditional_source_qualified',
                quantity_value=q,scope_identity={'raw':'same'},ordinary_total_count=1,leaf_coverage_fingerprint='coverage',coverage_state='complete_nonduplicated_source_rows'))
            statuses.append(dict(request_date=d,mapped_research_product_id='SHFE.CU',status='conditional_all_required_scopes_qualified',
                required_scope_ids=['s'],bad_scope_ids=[],scope_membership_complete=True,unresolved_report_scope_ids=[]))
        source=review.RegistrationEvidence(scopes,statuses,calendar)
        r=source.at('SHFE.CU','3','2020-01-06')
        self.assertEqual((r['report_v'],r['report_w'],r['prospective_entry_date']),('2020-01-03','2020-01-02','2020-01-07'))
        self.assertEqual(r['scalar_primary'],'0.5')
        self.assertEqual(r['scalar_missing'],0)


if __name__=='__main__': unittest.main()
