# Stage539：固定 sector 残差头 actual 后独立复核，接受计算、关闭本规格

- line_id：`futures_full_market_long_signal_ai`；时间：2026-10-21 04:29 CST；day 模式。
- 阶段性质：538 唯一 actual 训练完成后的独立数据/逻辑/结果/置信度/bug 审查，非资金回测资格认证；非重要突破。
- 完整目标仍是六所 98 历史产品 / 95 family 的高质量绝对 long，成本后收益更高且回撤更低，再检验窄损与加注；独立于正式 C9/月池。
- 本 agent 只写自己的 review 工具、机器审查与本阶段；不改 538 实现、LINE、registry、其他线、正式/生产或 Git。
- 开始过拟合判断：**是且高**，同史反复择题，单个低自由度候选与一个固定 placebo 不重置研究者选择史。开始继续价值：**是，限完成已冻结试验的独立证伪**，不再讨论新惩罚、分组或斜率。

## 结论

**C/I/M=0/0/0；接受 538 计算与完整选择政策的实现，接受 `nominal_cash_prerequisite=false`。停止本固定 taxonomy / sumw1 / lambda1 / 冻结52残差截距方案，不跑现金。** 不是因形式上的未知门而被动搁置：held1 的 C−A 和 C−B 已知支持均值均为负，已经不满足收益前冻结门。此结果不证明所有行业分类、部分共享或 AI 都无效，也不给换分类、惩罚、目标、交互、品种或年份救参的理由。

主样本的小正数不替代跨 family 证据；本轮所有 R 均值都不是账户收益、复利、最大回撤或加注能力。没有新增金融结果可供挑选。

## 冻结规范及实现预审

536 协议 SHA256：`acd8fcbf9e738e266067179a6b1fe240e09775ade737d1616b73abf4a46cf592`；537 inventory：`015c814fe1298c7ee7e8808ef03330dcd14532e5f11796ee390bcba35a17ba2b`。538 最终脚本 SHA：`4e2e9f956f6856040049f84f78ff8a29c22163b772c7f3d063cba8a3319ebe6b`；fixture SHA：`0213d552604ca3abbc29973f07b0c47f582b7d0a811bc20ba556c679519066a5`。

actual 前定向读新脚本与 fixtures，未读旧大表；确认冻结的原 COMMON52、原成熟/union/day 权重、lambda1/sumw1、unknown/p0 精确零 fallback、原完整负分域、独立 held 头、C−A 与 C−B 两组各非负且每对至少一组严格正的 gate。冻结映射在原 family hash 两侧各保持标签 multiset，EC 单例固定；额外仅用小 protocol 独立重建这项映射，结果完全一致，没有重扫新 cache。

未知训练有质量 q 时，实际 `G=sum(w*Z*Z')` 一般为 `diag(p)−(2−q)pp'`，不能直接套 `diag(p)−pp'`。`sumwZ` 与 `sumwdelta` 也不能预写 0。538 正确保留此公式；本轮实际 q 在双精度误差内为 1，所以均值近 0 是实际重算结果，不是先以 S 无行情作假定。

