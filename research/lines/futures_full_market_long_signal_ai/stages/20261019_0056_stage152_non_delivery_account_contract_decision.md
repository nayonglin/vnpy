# Stage152：固定账户身份与全市场退出语义，暂不启动金融包

- line_id：`futures_full_market_long_signal_ai`；2026-10-19 00:56 CST；非重要突破。
- 上一goal轮分类为progress：完成一次6模型/4资金的FX实验和独审，151定位旧挂账的事实链，改变下一行动；本轮不重做这些工作。
- 本轮采用只读可行性路径：读取registry/LINE/151，三分工核本地字段、SHFE/INE/CFFEX及DCE/CZCE/GFEX官方资料；root读全部最终记录并另核RQAlpha官方GitHub。没有产品/策略代码实施，不创建分支/worktree。

## 决策

**固定研究账户身份，接受统一规则结构可表达；不把现有到期日改名为个人账户退出日，也不立即重训/重放。** 新研究假设为自然人、不能收交规定发票、未获国债托管审核、不接受实物的投机账户；这是明确的研究模型，不声称用户真实资格或其券商风控条款。原正式版与既有研究账本均不改。

完整目标仍是六所全市场全品种高质量做多识别，先证明成本后收益/回撤与稳定性，再讨论窄损和增加投注。规则元数据只改善可执行含义，不是新的预测alpha。不会以“数据合同通过”替代完整目标。

## 本地数据能做什么

本地目录98代码/10880epoch，原metadata10862epoch；clean97代码/9520epoch，041精确经济记录及known_lifecycle9502。六所个人/非交割截止、规则适用区间、发布时点和规则来源结构化字段覆盖均0。这里是数据字段0，不是历史没有公开规则。

known_lifecycle来自2026 vendor快照与名义月首/成熟/摘牌日期的静态研究假设；交割开始日/结束日也不是个人最后持仓日。目录身份可复用，不能凭当前字段直接签2010+训练、2020+执行的历史账户资格。新增2027尾合约18条精确metadata仍缺失，不能复制相邻合约补齐。详见[本地计数](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage152_local_non_delivery_metadata_feasibility/counts.json)。

## 规则结构及调研判断

| 制度族 | 已见历史语义 | 必须保留的边界 |
| --- | --- | --- |
| SHFE适用实物/FU/BU历史族 | 自然人T−3收盘清零，T−2起强平 | 不自动签每个新品种、2010至今全部版本；不等同更严格的券商规定 |
| INE历史SC/LU/NR；BC另组 | 前者相关个人T−8，BC历史T−3 | 旧T−8与今日T−5修订切点未绑定，不能择一个常数压全期 |
| CFFEX未审国债托管 | 历史TF/T自交割月前1交易日起持仓0 | 必须在此前已清零，不能误写该日收盘后才0；TS/TL与旧区间须单独绑定 |
| CZCE自然人 | 2019/2020直接官方正文支持交割月前清零 | 生效可能按特定合约，发布日期不等于所有条款统一生效 |
| DCE普通实物、GFEX候选 | 个人进入交割月前清零的制度族线索 | DCE旧原文未完整取得；GFEX官方原站返回bot/证书失败，不冒称正文已取到 |
| INE EC、CFFEX股指、DCE F身份 | 现金结算/交割必须独立分支 | DCE F官方正文/首适用合约未新认证；Commodity不等于实物；无结算数值不能自动了结 |

T为具体合约当时适用、含假期调整的末日；偏移按交易日历，不按自然日。清零义务、最迟申请点、目标开盘尝试、真实成交/现金交割是不同字段。清零截止K收盘、现模型下一开盘执行时，机械上应在prev(K)收盘申请K开盘；这不是收益优化提前天数，亦不保证零量/无对手方能成交。法定强平也不保证指定价格和数量。

一部分代表主源已直接读正文，一部分仅官方索引/同期副本；没有全历史版本区间。接受的是来源候选与语义，不是全市场日期资格。DCE普通/F分开、INE EC与股指现金分支、国债托管predicate都是保护原全市场范围所需，不能为了快速回测只留下容易查到的品种。

