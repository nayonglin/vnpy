# Stage020 已签资格分钟的轻量追加整合

- line_id：futures_trend_triple_screen；冻结时间2026-10-18 01:14 CST。
- 当前授权：只准备小builder、必要合成测试和本合同；实际构建必须等root提供016、019实际独立receipt SHA后唯一执行。不连接、不回放、不重跑旧stage。
- 研究判断：原015 builder已冻结且绑定旧scope，不能改其globals或重跑。018/019原始记录需要一次小型数据整合才能安全进入研究loader；复用既有纯验证/读SHA/append loader即可，不增加引擎或框架。

## 资格与范围

1. 上游为016已签独立资格的summary/readiness和不可变base、002/011/015。018及019仅接受独立receipt `qualified_research_data=true`、P0/P1=0且`accepted_sessions`明确列出的精确合约/交易日，质量表也必须accepted和后继完整；不取未列session或快照中其他行。
2. provider的raw/evidence/quality/parent/worker、manifest/preflight均须独立receipt明确SHA绑定且当前一致。parent必须已终态、inputs未变、无hard kill，worker单次provider且不是异常/close_failed。整批非0可仅在独立review明确认可部分session时消费这些session；不把逐session资格改写成整批成功。部分未通过仍missing；异常/硬杀或未完成落盘不接受。
3. 018的AP210及将来任何候选落入016四个完整时段的都排除，排除整个1500键网格，而非仅734correction/465append。这四会话只由016负责，避免重复注入和旧值前置条件冲突。
4. 每个候选的真实网格、完成后继、合法OHLCV/OI和独立绑定日线七字段重新核对。018使用原同SHA日线CSV；019可使用原CSV或已独立合格的013日线表，须精确symbol/date，且与manifest固定七字段一致。
5. 多源同键有差异整session隔离；与任何旧base/002/011/015键有冲突也整session隔离。沿既有011/002固定数值容差，不能改旧值；仅缺失键进入append-only overlay，不产生correction或删除。

## 构建与消费

1. 继承016全部readiness，只更新本阶段明确合格的候选对应行；保留016价格资格列及未触及行。物理ready不是全局价格资格，所有旧缺失约束继续有效。
2. 新overlay键对旧键、A0真实106731读取键和016全部1500scope键都必须交集0；A0读取仍为535anchor/501scan，不重跑A0。源码/来源/原数据全程不写，输入最终SHA未变才成功。
3. 输出沿015 schema：overlay、session_manifest/quarantine、source/input_manifest、readiness/remaining、A0零交集和summary。仅一个独立overlay，由既有002 append context载入；排序为002→011→015→020→最外层016。不新增第二种loader，不修改Stage001、正式策略或旧receipt。
4. 构建唯一不可覆盖；有失败记录则停止不自动重建。完成后独立agent审查新overlay范围/来源/旧键/A0/016交集与readiness，再由root决定后续。构建和数据review均不授权C0第三次金融回放。

## 验证、调研与反思

- 少量必要测试先RED后GREEN：partial名单限域且016排除、仅追加且冲突隔离、新键避开旧键/A0/016scope。不跑全仓测试、不重新审核其他源。
- 复用[官方TqSdk文档](https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html)、[官方源码](https://github.com/shinnytech/tqsdk-python/blob/master/tqsdk/api.py)及018实际独立后继证据；不新增网络调研或通路。
- 新增策略参数/修改/删除参数：无；金融账户/指标/费用/AI/0.5R均未变。期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率均N/A。下载、金融、订单、撤单、CTP、模型拟合、旧数据写入均0，production_qualified=false。
- 过拟合判断：否，范围由固定需求和独立数据资格决定；继续价值：是，让已取得合格数据真正进入严格研究覆盖，避免重复下载和逐缺口金融重试。
- 不改LINE/registry，由root统一登记。
