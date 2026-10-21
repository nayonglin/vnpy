# Stage050 缺失机制、事件复用与最小数据需求

- line_id：futures_ai_monthly_pool_generalization；2026-10-20 22:07 CST；只读诊断，非重要收益突破。不改LINE/registry/其他线。
- 输入仅046b的compact状态/首次unknown/时钟字段与048规范roles；040只查同日代表epoch hint；011/014/032只读轻量CSV/manifest。未读cumulative return列，未扫221MB大分钟文件、未下载、未回放或fit。

## 核实结果

19698源行不删，asof竞争成员8398；条件参考值4508，全部3890缺失保留=3657成熟未知+233未成熟。3669有firstday，221无day（181 immature+40 tickgrid error）。

成熟首阻塞C2缺分钟2209、连续session缺1016、初始signedR332、新entry signedR10、holding bar44、tickgrid40、pendingclose3、oldrollclose2、entryanchor1。immature233里37已有C2、7缺session、6 signedR、2 pendingclose，其余181未记录首阻塞。

3669月窗压为1684 product-day-reason事件，复用1/2/3/4月窗的事件数577/272/792/43。C2共2246月窗（2209成熟+37immature）压为920 product-day事件；复用1/2/3/4对应183/176/533/28，737复用事件首阻塞2063月窗。修一事件只可能去掉这些当前首阻塞，不保证后续60日全部known；不是独立样本增加或收益提升。

920个C2事件全部给held_contract_identified=False：040代表epoch只是hint，持仓可能旧约，不能把hint当下载请求/交易合约。精确held需重建各月窗trace，本次没有做。68个product-day与有界库存相交；12自然日命中hint；匹配68条011/52条014/5条继承manifest，032本次交集0。无匹配仅代表这批旧有界库存无证据，不证明全本地不存在；不能移植旧session/执行资格。

## 判断与下一步

成熟缺失率原18 36.99% vs 扩展47.61%；按年约34–63%、按所约36–62%，结构明显，MCAR假设无依据。观测汇总本身不能证明MNAR或MAR；C2未知也依赖未来触及stop/confirm的路径，不能拿known-only代表全域。当前批量定位held、复核已有资料及按first阻塞复用组织数据，比加模型复杂度更有价值；该优先级只看覆盖，未读收益。

最小需求：先精确held/episode/entry-stopR/guard/filltick/会话与pending-roll状态；再对已有68产品日线索核同provider完整分钟和clean OHLC；按重复首阻塞聚合920 C2需求。另把1023缺session月窗、40 tickgrid、348 signedR月窗分开：核日线/历史tick/gap，不能邻约填充、snap有利价、取abs或floorR造标签。233未成熟独立等时钟。完整需求与限制见outputs/stage050_missingness_diagnostic/README.md。

无alpha/模型参数新增修改删除；无金融结果新增修改删除，权益、收益、DD、Sharpe、滑点、交易次数、胜率N/A。fit/金融回放/下载/订单/生产/正式A-C均0，正式A/C仍因身份缺项禁跑。开始/结束新增按收益调参过拟合否；继续价值是，识别覆盖问题尚未解决，未证明模型/收益改善。
