"""Seal current manual integration/launcher scope; prior receipts remain immutable."""
from pathlib import Path
import ast,datetime,hashlib,json
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[4];D=Path(__file__).resolve().parent;sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();read=lambda n:json.loads((D/n).read_text())
v=read('Stage018_review_manual_integration_locked_attempt001.json');assert v['tests']==52 and v['failures']==v['errors']==v['skipped']==0 and v['source_unchanged']
for p,s in v['source_after'].items():assert sha(ROOT/p)==s,p
strict_paths=['examples/portfolio_backtesting/qmt_roll_weekly19_funding_store.py','examples/portfolio_backtesting/qmt_roll_weekly19_pipeline_state.py'];strict={}
for path in strict_paths:
 tree=ast.parse((ROOT/path).read_text());calls=[]
 for node in ast.walk(tree):
  if isinstance(node,ast.FunctionDef):
   for call in ast.walk(node):
    if isinstance(call,ast.Call)and isinstance(call.func,ast.Attribute)and call.func.attr=='_forward_ledger':
     # Avoid counting nested function calls twice: these two modules have no
     # nested function containing a forward-ledger call.
     kw={k.arg:ast.dump(k.value,include_attributes=False)for k in call.keywords};calls.append(dict(function=node.name,keywords=kw))
 strict[path]=calls
