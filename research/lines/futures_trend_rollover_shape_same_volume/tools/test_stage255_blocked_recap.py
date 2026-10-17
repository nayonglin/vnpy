"""Checks for the non-trade semantics of the blocked-candidate adapter."""
import unittest
import pandas as pd
from stage255_blocked_recap import signal_rows, signal_meta, adapt_html
from stage248_recap_html import load_renderer


class BlockedRecapTests(unittest.TestCase):
    def sample(self):
        return pd.DataFrame([dict(signal_id='s1', signal_date='2026-10-14',
            contract_vt_symbol='rb2701.SHFE', product_vt_symbol='rb.SHFE',
            direction='short', reference_price=3200, ai_rank=0, ai_score=0,
            blocking_reason_zh='AI过滤', is_ai_primary_block=True, ai_pool_disallowed=True,
            record_kind='candidate', candidate_status='skipped')])

    def test_context_uses_signal_date_and_no_account_numbers(self):
        rows=signal_rows(self.sample())
        self.assertEqual(rows.entry_date.iloc[0], pd.Timestamp('2026-10-14'))
        self.assertEqual(rows.entry_date.iloc[0], rows.exit_date.iloc[0])
        self.assertTrue(rows.realized_pnl.isna().all())
        self.assertTrue(rows.r_multiple.isna().all())
        self.assertTrue(rows.volume.isna().all())

    def test_public_meta_has_no_fake_trade_and_unknown_rank_is_null(self):
        internal=dict(entry_x=4.5, entry_source='rb2701.SHFE', entry_marker_price=3200,
                      entry_price=3200, exit_price=3200, volume=float('nan'),
                      realized_pnl=float('nan'), chart_x_start=0, chart_x_end=5,
                      draw_intraday=0, context_fallback_dates=[])
        meta=signal_meta(internal,self.sample().iloc[0].to_dict())
        self.assertEqual(meta['signal_x'],4.5)
        self.assertEqual(meta['reference_marker_price'],3200)
        self.assertIsNone(meta['ai_rank'])
        self.assertIsNone(meta['ai_score'])
        for key in ('entry_x','entry_price','exit_price','realized_pnl','r_multiple','volume'):
            self.assertNotIn(key,meta)

    def test_html_contains_only_signal_marker_and_distinct_ai_filter(self):
        renderer=load_renderer({})
        page=adapt_html(renderer['_html']([],dict(page_title='候选',coverage_note='候选',
            footer_scope='候选',source_label='Stage254',source_warning='非成交',episode_scope='all')))
        controller=page.rsplit('<script>',1)[1]
        self.assertIn('is_ai_primary_block',controller)
        self.assertIn('ai_pool_disallowed',controller)
        self.assertIn('信号参考（非成交）',controller)
        self.assertNotIn('m.entry_',controller)
        self.assertNotIn('m.exit_',controller)
        self.assertNotIn('realized_pnl',controller)
        self.assertNotIn('r_multiple',controller)
        self.assertNotIn("type:'rect'",controller)
        self.assertIn("data-period=\"day30\" checked",page)
        self.assertIn("data-period=\"daily\" checked",page)


if __name__=='__main__':unittest.main()
