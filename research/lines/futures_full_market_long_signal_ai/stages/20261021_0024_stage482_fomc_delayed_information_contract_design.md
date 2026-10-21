# Stage482：FOMC延迟异质信息的一次测量合同，先补精确公告前投影

- line_id：`futures_full_market_long_signal_ai`；2026-10-21 00:24 CST。独立设计，非突破；未执行实验，也未签发actual授权。
- 六所98历史产品/95家族、399252母体/1552456子动作、原129 stress first-exit目标、原资格/0.25N/SL/K/风险均保持。累计沿479为481完成fit/258完成cash及1旧partial，本轮全部新增为0；正式C9、月池、原四前瞻账户隔离。
- 先读registry，实读474/477—480及067/129/130/156、270、041/475的小记录和相关源码/小manifest。未读取原actions、COMMON、分数、价格数组或数值Y，未访问SQL/H5/行情CSV；未下载源、运行外部代码或派子agent。只新增本stage与小JSON设计，不改LINE/registry/旧工具。

## 裁决与一手方法

**当前“FF4正值=紧缩”的signed规格NO-GO；纯数值FF4×SP500 pair可以条件设计，不因尚无现成投影而永久否决。** 481同事已报告，两份作者代码只证明FF4被列入利率意外、SP500直接入M及后继PCA缩放；没有raw单位/报价方向/跨期桥接。一个固定、全局、非零的乘法变换可由训练内标准化和自由系数消去；跨年代变化的尺度、工具或公式不能由此修复。也不能由25h、DST两锚或标准化修复首发PIT、供应商修订、缺失和逐事件endpoint未知。这里最多允许带上述限制的历史数值反证，不能命名已识别政策冲击，不能实用上线。

