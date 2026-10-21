# Stage005：全市场做多观察母体唯一联合独立审查

line_id=`futures_full_market_long_signal_ai`；2026-10-18 11:19 CST；独立审查人`ai_label_validation`；非alpha突破。先读registry、LINE、001/003事前合同及266固定来源资格，再等002和004真实终态通知后审实际字节。只新增本文及 `outputs/stage005_opportunity_independent_review/`，不改作者源/测试、旧数据、LINE、registry、其他线或Git，不派agent。

## 结论

**接受固定合同下的代码与实际完整观察母体，Critical/Important/Minor=0/0/0。** 接受对象是Stage004当前两个源、指定manifest/terminal/gzip，以及002实际输入盘点与003固定来源绑定；不是全市场历史上市目录绝对完整性、全市场可交易、训练标签、模型或alpha资格。`financial_ready/label_ready/model_ready/production_qualified/publication_pit_certified`继续false。

本次只有一次独立实际检查命令：

```sh
.py311/bin/python research/lines/futures_full_market_long_signal_ai/outputs/stage005_opportunity_independent_review/review_actual.py
```

实际11:19:20.309276—11:19:25.451589 CST，工具chunk `7013d0` **exit0 / 5.141656秒**；脚本内部计时5.142365秒。stdlib-only，不导入作者选择器、不重新导出、不重hash378MB DB、不运行旧suite、native、金融、模型、prepare、provider或网络。所有实际JSON/CSV/NPY解析消费已核SHA的同份bytes；大库仅继承既有SHA资格并核stat/无sidecar，不能将这一边界写成新全库逐价认证。

## 代码与有限测试读审

实际完整阅读 `tools/stage004_product_day_opportunities.py` 和对应四方法测试；没有复跑作者已真GREEN的四方法。作者RED/GREEN/compile作为明确的作者证据继承，不冒充本人的独立运行。

- `:71–77,126–136,149–153`用六所完整contracts目录建立roster并按EXCHANGE.PRODUCT.YYYYMM核身份/重复，保留DCE L_F/PP_F/V_F及无scope clean行产品；没有用今日存续产品或有行情集合替代完整来源目录，也不补造上市公告。
- `:101–109,138–169`只看u当日accepted、有限正价格、合法OHLC、正V；按成交量降序、有限非负closeOI降序/缺失最后、epoch升序选择。没有C9信号、正式月池、train/openOI、D行情或未来成熟条件；closeOI不足只影响同量时排序，不把合法OHLCV删除。
- `:113–117,170–186`输出目录×绑定calendar完整积；无参考的价格/量保持空，方向只long，逐日版本eventID与代表epoch分开。planned D仅由固定calendar后继产生，不查询未来D价格。
- `:80–87,208–224,238–262`以mode=ro/query_only读取；小绑定先读bytes核SHA再解析，读取前后DB及小源stat一致；既有输出拒覆盖。绑定后的大库SHA明确继承266，不假装本轮重算。
- `:278–292`明确known-at只是历史信息集合同；未伪造午夜feature_known_at、成熟label、可成交或金融资格。作者四方法分别覆盖完整roster/旧标记、排序及epoch/无量非法行、前缀/D不筛选、真实只读与绑定/sidecar拒绝，范围与003相符。

JSON的`source_bytes_hashed_again=0`在相邻database_sha_policy约束下指大库全hash为0，小绑定实际已核SHA；不把该表述扩读为没有核小源。输出missing closeOI类型状态是允许分支；本固定实际源closeOI缺失0，未以该实际表声称新分支产生了真实记录。

## 实际全表与独立SQLite证据

本人的脚本独立解析绑定NPY（stdlib头与int64），核4074个唯一递增目标日期；从只读SQLite读取完整10,880个catalog身份、98个产品，核roster及元信息状态，未重新扫描4831原始价格源。完整gzip每行检查：

| 独立核对项 | 实际结果 |
|---|---:|
| 完整产品×calendar | 98×4074＝399252 |
| 唯一(product,u)及canonical eventID | 均399252，无重复/缺格 |
| observed_long_research_opportunity | 212852 |
| no_accepted_observation | 186400，全部数值空，无收益0 |
| 全表candidate_count加总 | 1552456，与002/266接受行数一致 |
| 缺真实openOI参考/旧train=0/旧legacy=0参考 | 各117995，均保留 |
| DCE F参考产品日 | 702，三家族均保留 |
| DCE.S | 4074空观察，未删除或推断原因 |
| 最后u=2026-10-16仍观察 | 85产品，D=2026-10-19，不要求未来价格行 |

