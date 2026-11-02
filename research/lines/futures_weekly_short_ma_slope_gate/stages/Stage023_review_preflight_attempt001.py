"""Read-only source/command admission. Never invokes generated commands or imports CTP."""
from pathlib import Path
from datetime import datetime, timezone
import ast, hashlib, json, shlex, subprocess
ROOT=Path(__file__).resolve().parents[4]
D=Path(__file__).resolve().parent
P=ROOT/'examples/portfolio_backtesting'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
checks=[]
def check(name, condition):
    checks.append(dict(name=name,passed=bool(condition)))
    if not condition: raise AssertionError(name)
def git(where,*args):
    return subprocess.check_output(['git','-C',str(where),*args],text=True).strip()
source=P/'run_qmt_roll_stage907_official_live_readonly_refresh_gate.py'
tree=ast.parse(source.read_bytes())
fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='_production_live_command')
ns=dict(PROJECT_DIR=P,REPO_ROOT=ROOT,shlex=shlex)
exec(compile(ast.Module(body=[fn],type_ignores=[]),str(source),'exec'),ns)
release=json.loads((D/'Stage022_m3_release_receipt.json').read_bytes())
options=('--weekly19-material-release-id',release['release_id'],'--weekly19-execution-profile','weekly19-15w-r150k','--weekly19-private-capture-dir','/private/tmp/weekly19-review-capture-placeholder')
cmd,shell=ns['_production_live_command'](30,'stage023-readonly-placeholder',weekly19_capture_options=options)
check('shell_not_executed_and_wrapper_bash_lc',cmd[:2]==['bash','-lc']and cmd[2]==shell)
lines=shell.splitlines();arguments=shlex.split(lines[-1]);check('formal_env_only',lines[1]=='set -a; source '+shlex.quote(str(P/'ctp_live.local.env'))+'; set +a')
check('formal_framework_before_py311_lib',lines[2].startswith('export DYLD_FRAMEWORK_PATH='+str(ROOT/'.py311/lib/python3.11/site-packages/vnpy_ctp/api/libs')+':'+str(ROOT/'.py311/lib')))
check('exact_python_probe',arguments[:2]==[str(ROOT/'.py311/bin/python'),str(P/'run_ctp_stage174_readonly_probe.py')])
check('connect_readonly_30s',arguments[2:6]==['--connect','--wait-seconds','30','--invocation-id'])
check('m3_capture_options_preserved',arguments[-len(options):]==list(options))
check('no_authority_fabricated',not any('authority' in item for item in arguments))
tricky="review;$(touch /private/tmp/NEVER_EXECUTED)'value"
_,quoted=ns['_production_live_command'](20,tricky,weekly19_capture_options=options)
check('invocation_shell_quoted',shlex.split(quoted.splitlines()[-1])[6]==tricky)
for opts in (('--send-order','1'),('--weekly19-private-capture-dir',)):
    try:ns['_production_live_command'](30,'placeholder',weekly19_capture_options=opts)
    except ValueError:check('invalid_option_rejected_'+str(len(checks)),True)
    else:check('invalid_option_rejected',False)
