# Stage002 Stage819候选分钟级A/C overlay

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：2026-06-14 15:42 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：候选内部 lot-level minute overlay A/C；冻结规则形状，不接正式版
- 是否重要突破：否。C2 是强线索，但还不是完整组合引擎结果，不能晋级正式候选。
- 是否触发A/B：否。已读取 `skills/version-ab-experiment/SKILL.md` 并判断本阶段只是 Stage819 候选内部 overlay，不做 Stage372/Stage78 正式 A/B/C，不写根目录 `back_log.md`。

## 外部调研与判断

- 参考资料：
  - GitHub / 公开资料中的 opening range breakout、固定止损止盈、失败退出、收盘前退出等日内规则样例。
  - 重点参考方向包括 ORB 的固定区间、固定风险、逐分钟触发，而不是复制任何外部参数。
- 我的判断：
  - Stage001 已经证明“早期失败不死扛”和“早期顺势确认”有结构性信号，Stage002 应该冻结规则做可执行语义，而不是继续扩大特征表。
  - 本阶段只验证 C1/C2 两个预声明形状，未扫 `30`、`0.5R`、`1R`、`2次重试` 等参数。
  - 同一根分钟K同时打到止损和确认时，按保守口径算止损先发生。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage826_stage819_intraday_ac_overlay.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `MODEL_TAG=stage826_stage819_intraday_ac_overlay_v1`
  - `FAILFAST_WINDOW_BARS=30`
  - `FAILFAST_STOP_R=0.5`
  - `FAILFAST_CONFIRM_R=0.5`
  - `FAILFAST_MAX_RETRIES=2`
  - `QUALITY_STOP_R=1.0`
  - `QUALITY_CONFIRM_R=1.0`
  - `MAX_CHANGED_ATLAS_PAGES=12`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：2018-01-01 至 2026-05-29
- 账户规模：30万，沿用 Stage819 候选配置
- 成本口径：沿用 Stage819 滑点，按每次执行 `slippage * size * volume` 扣除；A 的总滑点校验为 2,149,150
- 样本过滤：Stage819 closed lots 341 笔；分钟缺失 lot 保持原始退出，不用缺失数据制造收益
- 策略/归因口径：
  - A：原始 Stage819 closed lots，按日线逐日盯市复算，用于校验 overlay
  - C1：入场后 30 根1分钟K内，若先打到 0.5R 逆向且未先到 0.5R 顺向，实时止损；价格重新穿越原入场价最多重试 2 次
  - C2：入场日逐分钟比较 1R 逆向止损与 1R 顺向确认；若止损先发生则立即退出，确认先发生或都未发生则保持原始退出
  - 不修改 Stage372/20w 官方正式版，不连接 CTP，不调用下单 API

## 结果

- A 期末权益：26,322,730
- A 总收益：8,674.24%
- A 最大回撤：-54.75%
- A Sharpe：1.353（lot-level 统一口径重算；官方 summary Sharpe 为 1.436）
- A 总滑点：2,149,150
- A 总交易次数：666
- A 胜率：49.43%（非零日净收益胜率，lot-level 统一口径）
- C1 期末权益：29,217,632.7
- C1 总收益：9,639.21%
- C1 最大回撤：-52.94%
- C1 Sharpe：1.452
- C1 总滑点：2,349,070
- C1 总交易次数：724
- C1 胜率：49.36%
- C1 结论：净值 +2,894,902.7，回撤改善 1.82pp，但新增 58 次成交、滑点增加 199,920；重试分支拖累明显，只能作为次级线索。
- C2 期末权益：32,486,290.6
- C2 总收益：10,728.76%
- C2 最大回撤：-46.43%
- C2 Sharpe：1.502
- C2 总滑点：2,149,150
- C2 总交易次数：666
- C2 胜率：49.50%
- C2 结论：净值 +6,163,560.6，回撤改善 8.33pp，交易次数和滑点不增加，是当前最强线索，但还不能晋级。
- 新增回测结果：
  - A lot-level 复算：期末权益、最大回撤、滑点、交易次数与 Stage819 官方输出对齐。
  - C1 fail-fast/retry：53 笔出现止损，其中 22 笔止损后重试并回到原始退出；重试组净贡献 -1,742,961.3。
  - C2 first-1R stop：49 笔止损先于1R确认，净增 6,163,560.6。
- 修改回测结果：无
- 删除回测结果：无

