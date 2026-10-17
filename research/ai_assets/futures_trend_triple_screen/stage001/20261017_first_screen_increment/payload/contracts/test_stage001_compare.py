import unittest
from stage001_compare import evaluate_metrics


def metric(**delta):
    return dict(end_equity=300000,total_return_pct=100,max_dd_pct=-40,sharpe=1,
        total_slippage=10000,total_trade_count=100,min_equity=100000,
        max_broker10_margin_to_equity_pct=70,days_over_100pct=0,days_equity_below_zero=0,**delta)


class DecisionTests(unittest.TestCase):
    def test_return_increase_cannot_hide_worse_drawdown(self):
        a=metric();c={**a,'total_return_pct':110,'max_dd_pct':-41}
        self.assertFalse(evaluate_metrics(a,c)['fullperiod_screen_pass'])

    def test_both_outcomes_still_require_margin_not_worse(self):
        a=metric();c={**a,'total_return_pct':110,'max_dd_pct':-35,
            'max_broker10_margin_to_equity_pct':75}
        self.assertFalse(evaluate_metrics(a,c)['fullperiod_screen_pass'])

    def test_both_improvements_allow_next_stage_but_never_claim_promotion(self):
        a=metric();c={**a,'total_return_pct':110,'max_dd_pct':-35}
        d=evaluate_metrics(a,c)
        self.assertTrue(d['fullperiod_screen_pass'])
        self.assertFalse(d['production_qualified'])
        self.assertEqual(d['next_action'],'independent_review_then_fixed_multicycle')


if __name__=='__main__':unittest.main()
