# Stage196 第78 2015-2019 Tushare早期合约数据修复与复跑

- line_id：`futures_trend`
- 当前模式：`day`
- 记录时间：2026-05-10 01:27
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：数据修复 + 第78固定版本复跑
- 是否重要突破：是；2015起点请求窗口从不可用修复到覆盖率 `98.1151% PASS`
- 是否触发A/B：否，本轮只补数据并复验第78正式基准，不产生新策略分支

## 外部调研与判断

- 参考资料：
  - TqSdk DataDownloader 文档：确认可批量下载期货历史K线，但本轮直接拉老合约在当前环境里超时或返回不存在。
  - AkShare 新浪期货接口：本地验证连续合约如 `RB0` 可追溯到较早年份，但大量2015老的真实交割合约如 `RB1505`、`JM1505`、`FU1604` 返回空或异常。
  - RQData / vn.py RQData：本地安装存在，但没有 `rqdatac` 账号配置，不能作为本轮修复来源。
  - Tushare `fut_daily`：本地已有 token，可成功拉取 `RB1505.SHF`、`JM1505.DCE`、`FU1604.SHF`、`MA1506.ZCE` 等老合约日线。
- 我的判断：
  - 2015-2020覆盖差不是第78策略逻辑问题，而是早期真实主力合约K线缺失与郑商所三位合约代码年代歧义。
  - 本轮适合用 Tushare 按 Stage78 主力映射缺口做定向修复，而不是重跑现有 TqSdk 下载脚本。
  - 修复动作不能根据收益选择品种或窗口，只能根据映射缺失清单补数据；这样才不把数据修复变成隐性过拟合。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/repair_qmt_roll_stage196_stage78_2015_tushare_data.py`
- 修改脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage194_stage78_2015_multicycle_viability.py`
  - 调整报告决策标签：当2015总窗口通过但2015-2017早期子段未过门槛时，标记为 `yellow_long_sample_supported_early_segment_gap`。
- 删除脚本：无
- 新增参数：
  - 修复窗口：`2015-01-05` 至 `2019-12-31`
  - 数据源：Tushare `fut_daily`
  - 覆盖门槛：沿用 `95%`
  - 郑商所三位合约按映射日期推断完整年份，例如 `MA506.CZCE` 在2015窗口映射到 `MA1506.ZCE`
- 修改参数：无第78策略参数修改
- 删除参数：无

## 回测/归因参数

- 数据区间：
  - 数据修复：2015-01-05 至 2019-12-31
  - 复跑审计：2015-01-05 至 2026-04-30
- 账户规模：`200,000`
- 成本口径：沿用 Stage78 当前元数据滑点口径；本轮 `total_commission=0`
- 样本过滤：覆盖率低于 `95%` 的窗口不作为可信收益结论
- 策略/归因口径：`official_stage78_defensive_v1`，固定第78正式配置

## 结果

- 数据修复结果：
  - 修复前缺失合约：`223`
  - 修复前缺失映射日：`14,514`
  - 下载/导入状态：`imported=230`，`empty=1`
  - Tushare拉取后覆盖缺失日：`14,368`
  - 唯一空返回样例：`fu1805.SHFE / FU1805.SHF`
- 2015起点请求窗口：
  - 覆盖率：`98.1151% PASS`
  - 期末权益：`4,412,810`
  - 总收益：`2,106.4050%`
  - 最大回撤：`-36.1290%`
  - Sharpe：`0.9581`
  - 总滑点：`255,590`
  - 总交易次数：`785`
  - 胜率：`41.5190%`
- 2015-2017早期数据段：
  - 覆盖率：`94.5927% FAIL`
  - 结论：仍不能单独作为早期周期可信收益结论，主要残留在 `fu.SHFE` 与少量 `SM.CZCE`
- 2018-2019过渡段：
  - 覆盖率：`98.0505% PASS`
  - 期末权益：`190,420`
  - 总收益：`-4.7900%`
  - 最大回撤：`-9.3439%`
  - Sharpe：`-0.4241`
  - 总滑点：`1,440`
  - 总交易次数：`16`
  - 胜率：`28.5714%`
