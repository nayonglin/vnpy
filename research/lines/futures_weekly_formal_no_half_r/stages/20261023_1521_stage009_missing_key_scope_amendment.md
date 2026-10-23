# Stage009 G002之前的新增缓存范围修订

- line_id：futures_weekly_formal_no_half_r；记录时间：2026-10-23T15:21+08:00；day；重要突破：否。
- G001在2026-10-23 15:14、任何成交前因completed_minute_source_overlap_conflict失败；未产生完整绩效，失败目录/全部原始输入和工具保持不变。
- 根因：CF005.CZCE 2020-01-02 09:00与21:00，旧Stage859 first-seen未完成分钟为volume0/OHLC等于open；新完成raw的H/L/C/volume/close_oi不同。不是OI标准化。两key均不在预声明353请求集合，而来自宽快照的额外canonical派生。
- 外部/源码判断：已按systematic-debugging定位到Stage859 seen_ids不更新已出现分钟的机制；原始来源和完整边界证据均保留，不能覆盖旧基准、换09:01、删品种或借后验收益选择输入。

## 统一规则，在任何G完整绩效之前冻结

1. 旧base与所有旧proof依然用旧merge_verified_layers全字段1e-8严格互校，任何旧层冲突拒绝。
2. 所有新增G片段先互相严格比较，任何新新冲突拒绝。然后对所有旧库已有keys一律不导入新值（同值也一样），只补原不存在keys；不能只处理两个坏key。全部excluded keys及原/新values、冲突字段、请求身份写完整ledger。
3. 若被排除冲突属于原353预取请求，立即拒绝；若任何实际fill或anchor请求命中被排除冲突，最终整窗拒绝。请求包含退出/换月，不能只检查预取信号。
4. 旧CF零量bar保持原值；实际消费零量继续触发原执行接受门。严格缺锚、canonical时间/价格/量、持仓日真实日线、成本/账户守恒均保持。
5. G001宽scope失败保留。新增v2 runner/控制器/范围辅助函数，不改任何已冻结工具、行情、旧proof或旧输出。不把本修订称作成功回测或行情字段修复。
6. G数据入口仅消费新增缺失键，算法与旧基准的缓存只补缺目标一致；所有raw/proof与scope manifest形成SHA闭包。同窗、原19、MA5/10/20、ready21/storage41、halfR/C2/AI=False及所有资金/执行条件不变。
7. 只派生新增raw的catalog wrapper是data-only范围选择，旧119全市场源已有完整canonical与SHA收据，继续由旧输入提供；不改变既有数据。

## 评价与反思

- 已由独立fullmarket_data_audit在无G收益时复核规则可接受；最终结果仍需该agent全审。
- 过拟合判断：否，修复的是预绩效数据范围冲突，不根据收益/赢家或单笔盈亏筛选；同历史窗重复研究依然非OOS。
- 继续价值判断：是，旧值不改、实际消费冲突必拒绝后，仍可完成用户明确指定三均线原19单一消融；不扩大策略搜索。
- 新增参数：数据scope missing_keys_only_v1；修改/删除alpha参数：无；新增/修改/删除绩效：均无（G001仅失败证据）。
