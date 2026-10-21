# Stage651：ESR公开Corn历史来源规范化独立复核通过

- line_id：futures_full_market_long_signal_ai；时间：2026-10-21 12:28，Asia/Shanghai。
- 独立、唯一有界全数值复核；非重要突破，非回测。继承root已取得的649资料，不新增GET、行情、标签、模型、SQL、fit或cash，不调用或导入作者normalizer。
- 开始反思：本步没有按收益调参，否；累计同史多试的择题过拟合风险是且高。真实新数量来源的完整规范检查有价值，源正确本身不等于long收益。
- 当前累计551fit／294完成cash及1旧partial不变；629 false/inconclusive及646关闭K包不变，98/95目标active。

## 接受范围与结果

**只接受Corn全目的地公开历史响应与规范化表的一致性，58,585项检查全部通过，产物实质缺陷C/I/M=0/0/0。** 不签中国目的地、实际历史发布时间、首发vintage、模型/特征join或金融资格。

1. 一次读取raw、gzip规范、commodity metadata、summary及query receipt各1份；原始bytes/SHA均与649 manifest一致。manifest自身先cat一次，RAM精确重建1867B文本的SHA与root宣告相同，未二读。gzip解压后的SHA也一致。未读作者normalize_source.py或重新执行它。
2. 全1951行按原顺序独立解析；六个数量字段11,706次Decimal逐值精确，另11,706个原字段字符串精确；1-based source_row、ISO period_end、unit、numeric_state及publication_clock_state逐行通过。没有pandas浮点或作者函数提供独立证明。
3. **派发中的“13原字段”应纠正为12：1951行全都只有12个原字段，规范17列=12原字段+5派生列。** 不是丢失一列，不修改原件或规范。
4. 1951行对应1919个不同period_end，1990-01-04—2026-10-08，全部周四、源顺序非降；38个marketing-year定义。Standard 1882、MY Ending 37、MY Starting 32全部保留，不将同一period的营销年边界身份压成一行。
5. 完整身份按commodityId/weekEndingDate/myDefinition/mycoTypeName/weekNumber核重为0。年度分布、三类边界、负值、缺失及所有summary数值均独算一致。原netSales负73、nextYearNetSales负43，六数量字段缺失均0，无滤行/补值。
6. commodity metadata实际44项，唯一Corn id10/code401，名称CORN - UNMILLED，内外两层单位Metric Tons。规范metric_tonnes未按千吨缩放；不从SDK旧示例或猜China代码取得身份。
7. summary全部32个键已覆盖：可数值重建的项目独算；scope/revision/clock/净销售语义及零金融声明按输入结构和本次限定逐项检查。有关真实release与修订是保留的限制声明，**不是本复核从1951行推出来的历史实证**。

原字段为：accumulatedExport, commodityId, commodityName, myDefinition, mycoTypeName, netSales, nextYearNetSales, nextYearOutstandingSales, outstandingSales, weekEndingDate, weekNumber, weeklyExport。

## 原来源、时钟及证据边界

query receipt记录实际官方公开端点HTTP200／834460B：
https://apps.fas.usda.gov/esrqs/api/reports/WeeklyHistorialReportData?WeekEndingDate=10%2F16%2F2026&CommodityId=10
它与本次独读raw字节精确绑定。root另证正常公开站JS与路由链，本复核没有再次GET/打开JS，不能冒称独立重验网络链。三个metadata端点401已停止的事实继承root，本次不绕鉴权。

本表是美国Corn向全部目的地的汇总，不是China-specific，没有国家身份字段；未取得各国明细来重建全球和。weekEndingDate是报告期末，不能拿它代替release。普通次周四08:30ET的规则不能消除holiday/shutdown例外；当前数据库值不自动等于当周首发vintage。netSales允许取消、修订、MY转移，不能全叫新签订单。也不对当时数据库页面的可访问性、原条目经济正确性、实际贸易或首发披露真实性做超范围认证。

缺首发字节不构成永久源NO_GO；如root继续，可另行固定保守发布滞后及修订/缺失假设，标明条件历史研究，不伪造strict PIT。651不授权源日到u的join、训练或现金。

## 收据、执行与后续

[验收收据](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage651_esr_source_normalization_review/acceptance_receipt.json)，SHA256 e3cbe8bac82d7e98644b88ac8fa47d224de92065335dafa0f432c025f970ee5b。raw SHA a3175f29bbc4e96a20e029b7f1792609c2e90506efcff9101e36133dbc18ddfa；规范gzip SHA b9ebbc45fa89c2549c30cf092c921d364598464156241977dbfaf9a4d88681f5；plain SHA deb50e92691ac68bbc511e19a59fbefc1d582a29219fb86f87ee11f18b5c4e47；manifest SHA d0665ec86f8d3fe4be42421f13296aee51cf37855477330befb6b5ead55a00d5。其余小输入绑定见收据。

初始REPL包装字符串有一次SyntaxError，发生在任何数据读取之前；只修调用包装，随后RAM载入及58,585项数据检查各一次。另一次functions JS包装语法在向进程发命令前失败，无文件读写；未重做任何数据检查。源、规范和科学对象均未改。两项非数值准备错误留工具轨迹，不写成源/规范故障。

只新增本651 stage及小receipt，不修改LINE/registry/根memory/back_log/原649源/其他线/正式C9/生产/调度/Git。策略及回测参数、结果新增/修改/删除全0；期末权益、收益、DD、Sharpe、滑点、交易次数、胜率全N/A。

结束反思：新增按收益救参否；历史累积择题风险仍高。此次独核已完成，有价值；重复同payload资格工程无价值。新数量观测可进入root另冻的经济对象与发布假设设计，尚无alpha、95family泛化、收益/DD稳定或窄损加注证明；完整目标继续active。
