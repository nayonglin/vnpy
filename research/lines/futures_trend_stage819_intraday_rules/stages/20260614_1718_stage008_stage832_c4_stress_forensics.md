# Stage008 Stage832 C4 broker100/DD50压力归因

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：2026-06-14 17:18 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读归因；不改策略、不调参数、不连接 CTP、不调用下单。
- 是否重要突破：否，但属于 C4 是否继续研究前的关键风险拆解。
- 是否触发A/B：否。Stage832 只复跑和归因 Stage831 已失败的 C4 年度起点，不构成正式候选 A/B。

## 外部调研与判断

- 参考资料：
  - RePEc/Umea Economic Studies：`Assessing the profitability of intraday opening range breakout strategies`，机械 ORB 规则可以有统计检验价值，但必须处理假突破和执行风险。
  - NinjaTrader futures risk management：期货风险管理需要同时约束 margin、leverage、stop-loss 和 position sizing，止损应绑定交易假设失效点。
  - Optimus Futures position sizing：多持仓时必须把组合暴露、相关性和可用保证金一起看，不能只按单笔止损计算手数。
  - Investopedia range breakout risk：突破类规则常见问题是假突破、回抽和大行情稀缺；更稳的做法是等待确认或趋势展开后再进入。
- 我的判断：
  - C4 的入口保证金闸门是必要但不充分的生存线。期货账户逐日盯市，风险可以在入场后由价格路径、权益分母和集中持仓重新生成。
  - 下一步如果继续，只能做 full-path holding margin survival 或释放资金再使用纪律；不能继续扫 `1R`、broker 阈值、冷却天数、品种过滤或年份过滤。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage832_stage831_c4_stress_forensics.py`
- 修改脚本：无策略脚本修改；Stage832 脚本运行中修正了缓存复用、时区日期转换和 K 线绘图函数调用。
- 删除脚本：无。
- 新增参数：无交易参数。归因参数为压力起点 `2018-01, 2019-01, 2020-01, 2021-01`。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：各起点独立跑到 `2026-05-29`。
- 账户规模：Stage819 候选口径 `300,000`。
- 成本口径：沿用 Stage819/Stage830 回测成本；本阶段不做成本压力新增。
- 样本过滤：只选 Stage831 中 C4 出现 `broker10>100%` 或 `DD50` 压力的年度起点。
- 策略/归因口径：
  - A：Stage819 baseline，即 `stage827_stage819_baseline`。
  - C4：Stage830 `C2 + broker10 100% entry cap`，即 `stage830_stage819_c2_broker10_100_cap`。
  - 归因维度：压力日、锚点日、产品保证金贡献、入口 cap 触发前后投影、日线 K 图谱、日内止损事件图谱。

## 结果

- 期末权益：
  - `2018-01` A `26,322,730`，C4 `30,523,910.8`。
  - `2019-01` A `22,792,425`，C4 `35,491,021.8`。
  - `2020-01` A `18,787,535`，C4 `25,947,231.6`。
  - `2021-01` A `5,779,775`，C4 `13,705,900`。
- 总收益：
  - `2018-01` A `8674.2433%`，C4 `10074.6369%`。
  - `2019-01` A `7497.4750%`，C4 `11730.3406%`。
  - `2020-01` A `6162.5117%`，C4 `8549.0772%`。
  - `2021-01` A `1826.5917%`，C4 `4468.6333%`。
- 最大回撤：
  - `2018-01` A `-54.7546%`，C4 `-50.7900%`。
  - `2019-01` A `-43.4335%`，C4 `-50.7898%`。
  - `2020-01` A `-44.6223%`，C4 `-50.8993%`。
  - `2021-01` A `-42.8163%`，C4 `-49.4595%`。
- Sharpe：
  - `2018-01` A `1.4363`，C4 `1.4519`。
  - `2019-01` A `1.5297`，C4 `1.5931`。
  - `2020-01` A `1.5942`，C4 `1.6220`。
  - `2021-01` A `1.3961`，C4 `1.6024`。
- 总滑点：
  - `2018-01` A `2,149,150`，C4 `2,079,430`。
  - `2019-01` A `1,793,410`，C4 `2,348,680`。
  - `2020-01` A `1,489,460`，C4 `1,779,890`。
  - `2021-01` A `493,780`，C4 `954,740`。
- 总交易次数：
  - `2018-01` A `666`，C4 `677`。
  - `2019-01` A `621`，C4 `625`。
  - `2020-01` A `529`，C4 `534`。
  - `2021-01` A `387`，C4 `395`。
- 胜率：
  - `2018-01` A `53.1069%`，C4 `53.6294%`。
  - `2019-01` A `54.2778%`，C4 `53.9027%`。
  - `2020-01` A `54.7544%`，C4 `54.4397%`。
  - `2021-01` A `53.5475%`，C4 `54.0984%`。
- 其他关键指标：
  - C4 压力起点：`2018-01, 2019-01, 2020-01, 2021-01`。
  - C4 broker100 天数：`2018-01=2`、`2019-01=3`、`2020-01=2`、`2021-01=2`。
  - C4 DD50 天数：`2018-01=13`、`2019-01=13`、`2020-01=13`、`2021-01=0`。
  - C4 max broker10：`115.4012%`、`104.9794%`、`114.4678%`、`108.1240%`。
  - C4 最差 DD：`-50.7900%`、`-50.7898%`、`-50.8993%`、`-49.4595%`。
  - 入口 cap 触发前投影最高 `1.2375 -> 1.2713`，触发后均压到约 `1.0`，说明入口 cap 本身按设计生效。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage832_stage831_c4_stress_forensics_report_stage832_stage831_c4_stress_forensics_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage832_stage831_c4_stress_forensics_summary_stage832_stage831_c4_stress_forensics_v1.csv`
