"""Offline typed-capability immutability fixtures; never source qualification."""
import copy,hashlib,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
R=Path('/Users/mac/.codex/worktrees/weekly19-official-20261031/fian');sys.path.insert(0,str(R/'examples/portfolio_backtesting'))
import qmt_roll_weekly19_broker_evidence as p
import qmt_roll_weekly19_warm_evidence as warm
class AuthorityCacheIndependent(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory(dir='/private/tmp');self.addCleanup(self.t.cleanup);self.root=Path(self.t.name).resolve();self.root.chmod(0o700)
  self.identity=dict(account_key='a'*64,material_release_id='named-fixture-not-qualified',execution_profile='weekly19-15w-r150k')
  self.key=b'offline-fixture-key-no-authority!!';self.keypath=self.root/'key';self.keypath.write_bytes(self.key);self.keypath.chmod(0o600)
  self.body=dict(self.identity,allowed_capture_kinds=['stage174_query'],key_artifact=dict(path=str(self.keypath),sha256=hashlib.sha256(self.key).hexdigest()),authority_sources={n:p._source_digest(n)for n in p.CAPTURE_AUTHORITY_SOURCE_FILES})
  self.path=self.root/'registry.json';self.raw=p.funding._canonical(self.body);self.path.write_bytes(self.raw);self.path.chmod(0o600);self.ref=dict(path=str(self.path),sha256=hashlib.sha256(self.raw).hexdigest())
  # Simulate a previously loaded process-local capability only. The named
  # fixture omits real qualification; this private test token is NOT a receipt.
  self.cap=p.CaptureAuthority(p._AUTHORITY_TOKEN,self.ref,self.body,self.key)
 def load(self):return p._authority_for(self.ref,self.identity,None,capability=self.cap)
 def test_unmodified_snapshot_uses_cache_without_new_full_qualification(self):
  with patch.object(p,'load_capture_authority_registry',side_effect=AssertionError('no new real qualification')):self.assertIs(self.load(),self.cap)
 def test_in_memory_allowed_kinds_cannot_exceed_actual_private_registry(self):
  self.cap.registry['allowed_capture_kinds'].append('transfer_serial_query')
  with self.assertRaisesRegex(p.BrokerEvidenceError,'registry_body_changed'):self.load()
 def test_in_memory_qualification_metadata_cannot_be_added_under_same_raw_sha(self):
  self.cap.registry['qualification_identity']={'source_commit':'a'*40}
  with self.assertRaisesRegex(p.BrokerEvidenceError,'registry_body_changed'):self.load()
 def test_rotated_actual_key_is_detected_even_with_same_size_and_mtime(self):
  stat=self.keypath.stat();self.keypath.write_bytes(b'x'*len(self.key));__import__('os').utime(self.keypath,ns=(stat.st_atime_ns,stat.st_mtime_ns))
  with self.assertRaisesRegex(p.BrokerEvidenceError,'key_drift'):self.load()
 def test_mutated_cached_key_does_not_sign_with_different_material(self):
  self.cap._key=b'z'*len(self.key)
  with self.assertRaisesRegex(p.BrokerEvidenceError,'key_drift'):self.load()
 def test_raw_registry_reformat_is_not_accepted_by_semantic_json_equality(self):
  self.path.write_text(json.dumps(self.body,indent=2))
  with self.assertRaisesRegex(p.BrokerEvidenceError,'registry_drift'):self.load()
 def test_warm_cache_cannot_bypass_the_same_registry_body_guard(self):
  self.cap.registry['allowed_capture_kinds'].append('warm_epoch_snapshot')
  policy=dict(capture_authority_registry=self.ref,capture_authority_capability=self.cap,now=None)
  with self.assertRaisesRegex(p.BrokerEvidenceError,'registry_body_changed'):warm._capability(policy,self.identity)
 def test_plain_json_and_wrong_identity_never_grant_typed_authority(self):
  with self.assertRaises(p.BrokerEvidenceError):p._authority_for(self.ref,self.identity,None,capability={'qualified':True})
  with self.assertRaises(p.BrokerEvidenceError):p._authority_for(self.ref,dict(self.identity,account_key='b'*64),None,capability=self.cap)
if __name__=='__main__':unittest.main(verbosity=2)
