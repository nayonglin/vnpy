# Stage143：逐真实合约 OI 本地原始来源盘点

- 研究线：`futures_full_market_long_signal_ai`；2026-10-18 23:36 CST；只读盘点，非重要突破。
- 先读 registry 与本线 LINE 末尾，承接142：累计391次研究fit、202次现金回放；现有52槽/Ridge/.25N包停止救参。
- 开始反思：本次不按收益调参；同史择题偏差仍在。继续价值为是，仅用于识别真正新增观测、避免重复失败实验。

## 判断与本线已有使用

**close OI这个原始来源不是本线尚未使用的新信息源。** Stage130当前52槽为26原值及26缺失标记，本身没有OI；26原值是自身价量11、期限价格控制13、成本和止损距离2。但“当前评分器没带OI”不等于“本线没有试过OI”：Stage004已用closeOI作成交量相同的代表合约次序；Stage084—089更已实际比较共同控制与同epoch、完整源日滞后的 `(closeOI(v)−closeOI(w))/V(v)`。

089记载399252完整投影、206012有观察、193240缺失、1826合法零，12fit和8cash；四配对CI跨0、两held名义增量均负，停止固定日级OI/54槽Ridge/NARROW包。其证据属于本线，不借其他研究线旧overlay替代。

**适用边界必须保留：084的决策对象仍是004原代表epoch e。** 它允许取e尚非代表期间的真实历史，但没有对128展开后的所有子月份分别加OI评分，也没有完成“全子月OI排序”的实测。后者是决策域差异，不能写成已失败；同样不能仅凭这点把相同OI来源升格为全新信息，或从当前52槽缺列重新申请已停公式/窗口/分母。本阶段不给全子月OI新实验授权，133原固定包停止决定不变。

尚有两种“字段尚未消费”事实，但均未获得新信息资格：①真实`open_oi`没有被085读取，已有全库767710行缺失；②官方raw中的持仓变化未进入所读normalized CSV。后者可能只是前收OI差，前者也可能与前收近似重复；没有证明其不可由已用观测恢复、连续覆盖与决策前可得，就不能称新alpha通道。

## 已实际读取的小样本

以下路径均位于旧线 `outputs/stage265_deep_daily/`，只读每类首条/首两行，不全表遍历：

|来源|原始字段与样本|
|---|---|
|SHFE `other_exchanges/shfe/raw_tail/kx20261008.json`|`OPENINTEREST,OPENINTERESTCHG,DELIVERYMONTH`；cu2610的OI47325、变化−10876。|
|INE `other_exchanges/ine/raw_tail/kx20261008.json`|同类字段；sc2611的OI27069、变化2090。|
|CFFEX `other_exchanges/cffex_http_month_201004.zip` 的 `20100416_1.csv`|原表“合约代码、持仓量、持仓变化”；IF1005为2702、2702。|
|DCE `dce/official_raw/2016/a.response` 内 `a.csv`|原表“合约、日期、成交量、持仓量”；a1601在20160104为122、7072；没有真实openOI。|
|CZCE `opensource/work_AP_data_oi.raw`|第三方宽表列AP805.CZC等，2017-12-22为21646；不是官方源，单位/时钟尚待逐产品核验。|
|GFEX `tq_latest/GFEX_si2611_daily35.csv`|原TQ字段`open_oi,close_oi`；2026-08-21为305879、304492，起点/终点持仓不同。|

另只读RQ `rqalpha/futures.h5` 的AG2001一个dataset首行及dtype：有`open_interest`，没有`open_oi`；首行为20190116零成交、OI0，恰说明原值存在不能自动成为真实成交日。normalized SHFE/INE/CFFEX有`open_interest,oi_timing,unit_regime,source_member/source_row`；DCE有`close_open_interest`，原量仓明确native unscaled。未将normalized冒称下载原表。

来源收据分别是 `rqalpha/bundle_download_status.json`、`other_exchanges/official_archive_sources_manifest.json`、`official_tail_sources_manifest.json`、`cffex_month_sources_manifest.json`、`dce/official_fullmarket_manifest.json` 和 `czce/work_fullmarket_summary.json`。RQ为公开202610 bundle；SHFE/INE为官方历史包与daily端点；CFFEX为官方月份ZIP；DCE官方URL目录由GitHub `zjp-CN/commodity-exchange-zh` 固定commit辅助发现；CZCE Work来自 `ildhj0116/Work` 的2018快照，不能冒充官方全史。

## 六所可盘点边界与身份

`stage266_clean_daily/dataset_manifest.json` 的既有接受数如下，本次没有重新统计OI非空率：

|交易所|日线/epoch|首日—末日|
|---|---:|---|
|SHFE|535656/2951|2010-01-04—2026-10-16|
|DCE|471418/2935|2010-01-04—2026-10-16|
|CZCE|390570/2408|2010-01-04—2026-10-16|
|CFFEX|67345/692|2010-04-16—2026-10-16|
|INE|62785/396|2018-03-26—2026-10-16|
|GFEX|24682/138|2022-12-22—2026-10-16|

总1552456行、9520 epochs；逐合约入口为该目录 `csv/交易所/PRODUCTYYYYMM.csv`，另有clean_daily.sqlite，本次没有打开SQL。RQ原始10547 datasets及97有观察产品是vendor目录覆盖，不能证明交易所所有上市生命周期。DCE官方交叉层只有2006—2022；CZCE Work仅2015—2018；GFEX此次只看TQ尾样本，不能替代自上市连续官方交叉证据。

exact键应为`EXCHANGE.PRODUCT.YYYYMM`；旧raw各自有另一键式，必须显式映射。实际各读一行 `csv/CZCE/CF201501.csv` 与 `CF202501.csv`：前者2014-01-16来自RQ，后者2024-01-16来自`old_tq:CZCE.CF501`。同名CF501跨十年不能相接；完整YYYYMM、报告日期、metadata生命周期是必要条件，不能仅给三位年月补当前十年。DCE普通合约与L_F/PP_F/V_F也须分开。

## 单位与时点缺项

既有 `unit_contract.json` 将clean量仓统一为单边手：固定RQ四商品所2010—2019乘0.5、2020后乘1；CFFEX全期/GFEX自上市/TQ已校准文件乘1。消费clean不得再除2。官方按明确`unit_regime`，不按年份猜；DCE年度包因缺可靠逐包脚注，只作交叉参考。2294数量争议键与304价格争议键整日隔离，不为OI拼列补源；`open_interest`只是closeOI别名，不能以前收伪造openOI。

SHFE/INE样本raw自带`update_date=20261008 15:31:54/15:31:41`及report_date，收据却是10月17日取回；这只能证明响应自报更新时间，不能证明10月8日首次发布字节或当时无修订。CFFEX归档文件名只给交易日，RQ与Work为事后快照，TQ bar起止时点也不等于历史首发可得时点。缺当日抓取/版本链、修订政策、跨源同口径与许可范围证据；滞后一天不能自动补成严格PIT。

当前证据已足以完成去重，**不建议为closeOI重复做全量可用性扫描**。openOI与reported变化只记为原列差异，尚无独立性/PIT资格，不能据此重开。本阶段新下载、SQL、fit、cash、大库hash均0，仅新增本文，不改LINE/registry。策略参数和回测指标均无新增，权益/收益/DD/Sharpe/滑点/交易次数/胜率为N/A。

结束反思：新增按结果救参为否；把closeOI改名重试会构成过拟合，应停止。继续closeOI旧包价值为否；继续甄别独立观测或执行证据价值为是，完整高质量long目标仍未达成。
