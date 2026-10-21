# Stage156：原生事件身份与去向接合的独立审查

- line_id：`futures_trend_triple_screen`；记录时间：2026-10-18 11:04 CST。
- 本阶段是独立审查 Stage155 已闭合真实字节，不是 Stage140/153 第二轮审查，也不是新回测或训练。先读 registry、LINE、Stage152 与 Stage154，沿用既有研究线。
- 用户最新目标为全市场全品种高质量【做多】，不限正式 AI 月池；root 另建新线。本审查仍只覆盖旧 19 产品、900 个多空事件的身份层，不扩大至新目标的数据资格。窄止损和加注分别证伪，不受三重滤网形式或失败 B_OFF 等待条件限制。
- 唯一审查者按 Senior Code Reviewer 标准审源码、来源、实际数据关系与置信度；未派子 agent。只新增本文及 Stage156 输出目录；不改来源、Stage155、交易代码、测试、LINE、registry 或 Git。

## 审查结论

**接受 Stage155 为有限身份/原始去向接合，可作为旧范围身份映射参考。Critical=0、Important=0、Minor=0。** 未发现当前冻结输入、当前一次实际输出及上述声明范围内需要修复的问题；不为未来泛化输入、样式或无限防御检测增加阻塞。这不是全机会资格母体、成熟训练集、经济母交易账本、AI alpha 或金融/生产接受。

审查完整读取 `outputs/stage155_native_event_linkage/build_linkage.py` 的 385 行及全部实际输出，用自写 stdlib 检查独立重建身份和连接；未 import 或重跑作者导出器。各来源以同一次 read_bytes 的 SHA 校验和 CSV 解析，19 项来源绑定、10 项 manifest 产物全部一致。A_OFF 的八份相关 CSV 哈希另与 Stage106 已接受独审的 export_hashes 一致；该独审与 Stage110 接受记录的 receipt 绑定一致。A0 只核其候选观测与既有 Stage001 receipt，不延伸成 A0 执行账本审查。

Stage155 实际单次导出证据：chunk `03adb4`，10:58:46，exit 0，0.207604333 秒，stderr 空。独立检查实际运行：chunk `e4716d`，exit 0，0.0819585 秒；`all_checks_passed=true`。没有重复任何旧 suite、价格资格或导出。

## 逐关系证据与解释

| 核验对象 | 独立确认的事实 | 可用边界 |
| --- | ---: | --- |
| 005 potential 与候选五键 | 900 唯一 outer；两 A 各 886，键集完全相同；14 仅见 005；重复/无效 0 | 005 potential 不是全部合格机会；两臂不是 1772 独立样本 |
| 原始观测 | 2672=900+886+886，全行身份和原状态保留 | 不按收益、胜负、是否成交筛除 |
| 原 entry_risk | 320=312 flat+8 roll；319 非空 order | 诊断不等于已成交，更不等于经济闭合 |
| 精确初开 | 311 个不同 event，279 个 u 日期 | 全五键唯一 opened 候选→原诊断 order→实际初开→四表 trade_id/clock；非同日合约粗联 |
| 未解 flat_entry | 1，2020-05-11 CF009.CZCE，long_case2，candidate_index=37、entry_index=14，order 空 | 原因未知；不补造订单、收益 0 或 AI 拒绝 |
| 四表 fill | 817：404 open、413 close；trade_id 各唯一且集合一致 | 核对真实合约、方向/开平、交易日、signal/物理执行时钟、order 和 episode；不重定价 |
| retry | 85 显式关系，82 回连原生 event，3 属 roll 父单 | 原 root/child/order/episode/同日先后时钟逐项成立；不得作为独立初开或额外样本 |
| roll | 8 显式目标 fill/diagnostic 关系 | 目标方向、日期、合约、targeted 状态一致；source close/event/经济 mother 均空，不能宣称统一母链 |
| 连接到 event 的 fill | 393=311+82 | 424 未连含 413 close、8 roll 初开、3 roll retry；均未伪造归属 |
| 原 pending | 1，cu2611.SHFE Close/Submitting | 原行保留，event 空；不认作平仓完成 |

事件 ID 是原五字段 canonical JSON 的完整 SHA256，独立重算全部一致。六种原 signal 与 long/short 严格对应，日期规范、真实合约和产品前缀一致；14 个差集的完整五键已另存 independent_checks.json，不以推测状态解释来源缺行。

两 A 各 574 个 skipped 的原原因是 short_signal_rejected 320、ai_product_pool_blocked 151、sizing_zero_volume 87、concurrent_limit 16。仅池阻挡项明确标记 AI 产品池；所有 skipped 不能合称 AI 拒绝，也不能作为负标签。005 原 terminal_pending 仍保留，未选、未触发/未成原因未知、未成熟和未解关系不被并成一类。

