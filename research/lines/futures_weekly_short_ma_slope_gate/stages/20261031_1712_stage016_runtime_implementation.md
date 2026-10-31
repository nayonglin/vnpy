# Stage016 原 C 周线 runtime 薄适配实现封批次

- line_id：futures_weekly_short_ma_slope_gate；day；记录时间：2026-10-31 17:12:33（北京时间）。
- 工作树：/Users/mac/.codex/worktrees/weekly19-official-20261031/fian；分支 codex/weekly19-official-20261031。
- 本轮性质：按已授权迁移合同的工程实现；不是金融回测或生产资格。是否重要突破：否，执行语义落地。原Stage014经济结论和NO_PROMOTION不改变。
- 原冻结树只读，未修改原source/outputs/financial ledger；未接CTP、邮件、网络、生产、Git index、commit或push。

## 调研与判断

沿用本线20261031_1555_stage016_runtime_design.md的原源码及VeighNa官方GitHub调研。判断：保留原类和方法，真实账户、成交和异步生命周期由薄adapter约束；不得直接将旧C9 CURRENT导入链或盘中stop当周线规则。本机现有组合模板与原vendor模板SHA相同，未安装/升级依赖；不同SQLite驱动不用于此runtime，后续只读DTO数据reader另验证。

## 代码与固定资产

新增 qmt_roll_weekly19_runtime.py，weekly19_frozen/，weekly19_assets/，tests/test_weekly19_runtime.py 和 test_weekly19_strategy_equivalence.py。31原始源码（整模块仅imports归位，或五个完整原类+原helper/constants）分别对原Stage014实际input_manifest SHA核对；565个类/函数AST条目逐项一致。另保留88原始静态导入依赖的provenance，不把历史报告与旧CURRENT解析器带入运行；固定模板和项目guard字节也纳入证明。包__init__另做hash闭包。复制的CSV只有原19池、structural prefilter、portfolio eligibility；没有原始行情、DB、秘密或模型。

完整actual settings来自原真实C，原source SHA 360190915781cdbdbf92ef3d3005a6205f9b7e0d4a65644d8bcb298241a47199；路径仅改为显式ASSET/INPUT/EMPTY/DISABLED依赖，cold_start_date由真实新release资金state绑定。交易参数新增/修改/删除均无；所有原风险与换月设置保留，已加载参数漂移会在原on_bars前拒绝。

## 原规则及真实状态边界

- MRO保留Stage847→830→827→804→772→qmt核心，以及ThreeMa/NoMacd/Stage029v1+v2、Stage032False、short bottom20、HistoricalSafety。无自动reserve transfer wrapper。
- 纯warmup只更新AM，不运行历史on_bars，不造仓、target、资金建议或订单。
- broker Balance是唯一E，Available是额外执行上限；不把research交易成本、MTM或转账再加到E。E<=0不能通过or base_capital重新开仓。
- 原native候选通过weekly stop和short range后、parent sizing前登记原funding admission。资金模块返回建议；未确认不增加E。后续新账户generation/重价/重计划不得创造第二个资金候选。
- send/cancel facade只生成intent。position root/cycle/epoch为weekly自己的durable身份，初始entry可预分配，但不声称已成交；实际fill才改变pos，真实层保留各自cost/stop、signal/order身份，partial open取消只撤未成交层。
- 完整tagged JSON状态（无pickle）保留ProductState/Layer/AM/risk/roll/targets/pending/lifecycle/真实事件去重。已接受history prefix必须不变；允许追加未来数据及新合约；无完整保护层的外来实仓拒绝。
- 价格保护只fresh完成周close，非tick触价；日级风险与5日换月仍走原循环。日历延伸下一ISO周，行情截止target；原next trading day对夜盘可落在周五21:00。

## 已确认的异步执行协议及与研究模型差异

原_close_layers/_reduce_position_to_target会先以计划价更新realized_pnl、direction outcome和streak，再等回测完整成交；_sync_close_trade只补实际价差，不能自行修复“实际输赢符号变化”。root已明确批准本adapter协议：计划风险副作用冻结；捕获close前完整保护层和原lot顺序；实际partial fills只减少真实已成交量，实际PNL不加brokerE；cancel/reject保留剩余真实保护与reduce-only lifecycle，fresh broker+quote后只重试remaining。全部close/reduce目标实际完成后，以实际累计PNL调用原outcome/streak一次。源方法AST不变，实际成交时点与计划价记忆的差异明确存在，不能声称复验了59条原金融轨迹。

未终结跨日只更新AM与保存bar queue，保留真实保护与风险记忆，不回填历史opens；恢复后仅补原day-count/roll-delay时钟，再处理新的完成日。换月只有旧仓真实flat、现金交易日链正确、fresh目标quote及当前原sizing允许后才发续仓意图，手数不超过原实际仓量。

revalidate_open_intent在clone上按当前E/Available与当前bid/ask、原signal/history/weekly stop调用原sizing；不推进真实AM/日级风险记忆/资金建议，cap原批准未成交量。replan_after_confirmed_funding只在实际资金证据后重新批准原0量/小量且未发送的local候选，生成新的source-bound订单ID；原funding admission不变，同现金证据重放幂等。已真实fill或broker绑定的旧计划不能直接改大；信号过期不追单。

