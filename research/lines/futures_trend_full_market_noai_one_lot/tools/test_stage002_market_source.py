from pathlib import Path
import sys
import unittest
import pandas as pd
sys.path.insert(0, str(Path(__file__).parent))
try:
    import stage002_market_source as source
except ModuleNotFoundError:
    source = None


class MarketSourceTest(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(source, 'stage002 market source not implemented')

    def rows(self):
        return pd.DataFrame([
            dict(contract_epoch_id='DCE.A.202605',exchange='DCE',product='A',contract_yyyymm='202605',date='2026-04-01',close_oi=10,volume=10),
            dict(contract_epoch_id='DCE.A.202609',exchange='DCE',product='A',contract_yyyymm='202609',date='2026-04-01',close_oi=10,volume=20),
            dict(contract_epoch_id='DCE.A.202605',exchange='DCE',product='A',contract_yyyymm='202605',date='2026-04-02',close_oi=1000,volume=1000),
        ])

    def test_mapping_is_previous_session_only_and_no_stale_carry(self):
        m=source.build_causal_mapping(self.rows(), pd.DataFrame(), pd.to_datetime(['2026-04-01','2026-04-02','2026-04-03','2026-04-06']), [('DCE','A')])
        self.assertEqual(m.loc[m.date.eq('2026-04-02'),'contract_epoch_id'].iloc[0], 'DCE.A.202609')
        self.assertEqual(m.loc[m.date.eq('2026-04-03'),'contract_epoch_id'].iloc[0], 'DCE.A.202605')
        self.assertEqual(m.loc[m.date.eq('2026-04-06'),'contract_epoch_id'].iloc[0], '')
        self.assertEqual(m.loc[m.date.eq('2026-04-02'),'observation_date'].iloc[0], '2026-04-01')

    def test_expired_month_and_monthly_average_maturity_are_excluded(self):
        rows=self.rows().iloc[:2].copy()
        rows.loc[0,['product','contract_epoch_id','contract_yyyymm']]=['L_F','DCE.L_F.202605','202605']
        rows.loc[1,['product','contract_epoch_id','contract_yyyymm']]=['L_F','DCE.L_F.202603','202603']
        contracts=pd.DataFrame([dict(contract_epoch_id='DCE.L_F.202605',maturity_date='2026-04-01')])
        m=source.build_causal_mapping(rows, contracts, pd.to_datetime(['2026-04-01','2026-04-02']), [('DCE','L_F')])
        self.assertEqual(m.iloc[-1].contract_epoch_id,'')

    def test_stable_tie_and_full_epoch_keep_decade_and_F_identity(self):
        rows=self.rows().iloc[:2].copy();rows['volume']=20
        m=source.build_causal_mapping(rows,pd.DataFrame(),pd.to_datetime(['2026-04-01','2026-04-02']),[('DCE','A')])
        self.assertEqual(m.iloc[-1].contract_epoch_id,'DCE.A.202605')
        self.assertEqual(source.research_symbol('CZCE','TA','201505'),'TA201505.CZCE')
        self.assertEqual(source.research_symbol('DCE','L_F','202605'),'l_F202605.DCE')

    def test_exact_contract_specs_override_product_fallback_and_hand_fees_preserved(self):
        contracts=pd.DataFrame([dict(contract_epoch_id='DCE.A.202605',exchange='DCE',product='A',contract_yyyymm='202605')])
        metadata=[dict(exchange='DCE',underlying_symbol='A',order_book_id='A2605',trading_code='a2605',contract_multiplier=10,margin_rate=.1)]
        info=[dict(underlying_symbol='A',tick_size=2,commission_type='by_volume',open_commission_ratio=3,close_commission_ratio=4,close_commission_today_ratio=1,margin_rate=.2),dict(order_book_id='A2605',tick_size=1,commission_type='by_volume',open_commission_ratio=2,close_commission_ratio=5,close_commission_today_ratio=0,margin_rate=.15)]
        result=source.resolve_metadata(contracts,metadata,info).iloc[0]
        self.assertEqual((result['size'],result.pricetick,result.margin_ratio),(10,1,.15))
        self.assertEqual((result.rate,result.fee_per_lot_open,result.fee_per_lot_close,result.fee_per_lot_close_today),(0,2,5,0))
        self.assertEqual(result.commission_status,'observed_by_volume')

    def test_exact_instrument_margin_precedes_product_fee_fallback_margin(self):
        c=pd.DataFrame([dict(contract_epoch_id='DCE.A.202605',exchange='DCE',product='A',contract_yyyymm='202605')])
        m=[dict(exchange='DCE',underlying_symbol='A',order_book_id='A2605',contract_multiplier=10,margin_rate=.1)]
        f=[dict(underlying_symbol='A',tick_size=1,margin_rate=.2,commission_type='by_money',open_commission_ratio=.0001,close_commission_ratio=.0002,close_commission_today_ratio=.0003)]
        row=source.resolve_metadata(c,m,f).iloc[0]
        self.assertEqual(row.margin_ratio,.1)
        self.assertEqual(row.margin_source,'rq_exact_instrument')
        self.assertEqual((row.fee_method,row.fee_open,row.fee_close,row.fee_close_today),('by_money',.0001,.0002,.0003))

    def test_missing_specs_or_commission_fail_closed(self):
        c=pd.DataFrame([dict(contract_epoch_id='GFEX.PD.202608',exchange='GFEX',product='PD',contract_yyyymm='202608')])
        with self.assertRaisesRegex(ValueError,'metadata_missing'):
            source.resolve_metadata(c,[],[])
        m=[dict(exchange='GFEX',underlying_symbol='PD',order_book_id='PD2608',contract_multiplier=1000,margin_rate=.18)]
        with self.assertRaisesRegex(ValueError,'tick_missing'):
            source.resolve_metadata(c,m,[])
        i=[dict(underlying_symbol='PD',tick_size=.05)]
        with self.assertRaisesRegex(ValueError,'commission_missing'):
            source.resolve_metadata(c,m,i)

    def test_duplicate_contract_date_rejected(self):
        rows=pd.concat([self.rows(),self.rows().iloc[:1]],ignore_index=True)
        with self.assertRaisesRegex(ValueError,'duplicate_market_date'):
            source.build_causal_mapping(rows,pd.DataFrame(),pd.to_datetime(['2026-04-01','2026-04-02']),[('DCE','A')])

if __name__=='__main__':unittest.main()
