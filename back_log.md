# 2026-04-22 QMT Roll Backtest

## Version Change

- 将 `qmt_roll_portfolio_strategy.py` 中的 `max_single_trade_capital_usage_ratio` 从 `0.3` 调整为 `0.5`。
- 保持其他核心口径不变：
  - 全局冠军风险参数：`0.045 / 0.06 / 0.06 / 0.025`
  - 仓位 sizing 仍保留 `100 万` 资金上限
  - 空头初始止损仍为当天最高价
  - 新开空仍仅允许 `short_case1a`

## Backtest Parameters

- Script: `examples/portfolio_backtesting/run_qmt_roll_backtest.py`
- Capital: `200000`
- Max capital usage ratio: `0.9`
- Max single trade capital usage ratio: `0.5`
- Risk ratios:
  - `risk_ratio_of_total_assets = 0.045`
  - `risk_ratio_open_interest_surge = 0.06`
  - `risk_ratio_volume_open_interest_surge = 0.06`
  - `risk_ratio_open_interest_decline = 0.025`

## Backtest Result

- Start Date: `2020-01-02`
- End Date: `2026-04-21`
- End Balance: `1791385.00`
- Total Return: `795.69%`
- Max Drawdown: `-1109260.00`
- Max Drawdown Percent: `-56.02%`
- Sharpe Ratio: `0.6394`
- Total Net PnL: `1591385.00`
- Total Slippage: `337920.00`
- Total Trade Count: `992`
- Win Ratio: `40.71%`
- Win Count / Round Trips: `206 / 506`

## Quick Note

- 相比刚才的 `30%` 单笔资金上限版本，本次 `50%` 版本收益明显回升：
  - `30%` 版本期末权益约 `1610900`
  - `50%` 版本期末权益约 `1791385`
- 但回撤没有明显优于之前的正式基线，属于“在限制仍生效的前提下，放松仓位后收益恢复、风险同步抬升”的结果。

# 2026-04-22 单参数资金上限粗网格实验

## 版本改动

- 新增脚本：`examples/portfolio_backtesting/run_qmt_roll_single_cap_grid.py`
- 修改入口：`examples/portfolio_backtesting/run_qmt_roll_backtest.py`
  - 新增 `strategy_overrides` 参数，允许实验脚本覆盖策略参数
- 本次没有删除已有参数
- 本次实验固定其他核心口径不变：
  - 四档风险参数保持 `0.045 / 0.06 / 0.06 / 0.025`
  - `100 万` sizing 资金上限保持开启
  - 单笔资金上限作为唯一网格参数
  - 空头初始止损保持当天最高价
  - 新开空仍仅允许 `short_case1a`

## 实验参数

- 脚本：`examples/portfolio_backtesting/run_qmt_roll_single_cap_grid.py`
- 回测入口：`examples/portfolio_backtesting/run_qmt_roll_backtest.py`
- 初始资金：`200000`
- 粗网格候选：
  - `0.2`
  - `0.3`
  - `0.4`
  - `0.5`
  - `0.6`
  - `0.7`
  - `0.8`
- 汇总文件：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_single_cap_grid_summary.csv`

## 粗网格结果

- `0.7`
  - 期末权益 `2515715`
  - 总收益 `1157.86%`
  - 最大回撤 `-31.69%`
  - Sharpe `1.0574`
  - 总滑点 `308750`
  - 总交易次数 `980`
- `0.8`
  - 期末权益 `2502495`
  - 总收益 `1151.25%`
  - 最大回撤 `-32.15%`
  - Sharpe `1.0524`
  - 总滑点 `309750`
  - 总交易次数 `980`
- `0.4`
  - 期末权益 `2238420`
  - 总收益 `1019.21%`
  - 最大回撤 `-32.59%`
  - Sharpe `1.0370`
  - 总滑点 `292220`
  - 总交易次数 `998`
- `0.5`
  - 期末权益 `2117580`
  - 总收益 `958.79%`
  - 最大回撤 `-35.51%`
  - Sharpe `0.9469`
  - 总滑点 `296770`
  - 总交易次数 `990`
- `0.6`
  - 期末权益 `2072145`
  - 总收益 `936.07%`
  - 最大回撤 `-37.25%`
  - Sharpe `0.8973`
  - 总滑点 `301720`
  - 总交易次数 `988`
- `0.3`
  - 期末权益 `1862380`
  - 总收益 `831.19%`
  - 最大回撤 `-36.95%`
  - Sharpe `0.9152`
  - 总滑点 `269610`
  - 总交易次数 `997`
- `0.2`
  - 期末权益 `1590465`
  - 总收益 `695.23%`
  - 最大回撤 `-40.28%`
  - Sharpe `0.8205`
  - 总滑点 `246500`
  - 总交易次数 `999`

## 结果变化说明

- 新增的回测结果：
  - 新增 `0.2 ~ 0.8` 共 `7` 组单参数资金上限粗网格结果
- 修改的回测结果：
  - 当前默认单笔资金上限为 `0.5` 时，主回测结果已记录在上一个章节
- 删除的回测结果：
  - 本次无删除，仅新增实验结果

## 快速结论

- 第一轮粗网格冠军是 `0.7`
- `0.7` 和 `0.8` 的收益、Sharpe、回撤都明显优于 `0.5`
- `0.4` 也表现不错，且回撤接近最优区间
- 下一轮建议细化区间：
  - `0.60`
  - `0.65`
  - `0.70`
  - `0.75`
  - `0.80`

# 2026-04-22 单参数资金上限精细网格实验

## 版本改动

- 新增脚本：`examples/portfolio_backtesting/run_qmt_roll_single_cap_grid_refined.py`
- 本次没有新增、修改或删除策略参数
- 本次仅新增精细网格实验结果，复用上一轮粗网格的实验链路

## 实验参数

- 脚本：`examples/portfolio_backtesting/run_qmt_roll_single_cap_grid_refined.py`
- 回测入口：`examples/portfolio_backtesting/run_qmt_roll_backtest.py`
- 初始资金：`200000`
- 精细网格范围：`0.60 ~ 0.80`
- 步长：`0.05`
- 候选值：
  - `0.60`
  - `0.65`
  - `0.70`
  - `0.75`
  - `0.80`
- 汇总文件：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_single_cap_grid_refined_summary.csv`

## 精细网格结果

- `0.70`
  - 期末权益 `2515715`
  - 总收益 `1157.86%`
  - 最大回撤 `-31.69%`
  - Sharpe `1.0574`
  - 总滑点 `308750`
  - 总交易次数 `980`
- `0.75`
  - 期末权益 `2511225`
  - 总收益 `1155.61%`
  - 最大回撤 `-31.89%`
  - Sharpe `1.0548`
  - 总滑点 `309350`
  - 总交易次数 `980`
- `0.80`
  - 期末权益 `2502495`
  - 总收益 `1151.25%`
  - 最大回撤 `-32.15%`
  - Sharpe `1.0524`
  - 总滑点 `309750`
  - 总交易次数 `980`
- `0.65`
  - 期末权益 `2090375`
  - 总收益 `945.19%`
  - 最大回撤 `-37.26%`
  - Sharpe `0.8879`
  - 总滑点 `303230`
  - 总交易次数 `984`
- `0.60`
  - 期末权益 `2072145`
  - 总收益 `936.07%`
  - 最大回撤 `-37.25%`
  - Sharpe `0.8973`
  - 总滑点 `301720`
  - 总交易次数 `988`

## 结果变化说明

- 新增的回测结果：
  - 新增 `0.60 / 0.65 / 0.70 / 0.75 / 0.80` 共 `5` 组精细网格结果
- 修改的回测结果：
  - 无，当前默认参数未写回
- 删除的回测结果：
  - 无

## 快速结论

- 第二轮精细网格冠军仍然是 `0.70`
- `0.70 / 0.75 / 0.80` 三者非常接近，但 `0.70` 在收益、Sharpe、回撤三项综合上仍然最优
- `0.65` 以下出现明显性能台阶，说明单笔资金上限的甜点区间更接近 `0.70 ~ 0.80`
- 如果要写回默认配置，当前最优建议值为：
  - `max_single_trade_capital_usage_ratio = 0.70`

# 2026-04-22 将单笔资金上限 0.70 写回默认配置

## 版本改动

- 修改的参数：
  - `examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
  - `max_single_trade_capital_usage_ratio: 0.5 -> 0.7`
- 新增的参数：
  - 无
- 删除的参数：
  - 无

## 回测参数

- 脚本：`examples/portfolio_backtesting/run_qmt_roll_backtest.py`
- 初始资金：`200000`
- 总资金上限：`100 万`
- 单笔资金上限：`0.70`
- 四档风险参数：
  - `risk_ratio_of_total_assets = 0.045`
  - `risk_ratio_open_interest_surge = 0.06`
  - `risk_ratio_volume_open_interest_surge = 0.06`
  - `risk_ratio_open_interest_decline = 0.025`
- 空头初始止损：当天最高价
- 新开空限制：仅允许 `short_case1a`

## 新增的回测结果

- 期末权益 `2,515,715`
- 总收益 `1157.86%`
- 最大回撤 `-31.69%`
- Sharpe `1.0574`
- 总滑点 `308,750`
- 总交易次数 `980`
- 胜率 `41.00%`
- 胜场 / 完整回合 `205 / 500`

## 修改的回测结果

- 相比上一版默认值 `0.50`：
  - 期末权益：`1,791,385 -> 2,515,715`
  - 总收益：`795.69% -> 1157.86%`
  - 最大回撤：`-56.02% -> -31.69%`
  - Sharpe：`0.6394 -> 1.0574`
  - 总滑点：`337,920 -> 308,750`
  - 总交易次数：`992 -> 980`

## 删除的回测结果

- 无，本次仅刷新默认参数后的正式主回测产物

## 快速说明

- 单参数粗网格和精细网格都验证了 `0.70` 是当前最优点
- 本次已经将 `0.70` 正式写回默认配置，并完成主回测刷新
- 当前这版结果明显优于 `0.50` 默认值版本，可作为后续多周期、Walk-Forward 与蒙特卡洛验证的新基线

# 2026-04-22 基于 0.70 默认配置的多周期 / Walk-Forward / 蒙特卡洛验证

## 版本改动

- 修改的脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_period_sweep.py`
  - `examples/portfolio_backtesting/run_qmt_roll_walkforward.py`
- 改动内容：
  - 显式对齐到当前默认配置 `max_single_trade_capital_usage_ratio = 0.70`
  - Walk-Forward 候选标签补充 `cap070` 标识，避免和旧口径结果混淆
- 新增的参数：
  - 无
- 删除的参数：
  - 无

## 验证参数

- 当前默认配置：
  - `max_single_trade_capital_usage_ratio = 0.70`
  - `risk_ratio_of_total_assets = 0.045`
  - `risk_ratio_open_interest_surge = 0.06`
  - `risk_ratio_volume_open_interest_surge = 0.06`
  - `risk_ratio_open_interest_decline = 0.025`
- 初始资金：`200000`
- 总资金上限：`100 万`
- 空头初始止损：当天最高价
- 新开空限制：仅允许 `short_case1a`

## 新增的回测结果

### 多周期

- 全样本 `full_sample`
  - 期末权益 `2,515,715`
  - 总收益 `1157.86%`
  - 最大回撤 `-31.69%`
  - Sharpe `1.0574`
  - 总交易次数 `980`
- 最强窗口 `period_2020_2021`
  - 总收益 `725.78%`
  - 最大回撤 `-31.05%`
  - Sharpe `1.9608`
- 最弱窗口 `roll_2022_2024`
  - 总收益 `-32.85%`
  - 最大回撤 `-68.07%`
  - Sharpe `-0.1599`
- 其他关键窗口：
  - `period_2022_2023`: `2.39% / -67.24% / Sharpe 0.0125`
  - `period_2024_2026`: `-11.30% / -34.37% / Sharpe -0.2100`
  - `roll_2023_2026`: `-24.50% / -55.37% / Sharpe -0.2724`

### Walk-Forward

- 测试窗口总数：`9`
- 正收益窗口：`1`
- 负收益窗口：`8`
- 最好窗口：`2025-01-01 ~ 2025-12-31`
  - 总收益 `44.76%`
  - 最大回撤 `-48.42%`
  - Sharpe `0.6283`
  - 选中参数：`alt_0045_006_006_0030_cap070`
- 最差窗口：`2026-01-01 ~ 2026-04-30`
  - 总收益 `-53.20%`
  - 最大回撤 `-58.23%`
  - Sharpe `-3.7633`
  - 选中参数：`alt_0040_0055_007_0025_cap070`
- 参数被选中次数：
  - `champion_0045_006_006_0025_cap070`: `4`
  - `alt_0045_006_006_0030_cap070`: `2`
  - `alt_0040_0055_007_0025_cap070`: `2`
  - `alt_0040_006_006_0030_cap070`: `1`

### 蒙特卡洛

- `daily_block_bootstrap`
  - 亏损概率 `2.4%`
  - 爆仓概率 `0.0%`
  - 回撤超过 `30%` 的概率 `94.5%`
  - 回撤超过 `40%` 的概率 `67.3%`
  - 中位收益 `688.40%`
  - 中位最大回撤 `-44.47%`
- `trade_block_bootstrap`
  - 亏损概率 `0.5%`
  - 爆仓概率 `0.2%`
  - 回撤超过 `30%` 的概率 `83.6%`
  - 回撤超过 `40%` 的概率 `69.2%`
  - 中位收益 `996.67%`
  - 中位最大回撤 `-55.26%`

## 修改的回测结果

- 无旧验证结果覆盖写回，本次主要是基于新默认配置新增一轮完整验证

## 删除的回测结果

- 无

## 快速说明

- `0.70` 默认配置的全样本指标非常强，但阶段敏感性仍然明显
- 多周期显示 `2022-2024` 和 `2023-2026` 仍是弱窗口
- Walk-Forward 只有 `1/9` 个测试窗口为正收益，样本外稳定性不足
- 蒙特卡洛显示亏损概率不高，但大回撤尾部风险依旧显著
- 结论：这版更适合作为当前最优全样本基线，但还不能直接定义为“稳健型”参数

# 2026-04-22 2022-2026 弱窗口专项优化实验

## 版本改动

- 新增脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_weak_window_optimization.py`
  - `examples/portfolio_backtesting/run_qmt_roll_weak_window_optimization_refined.py`
- 本次没有修改默认策略参数
- 本次新增的是弱窗口专项实验结果和全样本 A/B 对照结果

## 实验目标

- 只针对 `2022-01-01 ~ 2026-04-30` 弱窗口做专项优化
- 优先目标：
  - 降低回撤
  - 提升稳定性
  - 保持弱窗口内尽量为正收益
- 固定基线：
  - `max_single_trade_capital_usage_ratio = 0.70`
  - `risk_ratio_of_total_assets = 0.045`
  - `risk_ratio_open_interest_surge = 0.06`
  - `risk_ratio_volume_open_interest_surge = 0.06`
  - `risk_ratio_open_interest_decline = 0.025`

## 第一轮弱窗口专项实验结果

- 汇总文件：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_weak_window_optimization_summary.csv`
- 冠军：
  - `streak_defensive`
  - 配置：`streak_risk_multipliers = "1.0,1.0,0.5,0.25"`
  - 期末权益 `377,435`
  - 总收益 `88.72%`
  - 最大回撤 `-61.68%`
  - Sharpe `0.2275`
  - 总滑点 `101,520`
  - 总交易次数 `676`
- 当前弱窗口默认基线：
  - `baseline_cap070`
  - 期末权益 `94,655`
  - 总收益 `-52.67%`
  - 最大回撤 `-85.23%`
  - Sharpe `-0.1999`
  - 总滑点 `76,360`
  - 总交易次数 `581`
- 诊断参考：
  - `long_only_reference`
  - 期末权益 `198,955`
  - 总收益 `-0.52%`
  - 最大回撤 `-53.88%`
  - Sharpe `-0.0025`
  - 说明：关闭全部新开空后，弱窗口显著改善，说明空头确实是主要拖累来源

## 第二轮弱窗口专项精细实验结果

- 汇总文件：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_weak_window_optimization_refined_summary.csv`
- 冠军：
  - `streak_defensive_singlecap06`
  - 配置：
    - `streak_risk_multipliers = "1.0,1.0,0.5,0.25"`
    - `max_single_trade_capital_usage_ratio = 0.60`
  - 期末权益 `395,260`
  - 总收益 `97.63%`
  - 最大回撤 `-59.45%`
  - Sharpe `0.2441`
  - 总滑点 `106,330`
  - 总交易次数 `680`
- 第二名：
  - `streak_defensive_base`
  - 期末权益 `377,435`
  - 总收益 `88.72%`
  - 最大回撤 `-61.68%`
  - Sharpe `0.2275`
- 说明：
  - 在弱窗口里，“连败后更激进降风险”是最有效的主因
  - 在此基础上，把单笔资金上限从 `0.70` 再收一点到 `0.60`，效果进一步提升

## 全样本 A/B 对照

- 全样本当前正式基线：
  - `max_single_trade_capital_usage_ratio = 0.70`
  - 期末权益 `2,515,715`
  - 总收益 `1157.86%`
  - 最大回撤 `-31.69%`
  - Sharpe `1.0574`
  - 总交易次数 `980`
- 弱窗口冠军方案直接套到全样本：
  - `streak_risk_multipliers = "1.0,1.0,0.5,0.25"`
  - `max_single_trade_capital_usage_ratio = 0.60`
  - 期末权益 `2,024,960`
  - 总收益 `912.48%`
  - 最大回撤 `-44.41%`
  - Sharpe `0.7704`
  - 总交易次数 `1037`
- 只上连败降风险，不收单笔资金：
  - `streak_risk_multipliers = "1.0,1.0,0.5,0.25"`
  - `max_single_trade_capital_usage_ratio = 0.70`
  - 期末权益 `1,893,630`
  - 总收益 `846.82%`
  - 最大回撤 `-48.18%`
  - Sharpe `0.7249`
  - 总交易次数 `1037`

## 结果变化说明

- 新增的回测结果：
  - 新增弱窗口专项实验第一轮 `10` 组结果
  - 新增弱窗口专项实验第二轮 `7` 组结果
  - 新增弱窗口冠军方案的全样本 A/B 对照结果
- 修改的回测结果：
  - 无默认参数写回，本次仅做实验对照
- 删除的回测结果：
  - 无

## 快速结论

- 针对 `2022-2026` 弱窗口，最有效的优化方向不是继续堆过滤器，而是：
  - 连败后更激进降风险
  - 同时略微收紧单笔资金上限
- 弱窗口专项冠军方案：
  - `streak_risk_multipliers = "1.0,1.0,0.5,0.25"`
  - `max_single_trade_capital_usage_ratio = 0.60`
- 但这套方案直接用于全样本会明显削弱正式基线表现，因此更适合作为：
  - 弱窗口专用防御配置
  - 或未来 regime switch 的候选配置

# 2026-04-22 自动 Regime Switch 实现与 A/B 验证

## 版本改动

- 修改的文件：
  - `examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
  - `examples/portfolio_backtesting/run_qmt_roll_backtest.py`
- 改动内容：
  - 修复 `qmt_roll_portfolio_strategy.py` 中 MA5 角度过滤函数缺少 `math` 导入的问题
  - 将弱窗口防御参数正式接入自动 `regime switch` 架构：
    - 防御单笔资金上限：`defensive_max_single_trade_capital_usage_ratio = 0.60`
    - 防御连败风控：`defensive_streak_risk_multipliers = "1.0,1.0,0.5,0.25"`
  - 在回测统计中新增 `regime_switch_count / regime_defensive_days / regime_defensive_day_ratio / regime_last_reason`
  - 将正式回测入口中的 `regime switch` 参数显式写入 `build_roll_setting`
  - 默认值策略调整为：
    - 功能已实现
    - 默认保持 `regime_switch_enabled = False`
    - 需要通过 `strategy_overrides={"regime_switch_enabled": True}` 显式开启

## 参数变化说明

- 新增的参数：
  - 无新增策略参数定义，本次主要是把已有 `regime switch` 参数接入正式回测入口
- 修改的参数：
  - `regime_switch_enabled` 默认值明确设为 `False`
  - `run_qmt_roll_backtest.py` 显式写入以下默认防御参数：
    - `regime_switch_drawdown_trigger_pct = 0.12`
    - `regime_switch_drawdown_recover_pct = 0.05`
    - `regime_switch_loss_streak_trigger = 2`
    - `regime_switch_loss_streak_confirm_drawdown_pct = 0.03`
    - `defensive_max_single_trade_capital_usage_ratio = 0.60`
    - `defensive_streak_risk_multipliers = "1.0,1.0,0.5,0.25"`
- 删除的参数：
  - 无

## 回测参数

- 解释器：`/Users/bytedance/Desktop/person/vnpy/.py311/bin/python`
- `PYTHONPATH=/Users/bytedance/Desktop/person/vnpy`
- 回测入口：`examples/portfolio_backtesting/run_qmt_roll_backtest.py`
- 初始资金：`200000`
- 全样本进攻基线：
  - `risk_ratio_of_total_assets = 0.045`
  - `risk_ratio_open_interest_surge = 0.06`
  - `risk_ratio_volume_open_interest_surge = 0.06`
  - `risk_ratio_open_interest_decline = 0.025`
  - `max_single_trade_capital_usage_ratio = 0.70`
- 自动防御组：
  - `defensive_max_single_trade_capital_usage_ratio = 0.60`
  - `defensive_streak_risk_multipliers = "1.0,1.0,0.5,0.25"`
- A/B 口径：
  - `full_default`: 默认关闭 `regime switch`
  - `full_regime_on`: 通过 override 开启 `regime switch`
  - `weak_default`: `2022-01-01 ~ 2026-04-21` 默认关闭
  - `weak_regime_on`: `2022-01-01 ~ 2026-04-21` 开启自动切换

## 新增的回测结果

- `full_regime_on`
  - 期末权益 `1,462,165`
  - 总收益 `631.08%`
  - 最大回撤 `-56.70%`
  - Sharpe `0.6049`
  - 总交易次数 `1040`
  - Regime 切换次数 `25`
  - 防御期占比 `86.16%`
- `weak_regime_on`
  - 期末权益 `374,635`
  - 总收益 `87.32%`
  - 最大回撤 `-60.67%`
  - Sharpe `0.2260`
  - 总交易次数 `678`
  - Regime 切换次数 `25`
  - 防御期占比 `98.56%`

## 修改的回测结果

- 全样本：
  - `full_default`
    - 期末权益 `2,515,715`
    - 总收益 `1157.86%`
    - 最大回撤 `-31.69%`
    - Sharpe `1.0574`
    - 总交易次数 `980`
  - 对比 `full_regime_on`
    - 期末权益：`2,515,715 -> 1,462,165`
    - 总收益：`1157.86% -> 631.08%`
    - 最大回撤：`-31.69% -> -56.70%`
    - Sharpe：`1.0574 -> 0.6049`
    - 总交易次数：`980 -> 1040`
- 弱窗口：
  - `weak_default`
    - 期末权益 `94,655`
    - 总收益 `-52.67%`
    - 最大回撤 `-85.23%`
    - Sharpe `-0.1999`
    - 总交易次数 `581`
  - 对比 `weak_regime_on`
    - 期末权益：`94,655 -> 374,635`
    - 总收益：`-52.67% -> 87.32%`
    - 最大回撤：`-85.23% -> -60.67%`
    - Sharpe：`-0.1999 -> 0.2260`
    - 总交易次数：`581 -> 678`

## 删除的回测结果

- 无，本次为新增 A/B 验证结果

## 快速结论

- 自动 `regime switch` 规则已经实现，且能正确切换到弱窗口防御参数
- 在弱窗口中，这套规则显著改善了收益、回撤和 Sharpe
- 但在全样本中，当前触发阈值过于敏感，导致策略长期停留在防御态，显著拖累正式基线
- 因此当前结论是：
  - 保留功能
  - 默认不启用
  - 后续若要上线为默认，需要继续优化 `activate / recover` 阈值，降低防御态占比

# 2026-04-22 自动 Regime Switch 阈值搜索与定稿

## 版本改动

- 新增脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_regime_threshold_grid.py`
  - `examples/portfolio_backtesting/run_qmt_roll_regime_threshold_grid_refined.py`
- 修改的文件：
  - `examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
  - `examples/portfolio_backtesting/run_qmt_roll_backtest.py`
- 改动内容：
  - 新增第一轮 `regime switch` 阈值粗网格实验脚本，搜索中等敏感度区间
  - 新增第二轮 `regime switch` 阈值精细实验脚本，搜索更迟钝的触发区间
  - 将默认阈值从上一版高敏感配置改为折中冠军：
    - `regime_switch_drawdown_trigger_pct: 0.12 -> 0.26`
    - `regime_switch_drawdown_recover_pct: 0.05 -> 0.16`
    - `regime_switch_loss_streak_trigger: 2 -> 6`
    - `regime_switch_loss_streak_confirm_drawdown_pct: 0.03 -> 0.12`
  - 保持以下口径不变：
    - `regime_switch_enabled = False`
    - `defensive_max_single_trade_capital_usage_ratio = 0.60`
    - `defensive_streak_risk_multipliers = "1.0,1.0,0.5,0.25"`

## 参数变化说明

- 新增的参数：
  - 无新增策略参数字段
- 修改的参数：
  - `regime_switch_drawdown_trigger_pct = 0.26`
  - `regime_switch_drawdown_recover_pct = 0.16`
  - `regime_switch_loss_streak_trigger = 6`
  - `regime_switch_loss_streak_confirm_drawdown_pct = 0.12`
- 删除的参数：
  - 无

## 回测参数

- 解释器：`/Users/bytedance/Desktop/person/vnpy/.py311/bin/python`
- `PYTHONPATH=/Users/bytedance/Desktop/person/vnpy`
- 回测入口：`examples/portfolio_backtesting/run_qmt_roll_backtest.py`
- 风险参数基线：
  - `risk_ratio_of_total_assets = 0.045`
  - `risk_ratio_open_interest_surge = 0.06`
  - `risk_ratio_volume_open_interest_surge = 0.06`
  - `risk_ratio_open_interest_decline = 0.025`
- 进攻仓位基线：
  - `max_single_trade_capital_usage_ratio = 0.70`
- 防御仓位基线：
  - `defensive_max_single_trade_capital_usage_ratio = 0.60`
  - `defensive_streak_risk_multipliers = "1.0,1.0,0.5,0.25"`
- 第一轮粗网格范围：
  - `drawdown_trigger`: `0.14 / 0.16 / 0.18`
  - `recover_pct`: `0.08 / 0.10`
  - `loss_streak_trigger`: `3 / 4`
  - `confirm_drawdown_pct`: `0.05 / 0.07`
- 第二轮精细网格范围：
  - `drawdown_trigger`: `0.22 / 0.26 / 0.30`
  - `recover_pct`: `0.12 / 0.16`
  - `loss_streak_trigger`: `5 / 6`
  - `confirm_drawdown_pct`: `0.08 / 0.12`

## 新增的回测结果

- 第一轮粗网格汇总文件：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_regime_threshold_grid_summary.csv`
- 第一轮粗网格最佳候选：
  - `dd18_rec10_ls4_cf05`
  - 全样本：
    - 期末权益 `1,400,440`
    - 总收益 `600.22%`
    - 最大回撤 `-56.45%`
    - Sharpe `0.5897`
    - 总交易次数 `1032`
    - 防御期占比 `73.77%`
  - 弱窗口：
    - 期末权益 `376,345`
    - 总收益 `88.17%`
    - 最大回撤 `-66.90%`
    - Sharpe `0.1921`
    - 总交易次数 `686`
- 第二轮精细网格汇总文件：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_regime_threshold_grid_refined_summary.csv`
- 第二轮折中冠军：
  - `dd26_rec16_ls6_cf12`
  - 全样本：
    - 期末权益 `2,365,835`
    - 总收益 `1082.92%`
    - 最大回撤 `-43.04%`
    - Sharpe `0.9281`
    - 总交易次数 `996`
    - Regime 切换次数 `16`
    - 防御期占比 `36.92%`
  - 弱窗口：
    - 期末权益 `294,110`
    - 总收益 `47.06%`
    - 最大回撤 `-75.28%`
    - Sharpe `0.1066`
    - 总交易次数 `664`
    - Regime 切换次数 `17`
    - 防御期占比 `63.14%`
- 第二轮全样本保护最强候选：
  - `dd30_rec12_ls6_cf12`
  - 全样本：
    - 期末权益 `2,745,550`
    - 总收益 `1272.78%`
    - 最大回撤 `-36.22%`
    - Sharpe `1.0727`
    - 防御期占比 `28.07%`
  - 弱窗口：
    - 期末权益 `243,445`
    - 总收益 `21.72%`
    - 最大回撤 `-81.33%`
    - Sharpe `0.0538`

## 修改的回测结果

- 对比上一版高敏感阈值 `0.12 / 0.05 / 2 / 0.03`：
  - 全样本开启 `regime switch` 时：
    - 总收益：`631.08% -> 1082.92%`
    - 最大回撤：`-56.70% -> -43.04%`
    - Sharpe：`0.6049 -> 0.9281`
    - 防御期占比：`86.16% -> 36.92%`
    - 切换次数：`25 -> 16`
  - 弱窗口开启 `regime switch` 时：
    - 总收益：`87.32% -> 47.06%`
    - 最大回撤：`-60.67% -> -75.28%`
    - Sharpe：`0.2260 -> 0.1066`
    - 防御期占比：`98.56% -> 63.14%`
- 对比默认关闭 `regime switch` 的正式基线：
  - 全样本：
    - 总收益：`1157.86% -> 1082.92%`
    - 最大回撤：`-31.69% -> -43.04%`
    - Sharpe：`1.0574 -> 0.9281`
  - 弱窗口：
    - 总收益：`-52.67% -> 47.06%`
    - 最大回撤：`-85.23% -> -75.28%`
    - Sharpe：`-0.1999 -> 0.1066`

## 删除的回测结果

- 无，本次为新增阈值搜索结果并刷新默认阈值

## 快速结论

- 第一轮 `0.14 ~ 0.18` 的阈值仍然过于敏感，全样本防御期占比最低仍在 `73%+`
- 第二轮更迟钝的阈值显著改善了这个问题，其中：
  - `dd30_rec12_ls6_cf12` 更偏向保全全样本表现
  - `dd26_rec16_ls6_cf12` 更偏向兼顾全样本与弱窗口
- 最终默认阈值采用折中冠军：
  - `drawdown_trigger = 0.26`
  - `recover_pct = 0.16`
  - `loss_streak_trigger = 6`
  - `confirm_drawdown_pct = 0.12`
- 当前建议：
  - 保留 `regime_switch_enabled = False` 作为默认
  - 但后续显式开启时，使用这套新阈值
  - 如果未来想进一步提高弱窗口保护力度，可以在 `0.26` 和 `0.30` 两档之间继续做更细化搜索

# 2026-04-22 完全移除 Regime Switch / 回撤保护逻辑

## 版本改动

- 修改的文件：
  - `examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
  - `examples/portfolio_backtesting/run_qmt_roll_backtest.py`
- 删除的文件：
  - `examples/portfolio_backtesting/run_qmt_roll_regime_threshold_grid.py`
  - `examples/portfolio_backtesting/run_qmt_roll_regime_threshold_grid_refined.py`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_regime_threshold_grid_summary.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_regime_threshold_grid_refined_summary.csv`
- 改动内容：
  - 从主策略中完全删除 `regime switch / 回撤保护` 相关参数、状态变量、切换逻辑和诊断字段
  - 恢复单笔资金上限与连败风控为纯基线实现，不再根据回撤状态动态切换
  - 从主回测入口中删除 `regime switch` 默认参数和统计输出
  - 删除该方向新增的两份阈值实验脚本和对应汇总产物

## 参数变化说明

- 新增的参数：
  - 无
- 修改的参数：
  - 无，本次是删除回撤保护方向，不新增新的替代参数
- 删除的参数：
  - `regime_switch_enabled`
  - `regime_switch_drawdown_trigger_pct`
  - `regime_switch_drawdown_recover_pct`
  - `regime_switch_loss_streak_trigger`
  - `regime_switch_loss_streak_confirm_drawdown_pct`
  - `defensive_max_single_trade_capital_usage_ratio`
  - `defensive_streak_risk_multipliers`
- 删除的统计字段：
  - `regime_switch_count`
  - `regime_defensive_days`
  - `regime_defensive_day_ratio`
  - `regime_last_reason`

## 当前保留的主回测口径

- 回测入口：`examples/portfolio_backtesting/run_qmt_roll_backtest.py`
- 初始资金：`200000`
- 风险参数：
  - `risk_ratio_of_total_assets = 0.045`
  - `risk_ratio_open_interest_surge = 0.06`
  - `risk_ratio_volume_open_interest_surge = 0.06`
  - `risk_ratio_open_interest_decline = 0.025`
- 仓位参数：
  - `max_single_trade_capital_usage_ratio = 0.70`
  - `streak_risk_multipliers = "1.0,1.0,1.0,0.1"`
- 本次未新增回测结果，属于逻辑清理回退

## 删除的回测结果

- 删除该方向对应的实验产物引用：
  - `qmt_roll_regime_threshold_grid_summary.csv`
  - `qmt_roll_regime_threshold_grid_refined_summary.csv`
- 历史记录仍保留在本日志中，作为已尝试但放弃的优化路径说明

## 快速结论

- 当前已完全放弃 `regime switch / 回撤保护` 这个方向
- 主策略恢复为不带动态回撤状态切换的纯基线版本
- 后续如果继续优化，应回到信号质量、仓位结构、止损结构或品种暴露分布这些更基础的方向

# 2026-04-23 13:33 主回测复验

## 版本改动

- 改动时间点：`2026-04-23 13:33`
- 改动内容：
  - 无新增代码改动
  - 本次仅在移除 `regime switch / 回撤保护` 后，重新执行主回测做链路复验

## 参数变化说明

- 新增的参数：
  - 无
- 修改的参数：
  - 无
- 删除的参数：
  - 无

## 回测参数

- 解释器：`/Users/bytedance/Desktop/person/vnpy/.py311/bin/python`
- `PYTHONPATH=/Users/bytedance/Desktop/person/vnpy`
- 回测入口：`examples/portfolio_backtesting/run_qmt_roll_backtest.py`
- 初始资金：`200000`
- 风险参数：
  - `risk_ratio_of_total_assets = 0.045`
  - `risk_ratio_open_interest_surge = 0.06`
  - `risk_ratio_volume_open_interest_surge = 0.06`
  - `risk_ratio_open_interest_decline = 0.025`
- 仓位参数：
  - `max_single_trade_capital_usage_ratio = 0.70`
  - `streak_risk_multipliers = "1.0,1.0,1.0,0.1"`
- 其他关键口径：
  - `100 万` sizing 资金上限保持开启
  - 新开空仍仅允许 `short_case1a`

## 新增的回测结果

- 期末权益 `2,515,715`
- 总收益 `1157.86%`
- 最大回撤 `-31.69%`
- Sharpe `1.0574`
- 收益回撤比 `2.6313`
- 总滑点 `308,750`
- 总交易次数 `980`
- 胜率 `41.00%`
- 胜场 / 完整回合 `205 / 500`

