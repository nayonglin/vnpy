# Stage455：Con4 可见来源与六fold支持独立审查

- line_id：`futures_full_market_long_signal_ai`。记录时间：2026-10-20 22:11 CST。
- 当前模式：先静态、后一次源独审；非重要突破；未触发拟合、现金回测或正式策略A/B。只修改自己的唯一stage及`outputs/stage455_Con4_visible_review/`。
- 结论：**completed；core_blockers=0；core_problems_remaining=0；all_support_passed=true。** 只接受条件性历史时钟下的来源资格，不是strict-PIT、原首见vintage、alpha、金融、加注或生产资格。

## 调研、最终合同与静态检查

开始前已在本任务读registry/LINE与450 scope；本455承接root已冻结453而不机械沿用451旧ordinary边界。父agent刷新CFTC官方发布规则、原论文及cot_reports维护者资料；本审查未联网，判断是官方年包足以核来源值，下载器和当前snapshot不能证明当年首发，也不证明中国窄损策略有增量。

最终protocol SHA `c82dfb499558b0ecc32e8f9654b3361f68741a74400c67507b1d01a69ca9e053`，clarifications SHA `9ce259c878659832da5d9b7e6936a5d724eafe1aba7449944d9092006945a5ff`；454工具SHA `06c9b4264c2e5fdbedbdbe292991ffd530cec6cf7f914f20c3198e57e887c38d`。独立静态读取454代码、8项测试及其既有fixture receipt，未重跑旧fixture。代码没有导入实际源的import副作用；读Y/common/score/price/ZIP/API/SQL或拟合调用均未进入source路径。

普通周冻结原生Tue→假定Fri再多7个日历日后的次NY00，即Tue+11日周六00；它是固定保守研究延迟，不是actual发布日期。已确认实际日期仍nextNY00；2013有限mask后仍明示恢复假设；2019铜采用root明确锚点；2025含12/30至源尾隔离。pending跨active gap取消、deferred≠unknown、原due隔离/consumed-asof floor、修订优先、Mar17同刻顺序、7日NY日历TTL与[available,expiry)边界均按最终合同审查。

## 唯一实际独审与覆盖

- review session `84454`，一次启动、一次完成，exit0；实际 2026-10-20T14:10:06.798874+00:00 至 2026-10-20T14:10:19.491960+00:00，耗时 `12.693288` 秒。未重跑454，未导入454作者函数。
- 独立工具从453源字段/例外/clarifications构造行资格，按时间桶处理expiry→reset→grant，保留source-asof floor；与454的全部episodes、八代码状态流及母查询逐项对照。
- 原448仅读一次：`6,680`行、`835`原生asof、完整8代码grid；每个原字段和Con4数值与新episode全核，没有只抽样原数值。四后修订、所有guard/plan、7条ION actual覆盖等不靠原asof或下载日提前放行。原ZIP没有读取。
- 新manifest/source episodes/clock streams/audit/npz/mother-support各一次；新源SHA/bytes逐件从同一次读取核对。新manifest精确绑定 `91296ee3972f3f3826edb8be7748b64febbc44a3142f8bff8f26163c8f568640`，`1,642,665`B。
- 旧mother仅一次明确身份usecols，全部`399,252`母行原序、ID/产品/家族/u/reference身份与新audit逐行一致；98产品/95家族保留。独立全量q向量、NaN mask、episode指针及audit全部时钟元字段与NPZ精确相等。`28,697` finite母行，`763` availability groups，`764` release episodes；同一可得时刻不因多asof/8channel/日级复制而增加独立时间事件。
- 六份原training CSV各一次仅读ID/u/family/原sample_weight；全`1,386,540`训练行逐fold复核原序、child/action aliases、epoch aliases、母ID/产品/家族/u映射、cutoff、held排除及原行/日期/家族/family-u组数。没有读Y或重算原权重。
- 每fold从新母q复制至其全部原child，独立重算finite/缺失权重、mu/总体方差/scale、源范围、独立发布组、episode/family/年覆盖及两种发布权重集中度；训练与既定预测support全对象均与manifest一致。六小scaler仅核原绑定，不读COMMON大数组。
- 共 `288,686` 个断言；q与身份向量为精确相等，汇总浮点最大绝对差`7.275957614183426e-12`，来自不同求和次序、在预定相对/绝对数值容差内。所有六支持门及各q_statistics一致。

| scope / cutoff | 原训练行 | finite训练行 | train / pred发布组 | train / pred映射家族 | 独立mu | 独立sd |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| main / 2020-01-01 | 247,795 | 59,530 | 474 / 152 | 8 / 8 | -0.185665207042019 | 0.201666613042418 |
| main / 2023-01-01 | 445,475 | 89,541 | 625 / 137 | 8 / 8 | -0.195313815637105 | 0.201153212420833 |
| holdout_0 / 2020-01-01 | 171,712 | 40,097 | 473 / 152 | 6 / 2 | -0.205544295547433 | 0.211511265425204 |
| holdout_0 / 2023-01-01 | 297,404 | 59,977 | 624 / 137 | 6 / 2 | -0.214547396673704 | 0.21308187552236 |
| holdout_1 / 2020-01-01 | 76,083 | 19,433 | 473 / 152 | 2 / 6 | -0.124224031579465 | 0.151433499233552 |
| holdout_1 / 2023-01-01 | 148,071 | 29,564 | 624 / 137 | 2 / 6 | -0.135724754333984 | 0.146388619768452 |

## 局限与接口

旧大CSV的SHA身份沿用已接受绑定而不重新全量hash；本轮确实独立parse当前ID/w一次，并核stat在读取前后未变化。未重验Y或原label maturity，原接受的训练选择与COMMON scaler身份沿用；本轮足以验证source标准化的权重和支持，不代替后续模型/Y/方程/全预测审查。历史普通假日、原首见与当前snapshot修订完整性仍非已证明事实；root冻结的lag/恢复/候选隔离窗都须保持研究假设标签。

供456的小receipt `13,639`B，SHA `d2f4bc036f980abe76e7bf0828b32896e5df0ace7841c37463cb92a582d76c01`；内含status、两种core字段、all_support_passed、protocol SHA及source_manifest精确binding，六fold关键统计与完整对象对比结论。较大详细物料见receipt.detail；没有把每组weight明细重复进小receipt。独立reviewer工具`28,426`B，SHA `2bb9d2c710bcb7074050c4b399e9da3b4dabf6862b6caf2aa61ec3250ac5cdc1`。root仍需按既定流程接受source，不能由本receipt擅自授权金融。

## 变更、结果与反思

新增自己的review_once.py、independent_detail.json、review_receipt.json和本文；未改454代码、453、原源、模型、账户、LINE/registry、Git或生产。无新策略/交易参数；金融结果新增、修改、删除均0。期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率均N/A。Y/common/price/score/fit/cash/API/SQL/原ZIP/author rerun均0。

开始/结束新增收益择参过拟合：**否**，独立核固定来源/时钟与标准化支持，未看金融成绩或改mask救门；历史择题风险不因此消失。开始/结束继续价值：**是，仅指这次必要来源独审，现已完成**；六支持门通过只允许root考虑既定下一步，不证明功效、泛化或收益。

本agent不更新LINE/registry或根memory/back_log；请root按本唯一stage合入。
