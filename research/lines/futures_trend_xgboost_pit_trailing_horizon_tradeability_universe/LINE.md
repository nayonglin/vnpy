# PIT历史镜像可成交宇宙资格线

- line_id：`futures_trend_xgboost_pit_trailing_horizon_tradeability_universe`
- 创建时间：2026-09-05 02:27 CST
- 上游：已失败闭线的`futures_trend_xgboost_pit_lagged_liquidity_roll_labels`提供冻结动态映射实现和失败机制证据；候选窗口与数据源身份不变。
- 研究问题：能否在query date只用此前一个完整20日标签窗的动态执行可成交记录，事前形成可稳定生成未来20日标签的候选宇宙。
- 当前状态：Stage001唯一全量资格执行已失败闭线；历史因果、候选宽度和选择隔离通过，但入池后仍有347条未来路径失败，不生成标签值、不训练XGBoost。
- 隔离边界：只写本线与registry；不修改上游研究线、正式逻辑回归、CTP、订单或生产文件。

## 当前阶段

- Stage000：`stages/20260905_0227_stage000_trailing_horizon_tradeability_preregistration.md`。
- Stage001计划：`plans/20260905_stage001_trailing_horizon_tradeability_qualification.md`。
- Stage001结果：`stages/20260905_0244_stage001_trailing_horizon_tradeability_fail_close.md`。
- 冻结结果：历史入池`54,085/56,272`条，每qid最小/中位/最大`47/50/58`；未来合格`53,738`、失败`347`；产物`15/15`、输入`8/8`、错误`0`。

## 过拟合反思

- 当前判断：本次不是；继续调历史窗会是。
- 原因：唯一执行前冻结对称20日、100/100和全产品全年度规则；结果显示历史过滤仍留下347条未来失败，并误排348条上一线合格路径。
- 边界：禁止看到结果后修改20日、100/100、30个候选、动态映射排序、产品或年份。

## 继续价值反思

- 当前判断：本线和本组日线流动性救援均无，XGBoost总目标仍有。
- 原因：历史镜像能排除长期不活跃路径，但无法预测流动性状态切换；不得继续加长窗口、提高阈值或按产品删除。后续必须换标签机制，或取得合法的更细粒度执行数据后另立线。
