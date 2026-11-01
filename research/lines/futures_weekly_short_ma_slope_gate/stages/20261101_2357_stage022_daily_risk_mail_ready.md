# Stage022 周线19品种每日风险通知邮件

- line_id：futures_weekly_short_ma_slope_gate。
- 记录时间：2026-11-01 23:57（Asia/Shanghai，封账结果在最终回执绑定）。
- 工作区：weekly19-official-20261031/fian；分支codex/weekly19-official-20261031。
- 阶段性质：实盘安装准备中的通知功能补齐；非alpha优化、非金融回测。重要突破：否；A/B：不触发。
- 用户授权：本轮明确“每日也帮我接入一下相关通知邮件吧”；沿用既有实盘安装授权，CTP依约周一09:00后核验。未请求重复授权，未发送真实测试邮件。

## 外部调研与判断

参考RFC5321（https://datatracker.ietf.org/doc/html/rfc5321/）和CPython smtplib（https://github.com/python/cpython/blob/main/Lib/smtplib.py）。我的判断：沿用原SMTP通道、私有原子发件箱和投递不明去重，比新增cron或只凭Message-ID去重更适合现有执行架构。通知不改变策略决策，也不能作为实际成交或正式生产资格的证明。

## 变更

1. 新增qmt_roll_weekly19_daily_report.py：每日纯报告，直接回答当日风险组压力降仓新信号“有/无/未确认”；列出其他平仓、原因中文/原码、原持仓方向与买平/卖平、原计划手数、累计实际成交、剩余量及状态。未知原因、数据不全和策略尚未评估不得伪报无风险。
2. 新增独立DailyMailOutbox，主键为profile/account/release/完成交易日/daily_risk。同日重复任务不重复发送；preview不占真实发送名额；sending/delivery_unknown不自动重发；日报和周五补资邮件分别去重。
3. 原postclose-report标签每天调用日报，复用Stage947/现有SMTP，不新增定时任务。真实模式先刷新只读账户/成交，再消费已证明原始回报并原子提交runtime/funding，发信在提交之后。未调用process_completed_day/on_bars、未发布或授权委托；原decision及decision_state保持。
4. IntentEngine只新增通知exit_reason：要求同信号日、合约、Close与原持仓方向一致且原因唯一，缺失/冲突留未知。刻意保留旧intent_kind计算，避免在通知变更中改变旧执行分类；邮件不拿该旧kind推断原因。
5. 仅在真实apply_broker_fill全部绑定/重复/手数门通过后，保存close lifecycle的完整成交semantic及原rawSHA。投影核trade ID唯一、在原fills档案、首次rawSHA与semanticSHA、account/release/plan绑定和累计量；日期不从计划日推定。重试按原lifecycle合并，不累加各retry计划量。
6. 旧状态没有成交日期时明确legacy/partial未知；历史已完成但日期未知的事项保留待核对。<8192字节普通engine和压缩engine统一_decode，不误当成必须压缩。
7. 周五报告保留原资金建议/闸门，平仓行增加具体中文退出原因。前两周保护不是两日；pressure0.4不是保证金40%。不扩成全周历史回测或更改补资行为。
8. 投递unknown/阻断不冒报完成，daily pipeline明确抛错误使CLI失败退出；原子业务状态和outbox证据保留，重新运行也不盲目重发。
9. 发布清单增加新模块及两套测试；原288关键文件只改声明8项，新增3项，共291；资格所需套件90→92。同步实盘SOP和启动Skill的新候选通知说明，原m0001/m0002不改写。

新增策略参数：无；修改/删除策略参数：无。新增业务字段为exit_reason、fill_evidence及日报元数据，不修改风险预算、止损线、开仓过滤、资金或真实API权限。固定19、无加仓、空头底部20%、原风险档位和15万交易＋15万场外口径均保留。

## 验收过程与失败保留

