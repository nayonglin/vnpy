# Stage339 年度赢家经济驱动与数据源缺口审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 09:27 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：低单笔风险扩池方向的经济驱动、相关性和 source backlog 决策板
- 是否重要突破：否；确认扩池方向仍有价值，但当前仍不能晋级
- 是否触发A/B：否；没有策略版本进入正式候选、paper 或交易白名单

## 外部调研与判断

- 参考资料：
  - EIA Petroleum & Other Liquids / Weekly Petroleum Status Report：`https://www.eia.gov/petroleum/index.php`
  - EIA petroleum data summary：`https://www.eia.gov/petroleum/data.php/summary`
  - LME warehouse and stock reports：`https://www.lme.com/en/market-data/reports-and-data/warehouse-and-stocks-reports`
  - USDA WASDE official report：`https://www.usda.gov/oce/commodity/wasde/`
  - USDA Historical WASDE data：`https://www.usda.gov/historical-wasde-report-data-3`
  - SHFE Daily Data：`https://www.shfe.cn/eng/reports/StatisticalData/DailyData/`
- 我的判断：
  - Stage338 证明年度趋势机会确实存在，但有效分散单位不是“品种数量”，而是独立经济驱动和低相关风险槽。
  - EIA/LME/USDA/SHFE 等官方源可以形成 source contract 候选；但 source 候选不等于 selector，必须继续证明 active fetch、PIT raw hash、字段稳定、预测力、真实 TCA。
  - 全球官方源对国内商品期货多为宏观或间接映射，国内交易所源更直接，但可能存在端点发现、授权、解析稳定性和延迟问题。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage639_economic_driver_source_gap_board.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - 目标年度赢家家族：`energy_oil/base_metals/grains_oilseeds/petrochem`
  - 当前有效风险槽：`4`
  - 目标有效风险槽：`7`
  - 禁止输出：selector、paper、A/B、交易白名单
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage541/638 冻结输出，年度范围 `2020-2026`
- 账户规模：不新增账户回测
- 成本口径：不新增成本重放
- 样本过滤：
  - 只读 Stage541 单品种年度机会、Stage638 年度独立风险槽审计、Stage633 产品相关性地图
  - 只关注 Stage338 中反复出现但不可直接晋级的四个家族
  - 读取既有 Stage629/635/620/624 source 证据，但不联网抓新数据
- 策略/归因口径：
  - 不重放策略、不改交易规则、不扫参数
  - 不连接 CTP，不生成 selector/paper/交易白名单
  - 本阶段只回答“年度赢家能否拆成独立风险槽和可执行 source backlog”

## 结果

- 期末权益：不适用；本阶段不是新策略回测
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：
  - decision：`economic_driver_source_gap_mapped_selector_locked`
  - target families：`4`
  - source candidate rows：`8`
  - official source candidate rows：`6`
  - active fetch validated rows：`0`
  - families with annual hits：`4`
  - families with source candidates：`4`
  - families with active fetch：`0`
  - deployable new slots：`0`
  - paper rows：`0`
  - trading whitelist rows：`0`
  - current/target effective slots：`4/7`
  - hard gates：`8/8`

## 家族结果