assert {x['function']for x in strict[strict_paths[0]]}=={'_recover','commit'}
assert all(x['keywords'].get('strict_manual_parent')=='Constant(value=True)'for x in strict[strict_paths[0]])
pipeline_calls={x['function']:x['keywords']for x in strict[strict_paths[1]]};assert pipeline_calls['_validate']=={}and pipeline_calls['transact']['strict_manual_parent']=='Constant(value=True)'
launcher=read('Stage018_review_launcher945_attempt002.json');assert launcher['exit_code']==0 and launcher['source_unchanged'] and all(launcher['three_c9_bodies_ast_preserved_after_dispatch_strip'].values())
source_map=dict(v['source_after']);source_map['examples/portfolio_backtesting/qmt_roll_weekly19_context_update.py']=launcher['source_after']['examples/portfolio_backtesting/qmt_roll_weekly19_context_update.py']
assert sha(D/'Stage018_review_manual_pure_acceptance.json')=='3e1ed34245ae32684fd89a58af487c89c08cbed03727fb19bbe897c898cd8945'
now=datetime.datetime.now(ZoneInfo('Asia/Shanghai')).isoformat();md=D/'Stage018_review_manual_integration_summary.md'
md.write_text(f'''# Stage018 人工核验接线与Stage945增量独审

时间：{now}；line_id=futures_weekly_short_ma_slope_gate。结论PASS_OFFLINE_INTEGRATION_WITH_LIMITATIONS；仅接受当前精确锁源的CLI、私有记录/引用、Backend、同actor/CAS和945日历接线。source_qualified=false、production_qualified=false。用户不再要求自动final parser/银行到账producer，该决定继续有效；不以它们尚未自动实现阻断本人工模式工程验收。

## 修复与已保留负例

- P2 CLI：topups:null的合法JSON曾在实际prepare抛未捕获TypeError，未结构化返回blocked。无证据证明实际凭证泄露，也未写资金。root补TypeError脱敏、component在读live源前严格验容器/金额/notes，原1失败及修复后结果保留。
- P2 私有记录目录：写link后父目录被rename并重建时，曾发布不存在visible record的引用并报published。资金未credit、后续source应拒，但发布语义错误。当前写前后可见父identity与发布前后实际record SHA复验，原1失败保留。
- P2 context持久化重试：首次replace后目录fsync失败会报unconfirmed，但重试已存在reference时曾直接return，未再做失败barrier却升级published。独审原2例1失败1通过；当前existing-ref分支重新dir fsync、父/record复验，两例都通过。不是将原unconfirmed当已消费。

纯资金两P1及85验收仍封在旧receipt3e1ed342…，不改历史、不重复85。新store/pipeline已变化，旧store4617身份不能冒继承为当前07cb身份，本记录另行接受下述增量。

## 真正CAS与历史链分开

原严格parent约束误用于decision_origin_cash→current cash历史，会拒同原decision分两次实际CAS完成的合法部分到账。现在只历史_validate使用默认前向检查；FundingStore.commit、journal recover和PipelineStateStore.transact实际调用均硬编码strict_manual_parent=True，不受JSON控制。

独审5例：两次真实独立store提交可读；实际pipeline history validator可验证旧origin至两review当前状态且保持原decision_state；一次真实CAS跨两review仍拒；错误父hash真实CAS拒；错误父journal恢复拒且不覆盖原状态。额外JSON strict_manual_parent:false不能关闭真实CAS门。历史分支仍验gross/time/receipt/append-only，不是放宽人工账守恒。

## CLI、I/O与Backend

CLI绝对路径、profile与明确确认文本、私有输入、operator/review ID绑定均有覆盖；status不publish，confirm只表示record/reference待actor消费，funding_consumed=false，错误不回显任意notes/raw。公有prepare对坏容器/金额先验并且零_live_inputs。生产资格与provider source gate仍先于接触calendar/写record；独审明确source_qualified=false结果在calendar前拒绝。所有正例authority/broker为标注fixture，不是新真实来源。

Backend先读取全部引用再应用最多1新review；null/int/缺path/None等mutable JSON均变manual_pending，不逃逸中断处理或部分入账。同ID不同字节冲突拒，旧已消费review不能核销新Deposit/新TradingDay。引用CAS保留并发其他cashrefs；每次消费仍重验真实source与当前fund baseline。作者实际旧warmreader/bridge/Runtime/PipelineStore的同actor0T人工日切用例通过：无on_bars重跑、原decision/decision_state不变，funding与runtime一起提交。缺manual的待核现金与原实际持仓减风险路径分开；这不是允许在unknown真实持仓下发close。

## Stage945

当前945 SHA bf43bd03ea358cdc8a8599a9423c63c1bd9e46eaa70852a99e32555d34a448d3。weekly分支由固定私有context、5源pin及同目录calendar解析，cold_start来自已绑定context，不用旧C9 Stage922/冷启动常量或caller布尔。16:29:59至16:30必须重新选择完成target，旧payload不能跨界沿用；future/stale/naive时钟、source漂移、旧C9 receipt/profile/release和过期forward calendar均拒。现金refs变更允许，account/release/mode变更会使旧证明失效。

六独审还使用实际inactive完整market generation（没有broker）验证11月2日09:00→10月30日，并按临时context11月1日cold_start安全skip；此证明只有calendar，不是实际账户或生产启动许可。作者11例覆盖夜盘/周六续段/假日与原daily receipt门仍在。三旧C9函数体剥离weekly dispatch后AST与实际Git基线b086a812…完全相同；_resolve_target_date新增可选keyword now=None，故不声称三个完整函数含signature AST全相同。首次独审预检范围错误（全函数比对）已记录，修比较范围后无core改动。

## 最终验证与界限

52次调用/1.210秒，32直接接线作者例与20独立反例，0失败/0错误/0跳过；11项code/test SHA运行前后一致，另锁context helper。没有重跑纯85、金融历史或真实接口。parent完整90suite首次已中断、无完整XML，不能把缺失counts当全通过；root另在必要本地runtime日志权限下完整重验。本记录既不归因未取证CI失败，也不替代完整CI。

实际source-qualified CTP账户/持仓/订单/quote、人工真实现金事实、不可变m2 release/qualification/activation、master readback及production安装/loadedjobs仍须各自验证。人工记录不是broker自动HMAC/到账证明，不虚增E/Available，R+T=15000000分；纯事实现有0signal报告不变成交易许可。对无statementparser的人工责任边界不作自动bank资格承诺。本文独审没有HTTP/网络/CTP/SMTP/银行/订单/Git/index/生产操作；不代表用户禁止另行授权的只读行情网络。

过拟合判断否，alpha/风险金额/阈值未动；继续价值为核清现金事实、原子状态和真实执行的边界。无新增金融回测，绩效指标N/A，Stage014经济NO_PROMOTION不改。
''')
names=['Stage018_review_manual_integration_locked_attempt001.json','Stage018_review_manual_integration_locked_attempt001.log','Stage018_review_manual_cli_adversarial.py','Stage018_review_manual_cli_attempt001.json','Stage018_review_manual_cli_attempt001.log','Stage018_review_manual_cli_attempt002.json','Stage018_review_manual_cli_attempt002.log','Stage018_review_manual_io_adversarial.py','Stage018_review_manual_io_adversarial_v2.py','Stage018_review_manual_io_attempt001.json','Stage018_review_manual_io_attempt001.log','Stage018_review_manual_io_attempt002.json','Stage018_review_manual_io_attempt002.log','Stage018_review_strict_parent.py','Stage018_review_strict_parent_attempt001.log','Stage018_review_manual_backend.py','Stage018_review_launcher945.py','Stage018_review_launcher945_precheck_attempt001.json','Stage018_review_launcher945_attempt002.json','Stage018_review_launcher945_attempt002.log','Stage018_review_manual_pure_acceptance.json','Stage018_review_signal_acceptance.json','Stage018_operator_manual_cash_runbook.md','20261101_0457_Stage018_manual_cash_implementation.md','20261101_Stage018_manual_cash_author_manifest_v2.json']
record=dict(schema='Stage018.independent-manual-integration-launcher-review.v1',recorded_at=now,line_id='futures_weekly_short_ma_slope_gate',status='PASS_OFFLINE_INTEGRATION_WITH_LIMITATIONS',accepted=True,accepted_scope='Current pinned manual CLI/private IO/backend/same-actor strict CAS and weekly Stage945 source/calendar wiring; not production qualification',failures=[],open_findings=[],severity_open=dict(P0=0,P1=0,P2=0),fixed_findings=[dict(id='MANUAL_CLI_NESTED_TYPEERROR',severity='P2'),dict(id='MANUAL_RECORD_PARENT_MOVED',severity='P2'),dict(id='MANUAL_EXISTING_REF_RETRY_MISSING_DIR_FSYNC',severity='P2')],verification=dict(test_invocations=52,author_direct_wiring_cases=32,independent_tests=20,failures=0,errors=0,skipped=0,source_drift=False,pure85_repeated=False,counts_not_globally_deduplicated=True),source_files_sha256=source_map,strict_parent_actual_calls=strict,historical_validation_can_span_two_real_commits=True,real_cas_parent_binding_not_json_configurable=True,legacy_945_body_ast_proof=launcher['three_c9_bodies_ast_preserved_after_dispatch_strip'],legacy_945_interface_delta=launcher['argument_changes'],legacy_945_baseline_commit=launcher['legacy_baseline_commit'],legacy_945_baseline_blob_sha256=launcher['legacy_blob_sha256'],source_qualified_by_real_capture=False,production_qualified=False,real_cash_verified=False,broker_automatically_verified=False,record_publication_is_not_funding_consumption=True,automatic_final_parser_required=False,automatic_bank_producer_required=False,real_ctp_account_positions_quote_gates_required=True,real_ctp_connected=False,real_bank_transfer=False,real_order_submitted=False,real_smtp_sent=False,financial_replays=0,git_index_modified=False,production_changed=False,master_promoted=False,full_selected_ci_pass_claimed=False,full_selected_ci='ROOT_OWNED_SEPARATE_COMPLETE_RETRY_REQUIRED',component_receipts_sha256=dict(pure_funding=sha(D/'Stage018_review_manual_pure_acceptance.json'),signal_scope=sha(D/'Stage018_review_signal_acceptance.json')),prior_pure_store_pin_not_inherited=True,code_policy='Actual current files pinned; no old whole-source acceptance is substituted',evidence_files_sha256={n:sha(D/n)for n in names},chinese_record_sha256=sha(md),remaining=['Complete offline selected CI in appropriate local runtime environment','New immutable release/source qualification and activation chain','Fresh actual CTP account/positions/orders/quotes after user-specified 2026-11-02 09:00 boundary','Operator truthful cash verification and controlled actor consumption','Master/production install/readback/loaded scheduler evidence'],overfitting=False,continuing_value=True)
p=D/'Stage018_review_manual_integration_acceptance.json';p.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n');print(p);print(sha(p));print(md);print(sha(md))
