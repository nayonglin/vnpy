"""Tiny metadata-shape regression only, no actual inputs/model/cash evaluation."""
import copy
import unittest
from stage072_actual_independent_review2 import validate_fit_root_chain

class MetadataBinding(unittest.TestCase):
    def fixture(self):
        binding={'path':'/fixed/fit/manifest.json','bytes':10,'sha256':'manifest'}
        terminal={'path':'/fixed/fit/terminal.json','bytes':11,'sha256':'terminal'}
        source=[{'path':'/code/model.py','bytes':12,'sha256':'source'}]
        inputs={'wide_labels':{'path':'/labels','bytes':13,'sha256':'labels'}}
        manifest={'protocol':{'sha256':'protocol'},'terminal':terminal,'source_bundle':source,'input_bindings':inputs}
        auth={'schema':'stage069_exact_root_authorization_v1','stage':'fit','authorized_by':'root','exact_source_authorized':True,
              'protocol_sha256':'protocol','output':'/fixed/fit','source_bundle':copy.deepcopy(source),'input_bindings':copy.deepcopy(inputs)}
        receipt={'fit_manifest':binding,'fit_terminal':terminal,'actual_starts':1,'auto_retries':0,'exit_code':0,'session_id':47352,
                 'model_fits_attempted':12,'model_fits_completed':12,'native_queries':0,'new_cash':0}
        return manifest,auth,receipt,binding,'/fixed/fit'

    def test_071_shape_has_no_top_level_authorization(self):
        args=self.fixture()
        with self.assertRaises(KeyError):_ = args[0]['authorization']
        validate_fit_root_chain(*args)

    def test_separate_chain_must_not_bypass_input_binding(self):
        args=self.fixture();args[1]['input_bindings']['wide_labels']['sha256']='changed'
        with self.assertRaises(AssertionError):validate_fit_root_chain(*args)

if __name__=='__main__':unittest.main()
