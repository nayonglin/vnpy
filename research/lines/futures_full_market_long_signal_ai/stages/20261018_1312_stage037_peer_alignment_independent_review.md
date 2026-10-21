# Stage037：同行关系对应输入与模型独立审查

line_id=`futures_full_market_long_signal_ai`；2026-10-18 13:12 CST。沿当前分支`codex/ai-training-data-expansion`，仅新增本stage及`outputs/stage037_peer_alignment_review/`；不改033协议、034/035作者文件、旧审查、LINE/registry或他线。036由root保留为决策编号，编号不表示实际先后。

## 结论及限定

**Critical=0、Important=0、Minor=0；接受本固定代理计算，拒绝信息质量筛选。** 035预声明20门为3真17假：入选日期/家族支持两门及holdout_1相对SHUFFLED的一项均值门通过，其余失败。本次未证明20日同步rho、一维滞后shock对应、固定null、19槽Ridge及OPEN标签包具有稳健继续价值，不应换窗口/lag/相关度/peer子集/null/阈值或GNN救参，也不能事后改选COMMON或SHUFFLED为赢家。

主对照为ALIGNED−SHUFFLED，COMMON只是次参考。两个配对的本段历史识别均值上下端均负；但upper对应的bootstrap CI跨0，不能将其写成稳定劣化、真实现金表现必差或所有同行信息无效。B等其他退出政策没有用于本次标签，024模型与mask未复用。

## 收益前设计与源码审读

先读最新registry/LINE、032独立设计与033协议/spec，实核协议SHA `6328b2429106028531916050982bcf57f033285366a745f2f08a29a308a2556b`，设计无实质阻塞。032/033已实际查阅原作者论文与GitHub；审查同意关联与因果须分离，海外网络实验不提供本期货long窄损收益证明，本阶段不重复下载或运行外部代码。

034稳定源SHA `9b3e7ac37cbe46e0124af9905e63d4d457d37f9853a3ca3d69e28650d7ba5f25`及6项行为测试已审读。关系窗为u−21至u−2共20源日，shock为u−1；窗口不包含shock/u/D，族内ready r1均值不按标签筛选。own及F先归家族排除；strict held peer池与四market摘要均排除g。先全peer作hash排序再过滤held，与对允许peer子集直接hash排序的相对次序相同，未偷偷改变null。无完整query历史时标context missing，原ready不删。

035稳定源SHA `7141bb6e026fece3baa88d1a98db1d5cbe2a6ed8268d5e5ed9d116b7d4204292`及4项行为测试已审读。scope context强绑定、共同18列与ALIGNED/SHUFFLED各半权重的pooled q scaler符合合同；COMMON原q恒0，经同scaler仍为常数，由截距吸收。19槽相同不等于有效信息方向相同，COMMON有效18方向，因此保留为次参考。未导入作者计算功能或重跑测试套件。

特别限制：COMMON S11没有显式own t=u−1 shock，q可能部分重建摘要遗漏的自身滞后状态。即使ALIGNED胜SHUFFLED，也最多支持相对本固定COMMON的对应表示效用，不能证明超越完整自身历史或因果传播。query在held测试时使用自身已观察历史是许可输入，不是零历史zero-shot；单个固定null也不是完整随机化检验。

## 034有限输入数值复核

root fresh确认034完整终态后才运行。绑定manifest `2a3abe55eabf0fba5bb5d749fb4343d1bf341e3d217b93619554ab11bf98d990`。037输入复核实际`34445/4a635d→f295b4 exit0`，耗时3.236636秒，一次完成：

- 三scope各194709×9 `<f8`、全部有限；完整ID顺序、状态、整数peer_count、missing/Z/q逻辑保留，541 ready未知未删。
- main四market摘要778836标量与009接受列全表一致，最大误差6.661338147750939e−16。完整source calendar5587日用于窗口，报告grid仍parent4074日；catalog95 family与ready94不同，不改变母体。
- 收益前按2010—2026各年首/中/末ready日期、字典序首/中/末query，并补F/unknown query，确定164行；三scope共492格，用独立逐peer Pearson、直接允许池hash排序重构q/held/null，最大误差2.1316282072803006e−14。
- 604个同family/同日额外F表达context逐scope全表精确一致。

