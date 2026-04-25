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

# 2026-04-24 12:20 第40阶段 cooldown3：序列型状态过滤验证

## 版本改动

- 改动时间点：`2026-04-24 12:20`
- 修改的文件：
  - `examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
  - `examples/portfolio_backtesting/run_qmt_roll_selection_pairwise_long015_cooldown_backtest.py`
  - `back_log.md`
  - `memory.md`
- 改动内容：
  - 基于失败簇分析，新增 `selection_pairwise_volume_tilt_cooldown_days`
  - 尝试验证一种更偏序列状态的过滤：
    - 如果近期已经发生过 long tilt
    - 则短时间内的新 tilt 机会先冷却
  - 正式验证 `cooldown3`

## 参数变化说明

- 新增的参数：
  - `selection_pairwise_volume_tilt_cooldown_days`
- 修改的参数：
  - 无
- 删除的参数：
  - 无

## 新增的分析结果

- `cooldown3` 并没有改善 `long015`
- 相反，它把原本已经成立的 alpha 再次稀释了
- 说明：
  - 失败簇里存在连续事件，不代表“加冷却期”就是正确修法
  - 序列现象是真存在的
  - 但把它直接翻译成硬规则后，组合层收益会受损

## 新增的回测结果

- `selection_pairwise_v2_volume_tilt_long015_cooldown3`
  - `期末权益 = 2,656,690`
  - `总收益 = 1228.35%`
  - `最大回撤 = -37.20%`
  - `Sharpe = 0.990`
  - `总滑点 = 352,190`
  - `总交易次数 = 1175`

## 修改的回测结果

- 无

## 删除的回测结果

- 无

## 我的判断

- 到第40阶段，结论已经足够明确：
  - `long015` 原版仍然是最优正式候选
  - `score gap` 条件化失败
  - `cooldown3` 也失败
- 这意味着：
  - 继续在 `long015` 上叠加局部条件过滤，当前已经进入边际递减区
  - 再往下挖，大概率只会进一步过拟合
- 所以后续更合理的选择不是继续细化规则
- 而是：
  - 暂时接受 `long015` 作为当前最优解
  - 把研究重心转向新的上层方向

# 2026-04-24 13:04 第41阶段 long015：上层过热状态过滤验证

## 版本改动

- 改动时间点：`2026-04-24 13:04`
- 修改的文件：
  - `examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
  - `examples/portfolio_backtesting/analyze_qmt_roll_selection_pairwise_long015_state_filter.py`
  - `examples/portfolio_backtesting/run_qmt_roll_selection_pairwise_long015_state_backtest.py`
  - `back_log.md`
  - `memory.md`
- 改动内容：
  - 不再继续细抠 `score gap / cooldown` 这类局部规则
  - 改为把 `long015` 的 long-side 倾斜事件提升到“上层状态”分析：
    - 先对真实发生的 long tilt 事件做未来 `5/10/20` 日 `delta_net_pnl` 分解
    - 再从事件级里筛选最像“过热失效”的状态量
  - 新增 long-side 两个正式状态参数：
    - `selection_pairwise_volume_tilt_long_max_avg_ret20_zscore`
    - `selection_pairwise_volume_tilt_long_max_avg_rsi`
  - 在正式策略里验证 3 条上层状态过滤分支：
    - `ret20cap075`
    - `rsi68`
    - `ret20cap075 + rsi68`

## 参数变化说明

- 新增的参数：
  - `selection_pairwise_volume_tilt_long_max_avg_ret20_zscore`
  - `selection_pairwise_volume_tilt_long_max_avg_rsi`
- 修改的参数：
  - 无
- 删除的参数：
  - 无

## 新增的分析结果

- `long015` 的 long tilt 事件共 `56` 个交易日、`86` 行候选改手数
- 事件级未来 `20` 日分解里，最像“不过热更好”的信号主要有两类：
  - `avg_ret20_zscore <= 0.748563`
  - `avg_rsi <= 63.843676 / 67.526386`
- 但事件级最优不等于正式组合层最优
- 正式验证结果说明：
  - `ret20cap075` 真实会生效，但会把 `long015` 的主要 alpha 一起削弱
  - `rsi68` 在正式策略里完全不改变结果，属于非绑定条件
  - `ret20cap075 + rsi68` 与 `ret20cap075` 完全一致，说明组合里真正起作用的只有 `ret20cap075`

## 新增的回测结果

- `selection_pairwise_v2_volume_tilt_long015_ret20cap075`
  - `期末权益 = 2,635,250`
  - `总收益 = 1217.63%`
  - `最大回撤 = -37.16%`
  - `Sharpe = 0.981`
  - `总滑点 = 355,440`
  - `总交易次数 = 1175`
- `selection_pairwise_v2_volume_tilt_long015_rsi68`
  - `期末权益 = 2,677,845`
  - `总收益 = 1238.92%`
  - `最大回撤 = -37.20%`
  - `Sharpe = 0.992`
  - `总滑点 = 354,830`
  - `总交易次数 = 1169`
- `selection_pairwise_v2_volume_tilt_long015_ret20cap075_rsi68`
  - `期末权益 = 2,635,250`
  - `总收益 = 1217.63%`
  - `最大回撤 = -37.16%`
  - `Sharpe = 0.981`
  - `总滑点 = 355,440`
  - `总交易次数 = 1175`

## 修改的回测结果

- 无

## 删除的回测结果

- 无

## 我的判断

- 到第41阶段，这条“上层过热过滤”支线已经可以收口：
  - `ret20cap075` 虽然比纯 `pairwise_v2` 还略好
  - 但明显跑不过原始 `long015`
  - `rsi68` 则完全没有边际影响
- 这说明：
  - 事件级的“过热失效”现象是真有的
  - 但把它直接翻成正式 long-side 硬过滤后，组合层收益会被稀释
  - `avg_rsi` 这条看起来合理的状态条件，在正式链路里甚至连绑定都没形成
- 当前正式候选顺序保持不变：
  - `selection_pairwise_v2 + long015`
  - `selection_pairwise_v2`
  - `ungated_baseline`
- 后续如果继续深挖，不该再围绕 `long015` 叠加新的局部状态过滤
- 这一层已经出现与前面 `score gap / cooldown` 同样的边际递减迹象

# 2026-04-24 13:26 第42阶段 long015：连续置信度缩放验证

## 版本改动

- 改动时间点：`2026-04-24 13:26`
- 修改的文件：
  - `examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
  - `examples/portfolio_backtesting/run_qmt_roll_selection_pairwise_long015_confidence_backtest.py`
  - `back_log.md`
  - `memory.md`
- 改动内容：
  - 不再使用 `score gap` 硬过滤
  - 新增 long-side 连续置信度缩放参数：
    - `selection_pairwise_volume_tilt_long_score_gap_reference`
  - 让 `long015` 的实际 tilt 强度按 `score_gap / reference` 连续缩放
  - 正式验证两档：
    - `gapref025`
    - `gapref050`

## 参数变化说明

- 新增的参数：
  - `selection_pairwise_volume_tilt_long_score_gap_reference`
- 修改的参数：
  - 无
- 删除的参数：
  - 无

## 新增的分析结果

- 连续缩放比硬过滤更符合第一性原理：
  - 保留 `long015` 的主体结构
  - 在低置信度日期自动收缩，而不是直接一刀切掉
- 但正式结果仍然说明：
  - `gapref025` 只是部分保住了 `long015` 的收益
  - `gapref050` 则明显过度收缩，正式收益进一步退步
- 这意味着：
  - “弱置信度缩手”这个方向不是完全错
  - 但当前这套 `score gap` 口径，仍不足以构成优于原始 `long015` 的正式增强项

## 新增的回测结果

- `selection_pairwise_v2_volume_tilt_long015_gapref025`
  - `期末权益 = 2,668,655`
  - `总收益 = 1234.33%`
  - `最大回撤 = -37.17%`
  - `Sharpe = 0.990`
  - `总滑点 = 355,020`
  - `总交易次数 = 1169`
- `selection_pairwise_v2_volume_tilt_long015_gapref050`
  - `期末权益 = 2,641,935`
  - `总收益 = 1220.97%`
  - `最大回撤 = -37.13%`
  - `Sharpe = 0.986`
  - `总滑点 = 355,050`
  - `总交易次数 = 1173`

## 修改的回测结果

- 无

## 删除的回测结果

- 无

## 我的判断

- 第42阶段的结论是：
  - 连续缩放优于前面的 `score gap` 硬过滤
  - 但仍然跑不过原始 `long015`
- 具体看：
  - `gapref025` 相对 `long015` 少了 `9,190` 权益、`4.595%` 总收益、`0.0027` Sharpe
  - `gapref050` 退步更明显
- 所以当前排序仍然不变：
  - `selection_pairwise_v2 + long015`
  - `selection_pairwise_v2 + gapref025`
  - `selection_pairwise_v2`
  - `ungated_baseline`
- 这条线的真正价值在于：
  - 它证明“平滑收缩”比“硬过滤”更接近对的方向
  - 但当前基于 `score gap` 的置信度度量还不够强
- 后续如果继续深挖：
  - 可以保留“连续缩放”这个方法论
  - 但不该继续死抠 `score gap` 本身

# 2026-04-24 13:56 第43阶段 long015：组合拥挤度连续缩放验证

## 版本改动

- 改动时间点：`2026-04-24 13:56`
- 修改的文件：
  - `examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
  - `examples/portfolio_backtesting/run_qmt_roll_selection_pairwise_long015_crowding_backtest.py`
  - `back_log.md`
  - `memory.md`
- 改动内容：
  - 从事件级复盘中，发现 `long015` 的增益更偏向“组合不拥挤”的状态：
    - 高 `active_ratio` 反而显著拖累未来 `20` 日增益
  - 新增 long-side 拥挤度连续缩放参数：
    - `selection_pairwise_volume_tilt_long_active_ratio_full_strength_max`
  - 当组合当前持仓占用高于阈值时，连续缩小 long tilt 强度
  - 正式验证两档：
    - `crowd0375`
    - `crowd025`

## 参数变化说明

- 新增的参数：
  - `selection_pairwise_volume_tilt_long_active_ratio_full_strength_max`
- 修改的参数：
  - 无
- 删除的参数：
  - 无

## 新增的分析结果

- 事件级分解显示：
  - `active_ratio` 最高分位的 long tilt 事件，未来 `20` 日均值明显为负
  - 低拥挤状态更容易保留 `long015` 的正向边际
- 正式回测结果说明：
  - 组合拥挤度缩放比前面的 `score gap` 连续缩放更接近“组合层本质”
  - 但当前仍然跑不过原始 `long015`
  - 两档 `crowd0375 / crowd025` 结果完全一样
  - 说明当前真实生效的拥挤状态命中集合在这两个阈值下没有被进一步区分开

## 新增的回测结果

- `selection_pairwise_v2_volume_tilt_long015_crowd0375`
  - `期末权益 = 2,656,730`
  - `总收益 = 1228.37%`
  - `最大回撤 = -37.33%`
  - `Sharpe = 0.996`
  - `总滑点 = 352,630`
  - `总交易次数 = 1171`
- `selection_pairwise_v2_volume_tilt_long015_crowd025`
  - `期末权益 = 2,656,730`
  - `总收益 = 1228.37%`
  - `最大回撤 = -37.33%`
  - `Sharpe = 0.996`
  - `总滑点 = 352,630`
  - `总交易次数 = 1171`

## 修改的回测结果

- 无

## 删除的回测结果

- 无

## 我的判断

- 第43阶段说明：
  - “组合拥挤时少偏一点”这个方向，比“按 score gap 调置信度”更接近本质
  - 但当前版本还没有超过原始 `long015`
- 具体看：
  - 相对 `long015`，`crowd0375 / crowd025` 少了 `21,115` 权益、`10.5575%` 总收益
  - 但 `Sharpe` 反而提升了 `0.0032`
  - 这说明它更像“收益换了一点平滑度”，不是主收益增强
- 所以当前正式顺序仍然保持：
  - `selection_pairwise_v2 + long015`
  - `selection_pairwise_v2 + long015_crowding`
  - `selection_pairwise_v2 + gapref025`
  - `selection_pairwise_v2`
  - `ungated_baseline`
- 后续如果继续主导这条线：
  - 我会优先把“组合层拥挤度”保留为方法论备选
  - 但不会把当前 `crowding` 版本直接升格为正式候选第一名

# 2026-04-24 14:30 第44阶段 long015：基础仓位浓度连续缩放验证

## 版本改动

- 改动时间点：`2026-04-24 14:30`
- 修改的文件：
  - `examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
  - `examples/portfolio_backtesting/run_qmt_roll_selection_pairwise_long015_base_volume_backtest.py`
  - `back_log.md`
  - `memory.md`
- 改动内容：
  - 在继续研究组合层状态时，不再盯拥挤度阈值本身
  - 转向更直接的风险集中度问题：
    - 如果某次 tilt 的基础手数本来就很大
    - 再继续放大，是否反而会过度集中
  - 新增 long-side 基础仓位浓度连续缩放参数：
    - `selection_pairwise_volume_tilt_long_base_volume_reference`
  - 用 `avg_base_volume_before` 相对参考值连续收缩实际 tilt 强度
  - 正式验证两档：
    - `volref20`
    - `volref30`

## 参数变化说明

- 新增的参数：
  - `selection_pairwise_volume_tilt_long_base_volume_reference`
- 修改的参数：
  - 无
- 删除的参数：
  - 无

## 新增的分析结果

- 事件级分析显示：
  - `selected_volume_before` 最高分位的 long tilt 事件，未来 `20` 日均值为负
  - 这说明“基础仓位越大，继续倾斜越容易过度集中”是一个真实问题
- 正式回测结果进一步说明：
  - `volref20` 仍然跑不过原始 `long015`
  - `volref30` 则首次出现了比 `long015` 更优的正式结果
  - 这不是大幅碾压，但已经不是单纯的“风格变体”

## 新增的回测结果

- `selection_pairwise_v2_volume_tilt_long015_volref20`
  - `期末权益 = 2,664,535`
  - `总收益 = 1232.27%`
  - `最大回撤 = -37.20%`
  - `Sharpe = 0.990`
  - `总滑点 = 354,650`
  - `总交易次数 = 1169`
- `selection_pairwise_v2_volume_tilt_long015_volref30`
  - `期末权益 = 2,683,135`
  - `总收益 = 1241.57%`
  - `最大回撤 = -37.20%`
  - `Sharpe = 0.994`
  - `总滑点 = 354,660`
  - `总交易次数 = 1173`

## 修改的回测结果

- 无

## 删除的回测结果

- 无

## 我的判断

- 第44阶段是目前为止最有价值的一次延伸：
  - `基础仓位浓度连续缩放` 比前面的 `score gap` 和 `crowding` 更接近真实有效方向
  - `volref30` 已经正式超过原始 `long015`
- 相对 `long015`：
  - `期末权益 +5,290`
  - `总收益 +2.645%`
  - `Sharpe +0.0015`
  - `总滑点 -170`
  - `总交易次数 +4`
- 虽然增益不大，但结构是健康的：
  - 没有恶化回撤
  - Sharpe 还进一步抬高
  - 滑点也没有变差
- 当前正式候选顺序应更新为：
  - `selection_pairwise_v2 + long015_volref30`
  - `selection_pairwise_v2 + long015`
  - `selection_pairwise_v2 + long015_crowding`
  - `selection_pairwise_v2 + gapref025`
  - `selection_pairwise_v2`
  - `ungated_baseline`

# 2026-04-24 14:37 第45阶段 long015_volref30：稳定性验证与随机性压测

## 版本改动

- 改动时间点：`2026-04-24 14:37`
- 修改的文件：
  - `examples/portfolio_backtesting/analyze_qmt_roll_selection_pairwise_long015_volref30_bootstrap.py`
  - `back_log.md`
  - `memory.md`
- 改动内容：
  - 不再继续往 `long015_volref30` 上叠加新规则
  - 转而验证它相对 `long015` 的优势是否只是短期随机收益
  - 新增 `volref30 vs long015` 的日度稳定性分析脚本
  - 用已存在的正式资金曲线做两层验证：
    - `moving block bootstrap`
    - `126 / 252 / 504` 日 rolling window 稳定性统计
  - 本阶段不把 `volref25 / volref35` 作为正式结论来源：
    - 因为对应正式统计产物当前并不完整
    - 先只使用可复查的 `long015 / volref30` 正式结果做判断

## 参数变化说明

- 新增的参数：
  - 无
- 修改的参数：
  - 无
- 删除的参数：
  - 无

## 新增的分析结果

- 新增产物：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_v2_volume_tilt_long015_volref30_bootstrap_summary.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_v2_volume_tilt_long015_volref30_bootstrap_rolling_summary.csv`
- `volref30` 相对 `long015` 的全样本观测净增益：
  - `observed_total_delta_net_pnl = +58,500`
  - `observed_mean_daily_delta_net_pnl = +38.36`
- block bootstrap 正收益概率：
  - `5` 日块：`85.66%`
  - `20` 日块：`90.32%`
  - `60` 日块：`90.74%`
- rolling window 稳定性：
  - `126` 日窗口：
    - `positive_end_balance_ratio = 63.43%`
    - `positive_total_return_ratio = 57.50%`
    - `better_max_dd_ratio = 68.14%`
  - `252` 日窗口：
    - `positive_end_balance_ratio = 68.29%`
    - `positive_total_return_ratio = 63.66%`
    - `better_max_dd_ratio = 77.55%`
  - `504` 日窗口：
    - `positive_end_balance_ratio = 85.13%`
    - `positive_total_return_ratio = 85.81%`
    - `better_max_dd_ratio = 80.23%`
- 多周期正式分窗对比（`volref30` 相对 `long015`）：
  - `since_2020`：`期末权益 +58,500`，`总收益 +29.25%`，`Sharpe +0.0075`
  - `since_2021`：`期末权益 +77,560`，`总收益 +38.78%`，`Sharpe +0.0210`
  - `since_2022`：`期末权益 +8,520`，`总收益 +4.26%`，`Sharpe +0.0098`
  - `since_2023`：`期末权益 +6,570`，`总收益 +3.285%`，`Sharpe +0.0009`
  - `since_2024`：`期末权益 -1,010`，`总收益 -0.505%`，`Sharpe -0.0088`
  - `since_2025`：`期末权益 +34,745`，`总收益 +17.3725%`，`Sharpe +0.0667`
  - `since_2026`：`期末权益 +700`，`总收益 +0.35%`，但 `Sharpe -0.0042`

## 新增的回测结果

- 无

## 修改的回测结果

- 无

## 删除的回测结果

- 无

## 我的判断

- 第45阶段的结论不是“`volref30` 已经被充分证明”，而是：
  - 它已经明显强于“纯随机一把梭”的嫌疑
  - 但证据强度仍属于`中等偏强`，不是压倒性
- 具体理解是：
  - 长窗口上，`volref30` 的稳定性明显更好
  - `20 / 60` 日块 bootstrap 已经到 `90%+`
  - `504` 日 rolling window 里，总收益更优占比也到 `85.81%`
- 但短中窗口仍不够碾压：
  - `126 / 252` 日窗口里只是温和占优
  - `since_2024` 这一个正式分窗仍然轻微跑输
- 所以当前最稳妥的判断应更新为：
  - `selection_pairwise_v2 + long015_volref30` 依然是正式候选第一名
  - 但它更像“中等强度、长窗口更稳的结构增强”
  - 还不该被夸大成“已经被完全证实的强 alpha”

# 2026-04-24 15:17 第46阶段 long015_volref30：邻域正式验证（25/30/35）

## 版本改动

- 改动时间点：`2026-04-24 15:17`
- 修改的文件：
  - `examples/portfolio_backtesting/run_qmt_roll_selection_pairwise_long015_base_volume_neighbors_backtest.py`
  - `back_log.md`
  - `memory.md`
- 改动内容：
  - 不再继续往 `volref30` 上叠新规则
  - 转而验证它是不是一个真正的`局部稳定中心`
  - 新增并完善邻域正式对照脚本：
    - `long015`
    - `volref25`
    - `volref30`
    - `volref35`
  - 这版脚本不再重复浪费时间：
    - 直接复用已经存在的 `long015 / volref30` 正式统计
    - 只补跑缺失的 `volref25 / volref35`
  - 产出正式总表：
    - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_base_volume_neighbors_backtest_summary.csv`
    - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_base_volume_neighbors_backtest_summary.json`

## 参数变化说明

- 新增的参数：
  - 无
- 修改的参数：
  - 无
- 删除的参数：
  - 无

## 新增的分析结果

- 这轮最关键的新结论不是“`30` 比 `20` 好”，而是：
  - `25 / 35` 都没有塌掉
  - 所以 `30` 不是孤立尖点
  - 但 `30` 仍然是邻域里的正式最优点
- 邻域排序非常清楚：
  - `volref30 > volref35 > volref25 > long015`
- 相对 `long015`：
  - `volref25`
    - `期末权益 +41,660`
    - `总收益 +20.83%`
    - `Sharpe +0.0039`
    - `总滑点 -630`
  - `volref30`
    - `期末权益 +58,500`
    - `总收益 +29.25%`
    - `Sharpe +0.0075`
    - `总滑点 -780`
    - `总交易次数 +4`
  - `volref35`
    - `期末权益 +47,350`
    - `总收益 +23.675%`
    - `Sharpe +0.0050`
    - `总滑点 -570`
- 相对 `volref30`：
  - `volref25`
    - `期末权益 -16,840`
    - `总收益 -8.42%`
    - `Sharpe -0.0036`
  - `volref35`
    - `期末权益 -11,150`
    - `总收益 -5.575%`
    - `Sharpe -0.0025`

## 新增的回测结果

- `selection_pairwise_v2_volume_tilt_long015_volref25`
  - `期末权益 = 2,666,295`
  - `总收益 = 1233.15%`
  - `最大回撤 = -37.20%`
  - `Sharpe = 0.990`
  - `总滑点 = 354,810`
  - `总交易次数 = 1169`
- `selection_pairwise_v2_volume_tilt_long015_volref35`
  - `期末权益 = 2,671,985`
  - `总收益 = 1235.99%`
  - `最大回撤 = -37.20%`
  - `Sharpe = 0.991`
  - `总滑点 = 354,870`
  - `总交易次数 = 1169`

## 修改的回测结果

- 无

## 删除的回测结果

- 无

## 我的判断

- 第46阶段把一个很关键的问题正式回答掉了：
  - `volref30` 不是过拟合出来的孤点
  - 它在邻域里确实是最优中心
- 但这个中心也不是特别尖锐：
  - `25 / 35` 都仍然明显优于原始 `long015`
  - 说明这条线本身是稳的
  - 只是 `30` 的平衡最好
- 所以当前最合理的工程结论应更新为：
  - `selection_pairwise_v2 + long015_volref30` 继续保留为正式候选第一名
  - `volref35` 是最接近的次优备选
  - 后续如果继续深挖，不该再盯着 `25 / 30 / 35` 这种微调打转
  - 应转向新的上层变量，而不是继续细抠 `base_volume_reference`

# 2026-04-24 15:24 第47阶段 long015_volref30：失败簇拆解与上层状态变量可编码性评估

## 本次版本改动

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_selection_pairwise_long015_volref30_failure_clusters.py`
- 新增产物：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_v2_volume_tilt_long015_volref30_failure_cluster_summary.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_v2_volume_tilt_long015_volref30_failure_clusters.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_v2_volume_tilt_long015_volref30_failure_cluster_date_features.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_v2_volume_tilt_long015_volref30_failure_cluster_feature_diff.csv`
- 改动说明：
  - 不再继续微调 `base_volume_reference`
  - 转而拆 `long015_volref30` 相对 `long015` 的剩余失败簇
  - 目标是判断：当前是否已经存在足够强、足够稳定、值得接回正式策略层的上层状态变量

## 参数变更

- 新增的参数：
  - 无
- 修改的参数：
  - 无
- 删除的参数：
  - 无

## 新增的分析结果

- 全样本 `1525` 个交易日里：
  - `volref30 - long015` 的累计净增益仍为 `+58,500`
  - 但拆成连续盈亏簇后：
    - 正簇 `134` 个，累计 `+390,655`
    - 负簇 `120` 个，累计 `-332,155`
- 更关键的新发现不是“哪几个日期最差”，而是：
  - 很多最大负簇根本不发生在 tilt 当天
  - 而是发生在 `tilt` 之后的持仓传播期
  - 说明 `volref30` 剩余问题的主矛盾，已经不是“当日是否加了这一手”，而是“放大后的后续持仓路径”
- 只看真正发生 `tilt` 事件的簇（`event clusters = 53`）后：
  - 负簇 `22` 个
  - 正簇 `28` 个
  - 事件级差异不是没有，但强度明显不够支撑直接写成新规则
- 事件级负簇相对正簇，呈现出的偏弱特征是：
  - `avg_rsi` 更低，约 `70.24 vs 71.31`
  - `avg_base_volume` 更高，约 `19.93 vs 19.43`
  - `max_base_volume` 更高，约 `24.91 vs 22.23`
  - `avg_active_positions_before` 更高，约 `2.52 vs 2.20`
  - `max_range_zscore` 更高，约 `0.75 vs 0.46`
  - `avg_score_gap` 反而略高，约 `0.63 vs 0.50`
- 这组结果非常关键：
  - `score gap` 并不是剩余失败的核心解释变量
  - `base volume / 持仓拥挤 / 局部极端波动` 更像真正相关的状态
  - 但这些差异量级仍偏小，暂时还不足以直接写成一条正式过滤规则
- 最具代表性的负簇日期包括：
  - `2021-05-06 -> 2021-05-12`
  - `2022-11-29 -> 2022-12-02`
  - `2026-03-02 -> 2026-03-05`
  - `2025-08-11 -> 2025-08-13`
  - `2024-04-29 -> 2024-05-08`
- 这些失败簇的共性，不是简单的“分差不够大”，而更像：
  - `base volume` 已经不小
  - `range` 往往偏高
  - `RSI` 已经不低，部分样本甚至明显偏热
  - 所以更接近“放大后暴露过多”，而不是“排序模型判断方向完全错误”

## 新增的回测结果

- 无

## 修改的回测结果

- 无

## 删除的回测结果

- 无

## 我的判断

- 第47阶段把一个本来容易被误判的问题正式回答清楚了：
  - `long015_volref30` 的剩余弱点，主因不是“当日排序信息不够”
  - 而是“放大后的仓位，在后续传播期被更差的路径放大了”
- 这意味着下一步如果继续深挖：
  - 不该再回去做 `score gap / top gap` 这类分数阈值规则
  - 也不该继续在 `25 / 30 / 35` 这种参数上打转
  - 更值得继续的，是围绕 `base volume / active positions / 局部波动极值` 做更上层的组合状态缩放
- 但现阶段我也不会强行把这些分析差异直接写成新规则：
  - 因为差异方向是对的
  - 但量级还不够强
  - 现在贸然接策略，过拟合风险偏高
- 所以当前最稳妥的工程结论保持为：
  - `selection_pairwise_v2 + long015_volref30` 继续保留为正式候选第一名
  - 下一轮应优先研究“组合层状态缩放”
  - 而不是继续追加局部硬过滤

# 2026-04-24 15:41 第48阶段 long015_volref30：绝对持仓数连续缩放验证

## 本次版本改动

- 修改文件：
  - `examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
- 新增脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_selection_pairwise_long015_volref30_active_positions_backtest.py`
  - `examples/portfolio_backtesting/run_qmt_roll_selection_pairwise_long015_volref30_active_positions_fast_backtest.py`
- 新增产物：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_active_positions_fast_backtest_summary.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_active_positions_fast_backtest_summary.json`
- 改动说明：
  - 不再沿用之前已经证伪过的 `active_ratio` 拥挤度逻辑
  - 改为在 `long015_volref30` 上增加 `absolute active positions` 连续缩放
  - 核心思想是：
    - 当同日 long tilt 发生时
    - 如果 `active_positions_before` 本来就偏高
    - 则连续缩小 tilt 强度
    - 但不做硬过滤

## 参数变更

- 新增的参数：
  - `selection_pairwise_volume_tilt_long_active_positions_reference`
- 修改的参数：
  - 无
- 删除的参数：
  - 无

## 新增的分析结果

- 这轮最关键的结论是：
  - `absolute active positions` 这条线不是完全无效
  - 但它提供的边际非常薄
  - 目前只能算轻微风格修正，不足以成为新的正式第一候选
- 相对当前正式第一候选 `volref30`：
  - `apref2`
    - 明显更差
    - 说明收得过早、过强
  - `apref2.5`
    - 期末权益几乎持平
    - 但回撤更差
    - 不值得替代
  - `apref3`
    - 出现了轻微正向
    - 但增益量级太小
    - 仍然不足以单独升级为新的正式最优版本

## 新增的回测结果

- `selection_pairwise_v2_volume_tilt_long015_volref30_apref2`
  - `期末权益 = 2,669,265`
  - `总收益 = 1234.63%`
  - `最大回撤 = -37.29%`
  - `Sharpe = 0.9911`
  - `总滑点 = 354,820`
  - `总交易次数 = 1173`
- `selection_pairwise_v2_volume_tilt_long015_volref30_apref25`
  - `期末权益 = 2,683,215`
  - `总收益 = 1241.61%`
  - `最大回撤 = -37.43%`
  - `Sharpe = 0.9942`
  - `总滑点 = 354,730`
  - `总交易次数 = 1173`
- `selection_pairwise_v2_volume_tilt_long015_volref30_apref3`
  - `期末权益 = 2,685,555`
  - `总收益 = 1242.78%`
  - `最大回撤 = -37.33%`
  - `Sharpe = 0.9939`
  - `总滑点 = 354,650`
  - `总交易次数 = 1173`

## 修改的回测结果

- 无

## 删除的回测结果

- 无

## 我的判断

- 第48阶段的答案已经够清楚：
  - `absolute active positions` 连续缩放不是错方向
  - 但它不像 `base_volume_reference` 那样是明显的结构增强
- 更具体地说：
  - `apref2` 说明过早收缩是有害的
  - `apref2.5` 基本只是和 `volref30` 打平
  - `apref3` 虽然略高于 `volref30`
  - 但只多了 `+2,420` 权益、`+1.21%` 总收益
  - 同时 `最大回撤` 还更差 `0.13` 个百分点
- 所以当前最合理的结论是：
  - `selection_pairwise_v2 + long015_volref30` 继续保留为正式候选第一名
  - `volref30_apref3` 可以记为轻微正向的风格变体
  - 但目前不值得升级为新的主版本
- 后续如果继续研究：
  - 不该再在 `active_positions_reference` 上做细参数打磨
  - 这条线的边际已经很薄
  - 应继续寻找更强、真正正交的组合层状态变量

# 2026-04-24 15:56 第49阶段 long015_volref30：局部波动极值连续缩放验证

## 本次版本改动

- 修改文件：
  - `examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
- 新增脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_selection_pairwise_long015_volref30_range_fast_backtest.py`
- 新增产物：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_range_fast_backtest_summary.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_range_fast_backtest_summary.json`
- 改动说明：
  - 在当前正式第一候选 `selection_pairwise_v2 + long015_volref30` 上
  - 继续验证“局部波动极值过高时，是否应连续收缩 long tilt 强度”
  - 新逻辑不做硬过滤
  - 而是读取同日 long 方向候选中的 `max range zscore`
  - 再按参考值对 tilt 强度做连续缩放

## 参数变更

- 新增的参数：
  - `selection_pairwise_volume_tilt_long_max_range_zscore_reference`
- 修改的参数：
  - 无
- 删除的参数：
  - 无

## 新增的分析结果

- 这轮的答案已经很清楚：
  - `max_range_zscore` 这条线不是错方向
  - 但它当前更像“保险丝”
  - 不是新的主增强
- 更具体地说：
  - `range075 / range100 / range150` 三档全部跑输 `volref30`
  - 说明“局部波动极值过高时，适度收缩 tilt”这个直觉并非完全错误
  - 但它削掉的是主增益，而不是剩余失败簇
- 结构上它确实带来了一些副作用改善：
  - 三档 `总滑点` 都低于 `volref30`
  - `range075 / range100` 的 `最大回撤` 也略好于 `volref30`
  - 但这些改善不足以覆盖收益与 Sharpe 的系统性回落

## 新增的回测结果

- `selection_pairwise_v2_volume_tilt_long015_volref30_range075`
  - `期末权益 = 2,638,095`
  - `总收益 = 1219.05%`
  - `最大回撤 = -37.14%`
  - `Sharpe = 0.9880`
  - `总滑点 = 352,880`
  - `总交易次数 = 1173`
- `selection_pairwise_v2_volume_tilt_long015_volref30_range100`
  - `期末权益 = 2,642,885`
  - `总收益 = 1221.44%`
  - `最大回撤 = -37.16%`
  - `Sharpe = 0.9869`
  - `总滑点 = 352,520`
  - `总交易次数 = 1173`
- `selection_pairwise_v2_volume_tilt_long015_volref30_range150`
  - `期末权益 = 2,638,190`
  - `总收益 = 1219.10%`
  - `最大回撤 = -37.20%`
  - `Sharpe = 0.9870`
  - `总滑点 = 352,700`
  - `总交易次数 = 1175`

## 修改的回测结果

- 无

## 删除的回测结果

- 无

## 我的判断

- 第49阶段说明：
  - `局部波动极值连续缩放` 不是新的正式第一候选
  - 当前仍然不如 `selection_pairwise_v2 + long015_volref30`
- 具体比较相对 `volref30`：
  - `range075`
    - `期末权益 -45,040`
    - `总收益 -22.52%`
    - `Sharpe -0.0059`
    - `最大回撤` 仅改善 `0.06` 个百分点
  - `range100`
    - `期末权益 -40,250`
    - `总收益 -20.13%`
    - `Sharpe -0.0070`
    - `最大回撤` 仅改善 `0.04` 个百分点
  - `range150`
    - `期末权益 -44,945`
    - `总收益 -22.47%`
    - `Sharpe -0.0069`
    - `总交易次数` 还多了 `2` 次
- 所以当前最合理的工程结论是：
  - `selection_pairwise_v2 + long015_volref30` 继续保留为正式候选第一名
  - `max_range_zscore` 这条线可以记为“保险丝型思路”
  - 但目前不值得升级为正式增强项
  - 下一步如果继续，应该继续寻找更正交、更接近路径暴露本质的组合层状态变量

# 2026-04-24 17:35 第50阶段 long015_volref30：正式候选重跑复核

## 本次版本改动

- 改动时间：
  - `2026-04-24 17:35`
- 新增脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_selection_pairwise_long015_volref30_formal_backtest.py`
- 本次没有修改策略交易逻辑。
- 本次动作是把当前正式候选重新放回同一口径下复核：
  - `ungated_baseline`
  - `selection_pairwise_v2`
  - `selection_pairwise_v2_volume_tilt_long015`
  - `selection_pairwise_v2_volume_tilt_long015_volref30`
- 使用解释器：
  - `.py311/bin/python`
- 执行命令：
  - `PYTHONPATH=/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting:/Users/bytedance/Desktop/person/vnpy .py311/bin/python examples/portfolio_backtesting/run_qmt_roll_selection_pairwise_long015_volref30_formal_backtest.py`
- 输出文件：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_formal_backtest_summary.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_formal_backtest_summary.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_formal_*`

## 回测参数

- 基础资金：
  - `200,000`
- 回测区间：
  - `2020-01-01` 至 `2026-04-30`
- 风险参数：
  - `risk_ratio = 0.045`
- 保存产物：
  - `save_artifacts = True`
- 启动年份稳健性扫描：
  - `include_start_year_sweep = True`
- 复核组合：
  - `ungated_baseline`
    - `strategy_overrides = {}`
  - `selection_pairwise_v2`
    - `enable_selection_pairwise_v2 = True`
    - `enable_selection_pairwise_v2_catastrophic_veto = False`
  - `selection_pairwise_v2_volume_tilt_long015`
    - `enable_selection_pairwise_v2 = True`
    - `enable_selection_pairwise_v2_catastrophic_veto = False`
    - `enable_selection_pairwise_v2_volume_tilt = True`
    - `selection_pairwise_volume_tilt_long_strength = 0.15`
    - `selection_pairwise_volume_tilt_short_strength = 0.0`
    - `selection_pairwise_volume_tilt_strength = 0.0`
  - `selection_pairwise_v2_volume_tilt_long015_volref30`
    - `enable_selection_pairwise_v2 = True`
    - `enable_selection_pairwise_v2_catastrophic_veto = False`
    - `enable_selection_pairwise_v2_volume_tilt = True`
    - `selection_pairwise_volume_tilt_long_base_volume_reference = 30.0`
    - `selection_pairwise_volume_tilt_long_strength = 0.15`
    - `selection_pairwise_volume_tilt_short_strength = 0.0`
    - `selection_pairwise_volume_tilt_strength = 0.0`

## 参数变更

- 新增的参数：
  - 无，策略层没有新增参数。
- 修改的参数：
  - 无，本轮是正式复核，不做新参数探索。
- 删除的参数：
  - 无。

## 新增的回测结果

- `ungated_baseline`
  - `期末权益 = 2,612,605`
  - `总收益 = 1206.30%`
  - `最大回撤 = -37.34%`
  - `Sharpe = 0.9843`
  - `总滑点 = 355,230`
  - `总交易次数 = 1169`
- `selection_pairwise_v2`
  - `期末权益 = 2,624,635`
  - `总收益 = 1212.32%`
  - `最大回撤 = -37.34%`
  - `Sharpe = 0.9864`
  - `总滑点 = 355,440`
  - `总交易次数 = 1169`
- `selection_pairwise_v2_volume_tilt_long015`
  - `期末权益 = 2,677,845`
  - `总收益 = 1238.92%`
  - `最大回撤 = -37.20%`
  - `Sharpe = 0.9924`
  - `总滑点 = 354,830`
  - `总交易次数 = 1169`
- `selection_pairwise_v2_volume_tilt_long015_volref30`
  - `期末权益 = 2,683,135`
  - `总收益 = 1241.57%`
  - `最大回撤 = -37.20%`
  - `Sharpe = 0.9939`
  - `总滑点 = 354,660`
  - `总交易次数 = 1173`

## 启动年份稳健性结果

- `2020-01-01` 起点：
  - `volref30` 期末权益 `2,683,135`，高于 `long015` 的 `2,677,845`
- `2021-01-01` 起点：
  - `volref30` 期末权益 `2,214,410`，高于 `long015` 的 `2,209,120`
- `2022-01-01`、`2023-01-01`、`2024-01-01`、`2025-01-01`、`2026-01-01` 起点：
  - `volref30` 与 `long015` 结果一致或几乎一致
- 这说明 `base_volume_reference = 30.0` 不是强行改变全局交易行为，而是在少数高容量状态下提供边际修正。

## 修改的回测结果

- 无

## 删除的回测结果

- 无

## 我的判断

- 第50阶段的核心结论：
  - 当前正式候选第一名仍然是 `selection_pairwise_v2 + long015_volref30`
- 相对 `ungated_baseline`：
  - `期末权益 +70,530`
  - `总收益 +35.27` 个百分点
  - `Sharpe +0.0096`
  - `最大回撤` 改善约 `0.14` 个百分点
  - `总滑点 -570`
- 相对 `long015`：
  - `期末权益 +5,290`
  - `总收益 +2.65` 个百分点
  - `Sharpe +0.0015`
  - `总滑点 -170`
  - `最大回撤` 持平
- 我的判断是：
  - `volref30` 的价值不是“大幅提高胜率”，而是对已打开候选的容量倾斜做温和校准
  - 它没有破坏主策略结构，也没有通过硬过滤制造样本内幻觉
  - 但它仍然不能解决 `2024` 和 `2026` 起点的弱窗口
  - 下一步不应该继续在入场日局部过滤上微调，而应该转向组合持仓路径暴露、净风险预算、以及跨品种拥挤度这类更本质的状态变量

# 2026-04-24 17:45 第51阶段 long015_volref30：组合回撤连续缩放验证

## 本次版本改动

- 改动时间：
  - `2026-04-24 17:45`
- 修改文件：
  - `examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
- 新增脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_selection_pairwise_long015_volref30_drawdown_gate_fast_backtest.py`
- 本次设计意图：
  - 不再继续加局部入场滤网
  - 改为测试组合层“持仓路径暴露”是否能改善 `long015_volref30`
  - 具体做法是当组合权益从高水位回撤后，对新开仓 `selected_volume` 做连续缩放
- 使用解释器：
  - `.py311/bin/python`
- 执行命令：
  - `PYTHONPATH=/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting:/Users/bytedance/Desktop/person/vnpy .py311/bin/python examples/portfolio_backtesting/run_qmt_roll_selection_pairwise_long015_volref30_drawdown_gate_fast_backtest.py`
- 输出文件：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_drawdown_gate_fast_summary.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_drawdown_gate_fast_summary.json`

## 回测参数

- 基础资金：
  - `200,000`
- 回测区间：
  - `2020-01-01` 至 `2026-04-30`
- 风险参数：
  - `risk_ratio = 0.045`
- 本轮回测类型：
  - 快速探索
  - `save_artifacts = False`
  - `include_start_year_sweep = False`
- 基础候选：
  - `selection_pairwise_v2 + long015_volref30`
  - `selection_pairwise_volume_tilt_long_strength = 0.15`
  - `selection_pairwise_volume_tilt_long_base_volume_reference = 30.0`
- 对照组合：
  - `volref30_current`
  - `volref30_ddgate_10_25_floor50`
  - `volref30_ddgate_10_25_floor35`
  - `volref30_ddgate_15_30_floor50`

## 参数变更

- 新增的参数：
  - `enable_portfolio_drawdown_gate`
  - `portfolio_drawdown_gate_start_pct`
  - `portfolio_drawdown_gate_full_pct`
  - `portfolio_drawdown_gate_weight_floor`
- 修改的参数：
  - 无
- 删除的参数：
  - 无

## 新增的回测结果

- `volref30_current`
  - `期末权益 = 2,683,135`
  - `总收益 = 1241.57%`
  - `最大回撤 = -37.20%`
  - `Sharpe = 0.9939`
  - `总滑点 = 354,660`
  - `总交易次数 = 1173`
- `volref30_ddgate_10_25_floor35`
  - `期末权益 = 639,480`
  - `总收益 = 219.74%`
  - `最大回撤 = -44.08%`
  - `Sharpe = 0.4583`
  - `总滑点 = 151,100`
  - `总交易次数 = 938`
- `volref30_ddgate_10_25_floor50`
  - `期末权益 = 474,390`
  - `总收益 = 137.20%`
  - `最大回撤 = -52.26%`
  - `Sharpe = 0.3386`
  - `总滑点 = 124,790`
  - `总交易次数 = 937`
- `volref30_ddgate_15_30_floor50`
  - `期末权益 = 437,395`
  - `总收益 = 118.70%`
  - `最大回撤 = -52.12%`
  - `Sharpe = 0.3031`
  - `总滑点 = 123,710`
  - `总交易次数 = 905`

## 修改的回测结果

- 无

## 删除的回测结果

- 无

## 我的判断

- 第51阶段的结论非常明确：
  - `portfolio_drawdown_gate` 不应该升级为正式候选
  - 不需要继续做启动年份正式复核
- 失败不是因为“阈值没调好”，而是这条逻辑的结构有问题：
  - 组合已经进入回撤后再降低新仓
  - 表面上是在降风险
  - 实际上同时削弱了趋势系统最重要的恢复弹性
  - 结果是绝对滑点和交易次数下降，但净值恢复能力被严重压制
- 三档结果都明显差于 `volref30_current`：
  - 最好的 `floor35` 也只有 `639,480` 期末权益
  - 相对当前候选少 `2,043,655`
  - Sharpe 从 `0.9939` 降到 `0.4583`
  - 最大回撤百分比还从 `-37.20%` 恶化到 `-44.08%`
- 这说明：
  - “组合回撤后缩新仓”不是当前系统的主矛盾解法
  - 它解决的是交易频率和滑点
  - 但牺牲的是趋势策略穿越周期所依赖的再入场能力
- 当前正式候选仍保持：
  - `selection_pairwise_v2 + long015_volref30`
- 下一步如果继续，不应该再做权益回撤型刹车：
  - 应转向更前置的组合状态变量
  - 例如入场前的品种相关拥挤、同方向风险预算、或持仓间收益相关性
  - 这些变量比“回撤后再降仓”更可能接近真实风险源

# 2026-04-24 17:58 第52阶段 long015_volref30：连亏风险缩放参数验证

## 本次版本改动

- 改动时间：
  - `2026-04-24 17:58`
- 新增脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_selection_pairwise_long015_volref30_streak_risk_fast_backtest.py`
- 本次没有新增策略逻辑。
- 本次先对正式候选的历史成交做了归因判断：
  - 高 `margin_ratio_before` 并不是明显负收益源
  - 高 `projected_margin_ratio_after` 反而不是坏组
  - 继续做“保证金拥挤上限”大概率会误杀主趋势
  - `loss_streak` 高位入场偏弱，值得用已有参数做一轮快速验证
- 使用解释器：
  - `.py311/bin/python`
- 执行命令：
  - `PYTHONPATH=/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting:/Users/bytedance/Desktop/person/vnpy .py311/bin/python examples/portfolio_backtesting/run_qmt_roll_selection_pairwise_long015_volref30_streak_risk_fast_backtest.py`
- 输出文件：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_streak_risk_fast_summary.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_streak_risk_fast_summary.json`

## 回测参数

- 基础资金：
  - `200,000`
- 回测区间：
  - `2020-01-01` 至 `2026-04-30`
- 风险参数：
  - `risk_ratio = 0.045`
- 本轮回测类型：
  - 快速探索
  - `save_artifacts = False`
  - `include_start_year_sweep = False`
- 基础候选：
  - `selection_pairwise_v2 + long015_volref30`
  - `selection_pairwise_volume_tilt_long_strength = 0.15`
  - `selection_pairwise_volume_tilt_long_base_volume_reference = 30.0`
- 对照组合：
  - `volref30_current`
    - 默认 `streak_risk_multipliers = 1.0,1.0,1.0,0.1`
  - `volref30_streak_soft_after2`
    - `streak_risk_multipliers = 1.0,1.0,0.5,0.1`
  - `volref30_streak_linear`
    - `streak_risk_multipliers = 1.0,0.7,0.3,0.1`
  - `volref30_streak_cut_after2`
    - `streak_risk_multipliers = 1.0,1.0,0.0,0.0`

## 参数变更

- 新增的参数：
  - 无
- 修改的参数：
  - `streak_risk_multipliers`
- 删除的参数：
  - 无

## 新增的回测结果

- `volref30_current`
  - `期末权益 = 2,683,135`
  - `总收益 = 1241.57%`
  - `最大回撤 = -37.20%`
  - `Sharpe = 0.9939`
  - `总滑点 = 354,660`
  - `总交易次数 = 1173`
- `volref30_streak_soft_after2`
  - `期末权益 = 2,064,665`
  - `总收益 = 932.33%`
  - `最大回撤 = -36.62%`
  - `Sharpe = 0.8193`
  - `总滑点 = 327,810`
  - `总交易次数 = 1167`
- `volref30_streak_linear`
  - `期末权益 = 1,200,535`
  - `总收益 = 500.27%`
  - `最大回撤 = -56.23%`
  - `Sharpe = 0.5601`
  - `总滑点 = 269,690`
  - `总交易次数 = 1169`
- `volref30_streak_cut_after2`
  - `期末权益 = 155,810`
  - `总收益 = -22.09%`
  - `最大回撤 = -23.92%`
  - `Sharpe = -0.6960`
  - `总滑点 = 3,850`
  - `总交易次数 = 28`

## 修改的回测结果

- 无

## 删除的回测结果

- 无

## 我的判断

- 第52阶段结论：
  - `streak_risk_multipliers` 收紧不应升级为正式候选
- `volref30_streak_soft_after2` 是唯一有一点风险侧改善的版本：
  - 最大回撤从 `-37.20%` 改到 `-36.62%`
  - 但期末权益少 `618,470`
  - Sharpe 从 `0.9939` 降到 `0.8193`
  - 这个交换不划算
- `volref30_streak_linear` 和 `volref30_streak_cut_after2` 说明：
  - 连亏后过早或过强缩风险，会和第51阶段类似
  - 容易切断系统恢复弹性
  - 尤其 `cut_after2` 几乎让系统失去交易能力
- 所以当前判断是：
  - 不继续围绕连亏参数微调
  - `soft_after2` 可以记为“轻微降回撤保险型变体”
  - 但不能替代 `volref30_current`
- 更重要的是本轮归因否定了一个直觉误区：
  - 入场前保证金高，不等于风险源
  - 在趋势系统里，高保证金往往也代表趋势机会更强
  - 所以下一步不应做粗暴保证金拥挤上限
  - 更应该识别“相关性拥挤”而不是“名义暴露拥挤”

# 2026-04-24 18:20 第53阶段 long015_volref30：同向相关性拥挤连续缩放验证

## 本次版本改动

- 改动时间：
  - `2026-04-24 18:20`
- 修改文件：
  - `examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
- 新增脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_fast_backtest.py`
  - `examples/portfolio_backtesting/run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest.py`
- 本次设计意图：
  - 不再用名义保证金、权益回撤、连亏次数做粗暴刹车
  - 改为识别更接近风险源的“同向相关性拥挤”
  - 当新候选与当前同方向持仓的 20 日收益相关性过高时，只对新开仓 `selected_volume` 做连续缩放
  - 不做硬过滤，避免切断趋势系统的再入场能力
- 使用解释器：
  - `.py311/bin/python`
- 快速回测命令：
  - `PYTHONPATH=/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting:/Users/bytedance/Desktop/person/vnpy .py311/bin/python examples/portfolio_backtesting/run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_fast_backtest.py`
- 正式回测命令：
  - `PYTHONPATH=/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting:/Users/bytedance/Desktop/person/vnpy .py311/bin/python examples/portfolio_backtesting/run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest.py`
- 输出文件：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_corr_crowding_fast_summary.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_corr_crowding_fast_summary.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_summary.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_summary.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_formal_*`

## 回测参数

- 基础资金：
  - `200,000`
- 回测区间：
  - `2020-01-01` 至 `2026-04-30`
- 风险参数：
  - `risk_ratio = 0.045`
- 快速回测：
  - `save_artifacts = False`
  - `include_start_year_sweep = False`
- 正式回测：
  - `save_artifacts = True`
  - `include_start_year_sweep = True`
- 基础候选：
  - `selection_pairwise_v2 + long015_volref30`
  - `selection_pairwise_volume_tilt_long_strength = 0.15`
  - `selection_pairwise_volume_tilt_long_base_volume_reference = 30.0`
- 相关性拥挤候选：
  - `enable_same_direction_correlation_gate = True`
  - `same_direction_correlation_gate_lookback = 20`
  - `same_direction_correlation_gate_start = 0.60`
  - `same_direction_correlation_gate_full = 0.80`
  - `same_direction_correlation_gate_weight_floor = 0.35 / 0.50`

## 参数变更

- 新增的参数：
  - `enable_same_direction_correlation_gate`
  - `same_direction_correlation_gate_lookback`
  - `same_direction_correlation_gate_start`
  - `same_direction_correlation_gate_full`
  - `same_direction_correlation_gate_weight_floor`
- 修改的参数：
  - 无
- 删除的参数：
  - 无

## 新增的快速回测结果

- `volref30_current`
  - `期末权益 = 2,683,135`
  - `总收益 = 1241.57%`
  - `最大回撤 = -37.20%`
  - `Sharpe = 0.9939`
  - `总滑点 = 354,660`
  - `总交易次数 = 1173`
- `volref30_corr20_06_08_floor35`
  - `期末权益 = 2,902,355`
  - `总收益 = 1351.18%`
  - `最大回撤 = -36.99%`
  - `Sharpe = 1.0225`
  - `总滑点 = 349,080`
  - `总交易次数 = 1158`
- `volref30_corr20_06_08_floor50`
  - `期末权益 = 2,833,090`
  - `总收益 = 1316.55%`
  - `最大回撤 = -37.45%`
  - `Sharpe = 1.0168`
  - `总滑点 = 349,640`
  - `总交易次数 = 1150`
- `volref30_corr20_05_08_floor50`
  - `期末权益 = 2,677,580`
  - `总收益 = 1238.79%`
  - `最大回撤 = -36.92%`
  - `Sharpe = 0.9664`
  - `总滑点 = 339,310`
  - `总交易次数 = 1144`

## 新增的正式回测结果

- `volref30_current`
  - `期末权益 = 2,683,135`
  - `总收益 = 1241.57%`
  - `最大回撤 = -37.20%`
  - `Sharpe = 0.9939`
  - `总滑点 = 354,660`
  - `总交易次数 = 1173`
- `volref30_corr20_06_08_floor35`
  - `期末权益 = 2,902,355`
  - `总收益 = 1351.18%`
  - `最大回撤 = -36.99%`
  - `Sharpe = 1.0225`
  - `总滑点 = 349,080`
  - `总交易次数 = 1158`
- `volref30_corr20_06_08_floor50`
  - `期末权益 = 2,833,090`
  - `总收益 = 1316.55%`
  - `最大回撤 = -37.45%`
  - `Sharpe = 1.0168`
  - `总滑点 = 349,640`
  - `总交易次数 = 1150`

## 启动年份稳健性结果

- `volref30_corr20_06_08_floor35` 相对 `volref30_current`：
  - `2020-01-01` 起点：
    - 期末权益 `+219,220`
    - 最大回撤改善 `0.21` 个百分点
    - Sharpe `+0.0286`
  - `2021-01-01` 起点：
    - 期末权益 `+220,935`
    - 最大回撤改善 `3.28` 个百分点
    - Sharpe `+0.0454`
  - `2022-01-01` 起点：
    - 期末权益 `+296,480`
    - 最大回撤改善 `4.90` 个百分点
    - Sharpe `+0.1630`
  - `2023-01-01` 起点：
    - 期末权益 `+97,880`
    - 最大回撤改善 `10.88` 个百分点
    - Sharpe `+0.1477`
  - `2024-01-01` 起点：
    - 期末权益 `+9,045`
    - 最大回撤恶化 `2.77` 个百分点
    - Sharpe `+0.0787`
  - `2025-01-01` 起点：
    - 期末权益 `+56,470`
    - 最大回撤改善 `1.62` 个百分点
    - Sharpe `+0.1170`
  - `2026-01-01` 起点：
    - 期末权益 `+4,170`
    - 最大回撤改善 `1.52` 个百分点
    - Sharpe `+0.1142`

## 修改的回测结果

- 无

## 删除的回测结果

- 无

## 我的判断

- 第53阶段的结论：
  - `volref30_corr20_06_08_floor35` 应升级为当前正式候选第一名
- 相对 `volref30_current`：
  - `期末权益 +219,220`
  - `总收益 +109.61` 个百分点
  - `最大回撤改善 0.21` 个百分点
  - `Sharpe +0.0286`
  - `总滑点 -5,580`
  - `总交易次数 -15`
- 这个增强和前几轮失败线的本质区别：
  - 它不是回撤后刹车
  - 不是连亏后刹车
  - 也不是按名义保证金粗暴限仓
  - 它识别的是“多个同向仓位正在交易相似收益路径”这类更接近真实风险因子的拥挤
- 邻近结果也支持这个方向：
  - `floor50` 也显著提高期末权益和 Sharpe
  - 说明 `corr20 0.60 -> 0.80` 不是孤立点
  - `start=0.50` 过早收缩会损失 Sharpe，说明不能太早惩罚正常趋势共振
- 风险侧需要保留的警惕：
  - `2024` 起点最大回撤恶化 `2.77` 个百分点
  - 所以它不是完美风险降低器
  - 但该起点期末权益与 Sharpe 仍改善
- 当前最合理版本顺位：
  - 第一名：`selection_pairwise_v2 + long015_volref30 + corr20_06_08_floor35`
  - 第二名：`selection_pairwise_v2 + long015_volref30`
  - 第三名：`selection_pairwise_v2 + long015`

# 第54阶段：`corr20_06_08_floor35` 小邻域复核

## 改动时间

- `2026-04-24 18:30 CST`

## 本次版本改动内容

- 新增快速邻域回测脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_neighbors_fast_backtest.py`
- 目的：
  - 不再继续发明新规则
  - 只围绕第53阶段正式第一候选 `corr20_06_08_floor35` 做小邻域复核
  - 判断它是局部偶然点，还是参数盆地里的稳健点
- 输出文件：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_corr_crowding_neighbors_fast_summary.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_corr_crowding_neighbors_fast_summary.json`

## 回测参数

- 共同参数：
  - `risk_ratio = 0.045`
  - `capital = 200,000`
  - `analysis_start = 2020-01-01`
  - `analysis_end = 2026-04-30`
  - `enable_selection_pairwise_v2 = True`
  - `enable_selection_pairwise_v2_catastrophic_veto = False`
  - `enable_selection_pairwise_v2_volume_tilt = True`
  - `selection_pairwise_volume_tilt_strength = 0.0`
  - `selection_pairwise_volume_tilt_long_strength = 0.15`
  - `selection_pairwise_volume_tilt_short_strength = 0.0`
  - `selection_pairwise_volume_tilt_long_base_volume_reference = 30.0`
- 对照组：
  - `volref30_current`
- 同向相关性拥挤门控邻域：
  - `corr20_060_080_floor35`
  - `corr20_060_080_floor25`
  - `corr20_060_080_floor50`
  - `corr15_060_080_floor35`
  - `corr30_060_080_floor35`
  - `corr20_055_080_floor35`
  - `corr20_060_085_floor35`

## 新增的参数

- 无新增策略参数
- 新增回测邻域参数取值：
  - `same_direction_correlation_gate_weight_floor = 0.25`
  - `same_direction_correlation_gate_full = 0.85`
  - `same_direction_correlation_gate_lookback = 15`
  - `same_direction_correlation_gate_lookback = 30`
  - `same_direction_correlation_gate_start = 0.55`

## 修改的参数

- 无生产默认参数修改
- 仅在快速回测脚本中临时修改邻域参数

## 删除的参数

- 无

## 新增的回测结果

- `corr20_060_080_floor35`
  - `期末权益 = 2,902,355`
  - `总收益 = 1351.18%`
  - `最大回撤 = -36.99%`
  - `Sharpe = 1.0225`
  - `总滑点 = 349,080`
  - `总交易次数 = 1158`
- `corr20_060_080_floor25`
  - `期末权益 = 2,884,150`
  - `总收益 = 1342.08%`
  - `最大回撤 = -37.01%`
  - `Sharpe = 1.0161`
  - `总滑点 = 347,500`
  - `总交易次数 = 1156`
- `corr20_055_080_floor35`
  - `期末权益 = 2,864,865`
  - `总收益 = 1332.43%`
  - `最大回撤 = -37.08%`
  - `Sharpe = 1.0098`
  - `总滑点 = 342,960`
  - `总交易次数 = 1156`
- `corr20_060_085_floor35`
  - `期末权益 = 2,848,490`
  - `总收益 = 1324.25%`
  - `最大回撤 = -37.34%`
  - `Sharpe = 1.0174`
  - `总滑点 = 348,190`
  - `总交易次数 = 1150`
- `corr20_060_080_floor50`
  - `期末权益 = 2,833,090`
  - `总收益 = 1316.55%`
  - `最大回撤 = -37.45%`
  - `Sharpe = 1.0168`
  - `总滑点 = 349,640`
  - `总交易次数 = 1150`
- `corr15_060_080_floor35`
  - `期末权益 = 2,695,690`
  - `总收益 = 1247.85%`
  - `最大回撤 = -36.83%`
  - `Sharpe = 0.9719`
  - `总滑点 = 345,690`
  - `总交易次数 = 1156`
- `volref30_current`
  - `期末权益 = 2,683,135`
  - `总收益 = 1241.57%`
  - `最大回撤 = -37.20%`
  - `Sharpe = 0.9939`
  - `总滑点 = 354,660`
  - `总交易次数 = 1173`
- `corr30_060_080_floor35`
  - `期末权益 = 2,627,135`
  - `总收益 = 1213.57%`
  - `最大回撤 = -37.20%`
  - `Sharpe = 0.9839`
  - `总滑点 = 341,970`
  - `总交易次数 = 1158`

## 修改的回测结果

- 无

## 删除的回测结果

- 无

## 相对第53阶段锚点的判断

- `corr20_060_080_floor35` 仍是邻域内第一：
  - 期末权益最高
  - Sharpe 最高
  - 最大回撤没有显著牺牲
- `floor25` 和 `floor50` 仍显著优于 `volref30_current`：
  - 说明相关性拥挤门控不是单点过拟合
  - 但它们都弱于 `floor35`
- `lookback=15`：
  - 最大回撤略好
  - 但期末权益和 Sharpe 明显下降
  - 说明窗口太短会把正常趋势共振误判成拥挤
- `lookback=30`：
  - 滑点下降
  - 但期末权益、总收益、Sharpe 全部弱于当前对照
  - 说明窗口太长会让拥挤识别变钝
- `start=0.55`：
  - 仍优于 `volref30_current`
  - 但弱于 `start=0.60`
  - 继续支持“不要太早惩罚正常趋势共振”
- `full=0.85`：
  - Sharpe 仍强
  - 但期末权益低于 `full=0.80`
  - 说明完全惩罚阈值放太宽会错过部分真实拥挤

## 是否进入正式复测

- 不进入新的正式复测
- 原因：
  - 本轮没有邻域参数明显战胜第53阶段正式第一候选
  - `corr20_060_080_floor35` 已经在第53阶段完成正式回测和启动年份 sweep
  - 继续正式复测邻域弱参数只会增加噪音，不提高决策质量

## 我的判断

- 维持当前正式第一候选：
  - `selection_pairwise_v2 + long015_volref30 + corr20_06_08_floor35`
- 第54阶段真正有价值的结论不是“又找到更高收益”，而是：
  - `lookback=20`
  - `start=0.60`
  - `full=0.80`
  - `floor=0.35`
  - 这组参数处在一个相对合理的经验盆地中心
- 后续不应继续在 `corr` 门控上做细粒度网格搜索：
  - 那会开始变成过拟合
  - 更合理的下一步是研究“相关性拥挤发生时，是哪些品种簇、方向簇、阶段簇贡献了收益和回撤”

# 第55阶段：相关性拥挤门控事件归因

## 改动时间

- `2026-04-24 18:44 CST`

## 本次版本改动内容

- 新增归因分析脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_attribution.py`
- 本阶段不新增策略规则、不调参数、不重跑回测
- 目标：
  - 解释第53阶段正式第一候选 `corr20_06_08_floor35` 的收益来源
  - 判断相关性拥挤门控是在“同日避损”，还是通过改变后续组合路径产生效果
  - 找出门控主要作用在哪些方向、品种和阶段

## 使用的数据

- 对照组正式明细：
  - `qmt_roll_selection_long015_volref30_corr_formal_current_*`
- 门控组正式明细：
  - `qmt_roll_selection_long015_volref30_corr_formal_floor35_*`
- 归因输出：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_corr_crowding_attribution_summary.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_corr_crowding_attribution_gate_events.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_corr_crowding_attribution_daily_attribution.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_corr_crowding_attribution_by_product.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_corr_crowding_attribution_by_product_pnl.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_corr_crowding_attribution_by_daily_regime.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_corr_crowding_attribution_by_month.csv`

## 回测参数

- 本阶段未运行新回测
- 引用第53阶段正式回测参数：
  - `risk_ratio = 0.045`
  - `capital = 200,000`
  - `analysis_start = 2020-01-01`
  - `analysis_end = 2026-04-30`
  - `enable_selection_pairwise_v2 = True`
  - `enable_selection_pairwise_v2_catastrophic_veto = False`
  - `enable_selection_pairwise_v2_volume_tilt = True`
  - `selection_pairwise_volume_tilt_strength = 0.0`
  - `selection_pairwise_volume_tilt_long_strength = 0.15`
  - `selection_pairwise_volume_tilt_short_strength = 0.0`
  - `selection_pairwise_volume_tilt_long_base_volume_reference = 30.0`
  - `enable_same_direction_correlation_gate = True`
  - `same_direction_correlation_gate_lookback = 20`
  - `same_direction_correlation_gate_start = 0.60`
  - `same_direction_correlation_gate_full = 0.80`
  - `same_direction_correlation_gate_weight_floor = 0.35`

## 新增的参数

- 无

## 修改的参数

- 无

## 删除的参数

- 无

## 新增的回测结果

- 无，本阶段未运行新回测
- 沿用第53阶段正式第一候选结果：
  - `期末权益 = 2,902,355`
  - `总收益 = 1351.18%`
  - `最大回撤 = -36.99%`
  - `Sharpe = 1.0225`
  - `总滑点 = 349,080`
  - `总交易次数 = 1158`

## 修改的回测结果

- 无

## 删除的回测结果

- 无

## 新增的归因结果

- 门控触发开仓事件：
  - `78` 次
  - 分布在 `67` 个交易日
  - 覆盖 `14` 个品种
- 门控缩量：
  - 触发事件未门控手数合计 `1575`
  - 门控后手数合计 `1019`
  - 缩量 `557`
  - 缩量比例 `35.37%`
- 触发时相关性特征：
  - 平均最大相关性 `0.7345`
  - 最高相关性 `0.9837`
  - 平均同向活跃仓位数 `3.35`
  - 平均门控权重 `0.6566`
- 方向分布：
  - 多头触发 `63` 次，缩量 `396`
  - 空头触发 `15` 次，缩量 `161`
- 主要缩量品种：
  - `rb.SHFE` 缩量 `139`
  - `hc.SHFE` 缩量 `138`
  - `SA.CZCE` 缩量 `96`
  - `MA.CZCE` 缩量 `68`
  - `FG.CZCE` 缩量 `56`
  - `jm.DCE` 缩量 `28`
- 品种净贡献改善：
  - `lc.GFEX +302,080`
  - `jm.DCE +73,320`
  - `rb.SHFE +60,640`
  - `CF.CZCE +43,750`
  - `lh.DCE +30,880`
- 品种净贡献恶化：
  - `MA.CZCE -57,370`
  - `FG.CZCE -57,120`
  - `hc.SHFE -56,560`
  - `cu.SHFE -31,300`
  - `SA.CZCE -26,360`
- 日度路径归因：
  - 最近 `20` 日有门控事件的日期区间贡献 `+268,745`
  - 最近 `20` 日无门控事件的日期区间贡献 `-49,525`
  - 同日门控事件本身只贡献 `+250`
  - 说明门控的收益主要来自后续持仓路径改变，不是单纯同日避损

## 我的判断

- 这个门控不是“当天少亏一点”的工具
- 它更像组合路径修正器：
  - 在多头或空头同向仓位高度相似时，提前削弱新增仓位
  - 后续组合路径因此发生改变
  - 最大收益并不一定出现在触发当天，而是出现在之后的持仓演化
- 最强的直接缩量发生在黑色和建材链：
  - `rb`
  - `hc`
  - `SA`
  - `MA`
  - `FG`
  - `jm`
- 但最大的净利润改善来自 `lc / jm / rb`，这说明归因具有路径依赖：
  - 不能把“触发品种”机械等同于“最终赚钱品种”
  - 门控改变的是组合状态，而不是单笔交易的孤立盈亏
- 这强化了第53阶段结论：
  - 相关性拥挤确实比名义保证金和回撤刹车更接近真实风险源
- 但也提出一个实盘风险：
  - 如果未来某段行情的收益来自高度同步的趋势扩散，门控可能会少吃趋势
  - 所以后续监控重点不是继续调参数，而是记录触发后的 `20` 日路径表现

# 第56阶段：相关性拥挤门控触发后 20 日路径验证

## 改动时间

- `2026-04-24 18:51 CST`

## 本次版本改动内容

- 新增触发后路径归因脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_forward_paths.py`
- 本阶段不新增策略规则、不调参数、不重跑回测
- 目标：
  - 检查第55阶段提出的“门控是组合路径修正器”是否成立
  - 统计每次门控触发后 `5 / 10 / 20 / 40` 个交易日的相对路径
  - 同时保留事件级和日期级两套口径，避免单日多个事件被重复加权误导

## 使用的数据

- 读取第55阶段输出：
  - `qmt_roll_selection_pairwise_long015_volref30_corr_crowding_attribution_gate_events.csv`
  - `qmt_roll_selection_pairwise_long015_volref30_corr_crowding_attribution_daily_attribution.csv`
- 新增输出：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_corr_crowding_forward_paths_summary.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_corr_crowding_forward_paths_event_paths.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_corr_crowding_forward_paths_date_paths.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_corr_crowding_forward_paths_by_year.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_corr_crowding_forward_paths_by_direction.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_corr_crowding_forward_paths_by_product.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_corr_crowding_forward_paths_by_corr_bin.csv`

## 回测参数

- 本阶段未运行新回测
- 沿用第53阶段正式第一候选口径：
  - `risk_ratio = 0.045`
  - `capital = 200,000`
  - `analysis_start = 2020-01-01`
  - `analysis_end = 2026-04-30`
  - `enable_selection_pairwise_v2 = True`
  - `selection_pairwise_volume_tilt_long_strength = 0.15`
  - `selection_pairwise_volume_tilt_long_base_volume_reference = 30.0`
  - `enable_same_direction_correlation_gate = True`
  - `same_direction_correlation_gate_lookback = 20`
  - `same_direction_correlation_gate_start = 0.60`
  - `same_direction_correlation_gate_full = 0.80`
  - `same_direction_correlation_gate_weight_floor = 0.35`

## 新增的参数

- 无

## 修改的参数

- 无

## 删除的参数

- 无

## 新增的回测结果

- 无，本阶段未运行新回测
- 沿用第53阶段正式第一候选结果：
  - `期末权益 = 2,902,355`
  - `总收益 = 1351.18%`
  - `最大回撤 = -36.99%`
  - `Sharpe = 1.0225`
  - `总滑点 = 349,080`
  - `总交易次数 = 1158`

## 修改的回测结果

- 无

## 删除的回测结果

- 无

## 新增的路径归因结果

- 事件级口径：
  - 事件数 `78`
  - 触发后 `5` 日平均相对贡献 `+329`
  - 触发后 `5` 日中位数 `-435`
  - 触发后 `10` 日平均相对贡献 `+592`
  - 触发后 `10` 日中位数 `+1,265`
  - 触发后 `20` 日平均相对贡献 `+18,316`
  - 触发后 `20` 日中位数 `+6,963`
  - 触发后 `20` 日胜率 `67.95%`
- 日期级口径：
  - 触发日期数 `67`
  - 触发后 `5` 日平均相对贡献 `+64`
  - 触发后 `5` 日中位数 `+400`
  - 触发后 `10` 日平均相对贡献 `+922`
  - 触发后 `10` 日中位数 `+540`
  - 触发后 `20` 日平均相对贡献 `+15,620`
  - 触发后 `20` 日中位数 `+5,340`
  - 触发后 `20` 日胜率 `68.66%`
- 方向：
  - 多头事件 `63` 次，触发后 `20` 日平均 `+9,944`，中位数 `+6,380`，胜率 `68.25%`
  - 空头事件 `15` 次，触发后 `20` 日平均 `+53,482`，中位数 `+7,845`，胜率 `66.67%`
- 年份：
  - `2020`：平均 `+1,415`，胜率 `66.67%`
  - `2021`：平均 `-11,662`，胜率 `30.00%`
  - `2022`：平均 `+19,451`，胜率 `75.00%`
  - `2023`：平均 `+10,089`，胜率 `87.50%`
  - `2024`：平均 `+2,737`，胜率 `62.50%`
  - `2025`：平均 `+62,453`，胜率 `62.50%`
  - `2026`：平均 `+20,638`，胜率 `100.00%`
- 最强正贡献日期：
  - `2025-04-02`，`hc.SHFE/rb.SHFE`，触发后 `20` 日 `+292,720`
  - `2025-03-31`，`ru.SHFE`，触发后 `20` 日 `+226,330`
  - `2025-07-25`，`sp.SHFE`，触发后 `20` 日 `+86,635`
- 最强负贡献日期：
  - `2022-07-06`，`hc.SHFE`，触发后 `20` 日 `-99,840`
  - `2021-04-30`，`MA.CZCE`，触发后 `20` 日 `-48,240`
  - `2024-12-03`，`SA.CZCE`，触发后 `20` 日 `-26,935`

## 我的判断

- 第56阶段确认了第55阶段的核心判断：
  - 门控优势不是触发后 `5` 日立刻显现
  - 真正优势主要在触发后 `20` 日路径中释放
- 这个特征更像“减少后续组合共振失效”，不是“当天风控止血”
- `2021` 是明显反例：
  - 平均 `-11,662`
  - 胜率只有 `30.00%`
  - 说明在某些趋势扩散环境中，门控会过早削弱有效趋势
- 但跨年份看，除 `2021` 外大多数年份为正
- 实盘监控建议：
  - 每次门控触发后记录未来 `20` 个交易日相对路径
  - 连续出现 `20` 日负路径时，不应马上调参数
  - 应先判断是否处于“趋势扩散行情”，因为这正是门控可能误伤的环境
- 后续研究方向：
  - 不继续调 `corr` 参数
  - 研究 `2021` 这类负样本与 `2025-04` 这类正样本的市场状态差异

# 第57阶段：相关性拥挤门控正负样本市场状态对比

## 改动时间

- `2026-04-24 18:56 CST`

## 本次版本改动内容

- 新增状态对比脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_state_contrast.py`
- 本阶段不新增策略规则、不调参数、不重跑回测
- 目标：
  - 对比触发后 `20` 日正贡献样本与负贡献样本
  - 解释为什么 `2021` 是相关性拥挤门控的负样本
  - 找出后续实盘监控中应该关注的误伤条件

## 使用的数据

- 读取第56阶段输出：
  - `qmt_roll_selection_pairwise_long015_volref30_corr_crowding_forward_paths_event_paths.csv`
  - `qmt_roll_selection_pairwise_long015_volref30_corr_crowding_forward_paths_date_paths.csv`
- 读取第55阶段日度归因：
  - `qmt_roll_selection_pairwise_long015_volref30_corr_crowding_attribution_daily_attribution.csv`
- 新增输出：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_corr_crowding_state_contrast_summary.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_corr_crowding_state_contrast_date_state.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_corr_crowding_state_contrast_feature_diff_positive_vs_negative.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_corr_crowding_state_contrast_feature_diff_strong_positive_vs_negative.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_corr_crowding_state_contrast_year_summary.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_corr_crowding_state_contrast_period_summary.csv`

## 回测参数

- 本阶段未运行新回测
- 沿用第53阶段正式第一候选口径：
  - `risk_ratio = 0.045`
  - `capital = 200,000`
  - `analysis_start = 2020-01-01`
  - `analysis_end = 2026-04-30`
  - `enable_selection_pairwise_v2 = True`
  - `selection_pairwise_volume_tilt_long_strength = 0.15`
  - `selection_pairwise_volume_tilt_long_base_volume_reference = 30.0`
  - `enable_same_direction_correlation_gate = True`
  - `same_direction_correlation_gate_lookback = 20`
  - `same_direction_correlation_gate_start = 0.60`
  - `same_direction_correlation_gate_full = 0.80`
  - `same_direction_correlation_gate_weight_floor = 0.35`

## 新增的参数

- 无

## 修改的参数

- 无

## 删除的参数

- 无

## 新增的回测结果

- 无，本阶段未运行新回测
- 沿用第53阶段正式第一候选结果：
  - `期末权益 = 2,902,355`
  - `总收益 = 1351.18%`
  - `最大回撤 = -36.99%`
  - `Sharpe = 1.0225`
  - `总滑点 = 349,080`
  - `总交易次数 = 1158`

## 修改的回测结果

- 无

## 删除的回测结果

- 无

## 新增的状态对比结果

- 日期级样本：
  - 总触发日期 `67`
  - 触发后 `20` 日正贡献日期 `46`
  - 触发后 `20` 日负贡献日期 `21`
  - 正贡献均值 `+30,361`
  - 负贡献均值 `-16,671`
  - 强正阈值 `>= +19,790`
  - 强负阈值 `<= -4,570`
- `2021` 负样本：
  - 日期数 `9`
  - 触发后 `20` 日均值 `-12,312`
  - 中位数 `-8,880`
  - 胜率 `33.33%`
  - 平均 RSI `73.13`
  - 平均 range zscore `0.187`
  - 触发前 `20` 日收益和 `0.0477`
- `2025-03/04` 正样本簇：
  - 日期数 `3`
  - 触发后 `20` 日均值 `+194,970`
  - 中位数 `+226,330`
  - 胜率 `100.00%`
  - 平均 RSI `33.94`
  - 平均 range zscore `-0.229`
  - 触发前 `20` 日收益和 `0.1162`
- 正贡献样本相对负贡献样本：
  - 平均 RSI 更低：`62.60` vs `66.63`
  - 突破率更低：`0.297` vs `0.508`
  - range zscore 更低：`-0.058` vs `0.200`
  - 平均同向活跃数更低：`3.15` vs `3.62`
  - 平均 loss_streak 更低：`1.11` vs `1.48`
  - 触发前 `20` 日净利润更高：`71,279` vs `51,434`
- 强正样本相对强负样本：
  - 触发前 `20` 日净利润更高：`113,613` vs `27,993`
  - 触发前 `20` 日权益变化更高：`106,536` vs `22,537`
  - 平均 active_count 更低：`2.82` vs `3.65`
  - 平均 loss_streak 更低：`0.59` vs `1.71`
  - 平均 range zscore 更低：`-0.127` vs `0.225`
  - 平均 ret20 zscore 更低：`0.132` vs `0.328`

## 我的判断

- `2021` 的失败不是因为相关性门控逻辑完全错误
- 更本质的解释是：
  - 当市场处在高 RSI
  - 高突破率
  - 波动/区间扩张
  - 多个同向趋势同时扩散
  - 且系统已经出现一定连亏或切换摩擦时
  - 门控会把真实趋势扩散误判为危险拥挤
- 正样本更像：
  - 前 `20` 日已经有利润垫
  - 触发时 RSI 没有过热
  - range zscore 不高
  - 同向活跃数没有极端拥挤
  - 此时门控削弱的是更可能失效的重复风险因子
- 这给实盘监控提供了比继续调参更有价值的准则：
  - 若门控触发时 `RSI 高 / breakout 高 / range zscore 高 / ret20 zscore 高`
  - 应警惕它可能少吃趋势扩散
  - 但现在不应直接加开关
  - 因为样本少，直接加状态开关会过拟合
- 后续合理动作：
  - 做“门控触发监控报表”
  - 把每次触发的 RSI、breakout、range zscore、ret20 zscore、active_count、20 日后路径写出来
  - 用未来新增样本判断是否需要状态化门控

# 第58阶段：相关性拥挤门控触发监控报表

## 改动时间

- `2026-04-24 19:02 CST`

## 本次版本改动内容

- 新增监控报表脚本：
  - `examples/portfolio_backtesting/build_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_monitor_report.py`
- 本阶段不新增策略规则、不调参数、不重跑回测
- 目标：
  - 把第57阶段的误伤条件转成可复用监控报表
  - 验证“趋势扩散警戒分数”是否有区分度
  - 明确它只能用于观察和复盘，不能自动关闭门控

## 使用的数据

- 读取第57阶段输出：
  - `qmt_roll_selection_pairwise_long015_volref30_corr_crowding_state_contrast_date_state.csv`
- 新增输出：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_corr_crowding_monitor_summary.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_corr_crowding_monitor_events.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_corr_crowding_monitor_by_warning_label.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_corr_crowding_monitor_by_warning_score.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_corr_crowding_monitor_report.md`

## 回测参数

- 本阶段未运行新回测
- 沿用第53阶段正式第一候选口径：
  - `risk_ratio = 0.045`
  - `capital = 200,000`
  - `analysis_start = 2020-01-01`
  - `analysis_end = 2026-04-30`
  - `enable_selection_pairwise_v2 = True`
  - `selection_pairwise_volume_tilt_long_strength = 0.15`
  - `selection_pairwise_volume_tilt_long_base_volume_reference = 30.0`
  - `enable_same_direction_correlation_gate = True`
  - `same_direction_correlation_gate_lookback = 20`
  - `same_direction_correlation_gate_start = 0.60`
  - `same_direction_correlation_gate_full = 0.80`
  - `same_direction_correlation_gate_weight_floor = 0.35`

## 新增的参数

- 无

## 修改的参数

- 无

## 删除的参数

- 无

## 新增的回测结果

- 无，本阶段未运行新回测
- 沿用第53阶段正式第一候选结果：
  - `期末权益 = 2,902,355`
  - `总收益 = 1351.18%`
  - `最大回撤 = -36.99%`
  - `Sharpe = 1.0225`
  - `总滑点 = 349,080`
  - `总交易次数 = 1158`

## 修改的回测结果

- 无

## 删除的回测结果

- 无

## 新增的监控规则

- `flag_rsi_hot`：
  - `avg_rsi >= 70`
- `flag_breakout_hot`：
  - `breakout_rate >= 0.5`
- `flag_range_expanding`：
  - `avg_range_zscore >= 0`
- `flag_ret20_hot`：
  - `avg_ret20_zscore >= 0.25`
- `flag_active_crowded`：
  - `avg_active_count >= 3.5`
- `flag_loss_streak_active`：
  - `avg_loss_streak >= 1`
- `trend_expansion_warning_score`：
  - 上述 6 个 flag 的合计分数
- `trend_expansion_warning_label`：
  - `0-2` 分：`normal_watch`
  - `3-4` 分：`medium_watch`
  - `5-6` 分：`severe_watch`

## 新增的监控结果

- 总触发日期：
  - `67`
- `severe_watch`：
  - 日期数 `9`
  - 触发后 `20` 日均值 `-5,986`
  - 触发后 `20` 日中位数 `-5,930`
  - 胜率 `22.22%`
  - 负贡献日期 `7`
- 非 `severe_watch`：
  - 日期数 `58`
  - 触发后 `20` 日均值 `+18,973`
  - 触发后 `20` 日中位数 `+9,198`
  - 胜率 `75.86%`
- 按标签：
  - `normal_watch`
    - 日期数 `32`
    - `20` 日均值 `+24,727`
    - 胜率 `78.13%`
  - `medium_watch`
    - 日期数 `26`
    - `20` 日均值 `+11,890`
    - 胜率 `73.08%`
  - `severe_watch`
    - 日期数 `9`
    - `20` 日均值 `-5,986`
    - 胜率 `22.22%`
- 按分数：
  - `score=5`
    - 日期数 `8`
    - `20` 日均值 `-4,944`
    - 胜率 `25.00%`
  - `score=6`
    - 日期数 `1`
    - `20` 日均值 `-14,320`
    - 胜率 `0.00%`

## 我的判断

- 第58阶段把第57阶段的直觉转成了可执行监控：
  - 高 RSI
  - 高突破率
  - range 扩张
  - ret20 过热
  - 同向活跃数高
  - loss streak 存在
  - 这些同时出现时，门控误伤趋势扩散的概率明显上升
- `severe_watch` 的区分度足够用于实盘复盘：
  - 它的 `20` 日均值为负
  - 胜率明显低于其他标签
- 但它仍不能直接变成交易开关：
  - 样本只有 `9` 个 severe 日期
  - 且 `score=4` 仍然表现不差
  - 直接用分数关掉门控，会把监控工具过拟合成新策略
- 当前正确用法：
  - 每次门控触发时记录 warning score
  - 若为 `severe_watch`，只提高复盘优先级
  - 等未来新增样本验证后，才考虑是否做状态化门控

# 第59阶段：当前候选准实盘可用性报告

## 改动时间

- `2026-04-24 19:07 CST`

## 本次版本改动内容

- 新增准实盘可用性报告脚本：
  - `examples/portfolio_backtesting/build_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_readiness_report.py`
- 本阶段不新增策略规则、不调参数、不重跑回测
- 目标：
  - 把第53至第58阶段的研究结果汇总成准实盘决策文档
  - 冻结当前第一候选
  - 生成日常复盘模板
  - 明确哪些东西可执行，哪些东西只能监控

## 使用的数据

- 正式回测摘要：
  - `qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_summary.json`
- 邻域复核摘要：
  - `qmt_roll_selection_pairwise_long015_volref30_corr_crowding_neighbors_fast_summary.json`
- 监控摘要：
  - `qmt_roll_selection_pairwise_long015_volref30_corr_crowding_monitor_summary.json`
- 启动年份 sweep：
  - `qmt_roll_selection_long015_volref30_corr_formal_current_period_sweep_summary.csv`
  - `qmt_roll_selection_long015_volref30_corr_formal_floor35_period_sweep_summary.csv`
- 新增输出：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_corr_crowding_readiness_report.md`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_corr_crowding_readiness_summary.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_corr_crowding_readiness_start_year_comparison.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_corr_crowding_readiness_daily_review_template.csv`

## 回测参数

- 本阶段未运行新回测
- 沿用第53阶段正式第一候选口径：
  - `risk_ratio = 0.045`
  - `capital = 200,000`
  - `analysis_start = 2020-01-01`
  - `analysis_end = 2026-04-30`
  - `enable_selection_pairwise_v2 = True`
  - `selection_pairwise_volume_tilt_long_strength = 0.15`
  - `selection_pairwise_volume_tilt_long_base_volume_reference = 30.0`
  - `enable_same_direction_correlation_gate = True`
  - `same_direction_correlation_gate_lookback = 20`
  - `same_direction_correlation_gate_start = 0.60`
  - `same_direction_correlation_gate_full = 0.80`
  - `same_direction_correlation_gate_weight_floor = 0.35`

## 新增的参数

- 无

## 修改的参数

- 无

## 删除的参数

- 无

## 新增的回测结果

- 无，本阶段未运行新回测
- 沿用第53阶段正式第一候选结果：
  - `期末权益 = 2,902,355`
  - `总收益 = 1351.18%`
  - `最大回撤 = -36.99%`
  - `Sharpe = 1.0225`
  - `总滑点 = 349,080`
  - `总交易次数 = 1158`

## 修改的回测结果

- 无

## 删除的回测结果

- 无

## 新增的准实盘结论

- 当前冻结候选：
  - `selection_pairwise_v2 + long015_volref30 + corr20_06_08_floor35`
- 准实盘状态：
  - `ready_for_paper_trading_review_not_unattended_live`
- 相对 `selection_pairwise_v2 + long015_volref30`：
  - 期末权益 `+219,220`
  - 总收益 `+109.61` 个百分点
  - 最大回撤改善 `0.21` 个百分点
  - Sharpe `+0.0286`
  - 总滑点 `-5,580`
  - 总交易次数 `-15`
- 治理规则：
  - 冻结当前候选参数：`True`
  - 继续做 `corr` 微网格搜索：`False`
  - 把 `severe_watch` 当交易开关：`False`
  - 每次门控触发后跟踪 `20` 日路径：`True`
  - 推荐下一阶段：`paper_trading_review`

## 新增的复盘模板

- 文件：
  - `qmt_roll_selection_pairwise_long015_volref30_corr_crowding_readiness_daily_review_template.csv`
- 关键字段：
  - `review_date`
  - `data_end_date`
  - `end_balance`
  - `daily_net_pnl`
  - `drawdown_pct`
  - `trade_count`
  - `same_direction_corr_gate_trigger_count`
  - `severe_watch_count`
  - `max_warning_score`
  - `manual_review_required`
  - `followup_due_date_20d`
  - `followup_relative_pnl_20d`
  - `action_taken`

## 我的判断

- 当前研究已经从“找参数”转入“候选治理”
- 继续在历史数据里寻找更高收益，大概率进入过拟合
- 现在最理性的动作是：
  - 冻结候选
  - 进入准实盘/纸面跟踪
  - 只记录、不干预
  - 用未来样本检验 `severe_watch` 是否真能识别趋势扩散误伤
- 当前版本可以作为准实盘观察对象
- 当前版本不应该作为无人值守实盘自动系统

# 第60阶段：多周期、Block Bootstrap 与滑点压力稳健性实验

## 改动时间

- `2026-04-24 19:14 CST`

## 本次版本改动内容

- 新增稳健性实验脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_robustness_experiments.py`
- 本阶段不新增策略规则、不调参数、不重跑回测
- 目标：
  - 用多周期 rolling window 检查候选是否只靠少数阶段
  - 用 block bootstrap 检查路径重排后的生存能力
  - 用滑点压力测试检查交易成本断点

## 使用的数据

- 对照组日度曲线：
  - `qmt_roll_selection_long015_volref30_corr_formal_current_daily.csv`
- 当前候选日度曲线：
  - `qmt_roll_selection_long015_volref30_corr_formal_floor35_daily.csv`
- 新增输出：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_corr_crowding_robustness_summary.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_corr_crowding_robustness_rolling_windows.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_corr_crowding_robustness_rolling_comparison.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_corr_crowding_robustness_rolling_summary.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_corr_crowding_robustness_block_bootstrap_paths.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_corr_crowding_robustness_block_bootstrap_summary.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_corr_crowding_robustness_slippage_stress.csv`

## 回测参数

- 本阶段未运行新回测
- 沿用第53阶段正式第一候选口径：
  - `risk_ratio = 0.045`
  - `capital = 200,000`
  - `analysis_start = 2020-01-01`
  - `analysis_end = 2026-04-30`
  - `enable_selection_pairwise_v2 = True`
  - `selection_pairwise_volume_tilt_long_strength = 0.15`
  - `selection_pairwise_volume_tilt_long_base_volume_reference = 30.0`
  - `enable_same_direction_correlation_gate = True`
  - `same_direction_correlation_gate_lookback = 20`
  - `same_direction_correlation_gate_start = 0.60`
  - `same_direction_correlation_gate_full = 0.80`
  - `same_direction_correlation_gate_weight_floor = 0.35`

## 新增的模拟参数

- Rolling window：
  - `240` 个交易日
  - `480` 个交易日
  - `720` 个交易日
  - 步长 `20` 个交易日
- Block Bootstrap：
  - block length `20`
  - block length `40`
  - block length `60`
  - 每组 `1000` 条路径
  - 随机种子 `20260424`
- 滑点压力：
  - `1.0x`
  - `1.5x`
  - `2.0x`
  - `3.0x`
  - `5.0x`

## 修改的参数

- 无

## 删除的参数

- 无

## 新增的回测结果

- 无，本阶段未运行新回测
- 沿用第53阶段正式第一候选结果：
  - `期末权益 = 2,902,355`
  - `总收益 = 1351.18%`
  - `最大回撤 = -36.99%`
  - `Sharpe = 1.0225`
  - `总滑点 = 349,080`
  - `总交易次数 = 1158`

## 修改的回测结果

- 无

## 删除的回测结果

- 无

## 新增的 Rolling 多周期结果

- `240` 日窗口：
  - 候选窗口数 `65`
  - 正收益窗口比例 `89.23%`
  - 候选相对基线期末权益胜率 `67.69%`
  - 候选相对基线 Sharpe 中位差 `+0.0653`
  - 候选最差窗口收益 `-13.13%`
- `480` 日窗口：
  - 候选窗口数 `53`
  - 正收益窗口比例 `100.00%`
  - 候选相对基线期末权益胜率 `67.92%`
  - 候选相对基线 Sharpe 中位差 `+0.0498`
  - 候选最差窗口收益 `+3.93%`
- `720` 日窗口：
  - 候选窗口数 `41`
  - 正收益窗口比例 `100.00%`
  - 候选相对基线期末权益胜率 `58.54%`
  - 候选相对基线 Sharpe 中位差 `+0.0284`
  - 候选最差窗口收益 `+7.14%`

## 新增的 Block Bootstrap 结果

- `block=20`：
  - 路径数 `1000`
  - 期末权益中位数 `1,647,469`
  - 期末权益 `5%` 分位 `264,010`
  - 期末权益 `1%` 分位 `137,165`
  - 期末低于初始资金概率 `2.20%`
  - 最大回撤中位数 `-47.61%`
  - 最大回撤 `5%` 分位 `-68.54%`
  - 最大回撤低于 `-50%` 概率 `41.90%`
  - Sharpe 中位数 `1.0114`
  - Sharpe `5%` 分位 `0.3065`
- `block=40`：
  - 路径数 `1000`
  - 期末权益中位数 `1,785,411`
  - 期末权益 `5%` 分位 `370,271`
  - 期末权益 `1%` 分位 `195,361`
  - 期末低于初始资金概率 `1.30%`
  - 最大回撤中位数 `-45.50%`
  - 最大回撤 `5%` 分位 `-65.53%`
  - 最大回撤低于 `-50%` 概率 `32.90%`
  - Sharpe 中位数 `1.0389`
  - Sharpe `5%` 分位 `0.4479`
- `block=60`：
  - 路径数 `1000`
  - 期末权益中位数 `2,178,158`
  - 期末权益 `5%` 分位 `434,393`
  - 期末权益 `1%` 分位 `224,354`
  - 期末低于初始资金概率 `0.50%`
  - 最大回撤中位数 `-43.28%`
  - 最大回撤 `5%` 分位 `-59.72%`
  - 最大回撤低于 `-50%` 概率 `23.60%`
  - Sharpe 中位数 `1.1085`
  - Sharpe `5%` 分位 `0.5111`

## 新增的滑点压力结果

- 说明：
  - 本段为固定成交路径的滑点压力模拟
  - Sharpe 使用脚本内日收益重算口径，不等同于 vn.py 正式统计口径
- `1.0x`：
  - 期末权益 `2,902,355`
  - 总收益 `1351.18%`
  - 最大回撤 `-36.99%`
  - 模拟 Sharpe `1.2097`
  - 总滑点 `349,080`
- `1.5x`：
  - 期末权益 `2,727,815`
  - 总收益 `1263.91%`
  - 最大回撤 `-37.72%`
  - 模拟 Sharpe `1.1657`
  - 总滑点 `523,620`
- `2.0x`：
  - 期末权益 `2,553,275`
  - 总收益 `1176.64%`
  - 最大回撤 `-38.47%`
  - 模拟 Sharpe `1.1214`
  - 总滑点 `698,160`
- `3.0x`：
  - 期末权益 `2,204,195`
  - 总收益 `1002.10%`
  - 最大回撤 `-40.25%`
  - 模拟 Sharpe `1.0319`
  - 总滑点 `1,047,240`
- `5.0x`：
  - 期末权益 `1,506,035`
  - 总收益 `653.02%`
  - 最大回撤 `-54.73%`
  - 模拟 Sharpe `0.8468`
  - 总滑点 `1,745,400`

## 我的判断

- 多周期结果支持候选进入准实盘：
  - `480/720` 日窗口全为正收益
  - 相对基线 Sharpe 中位数持续改善
  - 但 `720` 日窗口相对基线胜率只有 `58.54%`
  - 说明它不是所有阶段都更强，而是中位质量更好
- Bootstrap 结果给出更真实的风险感：
  - 期末亏损概率不高
  - 但最大回撤低于 `-50%` 的概率并不低
  - 所以资金曲线承受能力是核心约束
- 滑点压力显示：
  - 到 `3x` 滑点仍有较强收益
  - 到 `5x` 滑点仍未亏损，但最大回撤接近 `-55%`
  - 成本鲁棒性可以接受，但高成本环境下心理和资金压力会明显变大
- 综合判断：
  - 当前候选适合准实盘/纸面跟踪
  - 不适合直接大资金、无人值守运行
  - 下一阶段重点不是继续找收益，而是定义资金规模、回撤忍耐线和停用/降级规则

# 第61阶段：资金规模、回撤忍耐线与降级/暂停规则

## 改动时间

- `2026-04-24 19:27 CST`

## 本次版本改动内容

- 新增风险治理报告脚本：
  - `examples/portfolio_backtesting/build_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_risk_governance_report.py`
- 本阶段不新增策略规则、不调参数、不重跑回测
- 目标：
  - 把第60阶段的回撤分布转成准实盘治理规则
  - 明确资金规模下的绝对回撤损失
  - 定义人工复盘、降级、暂停和研究重置边界

## 使用的数据

- 准实盘可用性摘要：
  - `qmt_roll_selection_pairwise_long015_volref30_corr_crowding_readiness_summary.json`
- 稳健性实验摘要：
  - `qmt_roll_selection_pairwise_long015_volref30_corr_crowding_robustness_summary.json`
- 监控报表摘要：
  - `qmt_roll_selection_pairwise_long015_volref30_corr_crowding_monitor_summary.json`
- 新增输出：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_corr_crowding_risk_governance_report.md`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_corr_crowding_risk_governance_summary.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_corr_crowding_risk_governance_capital_scenarios.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_corr_crowding_risk_governance_rules.csv`

## 回测参数

- 本阶段未运行新回测
- 沿用第53阶段正式第一候选口径：
  - `risk_ratio = 0.045`
  - `capital = 200,000`
  - `analysis_start = 2020-01-01`
  - `analysis_end = 2026-04-30`
  - `enable_selection_pairwise_v2 = True`
  - `selection_pairwise_volume_tilt_long_strength = 0.15`
  - `selection_pairwise_volume_tilt_long_base_volume_reference = 30.0`
  - `enable_same_direction_correlation_gate = True`
  - `same_direction_correlation_gate_lookback = 20`
  - `same_direction_correlation_gate_start = 0.60`
  - `same_direction_correlation_gate_full = 0.80`
  - `same_direction_correlation_gate_weight_floor = 0.35`

## 新增的参数

- 无

## 修改的参数

- 无

## 删除的参数

- 无

## 新增的回测结果

- 无，本阶段未运行新回测
- 沿用第53阶段正式第一候选结果：
  - `期末权益 = 2,902,355`
  - `总收益 = 1351.18%`
  - `最大回撤 = -36.99%`
  - `Sharpe = 1.0225`
  - `总滑点 = 349,080`
  - `总交易次数 = 1158`

## 修改的回测结果

- 无

## 删除的回测结果

- 无

## 新增的风险刻度

- 正式最大回撤：
  - `-36.99%`
- Bootstrap 中位回撤代表值：
  - `-47.61%`
- `5x` 滑点压力最大回撤：
  - `-54.73%`
- Bootstrap `5%` 尾部回撤代表值：
  - `-68.54%`
- `severe_watch` 触发后 `20` 日胜率：
  - `22.22%`

## 新增的资金情景

- `200,000` 策略资金：
  - 正式回撤损失约 `73,981`
  - Bootstrap 中位回撤损失约 `95,228`
  - `5x` 滑点回撤损失约 `109,466`
  - Bootstrap `5%` 尾部回撤损失约 `137,080`
- `500,000` 策略资金：
  - 正式回撤损失约 `184,954`
  - Bootstrap 中位回撤损失约 `238,070`
  - `5x` 滑点回撤损失约 `273,666`
  - Bootstrap `5%` 尾部回撤损失约 `342,701`
- `1,000,000` 策略资金：
  - 正式回撤损失约 `369,907`
  - Bootstrap 中位回撤损失约 `476,140`
  - `5x` 滑点回撤损失约 `547,331`
  - Bootstrap `5%` 尾部回撤损失约 `685,402`
- `2,000,000` 策略资金：
  - 正式回撤损失约 `739,814`
  - Bootstrap 中位回撤损失约 `952,279`
  - `5x` 滑点回撤损失约 `1,094,662`
  - Bootstrap `5%` 尾部回撤损失约 `1,370,804`

## 新增的治理规则

- `green`：
  - 触发：实时/准实盘回撤 `< 30%`
  - 动作：正常观察，不调参数
- `yellow_review`：
  - 触发：回撤 `>= 35%` 或 `severe_watch` 在 `20` 个交易日内出现 `>=2` 次
  - 动作：人工复盘；禁止新增参数优化
- `orange_degrade`：
  - 触发：回撤 `>= 45%` 或突破 block bootstrap 中位回撤区间
  - 动作：降低资金/暂停扩大规模；只允许继续记录
- `red_pause`：
  - 触发：回撤 `>= 55%` 或实际滑点压力接近 `5x` 情景
  - 动作：暂停新资金；复核成交、滑点、品种映射和信号漂移
- `black_research_reset`：
  - 触发：回撤 `>= 65%` 或 `20` 日 `severe_watch` 跟踪连续显著为负
  - 动作：停止准实盘；回到研究模式，禁止用同一参数继续解释

## 我的判断

- 当前候选已经不是“如何提高收益”的问题
- 它现在的核心问题是：
  - 使用者是否能承受 `45% ~ 55%` 的真实路径回撤
  - 是否能在回撤时不临场调参
  - 是否能按照规则降级/暂停
- 如果不能接受 `200,000` 资金对应 `95,000 ~ 110,000` 级别的潜在中重度回撤，就不应该进入实盘
- 这不是策略逻辑问题，而是资金治理问题
- 下一步如果继续推进，应只做准实盘复盘流水，不再做策略优化

# 第62阶段：K线/成交量/持仓量/均线的AI影子诊断

## 改动时间

- `2026-04-24 19:45 CST`

## 本次版本改动内容

- 新增AI影子模型训练脚本：
  - `examples/portfolio_backtesting/train_qmt_roll_ai_microstructure_shadow_classifier.py`
- 使用既有候选训练样本：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_candidate_training_samples.csv`
- 生成新的影子AI输出：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_microstructure_shadow_samples_microstructure20d_shadow_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_microstructure_shadow_schema_microstructure20d_shadow_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_microstructure_shadow_classifier_microstructure20d_shadow_v1.joblib`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_microstructure_shadow_classifier_summary_microstructure20d_shadow_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_microstructure_shadow_classifier_coefficients_microstructure20d_shadow_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_microstructure_shadow_classifier_predictions_microstructure20d_shadow_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_microstructure_shadow_classifier_bucket_analysis_microstructure20d_shadow_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_microstructure_shadow_classifier_group_analysis_microstructure20d_shadow_v1.csv`
- 本阶段没有把AI分数接入策略，没有新增仓位开关，没有运行新回测

## 回测参数

- 本阶段未运行新回测
- 沿用第53阶段正式第一候选口径：
  - `risk_ratio = 0.045`
  - `capital = 200,000`
  - `analysis_start = 2020-01-01`
  - `analysis_end = 2026-04-30`
  - `enable_selection_pairwise_v2 = True`
  - `selection_pairwise_volume_tilt_long_strength = 0.15`
  - `selection_pairwise_volume_tilt_long_base_volume_reference = 30.0`
  - `enable_same_direction_correlation_gate = True`
  - `same_direction_correlation_gate_lookback = 20`
  - `same_direction_correlation_gate_start = 0.60`
  - `same_direction_correlation_gate_full = 0.80`
  - `same_direction_correlation_gate_weight_floor = 0.35`

## 新增的参数

- AI模型标签：
  - `MODEL_TAG = microstructure20d_shadow_v1`
- 样本目标：
  - `target_candidate_forward_20d_positive = label_candidate_forward_20d_r_multiple > 0`
- 样本权重：
  - `sample_weight_forward20_abs_r = clip(abs(label_candidate_forward_20d_r_multiple), 0.25, 3.0)`
- 时间切分：
  - `train < 2023-01-01`
  - `2023-01-01 <= valid < 2024-01-01`
  - `test >= 2024-01-01`
- 模型参数：
  - `LogisticRegression(C=0.25, solver=lbfgs, max_iter=3000, random_state=42)`
- 新增特征分组：
  - `kline_size_volatility`：ATR、range、波动zscore
  - `kline_shape_position`：上下影线、收盘位置、方向性有利/不利影线
  - `volume`：成交量zscore、成交量比率、量仓放大标记
  - `open_interest`：持仓量变化、持仓量比率、持仓量zscore
  - `moving_average_trend`：均线差、均线排列、方向性均线距离、动量
  - `portfolio_context`：方向、止损距离、保证金/权益、候选截面数量、连续亏损和持仓槽位

## 修改的参数

- 无

## 删除的参数

- 无

## 新增的回测结果

- 无，本阶段未运行新回测
- 沿用第53阶段正式第一候选结果：
  - `期末权益 = 2,902,355`
  - `总收益 = 1351.18%`
  - `最大回撤 = -36.99%`
  - `Sharpe = 1.0225`
  - `总滑点 = 349,080`
  - `总交易次数 = 1158`

## 修改的回测结果

- 无

## 删除的回测结果

- 无

## 新增的AI诊断结果

- 样本覆盖：
  - 总样本 `883`
  - 总交易日 `630`
  - 训练集 `359` 行 / `268` 日
  - 验证集 `169` 行 / `121` 日
  - 测试集 `355` 行 / `241` 日
- 训练集：
  - 正样本率 `55.71%`
  - AUC `0.7486`
  - Accuracy `67.97%`
  - F1 `0.7332`
  - LogLoss `0.5289`
  - Brier `0.1770`
- 验证集：
  - 正样本率 `50.30%`
  - AUC `0.4507`
  - Accuracy `46.15%`
  - F1 `0.4800`
  - LogLoss `0.9072`
  - Brier `0.3235`
- 测试集：
  - 正样本率 `57.18%`
  - AUC `0.4387`
  - Accuracy `43.38%`
  - F1 `0.4582`
  - LogLoss `0.9705`
  - Brier `0.3476`
- 测试集分桶不单调：
  - `q1` 平均预测概率 `0.1339`，实际正样本率 `60.56%`，平均 `20d R = 2.6312`
  - `q2` 平均预测概率 `0.2992`，实际正样本率 `67.61%`，平均 `20d R = 5.0379`
  - `q3` 平均预测概率 `0.4711`，实际正样本率 `52.11%`，平均 `20d R = 1.2956`
  - `q4` 平均预测概率 `0.6655`，实际正样本率 `54.93%`，平均 `20d R = 5.1117`
  - `q5` 平均预测概率 `0.8441`，实际正样本率 `50.70%`，平均 `20d R = 0.2128`
- 特征组平均绝对系数强度：
  - `portfolio_context = 0.2275`
  - `volume = 0.2181`
  - `moving_average_trend = 0.2117`
  - `kline_size_volatility = 0.1746`
  - `open_interest = 0.1264`
  - `kline_shape_position = 0.1091`

## 我的判断

- 这次AI实验的结论不是“AI没用”，而是“当前这种直接预测20日绝对正负的口径不稳”
- 样本内AUC `0.7486`，但验证/测试AUC都低于 `0.5`，说明模型学到的很可能是阶段性环境关系，而不是可穿越周期的稳定规律
- 测试集高分桶反而没有更高胜率，不能作为加仓、减仓或过滤信号
- K线大小、形态、成交量、持仓量、均线这些变量可以继续用于诊断和候选排序研究，但目前只能做影子分数
- 后续如果继续做AI，应该优先做：
  - walk-forward滚动重训
  - 只预测截面相对排序，而不是绝对涨跌
  - 只作为候选排序的弱特征，不作为硬开关
  - 先纸面跟踪新增样本，确认分桶单调性后再考虑接入策略

# 第63阶段：AI截面相对排序走前实验

## 改动时间

- `2026-04-24 19:51 CST`

## 本次版本改动内容

- 新增AI截面相对排序走前脚本：
  - `examples/portfolio_backtesting/train_qmt_roll_ai_microstructure_relative_walkforward.py`
- 延续第62阶段的微观结构特征，但把标签从“20日绝对正负”改为“同日候选相对排序”
- 使用滚动训练/测试窗口，不把未来窗口混入当前训练
- 新增输出：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_microstructure_relative_walkforward_samples_microstructure_relative_wf_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_microstructure_relative_walkforward_summary_microstructure_relative_wf_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_microstructure_relative_walkforward_predictions_microstructure_relative_wf_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_microstructure_relative_walkforward_window_metrics_microstructure_relative_wf_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_microstructure_relative_walkforward_bucket_analysis_microstructure_relative_wf_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_microstructure_relative_walkforward_top_picks_microstructure_relative_wf_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_microstructure_relative_walkforward_coefficients_microstructure_relative_wf_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_microstructure_relative_walkforward_group_analysis_microstructure_relative_wf_v1.csv`
- 本阶段没有把AI分数接入策略，没有新增仓位开关，没有运行新回测

## 回测参数

- 本阶段未运行新回测
- 沿用第53阶段正式第一候选口径：
  - `risk_ratio = 0.045`
  - `capital = 200,000`
  - `analysis_start = 2020-01-01`
  - `analysis_end = 2026-04-30`
  - `enable_selection_pairwise_v2 = True`
  - `selection_pairwise_volume_tilt_long_strength = 0.15`
  - `selection_pairwise_volume_tilt_long_base_volume_reference = 30.0`
  - `enable_same_direction_correlation_gate = True`
  - `same_direction_correlation_gate_lookback = 20`
  - `same_direction_correlation_gate_start = 0.60`
  - `same_direction_correlation_gate_full = 0.80`
  - `same_direction_correlation_gate_weight_floor = 0.35`

## 新增的参数

- AI模型标签：
  - `MODEL_TAG = microstructure_relative_wf_v1`
- 相对排序标签：
  - `target_relative_quality_top_half = label_candidate_quality_score_v2_rank_centered_1d > 0`
- 样本过滤：
  - `label_candidate_cross_section_count_1d >= 2`
- 样本权重：
  - `sample_weight_relative_quality_rank = clip(abs(label_candidate_quality_score_v2_rank_centered_1d), 0.25, 1.0)`
- 走前参数：
  - `TRAIN_WINDOW_DAYS = 720`
  - `TEST_WINDOW_DAYS = 180`
  - `STEP_DAYS = 180`
  - `MIN_TRAIN_ROWS = 80`
  - `MIN_TEST_ROWS = 20`
- 模型参数：
  - `LogisticRegression(C=0.20, solver=lbfgs, max_iter=3000, random_state=42)`

## 修改的参数

- 无

## 删除的参数

- 无

## 新增的回测结果

- 无，本阶段未运行新回测
- 沿用第53阶段正式第一候选结果：
  - `期末权益 = 2,902,355`
  - `总收益 = 1351.18%`
  - `最大回撤 = -36.99%`
  - `Sharpe = 1.0225`
  - `总滑点 = 349,080`
  - `总交易次数 = 1158`

## 修改的回测结果

- 无

## 删除的回测结果

- 无

## 新增的AI走前结果

- 样本覆盖：
  - 截面样本 `447`
  - 截面交易日 `194`
  - 走前窗口 `7`
  - 样本外预测行 `323`
  - 样本外预测日 `138`
- 样本外整体：
  - 正样本率 `44.89%`
  - AUC `0.5002`
  - Accuracy `47.99%`
  - Precision `42.07%`
  - Recall `42.07%`
  - F1 `0.4207`
  - LogLoss `0.8615`
  - Brier `0.3046`
- 样本外相关性：
  - 预测概率 vs 相对排序 Spearman `0.0041`
  - 预测概率 vs 质量分 Spearman `0.0198`
- top-pick 结果：
  - top-pick 天数 `138`
  - top-pick 命中率 `47.10%`
  - 日内候选基准命中率 `45.94%`
  - top-pick 相对基准优势 `+1.16` 个百分点
  - top-pick 平均相对排序 `0.0217`
  - top-pick 平均质量分 `0.5735`
- 分桶结果不单调：
  - `q1` 实际top-half率 `41.54%`，平均质量分 `0.3450`
  - `q2` 实际top-half率 `42.19%`，平均质量分 `0.5429`
  - `q3` 实际top-half率 `52.31%`，平均质量分 `0.6975`
  - `q4` 实际top-half率 `43.75%`，平均质量分 `0.7267`
  - `q5` 实际top-half率 `44.62%`，平均质量分 `0.5104`

## 我的判断

- 相对排序口径比绝对方向口径更合理，但这次走前结果仍然接近随机
- AUC `0.5002`、Spearman `0.0041` 说明模型没有稳定截面排序能力
- top-pick 只比日内基准高 `+1.16` 个百分点，无法覆盖实盘复杂性，也不值得为了它增加系统复杂度
- 分桶只有中间桶表现好，高分桶没有优势，说明模型概率不能解释成可靠置信度
- 结论：
  - 当前K线/成交量/持仓量/均线AI方向不应进入策略
  - 不应继续调这个模型参数寻找历史好看结果
  - 后续如果还做AI，应先换问题定义，例如预测“是否避开极端误伤/拥挤误杀”，而不是预测普通候选优劣

# 第64阶段：极端误伤/趋势扩散告警验证

## 改动时间

- `2026-04-24 20:01 CST`

## 本次版本改动内容

- 新增极端误伤告警验证脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_extreme_guardrail.py`
- 本阶段不训练黑箱模型
- 原因：
  - 相关性门控触发日期只有 `67` 个
  - `severe_watch` 只有 `9` 个
  - 用这类小样本训练AI会制造过拟合幻觉
- 本阶段只验证固定告警是否能抓住真正危险的左尾事件
- 新增输出：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_corr_crowding_extreme_guardrail_events.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_corr_crowding_extreme_guardrail_by_year.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_corr_crowding_extreme_guardrail_by_score.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_corr_crowding_extreme_guardrail_year_removal.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_corr_crowding_extreme_guardrail_permutation_summary.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_corr_crowding_extreme_guardrail_summary.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_pairwise_long015_volref30_corr_crowding_extreme_guardrail_report.md`
- 本阶段没有把告警接入策略，没有新增仓位开关，没有运行新回测

## 回测参数

- 本阶段未运行新回测
- 沿用第53阶段正式第一候选口径：
  - `risk_ratio = 0.045`
  - `capital = 200,000`
  - `analysis_start = 2020-01-01`
  - `analysis_end = 2026-04-30`
  - `enable_selection_pairwise_v2 = True`
  - `selection_pairwise_volume_tilt_long_strength = 0.15`
  - `selection_pairwise_volume_tilt_long_base_volume_reference = 30.0`
  - `enable_same_direction_correlation_gate = True`
  - `same_direction_correlation_gate_lookback = 20`
  - `same_direction_correlation_gate_start = 0.60`
  - `same_direction_correlation_gate_full = 0.80`
  - `same_direction_correlation_gate_weight_floor = 0.35`

## 新增的参数

- 极端负样本阈值：
  - `EXTREME_NEGATIVE_THRESHOLD = -10,000`
- 普通负样本阈值：
  - `NEGATIVE_THRESHOLD = 0`
- 随机置换次数：
  - `PERMUTATION_COUNT = 10,000`
- 随机种子：
  - `RANDOM_SEED = 42`
- 告警定义沿用第58阶段：
  - `severe_watch = trend_expansion_warning_score >= 5`

## 修改的参数

- 无

## 删除的参数

- 无

## 新增的回测结果

- 无，本阶段未运行新回测
- 沿用第53阶段正式第一候选结果：
  - `期末权益 = 2,902,355`
  - `总收益 = 1351.18%`
  - `最大回撤 = -36.99%`
  - `Sharpe = 1.0225`
  - `总滑点 = 349,080`
  - `总交易次数 = 1158`

## 修改的回测结果

- 无

## 删除的回测结果

- 无

## 新增的告警验证结果

- 样本覆盖：
  - 相关性门控触发日期 `67`
  - `severe_watch` 日期 `9`
  - 普通负样本日期 `21`
  - 极端负样本日期 `12`
- 对普通负样本：
  - Precision `77.78%`
  - Recall `33.33%`
  - False positive rate `4.35%`
  - 负样本基准率 `31.34%`
  - alert lift `2.48x`
  - `severe_watch` 20日均值 `-5,986`
  - 非 `severe_watch` 20日均值 `+18,972`
  - 均值差 `-24,959`
  - `severe_watch` 20日胜率 `22.22%`
  - 非 `severe_watch` 20日胜率 `75.86%`
- 对极端负样本：
  - Precision `44.44%`
  - Recall `33.33%`
  - False positive rate `9.09%`
  - 极端负样本基准率 `17.91%`
  - alert lift `2.48x`
- 随机置换检验：
  - observed severe/non-severe 20日均值差 `-24,959`
  - 随机均值差 `p50 = -4,606`
  - 随机均值差 `p05 = -23,325`
  - `P(random_diff <= observed) = 0.0383`
  - observed 极端负样本 precision `44.44%`
  - `P(random_extreme_precision >= observed) = 0.0453`
  - observed 普通负样本 precision `77.78%`
  - `P(random_negative_precision >= observed) = 0.0038`
- 剔除单年敏感性：
  - 剔除 `2021` 后普通负样本 precision 仍为 `66.67%`
  - 剔除 `2025` 后普通负样本 precision 为 `100.00%`
  - 各剔除年份后 severe/non-severe 均值差仍为负
  - 说明信号不完全由单一年份造成，但样本量仍小

## 我的判断

- 这个方向比第62/63阶段的普通AI更有价值
- 原因不是它能赚钱，而是它抓的是“策略最怕的左尾误伤环境”
- `severe_watch` 的优势是：
  - precision 高
  - 随机置换下不太像纯偶然
  - 剔除单年后方向仍保持
- `severe_watch` 的缺陷是：
  - recall 只有 `33.33%`
  - 会漏掉大部分负样本
  - 触发样本只有 `9`
- 因此不能做交易开关，不能自动关闭门控，也不能自动减仓
- 正确用途：
  - 准实盘人工复盘优先级
  - 触发后强制跟踪未来 `20` 日路径
  - 新样本积累标签
  - 若未来样本继续验证，再考虑是否做“人工确认后降级”规则

# 第65阶段：AI品种适配度走前影子验证

## 改动时间

- `2026-04-24 20:27 CST`

## 本次版本改动内容

- 新增AI品种适配度走前分析脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_ai_product_suitability_walkforward.py`
- 本阶段不改变正式交易逻辑，不接入品种过滤，不新增交易开关
- 设计目标：
  - 验证“AI是否能从全市场识别更适合当前趋势系统的品种地形”
  - 标签不预测价格涨跌，而是预测每个品种未来 `60` 个交易日对当前正式候选的净贡献是否处于同月截面前半
  - 先与透明的简单品种适配度分数对照，避免直接把AI历史拟合接入策略
- 使用数据：
  - 当前冻结候选成交/持仓变化：
    - `qmt_roll_selection_long015_volref30_corr_formal_floor35_position_changes_2020_2026_04.csv`
  - 当前冻结候选入场快照：
    - `qmt_roll_selection_long015_volref30_corr_formal_floor35_entry_candidate_snapshots_2020_2026_04.csv`
- 新增输出：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_product_suitability_walkforward_daily_product_suitability_wf_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_product_suitability_walkforward_samples_product_suitability_wf_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_product_suitability_walkforward_predictions_product_suitability_wf_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_product_suitability_walkforward_window_metrics_product_suitability_wf_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_product_suitability_walkforward_bucket_analysis_product_suitability_wf_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_product_suitability_walkforward_top_products_product_suitability_wf_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_product_suitability_walkforward_coefficients_product_suitability_wf_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_product_suitability_walkforward_summary_product_suitability_wf_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_product_suitability_walkforward_report_product_suitability_wf_v1.md`

## 回测参数

- 本阶段未运行新回测
- 沿用第53阶段正式第一候选口径：
  - `risk_ratio = 0.045`
  - `capital = 200,000`
  - `analysis_start = 2020-01-01`
  - `analysis_end = 2026-04-30`
  - `enable_selection_pairwise_v2 = True`
  - `selection_pairwise_volume_tilt_long_strength = 0.15`
  - `selection_pairwise_volume_tilt_long_base_volume_reference = 30.0`
  - `enable_same_direction_correlation_gate = True`
  - `same_direction_correlation_gate_lookback = 20`
  - `same_direction_correlation_gate_start = 0.60`
  - `same_direction_correlation_gate_full = 0.80`
  - `same_direction_correlation_gate_weight_floor = 0.35`

## 新增的参数

- AI模型标签：
  - `MODEL_TAG = product_suitability_wf_v1`
- 未来贡献标签：
  - `target_future_top_half_60d = future product net contribution ranks in top half of same monthly cross-section`
- 未来观察窗口：
  - `FUTURE_HORIZON_DAYS = 60`
- 滚动特征窗口：
  - `ROLLING_WINDOWS = 20 / 60 / 120`
- 走前参数：
  - `TRAIN_WINDOW_DAYS = 720`
  - `TEST_WINDOW_DAYS = 180`
  - `STEP_DAYS = 180`
  - `MIN_TRAIN_ROWS = 180`
  - `MIN_TEST_ROWS = 45`
- 模型参数：
  - `LogisticRegression(C=0.20, solver=lbfgs, max_iter=3000, random_state=42)`
- Top品种观察数量：
  - `TOP_N_PRODUCTS = 5`

## 修改的参数

- 无

## 删除的参数

- 无

## 新增的回测结果

- 无，本阶段未运行新回测
- 沿用第53阶段正式第一候选结果：
  - `期末权益 = 2,902,355`
  - `总收益 = 1351.18%`
  - `最大回撤 = -36.99%`
  - `Sharpe = 1.0225`
  - `总滑点 = 349,080`
  - `总交易次数 = 1158`

## 修改的回测结果

- 无

## 删除的回测结果

- 无

## 新增的AI品种适配度结果

- 样本覆盖：
  - 日度品种行 `27,450`
  - 月度样本行 `1,332`
  - 样本月份 `74`
  - 样本外预测行 `900`
  - 样本外预测月份 `50`
  - 品种数 `18`
  - 特征数 `108`
  - 走前窗口 `9`
- AI样本外整体：
  - AUC `0.5148`
  - Accuracy `52.89%`
  - Precision `53.21%`
  - Recall `66.59%`
  - F1 `0.5915`
  - 预测概率 vs 未来60日净贡献 Spearman `0.0171`
  - 预测概率 vs 未来截面排名 Spearman `0.0326`
  - 月度平均 rank IC `0.0591`
- 简单规则分数对照：
  - AUC `0.4745`
  - Accuracy `49.67%`
  - 月度平均 rank IC `-0.0489`
- Top 5品种观察：
  - AI Top 5 平均未来60日品种净贡献 `9,168.70`
  - AI Top 5 相对全品种均值边际 `+4,488.83`
  - AI Top 5 top-half率 `50.00%`
  - AI Top 5 平均未来截面排名中心值 `0.0224`
  - 简单分数 Top 5 平均未来60日品种净贡献 `136.38`
  - 简单分数 Top 5 相对全品种均值边际 `-4,543.49`
- AI分桶结果不单调：
  - `q1` top-half率 `46.11%`，平均未来60日净贡献 `3,509`
  - `q2` top-half率 `51.67%`，平均未来60日净贡献 `-1,058`
  - `q3` top-half率 `52.22%`，平均未来60日净贡献 `1,580`
  - `q4` top-half率 `57.22%`，平均未来60日净贡献 `13,547`
  - `q5` top-half率 `48.89%`，平均未来60日净贡献 `5,820`
- 年度拆分：
  - `2022` AI Top 5 平均边际 `+1,051`，top-half率 `53.33%`
  - `2023` AI Top 5 平均边际 `+15,225`，top-half率 `56.67%`
  - `2024` AI Top 5 平均边际 `+3,730`，top-half率 `50.00%`
  - `2025` AI Top 5 平均边际 `+3,513`，top-half率 `43.33%`
  - `2026` AI Top 5 平均边际 `-28,890`，top-half率 `30.00%`

## 我的判断

- 这个方向比“AI直接预测品种涨跌方向”更接近趋势系统本质
- 但第65阶段结果只能算弱正证据，不能接入正式交易：
  - AUC 仅 `0.5148`
  - 月度 rank IC 仅 `0.0591`
  - 分桶不单调，最高分桶 `q5` 反而弱于 `q4`
  - 年度上 `2025` 已经变弱，`2026` 明显失效
- 它真正有价值的地方是：
  - 证明“品种地形适配度”这条问题定义比第62/63阶段普通AI更合理
  - AI确实比当前手写简单分数更能抓到一点品种边际
  - 但强度还不够，不能做品种白名单/黑名单，也不能做自动过滤
- 下一步如果继续：
  - 不应立刻接入正式组合回测
  - 应先改进标签和特征，例如加入主连价格趋势性、波动结构、成交量/持仓量状态、期限结构或跨品种相关性簇
  - 同时保留透明基线，要求AI在样本外稳定胜过简单规则后，再考虑做正式品种池回测

# 第66阶段：AI品种适配度加入主连市场地形特征

## 改动时间

- `2026-04-24 20:35 CST`

## 本次版本改动内容

- 新增AI品种适配度V2走前分析脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_ai_product_suitability_market_walkforward.py`
- 本阶段仍不改变正式交易逻辑，不接入品种过滤，不新增交易开关
- 相比第65阶段，新增独立于系统成交路径之外的主连市场地形特征：
  - 主连价格收益
  - 主连实现波动
  - 主连日内振幅
  - 趋势效率
  - 收盘位置
  - 突破率
  - 成交量相对状态
  - 持仓量变化和标准化状态
  - 均线结构
- 设计目标：
  - 检验“品种适配度”是否能由市场自身地形增强，而不是只拟合当前系统过去在哪些品种赚钱
  - 继续保持走前样本外验证，避免把历史最优品种筛选误当成可交易能力
- 新增输出：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_product_suitability_market_walkforward_market_daily_product_suitability_market_wf_v2.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_product_suitability_market_walkforward_featured_daily_product_suitability_market_wf_v2.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_product_suitability_market_walkforward_samples_product_suitability_market_wf_v2.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_product_suitability_market_walkforward_predictions_product_suitability_market_wf_v2.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_product_suitability_market_walkforward_window_metrics_product_suitability_market_wf_v2.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_product_suitability_market_walkforward_bucket_analysis_product_suitability_market_wf_v2.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_product_suitability_market_walkforward_top_products_product_suitability_market_wf_v2.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_product_suitability_market_walkforward_coefficients_product_suitability_market_wf_v2.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_product_suitability_market_walkforward_summary_product_suitability_market_wf_v2.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_product_suitability_market_walkforward_report_product_suitability_market_wf_v2.md`

## 回测参数

- 本阶段未运行新回测
- 沿用第53阶段正式第一候选口径：
  - `risk_ratio = 0.045`
  - `capital = 200,000`
  - `analysis_start = 2020-01-01`
  - `analysis_end = 2026-04-30`
  - `enable_selection_pairwise_v2 = True`
  - `selection_pairwise_volume_tilt_long_strength = 0.15`
  - `selection_pairwise_volume_tilt_long_base_volume_reference = 30.0`
  - `enable_same_direction_correlation_gate = True`
  - `same_direction_correlation_gate_lookback = 20`
  - `same_direction_correlation_gate_start = 0.60`
  - `same_direction_correlation_gate_full = 0.80`
  - `same_direction_correlation_gate_weight_floor = 0.35`

## 新增的参数

- AI模型标签：
  - `MODEL_TAG = product_suitability_market_wf_v2`
- 市场特征窗口：
  - `ROLLING_WINDOWS = 20 / 60 / 120`
- 新增市场地形特征：
  - `market_ret_20d / 60d / 120d`
  - `market_realized_vol_20d / 60d / 120d`
  - `market_range_pct_mean_20d / 60d / 120d`
  - `market_trend_efficiency_20d / 60d / 120d`
  - `market_close_position_20d / 60d / 120d`
  - `market_breakout_rate_20d / 60d / 120d`
  - `market_volume_ratio_20d / 60d / 120d`
  - `market_open_interest_change_20d / 60d / 120d`
  - `market_ma20_over_ma60_60d`
  - `market_ma60_over_ma120_120d`
  - `market_volume_zscore_60d`
  - `market_open_interest_zscore_60d`
- 继续沿用第65阶段标签和走前参数：
  - `FUTURE_HORIZON_DAYS = 60`
  - `target_future_top_half_60d = future product net contribution ranks in top half of same monthly cross-section`
  - `TRAIN_WINDOW_DAYS = 720`
  - `TEST_WINDOW_DAYS = 180`
  - `STEP_DAYS = 180`
  - `MIN_TRAIN_ROWS = 180`
  - `MIN_TEST_ROWS = 45`
  - `LogisticRegression(C=0.20, solver=lbfgs, max_iter=3000, random_state=42)`
  - `TOP_N_PRODUCTS = 5`

## 修改的参数

- 无正式策略参数修改
- AI影子研究特征数从第65阶段 `108` 增加到 `136`
- 其中新增主连市场地形特征数 `28`

## 删除的参数

- 无

## 新增的回测结果

- 无，本阶段未运行新回测
- 沿用第53阶段正式第一候选结果：
  - `期末权益 = 2,902,355`
  - `总收益 = 1351.18%`
  - `最大回撤 = -36.99%`
  - `Sharpe = 1.0225`
  - `总滑点 = 349,080`
  - `总交易次数 = 1158`

## 修改的回测结果

- 无

## 删除的回测结果

- 无

## 新增的AI品种适配度结果

- 样本覆盖：
  - 月度样本行 `1,332`
  - 样本外预测行 `900`
  - 样本月份 `74`
  - 样本外预测月份 `50`
  - 品种数 `18`
  - 特征数 `136`
  - 主连市场特征数 `28`
  - 走前窗口 `9`
- AI样本外整体：
  - AUC `0.5180`
  - Accuracy `51.89%`
  - Precision `52.63%`
  - Recall `60.74%`
  - F1 `0.5639`
  - 预测概率 vs 未来60日净贡献 Spearman `0.0300`
  - 预测概率 vs 未来截面排名 Spearman `0.0444`
  - 月度平均 rank IC `0.0622`
- 简单规则分数对照：
  - AUC `0.4745`
  - Accuracy `49.67%`
  - 月度平均 rank IC `-0.0489`
- Top 5品种观察：
  - AI Top 5 平均未来60日品种净贡献 `13,489.28`
  - AI Top 5 相对全品种均值边际 `+8,809.41`
  - AI Top 5 正贡献率 `33.20%`
  - AI Top 5 top-half率 `50.80%`
  - AI Top 5 平均未来截面排名中心值 `0.0412`
  - 简单分数 Top 5 平均未来60日品种净贡献 `136.38`
  - 简单分数 Top 5 相对全品种均值边际 `-4,543.49`
  - 简单分数 Top 5 top-half率 `45.20%`
- AI分桶结果：
  - `q1` top-half率 `43.33%`，平均未来60日净贡献 `-1,159`
  - `q2` top-half率 `54.79%`，平均未来60日净贡献 `2,256`
  - `q3` top-half率 `57.56%`，平均未来60日净贡献 `6,092`
  - `q4` top-half率 `50.56%`，平均未来60日净贡献 `3,765`
  - `q5` top-half率 `50.00%`，平均未来60日净贡献 `12,615`
- 走前窗口：
  - `wf_01` AUC `0.5196`，月度 rank IC `0.0371`
  - `wf_02` AUC `0.5394`，月度 rank IC `0.0647`
  - `wf_03` AUC `0.4967`，月度 rank IC `0.0802`
  - `wf_04` AUC `0.6133`，月度 rank IC `0.1933`
  - `wf_05` AUC `0.4328`，月度 rank IC `-0.0254`
  - `wf_06` AUC `0.5469`，月度 rank IC `0.1389`
  - `wf_07` AUC `0.4623`，月度 rank IC `-0.0130`
  - `wf_08` AUC `0.4874`，月度 rank IC `-0.0517`
  - `wf_09` AUC `0.5693`，月度 rank IC `0.2352`
- 年度拆分：
  - `2022` AI Top 5 平均边际 `+11,247`，top-half率 `53.33%`
  - `2023` AI Top 5 平均边际 `+11,542`，top-half率 `56.67%`
  - `2024` AI Top 5 平均边际 `+12,826`，top-half率 `50.00%`
  - `2025` AI Top 5 平均边际 `+16`，top-half率 `43.33%`
  - `2026` AI Top 5 平均边际 `+6,446`，top-half率 `50.00%`

## 验证

- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_ai_product_suitability_walkforward.py examples/portfolio_backtesting/analyze_qmt_roll_ai_product_suitability_market_walkforward.py`
- 已运行V2影子分析并生成上述输出

## 我的判断

- 主连市场地形特征确实让问题定义更干净：
  - 第65阶段只看系统自身路径，容易把“过去系统在某品种赚过钱”误当作适配度
  - 第66阶段加入价格、波动、成交量、持仓量和趋势效率后，AI Top 5 边际从 `+4,489` 提高到 `+8,809`
  - `2026` 从第65阶段的明显负边际改善为正边际
- 但这仍然不能接入正式交易：
  - AUC 只有 `0.5180`
  - 月度 rank IC 只有 `0.0622`
  - top-half率只有 `50.80%`
  - `2025` 仍然偏弱，说明它没有稳定穿越所有环境
  - 分桶的top-half率不单调，概率不能直接当仓位或白名单强度
- 当前结论：
  - “AI筛选更适合趋势系统的品种”这个方向成立为研究方向
  - 但还没有成立为交易规则
  - 下一步不应该立刻改正式策略，而应先做动态品种池影子组合对照，要求在不调参的前提下改善收益回撤比、减少低适配品种交易消耗，并且不能牺牲跨年度稳定性

# 第67阶段：AI动态品种池影子组合归因

## 改动时间

- `2026-04-24 20:44 CST`

## 本次版本改动内容

- 新增AI动态品种池影子组合脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_ai_product_pool_shadow_portfolio.py`
- 本阶段不改变正式交易策略，不接入正式品种过滤，不修改 `qmt_roll_portfolio_strategy.py`
- 本阶段不是正式可执行 vn.py 回测：
  - 它基于第53阶段冻结的逐日逐合约 `position_changes` 做归因式影子组合
  - 不重算过滤后的资金曲线下的仓位规模
  - 不补做被过滤后可能出现的替代交易
  - 只用于判断AI品种池是否值得进入下一层正式回测
- 影子组合设计：
  - 使用第66阶段V2样本外月度预测
  - 月末信号只在下一交易日之后生效
  - 避免同日和未来信息泄露
  - 只做入场过滤，不做月度强制平仓
  - 评估起点已有仓位按原始路径持有到原始退出
- 新增输出：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_product_pool_shadow_portfolio_daily_ai_product_pool_shadow_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_product_pool_shadow_portfolio_summary_ai_product_pool_shadow_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_product_pool_shadow_portfolio_yearly_ai_product_pool_shadow_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_product_pool_shadow_portfolio_product_attribution_ai_product_pool_shadow_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_product_pool_shadow_portfolio_product_year_attribution_ai_product_pool_shadow_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_product_pool_shadow_portfolio_eligibility_ai_product_pool_shadow_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_product_pool_shadow_portfolio_summary_ai_product_pool_shadow_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_product_pool_shadow_portfolio_report_ai_product_pool_shadow_v1.md`

## 回测参数

- 本阶段未运行新的正式 vn.py 回测
- 沿用第53阶段正式第一候选口径：
  - `risk_ratio = 0.045`
  - `capital = 200,000`
  - `analysis_start = 2020-01-01`
  - `analysis_end = 2026-04-30`
  - `enable_selection_pairwise_v2 = True`
  - `selection_pairwise_volume_tilt_long_strength = 0.15`
  - `selection_pairwise_volume_tilt_long_base_volume_reference = 30.0`
  - `enable_same_direction_correlation_gate = True`
  - `same_direction_correlation_gate_lookback = 20`
  - `same_direction_correlation_gate_start = 0.60`
  - `same_direction_correlation_gate_full = 0.80`
  - `same_direction_correlation_gate_weight_floor = 0.35`

## 新增的参数

- 影子模型标签：
  - `MODEL_TAG = ai_product_pool_shadow_v1`
- 信号来源：
  - `product_suitability_market_wf_v2`
- 第一个样本外预测日期：
  - `first_prediction_eval_date = 2022-01-28`
- 影子组合评估起点：
  - `evaluation_start = 2022-02-07`
- 影子组合初始权益：
  - `initial_balance = 1,428,780`
- 信号生效规则：
  - `latest eval_date strictly earlier than trade date`
- 既有持仓处理规则：
  - `positions already open at evaluation_start are kept until original exit`
- 年化交易日：
  - `TRADING_DAYS_PER_YEAR = 240`
- 动态品种池方案：
  - `baseline_all_products`
  - `ai_top5_entry_filter`
  - `ai_top8_entry_filter`
  - `simple_top5_entry_filter`

## 修改的参数

- 无正式策略参数修改

## 删除的参数

- 无

## 新增的回测结果

- 无新的正式 vn.py 回测结果
- 沿用第53阶段正式第一候选完整周期结果：
  - `期末权益 = 2,902,355`
  - `总收益 = 1351.18%`
  - `最大回撤 = -36.99%`
  - `Sharpe = 1.0225`
  - `总滑点 = 349,080`
  - `总交易次数 = 1158`

## 修改的回测结果

- 无

## 删除的回测结果

- 无

## 新增的影子组合结果

- 评估周期：
  - `2022-02-07` 到 `2026-04-21`
  - 交易日 `1020`
  - 初始权益 `1,428,780`
- 冻结正式路径基准 `baseline_all_products`：
  - 期末权益 `2,902,355`
  - 区间收益 `103.14%`
  - 最大回撤 `-28.66%`
  - Sharpe `0.7096`
  - 总滑点 `287,470`
  - 总交易次数 `829`
- `ai_top8_entry_filter`：
  - 期末权益 `3,172,760`
  - 相对基准 `+270,405`
  - 区间收益 `122.06%`
  - 最大回撤 `-21.15%`
  - Sharpe `1.0501`
  - 总滑点 `133,260`
  - 总交易次数 `357`
  - 保留交易次数比例 `43.06%`
  - 保留滑点比例 `46.36%`
- `ai_top5_entry_filter`：
  - 期末权益 `2,767,185`
  - 相对基准 `-135,170`
  - 区间收益 `93.67%`
  - 最大回撤 `-11.18%`
  - Sharpe `1.0314`
  - 总滑点 `82,240`
  - 总交易次数 `206`
  - 保留交易次数比例 `24.85%`
  - 保留滑点比例 `28.61%`
- `simple_top5_entry_filter`：
  - 期末权益 `1,282,695`
  - 相对基准 `-1,619,660`
  - 区间收益 `-10.22%`
  - 最大回撤 `-37.58%`
  - Sharpe `0.0021`
  - 总滑点 `76,200`
  - 总交易次数 `215`
- `ai_top8_entry_filter` 年度相对基准：
  - `2022` `+162,755`
  - `2023` `+451,955`
  - `2024` `+114,285`
  - `2025` `-634,140`
  - `2026` `+175,550`
- `ai_top5_entry_filter` 年度相对基准：
  - `2022` `+46,455`
  - `2023` `+346,375`
  - `2024` `+65,830`
  - `2025` `-740,170`
  - `2026` `+146,340`
- `ai_top8_entry_filter` 在 `2025` 的主要误伤：
  - `SH.CZCE` 少赚 `501,540`
  - `cu.SHFE` 少赚 `170,950`
  - `SA.CZCE` 少赚 `130,420`
  - `CF.CZCE` 少赚 `115,850`
- `ai_top8_entry_filter` 在 `2025` 也过滤掉部分亏损：
  - `jm.DCE` 避免 `114,690`
  - `si.GFEX` 避免 `72,600`
  - `AP.CZCE` 避免 `61,380`
  - `OI.CZCE` 避免 `56,760`
  - 但避免亏损不足以抵消错过 `SH.CZCE / cu.SHFE / SA.CZCE / CF.CZCE` 的趋势利润

## 验证

- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_ai_product_pool_shadow_portfolio.py`
- 已运行影子组合归因：
  - `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_ai_product_pool_shadow_portfolio.py`

## 我的判断

- 第67阶段比第65/66阶段更接近“能否用于策略”的核心问题，因为它不只看排名IC，而是看组合路径
- AI品种池显示出真实边际：
  - `ai_top8` 提高期末权益 `270,405`
  - 最大回撤从 `-28.66%` 改善到 `-21.15%`
  - Sharpe 从 `0.7096` 改善到 `1.0501`
  - 交易次数和滑点明显下降
  - 简单规则Top5显著失败，说明不是“少交易自然变好”
- 但它仍不能直接接入正式策略：
  - `2025` 错过大趋势品种，年度相对基准 `-634,140`
  - `ai_top5` 太窄，防守很好但损失收益
  - `ai_top8` 比较合理，但仍可能把强趋势早期误判为低适配
  - 本阶段没有重算资金规模和替代交易，只是冻结路径归因
- 当前结论：
  - AI品种池方向值得进入“正式回测前验证层”
  - 不能直接实盘或直接改正式策略
  - 下一步如果继续，应做正式动态品种池回测，但必须采用固定、低自由度规则，例如 `ai_top8` 或“只剔除低分尾部”，并且重点检验 `2025` 这类趋势爆发年份是否会被误伤

# 第68阶段：AI Top8动态品种池正式回测

## 改动时间

- `2026-04-24 20:52 CST`

## 本次版本改动内容

- 在正式组合策略中新增默认关闭的AI动态品种池过滤参数：
  - `enable_ai_product_pool_filter`
  - `ai_product_pool_eligibility_path`
  - `ai_product_pool_strategy`
- 新增正式回测脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_ai_product_pool_formal_backtest.py`
- 正式策略默认行为不变：
  - 不开启 `enable_ai_product_pool_filter` 时，原策略不受影响
- 本次正式回测固定使用第67阶段影子组合中较稳的 `ai_top8_entry_filter`
- 信号规则：
  - 月末AI信号只在下一交易日及之后生效
  - 第一个样本外AI信号为 `2022-01-28`
  - 信号前 `2020-2021` 保持原策略不过滤
- 技术修复：
  - 修复 `target_bar.datetime` 带时区而AI信号日期无时区导致的比较错误
  - 统一转换为无时区日期后进行信号匹配
- 新增输出：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_ai_product_pool_formal_summary.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_ai_product_pool_formal_summary.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_ai_top8_product_pool_formal_daily.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_ai_top8_product_pool_formal_daily_equity.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_ai_top8_product_pool_formal_trades_2020_2026_04.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_ai_top8_product_pool_formal_position_changes_2020_2026_04.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_ai_top8_product_pool_formal_end_positions_wide_2020_2026_04.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_ai_top8_product_pool_formal_entry_risk_diagnostics_2020_2026_04.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_ai_top8_product_pool_formal_entry_candidate_snapshots_2020_2026_04.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_ai_top8_product_pool_formal_entry_candidate_snapshots_schema.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_ai_top8_product_pool_formal_statistics.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_ai_top8_product_pool_formal_chart.html`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_ai_top8_product_pool_formal_professional_dashboard.html`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_ai_top8_product_pool_formal_trade_review.html`

## 回测参数

- `risk_ratio = 0.045`
- `capital = 200,000`
- `analysis_start = 2020-01-01`
- `analysis_end = 2026-04-30`
- `enable_selection_pairwise_v2 = True`
- `enable_selection_pairwise_v2_catastrophic_veto = False`
- `enable_selection_pairwise_v2_volume_tilt = True`
- `selection_pairwise_volume_tilt_strength = 0.0`
- `selection_pairwise_volume_tilt_long_strength = 0.15`
- `selection_pairwise_volume_tilt_short_strength = 0.0`
- `selection_pairwise_volume_tilt_long_base_volume_reference = 30.0`
- `enable_same_direction_correlation_gate = True`
- `same_direction_correlation_gate_lookback = 20`
- `same_direction_correlation_gate_start = 0.60`
- `same_direction_correlation_gate_full = 0.80`
- `same_direction_correlation_gate_weight_floor = 0.35`
- `enable_ai_product_pool_filter = True`
- `ai_product_pool_strategy = ai_top8_entry_filter`
- `ai_product_pool_eligibility_path = examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_product_pool_shadow_portfolio_eligibility_ai_product_pool_shadow_v1.csv`

## 新增的参数

- `enable_ai_product_pool_filter`
- `ai_product_pool_eligibility_path`
- `ai_product_pool_strategy`

## 修改的参数

- 无既有正式参数修改
- 本次仅在实验回测中开启新增AI品种池参数

## 删除的参数

- 无

## 新增的回测结果

- 实验名：
  - `ai_top8_product_pool`
- 文件前缀：
  - `qmt_roll_selection_long015_volref30_corr_ai_top8_product_pool_formal`
- 正式回测结果：
  - `期末权益 = 3,894,190`
  - `总收益 = 1847.09%`
  - `年化收益 = 290.69%`
  - `最大回撤 = -36.99%`
  - `Sharpe = 1.2080`
  - `Return Drawdown Ratio = 6.8319`
  - `总滑点 = 257,880`
  - `总交易次数 = 720`
  - `总净盈亏 = 3,694,190`
  - `盈利日 = 546`
  - `亏损日 = 595`
- 相对第53阶段正式第一候选：
  - 期末权益增加 `+991,835`
  - 总收益增加 `+495.91` 个百分点
  - 最大回撤基本持平，差值 `-0.0007` 个百分点
  - Sharpe 增加 `+0.1855`
  - 总滑点减少 `-91,200`
  - 总交易次数减少 `-438`

## 修改的回测结果

- 无既有回测结果修改

## 删除的回测结果

- 无

## 年度拆分

- `2020`：
  - AI Top8 与基准一致，净盈亏差 `0`
- `2021`：
  - AI Top8 与基准一致，净盈亏差 `0`
- `2022`：
  - AI Top8 净盈亏 `180,895`
  - 基准净盈亏 `246,310`
  - 差值 `-65,415`
- `2023`：
  - AI Top8 净盈亏 `702,030`
  - 基准净盈亏 `255,635`
  - 差值 `+446,395`
- `2024`：
  - AI Top8 净盈亏 `437,290`
  - 基准净盈亏 `179,425`
  - 差值 `+257,865`
- `2025`：
  - AI Top8 净盈亏 `1,243,330`
  - 基准净盈亏 `953,360`
  - 差值 `+289,970`
- `2026`：
  - AI Top8 净盈亏 `-54,260`
  - 基准净盈亏 `-117,280`
  - 差值 `+63,020`

## AI信号生效后区间对比

- 区间：
  - `2022-02-07` 到 `2026-04-21`
- 基准：
  - 期末权益 `2,902,355`
  - 区间收益 `103.14%`
  - 最大回撤 `-28.66%`
  - Sharpe `0.7096`
  - 交易次数 `829`
  - 总滑点 `287,470`
- AI Top8：
  - 期末权益 `3,894,190`
  - 区间收益 `172.55%`
  - 最大回撤 `-27.88%`
  - Sharpe `1.0938`
  - 交易次数 `391`
  - 总滑点 `196,270`

## AI品种池过滤统计

- 候选记录总数：
  - `1010`
- AI品种池拦截候选：
  - `234`
- 最终开仓候选：
  - `333`
- 年度拦截数：
  - `2020`：`0`
  - `2021`：`0`
  - `2022`：`49`
  - `2023`：`61`
  - `2024`：`59`
  - `2025`：`48`
  - `2026`：`17`
- 拦截次数最多的品种：
  - `rb.SHFE` `23`
  - `OI.CZCE` `19`
  - `sp.SHFE` `18`
  - `CF.CZCE` `18`
  - `hc.SHFE` `18`

## 验证

- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_ai_product_pool_formal_backtest.py`
- 已运行正式回测：
  - `.py311/bin/python examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_ai_product_pool_formal_backtest.py`

## 我的判断

- 第68阶段是到目前为止AI品种池方向最有价值的一步：
  - 影子归因的优势在正式回测中没有消失，反而更明显
  - 全周期期末权益提高接近 `100万`
  - 交易次数减少 `37.8%`
  - 滑点减少 `26.1%`
  - `2023 / 2024 / 2025 / 2026` 均优于基准
- 但仍不能直接实盘化：
  - 最大回撤没有改善，因为最大回撤来自 `2021`，AI信号尚未生效
  - `2022` 生效初期表现弱于基准
  - `ai_top8` 是经过影子验证后选出的固定规则，仍需要稳健性验证，不能继续调成更好看的 `topN`
- 当前结论：
  - `ai_top8` 动态品种池已经有资格成为新的正式候选版本
  - 下一步应该做抗过拟合验证：
    - 不改变AI模型
    - 不继续搜索 `topN`
    - 做年度剔除、滑点压力、低分尾部剔除对照、以及2022起点敏感性
  - 如果这些验证仍成立，才考虑把它提升为正式第一候选

# 第69阶段：AI Top8正式结果稳健性验证

## 改动时间

- `2026-04-24 20:55 CST`

## 本次版本改动内容

- 新增AI Top8正式结果稳健性分析脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_ai_product_pool_formal_robustness.py`
- 本阶段不改变正式策略逻辑，不搜索新的 `topN`，不改AI模型
- 验证目标：
  - 判断第68阶段 `+991,835` 的优势是否依赖单一年份
  - 判断优势是否依赖低滑点假设
  - 判断不同起点下是否仍优于基准
- 新增输出：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_product_pool_formal_robustness_leave_one_year_ai_top8_formal_robustness_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_product_pool_formal_robustness_slippage_stress_ai_top8_formal_robustness_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_product_pool_formal_robustness_start_date_ai_top8_formal_robustness_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_product_pool_formal_robustness_summary_ai_top8_formal_robustness_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_product_pool_formal_robustness_report_ai_top8_formal_robustness_v1.md`

## 回测参数

- 本阶段未运行新的正式回测
- 使用第68阶段正式回测结果做稳健性分析：
  - `baseline = qmt_roll_selection_long015_volref30_corr_formal_floor35`
  - `ai = qmt_roll_selection_long015_volref30_corr_ai_top8_product_pool_formal`
- 使用第68阶段正式AI Top8结果：
  - `期末权益 = 3,894,190`
  - `总收益 = 1847.09%`
  - `最大回撤 = -36.99%`
  - `Sharpe = 1.2080`
  - `总滑点 = 257,880`
  - `总交易次数 = 720`

## 新增的参数

- 稳健性模型标签：
  - `MODEL_TAG = ai_top8_formal_robustness_v1`
- AI信号生效后起点：
  - `POST_SIGNAL_START = 2022-02-07`
- 滑点压力倍数：
  - `SLIPPAGE_MULTIPLIERS = 1.0 / 2.0 / 3.0 / 5.0`
- 起点敏感性日期：
  - `2022-02-07`
  - `2023-01-03`
  - `2024-01-02`
  - `2025-01-02`
  - `2026-01-02`

## 修改的参数

- 无

## 删除的参数

- 无

## 新增的回测结果

- 无新的正式回测结果
- 本阶段新增的是第68阶段正式结果的稳健性分析

## 修改的回测结果

- 无

## 删除的回测结果

- 无

## 年度剔除验证

- 剔除 `2022`：
  - AI相对基准净盈亏差 `+1,057,250`
  - Sharpe差 `+0.5884`
- 剔除 `2023`：
  - AI相对基准净盈亏差 `+545,440`
  - Sharpe差 `+0.2588`
- 剔除 `2024`：
  - AI相对基准净盈亏差 `+733,970`
  - Sharpe差 `+0.3799`
- 剔除 `2025`：
  - AI相对基准净盈亏差 `+701,865`
  - Sharpe差 `+0.4165`
- 剔除 `2026`：
  - AI相对基准净盈亏差 `+928,815`
  - Sharpe差 `+0.3837`

## 滑点压力验证

- 全周期 `1x` 滑点：
  - AI相对基准期末权益差 `+991,835`
  - Sharpe差 `+0.1665`
- 全周期 `2x` 滑点：
  - AI相对基准期末权益差 `+1,083,035`
  - Sharpe差 `+0.1846`
- 全周期 `3x` 滑点：
  - AI相对基准期末权益差 `+1,174,235`
  - Sharpe差 `+0.2052`
- 全周期 `5x` 滑点：
  - AI相对基准期末权益差 `+1,356,635`
  - Sharpe差 `+0.2565`
- AI信号生效后区间 `5x` 滑点：
  - AI相对基准期末权益差 `+1,356,635`
  - Sharpe差 `+0.4874`
  - 说明优势不是依赖低滑点，反而来自减少交易和滑点暴露

## 起点敏感性验证

- 从 `2022-02-07` 开始：
  - AI相对基准期末权益差 `+991,835`
  - Sharpe差 `+0.3842`
- 从 `2023-01-03` 开始：
  - AI相对基准期末权益差 `+1,057,250`
  - Sharpe差 `+0.5871`
- 从 `2024-01-02` 开始：
  - AI相对基准期末权益差 `+610,855`
  - Sharpe差 `+0.3803`
- 从 `2025-01-02` 开始：
  - AI相对基准期末权益差 `+352,990`
  - Sharpe差 `+0.3087`
- 从 `2026-01-02` 开始：
  - AI相对基准期末权益差 `+63,020`
  - Sharpe差 `+0.4158`

## 验证

- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_ai_product_pool_formal_robustness.py`
- 已运行稳健性分析：
  - `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_ai_product_pool_formal_robustness.py`

## 我的判断

- 第69阶段没有推翻第68阶段结果，反而增强了可信度：
  - 剔除任一年后AI仍然明显优于基准
  - 滑点越高，AI相对优势越大
  - 从 `2022/2023/2024/2025/2026` 任一测试起点开始，AI均优于基准
- 这个结果说明AI Top8不是单纯靠某一年或低摩擦环境成立
- 但仍要保持边界：
  - 这还不是“AI会预测方向”
  - 它更像一个减少低适配品种消耗的品种地形过滤器
  - 不应该继续搜索更优 `topN`
- 当前结论：
  - `ai_top8` 动态品种池可以升级为新的正式第一候选版本
  - 下一步应进入准实盘前治理：
    - 固定模型和Top8规则
    - 增加每日候选和拦截监控
    - 记录被拦截品种未来路径，重点防止误杀早期大趋势
    - 不允许在没有新增样本的情况下继续调参

# 2026-04-24 21:03 第70阶段：AI Top8正式品种池准实盘监控与误杀跟踪

## 改动时间点

- `2026-04-24 21:03`

## 本次版本改动内容

- 新增AI Top8正式品种池监控脚本：
  - `examples/portfolio_backtesting/build_qmt_roll_ai_product_pool_formal_monitor_report.py`
- 本阶段不重新训练模型、不搜索 `topN`、不修改正式策略参数
- 监控目标：
  - 固定第68阶段 `ai_top8_entry_filter`
  - 输出最新AI品种池
  - 汇总被AI品种池拦截的候选
  - 用基准品种日度归因标记被拦截事件后续 `20/60` 个交易日路径
  - 重点识别“误杀早期趋势”和“规避亏损”两类事件

## 新增的参数

- 监控脚本内部新增阈值，不进入交易策略参数：
  - `TOP_N = 8`
  - `FUTURE_WINDOWS = (20, 60)`
  - `MISSED_TREND_60D_NET_PNL_THRESHOLD = 50,000`
  - `MISSED_TREND_60D_RUNUP_THRESHOLD = 100,000`
  - `AVOIDED_LOSS_60D_NET_PNL_THRESHOLD = -50,000`
  - `BORDERLINE_RANK_MAX = 12`

## 修改的参数

- 无

## 删除的参数

- 无

## 新增的回测结果

- 无新增回测
- 本阶段新增的是第68阶段正式候选的准实盘治理监控结果

## 修改的回测结果

- 无

## 删除的回测结果

- 无

## 沿用的当前正式候选结果

- 期末权益 `3,894,190`
- 总收益 `1847.09%`
- 最大回撤 `-36.99%`
- Sharpe `1.2080`
- 总滑点 `257,880`
- 总交易次数 `720`

## 新增监控结果

- 最新AI评估日：`2026-02-27`
- 最新Top8品种池：
  - `ru.SHFE`
  - `SH.CZCE`
  - `si.GFEX`
  - `AP.CZCE`
  - `lh.DCE`
  - `OI.CZCE`
  - `MA.CZCE`
  - `SA.CZCE`
- 历史AI拦截候选数：`234`
- 其中边界排名 `9-12` 的拦截事件：`84`
- `60` 日误杀趋势风险事件：`33`
- `60` 日规避亏损事件：`27`
- 年度误杀趋势风险事件：
  - `2022`：`3`
  - `2023`：`5`
  - `2024`：`10`
  - `2025`：`14`
  - `2026`：`1`
- 年度规避亏损事件：
  - `2022`：`5`
  - `2023`：`9`
  - `2024`：`9`
  - `2025`：`3`
  - `2026`：`1`
- 误杀风险最高的品种：
  - `SH.CZCE`：拦截 `9` 次，误杀风险 `6` 次，60日后续均值 `116,687`
  - `SA.CZCE`：拦截 `15` 次，误杀风险 `5` 次，60日后续均值 `55,785`
  - `jm.DCE`：拦截 `13` 次，误杀风险 `3` 次，同时规避亏损 `6` 次
  - `OI.CZCE`：拦截 `19` 次，误杀风险 `3` 次，边界排名事件 `10` 次
  - `cu.SHFE`：拦截 `12` 次，误杀风险 `3` 次，边界排名事件 `7` 次

## 新增产物

- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_product_pool_formal_monitor_latest_pool_ai_top8_formal_monitor_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_product_pool_formal_monitor_blocked_events_ai_top8_formal_monitor_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_product_pool_formal_monitor_blocked_by_year_ai_top8_formal_monitor_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_product_pool_formal_monitor_blocked_by_product_ai_top8_formal_monitor_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_product_pool_formal_monitor_blocked_by_signal_ai_top8_formal_monitor_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_product_pool_formal_monitor_review_template_ai_top8_formal_monitor_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_product_pool_formal_monitor_summary_ai_top8_formal_monitor_v1.json`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_product_pool_formal_monitor_report_ai_top8_formal_monitor_v1.md`

## 验证

- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/build_qmt_roll_ai_product_pool_formal_monitor_report.py`
- 已运行监控报告生成：
  - `.py311/bin/python examples/portfolio_backtesting/build_qmt_roll_ai_product_pool_formal_monitor_report.py`

## 我的判断

- 第70阶段的本质不是继续优化收益，而是建立AI品种池的失效观测面
- 监控结果说明：
  - AI Top8仍然值得作为正式第一候选，因为第68和第69阶段已经证明其组合路径优势
  - 但历史上确实存在 `33` 次后续趋势误杀风险，尤其集中在 `2024-2025`
  - `SH.CZCE` 和 `SA.CZCE` 是最需要人工复盘的误杀风险品种
  - `jm.DCE` 这种品种同时有误杀和规避亏损，不能简单加白名单
- 不能把被拦截事件后续PnL直接相加当成可获得收益：
  - 事件路径会重叠
  - 同一品种可能被多次拦截
  - 这些数字只能作为治理标签，不是可交易收益
- 下一步如果继续，应做“只监控不交易”的准实盘日报：
  - 每日记录Top8
  - 记录被拦截候选
  - 重点观察排名 `9-12` 且重复出现的品种
  - 在没有新增样本前，不应修改 `topN`

# 2026-04-24 21:14 第71阶段：AI Top8多周期重启回测

## 改动时间点

- `2026-04-24 21:14`

## 本次版本改动内容

- 新增多周期重启回测脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_ai_product_pool_multicycle_backtest.py`
- 固定对照：
  - `baseline_floor35`
  - `ai_top8_product_pool`
- 固定规则：
  - 不重新训练AI模型
  - 不搜索 `topN`
  - 不修改交易策略参数
  - 每个周期尽量保留一年预热上下文后做分析窗口统计
- 本阶段不是简单切已有日度权益，而是重新调用 `run_backtest` 跑多周期对照

## 新增的参数

- 仅新增回测脚本内部周期配置，不进入交易策略：
  - `MODEL_TAG = ai_top8_multicycle_v1`
  - `CAPITAL = 200,000`
  - `CYCLE_WINDOWS`：
    - `full_2020_2026`：`2020-01-01` 至 `2026-04-30`
    - `pre_ai_2020_2021`：`2020-01-01` 至 `2021-12-31`
    - `post_signal_2022_2026`：`2022-02-07` 至 `2026-04-30`
    - `early_ai_2022_2023`：`2022-02-07` 至 `2023-12-31`
    - `trend_rich_2024_2025`：`2024-01-01` 至 `2025-12-31`
    - `latest_2026`：`2026-01-01` 至 `2026-04-30`

## 修改的参数

- 无

## 删除的参数

- 无

## 新增的回测结果

### 全周期 `full_2020_2026`

- AI Top8：
  - 期末权益 `3,894,190`
  - 总收益 `1847.09%`
  - 最大回撤 `-36.99%`
  - Sharpe `1.2080`
  - 总滑点 `257,880`
  - 总交易次数 `720`
- 相对基准：
  - 期末权益 `+991,835`
  - 总收益 `+495.92` 个百分点
  - 最大回撤差 `0.00` 个百分点
  - Sharpe `+0.1855`
  - 总滑点 `-91,200`
  - 总交易次数 `-438`

### AI生效前 `pre_ai_2020_2021`

- AI Top8：
  - 期末权益 `1,384,905`
  - 总收益 `592.45%`
  - 最大回撤 `-36.99%`
  - Sharpe `1.6313`
  - 总滑点 `57,190`
  - 总交易次数 `306`
- 相对基准：
  - 期末权益差 `0`
  - 总收益差 `0.00` 个百分点
  - 最大回撤差 `0.00` 个百分点
  - Sharpe差 `0.0000`
  - 总滑点差 `0`
  - 总交易次数差 `0`
- 说明AI生效前没有产生额外路径偏差，这是一个必要的完整性校验

### AI信号生效后 `post_signal_2022_2026`

- AI Top8：
  - 期末权益 `2,048,580`
  - 总收益 `924.29%`
  - 最大回撤 `-50.58%`
  - Sharpe `1.0486`
  - 总滑点 `153,630`
  - 总交易次数 `372`
- 相对基准：
  - 期末权益 `+1,278,600`
  - 总收益 `+639.30` 个百分点
  - 最大回撤改善 `+7.80` 个百分点
  - Sharpe `+0.5696`
  - 总滑点 `-4,300`
  - 总交易次数 `-359`

### AI早期样本 `early_ai_2022_2023`

- AI Top8：
  - 期末权益 `562,750`
  - 总收益 `181.38%`
  - 最大回撤 `-50.58%`
  - Sharpe `0.9895`
  - 总滑点 `31,840`
  - 总交易次数 `156`
- 相对基准：
  - 期末权益 `+242,825`
  - 总收益 `+121.41` 个百分点
  - 最大回撤改善 `+6.23` 个百分点
  - Sharpe `+0.6001`
  - 总滑点 `-9,865`
  - 总交易次数 `-142`

### 趋势富集期 `trend_rich_2024_2025`

- AI Top8：
  - 期末权益 `759,500`
  - 总收益 `279.75%`
  - 最大回撤 `-38.82%`
  - Sharpe `1.2459`
  - 总滑点 `38,020`
  - 总交易次数 `147`
- 相对基准：
  - 期末权益 `+562,820`
  - 总收益 `+281.41` 个百分点
  - 最大回撤改善 `+4.96` 个百分点
  - Sharpe `+1.2714`
  - 总滑点 `+22,360`
  - 总交易次数 `-61`
- 注意：
  - 这一段AI虽然显著优于基准，但滑点高于基准
  - 说明AI Top8不是单纯减少交易成本，还可能集中到更大合约或更高摩擦路径

### 最新尾部 `latest_2026`

- AI Top8：
  - 期末权益 `192,765`
  - 总收益 `-3.62%`
  - 最大回撤 `-16.17%`
  - Sharpe `-0.5194`
  - 总滑点 `1,390`
  - 总交易次数 `18`
- 相对基准：
  - 期末权益 `+161,755`
  - 总收益 `+80.88` 个百分点
  - 最大回撤改善 `+71.86` 个百分点
  - Sharpe `+3.2646`
  - 总滑点 `-4,950`
  - 总交易次数 `-31`
- 注意：
  - AI仍是亏损，只是显著少亏
  - 不能把这一段解释为“最新环境已经恢复赚钱”

## 修改的回测结果

- 无

## 删除的回测结果

- 无

## 新增产物

- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_product_pool_multicycle_backtest_summary_ai_top8_multicycle_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_product_pool_multicycle_backtest_comparison_ai_top8_multicycle_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_product_pool_multicycle_backtest_curves_ai_top8_multicycle_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_product_pool_multicycle_backtest_summary_ai_top8_multicycle_v1.json`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_product_pool_multicycle_backtest_report_ai_top8_multicycle_v1.md`

## 验证

- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_ai_product_pool_multicycle_backtest.py`
- 已完成多周期重启回测：
  - `.py311/bin/python examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_ai_product_pool_multicycle_backtest.py`

## 我的判断

- 第71阶段显著增强了AI Top8的可信度：
  - AI生效前与基准完全一致，说明开关没有污染历史路径
  - AI生效后整体明显优于基准
  - `2022-2023` 早期样本优于基准
  - `2024-2025` 趋势富集期优于基准
  - `2026` 最新尾部虽然AI仍亏损，但比基准少亏很多
- 这说明AI Top8不是只靠某一个年份或全周期复利路径成立
- 但也不能过度乐观：
  - `latest_2026` 仍为负收益
  - `trend_rich_2024_2025` 的AI滑点高于基准
  - AI Top8的价值更像“减少错误暴露和大回撤”，不是保证每段都盈利
- 当前判断：
  - AI Top8仍应保持正式第一候选
  - 不应继续调 `topN`
  - 下一步应做准实盘日报和滑点异常归因，尤其跟踪AI集中交易导致的摩擦成本上升

# 2026-04-24 21:53 第72阶段：全市场扩池压力测试与AI筛选否决

## 本次版本改动内容

- 新增全市场可交易池构建脚本：
  - `examples/portfolio_backtesting/build_qmt_roll_full_market_tradable_universe.py`
- 新增全市场正式基线回测脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_full_market_universe_formal_backtest.py`
- 新增全市场AI品种适配度walk-forward脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_ai_product_suitability_full_market_walkforward.py`
- 新增全市场AI品种池shadow过滤脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_ai_product_pool_full_market_shadow_portfolio.py`
- 修改动态品种宇宙基础设施：
  - `examples/portfolio_backtesting/main_contract_mapping.py`
  - `examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
  - `examples/portfolio_backtesting/run_qmt_roll_backtest.py`
- 核心原则：
  - 默认仍保持原18品种，不影响既有正式AI Top8版本
  - 只有显式传入 `product_universe_csv_path` 时才启用全市场候选池

## 新增的参数

- `product_universe_csv_path`
  - 用于在回测引擎和策略内部同时切换动态品种宇宙
  - 默认空字符串，保持原18品种逻辑不变
- 全市场可交易池过滤参数：
  - `recent_days = 240`
  - `min_mapping_days = 360`
  - `min_recent_mapping_days = 120`
  - `min_recent_bar_coverage = 0.75`
  - `min_recent_nonzero_volume_ratio = 0.60`
  - `min_recent_median_volume = 100`
  - `default_margin_ratio = 0.15`
  - `capital = 200,000`
  - `max_single_trade_capital_usage_ratio = 0.70`
- 全市场shadow池预设：
  - `ai_top8_entry_filter`
  - `ai_top12_entry_filter`
  - `simple_top8_entry_filter`

## 修改的参数

- 正式18品种AI Top8版本参数未修改
- `main_contract_mapping.build_daily_mapping()` 和 `build_contract_metadata()` 增加可选 `supported_symbols`
- `run_qmt_roll_backtest.build_backtest_engine()` 增加可选 `product_universe_csv_path`

## 删除的参数

- 无

## 新增的回测结果

### 全市场可交易池

- 原始连续品种数：`86`
- 可交易候选品种数：`50`
- 原18品种保留数：`18`
- 新增可交易候选品种数：`32`
- 回测合约数从原18品种的 `736` 增加到全市场候选池的 `2881`

### 全市场50品种正式基线回测

- 回测脚本：
  - `.py311/bin/python examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_full_market_universe_formal_backtest.py`
- 回测参数：
  - 基础策略：`volref30_corr20_06_08_floor35`
  - 初始资金：`200,000`
  - 品种池：全市场可交易候选池50品种
  - 不启用AI品种池过滤
- 结果：
  - 期末权益 `113,455`
  - 总收益 `-43.27%`
  - 最大回撤 `-81.09%`
  - Sharpe `-0.1812`
  - 总滑点 `106,750`
  - 总交易次数 `1733`
- 对比第53阶段18品种基线：
  - 期末权益减少 `-2,788,900`
  - 总收益降低约 `-1394.45` 个百分点
  - 最大回撤恶化约 `-44.10` 个百分点
  - Sharpe降低约 `-1.2037`
  - 总交易次数增加 `+575`

### 全市场AI品种适配度walk-forward

- 样本：
  - 产品数 `50`
  - 样本行数 `3700`
  - 预测行数 `2500`
  - 预测月份 `50`
  - 特征数 `136`
  - 市场地形特征数 `28`
- AI结果：
  - AUC `0.5559`
  - 月度Rank IC `0.0626`
  - Spearman vs 未来PnL `0.0635`
  - Top5平均60日未来PnL `62.86`
  - Top5相对全市场均值优势 `+227.01`
- 简单分数结果：
  - AUC `0.5079`
  - 月度Rank IC `0.0132`
- 判断：
  - AI在全市场横截面中有弱排序信号
  - 但排序信号强度不足以直接证明可交易

### 全市场AI品种池shadow过滤

- 评估起点：`2022-02-07`
- 初始权益：`240,410`
- 冻结路径基线：
  - 期末权益 `113,455`
  - 总收益 `-52.81%`
  - 最大回撤 `-61.85%`
  - Sharpe `-0.1332`
  - 总滑点 `60,830`
  - 总交易次数 `1109`
- `ai_top8_entry_filter`：
  - 期末权益 `156,300`
  - 相对基线 `+42,845`
  - 总收益 `-34.99%`
  - 最大回撤 `-35.81%`
  - Sharpe `-0.7386`
  - 总滑点 `7,050`
  - 总交易次数 `122`
- `ai_top12_entry_filter`：
  - 期末权益 `134,840`
  - 相对基线 `+21,385`
  - 总收益 `-43.91%`
  - 最大回撤 `-51.50%`
  - Sharpe `-0.7271`
  - 总滑点 `11,430`
  - 总交易次数 `198`
- `simple_top8_entry_filter`：
  - 期末权益 `186,470`
  - 相对基线 `+73,015`
  - 总收益 `-22.44%`
  - 最大回撤 `-32.38%`
  - Sharpe `-0.2710`
  - 总滑点 `11,540`
  - 总交易次数 `236`

## 修改的回测结果

- 无

## 删除的回测结果

- 无

## 新增产物

- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_full_market_tradable_universe_audit_full_market_tradable_universe_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_full_market_tradable_universe_eligible_full_market_tradable_universe_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_full_market_tradable_universe_summary_full_market_tradable_universe_v1.json`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_full_market_tradable_universe_report_full_market_tradable_universe_v1.md`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_full_market_universe_formal_summary.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_full_market_universe_formal_summary.json`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_product_suitability_full_market_walkforward_summary_product_suitability_full_market_wf_v1.json`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_product_suitability_full_market_walkforward_report_product_suitability_full_market_wf_v1.md`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_product_pool_full_market_shadow_portfolio_summary_ai_product_pool_full_market_shadow_v1.json`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_ai_product_pool_full_market_shadow_portfolio_report_ai_product_pool_full_market_shadow_v1.md`

## 验证

- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/build_qmt_roll_full_market_tradable_universe.py`
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/main_contract_mapping.py examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py examples/portfolio_backtesting/run_qmt_roll_backtest.py`
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_full_market_universe_formal_backtest.py`
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_ai_product_suitability_full_market_walkforward.py`
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_ai_product_pool_full_market_shadow_portfolio.py`
- 已完成运行：
  - `.py311/bin/python examples/portfolio_backtesting/build_qmt_roll_full_market_tradable_universe.py`
  - `.py311/bin/python examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_full_market_universe_formal_backtest.py`
  - `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_ai_product_suitability_full_market_walkforward.py`
  - `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_ai_product_pool_full_market_shadow_portfolio.py`

## 我的判断

- 这次结果不是“全市场扩池突破”，而是一次重要否决：
  - 全市场50品种直接放开严重破坏原趋势系统
  - AI在全市场横截面中确实有弱排序信号
  - 但AI Top8/Top12 shadow仍为亏损，不能进入正式可交易版本
- 当前不能把全市场候选池替换原18品种池
- 第68至第71阶段的18品种AI Top8仍是当前正式第一候选
- 全市场分支的价值是暴露了一个本质问题：
  - 趋势系统并不是“品种越多越好”
  - 全市场里大量品种的噪声、流动性结构、合约乘数和趋势地形会吞噬系统优势
  - AI可以减少坏暴露，但现阶段还不能把坏扩池变成正收益
- 下一步如果继续做全市场，不应再扩大回测，而应先做“毒性品种归因”和“两阶段品种预过滤”：
  - 先用长期流动性、趋势效率、合约可承载性剔除明显不适合趋势系统的品种
  - 再让AI在更干净的候选池里排序
  - 不能直接从86或50品种里追求TopN优化

## 第73阶段：全市场毒性归因与结构预过滤验证

- 改动时间：`2026-04-24 22:10`
- 本次目标：
  - 继续第72阶段的全市场扩池否决结论
  - 先做产品毒性归因，再做两阶段结构预过滤
  - 验证“结构过滤后再让AI排序”是否能进入正式候选

## 本次版本改动内容

- 新增产品毒性归因脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_full_market_product_toxicity.py`
- 新增结构预过滤品种池构建脚本：
  - `examples/portfolio_backtesting/build_qmt_roll_full_market_structural_prefilter_universe.py`
- 新增结构预过滤正式回测脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_structural_prefilter_formal_backtest.py`
- 没有修改原18品种正式策略默认参数
- 没有把结构预过滤版本设为正式候选

## 新增参数

- `min_new_recent_median_volume = 50,000`
- `max_new_margin_per_contract = 45,000`
- `min_new_trend_efficiency_60d = 0.09`
- `min_new_realized_vol_60d = 0.10`
- `min_new_range_pct_60d = 0.018`
- `ai_top_n = 8`
- 新增结构预过滤动态品种池：
  - `qmt_roll_full_market_structural_prefilter_eligible_full_market_structural_prefilter_v1.csv`
- 新增结构池内AI资格文件：
  - `qmt_roll_full_market_structural_prefilter_ai_eligibility_full_market_structural_prefilter_v1.csv`

## 修改的参数

- 全市场研究分支的候选池从第72阶段的 `50` 个可交易品种压缩为 `23` 个结构预过滤品种
- 新增品种从 `32` 个压缩为 `5` 个：
  - `UR.CZCE`
  - `eb.DCE`
  - `pg.DCE`
  - `fu.SHFE`
  - `sn.SHFE`
- 结构池内AI排序从全市场50品种Top8改为结构池23品种Top8

## 删除的参数

- 无

## 毒性归因结果

- 全市场50品种中：
  - 原18品种全周期净利润合计：`+168,270`
  - 新增32品种全周期净利润合计：`-254,815`
  - 原18品种评估期净利润合计：`+24,675`
  - 新增32品种评估期净利润合计：`-151,630`
- 高毒性产品数：`15`
- 典型高毒性新增品种：
  - `nr.INE`：全周期净利润 `-115,850`
  - `zn.SHFE`：全周期净利润 `-83,450`
  - `SF.CZCE`：全周期净利润 `-37,520`
  - `ss.SHFE`：全周期净利润 `-30,775`
  - `a.DCE`：全周期净利润 `-26,330`
- 判断：
  - 全市场失败不是随机波动，而是新增品种整体结构与当前趋势系统不匹配
  - 历史PnL只用于归因，不能直接作为选品规则

## 结构预过滤池

- 输入：第72阶段全市场可交易候选 `50` 品种
- 输出：结构预过滤 `23` 品种
- 保留原18品种：`18`
- 新增放行品种：`5`
- 新增放行逻辑：
  - 流动性足够
  - 单合约保证金可承载
  - 60日趋势效率足够
  - 60日波动和振幅足够
  - 不使用历史收益排名作为入池条件

## 新增回测结果

### `structural_prefilter_all`

- 回测脚本：
  - `.py311/bin/python examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_structural_prefilter_formal_backtest.py`
- 回测参数：
  - 基础策略：`volref30_corr20_06_08_floor35`
  - 初始资金：`200,000`
  - 品种池：结构预过滤23品种
  - 不启用AI品种池过滤
- 结果：
  - 期末权益 `2,239,105`
  - 总收益 `1019.55%`
  - 最大回撤 `-45.49%`
  - Sharpe `0.7029`
  - 总滑点 `316,180`
  - 总交易次数 `1436`
  - 盈利日 `711`
  - 亏损日 `704`
- 新增5品种在本路径中的产品归因：
  - `fu.SHFE`：净利润 `+258,560`
  - `sn.SHFE`：净利润 `+46,980`
  - `eb.DCE`：净利润 `-4,550`
  - `pg.DCE`：净利润 `-62,640`
  - `UR.CZCE`：净利润 `-214,240`

### `structural_prefilter_ai_top8`

- 回测参数：
  - 品种池：结构预过滤23品种
  - 启用AI结构池Top8：
    - `enable_ai_product_pool_filter = True`
    - `ai_product_pool_strategy = ai_structural_top8_entry_filter`
- 结果：
  - 期末权益 `524,380`
  - 总收益 `162.19%`
  - 最大回撤 `-70.43%`
  - Sharpe `0.3060`
  - 总滑点 `118,530`
  - 总交易次数 `786`
  - 盈利日 `572`
  - 亏损日 `581`

### `structural_prefilter_simple_top8`

- 回测参数：
  - 品种池：结构预过滤23品种
  - 启用简单结构池Top8：
    - `enable_ai_product_pool_filter = True`
    - `ai_product_pool_strategy = simple_structural_top8_entry_filter`
- 结果：
  - 期末权益 `552,165`
  - 总收益 `176.08%`
  - 最大回撤 `-48.39%`
  - Sharpe `0.3194`
  - 总滑点 `154,200`
  - 总交易次数 `814`
  - 盈利日 `565`
  - 亏损日 `610`

## 对比结论

- 相比第72阶段全市场50品种基线：
  - 结构预过滤23品种显著修复：期末权益从 `113,455` 提升到 `2,239,105`
  - 但仍低于第53阶段原18品种基线 `2,902,355`
  - 也远低于第68至71阶段原18品种AI Top8 `3,894,190`
- 结构池内AI Top8和简单Top8均显著弱于结构池全开：
  - AI Top8期末权益只有 `524,380`
  - 简单Top8期末权益只有 `552,165`
  - 说明当前AI排序在扩池后的可执行正式回测里不合格

## 修改的回测结果

- 无

## 删除的回测结果

- 无

## 新增产物

- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_full_market_product_toxicity_products_full_market_product_toxicity_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_full_market_product_toxicity_summary_full_market_product_toxicity_v1.json`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_full_market_product_toxicity_report_full_market_product_toxicity_v1.md`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_full_market_structural_prefilter_audit_full_market_structural_prefilter_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_full_market_structural_prefilter_eligible_full_market_structural_prefilter_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_full_market_structural_prefilter_ai_eligibility_full_market_structural_prefilter_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_full_market_structural_prefilter_summary_full_market_structural_prefilter_v1.json`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_full_market_structural_prefilter_report_full_market_structural_prefilter_v1.md`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_structural_prefilter_formal_summary.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_structural_prefilter_formal_summary.json`

## 验证

- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_full_market_product_toxicity.py examples/portfolio_backtesting/build_qmt_roll_full_market_structural_prefilter_universe.py examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_structural_prefilter_formal_backtest.py`
- 已完成运行：
  - `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_full_market_product_toxicity.py`
  - `.py311/bin/python examples/portfolio_backtesting/build_qmt_roll_full_market_structural_prefilter_universe.py`
  - `.py311/bin/python examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_structural_prefilter_formal_backtest.py`

## 我的判断

- 两阶段结构预过滤是有价值的：
  - 它证明全市场不是完全不能用，而是必须先做结构筛除
  - 从50品种直接扩池的灾难性结果，被23品种结构池显著修复
- 但这不是正式突破版本：
  - 结构池全开仍弱于原18品种基线
  - 结构池AI Top8和简单Top8均明显失败
  - 当前正式第一候选仍然是原18品种AI Top8
- 下一步不应继续调结构池TopN：
  - 应先做新增5品种的边际贡献归因
  - `fu.SHFE`贡献明显为正，`sn.SHFE`为正
  - `UR.CZCE`和`pg.DCE`在正式路径中是明显拖累
  - 需要做“新增品种逐一加入/剔除”的消融回测，确认是否存在少数可迁移新品种，而不是继续扩大池子

# 第74阶段：新增品种边际贡献消融回测

## 改动时间

- `2026-04-24 22:22`

## 本次版本改动内容

- 新增脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_new_product_ablation_backtest.py`
- 本阶段不是正式策略升级，而是对第73阶段结构预过滤放行的5个新品种做边际贡献消融：
  - 单独把 `UR.CZCE`、`eb.DCE`、`fu.SHFE`、`pg.DCE`、`sn.SHFE` 加入原18品种池
  - 再测试 `fu+sn`、`fu+sn+eb`
  - 最后测试结构池剔除明显拖累品种 `UR.CZCE` 和 `pg.DCE` 后的组合
- 消融判断原则：
  - 不因为单品种收益高就直接纳入正式版本
  - 必须同时看期末权益、最大回撤、Sharpe、滑点、交易次数和相对原18品种/原18 AI Top8的差距

## 新增参数

- 新增诊断实验配置：
  - `experiment_name`
  - `added_new_products`
  - `added_new_product_count`
- 新增诊断品种组合：
  - `static18_plus_UR = UR.CZCE`
  - `static18_plus_eb = eb.DCE`
  - `static18_plus_fu = fu.SHFE`
  - `static18_plus_pg = pg.DCE`
  - `static18_plus_sn = sn.SHFE`
  - `static18_plus_fu_sn = fu.SHFE,sn.SHFE`
  - `static18_plus_fu_sn_eb = fu.SHFE,sn.SHFE,eb.DCE`
  - `structural23_without_UR_pg = eb.DCE,fu.SHFE,sn.SHFE`

## 修改的参数

- 无
- 沿用第73阶段正式回测参数：
  - `enable_same_direction_correlation_gate = True`
  - `same_direction_correlation_gate_lookback = 20`
  - `same_direction_correlation_gate_start = 0.6`
  - `same_direction_correlation_gate_full = 0.8`
  - `same_direction_correlation_gate_weight_floor = 0.35`
  - `enable_selection_pairwise_v2 = True`
  - `enable_selection_pairwise_v2_volume_tilt = True`
  - `selection_pairwise_volume_tilt_long_strength = 0.15`
  - `selection_pairwise_volume_tilt_long_base_volume_reference = 30.0`
  - `selection_pairwise_volume_tilt_short_strength = 0.0`

## 删除的参数

- 无

## 新增回测结果

| 实验 | 新增品种 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `static18_plus_UR` | `UR.CZCE` | `2,405,330` | `1102.67%` | `-38.77%` | `0.8998` | `362,750` | `1214` |
| `static18_plus_eb` | `eb.DCE` | `1,224,325` | `512.16%` | `-50.31%` | `0.5350` | `311,890` | `1235` |
| `static18_plus_fu` | `fu.SHFE` | `3,520,720` | `1660.36%` | `-47.69%` | `0.8673` | `356,360` | `1213` |
| `static18_plus_pg` | `pg.DCE` | `1,410,305` | `605.15%` | `-47.29%` | `0.6026` | `299,780` | `1182` |
| `static18_plus_sn` | `sn.SHFE` | `2,188,680` | `994.34%` | `-41.39%` | `0.8381` | `342,910` | `1218` |
| `static18_plus_fu_sn` | `fu.SHFE,sn.SHFE` | `3,558,165` | `1679.08%` | `-48.10%` | `0.9005` | `354,460` | `1270` |
| `static18_plus_fu_sn_eb` | `fu.SHFE,sn.SHFE,eb.DCE` | `2,821,035` | `1310.52%` | `-41.65%` | `0.7892` | `315,950` | `1345` |
| `structural23_without_UR_pg` | `eb.DCE,fu.SHFE,sn.SHFE` | `2,821,035` | `1310.52%` | `-41.65%` | `0.7892` | `315,950` | `1345` |

## 对比基准

- 第53阶段原18品种基线：
  - 期末权益 `2,902,355`
  - 总收益 `1351.18%`
  - 最大回撤 `-36.99%`
  - Sharpe `1.0225`
  - 总滑点 `349,080`
  - 总交易次数 `1158`
- 第68至71阶段原18品种AI Top8正式第一候选：
  - 期末权益 `3,894,190`
  - 总收益 `1847.09%`
  - 最大回撤 `-36.99%`
  - Sharpe `1.2080`
  - 总滑点 `257,880`
  - 总交易次数 `720`
- 第73阶段结构预过滤23品种全开：
  - 期末权益 `2,239,105`
  - 总收益 `1019.55%`
  - 最大回撤 `-45.49%`
  - Sharpe `0.7029`
  - 总滑点 `316,180`
  - 总交易次数 `1436`

## 修改的回测结果

- 无

## 删除的回测结果

- 无

## 新增产物

- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_new_product_ablation_summary.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_new_product_ablation_summary.json`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_new_product_ablation_universes/`
- 每组实验对应的 `daily`、`daily_equity`、`trades`、`position_changes`、`entry_risk_diagnostics`、`entry_candidate_snapshots`、`trade_review`、`statistics`、`chart` 和 `professional_dashboard` 文件

## 验证

- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_new_product_ablation_backtest.py`
- 已完成运行：
  - `.py311/bin/python examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_new_product_ablation_backtest.py`

## 我的判断

- `fu.SHFE` 是这5个新品种里唯一有明确正向边际价值的品种：
  - 单独加入后期末权益 `3,520,720`，高于原18品种基线 `2,902,355`
  - 但最大回撤扩大到 `-47.69%`，Sharpe 降到 `0.8673`
  - 所以它是候选增量，不是正式替代版本
- `fu.SHFE + sn.SHFE` 收益略高于单独 `fu.SHFE`：
  - 期末权益 `3,558,165`
  - 但最大回撤扩大到 `-48.10%`
  - 收益增加不足以补偿回撤恶化，不能直接晋级
- `eb.DCE`、`pg.DCE`、`UR.CZCE` 不应直接纳入：
  - `eb.DCE` 单独加入期末权益只有 `1,224,325`，最大回撤 `-50.31%`
  - `pg.DCE` 单独加入期末权益只有 `1,410,305`
  - `UR.CZCE` 虽比结构池全开强，但仍低于原18品种基线
- 本阶段的价值不是找到正式新版本，而是把“全市场扩池”收敛成一个可验证方向：
  - 不再继续扩大品种池
  - 后续只围绕 `fu.SHFE` 做更严格的多周期、起始年份、成本敏感性和是否进入AI Top8体系的验证
  - 当前正式第一候选仍是原18品种AI Top8，不改变

# 第75阶段：`fu.SHFE` 卫星品种严测与AI信号后启用正式候选

## 改动时间

- `2026-04-24 22:52`

## 本次版本改动内容

- 新增脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest.py`
  - `examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_fu_satellite_post_signal_formal_backtest.py`
- 本阶段继续第74阶段结论，不再扩大全市场品种池，只围绕 `fu.SHFE` 做严测。
- 核心设计边界：
  - `static18_plus_fu`：原18品种静态加入 `fu.SHFE`
  - `ai_top8_plus_fu_satellite`：原18 AI Top8 + 固定放行 `fu.SHFE`，但2022年前也允许 `fu.SHFE`
  - `ai_top8_plus_fu_satellite_post_signal`：2022年前只允许原18品种，AI信号生效后再把 `fu.SHFE` 作为卫星品种放行
- 关键判断：
  - 静态加入 `fu.SHFE` 不合格
  - 从2020年就放行 `fu.SHFE` 不够干净
  - “AI信号后启用 `fu.SHFE` 卫星”符合数据可得性边界，不是收益排名拟合，是本阶段最干净的新候选

## 新增参数

- 新增常量：
  - `FU_PRODUCT = fu.SHFE`
  - `AI_SATELLITE_STRATEGY_NAME = ai_top8_plus_fu_satellite_entry_filter`
  - `AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME = ai_top8_plus_fu_satellite_post_signal_entry_filter`
  - `SLIPPAGE_MULTIPLIERS = 1.0,1.5,2.0,3.0,5.0`
- 新增诊断窗口：
  - `full_2020_2026`
  - `pre_ai_2020_2021`
  - `post_signal_2022_2026`
  - `early_ai_2022_2023`
  - `trend_rich_2024_2025`
  - `latest_2026`
- 新增衍生品种池：
  - `static18_plus_fu_universe`
- 新增衍生AI准入表：
  - `ai_top8_plus_fu_satellite_eligibility`
  - `ai_top8_plus_fu_satellite_post_signal_eligibility`
- `post_signal` 版本的边界规则：
  - `2019-12-31` 预置信号只放行原18品种
  - 从已有AI Top8月度信号开始，放行当月AI Top8 + `fu.SHFE`

## 修改的参数

- 无核心策略参数修改
- 沿用第68至第74阶段正式参数：
  - `enable_same_direction_correlation_gate = True`
  - `same_direction_correlation_gate_lookback = 20`
  - `same_direction_correlation_gate_start = 0.6`
  - `same_direction_correlation_gate_full = 0.8`
  - `same_direction_correlation_gate_weight_floor = 0.35`
  - `enable_selection_pairwise_v2 = True`
  - `enable_selection_pairwise_v2_volume_tilt = True`
  - `selection_pairwise_volume_tilt_long_strength = 0.15`
  - `selection_pairwise_volume_tilt_long_base_volume_reference = 30.0`
  - `selection_pairwise_volume_tilt_short_strength = 0.0`

## 删除的参数

- 无

## 新增回测结果

### 正式候选：`ai_top8_plus_fu_satellite_post_signal`

- 回测区间：`2020-01-01` 至 `2026-04-30`
- 期末权益：`4,644,365`
- 总收益：`2222.18%`
- 最大回撤：`-36.99%`
- Sharpe：`1.2926`
- 总滑点：`289,960`
- 总交易次数：`791`
- 盈利日：`592`
- 亏损日：`624`

### 对比第68至71阶段原18品种AI Top8

- 原18品种AI Top8：
  - 期末权益 `3,894,190`
  - 总收益 `1847.10%`
  - 最大回撤 `-36.99%`
  - Sharpe `1.2080`
  - 总滑点 `257,880`
  - 总交易次数 `720`
- `ai_top8_plus_fu_satellite_post_signal` 相对变化：
  - 期末权益增加 `750,175`
  - 总收益增加 `375.09` 个百分点
  - 最大回撤基本持平
  - Sharpe 增加 `0.0846`
  - 总滑点增加 `32,080`
  - 总交易次数增加 `71`

### 多周期结果

| 窗口 | 策略 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `full_2020_2026` | `ai_top8_plus_fu_satellite_post_signal` | `4,644,365` | `2222.18%` | `-36.99%` | `1.2926` | `289,960` | `791` |
| `pre_ai_2020_2021` | `ai_top8_plus_fu_satellite_post_signal` | `1,384,905` | `592.45%` | `-36.99%` | `1.6313` | `57,190` | `306` |
| `post_signal_2022_2026` | `ai_top8_plus_fu_satellite_post_signal` | `2,906,700` | `1353.35%` | `-37.54%` | `1.3176` | `196,970` | `443` |
| `early_ai_2022_2023` | `ai_top8_plus_fu_satellite_post_signal` | `722,360` | `261.18%` | `-37.54%` | `1.3062` | `37,895` | `185` |
| `trend_rich_2024_2025` | `ai_top8_plus_fu_satellite_post_signal` | `1,144,445` | `472.22%` | `-32.50%` | `1.3679` | `72,635` | `211` |
| `latest_2026` | `ai_top8_plus_fu_satellite_post_signal` | `164,405` | `-17.80%` | `-40.06%` | `-0.5618` | `6,020` | `35` |

### 与原18 AI Top8分段对比

- `pre_ai_2020_2021`：
  - 与原18 AI Top8完全一致，说明2022年前没有引入 `fu.SHFE` 的错误暴露
- `post_signal_2022_2026`：
  - 新候选期末权益 `2,906,700`
  - 原18 AI Top8期末权益 `2,048,580`
  - 新候选最大回撤 `-37.54%`
  - 原18 AI Top8最大回撤 `-50.58%`
  - 新候选Sharpe `1.3176`
  - 原18 AI Top8 Sharpe `1.0486`
- `latest_2026`：
  - 新候选期末权益 `164,405`
  - 原18 AI Top8期末权益 `192,765`
  - 新候选最大回撤 `-40.06%`
  - 原18 AI Top8最大回撤 `-16.17%`
  - 这是当前新候选的主要瑕疵

### 失败路径：`static18_plus_fu`

- 全周期：
  - 期末权益 `3,520,720`
  - 总收益 `1660.36%`
  - 最大回撤 `-47.69%`
  - Sharpe `0.8673`
  - 总滑点 `356,360`
  - 总交易次数 `1213`
- `post_signal_2022_2026`：
  - 期末权益 `2,067,885`
  - 最大回撤 `-65.06%`
  - Sharpe `0.7428`
- 起始年份敏感性：
  - `since_2021` 最大回撤 `-53.98%`
  - `since_2022` 最大回撤 `-66.47%`
  - `since_2026` 出现资金小于等于0，vn.py无法计算统计指标，输出为0；这是爆仓/资金归零风险信号，不是正常0收益

### 正式候选滑点压力

| 滑点倍数 | 期末权益 | 总收益 | 最大回撤 | 总滑点 | 总交易次数 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `1.0x` | `4,644,365` | `2222.18%` | `-36.99%` | `289,960` | `791` |
| `1.5x` | `4,499,385` | `2149.69%` | `-37.72%` | `434,940` | `791` |
| `2.0x` | `4,354,405` | `2077.20%` | `-38.47%` | `579,920` | `791` |
| `3.0x` | `4,064,445` | `1932.22%` | `-40.25%` | `869,880` | `791` |
| `5.0x` | `3,484,525` | `1642.26%` | `-44.50%` | `1,449,800` | `791` |

## 修改的回测结果

- 无

## 删除的回测结果

- 无

## 新增产物

- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_static18_plus_fu_universe.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_ai_top8_plus_fu_satellite_eligibility.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_ai_top8_plus_fu_satellite_post_signal_eligibility.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_cycle_summary.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_start_year_summary.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_slippage_stress.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_combined_cycle_summary.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_summary.json`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_report.md`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_post_signal_formal_summary.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_post_signal_formal_summary.json`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_post_signal_formal_slippage_stress.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_post_signal_formal_daily.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_post_signal_formal_trades_2020_2026_04.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_post_signal_formal_professional_dashboard.html`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_post_signal_formal_trade_review.html`

## 验证

- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest.py examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_fu_satellite_post_signal_formal_backtest.py`
- 已完成运行：
  - `.py311/bin/python examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest.py`
  - `.py311/bin/python examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_fu_satellite_post_signal_formal_backtest.py`

## 我的判断

- 这是目前最有价值的一次突破：
  - 新候选首次在全周期期末权益、总收益、Sharpe上同时超过原18 AI Top8
  - 最大回撤没有恶化，仍保持在 `-36.99%`
  - 不是全市场扩池，而是“结构预过滤 + 单一卫星品种 + AI信号后启用”的窄口径扩展
- 但它还不是无条件实盘定版：
  - `latest_2026` 尾部弱于原18 AI Top8
  - 2026年新候选回撤 `-40.06%`，说明 `fu.SHFE` 卫星在最近尾部可能放大风险
  - 下一步不应继续找更多品种，而应做 `fu.SHFE` 卫星的尾部风险归因和可解释风控
- 当前研究第一候选可以从“原18品种AI Top8”升级为：
  - `ai_top8_plus_fu_satellite_post_signal`
- 当前实盘前置条件：
  - 必须再完成2026尾部亏损归因
  - 必须确认 `fu.SHFE` 的卫星放行不是由少数极端交易贡献
- 必须确认风控规则不是针对2026过拟合，而是可穿越周期的结构性约束

## 第76阶段：`fu.SHFE`卫星2026尾部归因与核心连续亏损状态隔离验证

### 改动时间

- `2026-04-24 23:11`

### 本次版本改动内容

- 新增`fu`卫星2026尾部归因脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_selection_long015_volref30_corr_fu_satellite_tail_2026_attribution.py`
- 新增策略参数：
  - `streak_risk_state_excluded_products`
- 修改`QmtRollPortfolioStrategy`连续亏损风控状态更新逻辑：
  - 默认行为不变
  - 当某品种在`streak_risk_state_excluded_products`中时，该品种平仓盈亏不更新组合级`loss_streak`
- 新增验证回测脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_fu_satellite_core_streak_backtest.py`
- 设计意图：
  - 先做归因，不直接按2026亏损拟合过滤规则
  - 验证“`fu.SHFE`卫星是否污染组合级连续亏损状态”，而不是简单禁用`fu.SHFE`

### 新增的参数

- `streak_risk_state_excluded_products`
  - 默认值：空字符串
  - 本次验证值：`fu.SHFE`
  - 含义：指定品种的平仓盈亏不参与组合级连续亏损风控状态更新

### 修改的参数

- 正式第一候选参数未修改
- 仅新增验证路径使用：
  - `streak_risk_state_excluded_products=fu.SHFE`

### 删除的参数

- 无

### 新增的归因结果

- `ai_top8_plus_fu_satellite_post_signal`在正式全周期路径中，`2026`段表现：
  - 卫星版本期初权益 `4,716,880`
  - 卫星版本期末权益 `4,644,365`
  - 卫星版本净损益 `-72,515`
  - 原18 AI Top8同期净损益 `-54,260`
  - 卫星版本相比原18 AI Top8差额 `-18,255`
- `fu.SHFE`自身并不是2026尾部弱化主因：
  - `fu.SHFE`净损益 `+77,280`
  - `fu.SHFE`交易次数 `2`
  - `fu.SHFE`总滑点 `1,120`
  - `fu.SHFE`最差日 `2026-02-02`，净损益 `-79,520`
- 最大负差额来自`SH.CZCE`：
  - 卫星版本`SH.CZCE`净损益 `-209,550`
  - 原18 AI Top8`SH.CZCE`净损益 `-87,330`
  - 差额 `-122,220`
  - 两个版本`SH.CZCE`入场次数同为 `4`
  - 卫星版本`SH.CZCE`入场手数和 `77`
  - 原18 AI Top8`SH.CZCE`入场手数和 `22`
- 事件级诊断：
  - `2026-02-06`，`SH.CZCE`空头，卫星版风险乘数 `1.00`，原18 AI Top8风险乘数 `0.10`
  - `2026-03-02`，`SH.CZCE`空头，卫星版风险乘数 `1.00`，原18 AI Top8风险乘数 `0.10`
  - 本质原因是：`fu.SHFE`卫星盈利改变了组合级`loss_streak`路径，使原本应被连续亏损风控降档的核心品种没有降档

### 新增的回测结果

验证路径：`ai_top8_plus_fu_satellite_post_signal_core_streak`

| 周期 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `full_2020_2026` | `4,260,025` | `2030.01%` | `-36.99%` | `1.2083` | `275,900` | `787` |
| `pre_ai_2020_2021` | `1,384,905` | `592.45%` | `-36.99%` | `1.6313` | `57,190` | `306` |
| `post_signal_2022_2026` | `2,360,725` | `1080.36%` | `-58.14%` | `0.9817` | `155,550` | `437` |
| `early_ai_2022_2023` | `504,620` | `152.31%` | `-58.14%` | `0.7882` | `31,710` | `189` |
| `trend_rich_2024_2025` | `1,075,435` | `437.72%` | `-33.72%` | `1.4288` | `50,665` | `179` |
| `latest_2026` | `188,915` | `-5.54%` | `-32.37%` | `-0.3387` | `2,340` | `24` |

### 滑点压力结果

| 滑点倍数 | 期末权益 | 总收益 | 最大回撤 | 总滑点 | 总交易次数 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `1.0x` | `4,260,025` | `2030.01%` | `-36.99%` | `275,900` | `787` |
| `1.5x` | `4,122,075` | `1961.04%` | `-37.72%` | `413,850` | `787` |
| `2.0x` | `3,984,125` | `1892.06%` | `-38.47%` | `551,800` | `787` |
| `3.0x` | `3,708,225` | `1754.11%` | `-40.25%` | `827,700` | `787` |
| `5.0x` | `3,156,425` | `1478.21%` | `-44.50%` | `1,379,500` | `787` |

### 修改的回测结果

- 无

### 删除的回测结果

- 无

### 新增产物

- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_tail_2026_attribution_product_attribution_fu_satellite_tail_2026_attribution_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_tail_2026_attribution_monthly_attribution_fu_satellite_tail_2026_attribution_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_tail_2026_attribution_worst_days_fu_satellite_tail_2026_attribution_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_tail_2026_attribution_entry_comparison_vs_ai_top8_fu_satellite_tail_2026_attribution_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_tail_2026_attribution_opened_entry_event_comparison_vs_ai_top8_fu_satellite_tail_2026_attribution_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_tail_2026_attribution_summary_fu_satellite_tail_2026_attribution_v1.json`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_tail_2026_attribution_report_fu_satellite_tail_2026_attribution_v1.md`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_core_streak_cycle_summary.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_core_streak_slippage_stress.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_core_streak_summary.json`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_core_streak_report.md`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_core_streak_formal_daily.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_core_streak_formal_trades_2020_2026_04.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_core_streak_formal_position_changes_2020_2026_04.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_core_streak_formal_entry_risk_diagnostics_2020_2026_04.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_core_streak_formal_entry_candidate_snapshots_2020_2026_04.csv`

### 验证

- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_fu_satellite_core_streak_backtest.py`
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_selection_long015_volref30_corr_fu_satellite_tail_2026_attribution.py`
- 已完成运行：
  - `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_selection_long015_volref30_corr_fu_satellite_tail_2026_attribution.py`
  - `.py311/bin/python examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_fu_satellite_core_streak_backtest.py`

### 我的判断

- `fu.SHFE`卫星本身不是2026尾部弱化主因，主因是卫星品种改变了组合级连续亏损风控状态，使核心品种`SH.CZCE`在错误时点放大仓位。
- `streak_risk_state_excluded_products=fu.SHFE`验证了因果链：`latest_2026`从第75阶段的`164,405`改善到`188,915`。
- 但该隔离规则不能升级正式版本：
  - 全周期期末权益从第75阶段`4,644,365`降至`4,260,025`
  - Sharpe从第75阶段`1.2926`降至`1.2083`
  - `post_signal_2022_2026`最大回撤恶化到`-58.14%`
  - `early_ai_2022_2023`质量明显下降
- 当前研究第一候选仍是第75阶段：
  - `ai_top8_plus_fu_satellite_post_signal`
- 下一步不应直接隔离`fu.SHFE`，也不应禁用`fu.SHFE`；更合理的方向是研究可穿越周期的“组合状态治理”，让卫星品种不能轻易重置核心池风险状态，但也不能机械地把卫星盈亏完全排除。

## 2026-04-24 23:21 第77阶段：连续亏损状态渐进恢复验证（不升级）

### 改动内容

- 本阶段目标：验证“盈利不一次性清零连续亏损状态，而是逐级恢复”是否能解决第75阶段`fu.SHFE`卫星污染组合级风控状态的问题。
- 修改策略文件：
  - `examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
- 新增回测脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_fu_satellite_gradual_streak_backtest.py`

### 新增的参数

- `streak_profit_recovery_mode`
  - 默认值：`reset`
  - 验证值：`decrement`
  - 含义：盈利平仓后不把`loss_streak`直接清零，而是每次盈利只降低一级连续亏损状态。

### 修改的参数

- 本次验证路径在第75阶段`ai_top8_plus_fu_satellite_post_signal`基础上覆盖：
  - `streak_profit_recovery_mode=decrement`
- 其余核心参数延续第75阶段，不主动调参拟合。

### 删除的参数

- 无

### 新增的回测结果

验证路径：`ai_top8_plus_fu_satellite_gradual_streak`

| 周期 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `full_2020_2026` | `292,975` | `46.49%` | `-20.25%` | `0.3863` | `13,150` | `285` |
| `pre_ai_2020_2021` | `190,310` | `-4.85%` | `-16.69%` | `-0.2159` | `3,970` | `101` |
| `post_signal_2022_2026` | `450,515` | `125.26%` | `-19.77%` | `0.8206` | `20,850` | `288` |
| `early_ai_2022_2023` | `319,920` | `59.96%` | `-19.77%` | `0.9530` | `3,945` | `112` |
| `trend_rich_2024_2025` | `241,120` | `20.56%` | `-16.64%` | `0.4553` | `6,790` | `96` |
| `latest_2026` | `193,575` | `-3.21%` | `-6.48%` | `-0.9584` | `530` | `18` |

### 修改的回测结果

- 无

### 删除的回测结果

- 无

### 新增产物

- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_gradual_streak_cycle_summary.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_gradual_streak_summary.json`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_gradual_streak_report.md`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_gradual_streak_formal_daily.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_gradual_streak_formal_trades_2020_2026_04.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_gradual_streak_formal_position_changes_2020_2026_04.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_gradual_streak_formal_entry_risk_diagnostics_2020_2026_04.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_gradual_streak_formal_entry_candidate_snapshots_2020_2026_04.csv`

### 验证

- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_fu_satellite_gradual_streak_backtest.py`
- 已完成运行：
  - `.py311/bin/python examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_fu_satellite_gradual_streak_backtest.py`

### 我的判断

- 该版本不能升级正式候选。
- 正面信息：`latest_2026`最大回撤从第75阶段的`-40.06%`压到`-6.48%`，说明“风险状态被过快恢复”确实是尾部问题的一部分。
- 负面代价过大：全周期期末权益从第75阶段`4,644,365`降至`292,975`，Sharpe从`1.2926`降至`0.3863`，总交易次数从`791`降至`285`。
- 本质问题：`decrement`让`loss_streak`过度黏滞，使趋势系统长期处于低风险状态，虽然少亏了尾部，但也错过了主趋势段；这不是可穿越周期的改进。
- 当前研究第一候选仍是第75阶段：
  - `ai_top8_plus_fu_satellite_post_signal`
- 后续方向应从“什么时候允许恢复风险”入手，例如要求恢复发生在组合权益、核心池贡献和波动环境同时改善之后，而不是简单慢恢复或机械隔离卫星品种。

## 2026-04-24 23:40 第78阶段：卫星盈利屏蔽连续亏损恢复（升级为风险治理第一候选）

### 改动内容

- 本阶段目标：继续处理第75阶段`fu.SHFE`卫星污染组合级连续亏损状态的问题，但避免第77阶段“全局慢恢复/确认恢复”过度压制趋势收益。
- 修改策略文件：
  - `examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
- 新增验证脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_fu_satellite_confirmed_streak_backtest.py`
  - `examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_streak_backtest.py`
  - `examples/portfolio_backtesting/analyze_qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_stress.py`

### 新增的参数

- `streak_profit_recovery_confirm_wins`
  - 默认值：`1`
  - 用途：在`streak_profit_recovery_mode=confirm`时，要求连续盈利平仓达到指定次数后才清零`loss_streak`
- `streak_risk_state_exclusion_mode`
  - 默认值：`all`
  - 可选验证值：`profit_only`
  - 用途：对`streak_risk_state_excluded_products`指定品种进行非对称处理；`profit_only`表示该品种盈利不恢复`loss_streak`，但亏损仍增加`loss_streak`

### 修改的参数

- 验证一：全局确认恢复
  - `streak_profit_recovery_mode=confirm`
  - `streak_profit_recovery_confirm_wins=2`
- 验证二：`fu.SHFE`卫星盈利屏蔽
  - `streak_risk_state_excluded_products=fu.SHFE`
  - `streak_risk_state_exclusion_mode=profit_only`
- 其他核心参数延续第75阶段`ai_top8_plus_fu_satellite_post_signal`，不进行收益拟合。

### 删除的参数

- 无

### 新增的回测结果

验证路径一：`ai_top8_plus_fu_satellite_post_signal_confirmed_streak`

| 周期 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `full_2020_2026` | `629,305` | `214.65%` | `-38.27%` | `0.5478` | `38,080` | `380` |
| `pre_ai_2020_2021` | `142,330` | `-28.84%` | `-38.27%` | `-0.6546` | `7,310` | `147` |
| `post_signal_2022_2026` | `1,368,780` | `584.39%` | `-36.74%` | `1.0118` | `92,830` | `394` |
| `early_ai_2022_2023` | `421,780` | `110.89%` | `-36.74%` | `0.8966` | `20,635` | `169` |
| `trend_rich_2024_2025` | `611,425` | `205.71%` | `-35.59%` | `1.2344` | `25,950` | `150` |
| `latest_2026` | `227,705` | `13.85%` | `-18.41%` | `0.6553` | `2,180` | `24` |

验证路径二：`ai_top8_plus_fu_satellite_post_signal_profit_shield_streak`

| 周期 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `full_2020_2026` | `4,600,090` | `2200.05%` | `-36.99%` | `1.2919` | `260,110` | `779` |
| `pre_ai_2020_2021` | `1,384,905` | `592.45%` | `-36.99%` | `1.6313` | `57,190` | `306` |
| `post_signal_2022_2026` | `2,863,385` | `1331.69%` | `-37.54%` | `1.3008` | `167,710` | `431` |
| `early_ai_2022_2023` | `721,720` | `260.86%` | `-37.54%` | `1.3070` | `36,710` | `185` |
| `trend_rich_2024_2025` | `964,180` | `382.09%` | `-31.12%` | `1.4577` | `42,120` | `164` |
| `latest_2026` | `188,645` | `-5.68%` | `-32.41%` | `-0.3449` | `2,360` | `24` |

### 滑点压力结果

| 版本 | 滑点倍数 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 第75阶段 | `1.0x` | `4,644,365` | `2222.18%` | `-36.99%` | `1.4565` | `289,960` | `791` |
| 第75阶段 | `3.0x` | `4,064,445` | `1932.22%` | `-40.25%` | `1.3152` | `869,880` | `791` |
| 第75阶段 | `5.0x` | `3,484,525` | `1642.26%` | `-44.50%` | `1.1792` | `1,449,800` | `791` |
| 盈利屏蔽版 | `1.0x` | `4,600,090` | `2200.05%` | `-36.99%` | `1.4551` | `260,110` | `779` |
| 盈利屏蔽版 | `3.0x` | `4,079,870` | `1939.94%` | `-40.25%` | `1.3191` | `780,330` | `779` |
| 盈利屏蔽版 | `5.0x` | `3,559,650` | `1679.83%` | `-44.50%` | `1.1887` | `1,300,550` | `779` |

### 修改的回测结果

- 无

### 删除的回测结果

- 无

### 新增产物

- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_confirmed_streak_cycle_summary.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_confirmed_streak_summary.json`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_confirmed_streak_report.md`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_confirmed_streak_formal_daily.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_confirmed_streak_formal_trades_2020_2026_04.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_confirmed_streak_formal_position_changes_2020_2026_04.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_confirmed_streak_formal_entry_risk_diagnostics_2020_2026_04.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_confirmed_streak_formal_entry_candidate_snapshots_2020_2026_04.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_streak_cycle_summary.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_streak_summary.json`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_streak_report.md`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_streak_formal_daily.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_streak_formal_trades_2020_2026_04.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_streak_formal_position_changes_2020_2026_04.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_streak_formal_entry_risk_diagnostics_2020_2026_04.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_streak_formal_entry_candidate_snapshots_2020_2026_04.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_stress.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_stress_report.md`

### 验证

- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_fu_satellite_confirmed_streak_backtest.py`
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_streak_backtest.py examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_fu_satellite_confirmed_streak_backtest.py`
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_stress.py`
- 已完成运行：
  - `.py311/bin/python examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_fu_satellite_confirmed_streak_backtest.py`
  - `.py311/bin/python examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_streak_backtest.py`
  - `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_stress.py`

### 我的判断

- `streak_profit_recovery_mode=confirm`不升级：它把2026尾部变好，但全周期收益从第75阶段`4,644,365`压到`629,305`，说明全局确认恢复仍然过度保守。
- `streak_risk_state_exclusion_mode=profit_only`是本阶段有效突破：
  - 全周期期末权益仅比第75阶段少`44,275`
  - Sharpe基本持平：第75阶段`1.2926`，盈利屏蔽版`1.2919`
  - `latest_2026`期末权益从第75阶段`164,405`改善到`188,645`
  - `latest_2026`最大回撤从第75阶段`-40.06%`改善到`-32.41%`
  - 总滑点从第75阶段`289,960`降到`260,110`
  - 3倍和5倍滑点压力下，盈利屏蔽版反而超过第75阶段
- 本质判断：趋势系统不能让卫星品种的一笔盈利替核心池“洗白”连续亏损状态；但卫星品种亏损仍是组合风险信息，应该计入降风险。这种非对称规则比完全隔离和全局慢恢复更接近交易系统的真实风险结构。
- 当前研究状态调整：
  - 第75阶段`ai_top8_plus_fu_satellite_post_signal`保留为收益上限基准
  - 第78阶段`ai_top8_plus_fu_satellite_post_signal_profit_shield_streak`升级为风险治理第一候选
- 仍不能实盘定版：下一步应做起始年份、极端交易、2026事件级归因和执行成本复核，确认该规则不是偶然改善2026。

## 2026-04-24 23:56 第79阶段：第78阶段风险治理反证验证

### 改动内容

- 本阶段不新增策略逻辑，专门验证第78阶段`profit_shield_streak`是否只是偶然改善全周期和2026尾部。
- 新增起始年份稳健性脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_start_year_robustness.py`
- 新增2026事件归因脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_tail_2026_attribution.py`
- 修正归因报告措辞：全周期口径下第78阶段2026期初权益低于第75阶段，因此归因报告明确优先比较2026区间净损益，而不是绝对期末权益。

### 新增的参数

- 无

### 修改的参数

- 无策略参数修改。
- 起始年份稳健性验证沿用第75阶段和第78阶段参数，只改变回测起始年份：
  - `since_2020`
  - `since_2021`
  - `since_2022`
  - `since_2023`
  - `since_2024`
  - `since_2025`
  - `since_2026`
- 第78阶段验证参数仍为：
  - `streak_risk_state_excluded_products=fu.SHFE`
  - `streak_risk_state_exclusion_mode=profit_only`
- 事件归因参数：
  - `TAIL_START=2026-01-01`
  - `KEY_PRODUCT=SH.CZCE`
  - 关键日期：`2026-02-06`、`2026-03-02`

### 删除的参数

- 无

### 新增的回测结果

起始年份稳健性：第78阶段`profit_shield_streak` vs 第75阶段`post_signal`

| 起始窗口 | 第78阶段期末权益 | 第75阶段期末权益 | 权益差额 | 第78阶段最大回撤 | 第75阶段最大回撤 | 第78阶段Sharpe | 第75阶段Sharpe | 滑点差额 | 交易次数差额 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `since_2020` | `4,600,090` | `4,644,365` | `-44,275` | `-36.99%` | `-36.99%` | `1.2919` | `1.2926` | `-29,850` | `-12` |
| `since_2021` | `4,125,980` | `4,170,255` | `-44,275` | `-42.32%` | `-42.32%` | `1.1929` | `1.1948` | `-29,850` | `-12` |
| `since_2022` | `3,016,845` | `3,074,745` | `-57,900` | `-36.77%` | `-36.77%` | `1.2448` | `1.2603` | `-29,620` | `-12` |
| `since_2023` | `1,918,185` | `2,198,170` | `-279,985` | `-39.44%` | `-35.99%` | `1.3242` | `1.4015` | `-44,870` | `-30` |
| `since_2024` | `993,155` | `1,071,930` | `-78,775` | `-31.12%` | `-32.50%` | `1.2924` | `1.1626` | `-35,535` | `-49` |
| `since_2025` | `882,655` | `811,485` | `71,170` | `-28.88%` | `-28.88%` | `1.6574` | `1.4266` | `-17,260` | `-6` |
| `since_2026` | `188,645` | `164,405` | `24,240` | `-32.41%` | `-40.06%` | `-0.3449` | `-0.5618` | `-3,660` | `-11` |

稳健性汇总：

- 起始年份窗口数：`7`
- 第78阶段期末权益胜出窗口：`2`
- 第78阶段Sharpe胜出窗口：`3`
- 平均期末权益差额：`-58,543`
- 平均Sharpe差额：`0.0689`
- 平均滑点差额：`-27,235`

2026全周期尾部归因：

| 版本 | 2026期初权益 | 2026期末权益 | 2026净损益 | 2026区间收益 | 2026最大回撤 | 2026总滑点 | 2026交易次数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 第75阶段 | `4,716,880` | `4,644,365` | `-72,515` | `-1.54%` | `-5.31%` | `14,380` | `37` |
| 第78阶段 | `4,571,885` | `4,600,090` | `28,205` | `0.62%` | `-5.36%` | `9,380` | `35` |
| 差额 | `-144,995` | `-44,275` | `100,720` | `2.15%` | `-0.05pct` | `-5,000` | `-2` |

关键品种归因：

- `SH.CZCE`第75阶段2026净损益：`-209,550`
- `SH.CZCE`第78阶段2026净损益：`-87,330`
- `SH.CZCE`净损益改善：`122,220`
- `SH.CZCE`绝对持仓变化差额：`-110`
- `2026-02-06`空头事件：第75阶段`31`手、风险乘数`1.0`；第78阶段`3`手、风险乘数`0.1`
- `2026-03-02`空头事件：第75阶段`31`手、风险乘数`1.0`；第78阶段`4`手、风险乘数`0.1`

### 修改的回测结果

- 无

### 删除的回测结果

- 无

### 新增产物

- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_start_year_robustness_summary.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_start_year_robustness_comparison.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_start_year_robustness_summary.json`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_start_year_robustness_report.md`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_tail_2026_attribution_product_comparison_profit_shield_tail_2026_attribution_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_tail_2026_attribution_entry_event_comparison_profit_shield_tail_2026_attribution_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_tail_2026_attribution_key_events_profit_shield_tail_2026_attribution_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_tail_2026_attribution_daily_comparison_profit_shield_tail_2026_attribution_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_tail_2026_attribution_summary_profit_shield_tail_2026_attribution_v1.json`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_tail_2026_attribution_report_profit_shield_tail_2026_attribution_v1.md`

### 验证

- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_start_year_robustness.py examples/portfolio_backtesting/analyze_qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_tail_2026_attribution.py`
- 已完成运行：
  - `.py311/bin/python examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_start_year_robustness.py`
  - `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_tail_2026_attribution.py`

### 我的判断

- 第78阶段不能直接替代第75阶段作为收益第一候选：7个起始年份窗口中，第78阶段只在`since_2025`和`since_2026`两个窗口期末权益胜出，平均期末权益仍低`58,543`。
- 第78阶段仍保留为风险治理第一候选：它在所有起始年份窗口都降低滑点和交易次数，2026独立窗口期末权益从`164,405`提高到`188,645`，最大回撤从`-40.06%`改善到`-32.41%`。
- 事件归因支持第78阶段的设计逻辑：2026尾部净损益改善`100,720`，主要来自`SH.CZCE`风险乘数被压到`0.1`后少放大了两笔错误空头；这不是随机产品盈亏抵消。
- 负面信息同样明确：`since_2023`窗口第78阶段权益少`279,985`且最大回撤更深`3.45`个百分点，说明该规则会牺牲一部分趋势再启动收益。
- 当前版本关系保持不变：
  - 第75阶段`ai_top8_plus_fu_satellite_post_signal`是收益上限基准
  - 第78阶段`ai_top8_plus_fu_satellite_post_signal_profit_shield_streak`是风险治理第一候选
- 下一步不应继续微调`fu.SHFE`单点规则；更有价值的是做统一的“组合风险状态归因层”，把卫星、核心、相关性拥挤和近期权益曲线统一到同一个可解释风控框架中。

## 2026-04-25 00:09 第80阶段：组合风险状态归因层第一版

### 改动内容

- 本阶段按第79阶段判断推进，但不直接修改策略交易规则，先建立“组合风险状态归因层”。
- 新增分析脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_selection_long015_volref30_corr_portfolio_risk_state_attribution.py`
- 该脚本读取第75阶段和第78阶段既有正式产物，将开仓事件与后续`5/10/20`个交易日产品级、组合级净损益连接，生成状态桶和风险恢复分歧表。
- 本阶段不是回测，不产生新的策略版本；目的是判断第78阶段风险治理逻辑是否具备跨周期抽象价值。

### 新增的参数

- 无策略参数。
- 分析脚本使用的诊断参数：
  - `HORIZONS=(5, 10, 20)`
  - `SATELLITE_PRODUCTS={fu.SHFE}`
  - 分段：`pre_ai_2020_2021`、`early_ai_2022_2023`、`trend_rich_2024_2025`、`latest_2026`

### 修改的参数

- 无

### 删除的参数

- 无

### 新增的回测结果

- 无。本阶段未运行新回测，只基于第75阶段和第78阶段已有正式回测产物做归因诊断。

### 新增的分析结果

开仓事件总体：

| 版本 | 开仓事件数 | 产品数 | 卫星事件数 | 平均风险乘数 | 平均loss_streak | 20日产品级前瞻净损益 | 20日产品级亏损率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 第75阶段`post_signal` | `365` | `19` | `32` | `0.8422` | `1.5151` | `5,593,770` | `54.52%` |
| 第78阶段`profit_shield` | `359` | `19` | `32` | `0.8019` | `1.7521` | `5,570,085` | `55.15%` |

风险恢复分歧事件：

| 指标 | 数值 |
| --- | ---: |
| 分歧事件数 | `21` |
| 涉及产品数 | `11` |
| 第75阶段手数 | `722` |
| 第78阶段手数 | `90` |
| 第75阶段额外手数 | `632` |
| 第75阶段20日产品级前瞻净损益 | `279,460` |
| 第78阶段20日产品级前瞻净损益 | `235,815` |
| 第78阶段相对差额 | `-43,645` |

分阶段分歧：

| 周期 | 分歧事件数 | 产品数 | 第75额外手数 | 第75阶段20日前瞻净损益 | 第78阶段20日前瞻净损益 | 第78阶段相对差额 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `early_ai_2022_2023` | `1` | `1` | `45` | `313,600` | `311,800` | `-1,800` |
| `trend_rich_2024_2025` | `16` | `11` | `515` | `155,250` | `385` | `-154,865` |
| `latest_2026` | `4` | `2` | `72` | `-189,390` | `-76,370` | `113,020` |

关键事件：

- 第78阶段保护最有效事件：
  - `2026-02-06 SH.CZCE short_case1a`：第75阶段`31`手，第78阶段`3`手，20日前瞻净损益改善`122,220`
  - `2026-03-02 SH.CZCE short_case1a`：第75阶段`31`手，第78阶段`4`手，20日前瞻净损益改善`56,700`
- 第78阶段代价最大事件：
  - `2024-07-22 jm.DCE short_case1a`：第75阶段`22`手，第78阶段`2`手，20日前瞻净损益差额`-194,400`
  - `2025-11-11 lc.GFEX long_case1a`：第75阶段`25`手，第78阶段`2`手，20日前瞻净损益差额`-100,280`

### 修改的回测结果

- 无

### 删除的回测结果

- 无

### 新增产物

- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_portfolio_risk_state_attribution_event_table_portfolio_risk_state_attribution_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_portfolio_risk_state_attribution_state_bucket_summary_portfolio_risk_state_attribution_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_portfolio_risk_state_attribution_stage75_vs_stage78_pair_comparison_portfolio_risk_state_attribution_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_portfolio_risk_state_attribution_risk_recovery_divergence_portfolio_risk_state_attribution_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_portfolio_risk_state_attribution_summary_portfolio_risk_state_attribution_v1.json`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_portfolio_risk_state_attribution_report_portfolio_risk_state_attribution_v1.md`

### 验证

- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_selection_long015_volref30_corr_portfolio_risk_state_attribution.py`
- 已完成运行：
  - `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_selection_long015_volref30_corr_portfolio_risk_state_attribution.py`

### 我的判断

- 第78阶段的`profit_shield`逻辑不能直接抽象成统一风控规则。它在`latest_2026`保护有效，20日前瞻净损益改善`113,020`；但在`trend_rich_2024_2025`明显压制趋势再启动，20日前瞻净损益损失`154,865`。
- 风险恢复分歧不是单一品种问题：21笔分歧涉及11个产品，说明继续写`fu.SHFE`专属补丁会过拟合。
- 当前更接近本质的方向不是“卫星盈利永不恢复风险”，而是“卫星盈利不能单独恢复风险，必须有核心池或组合权益状态确认”。
- 下一步如果要进入策略层，应先设计一个很克制的通用候选：
  - 不针对具体产品
  - 不针对具体年份
  - 只区分核心确认、卫星确认、组合权益确认
  - 参数数量尽量少
- 现阶段不建议立即升级第78阶段为正式版本；第75阶段继续作为收益上限基准，第78阶段继续作为风险治理候选。

## 2026-04-25 00:18 第81阶段：卫星盈利屏蔽的组合权益确认候选

### 改动内容

- 本阶段按第80阶段结论进入策略层，但只做一个低自由度候选，不做参数扫描。
- 在组合连亏风险恢复逻辑中新增“组合权益确认”钩子：卫星品种盈利默认不恢复风险，但当组合权益回撤已经回到指定阈值以内时，允许该盈利按正常逻辑恢复风险。
- 修改策略文件：
  - `examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
- 新增多周期回测脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_equity_confirm_backtest.py`
- 本阶段的核心目的不是追求更高收益，而是验证“卫星盈利不能单独恢复风险，但组合权益状态可以作为确认信号”是否能修复第78阶段在2024-2025趋势再启动中的机会成本。

### 新增的参数

- `streak_profit_recovery_equity_confirm_drawdown_pct`
  - 默认值：`-1.0`
  - 含义：小于`0`时关闭组合权益确认，保持原行为不变；大于等于`0`时，只有当`portfolio_drawdown_pct <= threshold`，被盈利屏蔽的卫星盈利才允许恢复组合风险状态。
  - 本次候选取值：`0.01`
  - 直觉解释：组合权益已回到距高水位`1%`以内，才承认卫星盈利可能代表组合状态恢复。

### 修改的参数

- 延续第78阶段风险治理候选：
  - `streak_risk_state_excluded_products=fu.SHFE`
  - `streak_risk_state_exclusion_mode=profit_only`
- 本次在第78阶段基础上新增：
  - `streak_profit_recovery_equity_confirm_drawdown_pct=0.01`

### 删除的参数

- 无

### 新增的回测结果

| 周期 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `full_2020_2026` | `4,600,090` | `2200.0450%` | `-36.9907%` | `1.2919` | `260,110` | `779` |
| `pre_ai_2020_2021` | `1,384,905` | `592.4525%` | `-36.9907%` | `1.6313` | `57,190` | `306` |
| `post_signal_2022_2026` | `2,863,385` | `1331.6925%` | `-37.5422%` | `1.3008` | `167,710` | `431` |
| `early_ai_2022_2023` | `721,720` | `260.8600%` | `-37.5422%` | `1.3070` | `36,710` | `185` |
| `trend_rich_2024_2025` | `964,180` | `382.0900%` | `-31.1166%` | `1.4577` | `42,120` | `164` |
| `latest_2026` | `188,645` | `-5.6775%` | `-32.4059%` | `-0.3449` | `2,360` | `24` |

全周期补充指标：

- 期末权益：`4,600,090`
- 总收益：`2200.0450%`
- 最大回撤：`-36.9907%`
- Sharpe：`1.2919`
- 总滑点：`260,110`
- 总交易次数：`779`
- 总净盈亏：`4,400,090`
- 盈利天数：`583`
- 亏损天数：`621`

对比结果：

| 对比对象 | 期末权益差额 | Sharpe差额 | 总滑点差额 | 总交易次数差额 |
| --- | ---: | ---: | ---: | ---: |
| 第75阶段收益基准 | `-44,275` | `-0.0007` | `-29,850` | `-12` |
| 第78阶段风险治理候选 | `0` | `0.0000` | `0` | `0` |

### 修改的回测结果

- 无

### 删除的回测结果

- 无

### 新增产物

- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_equity_confirm_cycle_summary.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_equity_confirm_summary.json`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_equity_confirm_report.md`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_equity_confirm_formal_daily.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_equity_confirm_formal_daily_equity.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_equity_confirm_formal_trades_2020_2026_04.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_equity_confirm_formal_position_changes_2020_2026_04.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_equity_confirm_formal_entry_risk_diagnostics_2020_2026_04.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_equity_confirm_formal_entry_candidate_snapshots_2020_2026_04.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_equity_confirm_formal_chart.html`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_equity_confirm_formal_professional_dashboard.html`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_equity_confirm_formal_trade_review.html`

### 验证

- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_equity_confirm_backtest.py`
- 已完成多周期回测：
  - `.py311/bin/python examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_equity_confirm_backtest.py`

### 我的判断

- 该候选不能升级。原因不是表现差，而是相对第78阶段完全没有产生交易层面的增量：期末权益、Sharpe、滑点、交易次数均一致。
- 这说明`1%`组合权益确认在当前路径上过于严格或触发位置不关键，不能修复第78阶段在`trend_rich_2024_2025`压制趋势再启动的问题。
- 这个负结果有价值：它排除了一个看似合理但实际惰性的确认条件，避免继续围绕权益阈值做过拟合式参数扫描。
- 当前版本关系不变：
  - 第75阶段`ai_top8_plus_fu_satellite_post_signal`仍是收益上限基准
  - 第78阶段`ai_top8_plus_fu_satellite_post_signal_profit_shield_streak`仍是风险治理第一候选
  - 第81阶段`profit_shield_equity_confirm`仅保留为已验证但不升级的候选
- 下一步不应扫描`0.02/0.05/0.10`这类阈值；更应回到本质：风险恢复需要来自核心池趋势确认、全组合风险贡献下降，或入场后前瞻表现结构，而不是单一权益高水位距离。

## 2026-04-25 00:26 第82阶段：风险恢复的核心池确认归因反证

### 改动内容

- 本阶段按第81阶段判断继续推进，但不修改交易规则、不新增回测。
- 新增只读归因脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_selection_long015_volref30_corr_risk_recovery_core_confirmation.py`
- 脚本读取第80阶段的风险恢复分歧事件，并对每笔事件补充事件发生前的核心池状态：
  - 核心池近`5/10/20`日净盈亏
  - 核心池近`20`日盈利广度
  - 非事件核心池近`20`日净盈亏
  - 事件品种近`20`日净盈亏
  - 组合近`5/10/20`日净盈亏和回撤变化
- 事件后的`20`日产品级净盈亏只作为标签和评分，不作为特征，避免未来函数。

### 新增的参数

- 无策略参数。
- 分析脚本使用的诊断窗口：
  - `LOOKBACKS=(5, 10, 20)`
- 诊断候选条件：
  - `core_prev10_pnl_positive`
  - `core_prev20_pnl_positive`
  - `core_prev20_breadth_half`
  - `core_prev20_pnl_and_breadth`
  - `core_prev20_and_portfolio_prev10`
  - `core_prev20_non_event_positive`

### 修改的参数

- 无

### 删除的参数

- 无

### 新增的回测结果

- 无。本阶段没有运行新回测，只做第75阶段与第78阶段既有正式产物的事件级归因分析。

### 新增的分析结果

总体：

| 指标 | 数值 |
| --- | ---: |
| 风险恢复分歧事件数 | `21` |
| 涉及产品数 | `11` |
| 事后看应该恢复风险的事件数 | `8` |
| 事后看继续屏蔽更好的事件数 | `13` |
| 始终恢复的20日产品级前瞻净损益 | `279,460` |
| 始终屏蔽的20日产品级前瞻净损益 | `235,815` |
| 屏蔽相对始终恢复差额 | `-43,645` |

核心池确认候选评分：

| 候选条件 | 恢复事件数 | 命中应该恢复事件数 | 错误恢复事件数 | 候选20日前瞻净损益 | 相对第78阶段差额 | 恢复命中率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `core_prev20_pnl_positive` | `3` | `2` | `1` | `195,840` | `-39,975` | `66.67%` |
| `core_prev20_and_portfolio_prev10` | `3` | `2` | `1` | `195,840` | `-39,975` | `66.67%` |
| `core_prev20_breadth_half` | `2` | `1` | `1` | `194,040` | `-41,775` | `50.00%` |
| `core_prev20_pnl_and_breadth` | `2` | `1` | `1` | `194,040` | `-41,775` | `50.00%` |
| `core_prev10_pnl_positive` | `4` | `2` | `2` | `191,340` | `-44,475` | `50.00%` |
| `core_prev20_non_event_positive` | `4` | `2` | `2` | `139,140` | `-96,675` | `50.00%` |

分阶段结构：

| 周期 | 标签 | 事件数 | 第75阶段20日前瞻净损益 | 第78阶段20日前瞻净损益 | 第78相对差额 | 第78阶段事件前核心池20日均值 | 第78阶段事件前核心池盈利广度 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `early_ai_2022_2023` | 应该恢复 | `1` | `313,600` | `311,800` | `-1,800` | `142,200` | `20.00%` |
| `trend_rich_2024_2025` | 应该恢复 | `5` | `422,970` | `28,185` | `-394,785` | `-13,818` | `10.00%` |
| `trend_rich_2024_2025` | 继续屏蔽更好 | `11` | `-267,720` | `-27,800` | `239,920` | `-20,411` | `7.58%` |
| `latest_2026` | 应该恢复 | `2` | `69,600` | `3,700` | `-65,900` | `-66,385` | `0.00%` |
| `latest_2026` | 继续屏蔽更好 | `2` | `-258,990` | `-80,070` | `178,920` | `-25,670` | `12.50%` |

关键观察：

- 所有“核心池确认”候选都不如第78阶段继续屏蔽，最优候选相对第78阶段仍少`39,975`。
- 2024-2025真正应该恢复的几笔大机会，事件发生前核心池20日净盈亏通常仍为负，说明“等核心池盈利转正再恢复”在趋势启动早期太慢。
- 2026的保护事件也不能被核心池盈利确认清晰区分：`latest_2026`中应该恢复与应该屏蔽的事件，核心池20日状态都偏弱。

### 修改的回测结果

- 无

### 删除的回测结果

- 无

### 新增产物

- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_risk_recovery_core_confirmation_event_table_risk_recovery_core_confirmation_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_risk_recovery_core_confirmation_candidate_summary_risk_recovery_core_confirmation_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_risk_recovery_core_confirmation_period_summary_risk_recovery_core_confirmation_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_risk_recovery_core_confirmation_summary_risk_recovery_core_confirmation_v1.json`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_risk_recovery_core_confirmation_report_risk_recovery_core_confirmation_v1.md`

### 验证

- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_selection_long015_volref30_corr_risk_recovery_core_confirmation.py`
- 已完成运行：
  - `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_selection_long015_volref30_corr_risk_recovery_core_confirmation.py`

### 我的判断

- “核心池近期盈利确认”这个方向暂时不能进入策略层。它符合直觉，但事件级证据不支持：确认信号出现太晚，错过了趋势早期的有效恢复。
- 第82阶段进一步说明，风险恢复问题不是简单的“核心池盈利了就恢复”，而是更接近“趋势信号出现时，当前风险压制是否正在阻止非拥挤、非高相关、低持仓的早期突破”。
- 下一步不应把核心池盈利确认写进策略，也不应继续扫盈利窗口；更值得研究的是“入场结构确认”：
  - 低相关/低拥挤
  - 当前无同向持仓挤压
  - 信号属于早期突破而不是亏损后的追随
  - 产品级趋势结构足够干净
- 当前版本关系不变：
  - 第75阶段仍是收益上限基准
  - 第78阶段仍是风险治理第一候选
  - 第81阶段权益确认候选拒绝升级
  - 第82阶段核心池确认只作为反证归因留档，不进入策略

## 2026-04-25 00:34 第83阶段：风险恢复的入场结构确认归因

### 改动内容

- 本阶段继续第82阶段反证后的方向，仍然不修改策略、不新增回测。
- 新增只读归因脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_selection_long015_volref30_corr_risk_recovery_entry_structure_confirmation.py`
- 脚本读取第82阶段事件表，比较以下结构候选：
  - 当前组合是否无持仓
  - 是否无同向相关拥挤
  - 是否`long_case1a/short_case1a`早期交叉
  - 是否排除`case2`中后段均线交叉
  - 是否方向专属
- 本阶段的目的：验证“入场结构确认”是否比第82阶段的“核心池历史盈利确认”更接近风险恢复问题的本质。

### 新增的参数

- 无策略参数。
- 分析候选：
  - `clean_book`
  - `clean_book_not_case2`
  - `early_cross_clean_book`
  - `early_cross_clean_book_top_rank`
  - `early_cross_clean_book_not_satellite`
  - `long_early_cross_clean_book`
  - `short_early_cross_clean_book`
  - `clean_book_low_drawdown`

### 修改的参数

- 无

### 删除的参数

- 无

### 新增的回测结果

- 无。本阶段没有运行新回测，只做第75阶段与第78阶段风险恢复分歧事件的结构归因。

### 新增的分析结果

总体基准：

| 基准 | 20日产品级前瞻净损益 |
| --- | ---: |
| 始终屏蔽，即第78阶段 | `235,815` |
| 始终恢复，即第75阶段 | `279,460` |

候选评分：

| 候选条件 | 恢复事件数 | 命中应该恢复事件数 | 错误恢复事件数 | 候选20日前瞻净损益 | 相对第78阶段差额 | 相对始终恢复差额 | 命中率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `early_cross_clean_book` | `7` | `4` | `3` | `470,995` | `235,180` | `191,535` | `57.14%` |
| `early_cross_clean_book_top_rank` | `7` | `4` | `3` | `470,995` | `235,180` | `191,535` | `57.14%` |
| `early_cross_clean_book_not_satellite` | `7` | `4` | `3` | `470,995` | `235,180` | `191,535` | `57.14%` |
| `clean_book_not_case2` | `9` | `5` | `4` | `459,745` | `223,930` | `180,285` | `55.56%` |
| `long_early_cross_clean_book` | `4` | `3` | `1` | `426,635` | `190,820` | `147,175` | `75.00%` |
| `clean_book` | `15` | `6` | `9` | `394,555` | `158,740` | `115,095` | `40.00%` |
| `short_early_cross_clean_book` | `3` | `1` | `2` | `280,175` | `44,360` | `715` | `33.33%` |
| `always_restore` | `21` | `8` | `13` | `279,460` | `43,645` | `0` | `38.10%` |
| `always_shield` | `0` | `0` | `0` | `235,815` | `0` | `-43,645` | `0.00%` |

最优结构候选`early_cross_clean_book`分阶段：

| 周期 | 恢复事件数 | 命中应该恢复事件数 | 错误恢复事件数 | 候选20日前瞻净损益 | 相对第78阶段差额 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `early_ai_2022_2023` | `0` | `0` | `0` | `311,800` | `0` |
| `trend_rich_2024_2025` | `5` | `3` | `2` | `317,085` | `316,700` |
| `latest_2026` | `2` | `1` | `1` | `-157,890` | `-81,520` |

### 修改的回测结果

- 无

### 删除的回测结果

- 无

### 新增产物

- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_risk_recovery_entry_structure_confirmation_event_table_risk_recovery_entry_structure_confirmation_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_risk_recovery_entry_structure_confirmation_candidate_summary_risk_recovery_entry_structure_confirmation_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_risk_recovery_entry_structure_confirmation_period_candidate_summary_risk_recovery_entry_structure_confirmation_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_risk_recovery_entry_structure_confirmation_summary_risk_recovery_entry_structure_confirmation_v1.json`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_risk_recovery_entry_structure_confirmation_report_risk_recovery_entry_structure_confirmation_v1.md`

### 验证

- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_selection_long015_volref30_corr_risk_recovery_entry_structure_confirmation.py`
- 已完成运行：
  - `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_selection_long015_volref30_corr_risk_recovery_entry_structure_confirmation.py`

### 我的判断

- 入场结构确认明显优于第82阶段的核心池历史盈利确认。`early_cross_clean_book`不是简单方向拟合，它同时包含多空`case1a`，并要求组合无持仓、无同向拥挤。
- 但该归因仍有明显风险：它在`trend_rich_2024_2025`贡献很大，在`latest_2026`反而损失`81,520`，说明它可能是“趋势丰富期恢复收益”的解释，而不是完整尾部保护规则。
- 方向专属的`long_early_cross_clean_book`命中率更高，但不能优先进入策略层，因为方向专属更容易变成多头年份拟合。
- 可以进入策略候选回测，但只能测试非方向专属的`early_cross_clean_book`，且必须用多周期反证，不能直接升级。

## 2026-04-25 00:38 第84阶段：入场结构恢复策略候选回测

### 改动内容

- 本阶段将第83阶段最优的非方向专属结构候选写入策略层，并运行多周期回测。
- 修改策略文件：
  - `examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
- 新增回测脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_recovery_backtest.py`
- 策略实现要点：
  - 默认关闭，不影响既有版本。
  - 不清空`loss_streak`。
  - 只在单笔入场计算风险预算时，临时把风险乘数恢复到至少`1.0`。
  - 条件为：`flat_entry`、信号属于`long_case1a/short_case1a`、当前组合无持仓、无同向相关拥挤。

### 新增的参数

- `enable_streak_entry_structure_risk_recovery`
  - 默认值：`False`
  - 本次候选：`True`
- `streak_entry_structure_recovery_signals`
  - 默认值：`long_case1a,short_case1a`
  - 本次候选：`long_case1a,short_case1a`
- `streak_entry_structure_recovery_min_multiplier`
  - 默认值：`1.0`
  - 本次候选：`1.0`
- `streak_entry_structure_recovery_require_flat_portfolio`
  - 默认值：`True`
  - 本次候选：`True`
- `streak_entry_structure_recovery_max_same_direction_corr`
  - 默认值：`0.30`
  - 本次候选：`0.30`

新增诊断字段：

- `streak_entry_structure_risk_recovery_enabled`
- `streak_entry_structure_risk_recovery_applied`
- `streak_entry_structure_risk_recovery_reason`
- `streak_entry_structure_risk_recovery_base_multiplier`
- `streak_entry_structure_risk_recovery_effective_multiplier`

### 修改的参数

- 延续第78阶段风险治理候选：
  - `streak_risk_state_excluded_products=fu.SHFE`
  - `streak_risk_state_exclusion_mode=profit_only`
- 在第78阶段基础上新增：
  - `enable_streak_entry_structure_risk_recovery=True`
  - `streak_entry_structure_recovery_signals=long_case1a,short_case1a`
  - `streak_entry_structure_recovery_min_multiplier=1.0`
  - `streak_entry_structure_recovery_require_flat_portfolio=True`
  - `streak_entry_structure_recovery_max_same_direction_corr=0.30`

### 删除的参数

- 无

### 新增的回测结果

| 周期 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `full_2020_2026` | `4,585,520` | `2192.7600%` | `-39.2924%` | `1.1193` | `289,290` | `771` |
| `pre_ai_2020_2021` | `1,045,295` | `422.6475%` | `-39.2924%` | `1.3391` | `56,570` | `304` |
| `post_signal_2022_2026` | `1,896,460` | `848.2300%` | `-45.4471%` | `0.9966` | `108,860` | `381` |
| `early_ai_2022_2023` | `250,040` | `25.0200%` | `-45.4471%` | `0.3446` | `15,070` | `145` |
| `trend_rich_2024_2025` | `1,696,160` | `748.0800%` | `-36.0518%` | `1.6452` | `75,515` | `199` |
| `latest_2026` | `203,985` | `1.9925%` | `-38.0446%` | `-0.0081` | `6,270` | `33` |

全周期补充指标：

- 期末权益：`4,585,520`
- 总收益：`2192.7600%`
- 最大回撤：`-39.2924%`
- Sharpe：`1.1193`
- 总滑点：`289,290`
- 总交易次数：`771`
- 总净盈亏：`4,385,520`
- 盈利天数：`589`
- 亏损天数：`615`

对比结果：

| 对比对象 | 期末权益差额 | Sharpe差额 | 最大回撤差额 | 总滑点差额 | 总交易次数差额 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 第75阶段收益基准 | `-58,845` | `-0.1733` | `-2.3017` | `-670` | `-20` |
| 第78阶段风险治理候选 | `-14,570` | `-0.1726` | `-2.3017` | `29,180` | `-8` |

入场结构恢复触发统计：

| 周期 | 触发事件数 | 触发手数 |
| --- | ---: | ---: |
| `pre_ai_2020_2021` | `5` | `148` |
| `early_ai_2022_2023` | `10` | `511` |
| `trend_rich_2024_2025` | `4` | `372` |
| `latest_2026` | `2` | `48` |

### 修改的回测结果

- 无

### 删除的回测结果

- 无

### 新增产物

- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_recovery_cycle_summary.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_recovery_summary.json`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_recovery_report.md`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_recovery_formal_daily.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_recovery_formal_daily_equity.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_recovery_formal_trades_2020_2026_04.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_recovery_formal_position_changes_2020_2026_04.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_recovery_formal_entry_risk_diagnostics_2020_2026_04.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_recovery_formal_entry_candidate_snapshots_2020_2026_04.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_recovery_formal_chart.html`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_recovery_formal_professional_dashboard.html`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_recovery_formal_trade_review.html`

### 验证

- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py examples/portfolio_backtesting/analyze_qmt_roll_selection_long015_volref30_corr_risk_recovery_entry_structure_confirmation.py examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_recovery_backtest.py`
- 已完成多周期回测：
  - `.py311/bin/python examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_recovery_backtest.py`

### 我的判断

- 第84阶段不能升级。它验证了第83阶段归因的危险：事件级结构信号能解释部分分歧，但写入策略后会在更宽的样本里放大错误交易。
- 优点很明确：`trend_rich_2024_2025`从第78阶段的`964,180`提高到`1,696,160`，说明入场结构恢复确实能抓回趋势期机会成本；`latest_2026`期末权益也从第78阶段的`188,645`提高到`203,985`。
- 但缺点更关键：全周期期末权益低于第75和第78阶段，Sharpe从第78阶段`1.2919`降到`1.1193`，最大回撤从`-36.9907%`恶化到`-39.2924%`；`early_ai_2022_2023`尤其差，期末权益只有`250,040`。
- 本质判断：`early_cross_clean_book`是一个有效的趋势期机会恢复信号，但不是独立的风险恢复规则。它需要再叠加“不要在弱品种/弱年份/弱结构里放大”的约束，否则会把早期启动和早期假突破一起放大。
- 当前版本关系不变：
  - 第75阶段仍是收益上限基准
  - 第78阶段仍是风险治理第一候选
  - 第83阶段结构归因保留为有效线索
  - 第84阶段策略候选拒绝升级
- 下一步不应继续调`early_cross_clean_book`阈值；更有价值的是对第84阶段触发事件做失败归因，区分“趋势期真启动”和“早期假突破”。

## 2026-04-25 01:02 第85阶段：第84触发事件失败归因

### 改动内容

- 本阶段不修改交易策略、不新增回测，只读取第84、第78、第75阶段正式产物，对第84阶段实际触发的入场结构恢复事件做失败归因。
- 新增分析脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_selection_long015_volref30_corr_entry_structure_recovery_trigger_attribution.py`
- 分析方法：
  - 只选取第84阶段中`streak_entry_structure_risk_recovery_applied=1`且实际开仓的事件。
  - 对同一事件匹配第78阶段和第75阶段的开仓手数、风险乘数。
  - 计算事件后`5/10/20/40/60/120`个交易日产品级和组合级净损益。
  - 评分标签使用第84阶段相对第78阶段的20日产品级净损益差额。
  - 候选条件只使用入场当下已有字段，避免未来函数。

### 新增的参数

- 无

### 修改的参数

- 无

### 删除的参数

- 无

### 新增的回测结果

- 无。本阶段只做归因分析，没有运行新回测。

### 新增的分析结果

总体触发样本：

| 指标 | 数值 |
| --- | ---: |
| 触发事件数 | `21` |
| 涉及产品数 | `13` |
| 第84优于第78事件数 | `10` |
| 第78优于第84事件数 | `11` |
| 第84 20日产品级净损益 | `595,360` |
| 第78 20日产品级净损益 | `-7,530` |
| 第84相对第78差额 | `602,890` |

多窗口稳定性：

| 窗口 | 产品级差额 | 组合级差额 | 第84更优事件数 | 第78更优事件数 |
| --- | ---: | ---: | ---: | ---: |
| `5`日 | `350,990` | `323,665` | `11` | `10` |
| `10`日 | `278,710` | `274,600` | `9` | `12` |
| `20`日 | `602,890` | `360,850` | `10` | `11` |
| `40`日 | `746,430` | `584,630` | `11` | `10` |
| `60`日 | `748,115` | `844,875` | `11` | `10` |
| `120`日 | `744,180` | `244,900` | `11` | `10` |

分周期归因：

| 周期 | 事件数 | 第84优于第78 | 第78优于第84 | 20日产品级差额 |
| --- | ---: | ---: | ---: | ---: |
| `pre_ai_2020_2021` | `5` | `1` | `4` | `-121,050` |
| `early_ai_2022_2023` | `10` | `5` | `5` | `365,220` |
| `trend_rich_2024_2025` | `4` | `3` | `1` | `393,140` |
| `latest_2026` | `2` | `1` | `1` | `-34,420` |

候选过滤条件评分：

| 候选条件 | 恢复事件数 | 第84更优事件数 | 第78更优事件数 | 相对第78差额 | 命中率 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `rsi_continuation` | `17` | `9` | `8` | `705,340` | `52.94%` |
| `all_triggers` | `21` | `10` | `11` | `602,890` | `47.62%` |
| `no_breakout` | `12` | `7` | `5` | `476,910` | `58.33%` |
| `direction_ret20_aligned` | `5` | `3` | `2` | `350,000` | `60.00%` |
| `breakout_only` | `9` | `3` | `6` | `125,980` | `33.33%` |
| `ai_rank_top5` | `12` | `3` | `9` | `-230,930` | `25.00%` |

### 修改的回测结果

- 无

### 删除的回测结果

- 无

### 新增产物

- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_entry_structure_recovery_trigger_attribution_event_table_entry_structure_recovery_trigger_attribution_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_entry_structure_recovery_trigger_attribution_candidate_summary_entry_structure_recovery_trigger_attribution_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_entry_structure_recovery_trigger_attribution_period_summary_entry_structure_recovery_trigger_attribution_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_entry_structure_recovery_trigger_attribution_feature_summary_entry_structure_recovery_trigger_attribution_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_entry_structure_recovery_trigger_attribution_horizon_summary_entry_structure_recovery_trigger_attribution_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_entry_structure_recovery_trigger_attribution_summary_entry_structure_recovery_trigger_attribution_v1.json`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_entry_structure_recovery_trigger_attribution_report_entry_structure_recovery_trigger_attribution_v1.md`

### 验证

- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_selection_long015_volref30_corr_entry_structure_recovery_trigger_attribution.py`
- 已完成运行：
  - `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_selection_long015_volref30_corr_entry_structure_recovery_trigger_attribution.py`

### 我的判断

- 第85阶段证明第84阶段不是“完全没价值”。实际触发事件在多个前瞻窗口里相对第78阶段为正，说明恢复风险本身确实能抓回一部分趋势收益。
- 但它仍不能推翻第84阶段完整回测失败的事实。局部事件窗口为正，不等于完整组合路径更稳，因为回测最终还受仓位重叠、后续再入场、权益路径和尾部启动影响。
- `rsi_continuation`是目前最有解释力的非方向专属线索：多头RSI较强、空头RSI较弱时，早期交叉更像趋势延续，而不是弱动量假启动。
- `ai_rank_top5`在本归因中反而为负，说明“AI排名越靠前越适合恢复风险”这个直觉在当前触发样本上不成立，不能用排名阈值继续加补丁。
- 下一步可以只做一个低自由度策略验证：在第84结构条件上叠加RSI方向延续确认。不能扫描阈值，先用经典且可解释的`60/40`。

## 2026-04-25 01:02 第86阶段：入场结构RSI确认恢复策略候选回测

### 改动内容

- 本阶段把第85阶段的`rsi_continuation`线索写入策略层，并运行多周期回测。
- 修改策略文件：
  - `examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
- 新增回测脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_backtest.py`
- 策略实现要点：
  - 默认关闭，不影响既有版本。
  - 延续第84阶段：只在`flat_entry`、`long_case1a/short_case1a`、组合无持仓、无同向相关拥挤时考虑临时恢复风险。
  - 新增RSI方向延续确认：多头要求`RSI >= 60`，空头要求`RSI <= 40`。
  - 仍然不清空`loss_streak`，只影响单笔入场风险预算。

### 新增的参数

- `streak_entry_structure_recovery_require_rsi_confirmation`
  - 默认值：`False`
  - 本次候选：`True`
- `streak_entry_structure_recovery_long_min_rsi`
  - 默认值：`60.0`
  - 本次候选：`60.0`
- `streak_entry_structure_recovery_short_max_rsi`
  - 默认值：`40.0`
  - 本次候选：`40.0`

新增诊断字段：

- `streak_entry_structure_risk_recovery_rsi_confirmation_enabled`
- `streak_entry_structure_risk_recovery_rsi_value`
- `streak_entry_structure_risk_recovery_long_min_rsi`
- `streak_entry_structure_risk_recovery_short_max_rsi`

### 修改的参数

- 延续第78阶段风险治理候选：
  - `streak_risk_state_excluded_products=fu.SHFE`
  - `streak_risk_state_exclusion_mode=profit_only`
- 延续第84阶段入场结构恢复：
  - `enable_streak_entry_structure_risk_recovery=True`
  - `streak_entry_structure_recovery_signals=long_case1a,short_case1a`
  - `streak_entry_structure_recovery_min_multiplier=1.0`
  - `streak_entry_structure_recovery_require_flat_portfolio=True`
  - `streak_entry_structure_recovery_max_same_direction_corr=0.30`
- 本阶段新增启用：
  - `streak_entry_structure_recovery_require_rsi_confirmation=True`
  - `streak_entry_structure_recovery_long_min_rsi=60.0`
  - `streak_entry_structure_recovery_short_max_rsi=40.0`

### 删除的参数

- 无

### 新增的回测结果

| 周期 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `full_2020_2026` | `4,818,660` | `2309.3300%` | `-36.9688%` | `1.2293` | `285,400` | `773` |
| `pre_ai_2020_2021` | `1,233,895` | `516.9475%` | `-36.9688%` | `1.5307` | `57,540` | `306` |
| `post_signal_2022_2026` | `1,744,770` | `772.3850%` | `-42.6406%` | `0.9396` | `103,550` | `381` |
| `early_ai_2022_2023` | `228,080` | `14.0400%` | `-42.6406%` | `0.2542` | `13,585` | `145` |
| `trend_rich_2024_2025` | `1,696,160` | `748.0800%` | `-36.0518%` | `1.6452` | `75,515` | `199` |
| `latest_2026` | `107,275` | `-46.3625%` | `-63.1338%` | `-2.0342` | `4,750` | `22` |

全周期补充指标：

- 期末权益：`4,818,660`
- 总收益：`2309.3300%`
- 最大回撤：`-36.9688%`
- Sharpe：`1.2293`
- 总滑点：`285,400`
- 总交易次数：`773`
- 总净盈亏：`4,618,660`
- 盈利天数：`587`
- 亏损天数：`617`

对比结果：

| 对比对象 | 期末权益差额 | 总收益差额 | 最大回撤差额 | Sharpe差额 | 总滑点差额 | 总交易次数差额 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 第75阶段收益基准 | `174,295` | `87.1475` | `0.0219` | `-0.0633` | `-4,560` | `-18` |
| 第78阶段风险治理候选 | `218,570` | `109.2850` | `0.0219` | `-0.0626` | `25,290` | `-6` |
| 第84阶段入场结构恢复 | `233,140` | `116.5700` | `2.3236` | `0.1100` | `-3,890` | `2` |

### 修改的回测结果

- 无

### 删除的回测结果

- 无

### 新增产物

- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_cycle_summary.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_summary.json`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_report.md`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_formal_daily.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_formal_daily_equity.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_formal_trades_2020_2026_04.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_formal_position_changes_2020_2026_04.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_formal_entry_risk_diagnostics_2020_2026_04.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_formal_entry_candidate_snapshots_2020_2026_04.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_formal_chart.html`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_formal_professional_dashboard.html`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_formal_trade_review.html`

### 验证

- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_backtest.py examples/portfolio_backtesting/analyze_qmt_roll_selection_long015_volref30_corr_entry_structure_recovery_trigger_attribution.py`
- 已完成多周期回测：
  - `.py311/bin/python examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_backtest.py`

### 我的判断

- 第86阶段是一个真实突破，但不能直接升级为正式版本。它在全周期上同时超过第75和第78阶段，且最大回撤略好于第78，说明RSI方向确认确实把第84阶段的一部分假启动过滤掉了。
- 但它的`latest_2026`独立启动表现严重失真：期末权益只有`107,275`，最大回撤`-63.1338%`，Sharpe`-2.0342`。这说明该规则在完整历史权益路径下可赚钱，但对不利起点非常脆弱。
- 当前定位应调整为“收益增强候选”，不是“风险治理第一候选”。第78阶段仍保留为风险治理第一候选，第86阶段进入下一轮鲁棒性反证。
- 后续不应继续扫描RSI阈值。更有价值的是做起始年份、滑点压力、2026尾部归因和触发事件止损/暂停机制，确认它是否能在不牺牲尾部保护的情况下保留全周期收益提升。

## 2026-04-25 01:12 第87阶段：第86阶段起始年份稳健性反证

### 改动内容

- 本阶段不修改策略参数，不改变第86阶段规则，只新增起始年份鲁棒性回测脚本。
- 新增脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_start_year_robustness.py`
- 设计目的：
  - 对第86阶段同一套参数从`2020/2021/2022/2023/2024/2025/2026`七个起始年份分别启动回测。
  - 第75阶段和第78阶段起始年份结果复用既有产物，不重复回测。
  - 目标是验证第86阶段全周期创新高是否依赖单一历史起点。

### 新增的参数

- 无。

### 修改的参数

- 无。
- 本阶段复用第86阶段参数：
  - `streak_risk_state_excluded_products=fu.SHFE`
  - `streak_risk_state_exclusion_mode=profit_only`
  - `enable_streak_entry_structure_risk_recovery=True`
  - `streak_entry_structure_recovery_signals=long_case1a,short_case1a`
  - `streak_entry_structure_recovery_min_multiplier=1.0`
  - `streak_entry_structure_recovery_require_flat_portfolio=True`
  - `streak_entry_structure_recovery_max_same_direction_corr=0.30`
  - `streak_entry_structure_recovery_require_rsi_confirmation=True`
  - `streak_entry_structure_recovery_long_min_rsi=60.0`
  - `streak_entry_structure_recovery_short_max_rsi=40.0`

### 删除的参数

- 无。

### 新增的回测结果

| 起始窗口 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `since_2020` | `4,818,660` | `2309.3300%` | `-36.9688%` | `1.2293` | `285,400` | `773` |
| `since_2021` | `4,471,120` | `2135.5600%` | `-42.3203%` | `1.1558` | `264,040` | `624` |
| `since_2022` | `3,077,440` | `1438.7200%` | `-46.1121%` | `1.0793` | `184,830` | `453` |
| `since_2023` | `2,624,510` | `1212.2550%` | `-34.9723%` | `1.4917` | `141,560` | `345` |
| `since_2024` | `1,647,145` | `723.5725%` | `-36.0518%` | `1.4830` | `86,875` | `234` |
| `since_2025` | `974,635` | `387.3175%` | `-30.0946%` | `1.6592` | `55,130` | `131` |
| `since_2026` | `107,275` | `-46.3625%` | `-63.1338%` | `-2.0342` | `4,750` | `22` |

对比第78阶段：

| 起始窗口 | 期末权益差额 | 总收益差额 | 最大回撤差额 | Sharpe差额 | 交易次数差额 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `since_2020` | `218,570` | `109.2850` | `0.0219` | `-0.0626` | `-6` |
| `since_2021` | `345,140` | `172.5700` | `0.0000` | `-0.0371` | `18` |
| `since_2022` | `60,595` | `30.2975` | `-9.3435` | `-0.1654` | `-3` |
| `since_2023` | `706,325` | `353.1625` | `4.4674` | `0.1675` | `20` |
| `since_2024` | `653,990` | `326.9950` | `-4.9352` | `0.1906` | `35` |
| `since_2025` | `91,980` | `45.9900` | `-1.2133` | `0.0018` | `0` |
| `since_2026` | `-81,370` | `-40.6850` | `-30.7279` | `-1.6893` | `-2` |

汇总：

- 起始年份窗口数：`7`
- 第86阶段相对第78阶段期末权益胜出窗口：`6`
- 第86阶段相对第78阶段Sharpe胜出窗口：`3`
- 第86阶段相对第78阶段平均期末权益差额：`285,033`
- 第86阶段相对第78阶段平均Sharpe差额：`-0.2278`
- 第86阶段相对第78阶段最差期末权益差额：`-81,370`

### 修改的回测结果

- 无。

### 删除的回测结果

- 无。

### 新增产物

- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_start_year_summary.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_start_year_comparison.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_start_year_summary.json`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_start_year_report.md`

### 验证

- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_start_year_robustness.py`
- 已完成起始年份鲁棒性回测：
  - `.py311/bin/python examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_start_year_robustness.py`

### 我的判断

- 第87阶段确认第86不是单一起点幻觉：从`since_2020`到`since_2025`，第86阶段有`6/6`个窗口期末权益高于第78阶段。
- 但它仍然不能升级为正式主版本：Sharpe只赢`3/7`个窗口，且`since_2026`相对第78阶段期末权益少`81,370`、最大回撤恶化`30.7279`个百分点、Sharpe低`1.6893`。
- 这说明第86的本质是“趋势顺风期收益释放增强”，不是“全环境风险治理增强”。它能提高上行捕获，但会在冷启动或尾部不利环境里放大假突破。
- 当前版本排序不变：第78阶段仍是风险治理第一候选；第86阶段保留为收益增强候选；第75阶段仍是收益上限参照。
- 下一步不应该扫描RSI阈值。更有价值的是做2026尾部归因，找出第86在冷启动窗口中具体是哪几笔触发造成破坏，再设计低自由度的暂停或冷启动保护。

## 2026-04-25 01:19 第88阶段：第86阶段2026冷启动尾部归因

### 改动内容

- 本阶段新增2026冷启动尾部归因脚本，并重跑第78阶段、第86阶段的`since_2026`冷启动版本，保存交易、持仓、入场候选和风险诊断明细。
- 新增脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_tail_2026_cold_start_attribution.py`
- 设计目的：
  - 不继续调参，不扫描RSI阈值。
  - 解释第86阶段相对第78阶段在2026冷启动窗口的损害来源。
  - 从组合、产品、日度、恢复风险触发事件四层做归因。

### 新增的参数

- 无。

### 修改的参数

- 无。
- 第78阶段冷启动复用参数：
  - `streak_risk_state_excluded_products=fu.SHFE`
  - `streak_risk_state_exclusion_mode=profit_only`
- 第86阶段冷启动复用参数：
  - `enable_streak_entry_structure_risk_recovery=True`
  - `streak_entry_structure_recovery_signals=long_case1a,short_case1a`
  - `streak_entry_structure_recovery_min_multiplier=1.0`
  - `streak_entry_structure_recovery_require_flat_portfolio=True`
  - `streak_entry_structure_recovery_max_same_direction_corr=0.30`
  - `streak_entry_structure_recovery_require_rsi_confirmation=True`
  - `streak_entry_structure_recovery_long_min_rsi=60.0`
  - `streak_entry_structure_recovery_short_max_rsi=40.0`
  - `streak_risk_state_excluded_products=fu.SHFE`
  - `streak_risk_state_exclusion_mode=profit_only`

### 删除的参数

- 无。

### 新增的回测结果

| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 第78阶段`since_2026`冷启动 | `188,645` | `-5.6775%` | `-32.4059%` | `-0.3449` | `2,360` | `24` |
| 第86阶段`since_2026`冷启动 | `107,275` | `-46.3625%` | `-63.1338%` | `-2.0342` | `4,750` | `22` |

第86相对第78差额：

- 期末权益差额：`-81,370`
- 总收益差额：`-40.6850`个百分点
- 最大回撤差额：`-30.7279`个百分点
- Sharpe差额：`-1.6893`
- 总滑点差额：`2,390`
- 总交易次数差额：`-2`

产品归因最差项：

| 产品 | 第86净盈亏 | 第78净盈亏 | 差额 | 第86仓位变动 | 第78仓位变动 | 仓位变动差额 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `SH.CZCE` | `-88,560` | `-6,540` | `-82,020` | `80` | `6` | `74` |
| `AP.CZCE` | `-46,400` | `0` | `-46,400` | `16` | `0` | `16` |
| `OI.CZCE` | `0` | `2,180` | `-2,180` | `0` | `2` | `-2` |
| `SA.CZCE` | `-2,220` | `-740` | `-1,480` | `6` | `2` | `4` |
| `rb.SHFE` | `-2,940` | `-2,730` | `-210` | `28` | `26` | `2` |

最差日归因：

| 日期 | 第86净盈亏 | 第78净盈亏 | 差额 | 第86权益 | 第78权益 | 权益差额 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `2026-03-23` | `-46,240` | `740` | `-46,980` | `107,275` | `234,485` | `-127,210` |
| `2026-02-09` | `-43,320` | `-2,280` | `-41,040` | `200,135` | `234,945` | `-34,810` |
| `2026-03-03` | `-42,840` | `-4,080` | `-38,760` | `156,035` | `230,745` | `-74,710` |

第86恢复风险触发事件：

| 日期 | 产品 | 方向 | 信号 | 第86手数 | 第78手数 | 手数差 | 第86风险乘数 | 第78风险乘数 | 20日前瞻产品差额 |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `2026-02-06` | `SH.CZCE` | `short` | `short_case1a` | `19` | `1` | `18` | `1.0` | `0.1` | `-82,020` |
| `2026-03-02` | `SH.CZCE` | `short` | `short_case1a` | `21` | `2` | `19` | `1.0` | `0.1` | `-39,900` |
| `2026-03-20` | `AP.CZCE` | `long` | `long_case1a` | `8` | `0` | `8` | `1.0` | `0.0` | `-46,400` |

### 修改的回测结果

- 无。

### 删除的回测结果

- 无。

### 新增产物

归因产物：

- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_tail_2026_cold_start_attribution_summary.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_tail_2026_cold_start_attribution_product_attribution.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_tail_2026_cold_start_attribution_daily_attribution.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_tail_2026_cold_start_attribution_entry_event_comparison.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_tail_2026_cold_start_attribution_recovery_events.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_tail_2026_cold_start_attribution_summary.json`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_tail_2026_cold_start_attribution_report.md`

冷启动明细产物：

- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_streak_since_2026_cold_start_daily.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_streak_since_2026_cold_start_trades_2020_2026_04.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_streak_since_2026_cold_start_position_changes_2020_2026_04.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_streak_since_2026_cold_start_entry_candidate_snapshots_2020_2026_04.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_streak_since_2026_cold_start_entry_risk_diagnostics_2020_2026_04.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_since_2026_cold_start_daily.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_since_2026_cold_start_trades_2020_2026_04.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_since_2026_cold_start_position_changes_2020_2026_04.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_since_2026_cold_start_entry_candidate_snapshots_2020_2026_04.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_since_2026_cold_start_entry_risk_diagnostics_2020_2026_04.csv`

### 验证

- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_tail_2026_cold_start_attribution.py`
- 已完成2026冷启动归因回测：
  - `.py311/bin/python examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_tail_2026_cold_start_attribution.py`

### 我的判断

- 第86阶段2026冷启动崩坏不是全市场普遍恶化，而是高度集中在少数恢复风险事件上。
- 主要损害来自`SH.CZCE`两笔短空恢复：第86把第78原本`0.1`风险乘数下的`1/2`手放大到`19/21`手，两个事件合计贡献大约`-121,920`的产品级前瞻差额。
- `AP.CZCE`的`2026-03-20`多头恢复是第二个尾部点，第78没有开仓，第86开`8`手，20日前瞻差额`-46,400`。
- 这说明第86的问题不是RSI方向确认本身完全无效，而是“亏损连击后、组合已进入回撤时，把风险一次性恢复到1.0”过于激进。
- 下一步不应删除第86，也不应扫描RSI阈值。更合理的方向是设计低自由度冷启动/回撤保护：例如恢复风险只允许在组合回撤很浅时生效，或把恢复乘数从`1.0`改成渐进式，而不是一次性满恢复。

## 2026-04-25 01:40 第89阶段：恢复风险组合回撤硬保护反证

### 改动内容

- 修改策略文件：
  - `examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
- 新增回测脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_dd_guard_backtest.py`
- 设计目的：
  - 不扫描RSI阈值。
  - 只测试一个低自由度风控假设：组合回撤超过阈值后，不允许入场结构RSI恢复风险。
  - 目标是修复第86阶段`latest_2026`独立启动崩坏，同时尽量保留全周期收益增强。

### 新增的参数

- `streak_entry_structure_recovery_max_portfolio_drawdown_pct`
  - 默认值：`-1.0`
  - 含义：小于`0`时关闭；大于等于`0`时，组合当前回撤超过该比例则禁止恢复风险。
- 新增诊断字段：
  - `streak_entry_structure_risk_recovery_portfolio_drawdown_pct`
  - `streak_entry_structure_risk_recovery_max_portfolio_drawdown_pct`

### 修改的参数

- 第89阶段候选设置：
  - `streak_entry_structure_recovery_max_portfolio_drawdown_pct=0.05`
- 其余核心参数沿用第86阶段：
  - `streak_entry_structure_recovery_min_multiplier=1.0`
  - `streak_entry_structure_recovery_require_rsi_confirmation=True`
  - `streak_entry_structure_recovery_long_min_rsi=60.0`
  - `streak_entry_structure_recovery_short_max_rsi=40.0`
  - `streak_entry_structure_recovery_max_same_direction_corr=0.30`
  - `streak_entry_structure_recovery_require_flat_portfolio=True`
  - `streak_risk_state_excluded_products=fu.SHFE`
  - `streak_risk_state_exclusion_mode=profit_only`

### 删除的参数

- 无。

### 新增的回测结果

| 周期 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `full_2020_2026` | `4,495,050` | `2147.5250%` | `-36.9907%` | `1.2819` | `266,370` | `779` |
| `pre_ai_2020_2021` | `1,384,905` | `592.4525%` | `-36.9907%` | `1.6313` | `57,190` | `306` |
| `post_signal_2022_2026` | `2,786,165` | `1293.0825%` | `-37.5422%` | `1.2874` | `169,690` | `431` |
| `early_ai_2022_2023` | `721,720` | `260.8600%` | `-37.5422%` | `1.3070` | `36,710` | `185` |
| `trend_rich_2024_2025` | `964,180` | `382.0900%` | `-31.1166%` | `1.4577` | `42,120` | `164` |
| `latest_2026` | `188,645` | `-5.6775%` | `-32.4059%` | `-0.3449` | `2,360` | `24` |

### 修改的回测结果

- 无。

### 删除的回测结果

- 无。

### 新增产物

- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_dd_guard_cycle_summary.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_dd_guard_summary.json`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_dd_guard_report.md`

### 验证

- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_dd_guard_backtest.py`
- 已完成多周期回测：
  - `.py311/bin/python examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_dd_guard_backtest.py`

### 我的判断

- 第89阶段把`latest_2026`修回第78阶段水平，但代价是全周期期末权益降到`4,495,050`，低于第78阶段`4,600,090`，也低于第75阶段`4,644,365`。
- 这说明“组合回撤超过5%就完全禁止恢复”过于粗糙，它只是把第86收益增强机制大面积关掉，并没有提炼出更本质的有效条件。
- 第89阶段不升级，定位为反证：硬回撤门槛能防尾部，但收益损失过大。

## 2026-04-25 01:40 第90阶段：入场结构RSI恢复风险半恢复候选

### 改动内容

- 新增回测脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_half_backtest.py`
- 策略代码复用第89阶段新增的诊断能力，本阶段不新增策略逻辑。
- 设计目的：
  - 不继续加过滤条件。
  - 把第86阶段一次性恢复到`1.0`改为恢复到`0.5`，测试“恢复幅度”是不是尾部风险的主要来源。

### 新增的参数

- 无。

### 修改的参数

- 第90阶段候选设置：
  - `streak_entry_structure_recovery_min_multiplier=0.5`
- 对比第86阶段：
  - 第86为`streak_entry_structure_recovery_min_multiplier=1.0`
- 其余核心参数沿用第86阶段：
  - `streak_entry_structure_recovery_require_rsi_confirmation=True`
  - `streak_entry_structure_recovery_long_min_rsi=60.0`
  - `streak_entry_structure_recovery_short_max_rsi=40.0`
  - `streak_entry_structure_recovery_max_same_direction_corr=0.30`
  - `streak_entry_structure_recovery_require_flat_portfolio=True`
  - `streak_entry_structure_recovery_max_portfolio_drawdown_pct=-1.0`
  - `streak_risk_state_excluded_products=fu.SHFE`
  - `streak_risk_state_exclusion_mode=profit_only`

### 删除的参数

- 无。

### 新增的回测结果

| 周期 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `full_2020_2026` | `4,732,125` | `2266.0625%` | `-37.0038%` | `1.2885` | `275,290` | `781` |
| `pre_ai_2020_2021` | `1,376,130` | `588.0650%` | `-37.0038%` | `1.6250` | `58,000` | `308` |
| `post_signal_2022_2026` | `2,602,655` | `1201.3275%` | `-41.4342%` | `1.1929` | `154,100` | `428` |
| `early_ai_2022_2023` | `520,520` | `160.2600%` | `-41.4342%` | `1.0032` | `26,305` | `184` |
| `trend_rich_2024_2025` | `1,388,965` | `594.4825%` | `-33.4188%` | `1.5483` | `67,825` | `199` |
| `latest_2026` | `170,775` | `-14.6125%` | `-39.3824%` | `-0.8342` | `3,300` | `22` |

关键对比：

- 相对第78阶段全周期：期末权益`+132,035`，最大回撤恶化约`0.0131`个百分点，Sharpe低`0.0034`，总滑点多`15,180`，交易多`2`笔。
- 相对第86阶段`latest_2026`：期末权益增加`63,500`，最大回撤改善约`23.75`个百分点，Sharpe改善约`1.20`。
- 相对第78阶段`latest_2026`：期末权益少`17,870`，最大回撤恶化约`6.98`个百分点，Sharpe低`0.4894`。

### 修改的回测结果

- 无。

### 删除的回测结果

- 无。

### 新增产物

- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_half_cycle_summary.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_half_summary.json`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_half_report.md`

### 验证

- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_half_backtest.py`
- 已完成多周期回测：
  - `.py311/bin/python examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_half_backtest.py`

### 我的判断

- 第90阶段比第89阶段更接近本质：不是简单禁止恢复，而是承认信号有价值，但亏损连击后的恢复风险只能半开。
- 它全周期超过第75和第78，且大幅缓解第86的2026尾部，是当前最有价值的收益增强候选。
- 但它仍不能直接替代第78阶段，因为`latest_2026`相对第78仍亏更多、回撤更深。
- 下一步必须做起始年份鲁棒性反证和滑点压力，不能因为全周期权益更高就升级。

## 2026-04-25 01:40 第91阶段：第90阶段半恢复起始年份鲁棒性反证

### 改动内容

- 新增起始年份鲁棒性脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_half_start_year_robustness.py`
- 本阶段不改策略、不改参数，只对第90阶段同一套规则跑`2020/2021/2022/2023/2024/2025/2026`七个起始年份窗口。
- 第75阶段和第78阶段对照结果复用既有起始年份稳健性产物，避免重复回测和重复污染。

### 新增的参数

- 无。

### 修改的参数

- 无。
- 复用第90阶段参数：
  - `streak_entry_structure_recovery_min_multiplier=0.5`
  - `streak_entry_structure_recovery_require_rsi_confirmation=True`
  - `streak_entry_structure_recovery_long_min_rsi=60.0`
  - `streak_entry_structure_recovery_short_max_rsi=40.0`
  - `streak_entry_structure_recovery_max_same_direction_corr=0.30`
  - `streak_entry_structure_recovery_require_flat_portfolio=True`
  - `streak_entry_structure_recovery_max_portfolio_drawdown_pct=-1.0`
  - `streak_risk_state_excluded_products=fu.SHFE`
  - `streak_risk_state_exclusion_mode=profit_only`

### 删除的参数

- 无。

### 新增的回测结果

第90阶段起始年份结果：

| 起始窗口 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `since_2020` | `4,732,125` | `2266.0625%` | `-37.0038%` | `1.2885` | `275,290` | `781` |
| `since_2021` | `4,259,800` | `2029.9000%` | `-42.3203%` | `1.1893` | `252,590` | `632` |
| `since_2022` | `2,925,655` | `1362.8275%` | `-43.1572%` | `1.1512` | `179,290` | `459` |
| `since_2023` | `2,386,695` | `1093.3475%` | `-35.1069%` | `1.4437` | `131,850` | `347` |
| `since_2024` | `1,382,070` | `591.0350%` | `-33.4188%` | `1.3986` | `78,105` | `234` |
| `since_2025` | `904,095` | `352.0475%` | `-29.5044%` | `1.6473` | `49,880` | `131` |
| `since_2026` | `170,775` | `-14.6125%` | `-39.3824%` | `-0.8342` | `3,300` | `22` |

相对第78阶段：

| 起始窗口 | 期末权益差额 | 最大回撤差额 | Sharpe差额 |
| --- | ---: | ---: | ---: |
| `since_2020` | `132,035` | `-0.0131`个百分点 | `-0.0034` |
| `since_2021` | `133,820` | `0.0000`个百分点 | `-0.0036` |
| `since_2022` | `-91,190` | `-6.3886`个百分点 | `-0.0935` |
| `since_2023` | `468,510` | `4.3327`个百分点 | `0.1195` |
| `since_2024` | `388,915` | `-2.3022`个百分点 | `0.1063` |
| `since_2025` | `21,440` | `-0.6231`个百分点 | `-0.0101` |
| `since_2026` | `-17,870` | `-6.9765`个百分点 | `-0.4894` |

汇总：

- 第90相对第78期末权益胜出窗口：`5/7`
- 第90相对第78 Sharpe胜出窗口：`2/7`
- 第90相对第78平均期末权益差额：`147,951`
- 第90相对第78平均Sharpe差额：`-0.0534`
- 第90相对第78最差期末权益差额：`-91,190`

### 修改的回测结果

- 无。

### 删除的回测结果

- 无。

### 新增产物

- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_half_start_year_summary.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_half_start_year_comparison.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_half_start_year_summary.json`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_half_start_year_report.md`

### 验证

- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_half_start_year_robustness.py`
- 已完成起始年份鲁棒性回测：
  - `.py311/bin/python examples/portfolio_backtesting/run_qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_half_start_year_robustness.py`

### 我的判断

- 第90阶段通过了“收益增强候选”的最低门槛：`5/7`个起点期末权益高于第78，且`since_2026`没有重现第86阶段`-46.36%`亏损和`-63.13%`回撤。
- 第90阶段没有通过“正式替代第78”的门槛：Sharpe只赢`2/7`，`since_2022`和`since_2026`相对第78仍有明显回撤恶化。
- 当前排序应保持：
  - 第78阶段仍是风险治理正式候选。
  - 第90阶段是比第86更干净的收益增强候选。
  - 第89阶段拒绝升级。
- 下一步按第一性原理不应继续调RSI或回撤阈值，而应做成本压力和交易摩擦反证。如果第90在更高滑点下仍保持多数起点收益优势，再考虑进入正式候选；否则保留为研究分支。

## 2026-04-25 01:44 第92阶段：第90阶段半恢复滑点压力反证

### 改动内容

- 新增滑点压力脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_half_stress.py`
- 设计目的：
  - 不重跑策略，不改变信号、仓位路径和出入场。
  - 基于已保存日度`net_pnl/slippage/trade_count`，对第75、第78、第90做`1/1.5/2/3/5`倍滑点重估。
  - 验证第90阶段的收益增强是否只是来自更多交易和更高摩擦暴露。

### 新增的参数

- 压力测试参数：
  - `SLIPPAGE_MULTIPLIERS=(1.0, 1.5, 2.0, 3.0, 5.0)`

### 修改的参数

- 无。
- 被测策略参数仍为第90阶段：
  - `streak_entry_structure_recovery_min_multiplier=0.5`
  - `streak_entry_structure_recovery_require_rsi_confirmation=True`
  - `streak_entry_structure_recovery_long_min_rsi=60.0`
  - `streak_entry_structure_recovery_short_max_rsi=40.0`
  - `streak_entry_structure_recovery_max_same_direction_corr=0.30`
  - `streak_entry_structure_recovery_require_flat_portfolio=True`
  - `streak_risk_state_excluded_products=fu.SHFE`
  - `streak_risk_state_exclusion_mode=profit_only`

### 删除的参数

- 无。

### 新增的回测结果

第90阶段滑点压力结果：

| 滑点倍数 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `1.0` | `4,732,125` | `2266.0625%` | `-37.0038%` | `1.4545` | `275,290` | `781` |
| `1.5` | `4,594,480` | `2197.2400%` | `-37.7336%` | `1.4196` | `412,935` | `781` |
| `2.0` | `4,456,835` | `2128.4175%` | `-38.4797%` | `1.3850` | `550,580` | `781` |
| `3.0` | `4,181,545` | `1990.7725%` | `-40.0232%` | `1.3169` | `825,870` | `781` |
| `5.0` | `3,630,965` | `1715.4825%` | `-44.1885%` | `1.1851` | `1,376,450` | `781` |

第90相对第78：

| 滑点倍数 | 期末权益差额 | 总收益差额 | 最大回撤差额 | Sharpe差额 | 总滑点差额 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| `1.0` | `132,035` | `66.0175`个百分点 | `-0.0131`个百分点 | `-0.0006` | `15,180` |
| `1.5` | `124,445` | `62.2225`个百分点 | `-0.0137`个百分点 | `-0.0010` | `22,770` |
| `2.0` | `116,855` | `58.4275`个百分点 | `-0.0143`个百分点 | `-0.0014` | `30,360` |
| `3.0` | `101,675` | `50.8375`个百分点 | `0.2259`个百分点 | `-0.0022` | `45,540` |
| `5.0` | `71,315` | `35.6575`个百分点 | `0.3124`个百分点 | `-0.0036` | `75,900` |

第90相对第75：

| 滑点倍数 | 期末权益差额 | 总收益差额 | 最大回撤差额 | Sharpe差额 | 总滑点差额 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| `1.0` | `87,760` | `43.8800`个百分点 | `-0.0131`个百分点 | `-0.0020` | `-14,670` |
| `1.5` | `95,095` | `47.5475`个百分点 | `-0.0137`个百分点 | `-0.0011` | `-22,005` |
| `2.0` | `102,430` | `51.2150`个百分点 | `-0.0143`个百分点 | `-0.0002` | `-29,340` |
| `3.0` | `117,100` | `58.5500`个百分点 | `0.2259`个百分点 | `0.0017` | `-44,010` |
| `5.0` | `146,440` | `73.2200`个百分点 | `0.3124`个百分点 | `0.0059` | `-73,350` |

说明：

- 本阶段Sharpe为日度净盈亏重估口径，用于同一压力脚本内横向比较，不与vn.py引擎原始Sharpe直接混用。

### 修改的回测结果

- 无。

### 删除的回测结果

- 无。

### 新增产物

- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_half_stress.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_half_stress_comparison.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_half_stress_report.md`

### 验证

- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_half_stress.py`
- 已完成滑点压力分析：
  - `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_half_stress.py`

### 我的判断

- 第90阶段没有被全周期滑点压力击穿：即使在`5`倍滑点下，期末权益仍比第78多`71,315`，比第75多`146,440`。
- 但第90相对第78的Sharpe在所有滑点倍数下都略低，说明它的优势仍主要是收益弹性，不是风险调整收益全面改善。
- 成本压力支持第90继续验证，但仍不支持直接替代第78。
- 下一步最有价值的是做“起始年份 + 滑点压力”的交叉反证，尤其关注`since_2022`和`since_2026`两个薄弱起点。

## 2026-04-25 01:49 第93阶段：第90阶段薄弱起点滑点压力交叉反证

### 改动内容

- 新增薄弱起点滑点压力脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_half_weak_window_stress.py`
- 设计目的：
  - 不继续调参。
  - 只重跑第91阶段暴露出的两个薄弱起点：`since_2022`和`since_2026`。
  - 对第78和第90在同一起点下的日度路径做`1/1.5/2/3/5`倍滑点压力。
  - 验证第90的弱点是否会被交易成本进一步放大。

### 新增的参数

- 压力测试参数：
  - `WEAK_WINDOW_NAMES=("since_2022", "since_2026")`
  - `SLIPPAGE_MULTIPLIERS=(1.0, 1.5, 2.0, 3.0, 5.0)`

### 修改的参数

- 无。
- 第78复用参数：
  - `streak_risk_state_excluded_products=fu.SHFE`
  - `streak_risk_state_exclusion_mode=profit_only`
- 第90复用参数：
  - `streak_entry_structure_recovery_min_multiplier=0.5`
  - `streak_entry_structure_recovery_require_rsi_confirmation=True`
  - `streak_entry_structure_recovery_long_min_rsi=60.0`
  - `streak_entry_structure_recovery_short_max_rsi=40.0`
  - `streak_entry_structure_recovery_max_same_direction_corr=0.30`
  - `streak_entry_structure_recovery_require_flat_portfolio=True`
  - `streak_risk_state_excluded_products=fu.SHFE`
  - `streak_risk_state_exclusion_mode=profit_only`

### 删除的参数

- 无。

### 新增的回测结果

`since_2022`第90相对第78：

| 滑点倍数 | 第90期末权益 | 第78期末权益 | 期末权益差额 | 第90最大回撤 | 第78最大回撤 | 回撤差额 | Sharpe差额 | 总滑点差额 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `1.0` | `2,925,655` | `3,016,845` | `-91,190` | `-43.1572%` | `-36.7687%` | `-6.3886`个百分点 | `-0.0697` | `2,540` |
| `1.5` | `2,836,010` | `2,928,470` | `-92,460` | `-43.9209%` | `-37.2694%` | `-6.6515`个百分点 | `-0.0704` | `3,810` |
| `2.0` | `2,746,365` | `2,840,095` | `-93,730` | `-44.6995%` | `-37.7788%` | `-6.9207`个百分点 | `-0.0709` | `5,080` |
| `3.0` | `2,567,075` | `2,663,345` | `-96,270` | `-46.3029%` | `-38.8245%` | `-7.4783`个百分点 | `-0.0714` | `7,620` |
| `5.0` | `2,208,495` | `2,309,845` | `-101,350` | `-50.1798%` | `-41.6050%` | `-8.5747`个百分点 | `-0.0692` | `12,700` |

`since_2026`第90相对第78：

| 滑点倍数 | 第90期末权益 | 第78期末权益 | 期末权益差额 | 第90最大回撤 | 第78最大回撤 | 回撤差额 | Sharpe差额 | 总滑点差额 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `1.0` | `170,775` | `188,645` | `-17,870` | `-39.3824%` | `-32.4059%` | `-6.9765`个百分点 | `-0.4923` | `940` |
| `1.5` | `169,125` | `187,465` | `-18,340` | `-39.7939%` | `-32.6356%` | `-7.1583`个百分点 | `-0.5053` | `1,410` |
| `2.0` | `167,475` | `186,285` | `-18,810` | `-40.2078%` | `-32.8666%` | `-7.3411`个百分点 | `-0.5183` | `1,880` |
| `3.0` | `164,175` | `183,925` | `-19,750` | `-41.0429%` | `-33.3327%` | `-7.7101`个百分点 | `-0.5443` | `2,820` |
| `5.0` | `157,575` | `179,205` | `-21,630` | `-42.7427%` | `-34.2813%` | `-8.4614`个百分点 | `-0.5960` | `4,700` |

汇总：

- `since_2022`：第90期末权益胜出`0/5`，Sharpe胜出`0/5`，期末权益差额区间`-101,350`到`-91,190`。
- `since_2026`：第90期末权益胜出`0/5`，Sharpe胜出`0/5`，期末权益差额区间`-21,630`到`-17,870`。

说明：

- 本阶段Sharpe为日度净盈亏重估口径，用于同一压力脚本内横向比较，不与vn.py引擎原始Sharpe直接混用。

### 修改的回测结果

- 无。

### 删除的回测结果

- 无。

### 新增产物

- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_half_weak_window_stress.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_half_weak_window_stress_comparison.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_half_weak_window_stress_summary.json`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_half_weak_window_stress_report.md`

### 验证

- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_half_weak_window_stress.py`
- 已完成薄弱起点滑点压力交叉验证：
  - `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_half_weak_window_stress.py`

### 我的判断

- 第93阶段推翻了“第90可继续走向正式升级”的想法。
- 第90在全周期和高滑点压力下看起来不错，但在两个已知薄弱起点上，所有滑点倍数都输给第78，且滑点越高权益差距越大。
- 这说明第90的收益增强不是稳定穿越起点的结构优势，而是依赖部分有利路径；它可以保留为研究分支，但不应作为正式版本候选继续加码。
- 当前正式路线应回到第78阶段风险治理版本。后续如果继续研究恢复风险，应重新做事件级归因或动态进攻/防守版本切换，而不是继续在第90上微调。

## 2026-04-25 01:56 第94阶段：恢复风险研究分支第一版事件级归因

### 改动内容

- 新增研究脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_half_event_branch.py`
- 设计目的：
  - 另开恢复风险研究分支，不继续微调第90参数。
  - 以第90半恢复实际触发事件为样本，同时比较第90半恢复、第86满恢复、第78风险治理在事件后多窗口的产品级与组合级贡献。
  - 只使用入场当下已有字段做分桶和候选条件，避免把事后收益直接写成规则。

### 新增的参数

- 研究标签：
  - `MODEL_TAG=entry_structure_rsi_recovery_half_event_branch_v1`
- 研究窗口：
  - `HORIZONS=(5, 10, 20, 40, 60, 120)`

### 修改的参数

- 无。
- 本阶段不改策略参数，不新增正式交易规则。

### 删除的参数

- 无。

### 新增的回测/研究结果

事件级总览：

| 指标 | 数值 |
| --- | ---: |
| 第90恢复事件数 | `17` |
| 涉及产品数 | `12` |
| 第90优于第78事件数 | `9` |
| 第78优于第90事件数 | `8` |
| 第90事件后20日产品净盈亏 | `342,750` |
| 第78同事件后20日产品净盈亏 | `44,870` |
| 第90相对第78 20日产品差额 | `297,880` |
| 第86相对第78 20日产品差额 | `705,460` |
| 第90相对第86 20日产品差额 | `-407,580` |

多窗口稳定性：

| 前瞻窗口 | 第90相对第78产品差额 | 第86相对第78产品差额 | 第90相对第86产品差额 | 第90相对第78组合差额 |
| ---: | ---: | ---: | ---: | ---: |
| `5` | `176,165` | `426,930` | `-250,765` | `204,485` |
| `10` | `155,010` | `383,380` | `-228,370` | `193,195` |
| `20` | `297,880` | `705,460` | `-407,580` | `288,895` |
| `40` | `356,380` | `849,280` | `-492,900` | `388,085` |
| `60` | `356,380` | `849,280` | `-492,900` | `501,015` |
| `120` | `356,380` | `849,280` | `-492,900` | `350,505` |

分周期结果：

| 周期 | 事件数 | 第90优于第78 | 第78优于第90 | 第90相对第78差额 | 第86相对第78差额 | 第90相对第86差额 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `pre_ai_2020_2021` | `3` | `1` | `2` | `-20,880` | `-51,680` | `30,800` |
| `early_ai_2022_2023` | `9` | `5` | `4` | `185,150` | `441,220` | `-256,070` |
| `trend_rich_2024_2025` | `4` | `3` | `1` | `168,710` | `393,140` | `-224,430` |
| `latest_2026` | `1` | `0` | `1` | `-35,100` | `-77,220` | `42,120` |

候选条件线索：

| 候选条件 | 事件数 | 第90优于第78 | 第78优于第90 | 第90相对第78差额 | 命中率 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `ai_rank_gt5` | `8` | `6` | `2` | `363,700` | `75.00%` |
| `stage90_reduces_stage86_volume` | `16` | `9` | `7` | `325,700` | `56.25%` |
| `all_stage90_recovery_events` | `17` | `9` | `8` | `297,880` | `52.94%` |
| `no_breakout` | `8` | `6` | `2` | `251,270` | `75.00%` |
| `direction_ret20_aligned` | `4` | `3` | `1` | `175,940` | `75.00%` |
| `ai_rank_top5` | `9` | `3` | `6` | `-65,820` | `33.33%` |

产品贡献最差和最好：

| 产品 | 事件数 | 第90相对第78差额 | 第90相对第86差额 |
| --- | ---: | ---: | ---: |
| `cu.SHFE` | `2` | `-75,000` | `70,000` |
| `SH.CZCE` | `1` | `-35,100` | `42,120` |
| `sp.SHFE` | `1` | `-27,820` | `0` |
| `jm.DCE` | `3` | `121,620` | `-140,940` |
| `fu.SHFE` | `2` | `183,700` | `-232,000` |

### 修改的回测结果

- 无。

### 删除的回测结果

- 无。

### 新增产物

- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_half_event_branch_event_table_entry_structure_rsi_recovery_half_event_branch_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_half_event_branch_candidate_summary_entry_structure_rsi_recovery_half_event_branch_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_half_event_branch_period_summary_entry_structure_rsi_recovery_half_event_branch_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_half_event_branch_feature_summary_entry_structure_rsi_recovery_half_event_branch_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_half_event_branch_product_summary_entry_structure_rsi_recovery_half_event_branch_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_half_event_branch_horizon_summary_entry_structure_rsi_recovery_half_event_branch_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_half_event_branch_summary_entry_structure_rsi_recovery_half_event_branch_v1.json`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_half_event_branch_report_entry_structure_rsi_recovery_half_event_branch_v1.md`

### 验证

- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_half_event_branch.py`
- 已完成事件级研究分析：
  - `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_half_event_branch.py`

### 我的判断

- 第90不是没有价值。全周期事件级看，第90半恢复相对第78有`297,880`的20日产品级正贡献，并且多窗口都为正。
- 但这不能推翻第93阶段结论，因为第90优势高度依赖时期和路径：`early_ai_2022_2023`与`trend_rich_2024_2025`贡献为正，`pre_ai_2020_2021`和`latest_2026`为负。
- `ai_rank_gt5`、`no_breakout`等条件看起来很好，但样本很小，且带有明显反直觉和路径依赖，不应直接写成策略规则。
- 研究分支的下一步不是调阈值，而是验证“进攻/防守状态切换”：第78作为默认防守版本，只在组合处于有利路径状态时短暂打开恢复风险。这个状态必须来自组合自身的已发生表现，而不是事后品种或年份标签。

## 2026-04-25 01:59 第95阶段：恢复风险进攻/防守状态门反证

### 改动内容

- 新增研究脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_half_offense_state_gate.py`
- 设计目的：
  - 不使用年份、产品或事后收益标签。
  - 用第78防守版本在事件发生前已经形成的组合状态，评估是否存在可用于进攻/防守切换的低自由度状态门。
  - 所有状态特征都用事件日前的日度结果计算，避免同日和未来信息。

### 新增的参数

- 研究标签：
  - `MODEL_TAG=entry_structure_rsi_recovery_half_offense_state_gate_v1`
- 研究状态门：
  - `prior20/60/120_net_pnl > 0`
  - `prior20/60/120_positive_day_rate > 50%`
  - `balance_above_prior60/120_ma`
  - `not_cold_120d`
  - `prior_cum_pnl_gt0`
  - `prior_drawdown_lte20/30`
  - 组合门：`defense_mature_and_prior60_pnl_gt0`、`defense_mature_prior60_pnl_and_balance_gt60ma`

### 修改的参数

- 无。
- 本阶段不改策略参数，不新增正式交易规则。

### 删除的参数

- 无。

### 新增的回测/研究结果

状态门评分核心结果：

| 状态门 | 事件数 | 第90优于第78 | 第78优于第90 | 第90相对第78差额 | 负贡献成本 | 命中率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `all_events` | `17` | `9` | `8` | `297,880` | `-180,630` | `52.94%` |
| `not_cold_120d` | `17` | `9` | `8` | `297,880` | `-180,630` | `52.94%` |
| `prior_cum_pnl_gt0` | `17` | `9` | `8` | `297,880` | `-180,630` | `52.94%` |
| `prior_drawdown_lte30` | `16` | `8` | `8` | `289,000` | `-180,630` | `50.00%` |
| `prior120_pnl_gt0` | `15` | `8` | `7` | `257,330` | `-155,730` | `53.33%` |
| `balance_above_120ma` | `12` | `5` | `7` | `61,170` | `-175,990` | `41.67%` |
| `prior_drawdown_lte20` | `13` | `5` | `8` | `46,260` | `-180,630` | `38.46%` |
| `prior20_pnl_gt0` | `4` | `1` | `3` | `-62,800` | `-71,680` | `25.00%` |
| `balance_above_60ma` | `6` | `1` | `5` | `-122,290` | `-130,090` | `16.67%` |
| `prior60_pnl_gt0` | `9` | `2` | `7` | `-124,590` | `-175,990` | `22.22%` |
| `defense_mature_and_prior60_pnl_gt0` | `9` | `2` | `7` | `-124,590` | `-175,990` | `22.22%` |

### 修改的回测结果

- 无。

### 删除的回测结果

- 无。

### 新增产物

- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_half_offense_state_gate_event_table_entry_structure_rsi_recovery_half_offense_state_gate_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_half_offense_state_gate_gate_summary_entry_structure_rsi_recovery_half_offense_state_gate_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_half_offense_state_gate_summary_entry_structure_rsi_recovery_half_offense_state_gate_v1.json`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_half_offense_state_gate_report_entry_structure_rsi_recovery_half_offense_state_gate_v1.md`

### 验证

- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_half_offense_state_gate.py`
- 已完成进攻/防守状态门研究：
  - `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_rsi_recovery_half_offense_state_gate.py`

### 我的判断

- 第95阶段没有找到可用的低自由度组合状态门。
- 很多看似合理的“组合近期表现好再进攻”条件反而筛到了坏事件，例如`prior60_pnl_gt0`和`balance_above_60ma`都明显劣于全事件。
- 这说明第90事件价值不是简单由组合近期强弱决定；若强行写进攻/防守状态切换，很可能是对17笔小样本的二次过拟合。
- 研究分支当前结论应收敛为：第78保持正式版本；第90/第86恢复机制只保留为事件研究素材，不进入策略层。

## 2026-04-25 02:09 第96阶段：第78阶段正式版本固化审查

### 改动内容

- 新增正式化审查脚本：
  - `examples/portfolio_backtesting/build_qmt_roll_stage78_formal_readiness_report.py`
- 设计目的：
  - 不重新调参，不新增交易规则。
  - 以第75作为收益上限基准，对第78做全周期、起始年份、滑点压力、2026尾部表现审查。
  - 判断第78是否能固化为正式版本，以及应该以什么身份固化。

### 新增的参数

- 研究标签：
  - `MODEL_TAG=stage78_formal_readiness_v1`

### 修改的参数

- 无。
- 本阶段不修改策略参数。

### 删除的参数

- 无。

### 新增的回测/研究结果

第78全周期结果：

| 指标 | 数值 |
| --- | ---: |
| 期末权益 | `4,600,090` |
| 总收益 | `2200.0450%` |
| 最大回撤 | `-36.9907%` |
| Sharpe | `1.2919` |
| 总滑点 | `260,110` |
| 总交易次数 | `779` |

第78相对第75正式基准的关键证据：

| 审查项 | 结果 | 证据 |
| --- | --- | --- |
| 全周期收益成本交换 | `PASS` | 第78期末权益相对第75少`44,275`，但滑点少`29,850`，交易少`12`笔 |
| 全周期最大回撤 | `PASS` | 第78最大回撤`-36.9907%`，与第75持平 |
| 2026尾部改善 | `PASS` | since_2026期末权益相对第75多`24,240`，最大回撤改善`7.6546`个百分点，Sharpe改善`0.2170` |
| 起始年份收益占优 | `WARN` | 起始年份期末权益只赢`2/7`，平均期末权益差额`-58,543` |
| 起始年份Sharpe平衡 | `WARN` | 起始年份Sharpe赢`3/7`，平均Sharpe差额`0.0689` |
| 已知薄弱起点 | `WARN` | since_2023相对第75期末权益少`279,985`，最大回撤差`-3.4488`个百分点 |
| 高滑点韧性 | `PASS` | 5倍滑点下第78相对第75期末权益多`75,125`，Sharpe差`0.0095` |
| 2026绝对收益 | `WARN` | latest_2026仍为负收益：期末权益`188,645`，总收益`-5.6775%`，最大回撤`-32.4059%` |

第78正式化审查结论：

- `CONDITIONAL_PASS_DEFENSIVE_FORMAL`
- 第78可以固化为“防守型风险治理正式版”。
- 第78不能包装成“收益最高正式版”，也不能说它全维度替代第75。
- 它的本质价值是用很小的全周期收益代价，换取更低交易成本、更好的2026尾部和更清晰的风险状态治理。

### 修改的回测结果

- 无。

### 删除的回测结果

- 无。

### 新增产物

- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_stage78_formal_readiness_summary_stage78_formal_readiness_v1.json`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_stage78_formal_readiness_report_stage78_formal_readiness_v1.md`

### 验证

- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/build_qmt_roll_stage78_formal_readiness_report.py`
- 已生成正式化审查报告：
  - `.py311/bin/python examples/portfolio_backtesting/build_qmt_roll_stage78_formal_readiness_report.py`

### 我的判断

- 第78可以固化，但必须以“防守正式版”固化，不是收益增强版。
- 这个结论不来自单一全周期收益，而来自三点：全周期回撤不劣化、交易成本显著下降、弱环境和高滑点下韧性更好。
- 最大风险是第78在起始年份收益上并不全面占优，尤其`since_2023`明显弱于第75；所以正式文档里必须保留第75作为收益上限参照。
- 后续研发不应继续在第90/第86恢复风险上微调，而应以第78为冻结基准，去做全市场品种选择、样本外验证和组合容量/流动性约束。

## 2026-04-25 02:29 第97阶段：第78正式版本配置化固化

### 改动内容

- 新增第78正式配置模块：
  - `examples/portfolio_backtesting/qmt_roll_official_stage78_config.py`
- 新增第78正式运行入口：
  - `examples/portfolio_backtesting/run_qmt_roll_official_stage78_backtest.py`
- 本阶段只做配置化固化与清单生成，不修改策略类默认参数，不重跑完整回测。
- 固化版本名：
  - `official_stage78_defensive_v1`
- 固化定位：
  - `defensive_risk_governance_formal`

### 新增的参数

- 正式版本常量：
  - `OFFICIAL_STAGE78_VERSION=official_stage78_defensive_v1`
  - `OFFICIAL_STAGE78_PROFILE_NAME=ai_top8_plus_fu_satellite_post_signal_profit_shield_streak`
  - `OFFICIAL_STAGE78_ROLE=defensive_risk_governance_formal`
  - `OFFICIAL_STAGE78_FORMAL_PREFIX=qmt_roll_official_stage78_defensive_formal`
  - `OFFICIAL_STAGE78_EXPERIMENT_TAG=qmt_roll_official_stage78_defensive`
  - `OFFICIAL_STAGE78_CAPITAL=200000`
  - `OFFICIAL_STAGE78_PROFIT_SHIELD_MODE=profit_only`
- 正式配置生成函数：
  - `build_official_stage78_paths()`
  - `build_official_stage78_overrides()`
  - `build_official_stage78_manifest()`
- 后续研究开关策略：
  - 独立新研究默认不开启第78正式配置。
  - 只有研究目标是“基于正式版做增量改进”时才开启第78正式配置。
  - 所有新研究晋级前必须与`official_stage78_defensive_v1`对比。

### 修改的参数

- 无。
- `QmtRollPortfolioStrategy`默认参数未改动。
- 第86、第90恢复风险分支未写入正式配置。

### 删除的参数

- 无。

### 新增的回测/研究结果

- 本阶段未新增完整回测结果，只生成正式配置清单。
- 第78正式配置引用的冻结参考结果如下：

| 指标 | full_2020_2026 |
| --- | ---: |
| 期末权益 | `4,600,090` |
| 总收益 | `2200.0450%` |
| 最大回撤 | `-36.9907%` |
| Sharpe | `1.2919` |
| 总滑点 | `260,110` |
| 总交易次数 | `779` |

| 指标 | latest_2026 |
| --- | ---: |
| 期末权益 | `188,645` |
| 总收益 | `-5.6775%` |
| 最大回撤 | `-32.4059%` |
| Sharpe | `-0.3449` |
| 总滑点 | `2,360` |
| 总交易次数 | `24` |

### 修改的回测结果

- 无。

### 删除的回测结果

- 无。

### 新增产物

- `examples/portfolio_backtesting/qmt_roll_official_stage78_config.py`
- `examples/portfolio_backtesting/run_qmt_roll_official_stage78_backtest.py`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_defensive_manifest.json`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_defensive_manifest.md`

### 验证

- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/qmt_roll_official_stage78_config.py`
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/run_qmt_roll_official_stage78_backtest.py`
- 已生成正式配置清单：
  - `.py311/bin/python examples/portfolio_backtesting/run_qmt_roll_official_stage78_backtest.py --manifest-only`

### 我的判断

- 第78现在已经以配置形式固化，不是靠口头约定，也不是硬编码到策略默认值。
- 后续研究不要默认开启第78正式配置；否则新想法的效果会和正式版已有收益混在一起，容易误判。
- 正确用法是：独立新方向先单独验证本质，再与`official_stage78_defensive_v1`做晋级对比；如果研究目标是“正式版上再加一个小改动”，才显式从第78正式配置继承。
- 这能避免沉没成本和基准污染，也能保证第78作为当前正式防守版本可复现。

## 2026-04-25 02:58 第98阶段：第78正式版季度Walk-Forward与小资金流动性审计

### 改动内容

- 新增第78正式版季度冷启动验证脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_official_stage78_quarterly_walkforward_liquidity.py`
- 本阶段验证目标：
  - 用`official_stage78_defensive_v1`冻结配置，从每个季度起点冷启动到`2026-04-30`。
  - 分别统计完整`63d/126d/252d`窗口表现。
  - 对第78正式交易明细做小资金级别的日成交量占比审计。
- 本阶段没有修改交易策略逻辑，也没有新增交易过滤器。
- 修正一个统计口径问题：
  - 初版报告把`2026Q1/2026Q2`等不足`126d/252d`的短窗口计入 horizon 聚合。
  - 已新增`complete_horizon`字段，聚合只统计完整 horizon；不完整窗口保留在明细 CSV 中。
- 修正一个非行为性实现警告：
  - 将`fillna(method="ffill")`改为`.ffill()`，避免 pandas 未来版本兼容性警告。

### 新增的参数

- `MODEL_TAG=quarterly_wf_liquidity_v1`
- `OFFICIAL_STAGE78_VERSION=official_stage78_defensive_v1`
- `OFFICIAL_STAGE78_ROLE=defensive_risk_governance_formal`
- `HORIZON_DAYS=(63, 126, 252)`
- `LIQUIDITY_WARN_VOLUME_SHARE_PCT=1.0`
- `LIQUIDITY_EXTREME_VOLUME_SHARE_PCT=5.0`
- `complete_horizon=1`才进入对应 horizon 聚合。

### 修改的参数

- 无交易参数修改。
- 修改的是报告统计口径，不是策略参数：
  - 不完整 horizon 不参与`63d/126d/252d`聚合胜率。

### 删除的参数

- 无。

### 新增的回测结果

- 冻结参考全周期结果：

| 指标 | full_2020_2026 |
| --- | ---: |
| 期末权益 | `4,600,090` |
| 总收益 | `2200.0450%` |
| 最大回撤 | `-36.9907%` |
| Sharpe | `1.2919` |
| 总滑点 | `260,110` |
| 总交易次数 | `779` |

- 季度 cold-start 汇总：
  - 季度起点数量：`26`
  - horizon 明细行数：`78`
  - 完整 horizon 行数：`71`
  - 不完整 horizon 行数：`7`，已从聚合中剔除。

| Horizon | 完整窗口数 | 正收益窗口数 | 正收益率 | 中位收益 | 最差收益 | 中位最大回撤 | 最差最大回撤 | 中位Sharpe | 最差Sharpe |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `63d` | `25` | `17` | `68.0000%` | `16.2975%` | `-27.7950%` | `-26.6085%` | `-44.5792%` | `1.7456` | `-3.7231` |
| `126d` | `24` | `20` | `83.3333%` | `53.5100%` | `-15.5125%` | `-29.0193%` | `-44.5792%` | `1.5507` | `-2.6382` |
| `252d` | `22` | `21` | `95.4545%` | `103.7725%` | `-6.8250%` | `-30.9217%` | `-44.5792%` | `1.5879` | `-0.2394` |

- 典型弱窗口：
  - `q2020_1 63d`：期末权益`144,410`，总收益`-27.7950%`，最大回撤`-31.1218%`，Sharpe`-3.7231`，交易`33`笔。
  - `q2024_2 63d`：期末权益`156,905`，总收益`-21.5475%`，最大回撤`-43.3720%`，Sharpe`-0.6012`，交易`27`笔。
  - `q2024_2 126d`：期末权益`168,975`，总收益`-15.5125%`，最大回撤`-43.5632%`，Sharpe`-0.1813`，交易`30`笔。
  - `q2022_2 252d`：期末权益`186,350`，总收益`-6.8250%`，最大回撤`-19.9334%`，Sharpe`-0.2394`，交易`26`笔。

- 近端季度 to-end 结果：
  - `q2025_1`：期末权益`882,655`，总收益`341.3275%`，最大回撤`-28.8813%`，Sharpe`1.9483`，交易`131`笔。
  - `q2025_2`：期末权益`657,840`，总收益`228.9200%`，最大回撤`-25.7486%`，Sharpe`2.2330`，交易`99`笔。
  - `q2025_3`：期末权益`572,020`，总收益`186.0100%`，最大回撤`-30.4625%`，Sharpe`2.1148`，交易`81`笔。
  - `q2025_4`：期末权益`303,760`，总收益`51.8800%`，最大回撤`-41.4224%`，Sharpe`1.2014`，交易`54`笔。
  - `q2026_1`：期末权益`188,645`，总收益`-5.6775%`，最大回撤`-32.4059%`，Sharpe`0.0711`，交易`24`笔。
  - `q2026_2`：期末权益`200,000`，总收益`0.0000%`，最大回撤`0.0000%`，Sharpe`0.0000`，交易`0`笔；样本仅`14`日，不参与完整 horizon 结论。

- 小资金流动性审计：
  - 交易数：`779`
  - 缺失行情条数：`0`
  - 零成交量行情条数：`0`
  - 超过日成交量`1%`的交易数：`0`
  - 超过日成交量`5%`的交易数：`0`
  - 成交量占比中位数：`0.0026%`
  - 成交量占比P95：`0.0314%`
  - 最大成交量占比：`0.3029%`
  - 最大占比来自`AP.CZCE`，但仍低于`1%`预警线。

### 修改的回测结果

- 修改了 horizon 聚合统计结果：
  - 旧口径包含不足天数窗口。
  - 新口径只统计完整窗口。
- 交易明细、季度 to-end 结果、流动性审计交易级结果没有修改。

### 删除的回测结果

- 无。

### 新增产物

- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_defensive_quarterly_walkforward_liquidity_quarter_summary_quarterly_wf_liquidity_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_defensive_quarterly_walkforward_liquidity_horizon_summary_quarterly_wf_liquidity_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_defensive_quarterly_walkforward_liquidity_horizon_aggregate_quarterly_wf_liquidity_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_defensive_quarterly_walkforward_liquidity_liquidity_trade_audit_quarterly_wf_liquidity_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_defensive_quarterly_walkforward_liquidity_liquidity_product_summary_quarterly_wf_liquidity_v1.csv`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_defensive_quarterly_walkforward_liquidity_summary_quarterly_wf_liquidity_v1.json`
- `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_defensive_quarterly_walkforward_liquidity_report_quarterly_wf_liquidity_v1.md`

### 验证

- 已完成季度 cold-start 回测和流动性审计：
  - `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_official_stage78_quarterly_walkforward_liquidity.py`
- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_official_stage78_quarterly_walkforward_liquidity.py`
- 已用已有明细重建完整 horizon 聚合和报告：
  - 不重跑交易，只修正统计口径。

### 我的判断

- 对小资金来说，现阶段不需要做复杂容量曲线；但轻量流动性审计是必要的，这次审计通过。
- 第78正式版通过了季度 walk-forward 的基本检验，尤其`252d`完整窗口`21/22`为正，说明它不是单靠单一年份或早期行情成立。
- 但`63d`窗口只有`17/25`为正，且最差短窗口亏损`-27.7950%`，所以它不能被理解成“任意季度入场都平滑赚钱”的版本。
- 最值得监控的是`q2024_2`这类短中期弱窗口：收益修复能力存在，但冷启动初期回撤很深。
- 当前结论：第78可以继续作为正式防守基线；后续不应优先做容量模型，而应做季度复审、短窗口冷启动风险提示、以及与新研究方向的样本外对照。

## 2026-04-25 03:17 第99阶段：第78正式版关闭100万Sizing上限多周期研究

### 本次版本改动

- 改动时间点：`2026-04-25 03:17`
- 目标：临时关闭第78正式版主策略里的`1,000,000`资金 sizing 上限，做同口径多周期对照，判断是否值得正式固化。
- 新增策略参数：
  - `sizing_equity_cap`：默认`1,000,000`，保持第78正式版原行为；设置为`0`表示关闭上限。
- 修改策略逻辑：
  - 将原本写死的`min(estimated_equity, 1_000_000)`改成可配置上限。
  - `sizing_equity_cap <= 0`时使用完整估算权益做 sizing。
- 删除参数：
  - 无。
- 新增脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_official_stage78_sizing_cap_multicycle_backtest.py`
- 新增产物：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_sizing_cap_multicycle_summary_stage78_sizing_cap_multicycle_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_sizing_cap_multicycle_comparison_stage78_sizing_cap_multicycle_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_sizing_cap_multicycle_summary_stage78_sizing_cap_multicycle_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_sizing_cap_multicycle_report_stage78_sizing_cap_multicycle_v1.md`

### 新增回测参数

- 基准版本：`official_stage78_defensive_v1`
- 初始资金：`200,000`
- 基础风险比例：`0.015`
- 对照组一：`stage78_capped_1m`，`sizing_equity_cap=1,000,000`
- 对照组二：`stage78_sizing_cap_off`，`sizing_equity_cap=0`
- 多周期窗口：`full_2020_2026`、`pre_ai_2020_2021`、`post_signal_2022_2026`、`early_ai_2022_2023`、`trend_rich_2024_2025`、`latest_2026`

### 新增回测结果

| 窗口 | 1M封顶期末权益 | 关闭上限期末权益 | 权益差 | 1M封顶总收益 | 关闭上限总收益 | 1M封顶最大回撤 | 关闭上限最大回撤 | 1M封顶Sharpe | 关闭上限Sharpe | 1M封顶滑点 | 关闭上限滑点 | 1M封顶交易数 | 关闭上限交易数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `full_2020_2026` | `4,600,090` | `13,319,690` | `8,719,600` | `2200.0450%` | `6559.8450%` | `-36.9907%` | `-36.9907%` | `1.2919` | `1.2134` | `260,110` | `1,073,530` | `779` | `811` |
| `pre_ai_2020_2021` | `1,384,905` | `1,345,830` | `-39,075` | `592.4525%` | `572.9150%` | `-36.9907%` | `-36.9907%` | `1.6313` | `1.5396` | `57,190` | `63,120` | `306` | `308` |
| `post_signal_2022_2026` | `2,863,385` | `4,126,125` | `1,262,740` | `1331.6925%` | `1963.0625%` | `-37.5422%` | `-39.9498%` | `1.3008` | `1.2236` | `167,710` | `316,050` | `431` | `445` |
| `early_ai_2022_2023` | `721,720` | `721,720` | `0` | `260.8600%` | `260.8600%` | `-37.5422%` | `-37.5422%` | `1.3070` | `1.3070` | `36,710` | `36,710` | `185` | `185` |
| `trend_rich_2024_2025` | `964,180` | `964,180` | `0` | `382.0900%` | `382.0900%` | `-31.1166%` | `-31.1166%` | `1.4577` | `1.4577` | `42,120` | `42,120` | `164` | `164` |
| `latest_2026` | `188,645` | `188,645` | `0` | `-5.6775%` | `-5.6775%` | `-32.4059%` | `-32.4059%` | `-0.3449` | `-0.3449` | `2,360` | `2,360` | `24` | `24` |

### 修改的回测结果

- 无交易结果修改。
- 回测计算完成后，报告生成阶段因`to_markdown_table(max_rows=...)`不兼容报错；已修复脚本，且未重跑交易。
- Markdown报告使用已生成的CSV结果重建。

### 删除的回测结果

- 无。

### 验证

- 已完成多周期对照回测计算：
  - `.py311/bin/python examples/portfolio_backtesting/run_qmt_roll_official_stage78_sizing_cap_multicycle_backtest.py`
  - 说明：交易计算、CSV、JSON已完成；原进程在报告生成阶段退出码为`1`，原因是报告函数参数不兼容。
- 已修复报告函数并生成报告：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_sizing_cap_multicycle_report_stage78_sizing_cap_multicycle_v1.md`
- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py examples/portfolio_backtesting/run_qmt_roll_official_stage78_sizing_cap_multicycle_backtest.py`

### 我的判断

- 关闭`1,000,000` sizing上限在全周期显著放大期末权益，但这主要来自后期权益超过上限后的复利放大，不是信号质量本身变好。
- 关闭上限后全周期Sharpe从`1.2919`降到`1.2134`，总滑点从`260,110`升到`1,073,530`，交易数也增加；收益放大伴随交易成本放大。
- `pre_ai_2020_2021`关闭上限反而更差，`post_signal_2022_2026`收益更高但最大回撤从`-37.5422%`恶化到`-39.9498%`，Sharpe下降。
- 独立短窗口`early_ai_2022_2023`、`trend_rich_2024_2025`、`latest_2026`完全不变，说明关闭上限只有在权益已显著增长后才起作用，对冷启动和近端弱窗口没有帮助。
- 当前结论：不应把“完全关闭100万上限”固化进正式主策略；正式第78继续保持`1,000,000`封顶。后续如果要研究资金上限，应做“分段/渐进式上限”而不是直接关闭，例如`1,000,000 -> 1,500,000 -> 2,000,000`的阶梯 cap，并继续用季度 walk-forward 验证。

## 2026-04-25 03:37 第100阶段：第78正式版关闭100万Sizing上限季度Walk-Forward验证

### 本次版本改动

- 改动时间点：`2026-04-25 03:37`
- 目标：验证第99阶段“关闭100万 sizing 上限收益显著放大”是否能在季度冷启动、多固定持有期中成立，避免把路径依赖的复利放大误判为策略边际改善。
- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_official_stage78_sizing_cap_quarterly_walkforward.py`
- 新增产物：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_sizing_cap_quarterly_walkforward_quarter_summary_stage78_sizing_cap_quarterly_wf_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_sizing_cap_quarterly_walkforward_horizon_summary_stage78_sizing_cap_quarterly_wf_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_sizing_cap_quarterly_walkforward_horizon_aggregate_stage78_sizing_cap_quarterly_wf_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_sizing_cap_quarterly_walkforward_horizon_comparison_stage78_sizing_cap_quarterly_wf_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_sizing_cap_quarterly_walkforward_horizon_comparison_aggregate_stage78_sizing_cap_quarterly_wf_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_sizing_cap_quarterly_walkforward_summary_stage78_sizing_cap_quarterly_wf_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_sizing_cap_quarterly_walkforward_report_stage78_sizing_cap_quarterly_wf_v1.md`
- 修改策略参数：
  - 无。本阶段只做研究验证，不修改正式第78默认配置。
- 新增参数：
  - 对照 profile：`stage78_capped_1m`，`sizing_equity_cap=1,000,000`
  - 对照 profile：`stage78_sizing_cap_off`，`sizing_equity_cap=0`
  - 固定持有期：`63d`、`126d`、`252d`
  - 季度冷启动起点：`2020-01-01`至`2026-04-01`
- 删除参数：
  - 无。

### 新增回测参数

- 基准版本：`official_stage78_defensive_v1`
- 初始资金：`200,000`
- 基础风险比例：`0.045`
- 正式角色：`defensive_risk_governance_formal`
- 有上限组：`sizing_equity_cap=1,000,000`
- 无上限组：`sizing_equity_cap=0`
- 完整窗口统计口径：只统计`complete_horizon=1`的`63d/126d/252d`窗口。

### 新增回测结果

| profile | horizon | 完整窗口数 | 正收益数 | 正收益率 | 中位收益 | 最差收益 | 最差最大回撤 | 中位Sharpe | 最差Sharpe |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `stage78_capped_1m` | `63d` | `25` | `17` | `68.0000%` | `16.2975%` | `-27.7950%` | `-44.5792%` | `1.7456` | `-3.7231` |
| `stage78_sizing_cap_off` | `63d` | `25` | `17` | `68.0000%` | `16.2975%` | `-27.7950%` | `-44.5792%` | `1.7456` | `-3.7231` |
| `stage78_capped_1m` | `126d` | `24` | `20` | `83.3333%` | `53.5100%` | `-15.5125%` | `-44.5792%` | `1.5507` | `-2.6382` |
| `stage78_sizing_cap_off` | `126d` | `24` | `20` | `83.3333%` | `53.5100%` | `-15.5125%` | `-44.5792%` | `1.5507` | `-2.6382` |
| `stage78_capped_1m` | `252d` | `22` | `21` | `95.4545%` | `103.7725%` | `-6.8250%` | `-44.5792%` | `1.5879` | `-0.2394` |
| `stage78_sizing_cap_off` | `252d` | `22` | `21` | `95.4545%` | `103.7725%` | `-6.8250%` | `-44.5792%` | `1.5879` | `-0.2394` |

| horizon | 完整窗口数 | 发生差异窗口 | 无上限收益更好 | 无上限收益更差 | 无上限回撤更差 | 无上限Sharpe更差 | 中位收益差 | 最差收益差 | 最好收益差 | 最差回撤差 | 最差Sharpe差 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `63d` | `25` | `0` | `0` | `0` | `0` | `0` | `0.0000%` | `0.0000%` | `0.0000%` | `0.0000%` | `0.0000` |
| `126d` | `24` | `0` | `0` | `0` | `0` | `0` | `0.0000%` | `0.0000%` | `0.0000%` | `0.0000%` | `0.0000` |
| `252d` | `22` | `3` | `1` | `2` | `2` | `3` | `0.0000%` | `-11.3400%` | `61.1625%` | `-7.1012%` | `-0.0887` |

发生差异的完整窗口：

| 窗口 | 起点 | horizon | 有上限期末权益 | 无上限期末权益 | 收益差 | 回撤差 | Sharpe差 | 滑点差 |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `q2020_3` | `2020-07-01` | `252d` | `850,670` | `850,320` | `-0.1750%` | `-0.0262%` | `-0.0007` | `40` |
| `q2020_4` | `2020-10-01` | `252d` | `1,797,110` | `1,919,435` | `61.1625%` | `-7.1012%` | `-0.0887` | `12,990` |
| `q2021_1` | `2021-01-01` | `252d` | `912,735` | `890,055` | `-11.3400%` | `0.0000%` | `-0.0441` | `1,760` |

代表性全周期无上限结果沿用第99阶段主回测：期末权益`13,319,690`，总收益`6559.8450%`，最大回撤`-36.9907%`，Sharpe`1.2134`，总滑点`1,073,530`，总交易次数`811`。

### 修改的回测结果

- 无。本阶段新增季度 walk-forward 对照，不覆盖第78正式结果。

### 删除的回测结果

- 无。

### 验证

- 已完成季度 walk-forward 对照：
  - `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_official_stage78_sizing_cap_quarterly_walkforward.py`
- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_official_stage78_sizing_cap_quarterly_walkforward.py`

### 我的判断

- 全周期无上限期末权益从`4,600,090`放大到`13,319,690`，看起来涨了很多倍，但季度 walk-forward 说明这不是一个稳定改善冷启动窗口的参数。
- `63d`和`126d`完整窗口完全无差异，说明关闭上限对短中期冷启动没有帮助。
- `252d`只有`3/22`个完整窗口发生差异，且收益更差的窗口多于收益更好的窗口；无上限还带来更多回撤恶化和Sharpe恶化。
- 这更像“权益超过100万后继续放大仓位”的路径依赖复利效应，不是信号胜率、最差窗口、风险调整收益的本质改善。
- 当前结论：不值得关闭第78正式主策略的`1,000,000` sizing上限；正式版本继续默认开启上限。后续如果继续研究资金上限，应该研究分段或渐进式上限，并要求季度 walk-forward 的最差窗口和Sharpe不恶化。

## 2026-04-25 05:08 第101阶段：第78正式版资金上限参数面研究

### 本次版本改动

- 改动时间点：`2026-04-25 05:08`
- 目标：验证固定`1,000,000` sizing权益上限是否应该改成按本金倍数的规则，避免只凭全周期复利放大做判断。
- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_official_stage78_capital_cap_surface.py`
- 新增产物：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_capital_cap_surface_summary_stage78_capital_cap_surface_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_capital_cap_surface_comparison_stage78_capital_cap_surface_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_capital_cap_surface_summary_stage78_capital_cap_surface_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_capital_cap_surface_report_stage78_capital_cap_surface_v1.md`
- 修改策略参数：
  - 无。本阶段只使用第99阶段已配置化的`sizing_equity_cap`。
- 新增参数：
  - 初始资金：`200,000`、`400,000`
  - sizing上限倍数：`2.5x`、`5x`、`7.5x`、`10x`、`关闭上限`
  - 验证窗口：`full_2020_2026`、`post_signal_2022_2026`、`latest_2026`
- 删除参数：
  - 无。

### 新增回测结果

`200,000`本金：

| 窗口 | 上限 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `full_2020_2026` | `500,000` | `2,747,755` | `1273.8775%` | `-31.5415%` | `1.3110` | `134,810` | `728` |
| `full_2020_2026` | `1,000,000` | `4,600,090` | `2200.0450%` | `-36.9907%` | `1.2919` | `260,110` | `779` |
| `full_2020_2026` | `2,000,000` | `7,484,945` | `3642.4725%` | `-36.9907%` | `1.2771` | `469,970` | `803` |
| `post_signal_2022_2026` | `500,000` | `1,720,650` | `760.3250%` | `-36.5518%` | `1.2924` | `89,250` | `410` |
| `post_signal_2022_2026` | `1,000,000` | `2,863,385` | `1331.6925%` | `-37.5422%` | `1.3008` | `167,710` | `431` |
| `post_signal_2022_2026` | `2,000,000` | `4,209,880` | `2004.9400%` | `-39.9498%` | `1.3202` | `240,800` | `443` |
| `latest_2026` | `所有上限` | `188,645` | `-5.6775%` | `-32.4059%` | `-0.3449` | `2,360` | `24` |

`400,000`本金：

| 窗口 | 上限 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `full_2020_2026` | `1,000,000` | `5,712,450` | `1328.1125%` | `-38.8477%` | `1.2912` | `295,970` | `820` |
| `full_2020_2026` | `2,000,000` | `9,161,070` | `2190.2675%` | `-38.8477%` | `1.2177` | `575,330` | `858` |
| `full_2020_2026` | `3,000,000` | `11,524,430` | `2781.1075%` | `-38.8477%` | `1.1408` | `792,900` | `862` |
| `post_signal_2022_2026` | `1,000,000` | `3,370,360` | `742.5900%` | `-43.4199%` | `1.1886` | `192,050` | `448` |
| `post_signal_2022_2026` | `2,000,000` | `5,425,710` | `1256.4275%` | `-43.4199%` | `1.1896` | `339,280` | `466` |
| `post_signal_2022_2026` | `3,000,000` | `6,528,885` | `1532.2212%` | `-43.4199%` | `1.1991` | `393,010` | `472` |
| `latest_2026` | `1,000,000` | `422,315` | `5.5788%` | `-37.7378%` | `0.1275` | `9,140` | `35` |
| `latest_2026` | `2,000,000/3,000,000/4,000,000/关闭` | `414,655` | `3.6638%` | `-38.3765%` | `0.0704` | `9,280` | `37` |

### 修改的回测结果

- 无。第101阶段新增资金上限参数面对照，不覆盖第78正式结果。

### 删除的回测结果

- 无。

### 验证

- 已完成资金上限参数面回测：
  - `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_official_stage78_capital_cap_surface.py`
- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_official_stage78_capital_cap_surface.py`

### 我的判断

- 对`200,000`本金，`1,000,000`上限仍是较合理的收益/风险折中；`500,000`更防守但收益压缩过大，`2,000,000`以上主要是增加复利和交易成本。
- 对`400,000`本金，`2,000,000/3,000,000`上限全周期收益显著更高，但全周期Sharpe下降，`latest_2026`还比`1,000,000`上限差。
- 这说明资金约束不能简单改成“本金固定倍数越高越好”；更高上限是杠杆扩张，不是信号质量提升。
- 需要进一步用季度 walk-forward 检查`400,000`本金下`5x/7.5x`是否真的能穿越冷启动。

## 2026-04-25 05:08 第102阶段：全市场候选`sn.SHFE`作为第二卫星的多周期反证实验

### 本次版本改动

- 改动时间点：`2026-04-25 05:08`
- 目标：验证全市场品种选择在第78已纳入`fu.SHFE`后，是否还有可验证的增量品种。
- 新增脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_official_stage78_fu_sn_satellite_candidate_backtest.py`
- 新增产物：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_fu_sn_satellite_candidate_universe_stage78_fu_sn_satellite_candidate_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_fu_sn_satellite_candidate_eligibility_stage78_fu_sn_satellite_candidate_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_fu_sn_satellite_candidate_summary_stage78_fu_sn_satellite_candidate_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_fu_sn_satellite_candidate_comparison_stage78_fu_sn_satellite_candidate_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_fu_sn_satellite_candidate_summary_stage78_fu_sn_satellite_candidate_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_fu_sn_satellite_candidate_report_stage78_fu_sn_satellite_candidate_v1.md`
- 新增参数：
  - `sn.SHFE`作为第二个固定卫星品种，只在AI信号期后进入候选池。
  - `streak_risk_state_excluded_products=fu.SHFE,sn.SHFE`
  - `streak_risk_state_exclusion_mode=profit_only`
  - `sizing_equity_cap=1,000,000`
- 修改参数：
  - 在第78`fu`卫星基础上，将卫星集合从`fu.SHFE`扩展为`fu.SHFE,sn.SHFE`。
- 删除参数：
  - 无。

### 新增回测结果

| 窗口 | Stage78期末权益 | 候选期末权益 | 权益差 | Stage78总收益 | 候选总收益 | Stage78最大回撤 | 候选最大回撤 | Stage78 Sharpe | 候选Sharpe | 滑点差 | 交易数差 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `full_2020_2026` | `4,600,090` | `4,752,645` | `152,555` | `2200.0450%` | `2276.3225%` | `-36.9907%` | `-36.9907%` | `1.2919` | `1.3067` | `-11,500` | `45` |
| `post_signal_2022_2026` | `2,863,385` | `2,960,100` | `96,715` | `1331.6925%` | `1380.0500%` | `-37.5422%` | `-36.5869%` | `1.3008` | `1.2858` | `-10,170` | `44` |
| `early_ai_2022_2023` | `721,720` | `754,700` | `32,980` | `260.8600%` | `277.3500%` | `-37.5422%` | `-36.5869%` | `1.3070` | `1.2913` | `275` | `21` |
| `trend_rich_2024_2025` | `964,180` | `1,126,920` | `162,740` | `382.0900%` | `463.4600%` | `-31.1166%` | `-29.7382%` | `1.4577` | `1.6193` | `950` | `10` |
| `latest_2026` | `188,645` | `223,145` | `34,500` | `-5.6775%` | `11.5725%` | `-32.4059%` | `-29.1299%` | `-0.3449` | `0.4188` | `-140` | `2` |

### 修改的回测结果

- 无。候选分支不替换第78正式版。

### 删除的回测结果

- 无。

### 验证

- 已完成多周期候选回测：
  - `.py311/bin/python examples/portfolio_backtesting/run_qmt_roll_official_stage78_fu_sn_satellite_candidate_backtest.py`
- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/run_qmt_roll_official_stage78_fu_sn_satellite_candidate_backtest.py`

### 我的判断

- `sn.SHFE`没有被反证掉，反而成为目前全市场品种选择方向的第一个真实增量候选。
- 它的价值不在“扩大品种池”，而在“少数结构通过且和系统节奏互补的卫星品种”。
- 但它增加交易次数，且`post_signal`、`early_ai` Sharpe略降，所以不能只凭多周期结果固化，必须做季度 walk-forward。

## 2026-04-25 05:08 第103阶段：`fu/sn`双卫星季度Walk-Forward复核

### 本次版本改动

- 改动时间点：`2026-04-25 05:08`
- 目标：验证第102阶段`sn.SHFE`增量是否能穿越季度冷启动，而不是只在全周期或近端窗口好看。
- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_official_stage78_fu_sn_satellite_quarterly_walkforward.py`
- 新增产物：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_fu_sn_satellite_quarterly_walkforward_quarter_summary_stage78_fu_sn_satellite_quarterly_wf_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_fu_sn_satellite_quarterly_walkforward_horizon_summary_stage78_fu_sn_satellite_quarterly_wf_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_fu_sn_satellite_quarterly_walkforward_horizon_aggregate_stage78_fu_sn_satellite_quarterly_wf_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_fu_sn_satellite_quarterly_walkforward_horizon_comparison_stage78_fu_sn_satellite_quarterly_wf_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_fu_sn_satellite_quarterly_walkforward_horizon_comparison_aggregate_stage78_fu_sn_satellite_quarterly_wf_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_fu_sn_satellite_quarterly_walkforward_summary_stage78_fu_sn_satellite_quarterly_wf_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_fu_sn_satellite_quarterly_walkforward_report_stage78_fu_sn_satellite_quarterly_wf_v1.md`
- 新增参数：
  - 固定持有期：`63d`、`126d`、`252d`
  - 季度冷启动起点：`2020-01-01`至`2026-04-01`
- 修改参数：
  - 无。
- 删除参数：
  - 无。

### 新增回测结果

| 版本 | horizon | 完整窗口数 | 正收益数 | 正收益率 | 中位收益 | 最差收益 | 最差最大回撤 | 中位Sharpe | 最差Sharpe |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `Stage78` | `63d` | `25` | `17` | `68.0000%` | `16.2975%` | `-27.7950%` | `-44.5792%` | `1.7456` | `-3.7231` |
| `fu/sn`候选 | `63d` | `25` | `18` | `72.0000%` | `17.2250%` | `-27.7950%` | `-44.5792%` | `1.7754` | `-3.7231` |
| `Stage78` | `126d` | `24` | `20` | `83.3333%` | `53.5100%` | `-15.5125%` | `-44.5792%` | `1.5507` | `-2.6382` |
| `fu/sn`候选 | `126d` | `24` | `20` | `83.3333%` | `58.5675%` | `-9.9225%` | `-44.5792%` | `1.8126` | `-1.7229` |
| `Stage78` | `252d` | `22` | `21` | `95.4545%` | `103.7725%` | `-6.8250%` | `-44.5792%` | `1.5879` | `-0.2394` |
| `fu/sn`候选 | `252d` | `22` | `21` | `95.4545%` | `110.8075%` | `-7.2750%` | `-44.5792%` | `1.6681` | `-0.2691` |

候选相对Stage78差异：

| horizon | 完整窗口数 | 收益更好 | 收益更差 | 回撤更差 | Sharpe更差 | 中位收益差 | 最差收益差 | 最好收益差 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `63d` | `25` | `9` | `5` | `7` | `6` | `0.0000%` | `-10.4550%` | `46.4050%` |
| `126d` | `24` | `11` | `6` | `10` | `6` | `0.0000%` | `-8.5425%` | `80.0075%` |
| `252d` | `22` | `13` | `4` | `6` | `5` | `1.4538%` | `-9.9050%` | `143.2800%` |

### 修改的回测结果

- 无。季度复核只新增候选对照。

### 删除的回测结果

- 无。

### 验证

- 已完成季度 walk-forward：
  - `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_official_stage78_fu_sn_satellite_quarterly_walkforward.py`
- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_official_stage78_fu_sn_satellite_quarterly_walkforward.py`

### 我的判断

- `fu/sn`候选通过“值得继续研究”的门槛：63d正收益率从`68%`升到`72%`，126d中位收益和最差收益都改善，252d中位收益也改善。
- 但它没有达到“立即固化正式版”的门槛：部分季度窗口回撤或Sharpe变差，252d最差收益略差于Stage78。
- 这个方向不是“全市场大池继续扩张”，而是“结构预筛后的少数卫星候选”。后续应做`sn`交易归因、滑点压力和起始年份对照，再决定是否升级为第78的后继正式候选。

## 2026-04-25 05:08 第104阶段：40万本金资金上限阶梯季度Walk-Forward

### 本次版本改动

- 改动时间点：`2026-04-25 05:08`
- 目标：验证`400,000`本金是否应该把 sizing 上限从固定`1,000,000`提高到`2,000,000`或`3,000,000`。
- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_official_stage78_400k_cap_ladder_quarterly_walkforward.py`
- 新增产物：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_400k_cap_ladder_quarterly_walkforward_quarter_summary_stage78_400k_cap_ladder_quarterly_wf_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_400k_cap_ladder_quarterly_walkforward_horizon_summary_stage78_400k_cap_ladder_quarterly_wf_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_400k_cap_ladder_quarterly_walkforward_horizon_aggregate_stage78_400k_cap_ladder_quarterly_wf_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_400k_cap_ladder_quarterly_walkforward_horizon_comparison_stage78_400k_cap_ladder_quarterly_wf_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_400k_cap_ladder_quarterly_walkforward_horizon_comparison_aggregate_stage78_400k_cap_ladder_quarterly_wf_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_400k_cap_ladder_quarterly_walkforward_summary_stage78_400k_cap_ladder_quarterly_wf_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_400k_cap_ladder_quarterly_walkforward_report_stage78_400k_cap_ladder_quarterly_wf_v1.md`
- 新增参数：
  - 初始资金：`400,000`
  - 上限倍数：`2.5x=1,000,000`、`5x=2,000,000`、`7.5x=3,000,000`
  - 固定持有期：`63d`、`126d`、`252d`
- 修改参数：
  - 无。
- 删除参数：
  - 无。

### 新增回测结果

| 上限 | horizon | 完整窗口数 | 正收益数 | 正收益率 | 中位收益 | 最差收益 | 最差最大回撤 | 中位Sharpe | 最差Sharpe |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `2.5x` | `63d` | `25` | `21` | `84.0000%` | `23.7775%` | `-24.3137%` | `-45.9480%` | `1.8723` | `-3.2957` |
| `5x` | `63d` | `25` | `21` | `84.0000%` | `23.7775%` | `-24.3137%` | `-45.9480%` | `1.9441` | `-3.2957` |
| `7.5x` | `63d` | `25` | `21` | `84.0000%` | `23.7775%` | `-24.3137%` | `-45.9480%` | `1.9441` | `-3.2957` |
| `2.5x` | `126d` | `24` | `24` | `100.0000%` | `53.2644%` | `1.6375%` | `-51.8345%` | `1.7546` | `0.2639` |
| `5x` | `126d` | `24` | `24` | `100.0000%` | `53.2644%` | `1.6375%` | `-51.8345%` | `1.7546` | `0.2639` |
| `7.5x` | `126d` | `24` | `24` | `100.0000%` | `53.2644%` | `1.6375%` | `-51.8345%` | `1.7546` | `0.2639` |
| `2.5x` | `252d` | `22` | `22` | `100.0000%` | `134.5331%` | `29.9113%` | `-51.8345%` | `1.7690` | `0.6972` |
| `5x` | `252d` | `22` | `22` | `100.0000%` | `128.4131%` | `29.9113%` | `-51.8345%` | `1.7387` | `0.6972` |
| `7.5x` | `252d` | `22` | `22` | `100.0000%` | `128.4131%` | `29.9113%` | `-51.8345%` | `1.7387` | `0.6972` |

相对`2.5x=1,000,000`的差异：

| 候选上限 | horizon | 收益更好 | 收益更差 | 回撤更差 | Sharpe更差 | 中位收益差 | 最差收益差 | 最差回撤差 | 最差Sharpe差 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `5x` | `63d` | `1` | `5` | `6` | `5` | `0.0000%` | `-17.9225%` | `-7.9067%` | `-0.2525` |
| `7.5x` | `63d` | `1` | `5` | `6` | `5` | `0.0000%` | `-17.9225%` | `-7.9067%` | `-0.2525` |
| `5x` | `126d` | `4` | `5` | `7` | `6` | `0.0000%` | `-27.6200%` | `-10.3773%` | `-0.2529` |
| `7.5x` | `126d` | `4` | `5` | `7` | `6` | `0.0000%` | `-27.6200%` | `-10.3773%` | `-0.2529` |
| `5x` | `252d` | `7` | `8` | `9` | `13` | `0.0000%` | `-32.7538%` | `-11.7391%` | `-0.3016` |
| `7.5x` | `252d` | `7` | `8` | `9` | `13` | `0.0000%` | `-43.3863%` | `-16.3920%` | `-0.3371` |

### 修改的回测结果

- 无。第104阶段只新增`400,000`本金上限阶梯验证。

### 删除的回测结果

- 无。

### 验证

- 已完成季度 walk-forward：
  - `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_official_stage78_400k_cap_ladder_quarterly_walkforward.py`
- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_official_stage78_400k_cap_ladder_quarterly_walkforward.py`

### 我的判断

- `400,000`本金不应把 sizing 上限从`1,000,000`提高到`2,000,000/3,000,000`。
- 高上限在全周期能放大收益，但季度 WFA 显示它没有改善完整窗口中位收益，反而在多个窗口恶化收益、回撤和Sharpe。
- 对小资金来说，真正有价值的规则不是“取消上限”或“按本金提高上限”，而是保留绝对上限保护；如果后续要做，只能研究更保守的动态降杠杆，而不是提高上限。

## 2026-04-25 08:07 第105阶段：`fu/sn`双卫星反证归因与稳健性验证

### 本次版本改动

- 改动时间点：`2026-04-25 08:07`
- 目标：验证第102/103阶段的`sn.SHFE`候选是否只是回测偶然，重点做三件事：
  - `sn.SHFE`真实产品归因
  - 同口径公平滑点压力对照
  - 年度起点迁移对照
- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_official_stage78_fu_sn_satellite_robustness.py`
- 新增产物：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_fu_sn_satellite_robustness_full_summary_stage78_fu_sn_satellite_robustness_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_fu_sn_satellite_robustness_product_attribution_stage78_fu_sn_satellite_robustness_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_fu_sn_satellite_robustness_product_year_attribution_stage78_fu_sn_satellite_robustness_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_fu_sn_satellite_robustness_slippage_stress_stage78_fu_sn_satellite_robustness_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_fu_sn_satellite_robustness_slippage_comparison_stage78_fu_sn_satellite_robustness_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_fu_sn_satellite_robustness_start_year_comparison_stage78_fu_sn_satellite_robustness_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_fu_sn_satellite_robustness_summary_stage78_fu_sn_satellite_robustness_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_fu_sn_satellite_robustness_report_stage78_fu_sn_satellite_robustness_v1.md`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_fu_sn_satellite_robustness_candidate_full_daily.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_fu_sn_satellite_robustness_candidate_full_position_changes_2020_2026_04.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_fu_sn_satellite_robustness_candidate_full_trades_2020_2026_04.csv`
- 新增参数：
  - 稳健性模型标签：`stage78_fu_sn_satellite_robustness_v1`
  - 公平滑点压力倍数：`1.0`、`1.5`、`2.0`、`3.0`、`5.0`
  - 起点年份窗口：`q2020_1`、`q2021_1`、`q2022_1`、`q2023_1`、`q2024_1`、`q2025_1`、`q2026_1`
  - 候选卫星品种：`fu.SHFE,sn.SHFE`
  - 资金上限：`1,000,000`
- 修改参数：
  - 无。
- 删除参数：
  - 无。

### 新增回测结果

完整窗口正式统计：

| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `Stage78` | `4,600,090` | `2200.0450%` | `-36.9907%` | `1.2919` | `260,110` | `779` |
| `fu/sn`候选 | `4,752,645` | `2276.3225%` | `-36.9907%` | `1.3067` | `248,610` | `824` |
| 差异 | `+152,555` | `+76.2775%` | `0.0000%` | `+0.0148` | `-11,500` | `+45` |

`sn.SHFE`产品归因：

| 品种 | 净利润 | 组合净利润贡献 | 最大产品回撤/本金 | 交易次数 | 总滑点 | 单笔净利润 | 首次交易 | 最近交易 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| `sn.SHFE` | `222,720` | `4.8921%` | `-109.5350%` | `53` | `2,380` | `4,202.2642` | `2022-03-01` | `2026-01-19` |

`sn.SHFE`年度归因：

| 年份 | 净利润 | 交易次数 | 总滑点 | 活跃天数 |
| --- | ---: | ---: | ---: | ---: |
| `2020` | `0` | `0` | `0` | `0` |
| `2021` | `0` | `0` | `0` | `0` |
| `2022` | `134,080` | `10` | `650` | `25` |
| `2023` | `-17,910` | `14` | `680` | `29` |
| `2024` | `-113,550` | `13` | `550` | `21` |
| `2025` | `100,610` | `14` | `440` | `23` |
| `2026` | `119,490` | `2` | `60` | `7` |

公平滑点压力对照：

| 滑点倍数 | Stage78期末权益 | 候选期末权益 | 候选差异 | Stage78 Sharpe | 候选Sharpe | Sharpe差异 | 候选总滑点差异 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `1.0` | `4,600,090` | `4,752,645` | `152,555` | `1.4551` | `1.4687` | `0.0135` | `-11,500` |
| `1.5` | `4,470,035` | `4,628,340` | `158,305` | `1.4206` | `1.4350` | `0.0144` | `-17,250` |
| `2.0` | `4,339,980` | `4,504,035` | `164,055` | `1.3864` | `1.4017` | `0.0152` | `-23,000` |
| `3.0` | `4,079,870` | `4,255,425` | `175,555` | `1.3191` | `1.3360` | `0.0169` | `-34,500` |
| `5.0` | `3,559,650` | `3,758,205` | `198,555` | `1.1887` | `1.2092` | `0.0205` | `-57,500` |

年度起点迁移对照：

| 起点 | Stage78期末权益 | 候选期末权益 | 候选差异 | 收益差异 | 回撤差异 | Sharpe差异 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `q2020_1` | `4,600,090` | `4,752,645` | `152,555` | `76.2775%` | `0.0000%` | `0.0135` |
| `q2021_1` | `4,125,980` | `4,227,455` | `101,475` | `50.7375%` | `0.0000%` | `0.0091` |
| `q2022_1` | `3,016,845` | `3,098,020` | `81,175` | `40.5875%` | `0.6629%` | `-0.0068` |
| `q2023_1` | `1,918,185` | `1,954,595` | `36,410` | `18.2050%` | `2.6133%` | `0.0133` |
| `q2024_1` | `993,155` | `1,263,155` | `270,000` | `135.0000%` | `1.3784%` | `0.2168` |
| `q2025_1` | `882,655` | `1,034,575` | `151,920` | `75.9600%` | `-0.0900%` | `0.2501` |
| `q2026_1` | `188,645` | `223,145` | `34,500` | `17.2500%` | `3.2760%` | `0.7939` |

### 修改的回测结果

- 无。第105阶段仍然是候选反证，不替换正式第78策略。

### 删除的回测结果

- 无。

### 验证

- 已完成完整窗口稳健性验证：
  - `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_official_stage78_fu_sn_satellite_robustness.py`
- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_official_stage78_fu_sn_satellite_robustness.py`

### 我的判断

- `sn.SHFE`没有被反证掉，反而通过了更严格的三项验证：真实产品归因为正、同口径5倍滑点压力下仍优于第78、年度起点迁移全部正向。
- 这不属于典型参数过拟合，因为没有搜索周期参数、没有调阈值、没有按收益最优反复挑TopN；它只是把结构预筛中已经通过的第二个卫星品种做固定候选验证。
- 但`sn.SHFE`不是无风险增量：`2023`和`2024`年度归因为负，尤其`2024`亏损`113,550`。所以它更像“跨周期净贡献为正的卫星”，不是可以无限扩展品种池的证据。
- 方向判断：全市场品种选择方向有明确价值，但应该继续坚持“少数卫星、先验结构、反证检验”，不能回到大池扩张。
- 下一步建议：可以把`fu/sn`作为第78的后继候选版本进入正式固化前审查；资金上限方向则继续维持第104阶段结论，不提高`1,000,000`绝对上限。

## 2026-04-25 09:46 第106阶段：第105 `fu/sn`后继候选配置化固化

### 本次版本改动

- 改动时间点：`2026-04-25 09:46`
- 目标：把第105阶段通过反证的`fu/sn`候选固化为独立配置开关，但不覆盖第78正式防守版。
- 新增代码：
  - `examples/portfolio_backtesting/qmt_roll_stage105_fu_sn_config.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage105_fu_sn_backtest.py`
- 新增产物：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage105_fu_sn_satellite_successor_candidate_manifest.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage105_fu_sn_satellite_successor_candidate_manifest.md`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage105_fu_sn_satellite_successor_candidate_summary.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage105_fu_sn_satellite_successor_candidate_summary.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage105_fu_sn_satellite_successor_candidate_report.md`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage105_fu_sn_satellite_successor_candidate_daily.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage105_fu_sn_satellite_successor_candidate_position_changes_2020_2026_04.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage105_fu_sn_satellite_successor_candidate_trades_2020_2026_04.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage105_fu_sn_satellite_successor_candidate_statistics.json`
- 新增参数：
  - `STAGE105_VERSION=stage105_fu_sn_satellite_successor_candidate_v1`
  - `STAGE105_ROLE=stage78_successor_candidate`
  - `STAGE105_FORMAL_PREFIX=qmt_roll_stage105_fu_sn_satellite_successor_candidate`
  - `STAGE105_EXPERIMENT_TAG=qmt_roll_stage105_fu_sn_satellite_successor_candidate`
  - `STAGE105_SIZING_EQUITY_CAP=1,000,000`
  - `satellite_products=fu.SHFE,sn.SHFE`
  - `new_satellite_product=sn.SHFE`
  - `research_switch_policy.default_for_new_independent_research=off`
- 修改参数：
  - 无。第78正式配置没有被修改。
- 删除参数：
  - 无。

### 新增回测结果

第105配置化入口复跑完整窗口：

| 版本 | 窗口 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `stage105_fu_sn_satellite_successor_candidate_v1` | `full_2020_2026` | `4,752,645` | `2276.3225%` | `-36.9907%` | `1.3067` | `248,610` | `824` |

与第105冻结参考值对齐检查：

| 指标 | 差异 |
| --- | ---: |
| 期末权益差异 | `0` |
| Sharpe差异 | `0.0000` |
| 总滑点差异 | `0` |

配置化清单记录的关键证据：

| 证据 | 数值 |
| --- | ---: |
| `sn.SHFE`全周期净利润 | `222,720` |
| `sn.SHFE`交易次数 | `53` |
| `sn.SHFE`总滑点 | `2,380` |
| 公平`5x`滑点下相对第78期末权益差异 | `198,555` |
| 年度起点正向差异 | `7/7` |

### 修改的回测结果

- 无。第106阶段只是配置化固化第105候选，不改第78正式结果。

### 删除的回测结果

- 无。

### 验证

- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/qmt_roll_stage105_fu_sn_config.py examples/portfolio_backtesting/run_qmt_roll_stage105_fu_sn_backtest.py`
- 已完成配置化入口完整窗口复跑：
  - `.py311/bin/python examples/portfolio_backtesting/run_qmt_roll_stage105_fu_sn_backtest.py`

### 我的判断

- 第105候选已经完成配置化固化，可以作为第78的后继候选开关使用。
- 但它仍不是“覆盖第78”的正式版本：第78继续是冻结防守正式版，Stage105是`opt-in`候选。
- 后续独立新研究默认不应打开Stage105；只有当研究问题明确是在第78正式版上做增量改进，或专门审查`fu/sn`候选时，才使用这个开关。
- 这样处理能保留`sn`带来的真实增量，同时避免把`sn`的样本内路径优势混进所有新研究，降低过拟合扩散风险。

## 2026-04-25 10:10 第107阶段：Stage105小资金实盘适配审计

### 本次版本改动

- 改动时间点：`2026-04-25 10:10`
- 目标：验证`stage105_fu_sn_satellite_successor_candidate_v1`在`400,000`本金下是否具备实盘机械可行性。
- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage105_small_capital_live_readiness.py`
- 新增产物：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage105_fu_sn_small_capital_400k_daily.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage105_fu_sn_small_capital_400k_position_changes_2020_2026_04.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage105_fu_sn_small_capital_400k_trades_2020_2026_04.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage105_fu_sn_small_capital_400k_statistics.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage105_small_capital_live_readiness_daily_risk_stage105_small_capital_live_readiness_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage105_small_capital_live_readiness_product_exposure_stage105_small_capital_live_readiness_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage105_small_capital_live_readiness_contract_granularity_stage105_small_capital_live_readiness_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage105_small_capital_live_readiness_liquidity_trade_audit_stage105_small_capital_live_readiness_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage105_small_capital_live_readiness_liquidity_product_summary_stage105_small_capital_live_readiness_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage105_small_capital_live_readiness_summary_stage105_small_capital_live_readiness_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage105_small_capital_live_readiness_report_stage105_small_capital_live_readiness_v1.md`
- 新增参数：
  - 小资金审计本金：`400,000`
  - 保证金预警阈值：`60%`权益
  - 保证金极端阈值：`80%`权益
  - 单品种保证金占比预警阈值：`45%`
  - 流动性预警阈值：成交量占市场成交量`1%`
  - 流动性极端阈值：成交量占市场成交量`5%`
- 修改参数：
  - 无。Stage105交易规则未改。
- 删除参数：
  - 无。

### 新增回测结果

`400,000`本金Stage105完整窗口：

| 版本 | 本金 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `stage105_fu_sn_satellite_successor_candidate_v1` | `400,000` | `5,865,005` | `1366.2513%` | `-38.8477%` | `1.3040` | `284,470` | `865` |

路径风险：

| 指标 | 数值 |
| --- | ---: |
| 最差单日净盈亏 | `-336,350` |
| 最差单日日期 | `2025-07-28` |
| 最差单日/前一日权益 | `-5.8750%` |
| 最差5日净盈亏 | `-404,360` |
| 最差5日/初始本金 | `-101.0900%` |
| 最差20日净盈亏 | `-440,700` |
| 最差20日/初始本金 | `-110.1750%` |
| 最大连续亏损天数 | `7` |

保证金与集中度：

| 指标 | 数值 |
| --- | ---: |
| 最大保证金占用 | `477,095` |
| 最大保证金/权益 | `118.1558%` |
| 最大保证金/初始本金 | `119.2739%` |
| 最大名义本金/权益 | `957.6978%` |
| 最大同时活跃品种数 | `8` |
| 最大同时活跃合约数 | `8` |
| 保证金超过权益`60%`天数 | `53` |
| 保证金超过权益`80%`天数 | `14` |
| 单品种保证金占比超过`45%`天数 | `975` |
| 最大单手保证金品种 | `au.SHFE` |
| 最大单手保证金 | `62,972` |
| 最大单手保证金/初始本金 | `15.7430%` |

流动性审计：

| 指标 | 数值 |
| --- | ---: |
| 交易数 | `865` |
| 缺失行情 | `0` |
| 零成交量行情 | `0` |
| 超过市场成交量`1%`交易数 | `0` |
| 超过市场成交量`5%`交易数 | `0` |
| 成交量占比中位数 | `0.0029%` |
| 成交量占比P95 | `0.0303%` |
| 最大成交量占比 | `0.3029%` |

### 修改的回测结果

- 无。第107阶段只新增`400,000`本金审计，不改Stage105和第78正式结果。

### 删除的回测结果

- 无。

### 验证

- 已完成小资金实盘适配审计：
  - `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage105_small_capital_live_readiness.py`
- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_stage105_small_capital_live_readiness.py`

### 我的判断

- Stage105在`400,000`本金下收益仍然很强，但不能按当前版本直接实盘部署。
- 硬伤不是流动性，流动性审计很好；硬伤是保证金路径：最大保证金/权益达到`118.1558%`，这在真实账户里可能触发无法开仓、追加保证金或被动降风险。
- 最差5日亏损超过初始本金`100%`，这不代表账户必然归零，因为当时权益已增长，但说明路径波动对小本金心理和风控非常不友好。
- 结论：Stage105交易逻辑有价值，但`400,000`部署必须先做保证金感知降杠杆版本，不能直接把当前Stage105作为小资金正式版。

## 2026-04-25 10:10 第108阶段：Stage105正式晋级审查

### 本次版本改动

- 改动时间点：`2026-04-25 10:10`
- 目标：统一审查Stage105是否能替代第78正式防守版，尤其结合第107阶段小资金实盘约束。
- 新增脚本：
  - `examples/portfolio_backtesting/build_qmt_roll_stage105_promotion_review.py`
- 新增产物：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage105_promotion_review_scorecard_stage105_promotion_review_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage105_promotion_review_comparison_stage105_promotion_review_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage105_promotion_review_summary_stage105_promotion_review_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage105_promotion_review_report_stage105_promotion_review_v1.md`
- 新增参数：
  - 晋级审查模型标签：`stage105_promotion_review_v1`
  - 晋级硬阻断条件：`400k max margin/balance`超过部署阈值
  - 估算安全资金阈值：`80%`保证金上限、`60%`保证金上限
- 修改参数：
  - 无。
- 删除参数：
  - 无。

### 新增回测结果

- 无新增回测。第108阶段复用第75、第78、第103、第105、第107阶段结果做晋级审查。

核心对照：

| 版本 | 定位 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 相对第78期末权益 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `stage75_return_ceiling` | 收益上限参考 | `4,644,365` | `2222.1825%` | `-36.9907%` | `1.2926` | `289,960` | `791` | `44,275` |
| `official_stage78_defensive_v1` | 防守正式基线 | `4,600,090` | `2200.0450%` | `-36.9907%` | `1.2919` | `260,110` | `779` | `0` |
| `stage105_fu_sn_satellite_successor_candidate_v1` | 第78后继候选 | `4,752,645` | `2276.3225%` | `-36.9907%` | `1.3067` | `248,610` | `824` | `152,555` |

晋级评分卡：

| 维度 | 状态 | 证据 |
| --- | --- | --- |
| 全周期收益 | `PASS` | 相对第78期末权益`+152,555` |
| 全周期风险调整 | `PASS` | Sharpe相对第78`+0.0148`，最大回撤不变 |
| 季度冷启动 | `PASS_WITH_WARNING` | `63d`正收益率`72%`对第78`68%`，但`252d`最差收益差`-9.9050%` |
| 产品归因 | `PASS_WITH_WARNING` | `sn.SHFE`净利润`222,720`，但`2023/2024`为负 |
| 公平滑点压力 | `PASS` | `5x`公平滑点下仍优于第78 |
| 年度起点迁移 | `PASS` | 正向差异`7/7` |
| 小资金保证金 | `FAIL` | `400k`最大保证金/权益`118.1558%`，极端保证金天数`14` |
| 小资金路径亏损 | `WARN` | 最差5日亏损`-404,360`，约初始本金`-101.0900%` |
| 合约粒度 | `WARN` | 最大单手保证金`62,972`，约初始本金`15.7430%` |
| 流动性 | `PASS` | 超过市场成交量`1%`交易数为`0`，最大成交量占比`0.3029%` |

晋级审查结论：

| 项目 | 结果 |
| --- | --- |
| 决策 | `REJECT_FORMAL_REPLACEMENT_FOR_400K_AS_IS` |
| 硬阻断数量 | `1` |
| 主要阻断 | `400k margin occupancy exceeds deployable threshold` |
| 估算`80%`保证金上限所需最低资金 | `596,369` |
| 估算`60%`保证金上限所需最低资金 | `795,159` |

### 修改的回测结果

- 无。第108阶段是晋级审查，不重写已有回测。

### 删除的回测结果

- 无。

### 验证

- 已完成晋级审查：
  - `.py311/bin/python examples/portfolio_backtesting/build_qmt_roll_stage105_promotion_review.py`
- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/build_qmt_roll_stage105_promotion_review.py`

### 我的判断

- Stage105的交易逻辑值得保留，且在收益、Sharpe、滑点压力、起点迁移上明显优于第78。
- 但对于`400,000`本金，Stage105不能按当前版本正式替代第78，因为保证金占用是硬阻断。
- 下一步不应该继续做全市场加品种或提高资金上限，而应该做“保证金感知的Stage105部署版”：保留Stage105入场和品种逻辑，但在保证金占用过高、单手合约过粗、连续亏损或回撤状态下自动降风险。
- 第78继续保留为正式防守基线；Stage105继续保留为后继候选和研究开关，直到保证金感知版本通过同样审查。

## 2026-04-25 10:18 第109阶段：Stage105现有资金约束扫描（400k）

### 本次版本改动

- 改动时间点：`2026-04-25 10:18`
- 目标：先不新增复杂交易规则，只用策略已有的总资金占用上限和单笔资金占用上限，验证是否能把Stage105变成`400,000`本金可部署版本。
- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage105_margin_constraint_surface.py`
- 新增产物：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage105_margin_constraint_surface_summary_stage109_margin_constraint_surface_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage105_margin_constraint_surface_summary_stage109_margin_constraint_surface_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage105_margin_constraint_surface_report_stage109_margin_constraint_surface_v1.md`
- 新增参数：
  - 扫描模型标签：`stage109_margin_constraint_surface_v1`
  - 本金：`400,000`
  - 扫描档位：`cap70_single35`、`cap60_single30`、`cap50_single25`、`cap45_single20`
  - 保证金观察门槛：`60%`
  - 保证金极端门槛：`80%`
  - 保证金拒绝门槛：`100%`
- 修改参数：
  - 无。第109阶段只通过`strategy_overrides`扫描既有参数。
- 删除参数：
  - 无。

### 新增回测结果

| 档位 | `max_capital_usage_ratio` | `max_single_trade_capital_usage_ratio` | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 最大保证金/权益 | `>80%`天数 | `>100%`天数 | 标签 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `cap70_single35` | `0.70` | `0.35` | `4,472,335` | `1018.0838%` | `-26.2163%` | `1.4724` | `202,570` | `851` | `85.4174%` | `2` | `0` | `watch_margin_gate` |
| `cap60_single30` | `0.60` | `0.30` | `3,923,805` | `880.9513%` | `-22.9096%` | `1.5306` | `169,280` | `815` | `72.2309%` | `0` | `0` | `pass_margin_gate` |
| `cap50_single25` | `0.50` | `0.25` | `2,965,475` | `641.3687%` | `-23.1565%` | `1.4017` | `132,590` | `783` | `55.3008%` | `0` | `0` | `pass_margin_gate` |
| `cap45_single20` | `0.45` | `0.20` | `2,766,945` | `591.7363%` | `-21.6475%` | `1.4757` | `118,860` | `782` | `51.7933%` | `0` | `0` | `pass_margin_gate` |

路径风险补充：

| 档位 | 最差5日/初始资金 | 最差20日/初始资金 | 最大连续亏损天数 |
| --- | ---: | ---: | ---: |
| `cap70_single35` | `-75.6175%` | `-86.0475%` | `7` |
| `cap60_single30` | `-64.3975%` | `-74.5150%` | `7` |
| `cap50_single25` | `-52.6263%` | `-47.9075%` | `7` |
| `cap45_single20` | `-46.8525%` | `-45.4725%` | `7` |

### 修改的回测结果

- 无。

### 删除的回测结果

- 无。

### 验证

- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_stage105_margin_constraint_surface.py`
- 已完成扫描：
  - `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage105_margin_constraint_surface.py`

### 我的判断

- 静态资金约束是有效方向：从原始Stage105的`400k`最大保证金/权益`118.1558%`压到了`cap45_single20`的`51.7933%`。
- 但单次全周期不能决定正式部署。`cap60_single30`虽然收益更高，也通过完整窗口保证金门槛，但仍需要季度冷启动验证。
- 下一步只验证`cap60_single30`和`cap45_single20`，不继续扩大网格，避免把资金限制做成参数拟合。

## 2026-04-25 10:54 第110阶段：Stage105资金约束候选季度冷启动验证

### 本次版本改动

- 改动时间点：`2026-04-25 10:54`
- 目标：对第109阶段两个候选`cap60_single30`和`cap45_single20`做季度冷启动验证，防止只看全周期收益。
- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage105_margin_profile_quarterly_walkforward.py`
- 新增产物：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage105_margin_profile_quarterly_walkforward_quarter_summary_stage110_margin_profile_quarterly_wf_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage105_margin_profile_quarterly_walkforward_horizon_summary_stage110_margin_profile_quarterly_wf_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage105_margin_profile_quarterly_walkforward_horizon_aggregate_stage110_margin_profile_quarterly_wf_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage105_margin_profile_quarterly_walkforward_summary_stage110_margin_profile_quarterly_wf_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage105_margin_profile_quarterly_walkforward_report_stage110_margin_profile_quarterly_wf_v1.md`
- 新增参数：
  - 验证模型标签：`stage110_margin_profile_quarterly_wf_v1`
  - 验证候选：`cap60_single30`、`cap45_single20`
  - 冷启动起点：所有季度起点
  - 观察周期：`63d`、`126d`、`252d`
  - 本金：`400,000`
- 修改参数：
  - 无。
- 删除参数：
  - 无。

### 新增回测结果

季度冷启动聚合：

| 档位 | 周期 | 窗口数 | 正收益率 | 最差收益 | 中位收益 | 最差回撤 | 最大保证金/权益 | `>80%`窗口数 | `>100%`窗口数 | 最差20日/初始资金 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `cap60_single30` | `63d` | `25` | `76.0000%` | `-10.1900%` | `12.4838%` | `-32.7572%` | `108.5602%` | `6` | `2` | `-49.2050%` |
| `cap60_single30` | `126d` | `24` | `95.8333%` | `-2.5238%` | `42.1325%` | `-32.7572%` | `108.5602%` | `8` | `2` | `-67.9200%` |
| `cap60_single30` | `252d` | `22` | `100.0000%` | `12.2950%` | `78.4475%` | `-32.7572%` | `103.0240%` | `7` | `1` | `-74.5150%` |
| `cap45_single20` | `63d` | `25` | `72.0000%` | `-9.4875%` | `9.2850%` | `-26.1991%` | `60.6937%` | `0` | `0` | `-34.5575%` |
| `cap45_single20` | `126d` | `24` | `95.8333%` | `-1.2013%` | `20.6644%` | `-26.1991%` | `63.3237%` | `0` | `0` | `-42.1325%` |
| `cap45_single20` | `252d` | `22` | `100.0000%` | `6.0625%` | `43.7556%` | `-26.1991%` | `63.3237%` | `0` | `0` | `-44.3425%` |

关键冷启动暴露：

| 档位 | 冷启动窗口 | 到期收益 | 最大保证金/权益 | 结论 |
| --- | --- | ---: | ---: | --- |
| `cap60_single30` | `2020Q4` | `827.5838%` | `111.3877%` | 保证金硬失败 |
| `cap60_single30` | `2025Q4` | `44.5000%` | `108.5602%` | 尾部冷启动硬失败 |
| `cap45_single20` | `2020Q4` | `553.1212%` | `67.3967%` | 通过 |
| `cap45_single20` | `2025Q4` | `25.0937%` | `56.0852%` | 通过 |

### 修改的回测结果

- 无。

### 删除的回测结果

- 无。

### 验证

- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_stage105_margin_profile_quarterly_walkforward.py`
- 已完成季度冷启动验证：
  - `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage105_margin_profile_quarterly_walkforward.py`

### 我的判断

- `cap60_single30`不能作为`400k`正式部署档，原因不是收益差，而是季度冷启动存在`>100%`保证金/权益的硬失败。
- `cap45_single20`是目前唯一通过所有季度冷启动保证金门槛的Stage105小资金候选。
- 这个结果说明“更高收益档”不应被正式固化；对小资金实盘，生存约束优先于全周期收益最大化。

## 2026-04-25 11:01 第111阶段：Stage105 400k保证金安全部署候选固化

### 本次版本改动

- 改动时间点：`2026-04-25 11:01`
- 目标：把第110阶段通过验证的`cap45_single20`配置化固化为独立版本，后续可以显式开关和复现。
- 新增配置：
  - `examples/portfolio_backtesting/qmt_roll_stage111_400k_margin_safe_config.py`
- 新增runner：
  - `examples/portfolio_backtesting/run_qmt_roll_stage111_400k_margin_safe_backtest.py`
- 新增产物：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage111_400k_margin_safe_candidate_manifest.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage111_400k_margin_safe_candidate_manifest.md`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage111_400k_margin_safe_candidate_summary.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage111_400k_margin_safe_candidate_summary.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage111_400k_margin_safe_candidate_report.md`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage111_400k_margin_safe_candidate_statistics.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage111_400k_margin_safe_candidate_position_changes_2020_2026_04.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage111_400k_margin_safe_candidate_trades_2020_2026_04.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage111_400k_margin_safe_candidate_chart.html`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage111_400k_margin_safe_candidate_professional_dashboard.html`
- 新增参数：
  - 版本：`stage111_stage105_400k_margin_safe_profile_v1`
  - 角色：`stage105_400k_deployment_candidate`
  - 本金：`400,000`
  - `max_capital_usage_ratio=0.45`
  - `max_single_trade_capital_usage_ratio=0.20`
  - 基础版本：`stage105_fu_sn_satellite_successor_candidate_v1`
  - 使用策略：默认不开启，只在`400k`小资金部署、Stage105晋级审查或Stage111增量研究时开启
- 修改参数：
  - 无。主策略逻辑未改，只新增配置化profile。
- 删除参数：
  - 无。

### 新增回测结果

Stage111完整窗口`400k`结果：

| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 最大保证金/权益 | 最大保证金/初始资金 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `stage111_stage105_400k_margin_safe_profile_v1` | `2,766,945` | `591.7363%` | `-21.6475%` | `1.4757` | `118,860` | `782` | `51.7933%` | `51.2081%` |

Stage111季度验证引用：

| 周期 | 正收益率 | 最差收益 | 中位收益 | 最大保证金/权益 | `>80%`窗口数 | `>100%`窗口数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `63d` | `72.0000%` | `-9.4875%` | `9.2850%` | `60.6937%` | `0` | `0` |
| `126d` | `95.8333%` | `-1.2013%` | `20.6644%` | `63.3237%` | `0` | `0` |
| `252d` | `100.0000%` | `6.0625%` | `43.7556%` | `63.3237%` | `0` | `0` |

淘汰对照：

| 档位 | 被淘汰原因 | 完整窗口收益 | 完整窗口最大保证金/权益 | 季度最大保证金/权益 |
| --- | --- | ---: | ---: | ---: |
| `cap60_single30` | 季度冷启动保证金超过`100%` | `880.9513%` | `72.2309%` | `108.5602%` |

### 修改的回测结果

- 无。

### 删除的回测结果

- 无。

### 验证

- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/qmt_roll_stage111_400k_margin_safe_config.py examples/portfolio_backtesting/run_qmt_roll_stage111_400k_margin_safe_backtest.py`
- 已完成正式全周期回测：
  - `.py311/bin/python examples/portfolio_backtesting/run_qmt_roll_stage111_400k_margin_safe_backtest.py`

### 我的判断

- Stage111是当前Stage105家族里最适合`400,000`本金的部署候选，不是最高收益版本。
- 它牺牲了Stage105原始高收益，换来季度冷启动下不突破`80%`保证金门槛；这比追求全周期收益更符合小资金长期生存。
- Stage78仍然是正式防守基线；Stage105仍是高收益研究候选；Stage111是小资金部署候选。
- 后续新研究默认不应开启Stage111，除非研究主题是`400k`部署、保证金治理或Stage111本身的增量改进。

## 2026-04-25 11:19 第112阶段：Stage111思路迁移到20万本金可行性审计

### 本次版本改动

- 改动时间点：`2026-04-25 11:19`
- 是否是重要突破版本：否。属于重要否定结论版本，确认Stage111不能原样迁移到`200,000`本金。
- 目标：基于Stage111同一套资金约束，检查`200,000`本金是否可部署。
- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage111_200k_live_readiness.py`
- 新增产物：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage111_200k_live_readiness_daily_margin_stage112_stage111_200k_live_readiness_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage111_200k_live_readiness_product_daily_stage112_stage111_200k_live_readiness_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage111_200k_live_readiness_position_changes_2020_2026_04_stage112_stage111_200k_live_readiness_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage111_200k_live_readiness_summary_stage112_stage111_200k_live_readiness_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage111_200k_live_readiness_report_stage112_stage111_200k_live_readiness_v1.md`
- 新增参数：
  - 审计模型标签：`stage112_stage111_200k_live_readiness_v1`
  - 本金：`200,000`
  - 继承Stage111资金约束：`max_capital_usage_ratio=0.45`
  - 继承Stage111单笔约束：`max_single_trade_capital_usage_ratio=0.20`
  - 单手合约预警阈值：`20%`
  - 单手合约拒绝阈值：`25%`
  - 最差5日亏损拒绝阈值：`-50%`初始本金
  - 最差20日亏损拒绝阈值：`-70%`初始本金
- 修改参数：
  - 本次只把回测本金从Stage111的`400,000`改为`200,000`
  - 交易逻辑、品种池、AI过滤、相关性门控、资金占用比例均未改
- 删除参数：
  - 无。

### 新增回测结果

Stage111逻辑在`200,000`本金完整窗口结果：

| 版本 | 本金 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 胜率 | 决策 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `stage112_stage111_200k_live_readiness_v1` | `200,000` | `1,355,600` | `577.8000%` | `-24.5782%` | `1.3252` | `53,120` | `555` | `39.8601%` | `REJECT_200K_AS_IS` |

风险审计：

| 指标 | 结果 |
| --- | ---: |
| 最差单日净盈亏 | `-152,725` |
| 最差单日日期 | `2025-07-28` |
| 最差单日/前一日权益 | `-11.2079%` |
| 最差5日净盈亏 | `-171,625` |
| 最差5日/初始资金 | `-85.8125%` |
| 最差20日净盈亏 | `-112,335` |
| 最差20日/初始资金 | `-56.1675%` |
| 最大连续亏损天数 | `6` |
| 最大保证金/权益 | `49.9754%` |
| 最大保证金/初始资金 | `131.0379%` |
| 保证金`>60%`权益天数 | `0` |
| 保证金`>80%`权益天数 | `0` |
| 保证金`>100%`权益天数 | `0` |
| 最大单手合约保证金 | `64,950` |
| 最大单手合约保证金/初始资金 | `32.4750%` |

硬阻断原因：

| 阻断 | 解释 |
| --- | --- |
| `single_contract_margin_too_coarse` | 最大单手合约保证金约占`200,000`本金`32.4750%`，超过`25%`拒绝阈值 |
| `worst_5d_loss_too_large` | 最差5日亏损约初始本金`-85.8125%`，超过`-50%`拒绝阈值 |

### 修改的回测结果

- 无。第112阶段不修改Stage111的`400,000`结论。

### 删除的回测结果

- 无。

### 验证

- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_stage111_200k_live_readiness.py`
- 已完成完整窗口审计：
  - `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage111_200k_live_readiness.py`
- 未继续跑季度晋级验证：
  - 原因：完整窗口已触发单手合约粒度和最差5日亏损两个硬阻断，季度验证不应作为晋级流程继续消耗时间。

### 我的判断

- Stage111的“低资金占用比例”思路在`200,000`本金下仍能压住组合保证金/权益，但压不住合约粒度和路径亏损。
- 表面看总收益`577.8000%`很高，但真实小资金部署的第一性问题不是收益，而是单手合约太粗和短窗口损失太大。
- 结论：`200,000`本金不能直接沿用Stage111。

### 后续规划和TODO

- 不建议继续对Stage111的`0.45/0.20`做季度晋级。
- 下一步如果继续做`200,000`本金方向，应先做“20万可交易品种/合约粒度过滤”，排除单手保证金过高的品种，再重新构建小资金版本。
- 可研究方向：
  - 单手保证金/本金上限过滤，例如`<=15%`或`<=20%`
  - 最大同时持仓从`8`降到更保守档位
  - 对高保证金品种做白名单/黑名单
  - 单独做20万版本的季度冷启动，而不是沿用40万版本结论

## 2026-04-25 11:38 第113阶段：Stage111 20万单手合约粒度过滤审计

### 本次版本改动

- 改动时间点：`2026-04-25 11:38`
- 是否是重要突破版本：否。属于关键诊断版本，确认“过滤高单手保证金品种”能解决合约粒度问题，但完整窗口本身不足以晋级。
- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage111_200k_contract_granularity_filter.py`
- 新增产物：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage111_200k_contract_granularity_filter_contract_margin_audit_stage113_stage111_200k_contract_granularity_filter_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage111_200k_contract_granularity_filter_universe_threshold_20p0_stage113_stage111_200k_contract_granularity_filter_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage111_200k_contract_granularity_filter_summary_stage113_stage111_200k_contract_granularity_filter_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage111_200k_contract_granularity_filter_report_stage113_stage111_200k_contract_granularity_filter_v1.md`
- 新增参数：
  - 模型标签：`stage113_stage111_200k_contract_granularity_filter_v1`
  - 本金：`200,000`
  - 单手合约保证金过滤阈值：`20%`、`15%`
  - 继承Stage111资金约束：`max_capital_usage_ratio=0.45`
  - 继承Stage111单笔约束：`max_single_trade_capital_usage_ratio=0.20`
- 修改参数：
  - 品种池从Stage111原始品种池改为按“历史最大单手保证金/20万本金”过滤
  - 交易逻辑、AI品种池过滤、相关性门控、风险比例不变
- 删除参数：
  - 无。

### 新增回测结果

20%与15%阈值过滤后结果一致，保留`15`个品种，剔除`5`个品种：`au.SHFE`、`cu.SHFE`、`jm.DCE`、`lh.DCE`、`sn.SHFE`。

| 版本 | 本金 | 阈值 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 胜率 | 最大单手保证金/本金 | 决策 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `stage113_stage111_200k_contract_granularity_filter_v1` | `200,000` | `20%` | `932,280` | `366.1400%` | `-24.6971%` | `1.0501` | `53,700` | `512` | `40.3042%` | `10.7700%` | `RECHECK_BY_QUARTERLY_WF` |
| `stage113_stage111_200k_contract_granularity_filter_v1` | `200,000` | `15%` | `932,280` | `366.1400%` | `-24.6971%` | `1.0501` | `53,700` | `512` | `40.3042%` | `10.7700%` | `RECHECK_BY_QUARTERLY_WF` |

风险审计：

| 指标 | 结果 |
| --- | ---: |
| 最大保证金/权益 | `51.3696%` |
| 最大保证金/初始资金 | `121.1976%` |
| 保证金`>80%`权益天数 | `0` |
| 保证金`>100%`权益天数 | `0` |
| 最差单日/前一日权益 | `-12.7179%` |
| 最差5日/初始资金 | `-76.2450%` |
| 最差20日/初始资金 | `-53.2550%` |

### 修改的回测结果

- 无。

### 删除的回测结果

- 无。

### 验证

- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_stage111_200k_contract_granularity_filter.py`
- 已完成完整窗口审计：
  - `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage111_200k_contract_granularity_filter.py`

### 我的判断

- 20万版本的第一硬伤不是Stage111资金占用比例，而是某些品种单手保证金太粗。
- 单手保证金过滤后，最大单手保证金/本金从Stage112的`32.4750%`降到`10.7700%`，这是结构性改善，不是收益拟合。
- 但完整窗口最差5日按初始本金口径仍很难看，必须用季度冷启动重新判断，不能直接固化。

### 后续规划和TODO

- 使用`20%`过滤品种池做季度冷启动验证。
- 如果季度验证中保证金不越线且短窗口亏损可接受，再考虑固化为20万研究候选。

## 2026-04-25 11:49 第114阶段：Stage111 20万单手粒度过滤季度冷启动验证

### 本次版本改动

- 改动时间点：`2026-04-25 11:49`
- 是否是重要突破版本：是。确认20万经过单手合约粒度过滤后，保证金硬阻断消失，可作为研究候选继续推进。
- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage111_200k_granularity_quarterly_walkforward.py`
- 新增产物：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage111_200k_granularity_quarterly_walkforward_horizon_aggregate_stage114_stage111_200k_granularity_quarterly_wf_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage111_200k_granularity_quarterly_walkforward_horizon_summary_stage114_stage111_200k_granularity_quarterly_wf_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage111_200k_granularity_quarterly_walkforward_quarter_summary_stage114_stage111_200k_granularity_quarterly_wf_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage111_200k_granularity_quarterly_walkforward_report_stage114_stage111_200k_granularity_quarterly_wf_v1.md`
- 新增参数：
  - 模型标签：`stage114_stage111_200k_granularity_quarterly_wf_v1`
  - 本金：`200,000`
  - 品种池：Stage113 `20%`单手保证金过滤池
  - 季度冷启动窗口：`63d`、`126d`、`252d`
- 修改参数：
  - 无。交易逻辑、资金约束、AI过滤、相关性门控沿用Stage111/Stage113。
- 删除参数：
  - 无。

### 新增回测结果

季度冷启动聚合结果：

| 周期 | 窗口数 | 正收益率 | 最差收益 | 中位收益 | 最差最大回撤 | 最大保证金/权益 | `>80%`窗口数 | `>100%`窗口数 | 最差5日/本金 | 最差20日/本金 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `63d` | `25` | `64.0000%` | `-3.0550%` | `5.7550%` | `-28.9600%` | `46.7592%` | `0` | `0` | `-33.7975%` | `-41.6725%` |
| `126d` | `24` | `79.1667%` | `-5.5700%` | `11.1288%` | `-28.9600%` | `46.7592%` | `0` | `0` | `-33.7975%` | `-41.6725%` |
| `252d` | `22` | `77.2727%` | `-5.7800%` | `24.1625%` | `-28.9600%` | `46.7592%` | `0` | `0` | `-39.9050%` | `-49.0550%` |

完整到结束窗口补充观察：

- 所有完整到`2026-04-30`的季度起点未出现保证金`>80%`或`>100%`硬越线。
- `q2025_3`冷启动到结束：期末权益`252,795`，总收益`26.3975%`，最大回撤`-16.0752%`，Sharpe`1.1025`，总滑点`3,930`，总交易次数`42`。

### 修改的回测结果

- 无。

### 删除的回测结果

- 无。

### 验证

- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_stage111_200k_granularity_quarterly_walkforward.py`
- 已完成季度冷启动验证：
  - `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage111_200k_granularity_quarterly_walkforward.py`

### 我的判断

- Stage114解决了Stage112的两个核心硬阻断之一：单手合约粒度和保证金越线风险。
- 但它不如Stage111的40万版本稳定：`63d/126d/252d`正收益率分别为`64.0000%/79.1667%/77.2727%`，弱于40万Stage111的`72.0000%/95.8333%/100.0000%`。
- 因此它可以作为20万研究候选，但不能升为正式部署版本。

### 后续规划和TODO

- 将Stage114对应配置固化为Stage115研究候选。
- 后续研究目标不是继续追求完整窗口收益，而是提高季度冷启动稳定性，同时不重新引入高保证金品种。

## 2026-04-25 12:01 第115阶段：Stage111 20万单手粒度安全研究候选固化

### 本次版本改动

- 改动时间点：`2026-04-25 12:01`
- 是否是重要突破版本：否。属于候选固化版本，把Stage114结论变成可复用配置，但不晋级正式部署。
- 新增配置：
  - `examples/portfolio_backtesting/qmt_roll_stage115_200k_granularity_safe_config.py`
- 新增runner：
  - `examples/portfolio_backtesting/run_qmt_roll_stage115_200k_granularity_safe_backtest.py`
- 新增产物：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage115_200k_granularity_safe_candidate_manifest.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage115_200k_granularity_safe_candidate_manifest.md`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage115_200k_granularity_safe_candidate_summary.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage115_200k_granularity_safe_candidate_summary.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage115_200k_granularity_safe_candidate_report.md`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage115_200k_granularity_safe_candidate_statistics.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage115_200k_granularity_safe_candidate_trades_2020_2026_04.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage115_200k_granularity_safe_candidate_position_changes_2020_2026_04.csv`
- 新增参数：
  - 版本：`stage115_stage111_200k_granularity_safe_candidate_v1`
  - 定位：`stage111_200k_research_candidate`
  - 本金：`200,000`
  - 单手合约保证金过滤阈值：`20%`
  - 品种池：`qmt_roll_stage111_200k_contract_granularity_filter_universe_threshold_20p0_stage113_stage111_200k_contract_granularity_filter_v1.csv`
  - Stage111资金约束：`max_capital_usage_ratio=0.45`
  - Stage111单笔约束：`max_single_trade_capital_usage_ratio=0.20`
- 修改参数：
  - 相比Stage111，仅修改本金和产品池；交易规则、AI过滤、相关性门控、sizing equity cap保持一致。
- 删除参数：
  - 无。

### 新增回测结果

Stage115完整窗口复现结果：

| 版本 | 本金 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 胜率 | 定位 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `stage115_stage111_200k_granularity_safe_candidate_v1` | `200,000` | `932,280` | `366.1400%` | `-24.6971%` | `1.0501` | `53,700` | `512` | `40.3042%` | `20万研究候选，非正式部署` |

引用Stage114季度验证：

| 周期 | 正收益率 | 最差收益 | 中位收益 | 最大保证金/权益 | `>80%`窗口数 | `>100%`窗口数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `63d` | `64.0000%` | `-3.0550%` | `5.7550%` | `46.7592%` | `0` | `0` |
| `126d` | `79.1667%` | `-5.5700%` | `11.1288%` | `46.7592%` | `0` | `0` |
| `252d` | `77.2727%` | `-5.7800%` | `24.1625%` | `46.7592%` | `0` | `0` |

### 修改的回测结果

- 无。

### 删除的回测结果

- 无。

### 验证

- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/qmt_roll_stage115_200k_granularity_safe_config.py examples/portfolio_backtesting/run_qmt_roll_stage115_200k_granularity_safe_backtest.py`
- 已完成完整窗口复现：
  - `.py311/bin/python examples/portfolio_backtesting/run_qmt_roll_stage115_200k_granularity_safe_backtest.py`

### 我的判断

- Stage115可以作为后续20万本金研究的“安全起点”，但不应当作为正式部署版本。
- 它的价值在于：把20万最容易被忽视的单手合约粒度问题显式固化，避免高收益曲线掩盖生存约束。
- 它的短板在于：季度冷启动正收益率不够强，尤其`63d`只有`64.0000%`，说明短周期启动仍可能遇到磨损期。

### 后续规划和TODO

- 后续20万研究默认以Stage115作为小资金安全候选对照，但新alpha发现默认不要直接打开Stage115过滤池。
- 下一步优先研究：
  - 提高Stage115季度冷启动稳定性，尤其`63d`窗口
  - 对亏损季度做品种/方向/信号来源归因
  - 不新增高保证金品种，避免用收益换回不可交易风险

## 2026-04-25 12:16 第116阶段：Stage115 20万亏损冷启动窗口归因

### 本次版本改动

- 改动时间点：`2026-04-25 12:16`
- 是否是重要突破版本：否。属于诊断版本，明确Stage115弱点来源，暂不修改策略。
- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage115_200k_loss_window_attribution.py`
- 新增产物：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage115_200k_loss_window_attribution_weak_windows_stage116_stage115_200k_loss_window_attribution_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage115_200k_loss_window_attribution_product_attribution_stage116_stage115_200k_loss_window_attribution_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage115_200k_loss_window_attribution_top_loss_products_stage116_stage115_200k_loss_window_attribution_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage115_200k_loss_window_attribution_report_stage116_stage115_200k_loss_window_attribution_v1.md`
- 新增参数：
  - 模型标签：`stage116_stage115_200k_loss_window_attribution_v1`
  - 本金：`200,000`
  - 归因范围：Stage114中完整窗口且收益`<=0`的弱窗口
  - 弱窗口分类：`real_loss_window`、`mild_chop_window`、`thin_signal_friction`、`no_signal_idle`
- 修改参数：
  - 无。Stage115交易逻辑、资金约束、品种池均未修改。
- 删除参数：
  - 无。

### 新增回测结果

Stage116重跑并归因`19`个弱窗口：

| 类别 | 窗口数 | 含义 |
| --- | ---: | --- |
| `real_loss_window` | `4` | 真正亏损窗口，收益或回撤显著变差 |
| `mild_chop_window` | `7` | 轻微震荡磨损，不是结构性大亏 |
| `thin_signal_friction` | `6` | 低交易次数下的滑点/小亏损 |
| `no_signal_idle` | `2` | 无信号空窗，收益为`0` |

弱窗口品种亏损聚合：

| 品种 | 弱窗口亏损次数 | 聚合净盈亏 | 总滑点 | 总交易次数 | 最大单窗口亏损 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `fu.SHFE` | `5` | `-52,150` | `840` | `22` | `-23,590` |
| `SM.CZCE` | `5` | `-30,120` | `320` | `12` | `-14,350` |
| `rb.SHFE` | `3` | `-18,690` | `210` | `9` | `-6,230` |
| `sp.SHFE` | `4` | `-16,960` | `400` | `10` | `-4,920` |
| `SH.CZCE` | `3` | `-16,920` | `720` | `6` | `-5,640` |

### 修改的回测结果

- 无。

### 删除的回测结果

- 无。

### 验证

- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_stage115_200k_loss_window_attribution.py`
- 已完成弱窗口归因：
  - `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage115_200k_loss_window_attribution.py`

### 我的判断

- Stage115的弱窗口不是单一参数失效，更多是“低交易/震荡/空窗”导致的冷启动不稳定。
- `fu.SHFE`和`SM.CZCE`确实是弱窗口里最明显的亏损来源，但这只能说明需要消融验证，不能直接删除。
- 继续加复杂信号过滤容易过拟合；更合理的下一步是做极简产品消融，验证删除拖累品种的机会成本。

### 后续规划和TODO

- 测试`exclude_fu`与`exclude_fu_sm`两个最小消融。
- 若消融改善弱窗口但完整窗口代价过大，则不删除品种，只考虑条件性降权或冷启动节流。

## 2026-04-25 12:26 第117阶段：Stage115 20万弱窗口Top亏损品种消融

### 本次版本改动

- 改动时间点：`2026-04-25 12:26`
- 是否是重要突破版本：否。属于否定硬删除方案的验证版本。
- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage115_200k_top_loss_product_ablation.py`
- 新增产物：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage115_200k_top_loss_product_ablation_full_summary_stage117_stage115_200k_top_loss_product_ablation_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage115_200k_top_loss_product_ablation_weak_aggregate_stage117_stage115_200k_top_loss_product_ablation_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage115_200k_top_loss_product_ablation_weak_horizon_summary_stage117_stage115_200k_top_loss_product_ablation_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage115_200k_top_loss_product_ablation_report_stage117_stage115_200k_top_loss_product_ablation_v1.md`
- 新增参数：
  - 模型标签：`stage117_stage115_200k_top_loss_product_ablation_v1`
  - 消融1：`exclude_fu`，剔除`fu.SHFE`
  - 消融2：`exclude_fu_sm`，剔除`fu.SHFE,SM.CZCE`
  - 对照：`baseline_stage115`
- 修改参数：
  - 仅修改产品池，不修改交易信号、资金约束、AI过滤、相关性门控。
- 删除参数：
  - 无。

### 新增回测结果

完整窗口对比：

| 版本 | 剔除品种 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 胜率 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `baseline_stage115` | 无 | `932,280` | `366.1400%` | `-24.6971%` | `1.0501` | `53,700` | `512` | `40.3042%` |
| `exclude_fu` | `fu.SHFE` | `819,145` | `309.5725%` | `-24.6971%` | `1.0016` | `50,040` | `451` | `40.5172%` |
| `exclude_fu_sm` | `fu.SHFE,SM.CZCE` | `618,755` | `209.3775%` | `-18.9949%` | `0.8892` | `38,680` | `371` | `38.2199%` |

弱窗口聚合对比：

| 版本 | 弱窗口数 | 转正窗口数 | 转正率 | 中位收益 | 最差收益 | 平均收益 | 最差最大回撤 | 最大保证金/权益 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `baseline_stage115` | `19` | `0` | `0.0000%` | `-1.0100%` | `-5.7800%` | `-1.6526%` | `-19.0625%` | `50.4867%` |
| `exclude_fu` | `19` | `4` | `21.0526%` | `-0.9650%` | `-4.8950%` | `-0.2226%` | `-19.0246%` | `44.7737%` |
| `exclude_fu_sm` | `19` | `2` | `10.5263%` | `-0.7400%` | `-6.8300%` | `-1.5118%` | `-14.4525%` | `40.3984%` |

### 修改的回测结果

- 无。Stage117只做消融验证，不修改Stage115配置。

### 删除的回测结果

- 无。

### 验证

- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_stage115_200k_top_loss_product_ablation.py`
- 已完成完整窗口和弱窗口消融：
  - `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage115_200k_top_loss_product_ablation.py`

### 我的判断

- 不建议硬删除`fu.SHFE`。它确实改善弱窗口平均收益，但完整窗口期末权益下降`113,135`，总收益下降`56.5675`个百分点，最大回撤没有改善。
- 不建议硬删除`fu.SHFE+SM.CZCE`。虽然最大回撤从`-24.6971%`降到`-18.9949%`，但总收益从`366.1400%`降到`209.3775%`，Sharpe也降到`0.8892`，机会成本过大。
- 更本质的结论：`fu`是“高贡献但冷启动伤人”的品种，不是毒性品种；应该考虑条件性节流，而不是永久剔除。

### 后续规划和TODO

- 不把`exclude_fu`或`exclude_fu_sm`固化进Stage115。
- 下一步若继续改进，应研究`fu.SHFE`条件性降权/冷启动节流，例如只在冷启动前`126d`降低fu风险，或在fu短期亏损后临时降权。
- 所有进一步改动必须继续用20万本金、季度冷启动、完整窗口三者同时验证。

## 2026-04-25 14:00 第118阶段：Stage78 40万叠加Stage111资金约束直接验证

### 本次版本改动

- 改动时间点：`2026-04-25 14:00`
- 是否是重要突破版本：否。直接叠加能降风险，但把Stage78收益引擎压成接近Stage111的低收益版本。
- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage78_400k_stage111_margin_overlay.py`
- 新增产物：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage78_400k_stage111_margin_overlay_quarter_summary_stage118_stage78_400k_stage111_margin_overlay_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage78_400k_stage111_margin_overlay_horizon_summary_stage118_stage78_400k_stage111_margin_overlay_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage78_400k_stage111_margin_overlay_horizon_aggregate_stage118_stage78_400k_stage111_margin_overlay_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage78_400k_stage111_margin_overlay_full_comparison_stage118_stage78_400k_stage111_margin_overlay_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage78_400k_stage111_margin_overlay_report_stage118_stage78_400k_stage111_margin_overlay_v1.md`
- 新增参数：
  - 模型标签：`stage118_stage78_400k_stage111_margin_overlay_v1`
  - 本金：`400,000`
  - Stage78基础逻辑：保留`official_stage78_defensive_v1`的品种池、AI品种过滤、FU防守规则、相关性门控
  - Stage111资金约束：`max_capital_usage_ratio=0.45`
  - Stage111单笔约束：`max_single_trade_capital_usage_ratio=0.20`
  - sizing资金上限：`1,000,000`
  - 季度窗口：`63d`、`126d`、`252d`
- 修改参数：
  - 无。该阶段只做叠加研究，不修改正式策略配置。
- 删除参数：
  - 无。

### 新增回测结果

完整窗口对比：

| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 胜率 | 最大保证金/权益 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `Stage78_40w_cap2.5x参考` | `5,712,450` | `1328.1125%` | `-38.8477%` | `1.4531` | `295,970` | `820` | 不适用 | 未统计 |
| `Stage111_40w安全参考` | `2,766,945` | `591.7363%` | `-21.6475%` | `1.4757` | `118,860` | `782` | 不适用 | `51.7933%` |
| `Stage118_Stage78+Stage111约束` | `2,658,985` | `564.7462%` | `-21.6475%` | `1.4457` | `123,330` | `749` | `44.0104%` | `51.7933%` |

季度聚合结果：

| 窗口 | 正收益率 | 中位收益 | 最差收益 | 最差最大回撤 | 中位Sharpe | 最差Sharpe | 最大保证金/权益 | 保证金>80%窗口 | 保证金>100%窗口 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `63d` | `72.0000%` | `7.8250%` | `-9.4875%` | `-26.1991%` | `1.2126` | `-3.2458` | `59.9891%` | `0` | `0` |
| `126d` | `95.8333%` | `16.2956%` | `-1.4613%` | `-26.1991%` | `1.4598` | `-0.0057` | `63.3237%` | `0` | `0` |
| `252d` | `100.0000%` | `43.1344%` | `8.2700%` | `-26.1991%` | `1.4489` | `0.5357` | `63.3237%` | `0` | `0` |

### 修改的回测结果

- 无。

### 删除的回测结果

- 无。

### 验证

- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_stage78_400k_stage111_margin_overlay.py`
- 已完成40万本金季度滚动回测：
  - `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage78_400k_stage111_margin_overlay.py`

### 我的判断

- Stage111的`0.45/0.20`外壳确实能显著压低Stage78回撤和保证金风险。
- 但它也基本切掉了Stage78的收益优势：全周期收益从`1328.1125%`降到`564.7462%`，并且低于Stage111自身的`591.7363%`。
- 直接叠加不值得固化。它证明了资金约束有效，但不是Stage78和Stage111的最佳结合方式。

### 后续规划和TODO

- 不把`0.45/0.20`直接叠加固化为正式版本。
- 继续做低维资金约束曲面，验证是否存在更合理的中间档。

## 2026-04-25 14:00 第119阶段：Stage78 40万资金约束曲面验证

### 本次版本改动

- 改动时间点：`2026-04-25 14:00`
- 是否是重要突破版本：否。发现`0.60/0.30`有收益价值但季度保证金越界，`0.50/0.25`安全但优势太薄。
- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage78_400k_margin_profile_surface.py`
- 新增产物：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage78_400k_margin_profile_surface_quarter_summary_stage119_stage78_400k_margin_profile_surface_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage78_400k_margin_profile_surface_horizon_summary_stage119_stage78_400k_margin_profile_surface_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage78_400k_margin_profile_surface_horizon_aggregate_stage119_stage78_400k_margin_profile_surface_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage78_400k_margin_profile_surface_full_comparison_stage119_stage78_400k_margin_profile_surface_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage78_400k_margin_profile_surface_report_stage119_stage78_400k_margin_profile_surface_v1.md`
- 新增参数：
  - 模型标签：`stage119_stage78_400k_margin_profile_surface_v1`
  - `stage78_cap60_single30`：`max_capital_usage_ratio=0.60`，`max_single_trade_capital_usage_ratio=0.30`
  - `stage78_cap50_single25`：`max_capital_usage_ratio=0.50`，`max_single_trade_capital_usage_ratio=0.25`
  - 复用Stage118的`stage78_cap45_single20`
- 修改参数：
  - 只修改资金约束档位，不修改交易信号、品种池、AI过滤、相关性门控。
- 删除参数：
  - 无。

### 新增回测结果

完整窗口对比：

| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 胜率 | 最大保证金/权益 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `stage78_cap60_single30` | `3,789,405` | `847.3513%` | `-22.9096%` | `1.5116` | `177,210` | `776` | `42.7136%` | `72.2309%` |
| `stage78_cap50_single25` | `2,851,515` | `612.8788%` | `-23.1565%` | `1.3741` | `137,910` | `750` | `42.3377%` | `55.3008%` |
| `stage78_cap45_single20` | `2,658,985` | `564.7462%` | `-21.6475%` | `1.4457` | `123,330` | `749` | `44.0104%` | `51.7933%` |

季度聚合结果：

| 版本 | 窗口 | 正收益率 | 中位收益 | 最差收益 | 最差最大回撤 | 最大保证金/权益 | 保证金>80%窗口 | 保证金>100%窗口 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `stage78_cap60_single30` | `63d` | `76.0000%` | `11.7213%` | `-10.1900%` | `-32.7572%` | `103.0240%` | `6` | `1` |
| `stage78_cap60_single30` | `126d` | `95.8333%` | `29.3694%` | `-4.4838%` | `-32.7572%` | `103.0240%` | `8` | `1` |
| `stage78_cap60_single30` | `252d` | `100.0000%` | `83.0163%` | `12.1475%` | `-32.7572%` | `103.0240%` | `7` | `1` |
| `stage78_cap50_single25` | `63d` | `72.0000%` | `9.2750%` | `-11.4900%` | `-29.0256%` | `74.1755%` | `0` | `0` |
| `stage78_cap50_single25` | `126d` | `95.8333%` | `17.2419%` | `-1.3088%` | `-29.0256%` | `74.1755%` | `0` | `0` |
| `stage78_cap50_single25` | `252d` | `100.0000%` | `44.3019%` | `9.1913%` | `-29.0256%` | `74.1755%` | `0` | `0` |

### 修改的回测结果

- 无。

### 删除的回测结果

- 无。

### 验证

- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_stage78_400k_margin_profile_surface.py`
- 已完成40万本金资金约束曲面回测：
  - `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage78_400k_margin_profile_surface.py`

### 我的判断

- `0.60/0.30`的收益和Sharpe有吸引力，但季度冷启动最大保证金/权益达到`103.0240%`，已经突破实盘安全边界，不能固化。
- `0.50/0.25`安全，但相对Stage111只多`21.1425`个百分点总收益，Sharpe反而更低，不构成有价值的正式替代。
- Stage119说明问题不只是“Stage111约束太硬”，还需要拆分总约束和单笔约束。

### 后续规划和TODO

- 继续做总资金约束和单笔约束拆分实验。
- 原则上不做大网格搜索，只验证结构性档位，避免资金规则过拟合。

## 2026-04-25 14:00 第120阶段：Stage78 40万总约束和单笔约束拆分验证

### 本次版本改动

- 改动时间点：`2026-04-25 14:00`
- 是否是重要突破版本：是，研究层面的结构突破，但不是正式固化版本。发现`0.55/0.25`是目前Stage78和Stage111最有结合价值的中间候选。
- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage78_400k_decoupled_margin_surface.py`
- 新增产物：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage78_400k_decoupled_margin_surface_quarter_summary_stage120_stage78_400k_decoupled_margin_surface_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage78_400k_decoupled_margin_surface_horizon_summary_stage120_stage78_400k_decoupled_margin_surface_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage78_400k_decoupled_margin_surface_horizon_aggregate_stage120_stage78_400k_decoupled_margin_surface_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage78_400k_decoupled_margin_surface_full_comparison_stage120_stage78_400k_decoupled_margin_surface_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage78_400k_decoupled_margin_surface_report_stage120_stage78_400k_decoupled_margin_surface_v1.md`
- 新增参数：
  - 模型标签：`stage120_stage78_400k_decoupled_margin_surface_v1`
  - `stage78_cap55_single25`：`max_capital_usage_ratio=0.55`，`max_single_trade_capital_usage_ratio=0.25`
  - `stage78_cap60_single25`：`max_capital_usage_ratio=0.60`，`max_single_trade_capital_usage_ratio=0.25`
- 修改参数：
  - 只拆分总资金约束和单笔约束，不修改Stage78交易逻辑。
- 删除参数：
  - 无。

### 新增回测结果

完整窗口对比：

| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 胜率 | 最大保证金/权益 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `stage78_cap60_single25` | `3,662,100` | `815.5250%` | `-23.0316%` | `1.5104` | `171,410` | `778` | `42.8571%` | `71.5269%` |
| `stage78_cap55_single25` | `3,333,745` | `733.4363%` | `-24.1170%` | `1.4832` | `151,290` | `754` | `42.4870%` | `67.6146%` |

横向关键对照：

| 版本 | 总收益 | 最大回撤 | Sharpe | 季度最大保证金/权益 | 季度保证金>80%窗口 | 判断 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `Stage111_40w安全参考` | `591.7363%` | `-21.6475%` | `1.4757` | `63.3237%` | `0` | 更稳但收益低 |
| `stage78_cap50_single25` | `612.8788%` | `-23.1565%` | `1.3741` | `74.1755%` | `0` | 安全但优势薄 |
| `stage78_cap55_single25` | `733.4363%` | `-24.1170%` | `1.4832` | `79.9596%` | `0` | 当前最有研究价值 |
| `stage78_cap60_single25` | `815.5250%` | `-23.0316%` | `1.5104` | `92.2344%` | `7` | 收益好但保证金越界 |
| `stage78_cap60_single30` | `847.3513%` | `-22.9096%` | `1.5116` | `103.0240%` | `8` | 不可部署 |

`stage78_cap55_single25`季度聚合：

| 窗口 | 正收益率 | 中位收益 | 最差收益 | 最差最大回撤 | 中位Sharpe | 最差Sharpe | 最大保证金/权益 | 保证金>80%窗口 | 保证金>100%窗口 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `63d` | `80.0000%` | `10.2300%` | `-8.8925%` | `-29.5107%` | `1.2936` | `-2.9443` | `79.9596%` | `0` | `0` |
| `126d` | `91.6667%` | `26.0075%` | `-2.8000%` | `-30.0743%` | `1.8046` | `-0.0372` | `79.9596%` | `0` | `0` |
| `252d` | `100.0000%` | `63.3313%` | `10.4538%` | `-30.0743%` | `1.7080` | `0.5022` | `79.9596%` | `0` | `0` |

`stage78_cap55_single25`脆弱窗口：

| 窗口 | 63d收益 | 63d最大回撤 | 最大保证金/权益 |
| --- | ---: | ---: | ---: |
| `q2020_1` | `-8.8925%` | `-11.1276%` | `32.4030%` |
| `q2024_2` | `-6.1275%` | `-21.0907%` | `43.9658%` |
| `q2022_2` | `-4.2100%` | `-5.4343%` | `22.6320%` |

### 修改的回测结果

- 无。

### 删除的回测结果

- 无。

### 验证

- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_stage78_400k_decoupled_margin_surface.py`
- 已完成40万本金拆分资金约束回测：
  - `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage78_400k_decoupled_margin_surface.py`

### 我的判断

- Stage78和Stage111有结合价值，但不是直接套`0.45/0.20`。更合理的结构是保留Stage78收益引擎，同时用更严格的单笔约束控制合约粒度，再适度放宽总资金约束。
- `stage78_cap55_single25`是当前最有研究价值的中间候选：总收益比Stage111高`141.7000`个百分点，Sharpe略高于Stage111，季度`63d`正收益率从Stage111的`72.0000%`提高到`80.0000%`，且无保证金`>80%`窗口。
- 但它不能直接固化为正式版本，因为季度最大保证金/权益为`79.9596%`，距离`80%`红线只有`0.0404`个百分点，安全边际过薄。实盘保证金比例、滑点、跳空或主力切换误差都可能让它越线。
- `stage78_cap60_single25`说明单笔约束从`0.30`降到`0.25`仍不能解决总仓位越界，风险源主要是多品种并发，而不是单笔过大。

### 后续规划和TODO

- 不立即固化`stage78_cap55_single25`。
- 下一步应对`stage78_cap55_single25`做安全边际验证：保证金比例上浮、滑点上浮、弱窗口压力、起始年份压力。
- 如果压力测试后仍稳，可以把它作为Stage78和Stage111结合线的候选版本；如果一加压力就破`80%`，则回退到`stage78_cap50_single25`或继续保持Stage111作为40万安全基准。

## 2026-04-25 14:12 第121阶段：Stage120候选安全边际审计

### 本次版本改动

- 改动时间点：`2026-04-25 14:12`
- 是否是重要突破版本：否。该阶段否定`stage78_cap55_single25`直接固化，确认它是贴线候选而非正式版本。
- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage78_400k_cap55_safety_margin_audit.py`
- 新增产物：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage78_cap55_single25_safety_margin_audit_margin_stress_stage121_stage78_cap55_single25_safety_margin_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage78_cap55_single25_safety_margin_audit_equity_haircut_stage121_stage78_cap55_single25_safety_margin_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage78_cap55_single25_safety_margin_audit_slippage_stress_stage121_stage78_cap55_single25_safety_margin_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage78_cap55_single25_safety_margin_audit_report_stage121_stage78_cap55_single25_safety_margin_audit_v1.md`
- 新增参数：
  - 审计对象：`stage78_cap55_single25`
  - 保证金红线：`80.0000%`
  - 保证金上浮倍数：`1.001`、`1.005`、`1.010`、`1.030`、`1.050`、`1.100`
  - 权益误差：`0.1%`、`0.5%`、`1.0%`、`3.0%`、`5.0%`、`10.0%`
  - 滑点倍数：`1.0`、`1.5`、`2.0`、`3.0`
- 修改参数：
  - 无。该阶段不改交易逻辑，不新增交易回测，只对Stage120结果做压力审计。
- 删除参数：
  - 无。

### 新增回测结果

- 无新增交易回测。本阶段是基于Stage120输出的安全边际审计。

### 新增压力审计结果

`stage78_cap55_single25`基准完整窗口：

| 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 胜率 | 完整窗口最大保证金/权益 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `3,333,745` | `733.4363%` | `-24.1170%` | `1.4832` | `151,290` | `754` | `42.4870%` | `67.6146%` |

保证金安全边际：

| 窗口 | 基准最大保证金/权益 | 到80%缓冲 | 相对缓冲 | 0.1%保证金上浮后 | 是否破80% |
| --- | ---: | ---: | ---: | ---: | ---: |
| `63d` | `79.9596%` | `0.0404`个百分点 | `0.0505%` | `80.0396%` | 是 |
| `126d` | `79.9596%` | `0.0404`个百分点 | `0.0505%` | `80.0396%` | 是 |
| `252d` | `79.9596%` | `0.0404`个百分点 | `0.0505%` | `80.0396%` | 是 |

权益误差压力：

| 窗口 | 基准最大保证金/权益 | 0.1%权益误差后 | 是否破80% |
| --- | ---: | ---: | ---: |
| `63d` | `79.9596%` | `80.0397%` | 是 |
| `126d` | `79.9596%` | `80.0397%` | 是 |
| `252d` | `79.9596%` | `80.0397%` | 是 |

滑点压力：

| 滑点倍数 | 63d正收益率 | 63d中位收益 | 63d最差收益 | 126d正收益率 | 252d正收益率 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| `1.0` | `80.0000%` | `10.2300%` | `-8.8925%` | `91.6667%` | `100.0000%` |
| `1.5` | `80.0000%` | `10.0525%` | `-9.4900%` | `91.6667%` | `100.0000%` |
| `2.0` | `76.0000%` | `9.7950%` | `-10.0875%` | `91.6667%` | `100.0000%` |
| `3.0` | `76.0000%` | `9.2800%` | `-11.2825%` | `91.6667%` | `100.0000%` |

### 修改的回测结果

- 无。

### 删除的回测结果

- 无。

### 验证

- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_stage78_400k_cap55_safety_margin_audit.py`
- 已完成安全边际审计：
  - `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage78_400k_cap55_safety_margin_audit.py`

### 我的判断

- `stage78_cap55_single25`不是收益端的问题，滑点加倍后仍有一定韧性。
- 它的问题是保证金安全边际几乎为零：只要保证金比例上浮`0.1%`，或权益低估/实际亏损偏差`0.1%`，季度最大保证金/权益就从`79.9596%`越过`80%`。
- 因此它不能作为正式版本固化。它是一个有价值的研究信号，说明Stage78和Stage111确实可以结合，但正式候选应当带更厚安全垫。

### 后续规划和TODO

- 不固化`stage78_cap55_single25`。
- 下一步更合理的是检查`stage78_cap50_single25`是否能作为保守正式候选，或者寻找不靠贴近80%红线的结构性收益来源。
- 如果继续沿Stage78+Stage111方向，优先研究“降低并发但不降低单笔质量”的规则，而不是继续调`0.55`附近的小数。

## 2026-04-25 14:17 第122阶段：Stage78 cap50/single25保守正式候选审计

### 本次版本改动

- 改动时间点：`2026-04-25 14:17`
- 是否是重要突破版本：否。确认`stage78_cap50_single25`安全垫充足，但不具备替代Stage111的正式候选资格。
- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage78_400k_cap50_formal_candidate_audit.py`
- 新增产物：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage78_cap50_single25_formal_candidate_audit_full_selected_stage122_stage78_cap50_single25_formal_candidate_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage78_cap50_single25_formal_candidate_audit_horizon_selected_stage122_stage78_cap50_single25_formal_candidate_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage78_cap50_single25_formal_candidate_audit_safety_stress_stage122_stage78_cap50_single25_formal_candidate_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage78_cap50_single25_formal_candidate_audit_slippage_stress_stage122_stage78_cap50_single25_formal_candidate_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage78_cap50_single25_formal_candidate_audit_gate_decision_stage122_stage78_cap50_single25_formal_candidate_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage78_cap50_single25_formal_candidate_audit_report_stage122_stage78_cap50_single25_formal_candidate_audit_v1.md`
- 新增参数：
  - 审计对象：`stage78_cap50_single25`
  - 正式候选门槛：
    - `margin_safety_buffer`：5%保证金上浮和5%权益误差后仍不破`80%`
    - `full_return_premium_vs_stage111`：相对Stage111总收益至少高`100`个百分点
    - `sharpe_not_worse_than_stage111`：Sharpe不低于Stage111
    - `short_window_not_worse_than_stage111`：短窗口正收益率和最差收益不弱于Stage111
  - 滑点倍数：`1.0`、`1.5`、`2.0`、`3.0`
- 修改参数：
  - 无。该阶段不改交易逻辑，不新增交易回测，只审计Stage119结果。
- 删除参数：
  - 无。

### 新增回测结果

- 无新增交易回测。本阶段基于Stage119和Stage120输出做正式候选审计。

### 新增审计结果

完整窗口对比：

| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 胜率 | 最大保证金/权益 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `Stage111_40w安全参考` | `2,766,945` | `591.7363%` | `-21.6475%` | `1.4757` | `118,860` | `782` | 不适用 | `51.7933%` |
| `stage78_cap50_single25` | `2,851,515` | `612.8788%` | `-23.1565%` | `1.3741` | `137,910` | `750` | `42.3377%` | `55.3008%` |
| `stage78_cap55_single25` | `3,333,745` | `733.4363%` | `-24.1170%` | `1.4832` | `151,290` | `754` | `42.4870%` | `67.6146%` |

`stage78_cap50_single25`季度聚合：

| 窗口 | 正收益率 | 中位收益 | 最差收益 | 最差最大回撤 | 最大保证金/权益 | 保证金>80%窗口 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `63d` | `72.0000%` | `9.2750%` | `-11.4900%` | `-29.0256%` | `74.1755%` | `0` |
| `126d` | `95.8333%` | `17.2419%` | `-1.3088%` | `-29.0256%` | `74.1755%` | `0` |
| `252d` | `100.0000%` | `44.3019%` | `9.1913%` | `-29.0256%` | `74.1755%` | `0` |

安全边际：

| 压力 | 压力后最大保证金/权益 | 是否破80% |
| --- | ---: | ---: |
| `5%保证金上浮` | `77.8843%` | 否 |
| `5%权益误差` | `78.0795%` | 否 |
| `10%保证金上浮` | `81.5931%` | 是 |
| `10%权益误差` | `82.4172%` | 是 |

滑点压力：

| 滑点倍数 | 63d正收益率 | 63d中位收益 | 63d最差收益 | 126d正收益率 | 252d正收益率 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| `1.0` | `72.0000%` | `9.2750%` | `-11.4900%` | `95.8333%` | `100.0000%` |
| `1.5` | `72.0000%` | `9.0613%` | `-12.1638%` | `95.8333%` | `100.0000%` |
| `2.0` | `72.0000%` | `8.8288%` | `-12.8375%` | `95.8333%` | `100.0000%` |
| `3.0` | `72.0000%` | `8.3638%` | `-14.1850%` | `95.8333%` | `100.0000%` |

正式候选门槛：

| 门槛 | 是否通过 | 数值 | 阈值 |
| --- | ---: | ---: | ---: |
| `margin_safety_buffer` | 是 | `78.0795%` | `80.0000%` |
| `full_return_premium_vs_stage111` | 否 | `21.1425`个百分点 | `100.0000`个百分点 |
| `sharpe_not_worse_than_stage111` | 否 | `-0.1016` | `0.0000` |
| `short_window_not_worse_than_stage111` | 否 | `-2.0025`个百分点 | `0.0000` |
| `formal_candidate` | 否 | `1/4`通过 | `4/4` |

### 修改的回测结果

- 无。

### 删除的回测结果

- 无。

### 验证

- 已通过语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_stage78_400k_cap50_formal_candidate_audit.py`
- 已完成正式候选审计：
  - `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage78_400k_cap50_formal_candidate_audit.py`

### 我的判断

- `stage78_cap50_single25`的价值是安全垫：5%保证金上浮和5%权益误差后仍不破`80%`。
- 但它不值得替代Stage111：总收益只高`21.1425`个百分点，Sharpe低`0.1016`，63d最差收益比Stage111差`2.0025`个百分点。
- 因此它可以作为保守研究对照或安全下沿，但不能作为正式版本固化。

### 后续规划和TODO

- 不固化`stage78_cap50_single25`。
- Stage78+Stage111的简单资金约束路线暂时没有正式候选：`0.55/0.25`收益够但贴线，`0.50/0.25`安全但没优势。
- 下一步如果继续该方向，应做“降低并发但不降低单笔质量”的结构性规则，而不是继续调资金比例。

## 2026-04-25 14:26 第123阶段：官方Stage78完整窗口复现和看板生成

### 本次版本改动

- 改动时间点：`2026-04-25 14:26`
- 是否是重要突破版本：否。该阶段是冻结版本复现和图表生成，不是新策略。
- 过拟合反思：
  - 本次只复现`official_stage78_defensive_v1`，没有调参，没有基于结果新增规则，因此新增过拟合风险低。
  - 但如果后续根据资金曲线某几段走势反推规则，必须重新做多周期验证，否则容易变成曲线解释型过拟合。
- 运行脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_official_stage78_backtest.py`
- 新增或覆盖产物：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_defensive_formal_chart.html`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_defensive_formal_professional_dashboard.html`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_defensive_formal_trade_review.html`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_defensive_formal_daily.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_defensive_formal_daily_equity.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_defensive_formal_trades_2020_2026_04.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_defensive_formal_statistics.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_defensive_summary.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_official_stage78_defensive_summary.json`
- 新增参数：
  - 无。
- 修改参数：
  - 无。使用官方Stage78冻结配置。
- 删除参数：
  - 无。

### 新增回测结果

官方Stage78完整窗口复现：

| 版本 | 本金 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 胜率 | 盈利日 | 亏损日 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `official_stage78_defensive_v1` | `200,000` | `4,600,090` | `2200.0450%` | `-36.9907%` | `1.2919` | `260,110` | `779` | `42.1053%` | `583` | `621` |

### 修改的回测结果

- 覆盖刷新了官方Stage78图表、看板、交易复盘和summary产物。

### 删除的回测结果

- 无。

### 验证

- 已完成官方Stage78完整窗口回测：
  - `.py311/bin/python examples/portfolio_backtesting/run_qmt_roll_official_stage78_backtest.py`
- 生成了资金曲线图：
  - `qmt_roll_official_stage78_defensive_formal_chart.html`
- 生成了专业看板：
  - `qmt_roll_official_stage78_defensive_formal_professional_dashboard.html`
- 生成了交易复盘：
  - `qmt_roll_official_stage78_defensive_formal_trade_review.html`

### 我的判断

- 复现结果与官方Stage78冻结指标一致，可以用于观察资金曲线形态。
- 这条资金曲线的核心特征是收益很强，但最大回撤也明显，符合之前对Stage78“收益引擎强、资金约束不足”的判断。
- 看图时应重点看回撤段的速度和恢复时间，而不是只看最终收益。

### 后续规划和TODO

- 用户可先查看专业看板和交易复盘。
- 如果继续研究Stage78曲线形态，建议下一步做“回撤段归因”，拆分最大回撤来自哪些品种、方向、并发状态，而不是直接改参数。

## 2026-04-25 14:36 第124阶段：Stage78并发和单笔质量归因

### 本次版本改动

- 改动时间点：`2026-04-25 14:36`
- 是否是重要突破版本：否。该阶段是归因研究，不是交易规则变更。
- 过拟合反思：
  - 本次没有调参，没有新增开仓/过滤规则，只分析官方Stage78已有交易和候选快照，因此新增过拟合风险低。
  - 如果直接用`active>=6_ai_rank>8`这类样本只有`3`笔的条件做过滤，会明显过拟合；本阶段结论不能这样使用。
- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage78_concurrency_quality_attribution.py`
- 新增产物：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage78_concurrency_quality_attribution_report_stage124_stage78_concurrency_quality_attribution_v1.md`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage78_concurrency_quality_attribution_summary_stage124_stage78_concurrency_quality_attribution_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage78_concurrency_quality_attribution_daily_bucket_summary_stage124_stage78_concurrency_quality_attribution_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage78_concurrency_quality_attribution_entry_quality_by_active_before_stage124_stage78_concurrency_quality_attribution_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage78_concurrency_quality_attribution_hypothesis_block_summary_stage124_stage78_concurrency_quality_attribution_v1.csv`
- 新增参数：
  - 无。
- 修改参数：
  - 无。
- 删除参数：
  - 无。

### 新增回测结果

- 本阶段没有新增交易回测，基于官方Stage78复现结果做归因。
- 参考基准仍为官方Stage78：
  - 期末权益：`4,600,090`
  - 总收益：`2200.0450%`
  - 最大回撤：`-36.9907%`
  - Sharpe：`1.2919`
  - 总滑点：`260,110`
  - 总交易次数：`779`
  - 胜率：`42.1053%`

### 归因结果

| 并发桶 | 天数 | 总净利润 | 中位日收益 | 亏损日比例 | 最大保证金/权益 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `0` | `397` | `-76,360` | `0.0000%` | `21.1587%` | `0.0000%` |
| `1-2` | `792` | `1,453,255` | `0.0002%` | `48.9899%` | `70.5079%` |
| `3-4` | `262` | `1,995,585` | `0.1463%` | `45.4198%` | `90.8795%` |
| `5-6` | `59` | `815,350` | `0.7929%` | `40.6780%` | `100.1081%` |
| `7+` | `15` | `212,260` | `1.9977%` | `40.0000%` | `112.1465%` |

候选阻断假设：

| 假设 | 阻断笔数 | 20日后续净利润 | 20日正收益率 | 63日后续净利润 | 63日正收益率 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `active>=6_ai_rank>8` | `3` | `-6,320` | `33.3333%` | `62,550` | `66.6667%` |
| `active>=6_corr>0.6` | `3` | `8,260` | `66.6667%` | `357,110` | `100.0000%` |

### 修改的回测结果

- 无。

### 删除的回测结果

- 无。

### 验证

- 已完成语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_stage78_concurrency_quality_attribution.py`
- 已完成归因运行：
  - `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage78_concurrency_quality_attribution.py`

### 我的判断

- 高并发不是天然坏事，Stage78的高并发区间反而贡献了大量利润。
- 不能做简单`max_position`砍并发，也不能按少量样本的AI rank/corr阈值过滤。
- 真正值得研究的是结构性规则：在新增候选进入时按组合保证金预算顺序消耗，预算满了跳过后面的增量交易，而不是缩小前面高优先级交易。

### 后续规划和TODO

- 进入Stage125：做“增量保证金预算门槛”试验。
- 判断标准：
  - 是否压低最大保证金/权益；
  - 是否尽量保留Stage78收益引擎；
  - 是否主要阻断排序靠后的拥挤交易，而不是阻断前排高质量交易。

## 2026-04-25 14:44 第125阶段：增量保证金预算门槛试验

### 本次版本改动

- 改动时间点：`2026-04-25 14:44`
- 是否是重要突破版本：否。该阶段验证了方向有风险治理价值，但收益/Sharpe下降，暂不适合固化为正式版本。
- 过拟合反思：
  - 本次规则没有用未来收益、亏损日期或品种名单作为条件，只使用同日候选按排序顺序消耗新增保证金预算，属于结构性约束，过拟合风险低于结果型过滤。
  - 但`0.80`和`0.90`仍是人为阈值，且`gate80`已开始阻断`selection_pairwise_rank=1`的前排候选，继续围绕小数调阈值会过拟合。
- 修改代码：
  - `examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage125_incremental_margin_budget_gate.py`
- 新增产物：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage125_incremental_margin_budget_gate_summary_stage125_incremental_margin_budget_gate_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage125_incremental_margin_budget_gate_candidate_summary_stage125_incremental_margin_budget_gate_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage125_incremental_margin_budget_gate_blocked_candidates_stage125_incremental_margin_budget_gate_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage125_incremental_margin_budget_gate_summary_stage125_incremental_margin_budget_gate_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage125_incremental_margin_budget_gate_report_stage125_incremental_margin_budget_gate_v1.md`
- 新增参数：
  - `enable_incremental_margin_budget_gate`：默认`False`，开启后只对`flat_entry`候选生效。
  - `incremental_margin_budget_gate_usage_ratio`：默认`-1.0`，小于等于0时沿用当前有效资金使用率；大于0时作为新增候选顺序预算上限。
- 修改参数：
  - 无正式默认参数修改，新增开关默认关闭。
- 删除参数：
  - 无。

### 新增回测结果

| 版本 | 本金 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 胜率 | 最大保证金/权益 | 大于80%天数 | 大于100%天数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `official_stage78_reference` | `200,000` | `4,600,090` | `2200.0450%` | `-36.9907%` | `1.2919` | `260,110` | `779` | `42.1053%` | `112.1465%` | `11` | `3` |
| `stage78_incremental_gate90` | `200,000` | `4,284,020` | `2042.0100%` | `-36.2855%` | `1.2676` | `254,020` | `794` | `42.9975%` | `89.6254%` | `5` | `0` |
| `stage78_incremental_gate80` | `200,000` | `3,185,330` | `1492.6650%` | `-37.1814%` | `1.2244` | `225,200` | `770` | `42.7848%` | `77.3069%` | `0` | `0` |

候选拦截归因：

| 版本 | flat候选数 | 开仓数 | 增量门槛拦截 | 并发上限拦截 | 开仓中位rank | 拦截中位rank | 开仓中位AI rank | 拦截中位AI rank |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `stage78_incremental_gate90` | `1,082` | `373` | `7` | `4` | `1.0000` | `2.0000` | `6.0000` | `3.0000` |
| `stage78_incremental_gate80` | `1,083` | `361` | `20` | `4` | `1.0000` | `1.0000` | `6.0000` | `6.0000` |

### 修改的回测结果

- 无正式版本结果修改。本阶段为研究分支候选结果。

### 删除的回测结果

- 无。

### 验证

- 已完成语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py examples/portfolio_backtesting/analyze_qmt_roll_stage125_incremental_margin_budget_gate.py`
- 已完成Stage125回测：
  - `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage125_incremental_margin_budget_gate.py`

### 我的判断

- `gate90`有价值：最大保证金/权益从`112.1465%`降到`89.6254%`，且最大回撤略改善到`-36.2855%`，说明“同日增量保证金预算”确实抓到了部分拥挤风险。
- `gate90`不足以成为正式突破：期末权益少`316,070`，总收益少`158.035`个百分点，Sharpe从`1.2919`降到`1.2676`。
- `gate80`不值得继续作为主线：虽然保证金压到`77.3069%`，但总收益大幅降到`1492.6650%`，且已经拦截中位rank=`1`的前排候选，过度风控迹象明显。
- 这个方向应保留为“风险外壳工具”，暂不固化为正式策略默认开关。

### 后续规划和TODO

- 不继续围绕`0.80/0.90`做小数调参。
- 下一步如果继续本方向，应做更本质的版本：
  - 只在保证金已经接近危险区且同日候选数大于1时启用；
  - 或者只阻断同日排序靠后的候选，明确保护rank=1候选；
  - 或者把门槛改成“尖峰保护”而不是常态预算上限。

## 2026-04-25 14:54 第126阶段：rank=1保护的尖峰保证金保护试验

### 本次版本改动

- 改动时间点：`2026-04-25 14:54`
- 是否是重要突破版本：否。该阶段证明`rank=1保护`能修复`gate80`过度风控，但没有形成优于`gate90`或Stage78的正式候选。
- 运行前过拟合反思：
  - 判断：否。
  - 原因：本次只测试两个先验结构版本，规则来自Stage125暴露的“gate80拦截rank=1前排候选”问题，不使用具体亏损日期、品种名单或未来收益做条件。
  - 风险点：如果继续按结果寻找`0.83`、`0.87`这类最优小数，会转为过拟合。
- 运行后过拟合反思：
  - 判断：否，但不应继续微调。
  - 原因：`rank=1保护`改善了`gate80`，说明机制判断成立；但结果没有超过`gate90`，继续细调阈值的边际价值低且过拟合风险上升。
- 修改代码：
  - `examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage126_peak_margin_guard.py`
- 新增产物：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage126_peak_margin_guard_summary_stage126_peak_margin_guard_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage126_peak_margin_guard_candidate_summary_stage126_peak_margin_guard_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage126_peak_margin_guard_blocked_candidates_stage126_peak_margin_guard_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage126_peak_margin_guard_summary_stage126_peak_margin_guard_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage126_peak_margin_guard_report_stage126_peak_margin_guard_v1.md`
- 新增参数：
  - `incremental_margin_budget_gate_min_openable_candidates`：默认`1`，用于要求同日可开候选数达到指定数量才启用增量保证金门槛。
  - `incremental_margin_budget_gate_protected_selection_rank`：默认`0`，大于0时保护排序不高于该rank的候选不被增量保证金门槛拦截。
- 修改参数：
  - 无正式默认参数修改，新增开关和参数默认不改变原策略行为。
- 删除参数：
  - 无。

### 新增回测结果

| 版本 | 本金 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 胜率 | 最大保证金/权益 | 大于80%天数 | 大于100%天数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `official_stage78_reference` | `200,000` | `4,600,090` | `2200.0450%` | `-36.9907%` | `1.2919` | `260,110` | `779` | `42.1053%` | `112.1465%` | `11` | `3` |
| `stage78_peak_guard90_rank1` | `200,000` | `4,284,020` | `2042.0100%` | `-36.2855%` | `1.2676` | `254,020` | `794` | `42.9975%` | `89.6254%` | `5` | `0` |
| `stage78_peak_guard80_rank1` | `200,000` | `4,258,605` | `2029.3025%` | `-36.1518%` | `1.2629` | `253,300` | `792` | `42.6108%` | `90.1636%` | `3` | `0` |

候选拦截归因：

| 版本 | flat候选数 | 开仓数 | 增量门槛拦截 | rank保护数 | 超预算但被rank保护 | 开仓中位rank | 拦截中位rank |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `stage78_peak_guard90_rank1` | `1,082` | `373` | `7` | `337` | `0` | `1.0000` | `2.0000` |
| `stage78_peak_guard80_rank1` | `1,082` | `372` | `8` | `336` | `14` | `1.0000` | `2.0000` |

### 修改的回测结果

- 无正式版本结果修改。本阶段为研究分支候选结果。

### 删除的回测结果

- 无。

### 验证

- 已完成语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py examples/portfolio_backtesting/analyze_qmt_roll_stage126_peak_margin_guard.py`
- 已完成Stage126回测：
  - `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage126_peak_margin_guard.py`

### 我的判断

- `rank=1保护`是正确的结构约束：`gate80`原始版本总收益只有`1492.6650%`，加rank=1保护后恢复到`2029.3025%`，说明前排候选不能被机械预算拦截。
- 但Stage126不是突破：`peak_guard80_rank1`收益、Sharpe仍低于`peak_guard90_rank1`，且最大保证金/权益略高到`90.1636%`。
- `peak_guard90_rank1`与Stage125的`gate90`结果相同，说明`gate90`原本就没有拦截rank=1候选。
- 这个方向的结论是：可保留机制，但不应继续围绕阈值做优化；正式策略仍不应默认开启。

### 后续规划和TODO

- 停止“增量保证金预算/尖峰保护”的阈值微调。
- 如果未来要用，只把它作为风控外壳或压力测试开关，而不是收益增强模块。
- 下一步更有价值的方向应回到收益来源本身：
  - 做Stage78主要利润段和主要回撤段的品种/方向/信号归因；
  - 或者做“持仓期内减风险”而不是“开仓时拦截”，看能否减少回撤而少牺牲趋势启动收益。

## 2026-04-25 15:02 第127阶段：Stage78利润段和回撤段归因

### 本次版本改动

- 改动时间点：`2026-04-25 15:02`
- 是否是重要突破版本：否。该阶段是归因研究，不是新交易规则。
- 运行前过拟合反思：
  - 判断：否。
  - 原因：本阶段只读取官方Stage78已有日度、持仓、候选快照做归因，不修改策略，不使用未来收益生成规则。
  - 风险点：如果后续直接按单个亏损品种做黑名单，会变成过拟合。
- 运行后过拟合反思：
  - 判断：否。
  - 原因：输出只是解释利润和回撤来源；我已修正回撤归因口径，回撤拆解以“高点到谷底”阶段为主，而不是完整恢复周期，避免统计口径误导。
- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage127_stage78_profit_drawdown_attribution.py`
- 新增产物：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage127_stage78_profit_drawdown_attribution_drawdown_episode_summary_stage127_stage78_profit_drawdown_attribution_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage127_stage78_profit_drawdown_attribution_profit_window_summary_stage127_stage78_profit_drawdown_attribution_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage127_stage78_profit_drawdown_attribution_segment_product_attribution_stage127_stage78_profit_drawdown_attribution_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage127_stage78_profit_drawdown_attribution_segment_direction_attribution_stage127_stage78_profit_drawdown_attribution_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage127_stage78_profit_drawdown_attribution_segment_entry_signal_attribution_stage127_stage78_profit_drawdown_attribution_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage127_stage78_profit_drawdown_attribution_full_product_attribution_stage127_stage78_profit_drawdown_attribution_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage127_stage78_profit_drawdown_attribution_full_direction_attribution_stage127_stage78_profit_drawdown_attribution_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage127_stage78_profit_drawdown_attribution_summary_stage127_stage78_profit_drawdown_attribution_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage127_stage78_profit_drawdown_attribution_report_stage127_stage78_profit_drawdown_attribution_v1.md`
- 新增参数：
  - 无。
- 修改参数：
  - 无。
- 删除参数：
  - 无。

### 新增回测结果

- 本阶段没有新增交易回测，基于官方Stage78复现结果做归因。
- 参考基准仍为官方Stage78：
  - 期末权益：`4,600,090`
  - 总收益：`2200.0450%`
  - 最大回撤：`-36.9907%`
  - Sharpe：`1.2919`
  - 总滑点：`260,110`
  - 总交易次数：`779`
  - 胜率：`42.1053%`

### 归因结果

最差回撤段：

| 回撤段 | 起点 | 谷底 | 恢复/结束 | 谷底亏损 | 最大回撤 | 交易次数 |
| --- | --- | --- | --- | ---: | ---: | ---: |
| `dd_14` | `2021-05-12` | `2021-07-02` | `2021-09-15` | `-463,930` | `-36.9907%` | `62` |
| `dd_02` | `2020-01-08` | `2020-04-14` | `2020-07-13` | `-66,130` | `-31.5415%` | `60` |
| `dd_07` | `2020-09-02` | `2020-11-03` | `2020-12-02` | `-104,025` | `-27.3927%` | `33` |
| `dd_18` | `2021-11-18` | `2022-02-11` | `2022-03-03` | `-360,285` | `-21.9519%` | `57` |
| `dd_11` | `2020-12-21` | `2021-02-10` | `2021-02-22` | `-107,335` | `-21.8176%` | `25` |

非重叠20日利润窗口：

| 利润窗口 | 起点 | 终点 | 20日净利润 | 起点权益收益率 | 交易次数 |
| --- | --- | --- | ---: | ---: | ---: |
| `profit20_01` | `2025-06-30` | `2025-07-25` | `1,248,520` | `36.8398%` | `12` |
| `profit20_02` | `2021-08-25` | `2021-09-23` | `724,450` | `90.7031%` | `9` |
| `profit20_03` | `2021-04-12` | `2021-05-12` | `662,890` | `112.6081%` | `18` |
| `profit20_04` | `2022-02-10` | `2022-03-09` | `640,350` | `47.3817%` | `12` |
| `profit20_05` | `2024-03-06` | `2024-04-02` | `510,570` | `21.3685%` | `11` |

全周期品种贡献：

| 类型 | 品种 | 净利润 | 交易次数 | 滑点 |
| --- | --- | ---: | ---: | ---: |
| 最大赢家 | `jm.DCE` | `1,140,930` | `55` | `29,400` |
| 最大赢家 | `FG.CZCE` | `744,060` | `56` | `28,840` |
| 最大赢家 | `OI.CZCE` | `503,740` | `32` | `3,320` |
| 最大赢家 | `AP.CZCE` | `462,240` | `38` | `3,500` |
| 最大赢家 | `fu.SHFE` | `414,710` | `71` | `31,160` |
| 最大亏损 | `MA.CZCE` | `-141,160` | `57` | `16,250` |
| 最大亏损 | `SH.CZCE` | `-117,660` | `14` | `7,140` |
| 最大亏损 | `ru.SHFE` | `-70,650` | `50` | `18,900` |
| 最大亏损 | `cu.SHFE` | `-27,800` | `50` | `7,300` |

方向归因：

| 口径 | 多头净利润 | 空头净利润 |
| --- | ---: | ---: |
| 全周期 | `2,729,700` | `1,670,390` |
| 主要回撤高点到谷底合计 | `-1,281,885` | `-125,595` |
| 主要20日利润窗口合计 | `4,193,380` | `1,448,790` |

主要回撤谷底阶段亏损品种合计：

| 品种 | 高点到谷底合计净利润 |
| --- | ---: |
| `au.SHFE` | `-53,080` |
| `jm.DCE` | `-44,460` |
| `cu.SHFE` | `-42,850` |
| `CF.CZCE` | `-20,475` |
| `sp.SHFE` | `-17,800` |
| `SM.CZCE` | `-15,020` |

### 修改的回测结果

- 无。

### 删除的回测结果

- 无。

### 验证

- 已完成语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_stage127_stage78_profit_drawdown_attribution.py`
- 已完成Stage127归因运行：
  - `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage127_stage78_profit_drawdown_attribution.py`

### 我的判断

- Stage78不是“某几个坏品种拖累”，而是典型趋势系统：收益和回撤都来自同一套方向暴露，尤其是多头暴露。
- 主要利润窗口由少数强趋势窗口贡献，尤其`jm.DCE`、`SM.CZCE`、`FG.CZCE`等；这说明不能轻易降低单笔趋势持有质量。
- 主要回撤从高点到谷底时，多头合计亏损远大于空头，这说明下一步更应该研究“持仓期减风险/盈利回吐保护”，而不是继续开仓端过滤。
- 不建议按`MA.CZCE`、`SH.CZCE`等亏损品种直接做黑名单，因为这会把历史样本当未来规律，过拟合风险高。

### 后续规划和TODO

- 停止开仓并发阈值微调。
- 下一步建议做Stage128：持仓期风险下降归因和小规模规则验证。
- Stage128规则必须是结构性的，例如：
  - 持仓从浮盈转弱后降低仓位；
  - 高点回吐达到某个与ATR/止损距离相关的比例后减仓；
  - 组合回撤扩大时只处理已有仓位，不阻断新趋势启动。

## 2026-04-25 15:18 第128阶段：Stage78利润回吐保护候选突破

### 本次版本改动

- 改动时间点：`2026-04-25 15:18`
- 是否是重要突破版本：是，属于研究候选突破；还不是正式固化版本。
- 核心思路：
  - 延续官方Stage78，不改品种池、AI筛选、排序、仓位 sizing 和开仓逻辑。
  - 只在持仓已有足够浮盈后，把止损抬到“保留部分最大浮盈”的位置，目标是减少趋势盈利后的大回吐。
  - 该机制默认关闭，作为可配置研究开关。
- 修改文件：
  - `examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage128_profit_giveback_stop.py`
- 新增产物：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage128_profit_giveback_stop_summary_stage128_profit_giveback_stop_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage128_profit_giveback_stop_start_year_summary_stage128_profit_giveback_stop_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage128_profit_giveback_stop_start_year_comparison_stage128_profit_giveback_stop_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage128_profit_giveback_stop_summary_stage128_profit_giveback_stop_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage128_profit_giveback_stop_report_stage128_profit_giveback_stop_v1.md`

### 新增参数

- `enable_profit_giveback_stop`，默认`False`
- `profit_giveback_trigger_pct`，默认`0.08`
- `profit_giveback_retain_ratio`，默认`0.70`
- `profit_giveback_min_lock_pct`，默认`0.03`

### 修改参数

- 官方Stage78默认参数未修改。
- Stage128回测候选参数：
  - `stage78_giveback08_retain70_min03`：`trigger=0.08`，`retain=0.70`，`min_lock=0.03`
  - `stage78_giveback10_retain80_min03`：`trigger=0.10`，`retain=0.80`，`min_lock=0.03`

### 删除参数

- 无。

### 新增回测结果

全周期结果：

| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 胜率 | 备注 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `official_stage78_reference` | `4,600,090` | `2200.0450%` | `-36.9907%` | `1.2919` | `260,110` | `779` | `42.1053%` | 官方Stage78基准 |
| `stage78_giveback08_retain70_min03` | `4,032,955` | `1916.4775%` | `-35.4771%` | `1.2553` | `262,720` | `780` | `41.8546%` | 太早保护，切掉趋势收益，不取 |
| `stage78_giveback10_retain80_min03` | `4,935,450` | `2367.7250%` | `-31.5415%` | `1.3730` | `253,490` | `775` | `42.3174%` | 候选突破 |

`stage78_giveback10_retain80_min03`起始年份稳健性对比Stage78：

| 起始窗口 | 期末权益差额 | 最大回撤改善 | Sharpe差额 |
| --- | ---: | ---: | ---: |
| `since_2020` | `+335,360` | `+5.4492pct` | `+0.0811` |
| `since_2021` | `+316,285` | `+5.3476pct` | `+0.0869` |
| `since_2022` | `+152,265` | `+2.0365pct` | `+0.0784` |
| `since_2023` | `+163,240` | `+3.5659pct` | `+0.0844` |
| `since_2024` | `+2,720` | `-0.4290pct` | `+0.0173` |
| `since_2025` | `-5,680` | `-1.5480pct` | `-0.0271` |
| `since_2026` | `0` | `0.0000pct` | `0.0000` |

- 起始年份权益胜出：`5/7`
- 起始年份Sharpe胜出：`5/7`
- 起始年份最大回撤胜出：`4/7`
- `profit_giveback_stop_update_count`：全周期`125`次。

### 修改的回测结果

- 无正式版本结果修改。本阶段为Stage78增量研究候选。

### 删除的回测结果

- 无。

### 验证

- 已完成语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py examples/portfolio_backtesting/analyze_qmt_roll_stage128_profit_giveback_stop.py`
- 已完成Stage128回测：
  - `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage128_profit_giveback_stop.py`
- 已补齐Stage128与Stage78起始年份同口径对比表：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage128_profit_giveback_stop_start_year_comparison_stage128_profit_giveback_stop_v1.csv`

### 运行前过拟合反思

- 判断：否。
- 原因：这是持仓期通用风险机制，不按年份、品种、方向、亏损样本做过滤；只预设两个粗参数方案，没有做网格搜索。
- 风险点：如果后续围绕`0.09/0.75/0.025`这类细参数继续搜索，会转为过拟合。

### 运行后过拟合反思

- 判断：没有明显过拟合，但不能直接固化。
- 原因：
  - 全周期收益、回撤、Sharpe同时优于Stage78，不是单纯牺牲收益换回撤。
  - 起始年份`5/7`权益和Sharpe胜出，说明不是只靠2020-2021某个单段行情。
  - 但`since_2024`回撤略差、`since_2025`收益和Sharpe略差，说明它不是无条件改进。
- 结论：这是候选突破，应进入归因和季度walk-forward；不应继续微调参数。

### 我的判断

- `giveback08_retain70`太早介入，会切掉趋势策略最重要的尾部收益，应放弃。
- `giveback10_retain80`的行为更接近“强趋势已有较大浮盈后，禁止回吐太多”，符合趋势系统第一性原理：不阻断入场，不降低单笔启动质量，只处理持仓后的利润保护。
- 这个方向明显比前面的并发限制更有价值，因为它不伤害开仓机会，直接作用在Stage127指出的核心问题：利润和回撤都来自持仓期趋势暴露。

### 后续规划和TODO

- Stage129优先做交易归因：
  - 对比Stage78与Stage128 best的交易差异；
  - 找出新增利润来自哪些退出提前、哪些回撤段被改善；
  - 检查是否只是少踩少数历史亏损单。
- 对`stage78_giveback10_retain80_min03`做季度walk-forward和滑点压力测试。
- 如果归因合理且稳健性通过，再考虑把该开关作为正式候选配置；当前不默认开启。

## 2026-04-25 15:30 第129阶段：Stage128利润回吐保护交易归因

### 本次版本改动

- 改动时间点：`2026-04-25 15:30`
- 是否是重要突破版本：否。该阶段是验证Stage128候选突破真实性的归因，不是新策略版本。
- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage129_profit_giveback_trade_attribution.py`
- 新增产物：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage129_profit_giveback_trade_attribution_summary_stage129_profit_giveback_trade_attribution_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage129_profit_giveback_trade_attribution_product_delta_stage129_profit_giveback_trade_attribution_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage129_profit_giveback_trade_attribution_direction_delta_stage129_profit_giveback_trade_attribution_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage129_profit_giveback_trade_attribution_exit_reason_delta_stage129_profit_giveback_trade_attribution_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage129_profit_giveback_trade_attribution_rolling20_delta_windows_stage129_profit_giveback_trade_attribution_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage129_profit_giveback_trade_attribution_roundtrips_stage129_profit_giveback_trade_attribution_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage129_profit_giveback_trade_attribution_summary_stage129_profit_giveback_trade_attribution_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage129_profit_giveback_trade_attribution_report_stage129_profit_giveback_trade_attribution_v1.md`

### 新增参数

- 无。沿用Stage128候选参数：
  - `enable_profit_giveback_stop=True`
  - `profit_giveback_trigger_pct=0.10`
  - `profit_giveback_retain_ratio=0.80`
  - `profit_giveback_min_lock_pct=0.03`

### 修改参数

- 无。

### 删除参数

- 无。

### 新增回测结果

全周期复跑结果：

| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 胜率 | 回合数 | 回合毛利润 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `official_stage78_reference` | `4,600,090` | `2200.0450%` | `-36.9907%` | `1.2919` | `260,110` | `779` | `42.1053%` | `399` | `4,661,750` |
| `stage78_giveback10_retain80_min03` | `4,935,450` | `2367.7250%` | `-31.5415%` | `1.3730` | `253,490` | `775` | `42.3174%` | `397` | `4,990,490` |

产品净利润差异：

| 类型 | 品种 | Stage128净利润 | Stage78净利润 | 差额 |
| --- | --- | ---: | ---: | ---: |
| 最大改善 | `FG.CZCE` | `868,100` | `746,100` | `+122,000` |
| 改善 | `sp.SHFE` | `176,160` | `86,280` | `+89,880` |
| 改善 | `jm.DCE` | `1,220,940` | `1,134,450` | `+86,490` |
| 改善 | `hc.SHFE` | `242,960` | `206,310` | `+36,650` |
| 改善 | `rb.SHFE` | `179,700` | `158,450` | `+21,250` |
| 最大恶化 | `AP.CZCE` | `425,610` | `460,720` | `-35,110` |
| 恶化 | `fu.SHFE` | `395,800` | `414,710` | `-18,910` |
| 恶化 | `SM.CZCE` | `361,570` | `377,360` | `-15,790` |
| 恶化 | `SA.CZCE` | `154,300` | `161,540` | `-7,240` |

- 改善品种：`10`
- 恶化品种：`4`
- 持平品种：`5`
- 最大单品种贡献占权益增量：`36.38%`

方向归因：

| 方向 | Stage128回合毛利润 | Stage78回合毛利润 | 差额 | 回合数变化 |
| --- | ---: | ---: | ---: | ---: |
| 多头 | `3,159,640` | `2,871,560` | `+288,080` | `-1` |
| 空头 | `1,830,850` | `1,790,190` | `+40,660` | `-1` |

退出原因归因：

| 退出原因 | Stage128回合毛利润 | Stage78回合毛利润 | 差额 |
| --- | ---: | ---: | ---: |
| `long_base_stop` | `1,316,780` | `132,820` | `+1,183,960` |
| `short_base_stop` | `-162,910` | `-441,870` | `+278,960` |
| `long_rsi_partial_exit_half` | `840,630` | `819,610` | `+21,020` |
| `rollover_close` | `724,290` | `802,650` | `-78,360` |
| `short_prev2day_stop` | `1,519,935` | `1,738,675` | `-218,740` |
| `long_prev2day_stop` | `809,720` | `1,667,820` | `-858,100` |

20日差异窗口：

| 类型 | 起点 | 终点 | 20日净利润差异 |
| --- | --- | --- | ---: |
| 最大改善 | `2024-08-21` | `2024-09-19` | `+119,970` |
| 改善 | `2022-02-15` | `2022-03-14` | `+96,340` |
| 改善 | `2021-04-15` | `2021-05-17` | `+82,940` |
| 最大恶化 | `2022-12-30` | `2023-02-03` | `-83,300` |
| 恶化 | `2023-05-05` | `2023-06-01` | `-53,700` |
| 恶化 | `2023-03-28` | `2023-04-25` | `-53,230` |

### 修改的回测结果

- 无正式版本结果修改。本阶段为归因复跑。

### 删除的回测结果

- 无。

### 验证

- 已完成语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_stage129_profit_giveback_trade_attribution.py`
- 已完成Stage129归因回测：
  - `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage129_profit_giveback_trade_attribution.py`

### 运行前过拟合反思

- 判断：否。
- 原因：固定比较Stage78与Stage128 best，不新增规则、不搜索参数、不按结果挑品种。

### 运行后过拟合反思

- 判断：没有明显过拟合，但仍不能固化。
- 原因：
  - 改善不是单一品种造成：`10`个品种改善，`4`个品种恶化。
  - 最大单品种贡献`36.38%`，不算单点依赖，但`FG.CZCE`、`sp.SHFE`、`jm.DCE`三个品种贡献较大，需要后续压力测试确认。
  - 改善主要来自多头，符合Stage127“多头既贡献收益也贡献回撤”的结论。
  - 退出原因显示利润从`prev2day_stop`转移到更高的`base_stop`退出，本质是浮盈后止损上移，而不是开仓过滤。
- 风险：
  - 三个品种贡献较集中，仍有样本路径风险。
  - 20日最大改善和最大恶化都存在，说明规则会改变收益分布，不是无副作用。

### 我的判断

- Stage129支持Stage128继续深挖：它不是单一历史事故，也不是靠增加交易次数或加风险赚钱。
- 但它也不是可以立刻固化的版本：贡献分布有中等集中度，必须过季度walk-forward和滑点压力。
- 这条线的本质是“用更紧的利润保护重分配退出原因”，不是“提高开仓命中率”。因此下一步不应调参数，而应测稳健性。

### 后续规划和TODO

- Stage130做季度walk-forward：
  - 比较Stage78与Stage128 best在63d、126d、252d窗口的正收益率、最差收益、最大回撤、Sharpe。
- Stage131做滑点压力：
  - `1.0x`、`1.5x`、`2.0x`、`3.0x`滑点。
- 如果Stage130/131都通过，再考虑正式候选；否则保留为研究分支，不固化。

## 2026-04-25 16:03 第130阶段：Stage128利润回吐保护季度Walk-Forward

### 本次版本改动

- 改动时间点：`2026-04-25 16:03`
- 是否是重要突破版本：否。该阶段是稳健性验证，结论为“保留研究价值，但不能固化”。
- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage130_profit_giveback_quarterly_walkforward.py`
- 新增产物：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage130_profit_giveback_quarterly_walkforward_quarter_summary_stage130_profit_giveback_quarterly_wf_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage130_profit_giveback_quarterly_walkforward_horizon_summary_stage130_profit_giveback_quarterly_wf_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage130_profit_giveback_quarterly_walkforward_horizon_aggregate_stage130_profit_giveback_quarterly_wf_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage130_profit_giveback_quarterly_walkforward_horizon_comparison_stage130_profit_giveback_quarterly_wf_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage130_profit_giveback_quarterly_walkforward_horizon_comparison_aggregate_stage130_profit_giveback_quarterly_wf_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage130_profit_giveback_quarterly_walkforward_summary_stage130_profit_giveback_quarterly_wf_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage130_profit_giveback_quarterly_walkforward_report_stage130_profit_giveback_quarterly_wf_v1.md`

### 新增参数

- 无。沿用Stage128候选：
  - `enable_profit_giveback_stop=True`
  - `profit_giveback_trigger_pct=0.10`
  - `profit_giveback_retain_ratio=0.80`
  - `profit_giveback_min_lock_pct=0.03`
- 验证窗口：
  - 季度冷启动起点：从`2020Q1`到`2026Q2`
  - Horizon：`63d`、`126d`、`252d`

### 修改参数

- 无。

### 删除参数

- 无。

### 新增回测结果

完整窗口参考：

| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 胜率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `official_stage78_reference` | `4,600,090` | `2200.0450%` | `-36.9907%` | `1.2919` | `260,110` | `779` | `42.1053%` |
| `stage78_giveback10_retain80_min03` | `4,935,450` | `2367.7250%` | `-31.5415%` | `1.3730` | `253,490` | `775` | `42.3174%` |

Horizon聚合：

| Horizon | 版本 | 窗口数 | 正收益率 | 最差收益 | 中位收益 | 最差最大回撤 | 中位Sharpe | 最差Sharpe |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `63d` | Stage78 | `25` | `68.0000%` | `-27.7950%` | `16.2975%` | `-44.5792%` | `1.7456` | `-3.7231` |
| `63d` | Stage128 | `25` | `68.0000%` | `-27.7950%` | `16.9050%` | `-42.1658%` | `1.7754` | `-3.7231` |
| `126d` | Stage78 | `24` | `83.3333%` | `-15.5125%` | `53.5100%` | `-44.5792%` | `1.5507` | `-2.6382` |
| `126d` | Stage128 | `24` | `87.5000%` | `-9.9625%` | `54.4475%` | `-42.3565%` | `1.6201` | `-2.6382` |
| `252d` | Stage78 | `22` | `95.4545%` | `-6.8250%` | `103.7725%` | `-44.5792%` | `1.5879` | `-0.2394` |
| `252d` | Stage128 | `22` | `90.9091%` | `-11.6600%` | `112.7250%` | `-42.3565%` | `1.7013` | `-1.2756` |

Stage128相对Stage78比较：

| Horizon | 收益胜率 | 回撤胜率 | Sharpe胜率 | 中位收益差 | 最差收益差 | 中位Sharpe差 | 最差Sharpe差 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `63d` | `28.0000%` | `24.0000%` | `32.0000%` | `0.0000` | `-1.8000` | `0.0000` | `-0.1224` |
| `126d` | `50.0000%` | `33.3333%` | `50.0000%` | `+0.1538` | `-3.5200` | `+0.0048` | `-0.1541` |
| `252d` | `72.7273%` | `45.4545%` | `72.7273%` | `+3.7963` | `-16.3950` | `+0.0528` | `-1.6501` |

最差相对窗口：

| 窗口 | Horizon | Stage128收益 | Stage78收益 | 差额 | 最大回撤差 | Sharpe差 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `q2022_4` | `252d` | `-11.6600%` | `4.7350%` | `-16.3950` | `-4.7320` | `-1.6501` |
| `q2023_1` | `252d` | `60.0250%` | `64.8250%` | `-4.8000` | `-0.9100` | `-0.0962` |
| `q2023_1` | `126d` | `67.6600%` | `71.1800%` | `-3.5200` | `-2.3468` | `-0.1541` |
| `q2025_1` | `252d` | `355.9350%` | `359.2900%` | `-3.3550` | `-1.5480` | `-0.0374` |

### 修改的回测结果

- 无正式版本结果修改。本阶段为季度冷启动验证。

### 删除的回测结果

- 无。

### 验证

- 已完成语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_stage130_profit_giveback_quarterly_walkforward.py`
- 已完成Stage130季度walk-forward：
  - `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage130_profit_giveback_quarterly_walkforward.py`

### 运行前过拟合反思

- 判断：否。
- 原因：固定候选、固定全季度起点、固定`63/126/252d`窗口，不根据结果挑窗口或调参数。

### 运行后过拟合反思

- 判断：不是明显过拟合，但正式固化证据不足。
- 原因：
  - `252d`窗口收益和Sharpe胜率均为`72.7273%`，支持中长期持仓改善。
  - `126d`窗口中性偏好，正收益率和中位指标略改善。
  - `63d`窗口没有优势，收益胜率仅`28.0000%`，说明短冷启动阶段并不能证明Stage128更好。
  - `q2022_4 252d`出现明显恶化：收益差`-16.3950`个百分点，Sharpe差`-1.6501`，这是必须解释的弱点。
- 结论：
  - Stage128不是曲线拟合出来的单点幻觉，但还不是稳健到能固化。
  - 下一步不应立刻做滑点压力，而应先做`q2022_4 252d`弱窗口归因。

### 我的判断

- Stage128的本质更像“中长持仓收益再分配”：在`252d`更有效，在`63d`冷启动不明显。
- 这符合利润回吐保护的机制特征：它不提高入场质量，只有当持仓进入较大浮盈后才发挥作用。
- 但正式策略必须能解释最差窗口，否则可能是在牺牲某类趋势延续结构。

### 后续规划和TODO

- Stage131优先做弱窗口归因，而不是滑点压力：
  - 聚焦`q2022_4 252d`；
  - 对比Stage78和Stage128的交易差异、产品差异、退出原因差异；
  - 判断恶化是偶然少数交易，还是利润回吐机制天然会伤害某类行情。
- 如果弱窗口可解释且非结构性，再做Stage132滑点压力。
- 如果弱窗口显示利润回吐保护系统性切掉关键趋势，Stage128不固化，停止调参。

## 2026-04-25 16:14 第131阶段：Stage128利润回吐保护弱窗口归因

### 本次版本改动

- 改动时间点：`2026-04-25 16:14`
- 是否是重要突破版本：否。该阶段是关键否定证据，结论是不建议原始Stage128继续走正式固化路径。
- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage131_profit_giveback_weak_window_attribution.py`
- 新增产物：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage131_profit_giveback_weak_window_attribution_summary_stage131_profit_giveback_weak_window_attribution_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage131_profit_giveback_weak_window_attribution_product_delta_stage131_profit_giveback_weak_window_attribution_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage131_profit_giveback_weak_window_attribution_direction_delta_stage131_profit_giveback_weak_window_attribution_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage131_profit_giveback_weak_window_attribution_exit_reason_delta_stage131_profit_giveback_weak_window_attribution_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage131_profit_giveback_weak_window_attribution_daily_delta_stage131_profit_giveback_weak_window_attribution_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage131_profit_giveback_weak_window_attribution_top_roundtrips_stage131_profit_giveback_weak_window_attribution_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage131_profit_giveback_weak_window_attribution_candidate_summary_stage131_profit_giveback_weak_window_attribution_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage131_profit_giveback_weak_window_attribution_skip_reason_summary_stage131_profit_giveback_weak_window_attribution_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage131_profit_giveback_weak_window_attribution_summary_stage131_profit_giveback_weak_window_attribution_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage131_profit_giveback_weak_window_attribution_report_stage131_profit_giveback_weak_window_attribution_v1.md`

### 新增参数

- 无。沿用Stage128候选参数：
  - `enable_profit_giveback_stop=True`
  - `profit_giveback_trigger_pct=0.10`
  - `profit_giveback_retain_ratio=0.80`
  - `profit_giveback_min_lock_pct=0.03`
- 固定分析窗口：
  - `q2022_4`
  - 起点：`2022-10-01`
  - Horizon：`252`个交易日

### 修改参数

- 无。

### 删除参数

- 无。

### 新增回测结果

`q2022_4 252d`弱窗口结果：

| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 回合数 | 回合胜率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `official_stage78_reference` | `209,470` | `4.7350%` | `-8.3363%` | `0.3745` | `2,020` | `45` | `23` | `43.4783%` |
| `stage78_giveback10_retain80_min03` | `176,680` | `-11.6600%` | `-13.0683%` | `-1.2756` | `760` | `12` | `6` | `16.6667%` |

产品差异：

| 品种 | Stage128净利润 | Stage78净利润 | 差额 | 交易次数差 |
| --- | ---: | ---: | ---: | ---: |
| `OI.CZCE` | `0` | `21,080` | `-21,080` | `-2` |
| `SM.CZCE` | `-11,400` | `3,370` | `-14,770` | `-4` |
| `fu.SHFE` | `0` | `7,680` | `-7,680` | `-11` |
| `rb.SHFE` | `-1,470` | `0` | `-1,470` | `+2` |
| `SA.CZCE` | `0` | `520` | `-520` | `-2` |
| `FG.CZCE` | `2,300` | `-2,540` | `+4,840` | `-2` |

方向归因：

| 方向 | Stage128回合毛利润 | Stage78回合毛利润 | 差额 | 回合数差 |
| --- | ---: | ---: | ---: | ---: |
| 多头 | `2,490` | `25,130` | `-22,640` | `-18` |
| 空头 | `-25,050` | `-13,640` | `-11,410` | `+1` |

退出原因归因：

| 退出原因 | Stage128回合毛利润 | Stage78回合毛利润 | 差额 | 回合数差 |
| --- | ---: | ---: | ---: | ---: |
| `long_base_stop` | `3,220` | `-1,530` | `+4,750` | `-1` |
| `long_rsi_partial_exit_half` | `0` | `6,980` | `-6,980` | `-1` |
| `rollover_close` | `0` | `10,120` | `-10,120` | `-2` |
| `long_prev2day_stop` | `-730` | `9,560` | `-10,290` | `-14` |
| `short_prev2day_stop` | `-12,530` | `-1,120` | `-11,410` | `+1` |

候选和风险状态归因：

| 指标 | Stage78 | Stage128 |
| --- | ---: | ---: |
| 候选数 | `184` | `184` |
| 开仓候选数 | `20` | `6` |
| 实际开仓诊断数 | `22` | `6` |
| 开仓率 | `10.8696%` | `3.2609%` |
| 候选selected_volume合计 | `270` | `160` |
| 已开仓selected_volume合计 | `56` | `25` |
| 已开仓中位risk_multiplier | `1.00` | `0.55` |
| `sizing_zero_volume`跳过数 | `80` | `110` |
| `ai_product_pool_blocked`跳过数 | `22` | `6` |

### 修改的回测结果

- 无正式版本结果修改。本阶段为失败窗口归因。

### 删除的回测结果

- 无。

### 验证

- 已完成语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_stage131_profit_giveback_weak_window_attribution.py`
- 已完成Stage131弱窗口归因：
  - `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage131_profit_giveback_weak_window_attribution.py`

### 运行前过拟合反思

- 判断：否。
- 原因：固定分析Stage130暴露出的最差反证窗口，不调参、不删窗口、不新增规则。

### 运行前继续价值反思

- 判断：是。
- 原因：`q2022_4 252d`决定Stage128是否还能继续做滑点压力；如果该窗口是机制性缺陷，就应停止原分支。

### 运行后过拟合反思

- 判断：否。
- 原因：结果是负面归因，不是为了优化参数；没有用失败窗口反推新阈值。

### 运行后继续价值反思

- 判断：原始Stage128分支不值得继续直接做滑点压力；利润回吐概念仍可保留为新分支研究。
- 原因：
  - 弱窗口问题不是滑点或单笔执行成本，而是路径依赖和风险状态问题。
  - Stage128开仓数从`20`降到`6`，`sizing_zero_volume`从`80`升到`110`，说明利润回吐改变了前置路径后，仓位 sizing 和风险倍率抑制了后续恢复交易。
  - 它错过了`OI.CZCE`、`fu.SHFE`等Stage78贡献的恢复段利润。

### 我的判断

- 原始Stage128不能固化，也不应继续做滑点压力。
- 它的全周期改善是真的，但弱窗口显示它可能通过改变前序风险状态，让系统在后续恢复段“没有足够子弹”。
- 这不是简单参数问题。继续调`trigger/retain/min_lock`会过拟合。

### 后续规划和TODO

- 停止原始`stage78_giveback10_retain80_min03`正式化路线。
- 如果继续利润回吐方向，只能开新研究分支，核心不是调阈值，而是研究：
  - 利润保护退出是否应该影响亏损/恢复状态；
  - 是否需要把“保护性止盈退出”和“真正止损退出”在风险状态里分开计数；
  - 是否能在不伤害恢复段开仓能力的前提下保留利润回吐保护。
- 如果不做新分支，回到Stage78正式版本，优先研究其他不改变风险状态路径的方向。

## 2026-04-25 16:31 第132阶段：利润回吐保护与连亏惩罚解耦验证

### 本次版本改动

- 改动时间点：`2026-04-25 16:31`
- 是否是重要突破版本：否。该阶段是关键否定证据，说明“保护性止损亏损不进入连亏惩罚”无法修复Stage128弱窗口。
- 修改策略：
  - `examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage132_profit_giveback_streak_decouple.py`
- 新增产物：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage132_profit_giveback_streak_decouple_summary_stage132_profit_giveback_streak_decouple_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage132_profit_giveback_streak_decouple_comparison_stage132_profit_giveback_streak_decouple_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage132_profit_giveback_streak_decouple_candidate_summary_stage132_profit_giveback_streak_decouple_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage132_profit_giveback_streak_decouple_skip_reason_summary_stage132_profit_giveback_streak_decouple_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage132_profit_giveback_streak_decouple_summary_stage132_profit_giveback_streak_decouple_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage132_profit_giveback_streak_decouple_report_stage132_profit_giveback_streak_decouple_v1.md`

### 新增参数

- `profit_giveback_streak_update_mode`
  - 默认值：`normal`
  - 本次验证值：`loss_neutral`
  - 含义：当利润回吐止损曾经实际抬高止损，且最终该保护性止损变成亏损退出时，不把该笔退出计入连亏惩罚。
- 新增诊断变量：
  - `profit_giveback_streak_neutral_count`
  - 含义：记录利润回吐保护退出被风险状态中性化的次数。

### 修改参数

- Stage132验证组合在Stage128 best基础上只增加：
  - `profit_giveback_streak_update_mode=loss_neutral`
- Stage128原参数保持不变：
  - `enable_profit_giveback_stop=True`
  - `profit_giveback_trigger_pct=0.10`
  - `profit_giveback_retain_ratio=0.80`
  - `profit_giveback_min_lock_pct=0.03`

### 删除参数

- 无。

### 新增回测结果

全周期`2020-01-01`到`2026-04-21`：

| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 胜率 | 利润保护抬止损次数 | 风险中性化次数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `official_stage78_reference` | `4,600,090` | `2200.0450%` | `-36.9907%` | `1.2919` | `260,110` | `779` | `42.1053%` | `0` | `0` |
| `stage128_giveback_normal` | `4,935,450` | `2367.7250%` | `-31.5415%` | `1.3730` | `253,490` | `775` | `42.3174%` | `125` | `0` |
| `stage132_giveback_loss_neutral` | `4,883,250` | `2341.6250%` | `-31.5415%` | `1.3684` | `253,670` | `775` | `42.3174%` | `125` | `1` |

`q2022_4 252d`弱窗口：

| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 胜率 | 回合数 | 回合毛利润 | 风险中性化次数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `official_stage78_reference` | `209,470` | `4.7350%` | `-8.3363%` | `0.3745` | `2,020` | `45` | `43.4783%` | `23` | `11,490` | `0` |
| `stage128_giveback_normal` | `176,680` | `-11.6600%` | `-13.0683%` | `-1.2756` | `760` | `12` | `16.6667%` | `6` | `-22,560` | `0` |
| `stage132_giveback_loss_neutral` | `176,680` | `-11.6600%` | `-13.0683%` | `-1.2756` | `760` | `12` | `16.6667%` | `6` | `-22,560` | `1` |

弱窗口候选状态：

| 版本 | 候选数 | 开仓候选数 | 开仓率 | 已开仓中位risk_multiplier | 实际开仓诊断数 | 开仓诊断中位risk_multiplier |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `official_stage78_reference` | `184` | `20` | `10.8696%` | `1.00` | `22` | `1.00` |
| `stage128_giveback_normal` | `184` | `6` | `3.2609%` | `0.55` | `6` | `0.55` |
| `stage132_giveback_loss_neutral` | `184` | `6` | `3.2609%` | `0.55` | `6` | `0.55` |

### 修改的回测结果

- 无正式版本结果修改。本阶段是新增研究分支验证。

### 删除的回测结果

- 无。

### 验证

- 已完成语法检查：
  - `.py311/bin/python -m py_compile examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py examples/portfolio_backtesting/analyze_qmt_roll_stage132_profit_giveback_streak_decouple.py`
- 已完成Stage132验证：
  - `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage132_profit_giveback_streak_decouple.py`

### 运行前过拟合反思

- 判断：否。
- 原因：固定一个由Stage131失败归因推出的机制假设，只验证`loss_neutral`，不调利润保护阈值，不新增品种或窗口筛选。

### 运行前继续价值反思

- 判断：是。
- 原因：如果`loss_neutral`能修复`q2022_4 252d`且全周期不塌，利润保护思想仍可能进入季度walk-forward。

### 运行后过拟合反思

- 判断：否。
- 原因：结果是负向证据，没有继续根据结果改参数；风险中性化只触发`1`次，说明该假设本身不是主要矛盾。

### 运行后继续价值反思

- 判断：否。
- 原因：`q2022_4 252d`完全没有改善，全周期还较Stage128 normal少`52,200`权益；继续围绕`profit_giveback_streak_update_mode`调更多模式会变成过拟合。

### 后续规划和TODO

- 停止Stage132的`loss_neutral`分支。
- 利润保护方向暂时降级，不再优先投入。
- 下一步更值得回到Stage78正式基准，研究不改变退出后风险状态的方向，例如：
  - 更稳健的全市场品种池更新节奏；
  - 40万本金下的容量/并发/保证金自然约束；
  - 不影响单笔趋势质量的组合层风险上限。
