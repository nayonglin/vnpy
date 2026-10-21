# Stage064 剩余C2精确需求与本地可修复性

- 研究线：futures_ai_monthly_pool_generalization；2026-10-20 23:04 CST记录。只读source覆盖诊断，非重要alpha突破，不改标签、参数、正式或生产。
- 复用052 extractor与058 accepted117 minute adapter，21测试绿；第一次1931窗RO重放20.12秒，分类前缀修正后相同1931窗19.10秒。三份exact mapping/state CSV与12固定trace新旧逐字SHA相同；初跑保留，最终目录outputs/stage064_remaining_c2_local_repair/final_classification。
- 1931窗全部identified，795 exact epoch×source_trade_date/795状态，83产品；34 actualheld不同target、54 roll。1922原first-C2不变，9窗口前推到后续C2；9中4落旧拒绝event、5对应2新event。不能把target代表替代held、交易日当自然日、layer signalday替代fresh episode signalday。
- helper外778event/1889窗：375pre2020/931窗，403当前产品规则unsupported/958窗。helper内17event/42窗：13event/33窗已有056component拒绝（42无行+7缺格+4日OHLC冲突=53component），2event/4窗旧参考范围但无本地候选，另2新event/5窗仅候选。旧132剩33原first未解窗+9后续=42，不把修首阻塞等同恢复整60d。
- 新event：OI202301/2022-08-29影响2窗、2缓存3,120,356bytes；SH202605/2026-03-16影响3窗、4缓存1,622,084bytes和SH605 SQLite native索引候选。6文件4,742,440bytes，已有056rawSHA且当前stat全一致；未重读raw payload。两个345参考grid从8/26及3/13的21:00开始；不伪造physical/session/broker资格。
- 全1737缓存header及Stage861旧metadata库存匹配得77event/157文件候选；没有重扫332MB，没有打开Stage861。117 accepted CSV snapshot为相同058重放核hash，不是新增raw。panel/calendar/econ SHA、源代码链与046b/058同；cleanDB mode=ro/query_only且stat前后不变。静态费用False、逻辑T00、半Roff/C2on、数量/R/roll不变。
- 读SQLite官方URI与CPython官方GitHub sqlite3.rst：使用mode=ro，不以immutable=1跳过变更检查。判断：现存资料确有一个小而有界的新审计范围；只应按相同055核6CSV及SH605投影，不按收益/年份补，不保证5窗known。root已分派067统一输入audit。
- 初分类把两旧056无component/无candidate事件称new，已用新增回归先红后绿修为previous_reference_scope_no_local_native_candidate；source/trace未变。旧代码副本为事后capture、旧测试为反向重建核原SHA，收据明确标注。
- 独立review交monthly_driver_review，机读review待其签发。未做市场fit/下载/label更新/订单；权益、收益、DD、Sharpe、滑点、实际交易次数、胜率N/A。LINE/registry未动。
- 开始/结束新增收益择参过拟合：否，固定全部1931首阻塞cohort与冻结规则、不fit调参；来源后验偏差仍在。继续价值：有，仅限2新event数据资格否证；不应加复杂learner/减floor救分。后续另查有native缓存的CZCE历史session primary资料，不将2020helper倒推历史。
