from pathlib import Path
import json
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import pandas as pd
import test_stage249_verify_patches as fixtures

class CacheSourceTests(unittest.TestCase):
    def module(self):
        self.assertTrue(Path(__file__).with_name('stage249_validate_cache_sources.py').is_file(),'source closure module required')
        import stage249_validate_cache_sources
        return stage249_validate_cache_sources

    def test_completed_patch_proves_cache_when_legacy_source_absent(self):
        m=self.module()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);task,patch,_=fixtures.PatchManifestTests().fixture(root)
            cache=root/'cache.csv';pd.read_parquet(patch['parquet']).to_csv(cache,index=False)
            report=m.validate_sources(cache,[task],root/'absent',[root])
            self.assertEqual(report['status'],'complete');self.assertEqual(report['counts']['stage249_identical'],1)

    def test_cache_price_change_fails_source_closure(self):
        m=self.module()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);task,patch,_=fixtures.PatchManifestTests().fixture(root)
            frame=pd.read_parquet(patch['parquet']);frame.loc[0,'open']=99.5;cache=root/'cache.csv';frame.to_csv(cache,index=False)
            report=m.validate_sources(cache,[task],root/'absent',[root])
            self.assertEqual(report['status'],'incomplete');self.assertEqual(report['counts']['stage249_values_differ'],1)

if __name__=='__main__':unittest.main()
