# Task 1: Stage174 close 后 native 读取边界修复报告

时间：2026-08-03 16:32 CST
基线提交：`3bb0aae881baf7d7b03a1ea325b08f34c4dc1f27`

## 变更

- 新增 `_frozen_broker_trading_day(summary)`；它只清理有效连接代际已写入
  `summary["broker_trading_day"]` 的 Python 值，不接收或调用 `TdApi`。
- `_run_probe()` 在 `main_engine.close()` 后只通过该 helper 取得交易日，移除了
  `getTradingDay` 原生兜底读取。
- 新增源代码边界测试、冻结值 helper 测试；增强慢回调重连 fake，使
  `FakeMainEngine.close()` 后 `FakeTdApi.getTradingDay()` 立即抛错并计数，断言
  `_run_probe()` 返回后该计数为零。
- 未变更 alpha、信号、下单数量、止损重试、报撤单、vnpy_ctp、生产连接或 launchd。

## RED 证据

命令：

```bash
.py311/bin/python -m pytest -q \
  tests/test_stage174_query_bundle.py::Stage174ReadonlyQueryBundleTest::test_run_probe_never_reads_native_trading_day_after_close
```

原始结果摘要：退出码 `1`，`1 failed in 1.83s`。精确失败断言：

```text
E AssertionError: 'getTradingDay' unexpectedly found in '...\n        broker_trading_day = _clean_ctp_text(\n            summary.get("broker_trading_day")\n            or getattr(td_api, "getTradingDay", lambda: "")()\n        )...'
```

## GREEN 验证

指定命令：

```bash
.py311/bin/python -m pytest -q \
  tests/test_stage174_query_bundle.py::Stage174ReadonlyQueryBundleTest::test_run_probe_never_reads_native_trading_day_after_close \
  tests/test_stage174_query_bundle.py::Stage174ReadonlyQueryBundleTest::test_frozen_broker_trading_day_never_falls_back_to_native \
  tests/test_stage174_query_bundle.py::Stage174ReadonlyQueryBundleTest::test_mocked_ctp_slow_callbacks_rebuild_full_snapshot_after_reconnect
```

原始结果摘要：退出码 `0`，`3 passed in 4.28s`。

补充回归命令：

```bash
.py311/bin/python -m pytest -q tests/test_stage174_query_bundle.py
```

原始结果摘要：退出码 `0`，`22 passed in 5.43s`。

机械边界检查：

```bash
rg -n "main_engine.close|getTradingDay" \
  examples/portfolio_backtesting/run_ctp_stage174_readonly_probe.py
```

结果仅有两处：`1876: td_api.getTradingDay()`（有效连接代际冻结时）和
`1960: main_engine.close()`；`getTradingDay` 位于 close 之前。

## 自审

- TDD：先加入源边界测试并观察到预期 RED；随后实施最小 helper 与 fallback 替换，再观察 GREEN。
- 生命周期：close 后不再对 TdApi 做交易日读取；集成 fake 的 post-close 调用计数为 `0`。
- fail-closed：冻结值不存在时 helper 返回空串，既有 `broker_query_bundle.complete` 的
  `and broker_trading_day` 条件仍会拒绝不完整 bundle。
- 范围：未触碰正常 `main_engine.close()`、CTP runtime、生产状态、launchd 或任何策略逻辑。
- 过拟合反思：否。本修复只消除关闭后的 native 生命周期越界，测试覆盖源码边界、纯冻结输入和重连集成边界，没有优化任何市场结果。
- 继续价值反思：是。该变更把潜在 native use-after-close 从隐蔽崩溃路径改为稳定的 fail-closed 数据结果。

## Commit

提交信息：`fix(stage174): avoid native reads after close`。
