# Stage481：两份固定作者源码定义核证，当前精确金融规格仍 NO-GO

- line_id：`futures_full_market_long_signal_ai`；记录时间：2026-10-21 00:21 CST。
- 模式：一次有限实际定义核证，非回测、非重要突破，不触发正式候选或A/B。本线六所98产品95家族高质量做多目标保持，未缩为美国资产或少量国内品种。
- 前置读取：`research/registry.md`、479 `next_scope.json`、478独审、480两锚及477实际捕获记录。只新增本stage及481输出；不改LINE、registry、旧源、正式策略或生产。
- 开始过拟合判断：新增按收益调参否，本步没有收益、标签、模型或参数选择；整条线反复使用同一历史择题的风险仍是。
- 开始价值判断：是，固定两份作者文件可以分清作者输入命名、实际变换、单位与符号仍缺失的部分，并决定数值不变性是否能支持一个更窄的后续问题。

## 外部调研、真实请求与文件绑定

按479上限，只向作者固定commit `f788aef7d573f87f28b70ffc3763e73c4886a53f`取得`code/main.m`和`code/mypc.m`，各一次请求、0retry、25秒墙钟上限、禁止重定向、禁止替代文件。没有第三文件、其他央行、联系作者、外部Matlab执行或依赖安装。原385事件CSV未重取、未重读；其绑定和覆盖继承478，不能冒充本stage重新认证。

真实采集起止为2026-10-21 00:19:11.371223至00:19:13.337929 CST，脚本内部总耗时1.962653秒；唯一进程session47753最终exit0。2/2 HTTP200、各attempt1、0retry；终态`completed`，两项均`http_complete`、无error。这是网络接收和保存成功，不是字段经济定义认证成功。

