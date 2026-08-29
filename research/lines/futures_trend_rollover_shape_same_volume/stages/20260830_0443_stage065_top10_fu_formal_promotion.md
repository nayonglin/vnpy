# Stage065 Stage037 Top10+固定fu正式晋升

- line_id：`futures_trend_rollover_shape_same_volume`
- 当前模式：正式版本晋升（用户显式 operator override）
- 记录时间：2026-08-30 04:43 CST
- 工作区/分支：`.worktrees/stage056-ai-top14-plus-fu` / `codex/promote-stage065-top10-fu-official`
- 阶段性质：正式代码、AI决策资产、资格、远端master与生产安装治理；不新增回测
- 是否重要突破：是，变更当前正式AI选品合同
- 是否触发A/B：是；沿用Stage061全周期、Stage063固定多周期、Stage064随机多周期既有证据，不重新调参或重跑回测

## 外部调研与判断

- 参考资料：本阶段不新增alpha研究。Stage061已按公开趋势跟随、1/N与容量/成本文献完成调研并冻结Top10至Top19宽度扫描；Stage063/064已完成固定与随机多周期验证。
- 我的判断：Top10+固定fu不是自然门禁通过候选。Stage061滑点为Stage037的`130.36%`，超过冻结`105%`门；Stage063仍有固定多周期成本、回撤非劣与broker100硬失败；Stage064的192个随机窗口回撤非劣率仅`72.9167%`、总滑点比`113.6614%`且有1个broker100失败窗口。用户已明确要求直接晋升，故只能记录为人工承担已知风险的operator override，不能改写上述FAIL。

## 本次变更

- 新增脚本：正式AI policy唯一真源；Stage065 Top10+固定fu五件套构建器。
- 修改脚本：Stage182月度生成器、Stage935月更校验与发布、正式live配置、Stage901/659影子审计、Stage929报告阈值、Stage179发布指纹，以及实盘执行/启动/物料技能；Stage847历史候选继续保持原Top8策略与路径，仅作基线。
- 删除脚本：无。
- 新增参数：正式AI排名品种数`10`、固定品种`fu.SHFE`、总品种数`11`、策略名`ai_top10_plus_fu_official_live_v1`。
- 修改参数：原正式Top8非fu+固定fu（9品种）切换为Top10非fu+固定fu（11品种）；Stage929门槛从rank8切换为rank10。
- 删除参数：无；历史Top8研究常量与不可变m0016物料不改写。

## 回测/归因参数

- 数据区间：2018-01-01至2026-08-28（沿用Stage061）；固定/随机多周期沿用Stage063/064。
- 账户规模：150,000元。
- 成本口径：与Stage037一致；Top10全周期总滑点`2,163,390`。
- 样本过滤：模型排名Top10非fu，固定追加`fu.SHFE`；2019-12-31 pre-AI边界仍为静态18且不含fu。
- 策略/归因口径：Stage037 alpha与风控不变，只改变AI eligibility成员宽度；本阶段不运行新回测。

## 结果

- 期末权益：`21,870,488.80`
- 总收益：`14,480.3259%`
- 最大回撤：`-39.9147%`
- Sharpe：`1.586976`
- 总滑点：`2,163,390`
- 总交易次数：`798`
- 胜率：`53.7348%`
- 其他关键指标：broker10峰值`93.5807%`；相对Stage037滑点比`130.36%`；自然晋级`FAIL`，用户operator override为`true`。

## 输出文件

- report：待生成不可变material payload内`ai/stage182/report.md`。
- summary：待生成不可变material payload内`ai/stage182/summary.json`。
- orders：不生成；order/send/cancel API目标始终为`0/0/0`。
- daily：沿用Stage061已验证资金曲线，不新增回测daily。
- quality：Stage065构建器校验精确Stage061 Top10源SHA `cf3cced22a61b354dadbc2f67091143eec74d7a2f03577faf2fd4c10dcec0c0d`，共623行、56个eval_date；55个AI月各11行，pre-AI边界18行。

## 正式合同与安全边界

- AI月份必须是10个模型排名非fu品种+固定`fu.SHFE`，共11个唯一品种，rank`1..11`、`top_n=11`，固定fu只能位于rank11。
- Stage182、Stage935、Stage901/909、Stage929、正式live配置、发布指纹、资格测试和生产回执必须读取同一policy；Stage847历史候选保持旧Top8身份，不得把新policy写回历史候选；后续正式月更不能回退旧Top8/Top9常量。
- 五项运行/资格资产为latest pool、live eligibility、combined eligibility、summary、report；另保存精确Stage061 Top10来源CSV与Stage061/063/064原始decision作为复现和失败证据。
- 本阶段构建器不训练、不评分、不回测、不连接CTP、不调用订单API。正式资格只允许两次只读CTP采集，任何失败均保持fail closed。

## 实现与独立复核（截至2026-08-30 06:09 CST）

- 正式 policy、Stage065 五件套构建器、Stage182/935 月更、Stage901/659/909/929 consumer/audit、正式配置、Stage179关键文件清单及相关技能已经统一到 Top10+固定fu 合同。
- 核心策略在正式 strategy 下对整份 combined eligibility fail closed；唯一允许的历史边界为`2019-12-31`静态18品种，其他月份必须精确11品种且`fu.SHFE`位于rank11。缺失品种、score type、分数、整数rank/top_n、重复或不连续rank均阻断。
- publication request 的 source commit 现在必须为40位SHA、等于当前clean HEAD，并写入manifest provenance；避免后续月更把旧代码生成的AI资产错误绑定到新runtime。
- 独立reviewer最终结论：`APPROVE`，P0/P1/P2=`0/0/0`；独立验证`182 passed, 67 subtests passed`。
- 正式清单整组验证：40个required suite，`945 passed, 697 subtests passed`，耗时`477.14s`；`git diff --check`与相关Python `py_compile`通过。
- Stage063仅刷新允许变化的`render_provenance.rendered_at`与`runtime_contracts.current_runner.sha256`；原engine checkpoint、CSV、报告和5张资金曲线哈希均未改变。
- 本轮仍未连接CTP，order/send/cancel API调用均为`0/0/0`。

## 结论

- 本阶段结论：用户授权的正式晋升正在执行；自然研究门仍为FAIL，operator override不能抹掉失败。
- 是否进入下一步：是，继续完成独立评审、不可变release、资格、CURRENT、受控master、fresh clone、Stage948与最终六身份审计。
- 下一步：所有闭环完成前不得声称Top10+fu已在线；生产只读闸门失败时停止在已完成边界，不绕过。

## 过拟合反思

- 运行前判断：是，风险高。
- 运行后判断：待正式闭环后更新；发布治理本身不新增拟合。
- 原因：Top10来自Top10至Top19同时扫描且位于搜索边界，固定和随机多周期均保留硬失败；用户人工选择不能消除多重比较偏差。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：待正式闭环后更新。
- 原因：既然用户已决定新的正式AI宽度，必须让policy、AI资产、master和生产唯一一致，避免后续研究或月更悄悄回落到旧Top8；继续扫描TopN或放宽成本门没有价值。

## 合入建议

- 是否更新本线`LINE.md`：完成正式闭环后更新。
- 是否更新`research/registry.md`：完成正式闭环后更新。
- 是否追加根目录`memory.md/back_log.md`：本次属于正式基线变更，完成或明确阻断后追加准确摘要。