## 修改的回测结果

- 无，本次结果与当前正式基线一致，说明移除回撤保护后主回测链路正常

## 删除的回测结果

- 无

## 快速结论

- 主回测运行成功，无报错
- 结果回到当前正式基线：
  - `2,515,715 / 1157.86% / -31.69% / Sharpe 1.0574`
- 说明本次移除 `regime switch / 回撤保护` 没有把主回测逻辑改坏

# 2026-04-23 13:38 复盘图换月标记渲染优化

## 版本改动

- 改动时间点：`2026-04-23 13:38`
- 修改的文件：
  - `examples/portfolio_backtesting/run_qmt_alignment_backtest.py`
- 改动内容：
  - 移除专业看板第 1 行“组合权益曲线”上叠加的橙色 `换月标记` 点位
  - 保留下方单独的“换月事件时间轴”，继续用于查看换月发生日期
  - 删除已不再使用的 `_build_roll_daily_marker_df()` 辅助函数

## 参数变化说明

- 新增的参数：
  - 无
- 修改的参数：
  - 无
- 删除的参数：
  - 无

## 回测参数

- 解释器：`/Users/bytedance/Desktop/person/vnpy/.py311/bin/python`
- `PYTHONPATH=/Users/bytedance/Desktop/person/vnpy`
- 回测入口：`examples/portfolio_backtesting/run_qmt_roll_backtest.py`
- 本次仅重新生成图表产物，策略参数不变：
  - `risk_ratio_of_total_assets = 0.045`
  - `risk_ratio_open_interest_surge = 0.06`
  - `risk_ratio_volume_open_interest_surge = 0.06`
  - `risk_ratio_open_interest_decline = 0.025`
  - `max_single_trade_capital_usage_ratio = 0.70`

## 新增的回测结果

- 无新增策略结果，本次核心是图表渲染优化
- 重生成后的主回测结果保持不变：
  - 期末权益 `2,515,715`
  - 总收益 `1157.86%`
  - 最大回撤 `-31.69%`
  - Sharpe `1.0574`
  - 总滑点 `308,750`
  - 总交易次数 `980`

## 修改的回测结果

- 修改了 `qmt_roll_professional_dashboard.html` 的展示效果：
  - 组合权益主图不再显示密集橙色换月点
  - 权益折线细节可直接观察
  - 换月信息仍保留在独立时间轴子图中

## 删除的回测结果

- 无

## 快速结论

- 本次是纯展示层优化，不改变策略和回测结果
- 专业看板的主权益图可读性明显提升，换月信息没有丢失，只是从主图挪回独立子图查看

# 2026-04-23 13:46 注释掉 sp 后主回测复验

## 版本改动

- 改动时间点：`2026-04-23 13:46`
- 修改的文件：
  - `examples/portfolio_backtesting/qmt_universe.py`
- 改动内容：
  - 将 `ProductSpec("sp", Exchange.SHFE, 10, 2.0, 2.0, 0.10)` 注释掉
  - 使 `sp.SHFE` 暂时从主回测品种池中移除

## 参数变化说明

- 新增的参数：
  - 无
- 修改的参数：
  - 无
- 删除的参数：
  - 无
- 修改的品种池：
  - 删除 `sp.SHFE`

## 回测参数

- 解释器：`/Users/bytedance/Desktop/person/vnpy/.py311/bin/python`
- `PYTHONPATH=/Users/bytedance/Desktop/person/vnpy`
- 回测入口：`examples/portfolio_backtesting/run_qmt_roll_backtest.py`
- 初始资金：`200000`
- 风险参数：
  - `risk_ratio_of_total_assets = 0.045`
  - `risk_ratio_open_interest_surge = 0.06`
  - `risk_ratio_volume_open_interest_surge = 0.06`
  - `risk_ratio_open_interest_decline = 0.025`
- 仓位参数：
  - `max_single_trade_capital_usage_ratio = 0.70`
  - `streak_risk_multipliers = "1.0,1.0,1.0,0.1"`
- 其他关键口径：
  - `100 万` sizing 资金上限保持开启
  - 新开空仍仅允许 `short_case1a`
  - 本次仅调整品种池，其他策略逻辑不变

## 新增的回测结果

- `sp` 移除后的主回测结果：
  - 期末权益 `2,468,100`
  - 总收益 `1134.05%`
  - 最大回撤 `-31.66%`
  - Sharpe `0.9768`
  - 收益回撤比 `3.2041`
  - 总滑点 `287,740`
  - 总交易次数 `918`
  - 胜率 `42.52%`
  - 胜场 / 完整回合 `199 / 468`

## 修改的回测结果

- 对比上一版含 `sp` 的正式基线：
  - 期末权益：`2,515,715 -> 2,468,100`
  - 总收益：`1157.86% -> 1134.05%`
  - 最大回撤：`-31.69% -> -31.66%`
  - Sharpe：`1.0574 -> 0.9768`
  - 收益回撤比：`2.6313 -> 3.2041`
  - 总滑点：`308,750 -> 287,740`
  - 总交易次数：`980 -> 918`
  - 胜率：`41.00% -> 42.52%`

## 删除的回测结果

- 无

## 快速结论

- 去掉 `sp` 后，主回测没有报错，链路正常
- `sp` 对当前版本更像是“提高收益与 Sharpe 的贡献品种”，而不是主要回撤来源：
  - 去掉后总收益下降
  - Sharpe 下降
  - 回撤几乎不变
- 正面变化是交易数和滑点下降、胜率略升，但整体绩效并没有改善
- 当前结论：如果目标是穿越周期的整体收益效率，暂时不建议把 `sp` 从正式品种池里长期移除，除非后续专项归因能证明它在弱窗口存在不可接受的结构性风险

# 2026-04-23 13:58 加回 sp 且并发位从 4 提到 10 后主回测复验

## 版本改动

- 改动时间点：`2026-04-23 13:58`
- 修改的文件：
  - `examples/portfolio_backtesting/qmt_universe.py`
  - `examples/portfolio_backtesting/run_qmt_roll_backtest.py`
- 改动内容：
  - 将 `sp.SHFE` 加回主回测品种池
  - 将 `max_concurrent_positions` 从 `4` 调整为 `10`

## 参数变化说明

- 新增的参数：
  - 无
- 修改的参数：
  - `max_concurrent_positions: 4 -> 10`
- 删除的参数：
  - 无
- 修改的品种池：
  - 恢复 `sp.SHFE`

## 回测参数

- 解释器：`/Users/bytedance/Desktop/person/vnpy/.py311/bin/python`
- `PYTHONPATH=/Users/bytedance/Desktop/person/vnpy`
- 回测入口：`examples/portfolio_backtesting/run_qmt_roll_backtest.py`
- 初始资金：`200000`
- 风险参数：
  - `risk_ratio_of_total_assets = 0.045`
  - `risk_ratio_open_interest_surge = 0.06`
  - `risk_ratio_volume_open_interest_surge = 0.06`
  - `risk_ratio_open_interest_decline = 0.025`
- 仓位参数：
  - `max_single_trade_capital_usage_ratio = 0.70`
  - `max_concurrent_positions = 10`
  - `streak_risk_multipliers = "1.0,1.0,1.0,0.1"`
- 其他关键口径：
  - `100 万` sizing 资金上限保持开启
  - 新开空仍仅允许 `short_case1a`

## 新增的回测结果

- `sp` 加回且 `max_concurrent_positions = 10` 后主回测结果：
  - 期末权益 `2,902,960`
  - 总收益 `1351.48%`
  - 最大回撤 `-39.02%`
  - Sharpe `1.0385`
  - 收益回撤比 `3.6637`
  - 总滑点 `348,430`
  - 总交易次数 `1234`
  - 胜率 `41.81%`
  - 胜场 / 完整回合 `263 / 629`

## 修改的回测结果

- 对比当前正式基线（`sp` 在池内，`max_concurrent_positions = 4`）：
  - 期末权益：`2,515,715 -> 2,902,960`
  - 总收益：`1157.86% -> 1351.48%`
  - 最大回撤：`-31.69% -> -39.02%`
  - Sharpe：`1.0574 -> 1.0385`
  - 收益回撤比：`2.6313 -> 3.6637`
  - 总滑点：`308,750 -> 348,430`
  - 总交易次数：`980 -> 1234`
  - 胜率：`41.00% -> 41.81%`
- 对比上一版（`sp` 移除，`max_concurrent_positions = 4`）：
  - 期末权益：`2,468,100 -> 2,902,960`
  - 总收益：`1134.05% -> 1351.48%`
  - 最大回撤：`-31.66% -> -39.02%`
  - Sharpe：`0.9768 -> 1.0385`
  - 收益回撤比：`3.2041 -> 3.6637`
  - 总滑点：`287,740 -> 348,430`
  - 总交易次数：`918 -> 1234`
  - 胜率：`42.52% -> 41.81%`

## 删除的回测结果

- 无

## 快速结论

- 加回 `sp` 且放宽并发位后，组合显著放大了收益能力
- 代价是：
  - 回撤从 `-31.69%` 放大到 `-39.02%`
  - Sharpe 略低于当前正式基线
  - 成交次数和滑点明显上升
- 这说明 `max_concurrent_positions = 10` 更偏进攻型，不一定更适合“穿越周期”的正式默认配置

# 2026-04-23 14:02 max_concurrent_positions 四组对比回测

## 版本改动

- 改动时间点：`2026-04-23 14:02`
- 改动内容：
  - 无新增代码改动
  - 基于当前版本（`sp` 在池内）执行 `max_concurrent_positions = 4 / 6 / 8 / 10` 四组主回测对比

## 参数变化说明

- 新增的参数：
  - 无
- 修改的参数：
  - 仅通过 `strategy_overrides` 逐组覆盖：
    - `max_concurrent_positions = 4`
    - `max_concurrent_positions = 6`
    - `max_concurrent_positions = 8`
    - `max_concurrent_positions = 10`
- 删除的参数：
  - 无

## 回测参数

- 解释器：`/Users/bytedance/Desktop/person/vnpy/.py311/bin/python`
- `PYTHONPATH=/Users/bytedance/Desktop/person/vnpy`
- 回测入口：`examples/portfolio_backtesting/run_qmt_roll_backtest.py`
- 初始资金：`200000`
- 品种池：包含 `sp.SHFE`
- 固定风险参数：
  - `risk_ratio_of_total_assets = 0.045`
  - `risk_ratio_open_interest_surge = 0.06`
  - `risk_ratio_volume_open_interest_surge = 0.06`
  - `risk_ratio_open_interest_decline = 0.025`
- 固定仓位参数：
  - `max_single_trade_capital_usage_ratio = 0.70`
  - `streak_risk_multipliers = "1.0,1.0,1.0,0.1"`
  - `100 万` sizing 资金上限保持开启
- 说明：
  - 本轮四组使用 `save_artifacts=False`
  - 仅比较主回测统计，不覆盖正式产物文件

## 新增的回测结果

- `concurrent = 4`
  - 期末权益 `2,515,715`
  - 总收益 `1157.86%`
  - 最大回撤 `-31.69%`
  - Sharpe `1.0574`
  - 收益回撤比 `2.6313`
  - 总滑点 `308,750`
  - 总交易次数 `980`
  - 胜率 `41.00%`
- `concurrent = 6`
  - 期末权益 `2,805,720`
  - 总收益 `1302.86%`
  - 最大回撤 `-33.20%`
  - Sharpe `1.0684`
  - 收益回撤比 `3.5681`
  - 总滑点 `333,710`
  - 总交易次数 `1156`
  - 胜率 `41.69%`
- `concurrent = 8`
  - 期末权益 `3,015,735`
  - 总收益 `1407.87%`
  - 最大回撤 `-35.71%`
  - Sharpe `1.0854`
  - 收益回撤比 `3.8166`
  - 总滑点 `347,080`
  - 总交易次数 `1214`
  - 胜率 `42.00%`
- `concurrent = 10`
  - 期末权益 `2,902,960`
  - 总收益 `1351.48%`
  - 最大回撤 `-39.02%`
  - Sharpe `1.0385`
  - 收益回撤比 `3.6637`
  - 总滑点 `348,430`
  - 总交易次数 `1234`
  - 胜率 `41.81%`

## 修改的回测结果

- 相对 `concurrent = 4` 基线：
  - `concurrent = 6`
    - 总收益：`1157.86% -> 1302.86%`
    - 最大回撤：`-31.69% -> -33.20%`
    - Sharpe：`1.0574 -> 1.0684`
    - 收益回撤比：`2.6313 -> 3.5681`
  - `concurrent = 8`
    - 总收益：`1157.86% -> 1407.87%`
    - 最大回撤：`-31.69% -> -35.71%`
    - Sharpe：`1.0574 -> 1.0854`
    - 收益回撤比：`2.6313 -> 3.8166`
  - `concurrent = 10`
    - 总收益：`1157.86% -> 1351.48%`
    - 最大回撤：`-31.69% -> -39.02%`
    - Sharpe：`1.0574 -> 1.0385`
    - 收益回撤比：`2.6313 -> 3.6637`

## 删除的回测结果

- 无

## 快速结论

- 从“收益和回撤的平衡点”看：
  - `concurrent = 4` 最稳，但收益释放不足
  - `concurrent = 6` 是比较均衡的折中点
  - `concurrent = 8` 是本轮四组里的综合最佳平衡点
  - `concurrent = 10` 开始出现过度进攻，回撤明显放大，Sharpe 反而回落
- 当前四组里，如果兼顾穿越周期与收益效率，优先建议：
  - 第一选择：`max_concurrent_positions = 8`
  - 第二选择：`max_concurrent_positions = 6`

# 2026-04-23 14:14 正式默认值固化为 concurrent=8

## 版本改动

- 改动时间点：`2026-04-23 14:14`
- 修改的文件：
  - `examples/portfolio_backtesting/run_qmt_roll_backtest.py`
- 改动内容：
  - 将主回测默认 `max_concurrent_positions` 从 `10` 固化为 `8`
  - 重新执行正式主回测，刷新 `statistics/json/csv/html` 全部产物

## 参数变化说明

- 新增的参数：
  - 无
- 修改的参数：
  - `max_concurrent_positions: 10 -> 8`
- 删除的参数：
  - 无

## 回测参数

- 解释器：`/Users/bytedance/Desktop/person/vnpy/.py311/bin/python`
- `PYTHONPATH=/Users/bytedance/Desktop/person/vnpy`
- 回测入口：`examples/portfolio_backtesting/run_qmt_roll_backtest.py`
- 初始资金：`200000`
- 品种池：包含 `sp.SHFE`
- 风险参数：
  - `risk_ratio_of_total_assets = 0.045`
  - `risk_ratio_open_interest_surge = 0.06`
  - `risk_ratio_volume_open_interest_surge = 0.06`
  - `risk_ratio_open_interest_decline = 0.025`
- 仓位参数：
  - `max_single_trade_capital_usage_ratio = 0.70`
  - `max_concurrent_positions = 8`
  - `streak_risk_multipliers = "1.0,1.0,1.0,0.1"`
- 其他关键口径：
  - `100 万` sizing 资金上限保持开启
  - 新开空仍仅允许 `short_case1a`

## 新增的回测结果

- 正式主回测结果：
  - 期末权益 `3,015,735`
  - 总收益 `1407.87%`
  - 最大回撤 `-35.71%`
  - Sharpe `1.0854`
  - 收益回撤比 `3.8166`
  - 总滑点 `347,080`
  - 总交易次数 `1214`
  - 胜率 `42.00%`
  - 胜场 / 完整回合 `260 / 619`

## 修改的回测结果

- 对比上一版正式默认值（`concurrent = 10`）：
  - 期末权益：`2,902,960 -> 3,015,735`
  - 总收益：`1351.48% -> 1407.87%`
  - 最大回撤：`-39.02% -> -35.71%`
  - Sharpe：`1.0385 -> 1.0854`
  - 收益回撤比：`3.6637 -> 3.8166`
  - 总滑点：`348,430 -> 347,080`
  - 总交易次数：`1234 -> 1214`
- 对比旧正式基线（`concurrent = 4`）：
  - 期末权益：`2,515,715 -> 3,015,735`
  - 总收益：`1157.86% -> 1407.87%`
  - 最大回撤：`-31.69% -> -35.71%`
  - Sharpe：`1.0574 -> 1.0854`
  - 收益回撤比：`2.6313 -> 3.8166`

## 删除的回测结果

- 无

## 快速结论

- `max_concurrent_positions = 8` 已正式固化为当前默认值
- 这版相比 `10` 更均衡：
  - 收益更高
  - 回撤更小
  - Sharpe 更高
- 这版相比旧基线 `4` 更进攻，但收益、Sharpe、收益回撤比同步改善，当前可以作为新的正式默认配置

# 2026-04-23 14:23 单仓最大金额限制第一轮粗网格

## 版本改动

- 改动时间点：`2026-04-23 14:23`
- 修改的文件：
  - `examples/portfolio_backtesting/run_qmt_roll_single_cap_grid.py`
- 改动内容：
  - 将第一轮粗网格搜索范围收窄为 `0.40 / 0.50 / 0.60 / 0.70 / 0.80`
  - 明确本轮实验基于当前新基线：
    - `sp` 保留
    - `max_concurrent_positions = 8`

## 参数变化说明

- 新增的参数：
  - 无
- 修改的参数：
  - 单参数搜索范围更新为：
    - `max_single_trade_capital_usage_ratio = 0.40 / 0.50 / 0.60 / 0.70 / 0.80`
- 删除的参数：
  - 无

## 回测参数

- 解释器：`/Users/bytedance/Desktop/person/vnpy/.py311/bin/python`
- `PYTHONPATH=/Users/bytedance/Desktop/person/vnpy`
- 执行脚本：`examples/portfolio_backtesting/run_qmt_roll_single_cap_grid.py`
- 初始资金：`200000`
- 当前固定基线：
  - `sp.SHFE` 在品种池中
  - `max_concurrent_positions = 8`
  - `risk_ratio_of_total_assets = 0.045`
  - `risk_ratio_open_interest_surge = 0.06`
  - `risk_ratio_volume_open_interest_surge = 0.06`
  - `risk_ratio_open_interest_decline = 0.025`
  - `100 万` sizing 资金上限保持开启
- 本轮使用：
  - `save_artifacts = False`
  - 输出汇总文件：`backtest_outputs/qmt_roll_single_cap_grid_summary.csv`

## 新增的回测结果

- `single_cap = 0.40`
  - 期末权益 `2,844,565`
  - 总收益 `1322.28%`
  - 最大回撤 `-35.27%`
  - Sharpe `1.1288`
  - 收益回撤比 `3.7972`
  - 总滑点 `334,560`
  - 总交易次数 `1238`
  - 胜率 `41.68%`
- `single_cap = 0.50`
  - 期末权益 `2,844,745`
  - 总收益 `1322.37%`
  - 最大回撤 `-36.96%`
  - Sharpe `1.0748`
  - 收益回撤比 `3.6690`
  - 总滑点 `339,840`
  - 总交易次数 `1222`
  - 胜率 `41.89%`
- `single_cap = 0.60`
  - 期末权益 `2,810,500`
  - 总收益 `1305.25%`
  - 最大回撤 `-37.36%`
  - Sharpe `1.0277`
  - 收益回撤比 `3.5533`
  - 总滑点 `342,290`
  - 总交易次数 `1214`
  - 胜率 `42.00%`
- `single_cap = 0.70`
  - 期末权益 `3,015,735`
  - 总收益 `1407.87%`
  - 最大回撤 `-35.71%`
  - Sharpe `1.0854`
  - 收益回撤比 `3.8166`
  - 总滑点 `347,080`
  - 总交易次数 `1214`
  - 胜率 `42.00%`
- `single_cap = 0.80`
  - 期末权益 `2,850,180`
  - 总收益 `1325.09%`
  - 最大回撤 `-37.61%`
  - Sharpe `1.0225`
  - 收益回撤比 `3.6168`
  - 总滑点 `343,710`
  - 总交易次数 `1200`
  - 胜率 `41.99%`

## 修改的回测结果

- 对比当前正式默认值 `single_cap = 0.70`：
  - `0.40`
    - 总收益：`1407.87% -> 1322.28%`
    - 最大回撤：`-35.71% -> -35.27%`
    - Sharpe：`1.0854 -> 1.1288`
  - `0.50`
    - 总收益：`1407.87% -> 1322.37%`
    - 最大回撤：`-35.71% -> -36.96%`
    - Sharpe：`1.0854 -> 1.0748`
  - `0.60`
    - 总收益：`1407.87% -> 1305.25%`
    - 最大回撤：`-35.71% -> -37.36%`
    - Sharpe：`1.0854 -> 1.0277`
  - `0.80`
    - 总收益：`1407.87% -> 1325.09%`
    - 最大回撤：`-35.71% -> -37.61%`
    - Sharpe：`1.0854 -> 1.0225`

## 删除的回测结果

- 无

## 快速结论

- 第一轮粗网格冠军仍然是 `single_cap = 0.70`
- 但 `0.40` 非常接近，且呈现出更“防守型”的特征：
  - 收益略低于 `0.70`
  - 回撤更小
  - Sharpe 更高
- `0.50 / 0.60 / 0.80` 都没有同时打赢 `0.70`
- 第二轮精细搜索建议聚焦：
  - `0.40 ~ 0.70`
  - 优先看 `0.40 / 0.45 / 0.50 / 0.55 / 0.60 / 0.65 / 0.70`
- 当前判断：
  - 若偏收益最大化，保留 `0.70`
  - 若偏穿越周期和稳健性，`0.40` 很值得进入下一轮精细对比

# 2026-04-23 15:58 主回测接入七条起始周期分支与总复盘图净值曲线

## 版本改动

- 改动时间点：`2026-04-23 15:58`
- 修改的文件：
  - `examples/portfolio_backtesting/run_qmt_roll_backtest.py`
  - `examples/portfolio_backtesting/run_qmt_alignment_backtest.py`
  - `examples/portfolio_backtesting/run_qmt_roll_period_sweep.py`
- 改动内容：
  - 在主回测入口中新增 7 条“起始年 -> 2026 年 4 月”的分支回测联动执行
  - 主回测正式导出时，自动同时生成：
    - 分支统计汇总 CSV
    - 分支净值曲线 CSV
  - 在 `qmt_roll_professional_dashboard.html` 中新增一行折线图：
    - “多起始周期净值曲线”
    - 7 条分支曲线各自从起点归一化到 `1.0`
  - 将独立的 `run_qmt_roll_period_sweep.py` 同步为与主回测一致的 7 条起始周期口径

## 参数变化说明

- 新增的参数：
  - 无新增策略参数
- 修改的参数：
  - 无修改交易参数，本次主要是增强主回测导出能力
- 删除的参数：
  - 无

## 回测参数

- 解释器：`/Users/bytedance/Desktop/person/vnpy/.py311/bin/python`
- `PYTHONPATH=/Users/bytedance/Desktop/person/vnpy`
- 主回测入口：`examples/portfolio_backtesting/run_qmt_roll_backtest.py`
- 当前正式默认基线：
  - `sp.SHFE` 在品种池中
  - `max_concurrent_positions = 8`
  - `max_single_trade_capital_usage_ratio = 0.70`
  - `risk_ratio_of_total_assets = 0.045`
  - `risk_ratio_open_interest_surge = 0.06`
  - `risk_ratio_volume_open_interest_surge = 0.06`
  - `risk_ratio_open_interest_decline = 0.025`
- 本次新增的 7 条分支区间：
  - `2020-01-01 -> 2026-04-30`
  - `2021-01-01 -> 2026-04-30`
  - `2022-01-01 -> 2026-04-30`
  - `2023-01-01 -> 2026-04-30`
  - `2024-01-01 -> 2026-04-30`
  - `2025-01-01 -> 2026-04-30`
  - `2026-01-01 -> 2026-04-30`

## 新增的回测结果

- 主回测结果：
  - 期末权益 `3,015,735`
  - 总收益 `1407.87%`
  - 最大回撤 `-35.71%`
  - Sharpe `1.0854`
  - 收益回撤比 `3.8166`
  - 总滑点 `347,080`
  - 总交易次数 `1214`
- 7 条起始周期分支结果：
  - `20年开始`
    - 期末权益 `3,015,735`
    - 总收益 `1407.87%`
    - 最大回撤 `-35.71%`
    - Sharpe `1.0854`
  - `21年开始`
    - 期末权益 `2,347,810`
    - 总收益 `1073.91%`
    - 最大回撤 `-47.14%`
    - Sharpe `0.8687`
  - `22年开始`
    - 期末权益 `361,405`
    - 总收益 `80.70%`
    - 最大回撤 `-65.47%`
    - Sharpe `0.1737`
  - `23年开始`
    - 期末权益 `178,105`
    - 总收益 `-10.95%`
    - 最大回撤 `-56.67%`
    - Sharpe `-0.0895`
  - `24年开始`
    - 期末权益 `209,960`
    - 总收益 `4.98%`
    - 最大回撤 `-38.59%`
    - Sharpe `0.0608`
  - `25年开始`
    - 期末权益 `298,675`
    - 总收益 `49.34%`
    - 最大回撤 `-47.90%`
    - Sharpe `0.4736`
  - `26年开始`
    - 期末权益 `94,660`
    - 总收益 `-52.67%`
    - 最大回撤 `-57.83%`
    - Sharpe `-3.6730`
- 新增产物：
  - `backtest_outputs/qmt_roll_period_sweep_summary.csv`
  - `backtest_outputs/qmt_roll_period_sweep_equity_curves.csv`
  - 更新后的 `backtest_outputs/qmt_roll_professional_dashboard.html`

## 修改的回测结果

- 主回测正式结果未被本次功能增强改变：
  - 仍为 `3,015,735 / 1407.87% / -35.71% / Sharpe 1.0854`
- 修改的是：
  - 主回测现在会自动联动跑 7 条分支
  - 总复盘图新增“多起始周期净值曲线”子图

## 删除的回测结果

- 无

## 快速结论

- 主回测已优化为“一次运行，主结果 + 7 条起始周期分支 + 总复盘图”同时产出
- 现在可以非常直观看到阶段敏感性：
  - `2020/2021` 起始仍然较强
  - `2022` 起始后策略显著变弱
  - `2023` 起始为负收益
  - `2026` 单年到 4 月表现最差
- 这说明总样本很强，但近三年尤其 `2022+` 的路径稳定性仍然是核心优化方向

# 2026-04-23 16:12 离线 AI 打分器训练样本结构与特征提取脚本

## 版本改动

- 改动时间点：`2026-04-23 16:12`
- 新增的文件：
  - `examples/portfolio_backtesting/build_qmt_roll_ai_position_training_samples.py`
- 改动内容：
  - 新增“离线 AI 打分器”训练样本构造脚本
  - 复用现有：
    - `qmt_roll_entry_risk_diagnostics_2020_2026_04.csv`
    - `qmt_roll_trades_2020_2026_04.csv`
    - `downloaded_futures/tqsdk_daily_2010_2026_04`
  - 将每笔实际开仓交易整理为一行训练样本
  - 自动补齐：
    - 规则上下文特征
    - 市场结构特征
    - 收益/回撤/顺逆行标签
    - 可直接用于分类或回归训练的标签字段

## 参数变化说明

- 新增的参数：
  - 无新增策略参数
- 修改的参数：
  - 无
- 删除的参数：
  - 无

## 数据构造口径

- 样本定义：
  - 每一行对应一笔规则策略已触发且实际成交的 `Open` 开仓交易
- 样本主键：
  - `sample_id = entry_trade_id`
- 训练标签建议：
  - 主回归标签：`label_quality_score`
  - 备选回归标签：
    - `label_realized_r_multiple`
    - `label_forward_10d_return_pct`
    - `label_forward_20d_return_pct`
  - 分类标签：
    - `label_size_bucket = small / normal / large`

## 新增的数据产物

- 样本表：
  - `backtest_outputs/qmt_roll_ai_position_training_samples.csv`
- schema：
  - `backtest_outputs/qmt_roll_ai_position_training_schema.json`
- 当前样本量：
  - `534` 行

## 回测结果

- 本次不涉及新增回测，仅进行训练样本构造与脚本验证

## 快速结论

- 当前已经具备了做“离线 AI 打分器”的第一阶段数据基础
- 下一步可以直接在这份样本表上做：
  - `LightGBM/XGBoost` 回归 `label_quality_score`
  - 或三分类预测 `label_size_bucket`
- 后续若要增强效果，优先继续补：
  - 跨品种联动特征
  - 更长周期环境特征
  - 连续时间窗口归一化特征

# 2026-04-23 17:12 离线 AI 打分器 baseline 训练脚本与首轮训练结果

## 版本改动

- 改动时间点：`2026-04-23 17:12`
- 新增的文件：
  - `examples/portfolio_backtesting/train_qmt_roll_ai_position_scorer.py`
- 修改的文件：
  - `examples/portfolio_backtesting/train_qmt_roll_ai_position_scorer.py`
- 改动内容：
  - 新增基于 `LightGBMRegressor` 的 baseline 训练脚本
  - 增加时间切分训练流程：
    - `train`: `2023-01-01` 之前
    - `valid`: `2023-01-01 ~ 2023-12-31`
    - `test`: `2024-01-01` 之后
  - 自动导出模型、summary、feature importance、predictions、bucket analysis
  - 增加 `verbosity=-1`，压掉 LightGBM 的大量 warning 日志，便于后续复验

## 参数变化说明

- 新增的参数：
  - 无新增策略参数
- 修改的参数：
  - 无策略参数修改
  - 模型训练参数中新增 `verbosity = -1`
- 删除的参数：
  - 无

## 训练配置

- 训练样本：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_position_training_samples.csv`
- 样本量：
  - 总样本 `534`
  - `train = 237`
  - `valid = 96`
  - `test = 201`
- 目标列：
  - `label_quality_score`
- 分类特征：
  - `product_symbol`
  - `exchange`
  - `direction`
  - `signal`
  - `risk_mode`
  - `layer_kind`
  - `sizing_method`
- 主要模型参数：
  - `n_estimators = 400`
  - `learning_rate = 0.03`
  - `num_leaves = 31`
  - `subsample = 0.9`
  - `colsample_bytree = 0.8`
  - `min_child_samples = 15`
  - `reg_lambda = 1.0`
  - `random_state = 42`

## 新增的数据产物

- 模型：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_position_scorer.joblib`
- 训练摘要：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_position_scorer_summary.json`
- 特征重要度：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_position_scorer_feature_importance.csv`
- 逐样本预测：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_position_scorer_predictions.csv`
- 测试集分桶分析：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_position_scorer_bucket_analysis.csv`

## 新增的训练结果

- `train`
  - `RMSE = 2.9716`
  - `MAE = 0.8026`
  - `R2 = 0.7580`
  - `Spearman = 0.9292`
- `valid`
  - `RMSE = 3.5491`
  - `MAE = 2.2759`
  - `R2 = -1.8617`
  - `Spearman = 0.1539`
- `test`
  - `RMSE = 5.7704`
  - `MAE = 3.7559`
  - `R2 = -0.5856`
  - `Spearman = -0.0386`

## 测试集分桶结果

- `low_score`
  - 样本数 `67`
  - 平均真实质量分 `1.7054`
  - 平均实现 `R` 倍数 `0.7729`
  - 胜率 `52.24%`
- `mid_score`
  - 样本数 `67`
  - 平均真实质量分 `0.8118`
  - 平均实现 `R` 倍数 `0.1368`
  - 胜率 `41.79%`
- `high_score`
  - 样本数 `67`
  - 平均真实质量分 `2.2535`
  - 平均实现 `R` 倍数 `0.3428`
  - 胜率 `35.82%`

## 主要特征重要度

- Top 10：
  - `stop_distance`
  - `feature_close_vs_prev20_high_pct`
  - `feature_ma5_ma10_gap_pct`
  - `feature_mid_term_momentum_signed`
  - `feature_ma10_ma20_gap_pct`
  - `actual_margin_amount`
  - `feature_lower_wick_pct`
  - `feature_vol60`
  - `feature_ma20_ma40_gap_pct`
  - `entry_volume`

## 回测结果变化说明

- 新增的回测结果：
  - 无，本次仅新增离线训练脚本与训练产物
- 修改的回测结果：
  - 无
- 删除的回测结果：
  - 无

## 快速结论

- 当前 baseline 训练链路已经完整跑通，产物可直接用于后续 overlay A/B
- 训练集拟合较强，但 `valid/test` 的 `R2` 为负，样本外泛化明显不足
- 测试集分桶没有形成“高分组显著优于低分组”的稳定排序关系，暂时不适合直接接入实盘仓位放大
- 当前结果更适合作为“数据链路已打通”的里程碑，而不是“AI 仓位控制已可上线”的结论
- 下一步应优先补强：
  - 标签口径
  - 横截面相对强弱特征
  - 市场环境特征
  - 更严格的 walk-forward 样本外验证

# 2026-04-23 17:36 离线 AI 打分器第二版最小可验证方案

## 版本改动

- 改动时间点：`2026-04-23 17:36`
- 修改的文件：
  - `examples/portfolio_backtesting/build_qmt_roll_ai_position_training_samples.py`
  - `examples/portfolio_backtesting/train_qmt_roll_ai_position_scorer.py`
- 改动内容：
  - 新增第二版平滑标签 `label_quality_score_v2`
  - 新增第二版分类桶 `label_size_bucket_v2`
  - 将远期收益按止损距离换算为 `R multiple` 标签：
    - `label_forward_3d_r_multiple`
    - `label_forward_5d_r_multiple`
    - `label_forward_10d_r_multiple`
    - `label_forward_20d_r_multiple`
  - 新增一组更抗周期漂移的归一化特征：
    - 波动/振幅 zscore
    - 20 日收益 zscore
    - 成交量比值 zscore
    - OI 变化百分比及 zscore
    - 20/60 日区间位置
    - 风险/保证金/单笔资金占权益比例
  - 训练侧改为：
    - 默认目标列使用 `label_quality_score_v2`
    - 输出单独保存为 `_v2` 后缀，避免覆盖上一版 baseline 产物
    - 降低模型复杂度，减少过拟合对验证判断的干扰

## 参数变化说明

- 新增的参数：
  - 无新增策略参数
- 修改的参数：
  - 训练目标：`label_quality_score -> label_quality_score_v2`
  - 模型参数调整为更保守口径：
    - `n_estimators = 240`
    - `learning_rate = 0.04`
    - `num_leaves = 15`
    - `max_depth = 4`
    - `subsample = 0.8`
    - `colsample_bytree = 0.7`
    - `min_child_samples = 30`
    - `reg_alpha = 1.0`
    - `reg_lambda = 5.0`
- 删除的参数：
  - 无

## 数据与训练配置

