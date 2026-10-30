import importlib.util,json,tempfile,unittest
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest.mock import patch

def subject(test):
 test.assertIsNotNone(importlib.util.find_spec('stage009_finalize'),'new Stage009 finalizer missing')
 import stage009_finalize as m
 return m

def fixtures(m):
 ledgers={};summary=[];pairs=[]
 for start in m.STARTS:
  eligible=start!='2026-01-01';cohort='January' if start[5:7]=='01' else 'June'
  for arm in ['A','C']:
   for suffix,mode,extra in [('_idle','idle',0),('_R','reserve',10000)]:
    variant=arm+suffix;metrics=dict(initial_capital=300000.,end_equity=310000.+extra,net_pnl=10000.+extra,total_return_pct=(10000.+extra)/300000*100,max_dd_pct=-15. if mode=='reserve' else -20.,sharpe=.8 if mode=='reserve' else .7,total_slippage=200.,total_commission=0.,modeled_fill_count=12,actual_start=start,actual_end=m.END,trading_days=200,trading_end_equity=180000.+extra,reserve_end_balance=130000.,total_transferred=20000. if mode=='reserve' else 0.,nonpositive_total_equity_days=0,nonpositive_trading_equity_days=0)
    if mode=='idle':metrics.update(trading_end_equity=160000.,reserve_end_balance=150000.)
    ledger=dict(start=start,end=m.END,arm=arm,variant=variant,mode=mode,source_path='/actual/'+variant,metrics=metrics,risk=dict(trading_margin_peak_pct=60.,total_margin_peak_pct=30.,trading_margin_over100_days=0,total_margin_over100_days=0,trading_margin_undefined_days=0,total_margin_undefined_days=0),accounting=dict(complete_contract_rounds=dict(count=5,wins=2,losses=3,flat=0,win_rate_pct=40.,average_win=2000.,average_loss_abs=1000.,payoff_ratio=2.,profit_factor=4/3,closed_net_pnl=1000.),open_round_net_mtm=metrics['net_pnl']-1000.,open_round_count=1),transfer_event_count=1 if mode=='reserve' else 0)
    ledgers[(start,variant)]=ledger;summary.append(dict(start=start,variant=variant,arm=arm,mode=mode,cohort=cohort,vote_eligible=eligible,observation_only=not eligible,**metrics))
   idle=ledgers[(start,arm+'_idle')]['metrics'];reserve=ledgers[(start,arm+'_R')]['metrics'];p=dict(start=start,arm=arm,cohort=cohort,vote_eligible=eligible,observation_only=not eligible,equity_gate=True,dd_gate=True,sharpe_gate=True,three_gate_pass=True)
   for prefix,metrics in [('idle',idle),('reserve',reserve)]:
    for key in ['end_equity','total_return_pct','max_dd_pct','sharpe']:p[prefix+'_'+key]=metrics[key]
   pairs.append(p)
 return ledgers,summary,pairs

