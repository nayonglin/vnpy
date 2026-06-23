# Stage108 C9 15w 2026-06-22 收盘后无交易信号逐品种复核

- line_id：futures_trend_stage819_intraday_rules
- 当前模式：day
- 记录时间：2026-06-22 16:51 CST
- 工作区/分支：/Users/bytedance/Desktop/person/vnpy / master
- 阶段性质：官方 C9/15w 实盘影子盘收盘后只读复核；解释 16:35/16:37 邮件无今晚和明早交易信息的原因。
- 是否重要突破：否；但发现一个需要后续决策的品种池口径差异。
- 是否触发A/B：否；本阶段只读归因，不推广新版本、不接正式策略。

## 外部调研与判断

- 参考资料：
  - https://www.grahamcapital.com/blog/trend-following-primer/
  - https://github.com/amstrdm/mlm-trend-following
- 我的判断：外部资料只确认趋势跟随通常围绕均线、突破、动量确认和风险控制展开；没有资料能替代当前仓库已冻结的 C9 官方执行逻辑。本次判断必须以仓库里的 Stage847/Stage901/C9 profile、AI 品种池和今日收盘数据为准。

## 本次变更

- 新增脚本：无。
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：无。
- 修改参数：无。
- 删除参数：无。
- 新增记录：本 stage 记录。
- 只读对照：在内存中临时把 C9 profile 的 `ai_product_pool_eligibility_path` 覆盖为 `OFFICIAL_LIVE_AI_ELIGIBILITY_PATH`，仅用于归因，不落盘、不生成报单。

## 回测/归因参数

- 数据区间：Stage901 shadow `2026-06-16` 至 `2026-06-22`；目标日 `2026-06-22`。
- 账户规模：官方 live 口径 `150000`。
- 成本口径：沿用 Stage847/C9 官方 profile；本阶段不重新评估成本压力。
- 样本过滤：当前正式 C9 实际加载的 AI 品种池。
- 策略/归因口径：Stage847-C9-15w，Stage819 基础，C4 + 0.5R stop retry once；日线 MA5/10/20/40 + MACD hist；短开新仓最终只允许 `short_case1a`，并经过 AM41、wick chop、ma5/slope 等入口过滤。

## 数据与邮件核查

- Stage173 数据更新报告生成于 `2026-06-22 16:35:50`，`product_count=19`、`contract_count=19`、`saved_count=19`、`failed_count=0`、`empty_count=0`、`max_saved_date=2026-06-22`。今日收盘数据本身没有失败。
- 最新 timed cycle 报告生成于 `2026-06-22 16:37:10`，阶段 `post-close`，目标日 `2026-06-22`。
- Stage901：`target_signal_count=0`、`pending_order_count=0`、当前持仓 `0`。
- Stage905：`executor_no_intents`，ready `0`，blocked `0`。
- Stage260：可执行 `0`，blocked `0`，skipped_flat `0`。
- 报单 API 调用数 `0`。邮件提示“今晚和明早没有交易信息”与当前正式 C9 实际口径一致。

## 当前正式品种池

实际 C9 profile 当前加载：

`examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_ai_top8_plus_fu_satellite_post_signal_eligibility.csv`

最新 `eval_date=2026-02-27`，池内品种为：`ru.SHFE`、`SH.CZCE`、`si.GFEX`、`AP.CZCE`、`lh.DCE`、`OI.CZCE`、`MA.CZCE`、`SA.CZCE`、`fu.SHFE`。

逐品种基于 `2026-06-22` 收盘价的未触发原因：

| 品种 | 当前主力 | 今日收盘 | 归因 |
| --- | --- | ---: | --- |
| ru.SHFE | ru2609.SHFE | 17845.00 | MA5/10/20/40 没有形成完整多头或空头排列；今天没有新的均线/MACD 触发。MACD hist 为负只支持空头方向，但空头均线结构不成立。 |
| SH.CZCE | SH609.CZCE | 1976.00 | 当前合约仅 3 根日线，不足 AM41 预热要求，官方策略不能生成入场信号。 |
| si.GFEX | si2609.GFEX | 8540.00 | 日线已偏空，且 10 下穿 20，原始结构接近 `short_case2`；但被 wick chop filter 阻断，并且正式短开白名单只允许 `short_case1a`，`short_case2` 不可交易。 |
| AP.CZCE | AP610.CZCE | 7505.00 | 没有完整多头/空头均线排列；今天没有新的均线/MACD 触发。MACD hist 为正只支持多头方向，但多头结构不成立。 |
| lh.DCE | lh2609.DCE | 11760.00 | 当前合约 26 根日线，不足 AM41 预热要求，官方策略不能生成入场信号。 |
| OI.CZCE | OI609.CZCE | 9669.00 | MACD hist 为负，但 MA40 仍低于 MA20，完整空头排列不成立；今天也没有新的触发交叉。 |
| MA.CZCE | MA609.CZCE | 2528.00 | 已是偏空延续且向下突破，但 6 月 22 日没有新的入场触发。6 月 18 日曾出现 `short_case2` 候选，因短开白名单只允许 `short_case1a` 被拒。 |
| SA.CZCE | SA609.CZCE | 1128.00 | 空头趋势延续，但今天没有新的 5/10、10/20、20/40 或 MACD 死叉触发；趋势已经在路上，C9 不追旧信号。 |
| fu.SHFE | fu2609.SHFE | 3101.00 | 当前合约 33 根日线，不足 AM41 预热要求，官方策略不能生成入场信号。 |

