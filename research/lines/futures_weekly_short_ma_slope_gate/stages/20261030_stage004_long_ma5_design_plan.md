# Stage004 多头只看MA5：固定实验合同与计划

- 时间：2026-10-30 01:03 Asia/Shanghai；line_id=futures_weekly_short_ma_slope_gate；day；非重要突破，结果待回测。用户明确要求改完直接回测。
- 从Stage033 A原19品种、不加仓衍生；现有独立worktree/分支内新增stage004文件，与44品种研究解耦。Stage001/002/003、LINE、registry、根总账、正式物料不修改。
- 唯一规则变更：多头long_case1a/long_case2仅MA5当前完成周值小于上一已接受完成周值则拒开，MA10仍记录但不参与判断；零斜率允许。空头继续任一MA5/MA10正斜率拒开。换月续仓、平仓、动态手数及风险门沿用。
- 数据：冻结outputs/data_stage001_20261029/data_approved；当前10月30日凌晨，当日日线未完成，最新完整交易日为10月29日。2020独立空仓起点，实际2020-01-02—2026-10-29，15万、19池、手续费0、既有滑点、静态margin×1.65、原完成周与同约下一日开盘模型；不补数、不扫参。
- 对照：original=Stage001 A003，short_only=Stage001 C003，symmetric=Stage002 C001；仅新候选long_ma5跑完整引擎一次。逐日日期、设置、有效参数、数据SHA须一致。
- 预声明：对比symmetric，权益更高、最大回撤不更差、Sharpe不更低三项同时通过才算本窗支持；同时报告short_only差异。全部保留NO_PROMOTION；不因失败修改规则。

## 调研与判断

- 已查Backtrader官方指标文档https://www.backtrader.com/docu/indautoref/ 和官方GitHub示例https://github.com/mementum/backtrader/blob/master/samples/order-execution/order-execution.py 。均线方向与均线交叉是不同条件；本实验坚持相邻已完成周均线差，不增加回归窗口或角度阈值，不从示例推导收益保证。
- 第一性原理：MA10相较MA5更慢，取消其多头方向门可能保留反转初期机会，也可能增加逆势入场；效果必须看真实共享资金路径。MA10变化只保留审计字段。
- 过拟合判断：有事后选择风险，本次由已见负结果提出，不能称独立样本；固定结构、单候选，无窗口/品种/小数扫描。
- 继续价值：有，一次固定规则对照能检验较慢均线是否过度约束；不代表值得正式部署。

## 实施与验收

1. 先验证MA5非负/MA10负允许、MA5负/MA10正拦截、两个多头case、flat允许、原父级结果不变、空头和换月不变、最终开仓guard。
2. 新类、新runner绑定新代码/测试/合同，旧文件字节不变；只跑stage004_C_attempt001。
3. 从真实逐笔/逐日/持仓账本重算四版指标与年度数据；绘制净值=权益/150000和回撤。
4. 独立agent审查数据/逻辑/会计/周源/实际开仓/bug/置信度；保存中文结果、哈希与图。仅离线研究。
