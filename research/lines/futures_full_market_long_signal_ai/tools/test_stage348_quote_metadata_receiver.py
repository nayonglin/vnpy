"""One synthetic transmission group; no Tq import, price, source or account read."""
import asyncio
import importlib.util
from pathlib import Path
import unittest


class QuoteMetadataTiny(unittest.TestCase):
    def test_metadata_without_ticks_retired_partial_and_explicit_sim(self):
        path=Path(__file__).with_name('stage348_quote_metadata_receiver.py')
        spec=importlib.util.spec_from_file_location('tiny348',path)
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        symbols=['SHFE.fu2701','CZCE.AP610']
        complete=dict(instrument_id=symbols[0],exchange_id='SHFE',ins_class='FUTURE',
            trading_time=dict(day=[['09:00:00','15:00:00']],night=[['21:00:00','25:00:00']]),
            delivery_year=2027,delivery_month=1,expire_datetime=1798675200.,
            price_tick=1.,volume_multiple=10,datetime='')

        class API:
            def __init__(self,quotes,fail=False):
                self.quotes=quotes;self.fail=fail;self.calls=0;self.waits=0
                self.loop=asyncio.new_event_loop()
            def create_task(self,coro):return self.loop.create_task(coro)
            def get_quote_list(self,requested):
                assert self.loop.is_running(), 'must not use synchronous quote datetime readiness'
                self.calls+=1;assert requested==symbols
                if self.fail:raise TimeoutError('secret-token')
                return self.quotes
            def wait_update(self,deadline):
                self.waits+=1;self.loop.run_until_complete(asyncio.sleep(0))
                return False

        for retired in (False,True):
            q2=dict(complete,instrument_id=symbols[1],exchange_id='CZCE',delivery_year=2026,delivery_month=10,
                    trading_time=dict(day=[['09:00:00','15:00:00']],night=[]))
            if retired:q2.update(delivery_year=0,price_tick=float('nan'),trading_time=dict(day=[],night=[]))
            api=API([complete,q2]);report=m.new_report(symbols,'tqsdk/synthetic',{symbols[0]:'SHFE.FU.202701'})
            m.capture_metadata(api,symbols,report,secrets=['secret-token'])
            self.assertEqual(api.calls,1);self.assertEqual(report['requests']['quote_list'],1)
            self.assertEqual(report['items'][symbols[0]]['status'],'metadata_ready')
            row=report['items'][symbols[0]]
            self.assertEqual(row['fields']['trading_time.night']['value'][0][1],'25:00:00')
            self.assertEqual(row['fields']['delivery_year']['value'],2027)
            self.assertEqual(row['fields']['expire_datetime']['value'],1798675200.)
            self.assertIsNone(row['source_completed_at']);self.assertFalse(row['model_input_eligible'])
            self.assertEqual(report['items'][symbols[1]]['prior_identity_state'],'unknown')
            self.assertEqual(report['status'],'partial' if retired else 'completed')
            if retired:self.assertEqual(report['items'][symbols[1]]['fields']['delivery_year']['reason'],'sdk_default_or_invalid')
            api.loop.close()
        api=API([],True);report=m.new_report(symbols,'tqsdk/synthetic',{})
        m.capture_metadata(api,symbols,report,secrets=['secret-token'])
        self.assertEqual(api.calls,1);self.assertEqual(len(report['items']),2)
        self.assertEqual(report['status'],'partial');self.assertNotIn('secret-token',str(report))
        self.assertTrue(all(v['status']=='unknown' for v in report['items'].values()));api.loop.close()

        calls=[]
        class Sim:pass
        def auth(username,password):return ('auth',username,password)
        def factory(account,**kw):calls.append((account,kw));return object()
        m.connect_explicit(factory,auth,Sim,'not-real','not-real')
        self.assertIsInstance(calls[0][0],Sim)
        self.assertEqual({k:calls[0][1][k] for k in ('debug','disable_print','web_gui')},
                         dict(debug=False,disable_print=True,web_gui=False))


if __name__=='__main__':unittest.main()