- 2020-2026正式可信主样本：
  - 期末权益：`4,637,530`
  - 总收益：`2,218.7650%`
  - 最大回撤：`-36.9907%`
  - Sharpe：`1.2922`
  - 总滑点：`261,740`
  - 总交易次数：`782`
  - 胜率：`42.1053%`
- 滑点压力：
  - 3x滑点：期末权益 `4,114,050`，总收益 `1,957.0250%`，最大回撤 `-40.2491%`，Sharpe `1.3191`
  - 5x滑点：期末权益 `3,590,570`，总收益 `1,695.2850%`，最大回撤 `-44.5009%`，Sharpe `1.1888`
- 年度收益：
  - 2020至2026均为正：`122.1325% / 211.7295% / 19.1605% / 47.1962% / 19.8189% / 57.0800% / 1.4358%`
- 历史旧第78参考字段：
  - 期末权益 `1,610,900`
  - 总收益 `705.45%`
  - 最大回撤 `-54.93%`
  - Sharpe `0.661`
  - 总滑点 `100`
  - 总交易次数 `1000`
  - 本轮不是复跑旧口径，而是当前正式Stage78口径的2015数据修复复验。

## 输出文件

- repair report：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage196_stage78_2015_2019_tushare_data_repair_report_stage196_stage78_2015_2019_tushare_data_repair_v1.md`
- repair status：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage196_stage78_2015_2019_tushare_data_repair_repair_status_stage196_stage78_2015_2019_tushare_data_repair_v1.csv`
- repair missing contracts：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage196_stage78_2015_2019_tushare_data_repair_missing_contracts_stage196_stage78_2015_2019_tushare_data_repair_v1.csv`
- raw data：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/downloaded_futures/tushare_stage196_stage78_2015_2019`
- Stage194 report：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage194_stage78_2015_multicycle_viability_report_stage194_stage78_2015_multicycle_viability_v1.md`
- Stage194 summary：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage194_stage78_2015_multicycle_viability_summary_stage194_stage78_2015_multicycle_viability_v1.csv`
- Stage194 equity HTML：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage194_stage78_2015_multicycle_viability_equity_curves_stage194_stage78_2015_multicycle_viability_v1.html`

## 结论

- 本阶段结论：
  - “为什么15年到20年覆盖差”：根因确认是本地早期真实合约日线缺失，不是策略逻辑问题。
  - “是否要重新下载处理”：是；本轮已经用 Tushare 定向补齐到足以让2015总窗口通过的程度。
  - 第78不是因为这次补数据而变成无条件绿灯。更准确是黄绿之间：长样本总窗口通过，2020后主样本强，但2015-2017子段仍有残留数据缺口，且若按用户40%回撤边界，3x滑点和部分冷启动窗口会触碰边界。
- 是否进入下一步：可以。
- 下一步：
  - 继续追补早期 `fu.SHFE` 残留空洞，尤其 `fu1805.SHFE`。
  - 做 T+1 开盘/收盘/VWAP 成交审计。
  - 把30万资金、40%最大实盘回撤约束纳入影子盘风控，不用当前200,000研究本金直接外推。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否，但有数据外推风险。
- 原因：
  - 本轮按缺失映射清单补数据，没有调第78参数，也没有根据收益决定补哪些合约。
  - 风险在于不能因为2015总窗口通过，就忽略2015-2017子段仍低于覆盖门槛；这一点已在报告标签中修正为黄灯。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：
  - 它把“2015起点不能跑”推进成“2015总窗口可参考、早期子段有残缺提示”的更清晰状态。
  - 继续价值已经从数据可行性转向执行可行性：T+1成交、真实成本、影子盘对账和风控硬闸门。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新，等待T+1执行审计后统一整理。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：是，追加本次数据修复和复跑摘要。