| 家族 | 年度 top6 命中年数 | 命中次数 | 年度 top6 PnL 合计 | 代表品种 | P0 命中 | 高相关拒绝 | 数据/流动性拒绝 | source 候选 | 官方源候选 | active fetch | 平均对 P0 最大绝对相关 | 判断 |
| --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `energy_oil` | 6 | 8 | 130310.0 | `bu.SHFE,lu.INE,pg.DCE` | 3 | 5 | 0 | 2 | 2 | 0 | 0.5492 | P0 或高相关重复，不是新槽 |
| `base_metals` | 6 | 7 | 102315.0 | `al.SHFE,ao.SHFE,bc.INE` | 3 | 4 | 0 | 2 | 2 | 0 | 0.2850 | P0 或高相关重复，不是新槽 |
| `grains_oilseeds` | 6 | 11 | 74620.0 | `a.DCE,c.DCE,m.DCE,rr.DCE,y.DCE` | 8 | 2 | 0 | 2 | 1 | 0 | 0.3717 | P0 或高相关重复，不是新槽 |
| `petrochem` | 6 | 7 | 48895.0 | `PX.CZCE,v.DCE` | 6 | 0 | 1 | 2 | 1 | 0 | 0.4933 | P0 或数据源未验证，不是新槽 |

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage639_economic_driver_source_gap_board_report_stage639_economic_driver_source_gap_board_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage639_economic_driver_source_gap_board_decision_stage639_economic_driver_source_gap_board_v1.json`
- orders：不适用
- daily：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage639_economic_driver_source_gap_board_family_driver_board_stage639_economic_driver_source_gap_board_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage639_economic_driver_source_gap_board_source_backlog_stage639_economic_driver_source_gap_board_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage639_economic_driver_source_gap_board_annual_top6_detail_stage639_economic_driver_source_gap_board_v1.csv`
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage639_economic_driver_source_gap_board_gates_stage639_economic_driver_source_gap_board_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage639_economic_driver_source_gap_board_chart_stage639_economic_driver_source_gap_board_v1.png`

## 图表视觉复盘

- 左上图：
  - `energy_oil` 有 `3` 个 P0 命中和 `5` 个高相关命中。
  - `base_metals` 有 `3` 个 P0 命中和 `4` 个高相关命中。
  - `grains_oilseeds` 有 `8` 个 P0 命中和 `2` 个高相关命中。
  - `petrochem` 有 `6` 个 P0 命中和 `1` 个数据/流动性拒绝。
  - 紫色 worklist/monitor 全为 `0`，说明这些年度赢家还没有进入可执行监控通道。
- 右上图：
  - 四个家族都有 `2` 条 source 候选。
  - `energy_oil/base_metals` 的官方候选为 `2/2`，`grains_oilseeds/petrochem` 为 `1/2`。
  - 橙色 active fetch validated 全为 `0`，这是当前不能晋级的核心缺口。
- 左下图：
  - 四个家族都在 `0.15` 相关性观察线右侧；`energy_oil/petrochem` 尤其靠右。
  - 年度机会 PnL 越大，并不代表越独立；大机会往往仍然贴近核心 P0 风险。
- 右下图：
  - 绿色 gate 包含 fail-closed lock，不代表可以交易。
  - `deployable_new_slot_zero=0`、`paper=0`、`whitelist=0` 是正确锁定纪律。
  - `target_effective_slots_still_not_met=4/7` 说明低单笔风险扩池的核心目标仍未满足。

## 结论

- 本阶段结论：
  - 用户提出的“减少单笔风险、扩大品种池、每年抓部分品种趋势，同时避免高相关品种风险”是正确方向，但不能用简单宽池实现。
  - 当前四个反复出现的年度赢家家族都有机会，也都能找到 source 候选；但它们多数仍是 P0 重复或高相关重复，active fetch 和 PIT 样本均为 `0`，不能成为新增独立风险槽。
  - 当前有效风险槽仍是 `4/7`，deployable new slots 仍为 `0`。
- 是否进入下一步：继续，但只做 source contract/fetch probe，不做交易池扩容。
- 下一步：
  - 优先选择一个家族做 source probe，而不是同时铺开。
  - 候选优先级：
    - `base_metals`：`SHFE Daily Data + LME warehouse stocks`，优点是官方源更直接、频率高、结构清晰。
    - `energy_oil`：`EIA WPSR + SHFE/INE daily data`，优点是趋势机会大，但与核心风险相关性也高，需要更强独立性证明。
  - 对每个 source probe 必须建立 raw hash、PIT 日期、字段稳定、事件/库存/仓单方向定义，再进入固定 outcome/TCA 审计。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：
  - 本阶段没有调参数、没有改变交易规则、没有用收益结果生成交易白名单。
  - 年度赢家只用于解释机会结构，不作为事前 selector。
  - 结论是锁定晋级，而不是为了迎合扩池想法放宽门槛。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但应该收窄到 source/PIT/TCA。
- 原因：
  - 年度机会反复出现，说明扩池的目标方向不是伪命题。
  - 当前缺口不是风险参数，而是“事前如何选对低相关家族/品种”。
  - 如果 source probe 能形成稳定 PIT 账本，才有资格继续做 selector；否则扩池只会增加同源风险和噪音。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage339 当前状态。
- 是否更新 `research/registry.md`：是，更新当前阶段摘要。
- 是否追加根目录 `memory.md/back_log.md`：否；本阶段不是正式候选、路线废弃、跨线合并或重大突破。
