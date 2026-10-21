# Stage128：初开月选择合同独立设计复审

- 时间：2026-10-18 21:28 CST；line_id：`futures_full_market_long_signal_ai`。只读复审，非突破；读registry、127、128 data/capacity notes及070标签/现金、071训练源码。未运行SQL、标签、fit、cash或下载，未改旧资产、LINE或registry。
- 审查对象：root给定的“共同anchor、单评分器、u毛量1%且新开预留往返、退出只审计”候选；两份notes是输入建议，尚非统一冻结协议。

## 结论

**设计级Critical=0、Important=0；无必须改变经济假说的阻断。** 可进行一次固定风险、共同数据的动作空间检验；以下三项文字必须在最终协议统一，防实现偏离，不能据收益再决定。

1. **容量版本。** root的最终候选为`grosscap=lot*floor(.01*V_u/lot)`、`entrycap=lot*floor(grosscap/(2*lot))`；capacity notes仍写新开直接用grosscap，应明确被替代。u准入至少容纳一份lot的完整往返；该准入同时用于成熟训练的`u_action_eligible`和两臂请求，不能标签训练容许0cap而执行另筛。量未知与已知不足分列；fixture边界相应改成一手往返，不能沿旧99/100量边界当最终要求。
2. **产品月选择与family次序。** 两臂先在exact product内部择月，随后共同沿070普通优先/F次序竞争单一family仓位；不能A沿旧次序、B跨普通/F取全局最高分。预算缩至0后不换次优月，不把未用容量再分配。否则新增不止月份选择，无法归因。此合同检验“原family次序下初开月”，不覆盖F自由替换或自由续持。
3. **退化与判定口径。** canonical动作的单事件无容量路径/目标应退化070；A整条曲线因共同容量规则不必等于旧070，主比较须是本次新A对新B。主现金比较、family-held诊断和未知统计必须沿各臂实际事前选择，不能用全部child标签均值或赢家月oracle替代；held按family-u控制月份重复，unknown不可填0或按closed删选。

## 因果、公平与边界

u观察全集展开、D严格native后继、自身历史/精确经济键/生命周期准入，没有发现需用未来主力、D有价或未来closed才可决定的准入。52槽重算尤其应守住own SMA20 ATR和070 Wilder N不同、COMMON原2N量纲、peer池可重复查询并排自身；复制代表NPZ将使B不是真月份评分。held普通/F及所有月份整体隔离，训练只用cutoff前已成熟动作；成熟后闭合样本选择的局限仍在，但不是预测时未来筛选。

family-u区间union使多月只贡献一次跨u并发，组质量均分再等u，解决机械月份数加权。模型仍可能从更多月份挑中噪声，这是B政策自身风险，应由完整前向资金结果承担，不能用多候选调整胜率或只报正分交易均值。

anchor应保存u的canonical且不随held变化；v收盘改变/缺失发下一native open请求，已发请求不得被后来回归撤销。held!=anchor本身不退出；held缺价沿unknown/stale而非移动D，不能重用070直接以held对canonical比较。生命周期优先及缺价恢复后的理想清算须保留原不确定性。

每账户`(epoch,D)`全部BUY+SELL毛量共享exact native D−1上限，减仓、stop、新开不能各领一份；退出不硬截使现金仍是理想路径，任何超限/缺参考量必须保持账户执行容量unknown。即使两臂同受未知影响，也不能据相抵宣称可执行；0超限仅说明固定日线审计未发现冲突，不能证明开盘成交或允许加注。

## 调研与反思

沿127的[RBA原论文](https://www.rba.gov.au/publications/rdp/2017/2017-03/data-and-measurement-of-commodity-risk-premiums.html)及[LEAN筛选源码](https://github.com/QuantConnect/Lean/blob/master/Common/Securities/Future/FutureFilterUniverse.cs)：选月是独立经济动作，但不是国内窄损盈利证据；本次不重复搜索或扩展模型。

开始/结束按收益调参：否；历史同数据择题过拟合风险：是。继续价值：是，限这一次可证伪动作检验；尚未证明高质量long、跨周期优势或加注。新参数为固定参与率1%与往返预留；本次新增回测0，权益/收益/回撤/Sharpe/滑点/交易次数/胜率均N/A。实际完成后由独立132检查数据、资金、置信度和bug，不以本设计审查替代。
