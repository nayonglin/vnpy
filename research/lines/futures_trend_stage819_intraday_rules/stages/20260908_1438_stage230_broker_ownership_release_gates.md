# Stage230 真实账户定量的持仓归属与发布闸门补齐

- line_id：futures_trend_stage819_intraday_rules
- 记录时间：2026-09-08 14:38（北京时间；本轮工作持续更新）
- 用户确认：同意先修复 Stage229 阻塞，再进行发布验收。
- 工作区：`.worktrees/live-broker-account-sizing`；分支：`codex/live-broker-account-sizing`。
- 基础提交：`d492ee072aa5a9d71477235d79f17d2a5db59db3`；本候选尚未提交。
- 是否重要突破：否。执行安全修复，不是 alpha 版本或策略收益突破。
- 是否过拟合：否；未搜索参数、未产生回测结果，只验证实际资金、持仓归属、委托证据和并发边界。
- 是否值得继续：是；不能让真实账户定量上线后，因影子手数不一致而无法解释退出，亦不能擅自认领手工持仓。

## 代码变更

1. Stage931 新增有超时和查询节流的持仓明细查询。只接受同一请求号、完整末包、正确账户和券商交易日；拒绝串号、错误、重复末包及缺包。
2. 重定量全平按 `持仓明细 → 成交 → 委托Q1 → 持仓 → 委托Q2` 获取连续五个请求号的同连接证据。每笔剩余开仓明细必须精确关联到唯一 owned root/epoch；账户、TradeID、日期、价格、数量和 ledger 净仓同时成立。
3. 全平只读证据新增完整 ledger checksum 检查。每次查询完成即冻结 callback seal；proof 使用已经校验的冻结副本，之后只比较，不重新吸收迟到回包作为基线。独立 reviewer 发现的“校验 seal 后、返回 proof 前”窄窗口已增加故障注入回归。
4. SHFE/INE 只允许由已证明的今仓/昨仓桶组成的完整拆单；验证每个子单的合约、方向、价格、类型、数量、offset、顺序及原生请求号。错误子单、外部事件、连接变化、证据过期继续拒绝。
5. 原始 `onRtnTrade` 采集券商自然成交日、交易日、投机标志和账户指纹；与 EVENT_TRADE 的身份和经济字段精确一致后，独立追加 `broker_trade_ownership_metadata` sidecar。不得改变 canonical fill，避免实时回报和查询回报的幂等冲突。sidecar 只能补齐同一真实成交已有但缺失的元数据，不能创造历史成交或根仓位。
6. 旧 sent 只有在不可变 payload 或同 lease、checksum 有效的 ledger 已存在明确账户绑定，且新鲜完整快照证明全部 owned 实际订单终态时，才生成独立 legacy reconciliation proof。沿用 spool 原子 CAS；不改 payload/hash，不补造旧 sizing audit。没有历史订单证据仍拒绝。
7. 新增 5 个 broker 模块及 10 项新增测试纳入生产 critical 清单；必跑 qualification suite 从 41 增至 52（另补 Stage174 查询测试）。新增文件覆盖、去重、依赖闭包检查。

## 不变项

- 未改变 C9 信号、AI 池、0.5R 开仓日止损和最多一次 retry。
- 未更改 alpha 参数；没有新增、修改或删除任何回测结果，收益/回撤/Sharpe/滑点/胜率等指标不适用。
- 真实权益定量仍使用 Stage228 的 Broker Balance/Available/CurrMargin/Frozen 口径及既有风险上限，未以缩短止损距离为由放大手数。

## 外部资料与判断

