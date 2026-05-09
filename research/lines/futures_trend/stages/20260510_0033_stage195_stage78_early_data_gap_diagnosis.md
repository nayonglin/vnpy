# Stage195 第78早期数据覆盖缺口诊断

- line_id：`futures_trend`
- 当前模式：`day`
- 记录时间：2026-05-10 00:33
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：数据链路诊断，不是策略回测
- 是否重要突破：否；但为2015起点复验前置诊断
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - TqSdk 期货历史K线/主力合约相关资料检索。
  - vn.py 数据库与历史K线导入资料检索。
  - 本地脚本：`download_tqsdk_all_futures_daily_csv.py`、`import_tqsdk_all_futures_daily_to_db.py`、`build_qmt_roll_stage150_stage78_2010_data_repair_feasibility.py`。
- 我的判断：
  - 当前早期覆盖差，不是第78信号层问题，而是历史真实合约日线和郑商所合约代码年代语义问题。
  - 本地目录名虽然是 `tqsdk_daily_2010_2026_04`，但实际下载对象来自当时 TqSdk `query_quotes(ins_class="FUTURE", expired=True)` 可枚举列表；上期所/大商所/能源中心大量2015-2019老合约并未被枚举到。
  - 郑商所三位合约代码存在十年重复，例如 `MA506` 在映射里可代表2015年6月合约，但本地CSV实际日期是2024-06-18至2025-06-16，对2015窗口没有帮助。

## 本次变更

- 新增脚本：无
- 修改脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：诊断覆盖 2015-2020 早期数据缺口
- 账户规模：不适用
- 成本口径：不适用
- 样本过滤：检查 vn.py 数据库 overview、本地 TqSdk CSV、Stage150 repair feasibility 输出
- 策略/归因口径：第78正式基准的数据依赖链路

## 结果

- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：
  - vn.py数据库按交易所最早日期：
    - CFFEX：2020-01-20
    - CZCE：2016-01-04
    - DCE：2019-06-03
    - GFEX：2022-12-22
    - INE：2018-03-26
    - SHFE：2018-09-18
  - 第78关键品种数据库最早日期：
    - `rb.SHFE`：2019-06-03
    - `jm.DCE`：2019-06-03
    - `fu.SHFE`：2019-09-25
    - `cu.SHFE`：2019-06-03
    - `MA.CZCE`：2016-01-04
    - `FG.CZCE`：2016-01-04
  - 合约样例：
    - `rb1505.SHFE`：数据库0根K线；本地CSV不存在
    - `jm1505.DCE`：数据库0根K线；本地CSV不存在
    - `fu1604.SHFE`：数据库0根K线；本地CSV不存在
    - `MA506.CZCE`：数据库有241根K线，但日期是2024-06-18至2025-06-16，不是2015-06合约
  - 既有Stage150结果：
    - 2010起点本地重导入潜在覆盖率仍为 `51.8084%`
    - 2016起点本地重导入潜在覆盖率仍为 `67.8055%`
    - 2019-06起点本地重导入潜在覆盖率仍为 `92.7973%`
    - `raw_can_reimport_days=0`，说明简单重新导入本地CSV不能修复缺口

## 输出文件

- report：无新增；参考 `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage150_stage78_2010_data_repair_feasibility_report_stage150_stage78_2010_data_repair_feasibility_v1.md`
- summary：无新增；参考 `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage150_stage78_2010_data_repair_feasibility_gap_summary_stage150_stage78_2010_data_repair_feasibility_v1.csv`
- orders：不适用
- daily：不适用
- quality：本文件

## 结论

- 本阶段结论：
  - 2015-2020覆盖差的主因是本地历史真实合约K线缺失，以及郑商所三位合约代码年代歧义；不是第78策略自身导致。
  - 简单重新运行现有导入脚本没有意义，因为本地CSV没有对应老合约或对应日期。
  - 需要重新下载和处理数据，但不是“重跑一遍现有下载脚本”这么简单，而是要建立早期合约清单、补真实日线、处理郑商所年代映射，再重建数据库和覆盖报告。
- 是否进入下一步：可以。
- 下一步：
  - 先生成第78 2015-2019所需缺失合约清单。
  - 为上期所/大商所/能源中心补旧合约日线。
  - 为郑商所增加按交易日期解析合约年份的规则，避免 `MA506` 这类跨十年误配。
  - 补齐后复跑 Stage194。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本轮是数据完整性诊断，没有调参数、没有改策略、没有选择性保留收益好的窗口。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：它明确了2015起点审计的堵点在数据链路；继续做数据修复比继续调第78参数更有价值。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：暂不追加，等待真正补齐数据并复跑Stage194后再写入总账。
