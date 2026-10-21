import unittest
import stage048_asof_features_revalidated as role


class DomainIdentityTests(unittest.TestCase):
    def setUp(self):self.assertTrue(callable(getattr(role,'classify_domain_role',None)),'missing normalized domain role API')

    def test_lowercase_official_product_matches_uppercase_panel(self):
        self.assertEqual(role.classify_domain_role('AU.SHFE',False,['au.SHFE','MA.CZCE']),'old18')
        self.assertEqual(role.classify_domain_role('MA.CZCE',False,['au.SHFE','MA.CZCE']),'old18')

    def test_fixed_fu_case_normalized_and_never_competitive(self):
        for key in ['fu.SHFE','FU.SHFE','Fu.SHFE']:
            self.assertEqual(role.classify_domain_role(key,False,[]),'fixed_fu')

    def test_monthly_average_and_expanded_roles(self):
        self.assertEqual(role.classify_domain_role('L_F.DCE',True,['l.DCE']),'monthly_average_F')
        self.assertEqual(role.classify_domain_role('A.DCE',False,['au.SHFE']),'expanded')

    def test_bad_marker_or_product_identity_rejected(self):
        for key,marker in [('L_F.DCE',False),('L.DCE',True),('',False),('AU',False),('AU.BAD',False)]:
            with self.subTest(key=key),self.assertRaises(ValueError):role.classify_domain_role(key,marker,[])

if __name__=='__main__':unittest.main()
