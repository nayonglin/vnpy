# Stage765/766 2019 数据延展 readiness 与起点回测

- line_id：`futures_trend_2019_data_extension`
- 当前模式：`day`
- 记录时间：`2026-06-09 22:01 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：数据门禁 + 只读单臂回测
- 是否重要突破：否
- 是否触发A/B：否；本阶段不是新策略候选接入，只验证 2019 数据和启动路径。

## 外部调研与判断

- 参考资料：
  - vn.py 官方数据库文档：`https://www.vnpy.com/docs/cn/community/info/database.html`
  - Tushare 期货日线行情文档：`https://tushare.pro/document/2?doc_id=138`
- 我的判断：
  - 框架层没有阻塞，vn.py 支持按日线区间读取/写入历史 bar。
  - Tushare 期货日线字段包含 OHLC、成交量和持仓量，理论上足以重建早期合约日线/产品连续序列。
  - 真正约束不是 API，而是本地“主力映射、真实合约日线、执行开盘代理”三者覆盖是否一致。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage765_2019_data_extension_readiness.py`
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage766_2019_start_stage757_stage764.py`
- 修改脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage765_2019_data_extension_readiness.py`：修正实际 Stage757/Stage764 universe，纳入 `fu.SHFE`；把产品连续全覆盖和真实主力合约可回测分开。
- 删除脚本：无
- 新增参数：
  - Stage765：`ANALYSIS_START=2019-01-02`，`ANALYSIS_END=2019-12-31`，`PRELOAD_START=2018-06-01`
  - Stage766：`STARTS=2019-01,2020-01`，`ANALYSIS_END=2026-05-29`，2019 起点预热 `2018-01-01`
- 修改参数：无策略参数修改
- 删除参数：无

## 回测/归因参数

- 数据区间：
  - 数据门禁：`2019-01-02` 至 `2019-12-31`
  - 回测：`2019-01-01`/`2020-01-01` 独立起点至 `2026-05-29`
- 账户规模：
  - Stage757：`500,000`
  - Stage764：总资金 `500,000`，交易桶 `450,000`，备用金 `50,000`
- 成本口径：沿用既有 Stage757/Stage764 手续费/滑点与真实主力合约引擎口径。
- 样本过滤：
  - 2019 产品连续序列无全覆盖。
  - 当前真实主力合约引擎可覆盖 14 个 2019 可交易品种。
  - `SA.CZCE, SH.CZCE, lc.GFEX, lh.DCE, si.GFEX` 2019 排除/后上市/不可用。
- 策略/归因口径：
  - Stage757 C50 OI restore：`risk_multiplier=0.40`，无连败缩放/无 recovery sleeve，OI 确认恢复有效风险至 `0.80`。
  - Stage764：Stage757 信号不变，只增加 `45w/5w` 备用金桶。

## 数据门禁结果

- Stage765 决策：`2019_contract_backtest_ready_product_continuous_direct_not_ready`
- 当前实际 universe：`19` 个品种。
- 产品连续全覆盖可直接从 2019 起点跑：`0` 个。
- 当前主力合约引擎可跑：`14` 个。
- 需要外部 Tushare 合约补齐：`0` 个。
- 2019 排除/后上市/不可用：`5` 个。
- next-real-open proxy 覆盖：2019 相关 `0` 条；第一条 proxy signal date 为 `2020-01-06`。
- AI eligibility 覆盖：第一条 `2019-12-31`，在此之前策略代码默认不拦截，不使用未来 AI 评分。

## 回测结果

| 版本 | 起点 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 胜率 | 备用金 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Stage757 C50 OI restore | 2019-01 | `7,412,135` | `1382.43%` | `-44.79%` | `1.2510` | `754,880` | `706` | `52.38%` | 无 |
| Stage764 Stage757 + 45w/5w | 2019-01 | `8,793,115` | `1658.62%` | `-41.41%` | `1.3169` | `876,350` | `703` | `53.06%` | 用尽 `50,000` |
| Stage757 C50 OI restore | 2020-01 | `9,171,130` | `1734.23%` | `-41.65%` | `1.4222` | `901,820` | `691` | `52.52%` | 无 |
| Stage764 Stage757 + 45w/5w | 2020-01 | `8,554,870` | `1610.97%` | `-42.62%` | `1.3998` | `852,290` | `689` | `52.46%` | 用尽 `50,000` |

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage766_2019_start_stage757_stage764_report_stage766_2019_start_stage757_stage764_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage766_2019_start_stage757_stage764_summary_stage766_2019_start_stage757_stage764_v1.csv`
- curves：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage766_2019_start_stage757_stage764_curves_stage766_2019_start_stage757_stage764_v1.csv`
- source_counts：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage766_2019_start_stage757_stage764_source_counts_stage766_2019_start_stage757_stage764_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage766_2019_start_stage757_stage764_equity_curves_stage766_2019_start_stage757_stage764_v1.png`

## 结论

- 本阶段结论：
  - 可以从 2019 开始做“主力合约路径”的只读回测，但不能直接把产品连续路径改成 2019。
  - 2019 回测有执行代理 caveat：2019 年内开仓使用 `fallback_daily_next_open`，不是 2020 后的 Stage149 next-real-open 代理。
  - 备用金版本在 2019 起点胜出，但在 2020 起点弱于 Stage757；这说明备用金效果路径相关，不能因为 2019 一条起点表现好就推广。
- 是否进入下一步：是，但只能做数据/路径归因，不做调参。
- 下一步：
  - 归因 2019 起点相对 2020 起点的差异来自哪些 2019/2020 早期交易、哪些品种和备用金注入节点。
  - 若要把 2019 纳入正式稳健性矩阵，应补 2019 next-real-open 分钟代理或单独标注 daily fallback 口径。

## 过拟合反思

- 运行前判断：低过拟合风险。只改起点和预热，不改交易规则、风控参数、AI topN 或品种池。
- 运行后判断：低，但结果不能用于推广备用金参数。
- 原因：2019 起点提供路径压力样本，但执行代理口径不同，且备用金在 2019/2020 两个起点方向不一致。

## 继续价值反思

- 运行前判断：有价值。能回答“是否有 2019 数据、是否能跑”的基础问题。
- 运行后判断：有价值继续，但边界清楚。
- 原因：数据足够支持主力合约路径回测；下一步应做归因和执行代理补齐，而不是据此调策略参数。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：否，等待合入者统一维护。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段是数据延展门禁和只读验证，不是正式候选、重要突破或策略合入。
