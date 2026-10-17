"""Narrow frozen-source adapter gates; no strategy or market download."""
import importlib.util
from pathlib import Path
import tempfile
import unittest


class Recap253Tests(unittest.TestCase):
    def adapter(self):
        path=Path(__file__).with_name('stage253_recap.py')
        self.assertTrue(path.is_file(),'Stage253 adapter must exist')
        spec=importlib.util.spec_from_file_location('recap253',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module

    def test_incomplete_bundle_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError,'Incomplete frozen bundle'):
                self.adapter().require_bundle(Path(directory))

    def test_completed_cycles_use_trading_dates_and_exclude_residual(self):
        m=self.adapter();source=m.load_source('ai_no_half_r')
        episodes=m.episode_rows(source['cycles'],source['trades'])
        self.assertEqual(len(episodes),316)
        self.assertEqual(len(source['residual']),1)
        first=episodes.loc[episodes.open_trade_id.eq('BACKTESTING.1')].iloc[0]
        self.assertEqual(str(first.entry_date.date()),'2020-01-09')
        self.assertNotIn('BACKTESTING.646',set(episodes.open_trade_id))
        self.assertEqual(set(episodes.open_trade_id),set(source['cycles'].first_trade_id))

    def test_diagnostic_source_remains_diagnostic_and_output_isolated(self):
        m=self.adapter();source=m.load_source('no_ai_no_half_r')
        self.assertTrue(source['diagnostic'])
        self.assertEqual(len(source['residual']),3)
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory)
            with self.assertRaises(ValueError):m.validate_output(base/'..'/'escape',base)
            target=base/'existing';target.mkdir()
            with self.assertRaises(FileExistsError):m.validate_output(target,base)


if __name__=='__main__':unittest.main()