外部方法边界沿535已经实际查询的 [Stan 官方部分共享案例](https://mc-stan.org/learn-stan/case-studies/pool-binary-trials-rstanarm.html) 与 [Stan 维护者模型索引](https://github.com/stan-dev/example-models/wiki/ARM-Models-Sorted-by-Chapter)：它们支持共享截距的模型解释及留出评价，不提供本线期货 alpha。此阶段是固定规范实现审查，没有追加网络择题或第二套规格。

## 唯一独立实际审查与覆盖

独立工具：`tools/stage539_sector_residual_review.py`，不 import 538/130/156 的拟合、权重、选择或统计函数。先用纯合成例核 union/day 权重、未知正质量 Gram、K 重选和 ordinary/F 家族优先；编译通过。root 确认 538 完成后才启动本工具。

- 538：root 唯一 actual，12/12 offset，0 base refit / cash / SQL，exit0，182.728989 秒。
- 539：唯一独立数值审查，exec session **45175**，exit0，**43.186809 秒**。独立重建原已拟合头的线性代数不是新增候选训练；没有再次启动 538。
- 每个新训练 compact 各读一次、唯一 train raw26 NPZ 一次、完整 forward base compact 一次、main/held choices 各一次；其余为小模型、scaler、protocol、绑定和 daily/annual。旧大输入、旧训练表、原生行情、SQL、下载、旧现金重放均 0。
- 六 fold 的 cohort/成熟时钟与完整行数、日期、family、family-u union 组数均核；held 整族排除、已知日期严格早于 cutoff，未添加 K 训练域筛选。
- 从 entry/exit 索引独立构造 family-u union、同 family 并发倒数 uniqueness、月份均分、逐 u 总量与原均值1权重，再归一 sum1；不是直接采用作者新 weight 列。
- 从新 raw26 和原已绑定 portable/scaler 独立计算 52 与 Ahat、原 Y−Ahat；独立重解全部 12 个 G/b/gamma/delta/df/q/sumwZ/sumwdelta，核未知与训练未见组 fallback。
- **1,933,480** forward 行完整，main 与 held union 各 **966,740** child；两侧身份/父关联/部署 cutoff/原 held hash 一致。完整 **161,014** 母体在三 arm、main/held 两域均保留，**966,084** 条 choices 的 action ID、月份、准入/抑制状态精确一致。
- 用独立 K/正分/月内排序/ordinary-F 规则重建三 arm 政策；从实际 chosen action 重建 main/两 held 的 C−A、C−B、B−A，family-u→等 u、逐日及逐年诊断、same-action unknown 与 distinct-action unknown，全部匹配。2026 仍是不完整年，不把年度切片当独立实验。

实际最大绝对误差：权重 `9.95e−14`，Ahat `3.55e−15`，头 `1.54e−14`，完整 forward offset `1.46e−16`，chosen score `1.78e−15`，汇总均值 `2.71e−20`；daily/annual 均在约 `1e−16`。整数、身份、selected、动作/月份与未知计数精确一致。没有剩余 material 计算差异。

## 结果与不确定性

下表为既定“实际 chosen action 原 stress R、family-u 再等 u”的**已知支持诊断均值**：

| scope | C−A | C−B | B−A | C−A distinct unknown | C−B distinct unknown |
| --- | ---: | ---: | ---: | ---: | ---: |
| main | +0.000292331272 | +0.000429956785 | −0.000137625513 | 1 | 1 |
| holdout_0 | +0.000114203498 | +0.000555341684 | −0.000441138186 | 1 | 1 |
| holdout_1 | −0.001096434136 | −0.001097507354 | +0.000001073217 | 2 | 5 |

main 156,085 family-u、held0 62,434、held1 93,651；各 1,643 个源日。原 ordinary/F 去重完整。C−A 共同未解决但动作相同的计数 main/held0/held1 为 51/27/36，C−B 为 51/27/35；这类增量严格为0并披露共同未知。异动作未知保留 NaN，不填0、不填负类；没有结果界就不能把已知均值称为全域政策证据。未计算新的统计显著性或盲 OOS 置信声明。

12 个新增头 df 在 **0.611365—0.684207**，均小于1；C 的两个 main df 约 **0.658122 / 0.661289**。强收缩确实落实，低 df 仍不等于可靠泛化。EC 在所有训练头均未 warm，实际修正保持0；S 未知仍0，不把元数据占位当可学样本。C 的7个非运价组在各训练 fold 均有质量，但这不增加原留族/成熟支持的经济多样性，也不把任意 placebo 当抽样 p 值。

同 family/产品、u、部署 fold 的修正是一个常数；已逐行核完整 forward offset，所以 `score_i−score_j` 在同产品月份间保持，可以直接由已核公式证明。改变的是原 `score>0` 的行业准入门，经入选集合、占仓与共同预算间接影响暴露；没有新增行业择时状态，原现金也不按跨族 score 排资金。

different/add/remove/switch 的动作变化细分：**N/A，本次工具未保存该额外计数**。root 同意不为该解释性统计重扫大 cache；不能以低 df 或小均值反推变化数量很少。所有实际选择本身已独立精确验证。

## 机器结果与始末反思

机器结果：`outputs/stage539_sector_residual_independent_review/actual_review1/review.json`，**14,923B**，SHA256 **`4df99decc1cf4af267f4875a5fb3b4c3119add4adedf69b0ccfbe4133132c111`**。独立终态：同目录 `actual_terminal.json`，绑定 session/exit0/实际耗时/最终机器结果 SHA。review 源绑定已在机器结果保存。

新增实际策略参数：本 review 0；538 已实际按536新增12个固定 B/C 残差头，原52/止损/执行/风险未改。新增/修改/删除资金回测结果均0。期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率：全部 **N/A，无新现金回测**。累计候选 fit 因538从511增加到 **523**；完成cash仍 **278**，旧partial仍 **1**；独立审查的12次方程重建不再计入研究 fit。

结束过拟合风险：**仍是且高**，本轮没有看成绩后调参，但多轮历史选择偏差未消失。结束继续价值：**本次独立验证是且已完成；继续此固定 sector 截距包否**。负结果是一次允许失败的实际检验，并非要求事前保证盈利，也不因原全市场目标未完成就继续本包造变体。

最少下一实际动作：root 接受本次独立终态、绑定539至本线状态并按预门关闭固定规格；**0 新 cash，不更换 shrink、taxonomy、placebo、目标、斜率、cutoff 或品种救参**。原完整高质量 long / 高收益低回撤 / 窄损加注目标未完成，不晋级、不加注、不改正式/生产/CTP/邮件/任务。由 root 决定下一次有独立价值的信息或经济动作，不由本 reviewer 顺势提出下一参数。
