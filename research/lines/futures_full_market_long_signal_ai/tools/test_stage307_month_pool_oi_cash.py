"""One new adapter identity boundary; no kernel/data/financial execution."""
import argparse
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

P=Path(__file__).with_name('stage307_month_pool_oi_cash.py')
class AdapterIdentity(unittest.TestCase):
 def test_accepts_only_new_protocol_and_candidate_without_starting_cash(self):
  self.assertTrue(P.exists(),'missing new month-pool OI adapter')
  spec=importlib.util.spec_from_file_location('cash307_identity_fixture',P)
  m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  protocol=m.LINE/'outputs/stage304_month_pool_oi_share_protocol/protocol.json'
  out=m.LINE/'outputs/stage307_month_pool_oi_cash/fixture_never_started'
  self.assertFalse(out.exists())
  with tempfile.TemporaryDirectory(prefix='stage307-identity-') as tmp:
   authpath=Path(tmp)/'auth.json'
   auth=dict(schema='stage307_exact_root_authorization_v1',authorized_by='root',protocol_sha256=m.PROTOCOL_SHA,
    output=str(out),max_new_candidate_cash=4,max_new_fit=0,source_bundle=m.source_bundle(),interface_refs=m.binding(m.REFS))
   authpath.write_text(json.dumps(auth))
   args=argparse.Namespace(output=str(out),protocol=str(protocol),protocol_sha256=m.PROTOCOL_SHA,
    authorization=str(authpath),authorization_sha256=m.binding(authpath)['sha256'])
   got=m.authorize(args)
   self.assertEqual(got[1]['candidate'],'LAGGED_MONTH_POOL_OI_SHARE_OFFSET')
   self.assertFalse(out.exists())
   args.protocol_sha256='b604940cf2d43fa504883796a8532a734101a7d2291d7fee225296c384e39193'
   with self.assertRaises(ValueError):m.authorize(args)
  self.assertFalse(out.exists())
if __name__=='__main__':unittest.main()
