# Stage057：Stage056 Top14+fu 多周期回测身份闸门停止记录

## 基本信息

- 研究线：`futures_trend_rollover_shape_same_volume`
- 记录时间：2026-08-29 17:37（Asia/Shanghai）
- 工作模式：日间研究模式（`work-type.txt=day`）
- 研究分支：`codex/stage056-ai-top14-plus-fu`
- 计划基线：Stage037 正式物料（AI Top8 + 固定 fu）
- 计划候选：Stage056（同一模型评分 Top14 + 固定 fu，共 15 个品种）
- 计划验证：全周期，以及所有满足数据条件的 1 年、2 年、3 年窗口；每个周期同时包含 1 月起点与 6 月起点

## 本次结论

本次没有运行任何多周期回测，也没有生成资金曲线或统计结果。身份预检在构造 A/C 两组策略之前失败，流程按 `futures-multicycle-validation` 和 `version-ab-experiment` 的 fail-closed 规则停止。

## 身份预检证据

- 研究工作树 HEAD：`309e13828944e21fc617255a70f4d4a9d8360faf`
- 远端 `origin/master`：`a7d8599e9d895aa6fc7c73b25ef7f2e48d4e4c14`
- 研究工作树正式物料：
  - 策略：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`
  - ruleset：`Stage037`
  - source commit：`374df2...`
  - release：`m0016`
  - release commit：`efef...`
- 稳定实盘目录 `/Users/bytedance/Desktop/person/vnpy_production_live`：
  - HEAD：`09aa96a03fb91124be90bd69861be3f834ab6299`
  - ruleset：`Stage021-Q`
  - source commit：`c097...`
  - release：`m0015`
  - release commit：`d090...`

核心冲突是：master/研究工作树所认的正式物料为 Stage037 m0016，但稳定实盘安装仍为 Stage021-Q m0015。A 组无法同时满足“当前 master 正式版”和“当前稳定实盘版”两个身份约束，因此不能把任何后续数值称为正式版对照结果。

## 参数与结果变更

- 新增参数：无
- 修改参数：无
- 删除参数：无
- 新增回测结果：无（身份闸门前停止）
- 修改回测结果：无
- 删除回测结果：无
- 期末权益：未运行
- 总收益：未运行
- 最大回撤：未运行
- Sharpe：未运行
- 总滑点：未运行
- 总交易次数：未运行
- 胜率：未运行
- 是否重要突破版本：否
- 独立 reviewer：未拉取；本次没有产生回测数据

## 生产安全

- 未修改稳定实盘目录
- 未连接 CTP/券商
- 未生成或提交订单
- 订单 API 调用次数：0

## 过拟合与继续价值反思

- 开始前过拟合风险：中等。TopN 从 8 扩到 14 会增加一次离散参数选择，如果继续扫描多个 TopN，容易形成事后挑选。
- 结束后过拟合风险：未变化。本次没有运行回测、没有查看结果，也没有据结果调参。
- 是否值得继续：是，但必须先完成正式物料与稳定实盘身份对齐。身份对齐后，应只跑已冻结的 Top14+fu 与正式基准的固定多周期矩阵，不追加 TopN 扫描。

## 后续事项

1. 通过正式实盘发布流程确认并对齐稳定实盘到 Stage037 m0016，或明确重新定义当前正式基准；不得在研究回测中静默绕过身份闸门。
2. 对齐后重新执行 Stage057 固定多周期矩阵，并生成标准五张图和中文报告。
3. 只有产生真实回测结果后再拉独立 reviewer。
