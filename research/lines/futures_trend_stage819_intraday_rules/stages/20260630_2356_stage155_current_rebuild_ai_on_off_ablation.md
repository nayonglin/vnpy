# Stage155 当前重建版 C9 15万 AI ON/OFF 年度起点消融

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：`2026-06-30 23:56 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：延续 Stage154 历史复盘结论，对当前重建版 `official_live_stage847_c9_15w_stage819_05r_stop_retry_once` 做 AI 产品池开关消融，确认当前重建输入下 AI 是否仍有结构过滤价值。
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：本轮按用户此前“不要搜索”的约束不做外网/GitHub搜索；复用本仓 Stage901 C9 live wrapper 和当前 official live 配置。
- 我的判断：这是必要的质量审计，不是为了提出关 AI。历史 Stage404/784 已经证明关 AI 往往增加交易但降低质量；当前重建版也必须重新验证，避免把“AI 池和旧版不一样”误读成“AI 不重要”。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage155_c9_live_15w_ai_on_off_annual_starts.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：年度起点 `Jan 1 every year`；请求终点 `2026-06-30`；两组分支 `ai_on` / `ai_off`
- 修改参数：仅在 `ai_off` 分支关闭 `enable_ai_product_pool_filter` 并清空 `ai_product_pool_eligibility_path` / `ai_product_pool_strategy`
- 删除参数：无

## 回测/归因参数

- 策略口径：当前重建版 `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`
- 账户规模：`150,000`
- AI ON：当前 Stage182 combined eligibility 文件
- AI OFF：关闭 AI 产品池过滤；其他信号、C9 stop/retry、资金、分钟源、风险规则不变
- 起点：`2018-01` 至 `2026-01`，每年 1 个独立冷启动起点，共 `9` 对
- 请求终点：`2026-06-30`
- 连接/下单：不连接 CTP，不读取账户，不调用订单 API

## 结果

### 分支统计

| 分支 | 样本 | 正收益 | 期末权益中位 | 收益最低/中位/最高 | 最差回撤 | 回撤中位 | Sharpe中位 | 交易数合计 | DD30/DD40/DD50 | broker100 |
| --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | --- | ---: |
| `ai_on` | `9` | `9` | `339,299.0` | `1.9011% / 126.1993% / 9084.6458%` | `-56.2069%` | `-39.9820%` | `1.2246` | `3,531` | `5 / 4 / 4` | `0` |
| `ai_off` | `9` | `8` | `313,278.2` | `-16.9595% / 108.8521% / 576.5577%` | `-66.2013%` | `-49.6045%` | `0.6523` | `5,638` | `8 / 5 / 4` | `0` |

### 配对对比

- AI ON 收益胜出：`8/9`
- AI ON 回撤胜出：`9/9`
- AI ON Sharpe 胜出：`8/9`
- AI ON 交易数合计少 `2,107` 笔，但质量明显更高。
- 唯一收益输给 AI OFF 的起点是 `2025-01`：AI ON `32.3783%`，AI OFF `108.8521%`；但该起点 AI ON 回撤仍更浅，且不足以推翻整体结论。
- 早期起点差距极大：
  - `2018-01` AI ON 收益 `8471.4361%`，AI OFF `561.6874%`
  - `2019-01` AI ON 收益 `9084.6458%`，AI OFF `576.5577%`
  - `2020-01` AI ON收益 `3886.1873%`，AI OFF `295.7019%`

## 输出文件

- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage155_c9_live_15w_ai_on_off_annual_starts_summary_stage155_c9_live_15w_ai_on_off_annual_starts_v1.csv`
- stats：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage155_c9_live_15w_ai_on_off_annual_starts_stats_stage155_c9_live_15w_ai_on_off_annual_starts_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage155_c9_live_15w_ai_on_off_annual_starts_comparison_stage155_c9_live_15w_ai_on_off_annual_starts_v1.csv`
- curves：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage155_c9_live_15w_ai_on_off_annual_starts_curves_stage155_c9_live_15w_ai_on_off_annual_starts_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage155_c9_live_15w_ai_on_off_annual_starts_decision_stage155_c9_live_15w_ai_on_off_annual_starts_v1.json`
- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage155_c9_live_15w_ai_on_off_annual_starts_report_stage155_c9_live_15w_ai_on_off_annual_starts_v1.md`

## 结论

- 当前重建版仍支持历史主判断：AI 产品池是质量过滤器，不是简单减少交易机会的限制器。
- AI OFF 在当前 C9 15万口径下交易数从 `3,531` 增到 `5,638`，但收益、回撤、Sharpe 的系统性表现更差；所以后续不应沿“放宽/关闭 AI 来增加机会”优化。
- 当前可继续方向：
  1. 做 AI 拦截归因：被 AI OFF 多开的交易，哪些品种/方向/case/月份造成回撤和收益稀释；
  2. 做当前重建版三臂基准：Stage372 legacy、Stage819/C4、Stage847/C9；
  3. 保留 C9 stop/retry，转向账户/持仓层风险尾治理，而不是调 R 倍数或重试次数。

## 过拟合反思

- 运行前判断：否
- 运行后判断：否
- 原因：唯一变量预先固定为 AI 产品池开关；没有根据结果挑年份、品种、月份或参数。`2025-01` AI OFF 胜出也不应被拿来做年份补丁。

## 继续价值反思

- 运行前判断：是
- 运行后判断：是
- 原因：结果确认当前重建版仍应保留 AI，并把下一步优化收敛到 AI 拦截归因和 C9 风险尾治理。继续关 AI、放宽 AI 或扫 AI topN 没有价值。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新；等 Stage372/C4/C9 三臂基准和 AI 拦截归因补完后统一整理。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段是质量审计，不是正式候选或重要突破。
