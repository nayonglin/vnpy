# Stage041：最小现金字段的有限来源查验与直接实施映射

- line_id：`futures_full_market_long_signal_ai`；记录时间：2026-10-18 13:22 CST；工作区：`/Users/mac/Desktop/fian`，分支沿用`codex/ai-training-data-expansion`。
- 性质：0 fit、0金融回放的只读元数据查验，非策略候选、非正式A/B、非生产资格。重要突破：否；但现有资料足以支持带明确假设的首次研究现金回放，不必再停在泛readiness审计。
- 仅新增本stage、`outputs/stage041_minimum_cash_economics_sources/economic_projection.json`及小`read_receipt.json`；不修改038、040、LINE、registry或其他既有资产。不读035/037新成绩，不扫描SQL、行情CSV或全市场H5记录，不下载行情、不重hash大库。

## 结论与038边界的澄清

**可以直接开始研究级现金账户回放。** Stage266 clean schema缺现金字段，不等于本机没有字段。RQAlpha现有小metadata覆盖98代码，能对9520 clean epoch中的9502个提供精确合约身份/乘数；它们均可按官方开源lookup映射tick、margin及费用字段。仅18个2027新尾合约缺精确instruments记录，应逐项保留来源假设，不能把现在的product default包装成2010历史。98中DCE.S在目标区间没有clean行情，缺费用不应造出可交易样本。

038关于精确历史结算、broker附加、排队和权限的缺项，约束真实执行及精确历史声称；**不应升级为所有研究现金账本的共同前置门**。本轮按root采纳的040固定本金/风险/成本/保证金场景，统一close研究mark即可。它能检验跨日参考政策的经济量级和账户约束，不能证明真实历史券商权益、成交可行性或实盘资格。此澄清不改038冻结字节，亦不把旧DAY负结果外推多日右尾或全市场AI。

## 原始资料与调研判断

实际读了Stage265导出的`rqalpha/futures_metadata.json`、`future_info.json`与下载状态，Stage266的`csv_inventory.json`（仅epoch身份表，不读其指向价格）、现有TqSdk产品元数据CSV和`qmt_universe.py`规格定义；还读了Stage265原`contract_id`函数。没有安装RQAlpha或运行其引擎，本机对应site-packages源码路径不存在。来源绑定见receipt，行情H5/数据库SHA仅继承既有下载记录，未重新计算。