## 分年表现

- C1：
  - 2020：-350,442.9
  - 2021：+1,447,214.7
  - 2022：-172,435.6
  - 2023：+163,276.5
  - 2024：+1,760.0
  - 2025：+1,733,030.0
  - 2026：+72,500.0
- C2：
  - 2020：-8,180.6
  - 2021：+1,417,810.4
  - 2022：+754,719.8
  - 2023：+961,115.0
  - 2024：+1,282,836.0
  - 2025：+1,224,860.0
  - 2026：+530,400.0
- 2018/2019：入场日分钟K覆盖为 0，本阶段保持原始退出，不产生变化。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage826_stage819_intraday_ac_overlay_report_stage826_stage819_intraday_ac_overlay_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage826_stage819_intraday_ac_overlay_summary_stage826_stage819_intraday_ac_overlay_v1.csv`
- curves：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage826_stage819_intraday_ac_overlay_curves_stage826_stage819_intraday_ac_overlay_v1.csv`
- lot_outcomes：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage826_stage819_intraday_ac_overlay_lot_outcomes_stage826_stage819_intraday_ac_overlay_v1.csv`
- events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage826_stage819_intraday_ac_overlay_events_stage826_stage819_intraday_ac_overlay_v1.csv`
- yearly_delta：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage826_stage819_intraday_ac_overlay_yearly_delta_stage826_stage819_intraday_ac_overlay_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage826_stage819_intraday_ac_overlay_decision_stage826_stage819_intraday_ac_overlay_v1.json`
- changed-lot atlas：12 页 PNG，`qmt_roll_stage826_stage819_intraday_ac_overlay_changed_atlas_page001...012_stage826_stage819_intraday_ac_overlay_v1.png`

## 结论

- 本阶段结论：
  - C2 `1R止损先于1R确认则退出` 是当前最强线索，表现为净值、回撤、Sharpe 同向改善，且不增加滑点和交易次数。
  - C1 `0.5R fail-fast + 最多2次重试` 有一定价值，但重试部分目前是负贡献，说明“可以多次尝试”必须非常克制；不能因为用户偏好重试就强行加重试。
  - C2 的本质不是预测，而是承认入场后如果很快进入 1R 级别逆向波动，原始趋势信号的日内执行质量已经变差，应立刻认错退出。
  - 这个结论符合第一性原则：趋势策略收益来自少数顺畅右尾，早期迅速逆向的仓位通常是在用账户承担错误入场的路径成本。
- 是否进入下一步：是
- 下一步：
  - Stage003 优先把 C2 写进完整组合引擎开关，真实重算后续信号、资金、保证金、仓位联动和交易成本。
  - C1 暂不作为主线推进；最多保留为对照，不继续扫重试次数或 0.5R 阈值。
  - Stage003 之前不讨论接入正式版，仍不得改 Stage372/20w。

## 过拟合反思

- 运行前判断：否。C1/C2 是 Stage001 预声明形状，本阶段没有新增扫参。
- 运行后判断：当前不算过拟合，但 C2 的收益改善很强，反而更要警惕它是否依赖分钟覆盖区间和既有 closed lot 选择。
- 原因：
  - C2 的规则只有一个结构：1R止损先于1R确认则退出，复杂度低。
  - 但本阶段不是完整组合引擎，未重算后续仓位和资金联动，因此证据强但仍不充分。
  - 如果下一步为了让 C1 或 C2 更好看而改 `0.8R/1.2R/45分钟/3次重试`，就是过拟合，应禁止。

## 继续价值反思

- 运行前判断：有。Stage001 给出的 R2/R3/R4 需要真实触发语义验证。
- 运行后判断：有，而且方向应收窄到 C2 完整引擎验证。
- 原因：
  - C2 在 2021-2026 大多数有分钟覆盖年份为正，只有 2020 轻微负贡献。
  - C2 不增加交易次数和滑点，工程上比 C1 简洁。
  - C1 的重试分支表现不好，说明“多次尝试”不是越多越好；当前更像风险治理，不像 alpha 增强。

## 合入建议

- 是否更新本线 `LINE.md`：是，更新为 Stage002 已完成、Stage003 待启动。
- 是否更新 `research/registry.md`：否。按并行研究记录纪律，暂不频繁改 registry。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段不是完整组合引擎候选、不是正式候选、不是跨线合并。
