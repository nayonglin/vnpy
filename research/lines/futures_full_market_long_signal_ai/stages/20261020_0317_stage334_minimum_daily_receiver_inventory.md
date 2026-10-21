# Stage334：后续真实日线接收的最薄入口盘点

- line_id：`futures_full_market_long_signal_ai`
- 记录时间：2026-10-20 03:17（Asia/Shanghai）
- 性质：有限小源码与已存小metadata盘点；非实现、非接收演练、非正式C9/ABC。
- 重要突破：否。没有新增特征、模型、参数或金融结果；0行情请求、0SQL、0fit、0cash、0安装/调度。未读取价格文件、数据库、原大cache、私有配置或凭证。

## 结论先行

有可复用的最近日线传输代码，但本次所见入口中**没有可直接续到2026-10-19及以后、覆盖六所全部真实月份并提供因果完成时钟的ready updater**。最短后续是抽取Stage265的单合约最近日线订阅/等待/超时/脱敏部分，加一次六所真实月份目录刷新和新批次不可覆盖存档；不应重跑Stage266全历史建库器，也不应把旧全合约下载脚本改一个截止日就宣称接收链完成。

这一工作有继续价值：它补的是已经明确缺失的接收与证据接口。它不增加固定纯52相对其他政策的优越性证据，亦不解除既有历史择题、过拟合和非PIT边界。

## 已有证据与可复用部分

先读了registry以及本线317/318/329边界。317已确认纯52小模型/scaler与因果核可复用，无需重训；318要求冻结后才完成的u才可forward；329只是旧98目录与97有源商品的错误强等域导致snapshot失败，不是行情、模型或收益失败。330/331由root另行推进，本阶段不重审或干预。

| 已存入口或小metadata | 本次确认的事实 | 复用判断 |
|---|---|---|
| [Stage265最近日线脚本](/Users/mac/Desktop/fian/research/lines/futures_trend_rollover_shape_same_volume/tools/stage265_download_recent_daily.py:22) | `END=2026-10-16`，仅DCE/CZCE/GFEX；读已存目录；状态为downloaded就永久跳过该symbol。逐合约`get_kline_serial(86400,35)`并等待ready；按固定日期截断，覆盖写固定CSV。 | 最近窗口传输、独立series、超时与脱敏可抽用；当前脚本原样不能继续取得10月19日。既存状态不是增量水位。 |
| [旧全合约日线下载器](/Users/mac/Desktop/fian/examples/portfolio_backtesting/download_tqsdk_all_futures_daily_csv.py:54) | 六所过滤存在，但`expired=True`只选已下市合约；截止2026-04-30；已有非空CSV即跳过；请求较长历史，单次copy前没有该helper自己的ready等待。 | 不能据名称认作“所有当前合约updater”。不适合作为本轮短接收入口。 |
| [SHFE/INE尾部脚本](/Users/mac/Desktop/fian/research/lines/futures_trend_rollover_shape_same_volume/tools/stage265_exchanges_tail.py:15) | 仅校验/补齐预声明的10月8—16日七天、两所文件；默认离线，download只补缺文件。 | 官方文件绑定/校验可参考；不是滚动到新日的六所接收器。 |
| [Stage266清洗器](/Users/mac/Desktop/fian/research/lines/futures_trend_rollover_shape_same_volume/tools/stage266_clean_daily.py:97) | 固定2010—2026-10-16；目标或building DB已存在即拒绝；按全部历史源重建。 | 仅抽`row_issue/canonical_values/resolve_alias`等纯校验与已接受单位规则；不启动Builder、不更新原DB。 |
| [既存catalog](/Users/mac/Desktop/fian/research/lines/futures_trend_rollover_shape_same_volume/outputs/stage265_deep_daily/tq_latest/current_futures_catalog.json) | `TqSdk query_quotes`、`FUTURE/expired=False`，实际查询时刻2026-10-17 18:20:23+08，共870个symbol。 | 这是该时刻目录证据，不是以后目录真值，也不是870个都有完整新日日线的证明。 |
| [清洗小manifest](/Users/mac/Desktop/fian/research/lines/futures_trend_rollover_shape_same_volume/outputs/stage266_clean_daily/dataset_manifest.json) | 已接受历史上界为10月16日；97个有源商品。 | 只提供续接起点和旧身份；本阶段不读取其大DB或重做清洗资格。 |

六所目录应明确请求`ins_class=FUTURE`及当前真实月，不混入连续、主力、指数或组合。后续刷新还应保留前次目录及刚退市合约的差异，避免只取“今日未下市”就漏掉补采区间内刚结束的真实月。这个有限差集是接收完整性处理，不是新策略臂。

## 外部调研、时钟事实与未知

