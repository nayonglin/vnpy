"""Tiny source-only OI projection boundaries; no native SQL/fit/cash."""
import importlib.util
import json
import math
from pathlib import Path
import unittest

import pandas as pd


TOOLS=Path(__file__).parent
SOURCE=TOOLS/'stage085_oi_projection.py'
if SOURCE.exists():
    spec=importlib.util.spec_from_file_location('stage085_under_test',SOURCE)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
else:m=None
UNITS=json.loads((TOOLS.parents[1]/'futures_trend_rollover_shape_same_volume/outputs/stage266_clean_daily/unit_contract.json').read_bytes())
DATES=['2019-12-27','2019-12-30','2019-12-31','2020-01-02','2020-01-03']
EPOCH='SHFE.RB.202005'


def mother(epoch=EPOCH,u=4,event='event'):
    return pd.DataFrame([dict(sequence_index=0,event_id=event,product_id='SHFE.RB',family_id='SHFE.RB',
                              exchange='SHFE',u_date=DATES[u],u_index=u,reference_epoch=epoch)])


def bar(day,oi,volume=50.,epoch=EPOCH,source='rqalpha',factor=None,family='rqalpha'):
    factor=(.5 if day<'2020-01-01' else 1.) if factor is None else factor
    return dict(contract_epoch_id=epoch,exchange='SHFE',trade_date=day,close_oi=oi,volume=volume,
                source_id=source,source_family=family,volume_factor=factor,oi_factor=factor,
                quality_status='accepted',source_locator='fixture',native_volume=volume/factor,
                native_close_oi=oi/factor)


class OISourceBoundaries(unittest.TestCase):
    def project(self,rows,panel=None):
        self.assertIsNotNone(m,'new isolated OI source projection required')
        panel=mother() if panel is None else panel
        result=m.build_projection(panel,rows,DATES,UNITS)
        self.assertEqual(result.event_id.tolist(),panel.event_id.tolist())
        return result

    def test_canonical_factor_transition_is_comparable_without_second_division(self):
        rows=[bar(DATES[2],100.),bar(DATES[3],120.)]
        row=self.project(rows).iloc[0]
        self.assertEqual(row.w_date,'2019-12-31')
        self.assertEqual(row.v_date,'2020-01-02')
        self.assertEqual(row.w_oi_factor,.5)
        self.assertEqual(row.v_oi_factor,1.)
        self.assertEqual(row.oi_missing,0)
        self.assertAlmostEqual(row.oi_scalar_raw,.4)

    def test_epoch_switch_uses_current_real_epoch_lags_even_before_it_was_representative(self):
        newer='SHFE.RB.202010'
        panel=pd.concat([mother(u=2,event='previous'),mother(epoch=newer,u=4,event='new')],ignore_index=True)
        panel['sequence_index']=[0,1]
        rows=[bar(DATES[0],10.),bar(DATES[1],20.),bar(DATES[2],99999.),bar(DATES[3],100000.),
              bar(DATES[2],100.,epoch=newer),bar(DATES[3],125.,epoch=newer)]
        row=self.project(rows,panel).iloc[1]
        self.assertEqual(row.reference_epoch,newer)
        self.assertEqual(row.oi_scalar_raw,.5)
        missing=self.project([r for r in rows if not(r['contract_epoch_id']==newer and r['trade_date']==DATES[2])],panel).iloc[1]
        self.assertEqual(missing.oi_missing,1)
        self.assertIn('missing_w_bar',missing.missing_reason)
        self.assertTrue(math.isnan(missing.oi_scalar_raw))

    def test_missing_lag_day_cannot_jump_to_previous_available_quote(self):
        row=self.project([bar(DATES[1],5.),bar(DATES[3],120.)]).iloc[0]
        self.assertEqual(row.w_date,DATES[2])
        self.assertIn('missing_w_bar',row.missing_reason)
        first=self.project([],mother(u=0)).iloc[0]
        self.assertEqual(first.oi_missing,1)
        self.assertIn('missing_lag_source_day',first.missing_reason)

    def test_different_source_ids_are_missing_without_scalar_zero_repair(self):
        rows=[bar(DATES[2],100.),bar(DATES[3],120.,source='old_tq:SHFE.rb2005',family='old_tq',factor=1.)]
        row=self.project(rows).iloc[0]
        self.assertEqual(row.oi_missing,1)
        self.assertIn('different_source_id',row.missing_reason)
        self.assertTrue(math.isnan(row.oi_scalar_raw))

    def test_zero_close_OI_and_zero_change_are_valid_without_open_OI(self):
        row=self.project([bar(DATES[2],0.),bar(DATES[3],0.)]).iloc[0]
        self.assertEqual(row.oi_observed,1)
        self.assertEqual(row.oi_missing,0)
        self.assertEqual(row.oi_scalar_raw,0.)
        self.assertEqual(row.projection_state,'observed_same_epoch_same_source_canonical')
        large=self.project([bar(DATES[2],0.),bar(DATES[3],1000.,volume=10.)]).iloc[0]
        self.assertEqual(large.oi_scalar_raw,100.,'no clipping or abs(deltaOI)<=V gate')

    def test_invalid_v_volume_preserves_identity_and_explicit_missing(self):
        for volume in (0.,-1.,float('nan')):
            with self.subTest(volume=volume):
                row=self.project([bar(DATES[2],100.),bar(DATES[3],120.,volume=volume)]).iloc[0]
                self.assertEqual(row.oi_missing,1)
                self.assertIn('invalid_v_volume',row.missing_reason)

    def test_unknown_unit_factor_is_missing_but_accepted_official_has_no_new_regime_requirement(self):
        invalid=bar(DATES[3],120.,factor=.25)
        row=self.project([bar(DATES[2],100.),invalid]).iloc[0]
        self.assertEqual(row.oi_missing,1)
        self.assertIn('unaccepted_v_unit',row.missing_reason)
        official=[bar(DATES[2],100.,source='official:SHFE_futures_2019',family='official',factor=.5),
                  bar(DATES[3],120.,source='official:SHFE_futures_2019',family='official',factor=1.)]
        row=self.project(official).iloc[0]
        self.assertEqual(row.oi_observed,1,'stat-bound accepted official canonical rows need no absent raw unit_regime')
        self.assertEqual(row.oi_scalar_raw,.4)


if __name__=='__main__':unittest.main()
