# Stage044：同一B引擎有界数据等待编排实现

- line_id：futures_trend_triple_screen；非重要策略突破；实际记录时间见implementation receipt。
- 新增独立044工具及2项聚焦测试，原B attempt1/PID21822、036策略/引擎、040/041/039/042均不改。043仍为独立资格算法，044只编排真实请求及发布已合规pointer，不自行签receipt。
- 仅选择root manifest显式SHA固定的resolver、037/041 provider和对应reader。优先独立resolver的local accepted；真实needs_provider才执行已批准provider。037仅原CSV/013既有资格，041仅非空新签日线subset；其资格门由原provider独立执行。
- 新批次最多4次provider连接，总预算840—3600秒；启动provider前预留840秒，外层660秒等待保留原provider600秒hard guard。每次真实Popen rc0、source/原preflight/parent receipt匹配后才写终态；043/046验收和实际021 parser通过后发布022 atomic pointer。
- 旧partial/failed attempt拒绝重试；旧完整provider与已签parse_result复用。缺daily、unsupported multi、源漂移、任何错误具体blocked退出，不重启金融，不扫描未来理论缺口。
- 验证：2测试先RED（模块缺失）再GREEN（0.001秒），确认无真实audit拒绝及残缺/失败attempt拒绝；compile真实exit0。Root审043发现terminal缺new_minute_provider_connections，已在任何绑定/运行前补为1。未跑旧suite；本人未运行prepare/driver/network。
- 原sandbox不允许ps，本阶段未声称已核验真实PID；root actual prepare/run需在授权环境完成ps命令/lstart核验。
- 策略参数及金融结果新增/修改/删除0，权益/收益/回撤/Sharpe/滑点/交易次数/胜率均N/A。过拟合新增：否，只复用冻结候选的实际缺口数据管线。继续价值：是，减少逐请求重复人工操作，仍需B完整金融结果及独立038验收。
- TODO：root源审及045/046绑定就绪后显式小批运行；源码进入实际receipt后保持immutable。production_qualified=false。

- 实际绑定前恢复接口补充：root显式冻结reviewer_output_root，必须绝对且位于本线outputs内；resolver不得覆盖。043源码目录与输出目录同处，046源码位tools，单独绑定其输出目录才能只消费已有成功签收，避免再次调用不可覆盖的reader。compile exit0，不重复旧测试。
