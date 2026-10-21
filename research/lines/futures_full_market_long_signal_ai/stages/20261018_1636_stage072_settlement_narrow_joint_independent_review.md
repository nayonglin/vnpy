# Stage072：结算信息×跨日窄初损的独立审查

- line_id：`futures_full_market_long_signal_ai`；记录时间2026-10-18 16:36 CST。
- 当前阶段：069科学合同有限静态复核＋067唯一实际投影的有界输出验收。不是070/071源码终审，更不是12fit/24账户结果审查。
- 重要突破：否；正式A/B或生产操作：否。仅新增本阶段独立checker/输出/本中文记录，不改067/069、冻结063/064、旧结果、LINE或registry。
- 本轮结论：**未发现Critical/Important（0/0）。067输出支持另立069研究mask；是否签发source_acceptance与实际授权仍由root决定，本审查不代签。**

## 科学合同与调研判断

已读registry本线、069完整计划/JSON、067实际stage/小交接/manifest/terminal与相关因果字段实现。外部依据沿本agent068实际查阅的[MIT止损原稿摘要](https://dspace.mit.edu/entities/publication/bb69ca4b-0cdc-487f-831d-63b2e84fafee)、[Backtrader维护者stop源码](https://github.com/mementum/backtrader/blob/master/backtrader/brokers/bbroker.py)和[Lean期货fill源码](https://github.com/QuantConnect/Lean/blob/master/Common/Orders/Fills/FutureFillModel.cs)，本轮没有新网络/下载或外部代码运行。判断：单一预知barrier的日OHLC研究触发可定义，但不证明限价、深度、盘内跳价或真实成交；结算字段的来源存在不等于识别增量。

069明确直接采用3信息（COMMON/SETTLEMENT/OHLC_PROXY）×2初损（2N/0.25N）×2训练截止，12fit；六组合各161014、共966084个向前拼接分数；2冷启×2成本共24账户。不再叠加068建议的机械8账户。两种政策共同X26保持旧2N单位，各用自己的Y、first exit、成熟日期、训练内family并发与u同权。共同scalar的训练半池化、原模型参数和无阈值扫描均有固定合同。

已明确原始D.open参考F与不利fill不同、Wilder N不同于旧DAY简单ATR，所有k相关手数预算/持仓风险均须同步；风险率不加，gap可超1R。未知与开放不填0，不用未来闭合筛交易；2023模型按预先时钟接续、旧仓按原政策退出；空对照DD为N/A，不自动失败或通过。跨止损是模型/政策包效果，不声称纯止损或纯信息因果效应。上述设计未发现实质阻断；这不是实现已经正确的结论。

## 不可变输入与独立范围

| 输入 | bytes / SHA256 |
| --- | --- |
| 069计划 | 11093 / `09bfa91e95b854a346ad20f59ea837739d4d037e277ba108d8e782a40e6d583d` |
| 069 protocol | 以收据实测为准 / `0418566cd9b624fb5a985448b3b0d4c94dbef56280feffd49bce09e1c5bf2dde` |
| 067实际manifest | 2421 / `75e63071fa5d90c27d6fd54acd278b80c523bba1ef6236c2848b889d05496303` |
| 067 projection | 31253909 / `b9407b90c727f976201d70bf4cceb91994f78712d17441bc9887d00d609159f4` |
| 067实际terminal | 214 / `fb572fc86a54b1bf3e36d20ca3efff8fea705cd8761395717def6f34ffd42c32` |
| 067小交接 | 2432 / `3687e0291e07757dfe6e1e1771db592112ff6e5371b4c315c2ec6b120522eea8` |

独立工具`tools/stage072_source_bounded_review.py`不import067/070/071或作者计算核心。一遍读取压缩projection字节并只解析一次，以049 accepted features母表核完整ID/顺序和同epoch前日N/C，以accepted完整日历核严格v=u前一source日；manifest六产物大小/SHA闭包逐一核对，1.7MB summary只hash、不展开source catalog。

本轮没有重新读2619原CSV、H5、native SQL、完整原生路径或旧金融结果；不重跑22tests。H/L来源一致性与全N递推仍继承已接受原生/纯042的有限来源范围，本次不冒称全原生复算。独立同epoch前日代表交叉覆盖188569行，N(v)对049 normalizer(v)×accepted C(v)最大绝对误差`4.001776687800884e-11`；不匹配代表的行保留继承范围，不拼新旧epoch。

## 唯一有界实际终态

执行命令：`.py311/bin/python research/lines/futures_full_market_long_signal_ai/tools/stage072_source_bounded_review.py`。实际session `17034`，启动chunk `6b33bf`，终态chunk `b790bb`，exit0。**一启动一完整，8.49977675秒，47项通过，0C/0I**。没有失败重启或为格式重算。

checker SHA `4cf086931e6cb959762f95d56630826c54861258c62d4cbd64fabd1150963daa`，18489B。后续070/071或金融总审使用新的checker/目录，不修改此已跑checker或receipt掩盖身份。

## 全母体、算术与069研究mask

- 完整399252行/唯一event/原顺序，98产品、95family、六所；原reference 212852，无epoch186400，family/F归属和sequence全同049。
- `observed=207849`，占完整母体52.059601%、reference母体97.649541%；全N ready194709，观测且N ready193817。
- 原`feature_available/training_accepted/strict_pit_accepted`每行仍为0，available_at每行空白；历史重建＋一个完整source日滞后没有变成首发PIT接受。
- 当前候选C可数值比较208539行，accepted C最大差0。另311个RQ缺日期保留原已比较OHLC状态但候选C为空，projection为unknown，不造数/不入mask；不能误把该历史比较状态当作当前缺失候选已存在。
- 观测C−S对保存差额最大误差`2.842170943040401e-14`；unknown差额保持空白。身份/日期冲突与OHLC冲突0。
- source状态完整分解：observed207849、无epoch186400、missing_native_v4002、source_date_missing311、rule_family_unknown681、range_unknown9。9条越界不修价、不裁剪、不换源。

本轮**另外**产生`research_mask_069`：observed+value_observed1+N_ready20+有限正C/S/N+精确同epoch/date+严格前一source日+before_vendor_final_boundary+固定OHLC一致+已知benchmark、允许两类历史rule状态。没有使用收益、原训练标签或未来退出筛行。全部原source行与接受标记均未改。

| mask统计 | 数量 |
| --- | ---: |
| 全母体研究可用 | 193817 |
| 2020+研究可用 | 106957 |
| 合法零scalar | 6624 |
| historical_family_reconstruction_not_full_vintage | 132739 |
| family_default_assumption_no_primary_rule_bound | 61078 |

规则默认族进入的是069另定研究假设，不是067原training0被改写。unknown的scalar不填0作为观测；未来54槽缺失表示仍应由已冻训练预处理完成。本次只核输入mask，没有实际标准化/训练。

family×year完整1615格，母体分母合计399252，与067独立覆盖表逐格一致；同时保存exchange×year、annual与完整mask。年度示例：2020完整23814/reference15271/observed14802/mask13008；2023为23716/16455/16353/15502；2026为18424/15964/15039/14520，明确2026为截至10-16部分年。其余全年度均在机器输出，不择年展示成胜率。

## 输出、后续边界与反思

输出目录`outputs/stage072_joint_independent_review/source_bounded/`：`checks.json`、`mask_summary.json`、`mask_family_year.csv`、`mask_exchange_year.csv`、`mask_annual.csv`、`research_mask.csv.gz`、`review_receipt.json`与started/terminal；另有外层`source_bounded_run_receipt.json`保存本次命令/工具句柄与精确SHA。没有原始OHLC/H5/DB复制。

- 独立review receipt：8170B，SHA `f638a8634a813fc50391e11a187a9ac8addb8d0b85d01e4cd86531542203a3b7`。
- 独立terminal：224B，SHA `41864966488536d72610cb927ff71bdafff7485a561b9023759802a53d09e3e7`。
- 完整研究mask：19979710B，SHA `9b97774c72db4110fc352d199573c239695bc0d7add98efd659f87cde5e937de`。

本轮新增/修改/删除策略参数和金融结果0；fit/cash/SQL/下载/原源重读均0。期末权益、收益、DD、Sharpe、总滑点、交易数、胜率全部N/A。067作者的一次source SQL不冒称本独审SQL，也不计为金融成绩。

开始/结束新增按成绩调参过拟合：**否**，按已冻科学合同核source支持域，没有新收益、择源或调stop；历史研究选择、规则重建和日线成交假设仍存在。开始/结束继续价值：**是**，来源与因果输入的有限实际证据已落实，可由root另签研究接受并推进实现；不是又扩大来源资格工程。070/071最终源码与实际12fit/24账本尚待新的独立审查，计算/alpha/完整目标均未提前通过，full goal active未达成。