该复核结合源码/6行为边界，**没有独立重算全表q**，不冒称全表关系值逐格认证；这是root事先接受的有限合同，避免用重复上下文构建代替研究。0SQL、0fit、0下载、0大库重hash。

## 035模型及统计完整独立复算

收到root实读真实完整终态后才运行结果审查，未按部分成绩选择。035唯一实际108fit/55.521秒、0金融SQL网络，无失败或重启；最终manifest `073526fb3439f42b744519b6a7cb7c4a2931d8169e36c040513d27bc44962c51`。

037模型审查实际`37687/dcca9c→5d979a exit0`，2026-10-18 13:10:29—13:10:46，17.469294秒，一次完成，无重训/SQL/作者计算函数导入：

- 108个fit训练身份hash、membership的sequence_index/日期权重、严格成熟时钟、完整family排除、context_scope与训练侧shared18/pooled q缩放一致。ID由034原ready映射无损恢复，不要求membership重复保存长ID。
- 全969654个标量预测、mask及保存的9列context复算一致，含测试期unknown；最大预测误差2.220446049250313e−16。
- 事先选定2015 main与2026 holdout_0各3臂，检验6组保存系数正规方程而不解新模型；最大相对梯度残差2.4456795444243534e−13，最大加权截距残差2.099872489774027e−15。
- 4scope×14年度/期间共56报告、8daily、主样本两组共同60源日/2000次/seed20261018 bootstrap与20门一致；max daily误差3.552713678800501e−15、其他数值比较最大7.105427357601002e−15。
- 共同payoff的mask差取精确端点，相同mask歧义抵消，未用边际lower粗相减。参与率为事后共同identified cohort诊断；unknown不补0，source-grid空日NaN。压力沿同mask，不改阈值。

## 主要结果与置信度

2020+日期等权归一代理R（共同identified机会分母，不是每笔已交易平均或账户收益）：

| 指标 | lower均值 | upper均值 |
| --- | ---: | ---: |
| COMMON自身 | −0.000147694 | 0.001620290 |
| ALIGNED自身 | −0.000378689 | 0.001252986 |
| SHUFFLED自身 | −0.000133469 | 0.001356530 |
| ALIGNED−COMMON | −0.000367304 | −0.000230995 |
| ALIGNED−SHUFFLED | −0.000288109 | −0.000060656 |
| ALIGNED参与率诊断 | −0.000700040 | 0.001655583 |
| 同mask 1R成本ALIGNED | −0.005956230 | −0.004324554 |

ALIGNED入选已知701条/360日/83family；未知选择22条，原unknown仍保留。对COMMON配对lower的95%CI为[−0.000691498,−0.000084326]，upper的CI为[−0.000499035,0.000007780]；对SHUFFLED对应为[−0.000592629,−0.000026210]及[−0.000329216,0.000241656]。因此当前lower统计明显不支持优越，但不能把upper的跨0不确定性删除后宣称稳定劣化。

识别区间和抽样CI是不同层次；固定预测bootstrap不包含重训、研究者反复选择历史、真实执行或账户风险。同行输入虽新增于此模型，也不是新增外部数据或可交易alpha资格。

## 变更、反思与交付

本阶段仅独立审查：新增/修改/删除策略参数0，新增金融回测0，修改/删除成绩0；重要突破否。期末权益、总收益、最大回撤、Sharpe、真实总滑点、成交次数和真实胜率均N/A；真实经济/金融/生产资格false，无订单/CTP/部署/commit/push。未向未来038设计作者发送035成绩。

开始与结束新增按收益救参过拟合：**否**，按033固定合同核验、不增臂；历史择题、单null和短rho窗口的选择风险**有**。继续本包救参：**否**；继续用户完整全市场高质量long、更高收益低回撤目标：**是**，但须先审查下一问题与真实目标的关联，不能以小代理反复重包装替代财务和生存证据。原目标未达成，goal保持active。

输入复核收据SHA `a6ea4df797e7930b38b1686dddb370642bf91a28f0f07b48232cd619279cf1d1`；最终模型审查收据SHA `aa3aa439ebf37abb69a117493128dd8133e5773e72ed320cef5822c43c155770`；实际结果终态SHA `e5ff340598a75f69912078e434f9c7742a5e47a7d84ae7d6d52ba4987b13174f`。显式本stage资产清单单列，root归档并更新LINE/registry，不复制原始行情或写旧审查。
