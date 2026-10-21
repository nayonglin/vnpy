# Stage016 C2与分钟条件见证独审接纳及下一门槛

- line_id：`futures_ai_monthly_pool_generalization`；day；2026-10-20 19:28 CST。
- 用户授权：继续迭代全市场月度AI；仅该训练源关闭0.5R及其依赖retry，保留独立C2。没有生产更改授权。
- 是否重要突破：识别与来源审计进展，不是收益或模型突破。
- 本轮修改：新增Stage012条件识别、Stage014分来源分钟核查及测试，独立Stage013/015复核；本记录更新LINE与registry本线行。Stage012报告断言数由笔误1287校正为独审实际1289，不更改结果表。

## 接纳的实际证据

1. 185个已固定月末fresh观察全部保留。172个signed R有效，13个错误侧gap；有效者66两侧未达、51仅stop、35仅confirm、20双触。日线的动作识别均以真实全session首open及完整日OHLC为条件，不是实际交易认证。
2. 有界现存分钟库存只在27/185下一源日发现日期证据，20个双触中4个有证据；未按未来有无分钟删除原候选。
3. 对4个事件逐文件、逐minute_source组件检查52份投影：JM与AU各有1个完整且与日OHLC一致的来源；CF完整分钟与日线high/low/close冲突，M不在既有session支持域。没有拼接provider、修数据或扩规则救覆盖。
4. JM条件参考stop由首分钟双触的adverse-ties政策确定，参考fill3224.5；AU条件参考confirm解除C2。两者都不能证明真实tick顺序、来源真值或历史可成交性，其他provider冲突仍保留。20个双触因此只有2个条件收窄、18个仍未知。
5. 独立Stage013：1289断言、185/185复算一致。独立Stage015：248断言、52投影复核一致，未解决P0/P1/P2=0/0/0；未重扫221MB父文件，父文件到投影内容的完整关系不作独立重新背书。
6. root `.py311/bin/python -m unittest discover -s research/lines/futures_ai_monthly_pool_generalization/tools -p 'test_stage*.py' -v`：42项通过。正式Stage847配置SHA仍为`588e97e899f2291617fd935e474133a974da4088972e50a634ad0281e6edf83c`，正式halfR/C2均True；训练profile halfR=False且不覆盖C2。

## 决策与下一步

本轮不拟合，不生成伪确定60日点标签。全部未知必须保留；缺分钟不是0收益或负类，错误侧gap也不能通过abs或抬高R强行变成有效订单。也不能只删掉这些产品后重排并当全市场标签。

下一步先验证新研究源的连续状态合同：单品种/单epoch、固定初始单位风险、与共享资金和槽位解耦，使用不超过5日的有限合成分钟路径验证。必须涵盖gap、同分钟双触政策、成功fill的tick可达性、stop后空仓与confirm后继续持仓的不同分支；无可成交依据时保留execution_unknown。不得把收益区间内每点假定为可达，也不能把最差/最好分支任意丢弃。

状态合并必须保留所有未来规则依赖，且旧108中的滚动盈亏、胜率、回撤具有路径依赖，不能只凭当前仓位相同就合并。若重设计价格特征与固定单位风险目标，需明确它属于新输入/新目标合同，不能声称旧108可直接追加。有限合同验证通过后，再决定真实连续路径、60日标签与训练设计。正式比较臂另受生产身份缺项约束。

## 参数、回测与调研

- 模型参数新增/修改/删除：无；策略阈值、TopN、C、窗口修改：无。
- 新增/修改/删除金融回测结果：无。权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率均N/A。本轮模型fit、金融回放、60日经济标签、订单、下载均0。
- 调研沿用本轮Stage010/012已核对的[VeighNa官方组合回测实现](https://github.com/vnpy/vnpy_portfoliostrategy/blob/main/vnpy_portfoliostrategy/backtesting.py)与[Backtrader执行说明](https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/)；判断：信号、bar撮合政策与真实成交须分开，本仓库的未知不能从通用文档推导为确定结果。本地反例及实际来源核查才是本次分类依据。
- 开始与结束新增按收益选参过拟合：否，未扫描收益、调整阈值或删除困难成员；历史缺失和来源选择偏差仍存在。
- 开始与结束继续价值：是，标签可靠性是扩大全市场训练的前提；当前仅有输入/识别进展，未证明任何模型或收益改善。

证据：Stage012结果、Stage013独审、Stage014分钟见证及Stage015独审；详表保留于对应outputs，不覆盖原始数据库、正式源、池、CTP、调度或其他研究线。
