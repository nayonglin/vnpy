"""One regression for the report-only Stage128 top-level anchor contract."""
import importlib.util
from pathlib import Path
import unittest


class FinalizeMetadata(unittest.TestCase):
    def test_anchor_contract_is_top_level_while_capacity_remains_in_cash(self):
        path=Path(__file__).with_name('stage157_voluntary_finalize.py')
        self.assertTrue(path.exists(),'metadata-only finalizer missing')
        spec=importlib.util.spec_from_file_location('fixture157_finalize',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        execution={'cash':{'capacity':{'fraction':.01}},'anchor_and_execution':{'immutable':True}}
        protocol={'cash':{'initial_capital':1000000},'statistics':{'indices':{}}}
        result=module.build_disclosure(protocol,execution)
        self.assertEqual(result['anchor'],{'immutable':True})
        self.assertEqual(result['capacity'],{'fraction':.01})
        self.assertFalse(result['production_qualified'])


if __name__=='__main__':unittest.main()
