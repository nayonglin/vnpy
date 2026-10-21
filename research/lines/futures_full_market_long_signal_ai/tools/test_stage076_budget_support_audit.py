"""Only synthetic boundaries; never opens the accepted reservation ledger."""
import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).with_name('stage076_budget_support_audit.py')
spec = importlib.util.spec_from_file_location('stage076', SCRIPT)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def row(event='a', **changes):
    result = dict(budget_id=event, event_id=event, budget_kind='new_entry',
                  account_id='synthetic', scenario='stress', product_id=event,
                  family_id=event, u_date='2021-01-04', u_index='1',
                  cutoff='2020-01-01', score='1', potential='1',
                  label_history_ready20='1', u_equity='100000',
                  existing_risk='0', existing_buffered_margin='0',
                  unit_risk_u='100', unit_margin_u='1000', unit_fee_reserve_u='2',
                  target_qty_unscaled='2.5', joint_scale='1',
                  target_qty_prefloor='2.5', qty_cap='2', round_lot='1',
                  allocated_risk='250', allocated_buffered_margin='2500',
                  allocated_fee='5', budget_state='reserved')
    result.update(changes)
    return result


class SupportBoundaries(unittest.TestCase):
    # A bad individual-cap relaxation would incorrectly find a one-lot action.
    def test_individual_one_lot_unreachable(self):
        result = audit.audit_rows([row(unit_risk_u='300', qty_cap='0',
                                      target_qty_unscaled='.833333333',
                                      target_qty_prefloor='.833333333')])
        self.assertEqual(result['u_summary'][0]['decision'], 'no_positive_quantity_support')
        self.assertTrue(result['candidate_bounds'][0]['individual_one_lot_unreachable'])
        self.assertEqual(result['candidate_bounds'][0]['upper_qty'], 0)

    # A missing direct-add branch or wrong lot increment changes this witness.
    def test_direct_slack_and_nonproposal_identity(self):
        reduction = row('z', budget_kind='existing_position_reduction', qty_cap='7')
        result = audit.audit_rows([row(qty_cap='1', joint_scale='.5'), reduction])
        proof = result['certificates'][0]
        self.assertEqual(proof['kind'], 'direct_add')
        self.assertEqual([r['quantity'] for r in proof['original_vector']], [1, 7])
        self.assertEqual([r['quantity'] for r in proof['alternative_vector']], [2, 7])
        self.assertEqual(proof['alternative_proof']['total_risk'], '200')
        self.assertEqual(result['u_summary'][0]['rounding_direct_slack'], True)

    # Dropping all but one donor or ranking by score loses this deterministic witness.
    def test_competition_can_discard_all_other_new_orders(self):
        rows = [row('b', unit_risk_u='80', existing_risk='1680', qty_cap='2',
                    joint_scale='.64', score='999'),
                row('a', unit_risk_u='80', existing_risk='1680', qty_cap='2',
                    joint_scale='.64', score='.1')]
        result = audit.audit_rows(rows)
        proof = result['certificates'][0]
        self.assertEqual(proof['kind'], 'competition_reallocation')
        self.assertEqual(proof['increased_budget_id'], 'a')
        self.assertEqual([r['quantity'] for r in proof['alternative_vector']], [0, 3])
        self.assertEqual(proof['alternative_proof']['total_risk'], '240')
        self.assertTrue(result['u_summary'][0]['at_least_two_tradable_competition'])

    # Confusing inability to increase with inability to derisk overclaims the result.
    def test_no_increase_keeps_derisk_scope_and_decimal_boundary_unknown(self):
        result = audit.audit_rows([row(unit_risk_u='125', qty_cap='2')])
        self.assertEqual(result['u_summary'][0]['decision'], 'no_positive_quantity_support')
        self.assertTrue(result['u_summary'][0]['derisk_actions_remain_possible'])
        boundary = audit.audit_rows([row(unit_risk_u='125.00000000000001', qty_cap='2')])
        self.assertEqual(boundary['u_summary'][0]['decision'], 'unknown')
        self.assertIsNone(boundary['certificates'][0]['alternative_vector'])

    # Future execution/final outcomes must never affect membership, order or quantity.
    def test_future_columns_are_inert_and_wrong_cutoff_is_unknown(self):
        rows = [row(qty_cap='1')]
        changed = copy.deepcopy(rows)
        changed[0].update(D_qty='999999', D_state='closed', PnL='-99999',
                          execution_date='1900-01-01', exit='bad', closed='1')
        self.assertEqual(audit.audit_rows(rows), audit.audit_rows(changed))
        self.assertEqual(audit.audit_rows([row(cutoff='2019-01-01')])['u_summary'][0]['decision'], 'unknown')

    # The public callable, as well as CLI, must reject before protocol/source I/O.
    def test_wrong_authorization_does_not_read_protocol_or_create_output(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'fresh'
            original_read = Path.read_bytes
            def guarded_read(path):
                if path.resolve() != SCRIPT.resolve():
                    raise AssertionError('unauthorized input read')
                return original_read(path)
            with patch.object(Path, 'read_bytes', guarded_read):
                with self.assertRaises(audit.AuthorizationError):
                    audit.run_actual(Path(temp) / 'protocol.json', audit.FROZEN_PROTOCOL_SHA,
                                     '0' * 64, output)
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
