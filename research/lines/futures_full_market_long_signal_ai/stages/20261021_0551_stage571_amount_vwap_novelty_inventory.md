# Stage571：成交额/VWAP 是否是结算字段改名，有限本地盘点

- line_id：`futures_full_market_long_signal_ai`；时间：2026-10-21 05:51 CST；day；非重要突破。
- 已先读registry：最新569关闭固定PMI校准包；累计535fit/278完成cash及1旧partial。本阶段只读小schema/ingest源码/既有清单与2个raw header锚点，不重开PMI。
- 开始/结束过拟合判断：本轮无按新收益选参，**否**；长期同史择题偏差仍**是且高**。继续价值分对象：商品通用VWAP重名方案**否**；CFFEX全日成交均价的最小单位取样**有条件是**；直接训练或资金实验**当前否**。

## 决策

**“COMMON没有amount”是真的，“因此又找到全市场新alpha输入”不成立。** COMMON26及其26个缺失旗确无amount/turnover/VWAP，clean266也没有导入这些列；但066早已论证结算含成交价格分布，073实际检验过上一完整日 `(C−S)/N`，未见稳定增量。已核SHFE/INE规则的日结算是全日成交加权，重新从成交额/量恢复VWAP后再算同一偏离，主要是结算字段换名或取整重建，不值得扫全市场或再fit救分。

不能反过来把**所有**成交额VWAP都说成已经实测失败。**CFFEX已核日结算使用末小时基准，成交额可能给全日均价，两者定义不同。** 它是金融8个family的有限新增时段观测潜力，尚不是全98/95新字段已合格，也不是可直接晋级候选。若root认为值得，至多先做固定少量真实期货的单位、统计边数、历史乘数和同epoch映射核验，不应马上以全市场策略名义金融回测。

## 本地已见事实

1. `tools/stage071_settlement_narrow_fit.py` 的COMMON26为r1/r5/r20、body/range/close-location/gap、compression、量比、breakout、ATR%、normalizer、同行期限摘要与成本/止损距离；原130 COMMON52只加其缺失旗。无settlement/amount/turnover/VWAP。没有读取COMMON矩阵或重新构特征。
2. `stage265_exchanges_normalize.py` 将官方“成交金额”或“成交金额(万元)”原样归一为 `turnover`，与volume/settle同源保留，含source_member/sheet/row及完整contract_yyyymm/epoch。它没有把成交金额单位、单双边和乘数统一为可直接用的VWAP。
3. `stage266_clean_daily.py` 的RQ导入与官方导入明确只送OHLC/volume/closeOI/openOI到clean DB，丢弃total_turnover/turnover。**丢列不等于源不存在**；本阶段不读DB或全H5重建。
4. 066先前已实际核三个H5确定键AG2001/IF2612/T2612，schema有 `total_turnover`，六条与官方amount×10000一致；但它只认证这些锚点，不是全10547键、全历史单位证明。本阶段没有再读H5。066中的DCE官方规范schema没有amount，也说明源格式不统一。
5. 066/073边界不能省略：settlement实际包是严格v=u前一完整source日的同epoch `(C(v)−S(v))/N(v)`；合法零与missing分开，结算规则族分全天/末小时/未知，不是统一全天VWAP。073主窄损stress比COMMON仅微小约0.048893pp，多数窄损账户fill完全相同，增量CI跨0；这是该固定包失败，不是所有新价格分布信息的数学否定。

## 只读两份既有原件header锚点

每个zip只打开一个已知日CSV member，仅读header与首条数据，共4行；未遍历所有member/整月行、未全hash/CRC全扫，没有计算覆盖率或行情序列。精确路径和继承SHA在小inventory，raw SHA没有本轮重算。

| 原件/member | 当前小读 | 可以确认 / 不能确认 |
| --- | --- | --- |
| `.../other_exchanges/cffex_http_month_201004.zip` / `20100416_1.csv` | header含合约代码、成交量、成交金额、今收盘/今结算/前结算等；首行IF1005：V48988、金额5053880.532、C3415.6、S3431.2，O/H/L=3450/3488/3413.2 | 确认真实期货原字段存在、同一日同合约。header没有打印金额“万元”或单双边，不能仅凭数值认证全史单位。 |
| `.../other_exchanges/cffex_http_month_202609.zip` / `20260901_1.csv` | header仍有成交金额；首行HO2609-C-2500期权 | 只作近期schema锚点，不把期权V或金额当期货VWAP；不推断所有期货/月份均非空。 |