GitHub补充调研：[RQAlpha官方FuturePosition.settlement](https://raw.githubusercontent.com/ricequant/rqalpha/master/rqalpha/mod/rqalpha_mod_sys_accounts/position_model.py)在所见413—444行按摘牌时间生成旧last_price、零transaction_cost的系统平仓。**不采用这种合成成交作为本研究的实物平仓或已认证现金交割。** 当前master是可变引用，仅参考方法，无复制或固定依赖。[已有vn.py参考](https://github.com/vnpy/vnpy_portfoliostrategy/blob/main/vnpy_portfoliostrategy/backtesting.py)也不能给出账户历史资格。

## 已形成的可复用结果

- [account_contract.json](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage152_non_delivery_account_contract/account_contract.json)：固定研究身份、六所/普通F范围、券商资格unknown、清零/申请/真实成交分离、禁止后见填造与新增金融未授权状态。
- [rule_source_catalog.json](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage152_non_delivery_account_contract/rule_source_catalog.json)：10个制度/经济身份分支、官方URL、直接/索引/失败的证据层级及full_history_unknown；**新生成每epoch账户退出日0**，不包装成现成日期表。
- [decision.json](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage152_non_delivery_account_contract/decision.json)：本地覆盖计数、精确文档引用、结论和下一行动。没有保存或hash旧大库、重复下载行情。

## 取舍与下一步

否决把静态maturity直接当个人截止；否决按FU/LU两个结果特修、统一提前任意n天、按未来最后有效bar/stale筛样本；也否决先建设全品种全历史版本仓库。

推荐下一步只做**最小有证据规则区间补齐与完整目录状态映射**：按固定账户predicate保留规则生效日期/合约区间、公布时点/known_at、交割方法与特别调整。先补已定位的实际必需主源和T−8→T−5等制度切点，再报告整个母体哪些边界可计算、哪些unknown。缺证据不默默删掉其品种/时期，不把假日/零成交/现金结算制造成市场平仓。没有一张覆盖明确的表，不进入新资金或标签重算；可计算也仍不签真实执行保证。

这是原目标中的有限基础环节，不缩小目标，也不宣称改善了收益。若发现来源缺口无法经济地补足，明确记下该段unknown并重新选择有价值的研究路径，不无限循环相同网页检查；不复活已失败FX包。

本轮新增合同身份假设如上，新增/修改/删除生效策略参数与金融结果均0；新fit/cash/SQL/价格读取/标签/整库hash0，累计397fit/206cash。网页读到了部分新规则文档并做小型HTTP诊断，不能笼统写所有网络下载0。新权益、收益、DD、Sharpe、滑点、次数、胜率均N/A。独立金融审查不重复启动，因为本轮没有新回测。

开始/结束新增按收益调参过拟合：**否**，由制度与账户条件推导，不选成绩；同史择题与未来筛样本风险仍存在。继续本轮网页盘点：**应结束**；继续最小规则来源补齐/全域状态映射：**有价值**；立即重训/回放与全面版本工程：**无价值**。完整目标active，稳定优势、窄损上界及加注未证明。

## 分工证据

- [local](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/stages/20261019_0049_stage152_local_non_delivery_metadata_feasibility.md)：9533B，SHA `909af5f2b5ed911b8be02150e66a7a10f8c12a5adc06643d7c8c5f8d3e7b4b8d`。
- [local_counts](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage152_local_non_delivery_metadata_feasibility/counts.json)：4001B，SHA `910d4d599ad661d76f894f2a0ccf12549c30aa39907ca198fcddcecb95c8c405`。
- [shfe_ine_cffex](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/stages/20261019_0050_stage152_shfe_ine_cffex_non_delivery_feasibility.md)：12934B，SHA `09b477d946926d89821c4bf967e03372e792085d27b2a77d37d86047a4f4a38b`。
- [dce_czce_gfex](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/stages/20261019_0051_stage152_dce_czce_gfex_non_delivery_feasibility.md)：13569B，SHA `6f36a4d49d00ab8da7f796ffe99c47b65c5585461e950a18718b10ad0640b1da`。

root仅更新本线LINE/registry，不改根memory/back_log/外线，不Git/生产/CTP/邮件/自动化。
