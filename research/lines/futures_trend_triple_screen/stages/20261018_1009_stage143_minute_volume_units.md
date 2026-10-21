# Stage143：EMA限价分钟成交量单位的有界核查

- line_id=`futures_trend_triple_screen`；2026-10-18 10:09 CST；已先读registry，归入既有本线；非重要突破。仅查127 `floor(V)>=q` 的单位，不研究volume信号。
- 范围为正式基础池SHFE/INE/DCE/CZCE/GFEX的真实商品合约、交易期`2020-01-01..2026-10-14`；2019日线仅暖机，不用其分钟V进行本门撮合。金融合约不在范围内。
- Stage140原文件保持封存，SHA仍为`86fbb20d85a3c74d42dc72e99e22fdb08f5863cb9b4d1f52920399e19d851d6c`；本阶段只增本文和`outputs/stage143_minute_volume_units/sources_and_evidence.md`。

## 结论与建议

**有依据将本期分钟V按“单边合约手数、原值不缩放”作为研究撮合假设；没有依据声称五所全部厂商历史API已逐行证明同口径。** 原140提出的单位问题经查有了具体来源与限制，不能拿交易所单边规则直接冒充API全量认证。root已明确采用“2020统一单边制度＋未缩放TQ volume字段→provider报送lot量”的研究推断，GFEX及SDK未明说单边的缺项公开保留；本阶段不签新数据资格，不再扩查或下载。

最小可接受边界：保留原`V=floor(已资格分钟volume)`及冻结q，V有限非负，`V>=q`只排除分钟总量不足的情形；严格穿透一tick与第一次符合分钟仍沿124/126/127。**总分钟量达到q是必要非充分条件**：不证明L价位分配量、queue优先级或本单真实全量成交，未识别的部分成交仍由已经声明的all-or-none研究近似覆盖。不得从该规则宣称实盘可成交量、全局收益下界或真实FOK。

不除二、不乘二、不乘合约吨数/乘数，也不新增参与率、阈值、按交易所/年份择优换算或删bar救参。若未来出现具体厂商倍量或不同单位的反证，应报告并停止相关撮合资格，不能默修；目前有限核查没有发现这种反证。固定悲观反证与成本/路径验证仍需保留，单位核查不授金融readiness。

## 主来源及推断层次

1. [中国期货业协会《单边计量与双边计量》](https://www.cfachina.org/inv/wqbh/rxwd/202302/t20230208_36029.html)是协会官网对实时行情字段的正式说明：成交双方10手匹配按单边计10手；明确2020-01-01起SHFE/DCE/CZCE统计统一改单边。该来源支持市场计量惯例，不是TqSdk数据服务合同。
2. [上海期货交易所署名2019-08-02能源中心细则公告镜像](https://www.bocifco.com/newsinfo.aspx?cid=3&id=15893)明确INE成交量/持仓量改单边自2020-01-01实施；[能源中心现行交易细则的上期所官方页](https://www.shfe.com.cn/regulation/ineregulation/businessmethods/trade/202609/t20260914_833389.html)亦保留成交合约单边数量定义。历史生效日依据前者，不能只用2026现行条款倒推历史。
3. [TqSdk官方API文档](https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html#tqsdk.TqApi.get_kline_serial)和[官方GitHub api.py](https://github.com/shinnytech/tqsdk-python/blob/master/tqsdk/api.py)将`get_kline_serial(...,60)`的volume定义为本K线时间范围成交量；它是分钟bar量，而非当日累计量。官方文档将期货下单volume称为手数；Kline.volume与订单volume是不同对象，不能仅凭同名推导统计口径。
4. 当前在线文档显示3.10.3；本机已冻结3.10.2的`api.py:693`及`objs.py:226..248`有相同Kline.volume期间成交量注释，类型int。已读页面及本机两处未给出历史五所单双转换承诺；因此“2020后API沿交易所单边手数”是有依据的源级推断，不是本轮取得的厂商显式保证。
5. GFEX官网https/http访问均400/timeout；两组查询未取得GFEX专门历史口径条款，不能声称已直接核证GFEX。将GFEX解释为遵循2020后统一单边惯例属于推断，置信度低于前述明确历史通知；不能凭这一缺项编造二倍换算或扩展无界搜证。

## 本地字段链与一个有限实证

- `087._minute_worker`直接订阅真实合约60秒Kline；041引用原012 `BatchCollector`。`012:130`仅逐字段`float(row[key])`，`:137..143`把原七值放入raw DataFrame；`041:280..284`只to_csv。原`VALUES`含volume，不含乘数换算；007原collector同样逐字段float直取。
- 127 `limit_context:116/126`对同名volume校验有限非负后取floor比较q，未按吨数或双边变换。021七值/日线聚合保证值一致，**本身不授单位或queue资格**。
- 仅只读已有008接受证据和007 raw前两行，未新聚合、查DB或运行脚本。`rb2010.SHFE/2020-08-12`原345根分钟sumV=`740132`，与原日线CSV和DB的volume同为`740132`，差0；008独立receipt SHA `aab0b7062ff32e67d4fdf2f3132b00188c5779cf59c1462144f002a7b25ddaa6`。
- 同一raw SHA `0805e7083b24e988469bee78fabc53419d2855e85f92928256a184d9db9480ac`；首分钟volume=`15773`、次分钟=`4776`。这里只保留实际字段样例，不以奇偶、日聚合相等或同一vendor自洽冒充单双口径独立证明；不外推其余合约和日期。

## 收口与反思

- 严格只两组查询，后续仅打开同组来源/已知官方页；查询、源路径/实测SHA和未成功页面记于随附证据。未开展CTP连接、provider、下载、模型、金融、测试、资格签发或子agent。
- 新增/修改/删除策略参数与回测结果均0；期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率均N/A。未改任何旧源、140、LINE、registry或Git。
- 开始/结束新增过拟合：**否**，只核收益前固定V门的数据语义，未看收益择口径；历史选择偏差仍在。
- 开始/结束继续价值：**是，且本次已足够收口**；已区分交易所规范、API字段映射和不可识别的实际成交。沿root已明确的研究推断推进原接合，不把单位调查变成新优化或无限认证；主回测若有增益仍按124固定悲观/成本/生存门。目标active，financial_ready=false、production_qualified=false。
