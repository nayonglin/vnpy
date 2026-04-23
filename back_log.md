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
