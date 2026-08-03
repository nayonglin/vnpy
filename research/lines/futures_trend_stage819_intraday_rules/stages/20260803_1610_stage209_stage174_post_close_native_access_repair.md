# Stage209 Stage174 收市后 native 访问边界修复回归记录

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：正式只读资格认证前的候选修复验证；未连接 CTP、未触发生产执行。
- 记录时间：2026-08-03 16:37 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy_stage179_production_live` / `codex/stage200-production-reliability-repair`
- 阶段性质：Stage174 原生生命周期边界修复的静态与完整回归记录。
- 是否重要突破：否；这是确定性稳定性修复，不是策略能力或收益突破。
- 是否触发 A/B：否；未修改 alpha、策略或资金配置。

## 外部调研与判断

- 参考资料：本阶段不开展外部策略调研；严格复用 Task 1 已确认的 RED/GREEN 生命周期事实。
- 我的判断：根因是 `TdApi::getTradingDay()` 在 `main_engine.close()` 后仍可能被读取。应只使用有效连接代际中已冻结到 Python `summary["broker_trading_day"]` 的值；缺失时保持空值，由既有完整性条件 fail-closed，而不是对已关闭 native 对象回退读取。

## 本次变更

- 改动时间：2026-08-03 16:32 CST（Task 1 修复），2026-08-03 16:37 CST（本次完整回归与记录）。
- 新增脚本：无。
- 修改脚本：`examples/portfolio_backtesting/run_ctp_stage174_readonly_probe.py`，以 `_frozen_broker_trading_day(summary)` 仅清理 close 前冻结值；`tests/test_stage174_query_bundle.py`，新增源码边界、冻结值与 close 后 fake 原生调用计数覆盖。
- 删除脚本：无。
- 新增参数：无。
- 修改参数：无。
- 删除参数：无。
- 未变更：alpha、信号、下单数量、止损重试、报撤单、订单语义、vnpy_ctp、CTP runtime、生产连接、launchd 与所有 fail-closed 门禁。

## RED/GREEN 与回归验证

### Task 1 RED

命令：

```bash
.py311/bin/python -m pytest -q \
  tests/test_stage174_query_bundle.py::Stage174ReadonlyQueryBundleTest::test_run_probe_never_reads_native_trading_day_after_close
```

结果：退出码 `1`，`1 failed in 1.83s`；失败断言确认 close 后源码仍包含 `getTradingDay` native 回退读取。

### Task 1 GREEN

命令：

```bash
.py311/bin/python -m pytest -q \
  tests/test_stage174_query_bundle.py::Stage174ReadonlyQueryBundleTest::test_run_probe_never_reads_native_trading_day_after_close \
  tests/test_stage174_query_bundle.py::Stage174ReadonlyQueryBundleTest::test_frozen_broker_trading_day_never_falls_back_to_native \
  tests/test_stage174_query_bundle.py::Stage174ReadonlyQueryBundleTest::test_mocked_ctp_slow_callbacks_rebuild_full_snapshot_after_reconnect
```

结果：退出码 `0`，`3 passed in 4.28s`。

Task 1 补充回归命令：

```bash
.py311/bin/python -m pytest -q tests/test_stage174_query_bundle.py
```

结果：退出码 `0`，`22 passed in 5.43s`。

### 本次规定静态验证

命令：

```bash
.py311/bin/python -m py_compile \
  examples/portfolio_backtesting/run_ctp_stage174_readonly_probe.py \
  examples/portfolio_backtesting/qmt_roll_official_live_late_retry_fill.py
```

结果：退出码 `0`，无输出。

### 本次规定完整回归矩阵

命令：

```bash
.py311/bin/python -m pytest -q \
  tests/test_stage174_query_bundle.py \
  tests/test_official_live_late_retry_fill.py \
  tests/test_stage904_durable_state_integration.py \
  -p no:cacheprovider
```

结果：退出码 `0`，`111 passed, 40 subtests passed in 8.12s`。

## 回测/归因参数

- 数据区间：本次未运行回测，不新增或修改结果。
- 账户规模：本次未运行回测，不新增或修改结果。
- 成本口径：本次未运行回测，不新增或修改结果。
- 样本过滤：本次未运行回测，不新增或修改结果。
- 策略/归因口径：本次未运行回测，不新增或修改结果。

## 结果

- 期末权益：本次未运行回测，不新增或修改结果。
- 总收益：本次未运行回测，不新增或修改结果。
- 最大回撤：本次未运行回测，不新增或修改结果。
- Sharpe：本次未运行回测，不新增或修改结果。
- 总滑点：本次未运行回测，不新增或修改结果。
- 总交易次数：本次未运行回测，不新增或修改结果。
- 胜率：本次未运行回测，不新增或修改结果。
- 其他关键指标：静态编译 `0` 错误；规定回归矩阵 `111 passed, 40 subtests passed`。

## 风险、资格与回滚边界

- 资格状态：尚未声明已完成资格认证，尚未生产激活；本次不构成 CTP 连接、报撤单或生产授权。
- 风险控制：若 close 前没有有效 `broker_trading_day`，helper 返回空字符串，既有 `broker_query_bundle.complete and broker_trading_day` 条件继续拒绝不完整 bundle，保持 fail-closed。
- 回滚边界：仅回滚本候选中的 lifetime helper 与对应测试；不得通过回滚绕过既有 query-bundle 完整性、只读账户/持仓或其他 fail-closed 门禁。生产状态、launchd、CTP runtime 与订单状态均不在本次变更范围。

## 输出文件

- report：本记录。
- summary：无。
- orders：无；未生成或提交订单。
- daily：无。
- quality：`git diff --check` 通过；规定回归矩阵通过。

## 结论

- 本阶段结论：修复将收市后 `TdApi::getTradingDay()` 的 native 读取改为只消费 close 前冻结的 Python 值；完整规定矩阵通过，候选可供独立审查。
- 是否进入下一步：是，限于独立审查与后续正式只读资格认证流程；不等同于资格认证或生产激活。
- 下一步：由具备授权的流程按 SOP 在隔离的只读资格认证环境验证；任何 gate 异常保持 fail-closed。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：修复约束 native 生命周期，不依赖行情样本、品种或收益参数。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：它解除正式只读资格认证的确定性崩溃，但仍保留全部 fail-closed 门禁。

## 合入建议

- 是否更新本线 `LINE.md`：否；本次为候选修复回归记录，待合入者统一整理。
- 是否更新 `research/registry.md`：否；不改变研究线状态或生产默认路径。
- 是否追加根目录 `memory.md/back_log.md`：否；尚未资格认证、未生产激活，且非跨线重要合入。
