# Stage028 C3单品种路径亏损归因

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-05-25 23:28 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读归因；不修改 C3，不新增交易规则
- 是否重要突破：否，但明确下一步研究焦点
- 是否触发A/B：否；本阶段没有形成可接入正式版本的新候选

## 外部调研与判断

- 参考资料：
  - Moskowitz/Ooi/Pedersen 的 time-series momentum 研究强调期货趋势跟踪和波动率缩放框架。
  - Hurst/Ooi/Pedersen 的 trend-following 长周期研究说明趋势因子应优先追求跨市场、跨时期稳定性。
  - MAE/MFE 路径归因常用于判断入场后价格路径质量，而不是只看最终平仓盈亏。
- 我的判断：
  - Stage027 已经反证“保证金过高/持仓太多”不是 C3 剩余最大回撤的主因。
  - 本阶段应把视角下沉到单笔开仓后的路径质量：早期 MAE、MFE、趋势延伸、回撤窗口内的日度浮亏。
  - 不能把一个历史差桶直接变成过滤器；下一阶段必须先冻结低自由度规则，再做多周期和滑点压力。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage328_c3_single_path_loss_attribution.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无交易参数；新增只读归因字段 `mae_pct`、`mfe_pct`、`extension_60_atr`、`pullback_20_atr`、`dir_return_60d_pct`、`vol20_annual_pct` 等
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：`2020-01-02` 到 `2026-04-30`
- 账户规模：`500,000`
- 成本口径：C3 原有滑点口径；总滑点复现为 `1,556,750`
- 样本过滤：C3 全部平仓回合；分桶表默认关注样本数较充足的桶，避免 1-2 笔孤立样本直接决策
- 策略/归因口径：`C3_supply_headwind`，只读复盘开仓后路径，不改 alpha、不改 AI 池、不改风控参数

## 结果

- 期末权益：`30,925,650`
- 总收益：`6085.1300%`
- 最大回撤：`-31.0767%`
- Sharpe：`1.3663`
- 总滑点：`1,556,750`
- 总交易次数：`757`
- 胜率：`45.3826%`
- 其他关键指标：
  - 平仓回合数：`379`
  - 最大回撤窗口：峰值 `2021-05-12`，谷底 `2021-07-02`
  - 最大回撤窗口主要亏损品种：`hc.SHFE -151,140`、`FG.CZCE -107,020`、`SM.CZCE -94,330`、`rb.SHFE -74,340`、`SA.CZCE -67,380`、`jm.DCE -56,730`
  - 绝对盈亏最差桶：`hold_0_5d`，样本 `158`，总盈亏 `-12,099,715`，胜率 `19.6203%`，中位 MAE `-2.2100%`，中位 MFE `1.0929%`
  - 归一化收益最差的充足样本桶：
    - `mae_minus10_minus5`：样本 `25`，中位收益 `-3.8539%`
    - `long_base_stop`：样本 `27`，中位收益 `-2.0183%`
    - `mae_minus5_minus2`：样本 `148`，中位收益 `-1.5633%`
    - `hold_0_5d`：样本 `158`，中位收益 `-1.3476%`
    - `entry_month=5`：样本 `20`，中位收益 `-1.2774%`
  - 最大回撤窗口并非只有平仓亏损；部分长持仓最终盈利，但窗口内浮亏压低权益，说明只看 exit_reason 不够。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage328_c3_single_path_loss_attribution_report_stage328_c3_single_path_loss_attribution_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage328_c3_single_path_loss_attribution_bucket_summary_stage328_c3_single_path_loss_attribution_v1.csv`
- orders：无
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage328_c3_single_path_loss_attribution_dd_day_summary_stage328_c3_single_path_loss_attribution_v1.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage328_c3_single_path_loss_attribution_round_trips_stage328_c3_single_path_loss_attribution_v1.csv`

## 结论

- 本阶段结论：
  - 决策标签：`diagnostic_only_no_promotion`。
  - C3 剩余最大回撤更像是单品种趋势路径在开仓后短期快速反向波动造成的权益冲击，而不是保证金/持仓广度问题。
  - 最有价值的下一步不是品种黑名单，也不是继续调保证金阈值，而是检验低自由度“入场后早期不利波动/趋势过度延伸/基础止损状态”的覆盖层。
- 是否进入下一步：进入下一步，但仅进入冻结规则验证，不直接合入。
- 下一步：
  - 预注册 1-2 个低自由度候选，例如“高 MAE 风险状态下新仓降风险/更严格早期退出”或“过度延伸且近端无回撤时降低新仓风险”。
  - 必须做 C3 对照、全周期、起始年份、弱窗口、滑点压力；若只修复 2021 或 2026 个别路径，则废弃。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只复现冻结 C3 并做路径归因，没有新增交易规则或调参；但不能把最差桶直接升级为过滤器，否则会过拟合。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：它把研究从泛泛的账户层风控推进到具体可检验的单路径状态变量，能帮助下一阶段少走“调小数阈值”的路。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage028 只读归因结论。
- 是否更新 `research/registry.md`：是，更新当前状态和下一步。
- 是否追加根目录 `memory.md/back_log.md`：是，作为本研究线重要阶段摘要追加。
