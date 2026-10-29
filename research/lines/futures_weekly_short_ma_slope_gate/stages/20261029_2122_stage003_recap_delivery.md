# Stage003 拦截候选复盘HTML最终交付

- 时间：2026-10-29 21:22 Asia/Shanghai；line_id=futures_weekly_short_ma_slope_gate；非重要突破，只读展示。
- 最新源为Stage002 C attempt001：20多+15空共35个applied_block=True且前置正选量归零的候选，非35笔真实交易。多头比较Stage001 C，空头比较Stage001 A，34个旧版实际开仓+1个旧候选本就未开。
- 输出：/Users/mac/.codex/worktrees/weekly-short-ma-slope-20261029/fian/research/lines/futures_weekly_short_ma_slope_gate/outputs/stage003_blocked_recap/index.html；本机预览http://127.0.0.1:8783/index.html，IAB标签保留。HTML单文件嵌入Plotly，可本地打开；完整数据/manifest同目录。
- 复用canonical渲染和既有AST纯函数adapter，其他研究线和Stage001/002文件未变。
- 默认30日K+日K，支持10日/月/周；所有周期联动zoom。无15m缓存且未下载；35候选真实前史不足、13个后50日不足和MA暖机缺值均保留披露。
- 真实信号日close红叉，无成交价/持仓带/PnL/R；另列策略接受周MA5/10前值/本值/delta及11个源周证据，图表自然周MA仅参考。
- 作者与独立9项测试通过；3段JS解析通过；独立116677项数据/聚合MA/源与匹配检查通过，最终PASS_WITH_LIMITATIONS，P0/P1/P2=0/0/0。
- 实际CUA浏览器确认35/20/15、年份品种筛选、前后导航、默认周期、分钟缺失说明、控制台error0；真实Zoom in按钮使周K/日K两轴同步从[0,242]到[60.5,181.5]，matches=x。QA和两张截图由独审另行绑定。
- 修正过一处canonical缺分钟文案：不再暗示35页中另有补数交易；新增测试RED→GREEN，旧生成目录完整保留，五类records/数据表字节不变。图形数据、策略和回测参数未变。
- 原Stage0013105与Stage0023141绑定最终均保持。回测0、行情下载0、CTP/订单/生产访问0、策略改动0。
- 结束过拟合：否，只读核对既有账本，无调参；但不能用选定图形反向挑品种/年份/窗口救Stage002负结果。继续价值：有，帮助用户理解拦截位置和MA方向；不新增alpha/生产晋级证据。
- 结果与源码本地提交，不push/merge；保持与44池解耦。
