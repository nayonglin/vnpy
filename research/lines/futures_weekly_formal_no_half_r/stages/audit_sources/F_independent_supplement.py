from pathlib import Path
import json,hashlib,pandas as pd
ROOT=Path('/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian');L=ROOT/'research/lines/futures_weekly_formal_no_half_r';OUT=L/'outputs';P=OUT/'F_attempt016';A=OUT/'stage007_independent_review/F_audit.json'
w=pd.read_csv(P/'weekly_bars.csv');c=pd.read_csv(P/'entry_candidates.csv');bad=[];maxr=0
for r in c.itertuples():
 g=w.loc[w.vt_symbol.eq(r.contract_vt_symbol)&w.week_end.le(r.date)].sort_values('week_end');q=g.tail(41).close.to_numpy()
 if len(q)<41 or g.week_end.iloc[-1]!=r.date:bad.append((r.candidate_index,'date_or_readiness'));continue
 for n,v in [(10,r.ma_mid_value),(20,r.ma_long_value)]:maxr=max(maxr,abs(float(q[-n:].mean())-v))
 for n,v in [(10,r.ma_mid_prev_value),(20,r.ma_long_prev_value)]:maxr=max(maxr,abs(float(q[-n-1:-1].mean())-v))
x=json.loads(A.read_text());x['independent_candidate_weekly_MA']={'candidate_rows':len(c),'fresh_or_readiness_bad':bad,'max_MA10_MA20_current_previous_residual':maxr}
e=json.loads((OUT/'E_attempt009/actual_strategy_settings.json').read_text())[0]['actual'];f=json.loads((P/'actual_strategy_settings.json').read_text())[0]['actual'];keys=['ma_short','ma_mid','ma_long','ma_extra_long','rsi_length','warmup_days','array_manager_size_floor','research_exact_array_manager_size','risk_ratio_of_total_assets','risk_ratio_breakout','risk_ratio_volume_open_interest_surge','risk_ratio_open_interest_surge','risk_ratio_open_interest_decline','max_concurrent_positions','max_position_size','rollover_delay_trading_days','rollover_shape_history_mode','stage827_intraday_c2_stop_r','stage827_intraday_c2_confirm_r','stage847_stop_retry_r','stage847_max_retries']
x['frozen_numeric_settings']={k:f[k] for k in keys};x['frozen_numeric_settings_E_mismatches']={k:[e[k],f[k]] for k in keys if e[k]!=f[k]}
original=set(pd.read_csv(e['product_universe_csv_path']).product_vt_symbol);old=[z for z in x['per_product'] if z['product'] in original];new=[z for z in x['per_product'] if z['product'] not in original];x['coupled_account_product_groups']={'original19_F_mtm_net':sum(z['net_mtm_pnl'] for z in old),'new72_F_mtm_net':sum(z['net_mtm_pnl'] for z in new),'E_original19_mtm_net':x['E']['end_equity']-150000,'F_minus_E':x['F']['end_equity']-x['E']['end_equity'],'boundary':'Coupled account ledger decomposition only, not independently funded product marginal alpha attribution.'}
x['checks']['candidate_weekly_MA']=not bad and maxr<1e-8;x['checks']['frozen_numeric_settings']=not x['frozen_numeric_settings_E_mismatches'];x['verdict']='PASS_RESEARCH_ACCOUNTING_WITH_LIMITATIONS' if all(x['checks'].values()) else 'REJECT_UNRESOLVED_AUDIT_CHECKS'
x['audit_scripts']={}
for src,name in [('/private/tmp/stage007_F_independent_audit.py','F_independent_audit.py'),('/private/tmp/stage007_F_supplement.py','F_independent_supplement.py')]:
 target=A.parent/name;target.write_bytes(Path(src).read_bytes());x['audit_scripts'][str(target)]=hashlib.sha256(target.read_bytes()).hexdigest()
A.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:x[k] for k in ['verdict','checks','quote_capacity_diagnostic','warmup','coupled_account_product_groups','terminal_open_positions']},ensure_ascii=False,indent=2))
