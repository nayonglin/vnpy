---
name: "qmt-roll-review"
description: "执行 QMT Roll 回测复盘、结果审计与 bug 排查。用户说“复盘”、检查回测是否可信、是否按预期执行时调用。"
---

# QMT Roll 复盘

## 目的

这个 skill 用来标准化本仓库 `QMT Roll` 策略的复盘流程，目标不是只看收益，而是系统确认：

- 回测结果是否可信
- 净值和成交是否自洽
- 止损和平仓是否按当前代码预期执行
- 风险快照、复盘页、交易明细之间是否一致
- 当前版本是否存在隐藏 bug 或口径不一致

这个 skill 适用于以下工作区：

`/Users/bytedance/Desktop/person/vnpy`

## 何时调用

当用户表达以下任一意图时，应优先调用本 skill：

- 用户直接说“复盘”
- 用户要求“复盘一下回测”
- 用户要求“检查这版是不是有 bug”
- 用户要求“看看止损是不是按预期触发”
- 用户要求“净值算得对不对”
- 用户要求“交易、止损、净值、风控链路是否一致”
- 用户要求“定位某一笔交易为什么这样成交/平仓”
- 用户要求“检查策略是否按预期执行，而不只是看收益”

如果用户只要求跑主回测、多周期、Walk-Forward、蒙特卡洛，而不是做深入审计，应优先调用 `qmt-roll-validation`，不是本 skill。

## 硬规则

- 使用解释器：
  `/Users/bytedance/Desktop/person/vnpy/.py311/bin/python`
- 必须设置：
  `PYTHONPATH=/Users/bytedance/Desktop/person/vnpy`
- 默认执行目录为仓库根目录，避免 vn.py 误读用户级 `.vntrader`：
  `/Users/bytedance/Desktop/person/vnpy`
- 除非用户明确要求，不要顺手修改策略逻辑；先做审计和定位，再给出修复建议
- 如果用户要求“直接修”，先完成一轮最小闭环验证，再修改
- 复盘结论必须基于代码和产物双证据，不能只凭曲线形状主观判断

## 核心产物

复盘时优先读取下列文件：

- `backtest_outputs/qmt_roll_statistics.json`
- `backtest_outputs/qmt_roll_daily_equity.csv`
- `backtest_outputs/qmt_roll_trades_2020_2026_04.csv`
- `backtest_outputs/qmt_roll_position_changes_2020_2026_04.csv`
- `backtest_outputs/qmt_roll_entry_risk_diagnostics_2020_2026_04.csv`
- `backtest_outputs/qmt_roll_professional_dashboard.html`
- `backtest_outputs/qmt_roll_trade_review.html`

同时必须检查关键代码：