- 先RED验证旧版周一mail=None、新退出原因/成交日期缺失；随后实现。错误日期篡改与legacy完成遗漏各先RED后修复；真实/部分成交/撤拒重试、方向及日级去重均有集成检查。
- readonly刷新及投递unknown各保留独立RED；定向五模块108项通过（后续补queued用最终全CI为准）。纯组件最终47项通过。
- 独审发现P1：bars_queued=True/blocked_reason=unresolved_execution_lifecycle时当天策略没有推进，原renderer会误写无信号；受控解锁daily/test修复，保留旧源码/测试原字节及RED。正常reduce_only不误判为未评估。
- CI001：完整92套件，2311通过/33失败/0跳过；无source漂移。错误均来自沙箱不可用的Darwin启动时钟、ps/PGID和vnpy日志路径。原log/XML/源锁保留，没有删测试或放宽断言。
- CI002：同一套完整测试在可读取本机时钟/进程组/日志的环境运行，源锁Stage022_implementation_lock_attempt002.json；92套件2348项全通过，0失败/错误/跳过，291源在前后及root复验均一致。CI record SHA 5879ee6f20bbc021e86ecc9c56aa96e8f70ae3ef0b3f06c57f3d2bcc49231f78。
- 独立复核：Stage022_review_acceptance.json accepted=true / PASS_WITH_LIMITATIONS，P0/P1/P2=0；720源/AST/m2实物、332 CI与样例及32独立专项通过，raw SHA77acbddd8f90ce4013fee1980026c361daea496220ba1bf88e6f517dc7c97ac8。root复验所有绑定证据与源，无金融回跑或实盘来源资格冒用。预审/RED/中间GREEN分开保留，不把预审accepted=false冒作最终通过。

## 可审阅输出

组件全部12份作者RED/GREEN日志已按原字节复制到stages/stage022_mail_component_logs/，不只依赖临时目录。

最终离线样例：artifacts/stage022_daily_mail_previews_attempt002/，8封均显著标注“合成数据，不是实际交易信号”；覆盖无信号、风险组压力、空头保证金降仓、历史部分成交待重试、未知原因、数据未就绪、周五补资与当日策略未评估。preview_manifest绑定生成器、fixture及renderer SHA。旧7封草稿与旧生成器均保留。

工具：tools/Stage022_selected_ci.py、Stage022_mail_previews.py。独审和来源记录均在本线Stage022_*；不改44品种或其他研究线。

## 财务与生产边界

新增/修改/删除回测结果：均无。本轮无行情下载、金融引擎回测、CTP连接、SMTP真实发信、order/send/cancel API或生产访问变更。既有Stage019净利22380、18轮/36成交等不变；单元fixture不是金融重跑。

当前新代码尚未实际安装激活。需要冻结新不可变候选物料（不能覆盖m0002），然后周一以真实formal readonly和release-bound资格继续激活、master、fresh clone、Stage948安装闭环。旧CURRENT/生产状态不得用开发checkout覆盖。新物料和接续入口由Stage022最终handoff记录。

## 反思与后续

- 运行前/后过拟合判断：否，没有新增alpha或根据历史收益调参；只补通知和来源元数据。
- 运行前/后继续价值判断：是，每日风控已有但原邮件仅周五，补齐能避免用户把未通知或尚未评估当无信号。
- 更新本线LINE及安装handoff；不改registry或根memory.md/back_log.md。独审、全CI和新候选实物验收后交付；实际发信和实盘激活仍需真实资格，不以离线mock通过冒称已生效。

## 2026-11-02 最终冻结与安装接续

- 实现提交52b825c4efe88b20b8a9a33116c755003f1c9ab9；干净冻结来源39913bc2821c47a485913f6d7b2d2631c19e19ab。
- 官方prepare/verify/精确confirmation commit得到m0003_20261102T001414+0800_39913bc2821c，release commit65594f6320f4c625892be534f750275c9667e315；381 payload，CI291子集逐项一致；manifest raw e1e6fb3a560f9bbaa2981b1ea347d424bddd9de6463ac0936ebb2906fa84b8a6，canonical d93332a5adbfc39b0b4fd808bfba33c0cde97c8e463c4e0db4a93fe73002defe。
- 独立clone --no-local核381 source/top/payload/mode、291锁源、31历史manifest与实际LFS内容/独立cache通过；m1/m2与CURRENT旧m8不变。首checkout缺少clone命令级LFS filter导致pointer被正确拒，失败证据保留，仅在clone命令级标准filter materialize后复核通过，没有安装工具或改global/source config。
- 本机stable仍d55887e1def72629fbfa310e439dc3a879969a14/CURRENT旧m0008，生产五件套仍缺，故新通知尚未激活、未证明实际发信。Stage022_m3_clone_receipt只证明本地候选实物，不是remote-master clone或生产资格。
- 新Stage022_installation_handoff.json明确m3；既有9-19安装跟进任务只更新提示词，仍是北京时间2026-11-02 09:00一次性同对话任务，没有新增任务或修改时点，保留真实只读/人工资金核验/不追历史仓位边界。后续不安装缺少日报的m2，也不拿本轮离线CI代真实资格。
- 最终外层交付Stage022_delivery_receipt.json绑定新物料、独审、全CI、clone、8样例、该记录和新handoff；未执行activate/promote-master/生产安装、SMTP/CTP或订单API。
