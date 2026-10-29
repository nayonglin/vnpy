# Stage003 被MA方向门拦截候选：只读复盘合同

- line_id=futures_weekly_short_ma_slope_gate；2026-10-29；用户请求最新规则拦截多头和空头的复盘HTML。
- 来源唯一绑定Stage002 C attempt001（source HEAD4be2e9389），long/short_ma_slope_decisions applied_block=True共35唯一事件=20多（14case1a+6case2）+15空（case1a）。原选量已0者不纳入。
- 新版事件无实际成交，不存在该事件的真实盈亏、R、成交手数、持仓段或最终平仓。临时canonical适配坐标不得泄漏为实际开平仓。
- 信号标记是signal_date真实同物理合约日K收盘，不是成交价；单列策略已接受观察周MA5/10当前、前值、delta和日期，图表自然周MA只是参考。
- 仅复用标准canonical多周期聚合/蜡烛/坐标/selector/linkedzoom；窄显示语义扩展让其支持被拦候选，不能复制整套HTML或绘图实现。默认30日K+日K，周/月/10日可选，15m源缺失诚实说明。
- 日K信号前300/后50可用交易日、月K前后10月，受真实历史/到期/冻结截止边界限制；精确合约epoch，不做价格代理、补值或十年同名拼接，不下载。
- 对照只读：多头对上一版Stage001 C（short-only），空头对Stage001 A（original），按signal_date/contract/direction/signal四键候选匹配，再以order anchor+fills核对实际开仓。独立预核34个actual_open_matched、1个candidate_not_opened，不能把无成交说成没找到。
- 结果页面显示旧版本匹配开仓证据仅供定位，不将其当新版交易或其反事实利润。
- 输出本线outputs/stage003_blocked_recap/，遵守用户本线隔离要求，覆盖skill默认另一研究线输出目录；canonical文件和其他研究线不改。
- 验收：35记录/方向/源MA/价格/epoch/匹配关系一致，summary.json+chart_manifest.csv+index.html，JavaScript解析、浏览器默认周期/筛选/上一下一/周日联动zoom/缺分钟提示/无假PnL、源哈希前后不变，独立review。
- 本阶段策略回放0、市场下载0、生产访问0、策略改动0。开始过拟合判断：否，只读展示冻结候选；继续价值：是，让用户逐条查看拦截位置与市场后续。可视化不新增alpha或晋级证据。