- 训练样本：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_position_training_samples.csv`
- 样本量：
  - 总样本 `534`
  - `train = 237`
  - `valid = 96`
  - `test = 201`
- 第二版主目标：
  - `label_quality_score_v2`
- 第二版输出产物：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_position_scorer_v2.joblib`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_position_scorer_summary_v2.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_position_scorer_feature_importance_v2.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_position_scorer_predictions_v2.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_position_scorer_bucket_analysis_v2.csv`

## 新增的训练结果

- `train`
  - `RMSE = 0.9621`
  - `MAE = 0.7807`
  - `R2 = 0.7632`
  - `Spearman = 0.9237`
- `valid`
  - `RMSE = 1.9797`
  - `MAE = 1.5487`
  - `R2 = -0.2273`
  - `Spearman = -0.1178`
- `test`
  - `RMSE = 2.2839`
  - `MAE = 1.8677`
  - `R2 = -0.1056`
  - `Spearman = 0.0949`

## 与上一版 baseline 对比

- 改善的部分：
  - `test R2`: `-0.5856 -> -0.1056`
  - `test Spearman`: `-0.0386 -> 0.0949`
  - `test MAE`: `3.7559 -> 1.8677`
- 仍然不足的部分：
  - `valid Spearman`: `0.1539 -> -0.1178`
  - `valid R2` 仍为负值
  - 测试集分桶还没有形成单调稳定的高分优先关系

## 测试集分桶结果

- `low_score`
  - 样本数 `67`
  - 平均 `v2` 目标分 `0.2058`
  - 平均旧版质量分 `1.0357`
  - 平均实现 `R` 倍数 `0.0670`
  - 胜率 `41.79%`
- `mid_score`
  - 样本数 `67`
  - 平均 `v2` 目标分 `0.9056`
  - 平均旧版质量分 `1.6523`
  - 平均实现 `R` 倍数 `0.8443`
  - 胜率 `46.27%`
- `high_score`
  - 样本数 `67`
  - 平均 `v2` 目标分 `0.6243`
  - 平均旧版质量分 `2.0827`
  - 平均实现 `R` 倍数 `0.3412`
  - 胜率 `41.79%`

## 主要特征重要度

- Top 10：
  - `feature_range_pct_zscore_120`
  - `feature_vol60`
  - `feature_close_vs_prev20_low_pct`
  - `feature_vol20`
  - `feature_ret_20d_zscore_120`
  - `feature_ma20_ma40_gap_pct`
  - `feature_allowed_capital_to_equity`
  - `feature_actual_margin_to_equity`
  - `product_symbol`
  - `feature_close_position_60d`

## 回测结果变化说明

- 新增的回测结果：
  - 无，本次仅新增第二版离线训练方案与训练产物
- 修改的回测结果：
  - 无
- 删除的回测结果：
  - 无

## 快速结论

- 第二版最小方案已经验证完毕，方向上有一定改善：
  - `test` 样本外相关性从负值回到轻微正值
  - `test` 误差明显收敛
- 但这版仍然不够稳健：
  - `valid` 集表现转弱
  - 分桶没有形成稳定单调性
- 因此当前判断应保持克制：
  - 可以确认“平滑标签 + 归一化特征”方向值得保留
  - 但还不能据此把 AI 仓位控制接回正式回测或实盘逻辑
- 下一步更值得做的不是继续堆模型复杂度，而是：
  - 增加横截面相对强弱特征
  - 把标签改成更接近“同日候选排序”的口径
  - 用严格 walk-forward 方式做分段样本外检验

# 2026-04-23 17:49 离线 AI 打分器第三版横截面相对强弱方案

## 版本改动

- 改动时间点：`2026-04-23 17:49`
- 修改的文件：
  - `examples/portfolio_backtesting/build_qmt_roll_ai_position_training_samples.py`
  - `examples/portfolio_backtesting/train_qmt_roll_ai_position_scorer.py`
- 改动内容：
  - 新增同日横截面特征：
    - 对同日实际触发的候选开仓样本，计算多项特征的同日相对 rank
    - 输出 `*_cs_rank_pct_1d` 与 `*_cs_rank_centered_1d`
  - 新增第三版横截面标签：
    - `label_quality_score_v2_rank_pct_1d`
    - `label_quality_score_v2_rank_centered_1d`
    - `label_quality_score_v3`
    - `label_quality_score_v3_bucket`
  - 训练侧改为专注横截面任务：
    - 仅保留 `label_quality_score_v3_is_cross_sectional = 1` 的样本参与训练与评估
    - 目标列改为 `label_quality_score_v2_rank_centered_1d`
    - 特征集缩到“横截面 rank 特征 + 少量风险上下文”
  - 新增横截面专项评估指标：
    - `mean_group_spearman`
    - `top1_hit_rate`
    - `top1_target_lift`

## 参数变化说明

- 新增的参数：
  - 无新增策略参数
- 修改的参数：
  - 训练目标：`label_quality_score_v2 -> label_quality_score_v2_rank_centered_1d`
  - 训练样本范围：仅使用同日至少 `2` 个候选的横截面样本
  - 特征范围：仅保留同日相对 rank 特征和少量风险上下文，不再混入大批绝对口径特征
- 删除的参数：
  - 无

## 数据与训练配置

- 全量样本：
  - `534`
- 具备横截面意义的样本：
  - `218`
- 同日至少 `2` 个候选的交易日：
  - `96`
- 训练集 / 验证集 / 测试集横截面样本：
  - `train = 80`
  - `valid = 39`
  - `test = 99`
- 第三版输出产物：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_position_scorer_v3.joblib`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_position_scorer_summary_v3.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_position_scorer_feature_importance_v3.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_position_scorer_predictions_v3.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_position_scorer_bucket_analysis_v3.csv`

## 新增的训练结果

- 常规回归指标
  - `train`
    - `RMSE = 0.8238`
    - `MAE = 0.7557`
    - `R2 = 0.2268`
    - `Spearman = 0.5215`
  - `valid`
    - `RMSE = 0.9462`
    - `MAE = 0.8832`
    - `R2 = 0.0301`
    - `Spearman = 0.1399`
  - `test`
    - `RMSE = 0.9904`
    - `MAE = 0.9126`
    - `R2 = -0.1264`
    - `Spearman = -0.0686`

## 横截面专项评估

- `train`
  - 交易日组数 `35`
  - `mean_group_spearman = 0.5429`
  - `top1_hit_rate = 77.14%`
  - `top1_target_lift = 0.6095`
- `valid`
  - 交易日组数 `18`
  - `mean_group_spearman = 0.1111`
  - `top1_hit_rate = 50.00%`
  - `top1_target_lift = 0.0556`
- `test`
  - 交易日组数 `43`
  - `mean_group_spearman = -0.1558`
  - `top1_hit_rate = 37.21%`
  - `top1_target_lift = -0.2093`

## 测试集分桶结果

- `low_score`
  - 样本数 `33`
  - 平均横截面目标分 `0.0202`
  - 平均 `v2` 质量分 `1.1067`
  - 胜率 `51.52%`
- `mid_score`
  - 样本数 `33`
  - 平均横截面目标分 `0.1010`
  - 平均 `v2` 质量分 `0.6269`
  - 胜率 `45.45%`
- `high_score`
  - 样本数 `33`
  - 平均横截面目标分 `-0.1212`
  - 平均 `v2` 质量分 `0.6883`
  - 胜率 `42.42%`

## 主要特征重要度

- Top 10：
  - `feature_volume_ratio_2v2_cs_rank_centered_1d`
  - `feature_oi_delta_1d_pct_zscore_120_cs_rank_centered_1d`
  - `feature_close_vs_prev20_low_pct_cs_rank_centered_1d`
  - `feature_actual_margin_to_equity`
  - `feature_range_pct_zscore_120_cs_rank_centered_1d`
  - `exchange`
  - `feature_ret_signed_5d_cs_rank_centered_1d`
  - `feature_stop_distance_pct`
  - `feature_mid_term_momentum_signed_cs_rank_centered_1d`

## 回测结果变化说明

- 新增的回测结果：
  - 无，本次仅新增第三版离线横截面训练方案与训练产物
- 修改的回测结果：
  - 无
- 删除的回测结果：
  - 无

## 快速结论

- 第三版已经完成最小闭环验证，但结果不支持继续沿这条线直接接回测：
  - `valid` 横截面结果只有轻微正向
  - `test` 横截面排序转为负值
  - `top1_hit_rate` 在测试集只有 `37.21%`
- 这说明当前“同日实际触发开仓样本”横截面密度太稀：
  - 大多数交易日只有 `1` 个候选
  - 真正可学习的横截面样本只有 `218` 条
- 当前可以保留的收获是：
  - 量能/OI/区间位置这类相对 rank 特征方向上有信息
  - 但现有样本生成口径还不足以支撑稳定的横截面学习
- 因此更合理的下一步不是继续调当前模型，而是重构数据层：
  - 把“未成交但满足初筛条件的候选”也纳入同日候选集
  - 扩大每个交易日的横截面宽度
  - 再做真正的候选排序模型

# 2026-04-23 18:12 第四版候选集快照数据结构与导出链路

## 版本改动

- 改动时间点：`2026-04-23 18:12`
- 修改的文件：
  - `examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
  - `examples/portfolio_backtesting/run_qmt_alignment_backtest.py`
- 改动内容：
  - 新增 `entry_candidate_snapshots` 候选集快照容器
  - 在 `QmtRollPortfolioStrategy.on_bars()` 中，对所有已经通过 `_generate_signal` 与 `_passes_entry_filters` 的基础开仓候选进行结构化记录
  - 将未成交但满足初筛条件的候选一并记录，补齐：
    - `candidate_status = opened / skipped`
    - `skip_reason`
  - 新增导出文件：
    - `qmt_roll_entry_candidate_snapshots_2020_2026_04.csv`
    - `qmt_roll_entry_candidate_snapshots_schema.json`
  - 当前第一阶段只覆盖：
    - `entry_context = flat_entry`
  - 当前暂不纳入：
    - 加仓候选
    - 换月重开候选

## 参数变化说明

- 新增的参数：
  - 无新增策略参数
- 修改的参数：
  - 无
- 删除的参数：
  - 无

## 候选集快照结构定义

- 主键字段：
  - `candidate_index`
  - `datetime`
  - `product_vt_symbol`
  - `contract_vt_symbol`
  - `signal`
- 核心状态字段：
  - `entry_context`
  - `candidate_status`
  - `skip_reason`
  - `is_opened`
- 风险与资金字段：
  - `estimated_equity`
  - `total_margin_in_use_before`
  - `allowed_capital`
  - `single_trade_capital_limit`
  - `free_capital`
  - `limited_balance`
  - `risk_ratio`
  - `risk_multiplier`
  - `target_risk_amount`
- sizing 字段：
  - `stop_price`
  - `stop_distance`
  - `risk_per_contract`
  - `margin_per_contract`
  - `contracts_by_risk`
  - `contracts_by_margin`
  - `contracts_by_single_trade_cap`
  - `selected_volume`
- 信号上下文字段：
  - `direction`
  - `risk_mode`
  - `bullish_alignment`
  - `bearish_alignment`
  - `breakout`
  - `rsi_value`
  - `ma_mid_value`
  - `ma_long_value`
  - `ma_mid_prev_value`
  - `ma_long_prev_value`
- 并发位上下文字段：
  - `active_positions_before`
  - `max_concurrent_positions`
  - `remaining_position_slots`

## 新增的数据产物

- 候选集快照 CSV：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_entry_candidate_snapshots_2020_2026_04.csv`
- 候选集 schema：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_entry_candidate_snapshots_schema.json`

## 候选集快照统计

- 总候选数：
  - `999`
- 实际进入开仓流程：
  - `opened = 562`
- 通过初筛但最终未成交：
  - `skipped = 437`
- 未成交原因分布：
  - `short_signal_rejected = 352`
  - `sizing_zero_volume = 74`
  - `concurrent_limit = 11`
- 当前候选上下文分布：
  - `flat_entry = 999`

## 回测参数

- 验证脚本：
  - `run_qmt_roll_backtest.run_backtest(...)`
- 初始资金：
  - `200000`
- 本次验证口径：
  - `save_artifacts = True`
  - `include_start_year_sweep = False`
- 说明：
  - 本次关闭多起始周期 sweep，仅用于更快验证候选集快照导出链路，不改策略设计方向

## 新增的回测结果

- Start Date: `2020-01-02`
- End Date: `2026-04-21`
- 期末权益 `3,015,735`
- 总收益 `1407.87%`
- 最大回撤 `-35.71%`
- Sharpe `1.0854`
- 总滑点 `347,080`
- 总交易次数 `1214`
- 胜率 `42.00%`
- 胜场 / 完整回合 `260 / 619`

## 修改的回测结果

- 本次主要新增候选集快照导出链路，并同步刷新一轮主回测导出产物

## 删除的回测结果

- 无

## 快速结论

- 第四版第一阶段已经把“已开仓样本”扩展为“候选集快照样本”
- 当前最大的新增价值不是模型结果，而是数据宽度：
  - 已经拿到 `437` 条通过初筛但未成交的候选
  - 这些样本可以显著扩大同日横截面宽度
- 当前第一阶段仍然偏保守：
  - 只记录 `flat_entry`
  - 尚未把加仓和换月重开并入候选池
- 下一步更合理的是：
  - 基于这份候选集快照，构建第四版训练样本
  - 给每个候选补齐“是否最终被选中”“若未选中是为何被拦截”的监督标签
  - 再做真正的候选排序/筛选模型

# 2026-04-23 18:47 第四版第二阶段候选训练样本表

## 版本改动

- 改动时间点：`2026-04-23 18:47`
- 新增的文件：
  - `examples/portfolio_backtesting/build_qmt_roll_ai_candidate_training_samples.py`
- 改动内容：
  - 将 `qmt_roll_entry_candidate_snapshots_2020_2026_04.csv` 转为候选训练样本表
  - 为每个候选补齐两层标签：
    - 规则选择标签：
      - `label_is_selected`
      - `label_selection_status`
      - `label_rejection_reason`
      - `label_rejection_stage`
    - 市场结果标签：
      - `label_candidate_forward_*`
      - `label_candidate_20d_mfe_r`
      - `label_candidate_20d_mae_r`
      - `label_candidate_quality_score_v2`
  - 对已被选中的候选，继续补齐真实成交标签：
    - `label_realized_r_multiple`
    - `label_quality_score`
    - `label_quality_score_v2`
    - 以及完整的 exit / holding / MFE / MAE 标签
  - 新增候选样本 schema：
    - `qmt_roll_ai_candidate_training_schema.json`

## 参数变化说明

- 新增的参数：
  - 无新增策略参数
- 修改的参数：
  - 无
- 删除的参数：
  - 无

## 样本映射规则

- 候选主键：
  - `datetime`
  - `product_vt_symbol`
  - `contract_vt_symbol`
  - `direction`
  - `signal`
  - `selected_volume`
- 选择标签规则：
  - `candidate_status = opened -> label_is_selected = 1`
  - `candidate_status = skipped -> label_is_selected = 0`
- 拦截原因标签：
  - `short_signal_rejected`
  - `sizing_zero_volume`
  - `concurrent_limit`
- 已选中候选的真实成交标签补齐方式：
  - 先匹配 `entry_risk_diagnostics` 的 `base` 开仓
  - 再通过 `trade_link_map` 关联对应 exit trades

## 新增的数据产物

- 候选训练样本表：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_training_samples.csv`
- 候选训练样本 schema：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_training_schema.json`

## 样本覆盖统计

- 候选快照原始总数：
  - `999`
- 原始已选中候选：
  - `562`
- 原始未选中候选：
  - `437`
- 最终成功转为训练样本：
  - `883`
- 最终训练样本中的已选中 / 未选中：
  - `497 / 386`
- 已选中候选与真实成交链路匹配成功：
  - `497`
- 已选中候选与真实成交链路匹配失败：
  - `0`
- 过滤原因：
  - `missing_bar_rows = 116`
  - `feature_unavailable_rows = 0`
  - `market_label_unavailable_rows = 0`

## 标签分布

- 规则选择标签：
  - `selected = 497`
  - `skipped = 386`
- 拦截原因分布：
  - `short_signal_rejected = 314`
  - `sizing_zero_volume = 61`
  - `concurrent_limit = 11`
- 横截面宽度：
  - 至少有 `2` 个候选的交易日 `194`
  - 这些交易日上的样本数 `447`

## 数据结构结论

- 当前这份候选训练样本表已经具备三类用途：
  - 模仿当前规则链路的二分类：
    - 是否被选中
  - 多分类：
    - 被哪一层拦截
  - 排序/回归：
    - 候选统一前瞻质量分
- 与之前只用已成交开仓样本相比，这一步的价值更大：
  - 样本从“只有正例”扩展为“正例 + 负例 + 落选原因”
  - 横截面天数和横截面行数显著增加

## 回测结果变化说明

- 新增的回测结果：
  - 无，本次主要新增候选训练样本数据集与 schema
- 修改的回测结果：
  - 无
- 删除的回测结果：
  - 无

## 快速结论

- 第四版第二阶段已经完成，候选快照成功转成可训练的数据表
- 当前最关键的验证结果是：
  - 已选中候选与真实成交标签匹配 `100%` 成功
  - 未选中候选也具备统一口径的市场前瞻标签
- 当前仍然存在的限制：
  - 有 `116` 条候选因为本地历史行情不足，暂时无法生成特征
  - 当前样本仍只覆盖 `flat_entry`
- 下一步最值得做的是：
  - 基于这份候选训练样本表，先做一个第四版第一轮候选选择分类器
  - 再做一个候选质量排序器
  - 比较 imitation 和 ranking 哪条线更稳

# 2026-04-23 18:59 第四版第三阶段 label_is_selected 二分类 baseline

## 版本改动

- 改动时间点：`2026-04-23 18:59`
- 新增的文件：
  - `examples/portfolio_backtesting/train_qmt_roll_ai_candidate_selector.py`
- 修改的文件：
  - `examples/portfolio_backtesting/build_qmt_roll_ai_candidate_training_samples.py`
- 改动内容：
  - 新增第四版第三阶段 baseline 训练脚本，目标列为 `label_is_selected`
  - 训练脚本使用时间切分：
    - `train`: `2023-01-01` 之前
    - `valid`: `2023-01-01 ~ 2023-12-31`
    - `test`: `2024-01-01` 之后
  - 导出分类模型、summary、feature importance、predictions、bucket analysis
  - 新增横截面专项指标：
    - `top1_hit_rate`
    - `top1_selected_lift`
    - `top1_quality_lift`
  - 修复候选训练样本中的未来收益标签极端值问题：
    - 当 `stop_distance <= 0` 时，改用 `risk_per_contract / contract_size` 作为 `effective_stop_distance`
    - 避免 `R multiple` 因分母过小而失真

## 参数变化说明

- 新增的参数：
  - 无新增策略参数
- 修改的参数：
  - baseline 二分类模型参数：
    - `n_estimators = 220`
    - `learning_rate = 0.04`
    - `num_leaves = 15`
    - `max_depth = 4`
    - `subsample = 0.8`
    - `colsample_bytree = 0.7`
    - `min_child_samples = 30`
    - `reg_alpha = 1.0`
    - `reg_lambda = 5.0`
- 删除的参数：
  - 无

## 新增的数据产物

- 模型：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_selector_selector_v1.joblib`
- 训练摘要：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_selector_summary_selector_v1.json`
- 特征重要度：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_selector_feature_importance_selector_v1.csv`
- 逐样本预测：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_selector_predictions_selector_v1.csv`
- 测试集分桶分析：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_selector_bucket_analysis_selector_v1.csv`

## 样本配置

- 数据集：
  - `qmt_roll_ai_candidate_training_samples.csv`
- 总样本：
  - `883`
- `train / valid / test`：
  - `359 / 169 / 355`
- 标签：
  - `label_is_selected`

## 新增的训练结果

- 常规分类指标
  - `train`
    - `ROC AUC = 0.9999`
    - `LogLoss = 0.0482`
    - `Accuracy = 98.89%`
    - `F1 = 0.9909`
  - `valid`
    - `ROC AUC = 0.9999`
    - `LogLoss = 0.0630`
    - `Accuracy = 98.22%`
    - `F1 = 0.9841`
  - `test`
    - `ROC AUC = 0.9997`
    - `LogLoss = 0.0584`
    - `Accuracy = 99.44%`
    - `F1 = 0.9947`

## 横截面专项结果

- `train`
  - `top1_hit_rate = 53.52%`
  - `top1_selected_lift = 0.2042`
  - `top1_quality_lift = 0.2209`
- `valid`
  - `top1_hit_rate = 35.90%`
  - `top1_selected_lift = 0.2372`
  - `top1_quality_lift = -0.1361`
- `test`
  - `top1_hit_rate = 36.90%`
  - `top1_selected_lift = 0.1958`
  - `top1_quality_lift = -0.4119`

## 主要特征重要度

- Top 10：
  - `signal`
  - `contracts_by_risk`
  - `feature_ma5_ma10_gap_pct`
  - `contracts_by_margin`
  - `feature_trend_ma20_gap_pct`
  - `feature_trend_ma10_gap_pct`
  - `active_positions_before`
  - `feature_target_risk_to_equity`
  - `direction`
  - `feature_ma10_ma20_gap_pct`

## 结果解释

- 这个 baseline 的本质不是“学会未来收益”，而是“高度复现当前规则是否会选中候选”
- 指标之所以异常高，核心原因是当前目标本身包含大量强规则结构：
  - `signal`
  - `contracts_by_risk`
  - `contracts_by_margin`
  - `active_positions_before`
- 这说明模型已经能很好蒸馏当前规则链路，但还不能说明它有独立的 alpha 选择能力
- 更关键的是横截面质量指标：
  - `test top1_selected_lift` 为正，说明模型确实更容易挑出“当前规则会选中的候选”
  - 但 `test top1_quality_lift` 为负，说明它挑出的最高概率候选，并没有比同日平均候选更高的未来质量

## 回测结果变化说明

- 新增的回测结果：
  - 无，本次仅新增候选选择二分类 baseline 训练结果
- 修改的回测结果：
  - 无
- 删除的回测结果：
  - 无

## 快速结论

- 第四版第三阶段 baseline 已完成，代码链路与训练产物都已落地
- 当前结论要非常克制：
  - 这个模型非常适合做“规则蒸馏器”
  - 不适合直接当作“未来更优候选选择器”
- 这一步仍然有价值，因为它验证了两件事：
  - 候选训练样本表质量足够高，模型能稳定学习当前规则边界
  - 未来质量和当前规则选择不是一回事，下一步不能继续只做 imitation
- 更合理的下一步是：
  - 保留这个 selector 作为 imitation baseline
  - 继续做第四版第四阶段的 ranking baseline
  - 用 `label_candidate_quality_score_v2_rank_centered_1d` 直接学“同日相对质量”

# 2026-04-23 19:03 第四版第四阶段 ranking baseline

## 版本改动

- 改动时间点：`2026-04-23 19:03`
- 新增的文件：
  - `examples/portfolio_backtesting/train_qmt_roll_ai_candidate_ranker.py`
- 修改的文件：
  - `examples/portfolio_backtesting/train_qmt_roll_ai_candidate_ranker.py`
- 改动内容：
  - 新增第四版第四阶段 ranking baseline 训练脚本
  - 目标列使用：
    - `label_candidate_quality_score_v2_rank_centered_1d`
  - 训练时仅保留同日至少 `2` 个候选的样本，确保目标具有真实横截面含义
  - 评估重点放在组内排序：
    - `mean_group_spearman`
    - `top1_hit_rate`
    - `top1_target_lift`
    - `top1_quality_lift`
    - `top1_selected_lift`
  - 增加对常量组的保护，避免组内 `spearman` 计算触发 warning

## 参数变化说明

- 新增的参数：
  - 无新增策略参数
- 修改的参数：
  - ranking baseline 模型参数：
    - `n_estimators = 260`
    - `learning_rate = 0.04`
    - `num_leaves = 15`
    - `max_depth = 4`
    - `subsample = 0.8`
    - `colsample_bytree = 0.7`
    - `min_child_samples = 30`
    - `reg_alpha = 1.0`
    - `reg_lambda = 5.0`
- 删除的参数：
  - 无

## 样本配置

- 样本来源：
  - `qmt_roll_ai_candidate_training_samples.csv`
- 仅保留具备横截面意义的样本：
  - 总样本 `447`
- `train / valid / test`：
  - `162 / 87 / 198`
- 对应横截面交易日：
  - `71 / 39 / 84`

## 特征设计判断

- 本次刻意不再强调规则蒸馏特征，弱化或移除：
  - `active_positions_before`
  - `remaining_position_slots`
  - `contracts_by_risk`
  - `contracts_by_margin`
  - `contracts_by_single_trade_cap`
- 优先保留更接近未来质量的市场状态特征：
  - 趋势结构
  - 波动与振幅
  - OI 与量能变化
  - 区间位置
  - 风险归一化特征

## 新增的数据产物

- 模型：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_ranker_ranker_v1.joblib`
- 训练摘要：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_ranker_summary_ranker_v1.json`
- 特征重要度：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_ranker_feature_importance_ranker_v1.csv`
- 逐样本预测：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_ranker_predictions_ranker_v1.csv`
- 测试集分桶分析：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_ranker_bucket_analysis_ranker_v1.csv`

## 新增的训练结果

- 常规回归指标
  - `train`
    - `RMSE = 0.6066`
    - `MAE = 0.5587`
    - `R2 = 0.5829`
    - `Spearman = 0.8636`
  - `valid`
    - `RMSE = 0.9935`
    - `MAE = 0.9116`
    - `R2 = -0.0978`
    - `Spearman = 0.0255`
  - `test`
    - `RMSE = 0.9523`
    - `MAE = 0.8616`
    - `R2 = -0.0757`
    - `Spearman = 0.0858`

## 横截面专项结果

- `train`
  - `mean_group_spearman = 0.9803`
  - `top1_hit_rate = 97.18%`
  - `top1_quality_lift = 1.0814`
  - `top1_selected_lift = 0.0775`
- `valid`
  - `mean_group_spearman = 0.0641`
  - `top1_hit_rate = 48.72%`
  - `top1_quality_lift = 0.1989`
  - `top1_selected_lift = 0.1346`
- `test`
  - `mean_group_spearman = 0.0145`
  - `top1_hit_rate = 46.43%`
  - `top1_quality_lift = 0.0598`
  - `top1_selected_lift = 0.0411`

## 测试集分桶结果

- `low_score`
  - 样本数 `66`
  - 平均目标分 `-0.1061`
  - 平均候选质量分 `0.5103`
  - 选中率 `39.39%`
- `mid_score`
  - 样本数 `66`
  - 平均目标分 `0.0909`
  - 平均候选质量分 `0.9417`
  - 选中率 `60.61%`
- `high_score`
  - 样本数 `66`
  - 平均目标分 `0.0152`
  - 平均候选质量分 `0.9067`
  - 选中率 `75.76%`

## 主要特征重要度

- Top 10：
  - `feature_lower_wick_pct`
  - `exchange`
  - `feature_atr14_pct_zscore_120`
  - `feature_oi_delta_5d_pct`
  - `feature_close_position_60d`
  - `feature_oi_delta_1d_pct`
  - `feature_margin_per_contract_to_equity`
  - `feature_trend_ma20_gap_pct`
  - `feature_ma20_ma40_gap_pct`
  - `feature_vol20`

## 结果解释

- 这版和 `label_is_selected` 二分类 baseline 的本质区别在于：
  - 分类 baseline 学的是“当前规则会不会选”
  - ranking baseline 学的是“同日候选谁的未来质量更高”
- 从结果上看，这个方向比 imitation 更接近我们真正想要的目标：
  - `test top1_quality_lift` 已经转正
  - 特征重要度也开始更多落在市场状态，而不是规则门槛本身
- 但当前强度仍然偏弱：
  - `test mean_group_spearman` 仅 `0.0145`
  - `test top1_quality_lift` 只有 `0.0598`
  - 分桶结果没有形成很强的单调性
- 这说明：
  - 方向是对的
  - 但信号强度还不足以直接驱动仓位放大或替代当前规则

## 回测结果变化说明

- 新增的回测结果：
  - 无，本次仅新增 ranking baseline 训练结果
- 修改的回测结果：
  - 无
- 删除的回测结果：
  - 无

## 快速结论

- 第四版第四阶段已经完成，ranking baseline 已经跑通
- 当前应保持克制判断：
  - 这版比 `label_is_selected` baseline 更接近 alpha 排序器
  - 但样本外优势还很弱，只能算“略有正向”
- 当前最值得保留的收获：
  - 未来质量排序这条路比规则模仿更对
  - OI、波动、区间位置、影线结构这类特征开始体现信息量
- 下一步更合理的是：
  - 基于 ranking baseline 继续做特征层增强
  - 尤其补横截面相对特征与同日标准化特征
  - 而不是继续深挖 `label_is_selected`

# 2026-04-23 19:11 第五阶段横截面标准化特征增强版 ranking baseline

## 版本改动

- 改动时间点：`2026-04-23 19:11`
- 修改的文件：
  - `examples/portfolio_backtesting/build_qmt_roll_ai_candidate_training_samples.py`
- 新增的文件：
  - `examples/portfolio_backtesting/train_qmt_roll_ai_candidate_ranker_v2.py`
- 改动内容：
  - 在候选训练样本表中新增同日横截面特征增强：
    - `*_cs_rank_pct_1d`
    - `*_cs_rank_centered_1d`
    - `*_cs_zscore_1d`
  - 横截面增强覆盖的特征包括：
    - 趋势
    - 波动
    - 区间位置
    - 量能
    - OI
    - 风险归一化特征
  - 新增第五阶段 ranker：
    - `train_qmt_roll_ai_candidate_ranker_v2.py`
  - 训练侧主要使用：
    - 横截面 rank/zscore 特征
    - 少量风险归一化上下文

## 参数变化说明

- 新增的参数：
  - 无新增策略参数
- 修改的参数：
  - `ranker_v2_cs` 模型参数：
    - `n_estimators = 220`
    - `learning_rate = 0.035`
    - `num_leaves = 15`
    - `max_depth = 4`
    - `subsample = 0.8`
    - `colsample_bytree = 0.7`
    - `min_child_samples = 24`
    - `reg_alpha = 1.0`
    - `reg_lambda = 6.0`
- 删除的参数：
  - 无

## 样本配置

- 样本来源：
  - `qmt_roll_ai_candidate_training_samples.csv`
- 仅保留同日至少 `2` 个候选的横截面样本：
  - 总样本 `447`
- `train / valid / test`：
  - `162 / 87 / 198`

## 新增的数据产物

- 模型：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_ranker_ranker_v2_cs.joblib`
- 训练摘要：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_ranker_summary_ranker_v2_cs.json`
- 特征重要度：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_ranker_feature_importance_ranker_v2_cs.csv`
- 逐样本预测：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_ranker_predictions_ranker_v2_cs.csv`
- 测试集分桶分析：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_ranker_bucket_analysis_ranker_v2_cs.csv`

## 新增的训练结果

- 常规回归指标
  - `train`
    - `RMSE = 0.6326`
    - `MAE = 0.5767`
    - `R2 = 0.5464`
    - `Spearman = 0.8357`
  - `valid`
    - `RMSE = 1.0000`
    - `MAE = 0.9217`
    - `R2 = -0.1119`
    - `Spearman = -0.0099`
  - `test`
    - `RMSE = 0.9539`
    - `MAE = 0.8642`
    - `R2 = -0.0792`
    - `Spearman = -0.0034`

## 横截面专项结果

- `train`
  - `mean_group_spearman = 0.9695`
  - `top1_hit_rate = 95.77%`
  - `top1_quality_lift = 0.9382`
- `valid`
  - `mean_group_spearman = -0.1026`
  - `top1_hit_rate = 43.59%`
  - `top1_quality_lift = -0.0908`
- `test`
  - `mean_group_spearman = -0.0281`
  - `top1_hit_rate = 39.29%`
  - `top1_quality_lift = -0.3609`
  - `top1_selected_lift = 0.1363`

## 与上一版 ranker_v1 对比

- 退化的部分：
  - `test mean_group_spearman`: `0.0145 -> -0.0281`
  - `test top1_hit_rate`: `46.43% -> 39.29%`
  - `test top1_quality_lift`: `+0.0598 -> -0.3609`
- 基本持平的部分：
  - `test RMSE` 变化很小
  - `test R2` 仍然为负值
- 当前结论：
  - 单纯加入横截面标准化特征没有提升样本外质量排序能力
  - 反而放大了噪声或带来了过拟合

## 主要特征重要度

- Top 10：
  - `feature_oi_delta_5d_pct_cs_rank_centered_1d`
  - `feature_oi_delta_1d_pct_zscore_120_cs_zscore_1d`
  - `feature_ret_20d_zscore_120_cs_rank_centered_1d`
  - `feature_volume_ratio_1d_20d_zscore_120_cs_zscore_1d`
  - `feature_close_position_60d_cs_rank_centered_1d`
  - `feature_margin_per_contract_to_equity_cs_zscore_1d`
  - `feature_lower_wick_pct_cs_rank_centered_1d`
  - `feature_candidate_cross_section_count_1d`
  - `feature_target_risk_to_equity_cs_zscore_1d`
  - `feature_atr14_pct_zscore_120_cs_rank_centered_1d`

## 结果解释

- 这次反例很有价值：
  - 不是所有“看起来更高级”的横截面特征都能提升样本外质量
  - 当前候选池宽度仍然有限，直接做同日标准化容易把噪声也同步放大
- `ranker_v2_cs` 的特征已经明显偏向横截面相对表达，但结果退化说明：
  - 问题不只是“缺横截面标准化”
  - 还缺更稳定的目标定义或更适配的训练目标
- 当前更接近本质的判断是：
  - 横截面特征值得保留为候选方向
  - 但不能机械叠加到现有 pointwise 回归目标上

## 回测结果变化说明

- 新增的回测结果：
  - 无，本次仅新增第五阶段 ranking baseline 对比结果
- 修改的回测结果：
  - 无
- 删除的回测结果：
  - 无

## 快速结论

- 第五阶段已经完成，结果不支持继续沿“pointwise + 横截面标准化特征叠加”这条线深挖
- 当前最应该保留的结论不是“v2 失败了”，而是：
  - `ranker_v1` 虽弱但至少轻微正向
  - `ranker_v2_cs` 说明横截面特征需要和更合适的排序目标一起设计
- 下一步更值得做的是：
  - 不再继续堆特征
  - 改做 pairwise / listwise 风格的排序目标
  - 或重构标签为更明确的同日胜负关系

# 2026-04-23 19:21 第六阶段 pairwise ranking baseline

## 版本改动

- 改动时间点：`2026-04-23 19:21`
- 新增的文件：
  - `examples/portfolio_backtesting/train_qmt_roll_ai_candidate_pairwise_ranker.py`
- 改动内容：
  - 新增真正的 pairwise ranking baseline，使用 `LGBMRanker`
  - 训练方式从 pointwise 回归切换为按 `candidate_date` 分组的 `lambdarank`
  - 新增 pairwise 相关性标签：
    - `label_candidate_pairwise_relevance_1d`
  - relevance 构造方式：
    - 按同日 `label_candidate_quality_score_v2` 降序做 dense rank
    - 再映射为组内 relevance 值，供 `LGBMRanker` 使用
  - 评估新增 / 保留：
    - `ndcg_at_1`
    - `ndcg_at_3`
    - `top1_quality_lift`
    - `top1_selected_lift`
    - `mean_group_spearman`

## 参数变化说明

- 新增的参数：
  - 无新增策略参数
- 修改的参数：
  - pairwise ranker 模型参数：
    - `objective = lambdarank`
    - `metric = ndcg`
    - `eval_at = [1, 3]`
    - `n_estimators = 220`
    - `learning_rate = 0.04`
    - `num_leaves = 15`
    - `max_depth = 4`
    - `subsample = 0.8`
    - `colsample_bytree = 0.7`
    - `min_child_samples = 24`
    - `reg_alpha = 1.0`
    - `reg_lambda = 5.0`
- 删除的参数：
  - 无

## 样本配置

- 样本来源：
  - `qmt_roll_ai_candidate_training_samples.csv`
- 仅保留同日至少 `2` 个候选的样本：
  - 总样本 `447`
- `train / valid / test`：
  - `162 / 87 / 198`
- 组数：
  - `train_groups = 71`
  - `valid_groups = 39`
  - `test_groups = 84`

## 新增的数据产物

- 模型：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_pairwise_ranker_pairwise_v1.joblib`
- 训练摘要：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_pairwise_ranker_summary_pairwise_v1.json`
- 特征重要度：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_pairwise_ranker_feature_importance_pairwise_v1.csv`
- 逐样本预测：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_pairwise_ranker_predictions_pairwise_v1.csv`
- 测试集分桶分析：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_pairwise_ranker_bucket_analysis_pairwise_v1.csv`

