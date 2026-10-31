"""Seal pure funding review only; integration and production remain separate."""
from pathlib import Path
import ast,datetime,hashlib,json,subprocess
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[4];D=Path(__file__).resolve().parent;sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();read=lambda n:json.loads((D/n).read_text())
v=read('Stage018_review_manual_pure_locked_attempt002.json');assert v['tests']==85 and v['failures']==v['errors']==v['skipped']==0 and v['source_unchanged']
for f,s in v['source_after'].items():
 if not f.startswith('tests/'):assert sha(ROOT/f)==s,f
test_drift={f:dict(tested=s,current=sha(ROOT/f))for f,s in v['source_after'].items()if f.startswith('tests/')and sha(ROOT/f)!=s}
base='e3d08592e85e00a2a6b8fde880f69e771755f10b';fundpath='examples/portfolio_backtesting/qmt_roll_weekly19_funding.py';storepath='examples/portfolio_backtesting/qmt_roll_weekly19_funding_store.py'
def asts(raw,top=False):
 tree=ast.parse(raw);nodes=tree.body if top else ast.walk(tree)
 return {n.name:hashlib.sha256(ast.dump(n,include_attributes=False).encode()).hexdigest()for n in nodes if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
relations={}
for path,top,allowed in [(fundpath,True,{'validate_state','_request_chain'}),(storepath,False,{'_forward_ledger'})]:
 old=subprocess.run(['git','show',base+':'+path],capture_output=True,check=True).stdout;new=(ROOT/path).read_bytes();a,b=asts(old,top),asts(new,top);changed=[name for name in a if b.get(name)!=a[name]];assert set(changed)==allowed
 relations[path]=dict(old_source_commit=base,old_source_sha256=hashlib.sha256(old).hexdigest(),current_source_sha256=hashlib.sha256(new).hexdigest(),changed_legacy_functions=changed,unchanged_legacy_functions_sha256={n:s for n,s in a.items()if b.get(n)==s},new_functions_sha256={n:s for n,s in b.items()if n not in a})
now=datetime.datetime.now(ZoneInfo('Asia/Shanghai')).isoformat();md=D/'Stage018_review_manual_pure_summary.md'
md.write_text(f'''# Stage018 人工资金纯核心独立验收

时间：{now}；line_id=futures_weekly_short_ma_slope_gate。PASS_OFFLINE_PURE_MANUAL_FUNDING_WITH_LIMITATIONS，仅接受当前锁源纯资金转移/持久化语义；CLI、Backend、actor接线与真实生产均未由本记录接受。

## 发现与修复

1. P1：持久化manual ledger只核自洽SHA回链，没有重核逐日gross与补资T。独审将合法Friday入金30000/闭日Deposit30000改为闭日Deposit0，并同步重算review、roll、receipt SHA，validate_state与FundingStore跨日commit仍接受T30000、R120000。首次2例均失败，来源fund5f36a542…/store4617b1b…前后相同。作者抽取_operator_cash_totals供apply与持久化validate共同核逐日Deposit/T、gross计数、时序/日期和R。原失败保留，当前两例通过。
2. P1：持久化request时窗只比较review.created_at，未比较实际item.applied_at。请求过期前1分钟创建review，过期后1分钟才记为应用（仍在30分钟review窗口与账户fresh内），validator/store均接受，而纯apply会拒。第二轮4例为2失败2通过。当前显式核applied_at早于原request.expires_at，历史合法记录不因后续retirement重写，原失败保留，当前通过。

修复不要求自动银行/最终statement证明，只要求人工账自身守恒和时序诚实。用户取消的自动producer/parser不再列为本纯模块必须完成项。

## 最终验证

85次调用全绿：61旧资金回归、12作者manual用例、12独立对抗，0失败/错误/跳过；不是全局去重测试总数。第一次组合运行因独审调用旧confirm_topup漏传request_id有1个TypeError，保留日志；只修独审脚本v2后，在相同实现上85通过，未把适配错误当core故障。

独立还覆盖跨review重复receipt、旧已消费record过期后只保持事实且不能核销新Deposit/新TradingDay、利润余额恢复不产生T/旧债、失败输入不部分修改、manual schema/qualified旗标不能变自动receipt、已验calendar中缺闭日拒绝、store父fund hash重写拒绝、零topup人工记录也append-only。

当前funding SHA 419b8c31b9685ab69ef47c4abc35f266cfc56ad7c9fb9f76c1ceffa44609c677；store SHA4617b1b9509a83e5d4c8b2ae2fae983950811256d022a233b38e9b5da2f7ef47。测试运行前后4项code/test SHA完全一致。作者在这次运行完成后继续追加manual测试，当前test文件已变化；85不冒称覆盖这些新增测试，两项实现锁SHA未变，新增I/O/backend另审。独立与m0001 source commit {base}的实际Git blob对比：fund旧29个函数AST完全不变，只有validate_state/_request_chain变动；store旧13个函数AST完全不变，只有_forward_ledger变动。新增5个operator函数单列。_request_chain仅为已标operator_manual且ledger可核的gross提现语义分支，旧自动分支仍原约束；validate对manual非零following有完整review覆盖，人工不是旧自动来源豁免旗标。

## 接受边界

人工记录明确operator_manual、broker_automatically_verified=false，不产生source-qualified/production-qualified。R+T恒等15000000分且不会把T再次加到E/Available；账户真实权益、实际可用资金、持仓、订单、报价、source qualification仍由真实CTP与执行门负责。纯模块接纳的envelope在测试中全为fixture，不能冒称真实到账E2E。

CLI私有落盘/引用CAS、同actor消费、多ref失败/崩溃恢复、context mode与新release policy/critical source闭包尚待后续独审。直接读回validate只核本账可确定的内部语义；交易日历完整性在apply接受已验calendar时核，需Backend保证该calendar来源，不能给不可信列表。旧自动兼容回归不代表新生产链已合格。

本轮无alpha/风险金额/阈值调整，无金融回放，过拟合判断否；继续价值是消除资金账与持久化之间的语义落差。Stage014原经济NO_PROMOTION不改。无CTP/SMTP/银行/订单/HTTP/生产或Git/index操作，11月2日09:00前不试CTP。此前Stage018零交叉信号审查仍为独立历史时点结果，不能被本模块或人工记录变成actionable。
''')
names=['Stage018_review_manual_ledger_adversarial.py','Stage018_review_manual_ledger_adversarial_v2.py','Stage018_review_manual_ledger_attempt001.json','Stage018_review_manual_ledger_attempt001.log','Stage018_review_manual_ledger_attempt002.json','Stage018_review_manual_ledger_attempt002.log','Stage018_review_manual_pure_boundaries.py','Stage018_review_manual_pure_boundaries_v2.py','Stage018_review_manual_pure_locked_attempt001.json','Stage018_review_manual_pure_locked_attempt001.log','Stage018_review_manual_pure_locked_attempt002.json','Stage018_review_manual_pure_locked_attempt002.log','Stage018_review_manual_design_preflight.json','Stage018_review_manual_design_input.md','Stage018_review_signal_acceptance.json']
record=dict(schema='Stage018.independent-pure-manual-funding-review.v1',recorded_at=now,line_id='futures_weekly_short_ma_slope_gate',status='PASS_OFFLINE_PURE_MANUAL_FUNDING_WITH_LIMITATIONS',accepted=True,accepted_scope='Pure funding API, validator and FundingStore forward semantics only; CLI/backend/integrated runtime not accepted',failures=[],open_findings=[],severity_open=dict(P0=0,P1=0,P2=0),fixed_findings=[dict(id='MANUAL_PERSISTED_GROSS_INCONSISTENCY',severity='P1',red='2 failures; self-consistent hashes unsupported by declared gross deposits',status='FIXED'),dict(id='MANUAL_PERSISTED_APPLIED_AFTER_REQUEST_EXPIRY',severity='P1',red='4 tests / 2 failures / 2 pass after prior gross fix',status='FIXED')],verification=dict(test_invocations=85,independent_cases=12,legacy_funding_regression=61,author_manual_cases=12,failures=0,errors=0,skipped=0,source_drift=False,prior_adapter_error_preserved=True),source_files_sha256={f:s for f,s in v['source_after'].items()if not f.startswith('tests/')},tested_source_files_sha256=v['source_after'],post_run_test_file_changes=test_drift,legacy_ast_relations=relations,source_qualified=False,production_qualified=False,real_bank_cashflow_verified=False,broker_automatically_verified=False,manual_mode_integrated=False,cli_backend_accepted=False,full_selected_ci_claimed=False,financial_replays=0,real_external_actions=False,git_index_modified=False,old_records_modified=False,automatic_final_parser_required=False,automatic_bank_producer_required=False,real_ctp_account_positions_quote_gates_required=True,evidence_files_sha256={n:sha(D/n)for n in names},chinese_record_sha256=sha(md),remaining_validation=['Private immutable manual review IO / context ref CAS / retry and crash behavior','Backend mode policy and provider-source gate before raw data use','Same actor atomic cash/runtime consumption and multi-reference failure behavior','Actual authoritative calendar provenance and complete production source/qualification/activation chain'],overfitting=False,continuing_value=True)
p=D/'Stage018_review_manual_pure_acceptance.json';p.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n');print(p);print(sha(p));print(md);print(sha(md))
