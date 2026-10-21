import unittest
from stage024_fixed_r_accounting import Economics, Fill, FixedRiskLedger


def meta(multiplier=10,validated=False,**kw):
    base=dict(multiplier=multiplier,tick=1,open_per_lot=2,open_rate=0,
              close_per_lot=3,close_rate=0,close_today_per_lot=5,close_today_rate=0,
              historical_validated=validated)
    base.update(kw)
    return Economics(**base)


def fill(kind,day,price,qty=2,contract='A',economics=None,roll=False,slippage=0):
    return Fill(kind,contract,day,price,qty,economics or meta(),slippage,roll)


class AccountingTests(unittest.TestCase):
    def test_partial_exit_close_today_and_fixed_r(self):
        book=FixedRiskLedger('long',90)
        book.apply(fill('open','2020-01-02',100))
        book.apply(fill('close','2020-01-02',110,1))
        book.apply(fill('close','2020-01-03',120,1))
        x=book.mark({})
        self.assertEqual(x['risk_currency'],200)
        self.assertEqual(x['realized_gross'],300)
        self.assertEqual(x['commission'],12)
        self.assertEqual(x['net'],288)
        self.assertEqual(x['net_r'],1.44)
        self.assertEqual(x['status'],'conditional_economics')

    def test_short_side_and_explicit_extra_slippage(self):
        book=FixedRiskLedger('short',110)
        book.apply(fill('open','2020-01-02',100,slippage=1))
        book.apply(fill('close','2020-01-03',90,slippage=1))
        x=book.mark({})
        self.assertEqual(x['realized_gross'],200)
        self.assertEqual(x['extra_slippage'],40)
        self.assertEqual(x['net'],150)

    def test_roll_uses_each_multiplier_and_no_contract_price_gap(self):
        book=FixedRiskLedger('long',90)
        book.apply(fill('open','2020-01-02',100))
        book.apply(fill('close','2020-01-03',110,roll=True))
        book.apply(fill('open','2020-01-03',1000,1,'B',meta(20),True))
        x=book.mark({'B':1010})
        self.assertEqual(x['risk_currency'],200)
        self.assertEqual(x['realized_gross'],200)
        self.assertEqual(x['unrealized_gross'],200)
        self.assertEqual(x['gross_r'],2)
        self.assertEqual(x['commission'],12)

    def test_mark_not_close_and_missing_mark_unknown(self):
        book=FixedRiskLedger('long',90)
        book.apply(fill('open','2020-01-02',100))
        x=book.mark({'A':110})
        self.assertEqual(x['realized_gross'],0)
        self.assertEqual(x['unrealized_gross'],200)
        self.assertEqual(x['commission'],4)
        self.assertEqual(x['remaining_qty'],2)
        self.assertIsNone(book.mark({})['net'])
        self.assertIsNone(book.mark({})['unrealized_gross'])

    def test_missing_cost_not_zero_and_explicit_zero_is_known(self):
        book=FixedRiskLedger('long',90)
        book.apply(fill('open','2020-01-02',100,economics=meta(open_per_lot=None)))
        x=book.mark({'A':110})
        self.assertIsNone(x['commission'])
        self.assertIsNone(x['net'])
        self.assertEqual(x['realized_gross'],0)
        zero=FixedRiskLedger('long',90)
        zero.apply(fill('open','2020-01-02',100,economics=meta(validated=True,open_per_lot=0)))
        self.assertEqual(zero.mark({'A':100})['net'],0)
        self.assertEqual(zero.mark({'A':100})['status'],'computed_with_declared_validated_economics')

    def test_turnover_rate_each_side_and_close_today_not_close_rate(self):
        m=meta(open_per_lot=0,open_rate=.001,close_today_per_lot=0,close_today_rate=.002,
               close_per_lot=999,close_rate=.9)
        book=FixedRiskLedger('long',90)
        book.apply(fill('open','2020-01-02',100,economics=m))
        book.apply(fill('close','2020-01-02',110,economics=m))
        self.assertEqual(book.mark({})['commission'],6.4)

    def test_rejects_invalid_fills_without_changing_state(self):
        book=FixedRiskLedger('long',90)
        book.apply(fill('open','2020-01-02',100))
        before=book.mark({'A':100})
        for bad in [fill('close','2020-01-03',100,3),fill('open','2020-01-03',100),
                    fill('close','2020-01-01',100),fill('close','2020-01-03',100,contract='B'),
                    fill('close','2020-01-03',100,economics=meta(20)),
                    fill('close','2020-01-03',100.5),fill('close','2020-01-03',100,qty=.5),
                    fill('close','2020-01-03',100,slippage=-1)]:
            with self.assertRaises(ValueError):book.apply(bad)
            self.assertEqual(book.mark({'A':100}),before)

    def test_wrong_side_initial_risk_and_reentry_without_roll_rejected(self):
        book=FixedRiskLedger('long',110)
        with self.assertRaises(ValueError):book.apply(fill('open','2020-01-02',100))
        book=FixedRiskLedger('long',90)
        book.apply(fill('open','2020-01-02',100))
        book.apply(fill('close','2020-01-03',110))
        with self.assertRaises(ValueError):book.apply(fill('open','2020-01-06',100))


if __name__=='__main__':unittest.main()
