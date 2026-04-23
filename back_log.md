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
