# Stage496：具名会员残差头实现已就绪，尚未执行历史实验

- line_id：`futures_full_market_long_signal_ai`；记录时间2026-10-21 01:49 CST；不是重要突破。
- 已先读`research/registry.md`，并读493来源排重、494身份附录、165接受合同、root495完整协议；只新增本阶段自己的工具、测试、output和本stage。未切分支或工作树、未改LINE/registry/旧工具。
- 开始反思：同一历史长期择题的过拟合风险是且高；当前实现只验证已冻结识别对象与数值约束，不以新收益选规则。继续一次有限证伪有条件价值，因为姓名配对是170匿名HHI不能复原的信息；不是会员聪明钱认证。

## 已实现的唯一规格

遵循root495 SHA `d3e3a5430b18ef71293cb950c06c5ef4e68f56d452edad3a8bf2bd343a653918`。新输入来自现成162规范向量，不下载新数据：精确epoch、完整052日历u的紧前v、verified多空榜内贡献，逐行复核已保存的long/short vector SHA；不最近成功前填、不跨all/F别名，不补未披露真实仓位。

每个原标签优先精确`N|exchange|member_name`；只有姓名空才用`I|exchange|member_id`。不做法律实体或别名合并。以原披露同gross计算`z=(L-S)/gross`和匿名`r=(sumL-sumS)/gross`，仅训练内正gross token进入词表，未来或held标签不参与建词表。

B仅为[常数1,r]，拟合冻结原130预测残差；sumw1、斜率罚1、截距不罚、无zscore。C冻结B，在signed token上追加无截距Ridge1；`H=stack(ones(p),X_B'WZ)`的SVD零空间P固定系数约束，`beta=P solve((ZP)'W(ZP)+I,(ZP)'W residual_B)`。因此训练新增项严格正交B共同匿名方向、系数和0、`df<=traceG<=1`，同时披露实际参数数p。全OOV的C增量严格0但C=B；缺源双方都逐值fallback A。权重复用原130 interval-union/equal-u算法，但在来源/eligible/K/成熟/held补集上重新计算后归sum1，不冒充原52训练数值权重。

原52六模型、原129stressR目标、0.25N、155/156共同K及完整六所98产品95家族政策保留。源覆盖SHFE/INE不是缩池依据。没有新增阈值、窗口、风险预算、止损或执行行为。

## 单次实际入口与检查点

入口`tools/stage496_member_identity_residual.py fit`需要495完整绑定、root exact源码bundle授权和全新496目录。当前没有此实际授权，也没有启动actual。

1. 已接受162规范源一遍，写source scope身份与原vector SHA、稀疏具名signed/gross；先做source-only零Y结构检查。
2. 原129一遍固定白名单，保留全部source可见历史identity/标签，以及全部966740 forward已有标签，以免差异候选被人为变成unknown。该流会看到原metadata和R；成熟支持门只用metadata/有限有效性，不声称0Y读取。
3. 所有六成熟fold先完成严格cutoff、held补集、正支持词表、null维度、`trace>1e-12`及forward支持门；任一失败则0fit/0cash停止。不为过门修源/合并名字。
4. 仅通过门后读旧COMMON一次，写165413个source-observable行的26列供独审复用；原六52模型/scale只读，最多六B和六C微型估计。每次物理solve完成即增加并落盘计数，再检查方程或报告。
5. 原130分数一遍覆盖全部1933480 main/held行，共同156选择逻辑重算全部9个完整母体政策；保存source overlay、原A主政策与156严格chosen/selected核对、年度全98产品95家族源/missing/OOV/nochild诊断和全部held已有标签差异。
6. cash handoff只指向新choice、共同K及489既有不变causal16/mother7，不新增原129现金大表流、不重放A157，不在本工具运行现金。

源完成、各fold支持、各B/C物理solve与输出、全选择结果均有保存。失败无自动重试。独审可复用本次派生source/COMMON/labels，不必重复旧大流或现金回放。

预定作者大流预算：162规范源1、129 whitelist1、原COMMON1、原130 score1、489 mother7 1；旧全母0、原1.26GB raw0、SQL0、下载0、原52重训0、现金0。金融预算仍须root单独授权，code-ready不是actual凭证。

