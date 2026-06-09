# Stage405 正式版 Stage372 鸡蛋 + AI Top9 + maxpos5 反证

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-07 14:58 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：当前正式版 Stage372/20万扩池与并发候选 A/B/C 回测
- 是否重要突破：否，但属于正式候选关键反证
- 是否触发A/B：是，属于可能接入正式版的品种池/AI选品/并发上限候选

## 外部调研与判断

- 参考资料：
  - GitHub `quantiacs/strategy-futures-trend-following`：商品期货趋势跟踪模板显示多市场趋势跟踪是常见结构。
  - CFA Institute Research Foundation 2025 `Machine Learning in Commodity Futures`：商品期货机器学习需要把理论嵌入特征、做横截面组合与样本外验证。
  - NBER `The Tactical and Strategic Value of Commodity Futures`：商品期货动量/战术策略存在历史价值，但应关注风险与组合约束。
- 我的判断：多品种分散化本身是对的，但“新增品种 + 放宽并发 + 改 AI topN”不是免费机会。只有当新增品种不挤占已有右尾、AI排序能在点时化样本外稳定保留核心赢家、保证金路径不恶化时，才可接正式版。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage692_official_stage372_jd_top9_maxpos5.py`
- 修改脚本：无正式策略修改。
- 删除脚本：无。
- 新增参数：
  - `JD_PRODUCT="jd.DCE"`
  - `AI_TOP_N=9`
  - `AI_TOP9_STRATEGY="stage692_official_stage372_plus_jd_full_market_ai_top9_entry_filter"`
  - `max_concurrent_positions=5`
- 修改参数：
  - B 分支只把 `max_concurrent_positions` 从 `4` 改为 `5`。
  - C 分支把 `jd.DCE` 写入 product universe，使用 full-market AI OOS predictions 月度纯 `top9` eligibility，并把 `max_concurrent_positions` 改为 `5`。
- 删除参数：C 分支不再使用正式 AI 的固定 `top8 + fu satellite` 口径；2020-2021 因 full-market AI 预测未覆盖，沿用正式 AI 快照且不放行鸡蛋。
- 正式配置：未修改。
- CTP/下单：未连接 CTP，未调用 order API。

## 回测/归因参数

- 数据区间：沿用 Stage653/Stage372 全周期回测口径。
- 账户规模：`200,000`
- 成本口径：正常成本、`2x`、`3x` 滑点压力。
- 样本过滤：full-market AI predictions 覆盖 `2022-01-28` 至 `2026-02-27`；此前使用正式 AI eligibility 快照，避免首个 AI eval_date 前所有品种默认放开。
- 策略/归因口径：
  - A：当前正式版 `stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4`
  - B：`stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos5`
  - C：`stage526_200k_force95_to80_recovery_sleeve_r080_pc25_plus_jd_ai_top9_maxpos5`

## 结果

- A 正式版：
  - 期末权益 `8,728,285`
  - 总收益 `4264.1425%`
  - 最大回撤 `-38.6713%`
  - Sharpe `1.6279`
  - 总滑点 `506,220`
  - 总交易次数 `633`
  - 胜率 `52.2586%`
  - broker10 峰值 `79.6015%`
  - 强制减仓 `6` 次，`299` 手
- B 仅 maxpos5：
  - 期末权益 `7,511,205`
  - 总收益 `3655.6025%`
  - 最大回撤 `-38.7987%`
  - Sharpe `1.5831`
  - 总滑点 `434,330`
  - 总交易次数 `661`
  - 胜率 `52.2748%`
  - broker10 峰值 `77.3076%`
  - 强制减仓 `15` 次，`474` 手
  - 相对 A：交易 `+28`，收益少 `608.54pp`，期末权益少 `1,217,080`，Sharpe 少 `0.0447`
- C 鸡蛋 + AI top9 + maxpos5：
  - 期末权益 `590,220`
  - 总收益 `195.1100%`
  - 最大回撤 `-59.3539%`
  - Sharpe `0.6476`
  - 总滑点 `158,870`
  - 总交易次数 `619`
  - 胜率 `48.9037%`
  - broker10 峰值 `108.0745%`
  - 超 `100%` 保证金 `1` 天，超 `90%` 保证金 `4` 天
  - 强制减仓 `7` 次，`60` 手
  - 相对 A：期末权益少 `8,138,065`，收益少 `4069.0325pp`，最大回撤恶化 `20.6826pp`，Sharpe 少 `0.9802`，交易少 `14`
  - 相对 B：期末权益少 `6,920,985`，收益少 `3460.4925pp`，最大回撤恶化 `20.5552pp`，Sharpe 少 `0.9355`
- 成本压力：
  - A `2x/3x` DD：`-40.6555%/-42.7649%`
  - B `2x/3x` DD：`-40.7796%/-42.8862%`
  - C `2x/3x` DD：`-67.7997%/-77.3618%`
- 年度：
  - C 在 `2022` 为 `-38,255/-4.3165%`
  - C 在 `2023` 为 `-214,075/-23.1312%`
  - C 在 `2024` 为 `-180,260/-25.3386%`
  - C 在 `2026` 为 `-37,775/-6.0152%`
- AI 审计：
  - AI eval dates `51`
  - 鸡蛋进入 AI top9 `19/51` 次，选择率 `37.2549%`
  - 说明本次不是“鸡蛋几乎没进池”的无效测试。
- 产品归因：
  - 鸡蛋自身净 PnL `-75,300`
  - C 相对 A 主要恶化：`jm -3,196,470`、`oi -1,225,820`、`fu -922,050`、`lh -795,600`、`ru -697,500`、`si -610,675`、`au -543,660`
  - 少数改善：`ma +518,870`、`ap +288,960`、`hc +177,590`、`sp +117,900`、`sa +79,440`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage692_official_stage372_jd_top9_maxpos5_report_stage692_official_stage372_jd_top9_maxpos5_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage692_official_stage372_jd_top9_maxpos5_summary_stage692_official_stage372_jd_top9_maxpos5_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage692_official_stage372_jd_top9_maxpos5_daily_stage692_official_stage372_jd_top9_maxpos5_v1.csv`
