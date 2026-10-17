# Stage016 四个受影响完整时段的研究修正表已构建

- line_id：futures_trend_triple_screen。
- 当前模式：离线数据资格修正；未运行金融账户，未部署。
- 记录时间：2026-10-18 01:10 CST；唯一构建耗时6.9645秒，exit0。
- 工作区/分支：`/Users/mac/Desktop/fian`，`codex/ai-training-data-expansion`。
- 阶段性质：已知source859 producer不满足completed合同后的固定范围数据修正。
- 是否重要突破：数据完整性推进，不是策略收益突破。
- 是否触发A/B：本阶段没有新A/B账户；仅为后续严格研究保留数据证据。

## 外部调研与判断

- 复用本线Stage014对原producer及官方TqSdk完成bar语义的核查，和Stage018正常公开历史流的真实证据。官方参考为[API文档](https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html)及[官方源码](https://github.com/shinnytech/tqsdk-python/blob/master/tqsdk/api.py)。
- 原source859按新datetime保存形成中的末行，后续seen-id阻止更新，因此不能把物理分钟覆盖当盘中H/L价格资格。修正范围由固定Stage010完整时段需求和来源决定，没有依据PnL挑选。
- 原Stage017失败、raw0、独立资格0均保留。Stage018相同目标下修正等待预算后，在同一正常api内idle两次仍完成12945分钟；其实际独立资格receipt SHA为`b7820471cc7d84963251182b8d10cf26e82cfc009a45e70ac9a7184ab39cd0cf`。Stage016显式引用018身份，不覆盖017失败证据。

## 本次变更

- 新增脚本：`tools/stage016_source859_qualification.py`及必要合成契约测试。
- 修改脚本：正式策略、原行情、Stage001回放入口及旧overlay均未修改；Stage016首次执行前显式绑定018来源与独立review。
- 删除脚本：无。
- 新增参数：构建CLI的两个独立receipt SHA绑定；没有策略参数。
- 修改/删除策略参数：无；AI、0.5R、费用、风险和资金规则未变。
- 验证：原5个范围/原值/loader恢复合成测试通过；018来源切换另1个必要入口contract先RED后GREEN。没有重跑旧账户或全仓测试。

## 数据和归因参数

- 范围严格固定为下表四个`vt_symbol × execution trading date`的完整交易时段。
- 现有base与002/011/015作为不可变上游；三个本机completed替代源和018 AP210原始完成记录，均绑定原字节及原CSV七字段。
- 只允许原base中source859的实际差异键进入corrections；非859旧键逐字段一致，open与openOI变化则拒绝；缺失分钟进入独立append-only表。
- 未读取PnL、未下载、未创建策略账户引擎或模型拟合。生产资格保持false。

## 结果

| 时段 | 完整分钟数 | 原source859键 | 实际替换键 | 新增分钟 |
| --- | ---: | ---: | ---: | ---: |
| cu2010.SHFE / 2020-08-27 | 465 | 284 | 283 | 181 |
| fu2205.SHFE / 2022-03-30 | 345 | 225 | 225 | 0 |
| AP210.CZCE / 2022-04-06 | 225 | 225 | 225 | 0 |
| cu2507.SHFE / 2025-06-11 | 465 | 1 | 1 | 284 |
| 合计 | 1,500 | 735 | 734 | 465 |

- 实际改变键为`734替换＋465新增＝1,199`；原source859中1键已与完成记录相同，因此不制造无意义替换。
- 非859旧键改变0、open/openOI改变0、删除0；四个完整时段重建后均与合格参考七字段一致。
- A0真实读取535个anchor请求、501个scan请求，共106,731个唯一分钟键。全部1,199个实际变更键（含替换，非仅新增）与其交集为0；因此本阶段有明确的数据因果依据复用A0原路径，没有重新计算或更改A0经济指标。
- 继承的物理readiness为20,191→20,193，新增就绪来自两个cu时段。fu/AP原本物理已覆盖，此次补上新的completed价格资格。该数量不是全市场分钟价格合格结论；Stage016价格资格仅四个时段。
- 全部绑定输入构建后SHA未变，原base/002/011/015及失败证据写入0；下载0、金融回放0、订单0、撤单0、CTP连接0、模型拟合0、production_qualified=false。
- 期末权益：N/A；总收益：N/A；最大回撤：N/A；Sharpe：N/A；总滑点：N/A；总交易次数：N/A；胜率：N/A。本阶段不是新金融回测，不能将这些字段填0或据此声称C0改善。

## 输出文件

- 输出目录：`outputs/stage016_source859_qualification/`。
- `summary.json`：SHA `0db3b3fbe4696b8bcc867460e1e81800f51a2f68e652bb5621e10bccaeb8cabd`。
- `corrections.csv`：SHA `373f0e29ef26fb1ffd1ea9143c3eb758a806bc6dcbe372c38b032c412c1f66be`；含原source、逐键旧值/新值及替代来源，loader须核旧值前置条件。
- `append_only.csv`：SHA `4386affa251886b98b3afca918aa9bc537fed8f523bf90ed4fbec44fc4ef74cb`。
- `a0_path_equivalence.json`：SHA `216a3e352c0b32a55a96cf792819ff18a191d8dff6e60d13b8252a55c647e326`。
- 另含逐时段资格、input_manifest、继承readiness、remaining_demand与唯一attempt开始记录。

## 结论与下一步

- 唯一构建成功，状态为`built_source859_delta_pending_independent_review`。独立实际审查正在进行，结论及receipt待追加；构建成功不自动授予loader使用资格。
- 研究loader仅在精确独立资格通过后启用，绑定原key/旧值，退出恢复loader及缓存。Stage016应处于所有append-only loader之外；四个所属时段不得再由其他overlay重复注入。
- 不自动开启C0、不部署、不做daily-open fallback，不扩大为source859全局重洗。FG209 anchor-only旧冲突保持隔离。
- 后续可用轻量数据整合将018其余38时段及将来019已签资格的分钟转为append-only；必须继承本阶段readiness并排除四个已归属时段，另行审查后才能使用。

## 过拟合与继续价值反思

- 运行前/后过拟合判断：否。来源缺陷、固定时段、完成bar和原七字段决定修正，没有看收益选范围或调参。
- 运行前/后继续价值判断：是。修正已证实影响盘中H/L的原始源，并用实际读集证明A0未受这些变更影响，使后续策略对比具有可解释数据基础。
- 不改本线LINE或registry，由root统一登记；本阶段不追加根目录历史总账。

## 独立实际审查补充（2026-10-18 01:16 CST）

- 独立receipt：`outputs/stage016_independent_review/review_receipt.json`，SHA `98b6ad7b3e312e839abb51eefb3377e8e5c7239fbdd44c4ae30df5e9ace2308b`；P0/P1=0，`qualified_research_source859_delta=true`，绑定summary SHA `0db3b3fbe4696b8bcc867460e1e81800f51a2f68e652bb5621e10bccaeb8cabd`。
- 审查覆盖四个精确完整网格与原CSV七字段、734个原source859旧值前置条件及替换、465个无覆盖新增、全部1199改变键与A0实读交集0。真实`read_qualified_delta`按最终receipt pin消费成功，纯fake故意异常后loader与三缓存对象恢复通过。
- 因此资格由“构建待审”推进为“四个精确时段的研究数据修正可消费”；原summary保留构建时状态和原字节，不改写历史产物。这不是全source859合格结论，不授权C0第三次回放、fallback或生产部署。Stage020可按此receipt继承readiness，但四时段仍应排除。