本轮重新查验[AEA原论文摘要](https://www.aeaweb.org/articles?id=10.1257/mac.20180090)：联合利率/股票变化用于分辨信息类别；它不许可在raw定义不明时硬签经济方向。[BoE1114原文](https://www.bankofengland.co.uk/-/media/boe/files/working-paper/2025/liquidity-monetary-policy-and-the-commodity-futures-market.pdf)§4.1.3/§5.2明确以成交手数×合约大小×结算价构造名义成交额，并用事前成交暴露交互检验异质响应。该研究的19个海外商品、2000—2008公告日结果不证明中国全市场25h以后有效；不复制其因果HFIV、方向dummy或窗口。作者[固定commit仓库](https://github.com/marekjarocinski/jkshocks_update_fed/tree/f788aef7d573f87f28b70ffc3763e73c4886a53f)网页本轮两次返回获取失败，GitHub方法证据复用477—479固定捕获及481两文件核证，不声称新增成功拉取或核作者全仓。

## 唯一必要的新投影：有本机来源，尚无所需派生表

067只投影母体代表epoch在`v=u−1`的S，不是事件发生前完成日，也没有全子月的volume/现金乘数；不能与129延迟后`u_volume`相乘冒充事前暴露。但现有来源足以实施**一次exact(epoch,pre_event_completed_date)投影**：Stage266的clean DB给出精确epoch/date、已转为单边手数的`d.volume`及原source locator；原CSV/H5给settlement；041给9502/9520精确epoch的`contract_multiplier`。266的`canonical_values`和小`unit_contract.json`已明确单/双边转换，**直接使用clean volume，不再乘volume_factor**；factor只用于追溯及与原量核对。041把国内CNY作为研究假设，未逐合同核币种，且乘数是合约快照、非逐日历史版本。对债券/指数等使用每报价点现金价值的`contract_multiplier`，不是把实物吨数规则套给所有产品；名义值仅是该现金报价模型下的CNY等价交易额，不等同法定债券面值或真实支付现金。

最小任务不新建数据系统：一次母/子身份流定位每场事件首个可消费u的全部候选epoch，再对这些epoch查询公告前最后完成日。固定研究日完成时刻为上海18:00：`p(e)=max{原source日期t: t的18:00<公告上海时刻}`；`u(e)=min{原source日期t: t的18:00>=公告UTC+25h换算上海}`；D仍为完整5587日历的`u_index+1`，不是下一条有价bar。18:00是本合同显式的保守研究时钟假设，不是已核vendor或settlement实际发布时间；若root不接受该假设，精确消费时钟即真实阻断，不能假造“真实时刻已认证”。国内D的夜盘可能在其名义日期前夜开盘，故必须保留u/ready/D和夜盘解释；只能计原129实际D-open后的bar模型净R，不能把公告到D的gap当可赚收益。逐事件实际入场时钟仍不由日线证明。

源投影白名单与预算详见JSON：一条只读SQL仅join请求的exact(epoch,p)，禁止重新拉全1552456 native；原locator优先，仅原schema无结算列才按067已固定RQ替代，缺行/坏值/身份或OHLC冲突不得换源。用`log(clean_volume × exact_cash_multiplier × settlement)`，不以close填S、不用旧可用日代替p、普通/F不互借。保留原量、factor、乘数/币种假设、S打印值、来源SHA/locator和状态。CSV每物理文件最多一次，H5最多两次只读打开、每请求key日期索引一次/只取请求记录；本机源已有，不是下载任务。预算耗尽或stat改变即保留现场停止，0自动重跑。真实覆盖/原字段可用率仍unknown，不在此稿编造。

## 一次经济反证的冻结对象

若root接受上述研究假设，可把投影和以下测量放在**同一actual，一次IO、0预测fit/0cash**中，不再先跑多轮小盘点。全母/子流各一次保留身份及所有状态，只在事前`u_action_eligible=1`且原共同`D<K`域定义可行动estimand；不取score>0、原选中、已成交、closed或赢家集合。取事件后的首个u，不给旧事件无限TTL；所有事件类别/原0与缺失保留，SP500缺失不换FUT。同u多事件保持各自ID并标碰撞，不将重复的同一后续路径算独立事件；无法分离时只报共同碰撞块，不称单公告因果效应。2010—2019为开发描述，2020—2025为固定反证期，2026单列支持/未成熟，不宣称全新盲OOS。

主对象仍是129的stress净R first-exit：已完成filled用原`net_R_stress`，确定未参与的政策结果为0并与trade target分列；未决/缺价/右删失不填0。不得用K退出、log效用、固定日收益或新止损代替。唯一异质项是`事前log名义成交额 × [FF4,SP500]`，两个原变量系数自由，不选紧缩符号/阈值/象限。公告前close只可用于单列`公告前完成日→D-open`的不可得调整诊断，不能代替settlement或进入Y。

为区别“独立新源”与“相对已见52有增量”，只做一个预声明的线性增量诊断：nuisance为原COMMON52、暴露直接项、事件和family截距；两个新列为按2010—2019事件等权均值/标准差标准化的原数值pair与事件内中心暴露的交互。每事件总质量相同，每family等质量，family内月份/普通F均分，权重仅依事前域。两时期各一次FWL/QR诊断解，分别记录`diagnostic_linear_solves=2`，不藏成“完全无估计”，不建新预测模型、不扫描lambda/learner。设计矩阵除尺度与符号外固定；主报告是交互系数、stress R量纲及两时期方向一致性，反证期不再选方向。该检验至多回答给定线性52 span是否残留异质关联，不证明条件互信息、因果机制或现金排名提升。原26及missing列照用，不重新发明COMMON或原annual包。

统计单位是事件/共同u块，不是panel行。输出每事件/全部95family及六所的支持、未知质量、贡献和固定系数下删一事件/删一家族影响。另以原entry/exit/unknown区间建立事件依赖图，同行月份、相同u及跨事件路径重叠均连接；独立连通块若不足，则置信推断unsupported，不给行级t值/虚假窄CI。FWL系数是Y的线性函数，故对未知Y逐项作完整识别界；first-exit无已证有限未来上界时就用无界，**不能从已闭Y的min/max借界**。暴露/时钟/原pair缺失同样是full-domain未识别质量，known-support点估计只能诊断，不能给完整GO。若完整界含0/无界、方向翻转、依赖不足或只靠一两事件/家族，关闭本规格；不缩短25h、不换FF4/stock代理、不挑品种或重分时期续试。支持也只允许root另评估一次增量预测/现金合同，不代表本任务收益/DD、窄损或加注合格。

## 终态与反思

本轮只完成设计；新增/修改/删除策略参数、金融结果及旧文件均0。权益、总收益、DD、Sharpe、滑点、交易次数、胜率N/A。当前signed规格NO-GO；数值pair为`conditional_research_design_only`，**没有实际投影/经济证据、冻结授权或实用资格**。真正阻断是精确投影尚未生成、消费时钟须root明示接受研究假设、完整未知界及事件有效支持尚未测量；raw单位跨期/PIT未知限制解释，不能包装成已修复，也不单凭固定单位正号未知宣布纯数值永远无价值。

开始/结束本轮按新成绩调参过拟合：否，没有新成绩；长期同史反复选题风险：是，暴露/标准化/检验形式也消耗自由度。继续价值：是，限一次上述有界投影加有限反证；泛扩源、先建训练系统或复活旧annual/K/log/共同宏观scalar无当前价值。若任何真实经济实验发生，之后须root另派独立agent全面审数据/逻辑/未知界/置信度/bug，再裁决；本设计者没有自行派遣。完整用户目标仍未完成，生产/加注资格false。

设计JSON：`outputs/stage482_fomc_delayed_information_contract_design/design.json`；只供root独立决定是否修改、冻结和执行。
