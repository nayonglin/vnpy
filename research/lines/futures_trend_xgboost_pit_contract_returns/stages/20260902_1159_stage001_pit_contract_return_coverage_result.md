# Stage001 PIT逐合约收益覆盖审计结果

- line_id：`futures_trend_xgboost_pit_contract_returns`
- 当前模式：Stage001正式只读审计完成，本线闭线
- 记录时间：2026-09-02 11:59 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：标签前数据覆盖审计；不训练、不回测
- 是否重要突破：否；但识别出正式历史排序的PIT上市资格缺口
- 是否触发A/B：否；没有策略候选或回测数据

## 外部调研与判断

- QuantConnect和CME均把连续合约的“选哪张合约”和“如何处理换约价格”分开；持仓量是可辩护的流动性选约依据，但必须同时处理映射时点和价差。
- 本次使用预注册的`T-1`持仓量选约，并只计算同一张合约的两日close收益；未复用Stage020换约置0或Stage122拼接价格涨跌。
- 我的判断：收益构造本身通过PIT技术门；失败原因是正式历史排序在品种上市前仍把`SH/lc/si`放入18品种排序。不能用补零或当前上市事实回填历史。

## 本次变更

- 新增核心：`tools/pit_contract_returns.py`
- 新增入口：`tools/stage001_pit_contract_return_coverage.py`
- 新增测试：`tests/test_pit_contract_returns.py`、`tests/test_stage001_pit_contract_return_coverage.py`
- 新增参数：120日完整窗口、Top9、`T-1 OI -> T-1 volume -> contract`确定性选约
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：逐合约日线最早2015-01-05；正式审计窗口为51个eval month，每月截至eval_date的最近120个全局交易日
- 账户规模：不适用；未运行账户
- 成本口径：不适用；未产生交易
- 样本过滤：459个rank10..18样本及对应459个Top9品种窗口，未删月份、年份、品种或rank
- 策略/归因口径：前一交易日持仓量选约；同合约`close_d / close_{d-1} - 1`

## 结果

- 期末权益：不适用；未回测
- 总收益：不适用；未回测
- 最大回撤：不适用；未回测
- Sharpe：不适用；未回测
- 总滑点：不适用；未回测
- 总交易次数：不适用；未回测
- 胜率：不适用；未回测
- 读取SQLite日线：`250,378`行
- 构造产品收益：`39,646`行，其中有效`39,422`行
- PIT违规：`0`
- 事后fallback：`0`
- 跨合约比价：`0`
- 120日完整候选窗口：`445/459`
- 120日完整Top窗口：`415/459`
- 必需缺失单元：`5,959`
- 受影响月份：`2022-04-29`至`2024-02-29`共23个月；2024-03起窗口完整
- 缺失来源：仅`SH.CZCE/lc.GFEX/si.GFEX`。三者本地首个可构造收益日分别为`2023-09-18/2023-07-24/2022-12-23`；上市前不能存在真实120日收益
- 候选不完整窗口：`SH=5`、`lc=4`、`si=5`，合计`14`
- Top9不完整窗口：合计`44`
- 决策：`stage001_pit_contract_return_coverage_fail_stop_no_features`

## 输出文件

- report：`artifacts/stage001_pit_contract_return_coverage/report.md`
- summary：`artifacts/stage001_pit_contract_return_coverage/stage001_summary.json`
- daily：`artifacts/stage001_pit_contract_return_coverage/product_daily_returns.csv.gz`
- quality：`coverage_by_eval_product.csv`、`missing_required_cells.csv`、`window_audit.csv`、`source_product_summary.csv`
- manifest：`artifact_manifest.json`，SHA256=`32ead9d84ff97d6722a4491e389912c40d9c6558f5f4c6afbfdaa11a64c0c9b5`

## 验证

- TDD RED：核心模块和runner分别先因文件不存在而失败，确认测试可捕获缺失实现
- 专项测试：`12 passed in 0.22s`
- manifest：7项文件集合、大小和SHA全部匹配
- SQLite运行前后SHA均为`7e2633909f73d77c3b0b044199418d7c1ed2989afde480596aefbb18a83b724a`
- 正式排序、Stage014标签前面板、Stage000规格运行前后SHA均无漂移
- 账户边际标签读取：`0`
- sealed holdout标签读取：`0`
- 模型训练/回测/CTP/订单：均为`0`

## 结论

- 本阶段结论：直接把该市场收益源补入原459行/rank10..18面板不可行，本线按预注册闭线
- 是否进入下一步：不进入本线Stage002特征设计
- 禁止项：不得补0、降120日、删23个月、删`SH/lc/si`、只保留2024-03以后、按rank或split选择样本，亦不得让XGBoost用missing默认分支掩盖“品种尚未上市”
- 新线索：正式历史排序把尚未上市品种以默认概率排入Top10/Top9；若继续，只能另立“PIT上市/可交易资格先于排序”的新标签机制，而不是修补本线覆盖门

## 过拟合反思

- 运行前判断：是，整个XGBoost研究序列风险高
- 运行后判断：本阶段自身否；没有读取标签或效果，也没有根据结果改门。但若现在只保留完整月份或允许missing分支，将构成明确的结果后样本选择
- 原因：技术规则在运行前冻结，失败被原样保留

## 继续价值反思

- 运行前判断：有，只值得一次覆盖审计
- 运行后判断：本线无继续价值；更上游的PIT资格重建有继续研究价值
- 原因：市场收益不能为尚未上市品种创造历史；正确问题已经从“补什么收益”变为“这些品种当时为何进入排序和TopN”

## 合入建议

- 是否更新本线`LINE.md`：是，标记Stage001失败并闭线
- 是否更新`research/registry.md`：是，更新状态和下一步边界
- 是否追加根目录`memory.md/back_log.md`：否；尚未形成正式候选、回测突破或跨线合并
