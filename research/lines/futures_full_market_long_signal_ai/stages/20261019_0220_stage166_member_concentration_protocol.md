# Stage166：固定持仓分布新信息对照

- line_id：`futures_full_market_long_signal_ai`；2026-10-19 02:20 CST。接受165来源与164结果前设计，尚无新训练/现金结果。root明确两held已识别u等权增量>=0为nominal必要条件，差异unknown仍使泛化未识别；CONTROL最终q列恒0，不能raw0后减q均值。
- 两臂54槽，CONTROL54=旧COMMON52+共同q缺失+恒0；CONCENTRATION54只把恒0换为训练fold内标准化q；原训练净Rstress first-exit、成熟时钟、family-u union权重、Ridge1不变。共同K政策不是alpha，159unsupported不撤销，不重新做K标签或调整模型救K。
- 先全六fold成熟q观测和正加权variance预检，任一失败0fit/0cash；通过才2臂×2cutoff×3scope=12fit，main2臂×2window×2cost=8cash。母体/全部child/四所missing保留，不筛未来成交/可闭合/收益。先D<K再每产品argmax及普通/Ffamily优先，各账本自有递推。
- 主2020stress须收益严格提高、DD严格变浅、固定070块bootstrap的日log差95%CI下界>0；另3收益/DD不劣，新信息臂自身4收益>0，8本财富正；CONTROL空账DD为NA则unknown不算过门。held仅旧target诊断，不能伪称K现金或新因果聪明钱。
- 新增参数：仅新q及共享missing槽；原参数修改/删除无，正式参数无改动。新旧回测成绩均N/A，本阶段未运行；预算12fit/8cash不是实绩。当前397fit/210cash，全部完成才409/218。权益/收益/DD/Sharpe/总滑点/交易次数/胜率本阶段N/A。
- 协议 `ebd24d42728e9309d390e4b31ff692ed5e0b723b4721744bcdd0ea063a9c014a`；实际需root单独绑定代码+输入再唯一启动；actual失败保留计数，已完成fit/账本不得为metadata重跑。结果后独立agent全审。
- 开始/结束新增按成绩调参过拟合：否；历史多轮择题与重用同史风险有。继续这一次新观测对照有价值：是；继续改q定义/lag/缺失/品种/月份/模型/止损/风险救参无价值。正式/生产/CTP/仓库分支不动，goal active。
