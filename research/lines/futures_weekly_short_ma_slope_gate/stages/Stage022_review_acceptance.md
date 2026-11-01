# Stage022 每日风险邮件：独立离线候选验收

时间：2026-11-02T00:10+08:00；研究线 futures_weekly_short_ma_slope_gate；BASE 30b236c973367a859ceae053ee8f1f37a36ac558；最终锁Stage022_implementation_lock_attempt002.json。结论 PASS_WITH_LIMITATIONS，最终未解决P0/P1/P2均0。本阶段是通知及来源元数据接线，非alpha优化或金融回测；不等于生产资格、安装激活或真实邮件已送达。

已独立核720项源范围/AST与旧m2实物，332项完整CI/实际源/SHA及8封样例。完整92套件CI由主任务执行，独审实读XML、log、前后源映射与当前291文件：2348通过、0失败/错误/跳过、0源码漂移。不是独审重新运行全CI。原CI001完整33失败/2311通过的log/XML保留，日志/主任务定位为沙箱Darwin时钟、进程组和vnpy日志权限；33旧失败测试身份全部保留并在允许本机测试资源的CI002通过。两次源锁仅daily renderer/test两项受控queued修复差异，没有删测试或放松旧断言。

分阶段独立执行32项专项（元数据9、完整fill来源投影7、pure邮件/outbox9、queued状态4、actor/store事务3）均GREEN；各日志和所审版本分开保留，不把它们与全CI相加声称唯一覆盖。最终queued4和actor3对应当前锁；早期专项通过后所加queued守卫另有明确正负例，来源全图由最终锁和全CI再绑定。

关键结论：

- 新exit_reason只取同信号日、合约、Close及原持仓方向的唯一原始diagnostic，旧日/Open/RiskSizing/异合约/反方向/冲突均不猜。未知仍是有平仓计划，不变成无风险。旧intent、decision与decision_state不回填；旧intent_kind执行分类刻意保留在原语义范围，邮件不拿旧kind推原因。
- close lifecycle按原volume/actualfilled聚合，重试不累加计划量。成交日仅取通过原生绑定、数量及重复门后的完整semantic/rawSHA；投影核tradeID唯一、原fills档案、raw与semantic摘要、account/release/plan和累计量。legacy缺日期仍保留待核对，不拿计划日推当天成交。买平/卖平与原多/空持仓分清。
- report先刷新只读账户与原始回报、实际fill先于order确认及最终持仓对账，再CAS提交runtime/funding，最后发件；不on_bars/process_completed_day、不publish委托/撤单。独立注入sender观察到新broker状态已落盘，原decision及完整decision_state保持；receipt漂移不发信。unknown投递明确失败，业务状态不回滚，同日重试不再次调用sender。
- 发现并修复P1：真实bars_queued/unresolved_execution_lifecycle决策没有执行当天策略，不能回答新风险组信号“无”。独立RED保留，受控修复后显示“未确认/当天策略尚未推进”，旧pending与actualfill仍可见。正常已评估reduce_only+已知heat正例继续显示“有”，未全阻断。
- 每日主键profile/account/release/完成交易日/daily_risk，独立于原周五week类别。预览不占发件名额；sent去重；sending/unknown连正文变更也不盲重试。独立模拟进程在sender处丢失，durable sending保留，重入unknown且只尝试一次。private目录/文件安全IO继承原AST，完整CI含并发/权限边界。
- 日报直接回答风险组新信号有N/无/未确认，其他技术保护、组合保证金降仓、历史pending和当天实际回报分别展示；累计成交不称当日新增。前两根完成周保护不误译成两日，heat0.4不是保证金40%。周五资金计算AST除退出原因文字外与BASE完全相同。

BASE关键文件仅声明8旧文件改变、3新文件，合计291；37份冻结源/资产pin不变（32源码包文件与5资产）。runtime仅send_order新增metadata及已验证fill后追加显示证据；将这两个增量移除后原方法AST精确同BASE，原校验/实际PnL/去重/回滚不改。原pipeline策略/session/资金advice helpers、backend除send_mail、原Friday资金计算与outbox安全IO有AST对应证明。旧m2 manifest与378payload均未改变；不将m2旧整体资格继承给新代码。

8封最终样例逐文件SHA与source pins核对，均明确“合成数据离线样例，不是实际交易信号”。覆盖无信号、heat有1、原空头买平、历史部分成交、原因未知、数据不全、周五原因及当天策略未评估。它们不是本机账户或今天真实信号，生成过程没有SMTP/CTP/金融回放。

置信度：对本次通知增量、生命周期/来源边界、私有去重、当前锁源和离线测试较高；真实券商source、SMTP实际投递、scheduler加载及生产激活未由本轮验证。真实APIs/CTP/SMTP/银行/生产操作均0，源资格和生产资格仍false。用户授权安装与场外人工核验模式不等于技术已qualified；自动银行与最终结算parser要求此前已取消，本轮不恢复该工作。

独审失败/发现与中间通过均留存：原projection probe因合法小engine被强制unpack而失败（已统一_decode，small/compressed正例过）；初始legacy来源/日期投影缺口已核修；queuedP1独立1F及最终4GREEN保留；原执行kind不作通知scope外修改。预审accepted=false和历史OPEN_P1记录是当时快照，不冒作最终结果。

反思：无新增调参性过拟合，alpha/风险/资金参数未改；继续有价值，避免用户把未通知、未知或尚未评估当无信号。未新增或删除金融结果，既有研究限制与NO_PROMOTION结论不因通知代码改变。后续仅由主任务封交付/冻结新不可变候选；实际安装激活/真实来源和投递由已授权流程另外闭环。本独审不绑定正在编辑的root文档或未来release，避免循环哈希。