真实回报保留onRspQryOrder/Trade与onRtnOrder/Trade身份；同batch必须先fills后累计order状态。业务offset open/close与native broker_offset（open/close/closetoday/closeyesterday、0/1/3/4）分列，原rawSHA不变，parent qmt只收到业务Offset.CLOSE以正确消费pending lots。真实经济事件按稳定业务语义去重，查询generation/observed/raw capture SHA变化不重复记账；业务字段冲突则拒绝。delivery W19EXEC身份与原planned/signal身份由provider/执行ledger保留完整映射，本runtime拥有原业务ID。

## 公共接口

- build_weekly19_runtime(settings_asset, metadata, session_calendar, physical_epoch_daily, broker_snapshot, durable_state, confirmed_cash_state, *, clock=None)
- Runtime.warmup(real_bar_batches)
- Runtime.process_completed_day(trading_date, bars, data_receipt, broker_snapshot, confirmed_cash_state) -> decision
- Runtime.apply_order_update(envelope) / apply_broker_fill(envelope, signal_identity)
- Runtime.reconcile_broker_snapshot(snapshot, cash_state, *, quote_snapshot=None) -> fresh E/Available与retry/rollover intents
- Runtime.revalidate_open_intent(intent_id, *, broker_snapshot, confirmed_cash_state, quote_snapshot) -> 只读原风险proof
- Runtime.replan_after_confirmed_funding(signal_identity, broker_snapshot, confirmed_cash_state, quote_snapshot)
- Runtime.export_state() / execution_state(intent_id)

metadata必需product_symbols、vt_symbols、source_symbol_by_contract、daily_mapping、sizes/priceticks/margin_ratios/rates/slippages；physical Frame必列vt_symbol/date/contract_epoch_id/open/high/low/close/volume，正量真实数据。bar为同一交易日真实BarData；data_receipt schema weekly19.data-receipt.v1含trading_date/complete/material_release_id/source_sha256。decision.trading_date是已完成来源日，intent.trading_date是下一实际交易日，另分target_date/completed_target_date/next_execution_day。

state_sha256覆盖全部交易/资金/风险/输入状态；缓存中的after_state_sha256是指向同一digest的派生字段，仅该自引用annotation被digest规范化排除，避免循环。该字段与结束时export_state的state_sha实际一致；外部私有状态文件仍应另绑完整文件SHA与CAS/WAL。checksum不是恶意同用户篡改的身份认证。

## 验证与问题记录

Owned runtime/equivalence：26 tests绿，565 AST条目逐项核对；本轮日志：20261031_1712_stage016_runtime_owned_tests.log。

曾跑全weekly suite 157项绿。锁前新一次全weekly discover 193项，183绿、10红；失败全是root刚加入但尚未实现的live_pipeline setUp“pipeline implementation missing”，完整保留20261031_1708_stage016_runtime_full_weekly_tests.log，不能称当时全仓绿。root随后通知state10+pipeline10已绿；此处不替代其独立最终资格suite。

已捕获并修复：OrderType恢复白名单、原entry_date YYYYMMDD匹配、derived after-state hash自引用、原native offset映射、跨query经济事件幂等、原funding候选稳定、无层实仓和参数漂移拒绝。保留所有源和旧金融账本，不用改alpha救测试。

期末权益/总收益/DD/Sharpe/滑点/交易次数/胜率：本轮均N/A，无金融回测或新增收益声明。所有生产资格字段仍false；fixture不证明真实provider、盘口、容量、真实费用或broker可部署性。实盘资格、真实capture authority、orders/trades桥、daily writer、release/activation/master/Stage948由root后续完整审查。

## 反思与合入建议

运行前/后过拟合：本轮否，固定规则和工程事件边界，无窗口/阈值/品种寻优；原历史选择与非OOS限制继续保留。继续价值：是，真实资金/异步成交/状态恢复错误会直接改变风险，值得完成source-bound独审。原方法保持不等于原全部金融路径自然通过。

本轮只新增本线stage，暂不改LINE、registry或根总账。等待独立review；重要或严重缺陷必须修复后重新封SHA。root独占Git/index/commit与正式发布。本批次接下来可读数据reader单独实现，原金融结果不动。

## 本批次SHA

```json
{
  "examples/portfolio_backtesting/qmt_roll_weekly19_runtime.py": "659b1f46ab6661fa8aa5306746a585be1a9205a77789fe80eef3747c62137b4c",
  "examples/portfolio_backtesting/weekly19_assets/actual_settings.json": "513ef478b031ad819dd0a81baf11b76f1fee1bad8671de6526966ad68e6b71ab",
  "examples/portfolio_backtesting/weekly19_assets/source_manifest.json": "b473e88f21d2d139615e638c9df0e0fac5358596d919624f55411438926a303c",
  "tests/test_weekly19_runtime.py": "f47ed323efdf21d7e1105e8e48f740fddf812257a1709ae3f058495a22d511e8",
  "tests/test_weekly19_strategy_equivalence.py": "ef03927995ea9c7cec41f43952f08c58d99700b64f786017bfaf89c46ba025cd"
}
```
