# Stage000 XGBoost PIT逐合约收益设计冻结

- line_id：`futures_trend_xgboost_pit_contract_returns`
- 当前模式：设计冻结，用户已选择路径2
- 记录时间：2026-09-02 11:46 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：新研究线数据契约；不训练、不回测
- 是否重要突破：否
- 是否触发A/B：否；尚无策略候选或回测结果

## 外部调研与判断

- 参考资料：QuantConnect连续期货官方文档、LEAN GitHub期货数据格式、CME连续价格说明、时间序列动量原论文；完整URL见本线`LINE.md`。
- 仓库证据：Stage020在换约日把收益置0，Stage122对拼接价格直接计算涨跌；历史主力映射缺少逐日发布版本证据，均不能直接满足严格PIT。
- 我的判断：`T-1`持仓量选约加同合约两日close收益，是当前本地数据中最可辩护的无未来信息构造；但正式排序包含上市前品种，覆盖失败概率高，必须先fail-closed审计。

## 本次变更

- 新增研究线：`research/lines/futures_trend_xgboost_pit_contract_returns/`
- 新增文件：本线`LINE.md`与本Stage000记录
- 修改文件：`research/registry.md`新增研究线索引并更新时间
- 新增参数：120日完整覆盖门；`T-1` OI/volume/contract确定性tie-break；零fallback、零跨合约比价、零PIT违规
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：由Stage014的51个eval month和每月前120个全局交易日决定
- 账户规模：不适用；不运行账户
- 成本口径：不适用；不产生交易
- 样本过滤：正式51个月完整rank10..18与对应Top9，禁止结果后删样本
- 策略/归因口径：只构造并审计逐合约市场日收益；不计算模型效果或策略收益

## 结果

- 期末权益：不适用；未回测
- 总收益：不适用；未回测
- 最大回撤：不适用；未回测
- Sharpe：不适用；未回测
- 总滑点：不适用；未回测
- 总交易次数：不适用；未回测
- 胜率：不适用；未回测
- 其他关键指标：尚未运行Stage001

## 输出文件

- report：本文件
- summary：`research/lines/futures_trend_xgboost_pit_contract_returns/LINE.md`
- orders：不适用
- daily：待Stage001
- quality：待Stage001

## 结论

- 本阶段结论：`stage000_pit_contract_return_design_frozen`
- 是否进入下一步：是，只进入测试先行的Stage001标签前覆盖审计
- 下一步：先写合约识别、T-1选约、同合约收益和fail-closed覆盖门测试；确认测试按预期失败后实现最小工具并运行一次正式审计

## 过拟合反思

- 运行前判断：是，研究序列整体风险高
- 运行后判断：本阶段没有读取标签或策略效果，没有新增结果拟合；后续风险仍高
- 原因：唯一假设、输入和失败门在看到Stage001覆盖结果前冻结，失败后禁止改门救援

## 继续价值反思

- 运行前判断：是
- 运行后判断：是，但仅限一次覆盖审计
- 原因：现有账户损益源的候选活动稀疏已被证明；逐合约市场收益是当前唯一仍有数据层可证伪性的独立来源

## 合入建议

- 是否更新本线`LINE.md`：是，已建立
- 是否更新`research/registry.md`：是，新增索引
- 是否追加根目录`memory.md/back_log.md`：否；设计阶段不是重要突破、正式候选或跨线合并
