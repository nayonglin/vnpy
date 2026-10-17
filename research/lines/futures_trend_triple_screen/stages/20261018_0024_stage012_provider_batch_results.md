# Stage012 首次正规批量暖机历史取数结果

- line_id：futures_trend_triple_screen；记录时间2026-10-18 00:24 CST。
- 性质：固定C0数据准备，非alpha迭代、非金融回测、非部署；是否重要突破：否（数据通路取得进展，策略目标未证明）。
- 分支codex/ai-training-data-expansion；当时HEAD a2b1d3a95；解释器.py311/bin/python，SDK3.10.2未升级。

## 调研判断与本次变更

沿本阶段协议所列官方TqSdk文档/GitHub，独立agent确认公开get_kline_serial(10000)的初始化会正常提供回放时点之前的暖机历史，不需要用户循环逐分钟推进整段窗口。判断：用正规公开接口的暖机快照可提高批量取数效率，但不保证账户无限权限、全部历史或任意订阅规模。本阶段未改授权、未用私有网络接口。

新增stage012_provider_batch.py和4个必要collector合同测试，新增--prepare/--preflight/--run数据操作参数；策略/资金/AI/0.5R/换月/风险/成本参数新增修改删除均无。固定选择Stage011剩余真实日线session中incomplete_session且原CSV已绑定的最早10自然日窗口；排除缺CSV和3个base冲突，目标最多8合约/20000分钟，不使用PnL。

实际批次为hc2010.SHFE/rb2010.SHFE两个合约、2020-04-01至2020-04-10中的11个需求日，共2475分钟。provider观察起点2020-04-13 09:01、终点09:05，均在目标结束后；时间用途是取回已存在的历史，不将观察日信息注入策略。每根目标均有严格更晚已观察K线，最后形成行不接受。

## 实际结果

- 唯一实际连接：parent exec session36179，已终端exit0；父进程37.928秒、worker37.217秒，没有超时kill或自动重连。
- 2475/2475目标完成分钟、11/11完整网格及原CSV七字段全部通过；无缺失/重复，DBcloseOI不虚构参与校验。
- 正常TqAuth＋本地TqSim、一个TqApi/TqBacktest；订单/撤单/券商或CTP连接/金融策略回放/模型训练均0。SDK raw输出和凭证未保存。
- parent all_inputs_unchanged=true；原base、Stage002、Stage011 overlay未写入；新raw/evidence只保留本研究outputs，尚未合并。P2已知：脚本返回码不单独保证输入未变，接受同时检查该布尔门，本批实际通过。
- 该批的原CSV字段核对属于数据证据，不是C0绩效。新增、修改、删除回测结果均无；权益/总收益/最大回撤/Sharpe/滑点/交易次数/胜率全部N/A，累计金融attempt仍4、完成仍1。

## 测试与独立复审

4个离线测试先RED后GREEN：形成中末行不得接受、两合约时戳不重合也应保留、相同完成bar冲突拒绝、初始快照早端历史不得被末3条截掉。仅在真实连接前测试，没有将网络尝试当测试重试。

triple_screen_baseline独立复审P0/P1=0：标准库csv/Decimal核2475全键网格/唯一/合法OHLCV/OI及逐键后继；两个合约各首末日共4session七字段独立聚合与CSV零差，其余7日只核已绑定quality receipt，不冒称独立全量重聚合。复审重新检查preflight源SHA均未变化，无网络/账户重跑。

独立receipt SHA：7992c3bdee73838d54769a9034148ef364be42a4f016efa2085d5a5bf4dbf7ef。数据、completion_evidence、quality、worker/parent receipt见outputs/stage012_provider_batch/network_attempt1，独立报告见outputs/stage012_independent_review。

## 后续与反思

仅接受这11个session/2475行作为研究补数候选；不得外推所有剩余需求、自动合并或启动C0。下一步恢复94个缺文件合约的日线依据，并针对新增合格日线所涉session复用本机completed源；3个base冲突和16carry约束仍单列，不靠更换数值或daily-open fallback绕过。

结束过拟合判断：否，分包按缺失数据密度和公开API限制，不按收益选参数；既有策略选择偏差仍保留。继续价值：是，首次小批量真实完成且获独立资格，后续应批量推进必要数据后取得真正候选成绩，不能把取数成功当交易优势。