| 文件与作者固定URL | 原body字节 | SHA256 | 耗时秒 |
| --- | ---: | --- | ---: |
| [code/main.m](https://raw.githubusercontent.com/marekjarocinski/jkshocks_update_fed/f788aef7d573f87f28b70ffc3763e73c4886a53f/code/main.m) | 1545 | `0f273a2c781e54dad9b5c9ef24797b4e23b15ae18498c7c29a9e81d0c2b8aa3a` | 1.135279 |
| [code/mypc.m](https://raw.githubusercontent.com/marekjarocinski/jkshocks_update_fed/f788aef7d573f87f28b70ffc3763e73c4886a53f/code/mypc.m) | 758 | `7efcb94510ff96e7e084f3e0c24f6f55367bb9195d78fee6fe633012572b356c` | 0.821588 |

原body保留响应原始字节与CRLF，没有改名义单位、换行、缺失或编码。每请求收据保留固定URL、HTTP状态、headers、起止、耗时、body字节与SHA；后续本地核对与原收据一致。URL包含固定commit，资格限于已接收的HTTPS响应及其本地hash，不声称额外认证整棵Git历史。

## 直接可证与unknown

| 核证对象 | 两份原文直接可证 | 仍unknown，不能补推 |
| --- | --- | --- |
| FF4作者用途 | main第6—8行将MP1、FF4、ED2、ED3、ED4列为`Interest rate surprises`，另选SP500；第11行从原CSV读表。 | raw FF4究竟是合约报价差或已换为隐含利率差、精确单位、正值对应利率上升/紧缩的规范。作者用途命名没有补齐这些定义。 |
| SP500数据通路 | main第8、23—26行选择大写SP500并将原数值列直接放入M；本文件没有对SP500做log、乘100或反号转换。 | raw SP500的精确计算公式、水平差/算术收益/log收益、单位和正值经济解释。原列无额外变换只证明通路，不能自行认证原始构造。 |
| 作者样本 | main第14—15行只在作者处理路径保留start年份大于1989的行。 | 这不授权本研究按覆盖删1987—1989；原385事件母表保持。 |
| mypc缺失和尺度 | mypc第9—17行识别全缺失行，部分缺失填0，各列除以本作者样本std，未中心PCA，再恢复全缺失行NaN。 | 这不是本研究可采用的缺失处理或PIT方案；不能把全样本作者变换当训练内变换。 |
| ED4对pc1的作用 | main第19行以ED4作为第三实参；mypc第20行用ED4的标准差乘回pc1，即以ED4数值离散尺度缩放。 | **没有显式ED4符号锚定。** mypc全22行未依据ED4相关、载荷或方向进行符号翻转；非负标准差不能规定经济正号。raw ED4的物理单位也未在二者定义；不能从pc1缩放反推raw FF4单位或正号。 |
| 时钟、版本与跨年代一致性 | 两份文件没有补足这些证据。 | 385行时区、每行原始发布时间/修订vintage、真实计算与送达时刻、跨年代工具/测量尺度是否为同一固定映射仍未认证。 |

作者main在全部筛选样本上调用mypc，并在后面生成poor-man、旋转和月聚合；本stage没有运行这些代码，没有取其pc1/旋转/最终月度结果作为输入，也不采用其缺失补0或全样本标准化。底层PCA实现即使有软件符号约定，也不能从这两份文件中认证为经济方向；这里的结论严格是“没有显式ED4经济符号锚定”。

## 固定尺度与反号的窄数学事实

令同一数值字段在所有训练和测试事件上仅发生全局固定重编码`x′=a x`，其中`a≠0`。用训练样本的均值和标准差且`σtrain>0`，有`μ′train=a μtrain`、`σ′train=|a|σtrain`，因此`z′=sign(a) z`。正比例下训练内标准化相同；全局反号下只是整列反号。若预测器含自由、无方向约束的系数，对应系数及其固定交互系数同样反号即可得到完全相同预测。标准化后对这些系数使用对称L1/L2罚项时，反号不改变罚项。

这只是条件成立时的代数恒等式，并未证明raw FF4/SP500跨年代的未知定义恰是这种重编码。未标准化且固定惩罚强度、符号约束、单边紧缩规则、固定绝对幅度阈值、非对称正则或按结果挑方向，都不能笼统借用上述等价性。纯无惩罚自由线性系数可用`β′=β/a`吸收固定尺度，但这也不认证经济语义。

**我的判断：这条事实允许提出一个不预设紧缩方向、对整列固定尺度/反号不敏感的数值假说；它不能单独放行本线当前精确金融检验。** 后续若采用它，必须事先固定双边/整体信息检验、训练内变换和对称模型约束，并明确只研究匿名数值测量；不得按结果命名紧缩、选正负方向或改代理。所有原六所品种不能因覆盖或效果被缩小，共同宏观标量本身也不能冒充品种异质排序。

跨年代`a_t`、工具切换、非线性或随水平变化的变换、事件定义变化与缺失机制都不被一个全局系数吸收。标准化亦不能解决历史PIT、时区错误、计算窗口或进入前收益泄漏。没有据此忽略478指出的来源/工具变化；本stage没有新增能够证明其可忽略的证据。

## 当前裁决和后继边界

当前精确规格为**NO-GO**：两份文件补足作者命名与变换通路，却未补齐raw FF4/SP500的完整单位和经济正号。未知名义单位或全局正号本身并非匿名数值假说的充分否决理由；满足上述不变性条件时，可明确把问题限定为匿名数值信息。当前尚未冻结完整的这种规格，跨年代可比性也未被证明；479要求的显式时钟/u/D合同、严格公告前可见的单一异质暴露、原accepted成本后可执行目标和有限新fit/cash预算，均不能由本stage代签。

480的一夏一冬两锚仅支持America/New_York/DST的有限解释，不能认证全385事件，尤其不能外推早期/非预定类别。`+25h`仍只是测量窗的保守计算上界，不是作者历史首发PIT或vendor firstseen。若后续设计采用纽约解释、延迟和当前快照，必须显式标注推断与修订边界，不能命名为严格历史PIT。

有限定义核证现已到上限，应停止取源和泛搜。此次不继续建模、金融检验、收益回放或部署；完整长期目标未完成。本stage不能授权以pc1/旋转或最终月度结果填输入，也不能以新增已知语义为理由改FF4/SP500、央行、频率、样本或风险参数。

## 变更、财务与独立复核

新增481采集脚本、两份原body、请求/汇总收据、定义审查JSON及本stage；修改/删除旧脚本与源0，新增/修改/删除策略参数0、标签0、模型0、金融结果0。0新fit/cash/SQL，0市场大输入、行情下载、CTP/订单/邮件/launchd操作；累计仍481fit/258完成cash及1旧partial。期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率全部N/A。

独立agent `/root/mechanism475`仅本地读取两个原body复核，没有新增网络或文件写；同意SP500在作者样本内原列通过、ED4只有标准差缩放无经济符号锚定、raw单位/正号仍unknown；同意固定非零比例下训练内标准化的等价条件以及跨年代/PIT/时钟不能随之消失。非回测，无新增金融成绩需要复审。

结束过拟合判断：本stage新增按收益调参否，两个文件和两次请求预先固定，未看收益、选方向或救参；长期同史择题风险仍是。结束价值判断：本次价值已实现，区分了作者命名、ED4尺度作用及尚无符号锚定；继续无限找定义或直接做金融无当前价值/授权。更窄的匿名数值假说仅可交后续设计裁决，不能将其当成本stage已经验证的alpha。

输出目录：[Stage481输出](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage481_fomc_raw_definition/)。原文：[main.body](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage481_fomc_raw_definition/main.body)、[mypc.body](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage481_fomc_raw_definition/mypc.body)；[捕获收据](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage481_fomc_raw_definition/receipt.json)、[定义审查](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage481_fomc_raw_definition/definition_audit.json)、[本地核对](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage481_fomc_raw_definition/verification.json)。不更新LINE、registry或根总账，由root合入者统一决定。