所有输出参考epoch逐行属于真实catalog相应产品/年月；全表long、合法数值/OHLC、正V、空状态、calendar后继/执行未评估状态均通过。完整产品年1666格、所年102格独立重算与导出相符；002的产品年观测数/日历数逐格同本次全表，不能把2672旧观测或900旧多空事件借作本线样本。

另外只从SQLite原日期索引查询**19个产品日、105条原合约日**，覆盖六所早期/尾部、CZCE.CF.201005与202005跨十年、三类F、DCE.S首尾无行；按独立排序重算最大V/同量OI/epoch，并逐项核价格、量、OI、缺失、旧标记、来源ID/locator等字段。全部相符。SQL样本及候选数逐项保存于`actual_review_checks.json`。本次未逐条重取212852个代表的全部候选，也未声称105条样本重新认证了整库价格；覆盖来自固定源码审查、全表身份/状态核验、有限原DB价格/排序证据与继承266来源接受的组合。

原DB读前后都是378552320 bytes、mtime_ns1792236170627661666、inode28078628，WAL/SHM均无；大库SHA `a63f92ce7e1d51080ba92f7214fc493f1e6a69aa0079d6ecef7190eea9b58711`只继承原266独立固定来源资格。98是当前完整来源catalog，97是有clean产品；两者都不是独立核对过的交易所全历史上市公告总数。无参考日只能称no_accepted_observation，不能拆成已认证未上市/退市/无成交/缺数据原因。

## 实际终态与绑定

002：root实际通知`49e768 exit0 / 15.858875秒`，对应handoff/actual_terminal与artifact bindings实际全部匹配；002不是作者自签的独立资格。004：root实际通知session82511/chunk1249a2 exit0，与11:14:34—11:14:59 actual_terminal相符，唯一导出1次；本人没有伪称自己轮询该作者session。

| 接受对象 | SHA256 |
|---|---|
| 004 selector | `a6093f91c30fe835f3ddd84882a074f7b13185ef36013d2ed6f41a0e9ee8f8af` |
| 004四方法测试 | `f9357a8fc03ae90f310665b33578f023ad273e6796c87bbe3efa746c41edcd64` |
| 004 manifest | `1c1c28e54af995dbe4aa516fcd0d7aa80e9be347fe0efaa4408f329425274003` |
| 004 actual_terminal | `a72b06d9dcfab8e6e41261cc35d1e5dcb8c53762a28741463412b7c9f7da447b` |
| 004 panel gzip | `8c6fc733cb14bb2ceb7573735d11f26e8885efd7cfce0d7be5232a3b3910a9ce` |
| 003 root小绑定 | `4423b84d1f16c76947d59a9c1a247916e44d634ebba77ece5b02ebf56260baeb` |
| 002 handoff | `855ea6ba469a9c91b947e8fb3084adf97f766bb1fedd87cf08afd738b3182caf` |
| 002 input_inventory | `5d3b65aa5058911f6a0cc4a4895736109a68c5c1c90201bcbd8e7bf402eb3f6f` |

实际各小绑定、输出CSV/gzip、完整checks、SQL哨兵与读前后stat都在本目录JSON中。原输入不因本审查被重写；本receipt为新层独立观察资格，不修改004的原manifest为accepted，也不改变266旧价格/单位资格。

## 未判定项与后续边界

本轮不判定正式主力、可交易状态、可成交量、历史具体发布时间/修订、真实乘数/tick/保证金/费用/会话/价格限制、窄止损分钟先后、未成熟标签或模型预测力。DCE F为独立品种身份，未以普通L/PP/V参数授执行权。完整product-day观察的数量不能称独立交易经验。

不以这些执行缺项阻止本次仅观察层接受，也不扩展为全市场再清洗/再下载工程。下一步由root另冻结收益盲的小型long路径/执行合同与样本ID；不回到旧19多空pilot、不先训练或联合扫窄stop/杠杆。只读母体通过不意味着需要立即重做已失败的高分加注/meta-label。

## 调研、指标与反思

来源判断沿001/003已查交易所/官方GitHub与266原单位/日线文档，本轮不新增网络检索或运行外部代码。它们支持字段时点、真实合约与信息集约束；不能证明全市场训练或交易资格。新增/修改/删除策略参数、模型、回测结果均0；期末权益、收益、回撤、Sharpe、滑点、交易次数、胜率均N/A。

开始/结束新增过拟合：**否**，只核事前固定观察/代表规则和来源，没有按收益选品种或未来成熟筛样；旧历史反复研究的选择风险不因数据审查消失。开始/结束继续价值：**是，限于已完成母体之后的一次有界路径合同**，没有AI优势证据，不应把行数、窄R分母或加注收益当目标达成。目标active、production_qualified=false。
