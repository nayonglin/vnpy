# Stage003 双向MA斜率门实际拦截候选：canonical复盘HTML

- 记录时间：2026-10-29 21:11 Asia/Shanghai；line_id=futures_weekly_short_ma_slope_gate；day。
- 是否重要突破：否，仅展示已冻结数据，非新策略/绩效证据。
- 源：Stage002 C `weekly_symmetric_ma_slope_gate_v1`、`outputs/stage002_C_attempt001`，最终源码HEAD `4be2e9389`；run preflight来源HEAD `865c9a8c22301755e998cae562d2f9718f36e5ec`，两者是生成时与最终交付源码身份，不混称同一提交。
- Stage002 delivery的3141文件绑定在生成前后全部重验通过；原trades/daily/metrics/preflight/配置与比较summary冻结不变。
- 没有金融回放、行情下载、CTP/订单或生产访问；没有修改Stage001/002、LINE、其他研究线、根registry/总账。

## 唯一选样与语义

- 只选Stage002 C真实路径门控记录`applied_block=True`且`selected_volume_before>0`、`selected_volume_after=0`。
- 共35个唯一`signal_date+vt_symbol+direction+signal`候选：多头20（14个long_case1a、6个long_case2），空头15（short_case1a）。原选量已经0、门控未实际作用的记录全部排除。
- 这35个是被拦候选，没有在新C成交；页面和最终records使用signal_date/signal_close/signal_x、状态“被拦候选，未成交”，不伪造开平仓端点、持仓区间或交易损益。
- 新C真实成交量、已实现PnL、R、lot_count和标的交易区间涨跌均null/N/A。`selected_volume_before`只标作过滤前计划手数。
- marker位于信号日真实同物理合约daily.close；红叉/红竖线只是信号，不是成交价格。

## 复用canonical与数据

- 按`skills/futures-recap-html/SKILL.md`及`references/recap-contract.md`，调用canonical `stage038_c9_15w_big_winner_multiscale_html.py`的原始纯函数，未复制蜡烛、MA聚合、坐标、分桶、axes或缩放算法。
- 使用既有Stage031 adapter的AST纯函数loader与exact_epoch_bars；无策略/Tq模块导入。
- 本线`stage003_blocked_recap.py`仅做冻结事件adapter、精确数据I/O及窄语义UI替换；Plotly.react hook删假成交点/持仓矩形并替换候选指标/标签，保留canonical多周期与linked zoom。
- 数据只来自本线独立原19快照`outputs/data_stage001_20261029/data_approved`，按信号日physical epoch限定同名合约；SQLite与physical OHLCV逐字段核对，零代理、零跨十年拼接、零填充。
- 默认30日K+日K；可选10日/月/周；15m无冻结缓存，明确不可用，未补下载。
- 日K按信号前300/后50实际产品交易日视窗；月K前后各10月。35个均受真实合约上市前历史不足影响，13个不足信号后50真实日；不制造上市前或到期后K线。
- 图表自然周MA只参考，与策略跳缺周后的接受观察周不同。每个候选另外叠加两点“策略观察周MA5/MA10”，与实际前/本接受周日期对齐；指标和展开证据展示11个源周收盘、前/本MA5/10和delta，可复算OR方向门。
- 全部周期MA只用同epoch真实历史预热；不足处保持null。各候选各周期各MA预热null计数和精确历史边界写入records及chart_manifest，不掩盖自然月/10/30日MA40不足。

## 上一版本实际开仓核对

- 多头20个对Stage001 C（只空头门）；空头15个对Stage001 A（原始无门）。
- 先精确匹配四键候选且entry_context=flat_entry，再通过execution_anchor_requests的signal_date/contract/open及order_id关联真实trades的direction/open。
- 34个匹配旧路径真实开仓：多头19、空头15。`B001 ru2009.SHFE 2020-07-10 long_case2`在旧路径已有同键候选但本就未开。
- 旧路径实际成交日期/量/trade_id/价格单独列为baseline_actual；不把这些叫新C被拦交易的实际成交，不计算或虚构旧路径最终PnL，不据此推断35笔固定反事实。

## 产物与验证

- 输出：`outputs/stage003_blocked_recap/index.html`。
- 同目录：summary.json、chart_manifest.csv、records.json、exact_epoch_coverage.csv、previous_version_actual_open_matches.csv、source_hashes.json、delivery_manifest.json。
- 8项语义测试RED→GREEN：正选量实际拦截与0排除、冻结35/20/15计数、无假成交/持仓/PnL、旧版四键+actual fill、计划未成交分离、输出隔离、epoch拒绝、哈希错误拒绝。
- 初次构建尾段因shell无node失败，未修改源；改用Codex捆绑Node并恢复未完成的展示构建。3段嵌入JS全部node --check通过，未安装依赖；失败build.log保留。
- 新manifest绑定10个展示产物，所有直接source hash和原3141源绑定生成后未改变。最终records35条均无entry/exit日期/价格/open_trade_id/holding字段；volume/PnL/R/lot_count/区间涨跌全部null。
- `git diff --check`通过。浏览器默认周期/筛选/切换/联动缩放及独立全面复核由root接续，本文不冒称这些已完成。

## 反思与边界

本轮没有策略变化/调参/新回测，因此没有新增调参过拟合；选中被拦事件的图形不能替代OOS或证明alpha。继续价值在核验门控语义和被拦的具体市场形态，不是据图挑年份、品种、角度或MA窗口救参。冻结Stage002的负结果和NO_PROMOTION不改变。


## 21:17 缺15分钟缓存文案修订

- root浏览器预检已确认35/20/15、年份/品种筛选、前后导航；周/日真实zoom按钮使两轴[0,242]→[60.5,181.5]同步，console error=0。
- 预检发现canonical缺分钟提示残留“切到已补数交易时恢复”；本页全部35候选均无分钟缓存，会误导。只在本线语义adapter替换成“本页15分钟无缓存、未下载”；勾选15分钟时提示已跳过，不再暗示存在已补数候选。
- 新增回归测试先RED（准确命中误导提示）后GREEN；现在9测试全部通过。
- 旧生成件完整保留于`outputs/stage003_blocked_recap_build_attempt001_before_textfix/`，按完全相同冻结来源重建正式`outputs/stage003_blocked_recap/`，0金融回放/0下载/0生产。
- records、summary、chart_manifest、epoch coverage及旧版本匹配表字节均与上版完全一致，只有adapter/UI文案及对应工具/JS/manifest身份变化；3段JS再次node--check通过，原3141绑定仍前后零变化。
- 新index.html SHA256：`b2331ba0e88c04b70c3335a603b0066be1c60a9ba28dba54e13f91c89df5c249`。本次修文案后浏览器/独立复核由root接续。
