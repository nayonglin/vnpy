# Stage110 同表会员类别构成：固定一次信息对照

- line_id：`futures_full_market_long_signal_ai`；时间：2026-10-18 19:43 CST。沿用当前研究分支，不新建工作树。不是重要突破或正式策略晋升。
- 目前只完成协议/实现授权，没有本包projection/fit/cash/SQL实际结果。期末权益、收益、最大回撤、Sharpe、滑点、交易次数、胜率本期N/A；累计仍361研究fit/94现金。既有结果不修改、删除或冒充本轮控制。

## 收益前科学收敛与调研判断

[上期所历史披露制度](https://www.shfe.com.cn/content/cxxc/7wsxx.pdf)表明分类观测针对活跃月份；[历史合规指南](https://www.shfe.com.cn/upload/20140909/1410241505340.pdf)和当期业务规则支持经纪/自主业务角色差异，不支持产业或聪明资金标签。[AKShare维护者源码](https://github.com/akfamily/akshare/blob/main/akshare/futures/cot.py)过滤非正rank，会丢掉这层观测。104/106实际原表确认它不能由总OI与COMMON26代数恢复；这不证明未来条件收益有增量。月度库存/风险溢价文献也不直接证明0.25N first-exit优势。

107原草案用自身比例(LN−SN)/(LN+SN)。root在新金融成绩前指出：1手与10万手单边同值，若研究风险承接构成，它丢失类别参与份额。独立设计agent未读109新增数值或任何金融成绩，比较测量含义后，建议唯一采用**同表gross比例**：

`s=(LN−SN)/(LN+SN+LF+SF)`。

本110据此一次冻结；原107不覆盖，own比例未实测也不再待测，未来不因结果改回分母或另跑两种挑优。问题只限：当期已披露集合中非经纪类有符号净持仓构成，能否在COMMON之外为固定long/不做决策提供成本后信息。它不是市场净需求、逐笔压力或因果风险溢价；方向由cutoff前训练一次学习。新旧境内/境外群体版本和真实披露范围变迁必须由实验承受。

## 来源与完整母体

109按108原协议继续单遍3588日期、13复用/最多3575新GET；当前仍运行，终态前不作完整来源已接受声明。111只读取本地绑定raw，0网络/SQL，恢复整份报告的真实contract集合。若唯一完整all存在，仅用all一次；all残缺不回退。无all时，产品在整份报告披露的每个实际contract都须两类完整同范围且平衡；先sum四原量，再算一次s，不平均ratio，不用剩余子集救缺。

精确认可已观察的两套ABBR与rank角色，保留原label/population_version；未知不猜。四量都真实有限非负整数，全gross0是真s0；缺日/缺类/冲突为双方共享missing。成交/变化仅QA，不反推L/S。source日期存在时须相等，早期无时钟单独保留。已接受官方归档重建加一完整source日lag的有限研究假设，不冒充历史首发或无修订PIT。

lag使用070全母体4074个唯一u_date的有序序列紧前日v，不用u日数据，也不找最近可用源ffill。原u_index、目标与现金native calendar均不改。精确映射只到SHFE.<CODE>，不跨交易所或普通/F经济身份复制。全399252母体/98目录产品/95family/六所和各臂2020+161014行继续保留；外部可得性不是训练、预测或动作硬门。

## 固定模型、现金与判断

CONTROL/NFC两臂同54槽：COMMON26、26共同missing、1共享external_missing和1scalar。CONTROL scalar严格0，NFC为s。原071 Ridge alpha1/截距/cholesky、各fold自身成熟NARROW目标、family-concurrency后u日等权、训练内scaler/mean imputation保持；不能用窄目标成熟前的未来闭合资料。两cutoff2020/2023、main/两family-held，共最多12fit；每臂完整main和held并集161014，各臂共322028分数，总644056。六cell训练有限s无正加权变异则整包不识别停止，不移cutoff或缩池。

最多8现金账户=两臂×2020连续/2023独立冷启×base/stress。复用070原20low/换月/lifecycle/stale/gap、100万/单family0.25%/总风险2%/buffered margin25%/1.10buffer/0.25N初损、u预留/D只减量/整数手；不叠080、不设PT、持有上限、retry或加注。只允许一次共享native SELECT，不重建labels、hash大库或重放旧金融。已包含于成交价的滑点只归因不重复扣除。

主2020stress要求NFC自身收益>0、相对CONTROL收益增量>0、DD不更深、既有同indices的252日block/2000次配对log增量95%CI低>0；另外三组收益差>=0且DD不深，NFC自身四组收益正。两个既定family-held的已识别u日等权诊断增量须均>=0，未知差异可能翻转就不签泛化；held不跑资金。年度/2026不完整年/贡献集中/gap/>1R损失、所有unknown/open/stale与空账户DD N/A都保留，不能用胜率或单事件均值替代现金证据。

不支持即停止此scalar/lag/Ridge/NARROW包，不扫分母、类别规模gate、方向、变化、window、模型、stop或risk。正结果仅进后续严格验证，不能直接正式或增加投注。

## 执行与反思

111投影/112模型由独立实现agent负责，113原现金包装由另一agent并行实现；只写对应新文件与少量新增语义fixture，不重跑旧suite。actual须等109终态、来源接受与root精确hash输入授权；尚未授权金融实际。actual终态后114另派独立agent全面核来源、逻辑、模型/完整预测/账本/置信度/bug，最后root决策。

协议10,850B SHA80b9eb2f8e959fb61218b92c3c35049a3f5084817d784c211ece2fc5970a81bc；小实施澄清SHAcf11f1d328ee7a0083668c7a364bf0f526c1c1612f55a26ce4880ed800f2e10e，明确4074日lag、raw恢复全集、四量必要条件与主base相等的门边界，未改科学字段或预算。

开始/结束新增按本包收益调参：否。历史同史多轮择题的过拟合风险：是，新来源不消除研究自由度，2020/2023/held不冒充新盲样本。继续价值：是，限这一真实新观测和一次固定增量检验；完整更高收益/更低DD/极窄损加注目标仍未达到。正式/CTP/订单/分钟/Git/外线/根memory与back_log不动。
