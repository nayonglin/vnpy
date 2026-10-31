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
