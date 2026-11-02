# 周线空头MA斜率门研究线

- line_id: futures_weekly_short_ma_slope_gate；day；版本weekly_short_ma_slope_gate_v1 / Stage001 C。
- 独立worktree: /Users/mac/.codex/worktrees/weekly-short-ma-slope-20261029/fian
- 分支: codex/weekly-short-ma-slope-20261029；来源HEAD24b975025355d2ea05ba80f5dd67105683ac1b62。
- 来源为Stage033 A / Stage029v2，15万、原19品种、动态底仓、不加仓，2020独立起点；不使用44品种版本。
- 2026-10-29 Stage001：A/C同源完整回放至10/29。C仅在新开空信号时MA5或MA10相邻完成周上升则拒开；零斜率允许，换月续仓/多头/退出/其他风险规则不变。
- A: 期末1304010元，收益769.3400%，DD-55.0429%，Sharpe0.966500，滑点81020元，464成交，完整周期胜率47.8070%，PF1.377325。
- C: 期末1690065元，收益1026.7100%，DD-56.6065%，Sharpe1.036320，滑点85160元，435成交，完整周期胜率45.7944%，PF1.476028。
- C真实路径65次short_case1a sizing中21次正斜率，17次父级选量>0被实际归零；不是17笔必然成交的固定反事实。
- 独立数据、逐日/逐笔/周源/门控/实际开空与旧A至28等价复核PASS_WITH_LIMITATIONS，P0/P1/P2=0/0/0；策略评价MIXED_OR_FAIL_NO_RESCUE_TUNING，NO_PROMOTION。
- 结果记录: stages/20261029_2008_stage001_short_ma_slope_result.md；独立审查stages/stage001_independent_review.md 和 stage001_independent_final.json。
- 仍有零手续费、静态margin×1.65、历史PIT/生命周期/容量及未平MTM限制；C配置保证金占用峰值105.8627%，不是可实盘资格证明。
- 后续：冻结版本；固定规则的独立起点/OOS验证有条件价值，不自动扫斜率/MA窗口/品种/年份或扩池。保留所有失败日志和有效003账本。
- 与另一对话Stage040 44池代码、数据快照与写路径隔离；不改其文件、根registry/总账或正式物料/CTP/生产/邮件/调度。

## 2026-10-31T20:33+08:00 Stage016 正式迁移候选

Stage014 C_R150固定规则迁移到独立weekly19-15w-r150k来源工作区；完整88套件2263通过，分批独审与最终时钟增量通过，仅离线条件接受。真实CTP/最终日结/到账来源资格未通过，生产仍d558/旧m0008、canonical7jobs未加载，master仍e41，未激活或安装。详见stages/20261031_stage016_offline_candidate_acceptance_and_blockers.md；原Stage014金融与NO_PROMOTION判断不重写。

- Stage016本地不可变候选已冻结：m0001_20261031T203743+0800_e3d08592e85e，source e3d08592e85e00a2a6b8fde880f69e771755f10b，release d5243461b9cf0368723899bcce67a3dc6fb0ec1a；fresh clone371文件/LFS实体/executable位通过。真实qualification仍缺，CURRENT/master/production均未变，详见stages/20261031_stage016_local_release_and_qualification_blockers.md。

## 2026-10-31T21:39+08:00 Stage017 用户改为人工资金核验

用户取消最终日结解析/自动到账核验的自动化要求，由其人工核验；真实CTP回执等2026-11-02周一。Stage016旧阻断清单相关自动化要求被本决定取代，m0001不改写；激活前接入明确人工确认来源并生成新物料，不把决定记录当已部署。详见stages/20261031_2139_stage017_manual_cash_verification_decision.md。未改alpha、master或生产。

## 2026-11-01T05:06+08:00 Stage018 安装准备与本周信号

Stage014 C_R150固定19品种截至10/30无新开信号（15万空仓条件），已独审原始数据；人工资金核验与独立日历启动接线已实现、独审及完整90套件2309通过/0失败/0跳过，288关键源无漂移。新代码待官方发布器冻结m0002，不覆盖m0001。独立market generation及真实未来日历已备好；实际stable/CURRENT/master/7jobs尚未切换，CTP未连。11/2周一09:00一次性本对话任务9-19先只读核验，再继续已授权的真实资格/正式激活和安装。自动final/parser与银行producer已取消，不再列为前置。详见stages/20261101_0506_stage018_manual_candidate_ready.md；原Stage014金融和NO_PROMOTION保留，与44品种线隔离。

