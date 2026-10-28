# Stage032 Task2 日K加仓适配器实施审计

- line_id：`futures_weekly_formal_no_half_r`；2026-10-28 16:50（Asia/Shanghai）。
- 范围：仅本线新增 adapter、测试及本md/json，不改冻结源码、LINE、registry或生产；不commit，不金融回放。
- 是否重要突破：否。实现就绪不等于收益有效；独立预审及A/C金融结果由root负责。

## 实施结果与接口

`daily_addon_strategy_class(base,weeks,calendar,epoch_lookup,enabled=True)`内部包装Stage029v2；输入原正式base。禁用直接返回原Stage029v2类，只附enabled=False标记，没有新callback。`daily_addon_engine_class(base)`包在历史引擎外层，仅override `_fill_order`；保留原epoch核验、成交时钟、跨品种顺序和父订单成交。`audit_daily_addon(strategy,frames=None)`核验实际次数、加仓fill方向/手数/stop和全真实成交分片数量守恒。

导出6列表：events、decisions、rounds、allocations、snapshots、guard_failures（前缀daily_addon_）。allocations每个真实fill可以分成base/daily_addon两条，字段为trade_id/order_id/vt_symbol/product_vt_symbol/trading_date/datetime/direction/offset/volume/price/sleeve/round_id/addon_id/reason/entry_price/stop_price；offset使用open/close小写，direction使用long/short。真实fill的volume分片严格相加回原成交。A原wrapper无这些列表，runner以getattr([], default)导出空表。

## 裁决及理由

1. 使用新kind=`stage032_daily_addon`的PositionLayer承担真实净仓、目标、保证金、cluster和强平风险，独立实际fill账本保留归属。否决overlay，因为不能检验真实资金反馈。
2. 周动态止损、prev2day、layer技术检查局部隐藏tag；父全平前恢复tag，避免漏平。普通reconcile仍看到完整layer量。tag从未启用旧add/donchian/post_quality全局锁盈。
3. 加仓止损与技术状态独立；其PnL进入账户，单独加仓退出不喂给父层胜负连串及品种方向alpha记忆。父仓本身关闭的统计仍走原代码。
4. roll先平tag再走父roll，父roll previous_volume只含底仓；保留同一逻辑round次数，清上涨序列；新约须有真实底仓和同epoch连续数据。
5. 当日父循环/安全处理完成后才生成日K加仓；所有pending上锁。下一交易日真实open复核stop、epoch、预算后才fill计次。收盘stop严格小于；开仓当日可触发；退出真实成交日close可重新作为第1上涨日。
6. D3不能读取未来close更新风险。逐单D2冻结预算不足以保证同批合计安全，独立预审的双symbol反证已证实。现同批账本补齐各快照遗漏的后续pending预留，按原执行顺序登记批准价占用，取消释放，cluster独立记增量。父普通订单成交不新增拦截；其真实开盘margin差额仅扣后续addon容量。当前addon同约底仓按已知open重估margin；其他品种未观测open/close不读。权益上限保留D2冻结口径，属于保守准入，不因当日未实现盈利扩大额度。
7. 对实际1手再次执行heat整数gate，不能先算多手可容纳量再直接截为1而绕过取整。固定手数、次数、两上涨天和止损天数均不调参。

## TDD与验证

先写13测试，执行得到13个明确缺实现失败，再实施。后续针对真实单手heat、开盘冻结risk/broker/incremental/heat容量、D3事件日期、共享预算/取消释放、显式close原因及已持底仓跳空逐项RED→GREEN。初次heat fixture使用了错误mapping分隔和缺drawdown压力，已修fixture并撤掉单手补丁重新重现RED后恢复GREEN，未把无效fixture失败当证据。

最终新adapter **28/28通过**；Stage029旧止损/准入回归 **48/48通过**。独立共享预算反证修复后得到 `[False, True]`，`confirmed_violation=false`。预审另行检验真实父update_trade的混合全平PnL/成本/归属；其签字由root管理，本文不代签。尚未运行金融回放或全仓CI；root负责最终研究线全回归。

命令（工作目录为本研究worktree）：

```sh
MPLCONFIGDIR=/private/tmp/stage032-mpl PYTHONDONTWRITEBYTECODE=1 PYTHONPATH='.:/Users/mac/Documents/Codex/fian-handoff-20261014/vnpy_handoff_20261014/vendor:examples/portfolio_backtesting:research/lines/futures_weekly_formal_no_half_r/tools' .py311/bin/python -m unittest discover -s research/lines/futures_weekly_formal_no_half_r/tools -p test_stage032_daily_addon.py -q
```

旧回归使用相同环境，pattern=`test_stage029_week_close_exits*.py`。

## 调研、风险与继续价值

沿用已确认设计中的Backtrader完成bar/次bar执行原则与vn.py官方组合引擎（https://github.com/vnpy/vnpy_portfoliostrategy/blob/main/vnpy_portfoliostrategy/backtesting.py），实际实现以本机冻结源码消费者逐项核对。判断：多周期与tag思路有实现价值，不能把规则直觉或代码通过测试视为信号有效。原日K开盘模型并不提供分钟报价、容量或可成交性证据。

开始/结束过拟合判断：**仍有样本内开发风险**，此次仅固定规则实现和反例修复，没有金融结果或参数扫描，修复不构成救参。继续价值：**有**，完成独立预审后值得用户授权的一次2020年至今同源A/C；没有晋级或激活结论。

新增参数：独立addon两上涨日、每次1手、每round最多2次、同时最多1笔、固定前2日low。修改/删除原策略参数：无。新增/修改/删除金融回测结果：均无；期末权益、收益、回撤、Sharpe、滑点、交易数、胜率：本任务未金融回放，不填数。TODO：独立预审最终签字、root A/C、结果独审与会计守恒。
