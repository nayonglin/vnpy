---
name: "qmt-roll-risk-grid"
description: "执行 QMT Roll 四参数风险网格实验与结果汇总。用户要求做风险参数网格搜索、粗细两轮实验或排查 default/base risk 是否生效时调用。"
---

# QMT Roll 四参数网格

## 目的

这个 skill 用来标准化本仓库 `QMT Roll` 策略的四参数风险实验流程，避免不同 agent 用不同口径扫参，导致结果不可比。

本 skill 关注的四个核心风险参数是：

- `risk_ratio_of_total_assets`
- `risk_ratio_open_interest_surge`
- `risk_ratio_volume_open_interest_surge`
- `risk_ratio_open_interest_decline`

目标不是只找“收益最高”的参数，而是系统确认：

- 哪组四参数在当前代码口径下真正生效
- `base/default risk` 是否有真实命中，而不是死参数
- 风险分档是否按预期触发
- 候选参数是否在收益、Sharpe、回撤、胜率之间更均衡
- 是否需要从粗网格继续收缩到精细网格

这个 skill 仅适用于以下工作区：

`/Users/bytedance/Desktop/person/vnpy`

## 何时调用

当用户表达以下任一意图时，应优先调用本 skill：

- 用户说“做四参数网格实验”
- 用户说“帮我扫一下 risk ratio 参数”
- 用户要求“完整网格”“精细网格”“第二轮细化”
- 用户要求比较 `base / oi_surge / vol_oi_surge / oi_decline` 四档风险比例
- 用户要求排查 `default risk` 或 `base risk` 为什么没触发
- 用户要求判断某个风险参数是否是死参数
- 用户要求把风险参数优化过程沉淀成固定流程

如果用户更关心的是主回测、多周期、Walk-Forward、蒙特卡洛整体验证，应优先调用 `qmt-roll-validation`。

如果用户更关心的是成交、净值、止损、风险快照是否可信，应优先调用 `qmt-roll-review`。

## 硬规则

- 使用解释器：
  `/Users/bytedance/Desktop/person/vnpy/.py311/bin/python`
- 必须设置：
  `PYTHONPATH=/Users/bytedance/Desktop/person/vnpy`
- 默认执行目录：
  `/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting`
- 除非用户明确要求，不要在扫参过程中顺手改其他策略逻辑
- 如果用户刚改过风险模式阈值，必须先检查当前策略代码，再决定是直接跑粗网格还是先做 spot check
- 网格结论必须同时基于：
  - `statistics`
  - `entry_risk_diagnostics`
  - `risk_mode` 命中分布
- 不能只看 `score` 排名，不检查 `count_regular / count_oi_surge / count_vol_oi_surge / count_oi_decline`

## 当前代码口径必须先确认

开始实验前，先检查以下代码：