**只作条件算例**：若2010Apr16金额单位万元、V和金额同一单边口径、IF1005当时每点每手300元，则 `VWAP=5053880.532×10000/(48988×300)=3438.856136…`，与日结算3431.2相差7.656136点。它支持“CFFEX全日与末小时可能不是同一个观测”，不是收益/alpha证据；三个单位/历史乘数假设仍需主来源绑定。不能用算出来恰在OHLC内反向证明单位一定正确。

## 单位、统计边数和身份风险

- `cffex_month_sources_manifest.json` 既有声明为official single-side保留原值，normalizer对CFFEX无注释也固定该regime。它是已有资料/代码约定；本轮原header没有独立打印边数，不能把约定升为全史认证。
- SHFE/INE旧资料有双边、单边regime，clean阶段会按已接受factor转换volume/OI。**不能把已减半的clean volume与未同比例处理的原amount相除**。若原amount和V同边数，公共因子可抵消；若只处理V则会直接把均价翻倍。volume/OI单位审通过并不自动认证turnover边数。
- 恢复价格必须使用同epoch同日原amount、原volume与相应历史合约乘数。IF/IH、IC/IM及国债报价面值不是一个统一乘数，当前静态经济快照不能替代每个历史合同身份。普通/F不得短码串约或用主力替代。
- 原normalizer已保留完整`contract_yyyymm/contract_epoch_id/source locator`；067已有metadata_index从挂牌身份/maturity解析真实年月的复用方法，可以避免3位/4位短码歧义。**接口能映射不等于每条原行情已与当前accepted close绑定**，本阶段没有重新做该投影。
- 全日amount当日何时可得仍须单独处理，不能用S(u)或VWA(u)回填已封存决策。066的一完整日滞后仅为旧固定实验；本次未授权换lag或把一日滞后失败直接改同日救分。

## 调研与判断依据

本任务明确限定不新增网络，故复用066已经实际核过的一手资料与GitHub维护者源码，并读本机实现，不假称本轮重新查网：

