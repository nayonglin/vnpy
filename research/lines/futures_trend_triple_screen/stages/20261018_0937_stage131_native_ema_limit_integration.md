# Stage131：独立EMA限价定价、预算与真实native接合

- line_id：`futures_trend_triple_screen`；模式day；2026-10-18 09:37 CST；实施约09:30—09:37。
- 当前root指定分支，同一工作区，无Git操作、无worktree。仅Stage127 Task2/4，非重要突破，不创建金融臂/readiness或生产资格。
- 已读registry、124/125/126/127及128 ledger；Task1已由129封存，Task3作者130完成并明确交接测试文件后，才追加其两个native组合方法。未修改LINE、registry、128 ledger、其他研究线、027/028/035/065/109或native源码。

## 调研判断与本次边界

沿121/123既有原著、作者官网与GitHub有限调研，不重复联网。透明的EMA穿透适配可以定义，但没有唯一作者算法或alpha证据；只有真实经济链和因果约束可先组件验收。本次继承root126的两项裁决：错误侧gap仍记初开、同母保护close、R=N/A、不retry；合法R原retry仍是F reclaim，可越L。本次不改窗长、撮合口径、成本、原风险recipe或OFF八键。

## 版本改动

新增`tools/stage127_ema_limit_strategy.py`及`tools/test_stage127_ema_limit_strategy.py`；在130交接后扩展`test_stage127_ema_limit_engine.py`，只追加计划的两个真实native组合和相关新fixture调用；`stage127_ema_limit_engine.py`保持130原SHA。

定价层在真实847→830→827→804→772→qmt MRO中插入局部价格适配，先用原S验证signed距离，再把L传给035已冻结纯定价算术，避免错误侧进入abs。原bar/history不改，OI、连败、风险倍率、minimum-risk与各整数cap继续原路径；非flat/add沿原价与原native路径。最终gross前缀只缩量、不回收、不补位，正q只在原snapshot循环位置reserve一次。OFF工厂仅用`dataclasses.replace`投影原八键，不调用旧arm工厂/prepare，不载入模型或实例化金融engine，输出新机制及`financial_ready=False`。

新策略在planner前观察周/FI与u资格特征，execution_tick必须来自调用者交付的u资格feature，不用configured风险/成本tick代替；Task1独立状态/ID贯穿。真实heap pop才沿028通用激活开仓，`ts_commit_fill`自建新审计并只消费一次，不先写C/B审计再改owner。已有仓/普通held/roll不走EMA初开分支。

错误侧actual F在任何827 diagnostic/847或827的R分支前分流：诊断signed距离保留、risk/stop-distance为N/A，保留实际margin。返回同母native synthetic保护close，价格是入场分钟不利极值的合法tick可达proxy；不是即时真实逐笔成交证明，不retry。正确侧保留原minimum-risk guard、0.5R、从下一分钟起原F reclaim一次，可能在L不利侧成交，q/R不重算。

首分钟私有视图同时接即时扫描和lifetime聚合；先由全日raw产生原环境/技术snapshot，随后只对该母持仓的lifetime bar应用保守后缀。多first high=F/close=min(close,F)，空镜像；raw与临时分钟映射在finally恢复。

接口补充：native synthetic CLOSE/retry创建TradeData时只继承signal_order_id，不复制任意context，且CLOSE不会调用entry diagnostic。因此root明确采纳极窄`update_trade` override，按预存新机制context绑定真实初开/CLOSE/retry的母身份字段，再恰调用一次super经济路径；不改价、q/R、现金或费用。此为母链闭合的必要接合，不是新增金融模型。

新增可扫参数0，修改/删除参数0；新增/修改/删除回测结果0。execution_tick、rank与run_id为既有合同身份/元数据输入。真实区间、账户、生产配置、provider、行情、模型、凭证或训练均未运行/改变。

## 有限验收及真实失败

完整命令、session/chunk、终态、六源SHA见`outputs/stage131_native_ema_limit_integration/implementation_receipt.json`。

- Task2 RED：`a2e85d` exit1，独立adapter不存在的明确断言；数值环境已成功import，font cache/TqSdk import banner不当RED。首GREEN `100590` exit0，1测试。
- Task4 gap RED：`084b31` exit1，多/空两个subtest均被spy抓到错误侧进入原827 abs diagnostic。
- Task4双consumer RED：`8ce5fc` exit1，真实lifetime bar high105而非100。
- 首次六方法组合`7110e4` exit1，五过一失败。唯一失败是测试oracle把100→98及103→98两次损失误加为−5，实际是−2−5=−7；真实native net_pnl为−683.94，误写expected为−563.94。明确保留，不冒充实现RED，也没有改变原撮合/经济结果。
- 修正oracle并加强u.close99≠L100、非flat原价、普通roll不进入私有视图及现金核验后，最终新增六方法`cc88d0` exit0，6 tests/0.289秒；六文件py_compile `9670c0` exit0。未跑旧suite或金融入口。

验收事实：真实planner L100/S95/size10→rho50、margin100，即使u.close99仍保持L定价；原admitted22/22/22，gross前缀0/2200/4400，最终22/3/0；仅AP22及au3 reserve，合计2500，q0无补位。nonflat add margin回到raw close99。

多gap真实TradeData价格90→88、空镜像110→112，各两笔真实成本、同新经济母链、setup只消费一次、R=N/A、无retry、最终flat；strategy成本、native calculate_result费用及实际settled cash一致。双consumer fixture raw首分钟103/105/99/104，私有100/100/99/100；即时与真实lifetime consumer均拒绝成交前有利high105，raw恢复。合法R原生价格链100→98→103→98，同q6、初始R4、stop98；retry103确越初开L100且不改q/R。真实四fill费用263.94、native净损益−683.94和settled cash一致。另两项因未触价/量不足无单，已占资源不释放；毒化D日线close/high与估计权益不改u q/L/S。

## 限制、交接与反思

`fixture_only=true`，`financial_replays=0`、`model_calls=0`、`provider_calls=0`、`network_calls=0`、`production_qualified=false`。期末权益、总收益、最大回撤、Sharpe、总滑点、总交易数、母链胜率全部N/A；以上tiny损益仅用于验证经济恒等式，不能作为回测表现。

当前只交组件，root下一步进行一次整体独立review；本agent暂停代码，不另派审查或扩金融波次。未来真实金融仍须独立run_id、u资格execution_tick、真实日线/分钟scope及源SHA、完整38bar覆盖、中性owner/checkpoint/readiness等root交付；fixture使用`fixture-only`身份。分钟总量门和全量近似没有证明真实queue，gap不利极值proxy也不证明真实即时可得价。当前B运行和财务审计继续由root独占，本agent未读其目录、收益或handle。

开始/结束新增过拟合判断：**否**，全部实现和反例来自收益盲固定124/126，不读取B收益、不扫描参数；历史选择偏差仍在。开始/结束继续价值：**是，限于真实native经济与因果接合的必要验证**，能够直接证伪错误侧abs、首bar泄漏和成本/母链错配；通过不等于alpha、金融就绪、生产资格或目标完成。
