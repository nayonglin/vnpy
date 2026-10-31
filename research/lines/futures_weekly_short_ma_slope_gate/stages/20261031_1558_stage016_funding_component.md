# Stage016 真正场外15万备用金：建议/到账状态机组件

- line_id：futures_weekly_short_ma_slope_gate；当前模式 day。
- 记录时间：2026-10-31 15:58 CST。
- 工作区：/Users/mac/.codex/worktrees/weekly19-official-20261031/fian；原研究树只读。
- 阶段性质：周线19正式候选的资金执行纪律组件；不是策略alpha、不是新回测、不是实盘资格。
- 是否重要突破：否，修复研究模拟转账与真实场外到账之间的语义边界。
- 是否触发A/B：否，本组件不改变信号、止损、风控或选量；不调用银行/CTP/SMTP。
- production_qualified=false；下面fixture全部是手工测试证据，不能作为真实券商现金流/E2E证明。

## 外部调研与判断

- 调研：[vnpy_ctp官方源码](https://github.com/vnpy/vnpy_ctp/blob/main/vnpy_ctp/gateway/ctp_gateway.py) 的账户推送保留 balance/frozen/available；[SimNow官方CTP Mini文档](https://www.simnow.com.cn/DocumentDown/api_3/5_2_4/CTPIIMini_API_Ver1.0.pdf) 区分入金、出金、交易日与余额。
- 当前仓库 qmt_roll_official_live_broker_account_snapshot.py 的合格 sizing 快照只保存 Balance/Available/CurrMargin/Frozen*，缺Deposit/Withdraw/TradingDay；Stage655原始探针虽有Deposit/Withdraw，但并不等于新的完整真实现金流capture资格。
- 判断：账户权益上升可能是未平仓MTM，不能作为入金凭证。仅哈希一致证明原始字节未变，不证明源头真实。必须由后续独立qualified capture adapter负责真实券商原始凭证来源/完整性，本组件只核对边界、原始字节哈希和现金流守恒。
- Stage014 research/tools/stage014_reserve.py 会直接加 settled_balance；本组件未复制该模拟转账。所有建议都不加交易权益，只有真实流水与账户日累计Deposit精确匹配后才扣场外R。

## 本次变更

- 新增 examples/portfolio_backtesting/qmt_roll_weekly19_funding.py：无入参修改的资金状态机。
- 新增 examples/portfolio_backtesting/qmt_roll_weekly19_funding_store.py：0600文件、0700私有父目录、全路径O_NOFOLLOW、不接受hardlink、flock锁、revision CAS、WAL先写、原子rename/fsync、重启按下一revision恢复。
- 新增 tests/test_weekly19_external_funding.py：36个unittest行为测试。
- 新增参数：固定初始交易150000元、真正场外R150000元；新原始账户/银行现金流/交易日关闭continuity证据schema；账户证据最大年龄300秒；请求7日过期（等于expires_at即过期）。所有金额strict decimal字符串进入、整数分存储，时钟必须带时区。
- 修改参数/删除参数：无；未修改任何alpha配置、旧研究账本或生产物料。

## 固定资金规则和接口

1. 上游先完成原生new-entry admission：flat/reverse，long_case1a/long_case2或short_case1a，有效已完成周stop，short bottom20门通过；在parent sizing前传admitted_entry_ids。不能要求最终selected_volume>0。
2. 有有效新候选且E（原始Balance，含未平仓MTM）<150000时，T=min(150000-E,Rleft)。无信号不请求；盈利不回补R；只发建议，不把R或建议额加进E。
3. initial_state(account_key, material_release_id, cold_start_date) -> state；账户key为SHA256(BrokerID+NUL+AccountID)。
4. recommend_topup(state, broker, target_week_end, admitted_entry_ids, source_sha256, now) -> {state, recommendation}；同一admission不重复建议，pending不叠加新请求。
5. confirm_topup(state, request_id, cashflow_receipt, broker, now) -> new_state；原始流水SHA、账户/release/request、银行receipt ID、名义交易日、金额、时间、请求前Deposit/Withdraw基线与当前日累计Deposit增量必须全部一致。部分入金仅扣已证实额，仍阻新开；超额/未知入金或出金/过期/乱序全阻断且不部分扣R。
6. reconcile_trading_day(state, closing_broker, next_broker, now, continuity_receipt=...) -> new_state；需要券商最终day-close凭证绑定关闭账户raw SHA、最终Deposit/Withdraw、完整性和下一个权威名义交易日，并有下日零现金流起点。可携pending跨周末；周五21:00观测但TradingDay为周一合法，不能用UTC/自然日差代替交易日。没有连续证据一律阻断，不凭权益差补证据。
7. assert_open_funding_ready(state, broker, now) -> None或FundingError；只有pending资金才额外阻新开，R耗尽且E仍为正不永久封禁原风险；E<=0阻新开；冷启动按broker名义TradingDay。此函数不构成下单/生产资格，退出减仓不经过它。
8. FundingStore(path)要求已存在的私有0700父目录；create(initial_state)仅一次，load()先恢复journal，commit(old_revision, new_state)必须在发布建议/放行新开前完成。历史receipt、admission、请求身份、已扣R与cashflow checkpoint不可倒退。

## 原始证据 envelope

- 所有输入使用 {raw_payload: UTF8原始JSON字符串, raw_sha256: SHA256(raw_payload字节)}；拒绝重复JSON key、NaN、float钱数、子分位、无时区和仅verified:true。
- 账户raw：schema=weekly19.ctp-account.v1、source_kind=ctp_account_callback、account_key、material_release_id、observed_at、trading_day、generation_uuid、query_reqid、query_complete=true、CurrencyID=CNY、BrokerID、AccountID、Balance、Deposit、Withdraw。
- 流水raw：schema=weekly19.bank-cashflow.v1、source_kind=broker_cashflow_receipt、account_key、release、request_id、trading_day、occurred_at、receipt_id、Amount、Direction=deposit、Status=completed。
- 日切raw：schema=weekly19.cashflow-day-close.v1、source_kind=broker_cashflow_day_close、account_key、release、trading_day、next_trading_day、closed_at、closing_account_sha256、Deposit、Withdraw、cashflows_complete=true、statement_id。
- 字段material_release_id在三类schema内名称完全一致；上文release只为说明简写。

## 验证与限制

- TDD首轮：实现前24/24失败（external funding component/store absent），建立缺失功能红灯；实现后先发现1个fixture参数重复问题并修复；跨日/单调账本新增测试先红后绿；进一步自查新增5个失败和1个错误后逐项修复。
- 最终命令：.py311/bin/python -m unittest discover -s tests -p test_weekly19_external_funding.py -v。
- 最终结果：36 tests，exit=0，OK。覆盖建议不虚增E、部分/重复/超额、未知资金、账户/release串用、过期/乱序、名义日切、pending跨周末和部分跨日续完、重启journal恢复、CAS、防旧账复活R、权限/软硬链接及hash篡改。
- 3个源/测试文件已用Python compile内存编译通过；未生成额外字节码。最初py_compile尝试被沙箱禁止写__pycache__，之后改用内存compile并通过。
- 没有运行金融回测；期末权益/总收益/回撤/Sharpe/滑点/交易次数/胜率/payoff/PF均不适用，旧回测结果全部保留。
- 未发现真实accepted broker/银行/连续现金流provider；未配置到账CLI/银行自动转账/邮件发送器；真实资金确认E2E未执行，production_qualified=false。不存在凭fixture晋级或声称真实到账已验收。
- 只验证该隔离组件测试集；全仓历史suite由合入者按统一发布范围验证。独立代码审查由root组织，最终审查结论另记。
- 当前没有自动消解未知现金流或过期未完成请求的operator reconciliation命令，保持fail-closed，必须通过下一阶段具体真实凭证设计；不得手工编辑R跳过。

## 过拟合及继续价值反思

- 运行前/后过拟合判断：否。组件固定执行现金守恒，不看历史收益，不搜索参数，不改变alpha；不把较好资金曲线当成策略性能。
- 运行前/后继续价值判断：是。真实场外资金与研究模拟转账不可混同，本组件可防权益虚增、重复扣R与未到账开仓。后续价值在真实capture/连续流水资格、独立安全审查和完整production链集成，不在新参数扫描。

## 合入建议

- 只新增本线唯一stage文件，本agent不改LINE.md/registry/root总账/Git index，也不commit。
- 下一步：root审查接口/边界，并接真实capture adapter及邮件建议、执行前资金gate；真实流程未合格前不得以这36个fixture测试作为live-ready证据。
- 源码SHA256与测试日志见同前缀manifest.json和unittest.txt。
