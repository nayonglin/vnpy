# Stage015 国内外生数据可得性探针

## 基本信息

- 记录时间：2026-05-25 18:21 CST
- 研究线：`futures_trend_drawdown30_preserve_return`
- 上游基准：`official_stage78_1_defensive_50w_no_sizing_cap`
- 本阶段性质：数据可得性探针，不修改第78-1交易规则，不运行收益回测。
- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage314_domestic_external_data_availability_probe.py`

## 调研和判断结论

- 用户截图里关于 COT 的判断基本正确：COT 更适合作为外盘资金温度计，不适合作为中国期货开仓质量主因子。
- 本阶段转向更贴近中国盘的数据：交易所会员成交持仓排名、仓单/库存、现货/基差。
- 官方页面和 AKShare 文档都显示国内期货会员持仓、仓单、基差等数据可以程序化获取；其中郑商所页面明确提示当日数据需收市结算后生成，因此必须按下一交易日可用处理。
- 仓库环境已有 `akshare 1.18.55`，可以作为第一阶段数据采集适配层；正式接入前仍需保存原始数据和点时化时间，避免第三方接口回填污染。

## 数据源探针结果

可用数据源：

| source_id | family | source_name | exchange | products | rows | frames | 点时化纪律 |
| --- | --- | --- | --- | --- | ---: | ---: | --- |
| member_rank_shfe | member_rank | 上期所会员成交持仓排名 | SHFE | RB,RU,FU,AU,CU,HC,SP | 616 | 30 | 交易日16:30左右更新，只用于下一交易日及之后 |
| member_rank_czce | member_rank | 郑商所会员成交持仓排名 | CZCE | AP,CF,FG,MA,OI,SA,SH,SM | 2039 | 105 | 收市结算后生成，只用于下一交易日及之后 |
| member_rank_gfex | member_rank | 广期所日成交持仓排名 | GFEX | LC,SI | 80 | 4 | 收市结算后生成，只用于下一交易日及之后 |
| warehouse_shfe | warehouse_receipt | 上期所仓单日报 | SHFE | RB,RU,FU,AU,CU,HC,SP | 400 | 28 | 发布后才可用，只用于下一交易日及之后 |
| warehouse_czce | warehouse_receipt | 郑商所仓单日报 | CZCE | AP,CF,FG,MA,OI,SA,SH,SM | 805 | 23 | 发布后才可用，只用于下一交易日及之后 |
| warehouse_gfex | warehouse_receipt | 广期所仓单日报 | GFEX | LC,SI | 40 | 2 | 发布后才可用，只用于下一交易日及之后 |
| basis_100ppi | spot_basis | 生意社现货与基差 | ALL | 19个第78-1品种 | 18 | 1 | 第三方数据，保守滞后到下一交易日使用 |

暂不可用或需修复：

| source_id | family | source_name | exchange | products | error_type | error_message |
| --- | --- | --- | --- | --- | --- | --- |
| member_rank_dce | member_rank | 大商所会员持仓排名 | DCE | JM,LH | BadZipFile | File is not a zip file |
| warehouse_dce | warehouse_receipt | 大商所仓单日报 | DCE | JM,LH | JSONDecodeError | Expecting value |

## 第78-1品种覆盖

- 总品种数：`19`
- 至少有一类外生数据覆盖：`19`
- 有会员持仓排名覆盖：`17`
- 有仓单/库存覆盖：`17`
- 有现货/基差覆盖：`19`
- DCE 的 `jm.DCE`、`lh.DCE` 当前只确认基差可用，会员持仓和仓单接口需要单独修。

## 判定

- `domestic_member_rank_data_layer_ready_for_feature_build`

这个判定只表示“国内外生数据层值得进入因子构建”，不表示策略已经改善。

## 下一步最小可验证实验

优先顺序：

1. 会员持仓净变化因子：
   - 前20多头合计变化；
   - 前20空头合计变化；
   - 前20净多变化；
   - 净多变化与趋势方向一致则加分，反向则扣分；
   - 做滚动分位或zscore，但先固定窗口，不扫参。
2. 仓单/库存变化因子：
   - 仓单增加对多头质量扣分、对空头质量加分；
   - 仓单减少反向处理；
   - 只作为弱辅助，不能单独禁止开仓。
3. 基差/期限结构因子：
   - 主力基差、基差变化、近远月结构；
   - 只验证是否能减少追涨后的20日不利波动。

每条外生记录必须生成：

- `available_datetime`
- `product_vt_symbol`
- `direction`
- `external_quality_score`
- `suggested_volume_multiplier`
- `veto_flag`
- `confidence`

然后沿用 Stage013 评估器做 valid/test 分桶；分桶不过，不进入 A/C 回测。

## 回测指标

本阶段没有运行新的策略收益回测，因此没有新的期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数或胜率。

当前对照仍沿用 Stage012 最强内部风控线索：

- `C_pressure040`
- 期末权益：`25,429,055`
- 总收益：`4985.811%`
- 最大回撤：`-31.0767%`
- Sharpe：`1.2650`
- 总滑点：`2,047,490`
- 总交易次数：`862`
- 胜率：`45.0346%`

## 过拟合反思

- 运行前：不是过拟合。
- 原因：本阶段只检验数据可得性和覆盖，不使用收益结果调参数。
- 运行后：仍不是过拟合。
- 原因：数据源可用性探针不产生交易信号，也没有挑样本让结果好看。
- 风险提示：下一阶段如果反复调滚动窗口、阈值和品种权重直到收益好看，就会过拟合；因此应先固定低自由度公式，再做样本外分桶。

## 继续价值反思

- 运行前：有价值。
- 原因：内生风控已接近边界，外生开仓质量因子可能在不粗暴降仓的情况下减少差开仓。
- 运行后：继续有价值。
- 原因：国内数据覆盖明显优于 COT，且更贴近中国期货的供需和资金结构；值得进入特征构建和分桶验证。

## 输出文件

- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage314_domestic_external_data_availability_probe_source_checks_stage314_domestic_external_data_availability_probe_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage314_domestic_external_data_availability_probe_product_coverage_stage314_domestic_external_data_availability_probe_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage314_domestic_external_data_availability_probe_report_stage314_domestic_external_data_availability_probe_v1.md`