外部只读查验原作者主仓库：[instrument.py](https://raw.githubusercontent.com/ricequant/rqalpha/master/rqalpha/model/instrument.py)、[storages.py](https://raw.githubusercontent.com/ricequant/rqalpha/master/rqalpha/data/base_data_source/storages.py)、[data_source.py](https://raw.githubusercontent.com/ricequant/rqalpha/master/rqalpha/data/base_data_source/data_source.py)、[position_model.py](https://github.com/ricequant/rqalpha/blob/master/rqalpha/mod/rqalpha_mod_sys_accounts/position_model.py)，以及[RQAlpha类型文档](https://www.ricequant.com/doc/rqalpha-plus/api/types)。`contract_multiplier`来自instrument；tick由future-info getter取得；开源`FutureInfoStore`先查`order_book_id`，再查`underlying_symbol`；静态store没有逐日生效版本，`get_futures_trading_parameters(instrument, dt)`的这条base实现不因dt改变lookup。开源position按乘数后的市值计算margin，并区分settlement/close标记。

判断：复用其字段语义、合约优先/产品fallback关系是合适的；不能把有dt参数、合同到期日或2026快照误当逐日历史费用/保证金资格。上游缺乘数时的默认1也不能沿用到本研究。现有字段足以建立可解释研究情景，继续寻找全部历史公告不是本次回放前置。

## 实际元数据覆盖（仅小metadata计数）

| 来源 | 实际记录/字段 | 本次判断 |
| --- | --- | --- |
| Stage265 `futures_metadata.json` | 7,112,153字节，11,355 records；10,862个可按原函数归一的真实epoch/98代码，epoch重复0 | `exchange`、`underlying_symbol`、`order_book_id`、listed/maturity/delisted、`contract_multiplier`、`round_lot`、`margin_rate`；不含tick |
| Stage265 `future_info.json` | 1,759,224字节，7,574 unique keys，0重复；7,480 exact contract、94 product defaults；by_volume 4,275、by_money 3,299 | tick_size、margin_rate、open/close/close_today commission及type；静态快照，不是broker逐日表 |
| Stage266 `csv_inventory.json` | 2,014,579字节，9,520 clean epoch身份 | 仅作为这次经济映射分母；不新验价格覆盖或行情质量 |
| TqSdk产品元数据CSV | 86行/86产品，全是product_cont；2026-06-30抓取 | 86均有price_tick/volume_multiple，margin_ratio/commission非空均0；仅当前规格交叉参考 |
| `qmt_universe.py` | 18个显式ProductSpec，且旧RATES为0 | 不是98代码或历史规格，不得作为全市场默认经济表 |

精确join结果：**9502/9520**有RQ真实epoch metadata；9502均有有限正数乘数、round_lot和metadata margin，均映射到有限正数tick/margin及可解析的非负费用。future_info来源为**7146 exact、2356 product fallback**。2164个epoch的metadata margin与future_info margin差异大于1e−12（二进制直接不等为2168，另4个仅浮点尾数差）；不能静默挑较小者。DCE.S有25条历史instrument metadata、乘数10/margin0.05，但无future_info且本目标clean epoch为0；本线仍保留该产品目录，不虚构成交。

TqSdk相对98代码缺12：`CZCE.ER/ME/RO/TC/WS/WT`、`DCE.L_F/PP_F/S/V_F`、`GFEX.PD/PT`。因此当前TQ连续产品规格既不替代RQ精确epoch，也不用于证明退市品种历史费率。

## 可直接实施的身份与字段映射

1. 从9520个accepted epoch join RQ原`contract_id`，合约正则为`([A-Z]+)([0-9]{4})(F?)`，YY完整年用maturity年邻域解析，**标称月份来自合约代码，不取maturity月份**；`underlying_symbol`必须与普通/F后缀一致，exchange一致。9502精确join无重复，不使用连续主力代码。
2. 每epoch保存`order_book_id/exchange/underlying_symbol/contract_multiplier/round_lot/listed_date/maturity_date/de_listed_date`及原来源SHA。乘数直接取该epoch，不用当前产品统一覆盖。研究币种统一CNY为本次国内期货现金模型假设；metadata无独立currency字段，不能声称已逐合同验证币种。
3. tick与future-info margin/fee采用exact order_book_id优先、underlying_symbol fallback，逐行保存`exact_contract`/`product_default_snapshot`。vendor rate取两份已知正margin的max，再应用040的base/stress floor。缺项不能默认乘数1或手续费0。round_lot为1并不证明任意账户都具有开仓权限。
4. 普通与_F仍是不同经济表达，保留自身真实乘数/日期/tick，family只控制重复风险。`L2703F/PP2703F/V2703F`均有完整实际metadata，**名义2703但maturity/delisted为2027-02-26**；所以交割年月不是最后交易日。持仓退场必须同时遵守冻结的研究边界及已知maturity/delisted（更早者），不能用未来最后一根bar推断。
5. 来源是2026-10 bundle中保存的合约规格快照，目标历史覆盖不得解释为2010当时可见元数据。它可以用于离线经济点值重建；费用/margin等随日变化未被此表证明。snapshot time与assumed applicability interval须分列。

### 不是账户凭证的真实字段样例

| epoch / future-info来源 | 乘数 / metadata margin | tick / info margin | vendor费用字段（open,close,close_today） |
| --- | --- | --- | --- |
| CFFEX.IF.201506 / product IF | 300 / 0.10 | 0.2 / 0.12 | by_money：0.0000253,0.0000253,0.000253 |
| CFFEX.TL.202409 / exact TL2409 | 10000 / 0.05 | 0.01 / 0.05 | by_volume：3,3,0 CNY/lot |
| CFFEX.TS.202409 / exact TS2409 | 20000 / 0.01 | 0.002 / 0.01 | by_volume：3,3,0 CNY/lot |
| SHFE.AL.202105 / exact AL2105 | 5 / 0.20 | 5 / 0.20 | by_volume：3,3,0 CNY/lot |
| SHFE.RU.201301 / product RU | 10 / 0.05 | 5 / 0.11 | by_volume：3,3,0 CNY/lot |

vendor费用字段只是资料可用性的证据；本轮040采用固定费用情景，**不在本轮按这些费率再开第三条账本**。

### 必须保留的历史乘数版本

| 产品 | clean epoch中实际观察到的乘数版本 |
| --- | --- |
| SHFE.PB | 25：201109..201308共24；5：201309..202709共169 |
| SHFE.RU | 5：201001..201207共26；10：201208..202709共152 |
| SHFE.FU | 50：201202..201805共68；10：201003..202709共126 |
| DCE.FB | 500：201404..201911共53；10：201912..202709共92 |

范围是该数值在现有clean epoch中的min/max，不是已认证的公告生效区间，FU两个范围重叠不能擅自压成一次日期切换。tick也有合约版本，例如TS从所映射旧合约0.005到新合约0.002、LC部分2024合约50与2025起合约20；这仍是vendor合约字段，不证明合约存续期间逐日版本。

## 精确缺项18个：本轮固定unresolved

只有下列新尾部epoch缺RQ instruments。它们超出该bundle已覆盖的合约尾部，不能称2010历史缺口：

```
DCE.L_F.202704   DCE.PP_F.202704  DCE.V_F.202704
INE.LU.202710    INE.NR.202710    INE.SC.202710
SHFE.AG.202710   SHFE.AL.202710   SHFE.AO.202710
SHFE.AU.202701   SHFE.BU.202710   SHFE.CU.202710
SHFE.FU.202710   SHFE.HC.202710   SHFE.NI.202710
SHFE.RB.202710   SHFE.RU.202710   SHFE.SS.202710
```

root最终决定：**这18个本轮全部固定unresolved，禁止现金成交，不在看到意向后临时启用fallback。** 投影主字段乘数/round_lot/tick/vendor margin均null，potential signal仍保留，若无意向自然不影响账本，若有则记录精确经济资格拒绝，不删除观察母体。

只作以后补数线索的`fallback_candidate`遵循：同exchange、同完整underlying_symbol（保留_F），nominal month严格早于本epoch的最近已知合约；记录exact donor，但status固定`future_data_lead_only_disabled_for_current_replay`。15个普通合约另有product future_info default；3个_F donor分别L2703F/PP2703F/V2703F，三者乘数5、round_lot1、margin0.10、tick1，vendor费用均by_volume每边1。此线索**不是本轮启用的经济合同**，不改9502行精确乘数，不增加结果后的选择权。

缺失18个的listed/maturity/delisted**不复制邻约日期**，投影保持null；不新增开仓，不通过期限或规格猜测解除本轮unresolved。本次仅确认邻近规格线索，不证明_F真实结算及所有账户权限；9502精确epoch可按固定研究假设记账，实盘资格保持false。

## 唯一机器加载入口

`outputs/stage041_minimum_cash_economics_sources/economic_projection.json`已生成，schema=`stage041_epoch_economics_projection_v1`；不含OHLC或价格值。直接加载：

```python
import json
from pathlib import Path
projection = json.loads(Path("research/lines/futures_full_market_long_signal_ai/outputs/stage041_minimum_cash_economics_sources/economic_projection.json").read_text())
spec = projection["instruments"][contract_epoch_id]
eligible = spec["economics_status"] == "exact_epoch_metadata_snapshot"
# 本轮eligible为False时保留意向和拒绝，不读取fallback_candidate成交。
```

9520键和原clean inventory一一对应；经济字段为`contract_multiplier`、`round_lot`、`tick_size`、`instrument_margin_rate`、`future_info_margin_rate`、`vendor_margin_rate`（两已知值max）；来源为`order_book_id`、`future_info_key`、`future_info_scope`。`exact_contract`仅指vendor记录键精确，不代表逐日历史PIT资格。

期限字段为`listed_date`、`maturity_date`、`de_listed_date`、`nominal_month_first_date`；9502行的`known_lifecycle_exit_boundary=min(nominal_month_first_date, known maturity_date, known de_listed_date)`。这是日期边界，engine按source calendar安排边界前退出，不在该日期再开仓；不把boundary本身当必然有bar。`lifecycle_source`与`historical_broker_specification_qualified=false`固定保留，CNY有`fixed_domestic_research_assumption`来源。原函数可复用`research/lines/futures_trend_rollover_shape_same_volume/tools/stage265_rqalpha_inventory.py::contract_id`，源码SHA随projection绑定；本次不修改该函数。

## 本轮唯一成本/保证金情景（沿root已采纳040，不新增调参）

- 初始CNY1,000,000；单family初始风险0.25%、总初始风险2%、margin准入25%，u收盘共同缩放后floor，D只减/取消、不重分配其他候选资金。具体现金规则沿040，非本阶段重新设计。
- `vendor_rate=max(正metadata margin,正future_info margin)`；base=`max(vendor_rate,0.20)`，stress=`max(vendor_rate,0.40)`。未知率分别用0.20/0.40并标假设。不是历史实际率，不保证覆盖全部交易所/券商压力。
- base每手每边手续费=`max(CNY2,abs(fill_price)*multiplier*0.0001)`；不利滑点=`max(1*tick,abs(reference_price)*0.0001)`。stress手续费=`max(CNY6,notional*0.0003)`；滑点=`max(3*tick,abs(reference_price)*0.0003)`。tick确实缺失时只用预声明bps，标`untickized_research_fill`，不堵现金回放。
- **统一用accepted同epoch close作研究daily mark**；不混用“部分settlement、部分close”改变本轮账户。费用真实扣现金，margin冻结而非当亏损，PnL不重复累计。停止净值不足/强减仓/缺价stale mark及延迟退出按040冻结规则。
- 这两个是预声明经济情景，均报告，不能挑胜者；不是可执行成交证明、历史真实费用或普遍最坏上界。原价格政策55/20/2N、无PT、无任意最大持仓日数、不加仓、不训练均不改。

原RQ futures.h5只读header有限抽查了AL2105（243 rows）与IF1506（166 rows），dtype均有`settlement/prev_settlement/limit_up/limit_down`，L2601F这个键不存在。**未读记录、未扫9520键、未核字段数值覆盖**，不能将两例外推全市场。若后续结果确实对variation margin/限价敏感，可只join实际持仓epoch×date的原字段；不需要先另做全市场数据下载或大历史公告工程。

## 直接下一行动与停止边界

root下一协议冻结上述字段优先级、18个固定unresolved及040全部数值，就可一次共享价格状态机和base/stress现金回放。root指定2010全期、2020全期及2020—2026各年独立冷启动，共9窗口×2情景=18账本；它们应在一次accepted源读取内产生，不作为选参网格。映射表逐epoch带source-kind/假设区间，fills/positions/cash/margin/equity带单位及费用凭据；结束由独立agent核现金恒等式和全部结果。本次仅落地经济投影，不实现该引擎、不执行其中任何账本。

如遇乘数非正/身份歧义/找不到同underlying donor，保留精确epoch错误、不得默认1或借普通_F互换；只在该表达上保留未知，不回退旧19池。若未决敞口能改变收益/DD方向，报告条件性及压力，不声称完整目标通过。生产资格、逐日broker收费/保证金、涨跌停队列以及盘中强平时刻仍不具备；它们不再充当这次研究场景回放的无限前置。**不新增策略指标、不扫描成本/本金/窗口、不用新经济标签重训024/035救参。**

## 工作量与反思

新增策略实现/SQL/模型fit/金融回放/行情下载/订单/CTP均0；只读小metadata与相关源码并导出一个经济投影，H5仅两个现存键的header及一个缺键探查，大H5/数据库未重hash。投影生成前两次在统计断言处退出，未写投影/未读行情；原因是直接浮点不等2168与原容差差异2164的统计口径不一致，最终同时保留两计数，不改变任何原经济值或行情/政策。第三次投影导出exit0，0.137秒。外部网页仅资料调研。`financial_ready`和`production_qualified`均false；`research_cash_scenario_can_proceed_after_protocol_freeze`为true，不等于策略引擎已实现。

期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率全部N/A。新增参数只有建议已被root采纳的040场景映射，无正式参数/回测成绩修改删除。本次无金融结果，不触发结果独审；下一回放必须独立复审。

开始/结束新增按结果救参过拟合：否，本阶段未读取新金融结果、未选优，保留固定两成本情景和真实乘数版本；历史策略选择风险仍存在。开始/结束继续价值：是，已有资料解决具体现金单位问题，应直接走一次经济参考回放；继续扩大泛资格盘点的边际价值低。完整AI识别、极窄损后加注、更高收益低回撤目标均未完成，goal继续active。