## 合成验证与来源调研判断

已运行专属7个synthetic unittest，全部通过；未跑全suite。覆盖：保持匿名量的姓名置换；精确名称/ID命名空间；OOV与缺源不同fallback；sumzero/约束Ridge/df界；纯匿名方向拒绝；严格成熟/cutoff/held补集；紧前日与F不补；完整母体保留missing/nochild。只用toy，无历史源、大表、Y、native行情或账户读取。

调研沿root493/494实际读到的[官方披露语义](https://www.shfe.com.cn/content/cxxc/7wsxx.pdf)及[AkShare维护者原映射](https://raw.githubusercontent.com/akfamily/akshare/main/akshare/futures/cot.py)：左右榜内名称和量是原观测，经纪会员聚合不等于最终投资者，未上榜不等于0持仓；网页或可变main不认证完整历史PIT。自己的判断是允许一次强收缩、可反证的条件信息检验，不据此提前认定alpha或跨周期稳定。

## 结果与后续

新增实现参数仅来自已冻结495，未修改或删除任何旧策略/金融结果。实际新fit=0、cash=0、历史大流=0、SQL=0、下载=0。期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率全部N/A；本阶段没有金融结果。累计继承493完成fit/266完成cash及1旧partial，未增加。

`outputs/stage496_member_identity_residual/code_ready.json`包含最终sourcebundle、授权字段与读取预算；498可在root actual授权前独立静审，实际完成后再独立核source/model/choices/cash。不存在因等待今天日线而暂停历史研究。

结束反思：新增收益后调参否，当前无新收益；整体同史自适应择题过拟合风险仍是高。代码实现与有界验证有价值；反复扩测试或重新认证旧raw无价值。该固定规格若失败即停，不改词表、lag、方向、alpha或风险救参。完整全市场高质量做多目标未完成，未取得窄损加注、生产或正式C9资格。

## 2026-10-21 01:56 CST：首次actual技术中止与最小恢复准备

root后来授权的唯一实际session68782已真实退出1，耗时76.807743秒，0fit/0cash/0SQL。162源一遍已完整规范投影170803，source-only六cell支持门已完成且ready；随后完整129 whitelist流结束，在新写的“子产品数=98/子家族数=95”断言中止。这个断言把完整政策母体的全域误当每个品种必须有原生子候选，与原129已接受186400个无子母行的语义不符。原失败异常未保存实际观察子产品/族数，因此本次不猜测实际数或宣称知道哪一项OR触发；这是作者新增guard语义错误，不能作为数据损坏或alpha失败结论。

只做以下修复：原1552456行动行、966740 forward行、连续seq和所有身份/日历仍严格检查；子产品和族必须属于已经完整验证的98/95母域canonical集合，不要求集合相等。完整母域及无子行保留。新增专属toy用完整母域含永未列出/无子的品种、子域仅少数品种重现原guard的RED异常，随后修正为GREEN；全部8个synthetic tests通过。不是扩大模型测试或改变任何math、标签、权重、源语义、止损、风险、执行规则。

下一次若root批准恢复，`recover-source-fit`新入口要求准确495、最新源码bundle、原失败manifest及三个source checkpoint绑定；直接读原run的source稀疏数值/身份投影及已完成source_X门，不再读162、原raw，也不重算已完成source门。129中间结果在原guard前没有落盘，随进程退出已丢失，所以必须明确再做一次同样whitelist流：作者累计129完整流将为2，而不是1；原COMMON/score尚未读、fit仍0，所以后续不重复已完成模型或现金。

恢复时在guard前将真实行动行/forward行/观察子产品族及canonical数量写`original_action_domain_precheck.json`，避免再次丢失诊断；输出完整母和实际无子/观察域报告。全部恢复预算和所需新授权字段保存在`outputs/stage496_member_identity_residual/recovery_code_ready.json`。未自动重跑，当前恢复actual=0，须498限定delta复审与root新的明确授权。

本段财务指标仍全N/A，首次实际0fit/0cash不改变累计估计数。过拟合反思：这是恢复原冻结科学问题的技术修复，不用收益选参；长期同史风险依然高。继续一次准确恢复有价值，重读已成功源、泛审或修普通小差异无价值。
