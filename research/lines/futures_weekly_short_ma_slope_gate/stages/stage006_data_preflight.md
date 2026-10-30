# Stage006 2015独立起点：数据只读预检

- 时间：2026-10-30T12:44:59.825599+08:00；line_id=futures_weekly_short_ma_slope_gate。0回测/0下载/0数据修改/0生产访问。
- 固定同一独立原19快照，物理批准日线2014-01-02—2026-10-29共392197行。receipt.financial_start=2020只是旧实验标签，不是数据库开始日期；本次新合同显式2015，旧receipt不改。
- 请求2015-01-01—2026-10-29，实际2015-01-05—2026-10-29共2871交易日。2014有245日历交易日仅供预热；A/C都各15万空仓，不能继承2014或2020账户路径。
- 原19非空主力mapping金融期43821条；缺正量键591，其中有raw零成交证据573，冻结mapping结构无效18，未知0。已知零量/结构不可用只分类，不作为可交易bar或制造周线，实际持仓/成交/周源日仍需引擎逐一硬验。
- 首日各主力2014有效完整周按同全局日历/同epoch统计见JSON；不足21周的首日主力：[{'product': 'hc.SHFE', 'first_main': 'hc1505.SHFE', 'available_accepted_complete_2014_weeks': 13, 'ready21_at_start': False}]。这不是全品种首日全部可交易；不足者应按原21-ready自然等待。2014 MA alias有228已知缺mapped日，不能补价或缩短ready。
- 原Stage033 A同规则2015账本仍在/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/outputs/stage033_A_attempt001，末到10/28权益3536289.999999998。它是身份/历史对照，不是本次带range门的成绩；本次A完整到28切片可用于原版等价核验，不能把2020曲线接到2015或带入旧资金/持仓。
- Stage033旧来源HEAD24b975025355d2ea05ba80f5dd67105683ac1b62；数据到28，与本线在旧行保全基础上追加29，故文件SHA不同并非自动规则差异。不要机械要求当前全部DATA SHA与旧28日快照相同，也不要据此覆盖老来源。
- 本次range类须原字节复用Stage005，只改变金融起点；缓存同physical epoch日线history截至每次signal（含本日）不变，20%不变，两侧MA门OFF；尚未计算任何2015新绩效。
- 预检结论：PASS_FOR_FIXED_BOUNDED_REPLAY_WITH_INHERITED_LIMITATIONS。完整主力非PIT/6个历史未知完整生命周期、静态元数据/零手续费/无盘口容量等原界限继承。每臂仍需全部实际持仓/成交/周源/epoch/nextopen/会计验收及独立review。