class FinalizerTests(unittest.TestCase):
 def test_exact46_new_and92_cache_inventory_no_partial(self):
  m=subject(self);jobs={s+'|'+a:dict(status='validated',reused=False) for s in m.STARTS for a in ['A','C']};f=dict(starts=list(m.STARTS),cutoff=m.END,planned_financial_replays=46);reg=dict(jobs=jobs,financial_replays_started=46,financial_engine_batch_complete=True);cache={s+'|'+v for s in m.STARTS for v in m.VARIANTS};m.require_inventory(f,reg,set(jobs),cache)
  for bad in [dict(reg,financial_replays_started=42),dict(reg,jobs=dict(list(jobs.items())[:-1]))]:
   with self.assertRaises(ValueError):m.require_inventory(f,bad,set(jobs),cache)
  with self.assertRaises(ValueError):m.require_inventory(f,reg,set(jobs),set(list(cache)[:-1]))
 def test92_rows_same300k_and46_pairs_with_observation_no_vote(self):
  m=subject(self);l,s,p=fixtures(m);m.require_report_rows(l,s,p)
  bad=[dict(x) for x in s];bad[0]['initial_capital']=150000
  with self.assertRaises(ValueError):m.require_report_rows(l,bad,p)
  bad=[dict(x) for x in p];bad[-1]['vote_eligible']=True
  with self.assertRaises(ValueError):m.require_report_rows(l,s,bad)
  with self.assertRaises(ValueError):m.require_report_rows(l,s,p[:-1]+[p[0]])
 def test_equity_ties_cannot_be_three_gate_pass(self):
  m=subject(self);l,s,p=fixtures(m);key=(m.STARTS[0],'A_R');l[key]['metrics'].update(end_equity=310000.,total_return_pct=10000./300000*100);s[1].update(end_equity=310000.,total_return_pct=10000./300000*100);p[0].update(reserve_end_equity=310000.,reserve_total_return_pct=10000./300000*100)
  with self.assertRaises(ValueError):m.require_report_rows(l,s,p)
 def test_final_review_and_five_figures_require_exact_locked_sha_scope(self):
  m=subject(self);r=dict(status='PASS_WITH_LIMITATIONS',P0=0,P1=0,P2=0,failures=0,freeze_sha256='f',arm_windows=46,paired_windows=46,independent_starts=23,report_comparison_sha256='c');m.require_final_review(r,'f','c')
  for key,value in [('paired_windows',23),('P1',1),('report_comparison_sha256','old')]:
   bad=dict(r);bad[key]=value
   with self.assertRaises(ValueError):m.require_final_review(bad,'f','c')
  with tempfile.TemporaryDirectory() as td:
   folder=Path(td);mapping={}
   for name in m.FIGURES:(folder/name).write_bytes(name.encode());mapping[str((folder/name).resolve())]=m.sha(folder/name)
   visual=dict(independent_review_sha256='locked',reviewed_figures_sha256=mapping);m.require_visual(visual,'locked',folder)
   with self.assertRaises(ValueError):m.require_visual(visual,'drifted',folder)
   del mapping[next(iter(mapping))]
   with self.assertRaises(ValueError):m.require_visual(visual,'locked',folder)
 def test_reserve_cache_metrics_match_independent_total_not_raw(self):
  m=subject(self);self.assertTrue(hasattr(m,'require_independent_metrics'),'independent total metric acceptance missing');ledger=fixtures(m)[0][(m.STARTS[0],'A_R')];metrics=dict(ledger['metrics'],total_trade_count=ledger['metrics']['modeled_fill_count'],rounds=ledger['accounting']['complete_contract_rounds'],open_round_net_mtm=ledger['accounting']['open_round_net_mtm']);risk=dict(configured_margin_max_trading_pct=60.,configured_margin_over100_trading_days=0,configured_margin_undefined_trading_days=0,configured_margin_max_total_pct=30.,configured_margin_over100_total_days=0,nonpositive_total_equity_days=0);receipt=dict(metrics=metrics,risk=risk)
  m.require_independent_metrics(ledger,receipt);bad=dict(receipt,metrics=dict(metrics,end_equity=160000.))
  with self.assertRaises(ValueError):m.require_independent_metrics(ledger,bad)
 def test_real_summary_may_omit_cohort_but_conflicting_cohort_is_rejected(self):
  m=subject(self);l,s,p=fixtures(m)
  for row in s:row.pop('cohort')
  m.require_report_rows(l,s,p);s[0]['cohort']='June'
  with self.assertRaises(ValueError):m.require_report_rows(l,s,p)
 def test_comparison_requires_exact_four_variant_names_not_numeric_count(self):
  m=subject(self);self.assertTrue(hasattr(m,'require_comparison'),'real comparison schema gate missing')
  doc=dict(expected_new_engines=46,arm_windows=46,paired_windows=46,summary_rows=92,independent_starts=23,complete_pairs_per_arm=22,observation_per_arm=1,total_daily_points=141996,variants=list(m.VARIANTS),five_figures=list(m.FIGURES),starts=list(m.STARTS),cutoff=m.END,total_initial_capital=300000,engine_initial_capital=150000,reserve_initial_capital=150000,freeze_sha256='f',source_head='h',financial_source_head='h',promotion_decision='NO_PROMOTION');m.require_comparison(doc,'f','h')
  for variants in [4,list(m.VARIANTS[:-1]),['A_idle','A_R','C_idle','C_idle']]:
   bad=dict(doc,variants=variants)
   with self.assertRaises(ValueError):m.require_comparison(bad,'f','h')
 def test_checkpoint_hash_preserves_frozen_integer_amount_serialization(self):
  m=subject(self);self.assertTrue(hasattr(m,'checkpoint_identity'),'literal freeze checkpoint identity missing')
  from stage009_contract import checkpoint_key
  freeze=dict(source_head='a'*40,cutoff=m.END,engine_initial_capital=150000,reserve_initial_capital=150000,total_initial_capital=300000)
  self.assertEqual(m.checkpoint_identity(freeze,'f'*64,'A','2015-01-01'),checkpoint_key(freeze,'f'*64,'A','2015-01-01'))
  altered=dict(freeze,engine_initial_capital=150000.)
  self.assertEqual(m.checkpoint_identity(altered,'f'*64,'A','2015-01-01'),checkpoint_key(altered,'f'*64,'A','2015-01-01'))
 def test_exact_source_bytes_no_tolerance(self):
  m=subject(self)
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'source';p.write_text('1.00');book=m.SourceBook();book.add(p);p.write_text('1.01')
   with self.assertRaises(ValueError):book.verify()
 def test_chinese_window_separates_idle_old_run_and_funds(self):
  m=subject(self);l,_,_=fixtures(m);start=m.STARTS[0];text=m.render_window(l[(start,'A_idle')],l[(start,'A_R')],dict(started_at='new_start',completed_at='new_end'),dict(started_at='old_start',completed_at='old_end'),Path('/receipt'),'rsha','csha',datetime(2026,10,30,16,0,tzinfo=ZoneInfo('Asia/Shanghai')))
  for word in ['旧账本','300,000','150,000','备用','内部转账','new_start','old_start','完整周期胜率','平均盈亏比','Profit Factor','末未平','rsha','csha','不投票' if start=='2026-01-01' else '参与投票']:self.assertIn(word,text)
 def test_atomic_manifest_last_no_overwrite_and_failed_marker_rolls_back(self):
  m=subject(self)
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);records={f'{i:02}.md':'中文' for i in range(46)};m.atomic_publish(root/'windows',root/'stage.md',root/'manifest.json',records,'中文总stage',{})
   before=(root/'manifest.json').read_bytes()
   with self.assertRaises(ValueError):m.atomic_publish(root/'windows',root/'stage.md',root/'manifest.json',records,'改写',{})
   self.assertEqual((root/'manifest.json').read_bytes(),before)
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);real=__import__('os').link
   def fail_marker(src,dst):
    if Path(dst).name=='manifest.json':raise OSError('marker failure')
    return real(src,dst)
   with patch('stage009_finalize.os.link',side_effect=fail_marker):
    with self.assertRaises(OSError):m.atomic_publish(root/'windows',root/'stage.md',root/'manifest.json',{f'{i:02}.md':'中文' for i in range(46)},'总stage',{})
   self.assertFalse((root/'windows').exists());self.assertFalse((root/'stage.md').exists());self.assertFalse((root/'manifest.json').exists())

if __name__=='__main__':unittest.main()
