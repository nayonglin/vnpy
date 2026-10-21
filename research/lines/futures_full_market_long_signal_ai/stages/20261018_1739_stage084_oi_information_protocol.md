# Stage084 真实合约净持仓变化：一次独立信息对照

- line_id：`futures_full_market_long_signal_ai`；记录时间：2026-10-18 17:39 CST。
- 当前模式：国内六所全市场全历史品种long-only独立AI研究，沿现checkout/分支，无worktree/新分支。
- 重要突破：否；开始实际0；累计333fit/70cash，goal active未达成。正式版/生产/CTP/邮件/定时任务不在范围。

## 调研、第一性原理与选择

078已读取CME/CFTC定义、TqSdk/RiceQuant维护方代码、INE单位说明与Hong–Yogo摘要。OI是日终尚未平仓匹配风险存量，每张合约同时有多空方，不是市场净多资金或增仓必涨。该观测不能由现有OHLCV/期限common26唯一恢复，但旧价格×OI确认、削仓和风险恢复已有负证据，先验偏低。本次只允许一次固定连续标量的条件信息反证，不复活旧规则，不扫OI窗口/分母/符号/阈值。078来源与访问限制照保留，不冒称本次读完403论文正文。

083独立代数反证否决单独重训netCNY/ru：主stress同源接受域中为原net_R乘1/(1+8*stress_u_cost_R)，可由现有输入恢复，理想score>0动作不变；有限Ridge投影可变不是新增信息，未采用也不写成实测失败。因此选择有实质数量观测差的OI，不同时改目标、模型、stop或预算算法。080预过滤收益前一式已停止，本轮回到accepted070原分配，不能叠加失败规则。

