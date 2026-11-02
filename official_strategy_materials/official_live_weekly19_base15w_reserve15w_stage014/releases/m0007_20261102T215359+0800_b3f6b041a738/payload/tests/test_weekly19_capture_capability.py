"""Process-local authority reuse checks using a named offline capability fixture."""
from copy import deepcopy
from pathlib import Path
import hashlib,json,sys,tempfile,unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'examples/portfolio_backtesting'))
import qmt_roll_weekly19_broker_evidence as provider
class CapabilityTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir='/private/tmp');self.root=Path(self.tmp.name).resolve();self.root.chmod(0o700);self.path=self.root/'registry.json'
  self.identity=dict(account_key='fixture',material_release_id='fixture-release',execution_profile='weekly19-15w-r150k')
  self.key=self.root/'key';self.key.write_bytes(b'fixture-not-production');self.key.chmod(0o600)
  self.registry=dict(self.identity,allowed_capture_kinds=['stage174_query'],key_artifact=dict(path=str(self.key),sha256=hashlib.sha256(self.key.read_bytes()).hexdigest()),authority_sources={p:provider._source_digest(p)for p in provider.CAPTURE_AUTHORITY_SOURCE_FILES})
  self.raw=json.dumps(self.registry).encode();self.path.write_bytes(self.raw);self.path.chmod(0o600)
  self.ref=dict(path=str(self.path),sha256=hashlib.sha256(self.raw).hexdigest())
  self.cap=provider.CaptureAuthority(provider._AUTHORITY_TOKEN,self.ref,self.registry,b'fixture-not-production')
 def tearDown(self):self.tmp.cleanup()
 def load(self,**kw):return provider._authority_for(kw.get('reference',self.ref),kw.get('identity',self.identity),None,capability=kw.get('capability',self.cap))
 def test_already_loaded_capability_avoids_full_qualification_but_checks_real_sources(self):
  with patch.object(provider,'load_capture_authority_registry',side_effect=AssertionError('not a new qualification')):
   self.assertIs(self.load(),self.cap)
 def test_json_qualified_flag_cannot_replace_typed_capability(self):
  with self.assertRaisesRegex(ValueError,'capability_invalid'):self.load(capability={'qualified':True})
 def test_wrong_registry_identity_and_source_drift_rejected(self):
  for key in self.identity:
   identity=dict(self.identity,**{key:'other'})
   with self.assertRaisesRegex(ValueError,'identity_mismatch'):self.load(identity=identity)
  with self.assertRaisesRegex(ValueError,'registry_mismatch'):self.load(reference=dict(self.ref,sha256='a'*64))
  with patch.object(provider,'_source_digest',return_value='f'*64):
   with self.assertRaisesRegex(ValueError,'source_drift'):self.load()
 def test_live_registry_bytes_and_complete_source_closure_required(self):
  self.path.write_text('{"fixture_only":false}')
  with self.assertRaisesRegex(ValueError,'registry_drift'):self.load()
  self.path.write_bytes(self.raw);self.cap.registry['allowed_capture_kinds'].append('transfer_serial_query')
  with self.assertRaisesRegex(ValueError,'registry_body_changed'):self.load()
 def test_rotated_private_key_or_mutated_cached_key_cannot_sign(self):
  self.cap._key=b'other'
  with self.assertRaisesRegex(ValueError,'key_drift'):self.load()
  self.cap._key=b'fixture-not-production';self.key.write_bytes(b'rotated')
  with self.assertRaisesRegex(ValueError,'key_drift'):self.load()
if __name__=='__main__':unittest.main()
