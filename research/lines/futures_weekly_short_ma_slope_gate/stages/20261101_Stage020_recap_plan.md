# Stage020 2026年度C_R150逐笔离线复盘设计与计划

2026-11-01；line_id=futures_weekly_short_ma_slope_gate。用户已要求为上一轮年度回测生成复盘HTML，并保留先前“本地文件直接打开、不起HTTP服务”要求。既有recap contract已确定UI、周期、联动与来源，本次不重新设计界面。

唯一采用方式：在本研究线新增窄数据适配器，调用既有Stage031安全纯函数loader和Stage038 canonical renderer；不复制HTML/图表实现，不修改其他研究线或固定m0002。当前source bundle唯一为Stage019已封年度独立窗口及其原Stage014_C_20260101_attempt001。

- 全部18个flat-to-flat闭合轮次、36笔成交、净PnL22380=毛25310−滑点2930；不能误用canonical gross充净利润。8盈10亏、无期末残仓。R没有已封统计口径，保持N/A。
- 以真实trading_date定位K线，保留natural execution datetime，严格同物理交割epoch（含CZCE十年别名重用），只读SQLite与physical逐项核验；禁止代理K线、合成填充。
- 默认30日K+日K，保留10日/月/周及合格15分钟、全部均线和共享缩放。日K前300/后50、月K前后10月受真实上市历史/截止日约束，逐笔披露截断及MA不足。
- 已知本地分钟缓存有候选；独立agent逐日/桶核准后才接入。未通过资格的缺日保留缺口，不能把有1m文件说成完整15m；不下载。若有更早合格分钟，为可见MA预热保留隐藏历史，不从窗口边缘重新算造成可避免空值。
- 页面内嵌Plotly、records和已封年度净值PNG，单文件file打开；只加净值/成交事实语义块，不改变canonical candle/axis/zoom实现。
- 输出仅artifacts/stage020_2026_ytd_recap/，含index.html、summary.json、chart_manifest.csv、records.json、来源与测试/浏览器验收。独立agent核来源、净PnL、markers、OHLCV、MA、缺口；根代理用真实浏览器验收筛选/切换/联动。

测试先行：错误/缺失来源拒绝，残余开仓不得丢弃，输出不能覆盖原版或其他线，净损益扣费、空头原始价格涨跌不反向，夜盘真实交易日不误当自然日。随后生成、JS语法/语义检查、浏览器file验收、独审与交付封存。

调研：核对Plotly官方relayout与离线JS说明，判断复用已内嵌get_plotlyjs的canonical renderer即可，无需CDN或HTTP。未调alpha/回放金融，过拟合判断为否；价值在18轮盈利与回撤的逐笔核查。
