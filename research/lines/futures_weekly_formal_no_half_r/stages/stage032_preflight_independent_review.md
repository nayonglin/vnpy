# Stage032 数据、入口与日K加仓独立预审

- line_id：futures_weekly_formal_no_half_r；记录时间：2026-10-28T16:54:48.670051+08:00。
- 结论：**PASS_BOUNDED_A_C_FINANCIAL_REPLAY_PREFLIGHT，允许按冻结规则运行 A/C 金融回放**。当前未解决 P0=0、P1=0、P2=0。此结论不是金融结果通过、完整市场真值、PIT/OOS或生产资格认证。
- 审查者未参与实现；未改工具/数据，未跑金融历史，未下载新行情、未连接交易/生产、未提交。仅写本独有阶段文件和review outputs。

## 独立核验结果

1. 新source_manifest的2607绑定、Stage031旧3603绑定均逐文件重算，零缺失/变化。旧physical daily与mapping保持逐字节前缀，metadata/physical_epochs逐字节不变。
2. SQLite旧1,345,673行以全字段EXCEPT核验缺失0；新1,345,729行，恰增56。28合约×10月27/28各1行；56行来源定位、OHLCV/当日closeOI、SQLite完全一致，28个overview计数/首末日一致，integrity_check=ok。正量、物理年代与生命周期检查通过。
3. 新增38主力mapping覆盖原19品种两天；冻结R003终仓/pending与主力合计40必要键无缺。10月28日探针16:29:23—16:29:53，晚于15:30；10月29不入批准日K，10月28不作为完整周。
4. 10月27日后续同供应商观测对jm2701、lc2701、lh2611、lh2701有volume/closeOI差异；保持既定Stage283权威而不覆盖。不能据同源对齐声称交易所最终真值。
5. runner经s901→s847把START设为2020-01-01、建立新engine与15万元账户，最多一年预加载；trade_start_date阻止预加载期交易，因此不是旧权益切片。全实际settings/effective仅允许日期、mapping及显式批准的新元数据差异。本次无新metadata。原19、周MA5/10/20、MACD/全部AI/short_case2/RSI/0.5R/C2/原加仓/减半禁用链保持；实际addon开关与请求臂核对，A返回原Stage029v2类。
6. 撮合由真实同约下一交易日日K open和独立calendar时钟构成，分钟与proxy访问被禁。runner仍必须检查实际held/traded逐日正量覆盖、21完成周readiness、epoch、实际账户日期、退出、open、输入postflight等；缺项必须fail closed，不能因本次数据预审跳过。
7. 静态审阅tagged layer/net target/reconcile、pending锁、真实fill计次、固定stop、退出当日重计、roll随平/名额继承、周技术局部隐藏与账户风险可见。实际父Stage847→Qmt update_trade微型核验：base2@100＋addon1@106→全平@104，毛利80−20=60；测试费率0.1%与1跳总费用44.18，分配守恒且pending lot清空。该测试费率仅合成验算，不修改研究的零手续费设置。
8. 实际父类forced-margin consumer微型核验：真实3手发目标1手，先addon再base；重复调用无重复平仓。次日平2后仅剩base1，毛利20、成本33.14，reason一致、归属和余量守恒。

## 发现与修复闭环

- P1（已修）：原开盘检查把同日不同品种各自冻结容量独立使用。最小反证D2两单保证金103+103=206，D3一单104、另一单103，两单皆放行导致207>206。保留失败脚本、JSON与原源码SHA475a2cd5…f66c34a，没有运行金融历史。
- 修复引入全pending共享预留、执行时序开盘差额、取消释放和cluster单独调整；普通base open仍由原引擎执行，已知margin gap只影响后续addon。最后补入同约既持base在已知open的margin差额。
- 独立重验24路径（3品种、4组价差/取消、6种顺序）全通过；检验总新增margin加已知底仓mark差额不超共同容量。负向底仓margin差额释放属于同一会计口径，不能只加新增margin而遗漏合法释放。不同cluster、真实adapter engine普通parent gap、取消释放均通过。故意设置未来D3close及self equity/margin极端值，不改变冻结预算判断。独立手算D2 base2×103＋拟addon103、cap310，D3open104时312>310被拒绝。
- P2（已修）：风险消费者先close_layers后record_event时，base allocation曾可能继承旧reason；现在显式exit_reason同样进入base/addon队列，独立重验通过。
- 最终adapter SHA：`560232fcf1227a37f3d6c81613db422d6bdfff1472da4070e855eb87a77aadac`；test SHA：`a8ba5011774da0f3ce2874fa486ee1b29d60335d896e9251746108e808139dd7`。所有其他审阅源码与证据SHA见同名JSON。

## 边界与后续

- 开盘准入采用D2冻结容量加已观察D3open保证金变化；未观察其他合约保持D2 marks、普通基仓原成交保持既有模型。这是可复验日K实验，不是实时全账户券商风控/可成交证明。
- A/C每次回放后必须新的独立结果审查，核对实际信号与fills、逐笔归属、总PnL/费用/终仓/日权益以及实际数据覆盖；预审不预判收益改善。
- 新增/修改/删除回测结果：均无。期末权益、收益、DD、Sharpe、滑点、交易次数、胜率尚无本次金融结果。审查不修改策略规则或参数。
- 外部调研：复核Tq官方API文档和GitHub源码，86400秒为日线、close_oi为K线结束时持仓量；判断采用closeOI映射是明确且可追踪的，供应商语义不能替代交易所真值。来源：https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html 与 https://github.com/shinnytech/tqsdk-python/blob/master/tqsdk/api.py 。
- 开始/结束过拟合判断：本次正确性审查没有优化或挑参数；策略想法仍是同历史样本内研发，存在开发偏差，固定规则和禁止救参不产生OOS。
- 开始/结束继续价值判断：有。已在金融回放前排除具体共享资金漏洞，可做一次固定同源A/C对照；结果不满足预定门槛就保留失败，不救参、不晋级。
