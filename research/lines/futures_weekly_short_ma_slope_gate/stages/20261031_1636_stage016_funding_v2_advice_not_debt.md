# Stage016 资金V2：建议不是债务，真实E恢复后保留未用场外备用金

- line_id：futures_weekly_short_ma_slope_gate；day。
- 时间：2026-10-31 16:36 CST；工作树 /Users/mac/.codex/worktrees/weekly19-official-20261031/fian。
- 性质：必要的真实资金执行合同修正；不改alpha，不运行金融回测，不变初始15万交易/15万场外比例。
- 是否重要突破：否；是否触发A/B：否。production_qualified=false。
- V1 checkpoint：09e7e07e8；V1源码、合同、manifest和独审证明均保留，不重写其历史SHA或结论。

## 外部资料与业务判断

- 本轮沿用前一provider阶段已调研的[CTP官方原始字段](https://github.com/vnpy/vnpy_ctp/blob/main/vnpy_ctp/api/include/ctp/ThostFtdcUserApiStruct.h)：Balance含市场变化、Deposit/Withdraw是独立现金流。V2只修改建议的有效性和生命周期，不改这些会计证据口径。
- 用户原话“如果回到了15万就保留着，永远不参与交易”意味着：尚在场外的钱不应因为旧建议而强制转入；补资建议不是欠款。V1的“任一pending无条件封新开”在人工入金时滞下过强，可能误封真实E已经恢复的账户，也可能让已过期建议锁死后续原生信号。
- 判断：保留V1现金守恒与真实到账证明门；旧建议既不应虚增E，也不应变成必须偿还的债务。只用当前真实E决定本资金闸是否仍需补资；R只按真实已确认到账递减。

## 版本/API变动

- 新state schema=weekly19.external-funding.v2，funding_contract_version=2。
- 新retirements：按request_id保存退休原因、完整现金链证据/原始账户SHA、已确认/未付额、真实E及当时R；未付额只是历史上限，不是债务。
- 新request_attempts：admission_key -> 追加的request IDs；admitted_entries保留首次归属，不重指。新request带attempt=len(existing requests)，纳入新rid hash；旧V1 rid和所有receipt原样保留。
- 新upgrade_funding_state(v1)->v2：保留旧身份、资金、request、receipt和原生admission，revision仅+1，必须FundingStore.commit(old_revision,new_state)一次CAS落地；旧V1允许validate/load审账，业务变更入口明确upgrade_required，不静默reset。V2重复upgrade幂等。
- 新retire_topup_request(state,request_id,broker,now,reason=...)，reason只接受equity_recovered、expired_superseded、superseded_current_gap。
- 旧recommend_topup/confirm_topup/assert_open_funding_ready/reconcile_trading_day签名保持；底层_broker/_parse/_money等provider依赖未改。
- 新退休终态retired_unpaid/retired_partial；active仅pending或partially_confirmed。调用方不能再用status!='confirmed'把退休历史当未到账债务。
- 原固定初始交易/场外R、300秒freshness、7日过期不变；没有新增可调alpha/资金比例参数。

## V2业务合同

1. 无未知现金流且真实E>=150000时，旧pending单独不封新开；当前T=0，尚未入金的R继续留场外。E含未平仓MTM，但权益上涨绝不登记为入金或回补R。
2. 实际部分入金使E达到floor，也不强补历史建议余量。E<floor且仍有active未到账建议则继续封新开；R=0且没有active且E>0仍按剩余真实E和原风险继续。
3. recommend的amount_fen按当前T=min(max(150000-E,0),R)；历史未付另列historical_request_remaining_fen/historical_request_id。当前gap与旧request cap不同，返回request_refresh_required、actionable=false、request_id=None，不能把50k建议写到原30k request上。
4. 必须先用完整现金链证据retire旧建议，再创建新attempt，才给actionable新建议。退休不减少/增加R，不删除已确认receipt，不撤销银行已发出的付款；晚到款或未知Deposit/Withdraw增量保持fail-closed待显式对账，绝不吞并进新request。
5. 退休证据：当前完整原始broker query的Deposit/Withdraw必须与持久checkpoint精确一致；请求原始baseline到当前名义日之间的每个已接受day-close/zero-start边界必须连续，当前active-day Deposit增量必须等于已确认金额。任何缺日、源不匹配或未知款不能retire，E恢复不能补现金证明。
6. reconcile_trading_day允许过期active建议随完整现金中性日切链携带，仅为收齐退休证据；不自动确认、不延长expires_at、不自动给原信号增加资金。真实最终日切来源没qualified仍阻断。
7. 资金建议只在原native“新信号形成/parent sizing之前”的admission批次调用（完成周/周五），不是每个tick、fill、订单投递或重报价把账户补到15万的服务。admitted_entry_ids必须保留original_admission_id，不含broker generation、delivery ID、报价或现金generation。
8. 已confirmed原admission永久消费，即便市场跌回130k、source hash和broker query generation变了，也不能再次建议。equity_recovered或expired_superseded退休也结束旧候选；只有superseded_current_gap明确允许同一候选的一次新cap替换。新周/真正新原生候选出现才按其当前E/R重新建议。

## 固定反例/结果

- 未付：E120k建议30k，真实行情涨到151k -> T0/R150k，新开资金闸可过，confirmed现金仍0。
- 部分：已到账10k，E回150k -> T0/R140k，不强补剩余20k；旧receipt保留。
- 变差：旧30k等待期间E跌到100k -> 当前T50k，但request_refresh_required不可操作；完整现金链retire后新attempt cap50k，旧cap30k不改。
- 过期partial：按每个名义交易日完整close/零起点跨到expiry，退休旧partial，再对新周真实新候选生成当前缺口建议；已付R单调，不复活。
- 退休后晚到/未知款 -> confirm/open均阻断；已确认旧receipt重放仍幂等，不扣第二次R。
- 缺完整日切或未知入出金，即使E>=floor也不能retire，也不能绕过现金未知闸。
- 同original admission已全额到账后，真实E130k且换broker generation/source hash -> duplicate_admission、0新建议、R不变。
- V1 partial持久账本迁移：旧request/receipt/资金/身份保持，单CAS +1；防schema降级、retirement删除、attempt漏记和检查点倒退。
- 旧V1 crash后state和journal同版本：先幂等恢复，再显式迁移，不能被migration闸误拒。

## 验证和边界

- TDD：先新增10个V2行为用例，旧实现1失败+8错误；实现后46tests绿；再补5个自查用例，发现旧V1同版journal与attempt归属2个问题，修后51tests绿。
- 资金51 + 冻结provider兼容23 = 74 tests全部exit0。Python内存compile、git diff --check通过；provider/Stage174/provider tests三源SHA与1622原manifest完全一致。
- 全部新证据见同前缀manifest.json、unittest.txt；本轮没改任何V1历史证明文件，也没有改provider锁定源。
- 没有金融回测，期末权益/收益/回撤/Sharpe/滑点/成交/胜率/payoff/PF均不适用；旧研究业绩保持原记录。
- 真实capture authority、银行回调资格及final cashflow day-close statement仍没有accepted原始样本；外部资格缺口不因V2单测通过而消失，production_qualified=false，不能声称真实到账/日切E2E已通过。
- root负责runtime/execution/report集成、独立V2审查、不可变新manifest和后续真实证据。已请求新独审，未在本记录预先宣称PASS。

## 反思/后续

- 开始/结束过拟合判断：否。真实人工资金时滞暴露执行合同错误，修正不看历史收益、不改alpha或资金比例、不扫参数。
- 开始/结束继续价值判断：是。避免旧建议变债务及过期锁死，同时保住真实现金流守恒与稳定原生信号只消费一次；下一步是独审与真实来源资格，不是补资节奏/金额寻优。
- 不改LINE/registry/根总账、不碰生产、CTP connect/银行/SMTP/Git index/commit。
