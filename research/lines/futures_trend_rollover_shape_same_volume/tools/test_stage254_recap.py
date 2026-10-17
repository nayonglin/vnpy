"""Narrow checks for Stage254 frozen recap, including retry and no-residual cases."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
import pandas as pd

class Recap254Tests(unittest.TestCase):
    def adapter(self):
        path=Path(__file__).with_name('stage254_recap.py')
        self.assertTrue(path.exists(),'Stage254 recap adapter missing')
        spec=importlib.util.spec_from_file_location('recap254',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module

    def test_missing_frozen_bundle_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError,'Incomplete frozen bundle'):
                self.adapter().require_bundle(Path(directory))

    def test_retry_cycles_remain_visible_with_root_identity(self):
        m=self.adapter();run=m.LINE/'outputs/stage251_half_r_ab/A_final3'
        cycles=pd.read_csv(run/'statistics_audit/complete_cycles.csv')
        trades=pd.read_csv(run/'trades.csv').set_index('trade_id')
        records=m.cycle_rows(cycles,trades)
        self.assertEqual(len(records),len(cycles))
        expected=set(cycles.loc[cycles.is_retry,'first_trade_id'])
        observed=set(records.loc[records.is_retry,'open_trade_id'])
        self.assertEqual(expected,observed)
        self.assertTrue(expected)
        self.assertTrue(records.loc[records.is_retry,'selection_basis'].str.contains('0.5R重试').all())

    def test_empty_residual_file_does_not_fabricate_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'empty.csv';path.write_text('\n')
            residual=self.adapter().optional_table(path,['trade_ids','net_mtm'])
            self.assertTrue(residual.empty)
            self.assertEqual(float(residual.net_mtm.sum()),0.)

if __name__=='__main__':unittest.main()
