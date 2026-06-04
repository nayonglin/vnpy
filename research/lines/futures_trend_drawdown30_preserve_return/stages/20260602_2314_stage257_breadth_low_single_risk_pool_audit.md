# Stage257 低单笔风险扩池/相关簇约束审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-02 23:14 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：结构性负验证；固定 Stage526 核心不动，用 `11.5万` 卫星仓审计“低单笔风险 + 扩大非核心商品池 + 产品族保证金 cap + 同向相关性闸门”。
- 是否重要突破：否，但属于重要否定结论。
- 是否触发A/B：否。本阶段没有形成值得接入正式版本或与第78正式基准结合的候选。

## 外部调研与判断

- 参考资料：
  - AQR Trend Following / Managed Futures 资料：长期趋势跟随的核心价值来自跨市场、跨资产的独立趋势机会与风险分散。
  - Rob Carver / `pysystemtrade`：系统化期货组合通常用 instrument diversification、相关性、风险目标和 instrument weights 管理多品种组合，而不是简单增加品种数量。
- 我的判断：
  - “减少单笔风险，扩大品种池，每年抓到部分品种趋势收益”在第一性原理上成立：趋势收益本身稀疏，更多独立市场能增加命中机会。
  - 但扩池不是 alpha。若没有更强的事前品种状态，宽池会把大量震荡噪音也放进来；相关性闸门只能降低集中风险，不能把弱趋势品种变成好品种。
  - 所以本阶段只测三个粗档，不扫 `risk/cap/corr/maxpos` 小数；如果失败，就说明当前“简单宽池/上一年为正宽池”方向不值得救参。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage557_breadth_low_single_risk_pool_audit.py`
- 修改脚本：
  - 无策略本体默认修改。
  - 审计脚本内修复两处汇总层兼容性：缺失 entry diagnostic 列时填 `0`；报告生成时避免旧 summary 同名列 suffix 冲突。
- 删除脚本：无。
- 新增参数：
  - `breadth_all_noncore_r020_famcap20_corr5075_maxpos8`
  - `breadth_prevpos_r020_famcap20_corr5075_maxpos8`
  - `breadth_prevpos_r015_famcap15_corr5075_maxpos10`
  - 共同结构：`SLEEVE_CAPITAL=115000`、`START_TRADE_DT=2021-01-01`、非核心商品宽池、同产品族保证金 cap、20日同向相关性闸门 `start=0.50/full=0.75/floor=0.40`。
- 修改参数：无正式参数修改。
- 删除参数：无。

## 回测/归因参数

- 数据区间：`2020-2026`，卫星新开从 `2021-01-01` 后开始。
- 账户规模：组合口径 `615000`，Stage526 核心不动，扩池卫星仓 `115000`。
- 成本口径：正常成本 + `2x/3x` 滑点压力；broker10 保证金仍按 Stage526 exact margin 口径合并。
- 样本过滤：
  - `all_noncore`：所有 eligible 非核心商品均可新开仓。
  - `prev_year_positive`：只允许上一年单品种真实账本为正的非核心商品新开仓；不限制 TopN。
- 策略/归因口径：
  - 固定复用下一真实窗口/C3 配置和 Stage526 核心 daily。
  - 不改入场/出场/AI池/产品池历史定义；只改变卫星仓宽池与风险预算结构。
  - `future_year_single_product_pnl_sum` 只用于事后解释，不参与交易。

## 结果

### A/C 总览

| 版本 | 期末权益 | 总收益 | 最大回撤 | Ulcer | Sharpe | 卫星PnL | 63日p05 | 126日p05 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Stage526 | 23,369,505 | 3699.9195% | -36.2670% | 14.4691 | 1.6385 | 0 | -18.2169% | -10.9700% |
| Stage256 fixed top6 | 23,423,510 | 3708.7008% | -36.0729% | 14.3808 | 1.6433 | 54,005 | -17.9434% | -10.6742% |
| 全非核心宽池 r020 | 23,378,900 | 3701.4472% | -36.3714% | 14.4902 | 1.6374 | 9,395 | -18.2402% | -11.0259% |
| 上年为正宽池 r020 | 23,351,260 | 3696.9528% | -36.4055% | 14.5093 | 1.6355 | -18,245 | -18.2589% | -11.0045% |
| 上年为正宽池 r015 | 23,354,530 | 3697.4846% | -36.4126% | 14.5039 | 1.6361 | -14,975 | -18.2667% | -11.0047% |

### 成本压力

- Stage526：`2x DD=-39.0565%`，`3x DD=-42.0555%`。
- Stage256 fixed top6：`2x DD=-38.8479%`，`3x DD=-41.8307%`。
- 全非核心宽池 r020：`2x DD=-39.1923%`，`3x DD=-42.2290%`。
- 上年为正宽池 r020：`2x DD=-39.2171%`，`3x DD=-42.2407%`。
- 上年为正宽池 r015：`2x DD=-39.2217%`，`3x DD=-42.2423%`。

### 卫星 standalone

- 全非核心宽池 r020：卫星期末 `124,395`，PnL `9,395`，收益 `8.1696%`，最大回撤 `-28.5068%`，Sharpe `0.1709`，交易 `449`，滑点 `7,430`，最大 broker10 sleeve margin/equity 约 `106.5185%`。
- 上年为正宽池 r020：卫星期末 `96,755`，PnL `-18,245`，收益 `-15.8652%`，最大回撤 `-22.0535%`，Sharpe `-0.5013`。
- 上年为正宽池 r015：卫星期末 `100,025`，PnL `-14,975`，收益 `-13.0217%`，最大回撤 `-20.0887%`，Sharpe `-0.4570`。

### 归因观察

- 全非核心宽池比 Stage526 多赚 `9,395`，但回撤、Ulcer、63/126日 p05 均劣化；它不是更平滑的组合结构。
- `prev_year_positive` 宽池反而亏损，说明“上一年单品种账本为正”是很弱的选品特征，甚至会追错趋势。
- 全非核心宽池的年度/产品贡献不是单一产品支撑，最大绝对产品贡献占比约 `10.2221%`，说明它确实较分散；问题是分散后收益材料性不足。
- 图表视觉复盘：账户主曲线几乎重合，但卫星仓图显示 Stage256 top6 的紫线明显强于三个宽池版本；宽池在 3/6个月 p05 横条上没有右移，成本压力图中 3x 仍全数越过 `-40%`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage557_breadth_low_single_risk_pool_audit_report_stage557_breadth_low_single_risk_pool_audit_v1.md`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage557_breadth_low_single_risk_pool_audit_decision_stage557_breadth_low_single_risk_pool_audit_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage557_breadth_low_single_risk_pool_audit_chart_stage557_breadth_low_single_risk_pool_audit_v1.png`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage557_breadth_low_single_risk_pool_audit_summary_stage557_breadth_low_single_risk_pool_audit_v1.csv`
- cost：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage557_breadth_low_single_risk_pool_audit_cost_stress_stage557_breadth_low_single_risk_pool_audit_v1.csv`
- rolling：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage557_breadth_low_single_risk_pool_audit_rolling_holding_stage557_breadth_low_single_risk_pool_audit_v1.csv`
- satellite daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage557_breadth_low_single_risk_pool_audit_satellite_daily_stage557_breadth_low_single_risk_pool_audit_v1.csv`
- product/family harvest：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage557_breadth_low_single_risk_pool_audit_satellite_product_harvest_stage557_breadth_low_single_risk_pool_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage557_breadth_low_single_risk_pool_audit_satellite_family_harvest_stage557_breadth_low_single_risk_pool_audit_v1.csv`

