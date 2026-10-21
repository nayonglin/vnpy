# Stage141 已接受账本资金差增量独审：设计与实施

记录时间：2026-10-18 23:21 CST。研究线：`futures_full_market_long_signal_ai`。非重要突破；没有新策略参数、训练、标签或资金账户。当前已完成有限实施，尚未收到141实际审查的root精确授权，未执行actual。

## 范围与接口

- 先读研究registry及138最终报告，确认当前排序优势未被证明、8个原CI均跨0、原133 unsupported与不加注/不晋级边界保留。
- 冻结139：`outputs/stage139_funded_gap_protocol/protocol.json`，9,963字节，SHA256 `7d07e65db4dd4287b0245b535c19af76d6a23ffc9e9896defab7f1b278b2057d`。本次仅141新增会计、身份与结果核验；原137接受资格直接作为信任根，不调用137/132/102总入口，不重审旧模型、native行情、保证金、预算或88条资金路径。
- 新增 `tools/stage141_funded_gap_review.py` 和 `tools/test_stage141_funded_gap_review.py`。不import作者140或具有import-time执行副作用的133，也不调用任何资金回放函数。
- CLI严格绑定139协议/SHA、140最终manifest/SHA、141源bundle SHA、root授权/SHA和全新输出目录。授权字段为 `stage139_exact_root_authorization_v1`、`authorized_by=root`、`stage=review`、固定 `protocol_sha256`、`attribution_manifest` binding、`source_bundle`、139 `input_bindings`、绝对 `output`、`exact_source_authorized=true`。
- 作者140产物的每个顶层输出binding均验hash；新作者源码只验证身份，不import或复用其数学。旧AI账本从已接受131 manifest的logical_name精确取binding，控制账户从已接受136 accounts取binding；不从裸目录发现输入。
- 全部161,014行main B原父本引用及4917 selected父本身份保留。4917×88本=432,696行book-parent、4917×84对=413,028行pair-parent完整域逐一核对，无事后入场交集筛选。

## 独立审查方法

1. 每个root按closed/open与fills独立对账：`Σfill realized_gross−Σfill fee+open unrealized`，与episode已记费用及closed net_pnl核对，再合计到`ending_equity−1,000,000`。部分减仓open贡献保留已实现与浮盈；滑点已入fill，不重复扣除。
2. root通过原child/parent/mother/epoch/product/family/u身份映射，不解析root命名。核一笔初BUY、正整数数量、终值数量、一致的入场费和初始risk；派生F/Y必须有限。该轻量桥一致性不重建成交价、mark、risk公式或资金路径资格。
3. 用5587交易日日历索引核完整entry decision域，包含start−1预留、end−1截至边界；只排除existing_position_reduction。无BUY的账面贡献为0，F/Y保持null，entry_execution_unknown与窗外父事件保留。不会把模型未入账0解释成真实执行已知0。
4. 双方入场使用F=`initial_qty×immutable risk_per_lot`及Y=`observed CNY/F`；风险项、单位项和单边参与项逐parent/逐pair回加ΔC。same-action不强设相同Y。总额亦按gross、negative fee、unrealized三项回加。
5. 每个固定随机对先分解，再对20个pair的CNY分量等权均值，独立匹配AI期末权益减20本期末权益算术均值；不平均F/Y后乘、不替换成log、中位数或最好seed。
6. 全部category/family/cohort/affected/path分层表、账户及pair汇总、8组总汇总、固定top5正/负父贡献均独立复算。positive_delta_CNY和negative_delta_CNY在各pair内部先分别求和，再按20pair平均，保留抵消信息。cohort-year只是u_date信号归属年；top表不删交易、不产生反事实资金曲线。
7. path诊断仅比较原顺序分数化fills与终态元数据，round12并绑定规范JSON；复用作者输出的union-schema缺失字段表示，仅是观察路径签名，不宣称完整日内/日级路径相同或执行未知抵消。

## 有限验证、复核和冻结源

