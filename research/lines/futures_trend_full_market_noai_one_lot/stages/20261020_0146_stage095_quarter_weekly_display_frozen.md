# Stage095：0.25%双版展示冻结

- 时间：2026-10-20 01:46 CST；本研究线唯一记录，重要突破：否，展示适配与验证。
- 用户指定本轮风险0.25%=0.0025，100万2500元；严格同参数/代码/数据，分周过滤启用/关闭两臂。0.5% v3 f2fb…为执行父身份，N859982…仅冻结数据锚，均不是本次资金曲线对照臂。
- 本阶段新增/修改/删除金融绩效：无；未金融回跑、未下载、未访问生产、未改金融入口/旧冻结模块/旧输出/LINE/Git。真实两源尚未出本阶段显示产物。
- TDD：四入口核心测试先缺模块RED，再实现；最终9项专项PASS（9.028秒），包含完整两臂冻结toy fixture与两条2862点曲线全部资金/高点/回撤、13行表、双方PNG、全部hash/JS/逐笔R费用及周图的独立验收。toy不是金融回测，数字不得当成策略绩效。
- 测试命令：`MPLCONFIGDIR=/private/tmp/fian-stage055-mpl /Users/mac/Desktop/fian/.py311/bin/python -m unittest discover -s research/lines/futures_trend_full_market_noai_one_lot/tools -p 'test_stage09[4-7]*.py' -v`。
- 过拟合：此展示工作否，不调收益参数或选择赢家；同样本双版比较只描述冻结结果，不作晋级结论。继续价值：是，确认策略周门关闭时不把纯显示周图/零检查误称过滤通过，保持多手完整entry的正确计量。

095复用063的canonical周聚合/MA、records替换、全部值校验与非周/坐标hash；独立纯市场+calendar表构建，不实例化/查询058/091或其他金融周线provider。两臂均显示交易合约自身accepted-clean未复权完整周格，坏周不压缩，先完整历史MA再裁窗；off features仍源为空、不查询金融provider、不把周图当策略门证据，显著N/A。只有enabled才对源冻结策略features做一致性核对。

```json
{
  "stage094_quarter_risk_recap.py": "d57815e4e8df26b0390c0f54fe7d687e23502f1fc7e82fe48fd49ae1f9675b04",
  "stage095_quarter_weekly_display.py": "a1d77563c8576c3b03f841ff6c78f0775340df953bd3ee627d5cd47f958391e5",
  "stage096_quarter_pair_overview.py": "ef3c4db803e97320e99b181d8bf61ae1af688f336db9bc2f48419d8c058cb552",
  "stage097_validate_quarter_display.py": "f31fc85b5f82eef83905b92df94df5ef78fe117b686d4562680f336f6a6c45b7",
  "test_stage094_quarter_risk_recap.py": "903ab11a1d29000a0e840b8fbcd212d2661f015ff012becfc4c960f787bea045",
  "test_stage095_quarter_weekly_display.py": "fd0ce494db058fbe6f0a0f388b2ae831d518409f0e1c8247bec6cdce6ec906c0",
  "test_stage096_quarter_pair_overview.py": "a88a1e14c4212d5a7453657031c21def85641bd559aa671fd21927d26ed99852",
  "test_stage097_validate_quarter_display.py": "5cc4e62ed6ef12bea5cc10fa59c09c006d34ba38360b6e658e0d84720c06a1ee"
}
```

外部调研：[Plotly官方子图文档](https://plotly.com/python/subplots/)、[Plotly官方GitHub共享轴示例](https://github.com/plotly/plotly.py/blob/main/doc/python/subplots.md)。判断：复用原图trace与公开add_trace/共享轴合同，无需改私有状态或重新计算图形；合并两臂时回撤可见范围必须覆盖两臂最小值，源码样例专门覆盖关闭版更深回撤。CME风险数量/总现金单位资料沿用Stage071已核依据，不引入新金融阈值。
