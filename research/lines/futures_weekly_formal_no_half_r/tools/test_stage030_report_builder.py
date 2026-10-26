"""Synthetic Stage030 publication/contract tests; never invoke a financial engine."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd
import stage029_build_artifacts as old
import test_stage029_report_builder as old_test

PATH = Path(__file__).with_name('stage030_build_artifacts.py')


class Stage030ReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not PATH.exists():
            raise AssertionError('Stage030 three-arm readonly report implementation is missing')
        spec = importlib.util.spec_from_file_location('stage030_report', PATH)
        cls.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.m)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root/'daily.sqlite'
        self.db.write_bytes(b'synthetic immutable identity; no market prices')
        self.source_files={}
        for name in ['stage030_profit5_half.py','test_stage030_profit5_half.py']:
            source=self.root/name;source.write_text('# synthetic source identity\n')
            self.source_files[str(source)]=old.sha(source)
        self.arms = {k:self.root/k for k in ['baseline', 'daily', 'weekly']}
        fixture = old_test.ReportTests();fixture.m = old
        for role, path in self.arms.items():
            fixture.write_empty_ledger(path, True, self.db)
            self.change(path/'preflight.json', lambda x:x.update(end='2026-10-26'))
            self.change(path/'historical_safety_acceptance.json', lambda x:x.update(requested_end='2026-10-26'))
            for name in ['daily.csv', 'positions.csv']:
                frame = pd.read_csv(path/name)
                frame.loc[frame.date.eq('2026-10-23'), 'date'] = '2026-10-26'
                frame.to_csv(path/name, index=False)
            if role != 'baseline':
                (path/'actual_profit_half_configuration.json').write_text(json.dumps(self.configuration(role)))
                self.change(path/'input_manifest.json', lambda x:x.update(self.source_files))
                (path/'profit_half_acceptance.json').write_text(json.dumps(self.proof(role)))
        self.baseline_pin = self.m.snapshot_identity(old.snapshot_dir(self.arms['baseline']), self.arms['baseline'])

    @staticmethod
    def change(path, mutation):
        value = json.loads(path.read_text());mutation(value);path.write_text(json.dumps(value))

    def configuration(self, frequency):
        return {'research_profit_half_enabled':True, 'research_profit_half_frequency':frequency,
            'research_profit_half_threshold':.05, 'research_profit_half_ratio':.5}

    def proof(self, frequency):
        return dict(schema='stage030_profit_half_acceptance_v1', accepted=True,
            frequency=frequency, threshold=.05, exit_ratio=.5, threshold_comparison='strict_gt',
            profit_basis='actual_synced_native_contract_weighted_entry_price',
            quantity_rule='floor_half_keep_at_least_one', once_per_native_contract_round=True,
            technical_exits_frequency='weekly', execution_model=old.EXECUTION_MODEL,
            trigger_count=0, executed_trigger_count=0, terminal_pending_trigger_count=0,
            one_lot_skipped_count=1, invariant_failures=[], source_files_sha256=self.source_files.copy())

    def build(self, out=None, figure=None):
        out = out or self.root/'report';figure = figure or out/'figure.png'
        with patch.object(self.m, 'BASELINE_SNAPSHOT_SHA256', self.baseline_pin):
            return self.m.build_artifacts(*self.arms.values(), out, figure)

    def test_three_arms_publish_hashes_without_changing_inputs(self):
        # A dropped arm, accidental input write or unhashed artifact breaks this.
        before = {k:old.snapshot_dir(v) for k,v in self.arms.items()}
        result = self.build()
        self.assertEqual(result['financial_replays'], 0)
        out = self.root/'report'
        summary = json.loads((out/'comparison.json').read_text())
        self.assertEqual(set(summary['arms']), {'baseline','daily','weekly'})
        self.assertEqual(summary['contract']['technical_exits_frequency'], 'weekly')
        self.assertEqual(summary['status'], 'DERIVED_PENDING_INDEPENDENT_REVIEW')
        self.assertEqual(summary['contract']['actual_margin_multiplier'], 1.65)
        self.assertEqual(summary['arms']['daily']['profit_half']['one_lot_skipped_count'], 1)
        self.assertEqual(len(pd.read_csv(out/'summary.csv')), 3)
        self.assertEqual(len(pd.read_csv(out/'products.csv')), 57)
        self.assertEqual(len(pd.read_csv(out/'slices_2015_2019_2020.csv')), 6)
        for role in self.arms:
            self.assertTrue((out/(role+'_daily.csv')).is_file())
        manifest = json.loads((out/'delivery_manifest.json').read_text())
        old.verify_sources(manifest['files_sha256'])
        old.verify_sources(summary['source_files_sha256'])
        self.assertIn(str(PATH.with_name('test_stage030_report_builder.py').resolve()), summary['source_files_sha256'])
        self.assertIn(str(PATH.with_name('stage029_build_artifacts.py').resolve()), summary['source_files_sha256'])
        self.assertEqual(before, {k:old.snapshot_dir(v) for k,v in self.arms.items()})
        self.assertGreater((out/'figure.png').stat().st_size, 1000)
        with self.assertRaises(FileExistsError):
            self.build()

    def test_cli_has_three_explicit_source_directories(self):
        result = subprocess.run([sys.executable, str(PATH), '--help'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        for flag in ['--baseline-dir', '--daily-dir', '--weekly-dir', '--out-dir', '--figure']:
            self.assertIn(flag, result.stdout)

    def test_swapped_frequency_and_unaccepted_or_missing_proof_fail_closed(self):
        for change in [lambda x:x.update(frequency='weekly'), lambda x:x.update(accepted=False), lambda x:x.pop('schema')]:
            proof = self.proof('daily');change(proof)
            (self.arms['daily']/'profit_half_acceptance.json').write_text(json.dumps(proof))
            with self.assertRaisesRegex(ValueError, 'profit_half'):
                self.build()
        (self.arms['daily']/'profit_half_acceptance.json').unlink()
        with self.assertRaisesRegex(ValueError, 'profit_half'):
            self.build()

    def test_threshold_ratio_once_cost_and_quantity_contract_are_fixed(self):
        # Treating 5% as >=, margin return, repeatable exits or one-lot closure must reject.
        changes = dict(threshold=.051, exit_ratio=.6, threshold_comparison='gte',
            profit_basis='margin_return', quantity_rule='ceil_half', once_per_native_contract_round=False,
            technical_exits_frequency='daily', execution_model='same_close')
        for key, value in changes.items():
            with self.subTest(key=key):
                proof = self.proof('daily');proof[key]=value
                (self.arms['daily']/'profit_half_acceptance.json').write_text(json.dumps(proof))
                with self.assertRaisesRegex(ValueError, 'profit_half'):
                    self.build(out=self.root/('report_'+key))

    def test_configuration_requires_exact_keys_and_values(self):
        path=self.arms['daily']/'actual_profit_half_configuration.json'
        for changes in [dict(research_profit_half_frequency='weekly'),dict(research_profit_half_ratio=.6),dict(unadvertised=True)]:
            value=self.configuration('daily');value.update(changes);path.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError,'profit_half_configuration'):
                self.build()

    def test_trigger_count_is_not_fill_count_and_terminal_pending_is_accounted(self):
        proof = self.proof('daily');proof.update(trigger_count=2, executed_trigger_count=1, terminal_pending_trigger_count=1)
        (self.arms['daily']/'profit_half_acceptance.json').write_text(json.dumps(proof))
        ledger = old.load_ledger(self.arms['daily'], 'candidate')
        self.m.validate_profit_acceptance(ledger, 'daily')
        for bad in [dict(trigger_count=3), dict(one_lot_skipped_count=-1), dict(executed_trigger_count=True), dict(invariant_failures=['future_week'])]:
            with self.subTest(bad=bad):
                x=deepcopy(ledger);x['acceptances']['profit_half_acceptance.json'].update(bad)
                with self.assertRaisesRegex(ValueError, 'profit_half'):
                    self.m.validate_profit_acceptance(x, 'daily')

    def test_proof_source_hash_mismatch_and_empty_source_binding_reject(self):
        wrong=self.source_files.copy();wrong[next(iter(wrong))]='0'*64
        for sources in [{}, wrong]:
            proof=self.proof('daily');proof['source_files_sha256']=sources
            (self.arms['daily']/'profit_half_acceptance.json').write_text(json.dumps(proof))
            with self.assertRaisesRegex(ValueError, 'source|profit_half'):
                self.build()

    def test_declared_source_bytes_must_still_match_the_replay_manifest(self):
        source=Path(next(iter(self.source_files)))
        source.write_text('# changed after replay\n')
        with self.assertRaisesRegex(ValueError,'immutable_source_changed'):
            self.build()

    def test_baseline_must_be_exact_frozen_R003_and_no_profit_flag(self):
        (self.arms['baseline']/'unadvertised.txt').write_text('a changed frozen baseline')
        with self.assertRaisesRegex(ValueError, 'frozen_R003'):
            self.build()
        (self.arms['baseline']/'unadvertised.txt').unlink()
        (self.arms['baseline']/'actual_profit_half_configuration.json').write_text(json.dumps(self.configuration('daily')))
        self.baseline_pin=self.m.snapshot_identity(old.snapshot_dir(self.arms['baseline']), self.arms['baseline'])
        with self.assertRaisesRegex(ValueError, 'baseline_profit_half'):
            self.build()

    def test_existing_flags_new_unknown_marker_and_effective_parameters_cannot_differ(self):
        path=self.arms['daily']/'actual_strategy_settings.json'
        original=path.read_text()
        for group,key,value in [('actual','enable_rsi_partial_exit',True),('setting','ma_short',6),('actual','research_unadvertised',True),('actual','research_profit_half_threshold',.06)]:
            with self.subTest(key=key):
                path.write_text(original);self.change(path,lambda x:x[0][group].update({key:value}))
                with self.assertRaisesRegex(ValueError,'RSI|setting|marker|profit_half|weekly_MA'):
                    self.build()
        path.write_text(original)
        self.change(self.arms['daily']/'effective_parameters.json',lambda x:x['spec'].update(profile='changed'))
        with self.assertRaisesRegex(ValueError,'effective_parameters'):
            self.build()

    def test_window_calendar_and_database_snapshot_must_match(self):
        path=self.arms['daily']/'daily.csv';d=pd.read_csv(path);d.loc[1,'date']='2019-12-30';d.to_csv(path,index=False)
        with self.assertRaisesRegex(ValueError,'calendar'):
            self.build()
        d.loc[1,'date']='2019-12-31';d.to_csv(path,index=False)
        other=self.root/'other.sqlite';other.write_bytes(b'another snapshot')
        self.change(self.arms['daily']/'actual_database_binding.json',lambda x:x.update(expected=str(other),database_list=[[0,'main',str(other)]]))
        with self.assertRaisesRegex(ValueError,'database_snapshot'):
            self.build()

    def test_closed_accounting_keeps_partial_realized_and_terminal_inventory_separate(self):
        fixture=old_test.ReportTests();fixture.m=old
        trades,clock,effective=fixture.fixture()
        fills=self.m.ordered_fills(trades,clock)
        segments,rounds,opened,stats=self.m.inventory_accounting(fills,effective,{'au2006.SHFE':14.})
        self.assertEqual(segments.net_pnl.tolist(),[18.,-22.,28.])
        self.assertEqual(rounds.net_pnl.tolist(),[-4.])
        self.assertEqual(opened.iloc[0]['partial_closed_net_pnl'],28.)
        self.assertEqual(opened.iloc[0]['remaining_open_net_mtm'],39.)
        self.assertEqual(stats['ledger_net_pnl'],63.)
        with self.assertRaisesRegex(ValueError,'unmatched_close'):
            self.m.inventory_accounting(fills.iloc[1:],effective,{})

    def test_daily_accounting_and_causality_gates_remain_active(self):
        path=self.arms['daily']/'daily.csv';frame=pd.read_csv(path);frame.loc[0,'account_equity']=149999.;frame.to_csv(path,index=False)
        with self.assertRaisesRegex(ValueError,'daily_equity_conservation'):
            self.build()
        frame.loc[0,'account_equity']=150000.;frame.to_csv(path,index=False)
        self.change(self.arms['daily']/'historical_safety_acceptance.json',lambda x:x.update(strict_next_trading_day_open=False))
        with self.assertRaisesRegex(ValueError,'historical_safety'):
            self.build()

    def test_report_risk_uses_actual_1p65_margin_instead_of_legacy_1p1(self):
        # 100000 raw margin / 150000 equity * 1.65 = 110%, on all four days.
        path=self.arms['daily']/'daily.csv';frame=pd.read_csv(path)
        frame['total_margin_exact']=100000.;frame['broker10_total_margin_exact']=110000.
        frame.to_csv(path,index=False);self.build()
        summary=json.loads((self.root/'report'/'comparison.json').read_text())
        risk=summary['arms']['daily']['risk']
        self.assertAlmostEqual(risk['actual_margin_to_equity_max_pct'],110.)
        self.assertEqual(risk['actual_margin_over100_days'],4)

    def test_atomic_publication_cannot_replace_existing_empty_directory(self):
        source=self.root/'prepared';source.mkdir();(source/'receipt').write_text('preserve source')
        target=self.root/'already-exists';target.mkdir()
        with self.assertRaises(FileExistsError):
            self.m.rename_exclusive(source,target)
        self.assertEqual((source/'receipt').read_text(),'preserve source')
        self.assertEqual(list(target.iterdir()),[])
        target.rmdir();self.m.rename_exclusive(source,target)
        self.assertFalse(source.exists())
        self.assertEqual((target/'receipt').read_text(),'preserve source')

    def test_output_cannot_be_in_input_or_replace_existing_external_figure(self):
        with self.assertRaisesRegex(ValueError,'inside_input'):
            self.build(self.arms['weekly']/'report')
        fig=self.root/'existing.png';fig.write_bytes(b'preserve')
        with self.assertRaises(FileExistsError):
            self.build(figure=fig)
        self.assertEqual(fig.read_bytes(),b'preserve')
        with self.assertRaisesRegex(ValueError,'distinct'):
            self.m.build_artifacts(self.arms['baseline'],self.arms['daily'],self.arms['daily'],self.root/'x',self.root/'x.png')


if __name__ == '__main__':
    unittest.main()
