---
name: "qmt-roll-validation"
description: "执行 QMT Roll 主回测、多周期、Walk-Forward 与蒙特卡洛验证。适用于本仓库策略改动后复验、做三个实验或版本对比时调用。"
---

# QMT Roll 验证

## 目的

这个 skill 用来标准化本仓库 `QMT Roll` 组合策略的验证流程，避免不同 agent 因口径不一致而得出不可对比的结论。

适用场景：

- 用户在修改策略逻辑或参数后，要求重跑主回测
- 用户要求做多周期验证
- 用户要求做 Walk-Forward 验证
- 用户要求做蒙特卡洛验证
- 用户要求判断最新版本是否更稳健、是否可能过拟合、是否更适合实盘
- 当用户说进行三个实验
- 新 agent 需要快速继承本项目的验证流程、产物路径与结果解读口径

本 skill 仅适用于以下工作区：

`/Users/bytedance/Desktop/person/vnpy`

## 硬规则

- 使用本地解释器：`/Users/bytedance/Desktop/person/vnpy/.py311/bin/python`
- 必须设置 `PYTHONPATH=/Users/bytedance/Desktop/person/vnpy`
- 所有脚本都从仓库根目录执行，避免 vn.py 误读用户级 `.vntrader`：
  `/Users/bytedance/Desktop/person/vnpy`
- 除非用户明确要求改参数，否则默认以 `run_qmt_roll_backtest.py` 当前配置为准
- 只有在对应脚本运行完成后，最新导出的 `CSV/JSON` 才能作为最终结果
- 如果批量脚本仍在运行，不要根据中途日志直接下最终结论，除非明确说明这是预览结果

## 策略上下文

验证时需要特别关注并保持一致的项目假设：

- 执行模型使用 `SameDayCloseBacktestingEngine`，即同一根日线收盘撮合
- 默认关闭所有加仓
- 当前仓位 sizing 逻辑可能随策略变更而变化，运行前必须先核对 `run_qmt_roll_backtest.py` 与 `qmt_roll_portfolio_strategy.py` 的当前实现，不能假设永远是 100 万上限
- 新开空只允许 `short_case1a`
- 标准验证流水线包含：
  - `run_qmt_roll_backtest.py`
  - `run_qmt_roll_period_sweep.py`
  - `run_qmt_roll_walkforward.py`
  - `run_qmt_roll_monte_carlo.py`

## 标准命令

以下命令统一在仓库根目录下执行：

`/Users/bytedance/Desktop/person/vnpy`

主回测：

```bash
PYTHONPATH=/Users/bytedance/Desktop/person/vnpy \
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python examples/portfolio_backtesting/run_qmt_roll_backtest.py
```

多周期：

```bash
PYTHONPATH=/Users/bytedance/Desktop/person/vnpy \
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python examples/portfolio_backtesting/run_qmt_roll_period_sweep.py
```

Walk-Forward：

```bash
PYTHONPATH=/Users/bytedance/Desktop/person/vnpy \
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python examples/portfolio_backtesting/run_qmt_roll_walkforward.py
```

蒙特卡洛：

```bash
PYTHONPATH=/Users/bytedance/Desktop/person/vnpy \
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python examples/portfolio_backtesting/run_qmt_roll_monte_carlo.py
```

## 标准流程

### 1. 先确认当前配置

开始跑任何实验前，先检查：

- 阅读 `run_qmt_roll_backtest.py`
- 确认当前默认参数，例如：
  - `risk_ratio_of_total_assets`
  - `risk_ratio_open_interest_surge`
  - `risk_ratio_volume_open_interest_surge`
  - 是否开启空头
  - 是否开启加仓
  - 如果最近改过品种池，要确认 pool / universe 假设是否变化

如果用户刚改过 `qmt_roll_portfolio_strategy.py`，还需要额外检查对应的策略函数。

### 2. 跑主回测

第一步先执行 `run_qmt_roll_backtest.py`。

需要提取并汇报：

- 期末权益
- 总收益率
- 最大回撤百分比
- Sharpe Ratio
- 收益回撤比
- 总成交笔数

主要输出文件：

- `backtest_outputs/qmt_roll_statistics.json`
- `backtest_outputs/qmt_roll_daily_equity.csv`
- `backtest_outputs/qmt_roll_trades_2020_2026_04.csv`
- `backtest_outputs/qmt_roll_entry_risk_diagnostics_2020_2026_04.csv`
- `backtest_outputs/qmt_roll_professional_dashboard.html`
- `backtest_outputs/qmt_roll_trade_review.html`