- `examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
- `examples/portfolio_backtesting/run_qmt_roll_backtest.py`
- `examples/portfolio_backtesting/run_qmt_alignment_backtest.py`

## 标准命令

如果需要先刷新产物，再执行：

```bash
PYTHONPATH=/Users/bytedance/Desktop/person/vnpy \
/Users/bytedance/Desktop/person/vnpy/.py311/bin/python examples/portfolio_backtesting/run_qmt_roll_backtest.py
```

## 标准流程

### 1. 先确认当前口径

开始复盘前，先核对当前代码版本的这些关键口径：

- 是否是 `SameDayCloseBacktestingEngine`
- 当前止损口径是“收盘判断”还是“盘中触发”
- `calculate_price()` 是否使用了 `execution_price_overrides`
- `update_trade()` 是否会回写真实成交价
- sizing 是不是基于真实账户权益
- `qmt_roll_trade_review.html` 是否是当前最新产物，而不是旧版本文件

如果这些前置口径没确认，后续结论容易错。

### 2. 审查主结果是否自洽

先从 `qmt_roll_statistics.json`、`qmt_roll_daily_equity.csv` 和 `qmt_roll_trades_2020_2026_04.csv` 提取：

- 初始资金
- 期末权益
- 总收益
- 最大回撤
- Sharpe
- 总成交笔数

然后验证以下两条恒等式：

- `balance = capital + cumulative(net_pnl)`
- `net_pnl = holding_pnl + trading_pnl - commission - slippage`

如果两条不成立，优先判定为“结果口径有 bug”，不要继续做主观策略分析。

### 3. 审查成交与净值是否一致

需要确认：

- `trades.csv` 的开平仓价格是否合理
- `daily_equity.csv` 中的当日 `holding_pnl`、`trading_pnl`、`slippage` 是否能解释净值变化
- 当用户质疑某一天净值异常时，必须把当日成交、收盘价、持仓盈亏和交易盈亏拆开说明

如果用户指定某几天或某几笔交易，优先做“点审计”。

### 4. 审查止损触发链路

必须把止损分开审：

- `prev2day stop`
- `base stop`
- `layer stop`
- `MA20` 趋势止损
- `RSI partial exit`

每次复盘至少要回答以下问题：

- 触发条件使用的是 `close`，还是 `high/low`
- 成交价使用的是 `close`，还是 `stop/open`
- `exit_reason` 是否和真实触发条件匹配
- 动态止损是否真的更新到了当前状态，而不是还在用开仓初始 stop

如果用户说“感觉这笔不像止损”，必须同时检查：

- 代码触发路径
- 当日 K 线
- 风险快照里的止损价
- 最终成交价
- `exit_reason`

### 5. 审查风险快照是否可信

必须确认 `entry_risk_diagnostics` 里的这些字段语义是否正确：

- `estimated_equity`
- `limited_balance`
- `planned_entry_price`
- `filled_entry_price`
- `entry_price`
- `stop_price`
- `stop_distance`
- `risk_per_contract`
- `actual_margin_amount`

如果 `entry_price`、`filled_entry_price`、真实成交价对不上，要明确指出是“计划价”问题还是“真实成交同步”问题。

### 6. 审查复盘页是否误导

需要确认 `qmt_roll_trade_review.html` 是否展示了当前应有信息：

- MA5/10/20/40
- BOLL
- 动态 `prev2day` 止损线
- 成交点
- `exit_reason`
- 风险卡片里的真实开仓价/计划开仓价

如果复盘页展示不完整或会误导用户，必须指出“是展示问题，不一定是策略逻辑问题”。

### 7. 当用户指定单笔交易时的固定模板

若用户指定某笔交易，应按下面顺序回答：

- 开仓时间、合约、方向、手数、真实成交价
- 风险快照：计划开仓价、真实开仓价、止损价、风险金额、保证金占用
- 对应窗口 K 线：开仓日、平仓日、关键 high/low/close
- 平仓原因：`exit_reason`
- 为什么会在这一天、这个价格平仓
- 这笔是否按当前代码预期执行

### 8. 隐藏 bug 排查清单

每次完整复盘时，至少要扫下面这些典型隐藏问题：

- 策略内部权益与引擎真实权益是否漂移
- `update_trade()` 是否真的用真实成交回写状态
- `entry_price` 是否仍然停留在计划价
- `exit_reason` 是否是强绑定，还是近似匹配
- 止损触发顺序是否符合语义
- `prev2day` 动态止损是否被别的 stop 提前抢走
- 复盘页中的线和标签是否与真实逻辑一致
- 用户当前打开的是不是旧版 HTML/CSV 产物

如果发现 bug，优先区分：

- `结果层 bug`：会影响净值、收益、回撤
- `解释层 bug`：主要影响复盘页、标签、风控诊断字段

### 9. 修复后回归验证

如果在复盘过程中顺手修了 bug，必须重新执行主回测，并重新核对：

- `statistics.json`
- `daily_equity.csv`
- `trades.csv`
- `entry_risk_diagnostics.csv`
- `trade_review.html`

至少做以下回归检查：

- 净值恒等式通过
- `Close` 成交 `exit_reason` 无空值
- `filled_entry_price` 已回填
- 样本内抽查 `prev2day stop` 与 `base stop` 至少各 1 笔

## 结果输出模板

最终建议按这个结构回答：

- `已检查`
  - 列出看了哪些代码和哪些产物
- `主结论`
  - 结果是否可信
  - 当前是否存在 bug
  - 是结果层问题还是解释层问题
- `交易与净值`
  - 是否自洽
  - 是否发现异常日或关键交易
- `止损与执行`
  - 当前止损是如何触发和成交的
  - 是否按预期执行
- `发现的问题`
  - 按严重级别列出
- `建议`
  - 是继续调参、继续复盘，还是先修 bug

## 典型结论措辞

可直接复用以下表达风格：

- “净值总账自洽，但止损标签和动态止损口径不一致，属于解释层 bug。”
- “这版收益变化不是单纯策略表现变化，而是成交价/权益同步修复后，回测口径更真实。”
- “当前 `prev2day` 触发逻辑与复盘页展示已对齐，可以继续做策略层优化，而不是继续修 bug。”

## 调用示例

以下说法都应触发本 skill：

- “你整体复盘一下交易和净值变化和止损触发，看看是否有什么隐藏 bug”
- “帮我审计一下这版回测结果靠不靠谱”
- “检查这几笔交易是不是按预期执行”
- “看下止损是不是生效了，净值算得对不对”
- “复盘一下回测，确认策略有没有 bug”