- [SHFE2020结算细则](https://www.shfe.com.cn/upload/20200930/1601455533699.pdf)、[INE结算细则入口](https://www.shfe.com.cn/regulation/ineregulation/businessmethods/settlement/202606/t20260622_832188.html)提供有成交/无成交及异常回退的区别。我的判断：全天商品VWAP不构成足以重开073的独立经济对象；无成交/特殊结算更不能用成交额硬造价格。
- [CFFEX2020结算细则](https://www.cffex.com.cn/u/cms/www/202003/27161736r3ck.pdf)、[IF交易细则](https://www.cffex.com.cn/u/cms/www/202003/27165505w3j5.pdf)支持末小时与交割对象区别；不代表已认证每个历史版本。判断：CFFEX全日成交成本与末小时重新定价可能含不同信息，但多空含义可持续也可回归，不能预设做多符号。
- [RQAlpha维护者data_source.py](https://github.com/ricequant/rqalpha/blob/master/rqalpha/data/base_data_source/data_source.py)与本机ingest共同支持字段接口独立，**没有本策略盈利证明**。不安装、clone或调用全量接口。

没有再列宏观大全。原CFFEX zip还保留期权列，但近期header连隐含波动率列也有变化；不能借“原件里有期权”直接声称已有稳定全史IV/skew训练集，本阶段不转这条线。

## 后继与指标

建议root关闭“通用商品VWAP重测结算”提议；若继续CFFEX部分，先冻极小、非金融的同合约双时段观测检查，证实金额单位/同边/历史M及全日与末小时真实差别，再决定研究价值。不可按现有赢家选合约或扩大到同名量价公式/lag/grid。后续即使只部分family有新输入，仍必须保留全98/95母域，缺输入精确A fallback，不把研究目标改成只做CFFEX。

新增/修改/删除策略参数与回测结果均0；新fit/cash/GET/SQL/H5read均0，累计535fit/278完成cash及1旧partial保持。期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率全 **N/A**。

产物为本唯一stage和 `outputs/stage571_amount_vwap_inventory/inventory.json`（11775B，SHA256 `1b3aaa64bf14c9776f99bf9cc4873d0a48a006ea7e2d9fb8559d59f6c25aa2be`）。不改LINE/registry、其他研究线、正式/CTP/生产、Git或scheduler。完整目标仍未完成。

05:53补录root所需ZIP-entry元数据：20100416_1.csv为650B，20260901_1.csv为56068B，仅getinfo读取，不再次解压正文；inventory补入两条原始首行与金额单位/单双边/乘数spec的明确证据限制。仍只2个raw锚点、4行读取。

## 05:57 CST 追加：优先现成 H5 同源金额，不进行199月新下载

root当前目录实核只有201004、202609、202610三份 `cffex_http_month_*.zip`（606278B）；这不是连续官方原月ZIP历史。旧月下载manifest路径/条目不能自动证明文件都在本机。571不建议199月新网络采集，优先已有vendor H5同源字段的一次有界恢复。

**066证据精度必须分清**：只有 `stages/20261018_1600_stage066_next_information_proposal.md:39—53` 中的六行人工小读记录，没有本阶段发现或声称存在独立066六桥行JSON/脚本。它明确说同symbol、完整交割年月和日期的OHLC、**volume**、OI、settlement、prev_settlement逐值一致，total_turnover为官方turnover×10000；但没有逐条列出V/金额原数。它能证明曾核V精确身份，不能当成新金额源的全CFFEX单位证书。

H5精确路径：`/Users/mac/Desktop/fian/research/lines/futures_trend_rollover_shape_same_volume/outputs/stage265_deep_daily/rqalpha/futures.h5`；067协议继承binding为377901136B、SHA `d288f6e4c7468981e95fbb0c1c9e2e1e66bfb99f5ba607843728aec535c8bfee`，不是本轮全hash。066三个已读键为AG2001/IF2612/T2612（shape244/113/137），其中CFFEX的IF2612/T2612均读2026Sep29/30。schema含datetime(i8)和OHLC/volume/total_turnover/settlement等f8；不保证每个键都如此，也没有本轮打开H5。

可复用的exact-key与接口：

- `.../rqalpha/full_market_contract_inventory.csv` 已有完整contract_id、source_symbol、exchange/product、listed/maturity/dataset_exists；`full_market_inventory_summary.json`已载CFFEX8产品692真实合约/692有dataset、68736raw、67507正成交OHLC、1229无成交。该数是旧inventory，不冒充当前H5新census。
- `.../rqalpha/futures_metadata.json`为7,112,153B、继承SHA `7feb3e6a98b9f6c054b329fb74a2044be2700ae83f7f11c8de07632cd9f2ae89`。本轮仅为定位读取该metadata JSON，没有行情或H5读取；其中IF1005明确上市2010Apr16/到期2010May21/M300，IF2612到期2026Dec18/M300，T2612到期2026Dec11/M10000。它们是逐合同vendor metadata证据，不代替root正在核的官方乘数/金额口径。
- `tools/stage067_settlement_source_projection.py:195—222` 的 `metadata_index` 用maturity完整年/月和order_book_id排除连续/未解短码；`:462—546` 的 `SourceReader._h5` 只开一次h5py.File，按明确请求的exact key分组、验证唯一日期/原locator、同一structured record读取OHLC/V/S，before/after stat并继承已核H5 SHA，不hash整H5。这个读取模式可以复用，**旧返回字典/settlement_projection并没有amount列**。

判断：在root冻结源范围后，可用现成CFFEX真实键白名单单次H5读取原同row `total_turnover + volume + OHLC + settlement`，以原记录元数据M恢复VWAP并保留字段/身份/缺失状态；不扫描其余商品键、不新下载199个月、不拼其他月主力。amount的CNY口径、统计边数、与accepted参考价可比性仍是**新列恢复的本次核验对象**，不能借066结算合格mask自动签amount合格。全98/95母域保持，其余90产品ID与任意缺输入保留精确A fallback，研究没有改成只交易8品种。

本追加0H5/GET/SQL/fit/cash；不实施批量。source inventory新增h5_reuse_followup小节保留上述路径、三个metadata样本、066证据限制和root三ZIP事实；阶段归属、财务N/A与累计计数不变。

## 05:58 CST root最终裁决：本方向金融 NO_GO，停止载体研究

572补充排重后，root明确采纳 **NO_GO**：066:72已排除turnover/VWAP，:97已在fixed包失败后的停止条件中明确不加turnover救分；而CFFEX结算窗不同与H5成交额当时就已知。因此本轮的字段可恢复性、有限算例和“全日vs末小时定义不同”不能充当新经济机制或允许重开实验证据。

本stage前文CFFEX最小取样/单次H5恢复只是当时条件建议，**现已被root最终裁决关闭，不是后继授权**。停止新增H5/ZIP读取、199月下载、实现、训练/资金回测；不以换source、lag、缩到8品种或换feature名字绕过旧停止条件。没有再读载体或执行批量。

保留真实header、metadata、3ZIP事实、H5路径与旧68736行inventory等技术定位，但这些没有被本轮新H5验证，不得包装成已补齐/已新验源。此NO_GO是同题排重与研究纪律，不虚称CFFEX全日VWAP在所有模型上都已被实测无效。全98/95原目标仍active且未完成，金融计数与N/A指标不变；继续这一载体方向价值为否，后继交root选择独立新机制。