## 结论

- 本阶段结论：`breadth_low_single_risk_not_promotion`。
- 是否进入下一步：宽池/上一年为正宽池不进入下一验证；全非核心宽池只作为“分散但收益弱”的经验。
- 下一步：
  - 停止在宽池结构上继续扫 `risk/cap/corr/maxpos` 小数。
  - “选对品种”仍有价值，但不能靠上一年 PnL 或简单产品族/相关约束；下一步应转向 forward 外生状态账本、真实接收时间戳的库存/basis/会员/舆情状态，或新的强事前特征。
  - Stage526 仍是正常成本主候选；Stage256 top6 继续只作为 paper/经验，不晋级部署。

## 过拟合反思

- 运行前判断：不是过拟合。原因是本阶段只测三个预声明粗档，且使用交易前可知的产品族、上一年账本、20日相关性和风险预算。
- 运行后判断：不是过拟合。失败后没有删除亏损产品，也没有继续救 `0.18/0.22` 等小数。
- 原因：本阶段是结构性否定；结论是停止简单宽池救援，而不是为了得到更好收益继续调参。

## 继续价值反思

- 运行前判断：有价值。因为它直接检验用户提出的“低单笔风险、扩池、避免高相关、每年抓一部分趋势”的本质假设。
- 运行后判断：该子方向继续价值低，总目标继续价值高。
- 原因：全宽池证明分散可以降低单品依赖但收益材料性不足；上一年为正宽池证明简单历史赢家特征不可靠。真正值得继续的是更强的事前品种状态，而不是宽池参数本身。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：是。该阶段是对“低单笔风险扩池选品”方向的重要否定结论，应进入总账。