## 新增的训练结果

- 常规指标
  - `train`
    - `RMSE = 0.6590`
    - `MAE = 0.5340`
    - `R2 = 0.5077`
    - `Spearman = 0.7379`
  - `valid`
    - `RMSE = 1.1174`
    - `MAE = 0.9808`
    - `R2 = -0.3887`
    - `Spearman = -0.0173`
  - `test`
    - `RMSE = 1.1240`
    - `MAE = 0.9447`
    - `R2 = -0.4985`
    - `Spearman = 0.0491`

## 横截面专项结果

- `train`
  - `mean_group_spearman = 0.9915`
  - `top1_hit_rate = 100.00%`
  - `top1_quality_lift = 1.1069`
  - `ndcg_at_1 = 1.0000`
  - `ndcg_at_3 = 0.9967`
- `valid`
  - `mean_group_spearman = -0.0487`
  - `top1_hit_rate = 38.46%`
  - `top1_quality_lift = -0.1581`
  - `ndcg_at_1 = 0.4530`
  - `ndcg_at_3 = 0.7990`
- `test`
  - `mean_group_spearman = -0.0916`
  - `top1_hit_rate = 39.29%`
  - `top1_quality_lift = 0.0376`
  - `top1_selected_lift = 0.1006`
  - `ndcg_at_1 = 0.4643`
  - `ndcg_at_3 = 0.7924`

## 与前两版 ranking 对比

- 对比 `ranker_v1`：
  - `test top1_quality_lift`: `0.0598 -> 0.0376`
  - `test mean_group_spearman`: `0.0145 -> -0.0916`
  - `test top1_hit_rate`: `46.43% -> 39.29%`
- 对比 `ranker_v2_cs`：
  - `test top1_quality_lift`: `-0.3609 -> 0.0376`
  - `test top1_hit_rate`: `39.29% -> 39.29%`（基本持平）
  - `test ndcg_at_1`: `新增 0.4643`

## 主要特征重要度

- Top 10：
  - `feature_atr14_pct_zscore_120`
  - `feature_oi_delta_1d_pct`
  - `feature_lower_wick_pct`
  - `feature_volume_ratio_2v2`
  - `feature_margin_per_contract_to_equity`
  - `feature_trend_ma20_gap_pct`
  - `feature_target_risk_to_equity`
  - `feature_vol20`
  - `feature_volume_ratio_1d_20d_zscore_120`
  - `feature_oi_delta_1d_pct_zscore_120`

## 结果解释

- 这版 pairwise baseline 的价值在于：
  - 终于用上了真正的排序学习目标
  - 训练目标和“同日候选谁更优”在形式上是一致的
- 但从结果看，结论仍然偏克制：
  - 它确实比 `ranker_v2_cs` 这种“特征增强但目标没变”的方案更稳
  - 但并没有明显超过最朴素的 `ranker_v1`
- 这说明当前瓶颈已经更靠近数据本身：
  - 标签仍然噪声较大
  - 同日候选宽度仍然有限
  - 单靠排序器类型切换，不足以带来实质突破

## 回测结果变化说明

- 新增的回测结果：
  - 无，本次仅新增 pairwise ranking baseline 训练结果
- 修改的回测结果：
  - 无
- 删除的回测结果：
  - 无

## 快速结论

- 第六阶段已经完成，pairwise baseline 已经落地并验证
- 当前最接近本质的判断是：
  - pairwise 目标本身没有错
  - 但它不是当前问题的主瓶颈
- 现阶段继续更换排序器意义有限，下一步更值得做的是：
  - 重构同日胜负标签
  - 进一步扩大候选宽度
  - 或把候选定义从“通过初筛”前移到“满足更早一级信号条件”

# 2026-04-23 19:36 第七阶段同日两两胜负样本数据层

## 版本改动

- 改动时间点：`2026-04-23 19:36`
- 新增的文件：
  - `examples/portfolio_backtesting/build_qmt_roll_ai_candidate_pairwise_samples.py`
- 改动内容：
  - 新增第七阶段数据层脚本，把同日候选从“按日分组 relevance”下沉为“显式两两胜负样本”
  - 新增固定 `left / right` 顺序的 pairwise 数据结构，避免镜像重复样本
  - 新增近似平手过滤逻辑，优先清理质量差值过小的高噪声 pair
  - 新增 `label_left_wins`、`label_quality_gap_abs`、`label_pair_weight`、`label_pair_strength_bucket` 等标签
  - 新增 `delta_feature_*` 与 `abs_delta_feature_*` 差分特征，便于后续直接训练二分类式 pairwise baseline

## 参数变化说明

- 新增的参数：
  - `PAIR_MIN_QUALITY_GAP = 0.75`
  - `PAIR_WEIGHT_CAP = 3.0`
- 修改的参数：
  - 无新增策略参数修改，本次仅新增 AI 样本数据层参数
- 删除的参数：
  - 无

## 数据结构说明

- 样本来源：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_training_samples.csv`
- pair 分组键：
  - `candidate_date`
- 固定顺序规则：
  - 按 `candidate_index -> sample_id` 升序固定 `left / right`
- 胜负标签口径：
  - `label_left_wins = 1` 表示 `left` 候选的 `label_candidate_quality_score_v2` 高于 `right`
- 去噪规则：
  - 仅保留 `|label_candidate_quality_score_v2_left - label_candidate_quality_score_v2_right| >= 0.75` 的 pair
- 样本权重口径：
  - `label_pair_weight = min(label_quality_gap_abs / 3.0, 1.0)`
- 强弱分档：
  - `weak`: `[0.75, 1.5)`
  - `medium`: `[1.5, 3.0)`
  - `strong`: `>= 3.0`

## 新增的数据产物

- Pairwise 样本表：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_pairwise_samples.csv`
- Pairwise schema：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_pairwise_schema.json`

## 新增的训练数据结果

- 候选主样本：
  - `883` 行
- 候选交易日：
  - `630` 天
- 至少有 `2` 个候选的交易日：
  - `194` 天
- 至少有 `3` 个候选的交易日：
  - `50` 天
- 原始 unordered pair 数：
  - `322`
- 被近似平手过滤掉的 pair：
  - `86`
- 最终保留的 pair：
  - `236`
- `label_left_wins` 占比：
  - `48.73%`
- `winner_selected_rate`：
  - `57.63%`
- 同方向 pair 占比：
  - `66.53%`
- `label_quality_gap_abs`：
  - `median = 2.2656`
  - `mean = 2.7920`
- 强弱分布：
  - `weak = 64`
  - `medium = 80`
  - `strong = 92`

## 结果解释

- 这一步的本质不是继续换模型，而是先把监督信号表达清楚
- 第六阶段的问题在于：
  - 虽然训练目标已经切到 `lambdarank`
  - 但样本层仍然把很多“接近平手”的 pair 隐式混在同日 relevance 里
- 第七阶段先把 pair 显式化后，有两个直接收益：
  - 后续可以训练真正的 pairwise binary baseline，而不是继续被迫绕回 pointwise 近似
  - 可以用 `label_quality_gap_abs` 和 `label_pair_weight` 控制弱信号噪声，而不是默认所有 pair 同权
- 从当前覆盖率看，首版阈值 `0.75` 是相对平衡的：
  - 既去掉了 `26.71%` 的近似平手 pair
  - 又保留了 `236` 个可用样本，没有把数据层砍空
- 这也再次说明当前真正的瓶颈仍然很接近数据本身：
  - 同日候选宽度依然偏窄
  - 真正有辨识度的 pair 数量并不多

## 回测结果变化说明

- 新增的回测结果：
  - 无，本次仅新增第七阶段 pairwise 样本数据层与统计结果
- 修改的回测结果：
  - 无
- 删除的回测结果：
  - 无

## 快速结论

- 第七阶段的数据结构已经落地，不再停留在“同日 relevance”的隐式近似
- 近似平手 pair 已经被显式过滤，后续可以更干净地训练 pairwise classifier / ranker
- 下一步更值得做的是：
  - 基于这份 `qmt_roll_ai_candidate_pairwise_samples.csv` 做首版二分类式 pairwise baseline
  - 对比是否优于第六阶段 `LGBMRanker` 的样本外 top1 / 胜负判别能力

# 2026-04-23 19:46 第八阶段 pairwise classifier 最小验证

## 版本改动

- 改动时间点：`2026-04-23 19:46`
- 新增的文件：
  - `examples/portfolio_backtesting/train_qmt_roll_ai_candidate_pairwise_classifier.py`
- 改动内容：
  - 基于第七阶段的 `qmt_roll_ai_candidate_pairwise_samples.csv` 新增最小可验证的 pairwise classifier baseline
  - 没有继续上高自由度模型，而是主动收敛为低自由度线性模型 `LogisticRegression`
  - 只保留 `12` 个差分 / 结构特征，避免在 `81` 行训练样本上继续堆复杂度
  - 使用 `label_pair_weight` 作为样本权重，提高大质量差 pair 的重要性
  - 新增强弱分桶评估（`weak / medium / strong`），验证是否至少在大 gap pair 上存在稳定方向性

## 参数变化说明

- 新增的参数：
  - `MODEL_TAG = pairwise_cls_v1`
  - `TARGET_COLUMN = label_left_wins`
  - `WEIGHT_COLUMN = label_pair_weight`
  - `VALID_START_DATE = 2023-01-01`
  - `TEST_START_DATE = 2024-01-01`
  - `C = 0.35`
  - `max_iter = 2000`
- 修改的参数：
  - 特征集改为小特征集，限制为 `12` 个字段：
    - `feature_pair_same_direction`
    - `feature_pair_same_signal`
    - `delta_risk_ratio`
    - `delta_remaining_position_slots`
    - `delta_feature_ret_signed_5d`
    - `delta_feature_trend_ma20_gap_pct`
    - `delta_feature_atr14_pct_zscore_120`
    - `delta_feature_lower_wick_pct`
    - `delta_feature_volume_ratio_2v2`
    - `delta_feature_margin_per_contract_to_equity`
    - `delta_feature_oi_delta_1d_pct`
    - `delta_feature_oi_delta_1d_pct_zscore_120`
- 删除的参数：
  - 无

## 样本配置

- 数据来源：
  - `qmt_roll_ai_candidate_pairwise_samples.csv`
- 总样本：
  - `236`
- 总交易日：
  - `151`
- 时间切分：
  - `train = 81`
  - `valid = 44`
  - `test = 111`
- 交易日切分：
  - `train_days = 52`
  - `valid_days = 30`
  - `test_days = 69`

## 新增的数据产物

- 模型：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_pairwise_classifier_pairwise_cls_v1.joblib`
- 训练摘要：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_pairwise_classifier_summary_pairwise_cls_v1.json`
- 系数表：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_pairwise_classifier_coefficients_pairwise_cls_v1.csv`
- 逐样本预测：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_pairwise_classifier_predictions_pairwise_cls_v1.csv`
- 测试集分桶分析：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_pairwise_classifier_bucket_analysis_pairwise_cls_v1.csv`

## 新增的训练结果

- 常规指标
  - `train`
    - `accuracy = 64.20%`
    - `weighted_accuracy = 65.80%`
    - `roc_auc = 0.7497`
    - `log_loss = 0.5717`
  - `valid`
    - `accuracy = 38.64%`
    - `weighted_accuracy = 36.36%`
    - `roc_auc = 0.4099`
    - `log_loss = 0.8241`
  - `test`
    - `accuracy = 42.34%`
    - `weighted_accuracy = 43.63%`
    - `roc_auc = 0.4205`
    - `log_loss = 0.7952`

## 强弱分桶结果

- `test weak`
  - `accuracy = 40.00%`
  - `roc_auc = 0.4118`
- `test medium`
  - `accuracy = 36.36%`
  - `roc_auc = 0.3500`
- `test strong`
  - `accuracy = 47.92%`
  - `roc_auc = 0.4580`

## 主要系数方向

- 系数绝对值 Top 5：
  - `delta_feature_trend_ma20_gap_pct`
  - `delta_feature_lower_wick_pct`
  - `delta_feature_margin_per_contract_to_equity`
  - `delta_feature_atr14_pct_zscore_120`
  - `delta_feature_volume_ratio_2v2`

## 结果解释

- 这次最重要的结论不是“模型训出来了”，而是：
  - 当前第七阶段 pairwise 标签链路，还不足以支持可用的样本外判别器
- 证据非常直接：
  - `valid/test roc_auc` 都跌到 `0.5` 以下
  - `test weighted_accuracy = 43.63%`，低于随机猜测附近应有的水平
  - 连 `strong` 组样本也没有恢复到正向，说明问题不只是弱 pair 噪声
- 更关键的是测试集分桶出现了反向信号：
  - 预测 `low_left_win_prob` 的那一桶，真实 `left_win_rate` 反而最高，达到 `64.86%`
  - 这说明当前线性 classifier 学到的方向在样本外是反的，不适合作为后续仓位或选股依据
- 这也印证了更本质的判断：
  - 第七阶段的数据结构改造是对的
  - 但“把当前候选质量标签直接转成 left/right 胜负”这条监督表达仍然不够稳
  - 继续在这条标签上换模型，大概率只是重复过拟合

## 回测结果变化说明

- 新增的回测结果：
  - 无，本次仅新增 pairwise classifier 训练结果
- 修改的回测结果：
  - 无
- 删除的回测结果：
  - 无

## 快速结论

- 第八阶段已经完成，而且结论应当明确判负
- 当前不建议继续沿着“现有 pairwise 标签 + 再换分类器”投入时间
- 下一步更值得做的是：
  - 回到标签本身，重构“胜负关系”的定义
  - 把 pair 的监督从静态 `quality_score` 扩展到更稳健的 horizon / dominance 口径
  - 或继续前移候选定义，扩大同日候选宽度后再重做 pairwise 学习

# 2026-04-23 19:59 第九阶段 horizon 口径 pair 标签重构

## 版本改动

- 改动时间点：`2026-04-23 19:59`
- 新增的文件：
  - `examples/portfolio_backtesting/build_qmt_roll_ai_candidate_pairwise_horizon_samples.py`
  - `examples/portfolio_backtesting/train_qmt_roll_ai_candidate_pairwise_horizon_classifier.py`
- 改动内容：
  - 重构 pair 标签，不再使用 `quality_score` 聚合值定义 left/right 胜负
  - 新增显式 horizon 数据层，用候选未来 `5d / 10d / 20d` 的 `R multiple` 直接构造 pair 标签
  - 把 `10d + 20d` 作为主确认 horizon，`5d` 降级为辅助一致性标签
  - 新增 horizon 版 pairwise baseline，继续使用低自由度线性模型，只验证新监督是否存在样本外方向性

## 参数变化说明

- 新增的参数：
  - `PRIMARY_HORIZON_WINDOWS = (10, 20)`
  - `AUXILIARY_HORIZON_WINDOW = 5`
  - `PRIMARY_MIN_HORIZON_GAP = 0.5`
  - `PRIMARY_WEIGHT_CAP = 3.0`
  - `MODEL_TAG = pairwise_horizon_cls_v1`
  - `TARGET_COLUMN = label_horizon_primary_left_wins`
  - `WEIGHT_COLUMN = label_horizon_primary_weight`
  - `VALID_START_DATE = 2023-01-01`
  - `TEST_START_DATE = 2024-01-01`
  - `C = 0.35`
  - `max_iter = 2000`
- 修改的参数：
  - 主标签从 `label_left_wins` 切换为 `label_horizon_primary_left_wins`
  - 样本过滤从 `quality_score gap` 切换为：
    - `10d` 和 `20d` 胜负方向必须一致
    - `min(|10d gap|, |20d gap|) >= 0.5`
- 删除的参数：
  - 无

## 标签口径说明

- 主标签：
  - `label_horizon_primary_left_wins`
- 主标签定义：
  - 比较 `left / right` 候选的 `forward_10d_r_multiple` 与 `forward_20d_r_multiple`
  - 只有当 `10d` 与 `20d` 两个 horizon 的胜负方向一致时，才认为这个 pair 有效
  - 再要求 `min(|10d gap|, |20d gap|) >= 0.5`，过滤掉确认不足的弱 pair
- 辅助标签：
  - `label_horizon_5d_left_wins`
  - `label_horizon_10d_left_wins`
  - `label_horizon_20d_left_wins`
  - `label_horizon_5d_support_primary`
- 样本权重：
  - `label_horizon_primary_weight = min(label_horizon_primary_gap_abs / 3.0, 1.0)`

## 新增的数据产物

- Horizon pair 样本表：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_pairwise_horizon_samples.csv`
- Horizon pair schema：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_pairwise_horizon_schema.json`
- Horizon classifier 模型：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_pairwise_horizon_classifier_pairwise_horizon_cls_v1.joblib`
- 训练摘要：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_pairwise_horizon_classifier_summary_pairwise_horizon_cls_v1.json`
- 系数表：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_pairwise_horizon_classifier_coefficients_pairwise_horizon_cls_v1.csv`
- 逐样本预测：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_pairwise_horizon_classifier_predictions_pairwise_horizon_cls_v1.csv`
- 测试集分桶分析：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_pairwise_horizon_classifier_bucket_analysis_pairwise_horizon_cls_v1.csv`

## 新增的数据层结果

- 候选主样本：
  - `883` 行
- 原始 unordered pair：
  - `322`
- 因 `10d/20d` 不同向被过滤：
  - `64`
- 因主 gap 不足 `0.5` 被过滤：
  - `37`
- 最终 horizon pair：
  - `221`
- 交易日：
  - `146`
- `primary_left_win_rate`：
  - `50.68%`
- `winner_selected_rate`：
  - `58.82%`
- `same_direction_rate`：
  - `66.97%`
- `5d` 对主标签的支持率：
  - `81.90%`
- `label_horizon_primary_gap_abs`：
  - `median = 3.0321`
  - `mean = 6.5134`
- 强弱分布：
  - `weak = 61`
  - `medium = 49`
  - `strong = 111`

## 新增的训练结果

- 样本切分：
  - `train = 76`
  - `valid = 42`
  - `test = 103`
- 常规指标
  - `train`
    - `accuracy = 71.05%`
    - `weighted_accuracy = 73.92%`
    - `roc_auc = 0.7736`
  - `valid`
    - `accuracy = 35.71%`
    - `weighted_accuracy = 38.13%`
    - `roc_auc = 0.4256`
  - `test`
    - `accuracy = 47.57%`
    - `weighted_accuracy = 45.73%`
    - `roc_auc = 0.4585`

## 强弱分桶结果

- `test weak`
  - `accuracy = 50.00%`
  - `weighted_accuracy = 48.48%`
  - `roc_auc = 0.4788`
- `test medium`
  - `accuracy = 68.18%`
  - `weighted_accuracy = 70.73%`
  - `roc_auc = 0.6190`
- `test strong`
  - `accuracy = 38.18%`
  - `weighted_accuracy = 38.18%`
  - `roc_auc = 0.3573`

## 测试集分桶分析

- `low_left_win_prob`
  - 样本数：`34`
  - 真实 `left_win_rate = 58.82%`
  - `winner_selected_rate = 38.24%`
- `mid_left_win_prob`
  - 样本数：`34`
  - 真实 `left_win_rate = 50.00%`
  - `winner_selected_rate = 64.71%`
- `high_left_win_prob`
  - 样本数：`35`
  - 真实 `left_win_rate = 45.71%`
  - `winner_selected_rate = 62.86%`

## 主要系数方向

- 系数绝对值 Top 5：
  - `delta_feature_lower_wick_pct`
  - `delta_feature_trend_ma20_gap_pct`
  - `delta_feature_volume_ratio_2v2`
  - `delta_feature_margin_per_contract_to_equity`
  - `delta_feature_oi_delta_1d_pct_zscore_120`

## 结果解释

- 第九阶段比第八阶段更接近本质，因为：
  - 主监督不再依赖 `quality_score` 聚合口径
  - 直接回到未来 horizon 结果本身
  - 并且要求 `10d/20d` 同向确认，减少单 horizon 偶然性
- 但从样本外结果看，这条链路仍然不能判定为正向可用：
  - `test roc_auc = 0.4585`
  - `test weighted_accuracy = 45.73%`
  - `high_left_win_prob` 桶真实胜率仍低于 `low_left_win_prob`
- 不过它比第八阶段多暴露了一层结构信息：
  - `medium` 组已经出现正向信号，`roc_auc = 0.6190`
  - 但 `strong` 组反而显著失真，`roc_auc = 0.3573`
- 这说明问题已经不是“标签整体完全错”，而更像是：
  - 极端 horizon gap 样本并不天然代表更好的训练监督
  - 大 gap 很可能混入了高波动、跳空、挤仓、流动性扰动等场景
  - 这些场景让 `strong` 标签在训练集中看起来更确定，在样本外却更容易反噬

## 回测结果变化说明

- 新增的回测结果：
  - 无，本次仅新增 horizon 标签样本与 baseline 训练结果
- 修改的回测结果：
  - 无
- 删除的回测结果：
  - 无

## 快速结论

- 第九阶段应判定为：
  - 数据层方向正确
  - 监督表达比第八阶段更接近本质
  - 但 baseline 仍未达到可上线或可接入仓位控制的要求
- 下一步不建议继续简单换模型
- 更值得做的是：
  - 继续重构极端 `strong` pair 的定义和过滤逻辑
  - 或把候选定义前移，扩大同日候选宽度后再重新构建 horizon pair 监督

# 2026-04-23 20:10 第十阶段 strong 组极端 pair 去噪

## 版本改动

- 改动时间点：`2026-04-23 20:10`
- 新增的文件：
  - `examples/portfolio_backtesting/build_qmt_roll_ai_candidate_pairwise_horizon_strong_denoised_samples.py`
  - `examples/portfolio_backtesting/train_qmt_roll_ai_candidate_pairwise_horizon_strong_denoised_classifier.py`
- 改动内容：
  - 在第九阶段 horizon pair 样本基础上，新增只针对 `strong` 组的结构化去噪逻辑
  - 不再全局裁样本，只过滤 `strong` 组中 `OI` 单日变化横截面差异过大的极端 pair
  - 保留 `weak / medium` 原样，避免误伤第九阶段里已经开始出现正向信号的 `medium` 组
  - 新增第十阶段 baseline，继续固定低自由度线性模型，确保比较主要来自样本去噪而不是模型复杂度变化

## 参数变化说明

- 新增的参数：
  - `STRONG_BUCKET_NAME = strong`
  - `OI_NOISE_COLUMN = abs_delta_feature_oi_delta_1d_pct_zscore_120`
  - `STRONG_OI_NOISE_THRESHOLD = 2.0`
  - `MODEL_TAG = pairwise_horizon_cls_v2_strong_denoised`
- 修改的参数：
  - 样本过滤从“第九阶段不做 strong 特殊处理”改为：
    - `label_horizon_primary_strength_bucket == 'strong'`
    - 且 `abs_delta_feature_oi_delta_1d_pct_zscore_120 > 2.0`
    - 满足时直接从训练样本中剔除
- 删除的参数：
  - 无

## 去噪逻辑说明

- 本质判断：
  - `strong` 组最有问题的并不只是大 gap 本身
  - 更像是“大 gap + 极端 OI 横截面冲击”的组合在制造伪强样本
- 规则口径：
  - 仅当 pair 已经属于 `strong`
  - 且 `abs_delta_feature_oi_delta_1d_pct_zscore_120 > 2.0`
  - 才视为挤仓 / 异动噪声并剔除
- 这样做的原因：
  - `OI` 横截面单日剧烈分化更容易来自短期资金拥挤、换月扰动、挤仓或流动性冲击
  - 这类事件可以制造巨大的 horizon gap，但不一定具有穿越周期的可重复性

## 新增的数据产物

- 去噪版样本：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_pairwise_horizon_strong_denoised_samples.csv`
- 去噪版 schema：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_pairwise_horizon_strong_denoised_schema.json`
- 去噪版模型：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_pairwise_horizon_strong_denoised_classifier_pairwise_horizon_cls_v2_strong_denoised.joblib`
- 训练摘要：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_pairwise_horizon_strong_denoised_classifier_summary_pairwise_horizon_cls_v2_strong_denoised.json`
- 系数表：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_pairwise_horizon_strong_denoised_classifier_coefficients_pairwise_horizon_cls_v2_strong_denoised.csv`
- 逐样本预测：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_pairwise_horizon_strong_denoised_classifier_predictions_pairwise_horizon_cls_v2_strong_denoised.csv`
- 测试集分桶分析：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_pairwise_horizon_strong_denoised_classifier_bucket_analysis_pairwise_horizon_cls_v2_strong_denoised.csv`

## 新增的数据层结果

- 第九阶段原样本：
  - `221` 行
- `strong` 行数：
  - 去噪前：`111`
  - 去噪后：`90`
- 被剔除的 `strong` 极端 OI 噪声样本：
  - `21`
- 保留样本：
  - `200`
- 保留交易日：
  - `138`
- 剔除样本按时间切分分布：
  - `train = 4`
  - `valid = 4`
  - `test = 13`
- 被剔除样本的平均 `OI noise`：
  - `3.2511`
- 被剔除样本的平均 `primary_gap_abs`：
  - `7.5713`
- 保留样本强弱分布：
  - `weak = 61`
  - `medium = 49`
  - `strong = 90`

## 新增的训练结果

- 样本切分：
  - `train = 72`
  - `valid = 38`
  - `test = 90`
- 常规指标
  - `train`
    - `accuracy = 75.00%`
    - `weighted_accuracy = 76.84%`
    - `roc_auc = 0.7995`
  - `valid`
    - `accuracy = 42.11%`
    - `weighted_accuracy = 42.59%`
    - `roc_auc = 0.4435`
  - `test`
    - `accuracy = 51.11%`
    - `weighted_accuracy = 49.83%`
    - `roc_auc = 0.5055`

## 强弱分桶结果

- `test weak`
  - `accuracy = 50.00%`
  - `weighted_accuracy = 50.49%`
  - `roc_auc = 0.5394`
- `test medium`
  - `accuracy = 72.73%`
  - `weighted_accuracy = 74.63%`
  - `roc_auc = 0.6571`
- `test strong`
  - `accuracy = 40.48%`
  - `weighted_accuracy = 40.48%`
  - `roc_auc = 0.4005`

## 与第九阶段对比

- 整体上：
  - `test roc_auc` 从 `0.4585` 回升到 `0.5055`
  - `test accuracy` 从 `47.57%` 回升到 `51.11%`
  - `test weighted_accuracy` 从 `45.73%` 回升到 `49.83%`
- 结构上：
  - `medium` 组正向信号被保住，且继续增强
  - `weak` 组也回到略正向
  - `strong` 组虽然仍然明显偏弱，但已经从“严重污染整体”缩小成“局部残留问题”

## 测试集分桶分析

- `low_left_win_prob`
  - 样本数：`30`
  - 真实 `left_win_rate = 53.33%`
  - 平均 `OI noise = 0.8340`
- `mid_left_win_prob`
  - 样本数：`30`
  - 真实 `left_win_rate = 53.33%`
  - 平均 `OI noise = 1.0541`
- `high_left_win_prob`
  - 样本数：`30`
  - 真实 `left_win_rate = 53.33%`
  - 平均 `OI noise = 1.2462`

## 主要系数方向

- 系数绝对值 Top 5：
  - `delta_feature_lower_wick_pct`
  - `delta_feature_volume_ratio_2v2`
  - `delta_feature_oi_delta_1d_pct`
  - `delta_feature_oi_delta_1d_pct_zscore_120`
  - `delta_feature_trend_ma20_gap_pct`

## 结果解释

- 第十阶段说明了一件重要的事：
  - 第九阶段里 `strong` 组的确混入了可以被结构化识别的噪声
  - 而且这个噪声与 `OI` 横截面冲击高度相关
- 这一步的意义在于：
  - 它第一次把整体 `test roc_auc` 拉回 `0.5` 上方
  - 也证明“不是所有 strong 都该被砍”，而是要精准砍掉特定类型的 `strong`
- 但这一步仍然不能判定为最终可用，原因同样明确：
  - `valid roc_auc` 仍然只有 `0.4435`
  - `strong` 组本身仍未真正转正，`test roc_auc = 0.4005`
  - 测试集概率分桶虽然不再明显反向，但也还没有形成清晰单调关系
- 所以这一步更准确的结论是：
  - strong 去噪方向是对的
  - 但它只是把问题从“整体失真”缩小成“强尾部残留失真”
  - 还没有把监督链真正修复完成

## 回测结果变化说明

- 新增的回测结果：
  - 无，本次仅新增 strong 去噪样本与 baseline 训练结果
- 修改的回测结果：
  - 无
- 删除的回测结果：
  - 无

## 快速结论

- 第十阶段应判定为：
  - 局部修复有效
  - 结构判断正确
  - 但整体仍未到可接入仓位控制的程度
- 下一步不建议继续无脑改模型
- 更值得做的是：
  - 继续细分 `strong` 尾部，识别“高 gap 但非拥挤噪声”的子集
  - 或前移候选定义，扩大同日候选宽度后再重新构建 horizon 监督

# 2026-04-23 20:20 第十一阶段 strong 二次细分 refined 标签

## 版本改动

- 改动时间点：`2026-04-23 20:20`
- 新增的文件：
  - `examples/portfolio_backtesting/build_qmt_roll_ai_candidate_pairwise_horizon_strong_refined_samples.py`
  - `examples/portfolio_backtesting/train_qmt_roll_ai_candidate_pairwise_horizon_strong_refined_classifier.py`
- 改动内容：
  - 在第十阶段 strong 去噪样本基础上，进一步把剩余 `strong` 样本细分为两类原型：
    - `crowding_noise`
    - `trend_continuation_or_structural`
  - 不再把 `strong` 当作单一强度桶，而是显式标注其结构子类
  - 用 refined 样本重新训练 baseline，验证这种“原型层次标签”是否比单纯删异常值更有效

## 参数变化说明

- 新增的参数：
  - `STRONG_SUBTYPE_COLUMN = label_strong_pair_subtype`
  - `STRONG_REFINED_KEEP_COLUMN = label_strong_refined_is_kept`
  - `TREND_DIFF_COLUMN = abs_delta_feature_trend_ma20_gap_pct`
  - `RET20_DIFF_COLUMN = abs_delta_feature_ret_20d_zscore_120`
  - `TREND_DIFF_FLOOR = 0.02`
  - `RET20_DIFF_FLOOR = 1.4`
  - `MODEL_TAG = pairwise_horizon_cls_v3_strong_refined`
- 修改的参数：
  - `strong` 的 refined 噪声定义改为：
    - `feature_pair_same_signal == 1`
    - 且 `abs_delta_feature_trend_ma20_gap_pct < 0.02`
    - 且 `abs_delta_feature_ret_20d_zscore_120 < 1.4`
- 删除的参数：
  - 无

## refined 逻辑说明

- 第十阶段只识别出一种强噪声：
  - `OI` 横截面冲击型
- 第十一阶段的进一步判断是：
  - 即使剔除了 `OI` 极端冲击，`strong` 里仍有一批“同信号、同主题拥挤、但趋势结构根本没真正拉开”的伪强样本
- 因此新增二次细分逻辑：
  - `crowding_noise`
    - `same_signal == 1`
    - `trend_ma20_gap` 结构差很小
    - `ret20 zscore` 结构差也很小
  - `trend_continuation_or_structural`
    - 不满足上述条件，说明强样本更可能来自真实趋势结构差

## 新增的数据产物

