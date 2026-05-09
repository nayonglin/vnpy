# Stage192 手工池 add-one 候选验证

- line_id：`futures_trend`
- 当前模式：`day`
- 记录时间：2026-05-09 17:44 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：第78趋势策略品种池候选 A/B 验证
- 是否重要突破：否
- 是否触发A/B：是。候选品种若有效，可能影响第78正式池/卫星品种配置。

## 外部调研与判断

- 参考资料：
  - Moskowitz/Ooi/Pedersen 的 time-series momentum 研究强调跨资产期货趋势效应与可交易流动合约样本。
  - `amstrdm/mlm-trend-following` 等趋势跟踪实现把连续合约、前月合约执行、波动过滤、定期再平衡作为工程核心。
- 我的判断：
  - 期货趋势品种池不能只看历史收益，应优先看可交易性、流动性、波动/趋势地形、成本和与当前策略机制的交互。
  - 本阶段是候选筛查，不是正式晋级。若某候选仅全样本表现好，仍需分窗、冷启动、30万实盘约束和影子盘验证。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage192_manual_pool_add_one_validation.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - 实验标签：`qmt_roll_stage192_manual_pool_add_one_validation`
  - 候选：`UR.CZCE`、`pg.DCE`、`sn.SHFE`、`eb.DCE`、`fu.SHFE`
  - 对照：`manual18_no_fixed_satellite`
  - AI 口径：原月度 `ai_top8_entry_filter`，并在月度AI后固定追加单个候选卫星品种。
  - 卫星品种风控排除：`streak_risk_state_exclusion_mode=profit_only`
- 修改参数：无正式第78参数修改
- 删除参数：无

## 回测/归因参数

- 数据区间：2020-01-01 至 2026-04-30
- 账户规模：200,000
- 成本口径：沿用当前元数据滑点口径；本轮 `total_commission=0`
- 样本过滤：
  - 先用手工18池作为基础池。
  - 月度AI开始前仅允许手工18池。
  - 月度AI开始后使用原 `ai_top8_entry_filter`，再固定追加一个 add-one 候选。
- 策略/归因口径：
  - 复用第78当前核心机制：pairwise v2、long015 volume tilt、同向相关性门控。
  - 每次只加一个候选，不做 TopN/阈值救结果。

## 结果

| 实验臂 | 候选 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 胜率 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| manual18_no_fixed_satellite | - | 3,931,630 | 1865.8150% | -36.9907% | 1.2091 | 259,510 | 723 | 41.4634% |
| manual18_plus_UR_CZCE | UR.CZCE | 3,511,495 | 1655.7475% | -36.9907% | 1.1374 | 278,640 | 781 | 40.9548% |
| manual18_plus_pg_DCE | pg.DCE | 3,616,590 | 1708.2950% | -36.9907% | 1.1500 | 261,000 | 772 | 40.6091% |
| manual18_plus_sn_SHFE | sn.SHFE | 4,016,850 | 1908.4250% | -36.9907% | 1.2160 | 247,770 | 772 | 42.6396% |
| manual18_plus_eb_DCE | eb.DCE | 3,895,580 | 1847.7900% | -36.9907% | 1.2022 | 259,710 | 787 | 40.8978% |
| manual18_plus_fu_SHFE | fu.SHFE | 4,637,530 | 2218.7650% | -36.9907% | 1.2922 | 261,740 | 782 | 42.1053% |

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage192_manual_pool_add_one_validation_report.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage192_manual_pool_add_one_validation_summary.csv`
- summary_json：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage192_manual_pool_add_one_validation_summary.json`
- equity_html：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage192_manual_pool_add_one_validation_equity_curves.html`
- equity_csv：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage192_manual_pool_add_one_validation_equity_curves.csv`
- trades：各实验臂 `*_trades_2020_2026_04.csv`
- daily：各实验臂 `*_daily.csv` / `*_daily_equity.csv`
- quality：各实验臂 `*_entry_risk_diagnostics_2020_2026_04.csv`、`*_entry_candidate_snapshots_2020_2026_04.csv`

## 结论

- 本阶段结论：
  - `fu.SHFE` 是本轮唯一明显胜出的 add-one 卫星品种：相对手工18池，期末权益增加 `705,900`，总收益增加 `352.95` 个百分点，Sharpe 增加 `0.0831`，最大回撤百分比未恶化。
  - `sn.SHFE` 小幅改善：期末权益增加 `85,220`，Sharpe 增加 `0.0069`，但远弱于 `fu.SHFE`，只能作为观察候选。
  - `UR.CZCE`、`pg.DCE`、`eb.DCE` 不通过本轮筛查，均弱于手工18池或边际不足。
- 是否进入下一步：
  - `fu.SHFE` 保持当前官方卫星候选/正式路径。
  - `sn.SHFE` 可进入下一轮“官方fu + sn”组合验证，但不能直接替代或并入正式版本。
  - `UR.CZCE`、`pg.DCE`、`eb.DCE` 暂停晋级。
- 下一步：
  - 若继续产品池研究，优先跑 `manual18 + fu + sn` 与官方第78的分窗/冷启动/30万实盘约束验证。
  - 不做 UR/pg/eb 的参数补丁式救结果。

## 过拟合反思

- 运行前判断：有轻度风险，但可控。
- 运行后判断：本轮实验本身不过拟合；若继续根据结果调候选排序、TopN或阈值，就会过拟合。
- 原因：
  - 本轮候选来自前一阶段的结构相似性探测，且预先固定为逐个 add-one，不在结果后改规则。
  - 但选择“表现最好的历史候选”天然需要后续 OOS、分窗和实盘影子盘反证，不能直接当成未来收益承诺。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是，但方向收窄。
- 原因：
  - 本轮明确区分了“像手工池”的候选与“真的对第78资金路径有帮助”的候选。
  - 继续价值集中在 `fu.SHFE` 的正式保留和 `sn.SHFE` 的组合反证；其余候选继续投入的边际价值低。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新，除非下一步 `fu + sn` 通过分窗和30万约束验证。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md`，不追加 `memory.md`。
