# Stage018 人工资金核验候选与周一安装准备

记录时间：2026-11-01T05:06+08:00；line_id=futures_weekly_short_ma_slope_gate。重要突破：否，固定Stage014 C_R150的工程接入与缺口修复，不新增alpha或金融回测。本阶段尚未安装或激活新策略。

## 已完成的用户请求

1. 截至2026-10-30完成周，以真实approved日线、假定15万元空仓冷启动，19品种均无新开仓信号。独审直接重算原始MA5/10/20交叉，19/19齐备且0交叉/0候选/0意向，不是资金不足压零。真实CTP持仓、权益及Available未知，因此不据此判断旧仓退出/减仓/换月；也不保证下周后续新数据永无信号。详情Stage018_signal_scope_20261101_record.md及Stage018_review_signal_acceptance.json。
2. 按Stage017用户决定接入operator_manual_v1：不再强求自动最终结算单解析或自动银行到账producer。人工记录明确来源、账户/物料/request/原始snapshot/实际受理时刻，R/T严格守恒；只发布私有记录与现金引用，由原actor与runtime原子消费。实际E/Available仍来自真实CTP，人工金额不修改券商权益。CLI/操作说明已提供，跨日人工核对覆盖全部已闭交易日。
3. 修复Stage945残留旧Stage922目标路由：weekly19使用自己的已封日历和context cold_start_date。保留C9函数体原逻辑，_resolve_target_date新增可选now参数；不冒称完整函数签名AST未变。不放宽activation、qualification、daily receipt、账户、持仓、报价、风险或原生子单门。
4. 复制原approved五源到独立私有候选market generation，加入真实TQ前向日历，完整SQL/physical 392382行0不匹配，19主力齐备；日K仍截至10/30。周一11/2 09:00解析10/30，未来日历不充当未来K线。source及原快照未改，路径及六pin见Stage018_signal_scope_complete_market_generation_receipt.json，root独立复核见Stage018_root_install_preflight_20261101.json。
5. 准备源工作区忽略且0600的本地运行依赖，来自实际stable已有配置，未显示秘密、未进Git。旧空默认vt_setting已私有备份；没有CTP或SMTP连接。独立源码/记录秘密扫描0匹配。
6. 本对话一次性跟进已建：automation id=9-19，2026-11-02 09:00北京时间。先正式env/framework guard和只读CTP；成功后继续真实资格、受控activate/promote-master、remote master fresh clone、新生产HEAD资格与Stage948。任务不会补历史理论仓位，不发单、撤单、转资或邮件。

## 验证与保留的失败

完整90套件2309通过，0失败/错误/跳过，耗时411.45秒；关键288源/test/doc前后SHA无漂移。CI记录Stage018_selected_final_attempt002.json、XML和log；它是离线验证，不是production qualification。随后source commit必须逐个Git blob对上该288指纹。

独立信号审查、旧pure85（只对应当时pure实现）及最终52次增量审查分别封存。最终增量覆盖实际strict-parent CAS/恢复与历史origin多次补资、Backend全引用先验/坏JSON pending、CLI与可恢复持久化、Stage945真实日历路径；最终severity见Stage018_review_manual_integration_acceptance.json。旧store证据没有继承到新store身份。

两P1（人工gross入金守恒、实际applied_at超过request有效期）及三P2（非法嵌套输入、记录目录移动、引用重试未重做dir-fsync）已修，所有独审RED保留。首完整CI为修复最后P2主动终止，exit -15、无XML；其0 counts不是0失败证明。中断进度中旧suite PermissionError已由同源88例在必要本地日志权限下全绿复验，根因是vn.py子进程写用户日志被sandbox拦截，不是945或manual逻辑。完整attempt002使用同一原环境及必要日志权限后通过，未为迎合测试改策略。

## 当前生产事实与尚待周一事项

本机stable仍为d55887e1def72629fbfa310e439dc3a879969a14、旧m0008；五件套均缺失，实际owned loaded jobs为0、冲突0。root只读preflight另存，不把普通checkout或候选称为生产。未改CURRENT、未推master、未操作真实生产；旧m0001不覆盖。新m0002待本次干净source提交后由官方发布器冻结，发布/克隆结果另记。

尚待真实只读CTP账户/持仓/委托等证据；若账户并非真实15万空仓或有活动委托，保留实际阻断原因，不自动转资或平仓。自动结算解析与银行producer已被用户取消，不再列为前置。真实资格后再完成活动物料/master和Stage948 7/7闭环，不能预先伪造或手填五件套。

## 变更参数与金融结果

新增工程参数cash_verification_mode=operator_manual_v1、manual_cash_review_root和cash_sources.manual_reviews。funding_credit明确人工核对真实现金，CLI确认记录最多30分钟受理，已消费历史永久保留。未修改19池、MA/空头底20%、原OI风险档位、初始15万元、场外15万元、无加仓及alpha/MRO；没有新增自动现金生产者。

本阶段没有金融回测，期末权益/收益/最大回撤/Sharpe/总滑点/成交次数/胜率/PF均不新增或改写。原Stage014及NO_PROMOTION、零手续费/非完整PIT等限制完整保留；用户正式替换授权与研究经济判断分别记录。

开始与结束判断：过拟合为否，没有选收益或扫描参数；继续有价值，当前价值在真实会计、启动路由与账户资格。外部资料采用vn.py/CTP既有正式只读流程、TQ官方日历响应及Codex官方定时跟进工具；判断是复用可追溯来源和现有执行链，不以离线测试替代真实连接。