- curves：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage832_stage831_c4_stress_forensics_curves_stage832_stage831_c4_stress_forensics_v1.csv`
- positions：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage832_stage831_c4_stress_forensics_positions_stage832_stage831_c4_stress_forensics_v1.csv`
- contract_margin：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage832_stage831_c4_stress_forensics_contract_margin_stage832_stage831_c4_stress_forensics_v1.csv`
- product_margin：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage832_stage831_c4_stress_forensics_product_margin_stage832_stage831_c4_stress_forensics_v1.csv`
- trade_events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage832_stage831_c4_stress_forensics_trade_events_stage832_stage831_c4_stress_forensics_v1.csv`
- intraday_events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage832_stage831_c4_stress_forensics_intraday_events_stage832_stage831_c4_stress_forensics_v1.csv`
- stress_days：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage832_stage831_c4_stress_forensics_stress_days_stage832_stage831_c4_stress_forensics_v1.csv`
- stress_anchors：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage832_stage831_c4_stress_forensics_stress_anchors_stage832_stage831_c4_stress_forensics_v1.csv`
- top_margin_products：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage832_stage831_c4_stress_forensics_top_margin_products_stage832_stage831_c4_stress_forensics_v1.csv`
- cap_event_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage832_stage831_c4_stress_forensics_cap_event_summary_stage832_stage831_c4_stress_forensics_v1.csv`
- charts：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage832_stage831_c4_stress_forensics_stress_path_chart_stage832_stage831_c4_stress_forensics_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage832_stage831_c4_stress_forensics_anchor_margin_chart_stage832_stage831_c4_stress_forensics_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage832_stage831_c4_stress_forensics_stress_kline_atlas_stage832_stage831_c4_stress_forensics_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage832_stage831_c4_stress_forensics_intraday_event_atlas_stage832_stage831_c4_stress_forensics_v1.png`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage832_stage831_c4_stress_forensics_decision_stage832_stage831_c4_stress_forensics_v1.json`

## 结论

- 本阶段结论：
  - C4 不晋级。它在四个压力起点收益和 Sharpe 都更强，但 `2019/2020` DD50、四个起点 broker100 暴露说明尾部路径不可接受。
  - C4 失败不是入口 cap 没工作。入口 cap 已把开仓投影压到约 `100%` 内，压力在持仓后产生。
  - DD50 与 broker100 是两个机制：
    - `2022-06` DD50 很多日期 C4 已空仓或低保证金，主要是此前高峰后的权益路径回撤，`2019-01` 甚至出现 C4 绝对权益高于 A 但相对自身高水位 DD 更深。
    - `2022-07-07` broker100 来自黑色/燃油短仓集群；不同起点上有的由权益分母塌缩主导，有的由 C4 更大持仓保证金分子主导。
  - 不能按 `hc/jm/rb/fu` 或 `2022` 做黑名单，因为这些也是趋势右尾的重要来源。
- 是否进入下一步：进入，但只允许结构性 full-path 生存线或释放资金再使用纪律。
- 下一步：
  - Stage009 优先验证一个冻结、低自由度的 full-path holding margin survival 规则：每日盯市后若 broker10 实际保证金/权益超过 `100%`，按产品保证金贡献从大到小减仓到 `100%` 内；这是生存约束，不是收益优化阈值。
  - 暂不做 `95/98/100` 阈值扫描，不做产品/方向/年份过滤，不调整 C2 的 `1R` 语义。

## 过拟合反思

- 运行前判断：否。Stage832 是对 Stage831 已失败压力样本的归因，不新增规则、不调参。
- 运行后判断：归因本身不过拟合；但若把 `2022-07-07` 的产品簇直接写成黑名单，或把 broker cap 从 `100` 改成一串小数扫描，就是过拟合。
- 原因：压力来自通用的期货账户路径问题，即持仓后盯市、权益分母和组合保证金暴露，不是单一品种或单一年份事故。

## 继续价值反思

- 运行前判断：有价值。Stage831 已证明 C4 收益强但尾部不合格，必须知道压力来自哪里。
- 运行后判断：仍有价值，但方向收窄。
- 原因：C4 的日内止损确实释放了收益潜力，问题不是日内止损无效，而是释放资金后缺少持仓全过程生存线。继续价值在账户路径治理，不在继续雕刻日内 `1R` 规则。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage008 结论和 Stage009 边界。
- 是否更新 `research/registry.md`：否。本阶段不是正式候选、重要突破或跨线合并。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段为研究线内部归因，未形成正式候选或重大突破。
