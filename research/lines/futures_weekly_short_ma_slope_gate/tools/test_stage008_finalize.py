import unittest,tempfile,json,hashlib
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest.mock import patch
from stage008_finalize import STARTS,FIGURES,SourceBook,require_inventory,require_final_review,require_visual,require_report_rows,render_window,atomic_publish

def rows():
 summary=[];pairs=[];ledgers={}
 for i,start in enumerate(STARTS):
  eligible=start!='2026-01-01';cohort='January' if start[5:7]=='01' else 'June'
  for arm in ['A','C']:
   m=dict(initial_capital=150000,end_equity=200000+i*1000+(10000 if arm=='C' else 0),net_pnl=50000+i*1000+(10000 if arm=='C' else 0),total_return_pct=((200000+i*1000+(10000 if arm=='C' else 0))/150000-1)*100,max_dd_pct=-35 if arm=='C' else -40,sharpe=.6 if arm=='C' else .5,total_slippage=100,modeled_fill_count=20,actual_start=start,actual_end='2026-10-29',trading_days=200)
   d=dict(start=start,arm=arm,reused=start in ['2015-01-01','2020-01-01'],source_path='/local/run',metrics=m,window=dict(cohort=cohort,vote_eligible=eligible,observation_only=not eligible,actual_first_day=start,trading_days=200),accounting=dict(complete_contract_rounds=dict(count=10,wins=4,losses=5,flat=1,win_rate_pct=40,average_win=1000,average_loss_abs=500,payoff_ratio=2,profit_factor=1.6,closed_net_pnl=m['net_pnl']),open_round_net_mtm=0,open_round_count=0),risk=dict(actual_margin_to_equity_max_pct=80,actual_margin_over100_days=0))
   ledgers[(start,arm)]=d;summary.append(dict(start=start,arm=arm,cohort=cohort,vote_eligible=eligible,observation_only=not eligible,**m))
  a=ledgers[(start,'A')]['metrics'];c=ledgers[(start,'C')]['metrics'];pairs.append(dict(start=start,cohort=cohort,vote_eligible=eligible,observation_only=not eligible,A_end_equity=a['end_equity'],C_end_equity=c['end_equity'],A_return_pct=a['total_return_pct'],C_return_pct=c['total_return_pct'],A_max_dd_pct=-40,C_max_dd_pct=-35,A_sharpe=.5,C_sharpe=.6,equity_gate=True,dd_gate=True,sharpe_gate=True,three_gate_pass=True))
 return ledgers,summary,pairs

class FinalizerTests(unittest.TestCase):
 def test_all46_and_exact22votes_required(self):
  jobs={s+'|'+a:dict(status='validated',reused=s in ['2015-01-01','2020-01-01']) for s in STARTS for a in ['A','C']};f=dict(starts=list(STARTS),cutoff='2026-10-29');r=dict(jobs=jobs,financial_replays_started=42,financial_engine_batch_complete=True)
  require_inventory(f,r,set(jobs),set(jobs))
  bad=dict(r,jobs=dict(list(jobs.items())[:-1]))
  with self.assertRaises(ValueError):require_inventory(f,bad,set(jobs),set(jobs))
  bad=dict(r,jobs={k:dict(v,status='running') if k==next(iter(jobs)) else v for k,v in jobs.items()})
  with self.assertRaises(ValueError):require_inventory(f,bad,set(jobs),set(jobs))
 def test_failed_independent_or_wrong_final_binding_fails(self):
  r=dict(status='PASS_WITH_LIMITATIONS',P0=0,P1=0,P2=0,failures=0,freeze_sha256='a',arm_windows=46,paired_windows=23,report_comparison_sha256='b')
  require_final_review(r,'a','b')
  for field,value in [('P1',1),('arm_windows',45),('freeze_sha256','x'),('report_comparison_sha256','x')]:
   bad=dict(r);bad[field]=value
   with self.assertRaises(ValueError):require_final_review(bad,'a','b')
 def test_source_hash_no_float_or_byte_tolerance(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'x';p.write_text('1.0000000000');b=SourceBook();b.add(p);p.write_text('1.0000000001')
   with self.assertRaises(ValueError):b.verify()
 def test_visual_requires_exact_five_names_and_locked_review(self):
  with tempfile.TemporaryDirectory() as td:
   d=Path(td);mapping={}
   for n in FIGURES:(d/n).write_bytes(n.encode());mapping[str((d/n).resolve())]=hashlib.sha256(n.encode()).hexdigest()
   v=dict(independent_review_sha256='locked',reviewed_figures_sha256=mapping);require_visual(v,'locked',d)
   with self.assertRaises(ValueError):require_visual(v,'changed',d)
   del mapping[next(iter(mapping))]
   with self.assertRaises(ValueError):require_visual(v,'locked',d)
 def test_pairs_never_use26Jan_as_vote_or_allow_duplicate(self):
  ledgers,summary,pairs=rows();require_report_rows(ledgers,summary,pairs)
  bad=[dict(x) for x in pairs];bad[-1]['vote_eligible']=True
  with self.assertRaises(ValueError):require_report_rows(ledgers,summary,bad)
  bad=[dict(x) for x in summary];bad[-1]=dict(bad[0])
  with self.assertRaises(ValueError):require_report_rows(ledgers,bad,pairs)
 def test_window_chinese_records_reuse_and_metrics_not_fake_new_run(self):
  d=rows()[0][('2015-01-01','C')];job=dict(path='/local/run',reused=True);text=render_window(d,job,dict(started_at='old-start',completed_at='old-end'),Path('/local/receipt.json'),'rsha','csha',datetime(2026,10,30,15,0,tzinfo=ZoneInfo('Asia/Shanghai')))
  for part in ['复用','old-start','old-end','期末权益','总滑点','完整周期胜率','平均盈亏比','Profit Factor','末未平','rsha','csha']:self.assertIn(part,text)
 def test_atomic_publisher_does_not_overwrite_and_rolls_back_before_commit_marker(self):
  with tempfile.TemporaryDirectory() as td:
   s=Path(td);windows={'20150101_A_result.md':'window'};stage=s/'stage.md';manifest=s/'delivery.json';source=s/'frozen';source.write_text('frozen');sources={str(source):hashlib.sha256(b'frozen').hexdigest()};atomic_publish(s/'windows',stage,manifest,windows,'stage',sources)
   self.assertTrue(manifest.exists());before=manifest.read_bytes()
   with self.assertRaises(ValueError):atomic_publish(s/'windows',stage,manifest,windows,'changed',{})
   self.assertEqual(manifest.read_bytes(),before)
  with tempfile.TemporaryDirectory() as td:
   s=Path(td);real_link=__import__('os').link
   def link(src,dst):
    if Path(dst).name=='delivery.json':raise OSError('commit marker failure')
    return real_link(src,dst)
   with patch('stage008_finalize.os.link',side_effect=link):
    with self.assertRaises(OSError):atomic_publish(s/'windows',s/'stage.md',s/'delivery.json',{'w.md':'w'},'stage',{})
   self.assertFalse((s/'windows').exists());self.assertFalse((s/'stage.md').exists());self.assertFalse((s/'delivery.json').exists())
if __name__=='__main__':unittest.main()
