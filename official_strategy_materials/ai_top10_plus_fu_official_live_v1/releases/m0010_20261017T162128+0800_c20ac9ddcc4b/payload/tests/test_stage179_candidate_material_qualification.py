from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

PORTFOLIO_DIR = Path(__file__).resolve().parents[1] / 'examples/portfolio_backtesting'
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

import build_qmt_roll_stage179_production_qualification_bundle as qualifier
from build_qmt_roll_official_strategy_material_release import (
    ReleaseRequest, activate_release, commit_prepared_release, prepare_release,
)
from qmt_roll_official_live_release_manifest import ReleaseManifestError
from qmt_roll_strategy_material_discovery import MaterialDeclaration, discover_materials
from qmt_roll_strategy_material_manifest import MaterialRole


class CandidateMaterialQualificationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.repo = Path(self.directory.name).resolve()
        self.git('init')
        self.git('config', 'user.name', 'Qualification Test')
        self.git('config', 'user.email', 'qualification@example.invalid')
        self.runtime = self.repo / 'runtime.py'
        self.runtime.write_text('VERSION = 1\n')
        self.config = self.repo / 'examples/portfolio_backtesting/qmt_roll_official_live_config.py'
        self.config.parent.mkdir(parents=True)
        self.config.write_text('OFFICIAL_LIVE_RULESET_VERSION = "test_rules"\n')
        self.git('add', '.')
        self.git('commit', '-m', 'initial source')
        discovery = discover_materials(
            repo_root=self.repo, entrypoints=(), declared_paths=(), ai_artifacts=(),
            config_assets=(
                MaterialDeclaration(self.runtime, 'runtime.py', MaterialRole.RUNTIME_CODE),
                MaterialDeclaration(self.config, 'examples/portfolio_backtesting/qmt_roll_official_live_config.py', MaterialRole.STRATEGY_CONFIG),
            ),
        )
        request = ReleaseRequest(
            repo_root=self.repo, official_version='test_strategy', capital=150000,
            capital_label='15w', research_line='test',
            source_commit=self.git('rev-parse', 'HEAD'),
            created_at_utc='2026-10-17T00:00:00Z', created_at_cst='2026-10-17T08:00:00+08:00',
            discovery=discovery, provenance={}, qualification={'status':'candidate','evidence_ids':[]},
        )
        initial = prepare_release(request)
        initial_commit = commit_prepared_release(
            repo_root=self.repo, prepared=initial,
            confirmation=f'I_UNDERSTAND_THIS_COMMITS_OFFICIAL_STRATEGY_MATERIALS:{initial.release_id}',
        )
        activate_release(
            repo_root=self.repo, release_id=initial.release_id, release_commit=initial_commit,
            qualification={'status':'passed','release_commit':initial_commit,'evidence_ids':['fixture'], 'order_api_called_count':0,'cancel_order_api_called_count':0},
            confirmation=f'I_UNDERSTAND_THIS_ACTIVATES_OFFICIAL_STRATEGY_MATERIALS:{initial.release_id}',
        )
        self.runtime.write_text('VERSION = 2\n')
        self.git('add', 'runtime.py')
        self.git('commit', '-m', 'fix runtime')
        self.candidate = prepare_release(replace(request, source_commit=self.git('rev-parse', 'HEAD')))
        self.release_commit = commit_prepared_release(
            repo_root=self.repo, prepared=self.candidate,
            confirmation=f'I_UNDERSTAND_THIS_COMMITS_OFFICIAL_STRATEGY_MATERIALS:{self.candidate.release_id}',
        )

    def git(self, *args: str) -> str:
        return subprocess.run(['git', '-C', str(self.repo), *args], check=True, capture_output=True, text=True).stdout.strip()

    def resolve(self, **kwargs: object) -> tuple[str, ...]:
        return qualifier._resolve_qualification_critical_files(
            repo=self.repo, critical_files=('runtime.py',), **kwargs,
        )

    def test_default_still_rejects_active_material_drift(self) -> None:
        with self.assertRaisesRegex(ReleaseManifestError, 'active_material_release_invalid:active_runtime_material_drift'):
            self.resolve()

    def test_candidate_binds_exact_release_without_changing_current(self) -> None:
        current = self.repo / 'official_strategy_materials/CURRENT.json'
        before = current.read_bytes()
        files = self.resolve(material_release_id=self.candidate.release_id, material_release_commit=self.release_commit)
        self.assertIn('runtime.py', files)
        relative_release = self.candidate.release_dir.relative_to(self.repo).as_posix()
        self.assertIn(f'{relative_release}/manifest.json', files)
        self.assertIn(f'{relative_release}/payload/runtime.py', files)
        self.assertNotIn('official_strategy_materials/CURRENT.json', files)
        self.assertEqual(before, current.read_bytes())
        self.assertEqual('', self.git('status', '--porcelain'))

    def test_candidate_requires_both_release_identity_fields(self) -> None:
        for kwargs in ({'material_release_id': self.candidate.release_id}, {'material_release_commit': self.release_commit}):
            with self.subTest(kwargs=kwargs), self.assertRaisesRegex(ReleaseManifestError, 'candidate_material_identity_incomplete'):
                self.resolve(**kwargs)

    def test_candidate_rejects_wrong_release_commit(self) -> None:
        with self.assertRaisesRegex(ReleaseManifestError, 'candidate_material_release_invalid'):
            self.resolve(material_release_id=self.candidate.release_id, material_release_commit=self.git('rev-parse', 'HEAD^'))

    def test_candidate_rejects_runtime_drift(self) -> None:
        self.runtime.write_text('VERSION = 3\n')
        with self.assertRaisesRegex(ReleaseManifestError, 'candidate_material_release_invalid'):
            self.resolve(material_release_id=self.candidate.release_id, material_release_commit=self.release_commit)

    def test_candidate_rejects_corrupt_payload(self) -> None:
        (self.candidate.release_dir / 'payload/runtime.py').write_text('VERSION = 7\n')
        with self.assertRaisesRegex(ReleaseManifestError, 'candidate_material_release_invalid'):
            self.resolve(material_release_id=self.candidate.release_id, material_release_commit=self.release_commit)

    def test_candidate_rejects_qualification_from_a_later_head(self) -> None:
        (self.repo / 'unrelated.txt').write_text('later\n')
        self.git('add', 'unrelated.txt')
        self.git('commit', '-m', 'later head')
        with self.assertRaisesRegex(ReleaseManifestError, 'candidate_material_release_invalid'):
            self.resolve(material_release_id=self.candidate.release_id, material_release_commit=self.release_commit)


if __name__ == '__main__':
    unittest.main()
