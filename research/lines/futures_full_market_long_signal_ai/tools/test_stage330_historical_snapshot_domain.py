"""One domain-only tiny; no real cache/economics/SQL or old tests."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

import numpy as np


class HistoricalDomainTiny(unittest.TestCase):
    def test_catalog_empty_product_survives_and_native_domain_must_match(self):
        # Catches deriving the full mother domain from observed price epochs,
        # or accepting an unexpected/missing observed native product.
        path=Path(__file__).with_name('stage330_historical_snapshot_domain.py')
        self.assertTrue(path.exists(),'correct catalog/native-domain adapter is not implemented')
        spec=importlib.util.spec_from_file_location('stage330_tiny',path)
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        ordinary=['SHFE.'+chr(65+i//26)+chr(65+i%26) for i in range(91)]
        products=['DCE.L','DCE.L_F','DCE.PP','DCE.PP_F','DCE.V','DCE.V_F','DCE.S']+ordinary
        roster=[dict(product_id=p,contracts_with_candidates='0' if p=='DCE.S' else '1') for p in products]
        epochs=[p+'.203001' for p in products if p!='DCE.S']
        full,domain=m.catalog_domain(epochs,roster)
        self.assertEqual(len(full),98)
        self.assertEqual(len({p.removesuffix('_F') for p in full}),95)
        self.assertEqual(domain['expected_native_products'],97)
        self.assertEqual(domain['observed_native_products'],97)
        self.assertEqual(domain['missing_native_products'],['DCE.S'])
        core=m.load_core()
        series={e:SimpleNamespace(days=np.array([0]),values=np.array([[100.,101.,99.,100.,1000.]]),
            accepted=np.array([True]),valid=np.array([True]),N=np.array([np.nan]),
            low20=np.array([np.nan]),run=np.array([1])) for e in epochs}
        current=[dict(contract_epoch_id=e,trade_date='2026-10-16',open=100.,high=101.,low=99.,
            close=100.,volume=1000.,close_oi=None,quality_status='accepted',source_id='tiny',source_locator='tiny') for e in epochs]
        snap=m.assemble_snapshot(series,['2026-10-16'],{},full,current,core=core)
        observed=core.build_u_observations(snap['series_by_epoch'],0,snap['dates'],{},full,D_context=snap['D_context'])
        self.assertEqual(len(observed['mothers']),98)
        empty=next(r for r in observed['mothers'] if r['product_id']=='DCE.S')
        self.assertEqual(empty['candidate_count'],0)
        self.assertEqual(empty['reference_epoch'],'')
        self.assertEqual(empty['status'],'no_accepted_observation')
        self.assertEqual(len(observed['candidates']),97)
        with self.assertRaises(ValueError):
            m.catalog_domain(epochs+['GFEX.NEW.203001'],roster)
        with self.assertRaises(ValueError):
            m.catalog_domain(epochs[1:],roster)
        with self.assertRaises(ValueError):
            m.catalog_domain(epochs,[r for r in roster if r['product_id']!='DCE.S'])


if __name__=='__main__':
    unittest.main()
