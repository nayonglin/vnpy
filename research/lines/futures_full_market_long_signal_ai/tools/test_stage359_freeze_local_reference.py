"""One bounded integration group for local payload preservation and true UTC T0."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from datetime import datetime, timezone

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parents[3]


class LocalReferenceFreezeTest(unittest.TestCase):
    def test_payload_receipt_and_failure_boundaries(self):
        spec = importlib.util.spec_from_file_location('freeze359', TOOLS/'stage359_freeze_local_reference.py')
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp)
            assets = []
            for name in ('stage320_causal_forward_core.py', 'stage321_forward_journal.py',
                         'stage322_continuous_paper_state.py', 'stage325_forward_caller.py'):
                p = TOOLS/name
                assets.append(dict(m.binding(p), logical_name=p.relative_to(ROOT).as_posix(),
                                   role='runtime_code', reproducibility_required=True))
            model = parent/'model.json'
            scaler = parent/'scaler.json'
            clock = parent/'clock_contract.json'
            model.write_text('{"test": "model"}\n')
            scaler.write_text('{"test": "scaler"}\n')
            clock.write_text(json.dumps(dict(schema='stage356_causal_clock_domain_policy_v1',
                version='pure52_input_vs_execution_v1', frozen_at=None)))
            # Synthetic files must also be in the allowed root: use an isolated
            # fixture directory beneath the real research line, then remove it.
            import shutil
            fixture = TOOLS.parent/'outputs'/('stage359_fixture_'+parent.name)
            fixture.mkdir()
            try:
                for p, role in ((model, 'model_artifact'), (scaler, 'feature_contract'),
                                (clock, 'operational_config')):
                    q = fixture/p.name
                    shutil.copyfile(p, q)
                    assets.append(dict(m.binding(q), logical_name=q.relative_to(ROOT).as_posix(),
                                       role=role, reproducibility_required=True))
                inventory = fixture/'inventory.json'
                x = dict(schema='test_inventory', closure_complete=True, assets=assets,
                         runtime={'qualification': 'synthetic only'}, source_provenance={},
                         external_entity_references_not_payload=[])
                inventory.write_text(json.dumps(x))
                bad = json.loads(json.dumps(x))
                bad['assets'][-1]['sha256'] = '0'*64
                inventory.write_text(json.dumps(bad))
                with self.assertRaises(ValueError):
                    m.freeze(inventory, parent/'bad')
                self.assertFalse((parent/'bad').exists())
                inventory.write_text(json.dumps(x))
                before = datetime.now(timezone.utc)
                result = m.freeze(inventory, parent/'actual')
                after = datetime.now(timezone.utc)
                event = json.loads(Path(result['freeze_event']['path']).read_bytes())
                t0 = datetime.fromisoformat(event['receipt']['recorded_at'])
                self.assertLessEqual(before, t0)
                self.assertLessEqual(t0, after)
                self.assertEqual(event['receipt']['kind'], 'research_reference_freeze')
                self.assertEqual(result['T0'], event['receipt']['recorded_at'])
                self.assertFalse(result['active'])
                self.assertIsNone(result['states'])
                self.assertEqual(result['asset_count'], 7)
                payload_model = parent/'actual'/'payload'/assets[-3]['logical_name']
                self.assertEqual(payload_model.read_bytes(), model.read_bytes())
                with self.assertRaises(FileExistsError):
                    m.freeze(inventory, parent/'actual')
            finally:
                shutil.rmtree(fixture)


if __name__ == '__main__':
    unittest.main()
