# Weekly19 每日风险邮件实施计划

> For agentic workers: use executing-plans for the root pipeline work; the pure report/outbox component is delegated with exact file ownership. Tests precede implementation, followed by an independent whole-change review.

**Goal:** 用户已要求接入每日相关通知；沿此前提出且用户接受的字段，每个完成交易日明确有无风险降仓、中文原因、合约/手数及实际执行状态，周五保留信号补资邮件。

**Architecture:** 复用Stage947→weekly19的postclose-report任务（现有收盘报告时点）及SMTP transport，新增纯daily renderer和私有日级outbox；日报读已提交决策和broker-confirmed runtime，不重跑on_bars、不触发委托。周五原发件箱与补资逻辑保持独立，补上具体退出原因。

**Tech Stack:** 现有Python3.11、unittest、原子私有JSON状态与flock；不引入依赖。

**Spec:** 本文件“设计与边界”。本次设计直接落实上一轮明确的通知内容和用户本轮接入指令，不重复请求已给出的授权。

## 设计与边界

- 每日执行：只在postclose-report触发daily通知，数据日期为已接受completed decision的trading_date；节假日不重复旧日期。postclose-precompute原周五资金邮件逻辑保留。
- 日报主键：execution profile/account/material release/completed trading day/daily-risk类别；已发送不重复，sending/delivery_unknown不盲目重发；预览不调用SMTP、不占真实发送名额。
- 中文展示所有真实close意图，尤其risk_cluster_heat_deleverage与forced_margin_deleverage；未知原因显示“原因未确认”，不得当成“无信号”。零交易信号只有数据完整且决策同源时才能明确“无”。
- 日报区分当日新平仓计划、历史待执行和当日原始回报支持的成交更新。volume/filled/status来自原close lifecycle，重试子单按lifecycle聚合，不能累加成重复手数。平仓order的direction不等同原持仓方向，正文明确买平/卖平或持仓方向。
- 引擎意图新增exit_reason元数据，仅来自同信号日/同合约原始退出diagnostic；不改任何alpha/风控条件、资金规则、冻结策略包、真实执行权限。
- 报告任务可消费原始执行回报并提交runtime状态；不重算历史决策、不得把planned_volume当filled，不因报告发送修改原decision/decision_state。
- 无生产安装/CTP/真实SMTP本轮调用；周一09:00既有只读核验约定保留。新关键源码应冻结为新物料，m0001/m0002不改写；不能把离线通过称作生产已生效。
- 参考：RFC5321 https://datatracker.ietf.org/doc/html/rfc5321/ 与CPython smtplib https://github.com/python/cpython/blob/main/Lib/smtplib.py 。判断：复用已具备私有权限/原子写/发送不明去重的发件箱，优于新增独立cron或仅依赖邮件Message-ID。

## Review Focus

1. 非周五/无信号也有日报；缺或错源决策不得伪报无信号。
2. 原始持仓方向与平仓委托方向相反，不能展示反。
3. 部分成交、撤拒后重试、同生命周期多意图不得重复量；成交仅凭真实回报。
4. 同日重复任务、两个账户、日报与周报并存、SMTP结果不明均有正确去重边界。
5. 报告只消费并更新已证明执行状态，原决策/资金建议/冻结alpha不变。

## Task 1 纯报告与发件箱（委派）

Files: 新增examples/portfolio_backtesting/qmt_roll_weekly19_daily_report.py及tests/test_weekly19_daily_report.py；修改qmt_roll_weekly19_friday_report.py（仅退出原因展示/发件箱扩展点）、tests/test_weekly19_friday_report.py。

Interface: build_daily_risk_report(*,decision,data_receipt,account_key,material_release_id,rows,now,preview=True,blocking_reasons=()) -> report dict；DailyMailOutbox(parent).deliver(report,sender)。rows由pipeline从已验证runtime投影：vt_symbol,position_direction,signal_date,next_execution_day,reason_code,planned_volume,filled_volume,status,close_lifecycle_id,intent_ids,fill_trading_dates。

- [x] 写失败测试并保留RED证据：非周五/有无信号/未知原因/错源/部分成交/重试聚合输入、日级去重、不同账户和周报分离、preview/unknown不重发。
- [x] 最小实现纯renderer及安全复用outbox，周报补上reason中文与原码。
- [x] 运行定向测试，留GREEN证据；作者不提交、不发送真实邮件。

## Task 2 接入现有日级报告链路（root）

Files: 修改qmt_roll_weekly19_runtime.py（仅退出原因元数据）、qmt_roll_weekly19_live_pipeline.py、qmt_roll_weekly19_local_backend.py；新增tests/test_weekly19_daily_mail_pipeline.py，必要时更新原pipeline fixtures。

- [x] 写非周五report返回daily mail的RED测试；原decision不变、预览无SMTP/委托、重复发送去重、旧pending/真实partial回报投影、元数据当日原因绑定、backend event_type路由。
- [x] 实现close reason元数据、按lifecycle合并的风险行投影、每天report刷新执行状态但不重跑策略、daily sender路由。
- [x] 定向回归；生成“有信号/无信号/部分成交/原因未确认”离线邮件样例，不访问真实账户。

## Task 3 独审、资格边界与交付（root＋独立reviewer）

- [x] 独立审查data/logic/confidence/bug、源SHA和SMTP/CTP/API计数为0；修复P0/P1/P2，保留失败证据。
- [x] 运行正式weekly19选定全套CI及关键源漂移核验；只允许声明的通知组件变化，冻结alpha不变。
- [x] 中文stage、LINE及周一安装handoff更新，保存本地提交；新不可变候选物料freeze/verify/fresh-clone。实际资格/激活/production仍由周一真实只读证据闭环。
- [x] 结束说明：过拟合否（不改决策规则）；继续价值是（让每日风控可见）；交付文件样例和实际尚未激活边界。