- refined 样本：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_pairwise_horizon_strong_refined_samples.csv`
- refined schema：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_pairwise_horizon_strong_refined_schema.json`
- refined classifier 模型：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_pairwise_horizon_strong_refined_classifier_pairwise_horizon_cls_v3_strong_refined.joblib`
- 训练摘要：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_pairwise_horizon_strong_refined_classifier_summary_pairwise_horizon_cls_v3_strong_refined.json`
- 系数表：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_pairwise_horizon_strong_refined_classifier_coefficients_pairwise_horizon_cls_v3_strong_refined.csv`
- 逐样本预测：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_pairwise_horizon_strong_refined_classifier_predictions_pairwise_horizon_cls_v3_strong_refined.csv`
- 测试集分桶分析：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_pairwise_horizon_strong_refined_classifier_bucket_analysis_pairwise_horizon_cls_v3_strong_refined.csv`

## 新增的数据层结果

- 第十阶段原样本：
  - `200`
- refined 后样本：
  - `182`
- 被识别为 `crowding_noise` 并剔除：
  - `18`
- 交易日：
  - `130`
- `strong` 行数：
  - 去噪前：`90`
  - refined 后：`72`
- refined 前 subtype 分布：
  - `crowding_noise = 18`
  - `trend_continuation_or_structural = 72`
  - `non_strong = 110`
- 被剔除样本分布：
  - `train = 9`
  - `valid = 4`
  - `test = 5`
- 被剔除样本统计：
  - `left_win_rate = 55.56%`
  - `mean_primary_gap_abs = 12.4763`
  - `mean_trend_diff = 0.0087`
  - `mean_ret20_diff = 0.5783`

## 新增的训练结果

- 样本切分：
  - `train = 63`
  - `valid = 34`
  - `test = 85`
- 常规指标
  - `train`
    - `accuracy = 69.84%`
    - `weighted_accuracy = 72.09%`
    - `roc_auc = 0.7939`
  - `valid`
    - `accuracy = 44.12%`
    - `weighted_accuracy = 47.13%`
    - `roc_auc = 0.4886`
  - `test`
    - `accuracy = 55.29%`
    - `weighted_accuracy = 55.05%`
    - `roc_auc = 0.5666`

## 强弱分桶结果

- `test weak`
  - `accuracy = 53.85%`
  - `weighted_accuracy = 54.14%`
  - `roc_auc = 0.5939`
- `test medium`
  - `accuracy = 63.64%`
  - `weighted_accuracy = 64.37%`
  - `roc_auc = 0.6667`
- `test strong`
  - `accuracy = 51.35%`
  - `weighted_accuracy = 51.35%`
  - `roc_auc = 0.4941`

## 子类结果

- `test non_strong`
  - `accuracy = 58.33%`
  - `weighted_accuracy = 60.54%`
  - `roc_auc = 0.6222`
- `test trend_continuation_or_structural`
  - `accuracy = 51.35%`
  - `weighted_accuracy = 51.35%`
  - `roc_auc = 0.4941`
- `valid trend_continuation_or_structural`
  - `roc_auc = 0.5278`
- 这说明 refined 后：
  - `trend_continuation_or_structural` 至少不再像前面那样明显反向
  - `strong` 的核心问题已经从“强样本整体失真”收缩成“趋势延续子类仍然偏弱，但不再系统性反噬”

## 测试集分桶分析

- `low_left_win_prob`
  - 样本数：`28`
  - 真实 `left_win_rate = 46.43%`
- `mid_left_win_prob`
  - 样本数：`28`
  - 真实 `left_win_rate = 57.14%`
- `high_left_win_prob`
  - 样本数：`29`
  - 真实 `left_win_rate = 62.07%`
- 这是第一次在测试集上出现比较清晰的单调分层，说明 refined 标签已经开始具备更像监督信号而不是纯噪声的性质

## 主要系数方向

- 系数绝对值 Top 5：
  - `delta_feature_volume_ratio_2v2`
  - `delta_feature_oi_delta_1d_pct`
  - `delta_feature_oi_delta_1d_pct_zscore_120`
  - `delta_remaining_position_slots`
  - `delta_feature_trend_ma20_gap_pct`

## 结果解释

- 这一步比第十阶段更接近本质，原因在于：
  - 第十阶段仍然是在“删异常”
  - 第十一阶段则开始把强样本本身分成“不同机制原型”
- 更重要的是，结果改善不再只体现在某一个局部指标：
  - `valid roc_auc` 从 `0.4435` 提升到 `0.4886`
  - `test roc_auc` 从 `0.5055` 提升到 `0.5666`
  - `test weighted_accuracy` 从 `49.83%` 提升到 `55.05%`
  - 测试集分桶开始出现明显单调性
- 这说明 refined strong 标签已经开始真正改善监督质量，而不是只做“表面去噪”
- 但仍然要保持克制：
  - `valid` 还没有稳稳站上 `0.5`
  - `trend_continuation_or_structural` 子类虽然改善了，但还称不上强 alpha
  - 所以这一步更像“第一次真正看到正向雏形”，还不是可以直接接进仓位控制的终局版本

## 回测结果变化说明

- 新增的回测结果：
  - 无，本次仅新增 refined strong 样本与 baseline 训练结果
- 修改的回测结果：
  - 无
- 删除的回测结果：
  - 无

## 快速结论

- 第十一阶段是目前为止最有信息含量的一步
- 我对这一步的判断是：
  - 方向正确
  - 提升真实
  - 已经出现“可继续投入”的正向雏形
- 下一步最值得做的不是急着换模型，而是：
  - 把 refined subtype 继续前移到候选生成阶段
  - 或在保持同一标签口径下，做一次更克制的时间外稳定性验证

# 2026-04-23 20:26 第十二阶段 refined 标签 walk-forward 稳定性验证

## 版本改动

- 改动时间点：`2026-04-23 20:26`
- 新增的文件：
  - `examples/portfolio_backtesting/validate_qmt_roll_ai_candidate_pairwise_horizon_strong_refined_walkforward.py`
- 改动内容：
  - 基于第十一阶段 refined 标签样本，新增 walk-forward 时间外稳定性验证脚本
  - 固化为递增训练窗，不再复用单次固定切分结果
  - 按三个测试分段验证：
    - `2023`
    - `2024`
    - `2025+`
  - 同时导出每段的整体指标、强弱分桶、subtype 分桶和概率分桶单调性

## 参数变化说明

- 新增的参数：
  - `MODEL_TAG = pairwise_horizon_cls_v3_strong_refined_walkforward`
  - `WALK_FORWARD_WINDOWS`
    - `wf_2023`: `train < 2023-01-01`, `test = 2023`
    - `wf_2024`: `train < 2024-01-01`, `test = 2024`
    - `wf_2025_plus`: `train < 2025-01-01`, `test >= 2025-01-01`
- 修改的参数：
  - 无
- 删除的参数：
  - 无

## Walk-forward 口径说明

- 训练方式：
  - 递增训练窗
- 测试方式：
  - 每个阶段只用该阶段之后不可见的数据做测试
- 验证重点：
  - `overall_roc_auc`
  - `overall_weighted_accuracy`
  - `bucket_monotonicity_pass`
  - `strength` / `subtype` 分段结果

## 新增的数据产物

- Walk-forward 摘要：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_pairwise_horizon_strong_refined_walkforward_summary_pairwise_horizon_cls_v3_strong_refined_walkforward.json`
- 窗口指标 CSV：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_pairwise_horizon_strong_refined_walkforward_window_metrics_pairwise_horizon_cls_v3_strong_refined_walkforward.csv`
- 分桶分析 CSV：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_pairwise_horizon_strong_refined_walkforward_bucket_analysis_pairwise_horizon_cls_v3_strong_refined_walkforward.csv`
- 逐样本预测：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_pairwise_horizon_strong_refined_walkforward_predictions_pairwise_horizon_cls_v3_strong_refined_walkforward.csv`

## 新增的时间外验证结果

- `wf_2023`
  - `train_rows = 63`
  - `test_rows = 34`
  - `accuracy = 44.12%`
  - `weighted_accuracy = 47.13%`
  - `roc_auc = 0.4886`
  - `bucket_monotonicity_pass = False`
  - 概率分桶：
    - `low = 36.36%`
    - `mid = 27.27%`
    - `high = 41.67%`

- `wf_2024`
  - `train_rows = 97`
  - `test_rows = 49`
  - `accuracy = 48.98%`
  - `weighted_accuracy = 48.86%`
  - `roc_auc = 0.4565`
  - `bucket_monotonicity_pass = False`
  - 概率分桶：
    - `low = 56.25%`
    - `mid = 43.75%`
    - `high = 58.82%`

- `wf_2025_plus`
  - `train_rows = 146`
  - `test_rows = 36`
  - `accuracy = 50.00%`
  - `weighted_accuracy = 51.75%`
  - `roc_auc = 0.5937`
  - `bucket_monotonicity_pass = True`
  - 概率分桶：
    - `low = 50.00%`
    - `mid = 58.33%`
    - `high = 66.67%`

## 强弱分段结果

- `wf_2023`
  - `weak roc_auc = 0.4000`
  - `medium roc_auc = 0.5938`
  - `strong roc_auc = 0.5278`
- `wf_2024`
  - `weak roc_auc = 0.5400`
  - `medium roc_auc = 0.5000`
  - `strong roc_auc = 0.3750`
- `wf_2025_plus`
  - `weak roc_auc = 0.5667`
  - `medium roc_auc = 0.7857`
  - `strong roc_auc = 0.6667`

## subtype 结果

- `wf_2023`
  - `non_strong roc_auc = 0.4904`
  - `trend_continuation_or_structural roc_auc = 0.5278`
- `wf_2024`
  - `non_strong roc_auc = 0.5222`
  - `trend_continuation_or_structural roc_auc = 0.3750`
- `wf_2025_plus`
  - `non_strong roc_auc = 0.5729`
  - `trend_continuation_or_structural roc_auc = 0.6667`

## 总体统计

- `window_count = 3`
- `all_bucket_monotonicity_pass = False`
- `mean_test_auc = 0.5129`
- `mean_test_weighted_accuracy = 49.25%`

## 结果解释

- 这次验证给出了一个非常关键的结论：
  - refined 标签不是“全阶段稳定”的
  - 它明显具有时变性，而且主要在 `2025+` 段开始变得更有效
- 也就是说，第十一阶段的正向结果不能被简单解释成“标签已经普适可用”
- 更准确的结论是：
  - `2023` 和 `2024` 阶段，refined 标签还没有稳定站住
  - 真正同时满足 `AUC > 0.5` 和分桶单调性的，是 `2025+`
- 但这并不是坏消息，反而说明我们离本质更近了：
  - 之前是完全不知道标签为什么时好时坏
  - 现在已经能明确看到：
    - `2025+` 的市场结构更匹配 refined 标签表达
    - `2023/2024` 还存在 regime mismatch

## 我的判断

- 第十二阶段的价值非常高，因为它阻止了我们误把“单次切分的正向结果”当成稳定规律
- 这一步说明：
  - refined 标签已经不是纯噪声
  - 但它仍然是有 regime 依赖的监督信号
- 从穿越周期的角度看，这意味着：
  - 不能直接把当前 refined classifier 当成统一时代码接入仓位控制
  - 下一步更该研究的是：
    - 为什么 `2025+` 有效而 `2023/2024` 不稳定
    - 哪些市场环境特征决定 refined 标签是否可信

## 回测结果变化说明

- 新增的回测结果：
  - 无，本次仅新增 refined 标签的 walk-forward 时间外验证结果
- 修改的回测结果：
  - 无
- 删除的回测结果：
  - 无

## 快速结论

- 第十二阶段不能得出“refined 标签已稳定可用”的结论
- 但可以得出更重要的结论：
  - refined 标签已经具备条件性有效性
  - 它在 `2025+` 段表现出明显更强的排序和分桶能力
- 下一步最值得做的，不是继续堆分类器，而是：
  - 研究 refined 标签的生效环境
  - 把环境条件显式化，再决定是否让它参与仓位调节

# 2026-04-23 20:31 第十三阶段 refined 标签生效环境识别

## 版本改动

- 改动时间点：`2026-04-23 20:31`
- 新增的文件：
  - `examples/portfolio_backtesting/analyze_qmt_roll_ai_candidate_refined_environment.py`
- 改动内容：
  - 不再继续改标签和分类器，转而分析 refined 标签何时更可能生效
  - 新增日度环境画像脚本，把候选样本和 refined pair 样本都按交易日聚合
  - 把 `2025+` 定义为相对有效环境，把 `2023-2024` 定义为相对失效环境，比较两者的日度结构差异
  - 输出环境画像表、特征迁移表和摘要 JSON，作为后续环境门控的研究底稿

## 参数变化说明

- 新增的参数：
  - `MODEL_TAG = refined_environment_v1`
  - `EFFECTIVE_START_DATE = 2025-01-01`
- 新增的分析维度：
  - 候选层：
    - `candidate_count_1d`
    - `selected_rate_1d`
    - `avg_atr14_pct_zscore_120_1d`
    - `avg_range_pct_zscore_120_1d`
    - `avg_volume_ratio_1d_20d_zscore_120_1d`
    - `avg_oi_delta_1d_pct_zscore_120_1d`
    - `avg_close_position_60d_1d`
    - `avg_signal_strength_signed_1d`
    - `avg_mid_term_momentum_signed_1d`
    - `avg_reversal_pressure_signed_1d`
  - Pair 层：
    - `pair_count_1d`
    - `avg_primary_gap_abs_1d`
    - `avg_primary_weight_1d`
    - `same_signal_share_1d`
    - `same_direction_share_1d`
    - `support_5d_share_1d`
    - `winner_selected_rate_1d`
    - `avg_abs_delta_trend_ma20_gap_pct_1d`
    - `avg_abs_delta_ret_20d_zscore_120_1d`
    - `avg_abs_delta_oi_delta_1d_pct_zscore_120_1d`
    - `avg_abs_delta_range_pct_zscore_120_1d`
    - `avg_abs_delta_volume_ratio_2v2_1d`
- 修改的参数：
  - 无
- 删除的参数：
  - 无

## 新增的数据产物

- 日度环境画像：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_refined_environment_daily_refined_environment_v1.csv`
- 特征迁移表：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_refined_environment_feature_shift_refined_environment_v1.csv`
- 环境摘要：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_refined_environment_summary_refined_environment_v1.json`

## 环境划分说明

- 相对有效环境：
  - `candidate_date >= 2025-01-01`
- 相对失效环境：
  - `2023-2024`
- 这里的“有效 / 失效”不是市场客观标签，而是针对第十二阶段 walk-forward 结果定义的监督有效性分组

## 新增的环境分析结果

- 有效环境交易日：
  - `26`
- 相对失效环境交易日：
  - `104`
- 有效环境日期范围：
  - `2025-01-03 ~ 2025-12-01`
- 相对失效环境日期范围：
  - `2020-05-11 ~ 2024-12-19`

## Top Shift 特征

- `avg_close_position_60d_1d`
  - `ineffective = 0.5109`
  - `effective = 0.3624`
  - `cohen_d = -0.5407`
- `support_5d_share_1d`
  - `ineffective = 0.7388`
  - `effective = 0.9231`
  - `cohen_d = 0.4613`
- `avg_reversal_pressure_signed_1d`
  - `ineffective = 0.00717`
  - `effective = 0.01093`
  - `cohen_d = 0.3750`
- `selected_rate_1d`
  - `ineffective = 0.6175`
  - `effective = 0.5224`
  - `cohen_d = -0.2703`
- `winner_selected_rate_1d`
  - `ineffective = 0.6369`
  - `effective = 0.5192`
  - `cohen_d = -0.2475`
- `avg_range_pct_zscore_120_1d`
  - `ineffective = 0.1614`
  - `effective = 0.3571`
  - `cohen_d = 0.2455`
- `avg_abs_delta_range_pct_zscore_120_1d`
  - `ineffective = 1.0469`
  - `effective = 1.2337`
  - `cohen_d = 0.2073`
- `avg_abs_delta_volume_ratio_2v2_1d`
  - `ineffective = 0.3042`
  - `effective = 0.3660`
  - `cohen_d = 0.2054`

## 关键环境画像

- `candidate_count_1d`
  - `ineffective = 2.4327`
  - `effective = 2.3462`
- `pair_count_1d`
  - `ineffective = 1.4038`
  - `effective = 1.3846`
- `avg_primary_gap_abs_1d`
  - `ineffective = 6.2424`
  - `effective = 4.7596`
- `avg_abs_delta_trend_ma20_gap_pct_1d`
  - `ineffective = 0.0395`
  - `effective = 0.0367`
- `avg_abs_delta_ret_20d_zscore_120_1d`
  - `ineffective = 1.0681`
  - `effective = 1.0668`
- `avg_abs_delta_oi_delta_1d_pct_zscore_120_1d`
  - `ineffective = 0.9188`
  - `effective = 0.9249`
- `strength_strong_share_1d`
  - `ineffective = 0.4022`
  - `effective = 0.4231`
- `support_5d_share_1d`
  - `ineffective = 0.7388`
  - `effective = 0.9231`

## 结果解释

- 这一步给出了一个非常关键、而且有点反直觉的结论：
  - `2025+` 有效环境并不是“趋势结构差更大、gap 更大、仓位更激进”的环境
  - 它反而更像：
    - 候选整体所处的 `60d` 位置更低
    - `5d` 对主标签的支持率更高
    - 波动活跃度略高
    - 规则层真实已选中的拥挤程度更低
- 也就是说，refined 标签更可能在这样一种环境中生效：
  - 市场并非高位拥挤顺风段
  - 而是中低位、短周期确认更一致、但规则没有过度扎堆选中的阶段
- 这和直觉上的“越强趋势越有效”并不完全一致
- 更接近本质的解释可能是：
  - 当候选处于更低的中期位置时，refined 标签更容易捕捉“结构性修复 / 延续”的差异
  - 而不是在高位一致拥挤环境里被同质化信号吞没

## 我的判断

- 第十三阶段最大的价值，是把“为什么 2025+ 有效”从结果现象推进到环境画像层
- 当前可以初步形成的判断是：
  - refined 标签的生效环境，倾向于：
    - 更低的 `60d` 价格位置
    - 更高的 `5d` horizon 支持一致性
    - 略高的波动活跃度
    - 更低的规则已选中拥挤
- 但还不能直接把这套环境画像当成实时门控器上线
- 下一步如果要继续，就应该做两件事之一：
  - 基于这些环境变量，构造一个前视可用的“启用条件”原型
  - 或把环境分层带回 walk-forward，再验证 gated 与 ungated 的差异

## 回测结果变化说明

- 新增的回测结果：
  - 无，本次仅新增 refined 标签的环境画像分析结果
- 修改的回测结果：
  - 无
- 删除的回测结果：
  - 无

## 快速结论

- refined 标签已经不只是“某一段有效”，而是开始出现可解释的生效环境
- 这意味着下一步最值得做的，不是继续堆特征，而是：
  - 让 refined 标签只在“更像有效环境”的时候说话
  - 把它从统一监督，升级成“条件性监督”

# 2026-04-23 20:37 第十四阶段 refined 环境门控原型

## 版本改动

- 改动时间点：`2026-04-23 20:37`
- 新增的文件：
  - `examples/portfolio_backtesting/validate_qmt_roll_ai_candidate_pairwise_horizon_strong_refined_environment_gated_walkforward.py`
- 改动内容：
  - 基于第十三阶段环境画像，新增前视可用的环境门控 prototype
  - 不再尝试让 gate 直接选出“更高质量”的 active 样本，而是改成 `abstention gate` 思路：
    - 环境不满足时，让 refined 模型闭嘴，预测退回 `0.5`
  - 继续沿用第十一阶段 refined classifier，不改标签、不换模型，只比较：
    - `ungated`
    - `gated_blended`
    - `gated_active`

## 参数变化说明

- 新增的参数：
  - `MODEL_TAG = pairwise_horizon_cls_v3_strong_refined_env_gated_v1`
  - `ENV_GATE_RULES`
    - `avg_close_position_60d_1d <= 0.42`
    - `avg_range_pct_zscore_120_1d >= 0.24`
    - `selected_rate_1d <= 0.56`
    - 满足以上 3 条中的至少 `2` 条，则 `gate_on = 1`
- 规则说明：
  - 只使用前视可用的日度环境特征
  - 明确不使用 `support_5d_share_1d` 这类未来标签衍生变量做 gate

## 新增的数据产物

- Gated walk-forward 摘要：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_pairwise_horizon_strong_refined_environment_gated_summary_pairwise_horizon_cls_v3_strong_refined_env_gated_v1.json`
- 窗口指标 CSV：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_pairwise_horizon_strong_refined_environment_gated_window_metrics_pairwise_horizon_cls_v3_strong_refined_env_gated_v1.csv`
- 逐样本预测：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_pairwise_horizon_strong_refined_environment_gated_predictions_pairwise_horizon_cls_v3_strong_refined_env_gated_v1.csv`

## 新增的验证结果

### `wf_2023`

- 覆盖率：
  - `active_rows = 16 / 34`
  - `active_days = 12 / 26`
  - `active_row_coverage = 47.06%`
- `ungated`
  - `roc_auc = 0.4886`
  - `weighted_accuracy = 47.13%`
- `gated_blended`
  - `roc_auc = 0.5303`
  - `weighted_accuracy = 35.83%`
- `gated_active`
  - `roc_auc = 0.4688`
  - `weighted_accuracy = 48.63%`

### `wf_2024`

- 覆盖率：
  - `active_rows = 30 / 49`
  - `active_days = 19 / 34`
  - `active_row_coverage = 61.22%`
- `ungated`
  - `roc_auc = 0.4565`
  - `weighted_accuracy = 48.86%`
- `gated_blended`
  - `roc_auc = 0.5301`
  - `weighted_accuracy = 53.08%`
- `gated_active`
  - `roc_auc = 0.4286`
  - `weighted_accuracy = 53.55%`

### `wf_2025_plus`

- 覆盖率：
  - `active_rows = 23 / 36`
  - `active_days = 16 / 26`
  - `active_row_coverage = 63.89%`
- `ungated`
  - `roc_auc = 0.5937`
  - `weighted_accuracy = 51.75%`
- `gated_blended`
  - `roc_auc = 0.5111`
  - `weighted_accuracy = 47.01%`
- `gated_active`
  - `roc_auc = 0.5952`
  - `weighted_accuracy = 43.50%`

## 总体统计

- `mean_ungated_auc = 0.5129`
- `mean_gated_blended_auc = 0.5238`
- `mean_active_auc = 0.4972`
- `mean_active_row_coverage = 57.39%`

## 结果解释

- 这次最重要的结论是：
  - 当前 gate 更像“防守闸门”，不是“精选 alpha 放大器”
- 证据有两层：
  - `gated_active` 并没有稳定优于 `ungated`
    - 说明 gate 还不能把真正高质量样本显著筛出来
  - 但 `gated_blended` 在 `2023/2024` 两段明显改善了 `roc_auc`
    - 说明它确实能在坏环境里让 refined 模型少犯错
- 同时也必须看到代价：
  - `2025+` 是 refined 标签相对有效的阶段
  - gate 在这一段反而削弱了表现，`roc_auc` 从 `0.5937` 降到 `0.5111`
- 所以当前 gate 的真实角色更接近：
  - 一个“风险约束器”
  - 而不是一个“提高正向期收益效率”的启用器

## 我的判断

- 第十四阶段是有效的，但结论必须克制：
  - 这版门控原型可以作为研究型保护层
  - 但还不适合直接成为 refined 标签的正式启用条件
- 更本质的问题是：
  - 当前 gate 只学会了“什么时候别说话”
  - 还没有学会“什么时候值得更积极地说话”
- 换句话说：
  - 它对失效环境有一定识别力
  - 但对有效环境的精确召回还不够好

## 回测结果变化说明

- 新增的回测结果：
  - 无，本次仅新增 refined 环境门控原型的 walk-forward 结果
- 修改的回测结果：
  - 无
- 删除的回测结果：
  - 无

## 快速结论

- 第十四阶段应判定为：
  - 作为“防守门控”有研究价值
  - 作为“正式启用门控”还不够成熟
- 下一步更值得做的，不是继续调 gate 阈值，而是：
  - 把“失效环境 gate”与“有效环境召回”分开建模
  - 或让 gate 输出连续权重，而不是简单二值开关

# 2026-04-23 20:48 第十五阶段 refined 连续权重环境门控

## 版本改动

- 改动时间点：`2026-04-23 20:48`
- 新增的文件：
  - `examples/portfolio_backtesting/validate_qmt_roll_ai_candidate_pairwise_horizon_strong_refined_environment_weighted_walkforward.py`
- 改动内容：
  - 把第十四阶段的二值 gate 升级为连续权重 gate
  - 不再简单判断“说话 / 闭嘴”，而是把 refined 概率按环境质量向 `0.5` 连续回缩
  - 同时保留三条对比线：
    - `ungated`
    - `binary`
    - `weighted`

## 参数变化说明

- 新增的参数：
  - `MODEL_TAG = pairwise_horizon_cls_v3_strong_refined_env_weighted_v1`
  - `ENV_WEIGHT_RULES`
    - `close_position_good_max = 0.25`
    - `close_position_bad_min = 0.60`
    - `range_good_min = 0.60`
    - `range_bad_max = 0.00`
    - `selected_rate_good_max = 0.35`
    - `selected_rate_bad_min = 0.75`
    - `weight_floor = 0.35`
- 核心口径：
  - `close_position` 越低，weight 越高
  - `range_zscore` 越高，weight 越高
  - `selected_rate` 越低，weight 越高
  - 三个组件平均后，映射到 `[0.35, 1.0]`
- 概率回缩公式：
  - `weighted_probability = 0.5 + env_gate_weight * (ungated_probability - 0.5)`

## 新增的数据产物

- Weighted walk-forward 摘要：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_pairwise_horizon_strong_refined_environment_weighted_summary_pairwise_horizon_cls_v3_strong_refined_env_weighted_v1.json`
- 窗口指标 CSV：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_pairwise_horizon_strong_refined_environment_weighted_window_metrics_pairwise_horizon_cls_v3_strong_refined_env_weighted_v1.csv`
- 逐样本预测：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_pairwise_horizon_strong_refined_environment_weighted_predictions_pairwise_horizon_cls_v3_strong_refined_env_weighted_v1.csv`

## 新增的验证结果

### `wf_2023`

- `ungated`
  - `roc_auc = 0.4886`
  - `weighted_accuracy = 47.13%`
  - 分桶单调：`False`
- `binary`
  - `roc_auc = 0.5303`
  - `weighted_accuracy = 35.83%`
- `weighted`
  - `roc_auc = 0.5492`
  - `weighted_accuracy = 47.13%`
  - 分桶单调：`True`

### `wf_2024`

- `ungated`
  - `roc_auc = 0.4565`
  - `weighted_accuracy = 48.86%`
  - 分桶单调：`False`
- `binary`
  - `roc_auc = 0.5301`
  - `weighted_accuracy = 53.08%`
- `weighted`
  - `roc_auc = 0.4866`
  - `weighted_accuracy = 48.86%`
  - 分桶单调：`True`

### `wf_2025_plus`

- `ungated`
  - `roc_auc = 0.5937`
  - `weighted_accuracy = 51.75%`
  - 分桶单调：`True`
- `binary`
  - `roc_auc = 0.5111`
  - `weighted_accuracy = 47.01%`
- `weighted`
  - `roc_auc = 0.5746`
  - `weighted_accuracy = 51.75%`
  - 分桶单调：`False`

## 总体统计

- `mean_ungated_auc = 0.5129`
- `mean_binary_auc = 0.5238`
- `mean_weighted_auc = 0.5368`

## 权重分布

- `wf_2023`
  - `gate_weight_mean = 0.6354`
  - `min = 0.35`
  - `max = 1.0`
- `wf_2024`
  - `gate_weight_mean = 0.6851`
  - `min = 0.4164`
  - `max = 1.0`
- `wf_2025_plus`
  - `gate_weight_mean = 0.6935`
  - `min = 0.35`
  - `max = 1.0`

## 结果解释

- 第十五阶段的核心改进，不是把所有阶段都做强，而是把门控从“粗暴开关”改成了“连续收缩”
- 这样带来的直接效果是：
  - 相比 `binary`，`weighted` 更少伤害 `2025+`
  - 相比 `ungated`，`weighted` 又能改善 `2023/2024` 的排序关系
- 特别值得注意的是：
  - `weighted` 在 `2023` 和 `2024` 都修复了概率分桶的单调性
  - 而 `2025+` 虽然 `roc_auc` 略低于 `ungated`，但明显好于 `binary`
- 这说明 `weighted` 的真实角色更接近：
  - 一个“软门控权重器”
  - 而不是“硬启停开关”

## 我的判断

- 目前为止，在门控方向上：
  - `binary` 更像风险闸门
  - `weighted` 更像均衡折中方案
- 如果目标是“能穿越周期”而不是“某一年最好看”，那么：
  - `weighted` 明显比 `binary` 更接近可继续投入的原型
- 但也必须保持克制：
  - `2025+` 的分桶单调性被部分削弱
  - `2024` 虽然 `roc_auc` 改善，但还没有真正强到可以放心上线
- 所以这一步还不能直接等价于“环境门控已经成熟”

## 回测结果变化说明

- 新增的回测结果：
  - 无，本次仅新增连续权重门控的 walk-forward 结果
- 修改的回测结果：
  - 无
- 删除的回测结果：
  - 无

## 快速结论

- 第十五阶段是当前门控方向里最平衡的一步
- 我对它的判断是：
  - 比 `binary` 更优
  - 比 `ungated` 更稳
  - 但还需要进一步验证，不能直接实盘化
- 下一步最值得做的不是继续调几个阈值，而是：
  - 把连续权重 gate 接进回测里的仓位倍率链路
  - 做一次最小闭环验证：`ungated vs weighted-gated` 的真实收益 / 回撤对比

# 2026-04-23 21:16 第十六阶段 weighted gate 接入仓位倍率链路并完成正式回测闭环

## 版本改动

- 改动时间点：`2026-04-23 21:16`
- 新增的文件：
  - `examples/portfolio_backtesting/run_qmt_roll_weighted_env_gate_backtest.py`
- 修改的文件：
  - `examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
- 改动内容：
  - 在策略内新增“日度环境权重 -> 基础开仓仓位缩放”的最小闭环链路
  - 保持原始入场信号、风控分档、加减仓规则不变，只对 `flat_entry` 基础开仓仓位做环境权重缩放
  - 环境权重不直接复用离线 pairwise 预测，而是改成策略内按当日候选池原位重建三类前视可用环境特征：
    - `avg_close_position_60d`
    - `avg_range_pct_zscore_120`
    - `native_selected_rate`
  - 新增正式对比脚本，统一跑：
    - `ungated_baseline`
    - `weighted_env_gate_v1`
  - 输出正式主回测结果与起始年份分支结果，验证 weighted gate 是否真的提升收益/回撤，而不只是在离线 AUC 上好看

## 参数变化说明

- 新增的参数：
  - `enable_weighted_env_gate = False`
  - `weighted_env_gate_close_position_good_max = 0.25`
  - `weighted_env_gate_close_position_bad_min = 0.60`
  - `weighted_env_gate_range_good_min = 0.60`
  - `weighted_env_gate_range_bad_max = 0.00`
  - `weighted_env_gate_selected_rate_good_max = 0.35`
  - `weighted_env_gate_selected_rate_bad_min = 0.75`
  - `weighted_env_gate_weight_floor = 0.35`
- 修改的参数：
  - 无，默认主策略仍保持 `enable_weighted_env_gate = False`
- 删除的参数：
  - 无

## 本次回测参数

- 脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_weighted_env_gate_backtest.py`
- 回测入口：
  - `examples/portfolio_backtesting/run_qmt_roll_backtest.py`
- 初始资金：`200000`
- 分析区间：`2020-01-01 ~ 2026-04-30`
- 基础风险参数：
  - `risk_ratio_of_total_assets = 0.045`
  - `risk_ratio_open_interest_surge = 0.06`
  - `risk_ratio_volume_open_interest_surge = 0.06`
  - `risk_ratio_open_interest_decline = 0.025`
- 仓位与风险硬约束保持不变：
  - sizing 资金上限 `100 万`
  - 最大并发位 `8`
  - 单笔资金上限 `0.70`
  - 空头初始止损仍基于开仓当日最高价
  - 所有止损仍基于收盘价判断
- `weighted_env_gate_v1` 的仓位缩放口径：
  - 仅作用于 `flat_entry`
  - `reverse_entry` 与 `rollover_reopen` 不缩放
  - `selected_volume = floor(selected_volume_ungated * env_gate_weight)`

## 新增的数据产物

- 汇总 CSV：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_weighted_env_gate_v1_summary.csv`
- 汇总 JSON：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_weighted_env_gate_v1_summary.json`
- 基线正式回测产物：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ungated_baseline_statistics.json`
- Weighted gate 正式回测产物：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_weighted_env_gate_v1_statistics.json`

## 新增的回测结果

### `ungated_baseline`

- 期末权益 `3,015,735`
- 总收益 `1407.87%`
- 最大回撤 `-35.71%`
- Sharpe `1.0854`
- 总滑点 `347,080`
- 总交易次数 `1,214`
- 胜率 `42.00%`

### `weighted_env_gate_v1`

- 期末权益 `448,690`
- 总收益 `124.35%`
- 最大回撤 `-48.46%`
- Sharpe `0.4033`
- 总滑点 `73,900`
- 总交易次数 `713`
- 胜率 `37.09%`

## 修改的回测结果

- 新增正式对比口径后，确认第十五阶段离线 `weighted gate` 的 AUC 改善并没有迁移成真实组合收益改善
- 与本次同口径基线相比，`weighted_env_gate_v1` 的正式主回测结果变化如下：
  - 期末权益变化：`-2,567,045`
  - 总收益变化：`-1283.52%`
  - 最大回撤变化：`-12.76%`
  - Sharpe 变化：`-0.6822`
  - 总交易次数变化：`-501`
  - 总滑点变化：`-273,180`

## 删除的回测结果

- 无

## 结果解释

- 这次闭环验证给出的结论非常明确：
  - `weighted gate` 在离线排序层面看起来更平衡
  - 但一旦直接映射到真实仓位倍率链路，组合表现出现结构性塌缩
- 我对其本质判断是：
  - 这个 gate 更像“交易频率压缩器”，而不是“风险收益比优化器”
  - 它减少了交易、压低了滑点，但没有把剩余交易的质量显著抬高
  - 反而因为缩掉了大量本来就该拿满的强趋势仓位，导致收益和 Sharpe 被严重削弱
- 从第一性原理看，问题不在于“0.35 floor 还不够细”，而在于：
  - 我们把“环境层描述变量”直接映射成了“单笔仓位缩放变量”
  - 这会把本来属于组合层节奏的问题，错误地下沉到单笔 sizing 层处理
  - `selected_rate` 还是一个内生变量，进入实时闭环后容易形成自抑制反馈，越缩越弱

## 我的判断

- 第十六阶段最重要的不是“成功接回了回测”，而是正式证伪了一个很诱人的方向：
  - `weighted gate` 不能直接作为真实仓位倍率器上线
- 因此当前不应该继续顺着这个方向微调几个阈值、`floor` 或分段常数
- 更合理的下一步应该二选一：
  - 要么把环境门控上移到组合层，只控制“当天是否放宽并发 / 总风险预算”，而不是缩每一笔
  - 要么回到更直接的 alpha 问题，只让 AI 在候选排序里决定“选谁”，而不是决定“缩多少”

## 快速结论

- 第十六阶段闭环实现本身是成功的
- 第十六阶段策略结论是否定的：
  - `weighted_env_gate_v1` 在正式主回测中显著劣于 `ungated_baseline`
  - 当前版本不应写回默认策略
  - 当前版本只保留为研究型反例与后续组合层门控设计的证据

# 2026-04-23 21:31 第十七阶段 组合层环境门控最小原型

## 版本改动

- 改动时间点：`2026-04-23 21:31`
- 新增的文件：
  - `examples/portfolio_backtesting/run_qmt_roll_portfolio_env_gate_backtest.py`
- 修改的文件：
  - `examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
- 改动内容：
  - 不再让环境权重直接缩放单笔 `selected_volume`
  - 把同一套环境权重上移到组合层，改为控制：
    - `flat_entry` 的有效并发位上限
    - `flat_entry` 的有效组合资本预算
  - 保持原有入场规则、单笔资金上限、加减仓逻辑、换月重开逻辑不变
  - 保持 `reverse_entry` 与 `rollover_reopen` 不受组合层环境门控影响

## 参数变化说明

- 新增的参数：
  - `enable_portfolio_env_gate = False`
- 复用的环境权重参数：
  - `weighted_env_gate_close_position_good_max = 0.25`
  - `weighted_env_gate_close_position_bad_min = 0.60`
  - `weighted_env_gate_range_good_min = 0.60`
  - `weighted_env_gate_range_bad_max = 0.00`
  - `weighted_env_gate_selected_rate_good_max = 0.35`
  - `weighted_env_gate_selected_rate_bad_min = 0.75`
  - `weighted_env_gate_weight_floor = 0.35`
- 修改的参数：
  - 无，默认主策略仍保持 `enable_portfolio_env_gate = False`
- 删除的参数：
  - 无

## 本次回测参数

- 脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_portfolio_env_gate_backtest.py`
- 回测入口：
  - `examples/portfolio_backtesting/run_qmt_roll_backtest.py`
- 初始资金：`200000`
- 分析区间：`2020-01-01 ~ 2026-04-30`
- 基础风险参数：
  - `risk_ratio_of_total_assets = 0.045`
  - `risk_ratio_open_interest_surge = 0.06`
  - `risk_ratio_volume_open_interest_surge = 0.06`
  - `risk_ratio_open_interest_decline = 0.025`
- 硬约束保持不变：
  - sizing 资金上限 `100 万`
  - 基础最大并发位 `8`
  - 单笔资金上限 `0.70`
  - 空头初始止损仍基于开仓当日最高价
  - 所有止损仍基于收盘价判断
