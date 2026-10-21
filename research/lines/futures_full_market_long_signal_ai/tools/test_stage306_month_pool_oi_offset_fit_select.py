"""One new identity contract; no research arrays, fits, network or cash."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

TOOLS=Path(__file__).resolve().parent
SPEC=importlib.util.spec_from_file_location('tiny306',TOOLS/'stage306_month_pool_oi_offset_fit_select.py')
M=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(M)


def binding(path):
    path=Path(path).resolve();raw=path.read_bytes()
    return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


class Identity(unittest.TestCase):
    # A stale reopening candidate/auth namespace must not authorize the OI run.
    def test_only_exact_oi_identity_authorizes_fresh_306_output(self):
        names=('stage306_month_pool_oi_offset_fit_select.py','test_stage306_month_pool_oi_offset_fit_select.py',
            'stage285_wasde_offset_fit_select.py','stage130_contract_choice_fit.py',
            'stage071_settlement_narrow_fit.py','stage156_voluntary_choices.py')
        roles=('fit_manifest','execution_protocol','market_protocol','mothers','actions','calendar',
            'source_manifest','source_proof_stage','static_review_receipt','control_choices_main',
            'control_choice_manifest','control_held_choices','control_held_manifest','control_held_review')
        with tempfile.TemporaryDirectory(prefix='stage306_identity_') as temporary:
            temporary=Path(temporary)
            output=TOOLS.parent/'outputs/stage306_month_pool_oi_offset_fit_select'/temporary.name
            source=temporary/'unopened_305_manifest.json'
            auth=dict(schema='stage306_exact_root_authorization_v1',authorized_by='root',exact_source_authorized=True,
                protocol_sha256='729aa21945cc9dc0f446485dd2671a970cec443f1c32783a083b99ce10ffe6a4',
                candidate='LAGGED_MONTH_POOL_OI_SHARE_OFFSET',output=str(output),max_new_fit=6,max_new_cash=0,
                source_bundle=sorted((binding(TOOLS/n) for n in names),key=lambda b:b['path']),
                inputs={r:dict(path=str(source if r=='source_manifest' else temporary/r),bytes=0,sha256='unopened') for r in roles})
            path=temporary/'authorization.json'
            def args(value):
                path.write_text(json.dumps(value),encoding='utf-8')
                return SimpleNamespace(authorization=str(path),authorization_sha256=binding(path)['sha256'],
                    source_manifest=str(source),output=str(output))
            try:result=M.authorize(args(auth))
            except ValueError as exc:self.fail('exact frozen OI identity rejected: '+str(exc))
            self.assertEqual(result[0],output)
            self.assertEqual(result[1]['candidate'],'LAGGED_MONTH_POOL_OI_SHARE_OFFSET')
            self.assertEqual(result[3]['schema'],'stage306_exact_root_authorization_v1')
            for old in (dict(auth,candidate='REOPENING_GAP20_OFFSET'),
                    dict(auth,schema='stage296_exact_root_authorization_v1')):
                with self.assertRaises(ValueError):M.authorize(args(old))
            self.assertFalse(output.exists());self.assertFalse(source.exists())


if __name__=='__main__':unittest.main()