### 3. 跑多周期验证

执行 `run_qmt_roll_period_sweep.py`。

主要读取：

- `backtest_outputs/qmt_roll_period_sweep_summary.csv`

重点关注：

- `full_sample`
- `period_2020_2021`
- `period_2022_2023`
- `period_2024_2026`
- 各类滚动窗口，例如 `roll_2020_2022`、`roll_2021_2023`、`roll_2022_2024`、`roll_2023_2026`

解读规则：

- 如果前期样本很强、但 `2022-2024` 很弱，说明阶段敏感性依旧存在
- 如果全样本变好，但弱窗口恶化，必须明确指出
- 只有弱窗口也能接受时，才能把策略描述为“稳定”

### 4. 跑 Walk-Forward 验证

执行 `run_qmt_roll_walkforward.py`。

主要读取：

- `backtest_outputs/qmt_roll_walkforward_train_summary.csv`
- `backtest_outputs/qmt_roll_walkforward_test_summary.csv`

需要汇总：

- 测试窗口总数
- 正收益窗口数和负收益窗口数
- 最好与最差的测试窗口
- 每个窗口最终选中的 `risk_ratio`
- 这些参数选择是否真的随窗口发生了有意义变化

重要提醒：

- 如果所有 `selected_risk_ratio` 都相同，或者训练集中不同 `risk_ratio` 的结果完全一样，必须明确指出参数网格没有形成真实区分度
- 这种情况下，Walk-Forward 仍可用于观察样本外表现，但不能证明参数选择本身有效

### 5. 跑蒙特卡洛验证

执行 `run_qmt_roll_monte_carlo.py`。

主要读取：

- `backtest_outputs/qmt_roll_monte_carlo_summary.csv`
- `backtest_outputs/qmt_roll_monte_carlo_simulations.csv`

两种方法都要看：

- `daily_block_bootstrap`
- `trade_block_bootstrap`

重点汇报：

- 亏损概率
- 爆仓概率
- 回撤超过 `20%`、`30%`、`40%` 的概率
- 中位收益和中位最大回撤
- 如果有必要，还要说明 `1%` 极端尾部回撤

解读规则：

- 如果爆仓概率接近 `0`，可以说明尾部生存性尚可
- 如果 `30%+` 或 `40%+` 回撤概率依旧很高，必须说明尾部回撤风险仍然显著
- 要比较 `daily bootstrap` 和 `trade bootstrap` 的尾部结果，以更差的一边作为风险提示基调

## 结果汇总模板

最终交付建议按下面这个中文结构输出：

- `已完成`:
  - 列出本次重跑了哪些脚本
- `主回测`:
  - 期末权益 / 收益 / 最大回撤 / Sharpe / 收益回撤比
- `多周期`:
  - 最强窗口
  - 最弱窗口
  - 对阶段敏感性的整体结论
- `Walk-Forward`:
  - 正负窗口数量
  - 最好和最差的测试区间
  - 参数网格是否真的形成区分
- `蒙特卡洛`:
  - 爆仓概率
  - 尾部回撤概率
  - 路径鲁棒性是否可接受
- `结论`:
  - 用一段话明确说明：最新版本到底是整体更稳健、只是全样本更好，还是仍需继续优化

## 环境排障

如果运行失败，按以下顺序排查：

- 如果出现 `python: command not found`，改用前面固定的解释器
- 如果出现 `ModuleNotFoundError: vnpy`，确认 `PYTHONPATH=/Users/bytedance/Desktop/person/vnpy`
- 如果批量脚本还在跑，不要过早相信中途写出的 CSV
- 如果当前终端繁忙，优先切到空闲终端，不要直接打断正在运行的任务

## 何时继续深挖

当主流程跑完后，如果结果异常或稳定性不足，建议继续深挖：

- `2022-2024` 弱势窗口归因
- 按品种、方向、风险模式做拆解
- 专项检查 `volume_open_interest_surge` 这类交易
- 排查为什么 Walk-Forward 的参数选择没有形成区分度

## 调用示例

当用户说出类似下面的话时，应调用本 skill：

- “帮我把回测和多周期、forward、蒙特卡洛都跑一遍”
- “这版改动后重新做完整验证”
- “看看这版是不是更稳，不要只看单次回测”
- “换个 agent 也能按固定流程跑验证吗”
