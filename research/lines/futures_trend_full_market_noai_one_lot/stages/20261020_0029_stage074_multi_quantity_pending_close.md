# Stage074 多手待平仓数量守恒修复

时间：2026-10-20 00:29（Asia/Shanghai）。研究线：`futures_trend_full_market_noai_one_lot`。不是重要突破或收益优化版本，是取消一手封顶前必要的执行正确性修复。作者参与本模块实现，不能作为随后金融回放的独立审查者。

## 问题与方案

原生 RSI 部分平仓会先排待平仓 lot，再减少策略层。真实持仓 5 手、计划平 2 手时，剩余层应为 3 手，待平仓 2 手，实际持仓仍为 5 手。旧 reconcile 只保护“全部实际仓位已经排平”的情况，部分平仓时会把剩余层补回 5 手；随后生命周期或移仓平仓可重复排队，产生 7 手待平仓及重复暂估损益。

本次只新增 `tools/stage074_pending_close_quantity.py`，不修改旧文件。`PendingCloseQuantityMixin` 放在 Stage070 FeeStrategy MRO 最前，先于生命周期和旧候选类：

1. 有待平仓时，reconcile 保留剩余层，稳定边界校验 `剩余层数量 + 待平仓数量 = 实际持仓绝对值`，目标为带原方向符号的实际持仓减待平仓。
2. queue 校验本次平仓量不超过实际持仓减已有待平仓量，拒绝分数、布尔、负数或错误方向。此处不提前校验层守恒，因为原生函数先 queue 后减层；否则会误伤正常过渡。
3. 无待平仓时仍调用原生 reconcile。全部待平仓且层已 reset 的状态合法。原生 RSI 部分平仓、移仓、生命周期、费用及成交时序继续运行；没有停用 RSI，也没有改变开仓预算或周线门。

## 调研与判断

复核了仓库内原生 `_reduce_position_to_target`、`_queue_pending_close_lot`、`_sync_close_trade`、`_reconcile_state_with_position`、生命周期和 Stage003 的全平保护，以及本机真实 engine 的持仓更新和回调顺序。官方 [vn.py 组合策略模板](https://github.com/vnpy/vnpy_portfoliostrategy/blob/main/vnpy_portfoliostrategy/template.py) 作为实际持仓、目标持仓分离的参考；本地冻结实现及真实成交测试是本次结论依据。

判断：不是过拟合。修复来自数量守恒，与历史收益、品种、年份及参数搜索无关。有价值继续，因为多手下保留原生 RSI 部分平仓会实际触发这一状态，错误不能由一手时期的回放通过证明不存在。

## TDD 与验证

首次在产品模块不存在时运行同名测试，使用空 mixin 接入真实旧策略和引擎，11 项测试产生 13 个预期断言失败（2 项原生正常顺序测试已通过）。失败包括 3 手被补回 5 手、生命周期/移仓重复排成 `[2,5]`、真实部分成交后剩余层被补成 4 手，以及坏数量未被拒绝。修复后定向 13 项通过；再把同样 13 项完整运行在最终 Stage070 FeeStrategy/FullMarketDailyEngine MRO 上，最终共 26 项通过。

最终命令：

```text
PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/tmp/fian-risk05-mpl .py311/bin/python -m unittest discover -s research/lines/futures_trend_full_market_noai_one_lot/tools -p test_stage074_pending_close_quantity.py -v
Ran 26 tests in 0.051s
OK
```

覆盖：多空 RSI 减半、缺真实行情延迟与旧单重发、两次各一手真实成交、生命周期叠加清理与幂等、生命周期 5 手真实全平成交、移仓重复调用、完整待平仓层 reset、无待平仓正常 reconcile、queue-before-decrement 原生顺序、超实际量、超未排量、错误方向及不合法数量。没有金融全段回放，没有下载或修改旧输出。

## 参数与结果

新增、修改、删除的经济参数均无。新增内部错误检查前缀 `stage074_`；不修改 0.5% 公式、整数向下取整、原始止损、long 自身合约完整周K门、short 开仓规则及 RSI 开关。

新增、修改、删除的金融回测结果均无；期末权益、收益、回撤、Sharpe、滑点、交易次数、胜率本阶段均不适用。本阶段只有合成执行验证，不能推断收益或可生产部署。

源码 SHA256：`2c098f576d2dd7be1458a1f9973b70314e8604ff242aaf546e3b4fc490f50255`。
测试 SHA256：`f3c97bbdd8548a73830769201c6bbe41ecc6345cc39e4d571a485042263d686c`。

## 后续

Root 接入已确认 MRO 最前并纳入 manifest code hash；需完成全套回归及未参与实现者预审，再冻结唯一金融回放。回放结束必须由未参与金融实现的代理审查多手全生命周期、FIFO 费用/盈亏、实际持仓与所有平仓量及期末残仓；本作者不能独立认证自己的 Stage074。未修改 LINE、registry、Git、其他研究线或生产。
