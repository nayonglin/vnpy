# Stage229 真实账户定量版本部署前检查

- line_id：futures_trend_stage819_intraday_rules
- 日期：2026-09-08 13:55（北京时间，检查记录）
- 用户请求：按技能部署到实盘。
- 结论：`deployment_blocked_before_activation`；不将用户部署授权当成绕过安全闸门的授权。
- 是否重要突破：否；是否回测/调参：否。

## 已核验

- 读取实盘执行SOP、自动化启动SOP、工作模式、研究registry、当前配置及Stage228记录。生产入口以当前生产事实和Stage948原子激活约束为准，不使用旧Stage930标签复制安装。
- 当前候选仍为 `codex/live-broker-account-sizing` 的未提交本地补丁；生产checkout HEAD仍为 `d492ee072aa5a9d71477235d79f17d2a5db59db3`，tracked状态干净。
- 当前代码仍显式拒绝重定量全平的跨日历史覆盖缺口：`resized_close_overnight_coverage_missing`。保护性拒绝不能代替跨日退出功能验收。
- 旧sent缺新审计时仍要求明确迁移：`broker_sizing_sent_legacy_audit_migration_required`。本次未评估或改写真实spool记录，不声称某笔线上委托已经命中此条件。
- 本地重新执行两项负向测试，2 passed，2.47秒：跨日重定量平仓被拒绝、旧sent必须迁移。测试通过证明闸门生效，不是证明部署可放行。
- 测试命令：`LANGUAGE=zh_CN OFFICIAL_LIVE_OUTPUT_DIR="$PWD/.test-output" QMT_BACKTEST_ALLOW_NON_PROJECT_TRADER_DIR=1 .py311/bin/python -m pytest -q 'tests/test_stage931_broker_sizing_gate.py::test_resized_close_rejects_unproven_ownership[overnight]' tests/test_sent_open_reconciliation.py::test_legacy_sent_requires_explicit_migration`。

## 外部资料与判断

- 核对 [vnpy_ctp官方仓库](https://github.com/vnpy/vnpy_ctp)；当前上游接口/安装说明不能替代本地固定CTP runtime、账户归属及生产发布证明，本次不升级SDK。
- 关键否决依据来自候选自身代码与SOP，不是网上资料推断。

## 未执行及后续

- 未commit/push，未调用Stage948安装/激活，未改production checkout、manifest、授权、launchd或spool；未重启、未停止现有实盘进程。
- 未连接CTP，未查询新鲜账户/持仓，未调用下单或撤单API。本次并未取得运行进程、月度AI池、数据就绪、券商账户或交易许可的新证明；上游检查已阻塞，不继续扰动生产。
- 先补齐跨日/拆单全平的可验证归属闭环和旧委托/旧持仓迁移，再进行完整回归、独立评审、固定发布版本及生产qualification/data-readiness/原子激活验收。
- 开始与结束反思：不过拟合，未改变alpha或搜索参数；继续有价值，应先保证真实仓位可安全退出，而非带着已知退出限制激活。