- `portfolio_env_gate_v1` 的组合层作用口径：
  - `effective_max_concurrent_positions = floor(max_concurrent_positions * env_gate_weight)`
  - `effective_capital_usage_ratio = max_capital_usage_ratio * env_gate_weight`
  - 仅对 `flat_entry` 生效

## 新增的数据产物

- 汇总 CSV：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_portfolio_env_gate_v1_summary.csv`
- 汇总 JSON：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_portfolio_env_gate_v1_summary.json`
- 基线正式回测产物：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_portfolio_gate_ungated_baseline_statistics.json`
- 组合层门控正式回测产物：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_portfolio_env_gate_v1_statistics.json`

## 新增的回测结果

### `ungated_baseline`

- 期末权益 `3,015,735`
- 总收益 `1407.87%`
- 最大回撤 `-35.71%`
- Sharpe `1.0854`
- 总滑点 `347,080`
- 总交易次数 `1,214`
- 胜率 `42.00%`

### `portfolio_env_gate_v1`

- 期末权益 `630,610`
- 总收益 `215.31%`
- 最大回撤 `-38.76%`
- Sharpe `0.5907`
- 总滑点 `96,280`
- 总交易次数 `725`
- 胜率 `40.38%`

## 修改的回测结果

- 与同口径基线相比，`portfolio_env_gate_v1` 的正式主回测结果变化如下：
  - 期末权益变化：`-2,385,125`
  - 总收益变化：`-1192.56%`
  - 最大回撤变化：`-3.06%`
  - Sharpe 变化：`-0.4947`
  - 总交易次数变化：`-489`
  - 总滑点变化：`-250,800`

## 删除的回测结果

- 无

## 结果解释

- 第十七阶段比第十六阶段更接近“正确层级”：
  - 没再直接缩每一笔
  - 而是改成缩组合层暴露
- 但正式回测仍然明确失败：
  - 组合层门控虽然比第十六阶段单笔缩放版本更温和
  - 但依旧显著跑输纯基线
- 我对其本质判断是：
  - 当前这套环境特征确实在描述“冷暖”
  - 但还不足以指导真实的组合级风险开关
  - 它更像一个解释器，而不是一个可以直接支配资金分配的控制器
- 更关键的是：
  - 不论门控落在单笔层还是组合层，都会显著减少交易与滑点
  - 但减少掉的并不只是噪声交易，也包括了大量真正贡献收益的趋势仓位

## 我的判断

- 这一步的价值不是“找到可上线版本”，而是再次缩小问题空间：
  - 问题已经不只是作用层级错了
  - 更深层的问题是当前环境画像到控制变量之间没有形成足够强的因果映射
- 因此下一步不应该继续围绕 gate 做小修小补
- 更合理的方向是：
  - 暂停继续投入环境门控主线
  - 回到候选排序 / 选谁 / 为什么某些候选在不同年份失效这个 alpha 核心问题

## 快速结论

- 第十七阶段的组合层环境门控，比第十六阶段单笔缩放更合理，但仍然失败
- 当前版本不应写回默认策略
- 环境门控方向到这里可以阶段性收口，后续优先级应让位于候选排序 alpha 主线

# 2026-04-23 21:37 第十八阶段 候选排序 alpha 最小验证方案

## 版本改动

- 改动时间点：`2026-04-23 21:37`
- 新增的文件：
  - `examples/portfolio_backtesting/validate_qmt_roll_ai_candidate_selection_rights.py`
- 修改的文件：
  - 无
- 改动内容：
  - 不直接把模型接回策略
  - 先做“选择权反事实验证”
  - 在同样的每日候选池、同样的每日入选个数下，用现有 `ranker_v2_cs` 模型对 `flat_entry` 候选重排
  - 比较三套选择结果：
    - `actual`：当前规则实际选中的候选
    - `predicted`：模型分数重排后的候选
    - `oracle`：按真实未来质量分数排序得到的理论上限

## 参数变化说明

- 新增的参数：
  - 无新增策略参数
- 复用的模型与样本：
  - 模型：`qmt_roll_ai_candidate_ranker_ranker_v2_cs.joblib`
  - 训练摘要：`qmt_roll_ai_candidate_ranker_summary_ranker_v2_cs.json`
  - 样本：`qmt_roll_ai_candidate_training_samples.csv`
- 样本过滤口径：
  - `entry_context == flat_entry`
  - 当日 `selected_count >= 1`
  - 当日 `selected_count < candidate_count`

## 本次验证口径

- 脚本：
  - `examples/portfolio_backtesting/validate_qmt_roll_ai_candidate_selection_rights.py`
- 核心思想：
  - 固定“每天最终选几个”
  - 只验证“同一天该选谁”这件事
- 评估窗口：
  - `valid_2023`
  - `test_2024`
  - `test_2025_plus`
  - `test_2024_plus`
- 比较指标：
  - `label_candidate_quality_score_v2`
  - `label_candidate_forward_10d_r_multiple`
  - `label_candidate_forward_20d_r_multiple`
  - `label_candidate_20d_mfe_r`
  - `label_candidate_20d_mae_r`

## 新增的数据产物

- 汇总 JSON：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_selection_rights_summary_ranker_v2_cs.json`
- 分窗口 CSV：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_selection_rights_windows_ranker_v2_cs.csv`
- 分日期明细 CSV：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_selection_rights_days_ranker_v2_cs.csv`

## 新增的验证结果

### `valid_2023`

- 重排发生率 `38.89%`
- 实际/预测集合重合率 `63.89%`
- 预测相对实际：
  - 质量分数 `+0.0789`
  - 10d forward `+0.1439`
  - 20d forward `+0.1390`

### `test_2024`

- 重排发生率 `30.00%`
- 实际/预测集合重合率 `76.25%`
- 预测相对实际：
  - 质量分数 `+0.1793`
  - 10d forward `+0.6634`
  - 20d forward `+0.3400`
  - 20d MFE `+0.6950`
  - 20d MAE `-0.1973`
- 这是当前最正向的窗口，说明“同日选谁”这件事在 2024 年确实存在可挖掘 alpha

### `test_2025_plus`

- 重排发生率 `38.46%`
- 实际/预测集合重合率 `61.54%`
- 预测相对实际：
  - 质量分数 `+0.3102`
  - 10d forward `-0.7055`
  - 20d forward `-0.8982`
  - 20d MFE `-0.3123`
  - 20d MAE `+1.3525`
- 说明模型虽然把“标签意义上的高质量候选”排得更靠前，但并没有抓住 2025+ 真正的收益候选

### `test_2024_plus`

- 重排发生率 `33.33%`
- 实际/预测集合重合率 `70.45%`
- 预测相对实际：
  - 质量分数 `+0.2309`
  - 10d forward `+0.1242`
  - 20d forward `-0.1478`
  - 20d MFE `+0.2982`
  - 20d MAE `+0.4132`

## 修改的回测/验证结论

- 第十八阶段没有新增正式资金回测结果
- 但新增了一条非常关键的 alpha 结论：
  - 候选排序方向和环境门控不同，它不是被完全证伪
  - 当前 `ranker_v2_cs` 在 2024 窗口对“同日选谁”有明显正贡献
  - 但到了 `2025+`，模型输出和真实未来收益重新脱锚

## 删除的回测结果

- 无

## 结果解释

- 这次验证说明两件事同时成立：
  - 第一，候选排序这条主线有真实头寸，不是伪命题
  - 第二，当前模型还没有稳到可以直接接入实盘选择权
- 更细一点讲：
  - `oracle` 相对 `actual` 的提升在所有窗口都非常大
  - 说明“同日候选池内部”确实存在很厚的可优化空间
  - 真问题不在于有没有 alpha，而在于当前 `ranker_v2_cs` 还没有把这部分 alpha 稳定抓出来
- 2025+ 的现象尤其重要：
  - 模型提升了 `quality_score_v2`
  - 但真实 `forward_10d/20d` 反而下降
  - 这说明我们当前离线标签与当前阶段真实收益口径之间，仍存在错配

## 我的判断

- 第十八阶段的核心结论是：
  - 应该继续投入“候选排序 alpha 主线”
  - 但下一步不是直接接策略回测
  - 而是先修正“排序监督标签”和“2025+ 失效机制”
- 最值得做的下一步不是调 LightGBM 超参，而是：
  - 专门分析 `2025+` 里模型重排失败的日期与候选特征
  - 找出为什么模型偏好的高分候选，真实 10d/20d 收益反而更差
  - 再据此重构选择权标签

## 快速结论

- 候选排序方向没有被证伪，和环境门控不同
- 当前 `ranker_v2_cs` 已经能在 `2024` 窗口改善“同日选谁”
- 但 `2025+` 仍明显失效，说明还不能直接接入实盘选择权
- 下一阶段应聚焦：
  - `2025+` 失效日期复盘
  - 监督标签重构
  - 然后再决定是否进入策略闭环

# 2026-04-23 21:43 第十九阶段 2025+ 失效日期复盘

## 版本改动

- 改动时间点：`2026-04-23 21:43`
- 新增的文件：
  - `examples/portfolio_backtesting/analyze_qmt_roll_ai_candidate_selection_failures_2025.py`
- 修改的文件：
  - 无
- 改动内容：
  - 基于第十八阶段的选择权反事实结果，专门分析 `test_2025_plus`
  - 只保留真正有伤害的失败日期：
    - `selection_changed = 1`
    - `predicted_minus_actual_candidate_forward_20d_r_multiple < 0`
  - 对每个失败日期展开：
    - `actual / predicted / oracle` 候选对比
    - 候选层特征差异
    - 失败模式归因

## 参数变化说明

- 新增的策略参数：
  - 无
- 复用的输入产物：
  - `qmt_roll_ai_candidate_selection_rights_days_ranker_v2_cs.csv`
  - `qmt_roll_ai_candidate_training_samples.csv`
  - `qmt_roll_ai_candidate_ranker_summary_ranker_v2_cs.json`
- 失败筛选口径：
  - 窗口：`test_2025_plus`
  - `selection_changed = 1`
  - `predicted_minus_actual_candidate_forward_20d_r_multiple < 0`

## 新增的数据产物

- 汇总 JSON：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_selection_failures_2025_summary.json`
- 失败日期明细：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_selection_failures_2025_dates.csv`
- 候选级明细：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_selection_failures_2025_cases.csv`
- 特征差异汇总：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_selection_failures_2025_feature_diff.csv`

## 新增的验证结果

- `2025+` 真正产生负面影响的失败日期只有 `2` 天：
  - `2025-04-03`
  - `2025-02-28`
- 这两天的平均伤害：
  - `predicted_minus_actual_10d_r = -9.2281`
  - `predicted_minus_actual_20d_r = -11.5365`

### 失败日期一：`2025-04-03`

- 实际选择：`candidate_837`，`lc`，`short_case1a`
- 模型选择：`candidate_836`，`CF`，`short_case3`
- 现象：
  - 两者 `quality_score_v2` 都是 `4.45`
  - 但真实 `20d_r` 分别是：
    - 实际 `18.8333`
    - 模型/Oracle `5.5313`
- 结论：
  - 这一天不是模型把“高质量候选”排错了
  - 而是当前 `quality_score_v2` 标签本身无法区分两者的未来收益差异
  - 这是典型的**标签分辨率不足 / 同分错序**问题

### 失败日期二：`2025-02-28`

- 实际选择：`candidate_808`，`OI`，`long_case2`
- 模型选择：`candidate_809`，`lh`，`short_case3`
- 现象：
  - 实际候选：
    - `20d_r = 2.5210`
    - `20d_MAE = 1.2350`
  - 模型候选：
    - `20d_r = -7.25`
    - `20d_MAE = 21.25`
  - 并且这一天 `oracle` 与 `actual` 完全一致
- 结论：
  - 这一天不是标签错了，而是模型真的把错误候选排到了前面
  - 失败候选呈现出典型特征：
    - `short_case3`
    - 更高的 `ret_20d_zscore`
    - 更高的 `range_pct_zscore_120`
    - 更极端的横截面趋势/位置特征
  - 这是典型的**模型过度偏好短期极端波动 / 极端趋势候选**问题

## 特征差异结论

- 失败样本里，模型相对实际更偏好的特征主要是：
  - 更高的 `feature_ret_20d_zscore_120`
  - 更高的 `feature_range_pct_zscore_120`
  - 更极端的 `feature_trend_ma20_gap_pct_cs_rank_centered_1d`
  - 更极端的 `feature_ma20_ma40_gap_pct_cs_zscore_1d`
  - 更极端的 `feature_close_position_60d_cs_zscore_1d`
- 这说明模型当前更容易被：
  - 强趋势尾部
  - 高波动尾部
  - 极端相对位置
  这些特征吸引
- 但这些特征在 `2025+` 并不稳定对应更好的持有期收益

## 修改的验证结论

- 第十八阶段只是知道“2025+ 失效”
- 第十九阶段把失效进一步拆成了两个本质不同的问题：
  - `2025-04-03`：标签分辨率不足
  - `2025-02-28`：模型偏好极端波动/极端趋势噪声候选

## 删除的回测结果

- 无

## 我的判断

- 现在已经能比较明确地定义下一步标签重构方向：
  - 不能只用当前 `quality_score_v2` 继续训练
  - 要专门提高对“同分候选”的区分能力
  - 同时抑制模型对极端波动/极端趋势尾部样本的错误偏好
- 因此下一步最值得做的不是再调模型参数，而是：
  - 重构选择权标签，让它更直接表达 `10d/20d` 持有收益与风险回撤的真实优劣
  - 尤其要处理：
    - 同分样本 tie-break
    - 极端尾部候选的惩罚项

## 快速结论

- `2025+` 失效不是单一问题，而是“标签分辨率不足 + 模型偏好极端噪声”叠加
- 当前已经有足够证据进入下一阶段标签重构
- 下一步应直接做：
  - 选择权标签重构
  - 不再继续调原版 `ranker_v2_cs`

# 2026-04-23 21:50 第20阶段 选择权标签重构 v1

## 版本改动

- 改动时间点：`2026-04-23 21:50`
- 新增的文件：
  - `examples/portfolio_backtesting/qmt_roll_ai_candidate_selection_label_v1.py`
  - `examples/portfolio_backtesting/train_qmt_roll_ai_candidate_ranker_selection_v1.py`
  - `examples/portfolio_backtesting/validate_qmt_roll_ai_candidate_selection_rights_v1.py`
- 修改的文件：
  - 无
- 改动内容：
  - 基于第十九阶段复盘结果，构建选择权标签 `v1`
  - 标签改动分成两部分：
    - 增加 `20d` 高收益尾部 `tail bonus`，解决 `quality_score_v2` 对高分候选同分错序的问题
    - 对高 `MAE`、高波动、高动量尾部、极端趋势横截面位置增加轻量惩罚，抑制模型继续偏好极端噪声候选
  - 在现有样本 CSV 上增量派生 `v1` 标签，不重写候选样本生成主链
  - 训练新的排序器 `selection_v1`，并复用第十八阶段的选择权反事实验证口径

## 参数变化说明

- 新增的标签：
  - `label_selection_quality_score_v1`
  - `label_selection_quality_bucket_v1`
  - `label_selection_quality_score_v1_rank_pct_1d`
  - `label_selection_quality_score_v1_rank_centered_1d`
- `v1` 标签的核心口径：
  - 保留 `5d / 10d / 20d` forward return 主干
  - 保留 `20d MFE - 20d MAE` 风险收益项
  - 新增：
    - `forward_20d_r_multiple > 5.0` 的尾部奖励
    - `feature_range_pct_zscore_120` 尾部惩罚
    - `feature_ret_20d_zscore_120` 尾部惩罚
    - `feature_trend_ma20_gap_pct_cs_rank_centered_1d` 极端惩罚
    - `feature_ma20_ma40_gap_pct_cs_zscore_1d` 极端惩罚
    - `feature_close_position_60d_cs_zscore_1d` 极端惩罚
- 新增模型标签：
  - `selection_v1`

## 新增的数据产物

- 重标注样本：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_training_samples_selection_v1.csv`
- 模型：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_ranker_selection_v1.joblib`
- 训练摘要：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_ranker_summary_selection_v1.json`
- 特征重要度：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_ranker_feature_importance_selection_v1.csv`
- 预测结果：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_ranker_predictions_selection_v1.csv`
- 分桶结果：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_ranker_bucket_analysis_selection_v1.csv`
- 选择权验证摘要：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_selection_rights_summary_selection_v1.json`
- 选择权分窗口：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_selection_rights_windows_selection_v1.csv`
- 选择权分日期：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_selection_rights_days_selection_v1.csv`

## 新增的训练结果

- 训练集：
  - `Spearman = 0.8243`
  - `R2 = 0.6023`
- 验证集：
  - `Spearman = -0.1867`
  - `R2 = -0.4362`
- 测试集：
  - `Spearman = -0.0301`
  - `R2 = -0.2876`
- 测试集横截面结果：
  - `mean_group_spearman = -0.0714`
  - `top1_hit_rate = 0.3929`
  - `top1_target_lift = -0.0754`
  - `top1_quality_lift = -0.3258`

## 新增的选择权验证结果

### `test_2024`

- `predicted_minus_actual_selection_quality_score_v1 = -0.2673`
- `predicted_minus_actual_10d_r = +0.0792`
- `predicted_minus_actual_20d_r = -0.2871`
- 结论：
  - `v1` 没有保住 2024 的正向选择权优势
  - 反而把 2024 拉成了轻度负贡献

### `test_2025_plus`

- `predicted_minus_actual_selection_quality_score_v1 = +0.0269`
- `predicted_minus_actual_10d_r = -0.7055`
- `predicted_minus_actual_20d_r = -0.8982`
- `predicted_minus_actual_20d_mae_r = +1.3525`
- 结论：
  - `v1` 虽然让模型选出的候选在新标签上略高于实际选择
  - 但并没有把真实 `10d/20d` 收益方向拉正
  - 说明标签对“极端噪声”的惩罚还不够精准，甚至可能把正确收益信息也一起压掉了

### `test_2024_plus`

- `predicted_minus_actual_selection_quality_score_v1 = -0.1514`
- `predicted_minus_actual_10d_r = -0.2299`
- `predicted_minus_actual_20d_r = -0.5279`
- 结论：
  - `v1` 作为整体版本不成立

## 修改的验证结论

- 第十九阶段给出的方向判断是正确的：
  - 需要 tie-break
  - 需要尾部惩罚
- 但第20阶段 `v1` 证明了另一件事：
  - 这两个机制不能直接通过一组静态线性权重硬拼在一起
  - 否则会把一部分真实 alpha 也一起惩罚掉

## 删除的回测结果

- 无

## 结果解释

- `v1` 是一次有价值的失败：
  - 它不是毫无作用
  - 而是告诉我们“方向对，配方错”
- 具体看：
  - `2025+` 新标签分数已经略优于实际选择，说明 tie-break 与风险惩罚确实触到了问题本质
  - 但真实收益没有同步改善，说明标签里把“未来收益”和“当前尾部特征惩罚”混得太硬
- 这会带来两个问题：
  - 第一，监督信号变得过于主观，模型更难学稳定
  - 第二，标签本身开始替模型做过多结构判断，导致样本外泛化反而更差

## 我的判断

- 第20阶段最重要的结论不是 `v1` 失败，而是：
  - 不能把“未来收益标签”和“当前特征惩罚”简单相加
- 更合理的下一步应该是：
  - 把 tie-break 部分继续保留在标签里
  - 但把“极端尾部惩罚”从标签中拿出来，改成：
    - 训练样本权重
    - 或候选过滤器
    - 或 pairwise 过滤规则
- 换句话说：
  - 标签负责描述未来优劣
  - 惩罚负责调样本可信度
  - 两者不应该继续强行混成一个分数

## 快速结论

- `selection_v1` 不是可用版本
- 但它成功验证了：
  - tie-break 是必要的
  - 尾部惩罚不该直接写死进标签
- 下一步更优路线应是：
  - 做 `选择权标签 v2`
  - 保留高收益 tie-break
  - 把尾部惩罚迁移到样本权重或过滤层

# 2026-04-23 21:58 第21阶段 选择权标签重构 v2

## 版本改动

- 改动时间点：`2026-04-23 21:58`
- 新增的文件：
  - `examples/portfolio_backtesting/qmt_roll_ai_candidate_selection_label_v2.py`
  - `examples/portfolio_backtesting/train_qmt_roll_ai_candidate_ranker_selection_v2.py`
  - `examples/portfolio_backtesting/validate_qmt_roll_ai_candidate_selection_rights_v2.py`
- 修改的文件：
  - 无
- 改动内容：
  - 延续第20阶段的核心判断：
    - 标签只负责表达未来收益优劣
    - 极端噪声处理迁移到样本权重层
  - `v2` 标签保留：
    - `5d/10d/20d` forward return 主干
    - `20d tail bonus`
    - `20d MAE` 风险项
  - `v2` 新增样本权重：
    - 对高波动尾部
    - 高动量尾部
    - 极端趋势横截面位置
    - 极端结构横截面位置
    - 极端 60 日位置
    进行可信度衰减

## 参数变化说明

- 新增的标签：
  - `label_selection_quality_score_v2p`
  - `label_selection_quality_bucket_v2p`
  - `label_selection_quality_score_v2p_rank_pct_1d`
  - `label_selection_quality_score_v2p_rank_centered_1d`
- 新增的样本权重：
  - `label_selection_sample_weight_v2p`
- 权重规则：
  - `noise_score` 由五类尾部特征线性组合得到
  - `sample_weight = clip(1 - 0.55 * noise_score, 0.35, 1.0)`

## 新增的数据产物

- 重标注样本：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_training_samples_selection_v2.csv`
- 模型：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_ranker_selection_v2.joblib`
- 训练摘要：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_ranker_summary_selection_v2.json`
- 特征重要度：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_ranker_feature_importance_selection_v2.csv`
- 预测结果：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_ranker_predictions_selection_v2.csv`
- 分桶结果：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_ranker_bucket_analysis_selection_v2.csv`
- 选择权验证摘要：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_selection_rights_summary_selection_v2.json`
- 选择权分窗口：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_selection_rights_windows_selection_v2.csv`
- 选择权分日期：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_selection_rights_days_selection_v2.csv`

## 新增的训练结果

- 训练集：
  - `Spearman = 0.8170`
  - `R2 = 0.5893`
- 验证集：
  - `Spearman = -0.1514`
  - `R2 = -0.3874`
- 测试集：
  - `Spearman = -0.0359`
  - `R2 = -0.2737`
- 测试集横截面结果：
  - `mean_group_spearman = -0.0512`
  - `top1_hit_rate = 0.4048`
  - `top1_target_lift = -0.0635`
  - `top1_quality_lift = -0.3143`

## 新增的选择权验证结果

### `test_2024`

- `predicted_minus_actual_selection_quality_score_v2p = -0.2603`
- `predicted_minus_actual_10d_r = +0.0792`
- `predicted_minus_actual_20d_r = -0.2871`
- 结论：
  - 与 `v1` 相比没有实质改善
  - 仍然无法保住 2024 窗口的选择权优势

### `test_2025_plus`

- `predicted_minus_actual_selection_quality_score_v2p = +0.0331`
- `predicted_minus_actual_10d_r = -0.7055`
- `predicted_minus_actual_20d_r = -0.8982`
- `predicted_minus_actual_20d_mae_r = +1.3525`
- 结论：
  - 即便把尾部惩罚迁移到样本权重层，`2025+` 仍没有转正
  - 这说明问题不再只是“标签和权重如何拆分”

### `test_2024_plus`

- `predicted_minus_actual_selection_quality_score_v2p = -0.1447`
- `predicted_minus_actual_10d_r = -0.2299`
- `predicted_minus_actual_20d_r = -0.5279`
- 结论：
  - `v2` 作为整体版本依然失败

## 修改的验证结论

- 第20阶段结论依旧成立：
  - 尾部惩罚不适合继续写进标签
- 但第21阶段新增了一个更深层的结论：
  - 即使把尾部惩罚迁到样本权重层
  - 现有这套单点回归式 candidate ranker 仍然无法学出稳定选择权

## 删除的回测结果

- 无

## 结果解释

- `v2` 比 `v1` 方法论上更干净：
  - 标签负责未来优劣
  - 权重负责样本可信度
- 但实证上依然没有救回来
- 这说明当前瓶颈开始上移到学习范式本身：
  - 单点分数回归虽然能表达“候选质量”
  - 但对“同日二选一 / 三选一”的真实相对优先级学习仍然不够强
- 换句话说：
  - 我们现在面对的是一个更像“相对胜负”而不是“绝对分数”的问题
  - 继续在 pointwise ranker 上修标签，边际收益正在迅速下降

## 我的判断

- 第21阶段之后，不建议继续迭代 `selection_v3`、`selection_v4` 这种 pointwise 标签版本
- 更合理的下一步应该是：
  - 转向选择权专用的 `pairwise / listwise` 监督
  - 直接学习“同日候选之间谁应该排在谁前面”
  - 并在 pair 构造时使用：
    - tie-break 后的未来收益优劣
    - 极端尾部样本的低权重或过滤
- 也就是说：
  - 未来收益标签继续保留
  - 但模型范式应从 `pointwise quality regression` 升级为 `selection-rights pairwise ranking`

## 快速结论

- `selection_v2` 不是可用版本
- `v2` 证明了：
  - 问题不再只是标签配方
  - 当前 pointwise ranker 本身已经成为主要瓶颈
- 下一步最优路线应是：
  - 进入 `第22阶段：选择权 pairwise / listwise 重构`

# 2026-04-23 22:47 第22阶段 选择权 pairwise 最小闭环验证

## 版本改动

- 改动时间点：`2026-04-23 22:47`
- 新增的文件：
  - `examples/portfolio_backtesting/build_qmt_roll_ai_candidate_selection_pairwise_samples.py`
  - `examples/portfolio_backtesting/train_qmt_roll_ai_candidate_selection_pairwise_classifier.py`
  - `examples/portfolio_backtesting/validate_qmt_roll_ai_candidate_selection_rights_pairwise.py`
- 改动内容：
  - 正式停止继续扩写 `selection_v3/v4` 这类 pointwise 标签版本
  - 新增选择权专用的 pairwise 数据层，只保留：
    - `flat_entry`
    - 当日 `selected_count >= 1`
    - 当日 `selected_count < candidate_count`
    的真实可重排候选池
  - pair 胜负标签不再直接回归绝对分数，而是改成：
    - 先比较 `label_selection_quality_score_v2p`
    - 再用 `20d forward R`
    - `10d forward R`
    - `20d MAE`
    做稳定 tie-break
  - 新增低自由度 `LogisticRegression` baseline，只验证“同日候选谁更该排前”是否存在样本外方向性
  - 新增 pairwise 版本选择权反事实验证：
    - 先用 pairwise 概率在同日候选池内累加成排序分数
    - 再固定每日实际入选个数，只比较“该选谁”是否优于当前规则

## 参数变化说明

- 新增的参数：
  - `MODEL_TAG = selection_pairwise_v1`
  - `TARGET_COLUMN = label_preferred_left_wins`
  - `WEIGHT_COLUMN = label_preferred_pair_weight`
  - `VALID_START_DATE = 2023-01-01`
  - `TEST_START_DATE = 2024-01-01`
  - `C = 0.35`
  - `max_iter = 2000`
- 新增的特征：
  - `feature_pair_same_direction`
  - `feature_pair_same_signal`
  - `feature_pair_same_risk_mode`
  - `delta_risk_ratio`
  - `delta_remaining_position_slots`
  - `delta_feature_ret_signed_5d`
  - `delta_feature_trend_ma20_gap_pct`
  - `delta_feature_atr14_pct_zscore_120`
  - `delta_feature_lower_wick_pct`
  - `delta_feature_volume_ratio_2v2`
  - `delta_feature_margin_per_contract_to_equity`
  - `delta_feature_oi_delta_1d_pct`
  - `delta_feature_oi_delta_1d_pct_zscore_120`
  - `delta_feature_close_position_60d`
  - `delta_feature_ret_20d_zscore_120`
- 新增的样本权重规则：
  - `base_weight = clip(abs(selection_quality_gap) / 2.0, 0.10, 1.0)`
  - 若 pair 跨越了“实际选中 / 未选中”边界，则额外乘以 `1.25`
  - 最终 `pair_weight` 上限为 `1.25`
- 修改的参数：
  - 学习范式从 `pointwise quality regression` 改为 `pairwise relative preference classification`
- 删除的参数：
  - 无

## 新增的数据产物

- Pairwise 样本：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_selection_pairwise_samples.csv`
- Pairwise schema：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_selection_pairwise_schema.json`
- Pairwise 模型：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_selection_pairwise_classifier_selection_pairwise_v1.joblib`
- 训练摘要：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_selection_pairwise_classifier_summary_selection_pairwise_v1.json`
- 系数表：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_selection_pairwise_classifier_coefficients_selection_pairwise_v1.csv`
- 逐样本预测：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_selection_pairwise_classifier_predictions_selection_pairwise_v1.csv`
- 测试集分桶分析：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_selection_pairwise_classifier_bucket_analysis_selection_pairwise_v1.csv`
- 选择权验证摘要：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_selection_rights_summary_selection_pairwise_v1.json`
- 选择权分窗口：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_selection_rights_windows_selection_pairwise_v1.csv`
- 选择权分日期：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_selection_rights_days_selection_pairwise_v1.csv`

## 新增的数据层结果

- 候选主样本：
  - `201` 行
- 可重排交易日：
  - `81` 天
- Pairwise 样本：
  - `169` 行
- Pairwise 交易日：
  - `81` 天
- `left_win_rate`：
  - `49.11%`
- `selection_disagreement_rate`：
  - `71.60%`
- `winner_selected_rate`：
  - `55.03%`
- `median_quality_gap_abs`：
  - `2.6708`
- `mean_quality_gap_abs`：
  - `3.1550`
- `mean_pair_weight`：
  - `0.9432`

## 新增的训练结果

- 样本切分：
  - `train = 62`
  - `valid = 33`
  - `test = 74`
- 常规指标
  - `train`
    - `accuracy = 67.74%`
    - `weighted_accuracy = 77.19%`
    - `roc_auc = 0.7672`
    - `log_loss = 0.4673`
  - `valid`
    - `accuracy = 45.45%`
    - `weighted_accuracy = 48.79%`
    - `roc_auc = 0.3593`
    - `log_loss = 0.8283`
  - `test`
    - `accuracy = 50.00%`
    - `weighted_accuracy = 49.95%`
    - `roc_auc = 0.5070`
    - `log_loss = 0.8372`
- 跨实际选择边界的 pair 子集：
  - `train weighted_accuracy = 77.90%`
  - `valid weighted_accuracy = 47.96%`
  - `test weighted_accuracy = 48.93%`

## 新增的选择权验证结果

### `valid_2023`

- 重排发生率 `55.56%`
- 实际/预测集合重合率 `47.22%`
- 预测相对实际：
  - `selection_quality_score_v2p = +0.8315`
  - `10d forward = +1.0936`
  - `20d forward = +2.4783`
  - `20d MFE = +3.1247`
  - `20d MAE = -0.6554`

### `test_2024`

- 重排发生率 `65.00%`
- 实际/预测集合重合率 `43.75%`
- 预测相对实际：
  - `selection_quality_score_v2p = +0.8574`
  - `10d forward = +3.5028`
  - `20d forward = +4.2996`
  - `20d MFE = +10.1618`
  - `20d MAE = +1.9840`

### `test_2025_plus`

- 重排发生率 `53.85%`
- 实际/预测集合重合率 `46.15%`
- 预测相对实际：
  - `selection_quality_score_v2p = +0.2412`
  - `10d forward = -1.0882`
  - `20d forward = -0.4213`
  - `20d MFE = +0.5863`
  - `20d MAE = +2.5037`

### `test_2024_plus`

- 重排发生率 `60.61%`
- 实际/预测集合重合率 `44.70%`
- 预测相对实际：
  - `selection_quality_score_v2p = +0.6147`
  - `10d forward = +1.6942`
  - `20d forward = +2.4398`
  - `20d MFE = +6.3896`
  - `20d MAE = +2.1887`

## 修改的验证结论

- 第21阶段的主判断被进一步坐实：
  - 当前 pointwise ranker 的确是主要瓶颈
- 第22阶段新增了一个更关键的结论：
  - 即使 pairwise classifier 自身的 `valid/test` AUC 并不强
  - 但一旦把它放回“固定每日入选个数、只比较该选谁”的反事实框架
  - `2024` 与 `2024+` 的真实 `10d/20d` 收益已经明显优于当前实际选择
- 这说明：
  - 选择权问题更接近“弱 pairwise 信号 + 日内聚合排序”
  - 而不是“单点分数本身必须先在全样本上表现很好”

## 删除的回测结果

- 无

## 结果解释

- 这一步最重要的不是 classifier 指标有多漂亮
- 而是：
  - `test roc_auc` 只是在随机附近微正 `0.5070`
  - 但真正关心的“同日该选谁”在 `2024` 和 `2024+` 已经出现明显正向改善
- 这和前面 pointwise 路线最大的区别在于：
  - pairwise 把监督目标直接对准了真实决策边界
  - 允许模型在局部相对优先级上有用
  - 不再强迫模型先学出一个全局稳定的绝对分数
- 但仍然要保持克制：
  - `2025+` 依然没有转正
  - 且 `20d MAE` 在所有正向窗口都恶化，说明模型现在更偏“放大利润弹性”，但还没有同时控制尾部回撤
- 更接近本质的判断是：
  - 第22阶段第一次证明了“pairwise 选择权”不是伪命题
  - 但当前版本更像“收益偏进攻”的第一版原型
  - 还不能直接接入正式资金回测或实盘选择权

## 我的判断

- 第22阶段应判定为：
  - 方向正确
  - 首次看到比 pointwise 更清晰的真实选择权改善
  - 值得继续投入
- 下一步最值得做的不是急着换复杂模型，而是：
  - 把 `20d MAE` 恶化的问题显式纳入 pair 构造或 pair 权重
  - 或把 pair 标签从“未来收益优先”扩成“收益优先但对尾部风险做软约束”的选择权监督
  - 再对 `2025+` 失效日期做专项复盘，确认为什么 pairwise 到这里仍然失真

## 快速结论

- `selection_pairwise_v1` 不是可上线版本
- 但它已经给出一条比 pointwise 更强的证据：
  - `2024` 与 `2024+` 的“同日该选谁”确实被改善了
  - 说明选择权主线继续投入是对的
- 第23阶段最优路线应是：
  - 保留 pairwise 范式
  - 专门修正尾部回撤恶化问题
  - 再看是否能把 `2025+` 一并拉正

# 2026-04-23 22:55 第23阶段 pairwise 风险权重修正 v2

## 版本改动

- 改动时间点：`2026-04-23 22:55`
- 新增的文件：
  - `examples/portfolio_backtesting/build_qmt_roll_ai_candidate_selection_pairwise_samples_v2.py`
  - `examples/portfolio_backtesting/train_qmt_roll_ai_candidate_selection_pairwise_classifier_v2.py`
  - `examples/portfolio_backtesting/validate_qmt_roll_ai_candidate_selection_rights_pairwise_v2.py`
- 改动内容：
  - 延续第22阶段的 pairwise 选择权范式，不再回退 pointwise
  - 不改 pair 胜负标签主干，继续保留：
    - `selection_quality_score_v2p`
    - `20d/10d forward R`
    - `20d MAE`
    的 tie-break 逻辑
  - 把第22阶段暴露出的“极端波动 / 极端趋势尾部”问题，下沉到 pair 权重层
  - 新增与失败模式直接相关的四列差分特征：
    - `delta_feature_range_pct_zscore_120`
    - `delta_feature_trend_ma20_gap_pct_cs_rank_centered_1d`
    - `delta_feature_ma20_ma40_gap_pct_cs_zscore_1d`
    - `delta_feature_close_position_60d_cs_zscore_1d`
  - 新增 `noise_score_v2`，对以下尾部进行可信度衰减：
    - 高波动尾部
    - 高动量尾部
    - 极端趋势横截面尾部
    - 极端结构尾部
    - 极端 60 日位置尾部

## 参数变化说明

- 新增的参数：
  - `MODEL_TAG = selection_pairwise_v2_risk_weighted`
  - `WEIGHT_COLUMN_V2 = label_preferred_pair_weight_v2`
  - `NOISE_SCORE_COLUMN = label_preferred_noise_score_v2`
- 新增的特征：
  - `delta_feature_range_pct_zscore_120`
  - `delta_feature_trend_ma20_gap_pct_cs_rank_centered_1d`
  - `delta_feature_ma20_ma40_gap_pct_cs_zscore_1d`
  - `delta_feature_close_position_60d_cs_zscore_1d`
- 新增的权重规则：
  - `noise_score_v2` 由五类尾部特征线性组合得到
  - `credibility_weight = clip(1 - 0.45 * noise_score_v2, 0.35, 1.0)`
  - `pair_weight_v2 = min(pair_weight_v1 * credibility_weight, 1.25)`
- 修改的参数：
  - Logistic 回归参数从 `C = 0.35` 调整为 `C = 0.30`
  - 其余训练框架保持不变，用于隔离“权重修正 + 新差分特征”的真实贡献
- 删除的参数：
  - 无

## 新增的数据产物

- Pairwise v2 样本：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_selection_pairwise_samples_v2.csv`
- Pairwise v2 schema：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_selection_pairwise_schema_v2.json`
- Pairwise v2 模型：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_selection_pairwise_classifier_selection_pairwise_v2_risk_weighted.joblib`
- 训练摘要：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_selection_pairwise_classifier_summary_selection_pairwise_v2_risk_weighted.json`
- 系数表：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_selection_pairwise_classifier_coefficients_selection_pairwise_v2_risk_weighted.csv`
- 逐样本预测：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_selection_pairwise_classifier_predictions_selection_pairwise_v2_risk_weighted.csv`
- 选择权验证摘要：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_selection_rights_summary_selection_pairwise_v2_risk_weighted.json`
- 选择权分窗口：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_selection_rights_windows_selection_pairwise_v2_risk_weighted.csv`
- 选择权分日期：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_selection_rights_days_selection_pairwise_v2_risk_weighted.csv`