- 按TDD先写缺实现RED，后实现GREEN。8个有限合成测试：partial-open净贡献与费用；错误BUY/fee/risk/手数及非有限派生量；F对称桥且same-action不同Y；无入场null与符号参与项；完整父域、cold start−1与int YYYYMMDD日历；normalized path和False字符串；固定20算术CNY均值；正负贡献保留抵消。
- 独立子agent仅静态读取141新helpers与合成fixtures，未读88账本/140或actual。复核发现原helper缺派生F有限性、数量轻量约束，以及fixture last_mark=106与unrealized=90不自洽。已补F/Y有限性/数量约束并将fixture last_mark修为103；没有增加实际价格/marks重验范围。
- root通报140首次派生在首本前因calendar int64 YYYYMMDD误cast失败；141不复现失败，有限夹具明确将20221230/20230103解析为ISO日期，防止同类适配错误。140实际重授权及失败证据由root归档。
- 最新验证：`.py311/bin/python -m unittest discover -s research/lines/futures_full_market_long_signal_ai/tools -p test_stage141_funded_gap_review.py -v`：8/8通过，0.003秒；py_compile及CLI `--help`均exit0。没有运行旧资格suite或真实结果审查。
- 冻结脚本：34,308字节，SHA256 `1d28178bac39778cff59fd042e02aee4f5a99850a004dbea0827f4bf781a1880`。
- 冻结测试：7,038字节，SHA256 `f1545ebe707918e8a69087b680c0c8de38e5bdbda2115f2df398552672e23d34`。
- 将上述绝对path/bytes/sha256 bindings按path排序，以 `json.dumps(...,ensure_ascii=False,sort_keys=True,separators=(',',':'))`编码，bundle SHA256为 `54be04e9e87201a1c2c2e63b8a19934f3b1f3cf20f67b6fe8f6f7f008215ad0e`。
- 新增SQL/fit/label/cash/native缓存读取/下载/整库hash均为0；实际141尚未启动。期末权益、收益、回撤、Sharpe、滑点、交易数、胜率不适用本实施阶段，原88本指标没有修改或重跑。

## 外部调研、判断与反思

