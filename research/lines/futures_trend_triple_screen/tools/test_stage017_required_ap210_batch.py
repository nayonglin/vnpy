"""The known AP210 source correction cannot be displaced by batch density."""
import unittest

try:
    import stage017_required_ap210_batch as module
except ImportError:
    module=None


def target(symbol,day="2022-04-06",minutes=225):
    return dict(vt_symbol=symbol,execution_trade_date=day,expected_minutes=minutes)


class RequiredBatchTests(unittest.TestCase):
    def setUp(self):self.assertIsNotNone(module,"Stage017 wrapper is not implemented")

    def test_ap210_is_reserved_before_sorted_other_contracts(self):
        required=target("AP210.CZCE")
        others=[target(f"AA{i:03d}.CZCE")for i in range(8)]
        selected=module.select_bounded_targets(others,required)
        self.assertEqual(len({x['vt_symbol']for x in selected}),8)
        self.assertIn(required,selected)
        self.assertNotIn(others[-1],selected)

    def test_budget_cannot_drop_mandatory_ap_or_exceed_20000_minutes(self):
        required=target("AP210.CZCE")
        selected=module.select_bounded_targets([target("CF205.CZCE",minutes=10000),
            target("FG205.CZCE",minutes=10000)],required)
        self.assertEqual(sum(x['expected_minutes']for x in selected),10225)
        self.assertIn(required,selected)
        with self.assertRaisesRegex(ValueError,"mandatory_ap210_target_invalid"):
            module.select_bounded_targets([],{**required,"expected_minutes":224})


if __name__=="__main__":unittest.main()
