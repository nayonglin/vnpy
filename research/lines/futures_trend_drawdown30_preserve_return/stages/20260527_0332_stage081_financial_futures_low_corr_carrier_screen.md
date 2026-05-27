# Stage081 金融期货低相关承载只读筛查

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：day
- 记录时间：2026-05-27 03:32 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读筛查；不修改第78-1、C3、AI池、商品池、入场、退出或仓位规则
- 是否重要突破：否
- 是否触发A/B：否；当前只是净值层/资产层筛查，没有进入真实引擎A/C

## 外部调研与判断

- 参考资料：
  - AQR/CBS 论文《A Century of Evidence on Trend-Following Investing》：`https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2993026`，说明趋势跟随研究通常覆盖股指、债券、外汇、商品等多资产市场。
  - 同文PDF镜像：`https://www.efficient.com/pdfs/A_Century_of_Evidence_on_Trend-Following_Investing.pdf`，用于确认多资产趋势跟随和危机分散的研究背景。
- 我的判断：
  - 金融期货作为低相关承载工具有第一性原理上的合理性：它不是继续在同一商品趋势路径上调阈值，而是换资产风险来源。
  - 但合理性不等于当前形状可用。本阶段只允许预声明窗口和粗权重筛查，不能因为某个品种全样本好看就继续调窗口、权重或只挑单品种。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage381_financial_futures_low_corr_carrier_screen.py`
- 修改脚本：无正式策略脚本修改；本脚本内部补充 `_md_table` 兼容报告输出
- 删除脚本：无
- 新增参数：
  - 金融期货品种：`IF/IC/IH/IM/T/TF/TS/TL`
  - 时间序列动量窗口：`20/60/120`
  - 组合C3权重：`80%/90%/95%`
  - 单次调仓成本：`2 bps`
  - 目标最大回撤：`-30%`
  - 收益保留闸门：`80%`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：C3公共区间 `2020-01-01` 至 `2026-04-30`；金融期货覆盖因品种上市不同而不同。
- 账户规模：净值层按 `500,000` 起始权益度量；不是实盘保证金/整数手数引擎。
- 成本口径：金融期货动量腿按持仓变动计 `2 bps`；C3收益沿用既有 Stage336 日度曲线。
- 样本过滤：只使用 CFFEX 主力映射与本地日线；换月日收益置零，避免把换月跳变当作收益。
- 策略/归因口径：
  - 独立腿：各金融期货品种 `20/60/120` 日时间序列动量。
  - 篮子：国债期货、股指期货、金融期货全篮子。
  - 组合：C3与金融篮子按 `80/90/95` 粗权重合成，并和同权重现金稀释对照。

## 结果

- 期末权益：
  - 最优全样本组合 `c3_95_rates_tsmom60_5`：`26,076,145.31`
  - 最优独立篮子 `equity_index_tsmom120`：`597,948.15`
- 总收益：
  - `c3_95_rates_tsmom60_5`：`5115.2291%`
  - 同权重现金对照：`5111.9950%`
  - 独立国债60日动量篮子：`1.2517%`
  - 独立国债120日动量篮子：`7.2478%`
  - 独立股指120日动量篮子：`19.5896%`
- 最大回撤：
  - `c3_95_rates_tsmom60_5`：`-29.7114%`
  - 同权重现金对照：`-29.7155%`
  - 独立国债60日动量篮子：`-3.8920%`
  - 独立国债120日动量篮子：`-3.2104%`
  - 独立股指120日动量篮子：`-35.3600%`
- Sharpe：
  - `c3_95_rates_tsmom60_5`：`1.6175`
  - 独立国债60日动量篮子：`0.1247`
  - 独立国债120日动量篮子：`0.6522`
  - 独立股指120日动量篮子：`0.2880`
- 总滑点：无真实引擎滑点；金融腿只计 `2 bps` 换仓成本；C3源口径未在本阶段重算。
- 总交易次数：无真实引擎成交次数；金融腿只统计仓位翻转换手。
- 胜率：本阶段不统计交易胜率。
- 其他关键指标：
  - 全样本组合候选数：`3`
  - 多窗口稳健候选数：`0`
  - 最优组合相对C3收益保留：`83.9552%`
  - 最优组合相对同权重现金收益增加：`3.2340pp`
  - 最优组合相对同权重现金回撤改善：`0.0041pp`
  - 最优组合弱窗口 `weak_2022_path` 相对现金收益：`-0.0529pp`
  - 最优组合 `ytd_2026` 相对现金收益：`-0.0365pp`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage381_financial_futures_low_corr_carrier_screen_report_stage381_financial_futures_low_corr_carrier_screen_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage381_financial_futures_low_corr_carrier_screen_combo_summary_stage381_financial_futures_low_corr_carrier_screen_v1.csv`
- orders：无
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage381_financial_futures_low_corr_carrier_screen_product_daily_stage381_financial_futures_low_corr_carrier_screen_v1.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage381_financial_futures_low_corr_carrier_screen_decision_stage381_financial_futures_low_corr_carrier_screen_v1.json`

## 结论

- 本阶段结论：
  - 金融期货方向理论上值得看，但当前 CFFEX 简单时间序列动量承载不够强。
  - 最好组合是 `95%C3 + 5%国债期货60日动量`，全样本过 `-30%` 回撤和 `80%` 收益保留，但它几乎等同于 `95%C3 + 5%现金`：收益只多 `3.2340pp`，回撤只改善 `0.0041pp`。
  - 多窗口稳健候选为 `0`；弱窗口和2026年初并不能稳定跑赢现金。
- 是否进入下一步：不进入正式真实引擎A/C；只保留为“金融资产低相关承载仍可研究，但当前简单动量形状不推广”的诊断。
- 下一步：
  - 不继续围绕 `20/60/120` 相邻窗口、`5%/10%/20%` 小权重或单一金融品种做小数救援。
  - 若继续金融期货方向，必须换成更可执行的真实风险预算/保证金模型，并先证明独立腿能显著跑赢现金稀释，而不是只靠稀释C3过线。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：本阶段不是过拟合，但后续若继续调金融期货窗口、挑单品种或调小数权重，就会变成过拟合。
- 原因：
  - 品种、窗口、成本和组合权重均预先固定。
  - 判定依赖全样本、多起点、弱窗口、现金对照，不按单一最好结果推广。
  - 失败后不继续救参数。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：金融期货这个“资产类别方向”仍有研究价值，但当前简单动量形状继续价值低。
- 原因：
  - 外部证据支持多资产趋势跟随包含金融期货。
  - 本地数据也显示部分金融期货腿与C3低相关、部分为正收益。
  - 但当前收益贡献太小，实际组合改善基本等同现金稀释，达不到“收益不显著降低且曲线更平滑”的强候选标准。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录金融期货简单动量形状不晋级。
- 是否更新 `research/registry.md`：是，更新当前线最新阶段和下一步禁区。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md`；`memory.md` 可暂不追加。
