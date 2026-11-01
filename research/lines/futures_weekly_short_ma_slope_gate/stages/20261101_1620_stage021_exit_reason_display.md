# Stage021 年度逐笔复盘的中文平仓原因展示

- line_id：futures_weekly_short_ma_slope_gate。
- 记录时间：2026-11-01 16:20，Asia/Shanghai。
- 工作区/分支：weekly19-official-20261031/fian；codex/weekly19-official-20261031。
- 阶段性质：对已接受Stage020离线复盘的显示修复；不是新回测、alpha变更或正式发布。
- 是否重要突破：否。是否触发A/B：否。与44品种线隔离，未改其他研究线。

## 核查与判断

原页面不是没有退出原因数据，而是仅在一行成交信息中露出英文exit_reason；平仓标记没有原因悬浮提示。冻结原账18轮均有唯一原因，所以应修展示，不应重跑金融数据或猜测退出理由。本次不是新策略研究，没有引入外部策略或参数；直接核查该冻结策略、周线wrapper、实际设置和成交原账，是解释历史退出的事实源。

遵循skills/futures-recap-html/SKILL.md及references/recap-contract.md，复用Stage038的纯函数渲染器；不改canonical renderer或Stage020适配器。采用requesting-code-review要求的独立复核。

## 本次变更

- 新增tools/Stage021_exit_reasons.py：只读原Stage020验收和源pins，按真实平仓trade_id→order_id锚点→信号日/合约/reason事件唯一绑定。
- 页面新增独立中文“平仓原因”卡片，列出规则、当笔依据、触发日、成交交易日、自然时间、实际价格/手数及原始代码；平仓图标悬浮与紫色平仓文字同步说明。
- 页面增加全部18轮原因对照表；无筛选结果时清除旧原因；仅勾选不可绘周期时仍更新对应原因。
- 每条旧record的全部字段、OHLCV、MA、坐标和财务数值保持完全相同，仅新增meta.exit_explanation。summary仅标题/说明计数改变。chart_manifest.csv、closed_rounds.csv字节复制。
- 新增9项Python边界/数据行为检查及215项JS专项检查；保留原Stage020的9项Python/252项JS回归。
- 策略参数新增/修改/删除：均无。原HTML、失败证据、已接受结果均保留。

## 退出语义与证据

18轮为前两周保护退出4、底仓保护价退出5、风险组压力降仓7、组合保证金风控降仓1、换月平旧合约1。trade_events还有未形成实际成交的风控计划，不计入本18轮。

1. long_prev2day_stop沿用旧代码名，但weekly19_frozen/stage029_week_close_exits.py:158–200实际传入完整周bar/history，入场后至少接受2个完成周；父策略取此前两周低点并保持保护价只上移，由周收盘≤保护价确认。本4笔不能译为“前2日”。
2. base_stop为当时有效的底仓保护线，允许动态更新和盈利保护，并非固定2%亏损止损。多头周收盘≤线、空头周收盘≥线。9个技术退出均使用weekly_stop_audit.csv中原triggered记录的close/stop/date，不用成交价反推。
3. 风险组pressure≥0.4时退出配置层base,add,donchian；0.4是标准化压力，不是保证金或亏损40%。原事件未存实际退出pressure及分量，页面明确缺失。
4. 组合模型margin×1.65/交易权益>95%时强减，目标80%，largest_margin优先。原事件未存当时的组合比例，不补造比例；它是策略模型风控，不冒称交易所强平。
5. MA610→MA611换月平旧7手；原换月诊断新手数0、no_positive_volume_allowed，显示“新合约未开仓”，不称已换入。

## 冻结区间与财务

沿用Stage019/020唯一2026-01-01独立起点窗，实际2026-01-05—10-30，198交易日；15万交易资金＋15万场外备用金，固定19品种、无加仓、空头历史底部20%过滤与原风险。

财务完全沿用：期末173100；展示增长15.4%含补资720，交易净利22380/14.92%；最大回撤−36.1614779%；Sharpe0.619534；滑点2930、手续费0；36成交/18轮、8盈10亏、胜率44.44%，平均盈亏比1.580752、PF1.264602；备用金余149280，末仓0。未新增/修改/删除任何回测结果。分钟覆盖仍8轮可绘、10轮缺少已核准分钟，原缺口披露保持。

## 验证与限制

- Python：18项通过（原9＋新9）；未知原因、歧义锚点、错误触发线、改动成交价、跨输出目录均拒绝。
- JS：原252＋新215＝467项静态与合成DOM检查通过，3内嵌脚本解析成功；专项检查在旧Stage020页面因缺少独立卡片而失败，新版通过。
- 288项m0002关键源文件无漂移。没有回测重跑、下载、CTP、生产访问或HTTP服务。
- 真正浏览器因既有file协议安全策略阻断，未尝试其他浏览器/HTTP/CDP绕行。JS检查不是浏览器验收，不声称Plotly实机渲染或指针缩放通过。该限制与原Stage020一致。
- 独立复核：Stage021_review_acceptance.json已签发accepted=true / PASS_WITH_LIMITATIONS，P0/P1/P2=0；502项证据/字段/SHA、236项独立JS、3脚本解析、9项独立Python通过。root复验签名与全部绑定文件；浏览器限制保持。

## 输出与后续

当前入口：artifacts/stage021_2026_exit_reasons/index.html，单文件内嵌Plotly/数据/净值PNG，可直接本地打开；附records、summary、exit_reasons、生成manifest及交付receipt。原Stage020输出保留。

运行前/后过拟合判断均为否：没有改信号、止损、风险、资金规则或筛选历史交易。继续价值均为是：让逐笔退出可以核对原始规则和事件，提高复盘可审计性；不据此调参救历史结果。

合入建议：验收后更新本线LINE.md；不改registry、根memory.md/back_log.md或任何正式物料。下周一既有CTP/安装任务不变。
