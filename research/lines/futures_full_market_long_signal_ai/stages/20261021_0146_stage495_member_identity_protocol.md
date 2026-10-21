# Stage495：具名会员身份增量唯一有限实验协议

line_id=futures_full_market_long_signal_ai；当前day；时间2026-10-21 01:46 CST；非重要突破；独立于正式C9。先读registry/493/494，使用brainstorming、writing-plans及并行agent，用户已授权自主持续研究；不再暂停日常实施审批，不切分支/工作树、不提交。

## 调研与判断

[交易所披露说明](https://www.shfe.com.cn/content/cxxc/7wsxx.pdf)及[维护者原实现](https://raw.githubusercontent.com/akfamily/akshare/main/akshare/futures/cot.py)支持双侧身份字段，不支持将经纪会员等同最终投资者或聪明钱。493/494确认原162向量保留身份、170匿名HHI不保留；同量姓名置换使z变化但HHI不变。原NFC/仓单/HHI/宏观及annual失败均不重开。完整机器规格见outputs/stage495_member_identity_protocol/protocol.json。

## 实施计划与验收

- [ ] 496一次真实162投影，exact epoch/紧前完整源日，exactname优先/缺名才独立IDtoken；训练only词表。source缺失双方A，全OOV C=B。
- [ ] 单129白名单流保留source可见历史及全部forward既有Y投影；成熟支持用metadata，不能称0Y。共同原stressR/.25N/K/成熟及held族，原六52模型冻结。
- [ ] 六cell支持通过后12微型头：B=[1,r]；C参数零空间约束ones及X'WZ，sumw1/ridge1/有效df<=1，无zscore。原130权重算法在共同条件训练样本上计算，不冒充原52数字。首fit前全6门checkpoint。
- [ ] 复用489已有现金因果16列/7identity，原COMMON与score各一次，全98/95政策和161014forward母不缩。497最多8新B/C账，A157自身四账不回放，100w和原费用/风险/.25N不改。每本raw账先checkpoint；含全部95family、年度、同账截至2025及12组配对CI。
- [ ] 498一次独立source/model/selection/资金核查，0金融回放；不无限二次认证旧raw/held。499root决策后更新本线LINE/registry。

C对A和B均须满足原四点收益/回撤及primary压力CI下界>0，held差异未知不补0。同史CI是条件证据，成功亦无加注或生产资格；失败不换token/lag/归一/容量/风险救成绩。

## 变更及结果

新增：exact身份token、B[1,r]及C参数约束残差头，sumw1/ridge1容量界。修改/删除原参数0，新增/修改/删除原金融结果0。本协议尚0新fit/cash/SQL/API/下载，累计493fit/266完成cash及1旧partial；权益/收益/DD/Sharpe/滑点/交易数/胜率N/A。普通文档生成曾一次引号SyntaxError，0数据读取，修正后仅重写文档；不是actual失败。

起止反思：长期同史择题过拟合风险是，无本轮收益后调参；一次有限身份反证有条件价值是，重复老包工程否。历史研究无需今天日线；原四前瞻账户独立。更高收益低回撤/全市场高质量long/极窄损加注完整目标active未达成。常规记录不写根memory/back_log，正式/生产/CTP/邮件/任务/Git不变。
