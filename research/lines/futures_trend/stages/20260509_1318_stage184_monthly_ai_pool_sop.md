# Stage184 月度AI品种池SOP固化

- line_id：`futures_trend`
- 当前模式：day
- 记录时间：2026-05-09 13:18 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：准实盘SOP固化
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - vn.py官方文档强调实盘流程包含接口配置、行情/合约查询、资金持仓监控、策略生命周期管理。
  - `vnpy_ctp` GitHub/PyPI说明其为VeighNa框架CTP交易接口，Mac环境涉及本地编译或动态库处理。
- 我的判断：公开资料支持把月度AI池放在“实盘前数据准备和影子盘SOP”层，而不是塞进交易接口或实时策略生命周期中。月度选品是低频前置决策，应先保证时序、源数据和留痕稳定。

## 本次变更

- 新增脚本：无
- 修改脚本：无
- 删除脚本：无
- 新增文档：`research/lines/futures_trend/SOP_stage78_monthly_ai_pool.md`
- 修改文档：`research/lines/futures_trend/LINE.md`
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：无新增回测
- 账户规模：无
- 成本口径：无
- 样本过滤：无
- 策略/归因口径：月度AI品种池SOP；不修改Stage78正式策略。

## 结果

- 期末权益：无新增
- 总收益：无新增
- 最大回撤：无新增
- Sharpe：无新增
- 总滑点：无新增
- 总交易次数：无新增
- 胜率：无新增
- 其他关键指标：
  - SOP明确每月使用上一个完整月末作为 `eval_date`
  - SOP要求先跑Stage183刷新源，再跑Stage182生成月度live inference池
  - SOP要求检查 `overwrites_official_stage78_eligibility=false`
  - SOP要求检查 `uses_future_label_for_eval_date=false`
  - SOP要求检查 `real_order_enabled=false`
  - 当前判断：暂不抽象成全局skill，先跑2到3个月后再评估

## 输出文件

- report：无
- summary：无
- orders：无
- daily：无
- quality：`research/lines/futures_trend/SOP_stage78_monthly_ai_pool.md`

## 结论

- 本阶段结论：已将月度AI池纳入 futures_trend 研究线SOP，并在 `LINE.md` 中挂入口。
- 是否进入下一步：是。
- 下一步：
  1. 后续每月按SOP执行 Stage183 + Stage182。
  2. 下一步可把SOP和日度影子盘runner做成一个只读 orchestrator，但仍不自动覆盖正式 eligibility。
  3. 连续跑2到3个月后再判断是否抽象为 repo-local skill。

## 过拟合反思

- 运行前判断：否。用户要求纳入SOP，本质是固定操作流程，不是调策略参数。
- 运行后判断：否。SOP只规定数据时序、源刷新、检查项和留痕，没有根据5月Top9结果反向优化。
- 原因：这类流程约束降低实盘操作风险，不增加策略自由度。

## 继续价值反思

- 运行前判断：有价值。月度AI池如果没有SOP，容易出现日线已更新但选品源过期的隐性失真。
- 运行后判断：有价值。
- 原因：SOP把“完整月末、源刷新、安全字段、阶段记录”固定下来，后续影子盘报告的可解释性更强。

## 合入建议

- 是否更新本线 `LINE.md`：已更新。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否，等月度SOP跑过稳定周期或正式接入影子盘再合入总账。
