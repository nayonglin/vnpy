"""Finite418 current-state resume and next-day delegation to unchanged325.

No market receiver, account initialization, model fit, scheduler or CLI trading.
The CLI below can only prepare and restore two existing contexts read-only.
"""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime,timezone
from functools import lru_cache
import argparse,hashlib,importlib.util,json,sys
from pathlib import Path

LINE=Path(__file__).resolve().parent.parent
SCOPE=LINE/'outputs/stage418_next_daily_scope/scope.json'
SCOPE_SHA='69cbc7ff9ff16bb0b46ec3704f6add980c33a4777f96eea4c353579ee117d9da'
OUT=LINE/'outputs/stage421_daily_pair_continuation'

def now():return datetime.now(timezone.utc).isoformat()
def canonical(o):return json.dumps(o,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def digest(o):return hashlib.sha256(canonical(o)).hexdigest()
def binding(path):
 p=Path(path).resolve();b=p.read_bytes();return {'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def bound(b):
 p=Path(b['path'])
 if p.is_symlink() or not p.is_file():raise ValueError('bound regular existing file required')
 raw=p.read_bytes()
 if len(raw)!=b['bytes'] or hashlib.sha256(raw).hexdigest()!=b['sha256']:raise ValueError('binding bytes/SHA mismatch: '+str(p))
 return raw
def value(b):return json.loads(bound(b))
def write(path,o):
 p=Path(path)
 with p.open('x') as f:json.dump(o,f,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False);f.write('\n')
 return binding(p)
def scope():
 b={'path':str(SCOPE),'bytes':18013,'sha256':SCOPE_SHA};o=value(b)
 if o['schema']!='stage418_bounded_next_daily_scope_v1' or not o['implementation_authorized']:raise ValueError('exact418 implementation scope required')
 return o,b
@lru_cache(maxsize=1)
def profiles():
 p=LINE/'tools/stage376_shared_frozen_profiles.py'
 if binding(p)['sha256']!='0a9edeb45907f9542299b4afee9a718c94b373c16e41349ce0c43d588a0ca910':raise ValueError('unchanged376 required')
 previous=sys.dont_write_bytecode;sys.dont_write_bytecode=True
 try:
  s=importlib.util.spec_from_file_location('stage421_original376',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
 finally:sys.dont_write_bytecode=previous

def journal_tail(path,identity,expected=None):
 """Read an existing original321 stream; never creates/repairs a journal."""
 p=Path(path)
 if p.is_symlink() or not p.is_dir() or not (p/'objects').is_dir() or (p/'objects').is_symlink():raise ValueError('original existing journal/objects required')
 for f in ['policy_identity.json','journal.jsonl']:
  if not (p/f).is_file() or (p/f).is_symlink():raise ValueError('original existing journal files required')
 policy=hashlib.sha256(canonical(identity)+b'\n').hexdigest()
 metadata={'schema':'stage321_local_journal_v1','policy_identity':identity,'policy_sha256':policy}
 if (p/'policy_identity.json').read_bytes()!=canonical(metadata)+b'\n':raise ValueError('original journal policy differs')
 raw=(p/'journal.jsonl').read_bytes()
 if not raw.endswith(b'\n'):raise ValueError('torn journal index')
 entries=[json.loads(s) for s in raw.splitlines()];previous='0'*64;last=None;seen=set()
 for i,e in enumerate(entries):
  content={k:v for k,v in e.items() if k!='entry_hash'}
  if (e['sequence']!=i or e['previous_entry_hash']!=previous or e['policy_sha256']!=policy or e['key'] in seen or hashlib.sha256(canonical(content)+b'\n').hexdigest()!=e['entry_hash']):raise ValueError('journal chain/policy changed')
  time=datetime.fromisoformat(e['recorded_at'])
  if last is not None and time<last:raise ValueError('journal clock regressed')
  last=time;previous=e['entry_hash'];seen.add(e['key'])
 if not entries:raise ValueError('nonempty original journal required')
 result={'path':str(p),'index':binding(p/'journal.jsonl'),'policy':binding(p/'policy_identity.json'),'tail':entries[-1],'entries':len(entries)}
 if expected is not None and result!=expected:raise ValueError('journal advanced or changed since accepted resume manifest; no automatic reentry')
 return result

def _object(journal,receipt):
 p=Path(journal)/'objects'/(receipt['payload_sha256']+'.json');raw=p.read_bytes()
 if p.is_symlink() or hashlib.sha256(raw).hexdigest()!=receipt['payload_sha256']:raise ValueError('original321 object digest changed')
 o=json.loads(raw)
 if canonical(o)+b'\n'!=raw:raise ValueError('original321 canonical object changed')
 return o

def restore_checkpoint(item,*,scenario,account_id,paper):
 plain=value(item)
 restored=paper.restore_state({'schema':paper.SCHEMA,'state':plain,'sha256':digest(plain)})
 if restored['scenario']!=scenario or restored['account_id']!=account_id:raise ValueError('own original scenario/account crossed')
 return restored

def prepare_resume(pointer_binding,accepted416_binding,output):
 frozen,sb=scope();ptr=value(pointer_binding);accepted=value(accepted416_binding)
 decision=value(frozen['previous']['accepted417'])
 if pointer_binding!=frozen['previous']['pointers'] or accepted416_binding!=decision['evidence']['review416'] or accepted['status']!='accepted_actual_pair_with_explicit_acquisition_deviation':raise ValueError('exact417 pointers/accepted416 required')
 terminal_b=decision['evidence']['actual415'];terminal=value(terminal_b)
 if terminal['status']!='completed' or not terminal['same_composed_unchanged']:raise ValueError('completed original415 required')
 p=profiles();rows={}
 base_env=value(ptr['profiles']['baseline']['own_original_initialization'])
 kernel_sources=base_env['kernel_sources']
 for name,b in kernel_sources.items():
  bound(b)
  if b['sha256']!=p.helper().KERNEL_SHA[name]:raise ValueError('original kernel changed')
 for name,info in ptr['profiles'].items():
  envelope=value(info['own_original_initialization']);event=envelope['event']
  profile=p.make_profile(value(info['model']),value(info['scaler']),info['model'],info['scaler'],frozen_at=info['model_T0'],candidate=p.BASELINE if name=='baseline' else p.CANDIDATE,clock_contract=value(frozen['full_inputs_unchanged']['clock_contract']))
  if profile['policy_identity']!=info['policy_identity'] or event['recorded_at']!=info['T_init'] or event['kind']!='paper_state_initialized':raise ValueError('original profile/init metadata changed')
  journal=journal_tail(info['own_original_journal'],info['policy_identity'])
  entries=[json.loads(s) for s in Path(journal['index']['path']).read_text().splitlines()]
  if entries[0]!=event or len(entries)!=7 or entries[-2]['kind']!='decision_proposal' or entries[-1]['kind']!='decision_classification':raise ValueError('exact accepted first415 tail required')
  proposal=_object(journal['path'],entries[-2]);classification=_object(journal['path'],entries[-1])
  if (classification['active'] is not True or classification['proposal_entry_hash']!=entries[-2]['entry_hash'] or classification['decision_sealed_at']!=entries[-2]['recorded_at'] or proposal['active'] is not False):raise ValueError('complete prior proposal/classification required')
  states={};ids={}
  for scenario,b in info['current_state_checkpoints'].items():
   if b!=terminal['state_checkpoints'][name][scenario]:raise ValueError('must use exact415 current state')
   state=value(b);previous=proposal['candidate_states'][scenario];previous=previous.get('state',previous)
   if state!=previous or state['phase']!='awaiting_D' or state['sealed']['D_index']!=frozen['day']['u_index']:raise ValueError('checkpoint not exact accepted complete proposal')
   if state['account_id']!=terminal['profiles'][name]['account_ids'][scenario]:raise ValueError('original account ID changed')
   states[scenario]=b;ids[scenario]=state['account_id']
  rows[name]={'profile':profile,'T_init':info['T_init'],'initialization_event':event,'initialization_envelope':info['own_original_initialization'],'state_files':states,'account_ids':ids,'journal':journal,'last_complete_proposal':entries[-2],'last_classification':entries[-1]}
 out=Path(output);out.mkdir(parents=True,exist_ok=False)
 manifest={'schema':'stage421_current_resume_manifest_v1','created_at':now(),'scope':sb,'pointers':pointer_binding,'accepted416':accepted416_binding,'accepted417':frozen['previous']['accepted417'],'prior_terminal415':terminal_b,'profiles':rows,'kernel_sources':kernel_sources,'adapter':binding(__file__),'actual_restores':0,'new_accounts':0,'inference':0,'D_execution':0}
 return write(out/'resume_manifest.json',manifest)

def resume_context(resume_manifest_binding,profile_name):
 manifest=value(resume_manifest_binding);frozen,sb=scope()
 if manifest['schema']!='stage421_current_resume_manifest_v1' or manifest['scope']!=sb or manifest['adapter']!=binding(__file__):raise ValueError('frozen421 resume manifest required')
 info=manifest['profiles'][profile_name];p=profiles();c=p.components()
 journal_tail(info['journal']['path'],info['profile']['policy_identity'],info['journal'])
 for b in manifest['kernel_sources'].values():bound(b)
 kernel=p.helper()._load(Path(manifest['kernel_sources']['stage131_contract_choice_kernel.py']['path']),'stage421_original131')
 states={s:restore_checkpoint(b,scenario=s,account_id=info['account_ids'][s],paper=c.paper) for s,b in info['state_files'].items()}
 # Existing files are verified before original ForwardJournal constructor. No append/initialize.
 journal=c.journal.ForwardJournal(info['journal']['path'],info['profile']['policy_identity'])
 context={'profile':info['profile'],'states':states,'journal':journal,'kernel':kernel,'T_init':info['T_init'],'initialization_event':info['initialization_event'],'initialization_envelope':info['initialization_envelope'],'resume_manifest':resume_manifest_binding,'accepted_journal_tail':info['journal']}
 p.validate_context(context)
 journal_tail(info['journal']['path'],info['profile']['policy_identity'],info['journal'])
 return context

def execution_dependencies(resumed_contexts):
 roles=[];unresolved=[];states_hash={}
 for profile,context in resumed_contexts.items():
  states_hash[profile]=digest(context['states'])
  for scenario,s in context['states'].items():
   owners=[('position',str(k),r) for k,r in s['ledger']['positions'].items()]+[('pending',str(r.get('budget_id',i)),r) for i,r in enumerate(s['pending'])]
   for kind,owner,row in owners:
    fields={'anchor_epoch','reference_epoch'} if kind=='pending' else {'epoch'}
    fields|={k for k in ('epoch','anchor_epoch','reference_epoch') if k in row}
    for field in sorted(fields):
     epoch=row.get(field,owner if kind=='position' and field=='epoch' else None)
     item={'profile':profile,'scenario':scenario,'owner_kind':kind,'row_id':owner,'field':field}
     if not isinstance(epoch,str) or not epoch:unresolved.append({**item,'reason':'own_execution_dependency_unknown'})
     else:roles.append({**item,'epoch':epoch})
 return {'schema':'stage421_execution_dependencies_v1','epochs':sorted({r['epoch'] for r in roles}),'roles':roles,'unresolved':unresolved,'complete':not unresolved,'states_sha256':states_hash}

def persist_pair(contexts,invoke,output,provenance):
 """Persist first result before touching second; never reenter an existing run."""
 out=Path(output);out.mkdir(parents=True,exist_ok=False);completed=[];results={}
 write(out/'started.json',{'started_at':now(),**provenance})
 try:
  for name in ('baseline','latest'):
   r=invoke(name,contexts[name]);rb=write(out/(name+'_result.json'),r)
   states={s:write(out/(name+'_'+s+'_state.json'),v) for s,v in r['states'].items()}
   write(out/(name+'_completed.json'),{'result':rb,'states':states,'status':r['status'],'completed_at':now()})
   completed.append(name);results[name]={'result':rb,'states':states,'status':r['status']}
  return write(out/'terminal.json',{'schema':'stage421_pair_terminal_v1','status':'completed','completed_at':now(),'profiles':results,'provenance':provenance,'new_accounts':0,'no_real_orders':True})
 except Exception as error:
  write(out/'failure.json',{'status':'partial_or_failed_no_automatic_retry','completed_models':completed,'error_type':type(error).__name__,'message':str(error),'journals_may_have_appended':True,'finished_at':now(),'instruction':'Preserve all journals/facts/checkpoints. Never rerun pair/reset; explicit root recovery only.'})
  raise

def process_pair_for_u(composed,acceptance_binding,contexts,day_scope_binding,output):
 clock=composed['snapshot'].get('clock') or {}
 if clock.get('source_completed_at') is None or clock.get('D_open_at') is None:
  raise ValueError('known source completion and D-open required before any paired invocation')
 frozen,sb=scope()
 if day_scope_binding!=sb:raise ValueError('only frozen418 finite next day allowed')
 a=value(acceptance_binding);day=frozen['day'];p=profiles();c=p.components();same=p.composed_identity(composed)
 if (a.get('schema')!='stage421_daily_pair_acceptance_v1' or a.get('accepted_by')!='root' or a.get('status')!='accepted' or a.get('execution_authorized') is not True or a.get('day')!=day or a.get('composed_identity')!=same or a.get('clock_domains_sha256')!=digest(composed['clock_domains']) or any(k in a for k in ['completed361','passed362','accepted363'])):raise ValueError('new explicit day acceptance required; no legacyu20 labels')
 evidence=a.get('evidence',{})
 if set(evidence)!={'source_terminal','source_review','root_decision'}:raise ValueError('new source/review/root bindings required')
 for b in evidence.values():value(b)
 authority=value(evidence['root_decision'])
 if (authority.get('schema')!='stage421_root_day_authorization_v1' or authority.get('day')!=day or authority.get('composed_identity')!=same or authority.get('authorized_pair_calls')!=1 or authority.get('execution_authorized') is not True or authority.get('source_terminal')!=evidence['source_terminal'] or authority.get('source_review')!=evidence['source_review']):raise ValueError('explicit root authority for one actual new-day pair required')
 snap=composed['snapshot'];domains=composed['clock_domains'];dates=snap['dates']
 if (snap['u_date']!=day['u_date'] or snap['u_index']!=day['u_index'] or dates[day['u_index']]!=day['u_date'] or dates[day['D_index']]!=day['D_date'] or domains['u_date']!=day['u_date'] or domains['D_date']!=day['D_date'] or domains.get('before_score') is not True or domains.get('score_or_winner_used') is not False):raise ValueError('exact next day/calendar/prescore domains required')
 clock=snap['clock']
 for group,key in [('input_completion','source_completed_at'),('execution_deadline','D_open_at')]:
  if domains[group][key]!=clock[key] or (domains[group]['unknown_epochs'] and clock[key] is not None):raise ValueError('unknown aggregate cannot become known')
 if set(contexts)!={'baseline','latest'}:raise ValueError('two own original contexts required')
 for name,context in contexts.items():
  p.validate_context(context)
  if context['resume_manifest']!=a['resume_manifest']:raise ValueError('accepted current resume manifest mismatch')
  journal_tail(context['accepted_journal_tail']['path'],context['profile']['policy_identity'],context['accepted_journal_tail'])
  if domains['policy']!=context['profile']['clock_contract']:raise ValueError('frozen dual-domain policy changed')
  for state in context['states'].values():
   if state['phase']!='awaiting_D' or state['sealed']['D_index']!=day['u_index']:raise ValueError('must advance own previously sealedD21, no reset/skip')
  complete=clock['source_completed_at']
  if complete is not None and (datetime.fromisoformat(complete)>datetime.now(timezone.utc) or datetime.fromisoformat(context['T_init'])>=datetime.fromisoformat(complete) or datetime.fromisoformat(context['profile']['T_model'])>=datetime.fromisoformat(complete)):raise ValueError('source must be genuinely complete after original freeze/init')
 deps=execution_dependencies(contexts)
 if not deps['complete'] or not set(deps['epochs']).issubset(set(domains['input_completion']['epochs']) & set(domains['execution_deadline']['epochs'])):raise ValueError('both own actual/reference/anchor execution dependencies required')
 accepted=deepcopy(snap);accepted.update(development_only=False,accepted_future_lineage={'schema':'stage421_new_day_lineage_v1','acceptance':acceptance_binding,'composed_identity':same,'clock_domains':deepcopy(domains)})
 def invoke(name,context):
  # Original325 owns current-D advancement then next-u seal and actual proposal timestamps.
  r=c.caller.process_snapshot(accepted,model=context['profile']['engine_model'],scaler=context['profile']['engine_scaler'],journal=context['journal'],policy_identity=context['profile']['policy_identity'],mode='future',states=context['states'],base_kernel=context['kernel'])
  if p.composed_identity(composed)!=same:raise ValueError('shared input mutated; preserve partial state/journal')
  return r
 return persist_pair(contexts,invoke,output,{'scope':sb,'acceptance':acceptance_binding,'composed_identity':same,'dependencies':deps,'no_collection':True,'no_refit':True})

def actual_read_only_resume():
 frozen,sb=scope();pointers=frozen['previous']['pointers'];decision=value(frozen['previous']['accepted417']);out=OUT/'actual_resume_once'
 manifest=prepare_resume(pointers,decision['evidence']['review416'],out)
 contexts={name:resume_context(manifest,name) for name in ('baseline','latest')}
 deps=execution_dependencies(contexts);db=write(out/'execution_dependencies.json',deps)
 summaries={}
 for name,context in contexts.items():
  summaries[name]={'T_model':context['profile']['T_model'],'actual_training_cutoff':context['profile']['actual_training_cutoff'],'T_init':context['T_init'],'journal_tail':context['accepted_journal_tail'],'states':{s:{'account_id':v['account_id'],'phase':v['phase'],'sealed_D_index':v['sealed']['D_index'],'pending':len(v['pending']),'pending_budget_aliases':all(any(row is b for b in v['budgets']) for row in v['pending'])} for s,v in context['states'].items()}}
 receipt={'schema':'stage421_actual_read_only_resume_v1','status':'restored_original_current_contexts_read_only','completed_at':now(),'scope':sb,'resume_manifest':manifest,'execution_dependencies':db,'profiles':summaries,'counts':{'restored_contexts':2,'initialize':0,'journal_append':0,'inference':0,'D_execution':0,'fit':0,'cash':0,'API':0,'SQL':0},'real_next_day_execution_ready':False,'reason':'Actual u21 source and new source review/root day acceptance do not exist yet. No financial execution authority now.'}
 b=write(out/'actual_read_only_receipt.json',receipt);print(json.dumps({'status':receipt['status'],'receipt':b,'dependency_epochs':len(deps['epochs']),'dependency_roles':len(deps['roles']),'dependency_unresolved':len(deps['unresolved']),'profiles':summaries},ensure_ascii=False))

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--actual-read-only-resume',action='store_true');args=parser.parse_args()
 if args.actual_read_only_resume:actual_read_only_resume()
 else:parser.error('only explicit read-only resume CLI allowed; new-day execution requires separate root acceptance')