## 新增的数据层结果

- 候选主样本：
  - `201` 行
- 可重排交易日：
  - `81` 天
- Pairwise v2 样本：
  - `169` 行
- Pairwise v2 交易日：
  - `81` 天
- `mean_pair_weight_v1`：
  - `0.9432`
- `mean_pair_weight_v2`：
  - `0.8360`
- `mean_noise_score_v2`：
  - `0.2496`

## 新增的训练结果

- 样本切分：
  - `train = 62`
  - `valid = 33`
  - `test = 74`
- 常规指标
  - `train`
    - `accuracy = 70.97%`
    - `weighted_accuracy = 77.28%`
    - `roc_auc = 0.7979`
    - `log_loss = 0.4491`
  - `valid`
    - `accuracy = 51.52%`
    - `weighted_accuracy = 57.13%`
    - `roc_auc = 0.4074`
    - `log_loss = 0.7888`
  - `test`
    - `accuracy = 54.05%`
    - `weighted_accuracy = 54.11%`
    - `roc_auc = 0.5344`
    - `log_loss = 0.8088`

## 新增的选择权验证结果

### `valid_2023`

- 重排发生率 `50.00%`
- 实际/预测集合重合率 `52.78%`
- 预测相对实际：
  - `selection_quality_score_v2p = +0.7936`
  - `10d forward = +0.6463`
  - `20d forward = +2.2539`
  - `20d MFE = +3.0346`
  - `20d MAE = -0.0137`

### `test_2024`

- 重排发生率 `70.00%`
- 实际/预测集合重合率 `41.25%`
- 预测相对实际：
  - `selection_quality_score_v2p = +0.9031`
  - `10d forward = +3.5843`
  - `20d forward = +4.3139`
  - `20d MFE = +10.2263`
  - `20d MAE = +1.9786`

### `test_2025_plus`

- 重排发生率 `53.85%`
- 实际/预测集合重合率 `51.28%`
- 预测相对实际：
  - `selection_quality_score_v2p = +0.5143`
  - `10d forward = +0.1067`
  - `20d forward = +0.1310`
  - `20d MFE = +0.5987`
  - `20d MAE = +1.0169`

### `test_2024_plus`

- 重排发生率 `63.64%`
- 实际/预测集合重合率 `45.20%`
- 预测相对实际：
  - `selection_quality_score_v2p = +0.7499`
  - `10d forward = +2.2143`
  - `20d forward = +2.6661`
  - `20d MFE = +6.4336`
  - `20d MAE = +1.5998`

## 修改的验证结论

- 第22阶段的正向主结论被保住：
  - `2024`
  - `2024+`
  的选择权改善仍然存在
- 第23阶段新增了一个更重要的改善：
  - `2025+` 从第22阶段的负值
    - `10d = -1.0882`
    - `20d = -0.4213`
    转成了轻微正值
    - `10d = +0.1067`
    - `20d = +0.1310`
- 同时：
  - `2025+` 的 `20d MAE` 恶化从 `+2.5037` 收敛到 `+1.0169`
  - `2024+` 的 `20d MAE` 也从 `+2.1887` 收敛到 `+1.5998`

## 删除的回测结果

- 无

## 结果解释

- 第23阶段说明上一阶段的本质判断是对的：
  - pairwise 主线没有问题
  - 真正需要修的不是标签主干，而是极端尾部样本在训练中的权重
- 这一步最有信息量的地方不是 `AUC` 小幅上升本身
- 而是：
  - `2025+` 从负转正
  - `MAE` 恶化被明显压缩
  - 说明“极端波动 / 极端趋势尾部下沉到 pair 权重层”确实击中了失效根因
- 但也不能过度乐观：
  - `2024` 的 `MAE` 仍然偏高
  - 当前版本依旧更偏“收益增强型选择器”，而不是“收益与尾部同时最优”的稳定控制器
- 更接近本质的结论是：
  - 第22阶段证明了 pairwise 方向成立
  - 第23阶段第一次证明了这条路不仅能提升收益，还能开始修正尾部风险失真

## 我的判断

- 第23阶段应判定为：
  - 真实改善
  - 路线继续收敛
  - 已经比 pointwise 时代明显更接近可用状态
- 下一步最值得做的不是盲目上复杂模型，而是：
  - 继续针对 `MAE` 最差的残余失败日期做局部复盘
  - 再决定是否把 `MAE` 直接纳入 pair 优劣标签，还是继续留在权重层
  - 如果后续还能再压一截 `2024` 的 `MAE`，就可以考虑接正式资金回测

## 快速结论

- `selection_pairwise_v2_risk_weighted` 仍不是最终上线版本
- 但它已经完成了两个关键跨越：
  - 保住了 `2024/2024+` 的选择权收益改善
  - 把 `2025+` 从负值拉回到轻微正值
- 第24阶段最优路线应是：
  - 保留 pairwise + 风险权重主线
  - 专门压剩余 `MAE` 尾部
  - 然后再决定是否进入正式资金回测闭环

# 2026-04-23 22:59 第24阶段 pairwise v2 残余尾部风险分型

## 版本改动

- 改动时间点：`2026-04-23 22:59`
- 新增的文件：
  - `examples/portfolio_backtesting/analyze_qmt_roll_ai_candidate_selection_pairwise_v2_tail_risk.py`
- 改动内容：
  - 不继续盲调模型，而是专门分析第23阶段 `pairwise_v2` 里残余的 `20d MAE` 尾部风险
  - 聚焦 `test_2024_plus` 唯一日期口径，避免和 `test_2024 / test_2025_plus` 重复计数
  - 只保留：
    - `selection_changed = 1`
    - `predicted_minus_actual_candidate_20d_mae_r > 0`
    的真实高尾部日期
  - 将这些日期按机制分成两类：
    - `catastrophic_tail`
      - `20d MAE` 变差
      - 且 `20d forward` 也更差
    - `aggressive_alpha`
      - `20d MAE` 变差
      - 但 `20d forward` 更好
  - 导出日期明细、候选级明细、分型特征漂移表和摘要 JSON

## 参数变化说明

- 新增的分析口径：
  - `focus_window = test_2024_plus`
  - `tail_risk_filter`
    - `selection_changed = 1`
    - `predicted_minus_actual_candidate_20d_mae_r > 0`
  - `tail_risk_type`
    - `catastrophic_tail`
      - `predicted_minus_actual_candidate_forward_20d_r_multiple <= 0`
    - `aggressive_alpha`
      - `predicted_minus_actual_candidate_forward_20d_r_multiple > 0`
- 新增的分析维度：
  - `feature_range_pct_zscore_120`
  - `feature_ret_20d_zscore_120`
  - `feature_volume_ratio_2v2`
  - `feature_oi_delta_1d_pct_zscore_120`
  - `feature_close_position_60d`
  - `feature_trend_ma20_gap_pct_cs_rank_centered_1d`
  - `feature_ma20_ma40_gap_pct_cs_zscore_1d`
  - `feature_close_position_60d_cs_zscore_1d`
- 修改的参数：
  - 无
- 删除的参数：
  - 无

## 新增的数据产物

- 分型摘要：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_selection_pairwise_v2_tail_risk_summary.json`
- 分型日期：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_selection_pairwise_v2_tail_risk_dates.csv`
- 候选级明细：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_selection_pairwise_v2_tail_risk_cases.csv`
- 特征漂移：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_selection_pairwise_v2_tail_risk_feature_diff.csv`

## 新增的分析结果

- 残余尾部日期总数：
  - `10` 天
- 分型分布：
  - `aggressive_alpha = 4`
  - `catastrophic_tail = 6`

### `aggressive_alpha`

- 平均 `predicted_minus_actual_20d_r = +23.7853`
- 平均 `predicted_minus_actual_20d_mae_r = +3.8798`
- 实际候选画像：
  - `forward_20d_r = 0.7077`
  - `mae_20d_r = 0.9312`
  - `mfe_20d_r = 1.9736`
- 模型候选画像：
  - `forward_20d_r = 24.4930`
  - `mae_20d_r = 4.8110`
  - `mfe_20d_r = 43.5306`
- 结论：
  - 这类日期不是“真错选”
  - 而是模型选择了更高弹性、也更高回撤的候选
  - 本质是风险偏好偏激进，而不是监督完全失真

### `catastrophic_tail`

- 平均 `predicted_minus_actual_20d_r = -6.8045`
- 平均 `predicted_minus_actual_20d_mae_r = +9.2925`
- 实际候选画像：
  - `forward_20d_r = 1.6023`
  - `mae_20d_r = 2.0967`
  - `mfe_20d_r = 4.3226`
- 模型候选画像：
  - `forward_20d_r = -4.1488`
  - `mae_20d_r = 9.2379`
  - `mfe_20d_r = 5.3179`
- 结论：
  - 这类日期才是下一阶段真正该优先打掉的“灾难型尾部”
  - 它们不是简单的高风险高收益
  - 而是高回撤且真实收益也更差

## 特征漂移结论

- 两类尾部都仍然和以下结构差异最相关：
  - `feature_trend_ma20_gap_pct_cs_rank_centered_1d`
  - `feature_close_position_60d_cs_zscore_1d`
  - `feature_ret_20d_zscore_120`
  - `feature_ma20_ma40_gap_pct_cs_zscore_1d`
  - `feature_oi_delta_1d_pct_zscore_120`
- 但第24阶段最关键的新发现不是“哪些特征重要”
- 而是：
  - 同样是 `MAE` 变差
  - 有一部分是值得接受的进攻型风险
  - 另一部分则是必须压掉的灾难型风险

## 修改的验证结论

- 第23阶段只能看到：
  - `MAE` 还没完全压住
- 第24阶段进一步把这个问题拆成了两类不同机制：
  - `aggressive_alpha`
    - 可以容忍，甚至可能不该过度抑制
  - `catastrophic_tail`
    - 必须优先约束
- 这意味着下一步不该继续做“统一 MAE 惩罚”
- 更合理的是：
  - 只针对灾难型尾部做更强 veto / filter / 风险约束
  - 避免把本来有效的进攻型 alpha 一起杀掉

## 删除的回测结果

- 无

## 我的判断

- 第24阶段最大的价值，不是又找到一个特征
- 而是把残余风险从“一个连续指标”推进成了“两个不同机制原型”
- 这一步之后，下一阶段的方向已经更清楚：
  - 不要再做统一风险惩罚
  - 而是做灾难型尾部专用的 veto / gating / pair 过滤逻辑
- 如果这一层再做对，才有资格进入正式资金回测

## 快速结论

- 当前 `pairwise_v2` 的残余问题不是“整体还不稳”
- 更准确地说，是：
  - 收益型进攻尾部和灾难型错误尾部还没有完全分开
- 第25阶段最优路线应是：
  - 保留现有 pairwise v2 主体
  - 新增“灾难型尾部 veto”机制
  - 只压 `catastrophic_tail`
  - 尽量不误杀 `aggressive_alpha`

# 2026-04-23 23:05 第25阶段 catastrophic tail veto 原型

## 版本改动

- 改动时间点：`2026-04-23 23:05`
- 新增的文件：
  - `examples/portfolio_backtesting/validate_qmt_roll_ai_candidate_selection_rights_pairwise_v2_catastrophic_veto.py`
- 改动内容：
  - 不改第23阶段模型本体，只在决策层新增一个最小 `catastrophic tail veto` 原型
  - veto 设计目标非常克制：
    - 只打掉第24阶段识别出来的灾难型尾部
    - 尽量不误伤仍然有正收益贡献的 `aggressive_alpha`
  - 具体做法：
    - 先复用 `selection_pairwise_v2_risk_weighted` 的同日 pairwise 排序分数
    - 再对满足灾难型签名的候选，在最终排序分数上施加固定惩罚

## 参数变化说明

- 新增的参数：
  - `MODEL_TAG = selection_pairwise_v2_catastrophic_veto_v1`
  - `VETO_PENALTY = 1.5`
- 新增的 veto 规则：
  - `direction == short`
  - `signal in {short_case2, short_case1a}`
  - `feature_ret_20d_zscore_120 < -0.3`
  - `feature_close_position_60d_cs_zscore_1d < 0.0`
  - `feature_range_pct_zscore_120 > 0.5`
- 修改的参数：
  - 无新增模型训练参数，本阶段只验证决策层 veto 是否有效
- 删除的参数：
  - 无

## 新增的数据产物

- 选择权验证摘要：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_selection_rights_summary_selection_pairwise_v2_catastrophic_veto_v1.json`
- 选择权分窗口：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_selection_rights_windows_selection_pairwise_v2_catastrophic_veto_v1.csv`
- 选择权分日期：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_selection_rights_days_selection_pairwise_v2_catastrophic_veto_v1.csv`

## 新增的选择权验证结果

### `valid_2023`

- `veto_rate = 9.30%`
- 预测相对实际：
  - `10d forward = +0.6224`
  - `20d forward = +2.3346`
  - `20d MAE = +0.3362`

### `test_2024`

- `veto_rate = 3.77%`
- 预测相对实际：
  - `10d forward = +3.5843`
  - `20d forward = +4.3139`
  - `20d MAE = +1.9786`
- 结论：
  - `2024` 主体表现基本未被破坏

### `test_2025_plus`

- `veto_rate = 9.68%`
- 预测相对实际：
  - `10d forward = +0.2754`
  - `20d forward = +0.3303`
  - `20d MAE = +0.9641`
- 与第23阶段相比：
  - `10d forward`：`+0.1067 -> +0.2754`
  - `20d forward`：`+0.1310 -> +0.3303`
  - `20d MAE`：`+1.0169 -> +0.9641`

### `test_2024_plus`

- `veto_rate = 5.95%`
- 预测相对实际：
  - `10d forward = +2.2808`
  - `20d forward = +2.7446`
  - `20d MAE = +1.5790`
- 与第23阶段相比：
  - `20d forward`：`+2.6661 -> +2.7446`
  - `20d MAE`：`+1.5998 -> +1.5790`

## 修改的验证结论

- 第24阶段提出的方向被验证为有效：
  - “只压灾难型尾部，不统一压所有高 MAE 候选”是对的
- 第25阶段说明：
  - 一个非常窄的 veto 原型就已经能做到：
    - 不明显伤害 `2024`
    - 继续提升 `2025+`
    - 同时再压一截 `MAE`
- 这意味着：
  - 第23阶段学到的 pairwise 主体已经足够好
  - 下一步更像是在决策层做尾部修边，而不是再推翻整个学习主线

## 删除的回测结果

- 无

## 结果解释

- 这一步最重要的不是 veto 命中了多少行
- 而是：
  - `veto_rate` 很低
  - 但 `2025+` 的 `20d` 和 `MAE` 还能继续同步改善
  - 说明第24阶段分出来的 `catastrophic_tail` 机制确实是可以被局部约束的
- 更接近本质的判断是：
  - 这类 veto 不是在“重新发明模型”
  - 而是在给已经有效的 pairwise 主体加一个灾难保险丝
- 当前版本仍然不能视为最终闭环：
  - veto 规则还是人工原型
  - 还没有做正式资金回测
  - 但它已经非常接近“可接回策略层做最小闭环试验”的状态

## 我的判断

- 第25阶段应判定为：
  - 真实有效
  - 方向收敛
  - 已经值得进入正式资金回测原型验证
- 下一步最值得做的不是继续堆更多 veto 条件
- 更合理的是：
  - 把 `selection_pairwise_v2_risk_weighted + catastrophic_veto_v1`
    接回策略选择权链路
  - 用同样的每日入选数控制，先做正式资金回测闭环
  - 再看收益、回撤、滑点是否相对当前实际选择继续改善

## 快速结论

- `catastrophic_veto_v1` 不是终局，但已经是一个有效原型
- 它证明了：
  - 灾难型尾部可以被局部压制
  - 而不必重新牺牲整条 pairwise 选择权主线
- 第26阶段最优路线应是：
  - 把当前 `pairwise_v2 + veto_v1` 接回正式资金回测
  - 做真正的收益/回撤闭环验证

# 2026-04-23 23:14 第26阶段 pairwise 选择权接回正式资金回测原型

## 版本改动

- 改动时间点：`2026-04-23 23:14`
- 新增的文件：
  - `examples/portfolio_backtesting/qmt_roll_ai_selection_pairwise_runtime.py`
  - `examples/portfolio_backtesting/run_qmt_roll_selection_pairwise_backtest.py`
- 修改的文件：
  - `examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
- 改动内容：
  - 把第23阶段 `selection_pairwise_v2_risk_weighted` 的同日候选排序逻辑正式接回 `QmtRollPortfolioStrategy`
  - 新增运行时 pairwise 打分桥接层：
    - 复用已训练好的 `LogisticRegression pairwise` 模型
    - 在策略内对同日 `flat_entry` 候选先做特征抽取、横截面标准化、再做排序
  - 新增可选 `catastrophic_veto_v1` 开关：
    - 沿用第25阶段验证过的灾难尾部 veto
    - 只对极窄的灾难型 short 候选施加固定分数惩罚
  - 将原策略的“按遍历顺序直接开仓”改成：
    - 先汇总同日候选
    - 再按 pairwise 分数重排
    - 最后在并发位约束下决定谁真正开仓
  - 为候选快照新增以下诊断字段：
    - `selection_pairwise_enabled`
    - `selection_pairwise_model_tag`
    - `selection_pairwise_score`
    - `selection_pairwise_rank`
    - `selection_pairwise_veto_flag`
    - `selection_pairwise_veto_penalty`

## 参数变化说明

- 新增的参数：
  - `enable_selection_pairwise_v2 = False`
  - `enable_selection_pairwise_v2_catastrophic_veto = False`
  - `selection_pairwise_model_path`
  - `selection_pairwise_summary_path`
  - `selection_pairwise_veto_penalty = 1.5`
- 修改的参数：
  - 无
- 删除的参数：
  - 无

## 新增的数据产物

- 正式资金回测汇总：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_v2_backtest_summary.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_v2_backtest_summary.json`

## 新增的回测结果

### `ungated_baseline`

- `期末权益 = 0`
- `总收益 = 0.00%`
- `最大回撤 = 0.00%`
- `Sharpe = 0.000`
- `总滑点 = 0`
- `总交易次数 = 0`

### `selection_pairwise_v2`

- `期末权益 = 0`
- `总收益 = 0.00%`
- `最大回撤 = 0.00%`
- `Sharpe = 0.000`
- `总滑点 = 0`
- `总交易次数 = 0`

### `selection_pairwise_v2_catastrophic_veto_v1`

- `期末权益 = 0`
- `总收益 = 0.00%`
- `最大回撤 = 0.00%`
- `Sharpe = 0.000`
- `总滑点 = 0`
- `总交易次数 = 0`

## 修改的回测结果

- 无

## 删除的回测结果

- 无

## 结果解释

- 这次第26阶段不是策略报错失败，而是正式资金回测所在环境没有可用历史成交数据：
  - 引擎日志显示所有合约 `Historical data loading completed, data count: 0`
  - 最终三组实验都变成了：
    - `0` 天
    - `0` 笔交易
    - `0` 条收益曲线
- 因此这一版能确认的只有两件事：
  - 代码层面的“pairwise 选择权接回策略主链路”已经完成
  - 工程闭环已经打通，且不会因为新逻辑直接崩溃
- 但这一版还不能回答最关键的问题：
  - 接回正式资金后，收益/回撤/滑点是否真的优于基线

## 新增的工程判断

- 第26阶段当前应判定为：
  - `工程接线完成`
  - `正式回测口径已具备`
  - `但数据环境为空，暂时无法形成有效资金结论`
- 更接近本质的判断是：
  - 现在的主要瓶颈已经不再是模型结构
  - 而是当前回测环境没有可用行情数据，导致正式资金验证失真为全零结果

## 快速结论

- `pairwise_v2 + catastrophic_veto_v1` 已经成功接回正式策略
- 但第26阶段正式资金结论目前是 `无效空结果`
- 下一步不是继续调模型
- 而是先恢复可用历史数据，再复跑同一套正式资金回测对比

# 2026-04-23 23:38 第27阶段 回测环境修复后正式资金复跑

## 版本改动

- 改动时间点：`2026-04-23 23:38`
- 本阶段没有新增策略代码文件
- 核心修复内容：
  - 定位并修复了第26阶段“正式资金回测全零”的环境问题
  - 根因不是策略逻辑，而是 `vnpy` 的数据库目录优先级：
    - 运行目录存在 `.vntrader/` 时，会优先使用当前目录数据库
    - 第26阶段临时生成的仓库内 `.vntrader/database.db` 是空库
    - 导致回测误连空库，才出现 `0` 交易、`0` 收益、`0` 滑点
  - 本阶段把仓库内 `.vntrader` 同步回用户原先一直在用的有效库后重新复跑

## 参数变化说明

- 新增的参数：
  - 无
- 修改的参数：
  - 无
- 删除的参数：
  - 无

## 修改的环境结论

- 第26阶段的“全零回测”判定为：
  - `无效环境结果`
  - 不能用于评估 `pairwise_v2` 本身
- 修复后重新确认：
  - 有效数据库概览数：`dbbaroverview = 4163`
  - 有效数据库K线数：`dbbardata = 979812`
  - 复跑时日志已恢复正常非零取数，例如：
    - `ru2005.SHFE data count = 232`
    - `si2401.GFEX data count = 242`
    - `sp2201.SHFE data count = 243`

## 修改的回测结果

### `ungated_baseline`

- 第26阶段错误结果：
  - `期末权益 = 0`
  - `总收益 = 0.00%`
  - `最大回撤 = 0.00%`
  - `Sharpe = 0.000`
  - `总滑点 = 0`
  - `总交易次数 = 0`
- 第27阶段修复后有效结果：
  - `期末权益 = 2,612,605`
  - `总收益 = 1206.30%`
  - `最大回撤 = -37.34%`
  - `Sharpe = 0.984`
  - `总滑点 = 355,230`
  - `总交易次数 = 1169`

### `selection_pairwise_v2`

- 第26阶段错误结果：
  - `期末权益 = 0`
  - `总收益 = 0.00%`
  - `最大回撤 = 0.00%`
  - `Sharpe = 0.000`
  - `总滑点 = 0`
  - `总交易次数 = 0`
- 第27阶段修复后有效结果：
  - `期末权益 = 2,624,635`
  - `总收益 = 1212.32%`
  - `最大回撤 = -37.34%`
  - `Sharpe = 0.986`
  - `总滑点 = 355,440`
  - `总交易次数 = 1169`

### `selection_pairwise_v2_catastrophic_veto_v1`

- 第26阶段错误结果：
  - `期末权益 = 0`
  - `总收益 = 0.00%`
  - `最大回撤 = 0.00%`
  - `Sharpe = 0.000`
  - `总滑点 = 0`
  - `总交易次数 = 0`
- 第27阶段修复后有效结果：
  - `期末权益 = 2,624,635`
  - `总收益 = 1212.32%`
  - `最大回撤 = -37.34%`
  - `Sharpe = 0.986`
  - `总滑点 = 355,440`
  - `总交易次数 = 1169`

## 新增的数据产物

- 正式资金复跑汇总：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_v2_backtest_summary.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_v2_backtest_summary.json`
- `selection_pairwise_v2_catastrophic_veto_v1` 全套回测产物：
  - `daily / trades / positions / candidate_snapshots / statistics / dashboard`

## 新增的比较结论

- 相对 `ungated_baseline`，`selection_pairwise_v2`：
  - `期末权益 +12,030`
  - `总收益 +6.015%`
  - `Sharpe +0.0022`
  - `最大回撤百分比 近乎不变`
  - `交易次数 不变`
  - `总滑点 +210`
- 相对 `ungated_baseline`，`selection_pairwise_v2_catastrophic_veto_v1`：
  - 与 `selection_pairwise_v2` 完全相同
  - 说明当前正式资金链路下：
    - 要么 veto 没有触发
    - 要么触发后没有改变最终入选集合
- 进一步检查候选快照后确认：
  - `selection_pairwise_enabled_sum = 230`
  - `selection_pairwise_veto_flag_sum = 0`
  - 所以这次正式资金回测里，`catastrophic_veto_v1` 实际上一次都没有命中

## 删除的回测结果

- 无

## 我的判断

- 第27阶段最重要的，不是收益多了 `12,030`
- 而是：
  - 现在终于拿到了有效的正式资金闭环
  - `pairwise_v2` 的正向性在真实资金曲线里被保住了
- 但也要实话实说：
  - 提升幅度目前还不大
  - `catastrophic_veto_v1` 接回正式策略后没有形成额外增益
  - 这说明离线选择权验证里的一部分 veto 效果，在正式资金链路里被稀释了

## 快速结论

- 第26阶段的问题已经确认是环境误连空库，不是策略失效
- 修复后正式回测表明：
  - `selection_pairwise_v2` 相对基线有小幅正向增益
  - `catastrophic_veto_v1` 暂时没有带来额外收益
- 下一步最合理的不是继续怀疑数据
- 而是直接复盘：
  - 为什么 veto 在线下有效、接回正式策略后却没有增量

# 2026-04-23 23:53 第28阶段 veto 正式链路失效定位

## 版本改动

- 改动时间点：`2026-04-23 23:53`
- 新增的文件：
  - `examples/portfolio_backtesting/analyze_qmt_roll_selection_pairwise_runtime_veto_gap.py`
- 修改的文件：
  - `examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
- 改动内容：
  - 新增 `veto` 失效对账脚本，专门比较：
    - 离线训练样本口径
    - 运行时重建特征口径
    - 正式回测候选快照里真实记录到的 `veto_flag`
  - 给策略候选快照新增运行时 veto 诊断字段：
    - `selection_pairwise_feature_ret_20d_zscore_120`
    - `selection_pairwise_feature_close_position_60d_cs_zscore_1d`
    - `selection_pairwise_feature_range_pct_zscore_120`
    - `selection_pairwise_runtime_veto_match_local`
  - 在策略侧补了一层本地 safeguard：
    - 即使 helper 没把 `veto_flag` 传下来
    - 也会再用运行时候选特征本地判断一次是否应命中 veto

## 参数变化说明

- 新增的参数：
  - 无
- 修改的参数：
  - 无
- 删除的参数：
  - 无

## 新增的数据产物

- veto 失效对账摘要：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_runtime_veto_gap_summary.json`
- veto 失效对账明细：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_runtime_veto_gap_cases.csv`

## 新增的分析结果

- 正式回测里 `selection_pairwise_enabled` 候选共：
  - `230` 行
  - `101` 个交易日
- 对账后发现：
  - 离线样本口径下满足 `veto` 条件的候选：`4`
  - 按运行时重建特征重新计算后满足 `veto` 条件的候选：`5`
  - 但正式回测候选快照里真实记录的 `veto_flag`：`0`

## 修改的回测结果

- 我又单独重跑了修补后的 `selection_pairwise_v2_catastrophic_veto_v1`
- 结果仍然与第27阶段一致：
  - `期末权益 = 2,624,635`
  - `总收益 = 1212.32%`
  - `最大回撤 = -37.34%`
  - `Sharpe = 0.986`
  - `总滑点 = 355,440`
  - `总交易次数 = 1169`
- 同时候选快照仍显示：
  - `selection_pairwise_veto_flag_sum = 0`

## 删除的回测结果

- 无

## 我的判断

- 第28阶段把问题进一步收窄了：
  - `catastrophic_veto_v1` 失效不是因为正式链路里没有这类候选
  - 也不是因为数据库或回测环境还有问题
  - 而是：
    - 正式链路里存在应被 veto 的候选
    - 但 `veto_flag` 没有真正进入最终策略决策和候选快照结果
- 当前最接近本质的判断是：
  - 问题不在高层研究路线
  - 而在 `helper -> strategy -> snapshot` 这一段仍然有口径脱节

## 快速结论

- 第28阶段已经证明：
  - 正式链路里确实存在应被 veto 的候选
  - 但 `veto_flag` 仍未真正生效
- 下一步最应该做的不是继续调 veto 条件
- 而是直接读取这次新增的运行时诊断字段，继续把脱节点锁到具体候选和具体交易日

# 2026-04-24 00:13 第29阶段 pairwise 运行时窗口修复与 veto 真正生效复盘

## 版本改动

- 改动时间点：`2026-04-24 00:13`
- 修改的文件：
  - `examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
- 改动内容：
  - 把正式策略 `ArrayManager` 的历史窗口从最小 `120` 提高到最小 `140`
  - 根因是运行时 `pairwise_v2` 特征里存在 `feature_ret_20d_zscore_120`
  - 该特征不是简单的 `120` 根窗口问题，而是：
    - 先计算 `20d return`
    - 再对 `20d return` 做 `zscore(120)`
  - 因此正式现场至少需要 `140` 根历史，之前的 `120` 根会让该特征在正式策略里系统性塌成 `0.0`

## 参数变化说明

- 新增的参数：
  - 无
- 修改的参数：
  - 无
- 删除的参数：
  - 无

## 新增的分析结果

- 修复前，正式候选快照里：
  - `selection_pairwise_feature_ret_20d_zscore_120` 对全部 `selection_pairwise_enabled` 候选都等于 `0.0`
  - 所以 `selection_pairwise_runtime_veto_match_local = 0`
  - `selection_pairwise_veto_flag = 0`
- 修复后，正式候选快照恢复正常：
  - `selection_pairwise_enabled = 144`
  - `selection_pairwise_veto_flag = 7`
  - `selection_pairwise_runtime_veto_match_local = 7`
  - `selection_pairwise_feature_ret_20d_zscore_120` 不再全零
- 说明第28阶段的真正根因不是 `helper -> strategy -> snapshot` 单纯传值丢失
- 而是更底层的运行时样本历史窗口不足，导致 veto 关键特征失真

## 修改的回测结果

- 在修复 `ArrayManager` 历史窗口后，重新完整回测：
  - `selection_pairwise_v2`
  - `selection_pairwise_v2_catastrophic_veto_v1`
- 两组新的正式统计结果都变为：
  - `期末权益 = 460,330`
  - `总收益 = 130.17%`
  - `最大回撤 = -53.76%`
  - `Sharpe = 0.251`
  - `总滑点 = 101,985`
  - `总交易次数 = 824`
- 相比第27阶段记录的旧结果：
  - 这次结果发生了明显变化
  - 说明之前正式策略里的 `pairwise` 运行时特征口径本身就是错的
  - 旧的资金曲线结论不能再直接当成当前版本依据

## 新增的回测结果

- `selection_pairwise_v2_catastrophic_veto_v1` 候选快照首次出现真实 veto 命中：
  - `2020-02-03 AP.CZCE`
  - `2022-07-06 SM.CZCE`
  - `2024-03-05 hc.SHFE`
  - `2024-06-27 SM.CZCE`
  - `2024-12-18 jm.DCE`
  - `2025-03-10 SH.CZCE`
  - `2026-03-02 SH.CZCE`

## 删除的回测结果

- 无

## 我的判断

- 第29阶段最关键的不是 veto 命中了 `7` 次
- 而是：
  - 现在终于确认正式策略现场的 `pairwise_v2` 关键特征口径和离线研究口径重新对齐了
  - 之前那种“veto 理论有效、正式策略完全不触发”的现象，本质上是运行时历史深度不足，不是 veto 逻辑本身错
- 但同时也暴露了另一个更本质的事实：
  - 即使 veto 已经真实触发
  - `selection_pairwise_v2_catastrophic_veto_v1` 的正式资金结果仍与 `selection_pairwise_v2` 完全一致
- 我继续逐日对账后确认：
  - 这 `7` 次 veto 都只改变了候选分数和排序
  - 但没有改变最终开仓集合
  - 原因不是 veto 没生效
  - 而是这些交易日里：
    - 组合仓位上限没有被打满
    - 或者其他候选本身不可开
    - 所以 veto 没有形成真正的交易替换

## 快速结论

- 第29阶段已经把问题走到本质：
  - `catastrophic_veto_v1` 现在技术上已经接通
  - 正式策略里也确实会触发
  - 但在当前组合约束下，它还不具备足够的“选择稀缺性”
- 下一步不该继续怀疑接线
- 更合理的是二选一：
  - 要么把 veto 改造成真正能替换入选名额的 hard filter
  - 要么只保留 `pairwise_v2`，承认当前 veto 在正式组合层没有边际价值

# 2026-04-24 00:21 第30阶段 catastrophic veto hard filter 正式验证