- `examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
- `examples/portfolio_backtesting/run_qmt_roll_backtest.py`
- `examples/portfolio_backtesting/run_qmt_roll_risk_4param_grid.py`
- `examples/portfolio_backtesting/run_qmt_roll_risk_4param_grid_refined.py`

特别注意当前 `open_interest` 风险模式死区口径：

- `latest_two_sum > previous_two_sum * 1.2` 才算 `open_interest_surge`
- `latest_two_sum < previous_two_sum * 0.9` 才算 `open_interest_decline`
- 中间区间回到 `regular`

如果后续用户继续改阈值，必须先按最新代码口径解释结果，不能沿用旧结论。

## 相关脚本

### 1. 第一轮粗网格

脚本：

- `run_qmt_roll_risk_4param_grid.py`

作用：

- 扫一轮离散粗网格
- 计算综合评分 `score`
- 导出四档 `risk_mode` 命中数
- 识别 `base/default risk` 是否真的生效

产物：

- `backtest_outputs/qmt_roll_risk_4param_grid_summary.csv`

### 2. 第二轮精细网格

脚本：

- `run_qmt_roll_risk_4param_grid_refined.py`

作用：

- 在第一轮候选附近缩小区间继续细化
- 对当前真正有效的风险分支做局部搜索
- 导出更细的最优组合排序

产物：

- `backtest_outputs/qmt_roll_risk_4param_grid_refined_summary.csv`

## 标准命令

统一在以下目录执行：

`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting`

粗网格：

```bash
PYTHONPATH=/Users/bytedance/Desktop/person/vnpy \
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python run_qmt_roll_risk_4param_grid.py
```

精细网格：

```bash
PYTHONPATH=/Users/bytedance/Desktop/person/vnpy \
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python run_qmt_roll_risk_4param_grid_refined.py
```

## 标准流程

### 1. 先确认当前风险模式是否有死参数

开始完整网格前，先检查：

- `_open_interest_risk_mode()` 的阈值
- `_volume_open_interest_risk_mode()` 的阈值
- `_calculate_entry_sizing()` 如何把 `risk_mode` 映射到 `risk_ratio`
- `run_qmt_roll_backtest.py` 中 `risk_overrides` 是否正确传入

如果用户刚改了阈值，先做一次代表性 spot check，确认：

- `regular` 是否重新出现
- `open_interest_decline` 是否过少或过多
- `volume_open_interest_surge` 是否仍然命中

如果 spot check 显示 `count_regular = 0`，要先解释清楚，再决定是否继续扫。

### 2. 跑第一轮粗网格

执行 `run_qmt_roll_risk_4param_grid.py` 后，读取：

- `qmt_roll_risk_4param_grid_summary.csv`

至少提取以下字段：

- `rank`
- `base_risk`
- `oi_surge_risk`
- `vol_oi_surge_risk`
- `oi_decline_risk`
- `score`
- `sharpe_ratio`
- `return_drawdown_ratio`
- `max_dd_percent`
- `total_return_pct`
- `win_ratio_pct`
- `count_regular`
- `count_active_base`
- `count_oi_surge`
- `count_vol_oi_surge`
- `count_oi_decline`

### 3. 判断是否要进第二轮精细网格

满足以下任一条件时，建议继续跑 `refined`：

- Top 3 组合非常接近
- 某个参数只在边界上更优，需要确认是不是边界假象
- `base risk` 已经恢复生效，需要重新展开更细的 base 搜索
- 用户明确要求“第二轮精细网格”

如果粗网格已经清楚显示某个参数维度是死参数，也要明确指出，而不是盲目继续细化。

### 4. 跑第二轮精细网格

执行 `run_qmt_roll_risk_4param_grid_refined.py` 后，读取：

- `qmt_roll_risk_4param_grid_refined_summary.csv`

重点关注：

- Top 5 排名是否稳定
- 与粗网格冠军相比是否真的改进
- `count_regular` 是否继续为正
- `count_oi_decline` 是否过于稀疏
- 细化后的最优点是否仍然落在边界

### 5. 输出结论时必须区分三件事

必须把下面三类结论分开说：

- `统计口径问题`
  - 例如以前把 `regular` 误统计成 `default`
- `策略逻辑问题`
  - 例如 `open_interest` 风险模式把 `regular` 全覆盖，导致 `base risk` 成为死参数
- `参数优劣问题`
  - 例如在当前逻辑下 `vol_oi_surge=0.075` 比 `0.08` 略优

不要把“统计错了”和“策略没生效”混成同一个问题。

## 结果解读规则

### 1. 关于 `score`

当前网格脚本的 `score` 是综合指标，不是唯一标准。

它偏好：

- 收益回撤比
- Sharpe
- 总收益
- 胜率

同时会惩罚较大的回撤。

因此输出结论时，除了给冠军参数，也要补一句：

- 是否只是 `score` 第一
- 还是 `Sharpe / 回撤 / 收益` 三者都比较均衡

### 2. 关于 `base risk`

当 `count_regular + count_breakout + count_ma_cross_breakout = 0` 时，要明确说明：

- 当前 `base risk` 在这版策略里没有生效
- 继续优化 `base_risk` 数值没有意义

当 `count_regular > 0` 时，要明确说明：

- 当前 `base risk` 已恢复成有效参数
- 后续完整网格应重新把 `base_risk` 放回主搜索空间

### 3. 关于 `oi_decline`

如果 `count_oi_decline` 非常少，要指出：

- `oi_decline` 参数虽可调，但样本支撑较弱
- 不能过度解读单次最优值

### 4. 关于 `vol_oi_surge`

如果 `count_vol_oi_surge` 很低但对结果影响明显，要指出：

- 它是低频高影响参数
- 需要重点关注极端回撤和收益放大效应

## 推荐输出模板

最终建议按下面结构汇报：

- `已完成`
  - 跑了哪些脚本
  - 读了哪些结果文件
- `当前口径`
  - 当前 `open_interest` 的 surge / decline / regular 切分阈值
  - `base risk` 是否已经恢复生效
- `粗网格结果`
  - Top 3 组合
  - 是否发现死参数
- `精细网格结果`
  - 最优组合
  - 相比粗网格是否改进
- `risk_mode 命中`
  - `regular`
  - `oi_surge`
  - `vol_oi_surge`
  - `oi_decline`
- `主结论`
  - 当前最推荐的四参数
  - 哪些维度值得继续细化
  - 哪些维度暂时不该过度优化

## 环境排障

如果运行失败，按以下顺序排查：

- 如果出现 `python: command not found`，改用固定解释器
- 如果出现 `ModuleNotFoundError: vnpy`，确认 `PYTHONPATH=/Users/bytedance/Desktop/person/vnpy`
- 如果结果文件没有生成，先看脚本是否跑完，不要根据中途日志下最终结论
- 如果终端忙，优先切到空闲终端，不要打断正在运行的长任务

## 典型调用示例

以下说法都应触发本 skill：

- “帮我做完整的四参数网格实验”
- “再跑一轮粗网格和精细网格”
- “看看 base risk 现在是不是已经生效”
- “把这四个风险比例系统性扫一遍”
- “我想要一套固定的风险参数优化流程”