参考：[CME OI](https://www.cmegroup.com/education/lessons/open-interest)、[CFTC COT解释](https://www.cftc.gov/MarketReports/CommitmentsofTraders/ExplanatoryNotes/index.htm)、[TqSdk维护方api.py](https://github.com/shinnytech/tqsdk-python/blob/master/tqsdk/api.py)、[SPO论文](https://arxiv.org/abs/1710.08005)。判断：信息不可恢复不等于可预测，更不等于可加注，只做最小可失败的实际对照。

## 唯一新观测与源语义

对004原代表epoch e、决策u，v=u之前一个完整源交易日，w=v之前一个完整源交易日：

`oi_scalar(u)=[close_oi(e,v)-close_oi(e,w)]/volume(e,v)`

- e保持完整YYYYMM真实epoch，普通/F不拼接，不用前日代表替代e，不改选约；v/w都必须是原冻结calendar连续索引。允许读取e当时尚非代表的已有真实历史。u与D及未来报价不进入OI输入。
- 仅消费已接受Stage266 clean_daily的canonical单边V/closeOI；不再除2。原固定source_id及单位转换合同绑定。两日同source_id且有效接受单位；单位factor跨制度变化如已由固定合同证明均canonical单边，可比较；不同source_id在本轮保守为unknown，不另外补源/拼字段/造证。
- 有限OI>=0、v分母V>0；缺任一源日/首bar/来源不可比/单位无证据/非有限/非正V保留明确missing原因。0变化及OI同为0合法，不能因真openOI缺失而删行。不是严格首次发布PIT，只是既定归档重建＋完整源日lag假设。
- 不裁剪大比率，不强加abs(deltaOI)<=V，不插值、不carry、不修隔离源、价格或旧DB，不按结果增加缺失规则。
- 完整399252母体与身份/原资格保留；missing进入两臂共享指示，不硬拒绝交易、不填成负类。保存v/w日期/索引、源/因子/可观察状态与标量；没有新标签。有限确定性首例用于独立SQL核验；不复制全库/OHLC/H5。

## 两臂、两时钟、两个训练外family组

- 固定NARROW原`net_R_stress`目标和自身成熟时钟、common26（仍为原2N单位）、26个共同missing、1个共享OI-missing、1个scalar共54槽。CONTROL最后槽恒0；OI用上述一列。OI缺失归训练均值后标准化0，两臂全部训练/预测资格相同。
- 固定Ridge(alpha=1,fit_intercept=True,solver=cholesky)，不裁剪/换目标/树/交互/seed/正负阈值/排名；实际只检验该加性线性增量，不声称穷尽所有OI条件关系。common与scalar各使用本fold成熟训练中加权有限均值/总体std，scale0或全missing=>1（全missing mean0），不读取验证统计。
- cutoff2020-01-01与2023-01-01，严格u<cutoff且非空label_known_date<cutoff、closed_complete_bar_model才训练；原family区间并发唯一性→u日期等质量→均值1权重，只在当前fold重算。截点以后未知/开放/取消不填0、不按最终闭合筛预测。
- main及holdout_0/1三scope；family组沿052既定`int(sha256(family_id.encode()).hexdigest(),16)%2`。holdout_g训练排除g，预测只评价g；自己的事前价格历史仍可用，不冒称没有query历史的zero-shot。每cutoff/scope/arm一个模型，恰12新fit；每臂主预测集沿accepted071的因果history-ready20全集，不因OI缺失或结果缩池。
- main2020模型只预测2020—2022；main2023模型预测2023至2026-10-16；同样应用held组。两个held组仅作训练外族信息诊断，不另跑cash，不用挑组/组阈值/组模型拼主账户。

## 8个新资金账户与冻结判定

只有main CONTROL/OI×2020连续/2023独立冷启×base/stress=8cash；CONTROL因共享OI-missing是必要新对照，不冒充旧070重跑或将旧070作为同信息控制。使用accepted070原reserve与纯run_cash_account，绝不调用080预过滤；两臂独立内生持仓/权益。

固定100万元、单family0.25%/总2%/buffered margin25%/buffer1.10、SL0=D.open−.25N/Wilder20/max(SL0,因果20low)、score>0、所有原经济/期限/换约/缺价延期/同日不重入/u预留/D只减不回收。无PT/DAY强平/持有上限/加注，不缩成旧Top10/19池。两窗均结束2026-10-16，2026部分年，重叠窗/成本非独立样本。

主预声明比较OI−CONTROL：主2020stress净收益更高、DD不更深、原252源日块/2000次/seed20261018配对日log差CI下端>0；base同方向，2023两成本收益差非负且DD不更深。复用079绑定的两个现成bootstrap indices（相同calendar），不另试块长或seed。

对两个held组各报告同截点前向样本、训练/缺失/完整标签状态、score、逐年和全family、已闭合共同机会的gated net_R差、信息预测误差差；只有各组按u聚合的名义已知增量均非负才支持进一步研究。其单位不是现金回报，不加总成账户收益。对两模型动作不同但标签未知的行单独保留；未知不能算0，也不能由known-mask好看推成全机会优势。

以上只为研究screen，不能证明全部市场/新family/未来稳定。任何主收益/DD/CI或冷启方向失败则停止这个固定日级OI标量/54槽Ridge/NARROW包，不换变换、窗口、方向、模型、产品、年份、阈值、stop或风险救援。名义通过但差异未决/删失可翻转则qualification unknown；未建立普遍损失界不假称已解决。即使通过也不增加投注、不晋级正式版、不宣称完成原goal，需另行多周期/新OOS讨论。

## 有限实现、实际预算与独立审查

085 source只写新隔离工具与必要新合成边界，最多一次只读native SELECT生成完整projection；086拟合/087现金另一owner实现，071纯训练定义/070现金定义仅接受引用，不改旧源、无monkeypatch。源1SQL、现金1SQL共享8账户，独立实际review可1次新OI列SQL重构核对；不重核整个旧清洗链，不读H5、下载分钟或整DBhash。

source/fit/cash每一phase最终源码/新tests/命令及最小具体manifest由root精确授权，fresh output，失败保留不自动修复重跑；这是agent内部运行控制，不向用户反复要求权限。只测试新字段/共享mask与train-only scaler/heldfold接线/新cash消费，不重复旧suite。一次聚焦preflight和实际后一次全面独立agent review足够，无重复资格流水线。

预算：新增12fit（不含必要合成fixturefit，另计）、8cash、0labels、源1SQL＋cash1SQL＋review1SQL、0旧金融回放/下载/整DB-H5hash；未实际前不写作已完成。实际保存全部模型/权重/scaler/predictions/labels状态计数、8完整账本/逐笔/年度/全family含零/费滑/暴露/unknown/贡献集中/零价情景、共同CI/门，引用旧source而不大量复制。

## 反思与记录

开始新增按新收益调参过拟合：否，唯一数量观测与公式在078已固定，原停止证据不删除，当前未见该新对照成绩；但研究者已见多轮历史，不能称无选择偏差或严格新OOS。继续价值：有，限一次真实信息增量的最小固定对照，OI prior偏弱，不做特征库/复杂学习器。期末权益/收益/DD/Sharpe/滑点/交易次数/胜率当前均N/A。

新增研究观测1、实盘交易参数新增/修改/删除0；目标/stop/成本/风险不改。各owner唯一stage；root合并本线LINE/registry，不更新他线，不常规追加memory/back_log。完整目标active，实施和数据合格本身不是收益进展。