## 版本改动

- 改动时间点：`2026-04-24 00:21`
- 修改的文件：
  - `examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
- 改动内容：
  - 新增实验开关 `enable_selection_pairwise_v2_catastrophic_hard_filter`
  - 当 `selection_pairwise_veto_flag = 1` 且开启该开关时：
    - 直接把该候选从 `native_openable` 候选集合里剔除
    - `skip_reason` 记为 `selection_pairwise_catastrophic_veto`
  - 这次不是继续调 `penalty`
  - 而是专门验证：
    - 如果把 `catastrophic veto` 升格为真正影响开仓集合的硬过滤
    - 它到底能不能带来正式资金改进

## 参数变化说明

- 新增的参数：
  - `enable_selection_pairwise_v2_catastrophic_hard_filter = True`
- 修改的参数：
  - 无
- 删除的参数：
  - 无

## 新增的回测结果

- 新增正式回测版本：
  - `qmt_roll_selection_pairwise_v2_catastrophic_hard_filter_v1`
- 正式回测结果：
  - `期末权益 = 267,255`
  - `总收益 = 33.63%`
  - `最大回撤 = -61.30%`
  - `Sharpe = 0.088`
  - `总滑点 = 85,085`
  - `总交易次数 = 788`

## 修改的回测结果

- 对照版本 `selection_pairwise_v2`（第29阶段修正后）：
  - `期末权益 = 460,330`
  - `总收益 = 130.17%`
  - `最大回撤 = -53.76%`
  - `Sharpe = 0.251`
  - `总滑点 = 101,985`
  - `总交易次数 = 824`
- `hard_filter_v1` 相对 `selection_pairwise_v2`：
  - `期末权益 -193,075`
  - `总收益 -96.54%`
  - `最大回撤更差 7.54 个百分点`
  - `Sharpe -0.163`
  - `总交易次数 -36`
  - `总滑点 -16,900`

## 删除的回测结果

- 无

## 新增的分析结果

- `hard filter` 版本里：
  - `selection_pairwise_veto_flag = 7`
  - `skip_reason = selection_pairwise_catastrophic_veto` 也是 `7`
  - 说明这次 veto 已经真实改变了候选集合，不再只是改分数
- 相比 `selection_pairwise_v2`：
  - 候选状态发生变化的行数：`30`
  - 其中：
    - `opened -> skipped`：`23`
    - `skipped -> opened`：`7`
- 这 `7` 次 hard veto 对应的正式交易日是：
  - `2020-02-03 AP.CZCE`
  - `2022-07-06 SM.CZCE`
  - `2024-03-05 hc.SHFE`
  - `2024-06-27 SM.CZCE`
  - `2024-12-18 jm.DCE`
  - `2025-03-10 SH.CZCE`
  - `2026-03-02 SH.CZCE`
- 但硬过滤不仅仅少做了这 `7` 笔
- 它还通过权益路径改变了后续仓位与开仓容量，带出更多连锁差异

## 我的判断

- 第30阶段已经把 `catastrophic veto` 的价值边界验证清楚了：
  - 把它从 soft veto 升格成 hard filter 之后
  - 它确实能改变正式开仓集合
  - 但结果不是改善，而是明显恶化
- 这说明：
  - 之前的问题不是“veto 不够强”
  - 而是这个 veto 规则本身不具备足够稳健的跨周期 alpha
  - 一旦真的给它交易级否决权，它会误杀有效交易并破坏组合路径

## 快速结论

- `catastrophic_veto_v1`：
  - 作为 soft veto，在正式组合层没有边际价值
  - 作为 hard filter，在正式资金层明显有害
- 所以下一步不该继续沿着 veto 这条线加码
- 更合理的方向是：
  - 回到 `pairwise_v2` 主线
  - 把精力放在排序本体，而不是再发明新的 veto 规则

# 2026-04-24 00:44 第31阶段 当前版本完整标准回测重跑与经验沉淀

## 版本改动

- 改动时间点：`2026-04-24 00:44`
- 新增的文件：
  - `memory.md`
- 改动内容：
  - 使用标准入口 `examples/portfolio_backtesting/run_qmt_roll_selection_pairwise_backtest.py`
  - 对当前版本重新完整重跑：
    - `ungated_baseline`
    - `selection_pairwise_v2`
    - `selection_pairwise_v2_catastrophic_veto_v1`
  - 所有实验都覆盖：
    - `2020-01-01 -> 2026-04-30`
    - `since_2020 ~ since_2026` 分窗结果
  - 把这次踩到的关键经验沉淀到项目根目录 `memory.md`

## 参数变化说明

- 新增的参数：
  - 无
- 修改的参数：
  - 无
- 删除的参数：
  - 无

## 新增的回测结果

- 新的完整汇总文件：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_v2_backtest_summary.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_v2_backtest_summary.json`

## 修改的回测结果

- 当前版本 `ungated_baseline` 正式全样本结果：
  - `期末权益 = 464,320`
  - `总收益 = 132.16%`
  - `最大回撤 = -52.86%`
  - `Sharpe = 0.254`
  - `总滑点 = 103,795`
  - `总交易次数 = 828`
- 当前版本 `selection_pairwise_v2` 正式全样本结果：
  - `期末权益 = 460,330`
  - `总收益 = 130.17%`
  - `最大回撤 = -53.76%`
  - `Sharpe = 0.251`
  - `总滑点 = 101,985`
  - `总交易次数 = 824`
- 当前版本 `selection_pairwise_v2_catastrophic_veto_v1` 正式全样本结果：
  - `期末权益 = 460,330`
  - `总收益 = 130.17%`
  - `最大回撤 = -53.76%`
  - `Sharpe = 0.251`
  - `总滑点 = 101,985`
  - `总交易次数 = 824`
- 相对 `ungated_baseline`：
  - `selection_pairwise_v2`：
    - `期末权益 -3,990`
    - `总收益 -1.995%`
    - `最大回撤更差 0.896 个百分点`
    - `Sharpe -0.0033`
    - `交易次数 -4`
  - `selection_pairwise_v2_catastrophic_veto_v1`：
    - 与 `selection_pairwise_v2` 完全相同

## 新增的分析结果

- 当前版本下，`pairwise_v2` 不再优于 `baseline`
- 更精确地说：
  - `2020-2026` 全样本上，当前 `baseline` 小幅优于 `pairwise_v2`
  - `catastrophic_veto_v1` 仍然没有任何额外边际价值
- 分窗结果显示：
  - `since_2021`：`pairwise_v2` 明显优于 `baseline`
  - 但 `since_2020` 全样本被拖回去
  - `since_2022` 以后，`baseline / pairwise / soft veto` 三者结果几乎完全一致
- 这说明：
  - `pairwise_v2` 的增益并不稳定地分布在整个 `2020-2026`
  - 它更像对部分时间段有用，而不是已经具备穿越周期的稳定优势

## 删除的回测结果

- 无

## 我的判断

- 第31阶段最重要的不是重新得到一组数字
- 而是把当前版本的正式结论重新拉回同一口径：
  - 在修复运行时特征窗口后
  - 必须重跑完整标准脚本
  - 否则旧版 `baseline` 与新版 `pairwise` 对比没有意义
- 当前完整重跑后的结论很直接：
  - `pairwise_v2` 不是没有价值
  - 但它还没有稳定到足以在全样本上战胜当前 `baseline`
  - `soft veto` 继续确认无效
  - `hard filter` 已经在第30阶段确认有害

## 快速结论

- 当前版本下，应当把正式主结论更新为：
  - `baseline` 仍是更稳的主版本
  - `pairwise_v2` 继续保留为研究分支，但暂不应视为正式升级
  - `catastrophic veto` 这条线可以阶段性收口
- 这次经验也已经写入项目根目录 `memory.md`
- 后续如果再动运行时特征口径，必须先想到：
  - 嵌套特征需要的真实历史窗口
  - 以及完整标准回测必须重跑

# 2026-04-24 00:51 第32阶段 第27阶段与第31阶段结果断层根因审计

## 版本改动

- 改动时间点：`2026-04-24 00:51`
- 修改的文件：
  - `examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
  - `memory.md`
- 改动内容：
  - 新增审计参数 `array_manager_size_floor`
  - 允许在同一份当前代码里直接回放：
    - `ArrayManager = 120`
    - `ArrayManager = 140`
  - 目标不是做新策略优化
  - 而是验证：
    - 第27阶段 `1206% / 1212%`
    - 第31阶段 `132% / 130%`
    - 到底是不是同一个主因造成的断层

## 参数变化说明

- 新增的参数：
  - `array_manager_size_floor`
- 修改的参数：
  - 无
- 删除的参数：
  - 无

## 新增的回测结果

- `ungated_baseline @ array_manager_size_floor = 120`
  - `期末权益 = 2,612,605`
  - `总收益 = 1206.30%`
  - `最大回撤 = -37.34%`
  - `Sharpe = 0.984`
  - `总滑点 = 355,230`
  - `总交易次数 = 1169`
- `selection_pairwise_v2 @ array_manager_size_floor = 120`
  - `期末权益 = 2,624,635`
  - `总收益 = 1212.32%`
  - `最大回撤 = -37.34%`
  - `Sharpe = 0.986`
  - `总滑点 = 355,440`
  - `总交易次数 = 1169`

## 修改的回测结果

- 对照 `array_manager_size_floor = 140` 的当前默认结果：
  - `ungated_baseline`
    - `期末权益 = 464,320`
    - `总收益 = 132.16%`
    - `最大回撤 = -52.86%`
    - `Sharpe = 0.254`
    - `总滑点 = 103,795`
    - `总交易次数 = 828`
  - `selection_pairwise_v2`
    - `期末权益 = 460,330`
    - `总收益 = 130.17%`
    - `最大回撤 = -53.76%`
    - `Sharpe = 0.251`
    - `总滑点 = 101,985`
    - `总交易次数 = 824`

## 新增的分析结果

- 在同一份当前代码里，仅仅把 `array_manager_size_floor` 从 `140` 回放到 `120`：
  - `ungated_baseline` 就精确回到了第27阶段那组历史结果
  - `selection_pairwise_v2` 也精确回到了第27阶段那组历史结果
- 这说明：
  - 第27阶段和第31阶段之间的巨大断层
  - 主因不是数据库、不是回测区间、不是用户记忆偏差
  - 而就是：
    - 我们后面为了修 AI 运行时特征
    - 把主策略共用的 `ArrayManager` 从 `120` 全局抬到了 `140`
    - 结果把主策略定义本身也一起改坏了

## 删除的回测结果

- 无

## 我的判断

- 第32阶段已经把因果关系锁死了：
  - 不是“第27阶段结果可疑”
  - 也不是“第31阶段数据不对”
  - 而是两者对应的是不同的主策略运行口径
- 更本质地说：
  - `am120` 能保住主策略原本那条高收益资金曲线
  - `am140` 能让 AI 运行时特征不再塌成零
  - 但把这两件事粗暴合并在同一个共享 `ArrayManager` 上，是错误设计

## 快速结论

- 现在真正的设计结论已经清楚：
  - `ArrayManager = 120` 才是当前主策略历史有效口径
  - AI 运行时如果需要更深历史，应该走独立历史供给
  - 不应再通过全局抬高主策略共享历史窗口来修
- 也就是说：
  - 第27阶段那组一千多收益的非 AI 基线是对的
  - 第31阶段那组一百多收益并不是“新发现”
  - 而是一次错误修法把主策略定义带偏后的结果

# 2026-04-24 01:23 第33阶段 正确修法落地：主策略恢复 am120，AI 改走独立历史

## 版本改动

- 改动时间点：`2026-04-24 01:23`
- 修改的文件：
  - `examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
  - `examples/portfolio_backtesting/qmt_roll_ai_selection_pairwise_runtime.py`
  - `memory.md`
- 改动内容：
  - 把主策略默认 `array_manager_size_floor` 恢复为 `120`
  - 保留该参数仅用于审计/实验，不再把 `140` 作为正式默认
  - `pairwise` 运行时不再依赖共享 `ArrayManager` 提供全部历史
  - 改为优先基于 `contract_vt_symbol` 直接加载独立合约日线历史，单独构造运行时特征
  - 同时补齐了 `target_contract` 为字符串时的兼容逻辑，以及历史日期比较的类型兼容

## 参数变化说明

- 新增的参数：
  - 无
- 修改的参数：
  - `array_manager_size_floor` 默认值从 `140` 恢复为 `120`
- 删除的参数：
  - 无

## 修改的回测结果

- 使用正确修法后，标准完整脚本重新回到第27阶段同口径结果：
  - `ungated_baseline`
    - `期末权益 = 2,612,605`
    - `总收益 = 1206.30%`
    - `最大回撤 = -37.34%`
    - `Sharpe = 0.984`
    - `总滑点 = 355,230`
    - `总交易次数 = 1169`
  - `selection_pairwise_v2`
    - `期末权益 = 2,624,635`
    - `总收益 = 1212.32%`
    - `最大回撤 = -37.34%`
    - `Sharpe = 0.986`
    - `总滑点 = 355,440`
    - `总交易次数 = 1169`
  - `selection_pairwise_v2_catastrophic_veto_v1`
    - `期末权益 = 2,624,635`
    - `总收益 = 1212.32%`
    - `最大回撤 = -37.34%`
    - `Sharpe = 0.986`
    - `总滑点 = 355,440`
    - `总交易次数 = 1169`

## 新增的分析结果

- 这次修法后的正式候选快照显示：
  - `selection_pairwise_enabled = 230`
  - `selection_pairwise_veto_flag = 5`
  - `selection_pairwise_runtime_veto_match_local = 5`
  - `selection_pairwise_feature_ret_20d_zscore_120` 不再全零
- 说明现在已经同时满足两件事：
  - 主策略回到原来有效的 `am120` 历史口径
  - AI 运行时特征也恢复到正确口径
- 但正式资金结果继续说明：
  - `soft veto` 即使已经真实触发
  - 仍然没有带来额外边际收益

## 删除的回测结果

- 无

## 我的判断

- 第33阶段才是这轮问题的真正闭环：
  - 不是简单把 `140` 改回 `120`
  - 也不是简单承认 AI 特征会塌零
  - 而是把两条本来冲突的需求拆开：
    - 主策略继续用历史有效口径
    - AI 运行时单独补历史
- 这样做之后：
  - 非 AI 基线恢复到你记忆里的那组一千多收益
  - AI 分支也恢复到之前相对基线小幅正向的结果

## 快速结论

- 当前正确的正式主结论应恢复为：
  - `ungated_baseline = 1206.30%`
  - `selection_pairwise_v2 = 1212.32%`
  - `soft veto` 依然无额外价值
- 后续若继续研究 AI：
  - 应该沿 `pairwise_v2` 主线继续
  - 但不要再通过修改主策略共享 `ArrayManager` 来满足 AI 特征需求

# 2026-04-24 01:47 第34阶段 pairwise 同日仓位倾斜实验

## 版本改动

- 改动时间点：`2026-04-24 01:47`
- 修改的文件：
  - `examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
  - `memory.md`
- 改动内容：
  - 新增实验开关 `enable_selection_pairwise_v2_volume_tilt`
  - 新增实验参数 `selection_pairwise_volume_tilt_strength`
  - 新方案不是继续改入选集合
  - 而是在`同日多个已开仓候选`里，按 `pairwise` 排名做对称式仓位倾斜：
    - top rank 稍微加仓
    - bottom rank 稍微减仓
    - 平均权重保持在 `1`

## 参数变化说明

- 新增的参数：
  - `enable_selection_pairwise_v2_volume_tilt`
  - `selection_pairwise_volume_tilt_strength`
- 修改的参数：
  - 无
- 删除的参数：
  - 无

## 新增的分析结果

- 当前正式主回测里，`pairwise_v2` 真正改变开仓集合的只有：
  - `2` 个交易日
  - `4` 条候选状态变化
- 这说明：
  - 当前 rank-only 接入方式天然杠杆过低
  - 更有潜力的方向是“同日已开仓候选之间的仓位重分配”
- 进一步分析训练标签后发现：
  - 在同日多个已开仓候选里，top-bottom 平均 `20d R` 差值为正
  - 但胜率不到一半，属于“少数大胜、很多小负”的结构
  - 更适合做温和仓位倾斜，不适合做简单硬决策

## 新增的回测结果

- `selection_pairwise_v2_volume_tilt_v015`
  - `期末权益 = 2,652,200`
  - `总收益 = 1226.10%`
  - `最大回撤 = -37.20%`
  - `Sharpe = 0.989`
  - `总滑点 = 352,240`
  - `总交易次数 = 1169`
- `selection_pairwise_v2_volume_tilt_v020`
  - `期末权益 = 2,563,020`
  - `总收益 = 1181.51%`
  - `最大回撤 = -37.75%`
  - `Sharpe = 0.958`
  - `总滑点 = 350,970`
  - `总交易次数 = 1172`
- `selection_pairwise_v2_volume_tilt_v025`
  - `期末权益 = 2,703,930`
  - `总收益 = 1251.97%`
  - `最大回撤 = -37.13%`
  - `Sharpe = 0.996`
  - `总滑点 = 354,170`
  - `总交易次数 = 1171`
- `selection_pairwise_v2_volume_tilt_v035`
  - `期末权益 = 2,751,390`
  - `总收益 = 1275.69%`
  - `最大回撤 = -35.83%`
  - `Sharpe = 1.018`
  - `总滑点 = 351,110`
  - `总交易次数 = 1169`

## 修改的回测结果

- 对照 `selection_pairwise_v2` 基线：
  - `期末权益 = 2,624,635`
  - `总收益 = 1212.32%`
  - `最大回撤 = -37.34%`
  - `Sharpe = 0.986`
  - `总滑点 = 355,440`
  - `总交易次数 = 1169`
- 相比 `pairwise_v2`：
  - `v015`：
    - `期末权益 +27,565`
    - `总收益 +13.78%`
    - `最大回撤改善 0.14 个百分点`
    - `Sharpe +0.003`
  - `v025`：
    - `期末权益 +79,295`
    - `总收益 +39.65%`
    - `最大回撤改善 0.21 个百分点`
    - `Sharpe +0.010`
  - `v035`：
    - `期末权益 +126,755`
    - `总收益 +63.38%`
    - `最大回撤改善 1.51 个百分点`
    - `Sharpe +0.032`
  - `v020`：
    - 明显劣于 `pairwise_v2`

## 删除的回测结果

- 无

## 我的判断

- 第34阶段第一次给出了一条比 `rank-only` 更值得继续的 AI 主线：
  - 同日仓位倾斜
- 但结果也说明这条线不能简单按“强度越大越好”来理解：
  - `0.15`、`0.25`、`0.35` 都比 `pairwise_v2` 好
  - `0.20` 却反而更差
  - 说明这里存在明显的整数手数阈值和权益路径反馈
- 从穿越周期角度看：
  - `0.35` 全样本最好
  - 但 `since_2024` 变成了负收益
  - 激进强度不够稳
  - `0.15` 更像保守且跨窗口更平衡的版本

## 快速结论

- `pairwise` 这条线并没有走到头
- 只是当前最优研究方向已经从：
  - “替换谁”
  - 转向了：
  - “同日已开仓候选怎么分配仓位”
- 如果现在要给一个更稳的下一步方向：
  - 优先继续沿 `volume_tilt` 主线
  - 首先考虑 `0.15` 这种保守强度
  - 而不是直接用 `0.35` 这种全样本最强但窗口波动更大的版本

# 2026-04-24 02:39 第35阶段 directional volume tilt 根因修复与正式复核

## 版本改动

- 改动时间点：`2026-04-24 02:39`
- 修改的文件：
  - `examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
  - `back_log.md`
  - `memory.md`
- 改动内容：
  - 修复 `directional volume tilt` 的一个真实逻辑错误
  - 原来的 `_apply_selection_pairwise_volume_tilt` 会先检查全局 `selection_pairwise_volume_tilt_strength`
  - 当 directional 实验把全局强度显式设成 `0.0`、仅使用 `selection_pairwise_volume_tilt_long_strength/short_strength` 时
  - 函数会在解析方向强度前提前 `return`
  - 导致之前“directional tilt 完全不生效”的结论是伪结论
  - 修复后，先解析 long/short 实际生效强度，再判断是否整体为 `0`
  - 同时继续保留运行时快照诊断字段，验证策略现场是否真的触发了仓位倾斜

## 参数变化说明

- 新增的参数：
  - 无
- 修改的参数：
  - 无
- 删除的参数：
  - 无

## 新增的分析结果

- `directional tilt` 之前失效，不是引擎没有把参数写进策略
- 也不是 `pairwise` 运行时没有进入正式链路
- 根因就是策略内部的提前返回写错了
- 修复后，`long015` 诊断快照里：
  - `selection_pairwise_volume_tilt_applied = 159`
  - 已开仓候选里实际改手数的有 `86` 行
  - 覆盖 `56` 个交易日
- 修复后，`short035` 正式快照里：
  - 已开仓候选实际改手数 `34` 行
  - 覆盖 `16` 个交易日
- 修复后，`global035` 正式快照里：
  - 已开仓候选实际改手数 `155` 行
  - 覆盖 `81` 个交易日
  - 其中 `long = 121` 行、`short = 34` 行
- 这说明当前 `volume tilt` 的主贡献明显来自`多头侧倾斜`
- 空头侧并非完全无效，但边际远弱于多头侧
- 同时，第34阶段的 `global v015 / v025 / v035` 结果已经在当前正确代码口径下重新复现
- 说明第34阶段主结论本身是对的
- 错的是后面把 directional 假失效当成策略层结论

## 新增的回测结果

- `selection_pairwise_v2_volume_tilt_long015_diag3`
  - `期末权益 = 2,677,845`
  - `总收益 = 1238.92%`
  - `最大回撤 = -37.20%`
  - `Sharpe = 0.992`
  - `总滑点 = 354,830`
  - `总交易次数 = 1169`
- `selection_pairwise_v2_volume_tilt_global035_fix1`
  - `期末权益 = 2,751,390`
  - `总收益 = 1275.69%`
  - `最大回撤 = -35.83%`
  - `Sharpe = 1.018`
  - `总滑点 = 351,110`
  - `总交易次数 = 1169`
- `selection_pairwise_v2_volume_tilt_short035_fix1`
  - `期末权益 = 2,631,755`
  - `总收益 = 1215.88%`
  - `最大回撤 = -37.34%`
  - `Sharpe = 0.990`
  - `总滑点 = 352,260`
  - `总交易次数 = 1169`
- `selection_pairwise_v2_volume_tilt_long015_short035_fix1`
  - `期末权益 = 2,681,480`
  - `总收益 = 1240.74%`
  - `最大回撤 = -37.20%`
  - `Sharpe = 0.996`
  - `总滑点 = 351,640`
  - `总交易次数 = 1169`

## 修改的回测结果

- `selection_pairwise_v2_volume_tilt_long015`
  - 之前错误结论：与 `pairwise_v2` 完全相同
  - 修复后正确结果：
    - `期末权益 = 2,677,845`
    - `总收益 = 1238.92%`
    - `最大回撤 = -37.20%`
    - `Sharpe = 0.992`
    - `总滑点 = 354,830`
    - `总交易次数 = 1169`
- `selection_pairwise_v2_volume_tilt_short035`
  - 之前错误结论：与 `pairwise_v2` 完全相同
  - 修复后正确结果：
    - `期末权益 = 2,631,755`
    - `总收益 = 1215.88%`
    - `最大回撤 = -37.34%`
    - `Sharpe = 0.990`
    - `总滑点 = 352,260`
    - `总交易次数 = 1169`

## 删除的回测结果

- 无

## 我的判断

- 第35阶段最关键的不是“又找到一组更好数字”
- 而是把一个会误导后续研究方向的伪结论纠正了：
  - `directional tilt` 并没有失效
  - 是代码提前返回把它短路了
- 修复后看正式资金结果：
  - `long015` 明显优于 `pairwise_v2`
  - `short035` 只有小幅边际改善
  - `long015 + short035` 比单独 `long015` 略强一点
  - 但最强全样本结果仍然是第34阶段已经验证过的 `global035`
- 从穿越周期和稳健性角度看：
  - 现在真正值得继续深耕的是`多头侧主导的仓位倾斜`
  - 而不是把 long/short 完全对称看待

# 2026-04-24 09:40 第36阶段 long015 与 long015+short035 分窗验证

## 版本改动

- 改动时间点：`2026-04-24 09:40`
- 修改的文件：
  - `back_log.md`
  - `memory.md`
- 改动内容：
  - 没有再改策略逻辑
  - 这一步专门做修复后 `directional tilt` 的正式分窗验证
  - 只验证当前最值得继续推进的两组：
    - `long015`
    - `long015 + short035`
  - 核心目标不是再看全样本是否更高
  - 而是判断它们是否真的符合“穿越周期”的要求

## 参数变化说明

- 新增的参数：
  - 无
- 修改的参数：
  - 无
- 删除的参数：
  - 无

## 新增的分析结果

- `long015` 的分窗表现相对均衡：
  - `since_2021` 明显优于 `pairwise_v2`
  - `since_2022`、`since_2023` 仍保持小幅正向
  - `since_2025` 提升明显
  - 只有 `since_2024` 轻微变差
  - `since_2026` 基本持平
- `long015 + short035` 的问题也被正式确认：
  - 全样本比 `long015` 再高一点
  - `since_2022` 也明显更强
  - 但 `since_2023` 出现显著恶化
    - 期末权益相对基线 `-67,220`
    - 总收益相对基线 `-33.61%`
    - 最大回撤恶化 `6.82` 个百分点
    - Sharpe `-0.0716`
- 这说明：
  - `short035` 不是单纯“加一点就更好”
  - 它会把组合带向更强的年份依赖
  - 不满足当前“能穿越周期”的要求

## 新增的回测结果

- `selection_pairwise_v2_volume_tilt_long015_sweep_fix1`
  - `期末权益 = 2,677,845`
  - `总收益 = 1238.92%`
  - `最大回撤 = -37.20%`
  - `Sharpe = 0.992`
  - `总滑点 = 354,830`
  - `总交易次数 = 1169`
- `selection_pairwise_v2_volume_tilt_long015_short035_sweep_fix1`
  - `期末权益 = 2,681,480`
  - `总收益 = 1240.74%`
  - `最大回撤 = -37.20%`
  - `Sharpe = 0.996`
  - `总滑点 = 351,640`
  - `总交易次数 = 1169`

## 修改的回测结果

- 无

## 删除的回测结果

- 无

## 我的判断

- 如果只看全样本：
  - `long015 + short035` 比 `long015` 略高
- 但如果按“穿越周期”标准判断：
  - `long015` 才是更值得推进的版本
  - 因为它的提升分布更均衡
  - 没有出现某个关键窗口被明显打坏的情况
- 当前这条线的最优判断应该收敛成：
  - `long side tilt` 是主线
  - `short side tilt` 暂时不应该进入正式版本
  - 后续若继续做正式候选，应优先从 `long015` 出发

# 2026-04-24 09:53 第37阶段 long015 正式候选版本对照回测

## 版本改动

- 改动时间点：`2026-04-24 09:53`
- 修改的文件：
  - `examples/portfolio_backtesting/run_qmt_roll_selection_pairwise_long015_backtest.py`
  - `back_log.md`
  - `memory.md`
- 改动内容：
  - 新增 `long015` 的正式候选对照脚本
  - 用标准入口把三组放到同一张正式汇总表里：
    - `ungated_baseline`
    - `selection_pairwise_v2`
    - `selection_pairwise_v2_volume_tilt_long015`
  - 目标是判断 `long015` 是否已经达到“比当前 pairwise 正式版更值得推进”的程度

## 参数变化说明

- 新增的参数：
  - 无
- 修改的参数：
  - 无
- 删除的参数：
  - 无

## 新增的分析结果

- `long015` 的正式候选结论已经成立：
  - 相对 `ungated_baseline` 明显更优
  - 相对当前 `selection_pairwise_v2` 也继续正向
  - 且没有增加交易次数
- 相对 `ungated_baseline`：
  - `期末权益 +65,240`
  - `总收益 +32.62%`
  - `最大回撤改善 0.14` 个百分点
  - `Sharpe +0.0081`
  - `总滑点 -400`
- 相对 `selection_pairwise_v2`：
  - `期末权益 +53,210`
  - `总收益 +26.61%`
  - `最大回撤改善 0.14` 个百分点
  - `Sharpe +0.0060`
  - `总滑点 -610`
- 这说明：
  - `long015` 已经不只是研究上“有启发”
  - 而是`正式版本候选`意义上的正向改进

## 新增的回测结果

- `ungated_baseline`
  - `期末权益 = 2,612,605`
  - `总收益 = 1206.30%`
  - `最大回撤 = -37.34%`
  - `Sharpe = 0.984`
  - `总滑点 = 355,230`
  - `总交易次数 = 1169`
- `selection_pairwise_v2`
  - `期末权益 = 2,624,635`
  - `总收益 = 1212.32%`
  - `最大回撤 = -37.34%`
  - `Sharpe = 0.986`
  - `总滑点 = 355,440`
  - `总交易次数 = 1169`
- `selection_pairwise_v2_volume_tilt_long015`
  - `期末权益 = 2,677,845`
  - `总收益 = 1238.92%`
  - `最大回撤 = -37.20%`
  - `Sharpe = 0.992`
  - `总滑点 = 354,830`
  - `总交易次数 = 1169`

## 修改的回测结果

- 无

## 删除的回测结果

- 无

## 我的判断

- 到第37阶段，`long015` 已经从“研究分支”升级成了“当前最优正式候选版本”
- 现在如果要给出主版本推进顺序：
  1. `selection_pairwise_v2_volume_tilt_long015`
  2. `selection_pairwise_v2`
  3. `ungated_baseline`
- 也就是说：
  - `pairwise` 主线保留
  - `catastrophic veto` 继续关闭
  - `short side tilt` 暂不进入正式版本
  - 当前最值得推进的正式组合，就是 `pairwise_v2 + long015`

# 2026-04-24 10:01 第38阶段 long015 随机收益检验：block bootstrap 与 rolling window

## 版本改动

- 改动时间点：`2026-04-24 10:01`
- 修改的文件：
  - `examples/portfolio_backtesting/analyze_qmt_roll_selection_pairwise_long015_bootstrap.py`
  - `back_log.md`
  - `memory.md`
- 改动内容：
  - 新增 `long015` 相对 `pairwise_v2` 的统计检验脚本
  - 不再只看全样本和分窗结果
  - 直接对日度 `delta_net_pnl` 做：
    - `moving block bootstrap`
    - `rolling window` 稳定性统计

## 参数变化说明

- 新增的参数：
  - 无
- 修改的参数：
  - 无
- 删除的参数：
  - 无

## 新增的分析结果

- 观测到的 `long015 - pairwise_v2` 全样本净增益：
  - `delta_net_pnl = +53,210`
  - 平均日度增益 `+34.89`
- `block bootstrap` 结果：
  - `5` 日块：
    - 正收益概率 `81.0%`
    - `p05 = -43,381`
  - `20` 日块：
    - 正收益概率 `86.32%`
    - `p05 = -26,181`
  - `60` 日块：
    - 正收益概率 `86.30%`
    - `p05 = -22,646`
- 这说明：
  - `long015` 不是只靠极少数孤立交易日抬出来的纯噪声结果
  - 但也没有强到可以说“已经完全排除随机性”
  - 它更像一个`中等强度、带统计优势但仍需克制看待`的改进
- `rolling window` 结果：
  - `126` 日窗口：
    - 终值更优占比 `54.93%`
    - 总收益更优占比 `49.29%`
    - 回撤更优占比 `65.50%`
  - `252` 日窗口：
    - 终值更优占比 `58.95%`
    - 总收益更优占比 `62.01%`
    - 回撤更优占比 `70.96%`
  - `504` 日窗口：
    - 终值更优占比 `73.48%`
    - 总收益更优占比 `85.81%`
    - 回撤更优占比 `80.23%`
- 这进一步说明：
  - `long015` 的优势在短窗口上不算碾压
  - 但窗口拉长后，正向占比明显提升
  - 所以它更像`偏稳态的结构改进`
  - 而不是短线爆发型 alpha

## 新增的回测结果

- 无

## 修改的回测结果

- 无

## 删除的回测结果

- 无

## 我的判断

- 如果只问一句“这点增益是不是随机收益”：
  - 我的答案仍然不是“确定不是”
  - 但现在已经可以更严谨地说：
    - `long015` 不是明显的纯随机假增益
    - 也还没强到可以说是高度确定的统计优势
- 当前最准确的定性应该是：
  - `中等强度、跨长窗口更稳、短窗口不碾压` 的改进
- 这和前面的工程结论是统一的：
  - 它足够值得进入正式候选版本
  - 但还不该被神化成压倒性 alpha

# 2026-04-24 10:29 第39阶段 conditional long015：按 score gap 条件化验证

## 版本改动

- 改动时间点：`2026-04-24 10:29`
- 修改的文件：
  - `examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
  - `examples/portfolio_backtesting/run_qmt_roll_selection_pairwise_long015_conditional_backtest.py`
  - `back_log.md`
  - `memory.md`
- 改动内容：
  - 新增 `selection_pairwise_volume_tilt_min_score_gap`
  - 让 `long015` 只有在同日 long 组内 `pairwise score gap` 足够大时才触发
  - 同时把 `group_size / score_gap / top_gap` 透传进候选快照，方便后续继续定位
  - 正式验证两档条件化版本：
    - `gap010`
    - `gap020`

## 参数变化说明

- 新增的参数：
  - `selection_pairwise_volume_tilt_min_score_gap`
- 修改的参数：
  - 无
- 删除的参数：
  - 无

## 新增的分析结果

- 从事件级分析看：
  - `score_gap <= 0.20` 的 tilt 事件平均表现确实偏弱
  - `score_gap > 0.20` 的事件整体更好
- 但把这个条件直接接回正式策略后，结果并没有更好
- 说明问题的本质不是：
  - “低 gap 事件天然有害”
- 而更像是：
  - 这些低 gap 事件虽然弱
  - 但简单删掉它们，并不能改善组合层的真实资金路径
  - 反而会稀释 `long015` 原本已经成立的正向增益

## 新增的回测结果

- `selection_pairwise_v2_volume_tilt_long015_gap010`
  - `期末权益 = 2,668,575`
  - `总收益 = 1234.29%`
  - `最大回撤 = -37.20%`
  - `Sharpe = 0.990`
  - `总滑点 = 355,010`
  - `总交易次数 = 1169`
- `selection_pairwise_v2_volume_tilt_long015_gap020`
  - `期末权益 = 2,669,375`
  - `总收益 = 1234.69%`
  - `最大回撤 = -37.17%`
  - `Sharpe = 0.990`
  - `总滑点 = 355,020`
  - `总交易次数 = 1169`

## 修改的回测结果

- 无

## 删除的回测结果

- 无

## 我的判断

- `conditional long015` 这条“按 score gap 做硬条件过滤”的支线，当前可以先收住
- 因为正式结果已经说明：
  - `gap010`、`gap020` 都跑不过原始 `long015`
  - 也没有实质性改善回撤结构
- 所以当前结论继续保持不变：
  - `long015` 原版仍然是最优正式候选
  - `score gap` 条件化这个具体方向，不值得继续细抠阈值