- Stage018本地m0002已冻结：m0002_20261101T050816+0800_e89fdcbb6826，source e89fdcbb68260a647372f03626800110470f61dd，release 48839375c26081bf6aeb5610aab70c72c688c59c，378物料fresh clone/LFS/执行位复核通过，m1完全保留。当前仍未activate/promote-master/生产安装；周一任务从stages/20261101_stage018_local_m0002_and_monday_handoff.md继续。

## 2026-11-01T13:31+08:00 Stage019 今年独立起点复核

复核原Stage014 2026-01-01 fresh_engine窗，实际1/5—10/30共198日，无新金融回跑/无切长曲线。E173100、展示增长15.4%含T720、净交易PnL22380（14.92%）、DD−36.1615%、Sharpe0.619534、36成交/18轮/44.44%胜率/盈亏比1.58075/PF1.26460；R149280、末仓0。单独年度PNG/CSV/report见artifacts/stage019_2026_ytd；独审/最终交付receipt与stages/20261101_1331_stage019_2026_ytd_rechecked.md。策略/m2/实盘任务均未改；手续费0/非新OOS等限制保留。

- Stage019最终独审accepted/PASS_WITH_LIMITATIONS，新增原账2701+派生187检查、未解决P0/P1/P2=0；外层交付artifacts/stage019_2026_ytd/delivery_receipt.json绑定原source_manifest和所有交付。原始审核失败保留；未改原财务或m2。

## 2026-11-01 Stage020 年度18轮逐笔离线复盘

基于Stage019唯一2026独立窗，统一Stage038纯函数渲染器的本线窄适配器，18轮/36成交/8盈10亏/净22380。日/周/月/10/30日全部精确epoch，8轮可用部分或完整本地15m；52缓存候选逐日/桶准入及3日隐藏预热，缺日后MA断段，未下载/代理/补造。最终入口artifacts/stage020_2026_ytd_recap_attempt002/index.html，单文件6.24MB内嵌Plotly/数据/年度净值图，9adapter测试、root252JS及独立1553数值+180JS等通过。真实浏览器因file协议安全策略阻止而未验收，未绕行或起HTTP，outer delivery明确此限制。未重跑金融或改策略/m2/生产；初始版本和失败证据保留。

## 2026-11-01 Stage021 平仓原因显示修复

已接受Stage020的18轮原账和全部图表数值保留，仅新增中文退出说明：9周收盘技术保护、7风险组压力降仓、1组合保证金风控、1换月平旧（新合约未开）。独立卡片及图标悬浮显示规则/原始代码/触发与成交日，9技术退出直接列原周close与stop；缺失压力/组合比率不补造。新单文件入口artifacts/stage021_2026_exit_reasons/index.html，旧HTML保留。18Python、root467静态JS/合成DOM、独立502字段/SHA及236JS通过，真实浏览器仍file协议阻断、未绕行。stages/Stage021_review_acceptance.json与版本化delivery_receipt绑定全部交付。未重跑金融/下载/改策略/m2/生产，288关键源保持；详见stages/20261101_1620_stage021_exit_reason_display.md。

## 2026-11-02 Stage022 每日风险通知候选

每日postclose-report已接日报，明确风险组新信号有/无/未确认，中文原因/原码/原持仓与买卖平/计划与累计成交/历史待执行；同日去重、投递不明不重发，周五独立补资邮件保留并显示退出原因。真实回报semantic/rawSHA绑定成交日期，旧缺日期和bars_queued未评估明确未知；不重跑策略或改alpha/资金规则。92套件2348通过/0跳过、291关键源无漂移，独审P0/P1/P2=0，旧CI沙箱33失败和queued RED均保留。8封合成离线样例见artifacts/stage022_daily_mail_previews_attempt002/；独审stages/Stage022_review_acceptance.json。代码本地提交52b825c4e，新不可变候选物料冻结/安装接续由Stage022新handoff记录；旧m2和CURRENT保持，不代表已发送或已安装。

