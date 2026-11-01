# Stage022 每日风险邮件纯组件候选交接

- 时间：2026-11-01 23:42（北京时间）。研究线：`futures_weekly_short_ma_slope_gate`。
- 性质：通知可见性与私有发件箱隔离修复；不属于策略突破版本。只交付可审查离线候选，不声明生产资格、激活、安装或已发送邮件。
- 作者边界：仅新增 daily_report.py / test_weekly19_daily_report.py，修改 friday_report.py / test_weekly19_friday_report.py；未修改runtime、pipeline、backend、LINE、manifest、注册表、alpha、Git/index或生产目录。

## 调研与判断

参考 [RFC5321](https://datatracker.ietf.org/doc/html/rfc5321/) 和 [CPython 3.11 smtplib源码](https://github.com/python/cpython/blob/3.11/Lib/smtplib.py)。判断：邮件传输结果不明确时保留发送尝试且禁止自动再次尝试，沿用已有私有原子outbox；不另造daemon、cron或SMTP客户端。日报扩展独立类别与日级主键，原Friday的API、周级主键及既有记录继续兼容。

过拟合：否。本次仅从已验证生命周期渲染通知与记录投递，不改变任何选品、alpha、风险条件、资金或委托行为；没有跑金融回测、调参或收益筛选。继续价值：是。能把部分成交、旧待执行和未知原因明确披露，避免把计划误作成交或把未知误作无风险。

## 精确接口与来源合同

```python
build_daily_risk_report(*, decision, data_receipt, account_key,
    material_release_id, rows, now, preview=True, blocking_reasons=()) -> dict
DailyMailOutbox(private_parent_0700).deliver(report, injected_sender) -> dict
```

- 输入decision必须为`weekly19.runtime-decision.v1`，账号、release、完成日和data receipt SHA精确一致；日报schema为`weekly19.daily-risk-report.v1`，`report_kind='daily_risk'`，`target_date=decision.trading_date`。缺/错源拒绝，来源blocked且没有事项时明确“不能确认”，不会伪报无风险。
- rows由root从已验证runtime投影，字段为vt_symbol、position_direction（原持仓long/short）、signal_date、next_execution_day、reason_code、planned_volume、filled_volume、status、close_lifecycle_id、intent_ids、fill_trading_dates、fill_date_coverage（complete/legacy_or_partial）。组件不自行读取账户、回报、历史AM或重跑策略。
- 同一lifecycle只计一项；精确重复可合并，冲突（包括原本会被日期过滤的旧完成项）拒绝。重试意图数量不累加计划手数。原多头显示卖平，原空头显示买平。
- 累计已成交只用已验证filled_volume；当日更新只用fill_trading_dates包含target_date，且不将累计量标成今日新增量。legacy/partial日期覆盖明确未确认。实际部分成交即使源status仍pending，也显示“部分成交；剩余待执行”，原status原样保留。
- reason中文和原码同时保留。未知原因仍是风险计划。prev2day_stop明确为前两根已完成周线保护价、完成周收盘确认；base_stop为动态保护线，不称固定2%亏损；0.4明确为标准化pressure阈值，不称保证金占比40%。周报只增加当前close项退出原因，不扩周累计schema。
- 日级key为profile/account/release/completed day/daily_risk。日报与周报同一周五可以共存，不改变旧Friday key。preview在任何outbox写入/锁/调用sender前返回preview_only；sent返回already_sent，sending/unknown返回delivery_unknown且换正文也不再次尝试。缺配置等保持既有blocked_before_send语义。目录0700、文件0600、flock/原子写/fsync与原outbox一致。
- 报告恒为production_qualified=False和actionable=False；报告与发送不授权委托、不增加E/Available、不确认补资。

## TDD与验证记录

1. 首次RED：`/private/tmp/weekly19_stage022_mail_component_red.log`，39项、18失败（daily尚不存在、周报未展示原因）；旧原用例继续保留。
2. 首次GREEN：`/private/tmp/weekly19_stage022_mail_component_green.log`，39项通过。
3. 补部分成交、周线说明、JSON形状反例RED：`/private/tmp/weekly19_stage022_mail_component_partial_red.log`，40项、2失败/2错误；随后GREEN：`/private/tmp/weekly19_stage022_mail_component_green_v2.log`，40项通过。
4. 生命周期先过滤漏冲突RED：`/private/tmp/weekly19_stage022_mail_component_conflict_red.log`，1项失败；修后最终组件GREEN：`/private/tmp/weekly19_stage022_mail_component_green_v3.log`，41项通过（19日报、22周报）。耗时0.058s。
5. 相关5模块回归：`/private/tmp/weekly19_stage022_mail_component_related_green.log`（历史文件名含green，但结果按实际记录）：80项、79通过/1失败，8.856s。唯一失败为root刚新增的`DailyMailIntegrationTests.test_unknown_delivery_is_explicit_error_and_does_not_resend`，期望pipeline抛错尚未落guard的正常TDD RED，已交root；作者没有修改pipeline迎合测试，也没有将该次称为全绿。root随后负责guard与重新验证。
6. 4文件compile(source)及尾部空格检查通过。单元测试只使用显式离线fixture、临时私有目录和注入sender；本作者没有调用真实SMTP、CTP、订单或资金API。

最终组件命令：

```sh
PYTHONPATH=tests:examples/portfolio_backtesting .py311/bin/python -m unittest tests.test_weekly19_daily_report tests.test_weekly19_friday_report -q
```

## 锁源

23:42起4文件LOCK，交root与独立reviewer；新发现先报告，再受控解锁，不悄改已锁source或测试。

| 文件（相对仓库） | SHA256 |
| --- | --- |
| examples/portfolio_backtesting/qmt_roll_weekly19_daily_report.py | abbecec123cb2be453ebc9e0cdeda88dc6e1f5bba78a660ddead2aa62d65083b |
| examples/portfolio_backtesting/qmt_roll_weekly19_friday_report.py | dcb41e2fc1a9dfc75873f9899988d8897b096a2e0d0597fad9ab463c2a2b3f59 |
| tests/test_weekly19_daily_report.py | 835009ba1ea5ab601e85d067fdb1ac112ad3b94a50be89f5336b8905b101f2ce |
| tests/test_weekly19_friday_report.py | 0116243246d5c27d8611a277e2a89809a0bce62e27f11a892d6a0a38ef725436 |

## 交接与限制

root负责实际verified runtime行投影、每天postclose-report调用、transport event_type区分、未知投递→CLI失败可见性、完整selected CI及新候选冻结；独立reviewer负责数据/语义/去重/文件权限/置信度反例。m0001/m0002及历史证据不可改。本组件没有自行更改生产安排，也没有宣称真实发送成功或完整实盘链路已通过。

## 原需求问句补齐与再次锁源（受控修订）

首次LOCK后root明确指出：总风险事项包含技术退出，不能替代回答“今日是否有风险组压力降仓新信号”。root授权仅解锁daily_report及其测试，Friday两文件保持原LOCK；不是策略条件变化。

- 明确新增一行“今日风险组压力降仓新信号：有N项 / 无 / 未确认”。只对new_signal且reason_code精确为risk_cluster_heat_deleverage及其long_/short_前缀计数；技术退出、forced_margin_deleverage和历史heat待执行不冒充今日新heat信号。
- 返回增加today_cluster_signal_status（present/none/unconfirmed）、today_cluster_signal_count（已识别精确项数）、today_unknown_reason_count（当日未知原因项数）。数据blocker或当日未知原因存在时，状态为unconfirmed；已识别项数只作部分证据，不假报总数或“无”。
- 新测试首次缺字段以KeyError RED记录于`/private/tmp/weekly19_stage022_mail_component_cluster_red.log`；改为明确断言后2项RED在`/private/tmp/weekly19_stage022_mail_component_cluster_red_v2.log`。最小实现后`/private/tmp/weekly19_stage022_mail_component_cluster_green.log`：43项通过（21日报、22周报），0.058s。compile与尾空格检查通过。
- 最终再次LOCK：daily_report.py **7218ed307ab50a6f8d338c7fa037e4f9232e27f432c2cb33142d765e6f3fad06**；test_weekly19_daily_report.py **8f27fd2da1121749162de61b16f587c6de1af9dd5e44ac7cadd83373cc6daefa**。Friday源码与测试仍为上表原SHA。上表首次版本及41GREEN仅保留历史，不冒算新版本资格。

## 独审排队决策P1修复与第三次锁源

时间：2026-11-01 23:55（北京时间）。独审`Stage022_review_queued_decision_tests.py`确认：真实Runtime._queue_pending_day虽有同源完成日receipt，但bars_queued=True/blocked_reason=unresolved_execution_lifecycle表示当天未执行on_bars；原组件可能把尚未评估显示为无新风险组信号。

root等待whole CI001完整结束并留存旧日志与source snapshots后，明确受控解锁仅daily_report及test_daily。未在CI运行期间修改critical。旧CI的系统沙箱错误由root处理，本作者不更改测试或执行源码来规避环境。

- 新增daily_strategy_not_evaluated blocker：bars_queued is True或blocked_reason精确等于unresolved_execution_lifecycle时，今日riskcluster为unconfirmed，中文明确当天策略尚未推进/今日新信号未评估；旧pending、累计真实成交及当日实际fill更新继续显示。空行时不伪报无风险。
- 不以reduce_only=True单独判断未评估；正常当日已计算close/heat的reduce_only仍显示present及精确数量。没有改Runtime、alpha、资金或发送幂等逻辑。
- 四边界作者RED：`/private/tmp/weekly19_stage022_mail_component_queued_red.log`，4项、3失败/1通过（正常reduce_only正例）；修后组件GREEN：`/private/tmp/weekly19_stage022_mail_component_queued_green.log`，47项通过（25日报、22周报），0.061s。compile与尾空格检查通过。
- 最终当前LOCK：daily_report.py **2b426e115be251f63d493c1efe64d1de687cdced3d07b368ccb2f122e6d4b3a5**；test_daily **30232803a468b5b41e1159fd2c8460337137aa516e22f900adf895510007d017**。Friday两文件保持dcb41e2f/01162432原完整SHA，未解锁。此前41/43项与旧SHA保留历史，不宣称覆盖当前源码。已交root和独审进行增量复验及新完整CI；本组件仍非生产资格证明。

CI001旧测试原字节补存：root已保存旧daily源码7218ed30...，作者仅向`stages/stage022_prequeue_fix_source/test_weekly19_daily_report.py`独立副本逆去刚新增4方法，严格核对为旧SHA **8f27fd2da1121749162de61b16f587c6de1af9dd5e44ac7cadd83373cc6daefa**。当前critical测试仍为30232803...且逐字未变；未通过回滚当前源码伪造旧证据。
