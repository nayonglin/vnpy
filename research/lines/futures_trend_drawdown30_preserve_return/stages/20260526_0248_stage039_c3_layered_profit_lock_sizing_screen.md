# Stage039 C3账户级分层锁盈sizing筛查

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：day
- 记录时间：2026-05-26 02:48 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：真实引擎全样本可行性筛查
- 是否重要突破：否
- 是否触发A/B：否。没有候选同时满足最大回撤30以内和C3收益保留80%。

## 外部调研与判断

- 参考资料：
  - Moskowitz/Ooi/Pedersen, Time Series Momentum。
  - Hurst/Ooi/Pedersen, A Century of Evidence on Trend-Following Investing。
- 我的判断：
  - 趋势策略常见的回撤治理是波动目标、账户层去杠杆、利润留白和多策略分散；但 Stage034/035 已反证当前波动预算真实引擎形状，Stage036 已反证静态现金留白，Stage037 已排除同源趋势组合。
  - 分层锁盈属于账户层部署机制，经济含义是“先让策略赚到高水位，再减少后续可复利权益”，不是针对2021单窗口写补丁，值得做一次粗档位筛查。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage339_c3_layered_profit_lock_sizing_screen.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `enable_layered_profit_lock_sizing=True`
  - `layered_profit_lock_base_equity=500000`
  - `layered_profit_lock_start_equity=1000000/2000000`
  - `layered_profit_lock_ratio=0.25/0.50`
  - `layered_profit_lock_tiers="2000000:0.50,5000000:0.65"`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：2020-01-02 至 2026-04-30
- 账户规模：500,000
- 成本口径：沿用 C3 真实引擎口径，滑点纳入统计，佣金为0
- 样本过滤：全样本筛查；若全样本不达标，不进入多周期和滑点压力
- 策略/归因口径：固定 `C3_supply_headwind`，只改变账户级 sizing 权益上限，不改核心 alpha、AI池、品种池、供需过滤和出场逻辑

## 结果

| variant | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 收益保留vs C3 | strict_pass |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `A_c3_supply_headwind` | `6085.1300%` | `-31.0767%` | `1.3663` | `1,556,750` | `757` | `100.0000%` | `0` |
| `C_lock_1m25` | `2913.1920%` | `-29.1036%` | `1.2542` | `853,850` | `749` | `47.8739%` | `0` |
| `C_lock_1m50` | `1126.8770%` | `-30.1024%` | `1.0529` | `447,100` | `733` | `18.5185%` | `0` |
| `C_lock_2m50` | `2340.2510%` | `-31.0767%` | `1.1816` | `1,034,810` | `751` | `38.4585%` | `0` |
| `C_lock_tier_1m25_2m50_5m65` | `1605.9050%` | `-29.1036%` | `1.1529` | `577,240` | `743` | `26.3906%` | `0` |

- 期末权益：
  - 最好收益仍是 C3：`30,925,650`
  - 最接近回撤目标的 `C_lock_1m25`：`15,065,960`
- 总收益：
  - C3：`6085.1300%`
  - `C_lock_1m25`：`2913.1920%`
- 最大回撤：
  - C3：`-31.0767%`
  - `C_lock_1m25`：`-29.1036%`
- Sharpe：
  - C3：`1.3663`
  - `C_lock_1m25`：`1.2542`
- 总滑点：
  - C3：`1,556,750`
  - `C_lock_1m25`：`853,850`
- 总交易次数：
  - C3：`757`
  - `C_lock_1m25`：`749`
- 胜率：本脚本未单独导出胜率列，沿用后续 summary 可补查
- 其他关键指标：
  - `C_lock_1m25` 可以压到30以内，但收益保留只有 `47.8739%`，未达 `80%` 闸门。
  - `C_lock_2m50` 触发更晚，收益也没有保住，且最大回撤仍为 `-31.0767%`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage339_c3_layered_profit_lock_sizing_screen_report_stage339_c3_layered_profit_lock_sizing_screen_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage339_c3_layered_profit_lock_sizing_screen_summary_stage339_c3_layered_profit_lock_sizing_screen_v1.csv`
- orders：无
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage339_c3_layered_profit_lock_sizing_screen_daily_stage339_c3_layered_profit_lock_sizing_screen_v1.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage339_c3_layered_profit_lock_sizing_screen_comparison_stage339_c3_layered_profit_lock_sizing_screen_v1.csv`

## 结论

- 本阶段结论：
  - 分层锁盈能降低后期复利暴露，说明账户级利润留白机制确实在起作用。
  - 但它把收益压得太重，没有候选同时满足“最大回撤30以内 + C3收益保留80%”。
  - 当前形状不进入多周期和滑点压力，不作为正式候选。
- 是否进入下一步：否，本形状停止。
- 下一步：
  - 不继续把100万改成98万、25%改成23%这类细调。
  - 继续方向应回到真正低相关收益源、分账户部署，或重新评估单策略 C3 自然回撤约 `-31%` 是否已接近该趋势策略的稳定边界。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：仍不是过拟合，但若继续细调就会开始过拟合。
- 原因：
  - 候选来自账户层粗档位利润留白，不使用单品种黑名单、日期补丁或单窗口亏损反推。
  - 全样本失败后直接停止，而不是通过小数参数救结果。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：本形状继续价值低，但结论有价值。
- 原因：
  - 它证明“压回撤”本身不难，难点是“压回撤同时保留复利收益”。
  - 这进一步支持当前研究判断：单策略内部账户层压缩很容易牺牲复利，剩余方向要么找真正低相关收益源，要么接受 C3 的自然回撤边界。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：是
- 是否追加根目录 `memory.md/back_log.md`：否。不是正式候选、重要突破或跨线合并。