- Stage022最终新m3已冻结并独立clone实物验收：m0003_20261102T001414+0800_39913bc2821c，source39913bc2821c47a485913f6d7b2d2631c19e19ab，release65594f6320f4c625892be534f750275c9667e315，381payload/291CI/实际LFS与执行位通过，旧m1/m2/CURRENT均保留。最新安装只读接续入口stages/Stage022_installation_handoff.json（替代安装目标，Stage018证据仅历史）；既有9-19任务已同步新候选，时点仍11/2 09:00。尚未激活/master/生产安装或真实发邮件，外层Stage022_delivery_receipt绑定全证据。

## 2026-11-02 Stage023 09:04真实只读与初始账户阻断

正式ctp_live env/framework已实测，CTP TD/MD认证登录成功，单连接账户/持仓/委托/成交查询完整、8 mutation API计数全0；原始回执及真实资金/仓位仅私有归档。实际账户非空仓且权益不符冻结的150000初始门，故保留m3、现仓和现金，不执行接管/初始化/激活/master/Stage948或SMTP。79项独审通过仅为真实只读观察，不是正式资格；Git保留脱敏Stage023_readonly_result/Stage023_review_observation，完整审计及失败版本私有原字节保留。既有一次性9点任务9-19已结束删除，未改每日通知代码或生产job。已询问用户现仓管理与启动基准；待答复从stages/Stage023_resume_handoff.json继续，必须取新快照，不复用本次诊断冒资格。

## 2026-11-02 Stage024 实际权益与现仓一次性接管候选

用户明确选择直接切换，保留真实账户盈余及现仓，替代Stage023精确15万空仓启动条件。独立查找未见可验证旧保护档案，故固定为新接管管理周期：原生OpenCost/真实乘数核聚合成本，管理日期重置、旧止损/峰值/计龄及旧风险记忆未知，不造旧成交；最近完整周原公式保护、完整layers/identity与真实现金同一原子初始化。启动前盈余单列，场外R15万/T0，后续风险仍按真实交易权益，人工现金确认不变。新入口不发单/邮件、不追历史开仓，默认flat门保留。

96套件2405通过、0跳过、298关键源无漂移；独审发现并修复实际E0高水位遗漏、非投机仓错误接管、旧一周保护可被采用三P1，原RED均保留且原断言复验绿，另有76次独立定向调用。详见Stage024_implementation_lock与独审记录；真实静态合约metadata已捕获仅作启动来源，旧9:04 CTP诊断不升级为新资格。尚未新m4冻结/真实新资格/激活/master/生产安装，后续从新版本化交接记录继续；m1/m2/m3和44品种线保持。

## 2026-11-02 Stage025 m4资格失败与m5工程修复候选

m4 source d43e23ca9a501acae3665501a28ecefb6918d7b1、release 1a4f7d06c2f964f8bb3bab3b818ac5e05b7b5876已冻结且local clone388payload/298critical/LFS及mode通过。可信逐套件资格失败于三组测试，尚未进入native捕获；不activate/master/生产。两组稳定复现为隔离HOME缺生产目录导致源门错误类型，最小改expected path resolve(strict=False)，actual repo仍strict存在/身份链不变。另独立故障注入证实通知lock首次exclusive-create ENOENT缺原8次retry分支，补catch保留权限/NOFOLLOW/最后raise/未知投递不重发；不把它冒认原Friday故障原因。原Friday30轮及原序前链未复现，保留UNKNOWN与原失败，下一次旁路尽力归档原始观察，不修改可信producer或用sidecopy授予资格。

4文件代码/测试最小delta，新增3回归先RED后GREEN；96套件2408/0F/0E/0skip、298锁前后/current一致，独审613绑定检查通过/剩余实现P0/P1/P2=0，原AST原型错误文本差异1F及历史原始轨迹丢失明确保存。无金融重跑/alpha/资金规则改变，未接管实账户；需新m5及真实新资格。最新离线入口Stage025_implementation_lock.json / Stage025_review_acceptance.json；m4不可变负结果不覆盖。
