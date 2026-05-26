# Stage044 C3利润留存账户层筛查

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-05-26 03:59 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：部署层 A vs C 筛查；不修改78-1/C3正式信号。
- 是否重要突破：否，反证“用利润自筹reserve可以替代11.5万外部现金”的形状。
- 是否触发A/B：是，但只做部署层 A vs C；没有独立 B alpha。

## 外部调研与判断

- 参考资料：
  - CPPI/TIPP 和 portfolio insurance 文献支持“现金/保险账户 + 风险资产”的第一性原理，用现金垫吸收回撤。
  - drawdown-control 和 managed futures 波动管理文献也说明，组合保险能降低回撤，但可能牺牲后续趋势利润或在快速下跌前来不及建立保护。
  - 参考链接：ScienceDirect `Time series momentum and volatility scaling`、SSRN `Robust Portfolio Insurance`、Stanford `multiperiod portfolio drawdown`。
- 我的判断：
  - 利润留存是低过拟合方向，因为它不看品种、不看某年、不看单次亏损原因，只处理账户层财富分配。
  - 但如果 reserve 必须靠盈利慢慢积累，就天然无法保护“刚启动后不久遇到深回撤”的窗口；这个缺陷必须用多起点测试验证。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage344_c3_profit_escrow_deployment.py`
- 修改脚本：无正式策略修改。
- 删除脚本：无。
- 新增参数：
  - `seed_reserve`：初始reserve种子资金，测试 `0/5万/6.7万/7.5万/10万/11.5万`
  - `skim_ratio`：月末高水位新增利润留存比例，测试 `0/25%/50%/100%`
  - `reserve_cap`：reserve上限，测试 `6.7万/11.5万`
  - `SLIPPAGE_MULTIPLIERS=(1x,2x,3x)`
- 修改参数：无。
- 删除参数：无。

## A/C定义与闸门

- A：C3，即 `c3_active100_cash0`。
- C：C3 + 账户层 reserve。
- 规则：交易账户初始仍按50万C3路径；reserve不参与交易。月末若总权益创新高，则按 `skim_ratio` 将新增高水位利润转入 reserve，直到 `reserve_cap`。
- 闸门：
  - 最大回撤 `>= -30%`
  - 正收益窗口收益保留 `>=80%`
  - 负收益窗口要求不比C3更差且回撤过线
  - 多起点窗口 `9/9` 通过才算严格通过

## 结果

- C3基准：
  - 期末权益：`30,925,650`
  - 总收益：`6085.1300%`
  - 最大回撤：`-31.0767%`
  - 总滑点：沿用C3 `1,556,750`
  - 总交易次数：沿用C3 `757`
  - 胜率：沿用C3 `45.3826%`
- 完全不加初始reserve，只靠利润留存：
  - `skim100_cap67k`：全样本总收益 `5821.2882%`、收益保留 `95.6642%`、最大回撤 `-30.5488%`、多周期 `4/9` 通过。
  - 原因：`start_2022` 窗口在深回撤前没有建立足够reserve，最大回撤仍为 `-34.9148%`。
- 小初始reserve + 利润补足：
  - `seed67_no_skim`：全样本总收益 `5366.0758%`、收益保留 `88.1834%`、最大回撤 `-29.9941%`，但最差多周期回撤 `-31.8094%`，仅 `8/9` 通过。
  - `seed67_skim100_cap115k`：全样本总收益 `5139.7958%`、收益保留 `84.4648%`、最大回撤 `-29.7870%`，但最差多周期回撤仍 `-31.8094%`，仅 `8/9` 通过。
  - `seed100_no_skim`：全样本总收益 `5070.9417%`、收益保留 `83.3333%`、最大回撤 `-29.7918%`，但最差多周期回撤 `-30.4744%`，仅 `8/9` 通过。
- 严格通过项：
  - `seed115_no_skim`：全样本总收益 `4947.2602%`、收益保留 `81.3008%`、最大回撤 `-29.7007%`、多周期 `9/9` 通过、最差多周期回撤 `-29.9039%`。
  - 但这等价于 Stage041 的 `11.5万` 外部现金缓冲，没有利润留存带来的新增优势。
- 滑点压力：
  - `2x` 下没有任何 profile 严格通过。
  - `seed115_no_skim` 在 `2x` 下全样本总收益 `4694.1302%`、最大回撤 `-31.2917%`、多周期仅 `4/9` 通过。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage344_c3_profit_escrow_deployment_report_stage344_c3_profit_escrow_deployment_v1.md`
- profile_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage344_c3_profit_escrow_deployment_profile_summary_stage344_c3_profit_escrow_deployment_v1.csv`
- window_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage344_c3_profit_escrow_deployment_window_summary_stage344_c3_profit_escrow_deployment_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage344_c3_profit_escrow_deployment_daily_stage344_c3_profit_escrow_deployment_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage344_c3_profit_escrow_deployment_decision_stage344_c3_profit_escrow_deployment_v1.json`

## 结论

- 本阶段结论：`profit_escrow_no_incremental_vs_external_cash`
- 是否进入下一步：不进入真实引擎；不作为新候选推广。
- 核心经验：
  - 利润留存自身方向有低过拟合逻辑，但无法替代启动时就存在的现金缓冲。
  - 如果目标要求多起点都过30%，`start_2022` 这种“启动后不久遇到深回撤”的窗口要求启动日已有足够reserve。
  - 因此 Stage041 的 `11.5万` 不是因为参数调得巧，而是由最差启动窗口的路径结构决定的。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：本轮不是过拟合，但继续在 `6.7万/7.5万/10万` 附近调小数会过拟合。
- 原因：
  - 本轮只测试粗档位、通用账户层规则和多起点窗口。
  - 失败集中在 `start_2022`，说明问题是启动时 reserve 不足，不是利润留存比例小数可救。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：利润留存形状继续价值低；总研究线仍有价值。
- 原因：
  - 它把“能不能靠盈利自筹缓冲”这个现实问题证伪了。
  - 下一步应停止内部账户层小数修补；若要继续达成目标，要么接受 Stage041 正常成本部署候选，要么寻找真正正收益、低相关、能覆盖 `start_2022/2021` 弱窗口的独立收益源。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录利润留存路线没有新增优势。
- 是否更新 `research/registry.md`：是，最新阶段更新为 Stage044。
- 是否追加根目录 `memory.md/back_log.md`：是，本阶段属于路线反证和部署边界确认。
