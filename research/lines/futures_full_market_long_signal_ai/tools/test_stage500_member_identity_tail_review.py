"""One display-metadata regression; synthetic only, no actual outputs."""
import importlib.util
from pathlib import Path
import unittest

TOOLS=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('tail_fixture500',TOOLS/'stage500_member_identity_tail_review.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


class TailIdentityMetadata(unittest.TestCase):
    def test_missing_A_summary_display_id_uses_exact_protocol_canonical_identity(self):
        original_summary={'ending_equity':1000000.}  # Deliberately no account_id.
        controls=[dict(window=w,cost=c,account_id='NARROW_VOLUNTARY_RESELECT_'+w+'_'+c,
            directory='/synthetic/stage157_voluntary_cash/'+w+'_'+c) for w in m.v.WINDOWS for c in m.v.COSTS]
        p=dict(cash_contract_inherited_exact=dict(control_accounts_reused=controls))
        ids=m.canonical_ids(p)
        self.assertNotIn('account_id',original_summary)
        self.assertEqual(ids['A','primary_2020','stress'],'NARROW_VOLUNTARY_RESELECT_primary_2020_stress')
        self.assertEqual(len(ids),12)
        p['cash_contract_inherited_exact']['control_accounts_reused'][0]['account_id']='NARROW_B_primary_2020_base'
        with self.assertRaises(AssertionError):m.canonical_ids(p)


if __name__=='__main__':unittest.main()
