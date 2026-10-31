# Stage018 人工资金模式合同预审

时间：2026-11-01T04:30:54.689415+08:00；研究线futures_weekly_short_ma_slope_gate。结论DESIGN_CONDITIONALLY_ACCEPTED_IMPLEMENTATION_NOT_REVIEWED：设计方向与用户Stage017责任调整相符，具体代码和接线尚未由本审查接受。

已读20261101_Stage018_manual_cash_design.md，按实际字节复制为Stage018_review_manual_design_input.md。用户明确不再要求自动最终日结解析及自动银行到账producer，因此不把两项继续列作必须开发的阻断；改为诚实记录operator_manual责任。不能因此取消真实CTP账户/持仓/报价及新release/activation来源资格。

必需合同与反例边界：

1. 人工现金来源与broker自动核验分列：operator_manual，不生成自动HMAC，不赋source/production qualified；人工记录不是订单许可。

2. E与Available永远来自当前fresh/source-qualified真实CTP；手填金额/余额差/历史模拟仓位不能credit账户；真实持仓、订单、报价、session/原风险全部仍验。

3. 新生产模式及manual目录是immutable context；缺mode不能默认通过。人工文件只append私有cashrefs，由同actor+PipelineStateStore CAS消费；CLI不直接写活跃fund/runtime。

4. 唯一record_id和receipt_id跨review去重；同id异bytes拒，已消费不重复扣R或续期；R+T=15000000分，T/R非负，上限不变，提现不恢复R。

5. 同TradingDay gross Deposit/Withdraw非负且不低于已知checkpoint，closed_days final也不得倒退；新增Deposit逐笔人工T覆盖，未知cash不silent ready。

6. 所有闭日按实际交易日历精确覆盖并有单调时序；真实TradingDay处理Friday夜盘到Monday，不用自然日猜测重置；无自动final parser仍可用明示人工责任。

7. 30分钟是未消费review受理窗口，已消费历史事实不因过期抹掉；新现金计数/TradingDay仍需新review，不可永久toggle豁免。

8. 原fund revision/checkpoint/amount/release/account/request/admission/data source全部绑定；stale或错误refs不得部分消费或吞掉失败。

9. 落人工文件、cashref CAS和actor消费三个状态分清；失败显示pending并保留原bytes，重试不延寿、不重复入账；恢复需与实际store一致。

10. 建议不是债务，E恢复15万不强迫补旧差；缺人工记录只限制未核现金支持的新开，保留真实减风险/平仓路径。

这些是后续实现验收要求，不是已经跑过的测试。尤其CLI成功写记录不代表已入账；人工核验不等于broker自动证明，也不把T再加一次E。设计本身无已确认P0/P1缺陷，但同日gross数单调、跨review receipt去重、故障不部分消费和三阶段状态恢复应在实现中明确证明。

截至10月30日信号独立复算另已通过：19原始交叉/候选/intent均0，与资金模式是否实现无关。该离线15万空仓假设不形成正式actionable或生产daily receipt，不得倒签cohort追历史信号。

本轮只查本机合同与冻结原始数据；明确禁止HTTP，未做外部网络调研。遵循实盘SOP的来源分离原则；Stage017用户新决定优先于旧自动现金flow要求。过拟合判断否，未改alpha/风控金额/阈值；继续价值是，人工责任、R/T账与真实E的边界需可操作且不可混淆。无金融回放/CTP/SMTP/银行/订单/生产/Git/index操作，不创建定时任务，11月2日09:00前不重试CTP。
