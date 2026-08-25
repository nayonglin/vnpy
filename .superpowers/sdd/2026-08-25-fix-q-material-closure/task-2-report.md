# Task 2：正式物料自动导入闭包修复报告

时间：2026-08-25 20:40 CST

## 改动

- 在正式 `DEFAULT_CRITICAL_FILES` 中显式纳入 `examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`。
- `_cli_prepare` 继续将全部 critical files（包括 tests、Skills、shell 与 plist）作为 `declared_paths`，但只将 `examples/portfolio_backtesting/*.py` 作为 `discover_materials` 的静态分析入口。
- 新增真实正式 critical-file 集回归：通过 `_cli_prepare` 捕获实际 `DiscoveryResult`，验证库存包含核心策略及其本地 `main_contract_mapping.py`、两个 AI runtime 模块；同时验证测试和 Skill 仍被声明，且没有 tests 来源的动态导入 blocker。

## TDD 证据

- RED：`/Users/bytedance/Desktop/person/vnpy/.py311/bin/python -m pytest tests/test_official_strategy_material_release.py -k cli_prepare_discovers_core_strategy_local_import_closure -q`
  - 失败，断言核心策略与其本地依赖不在 discovery inventory；当时 `_cli_prepare` 使用 `entrypoints=()`。
- GREEN：同一测试在实现后通过，`1 passed, 17 deselected`。
- 实测真实默认集：80 个生产 Python 入口、156 个声明路径、237 个 inventory 路径、0 个 blocker；核心闭包、测试声明路径与 Skill 声明路径均存在。

## 验证边界与 concern

- 最小新回归测试最终通过；`git diff --check` 通过。
- 扩展聚焦套件首次未设置 `PYTHONPATH=examples/portfolio_backtesting`，收集阶段报 `ModuleNotFoundError: qmt_roll_strategy_material_discovery` / `qmt_roll_strategy_material_manifest`；这是该 worktree 的测试环境前置条件，不是本修复断言失败。
- 带该 `PYTHONPATH` 的扩展套件已启动，但因主代理要求立即收敛而被终止，未取得完整汇总；由主代理复验。未发布、未写生产目录、未连接 CTP，order/send/cancel 均为 0。
- concern：入口筛选故意仅覆盖默认清单中的 `examples/portfolio_backtesting/*.py`。将来若正式运行时 Python 入口迁到其他目录，必须同步纳入该默认清单和筛选规则，否则静态闭包不会从新目录开始发现；发布器仍会因发现到的 blocker 保持 fail-closed。