lock_path=D/'Stage022_implementation_lock_attempt002.json';lock=json.loads(lock_path.read_bytes())
actual={name:sha(ROOT/name)for name in lock['critical_files_sha256']}
check('all_291_m3_critical_sources_match',actual==lock['critical_files_sha256']and len(actual)==291)
manifest_path=Path(release['manifest_path']);check('m3_manifest_file_pin',sha(manifest_path)==release['manifest_file_sha256'])
manifest=json.loads(manifest_path.read_bytes());payloads={row['payload_path']:sha(manifest_path.parent/row['payload_path'])for row in manifest['files']}
check('all_381_m3_payload_files_match',len(payloads)==381 and all(payloads[row['payload_path']]==row['sha256']for row in manifest['files']))
stable=Path.home()/'Desktop/person/vnpy_production_live'
current_path=stable/'official_strategy_materials/CURRENT.json';current=json.loads(current_path.read_bytes())
production=Path.home()/'Library/Application Support/qmt-roll-stage179/production-live'
required=['release-manifest.json','qualification-bundle/qualification.json','activation/latest.json','runtime/state/activation_receipt.json','data-readiness/latest.json']
artifacts={str(production/name):dict(exists=(production/name).is_file())for name in required}
files=[source,P/'run_ctp_stage174_readonly_probe.py',P/'build_qmt_roll_stage179_production_qualification_bundle.py',P/'build_qmt_roll_stage179_release_manifest.py',P/'qmt_roll_weekly19_broker_evidence.py',P/'qmt_roll_weekly19_local_backend.py',P/'qmt_roll_weekly19_funding.py',P/'qmt_roll_official_live_phase_d_config.py',D/'Stage022_m3_release_receipt.json',lock_path,manifest_path,current_path,Path(__file__)]
receipt=dict(schema='stage023.independent.readonly-preflight.v1',generated_at_utc=datetime.now(timezone.utc).isoformat(),status='PREFLIGHT_REVIEWED_WITH_QUALIFICATION_PENDING',accepted_for='root-owned formal-environment read-only diagnostic only',production_qualified=False,source_qualified=False,can_install_or_trade=False,actual_native_result_reviewed=False,source_head=git(ROOT,'rev-parse','HEAD'),observed_stable_head=git(stable,'rev-parse','HEAD'),observed_stable_material_release_id=current['release_id'],observed_stable_current_sha256=sha(current_path),m3_material_release=release['release_id'],m3_material_source_commit=release['source_commit'],m3_material_release_commit=release['release_commit'],source_files_sha256={str(p):sha(p)for p in files},m3_critical_count=len(actual),m3_critical_map_sha256=hashlib.sha256(json.dumps(actual,sort_keys=True,separators=(',',':')).encode()).hexdigest(),m3_payload_count=len(payloads),checks=checks,check_count=len(checks),failures=[],production_authority_files=artifacts,generated_command_never_executed=dict(argv=cmd,outer_required_env_gate='OFFICIAL_LIVE_PHASE_D_READONLY_REFRESH_ENABLED=1',outer_refresh_confirmation='I_UNDERSTAND_THIS_RUNS_CTP_READONLY_REFRESH_ONLY',outer_email_policy='never'),source_findings=[],qualification_requirements=[
'Trusted Stage179 runner must own exact clean source, required-suite executions and at least two native Stage907 captures; standalone diagnostic JSON is not trusted-runner evidence.',
'Candidate explicit material mode requires actual HEAD equal exact material release_commit. Current source HEAD and candidate release commit are distinct identities; no same-critical/ancestor shortcut.',
'Raw TD authentication/login/settlement-confirm readiness and MD lifecycle, same live connection generation; account/positions/orders/trades query reqids, completion-last/error/timestamps and normalized raw mappings; contracts query complete.',
'All eight send/cancel/native-mutation attempted and called counters explicitly zero; mutation firewall remains installed through engine close and evidence freezing.',
'Actual fresh account Balance must be exactly CNY150000 for initial cohort, Available known nonnegative, positions empty and no nonterminal orders; do not infer from a historical or simulated baseline.',
'Initial cash observation only pins actual cash after production/flat gate, preserves external R150000 and T0; manual operator cash review remains separate from actual broker Balance.',
'Private raw capture and HMAC registry do not self-qualify. Registry creation requires actual full production qualification, final manifest and activation plus exact stable HEAD, active material and semantic source closure.',
'Final production chain and scheduler/runtime/data readiness must be separately accepted. No automatic bank-producer or final-settlement parser requirement is revived; operator_manual_v1 is the authorized mode.'
],source_locations={'formal_command':str(source)+':223','trusted_native_captures':str(P/'build_qmt_roll_stage179_production_qualification_bundle.py')+':412','candidate_exact_head':str(P/'build_qmt_roll_stage179_production_qualification_bundle.py')+':1215','raw_native_validator':str(P/'build_qmt_roll_stage179_release_manifest.py')+':1270','registry_final_production_gate':str(P/'qmt_roll_weekly19_broker_evidence.py')+':1185','initial_real_account':str(P/'qmt_roll_weekly19_local_backend.py')+':146','initial_cash_observation':str(P/'qmt_roll_weekly19_funding.py')+':445'},operational_actions=dict(ctp_connections=0,order_calls=0,cancel_calls=0,smtp_sends=0,financial_replays=0,production_changes=0,credential_files_read=0),limitations=['This is static source/command review with isolated AST function evaluation; generated command was never executed.','No actual native capture, real account balance/positions, connection outcome or production authority is accepted by this receipt.','Stable checkout existence/CURRENT identity are observed; qualification/activation cannot be inferred from either.'],reflection=dict(overfitting=False,reason='No alpha/parameter selection or financial replay; validating runtime/source evidence boundaries only.',worth_continuing=True,value='Determine real connectivity/account facts while preserving qualification and cash/execution safety gates.'))
out=D/'Stage023_review_preflight_attempt001.json'
if out.exists():raise FileExistsError(out)
out.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
md=D/'Stage023_review_preflight_attempt001.md'
md.write_text('# Stage023 只读探针与资格接续独立预审\n\n仅接受 root 独占执行正式环境只读诊断，不接受为生产资格。独立检查 '+str(len(checks))+' 项通过；291 项 m3 critical 与381份封存payload实物哈希均相符，未执行生成命令。\n\nStage907 明确读取正式 env 并把正式 framework 放在 CP 库之前，20–45秒探针必须禁邮件并保留 mutation firewall 的8项零API证据。私有 capture 写入 m3 release/profile 并不授予来源资格。\n\n正式 Stage179 runner 需直接生成至少两次原生只读回执与 required suites；当前源码 HEAD '+receipt['source_head']+' 与 m3 release commit '+release['release_commit']+' 不同，候选入口要求 exact release HEAD，不得仅凭关键文件同字节放宽。现观察 stable HEAD '+receipt['observed_stable_head']+'、CURRENT '+current['release_id']+'；五份预期生产 authority 文件存在情况已在JSON列出，目录或指针不能冒充生产资格。\n\n首 cohort 必须由真实 fresh CTP 账户证明 Balance 恰为150000、Available已知非负、空仓且无非终态委托。资金初始化只登记真实现金，不增加账户E，不消耗场外R，不把初始Deposit重复算T。用户授权人工核验模式保持，不恢复已取消的自动银行或最终日结解析要求。\n\n本次没有 CTP/交易/撤单/SMTP/下载/金融重跑/生产修改，也未读取凭证。未发现所审正式命令分支的新代码缺陷；真实账户、原生来源、完整qualification、activation、runtime与data readiness仍需后续实际证据。\n\n过拟合判断：否，仅验证工程与证据边界；继续有价值：是，真实连接和账户条件必须先确证。\n')
print(json.dumps(dict(receipt=str(out),sha256=sha(out),markdown=str(md),markdown_sha256=sha(md),check_count=len(checks),production_qualified=False),ensure_ascii=False))