源码关键接缝：155:165–188 的 outer/歧义保留；190–220 的四表精确身份；224–262 的完整五键到实际初开；264–299 的 retry/roll 分边；301–312 的原状态与 pending 保留。独立检查从原表重建这些关系，且额外核实初开执行交易日等于 005 原 next-day、retry 同交易日和 roll 目标方向/日期；它们支持当前产物，未升级成通用任意数据输入认证。

## 时间、泄漏与置信度边界

u_date 是原逻辑信号日；原 midnight datetime 不能证明真实信息在午夜已知。旧 Stage827 `_sync_entry_risk_diagnostic` 在实际成交后回填 signal_order_id，所以这里是事后身份映射，不能把该 order 或账户未来去向用作 u 时刻特征。实际四表一致和 signal<execution 时钟可核查身份顺序，不能替代未来 feature_known_at/PIT 合同。

所有 maturity 是 unknown_not_assessed，未生成 label_known_at、PnL、胜负、netR、质量标签；economic_mother 全空。独立检查实际导出字段和空值，并审生产者未使用未来收益过滤或连接。当前 311 初开不等于 311 成熟可训练样本；279 日期也不等于独立统计有效样本量。全历史已多次看过，不得改称全新未来 OOS。

## Declined to judge（交 root 在后续独立任务裁定）

1. 900 potential 对全市场/全机会的覆盖资格、14 缺行的因果、空 order 的经济结果：来源不足，当前保持 unknown 是正确范围。
2. 全机会成本后反事实路径、未选事件收益、413 close 的事件归属、跨 retry/roll 完整经济 mother、成熟时钟与风险分母：本次未实现也未认证。
3. u 前特征可得性、完整标签区间、purge/embargo 与训练集划分：身份表不能提供这些资格。
4. 当前与新策略的预测优势、窄止损成交质量、加注最优性、组合现金/保证金与实际收益回撤：本次无此实验，不签 financial_ready 或 production qualification。
5. 全历史价格、全市场独立重新定价、vendor volume 排队真实性：沿已接受源级研究边界，不重 hash DB、不重建 EMA、不扩大数据认证。V>=q 如被后续路径采用仍是研究近似。

这些是明确未宣称的范围，不是本次应补齐的缺陷，未因此触发循环修复。

## 调研判断与下一步价值

沿用 Stage154 已实际阅读的 Stanford Risk-Constrained Kelly / Distributional Robust Kelly 论文及作者 GitHub；不重复联网或执行第三方代码。我的判断：分布误差与回撤约束应进入后续投注研究，但不能以理论替代本仓库预测优势；mlfinlab 页面含 pass 也不能冒称完整可运行 splitter。旧质量分数/加风险等失败证据继续有效。

若后续引用这批旧数据，路径合同应按以下边界另行设计；本阶段不再推进旧 pilot，新全市场做多任务由 root 另线决定：按结构而非未来 PnL 预选普通初开/退出、retry、普通 held-roll、各 skipped 原因、缺 order、14 来源差集及 terminal/pending 形状；明确独立反事实环境和成熟规则，再检查真实退出、成本、风险分母与母链。先验证 AI 选别所需标签和时钟，之后分别评估窄止损与加注；本次不自行实现或运行 adapter。新目标无需硬等失败 B_OFF，也不能将 B 失败改写为成功对照。旧 19 产品/900 多空事件及正式池阻挡观测绝不代表新全市场全品种做多训练数据已经准备。

## 参数、结果与变更

新增：本文、review_linkage.py、independent_checks.json、review_receipt.json。修改/删除源码、策略参数、回测参数及历史结果均 0。金融运行、模型/训练、provider、网络、DB 读取均 0；金融累计沿交接仍 11 attempt / 4 独立 accepted。权益、收益、回撤、Sharpe、滑点、交易次数、胜率均 N/A；817 只是既有 fill 身份数量，不是新增交易结果。非重要突破、未触发新 A/B。

开始/结束过拟合判断：**否**，本次只核固定来源的身份与关系，没有按结局筛样、调参或拟合。但未来把未知/未选当负类、把 retry/两 A 重复计数、联合扫描窄止损与重注会放大过拟合。开始/结束继续价值：**是**，接合保留了可复验的旧范围身份参考；尚不足以训练质量模型或增加投注，更不是新全市场做多数据准备完成。

本审查一次完成，无修复请求、无第二轮审查要求。LINE/registry 合入由 root 决定；不追加根目录总账，不签金融或生产接受。完整 SHA 绑定与计数见本阶段 review_receipt.json 及 independent_checks.json。