- product_delta：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage692_official_stage372_jd_top9_maxpos5_product_delta_stage692_official_stage372_jd_top9_maxpos5_v1.csv`
- ai_audit：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage692_official_stage372_jd_top9_maxpos5_ai_top9_audit_stage692_official_stage372_jd_top9_maxpos5_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage692_official_stage372_jd_top9_maxpos5_chart_stage692_official_stage372_jd_top9_maxpos5_v1.png`

## 结论

- 本阶段结论：`official_stage372_plus_jd_ai_top9_maxpos5_rejected`
- 是否进入下一步：不进入正式版，不进入 promotion。
- 核心判断：
  - 鸡蛋技术上可以加入，也能被 AI 选中。
  - 但当前组合不能接正式版，因为失败主因不是鸡蛋单品亏损，而是 full-market AI top9 改写了原正式 AI 的右尾保留结构，显著挤掉 `jm/oi/fu/lh/ru/si/au` 等核心赢家。
  - 只把 maxpos4 改为 maxpos5 也没有提升收益，交易多 `28` 笔但收益下降，说明当前正式 maxpos4 不是明显漏机会瓶颈。
- 下一步：
  - 不扫 `top8/top9/top10` 或 `maxpos5/6/7` 整数补丁。
  - 若继续研究鸡蛋，只允许做独立小 sleeve / 非挤占式风险槽 / 只读 forward 监控；不得塞进当前主账户共享风险池。
  - 若继续研究 AI 扩池，必须重新做点时化 live inference 覆盖最新月份，并先证明新 selector 不破坏原正式版核心右尾产品。

## 过拟合反思

- 运行前判断：不是过拟合；这是结构性 A/B/C 检验，变量预先声明。
- 运行后判断：本阶段本身不是过拟合，但继续围绕本失败形态扫 topN、maxpos 或按品种/年份补丁会变成过拟合。
- 原因：失败不是小阈值问题，而是账户右尾替换和 AI 选品口径变化导致的结构性失效。

## 继续价值反思

- 运行前判断：有价值；它直接回答“鸡蛋能不能加、maxpos5/top9 能不能释放机会”。
- 运行后判断：本形态无继续推广价值；扩池大方向仍有价值，但必须换成非挤占式或先验 selector 证据路线。
- 原因：C 收益保留仅 `4.5756%`，回撤恶化到 `-59.3539%`，2x成本 DD 到 `-67.7997%`，已经不是可通过微调修复的候选。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage405 反证。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：是，属于正式候选反证。