有界查阅两项官方/作者资料：[TqSdk API文档](https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html)、[维护者API源码入口](https://github.com/shinnytech/tqsdk-python/blob/master/tqsdk/api.py)。同时只读了本机已安装API的相关函数；本机版本为3.10.2，网页显示3.10.3，未安装升级、未实例化API、未验证账号权限。

官方接口支持真实期货目录、最近K线与交易日历。`is_serial_ready`表示订阅初始数据就绪；K线`datetime`是开始时间，不能单独证明当日bar最终完成。多symbol对齐K线会受共同有数据时点约束，因此完整月份接收应保存各合约独立series及缺失状态。上述均不构成已经取得新日行情的证明。

| 所需时钟/状态 | 现有证据能给什么 | 不能推导什么、最薄缺项 |
|---|---|---|
| 本地first_seen/received_at | 新批次到达后，可用321实际UTC append时间留痕；原目录有queried_at，下载状态有started/updated_at。 | 旧批次时间不是每根bar当年首次公开时间；不能回填成历史PIT。新版本应保留实际收到的内容与版本，不覆盖旧见证。 |
| u源完成 | 固定END筛掉上界之后的行；ready仅初始series加载完。 | 当前updater没有可核`source_completed_at`或bar-final证据。需要明确日线完成规则及对应来源/版本；不知道就保持completion unknown和observe-only。不能统一臆造六所各品种都在某个墙钟完成。 |
| D交易日 | `get_trading_calendar`可提供北京日期与是否交易日；保存取得时间及版本即可作为候选日历证据。 | 不是逐品种D首个交易时段开盘时间；`has_night`也不足以处理实际夜盘/节假日时刻。不能用下一自然日或午夜冒充D_open。 |
| D开盘前及时性 | 321可在已知真实D_open及完成证据时检验接收、最终seal先后。 | 等到下一根日bar出现才确认u，可能已跨D开盘；此时只能late/gap，不可补写active决定。`get_trading_status`有额外权限门，不因本盘点自动要求购买或扩接该接口。 |

判断：最近窗口API在形态上足以覆盖紧邻10月16日的日期；**当前账号、网络和全部真实月份覆盖未探测，不能承诺10月19日一定全取到**。10月19日已经发生，即使此前没取，后取仍为历史补暖机，不是冻结后的前瞻样本。

## 建议的下一项GO范围与保留缺项

建议root若继续，仅单独授权一个“六所真实月份最近日线批次接收”的小任务：刷新目录并保存真实查询时刻；只取10月16日之后的缺口/有限最近窗口，逐合约保留原返回及缺失、单位与身份状态；以新批次不可覆盖保存并由321追加实际UTC firstseen。复用266纯校验和320 Wilder已接受checkpoint续接，原历史源不重写。新商品没有足够暖机时保持unavailable，不用旧21根窗口重种Wilder，也不为凑齐数据扩大旧历史下载。

保留既有98商品/95family观察母域，包括DCE.S无源母行；同时把未来新目录项的catalog first_seen、unsupported、经济映射/单位/lifecycle未知分开记录。98是既有闭包，不应冒称永远覆盖未来全市场；名称相似不自动授予旧映射、上市时钟或经济参数。

源完成和D_open证据若尚缺，最小GO只到**真实接收＋完整观察＋缺失披露**，不能据此宣称真实paper资金/T0已初始化或决定已及时active。T0及state仍由root另行明确，不在这里新增冻结门。接收代码实现本身也尚未授权；本阶段只给最短复用路径与具体缺项，不安装receiver、jobs，不连接CTP/邮件，不恢复旧策略。

## 记录与反思

- 本次仅新增本stage；脚本、参数、模型与策略均未改。期末权益、收益、DD、Sharpe、滑点、交易次数与胜率：均无新增，不适用。
- 过拟合：开始与结束判断均为“本次不构成新的参数过拟合尝试”，因为仅盘点接收路径，没有读新成绩或搜参数；旧研究的选择偏差仍在，固定纯52不等于已证alpha。
- 继续价值：开始与结束均为“有，但限于上述接收缺口”。有可抽用传输和纯校验，继续全历史重建、救旧solver或重训没有本次必要性。
- 合入：由root决定后续最小接收任务。本stage不修改LINE/registry、根memory/back_log，也不授予前瞻或生产ready资格。

## 日期映射补核（03:19，小源码事实）

265最近日线脚本106—110行的实际映射只是`pd.to_datetime(ns, unit='ns', utc=True).dt.tz_convert('Asia/Shanghai').dt.strftime('%Y-%m-%d')`，即**北京时间自然日期**，没有夜盘→所属交易日转换。266的`tq()`第290行直接取CSV已有`trade_date[:10]`，最后导出为该日期00:00；因此两者是继承一致，不是独立核定交易日。不能由此直接断言已接受旧数据错日，本补核没有读旧bar或重审旧结果。

可复用的已装纯helper为[TqSdk datetime.py:85](/Users/mac/Desktop/fian/.py311/lib/python3.11/site-packages/tqsdk/datetime.py:85)的`_get_trading_day_from_timestamp(int_ns)`，再用同文件58行`_timestamp_nano_to_datetime(...).date().isoformat()`取标签。源码确切规则是北京时间**18:00及以后归次日，周六/日移到周一**，返回该交易日北京时间00:00的ns；输入已是交易日00:00则日期不变，普通周五21:00映周一。它不查询法定假日或逐品种session，不生成完成时钟。`get_kline_serial`本机文档只承诺datetime为K线起点；本次有限源码未证明所有86400返回戳都已规范为交易日00:00，也没有实际bar取样。因此新接收不能无条件复制265的自然日期截断：应保留raw_ns及本地时间，按已声明的源时间戳语义、该helper及已确认源交易日历确定trade_date；不能确定时明确mapping unknown，不按自然日填u。helper及此限制可直接用于下一轮接线说明，不需先读110MB旧源或下载新行情；inactive epoch恢复时的index-gap处理属于另行续接任务，本阶段未实施。
