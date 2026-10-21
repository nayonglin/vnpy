"""One synthetic group: ordinary anchors,25h,empty/missing and expiry."""
from copy import deepcopy
from datetime import datetime
import importlib.util
from pathlib import Path
import unittest
from zoneinfo import ZoneInfo

TOOLS=Path(__file__).resolve().parent

class SessionTiny(unittest.TestCase):
    def test_concrete_dates_do_not_guess_missing_templates_or_last_day_hours(self):
        path=TOOLS/'stage353_regular_sessions.py'
        self.assertTrue(path.exists(),'new pure session expander missing')
        spec=importlib.util.spec_from_file_location('fixture353',path)
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        cal={d:True for d in ['2026-10-16','2026-10-19','2026-10-20','2026-10-21']}
        anchors={'2026-10-19':'2026-10-16','2026-10-20':'2026-10-19','2026-10-21':'2026-10-20'}
        evidence=dict(policy='operational_regular_schedule',source_receipt={'350':'synthetic-approved'})
        expire=datetime(2026,12,1,15,tzinfo=ZoneInfo('Asia/Shanghai')).timestamp()
        meta=dict(symbol='SHFE.cu2612',metadata_received=True,day=[['09:00:00','15:00:00']],
            night=[['21:00:00','25:00:00']],expire_datetime=expire,source_receipt={'321':'synthetic'})
        kwargs=dict(calendar=cal,night_anchors=anchors,evidence=evidence)
        before=deepcopy((meta,kwargs))
        out=m.expand_sessions(meta,'2026-10-19',**kwargs)
        self.assertEqual(out['state'],'operational_regular_schedule')
        self.assertEqual(out['first_open'],'2026-10-16T21:00:00+08:00')
        self.assertEqual(out['intervals'][0]['end'],'2026-10-17T01:00:00+08:00')
        self.assertEqual(out['session_end'],'2026-10-19T15:00:00+08:00')
        self.assertNotIn('source_completed_at',out);self.assertNotIn('T0',out)
        self.assertEqual((meta,kwargs),before)
        third=m.expand_sessions(meta,'2026-10-21',**kwargs)
        self.assertEqual(third['first_open'],'2026-10-20T21:00:00+08:00')
        bond=dict(meta,symbol='CFFEX.T2612',night=[],day=[['09:30:00','11:30:00'],['13:00:00','15:15:00']])
        out=m.expand_sessions(bond,'2026-10-20',**kwargs)
        self.assertEqual(out['night_state'],'observed_empty')
        self.assertEqual(out['first_open'],'2026-10-20T09:30:00+08:00')
        self.assertEqual(out['session_end'],'2026-10-20T15:15:00+08:00')
        for bad in [dict(meta,metadata_received=False),dict(meta,source_receipt=None),dict(meta,day=[]),
                    dict(meta,expire_datetime=None),dict(meta,night=None),
                    dict(meta,day=[['09:00:00','11:30:00'],['11:00:00','15:00:00']])]:
            result=m.expand_sessions(bad,'2026-10-19',**kwargs)
            self.assertEqual(result['state'],'unknown');self.assertIsNone(result['first_open'])
        missing=dict(meta);missing.pop('night')
        self.assertEqual(m.expand_sessions(missing,'2026-10-19',**kwargs)['night_state'],'unknown')
        self.assertEqual(m.expand_sessions(meta,'2026-10-19',**dict(kwargs,calendar=dict(cal,**{'2026-10-17':True})))['state'],'unknown')
        expiry=datetime(2026,10,19,15,tzinfo=ZoneInfo('Asia/Shanghai')).timestamp()
        last=dict(bond,expire_datetime=expiry)
        self.assertIn('last_day_override_missing',m.expand_sessions(last,'2026-10-19',**kwargs)['reasons'])
        after=m.expand_sessions(last,'2026-10-20',**kwargs)
        self.assertEqual(after['state'],'expired');self.assertEqual(after['intervals'],[])
        override=dict(day=[['09:30:00','11:30:00']],night=[],source_receipt={'official':'synthetic-last-day-rule'})
        out=m.expand_sessions(last,'2026-10-19',**kwargs,last_day_override=override)
        self.assertEqual(out['session_end'],'2026-10-19T11:30:00+08:00')
        self.assertEqual(out['expiry_state'],'last_day_override_applied')

if __name__=='__main__':unittest.main()