- 核对 [vnpy_ctp 官方头文件](https://github.com/vnpy/vnpy_ctp/blob/main/vnpy_ctp/api/include/ctp/ThostFtdcUserApiStruct.h) 和 [官方 gateway](https://github.com/vnpy/vnpy_ctp/blob/main/vnpy_ctp/gateway/ctp_gateway.py)。CTP 分别提供 OpenDate、TradeDate、TradingDay；vn.py 成交时间取 TradeDate/TradeTime。不能把业务 target_date 当作券商 TradingDay。
- 调研否决：没有足够 primary 证据证明 OpenDate 可以任意等同于 TradeDate 或 TradingDay，因此不接受“两日期任选”的推断。日期不一致需可信且精确绑定的 broker_open_date；本轮未为缺证据的历史仓位生成该字段。
- 旧 sent 迁移复用 [SQLite 原子事务](https://www.sqlite.org/atomiccommit.html)，不另建可绕过现有状态机的存储。

## 生产只读审计边界

- 本轮独立审计读取实际生产 runtime/state spool，并在内存应用已提交 WAL。该快照的 intents/sent 均为 0；不能声称线上存在需要清理的旧 sent。
- 同次 ledger 快照为 345 行，包含 196 条未归属订单回报、93 条未归属成交回报、56 条持仓回报；checksum 通过，但正式 intent/fingerprint/fill 绑定为空。这不是持仓自动接管授权，也不证明此刻券商仓位。
- 当前生产仍为旧 d492ee07 对应版本；本轮没有安装、激活或重启生产，没有创建新 CTP 连接，没有调用真实下单/撤单。既有生产 daemon 的自主活动不属于本轮操作，不能从离线测试推断它的交易状态。

## 验证与剩余发布条件

- TDD 已覆盖明细查询、跨日已归属全平、夜盘自然日与交易日分离、今昨拆单、错误原生子单、旧 sent 迁移、canonical fill 幂等、sidecar 归属和迟到回包竞态。
- 最终统一测试结果将在本文件末尾记录；局部绿灯不等于正式 production qualification。
- 保留阻塞：历史仓位缺策略归属；OpenDate 与已证明日期不一致且无独立历史证据；候选未提交；新不可变 material、独立资格、两次正式生产只读采集及新 release 绑定尚未完成。
- 不借用旧版本 949 passed、两次只读采集和旧 review 作为本候选资格；不手改 stable HEAD、manifest、CURRENT 或 plist 绕过 Stage948。
- 最终实盘自动交易启用由用户执行；当前工作只完成离线修复、检查和交付准备，不代替该操作。

## 14:43 完整离线验收回执

- 执行 `PRODUCTION_REQUIRED_TEST_SUITES` 的全部 52 组，使用项目 `.py311/bin/python -m pytest -q`，设置 `LANGUAGE=zh_CN`、隔离 `OFFICIAL_LIVE_OUTPUT_DIR=$PWD/.test-output` 和 `QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR=1`。
- 本次结果：`1395 passed, 3 failed, 825 subtests passed`，耗时 497.21 秒。运行期间后续小修以最终聚焦回归另列，不把该结果包装为最终 clean-commit qualification。
- 两项 Stage037 规则一致性测试缺少当前 worktree 的本地结构池依赖 CSV：`qmt_roll_full_market_structural_prefilter_eligible_full_market_structural_prefilter_v1.csv`。未生成替代数据、未重跑回测、未改规则来迎合测试。
- 固定生产压力测试失败：20 品种、2000 tick/s、60 秒、writer delay 25ms，`durable_lag_p99=112.661875ms`，超过既定 `100ms`。120000 tick，正式压力测试的 send/cancel 计数为 0；没有改变阈值或抹掉这次失败。
- 补充修复 raw 回报缓存失效：同交易身份的合法→非法→合法、非法→合法两种序列均不能重新继承旧 verified metadata；异常需在独立冲突事件中持久化，归属 validator 继续拒绝。
- 独立 reviewer 已复现并确认关闭迟到回包及 raw 缓存污染路径；冲突 sentinel 的 validator 补丁另做最终聚焦验收。
- 生产 checkout 再次只读核对：HEAD 仍为 `d492ee072aa5a9d71477235d79f17d2a5db59db3`，tracked clean。本候选没有推送、正式物料发布、Stage948 prepare/activate 或 launchd 修改。
- 后续独立依赖审计发现原 checkout 有该结构池 CSV 及 `qmt_roll_ai_product_pool_shadow_portfolio_eligibility_ai_product_pool_shadow_v1.csv`，但未在 immutable manifest 中证明这两个原始输入已冻结。未将原 checkout 的共享 backtest_outputs 链接到测试区，也未把旧 Top8 父级 builder 输入当作当前正式 AI 池。
- 压测失败发生在测试的 TemporaryDirectory 中，退出后原始临时 JSON 未作为正式 bundle 留存；本记录仅保存测试回执及关键指标，不能冒充正式性能资格证据。后续应先确认 taskpolicy、并发及 I/O 条件，保留原失败，再决定是否进行一次固定配置的隔离复现；不反复试到变绿。

## 14:47 最终聚焦回归与结论

- 所有代码小修和 conflict sentinel 落盘后，重新运行本次影响的 24 组测试（Stage174、五个 broker 模块、Stage905/941、spool/reconciliation、Stage901、Stage930/931、授权、release manifest）：`835 passed, 623 subtests passed`，137.63 秒。
- `compileall` 及 `git diff --check` 通过。此后只追加本记录，没有继续改变代码。
- 独立 reviewer 的 raw 缓存污染路径已经关闭；新增 sentinel 对同 symbol、缺失 symbol、空 symbol 均 fail closed，其他明确 symbol 不影响本目标；最终聚焦组包含这些用例。
- 最终状态：本地安全修复已推进，`production_release_not_qualified`。完整 52 组的三项失败、生产存量归属/夜盘 OpenDate 证据缺口、候选提交与新物料资格仍未闭环，不执行实盘启用。
- 结束反思：不过拟合，未变策略参数或以回测取舍；继续有价值，但下一步必须解决证据与性能资格，不能继续扩大功能或降低门槛来促成上线。
