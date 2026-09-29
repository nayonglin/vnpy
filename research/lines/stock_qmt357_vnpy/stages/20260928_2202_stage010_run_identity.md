# Stage010 执行前身份冻结与失败产物门

- line_id：`stock_qmt357_vnpy`；时间：2026-09-28 22:02 CST。
- 范围：修复Stage009 P2，本agent转为有界实现者，不再担任此版本最终独立回测reviewer。
- 仅改 `qmt357_commit4ac255e/run.py`、`tests/test_cli.py`；不改策略、引擎、原数据、冻结快照、期货或共享LINE/registry。
- 参考与判断：沿用Stage008/009已核验的精确Git源码与真实vnpy迁移合同，仅补可审计运行状态，不改变alpha或行情语义。
- 使用TDD与writing-good-tests：先让真实买入后遇到无显式行动因子变化的fixture触发失败，观察旧runner丢失manifest，再实现；不通过mock替换成交或公司行为门。

## 变更

- 每次实际引擎构造/执行前，新建不可复用run目录，冻结 `code_snapshot.tar.gz`、`run_identity.json` 与初始 `manifest.json`。
- 固定identity包含run-id、代码SHA、输入快照及源SHA、参数、起止、来源scope、独立runtime与归档SHA；identity保持初始RUNNING状态，终态以manifest为准。
- 成功终态为COMPLETE且 `complete_period_result=true`；失败终态FAILED并保存异常类型/消息、失败日期、最后完整日期、完成日数、处理订单/成交计数、持仓数/证券，明确仅诊断非完整结果。
- 失败不发布完整summary/年度表/净值/report；发布阶段异常也清除本次新目录里的这些文件及其临时文件。不触及此前冻结目录或历史数据。
- 新增互斥必选入口 `--snapshot`（原股票只读）与 `--variant-snapshot`（本版本 `data/snapshots`）；按来源分别使用原loader/主agent新variant loader，不能把新快照写回原数据目录。
- 原资金、信号、分级止损、成交和guard参数无新增/修改/删除。

## 验证证据

- 第一轮RED：4 failed/3 passed。真实持仓因子失败没有manifest；成功manifest缺status；variant选项未识别和未互斥，均为预期缺功能失败。
- 第一轮GREEN：7 passed，10.84秒。
- 第二轮加入真实variant独立快照消费，以及发布阶段临时绩效残留检测：1 failed/8 passed，准确检出 `summary.json.tmp` 残留；最小清理修复后GREEN：**9 passed in 12.67s**。
- 最终命令：`QMT_BACKTEST_DISABLE_STARTUP_CWD_GUARD=1 .py311/bin/python -I -m pytest examples/stock_backtesting/qmt357_commit4ac255e/tests/test_cli.py -q --import-mode=importlib`，退出码0。
- 同一失败run-id重试拒绝，目录每个文件SHA保持一致；真实variant fixture只存在variant快照，无baseline拷贝，成功manifest绑定正确路径/SHA。
- `git diff --check`通过；原股票config/signals/strategy/engine四核心SHA仍与原9/24冻结manifest一致。
- 新runner SHA `3dc8cc604164a0796ea30544f9d1e376ad793d7f61a81535a03388a6dc914443`；CLI测试SHA `65169d666cd051c841ac7c037415b377118ba5a735090fc280fe7ce42a1d4dba`。
- 全股票套件按任务分工由主agent统一执行，本agent未宣称已独立跑全套。

## 结果与边界

- 未重新运行真实历史策略；只有合成测试fixture。无新的真实期末权益/收益/回撤/Sharpe/滑点/成交总数/胜率可发布。
- Stage008旧失败诊断未改写、未补造执行时SHA；本修复仅保障**未来新run**身份完整。
- 强杀/进程崩溃无法执行Python异常处理时，保留RUNNING身份而非伪造FAILED/COMPLETE；不可将RUNNING视为完整结果。
- 运行前后均无新增过拟合：只修复溯源与隔离，不改参数、不删异常股、不松数据门。
- 继续价值：有，失败仍可追溯；主agent全套验证与新的独立reviewer完成前，不据这些合成测试宣称真实长回测完成。
