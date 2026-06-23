# Stage265 执行回放真实包 validator

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：day
- 记录时间：2026-06-22 17:05 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读 broker/production execution replay 真实包验证器；不创建策略规则、不运行 true engine、不触发 A/B、不改官方配置、不连接 CTP/SimNow、不调用 order API
- 是否重要突破：否，非收益突破；是执行回放到货后的第一道实包验收资产
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - Frictionless Table Schema：`https://frictionlessdata.io/specs/table-schema/`
  - JSON Schema object/required properties：`https://json-schema.org/understanding-json-schema/reference/object`
  - Pandera DataFrameSchema：`https://pandera.readthedocs.io/en/latest/dataframe_schemas.html`
  - Great Expectations Checkpoint：`https://docs.greatexpectations.io/docs/reference/api/checkpoint_class/`
- 我的判断：实包验收必须显式检查 required files、required columns、manifest 约束、主键/外键式 join 和覆盖计数。Stage265 因此把 Stage261 的 execution replay 模板升级成可执行 validator；但 validator 通过也只是数据证据 ready，不自动生成交易规则。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage265_execution_replay_real_package_validator.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无交易参数；固定验证 `incoming/execution_replay`，要求 Stage261 的 `7` 个文件角色、`5` 张数据表 schema、`219` entry 覆盖、right-tail `18`、bottom-loss `18`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：复用 Stage251 官方 A 臂曲线，`2018-01-02` 至 `2026-06-15`
- 账户规模：复用官方 C9/15w 口径
- 成本口径：复用 Stage251 官方 A 臂，未新增成本假设
- 样本过滤：只读 Stage261 required schema/manifest template、Stage264 package inventory 与 `incoming/execution_replay`
- 策略/归因口径：执行回放真实包验收；不构造信号、不回测候选、不跑 true engine

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`53.2560%`
- 其他关键指标：
  - 决策：`stage265_execution_replay_validator_no_real_package_no_rule`
  - replay root：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_c9_minrisk_highquality/incoming/execution_replay`
  - package candidate：`1`
  - package root exists：`0`
  - package with files：`0`
  - accepted package：`0`
  - required file role：`7`
  - file role pass：`0/7`
  - table schema audit：`0/5`
  - manifest value pass：`0`
  - entry coverage pass：`0`
  - order-trade join pass：`0`
  - package gate：`1/10`，唯一通过项只是未命中 forbidden marker；root、文件角色、schema、manifest、coverage、join、account/book、strategy/true engine 全失败

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage265_execution_replay_real_package_validator/qmt_roll_stage265_c9_minrisk_execution_replay_real_package_validator_report_stage265_execution_replay_real_package_validator_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage265_execution_replay_real_package_validator/qmt_roll_stage265_c9_minrisk_execution_replay_real_package_validator_summary_stage265_execution_replay_real_package_validator_v1.csv`
- orders：不适用，本阶段不生成订单
- daily：官方路径图 `qmt_roll_stage265_c9_minrisk_execution_replay_real_package_validator_official_path_validator_status_stage265_execution_replay_real_package_validator_v1.png`
- quality：
  - `qmt_roll_stage265_c9_minrisk_execution_replay_real_package_validator_package_inventory_stage265_execution_replay_real_package_validator_v1.csv`
  - `qmt_roll_stage265_c9_minrisk_execution_replay_real_package_validator_file_role_audit_stage265_execution_replay_real_package_validator_v1.csv`
  - `qmt_roll_stage265_c9_minrisk_execution_replay_real_package_validator_table_schema_audit_stage265_execution_replay_real_package_validator_v1.csv`
  - `qmt_roll_stage265_c9_minrisk_execution_replay_real_package_validator_manifest_value_audit_stage265_execution_replay_real_package_validator_v1.csv`
  - `qmt_roll_stage265_c9_minrisk_execution_replay_real_package_validator_join_coverage_audit_stage265_execution_replay_real_package_validator_v1.csv`
  - `qmt_roll_stage265_c9_minrisk_execution_replay_real_package_validator_package_gate_stage265_execution_replay_real_package_validator_v1.csv`
  - 视觉图 5 张：official path、file role matrix、schema heatmap、join coverage chart、package gate chart

## 结论

- 本阶段结论：Stage265 已补齐 execution replay 到货后的可执行实包 validator。当前没有真实 broker/production replay 包，`incoming/execution_replay` root 不存在或为空，因此所有核心 gate 仍失败。
- 是否进入下一步：不进入规则、true engine 或 A/B。
- 下一步：
  1. 若真实 execution replay 包到货，先跑 Stage265；只有 accepted package `>=1` 后，才允许进入 Stage260 field/source audit 与 Stage141 promotion contract。
  2. 若没有真实包，继续 Stage264/265 监控与验收，不恢复本地 OHLCV/OI、价量/OI 小组合或阈值切片。
  3. 若出现 partial/invalid package，只修 manifest、文件角色、schema、license/hash、219 覆盖和 order-trade join，不用局部样本做 alpha。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只检查数据合同和 join，不使用收益、回撤、品种、年份、方向或阈值选择规则；它实际降低了伪数据进入规则研究的风险。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值但仍受外部数据约束。
- 原因：Stage265 把 Stage261 的纸面模板变成了实包 validator；后续真实 replay 到货时可以立即验收。当前未发现真实包，所以不能证明目标完成，但继续维护该验收链是必要的。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage265 两条摘要
- 是否更新 `research/registry.md`：否，非跨线正式候选或路线废弃
- 是否追加根目录 `memory.md/back_log.md`：否，非重要收益突破或正式候选
