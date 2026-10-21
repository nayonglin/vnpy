# Stage453 固定滞后Con4增量实验

- 时间：2026-10-20T21:56:12.183169+08:00；研究线`futures_full_market_long_signal_ai`；不是重要突破。
- 上轮goal分类：用户流程澄清，无新增金融证据；本轮消费451/452独立设计并冻结唯一实际协议，不能继续只报计划。
- 调研判断：CFTC官方通常Tue统计/Fri15:30ET公布，节假日可能延后；GitHub下载器没有解决PIT。原论文是美国特定市场/持有期关系，不能当国内高质量信号证明。
- 新增参数：固定Con4Net_All单列，train-only原权重z；53维。普通周再延迟7日，既有例外优先、7日freshness、unknown不回退。新增missing flag/交互/来源变体=0。
- 修改参数：无目标/原52/scaler/alpha1/样本权重/K/.25N止损/风险/成本修改。删除参数=0；不动正式C9。
- 对照：accepted130/156/157独立全市场研究控制；原四现金账直接复用。最多6新fit、4新cash，先所有6fold源支持，再读Y。
- 原98产品95家族/六所范围不缩到8来源映射；90结构N.A保留，unknown不填原值0。新列直接贡献0不保证N.A最终score不变，须披露联合重估间接影响。
- 时钟接受条件：普通假定Fri后多延7天仍是重建假设；已确认日期次日NY00；修订row永久隔离；停发reset取消跨入该期的延迟grant，ordinary deferred不自动当unknown。2013恢复仅假设；2025源尾隔离。
- 回测结果新增/修改/删除：均0。期末权益/总收益/最大回撤/Sharpe/滑点/胜率=N/A，总交易次数=0；累计仍460fit/250完成cash及1旧partial。

## 实施顺序

- [x] 冻结源时钟/单列设计/支持与经济门（本协议）。
- [ ] 新454工具：最小语义fixture先红后绿；只读448一次、原母身份与六训练身份/权重一次，生成可见值与支持，0Y/fit/cash。
- [ ] 独立核全部事件时钟、屏蔽/TTL/映射/源支持，不重做16ZIP。
- [ ] 源支持通过后单456六fit及完整预测选择，独审；不使用旧205方向门。
- [ ] 若选择变化，四候选cash和独审；否则0cash退化结束。
- [ ] 依原经济门及held泛化门做裁决；失败不改lag/符号/映射/窗口救参。

反思：历史择题过拟合风险是；有限一次不同信息检验继续价值是。未证明超高质量做多/窄损加注，完整目标仍active；原向前四账户另等真实21日完整事实，不阻塞本历史实验。

精确协议：[protocol.json](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage453_Con4_fixed_protocol/protocol.json)。