## 今日候选与池外信号

- 正式 Stage901 今日候选中有 `hc.SHFE`、`lc.GFEX`、`rb.SHFE` 的 `short_case1a`，但三者都不在当前正式 AI 池内，因此被 `ai_product_pool_blocked`。
- `rb.SHFE/rb2610.SHFE` 今日收盘 `3127.00`，在日线结构上满足 `short_case1a`，正式池外阻断是它没有进入当前实际加载的 `2026-02-27` AI 池。
- 配置文件另有 `OFFICIAL_LIVE_AI_ELIGIBILITY_PATH` 指向 Stage182 `2026-05-29` 池，池内包含 `rb.SHFE`。我做了只读内存对照：如果 C9 临时切到 Stage182 池，今日会出现 `rb2610.SHFE Short Open volume=11 price=3126.0` 的 pending order。
- 这不是今晚可直接下单的结论；它说明当前 live config 中存在“声明的 live AI eligibility path”与“实际 C9 profile overrides 加载路径”不一致的风险，需要单独决策和复核。

## 工具与异常

- 已尝试运行 futures-official-shadow skill 自带 `export_official_shadow_events.py` 导出事件，但该脚本仍按旧 `stage847_c9_30w_stage819_05r_stop_retry` profile 查找，和当前 C9/15w live profile 不匹配而失败。
- 因此本次以 Stage901 官方输出、entry candidates、pending orders、trade diagnostics 与只读 profile 对照为准。

## 结果

- 期末权益：本阶段不重新回测，N/A。
- 总收益：N/A。
- 最大回撤：N/A。
- Sharpe：N/A。
- 总滑点：N/A。
- 总交易次数：正式今日可执行交易 `0`。
- 胜率：N/A。
- 其他关键指标：正式口径 signal `0`、pending order `0`、current position `0`、API call `0`；Stage182 池只读对照 pending order `1`，标的 `rb2610.SHFE Short Open 11`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_live_15w_timed_cycle_latest_report.md`
- Stage901 report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow_report_stage901_stage847_c9_2026_ytd_live_shadow_v1.md`
- entry candidates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow_entry_candidates_stage901_stage847_c9_2026_ytd_live_shadow_v1.csv`
- pending orders：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow_pending_orders_stage901_stage847_c9_2026_ytd_live_shadow_v1.csv`

## 结论

- 本阶段结论：按当前正式 C9/15w 实际加载的老 AI 池，邮件提示今晚和明早无交易信息是正确的，没有漏掉正式可执行订单。
- 关键风险：`rb.SHFE` 今天本身已经达到 `short_case1a` 日线结构，但因为当前实际池不含 `rb.SHFE` 被阻断；如果运营意图已经是 Stage182 `2026-05-29` 池，则当前配置接线需要单独修正和完整重跑。
- 是否进入下一步：是，但下一步不是策略优化，而是配置口径决策。
- 下一步：明确 C9/15w 官方实盘到底继续使用当前 `2026-02-27` 老 AI 池，还是切换到 `OFFICIAL_LIVE_AI_ELIGIBILITY_PATH` 的 Stage182 池；若切换，必须先跑正式 shadow、dry-run、只读账户/持仓 gate，再考虑报单，不可直接根据本次 what-if 下单。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本次没有调参、没有按今日结果筛参数，也没有推广新规则；只是用冻结 C9 规则解释今日收盘后为何无信号，并发现配置路径差异。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：复核确认邮件在当前正式口径下正确，同时暴露 `rb.SHFE` 的池外阻断和 Stage182 池接线差异；这属于实盘执行前必须厘清的配置一致性问题。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新；这是日常信号复核，不是路线结论变化。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：暂不追加；除非后续决定切换官方 AI 池并完成正式 gate。
