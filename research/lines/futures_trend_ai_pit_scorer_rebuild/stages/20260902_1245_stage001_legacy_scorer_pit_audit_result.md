# Stage001 旧正式评分器PIT可重建性审计结果

- line_id：`futures_trend_ai_pit_scorer_rebuild`
- 完成时间：2026-09-02 12:45 CST
- 是否重要突破：否；属于阻止错误模型比较的基础证据
- 决策：`stage001_legacy_pit_audit_complete_allow_fixed_universe_conditional_rebuild`
- 生产/CTP/订单影响：0

## 结论

- 旧正式逻辑回归训练证据不是严格PIT，不能直接作为干净基线继续调XGBoost。
- 可以继续建立“固定当前18品种设计宇宙条件下”的PIT基线：上市资格过滤后每月仍有至少14个品种，主力映射的同日有效OHLC覆盖为100%。
- 无法恢复每个历史月份当时实际批准的策略品种名单，因此后续全周期结果仍有设计宇宙幸存者偏差残余，不能声称“完整历史as-of universe”。

## 标签边界

- 旧samples共`1,332`行=`74月×18品种`，日期`2020-01-23 -> 2026-02-27`。
- 用旧daily逐品种逐日重算未来净利润，最大绝对误差`2.9103830456733704e-11`，证明恢复的标签路径与旧实现一致。
- 旧`9/9`个walk-forward fold均有训练标签进入测试期；累计越界训练行`504`，各fold越界月份为3或4个月。
- 严格边界采用`future_label_end_date < test_start`；等于测试起点也算越界。
- 尾部`36`行、`2`个月只有30至59个未来交易日，不能与完整60日标签混训。

## 上市资格与目标变化

- 未上市样本共`133`行：`SH=44`、`lc=42`、`si=35`、`lh=12`，范围`2020-01-23 -> 2023-08-31`。
- 资格日采用`max(官方上市日, 首条有限且OHLC全正的普通合约日线日)`；18个品种均可解析。
- 先过滤资格、再计算月度横截面future-rank后，保留`1,199`行，旧目标中有`28`行发生变化。
- 每月有效横截面最小`14`，满足后续二分类至少8品种的结构下限。

## 主力映射与宇宙证据

- 旧daily共`1,532`个交易日；上市后主力映射`24,848`行全部能连接同日有限正OHLC，覆盖`100%`。
- 映射来自`TqContCalendar`历史导出，消费端按同日映射；本地没有独立的OI选主算法或原始请求回执，故“历史因果身份”仍不可独立证明。
- samples、当前`PRODUCT_SPECS`与position changes观察品种均为同一18品种；全市场mapping包含更多品种，但没有逐历史月份的策略批准名单。证据等级固定为`fixed_current_design_universe_only`。

## 产物

- `sample_label_boundary_audit.csv`：SHA256=`5c3a5d5484869b126face7bd9ed24ae4cc6d0f2e5d3ee75d5d6f8604552cda87`
- `fold_label_overlap_audit.csv`：SHA256=`0632a9b33dd86660a34ca8f838888a19794271344cf3e1f64df3a1317893a470`
- `listing_eligibility_audit.csv`：SHA256=`e968fefc17954239d7acf92b5800489536b3f32610b481fd5a51b17b30102823`
- `universe_provenance_audit.json`：SHA256=`cb4de4e24af6264da503f39723bc358bfbff5e3c0990db6c77aecbd1aa03e2c1`
- `stage001_summary.json`：SHA256=`9a95f0ea82236a311dd140652ec21cb75160f92f39050b8197a7d817d67da688`
- `artifact_manifest.json`：SHA256=`b5bb746c72d9dd4105ecfcc41cb213084fc3d3e317e39d32eae8088f15b29ca9`
- 测试：`12 passed`；py_compile通过。

## 版本变更与回测记录

- 新增参数：无。
- 修改参数：无。
- 删除参数：无。
- 新增/修改/删除回测结果：均无；本阶段策略回测次数0。
- 期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：均N/A。
- 根目录`back_log.md`未追加，因为没有实际回测数据。

## 运行后反思

- 是否过拟合：本审计本身**否**；若继续沿用旧fold或把当前18品种称为历史as-of宇宙，则**是**。本阶段只按时间和上市事实删除非法信息，没有查看候选策略收益。
- 是否值得继续：**是**。条件PIT基线具备足够横截面和完整映射覆盖，下一步先保持正式`StandardScaler + LogisticRegression(C=0.20)`，只修数据边界；这能把数据修复贡献与XGBoost模型贡献分开。

