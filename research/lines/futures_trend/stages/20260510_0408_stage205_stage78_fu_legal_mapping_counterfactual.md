# Stage205 第78 fu历史合法映射反事实

- line_id：futures_trend
- 当前模式：day
- 记录时间：2026-05-10 04:08
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：数据合法性反事实、只读回测
- 是否重要突破：否，但确认了早期覆盖率问题主要由老燃料油映射造成
- 是否触发A/B：否，不是策略升级，只是历史可交易域审计

## 外部调研与判断

- 参考资料：
  - 上海期货交易所《关于180燃料油期货合约终止交易以及保税380燃料油期货合约挂牌有关事项的通知》：2018-06-27起已挂牌180燃料油相关合约终止交易，保税380燃料油2018-07-16挂牌。
  - 中证网/央广网关于2018年上期所修订燃料油合约的报道：燃料油交易单位、交割品级、合约连续性等均发生制度调整。
  - TQSDK主连/连续合约资料：主连映射可通过`underlying_symbol`得到真实合约，但映射不等于该合约在每个历史日都有可交易K线。
- 我的判断：
  - 用户关于“主力切换周期不应造成整段缺数据”的质疑成立。
  - 第78早期覆盖率不达标主要是`fu.SHFE`老燃料油历史映射与真实可交易K线不一致造成。
  - 因为该处理基于交易所制度切换，而非收益挑选，所以不属于参数过拟合。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage205_stage78_fu_legal_mapping_counterfactual.py`
- 新增生成文件：
  - `examples/portfolio_backtesting/backtest_outputs/stage205_generated_inputs/qmt_roll_stage205_stage78_fu_legal_mapping_counterfactual_fu_from_20180716_stage205_stage78_fu_legal_mapping_counterfactual_v1.csv`
- 修改脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage205_stage78_fu_legal_mapping_counterfactual.py`：修正报告表格函数引用。
- 删除脚本：无
- 新增参数：
  - `FU_LEGAL_START=2018-07-16`
- 修改参数：
  - 仅在生成映射中将`fu.SHFE`在2018-07-16前的`main_contract_tq/main_contract_vt`置空。
- 删除参数：无

## 回测/归因参数

- 数据区间：
  - requested_since_2015：2015-01-05 至 2026-04-30
  - early_data_2015_2017：2015-01-05 至 2017-12-29
  - transition_2018_2019：2018-01-02 至 2019-12-31
  - full_2020_2026：2020-01-01 至 2026-04-30
- 账户规模：200,000
- 成本口径：沿用第78正式回测滑点，手续费为当前框架默认0
- 样本过滤：第78正式品种池与AI池逻辑不变
- 策略/归因口径：
  - baseline_original_mapping：原始全市场主力映射
  - fu_legal_from_20180716：2018-07-16前不映射`fu.SHFE`
  - 注：本阶段所有窗口统一使用2014-01-05预加载，目的是做baseline与fu_legal同口径对照；`full_2020_2026`结果不替代正式2020冷启动报告。

## 结果

### 覆盖率

- baseline requested_since_2015：mapped_days 41,541，present_days 40,758，missing_days 783，coverage 98.1151%，通过。
- baseline early_data_2015_2017：mapped_days 8,544，present_days 8,082，missing_days 462，coverage 94.5927%，未通过。
- fu_legal requested_since_2015：mapped_days 40,925，present_days 40,656，missing_days 269，coverage 99.3427%，通过。
- fu_legal early_data_2015_2017：mapped_days 8,057，present_days 7,980，missing_days 77，coverage 99.0443%，通过。
- fu_legal transition_2018_2019：mapped_days 6,488，present_days 6,488，missing_days 0，coverage 100%，通过。
- 2020-2026覆盖率两组一致：99.2722%。

### 回测结果

- baseline requested_since_2015：
  - 期末权益：4,412,810
  - 总收益：2,106.4050%
  - 最大回撤：-36.1290%
  - Sharpe：0.9581
  - 总滑点：255,590
  - 总交易次数：785
  - 胜率：41.5190%
- fu_legal requested_since_2015：
  - 期末权益：4,412,810
  - 总收益：2,106.4050%
  - 最大回撤：-36.1290%
  - Sharpe：0.9581
  - 总滑点：255,590
  - 总交易次数：785
  - 胜率：41.5190%
- early_data_2015_2017两组均无交易。
- transition_2018_2019两组一致：期末权益190,420，总收益-4.7900%，最大回撤-9.3439%，Sharpe -0.4241，总交易16。
- full_2020_2026两组一致：期末权益4,422,390，总收益2,111.1950%，最大回撤-35.7942%，Sharpe 1.2889，总交易769。该数值只用于同预加载反事实比较，不与正式2020冷启动窗口逐项比较。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage205_stage78_fu_legal_mapping_counterfactual_report_stage205_stage78_fu_legal_mapping_counterfactual_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage205_stage78_fu_legal_mapping_counterfactual_summary_stage205_stage78_fu_legal_mapping_counterfactual_v1.csv`
- coverage：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage205_stage78_fu_legal_mapping_counterfactual_coverage_stage205_stage78_fu_legal_mapping_counterfactual_v1.csv`
- generated_mapping：`examples/portfolio_backtesting/backtest_outputs/stage205_generated_inputs/qmt_roll_stage205_stage78_fu_legal_mapping_counterfactual_fu_from_20180716_stage205_stage78_fu_legal_mapping_counterfactual_v1.csv`

## 结论

- 本阶段结论：
  - 2015-2017覆盖率不达标确实主要由`fu.SHFE`老燃料油历史映射造成；置空2018-07-16前`fu`后，早期覆盖率从94.5927%提升到99.0443%。
  - 但第78在2015-2017仍然没有交易，且2015起点总体结果完全不变，说明早期无交易不是由`fu`缺口造成，而是正式第78信号/合约级指标机制本来没有形成开仓。
  - 2020-2026结果完全不变，说明该合法映射只影响历史数据解释，不污染正式样本。
- 是否进入下一步：是
- 下一步：
  - 用`fu_legal_from_20180716`映射重新跑2015-2019信号漏斗，确认早期无交易是信号/AM问题，而不是覆盖率问题。
  - 单独审计`SM.CZCE`剩余77天缺口，但它规模较小，不再阻断2015-2017覆盖率。

## 过拟合反思

- 运行前判断：否。本阶段按交易所制度切换定义历史可交易域，不按收益选择。
- 运行后判断：否。
- 原因：
  - 该处理没有提升收益，且回测结果完全不变，只提升数据覆盖解释的可信度。
  - 不允许把这个方法泛化成“哪个品种早期不好就剔除哪个品种”，必须有明确上市/终止交易/制度切换依据。

## 继续价值反思

- 运行前判断：有价值。它可以回答用户关于“是不是数据下载处理不对”的疑问。
- 运行后判断：有价值。
- 原因：
  - 已经把早期覆盖率失败归因到`fu`历史合法域，而不是第78策略本身。
  - 下一步可以更干净地解释“覆盖率已修复但仍无交易”的信号机制。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新，等待信号漏斗复核后统一整理。
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：否