查阅[Python3.11 math官方文档](https://docs.python.org/3.11/library/math.html)、[NumPy isclose官方文档](https://numpy.org/doc/stable/reference/generated/numpy.isclose.html)与[NumPy官方GitHub测试helper](https://github.com/numpy/numpy/blob/main/numpy/testing/_private/utils.py)。采用稳定求和与显式容差原则：金额`atol=1e-6 CNY, rtol=1e-10`，先拒绝非有限量，保留最大残差；不使用默认宽松容差。来源只支持数值工程判断，不证明策略有效。

开始与结束新增选参过拟合：否。本阶段只核已冻结会计口径，不改模型、资金、种子、风险、月份或筛样本；反复历史择题及事后故事选择风险仍存在。开始与结束继续价值：是，限一次解释动作R与资金增长差的机制坐标；会计分量是后验描述，不能识别纯选月因果效果或可执行加仓干预，不能据其正负救参。

下一步：等待140完成manifest及root精确授权后，仅执行一次141增量审查，将实际收据、终态、问题数与置信度追加本唯一stage。LINE/registry与142决策由root合入，本agent不改。

## 2026-10-18 23:24 CST：actual_run1失败保留，未自动重启

- root授权：`outputs/stage139_funded_gap_protocol/authorize141.json`，3,750字节，SHA256 `d846b70c799ef4fe163fc3410d4f2ce5639fdc5c2e1ebc4dcf3894e05da86d6f`。绑定140 `actual_run2/manifest.json`，7,252字节，SHA256 `4cb28f711632681bb16706cd94dcdd21e94ee503972adbf19f5eb1e9f302c2fc`。
- 唯一已启动141会话`72889`，exit1，实际62.252070秒。`actual_run1/actual_terminal.json`为930字节，SHA256 `99cd39bc8ba55b12a61b1dbfd56f0f43ae13834993771b356b79fae3495967a3`；没有成功review_receipt，不宣称独审通过。
- 已过阶段：88本root/fill净额与期末权益增长、432696/413028完整grid、84对parent级对称分解及gross/fee/mark、20对算术CNY、正负抵消、分层和top内部expected重建全部完成；随后第一张book产物外部比较在`observed_path_signature`字段停止，尚未比较外部pair/summary表。
- 只诊断单个MAXVOL primary2020/base root（child `stage129_contract_choice_action_v1_668c7b7a618e3223c177cc9b1a4b0eff979d21ff537a50ad3811788ea4ab8a68`）。SELL reference_price按141字符串再float读为`15821.592949406415`，按140 pandas默认数值读为`15821.592949406417`；round12后仍差2e-12。将同一root按默认数值解码后，独立signature精确等于140输出`82c3ea85d57ac468d1f985bf0abadca43d78b4ca795f785143de8f036e6e17a6`。
- 当前证据说明此root差异是CSV数值解析后hash表示差异，不是发现该root资金不平。未重算旧价格/marks、未改源、未重启actual。已向root提议仅signature投影匹配声明数值解码，在原有限夹具增加该精度反例，再新bundle/新授权/新目录审查；等待root决定。
- 本次仍为0SQL/fit/label/cash/native缓存读取。新增过拟合否；继续价值是，先修审查适配错误，不据失败或已过内核宣称策略有效。

## 2026-10-18 23:27 CST：root授权的签名表示修正，尚未重启actual

- 按root明确限定，先将原script/test复制到 `outputs/stage141_funded_gap_review/actual_run1/failed_sources/`，bytes/SHA与原授权完全一致；同目录`signature_parser_diagnosis.json`保存单root、两个解析值、双方digest及修正范围。
- 只新增 `signature_projection`，采用声明的pandas默认数值CSV解码，独立读取path用root/fills；`table(dtype=str)`金额解码、root净贡献、F/Y、分解、分组和容差全部未改。没有改140、139、旧账本或金融路径。
- 在原第6个有限fixture中加入`15821.592949406415`数值解码/round12 digest反例，观察缺helper RED后实现GREEN；仍为8项测试，无新增资格框架。
- 最新8/8 GREEN，0.005秒；py_compile exit0。新script 34,997字节，SHA256 `07120c64543ea18bb6084211699ebc107bc1ce0b42c95fc2335a7002fbad0eb1`；新test 7,606字节，SHA256 `d613fe76af99a68dbdc3a5ae0750ce27471ac4020fdb0850a53ee380de7625a5`。
- 新规范bundle SHA256 `fec52ec237f4b0b581ed787e56a38aca8d54080b3b4935082d278fe87244e99f`，待root新exact授权及fresh `actual_run2`。未自行重启。

## 2026-10-18 23:30 CST：actual_run2完成与独立结论

- 新root授权 `authorize141_signature_continuation.json`：4,232字节，SHA256 `cf0f7bdcd4e306511cecbf9be99026ca8fedad1e18a3c2c8072b6bbe70e963ed`。仅允许上节签名表示适配后的精确源，金额逻辑未改。
- 续审session `43913`，exit0，95.666019秒；实际总历史为run1失败62.252070秒、受控表示修正后run2成功95.666019秒。两个输出目录、旧源快照、原授权和失败诊断全部保留；没有自动重启或隐瞒失败。
- 成功收据 `outputs/stage141_funded_gap_review/actual_run2/review_receipt.json`：10,638字节，SHA256 `e545234a042e9b42909c60138e79a00a516325297dd13b3b0fd4737fae639b96`。
- 成功终态同目录`actual_terminal.json`：182字节，SHA256 `464138f4205f17c6d426b852c9c0ac991ac0a771ad8c0f1838fbfb6949db133b`。
- 完整通过88账户对账、432,696 book-parent、413,028 pair-parent、84 pair汇总、8总汇总、420 category、5,712 family、588 cohort、168 affected、327 path及80固定top记录的数学/身份/分量比较。原137 accepted bindings保持；没有原native、marks、预算或资金路径重审。
- 金额最大外部比较残差`4.656612873077393e-10 CNY`，低于冻结`1e-6+1e-10×|参考值|`容差。0SQL/fit/label/cash/native缓存读取；没有新回测指标，旧88本期末权益/收益/回撤/Sharpe/滑点/交易与胜率不变。
- 140归因产物科学/金额问题数Critical/Important/Minor=`0/0/0`。另有141收据展示minor一项：`checks[*].columns_checked`误记为行数，`rows`正确；实现的逐列循环实际全部比较，金额/身份覆盖没有遗漏。单列披露，保留原冻结源与成功证据，不修改收据或重跑。

主比较2020/stress AI减固定20随机的金额差`124,770.91`元，分解为风险项`19,207.86`、单位项`168,461.56`、参与项`-62,898.51`；正贡献合计`951,708.01`与负贡献`-826,937.10`相互抵消。双方入场但不同月的差额`185,115.23`，双方同月仅`2,554.18`。这些是后验坐标和加权路径结果，与已知域等日均source-R为负并不矛盾，也不证明单位项就是纯AI排序alpha。

增量不由affected分区贡献正差驱动：未affected分区`136,963.78`，affected分区`-12,192.87`；仍保留全部未知、stale、open和入场未知，不删它们制造另一条曲线。净差具有强正负抵消及父事件集中：最大正父贡献EC 2024-04-01为`168,059.70`，高于总净差，但不是“删掉该事件后”的可交易反事实。2024/2025 cohort正差与2022/2026 cohort负差说明不均匀；cohort不冒充实际年利润。

独立判断：接受本次会计桥的金额、身份和完整域；因果与稳定排序资格不成立，原138八个CI跨0、原133 unsupported、不加注/不晋级结论均不变。结束新增选参过拟合：否；历史反复择题与事后故事风险仍有。继续价值：完成本会计问题后不再扩展同一历史归因或按unit正项立即重训。下一最有价值行动是将固定模型/控制/风险的后续u时选择、资金初始风险和执行/估值证据前向登记，等真正未见样本检验；若要新alpha研究，须另行收益前冻结新的PIT信息或训练目标及OOS检验，不能按EC、年份、seed或当前贡献救参。

141本阶段已完成；最终decision、LINE/registry由root统一合入，本agent未修改。
